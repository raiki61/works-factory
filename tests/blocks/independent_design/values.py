"""独立設計の block の試験と筋書きが共に使う値（本物の run の値を縮めた物。docs/design/independent-design.md の 8 節）"""
PURPOSE = ("出口の語 deliver=pr の run が PR 用の commit を積むとき、commit のフックが、対象のテストのコマンドと同じ"
           "「対象のコマンドの環境」（利用者の HOME・XDG が戻り、工場の uv の python が PATH の頭に残らない環境）で走るようにして、"
           "フックが工場の環境のせいで偽の赤を出す余地をなくす。環境以外の振る舞いは変えない。")
CONSTRAINTS = [
    {"text": "workflows/merge/scripts/pr_commit.py の hook_env（73 行あたり）: hook_env は 環境の写しに read_gh_first(env) を足すだけで、"
             "outside_env を通していない（73〜76 行）。",
     "measured_how": "grep -n と sed で pr_commit.py を確認", "kind": "実測",
     "measured_output": "$ sed -n 73,76p workflows/merge/scripts/pr_commit.py\ndef hook_env() -> dict:\n    env = copy_of_env()\n"
                        "    read_gh_first(env)\n    return env"},
    {"text": "呼び元は 1 か所だけのはず", "measured_how": "grep の見込み", "kind": "仮説"},
]
ANSWERS = [{"decision": "continue", "text": "始める（main の確かめの run）"}]
AGENTS_MD = "# AGENTS.md（対象の AI 向けの決まり）\n\n- 新しい観点は block にする。\n- 環境の組み立ては 1 か所に置く。\n"
DESIGN_DOC = "# 設計書\n\n## 1 環境\n\n対象のコマンドの環境は outside_env の 1 か所で組む。\n\n## 2 試験\n\nフックの環境を試験で縛る。\n"
REPLY = {
    "question_stands": True,
    "reason": "問いは実在する。workflows/merge/scripts/pr_commit.py:73-76 の hook_env は outside_env を通していない。",
    "premise_invalid_reason": "",
    "design": "■ 方針: 対象のコマンドの環境を作る所を 1 か所にする。\n\nD1 hook_env を outside_env に寄せる。",
    "elements": [{"id": "D1", "adds": ["hook_env が outside_env を呼ぶ"], "removes": ["hook_env の自前の環境の組み立て"]}],
}
