"""仕様の承認ノードの文を組み（ask）、答えを受けて固める（answer）。今の lib/judge_accept.py の spec_approve・spec_ask・spec_answer と
lib/specblk.py の APPROVE・GATE_STOP_NOTE・FLAG_BY_PREFIX・gate_text・parse_gate の写し（docs/design/spec.md の 1.5）。
承認ノードの文の組み立て gatemarks.gate_text は lib/ に残る物（修正前の承認ノードと共に使う）を呼ぶ。"""
from __future__ import annotations

import pathlib

import answer as answers   # lib/。GO_WORDS・STOP_WORDS
import gatemarks           # lib/
import rolekit             # lib/。輪の諦め・BoardGap
import stopby              # lib/

from src import files, freeze, take


def gate_text(asking: dict, *, run_id: str) -> str:
    return gatemarks.gate_text(asking, run_id=run_id or "<id>", node=files.APPROVE, record_name="process.spec.approval")


def parse_gate(gate):
    """承認ノードの出口（開かなかった時は null）を dict か None（開かなかった）に。形の誤りは BoardGap"""
    if gate is None:
        return None
    if isinstance(gate, str):
        raise rolekit.BoardGap(f"承認ノードの答えが JSON として読めない: {gate[:200]!r}")
    if not isinstance(gate, dict):
        raise rolekit.BoardGap(f"承認ノードの答えが JSON のオブジェクトでない: {type(gate).__name__}")
    words = answers.GO_WORDS + answers.STOP_WORDS
    decision = gate.get("decision")
    if decision not in words:
        raise rolekit.BoardGap(f"承認ノードの答えの語 {decision!r} を知らない（{' / '.join(words)}）")
    text = gate.get("text")
    text = "" if text is None else text
    if not isinstance(text, str):
        raise rolekit.BoardGap(f"承認ノードの一言が文字列でない: {type(text).__name__}")
    return {"decision": decision, "text": text}


def approve(spec, review, revise, root):
    """仕様を人に諮る問いを組む。受け入れ条件の run は走らせずに字面を見せる——走らせるのは人が字面を見て通した後（freeze）。
    返り (pending, asking): pending は承認ノードに見せた仕様（受け入れ条件ごとの今の sha256 つき）、asking は問いの形
    {node, decision, reason, kinds, in_round, question, items, options}（gate_text が文にする）"""
    root = pathlib.Path(root or ".")
    rows = [{**a, "sha256": freeze.file_sha(root, a["file"])} for a in spec["acceptance"]]
    pending = {"requirements": spec["requirements"], "acceptance": rows, "out_of_scope": spec.get("out_of_scope") or []}
    handled = {r["key"]: r for r in (revise or {}).get("handled") or []}
    items = [f"要件 {r['key']}: {r['text']}" for r in spec["requirements"]]
    items += [f"受け入れ条件 {r['key']}（要件 {r['requirement']}）: {r['file']} の {r['name']}——承認すると機械が `{r['run']}` を"
              "作業ツリーで走らせる（承認の前には走らせていない）" for r in rows]
    items += [f"審査の穴 [{f['kind']}] {f['key']}: {f['why'][:200]}——"
              + (f"{handled[f['key']]['handled']}: {handled[f['key']]['how'][:200]}" if f["key"] in handled else "答え無し")
              for f in (review or {}).get("faces") or []]
    asking = {"node": files.APPROVE, "decision": "ask", "reason": "spec_approval", "kinds": ["spec_approval"], "in_round": True,
              "question": ("仕様（要件と受け入れ条件）を承認するか。承認すると各受け入れ条件の run のコマンドを走らせて承認の時点の終了コードを取り、"
                           "受け入れ条件を記録に固定し、判定と修正案の基準にする"
                           "（continue --note <承認の言葉や条件>）。承認しないなら run をここで止める（stop）——仕様を直してから新しい run で始めよ"),
              "items": items, "options": ["continue", "stop"]}
    return pending, asking


def ask(place, root, run_id: str) -> dict:
    """承認ノードを開くか・文 {ask, message}。止めの控えが在れば開かない。どれかの役の輪が諦めた・受けた返答が足りない
    （書く・審査・穴が在るのに直す）なら開かずに works:spec で止める。開く時は approve の問いを文にし、spec-ask.json に
    {pending, asking, message} を置く"""
    place = pathlib.Path(place)
    closed = {"ask": False, "message": ""}
    if files.read_stop(place):
        return closed
    for name in files.ROLES.values():
        why = rolekit.given_up_reason(place, name)
        if why:
            files.write_stop(place, files.STOP, why)
            return closed
    got = {role: files.read(files.role_file(place, role)) for role in files.ROLES}
    pend = [files.NODES[r] for r in ("write", "review") if got[r] is None]
    if not pend and got["revise"] is None and take.revise_due(got["review"]):
        pend.append(files.NODES["revise"])
    if pend:
        files.write_stop(place, files.STOP, f"仕様が固まっていない（待ちのノード: {'・'.join(pend)}）——ループか承認ノードが回らなかった")
        return closed
    pending, asking = approve(take.current(place), got["review"], got["revise"], root)
    message = gate_text(asking, run_id=run_id)
    files.write(place / files.SPEC_ASK, {"pending": pending, "asking": asking, "message": message})
    return {"ask": True, "message": message}


def answer(place, root, reply) -> dict:
    """承認ノードの答え（開かなかった時は null）を受ける。返り {go, reason}:
    - 開かなかった（None）: go 偽（前の node が止めた。止めの控えが無ければ works:spec で止める）
    - 止める語（stop・reject）: 一言（空なら GATE_STOP_NOTE）が request: で始まれば request:spec-gate、ほかは human:spec-gate で止める
    - 通す語（approve・continue）: spec-ask.json の仕様を固める（もう spec.json が在れば 2 度固めない）
    答えの形の誤り（知らない語など）は works:spec で止めて go 偽"""
    place = pathlib.Path(place)
    try:
        gate = parse_gate(reply)
    except rolekit.BoardGap as e:
        files.write_stop(place, files.STOP, str(e))
        return {"go": False, "reason": str(e)}
    if gate is None:
        if files.read_stop(place) is None:
            files.write_stop(place, files.STOP, "仕様の承認ノードが開かなかった（仕様が固まっていない）")
        return {"go": False, "reason": files.read_stop(place)["reason"]}
    if gate["decision"] in answers.STOP_WORDS:
        note = gate["text"] if gate["text"].strip() else files.GATE_STOP_NOTE
        by = (files.FLAG_BY_PREFIX if gate["text"].strip().startswith(files.FLAG_BY_PREFIX) else stopby.HUMAN) + files.GATE
        files.write_stop(place, by, note)
        return {"go": False, "reason": f"人が承認ノードで仕様を承認しなかった: {note}"}
    if (place / files.SPEC).exists():
        return {"go": True, "reason": ""}
    asked = files.read(place / files.SPEC_ASK)
    if not isinstance(asked, dict) or not isinstance(asked.get("pending"), dict):
        why = f"{files.SPEC_ASK} が無い・形が違う——承認ノードに見せた仕様が無いので固められない"
        files.write_stop(place, files.STOP, why)
        return {"go": False, "reason": why}
    approval = {"round": 1, "node": files.APPROVE, "kinds": list(asked.get("asking", {}).get("kinds") or []),
                "answer": "continue", "note": gate["text"]}
    freeze.freeze(place, root, asked["pending"], approval)
    return {"go": True, "reason": ""}
