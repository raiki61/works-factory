# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node suite-fix-prep（組の形。起動スクリプトが壊れていた組だけ）: 起動スクリプトを書き直す役の指示を prompts/suite-fix.md から組む
（src/suitefix.prompt_values。壊れた実行器の本文・壊れた回のログの末尾・test_cmd の単体のログ）。{write, prompt}。
落ちない: 読めない入力は write: false（書き手を起こさず、suite-fix-try が書き直せなかったとして組を止める）。docs/design/fix.md の 19 節"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

NODE = "suite-fix"


def compute() -> dict:
    import prompt
    from src import board, runvals, suitefix
    place, repo = ports.place(), Path.cwd()
    started = board.read_json(place / board.TDD_START_FILE) or {}
    if started.get("suite_broken") is not True:
        return {"write": False, "prompt": ""}
    values, when = suitefix.prompt_values(place, repo, runvals.read(place), started)
    return {"write": True, "prompt": prompt.emit(NODE, values, when, prompt.round_of(NODE))["prompt"]}


ports.run(compute, lambda why: {"write": False, "prompt": ""})
