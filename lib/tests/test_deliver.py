"""出口の考え deliver の住処 deliver（lib/deliver.py）の口の照らし: gh の呼び口 deliver._gh、語の照らし、枝の名、host の gh の探し方、
始めの確かめ。

呼びを控えに書く偽の gh を PATH に置き（頭に読むだけの口 gh・works-gh を置く）、gh が起きたかどうかで縛る。拒みは gh を起こす前。
出口の手順そのもの（柵・commit・push・PR・読み戻し）は tests/workflows/test_merge.py の DeliverTest が、偽の gh と裸の git の remote で縛る。
"""
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import deliver  # noqa: E402


def executable(path: pathlib.Path, body: str) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class GhCallCase(unittest.TestCase):
    """PATH の頭に読むだけの口 gh と works-gh（exit 2）、その後ろに呼びを控えに書く偽の gh を置く"""

    GOOD = (
        ["api", "--hostname", "github.com", "repos/o/r"],
        ["api", "--hostname", "github.com", "repos/o/r/compare/main...abc"],
        ["api", "--hostname", "github.com", "-X", "GET", "repos/o/r/git/ref/heads/works-factory/run-1"],
        ["pr", "list", "-R", "github.com/o/r", "--head", "b", "--state", "open", "--json", "url"],
        ["pr", "create", "-R", "github.com/o/r", "-B", "main", "--head", "b", "--title", "t", "--body", "x"],
        ["pr", "view", "7", "-R", "github.com/o/r", "--json", "state"],
    )

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.log = self.tmp / "calls.log"
        self.shim = self.tmp / "shim"
        executable(self.shim / "gh", "#!/bin/sh\necho shim >> \"$GH_CALLS\"\nexit 2\n")
        executable(self.shim / "works-gh", "#!/bin/sh\nexit 2\n")
        self.real = self.tmp / "real"
        executable(self.real / "gh", "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$GH_CALLS\"\necho '{}'\n")
        path = os.pathsep.join([str(self.shim), str(self.real), os.environ.get("PATH", "")])
        patch = mock.patch.dict(os.environ, {"PATH": path, "GH_CALLS": str(self.log)})
        patch.start()
        self.addCleanup(patch.stop)

    def calls(self) -> list:
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def test_api_write_flags_are_refused(self):
        """gh api は -X・-f・-F・--field・--raw-field・--input で method が POST に変わる。-R は api に無い。VERBS の外の動詞も拒む。
        どれも gh を起こす前に拒む（控えに呼びが載らない）。api の GET（--hostname と明示のパス）・pr list・pr create・pr view は
        読むだけの口の置き場を飛ばした host の gh に届く"""
        for args in self.GOOD:
            with self.subTest(allowed=args):
                before = len(self.calls())
                self.assertEqual(deliver._gh(args).returncode, 0)
                self.assertEqual(self.calls()[before:], [" ".join(args)])
        self.assertNotIn("shim", self.calls(), "読むだけの口を通った")
        self.assertEqual(deliver.VERBS, (("api",), ("pr", "list"), ("pr", "create"), ("pr", "view")))
        allowed_calls = self.calls()
        base = ["api", "--hostname", "github.com"]
        refused = (
            [*base, "-X", "POST", "repos/o/r/issues"],
            [*base, "--method", "DELETE", "repos/o/r"],
            [*base, "--method=PATCH", "repos/o/r"],
            [*base, "-XPUT", "repos/o/r"],
            [*base, "-f", "title=x", "repos/o/r/issues"],
            [*base, "-ftitle=x", "repos/o/r/issues"],
            [*base, "-F", "n=1", "repos/o/r/issues"],
            [*base, "--field", "n=1", "repos/o/r/issues"],
            [*base, "--raw-field", "n=1", "repos/o/r/issues"],
            [*base, "--input", "body.json", "repos/o/r/issues"],
            [*base, "-R", "github.com/o/r", "repos/o/r"],
            [*base, "--repo", "github.com/o/r", "repos/o/r"],
            ["api", "repos/o/r"],
            [*base, "graphql"],
            [*base, "repos/o/r", "repos/o/other"],
            ["pr", "merge", "7", "-R", "github.com/o/r"],
            ["pr", "close", "7", "-R", "github.com/o/r"],
            ["pr", "view", "7"],
            ["repo", "delete", "o/r"],
            ["issue", "create", "-R", "github.com/o/r"],
            [],
        )
        for args in refused:
            with self.subTest(refused=args), self.assertRaises(deliver.GhRefused):
                deliver._gh(args)
        with mock.patch.dict(os.environ, {"PATH": str(self.shim)}), self.assertRaises(deliver.GhRefused) as caught:
            deliver._gh(["api", "--hostname", "github.com", "repos/o/r"])
        self.assertIn("gh", str(caught.exception), "host の gh が無い時は訳を言う")
        self.assertEqual(self.calls(), allowed_calls, "拒んだ呼びが gh を起こした")


class WordsCase(unittest.TestCase):
    def test_check_accepts_only_empty_and_pr(self):
        """空と pr は通る（前後の空白は落とす）。None は空。ほかの語は、語を名指して拒む"""
        for word, want in (("", ""), (None, ""), ("pr", "pr"), ("  pr ", "pr")):
            with self.subTest(word=word):
                self.assertEqual(deliver.check(word), want)
        for word in ("push", "PR", "merge", "pr,push", "0"):
            with self.subTest(refused=word), self.assertRaises(deliver.Refused) as caught:
                deliver.check(word)
            self.assertIn(repr(word), str(caught.exception))

    def test_refused_is_null_only_when_nothing_was_asked(self):
        """空の語（Archon の飛んだ値 null も）は null。pr も知らない語も頼まれた扱いで、枝・commit・URL の空い delivered に訳を載せる"""
        for word in ("", None, "null", " "):
            with self.subTest(word=word):
                self.assertIsNone(deliver.refused(word, "x"))
        for word in ("pr", "push"):
            with self.subTest(asked=word):
                self.assertEqual(deliver.refused(word, "差分が空"),
                                 {"ok": False, "branch": "", "commit": "", "url": "", "reason": "差分を置かなかったので提出しない: 差分が空"})


class BranchCase(unittest.TestCase):
    def test_branch_of_is_fixed_prefix(self):
        """押す先の枝は、固定の接頭辞と実行の id だけで組む。枝の名・gh のパスに載せられない字の id は拒む"""
        self.assertEqual(deliver.BRANCH_PREFIX, "works-factory/run-")
        self.assertEqual(deliver.branch_of("53b2e825-14cb"), "works-factory/run-53b2e825-14cb")
        for bad in ("", "../x", "a b", "a/b", "-x", "a\nb", None, 7):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                deliver.branch_of(bad)


class HostGhCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name).resolve()

    def test_skips_the_read_only_gate_directory(self):
        """works-gh の在る置き場の gh は読むだけの口なので飛ばし、その次の置き場の gh を返す。実行できない gh・相対の置き場・gh の無い置き場も飛ばす"""
        gate = self.tmp / "gate"
        host = self.tmp / "host"
        plain = self.tmp / "plain"
        executable(gate / "gh", "#!/bin/sh\nexit 2\n")
        executable(gate / "works-gh", "#!/bin/sh\nexit 2\n")
        executable(host / "gh", "#!/bin/sh\nexit 0\n")
        plain.mkdir()
        (plain / "gh").write_text("not executable", encoding="utf-8")
        path = os.pathsep.join(["", "relative", str(plain), str(self.tmp / "none"), str(gate), str(host)])
        self.assertEqual(deliver.host_gh(path), str(host / "gh"))
        self.assertIsNone(deliver.host_gh(os.pathsep.join([str(gate), str(plain)])))
        self.assertIsNone(deliver.host_gh(""))
        self.assertIsNone(deliver.host_gh(None))


class PreflightCase(unittest.TestCase):
    """始めの確かめ。対象は github.com の https URL の origin を持つ git の木。gh api の答えは偽の gh が返す"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name).resolve()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git = ["git", "-C", str(self.repo)]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "remote", "add", "origin", "https://github.com/o/r.git"], check=True)
        self.shim = self.tmp / "bin"

    def with_gh(self, body: str):
        executable(self.shim / "gh", f"#!/bin/sh\n{body}\n")
        patch = mock.patch.dict(os.environ, {"PATH": os.pathsep.join([str(self.shim), os.environ.get("PATH", "")])})
        patch.start()
        self.addCleanup(patch.stop)

    def test_refuses_without_push_permission(self):
        """push の権限が偽なら、リポジトリを名指して拒む。真なら通る（空の訳）。GitHub でない remote と gh が無い時もそれぞれの訳で拒む"""
        self.with_gh("echo '{\"permissions\": {\"push\": false}}'")
        why = deliver.preflight(self.repo)
        self.assertIn("github.com/o/r", why)
        self.assertIn("push", why)
        self.with_gh("echo '{\"permissions\": {\"push\": true}}'")
        self.assertEqual(deliver.preflight(self.repo), "")
        self.with_gh("echo 'HTTP 404: Not Found' >&2; exit 1")
        self.assertIn("exit 1", deliver.preflight(self.repo))
        subprocess.run(["git", "-C", str(self.repo), "remote", "set-url", "origin", str(self.tmp / "bare")], check=True)
        self.assertIn("no_forge", deliver.preflight(self.repo))


if __name__ == "__main__":
    unittest.main()
