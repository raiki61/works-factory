"""修正案の項目の works 側の欄（planmarks）。役の型への重ね・欠けと誤りの行・テストの定義の行の引き・欄を外す受け付けの口・
盤面の控えの周つきの読み書きを、関数を直に呼んで見る（FAST。種は dev の target-seed を一時の置き場に写すだけ。git・盤面・
子のプロセスなし。writes.base_test_texts の試験だけは git の写しを使う）。test_stats.py の test_mean_of_three の定義は 8 行目、test_clamp_within_range は 11 行目"""
import copy
import json
import pathlib
import shutil
import sys
import tempfile
import types
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))
import planmarks  # noqa: E402

SEED = LIB.parent / "tests" / "e2e" / "target-seed"
MEAN = "stats.py mean: 分母が len(xs) - 1 になっている"
PLAN_KEYS = {"unit_keys", "approach", "files", "shrink_first", "narrows"}   # 写しの graph の修正案の項目の欄


def item(**over):
    base = {"unit_keys": [MEAN], "approach": "x" * 20, "files": [], "shrink_first": "y" * 20, "narrows": [],
            "route": "tdd", "route_why": "",
            "tests": [{"id": "test_stats.py::TestStats::test_mean_of_two", "behavior": "2 つの値の平均を返す",
                       "path": "stats.mean を直に呼ぶ（mock なし）", "red_kind": "assertion", "red_why": "今は len-1 で割り 3.0 になる"}],
            "rewrite_tests": [], "refactor": {"declared": False, "why": ""}, "allowed_paths": ["stats.py"], "out_of_scope": []}
    return {**base, **over}


def fadd(name):
    """files の symbols の行（足す）"""
    return {"name": name, "change": "add"}


def frm(name, why="古い名で、呼び手は新しい名に寄せた"):
    """files の symbols の行（消す。消す訳 why つき）"""
    return {"name": name, "change": "remove", "why": why}


def frow(path="stats.py", *symbols, op="modify", **extra):
    """files の 1 行（受け持ちは照らしに関わらない固定の字。home・considered は照らしに当たらない既定: 考えの名は行の path ごとに違う字、
    退けた置き場は根に置く 1 段の path 1 つ）"""
    return {"path": path, "op": op, "responsibility": "この行の受け持ち", "symbols": list(symbols),
            "home": {"concept": f"{path} の考え", "why": "この行の path が住処だから"},
            "considered": [{"path": "alt_home.py", "why_not": "同じ仕事の助け手が alt_home.py:3 に無かった"}], **extra}


REWRITE = {"id": "test_stats.py::TestStats::test_clamp_within_range", "behavior": "上限の内側の値をそのまま返す",
           "old": "clamp(5, 0, 10) は 5", "new": "新しい期待（依頼で変わる振る舞い）"}


class PlanFieldsCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name)
        self.repo = self.tmp / "repo"
        shutil.copytree(SEED, self.repo, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))

    def gaps(self, *items):
        return planmarks.gaps({"plan": list(items)}, self.repo)


class TestGaps(PlanFieldsCase):
    def test_gaps_tdd_item_needs_a_test(self):
        self.assertEqual(self.gaps(item()), [])
        got = self.gaps(item(tests=[]))
        self.assertTrue(any(g.startswith("plan[0].tests") for g in got), got)

    def test_gaps_direct_item_needs_route_why(self):
        got = self.gaps(item(route="direct", tests=[], route_why="短い"))
        self.assertTrue(any(g.startswith("plan[0].route_why") for g in got), got)
        self.assertEqual(self.gaps(item(route="direct", tests=[], route_why="文書だけの直しで先にテストを書けない")), [])

    def test_gaps_rewrite_must_name_an_existing_test(self):
        for tid in ("test_stats.py::TestStats::test_nope", "nope.py::T::t", "/abs/test_stats.py::TestStats::test_mean_of_three",
                    "../test_stats.py::TestStats::test_mean_of_three"):
            with self.subTest(tid):
                rw = [{"id": tid, "behavior": "依頼で変わる平均の定義", "old": "2", "new": "新しい期待は 2.0（float）"}]
                got = self.gaps(item(rewrite_tests=rw))
                self.assertTrue(any(g.startswith("plan[0].rewrite_tests[0]") and tid in g for g in got), got)

    def test_gaps_rewrite_of_existing_test_passes(self):
        self.assertEqual(self.gaps(item(rewrite_tests=[REWRITE])), [])

    def test_gaps_new_test_must_not_exist_yet(self):
        t = {**item()["tests"][0], "id": "test_stats.py::TestStats::test_mean_of_three"}
        got = self.gaps(item(tests=[t]))
        self.assertTrue(any("rewrite_tests" in g for g in got), got)   # 既に在るテストは rewrite_tests に書けと案内する

    def test_gaps_same_id_in_tests_and_rewrites(self):
        tid = REWRITE["id"]
        t = {**item()["tests"][0], "id": tid}
        got = self.gaps(item(tests=[t]), item(rewrite_tests=[REWRITE]))
        self.assertTrue(any(g.startswith("plan[1].rewrite_tests[0]") and tid in g and "plan[0].tests[0]" in g for g in got), got)

    def test_gaps_refactor_declared_needs_why(self):
        got = self.gaps(item(refactor={"declared": True, "why": "整える"}))
        self.assertTrue(any(g.startswith("plan[0].refactor") for g in got), got)
        self.assertEqual(self.gaps(item(refactor={"declared": True, "why": "名前の重なる 2 つの関数を 1 つに寄せる"})), [])

    def test_gaps_same_test_id_with_two_red_kinds_rejected(self):
        """同じ受け入れのテストの id を 2 つの項目が別の赤の種類で宣言したら拒む（黙って先の物を勝たせない）。同じ種類なら通す"""
        t = item()["tests"][0]
        got = self.gaps(item(), item(tests=[dict(t, red_kind="exception")]))
        self.assertTrue(any(g.startswith("plan[1].tests[0]") and "red_kind" in g for g in got), got)
        self.assertEqual(self.gaps(item(), item()), [])

    def test_gaps_type_errors_are_named(self):
        got = self.gaps(item(route="maybe", tests="test_stats.py::TestStats::test_x"))
        self.assertTrue(any(g.startswith("plan[0].route") for g in got), got)
        self.assertTrue(any(g.startswith("plan[0].tests") for g in got), got)
        bare = {k: v for k, v in item().items() if k not in planmarks.KEYS}
        got = self.gaps(bare, "項目でない")
        for k in ("route", "tests", "rewrite_tests", "refactor"):
            self.assertTrue(any(g.startswith(f"plan[0].{k}") for g in got), (k, got))
        self.assertTrue(any(g.startswith("plan[1]") for g in got), got)
        self.assertEqual(planmarks.gaps("返答でない", self.repo), [])   # 返答の形は写しの規則が拒む

    def test_gaps_adds_symbol_kind_named_by_file(self):
        """files の symbols の name が / で始まらずに / を含むか、行の path の拡張子で終わるなら、plan[0].files[i].symbols[j].name を名指して拒み、
        識別子で書いてパスは行の path に書けと言う（依頼 194c: receivers.py と書いた名を TDD の輪が 'py' と比べた）。ほかの誤りと同じ
        1 回の拒否に並べる。識別子・<パス>::<名前>・説明の文は今どおり通す"""
        got = self.gaps(item(files=[frow("app/receivers.py", fadd("clamp"), fadd("receivers.py"), fadd("app/schema/fields.json"),
                                         fadd("docs/scope.md"))], route="maybe"))
        for j, nm in ((1, "receivers.py"), (2, "app/schema/fields.json"), (3, "docs/scope.md")):
            row = [g for g in got if g.startswith(f"plan[0].files[0].symbols[{j}].name")]
            self.assertEqual(len(row), 1, got)
            self.assertIn(nm, row[0])
        self.assertFalse(any(g.startswith("plan[0].files[0].symbols[0]") for g in got), got)
        self.assertTrue(any(g.startswith("plan[0].route") for g in got), got)          # ほかの誤りと 1 回で並ぶ
        for name in ("Stats.median", "app.receivers.handle", "_probe(pgid_file) -> (pgid, why)", "plan[].files[].name", "Response.json",
                     "SKIP_REASON", "stats.mean", "/plan/files", "TestStats::test_mean_of_two"):
            with self.subTest(name=name):
                self.assertEqual(self.gaps(item(files=[frow("stats.py", fadd(name))])), [])

    def test_gaps_symbol_name_is_not_a_path_of_its_row(self):
        """symbols の name に、/ で始まらずに / を含む名か、行の path の拡張子で終わる名を書くと、plan[0].files[i].symbols[j].name を名指して
        拒む。Response.json（app/x.ts の行）や /plan/files は通す。拡張子の表は持たず、行の path の拡張子と照らす"""
        rows = [frow("app/x.ts", fadd("event.ts"), fadd("Response.json"), fadd("/plan/files"), fadd("tests/_real_db.SKIP_REASON")),
                frow("lib/y.py", fadd("y.py"), fadd("lib.y"), fadd("y.ts")), frow("Makefile", fadd("Makefile"))]
        got = self.gaps(item(files=rows))
        bad = sorted(g.split(".name", 1)[0] for g in got if ".name（" in g)
        self.assertEqual(bad, ["plan[0].files[0].symbols[0]", "plan[0].files[0].symbols[3]", "plan[0].files[1].symbols[0]"], got)
        self.assertTrue(all("symbols" in g for g in got), got)

    def test_gaps_removal_rows_need_why(self):
        """拒むのは 3 つ: why の無い change=remove の symbol、why の無い op=delete・rename の行、why・replaced_by を持つ足す側の行
        （change=add の symbol・op が create・modify の行）。why と replaced_by を書いた消す行は通る。名指しは行の why か symbol の why"""
        gone = "呼び手は新しい名に寄せたので要らない"
        ok = [frow("stats.py", frm("old_mean", why=gone, ) | {"replaced_by": "stats.py::mean"}),
              frow("old.py", op="delete", why=gone, replaced_by="stats.py"),
              frow("new.py", op="rename", why="名を実体に合わせて付け替えた", **{"from": "mid.py"})]
        self.assertEqual(self.gaps(item(files=ok)), [])
        bare = {k: v for k, v in frm("old_mean").items() if k != "why"}
        got = self.gaps(item(files=[frow("stats.py", bare), frow("old.py", op="delete"),
                                    frow("new.py", op="rename", **{"from": "mid.py"}, why="短い")]))
        for at in ("plan[0].files[0].symbols[0].why", "plan[0].files[1].why", "plan[0].files[2].why"):
            self.assertEqual(len([g for g in got if g.startswith(at)]), 1, (at, got))
        add_side = self.gaps(item(files=[frow("stats.py", fadd("median") | {"why": gone}, fadd("mode") | {"replaced_by": "x.py"}),
                                         frow("new.py", fadd("run"), op="create", why=gone),
                                         frow("mod.py", op="modify", replaced_by="x.py")]))
        for at in ("plan[0].files[0].symbols[0].why", "plan[0].files[0].symbols[1].replaced_by", "plan[0].files[1].why",
                   "plan[0].files[2].replaced_by"):
            self.assertEqual(len([g for g in add_side if g.startswith(at)]), 1, (at, add_side))
        dup = self.gaps(item(files=[frow("stats.py", fadd("median")), frow("stats.py", fadd("median"))]))
        self.assertTrue(any(g.startswith("plan[0].files[1].symbols[0]") and "同じ (path, name, change)" in g for g in dup), dup)
        same_name_two_paths = self.gaps(item(files=[frow("stats.py", fadd("median")), frow("other.py", fadd("median"))]))
        self.assertEqual(same_name_two_paths, [], "同じ名でも path が違えば別の行")
        self.assertTrue(any(g.startswith("plan[0].files[0].from") for g in self.gaps(item(files=[frow("a.py", op="rename", why=gone)]))))
        self.assertTrue(any(g.startswith("plan[0].files[0].from") for g in self.gaps(item(files=[frow("a.py", **{"from": "b.py"})]))))
        self.assertTrue(any(g.startswith("plan[0].files[0].path") for g in self.gaps(item(files=[frow("./a.py")]))))

    def test_depends_gaps_two_items_pass_cycle_and_self_rejected(self):
        """後の項目が depends_on で前の項目の単位と受ける物を書いた 2 項目は通る。拒むのは、自分指し・案に無い単位・前の項目に無い受ける物・
        2 項目の輪。受ける物は前の項目の files の行の path か symbol の <パス>::<名前>（op も change も問わない）"""
        first = item(unit_keys=[MEAN], files=[frow("stats.py", fadd("median"), op="modify"), frow("lib/new.py", op="create")])
        second = item(unit_keys=[CLAMP], depends_on=[{"unit": MEAN, "receives": ["stats.py::median", "lib/new.py"]}])
        self.assertEqual(planmarks.depends_gaps([first, second]), [])
        self.assertEqual(planmarks.depends_gaps([first, item(unit_keys=[CLAMP])]), [])
        selfie = item(unit_keys=[CLAMP], depends_on=[{"unit": CLAMP, "receives": ["stats.py"]}])
        unknown = item(unit_keys=[CLAMP], depends_on=[{"unit": "無い単位", "receives": ["stats.py"]}, {"unit": 3, "receives": ["stats.py"]}])
        lacking = item(unit_keys=[CLAMP], depends_on=[{"unit": MEAN, "receives": ["stats.py::median", "stats.py::nope", "other.py"]}])
        got = planmarks.depends_gaps([first, selfie])
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith("plan[1].depends_on[0].unit") and "自分" in got[0], got)
        got = planmarks.depends_gaps([first, unknown])
        self.assertEqual([g.split("（")[0] for g in got], ["plan[1].depends_on[0].unit", "plan[1].depends_on[1].unit"], got)
        got = planmarks.depends_gaps([first, lacking])
        self.assertEqual([g.split("（")[0] for g in got], ["plan[1].depends_on[0].receives[1]", "plan[1].depends_on[0].receives[2]"], got)
        loop1 = item(unit_keys=[MEAN], files=first["files"], depends_on=[{"unit": CLAMP, "receives": ["stats.py"]}])
        loop2 = item(unit_keys=[CLAMP], files=[frow("stats.py")], depends_on=[{"unit": MEAN, "receives": ["stats.py"]}])
        got = planmarks.depends_gaps([loop1, loop2])
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith("plan.depends_on") and "循環" in got[0], got)
        self.assertEqual(planmarks.depends_gaps("案でない"), [])
        self.assertEqual(planmarks.depends_gaps([first, "項目でない", {"unit_keys": "壊れ"}]), [])
        # gaps は depends_on の型（unit・receives が要る）だけを見る。指す先の照らしは案の全体を見る depends_gaps の 1 つの口に在り、
        # 案の直しの gaps が直した項目だけを受けても、直さない項目を指す行を誤って拒まない
        got = self.gaps(item(depends_on=[{"unit": MEAN}, {"receives": ["a.py"]}, {"unit": MEAN, "receives": []}]))
        for j in (0, 1, 2):
            self.assertTrue(any(g.startswith(f"plan[0].depends_on[{j}]") for g in got), (j, got))
        self.assertEqual(self.gaps(item(depends_on=[{"unit": "無い単位", "receives": ["a.py"]}])), [])
        # 組を作る対 depends_pairs: 後の項目の単位の全部は、指した前の項目の単位の全部の後に並ぶ。among の外を通る依存は中の端どうしに縮む
        chain = [item(unit_keys=["A"]), item(unit_keys=["B", "B2"], depends_on=[{"unit": "A", "receives": ["a.py"]}]),
                 item(unit_keys=["C"], depends_on=[{"unit": "B2", "receives": ["b.py"]}])]
        self.assertEqual(planmarks.depends_pairs(chain), [("A", "B"), ("A", "B2"), ("B", "C"), ("B2", "C")])
        self.assertEqual(planmarks.depends_pairs(chain, among=["A", "C"]), [("A", "C")])
        self.assertEqual(planmarks.depends_pairs(chain, among=["C"]), [])
        self.assertEqual(planmarks.depends_pairs([item(unit_keys=["A"], depends_on=[{"unit": "A", "receives": []}, "壊れ"]), "項目でない"]), [])

    def test_gaps_test_row_fields(self):
        t = {"id": "test_stats.py::TestStats::test_mean_of_two", "behavior": "短い", "red_kind": "import", "extra": 1}
        got = self.gaps(item(tests=[t]))
        for w in ("plan[0].tests[0].behavior", "plan[0].tests[0].red_kind", "'path'", "'red_why'", "'extra'"):
            self.assertTrue(any(w in g for g in got), (w, got))

    def test_files_schema_rows_hold_home_and_considered_without_kind(self):
        """FILES_SCHEMA の行は home {concept, why} と considered [{path, why_not}]（1 行以上）を必ず持ち、旧い正本の自由文の欄を持たない。symbol は
        種類の札を持たない。旧い正本の欄を持つ行・種類の札を持つ symbol・concept の無い home・空の considered・at など別の鍵を持つ considered の行は
        型の誤りになる（additionalProperties false）。種類の札の列挙は無い"""
        from engine.schema import validate_schema

        def errs(row):
            return validate_schema([row], planmarks.FILES_SCHEMA, "files")
        good = frow("lib/x.py", fadd("run"), frm("old_run"), op="create")
        self.assertEqual(errs(good), [])
        old = {k: v for k, v in good.items() if k not in ("home", "considered")} | {"canonical": "既存の正本"}
        self.assertTrue(any("'canonical'" in e for e in errs(old)), errs(old))
        self.assertTrue(any("'home'" in e for e in errs(old)) and any("'considered'" in e for e in errs(old)), errs(old))
        kinded = dict(good, symbols=[{"name": "run", "kind": "function", "change": "add"}])
        self.assertTrue(any("'kind'" in e for e in errs(kinded)), errs(kinded))
        no_concept = dict(good, home={"why": "ここを選んだ訳"})
        self.assertTrue(any("'concept'" in e for e in errs(no_concept)), errs(no_concept))
        loose_home = dict(good, home=dict(good["home"], path="lib/x.py"))
        self.assertTrue(any("'path'" in e for e in errs(loose_home)), errs(loose_home))
        self.assertTrue(errs(dict(good, home=dict(good["home"], why=" "))))
        self.assertTrue(errs(dict(good, considered=[])))
        at = dict(good, considered=[{"path": "alt_home.py", "why_not": "同じ仕事の助け手が無かった", "at": "alt_home.py"}])
        self.assertTrue(any("'at'" in e for e in errs(at)), errs(at))
        self.assertTrue(errs(dict(good, considered=[{"path": "alt_home.py", "why_not": "短い"}])))
        self.assertTrue(errs(dict(good, considered=[{"path": "", "why_not": "同じ仕事の助け手が無かった"}])))
        self.assertFalse(hasattr(planmarks, "SYMBOL_KIND_WORDS"))

    def test_gaps_considered_path_is_not_its_row_and_not_repeated(self):
        """considered[].path が行の path と同じ（自分を退けた先に数える）なら、plan[0].files[0].considered[k].path を名指して拒む。同じ行で
        同じ path を 2 度書いたら 2 度目を名指して拒む。行の path と違う path を 1 度ずつ書いた行は通す"""
        why = "同じ仕事の助け手が無かった"
        own = frow("lib/x.py", op="create", considered=[{"path": "stats.py", "why_not": why}, {"path": "lib/x.py", "why_not": why}])
        got = self.gaps(item(files=[own]))
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith("plan[0].files[0].considered[1].path"), got)
        twice = frow("lib/x.py", op="create", considered=[{"path": "stats.py", "why_not": why}, {"path": "stats.py", "why_not": why}])
        got = self.gaps(item(files=[frow("stats.py"), twice]))
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith("plan[0].files[1].considered[1].path"), got)
        once = frow("lib/x.py", op="create", considered=[{"path": "stats.py", "why_not": why}, {"path": "test_stats.py", "why_not": why}])
        self.assertEqual(self.gaps(item(files=[once])), [])

    def test_gaps_considered_path_is_relative_and_starts_at_a_root_name(self):
        """considered[].path が \\ を含む・根の外を指す（/abs・../x）・整えていない形（./x）・2 段以上で最初の段が種の根に無い
        （nowhere/x.py）なら、plan[0].files[0].considered[0].path を名指して 1 行拒む。通すのは、種の根に在る名で始まる path・まだ無い
        1 段の path（median.py）・作業ツリーにまだ無いファイルを根に在る段の下に置く path。根が dir でない時は根の名を照らさない"""
        (self.repo / "lib").mkdir()
        why = "同じ仕事の助け手が無かった"

        def row(path):
            return frow("lib/x.py", op="create", considered=[{"path": path, "why_not": why}])
        for bad in ("a\\b.py", "/abs/x.py", "../x.py", "./x.py", "nowhere/x.py", "stats.py//x", "lib/../x.py"):
            with self.subTest(bad):
                got = self.gaps(item(files=[row(bad)]))
                self.assertEqual(len(got), 1, got)
                self.assertTrue(got[0].startswith("plan[0].files[0].considered[0].path"), got)
        for good in ("stats.py", "test_stats.py", "median.py", "lib/new_helper.py", "lib/deep/er/new.py", "Makefile"):
            with self.subTest(good):
                self.assertEqual(self.gaps(item(files=[row(good)])), [])
        self.assertEqual(planmarks.gaps({"plan": [item(files=[row("nowhere/x.py")])]}, self.repo / "no-such-root"), [])
        for torn in ({"considered": "壊れ"}, {"considered": ["壊れ", {"path": 3}, {"why_not": "path が無い"}]}):
            with self.subTest(torn=torn):
                self.assertEqual(self.gaps(item(files=[frow("lib/x.py", **torn)])), [])   # 形の崩れは型が見る

    def test_home_gaps_concept_once_across_the_plan(self):
        """home_gaps(items) は、案の全部の行で home.concept（前後の空白を落として casefold）が 2 度出たら、2 度目の行の home.concept を
        名指し、1 度目の行も文に載せて拒む。2 つの項目でも同じ項目の 2 行でもよい。2 度目の行の path が 1 度目の行の considered に在れば
        （逆も）、退けた所に同じ考えを住まわせる矛盾の文でも拒む。考えが分かれていれば空。形の崩れた項目・行は飛ばす"""
        def row(path, concept, *, considered="alt_home.py"):
            return frow(path, home={"concept": concept, "why": "ここが住処だから"},
                        considered=[{"path": considered, "why_not": "同じ仕事の助け手が無かった"}])
        a = item(files=[row("lib/a.py", "出力の読み口")])
        self.assertEqual(planmarks.home_gaps([a, item(files=[row("lib/b.py", "別の考え")])]), [])
        got = planmarks.home_gaps([a, item(files=[row("lib/b.py", "  出力の読み口 ")])])
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith("plan[1].files[0].home.concept") and "plan[0].files[0]" in got[0], got)
        got = planmarks.home_gaps([item(files=[row("lib/a.py", "Reader"), row("lib/b.py", "別の考え"), row("lib/c.py", "READER")])])
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0].startswith("plan[0].files[2].home.concept") and "plan[0].files[0]" in got[0], got)
        # 退けた所に同じ考えを住まわせる矛盾: 後の行の path が先の行の considered に在る・先の行の path が後の行の considered に在る
        for first, second in ((row("lib/a.py", "考え", considered="lib/b.py"), row("lib/b.py", "考え")),
                              (row("lib/a.py", "考え"), row("lib/b.py", "考え", considered="lib/a.py"))):
            got = planmarks.home_gaps([item(files=[first]), item(files=[second])])
            clash = [g for g in got if "矛盾" in g]
            self.assertEqual(len(got), 2, got)
            self.assertEqual(len(clash), 1, got)
            self.assertTrue(clash[0].startswith("plan[1].files[0].home.concept"), got)
        self.assertEqual(planmarks.home_gaps([item(files=[row("lib/a.py", "考え", considered="lib/b.py"), row("lib/b.py", "別の考え")])]), [])
        torn = [a, "項目でない", {"files": "壊れ"}, item(files=["行でない", {"home": "壊れ"}, {"home": {"concept": 3}}, {"home": {}}, {}])]
        self.assertEqual(planmarks.home_gaps(torn), [])
        self.assertEqual(planmarks.home_gaps("案でない"), [])


class TestFindTest(PlanFieldsCase):
    def test_find_test_py_and_other(self):
        self.assertEqual(planmarks.find_test(self.repo, "test_stats.py::TestStats::test_mean_of_three"), 8)
        self.assertIsNone(planmarks.find_test(self.repo, "test_stats.py::Nope::test_mean_of_three"))
        (self.repo / "t.sh").write_text("a\ntest_x() {\n", encoding="utf-8")
        self.assertEqual(planmarks.find_test(self.repo, "t.sh::test_x"), 2)

    def test_find_test_module_function_and_misses(self):
        (self.repo / "test_top.py").write_text("import x\n\n\n@deco\ndef test_top():\n    pass\n", encoding="utf-8")
        self.assertEqual(planmarks.find_test(self.repo, "test_top.py::test_top"), 5)
        (self.repo / "broken.py").write_text("def test_b(:\n", encoding="utf-8")
        for tid in ("broken.py::test_b", "test_stats.py", "test_stats.py::test_mean_of_three", "nope.py::test_x",
                    "/abs/test_stats.py::TestStats::test_mean_of_three", "../repo/test_stats.py::TestStats::test_mean_of_three",
                    "test_stats.py::A::B::test_mean_of_three", "::test_x"):
            with self.subTest(tid):
                self.assertIsNone(planmarks.find_test(self.repo, tid))

    def test_find_test_symlink_out_of_root(self):
        outside = self.tmp / "out.py"
        outside.write_text("def test_o():\n    pass\n", encoding="utf-8")
        (self.repo / "link.py").symlink_to(outside)
        self.assertIsNone(planmarks.find_test(self.repo, "link.py::test_o"))


class TestSplitAndBoard(PlanFieldsCase):
    def test_split_strips_fields_and_resolves_limit(self):
        rw = [{"id": "test_stats.py::TestStats::test_clamp_within_range", "behavior": "上限の内側の値をそのまま返す",
               "old": "5", "new": "新しい期待（依頼で変わる振る舞い）"}]
        reply = {"plan": [item(rewrite_tests=rw)]}
        bare, fields = planmarks.split(reply, self.repo)
        self.assertEqual(set(bare["plan"][0]), PLAN_KEYS)
        self.assertEqual(fields[0]["rewrite_tests"][0]["limit"], "test_stats.py:11")
        self.assertEqual(fields[0]["route"], "tdd")
        self.assertIn("tests", reply["plan"][0])   # 渡した返答は変えない

    def test_split_freezes_tests_naming_removes_as_permits(self):
        """files の change=remove の symbol（消す名）を base の本体で名指すテストは、欄の行の removes_tests に {id, limit} で並ぶ（義務でない許しの行）。
        探す木は渡された base_tests（作業ツリーで既に消えたテストも並ぶ）。名指さないテストは並ばない"""
        base_tests = {"test_stats.py": (SEED / "test_stats.py").read_text(encoding="utf-8")}
        tree = self.repo / "test_stats.py"
        tree.write_text(base_tests["test_stats.py"].replace(
            "    def test_clamp_within_range(self):\n        self.assertEqual(clamp(5, 0, 10), 5)\n\n", ""), encoding="utf-8")
        self.assertNotIn("test_clamp_within_range", tree.read_text(encoding="utf-8"))
        _, fields = planmarks.split({"plan": [item(files=[frow("stats.py", frm("stats.clamp"))])]}, self.repo, base_tests=base_tests)
        got = sorted((r["id"], r["limit"]) for r in fields[0]["removes_tests"])
        self.assertEqual(got, [("test_stats.py::TestStats::test_clamp_above_range", "test_stats.py:14"),
                               ("test_stats.py::TestStats::test_clamp_within_range", "test_stats.py:11")])
        self.assertNotIn("test_stats.py::TestStats::test_mean_of_three", [r["id"] for r in fields[0]["removes_tests"]])

    def test_split_permits_tests_naming_removed_symbols_of_files(self):
        """change=remove の symbol の名を、修正前のテストの本体がコードで使う時、removes_tests に許しが並ぶ。op=delete の .py の行の
        モジュールの名を使うテストにも許しが並ぶ。change=add の名と op=create の行は許しの元にならない"""
        src = ("from stats import clamp\n\n\nclass TestStats:\n    def test_clamp(self):\n        assert clamp(5, 0, 10) == 5\n\n"
               "    def test_mean(self):\n        assert 1\n\n\ndef test_old():\n    import old_tool\n    assert old_tool.run()\n")
        base = {"test_stats.py": src}
        files = [frow("stats.py", frm("clamp"), fadd("mean")), frow("old_tool.py", op="delete", why="呼び手は stats に寄せたので要らない")]
        _, fields = planmarks.split({"plan": [item(files=files)]}, self.repo, base_tests=base)
        self.assertEqual(sorted(r["id"] for r in fields[0]["removes_tests"]),
                         ["test_stats.py::TestStats::test_clamp", "test_stats.py::test_old"])
        added_only = [frow("stats.py", fadd("clamp")), frow("old_tool.py", op="create")]
        _, fields = planmarks.split({"plan": [item(files=added_only)]}, self.repo, base_tests=base)
        self.assertEqual(fields[0]["removes_tests"], [])

    def test_split_permits_tests_naming_the_old_module_of_a_rename(self):
        """op=rename の行の元のパス from（.py）のモジュールの名を使う修正前のテストに、removes_tests の許しが並ぶ（移すモジュールの
        旧名を import するテストを書き換えられる）。移した先のパス path の名は許しの元にならない"""
        src = ("def test_old():\n    import old_tool\n    assert old_tool.run()\n\n\n"
               "def test_new():\n    import new_tool\n    assert new_tool.run()\n")
        files = [frow("tools/new_tool.py", op="rename", why="tools の下に寄せる", **{"from": "old_tool.py"})]
        _, fields = planmarks.split({"plan": [item(files=files)]}, self.repo, base_tests={"test_tools.py": src})
        self.assertEqual([r["id"] for r in fields[0]["removes_tests"]], ["test_tools.py::test_old"])

    def test_removes_tests_only_from_code_use(self):
        """消す名（files の change=remove の symbol）の語が文字列（題・辞書の値・parametrize の値・文字列で書いた注釈）やコメントの中にしか無いテストは removes_tests に
        並ばない。コードの名前（注釈の中の名も）・属性・点の付いたパスの文字列（mock.patch の的のどの段でも。デコレータでも）・属性の名の文字列（setattr・getattr・
        patch.object）・引数の名・from-import の元のモジュールの段で使うテストだけが並ぶ（ありふれた語で許しを広げない。#549）"""
        src = ("import pytest\n"
               "from unittest import mock\n"
               "\n"
               "def test_title():\n"
               "    assert make(title=\"The Test Book\").title\n"
               "\n"
               "def test_group():\n"
               "    assert lookup({\"product_group\": \"Book\"})\n"
               "\n"
               "@pytest.mark.parametrize(\"name\", ['(Book 1)'])\n"
               "def test_series(name):\n"
               "    assert parse(name)  # Book\n"
               "\n"
               "def test_builds():\n"
               "    assert Book(title=\"x\")\n"
               "\n"
               "def test_patched():\n"
               "    with mock.patch(\"pkg.validator.Book\"):\n"
               "        assert run()\n"
               "\n"
               "def test_quoted_hint(x: \"Book\"):\n"
               "    assert x\n"
               "\n"
               "def test_hint(x: Book):\n"
               "    assert x\n"
               "\n"
               "def test_fixture(Book):\n"
               "    assert Book\n"
               "\n"
               "def test_attr():\n"
               "    assert models.Book(title=\"x\")\n"
               "\n"
               "@mock.patch(\"pkg.validator.Book\")\n"
               "def test_decorated(m):\n"
               "    assert run()\n"
               "\n"
               "def test_setattr(monkeypatch):\n"
               "    monkeypatch.setattr(mod, \"Book\", None)\n"
               "\n"
               "def test_patch_object():\n"
               "    with mock.patch.object(mod, \"Book\"):\n"
               "        assert run()\n"
               "\n"
               "def test_getattr():\n"
               "    assert getattr(mod, \"Book\")\n"
               "\n"
               "def test_other_call_string():\n"
               "    assert find(mod, \"Book\")\n"
               "\n"
               "def test_patched_method():\n"
               "    with mock.patch(\"pkg.models.Book.save\"):\n"
               "        assert run()\n")
        _, fields = planmarks.split({"plan": [item(files=[frow("books.py", frm("Book"))])]}, self.repo, base_tests={"tests/test_books.py": src})
        self.assertEqual([r["id"] for r in fields[0]["removes_tests"]],
                         ["tests/test_books.py::test_builds", "tests/test_books.py::test_patched",
                          "tests/test_books.py::test_hint", "tests/test_books.py::test_fixture", "tests/test_books.py::test_attr",
                          "tests/test_books.py::test_decorated", "tests/test_books.py::test_setattr",
                          "tests/test_books.py::test_patch_object", "tests/test_books.py::test_getattr",
                          "tests/test_books.py::test_patched_method"])
        src = ("from unittest import mock\n"
               "\n"
               "def test_patched_inside():\n"
               "    with mock.patch(\"pkg.vendors.get_meta\"):\n"
               "        assert run()\n"
               "\n"
               "def test_local_import():\n"
               "    from pkg.vendors import AmazonAPI\n"
               "    assert AmazonAPI\n"
               "\n"
               "def test_unrelated():\n"
               "    assert run(\"vendors\")\n")
        _, fields = planmarks.split({"plan": [item(files=[frow("pkg/vendors.py", frm("pkg.vendors"))])]}, self.repo,
                                    base_tests={"tests/test_vendors.py": src})
        self.assertEqual([r["id"] for r in fields[0]["removes_tests"]],
                         ["tests/test_vendors.py::test_patched_inside", "tests/test_vendors.py::test_local_import"])

    def test_save_read_by_round(self):
        b = types.SimpleNamespace(dir=self.tmp, round=1)
        planmarks.save(self.tmp, 1, [{"route": "tdd"}])
        self.assertEqual(planmarks.read(b), [{"route": "tdd"}])
        self.assertIsNone(planmarks.read(types.SimpleNamespace(dir=self.tmp, round=2)))
        (self.tmp / planmarks.FIELDS_FILE).write_text("{壊れた", encoding="utf-8")
        self.assertIsNone(planmarks.read(b))
        self.assertIsNone(planmarks.read(types.SimpleNamespace(dir=self.tmp / "無い", round=1)))

    def test_rewrites_rows(self):
        _, fields = planmarks.split({"plan": [item(), item(unit_keys=["u2"], tests=[], route="direct",
                                                           route_why="文書だけの直しで先にテストを書けない",
                                                           rewrite_tests=[REWRITE])]}, self.repo)
        planmarks.save(self.tmp, 3, fields)
        b = types.SimpleNamespace(dir=self.tmp, round=3)
        self.assertEqual(planmarks.rewrites(b), [{"item": 2, "unit_keys": ["u2"], "id": REWRITE["id"], "new": REWRITE["new"],
                                                  "limit": "test_stats.py:11"}])
        self.assertEqual(planmarks.rewrites(types.SimpleNamespace(dir=self.tmp, round=4)), [])

    def test_review_section(self):
        self.assertEqual(planmarks.review_section(types.SimpleNamespace(dir=self.tmp, round=1)), "")
        _, fields = planmarks.split({"plan": [item()]}, self.repo)
        planmarks.save(self.tmp, 1, fields)
        got = planmarks.review_section(types.SimpleNamespace(dir=self.tmp, round=1))
        self.assertTrue(got.startswith("\n\n" + planmarks.REVIEW_HEAD), got)
        for w in (planmarks.REVIEW_ASK, "test_stats.py::TestStats::test_mean_of_two", "本物の経路", "mock"):
            self.assertIn(w, got)

    def test_head_names_every_field(self):
        for w in ("route", "route_why", "tests", "rewrite_tests", "refactor", "red_kind", "assertion", "exception", "brief"):
            self.assertIn(w, planmarks.HEAD)


class TestFrozenFields(PlanFieldsCase):
    """盤面の控え plan-fields.json の凍結: save が trace に印 {round, sha256} を書き、許しの元（rewrites）は印と突き合わせて読む"""

    def saved(self, rnd=1):
        _, fields = planmarks.split({"plan": [item(rewrite_tests=[REWRITE])]}, self.repo)
        planmarks.save(self.tmp, rnd, fields)
        return types.SimpleNamespace(dir=self.tmp, round=rnd)

    def marks(self):
        rows = [json.loads(x) for x in (self.tmp / "trace.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        return [r for r in rows if r.get("op") == planmarks.SAVED_OP]

    def test_save_writes_mark_with_round_and_sha(self):
        import hashlib
        self.saved(2)
        raw = (self.tmp / planmarks.FIELDS_FILE).read_bytes()
        got = self.marks()
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0]["round"], got[0]["sha256"]), (2, hashlib.sha256(raw).hexdigest()))

    def test_append_trace_is_the_save_row_shape(self):
        """trace を受けない save の印の行と append_trace の行は同じ形 {t, op, …}（t の書き方も同じ）"""
        planmarks.save(self.tmp, 1, [])
        planmarks.append_trace(self.tmp, "x", a=1)
        rows = [json.loads(x) for x in (self.tmp / planmarks.TRACE_FILE).read_text(encoding="utf-8").splitlines()]
        self.assertEqual([list(r)[:2] for r in rows], [["t", "op"], ["t", "op"]])
        self.assertEqual(rows[1], {"t": rows[1]["t"], "op": "x", "a": 1})
        self.assertEqual(len(rows[0]["t"]), len(rows[1]["t"]))

    def test_frozen_reads_saved_fields(self):
        b = self.saved()
        self.assertEqual(planmarks.frozen(b), planmarks.read(b))
        self.assertEqual(len(planmarks.rewrites(b)), 1)

    def test_rewritten_after_save_is_broken(self):
        """受け付けの後に rewrite_tests の行を足した控えは、許しの元にしない（FieldsBroken。理由に plan-fields.json を名指す）"""
        b = self.saved()
        p = self.tmp / planmarks.FIELDS_FILE
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["fields"][0]["rewrite_tests"].append(dict(REWRITE, id="test_stats.py::TestStats::test_mean_of_three",
                                                      limit="test_stats.py:8"))
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        for fn in (planmarks.frozen, planmarks.rewrites):
            with self.subTest(fn.__name__), self.assertRaisesRegex(planmarks.FieldsBroken, planmarks.FIELDS_FILE):
                fn(b)

    def test_removed_after_save_is_broken(self):
        b = self.saved()
        (self.tmp / planmarks.FIELDS_FILE).unlink()
        with self.assertRaisesRegex(planmarks.FieldsBroken, planmarks.FIELDS_FILE):
            planmarks.frozen(b)

    def test_unmarked_fields_read_as_none(self):
        """印の無い控え（変更前の盤面・save の外で置いた物）は無い物として読む（許しを広げない）"""
        _, fields = planmarks.split({"plan": [item(rewrite_tests=[REWRITE])]}, self.repo)
        (self.tmp / planmarks.FIELDS_FILE).write_text(json.dumps({"round": 1, "fields": fields}, ensure_ascii=False),
                                                      encoding="utf-8")
        b = types.SimpleNamespace(dir=self.tmp, round=1)
        self.assertIsNone(planmarks.frozen(b))
        self.assertEqual(planmarks.rewrites(b), [])

    def test_mark_of_other_round_does_not_count(self):
        self.saved(1)
        self.assertIsNone(planmarks.frozen(types.SimpleNamespace(dir=self.tmp, round=2)))


class TestIdPaths(PlanFieldsCase):
    """テストの id のパス: 区切りは /・根からの相対（絶対パスを拒む）・`..` で始まる名前のファイルは根の中"""

    def test_backslash_in_id_rejected(self):
        """\\ の入った id は、limit がそのまま残るので受け付けで拒む（理由に「/ で書け」）"""
        bad_rw = dict(REWRITE, id="test_stats.py\\..\\x::TestStats::test_clamp_within_range")
        bad_new = {"id": "tests\\test_new.py::test_x", "behavior": "2 つの値の平均を返す", "path": "stats.mean を直に呼ぶ（mock なし）",
                   "red_kind": "assertion", "red_why": "今は len-1 で割り 3.0 になる"}
        got = self.gaps(item(tests=[bad_new], rewrite_tests=[bad_rw]))
        rows = [g for g in got if "/ で書け" in g]
        self.assertEqual(len(rows), 2, got)
        self.assertTrue(any(g.startswith("plan[0].tests[0].id") for g in rows), got)
        self.assertTrue(any(g.startswith("plan[0].rewrite_tests[0].id") for g in rows), got)

    def test_absolute_tests_id_rejected(self):
        new = {"id": str(self.repo / "test_new.py") + "::test_x", "behavior": "2 つの値の平均を返す",
               "path": "stats.mean を直に呼ぶ（mock なし）", "red_kind": "assertion", "red_why": "今は len-1 で割り 3.0 になる"}
        got = self.gaps(item(tests=[new]))
        self.assertTrue(any(g.startswith("plan[0].tests[0].id") and "根からの相対" in g for g in got), got)

    def test_outside_root_tests_id_rejected(self):
        new = {"id": "../test_new.py::test_x", "behavior": "2 つの値の平均を返す",
               "path": "stats.mean を直に呼ぶ（mock なし）", "red_kind": "assertion", "red_why": "今は len-1 で割り 3.0 になる"}
        got = self.gaps(item(tests=[new]))
        self.assertTrue(any(g.startswith("plan[0].tests[0].id") and "根からの相対" in g for g in got), got)

    def test_relative_tests_id_passes(self):
        self.assertEqual(self.gaps(item()), [])

    def test_dotdot_prefixed_name_inside_root_found(self):
        """`..foo/x.py` は根の中のディレクトリ `..foo` の物（`..` の上り口でない）"""
        d = self.repo / "..foo"
        d.mkdir()
        (d / "x.py").write_text("def test_o():\n    pass\n", encoding="utf-8")
        self.assertEqual(planmarks.find_test(self.repo, "..foo/x.py::test_o"), 1)
        self.assertIsNone(planmarks.find_test(self.repo, "../x.py::test_o"))


CLAMP = "stats.py clamp: 上限を超えた値に lo を返す"


class UnitContractCase(unittest.TestCase):
    """単位の約束（planmarks.unit_contract）: その単位を unit_keys に含む項目の欄を合わせた物。純粋（盤面もファイルも読まない）"""
    T1 = {"id": "test_stats.py::TestStats::test_mean_of_two", "behavior": "x" * 10, "path": "y" * 10,
          "red_kind": "assertion", "red_why": "z" * 10}
    RW = {"id": "test_stats.py::TestStats::test_clamp_above_range", "behavior": "x" * 10, "old": "lo を返す",
          "new": "上限を超えたら hi を返す", "limit": "test_stats.py:14"}

    def f(self, keys, **over):
        return {"unit_keys": keys, "route": "tdd", "route_why": "", "tests": [], "rewrite_tests": [],
                "refactor": {"declared": False, "why": ""}, **over}

    def test_contract_joins_items_of_the_unit(self):
        fields = [self.f([MEAN], tests=[self.T1]), self.f([MEAN, CLAMP], route="direct", route_why="w" * 10,
                                                          rewrite_tests=[self.RW], refactor={"declared": True, "why": "w" * 10})]
        got = planmarks.unit_contract(fields, MEAN)
        self.assertEqual(got, {"items": [1, 2], "route": "tdd",
                               "tests": [{"id": self.T1["id"], "red_kind": "assertion"}],
                               "rewrites": [self.RW["id"]], "refactor": [{"item": 2, "why": "w" * 10}],
                               "names": []})
        self.assertEqual(planmarks.unit_contract(fields, CLAMP)["route"], "direct")

    def test_contract_refactor_empty_without_declaration(self):
        """整えの申告は申告した項目の {item, why} の並び。申告が無ければ空"""
        self.assertEqual(planmarks.unit_contract([self.f([MEAN])], MEAN)["refactor"], [])

    def test_contract_none_without_fields_or_items(self):
        self.assertIsNone(planmarks.unit_contract(None, MEAN))
        self.assertIsNone(planmarks.unit_contract([self.f([CLAMP])], MEAN))

    def test_rewrite_without_limit_is_not_in_contract(self):
        rw = {k: v for k, v in self.RW.items() if k != "limit"}
        self.assertEqual(planmarks.unit_contract([self.f([MEAN], rewrite_tests=[rw])], MEAN)["rewrites"], [])

    def test_same_test_id_in_two_items_listed_once(self):
        """tests は項目の順で、id の重複を除く"""
        fields = [self.f([MEAN], tests=[self.T1]), self.f([MEAN], tests=[dict(self.T1, red_kind="exception")])]
        self.assertEqual(planmarks.unit_contract(fields, MEAN)["tests"], [{"id": self.T1["id"], "red_kind": "assertion"}])


class TestUnitContract(PlanFieldsCase):
    def test_names_from_adds(self):
        """split は項目の files を写し、unit_contract の names は key を含む項目の files の change=add の symbol の名を順に重複なしで持つ
        （change=remove の名は持たない）"""
        reply = {"plan": [item(files=[frow("stats.py", fadd("clamp"), fadd("mean"), frm("old_mean"))]),
                          item(files=[frow("stats.py", fadd("clamp"))], unit_keys=[MEAN, CLAMP]),
                          item(files=[frow("stats.py", fadd("other"))], unit_keys=[CLAMP]), item(files=[], unit_keys=[MEAN])]}
        _, fields = planmarks.split(reply, self.repo)
        self.assertEqual(fields[0]["files"], reply["plan"][0]["files"])
        self.assertEqual(planmarks.unit_contract(fields, MEAN)["names"], ["clamp", "mean"])
        self.assertEqual(planmarks.unit_contract(fields, CLAMP)["names"], ["clamp", "other"])
        self.assertEqual(planmarks.unit_contract([{"unit_keys": [MEAN]}], MEAN)["names"], [])
        self.assertIsNone(planmarks.unit_contract(fields, "無い単位"))

    def test_names_from_files_add_symbols_and_created_modules(self):
        """unit_contract の names が、change=add の symbol の名と、op=create の .py の行の path を持つ（新しいモジュールの import の失敗を
        TDD の輪が宣言の赤に数える。依頼 194c: read_input の行が works/.shared/core/nodeio.py の op=create で、No module named 'nodeio' が
        綴りの誤りに数えられた）。change=remove の名・op=modify の行の path（home の考えが『新設』と言っても）・.py でない op=create の
        path は持たない。home・considered の字は読まない。同じ path の 2 行も重なりも 1 つ"""
        def housing(what):
            return {"concept": what, "why": "新しい口なので、ここに置く"}
        reply = {"plan": [item(files=[
            frow("works/.shared/core/nodeio.py", fadd("read_input"), op="create", home=housing("新設。前の節の出力を読む口")),
            frow("works/.shared/core/nodeio.py", fadd("board_out"), op="create", home=housing("新設。盤面の控えから読む口")),
            frow("app/receivers.py", fadd("handle"), op="create"),
            frow("stats.py", fadd("median"), frm("old_mean"), home=housing("stats.py（新設。在るモジュールに足す関数）")),
            frow("works/tests/fixtures/golden.json", fadd("golden"), op="create", home=housing("works/tests/fixtures/golden.py（新設）")),
            frow("textfmt.py", fadd("fmt"), home=housing("新設しない result.py を読む"))])]}
        _, fields = planmarks.split(reply, self.repo)
        self.assertEqual(planmarks.unit_contract(fields, MEAN)["names"],
                         ["works/.shared/core/nodeio.py", "read_input", "board_out", "app/receivers.py", "handle", "median", "golden", "fmt"])


class ScopeFieldsCase(PlanFieldsCase):
    """修正案の項目の範囲の欄（allowed_paths・out_of_scope。依頼 218）: 役の型の必須・glob の誤りと丸ごとの許しの拒否・欄を外す口・
    修正案の役と事前審査の役の頭の文"""

    def test_gaps_allowed_paths_must_be_relative_and_narrow(self):
        for g in ("/abs/x.py", "../x.py", "a\\b.py", "**", "*", "**/*",
                  "./x", " stats.py", "stats.py ", " ", "a/../b", "a//b",   # 整えない綴り・前後の空白（差分のパスに当たらない）
                  "C:/x.py", "C:x.py", "~/x"):                              # ドライブ文字・~ は絶対パスとして拒む
            with self.subTest(g):
                got = planmarks.gaps({"plan": [item(allowed_paths=[g])]}, self.repo)
                self.assertTrue(any(x.startswith("plan[0].allowed_paths[0]") for x in got), got)
        self.assertEqual(planmarks.gaps({"plan": [item(allowed_paths=["stats.py", "docs/**/*.md"])]}, self.repo), [])

    def test_glob_without_a_literal_character_is_a_whole_tree_allowance(self):
        """字の無い glob（* と ? と [..] と / と . だけ）は全部に当たり得る丸ごとの許しなので拒む（**/?* は全部の段が * か ** でないが
        全部のファイルに当たる。無人の run は範囲を広げるだけの案の直しを関所なしに通すので、ここで止める）。字の在る glob は通す"""
        for g in ("**/?*", "?*", "?", "*/?", "**/[a-z]*", "[!.]*", "**/*?", "*/**/*", "[]]*",
                  "**/*.*", "*.*", "**/.*"):   # 字が . だけの glob も拡張子を持つ全部・隠しの全部に当たる
            with self.subTest(g):
                self.assertIn("丸ごと", planmarks.glob_problem(g) or "")
                got = planmarks.gaps({"plan": [item(allowed_paths=[g])]}, self.repo)
                self.assertTrue(any(x.startswith("plan[0].allowed_paths[0]") for x in got), got)
        for g in ("*.py", "**/*.md", "src/**", "a?.py", "[ab].py", "docs/*", "**/test_*.py", "x", ".github/**"):
            with self.subTest(g):
                self.assertIsNone(planmarks.glob_problem(g))

    def test_globs_meet_only_says_no_when_no_path_can_match_both(self):
        for a, b in (("stats.py", "stats.py"), ("lib/a.py", "lib/*.py"), ("lib/**", "lib/x/y.py"), ("**/x.py", "a/x.py"),
                     ("tests/test_*.py", "tests/test_a*.py")):
            with self.subTest(a=a, b=b):
                self.assertTrue(planmarks.globs_meet(a, b))
                self.assertTrue(planmarks.globs_meet(b, a))
        for a, b in (("lib/a.py", "lib/b.py"), ("lib/*.py", "lib/*.md"), ("docs/**", "lib/**"), ("lib/*.py", "lib/x/a.py")):
            with self.subTest(a=a, b=b):
                self.assertFalse(planmarks.globs_meet(a, b))
                self.assertFalse(planmarks.globs_meet(b, a))

    def test_globs_meet_is_true_when_an_argument_is_not_a_string(self):
        """文字列でない引数は言い切れない時なので、交わると見る（組分けの保守側）"""
        for a, b in ((None, "a"), ("a", None), ("a", 1), (1, "a")):
            with self.subTest(a=a, b=b):
                self.assertTrue(planmarks.globs_meet(a, b))

    def test_globs_meet_reads_trailing_slash_like_glob_match(self):
        """末尾 / はその下の全部（glob_match と同じ _dir_glob の 1 か所から引く）と読む: 'a/' は 'a' と交わらず、a/x・a/** と交わり、
        同じパスに当たる glob の対は交わる"""
        self.assertFalse(planmarks.globs_meet("a/", "a"))
        self.assertFalse(planmarks.globs_meet("a", "a/"))
        self.assertTrue(planmarks.globs_meet("a/", "a/x"))
        self.assertTrue(planmarks.globs_meet("a/", "a/**"))
        globs = ["a/", "a", "a/*", "a/**", "lib/*.py", "lib/a.py"]
        paths = ["a/", "a", "a/x", "a/x/y", "lib/a.py"]
        for x in globs:
            for y in globs:
                for p in paths:
                    if planmarks.glob_match(p, x) and planmarks.glob_match(p, y):
                        with self.subTest(x=x, y=y, path=p):
                            self.assertTrue(planmarks.globs_meet(x, y))
        for g in ("a/", "a/**/", "lib/*/"):
            for p in ("a", "a/x", "a/x/y", "lib", "lib/a", "lib/a/x.py"):
                with self.subTest(glob=g, path=p):
                    self.assertEqual(planmarks.glob_match(p, g), planmarks.globs_meet(g, p))

    def test_glob_problem_reads_trailing_slash_as_dir_and_rejects_doubled_slash(self):
        """末尾 / はその下の全部（'/**' と同じ）と読む: 'lib/'・'a/**/'・'lib/*/' は通し、整えない綴り 'lib//'・'a//' と丸ごとの許し
        '**/'・'*/' は拒む"""
        for g in ("lib/", "a/**/", "lib/*/"):
            with self.subTest(g):
                self.assertIsNone(planmarks.glob_problem(g))
        for g in ("lib//", "a//"):
            with self.subTest(g):
                self.assertIn("整えた形でない", planmarks.glob_problem(g) or "")
        for g in ("**/", "*/"):
            with self.subTest(g):
                self.assertIn("丸ごと", planmarks.glob_problem(g) or "")
        got = planmarks.gaps({"plan": [item(allowed_paths=["lib//"])]}, self.repo)
        self.assertTrue(any(x.startswith("plan[0].allowed_paths[0]") for x in got), got)
        got = planmarks.gaps({"plan": [item(allowed_paths=["lib/"])]}, self.repo)
        self.assertFalse(any(x.startswith("plan[0].allowed_paths[0]") for x in got), got)

    def test_glob_match_reads_trailing_slash_as_everything_underneath(self):
        """末尾 / の glob は根からの相対の 'lib/**' と読む: その下のどの深さにも当たり、'lib' そのもの・名の似た別のディレクトリ・
        深い所の同じ名には当たらない"""
        for p in ("lib/planmarks.py", "lib/a/x.py", "lib/"):
            with self.subTest(p):
                self.assertTrue(planmarks.glob_match(p, "lib/"))
        self.assertTrue(planmarks.glob_match("lib/t/x.py", "lib/*/"))
        for p in ("lib", "libx/a.py", "docs/lib/a.py"):
            with self.subTest(p):
                self.assertFalse(planmarks.glob_match(p, "lib/"))

    def test_gaps_out_of_scope_rows(self):
        bad = [{"glob": "../x.py", "why": "根の外は触らない（試験の材料）"}]
        got = planmarks.gaps({"plan": [item(out_of_scope=bad)]}, self.repo)
        self.assertTrue(any(x.startswith("plan[0].out_of_scope[0]") for x in got), got)
        self.assertTrue(planmarks.gaps({"plan": [item(out_of_scope=[{"glob": "test_stats.py", "why": "短い"}])]}, self.repo))

    def test_gaps_scope_fields_required(self):
        it = item()
        del it["allowed_paths"]
        self.assertTrue(any(g.startswith("plan[0].allowed_paths") for g in planmarks.gaps({"plan": [it]}, self.repo)))

    def test_split_keeps_scope_fields_off_the_board(self):
        bare, fields = planmarks.split({"plan": [item()]}, self.repo)
        self.assertEqual(set(bare["plan"][0]), {"unit_keys", "approach", "files", "shrink_first", "narrows"})
        self.assertEqual((fields[0]["allowed_paths"], fields[0]["out_of_scope"]), (["stats.py"], []))

    def test_head_and_review_ask_name_scope_fields(self):
        for w in ("allowed_paths", "out_of_scope", "識別子", "home", "considered", "files", "depends_on", "why", "replaced_by"):
            self.assertIn(w, planmarks.HEAD)
        self.assertNotIn("canonical", planmarks.HEAD)
        self.assertIn("allowed_paths", planmarks.REVIEW_ASK)
        self.assertIn("change=remove", planmarks.REVIEW_ASK)
        self.assertNotIn("項目の removes", planmarks.REVIEW_ASK)

    def test_head_asks_for_moved_and_removed_paths(self):
        self.assertIn("移す・消すファイルの元のパスも allowed_paths に書け", planmarks.HEAD)

    def test_head_asks_tests_id_to_match_existing_layout(self):
        """tests の id と置き場は、名指すファイルの既存のテストの置き方に合わせよと言う（対象の決まりは写さない一般の 1 文）"""
        self.assertIn("クラスの中か一番外か", planmarks.HEAD)

    def test_gaps_out_of_scope_must_not_hit_named_tests(self):
        """out_of_scope の glob が、修正案の tests・rewrite_tests の id のファイルに当たる案は拒む（書けと言うファイルを触るなとも
        言う食い違いを修正の段へ渡さない）。当たらなければ通る"""
        oos = [{"glob": "test_*.py", "why": "既存の試験のファイルは触らない"}]
        got = planmarks.gaps({"plan": [item(out_of_scope=oos)]}, self.repo)
        self.assertTrue(any(x.startswith("plan[0].out_of_scope[0]") and "test_stats.py" in x for x in got), got)
        other = item(tests=[], route="direct", route_why="文書だけの直しで先にテストを書けない", rewrite_tests=[REWRITE])
        got = planmarks.gaps({"plan": [item(), {**other, "out_of_scope": oos}]}, self.repo)
        self.assertTrue(any(x.startswith("plan[1].out_of_scope[0]") for x in got), got)
        self.assertEqual(planmarks.gaps({"plan": [item(out_of_scope=[{"glob": "docs/**", "why": "文書は今回の直しの外"}])]},
                                        self.repo), [])

class ApprovedItemsCase(PlanFieldsCase):
    """approved_items: 今の周の承認済みの修正案の項目と、盤面の控えの欄を同じ番号で合わせた並び"""

    def board(self, plan, fields):
        b = types.SimpleNamespace(dir=self.tmp, round=1,
                                  output_of_round=lambda node, rnd: {"plan": plan} if plan is not None and rnd == 1 else None)
        if fields is not None:
            planmarks.save(self.tmp, 1, fields)
        return b

    def test_join_plan_and_fields_by_number(self):
        _, fields = planmarks.split({"plan": [item()]}, self.repo)
        plan = [{k: v for k, v in item().items() if k not in planmarks.KEYS}]
        got = planmarks.approved_items(self.board(plan, fields))
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0]["item"], got[0]["approach"], got[0]["allowed_paths"], got[0]["unit_keys"]),
                         (1, "x" * 20, ["stats.py"], [MEAN]))

    def test_none_without_plan_or_fields(self):
        _, fields = planmarks.split({"plan": [item()]}, self.repo)
        self.assertIsNone(planmarks.approved_items(self.board(None, fields)))
        self.tmp = self.tmp / "other"
        self.tmp.mkdir()
        self.assertIsNone(planmarks.approved_items(self.board([item()], None)))

    def test_count_mismatch_is_fields_broken(self):
        _, fields = planmarks.split({"plan": [item()]}, self.repo)
        with self.assertRaises(planmarks.FieldsBroken):
            planmarks.approved_items(self.board([item(), item()], fields))


class TestContractFields(PlanFieldsCase):
    """約束の欄（変えると関所に戻す物）と手段の欄（修正案の役が直してよい物）の表と、欄の比べ contract_diff"""

    def test_means_only_change_is_empty(self):
        old = item()
        new = copy.deepcopy(old)
        new["tests"][0]["red_kind"] = "exception"      # 224b の型
        new["tests"][0]["id"] = "test_stats.py::TestStats::test_mean_of_two_values"   # 225 の型
        new["approach"] = new["approach"] + "（直した）"
        self.assertEqual(planmarks.contract_diff(old, new), [])

    def test_contract_change_is_named(self):
        old = item()
        self.assertEqual(planmarks.contract_diff(old, item(allowed_paths=["stats.py", "lib/**/*.py"])), ["allowed_paths"])  # 195b の型
        self.assertEqual(planmarks.contract_diff(old, item(rewrite_tests=[REWRITE])), ["rewrite_tests"])                    # 194c の型
        beh = copy.deepcopy(old)
        beh["tests"][0]["behavior"] = "3 つの値の平均"
        self.assertEqual(planmarks.contract_diff(old, beh), ["tests.behavior"])

    def test_order_and_absence_do_not_count(self):
        """unit_keys の並べ替え・tests の並べ替え・欄が無いのと空の並びは違いに数えない。違いは CONTRACT_KEYS の順で並ぶ"""
        old = item(unit_keys=[MEAN, CLAMP])
        t2 = dict(old["tests"][0], id="test_stats.py::TestStats::test_mean_of_one", behavior="1 つの値の平均はその値")
        old["tests"].append(t2)
        new = copy.deepcopy(old)
        new["unit_keys"].reverse()
        new["tests"].reverse()
        del new["narrows"]
        self.assertEqual(planmarks.contract_diff(old, new), [])
        both = item(unit_keys=[CLAMP], out_of_scope=[{"glob": "docs/**", "why": "文書は今回の直しの外"}])
        self.assertEqual(planmarks.contract_diff(item(), both), ["unit_keys", "out_of_scope"])

    def test_files_add_side_is_means_and_removal_side_is_contract(self):
        """files の足す側だけを変えた時、contract_diff は空（手段の欄。同じ run の中で関所に戻さずに直せる）。消す側（op が delete・rename の
        行と change=remove の symbol）を変えた時は files を名指す。訳 why・受け持ち・正本の字の違いは約束の違いに数えない"""
        old = item(files=[frow("stats.py", fadd("median"), frm("old_mean")), frow("old.py", op="delete", why="呼び手は寄せたので要らない")])
        add_side = copy.deepcopy(old)
        add_side["files"][0]["symbols"].append(fadd("mode"))
        add_side["files"].append(frow("new.py", fadd("run"), op="create"))
        add_side["files"][0]["responsibility"] = "受け持ちの言い直し"
        add_side["files"][1]["why"] = "訳の言い直し（要らなくなったので消す）"
        self.assertEqual(planmarks.contract_diff(old, add_side), [])
        for name, edit in (("symbol を消す側に足した", lambda it: it["files"][0]["symbols"].append(frm("old_median"))),
                           ("消す行を足した", lambda it: it["files"].append(frow("gone.py", op="delete", why="要らなくなったので消す"))),
                           ("消す行の path を変えた", lambda it: it["files"][1].update(path="old2.py")),
                           ("消す symbol を外した", lambda it: it["files"][0]["symbols"].pop(1))):
            with self.subTest(name):
                new = copy.deepcopy(old)
                edit(new)
                self.assertEqual(planmarks.contract_diff(old, new), ["files"])
        # widened は files を丸ごと比べる: 足す側を変え、allowed_paths も広げた直しは『範囲を広げただけ』でない（None）
        base = item(files=[frow("stats.py", fadd("median"))])
        wide = {**base, "allowed_paths": ["stats.py", "README.md"]}
        self.assertEqual(planmarks.widened(base, wide), {"allowed_paths": ["README.md"], "out_of_scope": []})
        self.assertIsNone(planmarks.widened(base, {**wide, "files": [frow("stats.py", fadd("median"), fadd("mode"))]}))


class TestWidened(PlanFieldsCase):
    """範囲を広げるだけの直しか（widened）: 違いが allowed_paths に足した行と out_of_scope から外した行だけの時だけ、足した glob と
    外した glob を返す。ほかの欄（約束の欄も手段の欄も）が 1 つでも違えば・何も広げていなければ None（無人の run で関所を飛ばす決め手）"""

    OOS = [{"glob": "docs/**", "why": "文書は今回の直しの外に置く"}, {"glob": "README.md", "why": "利用者向けの説明は触らない"}]

    def test_added_allowed_paths(self):
        got = planmarks.widened(item(), item(allowed_paths=["stats.py", "README.md", "lib/*.py"]))
        self.assertEqual(got, {"allowed_paths": ["README.md", "lib/*.py"], "out_of_scope": []})

    def test_removed_out_of_scope(self):
        got = planmarks.widened(item(out_of_scope=self.OOS), item(out_of_scope=self.OOS[1:]))
        self.assertEqual(got, {"allowed_paths": [], "out_of_scope": ["docs/**"]})

    def test_both_at_once(self):
        got = planmarks.widened(item(out_of_scope=self.OOS), item(allowed_paths=["stats.py", "docs/a.md"], out_of_scope=[]))
        self.assertEqual(got, {"allowed_paths": ["docs/a.md"], "out_of_scope": ["docs/**", "README.md"]})

    def test_narrowing_or_other_changes_are_none(self):
        old = item(out_of_scope=self.OOS)
        wide = {"allowed_paths": ["stats.py", "README.md"]}
        red = copy.deepcopy(old["tests"])
        red[0]["red_kind"] = "exception"
        tid = copy.deepcopy(old["tests"])
        tid[0]["id"] = "test_stats.py::TestStats::test_mean_of_two_values"
        beh = copy.deepcopy(old["tests"])
        beh[0]["behavior"] = "3 つの値の平均を返す"
        cases = {
            "allowed_paths を外した": {"allowed_paths": []},
            "allowed_paths を差し替えた": {"allowed_paths": ["lib.py"]},
            "out_of_scope を足した": {"out_of_scope": [*self.OOS, {"glob": "lib/**", "why": "lib は今回の直しの外"}]},
            "out_of_scope の why を変えた": {"out_of_scope": [{**self.OOS[0], "why": "文書は別の依頼で直すので外"}, self.OOS[1]]},
            "rewrite_tests を足した": {**wide, "rewrite_tests": [REWRITE]},
            "red_kind も変えた": {**wide, "tests": red},
            "テストの id も変えた": {**wide, "tests": tid},
            "behavior も変えた": {**wide, "tests": beh},
            "approach も変えた": {**wide, "approach": "z" * 20},
            "files の足す側も変えた": {**wide, "files": [frow("stats.py", fadd("median"))]},
            "files の消す側も変えた": {**wide, "files": [frow("stats.py", frm("mean"))]},
            "narrows も変えた": {**wide, "narrows": [{"what": "空の列", "why": "空の列は例外のまま"}]},
            "unit_keys も変えた": {**wide, "unit_keys": [MEAN, CLAMP]},
            "route も変えた": {**wide, "route": "direct", "route_why": "z" * 20},
            "refactor も変えた": {**wide, "refactor": {"declared": True, "why": "z" * 20}},
            "何も変えない": {},
        }
        for name, over in cases.items():
            with self.subTest(name):
                self.assertIsNone(planmarks.widened(old, {**old, **copy.deepcopy(over)}))

    def test_old_without_scope_is_none(self):
        """範囲の欄の無い承認済みの項目（217 番の形の控え。範囲の縛りが無い）に allowed_paths を書いた直しは狭める物で、広げる物でない"""
        old = item()
        del old["allowed_paths"]
        self.assertIsNone(planmarks.widened(old, item(allowed_paths=["stats.py", "README.md"])))

    def test_order_and_rewrite_limit_do_not_count(self):
        """unit_keys・tests の並べ替え・rewrite_tests の範囲 limit（凍結の控えが足す）は違いに数えない（contract_diff と同じ読み）"""
        old = item(unit_keys=[MEAN, CLAMP], rewrite_tests=[{**REWRITE, "limit": "test_stats.py:12"}])
        new = item(unit_keys=[CLAMP, MEAN], rewrite_tests=[REWRITE], allowed_paths=["stats.py", "README.md"])
        self.assertEqual(planmarks.widened(old, new), {"allowed_paths": ["README.md"], "out_of_scope": []})

    def test_pure(self):
        old, new = item(out_of_scope=self.OOS), item(allowed_paths=["stats.py", "README.md"], out_of_scope=[])
        before = copy.deepcopy((old, new))
        planmarks.widened(old, new)
        self.assertEqual((old, new), before)


class TestStructure(PlanFieldsCase):
    """修正案の項目の欄 structure（計画 2026-10-09-clean-whole の Task 2.4）: 構造の目が汚れると見た単位を持つ項目は、その行ごとに
    避け方に従う（follows）か外れの訳（deviation）を書く。判定の処方（prescriptions）への答えも同じ欄に並べてよい"""
    OTHER = "stats.py clamp: 上限で lo を返す"
    DIRTY = {MEAN: {"unit_id": MEAN, "verdict": "汚れる", "chosen": "分母の決めを 1 か所に"},
             OTHER: {"unit_id": OTHER, "verdict": "汚れる", "chosen": "境の判定を 1 つに"}}
    WHY = "既存の呼び手が 3 つあり、今回は 1 か所に寄せると範囲が広がりすぎる"

    def test_plan_without_structure_row_is_refused(self):
        got = planmarks.structure_gaps([item()], [planmarks.design_need(self.DIRTY)])
        self.assertEqual(len(got), 1, got)
        self.assertIn(f"設計の行 {MEAN} に従うか、外れの訳を structure に書け", got[0])
        self.assertTrue(got[0].startswith("plan[0].structure"))

    def test_two_dirty_units_need_a_row_each(self):
        it = item(unit_keys=[MEAN, self.OTHER], structure=[{"row": MEAN, "follows": True}])
        got = planmarks.structure_gaps([it], [planmarks.design_need(self.DIRTY)])
        self.assertEqual(len(got), 1, got)
        self.assertIn(self.OTHER, got[0])
        it["structure"].append({"row": self.OTHER, "deviation": self.WHY})
        self.assertEqual(planmarks.structure_gaps([it], [planmarks.design_need(self.DIRTY)]), [])

    def test_clean_unit_needs_nothing(self):
        self.assertEqual(planmarks.structure_gaps([item()], [planmarks.design_need({})]), [])
        self.assertEqual(planmarks.structure_gaps([item()], [planmarks.design_need({self.OTHER: self.DIRTY[self.OTHER]})]), [])

    def test_bad_rows_are_named(self):
        for name, row in (("両方", {"row": MEAN, "follows": True, "deviation": self.WHY}),
                          ("どちらも無い", {"row": MEAN}),
                          ("短い訳", {"row": MEAN, "deviation": "短い"}),
                          ("汚れる行でない", {"row": "別の単位", "follows": True}),
                          ("行と処方の両方", {"row": MEAN, "prescription": MEAN, "follows": True}),
                          ("従わないと書く", {"row": MEAN, "follows": False})):
            with self.subTest(name):
                got = planmarks.structure_gaps([item(structure=[row])], [planmarks.design_need(self.DIRTY)])
                self.assertTrue(got, name)

    def test_prescription_answers_are_allowed(self):
        it = item(structure=[{"row": MEAN, "follows": True}, {"prescription": MEAN, "deviation": self.WHY}])
        self.assertEqual(planmarks.structure_gaps([it], [planmarks.design_need(self.DIRTY)]), [])
        self.assertEqual(self.gaps(it), [])

    def test_plan_with_deviation_passes_and_is_recorded(self):
        it = item(structure=[{"row": MEAN, "deviation": self.WHY}])
        self.assertEqual(planmarks.structure_gaps([it], [planmarks.design_need(self.DIRTY)]), [])
        self.assertEqual(self.gaps(it), [])
        bare, fields = planmarks.split({"plan": [it]}, self.repo)
        self.assertNotIn("structure", bare["plan"][0])
        self.assertEqual(fields[0]["structure"], [{"row": MEAN, "deviation": self.WHY}])
        self.assertEqual(planmarks.deviations(fields), [{"item": 1, "row": MEAN, "deviation": self.WHY}])


class TestWorldAnswers(PlanFieldsCase):
    """世界の解の行への答え（計画 world-solution の W8・5.3 節の 4）: 答えの要る行（applies が空でない）には、案のどれかの項目が
    欄 structure に {world: <類の id>, follows: true} か {world, deviation} を書き、どの項目も答えていない答えの要る行の在る案は拒む。
    足し方は構造の目の汚れる行と同じ structure_gaps（答えの要る行の表を受ける）で、世界の解の表は worldmark.need が作る"""
    WHY = "人の前の決定が仮の実装を禁じる（docs/decisions.md:40）ので定石に従わない"

    def rows(self):
        base = {"finding": 1, "where": "stats.py:3", "class_id": "w-mean", "problem": "平均の分母をどう決めるか",
                "activity": "統計の関数の直し", "practice": "算術平均は値の和を個数で割る", "sources": [],
                "applies": "平均の関数の直し", "not_applies": "", "versus": {"proposed": "", "verdict": "none", "challenge": ""},
                "basis": "knowledge", "cached": False}
        return [base, {**base, "finding": 2, "where": "docs/guide.md", "class_id": "w-doc", "applies": "案内の文書"}]

    def need(self, rows):
        import worldmark
        return worldmark.need(rows)

    def test_structure_gaps_shared_by_world_and_structure(self):
        dirty = {MEAN: {"unit_id": MEAN, "verdict": "汚れる", "chosen": "分母の決めを 1 か所に"}}
        rows = self.rows()[:1]
        tables = [planmarks.design_need(dirty), self.need(rows)]
        got = planmarks.structure_gaps([item()], tables)
        self.assertEqual(len(got), 2, got)
        self.assertTrue(any(f"設計の行 {MEAN}" in g for g in got), got)
        self.assertTrue(any("世界の解の行 w-mean" in g for g in got), got)
        it = item(structure=[{"row": MEAN, "follows": True}, {"world": "w-mean", "follows": True}])
        self.assertEqual(planmarks.structure_gaps([it], tables), [])
        it = item(structure=[{"row": MEAN, "follows": True}, {"world": "w-mean", "deviation": self.WHY}])
        self.assertEqual(planmarks.structure_gaps([it], tables), [])
        self.assertEqual(self.gaps(it), [])
        self.assertEqual(planmarks.deviations(planmarks.split({"plan": [it]}, self.repo)[1]),
                         [{"item": 1, "world": "w-mean", "deviation": self.WHY}])

    def test_unknown_world_class_is_named(self):
        it = item(structure=[{"world": "w-none", "follows": True}])
        got = planmarks.structure_gaps([it], [self.need(self.rows()[:1])])
        self.assertTrue(any("w-none" in g for g in got), got)

    def test_world_row_no_item_answers_is_refused(self):
        got = planmarks.structure_gaps([item(structure=[{"world": "w-mean", "follows": True}])], [self.need(self.rows())])
        self.assertEqual(len(got), 1, got)
        self.assertIn("w-doc", got[0])
        self.assertIn("どの項目も答えていない", got[0])


if __name__ == "__main__":
    unittest.main()
