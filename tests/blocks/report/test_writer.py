"""書き手のループと出口（workflows/report/src/writer.py）。受け付けの判断（書式と語で拒む・初見の読み手が 2 度拒んで 3 回目に印つきで採る・
機械の行だけへの指摘は書き直させない・書けない時は諦める）と、人に向けた報告に機械の頭が字を変えずに載ること・行の上限で切ること。
返答の型の YAML と lib の handoff.SCHEMA・受け付けの写しの一致も照らす（docs/concepts.json の bound）。語の言い換えと見出しの字の照らしは
2026-11-10 に落とした（docs/design/report.md の 8 節）"""
import json
import pathlib
import re
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
REDESIGN = json.dumps({"verdict": "redesign-needed", "stops": [{"line": "W1", "text": "冒頭の 2 行目"}], "guessed": [], "decidable": False},
                      ensure_ascii=False)
MACHINE_ONLY = json.dumps({"verdict": "redesign-needed", "stops": [{"line": "M1", "text": "起きたこと の行"}], "guessed": [], "decidable": False},
                          ensure_ascii=False)
MIXED = json.dumps({"verdict": "redesign-needed", "stops": [{"line": "W1", "text": "要約の1行目"}, {"line": "M1", "text": "起きたこと の行"}],
                    "guessed": [], "decidable": False}, ensure_ascii=False)
MARK = re.compile(r"\b[MW][0-9]+\b")
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


class ColdBodyCase(Base):
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

    def test_machine_lines_only_is_taken_without_a_rewrite(self):
        """すべての指摘の line が貼った機械の行の印なら、1 回目でも書き手に書き直させずに受け取り、通さなかった印を残す。印の書式の揺れ
        （'M1 | '）は印として読む。貼っていない印・印の取れない line・本文の印の指摘が 1 つでも在れば、1 回目で拒む"""
        got = self.accept(cold=MACHINE_ONLY)
        self.assertEqual((got["done"], got["ok"]), (True, True))
        self.assertIn(W.MACHINE_ONLY, got["reason"])
        self.assertIn("起きたこと の行", self.ai()["not_passed"])
        self.assertTrue(self.ai()["machine_only"])
        self.assertEqual(self.ai()["rejects"]["report"]["cold"], 0)
        for n, line in enumerate(("M1 | ", "M1:", "(M1)", " M1 ")):
            with self.subTest(line=line):
                out = self.out / f"wobble{n}"
                cold = json.dumps({"verdict": "redesign-needed", "stops": [{"line": line, "text": "起きたこと の行"}], "guessed": [],
                                   "decidable": False}, ensure_ascii=False)
                self.assertEqual((self.accept(cold=cold, out=out)["ok"], self.ai(out)["machine_only"]), (True, True))
                self.assertEqual(self.ai(out)["rejects"]["report"]["cold"], 0)
        for n, line in enumerate(("X9", "M99", "", "W1", "起きたこと", "M1, W1", "M1 and W1", "M1x")):
            with self.subTest(refused=line):
                out = self.out / f"refused{n}"
                cold = json.dumps({"verdict": "redesign-needed", "stops": [{"line": line, "text": "起きたこと の行"}], "guessed": [],
                                   "decidable": False}, ensure_ascii=False)
                got = self.accept(cold=cold, out=out)
                self.assertEqual((got["done"], got["ok"], got["kind"]), (False, False, "cold"))
        for n, shape in enumerate(({"verdict": "redesign-needed", "stops": [], "guessed": []},
                                   {"verdict": "redesign-needed", "stops": ["字のままの古い形の指摘"], "guessed": []},
                                   {"verdict": "redesign-needed", "stops": [{"line": "M1", "text": "頭"}], "guessed": [{"line": "W1", "text": "本文"}]})):
            with self.subTest(shape=shape):
                self.assertEqual(self.accept(cold=json.dumps(shape, ensure_ascii=False), out=self.out / f"shape{n}")["kind"], "cold")

    def test_writer_text_stop_with_machine_lines_still_rejects(self):
        """本文の指摘が 1 つでも在れば書き直させる。書き手への理由には本文の指摘の文だけが在り、頭の指摘の文も行の印も載らない。上限の回に受け取った
        時の知らせの行には、両方の指摘の文が（印でなく読み手の文で）載る"""
        got = self.accept(cold=MIXED)
        self.assertEqual((got["done"], got["kind"]), (False, "cold"))
        reason = (self.out / "rejects-report.md").read_text(encoding="utf-8")
        self.assertIn("止まった所: 要約の1行目", reason)
        self.assertNotIn("起きたこと の行", reason)
        self.assertNotRegex(reason, MARK)
        self.accept(cold=MIXED)
        self.assertTrue(self.accept(cold=MIXED)["ok"])
        self.assertFalse(self.ai()["machine_only"])
        reason = (self.out / "rejects-report.md").read_text(encoding="utf-8")
        self.assertNotRegex(reason, MARK)
        self.assertNotIn("起きたこと の行", reason)
        line = W.collect("# 報告\n\n起きたこと: 赤\n", place=self.out, stamp="run x").read_text(encoding="utf-8").splitlines()[3]
        self.assertIn("要約の1行目", line)
        self.assertIn("起きたこと の行", line)
        self.assertNotRegex(line, MARK)

    def test_unreadable_verdict_is_not_machine_only(self):
        self.assertEqual((self.accept(cold="壊れた")["done"]), False)

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
        top = "# 報告（run x）\n\n起きたこと: 直した\n差分を当ててよいか: 当ててよい。当てる命令: bin/apply x\n急ぎ: 壊れた所がある\n人が決めること: 1 件\n- 題 A（k）"
        machine = f"{top}\n\n## 1. 人が決めること\n\n- 承認ノード: 開かなかった\n"
        path = W.collect(machine, place=self.out, stamp="works-factory report / run x")
        self.assertEqual(path, self.out / "report-ai.md")
        human = self.human()
        self.assertTrue(human.startswith(f"{top}\n\n直した。\n\n## 1. 人が決めること"), "機械の頭の行（差分・急ぎ・件数）はそのまま人に向けた報告の頭: " + human)
        self.assertIn("- 寄せ: 合わせること", human.split(W.GLOSSARY_HEADING)[1])
        self.assertTrue(human.endswith(W.POINTER_LINE.format(file="report-detail.md") + "\nworks-factory report / run x\n"))
        self.assertNotIn("長い経緯", human)
        self.assertNotIn(W.MACHINE_HEADING, human)
        detail = self.detail()
        self.assertIn(f"{W.RAW_HEADING}\n\n{json.loads(reply)['text']}\n", detail)
        self.assertIn(W.MACHINE_HEADING, detail)
        self.assertIn(f"{W.COLD_REJECTS_LINE} 0 回", detail)
        self.assertTrue(detail.endswith("- 承認ノード: 開かなかった\n"), "機械の事実の行は書き換えずに最後に付ける")

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

    def test_given_up_reply_still_reports(self):
        for _ in range(rolekit.GIVE_UP_AFTER):
            self.accept("壊れた")
        human = W.collect("# 報告\n\n起きたこと: 赤\n\n## 1. 人が決めること\n\n事実", place=self.out, stamp="run x").read_text(encoding="utf-8")
        self.assertTrue(human.startswith("# 報告\n\n起きたこと: 赤\n\n"), human)
        self.assertIn(W.FAILED_TITLE, human)
        self.assertIn(f"report の返答が {rolekit.GIVE_UP_AFTER} 回とも受け付けで拒まれた（最後の拒否: ", human)
        self.assertTrue(self.detail().endswith("事実"))


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


if __name__ == "__main__":
    unittest.main()
