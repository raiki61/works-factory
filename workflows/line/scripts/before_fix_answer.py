# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正前の承認ノードの答えを受ける返し answer-before-fix（埋め P2。docs/design/line.md の 2 節の 2）。

答えの読みと返り {go, answer, stop_reason} は gate_answer と同じ（lib/answer.py の taken）。答えの asked は ask-before-fix が載せた項目の
行で、fix の answers が問いの単位を直す義務に戻す（S46）。無人の run が推しで進んだ時は ask-before-fix の pushed を答えとして記録する。
通した答えが方針の文書の変化の項目を通した時（ask-before-fix の policy_changed が真で通す語）は、今の方針の文書を固め直し
（policy.freeze）、始めの記録の欄 policy を書き直し（書き直すのは始めの記録の書き手の line だけ）、返りの policy にその写しのパスを
返す。ほかは配る値の policy（start が固めた写し）をそのまま返す（今の before_fix_answer.carry_policy と boardview.passed_version）。

対話モードの run で、承認ノードが開かずに設計の相談の合意（ask-before-fix の agreed）で修正へ進む時は、その合意を答えとして同じく書く
（合意の一言は修正役に届き、合意で見せた行は asked として直す義務に戻る。合意した承認を聞き直さないまま、答えの控えは残す）。
合意の後に新しく出た行で承認ノードが開き、人が通した時は、合意で見せた行を asked の前に、合意の一言を答えの一言の前に足して書く
（合意した中身を修正役へ落とさない）。

入力（with:）: gate（承認ノードの出力。飛ばされたら null）・go・stop_reason・place・asked・pushed・policy_changed・agreed（ask-before-fix の
返り）・record（始めの記録の pointer）・ports（start の配る値）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute() -> dict:
    raw = {"gate": os.environ.get("INPUTS_GATE"), "go": os.environ.get("INPUTS_GO"), "stop_reason": os.environ.get("INPUTS_STOP_REASON"),
           "place": os.environ.get("INPUTS_PLACE"), "asked": os.environ.get("INPUTS_ASKED"), "pushed": os.environ.get("INPUTS_PUSHED"),
           "policy_changed": os.environ.get("INPUTS_POLICY_CHANGED"), "agreed": os.environ.get("INPUTS_AGREED"),
           "record": os.environ.get("INPUTS_RECORD"), "ports": os.environ.get("INPUTS_PORTS")}
    import answer
    import policy
    from src import startrec

    given = ports.parsed(raw["ports"]) or {}
    asked = ports.parsed(raw["asked"]) or []
    gate, agreed = ports.parsed(raw["gate"]), ports.parsed(raw["agreed"])
    agreed = agreed if isinstance(agreed, dict) and agreed.get("decision") in answer.GO_WORDS else None
    if gate in (None, "") and agreed is not None and ports.flag(raw["go"]):
        gate = {"decision": agreed.get("decision"), "text": agreed.get("text") or ""}
        asked = agreed.get("asked") or []
    elif gate not in (None, "") and agreed is not None:   # 合意の後に新しい行で開いた: 合意した行と一言も修正役へ運ぶ
        said = answer.decision(gate)
        if said["decision"] in answer.GO_WORDS:
            text = "\n".join(t for t in (str(agreed.get("text") or "").strip(), said["text"].strip()) if t)
            gate = {"decision": said["decision"], "text": text}
            asked = [*(agreed.get("asked") or []), *(asked if isinstance(asked, list) else [])]
    got = answer.taken(gate, go=ports.flag(raw["go"]), stop_reason=ports.text(raw["stop_reason"]),
                       place=ports.text(raw["place"]), folder=ports.place(), asked=asked if isinstance(asked, list) else [],
                       pushed=ports.parsed(raw["pushed"]))
    frozen = str(given.get("policy") or "")
    if got["go"] and got["answer"] is not None and ports.flag(raw["policy_changed"]):
        frozen = refreeze(ports.file(raw["record"]), startrec, policy)
    return {**got, "policy": frozen}


def refreeze(record_path, startrec, policy) -> str:
    """今の方針の文書を固め直し、始めの記録の欄 policy を書き直して、写しのパスを返す（文書が消えていれば空）"""
    doc = startrec.load(record_path)
    old = policy.version(doc) or {}
    doc["policy"] = policy.freeze(ports.place(), Path.cwd(), old.get("named") or "")
    startrec.save(record_path, doc)
    return policy.frozen_copy(doc)


def fallback(reason: str) -> dict:
    from src import guard

    return {"go": False, "answer": None, "stop_reason": guard.LINE_SCRIPT, "policy": ""}


ports.run(compute, fallback)
