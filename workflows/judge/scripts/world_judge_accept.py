"""web の役の返答を受け付ける: 抜き書きを取り直した本文で照らし、字のまま無い抜き書きを指す根拠を外す（lib/judge_accept.world_accept）。3 回目の拒否で done。諦めても run は止めない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import judge_accept as ja  # noqa: E402

jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
jdir.mkdir(parents=True, exist_ok=True)
raw = os.environ.get("INPUTS_REPLY", "")
try:
    out = ja.world_accept(jdir, "world-judge", raw)
except Exception as e:  # noqa: BLE001  （受け付けは落ちない）
    import rolekit  # noqa: E402
    out = rolekit.with_done(jdir, "world-judge", {"ok": False, "reason": f"受け付けが落ちた（{type(e).__name__}: {e}）"})
boundary.returns({"ok": out["ok"], "done": out["done"], "reason": out["reason"]})
