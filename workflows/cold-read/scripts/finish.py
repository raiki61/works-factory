# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""初見の読み手の出口: 役の返答を読み、判定・止まった所・推測・書き直す側へ渡す行・報告の行を返す。どの段が落ちても落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def result(status, reason, c=None, stuck=()):
    from src import report
    c = c or {"verdict": "", "stops": [], "guessed": [], "decidable": False}
    passed = c["verdict"] == "pass"
    return {"ok": status == "ok", "status": status, "reason": reason, "verdict": c["verdict"], "pass": passed,
            "stops": c["stops"], "guessed": c["guessed"], "decidable": c["decidable"], "stuck": list(stuck),
            "report": report.lines(status=status, reason=reason, passed=passed, stuck=list(stuck))}


def compute():
    import jsonfile  # lib/
    from src import files, reply
    place = ports.place()
    prep = ports.parsed(os.environ.get("INPUTS_PREP"))
    raw = ports.text(os.environ.get("INPUTS_REPLY"))
    if not isinstance(prep, dict):
        out = result("failed", "支度の node が落ちた")
    elif prep.get("due") is not True:
        out = result("failed", str(prep.get("reason") or "支度が読ませなかった"))
    elif not raw.strip() or raw.strip() == "null":
        out = result("failed", "初見の読み手の役が返答を返さなかった（役が落ちたか飛ばされた）", stuck=[reply.COLD_UNREADABLE])
    else:
        try:
            jsonfile.write(place / files.REPLY_FILE, ports.parsed(raw))
        except ValueError:   # 読めない返答は写さない。下の読みが名指して failed にする
            pass
        c = reply.read(raw)
        out = (result("ok", "", c, reply.stuck(c)) if c["verdict"]
               else result("failed", reply.COLD_UNREADABLE, c, [reply.COLD_UNREADABLE]))
    jsonfile.write(place / files.READ_FILE, out)
    return out


def fallback(why: str) -> dict:
    return result("failed", f"出口が落ちた（{why}）")


ports.run(compute, fallback)
