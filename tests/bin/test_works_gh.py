"""読むだけの gh の口（bin/_lib/no-post-bin/works-gh）の検査。

- 通すのは pr list・pr view・pr diff・issue view（-R 付き）と repo view <OWNER/REPO>、api は PR の行コメントを読む 1 つの形
  （[--paginate] [--hostname <host>] repos/<OWNER>/<REPO>/pulls/<番号>/comments）だけ。ほかの形（書く命令・api の -X・-f・--input
  など・auth token）と -w・--web は本物の gh を起こさずに 2
- 口は本物の gh を起こす前に WORKS_FACTORY_GH_ACTIVE を立て、それが立った env で口に入れば拒む（読む側と立てる側の名を
  1 つの試験で縛る。片側だけ名を替えると輪の断ち方が黙って外れる）

偽の gh（受けた引数と WORKS_FACTORY_GH_ACTIVE を記録する）を口の後ろの PATH に置く。本物の gh・GitHub に触れない。
"""
import os
import pathlib
import subprocess
import sys
import unittest

TESTS = pathlib.Path(__file__).resolve().parent
WORKS_GH = TESTS.parents[1] / "bin" / "_lib" / "no-post-bin" / "works-gh"
sys.dont_write_bytecode = True
sys.path.insert(0, str(TESTS))

import hermetic  # noqa: E402

COMMENTS = "repos/o/r/pulls/7/comments"
ALLOWED = (["pr", "list", "-R", "o/r"], ["pr", "view", "1", "-R", "o/r"], ["pr", "diff", "br", "--repo=o/r"],
           ["pr", "view", "1", "--repo", "github.com/o/r"], ["repo", "view", "o/r"], ["issue", "view", "1", "-R", "o/r"],
           ["api", "--paginate", "--hostname", "github.com", COMMENTS], ["api", "--paginate", COMMENTS],
           ["api", "--hostname=ghe.corp.example", COMMENTS])
REFUSED = (["pr", "create", "-R", "o/r"], ["pr", "merge", "1", "-R", "o/r"], ["pr", "comment", "1", "-R", "o/r"],
           ["api", "repos/o/r"], ["issue", "view", "1"], ["issue", "create", "-R", "o/r"], ["issue", "comment", "1", "-R", "o/r"],
           ["pr", "view", "1"], ["repo", "view"], ["pr", "view", "1", "-R", "o/r", "-w"], ["pr", "list", "-R", "o/r", "--web"],
           ["repo", "view", "o/r", "--web"], ["issue", "view", "1", "-R", "o/r", "--web"], [], ["api"],
           ["api", "-X", "POST", COMMENTS], ["api", "--method=POST", COMMENTS], ["api", "--method", "GET", COMMENTS],
           ["api", COMMENTS, "-f", "body=x"], ["api", COMMENTS, "-F", "body=x"], ["api", COMMENTS, "--raw-field", "body=x"],
           ["api", "--input", "f", COMMENTS], ["api", "-H", "X: y", COMMENTS], ["api", "graphql", "-f", "query=x"],
           ["api", "repos/{owner}/{repo}/pulls/7/comments"], ["api", COMMENTS, "repos/o/r/issues"],
           ["api", COMMENTS + "?per_page=1"], ["api", "--hostname", COMMENTS], ["api", "--hostname", "a/b", COMMENTS],
           ["api", "--paginate", "--paginate", COMMENTS], ["auth", "token"], ["auth", "status", "--show-token"])


class WorksGhCase(unittest.TestCase):
    def setUp(self):
        self.tmp = hermetic.tmpdir(self)
        self.log = self.tmp / "gh.txt"
        bindir = self.tmp / "bin"
        bindir.mkdir()
        gh = bindir / "gh"
        gh.write_text(f'#!/bin/sh\nprintf \'%s|%s\\n\' "${{WORKS_FACTORY_GH_ACTIVE-(unset)}}" "$*" >> "{self.log}"\n',
                      encoding="utf-8")
        gh.chmod(0o755)
        self.path = os.pathsep.join([str(WORKS_GH.parent), str(bindir), os.environ.get("PATH", "")])

    def run_gate(self, args, **env):
        return subprocess.run([sys.executable, str(WORKS_GH), *args], capture_output=True, text=True, encoding="utf-8",
                              env=hermetic.child_env(PATH=self.path, **env), timeout=60)

    def gh_calls(self):
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def test_allowed_forms_reach_the_real_gh_with_the_guard_set(self):
        for args in ALLOWED:
            with self.subTest(args=args):
                self.log.unlink(missing_ok=True)
                r = self.run_gate(args)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(self.gh_calls(), ["1|" + " ".join(args)])

    def test_other_forms_and_web_are_refused_without_the_real_gh(self):
        for args in REFUSED:
            with self.subTest(args=args):
                r = self.run_gate(args)
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertTrue(r.stderr.startswith("works-gh: 通さない"), r.stderr)
        self.assertEqual(self.gh_calls(), [])

    def test_re_entry_with_the_guard_set_is_refused(self):
        r = self.run_gate(["pr", "view", "1", "-R", "o/r"], WORKS_FACTORY_GH_ACTIVE="1")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("起こし直された", r.stderr)
        self.assertEqual(self.gh_calls(), [])


if __name__ == "__main__":
    unittest.main()
