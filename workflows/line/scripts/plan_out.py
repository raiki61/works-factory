"""計画の往復（loop_group の plan-rounds）の終わりの返しの節 plan-out（埋め P2）。

loop_group の中の節は外から見えず、外から見えるのは $plan-rounds.output（本体の終わりの節の出力）だけなので、ここで plan と
plan-review の返りを欄ごとに受けて返す。外の節は $plan-rounds.output.<欄> を読む。plan-review は plan ができなかった周に飛ばされる
（`{from, if_skipped: null}`）。
done は往復を抜けるかで、until_bash が読む: 計画ができなかった・通った・同じ所で 2 度止めた（stalled）・plan の round が 3 以上。
3 周目の終わりで必ず真になるので、往復は上限（max_iterations: 3）に当たって落ちない。

入力（with:）: plan の 6 つの欄と plan-review の 7 つの欄（docs/design.md の「plan の返り」「plan-review の返り」）
"""
import os

import linekit

ROUND_LIMIT = 3
PLAN = ("ready", "plan", "structure", "ripple", "depth", "round")
REVIEW = ("pass", "stalled", "review", "design", "gate_axes", "ask_human", "questions")


def plan_out(got: dict) -> dict:
    done = (got["ready"] is not True or got["pass"] is True or got["stalled"] is True
            or (isinstance(got["round"], int) and got["round"] >= ROUND_LIMIT))
    return {**got, "done": done}


def from_env() -> dict:
    return {key: linekit.value(os.environ.get(f"INPUTS_{key.upper()}")) for key in PLAN + REVIEW}


def fallback(reason: str) -> dict:
    return {**{key: None for key in PLAN + REVIEW}, "ready": False, "done": True}


if __name__ == "__main__":
    linekit.run(lambda: plan_out(from_env()), fallback)
