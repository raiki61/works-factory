"""読んだ証拠（docs/design/plan-review.md の 1.3 の review-reads。今の lib/boardview.py の collect_reads の写し）。

この include の審査の役が、機械が渡したパス（材料のファイル review-material-<n>.md と方針の写し）を読んだかを lib/reads の collect で
集め、place に reads-<役>.json と索引を書く。記録は入口が intake.json を書いた時刻から後の、材料のファイルを読んだ session の行で切る
（材料のファイルはこの役だけに渡す物）。形 replan は役の名を reads.role_key の案の直しの名にする。形 text は材料のファイルが無いので、
方針の写しを渡した時だけ、その写しを目印に集める（渡したパスが無ければ索引に訳だけを書く）。木の往復は、束ね役の Agent の起動の数と
型ごとの数を、書いた下請けの項目の材料のファイルの数と並べて trace に AGENT_OP で残す（拒まない。測る）。受け付けの条件にしない。

- collect(place, log, repo) -> {ok: True, missing, index_file}（scripts/review_reads.py が lib/reads.guarded で包む）
- evidence(place) -> (読んだ証拠のパスか None, 欠けたパスの並び, 集める node が落ちた訳): 出口が返りと報告の行に使う
"""
from __future__ import annotations

import collections
import pathlib

import jsonfile    # lib/
import planmarks   # lib/。append_trace
import reads       # lib/

from src import files

AGENT_OP = "plan_review_agents"   # 下請けの起動の数の trace の行（今の planblk.AGENT_OP）
NOTHING_HANDED = "機械が渡したパスが無い（方針の写しの無い形 text は、指示に全部を貼る）"


def _role(doc: dict) -> tuple[str, bool]:
    """(役の名, 案の直しか)"""
    if doc.get("form") == "text":
        return files.TEXT_READS_ROLE, False
    return files.READS_ROLE, doc.get("form") == "replan"


def collect(place, log, repo) -> dict:
    place = pathlib.Path(place)
    doc = jsonfile.read_or(place / files.INTAKE)
    if not isinstance(doc, dict):
        raise ValueError(f"入口の控え {place / files.INTAKE} が無いか読めない")
    role, again = _role(doc)
    since = reads.stamp((place / files.INTAKE).stat().st_mtime)
    materials = sorted(str(p) for p in place.glob(files.MATERIAL.format(n="*")))
    policy = [doc["policy_copy"]] if doc.get("policy_copy") else []
    own = materials or policy
    index_name = reads.index_name(files.READS_ROLE, again)
    if not own:
        out = jsonfile.write(place / index_name, {reads.role_key(role, again): None, reads.INDEX_WHY: NOTHING_HANDED})
        return {"ok": True, "missing": [], "index_file": str(out)}
    got = reads.collect(place, role, [*materials, *policy], log, own=own, since=since, repo=repo, replan=again)
    out = jsonfile.write(place / index_name, {reads.role_key(role, again): got["reads_file"]})
    if doc.get("tree"):
        rows, why = got["records"], got["sources"]["why"]
        kinds = dict(collections.Counter(str(t or "") for t in reads.tool_inputs(rows, "Agent")))
        planmarks.append_trace(place, AGENT_OP, launched=None if rows is None else reads.tool_count(rows, "Agent"), types=kinds,
                               item_files=len(list((place / files.ITEMS_DIR).glob("item-*.md"))),
                               synergy_files=int((place / files.SYNERGY_ITEM).is_file()), **({"why": why} if why else {}))
    return {"ok": True, "missing": got["missing"], "index_file": str(out)}


def evidence(place) -> tuple:
    """(この include の読んだ証拠のパスか None, 欠けたパス, 集める node が落ちた訳)"""
    place = pathlib.Path(place)
    found, missing = None, []
    for name in files.READS_FILES:
        doc, _ = reads.read_evidence(place / name) if (place / name).is_file() else (None, "")
        if doc is not None:
            found, missing = place / name, [str(m) for m in doc["missing"]]
            break
    failed = ""
    for path in sorted((p for pattern in files.READS_FAILED for p in place.glob(pattern)), key=lambda p: p.name, reverse=True):
        doc = jsonfile.read_or(path)
        sources = doc.get("sources") if isinstance(doc, dict) else None
        if isinstance(sources, dict) and sources.get("why"):
            failed = str(sources["why"])
            break
    return found, missing, failed
