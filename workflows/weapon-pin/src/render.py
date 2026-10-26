"""型 pin の書き手の block が、共通の本体 workflows/.shared/writerblock.py に渡す表（型ごとに違う物はこの 3 つの定数だけ。どの型も 3 つとも書く）"""
ORDER_WEAPON = "pin"      # 注文の weapon の語
SPAWNS = True             # 下請けを起こすか（Agent を allowed_tools に持つか）
SUMMARY = False           # TDD の輪の要約を受けるか
