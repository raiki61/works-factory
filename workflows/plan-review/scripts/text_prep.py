# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""方針の文の審査の役の指示を prompts/review-text.md から組む（docs/design/plan-review.md の 8 節の text_prep。前の回までの却下は
place の控えから全部）。役を起こす前の作業ツリーの姿も置く。組めなければ crash.json に訳を書いてから落ちる"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402
from src import steps  # noqa: E402


def compute(place: Path, repo: Path) -> dict:
    import accept    # lib/
    import jsonfile  # lib/
    import prompt
    from src import files, textform
    intake = steps.read_intake(place)
    values, when = textform.values(place, intake, repo)
    out = prompt.emit(textform.NODE, values, when, prompt.round_of(textform.NODE))
    jsonfile.write(place / files.TREE_STATE, accept.tree_state(repo))
    return {"prompt": out["prompt"]}


try:
    ports.returns(compute(ports.place(), Path.cwd()))
except Exception as error:
    steps.record_crash(ports.place(), "text-prep", f"{type(error).__name__}: {error}")
    raise
