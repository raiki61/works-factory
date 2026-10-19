"""目的の監査の block を、script を子のプロセスで回して確かめる（docs/design/materials.md の 8 節・docs/design/purpose-review.md の 2.9）。

始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡し、intake → role_prep → 台本の返答 →
role_accept → finish と回し、material.json と出力の 5 欄を照らす。拒まれる返答 3 回で gave_up になる道も回す。
筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import json
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit

BLOCK = kit.BLOCKS / "purpose-review"
NAME = "purpose-review"
LOOP = f"{NAME}-loop"
WRITER = "③writer の要約"
PLAN = "②計画・タスク記述"
PR = "①PR 説明"
TEXT = "設定の読み込みが空のファイルでも落ちないようにする"


def purpose(source=WRITER, text=TEXT) -> str:
    return json.dumps({"purpose_text": text, "source": source, "known_weaknesses": [], "source_files": []}, ensure_ascii=False)


def reply(*findings, verdict="狭めている", reason="目的が件数の数えに狭まっている"):
    return {"verdict": verdict, "reason": reason,
            "findings": [{"text": "目的が件数の数えに狭まっている", "cite": cite, "hits": hits} for cite, hits in findings]}


GOOD = reply(("件数は 3 件", 1))


class FlowCase(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, NAME)
        (self.run.repo / "README.md").write_text("# 対象\n\n件数は 3 件\n", encoding="utf-8")
        git(self.run.repo, "add", "-A")
        git(self.run.repo, "commit", "-q", "-m", "seed")

    def intake(self, **inputs):
        ports = {"base": "", "purpose": purpose(), "entry": "", "lang": "", **inputs}
        return self.run.script("intake", "intake", **ports)

    def prep(self):
        return self.run.script("role_prep", f"{LOOP}.{NAME}-prep")

    def accept(self, got):
        return self.run.script("role_accept", f"{LOOP}.{NAME}-accept", reply=json.dumps(got, ensure_ascii=False))

    def finish(self):
        return self.run.script("finish", "finish")

    def material(self):
        return json.loads((self.run.artifacts / "material.json").read_text(encoding="utf-8"))

    def test_findings_are_counted_again_against_the_fixed_version(self):
        """写す元 MaterialCase.test_purpose_review_findings_must_cite_the_version: 数の合う根拠だけが material.json の reply に載り、
        版に無い字・数の合わない申告・根拠の無い『狭めている』は今の字の拒みの文で返る"""
        cases = ((GOOD, ""),
                 (reply(("どこにも無い字列", 1)), "'どこにも無い字列' が現物に 1 件も無い"),
                 (reply(("件数は 3 件", 2)), "'件数は 3 件' の件数の申告 2 が数え直し 1 と違う"),
                 (reply(), "『狭めている』のに findings が空"),
                 (reply(("件数は 3 件\n件数", 1)), "cite に改行が入っている"),
                 (reply(("  ", 1)), "cite（作業ツリーで引ける字列）が空"),
                 (reply(("件数\0", 1)), "NUL が入っている"),
                 ({**GOOD, "findings": ["件数は 3 件"]}, "素の文字列は受け取らない"))
        for got, why in cases:
            with self.subTest(why=why):
                self.setUp()
                self.assertTrue(self.intake()["due"])
                self.prep()
                done = self.accept(got)
                self.assertEqual(done["ok"], not why, done)
                if why:
                    self.assertIn("観点 purpose-review: ", done["reason"])
                    self.assertIn(why, done["reason"])
                else:
                    self.assertEqual(done, {"ok": True, "done": True, "reason": ""})
                    accepted = json.loads((self.run.artifacts / "accepted.json").read_text(encoding="utf-8"))
                    self.assertEqual(accepted["reply"], GOOD)

    def test_an_unresolvable_review_version_is_rejected_not_passed(self):
        self.assertTrue(self.intake()["due"])
        self.prep()
        path = self.run.artifacts / "intake.json"   # accept が固めた版を読むのは入口の控え（view.json は人が読む写し）
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["view"]["review_rev"] = "0123456789abcdef0123456789abcdef01234567"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        done = self.accept(GOOD)
        self.assertFalse(done["ok"], done)
        self.assertIn("採点する版 0123456789ab を解決できない", done["reason"])

    def test_a_good_reply_reaches_the_material(self):
        self.assertTrue(self.intake()["due"])
        self.prep()
        self.assertEqual(self.accept(GOOD), {"ok": True, "done": True, "reason": ""})
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"], fin["reason"]), (True, "ran", ""))
        self.assertEqual(fin["material"], {"type": "archon_artifact", "run_id": kit.RUN_ID, "path": "material.json"})
        self.assertEqual(fin["report"], ["観点 purpose-review: ran", "  - 判定: 狭めている（根拠 1 件）",
                                         "  - 根拠: 目的が件数の数えに狭まっている（件数は 3 件 が 1 行）"])
        doc = kit.load(NAME, "viewpoint").materialkit.read(self.run.artifacts / "material.json")
        self.assertEqual((doc["role"], doc["status"], doc["materials"], doc["reply"]), (NAME, "ran", {}, GOOD))

    def test_a_verdict_without_findings_is_fine_when_it_finds_no_problem(self):
        self.intake()
        self.prep()
        ok = reply(verdict="問題なし", reason="目的は実装の範囲より広いままだ")
        self.assertTrue(self.accept(ok)["ok"])
        fin = self.finish()
        self.assertEqual(fin["report"], ["観点 purpose-review: ran", "  - 判定: 問題なし（根拠 0 件）"])
        self.assertEqual(self.material()["reply"], ok)

    def test_three_rejections_give_up(self):
        self.intake()
        bad = reply()
        dones = []
        for _ in range(3):
            self.prep()
            dones.append(self.accept(bad)["done"])
        self.assertEqual(dones, [False, False, True])
        fin = self.finish()
        self.assertEqual((fin["ok"], fin["status"]), (False, "gave_up"))
        self.assertIn("3 回とも受け付けで拒まれた", fin["reason"])
        doc = self.material()
        self.assertEqual((doc["reply"], doc["materials"]), (None, {}))

    def test_other_sources_do_not_start_the_role(self):
        for source in (PR, PLAN):
            with self.subTest(source=source):
                self.setUp()
                got = self.intake(purpose=purpose(source))
                self.assertFalse(got["due"])
                self.assertTrue(got["reason"].startswith(f"目的テキストの出典が {source}——"), got["reason"])
                fin = self.finish()
                self.assertEqual((fin["ok"], fin["status"], fin["reason"]), (True, "skipped", got["reason"]))
                doc = self.material()
                self.assertEqual((doc["reply"], doc["materials"]), (None, {}))

    def test_missing_purpose_does_not_start_the_role(self):
        got = self.intake(purpose="null")
        self.assertFalse(got["due"])
        self.assertTrue(got["reason"].startswith("目的の文が渡されていない"), got["reason"])
        self.assertEqual(self.finish()["status"], "skipped")

    def test_the_entry_mark_does_not_stop_the_role(self):
        """写す元 DueCase: 差分が空で entry の在る run でも、出典が writer の要約なら回す（この観点は入口の印を読まない）"""
        got = self.intake(entry="人の依頼（試験）")
        self.assertTrue(got["due"])
        self.assertEqual(json.loads((self.run.artifacts / "view.json").read_text(encoding="utf-8"))["changed_files"], [])

    def test_unreadable_purpose_fails_with_the_port_name(self):
        for raw in ("{not json", json.dumps({"purpose_text": "x", "source": "どこか"})):
            with self.subTest(raw=raw):
                self.setUp()
                self.assertFalse(self.intake(purpose=raw)["due"])
                fin = self.finish()
                self.assertEqual((fin["ok"], fin["status"]), (False, "failed"))
                self.assertIn("purpose", fin["reason"])
                self.assertEqual(self.material()["materials"], {})

    def test_prep_without_intake_fails_the_node(self):
        self.assertIn("intake.json", self.run.failing("role_prep", f"{LOOP}.{NAME}-prep"))

    def test_the_role_changing_the_tree_is_refused(self):
        self.intake()
        self.prep()
        (self.run.repo / "README.md").write_text("書き換えた\n", encoding="utf-8")
        got = self.accept(GOOD)
        self.assertFalse(got["ok"])
        self.assertIn("読むだけの役が作業ツリーを変えた", got["reason"])

    def test_prompt_carries_the_values_and_the_rejection(self):
        self.intake(lang="Japanese")
        got = self.prep()["prompt"]
        self.assertIn(TEXT, got)
        self.assertIn("Revision to read: " + json.loads((self.run.artifacts / "view.json").read_text(encoding="utf-8"))["review_rev"], got)
        self.assertIn("`問題なし` (no problem) or `狭めている` (narrowed)", got)
        self.assertIn("findings` row in Japanese.", got)
        self.assertNotIn("new conversation", got, "later rounds resume the same conversation")
        self.assertNotIn("Why your previous answer was rejected", got)
        self.assertFalse(self.accept(reply())["ok"])
        again = self.prep()["prompt"]
        self.assertTrue(again.startswith("## Why your previous answer was rejected"), again[:80])
        self.assertIn("findings が空", again)
        self.assertTrue((self.run.artifacts / f"{NAME}-prompt-2.md").is_file())

    def test_braces_in_the_purpose_text_are_kept(self):
        self.intake(purpose=purpose(text="PATCH /threads/{id} を {a, b} で $x と受ける"))
        self.assertIn("PATCH /threads/{id} を {a, b} で $x と受ける", self.prep()["prompt"])

    def test_included_block_writes_in_its_own_place(self):
        self.run.script("intake", "judge__purpose-review-run__intake", base="", purpose=purpose(), entry="", lang="")
        self.run.script("role_prep", f"judge__purpose-review-run__{LOOP}.{NAME}-prep")
        self.assertTrue((self.run.artifacts / "judge" / "purpose-review-run" / f"{NAME}-prompt-1.md").is_file())
        fin = self.run.script("finish", "judge__purpose-review-run__finish")
        self.assertEqual(fin["material"]["path"], "judge/purpose-review-run/material.json")


class ViewpointCase(unittest.TestCase):
    def setUp(self):
        self.vp = kit.load(NAME, "viewpoint")
        self.mk = self.vp.materialkit

    def test_declaration(self):
        self.assertEqual((self.vp.MATERIALS, self.vp.GUARDED, self.vp.NA, self.vp.NA_PARAGRAPH),
                         ((), True, "never", False))

    def test_due_follows_the_source_word(self):
        empty = self.mk.View(".", "b", "r", "d", (), "c", "", 0)
        row = lambda source: {"purpose_text": "x", "source": source, "known_weaknesses": [], "source_files": []}
        self.assertTrue(self.vp.due(empty, {"purpose": row(WRITER), "entry": "e"}).run)
        self.assertFalse(self.vp.due(empty, {"purpose": row(PR)}).run)
        self.assertFalse(self.vp.due(empty, {"purpose": row(PLAN)}).run)
        self.assertFalse(self.vp.due(empty, {"purpose": None}).run)
        self.assertEqual(self.vp.fill(empty, {}, None), {})

    def test_report_lines_without_a_reply_are_empty(self):
        self.assertEqual(self.vp.report_lines({"reply": None}), [])
        self.assertEqual(self.vp.materials_of(GOOD), {})

    def test_words_match_the_yaml_and_the_other_blocks(self):
        doc = yaml.safe_load((BLOCK / f"works-factory-{NAME}.yaml").read_text(encoding="utf-8"))
        loop = next(n for n in doc["nodes"] if n["id"] == LOOP)["loop_group"]["nodes"]
        role = next(n for n in loop if n["id"] == NAME)
        self.assertEqual(list(self.vp.VERDICTS), role["output_format"]["properties"]["verdict"]["enum"])
        schema = json.loads((kit.SHARED / "schemas" / "purpose.schema.json").read_text(encoding="utf-8"))
        self.assertIn(self.vp.WRITER_SOURCE, schema["properties"]["source"]["enum"])
        steps = kit.load("purpose", "steps")
        self.assertEqual(self.vp.WRITER_SOURCE, steps.WRITER_SOURCE)
        self.assertEqual(schema["properties"]["source"]["enum"], list(steps.SOURCES))


class ShapeCase(unittest.TestCase):
    """YAML の揃い（block の形の検査は tests/layers/test_block_shape.py）"""

    def setUp(self):
        doc = yaml.safe_load((BLOCK / f"works-factory-{NAME}.yaml").read_text(encoding="utf-8"))
        self.nodes = {n["id"]: n for n in doc["nodes"]}
        self.body = {n["id"]: n for n in self.nodes[LOOP]["loop_group"]["nodes"]}

    def test_loop_bound_matches_the_give_up_count(self):
        import rolekit
        self.assertEqual(self.nodes[LOOP]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER)

    # 今の判定の purpose-review の役の起こし方（tests/workflows/test_judge.py の ROLES["purpose-review"] の行と、
    # workflows/judge/works-factory-judge.yaml の錨 read_launch を、作り直しの時に字で写した物）
    LAUNCH = {"model": "@wf-judge-materials", "settingSources": ["user"], "allowed_tools": ["Read", "Grep", "Glob"],
              "sandbox": {"enabled": True, "allowUnsandboxedCommands": False}, "idle_timeout": 1728000000,
              "mutates_checkout": False, "retry": {"max_attempts": 2, "on_error": "all"}}

    def test_launch_matches_the_judge_role(self):
        import launchgroups
        role = self.body[NAME]
        self.assertEqual({k: role.get(k) for k in self.LAUNCH}, self.LAUNCH)
        self.assertEqual(launchgroups.default_of(role["model"]), ("sonnet", "medium"))

    def test_the_reply_shape_is_the_current_one(self):
        shape = self.body[NAME]["output_format"]
        self.assertEqual(shape["required"], ["verdict", "reason", "findings"])
        row = shape["properties"]["findings"]["items"]
        self.assertEqual((row["required"], row["additionalProperties"]), (["text", "cite", "hits"], False))
        self.assertEqual(row["properties"]["hits"], {"type": "integer", "minimum": 0})


if __name__ == "__main__":
    unittest.main()
