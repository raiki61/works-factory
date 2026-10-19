# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""world と review（事前審査）の返りをまとめ、事前審査の block の穴と定石と違う行を先頭に並べた報告の行を返す。落ちない"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    raw = ports.text(os.environ.get("INPUTS_WORLD")).strip()
    world = None if raw in ("", "null") else ports.json(raw)
    if isinstance(world, dict) and world.get("rows"):
        world = {**world, "rows_file": str(ports.file(json.dumps(world["rows"])))}
    raw = ports.text(os.environ.get("INPUTS_REVIEW")).strip()
    review = None if raw in ("", "null") else ports.json(raw)
    faces = []
    if isinstance(review, dict) and review.get("holes"):
        holes = ports.json(json.dumps(review["holes"]))
        faces = [f for f in holes.get("faces") or [] if isinstance(f, dict)] if isinstance(holes, dict) else []
    return steps.result(world, review, faces)


ports.run(compute, lambda why: {"ok": False, "world": None, "holes": [], "report": [f"- まとめが落ちた（{why}）"]})
