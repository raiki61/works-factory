# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""頭の返し ins: graph の入力のうち when: が読む物（仕様の段を挟むか・世界の解を回すか・web）を出力に写す（docs/design/judge-eyes.md の 0 節）"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

ports.returns({"spec": ports.flag(os.environ.get("INPUTS_SPEC")), "world": ports.flag(os.environ.get("INPUTS_WORLD")),
               "web": ports.choice(os.environ.get("INPUTS_WEB"), ("on", "off"))})
