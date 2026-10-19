# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""R4 の出し直しの役（1 回目の役の会話の続き）の指示を prompts/r4-scope-fix.md から組む。出し直しの周だけ回る"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

ports.returns(steps.scope_fix_prompt(ports.place()))
