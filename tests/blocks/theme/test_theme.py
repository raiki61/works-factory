"""設計の案の書き手の block を、script を子のプロセスで回して確かめる（docs/design/theme.md の 9 章）。

始めの記録の無い使い捨ての run directory と git のリポジトリ（AGENTS.md と作り変える docs/rules.md を commit した物）で、port の値だけを
渡し、intake → write_prep → 台本の返答 → write_accept → finish と回す。受け付けの照らし（4.4 と 6.2）はどれも、全部通る設計の案を 1 か所
だけ崩して拒まれることで縛る。YAML と形のファイルの揃いも見る。筋書きを Archon の workflow test で回すのは tests/layers/test_block_shape.py。
"""
import copy
import json
import unittest

import yaml

from tests.bin.gitkit import git
from tests.blocks import kit
from tests.blocks.theme import values

BLOCK = kit.BLOCKS / "theme"
PORTS = ["theme", "prior", "prior_design", "answers", "world_rows", "policy", "recorded", "base", "lang"]


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def nodes(doc) -> dict:
    out, stack = {}, list(doc["nodes"])
    while stack:
        node = stack.pop()
        out[node["id"]] = node
        stack += (node.get("loop_group") or {}).get("nodes") or []
    return out


def strip(shape):
    if isinstance(shape, dict):
        return {k: strip(v) for k, v in shape.items() if k != "description"}
    if isinstance(shape, list):
        return [strip(v) for v in shape]
    return shape


class _Case(unittest.TestCase):
    def setUp(self):
        self.run = kit.Run(self, "theme")
        repo = self.run.repo
        (repo / "docs").mkdir()
        (repo / "AGENTS.md").write_text(values.AGENTS_MD, encoding="utf-8")
        (repo / "docs" / "rules.md").write_text(values.RULES_MD, encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "base")
        self.theme = self.run.artifacts.parent / "theme.md"
        self.theme.write_text(values.THEME_MD, encoding="utf-8")
        self.steps = kit.load("theme", "steps")   # lib/ を sys.path に足す（kit.returned が形の照らしを読む）

    def intake(self, **inputs):
        return self.run.script("intake", **{"theme": str(self.theme), "answers": dump(values.ANSWERS), **inputs})

    def prep(self, prev=""):
        return self.run.script("write_prep", prev=prev)

    def accept(self, reply=None, fix_reply=None):
        return self.run.script("write_accept", reply="" if reply is None else dump(reply), fix_reply="" if fix_reply is None else dump(fix_reply))

    def finish(self):
        return kit.returned("theme", self.run.script("finish"))

    def folder(self, k=1):
        return self.run.artifacts / f"r{k}"

    def rejected(self, reply, **inputs) -> str:
        self.assertTrue(self.intake(**inputs)["due"])
        got = self.accept(reply)
        self.assertFalse(got["ok"], got)
        return got["reason"]


class RoundTest(_Case):
    def test_a_proposal_that_passes_every_check_is_returned_by_pointer_with_its_md(self):
        """全部通る設計の案は design.json と design.md に置かれ、出口が pointer で返す。md は問いを MADR の並びで描く"""
        self.assertEqual(self.intake(), {"due": True, "round": 1, "reason": ""})
        built = self.prep()
        self.assertFalse(built["resubmit"])
        self.assertIn("You are the design writer.", built["prompt"])
        self.assertIn("H1 (owner_words): Short files are easier to read.", built["prompt"])
        self.assertIn("   5  The owner wants each rule callable on its own.", built["prompt"])
        self.assertEqual(self.accept(values.reply()), {"ok": True, "done": True, "give_up": False, "reason": ""})
        out = self.finish()
        self.assertEqual((out["ok"], out["status"]), (True, "ok"))
        self.assertEqual(out["design"]["path"], "r1/design.json")
        md = (self.folder() / "design.md").read_text(encoding="utf-8")
        self.assertLess(md.index("### Q1"), md.index("案 A1"))
        self.assertLess(md.index("代償"), md.index("推し: A1"))

    def test_the_round_is_one_more_than_the_passes_of_the_record(self):
        """周の番号は往復の記録の往復の数 + 1 で、周ごとのフォルダに分かれる（同じ place を何周も使う line の loop で拒否の数えが混ざらない）"""
        prior = {"passes": [{"pass": 1, "blocks": [], "faces": []}, {"pass": 2, "blocks": [], "faces": []}]}
        self.assertEqual(self.intake(prior=dump(prior))["round"], 3)
        self.assertTrue((self.folder(3) / "intake.json").is_file())

    def test_a_missing_theme_does_not_wake_the_writer(self):
        got = self.intake(theme=str(self.theme.parent / "none.md"))
        self.assertFalse(got["due"])
        out = self.finish()
        self.assertEqual((out["ok"], out["status"], out["design"]), (False, "failed", None))

    def test_three_rejections_give_up(self):
        """3 回目の拒否で done・give_up になり、出口は gave_up と最後の拒否を返す（keep-essence の 4）"""
        self.intake()
        bad = values.reply()
        bad["asks"][0]["pick"] = "A9"
        for n in (1, 2, 3):
            got = self.accept(bad)
            self.assertEqual((got["ok"], got["done"]), (False, n == 3))
        out = self.finish()
        self.assertEqual(out["status"], "gave_up")
        self.assertIn("A9", out["reason"])

    def test_a_resubmission_returns_only_the_rejected_fields(self):
        """拒まれた後は出し直しの役を起こし、返した欄だけを前の答えと合わせてから全体を照らす"""
        self.intake()
        bad = values.reply()
        bad["asks"][0]["pick"] = "A9"
        self.assertFalse(self.accept(bad)["ok"])
        self.assertEqual(self.prep(prev="false"), {"prompt": "", "resubmit": True})
        fix = self.run.script("fix_prep")["prompt"]
        self.assertIn("candidate-theme.json", fix)
        self.assertIn("A9", fix)
        got = self.accept(fix_reply={"asks": values.reply()["asks"]})
        self.assertTrue(got["ok"], got)


class AcceptTest(_Case):
    """受け付けの照らし（docs/design/theme.md の 4.4 の 1〜9 と 6.2 の 1〜4）。全部通る案を 1 か所だけ崩す"""

    def check(self, change, words, **inputs):
        reply = values.reply()
        change(reply)
        reason = self.rejected(reply, **inputs)
        self.assertIn(words, reason)

    def test_1_shape(self):
        self.check(lambda r: r["asks"][0]["options"].pop(), "形 shared:theme-design.schema.json に合わない")

    def test_2_named_lines_exist(self):
        self.check(lambda r: r["current"][0].update(where="AGENTS.md:40"), "AGENTS.md:40")
        self.check(lambda r: r["decided"][0].update(by="the rules"), "decided の R1 の by に <パス>:<行> の名指しが無い")

    def test_3_pick_is_an_option(self):
        self.check(lambda r: r["asks"][0].update(pick="A3"), "pick A3 が案の id")

    def test_3_ask_text_has_no_run_refs(self):
        """問いの文は設計の段の承認ノードに字のまま載るので、<パス>:<行> と <名>[<番号>] を拒む（共通の断片 plain-ask）"""
        self.check(lambda r: r["asks"][0].update(ask="Should AGENTS.md:3 stay?"), "asks Q1 の ask: 初見の読み手が解けない")
        self.check(lambda r: r["asks"][0]["options"][1].update(cost="parts[0] loses its entry."), "asks Q1 の案 A2 の cost")

    def test_5_reuse_points_at_current(self):
        self.check(lambda r: r["reuse"][0]["existing"].append("N7"), "existing N7 が current の id に無い")
        self.check(lambda r: r["reuse"][0].update(part="D9"), "reuse の part D9 が parts の id に無い")

    def test_6_rework_is_covered(self):
        self.check(lambda r: r["inventory"].pop(0), "空でない行 1 を覆っていない")
        self.check(lambda r: r["inventory"][1].update(lines="1-4"), "が docs/rules.md:1-1 と重なる")
        self.check(lambda r: r["inventory"][2].update(lines="6-9"), "ファイルの行の外")
        self.check(lambda r: r["narrows"].clear(), "narrows に docs/rules.md:6-6 を名指す行が無い")
        self.check(lambda r: r["narrows"][0].update(what="docs/rules.md:6-60 is dropped."), "narrows に docs/rules.md:6-6 を名指す行が無い")
        self.check(lambda r: r["inventory"][2].update(why=" "), "は drop なのに why が空")
        self.check(lambda r: r["inventory"][1].update(dest="D9"), "dest 'D9' が parts か changes の id に無い")
        self.check(lambda r: r["changes"][0].update(where="docs/none.md"), "docs/none.md が起点の木")
        self.check(lambda r: r["changes"][0].update(where="the rules file"), "がファイルのパス（<パス> か <パス>:<行>）でない")

    def test_6_rework_is_counted_at_the_base(self):
        """作り変えの照らしは起点の版 base の行を数える（HEAD で足した行は覆わなくてよい）"""
        base = git(self.run.repo, "rev-parse", "HEAD")
        (self.run.repo / "docs" / "rules.md").write_text(values.RULES_MD + "4. A new rule.\n", encoding="utf-8")
        git(self.run.repo, "commit", "-qam", "more")
        self.check(lambda r: None, "空でない行 7 を覆っていない")
        self.assertTrue(self.intake(base=base)["due"])
        self.assertTrue(self.accept(values.reply())["ok"])

    def test_ids_are_one_per_row_and_changes_point_at_parts(self):
        """欄ごとの id が重ならない・changes の parts が parts の id を指す（名指しの先を 1 つに決める）"""
        self.check(lambda r: r["current"][1].update(id="N1"), "current の id N1 が 2 行に在る")
        self.check(lambda r: r["changes"][0]["parts"].append("D9"), "changes C1 の parts D9 が parts の id に無い")

    def test_7_block_answers_answer_the_holes(self):
        prior = {"outcome": "again", "passes": [{"pass": 1, "blocks": ["k-hole"], "faces": [
            {"key": "k-hole", "kind": "design", "where": "D1", "why": "The split loses the shared heading."}]}]}
        self.check(lambda r: None, "block の key k-hole への答えが無い", prior=dump(prior))

    def test_8_every_answer_is_used(self):
        self.check(lambda r: r["answers_used"].clear(), "answers_used に人の答え H1 の行が無い")
        self.check(lambda r: r["answers_used"][0].pop("applied"), "applied も declined_why も無い")

    def test_9_owner_premises_point_at_what_a_person_said(self):
        self.check(lambda r: r["premises"][0].update(**{"from": "theme:2"}), "テーマの md の空でない行に当たらない")
        self.check(lambda r: r["premises"][1].update(**{"from": "H4"}), "人の答えの id（H<n>）でもテーマの md の行")


class ShapeTest(unittest.TestCase):
    def setUp(self):
        self.steps = kit.load("theme", "steps")
        self.doc = yaml.safe_load((BLOCK / "works-factory-theme.yaml").read_text(encoding="utf-8"))
        self.nodes = nodes(self.doc)

    def test_inputs_are_the_ports_of_the_design(self):
        self.assertEqual(list(self.doc["inputs"]), PORTS)

    def test_the_writer_schema_is_the_shared_shape(self):
        """書き手と出し直しの役の型は同じ物で、形 shared:theme-design の写し（根の required だけ空。#832）"""
        shared = json.loads((kit.SHARED / "schemas" / "theme-design.schema.json").read_text(encoding="utf-8"))
        writer, fixer = self.nodes["theme-writer"]["output_format"], self.nodes["theme-writer-fix"]["output_format"]
        self.assertEqual(writer, fixer)
        self.assertEqual(writer["required"], [])
        self.assertEqual(strip(writer["properties"]), strip(shared["properties"]))
        self.assertEqual(tuple(shared["required"]), kit.load("theme", "files").REQUIRED)

    def test_the_loop_gives_up_in_the_body(self):
        self.assertEqual(self.nodes["write-loop"]["loop_group"]["max_iterations"], self.steps.rolekit.GIVE_UP_AFTER)

    def test_no_node_is_named_like_the_include(self):
        """line は この block を include の id theme で取り込む（docs/design/README.md の 7.1 の 13）"""
        self.assertNotIn("theme", self.nodes)


if __name__ == "__main__":
    unittest.main()
