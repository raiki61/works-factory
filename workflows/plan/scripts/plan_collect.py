# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返す節（返りの約束の欄を組む。lib/planfile.collect・placeholders）。深さは直す義務の単位（planfile.owed_order）だけを決める。
案の直しの周で役が諦めた時は、項目ごとの諦めの行を plan-fields.json の隣に置く（planfile.note_gave_up）。
落ちない: 境の口と lib の import から先の誤りは全部捕まえ、標準ライブラリだけで ready: false と訳を周のフォルダの collect-error.txt に
書き、指し札の先（plan-fields.json・structure-state.json・ripple.json）が在って空でない形で返す（線は落ちた返す節の先へ進めない）"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

# lib/planfile.py の PLAN_DIR・ROUND_FILE・RIPPLE_FILE・DESIGN_FILE・UNREAD_STRUCTURE、planmarks.FIELDS_FILE、structmark.STATE_FILE と
# 同じ字。試験が突き合わせる
ROUND_FILE = "round.json"
COLLECT_ERROR_FILE = "collect-error.txt"
FIELDS_FILE = "plan-fields.json"
STATE_FILE = "structure-state.json"
DESIGN_FILE = "design.jsonl"
RIPPLE_FILE = "ripple.json"
PLAN_DIR = "plan"
UNREAD_STRUCTURE = "structure/unread"


def collected() -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    sys.path.append(str(boundary.lib_root()))
    import depth
    import planfile

    art = Path(os.environ["ARTIFACTS_DIR"])
    round_dir = art / os.environ["INPUTS_DIR"]
    rnd = planfile.read_round(round_dir)
    start, _ = planfile.read_pointed(os.environ["INPUTS_START"], boundary.pointed)
    start = start if isinstance(start, dict) else {}
    judgment, _ = planfile.read_judgment(os.environ["INPUTS_JUDGMENT"], start, boundary.pointed,
                                       ties=os.environ.get("INPUTS_ANSWER_TIES", ""), materials=os.environ.get("INPUTS_MATERIALS", ""))
    got = planfile.collect(round_dir, unit_ids=planfile.owed_order(judgment) if isinstance(judgment, dict) else [],
                           thickness=start.get("thickness") or "", checked=depth.has_checks(start))
    if not got["ready"]:
        conflicts, _ = planfile.read_pointed(os.environ["INPUTS_CONFLICTS"], boundary.pointed)
        planfile.note_gave_up(round_dir, art / planfile.PLAN_DIR, conflicts)
    reason = "" if got["ready"] else planfile.why_not_ready(round_dir)
    paths = planfile.placeholders(round_dir, art / planfile.PLAN_DIR / rnd["structure"], reason)
    return {"ready": got["ready"], **{k: boundary.pointer(p.relative_to(art).as_posix()) for k, p in paths.items()},
            "depth": got["depth"], "round": rnd["round"]}


def _filled(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _write(path: Path, doc) -> None:
    if not _filled(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def failed(error: BaseException) -> dict:
    """ready: false と、在って空でない指し札の先。境の口が読めなかった時にも出せるよう、札は境の口を通さずに組む"""
    art = Path(os.environ["ARTIFACTS_DIR"])
    round_dir = art / os.environ.get("INPUTS_DIR", "")
    reason = f"出力ノードの中で誤りが起きた: {type(error).__name__}: {' '.join(str(error).split())}"
    try:
        rnd = json.loads((round_dir / ROUND_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rnd = {}
    rnd = rnd if isinstance(rnd, dict) else {}
    k = rnd.get("round") if isinstance(rnd.get("round"), int) and rnd["round"] >= 1 else 1
    structure = art / PLAN_DIR / (rnd["structure"] if isinstance(rnd.get("structure"), str) else UNREAD_STRUCTURE)
    round_dir.mkdir(parents=True, exist_ok=True)
    structure.mkdir(parents=True, exist_ok=True)
    (round_dir / COLLECT_ERROR_FILE).write_text(reason + "\n", encoding="utf-8")
    _write(round_dir / FIELDS_FILE, {"round": k, "fields": []})
    if not (structure / DESIGN_FILE).is_file():
        (structure / DESIGN_FILE).write_bytes(b"")
    _write(structure / STATE_FILE, {"status": "failed", "reason": reason, "design_file": str(structure / DESIGN_FILE), "wall_s": 0})
    _write(round_dir / RIPPLE_FILE, {"items": [], "error": reason})
    run_id = os.environ.get("WORKFLOW_ID", "")
    return {"ready": False, **{k: {"type": "archon_artifact", "run_id": run_id, "path": p.relative_to(art).as_posix()}
                               for k, p in (("plan", round_dir / FIELDS_FILE), ("structure", structure / STATE_FILE),
                                            ("ripple", round_dir / RIPPLE_FILE))},
            "depth": [], "round": k}


def main() -> int:
    try:
        out = collected()
    except Exception as e:  # noqa: BLE001  返す節は落ちない（誤りは訳に残して ready: false）
        out = failed(e)
    print(json.dumps(out, ensure_ascii=False, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
