# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""報告のブロックの最初の節: 入力・型つきの成果物の一覧・run の記録を読み、結末を決め、機械の報告と持ち越しを run の置き場の
report/ に書く。0 以外で終わらない（落ちると線は報告の返りを受けられない）: lib/ を読めない時も含めて思わぬ誤りを捕まえ、
record_invalid で返す。lib/ は main の中で読む（読めない時の受け皿は place.unwritten）。"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

import typed  # noqa: E402
from place import UNWRITTEN, failed_line, out_dir, rel, unwritten  # noqa: E402

RETURNS = {
    "test-gate-base": os.environ.get("INPUTS_TEST_GATE_BASE", ""),
    "judge": os.environ.get("INPUTS_JUDGE", ""),
    "rejudge": os.environ.get("INPUTS_REJUDGE", ""),
    "plan": os.environ.get("INPUTS_PLAN", ""),
    "plan-review": os.environ.get("INPUTS_PLAN_REVIEW", ""),
    "replan": os.environ.get("INPUTS_REPLAN", ""),
    "replan-review": os.environ.get("INPUTS_REPLAN_REVIEW", ""),
    "fix": os.environ.get("INPUTS_FIX", ""),
    "test-gate-final": os.environ.get("INPUTS_TEST_GATE_FINAL", ""),
    "eyes": os.environ.get("INPUTS_EYES", ""),
    "merge-seal": os.environ.get("INPUTS_MERGE_SEAL", ""),
    "merge-apply": os.environ.get("INPUTS_MERGE_APPLY", ""),
}
GATES = {
    "gate-start": os.environ.get("INPUTS_GATE_START", ""),
    "gate-before-fix": os.environ.get("INPUTS_GATE_BEFORE_FIX", ""),
    "gate-replan": os.environ.get("INPUTS_GATE_REPLAN", ""),
    "gate-final": os.environ.get("INPUTS_GATE_FINAL", ""),
}
START = os.environ.get("INPUTS_START", "")
WORKFLOW_FILE = Path(__file__).resolve().parents[1] / "works-factory-report.yaml"   # 来歴の行の版を測る自分の工程


def parse(name: str, raw: str) -> tuple:
    """入力の字を (値, 読めなかった訳) に。空と字の null は (None, "")。JSON でない・オブジェクトでない時も落とさず None"""
    if raw.strip() in ("", "null"):
        return None, ""
    try:
        value = json.loads(raw)
    except ValueError as e:
        return None, f"入力 {name} が JSON でない（{e}）"
    if not isinstance(value, dict):
        return None, f"入力 {name} が JSON のオブジェクトでない"
    return value, ""


def opened(value, unopened: list, rid: str, field: str = ""):
    """返りの中の指し札を、開けたファイルのパスの字に替える（開けなければ None にし、(段, 返りの欄, 訳) を unopened に積む）"""
    if isinstance(value, dict) and value.get("type") == boundary.POINTER_TYPE:
        try:
            path = boundary.resolve(value)
        except (KeyError, ValueError) as e:
            unopened.append((rid, field, f"指し札 {value.get('path')} を開けない: {e}"))
            return None
        if not path.is_file():
            unopened.append((rid, field, f"指し札の先 {path} が無い"))
            return None
        return str(path)
    if isinstance(value, dict):
        return {k: opened(v, unopened, rid, field or k) for k, v in value.items()}
    if isinstance(value, list):
        return [opened(v, unopened, rid, field) for v in value]
    return value


def start_record(problems: list) -> dict:
    ptr, why = parse("start", START)
    if ptr is None:
        problems.append(why or "始めの記録（入力 start）が届いていない")
        return {}
    try:
        doc = json.loads(boundary.resolve(ptr).read_text(encoding="utf-8"))
    except (OSError, KeyError, ValueError) as e:
        problems.append(f"始めの記録を開けない: {e}")
        return {}
    if not isinstance(doc, dict):
        problems.append("始めの記録が JSON のオブジェクトでない")
        return {}
    return doc


def transcript() -> tuple:
    """run の記録の行と、読めなかった訳"""
    log_dir, run_id = os.environ.get("LOG_DIR", ""), os.environ.get("WORKFLOW_ID", "")
    if not log_dir or not run_id:
        return None, "run の記録の置き場（LOG_DIR）か run の id（WORKFLOW_ID）が届いていない"
    path = Path(log_dir) / f"{run_id}.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        return None, f"run の記録 {path} が読めない（{e.strerror or e}。dry-run は記録を書かない）"
    rows = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows, ""


def main() -> dict:
    sys.path.append(str(boundary.lib_root()))
    import outcome
    import runreport

    unread, unopened, returns, gates = [], [], {}, {}
    for rid, raw in RETURNS.items():
        value, why = parse(rid, raw)
        returns[rid] = opened(value, unopened, rid)
        unread += [why] if why else []
    for gid, raw in GATES.items():
        gates[gid], why = parse(gid, raw)
        unread += [why] if why else []
    problems, notes = outcome.record_problems(returns, gates, unread=unread, unopened=unopened)
    start = start_record(problems)
    rows, transcript_why = transcript()
    listing = typed.read_listing()
    listing["warnings"] = [*notes, *listing["warnings"], *([transcript_why] if transcript_why else [])]
    facts = runreport.transcript_facts(rows, exclude_prefix=typed.own_prefix(os.environ.get("ARCHON_NODE_EXECUTION", "")))
    decided = outcome.decide_outcome(returns, gates, {"start_ok": bool(start), "record_problems": problems,
                                                      "failed": facts["failed"],
                                                      "absorbed": facts["absorbed"], "answers": start.get("answers") or []})
    built = runreport.build(returns, gates, listing, facts, *decided, out_dir=out_dir(), start=start, problems=problems,
                            run_id=os.environ.get("WORKFLOW_ID", ""), transcript_why=transcript_why, repo=Path.cwd())
    report = rel(built["report"])
    run_id = os.environ.get("WORKFLOW_ID", "")
    return {"outcome": decided[0], "ok": decided[0] in outcome.OK_OUTCOMES, "stop_reason": decided[1],
            "report": report, "next_request": rel(built["next_request"]),
            "prior_failures": rel(built["prior_failures"]), "ai_go": built["ai_go"], "facts_file": report["path"],
            "stamp": runreport.stamp(run_id, WORKFLOW_FILE, outcome.as_dict(outcome.planned(returns)).get("round"),
                                     start=start)}


def fallen(error: BaseException) -> dict:
    """思わぬ誤りでも返る形（結末 record_invalid と誤りの 1 行を載せた機械の報告。lib/ を読めない・それも書けなければ訳だけの 1 ファイル）"""
    why = failed_line("報告の事実", error)
    out = {"outcome": "record_invalid", "ok": False, "stop_reason": f"report:{why}", "report": None,
           "next_request": None, "prior_failures": None, "ai_go": False, "facts_file": "", "stamp": ""}
    try:
        import runreport
        out["report"] = rel(runreport.fallback_report(out_dir(), why, UNWRITTEN))
    except Exception:  # noqa: BLE001 — lib/ を読めなくても、置き場に書けなくても返る
        out["report"] = unwritten(why)
    out["facts_file"] = out["report"]["path"]
    return out


if __name__ == "__main__":
    try:
        result = main()
    except Exception as error:  # noqa: BLE001 — 0 以外で終わると線が報告の返りを受けられない
        result = fallen(error)
    boundary.returns(result)
