"""Claude Code の会話の記録（隔離した設定の `projects/<フォルダ>/<会話の id>.jsonl`）の読み。LLM に入った物（system・道具・添え書き・
指示）と、往復ごとの道具の呼び出しとトークンを取る。

Claude Code の版は工場が止めていないので、記録の形は試験で照らせない（人が見る）。読まない型の行は型ごとに数えて返し、黙って落とさない。

- find(projects, preview) -> run の記録の会話の id の頭（sessionPreview）に当たる記録のパス（無ければ None。Claude Code が消した古い記録は結べない）
- read(path, keep) -> 1 本の会話。keep は同じ字を 1 つにして番号で指す関数（同じ system を会話ごとに持たない）
"""
import json
from pathlib import Path

READ_TYPES = ("user", "assistant", "api-request-shape", "api-request-blob", "cost-state")
REMINDER = "<system-reminder>"


def find(projects: Path, preview: str) -> Path | None:
    if not preview or not projects.is_dir():
        return None
    return next(iter(sorted(projects.glob(f"*/{preview}*.jsonl"))), None)


def read(path: Path, keep) -> dict:
    got = {"system": [], "tools": [], "inject": [], "prompt": None, "turns": [], "seq": [], "cost": None, "usage": None, "unread": {}}
    turns, by_id, results = [], {}, {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            _count(got, "JSON でない行")
            continue
        kind = row.get("type")
        if kind not in READ_TYPES:
            _count(got, f"読まない型 {kind}")
            continue
        message = row.get("message") or {}
        if kind == "api-request-shape" and not got["system"]:
            shape = row.get("shape") or {}
            got["system"] = [keep(part.get("text", "")) for part in shape.get("system") or []]
            got["tools"] = [[tool.get("name", "?"), len(json.dumps(tool, ensure_ascii=False))] for tool in shape.get("tools") or []]
        elif kind == "api-request-blob":
            _inject(got, message, keep)
        elif kind == "user":
            _user(got, message, keep, results)
        elif kind == "assistant":
            _assistant(got, message, keep, turns, by_id)
        elif kind == "cost-state":
            got["cost"], got["usage"] = row.get("totalCostUSD"), row.get("modelUsage")
    for turn in turns:
        for call in turn["calls"]:
            call["result"] = results.get(call.pop("id"))
    got["turns"] = turns
    return got


def _inject(got, message, keep):
    """添え書きは system の片と <system-reminder> の片だけ。指示そのものと道具の結果も blob に載るので、数えると二重になる"""
    for part in message.get("content") or []:
        text = part.get("text") if isinstance(part, dict) else None
        if text and (message.get("role") == "system" or text.lstrip().startswith(REMINDER)):
            mark = keep(text)
            if mark not in [i[1] for i in got["inject"]]:
                got["inject"].append([message.get("role", ""), mark])


def _user(got, message, keep, results):
    content = message.get("content")
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    for part in content or []:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "tool_result":
            body = part.get("content")
            body = body if isinstance(body, str) else "\n".join(p.get("text", "") for p in body or [] if isinstance(p, dict))
            results[part.get("tool_use_id")] = [len(body), _clip(body, 600), bool(part.get("is_error"))]
            got["seq"].append(["result", keep(body), bool(part.get("is_error"))])
        elif part.get("type") == "text":
            if got["prompt"] is None:
                got["prompt"] = keep(part["text"])
            got["seq"].append(["user", keep(part["text"])])


def _assistant(got, message, keep, turns, by_id):
    """1 つの返事は content の片ごとに行が分かれ、同じ message.id を持つ"""
    ident = message.get("id") or str(len(turns))
    if ident not in by_id:
        by_id[ident] = {"usage": {}, "calls": [], "say": ""}
        turns.append(by_id[ident])
    turn = by_id[ident]
    usage = message.get("usage") or {}
    if usage:
        counted = {"in": usage.get("input_tokens", 0), "cache_read": usage.get("cache_read_input_tokens", 0),
                   "cache_write": usage.get("cache_creation_input_tokens", 0), "out": usage.get("output_tokens", 0)}
        if not turn["usage"]:
            got["seq"].append(["usage", counted])
        turn["usage"] = counted
    for part in message.get("content") or []:
        kind = part.get("type") if isinstance(part, dict) else None
        if kind == "tool_use":
            turn["calls"].append({"id": part.get("id"), "name": part.get("name"), "input": _clip(_text(part.get("input")), 400)})
            got["seq"].append(["call", part.get("name"), keep(json.dumps(part.get("input"), ensure_ascii=False, indent=1))])
        elif kind == "text" and part.get("text"):
            turn["say"] = _clip(part["text"], 300)
            got["seq"].append(["say", keep(part["text"])])
        elif kind == "thinking" and part.get("thinking"):
            got["seq"].append(["think", keep(part["thinking"])])


def _count(got, what):
    got["unread"][what] = got["unread"].get(what, 0) + 1


def _text(value) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _clip(text: str, size: int) -> str:
    return text if len(text) <= size else text[:size] + f"\n…（残り {len(text) - size} 字）"
