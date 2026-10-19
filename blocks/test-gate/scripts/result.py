# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返す node result: run.json と（在れば）任せ先の役の ci-material.json を読み、赤の原因と証拠を出し（green_cert.classify）、今の指紋を
取って認証する（green_cert.certify。final で素材を任せ先の役が書いた緑は自己申告として認証しない）。base は直す前の結末のファイル
baseline.json を書く。final は port baseline の指すファイルを読み、修正前のテストの行を証拠に足し、テストごとの修正前と今の結末
（test_outcomes）を返す。足した欄は suite・suite_note（TDD の実行器と 1 行）と report（報告の日本語の行）。
落ちない: lib の import から先の誤りは全部捕まえ、終了の値 0 で ok: false・green: false・red_cause: incomplete と、誤りを名指した証拠の
pointer を返す（返す node が落ちると線が先へ進めない）。その時の by などの字の欄は空、reason は INNER_ERROR。
入力 optional（落ちても線が先へ進めてよい node の宣言）は読んだ並びのまま返りの欄 optional に載せる"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

from src import certify  # noqa: E402


def main() -> int:
    place = ports.place()
    try:
        out = certify.certified(place, os.environ.get("INPUTS_OPTIONAL"))
    except Exception as error:  # noqa: BLE001 — 落ちない node の口
        out = certify.failed(place, error)
    ports.returns(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
