# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 conflict-check（形 ""）: 子が集めた食い違いの申し出の名指し（<パス>:<行>）を親の作業ツリーの現物で照らし（cite）、在る申し出を
置き場の conflicts.json（conflict の形 {items: [...]}）に積む（conflict.park）。

読むのは親の木へ戻せた組（join.json の returned）の結果の conflicts（戻せなかった組の申し出は、その組の単位が not_done なので
裁かない）。名指してよいのは親の作業ツリーと、親と、その組の子の置き場（結果の place。元 works で組の役が共有した盤面にあたる）
それぞれの受け付けの根（conflict.cite_roots）の下（ほかの組の置き場は許さない）。名指しが現物に無い申し出は積まず、
組の id と理由を置き場の conflicts-dropped.json に残す。
返り {go: 裁かれていない申し出が在るか, count: その数}。置き場の groups.json・join.json が無い・読めない: 標準エラーに 1 行で 1。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))

import conflict  # noqa: E402
import fixboard  # noqa: E402


def main() -> dict:
    place = boundary.place("fix")
    plan = fixboard.read_json(place / fixboard.GROUPS_FILE)
    joined = fixboard.read_json(place / fixboard.JOIN_FILE)
    if not isinstance(plan, dict) or not isinstance(joined, dict):
        raise ValueError(f"置き場に groups.json か join.json が無い（{place}）")
    out_dir = Path(plan["out_dir"])
    back = [g["group_id"] for g in joined.get("groups") or [] if g.get("returned")]
    repo = boundary.work_tree()
    ok, dropped = [], []
    for gid in back:
        doc = fixboard.read_json(out_dir / gid / fixboard.RESULT_FILE, {}) or {}
        rows = [r for r in doc.get("conflicts") or [] if isinstance(r, dict)]
        child = doc.get("place") if isinstance(doc.get("place"), str) else ""
        roots = conflict.cite_roots(place) + (conflict.cite_roots(child) if child else [])
        kept, lost = fixboard.cited_rows(rows, repo, roots)
        ok += kept
        dropped += [f"{gid}: {line}" for line in lost]
    for r in ok:
        source = r.get("source") if r.get("source") in conflict.SOURCES else conflict.FIX_SOURCE
        conflict.park(place, [r], source=source, ruling=r.get("ruling"))
    if dropped:
        fixboard.write_json(place / "conflicts-dropped.json", {"dropped": dropped})
    todo = conflict.unruled(place)
    return {"go": bool(todo), "count": len(todo)}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:
        print(f"conflict-check: {type(e).__name__}: {' '.join(str(e).split())}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(result)
