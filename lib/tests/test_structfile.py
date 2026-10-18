"""構造のブロックの置き場の名の住処と書き手（lib/structfile.py）の試験。段 A を通しで回す試験は tests/workflows/test_structure.py。"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

import eye  # noqa: E402
import rolekit  # noqa: E402
import structfile  # noqa: E402
import structmark  # noqa: E402


class TmpCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)


class StateCase(TmpCase):
    """構造の目の控え structure-state.json（元 tests/test_structure_eye.py の CollectCase。元 blk-structure/scripts/collect.py）"""

    MEASURED = {"status": "ok", "reason": "", "units": [{"id": "u-1", "status": "measured", "measure": {"churn": 3}}],
                "timing": {"wall_s": 0.5}}

    def state(self, structure, kept=None, rejects=()):
        d = self.tmp / f"s{len(list(self.tmp.iterdir()))}"
        d.mkdir()
        (d / structfile.STRUCTURE_FILE).write_text(json.dumps(structure, ensure_ascii=False), encoding="utf-8")
        if kept is not None:
            (d / eye.EYE_FILE).write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")
        for why in rejects:
            rolekit.with_done(d, eye.NAME, {"ok": False, "reason": why})
        return json.loads(structfile.write_state(d).read_text(encoding="utf-8"))

    def test_each_failure_names_the_reason(self):
        """3 回拒まれた周の回の数と最後の拒否の文は、目の拒否の控え（rolekit の rejects-<eye.NAME>.json）から読む"""
        cases = {
            "目が通った": (self.MEASURED, {"status": "ok"}, (), "ok", ""),
            "目を起こさない run": ({**self.MEASURED, "units": []}, None, (), "ok", ""),
            "会話が落ちた": (self.MEASURED, None, (), "failed", "構造の目の会話が落ちたか走らなかった（目の受け付けの控えが無いか途中のまま）"),
            "3 回拒まれた": (self.MEASURED, {"status": "gave_up"}, ("欠け", "型", "行が無い"), "failed",
                         "構造の目の返答が 3 回とも受け付けで拒まれた: 行が無い"),
            "実測が落ちた": ({**self.MEASURED, "status": "failed", "reason": "git が無い"}, None, (), "failed", "実測が落ちた: git が無い"),
        }
        for name, (structure, kept, rejects, status, reason) in cases.items():
            with self.subTest(name):
                got = self.state(structure, kept, rejects)
                self.assertEqual((got["status"], got["reason"]), (status, reason))

    def test_wall_adds_the_eye_time(self):
        self.assertEqual(self.state(self.MEASURED, {"status": "ok", "wall_s": 2.25})["wall_s"], 2.75)

    def test_unmeasured_run_is_failed_with_an_existing_design_file(self):
        """段 A の控えが無い（実測の節が落ちたか走らなかった）run も failed の控えを書き、design_file は在る 0 バイトのファイルを指す"""
        got = json.loads(structfile.write_state(self.tmp / "x").read_text(encoding="utf-8"))
        self.assertEqual((got["status"], got["reason"]), ("failed", f"段 A の {structfile.STRUCTURE_FILE} が読めない"))
        self.assertEqual(pathlib.Path(got["design_file"]).stat().st_size, 0)


class MeasureCase(TmpCase):
    def test_empty_paths_are_skipped_and_named_in_the_state(self):
        """paths の空な単位は測らず、控えの skipped で読み手に渡る（読み手は隣の skipped-units.json を名で開かない）"""
        out = self.tmp / structfile.DIR
        structfile.measure(out, [{"id": "u-1", "paths": [], "summary": ""}], self.tmp, "")
        state = structfile.write_state(out)
        self.assertEqual(structmark.skipped(state), ["u-1"])
        self.assertEqual(json.loads((out / structfile.UNITS_FILE).read_text(encoding="utf-8")), [])


class KeepStateCase(TmpCase):
    def test_unwritable_state_goes_to_the_spare_folder(self):
        """控えを置き場に書けない run は節を落とさず、SPARE_DIR に「控えを書けない」の訳で failed の控えを置く（元 line_edge の structure_edge）"""
        (self.tmp / structfile.DIR / structfile.STATE_FILE).mkdir(parents=True)
        state = structfile.keep_state(self.tmp)
        self.assertEqual(state, self.tmp / structfile.SPARE_DIR / structfile.STATE_FILE)
        doc = structmark.read(state)
        self.assertEqual(doc["status"], "failed")
        self.assertIn(structfile.UNWRITABLE_STATE, doc["reason"])
        self.assertEqual(pathlib.Path(doc["design_file"]).stat().st_size, 0)

    def test_writable_state_stays_in_the_place(self):
        self.assertEqual(structfile.keep_state(self.tmp), self.tmp / structfile.DIR / structfile.STATE_FILE)


if __name__ == "__main__":
    unittest.main()
