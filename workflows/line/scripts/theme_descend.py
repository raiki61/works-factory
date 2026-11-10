# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""設計の段から降りる node theme-descend（docs/design/line.md の 3.3 節。決めは src.descend.descend）。

設計の往復が合意で終わったら（無人の run は関所の項目が無ければ）、承認された設計の変える所を依頼の行にした依頼のファイルと、承認された
設計の md の写しを書いて返す。止める答え・往復の止め・無人の run の推しの無い項目は止めの語を返し、後ろは飛び、報告は出る。受けた往復の返りのうち collect が読む
欄（src.loopcarry.THEME_ROUNDS）を欄 rounds で運ぶ（報告を組む collect は落ちうる loop_group を直に結ばず、ここから読む。欄が欠ければ
null。docs/design/line.md の 13.1）。

入力（with:）: rounds（theme-rounds の返り。往復の最後の周の theme-talk の出力）・ports（start の配る値）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute() -> dict:
    from src import descend
    raw_ports, raw_rounds = os.environ.get("INPUTS_PORTS"), os.environ.get("INPUTS_ROUNDS")
    given = ports.parsed(raw_ports)
    if not isinstance(given, dict):
        raise ValueError("配る値（ports）が読めない。with: の鍵の結びを確かめる")
    return {**descend.descend(ports.parsed(raw_rounds), given=given, place=ports.place()), "rounds": carried()}


def carried():
    """運ぶ往復の返り（collect が読む欄だけ。src.loopcarry）"""
    from src import loopcarry
    return loopcarry.carried(os.environ.get("INPUTS_ROUNDS"), loopcarry.THEME_ROUNDS)


def fallback(reason: str) -> dict:
    from src import descend, guard
    return {**descend._stopped(f"設計の段から降りられない: {reason}", guard.LINE_SCRIPT), "rounds": carried()}


ports.run(compute, fallback)
