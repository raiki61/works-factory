"""line の承認ノード（docs/design/line.md の 2 節・6 節・8.1。src/gates.py・src/final.py と script ask_before_fix・before_fix_answer・
ask_replan・replan_answer・ask_final・eyes_in）。

元は test_line.py の AskBeforeFixCase・AskReplanCase・AskFinalCase・AskFinalReadsCase・FinalGateCase・
LedgerAsksCase（docs/design/README.md の 9.5）。新しい形では修正前の承認ノードの軸・項目・聞かずに通した行を
line が事前審査の返りの行（asks・deviations）から組むので、行の材料は plan-review の出力の形で渡す。足した物: 修正の後の並行 PR の
確かめ直しの found と失敗が開ける理由に入り、must でない（8.1）。
守る keep-essence: 6（回さなかった試験を最後の承認ノードに名で並べる）・8（人に回した申し出で最後の承認ノードが開く）・10（守りの
パスに触れたら開き、封じの値を置く段へ渡す）・11（単位ごとの閉鎖の数え直しが最後の承認ノードに届く）・12（定石からの外れを修正前の
承認ノードで人に回す）。
"""
import json
import pathlib
import shutil
import tempfile
import unittest

from tests.blocks import kit
from tests.blocks.line.test_tiers import handed

BLOCK = "line"
SCRIPTS = kit.BLOCKS / BLOCK / "scripts"
RUN = kit.RUN_ID
REC = {"answer": "continue", "note": "空の列は 0 を返す形で通す", "why": "呼び手が 0 を前提に書かれている"}
STOP_REC = {**REC, "answer": "stop"}
NARROW = "修正案 1 が狭める能力: 空の列で例外を投げる——0 を返す形に変える"
FACE = "事前審査の穴 [regression] keep-zero: 0 を返すと前の呼び手が壊れる"


def ask_row(text=NARROW, *, decided=False, why=None, mark=None, kind="regression") -> dict:
    """plan-review の出力 asks の 1 行（plan-review の設計書の 10.1）"""
    return {"kind": kind, "node": "p2.fix_plan", "text": text, "units": ["u1"], "mark": mark or {},
            "decided": decided, "why": why if why is not None else ({} if decided else {"obvious": ["決め手の欄が揃わない"]})}


def rounds(**over) -> dict:
    """計画の往復の返り（plan-out の返り）。既定は修正へ進む抜け方で、人に回しうる行は無い"""
    return {"done": True, "ok": True, "status": "ok", "round": 1, "plan_prior": None, "record": None, "plan": None, "fix_plan": None,
            "reply": None, "handoffs": [], "ripple": None, "owed": ["u1"], "gave_up": None, "stalled": False, "capped": False,
            "review": None, "asks": [], "deviations": [], "review_status": "ok", "review_reason": "", "stop_reason": "", **over}


class AskBeforeFixCase(unittest.TestCase):
    def setUp(self):
        self.g = kit.load(BLOCK, "gates")
        self.gm = __import__("gatemarks")

    def ask(self, got=None, **kw):
        return self.g.before_fix(rounds() if got is None else got, unattended_run=kw.pop("unattended", False),
                                 design=kw.pop("design", False), **kw)

    def test_no_plan_goes_nowhere(self):
        for got in (None, rounds(ok=False), rounds(status="nothing_owed", ok=False)):
            with self.subTest(got=got):
                out = self.g.before_fix(got, unattended_run=False, design=False)
                self.assertEqual((out["open"], out["go"], out["stop_reason"]), (False, False, ""))

    def test_clean_plan_goes_to_fix_without_the_gate(self):
        out = self.ask()
        self.assertEqual((out["open"], out["go"], out["asked"]), (False, True, []))

    def test_undecided_row_opens(self):
        out = self.ask(rounds(asks=[ask_row()]))
        self.assertTrue(out["open"])
        self.assertEqual(out["items"][0][0], "regression")
        self.assertEqual(out["asked"], [NARROW], "決め手の欄が揃わない行は訳の尾を付けずに聞く（今の gatemarks._item の呼び）")

    def test_decided_row_passes_with_its_source(self):
        """L-G18・L-G19: decided が真で why の無い行は聞かずに通し、出どころつきで passes に返す"""
        mark = {"decided_by": "https://example.org/spec#zero"}
        out = self.ask(rounds(asks=[ask_row(decided=True, mark=mark)]))
        self.assertEqual((out["open"], out["go"]), (False, True))
        self.assertEqual(out["passes"], [{"node": self.gm.GATE_NODE, "round": 1, "by": self.gm.PASSED_BY, "item": NARROW,
                                          "decided_by": mark["decided_by"]}])
        self.assertTrue(any("聞かずに通した" in x for x in self.gm.pass_lines(out["passes"])))

    def test_decided_row_with_an_axis_reason_is_asked(self):
        out = self.ask(rounds(asks=[ask_row(decided=True, mark={"decided_by": "x"}, why={"not_overkill": ["柵の印が在る"]})]))
        self.assertTrue(out["open"])
        self.assertIn("柵の印が在る", out["asked"][0])

    def test_world_deviation_is_asked_once(self):
        """keep-essence 12: 定石からの外れ（why の在る world の行）は修正前の承認ノードで人に回し、前に continue で通した同じ文は聞き直さない"""
        dev = {"source": "world", "item": 1, "text": "修正案 1 の世界の解 w-mean から外れる", "mark": {"decided_by": "依頼"},
               "why": ["依頼を出どころにした外れ"]}
        out = self.ask(rounds(deviations=[dev]))
        self.assertEqual(out["items"][0][0], self.gm.WORLD_KIND)
        again = self.ask(rounds(deviations=[dev]), answered=[{"decision": "continue", "asked": out["asked"]}])
        self.assertFalse(again["open"])
        passed = self.ask(rounds(deviations=[{**dev, "why": []}]))
        self.assertEqual((passed["open"], len(passed["passes"])), (False, 1))

    def means_row(self, rec=REC, item=1):
        """plan-review の出力 deviations の頼みの解き方の行（計画 means-answers の 3.2 の 8）"""
        mark = {"decided_by": "リポジトリの決まりが別の層に置く"}
        if rec is not None:
            mark["recommend"] = rec
        return {"source": "means", "item": item, "why": [self.gm.MEANS_WHY], "mark": mark,
                "text": f"修正案 {item} は頼みの解き方 M1「分母を直す」に従わない——リポジトリの決まりが別の層に置く"}

    def test_means_row_is_asked_with_its_push(self):
        """計画 means-answers の 3.3: source means の行は種類 means の項目になり、世界の解の尾を付けない。無人の run は役の推しで抜け、
        推しが stop か無ければ止まる"""
        out = self.ask(rounds(deviations=[self.means_row()]))
        self.assertEqual(out["items"][0][0], self.gm.MEANS_KIND)
        self.assertNotIn("世界の解:", out["asked"][0])
        self.assertIn(self.gm.MEANS_WHY, out["asked"][0])
        self.assertEqual(out["items"][0][1]["recommend"], REC, "推しは項目の行の欄 recommend に在る")
        self.assertNotIn(self.gm.PUSH, out["asked"][0], "文には推しの尾が無い")
        got = self.ask(rounds(deviations=[self.means_row()]), unattended=True)
        self.assertTrue(got["go"])
        self.assertEqual(got["pushed"]["pushed"][0]["answer"], "continue")
        for rec in (STOP_REC, None):
            with self.subTest(rec=rec):
                got = self.ask(rounds(deviations=[self.means_row(rec)]), unattended=True)
                self.assertFalse(got["go"])
        again = self.ask(rounds(deviations=[self.means_row()]), answered=[{"decision": "continue", "asked": out["asked"]}])
        self.assertFalse(again["open"])

    def test_means_departure_is_asked_when_the_review_fell(self):
        """事前審査が諦めた・落ちた周も、計画の {means, deviation} は推しなしの項目として出る（無人の run は止まる）"""
        fields = [{"structure": [{"means": "M1", "deviation": "リポジトリの決まりが別の層に置くと決めている"}]}]
        got = rounds(review_status="gave_up", review_reason="受け付けが諦めた")
        out = self.ask(got, plan_fields=fields, means=["分母を len(xs) にする"])
        kinds = [k for k, _ in out["items"]]
        self.assertIn(self.gm.MEANS_KIND, kinds)
        row = dict(out["items"])[self.gm.MEANS_KIND]
        self.assertTrue(row["text"].startswith("修正案 1 は頼みの解き方 M1「分母を len(xs) にする」に従わない——"), row["text"])
        self.assertNotIn("recommend", row, "計画の欄から組む行は推しの欄を持たない")
        self.assertFalse(self.ask(got, plan_fields=fields, means=["分母を len(xs) にする"], unattended=True)["go"])
        self.assertNotIn(self.gm.MEANS_KIND, [k for k, _ in self.ask(rounds(), plan_fields=fields, means=["x"])["items"]],
                         "事前審査が通った周は計画の欄から組まない（事前審査の deviations が持つ）")

    RX = {"u1": ["分母を len(xs) にする", "上限の枝を hi にする"]}

    def prescription_row(self, rec=REC, item=1):
        """plan-review の出力 deviations の判定の処方からの外れの行"""
        mark = {"decided_by": "リポジトリの決まりが別の層に置く"}
        if rec is not None:
            mark["recommend"] = rec
        return {"source": "prescription", "item": item, "why": ["判定の処方と計画の決め手が別の答えを指す"], "mark": mark,
                "text": f"修正案 {item} は単位 u1 の判定の処方「1. 分母を len(xs) にする / 2. 上限の枝を hi にする」に従わない——"
                        "リポジトリの決まりが別の層に置く"}

    def test_prescription_row_is_always_asked_with_its_push(self):
        """source prescription の行は、決め手 decided_by が在っても passes に入らず、種類 prescription の項目になる。項目の文は判定の処方の
        文を含み、世界の解の尾を付けない。無人の run は continue の推しで進み、stop の推しか推しが無ければ止まる。前に continue で通した
        同じ文は聞き直さない"""
        out = self.ask(rounds(deviations=[self.prescription_row()]))
        self.assertTrue(out["open"], out)
        self.assertEqual(out["passes"], [])
        self.assertEqual(out["items"][0][0], "prescription")
        self.assertEqual(out["items"][0][0], self.gm.PRESCRIPTION_KIND)
        self.assertIn("1. 分母を len(xs) にする", out["asked"][0])
        self.assertNotIn("世界の解:", out["asked"][0])
        self.assertEqual(out["items"][0][1]["recommend"], REC, "推しは項目の行の欄 recommend に在る")
        self.assertNotIn(self.gm.PUSH, out["asked"][0], "文には推しの尾が無い")
        got = self.ask(rounds(deviations=[self.prescription_row()]), unattended=True)
        self.assertTrue(got["go"])
        self.assertEqual(got["pushed"]["pushed"][0]["answer"], "continue")
        for rec in (STOP_REC, None):
            with self.subTest(rec=rec):
                self.assertFalse(self.ask(rounds(deviations=[self.prescription_row(rec)]), unattended=True)["go"])
        again = self.ask(rounds(deviations=[self.prescription_row()]), answered=[{"decision": "continue", "asked": out["asked"]}])
        self.assertFalse(again["open"])

    def test_prescription_departure_is_asked_when_the_review_fell(self):
        """事前審査が諦めた・落ちた周も、計画の {prescription, deviation} は推しなしの項目として出る。文は引数 prescriptions の処方の文を
        含み、引数に単位が無ければ読めていないと名乗る。無人の run は止まる。事前審査が通った周は計画の欄から組まない"""
        fields = [{"structure": [{"prescription": "u1", "deviation": "リポジトリの決まりが別の層に置くと決めている"}]}]
        got = rounds(review_status="gave_up", review_reason="受け付けが諦めた")
        self.assertIn("prescription", [k for k, _ in self.ask(got, plan_fields=fields)["items"]], "処方の文を渡さなくても項目は出る")
        out = self.ask(got, plan_fields=fields, prescriptions=self.RX)
        row = dict(out["items"]).get("prescription", {})
        text = row.get("text", "")
        self.assertIn("1. 分母を len(xs) にする", text, out["items"])
        self.assertTrue(text.startswith("修正案 1 は単位 u1 の判定の処方"), text)
        self.assertNotIn("recommend", row, "計画の欄から組む行は推しの欄を持たない")
        self.assertFalse(self.ask(got, plan_fields=fields, prescriptions=self.RX, unattended=True)["go"])
        unread = dict(self.ask(got, plan_fields=fields, prescriptions={})["items"]).get("prescription", {}).get("text", "")
        self.assertIn("判定の処方の文を読めていない", unread)
        self.assertNotIn("prescription", [k for k, _ in self.ask(rounds(), plan_fields=fields, prescriptions=self.RX)["items"]],
                         "事前審査が通った周は計画の欄から組まない（事前審査の deviations が持つ）")

    def design_row(self, **over):
        return {"route": self.g.structmark.ROUTE_UP, "unit_id": "u1", "undecided_because": "2 つの形が割れる",
                "rejected": [{"option": "案B", "cost": "呼び手が増える"}], "chosen": "案A", "chosen_reason": "呼び手が前提にしている", **over}

    def test_unattended_design_row_whose_reason_ends_with_a_push_tail_stops(self):
        """#1014: 構造の目が人に上げた設計の行の採った案の訳の末尾が推しの尾の形でも、無人の run は推しで越えず works:needs-human で止まる。
        載せなかった行は推しの欄を持たず、その行の下書きの text は空"""
        tail = self.gm._push({self.gm.RECOMMEND: REC})
        out = self.ask(rounds(), unattended=True, design_rows_=[self.design_row(chosen_reason="呼び手が前提にしている" + tail)])
        self.assertEqual((out["open"], out["go"], out["stop_reason"], out["pushed"]), (False, False, "works:needs-human", None))
        [held] = out["deferred"]
        self.assertTrue(held["text"].startswith(self.gm.DESIGN_HEAD), held)
        self.assertNotIn("recommend", held, "設計の行は推しの欄を持たない")
        draft = self.gm.item_draft(held["text"], self.gm.GATE_NODE, recommend=held.get("recommend"))
        self.assertEqual(draft["text"], "")

    def test_pushed_row_carries_its_recommend_in_the_field_not_in_the_text(self):
        """事前審査の役が欄 recommend に通す推しを書いた行は、無人の run で推しで越える。見せた文（asked）は推しの尾の無い本文の字の並びで、
        pushed の各行の item はその本文、note・why は 1 行に畳まれた字になる"""
        rec = {"answer": "continue", "note": "空の列は 0 を返す\n形で／通す", "why": "呼び手が\n0 を前提に書かれている"}
        out = self.ask(rounds(asks=[ask_row(mark={"recommend": rec})]), unattended=True)
        self.assertEqual((out["go"], out["asked"]), (True, [NARROW]))
        [row] = out["pushed"]["pushed"]
        self.assertEqual((row["item"], row["answer"]), (NARROW, "continue"))
        self.assertEqual((row["note"], row["why"]), (self.gm._tail_text(rec["note"]), self.gm._tail_text(rec["why"])))
        self.assertNotIn("\n", row["note"] + row["why"] + out["pushed"]["text"])
        self.assertNotIn(self.gm.PUSH, out["asked"][0])

    def shown(self, out) -> list:
        asking = {"node": self.gm.GATE_NODE, "question": "q", "items": [r for _, r in out["items"]], "kinds": [k for k, _ in out["items"]]}
        return self.gm.gate_text(asking, run_id="r", node=self.gm.GATE_NODE, record_name="r").splitlines()

    def test_gate_head_push_is_not_cut_from_the_middle_of_a_role_text(self):
        """人の居る run の承認ノードの冒頭の推しの行は、行の欄からだけ組む。審査役の文の途中に「推し: …」が在っても、その切れ端は出ない"""
        middle = NARROW + "（割れる。推し: 案A——訳（審査役の字の途中）。ほかに案B が在る）"
        out = self.ask(rounds(asks=[ask_row(text=middle)]))
        lines = self.shown(out)
        self.assertIn("- " + middle, lines, "文は本文のまま並ぶ")
        self.assertEqual([x for x in lines if x.startswith(self.gm.PUSH)], [self.gm.PUSH + self.gm.NO_PUSH])
        pushed = self.ask(rounds(asks=[ask_row(mark={"recommend": REC})]))
        self.assertIn(self.gm.PUSH + "通す（continue）——空の列は 0 を返す形で通す（理由: 呼び手が 0 を前提に書かれている）", self.shown(pushed))

    def test_design_row_chosen_keeps_showing_in_the_head_and_item_line(self):
        """設計の行の構造の目が採った案は、項目の行に CHOSEN_HEAD の後ろで出て、冒頭の推しの行にも「構造の目が採った案: …」で出る。機械が検めた推しの
        子の行は出さず、抜け方も下書きも採った案を推しと読まない。採った案が無い行は NO_CHOSEN で、推しに数えない"""
        out = self.ask(rounds(), design_rows_=[self.design_row()])
        lines = self.shown(out)
        [item] = [x for x in lines if x.startswith("- " + self.gm.DESIGN_HEAD)]
        self.assertIn(self.gm.CHOSEN_HEAD + "案A（呼び手が前提にしている）", item)
        self.assertEqual([x for x in lines if x.startswith(self.gm.PUSH)], [self.gm.PUSH + self.gm.CHOSEN + "案A（呼び手が前提にしている）"])
        self.assertFalse(any(x.startswith(self.gm.MACHINE_PUSH) for x in lines))
        draft = self.gm.item_draft(out["items"][0][1]["text"], self.gm.GATE_NODE, recommend=None)
        self.assertEqual(draft["text"], "")
        bare = self.ask(rounds(), design_rows_=[self.design_row(chosen="", chosen_reason="")])
        self.assertIn(self.gm.CHOSEN_HEAD + self.gm.NO_CHOSEN, bare["items"][0][1]["text"])
        self.assertEqual([x for x in self.shown(bare) if x.startswith(self.gm.PUSH)], [self.gm.PUSH + self.gm.NO_PUSH])

    def test_deviation_of_an_unknown_source_is_asked(self):
        """表に無い source の外れの行は黙って捨てずに承認ノードの項目になる。source design の行は事前審査の穴の道で聞くので項目にしない"""
        odd = {**self.prescription_row(), "source": "elsewhere", "text": "修正案 1 は知らない種類の外れ"}
        out = self.ask(rounds(deviations=[odd]))
        self.assertTrue(out["open"], out)
        self.assertEqual(out["passes"], [])
        self.assertIn("修正案 1 は知らない種類の外れ", out["asked"][0])
        self.assertEqual(out["items"][0][0], self.gm.OTHER_DEPART_KIND)
        design = {"source": "design", "key": "d1", "kind": "contract_drift", "why": "独立設計との構造の食い違い: x"}
        self.assertFalse(self.ask(rounds(deviations=[design]))["open"])

    def test_route_up_rows_of_the_structure_eye_are_asked(self):
        row = {"unit_id": "u1", "route": "人に上げる", "undecided_because": "2 つの形が割れる", "chosen": "A"}
        out = self.ask(design_rows_=[row])
        self.assertEqual(out["items"][0][0], self.gm.DESIGN_KIND)
        self.assertTrue(out["asked"][0].startswith(self.gm.DESIGN_HEAD))

    def test_policy_change_is_asked_and_named(self):
        out = self.ask(policy_row="人の方針の文書 p.md が固定した版から変わった")
        self.assertEqual((out["open"], out["items"][0][0], out["policy_changed"]), (True, self.g.POLICY_CHANGED, True))

    def test_design_only_always_opens_with_one_row(self):
        out = self.ask(design=True)
        self.assertEqual([k for k, _ in out["items"]], [self.gm.DESIGN_ONLY_KIND])
        self.assertEqual(out["asked"], [self.gm.DESIGN_ONLY_ITEM])

    def test_stalled_has_one_row_with_the_reason(self):
        """L-D19・P249: 止まった往復は計画が ok でなくても開き、設計だけの種類の行を 1 行（止まった理由を尾に）。同じ種類の行が既に在れば足さない"""
        got = rounds(ok=False, stalled=True)
        out = self.ask(got, stuck_reason="同じ block が続いた")
        self.assertEqual(out["asked"], [f"{self.gm.STUCK_ITEM}。理由: 同じ block が続いた"])
        both = self.ask(got, design=True, stuck_reason="同じ block が続いた")
        self.assertEqual(len(both["asked"]), 1)
        self.assertTrue(both["asked"][0].startswith(self.gm.DESIGN_ONLY_ITEM))

    def stuck_doc(self, note: str, answer: str = "continue") -> dict:
        """項目 1 が開いたまま key-a1 が続いて止まった往復の記録（最後の往復の行に、事前審査の役の通す推し note）"""
        conv = __import__("converge")
        row = {"blocks": ["key-a1"], "faces": [{"key": "key-a1", "kind": "regression", "where": "a.py:1", "why": "w"}],
               "items": [{"n": 1, "state": conv.OPEN, "blocks": ["key-a1"]}]}
        return {"outcome": conv.PERSISTED, "passes": [
            {"pass": 1, **row, "persists": []},
            {"pass": 2, **row, "persists": ["key-a1"], "push": {"answer": answer, "note": note, "why": "端の穴だけが残った"}}]}

    def stalled_unattended(self, note: str, answer: str = "continue") -> dict:
        return self.ask(rounds(ok=False, stalled=True), unattended=True, stuck_reason="同じ block が続いた",
                        record_doc=self.stuck_doc(note, answer))

    def test_unattended_stuck_push_quoting_the_item_as_the_prompt_says_goes(self):
        """止まった案の推しの note が、事前審査の指示の md に渡す項目の引用の字（converge.ITEM_CITE。md の差し込み口 {item_cite}）で
        項目を引けば、無人の run は推しで修正へ進む。指示の字と照らしの字が食い違うと（前は md が "item n"・照らしが『項目 n』）推しは捨てられる"""
        cite = __import__("converge").ITEM_CITE.format(n=1)
        out = self.stalled_unattended(f"key-a1 は {cite} の修正の中で片付ける")
        self.assertEqual((out["go"], out["stop_reason"]), (True, ""), out)

    def test_unattended_stuck_push_dropped_for_a_missing_quote_says_so(self):
        """通す推しを引用の欠けだけで捨てた時は、止めた行（報告と次の依頼の下書きへ行く）に捨てた訳と欠けた字を出し、黙って落とさない"""
        out = self.stalled_unattended("key-a1 は item 1 の修正の中で片付ける")
        self.assertEqual((out["go"], out["stop_reason"]), (False, __import__("stopby").NEEDS_HUMAN))
        cite = __import__("converge").ITEM_CITE.format(n=1)
        self.assertEqual([r["text"] for r in out["deferred"]], [f"{self.gm.STUCK_ITEM}。理由: 同じ block が続いた" + self.g.CITE_DROPPED.format(missing=cite)])
        self.assertIn(f"推しは在ったが引用が欠けた（欠け: {cite}）", out["deferred"][0]["text"])
        stopped = self.stalled_unattended("key-a1 は直しの中で片付かない", answer="stop")
        self.assertNotIn("引用が欠けた", stopped["deferred"][0]["text"], "止める推しは引用の欠けで捨てた物でない")

    def test_unattended_stops_where_the_gate_would_open(self):
        out = self.ask(rounds(asks=[ask_row()]), unattended=True)
        self.assertEqual((out["open"], out["go"], out["stop_reason"]), (False, False, __import__("stopby").NEEDS_HUMAN))

    def test_unattended_design_only_stops(self):
        out = self.ask(design=True, unattended=True)
        self.assertEqual((out["open"], out["go"]), (False, False))

    def test_unattended_takes_the_push_when_every_item_pushes_continue(self):
        out = self.ask(rounds(asks=[ask_row(mark={"recommend": REC})]), unattended=True)
        self.assertEqual((out["open"], out["go"], out["stop_reason"]), (False, True, ""))
        self.assertEqual(out["pushed"]["decision"], "continue")
        self.assertEqual(len(out["asked"]), 1)

    def test_unattended_stops_when_a_push_stops_or_is_missing(self):
        for marks in ([{"recommend": STOP_REC}], [{"recommend": REC}, {}]):
            with self.subTest(marks=marks):
                out = self.ask(rounds(asks=[ask_row(mark=m) for m in marks]), unattended=True)
                self.assertEqual((out["go"], out["pushed"]), (False, None))

    def test_attended_run_opens_the_gate_even_with_pushes(self):
        out = self.ask(rounds(asks=[ask_row(mark={"recommend": REC})]))
        self.assertEqual((out["open"], out["pushed"]), (True, None))

    def test_unattended_stops_on_policy_change_rows(self):
        """方針の文書の変化の行は推しを持たないので、無人の run は止まる（機械は推しを作らない。L-G24）"""
        out = self.ask(policy_row="人の方針の文書 p.md が固定した版から変わった", unattended=True)
        self.assertEqual((out["go"], out["pushed"]), (False, None))


class PointedAskCase(unittest.TestCase):
    """版に無い名指しの文書（持ち主の決め pointed-ask。受付 9d05bd の問い 4 の B）: 人の居る run は修正前の承認ノードで問う。ほかの版にだけ
    在る文書は従ってよいかを聞いて開き、どの版にも無い文書は推し「気にせず進む」つきで並べるだけ（それだけでは開かない）。無人の run は
    項目にせず、報告の行だけ（ゲートの抜け方は今のまま）"""

    CANON = {"path": "docs/canon.md", "found": True, "at": "canon"}
    GONE = {"path": "tests/new_case.py", "found": False, "at": ""}
    RULE = {"path": "docs/deploy.adoc", "by": "AGENTS.md", "found": True, "at": "remotes/origin/canon"}

    def setUp(self):
        self.g = kit.load(BLOCK, "gates")
        self.gm = __import__("gatemarks")

    def ask(self, got=None, **kw):
        return self.g.before_fix(rounds() if got is None else got, unattended_run=kw.pop("unattended", False),
                                 design=kw.pop("design", False), **kw)

    def test_a_document_only_on_another_branch_opens_the_gate(self):
        out = self.ask(rounds(pointed=[self.CANON]), pointed=[self.RULE])
        self.assertEqual((out["open"], out["go"]), (True, True))
        self.assertEqual([k for k, _ in out["items"]], [self.gm.POINTED_KIND, self.gm.POINTED_KIND])
        canon, rule = out["asked"]
        self.assertIn("docs/canon.md", canon)
        self.assertIn(f"{self.g.POINTED_BY_ANSWER}が名指す docs/canon.md", canon)
        self.assertIn("canon", canon)
        self.assertTrue(rule.startswith("AGENTS.md が名指す docs/deploy.adoc"), rule)
        self.assertNotIn("recommend", out["items"][0][1], "従ってよいかは人が決める（機械は推しを作らない）")

    def test_a_document_in_no_version_alone_does_not_open(self):
        out = self.ask(rounds(pointed=[self.GONE]))
        self.assertEqual((out["open"], out["go"], out["asked"]), (False, True, []))

    def test_a_document_in_no_version_is_listed_with_the_push_to_go_on(self):
        out = self.ask(rounds(pointed=[self.GONE], asks=[ask_row()]))
        self.assertTrue(out["open"])
        self.assertEqual(out["items"][-1][0], self.gm.POINTED_MISSING_KIND)
        rec = out["items"][-1][1]["recommend"]
        self.assertEqual((rec["answer"], rec["note"]), ("continue", "気にせず進む"))
        self.assertIn("tests/new_case.py", out["asked"][-1])
        self.assertNotIn(self.gm.PUSH, out["asked"][-1], "asked の文には推しの尾が無い")

    def test_an_answered_row_is_not_asked_again(self):
        first = self.ask(rounds(pointed=[self.CANON]))
        again = self.ask(rounds(pointed=[self.CANON]), answered=[{"decision": "continue", "asked": first["asked"]}])
        self.assertEqual((again["open"], again["go"]), (False, True))

    def test_unattended_run_keeps_its_way_through_the_gate(self):
        """無人の run は名指しを項目にしない（報告の行だけ）。推しで抜ける・止まるは名指しの無い run と同じ"""
        for got in (rounds(pointed=[self.CANON, self.GONE]), rounds(pointed=[self.CANON], asks=[ask_row(mark={"recommend": REC})])):
            with self.subTest(got=got):
                bare = self.ask({**got, "pointed": []}, unattended=True)
                out = self.ask(got, unattended=True, pointed=[self.RULE])
                self.assertEqual((out["open"], out["go"], out["stop_reason"], out["asked"], out["deferred"]),
                                 (bare["open"], bare["go"], bare["stop_reason"], bare["asked"], bare["deferred"]))

    def test_structure_state_rows_are_read(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        state = tmp / "state.json"
        for doc, want in (({"status": "ok", "design_file": "", "pointed": [self.RULE, "x"]}, [self.RULE]),
                          ({"status": "failed", "reason": "落ちた", "design_file": ""}, [])):
            with self.subTest(doc=doc):
                state.write_text(json.dumps(doc), encoding="utf-8")
                self.assertEqual(self.g.structure_pointed(str(state)), want)
        self.assertEqual(self.g.structure_pointed(""), [])

    def test_report_lines_name_the_documents_of_the_answers(self):
        sections = kit.load(BLOCK, "sections")
        lines = sections.rounds_lines(rounds(pointed=[self.CANON, self.GONE]))
        self.assertTrue(any("docs/canon.md" in x and "canon" in x for x in lines), lines)
        self.assertTrue(any("tests/new_case.py" in x and "どの版にも無く" in x for x in lines), lines)


class DesignRowsCase(unittest.TestCase):
    """design_rows: 控えが無い・落ちた周は空、壊れた控えは読めないと名指して止まる（空の一覧で設計の問いを黙って消さない）"""

    def setUp(self):
        self.g = kit.load(BLOCK, "gates")
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def state(self, text: str, name="state.json") -> str:
        path = self.tmp / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_no_pointer_and_failed_state_are_empty(self):
        self.assertEqual(self.g.design_rows(""), [])
        failed = self.state(json.dumps({"status": "failed", "reason": "落ちた", "design_file": ""}))
        self.assertEqual(self.g.design_rows(failed), [])

    def test_ok_state_gives_its_rows(self):
        design = self.state('{"unit_id": "u1"}\n', "design.jsonl")
        ok = self.state(json.dumps({"status": "ok", "design_file": design}))
        self.assertEqual(self.g.design_rows(ok), [{"unit_id": "u1"}])

    def test_broken_state_is_named_not_emptied(self):
        for text in ("{not json", json.dumps({"status": "weird"})):
            with self.subTest(text=text), self.assertRaises(ValueError) as caught:
                self.g.design_rows(self.state(text))
            self.assertIn("state.json", str(caught.exception))

    def test_broken_design_file_is_named_not_emptied(self):
        design = self.state("not json\n", "design.jsonl")
        ok = self.state(json.dumps({"status": "ok", "design_file": design}))
        with self.assertRaises(ValueError) as caught:
            self.g.design_rows(ok)
        self.assertIn("設計の行", str(caught.exception))


class LedgerAsksCase(unittest.TestCase):
    """問いの台帳の問い（gatemarks.ledger の値の見え方）: 人の居る run は項目に、無人の run は deferred へ（L-G33・L-G38・L-G41）"""
    FORK = {"key": "q-a", "kind": "fork", "status": "held", "origin": "u1", "options": ["x", "y"], "reason": "割れる"}

    def setUp(self):
        self.g = kit.load(BLOCK, "gates")
        self.gm = __import__("gatemarks")

    def ledger(self, answers=(), takes_push=False):
        doc = {"units": [{"key": "u1", "label": "block"}], "questions": [self.FORK]}
        return self.gm.ledger(doc, answers=list(answers), takes_push=takes_push)

    def test_attended_run_asks_the_ledger_question(self):
        out = self.g.before_fix(rounds(), unattended_run=False, design=False, ledger=self.ledger())
        self.assertTrue(out["open"])
        self.assertEqual(out["items"][0][0], self.gm.ASK_KINDS[0])
        self.assertTrue(out["asked"][0].startswith(self.gm.ASK_HEAD))

    def test_unattended_run_defers_the_question(self):
        out = self.g.before_fix(rounds(), unattended_run=True, design=False, ledger=self.ledger(takes_push=True))
        self.assertEqual((out["open"], out["go"], len(out["deferred"])), (False, True, 1))

    def test_answered_question_is_not_asked(self):
        out = self.g.before_fix(rounds(), unattended_run=False, design=False,
                                ledger=self.ledger(answers=[{"question": "q-a", "text": "x"}]))
        self.assertFalse(out["open"])

    def test_a_deferred_ledger_question_keeps_its_title(self):
        """無人の run で載せなかった台帳の問いは deferred に {text, title} の行で返り、題は台帳の問いの title（2 行は 1 行に畳む。題が無ければ
        title の欄も無い）。機械が組んだ項目（推しで抜けられずに止めた行）の行の題は gatemarks.KIND_WORDS の種類の言い方"""
        titled = {**self.FORK, "title": "空の列で\n例外を投げるか決める"}
        bare = {**self.FORK, "key": "q-b"}
        doc = {"units": [{"key": "u1", "label": "block"}], "questions": [titled, bare]}
        out = self.g.before_fix(rounds(), unattended_run=True, design=False, ledger=self.gm.ledger(doc, takes_push=True))
        self.assertEqual(out["deferred"], [{"text": self.gm.ask_text(titled), "title": "空の列で 例外を投げるか決める"}, {"text": self.gm.ask_text(bare)}])
        stopped = self.g.before_fix(rounds(asks=[ask_row()]), unattended_run=True, design=False, ledger=self.gm.ledger(doc, takes_push=True))
        self.assertFalse(stopped["go"])
        self.assertEqual(stopped["deferred"][2:], [{"text": NARROW, "title": self.gm.KIND_WORDS["regression"]}], "止めた機械の項目の題は種類の言い方")
        self.assertEqual(stopped["deferred"][:2], out["deferred"])
        for kind in (self.gm.UNREAD_KIND, self.gm.AXIS_KIND, self.gm.POINTED_KIND, self.gm.POINTED_MISSING_KIND):
            self.assertIn(kind, self.gm.KIND_WORDS, "gates が組む種類は題の出どころ KIND_WORDS に在る")

    def test_a_push_the_copied_plan_counted_is_named(self):
        """直す前で止まった無人の run の写しを人の居る run で続ける時（planned は写しの計画が数えた推しの台帳）: 推しを答えに数えて組んだ
        計画だと問いの行に名指し、推しと違う答えなら止めて計画から回し直すと案内する。推しを数えていない計画（planned が None）は今どおり"""
        fork = {**self.FORK, "reason": "割れる。推し: x——帰結が狭い"}
        doc = {"units": [{"key": "u1", "label": "block"}], "questions": [fork]}
        planned = self.gm.ledger(doc, takes_push=True)
        self.assertEqual(self.gm.run_push(planned, fork), "x——帰結が狭い")
        out = self.g.before_fix(rounds(), unattended_run=False, design=False, ledger=self.gm.ledger(doc), planned=planned)
        self.assertTrue(out["open"])
        self.assertIn(self.g.PLANNED_PUSH.format(push="x——帰結が狭い"), out["asked"][0])
        plain = self.g.before_fix(rounds(), unattended_run=False, design=False, ledger=self.gm.ledger(doc))
        self.assertNotIn("計画は", plain["asked"][0])


class GatherCase(unittest.TestCase):
    """元 test_gate_axes.py の GatherCase（軸ごとの訳は事前審査の返りの行の why から）"""

    def setUp(self):
        self.g = kit.load(BLOCK, "gates")

    def test_no_rows_is_all_ok(self):
        self.assertEqual(self.g.gather([], [], []), {a: {"ok": True, "note": ""} for a in self.g.AXES})

    def test_rows_name_their_text(self):
        got = self.g.gather([ask_row(decided=True, why={"not_overkill": ["柵の印が在る"]})], [], [])
        self.assertEqual(sorted(a for a, v in got.items() if not v["ok"]), ["not_overkill"])
        self.assertIn(NARROW, got["not_overkill"]["note"])

    def test_world_deviation_and_route_up_rows(self):
        dev = {"source": "world", "text": "修正案 1 の w-mean から外れる", "why": ["依頼を出どころにした外れ"]}
        got = self.g.gather([], [dev, {"source": "design", "key": "k", "why": "x"}], [("design", "構造の目が決めきれない設計の問い u1")])
        self.assertFalse(got["world"]["ok"])
        self.assertIn("w-mean", got["world"]["note"])
        self.assertFalse(got["clean"]["ok"])


class ReplanAsksCase(unittest.TestCase):
    def setUp(self):
        self.g = kit.load(BLOCK, "gates")

    def test_contract_change_or_human_face_asks(self):
        rows = [{"item": 1, "contract_changed": ["allowed_paths"], "human": [], "widened": None},
                {"item": 2, "contract_changed": [], "human": [{"key": "k", "kind": "regression", "why": "w"}], "widened": None},
                {"item": 3, "contract_changed": [], "human": [], "widened": None}]
        self.assertEqual([r["item"] for r in self.g.replan_asks(rows, unattended_run=False)], [1, 2])

    def test_unattended_widen_only_is_not_asked(self):
        row = {"item": 1, "contract_changed": ["allowed_paths"], "human": [], "widened": {"added": ["src/**"], "removed": []}}
        self.assertEqual(self.g.replan_asks([row], unattended_run=True), [])
        self.assertEqual(len(self.g.replan_asks([row], unattended_run=False)), 1)

    def test_unreadable_row_is_asked(self):
        self.assertEqual(len(self.g.replan_asks(["x", {"contract_changed": []}], unattended_run=False)), 2)


class ReviewVerdictCase(unittest.TestCase):
    """独立の目の port review（修正が使った案を審査した最後の往復の結論）"""

    def setUp(self):
        self.g = kit.load(BLOCK, "gates")

    def record(self, outcome, faces=()):
        return {"round": 1, "outcome": outcome, "passes": [{"pass": 1, "faces": list(faces), "blocks": [f["key"] for f in faces]}]}

    def test_verdicts(self):
        self.assertEqual(self.g.review_verdict(self.record("clean"), round_=1)["verdict"], "accepted")
        blocked = self.g.review_verdict(self.record("persisted", [{"key": "k", "why": "w"}]), round_=1)
        self.assertEqual((blocked["verdict"], blocked["blocks"]), ("blocked", [{"key": "k", "why": "w"}]))
        self.assertEqual(self.g.review_verdict(self.record("unsettled"), round_=1)["verdict"], "held")
        self.assertEqual(self.g.review_verdict(None, round_=1)["verdict"], "unread")

    def test_review_of_another_plan_round_is_not_accepted(self):
        """今の test_plan_review_of_another_plan_round_is_not_accepted の能力: 往復と案の周が組まなければ unread"""
        got = self.g.review_verdict(self.record("clean"), round_=2)
        self.assertEqual(got["verdict"], "unread")
        self.assertIn("pass-1", got["why"])

    def test_replan_review_wins(self):
        got = self.g.review_verdict(self.record("clean"), round_=1, replan_review={"status": "ok", "round": 1, "blocks": [{"key": "b"}]})
        self.assertEqual(got["verdict"], "blocked")


def final_got(final, **over) -> dict:
    """最後の承認ノードの材料（src.final.gather の返りの形）。既定は全部通った run"""
    got = {"tests_ok": True, "green": True, "red_cause": "", "ran_steps": None,
           "tests": {"by": "test_cmd", "suites": "test_cmd・1 本", "log": "log.txt", "baseline": "直す前: 緑", "reason": "", "unread": ""},
           "worktree": "/w", "base_rev": "abc", "deliver_pr": False, "protected_hits": [], "protected_count": 0, "asked": [],
           "conflicts_unread": [], "handoffs": [], "mismatched": [],
           "eyes": {"r1": {"status": "pass", "reason": ""}, "r2": {"status": "pass", "reason": ""}, "r3": {"status": "pass", "reason": ""},
                    "r4": {"status": "pass", "reason": ""}, "premise_check": None},
           "questions": [], "means_questions": [], "spec_changed": [], "spec_unchecked": False, "objection": "", "rejudge_verdict": "", "rejudge": [],
           "split": "", "unproven": [], "amend": [], "delta": [], "stuck": [], "closure": [], "tests_left": [], "gates": [], "always": [],
           "beside_unread": [], "allowed_tests": [], "allowed_untouched": 0, "removed_tests": [], "untested": [], "unsatisfied": [], "structure_missing": "", "sealed": True, "seal_reason": "",
           "hash": "h", "deleted": [], "sealed_diff": "", "fenced": [], "after": [], "passes": [], "r2_inputs": [], "converge": [],
           "parallel_after": None, "held": [], "answered": [], "unmatched": [], "unread_holds": [], "lost_ties": [], "unread": [],
           "eyes_back": {"rows": [], "exit": "返す物が無い", "left": []},   # 独立の目から修正の段へ返さずに抜けた輪の記録
           "back_restore": None}   # 封じる前の戻しの結末（戻す節が飛んだ run は null）
    return {**got, **over}


class AskFinalCase(unittest.TestCase):
    def setUp(self):
        self.f = kit.load(BLOCK, "final")

    def ask(self, got, mode="", unattended=False):
        return self.f.ask(got, mode=mode, unattended=unattended, run_id=RUN)

    def test_always_is_the_default(self):
        out = self.ask(final_got(self.f))
        self.assertEqual((out["open"], out["reasons"]), (True, []))
        self.assertFalse(self.ask(final_got(self.f), mode="when_needed")["open"])

    def test_protected_hits_and_conflicts_open_in_every_mode(self):
        """keep-essence 10・8: 守りのパスの当たりと人に回した申し出は開き方に依らず開く"""
        for over in ({"protected_hits": ["lib/protected.json"], "protected_count": 1}, {"asked": ["申し出 c1"]},
                     {"spec_changed": ["受け入れ条件のテストが変わった"]}, {"allowed_tests": [{"path": "t.py", "permit": "p1", "source": "案"}]},
                     {"conflicts_unread": ["x"]}, {"beside_unread": ["y"]}):
            for mode in ("when_needed", "protected_only"):
                with self.subTest(over=over, mode=mode):
                    self.assertTrue(self.ask(final_got(self.f, **over), mode=mode)["open"])

    def test_tests_fixed_along_the_way_are_their_own_must_reason_and_section(self):
        """#836: 関わる試験で直す前から壊れていた物を修正役が直した行（許しの出どころ broken）は「ついでに直した試験」として、
        書き換えを許したテストと分けて開ける理由（must）と節に出す"""
        along = {"path": "tests/test_a.py", "permit": "broken-before-1", "source": "broken"}
        got = final_got(self.f, allowed_tests=[along])
        why = self.f.needs(got)
        self.assertIn((f"{self.f.ALONG_HEAD}が在る（1 件。人の確かめが要る）", True), why)
        self.assertFalse(any(self.f.ALLOWED_TESTS_HEAD in w for w, _ in why), why)
        self.assertTrue(self.ask(got, mode="protected_only")["open"])
        text = self.f.final_text(got, self.f.final_needs(got), RUN)
        self.assertIn(f"## {self.f.ALONG_HEAD}（1 件。", text)
        self.assertIn("- tests/test_a.py（許し broken-before-1）", text)
        self.assertNotIn(f"## {self.f.ALLOWED_TESTS_HEAD}", text)

    BACK_ROWS = [{"round": 1, "r1": "fix-needed", "r2": "pass", "items": [{"eye": "r1", "where": "src/a.py:12", "text": "写しが残っている"}]},
                 {"round": 2, "r1": "fix-needed", "r2": "fix-needed", "items": [{"eye": "r1", "where": "src/a.py:12", "text": "写しがまだ残っている"},
                                                                                 {"eye": "r2", "where": "", "text": "入口が足りない"}]}]

    def test_head_counts_the_returns_and_lists_each_round(self):
        """返した周が在れば、最後の承認ノードの頭の文に返した回数が入り、本文に『独立の目から修正の段へ返した物』の節が周ごとの項目と、
        返した段が通っていない確かめの 1 行と、抜けた訳を並べる。0 回なら頭の文にも節にも出ない"""
        self.assertTrue((kit.BLOCKS / BLOCK / "src" / "eyesback.py").exists(), "周の頭の決めの src/eyesback.py が無い")
        eb = kit.load(BLOCK, "eyesback")
        got = final_got(self.f, eyes_back={"rows": self.BACK_ROWS, "exit": "返す物が無い（どの目も通った）", "left": []})
        text = self.ask(got)["text"]
        self.assertIn("独立の目から修正の段へ 2 回返した。", text.splitlines()[0])
        self.assertIn(f"## {eb.HEAD}（2 回）", text)
        words = __import__("gatemarks").REVIEW_WORDS
        for line in eb.lines(self.BACK_ROWS, "返す物が無い（どの目も通った）"):
            self.assertIn(f"- {line}", text)
        self.assertIn(f"1 周目: 返した（R1: {words['fix-needed']}・R2: {words['pass']}）——返した項目: R1: src/a.py:12: 写しが残っている", text)
        self.assertIn(eb.NOT_REVIEWED, text)
        self.assertIn("輪を抜けた訳: 返す物が無い（どの目も通った）", text)
        self.assertLess(text.index(f"## {eb.HEAD}"), text.index("最後の承認ノード（最後のテストと独立の目の後・報告の前）"))
        none = self.ask(final_got(self.f, eyes_back={"rows": [], "exit": "返す物が無い", "left": []}))["text"]
        self.assertNotIn("回返した", none)
        self.assertNotIn(eb.HEAD, none)

    def test_fallen_return_loop_is_named(self):
        """材料の eyes_back が None の run と、eyes_back の exit が『輪の節が落ちた』の run では BACK_FELL が開き方に依らず開く理由に出る。
        返す物が無くて 0 回で抜けた run ではその行も返した節も出ない"""
        self.assertTrue((kit.BLOCKS / BLOCK / "src" / "eyesback.py").exists(), "周の頭の決めの src/eyesback.py が無い")
        eb = kit.load(BLOCK, "eyesback")
        fixing = {"r1": {"status": "fix-needed", "reason": "写し"}, "r2": {"status": "pass", "reason": ""}, "r3": {"status": "pass", "reason": ""},
                  "r4": {"status": "pass", "reason": ""}, "premise_check": None}
        for record in (None, {"rows": [], "exit": eb.EXITS["fell"], "left": []}):
            with self.subTest(record=record):
                got = final_got(self.f, eyes=fixing, eyes_back=record)
                self.assertIn((self.f.BACK_FELL, True), self.f.needs(got))
                for mode in ("when_needed", "protected_only"):
                    self.assertTrue(self.ask(got, mode=mode)["open"], mode)
                unattended = self.ask(got, mode="when_needed", unattended=True)
                self.assertEqual((unattended["open"], unattended["go"], unattended["stop_reason"]), (False, False, __import__("stopby").NEEDS_HUMAN))
                text = self.ask(got)["text"]
                self.assertIn(self.f.BACK_FELL, text)
                self.assertIn("R1: 直しが要る", text, "最初の目の行は出る")
                self.assertNotIn(eb.HEAD, text, "返した周が無いので節は出ない")
        zero = final_got(self.f, eyes=fixing, eyes_back={"rows": [], "exit": "返す物が無い", "left": []})
        self.assertFalse(any(self.f.BACK_FELL in phrase for phrase in self.f.final_needs(zero)))
        self.assertNotIn(eb.HEAD, self.ask(zero)["text"])

    def test_three_round_exit_names_the_left_items_for_a_person(self):
        """3 周で抜けた run（eyesback.capped）は、開き方が protected_only でも承認ノードが必ず開き、残った作り残しを名指して人の判断に回す。
        工場の不具合・安全の上限の字は出さない。無人の run は works:needs-human で止まり、go が偽になる"""
        self.assertTrue((kit.BLOCKS / BLOCK / "src" / "eyesback.py").exists(), "周の頭の決めの src/eyesback.py が無い")
        eb = kit.load(BLOCK, "eyesback")
        left = [{"eye": "r1", "where": "src/a.py:12", "text": "写しがまだ残っている"}, {"eye": "r2", "where": "", "text": "入口が足りない"}]
        record = {"rows": [{**self.BACK_ROWS[0], "round": k} for k in (1, 2, 3)], "exit": eb.CAP_WHY, "left": left}
        got = final_got(self.f, eyes_back=record)
        phrase = eb.cap_text(left)
        self.assertIn((phrase, True), self.f.needs(got))
        self.assertIn(f"{eb.LIMIT} 周返した", phrase)
        for mode in ("when_needed", "protected_only"):
            self.assertTrue(self.ask(got, mode=mode)["open"], mode)
        text = self.ask(got, mode="protected_only")["text"]
        for word in ("R1: src/a.py:12: 写しがまだ残っている", "R2: 入口が足りない", "人が判断する"):
            self.assertIn(word, text)
        for word in ("工場の不具合", "安全の上限"):
            self.assertNotIn(word, text)
        self.assertIn("独立の目から修正の段へ 3 回返した。", text.splitlines()[0])
        out = self.ask(got, mode="protected_only", unattended=True)
        self.assertEqual((out["open"], out["go"], out["stop_reason"]), (False, False, __import__("stopby").NEEDS_HUMAN))
        self.assertFalse(any(self.f.BACK_FELL in phrase for phrase in self.f.final_needs(got)), "3 周で抜けたのは輪の節が落ちたのとは別")

    def test_failed_restore_opens_and_the_returned_section_names_the_kept_patch(self):
        """返した段が止まって返す前の状態を封じる run（eyes_back が checkpoint を持つ）では、返した周の節が封じたのが 1 周目に返す前の状態であることと
        控えのパスを言う。戻しの結末が空でない reason を持つ（戻せなかった）時は、作業ツリーが半ば戻ったかもしれないので、開き方に依らず開く理由に出す。
        戻しの結末を持たない材料は今と同じ節のまま"""
        eb = kit.load(BLOCK, "eyesback")
        left = [{"eye": "r1", "where": "src/a.py:12", "text": "写しが残っている"}]
        record = {"rows": self.BACK_ROWS[:1], "exit": f"{eb.EXITS['stop']}（修正の段の合わせが進めなかった）", "left": left,
                  "checkpoint": {"round": 1, "tree": "t1"}}
        plain = final_got(self.f)
        self.assertEqual(self.f.returned_section(plain), [])
        kept = final_got(self.f, eyes_back=record, back_restore={"restored": True, "kept": "k.patch", "reason": ""})
        text = self.f.final_text(kept, self.f.final_needs(kept), RUN)
        self.assertIn("1 周目に返す前の状態", text)
        self.assertIn("k.patch", text)
        self.assertFalse(any("返す前の状態へ戻せなかった" in why for why, _ in self.f.needs(kept)), "戻せた時は開ける理由にしない")
        failed = final_got(self.f, eyes_back=record, back_restore={"restored": False, "kept": "k.patch", "reason": eb.RESTORE_DIFFERS})
        why = self.f.needs(failed)
        self.assertTrue(any("返す前の状態へ戻せなかった" in phrase and must for phrase, must in why), why)
        for mode in ("when_needed", "protected_only"):
            self.assertTrue(self.ask(failed, mode=mode)["open"], mode)
        self.assertIn(eb.RESTORE_DIFFERS, self.ask(failed, mode="protected_only")["text"])
        self.assertIn("k.patch", self.ask(failed, mode="protected_only")["text"], "戻せなくても控えの在りかを言う")

    def test_internal_error_round_opens_and_says_the_seal_is_the_state_before_the_return(self):
        """返した周の節が中の誤りで落ちて、次の周の頭が返す前の状態を持ち越した記録（exit が輪の節が落ちた・checkpoint が在る）では、最後の承認ノードは
        開き方に依らず開き、理由に BACK_FELL を出し、返した周の節が封じに出したのが 1 周目に返す前の状態であることと、返したが直せなかった項目を言う"""
        eb = kit.load(BLOCK, "eyesback")
        left = [{"eye": "r1", "where": "src/a.py:12", "text": "写しが残っている"}]
        record = {"rows": self.BACK_ROWS[:1], "exit": eb.EXITS["fell"], "left": left, "checkpoint": {"round": 1, "tree": "t1"}}
        got = final_got(self.f, eyes_back=record, back_restore={"restored": True, "kept": "k.patch", "reason": ""})
        self.assertTrue(any(self.f.BACK_FELL in phrase and must for phrase, must in self.f.needs(got)), self.f.needs(got))
        for mode in ("when_needed", "protected_only"):
            self.assertTrue(self.ask(got, mode=mode)["open"], mode)
        text = self.f.final_text(got, self.f.final_needs(got), RUN)
        self.assertIn("1 周目に返す前の状態", text)
        self.assertIn("返したが直せなかった項目", text)
        self.assertIn("写しが残っている", text)

    def test_removed_tests_are_their_own_must_reason_and_section(self):
        """下書き 4.1 の 7・4.3: 消した試験（修正の出力の removed_tests）は開き方に依らず開ける理由と節に出し、消しただけの試験のファイルを
        「書き換えを許したテストを触った」の数えから外す（同じファイルで書き換えもした物は数えに残す）"""
        gone = {"group_id": "g1", "weapon": "remove", "units": ["u1"], "tests": ["tests/test_a.py::test_old"],
                "only_removed": ["tests/test_a.py"], "stage": "修正の段"}
        allowed = [{"path": "tests/test_a.py", "permit": "p1", "source": "案"}]
        got = final_got(self.f, removed_tests=[gone], allowed_tests=allowed)
        why = self.f.needs(got)
        self.assertIn((f"{self.f.REMOVED_TESTS_HEAD}が在る（1 件。人の確かめが要る）", True), why)
        self.assertFalse(any(self.f.ALLOWED_TESTS_HEAD in w for w, _ in why), why)
        self.assertTrue(self.ask(got, mode="protected_only")["open"])
        text = self.f.final_text(got, self.f.final_needs(got), RUN)
        self.assertIn(f"## {self.f.REMOVED_TESTS_HEAD}（1 件。", text)
        self.assertIn("- tests/test_a.py::test_old（修正の段・組 g1・型 remove・単位 u1）", text)
        self.assertNotIn(f"## {self.f.ALLOWED_TESTS_HEAD}", text)
        both = final_got(self.f, removed_tests=[{**gone, "only_removed": []}], allowed_tests=allowed)
        self.assertIn((f"{self.f.ALLOWED_TESTS_HEAD}（1 件。人の確かめが要る）", True), self.f.needs(both))

    def test_unchecked_note_is_written_once_whichever_sections_show(self):
        """下書き 4.3: 封じた差分が無い時の注記 ALLOWED_UNCHECKED は、許したテスト・ついでに直した試験・消した試験のどの組み合わせでも
        1 度だけ出る"""
        allowed = {"path": "tests/test_b.py", "permit": "p1", "source": "案"}
        along = {"path": "tests/test_c.py", "permit": "broken-before-1", "source": "broken"}
        gone = {"group_id": "g1", "weapon": "remove", "units": ["u1"], "tests": ["tests/test_a.py::test_old"],
                "only_removed": ["tests/test_a.py"], "stage": "修正の段"}
        for rows, removed in (([allowed], []), ([along], []), ([], [gone]), ([allowed, along], [gone]), ([along], [gone])):
            with self.subTest(rows=rows, removed=removed):
                got = final_got(self.f, allowed_tests=rows, removed_tests=removed, allowed_untouched=None)
                self.assertEqual(self.f.final_text(got, [], RUN).count(self.f.ALLOWED_UNCHECKED), 1)
                self.assertEqual(self.f.final_text({**got, "allowed_untouched": 0}, [], RUN).count(self.f.ALLOWED_UNCHECKED), 0)

    def test_untested_fixes_have_their_own_section_and_mark_code_files(self):
        """下書き 3.7: 試験を求めなかった直し（untested）は節に分けて訳とファイルの種類を並べ、種類 code のファイルに印を付ける。
        code を触った時だけ開き方で開く理由（must でない）"""
        row = {"group_id": "g1", "weapon": "static", "units": ["u1"], "why": "README の言い回しだけで試験で示す物が無い",
               "files": [{"path": "README.md", "kind": "docs"}], "stage": "修正の段"}
        docs = final_got(self.f, untested=[row])
        self.assertEqual(self.f.final_needs(docs), [])
        text = self.f.final_text(docs, [], RUN)
        self.assertIn(f"## {self.f.UNTESTED_HEAD}（1 件。", text)
        self.assertIn("試験を求めない訳: README の言い回しだけで試験で示す物が無い", text)
        self.assertIn("  - README.md（docs）", text)
        code = final_got(self.f, untested=[{**row, "files": [{"path": "src/a.py", "kind": "code"}]}])
        self.assertIn((f"{self.f.UNTESTED_HEAD}が{self.f.CODE_UNTESTED}（1 件）", False), self.f.needs(code))
        self.assertIn(f"  - src/a.py（code。{self.f.CODE_UNTESTED}）", self.f.final_text(code, [], RUN))
        self.assertTrue(self.ask(code, mode="when_needed")["open"])
        self.assertFalse(self.ask(code, mode="protected_only")["open"])

    def test_unsatisfied_dependencies_are_named_in_a_section_that_never_opens(self):
        """F3: 守れなかった依存（fixed の groups の行の unsatisfied）は節に対を名で並べる。止めにせず、開ける理由に数えない。無ければ節が出ない"""
        self.assertNotIn(self.f.UNSATISFIED_HEAD, self.f.final_text(final_got(self.f), [], RUN))
        rows = self.f.unsatisfied_rows([{"group_id": "g1", "unsatisfied": [{"before": "u1", "after": "u2"}]},
                                        {"group_id": "g2"}, "壊れた行"])
        self.assertEqual(len(rows), 1)
        got = final_got(self.f, unsatisfied=rows)
        text = self.f.final_text(got, [], RUN)
        self.assertIn(f"## {self.f.UNSATISFIED_HEAD}（1 件", text)
        self.assertIn("組 g1: 単位 u1 → u2", text)
        self.assertEqual(self.f.final_needs(got), [])
        self.assertFalse(self.ask(got, mode="when_needed")["open"])

    MEANS_Q = "R2: 差分は頼みの解き方 M1「集計は 1 か所」どおりだが、独立設計と食い違う——形が違う（人に聞く訳: x）／推し: 通す（continue）——そのまま（理由: 頼みどおり）"

    def test_means_questions_open_in_every_mode(self):
        """計画 means-answers の 6.3 の 4・6.5 の 5: R2 の頼みどおりの違いの問いは開き方に依らず開く理由（must）。protected_only で
        守りのパスに当たらなくても開く"""
        got = final_got(self.f, means_questions=[self.MEANS_Q])
        for mode in ("when_needed", "protected_only", "always"):
            with self.subTest(mode=mode):
                self.assertTrue(self.ask(got, mode=mode)["open"])
        self.assertIn(("頼みの解き方どおりの違いを独立の目が聞いている（1 件）", True), self.f.needs(got))

    MEANS_BODY = MEANS_Q.split("／推し:")[0]
    MEANS_REC = {"answer": "continue", "note": "そのまま通す", "why": "頼みどおりだから"}

    def means_rows(self, *answers):
        """R2 の問いの行（文に推しの尾は書かず、推しは欄 recommend が運ぶ）"""
        return [{"text": self.MEANS_BODY.replace("M1", f"M{i}"), "recommend": {**self.MEANS_REC, "answer": a}}
                for i, a in enumerate(answers, 1)]

    def test_means_questions_with_continue_pushes_pass_an_unattended_run(self):
        """6.4（決め means-ask の 2）: 無人の run で開ける理由が頼みどおりの違いの問いだけで、どの問いの行も欄 recommend に通す推しを持てば、
        開かずに推しで進み、採った推しを pushed に返す（answer-final が gates/gate-final.json に残す）。字の問いの末尾の尾では進まない"""
        for mode in ("when_needed", "protected_only"):
            with self.subTest(mode=mode):
                out = self.ask(final_got(self.f, means_questions=self.means_rows("continue", "continue")), mode=mode, unattended=True)
                self.assertEqual((out["open"], out["go"], out["stop_reason"], out["text"]), (False, True, "", ""))
                self.assertEqual(out["pushed"]["decision"], "continue")
                self.assertEqual([r["answer"] for r in out["pushed"]["pushed"]], ["continue", "continue"])
                self.assertEqual(out["reasons"], ["頼みの解き方どおりの違いを独立の目が聞いている（2 件）"])
                tailed = self.ask(final_got(self.f, means_questions=[self.MEANS_Q]), mode=mode, unattended=True)
                self.assertEqual((tailed["go"], tailed["pushed"]), (False, None), "文の末尾の尾は推しの欄ではない")

    def test_means_question_rows_with_a_continue_recommend_field_pass_an_unattended_run(self):
        """問いの行が欄 recommend に通す推しを持てば、文に尾が無くても無人の run の最後の承認ノードは推しで進み、pushed の各行がその欄の answer と
        尾の無い本文を持つ。止める推しの行が混じれば止まる"""
        rows = self.means_rows("continue", "continue")
        out = self.ask(final_got(self.f, means_questions=rows), mode="when_needed", unattended=True)
        self.assertEqual((out["open"], out["go"], out["stop_reason"]), (False, True, ""))
        self.assertEqual([(r["item"], r["answer"], r["note"]) for r in out["pushed"]["pushed"]],
                         [(row["text"], "continue", "そのまま通す") for row in rows])
        self.assertTrue(all(self.f.gatemarks.PUSH not in r["item"] for r in out["pushed"]["pushed"]))
        halted = self.ask(final_got(self.f, means_questions=self.means_rows("continue", "stop")), mode="when_needed", unattended=True)
        self.assertEqual((halted["go"], halted["stop_reason"], halted["pushed"]), (False, "works:needs-human", None))

    def test_final_head_push_is_not_cut_from_the_middle_of_a_means_question_text(self):
        """最後の承認ノードの冒頭の推しの行は、問いの行の欄 recommend からだけ組む。欄を持たない問いの文の途中に「推し: …」が在っても、その切れ端は出ない"""
        gm = self.f.gatemarks
        middle = self.MEANS_BODY + "（人に聞く訳: x。" + gm._push({gm.RECOMMEND: self.MEANS_REC}).lstrip("／") + "。ほかにも案が在る）"
        head = self.f.final_head(final_got(self.f, means_questions=[{"text": middle}]), [])
        self.assertEqual([x for x in head if x.startswith(gm.PUSH)], [gm.PUSH + gm.NO_PUSH])
        rows = self.means_rows("continue")
        shown = self.f.final_head(final_got(self.f, means_questions=[{"text": middle}, *rows]), [])
        [line] = [x for x in shown if x.startswith(gm.PUSH)]
        self.assertIn("そのまま通す", line)
        self.assertNotIn("ほかにも案が在る", line)

    def test_unattended_means_questions_stop_without_a_continue_push_on_every_row(self):
        """推しの無い問い（引用を照らせず尾を外した行）か止める推しが 1 つでも在れば、今どおり works:needs-human で止まる"""
        bare = self.MEANS_Q.split("／推し:")[0] + "（引用を照らせなかった: 無い）"
        halt = self.MEANS_Q.replace("通す（continue）", "止める（stop）")
        for rows in ([bare], [self.MEANS_Q, bare], [self.MEANS_Q, halt]):
            with self.subTest(rows=rows):
                out = self.ask(final_got(self.f, means_questions=rows), mode="when_needed", unattended=True)
                self.assertEqual((out["open"], out["go"], out["stop_reason"], out["pushed"]), (False, False, "works:needs-human", None))

    def test_unattended_means_pushes_do_not_pass_other_reasons(self):
        """開ける理由が問いのほかにも在る（守りのパス・緑でない・目が通さない・R4 の問いなど）か、開き方 always で問いが無くても開く時は、
        推しが在っても今どおり止まる（開き方 protected_only で開かない理由も、推しで進む時は止める側に数える）"""
        for over in ({"protected_hits": ["lib/protected.json"], "protected_count": 1}, {"tests_ok": False, "green": False},
                     {"questions": ["R4 の問い"]}, {"sealed": False},
                     {"eyes": {**final_got(self.f)["eyes"], "r2": {"status": "redesign-needed", "reason": "別"}}}):
            for mode in ("when_needed", "protected_only"):
                with self.subTest(over=over, mode=mode):
                    out = self.ask(final_got(self.f, means_questions=[self.MEANS_Q], **over), mode=mode, unattended=True)
                    self.assertEqual((out["go"], out["stop_reason"], out["pushed"]), (False, "works:needs-human", None))
        out = self.ask(final_got(self.f, means_questions=[self.MEANS_Q]), mode="always", unattended=True)
        self.assertEqual((out["go"], out["stop_reason"], out["pushed"]), (False, "works:needs-human", None))

    def test_row_shaped_eye_questions_still_open_the_final_gate(self):
        """独立の目の問いが {text, title} の行で届いても、最後の承認ノードの事実（gather）の R4 の問いには本文の字として入り、R2 の問いは本文の行
        （欄 recommend を持ち回る）として入る。頼みどおりの違いの問いが在る時は開き方に依らず開く。字の問いは字のまま。本文が空の行は落とす"""
        eyes = {"questions": [{"text": "R4 の問い", "title": "題 1"}, "字の問い", {"title": "本文の無い行"}],
                "means_questions": [{"text": self.MEANS_BODY, "title": "題 2", "recommend": self.MEANS_REC}, "字の問い 2",
                                    {"title": "本文の無い行"}], "passes": [], "after": None}
        got = self.f.gather(fix_in={}, fixed={}, judged=None, tests=None, eyes=eyes, seal_got=None, spec_check=None, parallel_after=None,
                            replan_answer=None, widened=[], record={}, given={}, rounds_lines=[], unread=[],
                            eyes_back={"rows": [], "exit": "返す物が無い", "left": []})
        self.assertEqual(got["questions"], ["R4 の問い", "字の問い"])
        self.assertEqual(got["means_questions"], [{"text": self.MEANS_BODY, "recommend": self.MEANS_REC}, {"text": "字の問い 2"}],
                         "R2 の問いは本文の行になり、欄 recommend を落とさない")
        shaped = final_got(self.f, questions=got["questions"], means_questions=got["means_questions"])
        for mode in ("when_needed", "protected_only"):
            with self.subTest(mode=mode):
                self.assertTrue(self.ask(shaped, mode=mode)["open"], "頼みどおりの違いの問いは開き方に依らず開く")
        self.assertFalse(self.ask(final_got(self.f), mode="when_needed")["open"], "問いが無ければ開かない（比べの足場）")

    def test_attended_and_closed_returns_carry_no_push(self):
        """人の居る run と開かない run の返りの pushed は null（answer-final は人の答えか前の決めだけを書く）"""
        self.assertIsNone(self.ask(final_got(self.f, means_questions=[self.MEANS_Q]), mode="when_needed")["pushed"])
        self.assertIsNone(self.ask(final_got(self.f), mode="when_needed", unattended=True)["pushed"])

    def test_means_questions_have_their_own_section(self):
        """6.3 の 3 の 1: R2 の行は R4 の問いの節に入れず別の節に並べ、continue / stop が答えになると書く。R2 が redesign-needed の
        run では尾を R2_KEEPS_OUT にする"""
        got = final_got(self.f, means_questions=[self.MEANS_Q], questions=["R4 の問い"])
        text = self.f.final_text(got, self.f.final_needs(got), RUN)
        r4 = text.index("人に聞いている問い（記録のまま引く。1 件）")
        head = text.index(f"- {self.f.MEANS_HEAD}（R2。1 件）:")
        self.assertLess(r4, head)
        self.assertNotIn("集計は 1 か所", text[r4:head])
        tail = text[head:].split("\n")
        self.assertIn(f"  - {self.f.MEANS_ANSWERS}", tail[:6])
        self.assertIn("この承認ノードの continue は頼みどおりの差分を当てる答え", self.f.MEANS_ANSWERS)
        eyes = {**final_got(self.f)["eyes"], "r2": {"status": "redesign-needed", "reason": "別"}}
        red = self.f.final_text(final_got(self.f, means_questions=[self.MEANS_Q], eyes=eyes), [], RUN)
        part = red[red.index(f"- {self.f.MEANS_HEAD}"):].split("\n")[:6]
        self.assertIn(f"  - {self.f.R2_KEEPS_OUT}", part)
        self.assertNotIn(f"  - {self.f.MEANS_ANSWERS}", part)

    def test_r2_redesign_says_the_diff_is_not_applied_whichever_answer(self):
        """持ち主の決め small-core の 2026-11-04 の足し（案 1-B）: R2 が作り直しと言った run の最後の承認ノードは、進めても止めても差分を
        当てないことを冒頭の決めてほしいことと答え方の前に機械の字で書き、continue で当たる・PR を作ると読める行を出さない"""
        redesign = {"status": "redesign-needed", "reason": "別の設計"}
        eyes = {**final_got(self.f)["eyes"], "r2": redesign}
        got = final_got(self.f, eyes=eyes, deliver_pr=True, spec_changed=["受け入れ条件のテストが変わった"])
        text = self.f.final_text(got, self.f.final_needs(got), RUN)
        head, answers = text.split("\n")[:3], text.split("答え方（")[1]
        self.assertIn(self.f.R2_KEEPS_OUT, head[1])
        self.assertIn(self.f.R2_KEEPS_OUT, text.split("答え方（")[0].rsplit("\n- 封じた差分の hash", 1)[1])
        self.assertIn("small-core", self.f.R2_KEEPS_OUT)
        self.assertIn("進めても止めても", self.f.R2_KEEPS_OUT)
        self.assertNotIn(self.f.SPEC_APPLIES, text)
        self.assertNotIn("PR を作る", text)
        self.assertIn("continue", answers)
        for status in ("pass", "fix-needed", "unverifiable"):
            with self.subTest(status=status):
                other = final_got(self.f, eyes={**eyes, "r2": {"status": status, "reason": ""}})
                self.assertNotIn(self.f.R2_KEEPS_OUT, self.f.final_text(other, self.f.final_needs(other), RUN))
        self.assertNotIn(self.f.R2_KEEPS_OUT, self.f.final_text(final_got(self.f, eyes={**eyes, "r2": None}), [], RUN))

    def test_protected_only_ignores_other_reasons(self):
        self.assertFalse(self.ask(final_got(self.f, tests_ok=False), mode="protected_only")["open"])
        self.assertTrue(self.ask(final_got(self.f, tests_ok=False), mode="when_needed")["open"])

    def test_parallel_after_found_and_failure_are_reasons_but_not_must(self):
        """8.1: 修正の後の並行 PR の確かめ直しが重なりを見つけた・確かめ直せなかった時は開き方で開く理由（must でない）"""
        found = {"ok": True, "status": "found", "material": {"status": "found", "count": 2}, "reason": "", "report": ["- 重なり 2 件"]}
        failed = {"ok": False, "status": "failed", "material": {}, "reason": "gh が落ちた", "stop_reason": "", "report": []}
        for after, word in ((found, "重なる（2 件）"), (failed, "確かめ直しができなかった（gh が落ちた）")):
            with self.subTest(word=word):
                got = final_got(self.f, parallel_after=after)
                why = self.f.final_needs(got)
                self.assertTrue(any(word in w for w in why), why)
                self.assertFalse(any(m for _, m in self.f.needs(got)))
                self.assertTrue(self.ask(got, mode="when_needed")["open"])
                self.assertFalse(self.ask(got, mode="protected_only")["open"])
        clean = final_got(self.f, parallel_after={**found, "status": "clean"})
        self.assertEqual(self.f.final_needs(clean), [])

    def test_unread_notes_are_a_must_open_reason(self):
        """読めなかった控え（直した後の実測・封じた差分・問いの台帳など）は理由の一覧に載り、開き方に依らず開く。
        無人の run では理由つきで止まる（理由が空のまま「開けない」で進まない）"""
        got = final_got(self.f, unread=["直した後の実測の控えを読めない（柵の増えを数えていない）"])
        self.assertTrue(any("読めなかった" in w for w in self.f.final_needs(got)), self.f.final_needs(got))
        self.assertTrue(self.ask(got, mode="when_needed")["open"])
        out = self.ask(got, mode="when_needed", unattended=True)
        self.assertEqual((out["go"], out["stop_reason"]), (False, __import__("stopby").NEEDS_HUMAN))
        self.assertTrue(out["reasons"])

    def test_unattended_stops_instead_of_opening(self):
        out = self.ask(final_got(self.f, tests_ok=False), mode="when_needed", unattended=True)
        self.assertEqual((out["open"], out["go"], out["stop_reason"]), (False, False, __import__("stopby").NEEDS_HUMAN))

    def test_escalated_premise_check_opens_the_final_gate(self):
        eyes = {**final_got(self.f)["eyes"], "premise_check": {"verdict": "escalate", "reason": "r", "facts": []}}
        self.assertIn("前提の検算が人に上げた", self.f.final_needs(final_got(self.f, eyes=eyes)))

    def test_unsealed_is_a_reason(self):
        why = self.f.final_needs(final_got(self.f, sealed=False, seal_reason=self.f.SEAL_FELL))
        self.assertTrue(any("差分を封じられなかった" in w for w in why))

    def test_objection_left_after_the_rejudge_is_a_reason(self):
        self.assertIn("止めずに残った異議が在る", self.f.final_needs(final_got(self.f, objection="判定が違う")))
        self.assertNotIn("止めずに残った異議が在る",
                         self.f.final_needs(final_got(self.f, objection="判定が違う", rejudge_verdict=self.f.ADOPTED)))

    def test_held_questions_are_not_reasons(self):
        """L-G36: 判定の役が保留にしたままの問いは冒頭と本文に見せるが、開ける理由に数えない"""
        got = final_got(self.f, held=["問い q-a（保留）"])
        self.assertEqual(self.f.final_needs(got), [])
        self.assertIn("保留にしたままの問い", self.f.final_text(got, [], RUN))

    def test_final_text_names_left_tests_and_closure(self):
        """keep-essence 6・11: 回さなかった試験を名で並べ、単位ごとの閉鎖の数え直しが届く"""
        got = final_got(self.f, tests_left=["修正の受け付けが手元で回さなかった試験（1 件）:", "  - tests/test_a.py::t"],
                        closure=["u1: 閉じた"])
        text = self.f.final_text(got, [], RUN)
        self.assertIn("  - tests/test_a.py::t", text)
        self.assertIn("- u1: 閉じた", text)

    def test_parallel_section_comes_before_the_eyes(self):
        got = final_got(self.f, parallel_after={"ok": True, "status": "found", "material": {"count": 1}, "reason": "", "report": ["x"]})
        text = self.f.final_text(got, self.f.final_needs(got), RUN)
        self.assertLess(text.index(self.f.PARALLEL_HEAD), text.index("独立の目の判定"))

    def test_merge_values_come_from_the_receivers(self):
        """merge の apply に渡す値は封じの返りから。封じが飛んだ時は sealed_hash が空"""
        tests = {"ok": True, "fingerprint": {"head": "h", "diff_hash": "d"}}
        eyes = {"ok": False, "r2": {"status": "pass", "reason": ""}}
        got = self.f.merge_values(tests, eyes, {"ok": True, "hash": "x"})
        self.assertEqual(got, {"sealed_hash": "x", "fingerprint": tests["fingerprint"], "green_ok": True, "eyes_ok": False,
                               "r2": eyes["r2"]})
        self.assertEqual(self.f.merge_values(tests, eyes, None)["sealed_hash"], "")
        self.assertEqual(self.f.merge_values(tests, eyes, {"ok": False, "hash": "x"})["sealed_hash"], "")

    def test_keep_writes_the_open_text(self):
        with _tmp() as d:
            out = self.f.keep({"open": True, "text": "t"}, d)
            self.assertEqual((pathlib.Path(d) / self.f.files.FINAL_GATE_MD).read_text(encoding="utf-8"), "t")
            self.assertEqual(out["text"], "t")


def _tmp():
    import tempfile
    return tempfile.TemporaryDirectory()


class DirectionStopCase(unittest.TestCase):
    """修正前の承認の一言の向きで修正の前に止めるかの決め（gates.direction_stop。docs/design/line.md の 2 節の 2）。照らすのは、承認ノードが
    開いて人が通す語で答えた時だけ。その時、判定の返りが {ok: 真, aligned: 真} でなければ止める（fail-closed）。向きの語は block の中だけが
    持つので、ここは真偽 aligned だけを渡す"""
    NOTE = "計画と違い、空の列は例外を投げる形にして"
    GATE = {"decision": "continue", "text": NOTE}
    ANSWER = {**GATE, "asked": [NARROW]}
    ALIGNED = {"ok": True, "status": "ok", "reason": "", "direction": "aligned", "aligned": True, "why": "計画の向きを足しているだけ", "report": []}
    REDIRECTED = {**ALIGNED, "direction": "redirected", "aligned": False, "why": "計画は 0 を返すが一言は例外を選んでいる"}
    UNCLEAR = {**ALIGNED, "direction": "unclear", "aligned": False, "why": "どちらの向きか言っていない"}
    FAILED = {"ok": False, "status": "failed", "reason": "役が返答を返さなかった", "direction": "", "aligned": False, "why": "", "report": []}

    def setUp(self):
        self.g = kit.load(BLOCK, "gates")
        self.stopby = __import__("stopby")
        self.assertTrue(hasattr(self.g, "direction_stop"), "gates に一言の向きで止めるかの決め direction_stop が在る")
        self.assertTrue(hasattr(self.stopby, "ANSWER_REDIRECTED"), "stopby に一言の向きで止めた語 ANSWER_REDIRECTED が在る")

    def stop(self, gate=None, answer=None, checked=None, *, due=True):
        return self.g.direction_stop(self.GATE if gate is None else gate, self.ANSWER if answer is None else answer, checked, due=due)

    def test_stops_unless_the_judgment_reads_aligned(self):
        for name, checked, said in (("redirected", self.REDIRECTED, ("redirected", self.REDIRECTED["why"])),
                                    ("unclear", self.UNCLEAR, ("unclear", self.UNCLEAR["why"])),
                                    ("failed", self.FAILED, ("役が返答を返さなかった",)),
                                    ("ok false even if aligned", {**self.ALIGNED, "ok": False}, ()),
                                    ("aligned missing", {"ok": True}, ()),
                                    ("empty receiver", None, ()), ("not an object", "aligned", ())):
            with self.subTest(name):
                word, why = self.stop(checked=checked)
                self.assertEqual(word, self.stopby.ANSWER_REDIRECTED)
                self.assertIn(self.NOTE, why, "人の一言が訳に入る")
                for part in said:
                    self.assertIn(part, why)
        self.assertEqual(self.stop(checked=self.ALIGNED), ("", ""))
        word, why = self.stop(checked={**self.REDIRECTED, "why": "一行目\n二行目"}, gate={"decision": "continue", "text": "a\n\nb"})
        self.assertEqual(word, self.stopby.ANSWER_REDIRECTED)
        self.assertNotIn("\n", why, "訳は 1 行")

    def test_unopened_pushed_or_stopping_answers_are_not_checked(self):
        """承認ノードが開かなかった（対話モードの合意・推しで進んだ）・無人の run の推しで答えた・止める語で答えた・照らさない道（due 偽）は、
        判定の返りが無くても止めない。止める語の答えは human:gate-before-fix で止まるので、ここは足さない"""
        pushed = {**self.ANSWER, __import__("answer").PUSHED: [{"item": NARROW}]}
        stop = {"decision": "stop", "text": self.NOTE}
        for name, gate, answer, due in (("gate unopened (None)", None, self.ANSWER, True), ("gate unopened (empty)", "", self.ANSWER, True),
                                        ("pushed", self.GATE, pushed, True), ("stop word", stop, stop, True),
                                        ("reject word", {**stop, "decision": "reject"}, {**stop, "decision": "reject"}, True),
                                        ("no answer", self.GATE, None, True), ("not due", self.GATE, self.ANSWER, False)):
            with self.subTest(name):
                for checked in (None, self.REDIRECTED, self.FAILED):
                    self.assertEqual(self.g.direction_stop(gate, answer, checked, due=due), ("", ""))


class ScriptCase(unittest.TestCase):
    """script を子のプロセスで回す（block の返り・line の node の返りを JSON の字で渡す）"""

    def setUp(self):
        self.run = kit.Run(self, BLOCK)

    def put(self, rel: str, doc) -> str:
        path = self.run.artifacts / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return self.run.pointer(rel)

    def ports(self, **over) -> str:
        return json.dumps({"unattended": False, "design_talk": False, "policy": "", "base_rev": "abc", "deliver": "", **over})

    def test_ask_before_fix_opens_with_the_gate_text(self):
        record = self.put("r1/start.json", {"answers": []})
        out = self.run.script("ask_before_fix", request=handed({}), rounds=json.dumps(rounds(asks=[ask_row()])), structure="null",
                              judge=json.dumps({"judgment": None, "answer_ties": None, "materials": None}), record=record,
                              ports=self.ports())
        self.assertEqual((out["open"], out["go"], out["stop_reason"]), (True, True, ""), out)
        self.assertIn(NARROW, out["text"])
        self.assertIn("gate-before-fix", out["text"])

    def test_ask_before_fix_reopens_from_a_copy_that_stopped_before_the_fix(self):
        """直す前で止まった写しの run（fixture- の付いた node）: 計画の往復・判定・構造の目を写しの運ぶ値（fixture）から読み、写した run と
        同じ項目で承認ノードを開く。人の居る run なので推しで進まず人に聞く"""
        record = self.put("r1/start.json", {"answers": []})
        carried = self.put("fixture-carried.json", {"judge": {"judgment": None, "answer_ties": None, "materials": None},
                                                     "structure": {"structure": None}, "gate_rounds": rounds(asks=[ask_row()])})
        out = self.run.script("ask_before_fix", request=handed({}), rounds="", structure="", judge="", fixture=carried, record=record,
                              ports=self.ports())
        self.assertEqual((out["open"], out["go"], out["stop_reason"]), (True, True, ""), out)
        self.assertIn(NARROW, out["text"])

    def test_ask_before_fix_asks_the_structure_pointed_rows(self):
        """構造の目の控えの版に無い名指しの行が、材料の読み（src.asking.materials）を通って修正前の承認ノードに届く（持ち主の決め pointed-ask）"""
        record = self.put("r1/start.json", {"answers": []})
        (self.run.artifacts / "structure" / "design.jsonl").parent.mkdir(parents=True, exist_ok=True)
        (self.run.artifacts / "structure" / "design.jsonl").write_text("", encoding="utf-8")
        state = self.put("structure/state.json", {"status": "ok", "reason": "", "wall_s": 0, "skipped": [],
                                                  "design_file": str(self.run.artifacts / "structure" / "design.jsonl"),
                                                  "pointed": [PointedAskCase.RULE]})
        for structure, want in ((state, True), ("null", False)):
            with self.subTest(structure=structure):
                out = self.run.script("ask_before_fix", request=handed({}), rounds=json.dumps(rounds()), structure=structure,
                                      judge=json.dumps({"judgment": None, "answer_ties": None, "materials": None}), record=record,
                                      ports=self.ports())
                self.assertEqual((out["open"], out["go"]), (want, True), out)
                self.assertEqual(any("AGENTS.md が名指す docs/deploy.adoc" in x for x in out["asked"]), want, out["asked"])

    def test_ask_before_fix_reads_the_plan_fields_when_the_review_fell(self):
        """計画 means-answers の 3.2 の 8: 事前審査が諦めた周は、材料の読み（src.asking.materials）が判定の means と判定の処方の文と往復の
        plan の控え（plan-fields.json）を読んで before_fix に渡し、計画の {means, deviation}・{prescription, deviation} が推しなしの項目で出る
        （処方の文は入力 judgment の判定から引く。引かないと読めていないと名乗る）。事前審査が通った周は読まない"""
        record = self.put("r1/start.json", {"answers": []})
        plan = self.put("plan-fields.json", {"round": 1, "fields": [
            {"unit_keys": ["u1"], "allowed_paths": ["a.py"], "out_of_scope": [],
             "structure": [{"means": "M1", "deviation": "リポジトリの決まりが別の層に置くと決めている"},
                           {"prescription": "u1", "deviation": "リポジトリの決まりが別の層に置くと決めている"}]}]})
        judgment = self.put("judge/judgment.json", {"units": [{"key": "u1", "prescriptions": ["上限の枝を hi にする"]}], "questions": []})
        judge = json.dumps({"judgment": judgment, "answer_ties": None, "materials": None, "means": ["分母を len(xs) にする"]})
        for status, want in (("gave_up", True), ("ok", False)):
            with self.subTest(status=status):
                got = rounds(review_status=status, review_reason="受け付けが諦めた", plan=json.loads(plan))
                out = self.run.script("ask_before_fix", request=handed({}), rounds=json.dumps(got), structure="null", judge=judge,
                                      record=record, ports=self.ports())
                means = [a for a in out["asked"] if a.startswith("修正案 1 は頼みの解き方 M1「分母を len(xs) にする」に従わない——")]
                self.assertEqual(len(means), 1 if want else 0, out["asked"])
                rx = [a for a in out["asked"] if a.startswith("修正案 1 は単位 u1 の判定の処方")]
                self.assertEqual(len(rx), 1 if want else 0, out["asked"])
                if want:
                    self.assertIn("1. 上限の枝を hi にする", rx[0])

    def test_before_fix_answer_records_the_asked_rows(self):
        """S46: 答えの asked に載せた行を付け、gates/gate-before-fix.json に書く。方針の変化を通さない答えは配る値の policy のまま"""
        record = self.put("r1/start.json", {})
        gate = json.dumps({"decision": "continue", "text": "通す"})
        out = self.run.script("before_fix_answer", gate=gate, go="true", stop_reason="", place="gate-before-fix",
                              asked=json.dumps([NARROW]), pushed="null", policy_changed="false", record=record,
                              ports=self.ports(policy="/p.md"))
        self.assertEqual((out["go"], out["answer"]["asked"], out["policy"]), (True, [NARROW], "/p.md"))
        self.assertTrue((self.run.artifacts / "gates" / "gate-before-fix.json").is_file())

    def test_before_fix_answer_refreezes_a_passed_policy_change(self):
        """2 節の 2: 方針の文書の変化を通した答えは今の文書を固め直し、始めの記録の policy を書き直して写しのパスを返す"""
        doc = self.run.repo / "policy.md"
        doc.write_text("新しい方針\n", encoding="utf-8")
        record = self.put("r1/start.json", {"policy": {"named": str(doc), "path": str(doc), "sha256": "old", "copy": None}})
        out = self.run.script("before_fix_answer", gate=json.dumps({"decision": "continue", "text": ""}), go="true", stop_reason="",
                              place="gate-before-fix", asked="[]", pushed="null", policy_changed="true", record=record,
                              ports=self.ports())
        saved = json.loads((self.run.artifacts / "r1/start.json").read_text(encoding="utf-8"))
        self.assertNotEqual(saved["policy"]["sha256"], "old")
        self.assertEqual(out["policy"], saved["policy"]["copy"])
        self.assertTrue(pathlib.Path(out["policy"]).is_file())

    NOTE = "計画と違い、空の列は例外を投げる形にして"
    JUDGED = {"ok": True, "status": "ok", "reason": "", "direction": "redirected", "aligned": False,
              "why": "計画は 0 を返すが一言は例外を選んでいる", "report": []}

    def before_fix_answer(self, record, *, gate=None, direction="null", due=None, **over):
        inputs = {"gate": json.dumps(gate or {"decision": "continue", "text": self.NOTE}), "go": "true", "stop_reason": "",
                  "place": "gate-before-fix", "asked": json.dumps([NARROW]), "pushed": "null", "policy_changed": "false",
                  "record": record, "ports": self.ports(policy="/p.md"), **over}
        if due is not None:
            inputs.update(direction=direction, direction_due=due)
        return self.run.script("before_fix_answer", **inputs)

    def test_before_fix_answer_stops_a_redirected_note(self):
        """一言の向きの判定（direction）が aligned 偽なら、go 偽・止めの語 works:answer-redirected・判定の why と人の一言を含む reason。
        答えの控えには今どおり一言と asked が残る。方針は固め直さない"""
        record = self.put("r1/start.json", {})
        out = self.before_fix_answer(record, direction=json.dumps(self.JUDGED), due="true", policy_changed="true")
        self.assertEqual((out["go"], out["stop_reason"], out["policy"]), (False, "works:answer-redirected", "/p.md"), out)
        self.assertIn(self.JUDGED["why"], out["reason"])
        self.assertIn(self.NOTE, out["reason"])
        self.assertEqual(out["answer"], {"decision": "continue", "text": self.NOTE, "asked": [NARROW]})
        kept = json.loads((self.run.artifacts / "gates" / "gate-before-fix.json").read_text(encoding="utf-8"))
        self.assertEqual((kept["text"], kept["asked"]), (self.NOTE, [NARROW]))
        # 計画に沿う（aligned）・役を起こさなかった（skipped）判定なら止めずに修正へ進む
        aligned = {**self.JUDGED, "direction": "aligned", "aligned": True, "why": "足しているだけ"}
        for name, direction in (("aligned", aligned), ("skipped", {**aligned, "status": "skipped", "direction": "", "why": ""})):
            with self.subTest(name):
                went = self.before_fix_answer(record, direction=json.dumps(direction), due="true")
                self.assertEqual((went["go"], went["stop_reason"], went["reason"]), (True, "", ""), went)
        # 判定の返りが無い（飛んだ）・落ちた（ok 偽）時は止める（fail-closed）。訳は落ちた訳を言う
        failed = {"ok": False, "status": "failed", "reason": "役が返答を返さなかった", "direction": "", "aligned": False, "why": "", "report": []}
        for name, direction, said in (("null", "null", ""), ("failed", json.dumps(failed), failed["reason"])):
            with self.subTest(name):
                stopped = self.before_fix_answer(record, direction=direction, due="true")
                self.assertEqual((stopped["go"], stopped["stop_reason"]), (False, "works:answer-redirected"), stopped)
                self.assertIn(said, stopped["reason"])
                self.assertIn(self.NOTE, stopped["reason"])
        # 対話モードの合意だけで入る道（承認ノードが開かない）は、due 真でも判定の返りが無くて止めない。合意の一言は設計の相談の承認ノードが受ける
        agreed = json.dumps({"decision": "continue", "text": "合意の一言", "asked": [NARROW]})
        quiet = self.run.script("before_fix_answer", gate="null", go="true", stop_reason="", place="gate-before-fix", asked="[]", pushed="null",
                                policy_changed="false", agreed=agreed, record=record, ports=self.ports(policy="/p.md"),
                                direction="null", direction_due="true")
        self.assertEqual((quiet["go"], quiet["stop_reason"], quiet["reason"]), (True, "", ""), quiet)
        # 合意の後に新しい行で開いた承認ノードを人が通した時、判定に掛かる答えは承認ノードの出力そのもの（合意の一言は足されない）。
        # 止める時の訳の人の一言も、承認ノードで書いた一言だけ
        agreed = json.dumps({"decision": "continue", "text": "合意の一言", "asked": ["合意で見せた行"]})
        after = self.run.script("before_fix_answer", gate=json.dumps({"decision": "continue", "text": self.NOTE}), go="true", stop_reason="",
                                place="gate-before-fix", asked=json.dumps([NARROW]), pushed="null", policy_changed="false", agreed=agreed,
                                record=record, ports=self.ports(policy="/p.md"), direction=json.dumps(self.JUDGED), direction_due="true")
        self.assertEqual((after["go"], after["stop_reason"]), (False, "works:answer-redirected"), after)
        self.assertIn(self.NOTE, after["reason"])
        self.assertNotIn("合意の一言", after["reason"])

    def test_before_fix_answer_without_the_check_stays(self):
        """direction_due を渡さない（本線の）before_fix_answer は、一言付きの continue で今どおり go 真を返し、reason は空。判定の返りを渡しても、
        due を渡さなければ照らさない"""
        record = self.put("r1/start.json", {})
        for name, extra in (("main line", {}), ("due false", {"direction": json.dumps(self.JUDGED), "direction_due": "false"})):
            with self.subTest(name):
                out = self.before_fix_answer(record, **extra)
                self.assertEqual((out["go"], out["stop_reason"], out.get("reason")), (True, "", ""), out)

    def test_ask_before_fix_hands_the_plan_it_shows(self):
        """承認ノードに掛ける計画の行（src.talk.plan_lines の字の配列）を欄 plan で返す。往復が無い・修正案の項目が無い周は空。写しの運ぶ値から
        開き直す時も、写しの rounds の計画の行を同じ欄で返す。判定の block は修正案の形を知らず、この行だけを受ける"""
        record = self.put("r1/start.json", {"answers": []})
        judge = json.dumps({"judgment": None, "answer_ties": None, "materials": None})
        doc = {"plan": [{"unit_keys": ["u1"], "approach": "空の列の mean が 0 を返す形に変える",
                         "files": [{"path": "stats.py", "op": "modify", "responsibility": "平均を出す"}]}]}
        kit.shaped("shared:fix-plan.schema.json", doc)
        plan = json.loads(self.put("plan/fix-plan.json", doc))
        lines = ["- 項目 1（u1）: 空の列の mean が 0 を返す形に変える"]
        fresh = self.run.script("ask_before_fix", request=handed({}), rounds=json.dumps(rounds(asks=[ask_row()], fix_plan=plan)),
                                structure="null", judge=judge, record=record, ports=self.ports())
        self.assertTrue(fresh["open"], fresh)
        self.assertEqual(fresh.get("plan"), lines)
        empty = json.loads(self.put("plan/empty.json", {"plan": []}))
        broken = json.loads(self.put("plan/broken.json", {"plan": "形に合わない"}))
        for name, given in (("planless", json.dumps(rounds(asks=[ask_row()]))), ("no items", json.dumps(rounds(asks=[ask_row()], fix_plan=empty))),
                            ("absent", "null"), ("broken", json.dumps(rounds(asks=[ask_row()], fix_plan=broken)))):
            with self.subTest(name):
                out = self.run.script("ask_before_fix", request=handed({}), rounds=given, structure="null", judge=judge, record=record,
                                      ports=self.ports())
                self.assertEqual(out.get("plan"), [], out)
                if name == "broken":   # 形に合わない修正案の控えは本線でも関所を止めない（読みの誤りを受けて空にする）
                    self.assertTrue(out["open"], out)
        carried = self.put("fixture-carried.json", {"judge": {"judgment": None, "answer_ties": None, "materials": None},
                                                     "structure": {"structure": None},
                                                     "gate_rounds": rounds(asks=[ask_row()], fix_plan=plan)})
        copied = self.run.script("ask_before_fix", request=handed({}), rounds="", structure="", judge="", fixture=carried, record=record,
                                 ports=self.ports())
        self.assertEqual((copied["open"], copied.get("plan")), (True, lines))

    def plans(self):
        old = self.put("plan-fields.json", {"round": 1, "fields": [{"unit_keys": ["u1"], "allowed_paths": ["a.py"], "out_of_scope": []}]})
        new = self.put("replan/plan-fields.json", {"round": 1, "fields": [{"unit_keys": ["u1"], "allowed_paths": ["a.py", "b.py"], "out_of_scope": []}]})
        return old, new

    def replan_got(self, new):
        return {"ok": True, "status": "ok", "reason": "", "plan": json.loads(new), "fix_plan": None, "ripple": None, "round": 1}

    def review_got(self, rows, status="ok"):
        return {"ok": status == "ok", "status": status, "reason": "", "replan": rows, "round": 1, "holes": None, "blocks": [],
                "deviations": self.deviations}

    deviations: list = []

    def ask_replan(self, rows, *, status="ok", unattended=False, before_fix="null", record=None):
        old, new = self.plans()
        return self.run.script("ask_replan", replan=json.dumps(self.replan_got(new)),
                               review=json.dumps(self.review_got(rows, status)) if status else "null", old_plan=old,
                               items=json.dumps([1]), conflicts="null", before_fix=before_fix,
                               record=record or self.put("r1/start.json", {}), ports=self.ports(unattended=unattended))

    def test_same_contract_passes_without_asking(self):
        out = self.ask_replan([{"item": 1, "units": ["u1"], "contract_changed": [], "human": [], "widened": None}])
        self.assertEqual((out["open"], out["go"]), (False, True))

    def test_changed_contract_asks_with_both_items(self):
        out = self.ask_replan([{"item": 1, "units": ["u1"], "contract_changed": ["allowed_paths"], "human": [], "widened": None}])
        self.assertTrue(out["open"], out)
        self.assertIn("項目 1: 約束の欄が変わった（allowed_paths）", out["asked"])
        self.assertIn('"b.py"', out["text"])

    def test_unattended_passes_widening_only_and_records_it(self):
        row = {"item": 1, "units": ["u1"], "contract_changed": ["allowed_paths"], "human": [],
               "widened": {"added": ["b.py"], "removed": []}}
        out = self.ask_replan([row], unattended=True)
        self.assertEqual((out["open"], out["go"]), (False, True), out)
        self.assertEqual(len(out["widened"]), 1)

    def test_review_that_could_not_review_asks(self):
        out = self.ask_replan([], status="gave_up")
        self.assertTrue(out["open"])
        self.assertTrue(out["asked"][0].startswith("案の直しの事前審査が案を審査できていない"))

    def test_face_passed_before_the_fix_is_not_asked_again(self):
        """L-D26・S22: 修正前の承認ノードの答えで通した穴の行は、案の直しで聞き直さない"""
        face = {"key": "keep-zero", "kind": "regression", "why": "0 を返すと前の呼び手が壊れる"}
        row = {"item": 1, "units": ["u1"], "contract_changed": [], "human": [face], "widened": None}
        self.assertTrue(self.ask_replan([row])["open"])
        passed = json.dumps({"decision": "continue", "text": "", "asked": [FACE]})
        self.assertFalse(self.ask_replan([row], before_fix=passed)["open"])

    def test_means_rows_of_revised_items_are_asked_with_their_push(self):
        """計画 means-answers の 3.3 の 5: 直した項目の頼みの解き方の行を推しの欄 recommend つきで聞き（無人の run は推しで抜ける）、直さない項目の
        行と、修正前の承認ノードが continue で通した同じ鍵 (項目, M<n>, 向き) の行は、推しの文が書き直されていても聞かない（前に通したのが
        同じ項目の食い違いの行なら、今の外れの行は聞く）"""
        def dev(item, note):
            return {"source": "means", "item": item, "why": ["頼みの解き方と独立の目の食い違い"],
                    "text": f"修正案 {item} は頼みの解き方 M1「分母を直す」に従わない——決まりが別の層に置く",
                    "mark": {"decided_by": "決まり", "recommend": {**REC, "note": note}}}
        self.deviations = [dev(1, "計画のまま通す"), dev(2, "計画のまま通す")]
        row = {"item": 1, "units": ["u1"], "contract_changed": [], "human": [], "widened": None}
        out = self.ask_replan([row])
        self.assertTrue(out["open"], out)
        self.assertEqual([a[:9] for a in out["asked"]], ["修正案 1 は頼み"], out["asked"])
        self.assertNotIn("推し:", out["asked"][0], "asked の文には推しの尾が無い")
        self.assertIn(__import__("gatemarks").MACHINE_PUSH + "通す（continue）——計画のまま通す", out["text"], "推しは行の欄から子の行に出る")
        got = self.ask_replan([row], unattended=True)
        self.assertTrue(got["go"], got)
        self.assertEqual([r["answer"] for r in got["pushed"]["pushed"]], ["continue"])
        before = json.dumps({"decision": "continue", "text": "", "asked": [out["asked"][0]]})
        self.deviations = [dev(1, "前と違う一言で通す")]
        self.assertFalse(self.ask_replan([row], before_fix=before)["open"])
        drift = "修正案 1 は頼みの解き方 M1「分母を直す」に従うが、独立設計と食い違う——設計は別の層（人に聞く訳: 食い違い）"
        got = self.ask_replan([row], before_fix=json.dumps({"decision": "continue", "text": "", "asked": [drift]}))
        self.assertTrue(got["open"], "前に通したのが同じ項目の食い違いの行なら、今の外れの行は聞く")
        self.assertEqual([a[:9] for a in got["asked"]], ["修正案 1 は頼み"], got["asked"])

    def test_means_rows_of_revised_items_are_listed_without_push_when_the_review_fell(self):
        """計画 means-answers の 3.3 の 5: 案の直しの事前審査が諦めた・落ちた時も、直した項目の計画の {means, deviation} を推しなしで
        並べる（修正前の承認ノードと同じ。直さない項目の行は足さない）"""
        old, _ = self.plans()
        dev = {"means": "M1", "deviation": "決まりが別の層に置く"}
        new = self.put("replan/plan-fields.json", {"round": 1, "fields": [
            {"unit_keys": ["u1"], "allowed_paths": ["a.py"], "out_of_scope": [], "structure": [dev]},
            {"unit_keys": ["u2"], "allowed_paths": ["c.py"], "out_of_scope": [], "structure": [dev]}]})
        out = self.run.script("ask_replan", replan=json.dumps(self.replan_got(new)), review=json.dumps(self.review_got([], "gave_up")),
                              old_plan=old, items=json.dumps([1]), conflicts="null", before_fix="null",
                              record=self.put("r1/start.json", {}), means=json.dumps(["分母を直す"]), ports=self.ports())
        means = [a for a in out["asked"] if a.startswith("修正案")]
        self.assertEqual(len(means), 1, out["asked"])
        self.assertTrue(means[0].startswith("修正案 1 は頼みの解き方 M1「分母を直す」に従わない——"), means)
        self.assertNotIn("推し:", means[0])
        stopped = self.run.script("ask_replan", replan=json.dumps(self.replan_got(new)), review=json.dumps(self.review_got([], "gave_up")),
                                  old_plan=old, items=json.dumps([1]), conflicts="null", before_fix="null",
                                  record=self.put("r1/start.json", {}), means=json.dumps(["分母を直す"]), ports=self.ports(unattended=True))
        self.assertEqual((stopped["go"], stopped["pushed"]), (False, None), "推しの欄の無い行は無人の run では推し無しとして止まる")

    def prescription_dev(self, item, note="計画のまま通す", deviation="決まりが別の層に置く"):
        return {"source": "prescription", "item": item, "why": ["判定の処方と計画の決め手が別の答えを指す"],
                "text": f"修正案 {item} は単位 u1 の判定の処方「1. 分母を直す」に従わない——{deviation}",
                "mark": {"decided_by": "決まり", "recommend": {**REC, "note": note}}}

    def test_prescription_rows_of_revised_items_are_asked_with_their_push(self):
        """直した項目の判定の処方の外れの行を推しの欄 recommend つきで聞き（無人の run は推しで抜ける）、直さない項目の行は聞かない。事前審査が
        落ちた道では、入力 judgment の判定の処方の文を載せた推しなしの行を聞く"""
        self.deviations = [self.prescription_dev(1), self.prescription_dev(2)]
        row = {"item": 1, "units": ["u1"], "contract_changed": [], "human": [], "widened": None}
        out = self.ask_replan([row])
        self.assertEqual([a[:12] for a in out["asked"]], ["修正案 1 は単位 u1"], out["asked"])
        self.assertTrue(out["open"], out)
        self.assertNotIn("推し:", out["asked"][0], "asked の文には推しの尾が無い")
        self.assertIn(__import__("gatemarks").MACHINE_PUSH + "通す（continue）——計画のまま通す", out["text"])
        self.assertTrue(self.ask_replan([row], unattended=True)["go"])
        old, _ = self.plans()
        dev = {"prescription": "u1", "deviation": "決まりが別の層に置く"}
        new = self.put("replan/plan-fields.json", {"round": 1, "fields": [
            {"unit_keys": ["u1"], "allowed_paths": ["a.py"], "out_of_scope": [], "structure": [dev]},
            {"unit_keys": ["u2"], "allowed_paths": ["c.py"], "out_of_scope": [], "structure": [dev]}]})
        judgment = self.put("judgment.json", {"units": [{"key": "u1", "prescriptions": ["分母を直す"]}]})
        for given, word in ((judgment, "1. 分母を直す"), ("null", "判定の処方の文を読めていない")):
            with self.subTest(judgment=given[:8]):
                out = self.run.script("ask_replan", replan=json.dumps(self.replan_got(new)), review=json.dumps(self.review_got([], "gave_up")),
                                      old_plan=old, items=json.dumps([1]), conflicts="null", before_fix="null",
                                      record=self.put("r1/start.json", {}), judgment=given, ports=self.ports())
                rows = [a for a in out["asked"] if a.startswith("修正案")]
                self.assertEqual(len(rows), 1, out["asked"])
                self.assertIn(word, rows[0])
                self.assertNotIn("推し:", rows[0])

    def test_prescription_row_passed_before_is_not_reasked_when_only_the_push_changes(self):
        """修正前の承認ノードが continue で通した処方の外れの行と、同じ項目・同じ単位・同じ deviation で推しの note だけが違う行は聞き直さない。
        deviation の文を変えた行は聞く"""
        row = {"item": 1, "units": ["u1"], "contract_changed": [], "human": [], "widened": None}
        self.deviations = [self.prescription_dev(1)]
        first = self.ask_replan([row])["asked"][0]
        before = json.dumps({"decision": "continue", "text": "", "asked": [first]})
        self.deviations = [self.prescription_dev(1, note="前と違う一言で通す")]
        self.assertFalse(self.ask_replan([row], before_fix=before)["open"])
        self.deviations = [self.prescription_dev(1, deviation="別の訳で外れる")]
        got = self.ask_replan([row], before_fix=before)
        self.assertTrue(got["open"], got)
        self.assertIn("別の訳で外れる", got["asked"][0])

    def test_replan_answer_carries_the_conditions_in_order(self):
        before = {"decision": "continue", "text": "a.py だけ", "asked": [NARROW]}
        out = self.run.script("replan_answer", gate=json.dumps({"decision": "continue", "text": "b.py も"}), go="true", stop_reason="",
                              place="gate-replan", before_fix=json.dumps(before), asked="[]", pushed="null",
                              replan=json.dumps({"ok": True, "plan": None, "fix_plan": None, "ripple": None, "owed": ["u2"]}),
                              review="null", items="[1]", first_ripple="null",
                              units_tier=json.dumps([{"unit_id": "u1", "depth": "軽量", "why": "w"}]))
        text = out["fix_answers"]["text"]
        self.assertLess(text.index("a.py だけ"), text.index("b.py も"))
        self.assertEqual(out["fix_answers"]["asked"], [NARROW])
        self.assertEqual(out["skip_rerun"], [])
        self.assertEqual([r["unit_id"] for r in out["units_tier"]], ["u1", "u2"])
        self.assertIn("読めない", out["fix_notes"])

    def test_eyes_in_merges_only_when_the_eyes_run(self):
        fix_in = {"policy": "/p.md", "answer": {"decision": "continue", "asked": [NARROW]}, "record": None, "round": 1,
                  "switches": {"merge": True}, "no_fix": False}
        for due, want in ((True, True), (False, False)):
            with self.subTest(due=due):
                out = self.run.script("eyes_in", request=handed({}), fix_in=json.dumps(fix_in),
                                      fixed=json.dumps({"eyes_due": due, "no_fix": False, "refixed": False}), start_answer="null",
                                      replan_review="null", judged=json.dumps({"judgment": None, "answer_ties": None, "materials": None}),
                                      record="null", ports=self.ports())
                self.assertEqual(out["merge"], want)
                self.assertEqual(out["policy"], "/p.md")
                self.assertEqual(out["asked"], [{"kind": "regression", "text": NARROW}])
                self.assertEqual(out["review"]["verdict"], "unread")

    def test_ask_final_without_a_seal_does_not_seal(self):
        """封じの返りが無い（直す物が在る周）なら、差分を封じられなかったを開ける理由にし、置く段に hash を渡さない（閉じた側に倒れる）"""
        fix_in = {"answer": None, "passes": [], "structure": None, "record": None, "judgment": None, "units": []}
        fixed = {"no_fix": False, "conflicts": [], "handoffs": [], "mismatched": [], "objection": "", "units": [], "groups": [],
                 "stages": [], "replan_items": [], "refixed": False, "skip_why": ""}
        tests = {"ok": True, "green": True, "red_cause": "", "ran_steps": None, "by": "test_cmd", "suites_line": "1 本", "log": "l",
                 "baseline_line": "b", "reason": "", "fingerprint": {"head": "h", "diff_hash": "d"}}
        out = self.run.script("ask_final", request=handed({}), fix_in=json.dumps(fix_in), fixed=json.dumps(fixed), judged="null", tests=json.dumps(tests),
                              eyes="null", seal="null", spec_check="null", parallel_after="null", replan_review="null",
                              replan_answer="null", widened="null", start_answer="null", record="null", final_gate="when_needed",
                              ports=self.ports())
        self.assertEqual(out["stop_reason"], "", out)
        self.assertTrue(any("差分を封じられなかった" in r for r in out["reasons"]), out["reasons"])
        self.assertEqual((out["sealed_hash"], out["green_ok"], out["fingerprint"]), ("", True, tests["fingerprint"]))
        self.assertTrue((self.run.artifacts / "gates" / "final-gate.md").is_file())

    def ask_final_wired(self, **outputs):
        """ask_final の script を、line の YAML の ask-final の with: をそのまま node の返り outputs（node の id → 返り）で結んで回す
        （with: の配線の取り違えも赤になる）。無い node は飛んだ物（if_skipped）。字の値はそのまま、ほかは JSON の字で渡す"""
        from tests.blocks.line.test_wiring import TOP

        def resolve(value):
            skipped = None
            if isinstance(value, dict) and "from" in value:
                value, skipped = value["from"], value.get("if_skipped")
            if not (isinstance(value, str) and value.startswith("$")):
                return value
            node, _, path = value[1:].partition(".output")
            if node not in outputs:
                return skipped
            got = outputs[node]
            for key in filter(None, path.split(".")):
                got = (got or {}).get(key)
            return got
        base = {"fix-in": {"answer": None, "passes": [], "structure": None, "record": None, "judgment": None, "units": []},
                "fixed": {"no_fix": False, "conflicts": [], "handoffs": [], "mismatched": [], "objection": "", "units": [], "groups": [],
                          "stages": [], "replan_items": [], "refixed": False, "skip_why": ""},
                "test-gate-final": {"ok": True, "green": True, "red_cause": "", "ran_steps": None, "by": "test_cmd",
                                    "suites_line": "1 本", "log": "l", "baseline_line": "b", "reason": "",
                                    "fingerprint": {"head": "h", "diff_hash": "d"}},
                "start": {"record": None, "final_gate": "protected_only", "ports": json.loads(self.ports())},
                "request-in": json.loads(handed({}))}
        outputs = {**base, **outputs}
        env = {}
        for key, value in TOP["ask-final"]["with"].items():
            got = resolve(value)
            env[key] = got if isinstance(got, str) else json.dumps(got, ensure_ascii=False)
        return self.run.script("ask_final", **env)

    def test_ask_final_opens_on_unreadable_conflicts_from_the_fixed_stage(self):
        """keep-essence 8: 修正の段の合わせ fixed が運ぶ申し出の控え（conflicts の pointer）が読めない run は、ask-final の with: の配線
        どおりに回した script が開き方 protected_only でも開き、読めない控えを名指す（関数を直に呼ぶ AskFinalCase と違い、配線の道を通す）"""
        fixed = {"no_fix": False, "conflicts": [{"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "fix/conflicts.json"}],
                 "handoffs": [], "mismatched": [], "objection": "", "units": [], "groups": [], "stages": [], "replan_items": [],
                 "refixed": False, "skip_why": ""}
        out = self.ask_final_wired(fixed=fixed)
        self.assertIs(out["open"], True, out)
        self.assertIn(kit.load(BLOCK, "final").CONFLICT_UNREAD, out["text"])

    def test_ask_final_opens_when_the_fix_overlaps_open_prs(self):
        """8.1: 修正の後の並行 PR の確かめ直しが重なり（found）を返した run は、配線どおりに回した script が開き方 when_needed で開き、
        無人の run は当てずに止まる（重なる差分を聞かずに当てない）"""
        found = {"ok": True, "status": "found", "material": {"status": "found", "count": 1}, "reason": "", "stop_reason": "", "report": ["- 重なり 1 件"]}
        start = {"record": None, "final_gate": "when_needed", "ports": json.loads(self.ports())}
        out = self.ask_final_wired(**{"parallel-pr-after": found, "start": start})
        self.assertIs(out["open"], True, out)
        self.assertIn("開いている PR と重なる", out["text"])
        alone = {**start, "ports": json.loads(self.ports(unattended=True))}
        stopped = self.ask_final_wired(**{"parallel-pr-after": found, "start": alone})
        self.assertEqual((stopped["open"], stopped["go"]), (False, False), stopped)
        clean = self.ask_final_wired(start=start)
        self.assertNotIn("開いている PR と重なる", clean["text"], "重なりが無ければ重なりを開く訳にしない")

    def test_ask_final_takes_the_last_round_for_the_text_and_the_merge_values(self):
        """ask_final の script に、最初の試験・目と違う指紋と R2 を持つ輪の記録 eyes_back を渡すと、承認ノードの文と、返りの fingerprint・
        green_ok・eyes_ok・r2 がどちらも輪の記録の最後の周の物になる。輪の記録が落ちた記録なら最初の物のまま"""
        self.assertTrue((kit.BLOCKS / BLOCK / "src" / "eyesback.py").exists(), "周の頭の決めの src/eyesback.py が無い")
        eb = kit.load(BLOCK, "eyesback")
        fix_in = {"answer": None, "passes": [], "structure": None, "record": None, "judgment": None, "units": []}
        base_fixed = {"no_fix": False, "conflicts": [], "handoffs": [], "mismatched": [], "objection": "", "units": [], "groups": [],
                      "stages": [], "replan_items": [], "refixed": False, "skip_why": "", "more": []}
        def tests(diff, ok):
            return {"mode": "final", "ok": ok, "green": ok, "red_cause": "", "ran_steps": None, "baseline": None, "fingerprint": {"head": "h", "diff_hash": diff},
                    "test_outcomes": None, "evidence": None, "by": "test_cmd", "suites_line": "1 本", "log": "l", "baseline_line": "b", "reason": "",
                    "suite": None, "suite_note": "", "related": None, "report": []}
        def eyes(status, ok):
            row = {"status": status, "reason": f"{status} の訳"}
            return {"ok": ok, "r1": row, "r2": row, "r3": {"status": "pass", "reason": ""}, "r4": {"status": "pass", "reason": ""}, "questions": [],
                    "means_questions": [], "passes": [], "premise_check": None, "notes": [], "after": None, "dirty": 0, "escalate": 0, "after_ok": True,
                    "findings": [], "route": "stay", "route_why": "", "report": [], "sections": []}
        first_tests, first_eyes = tests("first", False), eyes("fix-needed", False)
        last_fixed = {**base_fixed, "units": [{"unit_id": "u9", "status": "fixed"}]}
        record = {"rows": [{"round": 1, "r1": "fix-needed", "r2": "pass", "items": [{"eye": "r1", "where": "a.py", "text": "写し"}]}],
                  "exit": "返す物が無い（どの目も通った）", "left": [], "fixed": last_fixed, "tests": tests("last", True), "eyes": eyes("pass", True),
                  "fingerprint": {"head": "h", "diff_hash": "last"}, "green_ok": True, "eyes_ok": True, "sealable": True, "item_claims": None}
        def ask(eyes_back):
            return self.run.script("ask_final", request=handed({}), fix_in=json.dumps(fix_in), fixed=json.dumps(base_fixed), judged="null",
                                   tests=json.dumps(first_tests), eyes=json.dumps(first_eyes), eyes_back=json.dumps(eyes_back), seal="null",
                                   spec_check="null", parallel_after="null", replan_review="null", replan_answer="null", widened="null",
                                   start_answer="null", record="null", final_gate="always", ports=self.ports())
        out = ask(record)
        self.assertEqual((out["fingerprint"], out["green_ok"], out["eyes_ok"], out["r2"]),
                         ({"head": "h", "diff_hash": "last"}, True, True, {"status": "pass", "reason": "pass の訳"}))
        self.assertIn("独立の目から修正の段へ 1 回返した。", out["text"])
        self.assertIn("通さなかった目: 無い", out["text"], "文の目の行も最後の周の目")
        self.assertIn(eb.HEAD, out["text"])
        fell = ask({**record, "exit": eb.EXITS["fell"], "fixed": None, "tests": None, "eyes": None, "sealable": False, "rows": []})
        self.assertEqual((fell["fingerprint"], fell["green_ok"], fell["eyes_ok"], fell["r2"]),
                         ({"head": "h", "diff_hash": "first"}, False, False, {"status": "fix-needed", "reason": "fix-needed の訳"}))
        self.assertIn(self.f_final().BACK_FELL, fell["reasons"])

    def f_final(self):
        return kit.load(BLOCK, "final")

    def test_scripts_do_not_fall_on_null_inputs(self):
        """どの script も with: の全部が null でも落ちず、止めの語 works:line-script の返りにする（L-G52・L-W63）"""
        names = {"ask_before_fix": ("rounds", "structure", "judge", "record", "ports", "request"),
                 "ask_replan": ("replan", "review", "old_plan", "items", "conflicts", "before_fix", "ports", "means"),
                 "ask_final": ("fix_in", "fixed", "judged", "tests", "eyes", "seal", "spec_check", "parallel_after", "replan_review",
                               "replan_answer", "widened", "start_answer", "record", "final_gate", "ports", "request")}
        for name, keys in names.items():
            with self.subTest(name=name):
                out = self.run.script(name, **dict.fromkeys(keys, "null"))
                self.assertIn("stop_reason", out)


if __name__ == "__main__":
    unittest.main()
