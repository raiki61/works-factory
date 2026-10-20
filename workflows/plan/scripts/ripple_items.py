# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""受け付けた案の項目ごとの波及の一覧を r<k>/ripple.json に書く。案が無い周も {items: [], error: <訳>} を書く。返り {ok}"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

from src import steps  # noqa: E402

ports.returns(steps.ripple_items(ports.place(), Path.cwd()))
