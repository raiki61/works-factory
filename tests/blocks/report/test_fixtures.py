"""報告の block の筋書き（fixtures/*.stubs.yaml）の結末の語を、止めた Archon の dry-run の trace の出口の出力で見る。YAML と lib・共通の形の
写しの揃いも照らす。全部の筋書きが通ることと validate は tests/layers/test_block_shape.py の ArchonCase が見る。"""
import json
import unittest

import yaml

from tests import archon
from tests.blocks import kit
from tests.blocks.report import base

M = base.src()
import report  # noqa: E402  lib/
import rolekit  # noqa: E402  lib/

BLOCK = base.BLOCK
DOC = yaml.safe_load((BLOCK / "works-factory-report.yaml").read_text(encoding="utf-8"))
NODES = {n["id"]: n for n in DOC["nodes"]}
BODY = {n["id"]: n for n in NODES["write-loop"]["loop_group"]["nodes"]}


class FixtureCase(unittest.TestCase):
    def test_scenarios_reach_their_words(self):
        """exec-code の筋書きの出口の出力（dry-run の trace）が、それぞれの結末を返す"""
        want = {"standalone": ("fixed", True), "no-ai-report": ("record_invalid", False), "stopped-by-request": ("stopped_by_request", True),
                "cold-gave-up": ("fixed", False)}
        for name, (word, human) in want.items():
            with self.subTest(name), archon.blocks_tree(["report"]) as tree:
                fixture = kit.fixture("report", name)
                stubs = tree.parent / "stubs.yaml"
                stubs.write_text(yaml.safe_dump({k: v for k, v in fixture.items() if k not in ("fixture", "exec-code")}, allow_unicode=True),
                                 encoding="utf-8")
                args = [arg for k, v in (fixture["fixture"].get("inputs") or {}).items() for arg in ("--input", f"{k}={v}")]
                done = archon.archon(tree, "workflow", "run", "works-factory-report", "--dry-run", "--exec-code", "--stubs", str(stubs),
                                     "--json", *args, "--cwd", str(tree))
                trace = {n["nodeId"]: n for n in json.loads(done.stdout)["trace"]}
                out = json.loads(trace["finish"]["output"])
                self.assertEqual((out["outcome"], out["human"] is not None), (word, human), done.stdout)
                self.assertIn("機械の報告: ", out["report"][2])
                if name == "cold-gave-up":
                    self.assertIn("write-accept", trace)

    def test_every_scenario_stubs_only_ai_nodes(self):
        ai = {"write", "cold"}
        for path in (BLOCK / "fixtures").glob("*.stubs.yaml"):
            with self.subTest(path.name):
                doc = yaml.safe_load(path.read_text(encoding="utf-8"))
                stubbed = set(doc) - {"fixture", "exec-code"}
                self.assertLessEqual(stubbed, ai, "script の node は本当に走らせる（AI の node の台本だけ）")
                self.assertTrue(doc["exec-code"])
                self.assertLessEqual(set(doc["fixture"].get("inputs") or {}), set(DOC["inputs"]))


class ShapeCase(unittest.TestCase):
    """YAML と src の揃い"""

    def test_returns_and_outcome_words(self):
        self.assertEqual((DOC["returns"], DOC["outcome_field"]), ("finish", "ok"))
        props = NODES["finish"]["output_format"]["properties"]
        self.assertEqual(tuple(props["outcome"]["enum"]), report.OUTCOMES)
        self.assertEqual(set(props), {"ok", "outcome", "stop_reason", "machine", "human", "detail", "next_request", "prior_failures", "report"})

    def test_loop_bound_matches_the_give_up_count(self):
        """輪が諦めの回より先に尽きない（書き手のループを飛ばす when は筋書き no-ai-report が見る）"""
        self.assertEqual(NODES["write-loop"]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER)

    def test_facts_fields_match_the_defaults(self):
        facts = json.loads((kit.SHARED / "schemas" / "facts.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(facts["properties"]), set(M.facts_in.DEFAULTS), "欄と既定は同じ並び")


if __name__ == "__main__":
    unittest.main()
