"""機械の報告・次の依頼・前の失敗・費用と時間・語の定義の節を組み、書き手の返答を受け付けて AI の報告を組む（報告のブロックの部品）。

元は works/.shared/core/report.py と works/blk-report/lib/report_roles.py の、盤面（b）を読む関数。ここでは同じ名のまま、
ブロックの返り・関所の答え・型つきの成果物の読み・run の記録の行を引数で受ける（盤面の偽物は作らない）。指し札は呼び手が
開けたファイルのパスの字にして渡す（開けなければ None）。

- transcript_facts(rows, *, exclude_prefix) -> {ok, failed, retried, cost, uncosted, minutes, models}（新しい。run の記録の行の読み）
- cost_rows(facts)・head_cost(facts): 節ごとの費用と時間の行と、費用の節（元 report.py:1769・1806）
- next_request(returns, gates, start, left)・prior_failures(returns, left): 次の依頼の findings と前の失敗の行（元 report.py:784・720）
- answer_drafts(returns, gates, start): 無人の run が答えないまま残した問いの答えの下書き（元 gatemarks.answer_drafts の報告の側）
- glossary_section(text, terms, pack_terms): 本文と機械の事実に現れる語だけの定義の節（元 report_roles.py の glossary_section）
- build(returns, gates, typed, transcript, outcome, stop_reason, *, out_dir, start, problems, run_id) -> dict（元 report.py:2000）
- accept(reply, cold, *, out_dir)・collect(machine, *, out_dir, stamp): 書き手の返答の受け付けと AI の報告（元 report_roles.py の同じ名）
"""
from __future__ import annotations

import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import carry  # noqa: E402
import gatepolicy  # noqa: E402
import gatemarks  # noqa: E402
import outcome as oc  # noqa: E402
import outpurpose  # noqa: E402
import promptsection  # noqa: E402
import report  # noqa: E402
import report_roles  # noqa: E402
import startrec  # noqa: E402
import worldmark  # noqa: E402

PACK_TERMS = _HERE / "glossary.json"
AI_FILE = "ai.json"                     # 受け付けた書き手の返答と初見の判定（collect が読む）
AI_REPORT_FILE = "report-ai.md"         # AI の報告（元 report_roles.REPORT_NAME）
REJECTS_FILE = "report-rejects.json"    # 拒否の行の控え（元 report_roles.REJECTS_NAME）
REJECT_TEXT = "reject-{n}.md"           # 拒否の訳の本文（書き手が次の回に Read する）
FALLBACK_FILE = "report-unwritten.md"   # 機械の報告も書けない時の、訳だけの 1 ファイル
REPORT_NODE = report_roles.REPORT_NODES[-1]   # 拒否の行の node（count_rejects が数える節の名）

COST_ROWS = ("node_complete", "node_error")   # 自分の費用を報告しうる行
DONE_ROWS = ("node_complete", "node_skipped")
OWN_SPEND = "node"                            # execution.accounting のうち、自分の費用を言う語（ほかは言い直しの行）

GREEN_HEADING = promptsection.Section("## 緑の認証（全部の周）", human=report.FOR_READERS)
EYES_HEADING = promptsection.Section("## 独立の目", human=report.FOR_READERS)
NOTES_HEADING = promptsection.Section("## 注意（読めなかった物）", human=report.FOR_READERS)
RED_KEPT = ("inherited", "environment")       # 認証が通した赤（元から赤・環境の赤）
EYE_KEYS = ("eye", "status", "reason")
GAVE_UP_WHERE = "修正の受け付けを通らなかった単位"
GATE_PASSES = "gate-passes.json"
UNSEEN = "取れない（docs/design.md の U6。読んだ証拠を run の記録から取り出す口が無い）"

POINTERS = (("judge", "judgment", "判定"), ("judge", "purpose", "目的"), ("judge", "world", "定石"),
            ("judge", "spec", "仕様"), ("judge", "out_of_purpose", "目的の外の所見"),
            ("plan", "plan", "計画"), ("plan", "structure", "構造の目"), ("plan", "ripple", "波及"),
            ("plan-review", "review", "事前審査"), ("plan-review", "design", "独立設計"),
            ("fix", "diff", "差分"), ("fix", "conflicts", "申し出と裁定"),
            ("test-gate-base", "baseline", "直す前の結末"), ("test-gate-base", "evidence", "試験の記録（直す前）"),
            ("test-gate-final", "evidence", "試験の記録（最後）"), ("eyes", "structure_after", "直した後の構造"),
            ("merge-seal", "diff", "封じた差分"), ("merge-apply", "diff", "置いた差分"))


def _dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def _list(v) -> list:
    return v if isinstance(v, list) else []


def _read_json(path) -> object:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _write_text(path: pathlib.Path, text: str) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    report._write_text(path, text)
    return path


def _ret(returns: dict, rid: str) -> dict:
    return _dict(oc.latest(returns, rid))


# ---------------------------------------------------------------- run の記録
def transcript_facts(rows, *, exclude_prefix: str = "") -> dict:
    """run の記録の行（実行基盤の logger の JSONL を 1 行ずつ読んだ dict）から、節ごとの事実。rows が None なら ok: False。
    failed は最後の行が node_error の節、retried は node_error の後に済んだ節。exclude_prefix で始まる節（報告のブロック自身）は
    failed・retried に入れない。費用は自分の費用を言う行（execution.accounting が node か無い）の cost_usd の和。cost_usd の無い
    行は 0 と数えず uncosted に件数を積む。時間は node_start から最後の node_complete・node_error まで（分）"""
    if rows is None:
        return {"ok": False, "failed": [], "retried": [], "cost": {}, "uncosted": {}, "minutes": {}, "models": {}}
    last, erred, began, ended = {}, set(), {}, {}
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
        if kind in COST_ROWS:
            ended[step] = report._time(r.get("ts"))
            execution = _dict(r.get("execution"))
            if execution.get("accounting", OWN_SPEND) != OWN_SPEND:
                continue
            if isinstance(r.get("cost_usd"), (int, float)) and not isinstance(r.get("cost_usd"), bool):
                cost[step] = cost.get(step, 0.0) + float(r["cost_usd"])
            else:
                uncosted[step] = uncosted.get(step, 0) + 1
            model = _dict(_dict(_dict(execution.get("binding")).get("model")).get("resolved")).get("value") \
                or _dict(_dict(execution.get("binding")).get("model")).get("requested")
            if isinstance(model, str) and model and model not in models.setdefault(step, []):
                models[step].append(model)

    def ours(step):
        return bool(exclude_prefix) and step.startswith(exclude_prefix)
    minutes = {s: round((ended[s] - began[s]).total_seconds() / 60, 1) for s in ended
               if began.get(s) is not None and ended[s] is not None}
    return {"ok": True,
            "failed": [s for s, k in last.items() if k == "node_error" and not ours(s)],
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
        rows.append(f"- {s}: " + "・".join(parts))
    return rows


def head_cost(facts: dict, why: str = "") -> list:
    """費用の節（元 report.py:1806）。記録が読めなければ「取れない（訳）」の 1 行"""
    if not facts.get("ok"):
        return [f"{report.COST_HEADING}", "", f"取れない（{why or 'run の記録が読めない'}）"]
    total = sum((facts.get("cost") or {}).values())
    return [f"{report.COST_HEADING}", "", f"合計（自分の費用を言う行の和。言い直しの行は数えない）: ${total:.4f}", *cost_rows(facts)]


def _model_lines(facts: dict) -> list:
    models = facts.get("models") or {}
    if not facts.get("ok"):
        return ["run の記録が読めない"]
    if not models:
        return ["記録に模型の欄が無い"]
    return [f"- {s}: {', '.join(ms)}{'（run の途中で替わった）' if len(ms) > 1 else ''}" for s, ms in sorted(models.items())]


# ---------------------------------------------------------------- 次の run に渡す物
def _unattended(start: dict) -> bool:
    return _dict(start).get(gatepolicy.UNATTENDED_KEY) == gatepolicy.UNATTENDED


def _questions(returns: dict) -> list:
    """人への問い（事前審査の問いと R4 の問い）を (出どころ, 文) で。同じ文は 1 度だけ"""
    seen, out = set(), []
    for source, rid in (("事前審査の問い", "plan-review"), ("独立の目 R4 の問い", "eyes")):
        for q in _list(_ret(returns, rid).get("questions")):
            if isinstance(q, str) and q.strip() and q not in seen:
                seen.add(q)
                out.append((source, q))
    return out


def answer_drafts(returns: dict, gates: dict, start: dict) -> list:
    """無人の run が答えないまま残した問いごとの答えの下書き [{question, text, draft, source, note?}]（元 gatemarks.answer_drafts の
    報告の側。推しの尾 gatemarks.PUSH_TAIL が在ればその推しを text に、無ければ text を空にして訳を note に）。人が関所で答えた
    run は作らない。測れていない素材ごとにも 1 行"""
    if not _unattended(start):
        return []
    answered = {"事前審査の問い": gates.get("gate-before-fix"), "独立の目 R4 の問い": gates.get("gate-final")}
    out = []
    for source, q in _questions(returns):
        if _dict(answered[source]).get("decision") in oc.PASS_WORDS:
            continue
        push = gatemarks.PUSH_IN.findall(q) if gatemarks.PUSH_TAIL.search(q) else []
        if push:
            out.append(carry.draft({"question": gatemarks.PUSH_TAIL.sub("", q), "text": push[-1].strip()}, f"{source}の推し"))
        else:
            out.append(carry.draft({"question": q, "text": ""}, source,
                                   f"推しは{gatemarks.NO_PUSH}（材料は報告の「{report.DECISIONS_HEADING.lstrip('# ')}」）"))
    for name, status in oc.unmeasured(returns).items():
        out.append(carry.draft({"question": name, "text": ""}, "測れていない素材",
                               f"素材 '{name}' は {status}。手元で確かめて answers に command と output を書く"))
    return out


def _outside(returns: dict) -> tuple[list, list]:
    """判定が目的の外とした所見の (次の依頼の行, 報告の行)。指し札の先は outpurpose の控えの名のファイル"""
    p = _ret(returns, "judge").get("out_of_purpose")
    if not (isinstance(p, str) and p):
        return [], []
    path = pathlib.Path(p)
    if path.name != outpurpose.FILE:
        return [], [f"目的の外の所見のファイル {p} の名が {outpurpose.FILE} でない（読まなかった）"]
    return outpurpose.next_items(path.parent), outpurpose.report_lines(path.parent)


def next_request(returns: dict, left: list) -> list:
    """次の依頼の findings（元 report.py:784）: 残りの行（R2 の作り直しの行は前の失敗にだけ載せる）・判定が目的の外とした所見"""
    rows = [r for r in left if not report._r2_redesign(r)]
    return rows + _outside(returns)[0]


def prior_failures(returns: dict, left: list) -> list:
    """前の失敗 [{where, text}]（元 report.py:720）: R2 の作り直しの訳と、受け付けを最後まで通らなかった物（修正の諦めた単位の理由）"""
    rows = [{"where": f"{GAVE_UP_WHERE} {u.get('unit_id')}", "text": report._one_line(u.get("reason") or "理由の記録が無い")}
            for u in _list(_dict(returns.get("fix")).get("units")) if isinstance(u, dict) and u.get("status") == "given_up"]
    r2 = [r for r in left if report._r2_redesign(r)]
    if r2:
        rows.append({"where": carry.REDESIGN_WHERE, "text": report._one_line(r2[0]["text"])})
    return rows


# ---------------------------------------------------------------- 語の定義
def pack_terms() -> list:
    try:
        return list(_dict(_read_json(PACK_TERMS)).get("terms") or [])
    except (OSError, ValueError):
        return []


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


# ---------------------------------------------------------------- 機械の報告の節
def _gate_passes(returns: dict) -> list:
    out = []
    for rid in ("plan-review", "replan-review"):
        r = returns.get(rid)
        if rid == "replan-review" and r is None:
            continue
        p = _dict(r).get("review")
        if not (isinstance(p, str) and p):
            out.append(f"- 修正前の関所が聞かずに通した行（{rid}）: 無い（{'返りが無い' if r is None else '事前審査の指し札が無い'}）")
            continue
        path = pathlib.Path(p).with_name(GATE_PASSES)
        try:
            rows = _read_json(path)
        except (OSError, ValueError) as e:
            out.append(f"- 修正前の関所が聞かずに通した行（{rid}）: 無い（{path} が読めない: {report._one_line(e)}）")
            continue
        rows = rows if isinstance(rows, list) else [rows]
        out.append(f"- 修正前の関所が聞かずに通した行（{rid}）: {len(rows)} 件")
        out += [f"  - {report._one_line(json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x)}" for x in rows]
    return out


def _decisions(returns: dict, outcome: str, left: list) -> tuple[list, str]:
    """人が決めることの行と、冒頭の 2 行目（件数）"""
    plan_qs = [q for q in _list(_ret(returns, "plan-review").get("questions")) if isinstance(q, str)]
    eye_qs = [q for q in _list(_dict(returns.get("eyes")).get("questions")) if isinstance(q, str)]
    asked = oc.asked_conflicts(returns)
    hits = [h for h in _list(_dict(returns.get("merge-seal")).get("protected_hits")) if isinstance(h, str)]
    tests = [t for t in _list(_dict(returns.get("fix")).get("allowed_test_changes")) if isinstance(t, str)]
    unreturned = [u for u in _list(_dict(returns.get("fix")).get("units")) if isinstance(u, dict) and u.get("status") == "not_done"]
    premise = _dict(_dict(returns.get("eyes")).get("premise_check"))
    escalate = [premise] if premise.get("verdict") == "escalate" else []
    checks = left if outcome == "fixed_needs_check" else []
    rest = left if outcome == "round_limit" else []
    parts = [("修正前の問い", plan_qs), ("独立の目 R4 の問い", eye_qs), ("人に回した食い違いの申し出", asked),
             ("守りのパスに当たった差分", hits), ("許したテストの変更", tests), ("直す義務に戻せなかった単位", unreturned),
             ("前提の検算が人に上げた物", escalate), (report.CHECKS_LEFT, checks), ("直しきれずに残った物", rest),
             ("記録が通らないこと", [outcome] if outcome == "record_invalid" else [])]
    lines = []
    for word, items in parts:
        lines.append(f"- {word}: {len(items)} 件")
        for x in items:
            text = x if isinstance(x, str) else (f"{x.get('where')}: {x.get('text')}" if "where" in x else json.dumps(x, ensure_ascii=False))
            lines.append(f"  - {report._one_line(text)}")
    counted = [(w, len(i)) for w, i in parts if i]
    decide = (f"{sum(n for _, n in counted)} 件——" + "・".join(f"{w} {n} 件" for w, n in counted) + f"（下の「{report.DECISIONS_HEADING.lstrip('# ')}」）"
              if counted else "")
    return lines + _gate_passes(returns), decide


def _tdd_stages(typed: dict, returns: dict) -> tuple[list, list]:
    """tdd-unit の成果物を (段の名, 組の段の物) の並びと、注意の行に。include の頭と周（loop）が違う物を別の修正の段に数える"""
    entries = _list(_dict(_dict(typed).get("by_type")).get("tdd-unit"))
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
    stages, notes = _tdd_stages(typed, returns)
    if stages:
        return report.tdd_lines(stages), report.freeze_lines(stages), notes
    units = [u for u in _list(_dict(returns.get("fix")).get("units")) if isinstance(u, dict)]
    if not units:
        return [], [], notes
    lines = ["型つきの成果物 tdd-unit が一覧に無い（修正の段が出していない・子の run の成果物が親の一覧に載らない。docs/design.md の U8）。"
             "修正の返りの単位の行で出す:"]
    lines += [f"  - {u.get('unit_id')}: {u.get('status')}（{report._one_line(u.get('reason') or '理由なし')}）" for u in units]
    return lines, [], notes


def _green_lines(typed: dict) -> list:
    out = []
    for e in _list(_dict(_dict(typed).get("by_type")).get("green-cert")):
        b = _dict(e.get("body"))
        head = e.get("include") or e.get("node")
        cause = b.get("red_cause") or ""
        line = f"- {head}（{b.get('mode') or '—'}）: {'緑' if b.get('green') is True else '緑でない'}・ok {b.get('ok')}" + (f"・赤の原因 {cause}" if cause else "")
        if b.get("ok") is True and cause in RED_KEPT:
            line += f"——赤のまま通した（{cause} の赤。直しが起こした赤でないと認証が見た）"
        out.append(line)
    return out or ["- 型つきの成果物 green-cert が一覧に無い"]


def _eye_lines(returns: dict, typed: dict) -> tuple[list, list]:
    eyes = returns.get("eyes")
    out, notes = [], []
    if eyes is None:
        out.append("- 独立の目のブロックの返りが無い（飛ばされた・落ちた）")
    for name in oc.EYE_NAMES:
        e = _dict(eyes).get(name)
        if eyes is not None:
            out.append(f"- {name.upper()}: " + (f"{e.get('status')}（{report._one_line(e.get('reason') or '理由なし')}）"
                                               if isinstance(e, dict) else "深さで省いた"))
    for v in _list(_dict(_dict(typed).get("by_type")).get("eye-verdict")):
        b = v.get("body")
        if not (isinstance(b, dict) and set(b) == set(EYE_KEYS)):
            notes.append(f"eye-verdict {v.get('path')} の中身が {{{', '.join(EYE_KEYS)}}} の形でない（読まなかった）")
            continue
        out.append(f"- 成果物 {b['eye']}（{v.get('include') or v.get('node')}）: {b['status']}（{report._one_line(b['reason'])}）")
    return out, notes


def _world_lines(returns: dict) -> list:
    p = _ret(returns, "judge").get("world")
    if not (isinstance(p, str) and p):
        return []
    try:
        rows = worldmark.rows(p)
    except ValueError as e:
        return [f"- 世界の解の行が読めない: {report._one_line(e)}"]
    return [f"- 類 {r['class_id']}（依頼の行 {r['finding']}）: {r['practice']}" for r in rows]


def _entry_lines(start: dict, returns: dict, tdd_freeze: list) -> list:
    s = _dict(start)
    out = [f"- 始めの記録: run {s.get('run_id') or '—'}・元の版 {s.get('base_rev') or '—'}・テストの命令 {s.get('test_cmd') or '—'}・"
           f"TDD の実行ファイル {s.get('tdd_suite') or '—'}・無人 {s.get(gatepolicy.UNATTENDED_KEY) or '—'}"]
    shape = startrec.shape(s)
    if shape is not None:
        try:
            out.append(f"- 入口: {startrec.words(shape)}")
        except (KeyError, TypeError):
            out.append("- 入口: 入口の入力の形が読めない")
    ran = [k for k, v in returns.items() if v is not None]
    skipped = [k for k, v in returns.items() if v is None]
    out.append(f"- 走った段: {'・'.join(ran) or '無い'}")
    out.append(f"- 飛ばされた・返りの無い段: {'・'.join(skipped) or '無い'}")
    depth = _list(_ret(returns, "plan").get("depth"))
    if depth:
        out.append("- 深さ: " + "・".join(f"{d.get('unit_id')} {d.get('depth')}" for d in depth if isinstance(d, dict)))
    base = returns.get("test-gate-base")
    if isinstance(base, dict):
        out.append(f"- 直す前のテスト: {'緑' if base.get('green') else '赤'}" + (f"（赤の原因 {base.get('red_cause')}）" if base.get("red_cause") else ""))
    return out + [f"- {x}" for x in tdd_freeze]


def _stop_lines(outcome: str, stop_reason: str, gates: dict, tfacts: dict, returns: dict, problems: list) -> list:
    out = [f"- 結末: {report.OUTCOME_WORDS.get(outcome, '結末が決まらない')}（{outcome}）", f"- 止めた段と理由の語: {stop_reason or '止めていない'}"]
    for gid in oc.GATES:
        g = gates.get(gid)
        out.append(f"- 関所 {gid}: " + (f"{g.get('decision')}（{report._one_line(g.get('text') or '')}）" if isinstance(g, dict) else "開かなかった"))
    if tfacts.get("ok"):
        if tfacts.get("failed"):
            out.append(f"- {report.INTERRUPTED_HEAD}: 落ちた節 {'・'.join(tfacts['failed'])}")
        if tfacts.get("retried"):
            out.append(f"- {report.RETRIED_HEAD}: {'・'.join(tfacts['retried'])}")
    out += [f"- 返りの続きが切れている: {x}" for x in oc.chain_notes(returns)]
    out += [f"- 結果を名乗れない訳: {report._one_line(p)}" for p in problems]
    return out


def _where_lines(returns: dict) -> list:
    out = []
    for rid, field, label in POINTERS:
        v = _ret(returns, rid).get(field)
        for p in oc._paths(v):
            out.append(f"- {label}（{rid}.{field}）: {p}")
    return out or ["- 返りに指し札が無い"]


def build(returns: dict, gates: dict, typed: dict, transcript: dict, outcome: str, stop_reason: str, *, out_dir,
          start: dict | None = None, problems=(), run_id: str = "", transcript_why: str = "") -> dict:
    """機械の報告（report.md）・次の依頼（next-request.json。空なら書かない）・前の失敗（prior-failures.json。空なら書かない）を
    out_dir に書き、{report, next_request, prior_failures, ai_go} のパスを返す（元 report.py:2000。元は盤面を読み、
    検証器の関所を踏んだ）。書き手に渡す事実のファイルは機械の報告そのもの（元の facts_text が線 A の機械の報告を字のまま使った形）。
    transcript は transcript_facts の返り、typed は型つきの成果物の読み {by_type, warnings}"""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    returns, gates, typed, start = returns or {}, gates or {}, typed or {}, start or {}
    tfacts = transcript or transcript_facts(None)
    left = oc.residue(returns)
    findings = next_request(returns, left)
    prior = prior_failures(returns, left)
    drafts = answer_drafts(returns, gates, start)
    decisions, decide = _decisions(returns, outcome, left)
    tdd, freeze, tdd_notes = _tdd_lines(typed, returns)
    eye_lines, eye_notes = _eye_lines(returns, typed)
    outside = _outside(returns)[1]
    _, material_note = oc.materials(returns)
    notes = [*_list(typed.get("warnings")), *tdd_notes, *eye_notes, *([material_note] if material_note else [])]
    next_count = len(findings) + len(drafts)
    head = gatemarks.head3(f"{report.OUTCOME_WORDS.get(outcome, '結末が決まらない')}（{outcome}）", decide,
                           gatemarks.pushes([q for _, q in _questions(returns)]), other=f"次の run に渡す物: {next_count} 件")
    sections = [
        (report.TITLE_HEADING.format(run=run_id or "—"), head),
        (report.DECISIONS_HEADING, decisions),
        (report.ENTRY_HEADING, _entry_lines(start, returns, freeze)),
        (report.STOP_HEADING, _stop_lines(outcome, stop_reason, gates, tfacts, returns, list(problems))),
        (report.READS_HEADING, [f"- 読んだ証拠: {UNSEEN}"]),
        (report.WHERE_HEADING, _where_lines(returns)),
        (report.TDD_HEADING, tdd or ["- 修正の段が走っていない（TDD の単位の行が無い）"]),
        (GREEN_HEADING, _green_lines(typed)),
        (EYES_HEADING, eye_lines),
        (report.WORLD_HEADING, _world_lines(returns)),
        (report.OUTSIDE_HEADING, outside),
        (report.PRIOR_HEADING, report.prior_lines(prior)),
        (report.MODEL_HEADING, _model_lines(tfacts)),
        (NOTES_HEADING, [f"- {report._one_line(n)}" for n in notes] or ["- 無い"]),
    ]
    text = "\n\n".join(f"{h}\n\n" + "\n".join(lines) for h, lines in sections if lines)
    text += "\n\n" + "\n".join(head_cost(tfacts, transcript_why)) + "\n"
    paths = {"report": _write_text(out_dir / report.REPORT_FILE, text), "next_request": None, "prior_failures": None}
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
    """機械の報告も書けない時の、訳だけの 1 ファイル（黙らない）"""
    return _write_text(pathlib.Path(out_dir) / FALLBACK_FILE, f"{report.TITLE_HEADING.format(run='—')}\n\n報告を組めなかった: {why}\n")


def failed_line(what: str, error: BaseException) -> str:
    """思わぬ誤りの 1 行（返す節は stop_reason に report: を付けて載せる）"""
    return f"{what}を組めなかった（{type(error).__name__}: {' '.join(str(error).split())}）"


def fallback_report(out_dir, why: str) -> pathlib.Path:
    """思わぬ誤りの時の機械の報告（結末 record_invalid と訳の 1 行）。それも組めなければ訳だけの 1 ファイル"""
    try:
        return build({}, {}, {}, None, "record_invalid", f"report:{why}", out_dir=out_dir, problems=[why])["report"]
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
    verdict = got.get("verdict") if got.get("verdict") in ("pass", "redesign-needed") else ""
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
    REJECT_TEXT に書いて書き手に返す。拒否が GIVE_UP_AFTER 回に達したら諦め（done、AI_FILE に受け取れなかった訳）。初見の読み手
    だけが通さない時は GIVE_UP_AFTER 回目に受け取り、NOT_PASSED の印を AI_FILE に残す"""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        rows = _read_json(out_dir / REJECTS_FILE)
        rows = rows if isinstance(rows, list) else []
    except (OSError, ValueError):
        rows = []
    c = _cold_of(cold)

    def reject(reason: str, kind: str) -> dict:
        rows.append({"node": REPORT_NODE, "attempt": len(rows) + 1, "kind": kind, "reason": reason})
        report._write_json(out_dir / REJECTS_FILE, rows)
        path = _write_text(out_dir / REJECT_TEXT.format(n=len(rows)), f"{report_roles.REJECT_HEADING}\n\n{reason}\n")
        give_up = len(rows) >= report_roles.GIVE_UP_AFTER
        if give_up:
            report._write_json(out_dir / AI_FILE, {"accepted": False, "reason": reason, "cold": c,
                                                   "rejects": report_roles.count_rejects(rows)})
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
    report._write_json(out_dir / AI_FILE, {"accepted": True, "text": got["text"], "terms": _list(got.get("terms")), "cold": c,
                                           "not_passed": not_passed, "rejects": report_roles.count_rejects(rows)})
    reason = f"上限の回なので受け取った。ただし{report_roles.NOT_PASSED}（報告の冒頭に出す）" if not_passed else ""
    return {"done": True, "ok": True, "reason": reason, "kind": "", "reason_file": ""}


def collect(machine_text: str, *, out_dir, stamp: str) -> pathlib.Path | None:
    """AI の報告（元 report_roles.collect）。AI_FILE が無ければ None（書き手の輪が落ちた・飛ばされた）。受け取っていれば 来歴の 1 行＋
    （通っていなければ NOT_PASSED の 1 行）＋本文＋語の定義の節＋機械の事実、受け取れなかった時は訳と機械の事実を書く"""
    out_dir = pathlib.Path(out_dir)
    try:
        ai = _read_json(out_dir / AI_FILE)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        ai = {"accepted": False, "reason": f"{AI_FILE} が読めない: {report._one_line(e)}"}
    ai = _dict(ai)
    if ai.get("accepted") is True:
        body = str(ai.get("text") or "").strip()
        if ai.get("not_passed"):
            body = f"{report_roles.NOT_PASSED}: {report._one_line(ai['not_passed'])}\n\n{body}"
    else:
        body = f"{report_roles.FAILED_TITLE}\n\n{ai.get('reason') or '書き手の返答を受け取れなかった'}"
    sec = glossary_section(f"{body}\n{machine_text}", ai.get("terms") or [])
    colds = sum(c.get("cold", 0) for c in _dict(ai.get("rejects")).values() if isinstance(c, dict))
    text = (f"{stamp}\n\n{body}\n\n" + (f"{sec}\n" if sec else "")
            + f"---\n\n{report_roles.MACHINE_HEADING}\n\n- 初見の読み手の拒否: {colds} 回\n\n{machine_text}")
    return _write_text(out_dir / AI_REPORT_FILE, text)
