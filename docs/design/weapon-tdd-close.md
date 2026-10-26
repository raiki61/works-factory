# block の設計書: weapon-tdd-close（書き手の型 tdd-close）

- 何の話か: 修正の block が `include:` する葉の block `workflows/weapon-tdd-close/` のうち、型 `tdd-close` の書き手の設計。共通の形（フォルダ・ports・node の並び・共通の本体・写しの照らし）は [fix.md](fix.md) の 24 節、書き手に渡す slots と鎖の並びは同じ文書の 2 節に書いてあり、この文書は型ごとに違う物だけを書く。
- 決めたこと: 型ごとに違う物は `src/render.py` の 3 つの定数（`ORDER_WEAPON`・`SPAWNS`・`SUMMARY`）と、頭の段落 `prompts/parts/head.md` だけ。
- 読む人: この block を作る・直す実装の役が、型ごとの違いを引く時に読む。急ぎではない。持ち主に求めること: なし。この文書を読んだだけで要る作業は無い。
- 語: D1・D2 は修正の block の型の block 化の段階（D1 が書き手 5 つ、D2 が variant）。「鎖」は修正の block の YAML で、型の block の include を並べた node の並び（fix.md の 2.2.1）。「箱」は型の区分（change・keep・outside。fix.md の 22 節）。`prep` は block の最初の script node で、注文と slots を読んで書き手の指示を組む（落ちるのは run がその node で止まること。fix.md の 24.3）。「注文」は修正の block が型ごとに書く依頼（単位・範囲・許し）。「受け付け」は書き手の返答を通すか拒むかを決める修正の block の検査。「赤を見ない clean の拒否」は、試験が赤になるのを見ずに直したと言う返答を拒む検査。
- block の状態: D1 で作る（別の作業場で写している最中）。名と形は `weapon-static` と同じで、違いは 3 つの定数と `head.md` だけ。

## 役

TDD の輪（`tdd`・`tdd-new`）が赤から緑まで直した単位について、直し直さずに、単位ごとの `changes` の行と周の全体の欄（1 回の返答の全体に付く欄。単位ごとの行とは別）を書く閉じの書き手。輪が緑にした単位の試験のファイルは変えない（受け付けが拒む。修正案が `rewrite_tests` に名指した物と範囲の裁定の範囲だけが例外）。

頭の段落が組み上がる指示の先頭に持つ 1 文（筋書き `fixtures/standalone.stubs.yaml` の `resolved-text-contains` が照らす）: 「You are the TDD loop's closing writer.」

## 表 `src/render.py` の 3 つの定数

- `ORDER_WEAPON = "tdd"`: 注文の `weapon` の語。注文の語が違えば `prep` が落ちる。
- `SPAWNS = False`: 下請けを起こすか。偽なので AI の node の `allowed_tools` に `Agent` を足さず、段落 `spawns`・`g1`・`ask_variant` は偽の値で本体が slots に足す（偽なので、その段落は組み上がる指示に入らない）。下書きの 11.8 の決め（案 B）は tdd の閉じの書き手の外の 5 つに下請けを付けるので、この型は偽のまま。下請けを起こさないので `g1-impl` も組まず、この型の `head.md` が持つ値 `{summary_file}` を下請けのために組むことはない。
- `SUMMARY = True`: TDD の輪の要約を受けるか。真なので、本体が slots の欄 `summary_file` を自分の値に足す。
- 注文の `weapon` の語（`ORDER_WEAPON`）が block の名の `<w>` と違う唯一の型（block の名は `tdd-close`、注文の語は `tdd`）。輪の側の型の名が `tdd`、書き手の側の block が閉じの書き手であることを字で分けるため。

## 頭の段落 `prompts/parts/head.md` の出どころ

D1 の基の main（`e52a1b45`）の `workflows/fix/prompts/parts/tdd-close.md` の、見出し `# Fixing (the writer's job)` と `<!-- end rules -->` の間の字を、字を変えずに移した物。頭の段落は 2 段落: 役の定義（輪がすでに直した単位の答えを書く役で、直し直さない）と、輪の結果のファイルを名指す段落（`{summary_file}`。輪が直した単位の `changes` の行に何を書くか）。`{summary_file}` を持つ md はこの block の頭の段落だけなので、slots の上の段の欄 `summary_file` を読むのもこの block だけ（`SUMMARY` が真）。型ごとの頭の文の照らしは `tests/workflows/test_weapon_assets.py`（頭の文の表の字が、この main の commit の `parts/tdd-close.md` の字に在ることと、組み上がった指示に在ること）。
- この型だけの決まり: この型の書き手が走るのは 1 回目の段（tdd の輪の後）だけ。裁定の後の段には tdd の閉じが無く、tdd の単位は `variant` の注文になる（22.5）。そのため block の include は 1 回目の鎖の `w-tdd-close` だけで、裁定の後の鎖（`wr-`）に無い。

## この型の受け付けの義務の在処

受け付けの義務は修正の block に在り、型の block は義務の表を知らない（[fix.md](fix.md) の 22.4）。型のモジュール `src/tdd.py` の `DUTIES` は空で、輪の中の赤の記録（輪の状態の凍結と名指し）が義務の出どころ。箱 change の `BOX_DUTIES` は今は空で、`duties.py` のコメントが段 2 で足すと書く物（`change_named_or_gone`）は、この D1 の外。型の箱は `duties.BOXES`（`tdd` は `change`）。指示の段落のうち義務の表から引く 4 つ（`rules_change`・`rules_sites`・`rules_red`・`conflict_change`）も修正の block が `writer_slots` で組んで slots に入れる（[fix.md](fix.md) の 2.3）。

## 指示の md と試験

指示の md `prompts/tdd-close.md` は `{shared:writer-top}`・`{part:head}` を含む枠・`{shared:writer}` を並べるだけで、書き手の型の block 全部（D1 の 5 つに D2 で variant を足した合計 6 つ）で同じ字（[fix.md](fix.md) の 24.1）。試験は `tests/blocks/weapon_tdd_close/test_tdd_close.py`（`tests/blocks/kit.py` の `WriterBlockCase` に block の名を渡して継ぐだけ。24.8）。
