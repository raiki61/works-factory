"""Archon を要る試験の助け（tests/AGENTS.md。テストのモジュールではない。test_*.py に当たらない）。

- 止めた Archon の源: 環境変数 WORKS_FACTORY_ARCHON_CACHE の置き場に <cache>/archon/<commit> が在る時だけ使う。
  在れば place._verify を当て、壊れていれば赤にする。環境変数か置き場が無い時だけ見送る。試験の中では取りに行かない。
- 見送らない: 環境変数 WORKS_FACTORY_ARCHON_REQUIRED が在れば（CI が立てる）、見送る所で同じ文の赤にする。
  CI の用意が崩れて Archon の要る試験が黙って見送られ、CI が緑のままになるのを防ぐ。
- 手元の確かめでは起こさない: 環境変数 WORKS_FACTORY_ARCHON_DEFER（tests/shard.py の --paths が立てる。tests/changed.py の道）が在り、
  REQUIRED が無ければ、Archon を起こす口 runner が源を見る前に hermetic.ARCHON_DEFERRED の訳で見送る（持ち主の決め light-in-loop・
  full-suite-in-ci。起こす試験は CI が回す）。どの試験が起こすかを表に並べず、起こす口のここ 1 か所で見分ける。源の字を読むだけの
  試験（source・pinned_source）は軽いので見送らない。
- 起こす: 源の Archon を bun で、使い捨ての ARCHON_HOME と、殻と同じ既定の provider（place.PROVIDER_ENV）と、このリポジトリを指す
  WORKS_FACTORY_ROOT（呼ぶ側が env で替え、None で外せる）をつけて起こす。家の config.yaml には群の別名（place.group_presets）を書く。殻は群の
  別名と run のノードへの環境変数を新しい run の --config で渡すが、止めた Archon の validate と workflow test は --config を受けない
  （「--config can only be used with workflow run, trigger fire, or trigger schedule」）。本番の家と同じく何も書かない家は
  aliases=False で起こす（家の置き場は別。--config の層が値を運ぶことを照らす試験が使う）。
  bun が無ければ見送る。
- 木: 使い捨ての git の木。中の .archon/workflows/<pack>/ に、名指した工程のフォルダとこのリポジトリの .shared/ を写して commit する。
  pack のフォルダは pack.json の ours.folder（WORKFLOWS。組み込みの入れ替えの前も後も同じ口）。blocks_tree は block の筋書き用に
  TARGET_FILES を 2 つ目の commit に置く木。
  `archon validate` は --workflow-source を受けず、--cwd は git の木しか受けないので、確かめる時はこの木を --cwd に渡す。
- 筋書きの木（blocks_tree）: 輪の本体の唯一の終わりの関所を外して置く（dry_run_bodies。止めた Archon の dry-run が輪の出力を本体の終わりの
  節から取り、飛んだ関所で空にするため。本物は関所が依る節の出力）。validate と本物の回しの木（tree）は外さない。
- validate の数えない警告: Claude Code に同梱の skill（BUILTIN_SKILLS）と、借りる superpowers の skill（BORROWED_SKILLS。
  lib/borrow/borrow.json の superpowers.skills）を節が名指した時の「ディスクに無い」の警告だけ。同梱の skill は SKILL.md を
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
from collections.abc import Callable, Iterable, Iterator

import yaml

from bin._lib import pack, place
from tests.bin import hermetic
from tests.bin.gitkit import git

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE_ENV = hermetic.ARCHON_CACHE_ENV
REQUIRED_ENV = hermetic.ARCHON_REQUIRED_ENV
DEFER_ENV = hermetic.ARCHON_DEFER_ENV
PACK = pack.load(ROOT)
BUILTIN_SKILLS = frozenset({"code-review", "simplify", "security-review"})
BORROWED_SKILLS = frozenset(json.loads((ROOT / "lib" / "borrow" / "borrow.json").read_text(encoding="utf-8"))
                            ["superpowers"]["skills"])
BUILTIN_SKILL_WARNING = re.compile(r"Skill '([^']+)' not found in ")
WORKFLOWS = ROOT / PACK["ours"]["folder"]
SHARED = ".shared"


def src_module(block: str, module: str):
    """pack の block の src/<module> を、この過程に読み込んだモジュール（試験は block の src を読んでよい。読んではいけないのは lib と
    ほかの block の側。docs/design/integration.md の 4.5-7）。src は package の名が block ごとに重なるので、読む前に前の src を外す
    （tests/blocks/kit.py の load と同じ）。lib/ も sys.path に置く（src は lib のモジュールを名だけで import する）"""
    import importlib
    import sys
    lib = str(ROOT / "lib")
    if lib not in sys.path:
        sys.path.append(lib)
    for name in [m for m in sys.modules if m == "src" or m.startswith("src.")]:
        del sys.modules[name]
    folder = str(WORKFLOWS / block)
    sys.path.insert(0, folder)
    try:
        return importlib.import_module(f"src.{module}")
    finally:
        sys.path.remove(folder)


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


def runner() -> tuple[pathlib.Path, str]:
    """Archon を起こす元（源と bun のパス）。Archon を起こす試験はここを通る。手元の確かめ（DEFER_ENV が在り REQUIRED_ENV が無い）では
    源を見る前に見送る。源か bun が無ければ absent"""
    if os.environ.get(DEFER_ENV) and not os.environ.get(REQUIRED_ENV):
        raise unittest.SkipTest(f"{hermetic.ARCHON_DEFERRED}（tests/changed.py の手元の確かめ。CI は回す）")
    found = source()
    bun = shutil.which("bun")
    if bun is None:
        raise absent("bun が無い")
    return found, bun


@contextlib.contextmanager
def tree(names: Iterable[str], workflows: pathlib.Path = WORKFLOWS, shared: pathlib.Path = WORKFLOWS / SHARED,
         files: dict[str, str] | None = None, later: dict[str, str] | None = None,
         shape: Callable[[pathlib.Path], object] | None = None) -> Iterator[pathlib.Path]:
    """workflows の names のフォルダと shared（既定はこのリポジトリの workflows/.shared/）を pack の形で置いて commit した使い捨ての git の木。
    files（根からのパス → 中身）は対象のリポジトリの側のファイルとして一緒に commit する（exec-code の筋書きの作業ツリーに入る）。
    later は 2 つ目の commit に置く（筋書きが base: HEAD~1 を渡すと、これが対象差分になる）。shape は置いた pack のフォルダを
    1 つ目の commit の前に書き直す口（commit を増やさず、later の対象差分を変えない）"""
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp) / "tree"
        placed = place.pack_folder(PACK, root)
        no_cache = shutil.ignore_patterns("__pycache__")
        for name in names:
            shutil.copytree(workflows / name, placed / name, ignore=no_cache)
        shutil.copytree(shared, placed / SHARED, ignore=no_cache)
        for rel, body in (files or {}).items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(body, encoding="utf-8")
        if shape is not None:
            shape(placed)
        git(root, "init", "-q")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", "seed")
        if later:
            for rel, body in later.items():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text(body, encoding="utf-8")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "target")
        yield root


# block の筋書きの作業ツリーに置く、対象のリポジトリの小さな入口（guidance-path の読み手が辿る所。.archon の外に要る）
TARGET_FILES = {"README.md": "# Fixture target\n\nSee AGENTS.md.\n", "AGENTS.md": "# Rules\n\nNew review viewpoints are blocks.\n"}


@contextlib.contextmanager
def blocks_tree(names: Iterable[str]) -> Iterator[pathlib.Path]:
    """pack の names の block と pack の .shared/ を置き、TARGET_FILES を 2 つ目の commit に置いた使い捨ての git の木
    （tree と同じ形。条件つきの観点の筋書きは base: HEAD~1 で TARGET_FILES を対象差分にできる）。筋書き（workflow test と
    workflow run --dry-run）だけが使う木なので、輪の本体の唯一の終わりの関所を外す（dry_run_bodies）"""
    with tree(names, WORKFLOWS, WORKFLOWS / SHARED, later=TARGET_FILES, shape=dry_run_bodies) as root:
        yield root


def dry_run_bodies(placed: pathlib.Path) -> list[str]:
    """木の工程の YAML の輪（loop_group）の本体から、本体の唯一の終わりの人の関所（wait: の attention）を外して書き直し、外した関所の
    id を返す。訳: 止めた Archon の dry-run（packages/workflows/src/dry-run.ts の simulateLoopGroup）は輪の 1 周の出力を本体の終わりの節
    から取るので、when: で飛んだ関所が終わりだと輪の出力が空になる。本物の run（dag-executor.ts の loopGroupIterationOutput）は、終わりの
    関所が依る節の出力を輪の出力にする。関所を外せば、その依る節が本体の終わりになり、dry-run の輪の出力が本物と同じになる。dry-run は
    until_bash の輪を 1 周で終えたことにし、関所の答えで次の周を回さないので、関所が開く・答える・再開する所は本物の Archon の試験
    （tests/e2e/test_design_talk_real.py）が照らす。docs/design/archon.md のループの行"""
    out = []
    for path in sorted(placed.glob("*/*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        changed = False
        for node in (doc or {}).get("nodes") or []:
            body = (node.get("loop_group") or {}).get("nodes") if isinstance(node, dict) else None
            if not body:
                continue
            depended = {d for n in body for d in n.get("depends_on") or []}
            sinks = [n for n in body if n["id"] not in depended]
            if len(sinks) == 1 and isinstance(sinks[0].get("wait"), dict) and "attention" in sinks[0]["wait"]:
                body.remove(sinks[0])
                out.append(sinks[0]["id"])
                changed = True
        if changed:
            path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return out


def archon(cwd: pathlib.Path, *args: str, aliases: bool = True, **env: str | None) -> subprocess.CompletedProcess:
    """源の Archon を cwd で起こす。ARCHON_HOME は cwd の横の使い捨て。源か bun が無ければ absent。子の環境は hermetic.child_env で
    作る（入口の殻が渡す Archon の頭・包みの宣言・親の run の名は継がない。試験が殻の中で走っても、線の後始末の節が外の Archon を
    起こさず、包みを通らない起動を外の run の記録で受け付けさせない）。子へ渡したい名は env で名指しし、値を None にした名は置かない"""
    head, child = command(cwd, aliases=aliases, **env)
    return subprocess.run([*head, *args], cwd=cwd, env=child, capture_output=True, text=True, encoding="utf-8")


def command(cwd: pathlib.Path, aliases: bool = True, **env: str | None) -> tuple[list[str], dict]:
    """archon が cwd で起こす命令の頭と子の環境（試験が自分で Popen する時や、頭を受ける部品に渡す時に使う）"""
    found, bun = runner()
    entry = found / place.ENTRY
    home = cwd.parent / ("archon-home" if aliases else "archon-home-bare")
    if aliases and not home.exists():
        home.mkdir()
        (home / "config.yaml").write_text("aliases:\n" + "".join(f"  {json.dumps(name)}: {json.dumps(preset)}\n"
                                                                for name, preset in place.group_presets().items()),
                                          encoding="utf-8")
    named = {"WORKS_FACTORY_ROOT": str(ROOT), **env, "ARCHON_HOME": str(home), place.PROVIDER_ENV: place.DEFAULT_PROVIDER}
    return [bun, str(entry)], hermetic.child_env(**{name: value for name, value in named.items() if value is not None})
