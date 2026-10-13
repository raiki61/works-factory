"""独立の目の返りを組む部品（lib/eyeverdict.py）の検査。関数を直に呼び、一時の置き場に目の返りのファイルを書くだけ。

場の出どころ（今の works 2aa7c66c の works/tests/）:
- R4 の問いから人が通した行を外す: test_plan_gate.py の R4GateCase・test_gate_drafts.py の R4PushTailCase（盤面でなく値で写す）
- 落ちた筋: test_blk_eyes_lanes.py の FallenLaneCase（R1・R2 の筋が落ちても R4 を回し、落ちた筋を名指す）と fell_text の場
- 『渡されていない』の照らし: test_blk_eyes.py の claims_given の場（design の試験）を、出口が控えに並べる所で写す
"""
import ast
import json
import os
import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.dont_write_bytecode = True
LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import design  # noqa: E402
import eyeverdict  # noqa: E402
import gatemarks  # noqa: E402
import rolekit  # noqa: E402
import seal  # noqa: E402
from tests.bin.gitkit import git  # noqa: E402

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

    def test_premise_reason_prefers_the_named_field_then_the_reason(self):
        self.assertEqual(eyeverdict.premise_reason(FALLS), FALLS["premise_invalid_reason"])
        self.assertEqual(eyeverdict.premise_reason({"question_stands": False, "reason": "立たない"}), "立たない")
        self.assertEqual(eyeverdict.premise_reason({}), "")


class ScalarsCase(unittest.TestCase):
    def test_counts_lines_and_files_from_the_diff(self):
        self.assertEqual(eyeverdict.scalars(DIFF),
                         {"added_lines": 3, "deleted_lines": 1, "doc_lines": 1, "files": ["a.py", "docs/x.md"]})

    def test_empty_diff_counts_zero(self):
        self.assertEqual(eyeverdict.scalars(""), {"added_lines": 0, "deleted_lines": 0, "doc_lines": 0, "files": []})

    def test_hunk_lines_that_look_like_file_heads_are_counted(self):
        diff = ("diff --git a/doc.md b/doc.md\n--- a/doc.md\n+++ b/doc.md\n@@ -1,2 +1,2 @@\n"
                " title\n----\n+++i;\n")
        self.assertEqual(eyeverdict.scalars(diff), {"added_lines": 1, "deleted_lines": 1, "doc_lines": 1, "files": ["doc.md"]})

    def test_quoted_non_ascii_path_is_read(self):
        diff = ('diff --git "a/\\346\\226\\207.md" "b/\\346\\226\\207.md"\n--- "a/\\346\\226\\207.md"\n'
                '+++ "b/\\346\\226\\207.md"\n@@ -1 +1 @@\n-古い\n+新しい\n')
        self.assertEqual(eyeverdict.changed_files(diff), ["文.md"])
        self.assertEqual(eyeverdict.scalars(diff), {"added_lines": 1, "deleted_lines": 1, "doc_lines": 1, "files": ["文.md"]})

    def test_unreadable_diff_is_named_not_zero(self):
        got = eyeverdict.scalars("これは差分でない")
        self.assertNotIn("added_lines", got)
        self.assertIn("unmeasured", got)
        self.assertIn("測れなかった", eyeverdict.scalars_text(got))

    def test_untaken_diff_is_named_not_zero(self):
        got = eyeverdict.scalars("", {"x_endpoints": 2}, "累積差分が取れない（git が落ちた）")
        self.assertEqual(got, {"x_endpoints": 2, "unmeasured": ["累積差分が取れない（git が落ちた）"]})

    def test_fix_x_scalars_are_added(self):
        got = eyeverdict.scalars(DIFF, {"x_endpoints": 2})
        self.assertEqual(got["x_endpoints"], 2)
        self.assertEqual(got["added_lines"], 3)
        self.assertIn("x_endpoints 2", eyeverdict.scalars_text(got))

    def test_part_measured_returns_the_measured_part(self):
        """元の scalars と同じく、測れた値は返し、測れなかった訳を並べる（全部を捨てない）"""
        got = eyeverdict.scalars("これは差分でない", {"x_endpoints": 2})
        self.assertEqual(got["x_endpoints"], 2)
        self.assertEqual(got["unmeasured"], ["累積差分が git の差分の形でない"])
        text = eyeverdict.scalars_text(got)
        self.assertIn("x_endpoints 2", text)
        self.assertIn("測れなかった: 累積差分が git の差分の形でない", text)

    def test_x_scalars_outside_the_graph_shape_are_named(self):
        got = eyeverdict.scalars(DIFF, {"x_ok": 1, "endpoints": 2, "x_flag": True})
        self.assertEqual(got["x_ok"], 1)
        self.assertNotIn("endpoints", got)
        self.assertNotIn("x_flag", got)
        self.assertIn("endpoints・x_flag", got["unmeasured"][0])
        self.assertIn("object でない", eyeverdict.scalars(DIFF, [1])["unmeasured"][0])


class HumanPassedCase(unittest.TestCase):
    QUESTIONS = [gatemarks.question_row("regression", NARROW), gatemarks.question_row("policy", "事前審査の穴 [policy] k: 方針の第 2 項とぶつかる"),
                 gatemarks.question_row("fork", "問いの台帳の問い q1: どちらにするか")]

    def test_pass_words_return_narrow_and_face_rows_without_heads(self):
        for word in ("approve", "continue"):
            with self.subTest(word):
                got = eyeverdict._human_passed(self.QUESTIONS, {"decision": word, "text": ""})
                self.assertEqual(got, {("regression", BODY): 1, ("policy", "方針の第 2 項とぶつかる"): 1})

    def test_stop_words_and_no_answer_pass_nothing(self):
        for answer in ({"decision": "stop", "text": ""}, {"decision": "reject", "text": ""}, None):
            with self.subTest(answer):
                self.assertEqual(eyeverdict._human_passed(self.QUESTIONS, answer), {})



class R4PushTailCase(unittest.TestCase):
    """修正前の関所で人が通した狭まりの本文は、推しの尾を外して照らす。R4 が推しの尾の無い本文を写しても聞き直さない"""
    REC = {"answer": "continue", "note": "古い入口だけを消す範囲で通す", "why": "使う人がいないと測った"}

    def test_r4_does_not_reask_when_the_asked_row_had_a_push_tail(self):
        asked = NARROW + gatemarks._push({gatemarks.RECOMMEND: self.REC})   # 関所の項目の尾と同じ作り
        self.assertIn("／推し", asked)
        passed = eyeverdict._human_passed([gatemarks.question_row("regression", asked)], {"decision": "continue", "text": ""})
        self.assertNotIn("推し", eyeverdict.carried_section(passed))
        r4 = {"capability_inventory": {"fired": True, "lost": [BODY]}, "policy_conflicts": []}
        self.assertEqual(eyeverdict.r4_gate_items(r4, passed), [])


class R4GateCase(unittest.TestCase):
    """修正の後の関所の問い（R4 の行）が、修正前の関所で人が通した狭まりと種類も本文も同じ行を聞き直さない。
    元と同じく、修正前の関所の答えから _human_passed を通して照らす"""

    def r4_gate(self, answer="continue", lost=(), policy=()):
        passed = eyeverdict._human_passed([gatemarks.question_row("regression", NARROW)], {"decision": answer, "text": ""})
        r4 = {"capability_inventory": {"fired": True, "lost": list(lost)}, "policy_conflicts": list(policy)}
        return eyeverdict.r4_gate_items(r4, passed), eyeverdict.gate_passes(r4, passed)

    def test_r4_does_not_reask_narrow_the_human_passed(self):
        for word in ("continue", "approve"):
            with self.subTest(word):
                asked, kept = self.r4_gate(word, lost=[BODY])
                self.assertEqual(asked, [])
                self.assertEqual(kept, [{"node": "r4.human_gate", "round": 1, "by": "human",
                                         "item": "R4 が BASE から消えたと見た能力: " + BODY,
                                         "passed_at": {"node": "p2.human_gate", "round": 1}}])

    def test_r4_reasks_other_kind_or_unpassed(self):
        for label, kw in (("種類が違う", {"policy": [BODY]}), ("stop で答えた", {"answer": "stop", "lost": [BODY]}),
                          ("reject で答えた", {"answer": "reject", "lost": [BODY]}),
                          ("本文が違う", {"lost": ["古い入口——別の理由"]})):
            with self.subTest(label):
                asked, kept = self.r4_gate(**kw)
                self.assertEqual(len(asked), 1)
                self.assertEqual(kept, [])

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
    FELL = [{"lane": "R1", "eye": "r1", "state": "出力のファイルが無い"},
            {"lane": "R2", "eye": "r2", "state": "出力のファイルが無い"}]

    def test_names_the_lanes_and_states(self):
        text = eyeverdict.fell_text(self.FELL)
        self.assertTrue(text.startswith("R1・R2 " + eyeverdict.FELL_MARK), text)
        self.assertIn("r1: 出力のファイルが無い・r2: 出力のファイルが無い", text)

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

    def test_light_run_with_an_unconfirmed_protected_check_is_not_ok(self):
        for protected in (None, {"hits": [seal.unknown_row("一覧が読めない")], "lines": [],
                                 "broken": "一覧が読めない"}):
            with self.subTest(protected=protected):
                self.assertFalse(self.collect(run_eyes=False, compare_due=False, protected=protected)["ok"])

    def test_r2_not_compared_names_which_input_was_missing(self):
        self.all_pass(r2=False)
        for label, design, why in (("目的の文が空", STANDS, eyeverdict.R2_NO_PURPOSE),
                                   ("問いが立つかの欄が無い", {"reason": "書いていない", "design": "設計"}, eyeverdict.R2_NO_STANDS),
                                   ("問いが立つかの欄が真偽でない", {"question_stands": "yes"}, eyeverdict.R2_NO_STANDS)):
            with self.subTest(label):
                got = self.collect(design=design, compare_due=False, premise_due=False)
                self.assertEqual(got["r2"], {"status": "unverifiable", "reason": why})
                self.assertFalse(got["ok"])

    def test_any_redesign_eye_is_not_ok(self):
        for eye in eyeverdict.EYES:
            with self.subTest(eye):
                self.all_pass()
                self.put(eye, {"status": "redesign-needed", "reason": "直しが要る"})
                self.assertFalse(self.collect()["ok"])

    def test_missing_eye_file_is_unverifiable_and_named(self):
        self.all_pass()
        (self.dir / "r1.json").unlink()
        got = self.collect()
        self.assertEqual(got["r1"]["status"], "unverifiable")
        self.assertTrue(got["r1"]["reason"].startswith("R1 " + eyeverdict.FELL_MARK), got["r1"]["reason"])
        self.assertIn("R4 を回した", got["r1"]["reason"])
        self.assertFalse(got["ok"])

    def test_fallen_r2_lane_still_runs_r4_and_is_named(self):
        """FallenLaneCase: R2 の筋（比較役）が落ちても R4 は回り、r2 が落ちた筋を名指す"""
        self.all_pass()
        (self.dir / "r2.json").unlink()
        got = self.collect()
        self.assertEqual(got["r2"]["status"], "unverifiable")
        self.assertTrue(got["r2"]["reason"].startswith("R2 " + eyeverdict.FELL_MARK + "まま R4 を回した"), got["r2"]["reason"])
        self.assertEqual(got["r4"]["status"], "pass")
        self.assertFalse(got["ok"])

    def test_unreadable_eye_file_is_unverifiable(self):
        self.all_pass()
        (self.dir / "r3.json").write_text("{", encoding="utf-8")
        got = self.collect()
        self.assertEqual(got["r3"]["status"], "unverifiable")
        self.assertIn(eyeverdict.FELL_MARK, got["r3"]["reason"])

    def test_off_contract_status_is_named(self):
        """判定の語が約束の外の返りは、落ちた筋と「出力の判定の語が約束の外」を名指して unverifiable にする（元 review-record.py:443-454）"""
        self.all_pass()
        self.put("r3", {"status": "ok", "reason": "整合", "seen": [], "unseen": []})
        got = self.collect()
        self.assertEqual(got["r3"]["status"], "unverifiable")
        self.assertIn("約束の外", got["r3"]["reason"])
        self.assertTrue(got["r3"]["reason"].startswith("R3 "), got["r3"]["reason"])
        self.assertFalse(got["ok"])

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
        self.assertTrue(got["premise_check"]["reason"].startswith("R2 " + eyeverdict.FELL_MARK + "まま R4 を回した"),
                        got["premise_check"]["reason"])

    def test_questions_drop_the_rows_the_human_passed(self):
        self.all_pass(lost=(BODY, "別の能力"))
        got = self.collect(passed=PASSED)
        self.assertEqual(got["questions"], ["R4 が BASE から消えたと見た能力: 別の能力"])

    def test_unverified_protected_is_a_hit_and_not_ok(self):
        self.all_pass()
        row = seal.unknown_row("一覧が読めない")
        got = self.collect(protected={"hits": [row], "lines": [], "broken": "一覧が読めない"})
        self.assertEqual(got["protected_hits"], [row])
        self.assertFalse(got["ok"])
        self.assertEqual(got["r1"]["status"], "pass")

    def test_fallen_protected_node_is_a_hit(self):
        self.all_pass()
        got = self.collect(protected=None)
        self.assertTrue(got["protected_hits"][0].startswith(seal.UNKNOWN_HEAD))
        self.assertFalse(got["ok"])

    def test_protected_hits_are_carried_without_failing_the_eyes(self):
        self.all_pass()
        got = self.collect(protected={"hits": ["pack.json"], "lines": ["pack.json（+1 −0）: 規則 p"], "broken": ""})
        self.assertEqual(got["protected_hits"], ["pack.json"])
        self.assertTrue(got["ok"])

    def test_unverified_fills_the_contract_shape(self):
        got = eyeverdict.unverified("支度の節が落ちた", {"hits": ["x"], "lines": [], "broken": ""})
        self.assertEqual(set(got), set(eyeverdict.RETURN_FIELDS))
        self.assertFalse(got["ok"])
        self.assertEqual([got[k]["status"] for k in ("r1", "r2", "r3", "r4")], ["unverifiable"] * 4)
        self.assertEqual((got["questions"], got["premise_check"], got["structure_after"], got["protected_hits"]),
                         ([], None, None, ["x"]))

    def test_unverified_keeps_a_clean_protected_check_empty(self):
        self.assertEqual(eyeverdict.unverified("支度の節が落ちた", OK_PROTECTED)["protected_hits"], [])

    def test_unverified_fallen_or_malformed_protected_is_a_hit(self):
        for protected in (None, [], {"hits": "pack.json"}):
            with self.subTest(protected=protected):
                hits = eyeverdict.unverified("出口が落ちた", protected)["protected_hits"]
                self.assertTrue(hits[0].startswith(seal.UNKNOWN_HEAD), hits)


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
                "changed": {"premise_drift": False, "mechanism_changed": True}, "constraints": None,
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

    def test_constraints_text_says_when_not_passed(self):
        self.assertIn("渡っていない", self.texts()["constraints_text"])
        self.assertIn("1 デプロイは 2 リポジトリ",
                      self.texts(constraints=[{"kind": "measured", "text": "1 デプロイは 2 リポジトリ"}])["constraints_text"])

    def test_lang_line_keeps_keys_untranslated(self):
        """目の支度は始めの記録を丸ごと rolekit.lang_line に渡す（inputs.lang への代わりの取り方も効く）"""
        self.assertIn("依頼文の言語", rolekit.lang_line({"lang": ""}))
        self.assertIn("English で書け", rolekit.lang_line({"lang": "English"}))
        self.assertIn("English で書け", rolekit.lang_line({"inputs": {"lang": "English"}}))
        self.assertIn("key・enum の値", rolekit.lang_line({}))


class MeasuredSectionCase(unittest.TestCase):
    """R2 の比較役に貼る機械の実測（issue #384）。試験の関門が比べたテストごとの base と最後の結末を移り方ごとに全部名指し、
    段ごとの TDD の記録を報告と同じ行で並べ、測っていない時は推し量らずにそう書く"""

    OUTCOMES = {"rows": [{"key": "tests.test_stats.TestStats::test_clamp_above_range", "base": "failure", "final": "passed",
                          "fail_message": "AssertionError: 0 != 10"}], "unmeasured": ""}

    def test_names_the_test_red_at_base_and_green_at_the_end(self):
        got = eyeverdict.measured_section(self.OUTCOMES, [])
        self.assertIn("- 赤→緑（base で赤・最後に緑）: 1 件\n"
                      "  - `tests.test_stats.TestStats::test_clamp_above_range`（base failure: AssertionError: 0 != 10）", got)

    def test_names_every_test_green_at_both_ends_when_nothing_was_red(self):
        """較正の対照 control-clearer-names（run 90970124）: 振る舞いを変えない改名の run は赤が無い。緑→緑のテストの名が載らないと、
        比較役は既存のテストが観点を覆うかを確かめられないと読む"""
        rows = [{"key": f"tests.test_stats.TestStats::test_median_{n}", "base": "passed", "final": "passed", "fail_message": ""}
                for n in ("odd", "even", "single")]
        got = eyeverdict.measured_section({"rows": rows, "unmeasured": ""}, [])
        self.assertIn("- 緑→緑（base でも最後でも緑）: 3 件\n", got)
        for n in ("odd", "even", "single"):
            self.assertIn(f"  - `tests.test_stats.TestStats::test_median_{n}`\n", got + "\n")
        self.assertNotIn("- 赤→緑", got)

    def test_every_transition_is_named_in_a_fixed_order(self):
        rows = [{"key": "k::gone", "base": "passed", "final": "", "fail_message": ""},
                {"key": "k::same", "base": "passed", "final": "passed", "fail_message": ""},
                {"key": "k::stuck", "base": "error", "final": "failure", "fail_message": "boom"},
                {"key": "k::broke", "base": "passed", "final": "failure", "fail_message": "1 != 2"},
                {"key": "k::fixed", "base": "failure", "final": "passed", "fail_message": ""},
                {"key": "k::skip", "base": "skipped", "final": "skipped", "fail_message": ""}]
        got = eyeverdict.measured_section({"rows": rows, "unmeasured": ""}, [])
        heads = [line for line in got.splitlines() if line.startswith("- ") and line.endswith("件")]
        self.assertEqual(heads, ["- 赤→緑（base で赤・最後に緑）: 1 件", "- 緑→緑（base でも最後でも緑）: 1 件",
                                 "- 緑→赤（base で緑・最後に赤）: 1 件", "- 赤→赤（base でも最後でも赤）: 1 件",
                                 "- 緑→測っていない: 1 件", "- 飛ばし→飛ばし: 1 件"])
        self.assertIn("  - `k::broke`（最後 failure: 1 != 2）", got)
        self.assertIn("  - `k::stuck`（base error・最後 failure: boom）", got)

    def test_says_when_the_gate_did_not_compare(self):
        got = eyeverdict.measured_section({"rows": [], "unmeasured": "最後のテストは 1 件ごとの結末を取っていない"}, [])
        self.assertIn("比べていない（最後のテストは 1 件ごとの結末を取っていない）。テストごとの base と最後の結末は測っていない", got)
        self.assertIn("test_outcomes）が渡っていない", eyeverdict.measured_section(None, []))

    def test_no_row_is_said_not_left_empty(self):
        self.assertIn("base と最後のどちらの一式にもテストが居ない", eyeverdict.measured_section({"rows": [], "unmeasured": ""}, []))

    def test_lists_the_tdd_record_as_the_report_does(self):
        import report
        import tddloop
        proved = {"unit_key": "u1", "route": "tdd", "red": "ok", "green": "ok", "tests": ["tests/test_x.py::test_new"],
                  tddloop.QUOTES_FIELD: {"tests/test_x.py::test_new": {"quote": "AssertionError: 1 != 2", "why": "上限を見ていない"}}}
        direct = {"unit_key": "u2", "route": "direct", "red": "", "green": "", "tests": [], "why": "テストが書けない"}
        g1 = {"group_id": "g1", "ran": True, "reason": "", "suite": "", "reused": {}, "units": [proved, direct]}
        g2 = {"group_id": "g2", "ran": False, "reason": "実行器が無い", "suite": "", "reused": {}, "units": []}
        got = eyeverdict.measured_section(self.OUTCOMES, [[g1, g2]])
        for row in report.tdd_lines([("修正の段（組 g1）", g1), ("修正の段（組 g2）", g2)]):
            self.assertIn(row if row.startswith(" ") else f"- {row}", got)
        self.assertIn("赤 ok・緑 ok", got)
        self.assertIn("赤の引用 tests/test_x.py::test_new: 「AssertionError: 1 != 2」", got)
        self.assertIn("u2: 初めから今どおりの直し（テストが書けない）", got)
        self.assertIn("修正の段（組 g2）: TDD のループを回していない（実行器が無い）", got)
        self.assertIn("案を直した後の修正の段（組 g3）", eyeverdict.measured_section(self.OUTCOMES, [[], [{**g2, "group_id": "g3"}]]))

    def test_tdd_record_that_cannot_be_read_is_named(self):
        self.assertIn("TDD のループの記録を読めない（tdd-unit.json が無い）",
                      eyeverdict.measured_section(self.OUTCOMES, ["tdd-unit.json が無い"]))
        self.assertIn("修正の段が走っていない", eyeverdict.measured_section(self.OUTCOMES, []))

    def test_reads_the_tdd_record_beside_each_fix_diff(self):
        import fixboard
        with tempfile.TemporaryDirectory() as tmp:
            stage = pathlib.Path(tmp) / "fix"
            stage.mkdir()
            (stage / fixboard.TDD_UNIT_FILE).write_text(json.dumps([{"group_id": "g1", "ran": False}]), encoding="utf-8")
            got = eyeverdict.tdd_stages([str(stage / "fix.diff"), str(pathlib.Path(tmp) / "refix" / "fix.diff")], pathlib.Path)
        self.assertEqual(got[0], [{"group_id": "g1", "ran": False}])
        self.assertIn(f"refix/{fixboard.TDD_UNIT_FILE} が無い", got[1])
        self.assertEqual(eyeverdict.tdd_stages(None, pathlib.Path), [])

        def refuse(ptr):
            raise ValueError("ほかの run のポインタ")
        self.assertIn("diffs）のポインタが読めない（ほかの run のポインタ）", eyeverdict.tdd_stages([{}], refuse)[0])
        self.assertIn("並びでない", eyeverdict.tdd_stages({"type": "x"}, pathlib.Path)[0])


class OriginSectionCase(unittest.TestCase):
    """累積差分の起点の訳（issue #384）: 起点が PR の根か修正前の HEAD かを書き、PR の差分と直しの差分を分けて名指す"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name)
        git(self.repo, "init", "-q")
        (self.repo / "cli.py").write_text("name = argv[0]\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "root")
        self.root = git(self.repo, "rev-parse", "HEAD")

    def pr_commit(self):
        (self.repo / "cli.py").write_text("name = argv[1]\n", encoding="utf-8")
        git(self.repo, "commit", "-q", "-am", "pr")
        return git(self.repo, "rev-parse", "HEAD")

    def test_empty_diff_from_the_pr_root_names_both_diffs(self):
        head = self.pr_commit()
        (self.repo / "cli.py").write_text("name = argv[0]\n", encoding="utf-8")
        got = eyeverdict.origin_section(self.repo, self.root, head, "PR #7 の根", cumulative_empty=True)
        self.assertIn(f"起点は PR の根 `{self.root[:12]}`（PR #7 の根）", got)
        self.assertIn("PR の commit が 1 個", got)
        self.assertIn("PR の差分（起点 → 修正前の HEAD）で変わったファイル: cli.py", got)
        self.assertIn("この run の直しの差分（修正前の HEAD → 作業ツリー）で変わったファイル: cli.py", got)
        self.assertIn("PR の変更と直しが打ち消し合った", got)
        self.assertNotIn("何も変えていない", got)

    def test_origin_at_head_has_no_pr_diff(self):
        (self.repo / "cli.py").write_text("name = argv[1]\n", encoding="utf-8")
        got = eyeverdict.origin_section(self.repo, self.root, self.root, "", cumulative_empty=False)
        self.assertIn(f"起点は修正前の HEAD `{self.root[:12]}`", got)
        self.assertIn("PR の差分は無い", got)
        self.assertIn("直しの差分（修正前の HEAD → 作業ツリー）で変わったファイル: cli.py", got)
        self.assertNotIn("打ち消し", got)

    def test_nothing_changed_is_told_apart_from_cancelling(self):
        got = eyeverdict.origin_section(self.repo, self.root, self.root, "", cumulative_empty=True)
        self.assertIn("PR も直しも何も変えていない", got)

    def test_skipped_paths_are_left_out_of_the_pr_diff_too(self):
        (self.repo / "skipped").mkdir()
        (self.repo / "skipped" / "w.yaml").write_text("x: 1\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "pr")
        head = git(self.repo, "rev-parse", "HEAD")
        got = eyeverdict.origin_section(self.repo, self.root, head, "", cumulative_empty=True, skip=("skipped/",))
        self.assertNotIn("skipped", got)
        self.assertIn("PR の差分（起点 → 修正前の HEAD）で変わったファイル: 無い", got)

    @unittest.skipIf(os.geteuid() == 0, "root はモードを無視してファイルを読める")
    def test_unreadable_work_tree_is_said_not_raised(self):
        secret = self.repo / "secret"
        secret.write_text("s\n", encoding="utf-8")
        secret.chmod(0)
        self.addCleanup(secret.chmod, 0o644)
        got = eyeverdict.origin_section(self.repo, self.root, self.root, "", cumulative_empty=False)
        self.assertIn("累積差分の起点を測れない", got)

    def test_unknown_origin_is_said(self):
        self.assertIn("起点が分からない", eyeverdict.origin_section(self.repo, "", self.root, "", cumulative_empty=True))
        self.assertIn("起点を測れない", eyeverdict.origin_section(self.repo, "0" * 40, self.root, "", cumulative_empty=True))


class PremiseSectionCase(unittest.TestCase):
    """元 blk-eyes/lib/eyes.py の premise_section: 比較役の頭に、design.premises の人の答え・依頼が名指した設計書の節・地図と、
    独立設計の後の答え・前提のずれの申告の本文・記録の制約を貼り、貼った物を控える"""
    START = {"decision": "continue", "text": "入口は 1 つに絞る"}
    BEFORE_FIX = {"decision": "continue", "text": "古い入口は消してよい"}
    REQUEST = "`docs/d.md` の 2 節のとおりに直す"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name)
        git(self.repo, "init", "-q")
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "d.md").write_text("# 設計\n\n## 2 入口\n\n入口は 1 つ\n\n## 3 出口\n\n出口\n", encoding="utf-8")
        (self.repo / "AGENTS.md").write_text("# 地図\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")

    def section(self, **kw):
        args = {"human_items": eyeverdict.human_items(self.START, self.BEFORE_FIX), "request_text": self.REQUEST,
                "repo": self.repo, "changed": {"premise_drift": True, "premise_drift_note": "入口は 2 つあった"},
                "constraints": [{"kind": "measured", "text": "1 デプロイは 2 リポジトリ"}], "design_seen": {"count": 1}, **kw}
        return eyeverdict.premise_section(**args)

    def test_pastes_every_premise_in_the_original_order(self):
        text, _ = self.section()
        heads = [design.HUMAN_HEAD, design.NAMED_HEAD, design.MAP_HEAD, eyeverdict.LATE_HEAD, eyeverdict.DRIFT_HEAD,
                 eyeverdict.CONSTRAINT_HEAD]
        self.assertEqual(sorted(heads, key=text.index), heads)
        for want in ("入口は 1 つに絞る", "古い入口は消してよい", "入口は 1 つ\n", "AGENTS.md:1-1", eyeverdict.LATE_ASK,
                     "入口は 2 つあった", "1 デプロイは 2 リポジトリ"):
            self.assertIn(want, text)
        self.assertNotIn("出口\n", text.split("入口は 1 つ\n")[1])

    def test_human_answer_rows_are_design_human_answers_rows(self):
        """独立設計の控えと同じ行の形（design.human_answers）で貼り、比較役の控えもその行を持つ"""
        items = eyeverdict.human_items(self.START, self.BEFORE_FIX)
        _, rows, _, seen = design.human_answers(types.SimpleNamespace(record={"process": {"human_items": items}}))
        _, ledger = self.section()
        self.assertEqual([g["what"] for g in ledger["given"] if g["kind"] == "human_answer"], rows)
        self.assertEqual(seen["count"], 2)
        self.assertEqual([i["node"] for i in items], [eyeverdict.START_GATE_NODE, gatemarks.GATE_NODE])

    def test_ledger_lists_what_was_given_and_withheld(self):
        _, ledger = self.section()
        self.assertEqual(ledger["node"], "r2.compare")
        self.assertEqual([g["kind"] for g in ledger["given"]],
                         ["human_answer", "human_answer", "named_section", "repo_map", "drift", "constraint"])
        self.assertEqual(ledger["withheld"], [])
        self.assertEqual(ledger["seen"], {"count": 2, "last_round": 1})

    def test_only_answers_after_the_design_are_late(self):
        """独立設計の控えの seen.count は始めの関所の答えを数えた物なので、後の修正前の関所の答えだけが後に来た答え"""
        _, ledger = self.section()
        self.assertEqual(len(ledger["after_design"]), 1)
        self.assertIn("古い入口は消してよい", ledger["after_design"][0])
        text, ledger = self.section(human_items=eyeverdict.human_items(None, self.BEFORE_FIX), design_seen={"count": 0})
        self.assertIn("古い入口は消してよい", ledger["after_design"][0])
        text, ledger = self.section(design_seen={"count": 2})
        self.assertEqual(ledger["after_design"], [])
        self.assertNotIn(eyeverdict.LATE_HEAD, text)
        text, ledger = self.section(design_seen=None)
        self.assertNotIn("after_design", ledger)
        self.assertNotIn(eyeverdict.LATE_HEAD, text)

    def test_link_anchor_finds_the_heading_by_its_slug(self):
        _, ledger = self.section(request_text="[入口](docs/d.md#2-入口) のとおりに直す")
        self.assertIn({"kind": "named_section", "what": "docs/d.md#2-入口"}, ledger["given"])

    def test_heading_inside_a_code_fence_is_not_an_anchor(self):
        """名指された文書の見出しは囲い（``` と ~~~。情報文字列つきも）の外だけを読む: 囲いの中の # 行はアンカーにならず、節も切らない
        （元 review-loop.py:2822-2850 の _md_lines・_md_slugs。works/tests/test_blk_eyes.py:736）"""
        for fence in ("```", "```js title=x", "~~~"):
            with self.subTest(fence):
                (self.repo / "docs" / "f.md").write_text(
                    f"# 設計\n\n## 2 入口\n\n{fence}\n## 9 偽\n{fence[:3]}\n\nBODY-2-TAIL\n\n## 3 出口\n\nS3\n", encoding="utf-8")
                git(self.repo, "add", "-A")
                git(self.repo, "commit", "-q", "-m", fence)
                text, ledger = self.section(request_text="[偽](docs/f.md#9-偽) と [入口](docs/f.md#2-入口) のとおりに直す")
                self.assertIn({"kind": "named_section", "what": "docs/f.md#2-入口"}, ledger["given"])
                self.assertNotIn({"kind": "named_section", "what": "docs/f.md#9-偽"}, ledger["given"])
                self.assertIn("docs/f.md#9-偽", [w["what"] for w in ledger["withheld"]])
                self.assertIn("BODY-2-TAIL", text)
                self.assertNotIn("S3", text)

    def test_premise_kinds_fence_is_design_premises(self):
        with mock.patch.object(design, "PREMISE_KINDS", ("named_section", "repo_map")):
            with self.assertRaises(design.BoardGap):
                self.section()

    def test_says_what_was_not_passed(self):
        text, ledger = self.section(human_items=[], request_text=None, changed=None, constraints=None)
        self.assertNotIn(design.HUMAN_HEAD, text)
        self.assertIn(f"{design.NAMED_HEAD}\n\n- {eyeverdict.NO_REQUEST}", text)
        self.assertLess(text.index(eyeverdict.NO_REQUEST), text.index(design.MAP_HEAD))
        self.assertIn({"kind": "named_section", "what": "依頼", "why": eyeverdict.NO_REQUEST}, ledger["withheld"])
        self.assertIn("（修正の印が渡っていない）", text)
        self.assertIn(eyeverdict.NO_CONSTRAINTS, text)
        text, _ = self.section(changed={"premise_drift": False})
        self.assertIn(f"{eyeverdict.DRIFT_HEAD}\n\n（無い）", text)
        text, _ = self.section(changed={"premise_drift": True})
        self.assertIn("（申告の文なし）", text)

    def test_constraints_read_the_same_in_the_compare_head_and_the_premise_check(self):
        cons = [{"kind": "measured", "text": "1 デプロイは 2 リポジトリ"}, "素の行"]
        text, _ = self.section(constraints=cons)
        texts = eyeverdict.prompt_texts(units=None, fix_units=None, changed=None, constraints=cons, green_ok=True,
                                        ripple_file="", world_file="", passed={})
        self.assertIn(f"{eyeverdict.CONSTRAINT_HEAD}\n\n{texts['constraints_text']}", text)
        self.assertEqual(eyeverdict.prompt_texts(units=None, fix_units=None, changed=None, constraints=None, green_ok=True,
                                                 ripple_file="", world_file="", passed={})["constraints_text"],
                         eyeverdict.NO_CONSTRAINTS)


class WriteNotesCase(unittest.TestCase):
    """最後の関所に出す材料: R2 の 2 つの役に渡した前提の控え・比較役の『渡されていない』の文とその照らし・人が通した行"""

    def test_writes_premise_inputs_and_gate_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            eyes = pathlib.Path(tmp)
            ledger = {"node": "r2.compare", "given": [{"kind": "repo_map", "what": "AGENTS.md:1-3"}], "withheld": []}
            (eyes / eyeverdict.R2_PREMISES).write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
            (eyes / "r2.json").write_text(json.dumps({"status": "pass", "reason": "地図が渡されていない。構造は同じ",
                                                      "differences": [{"kind": "表現", "text": "名が違う"}]}, ensure_ascii=False),
                                          encoding="utf-8")
            (eyes / "r4.json").write_text(json.dumps({"capability_inventory": {"fired": True, "lost": [BODY]}}, ensure_ascii=False),
                                          encoding="utf-8")
            design_ledger = {"given": [], "withheld": [], "seen": {"count": 0}}
            eyeverdict.write_notes(eyes, design_ledger=design_ledger, passed=PASSED)
            notes = json.loads((eyes / eyeverdict.PREMISE_INPUTS).read_text(encoding="utf-8"))
            passes = json.loads((eyes / eyeverdict.GATE_PASSES).read_text(encoding="utf-8"))
        self.assertEqual(notes["design"], design_ledger)
        self.assertEqual(notes["claims"], ["地図が渡されていない"])
        self.assertEqual(notes["compare"]["claims_given"],
                         [{"claim": "地図が渡されていない", "kind": "repo_map", "what": "AGENTS.md:1-3"}])
        self.assertEqual([p["item"] for p in passes], ["R4 が BASE から消えたと見た能力: " + BODY])

    def test_missing_files_leave_empty_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            eyes = pathlib.Path(tmp)
            eyeverdict.write_notes(eyes, design_ledger=None, passed={})
            notes = json.loads((eyes / eyeverdict.PREMISE_INPUTS).read_text(encoding="utf-8"))
            self.assertEqual(notes, {"design": None, "compare": None, "claims": []})
            self.assertEqual(json.loads((eyes / eyeverdict.GATE_PASSES).read_text(encoding="utf-8")), [])


class StatusOwnerCase(unittest.TestCase):
    """目の状態の語の持ち主は seal だけ。目の判定（eyeverdict）・結末の分け（outcome）・関所の文の語（gatemarks）は語を写さず持ち主から読む"""

    def test_readers_do_not_restate_the_words(self):
        words = set(seal.STATUSES) - {seal.PASSED}
        for name in ("eyeverdict.py", "outcome.py", "gatemarks.py"):
            with self.subTest(name=name):
                tree = ast.parse((LIB / name).read_text(encoding="utf-8"))
                restated = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and n.value in words}
                self.assertEqual(restated, set())

    def test_apply_refusal_follows_the_owner(self):
        with mock.patch.object(seal, "REDESIGN", "renamed"):
            got = seal.apply_refusal(sealed_hash="h", current_hash="h", answer={"decision": "continue", "text": ""},
                                     green_ok=True, eyes_ok=True, r2={"status": "renamed", "reason": "r"},
                                     fingerprint_ok=True, protected=[])
        self.assertIn("R2 が作り直し", got)


if __name__ == "__main__":
    unittest.main()
