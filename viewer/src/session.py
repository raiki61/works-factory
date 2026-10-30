"""Claude Code の会話の記録（隔離した設定の `projects/<フォルダ>/<会話の id>.jsonl`）の読み。LLM に入った物（system・道具・添え書き・
指示）と、往復ごとの道具の呼び出しとトークンを取る。

Claude Code の版は工場が止めていないので、記録の形は試験で照らせない（人が見る）。行の型は、読む型と読まない型（訳つき。UNREAD_TYPES）
に分け、どちらでもない知らない型の行は型ごとに数えて返し、黙って落とさない（読まない型は数えない。ページの帯の数が本当に読めなかった
物を指す）。読む型の行の中の欄の形が違う行も、落ちずに数える（runread.SHAPELESS）。ただし読まない型のうち字を別の型から読む物（READ_FROM）は、その代わりの型が記録に無い会話では、知らない型と同じく数える
（代わりが無ければ LLM に入った字が帯から消えるので）。

- find(projects, preview) -> run の記録の会話の id の頭（sessionPreview）に当たる記録のパス（無ければ None。Claude Code が消した古い記録は結べない。
  2 つ以上に当たれば黙って選ばずに LookupError）
- collect(run, projects, keep) -> run の出来事の会話を読んだ物（鍵は会話の id の頭）。当たる記録が 2 つ以上の頭は run["unread"] に数える。
  続けた会話（出来事の origin が runread.RESUMED）は、その出来事の始めを since にして読む
- read(path, keep, since) -> 1 本の会話。流れ（seq）は LLM に入った順の片で、往復の最初の行で ["turn", 往復の番号] を置く（usage を持つ
  行を待たない。トークンは往復の usage から後で埋め、usage の無い往復は空のまま。1 つの返事は行が分かれ、出力のトークンは終わりの行で
  数え終わるので、流れに写さない）。keep は同じ字を 1 つにして番号で指す関数（同じ system を会話ごとに持たない）。system と道具の一覧
  （api-request-shape）と添え書き（api-request-blob）は、その型の行が記録に在ったかを recorded に持つ（無ければページは欄を空にせず
  「記録に無い」と出す。普通の利用者の Claude Code でこの 2 つの型が出るかは確かめていない）。往復は最初の行の時刻 at を持ち、道具の
  呼び出しは切る前の入力の字の番号 text を持ち、会話は作業の場所 cwd（最初に cwd を持つ行の値）を持つ（無駄の手がかりの数え。src/waste.py）。
  since が在れば、それより前の往復に copied を付ける（続けた会話の記録は前の会話の往復を写して持つ。無駄の手がかりは数えず、流れには
  残す。LLM に入った物なので）。読めない時刻の往復は時刻を持たず、読めなかった物に数える
"""
import json
from pathlib import Path

from viewer.src import runread

SHAPE = "api-request-shape"
BLOB = "api-request-blob"
READ_TYPES = ("user", "assistant", SHAPE, BLOB, "cost-state")
UNREAD_TYPES = {
    "attachment": "Claude Code が添えた物（sandbox の説明・hook の出力など）。LLM に入った字は api-request-blob から読む",
    "api-request": "API への頼みの印（版・模型・betas）。LLM に入った字は api-request-shape と api-request-blob から読む",
    "queue-operation": "指示の待ち行列の出し入れの印。指示そのものは user の行から読む",
    "last-prompt": "最後の指示の頭の控え。指示そのものは user の行から読む",
    "ai-title": "Claude Code が付けた会話の題",
    "atis-latch": "Claude Code の中の印で、会話の中身を持たない",
    "mode": "権限のモードの印",
}
# 読まない型のうち、LLM に入った字を別の型から読む物と、その代わりの型（1 つでも記録に無ければ数える）
READ_FROM = {"attachment": (BLOB,), "api-request": (SHAPE, BLOB)}
REMINDER = "<system-reminder>"


AMBIGUOUS = "会話の id の頭が 2 つ以上の記録に当たる"


def find(projects: Path, preview: str) -> Path | None:
    if not preview or not projects.is_dir():
        return None
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
        except LookupError:
            run["unread"][AMBIGUOUS] = run["unread"].get(AMBIGUOUS, 0) + 1
            sessions[preview] = None
            continue
        if found is not None:
            sessions[preview] = read(found, keep, event.get("start") if event.get("origin") == runread.RESUMED else None)
    return {preview: got for preview, got in sessions.items() if got is not None}


def read(path: Path, keep, since: str | None = None) -> dict:
    got = {"system": [], "tools": [], "inject": [], "turns": [], "seq": [], "cost": None, "unread": {},
           "recorded": {SHAPE: False, BLOB: False}, "cwd": ""}
    turns, by_id, results, held = [], {}, {}, {}
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
        if kind in UNREAD_TYPES:
            if kind in READ_FROM:
                held[kind] = held.get(kind, 0) + 1
            continue
        if kind not in READ_TYPES:
            _count(got, f"知らない型 {kind}")
            continue
        try:
            message = row.get("message") or {}
            if kind in got["recorded"]:
                got["recorded"][kind] = True
            if not got["cwd"] and isinstance(row.get("cwd"), str):
                got["cwd"] = row["cwd"]
            if kind == SHAPE and not got["system"]:
                shape = row.get("shape") or {}
                got["system"] = [keep(part.get("text", "")) for part in shape.get("system") or []]
                got["tools"] = [[tool.get("name", "?"), len(json.dumps(tool, ensure_ascii=False))] for tool in shape.get("tools") or []]
            elif kind == BLOB:
                _inject(got, message, keep)
            elif kind == "user":
                _user(got, message, keep, results)
            elif kind == "assistant":
                at = row.get("timestamp") if isinstance(row.get("timestamp"), str) else None
                if at and runread.try_when(at) is None:
                    _count(got, "読めない時刻")
                    at = None
                _assistant(got, message, keep, turns, by_id, at)
            elif kind == "cost-state":
                got["cost"] = row.get("totalCostUSD")
        except (AttributeError, KeyError, TypeError):
            # 欄の形が違う行（message・shape が object でない・字の片に text が無いか字でないなど）は、落ちずに数える
            _count(got, runread.SHAPELESS)
    cut = runread.try_when(since) if since else None
    for turn in turns:
        for call in turn["calls"]:
            call["result"] = results.get(call.pop("id"))
        if cut and turn["at"] and runread.when(turn["at"]) < cut:
            turn["copied"] = True
    got["turns"] = turns
    for kind, n in held.items():
        if not all(got["recorded"][sub] for sub in READ_FROM[kind]):
            got["unread"][f"字を読む代わりの型が記録に無い {kind}"] = n
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
            results[part.get("tool_use_id")] = [len(body)]
            got["seq"].append(["result", keep(body), bool(part.get("is_error"))])
        elif part.get("type") == "text":
            got["seq"].append(["user", keep(part["text"])])


def _assistant(got, message, keep, turns, by_id, at):
    """1 つの返事は content の片ごとに行が分かれ、同じ message.id を持つ。往復の時刻は最初の行の時刻"""
    ident = message.get("id") or str(len(turns))
    if ident not in by_id:
        by_id[ident] = {"usage": {}, "calls": [], "at": at}
        got["seq"].append(["turn", len(turns)])
        turns.append(by_id[ident])
    turn = by_id[ident]
    usage = message.get("usage") or {}
    if usage:
        turn["usage"] = {"in": usage.get("input_tokens", 0), "cache_read": usage.get("cache_read_input_tokens", 0),
                         "cache_write": usage.get("cache_creation_input_tokens", 0), "out": usage.get("output_tokens", 0)}
    for part in message.get("content") or []:
        kind = part.get("type") if isinstance(part, dict) else None
        if kind == "tool_use":
            mark = keep(json.dumps(part.get("input"), ensure_ascii=False, indent=1))
            turn["calls"].append({"id": part.get("id"), "name": part.get("name"), "text": mark})
            got["seq"].append(["call", part.get("name"), mark])
        elif kind == "text" and part.get("text"):
            got["seq"].append(["say", keep(part["text"])])
        elif kind == "thinking" and part.get("thinking"):
            got["seq"].append(["think", keep(part["thinking"])])


def _count(got, what):
    got["unread"][what] = got["unread"].get(what, 0) + 1

