# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""埋め P8（docs/polyfills.md）。レンズの返りの中継（節 lens-reply）: レンズの節の返り（with: reply）をそのまま返す。
Archon は落ちた節の出口を、if_skipped を書いた結びでも読ませず、読んだ節を落とす（止めた Archon の dag-executor.ts の
resolveBindingDirective。#2696）。レンズが落ちるとこの節が飛ぶので、集め役（lens-collect）はこの節の返りを if_skipped: null で
受け、落ちたレンズを理由つきの failed の行に残して先へ進める。
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

if __name__ == "__main__":
    boundary.returns(boundary.value(os.environ["INPUTS_REPLY"]))
