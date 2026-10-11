"""pack.json の版の Archon の実行ファイルと ASF の工程を取り、Archon の家に置く。

置くのは $ARCHON_HOME の下の pack.json の ours.placed_at と asf.placed_at の 2 つだけ。ほかの置き場
（同梱の工程・ほかの pack）には触らない。実行ファイルの版の固定と sha256 の確かめは、今の works の
works/dev/archon.sh から持ってきた（E15）。
"""
import hashlib
import json
import platform
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

Download = Callable[[str, str, Path], Path]
Fetch = Callable[[str, str, str, Path], None]

_MACHINES = {"aarch64": "arm64", "x86_64": "x64", "AMD64": "x64"}


def asset_name() -> str:
    """この機械で走る Archon の実行ファイルの名（公開版の asset の名。例 archon-darwin-arm64）"""
    system, machine = platform.system(), platform.machine()
    return f"archon-{system.lower()}-{_MACHINES.get(machine, machine.lower())}"


def gh_release_download(repo: str, release: str, dest_dir: Path) -> Path:
    asset = asset_name()
    subprocess.run(
        ["gh", "release", "download", release, "-R", repo, "-p", asset, "-D", str(dest_dir), "--clobber"],
        check=True,
    )
    return dest_dir / asset


def git_sparse_fetch(repo: str, commit: str, folder: str, dest: Path) -> None:
    """repo の commit の folder の中身を dest に写す（dest は作る）。blob は folder の分だけ取る"""
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "clone"
        url = f"https://github.com/{repo}.git"
        subprocess.run(["git", "clone", "--quiet", "--filter=blob:none", "--sparse", "--no-checkout", url, str(clone)], check=True)
        subprocess.run(["git", "-C", str(clone), "sparse-checkout", "set", folder], check=True)
        subprocess.run(["git", "-C", str(clone), "checkout", "--quiet", "--detach", commit], check=True)
        shutil.copytree(clone / folder, dest, symlinks=True)


def archon_binary(pack: dict, cache: Path, download: Download = gh_release_download) -> Path:
    """<cache>/archon/<release>/<asset> の実行ファイルを返す。無ければ download で取り、sha256 を照らす。

    合わなければ RuntimeError で止まる。壊れたキャッシュは利用者のファイルなので消さず、消す命令を文に入れる。
    """
    archon = pack["archon"]
    asset = asset_name()
    expected = archon["assets"].get(asset)
    if expected is None:
        raise RuntimeError(f"pack.json の archon.assets に {asset} の sha256 が無い（この機械の実行ファイルの名）")
    dest_dir = cache / "archon" / archon["release"]
    path = dest_dir / asset
    if not path.is_file():
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = download(archon["repo"], archon["release"], dest_dir)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(
            f"sha256 が合わない: {path}（期待 {expected}、実際 {actual}）。"
            f"壊れたキャッシュなら、このファイルを消して回し直せば取り直す（rm \"{path}\"）"
        )
    path.chmod(path.stat().st_mode | 0o111)
    return path


def asf_tree(pack: dict, cache: Path, fetch: Fetch = git_sparse_fetch) -> Path:
    """ASF の工程のフォルダを <cache>/asf/<commit>/ に取って返す。在れば取らない。

    何から取ったか（repo・folder）を横の <commit>.json に残し、pack.json と違えば取り直す。
    取れなければ途中まで取った物を残さず（前に取った物は残す）、何が取れなかったかを 1 行の RuntimeError で言う。
    """
    asf = pack["asf"]
    dest = cache / "asf" / asf["commit"]
    record = dest.with_name(f"{dest.name}.json")
    source = {"repo": asf["repo"], "folder": asf["folder"]}
    if dest.is_dir() and _read_record(record) == source:
        return dest

    def fill(staging: Path) -> None:
        try:
            fetch(asf["repo"], asf["commit"], asf["folder"], staging)
        except Exception as error:
            reason = " ".join(str(error).split()) or type(error).__name__
            raise RuntimeError(f"ASF の {asf['repo']} {asf['commit']} の {asf['folder']} が取れない: {reason}") from error

    record.unlink(missing_ok=True)
    _replace(dest, fill)
    record.write_text(json.dumps(source), encoding="utf-8")
    return dest


def _read_record(record: Path) -> dict | None:
    try:
        return json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def place(pack: dict, root: Path, archon_home: Path, asf_dir: Path) -> None:
    """root の自分の工程と asf_dir を、Archon の家の各々の置き場にバイトのまま置く（E1）"""
    _swap_in(root / pack["ours"]["folder"], archon_home / pack["ours"]["placed_at"])
    _swap_in(asf_dir, archon_home / pack["asf"]["placed_at"])


def _swap_in(src: Path, target: Path) -> None:
    _replace(target, lambda staging: shutil.copytree(src, staging, symlinks=True))


def _replace(target: Path, fill: Callable[[Path], None]) -> None:
    """target の横の一時の置き場を fill で作り切ってから入れ替える。fill の途中で止まっても前の target は残る"""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent, prefix=f".{target.name}.") as tmp:
        staging = Path(tmp) / "new"
        fill(staging)
        if target.exists():
            target.rename(Path(tmp) / "old")
        staging.rename(target)
