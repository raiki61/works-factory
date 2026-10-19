# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""頭の返し ins: graph の入力のうち when: が読む物（目を回すか・R3 を R4 にまとめるか）を出力に写す（docs/design/judge-eyes.md の 2.3 の 1）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

ports.returns({"run": ports.flag(os.environ.get("INPUTS_RUN")), "merge": ports.flag(os.environ.get("INPUTS_MERGE"))})
