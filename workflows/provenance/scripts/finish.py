# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""根拠の出所検査の出口: 素材の状態を material.json に書き、block の返り {ok, status, reason, material, report} を返す。
どの段が落ちても落ちない（落とし穴 K1・K13）"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    import materialkit   # lib/（ports を読むと lib/ が sys.path に入る）。lib を読む物は守った中で読む（読めない時も fallback で返す。落とし穴 K1）
    from src import viewpoint
    return materialkit.finish(viewpoint, ports.place(), lambda path: ports.pointer(path, "json(shared:material.schema.json)"))


def fallback(why: str) -> dict:
    reason = f"出口が落ちた（{why}）"
    return {"ok": False, "status": "failed", "reason": reason, "material": None,
            "report": [f"観点 {Path(__file__).resolve().parents[1].name}: failed", reason]}


ports.run(compute, fallback)
