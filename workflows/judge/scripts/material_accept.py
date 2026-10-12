# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""素材集めの役（with: の role）の返答を受け付ける（lib/judge_accept.material_take）。通れば judge/material-<役>.json。
拒否は judge/rejects-<役>.json に積み、3 回目で done（諦めても止めない。素材の状態は diagnose-prep が組む）。{ok, done, reason}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import accept  # noqa: E402
import judge_accept as ja  # noqa: E402

jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
jdir.mkdir(parents=True, exist_ok=True)
role = os.environ.get("INPUTS_ROLE", "")
KEYS = accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", ""))
out = ja.accept_round(jdir, role or "material", os.environ.get("INPUTS_REPLY", ""),
                      lambda reply: ja.material_take(jdir, role, reply, Path.cwd(), keys=KEYS))
boundary.returns({"ok": bool(out["ok"]), "done": bool(out["done"]), "reason": str(out["reason"])})
