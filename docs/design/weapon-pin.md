# block の設計書: weapon-pin（書き手の型 pin）

- 何の話か: 修正の block が `include:` する葉の block `workflows/weapon-pin/` のうち、型 `pin` の書き手の設計。共通の形（フォルダ・ports・node の並び・共通の本体・写しの照らし）は [fix.md](fix.md) の 24 節、書き手に渡す slots と鎖の並びは同じ文書の 2 節に書いてあり、この文書は型ごとに違う物だけを書く。
- 決めたこと: 型ごとに違う物は `src/render.py` の 3 つの定数（`ORDER_WEAPON`・`SPAWNS`・`SUMMARY`）と、頭の段落 `prompts/parts/head.md` だけ。
- 読む人: この block を作る・直す実装の役が、型ごとの違いを引く時に読む。急ぎではない。持ち主に求めること: なし。この文書を読んだだけで要る作業は無い。
- 語: D1・D2 は修正の block の型の block 化の段階（D1 が書き手 5 つ、D2 が variant）。「鎖」は修正の block の YAML で、型の block の include を並べた node の並び（fix.md の 2.2.1）。「箱」は型の区分（change・keep・outside。fix.md の 22 節）。`prep` は block の最初の script node で、注文と slots を読んで書き手の指示を組む（落ちるのは run がその node で止まること。fix.md の 24.3）。「注文」は修正の block が型ごとに書く依頼（単位・範囲・許し）。「受け付け」は書き手の返答を通すか拒むかを決める修正の block の検査。「赤を見ない clean の拒否」は、試験が赤になるのを見ずに直したと言う返答を拒む検査。
- block の状態: 今の木に在る（`workflows/weapon-pin/`）。

## 役

コードを変えず、試験が捕らえていない欠陥の単位に、今の振る舞いを固める試験を足す書き手（pin。試験を走らせる準備のファイルだけを書く「下ごしらえ」の単位も受ける）。足した試験は直す前の版で通り（機械が 2 回走らせる）、足した試験ごとに、縛るコードを壊して赤・戻して緑を見る（`closure` の証明）。

頭の段落が組み上がる指示の先頭に持つ 1 文（筋書き `fixtures/standalone.stubs.yaml` の `resolved-text-contains` が照らす）: 「You are the pinning writer, a fixer.」

## 表 `src/render.py` の 3 つの定数

- `ORDER_WEAPON = "pin"`: 注文の `weapon` の語。注文の語が違えば `prep` が落ちる。
- `SPAWNS = True`: 下請けを起こすか。真なので AI の node の `allowed_tools` に `Agent` を足し（下書きの 11.8 の決め〔案 B〕: 下請けを付けるのは、TDD の輪の結果を閉じる書き手 `weapon-tdd-close` を除く 5 つの型 variant・remove・pin・tidy・static。この型も入る。D2 の 2 段目〔段 2〕で足した。案 B を選んだ理由は下書きの 11.8）、段落 `spawns`・`ask_variant` は真（`ask_variant` は、範囲の相談の節が入る周で真になる slots の `ask` が偽なら偽）で本体が slots に足す。段落 `g1` は slots の `subagents.owed`（下請けを起こす単位）が空でない周だけ真。下請けのファイルは本体が `prep` で block の place に書き、実装役の指示 `g1-impl-<n>.md` には、この block の `prompts/parts/head.md`（下の頭の段落）を値を渡さずに組んだ文面そのもの（この `head.md` は `{名}` の差し込み欄を持たない。持てば組む時に落ちる）が `{weapon_rule}` の段落として渡る（型の決まりが、下請けの実装役の手順書の「試験を書け」とぶつかる時に、下請けにも守らせる。fix.md の 24.9）。
- `SUMMARY = False`: TDD の輪の要約を受けるか。偽なので、`summary_file` は足さない。

## 頭の段落 `prompts/parts/head.md` の出どころ

D1 の基の main（`e52a1b45`）の `workflows/fix/prompts/parts/pin.md` の、見出し `# Fixing (the writer's job)` と `<!-- end rules -->` の間の字を、字を変えずに移した物。頭の段落は 2 段落: 直す前の版に在る設定のファイルは書き換えない、の 1 文（役の定義の前に置く。下ごしらえの単位の決まり）と、役の定義。型ごとの頭の文の照らしは `tests/workflows/test_weapon_assets.py`（頭の文の表の字が、この main の commit の `parts/pin.md` の字に在ることと、組み上がった指示に在ること）。

## この型の受け付けの義務の在処

受け付けの義務は修正の block に在り、型の block は義務の表を知らない（[fix.md](fix.md) の 22.4）。この型の義務は、箱 keep の `duties.keep_same_result`（`BOX_DUTIES`）と、型のモジュール `src/pin.py` の `DUTIES`（義務の関数の並び。`tests_only`・`twice`・`sites_per_test`）。`sites_per_test` は足した試験ごとに、`test` がその id で赤を見た `sites` の行を求め（`fixed_by` は書かない。戻す塊が無い）、書かせる段落 `rules_sites_test` を属性 `paragraph` で持つ（段 2 の PR F1）。壊して赤の証明の段落（`rules_sites`）と赤を見ない clean の拒否（`rules_red`）は、修正の block が `SITES_WEAPONS`・`board.RED_WEAPONS` から引く。型の箱は `duties.BOXES`（`pin` は `keep`）。指示の段落のうち義務の表から引く 7 つ（`rules_change`・`rules_sites`・`rules_red`・`conflict_change`・`rules_sites_at`・`rules_sites_test`・`rules_red_unit`）も修正の block が `writer_slots` で組んで slots に入れる（[fix.md](fix.md) の 2.3）。

## 指示の md と試験

指示の md `prompts/pin.md` は `{shared:writer-top}`・`{part:head}` を含む枠・`{shared:writer}` を並べるだけで、書き手の型の block 全部（D1 の 5 つに D2 で variant を足した合計 6 つ）で同じ字（[fix.md](fix.md) の 24.1）。試験は `tests/blocks/weapon_pin/test_pin.py`（`tests/blocks/kit.py` の `WriterBlockCase` に block の名を渡して継ぐだけ。24.8）。
