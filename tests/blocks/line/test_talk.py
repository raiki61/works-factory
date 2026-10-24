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


class TalkBase(unittest.TestCase):
    """設計の相談の試験の助け（周の頭と終わりを place の一時のフォルダで回す）"""

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

    def settle(self, turn_got, plan_out=None, previous=None, design_talk=True):
        with self.run.env():
            return self.t.settle(turn_got=turn_got, plan_out=plan_out, previous=previous,
                                 given={"design_talk": design_talk, "unattended": False}, materials=no_materials, run_id=kit.RUN_ID)

    def opened(self, **over) -> dict:
        """対話モードで往復が止まった周の design-talk の返り（関所が開いた）"""
        return self.settle(self.turn(), self.plan_out(**over))



class TalkCase(TalkBase):
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
        got = self.settle(self.turn(), self.plan_out(done=False, ok=False))
        self.assertEqual((got["open"], got["done"]), (False, False))

    def test_nothing_owed_and_a_failed_plan_return_the_result_of_the_talk(self):
        for over, word in (({"status": "nothing_owed", "ok": False}, "直す義務の単位が無い"),
                           ({"status": "gave_up", "ok": False, "review_status": "", "review_reason": "受け付けを通らない"}, "設計案を作れなかった")):
            with self.subTest(status=over["status"]):
                got = self.opened(**over)
                self.assertTrue(got["open"])
                self.assertIn(word, got["text"])
                self.assertIn("修正へ進まずに報告を出す", got["asked"][0])

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
        self.assertEqual([k["decision"] for k in kept], ["continue"])

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
        got = self.settle(self.turn(), None)
        self.assertEqual((got["done"], got["ok"], got["stop_reason"]), (True, False, "works:line-script"))


class NotesCase(TalkBase):
    """人の指摘の受け箱（issue #830。docs/design/line.md の 3.1 節）: 対話モードの run だけ、周の頭で受け箱の新しい行を拾い、人の block
    として往復の記録に差し込む（往復が無ければ依頼の答えの行だけ）。待たない。周ごとに設計の控えを書く。受け箱の
    承認（頭が「承認:」か「もういいよ」の行）が生きていれば止まる周に関所を開かない。収まる周に新しい指摘が在れば終えない"""

    def note(self, *lines):
        inbox = self.run.artifacts / "talk" / "notes.txt"
        inbox.parent.mkdir(parents=True, exist_ok=True)
        with inbox.open("a", encoding="utf-8") as f:
            f.write("".join(f"{line}\n" for line in lines))

    def round_ran(self, **over):
        """1 周目の計画が回り、往復が続く（done 偽）周の design-talk の返り"""
        return self.settle(self.turn(), self.plan_out(done=False, ok=False, **over))

    def settle(self, turn_got, plan_out=None, previous=None, design_talk=True):
        with self.run.env():
            return self.t.settle(turn_got=turn_got, plan_out=plan_out, previous=previous,
                                 given={"design_talk": design_talk, "unattended": False}, materials=no_materials, run_id=kit.RUN_ID,
                                 place=self.run.artifacts)

    def test_a_note_before_the_first_round_reaches_the_plan(self):
        self.note("a.py は触らない")
        got = self.turn()
        self.assertTrue(got["plan"], "待たずに計画を回す")
        self.assertEqual(got["notes"], ["a.py は触らない"])
        self.assertEqual(got["answers"][-1], {"question": self.t.NOTE_NAME.format(n=1), "text": "a.py は触らない"})
        self.assertEqual(got["recorded"][-1]["name"], self.t.NOTE_NAME.format(n=1))

    def test_a_note_goes_into_the_record_as_a_person_block(self):
        """往復の後に入った指摘は、次の周の頭で人の block（中央）として最後の往復に差し込まれ、往復を AGAIN に戻す。頭が「端:」の行は端"""
        first = self.turn()
        talk = self.round_ran()
        self.note("b.py にも直しを入れる", "端: 名前を揃える")
        got = self.turn("", previous=talk, last=first)
        self.assertEqual((got["plan"], got["notes"]), (True, ["b.py にも直しを入れる", "端: 名前を揃える"]))
        doc = json.loads((self.run.artifacts / "plan-converge.json").read_text(encoding="utf-8"))
        last = doc["passes"][-1]
        self.assertEqual((doc["outcome"], last["blocks"][-2:]), ("again", ["person-1", "person-2"]))
        reach = {f["key"]: f.get("reach") for f in last["faces"]}
        self.assertEqual((reach["person-1"], reach["person-2"]), ("forces_redesign", "peripheral"))
        self.assertEqual(last["faces"][-1]["why"], "名前を揃える")
        self.assertNotEqual(got["plan_prior"], talk["plan_prior"], "人の block を差し込んだ prior の写し")
        again = self.turn("", previous={**talk, "notes": got["notes"]}, last=got)
        self.assertEqual(again["notes"], got["notes"], "取った行は 2 度拾わない")
        self.assertEqual(len([a for a in again["answers"] if a["question"].startswith("設計の相談で人が入れた")]), 2)

    def test_normal_run_ignores_the_inbox(self):
        self.note("無視される")
        got = self.turn(design_talk=False)
        self.assertEqual((got["notes"], got["answers"]), ([], [{"question": "q", "text": "a"}]))

    def test_each_round_writes_the_design_and_tells_where(self):
        talk = self.round_ran()
        path = pathlib.Path(talk["shown"])
        self.assertEqual(path, self.run.artifacts / "talk" / "round-1.md")
        text = path.read_text(encoding="utf-8")
        for word in (f"項目 1（u1）: {APPROACH}", "事前審査の結果", str(self.run.artifacts / "talk" / "notes.txt"), "端:"):
            self.assertIn(word, text)

    def test_the_last_gate_waits_unless_the_human_approved(self):
        """収まった周に関所を開くかは、受け箱に生きている承認（頭が「承認:」か「もういいよ」の行）が在るかの yes/no（持ち主の決め
        human-notes-in-rounds）。承認が在れば開かず、承認を合意として修正前の承認ノードへ運ぶ。指摘が入っただけでは承認でない"""
        noted = self.turn()
        self.note("b.py も")
        taken = self.turn("", previous=self.round_ran(), last=noted)
        waited = self.settle(taken, self.plan_out())
        self.assertEqual((waited["open"], waited["done"]), (True, False), "指摘が入っただけでは承認でないので最後に聞いて待つ")
        self.note("承認: a.py だけで進めてよい")
        got = self.settle(taken, self.plan_out())
        self.assertEqual((got["open"], got["done"]), (False, True))
        self.assertEqual((got["agreed"]["decision"], got["agreed"]["text"]), ("approve", "a.py だけで進めてよい"))
        out = self.g.before_fix(got, unattended_run=False, design=True, agreed=got["agreed"])
        self.assertEqual((out["open"], out["go"]), (False, True), "設計だけの行で開き直さずに修正へ進む")

    def test_a_new_central_finding_after_the_approval_cancels_it(self):
        """承認の後に新しい中央の指摘が出たら、出し手を問わず承認は取り消される（人の中央の行・審査役が後の往復で出した中央の block）。
        端の指摘では取り消さない"""
        t = self.t
        fold = t.fold_approval
        self.assertEqual(fold(None, ["承認: 進めて"], passes=1), {"text": "進めて", "passes": 1})
        self.assertEqual(fold(None, ["もういいよ"], passes=0)["text"], "")
        self.assertIsNone(fold(None, ["b.py も"], passes=1), "指摘は承認でない")
        self.assertIsNone(fold(None, ["もういいよ", "b.py も直す"], passes=1), "承認の後の人の中央の指摘は取り消す")
        self.assertIsNotNone(fold(None, ["もういいよ", "端: 名前を揃える"], passes=1), "端の指摘は取り消さない")
        face = lambda key, reach=None: {"key": key, **({"reach": reach} if reach else {})}
        doc = {"passes": [{"blocks": ["a1"], "faces": [face("a1")]},
                          {"blocks": ["a1", "e1"], "faces": [face("a1"), face("e1", "peripheral")]},
                          {"blocks": ["b1"], "faces": [face("b1")]}]}
        self.assertEqual(t.approval({"text": "進めて", "passes": 3}, doc), "進めて", "承認の後に往復が無い")
        self.assertIsNone(t.approval({"text": "進めて", "passes": 2}, doc), "承認の後の往復で審査役が新しい中央の block b1 を出した")
        self.assertEqual(t.approval({"text": "x", "passes": 1}, {"passes": doc["passes"][:2]}), "x", "続いた a1 と端の e1 は新しい中央でない")
        back = {"passes": [{"blocks": ["a1"], "faces": [face("a1")]}, {"blocks": ["b1"], "faces": [face("b1")]},
                           {"blocks": ["a1"], "faces": [face("a1")]}]}
        self.assertEqual(t.approval({"text": "x", "passes": 2}, back), "x",
                         "2 往復前に在った a1 の挙げ直しは新しい中央でない（承認より前の全部の往復と比べる。直前の往復だけと比べない）")

    def test_the_approval_does_not_skip_the_result_of_the_talk(self):
        """承認は往復が収まった周（修正へ進む抜け方か止まり）にだけ当てる。直す義務が無い周・計画ができなかった周は、承認が生きていても
        関所を開いて相談の結果を見せる（黙って終わらない）。最後の周に中央の指摘と承認が続けて入り、その指摘を次の周に回せない時
        （その周が収まらなかった・往復の安全の上限の周）も関所を開き、回せなかった指摘を見せる（指摘を落として承認だけを通さない）。
        止まった周と、事前審査が諦めた周（計画は通った）には承認を当てる（修正前の承認ノードが今どおり諦めた訳で開く）。上限の周でも、
        受け箱が承認だけか端の行と承認だけなら承認を当てる。回せなかった行の案内は、上限の周では設計し直せない旨にし、収まらなかった周は
        revise に書く旨にする（上限の周の revise は止める答えになるので、revise を勧めない）"""
        approve, both, edge = ("承認: 進めて",), ("b.py も直す", "承認: 進めて"), ("端: 名前を揃える", "承認: 進めて")
        gave_up = {"status": "gave_up", "ok": False, "review_status": "", "review_reason": "受け付けを通らない"}
        rows = (  # (plan-out の欄, 受け箱の行, 関所を開くか, 文に在るべき字)
            ({"status": "nothing_owed", "ok": False}, approve, True, "相談の結果"),
            (gave_up, approve, True, "相談の結果"),
            ({"status": "failed", "ok": False, "review_status": "", "review_reason": "落ちた"}, approve, True, "相談の結果"),
            (gave_up, both, True, "- b.py も直す"),
            ({"round": 20}, both, True, "この周は設計し直せない"),
            ({"round": 20}, approve, False, None),
            ({"round": 20}, edge, False, None),
            (gave_up, both, True, "直すなら revise の一言に書く"),
            ({"capped": True}, both, True, "- b.py も直す"),
            ({"capped": True, "ok": False, "stalled": True}, both, True, "- b.py も直す"),
            ({"ok": False, "stalled": True}, approve, False, None),
            ({"ok": False, "review_status": "gave_up", "review_reason": "諦めた"}, approve, False, None),
        )
        for over, lines, opens, word in rows:
            with self.subTest(over=over, lines=lines):
                self.run = kit.Run(self, BLOCK)
                taken = self.turn()
                self.note(*lines)
                got = self.settle(taken, self.plan_out(**over))
                if opens:
                    self.assertEqual((got["open"], got["done"], got["agreed"]), (True, False, None))
                    self.assertIn(word, got["text"])
                else:
                    self.assertEqual((got["open"], got["done"], got["agreed"]["decision"]), (False, True, "approve"))

    def test_a_review_finding_after_the_approval_makes_the_last_gate_wait(self):
        """承認を拾った周の後の往復で、審査役が新しい中央の block を出せば、収まった周に関所を開いて待つ"""
        first = self.turn()
        talk = self.round_ran()
        self.note("承認: 進めて")
        taken = self.turn("", previous=talk, last=first)
        self.assertEqual(taken["approved"], {"text": "進めて", "passes": 1})
        po = self.plan_out()   # 記録を 1 往復で書き直すので、後の往復を足す前に作る
        with self.run.env():
            doc = self.r.read(self.run.artifacts / "plan-converge.json")
            doc["passes"].append({**doc["passes"][-1], "pass": 2, "blocks": ["key-new"],
                                  "faces": [{"key": "key-new", "kind": "x", "where": "", "why": "w"}]})
            self.r.write(self.run.artifacts / "plan-converge.json", doc)
        got = self.settle(taken, po)
        self.assertEqual((got["open"], got["agreed"]), (True, None))

    def test_an_approval_line_is_not_a_block(self):
        first = self.turn()
        talk = self.round_ran()
        self.note("承認: 進めて")
        got = self.turn("", previous=talk, last=first)
        self.assertEqual((got["notes"], got["plan_prior"]), (["承認: 進めて"], talk["plan_prior"]), "承認の行は block にせず、取った行に数える")

    def test_a_new_note_keeps_a_settled_round_going(self):
        """収まる周でも、まだ拾っていない指摘が在れば終えずに次の周へ回す（次の周の頭が拾う）"""
        taken = self.turn()
        self.note("最後に気づいた")
        got = self.settle(taken, self.plan_out())
        self.assertEqual((got["done"], got["open"]), (False, False))


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

    def test_dialogue_run_shows_the_design_and_the_review(self):
        trace = self.traces["design-talk"]
        self.assertEqual(self.sc.got(trace, "plan-rounds")["open"], True, "往復の返りは design-talk の返り（本物と同じ）")
        talk = self.sc.out(trace, "design-talk")
        self.assertEqual((talk["open"], talk["done"]), (True, False))
        for word in ("設計案（計画の周 1）", "事前審査の結果", " revise ", "人が決める項目"):
            self.assertIn(word, talk["text"])


if __name__ == "__main__":
    unittest.main()
