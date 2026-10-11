"""Archon を要る試験の助け（tests/AGENTS.md。テストのモジュールではない。test_*.py に当たらない）。

- 止めた Archon の源: 環境変数 WORKS_FACTORY_ARCHON_CACHE の置き場に <cache>/archon/<commit> が在る時だけ使う。
  在れば place._verify を当て、壊れていれば赤にする。環境変数か置き場が無い時だけ見送る。試験の中では取りに行かない。
- 起こす: 源の Archon を bun で、使い捨ての ARCHON_HOME と、このリポジトリを指す WORKS_FACTORY_ROOT をつけて起こす。
  bun が無ければ見送る。
- 木: 使い捨ての git の木。中の .archon/workflows/<pack>/ に、名指した工程のフォルダとこのリポジトリの .shared/ を写して commit する。
  `archon validate` は --workflow-source を受けず、--cwd は git の木しか受けないので、確かめる時はこの木を --cwd に渡す。
"""
import contextlib
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from collections.abc import Iterable, Iterator

from bin._lib import pack, place
from tests.bin.gitkit import git

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE_ENV = "WORKS_FACTORY_ARCHON_CACHE"
PACK = pack.load(ROOT)
WORKFLOWS = ROOT / PACK["ours"]["folder"]
SHARED = ".shared"


def pinned_source(cache: str | None, commit: str) -> pathlib.Path:
    """取り置いた Archon の源 <cache>/archon/<commit> を照らして返す。cache が無いか置き場が無ければ名前つきで見送る。
    源の字を読むだけなので bun は要らず、archon_source を通さない（無い置き場を作らない）"""
    if not cache:
        raise unittest.SkipTest(f"Archon の源が無い: 置き場の環境変数 {CACHE_ENV} が無い")
    source = pathlib.Path(cache) / "archon" / commit
    if not source.is_dir():
        raise unittest.SkipTest(f"Archon の源が無い: {source} が無い")
    place._verify(source, commit)
    return source


def source() -> pathlib.Path:
    return pinned_source(os.environ.get(CACHE_ENV), PACK["archon"]["commit"])


@contextlib.contextmanager
def tree(names: Iterable[str], workflows: pathlib.Path = WORKFLOWS) -> Iterator[pathlib.Path]:
    """workflows の names のフォルダとこのリポジトリの .shared/ を pack の形で置いて commit した使い捨ての git の木"""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp) / "tree"
        placed = place.pack_folder(PACK, root)
        no_cache = shutil.ignore_patterns("__pycache__")
        for name in names:
            shutil.copytree(workflows / name, placed / name, ignore=no_cache)
        shutil.copytree(WORKFLOWS / SHARED, placed / SHARED, ignore=no_cache)
        git(root, "init", "-q")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "seed")
        yield root


def archon(cwd: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    """源の Archon を cwd で起こす。ARCHON_HOME は cwd の横の使い捨て。源か bun が無ければ見送る"""
    entry = source() / place.ENTRY
    bun = shutil.which("bun")
    if bun is None:
        raise unittest.SkipTest("Archon の源が無い: bun が無い")
    env = {**os.environ, "ARCHON_HOME": str(cwd.parent / "archon-home"), "WORKS_FACTORY_ROOT": str(ROOT)}
    return subprocess.run([bun, str(entry), *args], cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8")
