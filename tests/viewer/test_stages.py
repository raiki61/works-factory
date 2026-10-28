"""段の表（viewer/stages.json）と段ごとの集計（viewer/src/stages.py。docs/design/viewer.md の 6.8 と照らしの 8）。

- 今の木の line の一番上のノードは、どれも段の表のちょうど 1 つの段に入り、表のノードはどれも line に在る（line にノードを足して
  表に足さなければ赤。表に残った古い id も赤）
- 出来事は道の頭のノードで段に寄せ、段ごとに状態・時間・人の待ち・AI の手番・費用・トークンを集める。繰り返しの器は数えない
- 子の run を起こすノードの費用（子の総額）は、子の中の出来事の費用と二重になるので足さない。周の数は繰り返しの周ごとに 1 つ
- トークンの新しく読んだ分は lib/runlog.py の add_tokens と同じ訳（cache の欄が欠けた手番が在れば知れない）。input が cache の和より
  小さい手番は数だけ持ち、新しく読んだ分を出さない
- 段の表の配線の列（wiring。合流・受け渡しだけで段の仕事をしないノード）は、その段のノードの中に在り、どの段にも配線でない
  ノードが在る。配線のノードだけが走った段は「飛んだ」（修正の段が飛んだ run でも fix-in・fixed・judged は走る）。最後に走った段の
  前で、間の段が全部飛んだ段を「止まった所」にする（間が記録に無いだけなら出さない）。最後に走った段が落ちたなら、その段が止まった所
- line でない run は段に集めない

試験は小さな作りと run の記録を手で組む。
"""
import unittest
import unittest.mock

from viewer import flowview
from viewer.src import stages

NODES = [node for stage in stages.TABLE["stages"] for node in stage["nodes"]]


def number(node: str) -> int:
    return next(n for n, stage in enumerate(stages.TABLE["stages"], 1) if node in stage["nodes"])


def line(ids: list[str]) -> dict:
    items = [{"id": i, "trigger": "", "when": ""} for i in ids]
    return {stages.TABLE["graph"]: {"name": "works-factory-line", "items": items}}


def event(tokens, kind="exec", start="2026-10-25T01:00:00.000Z", end="2026-10-25T01:00:01.000Z", cost=0.0, **more):
    return {"tokens": tokens, "kind": kind, "start": start, "end": end, "status": "ok", "cost": cost, "loop": [], **more}


def run_of(events: list[dict], skipped: list[dict]) -> dict:
    data = {"shape": {"graphs": line(NODES)}, "run": {"graph": "works-factory-line", "events": events, "skipped": skipped}}
    stages.attach(data)
    return data


def summed(events: list[dict]) -> list[dict]:
    return run_of(events, [])["stages"]["run"]


class StagesCase(unittest.TestCase):
    def test_every_line_node_is_in_exactly_one_stage(self):
        self.assertEqual(stages.check(flowview.tree_shape()["graphs"]), [])

    def test_a_new_line_node_and_a_stale_id_are_red(self):
        got = stages.check(line([*NODES[1:], "new-node"]))
        self.assertEqual(len(got), 2)
        self.assertTrue(any("new-node" in line for line in got) and any(NODES[0] in line for line in got))

    def test_wiring_outside_its_stage_or_a_stage_of_only_wiring_is_red(self):
        table = {**stages.TABLE, "stages": [{**stage, "wiring": list(stage["wiring"])} for stage in stages.TABLE["stages"]]}
        table["stages"][0]["wiring"].append("fixed")
        table["stages"][2]["wiring"] = list(table["stages"][2]["nodes"])
        with unittest.mock.patch.object(stages, "TABLE", table):
            got = stages.check(line(NODES))
        self.assertEqual(len(got), 2)
        self.assertTrue(any("fixed" in line for line in got) and any(table["stages"][2]["name"] in line for line in got))

    def test_a_stage_where_only_wiring_ran_is_skipped(self):
        """修正の段が飛んだ run（修正前の承認で止めた）でも、合流の fix-in・fixed と判定を渡す judged は走る。段は飛んだ"""
        events = [event(["judge", "diagnose"], kind="agent"), event(["ask-before-fix"]), event(["answer-before-fix"]),
                  event(["fix-in"]), event(["lens-in"]), event(["fixed"]), event(["judged"]), event(["collect"])]
        skipped = [{"tokens": [node]} for node in ("fix", "rejudge-run", "test-gate-final", "eyes", "merge-seal")]
        data = {"shape": {"graphs": line(NODES)}, "run": {"graph": "works-factory-line", "events": events, "skipped": skipped}}
        stages.attach(data)
        rows = data["stages"]["run"]
        self.assertEqual([rows[number(node) - 1]["state"] for node in ("judge", "gate-before-fix", "fix", "judged", "eyes", "collect")],
                         ["ok", "ok", "skipped", "skipped", "skipped", "ok"])
        self.assertEqual(data["stages"]["stop"], number("gate-before-fix"))
        self.assertEqual([e["through"] for e in events], [False, False, False, True, True, True, True, False])

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
        self.assertEqual(plan["tokens"], {**usage, "uncached": 10, "odd": 0})
        self.assertEqual([e["stage"] for e in events], [number(e["tokens"][0]) for e in events])
        self.assertEqual([(e["role"], e["through"]) for e in events],
                         [("machine", False), ("ai", False), ("group", False), ("ai", False), ("wait", False), ("machine", True), ("machine", False)])
        self.assertEqual(got["loose"], [])

    def test_a_child_run_cost_is_counted_once(self):
        # 子の run を起こすノードの行には子の総額が載る（docs/design/archon.md）。子の中の出来事の費用と二重に足さない
        got = summed([event(["merge-seal"], kind="workflow", cost=3.0),
                      event(["merge-seal", "a"], kind="agent", cost=1.0), event(["merge-seal", "b"], kind="agent", cost=2.0)])
        self.assertEqual(got[number("merge-seal") - 1]["cost"], 3.0)

    def test_rounds_are_counted_per_loop_round(self):
        got = summed([event(["plan-rounds"], kind="loop_group", loop=[]),
                      *[event(["plan-rounds", node], loop=[n]) for n in (1, 2, 3) for node in ("plan", "gate-design")]])
        self.assertEqual(got[number("plan-rounds") - 1]["rounds"], 3)
        self.assertEqual(got[number("start") - 1]["rounds"], 0)

    def test_tokens_unknown_cache_and_odd_turns(self):
        known = {"input": 100, "output": 7, "cacheRead": 60, "cacheWrite": 30}
        got = summed([event(["judge", "a"], kind="agent", usage=known), event(["judge", "b"], kind="agent", usage={"input": 50, "output": 1})])
        self.assertEqual(got[number("judge") - 1]["tokens"], {"input": 150, "output": 8, "cacheRead": 60, "cacheWrite": 30, "cacheUnknown": 1, "odd": 0})
        odd = {"input": 10, "output": 1, "cacheRead": 60, "cacheWrite": 30}
        got = summed([event(["judge", "a"], kind="agent", usage=known), event(["judge", "b"], kind="agent", usage=odd)])
        self.assertEqual(got[number("judge") - 1]["tokens"], {"input": 110, "output": 8, "cacheRead": 120, "cacheWrite": 60, "odd": 1})

    def test_stop_needs_a_skipped_stage_between(self):
        # 間の段が記録に無いだけでは、道が分かれたと言えない
        data = run_of([event(["start"]), event(["collect"])], [])
        self.assertEqual(data["stages"]["stop"], None)
        data = run_of([event(["start"]), event(["collect"])], [{"tokens": ["fix"]}])
        self.assertEqual(data["stages"]["stop"], number("start"))

    def test_a_failed_run_stops_at_the_failed_stage(self):
        # 落ちた後ろを Archon が飛んだと書かない run でも、落ちた段で止まる
        failed = event(["fix"], status="failed")
        self.assertEqual(run_of([event(["start"]), failed], [])["stages"]["stop"], number("fix"))
        self.assertEqual(run_of([event(["start"]), failed, event(["collect"])], [{"tokens": ["eyes"]}])["stages"]["stop"], number("fix"))
        self.assertEqual(run_of([event(["start"]), event(["fix"], status="running")], [])["stages"]["stop"], None)

    def test_a_run_of_another_graph_is_not_summed(self):
        data = {"shape": {"graphs": line(NODES)}, "run": {"graph": "works-factory-chain", "events": [event(["x"])], "skipped": []}}
        stages.attach(data)
        self.assertEqual((data["stages"]["run"], data["stages"]["stop"], len(data["stages"]["table"])), (None, None, len(stages.TABLE["stages"])))


if __name__ == "__main__":
    unittest.main()
