"""修正の block（workflows/fix/works-factory-fix.yaml）の形（docs/design/fix.md の 14.2 の test_yaml.py）: loop の上限が定数と同じ・柵 nodes-ok の
結び・all_done の node・会話を継ぐ役の直前の層・役の起こし方が今の YAML と同じ・自分を起こす組の node・指示の受け渡し"""
import pathlib
import sys
import unittest

import yaml

from tests.blocks import kit

ROOT = pathlib.Path(__file__).resolve().parents[3]
DOC = yaml.safe_load((kit.BLOCKS / "fix" / "works-factory-fix.yaml").read_text(encoding="utf-8"))
OLD = yaml.safe_load((ROOT / "workflows" / "fix" / "works-factory-fix.yaml").read_text(encoding="utf-8"))
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))

import rolekit  # noqa: E402

AI_NODES = ("fixer", "fix-ruled", "consult-answer", "ruled-consult-answer", "tdd", "tdd-new", "ruler", "clash-fix", "clash-ruled")
WRITE_TOOLS = {"Edit", "Write", "Bash", "NotebookEdit", "Agent"}
LAUNCH = ("model", "settingSources", "allowed_tools", "sandbox", "skills", "idle_timeout", "retry", "mutates_checkout", "context")


def top(doc=DOC) -> dict:
    return {n["id"]: n for n in doc["nodes"]}


def every(doc=DOC) -> dict:
    out = {}
    for n in doc["nodes"]:
        out[n["id"]] = n
        for m in (n.get("loop_group") or {}).get("nodes") or []:
            out[m["id"]] = m
    return out


def is_ai(node) -> bool:
    return "prompt" in node and "script" not in node


class LimitsCase(unittest.TestCase):
    def test_loop_limits_match_the_constants(self):
        tdd = kit.load("fix", "tdd")
        consult = kit.load("fix", "consult")
        t = top()
        self.assertEqual(t["tdd-loop"]["loop_group"]["max_iterations"], tdd.MAX_ITERATIONS)
        self.assertEqual(t["fix-loop"]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER + consult.BUDGET)
        self.assertEqual(t["fix-ruled-loop"]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER + consult.BUDGET)
        self.assertEqual(t["rule-loop"]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER)
        for loop, accept in (("clash-loop", "clash-accept"), ("clash-ruled-loop", "clash-ruled-accept")):
            with self.subTest(loop=loop):
                self.assertEqual(t[loop]["loop_group"]["max_iterations"], every()[accept]["with"]["limit"])


class WiringCase(unittest.TestCase):
    def test_fence_ties_every_node_but_finish_and_reads(self):
        t = top()
        self.assertEqual(set(t["nodes-ok"]["depends_on"]), set(t) - {"nodes-ok", "finish", "fix-reads"})
        self.assertNotIn("when", t["nodes-ok"])

    def test_only_finish_and_reads_run_after_all(self):
        self.assertEqual({nid for nid, n in every().items() if n.get("trigger_rule") == "all_done"}, {"finish", "fix-reads"})
        self.assertEqual(set(top()["finish"]["depends_on"]), set(top()) - {"nodes-ok", "finish"})

    def test_groups_start_this_block_and_stop_on_a_failed_child(self):
        for nid in ("groups-par", "groups-seq"):
            with self.subTest(node=nid):
                n = top()[nid]
                self.assertEqual(n["workflow"], DOC["name"])
                self.assertEqual(n["fan_out"]["join"], "all_success")
                self.assertEqual(set(n["with"]), {"mode", "from_tree", "out_dir"})

    def test_every_role_prompt_is_its_loop_prep_output(self):
        for loop in (n for n in DOC["nodes"] if "loop_group" in n):
            body = {m["id"]: m for m in loop["loop_group"]["nodes"]}
            for nid, m in body.items():
                if not is_ai(m):
                    continue
                with self.subTest(node=nid):
                    ref = m["prompt"]
                    self.assertRegex(ref, r"^\$[a-z-]+\.output\.prompt$")
                    self.assertIn(ref[1:].split(".")[0], body, "同じ loop の prep")
        self.assertEqual({nid for nid, n in every().items() if is_ai(n)}, set(AI_NODES))


class ConversationCase(unittest.TestCase):
    """fresh_context: false の loop で前の周の会話を継ぐ役の直前の層は 1 つの node（2 つ以上の層は Archon が会話を切る）"""

    def test_no_wide_layer_right_before_a_continuing_role(self):
        for loop in (n for n in DOC["nodes"] if "loop_group" in n and n["loop_group"].get("fresh_context") is False):
            nodes = {m["id"]: m for m in loop["loop_group"]["nodes"]}
            layer = {}
            for nid in nodes:   # YAML の並びは依存の順
                deps = [d for d in nodes[nid].get("depends_on") or [] if d in nodes]
                layer[nid] = 1 + max((layer[d] for d in deps), default=-1)
            for nid, m in nodes.items():
                if not is_ai(m) or m.get("context") == "fresh":
                    continue
                with self.subTest(loop=loop["id"], node=nid):
                    before = [x for x, k in layer.items() if k == layer[nid] - 1]
                    self.assertLessEqual(len(before), 1, before)
                    self.assertEqual([x for x, k in layer.items() if k == layer[nid]], [nid])

    def test_only_tdd_new_starts_fresh(self):
        self.assertEqual({nid for nid, n in every().items() if n.get("context") == "fresh"}, {"tdd-new"})


class RolesCase(unittest.TestCase):
    """役の起こし方（模型・道具・sandbox・skills・読むだけの印）は今の YAML と同じ。読むだけの役は書く道具を持たない"""

    def test_launch_keys_match_the_current_yaml(self):
        old, new = every(OLD), every()
        for nid in AI_NODES:
            with self.subTest(node=nid):
                self.assertEqual({k: new[nid].get(k) for k in LAUNCH}, {k: old[nid].get(k) for k in LAUNCH})
                self.assertEqual(new[nid]["output_format"], old[nid]["output_format"])

    def test_readers_do_not_write(self):
        for nid in ("ruler", "consult-answer", "ruled-consult-answer"):
            with self.subTest(node=nid):
                n = every()[nid]
                self.assertIs(n["mutates_checkout"], False)
                self.assertFalse(set(n["allowed_tools"]) & WRITE_TOOLS)


if __name__ == "__main__":
    unittest.main()
