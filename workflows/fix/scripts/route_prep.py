# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node route-prep（組の形の route-loop の中。役 route の前）: 振り分けの段の指示を md から組む（src/route.prep の材料を src/prompts.tdd が
prompts/parts/tdd.md に入れる。振り分けの段の字は今の TDD の輪の route の段と同じ）。振り分けが済んだ（resume で 1 周目から回り直した）・
振り分けない組は {prompt: "", go: false}。組の頭の返り tdd-start.json が無い（group-start が走らなかった）時は落ちる。brief の控えが
壊れた・座が組めない・指示が組めない時は prompt-error.json に書いて落ちる。
返り {prompt, go}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import oneline  # noqa: E402

from src import board, common, prompts, route, runvals  # noqa: E402

NODE = "route-prep"


def main() -> dict:
    place, repo = ports.place(), Path.cwd()
    if not isinstance(board.read_json(place / board.TDD_START_FILE), dict):
        raise ValueError(f"置き場に {board.TDD_START_FILE} が無い（group-start が走らなかった。{place}）")
    state = route.path(place)
    if not state.is_file():
        return {"prompt": "", "go": False}
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
        view = route.prep(state, sources=sources)
        if not view["go"]:
            return {"prompt": "", "go": False}
        out = prompts.tdd(place, repo, view, values)
    except (common.Broken, prompts.Broken) as e:
        prompts.error(place, NODE, oneline.one_line(e))
        raise
    return {"prompt": out["prompt"], "go": True}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:
        print(f"{NODE}: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(result)
