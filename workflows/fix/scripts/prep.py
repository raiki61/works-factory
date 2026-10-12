# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 prep（形 ""）: 入力を置き場に写し、git が無視するファイルを控え（p1.worktree_before）、始めの木を取り、組を作る（lanekit.groups）。
仕事は fixboard.prep が持つ（単独の run の節 group-start も同じ写しを置くのに呼ぶ）。

置き場（boundary.place("fix") = $ARTIFACTS_DIR/fix/<include の名>/）に書く物: r1/start.json（始めの記録の写し。欠けた欄は既定）・
judgment.json・plan-fields.json と凍結の印（planmarks.save）・p2.fix_plan.json（修正案の隣に在れば）・ripple.json・world.json・
depth.json・answers.json・units.json・only-items.json・baseline.json（{cases, exit}）・fix-ignored-before.json・human-notes.md（関所の一言と答えで戻った単位の行。
無ければ書かない）・base-rev.json
（修正前の版。親の HEAD の sha。組の子が写して受け付けの起点にする）・groups.json
（返りと同じ物）。組の子が結果を書く out_dir（置き場の groups/）も作る。記録の根が在れば、この作業ツリーの書き込みの記録を
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
import writelog  # noqa: E402


def main() -> dict:
    writelog.open_here()
    raw = {"start": os.environ.get("INPUTS_START", ""), "judgment": os.environ.get("INPUTS_JUDGMENT", ""),
           "plan": os.environ.get("INPUTS_PLAN", ""), "ripple": os.environ.get("INPUTS_RIPPLE", ""),
           "world": os.environ.get("INPUTS_WORLD", ""), "depth": os.environ.get("INPUTS_DEPTH", ""),
           "answers": os.environ.get("INPUTS_ANSWERS", ""), "units": os.environ.get("INPUTS_UNITS", ""),
           "only_items": os.environ.get("INPUTS_ONLY_ITEMS", ""), "baseline": os.environ.get("INPUTS_BASELINE", "")}
    return fixboard.prep(boundary.place("fix"), boundary.work_tree(), raw, boundary.resolve)


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:   # 回す側の誤り（入力が読めない・置き場が無い・git が効かない）
        print(f"prep: {type(e).__name__}: {' '.join(str(e).split())}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(result)
