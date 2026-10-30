"""設計の段（テーマの run。docs/design/line.md の 3.3 節。issue #862 の PR T3）: start の入口の欄 theme・依頼の出どころ request-in・
設計の往復の周の頭と終わり（src/talk.py の段 THEME と src/themetalk.py）・降りる theme-descend と設計へ戻す theme-return（src/descend.py）・
YAML の配線（判定から後ろは依頼を request-in からだけ読む・答えの語 redesign は計画の承認ノードだけ）。
"""
import json
import pathlib
import re
import unittest

import yaml

from tests.blocks import kit
from tests.blocks.line import test_start as ts
from tests.blocks.line.test_talk import TalkBase
from tests.blocks.theme import values as tv

BLOCK = "line"
LINE_YAML = kit.BLOCKS / "line" / "works-factory-line.yaml"
REQUEST_FIELDS = ("request", "request_file", "request_answers", "entry", "request_origin", "request_scope", "prior_rows")


# ---------------------------------------------------------------- 入口（start）
class ThemeStartCase(ts.Seeded):
    def theme_request(self, theme, **more) -> str:
        return str(self.outside("theme-request.json", json.dumps({"theme": theme, **more}, ensure_ascii=False)))

    def test_theme_text_starts_a_theme_run(self):
        got = self.start(request=self.theme_request("段を何段に分けるか"), design_talk="true")
        self.assertTrue(got["ok"], got)
        ports = got["ports"]
        self.assertEqual(pathlib.Path(ports["theme"]).read_text(encoding="utf-8"), "段を何段に分けるか\n")
        self.assertEqual(ports["theme_text"], "段を何段に分けるか")
        request = json.loads((self.artifacts / ports["theme_request"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(request, {"findings": [{"where": "テーマ", "text": "段を何段に分けるか"}]})
        self.assertEqual(self.record(got)["theme"], ports["theme"])

    def test_theme_md_is_read_from_the_target(self):
        (self.repo / "theme.md").write_text("# テーマ\n\n型を分けるか\n", encoding="utf-8")
        got = self.start(request=self.theme_request("theme.md"), design_talk="true")
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["ports"]["theme_text"], "# テーマ\n\n型を分けるか")

    def test_theme_run_needs_design_talk_and_no_rows(self):
        self.assertIn("design_talk=true", self.refused(request=self.theme_request("x")))
        self.assertIn("依頼の行（findings）", self.refused(request=self.theme_request("x", findings=[{"where": "a", "text": "b"}]),
                                                    design_talk="true"))
        self.assertIn("差分の根（base）", self.refused(request=self.theme_request("x"), base="base", design_talk="true"))
        self.assertIn("が無い", self.refused(request=self.theme_request("nowhere.md"), design_talk="true"))

    def test_runs_without_a_theme_deal_empty_theme_ports(self):
        got = self.start(request="request_ok.json")
        self.assertEqual((got["ports"]["theme"], got["ports"]["theme_text"], got["ports"]["theme_request"]), ("", "", None))


# ---------------------------------------------------------------- 周の頭と終わり（段 THEME）・降りる・戻す
class ThemeStageCase(TalkBase):
    def setUp(self):
        super().setUp()
        with self.run.env():
            self.tt = kit.load(BLOCK, "themetalk")
            self.d = kit.load(BLOCK, "descend")
            self.t = kit.load(BLOCK, "talk")
            self.r = kit.load(BLOCK, "rounds")
        (self.run.artifacts / "theme.md").write_text(tv.THEME_MD, encoding="utf-8")
        self.given = {"design_talk": True, "unattended": False, "theme": str(self.run.artifacts / "theme.md"),
                      "request_answers": [{"question": "q", "text": "a"}], "prior_rows": []}

    def design(self, **over) -> dict:
        return {**tv.reply(), **over}

    def theme_out(self, design=None, faces=(), **over) -> dict:
        """theme-out の返り（src.themetalk.record で、書き手の案と事前審査の返答から組む）"""
        d = self.put("theme/r1/design.json", design or self.design())
        md = self.run.artifacts / "theme/r1/design.md"
        md.write_text("# 設計の案\n", encoding="utf-8")
        holes = self.put("plan-review/review.json", {"faces": list(faces), "shrink": [], "reason": "読んだ"})
        with self.run.env():
            got = self.tt.record({"ok": True, "status": "ok", "design": d, "design_md": json.loads(self.run.pointer("theme/r1/design.md")),
                                  "reason": ""}, {"ok": True, "status": "ok", "holes": holes, "reason": ""}, "", place=self.run.artifacts)
        return {**got, **over}

    def theme_turn(self, answer="", previous=None, last=None, given=None):
        with self.run.env():
            return self.t.turn(answer_raw=answer if isinstance(answer, str) else json.dumps(answer),
                               previous_raw=json.dumps(previous) if previous is not None else "",
                               last_raw=json.dumps(last) if last is not None else "", given=given or self.given, recorded=[],
                               place=self.run.artifacts, stage=self.t.THEME,
                               check=lambda said: self.tt.check(said, self.tt.design_asks(previous or {})))

    def theme_settle(self, turn_got, po, previous=None, given=None):
        with self.run.env():
            return self.t.settle(turn_got=turn_got, plan_out=po, previous=previous, given=given or self.given, materials=None,
                                 run_id=kit.RUN_ID, place=self.run.artifacts, stage=self.t.THEME)

    # ---------------------------------------------- 往復の記録（項目の無い記録で止め時の決まりがそのまま回る。下書きの 14 章の 3）
    def test_theme_out_records_a_pass_without_items(self):
        po = self.theme_out()
        self.assertEqual((po["done"], po["ok"], po["round"]), (True, True, 1), po)
        doc = json.loads((self.run.artifacts / "theme-converge.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["outcome"], self.r.CLEAN)
        self.assertNotIn("plan", doc)
        again = self.theme_out(faces=[{"key": "gap", "kind": "scope_creep", "where": "Q1", "why": "w" * 20, "severity": "block",
                                       "reach": "forces_redesign"}])
        self.assertEqual((again["done"], again["ok"]), (False, False), "中央の block の 1 往復目は AGAIN")

    # ---------------------------------------------- 関所を開く・答えを読む
    def test_the_gate_opens_with_the_design_and_the_owner_questions(self):
        got = self.theme_settle(self.theme_turn(), self.theme_out())
        self.assertEqual((got["open"], got["done"]), (True, False))
        self.assertIn("設計の段の承認ノード（gate-theme）", got["text"])
        self.assertIn("設計の問い Q1", got["text"])
        self.assertIn("## 問いへの答え", got["text"])
        self.assertNotIn("redesign", got["text"], "設計の段に設計へ戻す答えは無い")
        self.assertTrue((self.run.artifacts / "talk/theme-1.md").is_file())

    def test_sections_of_the_answer_become_human_rows(self):
        prev = self.theme_settle(self.theme_turn(), self.theme_out())
        said = {"decision": "revise", "text": "## 持ち主の言葉\n短いほうがいい\n## 問いへの答え\n- Q1: A2（消してよい）\n"}
        got = self.theme_turn(said, previous=prev)
        self.assertTrue(got["plan"], got)
        rows = self.tt.answer_rows(got["talks"], self.given["request_answers"])
        self.assertEqual([(r["id"], r["kind"]) for r in rows], [("H1", "note"), ("H2", "owner_words"), ("H3", "ask_answer")])
        self.assertEqual((rows[2]["ask"], rows[2]["pick"]), ("Q1", "A2"))
        self.assertEqual(kit.shaped("shared:human-answers.schema.json", rows), rows)
        self.assertTrue((self.run.artifacts / "gates/gate-theme.json").is_file())

    def test_unreadable_sections_ask_again_without_redesigning(self):
        prev = self.theme_settle(self.theme_turn(), self.theme_out())
        got = self.theme_turn({"decision": "approve", "text": "## 問いへの答え\n- Q9: A1\n"}, previous=prev)
        self.assertFalse(got["plan"])
        self.assertIn("Q9 は見せた問いに無い", got["reason"])
        again = self.theme_settle(got, None, previous=prev)
        self.assertEqual((again["open"], again["done"]), (True, False), "同じ文で聞き直す")
        self.assertTrue(again["text"].startswith(got["reason"]))

    def test_each_line_of_the_ask_answers_is_one_answer(self):
        """問いへの答えは 1 行に 1 つ。「- 」の無い行も行ごとに照らし、つなげて 1 つに読んだり、「- 」の行に混ざった行を捨てたりしない"""
        asks = [{"id": "Q1", "options": [{"id": "A1"}, {"id": "A2"}]}, {"id": "Q2", "options": [{"id": "A1"}]}]
        for text in ("## 問いへの答え\nQ1: A2\nQ9: A9\n", "## 問いへの答え\n- Q1: A2\nQ9: A1\n"):
            with self.subTest(text=text):
                self.assertIn("Q9 は見せた問いに無い", self.tt.check({"text": text}, asks))
        text = "## 問いへの答え\n- Q1: A2（消してよい）\nQ2: A1\n"
        self.assertEqual(self.tt.check({"text": text}, asks), "")
        rows = self.tt.answer_rows([{"decision": "revise", "text": text}])
        self.assertEqual([(r["ask"], r["pick"], r["text"]) for r in rows], [("Q1", "A2", "Q1: A2（消してよい）"), ("Q2", "A1", "Q2: A1")])

    def test_approval_in_the_inbox_does_not_skip_open_questions(self):
        (self.run.artifacts / "talk").mkdir(exist_ok=True)
        (self.run.artifacts / "talk/notes.txt").write_text("承認: 進めて\n", encoding="utf-8")
        got = self.theme_settle(self.theme_turn(), self.theme_out())
        self.assertTrue(got["open"], "持ち主に聞く問いが残るので承認が在っても開く")
        bare = self.theme_settle(self.theme_turn(), self.theme_out(design=self.design(asks=[])))
        self.assertFalse(bare["open"])
        self.assertEqual(bare["agreed"]["by"], "notes")

    # ---------------------------------------------- 降りる・止める
    def agreed(self, decision="approve", text="進めて", design=None) -> dict:
        po = self.theme_out(design=design)
        return {**po, **self.t.talk_fields({}), "done": True, "agreed": {"round": 1, "decision": decision, "text": text, "asked": []},
                "talks": [{"round": 1, "decision": decision, "text": text, "asked": []}]}

    def descend(self, got, given=None):
        with self.run.env():
            return self.d.descend(got, given=given or self.given, place=self.run.artifacts)

    def test_agreement_descends_with_the_changes_as_request_rows(self):
        got = self.descend(self.agreed())
        self.assertTrue(got["go"], got)
        request = json.loads(pathlib.Path(got["request_file"]).read_text(encoding="utf-8"))
        self.assertEqual(request["findings"], [{"where": "docs/rules.md", "text": "Split the rules into blocks.（設計の段 C1。部品 D1）"}])
        questions = [a["question"] for a in request["answers"]]
        self.assertEqual(questions[0], "q", "依頼が先に持っていた答えが先")
        self.assertIn("設計の段の問い Q1", questions)
        self.assertIn(self.d.APPROVED_Q, questions)
        self.assertTrue(pathlib.Path(got["approved"]).is_file())
        import carry
        self.assertEqual(carry.parts(request)["findings"], request["findings"], "降りた依頼は依頼の容器の形に合う")
        given = {**self.given, "request": None, "request_file": "", "entry": "", "request_origin": "", "request_scope": False}
        into = self.d.request_in(given, got)
        self.assertEqual((into["go"], into["request_file"], into["request_scope"]), (True, got["request_file"], True))
        self.assertIn("設計の段で承認された設計", into["entry"])

    def test_stop_and_no_changes_do_not_descend(self):
        got = self.descend(self.agreed("stop", "やめる"))
        self.assertEqual((got["go"], got["stop_reason"]), (False, "human:gate-theme"))
        bare = self.descend(self.agreed(design=self.design(changes=[], inventory=[], narrows=[])))
        self.assertEqual((bare["go"], bare["no_change"], bare["stop_reason"]), (False, True, ""))
        stopped = self.d.request_in(self.given, got)
        self.assertEqual((stopped["go"], stopped["stop_reason"]), (False, "human:gate-theme"))
        self.assertEqual(self.d.request_in(self.given, None)["stop_reason"], "works:line-script")

    def test_unattended_run_descends_only_without_items(self):
        given = {**self.given, "unattended": True}
        po = {**self.theme_out(), **self.t.talk_fields({})}
        got = self.descend(po, given)
        self.assertEqual((got["go"], got["stop_reason"]), (False, "works:needs-human"), "問いが残れば止まる（pick は通す推しでない）")
        bare = {**self.theme_out(design=self.design(asks=[])), **self.t.talk_fields({})}
        went = self.descend(bare, given)
        self.assertTrue(went["go"], went)
        kept = json.loads((self.run.artifacts / "gates/gate-theme.json").read_text(encoding="utf-8"))
        self.assertIn(self.answer.PUSHED, kept)
        request = json.loads(pathlib.Path(went["request_file"]).read_text(encoding="utf-8"))
        approved = next(a for a in request["answers"] if a["question"] == self.d.APPROVED_Q)
        self.assertIn(self.answer.PUSHED_NOTE, approved["text"], "持ち主の承認と書かない")

    def test_other_runs_take_the_request_from_the_dealt_values(self):
        given = {"theme": "", **{n: f"v-{n}" for n in REQUEST_FIELDS}}
        got = self.d.request_in(given, None)
        self.assertEqual({n: got[n] for n in REQUEST_FIELDS}, {n: f"v-{n}" for n in REQUEST_FIELDS})
        self.assertTrue(got["go"])

    # ---------------------------------------------- 設計へ戻す（計画の承認ノードの redesign）
    def test_redesign_closes_the_plan_rounds_only_in_a_theme_run(self):
        po = self.plan_out()
        prev = {**po, **self.t.talk_fields({}), "open": True, "text": "文", "asked": []}
        said = {"decision": "redesign", "text": "C1 が今のコードで成り立たない"}
        got = self.turn(said, previous=prev, theme=self.given["theme"])
        self.assertEqual((got["plan"], got["reason"]), (False, ""))
        done = self.settle(got, None, previous=prev)
        self.assertEqual((done["done"], done["agreed"]["decision"]), (True, "redesign"))
        elsewhere = self.turn(said, previous=prev)
        self.assertEqual(elsewhere["reason"], self.t.REDESIGN_ELSEWHERE, "テーマでない run は聞き直す")
        again = self.settle(elsewhere, None, previous=prev)
        self.assertEqual((again["open"], again["done"]), (True, False))
        g = kit.load(BLOCK, "gates")
        self.assertEqual(g.before_fix(done, unattended_run=False, design=True, agreed=done["agreed"])["stop_reason"], "human:gate-design")

    def test_plan_gate_shows_redesign_only_in_a_theme_run(self):
        po = self.plan_out()
        with self.run.env():
            plain = self.t.settle(turn_got=self.turn(), plan_out=po, previous=None, given={"design_talk": True, "unattended": False},
                                  materials=self.materials, run_id=kit.RUN_ID)
            themed = self.t.settle(turn_got=self.turn(), plan_out=po, previous=None,
                                   given={"design_talk": True, "unattended": False, "theme": "t.md"}, materials=self.materials,
                                   run_id=kit.RUN_ID)
        self.assertNotIn(" redesign ", plain["text"])
        self.assertIn(" redesign ", themed["text"])

    def test_the_ledger_reads_the_descended_answers(self):
        """問いの台帳の依頼の答えは、判定が問いを結んだ答えと同じ降りた依頼の答え（request-in の返り。src.descend.dealt）。始めの記録には
        設計の段の答えが無いので、記録から読むと結んだ問いを gate-design・最後の承認ノード・報告で聞き直す"""
        gm = __import__("gatemarks")
        rin = self.d.request_in(self.given, self.descend(self.agreed()))
        fork = {"key": "q-a", "kind": "fork", "status": "held", "origin": "u1", "options": ["x", "y"], "reason": "割れる"}
        (self.run.artifacts / "judgment.json").write_text(json.dumps({"units": [{"key": "u1", "label": "block"}], "questions": [fork]}),
                                                         encoding="utf-8")
        ties = {"rounds": {"1": [{"answer": "設計の段の問い Q1", "to": "q-a"}]}}
        (self.run.artifacts / "answer-ties.json").write_text(json.dumps(ties, ensure_ascii=False), encoding="utf-8")
        with self.run.env():
            asking = kit.load(BLOCK, "asking")
            judge = json.dumps({"judgment": json.loads(self.run.pointer("judgment.json")),
                                "answer_ties": json.loads(self.run.pointer("answer-ties.json")), "materials": None})
            for dealt, want in ((self.d.dealt(self.given, json.dumps(rin)), []), (self.given, ["q-a"])):
                with self.subTest(descended=dealt is not self.given):
                    kw = asking.materials(None, structure_raw=None, judge_raw=judge, record_raw="", dealt=dealt, unattended=False,
                                          place=self.run.artifacts)
                    self.assertEqual([q["key"] for q in gm.pending(kw["ledger"])], want)

    def test_back_writes_the_next_run_materials(self):
        descended = self.descend(self.agreed())
        po = self.plan_out()
        rounds_got = {**po, "agreed": {"decision": "redesign", "text": "C1 が成り立たない"}, "talks": [{"decision": "redesign", "text": "C1 が成り立たない"}]}
        record = {"inputs": {"test_cmd": "make test", "lang": "Japanese", "spec": "on", "deliver": ""}}
        with self.run.env():
            got = self.d.back(rounds_got, given=self.given, record=record, descended=descended, place=self.run.artifacts,
                              env={"WORKS_ANSWER_CMD": "env H=1 /f/bin/works-factory workflow respond --cwd /t"})
        self.assertTrue(got["back"])
        theme = (self.run.artifacts / "theme/next/theme.md").read_text(encoding="utf-8")
        for part in (tv.THEME_MD.strip().splitlines()[0], "# 設計の案", "C1 が成り立たない"):
            self.assertIn(part, theme)
        request = json.loads((self.run.artifacts / "theme/next/request.json").read_text(encoding="utf-8"))
        import carry
        self.assertEqual(carry.parts(request)["theme"], str(self.run.artifacts / "theme/next/theme.md"))
        self.assertEqual(got["command"], "env H=1 /f/bin/works-factory workflow run works-factory-line --cwd /t --input request="
                         f"{self.run.artifacts / 'theme/next/request.json'} --input design_talk=true --input test_cmd='make test' --input lang=Japanese --input spec=on")
        with self.run.env():
            self.assertFalse(self.d.back(po, given=self.given, record={}, descended=descended, place=self.run.artifacts)["back"])


# ---------------------------------------------------------------- YAML の配線
class ThemeWiringCase(unittest.TestCase):
    def setUp(self):
        self.doc = yaml.safe_load(LINE_YAML.read_text(encoding="utf-8"))
        self.nodes = {}
        for n in self.doc["nodes"]:
            self.nodes[n["id"]] = n
            for inner in (n.get("loop_group") or {}).get("nodes") or []:
                self.nodes[inner["id"]] = inner

    def ancestors(self, nid: str) -> set:
        top = {n["id"]: n for n in self.doc["nodes"]}
        seen, stack = set(), [nid]
        while stack:
            for dep in top[stack.pop()].get("depends_on") or []:
                if dep not in seen:
                    seen.add(dep)
                    stack.append(dep)
        return seen

    def test_nodes_after_request_in_read_the_request_only_from_it(self):
        """request-in を（直にか間を通して）待つ node は、配る値の依頼の欄を読まない（判定から後ろの依頼の出どころは 1 つ）"""
        read = re.compile(r"\$start\.output\.ports\.(" + "|".join(REQUEST_FIELDS) + r")(?!\w)")
        for node in self.doc["nodes"]:
            if "request-in" not in self.ancestors(node["id"]):
                continue
            with self.subTest(node["id"]):
                self.assertEqual(read.findall(yaml.safe_dump(node, allow_unicode=True, width=10_000)), [])

    def test_redesign_is_only_on_the_plan_gate(self):
        for nid, node in self.nodes.items():
            options = [o["id"] for o in (node.get("wait") or {}).get("options") or []]
            if options:
                with self.subTest(nid):
                    self.assertEqual("redesign" in options, nid == "gate-design")
        self.assertIn("revise", [o["id"] for o in self.nodes["gate-theme"]["wait"]["options"]])

    def test_theme_rounds_counts_like_plan_rounds(self):
        talk = kit.load(BLOCK, "talk")
        rounds = kit.load(BLOCK, "rounds")
        self.assertEqual(self.nodes["theme-rounds"]["loop_group"]["max_iterations"], rounds.LIMIT + talk.EMPTY_LIMIT)
        self.assertIn("theme-talk.output.done", self.nodes["theme-rounds"]["loop_group"]["until_bash"])


if __name__ == "__main__":
    unittest.main()
