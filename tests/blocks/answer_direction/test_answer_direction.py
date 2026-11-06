"""一言の向きの判定の block を、script を子のプロセスで回して確かめる（docs/design/answer-direction.md の 6 節）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、direction_prep → 台本の返答（direction_save）
→ finish と回す。向きの語（aligned・redirected・unclear）と aligned の真偽の決めは block の中だけが持つので、ここで縛る。
YAML と筋書きの揃いは tests/layers/test_block_shape.py が見る。
"""
import json
import unittest

import yaml

from tests.blocks import kit

BLOCK = "answer-direction"
NOTE = "計画と違い、空の列は例外を投げる形にしてほしい"
ASKED = ["修正案 1 が狭める能力: 空の列で例外を投げる——0 を返す形に変える"]
PLAN = {"plan": [{"unit_keys": ["u1"], "approach": "空の列の mean が 0 を返す形に変える",
                  "files": [{"path": "stats.py", "op": "modify", "responsibility": "平均を出す"},
                            {"path": "tests/test_stats.py", "op": "modify", "responsibility": "平均の試験"}]},
                 {"unit_keys": ["u2"], "approach": "呼び手の docs を新しい戻り値に合わせる",
                  "files": [{"path": "docs/stats.md", "op": "modify", "responsibility": "文書"}]}]}
GO = {"decision": "continue", "text": NOTE}
REDIRECTED = {"direction": "redirected", "why": "計画は 0 を返すが、一言は例外を投げる向きを選んでいる"}
UNCLEAR = {"direction": "unclear", "why": "一言がどちらの向きかを言っていない"}
ALIGNED = {"direction": "aligned", "why": "一言は計画の 0 を返す向きを足しているだけ"}


def dump(doc) -> str:
    return json.dumps(doc, ensure_ascii=False)


class AnswerDirectionCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, BLOCK)

    def fix_plan_pointer(self, doc=PLAN) -> str:
        """承認に掛けた計画の修正案（fix-plan.schema.json の形）を置き場に置き、pointer を返す"""
        kit.shaped("shared:fix-plan.schema.json", doc)
        path = self.run.artifacts / "plan" / "fix-plan.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump(doc), encoding="utf-8")
        return self.run.pointer("plan/fix-plan.json")

    def prep(self, answer=GO, *, asked=ASKED, given=None, lang="") -> dict:
        return self.run.script("direction_prep", answer=answer if isinstance(answer, str) else dump(answer),
                               asked=asked if isinstance(asked, str) else dump(asked), plan=self.fix_plan_pointer() if given is None else given, lang=lang)

    def finish(self, prep, reply=None, raw: str | None = None) -> dict:
        """受け皿 direction-save に役の返答を渡して写させ、返す node finish を回す（finish は役の node を結ばず、写しのファイルで読む）"""
        if reply is not None or raw is not None:
            self.run.script("direction_save", reply=dump(reply) if raw is None else raw)
        return self.run.script("finish", prep=dump(prep))

    def test_redirected_reply_is_not_aligned(self):
        got = self.finish(self.prep(), REDIRECTED)
        self.assertEqual((got["ok"], got["status"], got["direction"], got["aligned"], got["why"]),
                         (True, "ok", "redirected", False, REDIRECTED["why"]))
        self.assertTrue(got["report"], "止めた向きは報告の行に出る")
        self.assertEqual(json.loads((self.run.artifacts / "reply.json").read_text(encoding="utf-8")), REDIRECTED)
        # 向きの語は YAML の宣言と同じ（役の返答の enum・返す node の enum）。出口の返りは全部、返す node の output_format に合う
        direction = kit.load(BLOCK, "direction")
        doc = yaml.safe_load((kit.BLOCKS / BLOCK / "works-factory-answer-direction.yaml").read_text(encoding="utf-8"))
        nodes = {n["id"]: n for n in doc["nodes"]}
        self.assertEqual(nodes["direction"]["output_format"]["properties"]["direction"]["enum"], list(direction.VERDICTS))
        self.assertEqual(nodes["finish"]["output_format"]["properties"]["direction"]["enum"], [*direction.VERDICTS, ""])
        for reply in (REDIRECTED, UNCLEAR, ALIGNED):
            kit.returned(BLOCK, self.finish(self.prep(), reply))
        kit.returned(BLOCK, self.finish(self.prep({"decision": "stop", "text": ""})))
        kit.returned(BLOCK, self.finish(None))

    def test_unclear_reply_is_not_aligned(self):
        got = self.finish(self.prep(), UNCLEAR)
        self.assertEqual((got["ok"], got["status"], got["direction"], got["aligned"], got["why"]),
                         (True, "ok", "unclear", False, UNCLEAR["why"]))

    def test_same_direction_note_reads_aligned(self):
        prep = self.prep()
        self.assertEqual((prep["due"], prep["reason"]), (True, ""))
        got = self.finish(prep, ALIGNED)
        self.assertEqual((got["ok"], got["status"], got["direction"], got["aligned"], got["report"]), (True, "ok", "aligned", True, []))

    def test_empty_note_skips_the_role_and_reads_aligned(self):
        """一言が空・空白だけの通す答え、止める語の答えは役を起こさない（reason も空。落ちたのでなく要らない）。aligned は真"""
        for answer in ({"decision": "continue", "text": ""}, {"decision": "approve", "text": " \n "}, {"decision": "continue"},
                       {"decision": "stop", "text": NOTE}, {"decision": "reject", "text": NOTE}):
            with self.subTest(answer=answer):
                prep = self.prep(answer)
                self.assertEqual((prep["due"], prep["prompt"], prep["reason"]), (False, "", ""))
                got = self.finish(prep)
                self.assertEqual((got["ok"], got["status"], got["aligned"], got["direction"], got["reason"]), (True, "skipped", True, "", ""))

    def test_prompt_carries_the_plan_approach_and_the_note(self):
        got = self.prep()
        self.assertTrue(got["due"])
        for want in (NOTE, ASKED[0], PLAN["plan"][0]["approach"], PLAN["plan"][1]["approach"], "stats.py", "modify", "docs/stats.md"):
            self.assertIn(want, got["prompt"])
        self.assertNotIn("responsibility", got["prompt"], "files は path と op だけを要約して渡す")
        self.assertEqual((self.run.artifacts / "direction-prompt-1.md").read_text(encoding="utf-8"), got["prompt"])
        # 言語: 既定は一言の言語、渡せばその言語
        self.assertIn("in the language of the note", got["prompt"])
        self.assertIn("in Japanese", self.prep(lang="Japanese")["prompt"])
        # 一言の中の {name} と $x.output.y は置き換わらずに残る（値の中の字は読み直さない）
        note = "Use $direction-prep.output.body and {plan} and {note} here."
        self.assertIn(note, self.prep({"decision": "continue", "text": note})["prompt"])
        # 見せた項目が無い（null）でも、一言と計画だけで判じる
        self.assertTrue(self.prep(asked="null")["due"])
        # include の中は place が include の道に分かれる
        self.run.script("direction_prep", "answer-direction__direction-prep", answer=dump(GO), asked=dump(ASKED), plan=self.fix_plan_pointer(), lang="")
        self.assertTrue((self.run.artifacts / "answer-direction" / "direction-prompt-1.md").is_file())

    def test_a_missing_reply_fails_closed(self):
        """役を起こしたのに返答の控えが無い（役が落ちた・飛ばされた）時は failed・aligned 偽。前の返答の控えは支度が消すので読み違えない"""
        (self.run.artifacts / "reply.json").write_text(dump(ALIGNED), encoding="utf-8")   # 前の周の古い控え
        prep = self.prep()
        self.assertFalse((self.run.artifacts / "reply.json").exists(), "支度が自分の名の控えを消す")
        got = self.finish(prep)
        self.assertEqual((got["ok"], got["status"], got["aligned"], got["direction"]), (False, "failed", False, ""))
        self.assertIn("返答を返さなかった", got["reason"])
        self.assertTrue(got["report"])
        # 返答が読めない（JSON でない・向きの語の外・why が無い・空）時も同じ
        for raw in ('"not json{"', dump(["x"]), dump({"direction": "maybe", "why": "x"}), dump({"direction": "aligned"}), dump({}), "null"):
            with self.subTest(raw=raw):
                (self.run.artifacts / "reply.json").unlink(missing_ok=True)
                broken = self.finish(self.prep(), raw=raw)
                self.assertEqual((broken["ok"], broken["status"], broken["aligned"]), (False, "failed", False))
        # 支度の node が落ちた時も通さない
        fell = self.run.script("finish", prep="null")
        self.assertEqual((fell["ok"], fell["status"], fell["aligned"]), (False, "failed", False))
        self.assertIn("支度の node が落ちた", fell["reason"])

    def test_unreadable_answer_fails_closed(self):
        for answer in ("not json{", "null", "", dump(["continue"]), dump({"text": NOTE}), dump({"decision": 3, "text": NOTE})):
            with self.subTest(answer=answer):
                prep = self.prep(answer)
                self.assertEqual((prep["due"], prep["prompt"]), (False, ""))
                self.assertIn("入力 answer", prep["reason"])
                got = self.finish(prep)
                self.assertEqual((got["ok"], got["status"], got["aligned"]), (False, "failed", False))
                self.assertEqual(got["reason"], prep["reason"])
        # 見せた項目が字の配列でない時も、役を起こさず入力 asked を名指して落ちた扱い
        asked = self.prep(asked='{"x": 1}')
        self.assertEqual((asked["due"], asked["prompt"]), (False, ""))
        self.assertIn("入力 asked", asked["reason"])

    def test_unreadable_plan_fails_closed(self):
        absent = self.run.pointer("plan/absent.json")
        for given in ("null", "", absent, dump({"plan": []}), "not-a-path-or-pointer{"):
            with self.subTest(given=given):
                prep = self.prep(given=given)
                self.assertEqual((prep["due"], prep["prompt"]), (False, ""))
                self.assertIn("入力 plan", prep["reason"])
                got = self.finish(prep)
                self.assertEqual((got["ok"], got["status"], got["aligned"]), (False, "failed", False))
        # 一言が空か止める語なら計画を読む前に要らないと決める（人が止めた答えは計画が読めなくても skipped）
        stopped = self.prep({"decision": "stop", "text": ""}, given="null")
        self.assertEqual((stopped["due"], stopped["reason"]), (False, ""))


if __name__ == "__main__":
    unittest.main()
