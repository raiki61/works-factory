# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""レンズの支度（節 lens-prep）: 利用者が入れた silent-failure-hunter の役の定義の本文（rolekit.agent_def）から、修正の差分を
見るレンズの指示書を組んで置き場に書く（lenses.render。中身は fixboard.lens_route）。振り分けの行は置き場の lens.json に残す。
変わったファイルが無い・役の定義が引けない時は go: false（理由は lens.json の行の reason）。返り {go, prompt_file}。
置き場に修正の差分が無い（差分の審査の支度が走っていない）のは標準エラーに 1 行で非 0。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import fixio  # noqa: E402
import fixboard  # noqa: E402
import startrec  # noqa: E402

LENS = "silent-failure-hunter"   # 工程の節 lens が受けるレンズ（lenses.LENSES の名）


def main() -> None:
    place = fixio.place()
    got = fixboard.lens_route(place, fixboard.lang_line(startrec.read(place)))[LENS]
    boundary.returns({"go": bool(got["go"]), "prompt_file": got["prompt_file"]})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"lens-prep: {type(e).__name__}: {' '.join(str(e).split())}")
