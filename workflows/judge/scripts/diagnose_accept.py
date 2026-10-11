"""判定役の返答を受け付ける（lib/judge_accept.accept）。拒否は rolekit.with_done で数え、3 回目で done。諦めた時は止めの控えを置く（_give_up）"""
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
try:
    got = ja.accept(jdir, os.environ.get("INPUTS_REPLY", ""), Path.cwd())
except Exception as e:   # 受け付けは落ちない（返答の形・lib の誤りも拒否の理由にする）
    got = {"ok": False, "reason": f"受け付けの中で例外（{type(e).__name__}: {e}）"}
out = rolekit.with_done(jdir, ja.DIAGNOSE_ROLE, {"ok": got.get("ok") is True, "reason": str(got.get("reason") or "")})
if out["done"] and not out["ok"]:
    ja._give_up(jdir)
boundary.returns({"ok": out["ok"], "done": out["done"], "reason": out["reason"]})
