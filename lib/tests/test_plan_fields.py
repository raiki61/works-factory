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
PLAN_KEYS = {"unit_keys", "approach", "adds", "removes", "shrink_first", "narrows"}   # 写しの graph の修正案の項目の欄


def item(**over):
    base = {"unit_keys": [MEAN], "approach": "x" * 20, "adds": [], "removes": [], "shrink_first": "y" * 20, "narrows": [],
            "route": "tdd", "route_why": "",
            "tests": [{"id": "test_stats.py::TestStats::test_mean_of_two", "behavior": "2 つの値の平均を返す",
                       "path": "stats.mean を直に呼ぶ（mock なし）", "red_kind": "assertion", "red_why": "今は len-1 で割り 3.0 になる"}],
            "rewrite_tests": [], "refactor": {"declared": False, "why": ""}, "allowed_paths": ["stats.py"], "out_of_scope": []}
    return {**base, **over}


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
        """kind が関数・欄（function・record_field）の adds の name がファイルの名・パスだけなら、行を名指して拒み、識別子で書いて
        パスは canonical に書けと言う（依頼 194c: receivers.py と書いた名を TDD の輪が 'py' と比べた）。ほかの誤りと同じ 1 回の拒否に
        並べる。識別子・<パス>::<名前>・説明の文・ファイルを名指すのが筋の kind（doc など）は今どおり通す"""
        def add(kind, name):
            return {"kind": kind, "name": name, "canonical": "新設: app/receivers.py"}
        got = self.gaps(item(adds=[add("function", "clamp"), add("function", "receivers.py"),
                                   add("record_field", "app/schema/fields.json"), add("function", " app/receivers ")], route="maybe"))
        for j, nm in ((1, "receivers.py"), (2, "app/schema/fields.json"), (3, "app/receivers")):
            row = [g for g in got if g.startswith(f"plan[0].adds[{j}].name")]
            self.assertEqual(len(row), 1, got)
            self.assertIn(nm, row[0])
            self.assertIn("canonical", row[0])
        self.assertFalse(any(g.startswith("plan[0].adds[0]") for g in got), got)
        self.assertTrue(any(g.startswith("plan[0].route") for g in got), got)          # ほかの誤りと 1 回で並ぶ
        for kind, name in (("function", "Stats.median"), ("function", "app.receivers.handle"),
                           ("function", "app/receivers.py::handle"), ("function", "role_run._probe(pgid_file) -> (pgid, why)"),
                           ("function", "tests/run.sh skip_capability（見送りの行から能力の名前を取り出す）"),
                           ("record_field", "plan[].adds[].name"), ("record_field", "event.ts"), ("function", "Response.json"),
                           ("record_field", "tests/_real_db.SKIP_REASON"),   # モジュールのパスと属性（本物の案の名）
                           ("function", "app/stats.mean"), ("record_field", "/plan/adds"),
                           ("doc", "docs/scope.md"), ("config", "setup.cfg"),
                           ("test", "test_stats.py::TestStats::test_mean_of_two"), ("other", "receivers.py")):
            with self.subTest(kind=kind, name=name):
                self.assertEqual(self.gaps(item(adds=[add(kind, name)])), [])

    def test_gaps_test_row_fields(self):
        t = {"id": "test_stats.py::TestStats::test_mean_of_two", "behavior": "短い", "red_kind": "import", "extra": 1}
        got = self.gaps(item(tests=[t]))
        for w in ("plan[0].tests[0].behavior", "plan[0].tests[0].red_kind", "'path'", "'red_why'", "'extra'"):
            self.assertTrue(any(w in g for g in got), (w, got))


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
        """removes（消す名）を base の本体で名指すテストは、欄の行の removes_tests に {id, limit} で並ぶ（義務でない許しの行）。
        探す木は渡された base_tests（作業ツリーで既に消えたテストも並ぶ）。名指さないテストは並ばない"""
        base_tests = {"test_stats.py": (SEED / "test_stats.py").read_text(encoding="utf-8")}
        tree = self.repo / "test_stats.py"
        tree.write_text(base_tests["test_stats.py"].replace(
            "    def test_clamp_within_range(self):\n        self.assertEqual(clamp(5, 0, 10), 5)\n\n", ""), encoding="utf-8")
        self.assertNotIn("test_clamp_within_range", tree.read_text(encoding="utf-8"))
        _, fields = planmarks.split({"plan": [item(removes=["stats.clamp"])]}, self.repo, base_tests=base_tests)
        got = sorted((r["id"], r["limit"]) for r in fields[0]["removes_tests"])
        self.assertEqual(got, [("test_stats.py::TestStats::test_clamp_above_range", "test_stats.py:14"),
                               ("test_stats.py::TestStats::test_clamp_within_range", "test_stats.py:11")])
        self.assertNotIn("test_stats.py::TestStats::test_mean_of_three", [r["id"] for r in fields[0]["removes_tests"]])

    def test_removes_tests_only_from_code_use(self):
        """removes の語が文字列（題・辞書の値・parametrize の値）や注釈の中にしか無いテストは removes_tests に並ばない。コードの
        名前・属性・点の付いたパスの文字列（mock.patch の的のどの段でも。デコレータでも）・属性の名の文字列（setattr・getattr・
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
        _, fields = planmarks.split({"plan": [item(removes=["Book"])]}, self.repo, base_tests={"tests/test_books.py": src})
        self.assertEqual([r["id"] for r in fields[0]["removes_tests"]],
                         ["tests/test_books.py::test_builds", "tests/test_books.py::test_patched",
                          "tests/test_books.py::test_fixture", "tests/test_books.py::test_attr",
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
        _, fields = planmarks.split({"plan": [item(removes=["pkg.vendors"])]}, self.repo,
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
        """split は項目の adds の name を写し、unit_contract の names は key を含む項目の name を順に重複なしで持つ"""
        add = lambda n: {"kind": "function", "name": n, "source": "x" * 10}
        reply = {"plan": [item(adds=[add("clamp"), add("mean")]), item(adds=[add("clamp")], unit_keys=[MEAN, CLAMP]),
                          item(adds=[add("other")], unit_keys=[CLAMP]), item(adds=[], unit_keys=[MEAN])]}
        _, fields = planmarks.split(reply, self.repo)
        self.assertEqual(fields[0]["adds"], ["clamp", "mean"])
        self.assertEqual(planmarks.unit_contract(fields, MEAN)["names"], ["clamp", "mean"])
        self.assertEqual(planmarks.unit_contract(fields, CLAMP)["names"], ["clamp", "other"])
        self.assertEqual(planmarks.unit_contract([{"unit_keys": [MEAN]}], MEAN)["names"], [])
        self.assertIsNone(planmarks.unit_contract(fields, "無い単位"))

    def test_names_carry_new_module_of_canonical(self):
        """canonical が新設の .py のパスを名指す adds は、そのパスも宣言した名前に足す（新しいモジュールの import の失敗を TDD の輪が
        宣言の赤に数える。依頼 194c: read_input の canonical が works/.shared/core/nodeio.py（新設…）で、No module named 'nodeio' が
        綴りの誤りに数えられた）。新設でない canonical・.py でないパス・作業ツリーに在るファイル（在るモジュールに新設の関数を
        足す行）・根の外のパスは足さない。重なりは 1 つ"""
        add = lambda n, c: {"kind": "function", "name": n, "canonical": c}
        reply = {"plan": [item(adds=[add("read_input", "works/.shared/core/nodeio.py（新設。前の節の出力を読む口）"),
                                     add("board_out", "works/.shared/core/nodeio.py（新設。盤面の控えから読む口）"),
                                     add("handle", "新設: app/receivers.py（受け手の表）"),
                                     add("mean", "stats.py の既存の mean を直す"),
                                     add("fmt", "既存の textfmt.py から引く（新設しない result.py を読む）"),
                                     add("golden", "works/tests/fixtures/golden.json（新設）"),
                                     add("median", "stats.py（新設。在るモジュールに足す関数）"),
                                     add("up", "../up.py（新設）")])]}
        _, fields = planmarks.split(reply, self.repo)
        self.assertEqual(fields[0]["adds"], ["read_input", "works/.shared/core/nodeio.py", "board_out", "handle",
                                             "app/receivers.py", "mean", "fmt", "golden", "median", "up"])
        self.assertEqual(planmarks.unit_contract(fields, MEAN)["names"], fields[0]["adds"])


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
        self.assertEqual(set(bare["plan"][0]), {"unit_keys", "approach", "adds", "removes", "shrink_first", "narrows"})
        self.assertEqual((fields[0]["allowed_paths"], fields[0]["out_of_scope"]), (["stats.py"], []))

    def test_head_and_review_ask_name_scope_fields(self):
        for w in ("allowed_paths", "out_of_scope", "識別子", "canonical", "removes"):
            self.assertIn(w, planmarks.HEAD)
        self.assertIn("allowed_paths", planmarks.REVIEW_ASK)

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
            "adds も変えた": {**wide, "adds": [{"kind": "function", "name": "median", "canonical": "stats.py の median"}]},
            "removes も変えた": {**wide, "removes": ["mean"]},
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
