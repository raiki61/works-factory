# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""読んだ証拠: 並行 PR の役が渡し物を読んだかを、隔離した設定のフックの記録から集め、place に reads-pr-check.json と索引を書く。
受け付けの条件にしない。落ちない: 中の誤りは ok: false と訳で返し、place に落ちた記録（lib/reads.guarded）を残す。返り {ok, missing, index_file, reason}"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    import reads
    from src import files, proof
    place = ports.place()
    return reads.guarded(lambda: proof.collect(place, reads.log_here(), Path.cwd()), owner=files.ROLE, place=place)


ports.run(compute, lambda why: {"ok": False, "missing": [], "index_file": "", "reason": why})
