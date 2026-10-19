"""報告の block の place のファイルの名と、機械の報告の見出しの字（docs/design/report.md の 1.4・1.5。名はこのモジュールだけが持つ）。

place（ports.place()）の下:
- facts.json: facts が決めた値 {outcome, stop_reason, ok, ai_go, stamp, lang, run_id, decisions}
- report.md: 機械の報告。report-unwritten.md: 組めなかった時の機械の報告。report-facts-unwritten.md・report-finish-unwritten.md: ライブラリを
  読めない時の訳だけのファイル
- next-request.json・prior-failures.json: 次の run の依頼の下書きと前の失敗（名は lib/carry が持つ。周の鎖と次の run の入口が読む）
- write-prompt-<n>.md・cold-prompt-<n>.md（prompt.emit が書く）
- rejects-report.json・rejects-report.md・candidate-report.json（lib/rolekit の控え。受け付けの名は ROLE）
- r<n>/handoff.json: 周ごとの引き継ぎのメモ
- ai.json（受けた書き手の返答と初見の読み手の判定）・report-ai.md・report-detail.md
"""
FACTS_FILE = "facts.json"
REPORT_FILE = "report.md"
UNWRITTEN_FILE = "report-unwritten.md"
FACTS_UNWRITTEN_FILE = "report-facts-unwritten.md"
FINISH_UNWRITTEN_FILE = "report-finish-unwritten.md"
AI_FILE = "ai.json"
AI_REPORT_FILE = "report-ai.md"
DETAIL_FILE = "report-detail.md"
NOTE_ROUND = "r{n}"
ROLE = "report"            # 受け付けの控えの名（rejects-report.json）。周の数えと拒みの数えもこの名
WRITE_NODE = "write"       # AI の node の id（prompts/write.md）
COLD_NODE = "cold"         # AI の node の id（prompts/cold.md）
WRITE_LOOP = "write-loop"  # 書き手のループの node の id（落ちたかを run の記録で見る）
WORKFLOW_FILE = "works-factory-report.yaml"

TITLE = "# 報告（run {run}）"
DECISIONS_HEADING = "## 1. 人が決めること"
STOP_HEADING = "## 2. 止めたか"
WHERE_HEADING = "## 3. 見る所"
CALLS_HEADING = "## 4. 役が呼んだ道具"
PRIOR_HEADING = "## 次の run に引き継ぐ落ちた理由"
MODEL_HEADING = "## 模型"
COST_HEADING = "## 費用"
NOTES_HEADING = "## 注意（読めなかった物）"


def bare(heading: str) -> str:
    """見出しの `## ` を外した字（指示に入れる時と、見出しを探す時の字）"""
    return heading.removeprefix("## ")
