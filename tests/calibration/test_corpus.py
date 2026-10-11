"""較正の束（corpus.json）と読み手（corpus.py）の試験。束の形・仕込みが本当に壊すか・リポジトリを汚さないかを縛る。

走るのは小さな種の試験と証人の子のプロセスだけ。Archon・claude・網・変異の道具を使わない。
"""
import copy
import json
import pathlib
import re
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

KINDS = {"boundary", "error-path-succeeds", "test-blesses-bug", "comment-lies", "dead-code", "hidden-scope",
         "swallowed-error", "stand-in-diverges", "main-path-broken", "none"}
WITNESSLESS = {"comment-lies", "dead-code", "none"}
ROW_FIELDS = {"id": str, "kind": str, "entry": str, "visible": str, "edits": list, "red": list, "request": list,
              "outcome": str, "why": str}


def _raw():
    return json.loads((HERE / "corpus.json").read_text(encoding="utf-8"))


def _seed_copy(dest):
    shutil.copytree(SEED, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return dest


def _corpus_dir(parent, data):
    """data を corpus.json に書き、種の写しを横に置いた一時の束のフォルダを作って corpus.json のパスを返す"""
    folder = pathlib.Path(parent) / "corpus"
    _seed_copy(folder / data["seed"])
    path = folder / "corpus.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _files(tree):
    tree = pathlib.Path(tree)
    return {p.relative_to(tree).as_posix(): p.read_bytes() for p in sorted(tree.rglob("*")) if p.is_file()}


def _acceptance_ids():
    text = (ROOT / "docs" / "design.md").read_text(encoding="utf-8")
    section = text[text.index("### 受け入れの一覧"):]
    end = section.find("\n## ")
    return set(re.findall(r"`([^`]+)`", section if end < 0 else section[:end]))


class TestCorpusShape(unittest.TestCase):
    def setUp(self):
        self.data = corpus.load()

    def test_corpus_rows_are_well_formed(self):
        data = self.data
        self.assertEqual(data["seed"], "seed")
        self.assertEqual(data["run_inputs"], {"unattended": "true"})
        self.assertIsInstance(data["about"], str)
        for gone in data["dropped"]:
            self.assertEqual(set(gone), {"id", "why"})
        ids = [row["id"] for row in data["rows"]]
        self.assertEqual(len(ids), len(set(ids)))
        for row in data["rows"]:
            with self.subTest(row=row["id"]):
                for field, kind in ROW_FIELDS.items():
                    self.assertIsInstance(row[field], kind, field)
                self.assertIn(row["kind"], KINDS)
                self.assertIn(row["entry"], {"change", "request"})
                self.assertIn(row["visible"], {"tests", "review"})
                self.assertTrue(row["edits"])
                for edit in row["edits"]:
                    self.assertEqual(set(edit), {"file", "old", "new"})
                    self.assertNotEqual(edit["old"], edit["new"])
                self.assertEqual(bool(row["red"]), row["visible"] == "tests")
                self.assertTrue(row["request"])
                for line in row["request"]:
                    self.assertEqual(set(line), {"where", "text"})
                control = row["kind"] == "none"
                self.assertEqual(row["catcher"] is None, control)
                if not control:
                    self.assertIsInstance(row["catcher"], str)
                self.assertTrue(all(isinstance(x, str) for x in row.get("also", [])))
                if row["visible"] == "review" and row["kind"] not in WITNESSLESS:
                    self.assertIsInstance(row["witness"], str)
                else:
                    self.assertIsNone(row["witness"])
                self.assertTrue(row["why"].strip())

    def test_load_reports_every_problem(self):
        broken = copy.deepcopy(_raw())
        del broken["rows"][0]["why"]
        del broken["rows"][1]["outcome"]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(corpus.CorpusError) as caught:
                corpus.load(_corpus_dir(tmp, broken))
        message = str(caught.exception)
        self.assertIn(broken["rows"][0]["id"], message)
        self.assertIn("why", message)
        self.assertIn(broken["rows"][1]["id"], message)
        self.assertIn("outcome", message)

    def test_catchers_are_rows_of_the_acceptance_list(self):
        known = _acceptance_ids()
        for row in self.data["rows"]:
            for aim in [row["catcher"], *row.get("also", [])]:
                if aim is not None:
                    self.assertIn(aim, known, row["id"])

    def test_review_materials_need_change_entry(self):
        for row in self.data["rows"]:
            aims = [row["catcher"] or "", *row.get("also", [])]
            if any(aim.startswith("p1.") for aim in aims):
                self.assertEqual(row["entry"], "change", row["id"])

    def test_outcomes_are_report_words(self):
        if str(ROOT / "lib") not in sys.path:
            sys.path.append(str(ROOT / "lib"))
        from report import OUTCOMES
        for row in self.data["rows"]:
            self.assertIn(row["outcome"], OUTCOMES, row["id"])

    def test_corpus_spans_entries_and_views(self):
        rows = self.data["rows"]
        self.assertEqual({row["entry"] for row in rows}, {"change", "request"})
        self.assertEqual({row["visible"] for row in rows}, {"tests", "review"})
        self.assertGreaterEqual(sum(row["kind"] == "none" for row in rows), 1)
        self.assertGreaterEqual(len({row["catcher"] for row in rows if row["catcher"]}), 6)


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
        for old in ("この字は種に無い", "    if not xs:\n"):
            count = stats.count(old)
            with self.subTest(count=count), tempfile.TemporaryDirectory() as tmp:
                data = copy.deepcopy(_raw())
                data["rows"][0]["edits"] = [{"file": "stats.py", "old": old, "new": "pass\n"}]
                path = _corpus_dir(tmp, data)
                dest = pathlib.Path(tmp) / "out"
                dest.mkdir()
                with self.assertRaises(corpus.NotInjected) as caught:
                    corpus.materialize(data["rows"][0]["id"], dest, corpus=path)
                self.assertIn("stats.py", str(caught.exception))
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
