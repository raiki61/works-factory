"""ファイルの名の字の定数は 1 か所で定義する（落とし穴 K20。持ち主の決め concept-home）。

lib/*.py と workflows/*/scripts/*.py のモジュールの頭の代入（`NAME = "x.json"`・`A, B = "a.md", "b.md"`・注釈つき）のうち、
字が .json・.md・.txt・.diff で終わる物を集め、同じ字の定義が 2 か所以上なら赤。写しの値は片方だけ直すとずれる。
- lib を読めない時にも返りを書く script（落とし穴 K1 の逃げ道）が持つ写しは、表 FALLBACKS に行ごとに名指して許す
- 今の lib の中の重なりは、表 OVERLAPS に行ごとに名指して許す（住処でない方の定義を名指す）
- どちらの表も、行が今の木の定義に当たらないか、その字が 1 か所にしか無ければ赤
ast で読むだけ（子のプロセスなし）。
"""
import ast
import pathlib
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
ROOT = LIB.parent
SUFFIXES = (".json", ".md", ".txt", ".diff")
FALLBACK = "lib を読めない時にも返りの約束の形を書く逃げ道の写し（K1）。lib の値との一致は script の頭の注記の試験が縛る"
BARE = "境の口か隣の place を読めない時の逃げ道 bare の写し（K1）。place.UNWRITTEN と字が違えば行が当たらず赤"

# (定義の在る所, 名) -> 訳
FALLBACKS = {
    ("workflows/plan-review/scripts/result.py", "REVIEW_FILE"): FALLBACK + "（boardview.REVIEW_FILE）",
    ("workflows/plan-review/scripts/result.py", "DESIGN_FILE"): FALLBACK + "（design.DESIGN_FILE）",
    ("workflows/plan-review/scripts/result.py", "PASSES_FILE"): FALLBACK + "（boardview.PASSES_FILE）",
    ("workflows/plan-review/scripts/pass_open.py", "OPEN_FILE"): FALLBACK + "（boardview.OPEN_FILE）",
    ("workflows/plan-review/scripts/pass_open.py", "OPEN_ERROR"): FALLBACK + "（boardview.OPEN_ERROR）",
    ("workflows/plan/scripts/plan_collect.py", "ROUND_FILE"): FALLBACK + "（planfile.ROUND_FILE）",
    ("workflows/plan/scripts/plan_collect.py", "STATE_FILE"): FALLBACK + "（structmark.STATE_FILE）",
    ("workflows/plan/scripts/plan_collect.py", "RIPPLE_FILE"): FALLBACK + "（planfile.RIPPLE_FILE）",
    ("workflows/plan/scripts/round.py", "ROUND_FILE"): FALLBACK + "（planfile.ROUND_FILE）",
    ("workflows/report/scripts/facts.py", "UNWRITTEN"): BARE,
    ("workflows/report/scripts/collect.py", "UNWRITTEN"): BARE,
}

# (定義の在る所, 名) -> 訳。住処は訳の頭に書いた方
OVERLAPS = {
    ("lib/planfile.py", "BRIEF_FILE"): "planbrief.NAME の写し。区分 P。区分の issue で外す",
    ("lib/judge_accept.py", "REJUDGE_BRIEF"):
        "再審の支度が置く別のファイルで、fixrules.BRIEF（修正の決まりの brief.md）と字だけ同じ。区分 J。区分の issue で外す",
    ("lib/judge_accept.py", "COUNT_BUDGET_FILE"): "recount.COUNT_BUDGET_FILE の写し。区分 J。区分の issue で外す",
    ("lib/judge_accept.py", "COUNT_CACHE_FILE"): "recount.COUNT_CACHE_FILE の写し。区分 J。区分の issue で外す",
    ("lib/fixboard.py", "DEPTH_FILE"):
        "fix の置き場の深さの写し（plan の返り depth の形）で、depth.FILE（盤面の根の控え）と字だけ同じ。区分 F。区分の issue で外す",
    ("lib/eyeverdict.py", "DESIGN_PREMISES"): "boardview.PREMISES_FILE の写し（plan-review の隣のファイルを名で開く）。区分 E。区分の issue で外す",
    ("lib/eyeverdict.py", "GATE_PASSES"): "boardview.PASSES_FILE の写し。区分 E。区分の issue で外す",
    ("lib/runreport.py", "GATE_PASSES"): "boardview.PASSES_FILE の写し。区分 R。区分の issue で外す",
    ("lib/report.py", "VERIFY_NOTES"): "judgeverify.VERIFY_FILE の写し。区分 R。区分の issue で外す",
    ("lib/boardview.py", "JUDGMENT_COPY"): "judge_accept.JUDGMENT_FILE の写し。区分 P。区分の issue で外す",
    ("lib/fixboard.py", "JUDGMENT_FILE"): "judge_accept.JUDGMENT_FILE の写し。区分 F。区分の issue で外す",
    ("lib/outcome.py", "MATERIALS_FILE"): "judge_accept.MATERIALS_FILE（書き手）の写し。区分 R。区分の issue で外す",
    ("lib/fixboard.py", "PLAN_REPLY_FILE"): "planfile.FIX_PLAN_FILE の写し。区分 F。区分の issue で外す",
    ("lib/runreport.py", "FIX_PLAN"): "planfile.FIX_PLAN_FILE の写し。区分 R。区分の issue で外す",
    ("lib/runreport.py", "PREMISES"): "premises.PREMISES_FILE の写し。区分 R。区分の issue で外す",
    ("lib/boardview.py", "REPLAN_FILE"):
        "事前審査の pass-<k>/ に置く別のファイルで、replan.TRIP_FILE（計画の周の控え）と字だけ同じ。区分 P。区分の issue で外す",
    ("lib/fixboard.py", "RIPPLE_FILE"): "planfile.RIPPLE_FILE の写し。区分 F。区分の issue で外す",
    ("lib/worldblk.py", "INTAKE"):
        "世界の解の段の置き場に置く別のファイル（段の入口の控え）で、judge_accept.INTAKE_FILE（判定の入口の返り）と字だけ同じ。"
        "区分 J。区分の issue で外す",
    ("lib/judge_accept.py", "START_FILE"): "startrec.NAME の写し。区分 J。区分の issue で外す",
    ("lib/planblk.py", "SYNERGY_FILE"):
        "事前審査の答えのフォルダに置く別のファイルで、judgeverify.SYNERGY_FILE と字だけ同じ。区分 P。区分の issue で外す",
    ("lib/fixboard.py", "UNITS_FILE"): "fix の置き場の入力 units の写しで、planfile.UNITS_FILE と字だけ同じ。区分 F。区分の issue で外す",
}


def file_name_constants(root: pathlib.Path) -> dict[str, list[tuple[str, str]]]:
    """字 -> [(定義の在る所, 名)]。lib/*.py と workflows/*/scripts/*.py のモジュールの頭の代入だけを見る"""
    found: dict[str, list[tuple[str, str]]] = {}
    paths = sorted(root.glob("lib/*.py")) + sorted(root.glob("workflows/*/scripts/*.py"))
    for path in paths:
        where = path.relative_to(root).as_posix()
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign):
                pairs = [(target, node.value) for target in node.targets]
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                pairs = [(node.target, node.value)]
            else:
                continue
            for target, value in pairs:
                if isinstance(target, ast.Tuple) and isinstance(value, ast.Tuple) and len(target.elts) == len(value.elts):
                    named = zip(target.elts, value.elts)
                else:
                    named = [(target, value)]
                for name, literal in named:
                    if (isinstance(name, ast.Name) and isinstance(literal, ast.Constant)
                            and isinstance(literal.value, str) and literal.value.endswith(SUFFIXES)):
                        found.setdefault(literal.value, []).append((where, name.id))
    return found


def overlaps(found: dict[str, list[tuple[str, str]]], allowed) -> dict[str, list[tuple[str, str]]]:
    """表に無い定義が 2 つ以上残る字 -> 残った定義"""
    left = {literal: [row for row in rows if row not in allowed] for literal, rows in found.items()}
    return {literal: rows for literal, rows in left.items() if len(rows) > 1}


def idle_rows(found: dict[str, list[tuple[str, str]]], allowed) -> list[tuple[str, str]]:
    """表の行のうち、今の木の定義に当たらないか、その字が 1 か所にしか無い行"""
    shared = {row for rows in found.values() if len(rows) > 1 for row in rows}
    return sorted(row for row in allowed if row not in shared)


class ConstantsCase(unittest.TestCase):
    def test_same_file_name_literal_is_defined_once(self):
        found = file_name_constants(ROOT)
        allowed = FALLBACKS.keys() | OVERLAPS.keys()
        self.assertEqual(overlaps(found, allowed), {}, "同じファイルの名の字を 2 か所で定義する")
        self.assertEqual(idle_rows(found, allowed), [], "表の行が今の木の重なりに当たらない")

    def test_every_allowed_row_has_a_reason(self):
        self.assertFalse(FALLBACKS.keys() & OVERLAPS.keys())
        for row, reason in {**FALLBACKS, **OVERLAPS}.items():
            with self.subTest(row=row):
                self.assertTrue(reason.strip())
        for row in FALLBACKS:
            self.assertTrue(row[0].startswith("workflows/"), row)

    def test_a_second_definition_is_red(self):
        """lib の 2 つと script の 1 つが同じ字を持てば赤。表で許した行は数えず、関数の中の代入と別の拡張子は見ない。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "lib").mkdir()
            (root / "workflows" / "blk" / "scripts").mkdir(parents=True)
            (root / "lib" / "home.py").write_text('FILE = "x.json"\nOTHER: str = "y.diff"\n', encoding="utf-8")
            (root / "lib" / "copy.py").write_text('A, B = "x.json", "z.md"\nC = "y.jsonl"\n'
                                                  'def f():\n    D = "y.diff"\n', encoding="utf-8")
            (root / "workflows" / "blk" / "scripts" / "s.py").write_text('E = "y.diff"\n', encoding="utf-8")
            found = file_name_constants(root)
            self.assertEqual(overlaps(found, set()), {
                "x.json": [("lib/copy.py", "A"), ("lib/home.py", "FILE")],
                "y.diff": [("lib/home.py", "OTHER"), ("workflows/blk/scripts/s.py", "E")],
            })
            allowed = {("lib/copy.py", "A"), ("workflows/blk/scripts/s.py", "E"), ("lib/copy.py", "B")}
            self.assertEqual(overlaps(found, allowed), {})
            self.assertEqual(idle_rows(found, allowed), [("lib/copy.py", "B")])


if __name__ == "__main__":
    unittest.main()
