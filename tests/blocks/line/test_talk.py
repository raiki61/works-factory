"""設計の相談（対話モードの run の計画の往復の末尾。docs/design/line.md の 3.1 節。issue #822）。src/talk.py・src/rounds.py の
ask_again・src/gates.py の before_fix の agreed・script design_turn・design_talk・ask_before_fix・before_fix_answer。

受け入れの照らし（#822 の頼みの受入確認）: 通常の run が変わらない（周の頭が前の周の値をそのまま運び、終わりが plan-out の返りを写す）・
対話の時に設計と審査を見せる・修正要望で設計し直しと再審査（人の block を記録に差し込み、次の周の plan と事前審査が答える）・合意の後に
修正前の承認ノードで聞き直さずに進む・止める答え・一言の空の修正要望は聞き直す（未回答を承認と読まない）・設計の要らない周と計画の
失敗の周も相談の結果を見せる・往復の安全の上限の周の修正要望は止める。複数の周を本物の Archon で回す照らしは
tests/e2e/test_design_talk_real.py。
"""
import json
import pathlib
import unittest

from tests.blocks import kit
from tests.blocks.line.test_gates import NARROW, ask_row, rounds

BLOCK = "line"
APPROACH = "空の列で 0 を返す形に変える"


def no_materials(_rounds) -> dict:
    """設計の相談の行の材料（判定・構造の目・方針の文書の変化・前の答えの無い run）"""
    return {"ledger": None, "design_rows_": [], "policy_row": "", "stuck_reason": "", "record_doc": None, "answered": [],
            "unread": []}


class TalkCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, BLOCK)
        with self.run.env():
            self.t = kit.load(BLOCK, "talk")
            self.r = kit.load(BLOCK, "rounds")
            self.g = kit.load(BLOCK, "gates")
        self.answer = __import__("answer")

    def put(self, rel: str, doc) -> dict:
        path = self.run.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return json.loads(self.run.pointer(rel))

    def record(self, *, outcome="clean", state="closed", blocks=()) -> dict:
        """往復が 1 つで、項目 1 つの記録（plan-converge.json）"""
        plan = [{"id": "u1", "unit_keys": ["u1"], "hash": "h1"}]
        p = {"pass": 1, "blocks": list(blocks), "faces": [{"key": b, "kind": "x", "where": "", "why": "w"} for b in blocks],
             "suggests": [], "answers": [], "notes": [], "resolved": [], "persists": [], "outcome": outcome, "origins": {},
             "origins_claimed": [], "files": {}, "rejects": [], "face_units": {},
             "items": [{"n": 1, "id": "u1", "unit_keys": ["u1"], "hash": "h1", "state": state, "blocks": list(blocks), "reopened": False}]}
        return {"round": 1, "passes": [p], "outcome": outcome, "plan": plan}

    def plan_out(self, **over) -> dict:
        """plan-out の返り（往復の記録と案の控えの pointer つき）"""
        record = self.put("plan-converge.json", self.record())
        prior = self.put("plan-rounds/prior-1.json", {"round": 1, "reply": None, "fields": None, "record": self.record()})
        fix_plan = self.put("plan/r1/p2.fix_plan.json", {"plan": [{"unit_keys": ["u1"], "approach": APPROACH}]})
        fields = self.put("plan/r1/plan-fields.json", {"fields": [{"unit_keys": ["u1"], "allowed_paths": ["a.py"], "route": "tdd"}]})
        return {**rounds(record=record, plan_prior=prior, fix_plan=fix_plan, plan=fields), **over}

    def turn(self, answer="", previous=None, last=None, design_talk=True, **given):
        with self.run.env():
            return self.t.turn(answer_raw=answer if isinstance(answer, str) else json.dumps(answer),
                               previous_raw=json.dumps(previous) if previous is not None else "",
                               last_raw=json.dumps(last) if last is not None else "",
                               given={"design_talk": design_talk, "unattended": False, "request_answers": [{"question": "q", "text": "a"}],
                                      **given},
                               recorded=[{"source": "doc", "name": "p.md", "text": ""}], place=self.run.artifacts)

    def settle(self, turn_got, plan_out=None, previous=None, design_talk=True, judge=None):
        with self.run.env():
            return self.t.settle(turn_got=turn_got, plan_out=plan_out, previous=previous,
                                 given={"design_talk": design_talk, "unattended": False}, materials=no_materials, run_id=kit.RUN_ID,
                                 judge=judge)

    def planned(self) -> dict:
        """対話モードで、1 周目の早い相談に approve と答えた後の周の頭（計画を回す周）"""
        first = self.turn()
        early = self.settle(first, None)
        return self.turn({"decision": "approve", "text": ""}, previous=early, last=first)

    def opened(self, **over) -> dict:
        """対話モードで往復が止まった周の design-talk の返り（関所が開いた）"""
        return self.settle(self.planned(), self.plan_out(**over))

    # ------------------------------------------------------------------ 通常の run は変わらない
    def test_normal_run_carries_the_previous_round_as_it_was(self):
        first = self.turn(design_talk=False)
        self.assertEqual((first["plan"], first["plan_prior"], first["record"]), (True, "", ""))
        self.assertEqual(first["answers"], [{"question": "q", "text": "a"}], "依頼の答えのまま（今の request_answers）")
        self.assertEqual(first["recorded"], [{"source": "doc", "name": "p.md", "text": ""}], "owed の recorded のまま")
        po = self.plan_out(done=False)
        later = self.turn(previous={**po, "open": False, "text": "", "asked": [], "agreed": None, "talks": []}, design_talk=False)
        self.assertEqual((later["plan"], later["plan_prior"], later["record"]), (True, po["plan_prior"], po["record"]))

    def test_normal_run_settles_to_the_plan_out_return(self):
        po = self.plan_out()
        got = self.settle(self.turn(design_talk=False), po, design_talk=False)
        self.assertEqual({k: got[k] for k in po}, po)
        self.assertEqual((got["open"], got["text"], got["agreed"]), (False, "", None))

    def test_unattended_design_only_run_does_not_talk(self):
        """無人の run は人がいないので、設計だけでも相談の関所を開かない（修正前の承認ノードの今の止め方のまま）"""
        self.assertFalse(self.t.dialogue({"design_talk": True, "unattended": True}))
        self.assertTrue(self.t.dialogue({"design_talk": True, "unattended": False}))

    # ------------------------------------------------------------------ 設計と審査を見せる
    def test_dialogue_opens_on_the_round_that_stops_with_the_design_and_the_review(self):
        got = self.opened(asks=[ask_row()])
        self.assertEqual((got["open"], got["done"]), (True, False), "答えを次の周の頭が読むので、往復はまだ終わらない")
        self.assertIn("設計の相談の承認ノード（gate-design）", got["text"])
        self.assertIn(f"項目 1（u1）: {APPROACH}", got["text"])
        self.assertIn("書く所: a.py・直し方: tdd", got["text"])
        self.assertIn("事前審査の壁打ち: 1 往復", got["text"])
        self.assertIn(f'{kit.RUN_ID} revise "<直してほしい所>"', got["text"])
        self.assertEqual(got["asked"], [NARROW], "人が決める項目は修正前の承認ノードと同じ決めで組む")

    def test_dialogue_keeps_going_while_the_rounds_go_on(self):
        got = self.settle(self.planned(), self.plan_out(done=False, ok=False))
        self.assertEqual((got["open"], got["done"]), (False, False))

    def test_nothing_owed_and_a_failed_plan_return_the_result_of_the_talk(self):
        for over, word in (({"status": "nothing_owed", "ok": False}, "直す義務の単位が無い"),
                           ({"status": "gave_up", "ok": False, "review_status": "", "review_reason": "受け付けを通らない"}, "設計案を作れなかった")):
            with self.subTest(status=over["status"]):
                got = self.opened(**over)
                self.assertTrue(got["open"])
                self.assertIn(word, got["text"])
                self.assertIn("修正へ進まずに報告を出す", got["asked"][0])

    # ------------------------------------------------------------------ 判定の後の早い相談（issue #830）
    def judge(self) -> dict:
        outside = self.put("judge/out-of-purpose.json", {"rounds": {"1": [{"source": "P1", "where": "b.py:3", "why_outside": "目的の外の読みの所見"}]}})
        return {"purpose_text": "空の列でも mean が落ちない", "units": [{"id": "u1", "paths": ["stats.py"], "summary": "空の列の mean が 0 割りで落ちる"}],
                "out_of_purpose": outside, "tier": "標準", "tier_why": "単位 1 つ",
                "questions": [{"key": "q-a", "kind": "fork", "reason": "0 か None かで割れる"}]}

    def early(self) -> tuple:
        """対話モードの 1 周目の (周の頭, 周の終わり)"""
        first = self.turn()
        return first, self.settle(first, None, judge=self.judge())

    def test_dialogue_asks_after_the_judge_before_planning(self):
        """対話モードの run の 1 周目は計画を回さず、判定の読み（目的・直す単位・目的の外・段・判定の問い）を見せる関所を開く"""
        first, got = self.early()
        self.assertEqual((first["plan"], first["early"]), (False, True), "計画を書く前に聞く")
        self.assertEqual((got["open"], got["done"], got["asked"], got["agreed"]), (True, False, [], None))
        for word in ("判定が済んだ所で開いた", "空の列でも mean が落ちない", "u1: 空の列の mean が 0 割りで落ちる（stats.py）",
                     "b.py:3: 目的の外の読みの所見", "深さの段: 標準（単位 1 つ）", "q-a: 0 か None かで割れる", f'{kit.RUN_ID} revise "<違う所'):
            self.assertIn(word, got["text"])

    def test_normal_and_unattended_runs_do_not_ask_early(self):
        """対話モードでない run と無人の run は 1 周目から計画を回す（早い相談の関所を開かない）"""
        for given in ({"design_talk": False}, {"design_talk": True, "unattended": True}):
            with self.subTest(**given):
                got = self.turn(**given)
                self.assertEqual((got["plan"], got["early"]), (True, False))

    def test_the_early_word_reaches_the_plan_and_the_review(self):
        """早い相談の「ここが違う」（revise と一言）と通す一言（continue と一言）は、次の周の plan の answers と事前審査の recorded に
        依頼の答えの行で届き、後の周にも運ぶ。一言の無い approve は依頼の答えを変えない。どれも設計への合意（agreed）にしない"""
        for decision, text, want in (("revise", "a.py は触らず b.py で直す", True), ("continue", "a.py だけ", True), ("approve", "", False)):
            with self.subTest(decision=decision):
                first, early = self.early()
                nxt = self.turn({"decision": decision, "text": text}, previous=early, last=first)
                self.assertEqual((nxt["plan"], nxt["early"], nxt["plan_prior"], nxt["record"]), (True, False, "", ""))
                name = self.t.EARLY_NAME.format(n=1)
                self.assertEqual(nxt["answers"][-1] == {"question": name, "text": text}, want, nxt["answers"])
                self.assertEqual(nxt["recorded"][-1].get("name") == name, want)
                po = self.plan_out()
                talk = self.settle(nxt, po)
                self.assertEqual((talk["open"], talk["agreed"]), (True, None), "設計案と事前審査の後に、改めて設計の相談で聞く")
                later = self.turn("", previous={**po, **{k: talk[k] for k in self.t.TALK_FIELDS}}, last=nxt)
                self.assertEqual(later["answers"][-1] == {"question": name, "text": text}, want, "後の周にも運ぶ")

    def test_stop_at_the_early_talk_stops_before_planning(self):
        first, early = self.early()
        nxt = self.turn({"decision": "stop", "text": "読みが違う"}, previous=early, last=first)
        self.assertFalse(nxt["plan"])
        got = self.settle(nxt, None, previous=early)
        self.assertEqual((got["done"], got["agreed"]["decision"], got["stop_reason"]), (True, "stop", ""))
        out = self.g.before_fix(got, unattended_run=False, design=True, agreed=got["agreed"])
        self.assertEqual((out["go"], out["stop_reason"]), (False, "human:gate-design"))

    def test_empty_revise_at_the_early_talk_asks_again(self):
        first, early = self.early()
        nxt = self.turn({"decision": "revise", "text": ""}, previous=early, last=first)
        self.assertEqual((nxt["plan"], nxt["early"]), (False, True), "早い相談のまま聞き直す")
        again = self.settle(nxt, None, previous=early)
        self.assertEqual((again["open"], again["done"]), (True, False))
        self.assertTrue(again["text"].startswith(self.t.EMPTY_REVISE))
        self.assertIn("空の列でも mean が落ちない", again["text"])
        go = self.turn({"decision": "approve", "text": ""}, previous=again, last=nxt)
        self.assertEqual((go["plan"], go["early"]), (True, False))

    # ------------------------------------------------------------------ 答え
    def shown(self) -> dict:
        return self.opened(asks=[ask_row()])

    def test_agreement_ends_the_rounds_and_keeps_the_answer(self):
        shown = self.shown()
        turn = self.turn({"decision": "continue", "text": "a.py だけ"}, previous=shown)
        self.assertFalse(turn["plan"], "合意の周は plan も事前審査も回さない")
        got = self.settle(turn, None, previous=shown)
        self.assertEqual((got["done"], got["open"]), (True, False))
        self.assertEqual(got["agreed"], {"round": 1, "decision": "continue", "text": "a.py だけ", "asked": [NARROW]})
        self.assertEqual({k: got[k] for k in ("ok", "status", "record", "fix_plan")}, {k: shown[k] for k in ("ok", "status", "record", "fix_plan")})
        kept = json.loads((self.run.artifacts / "gates" / "gate-design.json").read_text(encoding="utf-8"))
        self.assertEqual([k["decision"] for k in kept], ["approve", "continue"], "早い相談の答えと設計への合意を並べる")
        self.assertEqual([bool(k.get("early")) for k in kept], [True, False])

    def test_stop_ends_the_rounds_with_the_answer(self):
        shown = self.shown()
        got = self.settle(self.turn({"decision": "stop", "text": "やめる"}, previous=shown), None, previous=shown)
        self.assertEqual((got["done"], got["agreed"]["decision"]), (True, "stop"))

    def test_revise_puts_the_ask_into_the_record_and_plans_again(self):
        shown = self.shown()
        turn = self.turn({"decision": "revise", "text": "b.py にも直しを入れる"}, previous=shown)
        self.assertTrue(turn["plan"])
        self.assertNotEqual(turn["plan_prior"], shown["plan_prior"], "人の block を差し込んだ prior の写し")
        doc = json.loads((self.run.artifacts / "plan-converge.json").read_text(encoding="utf-8"))
        last = doc["passes"][-1]
        self.assertEqual((doc["outcome"], last["outcome"], last["blocks"][-1]), ("again", "again", "person-1"))
        self.assertEqual(last["faces"][-1]["why"], "b.py にも直しを入れる")
        self.assertEqual([it["state"] for it in last["items"]], ["open"], "閉じた項目を開き直す")
        prior = json.loads((self.run.artifacts / "plan-rounds" / "talk-1.json").read_text(encoding="utf-8"))
        self.assertEqual(prior["record"]["passes"][-1]["blocks"][-1], "person-1")
        self.assertEqual(turn["answers"][-1], {"question": "設計の相談で人が求めた 1 番目の直し", "text": "b.py にも直しを入れる"})
        self.assertEqual(turn["recorded"][-1]["name"], "設計の相談で人が求めた 1 番目の直し")
        again = self.turn("", previous=shown, last=turn)
        self.assertEqual(again["answers"][-1]["question"], "設計の相談で人が求めた 1 番目の直し", "求めは後の周にも運ぶ")

    def test_empty_revise_asks_again_without_planning(self):
        shown = self.shown()
        turn = self.turn({"decision": "revise", "text": " "}, previous=shown)
        self.assertFalse(turn["plan"])
        got = self.settle(turn, None, previous=shown)
        self.assertEqual((got["open"], got["done"], got["asked"]), (True, False, shown["asked"]))
        self.assertTrue(got["text"].startswith(self.t.EMPTY_REVISE))
        twice = self.settle(self.turn({"decision": "revise", "text": ""}, previous=got), None, previous=got)
        self.assertEqual(twice["text"].count(self.t.EMPTY_REVISE), 1, "断りの文を積み重ねない（独立レビューの指摘 3）")

    def test_revise_at_the_cap_stops(self):
        shown = self.opened(round=20)
        self.assertIn("設計し直させる: できない", shown["text"])
        turn = self.turn({"decision": "revise", "text": "もう一度"}, previous=shown)
        self.assertEqual((turn["plan"], turn["stop_reason"]), (False, "works:plan-converge"))
        got = self.settle(turn, None, previous=shown)
        self.assertEqual((got["done"], got["stop_reason"]), (True, "works:plan-converge"))
        self.assertIn("もう一度", got["agreed"]["text"], "上限の訳を足しても人の一言は報告に残す")
        out = self.g.before_fix(got, unattended_run=False, design=True, agreed=got["agreed"])
        self.assertEqual((out["go"], out["stop_reason"]), (False, "works:plan-converge"))

    def test_empty_revise_stops_after_the_limit(self):
        """一言の空の revise は計画を回さずにループの周を使うので、EMPTY_LIMIT 回まで聞き直し、その次は止める（max_iterations を越えない）"""
        got = self.shown()
        for _ in range(self.t.EMPTY_LIMIT):
            turn = self.turn({"decision": "revise", "text": ""}, previous=got)
            self.assertEqual(turn["stop_reason"], "")
            got = self.settle(turn, None, previous=got)
            self.assertTrue(got["open"])
        turn = self.turn({"decision": "revise", "text": ""}, previous=got)
        self.assertEqual((turn["plan"], turn["stop_reason"]), (False, "human:gate-design"))
        end = self.settle(turn, None, previous=got)
        self.assertEqual((end["done"], end["open"], end["stop_reason"]), (True, False, "human:gate-design"))
        out = self.g.before_fix(end, unattended_run=False, design=True, agreed=end["agreed"])
        self.assertEqual((out["go"], out["stop_reason"]), (False, "human:gate-design"))

    def test_a_failed_turn_does_not_make_up_an_answer(self):
        """周の頭が落ちた（答えの無い止め）周は、人が答えたことにしない（agreed は null）"""
        got = self.settle({"plan": False, "answer": None, "talks": [], "stop_reason": "works:line-script", "reason": "落ちた"}, None,
                          design_talk=False)
        self.assertEqual((got["done"], got["agreed"]), (True, None))

    def test_ask_names_do_not_overlap(self):
        """依頼の答えの行の名は名指しを字の一致で照らすので、ほかの番号の名を含まない（1 番目と 10 番目）"""
        self.assertNotIn(self.t.ASK_NAME.format(n=1), self.t.ASK_NAME.format(n=10))

    def test_a_failed_round_reuses_the_prior_it_was_given(self):
        """計画ができなかった周は prior を書かない。修正要望の周は、その周が受けた prior から計画し直す"""
        prior = self.put("plan-rounds/prior-1.json", {"round": 1})
        got = self.turn("", previous={"plan_prior": None, "record": None, "talks": []}, last={"plan_prior": prior, "asks": []})
        self.assertEqual(got["plan_prior"], prior)

    def test_a_missing_plan_out_fails_the_round_without_breaking_the_loop(self):
        got = self.settle(self.planned(), None)
        self.assertEqual((got["done"], got["ok"], got["stop_reason"]), (True, False, "works:line-script"))


class AskAgainCase(unittest.TestCase):
    """人の修正要望は中央の block。次の周の事前審査が挙げ直せば止まり（PERSISTED）、消えたと言えば閉じる（converge の止め時のまま）"""

    def setUp(self):
        self.r = kit.load(BLOCK, "rounds")

    def doc(self, state="closed"):
        return {"round": 1, "outcome": "clean", "plan": [{"id": "u1", "unit_keys": ["u1"], "hash": "h1"}],
                "passes": [{"pass": 1, "blocks": [], "faces": [], "suggests": [], "answers": [], "resolved": [], "persists": [],
                            "outcome": "clean", "face_units": {},
                            "items": [{"n": 1, "id": "u1", "unit_keys": ["u1"], "hash": "h1", "state": state, "blocks": [], "reopened": False}]}]}

    def test_held_items_open_too(self):
        doc = self.r.ask_again(self.doc("held"), key="person-1", text="直す")
        self.assertEqual(doc["passes"][-1]["items"][0]["state"], "open")

    def test_no_passes_is_left_as_it_is(self):
        self.assertEqual(self.r.ask_again({"round": 1, "passes": [], "outcome": None}, key="person-1", text="x")["passes"], [])

    def test_the_next_review_decides_with_the_same_rule(self):
        for faces, resolved, want in (([{"key": "person-1", "severity": "block", "why": "まだ"}], [], "persisted"),
                                      ([], ["person-1"], "clean")):
            with self.subTest(want=want):
                doc = self.r.ask_again(self.doc(), key="person-1", text="直す")
                row = self.r.add_pass(doc, {"faces": faces}, answers=[{"key": "person-1", "handled": "fixed", "how": "b.py を足した"}],
                                      resolved=resolved)
                self.assertEqual(row["outcome"], want)


class BeforeFixAgreedCase(unittest.TestCase):
    """修正前の承認ノードは、合意した同じ承認を聞き直さない（新しく出た行だけ開く）"""

    def setUp(self):
        self.g = kit.load(BLOCK, "gates")

    def ask(self, got, agreed, **kw):
        return self.g.before_fix(got, unattended_run=False, design=True, agreed=agreed, **kw)

    def test_agreed_rows_are_not_asked_again_and_no_design_only_row(self):
        out = self.ask(rounds(asks=[ask_row()]), {"decision": "continue", "text": "通す", "asked": [NARROW]})
        self.assertEqual((out["open"], out["go"], out["asked"]), (False, True, []))

    def test_a_new_row_after_the_agreement_opens(self):
        out = self.ask(rounds(asks=[ask_row()]), {"decision": "approve", "text": "", "asked": []})
        self.assertEqual((out["open"], out["asked"]), (True, [NARROW]))

    def test_stop_at_the_talk_stops_before_fix(self):
        """人が止めた時は、往復の返りの止めの語（計画の落ちなど）でなく human:gate-design を名乗る"""
        for got in (rounds(), rounds(status="nothing_owed", ok=False), rounds(ok=False, status="failed", stop_reason="works:line-script")):
            with self.subTest(status=got["status"]):
                out = self.ask(got, {"decision": "reject", "text": "x", "asked": []})
                self.assertEqual((out["open"], out["go"], out["stop_reason"]), (False, False, "human:gate-design"))

    def test_agreed_stalled_rounds_go_to_the_fix(self):
        stuck = "同じ block が続いた"
        row = f"{__import__('gatemarks').STUCK_ITEM}。理由: {stuck}"
        out = self.ask(rounds(ok=False, stalled=True), {"decision": "continue", "text": "", "asked": [row]}, stuck_reason=stuck)
        self.assertEqual((out["open"], out["go"]), (False, True))

    def test_agreed_policy_change_refreezes(self):
        row = "人の方針の文書 p.md が固定した版から変わった"
        out = self.ask(rounds(), {"decision": "continue", "text": "", "asked": [row]}, policy_row=row)
        self.assertEqual((out["open"], out["go"], out["policy_changed"]), (False, True, True))

    def test_agreed_nothing_owed_does_not_fix(self):
        out = self.ask(rounds(status="nothing_owed", ok=False), {"decision": "approve", "text": "", "asked": []})
        self.assertEqual((out["open"], out["go"], out["stop_reason"]), (False, False, ""))

    def test_the_report_shows_the_talk_answer(self):
        """設計の相談で止めた一言も、報告の承認ノードの答えに gate-design として出る（独立レビューの指摘 2）。対話モードでない run は出ない"""
        facts = kit.load(BLOCK, "facts")
        said = {"round": 1, "decision": "stop", "text": "やめる", "asked": []}
        self.assertEqual(facts.gates_of({"ask_before_fix": {"agreed": said}})["gate-design"], said)
        self.assertNotIn("gate-design", facts.gates_of({"ask_before_fix": {"agreed": None}}))

    def test_the_report_counts_one_agreement_once(self):
        """通す語の合意は answer-before-fix が修正前の答えとして書くので、報告は gate-design と 2 度数えない（修正前の答えが無い時だけ出す）"""
        facts = kit.load(BLOCK, "facts")
        said = {"round": 1, "decision": "continue", "text": "通す", "asked": []}
        written = {"answer": {"decision": "continue", "text": "通す", "asked": []}}
        self.assertNotIn("gate-design", facts.gates_of({"ask_before_fix": {"agreed": said}, "answer_before_fix": written}))
        self.assertEqual(facts.gates_of({"ask_before_fix": {"agreed": said}})["gate-design"], said)

    def test_agreed_ledger_question_is_not_asked_again(self):
        """設計の相談で見せた台帳の問いに合意したら、修正前の承認ノードは同じ問いで開かない（材料の台帳が合意を関所の答えとして読む）"""
        gm = __import__("gatemarks")
        fork = {"key": "q-a", "kind": "fork", "status": "held", "origin": "u1", "options": ["x", "y"], "reason": "割れる"}
        judgment = {"units": [{"key": "u1", "label": "block"}], "questions": [fork]}
        run = kit.Run(self, BLOCK)
        (run.artifacts / "judgment.json").write_text(json.dumps(judgment, ensure_ascii=False), encoding="utf-8")
        asked = [gm.ask_text(q) for q in gm.asks(gm.ledger(judgment))]
        agreed = {"decision": "continue", "text": "q-a は x", "asked": asked}
        with run.env():
            asking = kit.load(BLOCK, "asking")
            judge = json.dumps({"judgment": json.loads(run.pointer("judgment.json")), "answer_ties": None, "materials": None})
            for given, want in ((agreed, False), (None, True)):
                with self.subTest(agreed=given is not None):
                    kw = asking.materials({**rounds(), "agreed": given}, structure_raw=None, judge_raw=judge, record_raw="",
                                          unattended=False, place=run.artifacts)
                    out = self.g.before_fix(rounds(), unattended_run=False, design=False, agreed=given, **kw)
                    self.assertEqual(out["open"], want)

    def test_without_agreement_design_only_still_opens(self):
        out = self.g.before_fix(rounds(), unattended_run=False, design=True)
        self.assertTrue(out["open"])


class ScriptCase(unittest.TestCase):
    """script を子のプロセスで回す"""

    def setUp(self):
        self.run = kit.Run(self, BLOCK)

    def test_before_fix_answer_writes_the_agreement_as_the_answer(self):
        record = self.run.artifacts / "r1" / "start.json"
        record.parent.mkdir(parents=True)
        record.write_text("{}", encoding="utf-8")
        agreed = {"round": 1, "decision": "continue", "text": "a.py だけ", "asked": [NARROW]}
        out = self.run.script("before_fix_answer", gate="null", go="true", stop_reason="", place="gate-before-fix", asked="[]",
                              pushed="null", policy_changed="false", agreed=json.dumps(agreed, ensure_ascii=False),
                              record=self.run.pointer("r1/start.json"), ports=json.dumps({"policy": ""}))
        self.assertEqual((out["go"], out["answer"]["decision"], out["answer"]["text"], out["answer"]["asked"]),
                         (True, "continue", "a.py だけ", [NARROW]))
        kept = json.loads((self.run.artifacts / "gates" / "gate-before-fix.json").read_text(encoding="utf-8"))
        self.assertEqual(kept["text"], "a.py だけ")

    def test_a_gate_opened_after_the_agreement_still_carries_the_agreement(self):
        """合意の後に新しい行で修正前の承認ノードが開き、人が通した時も、合意した行と一言は修正役へ運ぶ（独立レビューの指摘 1）"""
        record = self.run.artifacts / "r1" / "start.json"
        record.parent.mkdir(parents=True)
        record.write_text("{}", encoding="utf-8")
        agreed = {"round": 1, "decision": "continue", "text": "B で", "asked": [NARROW]}
        new_row = "人の方針の文書 p.md が固定した版から変わった"
        out = self.run.script("before_fix_answer", gate=json.dumps({"decision": "continue", "text": "方針も通す"}, ensure_ascii=False),
                              go="true", stop_reason="", place="gate-before-fix", asked=json.dumps([new_row], ensure_ascii=False),
                              pushed="null", policy_changed="false", agreed=json.dumps(agreed, ensure_ascii=False),
                              record=self.run.pointer("r1/start.json"), ports=json.dumps({"policy": ""}))
        self.assertEqual((out["answer"]["asked"], out["answer"]["text"]), ([NARROW, new_row], "B で\n方針も通す"))
        stopped = self.run.script("before_fix_answer", gate=json.dumps({"decision": "stop", "text": "やめる"}, ensure_ascii=False),
                                  go="true", stop_reason="", place="gate-before-fix", asked=json.dumps([new_row], ensure_ascii=False),
                                  pushed="null", policy_changed="false", agreed=json.dumps(agreed, ensure_ascii=False),
                                  record=self.run.pointer("r1/start.json"), ports=json.dumps({"policy": ""}))
        self.assertEqual((stopped["go"], stopped["answer"]["asked"]), (False, [new_row]), "止める答えは合意と混ぜない")

    def test_ask_before_fix_reads_the_agreement_from_the_rounds(self):
        record = self.run.artifacts / "r1" / "start.json"
        record.parent.mkdir(parents=True)
        record.write_text('{"answers": []}', encoding="utf-8")
        agreed = {"round": 1, "decision": "continue", "text": "", "asked": [NARROW]}
        got = {**rounds(asks=[ask_row()]), "open": False, "text": "", "asked": [], "agreed": agreed, "talks": [agreed]}
        out = self.run.script("ask_before_fix", rounds=json.dumps(got, ensure_ascii=False), structure="null",
                              judge=json.dumps({"judgment": None, "answer_ties": None, "materials": None}),
                              record=self.run.pointer("r1/start.json"),
                              ports=json.dumps({"unattended": False, "design_talk": True, "policy": ""}))
        self.assertEqual((out["open"], out["go"], out["agreed"]), (False, True, agreed), out)


class DryRunBodiesCase(unittest.TestCase):
    def test_only_the_sole_end_gate_of_a_loop_body_is_taken_out(self):
        """筋書きの木の書き直し（tests/archon.py の dry_run_bodies）は、本体の唯一の終わりの関所だけを外す。ほかの関所と節は残す"""
        import shutil
        import tempfile

        import yaml

        from tests import archon
        with tempfile.TemporaryDirectory() as tmp:
            placed = pathlib.Path(tmp)
            shutil.copytree(kit.BLOCKS / BLOCK, placed / BLOCK)
            self.assertEqual(archon.dry_run_bodies(placed), ["gate-design"])
            doc = yaml.safe_load((placed / BLOCK / f"works-factory-{BLOCK}.yaml").read_text(encoding="utf-8"))
        top = {n["id"]: n for n in doc["nodes"]}
        body = [n["id"] for n in top["plan-rounds"]["loop_group"]["nodes"]]
        self.assertEqual(body, ["design-turn", "plan", "plan-review-run", "plan-out", "design-talk"])
        self.assertIn("gate-before-fix", top)


class DryRunCase(unittest.TestCase):
    """筋書きの dry-run（本物の line の script が回る）: 通常の run は周の頭と終わりが走っても関所が飛び、往復の返りは plan-out の返りの
    まま。対話モードの run は design-talk が関所を開く返りと設計の相談の文を出す（筋書きの木は本体の終わりの関所を外す。
    tests/archon.py の dry_run_bodies。dry-run は輪を 1 周で終えたことにするので、答えた後の周は回らない）"""

    @classmethod
    def setUpClass(cls):
        from tests.blocks.line import test_scenarios as sc
        cls.sc = sc
        cls.traces = sc.line_traces(("standard", "design-talk"))

    def test_normal_run_skips_the_talk_and_returns_the_plan_out(self):
        trace = self.traces["standard"]
        self.assertTrue(self.sc.ran(trace, "design-turn") and self.sc.ran(trace, "design-talk"))
        self.assertNotIn("gate-design", trace, "筋書きの木は本体の終わりの関所を外す")
        self.assertEqual(self.sc.got(trace, "plan-rounds")["status"], "ok", "往復の返りが空でない（dry-run でも本物と同じ形）")
        po, talk = self.sc.out(trace, "plan-out"), self.sc.out(trace, "design-talk")
        self.assertEqual({k: talk[k] for k in po}, po)
        self.assertEqual((talk["open"], talk["agreed"], talk["talks"]), (False, None, []))
        turn = self.sc.out(trace, "design-turn")
        self.assertEqual((turn["plan"], turn["plan_prior"], turn["record"], turn["recorded"]), (True, "", "", []))

    def test_dialogue_run_asks_after_the_judge_first(self):
        """対話モードの run の 1 周目は計画を回さず、判定の読みで早い相談の関所を開く（issue #830。計画と事前審査の後の相談の文は、
        答えた後の周が要るので test_talk の TalkCase と本物の Archon の tests/e2e/test_design_talk_real.py が照らす）"""
        trace = self.traces["design-talk"]
        self.assertEqual(self.sc.got(trace, "plan-rounds")["open"], True, "往復の返りは design-talk の返り（本物と同じ）")
        turn, talk = self.sc.out(trace, "design-turn"), self.sc.out(trace, "design-talk")
        self.assertEqual((turn["plan"], turn["early"]), (False, True))
        self.assertFalse(self.sc.ran(trace, "plan-out"), "計画を書く前に聞く")
        self.assertEqual((talk["open"], talk["done"]), (True, False))
        for word in ("判定が済んだ所で開いた", "空の列でも mean が落ちない", "u1: 空の列の mean が 0 割りで落ちる", " revise "):
            self.assertIn(word, talk["text"])


if __name__ == "__main__":
    unittest.main()
