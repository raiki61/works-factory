"""ASF が止めた版（factory/pack.json）の Archon の源を 1 度だけ取り、Archon の本体と ASF のグラフの両方をそこから使う。自分のグラフは置かずに起こす。

- Archon の本体: 源の packages/cli/src/cli.ts を bun で起こす（ASF の factory/consumer.py の cli() と同じ形）。
- ASF のグラフ: 源の中の asf.folder（factory/pack.json の source_directory）。ASF のグラフを回す時は --workflow-source に源を渡す。
- 自分のグラフ: Archon の家に写さない。Archon は --workflow-source <dir> の <dir>/.archon/workflows/ を読み、run の始めに
  その中身を run の物として写し取る（Archon の packages/workflows/src/workflow-source.ts）。だからその中の
  .archon/workflows/<pack>/ がリポジトリの workflows/ を指す小さな置き場を作り、そこを --workflow-source に渡す。
  pack の形にするのは、Archon が名前の script を pack のグラフの時だけグラフのフォルダの scripts/ から探し、
  pack の部品を <pack>/.shared/ から読むため（Archon の packages/workflows/src/script-discovery.ts）。

Archon の家（$ARCHON_HOME）には、工場が決める値（home_config）を書いた config.yaml のほかは何も置かない（$ARCHON_HOME/workflows など）。
AI ノードの群の別名（'@wf-<群>'）は家に書かず、新しい run に run 1 本ぶんの設定の層（run_config）で渡す。
"""
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType

from lib import launchgroups

ENTRY = "packages/cli/src/cli.ts"
SHARED = Path(__file__).resolve().parents[2] / "workflows" / ".shared"
WORKFLOW_FOLDER = ".archon/workflows"
# Archon は既定の provider の無い run を始めで拒む（packages/provider-contract/src/registration.ts の NO_DEFAULT_PROVIDER_MESSAGE）。
# 工場の役は claude で書いてあり、Archon の文書の口は家の config.yaml の defaultAssistant（docs-web の reference/configuration.md）。
# グラフごとの provider: では、手を加えない ASF のグラフに届かない
DEFAULT_PROVIDER = "claude"
PROVIDER_KEY = re.compile(r"^defaultAssistant\s*:", re.MULTILINE)
# Archon の既定（true）は、使用枠の上限に当たった run を落とさず paused で待たせる。工場の回復の道（落ちた run を別のアカウントで
# resume する）と fan_out の子の起こし方がその待ちに効くかは未実測なので、落とす形のまま置く（docs/owner-decisions.md の
# asf-follows-dev の近くの行）
QUOTA_KEY = "autoResumeOnQuotaReset"
QUOTA_VALUE = "false"
WORKFLOWS_KEY = re.compile(r"^workflows\s*:(?P<rest>.*)$", re.MULTILINE)

Fetch = Callable[[str, str, Path], None]
Install = Callable[[Path], None]


def cache_dir(env: Mapping[str, str]) -> Path:
    """取り置きの置き場 ${XDG_CACHE_HOME:-$HOME/.cache}/works-factory"""
    return Path(env.get("XDG_CACHE_HOME") or Path(env["HOME"]) / ".cache") / "works-factory"


def archon_folder(cache: Path, commit: str) -> Path:
    """cache の中で Archon の源 commit を取り置く所 <cache>/archon/<commit>"""
    return cache / "archon" / commit


def home_config(archon_home: Path) -> None:
    """archon_home/config.yaml に、工場が Archon の既定に従わずに決める値（defaultAssistant と workflows.autoResumeOnQuotaReset）が
    無ければ足す。在る値（利用者が選んだ物）は変えない。Archon は config.yaml の無い家にだけ注記だけの雛形を書くので、先に書けば
    雛形は置かれない"""
    config = archon_home / "config.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    before = config.read_text(encoding="utf-8") if config.exists() else ""
    text = before
    if not PROVIDER_KEY.search(text):
        text = appended(text, f"defaultAssistant: {DEFAULT_PROVIDER}\n")
    text = with_quota_policy(text, config)
    if text != before:
        config.write_text(text, encoding="utf-8")


def appended(text: str, lines: str) -> str:
    """text の末に lines を足す（text が改行で終わらなければ改行を挟む）"""
    gap = "" if not text or text.endswith("\n") else "\n"
    return f"{text}{gap}{lines}"


def with_quota_policy(text: str, config: Path) -> str:
    """text の workflows: の塊に QUOTA_KEY が無ければ足す。塊が無ければ末に作り、在れば塊の頭に子の字下げで足す（鍵を重ねない）"""
    found = WORKFLOWS_KEY.search(text)
    if found is None:
        return appended(text, f"workflows:\n  {QUOTA_KEY}: {QUOTA_VALUE}\n")
    if found["rest"].split("#", 1)[0].strip():
        raise RuntimeError(f"{config} の workflows: が 1 行の形で、{QUOTA_KEY} を足せない。塊の形（次の行から字下げ）に直す")
    head, rest = text[:found.end()], text[found.end():]
    children = []
    for line in rest.split("\n")[1:]:
        if line.strip() and not line[0].isspace() and not line.startswith("#"):
            break
        if line.strip() and not line.lstrip().startswith("#"):
            children.append(line)
    if any(re.match(rf"\s+{QUOTA_KEY}\s*:", line) for line in children):
        return text
    indent = re.match(r"\s*", children[0]).group() if children else "  "
    return f"{head}\n{indent}{QUOTA_KEY}: {QUOTA_VALUE}" + (rest or "\n")


def group_presets() -> dict[str, dict[str, str]]:
    """群の別名（群の名 → {provider, model, effort}）。値は lib/launchgroups.py の表の既定と DEFAULT_PROVIDER から組む"""
    return {name: {"provider": DEFAULT_PROVIDER, "model": model, "effort": effort}
            for name in launchgroups.GROUPS for model, effort in [launchgroups.default_of(name)]}


# 利用者の --config のファイルを Archon と同じ Bun.YAML.parse で読み、JSON で出す（packages/core/src/config/run-config.ts の
# loadWorkflowRunConfigFile。空のファイルは {}）
READ_YAML = ("try { console.log(JSON.stringify(Bun.YAML.parse(await Bun.file(process.argv.at(-1)).text()) ?? {})) }"
             " catch (error) { console.error(error.message); process.exit(1) }")


def read_run_config(bun: str, source: Path, path: Path) -> dict:
    """利用者の --config のファイル（YAML）を読む。読めない・object でない・aliases が object でない時は RuntimeError。
    鍵の照らしは Archon に任せる"""
    done = subprocess.run([bun, f"--config={source / 'bunfig.toml'}", "-e", READ_YAML, str(path)], cwd=source,
                          capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise RuntimeError(f"--config の {path} が読めない: {' '.join(done.stderr.split())}")
    layer = json.loads(done.stdout)
    if not isinstance(layer, dict) or not isinstance(layer.get("aliases", {}), dict):
        raise RuntimeError(f"--config の {path} は object にし、aliases も object にする")
    return layer


def run_config(where: Path, mine: dict | None = None) -> Path:
    """新しい run に --config で渡す、run 1 本ぶんの設定の層のファイル <where>/run-config/<中身の hash>.json を書いて返す。中身は利用者の
    --config の層 mine（read_run_config）に群の別名を aliases: で重ねた物で、同じ名の群の別名は工場の値が勝つ（群の付け替えは --model だけ）。
    起動の後はファイルは要らない。

    この層は対象のリポジトリの .archon/config.yaml を含む持続の設定より強く、呼ぶ人の --model だけがその上に立つ。Archon は起動の時に
    層を封じて run に記録し、workflow: の子の run が受け継ぎ、resume はその記録を戻す（止めた Archon の docs-web の reference/cli.md の
    --config の行）。Archon は --config を 1 つしか読まないので、利用者の層もここで合わせる。名を中身の hash にするのは、版の違う工場の木が
    同じ置き場を使っても互いの層を書き換えないため。利用者の env の値も入りうるので、ファイルは持ち主だけが読める"""
    mine = mine or {}
    layer = {**mine, "aliases": {**mine.get("aliases", {}), **group_presets()}}
    text = json.dumps(layer, ensure_ascii=False, indent=2) + "\n"
    path = where / "run-config" / f"{hashlib.sha256(text.encode()).hexdigest()[:16]}.json"
    if not (path.is_file() and path.read_text(encoding="utf-8") == text):
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False) as tmp:
            tmp.write(text)
        Path(tmp.name).replace(path)
    return path


def git_fetch(repo: str, commit: str, dest: Path) -> None:
    """repo（clone できる URL）の commit を dest に取り出す（dest は作る）"""
    subprocess.run(["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", repo, str(dest)], check=True)
    subprocess.run(["git", "-C", str(dest), "checkout", "--quiet", "--detach", commit], check=True)


def bun_install(source: Path) -> None:
    """源の bun.lock のとおりに依存を入れる。lock は書き換えない"""
    subprocess.run(["bun", "install", "--frozen-lockfile"], cwd=source, check=True)


def archon_source(pack: dict, cache: Path, fetch: Fetch = git_fetch, install: Install = bun_install) -> Path:
    """Archon の源を archon_folder(cache, commit) に取り、依存を入れて返す。在れば照らしてから使い、取らない。

    bun が無い・取れない・依存が入らない・本体か ASF のグラフが源に無ければ、途中まで取った物を残さず（前に取った物は残す）、
    何が取れなかったかを 1 行の RuntimeError で言う。在った物が照らしに合わなければ、消して取り直す案内つきの RuntimeError。
    """
    if shutil.which("bun") is None:
        raise RuntimeError("bun が無い。Archon の源は bun で起こす。入れ方は https://bun.sh")
    archon = pack["archon"]
    dest = archon_folder(cache, archon["commit"])
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


def pack_folder(pack: dict, base: Path) -> Path:
    """base の中で Archon が自分のグラフを pack として読む所 <base>/.archon/workflows/<pack>"""
    return base / WORKFLOW_FOLDER / pack["ours"]["pack"]


def workflow_source(pack: dict, root: Path, cache: Path) -> Path:
    """--workflow-source に渡す置き場を返す。その中の .archon/workflows/<pack> は root の自分のグラフのフォルダを指す。

    置き場の名は指す先のパスの hash なので、同じ root からは同じ置き場になる。前の形の置き場（.archon/workflows が
    直にグラフのフォルダを指す symlink）は、そのまま使うと pack の symlink をグラフのフォルダの中に作るので、消す案内で止まる。
    """
    target = (root / pack["ours"]["folder"]).resolve()
    shim = cache / "workflow-source" / hashlib.sha256(str(target).encode()).hexdigest()[:16]
    link = pack_folder(pack, shim)
    folder = link.parent
    if folder.is_symlink():
        raise RuntimeError(f"{folder} は前の形の置き場（{folder.readlink()} を指す symlink）。消して回し直せば作り直す（rm \"{folder}\"）")
    folder.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except FileExistsError:
        if not (link.is_symlink() and link.readlink() == target):
            raise RuntimeError(f"{link} が {target} を指していない。消して回し直せば作り直す（rm -r \"{link}\"）") from None
    except OSError as error:
        raise RuntimeError(f"{link} に {target} への symlink が作れない: {error.strerror or error}") from error
    return shim


def archon(bun: str, source: Path) -> list[str]:
    """源の Archon の本体を起こす命令の頭。後ろに Archon の引数を足す。

    bun は打った場所の bunfig.toml の preload を走らせる。対象の物を Archon の中で走らせないよう、源の物を名指す。
    """
    return [bun, f"--config={source / 'bunfig.toml'}", str(source / ENTRY)]


def shared(name: str) -> ModuleType:
    """グラフの境の workflows/.shared/<name>.py を読んだモジュール。2 度目からは読んだ物を返す。.shared は import の名にならず、
    Archon が置き場をバイトで照らすので __pycache__ を作らない"""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SHARED / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    sys.modules[name] = module
    return module


def workflow_run(source: Path, workflow_dir: Path, config: Path | None, cwd: Path, name: str, *args: str) -> list[str]:
    """グラフ name を workflow_dir から読み、run 1 本ぶんの設定の層 config（run_config。None なら付けない）をつけて cwd に対して回す命令。

    --cwd と --workflow-source と --config は利用者の引数より前に置く。利用者の -- の後ろに付くと、文として渡り、
    Archon が cwd のグラフを探す元の動きに黙って戻る（ASF の factory/consumer.py と同じ並べ）。
    """
    return [
        "bun", str(source / ENTRY),
        "workflow", "run", "--cwd", str(cwd), "--workflow-source", str(workflow_dir),
        *(["--config", str(config)] if config else []), name, *args,
    ]


def _verify(source: Path, commit: str) -> None:
    """取り置いた源の 3 つを照らす: HEAD が commit・git status --porcelain --untracked-files=all が空・node_modules が在る。
    依存（node_modules）は源の .gitignore に入るので status には出ない。
    ASF の factory/consumer.py の verify_source の照らしの一部で、無視・未追跡のグラフファイル・symlink・必須のファイルの欠けは見ない"""
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
