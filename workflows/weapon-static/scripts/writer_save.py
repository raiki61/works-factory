# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""書き手の返答を形に照らして place に書く（本体は workflows/.shared/writerblock.py の save）。6 つの書き手の型の block で 1 字も違わない"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import writerblock  # noqa: E402
from src import render  # noqa: E402

writerblock.save()
