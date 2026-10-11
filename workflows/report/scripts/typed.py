# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""型つきの成果物の一覧（$TYPED_ARTIFACTS_FILE）を読む部品（workflows/AGENTS.md の E5「読む部品は report ブロックの中に置く」）。
節の script でなく、facts.py が import する。

一覧の形は止めた Archon の packages/workflows/src/schemas/node-artifact.ts の nodeArtifactsListingSchema
（{runId, artifactsByType: {型: [{nodeId, outputType, loopGroupPath?, path, runId, producedAt, size}]}, errors: [{path, kind, code?}]}）。
型の名と include の名は決め打たず、一覧に在る物で組む。読めない物は名前つきの限りとして warnings に入れ、黙らない
（ASF の .archon/workflows/sdlc/.shared/report.ts:126-206 の型）。
"""
import json
import os
from pathlib import Path


def _include(node_id: str) -> str:
    """節の id の include の頭（最初の __ より前。無ければ空）"""
    head, sep, _ = node_id.partition("__")
    return head if sep else ""


def own_include(execution: str) -> str:
    """自分の節の実行の記録（ARCHON_NODE_EXECUTION の JSON）の path から、自分の include の頭"""
    try:
        doc = json.loads(execution) if execution else {}
    except ValueError:
        return ""
    path = doc.get("path") if isinstance(doc, dict) else None
    return _include(path.rsplit(".", 1)[-1]) if isinstance(path, str) else ""


def listing(listing_file: str, artifacts_dir: str, run_id: str, execution: str = "") -> dict:
    """{by_type: {型: [{include, loop, node, path, produced_at, body}]}, warnings: [文]}。body は中身の JSON（読めなければ None と
    注意）。ほかの run の行と自分の include の行は数えない。一覧の errors は 1 件ずつ warnings に入れる"""
    out = {"by_type": {}, "warnings": []}
    warn = out["warnings"].append
    if not listing_file:
        warn("型つきの成果物の一覧がこの節に届いていない（TYPED_ARTIFACTS_FILE が空。dry-run か、一覧の無い節）")
        return out
    try:
        listing = json.loads(Path(listing_file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        warn(f"型つきの成果物の一覧 {listing_file} が読めない: {e}")
        return out
    if not isinstance(listing, dict):
        warn(f"型つきの成果物の一覧 {listing_file} が JSON のオブジェクトでない")
        return out
    if listing.get("runId") not in (None, run_id):
        warn(f"型つきの成果物の一覧 {listing_file} がほかの run の物（{listing.get('runId')}。この run は {run_id}）")
        return out
    errors = listing.get("errors", [])
    if not isinstance(errors, list):
        warn(f"型つきの成果物の一覧 {listing_file} の errors が配列でない（読めなかった記録を数えられない）")
        errors = []
    for e in errors:
        e = e if isinstance(e, dict) else {}
        code = f"・{e['code']}" if e.get("code") else ""
        warn(f"実行基盤が読めなかった成果物の記録 {e.get('path') or '（名の無い記録）'}（{e.get('kind') or '読めない'}{code}）。直に開いて確かめる")
    by_type = listing.get("artifactsByType")
    if not isinstance(by_type, dict):
        warn(f"型つきの成果物の一覧 {listing_file} の artifactsByType がオブジェクトでない")
        return out
    own = own_include(execution)
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
            include = _include(a["nodeId"])
            if own and include == own:
                continue
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
