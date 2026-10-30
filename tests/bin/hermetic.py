"""試験を走らせた場に左右されない子の環境と一時フォルダ（test_* でないので unittest の発見に拾われない）。

試験の子へ親の環境を丸ごと渡すと、run の中（Archon・Claude Code の子）で親が立てた名が漏れて、その場でだけ赤くなる。
tox の pass_env と同じ向きで、外す名はここの 1 か所に置き、試験が意図して渡す名は child_env の overrides で名指しする。
試験が起こす子の環境を作るのはここだけ（os.environ を手で写す口と env を渡さない子の起こしは層の柵 E21 が赤にする）。
試験を回す口 tests/shard.py は、試験を集める前に scrub で自分の過程からも同じ名を外す（過程の中で読む既定の環境も場に依らない）。
利用者の環境を継ぐのが用途の試験（本物の役で回す試験）は、外す前の値を inherited で名指しして引く。
Archon が script の節に立てる変数の名は pack の口 .shared/ports.py が持ち、ここは引くだけ（runner_vars）。
macOS の一時フォルダは /var→/private/var の symlink の下にあり、pathlib の relative_to は字面で比べるので、比べる試験は
tmpdir の実体のパスを使う。
"""
import ast
import atexit
import functools
import json
import os
import pathlib
import shutil
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
# pack の口（pack.json の ours.folder の .shared/ports.py。組み込みの入れ替えの前も後も同じ口。docs/design/integration.md の 4.5-8）
PORTS = ROOT / json.loads((ROOT / "pack.json").read_text(encoding="utf-8"))["ours"]["folder"] / ".shared" / "ports.py"

# run が立てる名（bin/ の起動・Claude Code・graphloops の engine の子の目印）。Archon が script の節に立てる名は ports が持つので
# ここに写さない（dropped が runner_vars を引く）。
# ANTHROPIC_ は起こし役（bin/_lib/auth_launch.py）が受け継いだ認証として先に拾い、keychain の段の試験を素通りさせる。
# HERDR_ は herdr の枠の中で試験を回すと、殻が控えに本物の枠とサーバを残して本物の herdr へ送る（枠の試験は名指しで渡す）。
# WORKS_ANSWER_CMD は起動の殻が run に置く答えの行の頭（lib/answer.ENV）で、関所の文が既定で読む
DROPPED_PREFIXES = ("WORKS_FACTORY_", "CLAUDE_", "ARCHON_", "ANTHROPIC_", "HERDR_")
DROPPED = frozenset({"CLAUDECODE", "GRAPHLOOPS_ENGINE_CHILD", "WORKS_ANSWER_CMD"})
# 試験の用意が過程の中で読む名（Archon の源の置き場と、見送りを赤にする旗と、手元の確かめで Archon を起こさない旗。読むのは
# tests/archon.py。手元の旗は tests/shard.py の --paths が立てる）。scrub はこれを残す。ARCHON_DEFERRED は手元の旗で見送る時の訳の頭で、
# tests/shard.py が見送った試験の名を並べる時に引く
ARCHON_CACHE_ENV = "WORKS_FACTORY_ARCHON_CACHE"
ARCHON_REQUIRED_ENV = "WORKS_FACTORY_ARCHON_REQUIRED"
ARCHON_DEFER_ENV = "WORKS_FACTORY_ARCHON_DEFER"
ARCHON_SETUP = (ARCHON_CACHE_ENV, ARCHON_REQUIRED_ENV, ARCHON_DEFER_ENV)
ARCHON_DEFERRED = "Archon を起こす試験は手元では回さず CI に任せる"
_SCRUBBED: dict = {}


@functools.cache
def runner_vars() -> dict:
    """pack の口 ports.py の RUNNER_PREFIXES・RUNNER_NAMES（字から読む）。import しない: ports は import すると lib/ を sys.path に足し、
    __pycache__ を避ける作法も要る"""
    tree = ast.parse(PORTS.read_text(encoding="utf-8"))
    return {t.id: ast.literal_eval(n.value.args[0] if isinstance(n.value, ast.Call) else n.value)
            for n in tree.body if isinstance(n, ast.Assign) for t in n.targets
            if isinstance(t, ast.Name) and t.id in ("RUNNER_PREFIXES", "RUNNER_NAMES")}


def dropped(name: str) -> bool:
    runner = runner_vars()
    return (name in DROPPED or name.startswith(DROPPED_PREFIXES)
            or name in runner["RUNNER_NAMES"] or name.startswith(tuple(runner["RUNNER_PREFIXES"])))


# 起動の殻が読む、会社が配る設定の置き場の差し替えの口（bin/_lib/auth_launch.py の MANAGED_DIR_ENV。import しない: bin/ を sys.path に足さない）
MANAGED_DIR_ENV = "WORKS_FACTORY_MANAGED_DIR"


@functools.cache
def empty_managed_dir() -> str:
    """会社が配る設定の置き場の代わりの空のフォルダ（過程ごとに 1 つ。過程の終わりに消す）。殻を通る試験が、機械に会社の設定
    （apiKeyHelper など）が在っても本物を読まないための物"""
    folder = tempfile.mkdtemp(prefix="works-managed-")
    atexit.register(shutil.rmtree, folder, ignore_errors=True)
    return folder


def child_env(**overrides) -> dict:
    """os.environ から dropped の名を外し、会社が配る設定の置き場を空のフォルダへ向け、overrides を上に置いた子の環境"""
    env = {k: v for k, v in os.environ.items() if not dropped(k)}
    env[MANAGED_DIR_ENV] = empty_managed_dir()
    env.update(overrides)
    return env


def scrub() -> None:
    """この過程の os.environ から dropped の名を外す（試験の用意の名 ARCHON_SETUP は残す）。
    試験が過程の中で読む既定の環境も走らせた場に依らなくなる。外した名と値は inherited が引く"""
    for name in [k for k in os.environ if dropped(k) and k not in ARCHON_SETUP]:
        _SCRUBBED[name] = os.environ.pop(name)


def inherited(*prefixes: str) -> dict:
    """試験を回し始めた時の環境（scrub の前）のうち、名が prefixes のどれかで始まる名と値。利用者の環境を継ぐのが用途の試験
    （本物の役で回す試験の旗と認証）だけが、要る名をここで名指しして引く"""
    return {k: v for k, v in {**_SCRUBBED, **os.environ}.items() if k.startswith(prefixes)}


def tmpdir(case, **kw) -> pathlib.Path:
    """実体のパス（realpath）の一時フォルダ。case（unittest.TestCase）の後始末で消す"""
    d = pathlib.Path(os.path.realpath(tempfile.mkdtemp(**kw)))
    case.addCleanup(shutil.rmtree, d, ignore_errors=True)
    return d
