# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""仕様の関所に見せる文を組む。役の輪が諦めた・仕様が揃わない時は関所を開かずに止める（lib/judge_accept.spec_ask）"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import judge_accept as ja  # noqa: E402

jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
jdir.mkdir(parents=True, exist_ok=True)
try:
    got = ja.spec_ask(jdir, Path.cwd(), boundary.pointer(ja.JUDGE_DIR)["run_id"])
except Exception as e:  # 関所を開けない誤りは仕様の止めにする（後ろの spec-freeze と verdict が止めの控えを読む）
    ja.write_stop(jdir, ja.SPEC_STOP, f"仕様の関所の文を組めない（{type(e).__name__}: {e}）")
    got = {"ask": False, "message": ""}
boundary.returns({"ask": got["ask"], "message": got["message"]})
