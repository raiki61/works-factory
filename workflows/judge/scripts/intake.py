# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""入口の節: 始めの記録を開き、依頼の行を型に通し、判定の道か再審の道かと段の切り替えを返す（lib/judge_accept.intake）。
with: の test_caches（JSON の字の並び）は、読むだけの役の見張りが数えないテストのキャッシュの名の形"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import judge_accept as ja  # noqa: E402


def read(raw: str):
    """指し札の入力の先の JSON（null・空の字は None）"""
    path = boundary.pointed(raw)
    return None if path is None else json.loads(path.read_text(encoding="utf-8"))


start, prior, caches, error = None, None, [], ""
try:
    start = read(os.environ["INPUTS_START"])
    prior = read(os.environ.get("INPUTS_PRIOR_FAILURES"))
    caches = boundary.value(os.environ.get("INPUTS_TEST_CACHES")) or []
except (KeyError, OSError, TypeError, ValueError, AttributeError) as e:
    error = f"始めの記録か前の失敗の行かテストのキャッシュの名の形が読めない（{type(e).__name__}: {e}）"
boundary.returns(ja.intake(start, error, boundary.resolve(boundary.pointer(ja.JUDGE_DIR)),
                           boundary.resolve(boundary.pointer(ja.REJUDGE_DIR)), Path.cwd(),
                           os.environ.get("INPUTS_OBJECTION", ""), prior, caches))
