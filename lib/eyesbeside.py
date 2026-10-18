"""独立の目のブロック（workflows/eyes/）が隣に書くファイル（docs/design.md の「サブグラフの出力の約束」の eyes の出力の欄の先）の名の住処。

名の字はここだけが持つ（層の地図 docs/layers.json の homes が eyes の住処にここを宣言し、照らし beside はここを数えない）。目の書き手
lib/eyeverdict.py は、ここの定数を import して引く。目の外の読み手は名を持たず、目の出力の欄のポインタで受ける（#680）。
名は判定の lib/judgebeside.py に倣った。ここは何も import しない。
"""
R4_PASSES_FILE = "r4-gate-passes.json"   # 人が通したので R4 の問いから外した行（欄 r4_passes）
PREMISE_FILE = "premise-check.json"      # 前提の検算の役の返り（目の返りの eyes/<目>.json の 1 つ。key・resolution・facts_to_add。欄 premise_reply）
