"""報告の行の組み立て（docs/design/report.md の 1.5。lib/runreport.py の cost_rows・resubmit_rows・head_cost・_model_lines の
ノードごとの行・_reads_lines の道具の呼びの部分・writer_fell の写し）。run の記録を読む口（read・own_prefix・facts）は lib/runlog.py
（integration.md の 4.5-2）で、chain も使うので、ここは import して名を引き継ぐ。

- cost_rows(run)・token_rows(run)・resubmit_rows(run)・head_cost(run, why): 費用のセクションの行（token_rows は費用の行の後のトークンの行）
- node_model_lines(run): ノードごとの実際に走った模型と effort の行
- calls_lines(run, why, repo): 役が呼んだ道具のセクションの行
- writer_fell(rows, step): 書き手のループが落ちたか
- child_falls(run): 落ちた node が fan_out の子の run の落ちなら、その子の run の記録から読んだ落ちた訳
"""
import json
import os
import pathlib
import re

import oneline   # lib/
from runlog import (COST_ROWS, PATH_TOOLS, SHELL_TOOL, TOKEN_FIELDS, UNCACHED, UNKNOWN_CACHE,   # noqa: F401 — lib/（read・own_prefix・facts は呼び手が transcript.* で引く）
                    facts, own_prefix, read)

QUOTA_CLASS = "quota_exhausted"
CALLS_HEAD = "役が自分で呼んだ道具（run の記録の provider_event。ノードごと）:"
UNSEEN = "取れない（U6）: Bash で読み書きしたファイル（道具への入力が command の字だけで、フックも Read・Edit・Write の外）"
CHILD_RUNS = "子の run の道具の呼びは子の run の記録に在り、上のノードごとの行に入らない"
CHILD_LOOPS = "子の run のループの回り直しは子の run の記録に在り、この行に入らない"
SHOWN_FILES = 3
CHILD_NO_FALL = "記録に落ちたノードが無い（親の記録は子が落ちたと言う）"
CHILD_NO_RECORD = "記録が読めない（run の記録の置き場に <子の run の id>.jsonl が無い）"
CHILD_UNREADABLE = "{name} が読めない（{why}）"
CHILD_FALL = re.compile(r"child (\d+) \(run ([0-9a-f]{8})\)")   # Archon が fan_out の node の誤りに書く子の run の名乗り（run の id の先頭 8 字）


def _dict(v) -> dict:
    return v if isinstance(v, dict) else {}


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


def _tokens_text(got: dict) -> str:
    """トークンの和 1 つの字。入力は cacheRead・cacheWrite を含む総量。内訳が不明な起動が在れば、キャッシュの内訳（下限にすぎない）もキャッシュ外も出さず、件数を言う"""
    unknown = got.get(UNKNOWN_CACHE, 0)
    split = (f"（うちキャッシュの読み {got['cacheRead']}・書き {got['cacheWrite']}・キャッシュ外 {got[UNCACHED]}）" if UNCACHED in got else "")
    return (f"入力 {got['input']}{split}・出力 {got['output']}"
            + (f"・キャッシュの内訳が不明な起動 {unknown} 件" if unknown else ""))


def token_rows(run: dict) -> list:
    """トークンの行: 合計の行と node ごとの行。トークンの記録を持つ行が 1 本も無ければ合計の行は「記録なし」。記録の無い node は
    その旨と件数（AI ノードでないノードか、提供元がトークンを返さなかった）"""
    tokens, untokened = run.get("tokens") or {}, run.get("untokened") or {}
    if not tokens:
        total = "トークンの合計: 記録なし"
    else:
        # node ごとの和（add_tokens の返り）をさらに足す。内訳が不明な起動が 1 つでも在れば、合計もキャッシュ外を出さない
        summed = {field: sum(got.get(field, 0) for got in tokens.values()) for field in (*TOKEN_FIELDS, UNKNOWN_CACHE)}
        if not summed[UNKNOWN_CACHE]:
            summed[UNCACHED] = summed["input"] - summed["cacheRead"] - summed["cacheWrite"]
        total = f"トークンの合計: {_tokens_text(summed)}"
    rows = [total]
    for s in sorted(set(tokens) | set(untokened)):
        n = untokened.get(s, 0)
        if s in tokens:
            rows.append(f"{s}: {_tokens_text(tokens[s])}" + (f"・記録の無い行 {n} 件" if n else ""))
        else:
            rows.append(f"{s}: トークンの記録なし（記録の無い行 {n} 件）")
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
    """費用のセクションの行（費用の合計・node ごとの費用と時間・トークン・回り直し）。記録が読めなければ「取れない（訳）」の 1 行。
    報告は run の中で走るので、合計は自分の費用を言う行の和"""
    if not run.get("ok"):
        return [f"費用: 取れない（{why or 'run の記録が読めない'}）"]
    total = sum((run.get("cost") or {}).values())
    return [f"費用の合計: ${total:.4f}（途中。報告は run の中で走るので run の和は読まず、自分の費用を言う行の和。言い直しの行は数えない）",
            *cost_rows(run), *token_rows(run), *resubmit_rows(run)]


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


def child_falls(run: dict) -> list:
    """落ちた node（failed・absorbed）の誤りが fan_out の子の run の落ちを名指していれば、その子の run の記録（親の記録と同じ置き場の
    <子の run の id>.jsonl）の落ちた node ごとに {child, node, error}、記録が読めなければ {child, why}。親の記録の誤りは子の失敗の
    総括（落ちた node の名と飛ばした数）だけで、AI の provider の 429 のような落ちた訳は子の記録にだけ在る"""
    log_dir = os.environ.get("LOG_DIR", "")
    errors = run.get("errors") or {}
    out = []
    for child in dict.fromkeys(m.group(2) for e in errors.values() for m in CHILD_FALL.finditer(str(e))):
        paths = sorted(pathlib.Path(log_dir).glob(f"{child}*.jsonl")) if log_dir else []
        if not paths:
            out.append({"child": child, "why": CHILD_NO_RECORD})
            continue
        try:
            rows = [json.loads(line) for line in paths[0].read_text(encoding="utf-8").splitlines() if line.strip().startswith("{")]
        except (OSError, ValueError) as e:
            out.append({"child": child, "why": CHILD_UNREADABLE.format(name=f"記録 {paths[0].name}", why=getattr(e, "strerror", None) or e)})
            continue
        fell = facts(rows)["errors"]
        if not fell:
            out.append({"child": child, "why": CHILD_NO_FALL})
        out += [{"child": child, "node": step, "error": (str(error).strip().splitlines() or ["誤りの文が無い"])[0]}
                for step, error in fell.items()]
    return out
