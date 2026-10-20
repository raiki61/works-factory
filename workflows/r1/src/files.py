"""block r1 の place のファイルの名（docs/design/r1.md の 1.4）。名はこのモジュールだけが持つ。

- intake.json: port を読んだ値・累積差分の控え（本文を除く）・規模の数値と {due, reason}
- run.diff・run-diff-none.txt: 累積差分と、差分が空・取れない時の訳（lib/eyekit.take_diff が書く）
- r1-comments-prompt-<n>.md・r1-minimality-prompt-<n>.md: 組んだ指示（prompt.emit が書く）
- r1-comments.json・r1-minimality.json: 役の返答（save が書く。2 段目の役が前段の返答を Read する）
- finish.json: 出口の出力の写し
"""
COMMENTS = "r1-comments"        # 1 段目の AI の node の id（prompts/r1-comments.md）
MINIMALITY = "r1-minimality"    # 2 段目の AI の node の id（prompts/r1-minimality.md）
REPLIES = (COMMENTS, MINIMALITY)   # save が書いてよい返答の名（node の id と同じ。<名>.json）
INTAKE = "intake.json"
DIFF = "run.diff"
DIFF_NONE = "run-diff-none.txt"
FINISH = "finish.json"
# 入口が消す物: この block が名を持つファイルだけ（名で引く。広い形で消さない）
OWN_FILES = (INTAKE, DIFF, DIFF_NONE, FINISH, *(f"{name}.json" for name in REPLIES))
OWN_PROMPTS = tuple(f"{name}-{kind}-*.md" for name in REPLIES for kind in ("prompt", "system"))
