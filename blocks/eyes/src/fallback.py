"""eyes の graph のまとめが落ちた時の出力（docs/design/judge-eyes.md の 2.4 の「落ちない」。今の eyes の verdict.py の fallen）。
標準ライブラリだけ（verdict の script が境の口か lib を読めない時にも同じ形を返す）。

- OWN_TITLE・OPTIONAL（直した後の実測が落ちても先へ進む宣言）
- fallen(why) -> 2.2 の欄を全部持つ出力。ok は偽、目の行は全部 unverifiable（理由に誤りの 1 行）、ほかは null か空
"""
OWN_TITLE = "独立の目のまとめ"
OPTIONAL = [{"node": "structure-after__", "bare": False}]
EYES = ("r1", "r2", "r3", "r4")


def fallen(why: str) -> dict:
    reason = f"出口が落ちた: {why}"
    row = {"status": "unverifiable", "reason": reason}
    line = f"- 独立の目のまとめが落ちた（{why}）"
    return {"ok": False, **{eye: dict(row) for eye in EYES}, "questions": [], "passes": [], "premise_check": None, "notes": [],
            "after": None, "dirty": 0, "escalate": 0, "after_ok": False, "report": [line],
            "sections": [{"title": OWN_TITLE, "lines": [line]}], "optional": [dict(r) for r in OPTIONAL]}
