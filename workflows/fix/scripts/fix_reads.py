# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""読んだ証拠の節 fix-reads（lib/fixboard.collect_reads）: 修正役と裁定の後の修正役が、機械が渡したパス（指示書・判定の写し・
brief）を読んだかを、隔離した設定のフックの記録（lib/reads.log_here）から集め、置き場に reads-<役>.json と索引を書く。
受け付けの条件にしない。返す節に結ばない。落ちない: 中の誤りは ok: false と訳で返す。返り {ok, missing, index_file, reason}"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True


def collected() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    sys.path.append(str(boundary.lib_root()))
    import fixboard
    import reads

    got = fixboard.collect_reads(boundary.place("fix"), reads.log_here(), repo=boundary.work_tree())
    boundary.returns({**got, "reason": ""})


def main() -> int:
    try:
        collected()
    except Exception as e:  # noqa: BLE001  読んだ証拠は受け付けの条件でない（ブロックを止めない。境の口を読めない時も返す）
        print(json.dumps({"ok": False, "missing": [], "index_file": "", "reason": f"{type(e).__name__}: {' '.join(str(e).split())}"},
                         ensure_ascii=False, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
