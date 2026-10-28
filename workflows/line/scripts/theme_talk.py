# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""設計の往復（loop_group の theme-rounds）の本体の終わりの node theme-talk（docs/design/line.md の 3.3 節。決めは src.talk.settle を
段 THEME で）。本体の唯一の終わりの関所 gate-theme が依る node で、往復の返り（$theme-rounds.output）はこの node の返り。

- 人の居る run で往復が止まる周: 設計の案・事前審査の結果・持ち主に聞く問いを関所の文にして open にする（受け箱の承認が生きていて、
  持ち主に聞く問いが残っていなければ開かずに合意として返す）
- 無人の run: theme-out の返りを写すだけ（関所は開かない。降りるかは theme-descend が項目と推しで決める）
until_bash はこの node の done だけを読む。

入力（with:）: turn（theme-turn の返り）・theme_out（theme-out の返り。回さなかった周は null）・previous（$LOOP_PREV.theme-talk.output）・
ports（start の配る値）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute() -> dict:
    raw = {name: os.environ.get(f"INPUTS_{name.upper()}") for name in ("turn", "theme_out", "previous", "ports")}
    from src import talk, themetalk

    given = ports.parsed(raw["ports"])
    turn_got = ports.parsed(raw["turn"])
    if not isinstance(given, dict) or not isinstance(turn_got, dict):
        raise ValueError("配る値（ports）か周の頭の出力（turn）が読めない。with: の鍵の結びを確かめる")
    got = ports.picked(raw["theme_out"], tuple(themetalk.failed()))
    previous = ports.parsed(raw["previous"])
    return talk.settle(turn_got=turn_got, plan_out=dict(got) if got is not None else None,
                       previous=previous if isinstance(previous, dict) else None, given=given, materials=None,
                       run_id=os.environ["WORKFLOW_ID"], place=ports.place(), stage=talk.THEME)


def fallback(reason: str) -> dict:
    from src import talk, themetalk
    return {**themetalk.failed(), "reason": reason, **talk.talk_fields({})}


ports.run(compute, fallback)
