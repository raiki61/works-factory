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
GH_ENV = ("GH_CONFIG_DIR", "XDG_CONFIG_HOME", "GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")


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
    """ghreads.read_named を、偽の gh を PATH の頭に置いて同じプロセスで呼ぶ"""

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

    def read(self, prs, issues, logged_in=True):
        env = {name: None for name in GH_ENV}
        env.update(PATH=f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}", HOME=str(self.tmp / "home"))
        if logged_in:
            env["GH_CONFIG_DIR"] = str(self.login)
        with gh_env(env):
            return ghreads.read_named(self.repo, prs, issues)

    def test_reads_named_pr_and_issue_with_user_login(self):
        """利用者のログインが見える env で、名指した PR の本文・コメント・レビュー・行コメントと issue の本文・コメントが載る。
        gh は対象の根を cwd にして呼び、行コメントは gh api --paginate の {owner}/{repo} で引く"""
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
        self.assertTrue(any("repos/{owner}/{repo}/pulls/7/comments" in a and "--paginate" in a for _, a in calls), calls)

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
