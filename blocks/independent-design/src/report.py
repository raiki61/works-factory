"""独立設計の報告の行（docs/design/independent-design.md の 10 節）と、下げている所の行。

- 問いが立たないと返したのに根拠に <パス>:<行> の名指しが無い時だけ 1 行（lib/runreport.py の _design_lines と同じ字）
- 設計が無い時（status が unusable か failed）だけ 1 行「独立設計: <reason>」
- 設計が在り、根拠の名指しの欠けも無ければ行を返さない（在りかの索引は report の block が出力の pointer から組む）
"""
from __future__ import annotations

import design    # lib/
import oneline   # lib/

# lib/downgrades.json の node が r2.design の行を字のまま（tests/blocks/independent_design が突き合わせる）
DOWNGRADES = [{
    "node": "r2.design",
    "what": "独立設計を修正の前に 1 度だけ作る（作り直さない）。修正の中で申告された前提のずれ（loop.drift_notes）と、裏取りを通っていない目的の判定の控え（loop.purpose_review_stale）は設計の入力に載らない。前提のずれと記録の制約は最後の比較（r2.compare）の頭に貼り、設計の前提を崩していれば『設計の前提が変わった』と理由つきで出させる",
    "versus": "review-graph は r2.design を p4.assemble の後に起こし、前提のドリフトの周に作り直す（その周の drift_notes を読む）"}]


def lines(status: str, reason: str, made) -> list:
    """報告に載せる日本語の行。status は ok・unusable・failed、made は受け取った設計の返答（無ければ None）"""
    if status != "ok":
        return [f"独立設計: {reason}"]
    if isinstance(made, dict) and made.get("question_stands") is False:
        why = made.get("premise_invalid_reason") or made.get("reason") or ""
        if design.anchor_note(why):
            return [f"独立設計は問いが立たないと返したが、{design.UNANCHORED}（{oneline.one_line(why)}）"]
    return []
