"""直し方の型の段 1（docs/plans/2026-10-24-fix-weapons.md の 4.4）の、型を問わない部品の試験。

- route から型を引く表（src/route.weapon_of。4.1 の 3 の 5 行）と、振り分けの AI に渡す単位の集まり（route_keys）
- 試験が無いかの印 no_tests の決め（src/basecase._no_tests。4.4 の作る物 12 の 5 つの場合と、宣言を読む木）。どの試験も対象の試験を
  走らせない（持ち主の決め base-runs-nothing。走らせるのは試験の一覧のコマンドだけ）
- 確かめの表（src/duties.py）の形の決まりと、型の義務の関数（static・pin・remove・variant・rebuild）
- 口の形（schemas/weapon-order.schema.json・weapon-return.schema.json）
- 共通の受け付けが型の義務の表を引く口（duties.accept_problems）・赤を見ない clean の照らしを当てる単位（board.red_units・
  recount の red_units）・返しの控えを書く所（duties.write_returns）・返しの控えの凍結の照らし（duties.frozen_by_returns）・
  受け付けの名指しの出どころ（orders.named_tests）（4.4 の 4）
"""
import json
import pathlib
import sys
import tempfile
import unittest
import unittest.mock

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
        """static の単位: 訳が無い・試験のファイルを変えた返答を拒み、文書だけを訳つきで変えた返答は通す"""
        self.ordered({"S": "static"}, {"static": {"units": [{"key": "S", "removes": [], "tests": []}]}})
        (self.repo / "test_stats.py").write_text("def test_mean():\n    assert 1\n", encoding="utf-8")
        reply = {"changes": [{"unit_key": "S", "files": ["docs/a.md", "test_stats.py"]}]}
        got = self.duties.accept_problems(self.place, self.repo, self.rev, reply)
        self.assertEqual([k for k, _ in got], ["S", "S"], got)
        self.assertTrue(any("why_untested" in t for _, t in got) and any("試験のファイル" in t for _, t in got), got)
        self.ordered({"S": "static"}, {"static": {"units": [{"key": "S", "removes": [], "tests": []}], "why_untested": "文書の言い回し"}})
        self.assertEqual(self.duties.accept_problems(self.place, self.repo, self.rev,
                                                     {"changes": [{"unit_key": "S", "files": ["docs/a.md"]}]}), [])

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
        """返しを通した時に型ごとの returns/<k>.json を書き（tdd は輪の状態の frozen・frozen_tree・suite_made を写す）、後の受け付けは
        その凍ったファイルの、注文の許しの外の書き換えを拒む"""
        state = self.put("tdd-1/state.json", {"frozen": {"test_stats.py": self.common.hashes(self.repo, ["test_stats.py"])["test_stats.py"]},
                                              "frozen_tree": self.rev, "suite_made": ["made.log"],
                                              "units": {"T": {"tests": ["test_stats.py::test_mean"]}}})
        self.ordered({"T": "tdd", "V": "variant"}, {"tdd": {"units": [{"key": "T", "tests": ["test_stats.py::test_mean"]}]},
                                                    "variant": {"units": [{"key": "V", "tests": []}]}})
        (self.repo / "test_new.py").write_text("def test_added():\n    assert True\n", encoding="utf-8")
        got = self.duties.write_returns(self.place, self.repo, self.rev, {"changes": [
            {"unit_key": "T", "files": ["stats.py"]}, {"unit_key": "V", "files": ["test_new.py"]}]}, state=str(state))
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
        stale = self.put("g1/tdd-1/state.json", {"baseline_cases": [{**row, "outcome": "passed"}]})
        self.put("groups.json", {"out_dir": str(self.tmp / "out"), "groups": [{"group_id": "g1"}]})
        (self.tmp / "out" / "g1").mkdir(parents=True)
        (self.tmp / "out" / "g1" / "result.json").write_text(json.dumps(
            {"end_tree": "t", "base": str(base), "tdd_state": str(stale)}), encoding="utf-8")
        self.assertEqual(self.board.before_cases(self.place), [row])

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
        schema = json.loads((BLOCK / "schemas" / "weapon-order.schema.json").read_text(encoding="utf-8"))
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
        with unittest.mock.patch.object(self.duties.MODULES["tdd"], "DUTIES", flag):
            got = self.duties.accept_problems(self.place, self.repo, self.rev, reply)
        self.assertEqual(got, [("T", "型 tdd の単位 T の義務: 輪の赤の記録")])
        with unittest.mock.patch.object(self.duties.MODULES["variant"], "DUTIES", flag):
            self.assertEqual(self.duties.accept_problems(self.place, self.repo, self.rev, reply), [], "variant の義務は当てない")


if __name__ == "__main__":
    unittest.main()
