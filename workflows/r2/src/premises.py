"""設計の後の前提の材料と控え（docs/design/r2.md の 1.5）。比べの役の頭に貼る。

人が決めた前提の材料（承認ノードの答え・依頼が名指した設計書の節・対象の地図）は lib/design.py の premise_material が組む（independent-design と
共通。見出しと頼みの文は共通の断片 design-premises が持つ）。ここは view_of でその見え方を作り、後半は元の eyeverdict の premise_section の、
独立設計の後に来た答え・前提のずれ・記録の制約・控えの組み方を、値で受ける形に写した物。
"""
from __future__ import annotations

import types

import cite      # lib/。依頼の名指しを引く Markdown の読み（MD_LINK・_md_lines・_md_slugs）
import design    # lib/
import eyekit    # lib/
from rolekit import BoardGap   # lib/

NO_REQUEST = "依頼のファイルが渡っていない"
NO_MARKS = "（修正の印が渡っていない）"
NO_NOTE = "（申告の文なし）"
NONE = "（無い）"
KINDS = (*design.PREMISE_KINDS, "drift", "constraint", "means")   # 控えの given の kind の許す一覧（貼る入力の種類 + 後半が足す 3 つ）


# 依頼の名指しを引く道具（Markdown のリンク・囲いの外の行・見出しのアンカー）は lib/cite.py の物を使う
MD_RULES = types.SimpleNamespace(MD_LINK=cite.MD_LINK, _md_lines=cite._md_lines, _md_slugs=cite._md_slugs)


def view_of(answers, request_text: str) -> types.SimpleNamespace:
    """前提を組むだけの見え方（承認ノードの答え・依頼の本文・名指しを引く道具だけ）"""
    return types.SimpleNamespace(record={"process": {"human_items": eyekit.human_items(answers)}},
                                 state={"inputs": {"request": request_text}}, rules=MD_RULES)


# ---------------------------------------------------------------- 後半（premise_section の値で受ける写し）
def _lines(rows: list, none: str = NONE) -> str:
    return "\n".join(f"- {r}" for r in rows) if rows else none


def constraint_rows(constraints) -> list:
    """記録の制約の行 `（<kind>）<text>`。port constraints の値（行の配列か、それを constraints の欄に持つ object）"""
    rows = constraints.get("constraints") if isinstance(constraints, dict) else constraints
    return [f"（{c.get('kind')}）{c.get('text')}" if isinstance(c, dict) else str(c) for c in rows or []]


def constraints_text(constraints) -> str:
    return _lines(constraint_rows(constraints))


def after(ledger: dict, request_read: bool, design_premises, changed, constraints, means=None) -> dict:
    """設計の後の前提。{late, drift, constraints, ledger}。late は独立設計の控えの seen.count より後の人の答えの行（控えが無ければ
    数えず空）、drift は前提のずれの申告（changed.premise_drift が真なら premise_drift_note。空なら「（申告の文なし）」。changed が
    空なら「（修正の印が渡っていない）」）、constraints は記録の制約の行。ledger は貼った物の控え（given に drift・constraint の行を足し、
    依頼のファイルが読めない時は withheld に足し、控えが在れば after_design を持つ）。means は比べの役に貼った頼みの解き方
    {M<n>: 文}（given に kind means の 1 文 1 行で載る。独立設計の役には渡さないので、その控えには無い）。kind が KINDS の外なら BoardGap"""
    ledger = {"given": list(ledger["given"]), "withheld": list(ledger["withheld"]), "seen": ledger["seen"]}
    if not request_read:
        ledger["withheld"].append({"kind": "named_section", "what": "依頼", "why": NO_REQUEST})
    seen = design_premises.get("seen") if isinstance(design_premises, dict) else None
    late = ""
    if isinstance(seen, dict):
        answers = [g["what"] for g in ledger["given"] if g.get("kind") == "human_answer"]
        ledger["after_design"] = answers[seen.get("count") or 0:]
        late = _lines(ledger["after_design"], "")
    changed = changed if isinstance(changed, dict) and changed else None
    flag = changed.get("premise_drift") if changed else None
    drift = [str(changed.get("premise_drift_note") or "").strip() or NO_NOTE] if flag is True else []
    ledger["given"] += [{"kind": "drift", "what": d} for d in drift] + [{"kind": "constraint", "what": c} for c in constraint_rows(constraints)]
    ledger["given"] += [{"kind": "means", "what": f"{k}: {t}"} for k, t in (means or {}).items()]
    outside = sorted({g["kind"] for g in ledger["given"]} - set(KINDS))
    if outside:
        raise BoardGap(f"貼った前提の種類が許す一覧（{' / '.join(KINDS)}）の外: {', '.join(outside)}")
    return {"late": late, "drift": _lines(drift) if flag is not None else NO_MARKS, "constraints": constraints_text(constraints),
            "ledger": ledger}
