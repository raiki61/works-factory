"""report へ渡す sections と facts（workflows/line/src/sections.py・facts.py と scripts/collect.py。docs/design/line.md の 7 節）。

元は今の tests/workflows/test_line.py の CollectAndResultCase・FallbackCase・BrokenLibCase（docs/design/README.md の 9.5）。facts の欄は
docs/design/report.md の 1.2 の表の欄ごとに見る。組んだ形は report の block の schemas/facts.schema.json・sections.schema.json に照らす。

守る keep-essence: 8（人に回した申し出で人待ちに倒す。waits.conflicts）・10（守りのパスの当たりの数を tallied に入れる）・11（TDD の
単位ごとの節を fix の report から載せる）
"""
import json
import pathlib
import unittest
from unittest import mock

from tests.blocks import kit

BLOCK = "line"
ROOT = pathlib.Path(__file__).resolve().parents[3]
FACTS_SCHEMA = kit.BLOCKS / ".shared" / "schemas" / "facts.schema.json"
SECTIONS_SCHEMA = kit.BLOCKS / ".shared" / "schemas" / "sections.schema.json"
INPUTS = ("notices", "start", "answer_start", "test_gate_base", "judge", "tiers", "owed", "structure", "structure_in", "independent_design",
          "design_in", "rounds", "ask_before_fix", "answer_before_fix", "fix_in", "fix", "after_fix", "raise", "lens", "lens_in", "delta",
          "replan", "replan_review", "ask_replan", "answer_replan", "refix", "lens_2", "lens_2_in", "delta_2", "fixed", "parallel_after",
          "rejudge", "spec_check", "judged", "test_gate_final", "eyes_in", "eyes", "merge_seal", "ask_final", "answer_final", "merge_apply",
          "optional")


def ptr(path: str) -> dict:
    return {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": path}


def check(value, schema: pathlib.Path) -> list:
    import sys
    sys.path.insert(0, str(ROOT / "lib" / "graphloops"))
    from engine.schema import validate_schema
    return validate_schema(value, json.loads(schema.read_text(encoding="utf-8")))


def passing() -> dict:
    """どの段も通った run の collect の入力の値（受け皿の got と line の script の出力）"""
    tests = {"mode": "final", "ok": True, "green": True, "red_cause": "", "ran_steps": {"ran": ["t"], "unran": []}, "baseline": None,
             "fingerprint": None, "test_outcomes": None, "evidence": ptr("test-gate-final/evidence.txt"), "by": "test_cmd", "suites_line": "",
             "log": "", "baseline_line": "直す前のテスト: 緑", "reason": "", "suite": "", "suite_note": "",
             "related": {"applied": False, "whole": False, "files": [], "left": [], "far": [], "reasons": [], "ran": "none"},
             "report": ["- 最後のテスト: 緑"]}
    fix = {"ok": True, "reason": "", "units": [{"unit_id": "u1", "status": "fixed"}], "groups": [], "conflicts": None, "carry": None,
           "replan_items": [], "objection": "", "diff": ptr("fix/diff"), "start_tree": "t", "reply": None, "ruled_reply": None,
           "scope": None, "checked": {"ok": True, "reason": ""}, "allowed_test_changes": [], "changed": {}, "x_scalars": {}, "handoffs": [], "handoff_titles": {},
           "mismatched": [], "plan_declared": [], "stop_reason": "", "allowed_tests": None, "accept_trace": None, "closure": None,
           "tdd_unit": None, "tdd": [{"units": [{"unit_key": "u1", "test_cmd": "light"}]}], "frozen": None, "removed": [],
           "tdd_refused": {"refused": [], "unread": []}, "item_claims": None, "freeze_off": [], "removed_tests": [], "untested": [], "report": ["- u1: fixed"]}
    fix["closure"] = ptr("fix/closure.json")
    eyes = {"ok": True, **{f"r{n}": {"status": "pass", "reason": ""} for n in range(1, 5)}, "questions": [], "passes": [],
            "premise_check": None, "notes": [], "after": None, "dirty": 0, "escalate": 0, "after_ok": True, "report": ["- 目: 通した"],
            "sections": [{"title": "独立の目 R1 最小性とコメント", "lines": ["- R1 通した"]}, {"title": "直した後の構造の実測", "lines": ["- 実測"]}]}
    judge = {"ok": True, "stop_reason": "", "reason": "", "ready": True, "units": [{"id": "u1"}], "judgment": None, "answer_ties": None,
             "out_of_purpose": None, "materials": None, "brief": None, "inputs": None, "purpose": None, "purpose_text": "P",
             "purpose_source": "", "means": [], "purpose_review": None, "constraints": None, "world": None, "world_state": {"status": "ok", "reason": ""},
             "spec": None, "spec_rows": None, "spec_origin": "", "excluded": None, "pr_drafts": None, "downgrades": [], "decisions": None,
             "tier": "標準", "tier_why": "", "row_asks": [], "tier_record": None, "verify": None, "verify_why": "既定で切（features の既定）",
             "report": [], "sections": [{"title": "世界の解", "lines": ["- 世界"]}, {"title": "根本の診断", "lines": ["- 判定"]},
                                        {"title": "素材: 局所レビュー", "lines": ["- 局所"]}, {"title": "素材: コード衛生", "lines": ["- 衛生"]}],
             "optional": [{"node": "world", "bare": False}]}
    seal = {"mode": "seal", "ok": True, "hash": "h", "diff": ptr("merge-seal/diff"), "protected_hits": [], "protected_count": 0,
            "reason": "", "deliver": None, "report": ["- 封じた"]}
    fixed = {"go": True, "done": True, "held": False, "no_fix": False, "diffed": True, "checks": True, "eyes_due": True, "skip_why": "",
             "rejudge": False, "refixed": False, "stages": [{"stage": 1, "fix": fix, "lens": None, "delta": None}], "carry": [],
             "tdd": [fix["tdd"]], "units": fix["units"], "groups": [], "conflicts": [], "replan_items": [], "objection": "", "diff": fix["diff"],
             "item_claims": None, "allowed_test_changes": [], "changed": {}, "x_scalars": {}, "handoffs": [], "handoff_titles": {}, "mismatched": [],
             "plan_declared": [], "plan": None, "ripple": None, "left": [], "stop_reason": ""}
    return {name: None for name in INPUTS} | {
        "notices": "注意（test_cmd）: x",
        "start": {"ok": True, "stop_reason": "", "reason": "", "record": ptr("r1/start.json"), "prior_failures": None, "ask": False,
                  "gate_text": "", "unattended": False, "design_talk": False, "final_gate": "always", "from_fixture": False, "fixture": None,
                  "ports": {"run_id": kit.RUN_ID, "user_env_dir": ""}},
        "answer_start": {"go": True, "answer": None, "stop_reason": ""},
        "test_gate_base": {**tests, "mode": "base", "report": ["- 直す前: 緑"]},
        "judge": judge,
        "rounds": {"done": True, "ok": True, "status": "ok", "round": 1, "plan_prior": None, "record": None, "plan": ptr("plan/p.json"),
                   "fix_plan": None, "reply": None, "handoffs": [], "ripple": None, "owed": ["u1"], "gave_up": None, "stalled": False,
                   "capped": False, "review": None, "asks": [], "deviations": [], "review_status": "ok", "review_reason": "", "stop_reason": "", "pointed": []},
        "ask_before_fix": {"open": True, "go": True, "stop_reason": "", "text": "", "deferred": [], "asked": [], "pushed": None, "passes": [],
                           "policy_changed": False},
        "answer_before_fix": {"go": True, "answer": {"decision": "approve", "text": "よい"}, "stop_reason": "", "policy": ""},
        "fix_in": {"go": True, "no_fix": False, "received": None, "switches": {"tier": "標準", "lines": ["- 省く物は無い"]}},
        "fix": fix, "after_fix": {"replan": False, "prior": None, "stop_reason": ""},
        "raise": {"units": [{"unit_id": "u1", "depth": "軽量", "why": "単位が小さい"}], "checks": True, "skip_why": "", "eyes_due": True, "raised": [], "counted": "", "lines": ["深さ: 標準"],
                  "stop_reason": ""},
        "fixed": fixed, "judged": {"units": [], "lines": [], "carry": [], "stop_reason": ""}, "test_gate_final": tests, "eyes": eyes,
        "merge_seal": seal, "ask_final": {"open": True, "go": True, "stop_reason": "", "text": "", "reasons": []},
        "answer_final": {"go": True, "answer": {"decision": "approve", "text": "当てる"}, "stop_reason": ""},
        "optional": ["eyes__", "lens__", "lens-2__"],
    }


def seed(run) -> None:
    """修正の段の控え（閉鎖の表）を place に置く"""
    (run.artifacts / "fix").mkdir(exist_ok=True)
    (run.artifacts / "fix" / "closure.json").write_text(json.dumps({"rows": [{"unit_key": "u1", "closed": True}], "claimed": ["u1"]}))
    (run.artifacts / "fix" / "diff").write_text("")


def record() -> dict:
    return {"input": {"base": {"label": "差分なし（HEAD）"}}, "answers": [], "versions": {}}


class FactsCase(unittest.TestCase):
    def setUp(self):
        self.f = kit.load(BLOCK, "facts")
        self.s = kit.load(BLOCK, "sections")
        self.run = kit.Run(self, BLOCK)
        seed(self.run)

    def build(self, values, rec=None):
        with self.run.env(), mock.patch.object(__import__("report"), "CMD_LIGHT", "light", create=True):
            return self.f.build(values, rec if rec is not None else record())

    def test_passing_run(self):
        got = self.build(passing())
        self.assertEqual(check(got, FACTS_SCHEMA), [], "facts が report の形に合う")
        self.assertEqual((got["start_ok"], got["problems"], got["stops"], got["halts"], got["cut"], got["no_fix"], got["proved"]),
                         (True, [], [], [], None, False, True))
        self.assertEqual([g["at"] for g in got["gates"]], ["gate-start", "gate-before-fix", "gate-replan", "gate-final"])
        self.assertEqual([g["decision"] for g in got["gates"]], [None, "approve", None, "approve"])
        self.assertEqual(got["optional"], ["eyes__", "lens__", "lens-2__", "judge__world"])
        self.assertIn("judge", got["returned"])
        self.assertEqual(got["head"]["notices"], ["注意（test_cmd）: x"])
        self.assertEqual(got["left"], [])

    def test_unreadable_after_measure_is_a_left_row(self):
        """直した後の構造の実測を読めない時は、柵の増えが無いと数えずに残りの行にする（E23。最後の承認ノードの final.after_rows と同じ読み）"""
        v = passing()
        v["eyes"] = {**v["eyes"], "after": ptr("structure-after/after.json")}
        got = self.build(v)
        self.assertEqual([r["where"] for r in got["left"]], [self.f.AFTER_WHERE], got["left"])
        self.assertIn("柵の増えを数えていない", got["left"][0]["text"])

    def test_inner_node_ids_stay_out_of_the_head_lines_and_in_the_named_ones(self):
        """報告の頭の行には、人が読む言葉だけを出す（id・止めの語は出さない。tests/blocks/line/test_head_plain.py）。頭の外の節の行は
        「訳（id）」で名を残す（グラフの名で探せるように）"""
        stops = [{"at": "ask-final", "word": "works:needs-human"}]
        self.assertTrue(self.f.stop_words(stops)[0].startswith("最後の承認ノードを開ける所が止めた: "), self.f.stop_words(stops))
        self.assertTrue(self.f.stop_words_full(stops)[0].startswith("最後の承認ノードを開ける所（ask-final） が works:needs-human"))
        said = self.f.pushed_said({"gate-before-fix": {"pushed": [{"item": "x", "answer": "continue", "note": "n", "why": "w"}]}})
        self.assertIn("通した承認ノード: 修正前の承認ノード（推し", said)
        self.assertNotIn("gate-before-fix", said)
        lines = self.f.pushed_lines({"gate-before-fix": {"pushed": [{"item": "x", "answer": "continue", "note": "n", "why": "w"}]}})
        self.assertIn("承認ノード 修正前の承認ノード（gate-before-fix）", lines[0])

    def test_every_node_the_machine_names_has_a_plain_name(self):
        """止めの語を読む node と承認ノードの全部に、人が読む言葉の表の行が在る（行が無いと名だけが訳なしで出る）"""
        names = self.f.node_names()
        for node, _ in (*self.f.LINE_STOPS, *self.f.BLOCK_STOPS, *self.f.GATES):
            self.assertTrue(names.get(node), node)

    def test_line_and_block_stops(self):
        v = passing()
        v["owed"] = {"owed": False, "why": "", "recorded": [], "stop_reason": "works:line-script"}
        v["spec_check"] = {"ok": True, "status": "ok", "stop_reason": "", "reason": "", "spec": None, "added_rows": None, "added_origin": "",
                           "questions": ["受け入れ条件のテストが変わった"], "unchecked": False, "report": []}
        got = self.build(v)
        self.assertIn({"at": "owed", "word": "works:line-script"}, got["stops"])
        self.assertIn({"at": "spec-check-run", "word": "works:spec-changed"}, got["stops"], "承認し直すかの問いは人待ちの語")

    def test_script_fall_reason_reaches_the_problems(self):
        """script が落ちて返した reason（fix-in が壊れた start.json の名を運ぶ）は、止めの語と別に報告の problems に名指しで載る"""
        v = passing()
        v["fix_in"] = {**(v.get("fix_in") or {}), "stop_reason": "works:line-script", "reason": "json の入力のファイル r1/start.json が JSON として読めない"}
        got = self.build(v)
        self.assertTrue(any("fix-in" in p and "r1/start.json" in p for p in got["problems"]), got["problems"])
        v["fix_in"] = {**v["fix_in"], "stop_reason": "", "reason": ""}
        self.assertFalse(any("r1/start.json" in p for p in self.build(v)["problems"]))

    def test_halts(self):
        v = passing()
        v["merge_seal"] = {**v["merge_seal"], "ok": False}
        v["rounds"] = {**v["rounds"], "stalled": True}
        v["fixed"] = None
        got = self.build(v)
        self.assertIn({"at": "plan-review", "word": "works:plan-converge"}, got["halts"])
        self.assertIn({"at": "merge-seal", "word": "not-ok"}, got["halts"])
        self.assertFalse(got["proved"])

    def test_waits_conflict_asked(self):
        """keep-essence 8: 人に回した申し出で人待ち（waits.conflicts）"""
        (self.run.artifacts / "fix").mkdir(exist_ok=True)
        (self.run.artifacts / "fix" / "conflicts.json").write_text(json.dumps({"items": [
            {"id": "c1", "unit_key": "u1", "kind": "brief_vs_judgment", "ruling": {"decision": "ask_human", "text": "人に聞く"}}]}))
        v = passing()
        v["fixed"] = {**v["fixed"], "conflicts": [ptr("fix/conflicts.json")]}
        got = self.build(v)
        self.assertEqual(got["waits"]["conflicts"], [{"at": "fix", "word": "works:conflict"}])

    def test_eyes_rows_are_left(self):
        v = passing()
        v["eyes"] = {**v["eyes"], "r2": {"status": "needs-fix", "reason": "x"}, "questions": ["R4 の問い"]}
        got = self.build(v)
        self.assertEqual(got["left"][0]["where"], "独立の目 R2")
        self.assertIn({"at": "eyes", "word": "r4-ask"}, got["waits"]["others"])
        self.assertIn(self.f.EYE_ASK_HEAD, [a["kind"] for a in got["asks"]])

    def test_cut_when_the_final_test_is_missing(self):
        v = passing()
        v["test_gate_final"] = None
        got = self.build(v)
        self.assertEqual(got["cut"], {"at": "test-gate-final", "word": "chain-cut"})
        v["fixed"] = {**v["fixed"], "go": False}
        self.assertIsNone(self.build(v)["cut"], "fixed の go が偽（意図して飛ばした）は切れ目に数えない")

    def test_no_fix_round(self):
        v = passing()
        v["fixed"] = {**v["fixed"], "no_fix": True, "stages": [], "diffed": False}
        v["merge_seal"] = None
        got = self.build(v)
        self.assertEqual((got["no_fix"], got["cut"]), (True, None))

    def test_protected_hits_are_tallied(self):
        """keep-essence 10: 守りのパスの当たりの全件の数を tallied に入れる（4.5-18 (b)）"""
        v = passing()
        v["merge_seal"] = {**v["merge_seal"], "protected_hits": ["a", "b"], "protected_count": 7}
        got = self.build(v)
        self.assertEqual(got["tallied"], {"守りのパスに当たった差分": 7})

    def test_uncompared_reds_are_asked(self):
        """fix の #846: 確かめ直しで直す前の版と比べられなかったので組を戻さなかった赤（当てたままの組の行の uncompared）は、黙って
        通さず、人が決めることに 1 件 1 行で載せて聞く。戻した組の行の uncompared は聞かない（組を当てていない）"""
        v = passing()
        v["fixed"] = {**v["fixed"], "groups": [
            {"group_id": "g1", "unit_ids": ["u1"], "returned": True, "reason": "", "uncompared": ["test_a.TestA::test_env"]},
            {"group_id": "g2", "unit_ids": ["u2"], "returned": False, "reason": "赤", "uncompared": ["test_b.TestB::test_x"]}]}
        got = self.build(v)
        asked = [a["text"] for a in got["asks"] if a["kind"] == self.f.UNCOMPARED_HEAD]
        self.assertEqual(len(asked), 1, got["asks"])
        self.assertIn("test_a.TestA::test_env", asked[0])
        self.assertIn("g1", asked[0])
        self.assertIn("比べられなかった", self.f.UNCOMPARED_HEAD)
        self.assertIn(f"{self.f.UNCOMPARED_HEAD}: 1 件", got["decisions"]["before"])
        self.assertEqual(check(got, FACTS_SCHEMA), [])

    def test_record_unreadable_is_not_start_ok(self):
        got = self.build(passing(), rec={})
        self.assertFalse(got["start_ok"])
        why = self.f.build(passing(), None, "始めの記録が読めない")
        self.assertEqual((why["start_ok"], why["problems"][0]), (False, "始めの記録が読めない"))

    def test_cmd_light_is_counted(self):
        """integration.md 4.5-14: fixed の tdd の単位のうち test_cmd が軽量の語の物を数える（語は lib/report.py の CMD_LIGHT。lib の
        レーンが足すまで今の lib に無いので、create=True で差し替える）"""
        with mock.patch.object(__import__("report"), "CMD_LIGHT", "light", create=True):
            self.assertEqual(self.f.cmd_skipped([[{"units": [{"unit_key": "u1", "test_cmd": "light"}, {"unit_key": "u2", "test_cmd": "ok"}]}]]), 1)

    def test_policy_change_row(self):
        """integration.md 4.5-12: 始めの記録の固めた方針と今の方針の文書を比べた 1 行"""
        doc = self.run.repo / "policy.md"
        doc.write_text("前の方針\n", encoding="utf-8")
        policy = __import__("policy")
        frozen = policy.freeze(self.run.artifacts, self.run.repo, str(doc))
        doc.write_text("今の方針\n", encoding="utf-8")
        lines = self.f.policy_lines({"policy": frozen}, self.run.repo, self.run.artifacts)
        self.assertTrue(lines and lines[0].startswith(self.f.POLICY_CHANGED_HEAD), lines)
        doc.write_text("前の方針\n", encoding="utf-8")
        self.assertEqual(self.f.policy_lines({"policy": frozen}, self.run.repo, self.run.artifacts), [])


class MoreLinesCase(unittest.TestCase):
    """人が決めることの節の後ろの行（元 runreport の _conflict_line・unproven_lines・pr_lines・inner_word_lines・_gate_passes・
    _amend_lines・_line_lines。能力を残す）"""

    def setUp(self):
        self.f = kit.load(BLOCK, "facts")
        self.run = kit.Run(self, BLOCK)
        seed(self.run)

    def after(self, values):
        with self.run.env(), mock.patch.object(__import__("report"), "CMD_LIGHT", "light", create=True):
            return self.f.build(values, record(), cwd=self.run.repo)["decisions"]["after"]

    def test_lines_are_kept(self):
        v = passing()
        (self.run.artifacts / "judge").mkdir()
        (self.run.artifacts / "judge" / "pr-excluded.json").write_text(json.dumps(
            {"excluded": [{"pr": 7, "file": "a.py", "start": 1, "end": 3, "why": "重なる"}]}))
        v["judge"] = {**v["judge"], "excluded": ptr("judge/pr-excluded.json")}
        v["ask_before_fix"] = {**v["ask_before_fix"], "passes": [{"node": "p2.human_gate", "round": 1, "by": "decided", "item": "行 x",
                                                                         "decided_by": "https://example.org/std#3"}],
                               "deferred": [{"kind": "fork", "text": "載せなかった問い"}]}
        v["ask_final"] = {**v["ask_final"], "reasons": ["最後のテストが緑でない"]}
        after = self.after(v)
        joined = "\n".join(after)
        self.assertTrue(after[[i for i, x in enumerate(after) if x.startswith("食い違いの申し出: ")][0]].startswith("食い違いの申し出: 0 件"))
        self.assertIn("並行 PR #7 と重なるので外した範囲: a.py:1-3（重なる）", after)
        self.assertIn("修正前の承認ノードが聞かずに通した行（gate-before-fix）: 1 件", after)
        self.assertIn("（決め手: https://example.org/std#3）", joined)   # 定石で決めた行は出どころつきの 1 行で残る（settle-by-standard）
        self.assertIn(self.f.DEFERRED_HEAD + ": 1 件", after)
        self.assertIn("最後の承認ノードを開けた理由: 1 件", after)
        self.assertNotIn("組めない", joined)

    def test_final_reasons_head_follows_the_run_kind(self):
        """最後の承認ノードを開ける理由の見出しは、人が答える run では「無人の run」と言わない（無人の run だけが開かずに止める）"""
        for unattended, expected, absent in ((False, "最後の承認ノードを開けた理由: 1 件", "無人の run"),
                                             (True, "最後の承認ノードを開ける理由（無人の run では開かずに止めた理由）: 1 件", None)):
            v = passing()
            v["start"] = {**v["start"], "unattended": unattended}
            v["ask_final"] = {**v["ask_final"], "reasons": ["最後のテストが緑でない"]}
            after = self.after(v)
            self.assertIn(expected, after)
            if absent:
                self.assertFalse([x for x in after if x.startswith("最後の承認ノードを開け") and absent in x], after)

    def test_amend_lines_name_the_replanned_items(self):
        v = passing()
        v["fixed"] = {**v["fixed"], "replan_items": ["1"], "refixed": True}
        after = self.after(v)
        self.assertTrue(any(x.startswith("同じ run の中で直した修正案の項目: 1 件") for x in after), after)


class SectionsCase(unittest.TestCase):
    def setUp(self):
        self.s = kit.load(BLOCK, "sections")
        self.run = kit.Run(self, BLOCK)

    def build(self, values):
        with self.run.env(), mock.patch.object(__import__("report"), "CMD_LIGHT", "light", create=True):
            return self.s.build(values, record(), cwd=self.run.repo, folder=self.run.artifacts)

    def test_order_and_shape(self):
        got = self.build(passing())
        self.assertEqual(check(got, SECTIONS_SCHEMA), [])
        titles = [s["title"] for s in got]
        self.assertEqual(titles[:8], [self.s.ENTRY, self.s.TDD, self.s.GREEN, self.s.EYES, self.s.STRUCTURE, self.s.WORLD,
                                      self.s.LENS_LOCAL, self.s.JUDGMENT])
        self.assertIn("素材: コード衛生", titles)
        self.assertIn(self.s.ROUNDS, titles)
        self.assertIn(self.s.MERGE, titles)
        self.assertNotIn(self.s.TDD_2, titles, "走らなかった block の節は載せない")
        tdd = next(s for s in got if s["title"] == self.s.TDD)
        self.assertEqual(tdd["lines"], ["- u1: fixed"], "keep-essence 11: TDD の単位ごとの行は fix の report のまま")
        self.assertEqual(tdd["files"], [{"label": "差分", "ref": ptr("fix/diff"), "form": "file"}])
        entry = next(s for s in got if s["title"] == self.s.ENTRY)["lines"]
        self.assertIn("判定の裏取りを回さなかった: 既定で切（features の既定）", entry)
        self.assertIn("決めた人: 承認ノードの答え 2 件", entry)
        self.assertIn("直す前のテスト: 緑", entry)
        self.assertTrue(any(x.startswith("始めの記録: run ") for x in entry), entry)
        self.assertTrue(any(x.startswith("走った段: ") for x in entry), entry)
        self.assertFalse([x for x in entry if "組めない" in x], entry)
        self.assertNotIn("深さ: 標準", entry, "省いた数が在れば raise の lines を tiers.lines で組み直す")
        self.assertTrue(any("軽量の単位 1 個で省いた" in x for x in entry), entry)

    def test_not_run_section_names_what_was_left_to_ci_and_people(self):
        """持ち主の決め related-tests-only: 関わる試験に絞った run は、走らせた試験・走らせなかった試験・全体の試験を CI と人に任せた事を
        1 つの節に並べる。絞らない道は走らせ方の行（suites_line）を並べる。走らせた物の無い run は節を置かない"""
        self.assertNotIn(self.s.NOT_RUN, [s["title"] for s in self.build(passing())])
        v = passing()
        v["test_gate_final"] = {**v["test_gate_final"], "suites_line": "走らせた: suite／走らせなかった: 無い"}
        v["test_gate_base"] = {**v["test_gate_base"], "related": {"applied": True, "whole": False, "files": ["tests/test_a.py"],
                                                                 "left": ["tests/test_b.py"], "far": [], "reasons": [], "ran": "related"}}
        got = self.build(v)
        titles = [s["title"] for s in got]
        self.assertEqual(titles[titles.index(self.s.GREEN) + 1], self.s.NOT_RUN)
        lines = next(s for s in got if s["title"] == self.s.NOT_RUN)["lines"]
        text = "\n".join(lines)
        self.assertIn("直す前のテスト:", text)
        self.assertIn("  - tests/test_b.py", lines)
        self.assertIn("CI と人", text)
        self.assertIn("最後のテスト: 走らせた: suite／走らせなかった: 無い", text)

    def test_review_not_due_names_the_reason(self):
        v = passing()
        v["raise"] = {**v["raise"], "skip_why": "頭が軽量で全部の単位が軽量"}
        got = self.build(v)
        review = next(s for s in got if s["title"] == self.s.REVIEW_1)
        self.assertEqual(review["lines"], ["差分の審査を回さないのでレンズは起こさない（頭が軽量で全部の単位が軽量）"])


class CollectScriptCase(unittest.TestCase):
    def args(self, values) -> dict:
        return {name: "null" if values.get(name) is None else json.dumps(values[name], ensure_ascii=False) for name in INPUTS}

    def test_writes_both_files_and_returns_pointers(self):
        run = kit.Run(self, BLOCK)
        seed(run)
        (run.artifacts / "r1").mkdir()
        (run.artifacts / "r1" / "start.json").write_text(json.dumps(record()), encoding="utf-8")
        v = passing()
        got = run.script("collect", **self.args(v))
        self.assertEqual(set(got), {"sections", "facts"})
        facts = json.loads((run.artifacts / got["facts"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(check(facts, FACTS_SCHEMA), [])
        self.assertTrue(facts["start_ok"])
        self.assertEqual(got["facts"]["path"], "report-in/facts.json")

    def test_the_not_run_section_reaches_the_report_through_collect(self):
        """試験の関門の返りの related は、collect の受け皿の欄を通って報告の節「走らせなかった範囲」に届く（欄の一覧から外れると、絞った run
        でも走らせ方の行に落ち、「工場は絞らない」と誤って出る）"""
        run = kit.Run(self, BLOCK)
        seed(run)
        (run.artifacts / "r1").mkdir()
        (run.artifacts / "r1" / "start.json").write_text(json.dumps(record()), encoding="utf-8")
        v = passing()
        rel = {"applied": True, "whole": False, "files": ["tests/test_a.py"], "left": ["tests/test_b.py"], "far": [], "reasons": [], "ran": "related"}
        v["test_gate_base"] = {**v["test_gate_base"], "related": rel, "suites_line": "走らせた: x"}
        v["test_gate_final"] = {**v["test_gate_final"], "related": rel, "suites_line": "走らせた: x"}
        got = run.script("collect", **self.args(v))
        sections = json.loads((run.artifacts / got["sections"]["path"]).read_text(encoding="utf-8"))
        lines = next(s for s in sections if s["title"].startswith("走らせなかった範囲"))["lines"]
        text = "\n".join(lines)
        self.assertIn("  - tests/test_b.py", lines)
        self.assertNotIn("工場は絞らない", text)

    def test_prior_version_return_is_not_read_as_empty(self):
        """前の版の返り（受け皿の got の欄の欠け）を resume で受けたら空と読まず、訳だけの facts で record_invalid に倒す（4.3-12）"""
        run = kit.Run(self, BLOCK)
        v = passing()
        v["judge"] = {k: x for k, x in v["judge"].items() if k != "tier_record"}
        got = run.script("collect", **self.args(v))
        facts = json.loads((run.artifacts / got["facts"]["path"]).read_text(encoding="utf-8"))
        self.assertIn("collect が報告の材料を組めなかった", facts["problems"][0])
        self.assertEqual(facts["stops"], [{"at": "collect", "word": "works:line-script"}])

    def test_all_null_still_writes(self):
        """落ちない: どの入力も null（全部の段が飛んだ）でも 2 つのファイルを書く"""
        run = kit.Run(self, BLOCK)
        got = run.script("collect", **{name: "null" for name in INPUTS})
        facts = json.loads((run.artifacts / got["facts"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual((facts["start_ok"], check(facts, FACTS_SCHEMA)), (False, []))

    def test_line_script_word_matches_lib(self):
        import sys
        sys.path.insert(0, str(ROOT / "lib"))
        import stopby
        self.assertEqual(kit.load(BLOCK, "guard").LINE_SCRIPT, stopby.LINE_SCRIPT)


if __name__ == "__main__":
    unittest.main()


class SpecRunCase(unittest.TestCase):
    """仕様駆動の run の collect（docs/design/spec-driven.md の 6.2 の変える node の 7）: 判定の graph と計画の往復は回らないので、
    spec-rounds の判定の部と往復の部、spec- の付いた承認ノードの答えを今の欄の名で読み（src/specrounds.collect_values）、入口と形 check の
    報告の行を「仕様駆動の道」の節に載せ、止めの語は spec の node の名で数える"""

    def setUp(self):
        self.f = kit.load(BLOCK, "facts")
        self.s = kit.load(BLOCK, "sections")
        self.r = kit.load(BLOCK, "specrounds")
        self.run = kit.Run(self, BLOCK)
        seed(self.run)

    def spec_values(self, **over) -> dict:
        v = passing()
        judge = {k: v["judge"][k] for k in ("ok", "stop_reason", "ready", "units", "judgment", "answer_ties", "out_of_purpose", "materials",
                                            "brief", "inputs", "purpose", "purpose_text", "means", "constraints", "world", "spec", "excluded",
                                            "decisions", "tier", "tier_record", "verify")}
        report = ["- 仕様駆動の道の入口: 表 t.yaml と設計書 d.md を確かめた"]
        v.update({"judge": None, "rounds": None, "ask_before_fix": None, "answer_before_fix": None,
                  "spec_entry": {"ok": True, "stop_reason": "", "report": report},
                  "spec_diagnose": {"downgrades": [], "report": ["- 判定の役: 単位 1"]},
                  "spec_driven_check": {"ok": True, "stop_reason": "", "report": ["- 仕様とリポジトリの食い違いの照らし: 当たり無し"]},
                  "spec_rounds": {"judge": {**judge, "questions": []}, "rounds": passing()["rounds"], "stop_reason": "", "reason": ""},
                  "spec_ask_before_fix": passing()["ask_before_fix"], "spec_answer_before_fix": passing()["answer_before_fix"]})
        v.update(over)
        return self.r.collect_values(v)

    def rec(self) -> dict:
        return {**record(), "spec_table": "/x/t.yaml"}

    def test_spec_values_fill_the_current_fields(self):
        v = self.spec_values()
        self.assertEqual((v["rounds"]["status"], v["judge"]["tier"], v["answer_before_fix"]["answer"]["decision"]), ("ok", "標準", "approve"))
        with self.run.env(), mock.patch.object(__import__("report"), "CMD_LIGHT", "light", create=True):
            got = self.f.build(v, self.rec())
            secs = self.s.build(v, self.rec(), cwd=self.run.repo, folder=self.run.artifacts)
        self.assertEqual((got["stops"], got["cut"], got["no_fix"], got["proved"]), ([], None, False, True))
        spec = next(s for s in secs if s["title"] == "仕様駆動の道")
        self.assertEqual(spec["lines"][:2], ["- 仕様駆動の道の入口: 表 t.yaml と設計書 d.md を確かめた",
                                             "- 仕様とリポジトリの食い違いの照らし: 当たり無し"])
        self.assertIn("- 判定の役: 単位 1", next(s for s in secs if s["title"] == self.s.JUDGMENT)["lines"])

    def test_entry_stop_is_named_without_a_chain_cut(self):
        """入口の確かめで止まった run: 止めの語は spec-entry の名で数え、判定の graph が回らないことを続きの切れ目にしない"""
        v = passing()
        v.update({k: None for k in ("judge", "rounds", "ask_before_fix", "answer_before_fix", "fix_in", "fix", "after_fix", "raise", "fixed",
                                    "judged", "test_gate_final", "eyes", "merge_seal", "ask_final", "answer_final", "test_gate_base")})
        v.update({"spec_entry": {"ok": False, "stop_reason": "works:spec-entry", "report": ["- 止めた（works:spec-entry）: 表が無い"]},
                  "spec_diagnose": None, "spec_driven_check": None, "spec_rounds": None, "spec_ask_before_fix": None,
                  "spec_answer_before_fix": None})
        v = self.r.collect_values(v)
        with self.run.env(), mock.patch.object(__import__("report"), "CMD_LIGHT", "light", create=True):
            got = self.f.build(v, self.rec())
        self.assertIn({"at": "spec-entry", "word": "works:spec-entry"}, got["stops"])
        self.assertIsNone(got["cut"])
        names = self.f.node_names()
        for node in ("spec-entry", "spec-check", "spec-rounds"):
            self.assertTrue(names.get(node), node)

    def test_request_run_values_are_left_as_they_are(self):
        v = passing()
        v.update(dict.fromkeys(("spec_entry", "spec_diagnose", "spec_driven_check", "spec_rounds", "spec_ask_before_fix",
                                "spec_answer_before_fix")))
        self.assertEqual(self.r.collect_values(v), v)


class BaseSelfCheckLineCase(unittest.TestCase):
    """持ち主の決め base-runs-nothing: 節「走らせなかった範囲」の直す前の行は、直す前の走らせ方の行だけ。利用者の走らせ方を絞らない
    という添え書き（最後のテストの道 (1)(2) の物）は付けない"""

    def test_the_base_line_is_the_self_check_way_only(self):
        s = kit.load(BLOCK, "sections")
        way = "直す前の版では試験を走らせない（全部の試験も自己点検も置かない）"
        base = {"mode": "base", "suites_line": way, "related": {"applied": False}}
        self.assertEqual(s.not_run_lines(base, None), [f"直す前のテスト: {way}"])
