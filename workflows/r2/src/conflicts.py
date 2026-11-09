"""頼みどおりの違い request_conflicts の照らしと問いの行（docs/design/plan-review.md の 20 章の 6.2 の 4〜6。持ち主の決め means-ask）。

比べの役が「差分は頼みの解き方 M<n> どおりで、独立設計は別の形をとる」と書いた行を、状態（status）に数えず、最後の承認ノードで人に聞く
問いの文にする。引用は機械が照らす（yes/no）: design_quote は独立設計の本文に、diff_quote は累積差分の足した行か消した行の 1 行に
字のまま在るか。照らせない行は推しを持たせずに聞く（窓口の決め・案 C。出し直しの輪は持たない）。照らせた行だけ、役が書いた推しを行の欄 recommend に写す。照らし方は lib/design.py の
means_drift_gaps と同じで、受ける材料（独立設計の本文と累積差分）が R2 の物なので、使う block が R2 だけのここに置く（憲法 4）。
"""
from __future__ import annotations

import gatemarks   # lib/。推しの形（_recommend_gap）
import plainask    # lib/。人に聞く文の決まり
import worldmark   # lib/。頼みの解き方の番号（means_hints）

from src import report

FIELD = "request_conflicts"   # 比べの役の返答の欄


def changed_lines(diff_text: str) -> list:
    """累積差分の足した行と消した行の字（頭の + か - を外す。ファイルの頭の行 +++・--- は除く）"""
    return [line[1:] for line in (diff_text or "").splitlines()
            if line[:1] in ("+", "-") and not line.startswith(("+++", "---"))]


def gaps(row: dict, said: dict, design_text: str, lines: list) -> list:
    """行 1 つの照らせない訳の並び（照らせれば空）"""
    out = []
    key = row.get("means")
    if key not in said:
        out.append(f"{key} が頼みの解き方の番号の範囲の外（" + (f"M1〜M{len(said)}" if said else "頼みの解き方が渡されていない") + "）")
    dq, pq = row.get("design_quote"), row.get("diff_quote")
    if not (isinstance(dq, str) and dq.strip() and dq in (design_text or "")):
        out.append("design_quote が独立設計の本文に字のまま無い")
    if not (isinstance(pq, str) and pq.strip() and any(pq in line for line in lines)):
        out.append("diff_quote が累積差分の足した行か消した行の 1 行に字のまま無い")
    rec = row.get(gatemarks.RECOMMEND)
    bad = gatemarks._recommend_gap(rec)
    if bad:
        out.append(bad)
    out += plainask.gaps("why", row.get("why"))
    if not bad:
        for k in gatemarks.RECOMMEND_KEYS[1:]:
            out += plainask.gaps(f"{gatemarks.RECOMMEND}.{k}", rec[k])
    return out


def questions(reply, means, design_text: str, diff_text: str) -> list:
    """比べの役の返答の request_conflicts の行ごとの問いの行 {text, title?, recommend?}（行が無い・返答が読めなければ空）。text は問いの文、
    title は役が行に書いた題を lib の読み口 plainask.item_title が 1 行に畳んだ字（題が無い・空白だけの行は title の欄を持たない。題で行を拒まない）、
    recommend は引用を照らせた行（gaps が空）に役が書いた推し（照らせない行は欄を持たない）"""
    rows = reply.get(FIELD) if isinstance(reply, dict) else None
    said = worldmark.means_hints(means)
    lines = changed_lines(diff_text)
    out = []
    for row in rows or []:
        if isinstance(row, dict):
            missed = gaps(row, said, design_text, lines)
            out.append(plainask.item_row(report.means_conflict_text(row, said, missed), plainask.item_title(row),
                                         None if missed else row.get(gatemarks.RECOMMEND)))
    return out
