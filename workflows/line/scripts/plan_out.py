# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""計画の往復（loop_group の plan-rounds）の終わりの返しの節 plan-out（docs/design.md の U4）。

loop_group の中の節は外から見えず、外から見えるのは $plan-rounds.output（本体の終わりの節の出力）だけなので、ここで plan と
plan-review の返りを欄ごとに受けて返す。外の節は $plan-rounds.output.<欄> を読む。plan-review は plan ができなかった周に飛ばされる
（`{from, if_skipped: null}`）。
done は往復を抜けるかで、until_bash が読む: 計画ができなかった・通った・事前審査の壁打ちが止まった（stalled。止め時は
lib の converge.decide）・plan の round が往復の安全の上限 round_limit 以上。上限は max_iterations と同じ数（試験が
突き合わせる）で、届かない大きさの網（中央の新しい穴が出続ける往復も普通は届かず、届けば工場の不具合）。上限の周の終わりで必ず真になるので、往復は上限に当たって落ちない。
nothing_owed は計画ができなかった周のうち、直す義務の単位が 0 件で役を起こさなかった周か（周の round.json の訳。lib/outcome.py の
plan_nothing_owed と同じファイルを読む）。真なら design-only が走り、今の works の空の修正（works/darkfactory/lib/line_edge.py:1109-1114
の plan_edge）と同じく最後のテストと独立の目で周を締める（#291）。
例外の時は計画ができなかった形（ready: false・done: true・nothing_owed: false）と止めの理由 works:line-script を返す。

入力（with:）: plan の 6 つの欄と plan-review の 7 つの欄（docs/design.md の「plan の出力」「plan-review の出力」）と round_limit
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import planfile

PLAN = ("ready", "plan", "structure", "ripple", "depth", "round")
REVIEW = ("pass", "stalled", "review", "design", "gate_axes", "ask_human", "questions")


def round_owes_nothing(plan) -> bool:
    """計画の指し札 plan（plan-fields.json）の隣の round.json が、直す義務 0 件で役を起こさなかった周と言うか（lib/outcome.py の
    plan_nothing_owed と同じファイル）。指し札が無い・ほかの run の物・読めなければ偽で、今までの諦めの扱いに倒す"""
    try:
        return planfile.nothing_owed(boundary.resolve(plan).parent)
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        return False


def plan_out(got: dict, round_limit: int, nothing_owed: bool = False) -> dict:
    done = (got["ready"] is not True or got["pass"] is True or got["stalled"] is True
            or (isinstance(got["round"], int) and got["round"] >= round_limit))
    return {**got, "nothing_owed": got["ready"] is not True and nothing_owed, "done": done, "stop_reason": ""}


def from_env() -> tuple:
    got = {key: boundary.value(os.environ.get(f"INPUTS_{key.upper()}")) for key in PLAN + REVIEW}
    return got, boundary.value(os.environ.get("INPUTS_ROUND_LIMIT")), round_owes_nothing(got["plan"])


def fallback(reason: str) -> dict:
    return {**{key: None for key in PLAN + REVIEW}, "ready": False, "nothing_owed": False, "done": True,
            "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(lambda: plan_out(*from_env()), fallback)
