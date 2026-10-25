# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node tdd-prep（組の形の tdd-loop の中。役 tdd・tdd-new の前）: 今の段の指示を md から組む（src/tdd.prep の材料を
src/prompts.tdd が prompts/parts/tdd.md に入れる）。単位が替わった周かを new_unit で返し、YAML が同じ単位の続きの役 tdd（会話を継ぐ）
と新しい単位の役 tdd-new（context: fresh）を振り分ける。輪が済んだ（resume で 1 周目から回り直した）・実行器の無い run は
{prompt: "", go: false, new_unit: false}。brief の控えが壊れた・座が組めない・指示が組めない時は prompt-error.json に書いて落ちる。
返り {prompt, go, new_unit}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import oneline  # noqa: E402

from src import board, prompts, runvals, common, tdd  # noqa: E402

NODE = "tdd-prep"


def main() -> dict:
    place, repo = ports.place(), Path.cwd()
    started = board.read_json(place / board.TDD_START_FILE)
    if not isinstance(started, dict):
        raise ValueError(f"置き場に {board.TDD_START_FILE} が無い（group-start が走らなかった。{place}）")
    if not started.get("go"):
        return {"prompt": "", "go": False, "new_unit": False}
    run = runvals.read(place)
    judgment_file = place / board.JUDGMENT_FILE
    plan_file = place / board.PLAN_REPLY_FILE
    notes = place / board.NOTES_FILE
    values = {"judgment_file": str(judgment_file) if judgment_file.is_file() else "",
              "plan_file": str(plan_file) if plan_file.is_file() else "",
              "policy_path": run["policy"], "request_file": run["request_file"],
              "notes_file": str(notes) if notes.is_file() else "", "base_rev": board.base_rev_of(place)}
    sources = {"plan": board.read_json(plan_file), "judgment": board.read_json(judgment_file)}
    try:
        view = tdd.prep(started["state_file"], sources=sources)
        if not view["go"]:
            return {"prompt": "", "go": False, "new_unit": False}
        out = prompts.tdd(place, repo, view, values)
    except (common.Broken, prompts.Broken) as e:
        prompts.error(place, NODE, oneline.one_line(e))
        raise
    return {"prompt": out["prompt"], "go": True, "new_unit": bool(view["new_unit"])}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:
        print(f"{NODE}: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(result)
