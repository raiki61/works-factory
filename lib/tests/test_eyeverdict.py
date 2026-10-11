"""独立の目の返りを組む部品（lib/eyeverdict.py）の検査。関数を直に呼び、一時の置き場に目の返りのファイルを書くだけ。

場の出どころ（今の works 2aa7c66c の works/tests/）:
- R4 の問いから人が通した行を外す: test_plan_gate.py の R4GateCase・test_gate_drafts.py の R4PushTailCase（盤面でなく値で写す）
- 落ちた筋の文: test_blk_eyes_lanes.py の fell_text の場
"""
import json
import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import eyeverdict  # noqa: E402
import gatemarks  # noqa: E402

STANDS = {"question_stands": True, "reason": "問いは立つ", "design": "設計の本文"}
FALLS = {"question_stands": False, "reason": "問いが立たない", "premise_invalid_reason": "既存の機構で満たされている"}
MISSING = {"missing": "設計の役が 3 回とも拒まれた"}
NARROW = "修正案 1 が狭める能力: 古い入口——使う人がいない"
BODY = "古い入口——使う人がいない"
PASSED = {("regression", BODY): 1}
OK_PROTECTED = {"hits": [], "lines": [], "broken": ""}

DIFF = """diff --git a/a.py b/a.py
index 1..2 100644
--- a/a.py
+++ b/a.py
@@ -1,2 +1,3 @@
 keep
-old
+new
+more
diff --git a/docs/x.md b/docs/x.md
new file mode 100644
--- /dev/null
+++ b/docs/x.md
@@ -0,0 +1 @@
+doc line
"""


class DueCase(unittest.TestCase):
    def test_compare_is_due_only_when_the_question_stands_and_purpose_is_known(self):
        self.assertTrue(eyeverdict.r2_compare_due(STANDS, "目的"))
        self.assertFalse(eyeverdict.r2_compare_due(STANDS, "  "))
        self.assertFalse(eyeverdict.r2_compare_due(FALLS, "目的"))
        self.assertFalse(eyeverdict.r2_compare_due(MISSING, "目的"))

    def test_premise_is_invalid_only_when_the_design_says_no_question(self):
        self.assertTrue(eyeverdict.r2_premise_invalid(FALLS))
        self.assertFalse(eyeverdict.r2_premise_invalid(STANDS))
        self.assertFalse(eyeverdict.r2_premise_invalid(MISSING))
        self.assertFalse(eyeverdict.r2_premise_invalid({"missing": "x", "question_stands": False}))


class ScalarsCase(unittest.TestCase):
    def test_counts_lines_and_files_from_the_diff(self):
        self.assertEqual(eyeverdict.scalars(DIFF),
                         {"added_lines": 3, "deleted_lines": 1, "doc_lines": 1, "files": ["a.py", "docs/x.md"]})

    def test_empty_diff_counts_zero(self):
        self.assertEqual(eyeverdict.scalars(""), {"added_lines": 0, "deleted_lines": 0, "doc_lines": 0, "files": []})

    def test_unreadable_diff_is_named_not_zero(self):
        got = eyeverdict.scalars("これは差分でない")
        self.assertNotIn("added_lines", got)
        self.assertIn("unmeasured", got)
        self.assertIn("測れなかった", eyeverdict.scalars_text(got))


class HumanPassedCase(unittest.TestCase):
    QUESTIONS = [NARROW, "事前審査の穴 [policy] k: 方針の第 2 項とぶつかる", "問いの台帳の問い q1: どちらにするか"]

    def test_pass_words_return_narrow_and_face_rows_without_heads(self):
        for word in ("approve", "continue"):
            with self.subTest(word):
                got = eyeverdict._human_passed(self.QUESTIONS, {"decision": word, "text": ""})
                self.assertEqual(got, {("regression", BODY): 1, ("policy", "方針の第 2 項とぶつかる"): 1})

    def test_stop_words_and_no_answer_pass_nothing(self):
        for answer in ({"decision": "stop", "text": ""}, {"decision": "reject", "text": ""}, None):
            with self.subTest(answer):
                self.assertEqual(eyeverdict._human_passed(self.QUESTIONS, answer), {})

    def test_push_tail_is_dropped(self):
        """R4PushTailCase: 推しの尾の付いた問いでも、尾の無い本文で照らす"""
        got = eyeverdict._human_passed([NARROW + "／推し: continue（使う人がいない）"], {"decision": "continue", "text": ""})
        self.assertEqual(got, PASSED)


class R4GateCase(unittest.TestCase):
    def test_r4_does_not_reask_narrow_the_human_passed(self):
        r4 = {"capability_inventory": {"fired": True, "lost": [BODY]}, "policy_conflicts": []}
        self.assertEqual(eyeverdict.r4_gate_items(r4, PASSED), [])

    def test_r4_reasks_other_kind_or_unpassed(self):
        for label, r4, passed in (
                ("種類が違う", {"capability_inventory": {"fired": True, "lost": []}, "policy_conflicts": [BODY]}, PASSED),
                ("通していない", {"capability_inventory": {"fired": True, "lost": [BODY]}, "policy_conflicts": []}, {}),
                ("本文が違う", {"capability_inventory": {"fired": True, "lost": ["古い入口——別の理由"]}, "policy_conflicts": []}, PASSED)):
            with self.subTest(label):
                self.assertEqual(len(eyeverdict.r4_gate_items(r4, passed)), 1)

    def test_rows_carry_the_r4_heads(self):
        r4 = {"capability_inventory": {"fired": True, "lost": ["a"]}, "policy_conflicts": ["b"]}
        self.assertEqual(eyeverdict.r4_gate_items(r4, {}),
                         ["R4 が BASE から消えたと見た能力: a", "R4 が見た人の方針とのぶつかり: b"])

    def test_no_r4_asks_nothing(self):
        self.assertEqual(eyeverdict.r4_gate_items(None, PASSED), [])

    def test_carried_section_lists_passed_rows_under_the_gatemarks_head(self):
        text = eyeverdict.carried_section(PASSED)
        self.assertTrue(text.startswith(gatemarks.CARRIED_HEAD))
        self.assertIn(gatemarks.CARRIED_ASK, text)
        self.assertIn(f"- [regression] {BODY}", text)
        self.assertEqual(eyeverdict.carried_section({}), "")


class FellTextCase(unittest.TestCase):
    FELL = [{"lane": "R1", "eye": "r1", "state": "返りのファイルが無い"},
            {"lane": "R2", "eye": "r2", "state": "返りのファイルが無い"}]

    def test_names_the_lanes_and_states(self):
        text = eyeverdict.fell_text(self.FELL)
        self.assertTrue(text.startswith("R1・R2 " + eyeverdict.FELL_MARK), text)
        self.assertIn("r1: 返りのファイルが無い・r2: 返りのファイルが無い", text)

    def test_names_what_ran_after_the_fall(self):
        self.assertTrue(eyeverdict.fell_text(self.FELL[:1], "R4").startswith("R1 " + eyeverdict.FELL_MARK + "まま R4 を回した"))


class CollectCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)

    def put(self, eye, doc):
        (self.dir / f"{eye}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def all_pass(self, *, r2=True, lost=()):
        self.put("r1", {"status": "pass", "reason": "最小", "deletions": [], "ledger_audit": [], "increments": []})
        if r2:
            self.put("r2", {"status": "pass", "reason": "構造は同じ", "differences": []})
        self.put("r3", {"status": "pass", "reason": "整合", "seen": [], "unseen": []})
        self.put("r4", {"status": "pass", "reason": "横断の危うさなし", "seen": [], "unseen": [], "surfaced": [],
                        "capability_inventory": {"fired": bool(lost), "lost": list(lost)}, "policy_conflicts": []})

    def collect(self, **kw):
        args = {"eyes_dir": self.dir, "run_eyes": True, "compare_due": True, "premise_due": False, "design": STANDS,
                "after_ptr": None, "protected": OK_PROTECTED, "passed": {}, **kw}
        return eyeverdict.collect(**args)

    def test_all_pass_is_ok(self):
        self.all_pass()
        got = self.collect()
        self.assertTrue(got["ok"])
        self.assertEqual(got["r2"], {"status": "pass", "reason": "構造は同じ"})
        self.assertEqual((got["questions"], got["premise_check"], got["protected_hits"]), ([], None, []))

    def test_r2_redesign_is_not_ok(self):
        self.all_pass()
        self.put("r2", {"status": "redesign-needed", "reason": "継ぎ目が違う", "differences": []})
        got = self.collect()
        self.assertFalse(got["ok"])
        self.assertEqual(got["r2"]["status"], "redesign-needed")

    def test_light_run_has_null_eyes_and_is_ok(self):
        got = self.collect(run_eyes=False, compare_due=False)
        self.assertEqual([got[k] for k in ("r1", "r2", "r3", "r4")], [None] * 4)
        self.assertTrue(got["ok"])

    def test_missing_eye_file_is_unverifiable_and_named(self):
        self.all_pass()
        (self.dir / "r1.json").unlink()
        got = self.collect()
        self.assertEqual(got["r1"]["status"], "unverifiable")
        self.assertTrue(got["r1"]["reason"].startswith("R1 " + eyeverdict.FELL_MARK), got["r1"]["reason"])
        self.assertIn("R4 を回した", got["r1"]["reason"])
        self.assertFalse(got["ok"])

    def test_unreadable_eye_file_is_unverifiable(self):
        self.all_pass()
        (self.dir / "r3.json").write_text("{", encoding="utf-8")
        got = self.collect()
        self.assertEqual(got["r3"]["status"], "unverifiable")
        self.assertIn(eyeverdict.FELL_MARK, got["r3"]["reason"])

    def test_missing_design_makes_r2_unverifiable(self):
        self.all_pass(r2=False)
        got = self.collect(design=MISSING, compare_due=False)
        self.assertEqual(got["r2"], {"status": "unverifiable", "reason": eyeverdict.R2_MISSING_HEAD + MISSING["missing"]})
        self.assertFalse(got["ok"])

    def test_premise_path_makes_r2_unverifiable_and_carries_the_check(self):
        self.all_pass(r2=False)
        self.put("premise-check", {"key": "k", "assumption": "a", "assumption_false": True, "evidence": "e",
                                   "verdict": "resolved", "reason": "実態で偽と示した"})
        got = self.collect(design=FALLS, compare_due=False, premise_due=True)
        self.assertEqual(got["r2"], {"status": "unverifiable", "reason": eyeverdict.R2_PREMISE_HEAD + FALLS["premise_invalid_reason"]})
        self.assertEqual(got["premise_check"], {"verdict": "resolved", "reason": "実態で偽と示した"})
        self.assertFalse(got["ok"])

    def test_fallen_premise_check_escalates(self):
        self.all_pass(r2=False)
        got = self.collect(design=FALLS, compare_due=False, premise_due=True)
        self.assertEqual(got["premise_check"]["verdict"], "escalate")
        self.assertIn(eyeverdict.FELL_MARK, got["premise_check"]["reason"])

    def test_questions_drop_the_rows_the_human_passed(self):
        self.all_pass(lost=(BODY, "別の能力"))
        got = self.collect(passed=PASSED)
        self.assertEqual(got["questions"], ["R4 が BASE から消えたと見た能力: 別の能力"])

    def test_unverified_protected_is_a_hit_and_not_ok(self):
        self.all_pass()
        row = eyeverdict.PROTECTED_UNKNOWN_ROW + "一覧が読めない"
        got = self.collect(protected={"hits": [row], "lines": [], "broken": "一覧が読めない"})
        self.assertEqual(got["protected_hits"], [row])
        self.assertFalse(got["ok"])
        self.assertEqual(got["r1"]["status"], "pass")

    def test_fallen_protected_node_is_a_hit(self):
        self.all_pass()
        got = self.collect(protected=None)
        self.assertTrue(got["protected_hits"][0].startswith(eyeverdict.PROTECTED_UNKNOWN_ROW))
        self.assertFalse(got["ok"])

    def test_protected_hits_are_carried_without_failing_the_eyes(self):
        self.all_pass()
        got = self.collect(protected={"hits": ["pack.json"], "lines": ["pack.json（+1 −0）: 規則 p"], "broken": ""})
        self.assertEqual(got["protected_hits"], ["pack.json"])
        self.assertTrue(got["ok"])

    def test_unverified_fills_the_contract_shape(self):
        got = eyeverdict.unverified("支度の節が落ちた", ["x"])
        self.assertEqual(set(got), set(eyeverdict.RETURN_FIELDS))
        self.assertFalse(got["ok"])
        self.assertEqual([got[k]["status"] for k in ("r1", "r2", "r3", "r4")], ["unverifiable"] * 4)
        self.assertEqual((got["questions"], got["premise_check"], got["structure_after"], got["protected_hits"]),
                         ([], None, None, ["x"]))


class DesignReadCase(unittest.TestCase):
    def test_missing_or_unreadable_design_names_why(self):
        self.assertIn("missing", eyeverdict.read_design(None))
        with tempfile.TemporaryDirectory() as tmp:
            bad = pathlib.Path(tmp) / "design.json"
            bad.write_text("[]", encoding="utf-8")
            self.assertIn("missing", eyeverdict.read_design(bad))
            bad.write_text(json.dumps(STANDS), encoding="utf-8")
            self.assertEqual(eyeverdict.read_design(bad), STANDS)


class PromptTextsCase(unittest.TestCase):
    def texts(self, **kw):
        args = {"units": [{"id": "u1", "paths": ["a.py"], "summary": "入口が古い"}],
                "fix_units": [{"unit_id": "u1", "group_id": "g1", "status": "fixed", "reason": "直した"}],
                "changed": {"premise_drift": False, "mechanism_changed": True}, "answer": None, "constraints": None,
                "green_ok": True, "ripple_file": "/r/ripple.json", "world_file": "", "passed": {}, **kw}
        return eyeverdict.prompt_texts(**args)

    def test_units_fixes_and_context_are_listed(self):
        got = self.texts()
        self.assertIn("u1", got["units_text"])
        self.assertIn("fixed", got["fixes_text"])
        self.assertIn("/r/ripple.json", got["r4_context"])
        self.assertIn("mechanism_changed", got["r4_context"])
        self.assertEqual(got["carried"], "")

    def test_green_line_only_when_not_certified(self):
        self.assertEqual(self.texts()["green_line"], "")
        for green in (False, None):
            with self.subTest(green):
                self.assertIn("認証が通っていない", self.texts(green_ok=green)["green_line"])

    def test_premises_name_the_late_answer_drift_and_constraints(self):
        got = self.texts(answer={"decision": "continue", "text": "古い入口は消してよい"}, changed={"premise_drift": True},
                         constraints=[{"kind": "measured", "text": "1 デプロイは 2 リポジトリ"}])["premises_text"]
        self.assertIn("古い入口は消してよい", got)
        self.assertIn("前提のずれの申告が在る", got)
        self.assertIn("1 デプロイは 2 リポジトリ", got)

    def test_premises_say_what_was_not_passed(self):
        got = self.texts()["premises_text"]
        self.assertIn("渡っていない", got)
        self.assertIn("前提のずれの申告は無い", got)


if __name__ == "__main__":
    unittest.main()
