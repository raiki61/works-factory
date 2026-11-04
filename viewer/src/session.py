"""Claude Code の会話の記録（隔離した設定の `projects/<フォルダ>/<会話の id>.jsonl`）の読み。LLM に入った物（system・道具・添え書き・
指示）と、往復ごとの道具の呼び出しとトークンを取る。

Claude Code の版は工場が止めていないので、記録の形は試験で照らせない（人が見る）。行の型は、読む型と読まない型（訳つき。UNREAD_TYPES）
に分け、どちらでもない知らない型の行は型ごとに数えて返し、黙って落とさない（読まない型は数えない。ページの帯の数が本当に読めなかった
物を指す）。読む型の行の中の欄の形が違う行も、落ちずに数え、その行の値は何も書かない（runread.SHAPELESS）。ただし LLM に入った字を別の型から読む型（READ_FROM。読まない attachment と、往復の始めの時刻だけを読む api-request）は、その
代わりの型が記録に無い会話では、知らない型と同じく数える（代わりが無ければ LLM に入った字が帯から消えるので）。

- find(projects, preview) -> run の記録の会話の id の頭（sessionPreview）に当たる記録のパス（無ければ None。Claude Code が消した古い記録は結べない。
  2 つ以上に当たれば黙って選ばずに LookupError。頭が 16 進の字と - でなければ探さずに ValueError）
- collect(run, projects, keep) -> run の出来事の会話を読んだ物（鍵は会話の id の頭）。当たる記録が 2 つ以上の頭と、16 進の字と - でない頭は
  run["unread"] に数える。
  続けた会話（出来事の origin が runread.RESUMED）は、その出来事の始めを since にして読む
- read(path, keep, since) -> 1 本の会話。流れ（seq）は LLM に入った順の片で、往復の最初の行で ["turn", 往復の番号] を置く（usage を持つ
  行を待たない。トークンは往復の usage から後で埋め、usage の無い往復は空のまま。1 つの返事は行が分かれ、出力のトークンは終わりの行で
  数え終わるので、流れに写さない）。keep は同じ字を 1 つにして番号で指す関数（同じ system を会話ごとに持たない）。system と道具の一覧
  （api-request-shape）と添え書き（api-request-blob）は、その型の行が記録に在ったかを recorded に持つ（無ければページは欄を空にせず
  「記録に無い」と出す。普通の利用者の Claude Code でこの 2 つの型が出るかは確かめていない）。往復は最初の行の時刻 at を持ち、道具の
  呼び出しは切る前の入力の字の番号 text を持ち、会話は作業の場所 cwd（最初に cwd を持つ行の値）を持つ。
  since が在れば、それより前の往復に copied を付ける（続けた会話の記録は前の会話の往復を写して持つ。無駄の手がかりは数えず、流れには
  残す。LLM に入った物なので）。読めない時刻の往復は時刻を持たず、読めなかった物に数える。
  トレースの組み（src/trace.py）のために、往復は始め start（返事の行の requestRef が指す api-request の時刻。無ければ前の user の行
  〔道具の結果か指示〕の時刻、それも無ければ最初の行の時刻）と終わり end（同じ message.id の最後の行の時刻）と模型 model を、道具の
  呼び出しは id・始め at（tool_use の行の時刻）・結果の時刻 done・結果の字の番号 out・誤りの印 error を、会話は読めた時刻の最初と最後
  span と、下請け agents（<会話の id>/subagents/ の agent-<id>.jsonl を read で読んだ物に、id と meta の欄 AGENT_META を足した物）を持つ
"""
import json
import re
from pathlib import Path

import runlog   # lib/（viewer/src/__init__.py が sys.path に足す）
from viewer.src import runread

SHAPE = "api-request-shape"
BLOB = "api-request-blob"
# API への頼みの印（版・模型・betas）。往復の始めの時刻だけを読み、LLM に入った字は api-request-shape と api-request-blob から読む
REQUEST = "api-request"
READ_TYPES = ("user", "assistant", SHAPE, BLOB, REQUEST, "cost-state")
UNREAD_TYPES = {
    "attachment": "Claude Code が添えた物（sandbox の説明・hook の出力など）。LLM に入った字は api-request-blob から読む",
    "queue-operation": "指示の待ち行列の出し入れの印。指示そのものは user の行から読む",
    "last-prompt": "最後の指示の頭の控え。指示そのものは user の行から読む",
    "ai-title": "Claude Code が付けた会話の題",
    "atis-latch": "Claude Code の中の印で、会話の中身を持たない",
    "mode": "権限のモードの印",
    "tools-used": "使った道具の名の控え。呼び出しそのものは assistant の tool_use から読む",
}
# LLM に入った字を別の型から読む型（読まない attachment と、時刻だけを読む api-request）と、その代わりの型（1 つでも記録に無ければ数える）
READ_FROM = {"attachment": (BLOB,), REQUEST: (SHAPE, BLOB)}
# 下請け（Agent の道具で起こした別の会話）の記録の置き場: <会話の id>/subagents/agent-<id>.jsonl と同じ名の .meta.json
AGENTS_DIR = "subagents"
AGENT_HEAD = "agent-"
META = ".meta.json"
# 下請けの meta の欄（返す名 → 記録の名）。toolUseId は親の会話の Agent の tool_use の id
AGENT_META = {"use": "toolUseId", "description": "description", "type": "agentType", "depth": "spawnDepth", "shape": "requestShape"}
BAD_META = "読めない下請けの meta"
REMINDER = "<system-reminder>"
# 往復の usage の欄（返す名 → 記録の名）
USAGE = {"in": "input_tokens", "cache_read": "cache_read_input_tokens", "cache_write": "cache_creation_input_tokens", "out": "output_tokens"}


AMBIGUOUS = "会話の id の頭が 2 つ以上の記録に当たる"
# 会話の id の頭に通す字（Claude Code の会話の id は UUID）。ほかの字（/・..・glob の字）は置き場の外や別の会話に当たるので通さない
PREVIEW = re.compile(r"[0-9A-Fa-f-]+")
STRANGE = "会話の id の頭が 16 進の字と - でない"


def find(projects: Path, preview: str) -> Path | None:
    if not preview or not projects.is_dir():
        return None
    if not PREVIEW.fullmatch(preview):
        raise ValueError(f"{STRANGE}: {preview!r}")
    hits = sorted(projects.glob(f"*/{preview}*.jsonl"))
    if len(hits) > 1:
        raise LookupError(f"{AMBIGUOUS}: {preview}")
    return hits[0] if hits else None


def collect(run: dict, projects: Path, keep) -> dict:
    sessions = {}
    for event in run["events"]:
        preview = event.get("session")
        if not preview or preview in sessions:
            continue
        try:
            found = find(projects, preview)
        except (LookupError, ValueError) as error:
            what = AMBIGUOUS if isinstance(error, LookupError) else STRANGE
            run["unread"][what] = run["unread"].get(what, 0) + 1
            sessions[preview] = None
            continue
        if found is not None:
            sessions[preview] = read(found, keep, event.get("start") if event.get("origin") == runread.RESUMED else None)
    return {preview: got for preview, got in sessions.items() if got is not None}


def read(path: Path, keep, since: str | None = None) -> dict:
    got = {"system": [], "tools": [], "inject": [], "turns": [], "seq": [], "cost": None, "unread": {},
           "recorded": {SHAPE: False, BLOB: False}, "cwd": "", "span": [None, None], "agents": []}
    turns, by_id, results, held = [], {}, {}, {}
    # api-request の id → 時刻・道具の呼び出しの id → 結果の時刻と字・最後の user の行の時刻（往復の始めの代わり）
    clock = {"requests": {}, "ends": {}, "user": None}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            _count(got, "JSON でない行")
            continue
        if not isinstance(row, dict):
            _count(got, runread.OBJECTLESS)
            continue
        kind = row.get("type")
        if not isinstance(kind, (str, type(None))):
            # 型の欄が字でない行は、型を引く前に数える（列や object の型は表を引く所で落ちる）
            _count(got, runread.SHAPELESS)
            continue
        if kind in READ_FROM:
            held[kind] = held.get(kind, 0) + 1
        if kind in UNREAD_TYPES:
            continue
        if kind not in READ_TYPES:
            _count(got, f"知らない型 {kind}")
            continue
        try:
            cwd = row.get("cwd")
            ts = _time(row)
            if kind == SHAPE:
                write = _shape(got, row.get("shape") or {}, keep)
            elif kind == BLOB:
                write = _inject(got, row.get("message") or {}, keep)
            elif kind == "user":
                write = _user(got, row.get("message") or {}, keep, results, clock, ts)
            elif kind == "assistant":
                write = _assistant(got, row, keep, turns, by_id, clock)
            elif kind == REQUEST:
                write = _request(row, clock, ts)
            else:
                write = _cost(got, row)
        except runread.SHAPE_ERRORS:
            # 欄の形が違う行（message・shape が object でない・content が字でも列でもない・字の片に text が無いか字でない・費用が
            # 数でないなど）は、何も書かずに数える
            _count(got, runread.SHAPELESS)
            continue
        if kind in got["recorded"]:
            got["recorded"][kind] = True
        if not got["cwd"] and isinstance(cwd, str):
            got["cwd"] = cwd
        if ts:
            first, last = got["span"]
            got["span"] = [first or ts, ts if not last or runread.when(ts) >= runread.when(last) else last]
        write()
    cut = runread.try_when(since) if since else None
    for turn in turns:
        ref, after = turn.pop("ref"), turn.pop("after")
        turn["start"] = (clock["requests"].get(ref) if ref else None) or after or turn["at"]
        for call in turn["calls"]:
            call["result"] = results.get(call["id"])
            call.update(clock["ends"].get(call["id"]) or {"done": None, "out": None, "error": False})
        if cut and turn["at"] and runread.when(turn["at"]) < cut:
            turn["copied"] = True
    got["turns"] = turns
    for kind, n in held.items():
        if not all(got["recorded"][sub] for sub in READ_FROM[kind]):
            got["unread"][f"字を読む代わりの型が記録に無い {kind}"] = n
    got["agents"] = _agents(path, keep, since, got)
    return got


def _agents(path: Path, keep, since, got) -> list[dict]:
    """下請けの記録（<会話の id>/subagents/agent-<id>.jsonl）を read で読み、id と meta の欄を足した物。meta が無いか読めない下請けも
    読み（親に結べないことは src/trace.py が数える）、読めない meta は got の読めなかった物に数える"""
    folder = path.with_suffix("") / AGENTS_DIR
    if not folder.is_dir():
        return []
    out = []
    for file in sorted(folder.glob(f"{AGENT_HEAD}*.jsonl")):
        meta, told = {}, file.with_name(file.stem + META)
        if told.is_file():
            try:
                raw = json.loads(told.read_text(encoding="utf-8", errors="replace"))
                meta = {short: raw.get(name) for short, name in AGENT_META.items()}
                if not isinstance(raw, dict) or any(not isinstance(v, (str, int, type(None))) or isinstance(v, bool) for v in meta.values()):
                    raise TypeError(f"欄の形が違う meta {raw!r}")
            except (ValueError, *runread.SHAPE_ERRORS):
                _count(got, BAD_META)
                meta = {}
        agent = read(file, keep, since)
        agent.update(id=file.stem[len(AGENT_HEAD):], meta=meta)
        out.append(agent)
    return out


# 行の読みはどれも 2 つに分ける。先に書き込む値を全部取り出して形を確かめ（形が違えば TypeError などで止まり、read が行ごと数える）、
# 書き込みは返す関数 write に置く。read は全部が通った行だけで write を呼ぶので、途中で止まった行は流れ・往復・添え書き・字の束
# （keep）を 1 つも変えない。write の中では形を確かめ終えた値だけを使い、止まらない


def _shape(got, shape, keep):
    """system と道具の一覧は、最初に system を持つ行の物"""
    if got["system"]:
        return lambda: None
    tools = [[runread.plain(tool.get("name", "?")), len(json.dumps(tool, ensure_ascii=False))] for tool in shape.get("tools") or []]
    system = [_string(part.get("text", "")) for part in shape.get("system") or []]

    def write():
        got["system"] = [keep(text) for text in system]
        got["tools"] = tools
    return write


def _inject(got, message, keep):
    """添え書きは system の片と <system-reminder> の片だけ。指示そのものと道具の結果も blob に載るので、数えると二重になる"""
    role = runread.plain(message.get("role")) or ""
    texts = [runread.plain(part.get("text")) if isinstance(part, dict) else None for part in message.get("content") or []]
    picked = [text for text in texts if text and (role == "system" or text.lstrip().startswith(REMINDER))]

    def write():
        for text in picked:
            mark = keep(text)
            if mark not in [i[1] for i in got["inject"]]:
                got["inject"].append([role, mark])
    return write


def _user(got, message, keep, results, clock, ts):
    """指示と道具の結果。結果は呼び出しの id ごとに長さ（results）と、行の時刻・字・誤りの印（clock の ends。トレースの道具の終わり）を持つ。
    行の時刻は次の往復の始めの代わり（api-request の無い往復）"""
    found, pieces, ends = {}, [], {}
    for part in _parts(message.get("content")):
        if not isinstance(part, dict):
            continue
        if part.get("type") == "tool_result":
            body = "\n".join(_string(p.get("text", "")) for p in _parts(part.get("content")) if isinstance(p, dict))
            ident, error = runread.plain(part.get("tool_use_id")), bool(part.get("is_error"))
            found[ident] = [len(body)]
            ends[ident] = (body, error)
            pieces.append(("result", body, error))
        elif part.get("type") == "text":
            pieces.append(("user", _string(part["text"])))

    def write():
        results.update(found)
        for ident, (body, error) in ends.items():
            clock["ends"][ident] = {"done": ts, "out": keep(body), "error": error}
        if ts:
            clock["user"] = ts
        got["seq"].extend([kind, keep(text), *rest] for kind, text, *rest in pieces)
    return write


def _request(row, clock, ts):
    """API への頼みの印は、往復の始めの時刻だけを読む（返事の行の requestRef がこの id を指す）"""
    ident = runread.plain(row.get("id"))

    def write():
        if ident and ts:
            clock["requests"][ident] = ts
    return write


def _assistant(got, row, keep, turns, by_id, clock):
    """1 つの返事は content の片ごとに行が分かれ、同じ message.id を持つ。往復の時刻は最初の行の時刻。往復と流れに入れる値（返事の
    id・トークンの数・道具の呼び出しの id と名・字）は、先に形を確かめる（後で使う無駄の手がかりと道具の結果の結びで落ちない）"""
    message = row.get("message") or {}
    at = row.get("timestamp") if isinstance(row.get("timestamp"), str) else None
    odd = bool(at) and runread.try_when(at) is None
    ident = runread.plain(message.get("id")) or str(len(turns))
    ref, model = runread.plain(row.get("requestRef")), runread.plain(message.get("model")) or ""
    usage = message.get("usage") or {}
    if usage:
        usage = {short: usage.get(name, 0) for short, name in USAGE.items()}
        if any(runlog.number(value) is None for value in usage.values()):
            raise TypeError(f"数でない usage {usage!r}")
    pieces = []
    for part in _parts(message.get("content")):
        kind = part.get("type") if isinstance(part, dict) else None
        if kind == "tool_use":
            pieces.append(("call", runread.plain(part.get("id")), runread.plain(part.get("name")),
                           json.dumps(part.get("input"), ensure_ascii=False, indent=1)))
        elif kind in ("text", "thinking"):
            # 偽の値（空の列・0）も形を確かめてから捨てる（空の字だけを流れに入れない）
            text = _string(part.get(kind))
            if text:
                pieces.append(("say" if kind == "text" else "think", text))

    def write():
        if odd:
            _count(got, "読めない時刻")
        if ident not in by_id:
            by_id[ident] = {"usage": {}, "calls": [], "at": None if odd else at, "end": None, "model": model, "ref": ref,
                            "after": clock["user"]}
            got["seq"].append(["turn", len(turns)])
            turns.append(by_id[ident])
        turn = by_id[ident]
        if at and not odd:
            turn["end"] = at
        if usage:
            turn["usage"] = usage
        for piece in pieces:
            if piece[0] == "call":
                _, call, name, text = piece
                mark = keep(text)
                turn["calls"].append({"id": call, "name": name, "text": mark, "at": None if odd else at})
                got["seq"].append(["call", name, mark])
            else:
                got["seq"].append([piece[0], keep(piece[1])])
    return write


def _time(row):
    """行の時刻（字で読める物だけ。読めない時刻は None。往復の読めない時刻は _assistant が数える）"""
    ts = row.get("timestamp")
    return ts if isinstance(ts, str) and runread.try_when(ts) is not None else None


def _cost(got, row):
    cost = row.get("totalCostUSD")
    if cost is not None and runlog.number(cost) is None:
        raise TypeError(f"数でない費用 {cost!r}")

    def write():
        got["cost"] = cost
    return write


def _parts(content) -> list:
    """message の content の片の列。字は字の片 1 つ（API の形で許される書き方）、None は空。ほかの形（object・数）は TypeError"""
    if content is None:
        return []
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return content
    raise TypeError(f"字でも列でもない content {content!r}")


def _string(value) -> str:
    """LLM に入った字。ほかの形（None も）は TypeError"""
    if isinstance(value, str):
        return value
    raise TypeError(f"字でない値 {value!r}")


def _count(got, what):
    got["unread"][what] = got["unread"].get(what, 0) + 1

