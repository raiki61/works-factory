"""較正の束（corpus.json）と読み手（corpus.py）の試験。束の形・仕込みが本当に壊すか・リポジトリを汚さないかを縛る。

走るのは小さな種の試験と証人の子のプロセスだけ。Archon・claude・網・変異の道具を使わない。
"""
import copy
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.bin.gitkit import git
from tests.calibration import corpus

ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
SEED = HERE / "seed"
CLI = HERE / "corpus.py"


def _raw():
    return json.loads((HERE / "corpus.json").read_text(encoding="utf-8"))


def _seed_copy(dest):
    shutil.copytree(SEED, dest, ignore=corpus.COPY_IGNORE)
    return dest


def _corpus_dir(parent, data):
    """data を corpus.json に書き、種の写しを横に置いた一時の束のフォルダを作って corpus.json のパスを返す"""
    folder = pathlib.Path(parent) / "corpus"
    _seed_copy(folder / _raw()["seed"])
    path = folder / "corpus.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _files(tree):
    tree = pathlib.Path(tree)
    return {p.relative_to(tree).as_posix(): p.read_bytes() for p in sorted(tree.rglob("*")) if p.is_file()}


class TestCorpusShape(unittest.TestCase):
    """同梱の束が通ることと、崩した束を load が CorpusError で断り、崩れを全部挙げることを縛る"""

    def refusal(self, *breaks):
        data = copy.deepcopy(_raw())
        rows = data["rows"]
        for brk in breaks:
            brk(data, rows)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(corpus.CorpusError) as caught:
                corpus.load(_corpus_dir(tmp, data))
        return str(caught.exception).splitlines()

    def assertReported(self, lines, *parts):
        self.assertTrue(any(all(part in line for part in parts) for line in lines), (parts, lines))

    def test_corpus_rows_are_well_formed(self):
        rows = corpus.load()["rows"]
        lines = self.refusal(
            lambda d, r: r[0].update(kind="unknown"),
            lambda d, r: r[1].update(entry="elsewhere"),
            lambda d, r: r[4].update(visible="nowhere"),
            lambda d, r: r[5]["edits"][0].update(new=r[5]["edits"][0]["old"]),
            lambda d, r: r[3].update(witness=None),
            lambda d, r: r[6].update(red=["test_stats.TestMean.test_mean"]),
            lambda d, r: r[10].update(catcher="p0.local_checks"),
            lambda d, r: r[8].update(why="  "),
            lambda d, r: r[7].update(id=r[9]["id"]),
            lambda d, r: d.update(dropped=[{"id": "gone"}]),
        )
        self.assertReported(lines, rows[0]["id"], "kind unknown")
        self.assertReported(lines, rows[1]["id"], "entry elsewhere")
        self.assertReported(lines, rows[4]["id"], "visible nowhere")
        self.assertReported(lines, rows[5]["id"], "edits[0]", "old と new")
        self.assertReported(lines, rows[3]["id"], "witness")
        self.assertReported(lines, rows[6]["id"], "red")
        self.assertReported(lines, rows[10]["id"], "catcher")
        self.assertReported(lines, rows[8]["id"], "why")
        self.assertReported(lines, f"id {rows[9]['id']} が 2 つ以上")
        self.assertReported(lines, "dropped[0]")

    def test_load_refuses_wrong_types_without_crashing(self):
        rows = _raw()["rows"]
        for field, value in (("rows", 5), ("dropped", None), ("seed", 5), ("run_inputs", [])):
            with self.subTest(field=field):
                self.assertReported(self.refusal(lambda d, r: d.update({field: value})), f"頭の欄 {field}")
        self.assertReported(self.refusal(lambda d, r: d.pop("about")), "頭の欄 about が無い")
        lines = self.refusal(lambda d, r: r[0]["request"][0].update(where=5),
                             lambda d, r: r[1].update(id=["unhashable"]),
                             lambda d, r: r[2].update(id=["unhashable"]),
                             lambda d, r: r[2].update(entry=["unhashable"]))
        self.assertReported(lines, rows[0]["id"], "request[0]")
        self.assertReported(lines, "rows[1]", "id")
        self.assertReported(lines, "rows[2]", "entry")

    def test_load_reports_every_problem(self):
        rows = _raw()["rows"]
        lines = self.refusal(lambda d, r: r[0].pop("why"), lambda d, r: r[1].pop("outcome"))
        self.assertReported(lines, rows[0]["id"], "why")
        self.assertReported(lines, rows[1]["id"], "outcome")

    def test_catchers_are_rows_of_the_acceptance_list(self):
        lines = self.refusal(lambda d, r: r[0].update(catcher="p9.nowhere"),
                             lambda d, r: r[2].update(also=["p9.elsewhere"]))
        self.assertReported(lines, _raw()["rows"][0]["id"], "p9.nowhere")
        self.assertReported(lines, _raw()["rows"][2]["id"], "p9.elsewhere")
        control = _raw()["rows"][10]
        self.assertEqual(control["kind"], "none")
        lines = self.refusal(lambda d, r: r[10].update(also=["p1.gate_efficacy"]))
        self.assertReported(lines, control["id"], "also")

    def test_review_materials_need_change_entry(self):
        row = _raw()["rows"][3]
        self.assertTrue(row["catcher"].startswith("p1."))
        lines = self.refusal(lambda d, r: r[3].update(entry="request"))
        self.assertReported(lines, row["id"], "p1.")

    def test_outcomes_are_report_words(self):
        lines = self.refusal(lambda d, r: r[0].update(outcome="made_up"))
        self.assertReported(lines, _raw()["rows"][0]["id"], "outcome made_up")
        self.assertLessEqual(set(corpus.UNREACHED), set(corpus.OUTCOMES))

    def test_corpus_spans_entries_and_views(self):
        def only(field, word):
            return lambda d, r: [row.update({field: word}) for row in r]

        def five_aims(d, r):
            for row in r[6:10]:
                row["catcher"] = "p1.gate_efficacy"

        for name, brk, part in (("entry", only("entry", "change"), "entry が ['request']"),
                                ("visible", only("visible", "review"), "visible が ['tests']"),
                                ("control", lambda d, r: r.pop(), "対照"),
                                ("aims", five_aims, "狙いの id が 5 種")):
            with self.subTest(name):
                self.assertReported(self.refusal(brk), part)


class TestInjection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = corpus.load()["rows"]
        cls.made = {}
        cls.tmp = tempfile.TemporaryDirectory()
        cls.seed_tree = _seed_copy(pathlib.Path(cls.tmp.name) / "seed")
        cls.seed = corpus.seed_results(cls.seed_tree)
        for row in cls.rows:
            dest = pathlib.Path(cls.tmp.name) / row["id"]
            dest.mkdir()
            cls.made[row["id"]] = corpus.materialize(row["id"], dest)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_seed_is_green(self):
        self.assertEqual(self.seed["failures"], [])
        self.assertEqual(self.seed["errors"], [])
        self.assertGreaterEqual(self.seed["ran"], 1)

    def test_seed_results_counts_only_assertions_as_failures(self):
        tree = pathlib.Path(self.tmp.name) / "mixed"
        tree.mkdir()
        (tree / "test_x.py").write_text(
            "import unittest\n\n\nclass T(unittest.TestCase):\n"
            "    def test_asserts(self):\n        self.assertEqual(1, 2)\n\n"
            "    def test_raises(self):\n        raise ValueError('x')\n", encoding="utf-8")
        (tree / "test_broken.py").write_text("import no_such_module\n", encoding="utf-8")
        got = corpus.seed_results(tree)
        self.assertEqual(got["failures"], ["test_x.T.test_asserts"])
        self.assertEqual(len(got["errors"]), 2, got["errors"])
        self.assertIn("test_x.T.test_raises", got["errors"])
        self.assertTrue(any("test_broken" in e for e in got["errors"]), got["errors"])

    def test_every_anchor_is_unique_when_applied(self):
        self.assertEqual(set(self.made), {row["id"] for row in self.rows})
        for made in self.made.values():
            for key in ("base", "head", "request"):
                self.assertTrue(pathlib.Path(made[key]).is_absolute())
                self.assertTrue(pathlib.Path(made[key]).exists())

    def test_tests_rows_fail_exactly_the_named_tests(self):
        for row in self.rows:
            if row["visible"] != "tests":
                continue
            with self.subTest(row=row["id"]):
                got = corpus.seed_results(self.made[row["id"]]["head"])
                self.assertEqual(set(got["failures"]), set(row["red"]))
                self.assertEqual(got["errors"], [])

    def test_review_rows_keep_seed_tests_green(self):
        for row in self.rows:
            if row["visible"] != "review":
                continue
            with self.subTest(row=row["id"]):
                got = corpus.seed_results(self.made[row["id"]]["head"])
                self.assertEqual(got["failures"], [])
                self.assertEqual(got["errors"], [])
                self.assertGreaterEqual(got["ran"], self.seed["ran"])

    def test_witness_passes_on_seed_and_asserts_on_defect(self):
        for row in self.rows:
            if row.get("witness") is None:
                continue
            with self.subTest(row=row["id"]):
                self.assertEqual(corpus.witness_result(self.seed_tree, row["witness"]), "pass")
                self.assertEqual(corpus.witness_result(self.made[row["id"]]["head"], row["witness"]), "assert")
        for source, want in (("raise ValueError('x')", "error"), ("import no_such_module", "error"),
                             ("assert False", "assert")):
            with self.subTest(source=source):
                self.assertEqual(corpus.witness_result(self.seed_tree, source), want)


class TestMaterialize(unittest.TestCase):
    def setUp(self):
        self.rows = corpus.load()["rows"]

    def test_materialize_leaves_repository_untouched(self):
        status = ["status", "--porcelain", "--untracked-files=normal"]
        before = git(ROOT, *status)
        with tempfile.TemporaryDirectory() as tmp:
            for row in self.rows:
                dest = pathlib.Path(tmp) / row["id"]
                dest.mkdir()
                made = corpus.materialize(row["id"], dest)
                with self.subTest(row=row["id"]):
                    differ = _files(made["base"]) != _files(made["head"])
                    self.assertEqual(differ, row["entry"] == "change")
                    self.assertEqual(json.loads(pathlib.Path(made["request"]).read_text(encoding="utf-8")),
                                     row["request"])
        self.assertEqual(git(ROOT, *status), before)
        self.assertEqual(list(SEED.rglob("__pycache__")), [])

    def test_materialize_refuses_nonempty_dest(self):
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / "left.txt").write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                corpus.materialize(self.rows[0]["id"], tmp)
            self.assertEqual(sorted(p.name for p in pathlib.Path(tmp).iterdir()), ["left.txt"])

    def test_materialize_reports_stale_anchor(self):
        stats = (SEED / "stats.py").read_text(encoding="utf-8")
        for name, old, count in (("stats.py", "この字は種に無い", 0), ("stats.py", "    if not xs:\n", None),
                                 ("renamed.py", "def mean", 0)):
            count = stats.count(old) if count is None else count
            with self.subTest(file=name, count=count), tempfile.TemporaryDirectory() as tmp:
                data = copy.deepcopy(_raw())
                data["rows"][0]["edits"] = [{"file": name, "old": old, "new": "pass\n"}]
                path = _corpus_dir(tmp, data)
                dest = pathlib.Path(tmp) / "out"
                dest.mkdir()
                with self.assertRaises(corpus.NotInjected) as caught:
                    corpus.materialize(data["rows"][0]["id"], dest, corpus=path)
                self.assertIn(name, str(caught.exception))
                self.assertIn(str(count), str(caught.exception))
                self.assertEqual(list(dest.iterdir()), [])

    def test_cli_list_and_materialize(self):
        def run(*args):
            return subprocess.run([sys.executable, str(CLI), *args], capture_output=True, text=True, encoding="utf-8",
                                  cwd=ROOT)

        listed = run("list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        lines = [json.loads(line) for line in listed.stdout.splitlines()]
        self.assertEqual([line["id"] for line in lines], [row["id"] for row in self.rows])
        self.assertEqual(set(lines[0]), {"id", "entry", "catcher"})

        with tempfile.TemporaryDirectory() as tmp:
            made = run("materialize", self.rows[0]["id"], tmp)
            self.assertEqual(made.returncode, 0, made.stderr)
            [line] = made.stdout.splitlines()
            self.assertEqual(set(json.loads(line)), {"id", "entry", "base", "head", "request"})

        with tempfile.TemporaryDirectory() as tmp:
            data = copy.deepcopy(_raw())
            data["rows"][0]["edits"] = [{"file": "stats.py", "old": "この字は種に無い", "new": "x"}]
            path = _corpus_dir(tmp, data)
            dest = pathlib.Path(tmp) / "out"
            dest.mkdir()
            refused = run("materialize", data["rows"][0]["id"], str(dest), "--corpus", str(path))
            self.assertEqual(refused.returncode, 1)
            self.assertEqual(refused.stdout, "")
            self.assertEqual(len(refused.stderr.strip().splitlines()), 1)
            self.assertIn("stats.py", refused.stderr)


if __name__ == "__main__":
    unittest.main()
