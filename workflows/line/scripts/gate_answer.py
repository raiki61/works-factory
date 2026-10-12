# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""人の関所の答えを受ける返しの節（answer-start・answer-final と、before_fix_answer を通して answer-before-fix、replan_answer を通して
answer-replan。埋め P2）。

関所が方針で飛ばされても走る（trigger_rule: none_failed_min_one_success）。関所の出力は `{from, if_skipped: null}` で受ける。
返り {go, answer, stop_reason}: 関所が飛ばされたら前の節が決めた go と止めの理由をそのまま返し、answer は null。
関所が開いたら答え {decision, text} を返し、通す語なら go、止める語なら go: false と止めの理由 human:<関所>。
asked_raw（関所で見せた問いの行。before_fix_answer だけが渡す）が在れば、答えに asked を足す。
答えは run の置き場の gates/<関所>.json に書く（同じ関所の答えは書き直す。人が読む控えで、関所の文が名指す）。
報告へは返りの answer が collect を通って届く。

入力（with:）: gate（関所の出力）・go・stop_reason（関所の前の節の決め）・place（関所の節の id）
"""
import json
import os
from pathlib import Path

import linekit

ANSWERS = "gates"


def decision_of(raw) -> dict:
    """関所の出力の字を {decision, text} に。決めの語を持つ関所は {decision, text} の JSON を返す。筋書きの関所はいつも approved の字"""
    got = linekit.value(raw)
    if isinstance(got, dict) and isinstance(got.get("decision"), str):
        return {"decision": got["decision"], "text": str(got.get("text") or "")}
    if got == linekit.DRY_RUN_APPROVED:
        return {"decision": "approve", "text": ""}
    return {"decision": str(got), "text": ""}


def answer(gate_raw, go_raw, stop_raw, place: str, artifacts: Path, asked_raw=None) -> dict:
    if linekit.text(gate_raw) == "":
        return {"go": linekit.flag(go_raw), "answer": None, "stop_reason": linekit.text(stop_raw)}
    got = decision_of(gate_raw)
    if asked_raw is not None:
        got["asked"] = [line for line in linekit.items(asked_raw) if isinstance(line, str)]
    folder = artifacts / ANSWERS
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{place}.json").write_text(json.dumps(got, ensure_ascii=False) + "\n", encoding="utf-8")
    go = got["decision"] in linekit.GO_WORDS
    return {"go": go, "answer": got, "stop_reason": "" if go else linekit.HUMAN + place}


def fallback(reason: str) -> dict:
    return {"go": False, "answer": None, "stop_reason": linekit.LINE_SCRIPT}


if __name__ == "__main__":
    linekit.run(lambda: answer(os.environ.get("INPUTS_GATE"), os.environ.get("INPUTS_GO"), os.environ.get("INPUTS_STOP_REASON"),
                               os.environ["INPUTS_PLACE"], Path(os.environ["ARTIFACTS_DIR"])),
                fallback)
