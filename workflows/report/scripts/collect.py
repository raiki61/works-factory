"""報告のブロックの返す節。facts の返りに AI の報告（在れば）を足して約束の欄を返す。落ちない: 中の誤りを全部捕まえ、
ok: false・outcome: record_invalid と訳を、返す節の output_format に合う形で返す（線は落ちた返す節の先へ進めない）。"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import runreport  # noqa: E402
from place import OUT, out_dir, rel  # noqa: E402

FACTS = os.environ.get("INPUTS_FACTS", "")
CARRIED = ("next_request", "prior_failures")


def main() -> dict:
    facts = json.loads(FACTS) if FACTS.strip() not in ("", "null") else None
    if not isinstance(facts, dict) or not isinstance(facts.get("report"), dict):
        raise ValueError("facts の返りが無いか、機械の報告の指し札を持たない")
    machine = boundary.resolve(facts["report"])
    ai = runreport.collect(machine.read_text(encoding="utf-8"), out_dir=out_dir(),
                           stamp=f"works-factory report / run {os.environ.get('WORKFLOW_ID', '')}")
    return {"outcome": facts["outcome"], "ok": facts["ok"], "stop_reason": facts["stop_reason"], "report": rel(machine),
            "report_ai": rel(ai) if ai else None, **{k: facts[k] for k in CARRIED}}


def facts_report() -> dict | None:
    """facts の返りの機械の報告の指し札（読めなければ None）"""
    try:
        got = json.loads(FACTS).get("report")
    except (ValueError, AttributeError):
        return None
    return got if isinstance(got, dict) and got.get("type") == boundary.POINTER_TYPE else None


def fallen(error: BaseException) -> dict:
    """訳と読めた分を書いた機械の報告を指して返る。置き場に書けなければ facts の機械の報告を、それも無ければ訳だけの
    ファイルの置き場を指す（指し札の形は output_format に合う。先が無い札は実行基盤が節の終わりに拒む）"""
    why = runreport.failed_line("報告", error)
    out = {"outcome": "record_invalid", "ok": False, "stop_reason": f"report:{why}", "report": None, "report_ai": None,
           "next_request": None, "prior_failures": None}
    try:
        out["report"] = rel(runreport.fallback_report(out_dir(), why))
    except Exception:  # noqa: BLE001 — 置き場に書けなくても返る
        out["report"] = facts_report() or {"type": boundary.POINTER_TYPE, "run_id": os.environ.get("WORKFLOW_ID", ""),
                                           "path": f"{OUT}/{runreport.FALLBACK_FILE}"}
    return out


if __name__ == "__main__":
    try:
        result = main()
    except Exception as error:  # noqa: BLE001 — 返す節は落ちない
        result = fallen(error)
    boundary.returns(result)
