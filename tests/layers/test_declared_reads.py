"""実行時に開く file の宣言（読む部品の一番上の `RUNTIME_READS`）は、木に在る file に当たる。

- 宣言は、字の言及でも import でも届かない実行時の読み（glob や include の展開）を、読む部品の 1 か所に書く物。変更に当たる試験を選ぶ地図
  （`lib/impact.py`）が、宣言の下の file の変更で、宣言した部品とそれを直に import する試験を選ぶ。宣言の値が値の当て方
  （`impact.reads_hits`）でどの file にも当たらなくなる（置き場の改名・消し）と、その試験は黙って選ばれなくなるので、ここで赤にする。
- 読む物は git が知る Python の file のうち宣言の名（`impact.READS_DECL`）を字に含む物で、宣言の読み取りは地図と同じ
  `impact.py_reads`、値の当て方も地図と同じ `impact.reads_hits`。
- 限り: 宣言の書き忘れは見ない。
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))
import impact  # noqa: E402

from tests.layers.trees import tree  # noqa: E402


def problems(root: pathlib.Path) -> list[str]:
    """どの file にも当たらない宣言の値を `<ファイル>: <値>` で 1 行ずつ返す（無ければ空）。読めない file は飛ばす"""
    root = pathlib.Path(root)
    files = impact.tree_files(root)
    if files is None:
        raise RuntimeError(f"git の一覧が取れない: {root}")
    out = []
    for rel in files:
        if not rel.endswith(".py"):
            continue
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
        if impact.READS_DECL not in text:
            continue
        out += [f"{rel}: {value}" for value in impact.py_reads(text) or [] if not impact.reads_hits([value], files)]
    return out


class DeclaredReadsTest(unittest.TestCase):
    def setUp(self):
        for name in ("READS_DECL", "py_reads", "reads_hits"):
            self.assertTrue(hasattr(impact, name), f"地図が宣言の読みの口 {name} を公開していない")

    def test_real_tree_clean(self):
        self.assertEqual(problems(ROOT), [])

    def test_missing_declared_path_is_red(self):
        files = {"tests/test_x.py": 'RUNTIME_READS = ("gone/", "data/x.json")\n', "data/y.json": "{}\n"}
        with tree(files, git_init=True) as root:
            self.assertEqual(problems(root), ["tests/test_x.py: gone/", "tests/test_x.py: data/x.json"])

    def test_declared_folder_with_files_passes(self):
        files = {
            "tests/test_x.py": 'RUNTIME_READS = ("flows/", "data/x.json")\n',
            "flows/a/b.yaml": "",
            "data/x.json": "{}\n",
            "tests/test_text.py": 'NOTE = "RUNTIME_READS = (\'gone/\',)"\n',
        }
        with tree(files, git_init=True) as root:
            self.assertEqual(problems(root), [])
