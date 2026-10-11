# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""目的の役の材料を置く（lib/judge_accept.purpose_prep）。依頼から前の run の判断を外した写し judge/purpose-request.json と、
それ・PR の説明・前提の実測を並べた judge/purpose-brief.md。止めの控えが在れば go 偽。支度が落ちたら止めの控え（stopby.PURPOSE）を置く。{go, brief_file, reason}"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import judge_accept as ja  # noqa: E402

jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
jdir.mkdir(parents=True, exist_ok=True)
try:
    stop = ja.read_stop(jdir)
    if stop:
        out = {"go": False, "brief_file": "", "reason": f"止まっている（{stop['stop_reason']}: {stop.get('reason', '')}）——目的の役を起こさない"}
    else:
        start = ja.read_json(jdir / ja.START_FILE) or ja.start_view({})
        out = ja.purpose_prep(jdir, Path.cwd(), start)
except Exception as e:  # noqa: BLE001  落ちずに理由を返す
    why = f"目的の役の支度が落ちた（{type(e).__name__}: {e}）"
    ja.write_stop(jdir, ja.stopby.PURPOSE, why)
    out = {"go": False, "brief_file": "", "reason": why}
boundary.returns({"go": bool(out["go"]), "brief_file": str(out["brief_file"]), "reason": str(out["reason"])})
