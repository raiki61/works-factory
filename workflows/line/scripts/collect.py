# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""report へ渡す 2 つの形（sections・facts）を組んで place に書く node collect（docs/design/line.md の 7 節。trigger_rule: all_done・
always_run: true）。sections は src/sections.py、facts は src/facts.py が組み、place の src.files.SECTIONS・FACTS に書いて pointer を返す。

受け皿の got・返し・承認の答え・line の script の出力を `{from, if_skipped: null}` で受ける（飛んだ物は null）。block の返り（受け皿の
got）は要る欄を全部名指して読む（欄の欠けた前の版の返りを resume で受けたら空と読まない。integration.md 4.3-12）。固定材料の run は
判定・計画が飛ぶので、fix-in が運んだ写し（received）で埋める（facts.returns_of・sections.build）。

落ちない: 組めない時も fallback が訳だけの sections と facts（problems に訳。結末は record_invalid）を書いて pointer を返す。facts の
部分ごとの組めなさは facts.build が訳を problems・notes に足す。

入力（with:）: notices（testcmd の注意の字）・start・answer_start・tiers・owed・structure_in・design_in・ask_before_fix・answer_before_fix・
fix_in・after_fix・raise・lens_in・ask_replan・answer_replan・lens_2_in・fixed・judged・eyes_in・ask_final・answer_final（line の script の
出力）・test_gate_base・judge・structure・independent_design・rounds・fix・lens・delta・replan・replan_review・refix・lens_2・delta_2・
parallel_after・rejudge・spec_check・test_gate_final・eyes・merge_seal・merge_apply（受け皿の got）・optional（line 自身の受け止める段の宣言）
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

# 受け皿の got の欄（YAML の受け皿の names と同じ並び）
GOT = {
    "test_gate_base": "mode ok green red_cause ran_steps baseline fingerprint test_outcomes evidence by suites_line log baseline_line reason suite suite_note related report",
    "judge": "ok stop_reason reason ready units judgment answer_ties out_of_purpose materials brief inputs purpose purpose_text purpose_source "
             "means purpose_review constraints world world_state spec spec_rows spec_origin excluded pr_drafts downgrades decisions tier tier_why "
             "row_asks tier_record verify verify_why report sections optional",
    "structure": "ok status reason structure after dirty escalate report",
    "independent_design": "ok status stands design premises reason downgrades report",
    "rounds": "done ok status round plan_prior record plan fix_plan reply handoffs ripple owed gave_up stalled capped review asks deviations review_status review_reason stop_reason",
    "fix": "ok reason units groups conflicts carry replan_items objection diff start_tree reply ruled_reply scope checked allowed_test_changes "
           "changed x_scalars handoffs mismatched plan_declared stop_reason allowed_tests accept_trace closure tdd_unit tdd frozen removed "
           "tdd_refused item_claims freeze_off report",
    "lens": "ok status reason rows ran failed not_routed carry report",
    "delta": "ok status reason rounds pass holes diff carry report",
    "replan": "ok status reason mode round owed plan fix_plan reply handoff replan ripple rejects gave_up report",
    "replan_review": "ok status form round reason holes blocks pass asks deviations replan gave_up reads report",
    "parallel_after": "ok status stop_reason reason material excluded drafts reads downgrades report",
    "rejudge": "ok status mode stop_reason reason ready judgment units questions inputs brief materials out_of_purpose answer_ties "
               "rejudge_verdict rejudge_exit rejudge_diff downgrades report",
    "spec_check": "ok status stop_reason reason spec added_rows added_origin questions unchecked report",
    "test_gate_final": "mode ok green red_cause ran_steps baseline fingerprint test_outcomes evidence by suites_line log baseline_line reason suite suite_note related report",
    "eyes": "ok r1 r2 r3 r4 questions passes premise_check notes after dirty escalate after_ok report sections",
    "merge_seal": "mode ok hash diff protected_hits protected_count reason deliver report",
    "merge_apply": "mode ok hash diff protected_hits protected_count reason deliver report",
}
GOT["refix"] = GOT["fix"]
GOT["lens_2"] = GOT["lens"]
GOT["delta_2"] = GOT["delta"]


def raw_inputs() -> dict:
    """with: の入力の全部（字のまま。名を組まずに 1 つずつ読む）"""
    return {
        "notices": os.environ.get("INPUTS_NOTICES"), "start": os.environ.get("INPUTS_START"),
        "answer_start": os.environ.get("INPUTS_ANSWER_START"), "test_gate_base": os.environ.get("INPUTS_TEST_GATE_BASE"),
        "judge": os.environ.get("INPUTS_JUDGE"), "tiers": os.environ.get("INPUTS_TIERS"), "owed": os.environ.get("INPUTS_OWED"),
        "structure": os.environ.get("INPUTS_STRUCTURE"), "structure_in": os.environ.get("INPUTS_STRUCTURE_IN"),
        "independent_design": os.environ.get("INPUTS_INDEPENDENT_DESIGN"), "design_in": os.environ.get("INPUTS_DESIGN_IN"),
        "rounds": os.environ.get("INPUTS_ROUNDS"), "ask_before_fix": os.environ.get("INPUTS_ASK_BEFORE_FIX"),
        "answer_before_fix": os.environ.get("INPUTS_ANSWER_BEFORE_FIX"), "fix_in": os.environ.get("INPUTS_FIX_IN"),
        "fix": os.environ.get("INPUTS_FIX"), "after_fix": os.environ.get("INPUTS_AFTER_FIX"), "raise": os.environ.get("INPUTS_RAISE"),
        "lens": os.environ.get("INPUTS_LENS"), "lens_in": os.environ.get("INPUTS_LENS_IN"), "delta": os.environ.get("INPUTS_DELTA"),
        "replan": os.environ.get("INPUTS_REPLAN"), "replan_review": os.environ.get("INPUTS_REPLAN_REVIEW"),
        "ask_replan": os.environ.get("INPUTS_ASK_REPLAN"), "answer_replan": os.environ.get("INPUTS_ANSWER_REPLAN"),
        "refix": os.environ.get("INPUTS_REFIX"), "lens_2": os.environ.get("INPUTS_LENS_2"), "lens_2_in": os.environ.get("INPUTS_LENS_2_IN"),
        "delta_2": os.environ.get("INPUTS_DELTA_2"), "fixed": os.environ.get("INPUTS_FIXED"),
        "parallel_after": os.environ.get("INPUTS_PARALLEL_AFTER"), "rejudge": os.environ.get("INPUTS_REJUDGE"),
        "spec_check": os.environ.get("INPUTS_SPEC_CHECK"), "judged": os.environ.get("INPUTS_JUDGED"),
        "test_gate_final": os.environ.get("INPUTS_TEST_GATE_FINAL"), "eyes_in": os.environ.get("INPUTS_EYES_IN"),
        "eyes": os.environ.get("INPUTS_EYES"), "merge_seal": os.environ.get("INPUTS_MERGE_SEAL"),
        "ask_final": os.environ.get("INPUTS_ASK_FINAL"), "answer_final": os.environ.get("INPUTS_ANSWER_FINAL"),
        "merge_apply": os.environ.get("INPUTS_MERGE_APPLY"), "optional": os.environ.get("INPUTS_OPTIONAL"),
    }


def values_of(raw: dict) -> dict:
    """読んだ値: 受け皿の got は picked（欄の全部を名指す）、ほかは parsed、notices は字"""
    out = {}
    for name, text in raw.items():
        if name == "notices":
            out[name] = ports.text(text) if text not in (None, "null") else ""
        elif name in GOT:
            got = ports.picked(text, GOT[name].split())
            out[name] = None if got is None else dict(got)
        else:
            out[name] = ports.parsed(text)
    return out


def record_of(start) -> tuple[dict | None, str]:
    """始めの記録の dict と読めなかった訳（start の出力の record の pointer の先）"""
    from src import facts
    ptr = start.get("record") if isinstance(start, dict) else None
    if ptr is None:
        return None, "始めの記録が無い（start が飛んだか、記録を書けなかった）"
    doc, why = facts.read_ptr(ptr)
    if why:
        return None, f"始めの記録が読めない: {why}"
    if not isinstance(doc, dict):
        return None, "始めの記録が JSON のオブジェクトでない"
    return doc, ""


def write(name: str, doc) -> dict:
    path = ports.place() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return ports.pointer(path)


def compute():
    raw = raw_inputs()
    from src import facts, files, sections
    values = values_of(raw)
    record, why = record_of(values.get("start"))
    built = facts.build(values, record, why, cwd=Path.cwd())
    secs = sections.build(values, record or {}, cwd=Path.cwd(), folder=ports.place())
    return {"sections": write(files.SECTIONS, secs), "facts": write(files.FACTS, built)}


def fallback(reason: str) -> dict:
    """訳だけの sections と facts（problems に訳。結末は record_invalid）"""
    from src import files, guard
    secs = [{"title": "入口・段・決めた人", "lines": [f"報告の材料を組めなかった（{reason}）"]}]
    doc = {"problems": [f"collect が報告の材料を組めなかった: {reason}"], "stops": [{"at": "collect", "word": guard.LINE_SCRIPT}]}
    return {"sections": write(files.SECTIONS, secs), "facts": write(files.FACTS, doc)}


ports.run(compute, fallback)
