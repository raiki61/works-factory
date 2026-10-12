# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 join（形 ""）: 子が out_dir/<group_id>/result.json に書いた結果を組の順に読み、並べた run（par）は子の差分を決めた順に親の
作業ツリーへ当てて確かめ直す（p3.lane_merge）。

並べた run: 組ごとに子の終わりの木と始めの木の差分（groups.diff_since）を 3 方向で当て（unittrees.apply。lanekit.merge_in_order の順）、
当てた後に、前の組とも重なったファイルの名指しのテストの中身が子の終わりの木と同じかを照らし（fixboard.tests_moved）、前に戻せた
組とその組で赤 → 緑を確かめた名指しと、変えたファイルに当たる試験（名指しの無い組も。重なったファイルから地図が届く試験も足す）を
親の木で走らせ直し、test_cmd の関門が on なら test_cmd も 1 回走らせる（fixboard.rerun_problem・rerun_cmd。元
works/blk-fix/lib/tddlanes.py:688 _green_after。その前に Archon の変数を環境から落とす）。赤なら今の組だけを戻す（元は当てた枝を
全部戻して順に回した。持ち主の答え待ち）。戻せた組の子の
書き込みの記録は、親の作業ツリーの記録へ写す（writes.carry_children。親の手直しの受け付けが、子の書いた変更を記録の無い変更と見ない）。結果のファイルが
無い（子が落ちた）組は当てず、当たらない・確かめ直しが赤・確かめ直しが落ちた組は当てたパスを戻して、returned: false と理由。
並べない run は子が親の木で直したので当てない。結果のファイルが在れば returned: true、無い組は、その子が親の木に残した変更を
子の始めの木に戻して（fixboard.drop_unreturned。次の組の group-start が先に戻した組はその控え）returned: false と理由。
置き場に join.json = {par, groups: [{group_id, unit_ids, returned, reason}], units: [{unit_id, group_id, status, reason}]} を書き、
組の差分は join/<group_id>.diff に控える。戻せた組の子の TDD の輪の状態（結果の tdd_state）は親の置き場の tdd-<k>/ に、実行器を
親の作業ツリーで解き直して写す（fixboard.adopt_tdd_states。裁定の後の修正の受け付けが読む）。返り {groups: 組の数, returned: 戻せた組の数}。
置き場の groups.json が無い・読めない・git が効かない: 標準エラーに 1 行で 1。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))

import fixboard  # noqa: E402
import lanekit  # noqa: E402
import startrec  # noqa: E402
import writes  # noqa: E402
import writelog  # noqa: E402


def result_of(out_dir: Path, gid: str):
    """子の結果（無い・読めない・形が違えば None）"""
    try:
        doc = fixboard.read_json(out_dir / gid / fixboard.RESULT_FILE)
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) and isinstance(doc.get("end_tree"), str) else None


def main() -> dict:
    place = boundary.place("fix")
    plan = fixboard.read_json(place / fixboard.GROUPS_FILE)
    if not isinstance(plan, dict) or not isinstance(plan.get("groups"), list):
        raise ValueError(f"置き場に groups.json が無いか形が違う（{place}）")
    out_dir = Path(plan["out_dir"])
    results = {g["group_id"]: result_of(out_dir, g["group_id"]) for g in plan["groups"]}
    outcomes = {}
    if plan["par"]:
        repo = boundary.work_tree()
        log = writelog.log_here()
        start = startrec.read(place)
        cases = (fixboard.read_json(place / fixboard.BASELINE_FILE, {}) or {}).get("cases") or []
        with_result = [g for g in plan["groups"] if results[g["group_id"]] is not None]
        boundary.drop_runner_env()   # 確かめ直しのテストに Archon の変数を継がせない（置き場のパスは上で取った）
        verified = []   # 戻せた組が赤 → 緑を確かめた名指し（後の組の確かめ直しで一緒に走らせる）

        def merge_one(g, earlier):
            r = results[g["group_id"]]
            tdd_rows = [u for u in (r.get("tdd") or {}).get("units") or [] if isinstance(u, dict)]
            union = sorted({f for u in tdd_rows for f in u.get("test_files") or []} | set(r.get("allowed_test_changes") or []))
            named = [*verified, *(r.get("verified") or [])]

            def check(names):
                shared = set(names) & earlier
                return fixboard.tests_moved(repo, r["end_tree"], tdd_rows, shared) or fixboard.rerun_problem(
                    place, repo, start.get("tdd_suite", ""), cases, named, name=f"rerun-{g['group_id']}", shared=shared,
                    test_cmd=fixboard.rerun_cmd(place, r, start.get("test_cmd", "")))
            try:
                got = fixboard.join_group(
                    repo, r.get("start_tree") or plan["start_tree"], r["end_tree"], place / "join" / f"{g['group_id']}.diff",
                    union=union, check=check)
            except Exception as e:   # 子の木が引けない・git が落ちた組は戻さない（ほかの組は先へ）
                return lanekit.Merge(f"組の差分を当てられない（{type(e).__name__}: {' '.join(str(e).split())[:300]}）",
                                     "", [], [], False)
            if not got.why:
                verified.extend(t for t in r.get("verified") or [] if t not in verified)
            return got
        applied = []
        for g, got in lanekit.merge_in_order(with_result, merge_one):
            outcomes[g["group_id"]] = (results[g["group_id"]], not got.why, got.why)
            r = results[g["group_id"]]
            if not got.why and r.get("worktree") and log is not None:
                applied.append((r["worktree"], writelog.log_here(r["worktree"]), got.names))
        if log is not None and log.is_file():
            writes.carry_children(log, repo, applied)
    else:
        repo = boundary.work_tree()
        for g in plan["groups"]:
            r = results[g["group_id"]]
            if r is not None:
                outcomes[g["group_id"]] = (r, True, "")
                continue
            dropped = fixboard.drop_unreturned(repo, out_dir / g["group_id"], boundary.SKIP)
            outcomes[g["group_id"]] = (None, False, fixboard.NO_RESULT + (
                fixboard.DROPPED.format(paths="・".join(dropped)[:300]) if dropped else ""))
    for g in plan["groups"]:
        outcomes.setdefault(g["group_id"], (None, False, fixboard.NO_RESULT))
    fixboard.adopt_tdd_states(place, [outcomes[g["group_id"]][0] for g in plan["groups"] if outcomes[g["group_id"]][1]],
                              boundary.work_tree())
    rows, units = fixboard.join_rows(plan["groups"], outcomes)
    fixboard.write_json(place / fixboard.JOIN_FILE, {"par": bool(plan["par"]), "groups": rows, "units": units})
    return {"groups": len(rows), "returned": sum(1 for r in rows if r["returned"])}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:   # 回す側の誤り（置き場が無い・groups.json が読めない・git が効かない）
        print(f"join: {type(e).__name__}: {' '.join(str(e).split())}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(result)
