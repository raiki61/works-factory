"""守りのファイルの一覧（lib/protected.json）と、その確かめ（lib/protect.py）の検査。

ASF の .factory/locks/floor.json に倣う: 工場（darkfactory の自分食い）は自分の試験・柵・受け付けの口を緩めない。一覧に当たる
ファイルを run が触ったら、最後の人の関所を必ず開いて冒頭 3 行で名指し、直後の最初の節に並べる（関所そのものは test_edge の ProtectedGateCase）。
- 一覧の行はどれも、このリポジトリで追跡しているファイルに 1 本以上当たる（当たらない行は古い行で赤。KNOWN の表と同じ扱い）
- 一覧の読み（match）は git の :(glob) と同じ当たり方をする（行ごとに git ls-files と突き合わせる）
- 一覧そのもの・確かめのモジュール・この試験と、赤と緑の判定（baseline_red・green_cert とその試験）は一覧に入っている
- 形の崩れた一覧（id の重なり・理由の無い行・絶対パス・.. ・空）は読み込みで拒む
- 差分の確かめ（touched）は数える版からの変更・消した物・未追跡を拾い、行数と当たった行を返す。触っていなければ空
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

LIB = pathlib.Path(__file__).resolve().parents[1]
REPO = LIB.parent                   # リポジトリの根（一覧のパスはここからの相対）
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import protect  # noqa: E402
from tests.bin.gitkit import committed_copy, git  # noqa: E402

SEED = LIB.parent / "tests" / "e2e" / "target-seed"


def tracked() -> list:
    out = subprocess.run(["git", "-C", str(REPO), "-c", "core.quotePath=false", "ls-files", "-z"], capture_output=True,
                         check=True).stdout.decode("utf-8")
    return [x for x in out.split("\0") if x]


def git_glob(pattern: str) -> set:
    out = subprocess.run(["git", "-C", str(REPO), "-c", "core.quotePath=false", "ls-files", "-z", "--", f":(top,glob){pattern}"],
                         capture_output=True, check=True).stdout.decode("utf-8")
    return {x for x in out.split("\0") if x}


class ManifestCase(unittest.TestCase):
    def setUp(self):
        self.doc = protect.load()
        self.files = tracked()

    def rel(self, p: pathlib.Path) -> str:
        return p.resolve().relative_to(REPO).as_posix()

    def test_every_rule_matches_a_tracked_file(self):
        """古い行（どの追跡ファイルにも当たらない）は赤。ファイルを動かした・消した時は一覧も直す"""
        stale = [r["id"] for r in self.doc["rules"] if not any(protect.match(f, r["glob"]) for f in self.files)]
        self.assertEqual(stale, [], "一覧の行がどの追跡ファイルにも当たらない（古い行）。行を直すか消す")

    def test_match_agrees_with_git_glob(self):
        """一覧の読みは git の :(glob) と同じ（** は 0 個以上のフォルダ・* と ? は / を跨がない）。フォルダの名前だけの行
        （git は中身に当てる）はここで食い違って赤になる——フォルダは /** で書く"""
        for r in self.doc["rules"]:
            with self.subTest(rule=r["id"]):
                mine = {f for f in self.files if protect.match(f, r["glob"])}
                self.assertEqual(mine, git_glob(r["glob"]))

    def test_manifest_and_checker_are_protected(self):
        for p in (protect.MANIFEST, LIB / "protect.py", pathlib.Path(__file__)):
            with self.subTest(path=p.name):
                self.assertTrue(protect.hits([self.rel(p)], self.doc), f"{self.rel(p)} が一覧に当たらない")

    def test_red_and_green_judges_are_protected(self):
        for name in ("baseline_red.py", "green_cert.py", "tests/test_baseline_red.py", "tests/test_green_cert.py"):
            with self.subTest(name=name):
                self.assertTrue(protect.hits([self.rel(LIB / name)], self.doc), f"lib/{name} が一覧に当たらない")

    def test_ordinary_files_are_not_protected(self):
        """守らない追跡ファイルは当たらない。lib/ の物でも照らす（一覧の外のパスだけで照らすと、lib/** のような広すぎる行を足しても緑のまま）"""
        for rel in ("README.md", "lib/impact.py", "lib/tests/test_blk_plan.py"):
            with self.subTest(rel=rel):
                self.assertIn(rel, self.files)
                self.assertEqual(protect.hits([rel], self.doc), [])



class ShapeCase(unittest.TestCase):
    def load(self, doc):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "m.json"
            p.write_text(json.dumps(doc) if not isinstance(doc, str) else doc, encoding="utf-8")
            return protect.load(p)

    def test_bad_shapes_refused(self):
        good = {"id": "a", "glob": "a/*.py", "why": "理由"}
        for name, doc in (("json でない", "{"), ("rules が無い", {"copies": []}), ("rules が空", {"rules": []}),
                          ("id の重なり", {"rules": [good, {**good, "glob": "b.py"}]}),
                          ("glob の重なり", {"rules": [good, {**good, "id": "b"}]}),
                          ("理由が無い", {"rules": [{**good, "why": ""}]}),
                          ("絶対パス", {"rules": [{**good, "glob": "/etc/x"}]}),
                          ("..", {"rules": [{**good, "glob": "a/../b.py"}]}),
                          ("末尾の /", {"rules": [{**good, "glob": "a/"}]}),
                          ("知らない鍵", {"rules": [{**good, "x": 1}]}),
                          ("copies の made_by が無い", {"rules": [good], "copies": [{"id": "c", "glob": "c/**", "why": "理由"}]})):
            with self.subTest(name):
                with self.assertRaises(protect.Broken):
                    self.load(doc)

    def test_good_shape_loads(self):
        doc = self.load({"rules": [{"id": "a", "glob": "a/*.py", "why": "理由"}]})
        self.assertEqual([r["id"] for r in protect.rules(doc)], ["a"])


class MatchCase(unittest.TestCase):
    def test_glob_words(self):
        for pattern, path, want in (("a/*.py", "a/x.py", True), ("a/*.py", "a/b/x.py", False),
                                    ("a/**", "a/b/c.py", True), ("a/**/c.py", "a/c.py", True), ("a/**/c.py", "a/b/d/c.py", True),
                                    ("blk-*/scripts/accept*.py", "blk-fix/scripts/accept_refix.py", True),
                                    ("blk-*/scripts/accept*.py", "blk-fix/scripts/x/accept.py", False),
                                    ("a/?.py", "a/xy.py", False), ("a/[xy].py", "a/y.py", True), ("a.py", "b/a.py", False),
                                    ("a+b(1).py", "a+b(1).py", True)):
            with self.subTest(pattern=pattern, path=path):
                self.assertEqual(protect.match(path, pattern), want)


class TouchedCase(unittest.TestCase):
    """種の git で: 数える版からの変更・消した物・未追跡・commit した物を拾い、行数と当たった行を返す"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self._tmp.name) / "repo"
        self.rev = committed_copy(self.repo, SEED)
        self.doc = {"rules": [{"id": "stats", "glob": "stats.py", "why": "種の芯"},
                              {"id": "tests", "glob": "test_*.py", "why": "種の試験"},
                              {"id": "new", "glob": "guards/**", "why": "新しい柵"}], "copies": []}

    def tearDown(self):
        self._tmp.cleanup()

    def test_untouched_is_empty(self):
        self.assertEqual(protect.touched(self.repo, self.rev, self.doc), [])
        (self.repo / "other.txt").write_text("x\n", encoding="utf-8")
        self.assertEqual(protect.touched(self.repo, self.rev, self.doc), [])

    def test_changed_deleted_untracked_committed(self):
        src = (self.repo / "stats.py").read_text(encoding="utf-8")
        (self.repo / "stats.py").write_text(src + "# a\n# b\n", encoding="utf-8")
        (self.repo / "test_stats.py").unlink()
        (self.repo / "guards").mkdir()
        (self.repo / "guards" / "日本語.py").write_text("x = 1\ny = 2\nz = 3\n", encoding="utf-8")
        rows = protect.touched(self.repo, self.rev, self.doc)
        got = {r["path"]: (r["id"], r["added"], r["deleted"]) for r in rows}
        n_test = len((SEED / "test_stats.py").read_text(encoding="utf-8").splitlines())
        self.assertEqual(got, {"stats.py": ("stats", 2, 0), "test_stats.py": ("tests", 0, n_test),
                               "guards/日本語.py": ("new", 3, 0)})
        self.assertEqual([r["path"] for r in rows], sorted(got))
        self.assertTrue(all(r["why"] and r["glob"] for r in rows))
        # commit して HEAD を動かしても、数える版からの差分として残る
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "hide")
        again = {r["path"]: (r["id"], r["added"], r["deleted"]) for r in protect.touched(self.repo, self.rev, self.doc)}
        self.assertEqual(again, got)

    def test_marked_protected_file_is_still_counted(self):
        """本物の index で assume-unchanged の印を付けた一覧のファイルも、挙げて行数を数える"""
        git(self.repo, "update-index", "--assume-unchanged", "stats.py")
        src = (self.repo / "stats.py").read_text(encoding="utf-8")
        (self.repo / "stats.py").write_text(src + "# a\n", encoding="utf-8")
        rows = protect.touched(self.repo, self.rev, self.doc)
        self.assertEqual([(r["path"], r["added"], r["deleted"]) for r in rows], [("stats.py", 1, 0)])

    def test_sparse_checkout_out_of_cone_protected_file_is_untouched(self):
        """sparse checkout の範囲外で disk に無い一覧のファイルは、触っていないので挙げない"""
        (self.repo / "guards").mkdir()
        (self.repo / "guards" / "g.py").write_text("x = 1\n", encoding="utf-8")
        (self.repo / "keep").mkdir()
        (self.repo / "keep" / "k.txt").write_text("k\n", encoding="utf-8")
        git(self.repo, "add", "guards", "keep")
        git(self.repo, "commit", "-q", "-m", "guards")
        rev = git(self.repo, "rev-parse", "HEAD").strip()
        git(self.repo, "sparse-checkout", "set", "keep")
        self.assertEqual(protect.touched(self.repo, rev, self.doc), [])

    def test_lines_name_file_stat_and_rule(self):
        (self.repo / "stats.py").write_text("x\n", encoding="utf-8")
        rows = protect.touched(self.repo, self.rev, self.doc)
        line = protect.lines(rows)[0]
        for want in ("stats.py", "+1", "−", "stats", "種の芯"):
            self.assertIn(want, line)

    def test_lines_say_no_count_for_binary(self):
        """行数の数えられない物（未追跡のバイナリ）の行は「行数なし」と書き、「+None」を書かない"""
        (self.repo / "guards").mkdir()
        (self.repo / "guards" / "blob.bin").write_bytes(b"\0\1\2")
        rows = protect.touched(self.repo, self.rev, self.doc)
        self.assertEqual([(r["path"], r["added"], r["deleted"]) for r in rows], [("guards/blob.bin", None, None)])
        line = protect.lines(rows)[0]
        self.assertIn("行数なし", line)
        self.assertNotIn("None", line)

    def test_default_manifest_used(self):
        """doc を渡さなければ MANIFEST を読む（試験は MANIFEST を差し替えて見る）"""
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "m.json"
            p.write_text(json.dumps({"rules": [{"id": "stats", "glob": "stats.py", "why": "種の芯"}]}), encoding="utf-8")
            (self.repo / "stats.py").write_text("x\n", encoding="utf-8")
            with mock.patch.object(protect, "MANIFEST", p):
                self.assertEqual([r["id"] for r in protect.touched(self.repo, self.rev)], ["stats"])




class TargetCase(unittest.TestCase):
    """対象のリポジトリの根の宣言（protect.TARGET_FILE）を始めの版から読み、自分の一覧と合わせる"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = pathlib.Path(self._tmp.name) / "repo"
        committed_copy(self.repo, SEED)
        self.own = {"rules": [{"id": "own", "glob": "own.txt", "why": "自分の柵"}], "copies": []}

    def declare(self, doc) -> str:
        (self.repo / protect.TARGET_FILE).write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
        git(self.repo, "add", protect.TARGET_FILE)
        git(self.repo, "commit", "-q", "-m", "declare")
        return git(self.repo, "rev-parse", "HEAD").strip()

    def test_target_rules_are_read_at_base_rev(self):
        rev = self.declare({"rules": [{"id": "core", "glob": "stats.py", "why": "対象の芯"}]})
        (self.repo / protect.TARGET_FILE).unlink()
        (self.repo / "stats.py").write_text("x\n", encoding="utf-8")
        (self.repo / "own.txt").write_text("y\n", encoding="utf-8")
        rows = protect.touched(self.repo, rev, protect.merged(self.repo, rev, self.own))
        self.assertEqual({r["path"]: r["id"] for r in rows},
                         {"stats.py": protect.TARGET_ID + "core", "own.txt": "own",
                          protect.TARGET_FILE: protect.TARGET_SELF["id"]})
        self.assertTrue(all(set(r) == {"path", "id", "glob", "why", "added", "deleted"} for r in rows), rows)

    def test_target_declaration_itself_is_protected(self):
        rev = git(self.repo, "rev-parse", "HEAD").strip()
        self.assertIsNone(protect.target_doc(self.repo, rev))
        doc = protect.merged(self.repo, rev, self.own)
        self.assertEqual(protect.hits([protect.TARGET_FILE, "stats.py"], doc),
                         [{"path": protect.TARGET_FILE, **{k: protect.TARGET_SELF[k] for k in ("id", "glob", "why")}}])
        self.assertEqual(doc["rules"][0], self.own["rules"][0], "自分の一覧は残す")

    def test_broken_target_declaration_raises(self):
        for name, doc in (("JSON でない", "{"), ("rules が空", {"rules": []}),
                          ("鍵が足りない", {"rules": [{"id": "a", "glob": "a.py"}]})):
            with self.subTest(name):
                rev = self.declare(doc)
                with self.assertRaises(protect.Broken):
                    protect.merged(self.repo, rev, self.own)
        with self.assertRaises(protect.Broken):
            protect.target_doc(self.repo, "no-such-rev")

if __name__ == "__main__":
    unittest.main()
