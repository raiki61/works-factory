# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""報告のブロックの返す節。facts の返りに AI の報告（在れば）を足して約束の欄を返す。落ちない: lib/ を読めない時も含めて
中の誤りを全部捕まえ、ok: false・outcome: record_invalid と訳を、返す節の output_format に合う形で返す（線は落ちた返す節の
先へ進めない）。lib/ は main の中で読む。"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

from place import UNWRITTEN, failed_line, out_dir, rel, unwritten  # noqa: E402

FACTS = os.environ.get("INPUTS_FACTS", "")
CARRIED = ("next_request", "prior_failures")


def main() -> dict:
    sys.path.append(str(boundary.lib_root()))
    import runreport

    facts = json.loads(FACTS) if FACTS.strip() not in ("", "null") else None
    if not isinstance(facts, dict) or not isinstance(facts.get("report"), dict):
        raise ValueError("facts の返りが無いか、機械の報告の指し札を持たない")
    machine = boundary.resolve(facts["report"])
    ai = runreport.collect(machine.read_text(encoding="utf-8"), out_dir=out_dir(), stamp=facts["stamp"])
    return {"outcome": facts["outcome"], "ok": facts["ok"], "stop_reason": facts["stop_reason"], "report": rel(machine),
            "report_ai": rel(ai) if ai else None, **{k: facts[k] for k in CARRIED}}


def facts_pointers() -> dict:
    """facts の返りの機械の報告と持ち越しの指し札（形の合う物だけ。読めなければ空）"""
    try:
        got = json.loads(FACTS)
    except ValueError:
        return {}
    if not isinstance(got, dict):
        return {}
    return {k: got[k] for k in ("report", *CARRIED)
            if isinstance(got.get(k), dict) and got[k].get("type") == boundary.POINTER_TYPE}


def fallen(error: BaseException) -> dict:
    """facts の機械の報告と持ち越しの指し札が在ればそれを指して返る。無ければ訳と読めた分を書いた機械の報告（facts の report.md を
    上書きしない別の名）を、lib/ を読めない・それも書けなければ訳だけのファイルを指す"""
    why = failed_line("報告", error)
    out = {"outcome": "record_invalid", "ok": False, "stop_reason": f"report:{why}", "report": None, "report_ai": None,
           "next_request": None, "prior_failures": None}
    got = facts_pointers()
    if "report" in got:
        return {**out, **got}
    try:
        import runreport
        out["report"] = rel(runreport.fallback_report(out_dir(), why, UNWRITTEN))
    except Exception:  # noqa: BLE001 — lib/ を読めなくても、置き場に書けなくても返る
        out["report"] = unwritten(why)
    return out


if __name__ == "__main__":
    try:
        result = main()
    except Exception as error:  # noqa: BLE001 — 返す節は落ちない
        result = fallen(error)
    boundary.returns(result)
