"""report へ渡す sections と facts（workflows/line/src/sections.py・facts.py と scripts/collect.py。docs/design/line.md の 7 節）。

元は test_line.py の CollectAndResultCase・FallbackCase・BrokenLibCase（docs/design/README.md の 9.5）。facts の欄は
docs/design/report.md の 1.2 の表の欄ごとに見る。組んだ形は report の block の schemas/facts.schema.json・sections.schema.json に照らす。

守る keep-essence: 8（人に回した申し出で人待ちに倒す。waits.conflicts）・10（守りのパスの当たりの数を tallied に入れる）・11（TDD の
単位ごとの節を fix の report から載せる）
"""
import inspect
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
          "rejudge", "spec_check", "judged", "test_gate_final", "eyes_in", "eyes", "eyes_back", "back_1", "merge_seal", "ask_final", "answer_final", "merge_apply",
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
    eyes = {"ok": True, **{f"r{n}": {"status": "pass", "reason": ""} for n in range(1, 5)}, "questions": [], "means_questions": [], "passes": [],
            "premise_check": None, "notes": [], "after": None, "dirty": 0, "escalate": 0, "after_ok": True, "findings": [], "route": "stay",
            "route_why": "返す物が無い（どの目も通った）", "report": ["- 目: 通した"],
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
             "rejudge": False, "refixed": False, "stages": [{"stage": 1, "kind": "first", "fix": fix, "lens": None, "delta": None}], "carry": [],
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
        self.assertEqual(got["head"]["notices"], [{"kind": "test_cmd_note", "slots": {}, "text": "注意（test_cmd）: x"}],
                         "試験のコマンドの注意の種の行 1 つ。本文は行の全文")
        self.assertEqual(got["left"], [])

    def with_request(self, doc=None, *, path="start/request.json", raw=None, other=None):
        """始めの節の ports.request に依頼の写し（doc を書いた path）の pointer を置いた collect の入力。other は request-in の返りの写し"""
        v = passing()
        if doc is not None or raw is not None:
            target = self.run.artifacts / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(raw if raw is not None else json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        v["start"] = {**v["start"], "ports": {**v["start"]["ports"], "request": ptr(path)}}
        if other is not None:
            (self.run.artifacts / "descend").mkdir(exist_ok=True)
            (self.run.artifacts / "descend" / "request.json").write_text(json.dumps(other, ensure_ascii=False), encoding="utf-8")
            v["request_in"] = {"request": ptr("descend/request.json")}
        return v

    def test_unreadable_request_copy_is_named_in_the_notes(self):
        draft = {"findings": [{"where": "a.py:1", "text": "下書き", "draft": True, "source": "前の run"}]}
        for name, v in (("missing", self.with_request(path="start/missing.json")), ("draft", self.with_request(draft))):
            with self.subTest(name):
                got = self.build(v)
                self.assertEqual(got.get("request_texts"), [], "読めない時は空の配列")
                self.assertTrue([n for n in got["notes"] if "依頼の字を組めない" in n], got["notes"])

    def test_unreadable_after_measure_is_a_left_row(self):
        """直した後の構造の実測を読めない時は、柵の増えが無いと数えずに残りの行にする（E23。最後の承認ノードの final.after_rows と同じ読み）"""
        v = passing()
        v["eyes"] = {**v["eyes"], "after": ptr("structure-after/after.json")}
        got = self.build(v)
        self.assertEqual([r["where"] for r in got["left"]], [self.f.AFTER_WHERE], got["left"])
        self.assertIn("柵の増えを数えていない", got["left"][0]["text"])

    def test_unreadable_answer_ties_is_named_in_the_notes(self):
        """問いの台帳の答えの結びを読めない時は、結びが無いと黙って数えずに訳を notes に名指す（E23。final.ledger_rows と同じ読み）"""
        v = passing()
        v["judge"] = {**v["judge"], "answer_ties": ptr("judge/ties.json")}
        got = self.build(v)
        self.assertTrue([n for n in got["notes"] if "judge/ties.json" in n], got["notes"])

    def test_stop_rows_name_a_returned_stage_apart_from_the_refix(self):
        """修正の段の止めの語の at は段の種類で引く: 独立の目から返した段は back-<k>-fix（k は返した段の中の何回目か）、案の直しの後の段は
        refix-run のまま。報告の頭の止めの行は、返した段を人の言葉の名で出す"""
        def stage(n, kind, word=""):
            return {"stage": n, "kind": kind, "fix": {"stop_reason": word}, "lens": None, "delta": None}
        v = passing()
        word = "works:no-suite"
        refix = self.f.stop_rows(v, {"fix": {"stages": [stage(1, "first"), stage(2, "refix", word)]}})
        self.assertIn({"at": "refix-run", "word": word}, refix)
        returned = self.f.stop_rows(v, {"fix": {"stages": [stage(1, "first"), stage(2, "returned", word)]}})
        self.assertIn({"at": "back-1-fix", "word": word}, returned, "案の直しが走らない run の返した段は並びの 2 番目でも返した段")
        self.assertNotIn({"at": "refix-run", "word": word}, returned)
        second = self.f.stop_rows(v, {"fix": {"stages": [stage(1, "first"), stage(2, "refix"), stage(3, "returned"), stage(4, "returned", word)]}})
        self.assertIn({"at": "back-2-fix", "word": word}, second)
        self.assertTrue(self.f.stop_words([{"at": "back-1-fix", "word": word}])[0].startswith("独立の目から返した修正の段が止めた"),
                        self.f.stop_words([{"at": "back-1-fix", "word": word}]))

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

    def test_r2_fix_needed_row_goes_to_findings_like_r1(self):
        """R2 が fix-needed（作り残し）で終わった run の R2 の行は、R1 の fix-needed の行と同じく次の依頼の findings に入り、prior_failures に
        運ばれない。R2 が redesign-needed の行は今どおり findings から外し、where『独立の目 R2』の行として prior_failures に運ぶ"""
        carry = __import__("carry")
        for eye in ("r1", "r2"):
            with self.subTest(eye=eye):
                v = passing()
                v["eyes"] = {**v["eyes"], eye: {"status": "fix-needed", "reason": "入口が 2 つ残る"}}
                carried = self.build(v)["carry"]
                self.assertEqual([r["text"] for r in carried["findings"]], [f"{eye.upper()} が fix-needed: 入口が 2 つ残る"])
                self.assertEqual(carried["prior"], [])
        v = passing()
        v["eyes"] = {**v["eyes"], "r2": {"status": "redesign-needed", "reason": "入口が 2 つ残る"}}
        carried = self.build(v)["carry"]
        self.assertEqual([(r["where"], r["text"]) for r in carried["prior"]], [(carry.REDESIGN_WHERE, "R2 が redesign-needed: 入口が 2 つ残る")])
        self.assertEqual(carried["findings"], [])

    MEANS_Q = "R2: 差分は頼みの解き方 M1「x」どおりだが、独立設計と食い違う——y"

    def test_means_questions_wait_only_while_unanswered(self):
        """計画 means-answers の 6.3 の 3 の 2・3: R2 の行は R4 の見出しの下に入れない。最後の承認ノードが continue か stop で答えた
        run では人待ちに数えず人が決めることにも載せない。答えの無い run と、R2 が redesign-needed の run（差分が当たらないので continue
        を答えに数えない）では語 r2-means-ask で数え、別の見出しの下に載せる"""
        v = passing()
        v["eyes"] = {**v["eyes"], "means_questions": [self.MEANS_Q]}
        for decision in ("approve", "continue", "stop"):
            with self.subTest(decision=decision):
                v["answer_final"] = {"go": decision != "stop", "answer": {"decision": decision, "text": "x"}, "stop_reason": ""}
                got = self.build(v)
                self.assertNotIn({"at": "eyes", "word": "r2-means-ask"}, got["waits"]["others"])
                self.assertNotIn(self.f.MEANS_ASK_HEAD, [a["kind"] for a in got["asks"]])
        for case, over in (("no-answer", {"answer_final": {"go": False, "answer": None, "stop_reason": "works:needs-human"}}),
                           ("redesign", {"eyes": {**v["eyes"], "r2": {"status": "redesign-needed", "reason": "別"}}})):
            with self.subTest(case=case):
                got = self.build({**v, "answer_final": {"go": True, "answer": {"decision": "continue", "text": "x"}, "stop_reason": ""},
                                  **over})
                self.assertIn({"at": "eyes", "word": "r2-means-ask"}, got["waits"]["others"])
                self.assertNotIn({"at": "eyes", "word": "r4-ask"}, got["waits"]["others"])
                kinds = {a["kind"]: a["text"] for a in got["asks"]}
                self.assertIn(self.MEANS_Q, kinds[self.f.MEANS_ASK_HEAD])
                self.assertNotIn(self.f.EYE_ASK_HEAD, kinds)

    def test_row_shaped_eye_questions_keep_the_wait_the_ask_and_the_draft(self):
        """eyes の questions と means_questions が {text, title} の行で届いても、人待ちの印（範囲を見る目の r4-ask と頼みどおりの違いの待ち）が立ち、
        範囲の問いと頼みどおりの違いの問いの種の行が人が決めることに並び（題は行の title）、次の依頼の下書きにその本文が載る。本文が空の行は数えない"""
        v = passing()
        v["answer_final"] = {"go": False, "answer": None, "stop_reason": "works:needs-human"}
        v["eyes"] = {**v["eyes"], "questions": [{"text": "守りを触ってよいか", "title": "守りを触ってよいか決める"}, {"text": " ", "title": "本文が無い"}],
                     "means_questions": [{"text": self.MEANS_Q, "title": "頼みどおりにするか決める"}]}
        got = self.build(v)
        self.assertEqual(check(got, FACTS_SCHEMA), [])
        self.assertIn({"at": "eyes", "word": "r4-ask"}, got["waits"]["others"])
        self.assertIn({"at": "eyes", "word": "r2-means-ask"}, got["waits"]["others"])
        rows = {a["kind"]: a for a in got["asks"]}
        self.assertEqual((rows[self.f.EYE_ASK_HEAD]["text"].split("——")[0], rows[self.f.EYE_ASK_HEAD]["title"]), ("守りを触ってよいか", "守りを触ってよいか決める"))
        self.assertEqual((rows[self.f.MEANS_ASK_HEAD]["text"].startswith(self.MEANS_Q), rows[self.f.MEANS_ASK_HEAD]["title"]), (True, "頼みどおりにするか決める"))
        self.assertEqual([a["kind"] for a in got["asks"]].count(self.f.EYE_ASK_HEAD), 1, "本文が空の行は載せない")
        with self.run.env():
            drafts = self.f.answer_drafts(v, self.f.returns_of(v, record()), self.f.gates_of(v), True)
        self.assertEqual(sorted(d["question"] for d in drafts), sorted(["守りを触ってよいか", self.MEANS_Q]))

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
        self.assertEqual(got["tallied"], {self.f.PROTECTED_HITS_HEAD: 7})
        self.assertEqual(self.f.PROTECTED_HITS_HEAD, "守ると決めたファイルに当たった差分", "頭に出る種の名は語の表の語を使わない言い方")

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


class CollectTest(unittest.TestCase):
    """周の鎖の 2 周目からの run は、前の周の報告から機械が組んだ次の依頼の容器を、人が見直さないまま依頼のファイルとして受ける"""

    setUp = FactsCase.setUp
    build = FactsCase.build
    with_request = FactsCase.with_request

    def test_request_texts_come_from_a_chain_next_request(self):
        chain_request = {
            "findings": [{"where": "a.py:1", "text": "前の周が残した 1 行目"}, {"where": "b.py:2", "text": "前の周が残した 2 行目"}],
            "prior_failures": [{"where": "c.py:3", "text": "前の周の失敗"}],
            "constraints": [{"text": "前の周の制約", "measured_how": "前の周の実測", "kind": "実測"}],
            "pr": [12],
        }
        got = self.build(self.with_request(chain_request))
        self.assertEqual(got.get("request_texts"), ["前の周が残した 1 行目", "前の周が残した 2 行目"], "容器の findings の text を依頼の順のまま")
        self.assertEqual(check(got, FACTS_SCHEMA), [], "facts が report の形に合う")


class SectionsCase(unittest.TestCase):
    def setUp(self):
        self.s = kit.load(BLOCK, "sections")
        self.run = kit.Run(self, BLOCK)

    def build(self, values):
        with self.run.env(), mock.patch.object(__import__("report"), "CMD_LIGHT", "light", create=True):
            return self.s.build(values, record(), cwd=self.run.repo, folder=self.run.artifacts)

    def test_returned_rounds_are_a_section(self):
        """報告の sections に、承認ノードと同じ見出しと行で、返した周の節が入る。返した周が 0 なら節は無い"""
        eb = kit.load(BLOCK, "eyesback")
        items = [{"eye": "r1", "where": "src/a.py:12", "text": "写しが残っている"}]
        rows = [{"round": 1, "r1": "fix-needed", "r2": "pass", "items": items}]
        got = self.build({**passing(), "eyes_back": {"rows": rows, "exit": "返す物が無い（どの目も通った）", "left": []}})
        self.assertEqual(check(got, SECTIONS_SCHEMA), [])
        section = next(s for s in got if s["title"] == self.s.BACK)
        self.assertEqual(self.s.BACK, eb.HEAD)
        self.assertEqual(section["lines"], eb.lines(rows, "返す物が無い（どの目も通った）"))
        titles = [s["title"] for s in got]
        self.assertLess(titles.index(self.s.EYES), titles.index(self.s.BACK))
        for record in (None, {"rows": [], "exit": "返す物が無い", "left": []}):
            self.assertNotIn(self.s.BACK, [s["title"] for s in self.build({**passing(), "eyes_back": record})])

    def test_back_lines_read_a_missing_restore_outcome_as_no_record(self):
        """返した周の節の行 back_lines は、封じた周の checkpoint を持つ記録と戻しの結末を lines に渡す。戻しの結末が null（戻す節が飛んだ）なら
        結末の記録が無いと言い、変えていなかったとは言わない。空の dict（戻す節が走って何も変えなかった）とは行が違う"""
        params = inspect.signature(self.s.back_lines).parameters
        self.assertIn("back_restore", params, f"back_lines の引数 {sorted(params)} に back_restore が無い")
        items = [{"eye": "r1", "where": "src/a.py:12", "text": "写しが残っている"}]
        eb = kit.load(BLOCK, "eyesback")
        rows = [{"round": 1, "r1": "fix-needed", "r2": "pass", "items": items}]
        record = {"rows": rows, "exit": eb.EXITS["stop"], "left": items, "checkpoint": {"round": 1, "tree": "t1"}}
        missing = self.s.back_lines(record, None)
        self.assertTrue(any("戻しの結末の記録が無い" in line for line in missing), missing)
        self.assertFalse(any("変えていなかった" in line for line in missing), missing)
        ran = self.s.back_lines(record, {})
        self.assertTrue(any("変えていなかった" in line for line in ran), ran)
        self.assertNotEqual(missing, ran)

    def test_broken_loop_is_named_when_a_round_head_ran(self):
        """周の節が中の誤りで落ちると集め eyes-back が飛ぶ（eyes_back が null）。周の頭 back-1 が走っていれば、返した周の節に「返す輪が途中で
        落ちた（下の状態は返す前の物）」の 1 行を出す。周の頭も走らなかった run は今どおり節を出さない"""
        eb = kit.load(BLOCK, "eyesback")
        got = self.build({**passing(), "eyes_back": None, "back_1": {"go": True, "round": 1}})
        section = next(s for s in got if s["title"] == self.s.BACK)
        self.assertEqual(section["lines"], [eb.BROKE])
        self.assertNotIn(self.s.BACK, [s["title"] for s in self.build({**passing(), "eyes_back": None, "back_1": None})])

    def test_tdd_rows_are_the_fix_report(self):
        """keep-essence 11: TDD の単位ごとの行と差分の控えは fix の report のまま節に載る"""
        got = self.build(passing())
        self.assertEqual(check(got, SECTIONS_SCHEMA), [])
        self.assertNotIn(self.s.TDD_2, [s["title"] for s in got], "走らなかった block の節は載せない")
        tdd = next(s for s in got if s["title"] == self.s.TDD)
        self.assertEqual(tdd["lines"], ["- u1: fixed"])
        self.assertEqual(tdd["files"], [{"label": "差分", "ref": ptr("fix/diff"), "form": "file"}])

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


class CollectScriptCase(unittest.TestCase):
    def args(self, values) -> dict:
        return {name: "null" if values.get(name) is None else json.dumps(values[name], ensure_ascii=False) for name in INPUTS}

    def seeded_run(self) -> "kit.Run":
        run = kit.Run(self, BLOCK)
        seed(run)
        (run.artifacts / "r1").mkdir()
        (run.artifacts / "r1" / "start.json").write_text(json.dumps(record()), encoding="utf-8")
        return run

    def test_writes_both_files_and_returns_pointers(self):
        run = self.seeded_run()
        v = passing()
        got = run.script("collect", **self.args(v))
        self.assertEqual(set(got), {"sections", "facts", "digest"})
        facts = json.loads((run.artifacts / got["facts"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(check(facts, FACTS_SCHEMA), [])
        self.assertTrue(facts["start_ok"])
        self.assertEqual(got["facts"]["path"], "report-in/facts.json")

    def test_same_inputs_give_the_same_return(self):
        """同じ入力で hash の種の違う子のプロセスを 2 本回すと、返りは digest まで等しい（書き手だけが落ちた run の resume で報告の事実の段が
        再生される。resume の子は種を新しく引き、親が種を立てていれば子へそのまま渡るので、種を名指して替える）"""
        returns = []
        for seed in ("0", "1"):
            with mock.patch.dict("os.environ", {"PYTHONHASHSEED": seed}):
                returns.append(self.seeded_run().script("collect", **self.args(passing())))
        first, second = returns
        self.assertEqual(first, second)
        self.assertRegex(first["digest"], r"^[0-9a-f]{64}$")

    def test_changed_facts_change_the_digest(self):
        """facts の材料を 1 か所変えると、pointer の path は同じまま digest が変わる（中身が変わった時に report が回し直る値の変化）"""
        run = self.seeded_run()
        before = run.script("collect", **self.args(passing()))
        changed = {**passing(), "notices": "注意（test_cmd）: 別の注意"}
        after = run.script("collect", **self.args(changed))
        self.assertEqual(before["facts"]["path"], after["facts"]["path"])
        self.assertNotEqual(before["digest"], after["digest"])

    def test_the_not_run_section_reaches_the_report_through_collect(self):
        """試験の関門の返りの related は、collect の受け皿の欄を通って報告の節「走らせなかった範囲」に届く（欄の一覧から外れると、絞った run
        でも走らせ方の行に落ち、「工場は絞らない」と誤って出る）"""
        run = self.seeded_run()
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

    def test_returns_use_the_last_round_eyes(self):
        """collect の script は eyes_back が在れば、その最後の周の目と試験と合わせを報告に使う（返さなかった run は最初の物）"""
        run = self.seeded_run()
        v = passing()
        last_eyes = {**v["eyes"], "report": ["- 最後の周の目: 通した"], "sections": [{"title": "独立の目 R1 最小性とコメント", "lines": ["- 最後の周の R1 通した"]}]}
        items = [{"eye": "r1", "where": "src/a.py:12", "text": "写しが残っている"}]
        v["eyes_back"] = {"rows": [{"round": 1, "r1": "fix-needed", "r2": "pass", "items": items}], "exit": "返す物が無い（どの目も通った）", "left": [],
                          "fixed": v["fixed"], "tests": v["test_gate_final"], "eyes": last_eyes, "fingerprint": None, "green_ok": True,
                          "eyes_ok": True, "sealable": True, "item_claims": None}
        got = run.script("collect", **self.args(v))
        sections = json.loads((run.artifacts / got["sections"]["path"]).read_text(encoding="utf-8"))
        text = json.dumps(sections, ensure_ascii=False)
        self.assertIn("最後の周の目: 通した", text)
        self.assertIn("最後の周の R1 通した", text)
        self.assertNotIn("- R1 通した", text, "最初の目の節は使わない")
        self.assertIn(kit.load(BLOCK, "eyesback").HEAD, [s["title"] for s in sections])
        fell = {**v["eyes_back"], "exit": kit.load(BLOCK, "eyesback").EXITS["fell"], "fixed": None, "tests": None, "eyes": None, "rows": []}
        got = run.script("collect", **self.args({**v, "eyes_back": fell}))
        text = (run.artifacts / got["sections"]["path"]).read_text(encoding="utf-8")
        self.assertIn("- R1 通した", text, "輪の節が落ちた記録なら最初の目を使う")
        self.assertNotIn("最後の周の目: 通した", text)

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
