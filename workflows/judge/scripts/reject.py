# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""前の周の受け付けが拒んだ理由（with: の reason。1 周目は空の字）を、そのまま今の周の返りにする。
役が周ごとに新しい会話で起きる輪（fresh_context: true）は reason を結ばず、with: の board（置き場からの相対のフォルダ）と accept
（受け付けの拒否の控えの名）を結ぶ: 返りの reason は控え rejects-<accept>.json の拒否の全部（rolekit.rejects_text。最後の 1 件だけでは
3 回目の役が 1 回目の誤りを繰り返す。#345）。
輪の中の役の節は、自分の with: で結んだ名を $INPUTS で読めない: 線が include した時に、止めた Archon が「入力が無い」と止める
（packages/workflows/src/include-expander.ts:566・627。輪の中の節の with: を楯にしない）。だから前の周の値は、今の周のこの節の返りを
役の指示書が $<この節>.output.reason で読む形で渡す（ASF の W/deliver/archon-deliver.yaml の ci-evidence と同じ形）。
同じ形で、役の文の頭に足す言語の 1 行（始めの記録の lang から rolekit.lang_line。元 works/.shared/core/rolekit.py 147-150 行）を
lang_line で返し、役の指示書が $<この節>.output.lang_line で読む。lib/ を読めなくても落ちずに訳の 1 行を返す"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402


def lang_line() -> str:
    try:
        sys.path.append(str(boundary.lib_root()))
        import rolekit
        return rolekit.record_lang_line(boundary.pointed(os.environ.get("INPUTS_START")))
    except Exception as error:  # noqa: BLE001 — 拒否の理由を役へ渡す節は落ちない
        return f"（言語の 1 行を組めない: {type(error).__name__}: {error}。人が読む文の欄は依頼文の言語で書け）"


def reason() -> dict:
    accept = os.environ.get("INPUTS_ACCEPT")
    if not accept:
        return boundary.prev_reason()
    sys.path.append(str(boundary.lib_root()))
    import rolekit
    board = boundary.resolve(boundary.pointer(os.environ["INPUTS_BOARD"]))
    return {"reason": rolekit.rejects_text(rolekit.rejected(board, accept))}


boundary.returns({**reason(), "lang_line": lang_line()})
