"""段 → 回す物の表・単位の深さ・修正の後の上げ直し（docs/design/line.md の 5 節。node tiers と raise。src/tiers.py）。

元は今の tests/workflows/test_line.py の RedepthCase と lib/tests/test_depth.py の表の照らし。表の行は今の lib/depth.py の TIERS と同じ
（組み込みの前に写しを照らす。lib の元が消えた後は見送る）。上げ直しの信号の全部（止めた単位・申し出・答えていない問い・案の直し・
修正役の異議・引用の外の差分・TDD の輪の拒否・範囲の相談・直さずに残した事前審査の block・読めない控え）と、checks・eyes_due
（前の run が運んだ実測が在る run は目を省かない）を見る。
"""
import json
import unittest

from tests.blocks import kit

BLOCK = "line"
tiers = kit.load(BLOCK, "tiers")
import headdepth  # noqa: E402  （KEEP の lib）

UNKNOWN_NONE = "無し"   # head-depth の行ごとの未知の種類「無し」（workflows/head-depth/src/steps.py の NONE。block の間は import しない）

U1 = "u1: 一つ目の根本"
LIGHT_ROWS = [{"unit_id": U1, "depth": "軽量", "why": "配線だけ"}]
ASKED_OP = "plan_scope_asked"   # lib/conflict.py の ASKED_OP（範囲の相談の行の op）


def patch(*names):
    return "".join(f"diff --git a/{n} b/{n}\n--- a/{n}\n+++ b/{n}\n@@ -1 +1 @@\n-x\n+y\n" for n in names)


class TableCase(unittest.TestCase):
    def test_words_come_from_headdepth(self):
        self.assertEqual((tiers.LIGHT, tiers.STANDARD), (headdepth.LIGHT, headdepth.STANDARD))
        self.assertEqual(tiers.HEADS, ("軽量", "標準", "重厚"))

    def test_light_omits_and_merges_only(self):
        self.assertTrue(tiers.omits("軽量") and not tiers.omits("標準") and not tiers.omits("重厚"))
        self.assertEqual(tiers.merges("軽量"), ("r3.coherence", "r4.hidden_scope"))
        self.assertEqual(tiers.tier_adds("重厚"), tuple(__import__("entry").FEATURE_DEFAULTS))

    def test_report_line_reads_the_table(self):
        """元 lib/headdepth.py の report_line（integration.md 4.5-6。表と一緒に line へ移した）"""
        self.assertTrue(tiers.report_line("軽量", "易しい").startswith("run の頭の深さ: 軽量（根拠: 易しい）／省く物（単位がどれも軽量の時）"))
        self.assertIn("足した物: judge_verify（名指しで切った）", tiers.report_line("重厚", "", cut=("judge_verify",)))
        self.assertTrue(tiers.report_line("知らない", "").startswith("run の頭の深さ: 標準"))


class SwitchesCase(unittest.TestCase):
    def test_tree_follows_the_named_word_or_the_tier(self):
        """事前審査の木: 名指し（on・off）ならその語、無ければ重厚は on・軽量は off・標準は auto（今の boardview.py:426-429 と同じ式）"""
        self.assertEqual([tiers.switches(t, "", None)["tree"] for t in ("重厚", "軽量", "標準")], ["on", "off", "auto"])
        self.assertEqual(tiers.switches("軽量", "on", None)["tree"], "on")
        self.assertEqual(tiers.switches("重厚", "off", None)["tree"], "off")
        self.assertEqual(tiers.switches("標準", "", {"features_off": ["review_tree"]})["tree"], "off", "記録の features を読む")

    def test_unknown_tier_reads_standard_with_a_line(self):
        got = tiers.switches("知らない", "", None)
        self.assertEqual((got["tier"], got["omits"], got["merge"]), ("標準", False, False))
        self.assertIn("知らない", got["lines"][0])

    def test_tiers_node(self):
        run = kit.Run(self, BLOCK)
        got = run.script("tiers", tier="軽量", tree_named="", record="null")
        self.assertEqual({k: got[k] for k in ("tier", "omits", "merge", "tree", "stop_reason")},
                         {"tier": "軽量", "omits": True, "merge": True, "tree": "off", "stop_reason": ""})
        self.assertTrue(run.script("tiers", tier="重厚", tree_named="", record="null")["adds"])
        broken = run.script("tiers", tier="軽量", tree_named="", record="{壊れた")
        self.assertEqual(broken["stop_reason"], "works:line-script")


class UnitTierCase(unittest.TestCase):
    """単位の深さ（fix-in。5.2）と skip_rerun"""

    def test_skip_rerun_only_when_the_tier_omits(self):
        items = [{"unit_keys": [U1], "allowed_paths": ["a.py"], "tests": [], "rewrite_tests": []}]
        doc = tiers.decide_doc(items, [U1], forced="", checked=True)
        self.assertEqual(doc["units"][U1]["depth"], "軽量")
        self.assertEqual(tiers.skip_rerun(doc, "軽量"), [U1])
        self.assertEqual(tiers.skip_rerun(doc, "標準"), [], "省く物を持たない段は走らせ直しを省かない")
        self.assertEqual(tiers.skip_rerun(tiers.decide_doc(items, [U1], forced="標準", checked=True), "軽量"), [])

    def test_rows_and_docs_go_back_and_forth(self):
        doc = tiers.docs_of(LIGHT_ROWS, forced="軽量")
        self.assertEqual(doc, {"units": {U1: {"depth": "軽量", "why": ["配線だけ"]}}, "forced": "軽量", "raised": []})
        self.assertEqual(tiers.rows_of(doc), LIGHT_ROWS)


class RaiseCase(unittest.TestCase):
    """node raise（5.3）: 信号で標準へ上げ、下げない。checks・skip_why・eyes_due・counted・lines（元 RedepthCase）"""

    def setUp(self):
        self.run = kit.Run(self, BLOCK)

    def put(self, rel, doc):
        path = self.run.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(doc if isinstance(doc, str) else json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": rel}

    def fix(self, **kw):
        diff = self.put("fix/diff.patch", patch("a.py"))
        return {"units": [{"unit_id": U1, "status": "fixed"}], "conflicts": None, "objection": "", "diff": diff, "plan_declared": [],
                "tdd_refused": {"refused": [], "unread": []}, "accept_trace": self.put("fix/accept-trace.json", []), **kw}

    def raised(self, *, fix=None, replan=False, tier="軽量", dealt=None, judgment=None, answer=None, tier_record=None, plan=None,
               rows=LIGHT_ROWS):
        return self.run.script("raise_depth", fix=json.dumps(fix or self.fix(), ensure_ascii=False), replan=json.dumps(replan),
                               units_tier=json.dumps(rows, ensure_ascii=False), switches=json.dumps({"tier": tier}, ensure_ascii=False),
                               judgment=json.dumps(judgment), tier_record=json.dumps(tier_record), answer=json.dumps(answer),
                               record="null", ports=json.dumps(dealt or {"forced": "", "carried_measured": False}),
                               plan=json.dumps(plan))

    def test_quiet_light_run_skips_and_says_why(self):
        got = self.raised()
        self.assertEqual((got["units"][0]["depth"], got["checks"], got["eyes_due"], got["stop_reason"]), ("軽量", False, False, ""))
        self.assertTrue(got["skip_why"].startswith("軽量で省いた"))
        self.assertTrue(any(line.startswith("軽量で省いた: ") for line in got["lines"]))

    def test_standard_or_heavy_head_runs_the_checks(self):
        """issue #561: 単位がどれも軽量でも、run の頭の深さが標準・重厚・不明なら回す"""
        for tier in ("標準", "重厚", "", "知らない"):
            with self.subTest(tier=tier):
                got = self.raised(tier=tier)
                self.assertEqual((got["units"][0]["depth"], got["checks"], got["skip_why"]), ("軽量", True, ""))

    def test_carried_measurement_keeps_the_eyes(self):
        """前の run の前提の検算が運んだ実測が在る run は、差分の審査を省いても目を省かない（今の eyes/prep.py:107-109）"""
        got = self.raised(dealt={"forced": "", "carried_measured": True})
        self.assertEqual((got["checks"], got["eyes_due"]), (False, True))

    def test_every_signal_raises_to_standard(self):
        conflicts = self.put("fix/conflicts.json", {"items": [{"kind": "test", "path": "t.py"}]})
        questions = [{"key": "q1", "kind": "fork", "status": "held", "origin": U1, "reason": "a か b か"}]
        judgment = self.put("judge/judgment.json", {"units": [], "questions": questions})
        record = self.put("judge/depth-head.json", headdepth.record("軽量", "易しい", items=[
            {"item": 1, "unknown": UNKNOWN_NONE, "where": "a.py:1", "cause_quote": "x", "code_quote": "y"}]))
        cases = {
            "止めた単位": ({"fix": self.fix(units=[{"unit_id": U1, "status": "given_up"}])}, "修正の段が止めた単位"),
            "申し出": ({"fix": self.fix(conflicts=conflicts)}, "申し出が在る（1 件）"),
            "答えていない問い": ({"judgment": judgment}, "答えていない問い q1"),
            "案の直し": ({"replan": True}, "案の直しが走る"),
            "修正役の異議": ({"fix": self.fix(objection="判定の単位が違う")}, "修正役の異議が在る"),
            "引用の外": ({"fix": self.fix(diff=self.put("fix/wide.patch", patch("a.py", "other.py"))), "tier_record": record},
                       "引用した where の外に出た"),
            "TDD の拒否": ({"fix": self.fix(tdd_refused={"refused": [U1], "unread": []})}, "TDD のループで修正役が拒まれた"),
            "範囲の相談": ({"fix": self.fix(accept_trace=self.put("fix/asked.json", [{"op": ASKED_OP, "item": 1, "unit_keys": [U1]}]))},
                      "修正役が範囲の相談をした"),
            "残した block": ({"fix": self.fix(plan_declared=["b1: 残す"])}, "直さずに残すと答えた事前審査の block が在る"),
            "読めない控え": ({"fix": self.fix(accept_trace=self.put("fix/broken.json", "{壊れた"))}, "修正の後の信号の控えが読めない"),
        }
        for name, (kw, why) in cases.items():
            with self.subTest(name):
                got = self.raised(**kw)
                self.assertEqual((got["units"][0]["depth"], got["checks"], got["skip_why"]), ("標準", True, ""))
                self.assertTrue(any(why in r for r in [*got["raised"], *(u["why"] for u in got["units"])]), (why, got["raised"]))

    def test_answered_question_does_not_raise(self):
        """修正前の承認ノードの答えが聞いた問いと、依頼の answers が答えた問いは数えない（L-D08）"""
        import gatemarks
        q = {"key": "q1", "kind": "fork", "status": "held", "origin": U1, "reason": "a か b か"}
        judgment = self.put("judge/judgment.json", {"units": [], "questions": [q]})
        answer = {"decision": "continue", "text": "", "asked": [gatemarks.ask_text(q)]}
        self.assertEqual(self.raised(judgment=judgment, answer=answer)["units"][0]["depth"], "軽量")
        dealt = {"forced": "", "request_answers": [{"question": "q1", "text": "a"}]}
        self.assertEqual(self.raised(judgment=judgment, dealt=dealt)["units"][0]["depth"], "軽量")
        broken = self.put("judge/broken.json", "{壊れた")
        self.assertIn("問いの台帳が読めない", self.raised(judgment=broken)["raised"][0])

    def test_missing_trace_is_noted_not_raised(self):
        got = self.raised(fix=self.fix(accept_trace=None))
        self.assertEqual(got["units"][0]["depth"], "軽量")
        self.assertIn(tiers.NO_LATE_RECORD.format(name=tiers.ACCEPT_TRACE), got["counted"])

    def test_width_is_counted_not_raised(self):
        """issue #760: run の広さは上げる信号にせず、counted に記録として残す"""
        wide = self.put("fix/wide.patch", patch(*(f"w{n}.py" for n in range(10))))
        plan = self.put("plan/plan-fields.json", {"round": 1, "fields": [{"unit_keys": [U1], "allowed_paths": ["a.py"], "out_of_scope": [], "tests": [], "rewrite_tests": []}]})
        got = self.raised(fix=self.fix(diff=wide), plan=plan)
        self.assertEqual(got["units"][0]["depth"], "軽量")
        self.assertTrue(got["counted"].startswith("触るファイル 11 個（起点: 修正の差分 fix/wide.patch）"), got["counted"])

    def test_broken_input_holds_with_the_stop_word(self):
        got = self.run.script("raise_depth", fix="{壊れた", replan="false", units_tier="[]", switches="{}", judgment="null",
                              tier_record="null", answer="null", record="null", ports="{}")
        self.assertEqual((got["stop_reason"], got["checks"], got["eyes_due"]), ("works:line-script", True, True))


if __name__ == "__main__":
    unittest.main()
