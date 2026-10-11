# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""世界の解の段の出口: 行を judge/world.jsonl に、段の控えを judge/world-state.json に書く（lib/judge_accept.world_finish）。
落ちた段・網に出られない段も run を止めない（持ち主の決め world）"""
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
    out = ja.world_finish(jdir)
except Exception as e:  # noqa: BLE001  （世界の解の段は run を止めない）
    out = {"ok": False, "status": "failed", "reason": f"出口が落ちた（{type(e).__name__}: {e}）"}
boundary.returns(out)
