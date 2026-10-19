"""Archon の run の記録（$LOG_DIR/<WORKFLOW_ID>.jsonl）を読む部品（docs/design/report.md の 1.5。lib/runreport.py の transcript_facts・
cost_rows・resubmit_rows・head_cost・_model_lines のノードごとの行・_reads_lines の道具の呼びの部分・writer_fell と、
workflows/.shared/boundary.py の transcript・own_prefix の写し）。

- read() -> (行の並び, 読めなかった訳): 読めなければ (None, 訳)
- own_prefix() -> 自分の include の node の id の頭（無ければ ""）
- facts(rows, *, exclude_prefix, optional) -> {ok, failed, absorbed, errors, retried, cost, uncosted, minutes, models, efforts, calls, resubmits}
- cost_rows(run)・resubmit_rows(run)・head_cost(run, why): 費用のセクションの行
- node_model_lines(run): ノードごとの実際に走った模型と effort の行
- calls_lines(run, why, repo): 役が呼んだ道具のセクションの行
- writer_fell(rows, step): 書き手のループが落ちたか
"""
import json
import os
import pathlib

import oneline   # lib/
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
QUOTA_CLASS = "quota_exhausted"
CALLS_HEAD = "役が自分で呼んだ道具（run の記録の provider_event。ノードごと）:"
UNSEEN = "取れない（U6）: Bash で読み書きしたファイル（道具への入力が command の字だけで、フックも Read・Edit・Write の外）"
CHILD_RUNS = "子の run の道具の呼びは子の run の記録に在り、上のノードごとの行に入らない"
CHILD_LOOPS = "子の run のループの回り直しは子の run の記録に在り、この行に入らない"
SHOWN_FILES = 3


def _dict(v) -> dict:
    return v if isinstance(v, dict) else {}


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
    自身）は数えない。費用は自分の費用を言う行の cost_usd の和（無い行は uncosted に件数）。時間は node_start から最後の完了・失敗まで（分）。
    calls は役が呼んだ道具の node ごとの {Read・Edit・Write: ファイル, Bash: 回数}。resubmits はループごとの {count, minutes}"""
    if rows is None:
        return {"ok": False, "failed": [], "absorbed": [], "errors": {}, "retried": [], "cost": {}, "uncosted": {}, "minutes": {},
                "models": {}, "efforts": {}, "calls": {}, "resubmits": {}}

    def ours(step):
        return bool(exclude_prefix) and step.startswith(exclude_prefix)
    last, falls, errors, began, ended = {}, {}, {}, {}, {}
    cost, uncosted, models, efforts, calls = {}, {}, {}, {}, {}
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
            if isinstance(r.get("cost_usd"), (int, float)) and not isinstance(r.get("cost_usd"), bool):
                cost[step] = cost.get(step, 0.0) + float(r["cost_usd"])
            else:
                uncosted[step] = uncosted.get(step, 0) + 1
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
            "cost": cost, "uncosted": uncosted, "minutes": minutes, "models": models, "efforts": efforts, "calls": calls,
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


def cost_rows(run: dict) -> list:
    """node ごとの費用と時間の行"""
    steps = sorted(set(run.get("cost") or {}) | set(run.get("uncosted") or {}) | set(run.get("minutes") or {}))
    rows = []
    for s in steps:
        usd = (run.get("cost") or {}).get(s)
        n = (run.get("uncosted") or {}).get(s, 0)
        m = (run.get("minutes") or {}).get(s)
        parts = [f"${usd:.4f}" if usd is not None else "費用の記録なし"]
        if n:
            parts.append(f"費用の欄が無い行 {n} 件（AI ノードでないノードか、提供元が費用を返さなかった）")
        parts.append(f"{m} 分" if m is not None else "時間を測れない")
        rows.append(f"{s}: " + "・".join(parts))
    return rows


def resubmit_rows(run: dict) -> list:
    """ループの回り直しの行。回り直したループごとに 1 行、どれも 0 なら 0 回の 1 行、until の行が 1 本も無ければ数えられない旨の 1 行
    （空と合格を見分ける）。最後に子の run のループを数えない旨"""
    loops = run.get("resubmits") or {}
    again = [(loop, got) for loop, got in sorted(loops.items()) if got.get("count")]
    if not loops:
        rows = ["回り直し: 数えられない（記録にループの until の行が無い）"]
    elif not again:
        rows = [f"回り直し: 0 回（until の行を読んだループ {len(loops)} 本）"]
    else:
        rows = [f"{loop}: until が通らず回り直した回 {got['count']}（受け付けのループでは拒否で出し直した回）・{got['minutes']} 分"
                for loop, got in again]
    return [*rows, CHILD_LOOPS]


def head_cost(run: dict, why: str = "") -> list:
    """費用のセクションの行。記録が読めなければ「取れない（訳）」の 1 行。報告は run の中で走るので、合計は自分の費用を言う行の和"""
    if not run.get("ok"):
        return [f"費用: 取れない（{why or 'run の記録が読めない'}）"]
    total = sum((run.get("cost") or {}).values())
    return [f"費用の合計: ${total:.4f}（途中。報告は run の中で走るので run の和は読まず、自分の費用を言う行の和。言い直しの行は数えない）",
            *cost_rows(run), *resubmit_rows(run)]


def node_model_lines(run: dict) -> list:
    """node ごとの実際に走った模型と effort（呼ぶ人の名指しも層の付け替えも解いた後の値）の行"""
    models, efforts = run.get("models") or {}, run.get("efforts") or {}
    if not run.get("ok"):
        return ["run の記録が読めない"]
    if not models:
        return ["記録に模型の欄が無い"]
    return [f"{s}: {', '.join(ms)}{'（run の途中で替わった）' if len(ms) > 1 else ''}"
            + (f"（effort: {', '.join(efforts[s])}）" if efforts.get(s) else "") for s, ms in sorted(models.items())]


def _shown(path: str, repo) -> str:
    """repo の中のパスは repo からの相対、ほかは字のまま"""
    if repo:
        try:
            return pathlib.Path(path).relative_to(pathlib.Path(repo)).as_posix()
        except ValueError:
            pass
    return path


def calls_lines(run: dict, why: str, repo) -> list:
    """役が呼んだ道具のセクションの行（run の記録の provider_event。フックの証拠のファイルは読まない）"""
    calls = _dict(run.get("calls"))
    out = [CALLS_HEAD]
    if not run.get("ok"):
        out.append(f"  - run の記録が読めない（{why or '訳の記録が無い'}）")
    elif not calls:
        out.append("  - 道具を呼んだノードが run の記録に無い")
    for step, mine in calls.items():
        files = list(dict.fromkeys(p for tool in PATH_TOOLS for p in mine[tool]))
        shown = ("・".join(_shown(p, repo) for p in files[:SHOWN_FILES])
                 + (f" ほか {len(files) - SHOWN_FILES} 件" if len(files) > SHOWN_FILES else ""))
        out.append(f"  - {step}: " + "・".join(f"{tool} {len(mine[tool])} 件" for tool in PATH_TOOLS)
                   + (f"（ファイル: {shown}）" if files else ""))
    shell = {step: mine[SHELL_TOOL] for step, mine in calls.items() if mine[SHELL_TOOL]}
    counted = (f"。Bash の呼び {sum(shell.values())} 回" + (": " + "・".join(f"{s} {n}" for s, n in shell.items()) if shell else "")
               if run.get("ok") else "。Bash の呼びは run の記録が読めないので数えられない")
    return [*out, UNSEEN + counted, CHILD_RUNS]


def writer_fell(rows, step: str) -> dict | None:
    """run の記録の行で、書き手のループの node step の最後の行が node_error なら {error: 誤りの文の 1 行目, quota: 使用枠が切れて
    落ちたか}。済んだ・飛ばされた・行が無い・記録が読めない（rows が None）なら None。resume で書き直した run は最後の行が済んだ行なので None"""
    last = None
    for r in rows or ():
        if isinstance(r, dict) and r.get("step") == step and r.get("type") in (*COST_ROWS, "node_skipped"):
            last = r
    if last is None or last.get("type") != "node_error":
        return None
    failure = _dict(_dict(_dict(last.get("execution")).get("lifecycle")).get("providerFailure"))
    first = (str(last.get("error") or "").strip().splitlines() or [""])[0]
    return {"error": oneline.one_line(first) or "誤りの文が無い", "quota": failure.get("class") == QUOTA_CLASS}
