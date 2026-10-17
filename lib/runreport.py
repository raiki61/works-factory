"""機械の報告・次の依頼・前の失敗・費用と時間・語の定義の節を組み、書き手の返答を受け付けて AI の報告を組む（報告のブロックの部品）。

元は works/.shared/core/report.py と works/blk-report/lib/report_roles.py の、盤面（b）を読む関数。ここでは同じ名のまま、
ブロックの返り・関所の答え・始めの記録・型つきの成果物の読み・run の記録の行を引数で受ける（盤面の偽物は作らない）。指し札は呼び手が
開けたファイルのパスの字にして渡す（開けなければ None）。指し札の隣のファイル（docs/design.md の「書き方の決め」の名指しの
隣のファイル）は指し札の先と同じフォルダから読む。

- transcript_facts(rows, *, exclude_prefix, optional) -> {ok, failed, absorbed, errors, retried, cost, uncosted, minutes, models, efforts, calls, resubmits}
  （run の記録の行の読み。efforts は models と同じ形の、行の execution.binding.effort。resubmits はループごとの {count: until が通らなかった回,
  minutes: 回り直しにかかった分}）
- 報告の ## 模型 のセクション（_model_lines）: 群ごとの選びの行（headdepth.groups_lines）・ノードごとの実際に走った模型と effort・結末の行
  （_outcome_line。結末の語・最後の承認ノードの答え・目ごとの語・次の run に渡す物と持ち越した失敗の件数・DATA_PLACES）
- cost_rows(facts)・resubmit_rows(facts)・head_cost(facts, why): 節ごとの費用と時間の行・ループの回り直しの行と、費用の節の行（元 report.py:1769・1806）
- next_request(returns, left, closed, *, beside, exit_doc)・prior_failures(returns, left): 次の依頼の findings と前の失敗の行（元 report.py:784・720）
- ledger_state(returns, gates, start): 問いの台帳の保留の行と答えた行（元 gatemarks.held_lines・answered_lines）
- answer_drafts(returns, gates, start, spec_changed, spec_unchecked): 人の判断を待つ項目への答えの下書き（元 gatemarks.answer_drafts。承認し直すかの問いも）
- glossary_section(text, terms, pack)・pack_terms(): 本文と機械の事実に現れる語だけの定義の節（元 report_roles.py の glossary_section）
- build(returns, gates, typed, transcript, outcome, stop_reason, *, out_dir, start, problems, run_id, transcript_why, repo,
  report_name, line) -> {report, next_request, prior_failures, ai_go}（元 report.py:2000。line は線の値）
- fallback_report(out_dir, why, name, *, user_env): 思わぬ誤りの時の機械の報告（名は呼び手が渡す。facts の報告を上書きしない名）
- cold_body(raw)・accept(reply, cold, *, out_dir)・collect(machine, *, out_dir, stamp)・stamp(run_id, workflow_file, rnd, start): 書き手の
  返答の受け付けと AI の報告（元 report_roles.py の write_cold_prep・accept・collect・stamp）
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import answer  # noqa: E402
import baseline_red  # noqa: E402
import carry  # noqa: E402
import changemap  # noqa: E402
import conflict  # noqa: E402
import depth as depthlib  # noqa: E402
import declared_checks  # noqa: E402
import design  # noqa: E402
import diverted  # noqa: E402
import fixbeside  # noqa: E402
import fixboard  # noqa: E402
import fixture  # noqa: E402
import entry as entrylib  # noqa: E402
import eyeverdict  # noqa: E402
import forge  # noqa: E402
import gatemarks  # noqa: E402
import gatepolicy  # noqa: E402
import green_cert  # noqa: E402
import headdepth  # noqa: E402
import judgeverify  # noqa: E402
import marks  # noqa: E402
import oneline  # noqa: E402
import outcome as oc  # noqa: E402
import outpurpose  # noqa: E402
import planblk  # noqa: E402
import planmarks  # noqa: E402
import prcheck  # noqa: E402
import premises  # noqa: E402
import promptsection  # noqa: E402
import querytest  # noqa: E402
import reads  # noqa: E402
import report  # noqa: E402
import replan  # noqa: E402
import report_roles  # noqa: E402
import versions  # noqa: E402
import rolekit  # noqa: E402
import seal as seallib  # noqa: E402
import startrec  # noqa: E402
import stopby  # noqa: E402
import structmark  # noqa: E402
import userenv  # noqa: E402
import worldmark  # noqa: E402

as_dict = oc.as_dict
PACK_TERMS = _HERE / "glossary.json"
OUT_DIR = "report"                      # run の置き場の中の報告の置き場（報告のサブグラフの script が run の置き場に足す）
UNWRITTEN = "report-unwritten.md"       # 報告を組めない時の機械の報告（fallback_report。facts の report.md を上書きしない名）
AI_FILE = "ai.json"                     # 受け付けた書き手の返答と初見の判定（collect が読む）
AI_REPORT_FILE = "report-ai.md"         # AI の報告（元 report_roles.REPORT_NAME）
PREV_ANSWER_FILE = "prev-answer.json"   # 拒んだ回の書き手の本文と、周ごとの引き継ぎのメモ（次の周の書き手が読む）
REPORT_NODE = report_roles.REPORT_NODES[-1]   # 拒否の行の node（count_rejects が数える節の名）
# 初見の読み手（report.cold_check）の返答の型。型の正本は工程の cold の節の output_format で、これと同じかを試験が縛る
COLD_SCHEMA = {"type": "object", "required": ["verdict", "stops", "guessed", "decidable"], "additionalProperties": False,
               "properties": {"verdict": {"type": "string", "enum": ["pass", "redesign-needed"]},
                              "stops": {"type": "array", "items": {"type": "string"}},
                              "guessed": {"type": "array", "items": {"type": "string"}},
                              "decidable": {"type": "boolean"}}}

COST_ROWS = ("node_complete", "node_error")   # 自分の費用を報告しうる行
DONE_ROWS = ("node_complete", "node_skipped")
OWN_SPEND = "node"                            # execution.accounting のうち、自分の費用を言う語（ほかは言い直しの行）
# 役が呼んだ道具の行（止めた実行基盤の logger.ts の logProviderEvent が {type, step, …, event} で書き、event は provider-contract の
# tool_call {type, toolCallId, name, rawInput}。境の試験の写しの表が源と照らす）
PROVIDER_ROW = "provider_event"
PROVIDER_EVENT = "event"
TOOL_CALL = "tool_call"
TOOL_NAME = "name"
TOOL_INPUT = "rawInput"
PATH_TOOLS = ("Read", "Edit", "Write")         # 道具への入力の file_path でファイルを名指す道具
SHELL_TOOL = "Bash"                            # 読み書きしたファイルを入力から取れない道具（数だけ数える）
# ループの until の行（止めた実行基盤の logger.ts の logExecOutput が {type, step, content: 呼びの名, exit_code} で書き、dag-executor.ts の
# ループの until の呼びが content を '<until_bash>'、step を <ループの id>-iteration-<回> にする。境の試験の写しの表が源と照らす）
EXEC_ROW = "exec_output"
EXEC_LABEL = "content"
EXIT_CODE = "exit_code"
UNTIL_ROW = "<until_bash>"
ITERATION_MARK = "-iteration-"

GREEN_HEADING = promptsection.Section("## 緑の認証（全部の周）", human=report.FOR_READERS)
EYES_HEADING = promptsection.Section("## 独立の目", human=report.FOR_READERS)
NOTES_HEADING = promptsection.Section("## 注意（読めなかった物）", human=report.FOR_READERS)
# AI の報告に機械の事実を付ける時の、機械の「人が決めること」の見出しの言い換え（判断は書き手の頭の 1 か所に集める）
MACHINE_DECISIONS = promptsection.Section("## 1. 人の判断を待つ物の機械の数え（判断の本文は報告の頭）", human=report.FOR_READERS)
RED_KEPT = (green_cert.INHERITED, green_cert.ENVIRONMENT)   # 認証が通した赤（元から赤・環境の赤）
# 機械の報告の冒頭に在れば、書き手の頭にもそのまま要る句（accept が照らす）
HEAD_NOTES = (*green_cert.RAN_NOTES, userenv.NOTE)
GATE_RUNS = (("test-gate-base", "直す前のテスト"), ("test-gate-final", "最後のテスト"))
EYE_KEYS = ("eye", "status", "reason")
GAVE_UP_WHERE = "修正の受け付けを通らなかった単位"
PLAN_GAVE_UP_WHERE = "受け付け 計画"          # 元 report.ACCEPT_WHERE（受け付け <名>）の計画の行
REPLAN_GAVE_UP_WHERE = "案の直しを終えられなかった項目 {item}"
STOPPED_WHERE = "止めた段"                     # 前の失敗の、止めの語で止めた段の行（元 accept-last.json の ok でない行の代わり）
FIX_PLAN = "p2.fix_plan.json"                 # 計画の隣の修正案の役の返答（関所の決め手の欄つき）
HYPOTHESIS = "仮説"                           # 前提の役が実測でなく仮説で書いた制約の kind
GROUP_WHERE = "組"
REJUDGE_LEFT_WHERE = "判定（再審されずに残った異議）"
UNSEEN = "取れない（U6）: Bash で読み書きしたファイル（道具への入力が command の字だけで、フックも Read・Edit・Write の外）"
EYE_PASSES_HEAD = ("修正前の承認ノードで通した行（人が通したか、無人の run が推しで通したので、独立の目 R4 の問いから外して聞き直さ"
                   "なかった行。どちらかは行ごとに書く）")
# 線の値（線の collect が report の入力で渡す物。docs/design.md の report の返り）の行の頭
DEFERRED_HEAD = "無人の run で修正前の承認ノードに載せずに報告へ回した問い（承認ノードを開かずに修正へ進めた）"
FINAL_REASONS_HEAD = "最後の承認ノードを開ける理由（無人の run では開かずに止めた理由）"
PRIOR_IN_HEAD = "依頼が運んだ前の run の失敗（prior_failures）"
NO_REDEPTH = "直した後の深さの上げ直しの出力が無い（上げ直しのノードが走っていない）。計画の深さのまま"
NO_REJECT = "受け付けの最後の拒否の控えが置き場に無い"
# 止めた段の拒否の控えを探す置き場（段の返りの指し札の欄。指し札の先と同じフォルダの下に受け付けが拒否を残す）
REJECT_PLACES = {"judge": "judgment", "rejudge": "judgment", "plan": "plan", "replan": "plan", "plan-review": "review",
                 "replan-review": "review", "fix": "diff", "test-gate-base": "evidence", "test-gate-final": "evidence",
                 "eyes": "structure_after", "merge-seal": "diff", "merge-apply": "diff"}
RESIDUE_HEAD = "残り"   # 元 always_rows の残りの件数の行（結末に依らず 0 件も）
MISSING_EYE_NOTE = "結果が無い目は阻害 0 件でなく判定が無い（再実行の要あり。深さで省いた目は数えない）"   # 元 MISSING_GATE_NOTE
FORGE_HEAD = "PR を持つホスト（forge）"   # 元 report.FORGE_HEAD
POLICY_CHANGED_HEAD = "方針の文書が始めに固定した版から変わったまま終わった"
APPLY_HEAD = "差分を対象に当てる"
BACKED_OUT_HEAD = "当ててから確かめ直しが赤か落ちて戻した組"   # 組の合わせの意味の食い違い（持ち主の決め clash-goes-to-ruling）
REPAIRED_HEAD = "合わせ役が直して当てた組"   # 確かめ直しが赤で戻した組か字で当たらなかった組を、合わせのループが組の変えたファイルの中だけで直した（fix.groups の clash.outcome repaired）
UNRESTORED_GROUP_HEAD = "戻せず親の作業ツリーに当たったままの組（人が確かめる）"   # fixboard.UNRESTORED。線は先へ進めずに止めた
STOP_OUTCOMES = ("stopped_by_request", "stopped_by_human", "stopped_by_line", "needs_human")   # 止まった run の結末（bin/apply が拒む）

POINTERS = (("judge", "judgment", "判定"), ("judge", "purpose", "目的"), ("judge", "world", "定石"),
            ("judge", "spec", "仕様"), ("judge", "out_of_purpose", "目的の外の所見"),
            ("plan", "plan", "計画"), ("plan", "structure", "構造の目"), ("plan", "ripple", "波及"),
            ("plan-review", "review", "事前審査"), ("plan-review", "design", "独立設計"),
            ("fix", "diff", "差分"), ("fix", "conflicts", "申し出と裁定"),
            ("test-gate-base", "baseline", "直す前の結末"), ("test-gate-base", "evidence", "試験の記録（直す前）"),
            ("test-gate-final", "evidence", "試験の記録（最後）"), ("eyes", "structure_after", "直した後の構造"),
            ("merge-seal", "diff", "封じた差分"), ("merge-apply", "diff", "置いた差分"))


def _list(v) -> list:
    return v if isinstance(v, list) else []


def _write_text(path: pathlib.Path, text: str) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    report._write_text(path, text)
    return path


def _ret(returns: dict, rid: str) -> dict:
    return as_dict(oc.latest(returns, rid))


def _beside(returns: dict, rid: str, field: str, name: str) -> pathlib.Path | None:
    """段の返りの指し札の先と同じフォルダの name（指し札が無ければ None）"""
    p = _ret(returns, rid).get(field)
    return pathlib.Path(p).with_name(name) if isinstance(p, str) and p else None


def _first_beside(returns: dict, name: str) -> pathlib.Path | None:
    """1 回目の判定（judge の差し込み）の judgment の隣の name。世界の解・局所レビュー・並行 PR の控えは判定の道の置き場にだけ在り、
    再審の judgment の隣には無い（docs/design.md の隣のファイル）。指し札が無ければ None"""
    p = as_dict(returns.get("judge")).get("judgment")
    return pathlib.Path(p).with_name(name) if isinstance(p, str) and p else None


def eyes_skip(line):
    """線の値 line の redepth が許した、省いてよい目（skip_optional。無ければ None）"""
    redepth = as_dict(line).get("redepth")
    return redepth.get("skip_optional") if isinstance(redepth, dict) else None


def fix_beside(returns: dict) -> dict:
    """修正の段ごとの diff の隣の約束のファイルの見え方（fixbeside.read。fix の返りの diffs の先のフォルダ。1 回目と 2 度目の修正）"""
    return fixbeside.read(oc.fix_folders(returns))


def eye_notes_dir(returns: dict) -> pathlib.Path | None:
    """独立の目の返り notes（premise-inputs.json）のフォルダ（隣の r4-gate-passes.json・premise-check.json と一緒の約束）。無ければ None"""
    p = as_dict(returns.get("eyes")).get("notes")
    return pathlib.Path(p).parent if isinstance(p, str) and p else None


def _read_beside(returns: dict, rid: str, field: str, name: str):
    """(中身, 読めなかった訳)。指し札が無い・隣のファイルが無ければ (None, "")"""
    path = _beside(returns, rid, field, name)
    if path is None or not path.is_file():
        return None, ""
    try:
        return oc.read_json(path), ""
    except (OSError, ValueError) as e:
        return None, f"{path} が読めない: {oneline.one_line(e)}"


# ---------------------------------------------------------------- run の記録
def _declared(step: str, optional) -> bool:
    """受け止めると宣言した段の中の節か。宣言の 1 つは、区切り（__・-）で終わる節の id の頭か、節の id そのもの（そのループの中の
    節 <id>.<中の id> も含む）。区切りの無い頭で比べると、fix__lens が止める段の fix__lens-collect まで受け止めてしまう"""
    return any(isinstance(head, str) and head
               and (step.startswith(head) if head.endswith(("__", "-")) else step == head or step.startswith(head + "."))
               for head in optional or ())


def transcript_facts(rows, *, exclude_prefix: str = "", optional=()) -> dict:
    """run の記録の行（実行基盤の logger の JSONL を 1 行ずつ読んだ dict）から、節ごとの事実。rows が None なら ok: False。
    最後の行が node_error の節は、線が受け止めると宣言した段（optional。線の YAML の 1 か所が宣言する、節の id の頭か節の id の並び。_declared）の中なら
    受け止めた落ち（absorbed）、宣言の外なら後にほかの節が始まっていても run を途中で終わらせた落ち（failed）。元 report.split_fallen
    （:545。宣言は元 _optional :533 の線の YAML の [optional]）。報告は線の出口（collect の後）で走るので、元の出口の印は在るものと
    読む。errors は落ちた節の最後の誤りの文、
    retried は node_error の後に済んだ節 [{node, failures, error}]（落ちた回と最後の誤り。元 reads.retried_nodes）。
    exclude_prefix で始まる節（報告のブロック自身）は数えない。費用は自分の費用を言う行（execution.accounting が node か無い）の
    cost_usd の和。cost_usd の無い行は 0 と数えず uncosted に件数を積む。時間は node_start から最後の node_complete・node_error まで（分）。
    calls は役が呼んだ道具（provider_event の tool_call の行）の節ごとの {Read・Edit・Write: 名指したファイル（記録の順で重ねない）,
    Bash: 呼んだ回数}。resubmits はループ（step の ITERATION_MARK の前）ごとの {count, minutes}（ループの until の行から。_resubmit）。
    exclude_prefix で始まるループは数えない"""
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
            _count_call(calls, step, as_dict(r.get(PROVIDER_EVENT)))
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
            execution = as_dict(r.get("execution"))
            if execution.get("accounting", OWN_SPEND) != OWN_SPEND:
                continue
            if isinstance(r.get("cost_usd"), (int, float)) and not isinstance(r.get("cost_usd"), bool):
                cost[step] = cost.get(step, 0.0) + float(r["cost_usd"])
            else:
                uncosted[step] = uncosted.get(step, 0) + 1
            model = as_dict(as_dict(as_dict(execution.get("binding")).get("model")).get("resolved")).get("value") \
                or as_dict(as_dict(execution.get("binding")).get("model")).get("requested")
            if isinstance(model, str) and model and model not in models.setdefault(step, []):
                models[step].append(model)
            effort = as_dict(execution.get("binding")).get("effort")
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
    """ループ 1 本の until の行（記録の順の (exit_code, ts)）から {count, minutes}。count は exit_code が bool でない int で 0 でない行
    （字の exit_code は打ち切りで、回り直しではない）。minutes は通らなかった行の ts から同じループの次の until の行の ts までの分の和
    （次の行が無いか、ts が読めない行は足さない）"""
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
    path = as_dict(event.get(TOOL_INPUT)).get("file_path")
    if isinstance(path, str) and path and path not in mine[tool]:
        mine[tool].append(path)


def cost_rows(facts: dict) -> list:
    """節ごとの費用と時間の行（元 report.py:1769 の cost_rows を run の記録の行の形で書き直した物。読む時に作り、保存しない）"""
    steps = sorted(set(facts.get("cost") or {}) | set(facts.get("uncosted") or {}) | set(facts.get("minutes") or {}))
    rows = []
    for s in steps:
        usd = (facts.get("cost") or {}).get(s)
        n = (facts.get("uncosted") or {}).get(s, 0)
        m = (facts.get("minutes") or {}).get(s)
        parts = [f"${usd:.4f}" if usd is not None else "費用の記録なし"]
        if n:
            parts.append(f"費用の欄が無い行 {n} 件（AI ノードでないノードか、提供元が費用を返さなかった）")
        parts.append(f"{m} 分" if m is not None else "時間を測れない")
        rows.append(f"{s}: " + "・".join(parts))
    return rows


def resubmit_rows(facts: dict) -> list:
    """ループの回り直しの行（run の記録のループの until の行から作る。読む時に作り、保存しない）。回り直したループ（count が 1 以上）ごとに 1 行、
    どのループも 0 なら 0 回の 1 行、until の行が 1 本も無ければ数えられない旨の 1 行（空と合格を見分ける）。最後に子の run のループを数えない旨"""
    loops = facts.get("resubmits") or {}
    again = [(loop, got) for loop, got in sorted(loops.items()) if got.get("count")]
    if not loops:
        rows = ["回り直し: 数えられない（記録にループの until の行が無い）"]
    elif not again:
        rows = [f"回り直し: 0 回（until の行を読んだループ {len(loops)} 本）"]
    else:
        rows = [f"{loop}: until が通らず回り直した回 {got['count']}（受け付けのループでは拒否で出し直した回）・{got['minutes']} 分"
                for loop, got in again]
    return [*rows, CHILD_LOOPS]


def head_cost(facts: dict, why: str = "") -> list:
    """費用の節の行（元 report.py:1806）。記録が読めなければ「取れない（訳）」の 1 行。報告は run の中で走るので、合計は節の和を
    途中の値として出す"""
    if not facts.get("ok"):
        return [f"費用: 取れない（{why or 'run の記録が読めない'}）"]
    total = sum((facts.get("cost") or {}).values())
    return [f"費用の合計: ${total:.4f}（途中。報告は run の中で走るので run の和は読まず、自分の費用を言う行の和。言い直しの行は数えない）",
            *cost_rows(facts), *resubmit_rows(facts)]


DATA_PLACES = ("固定のデータの在り処（鍵は run の id）: 選び = 判定の置き場の隣の depth-head.json の groups／"
               "実際の値 = $LOG_DIR/<run の id>.jsonl の行の execution.binding／"
               "結末 = メイングラフの出力 result の outcome・stop_reason")


def _outcome_line(outcome: str, gates: dict, returns: dict, carried: int, prior: list, eyes_skip=None) -> str:
    eyes = returns.get("eyes")
    seen = NO_EYES if eyes is None else "・".join(f"{name.upper()}: {_eye_word(eyes, name, eyes_skip)}" for name in oc.EYE_NAMES)
    return "／".join([f"結末: {report.OUTCOME_WORDS.get(outcome, '結末が決まらない')}（{outcome}）",
                     f"最後の承認ノード gate-final: {_gate_line(gates.get('gate-final'))}", f"独立の目: {seen}",
                     f"次の run に渡す物: {carried} 件", f"持ち越した失敗: {len(prior)} 件", DATA_PLACES])


def _model_lines(facts: dict, head_doc, outcome_line: str) -> list:
    """## 模型 のセクション: 群ごとの役の選び（headdepth.groups_lines。head_doc は判定の隣の控え）・ノードごとの実際に走った模型と
    effort（呼ぶ人の名指しも層の付け替えも解いた後の値）・結末の行（_outcome_line）"""
    models, efforts = facts.get("models") or {}, facts.get("efforts") or {}
    if not facts.get("ok"):
        nodes = ["run の記録が読めない"]
    elif not models:
        nodes = ["記録に模型の欄が無い"]
    else:
        nodes = [f"{s}: {', '.join(ms)}{'（run の途中で替わった）' if len(ms) > 1 else ''}"
                 + (f"（effort: {', '.join(efforts[s])}）" if efforts.get(s) else "") for s, ms in sorted(models.items())]
    return [*headdepth.groups_lines(head_doc), *nodes, outcome_line]


# ---------------------------------------------------------------- 問いの台帳（判定の judgment.json の questions）
def _request_answers(start: dict) -> list:
    """依頼の answers（始めの記録の欄。元 gatemarks.request_answers）"""
    return [a for a in _list(as_dict(start).get("answers")) if isinstance(a, dict)]


def ledger(returns: dict, gates: dict, start: dict):
    """問いの台帳の値の見え方（gatemarks.ledger）: 判定（再審が在ればその）の judgment.json の問いと単位の全部（開いていない単位も。
    最後の関所と fix の直す義務と同じ単位で、関所の答えが返す単位を読む）、始めの記録の依頼の answers、
    修正前の関所の答え {decision, text, asked}、1 回目の判定の隣の結び（answer-ties.json。再審の判定の隣には無い）、判定の隣の素材の状態、
    無人の run か（判定の推しを答えに採る。gatemarks.run_push）"""
    first = as_dict(returns.get("judge")).get("judgment")
    ties = gatemarks.ties_of(marks.load(pathlib.Path(first).with_name(gatemarks.BESIDE[0]))) if isinstance(first, str) and first else []
    mats, _ = oc.materials(returns)
    return gatemarks.ledger(oc.judgment_doc(returns), answers=_request_answers(start), gate=gates.get("gate-before-fix"), ties=ties,
                            materials=mats, takes_push=gatepolicy.unattended_of(start))


def ledger_state(returns: dict, gates: dict, start: dict) -> dict:
    """問いの台帳の読み（gatemarks の held_lines・answered_lines・unmatched_answer_lines・answer_tie_lines を ledger の見え方で引いた物）:
    {held: [(問い（直す単位に入れられなかった行は None）, 行)], answered: [行], unmatched: [行], ties: [行], unread_holds: [行],
    drafts: [(保留の問い, answer_key)]}。
    関所に載る問いは fork と escalate だけで、答えたのは依頼の answers がこの問いだけに当たるか（字の一致・判定の結び・測れていない素材の
    名）、修正前の関所が通す語を受けてこの問いの行を聞き（答えの asked）、一言が「保留: <key>」と名指していない物。依頼の答えが当たった
    測れていない素材は、命令と出力が在れば残りに数えない。ties は判定が単位にしなかった作り直しの行（answer_tie_lines）、unread_holds は
    修正前の関所の一言の「保留」で台帳の key を拾えなかった断片（gatemarks.unread_hold_lines。元は報告の冒頭 1 の関所の答えの直後）"""
    b = ledger(returns, gates, start)
    held_qs = gatemarks.held_questions(b)
    lines = gatemarks.held_lines(b)
    held = [*zip(held_qs, lines), *((None, line) for line in lines[len(held_qs):])]
    done = gatemarks.answered_ledger_lines(b)
    for n, st in gatemarks.unmeasured(b).items() if b.answers else ():
        a = gatemarks.material_answer(b, n)
        if a is not None:
            how = (f"{gatemarks.HAND_CHECKED}。残りに数えない" if gatemarks._measured(a)
                   else "command と output が無いので測りの代わりにせず、測れていないまま残りに数える")
            done.append(f"素材 {n}（{st}）: {how}——{gatemarks.answer_note(a)}")
    return {"held": held, "answered": done, "unmatched": gatemarks.unmatched_answer_lines(b), "ties": gatemarks.answer_tie_lines(b),
            "unread_holds": gatemarks.unread_hold_lines(b), "drafts": [(q, gatemarks.answer_key(b, q)) for q in held_qs]}


# ---------------------------------------------------------------- 答えの下書き
def _fix_plan_rows(returns: dict) -> list:
    """修正案の狭める行 [(文, 決め手の欄の形, 節)]（計画の隣の p2.fix_plan.json の plan[].narrows）"""
    doc, _ = _read_beside(returns, "plan", "plan", FIX_PLAN)
    return [(f"修正案 {i + 1} が狭める能力: {n.get('what')}——{n.get('why')}", n, "p2.fix_plan")
            for i, p in enumerate(_list(as_dict(doc).get("plan"))) if isinstance(p, dict)
            for n in _list(p.get("narrows")) if isinstance(n, dict)]


def _face_rows(returns: dict) -> list:
    """事前審査の人に回す種類の穴 [(文, 決め手の欄の形, 節)]（事前審査の review の faces）"""
    p = _ret(returns, "plan-review").get("review")
    try:
        doc = oc.read_json(p) if isinstance(p, str) and p else {}
    except (OSError, ValueError):
        return []
    return [(f"事前審査の穴 [{f.get('kind')}] {f.get('key')}: {f.get('why')}", f, "p2.plan_review")
            for f in _list(as_dict(doc).get("faces")) if isinstance(f, dict) and f.get("kind") in fixboard.HUMAN_FACE_KINDS]


def _world_rows(returns: dict) -> list:
    """定石から外れた修正案の項目 [(文, 決め手の欄の形, 節)]（元 gatemarks.world_items: 計画の控え plan-fields.json の fields の
    欄 structure の世界の解の答えのうち従わない物を、判定の定石の行と合わせる）"""
    wp, pp = _ret(returns, "judge").get("world"), _ret(returns, "plan").get("plan")
    if not (isinstance(wp, str) and wp and isinstance(pp, str) and pp):
        return []
    try:
        world = {r["class_id"]: r for r in worldmark.rows(wp)}
        fields = oc.read_json(pp)
    except (OSError, ValueError):
        return []
    out = []
    for n, f in enumerate(_list(as_dict(fields).get("fields")), 1):
        for a in _list(as_dict(f).get("structure")):
            if isinstance(a, dict) and isinstance(a.get(worldmark.ANSWER_KEY), str) and a.get("follows") is not True:
                row = world.get(a[worldmark.ANSWER_KEY]) or {"class_id": a[worldmark.ANSWER_KEY]}
                line = worldmark.gate_line(row, a)
                out.append((f"修正案 {n} の{line}", {"decided_by": str(a.get("deviation") or ""), "world": line}, planmarks.NODE))
    return out


def _gate_draft(question: str, rows: list) -> dict:
    """関所の項目 1 つの下書き（元 gatemarks.answer_drafts の関所の項目の側）: 項目の文が修正案・事前審査・定石の外れの行で始まれば
    その行の決め手（recommend・no_narrow・world）、当たらなければ文の推しの尾"""
    for text, mark, node in rows:
        if question.startswith(text):
            return gatemarks._gate_draft(text, mark, node)
    push = gatemarks.PUSH_IN.findall(question) if gatemarks.PUSH_TAIL.search(question) else []
    if push:
        return gatemarks._draft(gatemarks.PUSH_TAIL.sub("", question), push[-1].strip(), f"{gatemarks.named(gatemarks.GATE_NODE)}の項目の文の推し")
    return gatemarks._gate_draft(question, {}, gatemarks.GATE_NODE)


def _ask_draft(q: dict, key: str) -> dict:
    """台帳の問い 1 つの下書き（元 gatemarks._ask_draft。question は answer_key: 出どころが測れていない素材の名でこの問いだけに
    当たればその名、ほかは問いの key）"""
    push = gatemarks.reason_push(q)
    if push:
        return gatemarks._draft(key, push, f"{gatemarks.ASK_HEAD} {key} の理由の推し（判定の役）")
    opts = "・".join(str(o) for o in q.get("options") or []) or "（無し）"
    return gatemarks._draft(key, "", f"{gatemarks.ASK_HEAD} {key} の選択肢", f"推しを判定の役が書いていない。選択肢から人が答えを text に書く: {opts}")


SPEC_CHANGED_NOTE = ("機械は承認し直さない。変更を確かめ、承認し直すなら次の run で仕様の段（spec=on）を回して承認し、戻すならテストを承認の版に"
                     "戻して直す依頼にする。採らないなら行を消す")


def spec_changed_of(line: dict | None) -> list:
    """線の値の承認し直すかの問い（線の spec-check の questions。字の行だけ）"""
    return [q for q in _list(as_dict(line).get("spec_changed")) if isinstance(q, str) and q.strip()]


def spec_unchecked_of(line: dict | None) -> bool:
    """線の値の、受け入れ条件のテストが変わったかを照らせなかったか（線の spec-check の unchecked）"""
    return as_dict(line).get("spec_unchecked") is True


def answer_drafts(returns: dict, gates: dict, start: dict, spec_changed=(), spec_unchecked=False) -> list:
    """人の判断を待つ項目への答えの下書き [{question, text, draft, source, note?}]（元 gatemarks.answer_drafts）:
    ⓪承認の後に受け入れ条件のテストが変わった問い（線の spec-check の questions）ごとに 1 行。照らせなかった（spec_unchecked）時は
    source が「照らせなかった」と言う。機械は承認し直さない
    ①無人の run で修正前の関所が通さなかった事前審査の問いと、人の居る run でも無人の run でも R4 が人に回した問い（元
    report.next_items の pending_human）ごとに 1 行。項目の文が修正案の狭める行・事前審査の穴・定石の外れに当たれば、その行の決め手
    （推し recommend・狭めない案 no_narrow・世界の解 world）を使う
    ②人の居る run でも無人の run でも、保留のままの台帳の問いごとに 1 行（理由の推しか選択肢）
    ③問いの立っていない測れていない素材ごとに 1 行（materials.json の reason つき。依頼の answers が当たった素材は除く）
    同じ question の行は 1 度だけ。機械は関所にも問いにも答えない——下書きは依頼の入口が拒むので、人が見直してから使う"""
    rows = [*_fix_plan_rows(returns), *_face_rows(returns), *_world_rows(returns)]
    asked = oc.eye_questions(returns)
    if gatepolicy.unattended_of(start) and as_dict(gates.get("gate-before-fix")).get("decision") not in oc.PASS_WORDS:
        asked = gatemarks.row_texts(_list(_ret(returns, "plan-review").get("questions"))) + asked
    source = gatemarks.spec_words(spec_unchecked).source
    out = [gatemarks._draft(q, "", source, SPEC_CHANGED_NOTE) for q in spec_changed if isinstance(q, str) and q.strip()]
    out += [_gate_draft(q, rows) for q in asked if isinstance(q, str) and q.strip()]
    missing = oc.unmeasured(returns)
    out += [_ask_draft(q, key) for q, key in ledger_state(returns, gates, start)["drafts"]]
    mats, _ = oc.materials(returns)
    asked = {oc.origin_of(q, missing) for q in oc.ledger(returns)}
    b = ledger(returns, gates, start)
    out += [gatemarks._material_draft(n, st, as_dict(mats.get(n)).get("reason")) for n, st in missing.items()
            if n not in asked and gatemarks.material_answer(b, n) is None]
    seen, kept = set(), []
    for d in out:
        if d["question"] not in seen:
            seen.add(d["question"])
            kept.append(d)
    return kept


# ---------------------------------------------------------------- 次の run に渡す物
def _outside(returns: dict, next_file: str = "") -> tuple[list, list, str]:
    """判定が目的の外とした所見の (次の依頼の行, 報告の行, 人が決めることの節に置く件数と置き場の 1 行)。指し札の先は outpurpose の
    控えの名のファイル。無い・名違いなら件数の行は ""（名違いは報告の行が言う）"""
    p = _ret(returns, "judge").get("out_of_purpose")
    if not (isinstance(p, str) and p):
        return [], [], ""
    path = pathlib.Path(p)
    if path.name != outpurpose.FILE:
        return [], [f"目的の外の所見のファイル {p} の名が {outpurpose.FILE} でない（読まなかった）"], ""
    return (outpurpose.next_items(path.parent), outpurpose.report_lines(path.parent),
            outpurpose.count_line(path.parent, next_file, report.OUTSIDE_HEADING.removeprefix("## ")))


def _parked(returns: dict) -> list:
    """修正の段が親の木へ戻せなかった組（fix.groups の returned が偽）"""
    return [g for g in _list(as_dict(returns.get("fix")).get("groups")) if isinstance(g, dict) and g.get("returned") is False]


def split_line(returns: dict) -> str:
    """冒頭の 1 行目に添える、修正の段が受けた単位と止めて持ち越した単位の 1 文（元 report.split_line）。当ててから確かめ直しが赤か
    落ちて戻した組（_backed_out）と、戻せず当たったままの組（_unrestored）は名指して足す。止めた組が無くても、合わせ役が直して
    当てた組（_repaired）が在ればそれを名指す 1 文、どちらも無ければ空"""
    groups = [g for g in _list(as_dict(returns.get("fix")).get("groups")) if isinstance(g, dict)]
    parked = _parked(returns)
    repaired = f"{REPAIRED_HEAD}: 組 {'・'.join(str(g.get('group_id')) for g in got)}" if (got := _repaired(returns)) else ""
    if not parked:
        return repaired
    kept = [str(u) for g in groups if g.get("returned") is True for u in _list(g.get("unit_ids"))]
    held_ = [str(u) for g in parked for u in _list(g.get("unit_ids"))]
    marked = [(head, gs) for head, gs in ((BACKED_OUT_HEAD, _backed_out(returns)), (UNRESTORED_GROUP_HEAD, _unrestored(returns))) if gs]
    return (f"修正の段は {len(kept)} 単位（{'・'.join(kept) or 'なし'}）を受け、{len(held_)} 単位"
            f"（{'・'.join(held_)}）を止めて持ち越した（組 {'・'.join(str(g.get('group_id')) for g in parked)}。次の run の依頼に載る）"
            + "".join(f"。{head}: 組 {'・'.join(str(g.get('group_id')) for g in gs)}" for head, gs in marked)
            + (f"。{repaired}" if repaired else ""))


def _repaired(returns: dict) -> list:
    """戻せた組のうち、確かめ直しが赤で戻すか字で当たらなかった後に合わせ役が直して当てた組（fix.groups の欄 clash の outcome が repaired）"""
    return [g for g in _list(as_dict(returns.get("fix")).get("groups"))
            if isinstance(g, dict) and g.get("returned") is True and as_dict(g.get("clash")).get("outcome") == "repaired"]


def _backed_out(returns: dict) -> list:
    """戻せなかった組のうち、当ててから確かめ直しが赤か落ちて戻した組（fix.groups の欄 backed_out が在る物。fixboard.join_rows）"""
    return [g for g in _parked(returns) if _list(g.get("backed_out"))]


def _unrestored(returns: dict) -> list:
    """戻せなかった組のうち、当ててから戻そうとして戻せず親の作業ツリーに当たったままの組（fix.groups の欄 unrestored が在る物）"""
    return [g for g in _parked(returns) if _list(g.get("unrestored"))]


def unrestored_lines(returns: dict) -> list:
    """人が決めることの節の頭の、戻せず当たったままの組ごとの 2 行（組と単位と当たったままのパス・訳）"""
    out = []
    for g in _unrestored(returns):
        units = "・".join(str(u) for u in _list(g.get("unit_ids"))) or "なし"
        out += [f"{UNRESTORED_GROUP_HEAD}: 組 {g.get('group_id')}（単位 {units}）。当たったままのパス {'・'.join(map(str, _list(g.get('unrestored'))))}",
                f"  - 訳: {oneline.one_line(g.get('reason') or '訳の記録が無い')}"]
    return out


def backed_out_lines(returns: dict) -> list:
    """人が決めることの節の頭の、当ててから確かめ直しが赤か落ちて戻した組ごとの 3 行（組と単位と戻したパス・赤の文・合わせの結果）。
    合わせの結果は欄 clash で言い分ける: 合わせ役が直せず申し出を回した組（parked）は申し出の id と控えの差分、clash の無い組
    （確かめ直しが落ちた・合わせのループが走らなかった）は外したまま"""
    kept = [g for g in _list(as_dict(returns.get("fix")).get("groups")) if isinstance(g, dict) and g.get("returned") is True]
    out = []
    for g in _backed_out(returns):
        units = "・".join(str(u) for u in _list(g.get("unit_ids"))) or "なし"
        mark = as_dict(g.get("clash"))
        said = (f"合わせ役が直せず、組どうしの合わせの申し出 {'・'.join(map(str, _list(mark.get('requests'))))} にした（控えの差分 {mark.get('patch')}）"
                if mark.get("outcome") == "parked" else "合わせ役が直していない")
        out += [f"{BACKED_OUT_HEAD}: 組 {g.get('group_id')}（単位 {units}）。戻したパス {'・'.join(map(str, _list(g.get('backed_out'))))}",
                f"  - 赤: {oneline.one_line(g.get('reason') or '訳の記録が無い')}",
                f"  - 合わせの結果: {said}。ほかの組は {len(kept)} 組を当てたまま、外した単位 {units} は次の run の依頼に回した"]
    return out


def _rejudge(returns: dict) -> tuple[str, str]:
    """(再審の答え, 修正役の異議の文)"""
    verdict = as_dict(returns.get("rejudge")).get("rejudge_verdict")
    objection = as_dict(returns.get("fix")).get("objection")
    return (verdict if isinstance(verdict, str) else "", oneline.one_line(objection) if isinstance(objection, str) else "")


def _judgment_units(ret) -> dict:
    """段の返りの judgment の指し札の先（今の works の judgment.json）の units {key: 単位}。指し札が無い・読めなければ空"""
    p = as_dict(ret).get("judgment")
    try:
        doc = oc.read_json(p) if isinstance(p, str) and p else {}
    except (OSError, ValueError):
        return {}
    return {u["key"]: u for u in _list(as_dict(doc).get("units")) if isinstance(u, dict) and isinstance(u.get("key"), str)}


def rejudge_exit(returns: dict) -> tuple:
    """(再審の出口 rejudge-exit.json の中身, 読めなかった訳)。再審の judgment の隣の約束のファイル（判定のブロックが書く。
    lib/report.rejudge_exit）。再審が走っていなければ (None, "")"""
    rejudge = returns.get("rejudge")
    if not isinstance(rejudge, dict):
        return None, ""
    p = rejudge.get("judgment")
    if not (isinstance(p, str) and p):
        return None, "再審の判定のポインタが無いか開けなかった"
    return report.rejudge_exit(pathlib.Path(p).parent)


def _exit_keys(doc, field: str) -> list:
    return [k for k in _list(as_dict(doc).get(field)) if isinstance(k, str) and k]


def rejudge_lowered(returns: dict, exit_doc) -> list:
    """再審が block から他のラベルに下げた単位 [(key, 今のラベル)]（再審の出口 exit_doc（rejudge_exit の中身）の lowered。今のラベルは
    再審の judgment。指示書は禁じるが受け付けは拒まないので、拒まずに見せる）"""
    now = _judgment_units(returns.get("rejudge"))
    return [(k, str(as_dict(now.get(k)).get("label") or "（判定に無い）")) for k in _exit_keys(exit_doc, "lowered")]


def unproven_lines(returns: dict) -> list:
    """例で証明できない判定の問いの行（元 querytest.unproven_lines。今の判定の judgment の units から querytest.unproven で出し
    直す。開いた単位は元の検証器の is_open と同じ式）"""
    rows = querytest.unproven(list(_judgment_units(_ret(returns, "judge")).values()), gatemarks._fix_duty)
    return [f"{querytest.UNPROVEN_HEAD}: {len(rows)} 件", *[f"  - {r['key']}: {r['why']}" for r in rows]] if rows else []


def rejudge_opened(returns: dict, exit_doc) -> list:
    """再審が直す単位にした単位のうち修正の段が受けていない物（再審の出口 exit_doc の new_open_units。この run では直していない）"""
    fixed = {u.get("unit_id") for u in _list(as_dict(returns.get("fix")).get("units")) if isinstance(u, dict)}
    return [k for k in _exit_keys(exit_doc, "new_open_units") if k not in fixed]


def rejudge_changes(returns: dict) -> list:
    """再審で単位が変わった行（元 report._rejudge_changes。再審の judgment の隣の rejudge-diff.json の changed の全部。異議に名指されて
    いない物は「争点でない」と印を付ける）"""
    rows, why = _read_beside(returns, "rejudge", "judgment", report.REJUDGE_DIFF)
    if why:
        return [f"再審の単位の前後の差: {why}"]
    lines = []
    for row in _list(rows):
        for c in _list(as_dict(row).get("changed")):
            if not isinstance(c, dict):
                continue
            who = "異議に名指された単位" if c.get("named") else "争点でない単位"
            if c.get("kind") == "changed":
                lines.append(f"再審（{row.get('pass')}）で{who}が変わった: {c.get('key')} の {c.get('field')}: "
                             f"{json.dumps(c.get('before'), ensure_ascii=False)} → {json.dumps(c.get('after'), ensure_ascii=False)}")
            else:
                lines.append(f"再審（{row.get('pass')}）で{who}が{'足された' if c.get('kind') == 'added' else '消えた'}: {c.get('key')}")
    return lines


def rejudge_lines(returns: dict, exit_: tuple) -> list:
    """決着した再審の結果の行（元 report.rejudge_lines・_settled_rounds。再審の judgment の隣の rejudge-exit.json の往復の数と答えの
    並び・異議の文、再審が直す単位にした単位と block から下げた単位）と、再審されずに残った異議（線の fixed の objection は 1 回目と 2 度目の修正の異議をつないだ文）。出口が
    読めない再審は 1 行で名指す。exit_ は rejudge_exit の返り"""
    verdict, objection = _rejudge(returns)
    left = [f"再審されずに残った異議: {objection}"] if objection and not verdict else []
    if not isinstance(returns.get("rejudge"), dict):
        return left
    doc, why = exit_
    if doc is None:
        return [f"再審の記録が読めない（{why}）——再審の結果を確かめる", *left]
    raw = _list(doc.get("verdicts"))
    obj = oneline.one_line(doc.get("objection") or "") or objection
    opened, lowered = rejudge_opened(returns, doc), rejudge_lowered(returns, doc)
    if not (raw or opened or lowered or obj):
        return left
    verdicts = "・".join(v if isinstance(v, str) and v else "（判定の欄が無い）" for v in raw) or "（判定の往復が無い）"
    return [f"再審の結果（{len(raw)} 往復）: {verdicts}" + (f"（異議: {obj}）" if obj else ""),
            *[f"  - 再審が直す単位にした（この run では直していない——次の run に渡す）: {k}" for k in opened],
            *[f"  - 再審が block から {label} に下げた（拒まずに見せる——人が確かめる）: {k}" for k, label in lowered],
            *left]


def _asked_rows(returns: dict, closed: bool) -> list:
    """人に回した申し出を外した単位ごとの次の依頼の行（元 next_request の conflict.asked の行）と、途中で落ちた run の案の直しを
    待つ行（元 next_request の conflict.waiting の行。案の直しの欄に PENDING_WHY）"""
    out = []
    if not closed:
        for k, r in oc.asked_units(returns, rows=oc.waiting_conflicts(returns)):
            out.append({"where": k, "text": f"{k}（{oc.PENDING_WHY}。裁定の文: {as_dict(r.get(conflict.RULING)).get('text') or ''}。"
                                            f"名指し {', '.join(str(x) for x in _list(r.get('between')))}。{conflict.HELD_WORK_KEPT}）"})
    asked = oc.asked_conflicts(returns, closed)
    for k, r in oc.asked_units(returns, closed, rows=asked):
        ruling = as_dict(r.get(conflict.RULING))
        why = r.get(conflict.REPLAN_WHY)
        out.append({"where": k,
                    "text": f"{k}（{conflict.HEAD}を人に回した——{conflict.place_words(conflict.unit_rows(asked, k))}。"
                            f"裁定の文: {ruling.get('text') or ''}。名指し {', '.join(str(x) for x in _list(r.get('between')))}"
                            + (f"。案の直し: {why}" if why else "") + "）"})
    return out


def next_request(returns: dict, left: list, closed: bool = True, *, beside: dict, exit_doc) -> list:
    """次の依頼の findings（元 report.py:784）: 残りの行（R2 の作り直しの行は前の失敗にだけ載せる。人に回した単位の修正の行は
    その単位の行が持つ）・判定が目的の外とした所見・親の木へ戻せなかった組・再審の結果と再審されずに残った異議・再審が直す単位にした
    単位・手直しが declared で残した穴と 2 回目の手直しが fixed と言った穴（枝の名札つき）・落ちたレンズの「再実行の要あり」
    （fixbeside.next_items）・人に回した申し出の単位・途中で落ちた run（closed が偽）の案の直しを待つ単位。beside は fix_beside の返り、
    exit_doc は再審の出口の中身"""
    asked = _asked_rows(returns, closed)
    owned = {f"修正 {r['where']}" for r in asked}
    items = [r for r in left if not report._r2_redesign(r) and r["where"] not in owned]
    items += _outside(returns)[0]
    items += [{"where": f"{GROUP_WHERE} {g.get('group_id')}",
               "text": f"組 {g.get('group_id')}（単位 {'・'.join(str(u) for u in _list(g.get('unit_ids')))}）を親の木へ戻せなかった——"
                       f"直しを持ち越した: {oneline.one_line(g.get('reason') or '理由の記録が無い')}"} for g in _parked(returns)]
    verdict, objection = _rejudge(returns)
    if verdict:
        items.append({"where": report.REJUDGE_WHERE, "text": f"再審: {verdict}" + (f"（異議: {objection}）" if objection else "")})
    elif objection:
        items.append({"where": REJUDGE_LEFT_WHERE, "text": objection})
    items += [{"where": k, "text": f"{k}（再審が直す単位にした——この run では直していない）"} for k in rejudge_opened(returns, exit_doc)]
    items += [{"where": k, "text": f"{k}（再審が block から {label} に下げた——人が確かめる）"} for k, label in rejudge_lowered(returns, exit_doc)]
    items += fixbeside.next_items(beside)
    items += asked
    seen, out = set(), []
    for it in items:
        k = (it["where"], it["text"])
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out


def _last_reject(returns: dict, rid: str) -> str:
    """止めた段の受け付けの最後の拒否の本文の 1 句（元 accept-last.json の reason_file の本文。段の返りの指し札の先のフォルダの下を
    rolekit.last_reject で探す）。無ければ NO_REJECT"""
    p = as_dict(returns.get(rid)).get(REJECT_PLACES.get(rid, ""))
    last = rolekit.last_reject(pathlib.Path(p).parent) if isinstance(p, str) and p else ""
    return f"受け付けの最後の拒否: {last}" if last else NO_REJECT


def replan_gave_up(returns: dict) -> list:
    """案の直しを終えられなかった項目ごとの前の失敗の行（計画と事前審査の返りの指し札の隣の planblk.REPLAN_GAVE_UP_FILE。
    元 works/.shared/core/replan.py の _give_up が待つ行に書いた諦めの訳と、裁定の文を字のまま）。読めない控えはその訳の行"""
    rows = []
    for rid, field in (("replan", "plan"), ("replan-review", "review")):
        got, why = _read_beside(returns, rid, field, planblk.REPLAN_GAVE_UP_FILE)
        if why:
            rows.append({"where": REPLAN_GAVE_UP_WHERE.format(item="?"), "text": why})
        rows += [{"where": REPLAN_GAVE_UP_WHERE.format(item=r.get("item")),
                  "text": oneline.one_line(f"{r.get('why')}。裁定の文: {r.get('ruling')}")}
                 for r in _list(got) if isinstance(r, dict)]
    return rows


def outcome_facts(start: dict | None, transcript: dict | None, line: dict | None, beside: dict | None = None) -> dict:
    """結末と残りを決める lib/outcome の facts のうち、報告の入力から組む物（1 か所で組み、facts の節の decide_outcome と build の
    residue・前の失敗が同じ物を読む）: 依頼の answers・受け止めた落ち absorbed・メイングラフのノードの止めの語 stops・省いてよい目
    eyes_skip と、修正の diff の隣の控え beside（渡せば。無ければ residue が読む）"""
    line = as_dict(line)
    out = {"answers": _request_answers(start or {}), "absorbed": as_dict(transcript).get("absorbed"),
           "stops": list(as_dict(line.get("stops")).items()), "eyes_skip": eyes_skip(line)}
    return {**out, "beside": beside} if beside is not None else out


def prior_failures(returns: dict, left: list, facts: dict) -> list:
    """前の失敗 [{where, text}]（元 report.py:720）: 受け付けを最後まで通らなかった物（修正の諦めた単位の理由と、計画が修正案を
    出せなかった訳と、止めの語で止めた段の語とその意味。facts の stops のメイングラフのノードの止めも）と R2 の作り直しの訳"""
    rows = [{"where": f"{GAVE_UP_WHERE} {u.get('unit_id')}", "text": oneline.one_line(u.get("reason") or "理由の記録が無い")}
            for u in _list(as_dict(returns.get("fix")).get("units")) if isinstance(u, dict) and u.get("status") == fixboard.GIVEN_UP]
    gave_up = oc.plan_gave_up(returns)
    items = replan_gave_up(returns)
    rows += items
    if gave_up and not items:
        sr = oc.planned(returns).get("stop_reason")
        rows.append({"where": PLAN_GAVE_UP_WHERE,
                     "text": "計画が直す単位を受けたのに修正案を出せなかった（受け付けが 3 回とも拒んだか、行き止まりの単位が在る）"
                             + (f": {sr}" if isinstance(sr, str) and sr else "")})
    rows += [{"where": f"{STOPPED_WHERE} {rid}",
              "text": f"{sr}（{stopby.REASONS.get(sr.removeprefix(stopby.HEAD), '語の意味の記録が無い')}）。{_last_reject(returns, rid)}"}
             for rid, sr in oc.stop_reasons(returns, facts)
             if stopby.is_line(sr) and sr not in oc.WAIT_WORDS and not (gave_up and rid in ("plan", "replan"))]
    r2 = [r for r in left if report._r2_redesign(r)]
    if r2:
        rows.append({"where": carry.REDESIGN_WHERE, "text": oneline.one_line(r2[0]["text"])})
    return rows


# ---------------------------------------------------------------- 語の定義
def pack_terms() -> list:
    """pack の語の定義の一覧（元 report_roles._pack_terms。無ければ空、在って読めなければ ValueError）"""
    if not PACK_TERMS.is_file():
        return []
    try:
        return list(as_dict(oc.read_json(PACK_TERMS)).get("terms") or [])
    except (OSError, ValueError) as e:
        raise ValueError(f"{PACK_TERMS} を読めない: {e}") from None


def glossary_section(text, terms=(), pack=None) -> str:
    """pack の一覧と terms（同じ語は pack を採る）のうち text に現れる語だけを並べた語の定義の節。無ければ空の字
    （元 works/blk-report/lib/report_roles.py の glossary_section。元は pack の一覧を盤面の置き場から読んだ）"""
    seen, rows = set(), []
    for t in list(pack_terms() if pack is None else pack) + list(terms or []):
        term = t.get("term") if isinstance(t, dict) else None
        if not term or term in seen:
            continue
        seen.add(term)
        if term in str(text or ""):
            rows.append(f"- {term}: {t.get('definition')}")
    return f"{report_roles.GLOSSARY_HEADING}\n\n" + "\n".join(rows) + "\n" if rows else ""


# ---------------------------------------------------------------- 機械の報告の節（行は「- 」を付けずに返し、build が付ける）
def _gate_passes(returns: dict) -> list:
    out = []
    for rid in ("plan-review", "replan-review"):
        r = returns.get(rid)
        if rid == "replan-review" and r is None:
            continue
        p = as_dict(r).get("review")
        if not (isinstance(p, str) and p):
            out.append(f"修正前の承認ノードが聞かずに通した行（{rid}）: 無い（{'出力が無い' if r is None else '事前審査のポインタが無い'}）")
            continue
        try:
            rows = gatemarks.passes_of(pathlib.Path(p).parent)
        except (OSError, ValueError) as e:
            out.append(f"修正前の承認ノードが聞かずに通した行（{rid}）: 無い（{pathlib.Path(p).with_name(gatemarks.PASSES_FILE)} が読めない: "
                       f"{oneline.one_line(e)}）")
            continue
        out.append(f"修正前の承認ノードが聞かずに通した行（{rid}）: {len(rows)} 件")
        out += [f"  - {oneline.one_line(x)}" for x in rows]
    at = eye_notes_dir(returns)
    if at is not None:   # E66: 人が通したので R4 の問いから外した行（元 gatemarks.lines の by human の行）
        rows = eyeverdict.gate_pass_rows(at)
        out += ([f"{EYE_PASSES_HEAD}: {len(rows)} 件", *[f"  - {x}" for x in gatemarks.pass_lines(rows)]] if rows is not None
                else [f"{EYE_PASSES_HEAD}: 読めない（{at / eyeverdict.GATE_PASSES}）"])
    return out


def _conflict_line(returns: dict) -> str:
    """申し出の件数と裁定・種類の内訳（元 report._conflict_line）"""
    c, k = oc.conflict_counts(returns)
    plan_n = f"・案の項目を直す（{conflict.REPLAN}）{c[conflict.REPLAN]}" if conflict.REPLAN in c else ""
    swap = f"・問いを置き換える（{conflict.REPLACE}）{c[conflict.REPLACE]}" if conflict.REPLACE in c else ""
    swap += f"・判定をやり直す（{conflict.REJUDGE}）{c[conflict.REJUDGE]}" if conflict.REJUDGE in c else ""
    kinds = [f"{x} {k[x]}" for x in conflict.DIV_KINDS] + ([f"種類なし {k[conflict.UNSET]}"] if conflict.UNSET in k else [])
    return (f"{conflict.HEAD}: {c['parked']} 件（裁定の内訳。括弧は記録の名: テストの直しを許す（fix_test_scope）"
            f"{c['fix_test_scope']}・コードをこう直す（fix_code_as）{c['fix_code_as']}・人に回す（ask_human）{c[conflict.ASK]}"
            f"{swap}{plan_n}・裁定なし {c['unruled']}）。種類の内訳: " + "・".join(kinds))


def _target_uses(repo, rev: str, word: str) -> bool:
    """対象が直す前の版で既にその語を使うか（元 report._target_uses。版か置き場が無い・git が落ちれば偽＝並べる側）"""
    if not (repo and rev):
        return False
    try:
        got = subprocess.run(["git", "-C", str(repo), "grep", "-q", "-F", "-e", word, str(rev), "--"], capture_output=True)
    except OSError:
        return False
    return got.returncode == 0


def inner_word_lines(diff_path, known) -> list:
    """直しの差分が足した行のうち works の内側の語（report.INNER_WORDS）を含む行（元 report.inner_word_lines。対象が直す前の版で
    既に使う語 known(語) は数えない）。差分が無い・当たりが無ければ空。差分が読めなければその行"""
    if not (isinstance(diff_path, str) and diff_path):
        return []
    try:
        text = pathlib.Path(diff_path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return [f"差分 {diff_path} が読めない（{type(e).__name__}）——内側の語を確かめていない"]
    seen, rows = {}, []
    for path, lines in changemap.split_diff(text)[0].items():
        for n, ln in changemap.new_side(lines):
            words = list(dict.fromkeys(report.INNER_WORD.findall(ln))) if ln.startswith("+") else []
            words = [w for w in words if not seen.setdefault(w, known(w))]
            if words:
                rows.append(f"{path}:{n}（{'・'.join(words)}）: {oneline.one_line(ln[1:].strip())}")
    return [f"{report.INNER_WORDS_HEAD}: {len(rows)} 件", *[f"  - {r}" for r in rows]] if rows else []


def verify_lines(returns: dict) -> list:
    """判定の単位の裏取りの申し送り（判定の隣の judge-verify.json）の行（元 report.verify_lines の 1 周分）"""
    doc, why = _read_beside(returns, "judge", "judgment", judgeverify.VERIFY_FILE)
    if why or (doc is not None and not (isinstance(doc, dict) and isinstance(doc.get("units"), list))):
        return [f"判定の単位の裏取り: 申し送りが読めない（{why or '欄 units の配列が無い'}）"]
    if doc is None:
        return []
    units = [u for u in doc["units"] if isinstance(u, dict)]
    notes = []
    for u in units:
        key = u.get("key")
        if u.get("state") != "checked":
            notes.append(f"確かめられなかった: {key}（{oneline.one_line('・'.join(map(str, u.get('errors') or [])))}）")
            continue
        if u.get("verdict") == "not_root":
            notes.append(f"根本でない: {key}（本当の根: {oneline.one_line(u.get('real_root'))}。{oneline.one_line(u.get('why'))}）")
        elif u.get("verdict") == "unsure":
            notes.append(f"根本か決められない: {key}（{oneline.one_line(u.get('why'))}）")
        if u.get("evidence_found") is False:
            notes.append(f"証拠が無い: {key}（{oneline.one_line(u.get('evidence'))}）")
        if u.get("location_ok") is False:
            notes.append(f"場所が違う: {key}（正しい場所: {oneline.one_line(u.get('location'))}）")
    syn = as_dict(doc.get("synergy"))
    if syn.get("state") == "checked":
        notes += [f"重複: {'・'.join(map(str, r.get('units') or []))}（{oneline.one_line(r.get('why'))}）"
                  for r in _list(syn.get("duplicates")) if isinstance(r, dict)]
        notes += [f"順番: {r.get('first')} → {r.get('then')}（{oneline.one_line(r.get('why'))}）"
                  for r in _list(syn.get("order")) if isinstance(r, dict)]
    else:
        notes.append("単位どうしの相乗りは確かめられなかった")
    if not notes:
        return [f"判定の単位の裏取り: {len(units)} 単位とも根本・証拠・場所が合った（重複・順番の名指しなし）"]
    return [f"判定の単位の裏取り（{len(units)} 単位。単位は消していない。減らすなら承認ノードか再審で）:", *[f"  - {x}" for x in notes]]


def pr_lines(returns: dict) -> list:
    """並行 PR と重なるので外した範囲（判定の隣の pr-excluded.json。元 report._pr_lines の外した範囲の側）"""
    doc, why = _read_beside(returns, "judge", "judgment", prcheck.EXCLUDED)
    if why:
        return [f"並行 PR と重なるので外した範囲: {why}"]
    return [f"並行 PR #{x.get('pr')} と重なるので外した範囲: {x.get('file')}:{x.get('start')}-{x.get('end')}（{x.get('why') or ''}）"
            for x in _list(as_dict(doc).get("excluded")) if isinstance(x, dict)]


def premise_lines(returns: dict, start: dict) -> list:
    """依頼が実測（measured）を持っていたのに、前提の役が仮説でしか書けなかった制約（判定の隣の premises.json。元
    report._premise_hypotheses。依頼の行は始めの記録の依頼のファイルから）"""
    doc, why = _read_beside(returns, "judge", "judgment", premises.PREMISES_FILE)
    if why:
        return [f"前提の制約: {why}"]
    hyp = [c for c in _list(as_dict(doc).get("constraints")) if isinstance(c, dict) and c.get("kind") == HYPOTHESIS]
    req = startrec.request_file(start)
    if not (hyp and req):
        return []
    try:
        findings = carry.parts(oc.read_json(req))["findings"]
    except (OSError, ValueError):
        return []
    lines = []
    for f in findings:
        if isinstance(f, dict) and f.get("measured") and f.get("where"):
            c = next((c for c in hyp if str(f["where"]) in str(c.get("text") or "")), None)
            if c is not None:
                lines.append(f"依頼の実測を測り直せなかった（前提は仮説）: {f['where']}——{c.get('text')}")
    return lines


def _hits(returns: dict) -> list:
    """守りのパスの当たり（封じた差分と独立の目の両方。重ねない）"""
    got = [h for rid in ("merge-seal", "eyes") for h in _list(as_dict(returns.get(rid)).get("protected_hits")) if isinstance(h, str)]
    return list(dict.fromkeys(got))


def _counted(head: str, rows: list) -> list:
    """見出しの件数の行と 1 件 1 行（rows が空なら何も出さない）"""
    return [f"{head}: {len(rows)} 件", *[f"  - {oneline.one_line(x)}" for x in rows]] if rows else []


def _line_lines(line: dict) -> list:
    """線の値の行: 無人の run で修正前の関所に載せなかった問い（ask-before-fix の deferred）・最後の関所を開ける理由（ask-final の
    reasons）。聞かずに通した範囲を広げるだけの直し（ask-replan の widened）は案の直しの項目の行（_amend_lines）が持つ"""
    line = as_dict(line)
    return [*_counted(DEFERRED_HEAD, _list(line.get("deferred"))), *_counted(FINAL_REASONS_HEAD, _list(line.get("final_reasons")))]


def _amend_lines(returns: dict, gates: dict, line: dict, closed: bool) -> list:
    """同じ run の中で直した修正案の項目ごとの 1 行（元 report._amend_lines・replan.lines。lib/replan.amend_lines）: 修正の返りの
    replan_items と refixed・案の直しの関所の答え・線の widened・申し出の行の諦めた訳（replan_why。項目の番号は conflict.ruled_items）"""
    fix = as_dict(returns.get("fix"))
    items = [str(i) for i in _list(fix.get("replan_items"))]
    whys = {}
    for r in oc.conflict_rows(returns)[0]:
        why = r.get(conflict.REPLAN_WHY)
        for n in map(str, conflict.ruled_items(r)):
            if isinstance(why, str) and why:
                whys.setdefault(n, why)
    rows = replan.amend_lines(items, refixed=fix.get("refixed") is True, answer=gates.get("gate-replan"),
                              widened=_list(as_dict(line).get("widened")), whys=whys, pending=not closed)
    return _counted(replan.AMEND_HEAD, rows)


def _converge_lines(returns: dict) -> list:
    """事前審査の壁打ちの往復の行（元 report.head_decisions の converge.lines。返り review の隣の gate.json の converge。計画の往復と
    案の直しの事前審査）。控えが無ければ空、読めなければその 1 行"""
    out = []
    for rid in ("plan-review", "replan-review"):
        p = as_dict(returns.get(rid)).get("review")
        if not (isinstance(p, str) and p):
            continue
        if not (pathlib.Path(p).parent / gatemarks.PLAN_GATE_FILE).is_file():
            continue   # 控えが無いことは _gate_passes の行が言う
        try:
            out += gatemarks.converge_of(pathlib.Path(p).parent)
        except (OSError, ValueError) as e:
            out.append(f"事前審査の壁打ちの行（{rid}）: 無い（{pathlib.Path(p).with_name(gatemarks.PLAN_GATE_FILE)} が読めない: "
                       f"{oneline.one_line(e)}）")
    return out


def _plan_questions(returns: dict, gates: dict, start: dict) -> tuple[list, list]:
    """事前審査の問いの文を (人が決める物, 修正前の承認ノードが通す語で答えた台帳の外の物) に分ける。答えた物は問いの台帳が関所の
    continue（gatemarks.gate_items）の asked に在ると読む行で、一言が「保留: <key>」と名指した台帳の問い（held_questions）は答えていない。
    答えた台帳の問いは人が決める物から外すだけで返さない（ledger_state の answered が並べる）"""
    texts = gatemarks.row_texts(_list(_ret(returns, "plan-review").get("questions")))
    b = ledger(returns, gates, start)
    held = [gatemarks._prefix(q) for q in gatemarks.held_questions(b)]
    done = [q for q in texts if gatemarks._continued(b, q) and not any(q.startswith(h) for h in held)]
    owned = [gatemarks._prefix(q) for q in gatemarks._asking(b)]
    return [q for q in texts if q not in done], [q for q in done if not any(q.startswith(h) for h in owned)]


def _decisions(returns: dict, gates: dict, start: dict, outcome: str, left: list, *, closed: bool, beside: dict, exit_: tuple,
               repo=None, line: dict | None = None) -> tuple[list, str]:
    """人が決めることの行と、冒頭の 2 行目（件数）。数える物は元 head3 と head_decisions の人が決める物。round_limit の残りは
    直す義務に戻せなかった単位の行を重ねて数えない。closed は途中で落ちていない run（案の直しを待つ行を人に回した行に数える）"""
    plan_qs, plan_done = _plan_questions(returns, gates, start)
    eye_qs = oc.eye_questions(returns)
    spec_qs = spec_changed_of(line)
    ledger = ledger_state(returns, gates, start)
    held_ = [line for q, line in ledger["held"] if q is None or not any(x.startswith(gatemarks._prefix(q)) for x in plan_qs)]
    done = ledger["answered"] + [oneline.one_line(x) for x in plan_done]
    asked = oc.asked_conflicts(returns, closed)
    tests = [t for t in _list(as_dict(returns.get("fix")).get("allowed_test_changes")) if isinstance(t, str)]
    unreturned = [u for u in _list(as_dict(returns.get("fix")).get("units")) if isinstance(u, dict) and u.get("status") == fixboard.NOT_DONE]
    premise = as_dict(as_dict(returns.get("eyes")).get("premise_check"))
    escalate = [premise] if premise.get("verdict") == "escalate" else []
    checks = left if outcome == "fixed_needs_check" else []
    handoffs = [x for x in _list(as_dict(returns.get("fix")).get("handoffs")) if isinstance(x, str)]
    counted_units = {f"修正 {u.get('unit_id')}" for u in unreturned}
    rest = [r for r in left if r["where"] not in counted_units] if outcome == "round_limit" else []
    spec_head = gatemarks.spec_words(spec_unchecked_of(line)).head
    parts = [(spec_head, spec_qs), ("修正前の問い", plan_qs), ("独立の目 R4 の問い", eye_qs), ("保留にしたままの問い", held_),
             ("人に回した食い違いの申し出", asked), (fixboard.HANDOFF_HEAD, handoffs),
             ("守りのパスに当たった差分", _hits(returns)), ("許したテストの変更", tests),
             ("直す義務に戻せなかった単位", unreturned), ("前提の検算が人に上げた物", escalate), (report.CHECKS_LEFT, checks),
             ("直しきれずに残った物", rest), ("記録が通らないこと", [outcome] if outcome == "record_invalid" else [])]
    lines = []
    for word, items in parts:
        if not items:
            continue
        lines.append(f"{word}: {len(items)} 件")
        for x in items:
            text = x if isinstance(x, str) else (f"{x.get('where')}: {x.get('text')}" if "where" in x else json.dumps(x, ensure_ascii=False))
            lines.append(f"  - {oneline.one_line(text)}")
    if held_:
        lines.append(f"  {gatemarks.ANSWER_HOW}")
    if done:
        lines.append(f"{gatemarks.ANSWERED_HEAD}（{len(done)} 件。保留と人が決めることの件数には数えない）:")
        lines += [f"  - {x}" for x in done]
    lines += ledger["unmatched"]
    lines += ledger["unread_holds"]
    lines += ledger["ties"]
    counted = [(w, len(i)) for w, i in parts if i]
    decide = (f"{sum(n for _, n in counted)} 件——" + "・".join(f"{w} {n} 件" for w, n in counted) + f"（下の「{report.DECISIONS_HEADING.lstrip('# ')}」）"
              if counted else "")
    rev = as_dict(start).get("base_rev")
    lines.append(_conflict_line(returns))
    lines += unproven_lines(returns)
    lines += rejudge_lines(returns, exit_)
    lines += rejudge_changes(returns)
    lines += verify_lines(returns)
    lines += _pr_draft_lines(returns)
    lines += pr_lines(returns)
    lines += premise_lines(returns, start)
    lines += inner_word_lines(as_dict(returns.get("fix")).get("diff"), lambda w: _target_uses(repo, rev, w))
    lines += _design_lines(returns)
    lines.append(f"{RESIDUE_HEAD}: {len(left)} 件（最後のテストが緑でない・独立の目の阻害と結果が無い目・修正の段の残り・直しの後の実測が"
                 "見た住処の外の知る場所の増え・測れていない素材・落ちたがメイングラフが受け止めたノード）" + (f"。{MISSING_EYE_NOTE}" if left else ""))
    lines += fixbeside.always_rows(beside)
    lines += _tests_head_lines(returns)
    lines += [*fixbeside.tests_left_lines(beside), *fixbeside.gates_lines(beside), *fixbeside.plan_ask_lines(beside)]
    lines += _counted(querytest.STUCK_HEAD, fixbeside.closure_lines(beside, stuck_only=True))
    lines += _counted(querytest.CLOSURE_HEAD, fixbeside.closure_lines(beside))
    lines += fixbeside.branch_rows(beside)
    lines += [f"修正の控え: {x}" for x in beside["unread"]]
    return lines + _gate_passes(returns) + _converge_lines(returns) + _amend_lines(returns, gates, line, closed) + _line_lines(line), decide


def _design_lines(returns: dict) -> list:
    """独立設計が問いは立たないと返したのに根拠にパス:行の名指しが無い 1 行（元 report._design_unanchored :1265。事前審査の返りの
    design の先の design.json）"""
    out = []
    for rid in ("plan-review", "replan-review"):
        p = as_dict(returns.get(rid)).get("design")
        try:
            got = oc.read_json(p) if isinstance(p, str) and p else None
        except (OSError, ValueError):
            continue
        if not isinstance(got, dict) or got.get("question_stands") is not False:
            continue
        r = got.get("premise_invalid_reason") or got.get("reason") or ""
        if design.anchor_note(r):
            out.append(f"独立設計は問いが立たないと返したが、{design.UNANCHORED}（{oneline.one_line(r)}）")
    return out


def _tests_head_lines(returns: dict) -> list:
    """最後のテストの一式の行と修正前のテストの行（T35。test-gate の返りの欄から declared_checks.gate_values で。最後の関所の文と同じ字）・任せ先の
    申告の緑の次の手（T41）・封じた差分が消すファイル（M38）"""
    out = []
    ret = _ret(returns, "test-gate-final")
    if ret:
        v = declared_checks.gate_values(ret)
        out += [f"最後のテストの一式: {v['suites']}・ログ {v['log']}", v["baseline"]]
        if v["by"] == declared_checks.ROLE_NEEDED:
            out.append(declared_checks.SELF_REPORTED_NOTE)
    p = as_dict(returns.get("merge-seal")).get("diff")
    if isinstance(p, str) and p:
        try:
            out += seallib.deleted_lines(seallib.deleted_paths(pathlib.Path(p).read_text(encoding="utf-8", errors="replace")), where=p)
        except OSError as e:
            out.append(f"{seallib.DELETED_HEAD}: 封じた差分が読めない（{oneline.one_line(e)}）")
    return out


def _apply_lines(returns: dict, gates: dict, outcome: str, stop_reason: str, run_id: str) -> list:
    """差分を対象に当てる 1 行（M37。bin/apply <run-id>。元 works/dev/lib.sh:633-644）。止まった run には止まりの 1 行（結末の語・止めた
    所・人の一言。無人の run が推しで通した承認ノードの一言は人の一言でないので引かない）と --allow-stopped の要ることを出す。
    生の git apply の行は出さない（止まった run の拒みを素通りさせない）"""
    sealed = as_dict(returns.get("merge-seal"))
    if not (sealed.get("ok") is True and sealed.get("diff")):
        return [f"{APPLY_HEAD}: 無い（差分を封じていない）"]
    if as_dict(returns.get("merge-apply")).get("ok") is True:
        return [f"{APPLY_HEAD}: bin/apply {run_id}（置いた差分の hash を封じた hash と照らしてから当てる）"]
    said = next((g.get("text") for g in (gates.get(k) for k in ("gate-final", *oc.GATES))
                 if isinstance(g, dict) and g.get("text") and not answer.by_push(g)), "") or "一言なし"
    out = []
    if outcome in STOP_OUTCOMES:
        out.append(f"止まった run: {report.OUTCOME_WORDS.get(outcome, outcome)}（{stop_reason or outcome}）で止まった: 「{oneline.one_line(said)}」")
    if as_dict(as_dict(returns.get("eyes")).get("r2")).get("status") == seallib.REDESIGN:
        return [*out, f"{APPLY_HEAD}: しない（R2 が {seallib.REDESIGN} を言った run の差分は bin/apply も当てない）"]
    return [*out, f"{APPLY_HEAD}: bin/apply {run_id} --allow-stopped（差分を置かずに止まった run。止めの訳を確かめてから当てる）"]


def _tdd_stages(typed: dict) -> tuple[list, list]:
    """tdd-unit の成果物を (段の名, 組の段の物) の並びと、注意の行に。include の頭と周（loop）が違う物を別の修正の段に数える"""
    entries = _list(as_dict(as_dict(typed).get("by_type")).get("tdd-unit"))
    keys, stages, notes = [], [], []
    for e in entries:
        key = (e.get("include"), json.dumps(e.get("loop")))
        if key not in keys:
            keys.append(key)
        body = e.get("body")
        if not isinstance(body, list):
            notes.append(f"tdd-unit {e.get('path')} の中身が組ごとの段の物の配列でない（読まなかった）")
            continue
        stages += report.tdd_stage_groups(keys.index(key), body)
    return stages, notes


def _tdd_lines(typed: dict, returns: dict) -> tuple[list, list, list]:
    """(TDD の節の行, 凍結の行, 注意の行)。成果物が無く fix の units が在れば、その行と成果物が無い訳"""
    stages, notes = _tdd_stages(typed)
    if stages:
        return report.tdd_lines(stages), report.freeze_lines(stages), notes
    units = [u for u in _list(as_dict(returns.get("fix")).get("units")) if isinstance(u, dict)]
    if not units:
        return [], [], notes
    lines = ["型つきの成果物 tdd-unit が一覧に無い（修正の段が出していない・子の run の成果物が親の一覧に載らない。docs/design.md の U8）。"
             "修正の出力の単位の行で出す:"]
    lines += [f"  - {u.get('unit_id')}: {u.get('status')}（{oneline.one_line(u.get('reason') or '理由なし')}）" for u in units]
    return lines, [], notes


def _evidence_lines(returns: dict) -> list:
    """試験の関所の段ごとの、走らせた一式の行とログの置き場（元 report.py:1042-1050。返りの欄から declared_checks.gate_values で）と、最後のテストの
    修正前のテストの行（返りの baseline_line。元の報告の冒頭の entry.baseline_line）"""
    out = []
    for rid, label in GATE_RUNS:
        ret = _ret(returns, rid)
        if not ret:
            continue
        head = f"{label}（{rid}）"
        v = declared_checks.gate_values(ret)
        out += [f"{head}の走らせ方: {v['suites']}", f"{head}のログ: {v['log']}"]
        if rid == "test-gate-final":
            out.append(f"{head}の{v['baseline']}")
    return out


def _green_lines(typed: dict, returns: dict) -> list:
    out = []
    for e in _list(as_dict(as_dict(typed).get("by_type")).get("green-cert")):
        b = as_dict(e.get("body"))
        head = e.get("include") or e.get("node")
        cause = b.get("red_cause") or ""
        line = f"{head}（{b.get('mode') or '—'}）: {'緑' if b.get('green') is True else '緑でない'}・ok {b.get('ok')}" + (f"・赤の原因 {cause}" if cause else "")
        if b.get("ok") is True and cause in RED_KEPT:
            line += f"——赤のまま通した（{cause} の赤。直しが起こした赤でないと認証が見た）"
        out.append(line)
    return (out or ["型つきの成果物 green-cert が一覧に無い"]) + _evidence_lines(returns)


NO_EYES = "独立の目のサブグラフの出力が無い（飛ばされた・落ちた）"


def _eye_word(eyes, name: str, eyes_skip=None) -> str:
    """目 1 つの語。出力の在る目は status と理由。出力の無い目は、直した後の深さが標準（eyes_skip が空の字）なら結果が無い目、
    ほかは深さで省いた目。『独立の目』のセクションの目ごとの行と、## 模型 のセクションの結末の行が同じ字を言う（_eye_lines・_outcome_line）"""
    e = as_dict(eyes).get(name)
    if isinstance(e, dict):
        return f"{e.get('status')}（{oneline.one_line(e.get('reason') or '理由なし')}）"
    return oc.MISSING_EYE.removeprefix("の") if eyes_skip == "" else "深さで省いた"


def _eye_lines(returns: dict, typed: dict, eyes_skip=None) -> tuple[list, list]:
    """目ごとの行と注意の行。目 1 つの語は _eye_word"""
    eyes = returns.get("eyes")
    out, notes = [], []
    if eyes is None:
        out.append(NO_EYES)
    at = eye_notes_dir(returns)
    for name in oc.EYE_NAMES:
        e = as_dict(eyes).get(name)
        if eyes is not None:
            out.append(f"{name.upper()}: {_eye_word(eyes, name, eyes_skip)}")
            if name == "r2" and isinstance(e, dict):   # E45: R2 に渡した前提と『渡されていない』と言われた物（元 line_edge._r2_inputs）
                out += [f"  - {x}" for x in (eyeverdict.r2_input_lines(at) if at is not None
                                             else ["独立の設計と比べる目に渡した入力の控えが無い（独立の目の出力 notes が無い）"])]
    premise = as_dict(as_dict(eyes).get("premise_check"))
    if premise:
        out.append(f"前提の検算: {premise.get('verdict') or '語が無い'}（{oneline.one_line(premise.get('reason') or '')}）")
        out += [f"  - {x}" for x in (eyeverdict.premise_fact_lines(at) if at is not None else [])]
    for v in _list(as_dict(as_dict(typed).get("by_type")).get("eye-verdict")):
        b = v.get("body")
        if not (isinstance(b, dict) and set(b) == set(EYE_KEYS)):
            notes.append(f"eye-verdict {v.get('path')} の中身が {{{', '.join(EYE_KEYS)}}} の形でない（読まなかった）")
            continue
        out.append(f"成果物 {b['eye']}（{v.get('include') or v.get('node')}）: {b['status']}（{oneline.one_line(b['reason'])}）")
    return out, notes


def _world_lines(returns: dict) -> list:
    """依頼の行ごとの定石と、定石を web で確かめたかの印と、依頼の解き方との比べと、類の数と落とした抜き書きの数のまとめ（元
    worldmark.report_lines :265-277。数と段が落ちた訳は 1 回目の判定の隣の world-state.json）。判定が返ったのに world が null なら、
    段が落ちた訳（控えが無ければ、段が落ちたか行を取れなかった 1 行）"""
    judge = _ret(returns, "judge")
    state_at = _first_beside(returns, worldmark.STATE_FILE)
    state = worldmark.read(state_at.parent) if state_at is not None else None
    p = judge.get("world")
    if not (isinstance(p, str) and p):
        if state is not None and state.get("status") != "ok":
            return [f"世界の解の段が落ちた（行なしで進んだ）: {oneline.one_line(state.get('reason') or '理由の記録が無い')}"]
        return ["世界の解の行が無い（判定の出力の world が null: 世界の解の段が落ちたか、行を取れなかった。行なしで進んだ）"] if judge else []
    try:
        rows = worldmark.rows(p)
    except ValueError as e:
        return [f"世界の解の行が読めない: {oneline.one_line(e)}"]
    tail = f"類 {state.get('classes', len(rows))}・落とした抜き書き {state.get('dropped', 0)}" if state else f"類 {len(rows)}"
    return [*(f"類 {r['class_id']}（依頼の行 {r['finding']}）: {r['practice']}{worldmark._mark(r)}（{worldmark._versus(r)}）" for r in rows),
            tail]


def _unseen_lens_lines(returns: dict, beside: dict) -> list:
    """未確認のレンズの節（元 report.py:2069-2073: 局所レビューの戻した・見ていないレンズ diverted.report_lines を先に、修正の後の
    レンズ lens.report_lines を後に。1 回目の判定の隣の local-review-lenses.json と、修正の diff の隣の lenses.json）"""
    at = _first_beside(returns, diverted.LENS_FILE)
    return [*(diverted.report_lines(at.parent) if at is not None else []), *fixbeside.lens_lines(beside)] or ["無い"]


def _pr_draft_lines(returns: dict) -> list:
    """並行 PR の担当への申し送りの下書き（1 回目の判定の隣の pr-downgrades.json。prcheck.draft_lines）。読めなければその 1 行"""
    at = _first_beside(returns, prcheck.DRAFTS)
    if at is None or not at.is_file():
        return []
    try:
        return prcheck.draft_lines(_list(oc.read_json(at)))
    except (OSError, ValueError) as e:
        return [f"並行 PR の担当への申し送りの下書き: 読めない（{oneline.one_line(e)}）"]


def _downgrade_lines() -> list:
    """下げている所の数と 1 行ずつ（元 head_entry の declared_downgrades。lib/downgrades.json）"""
    try:
        rows = prcheck.downgrades()
    except ValueError as e:
        return [f"下げている所: 読めない（{oneline.one_line(e)}）"]
    return [prcheck.head_downgrades(rows), *[f"  - {r['node']}: {r['what']}（{r['versus']}）" for r in rows]]


def _structure_lines(returns: dict) -> list:
    """構造の目の行（計画の structure の隣の design.jsonl）と、直した後の構造の実測（eyes の structure_after。元 structmark.report_lines）"""
    sp, ap = _ret(returns, "plan").get("structure"), as_dict(returns.get("eyes")).get("structure_after")
    after_dir = pathlib.Path(ap).parent if isinstance(ap, str) and ap else None
    if isinstance(sp, str) and sp:
        return structmark.report_lines(pathlib.Path(sp).parent, after_dir)
    return structmark.after_lines(after_dir) if after_dir is not None else []


def _cmd_skipped(typed: dict) -> int:
    """TDD の輪が軽量で緑の後の test_cmd を走らせなかった単位（tdd-unit の単位の test_cmd が CMD_LIGHT）の数"""
    import tddloop
    stages, _ = _tdd_stages(typed)
    return len({u.get("unit_key") for _, tdd in stages for u in _list(as_dict(tdd).get("units"))
                if isinstance(u, dict) and u.get("test_cmd") == tddloop.CMD_LIGHT})


def _depth_lines(start: dict, returns: dict, line: dict, typed: dict) -> list:
    """深さの行（元 depth.lines。報告の冒頭 2）: 直した後に上げ直した深さ（線の redepth の返り {depth, raised, counted}）。上げ直しの
    返りが無ければ計画の深さと、上げ直しが無い訳。test_cmd の省きは省いた時点の記録（tdd-unit）から数える"""
    redepth = as_dict(as_dict(line).get("redepth"))
    rows = _list(redepth.get("depth")) if redepth else _list(_ret(returns, "plan").get("depth"))
    if not rows and not redepth:
        return []
    doc = {"units": {str(d.get("unit_id")): {"depth": d.get("depth"), "why": [str(d["why"])] if d.get("why") else []}
                     for d in rows if isinstance(d, dict)},
           "forced": as_dict(start).get("thickness") or "", "raised": _list(redepth.get("raised")),
           "counted": redepth.get("counted") or ""}
    return [*depthlib.lines(doc, as_dict(returns.get("judge")).get("depth"), cmd_skipped=_cmd_skipped(typed)),
            *([] if redepth else [NO_REDEPTH])]


def _head_depth_line(start: dict, returns: dict) -> list:
    judged = returns.get("judge")
    if not isinstance(judged, dict) or not judged.get("depth"):
        return []
    return [headdepth.report_line(judged["depth"], judged.get("depth_why") or "", as_dict(start).get(entrylib.FEATURES_KEY) or [])]


def _prior_in_lines(line: dict) -> list:
    """依頼が運んだ前の run の失敗の行（始めの節が置いた prior-failures-in.json。指し札が無ければ何も出さない）"""
    p = as_dict(line).get("prior_failures")
    if not (isinstance(p, str) and p):
        return []
    try:
        rows = oc.read_json(p)
    except (OSError, ValueError) as e:
        return [f"{PRIOR_IN_HEAD}: 読めない（{oneline.one_line(e)}）"]
    rows = [r for r in _list(rows) if isinstance(r, dict)]
    return [f"{PRIOR_IN_HEAD}: {len(rows)} 件", *[f"  - {r.get('where')}: {oneline.one_line(r.get('text'))}" for r in rows]]


def _policy_lines(returns: dict, repo) -> list:
    """方針の文書が事前審査の固めた版（返り review の隣の policy.json。案の直しの事前審査が在ればそちら）から変わったまま終わった
    run の 1 行（R75。boardview.policy_change。差分と写しの置き場を名指す）"""
    import boardview   # 事前審査の部品（報告の頭で読むと重い）
    for rid in ("replan-review", "plan-review"):
        p = as_dict(returns.get(rid)).get("review")
        if isinstance(p, str) and p and repo is not None:
            try:
                ch = boardview.policy_change(pathlib.Path(p).parent, repo)
            except (OSError, ValueError) as e:
                return [f"{POLICY_CHANGED_HEAD}か: 確かめられない（{oneline.one_line(e)}）"]
            return [f"{POLICY_CHANGED_HEAD}: {boardview.change_row(ch)}"] if ch else []
    return []


def _entry_lines(start: dict, returns: dict, tdd_freeze: list, line: dict | None = None, gates: dict | None = None,
                 repo=None, typed: dict | None = None) -> list:
    s = as_dict(start)
    out = [f"始めの記録: run {s.get('run_id') or '—'}・元の版 {s.get('base_rev') or '—'}・テストの命令 {s.get('test_cmd') or '—'}・"
           f"TDD の実行ファイル {s.get('tdd_suite') or '—'}・無人 {s.get(gatepolicy.UNATTENDED_KEY) or '—'}", *fixture.lines(s)]
    shape = startrec.shape(s)
    if shape is not None:
        try:
            out.append(f"入口: {startrec.words(shape)}")
        except (KeyError, TypeError):
            out.append("入口: 入口の入力の形が読めない")
    gate_words = gatepolicy.head_words(s)
    if gate_words:
        out.append(gate_words)
    adds = depthlib.tier_adds(as_dict(returns.get("judge")).get("depth"))
    feats = (f"・{entrylib.features_part(s.get(entrylib.FEATURES_KEY) or [], entrylib.features_on_of(s), adds)}"
             if entrylib.FEATURES_KEY in s else "")
    out.append(f"段: {s.get('thickness') or '自動（機械が単位ごとに決めた）'}{feats}")
    answered = [g for g in as_dict(gates).values() if isinstance(g, dict)]
    pushed = sum(1 for g in answered if answer.by_push(g))
    out.append(f"決めた人: 承認ノードの答え {len(answered) - pushed} 件" + (f"（ほかに無人の run が推しで通した承認ノード {pushed} 件）"
                                                                          if pushed else ""))
    why = forge.reason(forge.detect(repo)) if repo else ""
    if why:
        out.append(f"{FORGE_HEAD}: 無い——並行 PR の確かめは条件外（not_applicable。{why}）")
    ran = [k for k, v in returns.items() if v is not None]
    skipped = [k for k, v in returns.items() if v is None]
    out.append(f"走った段: {'・'.join(ran) or '無い'}")
    out.append(f"飛ばされた・出力の無い段: {'・'.join(skipped) or '無い'}")
    out += _downgrade_lines()
    out += _head_depth_line(start, returns)
    out += _depth_lines(start, returns, line, as_dict(typed))
    out += _prior_in_lines(line)
    out += _policy_lines(returns, repo)
    base = returns.get("test-gate-base")
    if isinstance(base, dict):
        out.append(f"直す前のテスト: {_base_word(base)}")
    return out + list(tdd_freeze)


def _base_word(base: dict) -> str:
    """直す前のテストの語。red_cause が incomplete で認証されなかった（ok 偽）base は、素材が測った結果でないか、素材が無いか、
    返す節の中の誤り（workflows/test-gate/scripts/result.py）なので「走らせられなかった」。認証された incomplete の base は、
    素材が not_applicable か awaiting_human（green_cert.certify が認証し classify が incomplete に畳む）なら元の結末のファイルの
    素材の語で言い、awaiting_human は走らせられなかった系統を名指す素材の reason を添える"""
    if base.get("green"):
        return "緑"
    if base.get("red_cause") == green_cert.INCOMPLETE:
        if base.get("ok") is not True:
            return f"走らせられなかった（{green_cert.INCOMPLETE}）——{gatemarks.BASELINE_NOT_RUN}"
        material = _base_material(base)
        status = material.get("status")
        if status in (green_cert.NOT_APPLICABLE, green_cert.AWAITING_HUMAN):
            why = oneline.one_line(material.get("reason") or "") if status == green_cert.AWAITING_HUMAN else ""
            return f"{gatemarks.MATERIAL_WORDS[status]}（{status}）" + (f"——{why}" if why else "")
    return "赤" + (f"（赤の原因 {base.get('red_cause')}）" if base.get("red_cause") else "")


def _base_material(base: dict) -> dict:
    """base の返りの baseline の指し札の先（元の結末のファイル）の素材。読めなければ空"""
    pointed = oc.paths(base.get("baseline"))
    try:
        material = baseline_red.read_baseline(pointed[0]).get("material") if pointed else None
    except ValueError:
        return {}
    return as_dict(material)


def _stop_words(line: dict | None) -> list:
    """メイングラフのノードの止めの 1 件ずつ: 「{ノード} が {止めの語}（{語の意味}）」"""
    return [f"{node} が {word}（{stopby.REASONS.get(str(word).removeprefix(stopby.HEAD), '語の意味の記録が無い')}）"
            for node, word in as_dict(as_dict(line).get("stops")).items()]


def _stopped_why(returns: dict, line: dict | None) -> list:
    """止まった run の冒頭 1 行目に足す訳: 止めの語・最後の承認ノードを開ける理由・阻害を返した目（どれも本文の節と同じ字）"""
    reasons = [str(x) for x in _list(as_dict(line).get("final_reasons"))]
    eyes = as_dict(returns.get("eyes"))
    blocked = [f"{gatemarks.eye_named(name.upper(), e.get('status'))}——{oneline.one_line(e.get('reason') or '理由なし')}"
               for name in oc.EYE_NAMES if isinstance(e := eyes.get(name), dict) and e.get("status") in oc.EYE_STATUS_LEFT]
    return [*_stop_words(line), *(["開けた理由: " + "・".join(reasons)] if reasons else []), *blocked]


def _pushed(gates: dict) -> list:
    """無人の run が推しで通した承認ノードと採った推し [(承認ノード, 推し {item, answer, note, why})]（承認ノードの順）"""
    return [(gid, rec) for gid in oc.GATES for rec in (as_dict(gates.get(gid)).get(answer.PUSHED) or []) if isinstance(rec, dict)]


def _pushed_lines(gates: dict, taken=()) -> list:
    """「人が決めること」の頭に、無人の run が採った推しを 1 件 1 行: 承認ノードの推しと、判定の推しを答えに採った台帳の問い
    （taken は gatemarks.taken_pushes。人の答えと読み分ける。違えば次の run の依頼で直す）"""
    return [*(f"無人の run で推しを採って通した（承認ノード {gid}）: {oneline.one_line(r.get('item') or '')}——"
              f"{gatemarks.RECOMMEND_WORDS.get(r.get('answer'), '')}（{r.get('answer')}）: {r.get('note')}（推す理由: {r.get('why')}）。"
              "違えば次の run の依頼で直す" for gid, r in _pushed(gates)),
            *(f"無人の run で推しを採って答えた（{gatemarks.ASK_HEAD} {q.get('key')}）: 推し: {oneline.one_line(push)}——出どころ・depends の"
              f"単位 {'・'.join(keep) or '（今の周の単位に無い）'} を直す義務に戻した。違えば次の run の依頼の answers で直す"
              for q, push, keep in taken)]


def _pushed_said(gates: dict, taken=()) -> str:
    """冒頭 1 行目の句: 推しで通した承認ノードと件数、推しを答えに採った台帳の問い（taken は gatemarks.taken_pushes）と件数（無ければ空）"""
    got = _pushed(gates)
    where = f"中身は「{report.DECISIONS_HEADING.lstrip('# ')}」のセクション"
    said = [f"無人の run で推しを採って通した承認ノード: {'・'.join(dict.fromkeys(gid for gid, _ in got))}（推し {len(got)} 件。{where}）"
            ] if got else []
    if taken:
        said.append(f"無人の run で推しを採って答えた台帳の問い: {'・'.join(str(q.get('key')) for q, _, _ in taken)}"
                    f"（推し {len(taken)} 件。{where}）")
    return "。".join(said)


def _gate_line(g) -> str:
    if not isinstance(g, dict):
        return "開かなかった"
    said = oneline.one_line(g.get("text") or "")
    return f"{g.get('decision')}（推しで通した: {said}）" if answer.by_push(g) else f"{g.get('decision')}（{said}）"


def _stop_lines(outcome: str, stop_reason: str, gates: dict, tfacts: dict, returns: dict, problems: list,
                line: dict | None = None) -> list:
    out = [f"結末: {report.OUTCOME_WORDS.get(outcome, '結末が決まらない')}（{outcome}）", f"止めた段と理由の語: {stop_reason or '止めていない'}"]
    out += [f"メイングラフのノードの止め: {x}" for x in _stop_words(line)]
    for gid in oc.GATES:
        out.append(f"承認ノード {gid}: {_gate_line(gates.get(gid))}")
    for rid in ("merge-seal", "merge-apply"):
        m = returns.get(rid)
        if isinstance(m, dict) and m.get("ok") is not True:
            out.append(f"{rid} が ok でない: {oneline.one_line(m.get('reason') or '訳の記録が無い')}")
    if tfacts.get("ok"):
        out += [f"{report.INTERRUPTED_HEAD}: ノード {s} が落ちた（誤り: {report._first_error({'error': (tfacts.get('errors') or {}).get(s)})}）"
                for s in tfacts.get("failed") or []]
        out += [f"{report.RETRIED_HEAD}: {r['node']}（落ちた回 {r['failures']}。最後の誤り: {r['error'] or '（誤りの文が無い）'}）"
                for r in tfacts.get("retried") or []]
        out += [f"{report.ABSORBED_HEAD}: {a['node']}（誤り: {report._first_error(a)}）" for a in tfacts.get("absorbed") or []]
    out += [f"出力の続きが切れている: {x}" for x in oc.chain_notes(returns)]
    out += [f"結果を名乗れない訳: {oneline.one_line(p)}" for p in problems]
    return out


def _where_lines(returns: dict) -> list:
    out = []
    for rid, field, label in POINTERS:
        for p in oc.paths(_ret(returns, rid).get(field)):
            out.append(f"{label}（{rid}.{field}）: {p}")
    return out or ["出力にポインタが無い"]


def _bullets(lines: list) -> list:
    """節の行に「- 」を付ける（字下げした内訳の行はそのまま。元 build の行の組み方）"""
    return [r if r.startswith("  ") else f"- {r}" for r in lines]


CALLS_HEAD = "役が自分で呼んだ道具（run の記録の provider_event。ノードごと）:"
HOOK_HEAD = "渡した物を読んだか（フック bin/_lib/record-read.py の記録。下請けの中の Read も数える）:"
CHILD_RUNS = "fix の組の子の run の道具の呼びは子の run の記録に在り、上のノードごとの行に入らない"
CHILD_LOOPS = "fix の組の子の run のループの回り直しは子の run の記録に在り、この行に入らない"
SHOWN_FILES = 3   # 1 ノードの行に名を出すファイルの数


def _reads_lines(tfacts: dict, artifacts: pathlib.Path, out_dir: pathlib.Path, transcript_why: str, repo) -> list:
    """「4. 読んだ証拠と包み」の行: run の記録の道具の呼び（tfacts の calls）と、読んだ証拠の節が run の置き場 artifacts に書いた
    reads-*.json（報告自身の置き場 out_dir と、置き場を丸ごと写した固定材料の物を外す。索引は訳 why だけを出す）と、どちらでも取れない物"""
    calls = as_dict(tfacts.get("calls"))
    out = [CALLS_HEAD]
    if not tfacts.get("ok"):
        out.append(f"  - run の記録が読めない（{transcript_why or '訳の記録が無い'}）")
    elif not calls:
        out.append("  - 道具を呼んだノードが run の記録に無い")
    for step, mine in calls.items():
        files = list(dict.fromkeys(p for tool in PATH_TOOLS for p in mine[tool]))
        shown = "・".join(_shown(p, repo) for p in files[:SHOWN_FILES]) + (f" ほか {len(files) - SHOWN_FILES} 件" if len(files) > SHOWN_FILES else "")
        out.append(f"  - {step}: " + "・".join(f"{tool} {len(mine[tool])} 件" for tool in PATH_TOOLS) + (f"（ファイル: {shown}）" if files else ""))
    out.append(HOOK_HEAD)
    skipped = (out_dir, artifacts / fixture.DIR)
    found = sorted(p for p in artifacts.rglob(reads.EVIDENCE_GLOB) if not any(d in p.parents for d in skipped))
    out += [f"  - {x}" for p in found
            for x in (_index_lines(p, p.relative_to(artifacts).as_posix()) if reads.is_index(p.name)
                      else [_evidence_line(p, p.relative_to(artifacts).as_posix(), repo)])] \
        or ["  - 読んだ証拠のノードが記録を書いていない（役を起こしていないか、ノードが走っていない）"]
    shell = {step: mine[SHELL_TOOL] for step, mine in calls.items() if mine[SHELL_TOOL]}
    counted = (f"。Bash の呼び {sum(shell.values())} 回" + (": " + "・".join(f"{s} {n}" for s, n in shell.items()) if shell else "")
               if tfacts.get("ok") else "。Bash の呼びは run の記録が読めないので数えられない")
    return [*out, UNSEEN + counted, CHILD_RUNS]


def _index_lines(path: pathlib.Path, rel: str) -> list:
    """索引が名指す訳（役を起こしていない段など）。役ごとの行は役ごとの証拠のファイルが出すので、ここは訳だけ"""
    why = reads.index_why(path)
    return [f"{rel}: {oneline.one_line(why)}"] if why else []


def _evidence_line(path: pathlib.Path, rel: str, repo) -> str:
    doc, why = reads.read_evidence(path)
    if doc is None:
        return f"{rel}: 読めない（{why}）"
    if doc["sources"].get("hook") == reads.FAILED:
        return f"{doc['role']}（{rel}）: 読んだ証拠のノードが落ちた（{doc['sources'].get('why') or '訳の記録が無い'}）"
    if doc["sources"].get("hook") != reads.RECORDED:
        return f"{doc['role']}（{rel}）: 測れない（{doc['sources'].get('why') or '訳の記録が無い'}）"
    missing = [str(m) for m in doc["missing"]]
    return (f"{doc['role']}（{rel}）: 渡した {len(doc['rows'])}・読んだ跡の無い {len(missing)}"
            + (f"（{'・'.join(_shown(m, repo) for m in missing)}）" if missing else ""))


def _shown(path: str, repo) -> str:
    """repo の中のパスは repo からの相対、ほかは字のまま"""
    if repo:
        try:
            return pathlib.Path(path).relative_to(pathlib.Path(repo)).as_posix()
        except ValueError:
            pass
    return path


def build(returns: dict, gates: dict, typed: dict, transcript: dict, outcome: str, stop_reason: str, *, out_dir,
          start: dict | None = None, problems=(), run_id: str = "", transcript_why: str = "", repo=None,
          report_name: str = report.REPORT_FILE, line: dict | None = None, user_env: bool = False) -> dict:
    """機械の報告（report_name）・次の依頼（next-request.json。空なら書かない）・前の失敗（prior-failures.json。空なら書かない）を
    out_dir に書き、{report, next_request, prior_failures, ai_go} のパスを返す（元 report.py:2000。元は盤面を読み、
    検証器の関所を踏んだ）。書き手に渡す事実のファイルは機械の報告そのもの（元の facts_text が線 A の機械の報告を字のまま使った形）。
    transcript は transcript_facts の返り、typed は型つきの成果物の読み {by_type, warnings}、repo は直しの内側の語を直す前の版と
    比べる対象の置き場（無ければ比べずに全部並べる）、line は線の値 {stops, deferred, widened, final_reasons, spec_changed,
    spec_unchecked, prior_failures（開けたファイルのパスの字か None）, redepth}（線の collect が report の入力で渡す物。無ければ空）、user_env は対象のコマンドを利用者の
    HOME・XDG に戻して起こした run か（userenv.ran。真なら冒頭の 1 行目が userenv.NOTE を言う）"""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    returns, gates, typed, start = returns or {}, gates or {}, typed or {}, start or {}
    tfacts = transcript or transcript_facts(None)
    closed = not oc.cut_at(returns, tfacts.get("failed"))
    skip, beside, exit_ = eyes_skip(line), fix_beside(returns), rejudge_exit(returns)
    facts = outcome_facts(start, tfacts, line, beside)
    left = oc.residue(returns, facts)
    findings = next_request(returns, left, closed, beside=beside, exit_doc=exit_[0])
    prior = prior_failures(returns, left, facts)
    drafts = answer_drafts(returns, gates, start, spec_changed_of(line), spec_unchecked_of(line))
    notes_at = eye_notes_dir(returns)   # E37: 前提の検算が偽と示した仮定の実測を次の run の制約に運ぶ
    constraints = carry.carried_constraints(eyeverdict.premise_facts(notes_at)["facts"] if notes_at is not None else [], run_id)
    decisions, decide = _decisions(returns, gates, start, outcome, left, closed=closed, beside=beside, exit_=exit_,
                                  repo=repo, line=line)
    tdd, freeze, tdd_notes = _tdd_lines(typed, returns)
    eye_lines, eye_notes = _eye_lines(returns, typed, skip)
    _, material_note = oc.materials(returns)
    notes = [*_list(typed.get("warnings")), *tdd_notes, *eye_notes, *([material_note] if material_note else [])]
    next_file = carry.NEXT_REQUEST_FILE if findings or drafts or constraints else ""
    draft = gatemarks.draft_line(drafts, next_file)
    _, outside, outside_count = _outside(returns, next_file)
    taken = gatemarks.taken_pushes(ledger(returns, gates, start))
    split, pushed = split_line(returns), _pushed_said(gates, taken)
    apply = _apply_lines(returns, gates, outcome, stop_reason, run_id or "—")
    stopped = outcome in STOP_OUTCOMES
    happened = "。".join([f"{report.OUTCOME_WORDS.get(outcome, '結末が決まらない')}（{outcome}）", *([split] if split else []),
                          *([pushed] if pushed else []),
                          *(_stopped_why(returns, line) if stopped else []), *_ran_notes(returns),
                          *([userenv.NOTE] if user_env else [])])
    if stopped:
        decide = "。".join(x for x in (decide, apply[-1]) if x)
    asked_texts = [*spec_changed_of(line), *_plan_questions(returns, gates, start)[0],
                   *oc.eye_questions(returns)]
    carried = len(findings) + len(drafts) + len(constraints)
    head_at = _first_beside(returns, headdepth.RECORD)
    head_doc = headdepth.read(head_at.parent) if head_at is not None else None
    head = gatemarks.head3(happened, decide, gatemarks.pushes(asked_texts), other=f"次の run に渡す物: {carried} 件")
    sections = [
        (report.DECISIONS_HEADING, [*_pushed_lines(gates, taken), *unrestored_lines(returns), *backed_out_lines(returns), *decisions,
                                    f"次の run に渡す物: {carried} 件" + (f"（{next_file}）" if next_file else ""),
                                    *([outside_count] if outside_count else []),
                                    *[f"次の run の制約に足す実測（前提の検算）: {c['text']}" for c in constraints],
                                    *([draft] if draft else []), *apply]),
        (report.ENTRY_HEADING, _entry_lines(start, returns, freeze, line, gates, repo, typed)),
        (report.STOP_HEADING, _stop_lines(outcome, stop_reason, gates, tfacts, returns, list(problems), line)),
        (report.READS_HEADING, _reads_lines(tfacts, out_dir.parent, out_dir, transcript_why, repo)),
        (report.WHERE_HEADING, _where_lines(returns)),
        (report.TDD_HEADING, tdd or ["修正の段が走っていない（TDD の単位の行が無い）"]),
        (GREEN_HEADING, _green_lines(typed, returns)),
        (EYES_HEADING, eye_lines),
        (report.STRUCTURE_HEADING, _structure_lines(returns)),
        (report.WORLD_HEADING, _world_lines(returns)),
        (report.UNSEEN_LENS_HEADING, _unseen_lens_lines(returns, beside)),
        (report.OUTSIDE_HEADING, outside),
        (report.PRIOR_HEADING, report.prior_lines(prior, next_file)),
        (report.MODEL_HEADING, _model_lines(tfacts, head_doc, _outcome_line(outcome, gates, returns, carried, prior, skip))),
        (report.COST_HEADING, head_cost(tfacts, transcript_why)),
        (NOTES_HEADING, [oneline.one_line(n) for n in notes] or ["無い"]),
    ]
    text = "\n\n".join([report.TITLE_HEADING.format(run=run_id or "—") + "\n\n" + "\n".join(head),
                        *(f"{h}\n\n" + "\n".join(_bullets(lines)) for h, lines in sections if lines)]) + "\n"
    paths = {"report": _write_text(out_dir / report_name, text), "next_request": None, "prior_failures": None}
    doc = carry.compose(findings, prior, drafts, constraints)
    if next_file:
        errs = carry.errors(doc, carry.NEXT_SCHEMA)
        if errs:
            raise ValueError(f"次の依頼が約束の Schema に合わない: {errs}")
    if prior:   # 2 つとも照らしてから書く（片方だけ合わない時に、もう片方を残さない）
        errs = carry.errors(prior, carry.PRIOR_SCHEMA)
        if errs:
            raise ValueError(f"前の失敗が約束の Schema に合わない: {errs}")
    if next_file:
        paths["next_request"] = out_dir / next_file
        carry.write(paths["next_request"], doc)
    if prior:
        paths["prior_failures"] = out_dir / carry.PRIOR_FAILURES_FILE
        carry.write(paths["prior_failures"], prior)
    return {**paths, "ai_go": outcome != "record_invalid"}


def _ran_notes(returns: dict) -> list:
    """最後のテストが走っていない・走ったと確かめられていない時の冒頭の句（green_cert.ran_note。#492）。最後のテストまで来なかった
    run は結末がそう言い、直す前のテストは本文の行が言う"""
    fin = _ret(returns, "test-gate-final")
    note = (green_cert.ran_note(green=fin.get("green") is True, red_cause=fin.get("red_cause") or "", by=fin.get("by") or "",
                                steps=fin.get("ran_steps")) if fin else "")
    return [note] if note else []


def fallback_report(out_dir, why: str, name: str, *, user_env: bool) -> pathlib.Path:
    """思わぬ誤りの時の機械の報告（結末 record_invalid と訳の 1 行）を name に書く（呼び手は facts の report.md と別の名を渡す）。
    user_env は build と同じ（落ちた run でも、利用者の HOME・XDG で走らせたことは冒頭が言う）。
    組めなければ誤りが上がり、呼び手が lib/ に頼らない訳だけのファイルに落ちる"""
    return build({}, {}, {}, None, "record_invalid", f"report:{why}", out_dir=out_dir, problems=[why], report_name=name,
                 user_env=user_env)["report"]


# ---------------------------------------------------------------- 書き手の返答の受け付けと AI の報告
def _parse(raw) -> tuple[dict | None, str]:
    if isinstance(raw, dict):
        return raw, ""
    try:
        got = json.loads(raw) if isinstance(raw, str) and raw.strip() else None
    except ValueError as e:
        return None, f"返答が JSON でない: {oneline.one_line(e)}"
    return (got, "") if isinstance(got, dict) else (None, "返答が JSON のオブジェクトでない")


def _cold_of(cold) -> dict:
    got, _ = _parse(cold)
    got = got or {}
    verdict = got.get("verdict") if got.get("verdict") in COLD_SCHEMA["properties"]["verdict"]["enum"] else ""
    return {"verdict": verdict, "stops": [str(s) for s in _list(got.get("stops"))],
            "guessed": [str(g) for g in _list(got.get("guessed"))], "decidable": got.get("decidable") is True}


COLD_UNREADABLE = "初見の読み手の返答を読めない（判定の語が無い）"
COLD_EMPTY = "（止まった所・推測の欄が空）"


def _cold_lines(c: dict) -> list[str]:
    """初見の読み手が通さなかった所（止まった所・推測で埋めた所）。判定を読めなければその事実の 1 つ"""
    if not c["verdict"]:
        return [COLD_UNREADABLE]
    return [f"止まった所: {s}" for s in c["stops"]] + [f"推測で埋めた所: {g}" for g in c["guessed"]]


def _cold_facts(c: dict) -> str:
    """通らなかった所の 1 行（AI_FILE の not_passed。報告の拒みの数の行の尾に出す）"""
    return oneline.one_line("；".join(_cold_lines(c)) or COLD_EMPTY)


def _cold_reason(c: dict) -> str:
    """書き手に返す拒みの文"""
    if not c["verdict"]:
        return COLD_UNREADABLE
    return ("初見の読み手（道具なし・報告の頭だけを読む）が redesign-needed を返した。次の所を、頭だけで意味が取れるように"
            "直した本文を丸ごと出し直せ:\n" + "\n".join(f"- {x}" for x in _cold_lines(c) or [COLD_EMPTY]))


def cold_body(raw) -> str:
    """初見の読み手に貼る本文: 書き手の返答の頭（report_roles.head_of）と、その後ろに付く語の定義の節（元 report_roles の
    write_cold_prep の本文。頭は見出しの付いた節を落とすので、書き手が本文に書いた定義は届かない）。読めなければ読めない事実"""
    got, why = _parse(raw)
    text = got.get("text") if got else None
    if not (isinstance(text, str) and text.strip()):
        return f"（書き手の返答を読めない: {why or '本文が無い'}）"
    terms = _list(got.get("terms")) if not report_roles._terms_problems(got) else []
    head = report_roles.head_of(text)
    sec = glossary_section(head, terms)
    return f"{head.rstrip()}\n\n{sec}" if sec else head


def _machine_head_notes(out_dir: pathlib.Path) -> list:
    """機械の報告（out_dir の report.REPORT_FILE）の冒頭に在る、HEAD_NOTES の句。green_cert.PARTLY_RAN は段を名指す括弧まで
    （名を落とした頭を通さない）。読めなければ求めない（事実の節に別の落ち方が在る）"""
    try:
        text = (out_dir / report.REPORT_FILE).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    head = text.split("\n## ", 1)[0]
    return [_named_note(head, note) for note in HEAD_NOTES if note in head]


def _named_note(head: str, note: str) -> str:
    if note != green_cert.PARTLY_RAN:
        return note
    start = head.index(note)
    end = head.find("）", start)
    return head[start:end + 1] if end >= 0 else note


def _refused(reason: str, kind: str) -> dict:
    return {"ok": False, "reason": reason, "kind": kind}


def _reject_count(out_dir: pathlib.Path) -> dict:
    """拒否の控え（rolekit の rejects-report.json）の種類ごとの回数。控えが読めなければ空の控えとして数える"""
    try:
        rows = rolekit.reject_rows(out_dir, REPORT_NODE)
    except (rolekit.BoardGap, OSError):
        rows = []
    return report_roles.count_rejects([{**r, "node": REPORT_NODE} for r in rows])


def _keep_rejected(out_dir: pathlib.Path, reply: dict, refused: dict) -> dict:
    text = reply.get("text")
    if not isinstance(text, str) or not text.strip():
        return refused
    path = out_dir / PREV_ANSWER_FILE
    stuck = None
    try:
        old = fixboard.read_json(path, {"handoffs": []})   # 無い時の既定を None にしない（中身が null の控えを『在るのに使えない』に入れる）
        if not isinstance(old, dict):
            stuck = "が JSON のオブジェクトでない"
        elif not isinstance(old.get("handoffs"), list):
            stuck = "の handoffs が並びでない"
        else:
            handoffs = old["handoffs"] + ([reply["handoff"]] if isinstance(reply.get("handoff"), dict) else [])
            carry.write(path, {"text": text, "terms": _list(reply.get("terms")), "handoffs": handoffs})
    except ValueError as e:
        stuck = f"が読めない（{type(e).__name__}）"
    except OSError as e:
        stuck = f"に書けない（{type(e).__name__}）"
    if stuck is None:
        return refused
    return {**refused, "give_up": True,
            "reason": f"{refused['reason']}\n前の答えの控え {path} {stuck}ので、前の周の引き継ぎのメモを次の周へ渡せない"}


def accept(reply, cold, *, out_dir) -> dict:
    """書き手の返答を受け付ける（元 report_roles.accept を、盤面の代わりに out_dir の控えで書き直した物）。{done, ok, reason, kind,
    reason_file, prev_file}。拒んだ回の返答の本文 text・terms と、返答の handoff（読んだ所・決めた訳・退けた案・迷い）を周の順に積んだ
    並び handoffs は、前の答えの控え PREV_ANSWER_FILE に書き、まだ諦めていない拒否の回の prev_file がそのパスを指す（受け取った回・
    諦めた回・控えの無い回は空の字）。handoff は AI_FILE にも初見の読み手に貼る本文（cold_body）にも載らない。控えが読めない・書けない
    時は上書きせず、take の拒否に give_up を付けて口に止めさせる。受け付けの回は rolekit.accept_round（out_dir、節 REPORT_NODE）が持つ。順: 読む（読めない返答・本文の無い返答は kind answer）
    → terms の型 → 表のセルの書式 → 機械の報告の冒頭の HEAD_NOTES の句が頭に在るか → 初見の読み手の判定。通らなければ口が拒否の行
    （kind つき）を rolekit の控え rejects-report.json に積み、reason_file は拒否の全部の rejects-report.md（rolekit.reject_file）。
    拒否が rolekit.GIVE_UP_AFTER 回に達した時か、控え rejects-report.json が読めない・書けない時は、口の後の 1 か所で AI_FILE に
    受け取れなかった訳（accepted: False）を書く（rejects-report.md が書けない時は OSError が上がる）。初見の読み手だけが通さない時は rolekit.is_last_attempt の回に受け取り、NOT_PASSED の印を AI_FILE に残す。
    作業ツリーを変えた返答を拒む確かめ（元の entry.take の写しの比べ）は、実行基盤が読むだけの節（mutates_checkout: false）を
    落とす形に置き換わったのでここに無い"""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    c = _cold_of(cold)

    def take(got: dict) -> dict:
        if not isinstance(got.get("text"), str) or not got["text"].strip():
            return _refused("返答に本文 text が無い", "answer")
        bad = report_roles._terms_problems(got)
        if bad:
            return _refused("返答の terms の欄が型に合わない（各要素は空でない term と definition の 2 つだけ）:\n"
                            + "\n".join(f"- {x}" for x in bad), "answer")
        bad = report_roles.format_problems(got["text"])
        if bad:
            return _refused(report_roles.CELL_REASON + "\n".join(f"- {x}" for x in bad), "format")
        head = report_roles.head_of(got["text"])
        for note in _machine_head_notes(out_dir):
            if note not in head:
                return _refused(f"機械の事実の冒頭が「{note}」と言うのに、報告の頭に無い。冒頭 3 行の 1 行目にこの句をそのまま入れる", "answer")
        not_passed = ""
        if c["verdict"] != "pass":
            if not rolekit.is_last_attempt(rolekit.attempt(out_dir, REPORT_NODE)):
                return _refused(_cold_reason(c), "cold")
            not_passed = _cold_facts(c)
        reason = f"上限の回なので受け取った。ただし{report_roles.NOT_PASSED}（機械の事実の拒みの数の行に出す）" if not_passed else ""
        return {"ok": True, "reason": reason, "text": got["text"], "terms": _list(got.get("terms")), "not_passed": not_passed}

    def kept(got: dict) -> dict:
        out = take(got)
        return out if out.get("ok") is True else _keep_rejected(out_dir, got, out)

    out = rolekit.accept_round(out_dir, REPORT_NODE, reply, kept, reject=lambda why: _refused(why, "answer"))
    if out["ok"]:
        carry.write(out_dir / AI_FILE, {"accepted": True, "text": out["text"], "terms": out["terms"], "cold": c,
                                        "not_passed": out["not_passed"], "rejects": _reject_count(out_dir)})
        return {"done": True, "ok": True, "reason": out["reason"], "kind": "", "reason_file": "", "prev_file": ""}
    if out["done"]:   # 諦めた時も、控えが扱えない時も、受け取れなかった訳を残す（collect が輪が落ちたと読まない）
        try:
            why = rolekit.given_up_reason(out_dir, REPORT_NODE)
        except (rolekit.BoardGap, OSError):
            why = ""
        carry.write(out_dir / AI_FILE, {"accepted": False, "reason": why or out["reason"], "cold": c,
                                        "rejects": _reject_count(out_dir)})
    answer = out_dir / PREV_ANSWER_FILE
    return {"done": out["done"], "ok": False, "reason": out["reason"], "kind": out.get("kind") or "answer",
            "reason_file": rolekit.reject_file_or_blank(out_dir, REPORT_NODE),
            "prev_file": str(answer) if not out["done"] and answer.is_file() else ""}


def stamp(run_id: str, workflow_file, rnd, start: dict | None) -> str:
    """報告の頭の来歴の 1 行（機械が刻む。元 report_roles.stamp の works の線・run・周・graph の版を、グラフの名（ファイルの名）・run・
    周（計画の round。何回目の案か。無ければ —）・グラフのファイルの sha256 の頭 12 字（グラフの版）・メイングラフの版（始めの記録 start の
    versions の versions.LINE_REV の頭 12 字）で。元の table の版は規則の表が無いので無い）。グラフのファイルが読めなければグラフの版の所に、
    start が None（始めの記録が読めない）ならメイングラフの版の所にその旨。読めた記録に版が無ければ「無い」と分けて書く"""
    try:
        sha = hashlib.sha256(pathlib.Path(workflow_file).read_bytes()).hexdigest()[:12]
    except OSError as e:
        sha = f"読めない（{type(e).__name__}）"
    parts = [pathlib.Path(workflow_file).stem, f"run {run_id or '—'}", f"周 {rnd if rnd is not None else '—'}", f"グラフの版 {sha}"]
    if start is None:
        parts.append("メイングラフの版 読めない（始めの記録が読めない）")
    else:
        line = versions.line_rev(start.get("versions"))
        parts.append(f"メイングラフの版 {line[:12]}" if line else f"メイングラフの版 始めの記録に無い（versions.{'.'.join(versions.LINE_REV)}）")
    return " / ".join(parts)


def embedded(machine_text: str) -> str:
    """AI の報告に付ける機械の事実: 見出しを 1 段下げて機械の事実の見出しの下に入れ、機械の「人が決めること」の見出しを
    MACHINE_DECISIONS に言い換える（人が決めることの節は書き手の頭の 1 か所だけ）"""
    out = []
    for line in machine_text.splitlines():
        if line == report.DECISIONS_HEADING:
            line = MACHINE_DECISIONS
        out.append(f"#{line}" if line.startswith("#") else line)
    return "\n".join(out) + ("\n" if machine_text.endswith("\n") else "")


def _not_passed_note(ai: dict) -> str:
    """初見の読み手が通さないまま受け取った時の、拒みの数の行の尾（通っていれば空）"""
    if ai.get("accepted") is not True or not ai.get("not_passed"):
        return ""
    return f"。{report_roles.NOT_PASSED}（上限の {rolekit.GIVE_UP_AFTER} 回目で受け取った。{oneline.one_line(ai['not_passed'])}）"


def collect(machine_text: str, *, out_dir, stamp: str) -> pathlib.Path | None:
    """AI の報告（元 report_roles.collect）。AI_FILE が無ければ None（書き手の輪が落ちた・飛ばされた）。受け取っていれば 来歴の 1 行＋
    本文＋語の定義の節＋機械の事実（embedded）、受け取れなかった時は訳と機械の事実を書く。初見の読み手が通さないまま受け取った時は、
    拒みの文を本文の頭に置かず、機械の事実の拒みの数の行（COLD_REJECTS_LINE）の尾に NOT_PASSED と通らなかった所（AI_FILE の
    not_passed）を 1 行で足す"""
    out_dir = pathlib.Path(out_dir)
    try:
        ai = oc.read_json(out_dir / AI_FILE)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        ai = {"accepted": False, "reason": f"{AI_FILE} が読めない: {oneline.one_line(e)}"}
    ai = as_dict(ai)
    if ai.get("accepted") is True:
        body = str(ai.get("text") or "").strip()
    else:
        body = f"{report_roles.FAILED_TITLE}\n\n{ai.get('reason') or '書き手の返答を受け取れなかった'}"
    note = _not_passed_note(ai)
    sec = glossary_section(f"{body}\n{note}\n{machine_text}", ai.get("terms") or [])
    colds = sum(c.get("cold", 0) for c in as_dict(ai.get("rejects")).values() if isinstance(c, dict))
    text = (f"{stamp}\n\n{body}\n\n" + (f"{sec}\n" if sec else "")
            + f"---\n\n{report_roles.MACHINE_HEADING}\n\n{report_roles.COLD_REJECTS_LINE} {colds} 回{note}\n\n{embedded(machine_text)}")
    return _write_text(out_dir / AI_REPORT_FILE, text)
