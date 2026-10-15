# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""レンズの集め（節 lens-collect）: レンズの返り（with: reply。中継の節 lens-reply の返りで、起こさなかった・レンズが落ちた時は
null）で置き場の lens.json の行を埋め（lenses.collect。返りが無ければ failed と理由、形が違えば failed と理由、在れば ran と
出どころつきの findings）、1 回目の審査役の材料の lens の欄に足す（fixboard.brief_lens）。この節は支度（lens-prep）が済めば
レンズが落ちても走り、支度が落ちた run では飛ぶ。
集め役の事実は diff の隣の lenses.json に {collector: {ok, reason}} で置く（fixboard.lens_collector）: 集め終えれば ok: true、
集めが ok でない・この節が誤りで落ちる時は ok: false と理由を書いてから非 0 で落ち、run を止める（元 works/blk-lens/scripts/exit.py
の lenses.exit_ も盤面を止めた）。止まった run の報告は lenses.json の理由を読む。この節が何も書けずに落ちた時は返す節 collect が
ok: false を書く。
返り {state（レンズの行の state）, count（集めた指摘の数）}。回す側の誤り（審査役の材料が無い）は標準エラーに 1 行で非 0。
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import fixboard  # noqa: E402
import lens  # noqa: E402
import lenses  # noqa: E402
import oneline  # noqa: E402

(LENS,) = (row["lens"] for row in lenses.LENSES)   # 工程のレンズの節は 1 つ（節 lens）


def main() -> None:
    place = boundary.place("fix")
    got = lenses.collect(place, {LENS: boundary.value(os.environ["INPUTS_REPLY"])})
    if not got["ok"]:
        raise ValueError(got["reason"])
    fixboard.brief_lens(place)
    fixboard.lens_collector(place, True)
    row = next((r for r in lens.read(place) or [] if r["lens"] == LENS), {})
    boundary.returns({"state": str(row.get("state") or "failed"), "count": len(row.get("findings") or [])})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        why = f"{type(e).__name__}: {oneline.one_line(e)}"
        try:
            fixboard.lens_collector(boundary.place("fix"), False, fixboard.LENS_NOT_DONE.format(why=why))
        except Exception as w:
            why += f"（集め役の事実 {fixboard.LENSES_FILE} を書けない: {type(w).__name__}: {oneline.one_line(w)}）"
        sys.exit(f"lens-collect: {why}")
