"""差分の審査の支度（節 delta-cut）: 修正だけの差分（run の始めの木 → 今の作業ツリー）を切り、審査役の材料を置き場に書く（refix.cut）。

全部の単位が軽量の run（置き場の depth.json。fixboard.depth_skip。持ち主の決め dynamic-depth）と、変更の確かめ（置き場の
assert-changed.json）が ok でない run は、置き場の delta/skipped.json に {reason} を書いて go: false で審査を飛ばす。
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

ASSERT_FILE = "assert-changed.json"   # 変更の確かめの節が書く {ok, reason}


def skip_reason(place) -> str:
    got = fixio.read_json(place / ASSERT_FILE)
    if not isinstance(got, dict):
        return f"変更の確かめの控え {ASSERT_FILE} が無い（assert-changed が落ちたか走らなかった）"
    if got.get("ok") is not True:
        return f"変更の確かめが通らなかった（{got.get('reason') or '理由の記録が無い'}）"
    return fixboard.depth_skip(place)


def main() -> None:
    place = fixio.place()
    skipped = place / fixboard.DELTA_DIR / fixboard.DELTA_SKIPPED
    why = skip_reason(place)
    if why:
        fixio.write_json(skipped, {"reason": why})
        boundary.returns({"go": False, "files": [], "diff_file": "", "brief_file": ""})
        return
    skipped.unlink(missing_ok=True)
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
