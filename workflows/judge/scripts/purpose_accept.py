# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""目的の役の返答を受け付ける（lib/judge_accept.check_purpose）。通れば judge/purpose.json と purpose-means.json。拒否は
judge/rejects-purpose.json に積み、3 回目で done。諦めたら止めの控え（stopby.PURPOSE）を置く。落ちずに {ok, done, reason} を返す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import accept  # noqa: E402
import judge_accept as ja  # noqa: E402
import rolekit  # noqa: E402
import stopby  # noqa: E402

KEYS = accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", ""))
jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
jdir.mkdir(parents=True, exist_ok=True)
out = ja.accept_round(
    jdir, ja.PURPOSE_ROLE, os.environ.get("INPUTS_REPLY", ""), lambda reply: ja.check_purpose(reply, jdir, Path.cwd(), keys=KEYS),
    on_give_up=lambda: ja.write_stop(jdir, stopby.PURPOSE, rolekit.given_up_reason(jdir, ja.PURPOSE_ROLE)))
boundary.returns({"ok": bool(out["ok"]), "done": bool(out["done"]), "reason": str(out["reason"])})
