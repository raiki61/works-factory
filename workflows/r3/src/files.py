"""block r3 の place のファイルの名（docs/design/r3.md の 1.4）。名はこのモジュールだけが持つ。

- intake.json: port を読んだ値・記録された方針の行 recorded・累積差分の控え（本文を除く）・依頼のファイルの中身が読めなかった訳 unread と {due, reason}
- run.diff・run-diff-none.txt: 累積差分と、差分が空・取れない時の訳（lib/eyekit.take_diff が書く）
- r3-coherence-prompt-<n>.md: 組んだ指示（prompt.emit が書く）
- r3-coherence.json: 役の返答（save が書く）
- finish.json: 出口の出力の写し
"""
import pathlib

COHERENCE = "r3-coherence"      # AI の node の id（prompts/r3-coherence.md）
REPLIES = (COHERENCE,)          # save が書いてよい返答の名（node の id と同じ。<名>.json）
INTAKE = "intake.json"
DIFF = "run.diff"
DIFF_NONE = "run-diff-none.txt"
FINISH = "finish.json"
# 入口が消す物: この block が名を持つファイルだけ（名で引く。広い形で消さない）
OWN_FILES = (INTAKE, DIFF, DIFF_NONE, FINISH, *(f"{name}.json" for name in REPLIES))
OWN_PROMPTS = tuple(f"{name}-{kind}-*.md" for name in REPLIES for kind in ("prompt", "system"))


def clear(place) -> None:
    """この block が名を持つファイルと前の回の指示を place から消す（入口と、lib を読めずに落ちた入口の fallback が呼ぶ。標準ライブラリだけ）"""
    place = pathlib.Path(place)
    for name in OWN_FILES:
        (place / name).unlink(missing_ok=True)
    for pattern in OWN_PROMPTS:
        for path in place.glob(pattern):
            path.unlink()
