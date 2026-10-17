"""Archon を要る試験の助け（tests/AGENTS.md。テストのモジュールではない。test_*.py に当たらない）。

- 止めた Archon の源: 環境変数 WORKS_FACTORY_ARCHON_CACHE の置き場に <cache>/archon/<commit> が在る時だけ使う。
  在れば place._verify を当て、壊れていれば赤にする。環境変数か置き場が無い時だけ見送る。試験の中では取りに行かない。
- 見送らない: 環境変数 WORKS_FACTORY_ARCHON_REQUIRED が在れば（CI が立てる）、見送る所で同じ文の赤にする。
  CI の用意が崩れて Archon の要る試験が黙って見送られ、CI が緑のままになるのを防ぐ。
- 起こす: 源の Archon を bun で、使い捨ての ARCHON_HOME（工場が決める値を書いた config.yaml。place.home_config）と、このリポジトリを指す WORKS_FACTORY_ROOT をつけて起こす。
  その config.yaml には群の別名（place.group_presets）も書く。殻は群の別名を新しい run の --config で渡すが、止めた Archon の
  validate と workflow test は --config を受けない（「--config can only be used with workflow run, trigger fire, or trigger schedule」）。
  本番の家と同じく別名を書かない家は aliases=False で起こす（家の置き場は別。--config の層が群の値を運ぶことを照らす試験が使う）。
  bun が無ければ見送る。
- 木: 使い捨ての git の木。中の .archon/workflows/<pack>/ に、名指した工程のフォルダとこのリポジトリの .shared/ を写して commit する。
  `archon validate` は --workflow-source を受けず、--cwd は git の木しか受けないので、確かめる時はこの木を --cwd に渡す。
- validate の数えない警告: Claude Code に同梱の skill（BUILTIN_SKILLS）と、借りる superpowers の skill（BORROWED_SKILLS。
  bin/_lib/borrow/borrow.json の superpowers.skills）を節が名指した時の「ディスクに無い」の警告だけ。同梱の skill は SKILL.md を
  持たず、借りる skill は起動の時に run の隔離した設定へ入るので使い捨ての木には無い。止めた Archon（packages/workflows/src/
  validator.ts の skills の照らし）はどちらも名指すたびに出す。
"""
import contextlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest
from collections.abc import Iterable, Iterator

from bin._lib import pack, place
from tests.bin import hermetic
from tests.bin.gitkit import git

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE_ENV = hermetic.ARCHON_CACHE_ENV
REQUIRED_ENV = hermetic.ARCHON_REQUIRED_ENV
PACK = pack.load(ROOT)
BUILTIN_SKILLS = frozenset({"code-review", "simplify", "security-review"})
BORROWED_SKILLS = frozenset(json.loads((ROOT / "bin" / "_lib" / "borrow" / "borrow.json").read_text(encoding="utf-8"))
                            ["superpowers"]["skills"])
BUILTIN_SKILL_WARNING = re.compile(r"Skill '([^']+)' not found in ")
WORKFLOWS = ROOT / PACK["ours"]["folder"]
SHARED = ".shared"


def absent(reason: str) -> unittest.SkipTest | AssertionError:
    """Archon の要る物が無い時に投げる物。REQUIRED_ENV が在れば赤（AssertionError）、無ければ見送り"""
    message = f"Archon の源が無い: {reason}"
    return AssertionError(message) if os.environ.get(REQUIRED_ENV) else unittest.SkipTest(message)


def counted(issue: dict) -> bool:
    """validate の返りの issue を数えるか。同梱の skill と借りる skill の「ディスクに無い」の警告だけ数えない"""
    name = BUILTIN_SKILL_WARNING.match(issue.get("message", ""))
    return not (issue.get("level") == "warning" and issue.get("field") == "skills"
                and name is not None and name.group(1) in BUILTIN_SKILLS | BORROWED_SKILLS)


def pinned_source(cache: str | None, commit: str) -> pathlib.Path:
    """取り置いた Archon の源 <cache>/archon/<commit> を照らして返す。cache が無いか置き場が無ければ absent。
    源の字を読むだけなので bun は要らず、archon_source を通さない（無い置き場を作らない）"""
    if not cache:
        raise absent(f"置き場の環境変数 {CACHE_ENV} が無い")
    source = place.archon_folder(pathlib.Path(cache), commit)
    if not source.is_dir():
        raise absent(f"{source} が無い")
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


def archon(cwd: pathlib.Path, *args: str, aliases: bool = True, **env: str) -> subprocess.CompletedProcess:
    """源の Archon を cwd で起こす。ARCHON_HOME は cwd の横の使い捨て。源か bun が無ければ absent。子の環境は hermetic.child_env で
    作る（入口の殻が渡す Archon の頭・包みの宣言・親の run の名は継がない。試験が殻の中で走っても、線の後始末の節が外の Archon を
    起こさず、包みを通らない起動を外の run の記録で受け付けさせない）。子へ渡したい名は env で名指しする"""
    entry = source() / place.ENTRY
    bun = shutil.which("bun")
    if bun is None:
        raise absent("bun が無い")
    home = cwd.parent / ("archon-home" if aliases else "archon-home-bare")
    if not home.exists():
        place.home_config(home)
        if aliases:
            with (home / "config.yaml").open("a", encoding="utf-8") as config:
                config.write("aliases:\n" + "".join(f"  {json.dumps(name)}: {json.dumps(preset)}\n"
                                                     for name, preset in place.group_presets().items()))
    child = hermetic.child_env(**{**env, "ARCHON_HOME": str(home), "WORKS_FACTORY_ROOT": str(ROOT)})
    return subprocess.run([bun, str(entry), *args], cwd=cwd, env=child, capture_output=True, text=True, encoding="utf-8")
