"""修正の block の型のモジュールが、別の型のモジュールを import しない（docs/plans/2026-10-24-fix-weapons.md の 4.1 の 2・6.1。段 1 の間の
yes/no の試験 1 本。段 2 で型が block になったら、この試験を消して block の形の検査 `tests/layers/test_block_shape.py` に任せる）。

型のモジュールの名は、確かめの表 `workflows/fix/src/duties.py` の `MODULES` の鍵（表の 1 か所。ここに名を写さない）。照らすのは
`from src import <名>`・`from src.<名> import …`・`import src.<名>` の形の import（関数の中の import も）。型を問わない部品
（common・basecase・route・duties など）を import するのはよい。
"""
import ast
import pathlib
import unittest

from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = pathlib.Path("workflows/fix/src")


def weapon_names(root) -> list:
    """duties.py の MODULES の鍵（字の dict の鍵）"""
    mod = ast.parse((pathlib.Path(root) / SRC / "duties.py").read_text(encoding="utf-8"))
    for node in mod.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MODULES" for t in node.targets):
            return [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
    return []


def problems(root) -> list:
    names = weapon_names(root)
    out = [] if names else [f"{SRC}/duties.py に MODULES の表が無い"]
    for name in names:
        path = pathlib.Path(root) / SRC / f"{name}.py"
        if not path.is_file():
            out.append(f"{SRC}/{name}.py が無い（型のモジュール）")
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            got = []
            if isinstance(node, ast.ImportFrom) and node.module == "src":
                got = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("src."):
                got = [node.module.split(".")[1]]
            elif isinstance(node, ast.Import):
                got = [a.name.split(".")[1] for a in node.names if a.name.startswith("src.")]
            for other in got:
                if other in names and other != name:
                    out.append(f"{SRC}/{name}.py:{node.lineno}: 型のモジュール {other} を import する（型どうしは注文と返しのファイルだけで受け渡す）")
    return out


class WeaponImportsTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(problems(ROOT), [])

    def test_names_come_from_the_table(self):
        self.assertIn("tdd", weapon_names(ROOT))
        self.assertIn("variant", weapon_names(ROOT))

    def test_import_of_another_weapon_is_red(self):
        table = 'MODULES = {"tdd": tdd, "variant": variant}\n'
        for text in ("from src import variant\n", "from src.variant import x\n", "import src.variant\n",
                     "def f():\n    from src import common, variant\n"):
            with self.subTest(text=text), tree({f"{SRC}/duties.py": table, f"{SRC}/tdd.py": text, f"{SRC}/variant.py": ""}) as root:
                got = problems(root)
                self.assertTrue(any("tdd.py" in line and "variant" in line for line in got), got)

    def test_import_of_a_shared_part_is_not_red(self):
        table = 'MODULES = {"tdd": tdd, "variant": variant}\n'
        with tree({f"{SRC}/duties.py": table, f"{SRC}/tdd.py": "from src import common, route\n", f"{SRC}/variant.py": ""}) as root:
            self.assertEqual(problems(root), [])
