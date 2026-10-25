"""診断の block の出口（docs/design/diagnose.md の 5.6）。どの段が落ちても落ちない: 出口は place のファイルだけを読み、
{ok, status, mode, stop_reason, reason, ready, judgment, units, questions, inputs, brief, materials, out_of_purpose, answer_ties,
rejudge_verdict, rejudge_exit, rejudge_diff, downgrades, report} を返す。judgment はいつも在る（受けた判定が無ければ空の形を書いて指す）。"""
from __future__ import annotations

import json
import pathlib

import gatemarks   # lib/
import jsonfile    # lib/
import oneline     # lib/
import rolekit     # lib/

import ports

from src import files, judge, rejudge, report

EMPTY_JUDGMENT = {"units": [], "questions": [], "framing": "", "one_shot": "", "materials_missing": [], "carried_r1": [],
                  "one_shot_closes": [], "precedents": []}
NO_RECORD = "判定役の返答を受けた記録が無い（ループが落ちたか、走っていない）"
NO_RECORD_REJUDGE = "再審の役の返答を受けた記録が無い（ループが落ちたか、走っていない）"


def _read(place: pathlib.Path, name: str):
    return jsonfile.read_or(place / name)


def _stop_word(mode: str) -> str:
    return files.REJUDGE_STOP if mode == files.REJUDGE else files.JUDGE_STOP


def _why_no_record(place: pathlib.Path, role: str) -> str:
    """受けた判定が無い訳: 指示が組めなかった訳 → 諦めた理由 → 最後の拒否の理由 → 記録が無い、の最初の物"""
    err = _read(place, files.PROMPT_ERROR_FILE)
    if isinstance(err, dict) and err.get("reason"):
        return str(err["reason"])
    rejected = rolekit.rejected(place, role)
    return (rolekit.given_up_reason(place, role) or (rejected[-1] if rejected else "")
            or (NO_RECORD_REJUDGE if role == files.REJUDGE_ROLE else NO_RECORD))


def _last_brief(place: pathlib.Path):
    prompts = sorted(place.glob(files.PROMPT_GLOB), key=lambda p: int(p.stem.rsplit("-", 1)[1]) if p.stem.rsplit("-", 1)[1].isdigit() else 0)
    return prompts[-1] if prompts else None


def _there(path) -> bool:
    return path is not None and pathlib.Path(path).is_file()


def _status(place: pathlib.Path, mode: str):
    """（status, stop_reason, reason）。intake の落ち・止め → 判定か再審の受けた記録、の順"""
    intake = _read(place, files.INTAKE_FILE)
    if not isinstance(intake, dict):
        return "failed", _stop_word(mode), f"{files.INTAKE_FILE} が読めない（無いか JSON でない）"
    if intake.get("status") in ("failed", "stopped"):
        return intake["status"], intake.get("stop_reason") or _stop_word(mode), str(intake.get("reason") or "")
    if mode == files.JUDGE:
        if (place / files.JUDGMENT_FILE).is_file():
            return "ok", "", ""
        return "failed", files.JUDGE_STOP, _why_no_record(place, files.DIAGNOSE_ROLE)
    written = (place / files.REJUDGE_EXIT_FILE).is_file()   # 受け付けが輪を抜ける時に書いた出口。在ればその訳が先
    if not written:
        rejudge.collect(place)
    exit_doc = _read(place, files.REJUDGE_EXIT_FILE)
    if isinstance(exit_doc, dict) and exit_doc.get("ok") is True and (place / files.JUDGMENT_FILE).is_file():
        return "ok", "", ""
    reason = str(exit_doc.get("reason") or "") if isinstance(exit_doc, dict) else ""
    err = None if written else _read(place, files.PROMPT_ERROR_FILE)
    if isinstance(err, dict) and err.get("reason"):   # 出口を書く前に node が落ちた（指示が組めない・受け付けが落ちた）訳
        reason = str(err["reason"])
    return "failed", files.REJUDGE_STOP, reason or _why_no_record(place, files.REJUDGE_ROLE)


def finish(place, repo, objection: str) -> dict:
    """出口の返り。mode は objection の字が空かで決める（intake が読めなくても決まる）。落ちる例外は上げる（script が fallback にする）"""
    place = pathlib.Path(place)
    mode = files.REJUDGE if str(objection or "").strip() else files.JUDGE
    status, stop_reason, reason = _status(place, mode)
    if not (place / files.JUDGMENT_FILE).is_file():
        jsonfile.write(place / files.JUDGMENT_FILE, EMPTY_JUDGMENT, parents=True)
    judgment = _read(place, files.JUDGMENT_FILE)
    ok = status == "ok"
    units = judge.structure_units(judgment, repo, record=place / files.STRUCTURE_DROPPED_FILE) if ok else []
    questions = [q for q in (judgment.get("questions") or []) if isinstance(q, dict) and gatemarks.asks_human(q)] if ok else []
    first = mode == files.JUDGE
    inputs, brief, mats = place / files.INPUT_FILE, _last_brief(place), place / files.MATERIALS_FILE
    outside, ties = place / files.OUT_OF_PURPOSE_FILE, place / files.ANSWER_TIES_FILE
    rexit, rdiff = place / files.REJUDGE_EXIT_FILE, place / files.REJUDGE_DIFF_FILE
    out = {
        "ok": ok, "status": status, "mode": mode, "stop_reason": stop_reason, "reason": reason,
        "ready": ok and bool(units), "judgment": ports.pointer(place / files.JUDGMENT_FILE, "json(shared:judgment.schema.json)"),
        "units": units, "questions": questions,
        "inputs": ports.pointer(inputs, "json(shared:diagnose-input.schema.json)") if first and _there(inputs) else None,
        "brief": ports.pointer(brief, "file") if first and _there(brief) else None,
        "materials": ports.pointer(mats, "json(shared:materials-state.schema.json)") if first and _there(mats) else None,
        "out_of_purpose": ports.pointer(outside, "json(lib:out-of-purpose.schema.json)") if first and ok and _there(outside) else None,
        "answer_ties": ports.pointer(ties, "json(shared:answer-ties.schema.json)") if first and ok and _there(ties) else None,
        "rejudge_verdict": rejudge.verdict_of(place) if not first and ok else None,
        "rejudge_exit": ports.pointer(rexit, "json(shared:rejudge-exit.schema.json)") if not first and _there(rexit) else None,
        "rejudge_diff": ports.pointer(rdiff, "json(shared:rejudge-diff.schema.json)") if not first and _there(rdiff) else None,
        "downgrades": [dict(row) for row in files.DOWNGRADES],
    }
    out["report"] = report.lines(place, mode, status, reason, judgment)
    json.dumps(out, ensure_ascii=False, allow_nan=False)   # JSON に書けない値は出口の落ちとして fallback にする
    return out


def fallback(place, why: str, objection: str) -> dict:
    """出口が思わぬ例外で落ちた時の返り（出口は落ちない）。judgment は在る判定のファイルが形に合えばそれを指し、無い・形に合わない時は
    空の形を書き直してから指す（形に合わない判定を指さない。fallback の中で形の誤りを投げない）"""
    mode = files.REJUDGE if str(objection or "").strip() else files.JUDGE
    reason = f"判定の出口が落ちた（{oneline.one_line(why)}）"
    place = pathlib.Path(place)
    try:
        judgment = ports.pointer(place / files.JUDGMENT_FILE, "json(shared:judgment.schema.json)")
    except ValueError:   # 無い・読めない・形に合わない（ShapeError も ValueError の子）
        jsonfile.write(place / files.JUDGMENT_FILE, EMPTY_JUDGMENT, parents=True)
        judgment = ports.pointer(place / files.JUDGMENT_FILE, "json(shared:judgment.schema.json)")
    return {"ok": False, "status": "failed", "mode": mode, "stop_reason": _stop_word(mode), "reason": reason, "ready": False,
            "judgment": judgment, "units": [], "questions": [], "inputs": None, "brief": None, "materials": None,
            "out_of_purpose": None, "answer_ties": None, "rejudge_verdict": None, "rejudge_exit": None, "rejudge_diff": None,
            "downgrades": [dict(row) for row in files.DOWNGRADES],
            "report": [report.head(mode, reason)]}
