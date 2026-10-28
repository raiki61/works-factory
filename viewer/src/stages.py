"""段の表（viewer/stages.json）と段ごとの集計（流れの画面。docs/design/viewer.md の 6.8）。

段は、line（メイングラフ）の一番上のノードを人の言葉で畳んだ単位で、見る道具だけの考え。表は工場の中に置かず、工場の中からも読まない
（viewer/AGENTS.md の E25）。出来事の段は、出来事の道の頭（line の一番上のノード。include・繰り返し・子の run の出来事も、道の頭は
line のノード）で引く。

- check(graphs) -> 照らしの問題の字の一覧。今の木の line の一番上のノードがどれもちょうど 1 つの段に入り、表の id がどれも line に在る
- attach(data) -> data["stages"] に段の表と、run が line の run なら段ごとの集計を足し、出来事と飛んだノードに段の番号 stage を付ける
"""
import json
from datetime import datetime
from pathlib import Path

import runlog   # lib/（viewer/src/__init__.py が sys.path に足す）
from viewer.src import runread

TABLE = json.loads((Path(__file__).resolve().parents[1] / "stages.json").read_text(encoding="utf-8"))
SHOWN = ("name", "line", "hands", "source", "nodes")


def check(graphs: dict) -> list[str]:
    graph = graphs.get(TABLE["graph"])
    if graph is None:
        return [f"段の表の graph {TABLE['graph']} が作りに無い"]
    tops = [item["id"] for item in graph["items"]]
    homes = {}
    for n, stage in enumerate(TABLE["stages"], 1):
        for node in stage["nodes"]:
            homes.setdefault(node, []).append(n)
    out = [f"{TABLE['graph']} のノード {top} が段の表のどの段にも無い" for top in tops if top not in homes]
    out += [f"ノード {node} が段の表の {len(at)} つの段（{'・'.join(map(str, at))}）に在る" for node, at in homes.items() if len(at) > 1]
    out += [f"段の表のノード {node} が {TABLE['graph']} に無い" for node in homes if node not in tops]
    return out


def attach(data: dict) -> None:
    graph = data["shape"]["graphs"].get(TABLE["graph"])
    of = {node: n for n, stage in enumerate(TABLE["stages"], 1) for node in stage["nodes"]}
    tops = [item["id"] for item in graph["items"]] if graph else []
    out = {"graph": graph["name"] if graph else "", "table": [{key: stage[key] for key in SHOWN} for stage in TABLE["stages"]],
           "loose": [top for top in tops if top not in of], "run": None, "stop": None}
    data["stages"] = out
    run = data["run"]
    if not run or not graph or run["graph"] != graph["name"]:
        return
    for entry in [*run["events"], *run["skipped"]]:
        top = entry["tokens"][0] if entry["tokens"] else ""
        entry["stage"] = of.get(top)
        if entry["stage"] is None and top not in out["loose"]:
            out["loose"].append(top)
    through = {item["id"] for item in graph["items"] if item["trigger"] and not item["when"]}
    out["run"] = [_sum(n, run, through) for n in range(1, len(TABLE["stages"]) + 1)]
    out["stop"] = _stop(out["run"])


def _sum(n: int, run: dict, through: set[str]) -> dict:
    """段 n の集計。時間は段の出来事の最初の始めから最後の終わり、人の待ちと AI の時間は出来事の長さの和（並んで走れば重なる）。
    中の出来事を束ねる器（繰り返し・子の run を起こすノード）は、数と長さに数えない（中の出来事と二重になる）。
    段の状態（通った・飛んだ）には、どの道でも走る合流のノード through（trigger_rule を持ち when の無い物。前の段が飛んでも走る）を
    数えない。段のノードが全部合流のノードなら（報告）数える"""
    events = [e for e in run["events"] if e.get("stage") == n]
    tops = set(TABLE["stages"][n - 1]["nodes"])
    deciding = [e for e in events if e["tokens"][0] not in through] if tops - through else events
    own = [e for e in events if e["kind"] not in runread.GROUP_KINDS]
    times = [t for e in events for t in (e["start"], e["end"]) if t]
    tokens = {field: 0 for field in (*runlog.TOKEN_FIELDS, "fresh", "odd")}
    for e in own:
        usage = e.get("usage") or {}
        for field in runlog.TOKEN_FIELDS:
            tokens[field] += usage.get(field) or 0
        if usage:
            # input は新しく読んだ分と cache の読み書きの和（lib/runlog.py の add_tokens）。和より小さい手番は引けないので数だけ持つ
            fresh = (usage.get("input") or 0) - (usage.get("cacheRead") or 0) - (usage.get("cacheWrite") or 0)
            tokens["fresh" if fresh >= 0 else "odd"] += fresh if fresh >= 0 else 1
    seen = {e["status"] for e in deciding}
    state = next((s for s in ("failed", "waiting", "running") if s in seen), "ok" if deciding else
                 "skipped" if any(s.get("stage") == n for s in run["skipped"]) else "none")
    return {"state": state, "start": min(times, key=_time) if times else None, "end": max(times, key=_time) if times else None,
            "seconds": _seconds(min(times, key=_time), max(times, key=_time)) if times else None,
            "wait": round(sum(_length(e) for e in own if e["kind"] == runread.WAIT_NODE), 1),
            "ai_seconds": round(sum(_length(e) for e in own if e["kind"] in runread.AI_KINDS), 1),
            "ai": sum(1 for e in own if e["kind"] in runread.AI_KINDS), "steps": len(own),
            "turns": sum(e.get("turns") or 0 for e in own), "cost": round(sum(e["cost"] for e in events), 6), "tokens": tokens}


def _stop(rows: list[dict]) -> int | None:
    """道が分かれて先を飛んだ段: 最後に走った段の 1 つ前に走った段で、その間の段が全部飛んだ物（飛んだ段が 1 つ以上。記録に無い段は
    間に在ってよい）。最後の段の前で走った段が続いていれば無い"""
    ran = [n for n, row in enumerate(rows, 1) if row["state"] not in ("skipped", "none")]
    if len(ran) < 2:
        return None
    between = [row["state"] for row in rows[ran[-2]:ran[-1] - 1]]
    return ran[-2] if "skipped" in between and set(between) <= {"skipped", "none"} else None


def _length(event: dict) -> float:
    return _seconds(event["start"], event["end"]) if event["start"] and event["end"] else 0.0


def _seconds(start: str, end: str) -> float:
    return round((_time(end) - _time(start)).total_seconds(), 1)


def _time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))
