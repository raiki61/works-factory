# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""計画の周の前の支度 owed（docs/design/line.md の 1.3 の 6）。判定の後に 1 度。

1. 計画の 1 回目の周が修正案の役を起こすか（owed）: 判定が読めない・直す義務の単位が無い・行き止まりの単位が在るなら偽で、その訳を
   why に（plan の block の周を開く口と同じ決め。src.rounds.owed_why。構造の目はこの node が真を返した run でだけ走る）
2. 事前審査に渡す記録された方針の行（recorded）: 方針の文書の写し・依頼の answers・起動の承認ノードの人の答え・判定の決着済みの論点
   （policy.recorded。始めの記録の欄 policy の固めた版と answers を読む）
出力 {owed, why, recorded, stop_reason}。例外の時は偽・空の行と止めの語 works:line-script を返し、計画の往復へ進めない。

入力（with:）: judgment・answer_ties・materials・world・decisions（判定のまとめの出力の pointer。null 可）・answer（起動の承認ノードの
答え。null 可）・ports（$start.output.ports）・request（request-in の返り。依頼の答えはここから読む）。record（始めの記録の pointer）は在れば読む
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute() -> dict:
    raw_judgment, raw_ties = os.environ.get("INPUTS_JUDGMENT"), os.environ.get("INPUTS_ANSWER_TIES")
    raw_materials, raw_world = os.environ.get("INPUTS_MATERIALS"), os.environ.get("INPUTS_WORLD")
    raw_decisions, raw_answer = os.environ.get("INPUTS_DECISIONS"), os.environ.get("INPUTS_ANSWER")
    raw_ports, raw_record = os.environ.get("INPUTS_PORTS"), os.environ.get("INPUTS_RECORD")
    from src import rounds
    from src import descend
    dealt = descend.dealt(ports.parsed(raw_ports), os.environ.get("INPUTS_REQUEST"))
    record = ports.json(raw_record, "start-record.schema.json") if ports.parsed(raw_record) is not None else None
    why = rounds.owed_why(lambda: ports.file(raw_judgment, "json(shared:judgment.schema.json)"),
                          lambda: ports.file(raw_ties, "json(shared:answer-ties.schema.json)"),
                          lambda: ports.file(raw_materials, "json(shared:materials-state.schema.json)"),
                          lambda: ports.file(raw_world, "jsonl(lib:world-row.schema.json)"),
                          answers=dealt.get("request_answers") or [], takes_push=dealt.get("takes_push") is True)
    decisions = ports.file(raw_decisions, "json(shared:material.schema.json)") if ports.parsed(raw_decisions) is not None else None
    recorded = rounds.recorded_rows(record, dealt, decisions=decisions,
                                    answer=ports.parsed(raw_answer))
    return {"owed": not why, "why": why, "recorded": recorded, "stop_reason": ""}


def fallback(reason: str) -> dict:
    from src import guard
    return {"owed": False, "why": f"直す義務を数えられない: {reason}", "recorded": [], "stop_reason": guard.LINE_SCRIPT}


ports.run(compute, fallback)
