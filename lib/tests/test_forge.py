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

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import forge  # noqa: E402

SECRET = "ghp_SECRETVALUE"


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


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
        br = subprocess.run(["git", "-C", str(self.repo), "branch", "--show-current"], capture_output=True, text=True, encoding="utf-8").stdout.strip()
        _git(self.repo, "branch", "--set-upstream-to=up/main", br)
        got = forge.detect(self.repo)
        self.assertEqual((got["kind"], got["remote"]), (forge.OTHER_HOST, "up"))

    def test_not_a_repo_is_unknown(self):
        """git が remote を引けない（リポジトリでない）は決めない: 種類 unknown・理由は空（今どおり役の道へ。forge が無いとは言わない）"""
        got = forge.detect(pathlib.Path(self._td.name) / "missing")
        self.assertEqual(got["kind"], forge.UNKNOWN)
        self.assertEqual(forge.reason(got), "")


if __name__ == "__main__":
    unittest.main()
