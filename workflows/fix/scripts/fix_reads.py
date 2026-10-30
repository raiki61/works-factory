# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node fix-reads（読んだ証拠。受け付けの条件にしない）: 修正役と裁定の後の修正役が、機械が渡したパス（判定の写し・brief）を読んだかを
フックの記録から集めて place の reads-<役>.json と索引に書く（board.collect_reads。役の session は段の頭の印の後に brief〔無ければ判定の
写し〕を読んだ物で見分ける。13.1 の 10）。前の node が落ちても飛ばされても走り、落ちない。返り {ok, missing, index_file, reason}"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def main() -> int:
    try:
        import reads
        from src import board
        place = ports.place()
        ports.returns(reads.guarded(lambda: board.collect_reads(place, reads.log_here(), repo=Path.cwd()),
                                    owner=board.READS_OWNER, place=place))
    except Exception as e:  # noqa: BLE001  読んだ証拠は受け付けの条件でない（block を止めない）
        print(json.dumps({"ok": False, "missing": [], "index_file": "", "reason": f"{type(e).__name__}: {' '.join(str(e).split())}"},
                         ensure_ascii=False, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
