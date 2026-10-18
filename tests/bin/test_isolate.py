"""run の置き場の隔離（bin/_lib/isolate.py）の検査。

今の works の dev/archon.sh の、HOME・ARCHON_HOME・CLAUDE_CONFIG_DIR・XDG_* を run の置き場へ向ける所を Python に移した物。
向け先は全部 run の置き場の下で、認証の起こし役（auth_launch.py）が読む利用者の HOME と CLAUDE_CONFIG_DIR は、変わらずに残る隔離の前の env から取る。
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bin" / "_lib"))
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))

import isolate  # noqa: E402
import userenv  # noqa: E402
from tests import archon  # noqa: E402
from tests.bin import hermetic  # noqa: E402

ISOLATED = {"HOME", "ARCHON_HOME", "CLAUDE_CONFIG_DIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"}


class IsolateCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.run_home = pathlib.Path(tmp.name).resolve() / "run"

    def test_every_target_is_a_separate_folder_under_the_run_home(self):
        env = {"HOME": "/u", "CLAUDE_CONFIG_DIR": "/u/.claude-x", "XDG_CONFIG_HOME": "/u/.config", "ARCHON_HOME": "/u/.archon"}
        child = isolate.isolate(env, self.run_home)
        self.assertEqual(set(isolate.DIRS), ISOLATED)
        targets = [pathlib.Path(child[name]) for name in sorted(ISOLATED)]
        self.assertEqual(len(set(targets)), len(ISOLATED))
        for name, target in zip(sorted(ISOLATED), targets):
            with self.subTest(name):
                self.assertTrue(target.is_relative_to(self.run_home), target)
                self.assertTrue(target.is_dir(), target)

    def test_users_home_and_claude_config_stay_in_the_given_env(self):
        env = {"HOME": "/u", "CLAUDE_CONFIG_DIR": "/u/.claude-x"}
        child = isolate.isolate(env, self.run_home)
        self.assertEqual(env, {"HOME": "/u", "CLAUDE_CONFIG_DIR": "/u/.claude-x"})
        self.assertTrue(pathlib.Path(child["CLAUDE_CONFIG_DIR"]).is_relative_to(self.run_home))

    def test_other_names_pass_through_and_the_given_env_is_not_changed(self):
        env = {"HOME": "/u", "PATH": "/usr/bin", "LANG": "ja_JP.UTF-8"}
        child = isolate.isolate(env, self.run_home)
        self.assertEqual((child["PATH"], child["LANG"]), ("/usr/bin", "ja_JP.UTF-8"))
        self.assertEqual(env, {"HOME": "/u", "PATH": "/usr/bin", "LANG": "ja_JP.UTF-8"})

    def test_users_home_and_xdg_are_always_recorded(self):
        """隔離の前の HOME・XDG_* の新しい控えをいつも置く（利用者の env から継いだ古い控え・印の置き場・印のパスは落とす）。
        控える名は、隔離する名から Archon と Claude Code の置き場を除いた物"""
        env = {"HOME": "/u", "XDG_CONFIG_HOME": "/u/.cfg", "CLAUDE_CONFIG_DIR": "/u/.c", userenv.RECORD: "stale",
               userenv.RAN_DIR_ENV: "/stale", userenv.MARK: "/stale/mark"}
        child = isolate.isolate(env, self.run_home)
        self.assertNotEqual(child[userenv.RECORD], "stale")
        self.assertNotIn(userenv.RAN_DIR_ENV, child)
        self.assertNotIn(userenv.MARK, child)   # #514: 継いだ印のパスは子に残さない
        record = json.loads(child[userenv.RECORD])
        self.assertEqual(record["HOME"], "/u")
        self.assertEqual(record["XDG_CONFIG_HOME"], "/u/.cfg")
        self.assertEqual(set(record), set(userenv.NAMES))
        self.assertEqual(set(userenv.NAMES), set(isolate.DIRS) - {"ARCHON_HOME", "CLAUDE_CONFIG_DIR"})
        self.assertIn(userenv.RECORD, isolate.isolate({"HOME": "/u"}, self.run_home))
        self.assertEqual(pathlib.Path(child["HOME"]), self.run_home / "home")   # 子の HOME は控えと別に隔離したまま

    def test_every_inherited_control_name_is_dropped(self):
        """#532: userenv が持つ制御の変数の組（userenv.CONTROL）の、継いだ値は子に残さない（子に残るのは新しく作った控えだけ）"""
        env = {"HOME": "/u", **{name: "stale" for name in userenv.CONTROL}}
        child = isolate.isolate(env, self.run_home)
        self.assertEqual(set(userenv.CONTROL) & set(child), {userenv.RECORD})
        self.assertNotEqual(child[userenv.RECORD], "stale")

    def test_relative_run_home_is_refused(self):
        """相対の置き場は cd した子で別の所を指すので、何も作らずに止める"""
        with self.assertRaises(ValueError):
            isolate.isolate({"HOME": "/u"}, pathlib.Path("run"))
        self.assertFalse(pathlib.Path("run").exists())


# 止めた Archon の作業場の作り（packages/isolation/src/providers/worktree.ts の addLockedWorktree）と同じ順で、まだ無い作業場の
# パスを git の全体の設定に足す（git worktree add の前に addSafeDirectory）。作業場の置き場は Archon 自身が ARCHON_HOME から組む
GRANT_TS = """\
import { getProjectWorktreesPath } from '@SOURCE@/packages/paths/src/archon-paths.ts';
import { addSafeDirectory } from '@SOURCE@/packages/git/src/repo.ts';
const [where, kind] = process.argv.slice(2);
const path = kind === 'new' ? `${getProjectWorktreesPath('o', 'r')}/${where}` : where;
await addSafeDirectory(path as never);
"""


@unittest.skipIf(os.geteuid() == 0, "止めた Archon は root の作業場のパスをいつも git の全体の設定に書く（書かずに済むのは root でない利用者）")
class ParallelWorktreeGrantCase(unittest.TestCase):
    """#727: 並べて走る子の run の作業場の作りが、工場の家の .gitconfig のロックにぶつからない。

    Archon の子の run は 1 つのプロセスの中で走り、git の全体の設定は殻が渡す HOME（工場の家）の .gitconfig 1 つを分け合う。git は
    設定を書く間 .gitconfig.lock を作り、ほかが持っていれば待たずに落ちる。ここではロックを持ったまま子 2 本ぶんの書きを同時に回す。
    止めた Archon は、まだ無いパスで、いちばん近い在る親がそのプロセスの利用者の物なら書かずに済ませる。殻が作業場の置き場
    （ARCHON_HOME）を利用者の物として作るので、子の作業場はいつもこれに当たる。
    """

    def setUp(self):
        source = archon.source()
        self.bun = shutil.which("bun")
        if self.bun is None:
            raise archon.absent("bun が無い")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = pathlib.Path(tmp.name).resolve()
        self.script = base / "grant.ts"
        self.script.write_text(GRANT_TS.replace("@SOURCE@", str(source)), encoding="utf-8")
        self.env = isolate.isolate(hermetic.child_env(), base / "run")
        for name in ("GIT_CONFIG_GLOBAL", "GIT_TEST_ASSUME_DIFFERENT_OWNER"):
            self.env.pop(name, None)
        self.gitconfig = pathlib.Path(self.env["HOME"]) / ".gitconfig"
        self.gitconfig.write_text("[user]\n\tname = factory\n", encoding="utf-8")
        self.gitconfig.with_name(".gitconfig.lock").touch()

    def grant(self, *args: str) -> subprocess.Popen:
        return subprocess.Popen([self.bun, str(self.script), *args], env=self.env, cwd=self.script.parent,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")

    def test_two_children_creating_worktrees_together_both_succeed(self):
        children = [self.grant(branch, "new") for branch in ("group-a", "group-b")]
        for child in children:
            _, err = child.communicate()
            self.assertEqual(child.returncode, 0, err)
        self.assertEqual(self.gitconfig.read_text(encoding="utf-8"), "[user]\n\tname = factory\n")

    def test_held_lock_fails_a_write_that_is_not_skipped(self):
        """上の試験が書きの省きで通り、ロックが効かずに通るのではないことの対照。在るパス（Archon が在る作業場を使い直す時に
        足す物）は省かれず、#727 の落ちと同じ文で落ちる"""
        existing = pathlib.Path(self.env["ARCHON_HOME"]) / "existing"
        existing.mkdir()
        _, err = self.grant(str(existing), "existing").communicate()
        self.assertIn("could not lock config file", err)


if __name__ == "__main__":
    unittest.main()
