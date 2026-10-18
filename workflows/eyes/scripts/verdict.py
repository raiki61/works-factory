# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""ブロックの返す節。返った節が置き場の eyes/ に書いたファイルを読み、lib の eyeverdict.collect でまとめる。返りの欄の外で
最後の関所に出す材料（eyeverdict.write_notes）も置き場に書き、返りの notes・r4_passes でその控えを、premise_reply で前提の検算の
役の返りを指す（最後の関所と報告が読む。書けなかった道は null）。
決して落ちない: 境の口と lib を読む所から中の誤りを全部捕まえ、ok: false と r1〜r4 の unverifiable（理由に誤りの 1 行）を返す"""
import json
import os
import sys
from pathlib import Path


def fallen(reason: str) -> dict:
    """lib を読めなかった時と、返りを JSON に書けない時の約束の形。守りのパスも確かめていないので、理由の行を当たりに数えさせる"""
    row = {"status": "unverifiable", "reason": reason}
    return {"ok": False, "r1": row, "r2": row, "r3": row, "r4": row, "questions": [], "premise_check": None,
            "structure_after": None, "protected_hits": [reason], "notes": None, "r4_passes": None, "premise_reply": None}


protected = None
eyeverdict = None
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary

    sys.path.append(str(boundary.lib_root()))
    import eyeverdict
    import structmark

    eyes = Path(os.environ["ARTIFACTS_DIR"]) / "eyes"
    protected = eyeverdict.read_json(eyes / "protected.json")
    prep = eyeverdict.read_json(eyes / eyeverdict.PREP_FILE)
    if prep is None:
        out = eyeverdict.unverified("支度のノード（prep か、その前の直しの後の実測）が落ちた", protected)
    else:
        design_file = boundary.pointed(os.environ["INPUTS_DESIGN"])
        answer = boundary.parsed(os.environ["INPUTS_ANSWERS"])
        passed = eyeverdict._human_passed(boundary.parsed(os.environ["INPUTS_PLAN_QUESTIONS"]), answer)
        out = eyeverdict.collect(
            eyes_dir=eyes, run_eyes=prep["run_eyes"], compare_due=prep["compare_due"], premise_due=prep["premise_due"],
            design=eyeverdict.read_design(design_file),
            after_ptr=boundary.pointer(f"eyes/{structmark.AFTER_FILE}") if (eyes / structmark.AFTER_FILE).is_file() else None,
            protected=protected, passed=passed)
        notes = eyeverdict.write_notes(eyes, passed=passed, by=eyeverdict.passed_by(answer),
                                       design_ledger=eyeverdict.read_json(boundary.pointed(os.environ["INPUTS_DESIGN_PREMISES"])))
        out.update({name: None if path is None else boundary.pointer(f"eyes/{path.name}") for name, path in notes.items()})
except Exception as e:  # noqa: BLE001  返す節は落ちない（落ちると線が先へ進めない）
    why = f"出口が落ちた: {type(e).__name__}: {e}"
    out = eyeverdict.unverified(why, protected) if eyeverdict else fallen(why)
try:   # Archon の JSON.parse が読めない NaN・Infinity は落ちた返りにする
    print(json.dumps(out, ensure_ascii=False, allow_nan=False), flush=True)
except ValueError as e:
    print(json.dumps(fallen(f"出口が落ちた: 出力が JSON に書けない: {e}"), ensure_ascii=False, allow_nan=False),
          flush=True)
