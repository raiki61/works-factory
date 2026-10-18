# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""目の出力の全体を置き場の eyes/<eye>.json に書き、型つきの成果物の行 {eye, status, reason} を返す。入力 part が在れば、出力の
その欄（まとめた役 eyes-one の返りの r3）を目の出力として読む"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

eye = os.environ["INPUTS_EYE"]
out = boundary.parsed(os.environ["INPUTS_OUT"])
part = os.environ["INPUTS_PART"]
if part:
    out = out[part]
eyes = Path(os.environ["ARTIFACTS_DIR"]) / "eyes"
eyes.mkdir(parents=True, exist_ok=True)
(eyes / f"{eye}.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
boundary.returns({"eye": eye, "status": out["verdict"] if "verdict" in out else out["status"], "reason": out["reason"]})
