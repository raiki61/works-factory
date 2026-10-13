# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""始めの版から今の作業ツリーまでの差分のうち守りの一覧（自分の一覧と、対象のリポジトリの始めの版の宣言を合わせた物）に当たる物。
一覧・宣言か git が読めない時も落ちず、確かめられなかった印の 1 行を当たりとして返す（黙って空にしない）。返りは置き場の eyes/protected.json にも書く"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import protect  # noqa: E402
import seal  # noqa: E402

try:
    start_file = boundary.pointed(os.environ["INPUTS_START"])
    start = json.loads(start_file.read_text(encoding="utf-8")) if start_file else {}
    base_rev = start.get("base_rev") or ""
    rows = protect.touched(Path.cwd(), base_rev, protect.merged(Path.cwd(), base_rev))
    out = {"hits": [r["path"] for r in rows], "lines": protect.lines(rows), "broken": ""}
except Exception as e:  # noqa: BLE001  protect.Broken と、始めの記録が読めない時
    why = str(e) or type(e).__name__
    out = {"hits": [seal.unknown_row(why)], "lines": [], "broken": why}
eyes = Path(os.environ["ARTIFACTS_DIR"]) / "eyes"
eyes.mkdir(parents=True, exist_ok=True)
(eyes / "protected.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
boundary.returns(out)
