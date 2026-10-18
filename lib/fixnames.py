"""修正のブロック（workflows/fix/）が隣に書くファイル（docs/design.md の「サブグラフの出力の約束」の fix の出力の欄の先）の名の住処。

名の字はここだけが持つ（層の地図 docs/layers.json の homes が fix の住処にここを宣言し、照らし beside はここを数えない）。修正の書き手
（fixboard・leftovers・tddloop・fixbeside）は、ここの定数を import して引く。修正の外の読み手は名を持たず、修正の出力の欄のポインタで受ける（#681）。
欄 → ファイルの表（PORTS・FROM）は lib/fixbeside.py に置く。

住処を fixbeside にしないのは、fixbeside が書き手 fixboard・leftovers・tddloop を import するため（書き手が fixbeside の名を引くと import が循環する）。
ここは何も import しない。
"""
ALLOWED_TESTS_FILE = "allowed-tests.json"   # 許したテストの変更の訳 [{path, permit, source}]（欄 allowed_tests。fixboard.allowed_test_rows）
ACCEPT_TRACE_FILE = "accept-trace.json"     # 受け付けが選んだ試験を走らせた回の行の並び（欄 accept_trace。fixboard.tests_trace が足す）
LENSES_FILE = "lenses.json"                 # レンズの集め役の事実 {collector: {ok, reason}}（返す節が数えを足して欄 lenses で返す）
CLOSURE_FILE = "closure.json"               # 閉鎖の表 {rows, claimed}（欄 closure。fixbeside.write）
DELTA_HOLES_FILE = "delta-holes.json"       # 差分の審査の穴の名札 {ties, handled}（欄 delta_holes。fixbeside.write）
TDD_UNIT_FILE = "tdd-unit.json"             # 組ごとの TDD の記録（欄 tdd_unit。fixboard.tdd_units の本文）
REMOVED_FILE = "fix-removed.json"           # clean が消したパスの全件 {"removed": [str]}（欄 removed の先。leftovers.remove_new_ignored）
TDD_STATE_FILE = "state.json"               # TDD の輪の状態（置き場の tdd-<k>/ の中。欄 tdd_refused の元。tddloop.start）
