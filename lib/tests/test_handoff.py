"""引き継ぎのメモの住処（lib/handoff.py）の検査。型・頼み・前の周の節・控えの書き読みが計画と報告で 1 つであること。"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import handoff  # noqa: E402
import planfile  # noqa: E402
import report_roles  # noqa: E402

NOTE = {"read": [{"path": "stats.py", "lines": "1-20", "why": "mean の分母を確かめた"}],
        "decided": ["分母は len(xs) にする"],
        "rejected": [{"option": "新しい助け手を足す", "why": "stats.py に clamp の枝が在る"}],
        "doubts": ["空の列の扱い"]}


class HandoffCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)

    def test_plan_and_report_take_the_one_schema(self):
        """計画も報告もメモの型・欄の名・頼みを自前で持たず、報告の書き手の返答の型の handoff は handoff.SCHEMA と同じで、
        4 つ目の欄は doubts。頼みは役の名を含まず、メモは本文・案に入らないと言う"""
        for module in (planfile, report_roles):
            for name in ("HANDOFF", "HANDOFF_KEYS", "HANDOFF_SCHEMA", "HANDOFF_HEAD", "HANDOFF_ASK", "NO_HANDOFF", "handoff_section"):
                with self.subTest(module=module.__name__, name=name):
                    self.assertFalse(hasattr(module, name), f"{module.__name__}.{name} がまだ在る")
        self.assertEqual(handoff.FIELD, "handoff")
        self.assertEqual(handoff.KEYS, ("read", "decided", "rejected", "doubts"))
        self.assertEqual(list(handoff.SCHEMA["properties"]), list(handoff.KEYS))
        self.assertEqual(handoff.SCHEMA["required"], list(handoff.KEYS))
        self.assertEqual(report_roles.TEXT_SCHEMA["properties"][handoff.FIELD], handoff.SCHEMA)
        for key in handoff.KEYS:
            self.assertIn(key, handoff.ASK)
        self.assertIn(handoff.FIELD, handoff.ASK)
        for role in ("plan", "報告"):
            self.assertNotIn(role, handoff.ASK, "頼みは役に依らない字")
        self.assertIn("本文", handoff.ASK)
        self.assertIn(handoff.FIELD, planfile.RESUBMIT_RULES)
        self.assertIn(handoff.FIELD, planfile.REPLAN_RESUBMIT_RULES)

    def test_section_names_every_prior_note_oldest_first(self):
        rounds = [self.dir / f"r{n}" for n in (1, 2, 3)]
        handoff.save(rounds[0], NOTE)
        rounds[1].mkdir()
        rounds[2].mkdir()
        (rounds[2] / "handoff.json").write_text("{壊れた", encoding="utf-8")
        text = handoff.section(rounds)
        self.assertTrue(text.startswith(handoff.HEAD), text)
        self.assertEqual(handoff.HEAD.source, "fn:handoff.section")
        self.assertLess(text.index(handoff.HEAD), text.index(handoff.USE))
        self.assertLess(text.index(handoff.USE), text.index(str(handoff.path_of(rounds[0]))))
        for word in ("read", "decided", "rejected", "doubts"):
            self.assertIn(word, handoff.USE)
        lines = [line for line in text.splitlines() if line.startswith("- ")]
        self.assertEqual(len(lines), 3, "1 周 1 行")
        self.assertIn(str(handoff.path_of(rounds[0])), lines[0])
        self.assertIn("r1", lines[0])
        self.assertIn(handoff.NONE, lines[1])
        self.assertIn("r2", lines[1])
        self.assertNotIn(str(handoff.path_of(rounds[1])), lines[1])
        self.assertIn(handoff.UNREADABLE, lines[2])
        self.assertIn("r3", lines[2])
        self.assertNotIn(NOTE["decided"][0], text, "中身は貼らずパスで名指す")
        self.assertEqual(handoff.section([]), "", "並びが空なら節ごと出さない")

    def test_unreadable_names_only_broken_prior_notes(self):
        r1, r2, r3, r4, r5 = (self.dir / f"r{n}" for n in range(1, 6))
        handoff.save(r1, NOTE)
        self.assertEqual(json.loads(handoff.path_of(r1).read_text(encoding="utf-8")), NOTE, "まだ無い周のフォルダも作って置く")
        r2.mkdir()
        handoff.path_of(r2).write_text("{壊れた", encoding="utf-8")
        r3.mkdir()
        handoff.path_of(r3).write_text("null", encoding="utf-8")
        r4.mkdir()
        self.assertEqual(handoff.unreadable([r1, r2, r3, r4]), [handoff.path_of(r2), handoff.path_of(r3)])
        r5b = self.dir / "r6"
        r5b.mkdir()
        handoff.path_of(r5b).write_text("[]", encoding="utf-8")
        self.assertEqual(handoff.unreadable([r5b]), [handoff.path_of(r5b)], "オブジェクトでない控えも読めない")
        handoff.save(r5, {})
        self.assertFalse(r5.exists(), "メモが空なら周のフォルダを作らない")
        handoff.save(r1, {})
        self.assertFalse(handoff.path_of(r1).exists(), "メモが空なら前の控えを消す")
        self.assertTrue(r1.is_dir())


if __name__ == "__main__":
    unittest.main()
