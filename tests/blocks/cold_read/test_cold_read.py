"""初見の読み手の block を、script を子のプロセスで回して確かめる（docs/design/cold-read.md の 11 節）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、cold_prep → 台本の返答 → finish と回す。
筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import unittest

from tests.blocks import kit
from tests.blocks.cold_read import values

BAD_REPLY = "初見の読み手の返答を読めない（判定の語が無い）"
EMPTY = "（止まった所・推測の欄が空）"


def dump(doc) -> str:
    return json.dumps(doc, ensure_ascii=False)


class _Case(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "cold-read")

    def put(self, name: str, text: str) -> str:
        (self.run.repo / name).write_text(text, encoding="utf-8")
        return name

    def prep(self, text: str = values.BODY, **inputs) -> dict:
        return self.run.script("cold_prep", text=self.put("draft.md", text), lang="", **inputs)

    def finish(self, prep, reply, raw: str | None = None) -> dict:
        """受け皿 cold-save に役の返答を渡して写させ、出口 finish を回す（出口は役の node を結ばず、写しのファイルで読む）"""
        self.run.script("cold_save", reply=dump(reply) if raw is None else raw)
        return self.run.script("finish", prep=dump(prep))


class PrepCase(_Case):
    def test_missing_file_is_not_due(self):
        got = self.run.script("cold_prep", text="absent.md", lang="")
        self.assertFalse(got["due"])
        self.assertEqual(got["prompt"], "")
        self.assertIn("absent.md", got["reason"])
        self.assertIn("読ませる本文のファイルを読めない", got["reason"])
        self.assertIn("入力 text", got["reason"], "壊れた入力を名指す")

    def test_not_utf8_is_not_due(self):
        (self.run.repo / "bin.md").write_bytes(b"\xff\xfe\x00bad")
        got = self.run.script("cold_prep", text="bin.md", lang="")
        self.assertFalse(got["due"])
        self.assertIn("UnicodeDecodeError", got["reason"])

    def test_empty_text_is_not_due(self):
        got = self.prep("  \n\n")
        self.assertEqual((got["due"], got["prompt"], got["reason"]), (False, "", "読ませる本文が空"))

    def test_no_text_input_is_not_due(self):
        self.assertFalse(self.run.script("cold_prep", text="", lang="")["due"])

    def test_deletes_only_its_own_files(self):
        (self.run.artifacts / "cold-prompt-1.md").write_text("old", encoding="utf-8")
        (self.run.artifacts / "read.json").write_text("{}", encoding="utf-8")
        (self.run.artifacts / "other-block.json").write_text("{}", encoding="utf-8")
        self.prep()
        self.assertTrue((self.run.artifacts / "other-block.json").is_file())
        self.assertFalse((self.run.artifacts / "read.json").exists())
        self.assertNotEqual((self.run.artifacts / "cold-prompt-1.md").read_text(encoding="utf-8"), "old")


class FinishCase(_Case):
    DUE = {"due": True, "prompt": "p", "reason": ""}

    def test_pass(self):
        got = self.finish(self.DUE, values.PASS)
        self.assertEqual((got["ok"], got["status"], got["verdict"], got["pass"], got["stuck"], got["report"]),
                         (True, "ok", "pass", True, [], []))
        self.assertTrue(got["decidable"])
        self.assertEqual(json.loads((self.run.artifacts / "reply.json").read_text(encoding="utf-8")), values.PASS)
        self.assertEqual(json.loads((self.run.artifacts / "read.json").read_text(encoding="utf-8")), got)

    def test_redesign_lists_stops_then_guesses(self):
        got = self.finish(self.DUE, values.REDESIGN)
        self.assertEqual((got["ok"], got["status"], got["verdict"], got["pass"]), (True, "ok", "redesign-needed", False))
        self.assertEqual(got["stuck"], [f"止まった所: {s}" for s in values.REDESIGN["stops"]]
                         + [f"推測で埋めた所: {g}" for g in values.REDESIGN["guessed"]])
        self.assertEqual(got["stops"], values.REDESIGN["stops"])
        self.assertEqual(got["report"], ["初見の読み手が通さなかった: " + "；".join(got["stuck"])])

    def test_redesign_with_empty_fields(self):
        got = self.finish(self.DUE, {"verdict": "redesign-needed", "stops": [], "guessed": [], "decidable": False})
        self.assertEqual((got["status"], got["stuck"]), ("ok", [EMPTY]))

    def test_broken_or_foreign_reply_is_named_not_passed(self):
        for raw in ('"not json{"', dump(["x"]), dump({"verdict": "maybe", "stops": [], "guessed": [], "decidable": True}), dump({})):
            with self.subTest(raw=raw):
                (self.run.artifacts / "reply.json").unlink(missing_ok=True)
                done = self.finish(self.DUE, None, raw)
                self.assertEqual((done["ok"], done["status"], done["verdict"], done["pass"]), (False, "failed", "", False))
                self.assertEqual((done["reason"], done["stuck"]), (BAD_REPLY, [BAD_REPLY]))
                self.assertEqual(done["report"], [f"初見の読み手: 読めなかった（{BAD_REPLY}）"])

    def test_null_reply_fails(self):
        for reply in ("null", ""):
            with self.subTest(reply=reply):
                got = self.finish(self.DUE, None, reply)
                self.assertEqual((got["status"], got["stuck"]), ("failed", [BAD_REPLY]))
                self.assertIn("返答を返さなかった", got["reason"])
        self.assertFalse((self.run.artifacts / "reply.json").exists())

    def test_prep_stopped_it(self):
        got = self.run.script("finish", prep=dump({"due": False, "prompt": "", "reason": "読ませる本文が空"}))
        self.assertEqual((got["ok"], got["status"], got["reason"], got["verdict"], got["pass"], got["stops"], got["guessed"],
                          got["decidable"], got["stuck"]), (False, "failed", "読ませる本文が空", "", False, [], [], False, []))
        self.assertEqual(got["report"], ["初見の読み手: 読めなかった（読ませる本文が空）"])

    def test_prep_fell(self):
        got = self.run.script("finish", prep="null")
        self.assertEqual((got["status"], got["reason"]), ("failed", "支度の node が落ちた"))

    def test_end_to_end_through_prep(self):
        prep = self.prep()
        got = self.finish(prep, values.REDESIGN)
        self.assertEqual(got["status"], "ok")


if __name__ == "__main__":
    unittest.main()
