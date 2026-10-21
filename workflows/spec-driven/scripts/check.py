# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""形 check（docs/design/spec-driven.md の 6.4）: 判定と計画の後に、仕様とリポジトリの食い違いを照らす（src/check.py）。落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def _true(raw) -> bool:
    """飛ばされうる真偽の字（true だけが真。空・null・false は偽）"""
    return ports.text(raw).strip() == "true"


def compute():
    from src import check
    got = check.check(ports.place(), Path.cwd(), ready=_true(os.environ.get("INPUTS_READY")),
                      plan_ok=_true(os.environ.get("INPUTS_PLAN_OK")), plan=ports.file(os.environ.get("INPUTS_PLAN")),
                      out_of_scope=ports.json(os.environ.get("INPUTS_OUT_OF_SCOPE") or "[]", "out-of-scope.schema.json"),
                      tdd=ports.flag(os.environ.get("INPUTS_TDD") or "false"),
                      out_of_purpose=ports.file(os.environ.get("INPUTS_OUT_OF_PURPOSE")),
                      base=ports.text(os.environ.get("INPUTS_BASE")).strip())
    return {"done": got["ok"], "reason": ""}


ports.run(compute, lambda why: {"done": False, "reason": f"照らしが落ちた（{why}）"})
