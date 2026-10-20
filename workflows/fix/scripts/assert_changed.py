# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node assert-changed（全体の形）: 戻せた組と裁定の後の返答の changes[].files が始めの木から本当に変わったか（申告が空なら、
直す義務が残らず外れた単位だけの run だけを通す）と、始めの木から今への変更が並行 PR に回した hunk に触れていないか。比べが通らない時は ok: false と理由（落ちない）。比べの外の誤り（groups.json が
無い・git が効かない）は assert-changed.json に訳を書いて落ちる。今のまま。返り {ok, reason}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


import oneline  # noqa: E402

from src import board  # noqa: E402

SKIP = (ports.RUNTIME_COPY_PREFIX,)


def replies(place: Path, plan: dict) -> list:
    """申告を読む返答の並び（戻せた組の reply_file と、裁定の後の返答）"""
    joined = board.read_json(place / board.JOIN_FILE, {}) or {}
    back = [g["group_id"] for g in joined.get("groups") or [] if g.get("returned")]
    out = []
    for gid in back:
        r = board.read_json(Path(plan["out_dir"]) / gid / board.RESULT_FILE, {}) or {}
        if r.get("reply_file"):
            out.append(board.read_json(r["reply_file"]))
    ruled = board.read_json(place / board.RULED_REPLY_FILE)
    return out + ([ruled] if ruled is not None else [])


def main(place: Path) -> dict:
    plan = board.read_json(place / board.GROUPS_FILE)
    if not isinstance(plan, dict) or not plan.get("start_tree"):
        raise ValueError(f"置き場に groups.json（start_tree）が無い（{place}）")
    declared = board.declared_files(replies(place, plan))
    touched = board.touched_since(Path.cwd(), plan["start_tree"], SKIP)
    owed = [k for g in plan["groups"] for k in g["unit_ids"]]
    excused = board.nothing_owed_but_excused(place, set(owed)) if not declared else {}
    ok, reason = board.changed_problem(declared, touched, excused)
    # 並行 PR に回した hunk は、始めの木から今への変更を 1 度照らす（TDD の役・合わせ役・裁定の後の修正役の変更も届く）
    held = board.check_excluded(place, Path.cwd(), plan["start_tree"])
    if held:
        return {"ok": False, "reason": "\n".join([reason, *held] if reason else held)}
    return {"ok": ok, "reason": reason}


if __name__ == "__main__":
    here = ports.place()
    try:
        result = main(here)
    except Exception as e:
        why = f"{type(e).__name__}: {oneline.one_line(e)}"
        board.write_json(here / board.ASSERT_FILE, {"ok": False, "reason": f"変更の確かめが回せない（{why}）"})
        print(f"assert-changed: {why}", file=sys.stderr)
        sys.exit(1)
    board.write_json(here / board.ASSERT_FILE, result)
    ports.returns(result)
