# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 prep（形 ""）: 入力を置き場に写し、git が無視するファイルを控え（p1.worktree_before）、始めの木を取り、組を作る（lanekit.groups）。
仕事は fixboard.prep が持つ（単独の run の節 group-start も同じ写しを置くのに呼ぶ）。

置き場（boundary.place("fix") = $ARTIFACTS_DIR/fix/<include の名>/）に書く物: r1/start.json（始めの記録の字のままの写し。startrec.adopt）・
judgment.json と隣の answer-ties.json・materials.json（在れば）・plan-fields.json と凍結の印（planmarks.save）・p2.fix_plan.json（修正案の隣に在れば）・
p2.plan_review.json（入力 plan_review の事前審査の返答の写し。修正役の plan_faces と差分の審査の材料。無ければ書かない）・ripple.json・
depth.json・answers.json・units.json・only-items.json・baseline.json（{cases, exit}）・fix-ignored-before.json・human-notes.md（関所の一言と答えで戻った単位の行と、
入力 notes の機械の申し送り。無ければ書かない）・base-rev.json
（修正前の版。親の HEAD の sha。組の子が写して受け付けの起点にする）・groups.json
（返りと同じ物）。入力 prior_conflicts（1 回目の段の申し出と裁定のポインタ。2 回目の修正の段だけ）が在れば、その先のフォルダの申し出と
裁定と TDD のループの状態を、組を作る前に写す（fixboard.adopt_prior_pass。直す項目 only_items の案の直しを待つ行は案を直した行になる）。
組の子が結果を書く out_dir（置き場の groups/）も作る。記録の根が在れば、この作業ツリーの書き込みの記録を
空で作る（writelog.open_here。在れば触らない）。
返り {groups: [{group_id, unit_ids, items}], count, par, start_tree, out_dir}。入力が読めない・git が効かない: 標準エラーに 1 行で 1。
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import fixboard  # noqa: E402
import oneline  # noqa: E402
import writelog  # noqa: E402

INPUTS = ("start", "judgment", "plan", "plan_review", "ripple", "depth", "answers", "units", "only_items", "baseline",
          "prior_conflicts", "notes")



def main() -> dict:
    writelog.open_here()
    raw = {name: os.environ.get(f"INPUTS_{name.upper()}", "") for name in INPUTS}
    return fixboard.prep(boundary.place("fix"), boundary.work_tree(), raw, boundary.parsed, boundary.pointed)


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:   # 回す側の誤り（入力が読めない・置き場が無い・git が効かない）
        print(f"prep: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(result)
