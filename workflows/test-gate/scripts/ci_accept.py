# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 ci-accept: 任せ先の CI の役の返答を受け付ける。役の前後の作業ツリーの姿（ci-prep の ci-snapshot.json と今。accept.tree_moved。
HEAD・枝・git が無視するパスも見る）を比べ、素材の欄の決まり（declared_checks.material_problems）を照らす。通れば素材を
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
import rolekit  # noqa: E402
from engine import util  # noqa: E402  （accept が lib/graphloops を sys.path に足す）


def judge(gate: Path, root: Path, snap: dict, raw: str, mode: str) -> dict:
    moved = accept.tree_moved({k: snap[k] for k in accept.TREE_KEYS}, root)
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
    out = rolekit.with_done(gate, declared_checks.CI_ROLE, judge(gate, root, snap, os.environ["INPUTS_REPLY"], mode))
    if not out["ok"]:
        (gate / "ci-material.json").unlink(missing_ok=True)
    if out["done"]:
        declared_checks.drop_copy(snap.get("top"))
    boundary.returns({"ok": out["ok"], "done": out["done"], "give_up": out["done"] and not out["ok"], "reason": out["reason"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
