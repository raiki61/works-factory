# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返す node finish（両方の形）: 各 node が place に書いたファイルを読んで出力の欄を組む（src/finish.collect。今の collect.py の後継）。
落ちない: 中の誤りは ok: false と理由で返し（diff は fix-collect-error.txt を指す）、lib を読めない時も標準ライブラリだけで返す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def main() -> None:
    from src import finish
    place = ports.place()
    try:
        out = finish.collect(place, Path.cwd())
    except BaseException as e:   # 返す node は落ちない（graph が先へ進めなくなる）
        why = f"fix の出力を組めない（{type(e).__name__}: {' '.join(str(e).split())[:500]}）"
        print(f"finish: {why}", file=sys.stderr)
        out = finish.fallback(place, why)
    try:
        ports.returns(out)
    except ValueError as e:
        last = finish.fallback(place, f"fix の出力を書けない（{type(e).__name__}: {e}）")
        try:
            ports.returns(last)
        except ports.ShapeError as again:   # 返しの控えの行が宣言に合わない時も、fallback の返りは同じ行を持つので、その 2 つを空にして返す
            last["removed_tests"], last["untested"] = [], []
            last["tdd_refused"]["unread"].append(f"返しの控えの行を返せない（{again}）")
            ports.returns(last)


if __name__ == "__main__":
    main()
