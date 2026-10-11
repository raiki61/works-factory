# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 ci-accept: 任せ先の CI の役の返答を受け付ける。役の前後の作業ツリーの姿（ci-prep の ci-snapshot.json と今。accept.tree_moved。
HEAD・枝・git が無視するパスも見る）を比べ、素材の欄の決まり（declared_checks.material_problems）を照らす。通れば素材を
test-gate/<mode>/ci-material.json に書く。拒めば理由を返し（拒否は rolekit の控えに積む）、GIVE_UP_AFTER 回目の拒否で done・give_up
（輪を max_iterations で落とさない）。終わる時（通った・諦めた）に写しを消す"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))

import accept  # noqa: E402
import declared_checks  # noqa: E402
import rolekit  # noqa: E402
from engine import util  # noqa: E402  （accept が lib/graphloops を sys.path に足す）

ROLE = "ci"
GIVE_UP_AFTER = rolekit.GIVE_UP_AFTER   # YAML の ci-loop の max_iterations と同じ数
COPY_PREFIX = "works-factory-ci-"


def drop_copy(top) -> None:
    """写しの置き場を消す（一時の置き場の直下の COPY_PREFIX で始まるフォルダだけ。symlink は辿らない）"""
    if not top or os.path.islink(top):
        return
    real = os.path.realpath(top)
    if os.path.dirname(real) == os.path.realpath(tempfile.gettempdir()) and os.path.basename(real).startswith(COPY_PREFIX):
        shutil.rmtree(real, ignore_errors=True)


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
    out = rolekit.with_done(gate, ROLE, judge(gate, root, snap, os.environ["INPUTS_REPLY"], mode), give_up_after=GIVE_UP_AFTER)
    if out["done"]:
        drop_copy(snap.get("top"))
    boundary.returns({"ok": out["ok"], "done": out["done"], "give_up": out["done"] and not out["ok"], "reason": out["reason"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
