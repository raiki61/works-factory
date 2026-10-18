"""入口の殻 bin/works-factory の中身: 利用者の環境から認証と隔離を整え、止めた Archon を bun で起こし、引数をそのまま渡す。

Archon の命令の別名は作らない（持ち主の決め one-launcher）。持つのはつなぎだけで、認証・隔離・プラグインの選び・gh の口・源の取り寄せ・
run の作業ツリーの起点は bin/_lib/ の部品を呼ぶ（E15）。順は今の works の works/dev/archon.sh と同じ（計画 docs/plans/2026-10-12-groundwork-line-launcher.md の
B の「約束」1〜11。約束 7 の後半——道具の信頼を子の環境に足す当て物——は消した。場所ごとの信頼は対象の宣言の setup で取り戻す）。止まる時は Archon を起こさない。トークンは読まない・出さない（auth_launch.py が持つ）。
"""
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from bin._lib import hostgh, isolate, pack, place, runstop, startpoint
from lib import answer, launchgroups, reads, writelog

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "bin" / "_lib"
NAME = "works-factory"
# 止めた Archon がグラフを走らせる命令（packages/cli/src/cli.ts の executesWorkflow の run と、run を続ける命令
# packages/cli/src/dispatch-guards.ts の CONTINUE_SUBCOMMANDS と、その前で捌く続きの命令。tests/shared/test_archon_contract.py が照らす）
RESUMING = frozenset({"resume", "approve", "reject", "respond", "answer"})
CONTINUING = frozenset({"wake", "signal"})
EXECUTING = frozenset({"run"}) | RESUMING | CONTINUING
# run のノードが lib/ を探すリポジトリの根（workflows/.shared/boundary.py の lib_root が読む名）
ROOT_ENV = "WORKS_FACTORY_ROOT"
# 読むだけと分かった上の命令。ほか（trigger・chat・serve・殻の知らない命令）は AI を走らせうるので認証に通す
READING = frozenset({"validate", "version", "help"})
HOME_ENV = "WORKS_FACTORY_HOME"   # 利用者が選ぶ家（run_home）
NO_AUTH_ENV = "WORKS_FACTORY_NO_AUTH"   # 認証の要らない起動（lib/entryshape.py の NO_AUTH_ENV と同じ名）
HOST_GH_DIR = "host-gh"
FENCE_DIR = "claude-fence"
FENCE = ROOT / "workflows" / ".shared" / "fence.py"
# 包みが印の在る起動を書く記録（fence.py の RECORDS_ENV と同じ名）。子の env に置くと、run が包みを通ると script のノードに宣言する
FENCE_RECORDS_ENV = "WORKS_FACTORY_FENCE_RECORDS"
FENCE_RECORDS = "launches.jsonl"
# TDD の実行器の取り置きの根を script のノードに渡す名（workflows/.shared/boundary.py の SUITE_KEEP_ENV と同じ名）
SUITE_KEEP_ENV = "WORKS_FACTORY_SUITE_KEEP"
SUITE_KEEP = "suites"
# run の中のノードが殻を入れ子にせず同じ Archon を起こす命令の頭を置く名（名の持ち主は読む側の埋め P7）
ARCHON_CLI_ENV = place.shared("childsweep").CLI_ENV
CLAUDE_BIN_ENV = "CLAUDE_BIN_PATH"   # Archon が起こす claude の実行ファイル（packages/providers/src/claude/binary-resolver.ts）
# Archon が起きた場所から読む env のファイル。.env* が名指す鍵は env から消し（packages/paths/src/strip-cwd-env.ts）、.archon/.env の
# 値で env を上書きする（packages/paths/src/env-loader.ts。CLAUDE_BIN_PATH は拒む鍵に無い）。--detach の子は --cwd の場所で起きる
# （packages/cli/src/commands/workflow.ts の spawnDetachedWorkflowRun）。<ARCHON_HOME>/.env も上書きで読む（env-loader.ts の
# loadArchonEnv。archon setup の既定の書き先で、claude の置き場を CLAUDE_BIN_PATH に書く）
ARCHON_CWD_ENV_FILES = (".env", ".env.local", ".env.development", ".env.production", ".archon/.env")
# 書く役の sandbox の Bash が書ける置き場（Claude の一時の置き場）。家・対象・取り置きがこの下だと、書く役が書き込みの記録・控え・DB・
# 対象の .git・取り置いた Archon の源（次の起動が sandbox の外で起こす）を書き換えられる。形は今の works の dev/guard.sh の
# works_dev_refuse_claude_tmp と同じ（実パスで照らす。* は / も越える）。読むだけの役（allowWrite が / ）はどこでも書けるので、
# この照らしでは守れない。その役からは write_fence の --own が取り置きと工場の根を守る
SANDBOX_WRITABLE = ("/tmp/claude-*", "/private/tmp/claude-*")
# 実行する run の起動で毎回出す 1 行（持ち主の決め target-user-env）。対象の試験・受け入れ・TDD の試験のコマンドは利用者の HOME・XDG で走る。
# コマンドごとの守りは工場が作らない（隔離が要る人は工場ごと包む）
TARGET_ENV_NOTICE = ("AI が書いた試験のコードを、あなたの権限（利用者の HOME・XDG）で走らせる。書く物も利用者の家に入る。"
                     "守りが要るなら工場ごとコンテナか VM の中で回す")


class Stop(Exception):
    """Archon を起こさずに止まる（終了の値つき）。文が空なら、部品が自分の文を出し終えている"""

    def __init__(self, message: str = "", code: int = 2):
        super().__init__(message)
        self.code = code


def main(argv: list[str]) -> int:
    try:
        return launch(argv, dict(os.environ), Path.cwd())
    except Stop as stop:
        if str(stop):
            print(f"{NAME}: {stop}", file=sys.stderr)
        return stop.code


def launch(argv: list[str], user: dict[str, str], here: Path) -> int:
    """Archon を起こす。workflow cancel だけは子として起こして終了の値を返し（止めた後の木の残りを止める。埋め P13 の runstop）、
    ほかは Archon に置き換わって戻らない"""
    flags = before_double_dash(argv)
    if any(a == "--workflow-source" or a.startswith("--workflow-source=") for a in flags):
        raise Stop("--workflow-source は渡さない。自分のグラフの置き場は殻が渡す")
    require_command_first(argv)
    workflow = fresh_run_workflow(argv, flags)
    if workflow is not None:
        refuse_unknown_groups(flags)
    no_auth = user.get(NO_AUTH_ENV) == "1"
    user_home = user.get("HOME")
    if not user_home:
        raise Stop("HOME が無い。利用者の HOME から認証と置き場を引く")
    raw_config = absolute(user.get("CLAUDE_CONFIG_DIR", ""), here)
    filled_config = raw_config or str(Path(user_home) / ".claude")
    auth = [sys.executable, "-I", str(LIB / "auth_launch.py")]
    auth_user = ["--for", NAME, "--user-home", user_home, "--user-config", raw_config]
    target = target_root(Path(flag_value(flags, "--cwd") or here), here)
    refuse_sandbox_writable("対象", target)
    home = run_home(user, target)
    cache = place.cache_dir(user)
    refuse_sandbox_writable("XDG_CACHE_HOME" if user.get("XDG_CACHE_HOME") else "HOME", cache)
    try:
        loaded = pack.load(ROOT)
        source = place.archon_source(loaded, cache)
    except (RuntimeError, ValueError) as error:
        raise Stop(str(error)) from None

    child = isolate.isolate(user, home)
    # GitHub の資格は AI の役に渡さない（持ち主の決め auth-middleware）。run の中の gh は、利用者の gh 自身の置き場のログインを
    # hostgh の口が継ぎ、役にはその前に置く読むだけの口 works-gh（no-post-bin/）だけが見える（持ち主の決め roles-read-only-gh）。
    # 環境変数だけでログインする利用者の値は、gh の読まない名（hostgh.RELAY）で口へ渡す
    for name in hostgh.TOKENS:
        child.pop(name, None)
    shim = hostgh.write(home / HOST_GH_DIR, user.get("PATH", ""), user_home, hostgh.config_dir(user))
    if shim:
        child.update(hostgh.relay(user))
    # gh の無い利用者には口も置かない（並行 PR の確かめが「gh が無い → 役に任せる」の道を通る）
    heads = [str(hostgh.NO_POST_BIN), str(Path(shim).parent)] if shim else []
    child["PATH"] = os.pathsep.join(filter(None, [*heads, user.get("PATH")]))
    child.update(ARCHON_TELEMETRY_DISABLED="1", DO_NOT_TRACK="1", **{place.PROVIDER_ENV: place.DEFAULT_PROVIDER})
    bun = shutil.which("bun", path=child.get("PATH"))  # 在ることは place.archon_source が確かめ済み
    child[ARCHON_CLI_ENV] = json.dumps(place.archon(bun, source))

    executing = len(argv) > 1 and argv[0] == "workflow" and argv[1] in EXECUTING
    if executing and workflow is None:
        # 前に始めた run を続ける命令。#679 より前に始めた run は封じた層に ROOT_ENV を持たない。層を持つ run では層の値が勝つ
        child[ROOT_ENV] = str(ROOT)
    if executing:
        refuse_bin_override([where / name for where in dict.fromkeys([here, here / (flag_value(flags, "--cwd") or "."), target])
                             for name in ARCHON_CWD_ENV_FILES] + [Path(child["ARCHON_HOME"]) / ".env"])
    if executing and not no_auth:
        check = subprocess.run([*auth, "check", *auth_user], env=user, stdout=subprocess.PIPE, text=True,
                               encoding="utf-8")
        if check.returncode != 0:
            raise Stop(code=check.returncode)
        print(f"{NAME}: 認証は {check.stdout.strip()} から拾う（値は出さない）", file=sys.stderr)
    real = None
    if executing:
        real = real_claude(user)
        if not real:
            raise Stop("本物の claude（隔離した設定にプラグインを入れ、役を起こす）が見つからない。CLAUDE_BIN_PATH に絶対パスを設定する")
    if executing or argv[:1] == ["validate"]:
        install_toolset(child, target, filled_config, claude=real if not no_auth else None)
    if executing:
        sweep_logs(child["CLAUDE_CONFIG_DIR"])
        keep = suite_keep(user)
        keep.mkdir(parents=True, exist_ok=True)
        child[SUITE_KEEP_ENV] = str(keep)
        child[CLAUDE_BIN_ENV] = write_fence(home, real, child, cache, keep)
        child[FENCE_RECORDS_ENV] = str(fence_records(home))

    if workflow is None:
        args = argv
    else:
        try:
            workflows = place.workflow_source(loaded, ROOT, cache)
        except RuntimeError as error:
            raise Stop(str(error)) from None
        rest = without_flag(without_flag(argv[3:], "--cwd"), "--config")
        config = run_config(bun, source, cache, home, target, flags)
        try:
            start, said = startpoint.choose(flags, workflow, target, f"{NAME}-")
        except RuntimeError as error:
            raise Stop(str(error)) from None
        if said:
            print(f"{NAME}: {said}", file=sys.stderr)
        args = place.workflow_run(source, workflows, config, target, workflow, *start, *rest)[2:]
    if executing:   # 止まる所を全部過ぎた後（起こさずに止まる起動は走らせないので、告げない）
        print(f"{NAME}: {TARGET_ENV_NOTICE}", file=sys.stderr)
    if argv[:2] == ["workflow", "cancel"]:
        return runstop.cancel(place.archon(bun, source), args, child, flag_value(flags, "--cwd"))
    command = [*place.archon(bun, source), *args]
    if not reads_only(argv):
        command = [*auth, "exec", *auth_user, "--", *command]
    os.execve(command[0], command, child)


def reads_only(argv: list[str]) -> bool:
    """認証を通さずに Archon を起こしてよい命令か: workflow の走らせない命令と、読むだけと分かった上の命令"""
    if argv[:1] == ["workflow"]:
        return argv[1:2] != [] and argv[1] not in EXECUTING
    return argv[:1] != [] and argv[0] in READING


def answer_head(home: Path, target: Path) -> str:
    """承認ノードの文の答えの行の頭: 家を env で名指し、殻を通して対象を名指した respond（家を選ぶ値の無いシェルで打っても同じ run の
    DB に届く。tests/shared/test_archon_contract.py が殻の後ろの引数の形を照らす）"""
    return shlex.join(["env", f"{HOME_ENV}={home}", str(ROOT / "bin" / NAME), "workflow", "respond", "--cwd", str(target)])


def require_command_first(argv: list[str]) -> None:
    """殻は命令を引数の位置で見分ける。旗が命令の前に在ると、Archon（旗を抜いた残りで見分ける）と食い違う"""
    command, subcommand = (argv + ["", ""])[:2]
    if command.startswith("-") or (command == "workflow" and subcommand.startswith("-")):
        raise Stop("使い方: works-factory <命令> [<下の命令>] [旗…]（旗は命令の後ろに置く。版は version、手引きは help）")


def fresh_run_workflow(argv: list[str], flags: list[str]) -> str | None:
    """新しい run（workflow run <グラフの名>。--resume でない）のグラフの名。--cwd・--workflow-source・--config（run_config）を殻が
    足すのはこの時だけ。続ける命令（RESUMING）は、Archon が起動の時に封じた層を戻す"""
    if argv[:2] != ["workflow", "run"] or "--resume" in flags:
        return None
    if len(argv) < 3 or argv[2].startswith("-"):
        raise Stop("使い方: works-factory workflow run <グラフの名> [Archon の旗…]")
    return argv[2]


def adopting(flags: list[str]) -> bool:
    """記録のある run を引き継ぐ起動（--adopt）か。Archon はその run の記録した AI の設定を受け継ぎ、aliases を持つ --config の層を
    「Cannot override AI configuration inherited from a recorded run.」で拒む（packages/workflows/src/run-preflight.ts）。env と
    workflows の層は受け、引き継ぐ run の層は受け継がない"""
    return any(a == "--adopt" or a.startswith("--adopt=") for a in flags)


def run_env(home: Path, target: Path) -> dict[str, str]:
    """run のノード（script・bash）に渡す環境変数: lib/ を探すリポジトリの根（workflows/.shared/boundary.py の lib_root）と、承認ノードの
    文の答えの行の頭（answer_head）"""
    return {ROOT_ENV: str(ROOT), answer.ENV: answer_head(home, target)}


def run_config(bun: str, source: Path, cache: Path, home: Path, target: Path, flags: list[str]) -> Path:
    """新しい run に渡す設定の層（place.run_config。--adopt の時は群の別名を除く）。利用者の --config があれば合わせる。Archon は
    --config を 1 つしか読まず後ろの物を採り、相対のパスは対象（--cwd）から引くので、ここも同じに読む。工場の値だけの層は秘密を
    持たないので取り置き cache に、利用者の層を合わせた物（env の秘密が入りうる）は対象の家 home（run_home。Archon の DB と封じた層を
    解く鍵の置き場）に置き、家と一緒に消える"""
    env, aliases = run_env(home, target), not adopting(flags)
    mine = (flag_values(flags, "--config") or [None])[-1]
    if not mine:
        return place.run_config(cache, env, aliases=aliases)
    try:
        layer = place.read_run_config(bun, source, target / mine)
    except RuntimeError as error:
        raise Stop(str(error)) from None
    replaced = sorted(set(layer.get("aliases", {})) & set(launchgroups.GROUPS)) if aliases else []
    if replaced:
        print(f"{NAME}: --config の群の別名 {'・'.join(replaced)} は工場の値で上書きした。群の値の付け替えは --model @wf-<群>=<模型>",
              file=sys.stderr)
    return place.run_config(home, env, layer, aliases=aliases)


def refuse_unknown_groups(flags: list[str]) -> None:
    """--model @wf-<群>=… の群の名が lib/launchgroups.py の表に無ければ止める。工場の接頭辞 @wf- でない名は Archon に任せる"""
    named = [value.split("=", 1)[0] for value in flag_values(flags, "--model")]
    unknown = [name for name in named if name.startswith("@wf-") and name not in launchgroups.GROUPS]
    if unknown:
        raise Stop(f"--model の群 {'・'.join(unknown)} は群の表（lib/launchgroups.py）に無い。知っている群: {'・'.join(launchgroups.GROUPS)}")


def absolute(value: str, here: Path) -> str:
    """空なら空。相対なら打った場所から絶対に直す"""
    return str(here / value) if value and not os.path.isabs(value) else value


def before_double_dash(argv: list[str]) -> list[str]:
    return argv[:argv.index("--")] if "--" in argv else argv


def flag_values(flags: list[str], name: str) -> list[str]:
    """name の旗の値の全部（name 値 と name=値。前から順に読み、値に取った字は旗として読まない）"""
    out, i = [], 0
    while i < len(flags):
        a = flags[i]
        if a == name and i + 1 < len(flags):
            out.append(flags[i + 1])
            i += 1
        elif a.startswith(name + "="):
            out.append(a[len(name) + 1:])
        i += 1
    return out


def flag_value(flags: list[str], name: str) -> str | None:
    return (flag_values(flags, name) or [None])[0]


def without_flag(args: list[str], name: str) -> list[str]:
    """args から name の旗とその値を抜く（-- の後ろは文なので触らない）"""
    cut = args.index("--") if "--" in args else len(args)
    out, skip = [], False
    for a in args[:cut]:
        if skip:
            skip = False
        elif a == name:
            skip = True
        elif not a.startswith(name + "="):
            out.append(a)
    return out + args[cut:]


def target_root(cwd: Path, here: Path) -> Path:
    """対象の実のパス。git の木の中なら git の根（同じ clone の下のどこから打っても同じ家になる）"""
    real = Path(os.path.realpath(here / cwd))
    if not real.is_dir():
        raise Stop(f"対象のフォルダ {real} が無い")
    try:
        top = subprocess.run(["git", "-C", str(real), "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                             encoding="utf-8")
    except FileNotFoundError:
        raise Stop("git が無い。対象の根を git で決める") from None
    return Path(os.path.realpath(top.stdout.strip())) if top.returncode == 0 else real


def run_home(user: Mapping[str, str], target: Path) -> Path:
    """Archon の DB と隔離した置き場の根。対象ごとに 1 つで起動をまたいで同じ（run・respond・resume が同じ DB を見る）"""
    chosen = user.get(HOME_ENV)
    if chosen:
        if not os.path.isabs(chosen):
            raise Stop(f"{HOME_ENV} は絶対パスにする（受けた値: {chosen}）")
        refuse_sandbox_writable(HOME_ENV, chosen)
        refuse_in_factory(HOME_ENV, chosen)
        return Path(chosen)
    home = factory_state(user) / "targets" / hashlib.sha256(str(target).encode()).hexdigest()[:8]
    what = "XDG_STATE_HOME" if user.get("XDG_STATE_HOME") else "HOME"
    refuse_sandbox_writable(what, home)
    refuse_in_factory(what, home)
    return home


def factory_state(user: Mapping[str, str]) -> Path:
    """家を選ばない起動の、利用者ごとの工場の置き場（隔離の前の XDG_STATE_HOME の下）"""
    return Path(user.get("XDG_STATE_HOME") or str(Path(user["HOME"]) / ".local" / "state")) / NAME


def suite_keep(user: Mapping[str, str]) -> Path:
    """TDD の実行器の取り置きの根（持ち主の決め suite-by-ai）。利用者ごとに 1 つで、対象をまたいで使い回す。選んだ家の下か、
    家を選ばない起動では対象ごとの家（targets/）の兄弟"""
    chosen = user.get(HOME_ENV)
    keep = (Path(chosen) if chosen else factory_state(user)) / SUITE_KEEP
    refuse_sandbox_writable("TDD の実行器の取り置き", keep)
    refuse_in_factory("TDD の実行器の取り置き", keep)
    return keep


def sandbox_writable(path) -> bool:
    real = os.path.realpath(path)
    return any(fnmatch.fnmatchcase(real, pattern) for pattern in SANDBOX_WRITABLE)


def refuse_sandbox_writable(what: str, path) -> None:
    if sandbox_writable(path):
        raise Stop(f"{what} の置き場 {os.path.realpath(path)} は /tmp/claude-* の下で、役の sandbox の Bash が書ける。"
                   "ほかの置き場を選ぶ")


def refuse_in_factory(what: str, path) -> None:
    """家が工場の checkout（ROOT）の下だと、ROOT を丸ごと禁じる柵（write_fence の --own）に家も入り、読むだけの役が隔離した HOME や
    一時の置き場に書けない"""
    real = Path(os.path.realpath(path))
    if real.is_relative_to(ROOT):
        raise Stop(f"{what} の置き場 {real} は工場の checkout {ROOT} の下で、読むだけの役の書き込みの柵に入り役が家に書けない。"
                   "checkout の外を選ぶ")


def install_toolset(child: dict[str, str], target: Path, user_config: str, claude: str | None) -> None:
    """隔離した Claude の設定に借りる物だけを入れる。claude が無ければ plugin の CLI を呼ばない（スキルの名は validate も照らす）"""
    how = ["--claude", claude] if claude else ["--no-plugins"]
    done = subprocess.run([sys.executable, str(LIB / "toolset.py"), "install", *how, "--user-config", user_config,
                           child["CLAUDE_CONFIG_DIR"]], env=child, cwd=target)
    if done.returncode != 0:
        raise Stop(code=done.returncode)


def real_claude(user: Mapping[str, str]) -> str | None:
    return user.get(CLAUDE_BIN_ENV) or on_absolute_path("claude", user.get("PATH", ""))


def refuse_bin_override(env_files: list[Path]) -> None:
    """Archon が起きる時に読む env のファイルが CLAUDE_BIN_PATH か WORKS_FACTORY_FENCE_RECORDS を名指すなら止める。前者が名指されると
    Archon は殻が向けた包みの殻を消すか置き換え、読むだけの役が柵の無い claude で起きる。後者は受け付けが読む包みの宣言を消すか
    ほかの記録へ向ける"""
    for env_file in env_files:
        for key in (CLAUDE_BIN_ENV, FENCE_RECORDS_ENV):
            if names_key(env_file, key):
                raise Stop(f"{env_file} が {key} を名指す。Archon が書き込みの柵の包みかその宣言を外すので、そこから消す"
                           + (f"（claude の置き場は殻を起こす env に {CLAUDE_BIN_ENV} で置く）" if key == CLAUDE_BIN_ENV else ""))


def names_key(path: Path, key: str) -> bool:
    """dotenv の形のファイル path が鍵 key の行を持つか（無い・読めないファイルは持たない）"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(re.match(rf"\s*(?:export\s+)?{re.escape(key)}\s*[=:]", line) for line in text.splitlines())


def write_fence(home: Path, real: str, child: Mapping[str, str], cache: Path, keep: Path) -> str:
    """Archon が役を起こす claude の前に置く包み（埋め P5。workflows/.shared/fence.py）の殻を書き、そのパスを返す。値は env でなく
    殻に焼く（Archon は claude に渡す env を掃除する）。-B は Archon がバイトで照らす workflows/ に __pycache__ を作らないため。
    --own は、同じ run の後の役の起動が sandbox の外で走らせる物（この殻・gh の口・包みを起こす解釈系〔sys.prefix と sys.base_prefix〕・本物の claude）と、
    次の起動が sandbox の外で走らせる物（取り置き cache〔Archon の源〕・TDD の実行器の取り置き keep・工場の checkout の根 ROOT 全体）。根は丸ごと禁じる。bin/works-factory は
    ROOT を import の先頭に置くので、根に新しく置いた shlex.py や bin.py が次の起動の import に勝つ。
    本物の claude は実パスで起こす（包みは --own を実パスに解いて禁じるので、symlink を通して起こすと symlink 自身は書ける）。
    --records は印の在る起動の記録（fence_records。--own の top の下なので役は書き換えられない）"""
    top = home / FENCE_DIR
    real = os.path.realpath(real)
    own = [top, home / HOST_GH_DIR, sys.prefix, sys.base_prefix, real, cache, keep, ROOT]
    body = ("#!/bin/sh\n"
            "# works-factory の起動（bin/_lib/launcher.py）が書いた包み: 読むだけの役の claude の sandbox に、起こす直前に組んだ\n"
            "# 書き込みを禁じるパスの一覧を足す\n"
            + "exec " + shlex.join([sys.executable, "-I", "-B", str(FENCE), "--real", real,
                                    "--archon-home", child["ARCHON_HOME"], "--claude-config", child["CLAUDE_CONFIG_DIR"],
                                    *(arg for path in dict.fromkeys(map(str, own)) for arg in ("--own", path)),
                                    "--records", str(fence_records(home))])
            + ' -- "$@"\n')
    return hostgh.place_shim(top, "claude", body)


def fence_records(home: Path) -> Path:
    return home / FENCE_DIR / FENCE_RECORDS


def sweep_logs(config: str) -> None:
    """作業の場が無くなった run の書き込みと読んだ証拠の記録を片付ける（writelog.sweep）。片付けは run の正しさに効かないので、
    しくじっても止めない"""
    for what, root in (("書き込みの記録", writelog.root(config)), ("読んだ証拠の記録", reads.root(config))):
        try:
            gone, failed = writelog.sweep(root)
        except OSError as error:
            print(f"{NAME}: 前の run の{what}を片付けられなかった（{error}）。run は続ける", file=sys.stderr)
            continue
        if failed:
            print(f"{NAME}: 前の run の{what}を {len(failed)} 件片付けられなかった（初めの 1 件: {failed[0]}）。run は続ける",
                  file=sys.stderr)
        if gone:
            print(f"{NAME}: 作業の場が無くなった run の{what}を {len(gone)} 件片付けた", file=sys.stderr)


def on_absolute_path(name: str, path: str) -> str | None:
    """PATH の絶対の置き場だけから name を探す。相対の置き場は打った場所の下の物を拾うので使わない"""
    for folder in path.split(os.pathsep):
        if os.path.isabs(folder) and (found := shutil.which(name, path=folder)):
            return found
    return None
