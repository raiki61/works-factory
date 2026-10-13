# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 ci-prep: 任せ先の CI の役を起こす前の支度。役を起こす前の作業ツリーの姿（accept.tree_state）を test-gate/<mode>/ci-snapshot.json に
置き（出し直しの回も最初の姿を残す。役が変えた後の姿で置き換えない）、テストを走らせる作業ツリーの写し（util.copy_worktree。
一時の置き場の直下）を作り（消えていれば作り直す）、役を起こす前の時刻を同じ ci-snapshot.json の prepared_at に回ごとに書き
（ci-accept がこの後の包みの起動の記録を探す）、前の回の拒否の理由 reject（1 回目は空）と一緒に返す。
run が包みを通ると宣言した（env の fence.RECORDS_ENV）のに宣言が読めなければ、出し直さずに諦めた拒否を控えに積んで落ち、役を起こさない
（今の works の ci_role.take と同じ所。棚卸しの T49。返すノードが控えの拒否を証拠に出す）。
reject は ci-accept が積んだ拒否の控え（rolekit.rejected）の最後の 1 件から読む。$LOOP_PREV で with: に貼ると、Archon が貼った値の中の
$<節>.output.<欄> の字をもう 1 度置き換え、拒否の文が節の参照を含むと輪が落ちる（元の裁定 R44）"""
import datetime
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
import declared_checks  # noqa: E402
import fence  # noqa: E402
import rolekit  # noqa: E402
from engine import util  # noqa: E402  （accept が lib/graphloops を sys.path に足す）


def main() -> int:
    mode = os.environ["INPUTS_MODE"]
    start = json.loads(boundary.needed(os.environ["INPUTS_START"], "start").read_text(encoding="utf-8"))
    root = Path(util.repo_root() or os.getcwd())
    gate = Path(os.environ["ARTIFACTS_DIR"]) / "test-gate" / mode
    gate.mkdir(parents=True, exist_ok=True)
    if (records := os.environ.get(fence.RECORDS_ENV, "")) and (why := fence.bad_declaration(records)):
        reason = f"包みの宣言が読めない: {why}——CI の任せ先の役を起こさずに止める"
        rolekit.with_done(gate, declared_checks.CI_ROLE, {"ok": False, "reason": reason}, give_up=True)
        sys.exit(reason)
    snap_path = gate / "ci-snapshot.json"
    snap = json.loads(snap_path.read_text(encoding="utf-8")) if snap_path.is_file() else {}
    if not set(accept.TREE_KEYS) <= set(snap):
        snap = accept.tree_state(root)
    if not (snap.get("copy_dir") and Path(snap["copy_dir"]).is_dir()):
        top = Path(tempfile.mkdtemp(prefix=declared_checks.COPY_PREFIX))
        snap.update(top=str(top), copy_dir=util.copy_worktree(top / "work"), tmp_dir=str(top / "tmp"))
        (top / "tmp").mkdir()
    snap["prepared_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    snap_path.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    rejects = rolekit.rejected(gate, declared_checks.CI_ROLE)
    boundary.returns({"copy_dir": snap["copy_dir"], "tmp_dir": snap["tmp_dir"], "root": str(root),
                      "base_rev": start.get("base_rev") or "", "mode": mode, "reject": rejects[-1] if rejects else "",
                      "attempt": len(rejects) + 1})
    return 0


if __name__ == "__main__":
    sys.exit(main())
