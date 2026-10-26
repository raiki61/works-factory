"""直し方の型の段 1（docs/plans/2026-10-24-fix-weapons.md の 4.4）の、型を問わない部品の試験。

- route から型を引く表（src/route.weapon_of。4.1 の 3 の 5 行）と、振り分けの AI に渡す単位の集まり（route_keys）
- 試験が無いかの印 no_tests の決め（src/basecase._no_tests。4.4 の作る物 12 の 5 つの場合と、宣言を読む木）。どの試験も対象の試験を
  走らせない（持ち主の決め base-runs-nothing。走らせるのは試験の一覧のコマンドだけ）
- 確かめの表（src/duties.py）の形の決まりと、型の義務の関数（static・pin・remove・variant・rebuild）
- 口の形（.shared/schemas/weapon-order.schema.json・schemas/weapon-return.schema.json）
- 共通の受け付けが型の義務の表を引く口（duties.accept_problems）・赤を見ない clean の照らしを当てる単位（board.red_units・
  recount の red_units）・返しの控えを書く所（duties.write_returns）・返しの控えの凍結の照らし（duties.frozen_by_returns）・
  受け付けの名指しの出どころ（orders.named_tests）（4.4 の 4）
- 受け付け（fix-accept）を通して、返しの控えの凍結の照らしと注文の名指しが効くこと（AcceptWiringCase。組の子の scripts で回す）
"""
import json
import os
import pathlib
import re
import sys
import tempfile
import unittest
import unittest.mock

from tests.bin.gitkit import git
from tests.blocks import kit
from tests.blocks.fix import support
from tests.blocks.fix import test_group as tg

route = kit.load("fix", "route")
basecase = kit.load("fix", "basecase")
duties = kit.load("fix", "duties")
pin = kit.load("fix", "pin")
static = kit.load("fix", "static")
remove = kit.load("fix", "remove")
variant = kit.load("fix", "variant")
rebuild = kit.load("fix", "rebuild")
writers = kit.load("fix", "writers")
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
             "kind_by_path": {"a.md": "docs"}, "test_files": [], "kinds_rows": [{"kind": "docs", "did": "リンクを引いた"}]}
        self.assertEqual([t for fn in static.DUTIES for t in fn(f)], [])
        self.assertTrue(static.kinds_rows({**f, "kinds_rows": []}), "差分の種類の行が無い")
        self.assertTrue(static.kinds_rows({**f, "kinds_rows": [{"kind": "prompts", "did": "x"}]}), "ほかの種類の行では足りない")
        self.assertTrue(static.why_untested({**f, "why_untested": ""}))
        self.assertTrue(static.kinds_allowed({**f, "kinds": {"code"}, "kind_by_path": {"a.py": "code"}}))
        self.assertTrue(static.kinds_allowed({**f, "kind_by_path": {"a.weird": None}}))
        self.assertIn(static.NO_ALLOWED.format(kinds=["docs"]), static.kinds_allowed({**f, "allowed_kinds": []}),
                      "計画から種類が引けない時は素通りさせない")
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
        for gone in ({}, {"fixed_by": []}):   # 照らす単位（hits が None でない）では fixed_by が 1 つ以上要る
            with self.subTest(fixed_by=gone):
                row = {k: v for k, v in f["sites"][0].items() if k != "fixed_by"}
                self.assertTrue(variant.sites_shape({**f, "sites": [{**row, **gone}]}))
        loose = {**f, "hits": None}   # 問いを行で結べない単位: at と fixed_by の在る無しは照らさず、書いた fixed_by は照らす
        self.assertEqual(variant.sites_shape({**loose, "sites": [{"site": "s1", "at": "a.py:9", "red_seen": True}]}), [])
        self.assertTrue(variant.sites_shape({**loose, "sites": [{**f["sites"][0], "fixed_by": ["a.py:9-10"]}]}))
        files = {**f, "class_query": {"how": {"patterns": ["x"], "count": "files"}}, "hits": {"a.py:3", "b.py:1"}}
        self.assertEqual(variant.sites_shape({**files, "sites": [{**f["sites"][0], "at": "a.py:9"}]}), [],
                         "count: files の問いは at が当たりのファイルに在ればよい（当たりの行でなくてよい）")
        self.assertTrue(variant.sites_shape({**files, "sites": [{**f["sites"][0], "at": "c.py:3"}]}))
        self.assertEqual(variant.unit_red({"red_seen": True}), [])
        self.assertTrue(variant.unit_red({"red_seen": False}))

    def test_rebuild_compared(self):
        self.assertTrue(rebuild.compared_same({"compared": []}))
        self.assertEqual(rebuild.compared_same({"compared": [{"input": "i", "old": "h", "new": "h"}]}), [])
        self.assertTrue(rebuild.compared_same({"compared": [{"input": "i", "old": "h", "new": "g"}]}))
        self.assertEqual(rebuild.compared_same({"compared": [{"input": "i", "old": "h", "new": "g", "noisy": True}]}), [])


class AcceptFactsCase(unittest.TestCase):
    """受け付けの事実 hits・hunks（duties.unit_facts。F1 の作る物の 2・3）"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = _repo(self.tmp, {"a.py": "x = 1\nlo = 1\nlo = 2\n", "b.py": "lo = 3\n", "c.py": "keep = 1\n"})
        self.rev = git(self.repo, "rev-parse", "HEAD").strip()
        self.unitrows = kit.load("fix", "unitrows")
        self.how = {"patterns": ["lo ="], "paths": ["*.py"], "count": "lines", "fixed": True}

    def test_hit_lines_are_path_and_line_without_the_rev_head(self):
        self.assertEqual(self.unitrows.hit_lines(self.how, self.repo, self.rev), ({"a.py:2", "a.py:3", "b.py:1"}, ""))
        self.assertEqual(self.unitrows.hit_lines({**self.how, "count": "files"}, self.repo, self.rev),
                         ({"a.py:2", "a.py:3", "b.py:1"}, ""), "count: files の問いも当たりの行を引く")
        (self.repo / "a.py").write_text("x = 1\n", encoding="utf-8")
        self.assertEqual(self.unitrows.hit_lines(self.how, self.repo), ({"b.py:1"}, ""), "版を渡さなければ作業ツリー")
        self.assertEqual(self.unitrows.hit_lines(self.how, self.repo, self.rev)[0], {"a.py:2", "a.py:3", "b.py:1"})
        self.assertIsNone(self.unitrows.hit_lines({**self.how, "paths": []}, self.repo, self.rev)[0])

    def test_hit_lines_keep_a_path_that_holds_a_colon_and_digits(self):
        """パスに `:<数字>:` を含んでも、パスと行を切り損なわない"""
        (self.repo / "x:1:y").mkdir()
        (self.repo / "x:1:y" / "e.py").write_text("lo = 4\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "colon")
        rev = git(self.repo, "rev-parse", "HEAD").strip()
        self.assertEqual(self.unitrows.hit_lines(self.how, self.repo, rev)[0], {"a.py:2", "a.py:3", "b.py:1", "x:1:y/e.py:1"})
        self.assertEqual(self.unitrows.hit_lines(self.how, self.repo)[0], {"a.py:2", "a.py:3", "b.py:1", "x:1:y/e.py:1"})

    def test_hunks_are_the_new_side_of_the_diff_from_since(self):
        (self.repo / "a.py").write_text("x = 1\nlo = 9\nlo = 2\nnew = 1\n", encoding="utf-8")
        (self.repo / "b.py").unlink()
        (self.repo / "d.py").write_text("one\ntwo\n", encoding="utf-8")
        got = duties._hunks(self.repo, self.rev, ["a.py", "b.py", "c.py", "d.py"])
        self.assertEqual(got, {"a.py": [(2, 2), (4, 4)], "d.py": [(1, 2)]}, "消しだけの塊・変えていないファイルは入れず、未追跡は全体")
        self.assertEqual(duties._hunks(self.repo, self.rev, []), {})

    def test_hits_are_none_when_the_query_cannot_be_bound_to_lines(self):
        cq = {"how": self.how, "counts": "defects", "total": 3}
        self.assertEqual(duties._query_hits(self.repo, self.rev, cq), {"a.py:2", "a.py:3", "b.py:1"})
        self.assertIsNone(duties._query_hits(self.repo, self.rev, {**cq, "total": 5}), "ファイルごとの合計が問いの合計と合わない")
        self.assertIsNone(duties._query_hits(self.repo, self.rev, None))
        self.assertIsNone(duties._query_hits(self.repo, self.rev, {"counts": "defects"}))

    def test_reply_facts_are_built_from_the_unit_rows(self):
        rows = [{"closure": {"sites": [{"site": "s", "red_seen": False}, {"site": "t", "red_seen": True, "test": "x"}]}}, {}]
        f = duties._reply_facts(rows, [{"kind": "docs", "did": "d"}, "x"])
        self.assertEqual(tuple(sorted(f)), tuple(sorted(duties.REPLY_FACTS)))
        self.assertEqual((len(f["sites"]), f["red_seen"], f["kinds_rows"]), (2, True, [{"kind": "docs", "did": "d"}]))
        self.assertFalse(duties._reply_facts([{"closure": {"sites": [{"red_seen": False}]}}], None)["red_seen"])


class NamedDutyCase(unittest.TestCase):
    """変える段の箱の義務 change_named_or_gone を受け付けの事実（duties.unit_facts の named・before・after・removes・gone）から引く
    （F2 の縛る試験の 1・2。実行器は本物の小さな実行器で、起点の木の結末は事後の関門と同じ口 gates.named_facts が引く）。
    起点の木では test_mean_of_three が failure（平均の分母の誤り）・test_clamp_within_range が通る。返した木の結末 cases は受け付けが走らせた
    回の結末（selected_problems の seen["cases"]）の代わりに渡す"""

    NAMED = "名指しの試験が起点の木で赤（failure）・返した木で緑にならず"
    MEAN3 = "test_stats.py::TestStats::test_mean_of_three"
    CLAMP = "test_stats.py::TestStats::test_clamp_within_range"
    TWO = "test_two.py::TestTwo::test_halve"
    TWO_FILE = ("import unittest\n\nfrom stats import halve\n\n\nclass TestTwo(unittest.TestCase):\n    def test_halve(self):\n"
                "        self.assertEqual(halve(4), 2)\n")
    STUB = "def halve(x):\n    return 0  # 仮の実装\n\n\ndef clamp(x, lo, hi):"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        seed = kit.ROOT / "tests" / "e2e" / "target-seed"
        files = {f.name: f.read_text(encoding="utf-8") for f in seed.glob("*.py")}
        self.repo = _repo(self.tmp, {**files, "legacy.py": "def old_helper():\n    return 1\n"})
        self.rev = git(self.repo, "rev-parse", "HEAD").strip()
        self.suite = self.tmp / "suite.py"
        self.suite.write_text(support.SUITE, encoding="utf-8")
        self.place = self.tmp / "place"
        self.place.mkdir()
        kit.load("fix", "duties")
        from src import common, duties, gates, orders
        self.common, self.duties, self.gates, self.orders = common, duties, gates, orders

    def put(self, rel, doc):
        p = self.place / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc), encoding="utf-8")
        return p

    def order(self, weapon, unit_extra=None, permits=(), units=None):
        keys = [u["key"] for u in units] if units else ["U"]
        self.put("orders.json", {"sequence": [weapon], "weapons": {k: weapon for k in keys}, "stage": 1, "since": self.rev})
        self.put(f"orders/{weapon}.json", {"weapon": weapon, "group": "g1", "stage": 1, "since": self.rev, "permits": list(permits),
                                           "units": units or [{"key": "U", "removes": [], "tests": [], **(unit_extra or {})}]})
        self.put("base.json", {"exe": str(self.suite), "work": str(self.place / "base"), "baseline": {}, "baseline_cases": [],
                               "rev": self.rev, "taken": True})

    def fix_mean(self):
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")

    @staticmethod
    def passed(*tests):
        return [{"classname": ".".join(t.partition("::")[0][:-3:].split("/") + t.split("::")[1:-1]), "name": t.rsplit("::", 1)[1],
                 "outcome": "passed"} for t in tests]

    def texts(self, named=(), files=("stats.py",), cases=None, record="", reply_extra=None):
        reply = {"changes": [{"unit_key": "U", "files": list(files)}],
                 "evidence": {"named": [{"unit_key": "U", "test": t} for t in named]}, **(reply_extra or {})}
        got = self.duties.accept_problems(self.place, self.repo, self.rev, reply, cases=cases, record=record)
        return [t for k, t in got if k == "U"]

    def rejected(self, texts) -> bool:
        return any(self.NAMED in t for t in texts)

    # ---- 拒む（縛る試験の 1）
    def test_a_variant_unit_with_neither_a_named_test_nor_a_removed_name_is_rejected(self):
        self.order("variant")
        self.fix_mean()
        self.assertTrue(self.rejected(self.texts(cases=self.passed(self.MEAN3))))

    def test_a_named_test_that_already_passes_at_the_base_is_rejected(self):
        """名指しの試験が起点の木で通る（赤を見ていない）単位: 返した木で緑でも拒む"""
        self.order("variant")
        self.fix_mean()
        self.assertTrue(self.rejected(self.texts(named=[self.CLAMP], cases=self.passed(self.CLAMP))))

    def test_a_named_test_that_is_not_green_in_the_returned_tree_is_rejected(self):
        self.order("variant")
        self.fix_mean()
        cases = [{**c, "outcome": "failure"} for c in self.passed(self.MEAN3)]
        self.assertTrue(self.rejected(self.texts(named=[self.MEAN3], cases=cases)))
        self.assertTrue(self.rejected(self.texts(named=[self.MEAN3], cases=[])), "走らせた回に居ない名指しは緑でない")
        self.assertTrue(self.rejected(self.texts(named=[self.MEAN3], cases=None)), "実行器が走らなかった回も緑でない")

    def test_a_remove_unit_whose_name_stays_in_the_returned_tree_is_rejected(self):
        self.order("remove", {"removes": ["old_helper"]})
        self.assertTrue(self.rejected(self.texts(files=["legacy.py"], cases=[])), "消していない")
        (self.repo / "legacy.py").unlink()
        (self.repo / "user.py").write_text("from legacy import old_helper\n", encoding="utf-8")   # 未追跡の新しいファイルに残る
        self.assertTrue(self.rejected(self.texts(files=["legacy.py", "user.py"], cases=[])), "未追跡のファイルに残る名も残りに数える")

    def test_a_remove_unit_whose_path_stays_is_rejected(self):
        self.order("remove", {"removes": ["legacy.py"]})
        self.assertTrue(self.rejected(self.texts(files=["legacy.py"], cases=[])))

    # ---- 通す（縛る試験の 2）
    def test_a_named_test_red_at_the_base_and_green_in_the_returned_tree_passes(self):
        self.order("variant")
        self.fix_mean()
        self.assertFalse(self.rejected(self.texts(named=[self.MEAN3], cases=self.passed(self.MEAN3))))

    def test_the_tests_the_order_names_count_without_the_reply_naming_them(self):
        """注文の units[].tests と、permits の rewrite の行の試験（1 単位の注文は全部がその単位）は、返答が名指さなくても名指しに数える"""
        self.fix_mean()
        self.order("variant", {"tests": [self.MEAN3]})
        self.assertFalse(self.rejected(self.texts(cases=self.passed(self.MEAN3))))
        self.order("variant", permits=[{"kind": "rewrite", "duty": True, "test": self.MEAN3, "source": "plan"}])
        self.assertFalse(self.rejected(self.texts(cases=self.passed(self.MEAN3))))
        self.order("variant", permits=[{"kind": "remove", "duty": False, "test": self.MEAN3, "source": "plan"}])
        self.assertTrue(self.rejected(self.texts(cases=self.passed(self.MEAN3))), "remove の許しは名指しでない")

    def test_a_rewrite_permit_of_an_order_with_two_units_is_tied_by_the_units_own_tests(self):
        """単位が 2 つの注文では、rewrite の行の試験は、その単位の注文の tests に在る単位だけに結ぶ（別の単位の書き換えで通さない）"""
        self.fix_mean()
        self.order("variant", permits=[{"kind": "rewrite", "duty": True, "test": self.MEAN3, "source": "plan"}],
                   units=[{"key": "U", "removes": [], "tests": [self.MEAN3]}, {"key": "V", "removes": [], "tests": []}])
        self.assertFalse(self.rejected(self.texts(cases=self.passed(self.MEAN3))))
        got = self.duties.accept_problems(self.place, self.repo, self.rev, {"changes": [{"unit_key": "V", "files": ["stats.py"]}]},
                                          cases=self.passed(self.MEAN3))
        self.assertTrue(any(k == "V" and self.NAMED in t for k, t in got), got)

    def test_a_guard_test_of_the_plan_is_not_a_named_test(self):
        """計画の守りのテスト（赤の種類が guard。直す前から緑で緑のまま）は、注文の tests に在っても名指しに数えない（数えると『起点の木で赤』を
        満たせず、正しい単位を拒む）。受け入れのテストは数える"""
        import planmarks
        row = {"behavior": "x", "path": "y", "red_why": "z"}
        planmarks.save(self.place, 1, [{"unit_keys": ["U"], "route": "tdd", "route_why": "", "rewrite_tests": [],
                                        "refactor": {"declared": False, "why": ""},
                                        "tests": [{**row, "id": self.MEAN3, "red_kind": "assertion"},
                                                  {**row, "id": self.CLAMP, "red_kind": planmarks.GUARD_KIND}]}])
        self.order("variant", {"tests": [self.MEAN3, self.CLAMP]})
        self.fix_mean()
        self.assertFalse(self.rejected(self.texts(cases=self.passed(self.MEAN3, self.CLAMP))))

    def test_a_remove_unit_whose_names_are_all_gone_passes_without_a_named_test(self):
        self.order("remove", {"removes": ["legacy.py", "old_helper"]})
        (self.repo / "legacy.py").unlink()
        self.assertEqual(self.texts(files=["legacy.py"], cases=[]), [])

    def test_a_tdd_unit_passes_by_the_loop_record_without_evidence_named(self):
        """tdd の単位は、書き手が evidence.named を書かなくても輪の記録 record.json の単位の tests で通る"""
        self.order("tdd")
        self.fix_mean()
        record = self.put("tdd-1/record.json", {"units": {"U": {"route": "tdd", "tests": [self.MEAN3]}}})
        self.assertFalse(self.rejected(self.texts(cases=self.passed(self.MEAN3), record=str(record))))
        self.assertTrue(self.rejected(self.texts(cases=self.passed(self.MEAN3))), "記録を渡さなければ名指しは無い")
        self.assertTrue(self.rejected(self.texts(cases=[], record=str(record))), "輪の名指しも返した木で緑が要る")

    def loop_record(self, red_tree):
        files = ["test_two.py"]
        hashes = self.common.hashes(self.repo, files)
        unit = {"unit_key": "U", "route": "tdd", "red": "ok", "tests": [self.TWO], "test_files": files, "test_hashes": hashes,
                "red_tree": red_tree}
        return self.put("tdd-1/record.json", {"units": {"U": unit}, "frozen": hashes})

    def test_a_tdd_test_that_leans_on_an_earlier_units_fix_is_not_rejected(self):
        """前の単位の直しに頼る tdd の試験: 起点の木では実装が無く一式の結末に居ない（error と同じ非 failure）が、輪の赤の木（単位の頭の木）では
        failure。輪の赤の木で見るので、正しい単位を拒まない。赤の木を渡さなければ起点の木で見て拒む"""
        self.order("tdd")
        (self.repo / "test_two.py").write_text(self.TWO_FILE, encoding="utf-8")
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("def clamp(x, lo, hi):", self.STUB), encoding="utf-8")
        red = self.common.snapshot(self.repo)
        stats.write_text(stats.read_text(encoding="utf-8").replace("return 0  # 仮の実装", "return x / 2"), encoding="utf-8")
        record = self.loop_record(red)
        cases = self.passed(self.TWO)
        self.assertEqual(self.texts(files=["stats.py", "test_two.py"], cases=cases, record=str(record)), [])
        bad = self.loop_record(self.rev)   # 赤の木が今の記録の赤を映さない（赤の木で通る）なら、名指しは赤を見ていない
        self.assertTrue(self.rejected(self.texts(files=["stats.py", "test_two.py"], cases=cases, record=str(bad))))
        self.put("tdd-1/record.json", {"units": {"U": {"route": "tdd", "tests": [self.TWO]}}})   # 赤の記録の無い輪の名指し: 起点の木で見る
        self.assertTrue(self.rejected(self.texts(files=["stats.py", "test_two.py"], cases=cases, record=str(record))))

    # ---- 事実
    def test_gone_reads_a_path_by_its_presence_and_a_name_by_a_word_search(self):
        legacy = self.repo / "legacy.py"
        self.assertEqual(self.duties.gone_of(self.repo, self.rev, ["legacy.py", "old_helper", "absent_name"]), [], "どれも残っている")
        legacy.unlink()
        self.assertEqual(self.duties.gone_of(self.repo, self.rev, ["legacy.py", "old_helper", "absent_name", "mean"]),
                         ["legacy.py", "old_helper"], "起点の木で引けない名は入れない。残る名（mean）は入れない")
        (self.repo / "note.md").write_text("old_helper_v2 は別の名\n", encoding="utf-8")
        self.assertEqual(self.duties.gone_of(self.repo, self.rev, ["old_helper"]), ["old_helper"], "語の単位で当てる（別の名の一部は残りでない）")

    def test_gone_leaves_out_a_name_it_cannot_read(self):
        (self.repo / "legacy.py").unlink()
        self.assertEqual(self.duties.gone_of(self.repo, "no-such-rev", ["legacy.py", "old_helper"]), [], "git が読めない名は gone に入れない")
        self.assertEqual(self.duties.gone_of(self.tmp / "no-repo", self.rev, ["old_helper"]), [])

    def test_the_named_tests_the_reply_the_order_and_the_loop_record_are_laid_without_repeats(self):
        self.order("tdd", {"tests": [self.MEAN3]}, permits=[{"kind": "rewrite", "duty": True, "test": self.MEAN3, "source": "plan"}])
        record = self.put("tdd-1/record.json", {"units": {"U": {"route": "tdd", "tests": [self.MEAN3, self.CLAMP]}}})
        facts = self.duties.unit_facts(self.place, self.repo, self.rev, "U", "tdd", [{"unit_key": "U", "files": ["stats.py"]}],
                                       order=self.orders.order_docs(self.place)["tdd"], base={"exe": ""}, cases=[],
                                       evidence={"named": [{"unit_key": "U", "test": self.TWO}, {"unit_key": "V", "test": "x.py::y"}]},
                                       record=str(record))
        self.assertEqual(facts["named"], [self.TWO, self.MEAN3, self.CLAMP])

    def test_before_and_after_are_not_taken_for_a_unit_without_names_or_outside_the_change_box(self):
        """名指しの無い単位・変える段でない型では before・after を引かない（実行器を起こさない）"""
        self.order("tidy")
        with unittest.mock.patch.object(self.gates, "named_before", side_effect=AssertionError("走らせない")):
            self.assertEqual(self.texts(named=[self.MEAN3], cases=[]), [])
            self.order("variant")
            self.assertTrue(self.rejected(self.texts(cases=[])))


class OrderQueriesCase(unittest.TestCase):
    """注文を書く段が単位の問いを引く口（orders._queries。F1 の作る物の 2）: 判定の写しの class_query か、裁定 replace_query が
    置き換えた問い"""

    HOW = {"patterns": ["lo ="], "paths": ["*.py"], "count": "lines", "fixed": True}

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.place = pathlib.Path(tmp.name)
        self.orders = kit.load("fix", "orders")
        self.judged = {"how": self.HOW, "counts": "defects", "total": 3}
        (self.place / "judgment.json").write_text(json.dumps({"units": [
            {"key": "a", "class_query": self.judged}, {"key": "b"}]}, ensure_ascii=False), encoding="utf-8")

    def replace(self, query):
        import conflict
        conflict.park(self.place, [{"unit_key": "a", "between": ["a.py:2", "a.py:2"], "why_both_cannot_hold": "問いが正しい形にも当たる",
                                    "which_is_right": "query", "kind": "query_hits_fixed"}], source=conflict.FIX_SOURCE,
                      ruling={"decision": "replace_query", "text": "問いを置き換える", "limits": [], "query": query})

    def test_the_judged_query_goes_to_the_unit(self):
        self.assertEqual(self.orders._queries(self.place, ["a", "b"]), {"a": self.judged})

    def test_a_replaced_query_wins_over_the_judged_one(self):
        how = {**self.HOW, "patterns": ["lo = 1"]}
        self.replace({"how": how, "counts": "population", "hits": ["lo = 1"], "misses": []})
        self.assertEqual(self.orders._queries(self.place, ["a"]), {"a": {"how": how, "counts": "population"}})

    def test_a_replaced_query_without_how_keeps_the_judged_one(self):
        self.replace({"counts": "population", "hits": ["lo = 1"], "misses": []})
        self.assertEqual(self.orders._queries(self.place, ["a"]), {"a": self.judged})


class SchemaCase(unittest.TestCase):
    def load(self, name):
        folder = kit.SHARED if name in ("weapon-order.schema.json", "writer-slots.schema.json", "writer-reply.schema.json") else BLOCK   # 注文・書き手の形は pack の共通（段 2 の D1）
        return json.loads((folder / "schemas" / name).read_text(encoding="utf-8"))

    def test_an_order_and_a_return_hold_the_shape(self):
        order = {"weapon": "variant", "group": "g1", "stage": 1, "since": "abc", "base": "/p/base.json",
                 "units": [{"key": "u", "removes": [], "tests": ["t.py::a"], "checked_as": "tdd"}],
                 "scope": {"allowed_paths": ["a.py"], "out_of_scope": []},
                 "permits": [{"kind": "rewrite", "duty": True, "test": "t.py::a"}]}
        self.assertEqual(validate_schema(order, self.load("weapon-order.schema.json")), [])
        self.assertTrue(validate_schema({**order, "weapon": "direct"}, self.load("weapon-order.schema.json")))
        self.assertTrue(validate_schema({**order, "units": []}, self.load("weapon-order.schema.json")))
        ret = {"weapon": "pin", "status": [{"unit": "u", "status": "done", "why": ""}], "tree": "t",
               "changes": [{"unit": "u", "files": ["t.py"], "what": "足した",
                            "closure": {"sites": [{"site": "s", "test": "t.py::a", "fixed_by": [], "red_seen": "赤"}]}}],
               "evidence": {"named": [], "added": ["t.py::a"], "rewritten": [], "removed": [], "gone": [],
                            "kinds": [{"kind": "docs", "did": "リンクを引いた"}]}}
        self.assertEqual(validate_schema(ret, self.load("weapon-return.schema.json")), [])
        self.assertTrue(validate_schema({**ret, "status": [{"unit": "u", "status": "fixed", "why": ""}]},
                                        self.load("weapon-return.schema.json")))
        ask = {"unit_key": "u", "between": ["a", "b"], "why_both_cannot_hold": "両方は立たない", "which_is_right": "test",
               "kind": "not_red", "correct_lines": []}
        self.assertEqual(validate_schema({**ret, "asks": [ask]}, self.load("weapon-return.schema.json")), [])
        for bad in ({"which_is_right": "maybe"}, {"kind": "other"}):
            with self.subTest(bad=bad):
                self.assertTrue(validate_schema({**ret, "asks": [{**ask, **bad}]}, self.load("weapon-return.schema.json")),
                                "申し出の語は lib/conflicts.schema.json と同じ語だけ")
        self.assertEqual(validate_schema({**order, "base": ""}, self.load("weapon-order.schema.json")), [],
                         "元の結末の無い組（裁定の後の段で写した元の結末が無い時）の注文は base が空")

    def test_precedent_conditions_of_the_writer_reply(self):
        """precedent の 3 つの条件（allOf の if/then。from_judge_row が真でなければ problem・not_found なら searched・not_found でなければ source）"""
        shape = self.load("writer-reply.schema.json")["properties"]["changes"]["items"]["properties"]["precedent"]

        def errors(**p):
            return validate_schema({"verdict": "adopt", "reason": "先行例に従う", "problem": "同じ欠陥", "source": "src.py:1", **p}, shape)
        self.assertEqual(errors(), [])
        self.assertTrue(validate_schema({"verdict": "adopt", "reason": "先行例に従う", "source": "s.py"}, shape),
                        "from_judge_row が真でなければ problem が要る")
        self.assertEqual(validate_schema({"verdict": "adopt", "reason": "判定の行どおり", "from_judge_row": True}, shape), [],
                         "from_judge_row が真なら problem も source も要らない")
        self.assertTrue(errors(verdict="not_found"), "not_found は searched が要る")
        self.assertEqual(errors(verdict="not_found", searched="全体を検索した", source="x" * 4), [])
        self.assertTrue(validate_schema({"verdict": "adopt", "reason": "先行例に従う", "problem": "同じ欠陥"}, shape), "not_found でなければ source が要る")
        self.assertEqual(validate_schema({"verdict": "not_found", "reason": "先行例が無い", "problem": "同じ欠陥", "searched": "全体を検索した"}, shape), [])

    def test_the_writer_reply_evidence_named_is_a_row_of_unit_key_and_test_and_may_be_absent(self):
        """F2 の作る物の 1: evidence.named は単位の鍵つきの行 {unit_key, test}（欠けてよい欄。書かない返答も形に合う）"""
        shape = self.load("writer-reply.schema.json")["properties"]["evidence"]
        self.assertEqual(validate_schema({}, shape), [])
        self.assertEqual(validate_schema({"named": [{"unit_key": "u", "test": "t.py::a"}]}, shape), [])
        self.assertTrue(validate_schema({"named": ["t.py::a"]}, shape), "試験の id だけの並びは単位に結べない")
        self.assertTrue(validate_schema({"named": [{"unit_key": "u"}]}, shape))
        self.assertTrue(validate_schema({"named": [{"unit_key": "u", "test": "t.py::a", "why": "x"}]}, shape))
        self.assertNotIn("required", shape, "evidence の欄は全部欠けてよい")

    def test_writer_slots_shape_requires_every_key(self):
        """段 2 の D1 で .shared/schemas/ に置いた writer-slots は、values・when の全部の鍵を required に持つ"""
        slots = self.load("writer-slots.schema.json")
        self.assertEqual(set(slots["required"]), {"values", "when", "subagents", "summary_file"})
        for key in ("values", "when"):
            self.assertEqual(set(slots["properties"][key]["required"]), set(slots["properties"][key]["properties"]))


class AcceptTableCase(unittest.TestCase):
    """4.4 の 4: 共通の受け付けが注文の索引の型で義務の表を引き、返しを通した時に returns/<k>.json を書き、その凍結を後で照らす"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = _repo(self.tmp, {"docs/a.md": "# a\n", "stats.py": "def mean(xs):\n    return sum(xs) / len(xs)\n",
                                     "test_stats.py": "def test_mean():\n    assert True\n"})
        self.rev = git(self.repo, "rev-parse", "HEAD").strip()
        self.place = self.tmp / "place"
        self.place.mkdir()
        kit.load("fix", "duties")
        from src import board, common, duties, orders
        self.board, self.common, self.duties, self.orders = board, common, duties, orders

    def put(self, rel, doc):
        p = self.place / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc), encoding="utf-8")
        return p

    def ordered(self, weapons: dict, docs: dict, since=""):
        self.put("orders.json", {"sequence": list(docs), "weapons": weapons, "stage": 1, "since": since or self.rev})
        for w, doc in docs.items():
            self.put(f"orders/{w}.json", {"weapon": w, "group": "g1", "stage": 1, "permits": [], **doc})

    def test_static_unit_is_checked_by_its_duties(self):
        """static の単位: 訳が無い・試験のファイルを変えた返答を拒み、文書だけを訳つきで変えた返答は通す（変えてよい種類は計画の項目の
        files から引く）"""
        import planmarks
        planmarks.save(self.place, 1, [{"unit_keys": ["S"], "route": "static", "route_why": "文書の言い回しだけを直す", "tests": [],
                                        "files": [{"path": "docs/a.md"}]}])
        self.ordered({"S": "static"}, {"static": {"units": [{"key": "S", "removes": [], "tests": []}]}})
        (self.repo / "test_stats.py").write_text("def test_mean():\n    assert 1\n", encoding="utf-8")
        reply = {"changes": [{"unit_key": "S", "files": ["docs/a.md", "test_stats.py"]}]}
        got = self.duties.accept_problems(self.place, self.repo, self.rev, reply)
        self.assertEqual({k for k, _ in got}, {"S"}, got)
        self.assertTrue(any("why_untested" in t for _, t in got) and any("試験のファイル" in t for _, t in got), got)
        self.ordered({"S": "static"}, {"static": {"units": [{"key": "S", "removes": [], "tests": []}], "why_untested": "文書の言い回し"}})
        self.assertEqual(self.duties.accept_problems(
            self.place, self.repo, self.rev, {"changes": [{"unit_key": "S", "files": ["docs/a.md"]}],
                                              "evidence": {"kinds": [{"kind": "docs", "did": "リンクを引いた"}]}}), [])

    def test_pin_and_remove_and_keep_duties(self):
        """pin はコードを変えると拒み試験を足さないと拒む。remove は許しの外で試験を消すと拒む。keep の箱は居なくなった試験を拒む"""
        self.ordered({"P": "pin", "R": "remove"}, {"pin": {"units": [{"key": "P", "removes": [], "tests": []}]},
                                                    "remove": {"units": [{"key": "R", "removes": ["x"], "tests": []}]}})
        (self.repo / "test_stats.py").write_text("", encoding="utf-8")
        got = self.duties.accept_problems(self.place, self.repo, self.rev, {"changes": [
            {"unit_key": "P", "files": ["stats.py"]}, {"unit_key": "R", "files": ["test_stats.py"]}]})
        self.assertEqual(sorted({k for k, _ in got}), ["P", "R"], got)
        self.assertTrue(any("test_stats.py::test_mean" in t for k, t in got if k == "R"), got)
        base = {"baseline_cases": [{"classname": "test_stats", "name": "test_mean", "outcome": "passed"}]}
        cases = [{"classname": "test_stats", "name": "test_other", "outcome": "passed"}]
        self.assertEqual(self.duties._vanished(base, cases), ["test_stats::test_mean"])
        self.assertEqual(self.duties.keep_same_result({"vanished": ["test_stats::test_mean"], "permits": []})[:1],
                         [self.duties.keep_same_result({"vanished": ["test_stats::test_mean"]})[0]])

    def test_units_without_orders_are_not_checked(self):
        self.assertEqual(self.duties.accept_problems(self.place, self.repo, self.rev,
                                                     {"changes": [{"unit_key": "S", "files": ["test_stats.py"]}]}), [])

    def test_red_units_follow_the_weapons(self):
        """F135（赤を見ない clean を拒む）は variant・remove・pin の単位の行だけで見る。注文の無い置き場は今のとおり全部の行"""
        import recount
        self.assertIsNone(self.board.red_units(self.place))
        self.ordered({"S": "static", "V": "variant", "T": "tdd"}, {"static": {"units": [{"key": "S"}]}})
        self.assertEqual(self.board.red_units(self.place), {"V"})
        clean = {"fix_closure": {"status": "clean"}, "changes": [
            {"unit_key": "S", "closure": {"sites": [{"red_seen": ""}]}},
            {"unit_key": "V", "closure": {"sites": [{"red_seen": ""}]}}]}
        msg = "閉鎖の実証で赤を一度も見ていない"
        with unittest.mock.patch.object(recount, "ref_problems", return_value=[]):
            self.assertTrue(any(msg in e for e in recount._after_problems(clean, self.place, self.rev, self.repo)))
            self.assertTrue(any(msg in e for e in recount._after_problems(clean, self.place, self.rev, self.repo, {"V"})))
            self.assertEqual(recount._after_problems(clean, self.place, self.rev, self.repo, {"T"}), [])
            seen = {**clean, "changes": [*clean["changes"], {"unit_key": "S", "closure": {"sites": [{"red_seen": "赤"}]}}]}
            self.assertTrue(any(msg in e for e in recount._after_problems(seen, self.place, self.rev, self.repo, {"V"})),
                            "static の単位の赤は variant の単位の赤に数えない")

    def test_accepted_reply_writes_returns_and_their_frozen_files_are_checked(self):
        """返しを通した時に型ごとの returns/<k>.json を書き（tdd は輪の記録の frozen・frozen_tree・suite_made を写す）、後の受け付けは
        その凍ったファイルの、注文の許しの外の書き換えを拒む"""
        record = self.put("tdd-1/record.json", {"frozen": {"test_stats.py": self.common.hashes(self.repo, ["test_stats.py"])["test_stats.py"]},
                                              "frozen_tree": self.rev, "suite_made": ["made.log"],
                                              "units": {"T": {"tests": ["test_stats.py::test_mean"]}}})
        self.ordered({"T": "tdd", "V": "variant"}, {"tdd": {"units": [{"key": "T", "tests": ["test_stats.py::test_mean"]}]},
                                                    "variant": {"units": [{"key": "V", "tests": []}]}})
        (self.repo / "test_new.py").write_text("def test_added():\n    assert True\n", encoding="utf-8")
        got = self.duties.write_returns(self.place, self.repo, self.rev, {"changes": [
            {"unit_key": "T", "files": ["stats.py"]}, {"unit_key": "V", "files": ["test_new.py"]}]}, record=str(record))
        rets = {json.loads(pathlib.Path(p).read_text(encoding="utf-8"))["weapon"]: json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
                for p in got}
        self.assertEqual(sorted(rets), ["tdd", "variant"])
        self.assertEqual((list(rets["tdd"]["frozen"]), rets["tdd"]["suite_made"], rets["tdd"]["added"]),
                         (["test_stats.py"], ["made.log"], ["test_stats.py::test_mean"]))
        self.assertEqual((rets["variant"]["frozen"], rets["variant"]["added"]), ({}, ["test_new.py::test_added"]))
        self.assertEqual(self.duties.frozen_by_returns(self.place, self.repo), [])
        (self.repo / "test_stats.py").write_text("def test_mean():\n    assert 1 == 1\n", encoding="utf-8")
        self.assertTrue(self.duties.frozen_by_returns(self.place, self.repo), "凍ったファイルの許しの外の書き換え")
        self.ordered({"T": "tdd"}, {"tdd": {"units": [{"key": "T", "tests": []}],
                                            "permits": [{"kind": "rewrite", "duty": True, "test": "test_stats.py"}]}})
        self.assertEqual(self.duties.frozen_by_returns(self.place, self.repo), [], "注文の許しの範囲の中は通す")

    def test_returns_carry_removed_tests_and_untested_into_the_output_rows(self):
        """下書き 4.1 の 7: 返しの控えは起点の版に在って今の木に無い試験の id（removed）と注文の why_untested を持ち、修正の出力の
        removed_tests・untested はそこから組む。消しただけのファイルは only_removed に出て、1 回目の段から写した控え（PRIOR_LOOP）は数えない"""
        kit.load("fix", "finish")
        from src import finish
        self.ordered({"R": "remove", "S": "static"}, {"remove": {"units": [{"key": "R", "tests": []}]},
                                                      "static": {"units": [{"key": "S", "tests": []}], "why_untested": "文書の言い回しだけ"}})
        (self.repo / "test_stats.py").write_text("x = 1\n", encoding="utf-8")
        (self.repo / "docs" / "a.md").write_text("# b\n", encoding="utf-8")
        self.duties.write_returns(self.place, self.repo, self.rev, {"changes": [
            {"unit_key": "R", "files": ["test_stats.py"]}, {"unit_key": "S", "files": ["docs/a.md"]}]})
        removed, untested = finish.returned_rows(self.place)
        self.assertEqual(removed, [{"group_id": "g1", "weapon": "remove", "units": ["R"], "tests": ["test_stats.py::test_mean"],
                                    "only_removed": ["test_stats.py"]}])
        self.assertEqual(untested, [{"group_id": "g1", "weapon": "static", "units": ["S"], "why": "文書の言い回しだけ",
                                     "files": [{"path": "docs/a.md", "kind": "docs"}]}])
        (self.repo / "test_stats.py").write_text("def test_other():\n    assert True\n", encoding="utf-8")
        for p in sorted((self.place / "returns").glob("*.json")):
            p.unlink()
        self.duties.write_returns(self.place, self.repo, self.rev, {"changes": [{"unit_key": "R", "files": ["test_stats.py"]}]})
        self.assertEqual(finish.returned_rows(self.place)[0][0]["only_removed"], [], "同じファイルに足した試験が在れば消しただけでない")
        for p in (self.place / "returns").glob("*.json"):
            p.write_text(json.dumps({**json.loads(p.read_text(encoding="utf-8")), self.board.PRIOR_LOOP: True}), encoding="utf-8")
        self.assertEqual(finish.returned_rows(self.place), ([], []))
        (self.place / "returns" / "9.json").write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError):
            finish.returned_rows(self.place)

    def test_before_cases_read_the_group_base(self):
        """確かめ直しが照らす直す前の結末は、組の結果の欄 base の base.json の baseline_cases（輪の状態は読まない）"""
        row = {"classname": "test_stats", "name": "test_mean", "outcome": "failure"}
        base = self.put("g1/base.json", {"baseline_cases": [row]})
        stale = self.put("g1/tdd-1/state.json", {"baseline_cases": [{**row, "outcome": "passed"}]})   # 古い結果の輪の状態は読まない
        self.put("groups.json", {"out_dir": str(self.tmp / "out"), "groups": [{"group_id": "g1"}]})
        (self.tmp / "out" / "g1").mkdir(parents=True)
        (self.tmp / "out" / "g1" / "result.json").write_text(json.dumps(
            {"end_tree": "t", "base": str(base), "tdd_state": str(stale)}), encoding="utf-8")
        self.assertEqual(self.board.before_cases(self.place), [row])

    def test_before_cases_do_not_fall_back_to_the_loop_state(self):
        """組の結果に base が無ければ、輪の状態（tdd_state）の baseline_cases には逃げず、足さない"""
        row = {"classname": "test_stats", "name": "test_mean", "outcome": "failure"}
        stale = self.put("g1/tdd-1/state.json", {"baseline_cases": [row]})
        self.put("groups.json", {"out_dir": str(self.tmp / "out"), "groups": [{"group_id": "g1"}]})
        (self.tmp / "out" / "g1").mkdir(parents=True)
        (self.tmp / "out" / "g1" / "result.json").write_text(json.dumps({"end_tree": "t", "tdd_state": str(stale)}), encoding="utf-8")
        self.assertEqual(self.board.before_cases(self.place), [])

    def test_named_tests_come_from_the_orders(self):
        self.ordered({"T": "tdd"}, {"tdd": {"units": [{"key": "T", "tests": ["t.py::a", "t.py::a"]}],
                                            "permits": [{"kind": "rewrite", "test": "u.py::b"}, {"kind": "remove", "test": "v.py"}]}})
        self.assertEqual(self.orders.named_tests(self.place), ["t.py::a", "u.py::b"])


class RuledOrderCase(unittest.TestCase):
    """4.4 の 5: 裁定の後の直しの注文（orders.write_ruled）・裁定の控えの段の番・段を越えた凍結の照らし（下書き 2.1・4.1 の 6）"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = pathlib.Path(tmp.name)
        self.repo = _repo(self.tmp, {"stats.py": "def mean(xs):\n    return sum(xs) / len(xs)\n",
                                     "test_stats.py": "import os\nLIMIT = 1\n\n\ndef test_mean():\n    assert True\n"})
        self.rev = git(self.repo, "rev-parse", "HEAD").strip()
        self.place = self.tmp / "place"
        self.place.mkdir()
        kit.load("fix", "duties")
        from src import board, common, duties, orders, ruling
        self.board, self.common, self.duties, self.orders, self.ruling = board, common, duties, orders, ruling
        self.hash = common.hashes(self.repo, ["test_stats.py"])["test_stats.py"]

    def put(self, rel, doc):
        p = self.place / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc), encoding="utf-8")
        return p

    def returned(self, k, weapon, keys, *, stage=1, frozen=True, **extra):
        return self.put(f"returns/{k}.json", {"stage": stage, "weapon": weapon, "group": "g1", "tree": self.rev,
                                              "units": [{"key": u, "named": []} for u in keys],
                                              "frozen": {"test_stats.py": self.hash} if frozen else {},
                                              "frozen_tree": self.rev if frozen else "", "suite_made": [], "added": [],
                                              "rewritten": [], **extra})

    def ruled(self, limits, stage=1):
        ruling = {"decision": "fix_test_scope", "text": "期待を直す", "limits": limits, "by": "ruler"}
        if stage is not None:
            ruling["stage"] = stage
        self.put("conflicts.json", {"items": [{"id": "c1", "unit_key": "T", "status": "ruled", "ruling": ruling}]})

    def test_write_ruled_draws_the_same_box_and_writes_checked_as(self):
        """tdd から来た単位は variant の注文に checked_as tdd で、static は static のまま、控えに無い単位は checked_as 無しの variant。
        段の番は ruled（2n）、索引は pass ruled、注文は schema の形"""
        self.returned(1, "tdd", ["T"])
        self.returned(2, "static", ["S"], frozen=False)
        self.put("bases/1/base.json", {"taken": True, "baseline_cases": []})
        self.put("bases/1/accept.json", {})
        seq = self.orders.write_ruled(self.place, ["T", "S", "X"], since=self.rev)
        self.assertEqual(seq, ["static", "variant"])
        idx = json.loads((self.place / "orders.json").read_text(encoding="utf-8"))
        self.assertEqual((idx["weapons"], idx["pass"], idx["stage"], idx["since"]),
                         ({"T": "variant", "S": "static", "X": "variant"}, "ruled", 2, self.rev))
        var = json.loads((self.place / "orders" / "variant.json").read_text(encoding="utf-8"))
        self.assertEqual([(u["key"], u.get("checked_as")) for u in var["units"]], [("T", "tdd"), ("X", None)])
        self.assertEqual(self.orders.checked_as(self.place), {"T": "tdd", "S": "static"})
        schema = json.loads((kit.SHARED / "schemas" / "weapon-order.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_schema(var, schema), [])
        self.assertTrue(self.orders.is_ruled(self.place))
        (self.place / "prior").mkdir()
        self.orders.write_ruled(self.place, ["T"], since=self.rev)
        self.assertEqual(json.loads((self.place / "orders.json").read_text(encoding="utf-8"))["stage"], 4, "2 回目の block の裁定の後は 4")

    def test_a_ruling_records_the_stage_it_saw(self):
        """裁定の控えの欄 stage は 1 回目の段の番（2n−1）で、機械が書く"""
        import conflict
        self.put("conflicts.json", {"items": [{"id": "c1", "unit_key": "T", "status": "parked", "ruling": None}]})
        conflict.apply_rulings(self.place, {"c1": {"decision": "fix_code_as", "text": "直す", "limits": []}}, by="ruler",
                               stage=self.ruling.seen_stage(self.place))
        self.assertEqual(conflict.items(self.place)[0]["ruling"]["stage"], 1)
        (self.place / "prior").mkdir()
        self.assertEqual(self.ruling.seen_stage(self.place), 3)

    def test_the_ruling_scope_frees_only_the_returns_it_saw(self):
        """裁定の範囲の許しは、裁定の段の番以下で返した物を引かず（裁定が見て許した）、後で返した物と、段の番の無い裁定では引く"""
        self.returned(1, "tdd", ["T"])
        self.ruled(["test_stats.py"])
        self.assertEqual([r["kind"] for r in self.orders.permits_for(self.place, [], stage=2, rulings=True)], ["ruled"])
        self.ruled(["test_stats.py"], stage=None)
        self.assertEqual(self.orders.permits_for(self.place, [], stage=2, rulings=True), [], "段の番の無い裁定は厳しい側")
        self.ruled(["test_stats.py"])
        self.returned(2, "tdd", ["T"], stage=2)
        self.assertEqual(self.orders.permits_for(self.place, [], stage=2, rulings=True), [], "裁定より後に返した物は引く")

    def test_the_ruled_pass_rejects_rewrites_of_frozen_tests_outside_the_ruling(self):
        """1 回目の段の輪が凍らせた試験を、裁定の後の段が裁定の範囲の外で書き換えたら拒み、範囲の中は通す"""
        self.returned(1, "tdd", ["T"])
        self.ruled(["other_test.py"])
        self.orders.write_ruled(self.place, ["T"], since=self.rev)
        (self.repo / "test_stats.py").write_text("import os\nLIMIT = 1\n\n\ndef test_mean():\n    assert 1\n", encoding="utf-8")
        self.assertTrue(self.duties.frozen_by_returns(self.place, self.repo))
        self.ruled(["test_stats.py"])
        self.orders.write_ruled(self.place, ["T"], since=self.rev)
        self.assertEqual(self.duties.frozen_by_returns(self.place, self.repo), [])

    def agree(self, n, granted):
        """範囲の相談の合意の行（conflict.ASKED_OP の答え allow）を置き場の trace に足す"""
        import conflict
        with (self.place / "trace.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"op": conflict.ASKED_OP, "id": n, "item": "1", "unit_keys": ["T"], "status": "answered",
                                "decision": "allow", "granted_tests": granted, "reason": "期待を直してよい"}) + "\n")

    def test_an_agreement_made_after_the_stage_head_frees_the_frozen_file(self):
        """段の頭（注文を書いた時）の後に範囲の相談で取れた合意は、前の返しの凍ったファイルの書き換えを許す（相談がその時の凍結を見て
        許した）。段の頭に在った合意は今までどおり前の返しに当たれば引く"""
        self.returned(1, "tdd", ["T"])
        self.agree(1, ["test_stats.py"])
        self.orders.write_ruled(self.place, ["T"], since=self.rev)
        self.assertEqual([r["kind"] for r in self.orders.permits_for(self.place, [], stage=2, rulings=False)], [],
                         "段の頭に在る合意は前の返しの凍結に当たれば引く")
        (self.repo / "test_stats.py").write_text("import os\nLIMIT = 1\n\n\ndef test_mean():\n    assert 1\n", encoding="utf-8")
        self.assertTrue(self.duties.frozen_by_returns(self.place, self.repo))
        self.agree(2, ["test_stats.py"])
        self.assertEqual(self.duties.frozen_by_returns(self.place, self.repo), [], "段の途中で取れた合意は通す")
        self.orders.write_ruled(self.place, ["T"], since=self.rev)
        self.assertTrue(self.duties.frozen_by_returns(self.place, self.repo), "次の段の頭からは段の頭に在った合意")

    def child_of_a_second_block(self, since):
        """2 回目の block の組の子: 親の prior/ を adopt_inputs が子に置き、1 回目の block の tdd の返し（印 prior_pass）を写した物"""
        parent = self.tmp / "parent"
        (parent / "prior").mkdir(parents=True)
        child = self.tmp / "child"
        self.board.adopt_inputs(parent, child)
        self.assertEqual(self.orders.stage_of(child), 3)
        self.place = child
        self.returned(1, "tdd", ["T"], prior_pass=True)
        rows = [{"id": "plan-rewrite-1", "test": "test_stats.py::test_mean", "limit": "test_stats.py:5", "source": "plan"}]
        with unittest.mock.patch.object(self.orders.conflict, "test_permits", return_value=rows):
            permits = self.orders.permits_for(child, [1], stage=3, rulings=False)
        self.assertEqual(permits, [], "1 回目の block の輪が凍らせた試験は、2 回目の block の計画の書き換えの許しから引く")
        self.put("orders.json", {"sequence": ["variant"], "weapons": {"T": "variant"}, "stage": 3, "since": since})
        self.put("orders/variant.json", {"weapon": "variant", "group": "g1", "stage": 3, "units": [{"key": "T"}], "permits": permits})
        return child

    def test_a_second_block_rejects_rewrites_of_the_first_block_frozen_tests(self):
        """1 回目の block の輪が凍らせた試験を、2 回目の block の段で書き換えたら拒む"""
        child = self.child_of_a_second_block(self.rev)
        (self.repo / "test_stats.py").write_text("import os\nLIMIT = 1\n\n\ndef test_mean():\n    assert 1\n", encoding="utf-8")
        self.assertTrue(self.duties.frozen_by_returns(child, self.repo))

    def test_a_second_block_does_not_take_the_first_block_rewrite_as_its_own(self):
        """指摘 M: 1 回目の block が書き換えた試験の差分（段の頭の木 since に在る）は、2 回目の block の書き換えとして拒まない"""
        (self.repo / "test_stats.py").write_text("import os\nLIMIT = 1\n\n\ndef test_mean():\n    assert 1\n", encoding="utf-8")
        child = self.child_of_a_second_block(self.common.snapshot(self.repo))
        self.assertEqual(self.duties.frozen_by_returns(child, self.repo), [])
        (self.repo / "test_stats.py").write_text("import os\nLIMIT = 1\n\n\ndef test_mean():\n    assert 2\n", encoding="utf-8")
        self.assertTrue(self.duties.frozen_by_returns(child, self.repo), "その後の書き換えは拒む")

    def test_rewrites_outside_the_functions_of_a_frozen_file_are_rejected(self):
        """指摘 N: 凍ったファイルの関数の外（import・モジュールの直下の定数）の書き換えも拒む。新しい名の import を足すだけは通す"""
        child = self.child_of_a_second_block(self.rev)
        for text in ("import sys\nLIMIT = 1\n\n\ndef test_mean():\n    assert True\n",
                     "import os\nLIMIT = 2\n\n\ndef test_mean():\n    assert True\n"):
            (self.repo / "test_stats.py").write_text(text, encoding="utf-8")
            self.assertTrue(self.duties.frozen_by_returns(child, self.repo), text)
        (self.repo / "test_stats.py").write_text("import os\nimport sys\nLIMIT = 1\n\n\ndef test_mean():\n    assert True\n",
                                                 encoding="utf-8")
        self.assertEqual(self.duties.frozen_by_returns(child, self.repo), [])

    def test_duties_are_drawn_by_checked_as_and_red_is_not_per_unit_after_a_ruling(self):
        """受け付けは単位の checked_as の型で義務を引き（tdd から来た単位に variant の義務を当てない）、裁定の後の段の注文では F135 を
        返答の全部の行で見る（red_units None）"""
        self.returned(1, "tdd", ["T"], frozen=False)
        self.orders.write_ruled(self.place, ["T"], since=self.rev)
        self.assertIsNone(self.board.red_units(self.place))
        reply = {"changes": [{"unit_key": "T", "files": ["stats.py"]}]}
        flag = (lambda f: ["輪の赤の記録"],)
        # 箱の義務（変える段の change_named_or_gone。両方の型に同じ）は外し、型の義務の表を引く型だけを見る
        with unittest.mock.patch.dict(self.duties.BOX_DUTIES, {"change": ()}):
            with unittest.mock.patch.object(self.duties.MODULES["tdd"], "DUTIES", flag):
                got = self.duties.accept_problems(self.place, self.repo, self.rev, reply)
            self.assertEqual(got, [("T", "型 tdd の単位 T の義務: 輪の赤の記録")])
            with unittest.mock.patch.object(self.duties.MODULES["variant"], "DUTIES", flag):
                self.assertEqual(self.duties.accept_problems(self.place, self.repo, self.rev, reply), [], "variant の義務は当てない")



class AcceptWiringCase(tg.GroupChildScriptsCase):
    """受け付け（fix-accept）を通して、返しの控えの凍結の照らし（duties.frozen_by_returns）と注文の名指し（orders.named_tests）が
    効くこと。組の子の scripts の道具立て（tg.GroupChildScriptsCase）を借り、借りた元の試験は load_tests で外す"""

    def direct_start(self, suite=None):
        """実行器の在る組で、mean の単位を direct に振って修正役の輪の頭まで回す（輪の状態は凍ったファイルを持たない）"""
        self.parent_inputs(str(suite or self.suite))
        self.start()
        got = self.step({"phase": "route", "units": [{"unit_key": tg.MEAN, "route": "direct", "why": "期待の書き換えだけで先に書ける試験が無い"}]})
        self.assertTrue(got["ok"], got)
        self.assertTrue(self.run_script("fix_prep")["go"])

    def fix_mean(self):
        stats = self.repo / "stats.py"
        stats.write_text(stats.read_text(encoding="utf-8").replace("(len(xs) - 1)", "len(xs)"), encoding="utf-8")

    def test_the_accept_rejects_a_rewrite_of_a_file_a_prior_return_froze(self):
        """前の型の返しの控えが凍らせた試験のファイルを、注文の許しの外で書き換えた返答を拒む（輪の状態の凍結の照らし check_frozen は
        何も凍らせていないので、返しの控えの照らしだけが拒む）"""
        import hashlib
        self.direct_start()
        rev = git(self.repo, "rev-parse", "HEAD").strip()
        test_file = self.repo / "test_stats.py"
        (self.place / "returns").mkdir(exist_ok=True)
        (self.place / "returns" / "1.json").write_text(json.dumps(
            {"stage": 1, "weapon": "tdd", "group": "g1", "tree": rev, "units": [{"key": "X", "named": []}],
             "frozen": {"test_stats.py": hashlib.sha256(test_file.read_bytes()).hexdigest()}, "frozen_tree": rev, "suite_made": [],
             "added": [], "rewritten": [], "removed": [], "files": [], "why_untested": ""}), encoding="utf-8")
        self.fix_mean()
        test_file.write_text(test_file.read_text(encoding="utf-8").replace("clamp(15, 0, 10), 10", "clamp(15, 0, 10), 10.0"),
                             encoding="utf-8")
        out = self.accept({"changes": [tg._change(tg.MEAN, ["stats.py", "test_stats.py"])]})
        self.assertFalse(out["ok"], out)
        self.assertIn("test_stats.py", self.frozen_reason(out["reason"]))

    def test_the_accept_runs_the_tests_the_order_names(self):
        """注文の単位の行が名指した試験は、変更から辿れなくても（import で結ばない）受け付けが走らせ、元で緑だった物を赤にする直しを
        拒む"""
        (self.repo / "test_source.py").write_text(
            "import unittest\n\n\nclass TestSource(unittest.TestCase):\n    def test_old_denominator(self):\n"
            "        with open('sta' + 'ts.py', encoding='utf-8') as f:\n            self.assertIn('(len(xs) - 1)', f.read())\n",
            encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "変更から辿れない試験")
        from tests.blocks.fix.support import DIFF_SUITE
        suite = self.tmp / "diff-suite.py"   # -k で選んだ試験だけを回す実行器（一式を回す SUITE では名指しの効きが見えない）
        suite.write_text(DIFF_SUITE.format(heed="True"), encoding="utf-8")
        self.direct_start(suite)
        order = self.place / "orders" / "variant.json"
        doc = json.loads(order.read_text(encoding="utf-8"))
        doc["units"][0]["tests"] = ["test_source.py::TestSource::test_old_denominator"]
        order.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        self.fix_mean()
        out = self.accept({"changes": [tg._change(tg.MEAN, ["stats.py"])]})
        self.assertFalse(out["ok"], out)
        self.assertIn("test_old_denominator", out["reason"])

    def whole_return(self, reply, *, ok=True, report=(), weapon="pin"):
        """型の block の返りまるごと（writer_out の形 {ok, reason, reply: <pointer>, report}）。返答は組の子の run の置き場に書く。
        ok が偽の返りは reply が null で、report が reason と同じ 1 行（docs/plans/2026-10-24-fix-weapons.md の 11.3）"""
        if not ok:
            reason = "書き手の返答が無い（書き手の AI の node か、返答を置く node pin-save が落ちた）"
            return json.dumps({"ok": False, "reason": reason, "reply": None, "report": [reason]})
        path = self.place / f"w-{weapon}" / "reply-1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(support.reply_json(reply), encoding="utf-8")
        rel = path.resolve().relative_to(self.art.resolve()).as_posix()
        return json.dumps({"ok": ok, "reason": "", "reply": {"type": "archon_artifact", "run_id": tg.RUN, "path": rel},
                           "report": list(report)})

    def test_the_accept_reads_a_writer_blocks_whole_return_and_keeps_its_report(self):
        """受け付けは型の block の返りまるごとを受け（E5。ok・reason・reply・report の 4 つとも読む）、report の行を置き場の
        writer-report.json に型の名と積む。積んだ行は finish の report に載る（WriterReportCase）"""
        self.direct_start()
        weapon = writers.current(self.place)
        out = self.run_script("fix_accept", reply_pin=self.whole_return({"changes": []}, report=["型の block の報告の 1 行"]),
                              consulted="true", iteration="1")
        self.assertEqual(out["reason"], tg._src("board").CONSULTED, out)
        rows = json.loads((self.place / "writer-report.json").read_text(encoding="utf-8"))
        self.assertEqual(rows, [{"weapon": weapon, "line": "型の block の報告の 1 行"}])

    # ---- 型の義務の表に足した照らし（F1。docs/plans/2026-10-24-fix-weapons.md の 11.6 の F1 の縛る試験の 1・2）
    HOW = {"patterns": ["len(xs) - 1"], "paths": ["stats.py"], "count": "lines", "fixed": True}

    def weapon_start(self, weapon, unit_extra=None):
        """mean の単位を型 weapon の注文に書き直して（注文を書く段の後・修正の輪の頭の前）、修正の輪の頭まで回す"""
        unit_extra = dict(unit_extra or {})
        query = unit_extra.pop("class_query", None)
        self.parent_inputs(str(self.suite))
        self.start()
        judgment = json.loads((self.place / "judgment.json").read_text(encoding="utf-8"))
        judgment["units"][0].pop("class_query", None)
        if query:   # 判定の写しにだけ置く。注文の単位へは注文を書く段（orders._queries・_order）が写す
            judgment["units"][0]["class_query"] = query
        (self.place / "judgment.json").write_text(json.dumps(judgment, ensure_ascii=False), encoding="utf-8")
        got = self.step({"phase": "route", "units": [{"unit_key": tg.MEAN, "route": "direct", "why": "期待の書き換えだけで先に書ける試験が無い"}]})
        self.assertTrue(got["ok"], got)
        orders_dir = self.place / "orders"
        (made,) = list(orders_dir.glob("*.json"))
        doc = json.loads(made.read_text(encoding="utf-8"))
        made.unlink()
        self.assertEqual(doc["units"][0].get("class_query"), query, "注文を書く段が判定の写しの問いを注文の単位に写す")
        doc["weapon"] = weapon
        doc["units"][0].update(unit_extra)
        (orders_dir / f"{weapon}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        idx = json.loads((self.place / "orders.json").read_text(encoding="utf-8"))
        (self.place / "orders.json").write_text(json.dumps({**idx, "sequence": [weapon], "weapons": {tg.MEAN: weapon}}), encoding="utf-8")
        self.assertTrue(self.run_script("fix_prep")["go"])
        self.assertEqual(writers.current(self.place), weapon)

    def weapon_accept(self, weapon, reply):
        return self.run_script("fix_accept", **{f"reply_{weapon}": self.whole_return(reply, weapon=weapon)}, consulted="false", iteration="1")

    def duty_lines(self, out) -> list:
        return [ln for ln in out["reason"].splitlines() if f"型 {writers.current(self.place)} の単位 {tg.MEAN} の義務" in ln]

    def test_the_accept_rejects_a_static_return_without_a_row_for_the_kind_it_touched(self):
        """static: 差分に docs の種類が在り、evidence.kinds に docs の行が無い返答を拒む。docs の行を書いた同じ返答は通す"""
        import planmarks
        planmarks.save(self.place, 1, [{"unit_keys": [tg.MEAN], "route": "static", "route_why": "文書の言い回しだけを直す", "tests": [],
                                        "files": [{"path": "docs/a.md"}]}])
        self.weapon_start("static", {"why": "文書の言い回しだけを直す"})
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "a.md").write_text("# a\n", encoding="utf-8")
        change = tg._change(tg.MEAN, ["docs/a.md"])
        bad = self.weapon_accept("static", {"changes": [change]})
        self.assertIn("evidence.kinds に差分の種類 ['docs'] の確かめの行が無い", bad["reason"])
        good = self.weapon_accept("static", {"changes": [change], "evidence": {"kinds": [{"kind": "docs", "did": "リンクを引いた"}]}})
        self.assertEqual(self.duty_lines(good), [], good)

    def test_the_accept_rejects_a_pin_return_with_a_test_no_site_binds(self):
        """pin: 足した試験に、test がその id の（赤を見た）sites の行が無い返答を拒む。test に id を書いた同じ形の返答は通す"""
        self.weapon_start("pin")
        test_file = self.repo / "test_stats.py"
        test_file.write_text(test_file.read_text(encoding="utf-8").replace("\n\nif __name__", tg.NEW_TEST + "\n\nif __name__"), encoding="utf-8")
        change = tg._change(tg.MEAN, ["test_stats.py"])
        bad = self.weapon_accept("pin", {"changes": [change]})
        self.assertIn("縛るコードを壊して赤を見た sites の行（test にその id）が無い", bad["reason"])
        (test_id,) = {t for t in re.findall(r"test_stats\.py::[\w:]+", bad["reason"]) if t.endswith("test_mean_of_two")}
        site = {"site": "stats.py:5", "red_seen": True, "test": test_id}
        good = self.weapon_accept("pin", {"changes": [{**change, "closure": {**change["closure"], "sites": [site]}}]})
        self.assertFalse([ln for ln in self.duty_lines(good) if "sites の行" in ln], good)

    MEAN3 = "test_stats.py::TestStats::test_mean_of_three"   # 起点の木で failure（分母の誤り）・直した木で緑
    NAMED = {"evidence": {"named": [{"unit_key": tg.MEAN, "test": MEAN3}]}}   # 変える段の箱の義務（F2）を満たす名指し

    def variant_change(self, site, **extra):
        change = tg._change(tg.MEAN, ["stats.py"])
        return {**change, "closure": {**change["closure"], "sites": [site]}, **extra}

    def test_the_accept_rejects_variant_sites_that_miss_the_query_or_the_diff(self):
        """variant: class_query の在る単位の at が当たりの行に無い返答・fixed_by が差分の塊と重ならない返答を拒み、書いた返答は通す"""
        self.weapon_start("variant", {"class_query": {"how": self.HOW, "counts": "defects", "total": 1}})
        self.fix_mean()
        site = {"site": "stats.py:5", "red_seen": True, "path": "stats.py", "at": "stats.py:5", "fixed_by": ["stats.py:5-5"]}
        good = self.weapon_accept("variant", {"changes": [self.variant_change(site)], **self.NAMED})
        self.assertEqual(self.duty_lines(good), [], good)
        self.assertTrue(good["ok"], "最後の回でない 1 回目で通る（最後の回の諦めで空になった訳ではない）")
        for field, value, text in (("at", "stats.py:9", "が判定の問いの当たりの行に無い"),
                                   ("fixed_by", ["stats.py:9-9"], "が差分の塊と重ならない")):
            with self.subTest(field=field):
                out = self.weapon_accept("variant", {"changes": [self.variant_change({**site, field: value})], **self.NAMED})
                self.assertTrue(any(text in ln for ln in self.duty_lines(out)), out["reason"])

    def test_the_accept_asks_each_variant_unit_for_its_own_red(self):
        """variant: 同じ周のほかの単位だけが赤を見た返答を拒む（周の全体の赤を見る F135 は通す）"""
        import recount
        site = {"site": "stats.py:5", "red_seen": False}
        self.weapon_start("variant", {"class_query": {"how": self.HOW, "counts": "defects", "total": 1}})
        self.fix_mean()
        out = self.weapon_accept("variant", {"changes": [self.variant_change(site)], **self.NAMED})
        self.assertTrue(any("sites のどれにも赤を見た記録（red_seen）が無い" in ln for ln in self.duty_lines(out)), out["reason"])
        other = {"unit_key": "other", "closure": {"sites": [{"site": "x", "red_seen": True}]}}
        self.assertEqual(recount._after_problems({"fix_closure": {"status": "clean"}, "changes": [self.variant_change(site), other]},
                                                 self.place, "HEAD", self.repo, set()), [], "周の全体の赤を見る照らしは通る（だから単位ごとの照らしが要る）")

    def test_the_accept_rejects_variant_sites_without_fixed_by(self):
        """variant: 照らす単位（問いを行で結べる単位）で、fixed_by が無い行・空の行を拒む"""
        self.weapon_start("variant", {"class_query": {"how": self.HOW, "counts": "defects", "total": 1}})
        self.fix_mean()
        site = {"site": "stats.py:5", "red_seen": True, "path": "stats.py", "at": "stats.py:5"}
        for gone in ({}, {"fixed_by": []}):
            with self.subTest(fixed_by=gone):
                out = self.weapon_accept("variant", {"changes": [self.variant_change({**site, **gone})], **self.NAMED})
                self.assertTrue(any("fixed_by が無い" in ln for ln in self.duty_lines(out)), out["reason"])

    def test_a_unit_the_query_cannot_bind_to_lines_skips_the_at_check_but_not_the_red(self):
        """問いを行で結べない単位（ファイルごとの数が合計と合わない）は at と fixed_by の在る無しを照らさず、赤を見た site を求める。
        書いた fixed_by は差分の塊と重なるかを照らす"""
        loose = {"how": self.HOW, "counts": "defects", "total": 5}
        self.weapon_start("variant", {"class_query": loose})
        self.fix_mean()
        site = {"site": "stats.py:5", "red_seen": True, "path": "stats.py", "at": "stats.py:9", "fixed_by": ["stats.py:5-5"]}
        out = self.weapon_accept("variant", {"changes": [self.variant_change(site)], **self.NAMED})
        self.assertEqual(self.duty_lines(out), [], out["reason"])
        out = self.weapon_accept("variant", {"changes": [self.variant_change({k: v for k, v in site.items() if k != "fixed_by"})], **self.NAMED})
        self.assertEqual(self.duty_lines(out), [], out["reason"])
        out = self.weapon_accept("variant", {"changes": [self.variant_change({**site, "fixed_by": ["stats.py:9-9"]})], **self.NAMED})
        self.assertTrue(any("が差分の塊と重ならない" in ln for ln in self.duty_lines(out)), out["reason"])
        out = self.weapon_accept("variant", {"changes": [self.variant_change({**site, "red_seen": False})], **self.NAMED})
        self.assertEqual(len(self.duty_lines(out)), 1, out["reason"])

    def test_a_unit_without_a_query_skips_the_sites_shape_but_not_the_red(self):
        """問いの無い単位（判定が class_query を返していない）は sites_shape が素通りし、unit_red だけが当たる"""
        self.weapon_start("variant")
        self.fix_mean()
        site = {"site": "stats.py:5", "red_seen": True, "path": "stats.py"}
        out = self.weapon_accept("variant", {"changes": [self.variant_change(site)], **self.NAMED})
        self.assertEqual(self.duty_lines(out), [], out["reason"])
        out = self.weapon_accept("variant", {"changes": [self.variant_change({**site, "red_seen": False})], **self.NAMED})
        self.assertEqual(len(self.duty_lines(out)), 1, out["reason"])
        self.assertTrue(any("赤を見た記録" in ln for ln in self.duty_lines(out)), out["reason"])

    # ---- 変える段の箱の義務（F2。docs/plans/2026-10-24-fix-weapons.md の 11.6 の F2 の縛る試験の 1・3）
    BY_NAME = '''
import pathlib, sys, unittest, xml.etree.ElementTree as ET
sys.dont_write_bytecode = True
sys.path.insert(0, ".")
out, args = sys.argv[1], sys.argv[2:]
named = [a for i, a in enumerate(args) if "::" in a and (i == 0 or args[i - 1] != "-k")]
words = [w.strip() for w in args[args.index("-k") + 1].split(" or ")] if "-k" in args else None
rows = []
class R(unittest.TestResult):
    def addSuccess(self, t): rows.append((t, None, ""))
    def addFailure(self, t, e): rows.append((t, "failure", str(e[1])))
    def addError(self, t, e): rows.append((t, "error", str(e[1])))
    def addSkip(self, t, r): rows.append((t, "skipped", ""))
loader = unittest.defaultTestLoader
def flat(s):
    for t in s:
        yield from (flat(t) if isinstance(t, unittest.TestSuite) else [t])
if named:   # 名指しだけを回す（起点の木の結末）
    for n in named:
        path, _, rest = n.partition("::")
        mod = pathlib.Path(path).resolve().relative_to(pathlib.Path.cwd().resolve()).with_suffix("").as_posix().replace("/", ".")
        loader.loadTestsFromName(mod + "." + rest.replace("::", ".")).run(R())
else:   # 受け付けの回: -k の語を id に含む試験だけ（無ければ全部）
    for t in flat(loader.discover(".", pattern="test_*.py", top_level_dir=".")):
        if words is None or any(w in t.id() for w in words):
            t.run(R())
root = ET.Element("testsuite")
for t, kind, message in rows:
    cls, name = t.id().rsplit(".", 1)
    tc = ET.SubElement(root, "testcase", classname=cls, name=name)
    if kind:
        ET.SubElement(tc, kind, message=message)
ET.ElementTree(root).write(out)
sys.exit(0 if all(k in (None, "skipped") for _, k, _ in rows) else 1)
'''
    NO_OLD = ("import unittest\n\n\nclass TestSource(unittest.TestCase):\n    def test_no_old_denominator(self):\n"
              "        with open('sta' + 'ts.py', encoding='utf-8') as f:\n            self.assertNotIn('(len(xs) - 1)', f.read())\n")

    def test_the_accept_rejects_a_variant_return_that_names_no_test_and_removes_no_name(self):
        """variant: 名指しの試験も消す名も無い単位を拒む（変える段の箱の義務）。起点の木で赤・返した木で緑の試験を evidence.named に書いた同じ返答は
        1 回目で通る"""
        self.weapon_start("variant", {"class_query": {"how": self.HOW, "counts": "defects", "total": 1}})
        self.fix_mean()
        site = {"site": "stats.py:5", "red_seen": True, "path": "stats.py", "at": "stats.py:5", "fixed_by": ["stats.py:5-5"]}
        bad = self.weapon_accept("variant", {"changes": [self.variant_change(site)]})
        self.assertTrue(any("名指しの試験が起点の木で赤（failure）" in ln for ln in self.duty_lines(bad)), bad["reason"])
        good = self.weapon_accept("variant", {"changes": [self.variant_change(site)], **self.NAMED})
        self.assertEqual(self.duty_lines(good), [], good)
        self.assertTrue(good["ok"], good)

    def test_the_accept_rejects_a_named_test_that_already_passes_at_the_base(self):
        self.weapon_start("variant", {"class_query": {"how": self.HOW, "counts": "defects", "total": 1}})
        self.fix_mean()
        site = {"site": "stats.py:5", "red_seen": True, "path": "stats.py", "at": "stats.py:5", "fixed_by": ["stats.py:5-5"]}
        clamp = "test_stats.py::TestStats::test_clamp_within_range"
        out = self.weapon_accept("variant", {"changes": [self.variant_change(site)],
                                             "evidence": {"named": [{"unit_key": tg.MEAN, "test": clamp}]}})
        self.assertTrue(any("名指しの試験が起点の木で赤（failure）" in ln for ln in self.duty_lines(out)), out["reason"])

    def test_a_named_test_in_a_file_the_change_does_not_reach_enters_the_selection_and_the_returns(self):
        """evidence.named の試験は受け付けの試験の選びに入る（変更から辿れないファイルの試験も走る）。書かなければ走らず、返した木の結末が無いので
        拒む。通した返答の evidence.named は returns/ の units[].named に入る"""
        (self.repo / "test_source.py").write_text(self.NO_OLD, encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "変更から辿れない試験")
        self.suite.write_text(self.BY_NAME, encoding="utf-8")
        self.weapon_start("variant", {"class_query": {"how": self.HOW, "counts": "defects", "total": 1}})
        self.fix_mean()
        site = {"site": "stats.py:5", "red_seen": True, "path": "stats.py", "at": "stats.py:5", "fixed_by": ["stats.py:5-5"]}
        named = "test_source.py::TestSource::test_no_old_denominator"
        out = self.weapon_accept("variant", {"changes": [self.variant_change(site)]})
        self.assertTrue(any("名指しの試験が起点の木で赤（failure）" in ln for ln in self.duty_lines(out)), out["reason"])
        good = self.weapon_accept("variant", {"changes": [self.variant_change(site)],
                                              "evidence": {"named": [{"unit_key": tg.MEAN, "test": named}]}})
        self.assertEqual(self.duty_lines(good), [], good)
        self.assertTrue(good["ok"], good)
        (ret,) = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((self.place / "returns").glob("*.json"))]
        self.assertEqual([u["named"] for u in ret["units"]], [[named]])

    def files(self) -> dict:
        """組の子の run の置き場のファイルの名と中身の組（走らせる前と後を比べる。ファイルの名の表を持たない）"""
        return {p.relative_to(self.art).as_posix(): p.read_bytes() for p in sorted(self.art.rglob("*")) if p.is_file()}

    def test_a_script_given_a_writer_block_return_whose_ok_is_false_stops_before_writing(self):
        """縛る試験の 10: 受け取る側の 3 つの script は、型の block の返りの ok が偽なら非 0 で終わり、place を変えない（単位の結末の重ね・
        型を済ませた印・却下の控えを書かない）。文は include の id と block の返りの reason を名指す（11.3 の「落ちた周の守り」）"""
        self.direct_start()
        for script, pass_, extra in (("consult_check", "first", {"pass": "first"}),
                                     ("fix_accept", "first", {"consulted": "false", "iteration": "1"}),
                                     ("consult_check", "ruled", {"pass": "ruled"}),
                                     ("fix_ruled_accept", "ruled", {"consulted": "false", "iteration": "1"})):
            with self.subTest(script=script, pass_=pass_):
                before = self.files()
                err = self.run_script(script, ok=False, reply_pin=self.whole_return({}, ok=False), **extra)
                self.assertIn(writers.node(pass_, "pin"), err)
                self.assertIn("書き手の返答が無い", err)
                self.assertEqual(self.files(), before, "ok が偽の返りを受けた script は place に何も書かない")


class ReplyOfCase(unittest.TestCase):
    """writers.reply_of の結末の欄 ok の読み（縛る試験の 10。11.4 の 3）"""
    REASON = "書き手の返答が無い"

    def test_a_block_whose_ok_is_false_stops_with_the_include_id_and_the_reason(self):
        for pass_ in ("first", "ruled"):
            with self.subTest(pass_=pass_):
                got = {"ok": False, "reason": self.REASON, "reply": None, "report": [self.REASON]}
                with self.assertRaises(ValueError) as caught:
                    writers.reply_of({"pin": got}, pass_)
                self.assertIn(writers.node(pass_, "pin"), str(caught.exception))
                self.assertIn(f"weapon-{writers.block_of('pin')}", str(caught.exception))
                self.assertIn(self.REASON, str(caught.exception))

    def test_a_skipped_block_is_not_read_for_ok(self):
        """飛んだ型の block（if_skipped: null で None）は ok を見ない。どれも起きていなければ (None, [])"""
        self.assertEqual(writers.reply_of({"pin": None, "tidy": None, "variant": None}, "first"), (None, []))

    def test_the_variant_block_is_read_like_the_other_blocks(self):
        """variant も型の block: 返りまるごとの reply の pointer を解いて返答と報告の行を返し、ok が偽ならその include の id で落ちる"""
        with tempfile.TemporaryDirectory() as tmp:
            place = pathlib.Path(tmp)
            reply = json.loads(support.reply_json({"changes": []}))
            (place / "reply-1.json").write_text(json.dumps(reply), encoding="utf-8")
            got = {"ok": True, "reason": "", "reply": {"type": "archon_artifact", "run_id": "wf-w", "path": "reply-1.json"}, "report": ["下請けの報告"]}
            with unittest.mock.patch.dict(os.environ, {"ARTIFACTS_DIR": str(place), "WORKFLOW_ID": "wf-w"}):
                self.assertEqual(writers.reply_of({"variant": got}, "first"), (reply, ["下請けの報告"]))
            with self.assertRaisesRegex(ValueError, "w-variant"):
                writers.reply_of({"variant": {**got, "ok": False, "reason": "返答が無い", "reply": None}}, "first")
            with self.assertRaisesRegex(ValueError, "wr-variant"):
                writers.reply_of({"variant": {**got, "ok": False, "reason": "返答が無い", "reply": None}}, "ruled")


class WriterReportCase(unittest.TestCase):
    """型の block の書き手の報告の行が、組の子の結果を通って親の finish の report に載る（board.add_writer_report・writer_report_rows・
    group_result の writer_report・report.writer_lines）"""

    def test_the_lines_go_from_a_group_child_to_the_parent_report(self):
        board, report = tg._src("board"), tg._src("report")
        with tempfile.TemporaryDirectory() as tmp:
            child, parent = pathlib.Path(tmp) / "child", pathlib.Path(tmp) / "parent"
            child.mkdir()
            parent.mkdir()
            board.add_writer_report(child, "pin", ["固定の 1 行"])
            board.add_writer_report(child, "tidy", [])
            result = board.group_result({"group_id": "g1", "unit_ids": []}, start_tree="", end_tree="", tdd=None,
                                        writer_report=board.writer_report_rows(child))
            board.add_writer_report(parent, "static", ["裁定の後の 1 行"])
            rows = board.writer_report_rows(parent, [result])
            self.assertEqual(report.writer_lines(rows), ["書き手 pin（組 g1）: 固定の 1 行", "書き手 static: 裁定の後の 1 行"])
            self.assertEqual(report.lines(parent, [], [], writers=rows)[:2], report.writer_lines(rows))


class ReadStagesCase(unittest.TestCase):
    """読んだ証拠の段の頭の印（board.read_stages）は、修正の block が自分の place に書くファイルだけ（型の block の place の中を
    読まない。E4）。型の block は 6 つとも渡した 1 回目の slots"""

    def test_the_marks_are_files_the_fix_block_writes_in_its_own_place(self):
        board = tg._src("board")
        with tempfile.TemporaryDirectory() as tmp:
            place = pathlib.Path(tmp)
            (place / "w-pin").mkdir()
            (place / "w-pin" / "pin-prompt-1.md").write_text("型の block の指示\n", encoding="utf-8")
            stages = {role: (mark, launched) for role, mark, launched in board.read_stages(place)}
            self.assertEqual({mark.parent for mark, _ in stages.values()}, {place})
            self.assertIsNone(stages["w-pin"][1], "型の block の place の中の指示書は印にしない")
            (place / "slots-w-pin-1.json").write_text("{}", encoding="utf-8")
            (place / "slots-w-variant-1.json").write_text("{}", encoding="utf-8")
            stages = {role: (mark, launched) for role, mark, launched in board.read_stages(place)}
            self.assertEqual(stages["w-pin"], (place / "slots-w-pin-1.json",) * 2)
            self.assertEqual(stages["w-variant"], (place / "slots-w-variant-1.json",) * 2, "variant も型の block の印")
            self.assertNotIn("variant", stages)
            self.assertIsNone(stages["wr-pin"][1])


def load_tests(loader, tests, pattern):
    """借りた tg.GroupChildScriptsCase の試験を回し直さない（AcceptWiringCase はこのクラスに書いた試験だけ）"""
    suite = unittest.TestSuite()
    for case in [v for v in globals().values() if isinstance(v, type) and issubclass(v, unittest.TestCase)
                 and v.__module__ == __name__]:
        names = loader.getTestCaseNames(case)
        if case is AcceptWiringCase:
            names = [n for n in names if n in case.__dict__]
        suite.addTests(case(n) for n in names)
    return suite


if __name__ == "__main__":
    unittest.main()
