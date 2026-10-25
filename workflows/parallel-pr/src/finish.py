"""並行 PR の出口（docs/design/parallel-pr.md の 3 節の finish）: place の控えを読み、block の返りを組む。どの段が落ちても落ちない
（落とし穴 K1・K13）。

- 役を諦めた（rolekit.given_up_reason が空でない）: status failed・stop_reason works:pr・material は not_run
- 素材の控えが無い（scan が落ちた・役の輪が回らなかった）: status failed・stop_reason works:pr・material は not_run（無言の空を作らない）。
  ok は偽（元の工場では役の輪が落ちると判定が止まった。止めは再開できる）
- ほか: status は素材の札、reason は scan の reason
"""
import json
import pathlib

import ports

import jsonfile   # lib/
import rolekit    # lib/
import stopby     # lib/

from . import files, report


def _read(path):
    return jsonfile.read_or(path, None)


def _path(place, name, *, nonempty=False):
    """指すファイル（無い・nonempty で空なら None）"""
    path = pathlib.Path(place) / name
    if not path.is_file() or nonempty and not _read(path):
        return None
    return path


def _point(path, point):
    return None if path is None else point(path)


def _proof_failure(place) -> str:
    """読んだ証拠を集める node が落ちた記録（lib/reads.guarded が置く。名に時刻が入る）の訳。無ければ空"""
    for path in sorted(pathlib.Path(place).glob(files.READS_FAILED), reverse=True):
        doc = _read(path)
        sources = doc.get("sources") if isinstance(doc, dict) else None
        return str((sources or {}).get("why") or "訳が記録に無い") if isinstance(sources, dict) else "記録が読めない"
    return ""


def build(place) -> dict:
    place = pathlib.Path(place)
    scan = _read(place / files.SCAN)
    scan = scan if isinstance(scan, dict) else {}
    said = str(scan.get("reason") or "")
    gave_up = rolekit.given_up_reason(place, files.ROLE)
    doc = _read(place / files.MATERIAL)
    material = ((doc.get("materials") or {}).get("parallel_pr") if isinstance(doc, dict) else None)
    if gave_up:
        status, stop, reason = "failed", stopby.PR, gave_up
        material = {"status": "not_run", "reason": gave_up}
    elif not isinstance(material, dict):
        status, stop = "failed", stopby.PR
        reason = f"並行 PR の確かめが走らなかった（{said or '機械の道も役の返答の記録も無い'}）"
        material = {"status": "not_run", "reason": reason}
    else:
        status, stop, reason = material.get("status", "failed"), "", said
    drafts_file = _read(place / files.DRAFTS)
    evidence = _read(place / files.READS)
    missing = evidence.get("missing") if isinstance(evidence, dict) and isinstance(evidence.get("missing"), list) else []
    return {"ok": stop == "", "status": status, "stop_reason": stop, "reason": reason, "material": material,
            "excluded": _point(_path(place, files.EXCLUDED), lambda p: ports.pointer(p, "json(shared:excluded.schema.json)")),
            "drafts": _point(_path(place, files.DRAFTS, nonempty=True), lambda p: ports.pointer(p, "json(shared:pr-drafts.schema.json)")),
            "reads": _point(_path(place, files.READS), lambda p: ports.pointer(p, "json(shared:reads.schema.json)")),
            "downgrades": files.DOWNGRADES,
            "report": report.lines(status, reason, material, drafts_file if isinstance(drafts_file, list) else [], missing,
                                  _proof_failure(place))}


def fallback(why: str) -> dict:
    """出口の中が落ちた時の返り（形は同じ。ok は真のまま——止めるかは line が決め、確かめられなかったと status が言う）"""
    reason = f"並行 PR の出口が落ちた（{why}）"
    return {"ok": True, "status": "failed", "stop_reason": "", "reason": reason, "material": {"status": "not_run", "reason": reason},
            "excluded": None, "drafts": None, "reads": None, "downgrades": files.DOWNGRADES,
            "report": [f"並行 PR: 確かめが終わらなかった（{reason}）"]}
