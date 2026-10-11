"""再審の役の返答を受け付け、通れば R/judgment.json と単位の前後の差を書く。輪を抜ける時（通った・3 回目の拒否）に
再審の出口 R/rejudge-exit.json を書く（lib/judge_accept.rejudge_take・rejudge_collect）"""
import json
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
rdir = boundary.resolve(boundary.pointer(ja.REJUDGE_DIR))
rdir.mkdir(parents=True, exist_ok=True)
try:
    reply, why = rolekit.parse_reply(os.environ.get("INPUTS_REPLY", ""))
    got = ja.rejudge_take(jdir, rdir, reply, Path.cwd()) if reply is not None else {"ok": False, "reason": why}
except Exception as e:  # 受け付けは落ちない（契約）。思わぬ誤りも拒否として数える
    got = {"ok": False, "reason": f"受け付けの中で誤りが起きた（{type(e).__name__}: {e}）"}
out = rolekit.with_done(rdir, ja.REJUDGE_ROLE, {"ok": got["ok"], "reason": got["reason"]})
if out["done"]:
    try:
        ja.rejudge_collect(rdir)
    except Exception as e:  # 出口が書けなくても輪は抜ける。verdict が止めの控えを読む
        ja.write_stop(rdir, ja.stopby.REJUDGE, f"再審の出口を書けない（{type(e).__name__}: {e}）")
boundary.returns({"ok": out["ok"], "done": out["done"], "reason": out["reason"]})
