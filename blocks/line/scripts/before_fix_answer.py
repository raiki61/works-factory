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

入力（with:）: gate（承認ノードの出力。飛ばされたら null）・go・stop_reason・place・asked・pushed・policy_changed（ask-before-fix の返り）・
record（始めの記録の pointer）・ports（start の配る値）
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
           "policy_changed": os.environ.get("INPUTS_POLICY_CHANGED"), "record": os.environ.get("INPUTS_RECORD"),
           "ports": os.environ.get("INPUTS_PORTS")}
    import answer
    import policy
    from src import startrec

    given = ports.parsed(raw["ports"]) or {}
    asked = ports.parsed(raw["asked"]) or []
    got = answer.taken(ports.parsed(raw["gate"]), go=ports.flag(raw["go"]), stop_reason=ports.text(raw["stop_reason"]),
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
