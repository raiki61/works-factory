"""前提の実測の block を、script を子のプロセスで回して確かめる（docs/design/premises.md の 7.2）。

始めの記録の無い使い捨ての run directory と git のリポジトリ（stats.py）で、port の値だけを渡し、intake → measure_prep → 台本の返答 →
measure_accept → finish と回す。受け付けの決まりは src/steps の check をこの過程で呼んで確かめる。YAML と筋書きの揃いも見る。筋書きを
Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import sys
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

sys.path.extend(str(kit.ROOT / "lib" / sub).rstrip("/") for sub in ("", "graphloops"))
from engine.schema import validate_schema  # noqa: E402

BLOCK = kit.BLOCKS / "premises"
FINDINGS = [{"where": "stats.py:4", "text": "mean は 2 でなく 3 を返す", "measured": "3"}]
REQUEST = json.dumps(FINDINGS, ensure_ascii=False)
CARRIED_ROW = {"text": "上限は config.py:3 の 10", "measured_how": "前の run の前提の検算（run run-0）", "kind": "実測"}
GOOD = {"constraints": [{"text": "stats.py:4: mean は 3 を返す", "measured_how": "python3 で呼んだ", "kind": "実測",
                         "measured_output": "$ python3 -c 'import stats; print(stats.mean([1,2,3]))'\n3"}]}
HYP = {"constraints": [{"text": "stats.py:4 は本番の値で測れない", "measured_how": "読んだ", "kind": "仮説"}]}


class _RepoCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "premises")
        (self.run.repo / "stats.py").write_text("def mean(xs):\n    return sum(xs) / len(xs)\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")
        self.steps = kit.load("premises", "steps")

    def intake(self, **inputs):
        return self.run.script("intake", **{"request": REQUEST, "carried": "[]", "lang": "", **inputs})

    def prep(self):
        return self.run.script("measure_prep")

    def accept(self, reply):
        return self.run.script("measure_accept", reply=json.dumps(reply, ensure_ascii=False))

    def read(self, name):
        return json.loads((self.run.artifacts / name).read_text(encoding="utf-8"))


class IntakeCase(_RepoCase):
    def test_array_and_container_give_the_same_findings(self):
        self.assertEqual(self.intake(), {"due": True, "reason": ""})
        self.assertEqual(self.read("intake.json")["findings"], FINDINGS)
        container = json.dumps({"findings": FINDINGS, "pr": [], "issue": []}, ensure_ascii=False)
        self.assertTrue(self.intake(request=container)["due"])
        self.assertEqual(self.read("intake.json")["findings"], FINDINGS)

    def test_empty_request_is_due(self):
        self.assertEqual(self.intake(request="[]"), {"due": True, "reason": ""})
        self.assertEqual(self.read("intake.json")["findings"], [])

    def test_carried_comes_from_the_port_or_the_container(self):
        """carried が空で依頼が容器なら容器の constraints を使う。port の carried が在ればそれ（配列でも {constraints} でも）"""
        container = json.dumps({"findings": FINDINGS, "constraints": [CARRIED_ROW]}, ensure_ascii=False)
        self.intake(request=container)
        self.assertEqual(self.read("intake.json")["carried"], [CARRIED_ROW])
        other = {**CARRIED_ROW, "text": "別の事実"}
        for shape in ([other], {"constraints": [other]}):
            with self.subTest(shape=shape):
                self.intake(request=container, carried=json.dumps(shape, ensure_ascii=False))
                self.assertEqual(self.read("intake.json")["carried"], [other])

    def test_carried_rows_of_a_past_run_need_no_output(self):
        """運ばれた実測は前の run の検算の行（carry.carried_constraints）で、kind が実測でも measured_output を持たない"""
        self.assertTrue(self.intake(carried=json.dumps([CARRIED_ROW], ensure_ascii=False))["due"])

    def test_tree_is_snapshot(self):
        self.intake()
        self.assertEqual(self.read("tree.json"), self.steps.accept.tree_state(self.run.repo))

    def test_unreadable_request_does_not_stop_the_run(self):
        for raw in (self.run.pointer("absent.json"), '{"rows": []}', ""):
            with self.subTest(raw):
                got = self.intake(request=raw)
                self.assertFalse(got["due"])
                self.assertIn("前提の実測の支度が落ちた", got["reason"])
                self.assertTrue(self.read("intake.json")["failed"])

    def test_bad_carried_row_is_named(self):
        got = self.intake(carried=json.dumps([{"text": "x", "measured_how": "y", "kind": "憶測"}], ensure_ascii=False))
        self.assertFalse(got["due"])
        self.assertIn("入力 carried", got["reason"])

    def test_intake_clears_only_its_own_files(self):
        self.intake()
        self.prep()
        self.assertFalse(self.accept({"constraints": []})["ok"])
        (self.run.artifacts / "premises.json").write_text("{}", encoding="utf-8")
        (self.run.artifacts / "other.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self.intake(), {"due": True, "reason": ""})
        for name in ("rejects-premises.json", "premises-prompt-1.md", "premises.json"):
            self.assertFalse((self.run.artifacts / name).exists(), name)
        self.assertTrue((self.run.artifacts / "other.json").is_file(), "ほかの物の名のファイルは消さない")


class PromptCase(_RepoCase):
    def test_request_json_reaches_the_prompt(self):
        self.intake()
        text = self.prep()["prompt"]
        self.assertIn('"where": "stats.py:4"', text)
        self.assertNotIn("ARTIFACTS_DIR", text)
        self.assertNotIn("judge/request.json", text)
        self.assertNotRegex(text, r"\{[a-z0-9_]+\}", "埋まらない差し込み口が無い")
        self.assertNotIn("Why your previous answer was rejected", text)
        self.assertTrue((self.run.artifacts / "premises-prompt-1.md").is_file())

    def test_empty_request_is_an_empty_array(self):
        self.intake(request="[]")
        self.assertIn("```json\n[]\n```", self.prep()["prompt"])

    def test_query_rule_is_in_without_the_spawns_paragraph(self):
        self.intake()
        text = self.prep()["prompt"]
        rule = (kit.SHARED / "prompts" / "query-rule.md").read_text(encoding="utf-8").splitlines()[1:]   # 0 行目は道具の印（指示には出ない）
        self.assertTrue(text.startswith(rule[0]), text[:80])
        self.assertNotIn("required-for-tools", text)
        spawns = rule[rule.index("<!-- if spawns -->") + 1:rule.index("<!-- end spawns -->")]
        self.assertTrue(spawns)
        for line in spawns:
            self.assertNotIn(line, text)

    def test_rejections_reach_the_next_prompt(self):
        self.intake()
        self.prep()
        got = self.accept({"constraints": []})
        self.assertEqual((got["ok"], got["done"]), (False, False))
        again = self.prep()["prompt"]
        self.assertTrue(again.startswith("## Why your previous answer was rejected"), again[:80])
        self.assertIn("stats.py:4", again)
        self.assertTrue((self.run.artifacts / "premises-prompt-2.md").is_file())

    def test_prep_without_intake_fails_the_node(self):
        self.assertIn("intake.json", self.run.failing("measure_prep"))


class AcceptCase(_RepoCase):
    def check(self, reply, findings=FINDINGS, carried=()):
        with self.run.env():
            return self.steps.check(reply, self.run.artifacts, self.run.repo, findings, list(carried))

    def snap(self):
        (self.run.artifacts / "tree.json").write_text(json.dumps(self.steps.accept.tree_state(self.run.repo)), encoding="utf-8")

    def test_measured_without_output_rejected(self):
        self.snap()
        for bad in ({"text": "a", "measured_how": "b", "kind": "実測"},
                    {"text": "a", "measured_how": "b", "kind": "実測", "measured_output": "  "}):
            with self.subTest(bad):
                got = self.check({"constraints": [bad]}, [])
                self.assertFalse(got["ok"])
                self.assertIn("measured_output", got["reason"])
        self.assertFalse((self.run.artifacts / "premises.json").exists(), "拒んだ返答は書かない")

    def test_hypothesis_needs_no_output_and_good_reply_is_written(self):
        self.snap()
        self.assertTrue(self.check({"constraints": [{"text": "a", "measured_how": "b", "kind": "仮説"}]}, [])["ok"])
        self.assertTrue(self.check(GOOD)["ok"])
        self.assertEqual(self.read("premises.json"), GOOD)

    def test_contradicts_names_a_request_line(self):
        """任意の欄 contradicts（docs/design/spec-driven.md の 2.5 の詰まった所の 4）: 行が食い違う依頼の行の where。依頼の行に無い
        where は拒む。書かない行は今どおり"""
        self.snap()
        row = {**GOOD["constraints"][0], "contradicts": "stats.py:4"}
        self.assertTrue(self.check({"constraints": [row]})["ok"])
        self.assertEqual(self.read("premises.json")["constraints"][0]["contradicts"], "stats.py:4")
        got = self.check({"constraints": [{**row, "contradicts": "nope.py:1"}]})
        self.assertFalse(got["ok"])
        self.assertIn("contradicts", got["reason"])

    def test_request_claim_must_be_measured_again(self):
        self.snap()
        other = {"constraints": [{"text": "README.md の件数は 3", "measured_how": "grep", "kind": "仮説"}]}
        got = self.check(other)
        self.assertFalse(got["ok"])
        self.assertIn("stats.py:4", got["reason"])
        self.assertTrue(self.check(HYP)["ok"], "測り直せず仮説に落としても where を text に含めば通る")

    def test_role_changed_the_tree_rejected(self):
        self.snap()
        (self.run.repo / "out.txt").write_text("測った出力\n", encoding="utf-8")
        got = self.check(GOOD)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリーが変わった", got["reason"])
        (self.run.repo / "out.txt").unlink()
        self.assertTrue(self.check(GOOD)["ok"])
        (self.run.repo / "stats.py").write_text("x = 1\n", encoding="utf-8")
        git(self.run.repo, "commit", "-qam", "x")
        self.assertFalse(self.check(GOOD)["ok"], "commit しても HEAD で見える")

    def test_bytecode_counts_like_any_change(self):
        self.snap()
        (self.run.repo / "__pycache__").mkdir()
        (self.run.repo / "__pycache__" / "m.cpython-312.pyc").write_bytes(b"\0")
        got = self.check(GOOD)
        self.assertFalse(got["ok"])
        self.assertIn("作業ツリー", got["reason"])

    def test_missing_snapshot_rejected(self):
        got = self.check(GOOD)
        self.assertFalse(got["ok"])
        self.assertIn("tree.json が無い", got["reason"])

    def test_unreadable_reply_is_a_rejection(self):
        self.intake()
        got = self.run.script("measure_accept", reply="not json")
        self.assertEqual((got["ok"], got["done"]), (False, False))


class CarriedCase(_RepoCase):
    def test_carried_rows_join_the_reply_once(self):
        with self.run.env():
            self.intake()
        joined = self.steps.with_carried(GOOD, [CARRIED_ROW, GOOD["constraints"][0]])
        self.assertEqual(joined["constraints"], [*GOOD["constraints"], CARRIED_ROW], "同じ text の行は 2 度足さない")

    def test_accepted_reply_is_written_with_the_carried_rows(self):
        self.intake(carried=json.dumps([CARRIED_ROW], ensure_ascii=False))
        self.prep()
        self.assertEqual(self.accept(GOOD), {"ok": True, "done": True, "reason": ""})
        self.assertEqual(self.read("premises.json")["constraints"], [*GOOD["constraints"], CARRIED_ROW])

    def test_real_carried_rows_fit_the_port_and_the_role_shape(self):
        """報告が次の依頼に書く行（carry.carried_constraints）は、port の形にも役の返答の行にもそのまま合う"""
        import carry
        rows = carry.carried_constraints(["上限は config.py:3 の 10", "  ", 3], "run-0")
        self.assertEqual(len(rows), 1)
        self.assertEqual(validate_schema({"constraints": rows}, _nodes()["premises"]["output_format"]), [])
        self.assertTrue(self.intake(carried=json.dumps(rows, ensure_ascii=False))["due"])
        self.assertEqual(self.read("intake.json")["carried"], rows)


class FinishCase(_RepoCase):
    def test_accepted_reply_is_returned(self):
        self.intake()
        self.prep()
        self.assertTrue(self.accept(GOOD)["ok"])
        self.assertEqual(self.run.script("finish"),
                         {"ok": True, "status": "ok", "reason": "",
                          "constraints": {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "premises.json"},
                          "report": []})

    def test_report_names_the_request_measured_that_stayed_a_hypothesis(self):
        self.intake()
        self.prep()
        self.assertTrue(self.accept(HYP)["ok"])
        fin = self.run.script("finish")
        self.assertEqual(fin["report"], [f"依頼の実測を測り直せなかった（前提は仮説）: stats.py:4——{HYP['constraints'][0]['text']}"])

    def test_report_is_empty_without_measured_in_the_request(self):
        self.intake(request=json.dumps([{"where": "stats.py:4", "text": "x"}]))
        self.prep()
        self.assertTrue(self.accept(HYP)["ok"])
        self.assertEqual(self.run.script("finish")["report"], [])

    def test_empty_request_is_ok_with_no_constraints(self):
        self.intake(request="[]")
        self.prep()
        self.assertTrue(self.accept({"constraints": []})["ok"])
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"], fin["report"]), (True, "ok", []))

    def test_three_rejections_give_up(self):
        self.intake()
        for _ in range(3):
            self.prep()
            got = self.accept({"constraints": []})
        self.assertEqual((got["ok"], got["done"]), (False, True))
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"], fin["constraints"]), (False, "failed", None))
        self.assertIn("stats.py:4", fin["reason"])
        self.assertIn("3 回とも", fin["reason"], "諦めた文（given_up_reason）で、最後の拒否の文そのままではない")
        self.assertEqual(fin["report"], [f"前提の制約: {fin['reason']}"])

    def test_one_rejection_reports_the_last_rejection(self):
        self.intake()
        self.prep()
        self.accept({"constraints": []})
        fin = self.run.script("finish")
        self.assertEqual(fin["status"], "failed")
        self.assertIn("stats.py:4", fin["reason"])
        self.assertNotIn("回とも", fin["reason"])

    def test_role_that_never_ran(self):
        self.intake()
        fin = self.run.script("finish")
        self.assertEqual(fin["status"], "failed")
        self.assertIn("前提の実測を受け付けた控えが無い", fin["reason"])

    def test_failed_intake_is_failed(self):
        self.intake(request="")
        fin = self.run.script("finish")
        self.assertEqual((fin["ok"], fin["status"], fin["constraints"]), (False, "failed", None))
        self.assertIn("前提の実測の支度が落ちた", fin["reason"])

    def test_included_block_writes_in_its_own_place(self):
        self.run.script("intake", "judge__premises-run__intake", request=REQUEST, carried="[]", lang="")
        self.run.script("measure_prep", "judge__premises-run__premises-loop.premises-prep")
        self.run.script("measure_accept", "judge__premises-run__premises-loop.premises-accept", reply=json.dumps(GOOD))
        fin = self.run.script("finish", "judge__premises-run__finish")
        self.assertEqual(fin["constraints"]["path"], "judge/premises-run/premises.json")
        self.assertFalse((self.run.artifacts / "premises.json").exists())


def _doc() -> dict:
    return yaml.safe_load((BLOCK / "works-factory-premises.yaml").read_text(encoding="utf-8"))


def _nodes() -> dict:
    return {m["id"]: m for n in _doc()["nodes"] for m in [n, *(n.get("loop_group") or {}).get("nodes", [])]}


class ShapeCase(unittest.TestCase):
    """YAML と src/steps の揃い（block の形の検査は tests/layers/test_block_shape.py）"""

    def setUp(self):
        self.steps = kit.load("premises", "steps")
        self.nodes = _nodes()

    def test_kind_enum_matches_the_words(self):
        enum = self.nodes["premises"]["output_format"]["properties"]["constraints"]["items"]["properties"]["kind"]["enum"]
        self.assertEqual(tuple(enum), (self.steps.MEASURED, self.steps.HYPOTHESIS))

    def test_loop_bound_matches_the_give_up_count(self):
        self.assertEqual(self.nodes["premises-loop"]["loop_group"]["max_iterations"], self.steps.rolekit.GIVE_UP_AFTER)

    def test_role_keeps_the_old_settings(self):
        node = self.nodes["premises"]
        self.assertEqual({k: node.get(k) for k in ("model", "settingSources", "allowed_tools", "mutates_checkout", "sandbox",
                                                   "idle_timeout", "retry")},
                         {"model": "@wf-judge-materials", "settingSources": ["user"],
                          "allowed_tools": ["Read", "Grep", "Glob", "Bash", "WebSearch", "WebFetch"], "mutates_checkout": None,
                          "sandbox": {"enabled": True, "allowUnsandboxedCommands": False,
                                      "filesystem": {"denyWrite": ["~/../archon-home"]}},
                          "idle_timeout": 1728000000, "retry": {"max_attempts": 2, "on_error": "all"}})

    def test_role_reply_outside_the_type_is_rejected(self):
        shape = self.nodes["premises"]["output_format"]
        row = {"text": "a", "measured_how": "b", "kind": "実測", "measured_output": "x"}
        self.assertEqual(validate_schema({"constraints": [row]}, shape), [])
        for bad in ({"constraints": [{**row, "kind": "憶測"}]}, {"constraints": [{**row, "measured_output": "  "}]},
                    {"constraints": [{**row, "extra": 1}]}, {"rows": []}):
            with self.subTest(bad):
                self.assertTrue(validate_schema(bad, shape))

    def test_finish_fields_match_the_returns_shape(self):
        props = self.nodes["finish"]["output_format"]["properties"]
        self.assertEqual(set(props), {"ok", "status", "reason", "constraints", "report"})


if __name__ == "__main__":
    unittest.main()
