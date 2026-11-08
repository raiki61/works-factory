"""報告の節「独立の目」に載せる R2 の行（docs/design/r2.md の 5.3）。頭の 1 行は eyekit.headline、続く行は最後の承認ノードと同じ
notes の行と、前提の検算の行（今の runreport._eye_lines の R2 の下の行と前提の検算の行と同じ並び）"""
import eyekit    # lib/
import gatemarks  # lib/。頼みの解き方の言い方・人に聞く訳・推しの尾（PR 1 の means_drift_text と同じ字）
import oneline   # lib/
import plainask  # lib/。人に聞く項目の要素の読み口（問いは字でも {text, title} の行でも本文を読む）

from src import notes as notes_mod

PREMISE_LINE = "前提の検算: {verdict}（{reason}）"
UNCHECKED = "（引用を照らせなかった: {why}）"   # 照らせない頼みどおりの違いの尾（推しの尾の代わり。窓口の決め・案 C）


def means_conflict_text(row: dict, said: dict, gaps: list) -> str:
    """頼みどおりの違いの行（比べの役の request_conflicts の 1 行）の問いの文（docs/design/plan-review.md の 20 章の 6.2 の 6）。
    said は {M<n>: 頼みの解き方の文}、gaps は照らせない訳（空なら推しの尾を付け、在れば推しを外して訳を付ける）"""
    head = (f"R2: 差分は頼みの解き方 {gatemarks._means_said(row.get('means'), said)}どおりだが、独立設計と食い違う——"
            f"{oneline.one_line(row.get('why') or '')}（人に聞く訳: {gatemarks.MEANS_WHY}）")
    if gaps:
        return head + UNCHECKED.format(why="；".join(gaps))
    return head + gatemarks._push({gatemarks.RECOMMEND: row.get(gatemarks.RECOMMEND)})


def lines(row: dict, notes: list, premise_check, replied: bool = True, questions=()) -> list:
    """row は判定の行、notes は notes の行、premise_check は検算の道の時の {verdict, reason, key, resolution, facts}（ほかは None）、
    replied は検算の役の返答のファイルが読めたか、questions は頼みどおりの違いの問い（本文は means_conflict_text の文。字でも {text, title} の行でもよく、
    報告の行には本文を並べる）"""
    out = [eyekit.headline("R2", row)]
    out += [f"  - {plainask.item_text(q)}" for q in questions]
    out += [f"  - {x}" for x in notes]
    if premise_check:
        out.append(PREMISE_LINE.format(verdict=premise_check.get("verdict") or "語が無い", reason=oneline.one_line(premise_check.get("reason") or "")))
        facts = {k: premise_check.get(k) or ("" if k != "facts" else []) for k in ("key", "resolution", "facts")}
        out += [f"  - {x}" for x in notes_mod.premise_fact_lines(facts, replied)]
    return out
