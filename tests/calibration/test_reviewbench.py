"""ReviewBench の口 tests/calibration/reviewbench.py の試験。網・本物の工場・判定役を使わない。

fixtures/ は運び役の機械の #214 の試み（works-factory の main5-a と今の works の works の mean-divides-by-n-minus-one--1）の
evidence/ から小さく切った写しで、head-tree.json はその対象の head の 3 つのファイル。judgment.json の 2 つ目の単位と局所レビューの
3 つ目の所見は、捨てられる側として番地を head に無い行に替えた。
"""
import json
import pathlib
import shutil
import unittest

import yaml

from tests.bin import hermetic
from tests.bin.gitkit import git
from tests.calibration import reviewbench
from tests.calibration import run as runner
from tests.archon import WORKFLOWS

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
                         (runner.WorksFactory.sources[0].file, reviewbench.NOT_AT_HEAD, 1))
        self.assertIn("stats.py:999-999", gone["refs"])
        self.assertEqual((record["final_diff"], record["leak_guard"]["web"]), (runner.SEALED, "denied"))
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
        (attempt / "evidence" / runner.SEALED).unlink()
        (attempt / "evidence" / runner.R1).write_text("{", encoding="utf-8")
        _, record = self.convert(runner.WorksFactory, attempt, head)
        self.assertEqual({f["in_final_diff"] for f in record["findings"]}, {None})
        self.assertIsNone(record["final_diff"])
        self.assertIn("sealed.diff", record["final_diff_why"])
        self.assertEqual(record["unread"], {runner.R1: "読めない（JSONDecodeError）"})

    def test_all_sources_missing_stops(self):
        """読み元が全部無い run は 0 件で採点を続けず止まる（置き場の道が記録と合わない合図。docs/design/integration.md の 4.3-15）。
        1 つでも在れば、無い物を unread に名指して続ける"""
        attempt, head = attempt_from(hermetic.tmpdir(self), "works-factory")
        for source in runner.WorksFactory.sources:
            (attempt / "evidence" / source.file).unlink()
        with self.assertRaises(reviewbench.BenchError) as caught:
            self.convert(runner.WorksFactory, attempt, head)
        self.assertIn(runner.JUDGMENT, str(caught.exception))
        attempt, head = attempt_from(hermetic.tmpdir(self), "works-factory")
        (attempt / "evidence" / runner.R4).unlink()
        _, record = self.convert(runner.WorksFactory, attempt, head)
        self.assertEqual(record["unread"], {runner.R4: reviewbench.MISSING})

    def test_rejudge_replaces_first_judgment(self):
        """再審が走った run は rejudge-run/judgment.json の units が工場の最後の判定"""
        attempt, head = attempt_from(hermetic.tmpdir(self), "works-factory")
        first, rejudge = runner.WorksFactory.sources[0].file, runner.WorksFactory.sources[0].prefer
        rejudged = attempt / "evidence" / rejudge
        rejudged.parent.mkdir()
        rejudged.write_text(json.dumps({"units": [{"key": "stats.py:3 の分母", "label": "block", "reason": "置き換えた単位"}]}),
                            encoding="utf-8")
        _, record = self.convert(runner.WorksFactory, attempt, head)
        units = [f for f in record["findings"] if f["source"].endswith("judgment.json")]
        self.assertEqual([(f["source"], f["file"], f["start_line"]) for f in units],
                         [(rejudge, "stats.py", 3)])
        self.assertEqual(record["dropped"], [])
        self.assertIn(rejudge, record["sources"])
        self.assertNotIn(first, record["sources"])

    def test_unit_without_any_reference_is_dropped_as_such(self):
        attempt, head = attempt_from(hermetic.tmpdir(self), "works-factory")
        judgment = runner.WorksFactory.sources[0].file
        (attempt / "evidence" / judgment).write_text(
            json.dumps({"units": [{"key": "どこでもない", "label": "nit", "reason": "番地を持たない"}]}), encoding="utf-8")
        _, record = self.convert(runner.WorksFactory, attempt, head)
        self.assertIn({"source": judgment, "refs": [], "why": reviewbench.NO_REF}, record["dropped"])

    def bare_name_attempt(self, files: dict, units: list, surfaced: list) -> tuple[pathlib.Path, str]:
        """工場の所見の番地がファイル名だけの試み。head に files を足し、判定の単位と目の所見を替える"""
        attempt, _ = attempt_from(hermetic.tmpdir(self), "works-factory")
        head = commit(attempt / "target", files, "nested")
        ev = attempt / "evidence"
        (ev / runner.WorksFactory.sources[0].file).write_text(json.dumps({"units": units}), encoding="utf-8")
        (ev / runner.R4).write_text(json.dumps({"surfaced": surfaced}), encoding="utf-8")
        return attempt, head

    def test_bare_file_names_resolve_to_repo_paths(self):
        lines = "x\n" * 420
        attempt, head = self.bare_name_attempt(
            {"app/static/dashboard.js": lines, "pkg/chat/interface.py": lines, ".devcontainer/devcontainer.json": lines},
            [{"key": "app/static/dashboard.js 版の上げ", "label": "suggest", "reason": "dashboard.js:392-399 で版を手で上げる"},
             {"key": "devcontainer.json workspaceFolder", "label": "suggest", "reason": "devcontainer.json:9 が名を固定する"}],
            [{"where": "pkg/chat/interface.py", "text": "interface.py:77-94 で audio_response が未定義になる"}])
        doc, record = self.convert(runner.WorksFactory, attempt, head)
        got = [(f["file"], f["start_line"], f["end_line"], f["ref_as_written"]) for f in record["findings"]]
        self.assertEqual(got, [("app/static/dashboard.js", 392, 399, "dashboard.js:392-399"),
                               (".devcontainer/devcontainer.json", 9, 9, "devcontainer.json:9-9"),
                               ("pkg/chat/interface.py", 77, 94, "interface.py:77-94")])
        self.assertEqual(record["resolved_count"], 3)
        self.assertEqual([f["file"] for f in doc["findings"]], [f[0] for f in got])
        self.assertTrue(all("ref_as_written" not in f for f in doc["findings"]))

    def test_same_name_twice_is_dropped_unless_the_key_names_one(self):
        lines = "x\n" * 20
        attempt, head = self.bare_name_attempt(
            {"a/util.py": lines, "b/util.py": lines},
            [{"key": "util の割り算", "label": "block", "reason": "util.py:3 が 0 で割る"},
             {"key": "b/util.py の割り算", "label": "block", "reason": "util.py:4 が 0 で割る"}], [])
        _, record = self.convert(runner.WorksFactory, attempt, head)
        judgment = runner.WorksFactory.sources[0].file
        self.assertIn({"source": judgment, "refs": ["util.py:3-3"], "why": reviewbench.AMBIGUOUS}, record["dropped"])
        self.assertNotEqual(reviewbench.AMBIGUOUS, reviewbench.NOT_AT_HEAD)
        [kept] = [f for f in record["findings"] if f["source"] == judgment]
        self.assertEqual((kept["file"], kept["start_line"], kept["ref_as_written"]), ("b/util.py", 4, "util.py:4-4"))

    def test_path_at_head_with_lines_out_of_range_is_not_moved(self):
        attempt, head = self.bare_name_attempt(
            {"setup.py": "x\n" * 30, "pkg/setup.py": "x\n" * 200},
            [{"key": "setup の版", "label": "block", "reason": "setup.py:150 が版を固定する"}], [])
        _, record = self.convert(runner.WorksFactory, attempt, head)
        judgment = runner.WorksFactory.sources[0].file
        self.assertIn({"source": judgment, "refs": ["setup.py:150-150"], "why": reviewbench.NOT_AT_HEAD}, record["dropped"])
        self.assertEqual([f for f in record["findings"] if f["source"] == judgment], [])
        self.assertEqual(record["resolved_count"], 0)

    def test_key_path_not_at_head_falls_back_to_the_head_files(self):
        attempt, head = self.bare_name_attempt(
            {"app/static/dashboard.js": "x\n" * 5},
            [{"key": "old/dashboard.js 版", "label": "suggest", "reason": "dashboard.js:3 で版を手で上げる"}], [])
        _, record = self.convert(runner.WorksFactory, attempt, head)
        judgment = runner.WorksFactory.sources[0].file
        self.assertEqual([(f["file"], f["start_line"], f["ref_as_written"]) for f in record["findings"] if f["source"] == judgment],
                         [("app/static/dashboard.js", 3, "dashboard.js:3-3")])

    def test_structured_locations_are_not_resolved(self):
        """素の Claude Code は file・start_line を構造で持つので、パスを推して解かない"""
        tmp = hermetic.tmpdir(self)
        attempt, head = attempt_from(tmp, "works-factory")
        head = commit(attempt / "target", {"app/only.py": "x\n" * 5}, "nested")
        shutil.rmtree(attempt / "evidence")
        (attempt / "evidence").mkdir()
        (attempt / "evidence" / "findings.json").write_text(json.dumps({"findings": [
            {"file": "only.py", "start_line": 2, "end_line": 2, "message": "m"},
            {"file": "app/only.py", "start_line": 3, "end_line": 3, "message": "n"}]}), encoding="utf-8")
        _, record = self.convert(runner.PlainClaude, attempt, head)
        self.assertEqual([(f["file"], f["ref_as_written"]) for f in record["findings"]], [("app/only.py", None)])
        self.assertEqual([d["why"] for d in record["dropped"]], [reviewbench.NOT_AT_HEAD])
        self.assertEqual(record["resolved_count"], 0)

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
        self.assertEqual(reviewbench.refs("関数はsrc/x.py:12で落ちる。②test_stats.py:40 が"),
                         [("src/x.py", 12, 12), ("test_stats.py", 40, 40)])
        diff = "--- a/x.py\n+++ b/x.py\n@@ -3,2 +3,4 @@\n--- /dev/null\n+++ b/new.py\n@@ -0,0 +1,2 @@\n--- a/y.py\n@@ -5,0 +6 @@\n"
        self.assertEqual(reviewbench.final_ranges(diff), {"x.py": [(3, 4)], "y.py": [(5, 5)]})


class SourceShapeCase(unittest.TestCase):
    """ランナーが読む works-factory の出力の欄は、それを書く持ち主の block（diagnose・r1・r4。pack の WORKFLOWS の下）のどれかの
    node の output_format に在る。名が変わるとファイルは在るので unread は空のまま、指摘が黙って減る"""
    # 読み元 → 書く block（読み元の place の include の道の最後の段）と、行に要る欄
    OWNERS = {runner.JUDGMENT: ("diagnose", {"key", "label", "reason"}), runner.R1: ("r1", {"where", "why"}),
              runner.R4: ("r4", {"where", "text", "mechanism"})}

    def test_sources_follow_their_owners(self):
        for source in runner.WorksFactory.sources:
            with self.subTest(source=source.file):
                block, want = self.OWNERS[source.file]
                graph = yaml.safe_load((WORKFLOWS / block / f"works-factory-{block}.yaml").read_text(encoding="utf-8"))
                found = []
                for node in [*graph["nodes"], *(b for n in graph["nodes"] for b in (n.get("loop_group") or {}).get("nodes", []))]:
                    shape = node.get("output_format") or {}
                    for step in source.rows:
                        shape = ((shape.get("properties") or {}).get(step) or {}).get("items") or {}
                    found.append(set(shape.get("properties") or {}))
                self.assertTrue(any(want <= names for names in found), f"{block} のどの node の output_format にも {sorted(want)} の行が無い")


if __name__ == "__main__":
    unittest.main()
