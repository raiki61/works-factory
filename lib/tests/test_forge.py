"""対象の remote が forge（PR を持つホスト。今は GitHub）かを git だけで決める口（.shared/core/forge.py）と、その決めを盤面へ
写す works の差し替え（entry.CORE_OVERRIDES の on_init・parallel_pr_due・fill_materials）の検査。

canary の run 5318f732 の事実: origin がローカルの bare リポジトリの run で、並行 PR の任せ先の役が素材 parallel_pr を
awaiting_human と書き、判定が問いの台帳に保留の問いを置いて、直しが済みテストも緑なのに結末が round_limit になった（同じ形の
run 1・2 は役が clean と書いて通った——役の判断で割れていた）。forge の無い remote（origin が無い・ローカルのパス・GitHub で
ないホスト）は機械が決めて並行 PR の節を条件外（not_applicable・reason は no_forge: <種類>）にし、役に聞かない。
GitHub の remote で gh が無い・未ログイン・API が落ちた時は今どおり（確かめる物が在るのに確かめられなかった）。

関数を直に呼ぶ・一時の置き場で git init と remote add を起こすだけ（盤面・子の実行器なし）。
"""
import pathlib
import subprocess
import sys
import tempfile
import unittest

from tests.bin.gitkit import GIT_ID

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import forge  # noqa: E402
from tests.bin import hermetic  # noqa: E402

SECRET = "ghp_SECRETVALUE"


def _git(repo, *args):
    subprocess.run(["git", *GIT_ID, "-C", str(repo), *args], check=True, capture_output=True, env=hermetic.child_env())


class ClassifyCase(unittest.TestCase):
    """URL の形から forge の種類を決める（GitHub か・forge でない 3 つの種類のどれか）"""

    def test_github_forms(self):
        for url in ("https://github.com/o/r.git", "https://github.com/o/r", "git@github.com:o/r.git",
                    "ssh://git@github.com/o/r.git", "ssh://git@ssh.github.com:443/o/r.git", "https://GitHub.com/o/r",
                    f"https://x-access-token:{SECRET}@github.com/o/r.git", "git://github.com/o/r.git",
                    "https://acme.ghe.com/o/r.git", "git@github.com-work:o/r.git", "ssh://git@github.com-work/o/r.git"):
            with self.subTest(url):
                self.assertEqual(forge.classify(url)["kind"], forge.GITHUB)

    def test_local_paths(self):
        for url in ("/home/x/canary/origin.git", "../origin.git", "origin.git", "file:///tmp/o.git", "file:/tmp/o.git",
                    "C:\\work\\o.git", "C:/work/o.git", "~/o.git"):
            with self.subTest(url):
                self.assertEqual(forge.classify(url)["kind"], forge.LOCAL_PATH)

    def test_other_hosts(self):
        for url, host in (("https://gitlab.com/o/r.git", "gitlab.com"), ("git@gitlab.example.com:o/r.git", "gitlab.example.com"),
                          ("ssh://git@git.example.com:2222/o/r.git", "git.example.com"),
                          ("https://bitbucket.org/o/r", "bitbucket.org"), ("https://notgithub.com/o/r", "notgithub.com"),
                          ("https://github.com.evil.example/o/r", "github.com.evil.example")):
            with self.subTest(url):
                got = forge.classify(url)
                self.assertEqual((got["kind"], got["where"]), (forge.OTHER_HOST, host))

    def test_unreadable_url_is_other_host_not_a_crash(self):
        """urlsplit が読めない URL（括弧の崩れた IPv6 の形）も落ちずに forge の無い側（理由に URL を載せない）"""
        got = forge.classify(f"https://u:{SECRET}@[abc/o/r")
        self.assertEqual(got["kind"], forge.OTHER_HOST)
        self.assertNotIn(SECRET, repr(got))

    def test_missing(self):
        for url in (None, "", "  "):
            with self.subTest(url):
                self.assertEqual(forge.classify(url)["kind"], forge.NO_REMOTE)

    def test_reason_never_carries_credentials(self):
        """URL の userinfo（トークン）は種類の理由にも where にも載せない"""
        for url in (f"https://u:{SECRET}@gitlab.com/o/r.git", f"https://{SECRET}@gitlab.com/o/r.git",
                    f"file://u:{SECRET}@localhost/tmp/o.git", f"https://u:{SECRET}@github.com/o/r.git"):
            with self.subTest(url):
                d = forge.classify(url)
                self.assertNotIn(SECRET, repr(d))
                self.assertNotIn(SECRET, forge.reason({**d, "remote": "origin"}))


class RepoOfCase(unittest.TestCase):
    """remote の URL から gh が名指せる {kind, host, owner, name}（ghreads が -R に使う）。userinfo（トークン）は載せない"""

    def test_github_forms(self):
        for url, host in (("git@github.com:o/r.git", "github.com"), (f"https://x:{SECRET}@github.com/o/r", "github.com"),
                          ("ssh://git@github.com-work/o/r.git", "github.com"), ("https://www.github.com/o/r/", "github.com"),
                          ("https://acme.ghe.com/o/r", "acme.ghe.com")):
            with self.subTest(url):
                got = forge.repo_of(url)
                self.assertEqual(got, {"kind": forge.GITHUB, "host": host, "owner": "o", "name": "r"})
                self.assertNotIn(SECRET, repr(got))

    def test_other_host_keeps_its_host(self):
        self.assertEqual(forge.repo_of("https://gitlab.example/o/r.git"),
                         {"kind": forge.OTHER_HOST, "host": "gitlab.example", "owner": "o", "name": "r"})
        self.assertEqual(forge.repo_of("git@ghe.corp.example:team/app.git")["host"], "ghe.corp.example")

    def test_not_a_repo_of_two_segments(self):
        for url in ("https://github.com/o", "https://github.com/o/r/x", "/tmp/o/r.git", "file:///tmp/o/r.git", "", None,
                    "https://github.com/o%2Fr/x", "foo::https://github.com/o/r"):
            with self.subTest(url):
                self.assertIsNone(forge.repo_of(url))


class ReasonCase(unittest.TestCase):
    def test_no_forge_reason_names_the_kind(self):
        for kind in forge.NO_FORGE:
            with self.subTest(kind):
                why = forge.reason({"kind": kind, "remote": "origin", "where": "x"})
                self.assertTrue(why.startswith(f"no_forge: {kind}"), why)

    def test_github_and_unknown_are_not_no_forge(self):
        """GitHub は forge（今どおり確かめる）。盤面に決めが無い（前の版の盤面）・形が崩れた値も今どおり（空の理由）"""
        for d in ({"kind": forge.GITHUB, "remote": "origin", "where": "github.com"}, None, {}, {"kind": "weird"}, "x"):
            with self.subTest(d):
                self.assertEqual(forge.reason(d), "")


class DetectCase(unittest.TestCase):
    """本物の git で remote を引く（upstream の remote を先に、無ければ origin。写しの _github_repo と同じ選び方）"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self._td.name) / "r"
        self.repo.mkdir()
        _git(self.repo, "init", "-q")

    def tearDown(self):
        self._td.cleanup()

    def test_no_origin(self):
        got = forge.detect(self.repo)
        self.assertEqual((got["kind"], got["remote"]), (forge.NO_REMOTE, "origin"))

    def test_local_bare_origin(self):
        _git(self.repo, "remote", "add", "origin", str(self.repo.parent / "origin.git"))
        self.assertEqual(forge.detect(self.repo)["kind"], forge.LOCAL_PATH)

    def test_github_origin(self):
        _git(self.repo, "remote", "add", "origin", "git@github.com:o/r.git")
        self.assertEqual(forge.detect(self.repo)["kind"], forge.GITHUB)

    def test_other_host_origin(self):
        _git(self.repo, "remote", "add", "origin", "https://gitlab.com/o/r.git")
        got = forge.detect(self.repo)
        self.assertEqual((got["kind"], got["where"]), (forge.OTHER_HOST, "gitlab.com"))

    def test_upstream_remote_wins(self):
        """枝の upstream の remote が在ればそれを見る（origin が GitHub でも upstream が GitLab なら forge でない）"""
        _git(self.repo, "remote", "add", "origin", "git@github.com:o/r.git")
        _git(self.repo, "remote", "add", "up", "https://gitlab.com/o/r.git")
        _git(self.repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "s")
        _git(self.repo, "update-ref", "refs/remotes/up/main", "HEAD")
        br = subprocess.run(["git", "-C", str(self.repo), "branch", "--show-current"], capture_output=True, text=True, encoding="utf-8",
                            env=hermetic.child_env()).stdout.strip()
        _git(self.repo, "branch", "--set-upstream-to=up/main", br)
        got = forge.detect(self.repo)
        self.assertEqual((got["kind"], got["remote"]), (forge.OTHER_HOST, "up"))

    def test_not_a_repo_is_unknown(self):
        """git が remote を引けない（リポジトリでない）は決めない: 種類 unknown・理由は空（今どおり役の道へ。forge が無いとは言わない）"""
        got = forge.detect(pathlib.Path(self._td.name) / "missing")
        self.assertEqual(got["kind"], forge.UNKNOWN)
        self.assertEqual(forge.reason(got), "")


class GhReadsCase(unittest.TestCase):
    """run の中の読み出し（ghreads.read_named）は、forge の無い対象でも利用者が名指した PR・issue を gh で読み（GH_REPO・
    別の remote・自前のドメインの GitHub Enterprise Server なら gh は読める）、gh も GitHub のホストを見つけなかった項だけを条件外
    （not_applicable、reason は no_forge: <種類>）と書く。gh が読みに行って読めなかった項は unreadable（理由は gh の言葉、欄 forge に
    no_forge の決め）。入力 pr は base・head が読めなければ、条件外なら no_forge の理由で、読めないならログインしてから回せと
    線の入口（entryshape.change_base）が止める"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._td.name).resolve()
        self.addCleanup(self._td.cleanup)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        _git(self.repo, "init", "-q")
        _git(self.repo, "remote", "add", "origin", str(self.tmp / "origin.git"))
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.called = self.tmp / "gh-called"
        gh = self.bin / "gh"
        gh.write_text(f'#!/bin/sh\necho "$*" >> "{self.called}"\nexit 4\n', encoding="utf-8")
        gh.chmod(0o755)

    def read(self, prs, issues=(), **env_kw):
        """偽の gh を PATH の頭に置き、利用者の gh の設定の置き場を外した env（env_kw を上に置く）で read_named を呼ぶ"""
        import os
        from unittest import mock
        import ghreads
        env = hermetic.child_env(PATH=f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}", HOME=str(self.tmp / "home"),
                                 XDG_CONFIG_HOME=str(self.tmp / "xdg"), **env_kw)
        if "GH_CONFIG_DIR" not in env_kw:
            env.pop("GH_CONFIG_DIR", None)
        with mock.patch.dict("os.environ", env, clear=True):
            return ghreads.read_named(self.repo, list(prs), list(issues))

    @staticmethod
    def refusal(doc):
        """読み出し doc で入力 pr=7 を解いた時の線の入口の拒みの文"""
        import entryshape
        try:
            entryshape.change_base({"pr": "7"}, pathlib.Path("/nonexistent"), doc)
        except entryshape.Refused as e:
            return str(e)
        raise AssertionError("拒まなかった")

    def test_named_items_gh_cannot_read_are_not_applicable(self):
        """gh が読めない（偽の gh は exit 4）名指しの項は unreadable でなく not_applicable（reason は no_forge: <種類>）。
        確かめる物が無いので人待ちにしない"""
        doc = self.read([7], [9])
        self.assertTrue(self.called.exists(), "利用者が名指した項を gh で読みに行かなかった")
        for got in (doc["pr"]["7"], doc["issue"]["9"]):
            self.assertEqual(got["status"], "not_applicable")
            self.assertTrue(got["reason"].startswith("no_forge: local_path"), got)
            self.assertIn("exit 4", got["reason"])   # gh が読めなかった理由も残す

    def test_pr_on_no_forge_refuses_with_the_reason(self):
        """入力 pr の base・head を gh が読めなければ、線の入口が no_forge の理由と base を名指す案内で止める"""
        text = self.refusal(self.read([7]))
        self.assertIn("no_forge: local_path", text)
        self.assertIn("base を名指して回す", text)

    def _reading_gh(self):
        """利用者のログインが見え、PR #7・issue #9 を返す偽の gh（test_ghreads.fake_gh）に替える"""
        from lib.tests.test_ghreads import fake_gh
        self.bin, calls, login = fake_gh(self.tmp)
        return {"GH_CONFIG_DIR": str(login)}

    def test_named_items_gh_can_read_are_kept_on_no_forge(self):
        """forge の無い対象でも、gh が読める名指しの項（GH_REPO・別の remote・自前のドメインの GHES）は読んだ中身を載せる
        （名指した物を黙って落とさない。条件外にするのは並行 PR の確かめと、gh が読めなかった項だけ）"""
        doc = self.read([7], [9], **self._reading_gh())
        self.assertEqual(doc["pr"]["7"]["body"], "非公開の本文")
        self.assertEqual(doc["issue"]["9"]["body"], "課題の本文")

    def test_pr_gh_can_read_runs_on_no_forge(self):
        """forge の無い対象でも、gh が PR の base・head を読めれば読み出しに載る"""
        got = self.read([7], **self._reading_gh())["pr"]["7"]
        self.assertEqual((got["baseRefOid"], got["headRefOid"]), ("b" * 40, "h" * 40))

    def test_pr_gh_reads_without_base_head_refuses_with_gh_words_on_no_forge(self):
        """forge の無い対象で gh が PR を読めたのに base・head の欄が欠けた時は、線の入口が 1 行で止める。読めた項を『ホストが
        無い』と言わず、forge の在る対象と同じ文で止まる"""
        from lib.tests.test_ghreads import fake_gh
        self.bin, _, login = fake_gh(self.tmp, base="", head="")
        text = self.refusal(self.read([7], GH_CONFIG_DIR=str(login)))
        self.assertIn("PR #7 の base・head を読めない", text)
        self.assertNotIn("PR を持つホストが無い", text)
        self.assertNotIn("\n", text)

    def _scripted_gh(self, rows):
        """引数の頭（"pr view 7"・"issue view 9"・"api … pulls/7/comments"）ごとに (exit, 標準出力, 標準エラー) を返す偽の gh に替える。
        当たらない呼び出しは exit 1 と GraphQL の見つからない文"""
        import json
        lines = ["#!/bin/sh", 'case "$*" in']
        for i, (pat, (code, out, err)) in enumerate(rows.items()):
            o, e = self.tmp / f"gh-out-{i}", self.tmp / f"gh-err-{i}"
            o.write_text(json.dumps(out, ensure_ascii=False) if out is not None else "", encoding="utf-8")
            e.write_text(err, encoding="utf-8")
            lines.append(f'  {pat}) cat "{o}"; cat "{e}" >&2; exit {code} ;;')
        lines += ['  *) echo "GraphQL: Could not resolve to a PullRequest" >&2; exit 1 ;;', "esac", ""]
        gh = self.bin / "gh"
        gh.write_text("\n".join(lines), encoding="utf-8")
        gh.chmod(0o755)

    PR = {"baseRefOid": "b" * 40, "headRefOid": "h" * 40, "title": "題", "body": "本文", "comments": [], "reviews": []}
    NO_HOST = ("none of the git remotes configured for this repository point to a known GitHub host. To tell gh about a "
               "new GitHub host, please use `gh auth login`\n")
    EXPIRED = "HTTP 401: Bad credentials (https://ghe.example.com/api/graphql)\nTry authenticating with:  gh auth login\n"

    def _ghes_target(self):
        """対象の remote を自前のドメインのホストにする（形からは GitHub でない＝forge の無い側。GitHub Enterprise Server でもありうる）"""
        _git(self.repo, "remote", "set-url", "origin", "https://ghe.example.com/o/r.git")

    def test_ghes_with_expired_login_is_unreadable_not_not_applicable(self):
        """forge の無い対象（形からは GitHub でないホスト）でも、gh が GitHub のホストとして読みに行って読めなかった項（自前のドメインの
        GHES でログインが切れた: HTTP 401）は not_applicable でなく unreadable で、理由は gh の言葉。forge の無い決めは別の欄 forge に
        残す（本当に条件外の項と見分ける）"""
        self._ghes_target()
        self._scripted_gh({"pr\\ view\\ 7*": (1, None, self.EXPIRED), "issue\\ view\\ 9*": (1, None, self.EXPIRED)})
        doc = self.read([7], [9])
        for got in (doc["pr"]["7"], doc["issue"]["9"]):
            self.assertEqual(got["status"], "unreadable", got)
            self.assertIn("HTTP 401: Bad credentials", got["reason"])
            self.assertFalse(got["reason"].startswith("no_forge"), got)
            self.assertTrue(got["forge"].startswith("no_forge: other_host"), got)
            self.assertNotIn("_no_host", got)   # 内側の印は読み出しに残さない

    def test_ghes_with_expired_login_pr_asks_to_log_in(self):
        """入力 pr でも同じ: gh が読みに行って読めなかったら『ホストが無い』でなく gh でログインしてから回せと言って止まる"""
        self._ghes_target()
        self._scripted_gh({"pr\\ view\\ 7*": (1, None, self.EXPIRED)})
        text = self.refusal(self.read([7]))
        self.assertIn("HTTP 401", text)
        self.assertIn("ログインしてから回す", text)
        self.assertNotIn("PR を持つホストが無い", text)

    def test_gh_sees_no_github_host_is_not_applicable(self):
        """gh 自身が対象の remote を GitHub のホストと見ない（none of the git remotes … known GitHub host）項は今どおり
        not_applicable（理由は no_forge: <種類> と gh の言葉）"""
        self._ghes_target()
        self._scripted_gh({"pr\\ view\\ 7*": (1, None, self.NO_HOST)})
        got = self.read([7])["pr"]["7"]
        self.assertEqual(got["status"], "not_applicable", got)
        self.assertTrue(got["reason"].startswith("no_forge: other_host"), got)
        self.assertIn("known GitHub host", got["reason"])

    def test_mixed_named_items_on_no_forge(self):
        """forge の無い対象で、読める項・行コメントだけ読めない項（partial）・gh が GitHub と見ない項・gh が読みに行って読めない項を
        1 つの依頼に混ぜても、項ごとに分けて書く（読めた項を落とさない・partial は partial のまま・条件外と読めないを混ぜない）"""
        self._ghes_target()
        self._scripted_gh({
            "pr\\ view\\ 7*": (0, self.PR, ""),
            "api*pulls/7/comments": (0, [{"path": "a.py", "line": 1, "body": "行"}], ""),
            "pr\\ view\\ 8*": (0, self.PR, ""),
            "api*pulls/8/comments": (1, None, "HTTP 502: Bad Gateway\n"),
            "pr\\ view\\ 5*": (1, None, self.NO_HOST),
            "issue\\ view\\ 9*": (1, None, self.EXPIRED),
        })
        doc = self.read([7, 8, 5], [9])
        self.assertEqual((doc["pr"]["7"]["status"], doc["pr"]["7"]["review_comments"][0]["body"]), ("ok", "行"))
        self.assertEqual(doc["pr"]["8"]["status"], "partial")
        self.assertEqual(doc["pr"]["8"]["body"], "本文")
        self.assertIn("HTTP 502", doc["pr"]["8"]["reason"])
        self.assertEqual(doc["pr"]["5"]["status"], "not_applicable")
        self.assertEqual(doc["issue"]["9"]["status"], "unreadable")
        self.assertIn("HTTP 401", doc["issue"]["9"]["reason"])
        for n in ("7", "8"):
            self.assertNotIn("forge", doc["pr"][n])   # 読めた項に forge の欄は足さない


if __name__ == "__main__":
    unittest.main()
