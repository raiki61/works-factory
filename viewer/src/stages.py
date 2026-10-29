"""段の表（viewer/stages.json）と段ごとの集計（流れの画面。docs/design/viewer.md の 6.8）。

段は、line（メイングラフ）の一番上のノードを人の言葉で畳んだ単位で、見る道具だけの考え。表は工場の中に置かず、工場の中からも読まない
（viewer/AGENTS.md の E25）。出来事の段は、出来事の道の頭（line の一番上のノード。include・繰り返し・子の run の出来事も、道の頭は
line のノード）で引く。

- check(graphs) -> 照らしの問題の字の一覧。今の木の line の一番上のノードがどれもちょうど 1 つの段に入り、表の id がどれも line に在り、
  段の配線の列 wiring がその段のノードの中に在り、どの段にも配線でないノードが在る
- attach(data) -> data["stages"] に段の表と、run が line の run なら段ごとの集計を足し、出来事と飛んだノードに段の番号 stage を、
  出来事に時間の帯の塗り分け role と、段の状態に数えない配線のノードの印 through を付ける
"""
import json
from datetime import datetime
from pathlib import Path

import answer   # lib/（viewer/src/__init__.py が sys.path に足す）
import runlog
from viewer.src import runread, shape

TABLE = json.loads((Path(__file__).resolve().parents[1] / "stages.json").read_text(encoding="utf-8"))
SHOWN = ("name", "line", "hands", "source", "nodes", "wiring")


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
    for stage in TABLE["stages"]:
        out += [f"段 {stage['name']} の配線 {node} がその段のノードに無い" for node in stage["wiring"] if node not in stage["nodes"]]
        if not set(stage["nodes"]) - set(stage["wiring"]):
            out.append(f"段 {stage['name']} のノードが全部配線で、段の状態を決められない")
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
    through = {node for stage in TABLE["stages"] for node in stage["wiring"]}
    for entry in [*run["events"], *run["skipped"]]:
        top = entry["tokens"][0] if entry["tokens"] else ""
        entry["stage"] = of.get(top)
        if entry["stage"] is None and top not in out["loose"]:
            out["loose"].append(top)
    for e in run["events"]:
        e["role"] = _role(e["kind"])
        e["through"] = e["stage"] is not None and e["tokens"][0] in through
    out["run"] = [_sum(n, run, through) for n in range(1, len(TABLE["stages"]) + 1)]
    out["stop"] = _stop(run)


def _sum(n: int, run: dict, through: set[str]) -> dict:
    """段 n の集計。時間は段の出来事の最初の始めから最後の終わり、人の待ちと AI の時間は出来事の長さの和（並んで走れば重なる）。
    中の出来事を束ねる器（繰り返し・子の run を起こすノード）は、数と長さと費用に数えない（中の出来事と二重になる。子の run を起こす
    ノードの行には子の総額が載る）。周の数は、繰り返しの本体の場所（道を繰り返しの区切りだけで切る。本体の include の中のノードも
    同じ周）と周の番号（入れ子なら内の周まで）の違う物の数。
    段の状態（通った・飛んだ）には、段の表の配線のノード through（合流・受け渡しだけの物。fix-in・fixed・judged は修正の段が
    飛んでも走る）を数えない"""
    events = [e for e in run["events"] if e.get("stage") == n]
    deciding = [e for e in events if e["tokens"][0] not in through]
    own = [e for e in events if e["kind"] not in runread.GROUP_KINDS]
    times = [t for e in events for t in (e["start"], e["end"]) if t]
    tokens, odd = {}, 0
    for e in own:
        usage = e.get("usage")
        if not usage:
            continue
        runlog.add_tokens(tokens, usage)
        # input は新しく読んだ分と cache の読み書きの和（lib/runlog.py の add_tokens）。和より小さい手番は引けないので数だけ持ち、
        # 新しく読んだ分 uncached を出さない
        if all(field in usage for field in runlog.CACHE_FIELDS) and usage["input"] < usage["cacheRead"] + usage["cacheWrite"]:
            odd += 1
    if odd:
        tokens.pop(runlog.UNCACHED, None)
    tokens = {**{field: 0 for field in runlog.TOKEN_FIELDS}, **tokens, "odd": odd}
    seen = {e["status"] for e in deciding}
    state = next((s for s in ("failed", "waiting", "running") if s in seen), "ok" if deciding else
                 "skipped" if any(s.get("stage") == n for s in run["skipped"]) else "none")
    return {"state": state, "start": min(times, key=_time) if times else None, "end": max(times, key=_time) if times else None,
            "seconds": _seconds(min(times, key=_time), max(times, key=_time)) if times else None,
            "wait": round(sum(_length(e) for e in own if e["kind"] == runread.WAIT_NODE), 1),
            "ai_seconds": round(sum(_length(e) for e in own if e["kind"] in runread.AI_KINDS), 1),
            "ai": sum(1 for e in own if e["kind"] in runread.AI_KINDS), "steps": len(own),
            "turns": sum(e.get("turns") or 0 for e in own),
            "rounds": len({(e["run"], *e["path"].split(shape.IN_LOOP)[:-1], *e["loop"]) for e in own if e["loop"]}),
            "cost": round(sum(e["cost"] for e in own), 6), "tokens": tokens}


def _role(kind: str) -> str:
    """時間の帯の塗り分け: AI の手番（ai）・人の答え待ち（wait）・中の出来事を束ねる器（group。帯に描かない）・機械の手番（machine）"""
    return "ai" if kind in runread.AI_KINDS else "wait" if kind == runread.WAIT_NODE else "group" if kind in runread.GROUP_KINDS else "machine"


def _stop(run: dict) -> int | None:
    """止まった段を記録の事実から引く（下書きの計画 2026-10-29-viewer-overview.md の 6.6.8）。人が止めた run は、答えが止める語
    （lib/answer.py の STOP_WORDS）だった最後の人の答え待ちの出来事の段。そうでなく落ちた run は、受け止めていない最後の落ちた出来事の段。
    受け止めた落ちは、その段より後ろの段（どの道でも走る報告の段、表の最後の段のほかで）の配線でないノードが走った物（line は独立の目と
    レンズの落ちを受け止めて先へ進むが、Archon は run を failed で終える。docs/design/archon.md）。
    次の run には出さない（窓口の決めで今は出さない。広げるかは後で決める）: 直した・直す物が無かった・まだ走っている run と、報告の結末
    （workflows/report/src/outcome.py）が line の止め stopped_by_line（止める語を script が受け渡しただけで人の答えが無い）・人待ち
    needs_human・記録が通らない record_invalid で、落ちていない run。
    道が分かれて先を飛んだ段は使わない（止めを受け渡しただけの段を止まった所と取り違える）"""
    rows = [e for e in run["events"] if e["kind"] == runread.WAIT_NODE and _answer(e.get("output")) in answer.STOP_WORDS]
    if not rows and run.get("status") == runread.FAILED:
        last = len(TABLE["stages"])
        went = {e["stage"] for e in run["events"] if e.get("stage") not in (None, last) and not e["through"]}
        rows = [e for e in run["events"] if e["status"] == "failed" and not any(n > (e.get("stage") or last) for n in went)]
    rows = [e for e in rows if e.get("stage") is not None]
    return rows[-1]["stage"] if rows else None


def _answer(output) -> str:
    """人の答え待ちの出力（{decision, text}。記録では JSON の字）の答えの語"""
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except ValueError:
            return ""
    return answer.decision(output)["decision"] if isinstance(output, dict) else ""


def _length(event: dict) -> float:
    return _seconds(event["start"], event["end"]) if event["start"] and event["end"] else 0.0


def _seconds(start: str, end: str) -> float:
    return round((_time(end) - _time(start)).total_seconds(), 1)


def _time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))
