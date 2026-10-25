"""型 rebuild（変えない段。大きな作り直し。docs/plans/2026-10-24-fix-weapons.md の 3.5）。段 1 は口の形と表の行だけ（注文を書く道は
開けない。route から型を引く表は rebuild を引かない）。型の義務: 境目について evidence.compared の行が 1 つ以上あり、揺れの印の無い
どの行でも古い経路と新しい経路の出力の hash が同じ"""
from __future__ import annotations

BOX = "keep"


def compared_same(f: dict) -> list:
    rows = list(f.get("compared") or [])
    if not rows:
        return ["evidence.compared に新旧を同じ入力で比べた行が無い"]
    bad = [r.get("input") for r in rows if not r.get("noisy") and r.get("old") != r.get("new")]
    return [f"新旧の出力の hash が違う入力 {bad[:10]}"] if bad else []


DUTIES = (compared_same,)
