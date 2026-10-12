# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正前の関所の答えを受ける返しの節 answer-before-fix（埋め P2）。

関所の答えの読みと返り {go, answer, stop_reason} は gate_answer と同じ（lib/answer.py の taken）。答えの asked は ask-before-fix が
関所に載せた項目の行（$ask-before-fix.output.asked）。fix の置き場の読み（lib/gatemarks.py の gate_items）は asked の行が問いの頭で
始まる時だけ、その問いを人が答えたと読み、問いの単位を直す義務に戻す。事前審査（replan-review の gate_answers）は asked の行を聞き直さない。

関所を通した答えは、始めの記録の欄 policy を事前審査が固め直した版（boardview.passed_version。人が方針の文書の変化を通した時だけ
変わる）で書き直す。fix・eyes・judge の再審は始めの記録の写し（policy.frozen_copy）を読むので、ブロックの入力を足さずに人が通した版が
届く。止めた答え・関所が開かなかった run は書き直さない。

入力（with:）: gate_answer の入力と asked（関所に載せた項目の行。$ask-before-fix.output.asked）と start（始めの記録の指し札）
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import answer
    import boardview
    import policy


def take(gate_raw, go_raw, stop_raw, place: str, asked_raw, start_raw, artifacts: Path) -> dict:
    got = answer.taken(boundary.value(gate_raw), go=boundary.flag(go_raw), stop_reason=boundary.text(stop_raw), place=place,
                       folder=artifacts, asked=boundary.items(asked_raw))
    if got["go"] and got["answer"] is not None:
        carry_policy(start_raw, got["answer"], artifacts)
    return got


def from_env() -> dict:
    """take の引数のうち with: の欄（全部を読む）"""
    return {"gate_raw": os.environ.get("INPUTS_GATE"), "go_raw": os.environ.get("INPUTS_GO"),
            "stop_raw": os.environ.get("INPUTS_STOP_REASON"), "place": os.environ.get("INPUTS_PLACE"),
            "asked_raw": os.environ.get("INPUTS_ASKED"), "start_raw": os.environ.get("INPUTS_START")}


def carry_policy(start_raw, passed: dict, artifacts: Path) -> None:
    """始めの記録の欄 policy を、関所の答えを受けた事前審査の版で書き直す（事前審査が版を置いていない・版が変わらなければ書かない）"""
    got = boardview.passed_version(artifacts / boardview.FOLDER, passed)
    if got is None:
        return
    path = boundary.resolve(boundary.value(start_raw))
    doc = json.loads(path.read_text(encoding="utf-8"))
    if got == policy.version(doc):
        return
    doc["policy"] = got
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fallback(reason: str) -> dict:
    return {"go": False, "answer": None, "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(lambda: take(**from_env(), artifacts=Path(os.environ["ARTIFACTS_DIR"])), fallback)
