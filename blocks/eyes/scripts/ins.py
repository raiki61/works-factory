# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""頭の返し ins: graph の入力のうち when: が読む物（目を回すか・R3 を R4 にまとめるか）を出力に写し、空の head を作業ツリーの HEAD の版に解く（docs/design/judge-eyes.md の 2.3 の 1。単独で回す時 structure の base が空で落ちないように）"""
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

head = (os.environ.get("INPUTS_HEAD") or "").strip()
if not head:
    done = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD^{commit}"], capture_output=True, text=True, encoding="utf-8")
    head = done.stdout.strip() if done.returncode == 0 else ""

ports.returns({"run": ports.flag(os.environ.get("INPUTS_RUN")), "merge": ports.flag(os.environ.get("INPUTS_MERGE")), "head": head})
