# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""報告のブロックの最初の節: 入力・型つきの成果物の一覧・run の記録を読み、結末を決め、機械の報告と持ち越しを run の置き場の
report/ に書く。0 以外で終わらない（落ちると線は報告の返りを受けられない）: lib/ を読めない時も含めて思わぬ誤りを捕まえ、
record_invalid で返す。lib/ は main の中で読む（読めない時の受け皿は place.unwritten）。境の口か隣の typed・place を読めない時も、
返す節が結ぶので、標準ライブラリだけで同じ形を返す。
書き手の役の文の頭に足す言語の 1 行（始めの記録の lang から rolekit.lang_line。元 works/.shared/core/rolekit.py 147-150 行）も
lang_line で返す（読めない記録・思わぬ誤りの時は既定の言語の 1 行）。"""
import json
import os
import sys
from pathlib import Path

UNWRITTEN = "report-unwritten.md"   # place.UNWRITTEN の写し。隣の place を読めない時の bare も同じ名へ書く
LANG_FALLBACK = "人が読む文の欄は依頼文の言語で書け（言語の 1 行を組めなかった）"   # 言語の 1 行を組めない道の 1 行

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary

    import typed
    from place import failed_line, out_dir, rel, unwritten
    unread = None
except Exception as error:  # noqa: BLE001 — 返す節が結ぶので落ちない（下の bare で返す）
    boundary, unread = None, error

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
LINE = {   # 線の値（線の collect が渡す。docs/design.md の report の返り）
    "stops": os.environ.get("INPUTS_STOPS", ""),
    "prior-failures": os.environ.get("INPUTS_PRIOR_FAILURES", ""),
    "deferred": os.environ.get("INPUTS_DEFERRED", ""),
    "widened": os.environ.get("INPUTS_WIDENED", ""),
    "final-reasons": os.environ.get("INPUTS_FINAL_REASONS", ""),
    "redepth": os.environ.get("INPUTS_REDEPTH", ""),
    "optional": os.environ.get("INPUTS_OPTIONAL", ""),
}
LISTS = ("deferred", "widened", "final-reasons", "optional")
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
            unopened.append((rid, field, f"ポインタ {value.get('path')} を開けない: {e}"))
            return None
        if not path.is_file():
            unopened.append((rid, field, f"ポインタの先 {path} が無い"))
            return None
        return str(path)
    if isinstance(value, dict):
        return {k: opened(v, unopened, rid, field or k) for k, v in value.items()}
    if isinstance(value, list):
        return [opened(v, unopened, rid, field) for v in value]
    return value


def line_values(unread: list, unopened: list) -> dict:
    """線の値を {stops, prior_failures, deferred, widened, final_reasons, redepth, optional} に（欄の名は - を _ に）。並びの入力は
    配列でなければ空にし、JSON でない入力は訳を unread に積む（黙って空にしない）。依頼の前の失敗の指し札は開けたパスの字にする"""
    out = {}
    for name, raw in LINE.items():
        key = name.replace("-", "_")
        if raw.strip() in ("", "null"):
            out[key] = [] if name in LISTS else None
            continue
        try:
            value = json.loads(raw)
        except ValueError as e:
            unread.append(f"入力 {name} が JSON でない（{e}）")
            value = None
        if name in LISTS and not isinstance(value, list):
            unread += [f"入力 {name} が配列でない"] if value is not None else []
            value = []
        out[key] = value
    out["stops"] = out["stops"] if isinstance(out["stops"], dict) else {}
    out["prior_failures"] = opened(out["prior_failures"], unopened, "prior-failures")
    return out


def start_record(problems: list) -> dict | None:
    """始めの記録。届いていない・開けない・オブジェクトでない時は訳を problems に足して None（読めた空の記録 {} と分ける）"""
    ptr, why = parse("start", START)
    if ptr is None:
        problems.append(why or "始めの記録（入力 start）が届いていない")
        return None
    try:
        doc = json.loads(boundary.resolve(ptr).read_text(encoding="utf-8"))
    except (OSError, KeyError, ValueError) as e:
        problems.append(f"始めの記録を開けない: {e}")
        return None
    if not isinstance(doc, dict):
        problems.append("始めの記録が JSON のオブジェクトでない")
        return None
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
    import rolekit
    import runreport

    unread, unopened, returns, gates = [], [], {}, {}
    for rid, raw in RETURNS.items():
        value, why = parse(rid, raw)
        returns[rid] = opened(value, unopened, rid)
        unread += [why] if why else []
    for gid, raw in GATES.items():
        gates[gid], why = parse(gid, raw)
        unread += [why] if why else []
    line = line_values(unread, unopened)
    problems, notes = outcome.record_problems(returns, gates, unread=unread, unopened=unopened)
    record = start_record(problems)
    start = record or {}
    rows, transcript_why = transcript()
    listing = typed.read_listing()
    listing["warnings"] = [*notes, *listing["warnings"], *([transcript_why] if transcript_why else [])]
    facts = runreport.transcript_facts(rows, exclude_prefix=typed.own_prefix(os.environ.get("ARCHON_NODE_EXECUTION", "")),
                                       optional=[x for x in line["optional"] if isinstance(x, str)])
    decided = outcome.decide_outcome(returns, gates, {"start_ok": bool(start), "record_problems": problems,
                                                      "failed": facts["failed"], **runreport.outcome_facts(start, facts, line)})
    built = runreport.build(returns, gates, listing, facts, *decided, out_dir=out_dir(), start=start, problems=problems,
                            run_id=os.environ.get("WORKFLOW_ID", ""), transcript_why=transcript_why, repo=Path.cwd(), line=line)
    report = rel(built["report"])
    run_id = os.environ.get("WORKFLOW_ID", "")
    return {"outcome": decided[0], "ok": decided[0] in outcome.OK_OUTCOMES, "stop_reason": decided[1],
            "report": report, "next_request": rel(built["next_request"]),
            "prior_failures": rel(built["prior_failures"]), "ai_go": built["ai_go"], "facts_file": report["path"],
            "stamp": runreport.stamp(run_id, WORKFLOW_FILE, outcome.as_dict(outcome.planned(returns)).get("round"),
                                     record),
            "lang_line": rolekit.lang_line(start)}


def fallen(error: BaseException) -> dict:
    """思わぬ誤りでも返る形（結末 record_invalid と誤りの 1 行を載せた機械の報告。lib/ を読めない・それも書けなければ訳だけの 1 ファイル）"""
    why = failed_line("報告の事実", error)
    out = {"outcome": "record_invalid", "ok": False, "stop_reason": f"report:{why}", "report": None,
           "next_request": None, "prior_failures": None, "ai_go": False, "facts_file": "", "stamp": "",
           "lang_line": LANG_FALLBACK}
    try:
        import rolekit
        out["lang_line"] = rolekit.lang_line({})
        import runreport
        out["report"] = rel(runreport.fallback_report(out_dir(), why, UNWRITTEN))
    except Exception:  # noqa: BLE001 — lib/ を読めなくても、置き場に書けなくても返る
        out["report"] = unwritten(why)
    out["facts_file"] = out["report"]["path"]
    return out


def bare(what: str, error: BaseException) -> tuple:
    """境の口か隣の部品を読めない時の訳と、訳だけを書いたファイルの指し札（place.failed_line・unwritten の標準ライブラリだけの写し）"""
    why = f"{what}を組めなかった（{type(error).__name__}: {' '.join(str(error).split())}）"
    rel_path = f"report/{UNWRITTEN}"
    try:
        path = Path(os.environ["ARTIFACTS_DIR"]) / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# 報告（run {os.environ.get('WORKFLOW_ID', '—')}）\n\n報告を組めなかった: {why}\n", encoding="utf-8")
    except (OSError, KeyError):
        pass
    return why, {"type": "archon_artifact", "run_id": os.environ.get("WORKFLOW_ID", ""), "path": rel_path}


if __name__ == "__main__" and boundary is None:   # 境の口を読めない時
    why, ptr = bare("報告の事実", unread)
    print(json.dumps({"outcome": "record_invalid", "ok": False, "stop_reason": f"report:{why}", "report": ptr,
                      "next_request": None, "prior_failures": None, "ai_go": False, "facts_file": ptr["path"], "stamp": "",
                      "lang_line": LANG_FALLBACK},
                     ensure_ascii=False, allow_nan=False), flush=True)
elif __name__ == "__main__":
    try:
        result = main()
    except Exception as error:  # noqa: BLE001 — 0 以外で終わると線が報告の返りを受けられない
        result = fallen(error)
    boundary.returns(result)
