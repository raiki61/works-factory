"""結末の語の決め方（docs/design.md の lib/outcome「決め方だけを持つ」）。語の正本は報告のブロックの返す節の enum で、
ここは report.OUTCOMES の 10 語のどれを返すかだけを決める。

元は works/.shared/core/report.py:670 の decide_outcome（盤面 b と検証器の関所 gate を読んだ）。ここでは盤面の代わりに
ブロックの返り（returns）・人の関所の答え（gates）・報告が集めた事実（facts）を引数で受ける。順は元の docstring の順を写し、
元に無い「途中で終わった」（interrupted）を 5 に置く。

- returns: 差し込んだブロックの id → 返りの dict か None（飛ばされた・落ちた・読めない）。指し札の欄は開けたファイルのパスの字
  （開けなければ None）。conflicts だけは段ごとのパスの配列もよい
- gates: 関所の id → {decision, text} か None（開かなかった）
- facts: {start_ok, record_problems, failed, absorbed, answers, stops}。failed は run の記録で落ちて、線が受け止めると宣言した段の
  外の節の id の並び（記録が読めなければ空）、absorbed は宣言した段の中で落ちた節 [{node, error}]、answers は依頼の answers（始めの
  記録の欄）、stops は線の節が返した止めの語 [(節の id, 語)]（線の collect が集めた物。入口の拒み・無人の関所の止め・線の script の
  例外・人の止め）。record_problems は record_problems() の返り
- decide_outcome(returns, gates, facts) -> (結末の語, stop_reason)。stop_reason は「<段の id>:<語>」、止まらなければ ""
- record_problems(returns, gates, *, unread, unopened) -> (結果を名乗れない訳, 注意): 入力の読めなかった訳・開けなかった指し札・
  申し出と裁定の読めなかった訳・知らない答えの語を、結果を名乗らせない物と注意に分ける
- residue(returns, facts) -> fixed を名乗らせない残りの行 [{where, text}]（報告と次の依頼が同じ行を読む）
- conflict_rows(returns)・asked_conflicts(returns, closed)・waiting_conflicts(returns)・conflict_counts(returns): 申し出と裁定の行・
  人に回した行・案の直しを待つ行・裁定と種類の内訳
- materials(returns)・unmeasured(returns)・answers_ledger(returns, answers)・measured_materials(returns, answers): 判定の隣の素材の
  状態と、今の周に測れていない素材 {名: status}と、依頼の答えを当てる台帳の見え方と、そのうち依頼の答えが命令と出力つきで答えた素材
- judgment_doc(returns)・questions(returns)・ledger(returns)・answer_binds(questions, answer, missing)・origin_of(question, missing):
  判定の judgment.json の中身と問いの台帳の全部と
  人に聞く状態の問いと、依頼の答えの当て方
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
import conflict  # noqa: E402
import fixbeside  # noqa: E402
import fixboard  # noqa: E402
import gatemarks  # noqa: E402
import replan  # noqa: E402
import report  # noqa: E402
import seal  # noqa: E402
import stopby  # noqa: E402
import structmark  # noqa: E402

OK_OUTCOMES = ("fixed", "fixed_needs_check", "no_fix_needed")   # 返す節の ok が true になる結末（docs/design.md の report の返り）
GATES = ("gate-start", "gate-before-fix", "gate-replan", "gate-final")
STOP_WORDS = answer.STOP_WORDS
PASS_WORDS = answer.GO_WORDS
WAIT_WORDS = stopby.WAITING
NOT_CLOSED = "直したと申告したが、機械が判定の問いで数え直すと閉じていない"   # 元 report._closed_units が残りから外さなかった単位
EYE_STATUS_LEFT = (seal.REDESIGN, seal.UNVERIFIABLE)
EYE_NAMES = tuple(e.lower() for e in report.EYES)
MISSING_EYE = "の結果が無い——再実行の要あり（深さは標準で、省いていない）"   # 元 rest_outside_validator の missing の行
GIVE_UP = "give-up"
NOT_OK = "not-ok"
NODE_ERROR = "node-error"
CHAIN_CUT = "chain-cut"
RECORD_INVALID = "record-invalid"
# 開けないと結果を名乗れない指し札 (段, 欄)。申し出と裁定が読めないと、人に回した申し出が見えなくなる
MUST_OPEN = (("fix", "conflicts"),)

# fix の conflicts の先（今の works の conflicts.json の包み）を読む欄の名と語と行の述語は lib/conflict.py の物を引く（S34。写さない）
# 案の直しを待つ行の締め（元 works/.shared/core/replan.py:99-101）。途中で落ちた run は締めずに次の依頼へ未完了で運ぶ
CLOSE_WHY = replan.CLOSE_WHY
PENDING_WHY = replan.PENDING_WHY

# 判定の judgment の隣の素材の測りの状態 {<素材の名>: {status, …}}（docs/design.md の「書き方の決め」の名指しの隣のファイル）。
# 測れていない status は元の写しの検証器の STATUS で阻害になる物（gatemarks.unmeasured。works/.shared/core/gatemarks.py:708-716）
MATERIALS_FILE = gatemarks.MATERIALS_FILE
UNMEASURED = gatemarks.UNMEASURED
MATERIAL_WHERE = "素材"

# 返りの続き (前の段, 前の段の欄（None は返りが在るだけ）, 後の段, 文)。前の段が欄を真にしたのに後の段の出力が無い run は途中で終わった
CHAIN = (("judge", "ready", "plan", "判定が直す単位を出したのに計画の出力が無い"),
         ("plan", "ready", "fix", "計画が修正案を出したのに修正の出力が無い"),
         ("fix", None, "test-gate-final", "修正の段が走ったのに最後のテストの出力が無い"),
         ("test-gate-final", "ok", "merge-seal", "最後のテストが通ったのに差分を封じた出力が無い"))


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


def fix_folders(returns: dict) -> list:
    """修正の段ごとの置き場（fix の返りの diffs の先のフォルダ。1 回目と 2 度目の修正の順。diffs の無い返りは diff の先）"""
    fix = as_dict(returns.get("fix"))
    return [pathlib.Path(p).parent for p in paths(fix.get("diffs") if "diffs" in fix else fix.get("diff"))]


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
            items = doc.get(conflict.ITEMS) if isinstance(doc, dict) else None
            if not isinstance(items, list):
                raise ValueError(f"欄 {conflict.ITEMS} の配列が無い")
        except (OSError, ValueError) as e:
            notes.append(f"申し出と裁定のファイル {p} が読めない: {report._one_line(e)}")
            continue
        rows += [i for i in items if isinstance(i, dict)]
    return rows, notes


def waiting_conflicts(returns: dict) -> list:
    """案の直しを待つ行（conflict.waiting_rows）"""
    return conflict.waiting_rows(conflict_rows(returns)[0])


def asked_conflicts(returns: dict, closed: bool = True) -> list:
    """人に諮る申し出の行（conflict.asked_rows）。closed（途中で落ちていない run）なら、案の直しを待つ行も諦めた行として足す
    （元 report.build が先に replan.close_at で締めた形。訳は CLOSE_WHY）"""
    asked = conflict.asked_rows(conflict_rows(returns)[0])
    return asked + [{**i, conflict.REPLAN_WHY: CLOSE_WHY} for i in waiting_conflicts(returns)] if closed else asked


def asked_units(returns: dict, closed: bool = True, rows: list | None = None) -> list:
    """人に回した行（rows を渡せばその行）が外した単位ごとの (単位, 行)（元 report._asked_units と conflict.ruled_units:
    ask_human は申し出の単位、諦めた fix_plan_item はその項目に載る単位の全部）。1 単位に 1 行で、単位自身の申し出の行を先に採る"""
    rows = asked_conflicts(returns, closed) if rows is None else rows
    own, out = {}, {}
    for r in rows:
        own.setdefault(r.get("unit_key"), r)
    for r in rows:
        for k in conflict.ruled_units(r):
            if isinstance(k, str) and k:
                out.setdefault(k, own.get(k, r))
    return list(out.items())


def conflict_counts(returns: dict) -> tuple[dict, dict]:
    """(裁定の内訳, 種類の内訳)（conflict.counts_of・kind_counts_of）"""
    rows, _ = conflict_rows(returns)
    return conflict.counts_of(rows), conflict.kind_counts_of(rows)


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
    return gatemarks.unmeasured_of(doc)


def judgment_doc(returns: dict) -> dict:
    """判定（再審が在ればその）の judgment.json の中身（読めない・無ければ空）"""
    jf = as_dict(judged(returns)).get("judgment")
    try:
        return as_dict(read_json(jf) if isinstance(jf, str) and jf else {})
    except (OSError, ValueError):
        return {}


def questions(returns: dict) -> list:
    """判定の judgment の問いの台帳の全部（読めない・無ければ空。依頼の答えはこの全部に当てる）"""
    qs = judgment_doc(returns).get("questions")
    return [q for q in qs if isinstance(q, dict)] if isinstance(qs, list) else []


def ledger(returns: dict) -> list:
    """問いの台帳のうち人に聞く状態の問い"""
    return [q for q in questions(returns) if q.get("status") in gatemarks.ASKING]


def origin_of(q: dict, missing: dict) -> str:
    """問いの出どころ（gatemarks.origin。missing は測れていない素材）"""
    return gatemarks.origin(q, missing)


def answer_binds(questions: list, a: dict, missing: dict) -> list:
    """依頼の答え a が当たる問い（gatemarks.binds。判定の結びはここでは当てない——結びを当てる読みは runreport.ledger）"""
    return gatemarks.binds(a, questions, missing=missing)


def answers_ledger(returns: dict, answers) -> "gatemarks.Ledger":
    """判定の問いの台帳と素材の状態に依頼の答え answers を当てる値の見え方（gatemarks.ledger。結びはここでは当てない——結びを当てる
    読みは runreport.ledger）。素材の当ての式は gatemarks.material_answer・measured_materials の 1 か所"""
    doc, _ = materials(returns)
    return gatemarks.ledger(judgment_doc(returns), answers=answers or [], materials=doc)


def measured_materials(returns: dict, answers) -> set:
    """依頼の答えが命令と出力つきで答えた、今の周に測れていない素材の名（gatemarks.measured_materials。残りに数えない。
    実測とは書かず、人が手元で確かめたと名乗る）"""
    return gatemarks.measured_materials(answers_ledger(returns, answers))


def _material_row(name: str, status: str) -> dict:
    return {"where": f"{MATERIAL_WHERE} {name}", "text": f"素材 '{name}' が {status}（run の中で測れていない確かめ。人が手元で確かめる）"}


def _is_material_row(row: dict) -> bool:
    return str(row.get("where") or "").startswith(f"{MATERIAL_WHERE} ")


def _eye_rows(returns: dict, eyes_skip=None) -> list:
    """独立の目の残り（元 rest_outside_validator の目の行と exit_problem）: 目ごとの阻害と確かめられない目と、直した後の深さが標準
    （eyes_skip が空の字。線の redepth の skip_optional）なのに返りの無い目（元 eye_counts の missing。深さで省いた目は数えない。深さの
    返りが届かない run（eyes_skip が None）は省いた目と分けられないので数えない）。目のブロックが ok でないのに数えた目が 1 つも
    無ければ、ok でないことを 1 行（深さで省いた目は数えないので、省かれた目だけの ok: false を黙らせない）"""
    eyes = returns.get("eyes")
    if not isinstance(eyes, dict):
        return []
    rows = []
    for name in EYE_NAMES:
        e = eyes.get(name)
        label = name.upper()
        if isinstance(e, dict) and e.get("status") in EYE_STATUS_LEFT:
            rows.append({"where": f"{report.EYES_WHERE} {label}",
                         "text": f"{label} が {e['status']}: {report._one_line(e.get('reason') or '理由なし')}"})
        elif e is None and eyes_skip == "":
            rows.append({"where": f"{report.EYES_WHERE} {label}", "text": f"{label} {MISSING_EYE}"})
    if eyes.get("ok") is False and not rows:
        rows.append({"where": report.EYES_WHERE,
                     "text": "独立の目のサブグラフが ok でない: 目ごとの出力（r1〜r4）に阻害も確かめられない目も無い"})
    return rows


def _after_rows(returns: dict) -> list:
    """直した後の構造の実測が見た、住処の外の知る場所の増え（structmark.after_rows。指し札の先のフォルダを読む）"""
    p = as_dict(returns.get("eyes")).get("structure_after")
    return structmark.after_rows(pathlib.Path(p).parent) if isinstance(p, str) and p else []


def _include(step: str) -> str:
    head, sep, _ = str(step).partition("__")
    return head if sep else ""


def absorbed_rows(returns: dict, absorbed) -> list:
    """落ちたが線が受け止めて先へ進んだ節の残りの行（元 report.absorbed_rows。その段が見るはずだった物は確かめていない）。返りの
    在るブロックの中の落ちは、そのブロックが返りで言うので重ねない（元の seen）"""
    return [{"where": f"{report.ABSORBED_WHERE} {a.get('node')}",
             "text": f"{a.get('node')} が落ちた（誤り: {report._first_error(a)}）——メイングラフは受け止めて先へ進んだが、その段の結果は確かめていない（再実行の要あり）"}
            for a in absorbed or [] if isinstance(a, dict) and not isinstance(returns.get(_include(a.get("node"))), dict)]


def residue(returns: dict, facts: dict | None = None) -> list:
    """fixed を名乗らせない残りの行 [{where, text}]（元 rest_outside_validator の行の形）。R4 の questions は残りでない
    （人が決めることの節に出す）。深さで省いた目（null）は数えない。facts の answers が命令と出力つきで答えた測れていない素材は
    数えず（元 residue の measured_materials）、facts の absorbed（受け止めた落ち）を数え、facts の eyes_skip（直した後の深さの
    省く理由。標準なら空）が空なら返りの無い目を数える。facts の beside（修正の diff の隣のファイルの fixbeside.read の返り）が
    在れば読み直さない。封じの ok は残りに数えない（読み手は _proved の docstring）"""
    facts = facts or {}
    rows = []
    final = returns.get("test-gate-final")
    if isinstance(final, dict) and (final.get("ok") is not True or final.get("green") is not True):
        rows.append({"where": "最後のテスト", "text": f"最後のテストが緑でない・認証できない（ok {final.get('ok')}・green {final.get('green')}・"
                                                 f"赤の原因 {final.get('red_cause') or '—'}）"})
    rows += _eye_rows(returns, facts.get("eyes_skip"))
    fix = returns.get("fix")
    if isinstance(fix, dict):
        for u in fix.get("units") or []:
            if isinstance(u, dict) and u.get("status") in fixboard.UNIT_LEFT:
                rows.append({"where": f"修正 {u.get('unit_id')}",
                             "text": f"単位 {u.get('unit_id')} が {u['status']}: {report._one_line(u.get('reason') or '理由なし')}"})
        left = {u.get("unit_id") for u in fix.get("units") or [] if isinstance(u, dict) and u.get("status") in fixboard.UNIT_LEFT}
        beside = facts.get("beside") or fixbeside.read(fix_folders(returns))
        for k in fixbeside.not_closed(beside):   # 元 report._closed_units: 申告しても表で閉じていない
            if k not in left:
                rows.append({"where": f"修正 {k}", "text": f"単位 {k} が閉鎖の表で閉じていない（{NOT_CLOSED}）"})
        rows += [{"where": "修正", "text": line} for line in beside["closure_unread"]]   # 読めない表を閉じたと数えない
        if fix.get("done") is False:
            rows.append({"where": "修正", "text": "修正の段が直し終えていない（done が false）"})
        if as_dict(fix.get("delta_review")).get("pass") is False:
            rows.append({"where": "差分の審査", "text": "差分の審査が通っていない（delta_review.pass が false）"})
    rows += _after_rows(returns)
    checked = measured_materials(returns, facts.get("answers"))
    rows += [_material_row(n, s) for n, s in unmeasured(returns).items() if n not in checked]
    rows += absorbed_rows(returns, facts.get("absorbed"))
    return rows


def unknown_answers(gates: dict) -> list:
    out = []
    for gid in GATES:
        g = gates.get(gid)
        if isinstance(g, dict) and g.get("decision") not in (*PASS_WORDS, *STOP_WORDS):
            out.append(f"承認ノード {gid} の知らない答えの語 {g.get('decision')!r}（通す語 {'・'.join(PASS_WORDS)}・止める語 {'・'.join(STOP_WORDS)}）")
    return out


def stop_reasons(returns: dict, facts: dict | None) -> list:
    """止めの語 [(段か線の節の id, 語)]: ブロックの返りの stop_reason と、facts の stops（線の節の止めの語）"""
    got = [(rid, r["stop_reason"]) for rid, r in returns.items() if isinstance(r, dict) and isinstance(r.get("stop_reason"), str)
           and r["stop_reason"]]
    return got + [(str(node), word) for node, word in as_dict(facts).get("stops") or () if isinstance(word, str) and word]


def _human_stop(returns: dict, gates: dict, facts: dict | None) -> tuple:
    """1. 人の止め: 関所の止める語か、返りの stop_reason が human:・request: で始まる。文が request: で始まれば止め札"""
    for gid in GATES:
        g = gates.get(gid)
        if isinstance(g, dict) and g.get("decision") in STOP_WORDS:
            word = "stopped_by_request" if str(g.get("text") or "").startswith(report.REQUEST_BY) else "stopped_by_human"
            return word, f"{gid}:{g['decision']}"
    for rid, sr in stop_reasons(returns, facts):
        if sr.startswith(report.REQUEST_BY):
            return "stopped_by_request", f"{rid}:{sr}"
        if sr.startswith(report.HUMAN_BY):
            return "stopped_by_human", f"{rid}:{sr}"
    return ()


def _line_stop(returns: dict, facts: dict | None) -> str:
    """2. 線の止め: stopby の語（人待ちの語を除く。線の節の語も）・事前審査の往復が進まない・計画が諦めた・封じと置きが ok でない"""
    for rid, sr in stop_reasons(returns, facts):
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


def _waits(returns: dict, gates: dict, closed: bool, facts: dict | None) -> str:
    """3. 人待ち: 人に回した申し出（closed なら締めた案の直しの行も）・返りの人待ちの語・前提の検算の escalate・無人の run が
    残した修正前の問い"""
    if asked_conflicts(returns, closed):
        return f"fix:{stopby.CONFLICT}"
    for rid, sr in stop_reasons(returns, facts):
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
        if after == "merge-seal" and returns.get("fix") is None:   # 直す物が無い周（L-W07）は差分が無いので封じない
            continue
        got = latest(returns, before)
        if got and (flag is None or got.get(flag) is True) and latest(returns, after) is None:
            out.append((after, text))
    return out


def cut_at(returns: dict, failed) -> str:
    """5. 途中で終わった所の「<段>:<語>」（終わっていなければ ""）: 記録で落ちて線が進まなかった節 failed が在るか、返りの続きが
    切れている"""
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
    """直したと名乗れる証: 最後のテストの ok と green が真で、差分を封じた（merge-seal の ok が真）。封じの ok の読み手は 3 つで
    役が違う: ここは結末を fixed と名乗れるか、_line_stop は ok: false を線の止めにするか、runreport._stop_lines は ok でない訳を
    報告に出すか"""
    final, seal = as_dict(returns.get("test-gate-final")), as_dict(returns.get("merge-seal"))
    return final.get("ok") is True and final.get("green") is True and seal.get("ok") is True


def decide_outcome(returns: dict, gates: dict, facts: dict) -> tuple[str, str]:
    """結末の語と止めの語。表の各行は元の docstring（works/.shared/core/report.py:672-686）の次の語に当たる:

    1. 止め札（by request:）→ stopped_by_request、関所の stop・reject（by human:）→ stopped_by_human
    2. 機械の止め（by works:）→ stopped_by_line（元は盤面の state.stop.by。ここは返りの stop_reason と線の節の止めの語 facts の stops
       と、往復の止まり・計画の諦め・封じの失敗を返りの欄で読む）
    3. 人に聞いたまま（pending_human）か食い違いの申し出を人に回した（conflict.asked）→ needs_human（元は盤面の pending_human。
       ここは返りの人待ちの語（無人の run の関所の止め works:needs-human も）・前提の検算の escalate・関所が開かなかった修正前の問い。途中で終わっていない run は、案の直しを
       待つ行も元の build の締めと同じく諦めた行として人に回す）
    4. 関所が通らない（accepted か round_closed が偽）→ record_invalid（元は検証器の関所。ここは始めの記録が読めない・
       record_problems が在る）
    5. 元に無い: 途中で終わった → interrupted（記録の落ちて線が進まなかった節か、返りの続きの切れ目 CHAIN。線が受け止めた落ちは
       ここでなく 7 の残り）
    6. 直す物が無い周 → no_fix_needed（周を締めた最後のテストと独立の目の残りが無い時。残りが在れば 7）
    7. 残り（residue。依頼の答えが命令と出力つきで答えた素材を除き、受け止めた落ちを含む）が測れていない素材の行だけで最後の
       テストが緑 → fixed_needs_check、ほかの残り → round_limit
    8. 他 → fixed。fixed・fixed_needs_check は最後のテストの ok と green と封じの ok が真の時だけ（_proved。返りが無ければ
       続きの切れ目、最後のテストの欄が真でなければ残りの行、封じの ok が false なら 2 の線の止めが先に拾う）"""
    returns = returns or {}
    gates = gates or {}
    facts = facts or {}
    stopped = _human_stop(returns, gates, facts)
    if stopped:
        return stopped
    line = _line_stop(returns, facts)
    if line:
        return "stopped_by_line", line
    cut = cut_at(returns, facts.get("failed"))
    wait = _waits(returns, gates, closed=not cut, facts=facts)
    if wait:
        return "needs_human", wait
    if not facts.get("start_ok") or facts.get("record_problems"):
        return "record_invalid", f"{'start' if not facts.get('start_ok') else 'report'}:{RECORD_INVALID}"
    if cut:
        return "interrupted", cut
    left = residue(returns, facts)
    if _no_fix(returns) and not left:   # 直す物が無い周は最後のテストと独立の目（R2）が確かめてから名乗る（L-W07）
        return "no_fix_needed", ""
    if left and all(_is_material_row(r) for r in left) and _proved(returns):
        return "fixed_needs_check", ""
    if left or not _proved(returns):
        return "round_limit", ""
    return "fixed", ""
