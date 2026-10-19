"""波及の一覧（blocks/plan/src/ripple.py。今の lib/tests/test_ripple.py の写し。docs/design/plan.md の 9.2）の検査。

項目が変える名（単位の key の `+` の後の名・files の change=add の symbol の名のうち対象に在る物）を `git grep -w` で引き、本体の呼び出し元と試験に分け、
項目の allowed_paths・tests・rewrite_tests に照らして覆っていない当たりを名指す。見本は run 195g の波及の見落としの形
（字のままの値を断言する試験が rewrite_tests に無い・既定の引数に頼る呼び出し元・入力の組を多くのファイルが共有する名）。
指示書に入れる材料の行（units_rows・rows・item_text）は英語の札の行だけで、見出しと頼みの文は md が持つ（md の字の照らしは別の試験）。
種の git は gitkit の型の写し（FAST）。
"""
import pathlib
import shutil
import tempfile
import unittest

from tests.bin.gitkit import committed_copy
from tests.blocks import kit

ripple = kit.load("plan", "ripple")
import planmarks  # noqa: E402  （lib/。kit.load が sys.path に足す）

SEED = {
    "works/report.py": "def always_rows(rows=None):\n    return rows or {}\n",
    "works/final.py": "from report import always_rows\n\n\ndef final():\n    return always_rows()\n",
    "works/tests/test_report.py": ("from report import always_rows\n\n\nclass TestReport:\n    def test_rows(self):\n"
                                   "        assert always_rows() == {}\n\n\ndef helper():\n    return always_rows([1])\n"),
    "works/edge.py": "EDGE_INPUTS = ('a', 'b')\n",
    "works/n1.py": "from edge import EDGE_INPUTS\n",
    "works/n2.py": "from edge import EDGE_INPUTS\n",
    "works/README.md": "always_rows は残りの数え\n",
    # 呼び出し元でない文書と生成物（当たりに数えない。run 68f35d6b の波及の当たりの大半が設計書の行だった）
    "works/docs/plans/2026-10-01-x.md": "always_rows の設計\n",
    "works/CHANGELOG.md": "- always_rows を足した\n",
    ".runner/workflows/works/report.py": "def always_rows(rows=None):\n    return rows or {}\n",
}
KEY = "works/report.py+always_rows: 残りの数えが今の周だけ"
SKIP_DIRS = ((".runner",),)


def setUpModule():
    global SRC
    SRC = pathlib.Path(tempfile.mkdtemp(prefix="works-ripple-seed-"))
    for name, text in SEED.items():
        p = SRC / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def tearDownModule():
    shutil.rmtree(SRC, ignore_errors=True)


def frow(path="works/report.py", *, adds=(), removes=(), op="modify", **extra):
    """files の 1 行（adds・removes は symbols の名の並び。消す symbol は why つき。受け持ちは波及の一覧に関わらない固定の字。
    home・considered は波及の一覧に当たらない既定で、考えの名は行の path ごとに違う字）"""
    symbols = [{"name": n, "change": "add"} for n in adds]
    symbols += [{"name": n, "change": "remove", "why": "古い名で、呼び手は新しい名に寄せた"} for n in removes]
    return {"path": path, "op": op, "responsibility": "この行の受け持ち", "symbols": symbols,
            "home": {"concept": f"{path} の考え", "why": "この行の path が住処だから"},
            "considered": [{"path": "alt_home.py", "why_not": "同じ仕事の助け手が alt_home.py:3 に無かった"}], **extra}


def gone(path):
    """消すファイルの行（op=delete。訳つき）"""
    return frow(path, op="delete", why="呼び手は寄せたので要らない")


def fields(unit_keys=(KEY,), files=(), allowed=("works/report.py",), tests=(), rewrites=()):
    return {"unit_keys": list(unit_keys), "files": list(files), "allowed_paths": list(allowed),
            "tests": [{"id": t} for t in tests], "rewrite_tests": [{"id": t} for t in rewrites], "out_of_scope": []}


def split_fields(unit_keys=(KEY,), removes=(), adds=(), deletes=(), allowed=("works/report.py",)):
    """修正案の項目を planmarks.split で欄にした物（盤面の plan-fields.json の項目の欄の形）。adds・removes は works/report.py の行の
    symbols の名、deletes は op=delete の行の path"""
    item = {"unit_keys": list(unit_keys), "approach": "x" * 20,
            "files": [frow(adds=adds, removes=removes), *[gone(d) for d in deletes]],
            "shrink_first": "y" * 20, "narrows": [], "route": "tdd", "route_why": "", "tests": [], "rewrite_tests": [],
            "refactor": {"declared": False, "why": ""}, "allowed_paths": list(allowed), "out_of_scope": []}
    return planmarks.split({"plan": [item]}, pathlib.Path("."))[1][0]


class RippleCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = pathlib.Path(self._tmp.name) / "repo"
        committed_copy(self.repo, SRC)

    def uncovered(self, doc, n=1):
        return [(h["kind"], h["at"]) for h in ripple.uncovered(doc, n)]

    def repo_with(self, extra: dict, base=SEED) -> pathlib.Path:
        """base の種に extra（パス → 中身）を足した種を commit した別のリポジトリ"""
        src = pathlib.Path(self._tmp.name) / "src"
        shutil.rmtree(src, ignore_errors=True)
        for name, text in {**base, **extra}.items():
            p = src / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        repo = pathlib.Path(self._tmp.name) / "repo2"
        shutil.rmtree(repo, ignore_errors=True)
        committed_copy(repo, src)
        return repo

    def test_names_from_unit_key_and_adds(self):
        """単位の key の `+` の後から `:` までの ASCII の名と、files の change=add の symbol の名の ASCII の語（日本語の語は名でない）"""
        self.assertEqual(ripple.names([KEY, "stats.py mean: 分母"], [frow(adds=["removed_rounds", "lens 数え"])]),
                         ["always_rows", "removed_rounds", "lens"])
        self.assertEqual(ripple.names(["a.py+Report.rows: x"], []), ["Report", "rows"])

    def test_names_skip_test_ids_and_paths(self):
        """試験の id（:: を含む名）と試験の名（test_・Test）は変える名でない（run 68f35d6b: 試験の id の断片 works・tests・
        test_report・HeadCase が当たりの大半を作った）。パスは行の path に在るので、名の字から読み分ける要はない"""
        files = [frow("works/tests/test_report.py", adds=["HeadCase::test_rows_carry", "TestCleanIgnored"]),
                 frow(adds=["_removed_file", "test_report", "report.always_rows"])]
        self.assertEqual(ripple.names([KEY], files), ["always_rows", "_removed_file", "report"])

    def test_names_count_helpers_in_test_modules(self):
        """試験のモジュール（impact.is_test が module を返す works/tests/test_report.py）の行の change=add の名も、試験の名でなければ
        変える名に数える（助け手の名 frow_rows・定数の名 SEED_ROWS。ほかの試験が import して使う時の呼び手を引く）。試験のフォルダの下の
        支え（works/tests/helpers.py）の行の名・本体の行の名も数える"""
        files = [frow("works/tests/test_report.py", adds=["frow_rows", "SEED_ROWS", "test_rows_carry"]),
                 frow("works/tests/helpers.py", adds=["seed_rows"]),
                 frow(adds=["always_rows"])]
        self.assertEqual(ripple.names([KEY], files), ["always_rows", "frow_rows", "SEED_ROWS", "seed_rows"])

    HELPER = "def seed_rows():\n    return [1]\n\n\ndef test_seed():\n    assert seed_rows()\n"
    HELPER_ITEM = fields(unit_keys=(), files=[frow("works/tests/test_report.py", adds=["seed_rows"])],
                         allowed=("works/tests/test_report.py",))

    def test_test_module_helper_used_by_other_test_is_named(self):
        """試験のモジュールの行で足す助け手 seed_rows を別の試験のファイルが import して使うと、その使い手が当たりに出る。定義した
        ファイル（works/tests/test_report.py）の中の当たりは捨てる"""
        user = "from test_report import seed_rows\n\n\ndef test_final_rows():\n    assert seed_rows()\n"
        repo = self.repo_with({"works/tests/test_report.py": self.HELPER, "works/tests/test_final.py": user})
        doc = ripple.build(repo, [self.HELPER_ITEM], skip_dirs=SKIP_DIRS)
        self.assertEqual(self.uncovered(doc), [("test", "works/tests/test_final.py:1"),
                                               ("test", "works/tests/test_final.py::test_final_rows")])

    def test_test_module_helper_used_only_in_own_file_is_not_named(self):
        """試験のモジュールの行で足す助け手 seed_rows の当たりが定義したファイルの中だけなら、名も当たりも出ない"""
        doc = ripple.build(self.repo_with({"works/tests/test_report.py": self.HELPER}), [self.HELPER_ITEM], skip_dirs=SKIP_DIRS)
        self.assertEqual((doc["items"][0]["names"], self.uncovered(doc)), ([], []))

    def test_docs_and_generated_copies_are_not_hits(self):
        """設計書（docs/plans）・CHANGELOG・実行基盤の pack の写し（skip_dirs）は当たりに数えない（ファイルの数にも）"""
        doc = ripple.build(self.repo, [fields()], skip_dirs=SKIP_DIRS)
        ats = [h[1] for h in self.uncovered(doc)]
        self.assertFalse([a for a in ats if "docs/plans" in a or "CHANGELOG" in a or a.startswith(".runner/")], ats)
        row = doc["items"][0]["names"][0]
        self.assertEqual(row["files"], 4)   # report.py・final.py・test_report.py・README.md

    def test_literal_test_not_in_rewrite_is_uncovered(self):
        """字のままの値を断言する試験（195g の removed-exact-dict-test-not-in-rewrite の形）は試験の関数の id で名指す"""
        doc = ripple.build(self.repo, [fields()], skip_dirs=SKIP_DIRS)
        self.assertIn(("test", "works/tests/test_report.py::TestReport::test_rows"), self.uncovered(doc))
        doc = ripple.build(self.repo, [fields(rewrites=["works/tests/test_report.py::TestReport::test_rows"])], skip_dirs=SKIP_DIRS)
        self.assertNotIn(("test", "works/tests/test_report.py::TestReport::test_rows"), self.uncovered(doc))

    def test_nested_class_test_id_is_the_plan_id(self):
        """入れ子のクラスの試験の id は修正案の試験の id（planmarks.test_functions）と同じ綴りで、rewrite_tests に挙げれば覆う（#567）"""
        path = "works/tests/test_nested.py"
        src = ("from report import always_rows\n\n\nclass Outer:\n    class Inner:\n        def test_rows(self):\n"
               "            assert always_rows() == {}\n")
        [tid] = planmarks.test_functions(src, path)
        repo = self.repo_with({path: src})
        self.assertIn(("test", tid), self.uncovered(ripple.build(repo, [fields()], skip_dirs=SKIP_DIRS)))
        self.assertNotIn(("test", tid), self.uncovered(ripple.build(repo, [fields(rewrites=[tid])], skip_dirs=SKIP_DIRS)))

    def test_caller_outside_scope_is_uncovered(self):
        """既定の引数に頼る呼び出し元（195g の always-rows-left-none-undefined の形）は本体の当たりで名指す。定義の在るファイルは
        allowed_paths の中なので覆っている。試験のファイルの試験でない関数は行で名指す。文書の当たりも本体に数える"""
        doc = ripple.build(self.repo, [fields()], skip_dirs=SKIP_DIRS)
        got = self.uncovered(doc)
        self.assertIn(("code", "works/final.py:1"), got)
        self.assertIn(("code", "works/final.py:5"), got)
        self.assertIn(("test", "works/tests/test_report.py:10"), got)
        self.assertIn(("code", "works/README.md:1"), got)
        self.assertFalse([h for h in got if h[1].startswith("works/report.py")])
        doc = ripple.build(self.repo, [fields(allowed=("works/*.py", "works/tests/test_report.py", "works/README.md"))], skip_dirs=SKIP_DIRS)
        self.assertEqual(self.uncovered(doc), [("test", "works/tests/test_report.py::TestReport::test_rows")])

    def test_hit_ids_are_stable_per_item(self):
        doc = ripple.build(self.repo, [fields()], skip_dirs=SKIP_DIRS)
        ids = [h["id"] for h in ripple.uncovered(doc, 1)]
        self.assertEqual(ids, [f"h{i}" for i in range(1, len(ids) + 1)])

    def test_common_name_counts_only(self):
        """当たりのファイルが多い名は数だけ載せ、覆っていない当たりに入れない（下請けが判断する）"""
        f = fields(unit_keys=["works/edge.py+EDGE_INPUTS: 入力の組"], allowed=("works/edge.py",))
        doc = ripple.build(self.repo, [f], common_files=2, skip_dirs=SKIP_DIRS)
        row = doc["items"][0]["names"][0]
        self.assertEqual((row["name"], row["common"], row["files"]), ("EDGE_INPUTS", True, 3))
        self.assertEqual(self.uncovered(doc), [])
        doc = ripple.build(self.repo, [f], skip_dirs=SKIP_DIRS)
        self.assertEqual(self.uncovered(doc), [("code", "works/n1.py:1"), ("code", "works/n2.py:1")])

    def test_names_absent_from_repo_are_dropped(self):
        doc = ripple.build(self.repo, [fields(unit_keys=["works/report.py+no_such_name: x"], files=[frow(adds=["also_missing"])])], skip_dirs=SKIP_DIRS)
        self.assertEqual(doc["items"][0]["names"], [])

    def test_overlaps_between_items(self):
        """2 つ以上の項目の allowed_paths・波及の当たりに出たファイル（相乗りの審査が突き合わせる）"""
        doc = ripple.build(self.repo, [fields(), fields(unit_keys=["works/final.py+final: y"], allowed=("works/final.py",))], skip_dirs=SKIP_DIRS)
        self.assertIn({"at": "works/final.py", "items": [1, 2]}, doc["overlaps"])

    def test_units_have_hits_without_coverage(self):
        """案の前（修正案の役に渡す）は単位の key の名だけを引き、照らす範囲が無いので覆っていない当たりを持たない"""
        doc = ripple.for_units(self.repo, [KEY], skip_dirs=SKIP_DIRS)
        row = doc["units"][0]
        self.assertEqual(row["unit_key"], KEY)
        self.assertIn("works/final.py:5", row["names"][0]["code"])
        self.assertIn("works/tests/test_report.py::TestReport::test_rows", row["names"][0]["tests"])

    def test_not_a_repo_gives_error_not_raise(self):
        doc = ripple.build(pathlib.Path(self._tmp.name) / "none", [fields()], skip_dirs=SKIP_DIRS)
        self.assertTrue(doc["error"])
        self.assertEqual(ripple.uncovered(doc, 1), [])

    def test_item_text_names_uncovered_with_ids(self):
        """項目の材料の行: 変える名と当たりの行と、覆っていない当たりを id つきで並べる（頼みの文は md が持つ）"""
        doc = ripple.build(self.repo, [fields()], skip_dirs=SKIP_DIRS)
        text = ripple.item_text(doc, 1)
        lines = text.splitlines()
        self.assertEqual(lines[0], f"### Item 1 (unit_keys: {KEY})")
        self.assertIn("Names changed and their hits:", lines)
        self.assertIn("- always_rows: hits in 4 files", lines)
        self.assertIn("  - body works/final.py:5", lines)
        self.assertIn("  - test works/tests/test_report.py::TestReport::test_rows", lines)
        self.assertIn("Hits not covered:", lines)
        for h in ripple.uncovered(doc, 1):
            self.assertIn(f"- {h['id']}: {h['kind']} {h['at']} (name {h['name']})", lines)
        self.assertIn("- h2: code works/final.py:1 (name always_rows)", lines)

    def test_item_text_without_names_or_uncovered(self):
        """在る名が無い項目は名の行の代わりに 1 行、覆っていない当たりが無ければ none"""
        doc = ripple.build(self.repo, [fields(unit_keys=["works/report.py+no_such_name: x"])], skip_dirs=SKIP_DIRS)
        self.assertEqual(ripple.item_text(doc, 1).splitlines(),
                         ["### Item 1 (unit_keys: works/report.py+no_such_name: x)", "", "Names changed and their hits:",
                          "- no name of it exists in the target", "", "Hits not covered:", "- none"])

    def test_item_text_of_missing_item(self):
        """一覧に無い項目は見出しと当たり無しの 1 文"""
        doc = ripple.build(self.repo, [fields()], skip_dirs=SKIP_DIRS)
        self.assertEqual(ripple.item_text(doc, 2), "### Item 2\n\nThe names it changes were not found in the target (no hits)")

    def test_item_text_common_name_is_count_only(self):
        """多い名は数と COMMON_NOTE だけで、当たりの下の行を持たない"""
        f = fields(unit_keys=["works/edge.py+EDGE_INPUTS: 入力の組"], allowed=("works/edge.py",))
        lines = ripple.item_text(ripple.build(self.repo, [f], common_files=2, skip_dirs=SKIP_DIRS), 1).splitlines()
        self.assertIn(f"- EDGE_INPUTS: hits in 3 files ({ripple.COMMON_NOTE})", lines)
        self.assertFalse([x for x in lines if x.startswith("  - ")], lines)
        self.assertEqual(lines[-1], "- none")

    def test_rows_join_items_and_overlaps(self):
        """全部の項目の行を空の行で並べ、項目どうしの重なりの行を後ろに置く"""
        doc = ripple.build(self.repo, [fields(), fields(unit_keys=["works/final.py+final: y"], allowed=("works/final.py",))],
                           skip_dirs=SKIP_DIRS)
        text = ripple.rows(doc)
        self.assertTrue(text.startswith(ripple.item_text(doc, 1) + "\n\n" + ripple.item_text(doc, 2) + "\n\n"), text)
        tail = text.split("\n\n")[-1].splitlines()
        self.assertEqual(tail[0], "Overlaps between items (files that appear in the scope or hits of two or more items):")
        self.assertIn("- works/final.py: items 1, 2", tail)
        self.assertNotIn("##", "".join(x for x in text.splitlines() if not x.startswith("### ")))

    def test_rows_without_overlaps(self):
        doc = ripple.build(self.repo, [fields()], skip_dirs=SKIP_DIRS)
        self.assertEqual(ripple.rows(doc), ripple.item_text(doc, 1))
        self.assertNotIn("Overlaps between items", ripple.rows(doc))

    def test_rows_empty_on_error_or_no_items(self):
        """誤りの一覧・項目の無い一覧は空の字（作れなかった文は md が持ち、訳は一覧の error から渡す）"""
        broken = ripple.build(pathlib.Path(self._tmp.name) / "none", [fields()], skip_dirs=SKIP_DIRS)
        self.assertTrue(broken["error"])
        self.assertEqual(ripple.rows(broken), "")
        self.assertEqual(ripple.rows({"items": [], "overlaps": [], "error": ""}), "")
        self.assertEqual(ripple.rows({"items": [], "error": "no plan"}), "")
        self.assertEqual(ripple.rows(None), "")

    def test_units_rows_per_unit(self):
        """案の前の材料の行: 単位ごとの見出しと名と当たりの行。在る名が無い単位は 1 行"""
        missing = "works/report.py+no_such_name: x"
        doc = ripple.for_units(self.repo, [KEY, missing], skip_dirs=SKIP_DIRS)
        parts = ripple.units_rows(doc).split("\n\n")
        self.assertEqual(len(parts), 2, parts)
        first = parts[0].splitlines()
        self.assertEqual(first[:2], [f"### Unit {KEY}", "- always_rows: hits in 4 files"])
        self.assertIn("  - body works/final.py:5", first)
        self.assertIn("  - test works/tests/test_report.py::TestReport::test_rows", first)
        self.assertEqual(parts[1].splitlines(), [f"### Unit {missing}", "- no name of it exists in the target"])

    def test_units_rows_common_name(self):
        doc = ripple.for_units(self.repo, ["works/edge.py+EDGE_INPUTS: 入力の組"], common_files=2, skip_dirs=SKIP_DIRS)
        self.assertEqual(ripple.units_rows(doc).splitlines(),
                         ["### Unit works/edge.py+EDGE_INPUTS: 入力の組", f"- EDGE_INPUTS: hits in 3 files ({ripple.COMMON_NOTE})"])

    def test_units_rows_empty_on_error_or_no_units(self):
        broken = ripple.for_units(pathlib.Path(self._tmp.name) / "none", [KEY], skip_dirs=SKIP_DIRS)
        self.assertTrue(broken["error"])
        self.assertEqual(broken["units"], [])
        self.assertEqual(ripple.units_rows(broken), "")
        self.assertEqual(ripple.units_rows({"units": [], "error": ""}), "")
        self.assertEqual(ripple.units_rows(None), "")

    def test_prompt_texts_are_not_kept(self):
        """見出し・頼み・作れなかった時の文は md に移した（Python は持たない）"""
        for name in ("HEAD", "UNITS_HEAD", "SCOPE_ASK", "ERROR_NOTE", "section", "units_section"):
            self.assertFalse(hasattr(ripple, name), name)

    def test_removes_names_hits_are_uncovered(self):
        """消す名（change=remove の symbol と op=delete の行の path）も名として引く: 識別子は探す語、.py のファイルの名はモジュールの名。
        残る名指しは kind removed で名指す"""
        f = split_fields(removes=["report.always_rows"], deletes=["works/final.py"])
        self.assertEqual([(r["path"], r["op"]) for r in f["files"]], [("works/report.py", "modify"), ("works/final.py", "delete")])
        doc = ripple.build(self.repo, [f], skip_dirs=SKIP_DIRS)
        self.assertEqual([r["name"] for r in doc["items"][0]["names"]], ["always_rows", "final"])
        self.assertIn(("removed", "works/final.py:1"), self.uncovered(doc))

    def test_files_rows_give_changed_and_removed_names(self):
        """files の change=add の symbol の名は変える名（kind code・test）に、change=remove の名と op=delete・op=rename の行のパス
        （rename は元のパス）は消す名（kind removed・removed_test）に引かれる"""
        edit = split_fields(unit_keys=[], adds=["always_rows"])
        kinds = {kind for kind, _ in self.uncovered(ripple.build(self.repo, [edit], skip_dirs=SKIP_DIRS))}
        self.assertEqual(kinds, {"code", "test"})
        cut = split_fields(unit_keys=[], removes=["always_rows"])
        kinds = {kind for kind, _ in self.uncovered(ripple.build(self.repo, [cut], skip_dirs=SKIP_DIRS))}
        self.assertEqual(kinds, {"removed", "removed_test"})
        gone_file = split_fields(unit_keys=[], deletes=["works/final.py"])
        got = self.uncovered(ripple.build(self.repo, [gone_file], skip_dirs=SKIP_DIRS))
        self.assertEqual({kind for kind, _ in got}, {"removed"}, got)
        moved = {"unit_keys": [], "approach": "x" * 20, "shrink_first": "y" * 20, "narrows": [],
                 "files": [frow("works/ended.py", op="rename", **{"from": "works/final.py"}, why="名を実体に合わせた")],
                 "allowed_paths": ["works/ended.py"], "out_of_scope": []}
        row = planmarks.split({"plan": [moved]}, pathlib.Path("."))[1][0]
        got = self.uncovered(ripple.build(self.repo, [row], skip_dirs=SKIP_DIRS))
        self.assertEqual({kind for kind, _ in got}, {"removed"}, "rename の元のパスを消す名に引く")

    def test_removed_and_changed_name_on_same_line_both_listed(self):
        """変える名と消す名が同じ行・同じ試験の関数に当たれば、変える名の行（code・test）と消す名の行（removed・removed_test）が両方残る"""
        doc = ripple.build(self.repo, [split_fields(removes=["report.always_rows"])], skip_dirs=SKIP_DIRS)
        got = self.uncovered(doc)
        for kind, at in (("code", "works/final.py:1"), ("removed", "works/final.py:1"),
                         ("test", "works/tests/test_report.py::TestReport::test_rows"),
                         ("removed_test", "works/tests/test_report.py::TestReport::test_rows")):
            self.assertIn((kind, at), got)
        only_changed = self.uncovered(ripple.build(self.repo, [split_fields()], skip_dirs=SKIP_DIRS))
        self.assertFalse([h for h in only_changed if h[0].startswith("removed")], only_changed)
        rewritten = split_fields(removes=["report.always_rows"])
        rewritten["rewrite_tests"] = [{"id": "works/tests/test_report.py::TestReport::test_rows"}]
        got = self.uncovered(ripple.build(self.repo, [rewritten], skip_dirs=SKIP_DIRS))
        self.assertNotIn(("removed_test", "works/tests/test_report.py::TestReport::test_rows"), got)

    def test_removed_name_hits_in_plan_docs_are_counted(self):
        """消す名に限り docs/plans の行も数える（CHANGELOG・実行基盤の pack の写し skip_dirs は今どおり捨てる）。足す名では docs/plans を
        数えない"""
        got = self.uncovered(ripple.build(self.repo, [split_fields(removes=["always_rows"])], skip_dirs=SKIP_DIRS))
        self.assertIn(("removed", "works/docs/plans/2026-10-01-x.md:1"), got)
        self.assertFalse([h for h in got if "CHANGELOG" in h[1] or h[1].startswith(".runner/")], got)
        added = self.uncovered(ripple.build(self.repo, [split_fields(unit_keys=[], adds=["always_rows"])], skip_dirs=SKIP_DIRS))
        self.assertFalse([h for h in added if "docs/plans" in h[1]], added)
        self.assertIn(("code", "works/final.py:1"), added)
        both = self.uncovered(ripple.build(self.repo, [split_fields(removes=["always_rows"])], skip_dirs=SKIP_DIRS))
        self.assertNotIn(("code", "works/docs/plans/2026-10-01-x.md:1"), both)

    def test_plan_docs_do_not_make_a_removed_name_common(self):
        """消す名の当たりに数え入れる計画書の数で、多い名（数だけ）に落とさない: 本体と試験の当たりのファイルの数だけで決める"""
        repo = self.repo_with({"works/docs/plans/2026-10-02-y.md": "EDGE_INPUTS の話\n"})
        f = split_fields(unit_keys=["works/edge.py+EDGE_INPUTS: 入力の組"], removes=["EDGE_INPUTS"], allowed=("works/edge.py",))
        row = ripple.build(repo, [f], common_files=3, skip_dirs=SKIP_DIRS)["items"][0]["names"][0]
        self.assertEqual((row["common"], row["files"]), (False, 4))
        self.assertIn(("removed", "works/n1.py:1"), self.uncovered(ripple.build(repo, [f], common_files=3, skip_dirs=SKIP_DIRS)))

    def test_removed_path_hits_are_uncovered(self):
        """消すファイルのパスは、パスの字のままの名指しと、.py ならモジュールの名の import も残りとして名指す"""
        repo = self.repo_with({"works/README.md": "道具は works/old_tool.py\n", "works/user.py": "import old_tool\n"})
        f = split_fields(unit_keys=["works/old_tool.py: 古い道具を消す"], deletes=["works/old_tool.py"], allowed=("works/old_tool.py",))
        got = self.uncovered(ripple.build(repo, [f], skip_dirs=SKIP_DIRS))
        self.assertIn(("removed", "works/README.md:1"), got)
        self.assertIn(("removed", "works/user.py:1"), got)
        self.assertEqual([h for h in got if h[0] != "removed"], [])

    def test_removed_non_python_path_uses_file_name(self):
        """.py でないパスは、最後の段のファイルの名も名にする"""
        repo = self.repo_with({"works/docs/old-notes.md": "古い\n", "works/README.md": "メモは old-notes.md にある\n"})
        f = split_fields(unit_keys=["x: y"], deletes=["works/docs/old-notes.md"], allowed=("works/docs/old-notes.md",))
        self.assertIn(("removed", "works/README.md:1"), self.uncovered(ripple.build(repo, [f], skip_dirs=SKIP_DIRS)))

    def test_item_text_marks_removed_name_hits(self):
        """消す名の当たりの行には、消した後に壊れる参照である印を出す"""
        doc = ripple.build(self.repo, [split_fields(removes=["report.always_rows"])], skip_dirs=SKIP_DIRS)
        text = ripple.item_text(doc, 1)
        marked = [x for x in text.splitlines() if x.startswith("- h") and " removed" in x]
        self.assertTrue(marked, text)
        self.assertTrue(all(x.endswith(ripple.REMOVED_MARK) for x in marked), marked)
        self.assertEqual(ripple.REMOVED_MARK, " (a hit of a name to remove: a reference that breaks after removal)")
        plain = next(x for x in text.splitlines() if x.startswith("- h") and " code " in x)
        self.assertNotIn(ripple.REMOVED_MARK, plain)


if __name__ == "__main__":
    unittest.main()
