# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""設計の往復（テーマの run の loop_group の theme-rounds）の本体の頭の node theme-turn（docs/design/line.md の 3.3 節。決めは src.talk.turn
を段 THEME で、答えの text のセクションの読みは src.themetalk）。

前の周の関所 gate-theme の答え（$LOOP_PREV。1 周目と関所が飛んだ周は空）と受け箱の新しい行を読み、この周に書き手と事前審査を回すかと、
この周の書き手・事前審査・theme-out に渡す値（前の周の設計の案 prior_design・往復の記録 record・人の答えの行 answers・記録された方針の行）を
返す。答えの text の見出しのセクションが読めなければ（見せた問いに無い Q など）、設計し直さずに訳を添えて同じ文で聞き直す。人の答えの行は
依頼の answers と、それまでの関所の答えの全部から組み直す（番号は通しで変わらない）。

入力（with:）: answer（$LOOP_PREV.gate-theme.output）・previous（$LOOP_PREV.theme-talk.output）・last（$LOOP_PREV.theme-turn.output）・
ports（start の配る値）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute() -> dict:
    raw = {name: os.environ.get(f"INPUTS_{name.upper()}") for name in ("answer", "previous", "last", "ports")}
    import answer
    from src import talk, themetalk

    given = ports.parsed(raw["ports"])
    if not isinstance(given, dict):
        raise ValueError("配る値（ports）が読めない。with: の鍵の結びを確かめる")
    previous = ports.parsed(raw["previous"])
    asks = themetalk.design_asks(previous) if isinstance(previous, dict) else []

    def check(said: dict) -> str:
        return "" if said.get("decision") in answer.STOP_WORDS else themetalk.check(said, asks)

    out = talk.turn(answer_raw=raw["answer"], previous_raw=raw["previous"], last_raw=raw["last"], given=given, recorded=[],
                    place=ports.place(), stage=talk.THEME, check=check)
    out["answers"] = themetalk.answer_rows(out["talks"], given.get("request_answers") or [])
    return out


def fallback(reason: str) -> dict:
    """読めない時は書き手を回さずに止める形（theme-talk が往復を止める）"""
    from src import guard
    return {"plan": False, "answer": None, "prior_design": None, "record": None, "answers": [], "recorded": [], "asks": [], "talks": [],
            "notes": [], "timeline": [], "stop_reason": guard.LINE_SCRIPT, "reason": reason}


ports.run(compute, fallback)
