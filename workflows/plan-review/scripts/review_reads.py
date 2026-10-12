# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""読んだ証拠の節（lib/boardview.collect_reads）: この差し込みの事前審査の役が、機械が渡したパスを読んだかを、隔離した設定の
フックの記録（lib/reads.log_here。隔離した Claude の設定の置き場の下）から集め、pass-<k>/ に reads-<役>.json と索引を書き、
束ね役が起こした下請けの数を trace に残す。受け付けの条件にしない。返す節に結ばない。落ちない: 中の誤りは ok: false と訳で返す。
返り {ok, missing, index_file, reason}"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROLE = "plan-review"            # 道具を持つ役の節（YAML の review-loop の中。道具を持たない役は独立設計 planblk.DESIGN_ROLE だけ）


def collected() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    sys.path.append(str(boundary.lib_root()))
    import boardview
    import planblk
    import reads

    got = boardview.collect_reads(Path(os.environ["ARTIFACTS_DIR"]) / boardview.FOLDER,
                                  reads.log_here(), role=ROLE, quiet=(planblk.DESIGN_ROLE,), repo=Path.cwd())
    boundary.returns({**got, "reason": ""})


def main() -> int:
    try:
        collected()
    except Exception as e:  # noqa: BLE001  読んだ証拠は受け付けの条件でない（線を止めない。境の口を読めない時も返す）
        print(json.dumps({"ok": False, "missing": [], "index_file": "", "reason": f"{type(e).__name__}: {' '.join(str(e).split())}"},
                         ensure_ascii=False, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
