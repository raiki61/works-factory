"""書き手のループと出口（workflows/report/src/writer.py）。写す元は lib/tests/test_runreport.py の GlossaryCase・AcceptCase・ReportGiveUpCase・
CollectCase・ColdBodyCase、lib/tests/test_report_roles.py の全部、lib/tests/test_handoff.py のうち型と控えの書き読みの物（文の定数の字の試験は
写さない。文は md が持つ）。返答の型の YAML と handoff.SCHEMA の一致も照らす。"""
import json
import pathlib
import unittest

import yaml

from tests.blocks import kit
from tests.blocks.report import base

M = base.src()
import handoff  # noqa: E402  lib/
import rolekit  # noqa: E402  lib/

W = M.writer
REPLY = json.dumps({"text": "直した。\n\n## 1. 人が決めること\n\n無い", "terms": []}, ensure_ascii=False)
PASS = json.dumps(base.GOOD_COLD)
REDESIGN = json.dumps({"verdict": "redesign-needed", "stops": ["冒頭の 2 行目"], "guessed": [], "decidable": False}, ensure_ascii=False)
NODE = "report"


class Base(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "report")
        self.out = self.run.artifacts / "place"

    def accept(self, reply=REPLY, cold=PASS, out=None):
        return W.accept(reply, cold, place=out or self.out)

    def ai(self, out=None) -> dict:
        return base.read((out or self.out) / "ai.json")

    def kept_answer(self, out=None) -> dict:
        return base.read(rolekit.candidate_path(out or self.out, NODE))

    def kept_note(self, n: int, out=None) -> dict:
        return base.read(handoff.path_of((out or self.out) / f"r{n}"))

    @staticmethod
    def with_handoff(text: str, tag: str) -> str:
        return json.dumps({"text": text, "terms": [], "handoff": {
            "read": [{"path": f"{tag}.py", "lines": "1", "why": f"{tag}を読んだ"}], "kept": [f"{tag}の訳"],
            "set_aside": [{"option": f"{tag}の脇に置いた案", "why": f"{tag}の置いた訳"}], "open": [f"{tag}の迷い"]}}, ensure_ascii=False)


class FormatCase(unittest.TestCase):
    def test_short_cells_pass(self):
        text = "結果\n\n| 項目 | 件数 |\n|---|---|\n| 直した | 3 |\n| `src/very/long/path/to/some/module_name.py` | 済み |\n"
        self.assertEqual(W.format_problems(text), [])

    def test_sentence_in_cell_rejected(self):
        got = W.format_problems("| 項目 | 説明 |\n|---|---|\n| A | これは説明の文である。 |\n")
        self.assertEqual(len(got), 1)
        self.assertIn("3 行目", got[0])

    def test_long_cell_rejected(self):
        self.assertEqual(len(W.format_problems("| 項目 |\n|---|\n| " + "あ" * (W.CELL_LIMIT + 1) + " |\n")), 1)

    def test_pipes_in_code_are_not_cells(self):
        self.assertEqual(W.format_problems("```\n| " + "あ" * 80 + "。 |\n```\n"), [])
        self.assertEqual(W.format_problems("| 項目 |\n|---|\n| `" + "。" * 80 + "` |\n"), [])


class HeadCase(unittest.TestCase):
    def test_head_keeps_lead_and_decisions_only(self):
        head = W.head_of("1 行目\n2 行目\n3 行目\n\n## 1. 人が決めること\n\n- 問い A\n\n## 2. 経緯\n\n長い経緯")
        self.assertIn("3 行目", head)
        self.assertIn("問い A", head)
        self.assertNotIn("長い経緯", head)
        self.assertEqual(W.head_of(" 本文だけ \n"), "本文だけ")

    def test_terms_must_be_term_and_definition(self):
        self.assertEqual(W.terms_problems({"text": "x"}), [])
        self.assertEqual(W.terms_problems({"text": "x", "terms": [{"term": "盤面", "definition": "置き場"}]}), [])
        self.assertNotEqual(W.terms_problems({"text": "x", "terms": [{"term": ""}]}), [])
        self.assertNotEqual(W.terms_problems({"text": "x", "terms": [{"term": "a", "definition": "b", "extra": 1}]}), [])

    def test_rows_without_kind_count_as_unknown(self):
        rows = [{"node": "report", "reason": "kind が入る前の行"}, {"node": "report", "kind": "cold"}, {"node": "report", "kind": "answer"},
                {"node": "report", "kind": "format"}, {"node": "report", "kind": "何か"}, {"node": "よその節", "kind": "cold"},
                {"node": "report.human_items", "kind": "cold"}]
        self.assertEqual(W.count_rejects(rows), {"report": {"cold": 1, "format": 1, "answer": 1, "unknown": 2}})

    def test_heading_that_asks_for_decisions_is_the_one_the_prompt_names(self):
        """指示が書き手に言う見出しの字と、頭を探す字は同じ値（md と受け付けが同じ字を持つ）"""
        self.assertEqual(W.DECISIONS_HEAD, "人が決めること")
        self.assertIn(W.DECISIONS_HEAD, M.files.DECISIONS_HEADING)


class GlossaryCase(unittest.TestCase):
    def test_only_terms_in_text(self):
        sec = W.glossary_section("寄せて止めた", [{"term": "寄せ", "definition": "合わせること"}, {"term": "周", "definition": "一巡"}])
        self.assertIn("- 寄せ: 合わせること", sec)
        self.assertNotIn("一巡", sec)
        self.assertEqual(W.glossary_section("何も無い", []), "")

    def test_pack_terms_come_from_the_block(self):
        pack = W.pack_terms()
        self.assertTrue(any(t["term"] == "承認ノード" for t in pack))
        self.assertTrue(all(set(t) == {"term", "plain"} for t in pack))
        for t in pack:
            with self.subTest(t["term"]):
                self.assertEqual([u["term"] for u in pack if u["term"] in t["plain"]], [])
        self.assertEqual((W.PACK_TERMS.parent.name, W.PACK_TERMS.name), ("src", "glossary.json"))

    def test_plain_words_swap_outside_code(self):
        pack = [{"term": "単位", "plain": "項目"}, {"term": "根本の単位", "plain": "直す項目"}]
        text, counts = W.plain_words("根本の単位と単位。`単位` は鍵\n```\n単位\n```\n単位", pack)
        self.assertEqual(text, "直す項目と項目。`単位` は鍵\n```\n単位\n```\n項目")
        self.assertEqual(counts, {"根本の単位": 1, "単位": 2})

    def test_plain_words_skip_katakana_words_that_only_contain_a_term(self):
        pack = [{"term": "ライン", "plain": "処理の段の組み合わせ"}, {"term": "ノード", "plain": "処理の段"}]
        text, counts = W.plain_words("パイプラインとライン。サブノードとノード", pack)
        self.assertEqual(text, "パイプラインと処理の段の組み合わせ。サブノードと処理の段")
        self.assertEqual(counts, {"ライン": 1, "ノード": 1})

    def test_plain_words_skip_compounds_that_only_contain_a_one_kanji_term(self):
        text, counts = W.plain_words("前の周に戻り、周ごとに柵の印を見た。周囲と周知、一周、周辺")
        self.assertEqual(counts, {"周": 2, "柵": 1})
        self.assertTrue(text.endswith("周囲と周知、一周、周辺"), text)
        self.assertEqual(W.plain_words("周りを見た。3 周目")[0], "周りを見た。3 周目")

    def test_plain_words_keep_any_question_key_on_a_ledger_line(self):
        for key in ("parallel_pr: 単位の柵", "柵（住処）", "柵（住処・素材）"):
            with self.subTest(key=key):
                line = f"{W.ASK_HEAD} {key}（fork・held・柵が要る）"
                text = W.plain_words(line)[0]
                self.assertIn(f" {key}（fork・held", text)
                self.assertNotIn("柵が要る", text)

    def test_every_pack_term_is_swapped(self):
        text = W.plain_words("守りのパスに当たった差分。無人の run が推しで通した承認ノード。周 2 のノード")[0]
        self.assertEqual([t["term"] for t in W.pack_terms() if t["term"] in text], [])


class ColdBodyCase(Base):
    def test_head_and_glossary_only(self):
        self.out.mkdir(parents=True)
        (self.out / "report.md").write_text("# 報告\n\n起きたこと: 赤\n\n## 1. 人が決めること\n\n- 機械の行\n", encoding="utf-8")
        reply = json.dumps({"text": "承認ノードで止めた。\n\n## 1. 人が決めること\n\n- A\n\n## 2. 経緯\n\n長い",
                            "terms": [{"term": "A", "definition": "決める物"}]}, ensure_ascii=False)
        body = W.cold_body(reply, place=self.out)
        self.assertTrue(body.startswith("# 報告\n\n起きたこと: 赤\n\n先へ進めるかを決める所で止めた。"), body)
        self.assertNotIn("長い", body)
        self.assertNotIn("機械の行", body)
        self.assertIn(W.GLOSSARY_HEADING, body)

    def test_unreadable_reply_says_so(self):
        self.assertIn("書き手の返答を読めない", W.cold_body("壊れた", place=self.out))
        self.assertIn("機械の報告の冒頭を読めない", W.cold_body(json.dumps({"text": "本文"}, ensure_ascii=False), place=self.out))

    def test_handoff_never_reaches_the_cold_reader(self):
        self.out.mkdir(parents=True)
        (self.out / "report.md").write_text("# 報告\n", encoding="utf-8")
        self.assertNotIn("a.py", W.cold_body(self.with_handoff("本文", "a"), place=self.out))


class AcceptCase(Base):
    def test_pass_is_taken(self):
        self.assertEqual(self.accept(), {"done": True, "ok": True, "reason": "", "kind": "", "prev_file": ""})
        self.assertTrue(self.ai()["accepted"])
        self.assertEqual(self.ai()["not_passed"], "")

    def test_cold_rejects_twice_then_takes_with_mark(self):
        first = self.accept(cold=REDESIGN)
        self.assertEqual((first["done"], first["kind"]), (False, "cold"))
        self.assertIn("冒頭の 2 行目", (self.out / "rejects-report.md").read_text(encoding="utf-8"))
        self.assertFalse(self.accept(cold=REDESIGN)["done"])
        third = self.accept(cold=REDESIGN)
        self.assertTrue(third["done"] and third["ok"])
        self.assertIn(W.NOT_PASSED, third["reason"])
        self.assertTrue(self.ai()["not_passed"])
        self.assertEqual(self.ai()["rejects"]["report"]["cold"], 2)

    def test_format_and_terms_rejected_first(self):
        bad_cell = json.dumps({"text": "| 項目 |\n|---|\n| 説明の文である。 |"}, ensure_ascii=False)
        got = self.accept(bad_cell)
        self.assertEqual((got["kind"], got["done"]), ("format", False))
        self.assertEqual(self.accept(json.dumps({"text": "x", "terms": [{"term": ""}]}))["kind"], "answer")
        third = self.accept("壊れた")
        self.assertTrue(third["done"])
        self.assertFalse(third["ok"])
        self.assertFalse(self.ai()["accepted"], "3 回とも拒めば受け取れなかった訳を残す")

    def test_rejected_reply_is_kept_for_the_next_round(self):
        """拒んだ回の本文 text・terms は前の答えの控え candidate-report.json に残り、prev_file が絶対パスで指す。handoff はその周のフォルダ r<n>/ に
        置かれ、初見の読み手に貼る本文に入らない。handoff の無い回は本文だけ新しくなり、その周のフォルダは作らない。受け取った回の prev_file は空"""
        terms = [{"term": "語", "definition": "定義"}]
        first = json.dumps({**json.loads(self.with_handoff("一回目の本文。\n\n## 1. 人が決めること\n\n無い", "a")), "terms": terms}, ensure_ascii=False)
        got = self.accept(first, REDESIGN)
        self.assertEqual((got["done"], got["ok"]), (False, False))
        candidate = rolekit.candidate_path(self.out, NODE)
        self.assertEqual(got["prev_file"], str(candidate))
        self.assertTrue(pathlib.Path(got["prev_file"]).is_absolute())
        self.assertEqual(self.kept_answer(), {"text": json.loads(first)["text"], "terms": terms})
        self.assertEqual(self.kept_note(1), json.loads(first)["handoff"])
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["candidate-report.json", "r1", "rejects-report.json", "rejects-report.md"])
        self.assertEqual(self.accept(cold=REDESIGN)["prev_file"], got["prev_file"])
        self.assertEqual(self.kept_answer(), {"text": json.loads(REPLY)["text"], "terms": []})
        self.assertFalse((self.out / "r2").exists(), "メモの無い回は周のフォルダを作らない")
        self.assertEqual(self.kept_note(1), json.loads(first)["handoff"], "前の周のメモは変わらない")
        taken = self.accept()
        self.assertEqual((taken["ok"], taken["prev_file"]), (True, ""))
        for path in self.out.rglob("*.json"):
            self.assertNotIn("handoffs", path.read_text(encoding="utf-8"), path.name)

    def test_blank_text_keeps_the_previous_answer_and_notes(self):
        first = self.with_handoff("一回目の本文", "a")
        self.accept(first, REDESIGN)
        before = self.kept_answer()
        for text in ("  \n", 3, None):
            with self.subTest(text=text):
                reply = json.dumps({"text": text, "terms": [], "handoff": json.loads(self.with_handoff("x", "z"))["handoff"]})
                got = self.accept(reply)
                self.assertEqual((got["ok"], got["kind"]), (False, "answer"))
                self.assertEqual(self.kept_answer(), before)
                self.assertEqual(self.kept_note(1), json.loads(first)["handoff"])
                self.assertFalse((self.out / "r2").exists())

    def test_unreadable_previous_note_stops_without_overwrite(self):
        for n, broken in enumerate(("{壊れた", "null", "[]")):
            with self.subTest(broken=broken):
                out = self.out / f"broken-{n}"
                prev = handoff.path_of(out / "r1")
                prev.parent.mkdir(parents=True)
                prev.write_text(broken, encoding="utf-8")
                rolekit.rejects_path(out, NODE).write_text(json.dumps([{"at": "x", "reason": "前", "kind": "cold"}]), encoding="utf-8")
                got = self.accept(self.with_handoff("本文", "a"), REDESIGN, out)
                self.assertEqual(prev.read_text(encoding="utf-8"), broken, "上書きしない")
                self.assertFalse((out / "r2").exists())
                self.assertFalse(rolekit.candidate_path(out, NODE).exists())
                self.assertEqual((got["done"], got["ok"], got["prev_file"]), (True, False, ""))
                rows = base.read(rolekit.rejects_path(out, NODE))
                self.assertIs(rows[-1]["give_up"], True)
                self.assertIn(str(prev), rows[-1]["reason"])
                ai = self.ai(out)
                self.assertIs(ai["accepted"], False)
                self.assertEqual(ai["reason"], rolekit.gave_up_text(NODE, 2, rows[-1]["reason"], at_once=True))

    def test_unwritable_candidate_gives_up_at_once(self):
        self.out.mkdir(parents=True)
        rolekit.candidate_path(self.out, NODE).mkdir()
        got = self.accept(self.with_handoff("本文", "a"), REDESIGN)
        self.assertEqual((got["done"], got["ok"], got["prev_file"]), (True, False, ""))
        rows = base.read(rolekit.rejects_path(self.out, NODE))
        self.assertEqual(len(rows), 1)
        self.assertIs(rows[-1]["give_up"], True)
        self.assertIn("前の答えの控え", rows[-1]["reason"])
        self.assertIn("前の答えの控え", self.ai()["reason"])
        blocked = self.out / "note-blocked"
        folder = blocked / "r1"
        folder.mkdir(parents=True)
        handoff.path_of(folder).with_name("handoff.json.tmp").mkdir()
        got = self.accept(self.with_handoff("本文", "a"), REDESIGN, blocked)
        self.assertEqual((got["done"], got["ok"]), (True, False))
        rows = base.read(rolekit.rejects_path(blocked, NODE))
        self.assertIn(f"前の周の引き継ぎのメモ {handoff.path_of(folder)} に書けない", rows[-1]["reason"])

    def test_unusable_ledger_still_leaves_the_unaccepted_reason(self):
        self.out.mkdir(parents=True)
        (self.out / "rejects-report.json").mkdir()
        for raw, cold in ((REPLY, REDESIGN), ("壊れた", PASS)):
            with self.subTest(raw=raw[:3]):
                (self.out / "ai.json").unlink(missing_ok=True)
                got = self.accept(raw, cold)
                self.assertEqual((got["done"], got["ok"]), (True, False))
                self.assertIn("拒否の控えが扱えない", got["reason"])
                ai = self.ai()
                self.assertFalse(ai["accepted"])
                self.assertEqual(ai["rejects"], W.count_rejects([]))
                path = W.collect("事実", place=self.out, stamp="run x")
                self.assertIn("拒否の控えが扱えない", path.read_text(encoding="utf-8"))
        (self.out / "ai.json").unlink()
        self.assertEqual(self.accept()["ok"], True)

    def test_give_up_text_is_rolekit_text(self):
        for _ in range(rolekit.GIVE_UP_AFTER):
            self.accept(json.dumps({"text": "x", "terms": [{"term": ""}]}))
        rows = rolekit.reject_rows(self.out, NODE)
        self.assertEqual([r["kind"] for r in rows], ["answer"] * 3)
        self.assertEqual(self.ai()["reason"], rolekit.gave_up_text(NODE, len(rows), rows[-1]["reason"]))

    def test_rejects_live_in_the_rolekit_ledger_with_kind(self):
        bad_cell = json.dumps({"text": "| 項目 |\n|---|\n| 説明の文である。 |"}, ensure_ascii=False)
        first = self.accept(bad_cell)
        second = self.accept(json.dumps({"text": "x", "terms": [{"term": ""}]}))
        self.assertEqual([(first["kind"], first["done"]), (second["kind"], second["done"])], [("format", False), ("answer", False)])
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["candidate-report.json", "rejects-report.json", "rejects-report.md"])
        text = (self.out / "rejects-report.md").read_text(encoding="utf-8")
        self.assertLess(text.index(first["reason"]), text.index(second["reason"]), "それまでの拒否を古い順に全部持つ")
        for n, raw in enumerate(("壊れた", "", json.dumps({"terms": []})), 1):
            with self.subTest(raw=raw):
                out = self.out / f"unreadable-{n}"
                got = self.accept(raw, out=out)
                self.assertEqual(set(got), {"done", "ok", "reason", "kind", "prev_file"})
                self.assertEqual((got["ok"], got["kind"], got["prev_file"]), (False, "answer", ""))
                self.assertEqual([r["kind"] for r in rolekit.reject_rows(out, NODE)], ["answer"])

    def test_handoff_rounds_name_every_prior_round_oldest_first(self):
        self.out.mkdir(parents=True)
        self.assertEqual(W.handoff_rounds(self.out), "", "前の周が無ければ空")
        first, second = self.with_handoff("一回目の本文", "a"), self.with_handoff("二回目の本文", "b")
        self.accept(first, REDESIGN)
        self.accept(second, REDESIGN)
        self.assertEqual(self.kept_answer()["text"], "二回目の本文")
        self.assertEqual(self.kept_note(2), json.loads(second)["handoff"])
        self.assertEqual(W.handoff_rounds(self.out), f"- r1: {handoff.path_of(self.out / 'r1')}\n- r2: {handoff.path_of(self.out / 'r2')}")
        (self.out / "r1" / "handoff.json").write_text("{壊れた", encoding="utf-8")
        (self.out / "r2" / "handoff.json").unlink()
        self.assertEqual(W.handoff_rounds(self.out), "- r1: (unreadable)\n- r2: (no notes)")
        rolekit.rejects_path(self.out, NODE).write_text("{壊れた", encoding="utf-8")
        self.assertEqual(W.handoff_rounds(self.out), "", "控えが読めない時は前の周を名指さない")


class CollectCase(Base):
    def human(self) -> str:
        return (self.out / "report-ai.md").read_text(encoding="utf-8")

    def detail(self) -> str:
        return (self.out / "report-detail.md").read_text(encoding="utf-8")

    def test_no_ai_file_is_none(self):
        self.assertIsNone(W.collect("機械の事実", place=self.out, stamp="run x"))
        self.assertFalse((self.out / "report-detail.md").exists())

    def test_taken_reply_becomes_ai_report(self):
        reply = json.dumps({"text": "直した。\n\n## 1. 人が決めること\n\n- 寄せるか\n\n## 2. 経緯\n\n長い経緯",
                            "terms": [{"term": "寄せ", "definition": "合わせること"}]}, ensure_ascii=False)
        self.accept(reply)
        machine = "# 報告（run x）\n\n起きたこと: 直した\n\n## 1. 人が決めること\n\n- 承認ノード: 開かなかった\n"
        path = W.collect(machine, place=self.out, stamp="works-factory report / run x")
        self.assertEqual(path, self.out / "report-ai.md")
        human = self.human()
        self.assertTrue(human.startswith("# 報告（run x）\n\n起きたこと: 直した\n\n直した。\n\n## 1. 人が決めること"), human)
        self.assertIn("- 寄せ: 合わせること", human.split(W.GLOSSARY_HEADING)[1])
        self.assertTrue(human.endswith(W.POINTER_LINE.format(file="report-detail.md") + "\nworks-factory report / run x\n"))
        self.assertNotIn("長い経緯", human)
        self.assertNotIn(W.MACHINE_HEADING, human)
        detail = self.detail()
        self.assertIn(f"{W.RAW_HEADING}\n\n{json.loads(reply)['text']}\n", detail)
        self.assertIn(W.MACHINE_HEADING, detail)
        self.assertIn(f"{W.COLD_REJECTS_LINE} 0 回", detail)
        self.assertTrue(detail.endswith("- 承認ノード: 開かなかった\n"), "機械の事実の行は書き換えずに最後に付ける")

    def test_head_phrases_of_the_machine_reach_the_human_report(self):
        self.accept()
        for note in ("試験は走っていない", "AI が書いた試験のコードを利用者の資格に届く環境で走らせた"):
            with self.subTest(note=note):
                machine = f"# 報告\n\n起きたこと: 赤。{note}\n\n## 1. 人が決めること\n\n- 無い\n"
                head = W.collect(machine, place=self.out, stamp="run x").read_text(encoding="utf-8").splitlines()[2]
                self.assertIn(W.plain_words(note)[0], head)

    def test_inner_words_are_swapped_only_in_the_human_report(self):
        self.accept(json.dumps({"text": "レンズが根本の単位を見た。`fix__lens` は名", "terms": []}, ensure_ascii=False))
        human = W.collect("# 報告\n\n起きたこと: 承認ノードで止めた\n", place=self.out, stamp="run x").read_text(encoding="utf-8")
        for t in W.pack_terms():
            self.assertNotIn(t["term"], human.replace("`fix__lens`", ""))
        self.assertIn("観点ごとの見直しが直す項目を見た。`fix__lens` は名", human)
        self.assertIn("レンズが根本の単位を見た。", self.detail())
        self.assertIn(f"- {W.SWAPPED_HEAD}: 承認ノード→先へ進めるかを決める所 1 回・レンズ→観点ごとの見直し 1 回・根本の単位→直す項目 1 回", self.detail())

    def test_human_report_is_cut_to_the_line_budget(self):
        long = "\n".join(["要約。", "", "## 1. 人が決めること", "", "```", *[f"行 {i}" for i in range(200)], "```"])
        self.accept(json.dumps({"text": long, "terms": []}, ensure_ascii=False))
        machine = "# 報告\n\n起きたこと: 赤\n差分を当ててよいか: 無い\n人が決めること: 2 件\n- a: x\n- b: y\n"
        human = W.collect(machine, place=self.out, stamp="run x").read_text(encoding="utf-8")
        self.assertLessEqual(len(human.splitlines()), W.line_budget(2), human)
        [cut] = [x for x in human.splitlines() if "report-detail.md" in x and "行は" in x]
        self.assertRegex(cut, r"ここから先 \d+ 行は")
        self.assertEqual(sum(1 for x in human.split(cut)[0].splitlines() if x.startswith("```")) % 2, 0, "コードの囲みを閉じる")
        self.assertIn("行 199", self.detail())

    def test_cut_right_after_an_opening_fence_opens_no_new_fence(self):
        cut = W._cut("a\nb\nc\n```\nx\ny\n```\nz", 5)
        self.assertEqual(cut.splitlines()[:3], ["a", "b", "c"])
        self.assertEqual(W._fences(cut.splitlines()), [])

    def test_definitions_are_kept_and_follow_the_shown_head(self):
        text = "\n".join(["寄せて直した。", "", "## 1. 人が決めること", "", *[f"- 行 {i}" for i in range(200)], "- 畳みの話"])
        terms = [{"term": "寄せ", "definition": "合わせること"}, {"term": "畳み", "definition": "後ろへ送ること"}]
        self.accept(json.dumps({"text": text, "terms": terms}, ensure_ascii=False))
        human = W.collect("# 報告\n\n起きたこと: 赤\n", place=self.out, stamp="run x").read_text(encoding="utf-8")
        self.assertLessEqual(len(human.splitlines()), W.line_budget(0), human)
        self.assertNotIn("畳みの話", human)
        defined = human.split(W.GLOSSARY_HEADING)[1]
        self.assertIn("- 寄せ: 合わせること", defined)
        self.assertNotIn("畳み", defined)

    def test_not_passed_is_said_at_the_head(self):
        for _ in range(rolekit.GIVE_UP_AFTER):
            self.accept(cold=REDESIGN)
        human = W.collect("# 報告\n\n起きたこと: 赤\n", place=self.out, stamp="run x").read_text(encoding="utf-8")
        said = W.plain_words(W.NOT_PASSED)[0]
        self.assertEqual(human.splitlines()[3].split("（")[0], said, human)
        self.assertIn("止まった所: 冒頭の 2 行目", human.splitlines()[3])
        self.assertEqual(human.count(said), 1)
        self.assertNotIn("出し直せ", human)
        [line] = [ln for ln in self.detail().splitlines() if W.NOT_PASSED in ln]
        self.assertTrue(line.startswith(f"{W.COLD_REJECTS_LINE} 2 回。{W.NOT_PASSED}"), line)

    def test_not_passed_line_keeps_guesses_and_unreadable_verdict(self):
        guessed = json.dumps({"verdict": "redesign-needed", "stops": [], "guessed": ["語 X を推測"]}, ensure_ascii=False)
        for cold, want in ((guessed, "推測で埋めた所: 語 X を推測"), ("壊れた", W.COLD_UNREADABLE)):
            with self.subTest(want=want):
                out = self.out / want
                for _ in range(rolekit.GIVE_UP_AFTER):
                    self.accept(cold=cold, out=out)
                W.collect("事実", place=out, stamp="run x")
                [line] = [ln for ln in (out / "report-detail.md").read_text(encoding="utf-8").splitlines() if W.NOT_PASSED in ln]
                self.assertIn(want, line)
                self.assertNotIn("初見の読み手", (out / "report-ai.md").read_text(encoding="utf-8"))

    def test_given_up_reply_still_reports(self):
        for _ in range(rolekit.GIVE_UP_AFTER):
            self.accept("壊れた")
        human = W.collect("# 報告\n\n起きたこと: 赤\n\n## 1. 人が決めること\n\n事実", place=self.out, stamp="run x").read_text(encoding="utf-8")
        self.assertTrue(human.startswith("# 報告\n\n起きたこと: 赤\n\n"), human)
        self.assertIn(W.FAILED_TITLE, human)
        self.assertIn(f"report の返答が {rolekit.GIVE_UP_AFTER} 回とも受け付けで拒まれた（最後の拒否: ", human)
        self.assertTrue(self.detail().endswith("事実"))

    def test_decisions_section_is_one_place(self):
        self.accept()
        machine = "# 報告\n\n起きたこと: 赤\n\n## 1. 人が決めること\n\n- a\n\n## 2. 止めたか\n\n- b\n"
        human = W.collect(machine, place=self.out, stamp="run x").read_text(encoding="utf-8")
        for text in (human, self.detail()):
            heads = [line for line in text.splitlines() if line.startswith("#") and W.DECISIONS_HEAD in line]
            self.assertEqual(heads, ["## 1. 人が決めること"])
        self.assertIn(f"#{W.MACHINE_DECISIONS}", self.detail())
        self.assertIn("### 2. 止めたか", self.detail())
        self.assertNotIn("2. 止めたか", human)


class HandoffShapeCase(unittest.TestCase):
    """返答の型の YAML（write の output_format の handoff）と lib/handoff.py の SCHEMA の一致。terms と cold の型も YAML と受け付けの写しを揃える"""

    @classmethod
    def setUpClass(cls):
        doc = yaml.safe_load((base.BLOCK / "works-factory-report.yaml").read_text(encoding="utf-8"))
        nodes = {n["id"]: n for n in doc["nodes"]}
        cls.body = {n["id"]: n for n in nodes["write-loop"]["loop_group"]["nodes"]}

    def test_write_reply_shape_is_the_one_schema(self):
        shape = self.body["write"]["output_format"]
        self.assertEqual(shape["properties"]["handoff"], handoff.SCHEMA)
        self.assertEqual(shape["properties"]["terms"], W.TEXT_SCHEMA["properties"]["terms"])
        self.assertEqual((shape["required"], shape["additionalProperties"]), (["text", "handoff"], False))
        self.assertEqual(W.TEXT_SCHEMA["properties"]["handoff"], handoff.SCHEMA)
        self.assertEqual(handoff.KEYS, ("read", "kept", "set_aside", "open"))

    def test_cold_reply_shape_is_the_acceptance_copy(self):
        self.assertEqual(self.body["cold"]["output_format"], W.COLD_SCHEMA)

    def test_note_is_saved_read_and_unreadable_is_named(self):
        run = kit.Run(self, "report")
        folder = run.artifacts / "r1"
        handoff.save(folder, base.NOTE)
        self.assertEqual(base.read(handoff.path_of(folder)), base.NOTE)
        handoff.save(folder, None)
        self.assertFalse(handoff.path_of(folder).exists())
        folder.mkdir(exist_ok=True)
        handoff.path_of(folder).write_text("{壊れた", encoding="utf-8")
        self.assertEqual(handoff.unreadable([folder]), [handoff.path_of(folder)])


if __name__ == "__main__":
    unittest.main()
