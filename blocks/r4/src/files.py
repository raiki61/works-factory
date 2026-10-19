"""block r4 の place のファイルの名（docs/design/r4.md の 1.4）。名はこのモジュールだけが持つ。

- intake.json: port を読んだ値・累積差分の控え（本文を除く）・記録された方針の行・まとめた形か・{due, reason}
- run.diff・run-diff-none.txt: 累積差分と、差分が空・取れない時の訳（lib/eyekit.take_diff が書く）
- r4-scope-prompt-<n>.md・r4-scope-fix-prompt-<n>.md: 組んだ指示（prompt.emit が書く）
- r4-scope.json: 受け付けが回ごとに書く、読めた最後の返答（出し直しは前の答えと合わせた物）
- rejects-r4-scope.json・candidate-r4-scope.json: 受け付けの拒否の控えと、合わせた答えの控え（lib/rolekit が名を組む）
- finish.json: 出口の出力の写し
"""
import pathlib

R4_NODE = "r4-scope"             # 範囲の役の AI の node の id（prompts/r4-scope.md）。受け付けの控えの名もこれ
FIX_NODE = "r4-scope-fix"        # 出し直しの役の AI の node の id（prompts/r4-scope-fix.md）
INTAKE = "intake.json"
DIFF = "run.diff"
DIFF_NONE = "run-diff-none.txt"
REPLY = f"{R4_NODE}.json"
FINISH = "finish.json"
# 入口が消す物: この block が名を持つファイルだけ（名で引く。広い形で消さない）
OWN_FILES = (INTAKE, DIFF, DIFF_NONE, REPLY, FINISH)
OWN_PROMPTS = (f"{R4_NODE}-prompt-*.md", f"{FIX_NODE}-prompt-*.md")


def rejects(place) -> pathlib.Path:
    import rolekit
    return rolekit.rejects_path(pathlib.Path(place), R4_NODE)


def candidate(place) -> pathlib.Path:
    import rolekit
    return rolekit.candidate_path(pathlib.Path(place), R4_NODE)


def own_files(place) -> list:
    """place の中のこの block のファイル（拒否の控えと合わせた答えの控えを含む。組んだ指示は含めない）"""
    place = pathlib.Path(place)
    return [place / name for name in OWN_FILES] + [rejects(place), candidate(place)]
