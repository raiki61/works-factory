"""機械の報告・次の依頼・前の失敗・費用と時間・語の定義の節を組み、書き手の返答を受け付けて AI の報告を組む（報告のブロックの部品）。

元は works/.shared/core/report.py と works/blk-report/lib/report_roles.py の、盤面（b）を読む関数。ここでは同じ名のまま、
ブロックの返り・関所の答え・始めの記録・型つきの成果物の読み・run の記録の行を引数で受ける（盤面の偽物は作らない）。指し札は呼び手が
開けたファイルのパスの字にして渡す（開けなければ None）。指し札の隣のファイル（docs/design.md の「書き方の決め」の名指しの
隣のファイル）は指し札の先と同じフォルダから読む。

- transcript_facts(rows, *, exclude_prefix) -> {ok, failed, errors, retried, cost, uncosted, minutes, models}（run の記録の行の読み）
- cost_rows(facts)・head_cost(facts, why): 節ごとの費用と時間の行と、費用の節の行（元 report.py:1769・1806）
- next_request(returns, gates, left)・prior_failures(returns, left): 次の依頼の findings と前の失敗の行（元 report.py:784・720）
- answer_drafts(returns, gates, start): 人の判断を待つ項目への答えの下書き（元 gatemarks.answer_drafts）
- glossary_section(text, terms, pack)・pack_terms(): 本文と機械の事実に現れる語だけの定義の節（元 report_roles.py の glossary_section）
- build(returns, gates, typed, transcript, outcome, stop_reason, *, out_dir, start, problems, run_id, transcript_why, repo,
  report_name) -> {report, next_request, prior_failures, ai_go}（元 report.py:2000）
- fallback_report(out_dir, why)・unwritten(out_dir, why): 思わぬ誤りの時の機械の報告と訳だけのファイル
- cold_body(raw)・accept(reply, cold, *, out_dir)・collect(machine, *, out_dir, stamp)・stamp(run_id, workflow_file): 書き手の
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

import carry  # noqa: E402
import changemap  # noqa: E402
import gatemarks  # noqa: E402
import gatepolicy  # noqa: E402
import outcome as oc  # noqa: E402
import outpurpose  # noqa: E402
import planmarks  # noqa: E402
import promptsection  # noqa: E402
import report  # noqa: E402
import report_roles  # noqa: E402
import startrec  # noqa: E402
import structmark  # noqa: E402
import worldmark  # noqa: E402

as_dict = oc.as_dict
PACK_TERMS = _HERE / "glossary.json"
AI_FILE = "ai.json"                     # 受け付けた書き手の返答と初見の判定（collect が読む）
AI_REPORT_FILE = "report-ai.md"         # AI の報告（元 report_roles.REPORT_NAME）
REJECTS_FILE = "report-rejects.json"    # 拒否の行の控え（元 report_roles.REJECTS_NAME）
REJECT_TEXT = "reject-{n}.md"           # 拒否の訳の本文（書き手が次の回に Read する）
FALLBACK_FILE = "report-unwritten.md"   # 思わぬ誤りの時の機械の報告（facts の report.md を上書きしない）
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

GREEN_HEADING = promptsection.Section("## 緑の認証（全部の周）", human=report.FOR_READERS)
EYES_HEADING = promptsection.Section("## 独立の目", human=report.FOR_READERS)
NOTES_HEADING = promptsection.Section("## 注意（読めなかった物）", human=report.FOR_READERS)
# AI の報告に機械の事実を付ける時の、機械の「人が決めること」の見出しの言い換え（判断は書き手の頭の 1 か所に集める）
MACHINE_DECISIONS = promptsection.Section("## 1. 人の判断を待つ物の機械の数え（判断の本文は報告の頭）", human=report.FOR_READERS)
RED_KEPT = ("inherited", "environment")       # 認証が通した赤（元から赤・環境の赤）
EYE_KEYS = ("eye", "status", "reason")
GAVE_UP_WHERE = "修正の受け付けを通らなかった単位"
PLAN_GAVE_UP_WHERE = "受け付け 計画"          # 元 report.ACCEPT_WHERE（受け付け <名>）の計画の行
GATE_PASSES = "gate-passes.json"
FIX_PLAN = "p2.fix_plan.json"                 # 計画の隣の修正案の役の返答（関所の決め手の欄つき）
PREMISES = "premises.json"                    # 判定の隣の実測した制約 {constraints}
HYPOTHESIS = "仮説"                           # 前提の役が実測でなく仮説で書いた制約の kind
ASKING = ("held", "escalate")                 # 問いの台帳で人に聞く状態（元の写しの検証器 review-record.py:343 の ASKING）
HUMAN_FACE_KINDS = ("regression", "policy")   # 事前審査の穴のうち人に回す種類（元の写しの規則 review-loop.py:4084）
GROUP_WHERE = "組"
REJUDGE_LEFT_WHERE = "判定（再審されずに残った異議）"
UNSEEN = "取れない（docs/design.md の U6。読んだ証拠を run の記録から取り出す口が無い）"

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


def _read_beside(returns: dict, rid: str, field: str, name: str):
    """(中身, 読めなかった訳)。指し札が無い・隣のファイルが無ければ (None, "")"""
    path = _beside(returns, rid, field, name)
    if path is None or not path.is_file():
        return None, ""
    try:
        return oc.read_json(path), ""
    except (OSError, ValueError) as e:
        return None, f"{path} が読めない: {report._one_line(e)}"


# ---------------------------------------------------------------- run の記録
def transcript_facts(rows, *, exclude_prefix: str = "") -> dict:
    """run の記録の行（実行基盤の logger の JSONL を 1 行ずつ読んだ dict）から、節ごとの事実。rows が None なら ok: False。
    failed は最後の行が node_error の節、errors はその節の最後の誤りの文、retried は node_error の後に済んだ節。exclude_prefix で
    始まる節（報告のブロック自身）は failed・retried に入れない。費用は自分の費用を言う行（execution.accounting が node か無い）の
    cost_usd の和。cost_usd の無い行は 0 と数えず uncosted に件数を積む。時間は node_start から最後の node_complete・node_error まで（分）"""
    if rows is None:
        return {"ok": False, "failed": [], "errors": {}, "retried": [], "cost": {}, "uncosted": {}, "minutes": {}, "models": {}}
    last, erred, errors, began, ended = {}, set(), {}, {}, {}
    cost, uncosted, models = {}, {}, {}
    for r in rows:
        if not isinstance(r, dict) or not isinstance(r.get("step"), str):
            continue
        step, kind = r["step"], r.get("type")
        if kind == "node_start":
            began.setdefault(step, report._time(r.get("ts")))
        if kind in (*COST_ROWS, "node_skipped"):
            last[step] = kind
        if kind == "node_error":
            erred.add(step)
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

    def ours(step):
        return bool(exclude_prefix) and step.startswith(exclude_prefix)
    minutes = {s: round((ended[s] - began[s]).total_seconds() / 60, 1) for s in ended
               if began.get(s) is not None and ended[s] is not None}
    failed = [s for s, k in last.items() if k == "node_error" and not ours(s)]
    return {"ok": True, "failed": failed, "errors": {s: errors.get(s, "") for s in failed},
            "retried": [s for s in erred if last.get(s) in DONE_ROWS and not ours(s)],
            "cost": cost, "uncosted": uncosted, "minutes": minutes, "models": models}


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
            parts.append(f"費用の欄が無い行 {n} 件（AI でない節か、提供元が費用を返さなかった）")
        parts.append(f"{m} 分" if m is not None else "時間を測れない")
        rows.append(f"{s}: " + "・".join(parts))
    return rows


def head_cost(facts: dict, why: str = "") -> list:
    """費用の節の行（元 report.py:1806）。記録が読めなければ「取れない（訳）」の 1 行。報告は run の中で走るので、合計は節の和を
    途中の値として出す"""
    if not facts.get("ok"):
        return [f"費用: 取れない（{why or 'run の記録が読めない'}）"]
    total = sum((facts.get("cost") or {}).values())
    return [f"費用の合計: ${total:.4f}（途中。報告は run の中で走るので run の和は読まず、自分の費用を言う行の和。言い直しの行は数えない）",
            *cost_rows(facts)]


def _model_lines(facts: dict) -> list:
    models = facts.get("models") or {}
    if not facts.get("ok"):
        return ["run の記録が読めない"]
    if not models:
        return ["記録に模型の欄が無い"]
    return [f"{s}: {', '.join(ms)}{'（run の途中で替わった）' if len(ms) > 1 else ''}" for s, ms in sorted(models.items())]


# ---------------------------------------------------------------- 問いの台帳（判定の judgment.json の questions）
def _ledger(returns: dict) -> list:
    """台帳で人に聞く状態の問い（読めない・無ければ空）"""
    jf = _ret(returns, "judge").get("judgment")
    try:
        doc = oc.read_json(jf) if isinstance(jf, str) and jf else {}
    except (OSError, ValueError):
        return []
    return [q for q in _list(as_dict(doc).get("questions")) if isinstance(q, dict) and q.get("status") in ASKING]


def _request_answers(start: dict) -> list:
    """依頼の answers（始めの記録の欄。元 gatemarks.request_answers）"""
    return [a for a in _list(as_dict(start).get("answers")) if isinstance(a, dict)]


def _origin(q: dict, unmeasured: dict) -> str:
    """問いの出どころ（元 gatemarks.origin_of: 台帳の origin。空なら key が測れていない素材の名で始まる時のその名）"""
    got = q.get("origin")
    if isinstance(got, str) and got:
        return got
    key = str(q.get("key") or "")
    return next((n for n in unmeasured if key.startswith(n) and not gatemarks.KEY_CHAR.match(key[len(n):len(n) + 1])), "")


def _gate_answered(q: dict, gates: dict, start: dict, keys: set, unmeasured: dict) -> bool:
    """依頼の answers が当たるか、修正前の関所で通す語を受け、一言が「保留: <key>」と名指していない（元 gatemarks._gate_answered。
    関所に載る問いは fork と escalate だけ）"""
    key = str(q.get("key") or "")
    if any(a.get("question") in (key, _origin(q, unmeasured)) for a in _request_answers(start)):
        return True
    gate = as_dict(gates.get("gate-before-fix"))
    asked = q.get("kind") == "fork" or q.get("status") == "escalate"
    return asked and gate.get("decision") in oc.PASS_WORDS and key not in gatemarks.hold_keys(str(gate.get("text") or ""), keys)


def held(returns: dict, gates: dict, start: dict) -> tuple[list, list]:
    """(保留にしたままの問い, 答えた問い)（元 gatemarks.held_lines・answered_lines の台帳の側）"""
    qs = _ledger(returns)
    keys = {str(q.get("key")) for q in qs if q.get("key")}
    missing = oc.unmeasured(returns)
    held_, done = [], []
    for q in qs:
        (done if _gate_answered(q, gates, start, keys, missing) else held_).append(q)
    return held_, done


def _ledger_line(q: dict, mark: str = "") -> str:
    return f"{gatemarks.ASK_HEAD} {q.get('key')}（{q.get('kind')}・{q.get('status')}{mark}）: {report._one_line(q.get('reason') or '')}"


# ---------------------------------------------------------------- 答えの下書き
def _unattended(start: dict) -> bool:
    return as_dict(start).get(gatepolicy.UNATTENDED_KEY) == gatepolicy.UNATTENDED


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
            for f in _list(as_dict(doc).get("faces")) if isinstance(f, dict) and f.get("kind") in HUMAN_FACE_KINDS]


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


def _ask_draft(q: dict, unmeasured: dict, qs: list) -> dict:
    """台帳の問い 1 つの下書き（元 gatemarks._ask_draft。question は answer_key: 出どころが測れていない素材の名でこの問いだけに
    当たればその名、ほかは問いの key）"""
    origin = _origin(q, unmeasured)
    only = origin in unmeasured and [x for x in qs if _origin(x, unmeasured) == origin] == [q]
    key = origin if only else str(q.get("key") or "")
    got = [m.strip() for m in gatemarks.PUSH_IN.findall(str(q.get("reason") or "")) if m.strip() and m.strip() != gatemarks.NO_PUSH]
    if got:
        return gatemarks._draft(key, got[0], f"{gatemarks.ASK_HEAD} {key} の理由の推し（判定の役）")
    opts = "・".join(str(o) for o in q.get("options") or []) or "（無し）"
    return gatemarks._draft(key, "", f"{gatemarks.ASK_HEAD} {key} の選択肢", f"推しを判定の役が書いていない。選択肢から人が答えを text に書く: {opts}")


def answer_drafts(returns: dict, gates: dict, start: dict) -> list:
    """人の判断を待つ項目への答えの下書き [{question, text, draft, source, note?}]（元 gatemarks.answer_drafts）:
    ①無人の run で修正前の関所が通さなかった事前審査の問い（と最後の関所が通さなかった R4 の問い）ごとに 1 行。項目の文が修正案の
    狭める行・事前審査の穴・定石の外れに当たれば、その行の決め手（推し recommend・狭めない案 no_narrow・世界の解 world）を使う
    ②人の居る run でも無人の run でも、保留のままの台帳の問いごとに 1 行（理由の推しか選択肢）
    ③問いの立っていない測れていない素材ごとに 1 行（materials.json の reason つき。依頼の answers が命令と出力つきで答えた素材は除く）
    同じ question の行は 1 度だけ。機械は関所にも問いにも答えない——下書きは依頼の入口が拒むので、人が見直してから使う"""
    out = []
    if _unattended(start):
        rows = [*_fix_plan_rows(returns), *_face_rows(returns), *_world_rows(returns)]
        for gid, rid in (("gate-before-fix", "plan-review"), ("gate-final", "eyes")):
            if as_dict(gates.get(gid)).get("decision") in oc.PASS_WORDS:
                continue
            out += [_gate_draft(q, rows) for q in _list(_ret(returns, rid).get("questions")) if isinstance(q, str) and q.strip()]
    missing = oc.unmeasured(returns)
    held_, _ = held(returns, gates, start)
    out += [_ask_draft(q, missing, held_) for q in held_]
    mats, _ = oc.materials(returns)
    asked = {_origin(q, missing) for q in _ledger(returns)}
    measured = {a.get("question") for a in _request_answers(start) if a.get("command") and a.get("output")}
    out += [gatemarks._material_draft(n, st, as_dict(mats.get(n)).get("reason")) for n, st in missing.items()
            if n not in asked and n not in measured]
    seen, kept = set(), []
    for d in out:
        if d["question"] not in seen:
            seen.add(d["question"])
            kept.append(d)
    return kept


# ---------------------------------------------------------------- 次の run に渡す物
def _outside(returns: dict) -> tuple[list, list]:
    """判定が目的の外とした所見の (次の依頼の行, 報告の行)。指し札の先は outpurpose の控えの名のファイル"""
    p = _ret(returns, "judge").get("out_of_purpose")
    if not (isinstance(p, str) and p):
        return [], []
    path = pathlib.Path(p)
    if path.name != outpurpose.FILE:
        return [], [f"目的の外の所見のファイル {p} の名が {outpurpose.FILE} でない（読まなかった）"]
    return outpurpose.next_items(path.parent), outpurpose.report_lines(path.parent)


def _parked(returns: dict) -> list:
    """修正の段が親の木へ戻せなかった組（fix.groups の returned が偽）"""
    return [g for g in _list(as_dict(returns.get("fix")).get("groups")) if isinstance(g, dict) and g.get("returned") is False]


def split_line(returns: dict) -> str:
    """冒頭の 1 行目に添える、修正の段が受けた単位と止めて持ち越した単位の 1 文（元 report.split_line。止めた組が無ければ ""）"""
    groups = [g for g in _list(as_dict(returns.get("fix")).get("groups")) if isinstance(g, dict)]
    parked = _parked(returns)
    if not parked:
        return ""
    kept = [str(u) for g in groups if g.get("returned") is True for u in _list(g.get("unit_ids"))]
    held_ = [str(u) for g in parked for u in _list(g.get("unit_ids"))]
    return (f"修正の段は {len(kept)} 単位（{'・'.join(kept) or 'なし'}）を受け、{len(held_)} 単位"
            f"（{'・'.join(held_)}）を止めて持ち越した（組 {'・'.join(str(g.get('group_id')) for g in parked)}。次の run の依頼に載る）")


def _rejudge(returns: dict) -> tuple[str, str]:
    """(再審の答え, 修正役の異議の文)"""
    verdict = as_dict(returns.get("rejudge")).get("rejudge_verdict")
    objection = as_dict(returns.get("fix")).get("objection")
    return (verdict if isinstance(verdict, str) else "", report._one_line(objection) if isinstance(objection, str) else "")


def rejudge_lines(returns: dict) -> list:
    """決着した再審の結果の行（元 report.rejudge_lines）と、再審されずに残った異議"""
    verdict, objection = _rejudge(returns)
    if verdict:
        return [f"再審の結果: {verdict}" + (f"（異議: {objection}）" if objection else "")]
    if objection:
        return [f"再審されずに残った異議: {objection}"]
    return []


def _asked_rows(returns: dict) -> list:
    """人に回した申し出を外した単位ごとの次の依頼の行（元 next_request の conflict.asked の行）"""
    out = []
    for k, r in oc.asked_units(returns):
        ruling = as_dict(r.get(oc.CONFLICT_RULING))
        why = r.get(oc.REPLAN_WHY)
        out.append({"where": k,
                    "text": f"{k}（{oc.CONFLICT_HEAD}を人に回した——直さずに残した。裁定の文: {ruling.get('text') or ''}。"
                            f"名指し {', '.join(str(x) for x in _list(r.get('between')))}"
                            + (f"。案の直し: {why}。{oc.HELD_WORK_KEPT}" if why else "") + "）"})
    return out


def next_request(returns: dict, left: list) -> list:
    """次の依頼の findings（元 report.py:784）: 残りの行（R2 の作り直しの行は前の失敗にだけ載せる。人に回した単位の修正の行は
    その単位の行が持つ）・判定が目的の外とした所見・親の木へ戻せなかった組・再審の結果と再審されずに残った異議・人に回した申し出の単位"""
    asked = _asked_rows(returns)
    owned = {f"修正 {r['where']}" for r in asked}
    items = [r for r in left if not report._r2_redesign(r) and r["where"] not in owned]
    items += _outside(returns)[0]
    items += [{"where": f"{GROUP_WHERE} {g.get('group_id')}",
               "text": f"組 {g.get('group_id')}（単位 {'・'.join(str(u) for u in _list(g.get('unit_ids')))}）を親の木へ戻せなかった——"
                       f"直しを持ち越した: {report._one_line(g.get('reason') or '理由の記録が無い')}"} for g in _parked(returns)]
    verdict, objection = _rejudge(returns)
    if verdict:
        items.append({"where": report.REJUDGE_WHERE, "text": f"再審: {verdict}" + (f"（異議: {objection}）" if objection else "")})
    elif objection:
        items.append({"where": REJUDGE_LEFT_WHERE, "text": objection})
    items += asked
    seen, out = set(), []
    for it in items:
        k = (it["where"], it["text"])
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out


def prior_failures(returns: dict, left: list) -> list:
    """前の失敗 [{where, text}]（元 report.py:720）: 受け付けを最後まで通らなかった物（修正の諦めた単位の理由と、計画が修正案を
    出せなかった訳）と R2 の作り直しの訳"""
    rows = [{"where": f"{GAVE_UP_WHERE} {u.get('unit_id')}", "text": report._one_line(u.get("reason") or "理由の記録が無い")}
            for u in _list(as_dict(returns.get("fix")).get("units")) if isinstance(u, dict) and u.get("status") == "given_up"]
    if oc.plan_gave_up(returns):
        sr = oc.planned(returns).get("stop_reason")
        rows.append({"where": PLAN_GAVE_UP_WHERE,
                     "text": "計画が直す単位を受けたのに修正案を出せなかった（受け付けが 3 回とも拒んだか、行き止まりの単位が在る）"
                             + (f": {sr}" if isinstance(sr, str) and sr else "")})
    r2 = [r for r in left if report._r2_redesign(r)]
    if r2:
        rows.append({"where": carry.REDESIGN_WHERE, "text": report._one_line(r2[0]["text"])})
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
            out.append(f"修正前の関所が聞かずに通した行（{rid}）: 無い（{'返りが無い' if r is None else '事前審査の指し札が無い'}）")
            continue
        path = pathlib.Path(p).with_name(GATE_PASSES)
        try:
            rows = oc.read_json(path)
        except (OSError, ValueError) as e:
            out.append(f"修正前の関所が聞かずに通した行（{rid}）: 無い（{path} が読めない: {report._one_line(e)}）")
            continue
        rows = rows if isinstance(rows, list) else [rows]
        out.append(f"修正前の関所が聞かずに通した行（{rid}）: {len(rows)} 件")
        out += [f"  - {report._one_line(json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x)}" for x in rows]
    return out


def _conflict_line(returns: dict) -> str:
    """申し出の件数と裁定・種類の内訳（元 report._conflict_line）"""
    c, k = oc.conflict_counts(returns)
    plan_n = f"・案の項目を直す（{oc.FIX_PLAN_ITEM}）{c[oc.FIX_PLAN_ITEM]}" if oc.FIX_PLAN_ITEM in c else ""
    swap = f"・問いを置き換える（{oc.REPLACE_QUERY}）{c[oc.REPLACE_QUERY]}" if oc.REPLACE_QUERY in c else ""
    kinds = [f"{x} {k[x]}" for x in oc.DIV_KINDS] + ([f"種類なし {k[oc.UNSET]}"] if oc.UNSET in k else [])
    return (f"{oc.CONFLICT_HEAD}: {c['parked']} 件（裁定の内訳。括弧は記録の名: テストの直しを許す（fix_test_scope）"
            f"{c['fix_test_scope']}・コードをこう直す（fix_code_as）{c['fix_code_as']}・人に回す（ask_human）{c[oc.ASK_HUMAN]}"
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
        n = 0
        for ln in lines:
            m = report.HUNK_NEW.match(ln)
            if m:
                n = int(m.group(1))
                continue
            if ln.startswith("-"):
                continue
            words = list(dict.fromkeys(report.INNER_WORD.findall(ln))) if ln.startswith("+") else []
            words = [w for w in words if not seen.setdefault(w, known(w))]
            if words:
                rows.append(f"{path}:{n}（{'・'.join(words)}）: {report._one_line(ln[1:].strip())}")
            n += 1
    return [f"{report.INNER_WORDS_HEAD}: {len(rows)} 件", *[f"  - {r}" for r in rows]] if rows else []


def verify_lines(returns: dict) -> list:
    """判定の単位の裏取りの申し送り（判定の隣の judge-verify.json）の行（元 report.verify_lines の 1 周分）"""
    doc, why = _read_beside(returns, "judge", "judgment", report.VERIFY_NOTES)
    if why or (doc is not None and not (isinstance(doc, dict) and isinstance(doc.get("units"), list))):
        return [f"判定の単位の裏取り: 申し送りが読めない（{why or '欄 units の配列が無い'}）"]
    if doc is None:
        return []
    units = [u for u in doc["units"] if isinstance(u, dict)]
    notes = []
    for u in units:
        key = u.get("key")
        if u.get("state") != "checked":
            notes.append(f"確かめられなかった: {key}（{report._one_line('・'.join(map(str, u.get('errors') or [])))}）")
            continue
        if u.get("verdict") == "not_root":
            notes.append(f"根本でない: {key}（本当の根: {report._one_line(u.get('real_root'))}。{report._one_line(u.get('why'))}）")
        elif u.get("verdict") == "unsure":
            notes.append(f"根本か決められない: {key}（{report._one_line(u.get('why'))}）")
        if u.get("evidence_found") is False:
            notes.append(f"証拠が無い: {key}（{report._one_line(u.get('evidence'))}）")
        if u.get("location_ok") is False:
            notes.append(f"場所が違う: {key}（正しい場所: {report._one_line(u.get('location'))}）")
    syn = as_dict(doc.get("synergy"))
    if syn.get("state") == "checked":
        notes += [f"重複: {'・'.join(map(str, r.get('units') or []))}（{report._one_line(r.get('why'))}）"
                  for r in _list(syn.get("duplicates")) if isinstance(r, dict)]
        notes += [f"順番: {r.get('first')} → {r.get('then')}（{report._one_line(r.get('why'))}）"
                  for r in _list(syn.get("order")) if isinstance(r, dict)]
    else:
        notes.append("単位どうしの相乗りは確かめられなかった")
    if not notes:
        return [f"判定の単位の裏取り: {len(units)} 単位とも根本・証拠・場所が合った（重複・順番の名指しなし）"]
    return [f"判定の単位の裏取り（{len(units)} 単位。単位は消していない。減らすなら関所か再審で）:", *[f"  - {x}" for x in notes]]


def pr_lines(returns: dict) -> list:
    """並行 PR と重なるので外した範囲（判定の隣の pr-excluded.json。元 report._pr_lines の外した範囲の側）"""
    doc, why = _read_beside(returns, "judge", "judgment", report.PR_EXCLUDED)
    if why:
        return [f"並行 PR と重なるので外した範囲: {why}"]
    return [f"並行 PR #{x.get('pr')} と重なるので外した範囲: {x.get('file')}:{x.get('start')}-{x.get('end')}（{x.get('why') or ''}）"
            for x in _list(as_dict(doc).get("excluded")) if isinstance(x, dict)]


def premise_lines(returns: dict, start: dict) -> list:
    """依頼が実測（measured）を持っていたのに、前提の役が仮説でしか書けなかった制約（判定の隣の premises.json。元
    report._premise_hypotheses。依頼の行は始めの記録の依頼のファイルから）"""
    doc, why = _read_beside(returns, "judge", "judgment", PREMISES)
    if why:
        return [f"前提の制約: {why}"]
    hyp = [c for c in _list(as_dict(doc).get("constraints")) if isinstance(c, dict) and c.get("kind") == HYPOTHESIS]
    req = as_dict(start).get("request_file")
    if not (hyp and isinstance(req, str) and req):
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


def _decisions(returns: dict, gates: dict, start: dict, outcome: str, left: list, *, repo=None) -> tuple[list, str]:
    """人が決めることの行と、冒頭の 2 行目（件数）。数える物は元 head3 と head_decisions の人が決める物。round_limit の残りは
    直す義務に戻せなかった単位の行を重ねて数えない"""
    plan_qs = [q for q in _list(_ret(returns, "plan-review").get("questions")) if isinstance(q, str)]
    eye_qs = [q for q in _list(as_dict(returns.get("eyes")).get("questions")) if isinstance(q, str)]
    held_, done = held(returns, gates, start)
    held_ = [q for q in held_ if not any(q2.startswith(f"{gatemarks.ASK_HEAD} {q.get('key')}（") for q2 in plan_qs)]
    asked = oc.asked_conflicts(returns)
    tests = [t for t in _list(as_dict(returns.get("fix")).get("allowed_test_changes")) if isinstance(t, str)]
    unreturned = [u for u in _list(as_dict(returns.get("fix")).get("units")) if isinstance(u, dict) and u.get("status") == "not_done"]
    premise = as_dict(as_dict(returns.get("eyes")).get("premise_check"))
    escalate = [premise] if premise.get("verdict") == "escalate" else []
    checks = left if outcome == "fixed_needs_check" else []
    counted_units = {f"修正 {u.get('unit_id')}" for u in unreturned}
    rest = [r for r in left if r["where"] not in counted_units] if outcome == "round_limit" else []
    parts = [("修正前の問い", plan_qs), ("独立の目 R4 の問い", eye_qs), ("保留にしたままの問い", [_ledger_line(q) for q in held_]),
             ("人に回した食い違いの申し出", asked), ("守りのパスに当たった差分", _hits(returns)), ("許したテストの変更", tests),
             ("直す義務に戻せなかった単位", unreturned), ("前提の検算が人に上げた物", escalate), (report.CHECKS_LEFT, checks),
             ("直しきれずに残った物", rest), ("記録が通らないこと", [outcome] if outcome == "record_invalid" else [])]
    lines = []
    for word, items in parts:
        lines.append(f"{word}: {len(items)} 件")
        for x in items:
            text = x if isinstance(x, str) else (f"{x.get('where')}: {x.get('text')}" if "where" in x else json.dumps(x, ensure_ascii=False))
            lines.append(f"  - {report._one_line(text)}")
    if held_:
        lines.append(f"  {gatemarks.ANSWER_HOW}")
    if done:
        lines.append(f"{gatemarks.ANSWERED_HEAD}（問いの台帳・{len(done)} 件。保留の件数には数えない）:")
        lines += [f"  - {_ledger_line(q)}" for q in done]
    counted = [(w, len(i)) for w, i in parts if i]
    decide = (f"{sum(n for _, n in counted)} 件——" + "・".join(f"{w} {n} 件" for w, n in counted) + f"（下の「{report.DECISIONS_HEADING.lstrip('# ')}」）"
              if counted else "")
    rev = as_dict(start).get("base_rev")
    lines.append(_conflict_line(returns))
    lines += rejudge_lines(returns)
    lines += verify_lines(returns)
    lines += pr_lines(returns)
    lines += premise_lines(returns, start)
    lines += inner_word_lines(as_dict(returns.get("fix")).get("diff"), lambda w: _target_uses(repo, rev, w))
    return lines + _gate_passes(returns), decide


def _tdd_stages(typed: dict) -> tuple[list, list]:
    """tdd-unit の成果物を (段の名, 組の段の物) の並びと、注意の行に。include の頭と周（loop）が違う物を別の修正の段に数える"""
    entries = _list(as_dict(as_dict(typed).get("by_type")).get("tdd-unit"))
    keys, stages, notes = [], [], []
    for e in entries:
        key = (e.get("include"), json.dumps(e.get("loop")))
        if key not in keys:
            keys.append(key)
        n = keys.index(key)
        name = report.TDD_STAGES[min(n, len(report.TDD_STAGES) - 1)] + (f" {n}" if n >= len(report.TDD_STAGES) else "")
        body = e.get("body")
        if not isinstance(body, list):
            notes.append(f"tdd-unit {e.get('path')} の中身が組ごとの段の物の配列でない（読まなかった）")
            continue
        for g in body:
            if isinstance(g, dict):
                stages.append((f"{name}（組 {g.get('group_id')}）", g))
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
             "修正の返りの単位の行で出す:"]
    lines += [f"  - {u.get('unit_id')}: {u.get('status')}（{report._one_line(u.get('reason') or '理由なし')}）" for u in units]
    return lines, [], notes


def _green_lines(typed: dict) -> list:
    out = []
    for e in _list(as_dict(as_dict(typed).get("by_type")).get("green-cert")):
        b = as_dict(e.get("body"))
        head = e.get("include") or e.get("node")
        cause = b.get("red_cause") or ""
        line = f"{head}（{b.get('mode') or '—'}）: {'緑' if b.get('green') is True else '緑でない'}・ok {b.get('ok')}" + (f"・赤の原因 {cause}" if cause else "")
        if b.get("ok") is True and cause in RED_KEPT:
            line += f"——赤のまま通した（{cause} の赤。直しが起こした赤でないと認証が見た）"
        out.append(line)
    return out or ["型つきの成果物 green-cert が一覧に無い"]


def _eye_lines(returns: dict, typed: dict) -> tuple[list, list]:
    eyes = returns.get("eyes")
    out, notes = [], []
    if eyes is None:
        out.append("独立の目のブロックの返りが無い（飛ばされた・落ちた）")
    for name in oc.EYE_NAMES:
        e = as_dict(eyes).get(name)
        if eyes is not None:
            out.append(f"{name.upper()}: " + (f"{e.get('status')}（{report._one_line(e.get('reason') or '理由なし')}）"
                                             if isinstance(e, dict) else "深さで省いた"))
    for v in _list(as_dict(as_dict(typed).get("by_type")).get("eye-verdict")):
        b = v.get("body")
        if not (isinstance(b, dict) and set(b) == set(EYE_KEYS)):
            notes.append(f"eye-verdict {v.get('path')} の中身が {{{', '.join(EYE_KEYS)}}} の形でない（読まなかった）")
            continue
        out.append(f"成果物 {b['eye']}（{v.get('include') or v.get('node')}）: {b['status']}（{report._one_line(b['reason'])}）")
    return out, notes


def _world_lines(returns: dict) -> list:
    """依頼の行ごとの定石と、定石を web で確かめたかの印と、依頼の解き方との比べ（元 worldmark.report_lines の行）"""
    p = _ret(returns, "judge").get("world")
    if not (isinstance(p, str) and p):
        return []
    try:
        rows = worldmark.rows(p)
    except ValueError as e:
        return [f"世界の解の行が読めない: {report._one_line(e)}"]
    return [f"類 {r['class_id']}（依頼の行 {r['finding']}）: {r['practice']}{worldmark._mark(r)}（{worldmark._versus(r)}）" for r in rows]


def _structure_lines(returns: dict) -> list:
    """構造の目の行（計画の structure の隣の design.jsonl）と、直した後の構造の実測（eyes の structure_after。元 structmark.report_lines）"""
    sp, ap = _ret(returns, "plan").get("structure"), as_dict(returns.get("eyes")).get("structure_after")
    lines = structmark.report_lines(pathlib.Path(sp).parent) if isinstance(sp, str) and sp else []
    after = structmark.after_lines(pathlib.Path(ap).parent) if isinstance(ap, str) and ap else []
    return [*lines, *(x for x in after if x not in lines)]


def _entry_lines(start: dict, returns: dict, tdd_freeze: list) -> list:
    s = as_dict(start)
    out = [f"始めの記録: run {s.get('run_id') or '—'}・元の版 {s.get('base_rev') or '—'}・テストの命令 {s.get('test_cmd') or '—'}・"
           f"TDD の実行ファイル {s.get('tdd_suite') or '—'}・無人 {s.get(gatepolicy.UNATTENDED_KEY) or '—'}"]
    shape = startrec.shape(s)
    if shape is not None:
        try:
            out.append(f"入口: {startrec.words(shape)}")
        except (KeyError, TypeError):
            out.append("入口: 入口の入力の形が読めない")
    gate_words = gatepolicy.head_words(s)
    if gate_words:
        out.append(gate_words)
    ran = [k for k, v in returns.items() if v is not None]
    skipped = [k for k, v in returns.items() if v is None]
    out.append(f"走った段: {'・'.join(ran) or '無い'}")
    out.append(f"飛ばされた・返りの無い段: {'・'.join(skipped) or '無い'}")
    depth = _list(_ret(returns, "plan").get("depth"))
    if depth:
        out.append("深さ: " + "・".join(f"{d.get('unit_id')} {d.get('depth')}" for d in depth if isinstance(d, dict)))
    base = returns.get("test-gate-base")
    if isinstance(base, dict):
        out.append(f"直す前のテスト: {'緑' if base.get('green') else '赤'}" + (f"（赤の原因 {base.get('red_cause')}）" if base.get("red_cause") else ""))
    return out + list(tdd_freeze)


def _stop_lines(outcome: str, stop_reason: str, gates: dict, tfacts: dict, returns: dict, problems: list) -> list:
    out = [f"結末: {report.OUTCOME_WORDS.get(outcome, '結末が決まらない')}（{outcome}）", f"止めた段と理由の語: {stop_reason or '止めていない'}"]
    for gid in oc.GATES:
        g = gates.get(gid)
        out.append(f"関所 {gid}: " + (f"{g.get('decision')}（{report._one_line(g.get('text') or '')}）" if isinstance(g, dict) else "開かなかった"))
    for rid in ("merge-seal", "merge-apply"):
        m = returns.get(rid)
        if isinstance(m, dict) and m.get("ok") is not True:
            out.append(f"{rid} が ok でない: {report._one_line(m.get('reason') or '訳の記録が無い')}")
    if tfacts.get("ok"):
        out += [f"{report.INTERRUPTED_HEAD}: 節 {s} が落ちた（誤り: {report._first_error({'error': (tfacts.get('errors') or {}).get(s)})}）"
                for s in tfacts.get("failed") or []]
        if tfacts.get("retried"):
            out.append(f"{report.RETRIED_HEAD}: {'・'.join(tfacts['retried'])}")
    out += [f"返りの続きが切れている: {x}" for x in oc.chain_notes(returns)]
    out += [f"結果を名乗れない訳: {report._one_line(p)}" for p in problems]
    return out


def _where_lines(returns: dict) -> list:
    out = []
    for rid, field, label in POINTERS:
        for p in oc.paths(_ret(returns, rid).get(field)):
            out.append(f"{label}（{rid}.{field}）: {p}")
    return out or ["返りに指し札が無い"]


def _bullets(lines: list) -> list:
    """節の行に「- 」を付ける（字下げした内訳の行はそのまま。元 build の行の組み方）"""
    return [r if r.startswith("  ") else f"- {r}" for r in lines]


def build(returns: dict, gates: dict, typed: dict, transcript: dict, outcome: str, stop_reason: str, *, out_dir,
          start: dict | None = None, problems=(), run_id: str = "", transcript_why: str = "", repo=None,
          report_name: str = report.REPORT_FILE) -> dict:
    """機械の報告（report_name）・次の依頼（next-request.json。空なら書かない）・前の失敗（prior-failures.json。空なら書かない）を
    out_dir に書き、{report, next_request, prior_failures, ai_go} のパスを返す（元 report.py:2000。元は盤面を読み、
    検証器の関所を踏んだ）。書き手に渡す事実のファイルは機械の報告そのもの（元の facts_text が線 A の機械の報告を字のまま使った形）。
    transcript は transcript_facts の返り、typed は型つきの成果物の読み {by_type, warnings}、repo は直しの内側の語を直す前の版と
    比べる対象の置き場（無ければ比べずに全部並べる）"""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    returns, gates, typed, start = returns or {}, gates or {}, typed or {}, start or {}
    tfacts = transcript or transcript_facts(None)
    left = oc.residue(returns)
    findings = next_request(returns, left)
    prior = prior_failures(returns, left)
    drafts = answer_drafts(returns, gates, start)
    decisions, decide = _decisions(returns, gates, start, outcome, left, repo=repo)
    tdd, freeze, tdd_notes = _tdd_lines(typed, returns)
    eye_lines, eye_notes = _eye_lines(returns, typed)
    outside = _outside(returns)[1]
    _, material_note = oc.materials(returns)
    notes = [*_list(typed.get("warnings")), *tdd_notes, *eye_notes, *([material_note] if material_note else [])]
    next_file = carry.NEXT_REQUEST_FILE if findings or drafts else ""
    draft = gatemarks.draft_line(drafts, next_file)
    split = split_line(returns)
    asked_texts = [q for rid in ("plan-review", "eyes") for q in _list(_ret(returns, rid).get("questions")) if isinstance(q, str)]
    head = gatemarks.head3(f"{report.OUTCOME_WORDS.get(outcome, '結末が決まらない')}（{outcome}）" + (f"。{split}" if split else ""),
                           decide, gatemarks.pushes(asked_texts), other=f"次の run に渡す物: {len(findings) + len(drafts)} 件")
    sections = [
        (report.DECISIONS_HEADING, [*decisions, f"次の run に渡す物: {len(findings) + len(drafts)} 件" + (f"（{next_file}）" if next_file else ""),
                                    *([draft] if draft else [])]),
        (report.ENTRY_HEADING, _entry_lines(start, returns, freeze)),
        (report.STOP_HEADING, _stop_lines(outcome, stop_reason, gates, tfacts, returns, list(problems))),
        (report.READS_HEADING, [f"読んだ証拠: {UNSEEN}"]),
        (report.WHERE_HEADING, _where_lines(returns)),
        (report.TDD_HEADING, tdd or ["修正の段が走っていない（TDD の単位の行が無い）"]),
        (GREEN_HEADING, _green_lines(typed)),
        (EYES_HEADING, eye_lines),
        (report.STRUCTURE_HEADING, _structure_lines(returns)),
        (report.WORLD_HEADING, _world_lines(returns)),
        (report.OUTSIDE_HEADING, outside),
        (report.PRIOR_HEADING, report.prior_lines(prior)),
        (report.MODEL_HEADING, _model_lines(tfacts)),
        (report.COST_HEADING, head_cost(tfacts, transcript_why)),
        (NOTES_HEADING, [report._one_line(n) for n in notes] or ["無い"]),
    ]
    text = "\n\n".join([report.TITLE_HEADING.format(run=run_id or "—") + "\n\n" + "\n".join(head),
                        *(f"{h}\n\n" + "\n".join(_bullets(lines)) for h, lines in sections if lines)]) + "\n"
    paths = {"report": _write_text(out_dir / report_name, text), "next_request": None, "prior_failures": None}
    doc = carry.compose(findings, prior, drafts)
    if findings or drafts:
        errs = carry.errors(doc, carry.NEXT_SCHEMA)
        if errs:
            raise ValueError(f"次の依頼が約束の Schema に合わない: {errs}")
        paths["next_request"] = out_dir / carry.NEXT_REQUEST_FILE
        carry.write(paths["next_request"], doc)
    if prior:
        errs = carry.errors(prior, carry.PRIOR_SCHEMA)
        if errs:
            raise ValueError(f"前の失敗が約束の Schema に合わない: {errs}")
        paths["prior_failures"] = out_dir / carry.PRIOR_FAILURES_FILE
        carry.write(paths["prior_failures"], prior)
    return {**paths, "ai_go": outcome != "record_invalid"}


def unwritten(out_dir, why: str) -> pathlib.Path:
    """機械の報告も組めない時の、訳だけの 1 ファイル（黙らない）"""
    return _write_text(pathlib.Path(out_dir) / FALLBACK_FILE, f"{report.TITLE_HEADING.format(run='—')}\n\n報告を組めなかった: {why}\n")


def fallback_report(out_dir, why: str) -> pathlib.Path:
    """思わぬ誤りの時の機械の報告（結末 record_invalid と訳の 1 行）を FALLBACK_FILE に書く（facts の report.md は上書きしない）。
    それも組めなければ訳だけの FALLBACK_FILE"""
    try:
        return build({}, {}, {}, None, "record_invalid", f"report:{why}", out_dir=out_dir, problems=[why],
                     report_name=FALLBACK_FILE)["report"]
    except Exception:  # noqa: BLE001 — 機械の報告も組めない時は訳だけを書く
        return unwritten(out_dir, why)


# ---------------------------------------------------------------- 書き手の返答の受け付けと AI の報告
def _parse(raw) -> tuple[dict | None, str]:
    if isinstance(raw, dict):
        return raw, ""
    try:
        got = json.loads(raw) if isinstance(raw, str) and raw.strip() else None
    except ValueError as e:
        return None, f"返答が JSON でない: {report._one_line(e)}"
    return (got, "") if isinstance(got, dict) else (None, "返答が JSON のオブジェクトでない")


def _cold_of(cold) -> dict:
    got, _ = _parse(cold)
    got = got or {}
    verdict = got.get("verdict") if got.get("verdict") in COLD_SCHEMA["properties"]["verdict"]["enum"] else ""
    return {"verdict": verdict, "stops": [str(s) for s in _list(got.get("stops"))],
            "guessed": [str(g) for g in _list(got.get("guessed"))], "decidable": got.get("decidable") is True}


def _cold_reason(c: dict) -> str:
    if not c["verdict"]:
        return "初見の読み手の返答を読めない（判定の語が無い）"
    lines = [f"- 止まった所: {s}" for s in c["stops"]] + [f"- 推測で埋めた所: {g}" for g in c["guessed"]]
    return ("初見の読み手（道具なし・報告の頭だけを読む）が redesign-needed を返した。次の所を、頭だけで意味が取れるように"
            "直した本文を丸ごと出し直せ:\n" + ("\n".join(lines) or "- （止まった所・推測の欄が空）"))


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


def accept(reply, cold, *, out_dir) -> dict:
    """書き手の返答を受け付ける（元 report_roles.accept を、盤面の代わりに out_dir の控えで書き直した物）。{done, ok, reason, kind,
    reason_file}。順: 読む → terms の型 → 表のセルの書式 → 初見の読み手の判定。通らなければ拒否の行を REJECTS_FILE に積み、訳を
    REJECT_TEXT に書いて書き手に返す（reason_file はその絶対パス）。拒否が GIVE_UP_AFTER 回に達したら諦め（done、AI_FILE に
    受け取れなかった訳）。初見の読み手だけが通さない時は GIVE_UP_AFTER 回目に受け取り、NOT_PASSED の印を AI_FILE に残す。
    作業ツリーを変えた返答を拒む確かめ（元の entry.take の写しの比べ）は、実行基盤が読むだけの節（mutates_checkout: false）を
    落とす形に置き換わったのでここに無い"""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        rows = oc.read_json(out_dir / REJECTS_FILE)
        rows = rows if isinstance(rows, list) else []
    except (OSError, ValueError):
        rows = []
    c = _cold_of(cold)

    def reject(reason: str, kind: str) -> dict:
        rows.append({"node": REPORT_NODE, "attempt": len(rows) + 1, "kind": kind, "reason": reason})
        carry.write(out_dir / REJECTS_FILE, rows)
        path = _write_text(out_dir / REJECT_TEXT.format(n=len(rows)), f"{report_roles.REJECT_HEADING}\n\n{reason}\n")
        give_up = len(rows) >= report_roles.GIVE_UP_AFTER
        if give_up:
            carry.write(out_dir / AI_FILE, {"accepted": False,
                                            "reason": f"{REPORT_NODE} の返答が {len(rows)} 回とも受け付けで拒まれた（最後の拒否: {reason}）",
                                            "cold": c, "rejects": report_roles.count_rejects(rows)})
        return {"done": give_up, "ok": False, "reason": reason, "kind": kind, "reason_file": str(path)}

    got, why = _parse(reply)
    if got is None or not isinstance(got.get("text"), str) or not got["text"].strip():
        return reject(why or "返答に本文 text が無い", "answer")
    bad = report_roles._terms_problems(got)
    if bad:
        return reject("返答の terms の欄が型に合わない（各要素は空でない term と definition の 2 つだけ）:\n"
                      + "\n".join(f"- {x}" for x in bad), "answer")
    bad = report_roles.format_problems(got["text"])
    if bad:
        return reject(report_roles.CELL_REASON + "\n".join(f"- {x}" for x in bad), "format")
    not_passed = ""
    if c["verdict"] != "pass":
        if len(rows) < report_roles.GIVE_UP_AFTER - 1:
            return reject(_cold_reason(c), "cold")
        not_passed = _cold_reason(c)
    carry.write(out_dir / AI_FILE, {"accepted": True, "text": got["text"], "terms": _list(got.get("terms")), "cold": c,
                                    "not_passed": not_passed, "rejects": report_roles.count_rejects(rows)})
    reason = f"上限の回なので受け取った。ただし{report_roles.NOT_PASSED}（報告の冒頭に出す）" if not_passed else ""
    return {"done": True, "ok": True, "reason": reason, "kind": "", "reason_file": ""}


def stamp(run_id: str, workflow_file) -> str:
    """報告の頭の来歴の 1 行（機械が刻む。元 report_roles.stamp の works の線・run・graph の版を、工程の名（ファイルの名）・run・
    工程のファイルの sha256 の頭 12 字で）。工程のファイルが読めなければ版の所にその旨"""
    try:
        sha = hashlib.sha256(pathlib.Path(workflow_file).read_bytes()).hexdigest()[:12]
    except OSError as e:
        sha = f"読めない（{type(e).__name__}）"
    return " / ".join([pathlib.Path(workflow_file).stem, f"run {run_id or '—'}", f"工程の版 {sha}"])


def embedded(machine_text: str) -> str:
    """AI の報告に付ける機械の事実: 見出しを 1 段下げて機械の事実の見出しの下に入れ、機械の「人が決めること」の見出しを
    MACHINE_DECISIONS に言い換える（人が決めることの節は書き手の頭の 1 か所だけ）"""
    out = []
    for line in machine_text.splitlines():
        if line == report.DECISIONS_HEADING:
            line = MACHINE_DECISIONS
        out.append(f"#{line}" if line.startswith("#") else line)
    return "\n".join(out) + ("\n" if machine_text.endswith("\n") else "")


def collect(machine_text: str, *, out_dir, stamp: str) -> pathlib.Path | None:
    """AI の報告（元 report_roles.collect）。AI_FILE が無ければ None（書き手の輪が落ちた・飛ばされた）。受け取っていれば 来歴の 1 行＋
    （通っていなければ NOT_PASSED の 1 行）＋本文＋語の定義の節＋機械の事実（embedded）、受け取れなかった時は訳と機械の事実を書く"""
    out_dir = pathlib.Path(out_dir)
    try:
        ai = oc.read_json(out_dir / AI_FILE)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        ai = {"accepted": False, "reason": f"{AI_FILE} が読めない: {report._one_line(e)}"}
    ai = as_dict(ai)
    if ai.get("accepted") is True:
        body = str(ai.get("text") or "").strip()
        if ai.get("not_passed"):
            body = f"{report_roles.NOT_PASSED}: {report._one_line(ai['not_passed'])}\n\n{body}"
    else:
        body = f"{report_roles.FAILED_TITLE}\n\n{ai.get('reason') or '書き手の返答を受け取れなかった'}"
    sec = glossary_section(f"{body}\n{machine_text}", ai.get("terms") or [])
    colds = sum(c.get("cold", 0) for c in as_dict(ai.get("rejects")).values() if isinstance(c, dict))
    text = (f"{stamp}\n\n{body}\n\n" + (f"{sec}\n" if sec else "")
            + f"---\n\n{report_roles.MACHINE_HEADING}\n\n{report_roles.COLD_REJECTS_LINE} {colds} 回\n\n{embedded(machine_text)}")
    return _write_text(out_dir / AI_REPORT_FILE, text)
