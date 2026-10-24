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

# env の名は字のまま書く（Archon は読み込みの時に script の字から INPUTS_ の名を拾う。組んだ名は拾われない）
RAW = {
    "mode": os.environ.get("INPUTS_MODE"),
    "routes": os.environ.get("INPUTS_ROUTES"),
    "judgment": os.environ.get("INPUTS_JUDGMENT"),
    "plan": os.environ.get("INPUTS_PLAN"),
    "fix_plan": os.environ.get("INPUTS_FIX_PLAN"),
    "answer_ties": os.environ.get("INPUTS_ANSWER_TIES"),
    "materials": os.environ.get("INPUTS_MATERIALS"),
    "skip_rerun": os.environ.get("INPUTS_SKIP_RERUN"),
    "answers": os.environ.get("INPUTS_ANSWERS"),
    "request_answers": os.environ.get("INPUTS_REQUEST_ANSWERS"),
    "plan_review": os.environ.get("INPUTS_PLAN_REVIEW"),
    "prior": os.environ.get("INPUTS_PRIOR"),
    "only_items": os.environ.get("INPUTS_ONLY_ITEMS"),
    "group": os.environ.get("INPUTS_GROUP"),
    "ripple": os.environ.get("INPUTS_RIPPLE"),
    "baseline": os.environ.get("INPUTS_BASELINE"),
    "policy": os.environ.get("INPUTS_POLICY"),
    "request": os.environ.get("INPUTS_REQUEST"),
    "unattended": os.environ.get("INPUTS_UNATTENDED"),
    "parallel": os.environ.get("INPUTS_PARALLEL"),
    "suite_made": os.environ.get("INPUTS_SUITE_MADE"),
    "notes": os.environ.get("INPUTS_NOTES"),
    "test_cmd": os.environ.get("INPUTS_TEST_CMD"),
    "tdd_suite": os.environ.get("INPUTS_TDD_SUITE"),
    "reuse_dir": os.environ.get("INPUTS_REUSE_DIR"),
    "reuse_key": os.environ.get("INPUTS_REUSE_KEY"),
    "user_env_dir": os.environ.get("INPUTS_USER_ENV_DIR"),
    "from_tree": os.environ.get("INPUTS_FROM_TREE"),
    "out_dir": os.environ.get("INPUTS_OUT_DIR"),
    "lang": os.environ.get("INPUTS_LANG"),
    "excluded": os.environ.get("INPUTS_EXCLUDED"),
}


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
