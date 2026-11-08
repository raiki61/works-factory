"""変更の周りの地図（.shared/core/impact.py）と、その土台の写し（.shared/core/changemap.py）の検査。

- 写し: changemap.py は attention の変更の地図の部品（attention/scripts/lib/changemap.py）のバイト単位の写しで、
  COPIED_FROM.changemap の 1 行目の commit と同じ（手直しは台帳の ! 行だけ）
- 地図: 使い捨ての小さなリポジトリ（gitkit の型の写し）で、逆向きの import・テストの見分け・名前の言及・YAML の参照・
  読めない物 → all_tests_required・盤面の置き場の使い回し（当たり・変わった file だけ読み直す。読み直した地図は同じ）
- 選ぶ: select_tests が速い段と選んだテストの和を返し、分からない時は全部
"""
import inspect
import pathlib
import shutil
import sys
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1]
if str(LIB) not in sys.path:
    sys.path.append(str(LIB))

import changemap  # noqa: E402
import impact  # noqa: E402
from tests.bin.gitkit import committed_copy, git  # noqa: E402

# 使い捨てのリポジトリの中身（path → 中身）
PROJ = {
    "pkg/__init__.py": "",
    "pkg/core.py": "def compute_total(x):\n    return x + 1\n\n\ndef helper():\n    return 2\n",
    "pkg/mid.py": "from pkg.core import compute_total\n\n\ndef use():\n    return compute_total(1)\n",
    "pkg/rel.py": "from . import core\n",
    "app/main.py": "import sys\nfrom pkg import mid\n\nprint(mid.use(), sys.argv)\n",
    "tests/test_core.py": "import unittest\n\nfrom pkg import core\n\n\nclass T(unittest.TestCase):\n    def test_a(self):\n"
                          "        self.assertEqual(core.helper(), 2)\n",
    "tests/test_mid.py": "from pkg.mid import use\n\nassert use() == 2\n",
    "tests/test_other.py": "import json\n\nassert json.loads('1') == 1\n",
    "tests/test_cli.py": "import subprocess\n\nsubprocess.run(['sh', 'scripts/run-job.sh'], check=False)\n",
    "tests/helper.py": "import os\n",
    "scripts/run-job.sh": "#!/bin/sh\npython3 app/main.py\n",
    ".github/workflows/ci.yml": "jobs:\n  t:\n    steps:\n      - run: sh scripts/run-job.sh\n",
    "docs/guide.md": "# guide\n\nSee `pkg/core.py` and compute_total.\n",
    "docs/設計.md": "core.py の中身は pkg/core.py にある\n",
    "conf/settings.json": '{"entry": "app/main.py"}\n',
    "lonely/solo.py": "def lonely_function():\n    pass\n",
    "web/widget.js": "export function widget() { return 1 }\n",
}

_SRC = None


def setUpModule():
    global _SRC
    _SRC = pathlib.Path(tempfile.mkdtemp(prefix="works-impact-src-"))
    for rel, text in PROJ.items():
        p = _SRC / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def tearDownModule():
    shutil.rmtree(_SRC, ignore_errors=True)


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="works-impact-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = self.tmp / "repo"
        self.head = committed_copy(self.repo, _SRC)
        self.cache = self.tmp / "cache"

    def write(self, rel, text):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def map(self, seeds=(), **kw):
        return impact.map(self.repo, seeds=seeds, **kw)


class CopyCase(unittest.TestCase):
    def test_copy_has_no_short_deadline(self):
        self.assertNotIn("timeout=15", (LIB / "changemap.py").read_text(encoding="utf-8"))


class ReverseImportCase(RepoCase):
    def test_reverse_imports_are_transitive_and_relative(self):
        m = self.map(["pkg/core.py"])
        self.assertEqual(m["seeds"]["files"], ["pkg/core.py"])
        rev = set(m["reverse_imports"])
        self.assertTrue({"pkg/mid.py", "pkg/rel.py", "app/main.py", "tests/test_core.py", "tests/test_mid.py"} <= rev, rev)
        self.assertNotIn("tests/test_other.py", rev)
        self.assertNotIn("lonely/solo.py", rev)
        self.assertEqual(m["reach"]["pkg/mid.py"]["depth"], 1)
        self.assertEqual(m["reach"]["app/main.py"]["depth"], 2)
        self.assertEqual(m["reach"]["app/main.py"]["parent"]["from"], "pkg/mid.py")
        # 当たりの行は 1 文字も変えずに持つ
        edge = next(e for e in m["edges"] if e["path"] == "pkg/mid.py" and e["dep"] == "pkg/core.py")
        self.assertEqual(edge["kind"], "import")
        self.assertEqual(edge["hits"], [[1, "from pkg.core import compute_total"]])

    def test_tests_are_detected_and_selected(self):
        m = self.map(["pkg/core.py"])
        # test_cli は sh を起こし、sh が app/main.py を起こし、main が mid を、mid が core を読む（言及を挟むので候補）
        self.assertEqual(m["tests"], ["tests/test_cli.py", "tests/test_core.py", "tests/test_mid.py"])
        self.assertFalse(m["reach"]["tests/test_core.py"]["candidate"])
        self.assertTrue(m["reach"]["tests/test_cli.py"]["candidate"])
        self.assertEqual(m["reach"]["tests/test_cli.py"]["parent"]["from"], "scripts/run-job.sh")
        self.assertNotIn("tests/helper.py", m["tests"])
        self.assertFalse(m["all_tests_required"], m["all_tests_reasons"])
        sel = impact.select_tests(m, fast=["test_other"])
        self.assertFalse(sel["run_all"])
        self.assertEqual(sel["selected"], ["tests/test_cli.py", "tests/test_core.py", "tests/test_mid.py"])
        self.assertEqual(sel["modules"], ["test_cli", "test_core", "test_mid", "test_other"])
        self.assertEqual(impact.select_tests(m, scope="tests/test_c")["modules"], ["test_cli", "test_core"])

    def test_direct_selection_keeps_only_tests_next_to_the_change(self):
        # 直に関わる試験だけ: 起点のテスト・起点を直に読む・言及する試験（深さ 1）・名指しの試験。先の物は left に名前で残す
        m = self.map(["pkg/core.py"])
        sel = impact.select_tests(m, direct_only=True)
        self.assertEqual(sel["selected"], ["tests/test_core.py"])
        self.assertEqual(sel["modules"], ["test_core"])
        self.assertEqual(sel["left"], ["tests/test_cli.py", "tests/test_mid.py"])
        named = impact.select_tests(m, direct_only=True, named=["tests/test_mid.py"])
        self.assertEqual(named["selected"], ["tests/test_core.py", "tests/test_mid.py"])
        self.assertEqual(named["left"], ["tests/test_cli.py"])
        self.assertEqual(impact.select_tests(m)["left"], [], "広い選びは何も残さない")
        seeded = impact.select_tests(self.map(["tests/test_mid.py"]), direct_only=True)
        self.assertEqual(seeded["selected"], ["tests/test_mid.py"], "起点のテストは直に関わる")

    def test_direct_selection_still_runs_all_when_unanalysable_is_near(self):
        m = self.map(["web/widget.js"])
        sel = impact.select_tests(m, direct_only=True, all_modules=["test_a"])
        self.assertTrue(sel["run_all"])
        self.assertEqual((sel["modules"], sel["left"]), (["test_a"], []))


class MentionCase(RepoCase):
    def test_mentions_and_symbol_hits_are_candidates(self):
        m = self.map(["pkg/core.py"])
        self.assertIn("docs/guide.md", m["refs"])
        hits = [e for e in m["edges"] if e["path"] == "docs/guide.md"]
        self.assertEqual({e["kind"] for e in hits}, {"path", "symbol"})
        self.assertTrue(all(e["candidate"] for e in hits))
        self.assertIn([3, "See `pkg/core.py` and compute_total."], hits[0]["hits"])
        # 日本語の名前は引用形にならない（core.quotePath=false と同じ）
        self.assertIn("docs/設計.md", m["refs"])

    def test_yaml_refs_and_shell_mentions_reach_tests(self):
        m = self.map(["scripts/run-job.sh"])
        self.assertIn(".github/workflows/ci.yml", m["refs"])
        e = next(e for e in m["edges"] if e["path"] == ".github/workflows/ci.yml")
        self.assertEqual(e["hits"], [[4, "      - run: sh scripts/run-job.sh"]])
        self.assertEqual(m["tests"], ["tests/test_cli.py"])
        self.assertTrue(m["reach"]["tests/test_cli.py"]["candidate"])
        m2 = self.map(["app/main.py"])
        self.assertIn("conf/settings.json", m2["refs"])
        self.assertIn("scripts/run-job.sh", m2["mentions"])
        # sh の言及から先へ伸びる（sh → test_cli）
        self.assertIn("tests/test_cli.py", m2["tests"])

    def test_name_seed_is_searched_as_symbol(self):
        m = self.map(["compute_total"])
        self.assertEqual(m["seeds"]["names"], ["compute_total"])
        self.assertIn("docs/guide.md", m["refs"])
        self.assertIn("pkg/core.py", m["mentions"])
        # mid は名前を書き（symbol）、core も読む（import）。届いた file の分類は import が先
        self.assertIn("pkg/mid.py", m["reverse_imports"])
        self.assertTrue(any(e["path"] == "pkg/mid.py" and e["kind"] == "symbol" and e["dep"] == "compute_total"
                            for e in m["edges"]))


class TestIsTest(unittest.TestCase):
    def test_is_test_by_cross_ecosystem_convention(self):
        # テストの実行器が自分で探す名の形（語の頭・尾）。言語の表でなく名の形 1 つで、文書・設定の拡張子には当てない
        for path in ("src/test/java/FooTest.java", "spec/foo_spec.rb", "src/foo_test.zig", "Calc.Tests/FooTests.cs",
                     "src/test/scala/FooSpec.scala", "src/test/java/FooIT.java", "web/foo.test.ts", "web/foo.spec.js",
                     "pkg/calc_test.go", "Tests/AppTests/APITests.swift", "src/test/java/UUIDTest.java",
                     "tests/test_core.py", "tests/core_test.py", "conftest.py", "t/x-case.py", "t/y.bats"):
            with self.subTest(path=path):
                self.assertEqual(impact.is_test(path), "module")
        for path in ("data/test_data.json", "docs/test_notes.md", "conf/test_ci.yml", "src/Contest.java",
                     "src/latest.go", "scripts/run_tests.sh", "src/attest.rs",
                     "tests/boards/steps/test_awaiting.json.gz",
                     # 語の尾の慣習（Spec・Test・IT）はテストのフォルダの下だけ（実装の KeySpec・job_spec・AbTest を数えない）
                     "src/main/java/KeySpec.java", "pkg/job_spec.go", "src/AbTest.java", "web/ApiSpec.ts",
                     # Python は実行器の慣習（TEST_NAME。pytest の python_files）だけ: 実装の tensor_spec.py・FooTest.py は数えない
                     "pkg/tensor_spec.py", "tests/FooTest.py"):
            with self.subTest(path=path):
                self.assertNotEqual(impact.is_test(path), "module")

    def test_is_test_file_declared_or_convention(self):
        """宣言と名の慣習を合わせた見分け: 宣言の組に在れば慣習に当たらない名もテスト（綴りは正規化してから照らす）"""
        self.assertTrue(impact.is_test_file("checks/verify.py", {"checks/verify.py"}), "慣習に当たらない名も宣言なら")
        self.assertTrue(impact.is_test_file("./checks/verify.py", {"checks/verify.py"}), "正規化の前の綴りでも宣言なら")
        self.assertFalse(impact.is_test_file("checks/verify.py", set()))
        for path in ("test_stats.py", "x_test.py", "conftest.py", "pkg/calc_test.go", "src/test/java/FooTest.java"):
            with self.subTest(path=path):
                self.assertTrue(impact.is_test_file(path, set()))
        self.assertFalse(impact.is_test_file("stats.py", set()))

    def test_is_code_known_code_extensions_only(self):
        """is_code は既知のコードの拡張子（Python と、import を読まない言語の表と、mentions がコードと数えるシェルなどの拡張子）
        だけに真を返す。文書とデータ・設定・知らない拡張子・拡張子の無い名は偽"""
        self.assertTrue(hasattr(impact, "is_code"), "impact に is_code が無い")
        for path in ("stats.py", "pkg/types.pyi", "web/app.js", "web/app.ts", "web/App.tsx", "cmd/main.go", "src/Main.java",
                     "lib/tool.rb", "src/lib.rs", "bin/run.sh", "scripts/x.bash", "build.mk"):
            with self.subTest(path=path, want=True):
                self.assertTrue(impact.is_code(path))
        for path in ("__snapshots__/x.snap", "docs/guide.md", "testdata/case.txt", "testdata/rows.csv", "expected.json",
                     "conf/ci.yaml", "golden/out.golden", "testdata/input", "Makefile"):
            with self.subTest(path=path, want=False):
                self.assertFalse(impact.is_code(path))
        # コードかどうかの分けは、mentions（コード）と refs（設定・文書）の分け（REF_EXT）と割れない
        for ext in impact.PY_EXT | impact.OTHER_CODE_EXT | impact.PATHREF_EXT | impact.DOC_EXT:
            with self.subTest(ext=ext):
                if impact.is_code("a." + ext):
                    self.assertNotIn(ext, impact.REF_EXT)


    def test_is_test_data_under_data_dirs(self):
        """is_test_data は、親のフォルダのどれかが試験のデータの置き場の名（testdata・fixtures・__fixtures__・__snapshots__・golden）
        のパスに真を返す。実装・試験のフォルダのコードは偽。is_test は広げず、データの置き場の下のコードは None のまま"""
        self.assertTrue(hasattr(impact, "is_test_data"), "impact に is_test_data が無い")
        for path in ("testdata/expected.go", "__fixtures__/expected.ts", "fixtures/expected_out.py", "__snapshots__/a.ts",
                     "golden/out.go", "pkg/testdata/deep/expected.go"):
            with self.subTest(path=path, want=True):
                self.assertTrue(impact.is_test_data(path))
        for path in ("stats.py", "src/app.go", "tests/test_x.py", "testdata.py", "pkg/golden_out.go"):
            with self.subTest(path=path, want=False):
                self.assertFalse(impact.is_test_data(path))
        self.assertIsNone(impact.is_test("testdata/expected.go"))


class UnanalysableCase(RepoCase):
    def test_unknown_language_seed_requires_all(self):
        m = self.map(["web/widget.js"])
        self.assertTrue(m["all_tests_required"])
        self.assertTrue(any("unknown-language" in r for r in m["all_tests_reasons"]))
        sel = impact.select_tests(m, fast=["test_other"], all_modules=["test_a", "test_b"])
        self.assertTrue(sel["run_all"])
        self.assertEqual(sel["modules"], ["test_a", "test_b"])

    def test_unknown_extension_selects_tests(self):
        # 表に無い拡張子（ここでは Zig）のコードを直した変更も、分からない＝全部を回す（文書と見なして何も選ばない形にしない）
        self.write("native/calc.zig", "pub fn add(a: i32, b: i32) i32 {\n    return a + b;\n}\n")
        m = self.map(["native/calc.zig"])
        self.assertTrue(m["all_tests_required"], m["all_tests_reasons"])
        self.assertIn("unknown-language: native/calc.zig", m["all_tests_reasons"])
        sel = impact.select_tests(m, all_modules=["test_a"])
        self.assertTrue(sel["run_all"])

    def test_python_spec_module_keeps_mention_edges(self):
        # 実装の x_spec.py は試験のモジュールでない（言及の辺を持ち、それを走らせる殻の試験が選ばれる）
        self.write("pkg/job_spec.py", "def build_job():\n    return 1\n")
        self.write("scripts/go.sh", "#!/bin/sh\npython3 pkg/job_spec.py\n")
        self.write("tests/go.bats", "@test go { sh scripts/go.sh; }\n")
        m = self.map(["pkg/job_spec.py"])
        self.assertIn("tests/go.bats", m["tests"])
        self.assertNotIn("pkg/job_spec.py", m["tests"])

    def test_linguist_documentation_attribute_marks_doc(self):
        # 表に無い拡張子でも、git の属性 linguist-documentation（GitHub Linguist の事実上の標準）で文書と宣言した物は文書
        self.write("ledger/COPIED_FROM.calc", "pkg/core.py  upstream/core.py\n")
        m = self.map(["ledger/COPIED_FROM.calc"])
        self.assertTrue(m["all_tests_required"], "宣言が無ければ読めないコード")
        self.write(".gitattributes", "ledger/COPIED_FROM.* linguist-documentation\n")
        m = self.map(["ledger/COPIED_FROM.calc"])
        self.assertFalse(m["all_tests_required"], m["all_tests_reasons"])

    def test_known_doc_and_dotfile_stay_doc(self):
        # 文書・データの拡張子、ドットで始まる設定の名、拡張子もシバンも無い名は今どおり文書（全部を回さない）
        for rel in ("notes/plan.md", "data/rows.jsonl", "conf/.gitignore", "LICENSE", "locale/ja.po", "__snapshots__/a.snap"):
            with self.subTest(rel=rel):
                self.write(rel, "plain words only\n")
                m = self.map([rel])
                self.assertFalse(m["all_tests_required"], m["all_tests_reasons"])

    def test_unanalysable_outside_the_neighbourhood_is_only_counted(self):
        m = self.map(["lonely/solo.py"])
        self.assertFalse(m["all_tests_required"])
        self.assertEqual(m["tests"], [])
        self.assertEqual(m["not_seen"]["unanalysable"].get("unknown-language"), 1)

    def test_dynamic_import_in_the_neighbourhood_requires_all(self):
        self.write("plug/loader.py", "import importlib\nfrom pkg import core\n\n\ndef load(name):\n"
                                     "    return importlib.import_module(name)\n")
        m = self.map(["pkg/core.py"])
        self.assertTrue(m["all_tests_required"])
        u = next(u for u in m["unanalysable"] if u["path"] == "plug/loader.py")
        self.assertEqual((u["reason"], u["line"]), ("dynamic-import", 6))
        self.assertTrue(u["in_neighbourhood"])

    def test_direct_selection_runs_all_only_when_unanalysable_is_direct(self):
        # 直に関わる選びでは、分からない物が起点か深さ 1 に在る時だけ全部。深さ 2 以上の物は far に残す（最後のテストの段が一式）
        self.write("plug/far.py", "import importlib\nfrom pkg import mid\n\n\ndef load(name):\n"
                                  "    return importlib.import_module(name)\n")
        m = self.map(["pkg/core.py"])
        self.assertEqual(m["reach"]["plug/far.py"]["depth"], 2)
        self.assertTrue(m["all_tests_required"], "地図そのものの決まりは変えない")
        self.assertTrue(impact.select_tests(m)["run_all"], "広い選びは今どおり全部")
        sel = impact.select_tests(m, direct_only=True)
        self.assertFalse(sel["run_all"])
        self.assertEqual(sel["selected"], ["tests/test_core.py"])
        self.assertEqual(sel["far"], ["dynamic-import: plug/far.py:6"])
        self.write("plug/near.py", "import importlib\nfrom pkg import core\n\n\ndef load(name):\n"
                                   "    return importlib.import_module(name)\n")
        near = impact.select_tests(self.map(["pkg/core.py"]), direct_only=True)
        self.assertTrue(near["run_all"], "深さ 1 の分からない物が在れば全部")
        self.assertEqual(near["left"], [])

    def test_deferring_caller_keeps_left_and_far_when_run_all(self):
        self.assertIn("defer_all", inspect.signature(impact.select_tests).parameters)
        self.write("plug/near.py", "import importlib\nfrom pkg import core\n\n\ndef load(name):\n"
                                   "    return importlib.import_module(name)\n")
        self.write("plug/far.py", "import importlib\nfrom pkg import mid\n\n\ndef load(name):\n"
                                  "    return importlib.import_module(name)\n")
        m = self.map(["pkg/core.py"])
        sel = impact.select_tests(m, direct_only=True, defer_all=True)
        self.assertTrue(sel["run_all"])
        self.assertEqual(sel["left"], ["tests/test_cli.py", "tests/test_mid.py"])
        self.assertEqual(sel["far"], ["dynamic-import: plug/far.py:6"])
        self.assertEqual(sel["selected"], ["tests/test_cli.py", "tests/test_core.py", "tests/test_mid.py"])
        plain = impact.select_tests(m, direct_only=True)
        self.assertTrue(plain["run_all"])
        self.assertEqual((plain["left"], plain["far"]), ([], []))

    def test_deferring_flag_changes_nothing_when_not_run_all(self):
        far_only = "import importlib\nfrom pkg import mid\n\n\ndef load(name):\n    return importlib.import_module(name)\n"
        for case, files in (("nothing unreadable near", {}), ("unreadable only two steps away", {"plug/far.py": far_only})):
            with self.subTest(case=case):
                for rel, text in files.items():
                    self.write(rel, text)
                m = self.map(["pkg/core.py"])
                plain = impact.select_tests(m, direct_only=True)
                deferring = impact.select_tests(m, direct_only=True, defer_all=True)
                self.assertFalse(plain["run_all"])
                self.assertEqual(deferring, plain)
                self.assertIn("tests/test_mid.py", deferring["left"], "深さ 2 の試験は left に残る")

    def test_constant_dynamic_import_is_an_import(self):
        self.write("plug/fixed.py", "import importlib\n\nmod = importlib.import_module('pkg.core')\n")
        m = self.map(["pkg/core.py"])
        self.assertFalse(m["all_tests_required"], m["all_tests_reasons"])
        self.assertIn("plug/fixed.py", m["reverse_imports"])

    def test_parse_error_that_may_import_requires_all(self):
        self.write("pkg/broken.py", "from pkg import core\ndef (:\n")
        m = self.map(["pkg/core.py"])
        self.assertTrue(m["all_tests_required"])
        self.assertIn("py-parse-error", {u["reason"] for u in m["unanalysable"] if u["path"] == "pkg/broken.py"})

    def test_too_deep_python_is_a_parse_error_not_a_crash(self):
        # 構文木を組む途中で深さが尽きる file（RecursionError・パーサの MemoryError）も読めない物に数え、地図を落とさない
        self.write("pkg/deep.py", "from pkg import core\nx = 1" + " + 1" * 100000 + "\n")
        self.write("pkg/deeper.py", "from pkg import core\nx = " + "-" * 100000 + "1\n")
        m = self.map(["pkg/core.py"])
        self.assertTrue(m["all_tests_required"])
        reasons = {u["path"]: u["reason"] for u in m["unanalysable"]}
        self.assertEqual((reasons.get("pkg/deep.py"), reasons.get("pkg/deeper.py")), ("py-parse-error", "py-parse-error"))


class ConftestCase(RepoCase):
    """conftest.py の fixture 越しに変更を使うテスト（client の fixture の形）は、テストのファイルが変更を import しなくても届く"""

    def test_tests_under_a_reached_conftest_are_reached(self):
        self.write("tests/conftest.py", "import pytest\n\nfrom pkg import core\n\n\n@pytest.fixture\ndef client():\n"
                                        "    return core\n")
        self.write("tests/api/test_api.py", "def test_get(client):\n    assert client.helper() == 2\n")
        self.write("elsewhere/test_far.py", "def test_far(client):\n    assert client\n")
        m = self.map(["pkg/core.py"])
        self.assertIn("tests/conftest.py", m["tests"])
        self.assertIn("tests/api/test_api.py", m["tests"])
        self.assertNotIn("elsewhere/test_far.py", m["tests"], "conftest.py のフォルダの外のテストには届かない")
        r = m["reach"]["tests/api/test_api.py"]
        self.assertEqual((r["parent"]["from"], r["parent"]["kind"], r["mention_hops"]), ("tests/conftest.py", "conftest", 0))
        self.assertEqual(r["depth"], m["reach"]["tests/conftest.py"]["depth"] + 1)
        self.assertIn("tests/api/test_api.py", m["reverse_imports"], "fixture の辺は import と同じく確かな依り")
        self.assertFalse(r["candidate"])


class RuntimeReadsCase(RepoCase):
    """実行時に glob や open で開く file は、字の言及でも import でも届かない。読む部品が一番上の RUNTIME_READS に宣言した物は、
    宣言した module と、それを直に import する module を依る側にした深さ 1 の確かな辺（reads）で届く"""

    def setUp(self):
        super().setUp()
        self.write("tests/test_flow.py", 'RUNTIME_READS = ("flows/",)\n')
        self.write("flows/sub/b.yaml", "nodes: []\n")
        self.write("flows2/x.yaml", "nodes: []\n")

    def test_declared_reads_make_the_reader_direct(self):
        m = self.map(["flows/sub/b.yaml"])
        self.assertIn("tests/test_flow.py", m["reach"], "宣言した下の file の変更は、宣言した試験に届く")
        r = m["reach"]["tests/test_flow.py"]
        self.assertEqual((r["depth"], r["parent"]["from"], r["parent"]["kind"]), (1, "flows/sub/b.yaml", "reads"))
        self.assertFalse(r["candidate"])
        self.assertIn("tests/test_flow.py", m["reverse_imports"], "宣言の辺は import と同じく確かな依り")
        sel = impact.select_tests(m, direct_only=True)
        self.assertIn("tests/test_flow.py", sel["selected"])
        self.assertNotIn("tests/test_flow.py", sel["left"])
        self.assertNotIn("tests/test_flow.py", self.map(["flows2/x.yaml"])["reach"], "宣言の外の file には届かない")
        with self.subTest(case="a value that does not end with a slash is the path itself"):
            self.write("tests/test_data.py", 'RUNTIME_READS = ("flows2/x.yaml",)\n')
            self.assertIn("tests/test_data.py", self.map(["flows2/x.yaml"])["reach"])
            self.assertNotIn("tests/test_data.py", self.map(["flows/sub/b.yaml"])["reach"])
        with self.subTest(case="the name inside a string or a function is not a declaration"):
            self.write("tests/test_text.py", 'NOTE = "RUNTIME_READS = (\'flows2/\',)"\n\n\ndef f():\n'
                                             '    RUNTIME_READS = ("flows2/",)\n')
            self.assertNotIn("tests/test_text.py", self.map(["flows2/x.yaml"])["reach"])
        with self.subTest(case="the map and the fence read a declaration the same way"):
            self.assertEqual(impact.py_reads('RUNTIME_READS = ("a/", "b.json")\n'), ["a/", "b.json"])
            self.assertIsNone(impact.py_reads("RUNTIME_READS = (\n"))
            files = ["a/x.yaml", "a/y/z.yaml", "ab/q", "b.json", "b.json5"]
            self.assertEqual(impact.reads_hits(["a/", "b.json"], files), ["a/x.yaml", "a/y/z.yaml", "b.json"])

    def test_a_test_importing_the_declaring_helper_is_direct(self):
        self.write("tests/flowread.py", 'RUNTIME_READS = ("flows/",)\n')
        self.write("tests/test_uses.py", "from tests import flowread\n")
        self.write("tests/test_far_uses.py", "from tests import test_uses\n")
        m = self.map(["flows/sub/b.yaml"])
        r = m["reach"]["tests/test_uses.py"]
        self.assertEqual((r["depth"], r["parent"]["from"], r["parent"]["kind"]), (1, "flows/sub/b.yaml", "reads"))
        self.assertFalse(r["candidate"])
        self.assertEqual(m["reach"]["tests/test_far_uses.py"]["depth"], 2, "宣言を受け継ぐのは直に import する module だけ")
        sel = impact.select_tests(m, direct_only=True)
        self.assertIn("tests/test_uses.py", sel["selected"])
        self.assertIn("tests/test_far_uses.py", sel["left"])
        self.assertNotIn("tests/test_uses.py", self.map(["flows2/x.yaml"])["reach"], "宣言の外の file には届かない")

    def test_files_without_a_declaration_keep_their_reach(self):
        seeds = ["pkg/core.py", "pkg/mid.py"]
        with_decl = self.map(seeds)
        (self.repo / "tests/test_flow.py").unlink()
        without = self.map(seeds)
        self.assertEqual(with_decl["reach"], without["reach"])
        self.assertEqual(with_decl["edges"], without["edges"])
        self.assertEqual([e for e in without["edges"] if e["kind"] == "reads"], [])
        r = without["reach"]["tests/test_core.py"]
        self.assertEqual((r["depth"], r["parent"]["from"], r["parent"]["kind"], r["candidate"]),
                         (1, "pkg/core.py", "import", False))
        self.assertEqual(without["reach"]["tests/test_mid.py"]["parent"]["kind"], "import")


class PrecisionCase(RepoCase):
    """自分の木（works を含むリポジトリ）で回して見つけた取り違えの留め"""

    def test_sys_path_suffix_picks_the_nearest_copy(self):
        # alpha/tool.py は alpha を sys.path に足す。beta/alpha も同じ字で終わるが、近いのは alpha
        for root in ("alpha", "beta/alpha"):
            self.write(f"{root}/engine/__init__.py", "")
            self.write(f"{root}/engine/advance.py", "X = 1\n")
        self.write("alpha/tool.py", "import pathlib\nimport sys\n\nROOT = pathlib.Path(__file__).parents[1]\n"
                                    "sys.path.insert(0, str(ROOT / 'alpha'))\nimport engine.advance\n")
        near = self.map(["alpha/engine/advance.py"])
        self.assertIn("alpha/tool.py", near["reverse_imports"])
        e = next(e for e in near["edges"] if e["path"] == "alpha/tool.py" and e["kind"] == "import")
        self.assertEqual(e["resolution"], "sys.path")
        far = self.map(["beta/alpha/engine/advance.py"])
        self.assertNotIn("alpha/tool.py", far["reach"])

    def test_names_stay_inside_their_project(self):
        self.write("other/pyproject.toml", "[project]\nname = 'other'\n")
        self.write("other/uses.py", "compute_total = None\n")
        self.write("pyproject.toml", "[project]\nname = 'root'\n")
        m = self.map(["pkg/core.py"])
        self.assertNotIn("other/uses.py", m["reach"])
        self.assertGreaterEqual(m["not_seen"]["ambiguous_mentions"], 1)

    def test_symbol_hits_are_leaves(self):
        # 関数名を書いただけの sh は届くが、その sh を呼ぶテストへは伸ばさない（使う側は import で辿る）
        self.write("scripts/calls-total.sh", "echo compute_total\n")
        self.write("tests/test_calls.py", "import subprocess\n\nsubprocess.run(['sh', 'scripts/calls-total.sh'])\n")
        m = self.map(["pkg/core.py"])
        self.assertIn("scripts/calls-total.sh", m["mentions"])
        self.assertNotIn("tests/test_calls.py", m["tests"])
        # 名前の起点なら伸ばす
        self.assertIn("tests/test_calls.py", self.map(["compute_total"])["tests"])

    def test_fixture_data_is_a_leaf_and_plain_lowercase_names_are_not_keys(self):
        self.write("tests/fixtures/data.json", '{"runs": "scripts/run-job.sh"}\n')
        self.write("tests/test_fix.py", "open('tests/fixtures/data.json').read()\n")
        m = self.map(["scripts/run-job.sh"])
        self.assertIn("tests/fixtures/data.json", m["refs"])
        self.assertNotIn("tests/test_fix.py", m["tests"])
        self.write("pkg/extra.py", "def problems():\n    pass\n\n\nclass DiskThing:\n    pass\n")
        self.write("docs/extra.md", "problems and DiskThing\n")
        m2 = self.map(["pkg/extra.py"])
        self.assertEqual({(e["kind"], e["key"]) for e in m2["edges"] if e["path"] == "docs/extra.md"},
                         {("symbol", "DiskThing")})

    def test_test_names_are_not_dependencies(self):
        # テストの名を書いた文書・設定はテストに依らない（テストから先へ伸ばさない）
        self.write("conf/list.yaml", "suite: tests/test_core.py\n")
        self.write("tests/test_conf.py", "open('conf/list.yaml').read()\n")
        m = self.map(["pkg/core.py"])
        self.assertNotIn("conf/list.yaml", m["reach"])
        self.assertNotIn("tests/test_conf.py", m["tests"])


class CacheCase(RepoCase):
    def test_hit_then_incremental(self):
        m1 = self.map(["pkg/core.py"], cache_dir=self.cache)
        self.assertEqual(m1["stats"]["cache"], "miss")
        self.assertEqual(m1["stats"]["scanned"], m1["counts"]["files"])
        path = pathlib.Path(m1["path"])
        self.assertTrue(path.is_file())
        self.assertEqual(path.parent, self.cache)
        self.assertIn(m1["key"], path.name)
        m2 = self.map(["pkg/core.py"], cache_dir=self.cache)
        self.assertEqual(m2["stats"]["cache"], "hit")
        self.assertEqual(m2["key"], m1["key"])
        self.assertEqual({k: v for k, v in m2.items() if k != "stats"}, {k: v for k, v in m1.items() if k != "stats"})
        # 1 本だけ書き換える → 鍵が変わり、読み直すのはその 1 本だけ
        self.write("pkg/mid.py", "def use():\n    return 2\n")
        m3 = self.map(["pkg/core.py"], cache_dir=self.cache)
        self.assertNotEqual(m3["key"], m1["key"])
        self.assertEqual(m3["stats"]["cache"], "miss")
        self.assertEqual(m3["stats"]["scanned"], 1)
        self.assertEqual(m3["stats"]["reused"], m3["counts"]["files"] - 1)
        self.assertNotIn("pkg/mid.py", m3["reverse_imports"])
        self.assertNotIn("tests/test_mid.py", m3["tests"])
        # 新しい file（未追跡）も数に入り、読み直すのはそれだけ
        self.write("tests/test_new.py", "from pkg import core\n")
        m4 = self.map(["pkg/core.py"], cache_dir=self.cache)
        self.assertEqual(m4["stats"]["scanned"], 1)
        self.assertIn("tests/test_new.py", m4["tests"])

    def test_scan_cache_without_declared_reads_is_read_again(self):
        # 宣言を読む前の控え（py の読み取りに reads が無い）は、宣言を黙って落とさないよう file を読み直す
        import json

        self.write("tests/test_flow.py", 'RUNTIME_READS = ("flows/",)\n')
        self.write("flows/sub/b.yaml", "nodes: []\n")
        self.map(["flows/sub/b.yaml"], cache_dir=self.cache)
        scan = self.cache / "scan.json"
        recs = json.loads(scan.read_text(encoding="utf-8"))
        for rec in recs.values():
            rec.get("py", {}).pop("reads", None)
        scan.write_text(json.dumps(recs), encoding="utf-8")
        self.write("docs/extra.md", "# extra\n")   # 地図の鍵を変えて、控えの地図でなく file の読み取りの控えを引かせる
        m = self.map(["flows/sub/b.yaml"], cache_dir=self.cache)
        self.assertGreaterEqual(m["stats"]["scanned"], 1)
        self.assertIn("tests/test_flow.py", m["reach"], "読み直した宣言で、宣言した試験に届く")
        self.assertEqual(m["reach"]["tests/test_flow.py"]["parent"]["kind"], "reads")

    def test_diff_seeds(self):
        self.write("pkg/core.py", PROJ["pkg/core.py"].replace("return x + 1", "return x + 2"))
        m = self.map(diff=True)
        self.assertEqual(m["seeds"]["from_diff"], ["pkg/core.py"])
        self.assertEqual(m["seeds"]["files"], ["pkg/core.py"])

    def test_deleted_and_renamed_seeds_keep_their_importers(self):
        # 消した file も、import する側はまだ名を書いている（その側とテストを選ぶ）
        (self.repo / "pkg/core.py").unlink()
        m = self.map(diff=True)
        self.assertEqual(m["seeds"]["missing"], ["pkg/core.py"])
        self.assertIn("pkg/mid.py", m["reverse_imports"])
        self.assertIn("tests/test_core.py", m["tests"])
        git(self.repo, "checkout", "--", "pkg/core.py")
        git(self.repo, "mv", "pkg/core.py", "pkg/core2.py")
        m2 = self.map(diff=True)
        self.assertEqual(m2["seeds"]["from_diff"], ["pkg/core.py", "pkg/core2.py"])
        self.assertIn("pkg/mid.py", m2["reverse_imports"])

    def test_seeds_from_units(self):
        units = [{"key": "直す", "reason": "pkg/core.py の compute_total が 1 足りない。solo.py は無関係"},
                 {"key": "別", "reason": "無い file nothere.py", "prescriptions": ["pkg/mid.py を直す"]}]
        self.assertEqual(impact.seeds_from_units(self.repo, units), ["lonely/solo.py", "pkg/core.py", "pkg/mid.py"])
        # パスは区切りを見て拾う（長い名の一部の字は起点にしない）
        self.assertEqual(impact.seeds_from_units(self.repo, [{"reason": "mypkg/core.pyc と xpkg/mid.py_old"}]), [])

    def test_seeds_from_units_take_dot_and_absolute_paths(self):
        """頭の ./ と絶対パスの中の、根からのパスも起点にする（一意でない basename の __init__.py で見る）"""
        self.write("app/__init__.py", "")
        self.assertEqual(impact.seeds_from_units(self.repo, [{"reason": "./pkg/__init__.py と /home/u/proj/app/__init__.py"}]),
                         ["app/__init__.py", "pkg/__init__.py"])


if __name__ == "__main__":
    unittest.main()
