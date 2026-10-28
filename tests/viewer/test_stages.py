"""段の表（viewer/stages.json）と段ごとの集計（viewer/src/stages.py。docs/design/viewer.md の 6.8 と照らしの 8）。

- 今の木の line の一番上のノードは、どれも段の表のちょうど 1 つの段に入り、表のノードはどれも line に在る（line にノードを足して
  表に足さなければ赤。表に残った古い id も赤）
- 出来事は道の頭のノードで段に寄せ、段ごとに状態・時間・人の待ち・AI の手番・費用・トークンを集める。繰り返しの器は数えない
- どの道でも走る合流のノード（trigger_rule を持ち when の無い物）だけが走った段は「飛んだ」。最後に走った段の前で、間の段が
  全部飛んだ段を「止まった所」にする
- line でない run は段に集めない

試験は小さな作りと run の記録を手で組む。
"""
import unittest

from viewer import flowview
from viewer.src import stages

NODES = [node for stage in stages.TABLE["stages"] for node in stage["nodes"]]
THROUGH = ("fix-in", "collect", "report", "sweep-children", "result")


def number(node: str) -> int:
    return next(n for n, stage in enumerate(stages.TABLE["stages"], 1) if node in stage["nodes"])


def line(ids: list[str]) -> dict:
    items = [{"id": i, "trigger": "none_failed_min_one_success" if i in THROUGH else "", "when": ""} for i in ids]
    return {stages.TABLE["graph"]: {"name": "works-factory-line", "items": items}}


def event(tokens, kind="exec", start="2026-10-25T01:00:00.000Z", end="2026-10-25T01:00:01.000Z", cost=0.0, **more):
    return {"tokens": tokens, "kind": kind, "start": start, "end": end, "status": "ok", "cost": cost, **more}


class StagesCase(unittest.TestCase):
    def test_every_line_node_is_in_exactly_one_stage(self):
        self.assertEqual(stages.check(flowview.tree_shape()["graphs"]), [])

    def test_a_new_line_node_and_a_stale_id_are_red(self):
        got = stages.check(line([*NODES[1:], "new-node"]))
        self.assertEqual(len(got), 2)
        self.assertTrue(any("new-node" in line for line in got) and any(NODES[0] in line for line in got))

    def test_run_is_summed_by_stage(self):
        usage = {"input": 100, "output": 7, "cacheRead": 60, "cacheWrite": 30}
        events = [
            event(["start"], end="2026-10-25T01:00:20.000Z"),
            event(["judge", "diagnose"], kind="agent", cost=1.5, usage=usage, turns=4,
                  start="2026-10-25T01:01:00.000Z", end="2026-10-25T01:03:00.000Z"),
            event(["plan-rounds"], kind="loop_group", start="2026-10-25T01:03:00.000Z", end="2026-10-25T01:10:00.000Z"),
            event(["plan-rounds", "plan"], kind="agent", cost=2.0, usage=usage, turns=3,
                  start="2026-10-25T01:03:00.000Z", end="2026-10-25T01:05:00.000Z"),
            event(["plan-rounds", "gate-design"], kind="wait", start="2026-10-25T01:05:00.000Z", end="2026-10-25T01:10:00.000Z"),
            event(["fix-in"], start="2026-10-25T01:10:01.000Z", end="2026-10-25T01:10:02.000Z"),
            event(["collect"], start="2026-10-25T01:11:00.000Z", end="2026-10-25T01:12:00.000Z"),
        ]
        skipped = [{"tokens": [node]} for node in ("fix", "parallel-pr-after", "eyes", "merge-seal")]
        data = {"shape": {"graphs": line(NODES)}, "run": {"graph": "works-factory-line", "events": events, "skipped": skipped}}
        stages.attach(data)
        got = data["stages"]
        states = {stage["name"]: row["state"] for stage, row in zip(got["table"], got["run"])}
        self.assertEqual([states[stages.TABLE["stages"][number(node) - 1]["name"]] for node in
                          ("start", "theme-world", "test-gate-base", "judge", "plan-rounds", "gate-before-fix", "fix", "judged",
                           "eyes", "merge-seal", "collect")],
                         ["ok", "none", "none", "ok", "ok", "none", "skipped", "skipped", "skipped", "skipped", "ok"])
        self.assertEqual(got["stop"], number("plan-rounds"))
        plan = got["run"][number("plan-rounds") - 1]
        self.assertEqual({key: plan[key] for key in ("seconds", "wait", "ai_seconds", "ai", "steps", "turns", "cost")},
                         {"seconds": 420.0, "wait": 300.0, "ai_seconds": 120.0, "ai": 1, "steps": 2, "turns": 3, "cost": 2.0})
        self.assertEqual(plan["tokens"], {**usage, "fresh": 10, "odd": 0})
        self.assertEqual([e["stage"] for e in events], [number(e["tokens"][0]) for e in events])
        self.assertEqual([(e["role"], e["through"]) for e in events],
                         [("machine", False), ("ai", False), ("group", False), ("ai", False), ("wait", False), ("machine", True), ("machine", False)])
        self.assertEqual(got["loose"], [])

    def test_a_run_of_another_graph_is_not_summed(self):
        data = {"shape": {"graphs": line(NODES)}, "run": {"graph": "works-factory-chain", "events": [event(["x"])], "skipped": []}}
        stages.attach(data)
        self.assertEqual((data["stages"]["run"], data["stages"]["stop"], len(data["stages"]["table"])), (None, None, len(stages.TABLE["stages"])))


if __name__ == "__main__":
    unittest.main()
