# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""レンズの指示を prompts/<レンズ>.md から組む。組めなければ errors.json に積んでから落ち（レンズの node は起きず、出口がその行を failed にする）"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

name = os.environ.get("INPUTS_LENS", "")
try:
    from src import steps
    out = steps.lens_prompt(ports.place(), name)
except Exception as e:  # noqa: BLE001
    why = " ".join(f"{type(e).__name__}: {e}".split())
    path = ports.place() / "errors.json"   # src が読めない時にも積めるよう標準ライブラリだけで書く（名は src/files.py の ERRORS と同じ。試験が結ぶ）
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rows = []
    path.write_text(json.dumps([*(rows if isinstance(rows, list) else []), {"node": name, "reason": why}], ensure_ascii=False) + "\n",
                    encoding="utf-8")
    sys.exit(f"lens-prep {name}: {why}")
ports.returns(out)
