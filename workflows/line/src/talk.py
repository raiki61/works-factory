"""設計の相談（対話モードの run の計画の往復の末尾。docs/design/line.md の 3.1 節。issue #822）。

対話モードは入力 design_talk が true で無人でない run（新しい旗は足さない）。計画の往復 plan-rounds の本体を
design-turn → plan → plan-review-run → plan-out → design-talk → gate-design（wait。本体の唯一の終わり）にし、往復が止まる周
（plan-out の done）で設計案と事前審査の結果を人に見せる。答えは止めた Archon（a972888a）の形のまま、次の周の頭の design-turn が
$LOOP_PREV.gate-design.output で読む（ASF の archon-plan・archon-attention と同じ。until_bash は飛びうる関所の出力を読まず、
design-talk の done だけを読む）。

- 合意（GO_WORDS）: 次の周は plan も事前審査も回さず、design-talk が前の周の返りを写して done にし、答えを agreed に置く。修正前の
  承認ノードは agreed を受けて、合意した行を聞き直さない（src.gates.before_fix）
- 修正要望（answer.REVISE と一言）: 一言を往復の記録の最後の往復に人の中央の block として差し込み（src.rounds.ask_again）、全部の項目を
  開き直した記録と、それを持つ plan の prior を書く。次の周の plan はその block に答え、事前審査が消えたか残ったかを照らす。一言は
  依頼の答えの行（ASK_NAME）としても plan と事前審査に渡す（往復の無い記録・計画の失敗の周にも届く）。一言が空なら設計し直さずに
  同じ文で聞き直す（未回答を承認と読まない。計画を回さずにループの周を使うので EMPTY_LIMIT 回まで。その次は止める）。往復の安全の上限（rounds.LIMIT）の周の修正要望は、設計し直さずに止める（plan-converge）
- 止める（STOP_WORDS と知らない語）: 次の周は回さず done にし、答えを agreed に置く（修正前の承認ノードが human:gate-design で止める）
- 相談の結果を返す: 直す義務が無い（nothing_owed）・計画ができなかった周も、done の周なら関所を開いて訳を見せる（黙って終わらない）

通常の run（対話モードでない）は design-turn が前の周の値をそのまま運び、design-talk が plan-out の返りをそのまま写す（関所はいつも
飛ぶ。往復の返りの欄は今と同じ値で、足した欄 open・text・asked・agreed・talks は空）。

- dialogue(given) -> bool: 配る値から対話モードの run か
- turn(...) -> dict: 周の頭 design-turn の返り
- settle(...) -> dict: 周の終わり design-talk の返り
- talk_text(...) -> str: 設計の相談の承認ノードの文
"""
from __future__ import annotations

import json
from pathlib import Path

import answer
import gatemarks
import jsonfile
import oneline
import ports
import stopby

ASK_NAME = "設計の相談で人が求めた {n} 番目の直し"   # 依頼の答えの行の question（記録された方針の行の名指し）
KEY = "person-{n}"   # 往復の記録に差し込む人の block の key（converge.KEY_CHAR の字だけ）
TALK_FIELDS = ("open", "text", "asked", "agreed", "talks")   # plan-out の返りに足す欄
EMPTY_REVISE = "前の答え revise の一言が空だった（直してほしい所が分からないので設計し直していない）。直してほしい所を一言に書いて答え直す"
CAPPED_REVISE = "往復の安全の上限 {n} 周に届いたので設計し直せない（revise は止める答えと同じに扱う）"
EMPTY_LIMIT = 2   # 一言の空の revise で聞き直す回数の上限（計画を回さずにループの周を 1 つ使う。plan-rounds の max_iterations は rounds.LIMIT にこの数を足す）
EMPTY_CAPPED = "一言の空の revise が {n} 回続いたので、もう聞き直さずに止める（直してほしい所を書いて新しい run で頼み直す）"
NO_ITEMS = "- （無し）"


def dialogue(given: dict) -> bool:
    return bool(given.get("design_talk")) and not bool(given.get("unattended"))


def _obj(raw):
    got = ports.parsed(raw)
    return got if isinstance(got, dict) else None


def _read(ptr):
    """pointer の指すファイルの JSON（pointer でない・無い・読めなければ None）"""
    try:
        return json.loads(ports.file(json.dumps(ptr)).read_text(encoding="utf-8")) if isinstance(ptr, dict) else None
    except (OSError, ValueError):
        return None


def _capped(po: dict) -> bool:
    """往復の安全の上限の周か（修正要望で設計し直せない）"""
    from src import rounds
    return (po.get("round") or 0) >= rounds.LIMIT or bool(po.get("capped"))


def _empties(talks: list) -> int:
    """一言の空の revise の数（計画を回さずに使ったループの周。周の番号とループの周の差）"""
    return sum(1 for t in talks if t.get("decision") == answer.REVISE and not str(t.get("text") or "").strip())


def _pointer_or_empty(value):
    return value if isinstance(value, dict) else ""


def turn(*, answer_raw, previous_raw, last_raw, given: dict, recorded, place: Path) -> dict:
    """周の頭 design-turn。answer_raw は前の周の関所の出力（$LOOP_PREV.gate-design.output。1 周目と飛んだ周は空）、previous_raw は前の周の
    design-talk の返り、last_raw は前の周の自分の返り。返り {plan, answer, plan_prior, record, answers, recorded, asks, talks, stop_reason,
    reason}: plan はこの周に plan と事前審査を回すか、plan_prior・record はこの周の plan と事前審査と plan-out の port prior（前の周の値。
    修正要望なら差し込んだ写し）、answers・recorded は依頼の答えと記録された方針の行に人の修正要望を足した物"""
    from src import files, gates, rounds

    prev, last = _obj(previous_raw), _obj(last_raw)
    asks = [a for a in (last or {}).get("asks") or [] if isinstance(a, dict)]
    talks = [t for t in (prev or {}).get("talks") or [] if isinstance(t, dict)]
    plan_prior = (prev or {}).get("plan_prior")
    if prev is not None and not isinstance(plan_prior, dict):   # 計画ができなかった周は prior を書かないので、その周が受けた prior を使い直す
        plan_prior = (last or {}).get("plan_prior")
    record = (prev or {}).get("record")
    out = {"plan": True, "answer": None, "plan_prior": _pointer_or_empty(plan_prior), "record": _pointer_or_empty(record), "asks": asks,
           "talks": talks, "stop_reason": "", "reason": ""}
    got = ports.parsed(answer_raw)
    if got not in (None, "") and prev is not None:
        said = answer.decision(got)
        entry = {"round": prev.get("round"), "decision": said["decision"], "text": said["text"],
                 "asked": [t for t in prev.get("asked") or [] if isinstance(t, str)]}
        talks.append(entry)
        out["answer"] = entry
        out["plan"] = False
        jsonfile.write(place / files.TALK_ANSWERS, talks, parents=True)
        if said["decision"] == answer.REVISE:
            if not said["text"].strip() and _empties(talks[:-1]) >= EMPTY_LIMIT:
                out.update(stop_reason=stopby.HUMAN + gates.TALK_GATE, reason=EMPTY_CAPPED.format(n=EMPTY_LIMIT + 1))
            elif not said["text"].strip():
                out["reason"] = EMPTY_REVISE
            elif _capped(prev):
                out.update(stop_reason=stopby.word("plan-converge"), reason=CAPPED_REVISE.format(n=rounds.LIMIT))
            else:
                n = len(asks) + 1
                asks.append({"n": n, "key": KEY.format(n=n), "round": prev.get("round"), "text": said["text"]})
                out.update(plan=True, **_ask_again(place, key=KEY.format(n=n), text=said["text"], n=n, record=record, plan_prior=plan_prior))
    out["answers"] = [*_list(given.get("request_answers")), *({"question": ASK_NAME.format(n=a["n"]), "text": a["text"]} for a in asks)]
    out["recorded"] = [*_list(recorded), *({"source": "answer", "name": ASK_NAME.format(n=a["n"]), "text": a["text"]} for a in asks)]
    return out


def _list(value) -> list:
    got = ports.parsed(value) if isinstance(value, str) else value
    return [r for r in got if isinstance(r, dict)] if isinstance(got, list) else []


def _ask_again(place: Path, *, key: str, text: str, n: int, record, plan_prior) -> dict:
    """人の修正要望を往復の記録に差し込み（往復が在れば）、記録と plan の prior の写しを書いて {record, plan_prior} の pointer を返す"""
    from src import files, rounds
    out = {}
    if isinstance(record, dict):
        doc = rounds.ask_again(rounds.read(ports.file(json.dumps(record))), key=key, text=text)
        out["record"] = ports.pointer(rounds.write(place / files.PLAN_CONVERGE, doc))
        if isinstance(plan_prior, dict):
            prior = json.loads(ports.file(json.dumps(plan_prior)).read_text(encoding="utf-8"))
            written = jsonfile.write(place / files.PLAN_TALK.format(n=n), {**prior, "record": doc}, parents=True)
            out["plan_prior"] = ports.pointer(written)
    return out


def settle(*, turn_got: dict, plan_out: dict | None, previous: dict | None, given: dict, materials, run_id: str) -> dict:
    """周の終わり design-talk。turn_got は design-turn の返り、plan_out は plan-out の返り（回さなかった周は None）、previous は前の周の
    design-talk の返り、materials は修正前の承認ノードの材料を読む口（rounds → before_fix の材料。src.asking.materials を包んだ物）。
    返りは plan-out の返りの欄と TALK_FIELDS"""
    from src import gates

    if turn_got.get("plan"):
        if plan_out is None:   # plan の include が落ちて plan-out が飛んだ: 計画ができなかった形で止める（輪を落とさない）
            return {**failed(), **talk_fields(turn_got)}
        out = {**plan_out, **talk_fields(turn_got)}
        if not dialogue(given) or not plan_out.get("done"):
            return out
        consult = _consult_row(plan_out)
        doc = None
        if consult:
            items = [(gatemarks.DESIGN_ONLY_KIND, consult)]
        else:
            kw = materials(plan_out)
            doc = kw["record_doc"]
            items = gates.before_fix(plan_out, unattended_run=False, design=False, **kw)["items"]
        text = talk_text(plan_out, items, run_id=run_id, consult=bool(consult), doc=doc)
        return {**out, "done": False, "open": True, "text": text, "asked": [t for _, t in items]}
    base = {k: v for k, v in (previous or failed()).items() if k not in TALK_FIELDS}
    said = turn_got.get("answer") or {}
    if turn_got.get("stop_reason"):   # 上限の周の修正要望・空の revise の続き・周の頭の落ち: 設計し直さずに止める
        why = "。".join(t for t in (str(turn_got.get("reason") or ""), f"人の一言: {said['text']}" if said.get("text") else "") if t)
        return {**base, **talk_fields(turn_got), "done": True, "stop_reason": turn_got["stop_reason"],
                "agreed": {**said, "text": why} if said else None}
    if said.get("decision") == answer.REVISE:   # 一言の空の修正要望: 同じ文で聞き直す
        again = str((previous or {}).get("text") or "").removeprefix(f"{EMPTY_REVISE}\n\n")
        return {**base, **talk_fields(turn_got), "done": False, "open": True, "text": f"{turn_got.get('reason')}\n\n{again}",
                "asked": list((previous or {}).get("asked") or [])}
    return {**base, **talk_fields(turn_got), "done": True, "agreed": said or None}


def talk_fields(turn_got: dict) -> dict:
    """TALK_FIELDS の閉じた値（関所を開かない周の欄。talks は周の頭が運んだ物）"""
    return {"open": False, "text": "", "asked": [], "agreed": None, "talks": list(turn_got.get("talks") or [])}


def failed() -> dict:
    """計画ができなかった形の plan-out の返り（plan-out の落ちた時・plan-out が飛んだ周・design-talk の落ちた時。欄の名の正本）"""
    from src import guard
    return {"done": True, "ok": False, "status": "failed", "round": 0, "plan_prior": None, "record": None, "plan": None, "fix_plan": None,
            "reply": None, "handoffs": [], "ripple": None, "owed": [], "gave_up": None, "stalled": False, "capped": False, "review": None,
            "asks": [], "deviations": [], "review_status": "", "review_reason": "", "stop_reason": guard.LINE_SCRIPT}


def _consult_row(po: dict) -> str:
    """直す義務が無い・計画ができなかった周の相談の結果の行（修正前の承認ノードが開かずに修正へ進まない周。ほかは空）"""
    from src import gates
    if po.get("status") == "nothing_owed":
        return f"相談の結果: 直す義務の単位が無い（{po.get('status')}）。合意すると修正へ進まずに報告を出す"
    if not po.get("ok") and not po.get("stalled") and not gates.review_fell_row(po):
        why = po.get("review_reason") or po.get("stop_reason") or "訳が返っていない"
        return f"相談の結果: 設計案を作れなかった（{po.get('status') or 'failed'}）: {why}。合意すると修正へ進まずに報告を出す"
    return ""


def plan_lines(po: dict) -> list:
    """設計案の行（修正案の項目ごとに、単位・やり方・書く所）。案の控えが無い・読めなければその訳の 1 行"""
    bare, fields = _read(po.get("fix_plan")), _read(po.get("plan"))
    items = bare.get("plan") if isinstance(bare, dict) else None
    if not isinstance(items, list) or not items:
        return ["- （設計案の控えが無い。下の相談の結果を見る）"]
    works = fields.get("fields") if isinstance(fields, dict) and isinstance(fields.get("fields"), list) else []
    out = []
    for n, it in enumerate(items, 1):
        it = it if isinstance(it, dict) else {}
        w = works[n - 1] if n <= len(works) and isinstance(works[n - 1], dict) else {}
        units = "、".join(str(k) for k in it.get("unit_keys") or [])
        out.append(f"- 項目 {n}（{units}）: {oneline.one_line(str(it.get('approach') or '（やり方が無い）'))}")
        if w.get("allowed_paths") or w.get("route"):
            out.append(f"  - 書く所: {'・'.join(str(p) for p in w.get('allowed_paths') or []) or '（無い）'}・直し方: {w.get('route') or '（無い）'}")
    return out


def _record(po: dict) -> dict:
    from src import rounds
    try:
        return rounds.read(ports.file(json.dumps(po["record"]))) if isinstance(po.get("record"), dict) else rounds.fresh()
    except ValueError:
        return rounds.fresh()


def review_lines(po: dict, doc: dict) -> list:
    """事前審査の結果の行（往復の記録 doc の報告の行と、最後の往復の block の穴）"""
    from src import rounds
    if not doc["passes"]:
        status = po.get("review_status") or "（回っていない）"
        return [f"- 事前審査の往復の記録が無い（事前審査の状態: {status}" + (f"。訳: {po['review_reason']}" if po.get("review_reason") else "") + "）"]
    out = [f"- {line.strip()}" for line in rounds.lines(doc)]
    out += [f"- 最後の往復の block {f.get('key')}（{f.get('kind')}）: {oneline.one_line(str(f.get('why') or ''))}"
            for f in doc["passes"][-1].get("faces") or []]
    return out


def talk_text(po: dict, items: list, *, run_id: str, consult: bool, doc: dict | None = None) -> str:
    """設計の相談の承認ノードの文: 冒頭 3 行 → 設計案 → 事前審査の結果 → 人が決める項目（合意で修正前に聞き直さない行）→ 答え方"""
    from src import gates, rounds
    k = po.get("round")
    doc = doc if isinstance(doc, dict) and isinstance(doc.get("passes"), list) else _record(po)   # 材料が読んだ往復の記録（無ければ読む）
    texts = [t for _, t in items]
    lines = gatemarks.head3(
        f"設計の相談の承認ノード（{gates.TALK_GATE}）が開いた。計画の周 {k} の設計案と事前審査の結果を見せる"
        + ("（相談の結果だけ。修正へは進まない）" if consult else ""),
        "この設計で修正・試験・レビューへ進めてよいか（合意）、直してほしい所を一言に書いて設計し直させるか、止めるか（打つ行は末尾の答え方）",
        gatemarks.push_of(texts) if texts else
        f"人が決める項目は無い。事前審査の抜け方は {rounds.WORDS.get(doc.get('outcome'), 'まだ無い')}") + [""]
    lines += [f"設計案（計画の周 {k}）:", *plan_lines(po), "", "事前審査の結果:", *review_lines(po, doc), ""]
    lines += [f"人が決める項目（{len(texts)} 件。合意すると修正前の承認ノードでは聞き直さない）:", *([f"- {t}" for t in texts] or [NO_ITEMS]), ""]
    lines += ["答え方（依頼者に聞いて、その言葉で答える。答えるまで run は待つ）:",
              f"- 合意して進める: {answer.line(run_id, 'continue', '<通す範囲と条件>')}（一言は run の記録 {gates.TALK_GATE} と修正前の答えに"
              "残り、修正役に届く。条件が無ければ approve でもよい）",
              (f"- 設計し直させる: {answer.line(run_id, answer.REVISE, '<直してほしい所>', verbs=(*answer.VERBS, answer.REVISE))}（一言を事前審査の block として計画の役に返し、"
               "事前審査をやり直して、もう一度ここで聞く。一言が空なら聞き直す）") if not _capped(po) else
              f"- 設計し直させる: できない（{CAPPED_REVISE.format(n=rounds.LIMIT)}）",
              f"- 止める: {answer.line(run_id, 'stop', '<理由>')}（報告は出る）"]
    if any(kind in gatemarks.ASK_KINDS for kind, _ in items):   # 台帳の問いは合意の一言で答える（修正前の答えとして台帳が読む）
        lines += [f"- {gatemarks.ASK_GATE_HEAD}"]
    return "\n".join(lines) + "\n"
