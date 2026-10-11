"""ASF が止めた版（factory/pack.json）の Archon の源を 1 度だけ取り、Archon の本体と ASF の工程の両方をそこから使う。自分の工程は置かずに起こす。

- Archon の本体: 源の packages/cli/src/cli.ts を bun で起こす（ASF の factory/consumer.py の cli() と同じ形）。
- ASF の工程: 源の中の asf.folder（factory/pack.json の source_directory）。ASF の工程を回す時は --workflow-source に源を渡す。
- 自分の工程: Archon の家に写さない。Archon は --workflow-source <dir> の <dir>/.archon/workflows/ を読み、run の始めに
  その中身を run の物として写し取る（Archon の packages/workflows/src/workflow-source.ts）。だからその場所がリポジトリの
  workflows/ を指す小さな置き場を作り、そこを --workflow-source に渡す。

Archon の家（$ARCHON_HOME/workflows など）には何も置かない。
"""
import hashlib
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

ENTRY = "packages/cli/src/cli.ts"
WORKFLOW_FOLDER = ".archon/workflows"

Fetch = Callable[[str, str, Path], None]
Install = Callable[[Path], None]


def git_fetch(repo: str, commit: str, dest: Path) -> None:
    """repo（clone できる URL）の commit を dest に取り出す（dest は作る）"""
    subprocess.run(["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", repo, str(dest)], check=True)
    subprocess.run(["git", "-C", str(dest), "checkout", "--quiet", "--detach", commit], check=True)


def bun_install(source: Path) -> None:
    """源の bun.lock のとおりに依存を入れる。lock は書き換えない"""
    subprocess.run(["bun", "install", "--frozen-lockfile"], cwd=source, check=True)


def archon_source(pack: dict, cache: Path, fetch: Fetch = git_fetch, install: Install = bun_install) -> Path:
    """Archon の源を <cache>/archon/<commit>/ に取り、依存を入れて返す。在れば照らしてから使い、取らない。

    bun が無い・取れない・依存が入らない・本体か ASF の工程が源に無ければ、途中まで取った物を残さず（前に取った物は残す）、
    何が取れなかったかを 1 行の RuntimeError で言う。在った物が照らしに合わなければ、消して取り直す案内つきの RuntimeError。
    """
    if shutil.which("bun") is None:
        raise RuntimeError("bun が無い。Archon の源は bun で起こす。入れ方は https://bun.sh")
    archon = pack["archon"]
    dest = cache / "archon" / archon["commit"]
    if dest.is_dir():
        _verify(dest, archon["commit"])
        return dest

    def fill(staging: Path) -> None:
        try:
            fetch(archon["repo"], archon["commit"], staging)
            install(staging)
            missing = [rel for rel in (ENTRY, pack["asf"]["folder"]) if not (staging / rel).exists()]
            if missing:
                raise FileNotFoundError(f"源に {', '.join(missing)} が無い")
        except Exception as error:
            reason = " ".join(str(error).split()) or type(error).__name__
            raise RuntimeError(f"Archon の源 {archon['repo']} {archon['commit']} が取れない: {reason}") from error

    _replace(dest, fill)
    return dest


def workflow_source(pack: dict, root: Path, cache: Path) -> Path:
    """--workflow-source に渡す置き場を返す。その中の .archon/workflows は root の自分の工程のフォルダを指す。

    置き場の名は指す先のパスの hash なので、同じ root からは同じ置き場になる。
    """
    target = (root / pack["ours"]["folder"]).resolve()
    shim = cache / "workflow-source" / hashlib.sha256(str(target).encode()).hexdigest()[:16]
    link = shim / WORKFLOW_FOLDER
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except FileExistsError:
        if not (link.is_symlink() and link.readlink() == target):
            raise RuntimeError(f"{link} が {target} を指していない。消して回し直せば作り直す（rm -r \"{link}\"）") from None
    except OSError as error:
        raise RuntimeError(f"{link} に {target} への symlink が作れない: {error.strerror or error}") from error
    return shim


def workflow_run(source: Path, workflow_dir: Path, cwd: Path, name: str, *args: str) -> list[str]:
    """工程 name を workflow_dir から読み、cwd に対して回す命令。

    --cwd と --workflow-source は利用者の引数より前に置く。利用者の -- の後ろに付くと、文として渡り、
    Archon が cwd の工程を探す元の動きに黙って戻る（ASF の factory/consumer.py と同じ並べ）。
    """
    return [
        "bun", str(source / ENTRY),
        "workflow", "run", "--cwd", str(cwd), "--workflow-source", str(workflow_dir),
        name, *args,
    ]


def _verify(source: Path, commit: str) -> None:
    """取り置いた源の 3 つを照らす: HEAD が commit・git status --porcelain --untracked-files=all が空・node_modules が在る。
    依存（node_modules）は源の .gitignore に入るので status には出ない。
    ASF の factory/consumer.py の verify_source の照らしの一部で、無視・未追跡の工程ファイル・symlink・必須のファイルの欠けは見ない"""
    def git(*args: str) -> str:
        done = subprocess.run(["git", "-C", str(source), *args], capture_output=True, text=True)
        return done.stdout.rstrip("\n") if done.returncode == 0 else f"git {args[0]} が失敗: {done.stderr.strip()}"

    head = git("rev-parse", "HEAD")
    changed = git("status", "--porcelain", "--untracked-files=all")
    if head != commit:
        problem = f"HEAD が {commit} でない（{head}）"
    elif changed:
        problem = f"変更が在る（{', '.join(line[3:] for line in changed.splitlines()[:5])}）"
    elif not (source / "node_modules").is_dir():
        problem = "node_modules が無い"
    else:
        return
    raise RuntimeError(f"取り置いた Archon の源 {source} が壊れている: {problem}。消して回し直せば取り直す（rm -rf \"{source}\"）")


def _replace(target: Path, fill: Callable[[Path], None]) -> None:
    """target の横の一時の置き場を fill で作り切ってから入れ替える。fill の途中で止まっても前の target は残る"""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent, prefix=f".{target.name}.") as tmp:
        staging = Path(tmp) / "new"
        fill(staging)
        if target.exists():
            target.rename(Path(tmp) / "old")
        staging.rename(target)
