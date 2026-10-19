"""目的の固定の block を、script を子のプロセスで回して確かめる（docs/design/purpose.md の 7.2）。

始めの記録の無い使い捨ての run directory と git のリポジトリ（README.md・docs/plan.md・sub/x.py と git が無視するファイル）で、
port の値だけを渡し、intake → purpose_prep → 台本の返答 → purpose_accept → finish と回す。受け付けの決まりは src/steps の check を
この過程で呼んで確かめる。YAML と筋書きの揃いも見る。筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import os
import shutil
import time
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = kit.BLOCKS / "purpose"
FINDINGS = [{"where": "stats.py:4", "text": "mean は 2 でなく 3 を返す。分母を len(xs) にする"}]
REQUEST = json.dumps(FINDINGS, ensure_ascii=False)
PRIOR = json.dumps({"findings": FINDINGS, "pr": [], "issue": [],
                    "prior_failures": [{"where": "受け付け", "text": "前の run で拒まれた行の印XYZ"}]}, ensure_ascii=False)
CONSTRAINTS = json.dumps([{"text": "stats.py の mean は sum(xs) / 2", "measured_how": "sed で読んだ", "kind": "実測",
                           "measured_output": "$ sed -n 4p stats.py\nreturn sum(xs) / 2"},
                          {"text": "呼び手は 1 つ", "measured_how": "grep の見込み", "kind": "仮説"}], ensure_ascii=False)
GOOD = {"purpose_text": "平均の関数が正しい値を返す", "source": "②計画・タスク記述", "known_weaknesses": [],
        "source_files": ["docs/plan.md"], "means": ["分母を len(xs) にする"]}


class _RepoCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "purpose")
        repo = self.run.repo
        (repo / "docs").mkdir()
        (repo / "sub").mkdir()
        (repo / "README.md").write_text("# stats\n", encoding="utf-8")
        (repo / "docs" / "plan.md").write_text("平均を直す\n", encoding="utf-8")
        (repo / "sub" / "x.py").write_text("x = 1\n", encoding="utf-8")
        (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
        (repo / "sub" / "skip.log").write_text("x\n", encoding="utf-8")
        old = time.time() - 60   # git が無視するファイルの印を書いた時刻の近さ（lib/accept の RACY_NS）に左右させない
        os.utime(repo / "sub" / "skip.log", (old, old))
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "seed")
        self.steps = kit.load("purpose", "steps")

    def intake(self, **inputs):
        ports = {"request": REQUEST, "pr_text": "", "constraints": "[]", "lang": "", **inputs}
        return self.run.script("intake", **ports)

    def prep(self):
        return self.run.script("purpose_prep")

    def accept(self, reply):
        return self.run.script("purpose_accept", reply=json.dumps(reply, ensure_ascii=False))

    def read(self, name):
        return json.loads((self.run.artifacts / name).read_text(encoding="utf-8"))


class IntakeCase(_RepoCase):
    def test_request_copy_has_no_prior_failures(self):
        """目的の役に前の run の判断を見せない（持ち主の決め premises-purpose。carry.without_prior）。ほかの欄は字のまま"""
        self.assertEqual(self.intake(request=PRIOR), {"due": True, "reason": ""})
        doc = self.read("intake.json")
        self.assertEqual(doc["request"], {"findings": FINDINGS, "pr": [], "issue": []})
        self.assertEqual((doc["frozen"], doc["failed"], doc["reason"]), (False, False, ""))

    def test_tree_is_snapshot(self):
        self.intake()
        accept = self.steps.accept
        self.assertEqual(self.read("tree.json"), accept.tree_state(self.run.repo))

    def test_frozen_purpose_skips_the_role_and_keeps_files(self):
        (self.run.artifacts / "purpose.json").write_text(json.dumps(GOOD), encoding="utf-8")
        (self.run.artifacts / "tree.json").write_text("{}", encoding="utf-8")
        got = self.intake()
        self.assertEqual(got, {"due": False, "reason": "目的は既に固めてある（purpose.json）"})
        self.assertTrue((self.run.artifacts / "tree.json").is_file(), "固めた目的の時はほかのファイルも消さない")
        self.assertTrue(self.read("intake.json")["frozen"])

    def test_unreadable_port_does_not_stop_the_run(self):
        for raw in (self.run.pointer("absent.json"), '{"rows": 1}'):
            with self.subTest(raw):
                got = self.intake(request=raw)
                self.assertFalse(got["due"])
                self.assertIn("目的の役の支度が落ちた", got["reason"])
                self.assertIn("入力 request", got["reason"])
                self.assertTrue(self.read("intake.json")["failed"])

    def test_measured_row_needs_its_output(self):
        bad = json.dumps([{"text": "数は 3", "measured_how": "数えた", "kind": "実測"}], ensure_ascii=False)
        got = self.intake(constraints=bad)
        self.assertFalse(got["due"])
        self.assertIn("measured_output", got["reason"])

    def test_constraints_in_a_container(self):
        self.intake(constraints=json.dumps({"constraints": json.loads(CONSTRAINTS), "other": 1}, ensure_ascii=False))
        self.assertEqual(self.read("intake.json")["constraints"], json.loads(CONSTRAINTS))


class PromptCase(_RepoCase):
    def test_pr_text_and_constraints_reach_the_prompt(self):
        self.intake(pr_text="#7 題 T\n\n本文X", constraints=CONSTRAINTS)
        text = self.prep()["prompt"]
        self.assertIn("本文X", text)
        self.assertNotIn("(This run has no PR.)", text)
        self.assertIn('"measured_how": "sed で読んだ"', text)
        self.assertIn('"where": "stats.py:4"', text)
        self.assertTrue((self.run.artifacts / "purpose-prompt-1.md").is_file())

    def test_run_without_pr_says_so(self):
        self.intake()
        text = self.prep()["prompt"]
        self.assertIn("(This run has no PR.)", text)
        self.assertIn("```json\n[]\n```", text, "前提の実測が無ければ空の配列")
        self.assertIn("in the language of the request", text, "lang が空なら既定の言語の文")

    def test_role_does_not_see_the_prior_run(self):
        self.intake(request=PRIOR)
        text = self.prep()["prompt"]
        node = next(n for n in _nodes(_doc()) if n["id"] == "purpose")
        for word in ("prior_failures", "prior-failures", "judgment", "PRIOR", "印XYZ"):
            with self.subTest(word):
                self.assertNotIn(word, json.dumps(node, ensure_ascii=False))
                if word != "judgment":   # md の決まった文「The judgments of earlier runs are removed from it.」が持つ
                    self.assertNotIn(word, text)

    def test_query_rule_and_source_words_are_filled(self):
        self.intake(lang="Japanese")
        text = self.prep()["prompt"]
        self.assertTrue(text.startswith("Rules for queries to outside services:"), text[:80])
        self.assertNotIn("If you start a sub-agent", text)
        for word in self.steps.SOURCES:
            self.assertIn(f"`{word}`", text)
        self.assertIn('write "目的不明: " followed by', text)
        self.assertIn("in Japanese", text)
        self.assertNotRegex(text, r"\{[a-z0-9_]+\}", "埋まらない差し込み口が無い")
        self.assertIn('`{"findings": [...], "pr": [...], "issue": [...]}`', text)

    def test_rejected_reply_brings_the_reasons_to_the_next_prompt(self):
        self.intake()
        self.prep()
        got = self.accept({**GOOD, "source_files": ["nothing.md"]})
        self.assertEqual((got["ok"], got["done"]), (False, False))
        again = self.prep()["prompt"]
        self.assertTrue(again.startswith("## Why your previous answer was rejected"), again[:80])
        self.assertIn("nothing.md", again)
        self.assertTrue((self.run.artifacts / "purpose-prompt-2.md").is_file())

    def test_prep_without_intake_fails_the_node(self):
        self.assertIn("intake.json", self.run.failing("purpose_prep"))


class AcceptCase(_RepoCase):
    def check(self, reply, repo=None):
        repo = repo or self.run.repo
        place = self.run.artifacts
        with self.run.env():
            return self.steps.check(dict(reply), place, repo)

    def snap(self, repo=None):
        (self.run.artifacts / "tree.json").write_text(
            json.dumps(self.steps.accept.tree_state(repo or self.run.repo)), encoding="utf-8")

    def test_good_reply_writes_purpose_and_means(self):
        """keep-essence の 9: purpose.json は means を外した物、解き方は purpose-means.json に"""
        self.snap()
        self.assertEqual(self.check(GOOD), {"ok": True, "reason": ""})
        doc = self.read("purpose.json")
        self.assertNotIn("means", doc)
        self.assertEqual(doc["source_files"], ["docs/plan.md"])
        self.assertEqual(self.read("purpose-means.json"), {"means": ["分母を len(xs) にする"]})

    def test_no_means_still_writes_the_means_file(self):
        self.snap()
        self.assertTrue(self.check({k: v for k, v in GOOD.items() if k != "means"})["ok"])
        self.assertEqual(self.read("purpose-means.json"), {"means": []})

    def test_role_changed_the_tree_rejected(self):
        self.snap()
        (self.run.repo / "note.txt").write_text("書いた\n", encoding="utf-8")
        got = self.check(GOOD)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリー", got["reason"])
        self.assertFalse((self.run.artifacts / "purpose.json").exists())

    def test_missing_snapshot_rejected(self):
        got = self.check(GOOD)
        self.assertFalse(got["ok"])
        self.assertIn("tree.json が無い", got["reason"])

    def test_source_files_outside_or_missing_rejected(self):
        self.snap()
        for bad in (["/etc/hosts"], ["./README.md"], ["nothing.md"], ["../x.md"]):
            with self.subTest(bad):
                got = self.check({**GOOD, "source_files": bad})
                self.assertFalse(got["ok"], got)
                self.assertIn("source_files", got["reason"])

    def test_source_files_nested_ignored_and_subdir(self):
        """入れ子の綴り・git が無視するファイル・正規形でない名前を拒み、未追跡の新規は通す。サブディレクトリで回しても根からの相対を
        通し、そこからの相対は拒む"""
        (self.run.repo / "sub" / "new.md").write_text("x\n", encoding="utf-8")
        sub = self.run.repo / "sub"
        for repo, good, bads in ((self.run.repo, ["sub/x.py", "sub/new.md"],
                                  ("sub//x.py", "sub/./x.py", "sub/skip.log", "sub/x.py/", "Sub/x.py", "./sub/x.py")),
                                 (sub, ["sub/x.py"], ("x.py",))):
            for bad in bads:
                with self.subTest(repo=repo.name, bad=bad):
                    shutil.rmtree(self.run.artifacts)
                    self.run.artifacts.mkdir()
                    self.snap(repo)
                    got = self.check({**GOOD, "source_files": [*good, bad]}, repo)
                    self.assertFalse(got["ok"], got)
                    self.assertIn(f"source_files に作業ツリーの根からの相対の正規形で版に在るファイルでない物が在る: {[bad]!r}",
                                  got["reason"])
            with self.subTest(repo=repo.name, good=good):
                shutil.rmtree(self.run.artifacts)
                self.run.artifacts.mkdir()
                self.snap(repo)
                got = self.check({**GOOD, "source_files": good}, repo)
                self.assertTrue(got["ok"], got)
                self.assertEqual(self.read("purpose.json")["source_files"], good)

    def test_frozen_purpose_is_not_overwritten(self):
        """once: 固めた目的を書き直さない"""
        self.snap()
        self.assertTrue(self.check(GOOD)["ok"])
        got = self.check({**GOOD, "purpose_text": "別の目的"})
        self.assertFalse(got["ok"])
        self.assertIn("既に在る", got["reason"])
        self.assertEqual(self.read("purpose.json")["purpose_text"], "平均の関数が正しい値を返す")

    def test_unreadable_reply_is_a_rejection(self):
        self.intake()
        got = self.run.script("purpose_accept", reply="not json")
        self.assertEqual((got["ok"], got["done"]), (False, False))


class FinishCase(_RepoCase):
    def test_accepted_purpose_is_returned(self):
        """keep-essence の 12: 依頼の解き方の並びが出力の欄に載る"""
        self.intake()
        self.prep()
        self.assertEqual(self.accept(GOOD), {"ok": True, "done": True, "reason": ""})
        fin = self.run.script("finish")
        self.assertEqual(fin, {"ok": True, "status": "ok", "reason": "",
                               "purpose": {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "purpose.json"},
                               "purpose_text": "平均の関数が正しい値を返す", "source": "②計画・タスク記述",
                               "means": ["分母を len(xs) にする"], "report": []})

    def test_frozen_purpose_is_returned(self):
        (self.run.artifacts / "purpose.json").write_text(json.dumps({k: v for k, v in GOOD.items() if k != "means"},
                                                                    ensure_ascii=False), encoding="utf-8")
        (self.run.artifacts / "purpose-means.json").write_text(json.dumps({"means": ["前の解き方"]}, ensure_ascii=False),
                                                               encoding="utf-8")
        self.intake()
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"], fin["reason"]), (True, "ok", "目的は既に固めてある（purpose.json）"))
        self.assertEqual((fin["purpose_text"], fin["means"]), ("平均の関数が正しい値を返す", ["前の解き方"]))

    def test_three_rejections_give_up(self):
        self.intake()
        for _ in range(3):
            self.prep()
            got = self.accept({**GOOD, "source_files": ["nothing.md"]})
        self.assertEqual((got["ok"], got["done"]), (False, True))
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"], fin["purpose"], fin["purpose_text"], fin["source"], fin["means"]),
                         (False, "failed", None, "", "", []))
        self.assertIn("nothing.md", fin["reason"])
        self.assertEqual(fin["report"], [f"目的の文: {fin['reason']}"])

    def test_failed_intake_is_failed(self):
        self.intake(request="")
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"], fin["purpose"]), (False, "failed", None))
        self.assertIn("目的の役の支度が落ちた", fin["reason"])

    def test_role_that_never_ran(self):
        self.intake()
        fin = self.run.script("finish")
        self.assertEqual(fin["status"], "failed")
        self.assertIn("目的の文を受け付けた控えが無い", fin["reason"])

    def test_included_block_writes_in_its_own_place(self):
        self.run.script("intake", "judge__purpose__intake", request=REQUEST, pr_text="", constraints="[]", lang="")
        self.run.script("purpose_prep", "judge__purpose__purpose-loop.purpose-prep")
        self.run.script("purpose_accept", "judge__purpose__purpose-loop.purpose-accept", reply=json.dumps(GOOD))
        fin = self.run.script("finish", "judge__purpose__finish")
        self.assertEqual(fin["purpose"]["path"], "judge/purpose/purpose.json")
        self.assertFalse((self.run.artifacts / "purpose.json").exists())


def _doc() -> dict:
    return yaml.safe_load((BLOCK / "works-factory-purpose.yaml").read_text(encoding="utf-8"))


def _nodes(doc) -> list:
    return [m for n in doc["nodes"] for m in [n, *(n.get("loop_group") or {}).get("nodes", [])]]


class ShapeCase(unittest.TestCase):
    """YAML と src/steps の揃い（block の形の検査は tests/layers/test_block_shape.py）"""

    def setUp(self):
        self.steps = kit.load("purpose", "steps")
        self.nodes = {n["id"]: n for n in _nodes(_doc())}

    def test_source_enums_match_the_words(self):
        role = self.nodes["purpose"]["output_format"]["properties"]["source"]["enum"]
        self.assertEqual(tuple(role), self.steps.SOURCES)
        self.assertEqual(tuple(self.nodes["finish"]["output_format"]["properties"]["source"]["enum"]), (*self.steps.SOURCES, ""))

    def test_loop_bound_matches_the_give_up_count(self):
        self.assertEqual(self.nodes["purpose-loop"]["loop_group"]["max_iterations"], self.steps.rolekit.GIVE_UP_AFTER)

    def test_role_keeps_the_old_settings(self):
        node = self.nodes["purpose"]
        self.assertEqual({k: node.get(k) for k in ("model", "settingSources", "allowed_tools", "mutates_checkout", "sandbox",
                                                   "idle_timeout", "retry")},
                         {"model": "@wf-judge-materials", "settingSources": ["user"],
                          "allowed_tools": ["Read", "Grep", "Glob", "WebSearch", "WebFetch"], "mutates_checkout": False,
                          "sandbox": {"enabled": True, "allowUnsandboxedCommands": False}, "idle_timeout": 1728000000,
                          "retry": {"max_attempts": 2, "on_error": "all"}})

    def test_tree_keys_leave_out_porcelain(self):
        self.assertEqual(self.steps.TREE_KEYS, self.steps.accept.BEYOND_STATUS)


if __name__ == "__main__":
    unittest.main()
