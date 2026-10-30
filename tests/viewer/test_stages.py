"""段の表（viewer/stages.json）と段ごとの集計（viewer/src/stages.py。docs/design/viewer.md の 6.8 と照らしの 8）。

- 今の木の line の一番上のノードは、どれも段の表のちょうど 1 つの段に入り、表のノードはどれも line に在る（line にノードを足して
  表に足さなければ赤。表に残った古い id も赤）
- 出来事は道の頭のノードで段に寄せ、段ごとに状態・時間・人の待ち・AI の手番・費用・トークンを集める。繰り返しの器は数えない
- 子の run を起こすノードの費用（子の総額）と並べて起こす器の手番・長さ・費用は、中の出来事と二重になるので足さない。周の数は
  繰り返しの周ごとに 1 つ（本体に include が在っても）
- トークンの新しく読んだ分は lib/runlog.py の add_tokens と同じ訳（cache の欄が欠けた手番が在れば知れない）。input が cache の和より
  小さい手番は数だけ持ち、新しく読んだ分を出さない
- 段の表の配線の列（wiring。合流・受け渡しだけで段の仕事をしないノード）は、その段のノードの中に在り、どの段にも配線でない
  ノードが在る。配線のノードだけが走った段は「飛んだ」（修正の段が飛んだ run でも fix-in・fixed・judged は走る。修正前の承認の
  聞きと受け ask-before-fix・answer-before-fix と仕様駆動の spec-ask-before-fix・spec-answer-before-fix は、人が聞かれずに止めや通しを受け渡しただけでも走る。人が答えた run は「通った」）
- 止まった段は記録の事実から引く: 人が止めた run は答えが stop だった人の答え待ちの段（run 642df5d7 の形で、止めを受け渡しただけの
  修正前の承認を返さない）、落ちた run は受け止めていない最後に落ちた出来事の段（後ろの段の配線でないノードが走った落ちは受け止めた物）。
  通す答えだけの run と落ちずに終わった run と、受け止めた落ちだけの run には無い。止まり方（人が止めた human・落ちた failed）と
  止まった出来事の番号も同じ所で決め、雛形は読むだけ（承認を通した後に同じ段で落ちた run を人の止めと取り違えない）
- line でない run は段に集めない
- 図の札ごとの AI の手番の費用（run の ai_cost。札の鍵は入れ子の場所ごと）は、札とその中の AI の手番の費用の和で、機械の手番と
  中の出来事を束ねる器（子の run を起こすノードの行は子の総額を載せる）を足さない。line でない run にも付ける。雛形は数えずに読む
- 結末の頭の語の表（outcomes）の語の組は、工場の結末の語の正本 lib/report.py の OUTCOMES と同じ（工場が結末の語を足せば赤）

試験は小さな作りと run の記録を手で組む。
"""
import unittest
import unittest.mock

from viewer import flowview
from viewer.src import stages

import report   # lib/（viewer/src/__init__.py が sys.path に足す）

NODES = [node for stage in stages.TABLE["stages"] for node in stage["nodes"]]


def number(node: str) -> int:
    return next(n for n, stage in enumerate(stages.TABLE["stages"], 1) if node in stage["nodes"])


def line(ids: list[str]) -> dict:
    items = [{"id": i, "trigger": "", "when": ""} for i in ids]
    return {stages.TABLE["graph"]: {"name": "works-factory-line", "items": items}}


def event(tokens, kind="exec", start="2026-10-25T01:00:00.000Z", end="2026-10-25T01:00:01.000Z", cost=0.0, **more):
    return {"tokens": tokens, "path": ".".join(tokens), "run": "r", "kind": kind, "start": start, "end": end, "status": "ok", "cost": cost,
            "loop": [], **more}


def run_of(events: list[dict], skipped: list[dict], status: str = "completed") -> dict:
    data = {"shape": {"graphs": line(NODES)}, "run": {"graph": "works-factory-line", "status": status, "events": events, "skipped": skipped}}
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

    def test_the_outcome_words_are_the_factorys(self):
        self.assertEqual(set(stages.TABLE["outcomes"]), set(report.OUTCOMES))
        self.assertTrue(all(isinstance(head, str) and head for head in stages.TABLE["outcomes"].values()))
        self.assertEqual(run_of([], [])["stages"]["outcomes"], stages.TABLE["outcomes"])

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
        skipped = [{"tokens": [node]} for node in ("gate-before-fix", "fix", "rejudge-run", "test-gate-final", "eyes", "merge-seal")]
        data = {"shape": {"graphs": line(NODES)}, "run": {"graph": "works-factory-line", "events": events, "skipped": skipped}}
        stages.attach(data)
        rows = data["stages"]["run"]
        self.assertEqual([rows[number(node) - 1]["state"] for node in ("judge", "gate-before-fix", "fix", "judged", "eyes", "collect")],
                         ["ok", "skipped", "skipped", "skipped", "skipped", "ok"])
        self.assertEqual([e["through"] for e in events], [False, True, True, True, True, True, True, False])

    def test_run_is_summed_by_stage(self):
        usage = {"input": 100, "output": 7, "cacheRead": 60, "cacheWrite": 30}
        events = [
            event(["start"], end="2026-10-25T01:00:20.000Z"),
            event(["judge", "diagnose"], kind="agent", cost=1.5, usage=usage, turns=4,
                  start="2026-10-25T01:01:00.000Z", end="2026-10-25T01:03:00.000Z"),
            event(["plan-rounds"], kind="loop_group", start="2026-10-25T01:03:00.000Z", end="2026-10-25T01:10:00.000Z"),
            event(["plan-rounds", "plan"], kind="agent", cost=2.0, usage=usage, turns=3,
                  start="2026-10-25T01:03:00.000Z", end="2026-10-25T01:05:00.000Z"),
            event(["plan-rounds", "gate-design"], kind="wait", start="2026-10-25T01:05:00.000Z", end="2026-10-25T01:10:00.000Z",
                  output='{"decision": "stop", "text": ""}'),
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

    def test_a_round_with_an_include_in_the_body_is_one_round(self):
        # 本体に直に在るノード（plan-rounds.design-turn）と include の中のノード（plan-rounds.plan__draft）は同じ周
        got = summed([event(["plan-rounds"], kind="loop_group"),
                      *[event(["plan-rounds", "design-turn"], loop=[n]) for n in (1, 2)],
                      *[event(["plan-rounds", "plan", "draft"], path="plan-rounds.plan__draft", loop=[n]) for n in (1, 2)]])
        self.assertEqual(got[number("plan-rounds") - 1]["rounds"], 2)

    def test_a_fan_out_holder_is_not_counted_twice(self):
        # 並べて起こす器（compose_fan_out）の行は中の出来事と重なる。手番の数・長さ・費用に器の分を足さない
        got = summed([event(["plan-rounds"], kind="compose_fan_out", cost=3.0, turns=4,
                            start="2026-10-25T01:00:00.000Z", end="2026-10-25T01:10:00.000Z"),
                      event(["plan-rounds", "a"], kind="agent", cost=1.0, turns=1,
                            start="2026-10-25T01:00:00.000Z", end="2026-10-25T01:01:00.000Z"),
                      event(["plan-rounds", "b"], kind="agent", cost=2.0, turns=3,
                            start="2026-10-25T01:00:00.000Z", end="2026-10-25T01:02:00.000Z")])
        plan = got[number("plan-rounds") - 1]
        self.assertEqual({key: plan[key] for key in ("steps", "ai", "turns", "ai_seconds", "cost")},
                         {"steps": 2, "ai": 2, "turns": 4, "ai_seconds": 180.0, "cost": 3.0})

    def test_tokens_unknown_cache_and_odd_turns(self):
        known = {"input": 100, "output": 7, "cacheRead": 60, "cacheWrite": 30}
        got = summed([event(["judge", "a"], kind="agent", usage=known), event(["judge", "b"], kind="agent", usage={"input": 50, "output": 1})])
        self.assertEqual(got[number("judge") - 1]["tokens"], {"input": 150, "output": 8, "cacheRead": 60, "cacheWrite": 30, "cacheUnknown": 1, "odd": 0})
        odd = {"input": 10, "output": 1, "cacheRead": 60, "cacheWrite": 30}
        got = summed([event(["judge", "a"], kind="agent", usage=known), event(["judge", "b"], kind="agent", usage=odd)])
        self.assertEqual(got[number("judge") - 1]["tokens"], {"input": 110, "output": 8, "cacheRead": 120, "cacheWrite": 60, "odd": 1})

    def test_a_failed_run_stops_at_the_last_failed_stage(self):
        # 落ちた後ろを Archon が飛んだと書かない run でも、落ちた出来事の段で止まる。落ちて続けて終わった run は止まっていない
        failed = event(["fix"], status="failed")
        self.assertEqual(run_of([event(["start"]), failed], [], status="failed")["stages"]["stop"], number("fix"))
        self.assertEqual(run_of([event(["start"]), failed, event(["collect"], status="failed")], [{"tokens": ["eyes"]}], status="failed")["stages"]["stop"],
                         number("collect"))
        self.assertEqual(run_of([event(["start"]), failed, event(["fix"]), event(["collect"])], [], status="completed")["stages"]["stop"], None)
        self.assertEqual(run_of([event(["start"]), event(["fix"], status="running")], [], status="running")["stages"]["stop"], None)

    def test_an_absorbed_failure_is_not_a_stop(self):
        """line が受け止めて先へ進んだ落ち（独立の目・レンズ）の在る run も、Archon は failed で終える（docs/design/archon.md）。後ろの段
        （報告の段のほか）の配線でないノードが走った落ちは止まった所でない。直した run には無く、その後に人が最後の承認で止めた run は
        最後の承認の段、受け止めた落ちの後で本当に落ちた run はその段"""
        absorbed = [event(["start"]), event(["fix"], kind="agent"), event(["lens", "check"], status="failed"), event(["lens-out"]),
                    event(["eyes-in"]), event(["eyes", "r1"], kind="agent", status="failed"), event(["eyes-out"]), event(["merge-seal"]),
                    event(["ask-final"])]
        tail = [event(["collect"]), event(["report"], kind="workflow"), event(["result"])]
        fixed = absorbed + [event(["answer-final"]), event(["merge-apply"])] + tail
        self.assertEqual(run_of(fixed, [], status="failed")["stages"]["stop"], None)
        stopped = absorbed + [event(["gate-final"], kind="wait", output='{"decision": "stop", "text": ""}'), event(["answer-final"])] + tail
        self.assertEqual(run_of(stopped, [{"tokens": ["merge-apply"]}], status="failed")["stages"]["stop"], number("gate-final"))
        failed = absorbed[:4] + [event(["rejudge-run"], kind="workflow", status="failed"), event(["judged"])] + tail
        self.assertEqual(run_of(failed, [{"tokens": ["eyes"]}], status="failed")["stages"]["stop"], number("rejudge-run"))

    def test_a_failure_after_an_approval_in_the_same_stage_is_a_failure(self):
        """最後の承認 gate-final を人が通した後に、同じ段の merge-apply が落ちた run。止まり方は落ちた、止まった出来事は merge-apply
        （同じ段に人の答え待ちが在っても、答えが止める語でなければ人の止めでない）。人が止めた run は答え待ちの出来事を指す"""
        events = [event(["start"]), event(["merge-seal"]), event(["ask-final"]),
                  event(["gate-final"], kind="wait", output='{"decision": "approve", "text": ""}'), event(["answer-final"]),
                  event(["merge-apply"], status="failed")]
        got = run_of(events, [], status="failed")["stages"]
        self.assertEqual((got["stop"], got["stop_by"], got["stop_event"]), (number("merge-apply"), "failed", 5))
        stopped = events[:3] + [event(["gate-final"], kind="wait", output='{"decision": "stop", "text": ""}'), event(["answer-final"])]
        got = run_of(stopped, [{"tokens": ["merge-apply"]}], status="completed")["stages"]
        self.assertEqual((got["stop"], got["stop_by"], got["stop_event"]), (number("gate-final"), "human", 3))
        got = run_of(events[:5], [], status="completed")["stages"]
        self.assertEqual((got["stop"], got["stop_by"], got["stop_event"]), (None, None, None))

    def test_a_human_stop_stops_at_the_stage_of_the_answer(self):
        """run 642df5d7 の形: 計画の段の中の相談 plan-rounds/gate-design で人が stop と答え、修正前の承認の聞きと受け（ask-before-fix・
        answer-before-fix）はその stop を受け渡しただけ（承認の聞き gate-before-fix は飛んだ）。止まった段は答えた段（計画）"""
        events = [event(["start"]), event(["judge", "diagnose"], kind="agent"), event(["plan-rounds"], kind="loop_group"),
                  event(["plan-rounds", "plan"], kind="agent", loop=[1]),
                  event(["plan-rounds", "gate-design"], kind="wait", loop=[1], output='{"decision": "stop", "text": "止める"}'),
                  event(["ask-before-fix"]), event(["answer-before-fix"]), event(["fix-in"]), event(["fixed"]), event(["judged"]),
                  event(["collect"]), event(["report"], kind="workflow"), event(["result"])]
        skipped = [{"tokens": [node]} for node in ("gate-before-fix", "fix", "rejudge-run", "test-gate-final", "eyes", "merge-seal")]
        got = run_of(events, skipped, status="completed")["stages"]
        self.assertEqual(got["stop"], number("plan-rounds"))
        # 修正前の承認は人が聞かれていない（聞きと受けは止めを受け渡しただけ）ので飛んだ
        self.assertEqual(got["run"][number("gate-before-fix") - 1]["state"], "skipped")

    def test_a_before_fix_approval_by_a_human_passes(self):
        # 人が修正前の承認 gate-before-fix で通した run は、修正前の承認の段が通った
        events = [event(["ask-before-fix"]), event(["gate-before-fix"], kind="wait", output='{"decision": "approve", "text": ""}'),
                  event(["answer-before-fix"]), event(["fix-in"]), event(["fix"], kind="agent")]
        self.assertEqual(summed(events)[number("gate-before-fix") - 1]["state"], "ok")

    def test_a_spec_driven_before_fix_approval_passes_only_when_a_human_answered(self):
        # 仕様駆動の run の聞きと受け spec-ask-before-fix・spec-answer-before-fix も、人に聞かずに止めを受け渡すだけで走る（受付 03e0e5）
        handed = [{"tokens": ["spec-rounds"]}, {"tokens": ["spec-ask-before-fix"]}, {"tokens": ["spec-answer-before-fix"]}]
        skipped = [{"tokens": [node]} for node in ("ask-before-fix", "gate-before-fix", "answer-before-fix", "spec-gate-before-fix", "fix")]
        events = [event(**e) for e in handed] + [event(["fix-in"]), event(["fixed"]), event(["collect"])]
        self.assertEqual(run_of(events, skipped)["stages"]["run"][number("spec-gate-before-fix") - 1]["state"], "skipped")
        answered = [event(["spec-ask-before-fix"]), event(["spec-gate-before-fix"], kind="wait", output='{"decision": "approve", "text": ""}'),
                    event(["spec-answer-before-fix"]), event(["fix-in"]), event(["fix"], kind="agent")]
        self.assertEqual(summed(answered)[number("spec-gate-before-fix") - 1]["state"], "ok")

    def test_a_go_answer_or_a_run_that_did_not_stop_has_no_stop(self):
        go = event(["plan-rounds", "gate-design"], kind="wait", output={"decision": "approve", "text": ""})
        self.assertEqual(run_of([event(["start"]), go, event(["collect"])], [{"tokens": ["fix"]}], status="completed")["stages"]["stop"], None)
        self.assertEqual(run_of([event(["start"]), event(["fix"]), event(["collect"])], [{"tokens": ["eyes"]}])["stages"]["stop"], None)

    def test_a_run_of_another_graph_is_not_summed(self):
        data = {"shape": {"graphs": line(NODES)}, "run": {"graph": "works-factory-chain", "events": [event(["x"])], "skipped": []}}
        stages.attach(data)
        self.assertEqual((data["stages"]["run"], data["stages"]["stop"], len(data["stages"]["table"])), (None, None, len(stages.TABLE["stages"])))

    def test_the_ai_cost_of_each_card_is_summed_in_the_data(self):
        """札の鍵は 雛形の K（場所 > graph/道）と同じ形。入れ子の札は中の AI の手番の和、AI の札は自分の和。機械の手番と、子の run を
        起こすノードの行（子の総額）は足さない"""
        child = {"graph": "line", "node": "rejudge-run", "via": []}
        inner = {"graph": "judge", "node": "judge-loop/diagnose", "via": [{"graph": "line", "node": "rejudge-run"}]}
        events = [event(["rejudge-run"], kind="workflow", cost=3.0, at=child),
                  event(["rejudge-run", "judge-loop", "diagnose"], kind="agent", cost=1.0, at=inner, loop=[1]),
                  event(["rejudge-run", "judge-loop", "diagnose"], kind="agent", cost=2.0, at=inner, loop=[2]),
                  event(["rejudge-run", "judge-loop", "check"], kind="exec", cost=0.5, at={**inner, "node": "judge-loop/check"}),
                  event(["start"], kind="agent", cost=0.25, at={"graph": "line", "node": "start", "via": []}), event(["x"], kind="agent", cost=9.0, at=None)]
        self.assertEqual(stages.spots(inner), ["line/rejudge-run", "line/rejudge-run>judge/judge-loop", "line/rejudge-run>judge/judge-loop/diagnose"])
        want = {"line/rejudge-run": 3.0, "line/rejudge-run>judge/judge-loop": 3.0, "line/rejudge-run>judge/judge-loop/diagnose": 3.0, "line/start": 0.25}
        self.assertEqual(run_of(events, [])["run"]["ai_cost"], want)
        other = {"shape": {"graphs": line(NODES)}, "run": {"graph": "works-factory-chain", "events": events, "skipped": []}}
        stages.attach(other)
        self.assertEqual(other["run"]["ai_cost"], want)


if __name__ == "__main__":
    unittest.main()
