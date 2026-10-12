# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""再審の役の返答を受け付け、通れば R/judgment.json と単位の前後の差を書く。輪を抜ける時（通った・3 回目の拒否）に
再審の出口 R/rejudge-exit.json を書く（lib/judge_accept.rejudge_take・rejudge_collect）"""
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
rdir = boundary.resolve(boundary.pointer(ja.REJUDGE_DIR))
rdir.mkdir(parents=True, exist_ok=True)
KEYS = accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", ""))
out = ja.accept_round(rdir, ja.REJUDGE_ROLE, os.environ.get("INPUTS_REPLY", ""),
                      lambda reply: ja.rejudge_take(jdir, rdir, reply, Path.cwd(), keys=KEYS))
if out["done"]:
    try:
        ja.rejudge_collect(rdir)
    except Exception as e:  # 出口が書けなくても輪は抜ける。verdict が止めの控えを読む
        ja.write_stop(rdir, ja.stopby.REJUDGE, f"再審の出口を書けない（{type(e).__name__}: {e}）")
boundary.returns({"ok": out["ok"], "done": out["done"], "reason": out["reason"]})
