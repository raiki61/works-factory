"""line の承認ノード（docs/design/line.md の 2 節・6 節・8.1。src/gates.py・src/final.py と script ask_before_fix・before_fix_answer・
ask_replan・replan_answer・ask_final・eyes_in）。

元は今の tests/workflows/test_line.py の AskBeforeFixCase・AskReplanCase・AskFinalCase・AskFinalReadsCase・FinalGateCase・
UnattendedPolicyCallCase・LedgerAsksCase（docs/design/README.md の 9.5）。新しい形では修正前の承認ノードの軸・項目・聞かずに通した行を
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
    """計画の往復の受け皿の got（plan-out の返り）。既定は修正へ進む抜け方で、人に回しうる行は無い"""
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


class GatherCase(unittest.TestCase):
    """元 lib/tests/test_gate_axes.py の GatherCase（軸ごとの訳は事前審査の返りの行の why から）"""

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
           "questions": [], "spec_changed": [], "spec_unchecked": False, "objection": "", "rejudge_verdict": "", "rejudge": [],
           "split": "", "unproven": [], "amend": [], "delta": [], "stuck": [], "closure": [], "tests_left": [], "gates": [], "always": [],
           "beside_unread": [], "allowed_tests": [], "allowed_untouched": 0, "removed_tests": [], "untested": [], "structure_missing": "", "sealed": True, "seal_reason": "",
           "hash": "h", "deleted": [], "sealed_diff": "", "fenced": [], "after": [], "passes": [], "r2_inputs": [], "converge": [],
           "parallel_after": None, "held": [], "answered": [], "unmatched": [], "unread_holds": [], "lost_ties": [], "unread": []}
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
        """merge の apply に渡す値は受け皿の got から。封じが飛んだ・落ちた時は sealed_hash が空"""
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


class UnattendedPolicyCallCase(unittest.TestCase):
    def test_gate_scripts_leave_the_unattended_choice_to_the_policy(self):
        """#653: 修正前と案の直しの承認ノードは、無人の run の進むか止まるかを gates.passage に渡すだけで、止めの語を自分で組まない"""
        for path in (kit.BLOCKS / BLOCK / "src" / "gates.py", SCRIPTS / "ask_replan.py"):
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("passage(", text)
        self.assertNotIn("NEEDS_HUMAN", (SCRIPTS / "ask_replan.py").read_text(encoding="utf-8"))
        self.assertNotIn("NEEDS_HUMAN", (SCRIPTS / "ask_before_fix.py").read_text(encoding="utf-8"))


class ScriptCase(unittest.TestCase):
    """script を子のプロセスで回す（受け皿の got・line の node の返りを JSON の字で渡す）"""

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
        out = self.run.script("ask_before_fix", rounds=json.dumps(rounds(asks=[ask_row()])), structure="null",
                              judge=json.dumps({"judgment": None, "answer_ties": None, "materials": None}), record=record,
                              ports=self.ports())
        self.assertEqual((out["open"], out["go"], out["stop_reason"]), (True, True, ""), out)
        self.assertIn(NARROW, out["text"])
        self.assertIn("gate-before-fix", out["text"])

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

    def plans(self):
        old = self.put("plan-fields.json", {"round": 1, "fields": [{"unit_keys": ["u1"], "allowed_paths": ["a.py"], "out_of_scope": []}]})
        new = self.put("replan/plan-fields.json", {"round": 1, "fields": [{"unit_keys": ["u1"], "allowed_paths": ["a.py", "b.py"], "out_of_scope": []}]})
        return old, new

    def replan_got(self, new):
        return {"ok": True, "status": "ok", "reason": "", "plan": json.loads(new), "fix_plan": None, "ripple": None, "round": 1}

    def review_got(self, rows, status="ok"):
        return {"ok": status == "ok", "status": status, "reason": "", "replan": rows, "round": 1, "holes": None, "blocks": []}

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
                out = self.run.script("eyes_in", fix_in=json.dumps(fix_in),
                                      fixed=json.dumps({"eyes_due": due, "no_fix": False, "refixed": False}), start_answer="null",
                                      replan_review="null", judged=json.dumps({"judgment": None, "answer_ties": None, "materials": None}),
                                      record="null", ports=self.ports())
                self.assertEqual(out["merge"], want)
                self.assertEqual(out["policy"], "/p.md")
                self.assertEqual(out["asked"], [{"kind": "regression", "text": NARROW}])
                self.assertEqual(out["review"]["verdict"], "unread")

    def test_ask_final_without_a_seal_does_not_seal(self):
        """封じの受け皿が飛んだ（直す物が在る周）なら、差分を封じられなかったを開ける理由にし、置く段に hash を渡さない（閉じた側に倒れる）"""
        fix_in = {"answer": None, "passes": [], "structure": None, "record": None, "judgment": None, "units": []}
        fixed = {"no_fix": False, "conflicts": [], "handoffs": [], "mismatched": [], "objection": "", "units": [], "groups": [],
                 "stages": [], "replan_items": [], "refixed": False, "skip_why": ""}
        tests = {"ok": True, "green": True, "red_cause": "", "ran_steps": None, "by": "test_cmd", "suites_line": "1 本", "log": "l",
                 "baseline_line": "b", "reason": "", "fingerprint": {"head": "h", "diff_hash": "d"}}
        out = self.run.script("ask_final", fix_in=json.dumps(fix_in), fixed=json.dumps(fixed), judged="null", tests=json.dumps(tests),
                              eyes="null", seal="null", spec_check="null", parallel_after="null", replan_review="null",
                              replan_answer="null", widened="null", start_answer="null", record="null", final_gate="when_needed",
                              ports=self.ports())
        self.assertEqual(out["stop_reason"], "", out)
        self.assertTrue(any("差分を封じられなかった" in r for r in out["reasons"]), out["reasons"])
        self.assertEqual((out["sealed_hash"], out["green_ok"], out["fingerprint"]), ("", True, tests["fingerprint"]))
        self.assertTrue((self.run.artifacts / "gates" / "final-gate.md").is_file())

    def test_scripts_do_not_fall_on_null_inputs(self):
        """どの script も with: の全部が null でも落ちず、止めの語 works:line-script の返りにする（L-G52・L-W63）"""
        names = {"ask_before_fix": ("rounds", "structure", "judge", "record", "ports"),
                 "ask_replan": ("replan", "review", "old_plan", "items", "conflicts", "before_fix", "ports"),
                 "ask_final": ("fix_in", "fixed", "judged", "tests", "eyes", "seal", "spec_check", "parallel_after", "replan_review",
                               "replan_answer", "widened", "start_answer", "record", "final_gate", "ports")}
        for name, keys in names.items():
            with self.subTest(name=name):
                out = self.run.script(name, **dict.fromkeys(keys, "null"))
                self.assertIn("stop_reason", out)


if __name__ == "__main__":
    unittest.main()
