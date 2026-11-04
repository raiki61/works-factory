"""run の記録のトレースへの組み（viewer/src/trace.py と、会話の記録の読みの足し viewer/src/session.py。docs/design/viewer.md の 8 章と
照らしの 6）。

- 木の親子: run → 段 → 繰り返しの器 → 周 → ノード → 往復と道具 → 下請け。下請けは meta の toolUseId の道具の span の下に入り、
  下請けの中の往復と道具はその下請けの span の下に入る（下請けの中の下請けも、名の並びが親の下請けより先でも）。line の段に入るノードは段の span の下
- 時刻: 往復は、返事の行の requestRef が指す api-request（並びのすぐ前の頼みとは限らない）の時刻から、同じ message.id の最後の行の時刻まで。api-request の無い往復は
  前の行（道具の結果か指示）の時刻から。道具は tool_use の行の時刻から、同じ tool_use_id の tool_result の行の時刻まで
- 続けた会話（sessionOrigin が resumed）の写しの往復（ノードの始めより前の往復）を span にしない
- 往復のトークン: llm.token_count.prompt は input_tokens と cache の読みと書きの和（Claude Code の input_tokens は cache を含まない）。
  cache の 2 つは内訳に置く
- 中の出来事を束ねる器（繰り返しの器）と周の span に費用を載せない（中と二重になる）。ノードの span は Archon の費用を持つ
- 裏で走る下請けの span が親の道具の span より後に終わっても組みは落ちない
- 中身の字は 1 欄 runread.CLIP 字で切り、切る前の字の数を持つ
- 読めない行（知らない型）と、親の呼び出しに当たらない下請けは数え、黙って落とさない
- 出来事の span の id は始めの時刻でも分ける（同じ run・道・周で落ちて走り直した起動が重ならない）
- 同じ記録から 2 度組むとトレースの id と span の id が同じ値になり、別の run の id では違う値になる

試験は一時のフォルダに、実物の行の形（型・欄の名）を写した小さな会話の記録と下請けの記録を書き、run の出来事を手で組む。
"""
import json
import tempfile
import unittest
from pathlib import Path

from viewer.src import runread, session, stages, trace

NODES = [node for stage in stages.TABLE["stages"] for node in stage["nodes"]]
MODEL = "claude-opus-5-5"


def at(minute: int, second: int, ms: int = 0) -> str:
    return f"2026-11-04T01:{minute:02d}:{second:02d}.{ms:03d}Z"


def usage(fresh: int, read: int, wrote: int, out: int) -> dict:
    return {"input_tokens": fresh, "cache_read_input_tokens": read, "cache_creation_input_tokens": wrote, "output_tokens": out}


def say(ident: str, ts: str, part: dict, ref: str | None = None, used: dict | None = None, **more) -> dict:
    row = {"type": "assistant", "timestamp": ts, "message": {"model": MODEL, "id": ident, "type": "message", "role": "assistant",
                                                              "content": [part], **({"usage": used} if used else {})}, **more}
    if ref:
        row["requestRef"] = ref
    return row


def ask(ident: str, ts: str, **more) -> dict:
    return {"type": "api-request", "id": ident, "timestamp": ts, "params": {"model": MODEL}, **more}


def told(text: str, ts: str, **more) -> dict:
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": text}, **more}


def result(use: str, text: str, ts: str, **more) -> dict:
    return {"type": "user", "timestamp": ts,
            "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": use, "content": [{"type": "text", "text": text}]}]},
            **more}


def use(ident: str, name: str, given: dict) -> dict:
    return {"type": "tool_use", "id": ident, "name": name, "input": given}


def text(said: str) -> dict:
    return {"type": "text", "text": said}


def event(tokens: list[str], kind: str, start: str, end: str, cost: float = 0.0, loop=(), **more) -> dict:
    return {"tokens": tokens, "path": ".".join(tokens), "run": "r1", "kind": kind, "start": start, "last_start": start, "end": end,
            "status": "ok", "cost": cost, "loop": list(loop), "calls": [], "exec": [], "error": "", **more}


class TraceCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.projects = Path(tmp.name) / "projects"
        (self.projects / "p").mkdir(parents=True)
        self._write_sessions()

    def _lines(self, path: Path, rows: list) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(row if isinstance(row, str) else json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    def _write_sessions(self) -> None:
        side = {"isSidechain": True}
        first = "aaaa1111-0000-0000-0000-000000000001"
        self._lines(self.projects / "p" / f"{first}.jsonl", [
            told("review the plan", at(0, 2)),
            ask("req-1", at(0, 3)),
            say("msg_1", at(0, 5), text("spawning"), ref="req-1", used=usage(3, 100, 20, 7)),
            say("msg_1", at(0, 6), use("toolu_A", "Agent", {"description": "item 1", "run_in_background": True}), ref="req-1",
                used=usage(3, 100, 20, 7)),
            result("toolu_A", "started in the background", at(0, 7)),
            # api-request の無い往復（前の行の時刻から）
            say("msg_2", at(0, 9), text("done"), used=usage(1, 130, 0, 4)),
            {"type": "weird-type", "timestamp": at(0, 9)},
        ])
        agents = self.projects / "p" / first / "subagents"
        self._lines(agents / "agent-a1.jsonl", [
            told("read the file", at(0, 6, 500), **side),
            ask("req-s1", at(0, 7), **side),
            say("msg_s1", at(0, 8), use("toolu_B", "Read", {"file_path": "plan.md"}), ref="req-s1", used=usage(2, 0, 900, 5), **side),
            # 実物に多い並び: 頼みが道具の結果の user の行より先に立つ
            ask("req-s2", at(0, 8, 500), **side),
            result("toolu_B", "x" * (runread.CLIP + 5), at(0, 9), **side),
            # 裏で走る下請けは、親の Agent の道具の span（00:07 まで）より後に終わる
            say("msg_s2", at(4, 0), text("item 1 is fine"), ref="req-s2", used=usage(2, 900, 40, 30), **side),
            say("msg_s2", at(4, 1), use("toolu_C", "Agent", {"description": "item 1a"}), ref="req-s2", used=usage(2, 900, 40, 30), **side),
            result("toolu_C", "item 1a is fine", at(4, 3), **side),
        ])
        # 下請けの中の下請け（名の並びで親の下請けより先に読む）
        self._lines(agents / "agent-a0.jsonl", [told("read item 1a", at(4, 1, 500), **side),
                                                 say("msg_n1", at(4, 2), text("1a ok"), used=usage(1, 0, 0, 2), **side)])
        (agents / "agent-a0.meta.json").write_text(json.dumps({
            "agentType": "Explore", "description": "item 1a", "toolUseId": "toolu_C", "spawnDepth": 2}), encoding="utf-8")
        (agents / "agent-a1.meta.json").write_text(json.dumps({
            "agentType": "general-purpose", "description": "item 1", "toolUseId": "toolu_A", "spawnDepth": 1,
            "requestShape": "background"}), encoding="utf-8")
        self._lines(agents / "agent-zz.jsonl", [told("orphan", at(0, 8), **side)])
        (agents / "agent-zz.meta.json").write_text(json.dumps({"agentType": "x", "description": "orphan", "toolUseId": "toolu_NOPE",
                                                               "spawnDepth": 1}), encoding="utf-8")
        # 続けた会話: 前の会話の往復（msg_old）を元の時刻のまま写して持つ
        self._lines(self.projects / "p" / "bbbb2222-0000-0000-0000-000000000002.jsonl", [
            told("review the plan", at(0, 2)),
            ask("req-old", at(0, 3)),
            say("msg_old", at(0, 5), text("old"), ref="req-old", used=usage(3, 100, 20, 7)),
            told("again", at(5, 11)),
            # 返事が指すのはすぐ前の頼みでない（並びで結ぶと 05:13 になる）
            ask("req-new", at(5, 12)),
            ask("req-retry", at(5, 13)),
            say("msg_new", at(5, 15), text("new"), ref="req-new", used=usage(5, 200, 0, 9)),
        ])

    def _data(self, run_id: str = "r1") -> dict:
        events = [
            event(["testcmd"], "script", at(0, 0), at(0, 1)),
            # 同じ run・道・周で始めの時刻だけが違う出来事（落ちて走り直した起動）
            event(["start"], "script", at(0, 0, 100), at(0, 0, 200), status="failed"),
            event(["start"], "script", at(0, 0, 300), at(0, 0, 400), fell=True),
            event(["plan-rounds"], runread.LOOP_GROUP, at(0, 1), at(9, 0), cost=4.0),
            event(["plan-rounds", "review-tree"], "agent", at(0, 1, 500), at(5, 0), cost=3.0, loop=[1], session="aaaa1111",
                  origin="fresh", model=MODEL, usage={"input": 300, "output": 20, "cacheRead": 200, "cacheWrite": 50}, turns=2),
            event(["plan-rounds", "review-tree"], "agent", at(5, 10), at(8, 0), cost=1.0, loop=[2], session="bbbb2222",
                  origin=runread.RESUMED, model=MODEL, usage={"input": 205, "output": 9, "cacheRead": 200, "cacheWrite": 0}, turns=1),
        ]
        for e in events:
            e["run"] = run_id
        items = [{"id": i, "trigger": "", "when": ""} for i in NODES]
        texts = {}

        def keep(said: str) -> str:
            texts[str(len(texts))] = said
            return str(len(texts) - 1)

        run = {"id": run_id, "graph": "works-factory-line", "status": "completed", "started": at(0, 0), "seconds": 540.0, "cost": 4.0,
               "events": events, "skipped": [], "children": [], "unread": {}, "checks": []}
        run["sessions"] = session.collect(run, self.projects, keep)
        data = {"shape": {"graphs": {stages.TABLE["graph"]: {"name": "works-factory-line", "items": items}}}, "run": run, "texts": texts}
        stages.attach(data)
        return data

    def _spans(self, data: dict | None = None) -> tuple[dict, dict]:
        got = trace.build(data or self._data())
        return got, {span["id"]: span for span in got["spans"]}

    @staticmethod
    def _kind(span: dict) -> str:
        return span["attributes"][trace.KIND]

    def _chain(self, spans: dict, span: dict) -> list[str]:
        out = []
        while span["parent"]:
            span = spans[span["parent"]]
            out.append(span["name"])
        return out

    def _one(self, spans: dict, **match) -> dict:
        found = [s for s in spans.values() if all(s["attributes"].get(k) == v or s.get(k) == v for k, v in match.items())]
        self.assertEqual(len(found), 1, f"{match}: {[s['name'] for s in found]}")
        return found[0]

    def test_the_tree_runs_from_the_run_to_the_subagents(self):
        got, spans = self._spans()
        root = [s for s in spans.values() if not s["parent"]]
        self.assertEqual([(s["name"], self._kind(s)) for s in root], [("works-factory-line", "AGENT")])
        node = self._one(spans, **{trace.LOOP: "1", "name": "plan-rounds.review-tree"})
        self.assertEqual(self._kind(node), "AGENT")
        self.assertEqual(self._chain(spans, node), ["round 1", "plan-rounds", "計画", "works-factory-line"])
        self.assertEqual(self._chain(spans, self._one(spans, name="testcmd")), ["受付", "works-factory-line"])
        tool = self._one(spans, **{trace.TOOL_NAME: "Agent", "parent": node["id"]})
        self.assertEqual(self._kind(tool), "TOOL")
        agent = self._one(spans, **{trace.AGENT_TYPE: "general-purpose"})
        self.assertEqual((self._kind(agent), agent["parent"]), ("AGENT", tool["id"]))
        under = sorted(self._kind(s) for s in spans.values() if s["parent"] == agent["id"])
        self.assertEqual(under, ["LLM", "LLM", "TOOL", "TOOL"])
        # 下請けの中の下請けは、親の下請けの Agent の道具の span の下に入り、その中の往復はその下請けの下に入る
        inner = self._one(spans, **{trace.AGENT_TYPE: "Explore"})
        spawn = spans[inner["parent"]]
        self.assertEqual((spawn["parent"], spawn["attributes"][trace.TOOL_NAME], inner["attributes"][trace.AGENT_DEPTH]),
                         (agent["id"], "Agent", 2))
        self.assertEqual([self._kind(s) for s in spans.values() if s["parent"] == inner["id"]], ["LLM"])
        read = self._one(spans, **{trace.TOOL_NAME: "Read"})
        self.assertEqual(read["parent"], agent["id"])
        # 中身の字は 1 欄 runread.CLIP 字で切り、切る前の字の数を持つ
        self.assertEqual((read["attributes"][trace.RESULT_CHARS], len(read["attributes"][trace.OUTPUT]),
                          read["attributes"][trace.CHARS + "output"]), (runread.CLIP + 5, runread.CLIP, runread.CLIP + 5))
        self.assertEqual(sorted(self._kind(s) for s in spans.values() if s["parent"] == node["id"]), ["LLM", "LLM", "TOOL"])

    def test_turns_run_from_their_request_to_their_last_row(self):
        _, spans = self._spans()
        node = self._one(spans, **{trace.LOOP: "1", "name": "plan-rounds.review-tree"})
        turns = sorted((s for s in spans.values() if s["parent"] == node["id"] and self._kind(s) == "LLM"), key=lambda s: s["start"])
        self.assertEqual([(s["start"], s["end"]) for s in turns], [(at(0, 3), at(0, 6)), (at(0, 7), at(0, 9))])
        tool = self._one(spans, **{trace.TOOL_NAME: "Agent", "parent": node["id"]})
        self.assertEqual((tool["start"], tool["end"]), (at(0, 6), at(0, 7)))
        agent = self._one(spans, **{trace.AGENT_TYPE: "general-purpose"})
        self.assertEqual((agent["start"], agent["end"]), (at(0, 6, 500), at(4, 3)))
        self.assertGreater(runread.when(agent["end"]), runread.when(tool["end"]))
        # 頼みが道具の結果の user の行より先に立っても、往復の始めはその頼みの時刻
        below = sorted(s["start"] for s in spans.values() if s["parent"] == agent["id"] and self._kind(s) == "LLM")
        self.assertEqual(below, [at(0, 7), at(0, 8, 500)])
        # 往復の始めは requestRef が指す頼みの時刻で、並びのすぐ前の頼み（05:13）ではない
        resumed = self._one(spans, **{trace.LOOP: "2", "name": "plan-rounds.review-tree"})
        late = [s for s in spans.values() if s["parent"] == resumed["id"] and self._kind(s) == "LLM"]
        self.assertEqual([(s["start"], s["end"]) for s in late], [(at(5, 12), at(5, 15))])

    def test_copied_turns_of_a_resumed_session_are_not_spans(self):
        _, spans = self._spans()
        node = self._one(spans, **{trace.LOOP: "2", "name": "plan-rounds.review-tree"})
        turns = [s for s in spans.values() if s["parent"] == node["id"] and self._kind(s) == "LLM"]
        self.assertEqual([(s["start"], s["attributes"][trace.OUTPUT]) for s in turns], [(at(5, 12), "new")])

    def test_prompt_tokens_hold_the_cache_and_groups_hold_no_cost(self):
        _, spans = self._spans()
        first = self._one(spans, start=at(0, 3))
        self.assertEqual({k: first["attributes"][k] for k in (trace.PROMPT, trace.CACHE_READ, trace.CACHE_WRITE, trace.COMPLETION, trace.TOTAL)},
                         {trace.PROMPT: 123, trace.CACHE_READ: 100, trace.CACHE_WRITE: 20, trace.COMPLETION: 7, trace.TOTAL: 130})
        self.assertEqual(first["attributes"][trace.MODEL], MODEL)
        group = self._one(spans, name="plan-rounds")
        rounds = [s for s in spans.values() if s["parent"] == group["id"]]
        self.assertEqual(sorted(s["name"] for s in rounds), ["round 1", "round 2"])
        for span in [group, *rounds]:
            self.assertNotIn(trace.COST, span["attributes"])
        node = self._one(spans, **{trace.LOOP: "1", "name": "plan-rounds.review-tree"})
        self.assertEqual(node["attributes"][trace.COST], 3.0)
        root = next(s for s in spans.values() if not s["parent"])
        self.assertEqual(root["attributes"][trace.COST], 4.0)

    def test_unread_rows_and_orphan_subagents_are_counted(self):
        got, _ = self._spans()
        self.assertEqual(got["unread"].get("知らない型 weird-type"), 1)
        self.assertEqual(got["unread"].get(trace.ORPHAN), 1)

    def test_ids_follow_the_run_id(self):
        once, again, other = trace.build(self._data()), trace.build(self._data()), trace.build(self._data("r2"))
        self.assertEqual(once["trace_id"], again["trace_id"])
        self.assertEqual([s["id"] for s in once["spans"]], [s["id"] for s in again["spans"]])
        # 落ちて走り直した起動（同じ run・道・周で始めの時刻だけが違う）も別の id になる
        self.assertEqual(len([s for s in once["spans"] if s["name"] == "start"]), 2)
        self.assertEqual(len({s["id"] for s in once["spans"]}), len(once["spans"]))
        self.assertNotEqual(once["trace_id"], other["trace_id"])
        self.assertFalse({s["id"] for s in once["spans"]} & {s["id"] for s in other["spans"]})
        self.assertEqual((len(once["trace_id"]), len(once["spans"][0]["id"])), (32, 16))


if __name__ == "__main__":
    unittest.main()
