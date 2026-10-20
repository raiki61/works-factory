"""前提の実測の報告の行（docs/design/premises.md の 3.4。lib/runreport.py の premise_lines の、依頼の行と制約を値で受ける形の写し）"""
from __future__ import annotations

HEAD = "依頼の実測を測り直せなかった（前提は仮説）: "


def lines(findings, constraints, hypothesis: str) -> list:
    """依頼が実測（measured）を持っていたのに、制約が仮説でしか書けなかった行ごとの報告の行。依頼の行の where を text に含む最初の
    仮説の制約を名指す。仮説の制約が無ければ []"""
    hyp = [c for c in constraints or [] if isinstance(c, dict) and c.get("kind") == hypothesis]
    out = []
    for f in findings or []:
        if hyp and isinstance(f, dict) and f.get("measured") and f.get("where"):
            c = next((c for c in hyp if str(f["where"]) in str(c.get("text") or "")), None)
            if c is not None:
                out.append(f"{HEAD}{f['where']}——{c.get('text')}")
    return out
