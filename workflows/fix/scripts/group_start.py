# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 group-start（形 group の子の run の頭）: 親の姿の木を自分の作業ツリーに写し、入力を自分の置き場に写し、git が無視する
ファイルの控えと始めの木を取り、TDD の輪の状態を置く。

- 入力 from_tree が在れば、作業ツリーと index をその木の姿にする（groups.adopt_tree）
- 入力の写し: 入力 out_dir が在る（親が起こした子）なら、親の置き場（out_dir の 1 つ上）の写しを自分の置き場に写す
  （fixboard.adopt_inputs。親の指し札は親の run の物で、この run では引けない）。out_dir が空の単独の run は、指し札を自分で
  引いて節 prep と同じ写しを置く（fixio.prep）
- 親の作業ツリーで 1 つずつ回る子（out_dir が在り from_tree が空）は、前の組の子が結果を書かずに落ちて残した変更を、その子の
  始めの木に戻してから始める（fixboard.drop_unreturned。最後の組の分は join が戻す）
- 記録の根が在れば、自分の作業ツリーの書き込みの記録を空で作る（fixio.start_writes_log。並べた子は自分の作業ツリーを持つ）
- 控え（leftovers.record_ignored）と始めの木（groups.end_tree）。自分の組だけの groups.json（{groups: [組], count: 1, par: false,
  start_tree, out_dir}）
- TDD の輪（tddloop.start）: 実行器は始めの記録の tdd_suite（空は実行器の無い run）。輪の頭で一式を 1 回走らせて元の結末を取る
  （今の works のまま。親の baseline.json は写して受け付けと join の確かめ直しが読む）。返りを置き場の tdd-start.json に控える。
  輪の頭の test_cmd は、線の run の置き場（fixio.line_top）の控えから同じ run の中の緑を使い回す（run の名は始めの記録の run_id。
  旗 tree_run.RERUN_ENV が立てば引かない）
置き場に書く物: 上の写し・fix-ignored-before.json・groups.json・tdd-start.json・tdd-<k>/（輪の状態）。組の置き場
（fixboard.group_dir）に group-start.json（{group, from_tree, out_dir, start_tree}。group-end と drop_unreturned が読む）。
返り {tdd: 輪を回すか, units: 組の単位の数, reason: 回さない理由}。入力が読めない・git が効かない・輪の頭が壊れた: 標準エラーに
1 行で 1。
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import fixio  # noqa: E402

import fixboard  # noqa: E402
import groups  # noqa: E402
import leftovers  # noqa: E402
import startrec  # noqa: E402
import tddloop  # noqa: E402
import tree_run  # noqa: E402

NO_UNITS = "組に単位が無い——TDD のループを回さない"


def read_group() -> dict:
    g = json.loads(os.environ["INPUTS_GROUP"])
    if not isinstance(g, dict) or not isinstance(g.get("group_id"), str) or not g["group_id"] \
            or not isinstance(g.get("unit_ids"), list):
        raise ValueError(f"入力 group が {{group_id, unit_ids, items}} の形でない（{os.environ['INPUTS_GROUP'][:200]!r}）")
    return g


def main() -> dict:
    group = read_group()
    from_tree = os.environ.get("INPUTS_FROM_TREE", "").strip()
    out_dir = os.environ.get("INPUTS_OUT_DIR", "").strip()
    place = fixio.place()
    repo = fixio.repo()
    fixio.start_writes_log()
    if from_tree:
        groups.adopt_tree(repo, from_tree)
    if out_dir:
        fixboard.adopt_inputs(Path(out_dir).parent, place)
        if not from_tree:
            for gdir in sorted(p for p in Path(out_dir).glob("*") if p.is_dir()):
                fixboard.drop_unreturned(repo, gdir, fixio.SKIP)
    else:
        fixio.prep()
    leftovers.record_ignored(place, repo)
    start_tree = groups.end_tree(repo)
    fixboard.write_json(place / fixboard.GROUPS_FILE,
                        {"groups": [group], "count": 1, "par": False, "start_tree": start_tree,
                         "out_dir": out_dir or str(place / "groups")})
    fixboard.write_json(fixboard.group_dir(place, out_dir, group["group_id"]) / fixboard.GROUP_START_FILE,
                        {"group": group, "from_tree": from_tree, "out_dir": out_dir, "start_tree": start_tree})
    start = startrec.read(place)
    keys = [str(k) for k in group["unit_ids"]]
    suite = str(start.get("tdd_suite") or "")
    depths = fixboard.unit_depths(place)
    if not keys:
        out = {"go": False, "reason": NO_UNITS, "suite": suite, "state_file": "", "summary_file": ""}
    else:
        reuse = tree_run.reuse_place(fixio.line_top(out_dir), str(start.get("run_id") or ""),
                                     rerun=bool(os.environ.get(tree_run.RERUN_ENV)))
        boundary.drop_runner_env()   # 対象のテストに Archon の変数を継がせない（place・repo・reuse は先に取った）
        out = tddloop.start(place, repo, suite, json.dumps(keys, ensure_ascii=False),
                            test_cmd=str(start.get("test_cmd") or ""), unit_depths=depths, owed=set(keys), reuse=reuse)
    fixboard.write_json(place / fixboard.TDD_START_FILE, out)
    return {"tdd": bool(out["go"]), "units": len(keys), "reason": str(out.get("reason") or "")}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:   # 回す側の誤り（入力が読めない・置き場が無い・git が効かない・輪の頭が壊れた）
        print(f"group-start: {type(e).__name__}: {' '.join(str(e).split())}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(result)
