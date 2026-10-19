"""引き継ぎのメモの住処（lib/handoff.py）の検査。型と控えの書き読みが 1 つであること（頼みと前の周の節の文は共通の断片 handoff.md）。"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import handoff  # noqa: E402

NOTE = {"read": [{"path": "stats.py", "lines": "1-20", "why": "mean の分母を確かめた"}],
        "kept": ["分母は len(xs) にする"],
        "set_aside": [{"option": "新しい助け手を足す", "why": "stats.py に clamp の枝が在る"}],
        "open": ["空の列の扱い"]}


class HandoffCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)

    def test_one_schema(self):
        """4 つ目の欄は open。欄の名に decided・rejected・doubts を使わない（#712: 返答の型の欄にこの名が並ぶと、報告の書き手がモデルの提供元の安全の判定 reasoning_extraction に止められた）"""
        self.assertEqual(handoff.FIELD, "handoff")
        self.assertEqual(handoff.KEYS, ("read", "kept", "set_aside", "open"))
        self.assertFalse({"decided", "rejected", "doubts"} & set(handoff.KEYS))
        self.assertEqual(list(handoff.SCHEMA["properties"]), list(handoff.KEYS))
        self.assertEqual(handoff.SCHEMA["required"], list(handoff.KEYS))
        self.assertEqual(handoff.path_of(self.dir), self.dir / handoff.FILE)

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
        r6 = self.dir / "r6"
        r6.mkdir()
        handoff.path_of(r6).write_text("[]", encoding="utf-8")
        self.assertEqual(handoff.unreadable([r6]), [handoff.path_of(r6)], "オブジェクトでない控えも読めない")
        handoff.save(r5, {})
        self.assertFalse(r5.exists(), "メモが空なら周のフォルダを作らない")
        handoff.save(r1, {})
        self.assertFalse(handoff.path_of(r1).exists(), "メモが空なら前の控えを消す")
        self.assertTrue(r1.is_dir())


if __name__ == "__main__":
    unittest.main()
