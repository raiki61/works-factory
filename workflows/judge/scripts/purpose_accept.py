"""目的の役の返答を受け付ける（lib/judge_accept.check_purpose）。通れば judge/purpose.json と purpose-means.json。拒否は
judge/rejects-purpose.json に積み、3 回目で done。諦めたら止めの控え（stopby.PURPOSE）を置く。落ちずに {ok, done, reason} を返す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import judge_accept as ja  # noqa: E402
import rolekit  # noqa: E402
import stopby  # noqa: E402

jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
jdir.mkdir(parents=True, exist_ok=True)
try:
    reply, why = rolekit.parse_reply(os.environ.get("INPUTS_REPLY", ""))
    got = {"ok": False, "reason": why} if reply is None else ja.check_purpose(reply, jdir, Path.cwd())
except Exception as e:  # noqa: BLE001  受け付けは落ちない
    got = {"ok": False, "reason": f"受け付けの中で例外（{type(e).__name__}: {e}）"}
try:
    out = rolekit.with_done(jdir, ja.PURPOSE_ROLE, {"ok": got["ok"], "reason": got["reason"]})
    if out["done"] and not out["ok"]:
        ja.write_stop(jdir, stopby.PURPOSE, rolekit.given_up_reason(jdir, ja.PURPOSE_ROLE) or out["reason"])
except Exception as e:  # noqa: BLE001
    out = {"ok": False, "done": True, "reason": f"拒否の控えが扱えない（{type(e).__name__}: {e}）"}
boundary.returns({"ok": bool(out["ok"]), "done": bool(out["done"]), "reason": str(out["reason"])})
