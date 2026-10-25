"""独立設計の返答から、どの役を起こすかと、起こさない時の訳の字を決める（docs/design/r2.md の 1.5）。lib/eyeverdict.py の
r2_compare_due・r2_premise_invalid・premise_reason・read_design と字（:55-59・:90）の写しで、ファイルでなく値で受ける形。"""
from __future__ import annotations

import design   # lib/。MISSING

R2_PREMISE_HEAD = "前提不成立: "
R2_MISSING_HEAD = f"{design.MISSING}: "
R2_NOT_COMPARED_HEAD = "独立設計と比べなかった: "
R2_NO_PURPOSE = R2_NOT_COMPARED_HEAD + "目的の文が空"
VERDICTS = ("resolved", "escalate")   # 検算の役の verdict の語（約束の語）
NO_DESIGN = "独立設計の出力が渡っていない"
DESIGN_NOT_OBJECT = "独立設計の控えが JSON の object でない"


def read_design(value, reason: str = "") -> dict:
    """独立設計の返答（port design の値）。null なら {"missing": 訳}（訳は port design_reason。空なら NO_DESIGN）。object でなければ
    {"missing": DESIGN_NOT_OBJECT}（port の形 shared:design.schema.json が閉じた object だけを通し、question_stands・reason・design の
    無い値と宣言の外の欄を持つ値は intake の ports.json が拒むので、この枝は形の照らしの外の守り）"""
    if value is None:
        return {"missing": reason or NO_DESIGN}
    return value if isinstance(value, dict) else {"missing": DESIGN_NOT_OBJECT}


def compare_due(design_doc: dict, purpose: str) -> bool:
    """独立設計が在り・問いが立つと言い・目的の文が空でない時に比べの役を起こす"""
    return "missing" not in design_doc and design_doc.get("question_stands") is True and bool(purpose.strip())


def premise_invalid(design_doc: dict) -> bool:
    """独立設計が在り、問いは立たないと言った時に検算の役を起こす（目的の文が空でも回る）"""
    return "missing" not in design_doc and design_doc.get("question_stands") is False


def premise_reason(design_doc: dict) -> str:
    return design_doc.get("premise_invalid_reason") or design_doc.get("reason") or ""
