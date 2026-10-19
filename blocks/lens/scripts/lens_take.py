# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""レンズの返答を place の reply-<key>.json に書く。書けなければ落ち、出口がその行を failed にする"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

from src import steps  # noqa: E402

ports.returns(steps.take(ports.place(), os.environ.get("INPUTS_LENS", ""), os.environ.get("INPUTS_REPLY")))
