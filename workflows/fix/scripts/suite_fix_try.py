# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node suite-fix-try（組の形。起動スクリプトが壊れていた組だけ）: 書き手の返り（with: reply。飛ばされた・落ちた時は null）の本文で
実行器を置き換え、TDD の輪の頭をやり直す（src/suitefix.retry）。直れば {tdd: true, stop: false}、書き直せない・直らなければ
{tdd: false, stop: true, reason}（組を止める。docs/design/fix.md の 19 節）。落ちない: 中の誤りも stop: true と訳"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute() -> dict:
    from src import intake, runvals, suitefix
    place, repo = ports.place(), Path.cwd()
    reply = ports.polyfill("skip_value").value(os.environ.get("INPUTS_REPLY"))
    group = intake.load(place)["group"]
    return suitefix.retry(place, repo, runvals.read(place), [str(k) for k in group["unit_ids"]], reply)


ports.run(compute, lambda why: {"tdd": False, "stop": True, "reason": f"起動スクリプトの書き直しの中の誤り（{why}）"})
