"""並行 PR の機械の道と受け付け（src/scan.py・src/take.py）を、関数のまま確かめる。今の judge の試験の写し
（lib/tests/test_judge_accept.py の PrScanCase・PrAcceptCase。`ja.pr_scan(jdir, repo)` を `scan.scan(place, repo, request=…, base=…, changed=…)`
の形に、judge/ の置き場を place に替えた）。gh は lib/ghreads の読む口の偽で返し、本物の gh・GitHub に触らない。
"""
import hashlib
import json
import unittest

from tests.bin import hermetic
from tests.bin.gitkit import git
from tests.blocks import kit

GITHUB = "git@github.com:o/r.git"
SOURCE = "def mean(xs):\n    return sum(xs)\n"
OK = {
    "material": {"status": "found", "count": 1, "detail": "PR #7 が stats.py の mean を同じく書き換えている（hunk @@ -1,3 +1,4 @@）"},
    "repo": "o/r", "listed": 2, "truncated": False,
    "conflicts": [{"pr": "7", "files": ["stats.py"], "handed_over": False,
                   "note": "PR #7 の担当へ: この run も stats.py の mean を直します。どちらを先に入れるか決めてください。"}],
    "excluded": [{"pr": "7", "file": "stats.py", "start": 1, "end": 2, "why": "PR #7 の hunk が mean の同じ行を書き換える"}],
}
NO_CONFLICTS = {
    "material": {"status": "clean", "checked": "gh -R o/r で open な PR 2 件を引き、交差した PR #7 の差分を読んだ。衝突 0 件・打ち切りなし"},
    "repo": "o/r", "listed": 2, "truncated": False, "conflicts": [], "excluded": [],
}
HANDED_OVER = {
    "material": {"status": "found", "count": 1, "detail": "PR #7 が stats.py の mean を同じく書き換えている。担当の PR に申し送った"},
    "repo": "o/r", "listed": 2, "truncated": False,
    "conflicts": [{"pr": "7", "files": ["stats.py"], "handed_over": True, "note": "gh pr comment 7 -R o/r で申し送った"}],
    "excluded": [],
}


def fake_gh(prs, files):
    calls = []

    def gh(*args):
        calls.append(args)
        if args[:2] == ("pr", "list"):
            return prs, None, False
        if args[:2] == ("pr", "view"):
            return {"files": [{"path": p} for p in files.get(args[2], [])]}, None, False
        return None, f"知らない語 {args}", False
    gh.calls = calls
    return gh


def never(*args):
    raise AssertionError(f"gh を呼んではいけない: {args}")


class Base(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "parallel-pr")
        self.repo, self.place = self.run.repo, self.run.artifacts
        (self.repo / "stats.py").write_text(SOURCE, encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "seed")
        git(self.repo, "remote", "add", "origin", GITHUB)
        self.head = git(self.repo, "rev-parse", "HEAD")
        self.scan_mod = kit.load("parallel-pr", "scan")
        self.take_mod = kit.load("parallel-pr", "take")
        self.files = self.scan_mod.files

    def scan(self, gh=None, which=lambda name: "/bin/gh", *, request=None, base="", changed=()):
        request = [{"where": "stats.py:2", "text": "mean が数で割っていない"}] if request is None else request
        return self.scan_mod.scan(self.place, self.repo, request=request, base=base, changed=list(changed), gh=gh or never, which=which)

    def material(self):
        return json.loads((self.place / self.files.MATERIAL).read_text(encoding="utf-8"))

    def brief(self):
        return json.loads((self.place / self.files.BRIEF).read_text(encoding="utf-8"))


class ScanCase(Base):
    def test_no_crossing_is_decided_by_machine(self):
        gh = fake_gh([{"number": 3, "headRefName": "me", "headRefOid": self.head},
                      {"number": 7, "headRefName": "x", "headRefOid": "f" * 40}], {"7": ["other.py"], "3": ["stats.py"]})
        got = self.scan(gh)
        self.assertEqual(got["go_role"], False, got)
        self.assertEqual(self.material()["materials"]["parallel_pr"]["status"], "clean")
        self.assertEqual(self.material()["role"], "pr-check")
        self.assertIn(("pr", "view", "7", "-R", "github.com/o/r", "--json", "files"), gh.calls)
        self.assertNotIn(("pr", "view", "3", "-R", "github.com/o/r", "--json", "files"), gh.calls, "自分の PR は見ない")
        doc = json.loads((self.place / self.files.EXCLUDED).read_text(encoding="utf-8"))
        self.assertEqual((doc["node"], doc["excluded"]), ("p0.parallel_pr", []))
        self.assertTrue(all("-R" in c for c in gh.calls), "gh は必ず -R で呼ぶ")

    def test_crossing_falls_back_to_role(self):
        got = self.scan(fake_gh([{"number": 7, "headRefOid": "f" * 40}], {"7": ["stats.py"]}))
        self.assertEqual(got["go_role"], True)
        self.assertIn("交差", got["reason"])
        brief = self.brief()
        self.assertEqual((brief["node"], brief["changed_files"], brief["fallback"]), ("p0.parallel_pr", ["stats.py"], got["reason"]))
        self.assertEqual(brief["request_wheres"], ["stats.py:2"])
        self.assertFalse((self.place / self.files.MATERIAL).exists(), "素材は役が返すまで書かない")

    def test_port_changed_wins_over_base_and_wheres(self):
        got = self.scan(fake_gh([{"number": 7, "headRefOid": "f" * 40}], {"7": ["stats.py"]}), changed=["new.py"])
        self.assertEqual(got["go_role"], False, got)
        self.assertEqual(self.brief()["changed_files"], ["new.py"])

    def test_diff_files_win_over_request_wheres(self):
        (self.repo / "new.py").write_text("x = 1\n", encoding="utf-8")
        got = self.scan(fake_gh([{"number": 7, "headRefOid": "f" * 40}], {"7": ["stats.py"]}), base=self.head)
        self.assertEqual(got["go_role"], False, got)
        self.assertEqual(self.brief()["changed_files"], ["new.py"])
        self.assertEqual(self.material()["materials"]["parallel_pr"]["status"], "clean")

    def test_gh_missing_falls_back(self):
        got = self.scan(which=lambda name: None)
        self.assertTrue(got["go_role"])
        self.assertIn("gh", got["reason"])

    def test_no_forge_is_not_applicable(self):
        git(self.repo, "remote", "set-url", "origin", str(self.repo.parent / "elsewhere"))
        got = self.scan()
        self.assertEqual(got["go_role"], False)
        m = self.material()["materials"]["parallel_pr"]
        self.assertEqual(m["status"], "not_applicable")
        self.assertTrue(m["reason"].startswith("no_forge: local_path"), m)

    def test_empty_set_is_not_run(self):
        got = self.scan(request=[{"where": "nowhere.py", "text": "x"}])
        self.assertFalse(got["go_role"])
        m = self.material()["materials"]["parallel_pr"]
        self.assertEqual(m["status"], "not_run")
        self.assertIn("空", m["reason"])

    def test_truncated_and_unreadable_wait_for_human(self):
        many = [{"number": n, "headRefOid": "f" * 40} for n in range(self.files.PR_LIMIT)]
        self.scan(fake_gh(many, {}))
        self.assertIn("打ち切られた", self.material()["materials"]["parallel_pr"]["reason"])
        self.scan(lambda *a: (None, "gh pr が exit 1: HTTP 401", False))
        m = self.material()["materials"]["parallel_pr"]
        self.assertEqual(m["status"], "awaiting_human")
        self.assertIn("HTTP 401", m["reason"])

    def test_machine_that_crashes_hands_over_to_the_role(self):
        def boom(*args):
            raise OSError("gh が起きない")
        got = self.scan(boom)
        self.assertEqual(got["go_role"], True)
        self.assertIn("機械の道が落ちた（OSError: gh が起きない）——役に任せる", got["reason"])
        self.assertEqual(self.brief()["fallback"], got["reason"])

    def test_repo_without_a_commit_cannot_snapshot_and_wakes_no_role(self):
        bare = hermetic.tmpdir(self) / "bare"
        bare.mkdir()
        git(bare, "init", "-q")
        got = self.scan_mod.scan(self.place, bare, request=[], base="", changed=["a.py"])
        self.assertEqual(got["go_role"], False)
        self.assertIn("作業ツリーの写しが取れない", got["reason"])

    def test_github_repo_redacts_token(self):
        git(self.repo, "remote", "set-url", "origin", "https://user:SECRET@git.example.com/o/r.git")
        slug, why = self.scan_mod.github_repo(self.repo)
        self.assertIsNone(slug)
        self.assertNotIn("SECRET", why)
        git(self.repo, "remote", "set-url", "origin", "https://github.com/o/r.git")
        self.assertEqual(self.scan_mod.github_repo(self.repo), ("github.com/o/r", None))

    def test_github_repo_reads_the_url_with_forge(self):
        for url, slug in (("ssh://git@ssh.github.com:443/o/r.git", "github.com/o/r"), ("https://www.github.com/o/r", "github.com/o/r"),
                          ("git@github.com-work:o/r.git", "github.com/o/r"), ("https://acme.ghe.com/o/r.git", "acme.ghe.com/o/r")):
            with self.subTest(url):
                git(self.repo, "remote", "set-url", "origin", url)
                self.assertEqual(self.scan_mod.github_repo(self.repo), (slug, None))

    def test_github_repo_takes_the_tracked_remote_first(self):
        git(self.repo, "remote", "add", "up", "https://github.com/up/r.git")
        git(self.repo, "update-ref", "refs/remotes/up/main", "HEAD")
        git(self.repo, "branch", "-q", "--set-upstream-to=up/main")
        self.assertEqual(self.scan_mod.github_repo(self.repo), ("github.com/up/r", None))
        git(self.repo, "branch", "-q", "base")
        git(self.repo, "branch", "-q", "--set-upstream-to=base")
        self.assertEqual(self.scan_mod.github_repo(self.repo), ("github.com/o/r", None))

    def test_gh_goes_through_the_read_only_form(self):
        """gh の打ち方は読むだけの口の許しの表に合う形（pr list・pr view の -R つき）だけ"""
        gh = fake_gh([{"number": 7, "headRefOid": "f" * 40}], {"7": ["stats.py"]})
        self.scan(gh)
        self.assertEqual([c[:2] for c in gh.calls], [("pr", "list"), ("pr", "view")])
        self.assertTrue(all(c[2 if c[1] == "list" else 3] == "-R" for c in gh.calls), gh.calls)


class TakeCase(Base):
    def setUp(self):
        super().setUp()
        self.scan(fake_gh([{"number": 7, "headRefOid": "f" * 40}], {"7": ["stats.py"]}))   # 役の前の作業ツリーの写しを置く

    def accept(self, reply):
        return self.take_mod.accept(self.place, self.repo, json.dumps(reply, ensure_ascii=False))

    def take(self, reply):
        return self.take_mod.take(self.place, self.repo, reply)

    def test_check_no_post(self):
        t = self.take_mod
        self.assertEqual(t.check_no_post(HANDED_OVER), ["7"])
        self.assertEqual(t.check_no_post(OK), [])
        self.assertEqual(t.check_no_post(NO_CONFLICTS), [])
        two = json.loads(json.dumps(OK))
        two["conflicts"] += [{"pr": "9", "files": ["a"], "handed_over": True}, {"pr": "11", "files": ["b"], "handed_over": True}]
        self.assertEqual(t.check_no_post(two), ["9", "11"])
        self.assertEqual(t.check_no_post({"conflicts": "x"}), [])

    def test_handed_over_true_rejected(self):
        got = self.accept(HANDED_OVER)
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("投稿しない", got["reason"])
        self.assertTrue(got["reason"].endswith(": 7"), got["reason"])
        self.assertFalse((self.place / self.files.MATERIAL).exists())
        self.assertFalse((self.place / self.files.DRAFTS).exists())

    def test_handover_draft_accepted_with_anchor(self):
        got = self.accept(OK)
        self.assertEqual(got, {"ok": True, "done": True, "reason": ""})
        doc = json.loads((self.place / self.files.EXCLUDED).read_text(encoding="utf-8"))
        self.assertEqual((doc["node"], doc["head"]), ("p0.parallel_pr", self.head))
        h = doc["excluded"][0]
        self.assertEqual({k: h[k] for k in ("pr", "file", "start", "end", "why")}, OK["excluded"][0])
        self.assertEqual(h["text"], SOURCE)
        self.assertEqual(h["sha256"], hashlib.sha256(SOURCE.encode("utf-8")).hexdigest())
        drafts = json.loads((self.place / self.files.DRAFTS).read_text(encoding="utf-8"))
        self.assertEqual(drafts, [{"pr": "7", "files": ["stats.py"], "note": OK["conflicts"][0]["note"]}])
        mat = self.material()
        self.assertEqual(mat["materials"]["parallel_pr"]["status"], "found")
        self.assertNotIn("excluded", mat["reply"])

    def test_no_conflicts_reply_accepted(self):
        self.assertTrue(self.accept(NO_CONFLICTS)["ok"])
        doc = json.loads((self.place / self.files.EXCLUDED).read_text(encoding="utf-8"))
        self.assertEqual(doc["excluded"], [])

    def test_excluded_checked(self):
        hunk = OK["excluded"][0]
        cases = {"conflicts に無い": {**OK, "excluded": [{**hunk, "pr": "99"}]},
                 "交差したファイル": {**OK, "excluded": [{**hunk, "file": "other.py"}]},
                 "より大きい": {**OK, "excluded": [{**hunk, "start": 2, "end": 1}]},
                 "行の数 2 を超える": {**OK, "excluded": [{**hunk, "end": 3}]},
                 "note": {**OK, "conflicts": [{k: v for k, v in OK["conflicts"][0].items() if k != "note"}]}}
        for word, bad in cases.items():
            got = self.take(bad)
            self.assertFalse(got["ok"], word)
            self.assertIn(word, got["reason"], word)
            self.assertFalse((self.place / self.files.DRAFTS).exists(), word)

    def test_excluded_file_listed_in_conflicts_but_absent_from_the_tree(self):
        """conflicts の files に在っても作業ツリーに無いファイルの hunk は、行の数を数えずに拒む"""
        hunk = OK["excluded"][0]
        bad = {**OK, "conflicts": [{**OK["conflicts"][0], "files": ["stats.py", "gone.py"]}],
               "excluded": [{**hunk, "file": "gone.py"}]}
        got = self.take(bad)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリーに無い", got["reason"])
        self.assertFalse((self.place / self.files.EXCLUDED).exists())

    def test_reply_that_is_not_an_object_is_refused(self):
        """JSON としては読めるが object でない返答（配列）は、落とさず拒む"""
        for raw in ([], "x", 3):
            got = self.take(raw)
            self.assertEqual(got, {"ok": False, "reason": "返答が JSON のオブジェクトでない"}, raw)
        got = self.accept([])
        self.assertFalse(got["ok"])
        self.assertIn("オブジェクト", got["reason"])
        self.assertFalse((self.place / self.files.MATERIAL).exists())

    def test_role_reads_only(self):
        (self.repo / "stats.py").write_text("changed\n", encoding="utf-8")
        got = self.take(OK)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリーを変えた", got["reason"])
        (self.repo / "stats.py").write_text(SOURCE, encoding="utf-8")
        git(self.repo, "checkout", "-q", "-b", "other")
        self.assertIn("ref", self.take(OK)["reason"])

    def test_missing_snapshot_is_refused(self):
        (self.place / self.files.TREE).unlink()
        got = self.take(OK)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリーの写し", got["reason"])

    def test_head_move_and_ignored_paths_are_refused(self):
        (self.repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
        git(self.repo, "add", ".gitignore")
        git(self.repo, "commit", "-q", "-m", "ignore")
        self.scan(fake_gh([{"number": 7, "headRefOid": "f" * 40}], {"7": ["stats.py"]}))
        tree = git(self.repo, "rev-parse", "HEAD^{tree}")
        other = git(self.repo, "commit-tree", tree, "-p", "HEAD", "-m", "same tree")
        git(self.repo, "checkout", "-q", "--detach", other)
        got = self.take(OK)
        self.assertFalse(got["ok"])
        self.assertIn(f"/ 今 {other}", got["reason"])
        self.assertIn("ref: 役を起こす前 refs/heads/", got["reason"])
        git(self.repo, "checkout", "-q", "-")
        (self.repo / "cache.log").write_text("x\n", encoding="utf-8")
        got = self.take(OK)
        self.assertFalse(got["ok"])
        self.assertIn("git が無視するパス: 増えた ['cache.log'] 消えた []", got["reason"])
        self.assertFalse((self.place / self.files.MATERIAL).exists())

    def test_malformed_reply_bounced_not_crashed(self):
        got = self.take_mod.accept(self.place, self.repo, "not json")
        self.assertFalse(got["ok"])
        self.assertIn("JSON", got["reason"])
        self.assertIn("記録の決まりに合わない", self.take(dict(OK, material={"status": "maybe"}))["reason"])

    def test_carried_over_and_not_applicable_are_refused(self):
        """走った役は流用（carried_over）も『条件に当たらない』（not_applicable）も名乗れない"""
        for status, word in (("carried_over", "今の周に走ったのに"), ("not_applicable", "名乗れない")):
            with self.subTest(status):
                got = self.take(dict(NO_CONFLICTS, material={"status": status, "reason": "前の周と同じ", "from_round": 1}))
                self.assertFalse(got["ok"])
                self.assertIn("記録の決まりに合わない", got["reason"])
                self.assertIn(word, got["reason"])

    def test_found_without_count_is_refused(self):
        got = self.take(dict(NO_CONFLICTS, material={"status": "found", "detail": "あった"}))
        self.assertFalse(got["ok"])
        self.assertIn("'count'", got["reason"])

    def test_third_rejection_gives_up(self):
        for n in range(1, 4):
            got = self.accept(HANDED_OVER)
            self.assertEqual(got["done"], n == 3, n)
        rows = json.loads((self.place / self.files.REJECTS).read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 3)

    def test_third_rejection_by_exception_also_counts(self):
        bad = dict(OK, conflicts=[dict(OK["conflicts"][0], note=5)])
        for n in range(1, 4):
            got = self.accept(bad)
            self.assertEqual((got["ok"], got["done"]), (False, n == 3), n)
        self.assertIn("例外", got["reason"])


if __name__ == "__main__":
    unittest.main()
