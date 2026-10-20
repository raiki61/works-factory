"""報告の節「独立の目」に載せる R4 の行（docs/design/r4.md の 5.3）。頭の 1 行は eyekit.headline"""
import eyekit      # lib/
import gatemarks   # lib/

# 元 lib/runreport.py:142 の EYE_PASSES_HEAD の字
EYE_PASSES_HEAD = ("修正前の承認ノードで通した行（人が通したか、無人の run が推しで通したので、独立の目 R4 の問いから外して聞き直さ"
                   "なかった行。どちらかは行ごとに書く）")
R3_NAME = "R3（R4 と同じ会話で見た）"


def lines(row: dict, coherence, passes: list, replied: bool) -> list:
    """row は R4 の判定の行、coherence はまとめた形の R3 の判定の行（まとめない run は None）、passes は人が通した行、replied は役の返答が在るか"""
    out = [eyekit.headline("R4", row)]
    if coherence is not None:
        out.append(eyekit.headline(R3_NAME, coherence))
    if replied:
        out += [f"{EYE_PASSES_HEAD}: {len(passes)} 件", *[f"  - {x}" for x in gatemarks.pass_lines(passes)]]
    return out
