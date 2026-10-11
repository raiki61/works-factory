"""並行 PR の機械の道: 開いている PR と、この run の差分・依頼の場所との交差を gh の読みだけで数え、機械で決められない時だけ
役 pr-check を起こす（lib/judge_accept.pr_scan）。仕様の段が止めた run は先へ進めない"""
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
    out = ja.pr_scan(jdir, Path.cwd())
except Exception as e:  # noqa: BLE001  （落ちずに役に任せる。訳は reason に）
    out = {"go": ja.read_stop(jdir) is None, "go_role": ja.read_stop(jdir) is None,
           "reason": f"機械の道が落ちた（{type(e).__name__}: {e}）——役に任せる"}
boundary.returns(out)
