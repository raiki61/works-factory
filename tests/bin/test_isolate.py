"""run の置き場の隔離（bin/_lib/isolate.py）の検査。

今の works の dev/archon.sh の、HOME・ARCHON_HOME・CLAUDE_CONFIG_DIR・XDG_* を run の置き場へ向ける所を Python に移した物。
向け先は全部 run の置き場の下で、認証の起こし役（auth_launch.py）が読む利用者の HOME と CLAUDE_CONFIG_DIR は隔離の前に取る。
"""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "bin" / "_lib"))

import isolate  # noqa: E402

ISOLATED = {"HOME", "ARCHON_HOME", "CLAUDE_CONFIG_DIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"}


class IsolateCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run_home = pathlib.Path(tmp.name).resolve() / "run"

    def test_every_target_is_a_separate_folder_under_the_run_home(self):
        env = {"HOME": "/u", "CLAUDE_CONFIG_DIR": "/u/.claude-x", "XDG_CONFIG_HOME": "/u/.config", "ARCHON_HOME": "/u/.archon"}
        child, _ = isolate.isolate(env, self.run_home)
        self.assertEqual(set(isolate.DIRS), ISOLATED)
        targets = [pathlib.Path(child[name]) for name in sorted(ISOLATED)]
        self.assertEqual(len(set(targets)), len(ISOLATED))
        for name, target in zip(sorted(ISOLATED), targets):
            with self.subTest(name):
                self.assertTrue(target.is_relative_to(self.run_home), target)
                self.assertTrue(target.is_dir(), target)

    def test_users_home_and_claude_config_are_taken_before_isolation(self):
        child, user = isolate.isolate({"HOME": "/u", "CLAUDE_CONFIG_DIR": "/u/.claude-x"}, self.run_home)
        self.assertEqual((user.home, user.claude_config), ("/u", "/u/.claude-x"))
        self.assertNotEqual(child["CLAUDE_CONFIG_DIR"], "/u/.claude-x")

    def test_unset_claude_config_is_kept_as_empty(self):
        """利用者が CLAUDE_CONFIG_DIR を置いていなければ空のまま渡す（auth_launch の --user-config は空を「置いていない」と読む）"""
        _, user = isolate.isolate({"HOME": "/u"}, self.run_home)
        self.assertEqual(user.claude_config, "")

    def test_other_names_pass_through_and_the_given_env_is_not_changed(self):
        env = {"HOME": "/u", "PATH": "/usr/bin", "LANG": "ja_JP.UTF-8"}
        child, _ = isolate.isolate(env, self.run_home)
        self.assertEqual((child["PATH"], child["LANG"]), ("/usr/bin", "ja_JP.UTF-8"))
        self.assertEqual(env, {"HOME": "/u", "PATH": "/usr/bin", "LANG": "ja_JP.UTF-8"})

    def test_relative_run_home_is_refused(self):
        """相対の置き場は cd した子で別の所を指すので、何も作らずに止める"""
        with self.assertRaises(ValueError):
            isolate.isolate({"HOME": "/u"}, pathlib.Path("run"))
        self.assertFalse(pathlib.Path("run").exists())


if __name__ == "__main__":
    unittest.main()
