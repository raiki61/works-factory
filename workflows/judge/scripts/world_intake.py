"""世界の解の段の入口: 依頼の行と凍った目的の文を読み、言い直す役の指示書の本文を組む（lib/judge_accept.world_intake）。
段が落ちても run は止めない"""
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
    out = ja.world_intake(jdir, Path.cwd())
except Exception as e:  # noqa: BLE001  （世界の解の段は run を止めない）
    out = {"due": False, "prompt": "", "reason": f"入口が落ちた（{type(e).__name__}: {e}）"}
boundary.returns(out)
