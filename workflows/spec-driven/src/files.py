"""spec-driven の block の place のファイルの名・止めの語・起動の殻から受ける環境変数の名（docs/design/spec-driven.md の 2.6・6.2）。
名はこのモジュールだけが持つ。

- ENTRY・CHECK: 形 entry と形 check の結果の控え（finish が読んで返す）
- REQUEST・PURPOSE・SPEC: 形 entry が表と設計書から組み、判定の役と計画の部品に渡すファイル
- REVIEWS_ENV: 起動の殻が、会話で回した審査の記録を照らした結果のファイルを渡す環境変数（bin/_lib/specreviews.py の RESULT_ENV と
  同じ字。tests/bin/test_spec_reviews.py が突き合わせる）
"""
import stopby   # lib/

ENTRY = "entry.json"
CHECK = "check.json"
REQUEST = "request.json"
PURPOSE = "purpose.json"
SPEC = "spec.md"
OWN_FILES = (ENTRY, CHECK, REQUEST, PURPOSE, SPEC)
REVIEWS_ENV = "WORKS_FACTORY_SPEC_REVIEWS"
STOP_ENTRY = stopby.declare("spec-entry", "仕様駆動の道の入口の確かめが通らない（表の形・設計書・審査の記録。AI を起こす前に止めた）")
STOP_MISMATCH = stopby.declare("spec-mismatch", "仕様駆動の道で、判定と計画の後に機械が仕様とリポジトリの食い違いを見た（仕様を書き換えずに止めた）")
NO_REVIEWS = "審査の記録を照らした結果が渡されていない（起動の殻を通して起動する）"
