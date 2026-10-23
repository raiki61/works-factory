"""Archon の run の記録（$LOG_DIR/<WORKFLOW_ID>.jsonl）を読む口（docs/design/integration.md の 4.5-2）。report の block と chain の
script が使う。元は workflows/.shared/boundary.py の transcript・own_prefix と lib/runreport.py の transcript_facts（今は
workflows/report/src/transcript.py の写し）。報告の行の組み立て（費用・回り直し・道具の呼びの行）は report の src/transcript.py に残る。

- read() -> (行の並び, 読めなかった訳): 読めなければ (None, 訳)
- own_prefix() -> 自分の include の node の id の頭（無ければ ""）
- facts(rows, *, exclude_prefix, optional) -> {ok, failed, absorbed, errors, retried, cost, uncosted, tokens, untokened, minutes, models, efforts, calls, resubmits}
- measurement(spend, key, accept) -> (値, 無い訳): Archon の spend の測り（{source, value} か {source: unavailable, reason}）を読む
- number(v) -> 数（bool でない int・float）か None
- tokens(value) -> 1 回の起動のトークンの dict か None。add_tokens(total, got) で node ごとの和に足す
"""
import json
import os
import pathlib

import report    # lib/

PROVIDER_ROW = "provider_event"
PROVIDER_EVENT = "event"
TOOL_CALL = "tool_call"
TOOL_NAME = "name"
TOOL_INPUT = "rawInput"
PATH_TOOLS = ("Read", "Edit", "Write")
SHELL_TOOL = "Bash"
EXEC_ROW = "exec_output"
EXEC_LABEL = "content"
EXIT_CODE = "exit_code"
UNTIL_ROW = "<until_bash>"
ITERATION_MARK = "-iteration-"
COST_ROWS = ("node_complete", "node_error")
DONE_ROWS = ("node_complete", "node_skipped")
OWN_SPEND = "node"
# Archon の tokenUsageSchema（packages/provider-contract/src/result.ts）の欄。input は cacheRead・cacheWrite を含む総量で、足し直さない。
# cachePartial は束ねた値にだけ立ち、キャッシュの欄が下限であることを言う
TOKEN_FIELDS = ("input", "output", "cacheRead", "cacheWrite")
CACHE_PARTIAL = "cachePartial"
CACHE_FIELDS = ("cacheRead", "cacheWrite")
# 和の欄: input − cacheRead − cacheWrite（キャッシュの内訳が全部知れた時だけ）と、内訳が不明な起動の件数
UNCACHED = "uncached"
UNKNOWN_CACHE = "cacheUnknown"


def _dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def number(v):
    """bool でない数ならその値、ほかは None"""
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def measurement(spend, key: str, accept=number) -> tuple:
    """Archon の spend の測り spend[key]（{source: provider, value} か {source: unavailable, reason}）の (値, 無い訳)。値は source が
    provider で accept(value) が None でない時だけ返し、ほかは (None, 訳)。訳は unavailable の reason、無ければ欄の名"""
    got = _dict(spend).get(key)
    if isinstance(got, dict) and got.get("source") == "provider":
        value = accept(got.get("value"))
        if value is not None:
            return value, None
        return None, f"spend.{key} の値が読めない"
    reason = _dict(got).get("reason")
    return None, reason if isinstance(reason, str) and reason else f"spend.{key} が無い"


def tokens(value):
    """1 回の起動の tokens の値（{input, output, cacheRead?, cacheWrite?, cachePartial?}）から、数の欄だけの dict。input・output が数でなければ None"""
    value = _dict(value)
    if number(value.get("input")) is None or number(value.get("output")) is None:
        return None
    got = {field: value[field] for field in TOKEN_FIELDS if number(value.get(field)) is not None}
    if value.get(CACHE_PARTIAL) is True:
        got[CACHE_PARTIAL] = True
    return got


def add_tokens(total: dict, got: dict) -> None:
    """起動 1 回の tokens（tokens() の返り）を和 total に足す。input は cacheRead・cacheWrite を含むので足し直さず、キャッシュ外
    （UNCACHED）は input − cacheRead − cacheWrite。キャッシュの欄が欠けた起動と cachePartial の起動は UNKNOWN_CACHE に数え、一度でも
    在れば UNCACHED を出さない（cacheRead・cacheWrite の和は下限）"""
    for field in TOKEN_FIELDS:
        total[field] = total.get(field, 0) + got.get(field, 0)
    if got.get(CACHE_PARTIAL) is True or any(field not in got for field in CACHE_FIELDS):
        total[UNKNOWN_CACHE] = total.get(UNKNOWN_CACHE, 0) + 1
    if total.get(UNKNOWN_CACHE):
        total.pop(UNCACHED, None)
    else:
        total[UNCACHED] = total["input"] - total["cacheRead"] - total["cacheWrite"]


def read() -> tuple:
    """この run の記録の行と、読めなかった訳。読めなければ (None, 訳)。JSON でない行は飛ばす"""
    log_dir, run_id = os.environ.get("LOG_DIR", ""), os.environ.get("WORKFLOW_ID", "")
    if not log_dir or not run_id:
        return None, "run の記録の置き場（LOG_DIR）か run の id（WORKFLOW_ID）が届いていない"
    path = pathlib.Path(log_dir) / f"{run_id}.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        return None, f"run の記録 {path} が読めない（{e.strerror or e}。dry-run は記録を書かない）"
    rows = []
    for record in lines:
        try:
            rows.append(json.loads(record))
        except ValueError:
            continue
    return rows, ""


def own_prefix() -> str:
    """自分の node の実行の記録（ARCHON_NODE_EXECUTION）の path から、自分の include の node の id の頭（入れ子なら outer__inner__。
    ループの本体の node は <ループの id>.<node の id> の形なので、段ごとの最後の __ より前を順に継ぐ。include の外なら空）"""
    try:
        doc = json.loads(os.environ.get("ARCHON_NODE_EXECUTION") or "{}")
    except ValueError:
        return ""
    path = doc.get("path") if isinstance(doc, dict) else None
    parts = [p for step in (path.split(".") if isinstance(path, str) else []) for p in step.split("__")[:-1] if p]
    return "__".join(parts) + "__" if parts else ""


def _declared(step: str, optional) -> bool:
    """受け止めると宣言したノードの中か。宣言の 1 つは、区切り（__・-）で終わる node の id の頭か、node の id そのもの（そのループの中の
    node <id>.<中の id> も含む）。区切りの無い頭で比べると、別の node まで受け止めてしまう"""
    return any(isinstance(head, str) and head
               and (step.startswith(head) if head.endswith(("__", "-")) else step == head or step.startswith(head + "."))
               for head in optional or ())


def facts(rows, *, exclude_prefix: str = "", optional=()) -> dict:
    """run の記録の行から node ごとの事実。rows が None なら ok: False。最後の行が node_error の node は、宣言（optional）の中なら受け止めた落ち
    （absorbed）、外なら run を途中で終わらせた落ち（failed）。retried は node_error の後に済んだ node。exclude_prefix で始まる node（この block
    自身）は数えない。費用は自分の費用を言う行の cost_usd の和（無い行は uncosted に件数）。トークンも自分の費用を言う行の
    execution.spend.tokens の欄ごとの和（add_tokens。無い行は untokened に件数）。時間は node_start から最後の完了・失敗まで（分）。
    calls は役が呼んだ道具の node ごとの {Read・Edit・Write: ファイル, Bash: 回数}。resubmits はループごとの {count, minutes}"""
    if rows is None:
        return {"ok": False, "failed": [], "absorbed": [], "errors": {}, "retried": [], "cost": {}, "uncosted": {}, "tokens": {},
                "untokened": {}, "minutes": {}, "models": {}, "efforts": {}, "calls": {}, "resubmits": {}}

    def ours(step):
        return bool(exclude_prefix) and step.startswith(exclude_prefix)
    last, falls, errors, began, ended = {}, {}, {}, {}, {}
    cost, uncosted, models, efforts, calls = {}, {}, {}, {}, {}
    spent, untokened = {}, {}
    untils = {}
    for r in rows:
        if not isinstance(r, dict) or not isinstance(r.get("step"), str):
            continue
        step, kind = r["step"], r.get("type")
        if kind == PROVIDER_ROW and not ours(step):
            _count_call(calls, step, _dict(r.get(PROVIDER_EVENT)))
        if kind == EXEC_ROW and r.get(EXEC_LABEL) == UNTIL_ROW and not ours(step):
            loop, mark, _ = step.rpartition(ITERATION_MARK)
            if mark and loop:
                untils.setdefault(loop, []).append((r.get(EXIT_CODE), report._time(r.get("ts"))))
        if kind == "node_start":
            began.setdefault(step, report._time(r.get("ts")))
        if kind in (*COST_ROWS, "node_skipped"):
            last[step] = kind
        if kind == "node_error":
            falls[step] = falls.get(step, 0) + 1
            errors[step] = str(r.get("error") or "")
        if kind in COST_ROWS:
            ended[step] = report._time(r.get("ts"))
            execution = _dict(r.get("execution"))
            if execution.get("accounting", OWN_SPEND) != OWN_SPEND:
                continue
            if number(r.get("cost_usd")) is not None:
                cost[step] = cost.get(step, 0.0) + float(r["cost_usd"])
            else:
                uncosted[step] = uncosted.get(step, 0) + 1
            got, _ = measurement(execution.get("spend"), "tokens", tokens)
            if got is None:
                untokened[step] = untokened.get(step, 0) + 1
            else:
                add_tokens(spent.setdefault(step, {}), got)
            binding = _dict(execution.get("binding"))
            model = _dict(_dict(binding.get("model")).get("resolved")).get("value") or _dict(binding.get("model")).get("requested")
            if isinstance(model, str) and model and model not in models.setdefault(step, []):
                models[step].append(model)
            effort = binding.get("effort")
            if isinstance(effort, str) and effort and effort not in efforts.setdefault(step, []):
                efforts[step].append(effort)

    minutes = {s: round((ended[s] - began[s]).total_seconds() / 60, 1) for s in ended
               if began.get(s) is not None and ended[s] is not None}
    fell = [s for s, k in last.items() if k == "node_error" and not ours(s)]
    return {"ok": True, "failed": [s for s in fell if not _declared(s, optional)],
            "absorbed": [{"node": s, "error": errors.get(s, "")} for s in fell if _declared(s, optional)],
            "errors": {s: errors.get(s, "") for s in fell},
            "retried": [{"node": s, "failures": n, "error": errors.get(s, "")} for s, n in falls.items()
                        if last.get(s) in DONE_ROWS and not ours(s)],
            "cost": cost, "uncosted": uncosted, "tokens": spent, "untokened": untokened, "minutes": minutes, "models": models, "efforts": efforts, "calls": calls,
            "resubmits": {loop: _resubmit(got) for loop, got in untils.items()}}


def _resubmit(untils: list) -> dict:
    """ループ 1 本の until の行（記録の順の (exit_code, ts)）から {count, minutes}。count は exit_code が bool でない int で 0 でない行。
    minutes は通らなかった行の ts から同じループの次の until の行の ts までの分の和"""
    count, seconds = 0, 0.0
    for (code, at), (_, after) in zip(untils, [*untils[1:], (None, None)]):
        if not isinstance(code, int) or isinstance(code, bool) or code == 0:
            continue
        count += 1
        if at is not None and after is not None:
            seconds += (after - at).total_seconds()
    return {"count": count, "minutes": round(seconds / 60, 1)}


def _count_call(calls: dict, step: str, event: dict) -> None:
    tool = event.get(TOOL_NAME)
    if event.get("type") != TOOL_CALL or tool not in (*PATH_TOOLS, SHELL_TOOL):
        return
    mine = calls.setdefault(step, {**{t: [] for t in PATH_TOOLS}, SHELL_TOOL: 0})
    if tool == SHELL_TOOL:
        mine[SHELL_TOOL] += 1
        return
    path = _dict(event.get(TOOL_INPUT)).get("file_path")
    if isinstance(path, str) and path and path not in mine[tool]:
        mine[tool].append(path)
