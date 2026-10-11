# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 ci-prep: 任せ先の CI の役を起こす前の支度。役を起こす前の作業ツリーの姿（accept.tree_state）を test-gate/<mode>/ci-snapshot.json に
置き（出し直しの回も最初の姿を残す。役が変えた後の姿で置き換えない）、テストを走らせる作業ツリーの写し（util.copy_worktree。
一時の置き場の直下）を作り（消えていれば作り直す）、前の回の拒否の理由 reject（1 回目は空）と一緒に返す"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))

import accept  # noqa: E402
import rolekit  # noqa: E402
from engine import util  # noqa: E402  （accept が lib/graphloops を sys.path に足す）

ROLE = "ci"
COPY_PREFIX = "works-factory-ci-"   # 写しの置き場（一時の置き場の直下）の頭。ci-accept はこの形の物だけ消す


def main() -> int:
    mode = os.environ["INPUTS_MODE"]
    start = json.loads(boundary.resolve(json.loads(os.environ["INPUTS_START"])).read_text(encoding="utf-8"))
    root = Path(util.repo_root() or os.getcwd())
    gate = Path(os.environ["ARTIFACTS_DIR"]) / "test-gate" / mode
    gate.mkdir(parents=True, exist_ok=True)
    snap_path = gate / "ci-snapshot.json"
    snap = json.loads(snap_path.read_text(encoding="utf-8")) if snap_path.is_file() else {}
    if not set(accept.TREE_KEYS) <= set(snap):
        snap = accept.tree_state(root)
    if not (snap.get("copy_dir") and Path(snap["copy_dir"]).is_dir()):
        top = Path(tempfile.mkdtemp(prefix=COPY_PREFIX))
        snap.update(top=str(top), copy_dir=util.copy_worktree(top / "work"), tmp_dir=str(top / "tmp"))
        (top / "tmp").mkdir()
    snap_path.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    boundary.returns({"copy_dir": snap["copy_dir"], "tmp_dir": snap["tmp_dir"], "root": str(root),
                      "base_rev": start.get("base_rev") or "", "mode": mode, "reject": os.environ["INPUTS_REJECT"],
                      "attempt": len(rolekit.rejected(gate, ROLE)) + 1})
    return 0


if __name__ == "__main__":
    sys.exit(main())
