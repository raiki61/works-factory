# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""読んだ証拠: この include の審査の役が、機械が渡したパス（材料のファイルと方針の写し）を読んだかを、隔離した設定のフックの記録
から集め、place に reads-<役>.json と索引を書く（src/proof.py）。受け付けの条件にしない。落ちない: 中の誤りは ok: false と訳で返し、
place に落ちた記録（lib/reads.guarded）を残す。返り {ok, missing, index_file, reason}"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    import reads
    import jsonfile
    from src import files, proof
    place = ports.place()
    doc = jsonfile.read_or(place / files.INTAKE)
    doc = doc if isinstance(doc, dict) else {}
    return reads.guarded(lambda: proof.collect(place, reads.log_here(), Path.cwd()), owner=proof.role(doc)[0], place=place,
                         replan=doc.get("form") == "replan")


ports.run(compute, lambda why: {"ok": False, "missing": [], "index_file": "", "reason": why})
