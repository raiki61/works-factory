"""範囲の相談の部品（workflows/fix/src/consult.py。lib/consult.py の写し）と、相談の script（consult_check・consult_accept）の配線の試験
（docs/design/fix.md の 3 節・8.4・14.2 の test_consult.py。今の lib/tests/test_consult.py の全部と tests/workflows/test_fix.py の
RolesCase の相談の配線を写した）。

縛る事:
- 先の確かめ（screen）: 知らない項目・頼む物が無い・理由が短い・根の外のパス・全部がもう範囲の中の頼みは、答えの役に聞かずに
  断る（記録は残す）。修正案の out_of_scope に当たるパスは断らずに答えの役へ回し（持ち主 2026-10-07「相談で考え直させる」）、
  指示はその項目の out_of_scope（と外した理由）・ほかの項目の out_of_scope の当たりを名指して考え直させる。許せば trace の行に
  out_of_scope を外した印（overrode_out_of_scope）が残る
- 答えの確かめ（judge）: 許すのは頼んだ物の中だけ（足した物は捨てて注記）。形の崩れた答えは invalid で、許しを作らない
- 確かめの節（settle）: 1 頼み 1 行を place の trace.jsonl（conflict.ASKED_OP）に書く（断った・聞けなかった行も）。allow の行は合意
  （conflict.agreed）として範囲とテストの許しに入る。答えのファイルを書き、支度（take）が 1 度だけ引く
- 人の関所の条件（gate_notes・gate_asks）: 今の周の直す前の関所の一言だけを、項目ごとの頼みにする。出し済みなら 2 度聞かない
- 答えの役の指示: asks_text は question の頼みごとの節だけ（決まりの文と答え方の行は md が持つ）。consult_values・consult_render は
  prompts/parts/consult.md の段落（ripple・gate・plain）を頼みの形で選ぶ
- 配線: 段 → 答えの役の表 rules.ANSWER_NODES と YAML の consult_check・consult_accept の pass と answer.from が一致し、consult_check は
  {consulted, go, prompt} を返す
place は使い捨てのフォルダ（git・子のプロセスなし。script の試験だけ kit.Run）。頼みの節の状態は、元の頼みの節（ask）が書いた形を
試験の助けが書く。
"""
import json
import pathlib
import tempfile
import unittest

import yaml

from tests.blocks import kit

BLOCK = kit.BLOCKS / "fix"
OOS_WHY = "README の節は別の依頼で書き直す"
ITEMS = {"3": {"unit_keys": ["lens.py count_line: 落ちたレンズの数"], "allowed_paths": ["works/.shared/core/lens.py"],
               "out_of_scope": [{"glob": "works/README.md", "why": OOS_WHY}], "tests": ["works/tests/test_lens.py"]},
         "4": {"unit_keys": ["report.py head: 頭の行"], "allowed_paths": ["works/.shared/core/report.py"],
               "out_of_scope": [{"glob": "works/docs/**", "why": "文書は項目 4 では触らない"}], "tests": []}}
WHY = "直しに伴って変更の記録を足す要がある"
NODE = "consult-answer"


def _load():
    """src.consult を読み込み、lib の conflict・gatemarks・jsonfile・planrange と一緒に返す"""
    consult = kit.load("fix", "consult")
    import conflict
    import gatemarks
    import jsonfile
    import planrange
    return consult, conflict, gatemarks, jsonfile, planrange


consult, conflict, gatemarks, jsonfile, planrange = _load()
GATE = gatemarks.GATE_NODE


def reply(*asks):
    return {"changes": [], conflict.CONSULT_FIELD: list(asks)}


# 修正役の頼みが必ず持つ 3 つの欄（試したこと・範囲の中で直せない訳・根拠のファイルと行。#833）
SUMMARY = {"tried": ["lens.py の count_line の数え方を直した"],
           "blocked": "数えは直ったが、変更の記録が範囲の外の CHANGELOG にしか無い",
           "evidence": [{"path": "works/.shared/core/lens.py", "line": 12}]}


def ask_row(item=3, paths=("works/CHANGELOG.md",), tests=(), why=WHY, **summary):
    return {"item": item, "paths": list(paths), "tests": list(tests), "why": why, **(summary or SUMMARY)}


def put_asked(place, asks, pass_="first", node=NODE, items=ITEMS, unavailable=""):
    """頼みの節の状態を置く（元の consult.ask が書いた形: 頼みごとに screen と oos_hits を当て、turns を 1 つ進め、turn_state を asked
    に）。asks は requests の形の行（と queued の行）。unavailable を渡すと聞く頼みを聞けなかった行にする。返り (状態, 指示書の本文)"""
    st = consult.state(place, pass_)
    turn = int(st.get("turns") or 0) + 1
    rows = []
    for n, a in enumerate(asks, 1):
        new_tests = a.get("new_tests") or []
        why = consult.screen_ask(items, a)
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
    return doc, consult.asks_text(items, asked) if asked else ""


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.b = pathlib.Path(self._tmp.name).resolve() / "place"
        self.b.mkdir()

    def ask(self, r, pass_="first"):
        return put_asked(self.b, consult.requests(r) or [], pass_)


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

    def test_trailing_slash_scope_globs_cover_paths_underneath(self):
        """consult が範囲の当て方を globs.glob_match から引く柵"""
        items = {"3": {**ITEMS["3"], "allowed_paths": ["works/.shared/core/"],
                       "out_of_scope": [{"glob": "works/docs/", "why": OOS_WHY}]}}
        self.assertIn("範囲の中", consult.screen(items, "3", ["works/.shared/core/lens.py"], [], WHY))
        hits = consult.oos_hits(items, "3", ["works/docs/flow.md"], [])
        self.assertEqual([(h["path"], h["item"], h["glob"]) for h in hits], [("works/docs/flow.md", "3", "works/docs/")])

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


class SummaryCase(unittest.TestCase):
    """#833: 修正役の頼み（origin の無い行）は、試したこと・範囲の中で直せない訳・根拠のファイルと行の 3 つを持たないと、答えの役に
    聞かずに断る（差し戻し）。受け付けが積んだ頼みと人の関所の条件の頼みは修正役が書いた物でないので照らさない"""

    def ask(self, **over):
        return {**ask_row(), **over}

    def test_full_summary_passes(self):
        self.assertIsNone(consult.screen_ask(ITEMS, consult.requests(reply(ask_row()))[0]))

    def test_missing_parts_are_refused(self):
        cases = {"試したこと": {"tried": []}, "直せない訳": {"blocked": "短い"},
                 "根拠": {"evidence": []}}
        for word, over in cases.items():
            with self.subTest(word=word):
                (a,) = consult.requests(reply(self.ask(**over)))
                self.assertIn(word, consult.screen_ask(ITEMS, a) or "")
        for bad in ([{"path": "../x.py", "line": 3}], [{"path": "a.py", "line": 0}], [{"path": "", "line": 3}], ["a.py:3"]):
            with self.subTest(evidence=bad):
                (a,) = consult.requests(reply(self.ask(evidence=bad)))
                self.assertIn("根拠", consult.screen_ask(ITEMS, a) or "")
        (a,) = consult.requests(reply({"item": 3, "paths": ["works/CHANGELOG.md"], "tests": [], "why": WHY}))
        self.assertIn("試したこと", consult.screen_ask(ITEMS, a) or "", "3 つの欄の無い頼みも断る")

    def test_machine_asks_are_not_checked(self):
        for origin in (consult.ORIGIN_ACCEPT, consult.ORIGIN_GATE):
            with self.subTest(origin=origin):
                a = {"item": "3", "paths": ["works/CHANGELOG.md"], "tests": [], "new_tests": [], "why": WHY, "origin": origin}
                self.assertIsNone(consult.screen_ask(ITEMS, a))

    def test_summary_reaches_the_answerer(self):
        (a,) = consult.requests(reply(ask_row()))
        text = consult.asks_text(ITEMS, [{**a, "n": 1}])
        for w in ("試したこと", SUMMARY["tried"][0], "範囲の中で直せない訳", SUMMARY["blocked"], "works/.shared/core/lens.py:12"):
            self.assertIn(w, text)


class HistoryCase(Base):
    """#833: 答えの役は新しい会話なので、同じ run の前の相談と答えの一覧（place の trace の相談の行）を指示で受け取る"""

    def test_empty_without_earlier_rows(self):
        self.assertEqual(consult.history_text(self.b), "")

    def test_earlier_rows_are_listed_with_their_answers(self):
        self.ask(reply(ask_row(), ask_row(paths=["../outside.md"])))
        consult.settle(self.b, {"answers": [{"ask": 1, "decision": "deny", "paths": [], "tests": [], "spec": "",
                                             "reason": "変更の記録は別の依頼で足す"}]}, "first", NODE)
        text = consult.history_text(self.b)
        for w in ("相談 1", "first", "works/CHANGELOG.md", "deny", "変更の記録は別の依頼で足す", "相談 2", "refused", "根の外"):
            self.assertIn(w, text)


class QuestionCase(unittest.TestCase):
    def test_own_out_of_scope_is_named_with_its_reason(self):
        """頼みの節は、頼んだパスがあなた自身がこの項目の out_of_scope に書いた物だと言い、外した理由を字のまま引く。考え直させる決まりの文は
        md（prompts/parts/consult.md）が持つ"""
        sec = consult.asks_text(ITEMS, [{"n": 1, "item": "3", "paths": ["works/README.md"], "tests": [], "why": WHY}])
        for w in ("works/README.md", "out_of_scope", OOS_WHY, "あなたがこの項目の out_of_scope"):
            self.assertIn(w, sec)
        self.assertNotIn("考え直", sec)
        self.assertIn("reconsider whether the reason for the exclusion still holds",
                      (BLOCK / "prompts" / "parts" / "consult.md").read_text(encoding="utf-8"))

    def test_other_item_out_of_scope_is_named(self):
        sec = consult.asks_text(ITEMS, [{"n": 1, "item": "3", "paths": ["works/docs/flow.md"], "tests": [], "why": WHY}])
        for w in ("works/docs/flow.md", "項目 4 の out_of_scope", "works/docs/**", "文書は項目 4 では触らない"):
            self.assertIn(w, sec)
        self.assertNotIn("あなたがこの項目の out_of_scope", sec)

    def test_plain_ask_says_nothing_about_out_of_scope_hits(self):
        q = consult.asks_text(ITEMS, [{"n": 1, "item": "3", "paths": ["works/CHANGELOG.md"], "tests": [], "why": WHY}])
        self.assertNotIn("当たる", q)


class AsksTextCase(unittest.TestCase):
    """答えの役の指示の差し込み口 {asks}（consult.asks_text）: 頼みごとの節だけで、決まりの文と関所の頼みの答え方は持たない
    （md の prompts/parts/consult.md が持つ）"""

    PLAIN = {"n": 1, "item": "3", "paths": ["works/README.md"], "tests": [], "why": WHY}
    GATE_ASK = {"n": 2, "item": "4", "paths": [], "tests": [], "why": "既存の集計を壊さないことを確かめよ", "origin": "gate"}

    def test_sections_are_the_question_sections_without_the_rules(self):
        text = consult.asks_text(ITEMS, [self.PLAIN])
        self.assertTrue(text.startswith("## 相談 1: 項目 3"), text)
        self.assertNotIn("# 範囲の相談（修正の段から）", text)
        self.assertNotIn("答えは次の JSON だけ", text)
        for w in ("works/README.md", OOS_WHY, "あなたがこの項目の out_of_scope", WHY):
            self.assertIn(w, text)

    def test_gate_ask_has_no_answer_how_line(self):
        text = consult.asks_text(ITEMS, [self.PLAIN, self.GATE_ASK])
        self.assertIn("## 相談 2: 項目 4", text)
        self.assertIn("既存の集計を壊さないことを確かめよ", text)
        self.assertNotIn("- 答え方:", text, "関所の頼みの答え方は md の段落 gate が持つ")
        self.assertFalse(text.endswith("\n"))


class ConsultPromptCase(unittest.TestCase):
    """src.prompts.consult_values・consult_render: 頼みの形で md の段落を選び、項目の頼みの節を {asks} に入れる"""

    PLAIN = AsksTextCase.PLAIN
    GATE_ASK = AsksTextCase.GATE_ASK

    def setUp(self):
        self.run = kit.Run(self, "fix")
        self.prompts = kit.load("fix", "prompts")
        self.md = (BLOCK / "prompts" / "parts" / "consult.md").read_text(encoding="utf-8")

    def test_values_and_paragraphs(self):
        with self.run.env():
            vals, when = self.prompts.consult_values(self.run.artifacts, ITEMS, [self.PLAIN], plan_file="/p/plan.json", ripple_file="")
            self.assertEqual(when, {"ripple": False, "gate": False, "plain": True, "history": False})
            self.assertEqual((vals["plan_file"], vals["count"], vals["min_why"]), ("/p/plan.json", 1, consult.MIN_WHY))
            self.assertEqual(vals["asks"], consult.asks_text(ITEMS, [self.PLAIN]))
            _, when = self.prompts.consult_values(self.run.artifacts, ITEMS, [self.GATE_ASK], plan_file="", ripple_file="/p/r.json")
            self.assertEqual(when, {"ripple": True, "gate": True, "plain": False, "history": False})
            vals, when = self.prompts.consult_values(self.run.artifacts, ITEMS, [self.PLAIN, self.GATE_ASK], plan_file="",
                                                     ripple_file="")
            self.assertEqual((when["gate"], when["plain"]), (True, True))
            self.assertEqual(vals["plan_file"], "（修正案のファイルは無い）")

    def test_history_paragraph_carries_earlier_answers(self):
        """#833: 前の相談の行が place に在れば、段落 history に一覧が入る。無ければ段落ごと出ない"""
        with self.run.env():
            vals, when = self.prompts.consult_values(self.run.artifacts, ITEMS, [self.PLAIN], plan_file="", ripple_file="")
            self.assertEqual((when["history"], vals["history"]), (False, ""))
            put_asked(self.run.artifacts, consult.requests(reply(ask_row())) or [])
            consult.settle(self.run.artifacts, {"answers": [{"ask": 1, "decision": "deny", "paths": [], "tests": [], "spec": "",
                                                             "reason": "変更の記録は別の依頼で足す"}]}, "first", NODE)
            vals, when = self.prompts.consult_values(self.run.artifacts, ITEMS, [self.PLAIN], plan_file="", ripple_file="")
            self.assertTrue(when["history"])
            self.assertEqual(vals["history"], consult.history_text(self.run.artifacts))
            text = self.prompts.consult_render(self.run.artifacts, "first", plan_file="", ripple_file="")(ITEMS, [self.PLAIN])
        self.assertIn("Earlier consultations in this run", text)
        self.assertIn("変更の記録は別の依頼で足す", text)

    def test_render_builds_the_answer_prompt_from_the_md(self):
        with self.run.env():
            render = self.prompts.consult_render(self.run.artifacts, "first", plan_file="/p/plan.json", ripple_file="/p/ripple.json")
            text = render(ITEMS, [self.PLAIN])
            again = self.prompts.consult_render(self.run.artifacts, "ruled", plan_file="", ripple_file="")(ITEMS, [self.GATE_ASK])
        for w in ("Read the fix plan /p/plan.json first", "Read the ripple list /p/ripple.json", "# Scope consultation (from the fixing stage)",
                  "How to answer a request for paths and tests", consult.asks_text(ITEMS, [self.PLAIN])):
            self.assertIn(w, text)
        self.assertNotIn("How to answer a consultation about a condition given at the approval node", text)
        self.assertIn("How to answer a consultation about a condition given at the approval node", again)
        self.assertNotIn("Read the ripple list", again)
        self.assertNotIn("How to answer a request for paths and tests", again)
        self.assertTrue((self.run.artifacts / "consult-answer-prompt-1.md").is_file(), "組んだ指示は place に控える")
        self.assertTrue((self.run.artifacts / "ruled-consult-answer-prompt-1.md").is_file())


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
        self.assertEqual(got, [{"item": "3", "paths": ["a.md"], "tests": ["t.py:3"], "why": WHY, **SUMMARY}])
        self.assertEqual(consult.requests({conflict.CONSULT_FIELD: ["x"]}),
                         [{"item": "", "paths": [], "tests": [], "why": "", "tried": [], "blocked": "", "evidence": []}],
                         "形の崩れた頼みは欄を空にして残す（screen_ask が断る）")


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

    def test_carry_agreed_copies_returned_childrens_agreed_rows_once(self):
        """戻せた組の子の置き場の allow の行だけを、group_id つきで親の trace に足す（deny の行・置き場の無い結果・親と同じ置き場は
        写さない）。2 度呼んでも増えない。その後に親で起こす相談の id は、写した行の最大の次から振る"""
        fixboard = consult.fixboard
        child = self.b.parent / "child"
        child.mkdir()
        _, _q = put_asked(child, consult.requests(reply(
            ask_row(paths=["../outside.md"]), ask_row(paths=["works/CHANGELOG.md"]), ask_row(paths=["works/NEWS.md"]))) or [])
        answers = {"answers": [{"ask": 2, "decision": "allow", "paths": ["works/CHANGELOG.md"], "tests": [], "spec": "",
                                "reason": "子が直しに伴う記録を足す"},
                               {"ask": 3, "decision": "deny", "paths": [], "tests": [], "spec": "", "reason": "範囲の中で直せる"}]}
        consult.settle(child, answers, "first", NODE)
        (own,) = conflict.agreed(child)
        self.assertEqual(own["id"], 2)
        results = [{"group_id": "g1", "place": str(child)}, {"group_id": "g2", "place": ""}, {"group_id": "g3", "place": str(self.b)},
                   {"group_id": "g4"}]
        consult.carry_agreed(self.b, results)
        (row,) = conflict.plan_asks(self.b, carried=True)
        self.assertEqual({k: v for k, v in row.items() if k not in ("op", "group_id")}, {k: v for k, v in own.items() if k != "op"})
        self.assertEqual((row["op"], row["group_id"]), (conflict.ASKED_OP, "g1"))
        consult.carry_agreed(self.b, results)
        self.assertEqual(len(conflict.plan_asks(self.b, carried=True)), 1, "2 度呼んでも行は増えない")
        self.assertEqual(len(fixboard.trace_rows(self.b, lambda r: r.get("op") == conflict.ASKED_OP)), 1)
        self.assertEqual(len(conflict.plan_asks(child)), 3, "子の置き場は変えない")
        self.ask(reply(ask_row()))
        consult.settle(self.b, {"answers": [{"ask": 1, "decision": "deny", "paths": [], "tests": [], "spec": "",
                                             "reason": "範囲の中で直せる"}]}, "first", NODE)
        self.assertEqual([r["id"] for r in conflict.plan_asks(self.b, carried=True)], [2, 3], "写した行の最大の次から振る")

    def test_carried_rows_widen_scope_but_are_not_asked_here(self):
        """写した行（group_id つき）は、親が自分で聞いた行（plan_asks の既定）には出ない。gate_asks は BASE どおり全部の項目を返す。
        一方、agreed と with_agreed には入る（agreed(carried=False) には入らない）"""
        note = "既存の集計を壊さないことを確かめるテストを足してから直せ"
        human = [{"round": 1, "node": GATE, "kinds": ["final"], "answer": "continue", "note": note}]
        consult.fixboard.trace(self.b, conflict.ASKED_OP, id=1, item="3", status="answered", decision="allow",
                               origin=consult.ORIGIN_GATE, round=1, granted_paths=["works/CHANGELOG.md"], granted_tests=[],
                               granted_new_tests=[], reason="子で許した", group_id="g1")
        self.assertEqual(conflict.plan_asks(self.b), [])
        self.assertEqual([a["item"] for a in consult.gate_asks(self.b, ITEMS, human)], ["3", "4"],
                         "写した関所の相談の行は、この置き場で関所の条件を出し済みにしない")
        (got,) = conflict.agreed(self.b)
        self.assertEqual((got["id"], got["group_id"]), (1, "g1"))
        self.assertEqual(conflict.agreed(self.b, carried=False), [])
        self.assertEqual(conflict.plan_asks(self.b, carried=True), [got])
        items = [{"item": 3, "allowed_paths": ["works/.shared/core/lens.py"], "tests": []}]
        (merged,) = planrange.with_agreed(items, conflict.agreed(self.b))
        self.assertIn("works/CHANGELOG.md", merged["allowed_paths"])
        self.assertEqual(planrange.scope(self.b, items=items, ruled=False)[0]["agreed"], [got])

    def test_carried_new_test_enters_the_accept_gate_as_an_agreed_permit(self):
        """子が許した新しいテスト（写した行の granted_new_tests）は、親の事後の関門の受け入れのテストに印 agreed で入る（今の木に
        在る物だけ。許しで義務でない）。親が自分で聞いていない行でも、写した行は既定の読み口 conflict.agreed に入るため"""
        gates = kit.load("fix", "gates")
        consult.fixboard.trace(self.b, conflict.ASKED_OP, id=1, item="1", status="answered", decision="allow", origin="",
                               granted_paths=[], granted_tests=[], reason="子が足した",
                               granted_new_tests=[{"id": "test_new.py::T::test_a", "red_kind": "assertion"}], group_id="g1")
        fields = [{"unit_keys": ["u"], "route": "direct", "tests": [], "allowed_paths": ["a.py"]}]
        tests, _ = gates._accept_tests(self.b, fields, None, owed={"u"})
        self.assertEqual([(t["id"], t["agreed"]) for t in tests], [("test_new.py::T::test_a", True)])
        self.assertEqual(conflict.plan_asks(self.b), [], "親が聞いた行ではない")

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
        self.assertIn("The acceptance found a change outside the scope", pathlib.Path(got["answer_file"]).read_text(encoding="utf-8"))
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
        self.assertEqual(consult.gate_notes(self.b, pushed), f"{consult.answer.PUSHED_NOTE}\n{note}")   # 推しの条件は人の答えと名乗らない
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

    def test_pushed_gate_condition_is_not_asked_again_after_a_grant_of_the_item(self):
        """無人の run が推しで通した関所の条件（人の言葉でない。機械が採った推しの再掲）は、その周にその項目で許しの行（合意）が
        既に在れば、答えの役を起こして聞き直さない（run 9744721f の 2 回目: 求める物が 0 の相談に、前の許しをそのまま当てた）。
        人の条件は許しの有る項目でも聞く。許しの無い項目の推しの条件は今までどおり聞く"""
        note = "区切りの単独行だけを数えから外す範囲で通す"
        pushed = [{"round": 1, "node": GATE, "kinds": ["final"], "answer": "continue", "note": note,
                   consult.answer.PUSHED: [{"item": "x", "answer": "continue", "note": note, "why": "y"}]}]
        human = [{"round": 1, "node": GATE, "kinds": ["final"], "answer": "continue", "note": note}]
        self.assertEqual([a["item"] for a in consult.gate_asks(self.b, ITEMS, pushed)], ["3", "4"], "許しが無ければ聞く")
        first = {"item": 3, "paths": ["works/CHANGELOG.md"], "tests": [], "why": WHY, **SUMMARY}
        put_asked(self.b, [first])
        consult.settle(self.b, {"answers": [{"ask": 1, "decision": "allow", "paths": ["works/CHANGELOG.md"], "tests": [], "spec": "",
                                              "reason": "変更の記録を足してよい"}]}, "first", NODE)
        self.assertEqual([a["item"] for a in consult.gate_asks(self.b, ITEMS, pushed)], ["4"], "項目 3 は許し済みなので聞き直さない")
        self.assertEqual([a["item"] for a in consult.gate_asks(self.b, ITEMS, human)], ["3", "4"], "人の条件は許し済みの項目でも聞く")

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
        self.assertIn("out_of_scope was lifted", text)

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


# ---------------------------------------------------------------- 相談の script と YAML の配線（今の RolesCase と FixLoopScriptsCase の相談の部分）
def _nodes() -> dict:
    """block の YAML の node を loop_group の中まで（id → node）"""
    doc = yaml.safe_load((BLOCK / "works-factory-fix.yaml").read_text(encoding="utf-8"))
    out = {}

    def walk(nodes):
        for node in nodes:
            out[node["id"]] = node
            walk((node.get("loop_group") or {}).get("nodes") or [])
    walk(doc["nodes"])
    return out


class ConsultWiringCase(unittest.TestCase):
    def setUp(self):
        self.nodes = _nodes()
        self.rules = kit.load("fix", "rules")

    def test_answer_nodes_are_keyed_by_passes_and_name_nodes_here(self):
        """#385: 段 → 範囲の相談に答える役の node は rules.PASSES を鍵にした表 1 つ。値はどれもこの YAML の node で、段ごとの組みは
        YAML の配線（consult_accept の pass: と answer.from の輪、その輪が待つ同じ段の consult_check）と一致する。表に無い段は例外"""
        rules = self.rules
        self.assertEqual(tuple(rules.ANSWER_NODES), rules.PASSES)
        for pass_, nid in rules.ANSWER_NODES.items():
            self.assertIn(nid, self.nodes, pass_)
            self.assertEqual(rules.answer_node(pass_), nid)
        checks = {n["with"]["pass"]: nid for nid, n in self.nodes.items() if n.get("script") == "consult_check"}
        accepts = {n["with"]["pass"]: n for n in self.nodes.values() if n.get("script") == "consult_accept"}
        self.assertEqual(set(checks), set(rules.PASSES))
        self.assertEqual(set(accepts), set(rules.PASSES))
        for pass_, accept in accepts.items():
            ask = accept["with"]["answer"]["from"].removeprefix("$").removesuffix(".output")   # 答えの役 1 つだけを置いた輪（13.3 の 1）
            self.assertEqual([m["id"] for m in self.nodes[ask]["loop_group"]["nodes"]], [rules.answer_node(pass_)], pass_)
            self.assertEqual(self.nodes[ask]["depends_on"], [checks[pass_]], pass_)
            self.assertEqual(self.nodes[rules.answer_node(pass_)]["prompt"], f"${checks[pass_]}.output.prompt", pass_)
            self.assertEqual(self.nodes[ask]["when"], f"${checks[pass_]}.output.go == true", pass_)
        with self.assertRaises(ValueError):
            self.rules.answer_node("refix")

    def test_check_returns_consulted_go_and_prompt(self):
        """consult_check の返りは {consulted, go, prompt}（今の prompt_file は prompt の字に）、consult_accept は {consulted, answer_file}"""
        for nid, n in self.nodes.items():
            if n.get("script") == "consult_check":
                self.assertEqual(set(n["output_format"]["required"]), {"consulted", "go", "prompt"}, nid)
            if n.get("script") == "consult_accept":
                self.assertEqual(set(n["output_format"]["required"]), {"consulted", "answer_file"}, nid)

    def test_answer_roles_are_read_only(self):
        """相談の答えの役は作業ツリーを変えない（mutates_checkout: false・書く道具を持たない）"""
        for nid in self.rules.ANSWER_NODES.values():
            node = self.nodes[nid]
            self.assertIs(node.get("mutates_checkout"), False, nid)
            self.assertFalse({"Write", "Edit", "Bash", "NotebookEdit", "MultiEdit"} & set(node.get("allowed_tools") or []), nid)


_MEAN = "u-mean"


class ConsultScriptsCase(unittest.TestCase):
    """consult_check・consult_accept を子のプロセスで回す（place は ARTIFACTS_DIR。修正案の欄の控えと返答の写しを試験が置く）"""

    def setUp(self):
        self.run = kit.Run(self, "fix")
        self.place = self.run.artifacts
        board = kit.load("fix", "board")
        import planmarks
        planmarks.save(self.place, 1, [{"route": "direct", "tests": [], "rewrite_tests": [], "allowed_paths": ["stats.py"],
                                        "out_of_scope": []}])
        (self.place / board.PLAN_REPLY_FILE).write_text(json.dumps(
            {"plan": [{"unit_keys": [_MEAN], "approach": "分母を直す", "adds": [], "removes": []}]}, ensure_ascii=False),
            encoding="utf-8")
        self.plan_reply = self.place / board.PLAN_REPLY_FILE

    def test_consult_check_launches_the_answer_on_an_ask(self):
        """返答の consult の頼みで答えの役の指示を組んで go: true、答えを受けて答えのファイルを書く"""
        reply_ = {"changes": [], "consult": [{"item": 1, "paths": ["docs/notes.md"], "tests": [],
                                              "why": "直しに伴う変更の記録を docs に残す要がある（範囲の外）", **SUMMARY}]}
        out = self.run.script("consult_check", reply=json.dumps(reply_, ensure_ascii=False), **{"pass": "first"})
        self.assertEqual(set(out), {"consulted", "go", "prompt"})
        self.assertEqual((out["consulted"], out["go"]), (True, True), out)
        self.assertIn(str(self.plan_reply), out["prompt"])
        self.assertIn("docs/notes.md", out["prompt"])
        self.assertIn("# Scope consultation (from the fixing stage)", out["prompt"])
        self.assertEqual((self.place / "consult-answer-prompt-1.md").read_text(encoding="utf-8"), out["prompt"])
        out = self.run.script("consult_check", reply=json.dumps({"changes": []}), **{"pass": "first"})
        self.assertEqual((out["consulted"], out["go"], out["prompt"]), (False, False, ""))
        answer = {"answers": [{"ask": 1, "decision": "allow", "paths": ["docs/notes.md"], "tests": [], "spec": "",
                               "reason": "記録を残すのは直しに伴う変更なので足してよい"}]}
        out = self.run.script("consult_accept", answer=json.dumps(answer, ensure_ascii=False), **{"pass": "first"})
        self.assertTrue(out["consulted"], out)
        self.assertIn("docs/notes.md", pathlib.Path(out["answer_file"]).read_text(encoding="utf-8"))
        (agreed,) = conflict.agreed(self.place)
        self.assertEqual(agreed["granted_paths"], ["docs/notes.md"])

    def test_ruled_pass_uses_its_own_answer_node_and_state(self):
        """段 ruled の頼みは ruled-consult-answer の指示を組み、段 first の状態と別に数える。答えの役が飛ばされた周（answer が null）は
        頼みの行を unavailable で残す"""
        reply_ = {"changes": [], "consult": [{"item": 1, "paths": ["docs/notes.md"], "tests": [],
                                              "why": "直しに伴う変更の記録を docs に残す要がある（範囲の外）", **SUMMARY}]}
        out = self.run.script("consult_check", reply=json.dumps(reply_, ensure_ascii=False), **{"pass": "ruled"})
        self.assertEqual((out["consulted"], out["go"]), (True, True), out)
        self.assertTrue((self.place / "ruled-consult-answer-prompt-1.md").is_file())
        self.assertFalse((self.place / "consult-answer-prompt-1.md").exists())
        self.assertEqual(consult.state(self.place, "first"), {"turns": 0})
        self.assertEqual(consult.state(self.place, "ruled")["node"], "ruled-consult-answer")
        out = self.run.script("consult_accept", answer="null", **{"pass": "ruled"})
        self.assertTrue(out["consulted"], out)
        (row,) = conflict.plan_asks(self.place)
        self.assertEqual((row["status"], row["pass"], row["node"]), ("unavailable", "ruled", "ruled-consult-answer"))

    def test_refused_only_ask_does_not_launch(self):
        """先の確かめで全部断った頼みは答えの役を起こさない（consulted: true・go: false・prompt は空）"""
        reply_ = {"changes": [], "consult": [{"item": 1, "paths": ["../outside.md"], "tests": [], "why": WHY, **SUMMARY}]}
        out = self.run.script("consult_check", reply=json.dumps(reply_, ensure_ascii=False), **{"pass": "first"})
        self.assertEqual((out["consulted"], out["go"], out["prompt"]), (True, False, ""))
        out = self.run.script("consult_accept", answer="null", **{"pass": "first"})
        (row,) = conflict.plan_asks(self.place)
        self.assertEqual(row["status"], "refused")


if __name__ == "__main__":
    unittest.main()
