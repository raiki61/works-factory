# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node ci-accept: 任せ先の CI の役の返答を受け付ける。run が包みを通ると宣言した（env の fence.RECORDS_ENV）なら、先に包みの起動の記録で
ci-prep の時刻（ci-snapshot.json の prepared_at）より後にこの作業ツリーで柵の掛かった起動が在ったかを見て、無ければ返答を受けず回数を待たずに
諦める（今の works の ci_role.take と同じ所。棚卸しの T49）。役の前後の作業ツリーの姿（ci-prep の ci-snapshot.json と今。accept.tree_moved。
HEAD・枝・git が無視するパスも見る。with: の status_guarded が真なら、Archon の状態の照らしと重なる git status の行は比べない）を比べ、
素材の欄の決まり（declared_checks.role_material_problems）を照らす。形は intake.json から読む。
拒まれた後の出し直しの役の返答 fix_reply（直す欄だけ）は、前の答えの控えと欄ごとに合わせてから照らす（rolekit.resubmitted に
rolekit.merge_fields）。通れば素材を place の ci-material.json に書く。拒めば理由を返し（拒否は rolekit.accept_round が控えに積む。控えが
読めない・書けない時も落ちずに done・give_up）、役が自分で置きうる ci-material.json を消し、rolekit.GIVE_UP_AFTER 回目の拒否で
done・give_up（輪を max_iterations で落とさない）。終わる時（通った・諦めた）に写しを消す"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import accept  # noqa: E402  （lib/）
import declared_checks  # noqa: E402
import rolekit  # noqa: E402
from engine import util  # noqa: E402  （lib/graphloops）

from src import files, inputs  # noqa: E402


def judge(place: Path, root: Path, snap: dict, got: tuple, mode: str, keys=accept.TREE_KEYS, records: str = "") -> dict:
    """got は (読めた返答, 読めない訳)（rolekit.resubmitted の返り）"""
    fence = ports.polyfill("fence")
    if records and (why := fence.fenced_since(Path(records), root, snap.get("prepared_at"))):
        return {"ok": False, "give_up": True,
                "reason": f"包みの柵が CI の任せ先の役の起動に掛かっていない: {why}——返答を受けず止める"}
    moved = accept.tree_moved({k: snap[k] for k in accept.TREE_KEYS}, root, keys=keys)
    if moved:
        return {"ok": False, "reason": f"読むだけの役が作業ツリーを変えた: CI の任せ先はテストを写し {snap.get('copy_dir')} の上で走らせ、"
                                       "対象の作業ツリー・HEAD・枝・git が無視するファイルを変えてはいけない（" + "・".join(moved) + "）"}
    reply, why = got
    if reply is None:
        return {"ok": False, "reason": why}
    problems = declared_checks.role_material_problems(reply.get("material"), mode=mode)
    if problems:
        return {"ok": False, "reason": "素材の欄 material が記録の決まりに合わない: " + "；".join(problems)}
    (place / files.MATERIAL).write_text(json.dumps({"material": reply["material"]}, ensure_ascii=False, indent=1) + "\n",
                                        encoding="utf-8")
    return {"ok": True, "reason": ""}


def main() -> int:
    fence = ports.polyfill("fence")
    place = ports.place()
    mode = files.intake(place)["mode"]
    root = Path(util.repo_root() or os.getcwd())
    snap = files.read(place, files.SNAPSHOT)
    keys = accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", ""))
    got = rolekit.resubmitted(place, declared_checks.CI_ROLE, inputs.value(os.environ.get("INPUTS_REPLY")),
                              inputs.value(os.environ.get("INPUTS_FIX_REPLY")), rolekit.merge_fields)
    judged = judge(place, root, snap, got, mode, keys, records=os.environ.get(fence.RECORDS_ENV, ""))
    out = rolekit.accept_round(place, declared_checks.CI_ROLE, None, lambda _: judged)   # give_up は judged の欄で渡す
    if not out["ok"]:
        (place / files.MATERIAL).unlink(missing_ok=True)
    if out["done"]:
        declared_checks.drop_copy(snap.get("top"))
    ports.returns(rolekit.round_outcome(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
