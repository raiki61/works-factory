"""公開ベンチの run のノードとサブグラフごとの表を、変換の控え（<out>/<作り手>/convert/）と試みに写した Archon の出来事から組む
（ランナー run.py の nodes が使う。試験のモジュールではない）。

ノードの id は出来事の step_name（子の run は <子のグラフの短い名>/<step_name>）、サブグラフは step_name の __ の前の最後の部分か、
無ければその run のグラフの短い名。数はノードが何をしたかの事実だけで、手書きの対応の表は持たない。
秒・費用・トークンの読みは lib/runlog.py の number・measurement・tokens・add_tokens（Archon の spend の形を知る 1 か所）に頼る。
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))   # 頭に入れると lib/tests が根の tests を隠す（tests/AGENTS.md）
import runlog  # noqa: E402
from bin._lib import place  # noqa: E402
from tests.calibration import reviewbench  # noqa: E402

INCLUDE_SEP = place.shared("childsweep").INCLUDE_SEP

PREFIX = "works-factory-"
NOTE = "数はノードが何をしたかの事実まで。そのノードのおかげで直ったとは言わない（それはノードを外して回し直す比べで、別に立てる）"
COUNTED = ("node_completed", "node_failed")


def short(workflow: str) -> str:
    return workflow.removeprefix(PREFIX)


def subgraph(step: str, workflow: str) -> str:
    return step.split(INCLUDE_SEP, 1)[0].split(".")[-1] if INCLUDE_SEP in step else short(workflow)


def _spent(data: dict) -> tuple:
    """1 回の起動の (秒, 秒が無い訳, 費用, 費用が無い訳, トークン, トークンが無い訳)。トークンは runlog.tokens が返す dict（input は
    cacheRead・cacheWrite を含む総量）"""
    timing = data.get("timing")
    ms = runlog.number(timing.get("durationMs")) if isinstance(timing, dict) else None
    seconds, seconds_why = (ms / 1000, None) if ms is not None else (None, "timing が無い")
    return (seconds, seconds_why, *runlog.measurement(data.get("spend"), "costUsd", runlog.number),
            *runlog.measurement(data.get("spend"), "tokens", runlog.tokens))


class Row:
    def __init__(self, node, sub):
        self.node, self.subgraph = node, sub
        self.tasks, self.invocations = set(), 0
        self.seconds, self.usd, self.tokens = [], [], []
        self.findings, self.resolved, self.in_final_diff, self.verdicts = 0, 0, Counter(), Counter()

    def ran(self, task: str, seconds, seconds_why, usd, usd_why, tokens, tokens_why):
        """起動 1 回。値が無い時は None と訳（_spent の返りの並び）。tokens は runlog.tokens の dict"""
        self.tasks.add(task)
        self.invocations += 1
        self.seconds.append((seconds, seconds_why))
        self.usd.append((usd, usd_why))
        self.tokens.append((tokens, tokens_why))

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
        self.tokens += other.tokens
        self.findings += other.findings
        self.resolved += other.resolved
        self.in_final_diff += other.in_final_diff
        self.verdicts += other.verdicts

    def view(self) -> dict:
        seconds, seconds_why = _total(self.seconds, "秒", 3)
        usd, usd_why = _total(self.usd, "費用", 6)
        tokens, tokens_why = _total_tokens(self.tokens)
        return {"node": self.node, "subgraph": self.subgraph, "tasks": len(self.tasks), "invocations": self.invocations,
                "seconds": seconds, "seconds_why": seconds_why, "usd": usd, "usd_why": usd_why,
                **{key: tokens.get(key) for _, key in TOKEN_COLUMNS}, runlog.UNKNOWN_CACHE: tokens.get(runlog.UNKNOWN_CACHE, 0),
                "tokens_why": tokens_why, "findings": self.findings, "resolved": self.resolved,
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


def _total_tokens(values: list) -> tuple[dict, str | None]:
    """起動ごとの (トークン, 無い訳) の欄ごとの和（runlog.add_tokens）と、値が無い・欠ける訳（トークンの無い起動の訳と、キャッシュの内訳が
    不明な起動の件数）。起動が 1 つも無い・トークンが 1 つも無い時の和は {}"""
    got = [t for t, _ in values if t is not None]
    why = "・".join(sorted({w for t, w in values if t is None and w}))
    if not values:
        return {}, "起動が無い"
    if not got:
        return {}, why
    total: dict = {}
    for tokens in got:
        runlog.add_tokens(total, tokens)
    notes = ([f"一部の起動のトークンが無い: {why}"] if len(got) < len(values) else []) + (
        [f"キャッシュの内訳が不明な起動 {total[runlog.UNKNOWN_CACHE]} 件"] if total.get(runlog.UNKNOWN_CACHE) else [])
    return total, "。".join(notes) or None


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
            row(producer.name, producer.name).ran(task, record.get("seconds"), why, record.get("usd"), why, None, "控えの tokens が無い")
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
# トークンの列（入力は cacheRead・cacheWrite を含む総量。キャッシュ外は内訳が全部知れた起動だけの時に出す）。COLUMNS の見出しの照らしを
# 変えないよう、markdown では COLUMNS と tail（差分に入った・当たり・本物・誤り）の後ろに並べる
TOKEN_COLUMNS = (("入力", "input"), ("キャッシュの読み", "cacheRead"), ("キャッシュの書き", "cacheWrite"), ("キャッシュ外", runlog.UNCACHED),
                 ("出力", "output"))


def _line(head: list[str], view: dict) -> str:
    cells = head + [_cell(view[k]) for _, k in COLUMNS] + [
        str(view["in_final_diff"]["yes"]), *(str(view["verdicts"][k]) for k in ("hit", "real", "wrong")),
        *(_cell(view[k]) for _, k in TOKEN_COLUMNS)]
    return "| " + " | ".join(cells) + " |"


def markdown(got: dict) -> str:
    tail = ["差分に入った", "当たり", "本物", "誤り"]
    names = [c for c, _ in COLUMNS] + tail + [c for c, _ in TOKEN_COLUMNS]
    lines = [f"# ノードごとの表（{got['producer']}）", "",
             f"- 公開ベンチの run の、ノードとサブグラフごとの時間・費用・トークン（入力・キャッシュの読み・書き・キャッシュ外・出力）・所見の数と行き先。",
             f"- 作り手 {got['producer']}・課題 {got['tasks']} 件・判定役の結果は{'在る' if got['judged'] else '無い（全部 unjudged）'}。",
             f"- {got['note']}。",
             "- 番地を解いた: 所見の番地のパスがファイル名だけで、候補の key・where のパスか head の一意なファイルに推して解いた数"
             "（元の番地は変換の控えの ref_as_written）。", "",
             "## ノード", "", "| ノード | サブグラフ | " + " | ".join(names) + " |", "|" + " --- |" * (len(names) + 2)]
    lines += [_line([_cell(v["node"]), _cell(v["subgraph"])], v) for v in got["nodes"]]
    lines += ["", "## サブグラフ", "", "| サブグラフ | " + " | ".join(names) + " |", "|" + " --- |" * (len(names) + 1)]
    lines += [_line([_cell(v["subgraph"])], v) for v in got["subgraphs"]]
    whys = [f"- {_cell(v['node'])}: {what} {v[key]}" for v in got["nodes"]
            for what, key in (("秒", "seconds_why"), ("費用", "usd_why"), ("トークン", "tokens_why")) if v[key]]
    if whys:
        lines += ["", "## 値が無い・欠ける訳", "", *whys]
    return "\n".join(lines) + "\n"
