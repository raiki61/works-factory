"""段の表（viewer/stages.json）と段ごとの集計（流れの画面。docs/design/viewer.md の 6.8）。

段は、line（メイングラフ）の一番上のノードを人の言葉で畳んだ単位で、見る道具だけの考え。表は工場の中に置かず、工場の中からも読まない
（viewer/AGENTS.md の E25）。出来事の段は、出来事の道の頭（line の一番上のノード。include・繰り返し・子の run の出来事も、道の頭は
line のノード）で引く。

- check(graphs) -> 照らしの問題の字の一覧。今の木の line の一番上のノードがどれもちょうど 1 つの段に入り、表の id がどれも line に在り、
  段の配線の列 wiring がその段のノードの中に在り、どの段にも配線でないノードが在る
- attach(data) -> data["stages"] に段の表と結末の頭の語の表 outcomes と、run が line の run なら段ごとの集計と止まった所（段の番号 stop・止まり方 stop_by・
  止まった出来事の番号 stop_event）を足し、出来事と飛んだノードに段の番号 stage を、出来事に時間の帯の塗り分け role と、段の状態に
  数えない配線のノードの印 through を付ける。雛形は止まり方を読むだけで、止める語を写さない。どの run にも、図の札ごとの AI の手番の
  費用 run["ai_cost"]（札の鍵 → 札とその中の AI の手番の費用の和）を付ける。雛形は費用を数えず、この欄と段の集計の cost を読む
- spots(at) -> 出来事の当たる所（flowview.unmatched が付ける at）が触れる札の鍵の列（外から順）。雛形の spots と同じ形
"""
import json
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
           "outcomes": TABLE["outcomes"],
           "loose": [top for top in tops if top not in of], "run": None, "stop": None, "stop_by": None, "stop_event": None}
    data["stages"] = out
    run = data["run"]
    if run:
        run["ai_cost"] = _ai_cost(run)
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
    by, at = _stop(run)
    if at is not None:
        out.update(stop=run["events"][at]["stage"], stop_by=by, stop_event=at)


def spots(at: dict) -> list[str]:
    """札の鍵は入れ子の場所ごと: 「<外の札の鍵>>graph/道」（一番外は「graph/道」）。道の頭から順の札（繰り返しの器と入れ子の札）も
    数える。雛形 page.tpl.html の K と spots と同じ形で、雛形はこの鍵で札を引く"""
    out, scope = [], ""
    for step in [*(at.get("via") or []), at]:
        head = f"{scope}>{step['graph']}/" if scope else f"{step['graph']}/"
        parts = step["node"].split("/")
        out += [head + "/".join(parts[:i + 1]) for i in range(len(parts))]
        scope = head + step["node"]
    return out


def _ai_cost(run: dict) -> dict[str, float]:
    """札ごとの AI の手番の費用（札の語と板の「AI の手番の費用」）。中の出来事を束ねる器は数えない（子の run を起こすノードの行は子の
    総額を載せ、中の手番と二重になる）。図に当たらない出来事は札が無いので数えない"""
    out = {}
    for e in run["events"]:
        at = e.get("at")
        if e["kind"] not in runread.AI_KINDS or not at or not at.get("graph"):
            continue
        for key in dict.fromkeys(spots(at)):
            out[key] = out.get(key, 0.0) + e["cost"]
    return {key: round(cost, 6) for key, cost in out.items()}


def _sum(n: int, run: dict, through: set[str]) -> dict:
    """段 n の集計。時間は段の出来事の最初の始めから最後の終わり、人の待ちと AI の時間は出来事の長さの和（並んで走れば重なる）。
    中の出来事を束ねる器（繰り返し・子の run を起こすノード）は、数と長さと費用に数えない（中の出来事と二重になる。子の run を起こす
    ノードの行には子の総額が載る）。周の数は、繰り返しの本体の場所（道を繰り返しの区切りだけで切る。本体の include の中のノードも
    同じ周）と周の番号（入れ子なら内の周まで）の違う物の数。
    段の状態（通った・飛んだ）には、段の表の配線のノード through（合流・受け渡しだけの物。fix-in・fixed・judged は修正の段が
    飛んでも走る）を数えない。状態は所（run・道・周）ごとの最後の出来事（出来事は始めの順）の結果で決め、落ちた後に起き直して
    通った段は通ったにして、一度落ちたことを印 fell に持つ（前の起動の id を使い直して走り直した出来事は、出来事の印 fell が持つ。
    src/runread.py）"""
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


def four(usage: dict) -> dict:
    """手番 1 回の 4 分けのトークンと新しく読んだ分 uncached（lib/runlog.py の add_tokens と同じ訳。input は新しく読んだ分と cache の
    読み書きの和で、cache の欄が欠けた手番は uncached を出さずに cacheUnknown を持つ）。input が cache の 2 つの和より小さい手番は
    引けないので uncached を出さずに odd を真にする（包みの関係は Claude Code と Archon の版で変わりうるので決まりとして照らさない）。
    段の集計と無駄の手がかり（src/waste.py）が使う"""
    got = {}
    runlog.add_tokens(got, usage)
    odd = _odd(usage)
    if odd:
        got.pop(runlog.UNCACHED, None)
    return {**got, "odd": odd}


def _odd(usage: dict) -> bool:
    return all(field in usage for field in runlog.CACHE_FIELDS) and usage["input"] < usage["cacheRead"] + usage["cacheWrite"]


def _role(kind: str) -> str:
    """時間の帯の塗り分け: AI の手番（ai）・人の答え待ち（wait）・中の出来事を束ねる器（group。帯に描かない）・機械の手番（machine）"""
    return "ai" if kind in runread.AI_KINDS else "wait" if kind == runread.WAIT_NODE else "group" if kind in runread.GROUP_KINDS else "machine"


def _stop(run: dict) -> tuple[str | None, int | None]:
    """止まり方（人が止めた human・落ちた failed）と止まった出来事の番号（run の events の中の位置）を記録の事実から引く（下書きの計画 2026-10-29-viewer-overview.md の 6.6.8）。人が止めた run は、答えが止める語
    （lib/answer.py の STOP_WORDS）だった最後の人の答え待ちの出来事の段。そうでなく落ちた run は、受け止めていない最後の落ちた出来事の段。
    受け止めた落ちは、その段より後ろの段（どの道でも走る報告の段、表の最後の段のほかで）の配線でないノードが走った物（line は独立の目と
    レンズの落ちを受け止めて先へ進むが、Archon は run を failed で終える。docs/design/archon.md）。
    次の run には出さない（窓口の決めで今は出さない。広げるかは後で決める）: 直した・直す物が無かった・まだ走っている run と、報告の結末
    （workflows/report/src/outcome.py）が line の止め stopped_by_line（止める語を script が受け渡しただけで人の答えが無い）・人待ち
    needs_human・記録が通らない record_invalid で、落ちていない run。
    道が分かれて先を飛んだ段は使わない（止めを受け渡しただけの段を止まった所と取り違える）。止まり方もここで決め、同じ段に人の
    答え待ちが在っても答えが止める語でなければ人の止めにしない（承認を通した後に同じ段で落ちた run は落ちた）"""
    events = run["events"]
    by, rows = "human", [i for i, e in enumerate(events) if e["kind"] == runread.WAIT_NODE and _answer(e.get("output")) in answer.STOP_WORDS]
    if not rows and run.get("status") == runread.FAILED:
        last = len(TABLE["stages"])
        went = {e["stage"] for e in events if e.get("stage") not in (None, last) and not e["through"]}
        by, rows = "failed", [i for i, e in enumerate(events) if e["status"] == "failed" and not any(n > (e.get("stage") or last) for n in went)]
    rows = [i for i in rows if events[i].get("stage") is not None]
    return (by, rows[-1]) if rows else (None, None)


def _answer(output) -> str:
    """人の答え待ちの出力（{decision, text}。記録では JSON の字）の答えの語（欄の名は runread.ANSWER_DECISION）"""
    return runread.field(output, runread.ANSWER_DECISION)
