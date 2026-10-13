"""ReviewBench の口 tests/calibration/reviewbench.py の試験。網・本物の工場・判定役を使わない。

fixtures/ は運び役の機械の #214 の試み（works-factory の main5-a と今の works の works の mean-divides-by-n-minus-one--1）の
evidence/ から小さく切った写しで、head-tree.json はその対象の head の 3 つのファイル。judgment.json の 2 つ目の単位と局所レビューの
3 つ目の所見は、捨てられる側として番地を head に無い行に替えた。
"""
import json
import pathlib
import shutil
import unittest

from tests.bin import hermetic
from tests.bin.gitkit import git
from tests.calibration import reviewbench
from tests.calibration import run as runner

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
TASK = json.loads((FIXTURES / "reviewbench" / "task.json").read_text(encoding="utf-8"))
ENDED = {"outcome": "needs_human", "seconds": 900.0, "usd": 6.05, "usd_from": "記録", "children": [], "web_calls": 0}


def commit(repo: pathlib.Path, files: dict, message: str) -> str:
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def attempt_from(tmp: pathlib.Path, producer: str) -> tuple[pathlib.Path, str]:
    """fixture の evidence/ と、head-tree.json を 1 つの commit にした target を持つ試み。(試み, head) を返す"""
    attempt = tmp / f"{producer}--1"
    shutil.copytree(FIXTURES / producer / "evidence", attempt / "evidence")
    (attempt / "target").mkdir()
    git(attempt / "target", "init", "-q", "-b", "main")
    head = commit(attempt / "target", json.loads((FIXTURES / "head-tree.json").read_text(encoding="utf-8")), "head")
    return attempt, head


class RequestCase(unittest.TestCase):
    def test_request_text_and_base_from_task(self):
        rows = reviewbench.request_rows(TASK, ["tests/test_chat.py"])
        body = TASK["body"].replace("\r\n", "\n").strip()
        self.assertEqual(rows, [{"where": "tests/test_chat.py", "text": f"{TASK['title']}\n\n{body}"}])
        self.assertNotIn("\r", rows[0]["text"])
        self.assertEqual(reviewbench.key(TASK), "AA-Factory_aafactory-prototype_17-a1978cb7")
        self.assertEqual(reviewbench.request_rows({**TASK, "body": None}, ["b.py", "a.py"]),
                         [{"where": "a.py b.py", "text": TASK["title"]}])

    def test_tasks_pick_the_language_in_manifest_order(self):
        tmp = hermetic.tmpdir(self)
        (tmp / "corpus").mkdir()
        rows = [{**TASK, "pr_number": 1}, {**TASK, "pr_number": 2, "language": "Go"}, {**TASK, "pr_number": 3}]
        (tmp / "corpus" / "manifest.json").write_text(json.dumps(rows), encoding="utf-8")
        self.assertEqual([t["pr_number"] for t in reviewbench.tasks(tmp)], [1, 3])
        with self.assertRaises(reviewbench.BenchError):
            reviewbench.tasks(tmp / "nowhere")


class PrepareCase(unittest.TestCase):
    def test_prepare_checks_out_head_with_base_reachable(self):
        tmp = hermetic.tmpdir(self)
        source = tmp / "source"
        source.mkdir()
        git(source, "init", "-q", "-b", "main")
        base = commit(source, {"app.py": "x = 1\n"}, "base")
        head = commit(source, {"app.py": "x = 2\n", "tests/test_app.py": "y = 1\n"}, "head")
        mirror = tmp / "mirror" / "owner_repo.git"
        git(tmp, "clone", "-q", "--bare", str(source), str(mirror))
        entry = {**TASK, "nwo": "owner/repo", "base": base, "head": head, "pr_number": "7"}
        got = reviewbench.prepare(entry, tmp / "attempt", tmp / "repos", f"file://{tmp / 'mirror'}/{{name}}.git")
        self.assertEqual(got, {"base": base, "head": head})
        target, attempt = tmp / "attempt" / "target", tmp / "attempt"
        self.assertEqual(git(target, "rev-parse", "HEAD"), head)
        self.assertEqual(git(target, "status", "--porcelain"), "")
        git(target, "merge-base", "--is-ancestor", base, "HEAD")
        self.assertEqual(git(attempt / "origin", "rev-parse", "main"), head)
        self.assertEqual(git(attempt / "origin", "rev-parse", "refs/bench/base"), base)
        pr = json.loads((attempt / "pr" / "pr.json").read_text(encoding="utf-8"))
        self.assertEqual(set(pr), {"repo", "pr_number", "base", "head", "nwo", "title", "body"})
        self.assertEqual(pr["pr_number"], 7)
        self.assertEqual((attempt / "pr" / "diff.patch").read_text(encoding="utf-8").strip(),
                         git(target, "diff", f"{base}...{head}"))
        [row] = json.loads((attempt / "request.json").read_text(encoding="utf-8"))
        self.assertEqual(row["where"], "app.py tests/test_app.py")
        self.assertTrue((attempt / "home").is_dir())


class ConvertCase(unittest.TestCase):
    def convert(self, producer, attempt, head, ended=ENDED):
        return reviewbench.convert(producer, TASK, attempt, "run-1", TASK["base"], head, ended)

    def test_works_factory_findings_and_dropped(self):
        attempt, head = attempt_from(hermetic.tmpdir(self), "works-factory")
        doc, record = self.convert(runner.WorksFactory, attempt, head)
        self.assertEqual(len(doc["findings"]), 2)
        for f in doc["findings"]:
            self.assertEqual(set(f), {"file", "start_line", "end_line", "message", "producer"})
            self.assertEqual(f["producer"], "works-factory")
        unit, surfaced = record["findings"]
        self.assertEqual((unit["file"], unit["start_line"], unit["end_line"]), ("stats.py", 9, 9))
        self.assertEqual(unit["node"], "judge__diagnose-loop.diagnose")
        self.assertTrue(unit["message"].startswith("[block] stats.py mean"))
        self.assertEqual((surfaced["file"], surfaced["start_line"], surfaced["end_line"]), ("stats.py", 5, 9))
        self.assertEqual(surfaced["node"], "eyes__r4-scope")
        self.assertEqual([f["in_final_diff"] for f in record["findings"]], [True, True])
        [gone] = record["dropped"]
        self.assertEqual((gone["source"], gone["why"], record["dropped_count"]),
                         ("parent/judge/judgment.json", reviewbench.NOT_AT_HEAD, 1))
        self.assertIn("stats.py:999-999", gone["refs"])
        self.assertEqual((record["final_diff"], record["leak_guard"]["web"]), ("parent/merge/sealed.diff", "denied"))
        self.assertEqual(record["unread"], {})
        self.assertEqual(doc["usage"], {"time_in_ms": 900000, "cost_usd": 6.05})
        self.assertEqual(doc["pr"], {"repo": TASK["repo"], "pr_number": 17, "base": TASK["base"], "head": head})

    def test_works_findings_and_dropped(self):
        attempt, head = attempt_from(hermetic.tmpdir(self), "works")
        doc, record = self.convert(runner.OldWorks, attempt, head)
        got = [(f["file"], f["start_line"], f["node"], f["in_final_diff"]) for f in record["findings"]]
        self.assertEqual(got, [("stats.py", 9, "judging__judge-loop.judge", True),
                               ("stats.py", 9, "gathering__local-review-loop.local-review", True),
                               ("README.md", 16, "gathering__local-review-loop.local-review", False)])
        [gone] = record["dropped"]
        self.assertEqual((gone["refs"], gone["why"]), (["stats.py:500-500"], reviewbench.NOT_AT_HEAD))
        self.assertEqual(record["final_diff"], "board/fix-delta-r1.patch")
        self.assertEqual(record["leak_guard"]["web"], "open")
        self.assertTrue(record["leak_guard"]["why"])

    def test_missing_final_diff_and_sources_are_named(self):
        attempt, head = attempt_from(hermetic.tmpdir(self), "works-factory")
        (attempt / "evidence" / "parent" / "merge" / "sealed.diff").unlink()
        (attempt / "evidence" / "parent" / "eyes" / "r1.json").write_text("{", encoding="utf-8")
        _, record = self.convert(runner.WorksFactory, attempt, head)
        self.assertEqual({f["in_final_diff"] for f in record["findings"]}, {None})
        self.assertIsNone(record["final_diff"])
        self.assertIn("sealed.diff", record["final_diff_why"])
        self.assertEqual(record["unread"], {"parent/eyes/r1.json": "読めない（JSONDecodeError）"})

    def test_unit_without_any_reference_is_dropped_as_such(self):
        attempt, head = attempt_from(hermetic.tmpdir(self), "works-factory")
        (attempt / "evidence" / "parent" / "judge" / "judgment.json").write_text(
            json.dumps({"units": [{"key": "どこでもない", "label": "nit", "reason": "番地を持たない"}]}), encoding="utf-8")
        _, record = self.convert(runner.WorksFactory, attempt, head)
        self.assertIn({"source": "parent/judge/judgment.json", "refs": [], "why": reviewbench.NO_REF}, record["dropped"])

    def test_write_keeps_record_out_of_the_judge_input(self):
        tmp = hermetic.tmpdir(self)
        attempt, head = attempt_from(tmp, "works-factory")
        doc, record = self.convert(runner.WorksFactory, attempt, head)
        found, kept = reviewbench.write(tmp / "out", "works-factory", reviewbench.key(TASK), doc, record)
        self.assertEqual(found, tmp / "out" / "works-factory" / "findings" / f"{reviewbench.key(TASK)}.json")
        self.assertEqual(list(json.loads(found.read_text(encoding="utf-8"))), ["pr", "agent", "findings", "usage"])
        self.assertEqual(kept.parent.name, "convert")
        self.assertEqual(list((tmp / "out" / "works-factory" / "findings").rglob("*")), [found])

    def test_references_and_final_ranges(self):
        self.assertEqual(reviewbench.refs("see ./a/b.py:3-5 and c.md:7, not x.py:z or http://h.io:80"),
                         [("a/b.py", 3, 5), ("c.md", 7, 7)])
        diff = "--- a/x.py\n+++ b/x.py\n@@ -3,2 +3,4 @@\n--- /dev/null\n+++ b/new.py\n@@ -0,0 +1,2 @@\n--- a/y.py\n@@ -5,0 +6 @@\n"
        self.assertEqual(reviewbench.final_ranges(diff), {"x.py": [(3, 4)], "y.py": [(5, 5)]})


if __name__ == "__main__":
    unittest.main()
