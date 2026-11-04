"""工場の中の字が書くリポジトリのパスは、在る物を指す（根の `AGENTS.md` の E26 の機械の行）。

- 照らすファイルは `bin/`・`lib/`（試験の `lib/tests/` と借りた写しの `lib/borrow/` を除く）・`workflows/`・見る道具（フォルダ `viewer`）の下の全部と、
  どの階層の `AGENTS.md` も。
- パスは、根の直下のフォルダの名（`.` で始まる物を除く。名の表は持たず、根を読んで決める）で始まり `/` が続く字の並び。
  前が英数字・`.`・`/`・`-` の所は別の語の途中なので数えない（`src/lib/x.py` の `lib/` など）。
- 在るとは、パスそのもの・`.py` を足した物（モジュールの名 `lib/rolekit`）・最後の段の `.` の前に `.py` を足した物
  （モジュールの中の名 `lib/reads.collect`・`tests/bin/hermetic.child_env`）のどれかが在ること。末の `.` と `/` は文の区切りとして外す。
- 字に `*`・`<`・`>`・`{`・`}` を含む物は型（`workflows/<block>/`・`lib/python*/`）で、1 つのファイルを指さないので数えない。
- 許すパスの表は持たない（憲法 6）。わざと無いパスを書く例（対象のリポジトリの例の `lib/x.py`、fixture の偽の対象のパス）は、
  根の直下のフォルダの名で始まらない形に書く。消えた物を語る時は、パスでなく名で書く（どこに在ったかは git の履歴が持つ）。
"""
import pathlib
import re
import unittest

from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCOPES = ("bin", "lib", "workflows", "viewer")
SKIPPED = ("lib/tests", "lib/borrow")
NOT_FILES = ("__pycache__", ".venv", "node_modules")
PATTERN_MARKS = "*<>{}"


def _roots(root: pathlib.Path) -> list[str]:
    return sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))


def _scanned(root: pathlib.Path):
    seen = set()
    for scope in SCOPES:
        base = root / scope
        if base.is_dir():
            seen.update(p for p in base.rglob("*") if p.is_file())
    seen.update(root.rglob("AGENTS.md"))
    for path in sorted(seen):
        rel = path.relative_to(root).as_posix()
        if any(part in NOT_FILES for part in path.relative_to(root).parts):
            continue
        if any(rel == s or rel.startswith(s + "/") for s in SKIPPED) and path.name != "AGENTS.md":
            continue
        yield rel, path


def _exists(root: pathlib.Path, rel: str) -> bool:
    if (root / rel).exists() or (root / f"{rel}.py").exists():
        return True
    folder, _, last = rel.rpartition("/")
    head = last.partition(".")[0]
    return bool(head) and ((root / folder / f"{head}.py").exists() or (root / folder / head).is_dir())


def problems(root: pathlib.Path) -> list[str]:
    """無いパスを書いた所を `<ファイル>:<行>: <パス>` で 1 行ずつ返す（無ければ空）。UTF-8 で読めないファイルは飛ばす（字のファイルでない）"""
    root = pathlib.Path(root)
    path_re = re.compile(r"(?<![A-Za-z0-9_./-])((?:" + "|".join(map(re.escape, _roots(root)))
                         + r")/[A-Za-z0-9_./*<>{}-]*)")
    out = []
    for rel, path in _scanned(root):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, 1):
            for match in path_re.finditer(line):
                found = match.group(1).rstrip("./")
                if any(mark in found for mark in PATTERN_MARKS) or _exists(root, found):
                    continue
                out.append(f"{rel}:{number}: {found}")
    return out


class PathsExistTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(problems(ROOT), [])

    def test_missing_path_is_red(self):
        files = {
            "lib/a.py": "# 元は lib/gone.py の f。docs/gone.md も見る\n",
            "docs/here.md": "",
            "AGENTS.md": "- `docs/gone2.md` を読む\n",
        }
        with tree(files) as root:
            self.assertEqual(problems(root), ["AGENTS.md:1: docs/gone2.md", "lib/a.py:1: lib/gone.py", "lib/a.py:1: docs/gone.md"])

    def test_present_paths_and_patterns_pass(self):
        files = {
            "lib/reads.py": "",
            "lib/a.py": ("# lib/reads.collect・lib/reads・lib/reads.py・docs/here.md。lib/ の下\n"
                         "# workflows/<block>/・lib/python*/・src/lib/x.py・mylib/x.py は数えない\n"),
            "docs/here.md": "",
            "workflows/AGENTS.md": "",
        }
        with tree(files) as root:
            self.assertEqual(problems(root), [])

    def test_tests_and_borrow_of_lib_are_not_scanned(self):
        files = {"lib/tests/test_a.py": "# docs/gone.md\n", "lib/borrow/x.md": "docs/gone.md\n", "docs/here.md": ""}
        with tree(files) as root:
            self.assertEqual(problems(root), [])


if __name__ == "__main__":
    unittest.main()
