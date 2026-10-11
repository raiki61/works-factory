"""直した後に深さを上げ直す節 redepth（docs/design.md の「線」の「順と関所」の 7 の後）。

計画の深さ（案の直しが走ればその深さ）を、修正の後の信号で標準へ上げる（lib/depth.py の raise_doc。下げない）。信号は、
単位ごとに: 修正の段が止めた単位（status が fixed でない単位）、run 全体に: 申し出が在る・答えていない問いが在る・案の直しが
走った・再審が走った。返り {depth: [{unit_id, depth, why}], skip_optional: 軽量で省く理由の文（標準なら空）, raised}。

入力（with:）: depth・replan_depth（`{from, if_skipped: null}`）・units・conflicts（fixed の返り）・questions・answer
（修正前の関所の答え）・replanned・rejudged（after-fix の返り）
"""
import os

import linekit

import depth as depthlib


def redepth(planned, replanned_depth, units, conflicts, questions, answer, *, replanned: bool, rejudged: bool) -> dict:
    rows = replanned_depth if isinstance(replanned_depth, list) else planned if isinstance(planned, list) else []
    doc = {"units": {r["unit_id"]: {"depth": r.get("depth"), "why": [r["why"]] if r.get("why") else []}
                     for r in rows if isinstance(r, dict) and r.get("unit_id")}, "raised": []}
    stopped = {u["unit_id"]: f"修正の段が止めた単位（{u.get('status')}）" for u in units or []
               if isinstance(u, dict) and u.get("unit_id") and u.get("status") != "fixed"}
    run = []
    if conflicts:
        run.append(f"申し出が在る（{len(conflicts)} 件）")
    if questions and answer is None:
        run.append(f"答えていない問いが在る（{len(questions)} 件）")
    if replanned:
        run.append("案の直しが走った")
    if rejudged:
        run.append("再審が走った")
    raised = depthlib.raise_doc(doc, units=stopped, run=run)
    return {"depth": [{"unit_id": key, "depth": row["depth"], "why": " / ".join(row["why"])} for key, row in raised["units"].items()],
            "skip_optional": depthlib.skip_reason(raised), "raised": raised["raised"]}


def fallback(reason: str) -> dict:
    return {"depth": [], "skip_optional": "", "raised": [f"深さを上げ直せなかった（{reason}）"]}


if __name__ == "__main__":
    linekit.run(lambda: redepth(linekit.value(os.environ.get("INPUTS_DEPTH")), linekit.value(os.environ.get("INPUTS_REPLAN_DEPTH")),
                                linekit.items(os.environ.get("INPUTS_UNITS")), linekit.items(os.environ.get("INPUTS_CONFLICTS")),
                                linekit.items(os.environ.get("INPUTS_QUESTIONS")), linekit.value(os.environ.get("INPUTS_ANSWER")),
                                replanned=linekit.flag(os.environ.get("INPUTS_REPLANNED")),
                                rejudged=linekit.flag(os.environ.get("INPUTS_REJUDGED"))),
                fallback)
