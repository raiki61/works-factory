# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""素材集め 11 本の要否を元の条件で決める（lib/judge_accept.material_route）。止めの控えが在れば全部偽。
対象差分を judge/diff.patch に、要否と回さない素材の埋めを judge/material-route.json に置く"""
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
    out = ja.material_route(jdir, Path.cwd())
except Exception as e:  # noqa: BLE001  落ちずに全部偽と理由を返す
    out = {**{ja.route_key(r): False for r in ja.MATERIAL_ROLES}, "reason": f"素材の要否を決められない（{type(e).__name__}: {e}）"}
boundary.returns({**{ja.route_key(r): bool(out[ja.route_key(r)]) for r in ja.MATERIAL_ROLES}, "reason": str(out["reason"])})
