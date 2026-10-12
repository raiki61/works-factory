"""構造の目の受け付けと出口の決定的な試験（blk-structure/lib/eye.py・scripts/collect.py）と、線の構造の境 h-structure の落ち所
（人の条件: 境の中の失敗は行なしで計画に進み、境の節そのものが落ちた周は h-plan の落ちと同じく計画なしで修正へ進まない）。
ブロックを通しで回す試験は test_blk_structure の EyeCase、計画の頭は test_blk_plan の StructureHeadCase が見る"""
import json
import pathlib
import re
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import eye  # noqa: E402

DOC = {"status": "ok", "reason": "", "units": [
    {"id": "u-1", "summary": "直す所", "paths": ["a.txt"], "status": "measured", "reason": "", "measure": {"churn": 3}},
    {"id": "u-2", "summary": "測れない所", "paths": ["b.txt"], "status": "failed", "reason": "x", "measure": None}],
    "timing": {"wall_s": 0.5}}
CLEAN = {"unit_id": "u-1", "verdict": "汚れない", "faces": [], "evidence": ["/units/0/measure/churn"], "reason": "形が増えない"}
DIRTY = {"unit_id": "u-1", "verdict": "汚れる", "faces": [2], "evidence": ["/units/0/measure"], "reason": "責務を割る",
         "chosen": "1 か所に固める", "chosen_reason": "読み直しを割らない"}


# 今の works の設計書 works/docs/specs/2026-09-29-structure-block-design.md:63-68（pack.json の works.commit の版
# 2aa7c66cf7abe1fe09699ac2942d107123214168）の 4 節「構造の目」の番号つきの一覧を字のまま（works-factory に設計書の 4 節は無い）
DESIGN_DOC_FORMS = """\
  1. 共有の物を run や呼び手ごとに書き換える
  2. 責務を 2 か所に割る
  3. 既存の仕組みを横から曲げる
  4. ブロックの境をまたいで、他のブロックの中身を前提にする
  5. 骨組みの無いまま新しい名前や口を足す
  6. 外の道具の事情を名指しで抱え込む
"""
# 設計書の字に許した直し（元の字, 写しの字）。持ち主の決め graph-words で語をグラフの語にそろえた物だけ
DESIGN_DOC_REWRITES = (("ブロックの境をまたいで、他のブロックの中身", "サブグラフの境をまたいで、他のサブグラフの中身"),)


class EyeLoopGateCase(unittest.TestCase):
    """元 tests/test_structure_eye.py の EyeLoopGateCase: 目は実測が ok で測れた単位が 1 つ以上の周だけ起こす"""

    def test_due_needs_ok_and_a_measured_unit(self):
        self.assertEqual((eye.due(DOC), eye.due({**DOC, "status": "failed"}), eye.due({**DOC, "units": DOC["units"][1:]})),
                         (True, False, False))


class EyeAcceptCase(unittest.TestCase):
    def test_six_forms_match_the_design_doc(self):
        """6 つの形の文は設計書の番号つきの一覧と、許した直しのほかは一字も違わない（faces の 1〜6 の意味の正本は設計書）"""
        forms = DESIGN_DOC_FORMS
        for original, copied in DESIGN_DOC_REWRITES:
            self.assertEqual(forms.count(original), 1, original)
            forms = forms.replace(original, copied)
        self.assertEqual(tuple(re.findall(r"^  \d\. (.+)$", forms, re.M)), eye.FORMS)

    def test_prompt_carries_only_measured_units_and_the_forms(self):
        prompt = eye.render(DOC)
        self.assertIn("u-1", prompt)
        self.assertNotIn("u-2", prompt)
        self.assertIn(eye.concepthome.EYE_ASK, prompt)
        for i, f in enumerate(eye.FORMS, 1):
            self.assertIn(f"{i}. {f}", prompt)
        self.assertNotIn(eye.REJECT_HEAD, prompt)
        again = eye.render(DOC, "evidence が空")
        self.assertTrue(again.startswith(f"{eye.REJECT_HEAD}\n\nevidence が空\n\nここを直した返答を丸ごと出し直せ"), again[:200])

    def test_own_decision_row_must_not_carry_undecided(self):
        got = eye.problems(DOC, {"rows": [{**DIRTY, "undecided_because": "人の前の決定が 2 つの置き場を別々に推している"}]})
        self.assertEqual(got, [f"行 0（u-1）: undecided_because は {eye.ROUTE_UP}行だけに書く"])

    def test_own_decision_row_gets_default_route(self):
        with tempfile.TemporaryDirectory() as d:
            s = pathlib.Path(d) / "structure.json"
            s.write_text(json.dumps(DOC, ensure_ascii=False), encoding="utf-8")
            design = pathlib.Path(d) / "design.jsonl"
            design.write_bytes(b"")
            eye.prep(s)
            self.assertTrue(eye.accept(s, design, {"rows": [DIRTY]})["ok"])
            row = json.loads(design.read_text(encoding="utf-8"))
        self.assertEqual((row["route"], row["route_reason"]), (eye.ROUTE, eye.ROUTE_REASON))
    def test_prompt_asks_chosen_to_follow_world_practice(self):
        """単位の要約の尾の世界の解の要点を読み、避け方 chosen を定石の作りに沿わせ、沿わないなら訳を chosen_reason に書けと頼む
        （計画 world-solution の W8・5.3 節の 3。入力の契約は 3 つのまま）"""
        prompt = eye.render(DOC)
        rule = next((ln for ln in prompt.splitlines() if "定石" in ln), "")
        self.assertIn("chosen", rule)
        self.assertIn("chosen_reason", rule)
        self.assertIn("世界の解", rule)

    def test_good_rows_pass(self):
        self.assertEqual(eye.problems(DOC, {"rows": [CLEAN]}), [])
        self.assertEqual(eye.problems(DOC, {"rows": [DIRTY]}), [])

    def test_bad_rows_are_named(self):
        """行の意味の外れ（行の形の外れ——知らない行き先・形の外の欄・形の番号の型——は目の節の output_format が拒む。
        tests/workflows/test_plan.py の EyeTypeCase）"""
        for name, rows in (("汚れるで避け方が無い", [{**DIRTY, "chosen": ""}]),
                           ("汚れるで形が無い", [{**DIRTY, "faces": []}]),
                           ("測れなかった単位", [CLEAN, {**CLEAN, "unit_id": "u-2"}]),
                           ("同じ単位の 2 行", [CLEAN, CLEAN]),
                           ("行が無い", []),
                           ("ポインタでない根拠", [{**CLEAN, "evidence": ["units/0/measure"]}]),
                           ("前に 0 を付けた添字", [{**CLEAN, "evidence": ["/units/00/measure"]}]),
                           ("測れなかった単位の null", [{**CLEAN, "evidence": ["/units/1/measure"]}])):
            with self.subTest(name):
                self.assertTrue(eye.problems(DOC, {"rows": rows}))
        self.assertTrue(eye.problems(DOC, None))

    def test_route_up_needs_reason(self):
        """人に上げる行は、決め手を当たっても決まらない訳（undecided_because）と、捨てた案と代償（rejected）が要る。汚れない行は上げない"""
        up = {**DIRTY, "route": "人に上げる", "rejected": [{"option": "2 か所に置く", "cost": "読み直しが割れる"}],
              "undecided_because": "人の前の決定が 2 つの置き場を別々に推していて、どちらにも決まらない"}
        self.assertEqual(eye.problems(DOC, {"rows": [up]}), [])
        for name, bad in (("訳が無い", {"undecided_because": ""}), ("捨てた案が無い", {"rejected": []}),
                          ("汚れないのに上げる", {"verdict": "汚れない", "faces": []})):
            with self.subTest(name):
                got = eye.problems(DOC, {"rows": [{**up, **bad}]})
                self.assertTrue(got, name)
        self.assertTrue(any("undecided_because" in g for g in eye.problems(DOC, {"rows": [{**up, "undecided_because": ""}]})))

    def test_route_up_row_written(self):
        """受け付けた人に上げる行は、行き先とその訳（route_reason＝決まらない訳）を design.jsonl に残す。自分で決める行は既定の訳"""
        up = {**DIRTY, "route": "人に上げる", "rejected": [{"option": "2 か所に置く", "cost": "読み直しが割れる"}],
              "undecided_because": "人の前の決定が 2 つの置き場を別々に推していて、どちらにも決まらない"}
        with tempfile.TemporaryDirectory() as d:
            s = pathlib.Path(d) / "structure.json"
            s.write_text(json.dumps(DOC, ensure_ascii=False), encoding="utf-8")
            design = pathlib.Path(d) / "design.jsonl"
            design.write_bytes(b"")
            eye.prep(s)
            self.assertTrue(eye.accept(s, design, {"rows": [up]})["ok"])
            row = json.loads(design.read_text(encoding="utf-8"))
        self.assertEqual((row["route"], row["route_reason"], row["undecided_because"]),
                         ("人に上げる", up["undecided_because"], up["undecided_because"]))
        schema = json.loads((LIB / "design-row.schema.json").read_text(encoding="utf-8"))
        import accept  # noqa: F401  （写しの engine を sys.path に足す）
        from engine.schema import validate_schema
        self.assertEqual(validate_schema(row, schema), [])

    def test_prompt_carries_concepts_and_rules(self):
        """目に見せる物に、単位に当たる考えの地図の行・知る場所の数と、方針と根の地図の文書が載る（段 A が structure.json に置いた物）"""
        doc = {**DOC, "rules": {"policy": {"path": "POLICY.md", "text": "置き場は 1 つにする", "reason": ""},
                                "maps": "### 対象のリポジトリの地図\n\n- 地図なし", "reason": ""},
               "units": [{**DOC["units"][0], "concepts": {"rows": [{"id": "outcome", "map": "docs/concepts.md",
                                                                     "text": "### `outcome` run の結末"}],
                                                          "places": [{"concept": "outcome", "what": "結末の語", "path": "a.txt",
                                                                      "lines": 1, "home": False, "known_places": 3}]}},
                         DOC["units"][1]]}
        prompt = eye.render(doc)
        for want in ("置き場は 1 つにする", "### `outcome` run の結末", "known_places", "地図なし"):
            self.assertIn(want, prompt)
        self.assertEqual(eye.problems(doc, {"rows": [{**CLEAN, "evidence": ["/units/0/concepts/places/0/known_places"]}]}), [])

    def test_evidence_indexes_the_units_the_prompt_showed(self):
        """測れなかった単位が先に在っても、目が見た /units/0 は実測した単位を指す"""
        doc = {**DOC, "units": DOC["units"][::-1]}
        self.assertIn('"u-1"', eye.render(doc))
        self.assertEqual(eye.problems(doc, {"rows": [CLEAN]}), [])
        self.assertTrue(eye.problems(doc, {"rows": [{**CLEAN, "evidence": ["/units/1/measure"]}]}))

    def test_long_duplicates_are_cut_with_the_total(self):
        """大きいファイルの塊の一致が数百件でも、目に見せるのは先頭 DUP_SHOWN 件と全件の数（支度の出力を小さく保つ）"""
        dups = [{"line": i, "other_line": i, "path": "x.yaml"} for i in range(eye.DUP_SHOWN * 40)]
        doc = {**DOC, "units": [{**DOC["units"][0], "measure": {"paths": [{"path": "a.txt", "duplicates": dups}]}}]}
        got = eye.view(doc)["units"][0]["measure"]["paths"][0]
        self.assertEqual(len(got["duplicates"]), eye.DUP_SHOWN)
        self.assertEqual(got["duplicates_total"], len(dups))
        self.assertEqual(eye.problems(doc, {"rows": [{**CLEAN, "evidence": ["/units/0/measure/paths/0/duplicates_total"]}]}), [])
        self.assertLess(len(eye.render(doc)), 4000)

    def test_third_rejection_gives_up(self):
        with tempfile.TemporaryDirectory() as d:
            s = pathlib.Path(d) / "structure.json"
            s.write_text(json.dumps(DOC, ensure_ascii=False), encoding="utf-8")
            design = pathlib.Path(d) / "design.jsonl"
            design.write_bytes(b"")
            got = []
            for _ in range(eye.rolekit.GIVE_UP_AFTER):
                self.assertEqual(eye.prep(s)["attempt"], len(got) + 1)
                got.append(eye.accept(s, design, {"rows": []}))
            self.assertEqual([(g["ok"], g["done"], g["give_up"]) for g in got],
                             [(False, False, False), (False, False, False), (False, True, True)])
            self.assertEqual(eye.state(d)["status"], "gave_up")
            self.assertEqual(design.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
