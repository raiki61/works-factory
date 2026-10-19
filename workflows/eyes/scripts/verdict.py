# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返す node verdict（docs/design/judge-eyes.md の 2.4）: 目ごとの受け皿と直した後の実測の受け皿の got から、変更を通してよいか（ok）と
line が読む欄を組み、place の verdict.json に写す。目を回すか（run）・まとめるか（merge）・省いた訳（skip_why）は graph の入力を読む。
落ちない: 中の誤りは全部捕まえ、ok: false と目の行の全部を unverifiable で返す。境の口か lib を読めない時も、標準ライブラリだけの
src/fallback で返す（NaN と Infinity は落ちた返りにする）"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]


def _got(ports, raw):
    raw = ports.text(raw).strip()
    whole = None if raw in ("", "null") else ports.json(raw)
    return whole.get("got") if isinstance(whole, dict) else None


def compute(ports):
    import jsonfile
    from src import files, verdict
    received = {
        "structure-after": _got(ports, os.environ.get("INPUTS_STRUCTURE_AFTER_OUT")),
        "r1": _got(ports, os.environ.get("INPUTS_R1_OUT")),
        "r2": _got(ports, os.environ.get("INPUTS_R2_OUT")),
        "r3": _got(ports, os.environ.get("INPUTS_R3_OUT")),
        "r4": _got(ports, os.environ.get("INPUTS_R4_OUT")),
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
        print(json.dumps(fallback.fallen(f"境の口が読めない: {type(error).__name__}: {error}"), ensure_ascii=False), flush=True)
        return

    def fell(why):
        from src import fallback
        return fallback.fallen(why)

    ports.run(lambda: compute(ports), fell)


main()
