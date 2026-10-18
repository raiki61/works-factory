"""事前審査のブロック（workflows/plan-review/）が隣に書くファイル（docs/design.md の「サブグラフの出力の約束」の plan-review の出力の欄の先）の名の住処。

名の字はここだけが持つ（層の地図 docs/layers.json の homes が plan-review の住処にここを宣言し、照らし beside はここを数えない）。事前審査の
書き手 lib/boardview.py は、ここの定数を import して引く。事前審査の外の読み手は名を持たず、事前審査の出力の欄のポインタで受ける（#680）。
返す節 workflows/plan-review/scripts/result.py は lib を読めない時にも書けるよう同じ字を写して持つ（試験が一致を縛る）。
名は判定の lib/judgebeside.py に倣った。ここは何も import しない。
"""
GATE_PASSES_FILE = "gate-passes.json"          # 修正前の承認ノードが聞かずに通した行（返り review の隣。欄 gate_passes）
GATE_FILE = "gate.json"                        # 承認ノードの項目 items と壁打ちの往復の行 converge（返り review の隣。欄 gate）
DESIGN_PREMISES_FILE = "design-premises.json"  # 独立設計の役に貼った物の控え {node, given, withheld, seen, claims?}（返り design の隣。欄 design_premises）
