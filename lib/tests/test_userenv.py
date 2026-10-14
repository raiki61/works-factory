"""利用者の HOME・XDG の控え（lib/userenv.py）の検査。戻す側は lib/tests/test_tree_run.py の OutsideEnvCase が照らす"""
import json
import pathlib
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import userenv  # noqa: E402


class RecordCase(unittest.TestCase):
    def test_only_an_explicit_switch_records(self):
        """既定は控えない（対象のコマンドも隔離のまま）。"1" のほかの値も明示と読まない"""
        for value in (None, "", "0", "true"):
            with self.subTest(value=value):
                env = {"HOME": "/u"} if value is None else {"HOME": "/u", userenv.OPT_IN: value}
                self.assertIsNone(userenv.record(env))

    def test_switch_records_home_and_xdg_with_null_for_unset(self):
        got = json.loads(userenv.record({"HOME": "/u", "XDG_CONFIG_HOME": "/u/.cfg", "CLAUDE_CONFIG_DIR": "/u/.c",
                                         userenv.OPT_IN: "1"}))
        self.assertEqual(got, {"HOME": "/u", "XDG_CONFIG_HOME": "/u/.cfg", "XDG_DATA_HOME": None, "XDG_CACHE_HOME": None,
                               "XDG_STATE_HOME": None})

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.top = pathlib.Path(tmp.name) / "line"

    def test_record_round_trips_through_restore(self):
        env = {"HOME": "/run/home", "XDG_DATA_HOME": "/run/data", userenv.RAN_DIR_ENV: str(self.top),
               userenv.RECORD: userenv.record({"HOME": "/u", userenv.OPT_IN: "1"})}
        self.assertTrue(userenv.opted(env))
        self.assertFalse(userenv.ran(self.top))
        userenv.restore(env)
        self.assertEqual(env, {"HOME": "/u", userenv.MARK: str(self.top / userenv.RAN_FILE)})
        self.assertFalse(userenv.opted(env))
        self.assertFalse(userenv.ran(self.top))   # 印は起こす側が子を起こす直前に置く
        self.assertTrue(userenv.mark(env[userenv.MARK]))
        self.assertTrue(userenv.ran(self.top))
        self.assertFalse(userenv.mark(env[userenv.MARK]))   # 前から在った印（起こせなかった時に消さない）

    def test_restore_without_the_marker_place_gives_nothing_back(self):
        """#504: 戻した印を置けない時は戻さない（利用者の HOME・XDG で走ったのを報告が言い漏らさない）"""
        env = {"HOME": "/run/home", userenv.RECORD: userenv.record({"HOME": "/u", userenv.OPT_IN: "1"})}
        with self.assertRaises(ValueError):
            userenv.restore(env)
        self.assertEqual(env["HOME"], "/run/home")

    def test_restore_without_record_leaves_no_marker(self):
        env = {"HOME": "/run/home", userenv.RAN_DIR_ENV: str(self.top)}
        userenv.restore(env)
        self.assertEqual(env, {"HOME": "/run/home"})
        self.assertFalse(userenv.ran(self.top))

    def test_ran_reads_only_the_marker(self):
        self.assertFalse(userenv.ran(None))
        self.top.mkdir()
        self.assertFalse(userenv.ran(self.top))
        (self.top / userenv.RAN_FILE).touch()
        self.assertTrue(userenv.ran(self.top))


if __name__ == "__main__":
    unittest.main()
