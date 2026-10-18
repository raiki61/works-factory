# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""差分の審査の支度（節 delta-cut）: 修正だけの差分（run の始めの木 → 今の作業ツリー）を切り、審査役の材料を置き場に書く（refix.cut）。

戻せず親の作業ツリーに当たったままの組が在る run（fixboard.held）と、変更の確かめ（置き場の assert-changed.json）が ok でない run は go: false で審査を回さない（審査は走らなかったので collect は
{rounds: 0, pass: false} を返す）。先に修正の後の信号（申し出・止めた単位・答えていない問い・案の直し・修正役の異議・引用の外の
差分・TDD の拒否・範囲の相談・残した block）で深さを標準へ上げ（fixboard.redepth。元の線の h-redepth。上げた控えは置き場の depth-raised.json）、run の頭の深さが軽量で、
それでも全部の単位が軽量の run（持ち主の決め dynamic-depth）は、置き場の delta/skipped.json に {reason} を書いて go: false で審査を飛ばす。
作業ツリーが修正前の版と同じ（.archon/ の下は数えない）で、修正が塞いだと言う事前審査の穴も無い run も、同じ印に訳を書いて
go: false で審査役を起こさない（fixboard.delta_review_due。元 review-loop.py:604 fix_delta_nonempty・:617 delta_review_due）。
go: false の時は、レンズも起こさないので diff の隣の lenses.json に集め役の事実 {collector: {ok: true, reason}} を置く
（前の試みの lenses.json は頭で消す。fixboard.lens_collector）。返り {go, files, diff_file, brief_file}。回す側の誤り（差分の起点が無い・差分を切れない・修正案の欄の控えが壊れた）は標準エラーに
1 行で非 0。
"""
import functools
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import fixboard  # noqa: E402
import oneline  # noqa: E402
import refix  # noqa: E402
import startrec  # noqa: E402

NO_GO = {"go": False, "files": [], "diff_file": "", "brief_file": ""}
NOT_CHECKED = "変更の確かめが通らない"


def no_go(place, why: str) -> None:
    """審査を回さない: レンズも起こさないので、レンズの集め役の事実を ok: true と訳で置いて go: false を返す"""
    fixboard.lens_collector(place, True, fixboard.LENS_NOT_DUE.format(why=why))
    boundary.returns(NO_GO)


def main() -> None:
    place = boundary.place("fix")
    skipped = place / fixboard.DELTA_DIR / fixboard.DELTA_SKIPPED
    skipped.unlink(missing_ok=True)
    (place / fixboard.LENSES_FILE).unlink(missing_ok=True)   # 前の試みの集め役の事実を返す節に読ませない
    if held := fixboard.held(place):
        no_go(place, held)
        return
    checked = fixboard.read_json(place / fixboard.ASSERT_FILE)
    if not isinstance(checked, dict) or checked.get("ok") is not True:
        no_go(place, str((checked.get("reason") if isinstance(checked, dict) else "") or NOT_CHECKED))
        return
    repo = boundary.work_tree()
    light = fixboard.redepth(place, repo, boundary.SKIP)
    if light:
        fixboard.write_json(skipped, {"reason": light})
        no_go(place, light)
        return
    fix_reply = fixboard.group_fix_reply(place)
    due, why = fixboard.delta_review_due(place, repo, boundary.SKIP, fix_reply)
    if not due:
        fixboard.write_json(skipped, {"reason": why})
        no_go(place, why)
        return
    start = startrec.read(place)
    got = refix.cut(place, 1, repo, fixboard.start_tree(place), plan_review=fixboard.plan_review_file(place),
                    fix_reply=fix_reply, items=functools.partial(fixboard.place_items, place),
                    policy=fixboard.policy_brief(start), skip=boundary.SKIP)
    if not got.get("ok"):
        raise ValueError(got.get("reason") or "差分を切れない")
    boundary.returns({"go": True, "files": got["files"], "diff_file": got["diff_file"], "brief_file": got["brief_file"]})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"delta-cut: {type(e).__name__}: {oneline.one_line(e)}")
