"""名指した PR・issue を run の中で読む部品（.shared/core/ghreads.py の read_named）と、線の入口がそれを使う所の検査（設計書 2.8）。

gh は偽物（fake_gh）。偽の gh は、利用者のログイン（GH_CONFIG_DIR・$XDG_CONFIG_HOME/gh・$HOME/.config/gh の hosts.yml）が
見える時だけ非公開の中身を返し、見えない時は本物と同じく exit 4 で終わる。run の中の gh は開発の殻（dev/hostgh.py の口）が
利用者のログインを継がせるので、「ログインが見えれば載り、見えなければ読めないと記録する」を本物の GitHub に触れずに縛れる。

- read_named: 名指した PR の本文・コメント・レビュー・行コメントと issue の本文・コメントを、cwd＝対象の根で 1 回だけ読む。
  読めない項は status unreadable で残す
- 線の入口: entry.check_inputs は gh を呼ばず、渡された読み出しの base・head を読む。entry.start は名指しを run の中で読んで
  盤面の根の github.json に置き、再開では盤面の写しを使う。WORKS_DEV_NO_AUTH=1 の run（利用者の gh を継がない）は 1 行で拒む
- ラインは読み出しのファイルを受けない（入力 github_reads は無い）
"""
import contextlib
import json
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

import ghreads  # noqa: E402

GHREADS = LIB / "ghreads.py"
GH_ENV = ("GH_CONFIG_DIR", "XDG_CONFIG_HOME", "GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN",
          "GH_REPO", "GH_HOST", "WORKS_FACTORY_GH_ACTIVE")
# run の中で PATH の頭に在る読むだけの口（works-gh）の置き場。lib/ は bin/ を import しない（パスの字だけを使う）
READ_ONLY_GH = LIB.parent / "bin" / "_lib" / "no-post-bin"


def fake_gh(tmp: pathlib.Path, *, base="b" * 40, head="h" * 40):
    """偽の gh を tmp/gh-bin に置き、(bin のフォルダ, 呼び出しの記録, 利用者のログインのフォルダ) を返す。
    記録は 1 行 1 呼び出しで「cwd<TAB>引数」。ログインのフォルダ（hosts.yml 入り）を GH_CONFIG_DIR に置いた時だけ中身を返す"""
    data = tmp / "gh-data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "pr-7.json").write_text(json.dumps({
        "baseRefOid": base, "headRefOid": head, "title": "非公開の題", "body": "非公開の本文",
        "comments": [{"author": {"login": "a"}, "body": "非公開のコメント"}],
        "reviews": [{"author": {"login": "b"}, "body": "非公開のレビュー", "state": "COMMENTED"}]}, ensure_ascii=False))
    (data / "review-comments-7.json").write_text(json.dumps([{"path": "stats.py", "line": 1, "body": "非公開の行コメント"}],
                                                            ensure_ascii=False))
    (data / "issue-9.json").write_text(json.dumps({"title": "課題の題", "body": "課題の本文",
                                                   "comments": [{"body": "課題のコメント"}]}, ensure_ascii=False))
    login = tmp / "user-gh"
    login.mkdir(exist_ok=True)
    (login / "hosts.yml").write_text("github.com:\n    user: someone\n", encoding="utf-8")
    bin_ = tmp / "gh-bin"
    bin_.mkdir(exist_ok=True)
    calls = tmp / "gh-calls.txt"
    gh = bin_ / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        f'printf \'%s\\t%s\\n\' "$(pwd -P)" "$*" >> "{calls}"\n'
        'if [ -n "${GH_CONFIG_DIR:-}" ]; then conf="$GH_CONFIG_DIR"\n'
        'elif [ -n "${XDG_CONFIG_HOME:-}" ]; then conf="$XDG_CONFIG_HOME/gh"\n'
        'else conf="${HOME:-/nonexistent}/.config/gh"; fi\n'
        'if [ ! -f "$conf/hosts.yml" ]; then\n'
        '  echo "To get started with GitHub CLI, please run:  gh auth login" >&2\n'
        "  exit 4\n"
        "fi\n"
        'case "$1" in\n'
        f'  pr) f="{data}/pr-$3.json" ;;\n'
        f'  issue) f="{data}/issue-$3.json" ;;\n'
        f'  api) n="$(printf \'%s\\n\' "$*" | sed -n \'s#.*pulls/\\([0-9]*\\)/comments.*#\\1#p\')"; f="{data}/review-comments-$n.json" ;;\n'
        '  *) f="" ;;\n'
        "esac\n"
        'if [ -z "$f" ] || [ ! -f "$f" ]; then echo "GraphQL: Could not resolve to a PullRequest" >&2; exit 1; fi\n'
        'cat "$f"\n',
        encoding="utf-8")
    gh.chmod(0o755)
    return bin_, calls, login


def gh_calls(calls: pathlib.Path):
    return [line.split("\t", 1) for line in calls.read_text(encoding="utf-8").splitlines()] if calls.exists() else []


class ReadNamedCase(unittest.TestCase):
    """ghreads.read_named を、run の中と同じく読むだけの口 works-gh を PATH の頭に、その後ろに偽の gh を置いて同じプロセスで呼ぶ"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        # 対象は GitHub の remote を持つ（forge の在る対象。forge の無い対象で gh が読めなかった項は条件外と書く: test_forge）
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.repo), "remote", "add", "origin", "git@github.com:o/r.git"], check=True,
                       capture_output=True)
        self.bin, self.calls, self.login = fake_gh(self.tmp)

    def read(self, prs, issues, logged_in=True, **extra):
        env = {name: None for name in GH_ENV}
        env.update(PATH=os.pathsep.join([str(READ_ONLY_GH), str(self.bin), os.environ.get("PATH", "")]),
                   HOME=str(self.tmp / "home"))
        env.update(extra)
        if logged_in:
            env["GH_CONFIG_DIR"] = str(self.login)
        with gh_env(env):
            return ghreads.read_named(self.repo, prs, issues)

    def test_reads_named_pr_and_issue_with_user_login(self):
        """利用者のログインが見える env で、名指した PR の本文・コメント・レビュー・行コメントと issue の本文・コメントが載る。
        gh は対象の根を cwd にして、読むだけの口が通す形（-R <OWNER/REPO>・api --paginate --hostname の 1 つのパス）で呼ぶ"""
        doc = self.read([7], [9])
        self.assertEqual(doc["version"], ghreads.GITHUB_READS_VERSION)
        pr = doc["pr"]["7"]
        self.assertEqual((pr["title"], pr["body"]), ("非公開の題", "非公開の本文"))
        self.assertEqual((pr["baseRefOid"], pr["headRefOid"]), ("b" * 40, "h" * 40))
        self.assertEqual([c["body"] for c in pr["comments"]], ["非公開のコメント"])
        self.assertEqual([c["body"] for c in pr["reviews"]], ["非公開のレビュー"])
        self.assertEqual([c["body"] for c in pr["review_comments"]], ["非公開の行コメント"])
        self.assertEqual(pr["status"], "ok")
        issue = doc["issue"]["9"]
        self.assertEqual((issue["title"], issue["body"]), ("課題の題", "課題の本文"))
        self.assertEqual([c["body"] for c in issue["comments"]], ["課題のコメント"])
        calls = gh_calls(self.calls)
        self.assertTrue(calls)
        self.assertEqual({cwd for cwd, _ in calls}, {str(self.repo)})
        self.assertEqual(sorted(a.split(" --json")[0] for _, a in calls),
                         ["api --paginate --hostname github.com repos/o/r/pulls/7/comments", "issue view 9 -R github.com/o/r",
                          "pr view 7 -R github.com/o/r"])

    def remote(self, name, url, *, add=False):
        subprocess.run(["git", "-C", str(self.repo), "remote", "add" if add else "set-url", name, url], check=True,
                       capture_output=True)

    def targets(self):
        """記録した呼び出しの -R の値と api のパスの組（呼び出しの順）"""
        got = []
        for _, args in gh_calls(self.calls):
            a = args.split()
            got.append(a[a.index("-R") + 1] if "-R" in a else " ".join(a[a.index("--hostname") + 1:]))
        return got

    def test_gh_repo_names_the_target(self):
        """GH_REPO が在れば remote に依らずそれを名指す（gh 自身と同じく remote より先）"""
        doc = self.read([7], [9], GH_REPO="other/x")
        self.assertEqual((doc["pr"]["7"]["status"], doc["issue"]["9"]["status"]), ("ok", "ok"))
        self.assertEqual(self.targets(), ["github.com/other/x", "github.com repos/other/x/pulls/7/comments",
                                          "github.com/other/x"])

    def test_gh_repo_without_host_takes_gh_host(self):
        """HOST の無い GH_REPO は gh 自身と同じく GH_HOST のホストの名（-R と api の --hostname が同じホストを読む）"""
        self.read([7], [], GH_REPO="o/r", GH_HOST="ghe.corp.example")
        self.assertEqual(self.targets(), ["ghe.corp.example/o/r", "ghe.corp.example repos/o/r/pulls/7/comments"])

    def test_gh_host_with_github_remote_names_github_in_both_reads(self):
        """GH_HOST を立てても GitHub の remote を読むなら、-R も api の --hostname も github.com（-R を o/r にすると gh は
        GH_HOST で解き、本文と行コメントが別のホストから来る）"""
        self.read([7], [], GH_HOST="ghe.corp.example")
        self.assertEqual(self.targets(), ["github.com/o/r", "github.com repos/o/r/pulls/7/comments"])

    def test_gh_repo_with_host(self):
        self.read([7], [], GH_REPO="ghe.corp.example/o/r")
        self.assertEqual(self.targets(), ["ghe.corp.example/o/r", "ghe.corp.example repos/o/r/pulls/7/comments"])

    def test_edge_names_pass_the_read_only_gh(self):
        """forge.SEGMENT・forge.HOST が通す名の端（点・下線・大文字の owner・ホストの数字とハイフン）を works-gh の名の形も通す"""
        doc = self.read([7], [9], GH_REPO="ghe-2.corp.example/Up.Org_1/my_repo.js-x")
        self.assertEqual((doc["pr"]["7"]["status"], doc["issue"]["9"]["status"]), ("ok", "ok"))

    def test_malformed_gh_repo_is_unreadable_without_gh(self):
        doc = self.read([7], [9], GH_REPO="a/b/c/d")
        for got in (doc["pr"]["7"], doc["issue"]["9"]):
            self.assertEqual(got["status"], "unreadable")
            self.assertIn("GH_REPO", got["reason"])
        self.assertEqual(gh_calls(self.calls), [])

    def test_undecided_target_is_left_to_gh(self):
        """GitHub の URL も GH_HOST のホストも無い remote では、読む先を gh に決めさせる打ち方（-R 無し）で gh を起こす（自前の
        ドメインの GHES は gh が hosts.yml で読める）。run の中ではそれを読むだけの口が拒み、項は口の言葉で unreadable"""
        self.remote("origin", "https://ghe.example.com/o/r.git")
        doc = self.read([7], [9], PATH=os.pathsep.join([str(self.bin), os.environ.get("PATH", "")]))
        self.assertEqual((doc["pr"]["7"]["status"], doc["issue"]["9"]["status"]), ("ok", "ok"))
        self.assertEqual(sorted(a.split(" --json")[0] for _, a in gh_calls(self.calls)),
                         ["api --paginate repos/{owner}/{repo}/pulls/7/comments", "issue view 9", "pr view 7"])
        self.calls.unlink()
        doc = self.read([7], [9])
        for got in (doc["pr"]["7"], doc["issue"]["9"]):
            self.assertEqual(got["status"], "unreadable")
            self.assertIn("works-gh", got["reason"])
            self.assertTrue(got["forge"].startswith("no_forge: other_host"), got)
        self.assertEqual(gh_calls(self.calls), [])

    def test_gh_host_reads_a_custom_domain_host(self):
        """GH_HOST が remote のホストを名指せば（自前のドメインの GitHub Enterprise Server）、そのホストで読む"""
        self.remote("origin", "https://gitlab.example/o/r.git")
        doc = self.read([7], [], GH_HOST="GitLab.example")
        self.assertEqual(doc["pr"]["7"]["status"], "ok")
        self.assertEqual(self.targets(), ["gitlab.example/o/r", "gitlab.example repos/o/r/pulls/7/comments"])

    def test_another_remote_on_github_is_read(self):
        """origin がローカルのパスでも、別の remote が GitHub を指せばそれを読む"""
        self.remote("origin", str(self.tmp / "origin.git"))
        self.remote("upstream", "git@github.com:up/r.git", add=True)
        doc = self.read([], [9])
        self.assertEqual(doc["issue"]["9"]["status"], "ok")
        self.assertEqual(self.targets(), ["github.com/up/r"])

    def test_tracking_remote_wins_over_upstream(self):
        """set-default が無ければ、forge.detect の選んだ remote（枝の追う remote）を upstream・github・origin より先に読む"""
        self.remote("origin", "git@github.com:me/r.git")
        self.remote("upstream", "git@github.com:up/r.git", add=True)
        self.remote("mine", "git@github.com:mine/r.git", add=True)
        git = ["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "x"], check=True, capture_output=True)
        subprocess.run([*git, "update-ref", "refs/remotes/mine/main", "HEAD"], check=True, capture_output=True)
        subprocess.run([*git, "branch", "-q", "--set-upstream-to=mine/main"], check=True, capture_output=True)
        self.read([], [9])
        self.assertEqual(self.targets(), ["github.com/mine/r"])

    def test_gh_resolved_default_wins(self):
        """gh repo set-default の remote（remote.<名>.gh-resolved = base）を先に選ぶ（gh 自身と同じ）"""
        self.remote("fork", "git@github.com:me/r.git", add=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "remote.fork.gh-resolved", "base"], check=True,
                       capture_output=True)
        self.read([], [9])
        self.assertEqual(self.targets(), ["github.com/me/r"])

    def test_gh_resolved_names_the_repo(self):
        """set-default が OWNER/REPO を記した remote（フォークの clone で親を名指した）は、その名をその remote のホストで読む"""
        self.remote("origin", "git@github.com:me/r.git")
        subprocess.run(["git", "-C", str(self.repo), "config", "remote.origin.gh-resolved", "up/r"], check=True,
                       capture_output=True)
        self.read([7], [])
        self.assertEqual(self.targets(), ["github.com/up/r", "github.com repos/up/r/pulls/7/comments"])

    def test_nothing_named_calls_nothing(self):
        self.remote("origin", "https://gitlab.example/o/r.git")
        self.assertEqual(self.read([], []), {"version": ghreads.GITHUB_READS_VERSION, "pr": {}, "issue": {}})
        self.assertEqual(gh_calls(self.calls), [])

    def test_without_login_marks_unreadable(self):
        """利用者のログインが見えない（gh は exit 4）と、名指した項に status unreadable と 1 行の理由を残す（止めない）"""
        doc = self.read([7], [9], logged_in=False)
        for got in (doc["pr"]["7"], doc["issue"]["9"]):
            self.assertEqual(got["status"], "unreadable")
            self.assertEqual(set(got), {"status", "reason"})   # forge の在る対象: 欄 forge も内側の印 _no_host も無い
            self.assertTrue(got["reason"].strip())
            self.assertNotIn("\n", got["reason"])
        self.assertNotIn("非公開", json.dumps(doc, ensure_ascii=False))

    def test_file_reading_entry_is_gone(self):
        """隔離の前に読んでファイルで渡す口（read の CLI・load・adopt・discard_source）は無い"""
        for name in ("read", "load", "adopt", "discard_source", "DiscardFailed"):
            self.assertFalse(hasattr(ghreads, name), name)
        r = subprocess.run([sys.executable, "-I", str(GHREADS), "read", "--repo", str(self.repo), "--out", str(self.tmp / "x")],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.tmp / "x").exists())


@contextlib.contextmanager
def gh_env(values):
    """os.environ に values を置く（None の名は外す）。抜ける時に元へ戻す"""
    saved = {k: os.environ.get(k) for k in values}
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class WriteCase(unittest.TestCase):
    """ghreads._write は非公開の本文を持つ読み出し（盤面の github.json。ghreads.place）を、umask に依らず所有者だけの権限
    （0600）で置き、書き込みが落ちても一時のファイルを残さない"""

    DOC = {"version": 1, "pr": {"7": {"baseRefOid": "b" * 40, "headRefOid": "h" * 40, "body": "非公開の本文"}}, "issue": {}}

    def test_write_is_owner_only_even_under_open_umask(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            out = pathlib.Path(tmp_str) / "reads" / "x.json"
            old = os.umask(0)
            try:
                ghreads._write(out, self.DOC)
            finally:
                os.umask(old)
            self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8")), self.DOC)

    def test_write_replaces_loose_tmp_and_out_with_owner_only(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = pathlib.Path(tmp_str)
            out = tmp / "x.json"
            out.write_text("{}", encoding="utf-8")
            out.chmod(0o644)
            leftover = tmp / f".{out.name}.{os.getpid()}.tmp"
            leftover.write_text("前の回の残り", encoding="utf-8")
            leftover.chmod(0o666)
            ghreads._write(out, self.DOC)
            self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8")), self.DOC)
            self.assertEqual(sorted(p.name for p in tmp.iterdir()), ["x.json"])

    def test_write_failure_leaves_no_tmp(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = pathlib.Path(tmp_str)
            out = tmp / "x.json"
            with mock.patch.object(ghreads.os, "replace", side_effect=OSError("boom")):
                with self.assertRaises(OSError):
                    ghreads._write(out, self.DOC)
            self.assertEqual(sorted(p.name for p in tmp.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
