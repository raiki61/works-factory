# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""R2 の比べの役（独立設計と累積差分の突き合わせ）の指示と system prompt を prompts/r2-compare.md と r2-compare.system.md から組み、貼った前提の控え r2-premises.json を書く"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402

ports.returns(steps.compare_prompt(ports.place(), Path.cwd()))
