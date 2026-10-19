"""並行 PR の出口（docs/design/parallel-pr.md の 3 節の finish）: place の控えを読み、block の返りを組む。どの段が落ちても落ちない
（落とし穴 K1・K13）。

- 役を諦めた（rolekit.given_up_reason が空でない）: status failed・stop_reason works:pr・material は not_run
- 素材の控えが無い（scan が落ちた・役の輪が回らなかった）: status failed・stop_reason ""・material は not_run（無言の空を作らない）。ok は真のまま
- ほか: status は素材の札、reason は scan の reason
"""
import json
import pathlib

import jsonfile   # lib/
import rolekit    # lib/
import stopby     # lib/

from . import files, report


def _read(path):
    return jsonfile.read_or(path, None)


def _pointer(place, name, pointer, *, nonempty=False):
    path = pathlib.Path(place) / name
    if not path.is_file():
        return None
    if nonempty and not _read(path):
        return None
    return pointer(path)


def build(place, pointer) -> dict:
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
        status, stop = "failed", ""
        reason = f"並行 PR の確かめが走らなかった（{said or '機械の道も役の返答の記録も無い'}）"
        material = {"status": "not_run", "reason": reason}
    else:
        status, stop, reason = material.get("status", "failed"), "", said
    drafts_file = _read(place / files.DRAFTS)
    evidence = _read(place / files.READS)
    missing = evidence.get("missing") if isinstance(evidence, dict) and isinstance(evidence.get("missing"), list) else []
    return {"ok": stop == "", "status": status, "stop_reason": stop, "reason": reason, "material": material,
            "excluded": _pointer(place, files.EXCLUDED, pointer), "drafts": _pointer(place, files.DRAFTS, pointer, nonempty=True),
            "reads": _pointer(place, files.READS, pointer), "downgrades": files.DOWNGRADES,
            "report": report.lines(status, reason, material, drafts_file if isinstance(drafts_file, list) else [], missing)}


def fallback(why: str) -> dict:
    """出口の中が落ちた時の返り（形は同じ。ok は真のまま——止めるかは line が決め、確かめられなかったと status が言う）"""
    reason = f"並行 PR の出口が落ちた（{why}）"
    return {"ok": True, "status": "failed", "stop_reason": "", "reason": reason, "material": {"status": "not_run", "reason": reason},
            "excluded": None, "drafts": None, "reads": None, "downgrades": files.DOWNGRADES,
            "report": [f"並行 PR: 確かめが終わらなかった（{reason}）"]}
