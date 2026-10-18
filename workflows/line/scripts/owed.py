# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""判定の後に、計画の 1 回目の周が修正案の役を起こすかを決めるノード owed。構造のサブグラフはこのノードが真を返した run でだけ走る
（元 works/darkfactory/lib/line_edge.py の structure_edge(plan_go=False)・works/darkfactory/darkfactory.yaml:454-457。役を起こさない
周は測らず目も起こさない）。

決めは計画の周を開く口と同じ物を引く: 始めの記録・判定・定石の行が読めない（読めない入力の訳）、判定に直す義務の単位が無い・
行き止まりの単位が在る（lib/planfile.held_why）なら偽。出力 {owed, why, stop_reason}（why は偽の訳。真なら空）。
例外の時は偽と止めの理由 works:line-script を返し、計画の往復へ進めない。

入力（with:）: start（始めの記録のポインタ）・judgment・answer_ties・materials・world（判定の出力のポインタ。null 可）
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import planfile


def owed(start_raw, judgment_raw, ties: str, materials: str, world_raw) -> dict:
    start, bad_start = planfile.read_pointed(start_raw, boundary.pointed)
    judgment, bad = planfile.read_judgment(judgment_raw, start, boundary.pointed, ties=ties, materials=materials)
    _, bad_world = planfile.world_rows(world_raw, boundary.pointed)
    unread = [f"{name} が読めない（{b}）" for name, b in (("start", bad_start), ("world", bad_world), ("判定", bad)) if b]
    why = "。".join(unread) or planfile.held_why(judgment)
    return {"owed": not why, "why": why, "stop_reason": ""}


def from_env() -> dict:
    return {"start_raw": os.environ.get("INPUTS_START", ""), "judgment_raw": os.environ.get("INPUTS_JUDGMENT", ""),
            "ties": os.environ.get("INPUTS_ANSWER_TIES", ""), "materials": os.environ.get("INPUTS_MATERIALS", ""),
            "world_raw": os.environ.get("INPUTS_WORLD", "")}


def fallback(reason: str) -> dict:
    return {"owed": False, "why": f"直す義務を数えられない: {reason}", "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(lambda: owed(**from_env()), fallback)
