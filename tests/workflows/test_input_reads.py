"""節の script は入力の字（INPUTS_<名>）を自分で json.loads しない。JSON に戻すのは境の口（workflows/.shared/boundary.py の
parsed・value・pointed・needed・items・flag・picked）だけ。

止めた Archon は output_format で宣言した欄の null と無い欄を、include の入力に空の字で渡す（tests/shared/test_archon_contract.py が
照らす）。json.loads("") は落ちるので、前の失敗の持ち越しの無い run が判定の入口で止まった（#265）。口は空の字を null と読む。

script の字を ast で読み、入力の字が流れ込む名（入力を代入した名・それを回した名・それを渡した script の中の関数の引数・入力の字を返す script の中の関数の返り）
を辿って、json.loads にそれが届けば赤にする。lib/ の関数・境の口・ファイルの読み（read_text）の返りは入力の字でないので、そこで辿りを切る。
"""
import ast
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]

SCRIPTS = sorted({*ROOT.glob("workflows/*/scripts/*.py"), *ROOT.glob("workflows/*/scripts/*/*.py")})
INPUT_HEAD = "INPUTS_"
FILE_READS = frozenset({"read_text", "read_bytes"})


def _input_name(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str) and node.value.startswith(INPUT_HEAD)
    return isinstance(node, ast.JoinedStr) and bool(node.values) and _input_name(node.values[0])


class _Flow:
    """1 つの script の中で、入力の字が流れ込む名"""

    def __init__(self, tree: ast.Module):
        self.tree = tree
        self.modules = {alias.asname or alias.name.split(".")[0] for node in ast.walk(tree)
                        if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
        self.functions = {node.name: node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.names: set[str] = set()
        self.returning: set[str] = set()   # script の中の関数で、返りが入力の字を持つ物
        while self._spread():
            pass

    def carries(self, node: ast.AST) -> bool:
        """式が入力の字（かその切れ端）を持つか"""
        if _input_name(node) or (isinstance(node, ast.Name) and node.id in self.names):
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in self.returning:
            return True
        if isinstance(node, ast.Call) and self._cuts(node.func):
            return False
        return any(self.carries(child) for child in ast.iter_child_nodes(node))

    def _cuts(self, func: ast.AST) -> bool:
        """返りが入力の字でない呼び: lib/ と境の口のモジュールの関数・入力の字を返さない script の中の関数・ファイルの読み"""
        if isinstance(func, ast.Name):
            return func.id in self.functions
        if isinstance(func, ast.Attribute):
            return func.attr in FILE_READS or (isinstance(func.value, ast.Name) and func.value.id in self.modules - {"os", "json"})
        return False

    def _spread(self) -> bool:
        before = len(self.names) + len(self.returning)
        for name, function in self.functions.items():
            if any(isinstance(node, ast.Return) and node.value is not None and self.carries(node.value)
                   for node in ast.walk(function)):
                self.returning.add(name)
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) and node.value is not None \
                    and self.carries(node.value):
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                    self._bind(target)
            elif isinstance(node, (ast.For, ast.comprehension)) and self.carries(node.iter):
                self._bind(node.target)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in self.functions:
                params = self.functions[node.func.id].args
                positional = [*params.posonlyargs, *params.args]
                for arg, param in zip(node.args, positional):
                    if self.carries(arg):
                        self.names.add(param.arg)
                for keyword in node.keywords:
                    if keyword.arg and self.carries(keyword.value):
                        self.names.add(keyword.arg)
        return len(self.names) + len(self.returning) != before

    def _bind(self, target: ast.AST) -> None:
        self.names |= {node.id for node in ast.walk(target) if isinstance(node, ast.Name)}


def _json_loads(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "loads" \
        and isinstance(node.func.value, ast.Name) and node.func.value.id == "json"


def input_decodes(path: pathlib.Path) -> list[str]:
    """script の中で入力の字を json.loads する所（パス:行）"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    flow = _Flow(tree)
    return [f"{path.relative_to(ROOT).as_posix()}:{node.lineno}" for node in ast.walk(tree)
            if _json_loads(node) and any(flow.carries(arg) for arg in node.args)]


class InputReadsCase(unittest.TestCase):
    def test_scripts_leave_input_decoding_to_the_boundary(self):
        self.assertTrue(SCRIPTS)
        self.assertEqual([hit for path in SCRIPTS for hit in input_decodes(path)], [])

    def test_the_rule_sees_through_names_and_helpers(self):
        """#265 の形（入力を関数の引数で受けて json.loads する）も、代入した名を通す形も拾い、ファイルの中身と口の返りは拾わない"""
        cases = {
            'def pointed(raw):\n    return json.loads(raw)\npointed(os.environ.get("INPUTS_PRIOR_FAILURES", "null"))\n': True,
            'raw = os.environ["INPUTS_GROUP"].strip()\ngroup = json.loads(raw) if raw else None\n': True,
            'LINE = {"a": os.environ.get("INPUTS_A", "")}\nfor name, raw in LINE.items():\n    json.loads(raw)\n': True,
            'v = json.loads(os.environ.get(f"INPUTS_{name}") or "null")\n': True,
            'path = boundary.pointed(os.environ["INPUTS_START"])\njson.loads(path.read_text(encoding="utf-8"))\n': False,
            'art = Path(os.environ["ARTIFACTS_DIR"]) / os.environ["INPUTS_DIR"]\njson.loads((art / "r.json").read_text())\n': False,
            'json.loads(os.environ.get("ARCHON_NODE_EXECUTION") or "{}")\n': False,
            'def given():\n    return {"a": os.environ.get("INPUTS_A")}\nline = given()\njson.loads(line["a"])\n': True,
            'def given():\n    return boundary.value(os.environ.get("INPUTS_A"))\njson.loads(given())\n': False,
        }
        for source, hit in cases.items():
            with self.subTest(source):
                tree = ast.parse("import json, os\nimport boundary\nfrom pathlib import Path\n" + source)
                flow = _Flow(tree)
                found = any(_json_loads(n) and any(flow.carries(a) for a in n.args) for n in ast.walk(tree))
                self.assertEqual(found, hit)

    def test_the_boundary_reads_empty_text_as_null(self):
        """宣言した null の欄が届く空の字を、口の読み手は全部「無い」と読む"""
        from tests.shared.test_boundary import boundary
        self.assertEqual((boundary.parsed(""), boundary.value(""), boundary.pointed(""), boundary.items(""), boundary.flag(""),
                          boundary.text("")),
                         (None, None, None, [], False, ""))
        with self.assertRaisesRegex(ValueError, "入力 start のポインタが無い"):
            boundary.needed("", "start")

    def test_picked_reads_only_the_named_fields(self):
        """まるごとの入力の字を、宣言した名だけの dict にする。欠けた名は None、宣言の外の名は [] でも .get でも KeyError。飛んだ節（null・
        空の字・無い入力）は None、dict でない値は ValueError"""
        from tests.shared.test_boundary import boundary
        raw = json.dumps({"ok": True, "hash": "123", "reason": "", "diff": None, "extra": 1})
        got = boundary.picked(raw, ("ok", "hash", "reason", "diff", "missing"))
        self.assertEqual(got, {"ok": True, "hash": "123", "reason": "", "diff": None, "missing": None})
        self.assertIsInstance(got, dict)
        self.assertEqual((got["hash"], got["reason"], got.get("diff"), got.get("missing")), ("123", "", None, None))
        for read in (lambda: got["extra"], lambda: got.get("extra"), lambda: got["typo"], lambda: got.get("typo")):
            with self.assertRaises(KeyError):
                read()
        for skipped in ("null", "", "  ", None):
            with self.subTest(skipped=skipped):
                self.assertIsNone(boundary.picked(skipped, ("ok",)))
        for not_dict in ("[]", "[1]", '"text"', "7", "true", "not json"):
            with self.subTest(not_dict=not_dict), self.assertRaises(ValueError):
                boundary.picked(not_dict, ("ok",))

    def test_picked_is_the_only_way_to_the_whole_dict(self):
        """返りまるごとを欄を削らずに戻す口は無い（素通しの口を置くと、宣言の外の欄が値として script に届く）"""
        from tests.shared.test_boundary import boundary
        self.assertFalse(hasattr(boundary, "passed"))


if __name__ == "__main__":
    unittest.main()
