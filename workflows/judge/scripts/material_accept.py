"""素材集めの役（with: の role）の返答を受け付ける（lib/judge_accept.material_take）。通れば judge/material-<役>.json。
拒否は judge/rejects-<役>.json に積み、3 回目で done（諦めても止めない。素材の状態は diagnose-prep が組む）。{ok, done, reason}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import judge_accept as ja  # noqa: E402
import rolekit  # noqa: E402

jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
jdir.mkdir(parents=True, exist_ok=True)
role = os.environ.get("INPUTS_ROLE", "")
try:
    reply, why = rolekit.parse_reply(os.environ.get("INPUTS_REPLY", ""))
    got = {"ok": False, "reason": why} if reply is None else ja.material_take(jdir, role, reply, Path.cwd())
except Exception as e:  # noqa: BLE001  受け付けは落ちない
    got = {"ok": False, "reason": f"受け付けの中で例外（{type(e).__name__}: {e}）"}
try:
    out = rolekit.with_done(jdir, role or "material", {"ok": got["ok"], "reason": got["reason"]})
except Exception as e:  # noqa: BLE001
    out = {"ok": False, "done": True, "reason": f"拒否の控えが扱えない（{type(e).__name__}: {e}）"}
boundary.returns({"ok": bool(out["ok"]), "done": bool(out["done"]), "reason": str(out["reason"])})
