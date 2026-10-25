"""計画の往復の記録と止め（元 lib/tests/test_converge.py の、line の src/rounds.py へ移る部分。integration.md 4.2-9）。

元の試験は盤面 b（round・dir・work・trace）に lib/converge.py の record_pass・read・stuck_reason・lines を当てた。line の記録は
盤面を持たず、記録の dict と place のパスを受けるので、元の試験の口の形を持つ小さな写し C（下の Adapter）を通して同じ値を照らす:
record_pass は pass.json の材料の形（{review, answers, resolved, synergy, hits, origins, refs, push, files, plan}）に詰め直して
src.rounds.record_pass に渡し、記録を place のファイルに書く。note_plan・note_answers は元どおり次の往復の材料に置く。
元の試験のうち lib に残る読み口（splice・owed_faces・revise_section・answer_gaps・resolved_gaps など）と trace の行を見る物は、
lib/tests に残るので写さない。
"""
import json
import pathlib
import tempfile
import types
import unittest

from tests.blocks import kit

rounds = kit.load("line", "rounds")
import converge  # noqa: E402  （KEEP の読み口 plan_rows・central_keys と語の定数）


class Adapter(types.SimpleNamespace):
    """元の converge の口の形で src.rounds を呼ぶ写し（試験の中だけ）"""

    def __getattr__(self, name):
        for mod in (rounds, converge):
            if hasattr(mod, name):
                return getattr(mod, name)
        raise AttributeError(name)

    @staticmethod
    def read(b):
        doc = rounds.read(b.dir / rounds_files.PLAN_CONVERGE)
        doc.setdefault("open", {"answers": b.open} if b.open else {})
        if b.plan is not None:
            doc["plan"] = b.plan
        return doc

    @staticmethod
    def pass_no(b):
        return len(rounds.read(b.dir / rounds_files.PLAN_CONVERGE)["passes"]) + 1

    @staticmethod
    def note_plan(b, rows):
        b.plan = converge.plan_rows(rows)

    @staticmethod
    def note_answers(b, answers):
        b.open = list(answers)

    @staticmethod
    def record_pass(b, review, *, resolved, files, synergy=None, hits=None, origins=None, at_cap=False, refs=None, push=None):
        doc = rounds.read(b.dir / rounds_files.PLAN_CONVERGE)
        got = {"review": review, "answers": b.open, "resolved": resolved, "synergy": synergy, "hits": hits, "origins": origins,
               "refs": refs, "push": push, "files": files, **({"plan": b.plan} if b.plan is not None else {})}
        row = rounds.record_pass(doc, got, at_cap=at_cap, dest=b.dir / rounds_files.PLAN_CONVERGE_FILES.format(k=len(doc["passes"]) + 1))
        rounds.write(b.dir / rounds_files.PLAN_CONVERGE, doc)
        b.open = []
        return row

    @staticmethod
    def stuck_reason(b):
        return rounds.stuck_reason(rounds.read(b.dir / rounds_files.PLAN_CONVERGE), b.work(C.PASS_DIR))

    @staticmethod
    def lines(b):
        return rounds.lines(rounds.read(b.dir / rounds_files.PLAN_CONVERGE), b.work(C.PASS_DIR))

    @staticmethod
    def open_items(b):
        return rounds.open_items(rounds.read(b.dir / rounds_files.PLAN_CONVERGE))


rounds_files = kit.load("line", "files")
rounds = kit.load("line", "rounds")
C = Adapter(PASS_DIR=converge.PASS_DIR, RECORD=converge.RECORD)


class BoardCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)
        self.b = self.board(1)

    def board(self, rnd):
        folder = self.tmp / f"r{rnd}"
        folder.mkdir(parents=True, exist_ok=True)
        return types.SimpleNamespace(round=rnd, dir=folder, work=lambda name: folder / name, plan=None, open=[])

    def src(self, name, text):
        p = self.tmp / "src" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return str(p)

    def record(self, keys, *, resolved=(), files=None, extra=(), **kw):
        return C.record_pass(self.b, {"faces": [face(k) for k in keys] + list(extra)}, resolved=list(resolved),
                             files=files or {}, **kw)


def face(key, severity="block", kind="regression", units=("u",), reach=None):
    """穴の行（reach を渡さなければ札の無い行。札の無い行は中央と読む）"""
    return {"key": key, "kind": kind, "where": f"{key} の場所", "why": f"{key} が穴である理由", "severity": severity,
            "unit_keys": list(units), **({C.REACH: reach} if reach else {})}


def edge(key, **kw):
    """端（peripheral）の札の穴の行"""
    return face(key, reach=C.PERIPHERAL, **kw)


def passed(*passes):
    """decide に渡す往復の行の並び（往復ごとに face の並び。blocks は block の face の key）"""
    return [{"blocks": [f["key"] for f in faces], "faces": faces} for faces in passes]


def answer(key, handled="fixed", how="案の項目 1 の手順を直した"):
    return {"key": key, "handled": handled, "how": how}


def row(*units, approach="案の手順"):
    return {"unit_keys": list(units), "approach": approach}


class DecideCase(unittest.TestCase):
    def test_no_block_is_clean(self):
        self.assertEqual(C.decide([{"blocks": ["a"]}, {"blocks": []}]), C.CLEAN)

    def test_new_central_blocks_go_again_without_counting(self):
        """中央の新しい block が出る往復は、開いた block の数が前より減らなくても増えても、往復の数に依らず AGAIN（数の比べで
        止めない）。札の無い face と faces の無い古い行は中央と読む"""
        for passes in (passed([face("a")], [face("b")]), passed([face("a"), face("b")], [face("c"), face("d"), face("e")]),
                       passed(*([face(f"k{n}")] for n in range(1, 8))),
                       passed([edge("a")], [face("b", reach="breaks_fix")]),
                       [{"blocks": ["a"]}, {"blocks": ["b"]}]):
            with self.subTest(passes=[p["blocks"] for p in passes]):
                self.assertEqual(C.decide(passes), C.AGAIN)
        # 同じ中央の key が戻る往復は PERSISTED
        self.assertEqual(C.decide(passed([face("a"), face("b")], [face("a"), face("c")])), C.PERSISTED)

    def test_peripheral_only_blocks_settle(self):
        """2 往復目から、最後の往復の block が端だけなら SETTLED（直しへ進む。proceeds が真）。1 往復目の端の block は AGAIN
        （一度は修正案の役に返す）"""
        self.assertEqual(C.decide(passed([edge("a")])), C.AGAIN)
        got = C.decide(passed([face("a")], [edge("b"), edge("c")]))
        self.assertEqual(got, C.SETTLED)
        self.assertTrue(C.proceeds(got))
        self.assertTrue(C.proceeds(C.CLEAN))
        for word in (C.AGAIN, C.PERSISTED, C.UNSETTLED):
            self.assertFalse(C.proceeds(word), word)

    def test_peripheral_block_that_persists_does_not_stop(self):
        """前の往復から続く block でも、今の往復の札が端なら PERSISTED にしない（端だけなら SETTLED、中央の新しい block が並べば
        AGAIN）。前に中央だった key を端に付け替えた往復も同じ"""
        self.assertEqual(C.decide(passed([face("a"), edge("b")], [edge("b")])), C.SETTLED)
        self.assertEqual(C.decide(passed([face("a")], [edge("a")])), C.SETTLED)
        self.assertEqual(C.decide(passed([edge("b")], [edge("b"), face("c")])), C.AGAIN)

    def test_central_keys_read_the_last_face_of_each_key(self):
        """key ごとの札は、その key を最後に挙げた往復の face から引く。faces に行の無い key は中央"""
        passes = passed([edge("a"), face("b", reach="loses_behavior")], [face("a", reach="against_policy"), edge("b")])
        self.assertEqual(C.central_keys(passes, ["a", "b", "z"]), ["a", "z"])
        self.assertEqual(C.REACH_SCHEMA["enum"], [*C.CENTRAL, C.PERIPHERAL])

    def test_block_from_any_earlier_pass_persists(self):
        self.assertEqual(C.decide([{"blocks": ["a"]}, {"blocks": ["a", "b"]}]), C.PERSISTED)
        self.assertEqual(C.decide([{"blocks": ["a", "b"]}, {"blocks": ["c"]}, {"blocks": ["a"]}]),
                         C.PERSISTED)

    def test_decreasing_blocks_go_on_regardless_of_pass_count(self):
        """中央の block が 3 → 2 → 1 と出続ける列は、往復の数に依らず続く（AGAIN）"""
        passes = [{"blocks": ["a", "b", "c"]}, {"blocks": ["d", "e"]}, {"blocks": ["f"]}]
        self.assertEqual(C.decide(passes), C.AGAIN)
        self.assertEqual(C.decide(passes[:2]), C.AGAIN)

    def test_block_faces_keep_order_and_drop_repeats(self):
        got = C.block_faces({"faces": [face("a"), face("s", severity="suggest"), face("b"), face("a")]})
        self.assertEqual([f["key"] for f in got], ["a", "b"])


class RecordCase(BoardCase):
    def test_answers_move_from_open_to_pass(self):
        self.record(["a"])
        C.note_answers(self.b, [answer("a")])
        self.assertEqual(C.read(self.b)["open"]["answers"], [answer("a")])
        row = self.record([], resolved=["a"])
        self.assertEqual((row["answers"], row["resolved"], row["outcome"]), ([answer("a")], ["a"], C.CLEAN))
        self.assertEqual(C.read(self.b)["open"], {})
        self.assertIsNone(C.held(C.read(self.b)))

    def test_stash_rejects_go_to_last_pass(self):
        self.record(["a"])
        rows = [{"role": "plan", "at": "1", "reason": "拒否 1"}, {"role": "plan", "at": "2", "reason": "拒否 2"}]   # 拒否の行の形（lib/rolekit）
        C.stash_rejects(self.b, rows[:1])
        C.stash_rejects(self.b, rows[1:])
        self.assertEqual(C.read(self.b)["passes"][-1]["rejects"], rows)

    def test_new_central_blocks_go_on_past_three_passes(self):
        """中央の新しい block が出る限り、往復の数では止めない（3 往復目も 5 往復目も AGAIN。直しの役に返す行は最後の往復）"""
        for k, keys in enumerate((["a1", "a2", "a3", "a4", "a5"], ["b1", "b2", "b3", "b4"], ["c1", "c2", "c3"], ["d1", "d2"], ["e1"]), 1):
            with self.subTest(pass_=k):
                self.assertEqual(self.record(keys)["outcome"], C.AGAIN)
                self.assertEqual(C.held(C.read(self.b))["pass"], k)

    def test_decreasing_pass_stops_only_at_loop_cap(self):
        """中央の新しい block が出る 3 往復目は、輪の安全の上限の周（at_cap）として記録した時だけ止まる（UNSETTLED・capped。held が None）"""
        self.record(["a", "b", "c"])
        self.record(["d", "e"])
        row = self.record(["f"], at_cap=True)
        self.assertEqual((row["outcome"], row["capped"]), (C.UNSETTLED, True))
        self.assertIsNone(C.held(C.read(self.b)))


class TextCase(BoardCase):
    def test_stuck_reason_names_keys_and_record(self):
        self.assertEqual(C.stuck_reason(self.b), "")
        self.record(["key-alpha"])
        self.assertEqual(C.stuck_reason(self.b), "")
        self.record(["key-alpha", "key-beta"])
        why = C.stuck_reason(self.b)
        self.assertEqual(why, C.PERSISTED_WHY.format(keys="key-alpha", n=2,
                                                             path=self.b.work(C.PASS_DIR)))
        self.record([], resolved=["key-alpha", "key-beta"])
        self.assertEqual(C.stuck_reason(self.b), "")

    def test_stuck_reason_unsettled(self):
        """UNSETTLED は輪の安全の上限の周（at_cap）の止まりだけ（中央の新しい block が出る 2 往復目は at_cap でなければ AGAIN）"""
        self.record(["key-a1"])
        self.assertEqual(self.record(["key-b1"])["outcome"], C.AGAIN)
        b = self.b = self.board(2)
        self.record(["key-a1"])
        self.record(["key-b1"], at_cap=True)
        why = C.stuck_reason(b)
        self.assertTrue(why.startswith(C.UNSETTLED_WHY.format(keys="key-b1", n=2, path=self.b.work(C.PASS_DIR))), why)
        self.assertIn("1 往復目 1 → 2 往復目 1", why)

    def test_capped_pass_stops_with_cap_reason(self):
        """輪の安全の上限の周（at_cap）に着いて、まだ AGAIN だった往復は UNSETTLED で止まり、行に capped が立つ。関所の理由は上限に
        届いた事実を工場の不具合として言い（中央の新しい穴が出続ける往復も普通は届かない）、往復ごとの数を添える。減らなかったとは
        言わず、頭の行の結末の名札も減らないと言わない。CLEAN と PERSISTED の往復は at_cap でもそのまま"""
        self.record(["key-a1", "key-a2"])
        row = self.record(["key-b1"], at_cap=True)
        self.assertEqual((row["outcome"], row["capped"]), (C.UNSETTLED, True))
        self.assertIsNone(C.held(C.read(self.b)))
        why = C.stuck_reason(self.b)
        self.assertTrue(why.startswith(C.UNSETTLED_WHY.split("（往復ごとに")[0].format(n=2)), why)
        self.assertIn(C.CAP_WHY.format(n=2, counts="1 往復目 2 → 2 往復目 1"), why)
        self.assertNotIn("前の往復より減らなかった", why)
        self.assertIn("工場の不具合", why)
        head = C.lines(self.b)[0]
        self.assertNotIn("減らない", head)
        self.assertIn("（記録の名 unsettled）", head)
        b = self.board(2)
        C.record_pass(b, {"faces": [face("key-a1")]}, resolved=[], files={})
        row = C.record_pass(b, {"faces": []}, resolved=["key-a1"], files={}, at_cap=True)
        self.assertEqual(row["outcome"], C.CLEAN)
        self.assertNotIn("capped", row)
        b = self.board(3)
        C.record_pass(b, {"faces": [face("key-a1")]}, resolved=[], files={})
        row = C.record_pass(b, {"faces": [face("key-a1"), face("key-b1")]}, resolved=[], files={}, at_cap=True)
        self.assertEqual(row["outcome"], C.PERSISTED)
        self.assertNotIn("capped", row)
        self.assertNotIn(C.CAP_WHY.split("（")[0].format(n=2), C.stuck_reason(b))

    def test_capped_marks_only_the_stop_at_the_cap(self):
        """止まった壁打ちを推しで越えてよいかの決め（gatepolicy.stuck_pushable）が読む、上限の周で止めたかの事実"""
        def doc(rnd, passes, plan=()):
            b = self.board(rnd)
            if plan:
                C.note_plan(b, [row(u) for u in plan])
            for keys, cap in passes:
                units = (lambda k: ["u1"] if k.startswith("key-a") else ["u2"]) if plan else (lambda k: ["u"])
                C.record_pass(b, {"faces": [face(k, units=units(k)) for k in keys]}, resolved=[], files={}, at_cap=cap)
            return C.read(b)
        again = doc(2, [(["key-a1"], False)])
        self.assertEqual(again["outcome"], C.AGAIN)
        self.assertFalse(C.capped(again))
        clean = doc(3, [([], False)])
        self.assertEqual(clean["outcome"], C.CLEAN)
        self.assertFalse(C.capped(clean))
        again = doc(4, [(["key-a1"], False), (["key-b1"], False)])
        self.assertEqual(again["outcome"], C.AGAIN, "中央の新しい block の往復は止まらない（数で止めない）")
        self.assertFalse(C.capped(again))
        persisted = doc(5, [(["key-a1"], False), (["key-a1", "key-b1"], False)])
        self.assertEqual(persisted["outcome"], C.PERSISTED)
        self.assertFalse(C.capped(persisted))
        capped = doc(6, [(["key-a1", "key-a2"], False), (["key-b1"], True)])
        self.assertEqual((capped["outcome"], capped["passes"][-1]["capped"]), (C.UNSETTLED, True))
        self.assertTrue(C.capped(capped))
        held_passes = [(["key-a1", "key-b1", "key-b2", "key-b3"], False), (["key-a1", "key-b4", "key-b5"], False), (["key-b6"], True)]
        held = doc(7, held_passes, plan=("u1", "u2"))
        self.assertEqual((held["outcome"], held["passes"][-1]["capped"]), (C.PERSISTED, True))
        self.assertTrue(C.capped(held), "保留の項目が在る上限の止まりは outcome が PERSISTED でも上限の止まり")
        self.assertFalse(C.capped({"outcome": None, "passes": []}))

    def test_capped_stop_names_open_counts_per_pass(self):
        """輪の上限の周で止めた時は、上限に届いた句に往復ごとの開いた数を添える（数の比べで止める句は無い）"""
        b = self.board(2)
        for keys, cap in ((["key-a1", "key-a2", "key-a3"], False), (["key-b1", "key-b2"], False), (["key-c1"], True)):
            C.record_pass(b, {"faces": [face(k) for k in keys]}, resolved=[], files={}, at_cap=cap)
        why = C.stuck_reason(b)
        self.assertTrue(why.startswith(C.UNSETTLED_WHY.split("（往復ごとに")[0].format(n=3)), why)
        self.assertIn(C.CAP_WHY.format(n=3, counts="1 往復目 3 → 2 往復目 2 → 3 往復目 1"), why)
        self.assertNotIn("開いた block の数", why)

    def test_lines_head_names_first_pass_share(self):
        """1 回目の block と後の回の見落としから、1 回目に出た割合を頭の行に出す。割合は閉じた項目の取りこぼしを数えない上限と書く。
        見落としの申告は項目の控えの事実（行の変わらない項目の block）で照らして採る"""
        C.note_plan(self.b, [row("u1")])
        self.record(["key-a1", "key-a2"])
        C.record_pass(self.b, {"faces": [face("key-b1")]}, resolved=["key-a1", "key-a2"], files={},
                             origins=[{"key": "key-b1", "origin": C.ORIGIN_MISSED}])
        head = C.lines(self.b)[0]
        for part in ("1 回目の block 2 件", "見落とし 1", "1 回目に出た割合は 2/3", "閉じた項目の取りこぼしは数えない上限",
                     "run の後で見つかった穴は割合に入らない"):
            self.assertIn(part, head)

    def test_lines_head_without_blocks_says_none(self):
        C.record_pass(self.b, {"faces": []}, resolved=[], files={})
        head = C.lines(self.b)[0]
        self.assertIn(C.LINE_NO_BLOCK, head)
        self.assertNotIn("0/0", head)
        self.assertNotIn("1 回目の block", head)

    def test_lines_summarize_passes(self):
        self.assertEqual(C.lines(self.b), [])
        self.record(["key-alpha"])
        C.note_answers(self.b, [answer("key-alpha")])
        self.record(["key-alpha"])
        got = C.lines(self.b)
        path = self.b.work(C.PASS_DIR)
        share = C.LINE_SHARE.format(first=1, missed=0, introduced=0, rephrased=0, unsplit=0, share="1/1", total="1/1")
        self.assertEqual(got[0], C.LINE_HEAD.format(n=2, word="同じ block が続いた", outcome="persisted",
                                                           persists="key-alpha", share=share, path=path))
        self.assertEqual(got[1:], [
            C.LINE_PASS.format(k=1, keys="key-alpha", f=0, d=0, resolved="無い", down="無い"),
            C.LINE_PASS.format(k=2, keys="key-alpha", f=1, d=0, resolved="無い", down="無い")])

    def test_lines_name_blocks_downgraded_to_suggest(self):
        """前の往復の block を審査が suggest に下げた key は、その往復の行に出る（block から消えたのが resolved でなく格下げだと
        報告で分かる。Task 1 の持ち越し m2）。前の往復で block でなかった suggest は出さない"""
        self.record(["key-alpha"])
        C.note_answers(self.b, [answer("key-alpha")])
        self.record([], extra=[face("key-alpha", severity="suggest"), face("key-gamma", severity="suggest")])
        got = C.lines(self.b)
        self.assertEqual(got[2], C.LINE_PASS.format(k=2, keys="無い", f=1, d=0, resolved="無い", down="key-alpha"))
        self.assertIn("key-alpha", got[2])
        self.assertNotIn("key-gamma", got[2])

    def test_lines_name_central_lowered_to_peripheral(self):
        """前の往復で中央だった block を審査が peripheral に付け替えた key は、その往復の行の『下げた key』に出る（前から端だった
        block は出さない）"""
        self.record([], extra=[face("key-alpha"), edge("key-beta")])
        C.note_answers(self.b, [answer("key-alpha"), answer("key-beta")])
        self.record([], extra=[edge("key-alpha"), edge("key-beta")])
        got = C.lines(self.b)
        self.assertEqual(got[2], C.LINE_PASS.format(k=2, keys="key-alpha、key-beta", f=2, d=0, resolved="無い", down="key-alpha"))
        self.assertIn("（記録の名 settled）", got[0])


class ItemsCase(BoardCase):
    """項目ごとの壁打ち（線の木の段 1。設計 docs/plans/2026-10-06-tree-line.md の 2.3 の 5）: block の無い項目は閉じて次の往復で
    審査も直しもしない・同じ中央の block が続いた項目は保留にしてほかの項目は中央の新しい block が出る間進める・相乗りの block は
    名指した項目だけを開き直す"""

    def setUp(self):
        super().setUp()
        C.note_plan(self.b, [row("u1"), row("u2")])

    def review(self, faces, *, resolved=(), synergy=()):
        return C.record_pass(self.b, {"faces": faces}, resolved=list(resolved), files={}, synergy=list(synergy))

    def second_pass(self, rnd, faces, *, origins=(), resolved=("key-a1",), plan=None):
        """項目 1 に block を出した 1 往復目の後、案を plan に置き直して（None なら据え置き）2 往復目を記録する（盤面, 2 往復目の行）"""
        b = self.board(rnd)
        C.note_plan(b, [row("u1"), row("u2")])
        C.record_pass(b, {"faces": [face("key-a1", units=["u1"])]}, resolved=[], files={})
        if plan is not None:
            C.note_plan(b, plan)
        got = C.record_pass(b, {"faces": faces}, resolved=list(resolved), files={}, origins=list(origins))
        return b, got

    def states(self, got):
        return [it["state"] for it in got["items"]]

    def test_clean_item_closes_and_blocked_item_goes_again(self):
        got = self.review([face("key-a1", units=["u1"])])
        self.assertEqual(self.states(got), [C.OPEN, C.CLOSED])
        self.assertEqual(got["items"][0]["blocks"], ["key-a1"])
        self.assertEqual(got["outcome"], C.AGAIN)
        self.assertEqual(C.open_items(self.b), [1])

    def test_closed_item_stays_closed_and_all_closed_is_clean(self):
        self.review([face("key-a1", units=["u1"])])
        got = self.review([], resolved=["key-a1"])
        self.assertEqual(self.states(got), [C.CLOSED, C.CLOSED])
        self.assertEqual(got["outcome"], C.CLEAN)

    def test_persisted_item_is_held_and_others_go_on(self):
        self.review([face("key-a1", units=["u1"]), face("key-b1", units=["u2"])])
        got = self.review([face("key-a1", units=["u1"]), face("key-b2", units=["u2"])])
        self.assertEqual(self.states(got), [C.HELD, C.OPEN])
        self.assertEqual(got["outcome"], C.AGAIN, "保留の項目のほかに開いた項目が在れば、中央の新しい block が出る間は進む")
        self.assertEqual(C.open_items(self.b), [2])
        got = self.review([], resolved=["key-b2"])
        self.assertEqual(self.states(got), [C.HELD, C.CLOSED])
        self.assertEqual(got["outcome"], C.PERSISTED)

    def test_loop_cap_with_held_item_is_persisted_and_without_is_unsettled(self):
        """中央の新しい block が出る 3 往復目は、輪の安全の上限の周（at_cap）として記録した時だけ止まる。止まる時の抜け方は、保留の項目が
        在れば PERSISTED・無ければ UNSETTLED（at_cap でなければ AGAIN）"""
        held_passes = ([face("key-a1", units=["u1"]), *[face(f"key-b{n}", units=["u2"]) for n in (1, 2, 3)]],
                       [face("key-a1", units=["u1"]), face("key-b4", units=["u2"]), face("key-b5", units=["u2"])],
                       [face("key-b6", units=["u2"])])
        plain_passes = tuple([face(k, units=["u1"]) for k in keys]
                             for keys in (("key-c1", "key-c2", "key-c3"), ("key-c4", "key-c5"), ("key-c6",)))
        for rnd, passes, at_cap, want in ((2, held_passes, False, C.AGAIN), (3, held_passes, True, C.PERSISTED),
                                          (4, plain_passes, False, C.AGAIN), (5, plain_passes, True, C.UNSETTLED)):
            with self.subTest(held=passes is held_passes, at_cap=at_cap):
                b = self.board(rnd)
                C.note_plan(b, [row("u1"), row("u2")])
                for n, faces in enumerate(passes, 1):
                    got = C.record_pass(b, {"faces": faces}, resolved=[], files={}, at_cap=at_cap and n == len(passes))
                self.assertEqual(got["outcome"], want)
                self.assertIs(got.get("capped", False), at_cap)

    def test_held_item_beside_new_central_goes_again(self):
        """保留の項目のほかに中央の新しい block の出た開いた項目が在れば、開いた block の数が減らなくても AGAIN: 1 往復目は u1・u2・u3
        に 1 件ずつ、2 往復目は u1 が同じ block（保留）で u2・u3 が新しい block、3 往復目は u2 だけ。数で止めず、関所の理由も無い"""
        C.note_plan(self.b, [row("u1"), row("u2"), row("u3")])
        self.review([face("key-a1", units=["u1"]), face("key-b1", units=["u2"]), face("key-c1", units=["u3"])])
        got = self.review([face("key-a1", units=["u1"]), face("key-b2", units=["u2"]), face("key-c2", units=["u3"])])
        self.assertEqual((self.states(got), got["outcome"]), ([C.HELD, C.OPEN, C.OPEN], C.AGAIN))
        got = self.review([face("key-b3", units=["u2"])], resolved=["key-b2", "key-c2"])
        self.assertEqual((self.states(got), got["outcome"]), ([C.HELD, C.OPEN, C.CLOSED], C.AGAIN))
        got = self.review([face("key-b4", units=["u2"])], resolved=["key-b3"])
        self.assertEqual((self.states(got), got["outcome"]), ([C.HELD, C.OPEN, C.CLOSED], C.AGAIN))
        self.assertEqual(C.stuck_reason(self.b), "")

    def test_stuck_keys_uncited_and_stuck_faces_of_a_held_item(self):
        """元 test_review_section_names_held_cites_for_the_stuck_push の止めた key の部分（src.rounds の stuck_keys・uncited・stuck_faces）:
        項目 1 を保留にした後、保留の項目のほかの開いた block が端だけの往復で止まる（PERSISTED）。stuck_keys は保留の項目の前の往復の
        block key-a1 と開いた項目の block key-b3。止まった時の推しの note は、止めた key と保留・開いた項目の『項目 n』を全部引けば
        uncited が空・欠けた物を名指す（『項目 12』と key-a12 は引用に数えない）。止まっていない控えは照らさない。保留の項目の前の往復の
        block は stuck_faces が印 HELD_MARK つきで返し、block_faces は数えない。
        元の review_section（HELD_CITES を事前審査の役に貼る節）は plan-review の src/material.py と md へ移ったので、ここでは見ない"""
        self.review([face("key-a1", units=["u1"]), face("key-b1", units=["u2"])])
        self.review([face("key-a1", units=["u1"]), face("key-b2", units=["u2"])])
        doc = C.read(self.b)
        self.assertEqual((C.stuck_keys(doc), C.uncited("何でも", doc), C.stuck_faces(doc)), ([], [], []),
                         "止まっていない控えは照らさない")
        got = self.review([edge("key-b3", units=["u2"])], resolved=["key-b2"])
        self.assertEqual(got["outcome"], C.PERSISTED, "保留の項目のほかの開いた block が端だけの往復")
        doc = C.read(self.b)
        self.assertEqual(C.stuck_keys(doc), ["key-a1", "key-b3"])
        self.assertIn("key-a1、key-b3", C.stuck_reason(self.b), "stuck_reason も同じ式で止めた key を出す")
        self.assertEqual(C.uncited("key-a1 と key-b3 を項目 1・項目 2 の修正の中で片付ける", doc), [])
        self.assertEqual(C.uncited("key-b3 を項目 2 の修正で片付ける", doc), ["key-a1", "項目 1"])
        self.assertEqual(C.uncited("key-a12 と key-b3 を項目 12・項目 2 で片付ける", doc), ["key-a1", "項目 1"])
        self.assertEqual(C.uncited("key-a1・key-b3・項目 1・項目 2", doc), [])
        held = C.stuck_faces(doc)
        self.assertEqual([f["key"] for f in held], ["key-a1"], "最後の往復の faces に在る key-b3 は足さない")
        self.assertEqual(held[0], {**face("key-a1", units=["u1"]), C.HELD_MARK: True})
        self.assertEqual(converge.block_faces({"faces": held}), [])

    def test_items_go_again_while_new_central_blocks_come(self):
        """開いた項目に中央の新しい block が出続ける間は、開いた数が減らなくても往復の数に依らず AGAIN。端だけになった往復で SETTLED"""
        for k in range(1, 6):
            got = self.review([face(f"key-a{k}", units=["u1"]), face(f"key-b{k}", units=["u2"])],
                              resolved=[f"key-a{k - 1}", f"key-b{k - 1}"] if k > 1 else [])
            self.assertEqual(got["outcome"], C.AGAIN, k)
        got = self.review([edge("key-a6", units=["u1"])], resolved=["key-a5", "key-b5"])
        self.assertEqual((self.states(got), got["outcome"]), ([C.OPEN, C.CLOSED], C.SETTLED))
        self.assertIsNone(C.held(C.read(self.b)), "SETTLED の往復は修正案の役に返さない")

    def test_peripheral_persist_keeps_item_open_and_settles(self):
        """前の往復から続く block でも端の札なら項目を保留にせず開いたまま。開いた block が端だけの 2 往復目は SETTLED、保留の項目が
        並べば PERSISTED"""
        self.review([face("key-a1", units=["u1"]), edge("key-b1", units=["u2"])])
        got = self.review([edge("key-a1", units=["u1"]), edge("key-b1", units=["u2"])])
        self.assertEqual((self.states(got), got["outcome"]), ([C.OPEN, C.OPEN], C.SETTLED))
        b = self.board(2)
        C.note_plan(b, [row("u1"), row("u2")])
        C.record_pass(b, {"faces": [face("key-a1", units=["u1"]), face("key-b1", units=["u2"])]}, resolved=[], files={})
        got = C.record_pass(b, {"faces": [face("key-a1", units=["u1"]), edge("key-b2", units=["u2"])]},
                                   resolved=["key-b1"], files={})
        self.assertEqual((self.states(got), got["outcome"]), ([C.HELD, C.OPEN], C.PERSISTED))

    def test_synergy_block_reopens_named_closed_item(self):
        self.review([face("key-a1", units=["u1"])])
        got = self.review([face("key-s1", units=["u2"])], resolved=["key-a1"], synergy=["key-s1"])
        self.assertEqual(self.states(got), [C.CLOSED, C.OPEN])
        self.assertTrue(got["items"][1]["reopened"])
        self.assertEqual(got["synergy"], ["key-s1"])
        self.assertEqual(got["outcome"], C.AGAIN)

    def test_face_naming_no_item_counts_for_every_reviewed_item(self):
        got = self.review([face("key-x1", units=["somewhere"])])
        self.assertEqual(self.states(got), [C.OPEN, C.OPEN])

    def splice(self, rows):
        self.assertTrue(hasattr(converge, "splice"), "C.splice が無い")
        return C.splice(C.read(self.b), rows)

    def hold_second(self):
        """項目 2（u2）が保留・項目 1（u1）が開いた往復の後の控え"""
        self.review([face("key-a1", units=["u1"]), face("key-b1", units=["u2"])])
        got = self.review([face("key-a2", units=["u1"]), face("key-b1", units=["u2"])])
        self.assertEqual(self.states(got), [C.OPEN, C.HELD])

    def open_and_closed_suggests(self):
        """項目 1（u1）に block a と suggest t、項目 2（u2）に suggest s だけ: 項目 1 が開き、項目 2 は閉じる"""
        got = self.review([face("a", units=["u1"]), face("t", severity="suggest", units=["u1"]),
                           face("s", severity="suggest", units=["u2"])])
        self.assertEqual(self.states(got), [C.OPEN, C.CLOSED])
        return got

    def test_new_block_on_changed_item_takes_given_origin(self):
        """行の変わった項目の新しい block は渡した語を採り、渡さない key は unsplit。行の変わっていない項目 1 への introduced も、
        項目 2 が変わったので採る"""
        origins = [{"key": "key-b1", "origin": C.ORIGIN_INTRODUCED}, {"key": "key-c1", "origin": C.ORIGIN_INTRODUCED}]
        b, got = self.second_pass(2, [face("key-b1", units=["u2"]), face("key-b2", units=["u2"]), face("key-c1", units=["u1"])],
                                  origins=origins, plan=[row("u1"), row("u2", approach="直した")])
        self.assertEqual(got["origins"], {"key-b1": C.ORIGIN_INTRODUCED, "key-b2": C.ORIGIN_UNSPLIT,
                                          "key-c1": C.ORIGIN_INTRODUCED})
        self.assertEqual(got["origins_claimed"], [])
        self.assertIn(C.LINE_SHARE.format(first=1, missed=0, introduced=2, rephrased=0, unsplit=1, share="1/2", total="1/4"),
                      C.lines(b)[0])

    def test_rephrased_block_is_not_counted_new(self):
        """前の block の言い換え（of が前の往復の block で、今の往復の resolved に在る）は rephrased で残り、頭の行は言い換え 1 件と出す"""
        claim = {"key": "key-a2", "origin": C.ORIGIN_REPHRASED, "of": "key-a1"}
        b, got = self.second_pass(2, [face("key-a2", units=["u1"])], origins=[claim])
        self.assertEqual((got["origins"], got["origins_claimed"]), ({"key-a2": C.ORIGIN_REPHRASED}, []))
        self.assertIn(C.LINE_SHARE.format(first=1, missed=0, introduced=0, rephrased=1, unsplit=0, share="1/1", total="1/1"),
                      C.lines(b)[0])

    def test_rephrased_without_resolved_prior_key_falls_back(self):
        """of が前の往復に無い key・今の往復の resolved に無い key の rephrased は採らず、既定（行が変わっていなければ missed）に
        落ちて、申告は origins_claimed に残る"""
        for rnd, of, resolved in ((2, "key-zzz", ("key-a1",)), (3, "key-a1", ()), (4, "key-zzz", ("key-zzz",))):
            claim = {"key": "key-a2", "origin": C.ORIGIN_REPHRASED, "of": of}
            with self.subTest(of=of, resolved=resolved):
                _, got = self.second_pass(rnd, [face("key-a2", units=["u1"])], origins=[claim], resolved=resolved)
                self.assertEqual((got["origins"], got["origins_claimed"]), ({"key-a2": C.ORIGIN_MISSED}, [claim]))
        b = self.board(5)   # 項目の控えの無い往復は、申告が無ければ分けられない
        C.record_pass(b, {"faces": [face("key-a1")]}, resolved=[], files={})
        got = C.record_pass(b, {"faces": [face("key-b1")]}, resolved=["key-a1"], files={})
        self.assertEqual(got["origins"], {"key-b1": C.ORIGIN_UNSPLIT})

    def test_block_on_new_item_defaults_introduced(self):
        """単位の組を組み直した新しい id の項目だけに当たる新しい block は、出自を渡さなくても introduced"""
        _, got = self.second_pass(2, [face("key-n1", units=["u3"])], plan=[row("u1"), row("u3")])
        self.assertEqual(got["origins"], {"key-n1": C.ORIGIN_INTRODUCED})

    def test_missed_claim_on_changed_item_falls_back(self):
        """1 回目に渡した出自の申告は新しい block が無いので採られない（origins は {}）。2 回目、行の変わった項目 2 に当たる新しい
        block への missed の申告は項目の事実と合わないので採らず、既定（unsplit）に落ちて、申告は origins_claimed に残る"""
        first = {"key": "key-a1", "origin": C.ORIGIN_MISSED}
        got = C.record_pass(self.b, {"faces": [face("key-a1", units=["u1"])]}, resolved=[], files={}, origins=[first])
        self.assertEqual((got["origins"], got["origins_claimed"]), ({}, [first]))
        C.note_plan(self.b, [row("u1"), row("u2", approach="直した")])
        claim = {"key": "key-b1", "origin": C.ORIGIN_MISSED}
        got = C.record_pass(self.b, {"faces": [face("key-b1", units=["u2"])]}, resolved=["key-a1"], files={},
                                   origins=[claim])
        self.assertEqual((got["origins"], got["origins_claimed"]), ({"key-b1": C.ORIGIN_UNSPLIT}, [claim]))

    def test_rephrased_claim_without_unit_overlap_falls_back(self):
        """of が前の往復の block で今の往復の resolved に在っても、of の face の単位（u1）と今の block の単位（u2）が重ならない
        言い換えの申告は採らない。既定（行の変わっていない項目なので missed）に落ちて、申告は origins_claimed に残る。重なれば採る"""
        claim = {"key": "key-a2", "origin": C.ORIGIN_REPHRASED, "of": "key-a1"}
        _, got = self.second_pass(2, [face("key-a2", units=["u2"])], origins=[claim])
        self.assertEqual((got["origins"], got["origins_claimed"]), ({"key-a2": C.ORIGIN_MISSED}, [claim]))
        _, got = self.second_pass(3, [face("key-a2", units=["u1", "u2"])], origins=[claim])
        self.assertEqual((got["origins"], got["origins_claimed"]), ({"key-a2": C.ORIGIN_REPHRASED}, []))

    def test_conflicting_claims_for_one_key_fall_back(self):
        """同じ key に introduced と missed の 2 件の申告が在れば、どちらも採らない。既定（行の変わった項目なので unsplit）に落ち、
        2 件とも origins_claimed に残る"""
        claims = [{"key": "key-b1", "origin": C.ORIGIN_INTRODUCED}, {"key": "key-b1", "origin": C.ORIGIN_MISSED}]
        _, got = self.second_pass(2, [face("key-b1", units=["u2"])], origins=claims, plan=[row("u1"), row("u2", approach="直した")])
        self.assertEqual((got["origins"], got["origins_claimed"]), ({"key-b1": C.ORIGIN_UNSPLIT}, claims))

    BEFORE = {"unit_keys": ["u1"], "approach": "最初の文はそのまま残す。二つ目の文をこの往復で書き換える。",
              "files": [{"path": "lib/a.py", "op": "modify"}, {"path": "lib/b.py", "op": "modify"}], "refactor": {"declared": False}}

    KEPT, GONE, ADDED = "最初の文はそのまま残す。", "二つ目の文をこの往復で書き換える。", "二つ目の文を直しで別の形に替えた。"

    def quoted_pass(self, rnd, faces, origins, after):
        """項目 1 を BEFORE の行で審査した 1 往復目の後、項目 1 を after(BEFORE) に置き直して 2 往復目を記録した行"""
        b = self.board(rnd)
        C.note_plan(b, [self.BEFORE, row("u2")])
        C.record_pass(b, {"faces": [face("key-a1", units=["u1"])]}, resolved=[], files={})
        C.note_plan(b, [after(self.BEFORE), row("u2")])
        return C.record_pass(b, {"faces": faces}, resolved=["key-a1"], files={}, origins=list(origins))

    def rewritten(self, it):
        """approach の 2 つ目の文を書き換え、files の頭に行を 1 つ足した項目"""
        return {**it, "approach": self.KEPT + self.ADDED, "files": [{"path": "lib/new.py", "op": "create"}, *it["files"]]}

    def test_quote_of_kept_sentence_is_missed_on_changed_item(self):
        """行の変わった項目でも、申告の引用が変わっていない文だけに当たれば missed（files の頭に行を足しても後ろの行の文は変わって
        いない文のまま）。並びだけを変えた項目は文の組が前と同じなので照らさずに unsplit。引用の無い申告と短い引用も unsplit"""
        for rnd, quote in ((2, self.KEPT), (3, "lib/b.py")):
            claim = {"key": "key-b1", "origin": C.ORIGIN_MISSED, C.QUOTE: quote}
            with self.subTest(quote=quote):
                got = self.quoted_pass(rnd, [face("key-b1", units=["u1"])], [claim], self.rewritten)
                self.assertEqual((got["origins"], got["origins_claimed"]), ({"key-b1": C.ORIGIN_MISSED}, []))
        claim = {"key": "key-b1", "origin": C.ORIGIN_MISSED, C.QUOTE: self.KEPT}
        got = self.quoted_pass(4, [face("key-b1", units=["u1"])], [claim], lambda it: {**it, "files": it["files"][::-1]})
        self.assertEqual((got["origins"], got["origins_claimed"]), ({"key-b1": C.ORIGIN_UNSPLIT}, [claim]))
        for rnd, quote in ((5, ""), (6, "最初")):
            claim = {"key": "key-b1", "origin": C.ORIGIN_MISSED, C.QUOTE: quote}
            with self.subTest(quote=quote):
                got = self.quoted_pass(rnd, [face("key-b1", units=["u1"])], [claim], self.rewritten)
                self.assertEqual(got["origins"], {"key-b1": C.ORIGIN_UNSPLIT})

    def test_quote_of_added_sentence_is_introduced(self):
        """引用が足した文だけに当たる新しい block は introduced（missed の申告は採らずに残る）。消した文に当たる引用と、変わっていない
        文と足した文の両方に当たる引用は unsplit。値だけを変えた欄（refactor.declared の反転）も足した文に数える"""
        cases = ((2, self.ADDED, self.rewritten, C.ORIGIN_INTRODUCED), (3, "lib/new.py", self.rewritten, C.ORIGIN_INTRODUCED),
                 (4, self.GONE, self.rewritten, C.ORIGIN_UNSPLIT), (5, "二つ目の文", self.rewritten, C.ORIGIN_UNSPLIT),
                 (6, "true", lambda it: {**it, "refactor": {"declared": True}}, C.ORIGIN_INTRODUCED))
        for rnd, quote, after, want in cases:
            claim = {"key": "key-b1", "origin": C.ORIGIN_MISSED, C.QUOTE: quote}
            with self.subTest(quote=quote):
                got = self.quoted_pass(rnd, [face("key-b1", units=["u1"])], [claim], after)
                self.assertEqual((got["origins"], got["origins_claimed"]), ({"key-b1": want}, [claim]))

    def test_claims_differing_only_in_quote_take_neither(self):
        """同じ key に引用だけが違う 2 件の申告が在れば食い違いに数え、どちらも採らずに引用の無い既定（unsplit）へ落ち、2 件とも
        origins_claimed に残る"""
        claims = [{"key": "key-b1", "origin": C.ORIGIN_MISSED, C.QUOTE: self.KEPT},
                  {"key": "key-b1", "origin": C.ORIGIN_MISSED, C.QUOTE: self.ADDED}]
        got = self.quoted_pass(2, [face("key-b1", units=["u1"])], claims, self.rewritten)
        self.assertEqual((got["origins"], got["origins_claimed"]), ({"key-b1": C.ORIGIN_UNSPLIT}, claims))

    def test_introduced_claim_quoting_kept_sentence_stays_introduced(self):
        """introduced の申告は今の往復でどれかの項目の行が変わっていれば採り、引用の当たりを見ない（引用つきも引用の無い申告も）"""
        claims = [{"key": "key-b1", "origin": C.ORIGIN_INTRODUCED, C.QUOTE: self.KEPT},
                  {"key": "key-b2", "origin": C.ORIGIN_INTRODUCED}]
        got = self.quoted_pass(2, [face("key-b1", units=["u1"]), face("key-b2", units=["u1"])], claims, self.rewritten)
        self.assertEqual((got["origins"], got["origins_claimed"]),
                         ({"key-b1": C.ORIGIN_INTRODUCED, "key-b2": C.ORIGIN_INTRODUCED}, []))

    def test_block_on_new_and_old_items_rejects_missed_claim(self):
        """新しい id の項目（u3）と、行の変わっていない既存の項目（u1）の両方に当たる新しい block は、申告が無くても unsplit で、
        引用の無い missed の申告も採らずに unsplit に落ちる（新しい id の項目の文は全部が足した文で、引用が無ければどちらとも決まらない）"""
        faces = [face("key-b1", units=["u1", "u3"])]
        _, got = self.second_pass(2, faces, plan=[row("u1"), row("u3")])
        self.assertEqual((got["origins"], got["origins_claimed"]), ({"key-b1": C.ORIGIN_UNSPLIT}, []))
        claim = {"key": "key-b1", "origin": C.ORIGIN_MISSED}
        _, got = self.second_pass(3, faces, origins=[claim], plan=[row("u1"), row("u3")])
        self.assertEqual((got["origins"], got["origins_claimed"]), ({"key-b1": C.ORIGIN_UNSPLIT}, [claim]))

    def test_claims_without_item_record_fall_back(self):
        """項目の控えの無い往復（note_plan なし）では、2 往復目の新しい block への missed・rephrased の申告を採らない。unsplit に
        落ち、申告は origins_claimed に残る"""
        b = self.board(2)
        C.record_pass(b, {"faces": [face("key-a1")]}, resolved=[], files={})
        claims = [{"key": "key-b1", "origin": C.ORIGIN_MISSED},
                  {"key": "key-a2", "origin": C.ORIGIN_REPHRASED, "of": "key-a1"}]
        got = C.record_pass(b, {"faces": [face("key-b1"), face("key-a2")]}, resolved=["key-a1"], files={},
                                   origins=claims)
        self.assertEqual(got["origins"], {"key-b1": C.ORIGIN_UNSPLIT, "key-a2": C.ORIGIN_UNSPLIT})
        self.assertEqual(got["origins_claimed"], claims)


class StuckKeysCase(BoardCase):
    """止めた block の key（src.rounds の stuck_keys・uncited）の項目の無い控えの分（元 lib/tests/test_converge.py の分に無かった分岐）"""

    def test_stuck_keys_without_items_follow_the_outcome(self):
        """stuck_keys の項目の無い控えの分: PERSISTED は最後の往復の続いた key、UNSETTLED は最後の往復の block（docstring の式）。
        uncited は『項目 n』を求めない"""
        self.record(["key-a"])
        self.record(["key-a"], resolved=[])
        doc = C.read(self.b)
        self.assertEqual((doc["outcome"], C.stuck_keys(doc)), (C.PERSISTED, ["key-a"]))
        self.assertEqual(C.uncited("key-a を直す", doc), [])
        self.b = b = self.board(2)
        self.record(["c1", "c2", "c3"])
        self.record(["c4", "c5"])
        self.record(["c6"], at_cap=True)
        doc = C.read(b)
        self.assertEqual((doc["outcome"], C.stuck_keys(doc)), (C.UNSETTLED, ["c6"]))
        self.assertEqual(C.uncited("推しの一言", doc), ["c6"])


class AddPassCase(BoardCase):
    def setUp(self):
        super().setUp()
        C.note_plan(self.b, [row("u1"), row("u2")])

    def test_add_pass_is_the_row_record_pass_writes(self):
        doc = C.read(self.b)
        review = {"faces": [face("key-a1", units=["u1"]), face("key-s1", units=["u2"], severity="suggest")]}
        want = C.add_pass(doc, review, answers=[], resolved=[])
        got = C.record_pass(self.b, review, resolved=[], files={})
        self.assertEqual(got, want)
        self.assertEqual(C.read(self.b)["outcome"], doc["outcome"])

    def test_add_pass_takes_origins_and_cap(self):
        """出自の申告と上限の周も add_pass と record_pass が同じ行を組む（盤面を持たない呼び手が控えを組み直しても同じ）"""
        first = {"faces": [face("key-a1", units=["u1"]), face("key-a2", units=["u2"])]}
        C.add_pass(doc := C.read(self.b), first, answers=[], resolved=[])
        C.record_pass(self.b, first, resolved=[], files={})
        review = {"faces": [face("key-b1", units=["u2"])]}
        said = [{"key": "key-b1", "origin": C.ORIGIN_MISSED}]
        want = C.add_pass(doc, review, answers=[], resolved=["key-a1", "key-a2"], origins=said, at_cap=True)
        got = C.record_pass(self.b, review, resolved=["key-a1", "key-a2"], files={}, origins=said, at_cap=True)
        self.assertEqual(got, want)
        self.assertEqual((got["origins"], got["capped"], got["outcome"]),
                         ({"key-b1": C.ORIGIN_MISSED}, True, C.UNSETTLED))
        self.assertEqual(C.read(self.b)["outcome"], doc["outcome"])

class PlaceRecordCase(BoardCase):
    """line の形の記録の読み書き（元 RecordCase の盤面の照らしの写し。pass.json の材料と place のパス）"""

    def test_read_without_record_is_first_pass(self):
        """無い記録だけが 1 往復目。読めない・形の違う記録は往復の無い記録にすり替えず、理由を名指して落ちる（#851）"""
        path = self.b.dir / rounds_files.PLAN_CONVERGE
        self.assertEqual(rounds.read(path), rounds.fresh())
        self.assertEqual(rounds.read(None), rounds.fresh())
        for text, word in (("{壊れた", "JSON として読めない"), (json.dumps({"passes": [7]}), "passes"),
                           (json.dumps({"round": 1}), "passes")):
            path.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, word):
                rounds.read(path)

    def test_record_pass_keeps_every_pass_and_copies_files(self):
        row1 = self.record(["a"], files={"plan.json": self.src("plan.json", "案 1"), "review.json": self.src("review.json", "審査 1")},
                           extra=[face("s", severity="suggest")])
        self.assertEqual((row1["pass"], row1["blocks"], row1["suggests"], row1["outcome"]), (1, ["a"], ["s"], C.AGAIN))
        self.assertEqual(row1["faces"], [{"key": "a", "kind": "regression", "where": "a の場所", "why": "a が穴である理由"}])
        row2 = self.record(["a"], files={"plan.json": self.src("plan.json", "案 2")})
        self.assertEqual((row2["pass"], row2["persists"], row2["outcome"]), (2, ["a"], C.PERSISTED))
        doc = C.read(self.b)
        self.assertEqual(([p["pass"] for p in doc["passes"]], doc["outcome"]), ([1, 2], C.PERSISTED))
        one, two = (self.b.dir / rounds_files.PLAN_CONVERGE_FILES.format(k=k) for k in (1, 2))
        self.assertEqual((one / "plan.json").read_text(encoding="utf-8"), "案 1")
        self.assertEqual((one / "review.json").read_text(encoding="utf-8"), "審査 1")
        self.assertEqual((two / "plan.json").read_text(encoding="utf-8"), "案 2")
        self.assertEqual(doc["passes"][1]["files"], {"plan.json": str(two / "plan.json")})
        self.assertEqual(list(self.b.dir.glob("*.tmp")), [])

    def test_record_pass_reads_faces_through_one_guard(self):
        for bad in (7, "faces", {"key": "a"}, None):
            with self.subTest(bad=bad):
                b = self.board(len(list(self.tmp.iterdir())) + 1)
                row = C.record_pass(b, {"faces": bad}, resolved=[], files={})
                self.assertEqual((row["blocks"], row["suggests"], row["outcome"]), ([], [], C.CLEAN))

    def test_rejects_and_precedents_ride_on_the_pass(self):
        """計画の拒否（role plan）と事前審査の拒否（pass.json の rejects）を行に積み、先行例の確かめを記録の頭に重ねる（控えに在る出典は
        書き換えない）。hits・refs の鍵は字の番号でも項目の番号で引く"""
        C.note_plan(self.b, [row("u1")])
        doc = rounds.fresh()
        got = {"review": {"faces": [face("key-a1", units=["u1"])]}, "answers": [], "resolved": [], "plan": self.b.plan,
               "hits": {"1": [{"hit": "h"}]}, "refs": {"1": ["e1"]}, "rejects": [{"role": "p2.plan_review", "at": 1, "reason": "r"}],
               "precedent_checks": {"https://x": {"ok": True}}}
        doc["precedent_checks"] = {"https://x": {"ok": False}}
        line = rounds.record_pass(doc, got, at_cap=False, dest=self.b.dir / "p", plan_rejects=[{"at": 1, "reason": "plan"}])
        self.assertEqual(line["rejects"], [{"role": rounds.PLAN_ROLE, "at": 1, "reason": "plan"},
                                           {"role": "p2.plan_review", "at": 1, "reason": "r"}])
        self.assertEqual(doc["precedent_checks"], {"https://x": {"ok": False}})
        self.assertEqual((line["items"][0]["hits"], line["items"][0]["refs"]), ([{"hit": "h"}], ["e1"]))


class PushableCase(unittest.TestCase):
    """止まった案を推しで越えてよいか（元 lib/gatepolicy.py の stuck_pushable。無人の印を引数で受ける形）"""

    def doc(self, *, outcome=C.PERSISTED, capped=False, blocks=("key-a1",)):
        return {"outcome": outcome, "passes": [{"pass": 1, "blocks": ["key-a1"], "faces": [face("key-a1")], "persists": []},
                                               {"pass": 2, "blocks": list(blocks), "faces": [face(k) for k in blocks],
                                                "persists": list(blocks), **({"capped": True} if capped else {})}]}

    def test_every_condition_is_needed(self):
        push = {"go": True, "note": "key-a1 は端なので進める"}
        self.assertTrue(rounds.stuck_pushable(self.doc(), push, unattended=True, design_talk=False))
        for kw, why in (({"unattended": False, "design_talk": False}, "人の居る run"), ({"unattended": True, "design_talk": True}, "設計だけ")):
            with self.subTest(why=why):
                self.assertFalse(rounds.stuck_pushable(self.doc(), push, **kw))
        self.assertFalse(rounds.stuck_pushable(self.doc(capped=True), push, unattended=True, design_talk=False), "上限の止まりは人が見る")
        self.assertFalse(rounds.stuck_pushable(self.doc(outcome=C.AGAIN), push, unattended=True, design_talk=False))
        self.assertFalse(rounds.stuck_pushable(self.doc(), {"go": False, "note": "key-a1"}, unattended=True, design_talk=False))
        self.assertFalse(rounds.stuck_pushable(self.doc(), {"go": True, "note": "引いていない"}, unattended=True, design_talk=False))
        self.assertFalse(rounds.stuck_pushable(self.doc(), None, unattended=True, design_talk=False))


if __name__ == "__main__":
    unittest.main()
