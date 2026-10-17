# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""報告のブロックの最初の節: 入力・型つきの成果物の一覧・run の記録を読み、結末を決め、機械の報告と持ち越しを run の置き場の
report/ に書く。0 以外で終わらない（落ちると線は報告の返りを受けられない）: lib/ を読めない時も含めて思わぬ誤りを捕まえ、
record_invalid で返す。lib/ は main の中で読む（読めない時の受け皿は unwritten）。境の口を読めない時も、返す節が結ぶので、
標準ライブラリだけで同じ形を返す。
書き手の役の文の頭に足す言語の 1 行（始めの記録の lang から rolekit.lang_line。元 works/.shared/core/rolekit.py 147-150 行）も
lang_line で返す（読めない記録・思わぬ誤りの時は既定の言語の 1 行）。

型つきの成果物の一覧（$TYPED_ARTIFACTS_FILE）を読むのもここ（workflows/AGENTS.md の E5「読む部品は report ブロックの中に置く」）。
一覧の形は止めた Archon の packages/workflows/src/schemas/node-artifact.ts の nodeArtifactsListingSchema
（{runId, artifactsByType: {型: [{nodeId, outputType, loopGroupPath?, path, runId, producedAt, size}]}, errors: [{path, kind, code?}]}）。
型の名と include の名は決め打たず、一覧に在る物で組む。読めない物は名前つきの限りとして warnings に入れ、黙らない
（ASF の .archon/workflows/sdlc/.shared/report.ts:126-206 の型）。"""
import json
import os
import sys
from pathlib import Path

LIBLESS = "report-facts-unwritten.md"   # lib/ を読めない時の訳だけのファイル（run の置き場の根。報告の置き場の名は lib が持つ）
LANG_FALLBACK = "人が読む文の欄は依頼文の言語で書け（言語の 1 行を組めなかった）"   # 言語の 1 行を組めない道の 1 行

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    unread = None
except Exception as error:  # noqa: BLE001 — 返す節が結ぶので落ちない（下の unwritten で返す）
    boundary, unread = None, error

RETURNS = {
    "before-tests": os.environ.get("INPUTS_BEFORE_TESTS", ""),
    "judge": os.environ.get("INPUTS_JUDGE", ""),
    "rejudge": os.environ.get("INPUTS_REJUDGE", ""),
    "plan": os.environ.get("INPUTS_PLAN", ""),
    "plan-review": os.environ.get("INPUTS_PLAN_REVIEW", ""),
    "replan": os.environ.get("INPUTS_REPLAN", ""),
    "replan-review-result": os.environ.get("INPUTS_REPLAN_REVIEW_RESULT", ""),
    "fix": os.environ.get("INPUTS_FIX", ""),
    "final-tests": os.environ.get("INPUTS_FINAL_TESTS", ""),
    "eyes": os.environ.get("INPUTS_EYES", ""),
    "sealed-diff": os.environ.get("INPUTS_SEALED_DIFF", ""),
    "applied-diff": os.environ.get("INPUTS_APPLIED_DIFF", ""),
}
GATES = {
    "start-answer": os.environ.get("INPUTS_START_ANSWER", ""),
    "before-fix-answer": os.environ.get("INPUTS_BEFORE_FIX_ANSWER", ""),
    "replan-answer": os.environ.get("INPUTS_REPLAN_ANSWER", ""),
    "final-answer": os.environ.get("INPUTS_FINAL_ANSWER", ""),
}
START = os.environ.get("INPUTS_START", "")
LINE = {   # 線の値（線の collect が渡す。docs/design.md の report の返り）
    "stops": os.environ.get("INPUTS_STOPS", ""),
    "stages": os.environ.get("INPUTS_STAGES", ""),
    "prior-failures": os.environ.get("INPUTS_PRIOR_FAILURES", ""),
    "deferred": os.environ.get("INPUTS_DEFERRED", ""),
    "widened": os.environ.get("INPUTS_WIDENED", ""),
    "final-reasons": os.environ.get("INPUTS_FINAL_REASONS", ""),
    "spec-changed": os.environ.get("INPUTS_SPEC_CHANGED", ""),
    "spec-unchecked": os.environ.get("INPUTS_SPEC_UNCHECKED", ""),
    "redepth": os.environ.get("INPUTS_REDEPTH", ""),
    "optional": os.environ.get("INPUTS_OPTIONAL", ""),
}
LISTS = ("deferred", "widened", "final-reasons", "spec-changed", "optional")
WORKFLOW_FILE = Path(__file__).resolve().parents[1] / "works-factory-report.yaml"   # 来歴の行の版を測る自分の工程


def out_dir() -> Path:
    """報告の置き場（run の置き場の runreport.OUT_DIR）"""
    import runreport
    return Path(os.environ["ARTIFACTS_DIR"]) / runreport.OUT_DIR


def rel(path) -> dict | None:
    """置き場の中のパスを、run の置き場からの相対の指し札に（None は None）"""
    return None if path is None else boundary.pointer(boundary.rel_of(path))


def failed_line(what: str, error: BaseException) -> str:
    """思わぬ誤りの 1 行（返す節は stop_reason に report: を付けて載せる）"""
    return f"{what}を組めなかった（{type(error).__name__}: {' '.join(str(error).split())}）"


def unwritten(why: str) -> dict:
    """lib/ にも境の口にも頼らず訳だけの 1 ファイルを書いて指す（書けなくても札は返す。先の無い札は実行基盤が節の終わりに拒む）。
    札は境の口を読めない時のために手で組む"""
    rel_path = LIBLESS
    try:
        path = Path(os.environ["ARTIFACTS_DIR"]) / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# 報告（run {os.environ.get('WORKFLOW_ID', '—')}）\n\n報告を組めなかった: {why}\n", encoding="utf-8")
    except (OSError, KeyError):
        pass
    return {"type": "archon_artifact", "run_id": os.environ.get("WORKFLOW_ID", ""), "path": rel_path}


def _include(node_id: str) -> str:
    """節の id の include の頭（最初の __ より前。無ければ空）"""
    head, sep, _ = node_id.partition("__")
    return head if sep else ""


def own_prefix(execution: str) -> str:
    """自分の節の実行の記録（ARCHON_NODE_EXECUTION の JSON）の path から、自分の include の名前空間の節の id の頭（節の id の
    最後の __ まで。入れ子の include の節の id は outer__inner__node なので outer__inner__。include の外の節なら空）"""
    try:
        doc = json.loads(execution) if execution else {}
    except ValueError:
        return ""
    path = doc.get("path") if isinstance(doc, dict) else None
    head = path.rsplit(".", 1)[-1].rpartition("__")[0] if isinstance(path, str) else ""
    return f"{head}__" if head else ""


def listing(listing_file: str, artifacts_dir: str, run_id: str, execution: str = "") -> dict:
    """{by_type: {型: [{include, loop, node, path, produced_at, body}]}, warnings: [文]}。body は中身の JSON（読めなければ None と
    注意）。ほかの run の行と自分の include の名前空間の行は数えない。一覧の errors は 1 件ずつ warnings に入れる"""
    out = {"by_type": {}, "warnings": []}
    warn = out["warnings"].append
    if not listing_file:
        warn("型つきの成果物の一覧がこのノードに届いていない（TYPED_ARTIFACTS_FILE が空。dry-run か、一覧の無いノード）")
        return out
    try:
        doc = json.loads(Path(listing_file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        warn(f"型つきの成果物の一覧 {listing_file} が読めない: {e}")
        return out
    if not isinstance(doc, dict):
        warn(f"型つきの成果物の一覧 {listing_file} が JSON のオブジェクトでない")
        return out
    if doc.get("runId") not in (None, run_id):
        warn(f"型つきの成果物の一覧 {listing_file} がほかの run の物（{doc.get('runId')}。この run は {run_id}）")
        return out
    errors = doc.get("errors", [])
    if not isinstance(errors, list):
        warn(f"型つきの成果物の一覧 {listing_file} の errors が配列でない（読めなかった記録を数えられない）")
        errors = []
    for e in errors:
        e = e if isinstance(e, dict) else {}
        code = f"・{e['code']}" if e.get("code") else ""
        warn(f"実行基盤が読めなかった成果物の記録 {e.get('path') or '（名の無い記録）'}（{e.get('kind') or '読めない'}{code}）。直に開いて確かめる")
    by_type = doc.get("artifactsByType")
    if not isinstance(by_type, dict):
        warn(f"型つきの成果物の一覧 {listing_file} の artifactsByType がオブジェクトでない")
        return out
    own = own_prefix(execution)
    for kind, entries in by_type.items():
        if not isinstance(entries, list):
            warn(f"型つきの成果物の一覧の artifactsByType['{kind}'] が配列でない")
            continue
        for a in entries:
            if not (isinstance(a, dict) and isinstance(a.get("nodeId"), str) and isinstance(a.get("path"), str)):
                warn(f"型つきの成果物の一覧の artifactsByType['{kind}'] の行の形が違う: {a!r}")
                continue
            if a.get("runId") not in (None, run_id):
                continue
            if own and a["nodeId"].startswith(own):
                continue
            include = _include(a["nodeId"])
            body = None
            try:
                body = json.loads((Path(artifacts_dir) / a["path"]).read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                warn(f"成果物 {kind} の中身 {a['path']}（{a['nodeId']}）が読めない: {e}")
            loop = [(f.get("groupId"), f.get("iteration")) for f in a.get("loopGroupPath") or [] if isinstance(f, dict)]
            out["by_type"].setdefault(kind, []).append({"include": include, "loop": loop, "node": a["nodeId"], "path": a["path"],
                                                        "produced_at": a.get("producedAt"), "body": body})
    return out


def read_listing() -> dict:
    """この節に届いた一覧（実行基盤が script の節に渡す環境変数）を listing で読む"""
    return listing(os.environ.get("TYPED_ARTIFACTS_FILE", ""), os.environ.get("ARTIFACTS_DIR", ""),
                   os.environ.get("WORKFLOW_ID", ""), os.environ.get("ARCHON_NODE_EXECUTION", ""))


def parse(name: str, raw: str) -> tuple:
    """入力の字を (値, 読めなかった訳) に。空と字の null は (None, "")。JSON でない・オブジェクトでない時も落とさず None"""
    try:
        value = boundary.parsed(raw)
    except ValueError as e:
        return None, f"入力 {name} が JSON でない（{e}）"
    if value is None:
        return None, ""
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


def stages_unread(value) -> str:
    """段の表（入力 stages）が表の形でない訳（形が合えば ""）。表は {nodes: {役の名: 節の名}, links: [行]}。届かない・形が違う表は
    段の名も続きの切れ目も決められないので、第 2 の道を置かず読めない入力に数える"""
    if value is None:
        return "入力 stages が届いていない（段の名と出力の続きの切れ目を決められない）"
    if not (isinstance(value, dict) and isinstance(value.get("nodes"), dict) and isinstance(value.get("links"), list)):
        return "入力 stages が段の表 {nodes, links} の形でない（段の名と出力の続きの切れ目を決められない）"
    return ""


def line_values(unread: list, unopened: list) -> dict:
    """線の値を {stops, stages, prior_failures, deferred, widened, final_reasons, spec_changed, spec_unchecked, redepth, optional} に
    （欄の名は - を _ に）。並びの入力は配列でなければ空にし、JSON でない入力は訳を unread に積む（黙って空にしない）。段の表は表の形でなければ
    空にして訳を unread に積む。依頼の前の失敗の指し札は開けたパスの字にする"""
    out = {}
    for name, raw in LINE.items():
        key = name.replace("-", "_")
        try:
            value = boundary.parsed(raw)
            broken = False
        except ValueError as e:
            unread.append(f"入力 {name} が JSON でない（{e}）")
            value, broken = None, True
        if name in LISTS and not isinstance(value, list):
            unread += [f"入力 {name} が配列でない"] if value is not None else []
            value = []
        if name == "stages":
            why = "" if broken else stages_unread(value)
            unread += [why] if why else []
            value = value if not why and not broken else {}
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


def main() -> dict:
    sys.path.append(str(boundary.lib_root()))
    import outcome
    import rolekit
    import runreport
    import userenv

    unread, unopened, returns, gates = [], [], {}, {}
    for rid, raw in RETURNS.items():
        value, why = parse(rid, raw)
        returns[rid] = opened(value, unopened, rid)
        unread += [why] if why else []
    for gid, raw in GATES.items():
        gates[gid], why = parse(gid, raw)
        unread += [why] if why else []
    line = line_values(unread, unopened)
    problems, notes = outcome.record_problems(returns, gates, unread=unread, unopened=unopened, stages=line["stages"])
    record = start_record(problems)
    start = record or {}
    rows, transcript_why = boundary.transcript()
    typed_listing = read_listing()
    typed_listing["warnings"] = [*notes, *typed_listing["warnings"], *([transcript_why] if transcript_why else [])]
    facts = runreport.transcript_facts(rows, exclude_prefix=own_prefix(os.environ.get("ARCHON_NODE_EXECUTION", "")),
                                       optional=[x for x in line["optional"] if isinstance(x, str)])
    decided = outcome.decide_outcome(returns, gates, {"start_ok": bool(start), "record_problems": problems,
                                                      "failed": facts["failed"], **runreport.outcome_facts(start, facts, line)})
    built = runreport.build(returns, gates, typed_listing, facts, *decided, out_dir=out_dir(), start=start, problems=problems,
                            run_id=os.environ.get("WORKFLOW_ID", ""), transcript_why=transcript_why, repo=Path.cwd(), line=line,
                            user_env=userenv.ran(boundary.line_place()))
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
        import userenv
        out["report"] = rel(runreport.fallback_report(out_dir(), why, runreport.UNWRITTEN,
                                                      user_env=userenv.ran(boundary.line_place())))
    except Exception:  # noqa: BLE001 — lib/ を読めなくても、置き場に書けなくても返る
        out["report"] = unwritten(why)
    out["facts_file"] = out["report"]["path"]
    return out


if __name__ == "__main__" and boundary is None:   # 境の口を読めない時
    why = failed_line("報告の事実", unread)
    ptr = unwritten(why)
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
