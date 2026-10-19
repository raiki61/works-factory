# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node join（全体の形）: 子が out_dir/<group_id>/result.json に書いた結果を組の順に読み、並べた run は子の差分を決めた順に親の
作業ツリーへ当てて確かめ直す（board.join_group・lanes.merge_in_order）。確かめ直しの赤で戻した組と字で当たらなかった組は合わせの
控えに積む（clash.record）。当たったままの組が在れば後の組を当てない。戻せた組の子から書き込みの記録・TDD の輪の状態・範囲の相談の
合意を親の place へ写す（board.adopt_returned）。走らせ直しの test_cmd は board.rerun_cmd が port skip_rerun で決める。今のまま。
返り {groups, returned}。結果の無い組・git が効かない: 標準エラーに 1 行で 1"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import oneline  # noqa: E402
import unittrees  # noqa: E402
import writelog  # noqa: E402

from src import board, clash, lanes, runvals  # noqa: E402


def main() -> dict:
    place = ports.place()
    plan = board.read_json(place / board.GROUPS_FILE)
    if not isinstance(plan, dict) or not isinstance(plan.get("groups"), list):
        raise ValueError(f"置き場に groups.json が無いか形が違う（{place}）")
    out_dir = Path(plan["out_dir"])
    results = {g["group_id"]: board.usable_result(out_dir / g["group_id"]) for g in plan["groups"]}
    missing = [gid for gid, r in results.items() if r is None]
    if missing:
        raise ValueError(f"組の子の結果のファイルが無いか読めない（{'・'.join(missing)}）")
    outcomes, backed_out, unrestored = {}, {}, {}
    applied, log = [], None   # 戻せた組の子の書き込みの記録の (子の作業ツリー, 子の記録, 当てたパス) と、親の作業ツリーの記録
    if plan["par"]:
        repo = Path.cwd()
        log = writelog.log_here()
        start = runvals.read(place)
        cases = (board.read_json(place / board.BASELINE_FILE, {}) or {}).get("cases") or []
        ports.drop_runner_env(start["user_env_dir"])   # 確かめ直しのテストに Archon の変数を継がせない（置き場のパスは上で取った）
        verified = []   # 戻せた組が赤 → 緑を確かめた名指し（後の組の確かめ直しで一緒に走らせる）
        red, clashes = {}, []   # 組ごとの確かめ直しの赤の文と、赤で戻した組・字で当たらない組（合わせのループが直す。clash.record）

        def merge_one(g, earlier):
            if unrestored:   # 戻せず当たったままの組が在れば後の組は当てない
                return lanes.Merge(board.AFTER_UNRESTORED.format(group=next(iter(unrestored))), "", [], [], False)
            r = results[g["group_id"]]
            tdd_rows = board.child_tdd_units(r)
            union = sorted({f for u in tdd_rows for f in board.unit_test_files(u)} | {t["path"] for t in board.child_allowed_rows(r)})
            named = [*verified, *board.child_verified(r)]

            def check(names):
                shared = set(names) & earlier
                red[g["group_id"]] = board.tests_moved(repo, r["end_tree"], tdd_rows, shared) or board.rerun_problem(
                    place, repo, start["tdd_suite"], cases, named, name=f"rerun-{g['group_id']}", shared=shared,
                    test_cmd=board.rerun_cmd(place, r, start["test_cmd"]))
                return red[g["group_id"]]
            try:
                got = board.join_group(
                    repo, r.get("start_tree") or plan["start_tree"], r["end_tree"], place / "join" / f"{g['group_id']}.diff",
                    union=union, check=check)
            except Exception as e:   # 子の木が引けない・git が落ちた組は戻さない（ほかの組は先へ）
                return lanes.Merge(f"組の差分を当てられない（{type(e).__name__}: {oneline.one_line(e)[:300]}）",
                                     "", [], [], False)
            if not got.why:
                verified.extend(t for t in board.child_verified(r) if t not in verified)
            if got.unrestored:
                unrestored[g["group_id"]] = got.unrestored
            elif got.backed_out and got.why == red.get(g["group_id"]):
                clashes.append(clash.new_row(g["group_id"], g["unit_ids"], got.patch, got.backed_out, earlier, got.why, clash.RED))
            elif got.clash:
                names = unittrees.patch_names(Path(got.patch).read_text(encoding="utf-8", errors="surrogateescape"))
                clashes.append(clash.new_row(g["group_id"], g["unit_ids"], got.patch, names, earlier, got.why, clash.TEXT))
            return got
        for g, got in lanes.merge_in_order(plan["groups"], merge_one):
            outcomes[g["group_id"]] = (results[g["group_id"]], not got.why, got.why)
            if got.backed_out:
                backed_out[g["group_id"]] = got.backed_out
            r = results[g["group_id"]]
            if not got.why and r.get("worktree") and log is not None:
                applied.append((r["worktree"], writelog.log_here(r["worktree"]), got.names))
    else:
        outcomes = {gid: (r, True, "") for gid, r in results.items()}
    if plan["par"]:
        clash.record(place, clashes)
    rows, units = board.join_rows(plan["groups"], outcomes, backed_out, unrestored)
    joined = {"par": bool(plan["par"]), "groups": rows, "units": units}
    if unrestored:   # 後の写しが落ちても、当たったままの組を後の節（board.held）が読めるように先に書く
        board.write_json(place / board.JOIN_FILE, joined)
    board.adopt_returned(place, Path.cwd(), [outcomes[g["group_id"]][0] for g in plan["groups"] if outcomes[g["group_id"]][1]],
                            log=log, applied=applied)
    board.write_json(place / board.JOIN_FILE, joined)
    return {"groups": len(rows), "returned": sum(1 for r in rows if r["returned"])}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:   # 回す側の誤り（置き場が無い・groups.json が読めない・git が効かない）か、結果の無い組
        print(f"join: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(result)
