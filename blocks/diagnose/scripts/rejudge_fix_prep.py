# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""拒まれた後の再審の出し直しの役の指示を prompts/rejudge-fix.md から組む（最後の拒否の理由と、合わせた前の答えの控えのパス）。
組めなければ prompt-error.json に訳を書いて node が落ち、後ろの rejudge-fix と rejudge-accept は依存の失敗で飛ぶ（訳は prompt-error.json に残る）"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import inputs  # noqa: E402

ports.returns(inputs.prep(ports.place(), inputs.rejudge_fix_prompt))
