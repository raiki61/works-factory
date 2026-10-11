"""ブロックの返す節。返った節が置き場の eyes/ に書いたファイルを読み、lib の eyeverdict.collect でまとめる。
決して落ちない: 中の誤りを全部捕まえ、ok: false と r1〜r4 の unverifiable（理由に誤りの 1 行）を返す"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import eyeverdict  # noqa: E402
import structmark  # noqa: E402


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


protected = None
try:
    eyes = Path(os.environ["ARTIFACTS_DIR"]) / "eyes"
    protected = read(eyes / "protected.json")
    prep = read(eyes / "prep.json")
    if prep is None:
        out = eyeverdict.unverified("支度の節（prep か、その前の直しの後の実測）が落ちた", protected)
    else:
        design_ptr = json.loads(os.environ["INPUTS_DESIGN"])
        answer = json.loads(os.environ["INPUTS_ANSWERS"])
        out = eyeverdict.collect(
            eyes_dir=eyes, run_eyes=prep["run_eyes"], compare_due=prep["compare_due"], premise_due=prep["premise_due"],
            design=eyeverdict.read_design(boundary.resolve(design_ptr) if design_ptr else None),
            after_ptr=boundary.pointer(f"eyes/{structmark.AFTER_FILE}") if (eyes / structmark.AFTER_FILE).is_file() else None,
            protected=protected,
            passed=eyeverdict._human_passed(json.loads(os.environ["INPUTS_PLAN_QUESTIONS"]), answer))
except Exception as e:  # noqa: BLE001  返す節は落ちない（落ちると線が先へ進めない）
    out = eyeverdict.unverified(f"出口が落ちた: {type(e).__name__}: {e}", protected)
boundary.returns(out)
