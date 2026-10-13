# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 ci-accept: 任せ先の CI の役の返答を受け付ける。run が包みを通ると宣言した（env の fence.RECORDS_ENV）なら、先に包みの起動の記録で
ci-prep の時刻（ci-snapshot.json の prepared_at）より後にこの作業ツリーで柵の掛かった起動が在ったかを見て、無ければ返答を受けず回数を待たずに
諦める（今の works の ci_role.take と同じ所。棚卸しの T49）。役の前後の作業ツリーの姿（ci-prep の ci-snapshot.json と今。accept.tree_moved。
HEAD・枝・git が無視するパスも見る。with: の status_guarded が真なら、Archon の状態の照らしと重なる git status の行は比べない）を比べ、素材の欄の決まり（declared_checks.material_problems）を照らす。通れば素材を
test-gate/<mode>/ci-material.json に書く。拒めば理由を返し（拒否は rolekit の控えに積む）、役が自分で置きうる ci-material.json を消し、
rolekit.GIVE_UP_AFTER 回目の拒否で done・give_up（輪を max_iterations で落とさない）。終わる時（通った・諦めた）に写しを消す"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))

import accept  # noqa: E402
import declared_checks  # noqa: E402
import fence  # noqa: E402
import rolekit  # noqa: E402
from engine import util  # noqa: E402  （accept が lib/graphloops を sys.path に足す）


def judge(gate: Path, root: Path, snap: dict, raw: str, mode: str, keys=accept.TREE_KEYS, records: str = "") -> dict:
    if records and (why := fence.fenced_since(Path(records), root, snap.get("prepared_at"))):
        return {"ok": False, "give_up": True,
                "reason": f"包みの柵が CI の任せ先の役の起動に掛かっていない: {why}——返答を受けず止める"}
    moved = accept.tree_moved({k: snap[k] for k in accept.TREE_KEYS}, root, keys=keys)
    if moved:
        return {"ok": False, "reason": f"読むだけの役が作業ツリーを変えた: CI の任せ先はテストを写し {snap.get('copy_dir')} の上で走らせ、"
                                       "対象の作業ツリー・HEAD・枝・git が無視するファイルを変えてはいけない（変えた物を元に戻し、"
                                       "写しの上で走らせ直せ）（" + "・".join(moved) + "）"}
    reply, why = rolekit.parse_reply(raw)
    if reply is None:
        return {"ok": False, "reason": why}
    problems = declared_checks.material_problems(reply.get("material"), mode=mode)
    if problems:
        return {"ok": False, "reason": "素材の欄を直した返答を丸ごと出し直せ: " + "；".join(problems)}
    (gate / "ci-material.json").write_text(json.dumps({"material": reply["material"]}, ensure_ascii=False, indent=1) + "\n",
                                           encoding="utf-8")
    return {"ok": True, "reason": ""}


def main() -> int:
    mode = os.environ["INPUTS_MODE"]
    root = Path(util.repo_root() or os.getcwd())
    gate = Path(os.environ["ARTIFACTS_DIR"]) / "test-gate" / mode
    snap = json.loads((gate / "ci-snapshot.json").read_text(encoding="utf-8"))
    keys = accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", ""))
    judged = judge(gate, root, snap, os.environ["INPUTS_REPLY"], mode, keys, records=os.environ.get(fence.RECORDS_ENV, ""))
    give_up = judged.pop("give_up", False)
    out = rolekit.with_done(gate, declared_checks.CI_ROLE, judged, give_up=give_up)
    if not out["ok"]:
        (gate / "ci-material.json").unlink(missing_ok=True)
    if out["done"]:
        declared_checks.drop_copy(snap.get("top"))
    boundary.returns({"ok": out["ok"], "done": out["done"], "give_up": out["done"] and not out["ok"], "reason": out["reason"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
