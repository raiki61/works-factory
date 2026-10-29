# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""計画の往復（loop_group の plan-rounds）の本体の終わりの node plan-out（docs/design/line.md の 3 節。往復の記録と止めは line）。

1. 入力: plan の返りまるごと・事前審査の返りまるごと（plan が通らなかった周は飛ぶ）・前の周の記録（$LOOP_PREV.plan-out.output.record）
2. 事前審査が通った周は、pass.json の材料で往復の行を記録 plan-converge.json に足す（src.rounds.record_pass。輪がもう 1 周回せない
   周〔周の番号が上限 LIMIT〕は at_cap。files を plan-converge/<k>/ へ写し、plan の rejects と事前審査の拒否を行に積み、
   precedent_checks を記録の頭に置く）。次の周の plan の prior（plan-rounds/prior-<k>.json。plan の plan-prior.schema.json の形）を書く
3. 事前審査の状態 review_status（ok・gave_up・failed。計画が通った周に事前審査の返りが無ければ failed）と訳 review_reason を返す
   （修正前の承認ノードが、諦めた・落ちた事前審査を開ける理由にする）
4. 止め時は src.rounds.decide の語（往復の数・block の数で止めない）。done は、plan が ok でない・事前審査が ok でない・抜け方が修正へ
   進む語（proceeds）・止まった（PERSISTED・UNSETTLED）・周の番号が上限 LIMIT 以上、のどれか。上限で止めた行には capped
5. 止まった案を無人の run が推しで進める時（rounds.stuck_push_due）は、保留の項目の前の往復の block（stuck_faces）を事前審査の
   返答に足したファイルを書いて review に返す（fix と delta-review の plan_review が読む）
例外の時は計画ができなかった形（ok: false・done: true）と止めの語 works:line-script。

入力（with:）: plan（$plan.output）・review（{from: $plan-review-run.output, if_skipped: null}）・prior（前の周の記録の pointer。
1 周目は空）・unattended（無人の run か）
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

PLAN = ("ok", "status", "reason", "round", "owed", "plan", "fix_plan", "reply", "handoff", "ripple", "rejects", "gave_up", "pointed")
POINTED = ("pointed",)   # plan の出力の欄のうち plan-out の output_format で required でない物
REVIEW = ("ok", "status", "round", "holes", "blocks", "pass", "asks", "deviations", "reason")


def _json_at(ptr, opened):
    """pointer の先の JSON。opened は宣言の form で照らしてパスを返す読み（ports.file）"""
    return json.loads(opened(json.dumps(ptr)).read_text(encoding="utf-8"))


def plan_out(plan, review, prior_raw, *, unattended: bool, place: Path) -> dict:
    from src import files, rounds
    k = plan["round"] if isinstance(plan["round"], int) else 1
    prior = ports.file(prior_raw, "json(shared:plan-converge.schema.json)") if ports.parsed(prior_raw) is not None else None
    doc = rounds.read(prior)
    passed = plan["ok"] is True and review is not None and review["ok"] is True and review["pass"] is not None
    if passed:
        rounds.record_pass(doc, _json_at(review["pass"], lambda raw: ports.file(raw, "json(shared:plan-review-pass.schema.json)")), at_cap=k >= rounds.LIMIT,
                           dest=place / files.PLAN_CONVERGE_FILES.format(k=len(doc["passes"]) + 1), plan_rejects=plan["rejects"])
    record = rounds.write(place / files.PLAN_CONVERGE, doc)
    outcome = doc["outcome"] if passed else None
    stalled = outcome in rounds.STUCK
    reviewed = review is not None and review["ok"] is True
    pointer_of_holes = review["holes"] if reviewed else None
    if stalled and rounds.stuck_push_due(doc, unattended=unattended, design_talk=False) and pointer_of_holes is not None:
        held = rounds.stuck_faces(doc)
        if held:
            holes = _json_at(pointer_of_holes, lambda raw: ports.file(raw, "json(shared:plan-review-reply.schema.json)"))
            written = place / files.PLAN_REVIEW.format(k=k)
            written.parent.mkdir(parents=True, exist_ok=True)
            written.write_text(json.dumps({**holes, "faces": list(holes.get("faces") or []) + held}, ensure_ascii=False, indent=1) + "\n",
                               encoding="utf-8")
            pointer_of_holes = ports.pointer(written, "json(shared:plan-review-reply.schema.json)")
    handoffs = [*_prior_handoffs(place, files, k), {"round": k, "handoff": plan["handoff"]}]
    prior_file = None
    if plan["ok"] is True and plan["reply"] is not None:   # 受けた案の在る周だけが次の周の prior（plan-prior の形は受けた案を要る）
        prior_file = place / files.PLAN_PRIOR.format(k=k)
        prior_file.parent.mkdir(parents=True, exist_ok=True)
        prior_file.write_text(json.dumps({"round": k, "reply": plan["reply"], "fields": plan["plan"], "fix_plan": plan["fix_plan"],
                                          "ripple": plan["ripple"], "review": pointer_of_holes, "record": doc, "handoffs": handoffs},
                                         ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    proceeds = rounds.proceeds(outcome)
    done = (plan["ok"] is not True or not reviewed or proceeds or stalled or k >= rounds.LIMIT)
    return {"done": done, "ok": plan["ok"] is True and reviewed and proceeds, "status": plan["status"] or "", "round": k,
            "plan_prior": ports.pointer(prior_file, "json(shared:plan-prior.schema.json)") if prior_file else None,
            "record": ports.pointer(record, "json(shared:plan-converge.schema.json)"),
            "plan": plan["plan"], "fix_plan": plan["fix_plan"], "reply": plan["reply"],
            "handoffs": [h for h in handoffs if isinstance(h.get("handoff"), dict)], "ripple": plan["ripple"],
            "owed": plan["owed"] if isinstance(plan["owed"], list) else [], "gave_up": plan["gave_up"] or (review or {}).get("gave_up"),
            "stalled": stalled, "capped": rounds.capped(doc), "review": pointer_of_holes,
            "asks": review["asks"] if reviewed and isinstance(review["asks"], list) else [],
            "deviations": review["deviations"] if reviewed and isinstance(review["deviations"], list) else [],
            "review_status": review_state(plan, review), "review_reason": (review or {}).get("reason") or "", "stop_reason": "",
            "pointed": plan["pointed"] if isinstance(plan["pointed"], list) else []}   # 欄の無い前の版の返りと stub は空と読む


def review_state(plan, review) -> str:
    """事前審査の状態（修正前の承認ノードが、諦めた・落ちた事前審査を人に見せる。計画が通らず事前審査が飛んだ周は空）。今の事前審査は
    受け付けが諦めた周の訳を関所の項目に載せた（元 lib/boardview.py の collect の GIVEN_UP_FACES）"""
    if review is None:
        return "" if plan["ok"] is not True else "failed"
    return str(review["status"] or "")


def _prior_handoffs(place: Path, files, k: int) -> list:
    """前の周の prior のファイル（同じ run の plan-rounds/prior-<k-1>.json）の handoffs（無い・読めなければ []）"""
    if k <= 1:
        return []
    try:
        got = json.loads((place / files.PLAN_PRIOR.format(k=k - 1)).read_text(encoding="utf-8")).get("handoffs")
    except (OSError, ValueError, AttributeError):
        return []
    return [h for h in got if isinstance(h, dict) and isinstance(h.get("round"), int) and h["round"] < k] if isinstance(got, list) else []


def compute() -> dict:
    raw_plan, raw_review = os.environ.get("INPUTS_PLAN"), os.environ.get("INPUTS_REVIEW")
    raw_prior, raw_unattended = os.environ.get("INPUTS_PRIOR"), os.environ.get("INPUTS_UNATTENDED")
    plan = ports.picked(raw_plan, PLAN, optional=POINTED)
    if plan is None:
        raise ValueError("plan の出力（plan）が読めない。with: の鍵の結びを確かめる")
    review = ports.picked(raw_review, REVIEW, optional=("gave_up",))
    return plan_out(plan, review, raw_prior, unattended=ports.flag(raw_unattended), place=ports.place())


def fallback(reason: str) -> dict:
    from src import talk
    return talk.failed()   # 計画ができなかった形（設計の相談の design-talk も plan-out が飛んだ周にこの形を返す。1 か所）


ports.run(compute, fallback)
