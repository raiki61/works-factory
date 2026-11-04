"""run の記録（Archon の記録の読み src/runread.py と会話の記録の読み src/session.py と段の集計 src/stages.py）から、OpenTelemetry の
トレース 1 本の span の木を組む（docs/design/viewer.md の 8 章）。字と数だけの dict の列を返し、網には出ない（送るのは src/otlp.py）。

- build(data) -> {"trace_id", "spans", "unread"}。data は flowview.read と同じ形（run に sessions、stages.attach の後なら出来事に段の
  番号 stage、texts に字の番号 → 字）。span は {id, parent, name, start, end, attributes}。時刻は記録の字のまま（ログの書き方の UTC）。
  属性は Phoenix が読む OpenInference の名（openinference.span.kind・llm.*・input.value・output.value・tool.name・session.id）と、工場の
  物の works_factory.* の名。unread は run と会話と下請けの読めなかった物に、組みで結べなかった物を足した数え

木: run（AGENT）→ 段（CHAIN。line の run だけ）→ 中の出来事を束ねる器（CHAIN。runread.GROUP_KINDS）→ 繰り返しの周（CHAIN）→ ノード
（AI のノードは AGENT、ほかは CHAIN）→ 往復（LLM）と道具（TOOL）→ 下請け（AGENT。meta の toolUseId の道具の下）→ 往復と道具 …。
器と周の span には費用を載せない（中と二重になる）。続けた会話の写しの往復（session の copied）は span にしない。
id は乱数にせず、トレースの id を run の id から、span の id を run の id と所の鍵（出来事の run・道・周・始め、往復の番号、道具の呼び出しの
id、下請けの id）から hash で決める（同じ run を 2 度組むと同じ id）。出来事は起動の id を持たず、落ちた後に同じ起動の id で走り直した
物も別の出来事なので、出来事の鍵は始めの時刻で分ける
"""
import hashlib
import json
from datetime import timedelta

from viewer.src import runread, stages

# OpenInference の名（https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md）
KIND = "openinference.span.kind"
INPUT = "input.value"
OUTPUT = "output.value"
MODEL = "llm.model_name"
PROVIDER = "llm.provider"
PROMPT = "llm.token_count.prompt"
COMPLETION = "llm.token_count.completion"
TOTAL = "llm.token_count.total"
CACHE_READ = "llm.token_count.prompt_details.cache_read"
CACHE_WRITE = "llm.token_count.prompt_details.cache_write"
TOOL_NAME = "tool.name"
SESSION = "session.id"
# 工場の物
RUN_ID = "works_factory.run_id"
STATUS = "works_factory.status"
OUTCOME = "works_factory.outcome"
PATH = "works_factory.path"
LOOP = "works_factory.loop"
NODE_KIND = "works_factory.kind"
STAGE = "works_factory.stage"
COST = "works_factory.cost_usd"
TURNS = "works_factory.turns"
TOKENS = "works_factory.tokens."
RESULT_CHARS = "works_factory.result_chars"
CHARS = "works_factory.chars."
AGENT_TYPE = "works_factory.subagent.type"
AGENT_DEPTH = "works_factory.subagent.depth"
AGENT_SHAPE = "works_factory.subagent.request_shape"
DESCRIPTION = "works_factory.subagent.description"
ERROR = "works_factory.error"
UNREAD = "works_factory.unread"
TIME_FROM_ANCESTOR = "works_factory.time_from_ancestor"   # 時刻が読めず、送る前に入口が一番近い時刻の在る祖先の時刻で埋めた span の印
FIELDS = {INPUT: "input", OUTPUT: "output"}   # 切る欄 → 切る前の字の数の名（CHARS の後ろ）
TOP = 10   # run の span の出力の表に並べる AI のノードの数

ORPHAN = "親の呼び出しに当たらない下請け"
TIMELESS = "時刻の無い出来事"
SHARED = "ほかの出来事と同じ会話の id の頭"


def build(data: dict) -> dict:
    run = data["run"]
    texts = data.get("texts") or {}
    tree = _Tree(run["id"], texts)
    unread = dict(run.get("unread") or {})
    events = [e for e in run["events"] if e.get("start")]
    if len(events) < len(run["events"]):
        unread[TIMELESS] = len(run["events"]) - len(events)
    table = stages.TABLE["stages"]
    start = run.get("started") or min((e["start"] for e in events), key=runread.when, default=None)
    end = _plus(start, run.get("seconds")) if start else None
    root = tree.span("run", None, run["graph"], start, end or start, {
        KIND: "AGENT", RUN_ID: run["id"], STATUS: run.get("status") or "", OUTCOME: run.get("outcome") or "",
        **({COST: run["cost"]} if run.get("cost") is not None else {}), OUTPUT: _costs(data, events, table)})
    parents = {}
    for e in events:
        parents[id(e)] = _parent(e, events)
    stage_spans = {}
    for e in events:
        n = e.get("stage")
        if n and parents[id(e)] is None and n not in stage_spans:
            inner = [x for x in events if x.get("stage") == n]
            stage_spans[n] = tree.span(f"stage|{n}", root, table[n - 1]["name"], _first(inner), _last(inner),
                                       {KIND: "CHAIN", STAGE: table[n - 1]["name"]})
    spans_of, rounds = {}, {}
    used = set()
    for e in sorted(events, key=lambda x: (len(x["tokens"]), runread.when(x["start"]))):
        up = parents[id(e)]
        if up is None:
            parent = stage_spans.get(e.get("stage"), root)
        else:
            parent = spans_of[id(up)]
            if up["kind"] == runread.LOOP_GROUP and len(e["loop"]) > len(up["loop"]):
                k = e["loop"][len(up["loop"])]
                if (id(up), k) not in rounds:
                    inner = [x for x in events if _under(x, up) and len(x["loop"]) > len(up["loop"]) and x["loop"][len(up["loop"])] == k]
                    rounds[(id(up), k)] = tree.span(f"{_key(up)}|round|{k}", parent, f"round {k}", _first(inner), _last(inner),
                                                    {KIND: "CHAIN", PATH: up["path"], LOOP: _loop([*up["loop"], k])})
                parent = rounds[(id(up), k)]
        spans_of[id(e)] = node = tree.span(_key(e), parent, e["path"], e["start"], e.get("end") or _last([e]), _node(e, table))
        said = (run.get("sessions") or {}).get(e.get("session") or "")
        if said is None or e["kind"] in runread.GROUP_KINDS:
            continue
        if e["session"] in used:
            unread[SHARED] = unread.get(SHARED, 0) + 1
            continue
        used.add(e["session"])
        tree.attrs(node, SESSION, e["session"])
        tree.attrs(node, INPUT, _opening(said, texts))
        orphans = tree.session(_key(e), node, said)
        if orphans:
            unread[ORPHAN] = unread.get(ORPHAN, 0) + orphans
        for got in _all(said):
            for what, n in got["unread"].items():
                unread[what] = unread.get(what, 0) + n
    if unread:
        tree.attrs(root, UNREAD, json.dumps(unread, ensure_ascii=False, sort_keys=True))
    return {"trace_id": _hash(f"trace|{run['id']}", 32), "spans": tree.spans, "unread": unread}


class _Tree:
    def __init__(self, run_id: str, texts: dict):
        self.run_id, self.texts, self.spans = run_id, texts, []

    def span(self, key: str, parent: dict | None, name: str, start, end, attributes: dict) -> dict:
        start = start or end
        end = end if end and start and runread.when(end) >= runread.when(start) else start
        span = {"id": _hash(f"{self.run_id}|{key}", 16), "parent": parent["id"] if parent else None, "name": name, "start": start,
                "end": end, "attributes": {}}
        for attr, value in attributes.items():
            self.attrs(span, attr, value)
        self.spans.append(span)
        return span

    @staticmethod
    def attrs(span: dict, name: str, value) -> None:
        """空の値は置かない。中身の字は 1 欄 runread.CLIP 字で切り、切る前の字の数を持つ"""
        if value is None or value == "":
            return
        if name in FIELDS and len(value) > runread.CLIP:
            span["attributes"][CHARS + FIELDS[name]] = len(value)
            value = value[:runread.CLIP]
        span["attributes"][name] = value

    def text(self, mark) -> str:
        return self.texts.get(mark, "") if mark is not None else ""

    def session(self, key: str, parent: dict, said: dict) -> int:
        """会話の往復と道具を parent の下に置き、下請けをその Agent の道具の下に置く（下請けの中の下請けも）。親に結べない下請けの数を返す"""
        calls = {}
        self._turns(key, parent, said, calls)
        agents = list(said.get("agents") or [])
        while agents:
            placed = [a for a in agents if (a.get("meta") or {}).get("use") in calls]
            if not placed:
                break
            for agent in placed:
                agents.remove(agent)
                meta = agent["meta"]
                first, last = agent.get("span") or [None, None]
                up = calls[meta["use"]]
                node = self.span(f"{up['key']}|agent|{agent['id']}", up["span"], meta.get("description") or f"subagent {agent['id']}",
                                 first, last, {KIND: "AGENT", DESCRIPTION: meta.get("description"), AGENT_TYPE: meta.get("type"),
                                                AGENT_DEPTH: meta.get("depth"), AGENT_SHAPE: meta.get("shape"),
                                                INPUT: _opening(agent, self.texts)})
                self._turns(f"{up['key']}|agent|{agent['id']}", node, agent, calls)
        # 写しの往復の呼び出しに結ぶ下請けは、写しと同じく span にしない（数えない）
        copied = {c["id"] for t in said["turns"] if t.get("copied") for c in t["calls"]}
        return sum(1 for a in agents if (a.get("meta") or {}).get("use") not in copied)

    def _turns(self, key: str, parent: dict, said: dict, calls: dict) -> None:
        news, replies = _pieces(said)
        for n, turn in enumerate(said["turns"]):
            if turn.get("copied"):
                continue
            used = turn.get("usage") or {}
            attributes = {KIND: "LLM", MODEL: turn.get("model") or None, PROVIDER: "anthropic",
                          INPUT: self._join(news.get(n, [])), OUTPUT: self._join(replies.get(n, []))}
            if used:
                prompt = used.get("in", 0) + used.get("cache_read", 0) + used.get("cache_write", 0)
                attributes.update({PROMPT: prompt, COMPLETION: used.get("out", 0), TOTAL: prompt + used.get("out", 0),
                                   CACHE_READ: used.get("cache_read", 0), CACHE_WRITE: used.get("cache_write", 0)})
            self.span(f"{key}|turn|{n}", parent, f"turn {n}", turn.get("start"), turn.get("end") or turn.get("at"), attributes)
            for m, call in enumerate(turn["calls"]):
                where = f"{key}|call|{call.get('id') or f'{n}.{m}'}"
                size = (call.get("result") or [None])[0]
                tool = self.span(where, parent, call.get("name") or "tool", call.get("at"), call.get("done"), {
                    KIND: "TOOL", TOOL_NAME: call.get("name") or None, INPUT: self.text(call.get("text")),
                    OUTPUT: self.text(call.get("out")), RESULT_CHARS: size, ERROR: True if call.get("error") else None})
                if call.get("id"):
                    calls[call["id"]] = {"span": tool, "key": where}

    def _join(self, pieces: list) -> str:
        return "\n\n".join(text for text in (self.text(mark) for mark in pieces) if text)


def _pieces(said: dict) -> tuple[dict, dict]:
    """流れ（seq）から、往復ごとの新しく入った字（前の往復の後の指示と道具の結果。最初の往復の前の指示はノードの span に置く）と返事の
    字（返事と考え）の番号"""
    news, replies, pending, now = {}, {}, [], None
    for row in said["seq"]:
        kind = row[0]
        if kind == "turn":
            now = row[1]
            news[now] = pending if now > 0 else []
            pending = []
        elif kind in ("user", "result"):
            pending.append(row[1])
        elif kind in ("say", "think") and now is not None:
            replies.setdefault(now, []).append(row[1])
    return news, replies


def _opening(said: dict, texts: dict) -> str:
    """system と道具の一覧と最初の往復の前の指示（ノードの span と下請けの span に 1 度だけ置く）"""
    parts = []
    system = "\n\n".join(texts.get(mark, "") for mark in said.get("system") or [])
    if system:
        parts.append(f"system:\n{system}")
    if said.get("tools"):
        parts.append("tools: " + ", ".join(str(tool[0]) for tool in said["tools"]))
    first = []
    for row in said["seq"]:
        if row[0] == "turn":
            break
        if row[0] == "user":
            first.append(texts.get(row[1], ""))
    if first:
        parts.append("prompt:\n" + "\n\n".join(first))
    return "\n\n".join(parts)


def _node(e: dict, table: list) -> dict:
    group = e["kind"] in runread.GROUP_KINDS
    attributes = {KIND: "AGENT" if e["kind"] in runread.AI_KINDS else "CHAIN", PATH: e["path"], LOOP: _loop(e["loop"]),
                  NODE_KIND: e["kind"], STATUS: e.get("status") or "", STAGE: table[e["stage"] - 1]["name"] if e.get("stage") else None,
                  ERROR: e.get("error") or None, OUTPUT: (e.get("output") or None)}
    if not group:
        attributes[COST] = e.get("cost") or 0.0
        attributes[TURNS] = e.get("turns")
        for name, value in (e.get("usage") or {}).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                attributes[TOKENS + name] = value
    return attributes


def _parent(e: dict, events: list) -> dict | None:
    """e を中に持つ一番内の器の出来事（無ければ None）"""
    best = None
    for g in events:
        if g is e or g["kind"] not in runread.GROUP_KINDS or not _under(e, g):
            continue
        if best is None or len(g["tokens"]) > len(best["tokens"]) or (len(g["tokens"]) == len(best["tokens"]) and _holds(g, e)):
            best = g
    return best


def _under(e: dict, g: dict) -> bool:
    """e が器 g の中の出来事か: 道が g の道の下で、同じ run なら外の周の番号が g と同じ（繰り返しの器は周を 1 つ深く持つ）。子の run
    （g が子の run を起こすノード）の出来事は run が違い、周の番号は子の中だけの物なので比べない"""
    if len(e["tokens"]) <= len(g["tokens"]) or e["tokens"][:len(g["tokens"])] != g["tokens"]:
        return False
    if e["run"] != g["run"]:
        return g["kind"] == "workflow"
    depth = len(g["loop"])
    if g["kind"] == runread.LOOP_GROUP:
        return len(e["loop"]) > depth and e["loop"][:depth] == g["loop"]
    return e["loop"][:depth] == g["loop"]


def _holds(g: dict, e: dict) -> bool:
    end = g.get("end")
    return runread.when(g["start"]) <= runread.when(e["start"]) and (not end or runread.when(e["start"]) <= runread.when(end))


def _costs(data: dict, events: list, table: list) -> str:
    """run の span の出力: 段ごとと AI のノードの上位の費用の表（Archon の値。Phoenix の費用の欄は値段の表から計算し直すので、正の
    内訳はここで読む）"""
    lines = []
    summed = (data.get("stages") or {}).get("run") or []
    if summed:
        lines.append("stage\tcost_usd")
        lines += [f"{table[n]['name']}\t{row.get('cost', 0.0):.4f}" for n, row in enumerate(summed) if row.get("cost")]
    ai = sorted((e for e in events if e["kind"] in runread.AI_KINDS), key=lambda e: -(e.get("cost") or 0.0))[:TOP]
    if ai:
        lines += ["", "node\tloop\tcost_usd"] if lines else ["node\tloop\tcost_usd"]
        lines += [f"{e['path']}\t{_loop(e['loop'])}\t{(e.get('cost') or 0.0):.4f}" for e in ai]
    return "\n".join(lines)


def _all(said: dict):
    yield said
    for agent in said.get("agents") or []:
        yield from _all(agent)


def _key(e: dict) -> str:
    return f"event|{e['run']}|{e['path']}|{_loop(e['loop'])}|{e['start']}"


def _loop(loop) -> str:
    return ".".join(str(k) for k in loop)


def _first(events: list):
    times = [e["start"] for e in events if e.get("start")]
    return min(times, key=runread.when) if times else None


def _last(events: list):
    times = [t for e in events for t in (e.get("start"), e.get("end")) if t]
    return max(times, key=runread.when) if times else None


def _plus(start: str, seconds) -> str | None:
    if seconds is None:
        return None
    end = runread.when(start) + timedelta(seconds=seconds)
    return end.strftime("%Y-%m-%dT%H:%M:%S.") + f"{end.microsecond // 1000:03d}Z"


def _hash(text: str, size: int) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:size]
