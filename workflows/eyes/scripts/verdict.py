# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返す node verdict（docs/design/judge-eyes.md の 2.4）: 目ごとの block と直した後の実測の返りから、変更を通してよいか（ok）と
line が読む欄を組み、place の verdict.json に写す。目を回すか（run）・まとめるか（merge）・省いた訳（skip_why）は graph の入力を読む。
落ちない: 中の誤りは全部捕まえ、ok: false と目の行の全部を unverifiable で返す。境の口か lib を読めない時も、標準ライブラリだけの
src/fallback で返す（NaN と Infinity は落ちた返りにする）。

入力（with:）: structure_after_out・r1_out〜r4_out（include した block の返りまるごと。飛ばされた block は null。読む欄は下の名の並びで
選び、どれも欄 optional を無くてよい欄として読む）"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]

# include した block の返りのうち読む欄（src/verdict.py が読む物）
STRUCTURE = ("ok", "status", "reason", "structure", "after", "dirty", "escalate", "report")
R1 = ("ok", "status", "reason", "verdict", "questions", "findings", "report")
R2 = ("ok", "status", "reason", "verdict", "questions", "premise_check", "notes", "findings", "report")
R3 = ("ok", "status", "reason", "verdict", "questions", "report")
R4 = ("ok", "status", "reason", "verdict", "questions", "passes", "coherence", "report")


def _plain(got):
    return None if got is None else dict(got)


def compute(ports):
    import jsonfile
    from src import files, verdict
    received = {
        "structure-after": _plain(ports.picked(os.environ.get("INPUTS_STRUCTURE_AFTER_OUT"), STRUCTURE, optional=("optional",))),
        "r1": _plain(ports.picked(os.environ.get("INPUTS_R1_OUT"), R1, optional=("optional",))),
        "r2": _plain(ports.picked(os.environ.get("INPUTS_R2_OUT"), R2, optional=("optional",))),
        "r3": _plain(ports.picked(os.environ.get("INPUTS_R3_OUT"), R3, optional=("optional",))),
        "r4": _plain(ports.picked(os.environ.get("INPUTS_R4_OUT"), R4, optional=("optional",))),
    }
    out = verdict.build(received, run=ports.flag(os.environ.get("INPUTS_RUN")), merge=ports.flag(os.environ.get("INPUTS_MERGE")),
                        skip_why=ports.text(os.environ.get("INPUTS_SKIP_WHY")))
    json.dumps(out, allow_nan=False)
    jsonfile.write(ports.place() / files.VERDICT, out)
    return out


def main():
    try:
        import ports
    except Exception as error:  # noqa: BLE001 — 境の口を読めない時も返す node は落ちない
        from src import fallback
        print(json.dumps(fallback.fallen(f"境の口が読めない: {type(error).__name__}: {error}"), ensure_ascii=False, allow_nan=False), flush=True)
        return

    def fell(why):
        from src import fallback
        return fallback.fallen(why)

    ports.run(lambda: compute(ports), fell)


main()
