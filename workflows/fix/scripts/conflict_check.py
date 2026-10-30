# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node conflict-check（全体の形）: 子と join が集めた食い違いの申し出の名指し（<パス>:<行>）を親の作業ツリーと許した根（依頼の
ファイルと親と子の place）で現物と照らし、在る申し出を place の conflicts.json に積み、行が無くなった申し出は conflicts-dropped.json に
名指す。今のまま。返り {go, count}"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


import conflict  # noqa: E402
import oneline  # noqa: E402

from src import board, files, runvals  # noqa: E402


def main() -> dict:
    place = ports.place()
    plan = board.read_json(place / board.GROUPS_FILE)
    joined = board.read_json(place / board.JOIN_FILE)
    if not isinstance(plan, dict) or not isinstance(joined, dict):
        raise ValueError(f"置き場に groups.json か join.json が無い（{place}）")
    out_dir = Path(plan["out_dir"])
    back = [g["group_id"] for g in joined.get("groups") or [] if g.get("returned")]
    repo = Path.cwd()
    ok, dropped = [], []
    for gid in back:
        doc = board.read_json(out_dir / gid / board.RESULT_FILE, {}) or {}
        rows = [r for r in doc.get("conflicts") or [] if isinstance(r, dict)]
        child = doc.get("place") if isinstance(doc.get("place"), str) else ""
        roots = conflict.cite_roots(runvals.read(place)["request_file"], place) + (
            conflict.cite_roots(runvals.read(child)["request_file"], child) if child else [])
        kept, lost = board.cited_rows(rows, repo, roots)
        ok += kept
        dropped += [f"{gid}: {line}" for line in lost]
    for r in ok:
        source = r.get("source") if r.get("source") in conflict.SOURCES else conflict.FIX_SOURCE
        conflict.park(place, [r], source=source, ruling=r.get("ruling"))
    if dropped:
        board.write_json(place / files.CONFLICTS_DROPPED, {"dropped": dropped})
    todo = conflict.unruled(place)
    return {"go": bool(todo) and not board.held(place), "count": len(todo)}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:
        print(f"conflict-check: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(result)
