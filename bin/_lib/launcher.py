"""入口の殻 bin/works-factory の中身: 利用者の環境から認証と隔離を整え、止めた Archon を bun で起こし、引数をそのまま渡す。

Archon の命令の別名は作らない（持ち主の決め one-launcher）。持つのはつなぎだけで、認証・隔離・プラグインの選び・gh の口・源の取り寄せは
bin/_lib/ の部品を呼ぶ（E15）。順は今の works の works/dev/archon.sh と同じ（計画 docs/plans/2026-10-12-groundwork-line-launcher.md の
B の「約束」1〜11）。止まる時は Archon を起こさない。トークンは読まない・出さない（auth_launch.py が持つ）。
"""
import hashlib
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from bin._lib import hostgh, isolate, pack, place
from lib import answer

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "bin" / "_lib"
NAME = "works-factory"
# 止めた Archon が工程を走らせる命令（packages/cli/src/cli.ts の executesWorkflow と、その前で捌く続きの命令。
# tests/shared/test_archon_contract.py が照らす）
CONTINUING = frozenset({"wake", "signal"})
EXECUTING = frozenset({"run", "resume", "approve", "reject", "respond"}) | CONTINUING
# GitHub の資格は AI の役に渡さない（持ち主の決め auth-middleware）。run の中の gh は、利用者の gh 自身の置き場のログインを
# hostgh の口が継ぎ、役にはその前に置く読むだけの口 works-gh（no-post-bin/）だけが見える（持ち主の決め roles-read-only-gh）
GITHUB_TOKENS = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")


class Stop(Exception):
    """Archon を起こさずに止まる（終了の値つき）。文が空なら、部品が自分の文を出し終えている"""

    def __init__(self, message: str = "", code: int = 2):
        super().__init__(message)
        self.code = code


def main(argv: list[str]) -> int:
    try:
        launch(argv, dict(os.environ), Path.cwd())
    except Stop as stop:
        if str(stop):
            print(f"{NAME}: {stop}", file=sys.stderr)
        return stop.code
    return 0


def launch(argv: list[str], user: dict[str, str], here: Path) -> None:
    flags = before_double_dash(argv)
    if any(a == "--workflow-source" or a.startswith("--workflow-source=") for a in flags):
        raise Stop("--workflow-source は渡さない。自分の工程の置き場は殻が渡す")
    require_command_first(argv)
    workflow = fresh_run_workflow(argv, flags)
    no_auth = user.get("WORKS_FACTORY_NO_AUTH") == "1"
    user_home = user.get("HOME")
    if not user_home:
        raise Stop("HOME が無い。利用者の HOME から認証と置き場を引く")
    raw_config = absolute(user.get("CLAUDE_CONFIG_DIR", ""), here)
    filled_config = raw_config or str(Path(user_home) / ".claude")
    auth = [sys.executable, "-I", str(LIB / "auth_launch.py")]
    auth_user = ["--for", NAME, "--user-home", user_home, "--user-config", raw_config]
    target = target_root(Path(flag_value(flags, "--cwd") or here), here)
    home = run_home(user, target)
    cache = place.cache_dir(user)
    try:
        loaded = pack.load(ROOT)
        source = place.archon_source(loaded, cache)
    except (RuntimeError, ValueError) as error:
        raise Stop(str(error)) from None

    child = isolate.isolate(user, home)
    for name in GITHUB_TOKENS:
        child.pop(name, None)
    shim = hostgh.write(home / "host-gh", user.get("PATH", ""), user_home, hostgh.config_dir(user))
    # gh の無い利用者には口も置かない（並行 PR の確かめが「gh が無い → 役に任せる」の道を通る）
    heads = [str(hostgh.NO_POST_BIN), str(Path(shim).parent)] if shim else []
    child["PATH"] = os.pathsep.join(filter(None, [*heads, user.get("PATH")]))
    child.update(ARCHON_TELEMETRY_DISABLED="1", DO_NOT_TRACK="1", WORKS_FACTORY_ROOT=str(ROOT))
    child[answer.ENV] = answer_head(target)
    child.pop(answer.WHO_ENV, None)  # respond に答えた者の引数は無い
    if not no_auth and mise_trusts(user, target):
        workspaces = Path(child["ARCHON_HOME"]) / "workspaces"
        workspaces.mkdir(parents=True, exist_ok=True)
        child["MISE_TRUSTED_CONFIG_PATHS"] = os.pathsep.join(
            filter(None, [user.get("MISE_TRUSTED_CONFIG_PATHS"), os.path.realpath(workspaces)]))

    executing = len(argv) > 1 and argv[0] == "workflow" and argv[1] in EXECUTING
    if executing and not no_auth:
        check = subprocess.run([*auth, "check", *auth_user], env=user, stdout=subprocess.PIPE, text=True,
                               encoding="utf-8")
        if check.returncode != 0:
            raise Stop(code=check.returncode)
        print(f"{NAME}: 認証は {check.stdout.strip()} から拾う（値は出さない）", file=sys.stderr)
    if executing or argv[:1] == ["validate"]:
        install_toolset(user, child, target, filled_config, plugins=executing and not no_auth)

    if workflow is None:
        archon = [str(source / place.ENTRY), *argv]
    else:
        try:
            workflows = place.workflow_source(loaded, ROOT, cache)
        except RuntimeError as error:
            raise Stop(str(error)) from None
        archon = place.workflow_run(source, workflows, target, workflow, *without_flag(argv[3:], "--cwd"))[1:]
    bun = shutil.which("bun", path=child.get("PATH"))  # 在ることは place.archon_source が確かめ済み
    # bun は打った場所の bunfig.toml の preload を走らせる。対象の物を認証つきの Archon の中で走らせないよう、源の物を名指す
    config = f"--config={source / 'bunfig.toml'}"
    os.execve(sys.executable, [*auth, "exec", *auth_user, "--", bun, config, *archon], child)


def answer_head(target: Path) -> str:
    """関所の文の答えの行の頭: 殻を通して対象を名指した respond（tests/shared/test_archon_contract.py が引数の形を照らす）"""
    return shlex.join([str(ROOT / "bin" / NAME), "workflow", "respond", "--cwd", str(target)])


def require_command_first(argv: list[str]) -> None:
    """殻は命令を引数の位置で見分ける。旗が命令の前に在ると、Archon（旗を抜いた残りで見分ける）と食い違う"""
    command, subcommand = (argv + ["", ""])[:2]
    if command.startswith("-") or (command == "workflow" and subcommand.startswith("-")):
        raise Stop("使い方: works-factory <命令> [<下の命令>] [旗…]（旗は命令の後ろに置く。版は version、手引きは help）")


def fresh_run_workflow(argv: list[str], flags: list[str]) -> str | None:
    """新しい run（workflow run <工程の名>。--resume でない）の工程の名。--cwd と --workflow-source を殻が足すのはこの時だけ"""
    if argv[:2] != ["workflow", "run"] or "--resume" in flags:
        return None
    if len(argv) < 3 or argv[2].startswith("-"):
        raise Stop("使い方: works-factory workflow run <工程の名> [Archon の旗…]")
    return argv[2]


def absolute(value: str, here: Path) -> str:
    """空なら空。相対なら打った場所から絶対に直す"""
    return str(here / value) if value and not os.path.isabs(value) else value


def before_double_dash(argv: list[str]) -> list[str]:
    return argv[:argv.index("--")] if "--" in argv else argv


def flag_value(flags: list[str], name: str) -> str | None:
    for i, a in enumerate(flags):
        if a == name and i + 1 < len(flags):
            return flags[i + 1]
        if a.startswith(name + "="):
            return a[len(name) + 1:]
    return None


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
    chosen = user.get("WORKS_FACTORY_HOME")
    if chosen:
        if not os.path.isabs(chosen):
            raise Stop(f"WORKS_FACTORY_HOME は絶対パスにする（受けた値: {chosen}）")
        return Path(chosen)
    state = user.get("XDG_STATE_HOME") or str(Path(user["HOME"]) / ".local" / "state")
    return Path(state) / NAME / "targets" / hashlib.sha256(str(target).encode()).hexdigest()[:8]


def mise_trusts(user: Mapping[str, str], target: Path) -> bool:
    """利用者の mise が対象の根を信頼済みか（run の worktree は家の下の新しいパスで、対象の根の信頼が効かない）。
    mise は HOME の下のパスを ~/… と出す"""
    mise = shutil.which("mise", path=user.get("PATH"))
    if mise is None:
        return False
    shown = subprocess.run([mise, "trust", "--show"], cwd=target, env=user, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, encoding="utf-8")
    for line in shown.stdout.splitlines():
        path, _, state = line.rpartition(": ")
        if path == "~" or path.startswith("~/"):
            path = user["HOME"] + path[1:]
        if state == "trusted" and path and os.path.realpath(path) == str(target):
            return True
    return False


def install_toolset(user: Mapping[str, str], child: dict[str, str], target: Path, user_config: str, plugins: bool) -> None:
    """隔離した Claude の設定に借りる物だけを入れる。plugins が偽なら plugin の CLI を呼ばない（スキルの名は validate も照らす）"""
    if plugins:
        claude = user.get("CLAUDE_BIN_PATH") or on_absolute_path("claude", user.get("PATH", ""))
        if not claude:
            raise Stop("本物の claude（隔離した設定にプラグインを入れる）が見つからない。CLAUDE_BIN_PATH に絶対パスを設定する")
        how = ["--claude", claude]
    else:
        how = ["--no-plugins"]
    done = subprocess.run([sys.executable, str(LIB / "toolset.py"), "install", *how, "--user-config", user_config,
                           child["CLAUDE_CONFIG_DIR"]], env=child, cwd=target)
    if done.returncode != 0:
        raise Stop(code=done.returncode)


def on_absolute_path(name: str, path: str) -> str | None:
    """PATH の絶対の置き場だけから name を探す。相対の置き場は打った場所の下の物を拾うので使わない"""
    for folder in path.split(os.pathsep):
        if os.path.isabs(folder) and (found := shutil.which(name, path=folder)):
            return found
    return None
