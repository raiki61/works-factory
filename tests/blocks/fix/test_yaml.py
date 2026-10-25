"""修正の block（workflows/fix/works-factory-fix.yaml）の形（docs/design/fix.md の 14.2 の test_yaml.py）: loop の上限が定数と同じ・柵 nodes-ok の
結び・all_done の node・会話を継ぐ役の直前の層・修正役の会話の続きと答えの役の切り離し・役の起こし方が今の YAML と同じ・自分を起こす組の node・指示の受け渡し"""
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

WRITERS = ("tdd-close", "pin", "tidy", "static", "variant", "remove", "pin-ruled", "tidy-ruled", "static-ruled", "variant-ruled",
           "remove-ruled")   # 型ごとの書き手（今の修正役 fixer・fix-ruled を型ごとに分けた物。docs/plans/2026-10-25-fix-weapons-stage1-b.md の 1）
AI_NODES = (*WRITERS, "consult-answer", "ruled-consult-answer", "tdd", "tdd-new", "ruler", "clash-fix", "clash-ruled")
ADDED_AI_NODES = ("suite-fix", "route")   # 作り直しの後に足した役（壊れた起動スクリプトの書き直し。#836・docs/design/fix.md の 19。振り分けの役。
#                                         今の TDD の役の振り分けの段を輪の外へ出した物。docs/plans/2026-10-24-fix-weapons.md の 4.1 の 3）
WRITE_TOOLS = {"Edit", "Write", "Bash", "NotebookEdit", "Agent"}
LAUNCH = ("model", "settingSources", "allowed_tools", "sandbox", "skills", "idle_timeout", "retry", "mutates_checkout", "context")


def top(doc=DOC) -> dict:
    return {n["id"]: n for n in doc["nodes"]}


def every(doc=DOC) -> dict:
    """node を loop_group の中まで（入れ子の輪も。id → node）"""
    out = {}

    def walk(nodes):
        for n in nodes:
            out[n["id"]] = n
            walk((n.get("loop_group") or {}).get("nodes") or [])
    walk(doc["nodes"])
    return out


def inner(loop) -> dict:
    """輪の本体の node を入れ子の輪の中まで（id → node）"""
    return every({"nodes": loop["loop_group"]["nodes"]})


def is_ai(node) -> bool:
    return "prompt" in node and "script" not in node


class LimitsCase(unittest.TestCase):
    def test_loop_limits_match_the_constants(self):
        tdd = kit.load("fix", "tdd")
        consult = kit.load("fix", "consult")
        writers = kit.load("fix", "writers")
        t = every()
        self.assertEqual(t["tdd-loop"]["loop_group"]["max_iterations"], tdd.MAX_ITERATIONS)
        self.assertEqual(t["fix-loop"]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER + consult.BUDGET)
        self.assertEqual(t["fix-ruled-loop"]["loop_group"]["max_iterations"], rolekit.GIVE_UP_AFTER + consult.BUDGET)
        self.assertEqual(t["writers-loop"]["loop_group"]["max_iterations"], len(writers.SEQUENCE["first"]))   # 1 周に型 1 つ
        self.assertEqual(t["ruled-writers-loop"]["loop_group"]["max_iterations"], len(writers.SEQUENCE["ruled"]))
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
            body = inner(loop)
            for nid, m in body.items():
                if not is_ai(m):
                    continue
                with self.subTest(node=nid):
                    ref = m["prompt"]
                    self.assertRegex(ref, r"^\$[a-z-]+\.output\.prompt$")
                    self.assertIn(ref[1:].split(".")[0], body, "同じ loop の prep")
        self.assertEqual({nid for nid, n in every().items() if is_ai(n)}, set(AI_NODES) | set(ADDED_AI_NODES))


class ConversationCase(unittest.TestCase):
    """fresh_context: false の loop で前の周の会話を継ぐ役の直前の層は 1 つの node（2 つ以上の層は Archon が会話を切る）"""

    def test_no_wide_layer_right_before_a_continuing_role(self):
        for loop in (n for n in every().values() if "loop_group" in n and n["loop_group"].get("fresh_context") is False):
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

    def test_fixers_continue_their_own_conversation(self):
        """13.3 の 1（#833）: 修正の輪の次の周の修正役は、前の周の修正役の会話を継ぐ。止めた Archon は輪の周の最後に走った AI の node の
        会話を次の周へ渡すので、修正の輪の本体に直に置く AI の node は修正役 1 つだけ。相談の答えの役を本体に直に置くと（context: fresh
        でも）、次の周の修正役は答えの役の会話を継ぐ。型ごとの書き手は 1 本の鎖に並び（どの層も node 1 つ）、周ごとに 1 つだけ起きる。
        型が替わる時は外の輪（fresh_context: true）の次の周で内の輪が 1 周目から起きるので、型どうしは会話を分け合わない"""
        writers = kit.load("fix", "writers")
        for outer, loop, pass_ in (("writers-loop", "fix-loop", "first"), ("ruled-writers-loop", "fix-ruled-loop", "ruled")):
            with self.subTest(loop=loop):
                self.assertIs(top()[outer]["loop_group"]["fresh_context"], True)
                self.assertIn(loop, [m["id"] for m in top()[outer]["loop_group"]["nodes"]])
                group = every()[loop]["loop_group"]
                self.assertIs(group["fresh_context"], False)
                self.assertEqual([m["id"] for m in group["nodes"] if is_ai(m)], writers.nodes(pass_))
                for w in writers.nodes(pass_):
                    self.assertNotIn("context", every()[w])

    def test_answerers_start_fresh_in_their_own_loop(self):
        """13.3 の 1（#833）: 相談の答えの役は修正役の会話を継がず、新しい会話で起きる。答えの役は修正の輪の本体の中の、答えの役
        1 つだけを置いた 1 周の輪（fresh_context: true）の中に在る。止めた Archon は輪の 1 周目の AI の node を新しい会話で起こし、
        輪の node の返りは会話を持たないので、外の輪の会話の続きは輪の前の修正役の物のまま（dag-executor.ts の executeLoopGroupNode が
        lastSequentialSession を i === 1 で空にし、runLayers が返りの sessionId の在る node だけで続きを替える）"""
        rules = kit.load("fix", "rules")
        for loop, answerer in (("fix-loop", rules.answer_node("first")), ("fix-ruled-loop", rules.answer_node("ruled"))):
            with self.subTest(loop=loop):
                holders = [m for m in every()[loop]["loop_group"]["nodes"]
                           if answerer in [x["id"] for x in (m.get("loop_group") or {}).get("nodes") or []]]
                self.assertEqual(len(holders), 1, "答えの役は修正の輪の本体の輪の中")
                group = holders[0]["loop_group"]
                self.assertEqual([x["id"] for x in group["nodes"]], [answerer])
                self.assertEqual((group["max_iterations"], group["fresh_context"]), (1, True))
                self.assertNotIn("context", every()[answerer])


class RolesCase(unittest.TestCase):
    """役の起こし方（模型・道具・sandbox・skills・読むだけの印）は今の YAML と同じ。読むだけの役は書く道具を持たない"""

    def test_launch_keys_match_the_current_yaml(self):
        old, new = every(OLD), every()
        for nid in AI_NODES:
            with self.subTest(node=nid):
                self.assertEqual({k: new[nid].get(k) for k in LAUNCH}, {k: old[nid].get(k) for k in LAUNCH})
                self.assertEqual(new[nid]["output_format"], old[nid]["output_format"])

    def test_the_runner_rewriter_is_launched_like_the_gate_runner_writer(self):
        """起動スクリプトの書き直し役 suite-fix は、試験の関門の書き手 suite-write と同じ群・道具・砂場・期限・返す形で起こす（読むだけの
        印は持たない。Bash を持ち、denyWrite が Archon の家を塞ぐ）"""
        doc = yaml.safe_load((kit.BLOCKS / "test-gate" / "works-factory-test-gate.yaml").read_text(encoding="utf-8"))
        writer = next(m for n in doc["nodes"] for m in [n, *((n.get("loop_group") or {}).get("nodes") or [])] if m["id"] == "suite-write")
        new = every()["suite-fix"]
        for k in ("model", "settingSources", "allowed_tools", "sandbox", "idle_timeout", "retry", "output_format"):
            with self.subTest(key=k):
                self.assertEqual(new.get(k), writer.get(k))
        self.assertNotIn("mutates_checkout", new)

    def test_readers_do_not_write(self):
        for nid in ("ruler", "consult-answer", "ruled-consult-answer"):
            with self.subTest(node=nid):
                n = every()[nid]
                self.assertIs(n["mutates_checkout"], False)
                self.assertFalse(set(n["allowed_tools"]) & WRITE_TOOLS)


if __name__ == "__main__":
    unittest.main()
