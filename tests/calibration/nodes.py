"""公開ベンチの run のノードとサブグラフごとの表を、変換の控え（<out>/<作り手>/convert/）と試みに写した Archon の出来事から組む
（ランナー run.py の nodes が使う。試験のモジュールではない）。

ノードの id は出来事の step_name（子の run は <子のグラフの短い名>/<step_name>）、サブグラフは step_name の __ の前の最後の部分か、
無ければその run のグラフの短い名。数はノードが何をしたかの事実だけで、手書きの対応の表は持たない。
"""
import json
from collections import Counter
from pathlib import Path

from tests.calibration import reviewbench
from tests.shared import shared_module

INCLUDE_SEP = shared_module.load("childsweep").INCLUDE_SEP

PREFIX = "works-factory-"
NOTE = "数はノードが何をしたかの事実まで。そのノードのおかげで直ったとは言わない（それはノードを外して回し直す比べで、別に立てる）"
COUNTED = ("node_completed", "node_failed")


def short(workflow: str) -> str:
    return workflow.removeprefix(PREFIX)


def subgraph(step: str, workflow: str) -> str:
    return step.split(INCLUDE_SEP, 1)[0].split(".")[-1] if INCLUDE_SEP in step else short(workflow)


def _spent(data: dict) -> tuple[float | None, str | None, float | None, str | None]:
    """1 回の起動の (秒, 秒が無い訳, 費用, 費用が無い訳)"""
    timing = data.get("timing")
    ms = timing.get("durationMs") if isinstance(timing, dict) else None
    seconds, seconds_why = (ms / 1000, None) if isinstance(ms, (int, float)) and not isinstance(ms, bool) else (None, "timing が無い")
    cost = (data.get("spend") or {}).get("costUsd") if isinstance(data.get("spend"), dict) else None
    if isinstance(cost, dict) and cost.get("source") == "provider" and isinstance(cost.get("value"), (int, float)):
        return seconds, seconds_why, cost["value"], None
    return seconds, seconds_why, None, (cost.get("reason") if isinstance(cost, dict) else None) or "spend.costUsd が無い"


class Row:
    def __init__(self, node, sub):
        self.node, self.subgraph = node, sub
        self.tasks, self.invocations = set(), 0
        self.seconds, self.usd = [], []
        self.findings, self.resolved, self.in_final_diff, self.verdicts = 0, 0, Counter(), Counter()

    def ran(self, task: str, seconds, seconds_why, usd, usd_why):
        self.tasks.add(task)
        self.invocations += 1
        self.seconds.append((seconds, seconds_why))
        self.usd.append((usd, usd_why))

    def found(self, finding: dict, status: str | None):
        self.findings += 1
        self.resolved += finding.get("ref_as_written") is not None
        self.in_final_diff[{True: "yes", False: "no"}.get(finding.get("in_final_diff"), "unknown")] += 1
        self.verdicts[reviewbench.VERDICTS.get(status, "unjudged")] += 1

    def add(self, other: "Row"):
        self.tasks |= other.tasks
        self.invocations += other.invocations
        self.seconds += other.seconds
        self.usd += other.usd
        self.findings += other.findings
        self.resolved += other.resolved
        self.in_final_diff += other.in_final_diff
        self.verdicts += other.verdicts

    def view(self) -> dict:
        seconds, seconds_why = _total(self.seconds, "秒", 3)
        usd, usd_why = _total(self.usd, "費用", 6)
        return {"node": self.node, "subgraph": self.subgraph, "tasks": len(self.tasks), "invocations": self.invocations,
                "seconds": seconds, "seconds_why": seconds_why, "usd": usd, "usd_why": usd_why, "findings": self.findings,
                "resolved": self.resolved,
                "in_final_diff": {k: self.in_final_diff[k] for k in ("yes", "no", "unknown")},
                "verdicts": {k: self.verdicts[k] for k in ("hit", "real", "wrong", "unjudged")}}


def _total(values: list, what: str, digits: int) -> tuple[float | None, str | None]:
    got = [v for v, _ in values if v is not None]
    why = "・".join(sorted({w for v, w in values if v is None and w}))
    if not values:
        return None, "起動が無い"
    if not got:
        return None, why
    return round(sum(got), digits), (f"一部の起動の{what}が無い: {why}" if len(got) < len(values) else None)


def table(out: Path, producer) -> dict:
    mine = Path(out) / producer.name
    try:
        records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((mine / "convert").glob("*.json"))]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise reviewbench.BenchError(f"{mine / 'convert'} の控えを読めない: {type(e).__name__}") from None
    judged = reviewbench.verdicts(mine / "scoring" / "results.details.json")
    rows: dict = {}

    def row(node, sub) -> Row:
        return rows.setdefault(node, Row(node, sub))

    for record in records:
        task = record["key"]
        if producer.archon:
            for workflow, events, prefix in producer.node_runs(Path(record["attempt"]) / "evidence"):
                for e in events:
                    if e.get("event_type") in COUNTED and isinstance(e.get("data"), dict):
                        step = str(e.get("step_name") or "")
                        row(prefix + step, subgraph(step, workflow)).ran(task, *_spent(e["data"]))
        else:
            why = "控えの seconds・usd が無い"
            row(producer.name, producer.name).ran(task, record.get("seconds"), why, record.get("usd"), why)
        for f in record.get("findings") or []:
            status = (judged or {}).get((task, f["file"], f["start_line"], f["end_line"], f["message"]))
            node = f.get("node")
            row(node, rows[node].subgraph if node in rows else None).found(f, status)
    subgraphs: dict = {}
    for r in rows.values():
        subgraphs.setdefault(r.subgraph, Row(None, r.subgraph)).add(r)
    return {"producer": producer.name, "tasks": len(records), "judged": judged is not None, "note": NOTE,
            "nodes": [r.view() for r in rows.values()],
            "subgraphs": [{k: v for k, v in r.view().items() if k != "node"} for r in subgraphs.values()]}


def _cell(value) -> str:
    return "—" if value is None else str(value)


COLUMNS = (("課題", "tasks"), ("起動", "invocations"), ("秒", "seconds"), ("USD", "usd"), ("所見", "findings"),
           ("番地を解いた", "resolved"))


def _line(head: list[str], view: dict) -> str:
    cells = head + [_cell(view[k]) for _, k in COLUMNS] + [
        str(view["in_final_diff"]["yes"]), *(str(view["verdicts"][k]) for k in ("hit", "real", "wrong"))]
    return "| " + " | ".join(cells) + " |"


def markdown(got: dict) -> str:
    tail = ["差分に入った", "当たり", "本物", "誤り"]
    names = [c for c, _ in COLUMNS] + tail
    lines = [f"# ノードごとの表（{got['producer']}）", "",
             f"- 公開ベンチの run の、ノードとサブグラフごとの時間・費用・所見の数と行き先。",
             f"- 作り手 {got['producer']}・課題 {got['tasks']} 件・判定役の結果は{'在る' if got['judged'] else '無い（全部 unjudged）'}。",
             f"- {got['note']}。",
             "- 番地を解いた: 所見の番地のパスがファイル名だけで、候補の key・where のパスか head の一意なファイルに推して解いた数"
             "（元の番地は変換の控えの ref_as_written）。", "",
             "## ノード", "", "| ノード | サブグラフ | " + " | ".join(names) + " |", "|" + " --- |" * (len(names) + 2)]
    lines += [_line([_cell(v["node"]), _cell(v["subgraph"])], v) for v in got["nodes"]]
    lines += ["", "## サブグラフ", "", "| サブグラフ | " + " | ".join(names) + " |", "|" + " --- |" * (len(names) + 1)]
    lines += [_line([_cell(v["subgraph"])], v) for v in got["subgraphs"]]
    whys = [f"- {_cell(v['node'])}: {what} {v[key]}" for v in got["nodes"]
            for what, key in (("秒", "seconds_why"), ("費用", "usd_why")) if v[key]]
    if whys:
        lines += ["", "## 値が無い・欠ける訳", "", *whys]
    return "\n".join(lines) + "\n"
