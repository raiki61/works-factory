"""結末の語の決め方（docs/design.md の lib/outcome「決め方だけを持つ」）。語の正本は報告のブロックの返す節の enum で、
ここは report.OUTCOMES の 10 語のどれを返すかだけを決める。

元は works/.shared/core/report.py:670 の decide_outcome（盤面 b と検証器の関所 gate を読んだ）。ここでは盤面の代わりに
ブロックの返り（returns）・人の関所の答え（gates）・報告が集めた事実（facts）を引数で受ける。順は元の docstring の順を写し、
元に無い「途中で終わった」（interrupted）を 5 に置く。

- returns: 差し込んだブロックの id → 返りの dict か None（飛ばされた・落ちた・読めない）。指し札の欄は開けたファイルのパスの字
  （開けなければ None）。conflicts だけは段ごとのパスの配列もよい
- gates: 関所の id → {decision, text} か None（開かなかった）
- facts: {start_ok, record_problems, failed}。failed は run の記録で最後が誤りの節の id の並び（記録が読めなければ None）。
  record_problems は record_problems() の返り
- decide_outcome(returns, gates, facts) -> (結末の語, stop_reason)。stop_reason は「<段の id>:<語>」、止まらなければ ""
- record_problems(returns, gates, *, unread, unopened) -> (結果を名乗れない訳, 注意): 入力の読めなかった訳・開けなかった指し札・
  申し出と裁定の読めなかった訳・知らない答えの語を、結果を名乗らせない物と注意に分ける
- residue(returns) -> fixed を名乗らせない残りの行 [{where, text}]（報告と次の依頼が同じ行を読む）
- conflict_rows(returns)・asked_conflicts(returns)・conflict_counts(returns): 申し出と裁定の行・人に回した行・裁定と種類の内訳
- materials(returns)・unmeasured(returns): 判定の隣の素材の状態と、今の周に測れていない素材 {名: status}
- unknown_answers(gates) -> 通しにも止めにも数えない答えの語の行
"""
from __future__ import annotations

import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import answer  # noqa: E402
import report  # noqa: E402
import stopby  # noqa: E402
import structmark  # noqa: E402

OK_OUTCOMES = ("fixed", "fixed_needs_check", "no_fix_needed")   # 返す節の ok が true になる結末（docs/design.md の report の返り）
GATES = ("gate-start", "gate-before-fix", "gate-replan", "gate-final")
STOP_WORDS = report.FINAL_GATE_STOPS   # stop は answer.VERBS の止める語、reject は今の works の最後の関所の止める語
PASS_WORDS = ("approve", *(v for v in answer.VERBS if v not in STOP_WORDS))   # approve は関所の decisions に要る語
WAIT_WORDS = (stopby.CONFLICT, stopby.REPLAN, stopby.TDD_REPEAT)   # 線の止めでなく、人の答えを待つ語
FIX_STATUS_LEFT = ("given_up", "not_done")
EYE_STATUS_LEFT = ("redesign-needed", "unverifiable")
EYE_NAMES = tuple(e.lower() for e in report.EYES)
GIVE_UP = "give-up"
NOT_OK = "not-ok"
NODE_ERROR = "node-error"
CHAIN_CUT = "chain-cut"
RECORD_INVALID = "record-invalid"
# 開けないと結果を名乗れない指し札 (段, 欄)。申し出と裁定が読めないと、人に回した申し出が見えなくなる
MUST_OPEN = (("fix", "conflicts"),)

# fix の conflicts の先（今の works の conflicts.json の包み）を欄の名で読む字。元は works/.shared/core/conflict.py:91-160 の
# FILE・DECISIONS・FIX_DECISIONS・PLAN_UNITS・DIV_KINDS・UNSET・HEAD・REPLAN_STATE・WAITING・AMENDED・REPLAN_WHY・HELD_WORK_KEPT
# と asked:388・ruled_units:470・counts:517・kind_counts:529（掃除の段で lib/conflict.py を引く形に寄せる）
CONFLICT_ITEMS = "items"
CONFLICT_RULING = "ruling"
CONFLICT_DECISION = "decision"
CONFLICT_REPLAN = "replan"
CONFLICT_KIND = "kind"
CONFLICT_HEAD = "食い違いの申し出"
ASK_HUMAN = "ask_human"
REPLACE_QUERY = "replace_query"
FIX_PLAN_ITEM = "fix_plan_item"
FIX_RULINGS = ("fix_test_scope", "fix_code_as", REPLACE_QUERY)
RULINGS = ("fix_test_scope", "fix_code_as", ASK_HUMAN, REPLACE_QUERY, FIX_PLAN_ITEM)
REPLAN_KEPT = ("waiting", "amended")
REPLAN_WHY = "replan_why"
PLAN_UNITS = "plan_units"
HELD_WORK_KEPT = "この run の修正の段で直した分は作業ツリーに残した"
DIV_KINDS = ("brief_vs_judgment", "unnamed_test_broke", "not_red", "scope_needed", "query_hits_fixed", "needs_context")
UNSET = "unset"

# 判定の judgment の隣の素材の測りの状態 {<素材の名>: {status, …}}（docs/design.md の「書き方の決め」の名指しの隣のファイル）。
# 測れていない status は元の写しの検証器の STATUS で阻害になる物（gatemarks.unmeasured。works/.shared/core/gatemarks.py:708-716）
MATERIALS_FILE = "materials.json"
UNMEASURED = ("not_run", "awaiting_human")
MATERIAL_WHERE = "素材"

# 返りの続き (前の段, 前の段の欄（None は返りが在るだけ）, 後の段, 文)。前の段が欄を真にしたのに後の段の返りが無い run は途中で終わった
CHAIN = (("judge", "ready", "plan", "判定が直す単位を出したのに計画の返りが無い"),
         ("plan", "ready", "fix", "計画が修正案を出したのに修正の返りが無い"),
         ("fix", None, "test-gate-final", "修正の段が走ったのに最後のテストの返りが無い"),
         ("test-gate-final", "ok", "merge-seal", "最後のテストが通ったのに差分を封じた返りが無い"))


def as_dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def read_json(path) -> object:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


LATER = {"judge": "rejudge", "plan": "replan", "plan-review": "replan-review"}   # 後の段の返り（線は後の段で先に読む）


def latest(returns: dict, rid: str) -> dict | None:
    """段の返り（後の段の返りが在ればそちら）"""
    got = returns.get(LATER.get(rid, ""))
    got = got if isinstance(got, dict) else returns.get(rid)
    return got if isinstance(got, dict) else None


def judged(returns: dict) -> dict | None:
    return latest(returns, "judge")


def planned(returns: dict) -> dict | None:
    return latest(returns, "plan")


def plan_reviewed(returns: dict) -> dict | None:
    return latest(returns, "plan-review")


def _units(returns: dict) -> list:
    got = as_dict(judged(returns)).get("units")
    return got if isinstance(got, list) else []


def paths(v) -> list:
    """指し札 1 つ（パスの字）・段ごとの配列・None を、パスの並びに"""
    if isinstance(v, str) and v:
        return [v]
    if isinstance(v, list):
        return [p for p in v if isinstance(p, str) and p]
    return []


def record_problems(returns: dict, gates: dict, *, unread=(), unopened=()) -> tuple[list, list]:
    """(結果を名乗れない訳, 注意)。unread は入力の読めなかった訳の行、unopened は開けなかった指し札 [(段, 欄, 訳)]。
    MUST_OPEN の指し札が開けない・申し出と裁定のファイルが読めない・知らない答えの語は結果を名乗れない訳、ほかの開けなかった
    指し札は注意"""
    must = [why for rid, field, why in unopened if (rid, field) in MUST_OPEN]
    notes = [why for rid, field, why in unopened if (rid, field) not in MUST_OPEN]
    return [*unread, *must, *conflict_rows(returns)[1], *unknown_answers(gates)], notes


def conflict_rows(returns: dict) -> tuple[list, list]:
    """fix の conflicts の先の行を全部の段で合わせた物と、読めなかった訳の行"""
    rows, notes = [], []
    for p in paths(as_dict(returns.get("fix")).get("conflicts")):
        try:
            doc = read_json(p)
            items = doc.get(CONFLICT_ITEMS) if isinstance(doc, dict) else None
            if not isinstance(items, list):
                raise ValueError(f"欄 {CONFLICT_ITEMS} の配列が無い")
        except (OSError, ValueError) as e:
            notes.append(f"申し出と裁定のファイル {p} が読めない: {report._one_line(e)}")
            continue
        rows += [i for i in items if isinstance(i, dict)]
    return rows, notes


def _ruling(row: dict) -> str | None:
    return as_dict(row.get(CONFLICT_RULING)).get(CONFLICT_DECISION)


def asked_conflicts(returns: dict) -> list:
    """人に諮る申し出の行（元 conflict.asked: 直す裁定でも裁定無しでもなく、案の直しを待つ・直した行でもない）"""
    rows, _ = conflict_rows(returns)
    return [i for i in rows if _ruling(i) not in (None, *FIX_RULINGS) and i.get(CONFLICT_REPLAN) not in REPLAN_KEPT]


def asked_units(returns: dict) -> list:
    """人に回した行が外した単位ごとの (単位, 行)（元 report._asked_units と conflict.ruled_units: ask_human は申し出の単位、
    諦めた fix_plan_item はその項目に載る単位の全部）。1 単位に 1 行で、単位自身の申し出の行を先に採る"""
    rows = asked_conflicts(returns)
    own, out = {}, {}
    for r in rows:
        own.setdefault(r.get("unit_key"), r)
    for r in rows:
        for k in dict.fromkeys([r.get("unit_key"), *(as_dict(r.get(CONFLICT_RULING)).get(PLAN_UNITS) or [])]):
            if isinstance(k, str) and k:
                out.setdefault(k, own.get(k, r))
    return list(out.items())


def conflict_counts(returns: dict) -> tuple[dict, dict]:
    """(裁定の内訳, 種類の内訳)（元 conflict.counts・kind_counts）。裁定は {parked, fix_test_scope, fix_code_as, ask_human,
    unruled} に、replace_query・fix_plan_item は裁いた物が在る時だけ足す。種類は DIV_KINDS の全部（0 も）に、kind の無い行が
    在る時だけ UNSET を足す"""
    rows, _ = conflict_rows(returns)
    rulings = {"parked": len(rows), "unruled": sum(1 for i in rows if i.get(CONFLICT_RULING) is None)}
    for d in RULINGS:
        n = sum(1 for i in rows if _ruling(i) == d)
        if n or d not in (REPLACE_QUERY, FIX_PLAN_ITEM):
            rulings[d] = n
    kinds = {k: sum(1 for r in rows if r.get(CONFLICT_KIND) == k) for k in DIV_KINDS}
    unset = sum(1 for r in rows if not r.get(CONFLICT_KIND))
    if unset:
        kinds[UNSET] = unset
    return rulings, kinds


def materials(returns: dict) -> tuple[dict, str]:
    """判定の judgment の隣の素材の状態と、読めなかった訳（読めれば ""。無い・読めない時は素材 0 と数える）"""
    jf = as_dict(judged(returns)).get("judgment")
    if not (isinstance(jf, str) and jf):
        return {}, ""
    p = pathlib.Path(jf).with_name(MATERIALS_FILE)
    try:
        doc = read_json(p)
    except (OSError, ValueError) as e:
        return {}, f"素材の状態 {p} が読めない（測れていない素材は無いと数えた）: {report._one_line(e)}"
    if not isinstance(doc, dict):
        return {}, f"素材の状態 {p} がオブジェクトでない（測れていない素材は無いと数えた）"
    return doc, ""


def unmeasured(returns: dict) -> dict:
    """今の周に測れていない素材 {名: status}"""
    doc, _ = materials(returns)
    return {n: m["status"] for n, m in doc.items() if isinstance(m, dict) and m.get("status") in UNMEASURED}


def _material_row(name: str, status: str) -> dict:
    return {"where": f"{MATERIAL_WHERE} {name}", "text": f"素材 '{name}' が {status}（run の中で測れていない確かめ。人が手元で確かめる）"}


def _is_material_row(row: dict) -> bool:
    return str(row.get("where") or "").startswith(f"{MATERIAL_WHERE} ")


def _eye_rows(returns: dict) -> list:
    """独立の目の残り（元 rest_outside_validator の目の行と exit_problem）: 目ごとの阻害と確かめられない目。目のブロックが ok で
    ないのに数えた目が 1 つも無ければ、ok でないことを 1 行（深さで省いた目は数えないので、省かれた目だけの ok: false を黙らせない）"""
    eyes = returns.get("eyes")
    if not isinstance(eyes, dict):
        return []
    rows = []
    for name in EYE_NAMES:
        e = eyes.get(name)
        if isinstance(e, dict) and e.get("status") in EYE_STATUS_LEFT:
            label = name.upper()
            rows.append({"where": f"{report.EYES_WHERE} {label}",
                         "text": f"{label} が {e['status']}: {report._one_line(e.get('reason') or '理由なし')}"})
    if eyes.get("ok") is False and not rows:
        rows.append({"where": report.EYES_WHERE,
                     "text": "独立の目のブロックが ok でない: 目ごとの返り（r1〜r4）に阻害も確かめられない目も無い"})
    return rows


def _after_rows(returns: dict) -> list:
    """直した後の構造の実測が見た、住処の外の知る場所の増え（structmark.after_rows。指し札の先のフォルダを読む）"""
    p = as_dict(returns.get("eyes")).get("structure_after")
    return structmark.after_rows(pathlib.Path(p).parent) if isinstance(p, str) and p else []


def residue(returns: dict) -> list:
    """fixed を名乗らせない残りの行 [{where, text}]（元 rest_outside_validator の行の形）。R4 の questions は残りでない
    （人が決めることの節に出す）。深さで省いた目（null）は数えない"""
    rows = []
    final = returns.get("test-gate-final")
    if isinstance(final, dict) and (final.get("ok") is not True or final.get("green") is not True):
        rows.append({"where": "最後のテスト", "text": f"最後のテストが緑でない・認証できない（ok {final.get('ok')}・green {final.get('green')}・"
                                                 f"赤の原因 {final.get('red_cause') or '—'}）"})
    seal = returns.get("merge-seal")
    if isinstance(seal, dict) and seal.get("ok") is not True:
        rows.append({"where": "封じ", "text": f"差分を封じていない（merge-seal の ok {seal.get('ok')}）"})
    rows += _eye_rows(returns)
    fix = returns.get("fix")
    if isinstance(fix, dict):
        for u in fix.get("units") or []:
            if isinstance(u, dict) and u.get("status") in FIX_STATUS_LEFT:
                rows.append({"where": f"修正 {u.get('unit_id')}",
                             "text": f"単位 {u.get('unit_id')} が {u['status']}: {report._one_line(u.get('reason') or '理由なし')}"})
        if fix.get("done") is False:
            rows.append({"where": "修正", "text": "修正の段が直し終えていない（done が false）"})
        if as_dict(fix.get("delta_review")).get("pass") is False:
            rows.append({"where": "差分の審査", "text": "差分の審査が通っていない（delta_review.pass が false）"})
    rows += _after_rows(returns)
    rows += [_material_row(n, s) for n, s in unmeasured(returns).items()]
    return rows


def unknown_answers(gates: dict) -> list:
    out = []
    for gid in GATES:
        g = gates.get(gid)
        if isinstance(g, dict) and g.get("decision") not in (*PASS_WORDS, *STOP_WORDS):
            out.append(f"関所 {gid} の知らない答えの語 {g.get('decision')!r}（通す語 {'・'.join(PASS_WORDS)}・止める語 {'・'.join(STOP_WORDS)}）")
    return out


def _stop_reasons(returns: dict) -> list:
    return [(rid, r["stop_reason"]) for rid, r in returns.items() if isinstance(r, dict) and isinstance(r.get("stop_reason"), str)
            and r["stop_reason"]]


def _human_stop(returns: dict, gates: dict) -> tuple:
    """1. 人の止め: 関所の止める語か、返りの stop_reason が human:・request: で始まる。文が request: で始まれば止め札"""
    for gid in GATES:
        g = gates.get(gid)
        if isinstance(g, dict) and g.get("decision") in STOP_WORDS:
            word = "stopped_by_request" if str(g.get("text") or "").startswith(report.REQUEST_BY) else "stopped_by_human"
            return word, f"{gid}:{g['decision']}"
    for rid, sr in _stop_reasons(returns):
        if sr.startswith(report.REQUEST_BY):
            return "stopped_by_request", f"{rid}:{sr}"
        if sr.startswith(report.HUMAN_BY):
            return "stopped_by_human", f"{rid}:{sr}"
    return ()


def _line_stop(returns: dict) -> str:
    """2. 線の止め: stopby の語（人待ちの語を除く）・事前審査の往復が進まない・計画が諦めた・封じと置きが ok でない"""
    for rid, sr in _stop_reasons(returns):
        if stopby.is_line(sr) and sr not in WAIT_WORDS:
            return f"{rid}:{sr}"
    if as_dict(plan_reviewed(returns)).get("stalled") is True:
        return f"plan-review:{stopby.PLAN_CONVERGE}"
    if plan_gave_up(returns):
        sr = planned(returns).get("stop_reason")
        return f"plan:{sr if isinstance(sr, str) and sr else GIVE_UP}"
    for rid in ("merge-seal", "merge-apply"):
        if isinstance(returns.get(rid), dict) and returns[rid].get("ok") is False:
            return f"{rid}:{NOT_OK}"
    return ""


def plan_gave_up(returns: dict) -> bool:
    """計画が直す単位を受けたのに修正案を出せなかった（受け付けが 3 回とも拒んだか、行き止まりの単位が在る）"""
    plan = planned(returns)
    return bool(plan) and plan.get("ready") is False and bool(_units(returns))


def _waits(returns: dict, gates: dict) -> str:
    """3. 人待ち: 人に回した申し出・返りの人待ちの語・前提の検算の escalate・無人の run が残した修正前の問い"""
    if asked_conflicts(returns):
        return f"fix:{stopby.CONFLICT}"
    for rid, sr in _stop_reasons(returns):
        if sr in WAIT_WORDS:
            return f"{rid}:{sr}"
    if as_dict(as_dict(returns.get("eyes")).get("premise_check")).get("verdict") == "escalate":
        return "eyes:premise-escalate"
    review = plan_reviewed(returns)
    if review and review.get("ask_human") is True and gates.get("gate-before-fix") is None and returns.get("fix") is None:
        return "plan-review:ask-human"
    return ""


def _chain_cuts(returns: dict) -> list:
    """返りの続きが切れている所 [(後の段, 文)]"""
    out = []
    for before, flag, after, text in CHAIN:
        got = latest(returns, before)
        if got and (flag is None or got.get(flag) is True) and latest(returns, after) is None:
            out.append((after, text))
    return out


def _cut(returns: dict, facts: dict) -> str:
    """5. 途中で終わった: 記録で最後が誤りの節が在るか、返りの続きが切れている"""
    failed = facts.get("failed")
    if isinstance(failed, list) and failed:
        return f"{failed[0]}:{NODE_ERROR}"
    if judged(returns) is None:
        return f"judge:{CHAIN_CUT}"
    cuts = _chain_cuts(returns)
    return f"{cuts[0][0]}:{CHAIN_CUT}" if cuts else ""


def chain_notes(returns: dict) -> list:
    """返りの続きが切れている所の文（報告の「止めたか」の行）"""
    return [text for _, text in _chain_cuts(returns)]


def _no_fix(returns: dict) -> bool:
    """6. 直す物が無い: 判定が ready でなく止めの語も無いか、直す単位が 0"""
    j = judged(returns)
    return bool(j) and ((j.get("ready") is False and not j.get("stop_reason")) or not _units(returns))


def _proved(returns: dict) -> bool:
    """直したと名乗れる証: 最後のテストの ok と green が真で、差分を封じた（merge-seal の ok が真）"""
    final, seal = as_dict(returns.get("test-gate-final")), as_dict(returns.get("merge-seal"))
    return final.get("ok") is True and final.get("green") is True and seal.get("ok") is True


def decide_outcome(returns: dict, gates: dict, facts: dict) -> tuple[str, str]:
    """結末の語と止めの語。表の各行は元の docstring（works/.shared/core/report.py:672-686）の次の語に当たる:

    1. 止め札（by request:）→ stopped_by_request、関所の stop・reject（by human:）→ stopped_by_human
    2. 機械の止め（by works:）→ stopped_by_line（元は盤面の state.stop.by。ここは返りの stop_reason と、往復の止まり・計画の諦め・
       封じの失敗を返りの欄で読む）
    3. 人に聞いたまま（pending_human）か食い違いの申し出を人に回した（conflict.asked）→ needs_human（元は盤面の pending_human。
       ここは返りの人待ちの語・前提の検算の escalate・関所が開かなかった修正前の問い）
    4. 関所が通らない（accepted か round_closed が偽）→ record_invalid（元は検証器の関所。ここは始めの記録が読めない・
       record_problems が在る）
    5. 元に無い: 途中で終わった → interrupted（記録の落ちた節か、返りの続きの切れ目 CHAIN）
    6. 直す物が無い周 → no_fix_needed
    7. 残りが測れていない素材の行だけで最後のテストが緑 → fixed_needs_check、ほかの残り → round_limit
    8. 他 → fixed。fixed・fixed_needs_check は最後のテストの ok と green と封じの ok が真の時だけ（_proved。返りが無ければ
       続きの切れ目、欄が真でなければ残りの行が先に拾う）"""
    returns = returns or {}
    gates = gates or {}
    facts = facts or {}
    stopped = _human_stop(returns, gates)
    if stopped:
        return stopped
    line = _line_stop(returns)
    if line:
        return "stopped_by_line", line
    wait = _waits(returns, gates)
    if wait:
        return "needs_human", wait
    if not facts.get("start_ok") or facts.get("record_problems"):
        return "record_invalid", f"{'start' if not facts.get('start_ok') else 'report'}:{RECORD_INVALID}"
    cut = _cut(returns, facts)
    if cut:
        return "interrupted", cut
    if _no_fix(returns):
        return "no_fix_needed", ""
    left = residue(returns)
    if left and all(_is_material_row(r) for r in left) and _proved(returns):
        return "fixed_needs_check", ""
    if left or not _proved(returns):
        return "round_limit", ""
    return "fixed", ""
