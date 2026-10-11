"""節 assert-changed（形 ""）: 申告したファイルが run の始めから本当に変わったか（p1.worktree_after。ASF の assert-changed と同じ考え）。

申告 = 親の木へ戻せた組（join.json の returned）の子が受け付けた修正役の返答（result.json の reply_file）と、裁定の後の修正役の返答
（置き場の fix-ruled-reply.json。在れば）の changes[].files。変わった物 = 始めの木（groups.json の start_tree）から作業ツリーの今の姿
（未追跡を含む。無視される物と .archon/ の下は数えない）で変わったパス。直す義務の単位が残らず外れた単位だけの run は空の申告を
通す（fixboard.nothing_owed_but_excused）。突き合わせは fixboard.changed_problem。
通らない時も落ちずに ok: false と理由を返す。結果は置き場の assert-changed.json = {ok, reason} にも書く（delta-cut・collect が読む）。
置き場の groups.json が無い・返答の形が違う・git が効かない: assert-changed.json に ok: false と理由を書き、標準エラーに 1 行で 1。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import fixio  # noqa: E402

import fixboard  # noqa: E402

ASSERT_FILE = "assert-changed.json"
RULED_REPLY = "fix-ruled-reply.json"   # 裁定の後の修正役の受け付けた返答の写し（fix-ruled-accept が書く）


def replies(place: Path, plan: dict) -> list:
    """申告を読む返答の並び（戻せた組の reply_file と、裁定の後の返答）"""
    joined = fixio.read_json(place / "join.json", {}) or {}
    back = [g["group_id"] for g in joined.get("groups") or [] if g.get("returned")]
    out = []
    for gid in back:
        r = fixio.read_json(Path(plan["out_dir"]) / gid / "result.json", {}) or {}
        if r.get("reply_file"):
            out.append(fixio.read_json(r["reply_file"]))
    ruled = fixio.read_json(place / RULED_REPLY)
    return out + ([ruled] if ruled is not None else [])


def main(place: Path) -> dict:
    plan = fixio.read_json(place / "groups.json")
    if not isinstance(plan, dict) or not plan.get("start_tree"):
        raise ValueError(f"置き場に groups.json（start_tree）が無い（{place}）")
    declared = fixboard.declared_files(replies(place, plan))
    touched = fixboard.touched_since(fixio.repo(), plan["start_tree"], fixio.SKIP)
    owed = [k for g in plan["groups"] for k in g["unit_ids"]]
    excused = fixboard.nothing_owed_but_excused(place, set(owed)) if not declared else {}
    ok, reason = fixboard.changed_problem(declared, touched, excused)
    return {"ok": ok, "reason": reason}


if __name__ == "__main__":
    here = fixio.place()
    try:
        result = main(here)
    except Exception as e:
        why = f"{type(e).__name__}: {' '.join(str(e).split())}"
        fixio.write_json(here / ASSERT_FILE, {"ok": False, "reason": f"変更の確かめが回せない（{why}）"})
        print(f"assert-changed: {why}", file=sys.stderr)
        sys.exit(1)
    fixio.write_json(here / ASSERT_FILE, result)
    boundary.returns(result)
