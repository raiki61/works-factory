"""範囲の相談の部品（lib/consult.py。設計 docs/plans/2026-10-06-ask-planner.md）の検査。

縛る事:
- 先の確かめ（screen）: 知らない項目・頼む物が無い・理由が短い・根の外のパス・全部がもう範囲の中の頼みは、答えの役に聞かずに
  断る（記録は残す）。修正案の out_of_scope に当たるパスは断らずに答えの役へ回し（持ち主 2026-10-07「相談で考え直させる」）、
  指示書はその項目の out_of_scope（と外した理由）・ほかの項目の out_of_scope の当たりを名指して考え直させる。許せば trace の行に
  out_of_scope を外した印（overrode_out_of_scope）が残る
- 答えの確かめ（judge）: 許すのは頼んだ物の中だけ（足した物は捨てて注記）。形の崩れた答えは invalid で、許しを作らない
- 確かめの節（settle）: 1 頼み 1 行を置き場の trace.jsonl（conflict.ASKED_OP）に書く（断った・聞けなかった行も）。allow の行は合意
  （conflict.agreed）として範囲とテストの許しに入る。答えのファイルを書き、支度（take）が 1 度だけ引く
- 人の関所の条件（gate_notes・gate_asks）: 今の周の直す前の関所の一言だけを、項目ごとの頼みにする。出し済みなら 2 度聞かない
置き場は使い捨てのフォルダ（git・子のプロセスなし）。頼みの節の状態は、元の頼みの節（ask。外した）が書いた形を試験の助けが書く。
"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import conflict  # noqa: E402
import consult  # noqa: E402
import gatemarks  # noqa: E402
import jsonfile  # noqa: E402
import planrange  # noqa: E402

OOS_WHY = "README の節は別の依頼で書き直す"
ITEMS = {"3": {"unit_keys": ["lens.py count_line: 落ちたレンズの数"], "allowed_paths": ["works/.shared/core/lens.py"],
               "out_of_scope": [{"glob": "works/README.md", "why": OOS_WHY}], "tests": ["works/tests/test_lens.py"]},
         "4": {"unit_keys": ["report.py head: 頭の行"], "allowed_paths": ["works/.shared/core/report.py"],
               "out_of_scope": [{"glob": "works/docs/**", "why": "文書は項目 4 では触らない"}], "tests": []}}
WHY = "直しに伴って変更の記録を足す要がある"
NODE = "consult-answer"


def reply(*asks):
    return {"changes": [], conflict.CONSULT_FIELD: list(asks)}


def ask_row(item=3, paths=("works/CHANGELOG.md",), tests=(), why=WHY):
    return {"item": item, "paths": list(paths), "tests": list(tests), "why": why}


def put_asked(place, asks, pass_="first", node=NODE, items=ITEMS, unavailable=""):
    """頼みの節の状態を置く（元の consult.ask が書いた形: 頼みごとに screen と oos_hits を当て、turns を 1 つ進め、turn_state を asked
    に）。asks は requests の形の行（と queued の行）。unavailable を渡すと聞く頼みを聞けなかった行にする。返り (状態, 指示書の本文)"""
    st = consult.state(place, pass_)
    turn = int(st.get("turns") or 0) + 1
    rows = []
    for n, a in enumerate(asks, 1):
        new_tests = a.get("new_tests") or []
        why = consult.screen(items, a["item"], a["paths"], a["tests"], a["why"], new_tests, gate=a.get("origin") == consult.ORIGIN_GATE)
        hits = consult.oos_hits(items, a["item"], a["paths"] + [consult._test_file(x) for x in new_tests], a["tests"]) \
            if a["item"] in items else []
        rows.append({**a, "n": n, "out_of_scope": hits, **({"status": consult.REFUSED, "why_refused": why} if why else {"status": consult.ASKED})})
    asked = [r for r in rows if r["status"] == consult.ASKED]
    if unavailable:
        for r in asked:
            r.update(status=consult.UNAVAILABLE, why_unavailable=unavailable)
        asked = []
    doc = {"turns": turn, "turn_state": consult.ASKED, "rows": rows, "question_file": "", "session": None, "node": node, "items": items}
    jsonfile.write(consult.state_path(place, pass_), doc)
    return doc, consult.question(items, asked) if asked else ""


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.b = pathlib.Path(self._tmp.name).resolve() / "place"
        self.b.mkdir()

    def ask(self, r, pass_="first"):
        return put_asked(self.b, consult.requests(r) or [], pass_)


GATE = gatemarks.GATE_NODE


class ScreenCase(unittest.TestCase):
    def test_refusals(self):
        self.assertIn("項目", consult.screen(ITEMS, "9", ["a.py"], [], WHY))
        self.assertIn("根の外", consult.screen(ITEMS, "3", ["../x.py"], [], WHY))
        self.assertIn("根の外", consult.screen(ITEMS, "3", ["/etc/x"], [], WHY))
        self.assertIn("範囲の中", consult.screen(ITEMS, "3", ["works/.shared/core/lens.py"], [], WHY))
        self.assertIn("何も", consult.screen(ITEMS, "3", [], [], WHY))
        self.assertIn("理由", consult.screen(ITEMS, "3", ["works/CHANGELOG.md"], [], "短い"))

    def test_passes(self):
        self.assertIsNone(consult.screen(ITEMS, "3", ["works/CHANGELOG.md"], [], WHY))
        self.assertIsNone(consult.screen(ITEMS, "3", [], ["works/tests/test_report.py:12"], WHY))
        self.assertIsNone(consult.screen(ITEMS, "3", ["works/.shared/core/lens.py", "works/CHANGELOG.md"], [], WHY),
                          "範囲の外を 1 本でも含む頼みは聞く")

    def test_out_of_scope_is_forwarded(self):
        """修正案が out_of_scope に書いたパスも断らない（持ち主 2026-10-07「相談で考え直させる」。run 54d81ef1 は CHANGELOG.md が
        項目 1 の out_of_scope に当たって断られ、scope_needed → fix_plan_item → 修正案の直しの関所で無人の run が止まった）。
        ほかの項目の out_of_scope に当たるパスも聞く（e7906845: ほかの項目の out_of_scope は、この項目が許すパスを禁じない）"""
        self.assertIsNone(consult.screen(ITEMS, "3", ["works/README.md"], [], WHY))
        self.assertIsNone(consult.screen(ITEMS, "3", ["works/docs/flow.md"], [], WHY))
        self.assertIsNone(consult.screen(ITEMS, "3", [], ["works/README.md:3"], WHY))

    def test_new_tests_only_request_is_not_refused(self):
        """パスも書き換えの範囲も無く new_tests（足したい新しいテスト）だけを持つ頼みと、パスが全部範囲の中で new_tests を持つ頼みは
        断らない（受け付けが見つけた案の外のテストの足しは、この形で聞く）"""
        tid = "works/tests/test_lens.py::LensCase::test_extra"
        self.assertIsNone(consult.screen(ITEMS, "3", [], [], WHY, new_tests=[tid]))
        self.assertIsNone(consult.screen(ITEMS, "3", ["works/.shared/core/lens.py"], [], WHY, new_tests=[tid]),
                          "パスがもう範囲の中でも、new_tests が在れば聞く")
        self.assertIn("何も", consult.screen(ITEMS, "3", [], [], WHY, new_tests=[]), "new_tests も空なら今どおり断る")

    def test_allowed_but_out_of_scope_is_not_already_inside(self):
        """allowed_paths の glob に入っても、その項目の out_of_scope に当たるパスは範囲の中でない（受け付けが拒む）ので、
        「もう範囲の中」と断らずに聞く"""
        items = {"3": {**ITEMS["3"], "allowed_paths": ["works/*.md"]}}
        self.assertIsNone(consult.screen(items, "3", ["works/README.md"], [], WHY))
        self.assertIn("範囲の中", consult.screen(items, "3", ["works/CHANGELOG.md"], [], WHY))


class QuestionCase(unittest.TestCase):
    def test_own_out_of_scope_is_named_with_its_reason(self):
        """指示書は、頼んだパスがあなた自身がこの項目の out_of_scope に書いた物だと言い、外した理由を字のまま引いて考え直させる"""
        q = consult.question(ITEMS, [{"n": 1, "item": "3", "paths": ["works/README.md"], "tests": [], "why": WHY}])
        sec = q[q.index("## 相談 1"):]
        for w in ("works/README.md", "out_of_scope", OOS_WHY, "あなたがこの項目の out_of_scope", "考え直"):
            self.assertIn(w, sec)

    def test_other_item_out_of_scope_is_named(self):
        q = consult.question(ITEMS, [{"n": 1, "item": "3", "paths": ["works/docs/flow.md"], "tests": [], "why": WHY}])
        sec = q[q.index("## 相談 1"):]
        for w in ("works/docs/flow.md", "項目 4 の out_of_scope", "works/docs/**", "文書は項目 4 では触らない"):
            self.assertIn(w, sec)
        self.assertNotIn("あなたがこの項目の out_of_scope", sec)

    def test_plain_ask_says_nothing_about_out_of_scope_hits(self):
        q = consult.question(ITEMS, [{"n": 1, "item": "3", "paths": ["works/CHANGELOG.md"], "tests": [], "why": WHY}])
        self.assertNotIn("当たる", q[q.index("## 相談 1"):])


class JudgeCase(unittest.TestCase):
    def test_grant_is_cut_to_what_was_asked(self):
        got, notes = consult.judge({"decision": "allow", "paths": ["a.md", "b.md"], "tests": ["t.py:3"], "spec": "",
                                    "reason": "変更の記録は直しに伴う"}, ["a.md"], ["t.py:3"])
        self.assertEqual((got["decision"], got["granted_paths"], got["granted_tests"]), ("allow", ["a.md"], ["t.py:3"]))
        self.assertTrue(any("b.md" in n for n in notes), notes)

    def test_allow_grants_requested_new_tests_with_red_kind(self):
        """allow の答えの new_tests のうち、頼んだ id だけが granted_new_tests に {id, red_kind} で残る。許したパスもテストの範囲も
        無くても行は正しい allow。頼んでいない id は捨てて注記する"""
        want = "works/tests/test_lens.py::LensCase::test_extra"
        got, notes = consult.judge({"decision": "allow", "paths": [], "tests": [], "spec": "", "reason": "守りのテストとして足してよい",
                                    "new_tests": [{"id": want, "red_kind": "red"},
                                                  {"id": "works/tests/test_lens.py::LensCase::test_other", "red_kind": "red"}]},
                                   [], [], new_tests=[want])
        self.assertIsNotNone(got, notes)
        self.assertEqual((got["decision"], got["granted_paths"], got["granted_tests"]), ("allow", [], []))
        self.assertEqual(got["granted_new_tests"], [{"id": want, "red_kind": "red"}])
        self.assertTrue(any("test_other" in n for n in notes), notes)

    def test_malformed_answers_are_invalid(self):
        for bad in ({"decision": "maybe", "reason": "x" * 12}, {"decision": "allow", "paths": [], "tests": [], "reason": "x" * 12},
                    {"decision": "deny"}, "not a dict", None):
            got, notes = consult.judge(bad, ["a.md"], [])
            self.assertIsNone(got, bad)
            self.assertTrue(notes, bad)

    def test_deny_and_defer_grant_nothing(self):
        for d in ("deny", "defer"):
            got, _ = consult.judge({"decision": d, "paths": ["a.md"], "tests": [], "spec": "", "reason": "今の run の仕様の外"},
                                   ["a.md"], [])
            self.assertEqual((got["granted_paths"], got["granted_tests"]), ([], []), d)


class RequestsCase(unittest.TestCase):
    def test_shapes(self):
        self.assertIsNone(consult.requests({"changes": []}))
        self.assertIsNone(consult.requests({conflict.CONSULT_FIELD: []}))
        self.assertIsNone(consult.requests(None))
        got = consult.requests(reply(ask_row(paths=["a.md", " "], tests=["t.py:3"])))
        self.assertEqual(got, [{"item": "3", "paths": ["a.md"], "tests": ["t.py:3"], "why": WHY}])
        self.assertEqual(consult.requests({conflict.CONSULT_FIELD: ["x"]}), [{"item": "", "paths": [], "tests": [], "why": ""}],
                         "形の崩れた頼みは欄を空にして残す（screen が断る）")


class FlowCase(Base):
    def test_no_consult_is_a_no_op(self):
        self.assertEqual(consult.settle(self.b, None, "first", NODE)["consulted"], False)
        self.assertIsNone(consult.take(self.b, "first"))
        self.assertEqual(conflict.plan_asks(self.b), [])

    def test_allow_round_trip(self):
        _, q = self.ask(reply(ask_row(tests=["works/tests/test_report.py:12"]), ask_row(paths=["../outside.md"])))
        self.assertIn("相談 1", q)
        self.assertNotIn("相談 2", q, "断った頼みは答えの役に聞かない")
        self.assertIn("works/CHANGELOG.md", q)
        answer = {"answers": [{"ask": 1, "decision": "allow", "paths": ["works/CHANGELOG.md", "works/other.md"],
                               "tests": ["works/tests/test_report.py:12"], "spec": "1 行だけ足す",
                               "reason": "直しに伴う変更の記録と期待の書き換え"}]}
        got = consult.settle(self.b, answer, "first", NODE)
        self.assertEqual((got["consulted"], got["turn"]), (True, 1))
        self.assertEqual(got["counts"], {"allow": 1, "refused": 1})
        rows = conflict.plan_asks(self.b)
        self.assertEqual([(r["id"], r["status"]) for r in rows], [(1, "answered"), (2, "refused")])
        self.assertIn("根の外", rows[1]["why_refused"])
        self.assertEqual((rows[0]["pass"], rows[0]["round"], rows[0]["turn"], rows[0]["node"]), ("first", 1, 1, NODE))
        (agreed,) = conflict.agreed(self.b)
        self.assertEqual((agreed["item"], agreed["granted_paths"]), ("3", ["works/CHANGELOG.md"]), "頼んでいない物は捨てる")
        (permit,) = conflict.agreed_permits([agreed])
        self.assertEqual((permit["limit"], permit["id"]), ("works/tests/test_report.py:12", f"{conflict.AGREED_TEST_ID}-3"))
        text = pathlib.Path(got["answer_file"]).read_text(encoding="utf-8")
        for w in ("allow", "works/CHANGELOG.md", "1 行だけ足す", "refused", "根の外", "works/other.md"):
            self.assertIn(w, text)
        self.assertEqual(pathlib.Path(got["answer_file"]).parent, self.b, "答えのファイルは置き場に書く")
        took = consult.take(self.b, "first")
        self.assertEqual((took["turn"], took["answer_file"], took["left"]), (1, got["answer_file"], consult.BUDGET - 1))
        self.assertIsNone(consult.take(self.b, "first"), "答えは 1 度だけ渡す")
        # 次の相談は id を続け、周を数える
        st, _ = self.ask(reply(ask_row()))
        self.assertEqual(st["turns"], 2)
        consult.settle(self.b, {"answers": [{"ask": 1, "decision": "deny", "paths": [], "tests": [], "spec": "",
                                             "reason": "範囲の中で直せる"}]}, "first", NODE)
        self.assertEqual([r["id"] for r in conflict.plan_asks(self.b)], [1, 2, 3])
        self.assertEqual(len(conflict.agreed(self.b)), 1, "deny は合意にならない")

    def test_queued_overflow_is_asked_without_reply_consult(self):
        """受け付けが見つけたはみ出し（consult.queue で積んだ頼み）は、確かめの行に origin accept が残り、new_tests の許しが合意に
        入る。積む周で turns が 1 増え、残りが 2 未満なら積まない"""
        tid = "works/tests/test_lens.py::LensCase::test_extra"
        row = {**ask_row(), "new_tests": [tid]}
        consult.queue(self.b, "first", [row])
        self.assertTrue(consult.queued(self.b, "first"))
        self.assertEqual(consult.state(self.b, "first")["turns"], 1, "積む周の分")
        queued = [{**r, "item": str(r["item"])} for r in consult.queued(self.b, "first")]
        st, q = put_asked(self.b, queued)
        self.assertEqual(st["turns"], 2)
        for w in ("works/CHANGELOG.md", tid):
            self.assertIn(w, q)
        answer = {"answers": [{"ask": 1, "decision": "allow", "paths": ["works/CHANGELOG.md"], "tests": [], "spec": "",
                               "new_tests": [{"id": tid, "red_kind": "red"}], "reason": "案の外のテストも足してよい"}]}
        got = consult.settle(self.b, answer, "first", NODE)
        (asked,) = conflict.plan_asks(self.b)
        self.assertEqual((asked["origin"], asked["status"], asked["decision"]), ("accept", "answered", "allow"))
        self.assertEqual(asked["granted_new_tests"], [{"id": tid, "red_kind": "red"}])
        (agreed,) = conflict.agreed(self.b)
        self.assertEqual(agreed["granted_new_tests"], [{"id": tid, "red_kind": "red"}])
        self.assertIn("受け付けが見つけたはみ出し", pathlib.Path(got["answer_file"]).read_text(encoding="utf-8"))
        # 残りが 2 未満なら積まない（積む周と相談の周の 2 周が要る）
        consult.state_path(self.b, "first").write_text(json.dumps({"turns": consult.BUDGET - 1}), encoding="utf-8")
        consult.queue(self.b, "first", [row])
        self.assertFalse(consult.queued(self.b, "first"))
        self.assertEqual(consult.state(self.b, "first")["turns"], consult.BUDGET - 1)

    def test_human_gate_condition_is_asked(self):
        """人の関所の continue の条件（今の周の直す前の関所の一言）は、項目ごとの頼みになり（条件の字のままが指示書に載る）、
        役は条件で要る新しいテストを頼まれていなくても許せ、合意（conflict.agreed）に入り、範囲の照らしが読む項目の tests に重なる。
        同じ周の同じ条件は 2 度聞かない"""
        note = "既存の集計を壊さないことを確かめるテストを足してから直せ"
        human = [{"round": 1, "node": GATE, "kinds": ["final"], "answer": "continue", "note": note},
                 {"round": 0, "node": GATE, "kinds": ["final"], "answer": "continue", "note": "前の周の一言"},
                 {"round": 1, "node": "p4.final_gate", "kinds": ["final"], "answer": "continue", "note": "ほかの関所の一言"}]
        self.assertEqual(consult.gate_notes(self.b, human), note)
        self.assertEqual(consult.gate_notes(self.b, human, round_=0), "前の周の一言")
        pushed = [{**human[0], consult.answer.PUSHED: [{"item": "x", "answer": "continue", "note": note, "why": "y"}]}]
        self.assertEqual(consult.gate_notes(self.b, pushed), consult.answer.PUSHED_NOTE + note)   # 推しの条件は人の答えと名乗らない
        asks = consult.gate_asks(self.b, ITEMS, human)
        self.assertEqual([(a["item"], a["origin"]) for a in asks], [("3", "gate"), ("4", "gate")])
        _, q = put_asked(self.b, asks[:1])
        self.assertIn(note, q)
        self.assertNotIn("前の周の一言", q)
        self.assertNotIn("ほかの関所の一言", q, "直す前の関所の一言だけを条件にする")
        tid = "works/tests/test_lens.py::LensCase::test_total_is_kept"
        answer = {"answers": [{"ask": 1, "decision": "allow", "paths": [], "tests": [], "spec": "",
                               "new_tests": [{"id": tid, "red_kind": "red"}], "reason": "人の条件のテストを項目に足してよい"}]}
        consult.settle(self.b, answer, "first", NODE)
        (agreed,) = conflict.agreed(self.b)
        self.assertEqual(agreed["granted_new_tests"], [{"id": tid, "red_kind": "red"}])
        (merged,) = planrange.with_agreed([{"item": agreed["item"], "allowed_paths": [], "tests": []}], [agreed])
        self.assertEqual([row["id"] for row in merged["tests"]], [tid], "合意した新しいテストは項目の tests と同じに読まれる")
        self.assertEqual(consult.gate_asks(self.b, ITEMS, human), [], "同じ周の同じ条件は 2 度聞かない")

    def test_out_of_scope_reconsidered(self):
        """out_of_scope に当たる頼みは答えの役に聞く。allow の行は、その項目の out_of_scope を外した印（overrode_out_of_scope。
        パス・glob・外した理由）を持ち、合意（conflict.agreed）になる。deny の行は何も外さない。ほかの項目の out_of_scope の当たりは
        行の out_of_scope に項目つきで残り、外した印にはならない（その項目の out_of_scope はその項目の物）"""
        _, q = self.ask(reply(ask_row(paths=["works/README.md", "works/docs/flow.md"]), ask_row(paths=["works/README.md"])))
        self.assertIn("相談 2", q, "out_of_scope に当たる頼みも聞く")
        self.assertIn(OOS_WHY, q)
        answer = {"answers": [{"ask": 1, "decision": "allow", "paths": ["works/README.md", "works/docs/flow.md"], "tests": [],
                               "spec": "", "reason": "外した時は README の節を書き直す依頼が別に在ると見たが、今は無い"},
                              {"ask": 2, "decision": "deny", "paths": [], "tests": [], "spec": "",
                               "reason": "README は今も別の依頼で直す（外した理由は立つ）"}]}
        got = consult.settle(self.b, answer, "first", NODE)
        self.assertEqual(got["counts"], {"allow": 1, "deny": 1})
        rows = conflict.plan_asks(self.b)
        self.assertEqual(rows[0]["overrode_out_of_scope"],
                         [{"path": "works/README.md", "glob": "works/README.md", "why": OOS_WHY}])
        self.assertEqual([(h["path"], h["item"], h["glob"]) for h in rows[0]["out_of_scope"]],
                         [("works/README.md", "3", "works/README.md"), ("works/docs/flow.md", "4", "works/docs/**")])
        self.assertEqual(rows[1]["overrode_out_of_scope"], [], "deny は何も外さない")
        self.assertEqual([h["path"] for h in rows[1]["out_of_scope"]], ["works/README.md"])
        (agreed,) = conflict.agreed(self.b)
        self.assertEqual(agreed["granted_paths"], ["works/README.md", "works/docs/flow.md"])
        text = pathlib.Path(got["answer_file"]).read_text(encoding="utf-8")
        self.assertIn("out_of_scope を外した", text)

    def test_passes_are_separate(self):
        self.ask(reply(ask_row()), pass_="first")
        self.assertEqual(consult.settle(self.b, None, "ruled", NODE)["consulted"], False)
        self.assertEqual(consult.state(self.b, "ruled"), {"turns": 0})

    def test_unavailable_rows_are_recorded(self):
        put_asked(self.b, consult.requests(reply(ask_row())), unavailable="答えの役を起こせない")
        got = consult.settle(self.b, None, "first", NODE)
        self.assertEqual(got["counts"], {"unavailable": 1})
        (row,) = conflict.plan_asks(self.b)
        self.assertIn("起こせない", row["why_unavailable"])

    def test_missing_or_broken_answer(self):
        self.ask(reply(ask_row()))
        consult.settle(self.b, None, "first", NODE)
        self.ask(reply(ask_row()))
        consult.settle(self.b, {"answers": [{"ask": 1, "decision": "allow", "paths": [], "tests": [], "spec": "",
                                             "reason": "全部よい（頼んだ物を名指さない）"}]}, "first", NODE)
        self.ask(reply(ask_row()))
        consult.settle(self.b, {"answers": [{"ask": 2, "decision": "allow", "paths": ["works/CHANGELOG.md"], "tests": [],
                                             "spec": "", "reason": "番号の違う答え"}]}, "first", NODE)
        self.assertEqual([r["status"] for r in conflict.plan_asks(self.b)], ["unavailable", "invalid", "invalid"])
        self.assertEqual(conflict.agreed(self.b), [])

    def test_budget(self):
        for _ in range(consult.BUDGET):
            self.ask(reply(ask_row()))
            self.assertTrue(consult.settle(self.b, None, "first", NODE)["consulted"])
            consult.take(self.b, "first")
        self.assertEqual(consult.left(self.b, "first"), 0)

    def test_round_is_written_on_rows(self):
        self.ask(reply(ask_row()))
        consult.settle(self.b, None, "first", NODE, round_=2)
        self.assertEqual([r["round"] for r in conflict.plan_asks(self.b)], [2])


class ConfigCase(unittest.TestCase):
    """相談の控え（write_config・load_config・offered）"""

    def test_config_round_trip_and_offered(self):
        with tempfile.TemporaryDirectory() as d:
            place = pathlib.Path(d) / "consult"
            self.assertFalse(consult.offered(place, "first"))
            path = consult.write_config(place, {"pass": "first", "items": ITEMS})
            self.assertEqual(consult.load_config(path)["place"], str(place))
            self.assertTrue(consult.offered(place, "first"))
            self.assertFalse(consult.offered(place, "ruled"))
            consult.write_config(place, {"pass": "", "items": {}})
            self.assertFalse(consult.offered(place, "first"), "項目の無い控えは相談を言わない")
            (place / consult.CONFIG).write_text("{", encoding="utf-8")
            with self.assertRaises(ValueError):
                consult.load_config(place / consult.CONFIG)


if __name__ == "__main__":
    unittest.main()
