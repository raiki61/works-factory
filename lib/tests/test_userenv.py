"""利用者の HOME・XDG の控え（lib/userenv.py）の検査。戻す側は lib/tests/test_tree_run.py の OutsideEnvCase が照らす"""
import json
import pathlib
import sys
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

    def test_record_round_trips_through_restore(self):
        env = {"HOME": "/run/home", "XDG_DATA_HOME": "/run/data",
               userenv.RECORD: userenv.record({"HOME": "/u", userenv.OPT_IN: "1"})}
        self.assertTrue(userenv.opted(env))
        userenv.restore(env)
        self.assertEqual(env, {"HOME": "/u"})
        self.assertFalse(userenv.opted(env))


if __name__ == "__main__":
    unittest.main()
