"""段の表（viewer/stages.json）と段ごとの集計（トレースの段の span と run の span の段ごとの費用の表が読む。docs/design/viewer.md の 6.5）。

段は、line（メイングラフ）の一番上のノードを人の言葉で畳んだ単位で、見る道具だけの考え。表は工場の中に置かず、工場の中からも読まない
（viewer/AGENTS.md の E25）。出来事の段は、出来事の道の頭（line の一番上のノード。include・繰り返し・子の run の出来事も、道の頭は
line のノード）で引く。

- check(graphs) -> 照らしの問題の字の一覧。今の木の line の一番上のノードがどれもちょうど 1 つの段に入り、表の id がどれも line に在り、
  段の配線の列 wiring がその段のノードの中に在り、どの段にも配線でないノードが在る
- attach(data) -> data["stages"] に段ごとの集計 run（line の run でなければ None）を置き、line の run なら出来事と飛んだノードに段の
  番号 stage を付ける（段の表に無いノードは None）
"""
import json
from pathlib import Path

import runlog   # lib/（viewer/src/__init__.py が sys.path に足す）
from viewer.src import runread, shape

TABLE = json.loads((Path(__file__).resolve().parents[1] / "stages.json").read_text(encoding="utf-8"))


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
    data["stages"] = {"run": None}
    run = data["run"]
    if not run or not graph or run["graph"] != graph["name"]:
        return
    of = {node: n for n, stage in enumerate(TABLE["stages"], 1) for node in stage["nodes"]}
    through = {node for stage in TABLE["stages"] for node in stage["wiring"]}
    for entry in [*run["events"], *run["skipped"]]:
        entry["stage"] = of.get(entry["tokens"][0] if entry["tokens"] else "")
    data["stages"]["run"] = [_sum(n, run, through) for n in range(1, len(TABLE["stages"]) + 1)]


def _sum(n: int, run: dict, through: set[str]) -> dict:
    """段 n の集計。時間は段の出来事の最初の始めから最後の終わり、人の待ちと AI の時間は出来事の長さの和（並んで走れば重なる）。
    中の出来事を束ねる器（繰り返し・子の run を起こすノード）は、数と長さと費用に数えない（中の出来事と二重になる。子の run を起こす
    ノードの行には子の総額が載る）。周の数は、繰り返しの本体の場所（道を繰り返しの区切りだけで切る。本体の include の中のノードも
    同じ周）と周の番号（入れ子なら内の周まで）の違う物の数。
    段の状態（通った・飛んだ）には、段の表の配線のノード through（合流・受け渡しだけの物。fix-in・fixed・judged は修正の段が
    飛んでも走る）を数えない。状態は所（run・道・周）ごとの最後の出来事（出来事は始めの順）の結果で決め、落ちた後に起き直して
    通った段は通ったにして、一度落ちたことを印 fell に持つ（前の起動の id を使い直して走り直した物は、読む部品が起動ごとの出来事に
    分け、走り直しの出来事も印 fell を持つ。src/runread.py）"""
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
        # 和より小さい手番は引けないので数だけ持ち、新しく読んだ分 uncached を出さない
        odd += _odd(usage)
    if odd:
        tokens.pop(runlog.UNCACHED, None)
    tokens = {**{field: 0 for field in runlog.TOKEN_FIELDS}, **tokens, "odd": odd}
    # 段の状態は所（run・道・周）ごとの最後の結果で決める。落ちた後に起き直して通った所は通ったにし、一度落ちたことは印 fell に残す
    last = {(e["run"], tuple(e["tokens"]), tuple(e["loop"])): e["status"] for e in deciding}
    seen = set(last.values())
    state = next((s for s in ("failed", "waiting", "running") if s in seen), "ok" if deciding else
                 "skipped" if any(s.get("stage") == n for s in run["skipped"]) else "none")
    start, end = (min(times, key=runread.when), max(times, key=runread.when)) if times else (None, None)
    return {"state": state, "fell": state != "failed" and any(e["status"] == "failed" or e.get("fell") for e in deciding),
            "start": start, "end": end, "seconds": runread.seconds(start, end),
            "wait": round(sum(runread.length(e) for e in own if e["kind"] == runread.WAIT_NODE), 1),
            "ai_seconds": round(sum(runread.length(e) for e in own if e["kind"] in runread.AI_KINDS), 1),
            "ai": sum(1 for e in own if e["kind"] in runread.AI_KINDS), "steps": len(own),
            "turns": sum(e.get("turns") or 0 for e in own),
            "rounds": len({(e["run"], *e["path"].split(shape.IN_LOOP)[:-1], *e["loop"]) for e in own if e["loop"]}),
            "cost": round(sum(e["cost"] for e in own), 6), "tokens": tokens}


def _odd(usage: dict) -> bool:
    return all(field in usage for field in runlog.CACHE_FIELDS) and usage["input"] < usage["cacheRead"] + usage["cacheWrite"]

