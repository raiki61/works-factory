"""報告の節「並行 PR」の行（docs/design/parallel-pr.md の 8 節）。"""
import oneline   # lib/


def draft_lines(rows) -> list:
    """申し送りの下書きの行（元 lib/prcheck.py の draft_lines。note を持つ行だけ）"""
    return [f"並行 PR #{r.get('pr')} の担当への申し送りの下書き（{'・'.join(map(str, r.get('files') or []))}。投稿していない）: "
            f"{r['note']}" for r in rows or [] if isinstance(r, dict) and r.get("note")]


def lines(status: str, reason: str, material: dict, drafts, missing) -> list:
    """頭の 1 行・下書きの行・読んだ証拠が欠けた時の 1 行"""
    if status == "failed":
        out = [f"並行 PR: 確かめが終わらなかった（{oneline.one_line(reason)}）"]
    else:
        why = next((material.get(k) for k in ("reason", "detail", "checked") if material.get(k)), "") or reason
        out = [f"並行 PR: {status}（{oneline.one_line(why)}）"]
    out += draft_lines(drafts)
    if missing:
        out.append(f"並行 PR の役が渡し物を読んだ記録が無い（{'・'.join(map(str, missing))}）")
    return out
