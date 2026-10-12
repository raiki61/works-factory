# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""2 回目の差分の審査の支度（節 cut2）: 1 回目の手直しを受けて、fixed と答えた穴が在る時だけ、手直しだけの差分（1 回目の差分で
固めた修正後の姿 → 今の作業ツリー）を切り、審査役の材料を置き場に書く（refix.cut の 2 回目）。1 回目の手直しを受けていない・
fixed が無い時は go: false（2 回目の審査は回さない）。返り {go, files, diff_file, brief_file}。回す側の誤り（1 回目の差分が無い・
差分を切れない）は標準エラーに 1 行で非 0。
"""
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

N = 2


def main() -> None:
    place = fixio.place()
    handled = (fixboard.output(place, refix.passes()[N - 1]["fix"]) or {}).get("handled") or []
    if not any(isinstance(r, dict) and r.get("handled") == "fixed" for r in handled):
        boundary.returns({"go": False, "files": [], "diff_file": "", "brief_file": ""})
        return
    start = startrec.read(place)
    got = refix.cut(place, N, fixio.repo(), policy=fixboard.policy_brief(start))
    if not got.get("ok"):
        raise ValueError(got.get("reason") or "差分を切れない")
    boundary.returns({"go": True, "files": got["files"], "diff_file": got["diff_file"], "brief_file": got["brief_file"]})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"cut2: {type(e).__name__}: {' '.join(str(e).split())}")
