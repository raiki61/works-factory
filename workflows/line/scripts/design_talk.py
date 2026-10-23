# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""計画の往復（loop_group の plan-rounds）の本体の終わりの node design-talk（docs/design/line.md の 3.1 節。決めは src.talk.settle）。

本体の唯一の終わりの関所 gate-design が依る node で、往復の返り（$plan-rounds.output）はこの node の返り。plan-out の返りの欄に、
設計の相談の欄 open・text・asked・agreed・talks を足して返す。

- 通常の run: plan-out の返りをそのまま写す（関所は飛ぶ）
- 対話モードの run で往復が止まる周（plan-out の done）: 設計案・事前審査の結果・人が決める項目（修正前の承認ノードと同じ材料と決め。
  src.asking.materials・src.gates.before_fix）を関所の文にして open にし、done を偽にする（答えを次の周の頭が読む）
- 対話モードの run の 1 周目（周の頭の early）: 計画を回さず、判定の読み（judge の got）を早い相談の文にして関所を開く（issue #830）
- 答えた後の周（plan を回さない周）: 前の周の返りを写し、合意か止めなら done にして答えを agreed に置く。一言の空の修正要望は聞き直す
until_bash はこの node の done だけを読む（飛びうる関所の出力を読まない。止めた Archon の決まり）。

入力（with:）: turn（design-turn の返り）・plan_out（plan-out の返り。回さなかった周は null）・previous（$LOOP_PREV.design-talk.output）・
structure（structure-in の structure）・judge（judge-out の got）・record（始めの記録の pointer）・ports（start の配る値）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute() -> dict:
    raw = {name: os.environ.get(f"INPUTS_{name.upper()}")
           for name in ("turn", "plan_out", "previous", "structure", "judge", "record", "ports")}
    from src import asking, talk

    given = ports.parsed(raw["ports"])
    turn_got = ports.parsed(raw["turn"])
    if not isinstance(given, dict) or not isinstance(turn_got, dict):
        raise ValueError("配る値（ports）か周の頭の出力（turn）が読めない。with: の鍵の結びを確かめる")
    plan_out = ports.picked(raw["plan_out"], tuple(talk.failed()))   # plan-out の返りの欄（落ちた形と同じ欄）
    previous = ports.parsed(raw["previous"])
    place = ports.place()

    def materials(rounds: dict) -> dict:
        return asking.materials(rounds, structure_raw=raw["structure"], judge_raw=raw["judge"], record_raw=raw["record"],
                                unattended=False, place=place)

    judge = ports.picked(raw["judge"], (), optional=talk.JUDGE_FIELDS) if turn_got.get("early") else None
    return talk.settle(turn_got=turn_got, plan_out=dict(plan_out) if plan_out is not None else None,
                       previous=previous if isinstance(previous, dict) else None, given=given, materials=materials,
                       run_id=os.environ["WORKFLOW_ID"], judge=dict(judge) if judge is not None else None)


def fallback(reason: str) -> dict:
    """読めない時は計画ができなかった形で往復を止める（輪を落とさない。修正前の承認ノードは開かずに修正へも進まない）"""
    from src import talk
    return {**talk.failed(), **talk.talk_fields({})}


ports.run(compute, fallback)
