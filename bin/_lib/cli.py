"""人の打つ口 bin/start・answer・show の中身。Archon は引数の archon 関数（Archon の CLI の引数 → 標準出力）で呼ぶ。

本物の archon 関数は pack.json の版の実行ファイルをホストの環境のまま起こすだけ。認証の切り替えと置き場の隔離は
ここでは持たない（土台の計画の Task 6）。
"""
import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from bin._lib import pack as packs
from bin._lib import place

Archon = Callable[[list[str]], str]

ROOT = Path(__file__).resolve().parents[2]


def default_archon_home() -> Path:
    """Archon 自身と同じ決め方（$ARCHON_HOME、無ければ ~/.archon）。起こす Archon も同じ環境を読む"""
    return Path(os.environ.get("ARCHON_HOME") or Path.home() / ".archon")


def default_cache() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "works-factory"


def start(
    target: Path,
    request: str,
    archon: Archon,
    *,
    archon_home: Path | None = None,
    cache: Path | None = None,
    fetch: place.Fetch = place.git_sparse_fetch,
) -> str:
    """版の工程を Archon の家に置いてから、target で線を起こし、run の id を返す。線の終わりは待たない"""
    pack = packs.load(ROOT)
    asf_dir = place.asf_tree(pack, cache or default_cache(), fetch)
    place.place(pack, ROOT, archon_home or default_archon_home(), asf_dir)
    ack = _ack(archon(["workflow", "run", pack["ours"]["line"], "--cwd", str(target), "--detach", "--json", request]))
    return ack["runId"]


def answer(run_id: str, text: str, archon: Archon) -> None:
    """関所で止まった run に text で答え、run を先へ進める（進むのは Archon の子の process。ここでは待たない）"""
    _ack(archon(["workflow", "approve", run_id, "--comment", text, "--detach", "--json"]))


def show(run_id: str, archon: Archon) -> str:
    """Archon の run の状態をそのまま返す（持ち主の居ない running の扱い、埋め P1 は段 1 で足す）"""
    return archon(["workflow", "get", run_id, "--verbose"])


def _ack(stdout: str) -> dict:
    """Archon の --json の返事を読む。ok でなければ Archon の言う誤りを RuntimeError に入れる"""
    try:
        ack = json.loads(stdout)
    except ValueError:
        raise RuntimeError(f"Archon の返事が JSON でない: {stdout.strip()!r}") from None
    if not ack.get("ok") or "runId" not in ack:
        raise RuntimeError(f"Archon が断った: {ack.get('error') or stdout.strip()}")
    return ack


def host_archon(binary: Path) -> Archon:
    """binary をホストの環境のまま起こす。標準エラーは人の端末にそのまま出す"""

    def archon(argv: list[str]) -> str:
        done = subprocess.run([str(binary), *argv], stdout=subprocess.PIPE, text=True)
        if done.returncode != 0:
            raise RuntimeError(f"archon {' '.join(argv[:2])} が終了の値 {done.returncode} で落ちた: {done.stdout.strip()}")
        return done.stdout

    return archon


def main(command: str, argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog=f"bin/{command}")
    if command == "start":
        parser.add_argument("target", type=Path, help="対象のリポジトリ")
        parser.add_argument("request", help="依頼の文か issue の番号")
    else:
        parser.add_argument("run_id", help="run の id")
        if command == "answer":
            parser.add_argument("text", help="関所への答え")
    args = parser.parse_args(argv)
    try:
        archon = host_archon(place.archon_binary(packs.load(ROOT), default_cache()))
        if command == "start":
            print(start(args.target.resolve(), args.request, archon))
        elif command == "answer":
            answer(args.run_id, args.text, archon)
        else:
            print(show(args.run_id, archon), end="")
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"bin/{command}: {error}", file=sys.stderr)
        return 1
    return 0
