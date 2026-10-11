"""再審の支度: 同じ run の 1 回目の判定と材料を読み、入力 objection と並べて R/brief.md を組み、単位の前の写しを置く。
1 回目の判定が無ければ rejudge-session で止める（lib/judge_accept.rejudge_prep）"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import judge_accept as ja  # noqa: E402
import stopby  # noqa: E402

jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
rdir = boundary.resolve(boundary.pointer(ja.REJUDGE_DIR))
rdir.mkdir(parents=True, exist_ok=True)
try:
    got = ja.rejudge_prep(jdir, rdir, os.environ.get("INPUTS_OBJECTION", ""), Path.cwd())
except Exception as e:  # 支度の誤りは再審の止めにする（verdict が rejudge/stop.json を読む）
    why = f"再審の支度ができない（{type(e).__name__}: {e}）"
    ja.write_stop(rdir, stopby.REJUDGE, why)
    got = {"go": False, "brief_file": "", "reason": why}
boundary.returns({"go": got["go"], "brief_file": got["brief_file"], "reason": got["reason"]})
