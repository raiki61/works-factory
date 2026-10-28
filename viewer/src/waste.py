"""無駄の手がかりの数え（無駄の手がかりの画面。docs/design/viewer.md の 6.9）。

選んだ run の記録（出来事・繰り返しの確かめ・会話）と作りの読みから、無駄かを見る人が決める材料の数を機械で数える。「無駄だ」とは
断じず、数えた事実だけを返す。記録で数えられない物は uncounted に並べ、黙って 0 にしない。読む部品（src/runread.py・src/session.py・
src/shape.py）の出す欄だけを読み、記録そのものは読み直さない。段（src/stages.py の attach が付ける出来事の stage）の後に呼ぶ。

- attach(data) -> data["waste"] に数えを置く（run が無ければ None）。欄は top（AI の手番の費用の大きい順）・time（時間の内訳）・
  rounds（繰り返した周）・idle（前と同じ出力・空の出力・出力の欄を引く先が無いノード）・context（文脈の重なり）・big（大きな道具の結果と
  往復ごとの積み上がり）・uncounted（数えられない物）。出来事は run["events"] の番号 event で、会話は run["sessions"] の鍵 session で指す
"""
import json
from datetime import datetime, timezone

from viewer.src import runread, shape
from viewer.src.stages import four

BIG = 10000    # 大きな道具の結果の線（字の数）。見る道具の表示の線で、決まりの数ではない
PAUSE = 300    # 前の往復から空いた秒がこれ以上の往復を出す（cache の既定の保ち時間 5 分）。見る道具の表示の線
READ_TOOL = "Read"
EMPTY = ("", "{}", "[]", "null")
UNCOUNTED = [
    "4 分けごとの費用（ドル）: 記録に在るのは手番ごとの費用の合計と 4 分けのトークンの数だけ。見る道具は値段の表を持たず、割らない",
    "script のノードがファイルを読んだか: 記録に無い。出力の欄を引く先が無いノードも、ファイルで渡した物（pointer）は読まれていることが多い",
    "重なりのトークンの数: system・道具の一覧・添え書きは字の数だけが記録に在る。トークンに直す係数を見る道具は持たない",
    "往復の数は 2 通り: Archon の数（手番の turns）と、会話の記録の返事の数（replies）。同じとは限らない",
]


def attach(data: dict) -> None:
    run = data["run"]
    if not run:
        data["waste"] = None
        return
    events, sessions, texts = run["events"], run.get("sessions") or {}, data["texts"]
    first = {}
    for n, e in enumerate(events):
        if e.get("session") in sessions:
            first.setdefault(e["session"], n)
    data["waste"] = {"top": _top(events, sessions), "time": _time_split(run), "rounds": _rounds(events, run["checks"]),
                     "idle": _idle(events, data["shape"]["graphs"]), "context": _context(events, sessions, first, texts),
                     "big": _big(sessions, first), "uncounted": UNCOUNTED}


def _top(events, sessions) -> dict:
    """AI の手番の費用の大きい順。割合は手番の費用の和に対する物"""
    ai = [(n, e) for n, e in enumerate(events) if e["kind"] in runread.AI_KINDS]
    total = sum(e["cost"] for _, e in ai)
    rows = [{"event": n, "tokens": e["tokens"], "stage": e.get("stage"), "cost": round(e["cost"], 6),
             "share": round(e["cost"] / total, 4) if total else None, "seconds": _length(e), "turns": e.get("turns"),
             "replies": len((sessions.get(e.get("session")) or {}).get("turns") or []) if e.get("session") in sessions else None,
             "tokens4": four(e["usage"]) if e.get("usage") else None} for n, e in ai]
    rows.sort(key=lambda row: (-row["cost"], row["event"]))
    return {"rows": rows, "cost": round(total, 6), "odd": [row["event"] for row in rows if row["tokens4"] and row["tokens4"]["odd"]]}


def _time_split(run) -> dict:
    """人の答え待ち（wait のノード）・AI（AI のノード）・機械（ほか）の出来事の長さの和。並んで走れば重なるので、和は run の長さを
    越えうる。中の出来事を束ねる器（繰り返し・子の run を起こすノード）は二重になるので数えない"""
    own = [e for e in run["events"] if e["kind"] not in runread.GROUP_KINDS]
    split = {"wait": 0.0, "ai": 0.0, "machine": 0.0}
    for e in own:
        split["wait" if e["kind"] == runread.WAIT_NODE else "ai" if e["kind"] in runread.AI_KINDS else "machine"] += _length(e)
    return {"run": run["seconds"], **{key: round(value, 1) for key, value in split.items()},
            "waits": sorted(({"event": n, "seconds": _length(e)} for n, e in enumerate(run["events"]) if e["kind"] == runread.WAIT_NODE),
                            key=lambda row: -row["seconds"])}


def _rounds(events, checks) -> list[dict]:
    """2 周以上回った繰り返しの器ごとの周。周は器の中の出来事（道が器の下で、外の周の番号が器と同じ物）を、器の周の番号で分けた物。
    周の終わりの確かめ（until_bash の終了の値。runread の checks）は、道と周の番号と器の時刻の内で当てる。前の周と落ちた道と確かめの値が
    同じ周に same を付ける"""
    out = []
    for n, group in enumerate(events):
        if group["kind"] != "loop_group":
            continue
        head, depth = group["tokens"], len(group["loop"])
        by = {}
        for m, e in enumerate(events):
            if e is not group and e["tokens"][:len(head)] == head and len(e["tokens"]) > len(head) and len(e["loop"]) > depth \
                    and e["loop"][:depth] == group["loop"]:
                by.setdefault(e["loop"][depth], []).append((m, e))
        if len(by) < 2:
            continue
        rows, before = [], None
        for k in sorted(by):
            inner = [e for _, e in by[k] if e["kind"] not in runread.GROUP_KINDS]
            times = [t for _, e in by[k] for t in (e["start"], e["end"]) if t]
            failed = sorted("/".join(e["tokens"][len(head):]) for e in inner if e["status"] == "failed")
            check = _check(checks, head, k, group)
            here = (failed, check["exit"] if check else None)
            rows.append({"round": k, "events": [m for m, _ in by[k]], "cost": round(sum(e["cost"] for e in inner), 6),
                         "seconds": _seconds(min(times, key=_at), max(times, key=_at)) if times else None,
                         "ai": sum(1 for e in inner if e["kind"] in runread.AI_KINDS), "failed": failed, "check": check,
                         "same": before == here})
            before = here
        out.append({"event": n, "tokens": head, "stage": group.get("stage"), "rounds": rows,
                    "cost": round(sum(row["cost"] for row in rows), 6)})
    return out


def _check(checks, head, k, group) -> dict | None:
    suffix = f"-iteration-{k}"
    for row in checks:
        step = row["step"]
        if not step.endswith(suffix):
            continue
        ids = [t for path in [*row["node"], step[:-len(suffix)]] for t in shape.tokens(path)]
        if ids == head and _inside(row["at"], group):
            return {"exit": row["exit"], "stdout": row["stdout"][:300], "stderr": row["stderr"][:300]}
    return None


def _inside(at, group) -> bool:
    if not at or not group["start"]:
        return True
    return _at(group["start"]) <= _at(at) and (not group["end"] or _at(at) <= _at(group["end"]))


def _idle(events, graphs) -> dict:
    """前と同じ出力（同じ道の前の起動の出力と字のまま同じ）・空の出力・出力の欄を引く先が無いノード（作りの読みで、同じ graph の中に
    `$<id>.output` の引きが 1 つも無く、graph の返りでもない AI・script・bash のノード。工場は大きい物をファイルに置いて pointer で
    渡すので、引きが無くても読まれていることが多い）。引く先の無いノードは、今の作りの数と、この run で走った物を出す"""
    last, same, empty = {}, [], []
    for n, e in sorted(enumerate(events), key=lambda pair: (_at(pair[1]["start"]) if pair[1]["start"] else datetime.min.replace(tzinfo=timezone.utc),
                                                            pair[0])):
        if "output" not in e or e["kind"] in runread.GROUP_KINDS:
            continue
        key = tuple(e["tokens"])
        if e["output"].strip() in EMPTY:
            empty.append(n)
        elif key in last and events[last[key]]["output"] == e["output"]:
            same.append({"event": n, "before": last[key]})
        last[key] = n
    unread, counted = _unreferenced(graphs)
    ran = {}
    for n, e in enumerate(events):
        at = e.get("at") or {}
        spot = (at.get("graph"), at.get("node", "").split("/")[-1])
        if spot in unread:
            ran.setdefault("/".join(spot), []).append(n)
    return {"same": same, "empty": empty, "unread": {"nodes": counted, "none": sorted("/".join(spot) for spot in unread),
                                                     "ran": [{"node": node, "events": got} for node, got in sorted(ran.items())]}}


def _unreferenced(graphs) -> tuple[set, int]:
    """引く先の無いノード {(graph, id)} と、数えたノード（AI・script・bash）の数"""
    out, counted = set(), 0
    for folder, graph in graphs.items():
        items = list(shape.walk(graph["items"]))
        text = json.dumps([{k: v for k, v in item.items() if k not in ("kids", "md", "system_md", "doc", "desc")} for item in items],
                          ensure_ascii=False)
        used = {m[1] for m in shape.REF.finditer(text)}
        for item in items:
            if item["kind"] not in ("ai", "script", "bash"):
                continue
            counted += 1
            if item["id"] not in used and item["id"] != graph["returns"]:
                out.add((folder, item["id"]))
    return out, counted


def _context(events, sessions, first, texts) -> dict:
    """文脈の重なり。system・道具の一覧・添え書きの片の、同じ物が入った会話の数と字の数。cache の読みと書きの和と割合。同じファイルの
    読み直し（Read のパスを runread.where で run ごとの頭を外して比べる）。前の往復から PAUSE 秒以上空いた往復"""
    def size(marks):
        return sum(len(texts.get(mark, "")) for mark in marks)

    systems, tools, injects, reads, pauses = {}, {}, {}, {}, []
    for sid, got in sessions.items():
        if got["system"]:
            systems.setdefault(tuple(got["system"]), []).append(sid)
        if got["tools"]:
            row = tools.setdefault(tuple(name for name, _ in got["tools"]), {"chars": sum(n for _, n in got["tools"]), "sessions": 0})
            row["sessions"] += 1
        for _, mark in got["inject"]:
            injects.setdefault(mark, []).append(sid)
        before = None
        for k, turn in enumerate(got["turns"]):
            for call in turn["calls"]:
                if call["name"] != READ_TOOL or not call.get("text"):
                    continue
                try:
                    path = json.loads(texts.get(call["text"], "")).get("file_path")
                except (ValueError, AttributeError):
                    path = None
                if isinstance(path, str):
                    row = reads.setdefault(runread.where(path, got.get("cwd") or ""), {"times": 0, "chars": 0, "sessions": set()})
                    row["times"] += 1
                    row["chars"] += (call.get("result") or [0])[0]
                    row["sessions"].add(sid)
            if turn.get("at") and before:
                gap = _seconds(before, turn["at"])
                if gap is not None and gap >= PAUSE:
                    pauses.append({"session": sid, "event": first.get(sid), "turn": k, "gap": gap,
                                   "cache_write": (turn["usage"] or {}).get("cache_write")})
            before = turn.get("at") or before
    total = {field: 0 for field in ("input", "output", "cacheRead", "cacheWrite")}
    for e in events:
        if e["kind"] in runread.AI_KINDS and e.get("usage"):
            for field in total:
                total[field] += e["usage"].get(field) or 0
    again = sorted(({"path": path, "times": row["times"], "chars": row["chars"], "sessions": len(row["sessions"])}
                    for path, row in reads.items() if row["times"] > 1), key=lambda row: (-row["chars"], row["path"]))
    return {"sessions": len(sessions),
            "system": sorted(({"marks": list(marks), "chars": size(marks), "sessions": len(sids)} for marks, sids in systems.items()),
                             key=lambda row: -row["sessions"]),
            "tools": sorted(({"names": list(names), **row} for names, row in tools.items()),
                            key=lambda row: -row["sessions"]),
            "inject": sorted(({"mark": mark, "chars": size([mark]), "sessions": len(set(sids))} for mark, sids in injects.items()
                              if len(set(sids)) > 1), key=lambda row: (-row["sessions"], -row["chars"])),
            "cache": {**total, "read_share": round(total["cacheRead"] / total["input"], 4) if total["input"] else None},
            "reads": {"files": len(reads), "again": again}, "pauses": pauses}


def _big(sessions, first) -> dict:
    """BIG 字を超える道具の結果（大きい順）と、会話ごとの往復の入力のトークン（新しく読んだ分と cache の読み書きの和）の積み上がり"""
    results, climb, calls = [], [], 0
    for sid, got in sessions.items():
        grown = []
        for k, turn in enumerate(got["turns"]):
            for call in turn["calls"]:
                calls += 1
                chars = (call.get("result") or [0])[0]
                if chars > BIG:
                    results.append({"session": sid, "event": first.get(sid), "turn": k, "name": call["name"], "chars": chars})
            usage = turn["usage"] or {}
            if usage:
                grown.append(usage.get("in", 0) + usage.get("cache_read", 0) + usage.get("cache_write", 0))
        if grown:
            climb.append({"session": sid, "event": first.get(sid), "turns": len(got["turns"]), "first": grown[0], "last": grown[-1],
                          "peak": max(grown)})
    results.sort(key=lambda row: -row["chars"])
    climb.sort(key=lambda row: -(row["last"] - row["first"]))
    return {"line": BIG, "calls": calls, "results": results, "climb": climb}


def _length(event) -> float:
    return (_seconds(event["start"], event["end"]) or 0.0) if event["start"] and event["end"] else 0.0


def _seconds(start, end):
    try:
        return round((_at(end) - _at(start)).total_seconds(), 1)
    except (TypeError, ValueError):
        return None


def _at(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))
