"""run の頭の深さの block を、script を子のプロセスで回して確かめる（docs/design/head-depth.md の 7.2）。

始めの記録の無い使い捨ての run directory と git のリポジトリ（stats.py の 4-5 行目に分母の誤り）で、port の値だけを渡し、
intake → depth_prep → 台本の返答 → depth_accept → finish と回す。受け付けの決まりは src/steps の check を直に呼んでも確かめる。
YAML と筋書きの揃いも見る。筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = kit.BLOCKS / "head-depth"
TEXT = "mean は 2 でなく 3 を返す"
ROWS = [{"where": "stats.py:4-5", "text": TEXT}]
REQUEST = json.dumps(ROWS, ensure_ascii=False)
CODE = "return sum(xs) / (len(xs) - 1)"
NONE_ITEM = {"item": 1, "unknown": "無し", "cause_quote": TEXT, "where": "stats.py:4-5", "code_quote": CODE}
CAUSE_ITEM = {"item": 1, "unknown": "原因", "cause_quote": TEXT}
LIGHT_REPLY = {"why": "直す所が引用で示せる", "items": [NONE_ITEM], "groups": []}


def reply(*items, groups=(), why="行ごとに種類を付けた"):
    return {"why": why, "items": list(items), "groups": list(groups)}


class _RepoCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "head-depth")
        (self.run.repo / "stats.py").write_text(
            "def mean(xs):\n    if not xs:\n        return 0\n    total = sum(xs)\n    " + CODE + "\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")
        self.steps = kit.load("head-depth", "steps")

    def intake(self, include="", **inputs):
        ports = {"request": REQUEST, "has_checks": "true", "thickness": "auto", "spec": "false", "design_only": "false", "lang": "",
                 **inputs}
        return self.run.script("intake", include, **ports)

    def prep(self):
        return self.run.script("depth_prep")

    def accept(self, doc):
        return self.run.script("depth_accept", reply=json.dumps(doc, ensure_ascii=False))

    def finish(self):
        return self.run.script("finish")

    def read(self, name):
        return json.loads((self.run.artifacts / name).read_text(encoding="utf-8"))


class GateCase(_RepoCase):
    def test_nothing_stops_the_role(self):
        self.assertEqual(self.intake(), {"due": True, "reason": ""})
        rec = self.read("depth-head.json")
        self.assertEqual((rec["depth"], rec["why"]), ("標準", self.steps.NO_REPLY))
        self.assertEqual(rec["facts"], {"items": [{"item": 1, "text": TEXT, "where": "stats.py:4-5", "path_ok": True, "lines_ok": True}],
                                        "test_cmd": True, "spec": False, "design_only": False, "forced": ""})
        doc = self.read("intake.json")
        self.assertEqual((doc["due"], doc["failed"], doc["reason"], doc["lang"]), (True, False, "", ""))

    def test_each_stop_skips_the_role_and_keeps_the_tier(self):
        for name, inputs, tier, why in (
                ("no checks", {"has_checks": "false"}, "標準", "機械の確かめが無い"),
                ("named light", {"thickness": "light"}, "軽量", "入力 thickness の名指し（軽量）"),
                ("named standard", {"thickness": "standard"}, "標準", "入力 thickness の名指し（標準）"),
                ("named heavy", {"thickness": "heavy"}, "重厚", "入力 thickness の名指し（重厚）"),
                ("spec", {"spec": "true"}, "標準", "仕様の段を挟む run"),
                ("design only", {"design_only": "true"}, "標準", "設計だけの run"),
                ("no rows", {"request": "[]"}, "標準", "依頼の行が無い")):
            with self.subTest(name):
                got = self.intake(**inputs)
                self.assertFalse(got["due"])
                self.assertIn(why, got["reason"])
                rec = self.read("depth-head.json")
                self.assertEqual(rec["depth"], tier)
                self.assertIn(why, rec["why"])

    def test_empty_thickness_means_auto(self):
        self.assertTrue(self.intake(thickness="")["due"])

    def test_place_measures_the_address(self):
        rows = json.dumps([{"where": "stats.py:4-5", "text": "a"}, {"where": "stats.py:99", "text": "b"},
                           {"where": "nothing.py:1", "text": "c"}, {"where": "", "text": "d"}])
        self.intake(request=rows)
        got = [(i["path_ok"], i["lines_ok"]) for i in self.read("depth-head.json")["facts"]["items"]]
        self.assertEqual(got, [(True, True), (True, False), (False, False), (False, False)])

    def test_request_in_a_container(self):
        self.intake(request=json.dumps({"findings": ROWS}, ensure_ascii=False))
        self.assertEqual(len(self.read("intake.json")["facts"]["items"]), 1)

    def test_unreadable_port_does_not_stop_the_run(self):
        for name, inputs in (("pointer", {"request": self.run.pointer("absent.json")}), ("shape", {"request": '{"rows": 1}'}),
                             ("flag", {"has_checks": "maybe"}), ("choice", {"thickness": "heavier"})):
            with self.subTest(name):
                got = self.intake(**inputs)
                self.assertFalse(got["due"])
                self.assertIn("run の頭の深さの支度が落ちた", got["reason"])
                self.assertTrue(self.read("intake.json")["failed"])
                self.assertEqual(self.read("depth-head.json")["depth"], "標準")

    def test_intake_clears_its_own_stale_files(self):
        self.intake()
        self.prep()
        self.assertFalse(self.accept(reply({**CAUSE_ITEM, "cause_quote": "依頼に無い字の引用"}))["ok"])
        self.prep()
        self.assertTrue((self.run.artifacts / "head-depth-prompt-2.md").is_file())
        (self.run.artifacts / "other.json").write_text("{}", encoding="utf-8")
        self.assertTrue(self.intake()["due"])
        for name in ("rejects-head-depth.json", "head-depth-prompt-1.md", "head-depth-prompt-2.md"):
            self.assertFalse((self.run.artifacts / name).exists(), name)
        self.assertTrue((self.run.artifacts / "other.json").is_file(), "ほかの物の名のファイルは消さない")
        self.assertNotIn("依頼に無い字の引用", self.prep()["prompt"])


class PromptCase(_RepoCase):
    def test_prompt_carries_rows_groups_and_words(self):
        self.intake()
        text = self.prep()["prompt"]
        self.assertIn("- Line 1: " + TEXT, text)
        self.assertIn("  - Location: stats.py:4-5 (file exists, line range inside the file)", text)
        self.assertIn("Allowed models (weakest first): haiku, sonnet, opus", text)
        launch = self.steps.launchgroups
        for name in launch.GROUPS:
            self.assertIn(f"`{name}`", text)
        self.assertEqual(sum(1 for line in text.splitlines() if line.startswith("- `@wf-")), len(launch.GROUPS))
        for word in (*self.steps.UNKNOWNS, *self.steps.HEADS):
            self.assertIn(word, text)
        self.assertNotRegex(text, r"\{[a-z0-9_]+\}", "埋まらない差し込み口が無い")
        self.assertNotIn("Why your previous answer was rejected", text)
        self.assertTrue((self.run.artifacts / "head-depth-prompt-1.md").is_file())

    def test_limits_come_from_the_code(self):
        self.intake()
        text = self.prep()["prompt"]
        cite = self.steps.cite
        self.assertIn(f"{cite.QUOTE_MIN} ", text)
        self.assertIn(f"{self.steps.WHERE_SPAN} ", text)

    def test_lang_fills_the_last_sentence(self):
        self.intake(lang="Japanese")
        self.assertIn("Japanese", self.prep()["prompt"])
        self.setUp()
        self.intake()
        self.assertIn("the language of the request", self.prep()["prompt"])

    def test_rejections_come_back_in_the_next_prompt_all_of_them(self):
        self.intake()
        self.prep()
        bad = reply({**CAUSE_ITEM, "cause_quote": "一回目の外れ"})
        self.assertEqual(self.accept(bad)["done"], False)
        self.prep()
        self.accept(reply({**CAUSE_ITEM, "cause_quote": "二回目の外れ"}))
        third = self.prep()["prompt"]
        self.assertTrue(third.startswith("## Why your previous answer was rejected"), third[:80])
        self.assertEqual(third.count("回目の拒否"), 2)
        self.assertTrue((self.run.artifacts / "head-depth-prompt-3.md").is_file())

    def test_prep_without_intake_fails_the_node(self):
        self.assertIn("intake.json", self.run.failing("depth_prep"))


class CheckCase(_RepoCase):
    def check(self, doc, rows=None, repo=None):
        facts = self.steps.facts(ROWS if rows is None else rows, has_checks=True, spec=False, design_only=False, forced="",
                                 repo=repo or self.run.repo)
        return self.steps.check(doc, facts["items"], repo or self.run.repo)

    def test_quoted_light_and_scope_pass(self):
        self.assertEqual(self.check(LIGHT_REPLY), [])
        self.assertEqual(self.check(reply({**NONE_ITEM, "unknown": "範囲", "where": "stats.py:1-5"})), [])

    def test_standard_kinds_pass_with_the_quote_only(self):
        self.assertEqual(self.check(reply(CAUSE_ITEM)), [])

    def test_quote_missing_from_the_text_or_code_is_refused(self):
        bad = self.check(reply({**NONE_ITEM, "cause_quote": "依頼に無い字の引用"}))
        self.assertIn("行 1: cause_quote が依頼のその行の字の部分でない", bad)
        bad = self.check(reply({**NONE_ITEM, "code_quote": "return nothing here"}))
        self.assertIn("行 1: code_quote が stats.py:4-5 の字に無い", bad)

    def test_quote_floor(self):
        bad = self.check(reply({**NONE_ITEM, "cause_quote": "me"}), rows=[{"where": "stats.py:4-5", "text": "mean は 2"}])
        self.assertEqual(len([b for b in bad if "字より短い" in b]), 1)
        self.assertIn(f"{self.steps.cite.QUOTE_MIN} 字より短い", bad[0])

    def test_where_span_edge(self):
        (self.run.repo / "long.py").write_text("value = 1\n" * 40, encoding="utf-8")
        edge = self.steps.WHERE_SPAN
        ok = {**NONE_ITEM, "where": f"long.py:1-{edge}", "code_quote": "value = 1"}
        self.assertEqual(self.check(reply(ok)), [])
        wide = self.check(reply({**ok, "where": f"long.py:1-{edge + 1}"}))
        self.assertTrue(any("より広い" in b for b in wide), wide)
        self.assertEqual(self.check(reply({**ok, "unknown": "形", "where": f"long.py:1-{edge + 1}"})), [])

    def test_no_rows_refused(self):
        self.assertEqual(self.check(reply(), rows=[]), [self.steps.NO_ROWS])

    def test_every_row_exactly_once(self):
        two = [*ROWS, {"where": "stats.py:1", "text": "def mean が要る"}]
        self.assertIn("ちょうど 1 度ずつ指していない", self.check(reply(CAUSE_ITEM), rows=two)[0])
        self.assertIn("ちょうど 1 度ずつ指していない", self.check(reply(CAUSE_ITEM, CAUSE_ITEM), rows=ROWS)[0])
        self.assertEqual(self.check("not a dict"), ["返答が object でない"])
        self.assertEqual(self.check({**LIGHT_REPLY, "why": " "}), ["why が空"])

    def test_unknown_word_outside_the_table(self):
        self.assertIn("unknown が", self.check(reply({**CAUSE_ITEM, "unknown": "不明"}))[0])

    def test_cause_checks_where_only_when_written(self):
        self.assertEqual(self.check(reply({**CAUSE_ITEM, "where": "stats.py:4-5", "code_quote": CODE})), [])
        bad = self.check(reply({**CAUSE_ITEM, "where": "stats.py:99", "code_quote": CODE}))
        self.assertTrue(any("where が通らない" in b for b in bad), bad)
        bad = self.check(reply({**CAUSE_ITEM, "where": "stats.py:4-5"}))
        self.assertTrue(any("code_quote が" in b for b in bad), bad)

    def test_tier_is_the_heaviest_kind(self):
        tier = self.steps.tier_of
        self.assertEqual(tier([{"unknown": "無し"}]), "軽量")
        self.assertEqual(tier([{"unknown": "無し"}, {"unknown": "形"}]), "標準")
        self.assertEqual(tier([{"unknown": "無し"}, {"unknown": "範囲"}, {"unknown": "原因"}]), "重厚")
        self.assertEqual(tier([]), "標準")
        self.assertEqual(tier([{"unknown": "未知"}]), "標準")


class AcceptCase(_RepoCase):
    def test_quoted_light_reply_is_taken(self):
        self.intake()
        self.prep()
        self.assertEqual(self.accept(LIGHT_REPLY), {"ok": True, "done": True, "reason": ""})
        rec = self.read("depth-head.json")
        self.assertEqual((rec["depth"], rec["why"], rec["items"]), ("軽量", "直す所が引用で示せる", [NONE_ITEM]))

    def test_tier_follows_the_heaviest_kind_and_the_row_kinds_are_recorded(self):
        self.intake(request=json.dumps([*ROWS, {"where": "stats.py:1", "text": "def mean の型を変える"}]))
        self.accept(reply(NONE_ITEM, {"item": 2, "unknown": "範囲", "cause_quote": "def mean の型を変える",
                                      "where": "stats.py:1", "code_quote": "def mean"}))
        rec = self.read("depth-head.json")
        self.assertEqual(rec["depth"], "重厚")
        self.assertEqual([i["unknown"] for i in rec["items"]], ["無し", "範囲"])

    def test_group_choices_are_recorded_without_changing_the_tier(self):
        groups = [{"group": "@wf-fix-writers", "model": "opus", "effort": "high", "why": "難しい"},
                  {"group": "@wf-nothing", "model": "opus", "effort": "high", "why": "表に無い"}]
        self.intake()
        self.accept(reply(CAUSE_ITEM, groups=groups))
        rec = self.read("depth-head.json")
        self.assertEqual(rec["depth"], "標準")
        self.assertEqual([(g["group"], g["model"], g["fallback"] != "") for g in rec["groups"]],
                         [("@wf-fix-writers", "opus", False), ("@wf-nothing", None, True)])

    def test_refused_reply_keeps_standard_and_the_role_why(self):
        self.intake()
        got = self.accept(reply({**CAUSE_ITEM, "cause_quote": "依頼に無い字の引用"}, why="役の訳です"))
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertIn("cause_quote が依頼のその行の字の部分でない", got["reason"])
        rec = self.read("depth-head.json")
        self.assertEqual(rec["depth"], "標準")
        self.assertTrue(rec["why"].startswith("役の返答が受け付けを通らない（"), rec["why"])
        self.assertIn("／役の訳: 役の訳です", rec["why"])
        self.assertEqual(rec["groups"], [])

    def test_unreadable_reply_is_a_rejection(self):
        self.intake()
        got = self.run.script("depth_accept", reply="not json")
        self.assertEqual((got["ok"], got["done"]), (False, False))
        self.assertEqual(self.read("depth-head.json")["depth"], "標準")

    def test_accept_without_intake_gives_up_without_falling(self):
        got = self.run.script("depth_accept", reply=json.dumps(LIGHT_REPLY))
        self.assertEqual((got["ok"], got["done"]), (False, True))


class FinishCase(_RepoCase):
    def assert_record_readable(self, fin, tier):
        self.assertEqual(fin["record"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "depth-head.json"})
        self.assertEqual(self.steps.headdepth.read_file(self.run.artifacts / "depth-head.json")["depth"], tier)
        self.assertEqual(fin["report"], [f"run の頭の深さ: {tier}（根拠: {fin['why']}）"])

    def test_accepted_reply(self):
        self.intake()
        self.prep()
        self.accept(LIGHT_REPLY)
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["reason"], fin["tier"], fin["why"], fin["rows"]),
                         (True, "ok", "", "軽量", "直す所が引用で示せる", [NONE_ITEM]))
        self.assert_record_readable(fin, "軽量")

    def test_machine_stop(self):
        self.intake(thickness="heavy")
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["reason"], fin["tier"], fin["rows"]), (True, "ok", "", "重厚", []))
        self.assert_record_readable(fin, "重厚")

    def test_three_rejections_give_up(self):
        self.intake()
        for _ in range(3):
            self.prep()
            got = self.accept(reply({**CAUSE_ITEM, "cause_quote": "依頼に無い字の引用"}))
        self.assertEqual((got["ok"], got["done"]), (False, True))
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["tier"], fin["rows"]), (False, "failed", "標準", []))
        self.assertIn("3 回とも", fin["reason"])
        self.assertIn("cause_quote が依頼のその行の字の部分でない", fin["reason"])
        self.assertIn("役の返答が受け付けを通らない", fin["why"])
        self.assert_record_readable(fin, "標準")

    def test_role_that_never_ran(self):
        self.intake()
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["tier"]), (False, "failed", "標準"))
        self.assertEqual(fin["reason"], self.steps.NO_REPLY)
        self.assert_record_readable(fin, "標準")

    def test_failed_intake_is_failed_with_standard(self):
        self.intake(request="")
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["tier"]), (False, "failed", "標準"))
        self.assertIn("run の頭の深さの支度が落ちた", fin["reason"])
        self.assert_record_readable(fin, "標準")

    def test_nothing_ran_still_returns_a_record(self):
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["tier"], fin["rows"]), (False, "failed", "標準", []))
        self.assert_record_readable(fin, "標準")

    def test_included_block_writes_in_its_own_place(self):
        self.intake("judge__head-depth__intake")
        self.run.script("depth_prep", "judge__head-depth__head-depth-loop.head-depth-prep")
        self.run.script("depth_accept", "judge__head-depth__head-depth-loop.head-depth-accept", reply=json.dumps(LIGHT_REPLY))
        fin = self.run.script("finish", "judge__head-depth__finish")
        self.assertEqual(fin["record"]["path"], "judge/head-depth/depth-head.json")
        self.assertFalse((self.run.artifacts / "depth-head.json").exists())


def _doc() -> dict:
    return yaml.safe_load((BLOCK / "works-factory-head-depth.yaml").read_text(encoding="utf-8"))


def _nodes(doc) -> list:
    return [m for n in doc["nodes"] for m in [n, *(n.get("loop_group") or {}).get("nodes", [])]]


class ShapeCase(unittest.TestCase):
    """YAML と src/steps の揃い（block の形の検査は tests/layers/test_block_shape.py）"""

    def setUp(self):
        self.steps = kit.load("head-depth", "steps")
        self.nodes = {n["id"]: n for n in _nodes(_doc())}

    def test_kind_and_tier_enums_match_the_code(self):
        role = self.nodes["head-depth"]["output_format"]["properties"]["items"]["items"]["properties"]["unknown"]["enum"]
        self.assertEqual(role, list(self.steps.UNKNOWNS))
        finish = self.nodes["finish"]["output_format"]["properties"]
        self.assertEqual(finish["rows"]["items"]["properties"]["unknown"]["enum"], list(self.steps.UNKNOWNS))
        self.assertEqual(finish["tier"]["enum"], list(self.steps.depth.HEADS))
        self.assertNotIn("tier", self.nodes["head-depth"]["output_format"]["properties"])
        self.assertNotIn("depth", self.nodes["head-depth"]["output_format"]["properties"])
        self.assertEqual(self.nodes["head-depth"]["output_format"]["required"], ["why", "items", "groups"])

    def test_thickness_words_match_the_input(self):
        text = _doc()["inputs"]["thickness"]["description"]
        self.assertTrue(text.startswith(f"choice({'|'.join(self.steps.THICKNESS)}):"), text)
        self.assertEqual(list(self.steps.THICKNESS.values())[1:], list(self.steps.HEADS))
        self.assertEqual(_doc()["inputs"]["thickness"]["default"], "auto")

    def test_loop_bound_matches_the_give_up_count(self):
        self.assertEqual(self.nodes["head-depth-loop"]["loop_group"]["max_iterations"], self.steps.rolekit.GIVE_UP_AFTER)

    def test_role_keeps_the_old_settings(self):
        node = self.nodes["head-depth"]
        self.assertEqual({k: node.get(k) for k in ("model", "settingSources", "allowed_tools", "mutates_checkout", "sandbox",
                                                   "idle_timeout", "retry")},
                         {"model": "@wf-judge-materials", "settingSources": ["user"], "allowed_tools": ["Read", "Grep", "Glob"],
                          "mutates_checkout": False, "sandbox": {"enabled": True, "allowUnsandboxedCommands": False},
                          "idle_timeout": 1728000000, "retry": {"max_attempts": 2, "on_error": "all"}})

    def test_the_old_reject_node_is_gone(self):
        self.assertEqual(set(self.nodes), {"intake", "head-depth-loop", "head-depth-prep", "head-depth", "head-depth-accept", "finish"})
        self.assertEqual(self.nodes["head-depth-accept"]["with"], {"reply": "$head-depth.output"})
        self.assertNotIn("with", self.nodes["head-depth-prep"])

    def test_kinds_map_to_the_old_tiers(self):
        self.assertEqual(self.steps.UNKNOWNS, {"無し": "軽量", "原因": "標準", "形": "標準", "範囲": "重厚"})


if __name__ == "__main__":
    unittest.main()
