"""報告の節「独立の目」に載せる R2 の行（docs/design/r2.md の 5.3）。頭の 1 行は eyekit.headline、続く行は最後の承認ノードと同じ
notes の行と、前提の検算の行（今の runreport._eye_lines の R2 の下の行と前提の検算の行と同じ並び）"""
import eyekit    # lib/
import oneline   # lib/

from src import notes as notes_mod

PREMISE_LINE = "前提の検算: {verdict}（{reason}）"


def lines(row: dict, notes: list, premise_check, replied: bool = True) -> list:
    """row は判定の行、notes は notes の行、premise_check は検算の道の時の {verdict, reason, key, resolution, facts}（ほかは None）、
    replied は検算の役の返答のファイルが読めたか"""
    out = [eyekit.headline("R2", row)]
    out += [f"  - {x}" for x in notes]
    if premise_check:
        out.append(PREMISE_LINE.format(verdict=premise_check.get("verdict") or "語が無い", reason=oneline.one_line(premise_check.get("reason") or "")))
        facts = {k: premise_check.get(k) or ("" if k != "facts" else []) for k in ("key", "resolution", "facts")}
        out += [f"  - {x}" for x in notes_mod.premise_fact_lines(facts, replied)]
    return out
