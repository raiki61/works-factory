"""読むだけの gh の口（bin/_lib/no-post-bin/works-gh）の検査。

- 通すのは pr list・pr view・pr diff・issue view（サブコマンドの直後に -R）と repo view <OWNER/REPO>、api は PR の行コメントを読む 1 つの形
  （[--paginate] [--hostname <host>] repos/<OWNER>/<REPO>/pulls/<番号>/comments）だけ。ほかの形（書く命令・api の -X・-f・--input
  など・auth token）と -w・--web は本物の gh を起こさずに 2
- -R・--repo はサブコマンドの直後の 1 つだけ（-R X・-RX・-R=X・--repo X・--repo=X）。ほかの位置に -R を含む語（--repo…・R を
  含む短い旗の束）が在れば拒む。後ろの -R は、前に値を取る旗が在ると pflag がその値として食べ（-t -R o/r・1 -qRo/r）、-- の
  後ろでは位置の引数になり、gh は手元の git の remote から repo を決める（remote は hosts.yml の全部のホストで絞られ、別の
  ホストへ繋ぎうる）。2 つ在れば gh は最後の値を読む
- 直後の短い旗の束の R の値は、R の後ろが空なら次の語、空でなければ残り（pflag の読み方。-Revil.example/o/R o/r は
  evil.example/o/R を読むので拒む）
- repo view は位置の引数がちょうど 1 つで、旗は --json（値は次の語か = の後ろ）だけ。-b・-t・-q など値を取る旗の値の語を
  位置の引数と数えると、-b o/r evil.example/o/r の o/r を照らし、gh は evil.example/o/r を読む
- 読むホストは github.com・<名>.ghe.com・GH_HOST・GH_REPO のホストだけ（-R・--hostname・URL の引数。gh は GH_ENTERPRISE_TOKEN を
  github.com の外のどのホストにも付けるので、ほかのホストへトークンを送らない）
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

from tests.bin import hermetic  # noqa: E402

COMMENTS = "repos/o/r/pulls/7/comments"
ALLOWED = (["pr", "list", "-R", "o/r"], ["pr", "view", "-R", "o/r", "1"], ["pr", "diff", "--repo=o/r", "br"],
           ["pr", "view", "--repo", "github.com/o/r", "1"], ["repo", "view", "o/r"], ["issue", "view", "-R", "o/r", "1"],
           ["api", "--paginate", "--hostname", "github.com", COMMENTS], ["api", "--paginate", COMMENTS],
           ["api", "--hostname=acme.ghe.com", COMMENTS], ["pr", "view", "-R", "acme.ghe.com/o/r", "1"],
           ["pr", "view", "-R", "o/r", "https://github.com/o/r/pull/1"], ["pr", "view", "-R", "o/r", "1", "-c"],
           ["pr", "view", "-Ro/r", "1"], ["pr", "view", "-R=o/r", "1", "--json", "number"], ["repo", "view", "o/r", "--json", "name,url"], ["repo", "view", "--json=name", "o/r"])
REFUSED = (["pr", "create", "-R", "o/r"], ["pr", "merge", "1", "-R", "o/r"], ["pr", "comment", "1", "-R", "o/r"],
           ["api", "repos/o/r"], ["issue", "view", "1"], ["issue", "create", "-R", "o/r"], ["issue", "comment", "1", "-R", "o/r"],
           ["pr", "view", "1"], ["repo", "view"], ["pr", "view", "-R", "o/r", "1", "-w"], ["pr", "list", "-R", "o/r", "--web"],
           ["repo", "view", "o/r", "--web"], ["issue", "view", "-R", "o/r", "1", "--web"], [], ["api"],
           ["api", "-X", "POST", COMMENTS], ["api", "--method=POST", COMMENTS], ["api", "--method", "GET", COMMENTS],
           ["api", COMMENTS, "-f", "body=x"], ["api", COMMENTS, "-F", "body=x"], ["api", COMMENTS, "--raw-field", "body=x"],
           ["api", "--input", "f", COMMENTS], ["api", "-H", "X: y", COMMENTS], ["api", "graphql", "-f", "query=x"],
           ["api", "repos/{owner}/{repo}/pulls/7/comments"], ["api", COMMENTS, "repos/o/r/issues"],
           ["api", COMMENTS + "?per_page=1"], ["api", "--hostname", COMMENTS], ["api", "--hostname", "a/b", COMMENTS],
           ["api", "--paginate", "--paginate", COMMENTS], ["auth", "token"], ["auth", "status", "--show-token"],
           ["pr", "view", "-R", "o/r", "1", "--repo", "x/y"], ["pr", "diff", "-R", "o/r", "1", "-R", "o/r"],
           ["issue", "view", "-Ro/r", "1", "--repo=x/y"], ["api", "--hostname", "-XPOST", COMMENTS],
           ["api", "--hostname", "evil.example", COMMENTS], ["pr", "view", "-R", "evil.example/o/r", "1"],
           ["repo", "view", "evil.example/o/r"], ["pr", "view", "-R", "o/r", "https://evil.example/o/r/pull/1"],
           ["pr", "view", "-R", "o/r", "1", "-cR", "x/y"], ["pr", "view", "-R=o/r", "1", "-cRx/y"],
           ["pr", "view", "-R", "o/r", "http://[x"], ["pr", "view", "-R"],
           ["pr", "view", "-Revil.example/o/R", "o/r"], ["pr", "diff", "-cRevil.example/o/R", "o/r"],
           # 直後でない -R は、前の値を取る旗が食べるか -- の後ろの位置の引数になり、gh は手元の git の remote から repo を決める
           ["pr", "view", "1", "-R", "o/r"], ["pr", "view", "1", "-cRo/r"], ["pr", "view", "1", "-c", "-R", "o/r"],
           ["pr", "view", "1", "--json", "number", "-qRo/r"], ["pr", "view", "--json", "number", "-t", "-R", "o/r"],
           ["pr", "view", "--jq", "-R", "o/r"], ["pr", "diff", "--", "-Ro/r"], ["issue", "view", "1", "--json", "number", "-qRo/r"],
           ["pr", "view", "-R", "o/r", "--jq", "-R", "x/y"], ["pr", "diff", "-R", "o/r", "1", "--", "-Rx/y"],
           ["pr", "list", "-cR", "o/r"], ["pr", "list", "-qRo/r"],
           ["repo", "view", "-b", "o/r", "evil.example/o/r"], ["repo", "view", "-b", "o/r", "git@evil.example:o/r"],
           ["repo", "view", "-t", "o/r", "evil.example/o/r"], ["repo", "view", "--jq=x", "o/r"], ["repo", "view", "o/r", "x/y"],
           ["repo", "view", "--", "evil.example/o/r"], ["repo", "view", "--json", "name"])
# GH_HOST か GH_REPO が名指した時だけ通るホスト
CORP = (["api", "--hostname=ghe.corp.example", COMMENTS], ["pr", "view", "-R", "ghe.corp.example/o/r", "1"],
        ["issue", "view", "-R", "GHE.corp.example/o/r", "1"])


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
        child = {k: v for k, v in hermetic.child_env(PATH=self.path).items() if k not in ("GH_HOST", "GH_REPO")}
        return subprocess.run([sys.executable, str(WORKS_GH), *args], capture_output=True, text=True, encoding="utf-8",
                              env={**child, **env}, timeout=60)

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

    def test_hosts_named_by_gh_host_or_gh_repo_pass(self):
        for env in ({}, {"GH_HOST": "other.example"}, {"GH_REPO": "o/r"}):
            for args in CORP:
                with self.subTest(env=env, args=args):
                    self.assertEqual(self.run_gate(args, **env).returncode, 2)
        self.assertEqual(self.gh_calls(), [])
        for env in ({"GH_HOST": "GHE.corp.example"}, {"GH_REPO": "ghe.corp.example/o/r"}):
            for args in CORP:
                with self.subTest(env=env, args=args):
                    self.log.unlink(missing_ok=True)
                    r = self.run_gate(args, **env)
                    self.assertEqual(r.returncode, 0, r.stderr)
                    self.assertEqual(self.gh_calls(), ["1|" + " ".join(args)])

    def test_re_entry_with_the_guard_set_is_refused(self):
        r = self.run_gate(["pr", "view", "-R", "o/r", "1"], WORKS_FACTORY_GH_ACTIVE="1")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("起こし直された", r.stderr)
        self.assertEqual(self.gh_calls(), [])


if __name__ == "__main__":
    unittest.main()
