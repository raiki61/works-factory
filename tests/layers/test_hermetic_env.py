"""`tests/`・`lib/tests/` の試験の子の環境は `tests/bin/hermetic.child_env` で作る（`tests/AGENTS.md` の E21 の機械の行）。

- `tests/` と `lib/tests/` の `*.py` に、`os.environ` を写す形（`scan.COPIED_ENVIRON`）と、`env=` の無い子の起こし（`scan.SPAWNS`）が無い。既定が `None` の引数を差し替えずに `env=` へ渡す形と、assert に環境の辞書（名が `environ`・`env`・`*_env` の変数。位置でも `msg=`・`container=` でも）を丸ごと渡す形（落ちると資格を含む中身が公開の CI のログに出る。`set(env)`・`env.get(鍵)` で比べる）も当てる。照らしは `tests/layers/scan.py` の `_hermetic_env`。
- 外しは `scan.ALLOWED["E21"]` の行（訳つき）だけ: 子の環境を作る道具でなく利用者の環境を継ぐのが用途の物（本物の run・較正の命令の道具・試験を回す口 `tests/changed.py`）と、子の環境を組む口でない物（偽の script の字）。
- 試験を回す口が過程の環境から名を外し、外した値を `inherited` で引けることは `tests/test_shard.py` の `ScrubTest`。
"""
import pathlib
import unittest

from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
# 種の字を継いで書く（この試験のファイルも E21 の対象で、1 つの綴りで書くと本物の木の走査に当たる）
ENVIRON = "os" + ".environ"
COPIES = (
    f'{{**{ENVIRON}, "A": "1"}}',
    f"{{k: v for k, v in {ENVIRON}.items()}}",
    f"dict({ENVIRON})",
    f'dict({ENVIRON}, A="1")',
    f"{ENVIRON}.copy()",
    f'{ENVIRON} | {{"A": "1"}}',
    f"subprocess.run(cmd, env={ENVIRON})",
    f"tree_run.outside_env({ENVIRON})",
    f'tree_run.outside_env({ENVIRON}, "A")',
)


class HermeticEnvTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(scan.problems("E21", ROOT), [])

    def test_seed_caught(self):
        files = {
            "tests/x/test_a.py": f'env = {{**{ENVIRON}, "A": "1"}}\n',
            "lib/tests/test_b.py": f"env = {{k: v for k, v in {ENVIRON}.items()}}\n",
        }
        with tree(files) as root:
            got = scan.problems("E21", root)
        for path in ("tests/x/test_a.py:1:", "lib/tests/test_b.py:1:"):
            self.assertTrue(any(line.startswith(path) for line in got), got)

    def test_every_form_that_copies_the_parent_environment_is_caught(self):
        for form in COPIES:
            with self.subTest(form=form), tree({"tests/x/test_a.py": f"env = {form}\n"}) as root:
                got = scan.problems("E21", root)
            self.assertTrue(any(line.startswith("tests/x/test_a.py:1:") for line in got), (form, got))

    def test_every_child_started_without_an_env_is_caught(self):
        for call in ("subprocess.run(cmd)", "subprocess.Popen(cmd, cwd=d)", "subprocess.check_output(cmd, env=None)",
                     "subprocess.call(cmd)", "subprocess.check_call(cmd)", "asyncio.create_subprocess_exec(*cmd)",
                     "os.system(cmd)", "os.popen(cmd)"):
            with self.subTest(call=call), tree({"lib/tests/test_a.py": f"x = 1\ndone = {call}\n"}) as root:
                got = scan.problems("E21", root)
            self.assertTrue(any(line.startswith("lib/tests/test_a.py:2:") for line in got), (call, got))

    def test_an_env_parameter_that_defaults_to_none_passed_straight_through_is_caught(self):
        for sig in ("env=None", "*, env=None", "env: dict | None = None"):
            text = f"def run(cmd, {sig}):\n    return subprocess.run(cmd, env=env)\n"
            with self.subTest(sig=sig), tree({"tests/x/test_a.py": text}) as root:
                got = scan.problems("E21", root)
            self.assertTrue(any(line.startswith("tests/x/test_a.py:2:") for line in got), (sig, got))

    def test_a_nested_function_is_judged_by_its_own_parameters(self):
        text = ("def outer(cmd, env):\n    def inner(cmd, env=None):\n        return subprocess.run(cmd, env=env)\n"
                "    return inner(cmd)\n\n\ndef wrap(cmd, env=None):\n    def go(cmd, env):\n"
                "        return subprocess.run(cmd, env=env)\n    return go(cmd, hermetic.child_env())\n")
        with tree({"tests/x/test_a.py": text}) as root:
            got = scan.problems("E21", root)
        self.assertEqual([line.partition(": ")[0] for line in got], ["tests/x/test_a.py:3"], got)

    def test_an_env_parameter_resolved_before_the_child_is_not_caught(self):
        text = ("def run(cmd, env=None):\n    env = hermetic.child_env(**(env or {}))\n"
                "    return subprocess.run(cmd, env=env)\n\n\ndef go(cmd, env):\n    return subprocess.run(cmd, env=env)\n")
        with tree({"tests/x/test_a.py": text}) as root:
            self.assertEqual(scan.problems("E21", root), [])

    def test_a_child_given_an_env_is_not_caught(self):
        text = "done = subprocess.run(cmd, env=hermetic.child_env(A=\"1\"))\nasyncio.run(main())\n"
        with tree({"tests/x/test_a.py": text}) as root:
            self.assertEqual(scan.problems("E21", root), [])

    def test_an_assert_given_the_whole_environment_is_caught(self):
        for call in (f"self.assertNotIn('K', {ENVIRON})", f"self.assertEqual({ENVIRON}, {{}})", "self.assertIn('K', env)",
                     "self.assertNotIn('K', child_env)", "self.assertIn('K', self.env)",
                     f"self.assertTrue(ok, msg={ENVIRON})", "self.assertIn('K', names, msg=env)", "self.assertNotIn('K', container=env)",
                     "self.assertEqual(env, {'HOME': '/u'})", "self.assertDictEqual(child_env, {})"):
            with self.subTest(call=call), tree({"tests/x/test_a.py": f"x = 1\n{call}\n"}) as root:
                got = scan.problems("E21", root)
            self.assertTrue(any(line.startswith("tests/x/test_a.py:2:") for line in got), (call, got))

    def test_an_assert_that_shows_no_environment_is_not_caught(self):
        for call in (f"self.assertNotIn('K', set({ENVIRON}))", "self.assertIn('K', set(env))", "self.assertIsNone(env.get('K'))",
                     "self.assertEqual(env['HOME'], '/u')", "self.assertIn('K', env.keys())", "self.assertIn('K', names)",
                     f"self.assertEqual({ENVIRON}['K'], '1')", "self.assertEqual(env.get('HOME'), '/u')"):
            with self.subTest(call=call), tree({"tests/x/test_a.py": f"{call}\n"}) as root:
                self.assertEqual(scan.problems("E21", root), [])

    def test_patching_the_environment_in_place_is_not_a_copy(self):
        text = f'with mock.patch.dict({ENVIRON}, {{"A": "1"}}):\n    pass\n'
        with tree({"tests/x/test_a.py": text}) as root:
            self.assertEqual(scan.problems("E21", root), [])


if __name__ == "__main__":
    unittest.main()
