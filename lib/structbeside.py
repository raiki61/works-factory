"""構造のブロック（workflows/structure/）の置き場のファイルのうち、出力の欄が指す物（docs/design.md の「structure の出力」）の名の住処。

名の字はここだけが持つ（層の地図 docs/layers.json の homes が structure の住処にここを宣言し、照らし beside はここを数えない）。
控えと段 A の書き手 structfile と構造の目の受け付け eye は、ここの定数を import して引く。構造の外の読み手は名を持たず、出力の欄
structure のポインタと、その先の控えの design_file で受ける。

住処を structfile にしないのは、structfile が eye を import するため（eye が structfile の名を引くと輪になる）。ここは何も import しない。
"""
STATE_FILE = "structure-state.json"   # 構造の目の控え（欄 structure が指す。structmark の形）
DESIGN_FILE = "design.jsonl"          # 設計の行のファイル（段 A が 0 バイトで置き、目の受け付けが書く。控えの design_file が指す）
