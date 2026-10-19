# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node ci-prep: 任せ先の CI の役を起こす前の支度。役を起こす前の作業ツリーの姿（accept.tree_state）を place の ci-snapshot.json に置き
（出し直しの回も最初の姿を残す。役が変えた後の姿で置き換えない）、テストを走らせる作業ツリーの写し（util.copy_worktree。一時の置き場の
直下）を作り（消えていれば作り直す）、役を起こす前の時刻を同じ ci-snapshot.json の prepared_at に回ごとに書き（ci-accept がこの後の包みの
起動の記録を探す）、役の指示を組んで返す。
run が包みを通ると宣言した（env の fence.RECORDS_ENV）のに宣言が読めなければ、出し直さずに諦めた拒否を控えに積んで落ち、役を起こさない
（今の works の ci_role.take と同じ所。棚卸しの T49。返す node が控えの拒否を証拠に出す）。
前の回の拒否の文は with: に貼らず、控えの拒否の全部から読む（$LOOP_PREV で貼ると、Archon が貼った値の中の $<node>.output.<欄> の字を
もう 1 度置き換え、拒否の文が node の参照を含むと輪が落ちる。元の裁定 R44）。with: の prev は前の周の受け付けの ok だけ。
前の周が拒まれ（prev が false）、受け付けが合わせた答えの控えが在れば、resubmit: true を返し（出し直しの役の指示は ci-fix-prep が組む。
1 回目の役の指示 prompt は空）、そうでなければ 1 回目の役の指示を組む。返りは {prompt, resubmit, attempt}"""
import datetime
import json
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import accept  # noqa: E402  （lib/）
import declared_checks  # noqa: E402
import rolekit  # noqa: E402
from engine import util  # noqa: E402  （lib/graphloops）

from src import files, inputs, prompts  # noqa: E402


def main() -> int:
    fence = ports.polyfill("fence")
    place = ports.place()
    doc = files.intake(place)
    root = Path(util.repo_root() or os.getcwd())
    if (records := os.environ.get(fence.RECORDS_ENV, "")) and (why := fence.bad_declaration(records)):
        reason = f"包みの宣言が読めない: {why}——CI の任せ先の役を起こさずに止める"
        rolekit.accept_round(place, declared_checks.CI_ROLE, None, lambda _: {"ok": False, "give_up": True, "reason": reason})
        sys.exit(reason)
    snap_path = place / files.SNAPSHOT
    snap = json.loads(snap_path.read_text(encoding="utf-8")) if snap_path.is_file() else {}
    if not set(accept.TREE_KEYS) <= set(snap):
        snap = accept.tree_state(root)
    if not (snap.get("copy_dir") and Path(snap["copy_dir"]).is_dir()):
        top = Path(tempfile.mkdtemp(prefix=declared_checks.COPY_PREFIX))
        snap.update(top=str(top), copy_dir=util.copy_worktree(top / "work"), tmp_dir=str(top / "tmp"))
        (top / "tmp").mkdir()
    snap["prepared_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    snap_path.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    resubmit = rolekit.resubmitting(place, declared_checks.CI_ROLE, inputs.value(os.environ.get("INPUTS_PREV")))
    prompt = "" if resubmit else prompts.ci(place, doc, snap, root)["prompt"]
    ports.returns({"prompt": prompt, "resubmit": resubmit, "attempt": rolekit.attempt(place, declared_checks.CI_ROLE)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
