# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node intake（両方の形）: 全部の port を字のまま読み、形ごとの必須を確かめ（src/intake.read）、place に intake.json と values.json を
書く（place は作るだけで消さない）。読めない port は落ちずに ok: false と「入力 <名>: …」の理由。返り {ok, whole, reason}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

RAW = {name: os.environ.get(f"INPUTS_{name.upper()}") for name in (
    "mode", "judgment", "plan", "fix_plan", "answer_ties", "materials", "skip_rerun", "answers", "request_answers", "plan_review",
    "prior", "only_items", "group", "ripple", "baseline", "policy", "request", "unattended", "parallel", "notes", "test_cmd",
    "tdd_suite", "reuse_dir", "reuse_key", "user_env_dir", "from_tree", "out_dir", "lang", "excluded")}


def compute() -> dict:
    from src import intake, runvals
    place = ports.place()
    doc = intake.read(RAW)
    intake.write(place, doc)
    runvals.write(place, intake.run_values(doc, os.environ.get("WORKFLOW_ID", "")))
    return {"ok": True, "whole": doc["mode"] == "whole", "reason": ""}


def fallback(why: str) -> dict:
    mode = (RAW.get("mode") or "").strip()
    return {"ok": False, "whole": mode == "whole", "reason": why.split(": ", 1)[1] if why.startswith("ValueError: ") else why}


ports.run(compute, fallback)
