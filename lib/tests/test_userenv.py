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
    def test_record_ignores_any_switch_and_always_records(self):
        """どの env でも NAMES の値（無い名は null）の JSON を返す。旗を見ない（控えの有無を分ける旗とその問いは無い）"""
        self.assertFalse(hasattr(userenv, "OPT_IN"))
        self.assertFalse(hasattr(userenv, "opted"))
        for env in ({}, {"HOME": "/u"}, {"HOME": "/u", "WORKS_FACTORY_TARGET_USER_ENV": "0"}):
            with self.subTest(env=env):
                got = json.loads(userenv.record(env))
                self.assertEqual(set(got), set(userenv.NAMES))
                self.assertEqual(got["HOME"], env.get("HOME"))

    def test_record_holds_home_and_xdg_with_null_for_unset(self):
        got = json.loads(userenv.record({"HOME": "/u", "XDG_CONFIG_HOME": "/u/.cfg", "CLAUDE_CONFIG_DIR": "/u/.c"}))
        self.assertEqual(got, {"HOME": "/u", "XDG_CONFIG_HOME": "/u/.cfg", "XDG_DATA_HOME": None, "XDG_CACHE_HOME": None,
                               "XDG_STATE_HOME": None})

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.top = pathlib.Path(tmp.name) / "line"

    def test_record_round_trips_through_restore(self):
        env = {"HOME": "/run/home", "XDG_DATA_HOME": "/run/data", userenv.RAN_DIR_ENV: str(self.top),
               userenv.RECORD: userenv.record({"HOME": "/u"})}
        self.assertFalse(userenv.ran(self.top))
        userenv.restore(env)
        self.assertEqual(env, {"HOME": "/u", userenv.MARK: str(self.top / userenv.RAN_FILE)})
        self.assertFalse(userenv.ran(self.top))   # 印は起こす側が子を起こす直前に置く
        self.assertTrue(userenv.mark(env[userenv.MARK]))
        self.assertTrue(userenv.ran(self.top))
        self.assertFalse(userenv.mark(env[userenv.MARK]))   # 前から在った印（起こせなかった時に消さない）

    def test_restore_without_the_marker_place_gives_nothing_back(self):
        """#504: 戻した印を置けない時は戻さない（利用者の HOME・XDG で走ったのを報告が言い漏らさない）"""
        env = {"HOME": "/run/home", userenv.RECORD: userenv.record({"HOME": "/u"})}
        with self.assertRaises(ValueError):
            userenv.restore(env)
        self.assertEqual(env["HOME"], "/run/home")

    def test_restore_without_record_leaves_no_marker(self):
        env = {"HOME": "/run/home", userenv.RAN_DIR_ENV: str(self.top)}
        userenv.restore(env)
        self.assertEqual(env, {"HOME": "/run/home"})
        self.assertFalse(userenv.ran(self.top))

    def test_restore_drops_every_inherited_control_name(self):
        """#532: 起動の殻と同じ制御の変数の組（CONTROL）を外す。控えが無ければ印のパスも置かない"""
        env = {"HOME": "/run/home", **{name: "stale" for name in userenv.CONTROL if name != userenv.RECORD}}
        userenv.restore(env)
        self.assertEqual(env, {"HOME": "/run/home"})

    def test_ran_reads_only_the_marker(self):
        self.assertFalse(userenv.ran(None))
        self.top.mkdir()
        self.assertFalse(userenv.ran(self.top))
        (self.top / userenv.RAN_FILE).touch()
        self.assertTrue(userenv.ran(self.top))


class NoteCase(unittest.TestCase):
    def test_note_says_whose_environment_and_that_no_action_is_needed(self):
        """報告の頭の知らせの行（#812）: 誰の環境で走ったかと、読み手の操作が要らないこと（毎回の決まりの動き）を言う"""
        self.assertIn("あなたの", userenv.NOTE)
        self.assertIn("操作は要らない", userenv.NOTE)


if __name__ == "__main__":
    unittest.main()
