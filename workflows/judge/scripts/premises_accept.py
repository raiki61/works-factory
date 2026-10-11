"""前提の実測役の返答を受け付ける（lib/judge_accept.check_premises）。拒否は judge/rejects-premises.json に積み、3 回目で done。
諦めたら止めの控え（stopby.PREMISES）を置く。落ちずに {ok, done, reason} を返す"""
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
    if reply is None:
        got = {"ok": False, "reason": why}
    else:
        got = ja.check_premises(reply, jdir, Path.cwd(), ja.read_json(jdir / ja.REQUEST_FILE, []) or [])
except Exception as e:  # noqa: BLE001  受け付けは落ちない
    got = {"ok": False, "reason": f"受け付けの中で例外（{type(e).__name__}: {e}）"}
try:
    out = rolekit.with_done(jdir, ja.PREMISES_ROLE, {"ok": got["ok"], "reason": got["reason"]})
    if out["done"] and not out["ok"]:
        ja.write_stop(jdir, stopby.PREMISES, rolekit.given_up_reason(jdir, ja.PREMISES_ROLE) or out["reason"])
except Exception as e:  # noqa: BLE001
    out = {"ok": False, "done": True, "reason": f"拒否の控えが扱えない（{type(e).__name__}: {e}）"}
boundary.returns({"ok": bool(out["ok"]), "done": bool(out["done"]), "reason": str(out["reason"])})
