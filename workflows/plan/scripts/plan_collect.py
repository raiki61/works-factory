"""返す節（返りの約束の欄を組む。lib/planfile.collect・placeholders）。落ちない: 中の誤りを全部捕まえ、ready: false と訳を
plan/r<k>/collect-error.txt に書き、指し札の先（plan-fields.json・structure-state.json・ripple.json）が在って空でない形で返す
（線は落ちた返す節の先へ進めない）"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import planfile  # noqa: E402


def main() -> None:
    art = Path(os.environ["ARTIFACTS_DIR"])
    plan_dir = art / planfile.PLAN_DIR
    round_dir = planfile.round_dir_of(plan_dir, os.environ["INPUTS_DIR"])
    reason = ""
    rnd = planfile.read_round(round_dir)
    try:
        start, _ = planfile.read_pointed(os.environ["INPUTS_START"], boundary.resolve)
        start = start if isinstance(start, dict) else {}
        units = planfile.units_of(os.environ["INPUTS_UNITS"])
        ids = [u["id"] for u in units if isinstance(u, dict) and isinstance(u.get("id"), str)] if isinstance(units, list) else []
        got = planfile.collect(round_dir, unit_ids=ids, thickness=start.get("thickness") or "",
                               checked=bool(start.get("test_cmd") or start.get("tdd_suite")))
        if not got["ready"]:
            reason = planfile.why_not_ready(round_dir)
    except Exception as e:  # noqa: BLE001  返す節は落ちない（誤りは訳に残して ready: false）
        got = {"ready": False, "depth": []}
        reason = f"返す節の中で誤りが起きた: {type(e).__name__}: {e}"
        round_dir.mkdir(parents=True, exist_ok=True)
        (round_dir / planfile.COLLECT_ERROR_FILE).write_text(reason + "\n", encoding="utf-8")
    paths = planfile.placeholders(round_dir, plan_dir / rnd["structure"], reason)
    boundary.returns({"ready": got["ready"], **{k: boundary.pointer(p.relative_to(art).as_posix()) for k, p in paths.items()},
                      "depth": got["depth"], "round": planfile.round_no(round_dir)})


if __name__ == "__main__":
    main()
