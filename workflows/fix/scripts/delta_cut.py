"""差分の審査の支度（節 delta-cut）: 修正だけの差分（run の始めの木 → 今の作業ツリー）を切り、審査役の材料を置き場に書く（refix.cut）。

変更の確かめ（置き場の assert-changed.json）が ok でない run は go: false で審査を回さない（審査は走らなかったので collect は
{rounds: 0, pass: false} を返す）。全部の単位が軽量の run（置き場の depth.json。fixboard.depth_skip。持ち主の決め dynamic-depth）は、
置き場の delta/skipped.json に {reason} を書いて go: false で審査を飛ばす。
返り {go, files, diff_file, brief_file}。回す側の誤り（差分の起点が無い・差分を切れない・修正案の欄の控えが壊れた）は標準エラーに
1 行で非 0。
"""
import functools
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import fixio  # noqa: E402
import fixboard  # noqa: E402
import refix  # noqa: E402
import startrec  # noqa: E402

NO_GO = {"go": False, "files": [], "diff_file": "", "brief_file": ""}


def main() -> None:
    place = fixio.place()
    skipped = place / fixboard.DELTA_DIR / fixboard.DELTA_SKIPPED
    skipped.unlink(missing_ok=True)
    checked = fixboard.read_json(place / fixboard.ASSERT_FILE)
    if not isinstance(checked, dict) or checked.get("ok") is not True:
        boundary.returns(NO_GO)
        return
    light = fixboard.depth_skip(place)
    if light:
        fixboard.write_json(skipped, {"reason": light})
        boundary.returns(NO_GO)
        return
    repo = fixio.repo()
    start = startrec.read(place)
    got = refix.cut(place, 1, repo, fixboard.start_tree(place), plan_review=None,
                    fix_reply=fixboard.group_fix_reply(place), items=functools.partial(fixboard.place_items, place),
                    policy=fixboard.policy_brief(start.get("policy_md") or ""))
    if not got.get("ok"):
        raise ValueError(got.get("reason") or "差分を切れない")
    boundary.returns({"go": True, "files": got["files"], "diff_file": got["diff_file"], "brief_file": got["brief_file"]})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"delta-cut: {type(e).__name__}: {' '.join(str(e).split())}")
