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

from bin._lib import auth_launch, hostgh, isolate, pack, place, recordroot, runstop, specreviews, startpoint
from lib import answer, launchgroups, reads, userenv, writelog

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "bin" / "_lib"
NAME = "works-factory"
# 止めた Archon がグラフを走らせる命令（packages/cli/src/cli.ts の executesWorkflow の run と、run を続ける命令
# packages/cli/src/dispatch-guards.ts の CONTINUE_SUBCOMMANDS と、その前で捌く続きの命令。tests/shared/test_archon_contract.py が照らす）
RESUMING = frozenset({"resume", "approve", "reject", "respond", "answer"})
CONTINUING = frozenset({"wake", "signal"})
EXECUTING = frozenset({"run"}) | RESUMING | CONTINUING
# run のノードが lib/ を探すリポジトリの根（workflows/.shared/ports.py の lib_root が読む名）
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
# TDD の実行器の取り置きの根を script のノードに渡す名（workflows/.shared/ports.py の SUITE_KEEP_ENV と同じ名）
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
# 実行する run の起動で毎回出す 1 行（持ち主の決め target-user-env）。tree_run.outside_env の env で起こす対象のコマンド（数え上げは
# docs/design/archon.md の「対象のコマンドの環境と準備」）は利用者の HOME・XDG で走る。コマンドごとの守りは工場が作らない（隔離が要る人は工場ごと包む）
TARGET_ENV_NOTICE = ("AI が書いた試験のコードを、あなたの権限（利用者の HOME・XDG）で走らせる。書く物も利用者の家に入る。"
                     "守りが要るなら工場ごとコンテナか VM の中で回す")


# 役の claude の会話のキャッシュの寿命の既定（cache_ttl が run の設定の層の env で運ぶ）と、寿命を選ぶ名（Claude Code の
# Choose the TTL yourself の順。promptCacheTtl の設定は 2 つ目と 3 つ目の間）
PROMPT_CACHE_TTL = ("CLAUDE_CODE_PROMPT_CACHE_TTL", "5m")
CHOSEN_TTL_ENVS = ("FORCE_PROMPT_CACHING_5M", PROMPT_CACHE_TTL[0], "ENABLE_PROMPT_CACHING_1H", "ENABLE_PROMPT_CACHING_1H_BEDROCK")
# 対象の下の Archon の repo 設定の置き場（対象からの相対。packages/core/src/config/config-loader.ts の loadRepoConfig が読む場所の写しで、
# tests/shared/test_archon_contract.py が照らす）
REPO_CONFIG = (".archon", "config.yaml")


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
        refuse_renamed_inputs(workflow, flags)
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
    cache_from = "XDG_CACHE_HOME" if user.get("XDG_CACHE_HOME") else "HOME"
    refuse_relative(cache_from, cache)
    refuse_sandbox_writable(cache_from, cache)
    try:
        loaded = pack.load(ROOT)
        source = place.archon_source(loaded, cache)
    except (RuntimeError, ValueError) as error:
        raise Stop(str(error)) from None

    profile = {"settings": {}, "env": {}, "drop": []}
    executing = len(argv) > 1 and argv[0] == "workflow" and argv[1] in EXECUTING
    if executing and not no_auth:
        try:
            managed = Path(user[auth_launch.MANAGED_DIR_ENV]) if user.get(auth_launch.MANAGED_DIR_ENV) else auth_launch.default_managed_dir()
            # 包み（HOME 基準の AWS の資格を本当の HOME で出す物）は、write_fence の --own の top の下に置く（役は書き換えられない）
            profile, notice = auth_launch.connection_profile(
                filled_config, user, managed, lambda name, body: hostgh.place_shim(home / FENCE_DIR, name, body))
        except ValueError as error:
            raise Stop(str(error)) from None
        if notice:   # 運んだ provider・出どころ・渡したファイル・名指す物の 1 行（値は出さない。無ければ告げない）
            print(f"{NAME}: {notice}", file=sys.stderr)
        user = auth_launch.profile_env(user, profile)
    child = isolate.isolate(user, home)
    # 名の持ち主は最終起動の包み。秘密をファイルや引数へ焼かず、env でだけ渡す。
    child[place.shared("fence").PROFILE_ENV] = json.dumps(profile)
    # GitHub の資格は AI の役に渡さない（持ち主の決め auth-middleware）。run の中の gh は、利用者の gh 自身の置き場のログインを
    # hostgh の口が継ぐ。script のノード（出口の語 pr の時に push と PR の作成をする archon-pr の publish も）は PATH の頭の
    # この口を打つ。役の claude には書き込みの柵の包みが PATH の頭に読むだけの口 works-gh（no-post-bin/）を足し（write_fence の
    # path_heads）、script のノードが起こす対象のコマンド（AI が書いた試験のコードも走る）には tree_run.outside_env が同じ口を
    # PATH の頭に足す（置き場は userenv.READ_GH_ENV で渡す）ので、どちらにも works-gh が先に見える（持ち主の決め roles-read-only-gh）。
    # 環境変数だけでログインする利用者の値は、gh の読まない名（hostgh.RELAY）で口へ渡す
    for name in hostgh.TOKENS:
        child.pop(name, None)
    shim = hostgh.write(home / HOST_GH_DIR, user.get("PATH", ""), user_home, hostgh.config_dir(user))
    if shim:
        child.update(hostgh.relay(user))
    # gh の無い利用者には口も置かない（並行 PR の確かめが「gh が無い → 役に任せる」の道を通る）
    child["PATH"] = os.pathsep.join(filter(None, [str(Path(shim).parent) if shim else "", user.get("PATH")]))
    role_heads = [str(hostgh.NO_POST_BIN)] if shim else []
    if shim:
        child[userenv.READ_GH_ENV] = str(hostgh.NO_POST_BIN)
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
    if executing:
        try:
            place.write_provider_cap(Path(child["ARCHON_HOME"]), place.provider_cap(user))
        except ValueError as error:
            raise Stop(str(error)) from None
        # 上限は置き場の設定として残り、渡さない起動も同じ置き場の上限の下で走る（Archon はリクエストのたびに読み直す）
        if (effective := place.read_provider_cap(Path(child["ARCHON_HOME"]))) is not None:
            print(f"{NAME}: claude の同時数の上限 {effective} が効いている（{Path(child['ARCHON_HOME']) / place.CAP_FILE}）",
                  file=sys.stderr)
        elif place.flow_cap_unread(Path(child["ARCHON_HOME"])):
            print(f"{NAME}: 上限の設定が 1 行の形で在るかもしれず、殻は値を読めない（{Path(child['ARCHON_HOME']) / place.CAP_FILE}）",
                  file=sys.stderr)
    real = None
    if executing:
        real = real_claude(user)
        if not real:
            raise Stop("本物の claude（隔離した設定にプラグインを入れ、役を起こす）が見つからない。CLAUDE_BIN_PATH に絶対パスを設定する")
        if user.get(CLAUDE_BIN_ENV):   # 利用者が起動方法（ラッパー）を置いた時だけ、その認証を check・exec が確かめる（読むのは殻のまま）
            auth_user += ["--runtime", user[CLAUDE_BIN_ENV]]
    if executing and not no_auth:
        # 隔離した子の環境で確かめる（exec と同じ見え方。役と同じ環境で起動方法の認証を確かめる）
        check = subprocess.run([*auth, "check", *auth_user], env=dict(child), stdout=subprocess.PIPE, text=True,
                               encoding="utf-8")
        if check.returncode != 0:
            raise Stop(code=check.returncode)
        print(f"{NAME}: 認証は {check.stdout.strip()} から拾う（値は出さない）", file=sys.stderr)
    if executing or argv[:1] == ["validate"]:
        install_toolset(child, target, filled_config, claude=real if not no_auth else None)
    if executing:
        sweep_logs(child["CLAUDE_CONFIG_DIR"])
        keep = suite_keep(user)
        keep.mkdir(parents=True, exist_ok=True)
        child[SUITE_KEEP_ENV] = str(keep)
        child[CLAUDE_BIN_ENV] = write_fence(home, real, child, cache, keep, role_heads)
        child[FENCE_RECORDS_ENV] = str(fence_records(home))

    if workflow is None:
        args = argv
    else:
        try:
            workflows = place.workflow_source(loaded, ROOT, cache)
        except RuntimeError as error:
            raise Stop(str(error)) from None
        rest = without_flag(without_flag(argv[3:], "--cwd"), "--config")
        config = run_config(bun, source, cache, home, target, flags,
                            spec_reviews(workflow, flags, user, child, place.archon(bun, source), home, target))
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
    if argv[:2] == ["workflow", "run"] and "--detach" not in flags:
        # 殻が入れ替わらず子で走らせ、終わった所で run の記録の置き場を告げる（切り離す run は殻が待たないので告げない）
        return recordroot.run_and_say(command, child, place.archon(bun, source), str(target), NAME)
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
    """run のノード（script・bash）に渡す環境変数: lib/ を探すリポジトリの根（workflows/.shared/ports.py の lib_root）と、承認ノードの
    文の答えの行の頭（answer_head）"""
    return {ROOT_ENV: str(ROOT), answer.ENV: answer_head(home, target)}


def spec_reviews(workflow: str, flags: list[str], user: Mapping[str, str], child: dict, head: list[str], home: Path,
                 target: Path) -> dict[str, str]:
    """仕様駆動の道の表を名指した起動（メイングラフの spec_table・block の table）だけ、会話で回した審査の記録を Archon の run の記録と照らし
    （bin/_lib/specreviews.py。docs/design/spec-driven.md の 2.6 の 2）、結果のファイルを run の設定の層の env で渡す。合わなければ
    Archon を起こさずに止める。表を名指さない起動は表も記録も読まず、uv も起こさず、{} を返す"""
    table = specreviews.named_table(workflow, flag_values(flags, "--input"))
    if table is None:
        return {}
    uv = shutil.which("uv", path=user.get("PATH"))
    if not uv:
        raise Stop("仕様駆動の道の表（YAML）を読むのに uv が要る（Archon の script のノードを回すのと同じ uv）。uv を PATH に置く")
    try:
        doc = specreviews.check(target, table, lambda t, name: specreviews.read_table(uv, t, name, dict(user)),
                                specreviews.archon_get(head, target, child))
    except RuntimeError as error:
        raise Stop(str(error)) from None
    bad = specreviews.problems(doc)
    if bad:
        raise Stop("仕様駆動の道の表か、会話で回した審査の記録が照らしに合わない（Archon を起こさずに止めた）:\n"
                   + "\n".join(f"- {line}" for line in bad))
    path = specreviews.write(home, doc)
    print(f"{NAME}: 会話で回した審査の記録 {len(doc['rows'])} 件を run の記録と照らした（{path}）", file=sys.stderr)
    return {specreviews.RESULT_ENV: str(path)}


def cache_ttl(*carried: Mapping) -> dict[str, str]:
    """役の claude の会話のキャッシュの寿命の既定を、run の設定の層の env に載せる {名: 値}。carried は工場の run だけに効く層の env
    （利用者の --config の env: と、対象の .archon/config.yaml の env:）。
    (a) carried のどれかが CHOSEN_TTL_ENVS の名を持てば {}（その選びは Archon が運び、載せると潰す）。
    (既定) 無ければ {PROMPT_CACHE_TTL}。
    利用者の shell の env は見ない（持ち主の決め factory-cache-ttl。訳は docs/design/archon.md）。

    訳: 加入の利用者では、Claude Code が会話のキャッシュの寿命を既定で 1 時間にし、書き込みの単価が 5 分の 2 倍になる。工場の役の会話は
    ノードをまたいだキャッシュの読みが無く、5 分を超える間も少ないので、書き直しを減らす向きで 5 分を既定にする。1 時間に戻す道は
    carried の層に ENABLE_PROMPT_CACHING_1H=1 を書くこと。出典: https://code.claude.com/docs/en/prompt-caching の Choose the TTL yourself。

    運び方: 役の claude は Archon が起こすので、子の env に置いても CLAUDE_CODE_* の掃除で消える。Archon が AI のノードの env に重ねる層は下から
    対象の .archon/config.yaml の env:、Archon の DB の codebase の env、run の設定の層の env で、どれも掃除の後に重なり、workflow: の子の
    run も受け継ぐ（docs/design/archon.md）。だから run の層の env に載せる。run の層の 5m は、CHOSEN_TTL_ENVS の順で下の層の同じ名と
    ENABLE_PROMPT_CACHING_1H に勝つので、選びが有る時は載せない。

    見られない選び: Archon の DB の codebase の env（Archon の server の API だけが書き、殻から読む口が無い）と、管理の設定（managed
    settings）の promptCacheTtl と、対象の .archon/.env が入れる ENABLE_PROMPT_CACHING_1H は、載せた 5m に負けて上書きされる。前に始めた
    run を続ける起動は、封じた層を戻すので、この既定を載せる前に始めた run は 1 時間のまま。

    対象の .archon/config.yaml は殻が --cwd の対象から読む（repo_env）。新しい run では Archon も同じ --cwd の config.yaml を、commit して
    いない変更や git の無視に入れた変更も含めて読むので、殻と Archon は同じ物を見る。--adopt の起動では、この既定を載せない（run_config が
    呼ばない）: 引き継ぐ run は repo の config を、枝を取り出して作った写し（task branch の commit）か、既に在る作業ツリーから読み、--cwd の
    物とは別なので、殻はそこに寿命の選びが在るか見られず、載せると repo の選び（.archon/config.yaml の env:）を潰しうる"""
    if any(name in env for env in carried for name in CHOSEN_TTL_ENVS):
        return {}
    return dict([PROMPT_CACHE_TTL])


def repo_env(bun: str, source: Path, target: Path) -> Mapping | None:
    """対象の .archon/config.yaml の env:（Archon が AI のノードの env の一番下の層に重ねる物）。ファイルが無ければ bun を起こさず {}、env: が
    無い・object でなければ {}。読めなければ（Archon もこのファイルを読めずに止まる）訳を標準エラーに 1 行言って None"""
    path = target.joinpath(*REPO_CONFIG)   # 対象の根（--cwd。git の木の中なら git の根）
    if not path.is_file():
        return {}
    try:
        doc = place.read_yaml(bun, source, path)
    except RuntimeError as error:
        print(f"{NAME}: {error}。対象の .archon/config.yaml が読めないので寿命の既定を載せない（Archon もこのファイルを読めずに止まる）",
              file=sys.stderr)
        return None
    env = doc.get("env") if isinstance(doc, dict) else None
    return env if isinstance(env, dict) else {}


def run_config(bun: str, source: Path, cache: Path, home: Path, target: Path, flags: list[str],
               extra: Mapping[str, str] | None = None) -> Path:
    """新しい run に渡す設定の層（place.run_config。--adopt の時は群の別名を除く）。利用者の --config があれば合わせる。Archon は
    --config を 1 つしか読まず後ろの物を採り、相対のパスは対象（--cwd）から引くので、ここも同じに読む。工場の値だけの層は秘密を
    持たないので取り置き cache に、利用者の層を合わせた物（env の秘密が入りうる）は対象の家 home（run_home。Archon の DB と封じた層を
    解く鍵の置き場）に置き、家と一緒に消える。

    層の env には run のノードに渡す環境変数（run_env）に加え、役の claude の会話のキャッシュの寿命の既定（cache_ttl）も載る。選びを
    潰さないため、利用者の --config の env: と対象の .archon/config.yaml の env:（repo_env）を読んで cache_ttl に渡す。対象の config.yaml が
    読めなければ寿命の既定を載せない。--adopt の起動は寿命の既定を載せず、対象の config.yaml も読まない: 引き継ぐ run は repo の config を
    --cwd の物でなく、枝の写しか既存の作業ツリーから読むので、殻はそこに寿命の選びが在るか見られない（cache_ttl の docstring）"""
    adopt = adopting(flags)
    env, aliases = {**run_env(home, target), **(extra or {})}, not adopt
    mine = (flag_values(flags, "--config") or [None])[-1]
    layer = {}
    if mine:
        try:
            layer = place.read_run_config(bun, source, target / mine)
        except RuntimeError as error:
            raise Stop(str(error)) from None
    repo = {} if adopt else repo_env(bun, source, target)
    ttl = {} if adopt or repo is None else cache_ttl(layer.get("env", {}), repo)
    if not mine:
        return place.run_config(cache, {**ttl, **env}, aliases=aliases)
    replaced = sorted(set(layer.get("aliases", {})) & set(launchgroups.GROUPS)) if aliases else []
    if replaced:
        print(f"{NAME}: --config の群の別名 {'・'.join(replaced)} は工場の値で上書きした。群の値の付け替えは --model @wf-<群>=<模型>",
              file=sys.stderr)
    return place.run_config(home, {**ttl, **env}, layer, aliases=aliases)


def refuse_unknown_groups(flags: list[str]) -> None:
    """--model @wf-<群>=… の群の名が lib/launchgroups.py の表に無ければ止める。工場の接頭辞 @wf- でない名は Archon に任せる"""
    named = [value.split("=", 1)[0] for value in flag_values(flags, "--model")]
    unknown = [name for name in named if name.startswith("@wf-") and name not in launchgroups.GROUPS]
    if unknown:
        raise Stop(f"--model の群 {'・'.join(unknown)} は群の表（lib/launchgroups.py）に無い。知っている群: {'・'.join(launchgroups.GROUPS)}")


RENAMED_INPUTS = {"design_only": "design_talk"}   # 名の替わった入力（古い名 → 新しい名。#827）
RENAMED_FOR = ("works-factory-line", "works-factory-chain")   # 名を替えたグラフ（ほかの block の同じ名の port は替えていない）


def refuse_renamed_inputs(workflow: str, flags: list[str]) -> None:
    """メイングラフと周の鎖に古い名の --input を渡したら止め、新しい名を案内する（Archon も知らない入力として拒むが、新しい名は言わない）"""
    if workflow not in RENAMED_FOR:
        return
    named = [value.split("=", 1) for value in flag_values(flags, "--input")]
    old = [(name, rest[0] if rest else "") for name, *rest in named if name in RENAMED_INPUTS]
    if old:
        raise Stop("\n".join(f"--input {name}=… は名が替わった。--input {RENAMED_INPUTS[name]}={value or 'true'} で渡す"
                             for name, value in old))


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
        refuse_relative(HOME_ENV, chosen)
        refuse_sandbox_writable(HOME_ENV, chosen)
        refuse_in_factory(HOME_ENV, chosen)
        return Path(chosen)
    home = factory_state(user) / "targets" / hashlib.sha256(str(target).encode()).hexdigest()[:8]
    what = "XDG_STATE_HOME" if user.get("XDG_STATE_HOME") else "HOME"
    refuse_relative(what, home)
    refuse_sandbox_writable(what, home)
    refuse_in_factory(what, home)
    return home


def refuse_relative(what: str, path) -> None:
    """相対パスの置き場は打った場所の下を指すので拒む（isolate も相対の家を受けない）"""
    if not os.path.isabs(path):
        raise Stop(f"{what} は絶対パスにする（受けた値: {path}）")


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


def write_fence(home: Path, real: str, child: Mapping[str, str], cache: Path, keep: Path, path_heads: list[str]) -> str:
    """Archon が役を起こす claude の前に置く包み（埋め P5。workflows/.shared/fence.py）の殻を書き、そのパスを返す。値は env でなく
    殻に焼く（Archon は claude に渡す env を掃除する）。-B は Archon がバイトで照らす workflows/ に __pycache__ を作らないため。
    --own は、同じ run の後の役の起動が sandbox の外で走らせる物（この殻・gh の口・包みを起こす解釈系〔sys.prefix と sys.base_prefix〕・本物の claude・
    child の PATH の絶対の置き場にある claude を全部〔real がラッパーの時にラッパーが起こす claude も、ラッパー自身が PATH の先頭で本物が後ろの
    置き場に在る時の本物も守る。相対の置き場を退ける決まりは on_absolute_path の 1 か所〕）と、
    次の起動が sandbox の外で走らせる物（取り置き cache〔Archon の源〕・TDD の実行器の取り置き keep・工場の checkout の根 ROOT 全体）。根は丸ごと禁じる。bin/works-factory は
    ROOT を import の先頭に置くので、根に新しく置いた shlex.py や bin.py が次の起動の import に勝つ。
    本物の claude は実パスで起こす（包みは --own を実パスに解いて禁じるので、symlink を通して起こすと symlink 自身は書ける）。
    --records は印の在る起動の記録（fence_records。--own の top の下なので役は書き換えられない）。
    --path-head は役の claude の PATH の頭に足す置き場（path_heads。読むだけの gh の口の置き場）"""
    top = home / FENCE_DIR
    real = os.path.realpath(real)
    on_path = [found for folder in child.get("PATH", "").split(os.pathsep) if (found := on_absolute_path("claude", folder))]
    own = [top, home / HOST_GH_DIR, sys.prefix, sys.base_prefix, real, *map(os.path.realpath, on_path), cache, keep, ROOT]
    body = ("#!/bin/sh\n"
            "# works-factory の起動（bin/_lib/launcher.py）が書いた包み: 読むだけの役の claude の sandbox に、起こす直前に組んだ\n"
            "# 書き込みを禁じるパスの一覧を足す\n"
            + "exec " + shlex.join([sys.executable, "-I", "-B", str(FENCE), "--real", real,
                                    "--archon-home", child["ARCHON_HOME"], "--claude-config", child["CLAUDE_CONFIG_DIR"],
                                    *(arg for path in dict.fromkeys(map(str, own)) for arg in ("--own", path)),
                                    "--records", str(fence_records(home)),
                                    *(arg for head in path_heads for arg in ("--path-head", head))])
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
