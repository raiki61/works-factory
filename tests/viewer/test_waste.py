"""無駄の手がかりの数え（viewer/src/waste.py。docs/design/viewer.md の 6.9 と照らしの 8）。

小さな作りと run の記録（周 2 つの繰り返し・前と同じ出力・空の出力・同じファイルの 2 回の読み・1 万字を超える結果・空いた往復・
引く先の無い出力・同じノードから起こした周の数の違う子の run 2 つ・出力の変わらない周・別の run の同じ名のファイル・続けた会話が
前の会話から写して持つ往復）を手で組み、数えがその値を返すことを照らす。数えを外せば落ちる。run の無いページには数えを置かない。
"""
import unittest

from viewer.src import runread, waste

T = "2026-10-25T01:{:02d}:{:02d}.000Z"


def at(minute: int, second: int = 0) -> str:
    return T.format(minute, second)


def event(tokens, kind="exec", start=0, end=1, loop=(), cost=0.0, run="r", **more):
    if "output" in more:
        more.setdefault("digest", more["output"])
    return {"tokens": tokens, "kind": kind, "start": at(start), "end": at(end), "status": "ok", "loop": list(loop), "cost": cost, "run": run,
            **more}


def check(step, exit, minute, run="r", node=()):
    return {"step": step, "node": list(node), "run": run, "exit": exit, "stdout": "", "stderr": "", "at": at(minute)}


def item(ident, kind="script", **more):
    return {"id": ident, "kind": kind, "kids": [], "with": {}, "refs": {}, "when": "", **more}


def call(name, text, chars):
    return {"name": name, "text": text, "result": [chars, "", False]}


def turn(minute, calls=(), usage=None):
    return {"at": at(minute), "calls": list(calls), "usage": usage or {}}


class WasteCase(unittest.TestCase):
    def setUp(self):
        usage = {"input": 100, "output": 5, "cacheRead": 70, "cacheWrite": 20}
        self.events = [
            event(["ask"], kind="wait", start=0, end=10),
            event(["rounds"], kind="loop_group", start=10, end=30),
            event(["rounds", "plan"], kind="agent", start=10, end=14, loop=[1], cost=3.0, usage=usage, turns=6, session="s1",
                  output='{"a":1}'),
            event(["rounds", "tidy"], start=14, end=15, loop=[1], output='{"same":true}'),
            event(["rounds", "plan"], kind="agent", start=15, end=18, loop=[2], cost=1.0, usage={**usage, "input": 10}, turns=2,
                  session="s2", output='{"a":2}'),
            event(["rounds", "tidy"], start=18, end=19, loop=[2], output='{"same":true}'),
            event(["blank"], start=20, end=21, output="{}"),
        ]
        checks = [check(f"rounds{runread.ITERATION_MARK}{n}", code, minute) for n, code, minute in ((1, 1, 15), (2, 0, 19))]
        texts = {"sys": "S" * 50, "r1": '{"file_path": "docs/a.md"}', "r2": '{"file_path": "/work/docs/a.md"}',
                 "r3": '{"file_path": "/home/x/artifacts/runs/abc/plan/out.md"}', "r4": '{"file_path": "/home/x/artifacts/runs/abc/plan/out.md"}',
                 "pin": "<system-reminder>same</system-reminder>"}
        sessions = {
            "s1": {"system": ["sys"], "tools": [["Read", 30]], "inject": [["user", "pin"]], "cwd": "/work",
                   "turns": [turn(10, [call("Read", "r1", 4000), call("Read", "r3", 12000)], {"in": 1, "cache_read": 0, "cache_write": 10}),
                             turn(17, [], {"in": 1, "cache_read": 10, "cache_write": 50})]},
            "s2": {"system": ["sys"], "tools": [["Read", 30]], "inject": [["user", "pin"]], "cwd": "/work",
                   "turns": [turn(15, [call("Read", "r2", 4000), call("Read", "r4", 12000)])]},
        }
        graphs = {"rounds": {"returns": "", "items": [item("plan", "ai", prompt="read $tidy.output"), item("tidy"), item("lost")]}}
        self.data = {"texts": texts, "shape": {"graphs": graphs},
                     "run": {"seconds": 1260.0, "events": self.events, "checks": checks, "sessions": sessions}}
        for e in self.events[2:6]:
            e["at"] = {"graph": "rounds", "node": e["tokens"][-1]}
        self.events[6]["at"] = {"graph": "rounds", "node": "lost"}
        waste.attach(self.data)
        self.got = self.data["waste"]

    def test_ai_turns_are_ranked_by_cost(self):
        top = self.got["top"]
        self.assertEqual([(row["event"], row["share"], row["replies"]) for row in top["rows"]], [(2, 0.75, 2), (4, 0.25, 1)])
        self.assertEqual(top["rows"][0]["tokens4"]["uncached"], 10)
        self.assertEqual(top["odd"], [4])   # input 10 は cache の 2 つの和 90 より小さい

    def test_time_is_split_into_waiting_ai_and_machine(self):
        time = self.got["time"]
        self.assertEqual({key: time[key] for key in ("wait", "ai", "machine")}, {"wait": 600.0, "ai": 420.0, "machine": 180.0})
        self.assertEqual(time["waits"], [{"event": 0, "seconds": 600.0}])

    def test_rounds_carry_their_cost_and_check(self):
        (group,) = self.got["rounds"]
        self.assertEqual(group["event"], 1)
        self.assertEqual([(row["round"], row["cost"], row["check"]["exit"], row["same"]) for row in group["rounds"]],
                         [(1, 3.0, 1, False), (2, 1.0, 0, False)])

    def test_outputs_same_as_before_empty_and_unread(self):
        idle = self.got["idle"]
        self.assertEqual(idle["same"], [{"event": 5, "before": 3}])
        self.assertEqual(idle["empty"], [6])
        self.assertEqual((idle["unread"]["nodes"], idle["unread"]["none"]), (3, ["rounds/lost", "rounds/plan"]))
        self.assertEqual(idle["unread"]["ran"], [{"node": "rounds/lost", "events": [6]}, {"node": "rounds/plan", "events": [2, 4]}])

    def test_context_overlaps_and_rereads(self):
        context = self.got["context"]
        self.assertEqual(context["system"], [{"marks": ["sys"], "chars": 50, "sessions": 2}])
        self.assertEqual(context["tools"], [{"names": ["Read"], "chars": 30, "sessions": 2}])
        self.assertEqual([(row["chars"], row["sessions"]) for row in context["inject"]], [(len(self.data["texts"]["pin"]), 2)])
        self.assertEqual(context["reads"], {"files": 2, "again": [
            {"path": runread.PLACE_MARK + "abc/plan/out.md", "times": 2, "chars": 24000, "sessions": 2},
            {"path": "docs/a.md", "times": 2, "chars": 8000, "sessions": 2}]})
        self.assertEqual(context["pauses"], [{"session": "s1", "event": 2, "turn": 1, "gap": 420.0, "cache_write": 50}])
        self.assertEqual(context["cache"]["cacheRead"], 140)

    def test_big_results_and_climb(self):
        big = self.got["big"]
        self.assertEqual([(row["session"], row["chars"]) for row in big["results"]], [("s1", 12000), ("s2", 12000)])
        self.assertEqual(big["calls"], 4)
        self.assertEqual(big["climb"], [{"session": "s1", "event": 2, "turns": 2, "first": 11, "last": 61, "peak": 61}])

    def test_uncounted_are_listed_and_no_run_has_no_waste(self):
        self.assertTrue(self.got["uncounted"])
        data = {"run": None}
        waste.attach(data)
        self.assertIsNone(data["waste"])

    def test_copied_turns_are_not_counted(self):
        """続けた会話が前の会話から写して持つ往復（copied）は、返事の数・道具の呼び出し・読み直し・大きな結果・空いた往復・積み上がりの
        どれにも数えない（写し元の会話の往復と二重になる）"""
        copied = {**turn(0, [call("Read", "r1", 4000), call("Read", "r3", 12000)], {"in": 1, "cache_read": 0, "cache_write": 1}), "copied": True}
        self.data["run"]["sessions"]["s2"]["turns"].insert(0, copied)
        waste.attach(self.data)
        got = self.data["waste"]
        self.assertEqual([row["replies"] for row in got["top"]["rows"]], [2, 1])
        self.assertEqual(got["big"]["calls"], 4)
        self.assertEqual([(row["session"], row["chars"]) for row in got["big"]["results"]], [("s1", 12000), ("s2", 12000)])
        self.assertEqual([row["times"] for row in got["context"]["reads"]["again"]], [2, 2])
        self.assertEqual(got["context"]["pauses"], self.got["context"]["pauses"])
        self.assertEqual(got["big"]["climb"], self.got["big"]["climb"])


class RoundsCase(unittest.TestCase):
    """周の数えの、子の run と同じ周の照らし"""

    def test_child_runs_of_one_node_keep_their_own_rounds(self):
        """同じノードから起こした子の run（fan_out）は出来事の道も周の番号も同じなので、run の id で分ける。c1 は 2 周、c2 は 1 周"""
        events = [
            event(["fan"], kind="workflow", start=0, end=9, run="top"),
            event(["fan", "rounds"], kind="loop_group", start=0, end=9, run="c1"),
            event(["fan", "rounds", "plan"], kind="agent", start=0, end=2, loop=[1], cost=1.0, run="c1", output="p"),
            event(["fan", "rounds", "plan"], kind="agent", start=2, end=4, loop=[2], cost=1.0, run="c1", output="q"),
            event(["fan", "rounds"], kind="loop_group", start=0, end=9, run="c2"),
            event(["fan", "rounds", "plan"], kind="agent", start=1, end=3, loop=[1], cost=1.0, run="c2", output="p"),
        ]
        checks = [check(f"rounds{runread.ITERATION_MARK}1", 7, 3, run="c2", node=["fan"]),
                  *(check(f"rounds{runread.ITERATION_MARK}{n}", code, minute, run="c1", node=["fan"]) for n, code, minute in ((1, 1, 2), (2, 0, 4)))]
        data = {"texts": {}, "shape": {"graphs": {}}, "run": {"seconds": 540.0, "events": events, "checks": checks, "sessions": {}}}
        waste.attach(data)
        (group,) = data["waste"]["rounds"]
        self.assertEqual((group["event"], group["cost"]), (1, 2.0))
        self.assertEqual([(row["round"], row["events"], row["check"]["exit"]) for row in group["rounds"]], [(1, [2], 1), (2, [3], 0)])
        self.assertEqual(data["waste"]["idle"]["same"], [])

    def test_a_round_is_same_when_its_outputs_did_not_change(self):
        """until_bash の途中の周はどれも終了の値が 1 で落ちが無いので、出力まで比べる。周 3 だけが前の周と同じ。切った字が同じでも、
        切る前の字の hash（digest）が違えば同じと数えない"""
        events = [event(["fix"], kind="loop_group", start=0, end=9),
                  *(event(["fix", "try"], start=n, end=n + 1, loop=[n], output=out) for n, out in ((1, "a"), (2, "b"), (3, "b"))),
                  event(["fix", "try"], start=4, end=5, loop=[4], output="b", digest="b-longer")]
        checks = [check(f"fix{runread.ITERATION_MARK}{n}", 1, n + 1) for n in (1, 2, 3, 4)]
        data = {"texts": {}, "shape": {"graphs": {}}, "run": {"seconds": 540.0, "events": events, "checks": checks, "sessions": {}}}
        waste.attach(data)
        (group,) = data["waste"]["rounds"]
        self.assertEqual([row["same"] for row in group["rounds"]], [False, False, True, False])
        self.assertEqual(data["waste"]["idle"]["same"], [{"event": 3, "before": 2}])


class WhereCase(unittest.TestCase):
    def test_run_heads_are_cut(self):
        self.assertEqual(runread.where("/w/t/a.md", "/w/t"), "a.md")
        self.assertEqual(runread.where("/h/workflow-source/runs/r1/project/.archon/x.md", ""), runread.COPY_MARK + "r1/.archon/x.md")
        self.assertEqual(runread.where("/elsewhere/a.md", "/w/t"), "/elsewhere/a.md")

    def test_other_runs_keep_their_id(self):
        """別の run（fan_out の子どうし・親と子）の置き場の同じ名のファイルは、別のファイルとして数える"""
        self.assertNotEqual(runread.where("/h/artifacts/runs/c1/plan.md", ""), runread.where("/h/artifacts/runs/c2/plan.md", ""))
        self.assertEqual(runread.where("/h/artifacts/runs/c1/plan.md", ""), runread.PLACE_MARK + "c1/plan.md")


if __name__ == "__main__":
    unittest.main()
