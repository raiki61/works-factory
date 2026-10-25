"""直し方の型の段 1（docs/plans/2026-10-24-fix-weapons.md の 4.4）の、型を問わない部品の試験。

- route から型を引く表（src/route.weapon_of。4.1 の 3 の 5 行）と、振り分けの AI に渡す単位の集まり（route_keys）
- 試験が無いかの印 no_tests の決め（src/basecase._no_tests。4.4 の作る物 12 の 5 つの場合と、宣言を読む木）。どの試験も対象の試験を
  走らせない（持ち主の決め base-runs-nothing。走らせるのは試験の一覧のコマンドだけ）
- 確かめの表（src/duties.py）の形の決まりと、型の義務の関数（static・pin・remove・variant・rebuild）
- 口の形（schemas/weapon-order.schema.json・weapon-return.schema.json）
"""
import json
import pathlib
import sys
import tempfile
import unittest

from tests.bin.gitkit import git
from tests.blocks import kit

route = kit.load("fix", "route")
basecase = kit.load("fix", "basecase")
duties = kit.load("fix", "duties")
pin = kit.load("fix", "pin")
static = kit.load("fix", "static")
remove = kit.load("fix", "remove")
variant = kit.load("fix", "variant")
rebuild = kit.load("fix", "rebuild")
from graphloops.engine.schema import validate_schema  # noqa: E402  （lib）

BLOCK = kit.BLOCKS / "fix"
PY = sys.executable


class WeaponTableCase(unittest.TestCase):
    def test_plan_words_come_first(self):
        for word in ("static", "tidy", "pin"):
            self.assertEqual(route.weapon_of(word, "tdd", ["x"]), word, "計画の語は振り分けの答えと消す名より先")

    def test_removes_go_to_remove(self):
        self.assertEqual(route.weapon_of("tdd", "tdd", ["old_name"]), "remove")
        self.assertEqual(route.weapon_of("", "", ["a.py"]), "remove")

    def test_tdd_by_plan_or_by_the_router(self):
        self.assertEqual(route.weapon_of("tdd", "direct", []), "tdd")
        self.assertEqual(route.weapon_of("direct", "tdd", []), "tdd")

    def test_the_rest_is_variant(self):
        for p, a in (("direct", "direct"), ("", ""), ("direct", ""), ("", "direct")):
            self.assertEqual(route.weapon_of(p, a, []), "variant", (p, a))

    def test_rebuild_is_never_drawn(self):
        """rebuild は口の形だけ: 表は rebuild を引かない（3.5 の届かない訳）"""
        got = {route.weapon_of(p, a, r) for p in ("", "tdd", "direct", "static", "tidy", "pin") for a in ("", "tdd", "direct")
               for r in ([], ["x"])}
        self.assertNotIn("rebuild", got)
        self.assertLessEqual(got, set(duties.WEAPONS))

    def test_route_keys_leave_out_words_and_removes(self):
        keys = ["a", "b", "c", "d"]
        self.assertEqual(route.route_keys(keys, {"a": "static", "b": "tdd"}, {"c": ["x"]}), ["b", "d"])


def _repo(tmp: pathlib.Path, files: dict) -> pathlib.Path:
    repo = tmp / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    for name, text in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "seed")
    return repo


def _decl(lines=None, setup=None, marker=None) -> str:
    """宣言の本文。lines は一覧が出す行の並び（None は list の鍵を置かない）、marker は一覧か準備が走った印を足すファイル"""
    doc = {"suite": [{"name": "s", "argv": ["true"]}]}
    if lines is not None:
        code = (f"open({str(marker)!r}, 'a').write('list\\n');" if marker else "") + "".join(f"print({x!r});" for x in lines)
        doc["list"] = [[PY, "-c", code or "pass"]]
    if setup is not None:
        doc["setup"] = [[PY, "-c", f"open({str(setup)!r}, 'a').write('setup\\n')"]]
    return json.dumps(doc)


class NoTestsCase(unittest.TestCase):
    """no_tests の決め（4.4 の作る物 12 の 5 つの場合と、宣言を読む木）"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)
        self.place = self.tmp / "place"
        self.place.mkdir()
        self.marker = self.tmp / "ran.txt"

    def tearDown(self):
        self._tmp.cleanup()

    def decide(self, repo, cases=()):
        return basecase._no_tests(self.place, repo, "HEAD", ["u"], 1, list(cases))

    def test_a_test_file_means_tests_and_the_list_is_not_run(self):
        repo = _repo(self.tmp, {"test_a.py": "def test_x():\n    pass\n", basecase.declared.DECL_NAME: _decl([], marker=self.marker)})
        rows, flag = self.decide(repo)
        self.assertEqual((rows["status"], flag), (basecase.SKIPPED, False))
        self.assertFalse(self.marker.exists(), "試験らしい名のファイルが在れば一覧を走らせない")

    def test_zero_listed_and_zero_cases_is_no_tests(self):
        repo = _repo(self.tmp, {"a.py": "x = 1\n", basecase.declared.DECL_NAME: _decl([])})
        rows, flag = self.decide(repo)
        self.assertEqual((rows["status"], rows["count"], flag), (basecase.LISTED, 0, True))

    def test_one_listed_is_not_no_tests(self):
        repo = _repo(self.tmp, {"a.py": "x = 1\n", basecase.declared.DECL_NAME: _decl(["check_one"])})
        rows, flag = self.decide(repo)
        self.assertEqual((rows["status"], rows["count"], flag), (basecase.LISTED, 1, False))

    def test_cases_in_the_base_win_over_an_empty_list(self):
        """一覧 0 件でも、一式で取った元の結末が 1 件以上なら偽（2.1 の (3)）"""
        repo = _repo(self.tmp, {"a.py": "x = 1\n", basecase.declared.DECL_NAME: _decl([])})
        rows, flag = self.decide(repo, [{"classname": "c", "name": "n", "outcome": "passed"}])
        self.assertEqual((rows["status"], flag), (basecase.LISTED, False))

    def test_absent_and_failing_lists_do_not_decide(self):
        repo = _repo(self.tmp, {"a.py": "x = 1\n", basecase.declared.DECL_NAME: _decl(None)})
        rows, flag = self.decide(repo)
        self.assertEqual((rows["status"], flag), (basecase.ABSENT, False))
        self.assertTrue(rows["why"])
        (repo / basecase.declared.DECL_NAME).write_text(json.dumps(
            {"suite": [{"name": "s", "argv": ["true"]}], "list": [[PY, "-c", "import sys; sys.exit(5)"]]}), encoding="utf-8")
        git(repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qam", "list fails")
        rows, flag = self.decide(repo)
        self.assertEqual((rows["status"], flag), (basecase.FAILED, False))
        self.assertIn("終了コード 5", rows["why"])

    def test_no_declaration_does_not_decide(self):
        repo = _repo(self.tmp, {"a.py": "x = 1\n"})
        rows, flag = self.decide(repo)
        self.assertEqual((rows["status"], flag), (basecase.ABSENT, False))

    def test_a_list_added_in_the_copied_tree_is_not_read(self):
        """起点の木の宣言に list が無く、写した木の宣言に在れば absent（run の中で足した list は読まない）"""
        repo = _repo(self.tmp, {"a.py": "x = 1\n", basecase.declared.DECL_NAME: _decl(None)})
        (repo / basecase.declared.DECL_NAME).write_text(_decl([], marker=self.marker), encoding="utf-8")
        rows, flag = self.decide(repo)
        self.assertEqual((rows["status"], flag), (basecase.ABSENT, False))
        self.assertFalse(self.marker.exists())

    def test_the_base_list_runs_not_the_rewritten_one(self):
        repo = _repo(self.tmp, {"a.py": "x = 1\n", basecase.declared.DECL_NAME: _decl(["one"], marker=self.marker)})
        (repo / basecase.declared.DECL_NAME).write_text(_decl([]), encoding="utf-8")   # 前の型が 0 件の一覧に書き換えた
        rows, flag = self.decide(repo)
        self.assertEqual((rows["count"], flag), (1, False))
        self.assertTrue(self.marker.exists(), "起点の木の list が走った")

    def test_the_base_setup_runs_not_the_rewritten_one(self):
        base_setup, new_setup = self.tmp / "base-setup.txt", self.tmp / "new-setup.txt"
        repo = _repo(self.tmp, {"a.py": "x = 1\n", basecase.declared.DECL_NAME: _decl([], setup=base_setup)})
        (repo / basecase.declared.DECL_NAME).write_text(_decl([], setup=new_setup), encoding="utf-8")
        self.decide(repo)
        self.assertTrue(base_setup.exists(), "起点の木の setup が一覧の前に走った")
        self.assertFalse(new_setup.exists(), "写した木の書き換えた setup は走らない")

    def test_no_setup_in_the_base_runs_nothing_before_the_list(self):
        """起点の木の宣言に setup が無く、写した木の宣言に在る組では、一覧の前に何も走らない（setup=[]）"""
        new_setup = self.tmp / "new-setup.txt"
        repo = _repo(self.tmp, {"a.py": "x = 1\n", basecase.declared.DECL_NAME: _decl([])})
        (repo / basecase.declared.DECL_NAME).write_text(_decl([], setup=new_setup), encoding="utf-8")
        rows, flag = self.decide(repo)
        self.assertEqual((rows["status"], flag), (basecase.LISTED, True))
        self.assertFalse(new_setup.exists())


class DutyTableCase(unittest.TestCase):
    def test_every_weapon_has_one_box_and_a_module(self):
        self.assertEqual(set(duties.BOXES), set(duties.MODULES))
        self.assertLessEqual(set(duties.BOXES.values()), set(duties.BOX_DUTIES))
        for name, mod in duties.MODULES.items():
            self.assertEqual(mod.BOX, duties.BOXES[name], name)

    def test_check_only_adds(self):
        """型の義務は箱の義務の問題に足すだけ（箱の義務の結果を受け取る口が無い）"""
        f = {"unit": "u", "vanished": ["c::gone"], "permits": [], "files": ["a.md"], "test_files": [], "added": []}
        got = duties.check("tidy", f)
        self.assertEqual(len(got), 1)
        self.assertIn("居なくなった", got[0])
        self.assertEqual(duties.check("tidy", {**f, "vanished": []}), [])
        self.assertEqual(duties.check("tidy", {**f, "permits": [{"kind": "remove", "test": "c::gone"}]}), [])

    def test_change_named_or_gone(self):
        ok = {"named": ["t"], "before": {"t": "failure"}, "after": {"t": "passed"}}
        self.assertEqual(duties.change_named_or_gone(ok), [])
        self.assertTrue(duties.change_named_or_gone({**ok, "before": {"t": "passed"}}))
        self.assertEqual(duties.change_named_or_gone({"removes": ["x"], "gone": ["x"]}), [])
        self.assertTrue(duties.change_named_or_gone({"removes": ["x", "y"], "gone": ["x"]}))


class WeaponDutiesCase(unittest.TestCase):
    def test_static(self):
        f = {"why_untested": "文書だけの直しで試験で示す物が無い", "kinds": {"docs"}, "allowed_kinds": ["docs"],
             "kind_by_path": {"a.md": "docs"}, "test_files": []}
        self.assertEqual([t for fn in static.DUTIES for t in fn(f)], [])
        self.assertTrue(static.why_untested({**f, "why_untested": ""}))
        self.assertTrue(static.kinds_allowed({**f, "kinds": {"code"}, "kind_by_path": {"a.py": "code"}}))
        self.assertTrue(static.kinds_allowed({**f, "kind_by_path": {"a.weird": None}}))
        self.assertTrue(static.no_test_edits({**f, "test_files": ["test_a.py"]}))

    def test_pin_tests_only_and_the_config_exception(self):
        f = {"files": ["test_a.py"], "test_files": ["test_a.py"], "added": ["test_a.py::test_x"], "kind_by_path": {}}
        self.assertEqual(pin.tests_only(f), [])
        self.assertTrue(pin.tests_only({**f, "added": []}), "足した試験が要る")
        code = {**f, "files": ["test_a.py", "a.py"], "kind_by_path": {"a.py": "code"}}
        self.assertTrue(pin.tests_only(code), "コードは書かない")
        cfg = {**f, "files": ["test_a.py", "setup.cfg"], "kind_by_path": {"setup.cfg": "config"}}
        self.assertTrue(pin.tests_only(cfg), "no_tests が偽なら設定のファイルは書かない")
        self.assertEqual(pin.tests_only({**cfg, "no_tests": True, "absent_at_base": ["setup.cfg"]}), [], "新しく作る設定は通す")
        kept = pin.tests_only({**cfg, "no_tests": True, "absent_at_base": []})
        self.assertTrue(any(pin.KEPT_CONFIG in t for t in kept), "起点の版に在る設定のファイルの書き換えは拒む")

    def test_pin_twice_reads_the_run(self):
        self.assertEqual(pin.twice({"twice": None}), [])
        self.assertEqual(pin.twice({"twice": ["2 回目に落ちた"]}), ["2 回目に落ちた"])

    def test_remove_in_permits(self):
        f = {"removed": ["t.py::a"], "permits": [{"kind": "remove", "test": "t.py::a"}]}
        self.assertEqual(remove.removed_in_permits(f), [])
        self.assertTrue(remove.removed_in_permits({**f, "permits": []}))

    def test_variant_sites_shape(self):
        f = {"class_query": {"patterns": ["x"]}, "hits": {"a.py:3"}, "hunks": {"a.py": [(2, 4)]},
             "sites": [{"site": "s1", "at": "a.py:3", "fixed_by": ["a.py:3-3"], "red_seen": "赤"}]}
        self.assertEqual(variant.sites_shape(f), [])
        self.assertTrue(variant.sites_shape({**f, "sites": []}))
        self.assertTrue(variant.sites_shape({**f, "sites": [{**f["sites"][0], "at": "a.py:9"}]}))
        self.assertTrue(variant.sites_shape({**f, "sites": [{**f["sites"][0], "fixed_by": ["a.py:9-10"]}]}))
        self.assertEqual(variant.sites_shape({**f, "class_query": None, "sites": []}), [], "問いの無い単位には当てない")
        self.assertEqual(variant.unit_red({"red_seen": True}), [])
        self.assertTrue(variant.unit_red({"red_seen": False}))

    def test_rebuild_compared(self):
        self.assertTrue(rebuild.compared_same({"compared": []}))
        self.assertEqual(rebuild.compared_same({"compared": [{"input": "i", "old": "h", "new": "h"}]}), [])
        self.assertTrue(rebuild.compared_same({"compared": [{"input": "i", "old": "h", "new": "g"}]}))
        self.assertEqual(rebuild.compared_same({"compared": [{"input": "i", "old": "h", "new": "g", "noisy": True}]}), [])


class SchemaCase(unittest.TestCase):
    def load(self, name):
        return json.loads((BLOCK / "schemas" / name).read_text(encoding="utf-8"))

    def test_an_order_and_a_return_hold_the_shape(self):
        order = {"weapon": "variant", "group": "g1", "stage": 1, "since": "abc", "base": "/p/base.json",
                 "units": [{"key": "u", "removes": [], "tests": ["t.py::a"], "checked_as": "tdd"}],
                 "scope": {"allowed_paths": ["a.py"], "out_of_scope": []},
                 "permits": [{"kind": "rewrite", "duty": True, "test": "t.py::a"}]}
        self.assertEqual(validate_schema(order, self.load("weapon-order.schema.json")), [])
        self.assertTrue(validate_schema({**order, "weapon": "direct"}, self.load("weapon-order.schema.json")))
        self.assertTrue(validate_schema({**order, "units": []}, self.load("weapon-order.schema.json")))
        ret = {"weapon": "pin", "status": [{"unit": "u", "status": "done", "why": ""}], "tree": "t",
               "changes": [{"unit": "u", "files": ["t.py"], "what": "足した", "na": ["breaks"],
                            "closure": {"sites": [{"site": "s", "test": "t.py::a", "fixed_by": [], "red_seen": "赤"}]}}],
               "evidence": {"named": [], "added": ["t.py::a"], "rewritten": [], "removed": [], "gone": [],
                            "kinds": [{"kind": "docs", "did": "リンクを引いた"}]}}
        self.assertEqual(validate_schema(ret, self.load("weapon-return.schema.json")), [])
        self.assertTrue(validate_schema({**ret, "status": [{"unit": "u", "status": "fixed", "why": ""}]},
                                        self.load("weapon-return.schema.json")))


if __name__ == "__main__":
    unittest.main()
