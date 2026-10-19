"""block r2 の place のファイルの名（docs/design/r2.md の 1.4）。名はこのモジュールだけが持つ。

- intake.json: port を読んだ値・累積差分の控え（本文を除く）・独立設計の読み・比べの道と検算の道のどちらを起こすか
- run.diff・run-diff-none.txt: 累積差分と、差分が空・取れない時の訳（lib/eyekit.take_diff が書く）
- r2-premises.json: 比べの役に貼った前提の控え {node, given, withheld, seen, after_design?}
- r2-compare-prompt-<n>.md・r2-compare-system-<n>.md・premise-check-prompt-<n>.md: 組んだ指示（prompt.emit が書く）
- r2-compare.json・premise-check.json: 役の返答（save が書く）
- premise-inputs.json: 2 つの役に渡した前提の控えと『渡されていない』の照らし（出口の notes の行の元）
- finish.json: 出口の出力の写し
"""
COMPARE = "r2-compare"        # 比べの役の AI の node の id（prompts/r2-compare.md）
PREMISE = "premise-check"     # 検算の役の AI の node の id（prompts/premise-check.md）
REPLIES = (COMPARE, PREMISE)  # save が書いてよい返答の名（node の id と同じ。<名>.json）
INTAKE = "intake.json"
DIFF = "run.diff"
DIFF_NONE = "run-diff-none.txt"
PREMISES = "r2-premises.json"
INPUTS = "premise-inputs.json"
FINISH = "finish.json"
# 入口が消す物: この block が名を持つファイルだけ（名で引く。広い形で消さない）
OWN_FILES = (INTAKE, DIFF, DIFF_NONE, PREMISES, INPUTS, FINISH, *(f"{name}.json" for name in REPLIES))
OWN_PROMPTS = tuple(f"{name}-{kind}-*.md" for name in REPLIES for kind in ("prompt", "system"))
