"""並行 PR の役の返答を受け付ける: 投稿していない・作業ツリーを変えていない・外す hunk が合う（lib/judge_accept.pr_accept）。
3 回目の拒否で done、諦めたら止めの控え（stopby.PR）を置く"""
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
    out = ja.pr_accept(jdir, raw, Path.cwd())
except Exception as e:  # noqa: BLE001  （受け付けは落ちない）
    import rolekit  # noqa: E402
    out = rolekit.with_done(jdir, "pr-check", {"ok": False, "reason": f"受け付けが落ちた（{type(e).__name__}: {e}）"})
boundary.returns({"ok": out["ok"], "done": out["done"], "reason": out["reason"]})
