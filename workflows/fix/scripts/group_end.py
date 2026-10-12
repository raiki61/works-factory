# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 group-end（形 group の子の run の終わり）: 組の結果を out_dir/<group_id>/result.json に書く（fixboard.group_result）。

読む物（無ければ空で読む）: 組の置き場（fixboard.group_dir）の group-start.json（始めの木）と、自分の置き場の
tdd-start.json（TDD の輪の頭の返り。輪の結果は tddloop.exit_fields、輪の状態のパスは tdd_state として結果に載せる）・fix-units.json（修正の輪の単位ごとの結末
{unit_key: {status, reason}}）・fix-reply.json（最後に受け付けた修正役の返答。異議 rejudge_requested と 6 つの印）・
allowed-tests.json（許したテストの変更のパス）・conflicts.json（今の段の申し出。conflict.this_pass。2 回目の修正の段が写した 1 回目の段の行は載せない）。終わりの木は作業ツリーの今の姿
（groups.end_tree）。子の作業ツリーの実パスも載せる（join がそこから子の書き込みの記録を引き、
親の記録へ写す。fixio.writes_log）。
TDD の輪の状態が済んでいなければ tdd を ran: false と理由にする。前の節が落ちた子ではこの節は走らず、結果のファイルは無い
（並べない run は、その子が親の作業ツリーに残した変更を次の組の group-start か join が戻す。fixboard.drop_unreturned）。
書く先: 入力 out_dir が在ればその下の <group_id>/result.json、空の単独の run は自分の置き場の groups/<group_id>/result.json。
返り {result_file}。入力 group が読めない・git が効かない・置き場のファイルが壊れた: 標準エラーに 1 行で 1。
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

import conflict  # noqa: E402
import fixboard  # noqa: E402
import groups  # noqa: E402
import tddloop  # noqa: E402


def tdd_exit(started) -> dict:
    """TDD の輪の出口の欄（tddloop.exit_fields）。輪の頭の返りが無い・輪が済んでいなければ ran: false と理由"""
    if not isinstance(started, dict):
        return {"ran": False, "suite": "", "reason": f"置き場に {fixboard.TDD_START_FILE} が無い（group-start が走らなかった）",
                "units": []}
    try:
        return tddloop.exit_fields(started)
    except tddloop.Broken as e:
        return {"ran": False, "suite": str(started.get("suite") or ""),
                "reason": f"TDD の輪が済まずに抜けた（{' '.join(str(e).split())}）", "units": []}


def main() -> dict:
    group = json.loads(os.environ["INPUTS_GROUP"])
    if not isinstance(group, dict) or not group.get("group_id"):
        raise ValueError("入力 group に group_id が無い")
    out_dir = os.environ.get("INPUTS_OUT_DIR", "").strip()
    place = fixio.place()
    repo = fixio.repo()
    gdir = fixboard.group_dir(place, out_dir, group["group_id"])
    began = fixboard.read_json(gdir / fixboard.GROUP_START_FILE) or {}
    reply_path = place / fixboard.FIX_REPLY_FILE
    result = fixboard.group_result(
        group, start_tree=str(began.get("start_tree") or fixboard.start_tree(place)), end_tree=groups.end_tree(repo),
        tdd=tdd_exit(fixboard.read_json(place / fixboard.TDD_START_FILE)), tdd_state=fixboard.loop_files(place)[0],
        fix_units=fixboard.read_json(place / fixboard.FIX_UNITS_FILE, {}), reply=fixboard.read_json(reply_path),
        reply_file=str(reply_path) if reply_path.is_file() else "",
        allowed=fixboard.read_json(place / fixboard.ALLOWED_TESTS_FILE, []) or [], conflicts=conflict.this_pass(place),
        worktree=os.path.realpath(repo))
    target = gdir / fixboard.RESULT_FILE
    fixboard.write_json(target, result)
    return {"result_file": str(target)}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"group-end: {type(e).__name__}: {' '.join(str(e).split())}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(out)
