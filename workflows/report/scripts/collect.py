# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""報告のブロックの返す節。facts の返りに AI の報告（在れば）を足して約束の欄を返す。落ちない: lib/ を読めない時も含めて
中の誤りを全部捕まえ、ok: false・outcome: record_invalid と訳を、返す節の output_format に合う形で返す（線は落ちた返す節の
先へ進めない）。lib/ は main の中で読む。境の口を読めない時も、標準ライブラリだけで同じ形を返す。"""
import json
import os
import sys
from pathlib import Path

LIBLESS = "report-collect-unwritten.md"   # lib/ を読めない時の訳だけのファイル（run の置き場の根。報告の置き場の名は lib が持つ）

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    unread = None
except Exception as error:  # noqa: BLE001 — 返す節は落ちない（下の unwritten で返す）
    boundary, unread = None, error

FACTS = os.environ.get("INPUTS_FACTS", "")
CARRIED = ("next_request", "prior_failures")


def out_dir() -> Path:
    """報告の置き場（run の置き場の runreport.OUT_DIR）"""
    import runreport
    return Path(os.environ["ARTIFACTS_DIR"]) / runreport.OUT_DIR


def rel(path) -> dict | None:
    """置き場の中のパスを、run の置き場からの相対の指し札に（None は None）"""
    return None if path is None else boundary.pointer(boundary.rel_of(path))


def failed_line(what: str, error: BaseException) -> str:
    """思わぬ誤りの 1 行（返す節は stop_reason に report: を付けて載せる）"""
    return f"{what}を組めなかった（{type(error).__name__}: {' '.join(str(error).split())}）"


def unwritten(why: str) -> dict:
    """lib/ にも境の口にも頼らず訳だけの 1 ファイルを書いて指す（書けなくても札は返す。先の無い札は実行基盤が節の終わりに拒む）。
    札は境の口を読めない時のために手で組む"""
    rel_path = LIBLESS
    try:
        path = Path(os.environ["ARTIFACTS_DIR"]) / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# 報告（run {os.environ.get('WORKFLOW_ID', '—')}）\n\n報告を組めなかった: {why}\n", encoding="utf-8")
    except (OSError, KeyError):
        pass
    return {"type": "archon_artifact", "run_id": os.environ.get("WORKFLOW_ID", ""), "path": rel_path}


def main() -> dict:
    sys.path.append(str(boundary.lib_root()))
    import runreport

    facts = boundary.parsed(FACTS)
    if not isinstance(facts, dict) or not isinstance(facts.get("report"), dict):
        raise ValueError("facts の出力が無いか、機械の報告のポインタを持たない")
    machine = boundary.resolve(facts["report"])
    ai = runreport.collect(machine.read_text(encoding="utf-8"), out_dir=out_dir(), stamp=facts["stamp"])
    return {"outcome": facts["outcome"], "ok": facts["ok"], "stop_reason": facts["stop_reason"], "report": rel(machine),
            "report_ai": rel(ai) if ai else None, **{k: facts[k] for k in CARRIED}}


def facts_pointers() -> dict:
    """facts の返りの機械の報告と持ち越しの指し札（形の合う物だけ。読めなければ空）"""
    try:
        got = boundary.parsed(FACTS)
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
        import userenv
        out["report"] = rel(runreport.fallback_report(out_dir(), why, runreport.UNWRITTEN,
                                                      user_env=userenv.ran(boundary.line_place())))
    except Exception:  # noqa: BLE001 — lib/ を読めなくても、置き場に書けなくても返る
        out["report"] = unwritten(why)
    return out


if __name__ == "__main__" and boundary is None:   # 境の口を読めない時
    why = failed_line("報告", unread)
    ptr = unwritten(why)
    print(json.dumps({"outcome": "record_invalid", "ok": False, "stop_reason": f"report:{why}", "report": ptr, "report_ai": None,
                      "next_request": None, "prior_failures": None}, ensure_ascii=False, allow_nan=False), flush=True)
elif __name__ == "__main__":
    try:
        result = main()
    except Exception as error:  # noqa: BLE001 — 返す節は落ちない
        result = fallen(error)
    boundary.returns(result)
