# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""役の返りを置き場の eyes/<name>.json に書く（後ろの役が Read で読む）"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

eyes = Path(os.environ["ARTIFACTS_DIR"]) / "eyes"
eyes.mkdir(parents=True, exist_ok=True)
(eyes / f"{os.environ['INPUTS_NAME']}.json").write_text(os.environ["INPUTS_OUT"], encoding="utf-8")
boundary.returns({"saved": True})
