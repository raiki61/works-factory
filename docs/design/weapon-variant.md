# block の設計書: weapon-variant（書き手の型 variant）

- 何の話か: 修正の block が `include:` する葉の block `workflows/weapon-variant/` のうち、型 `variant` の書き手の設計。共通の形（フォルダ・ports・node の並び・共通の本体・写しの照らし）は [fix.md](fix.md) の 24 節、書き手に渡す slots と鎖の並びは同じ文書の 2 節、下請けの部品は 24.9 に書いてあり、この文書は型ごとに違う物だけを書く。
- 決めたこと: 型ごとに違う物は `src/render.py` の 3 つの定数（`ORDER_WEAPON`・`SPAWNS`・`SUMMARY`）と、頭の段落 `prompts/parts/head.md` だけ。この型は、AI の node に `Agent` を足し、項目ごとに下請けの実装役と審査役を起こせる型。下書きの 11.8 の決め（案 B）で、下請けを起こすのは、TDD の輪の結果を閉じる書き手 `weapon-tdd-close` を除く 5 つ（variant・remove・pin・tidy・static）で、variant だけの型ではない（D2 の段 2 で pin・tidy・static・remove にも付けた。部品は 5 つで共通なので、この block の中に置かない）。
- 読む人: この block を作る・直す実装の役が、型ごとの違いを引く時に読む。急ぎではない。持ち主に求めること: なし。この文書を読んだだけで要る作業は無い。
- 語: D1・D2 は修正の block の型の block 化の段階（D1 が書き手 5 つ、D2 が variant）。「鎖」は修正の block の YAML で、型の block の include を並べた node の並び（fix.md の 2.2.1）。「箱」は型の区分（change・keep・outside。fix.md の 22 節）。`prep` は block の最初の script node で、注文と slots を読んで書き手の指示を組む（落ちるのは run がその node で止まること。fix.md の 24.3）。「注文」は修正の block が型ごとに書く依頼（単位・範囲・許し）。「受け付け」は書き手の返答を通すか拒むかを決める修正の block の検査。「下請け」は書き手が修正案の項目ごとに Agent で起こす実装役と審査役。
- block の状態: 今の木に在る（`workflows/weapon-variant/`）。

## 役

TDD の輪を通らず、振る舞いを変える直し（輪が緑にしなかった単位、振り分けを諦めた単位、裁定の後の段で tdd の単位から引き直した単位を含む）を直す書き手。同じ決まりを共有する所を全部見つけて直し、場所ごとに直しが効いている証を `closure` に書く。直す義務の単位のうち TDD の輪が緑にした単位を除いた物には、修正案の項目ごとに下請けの実装役と審査役を起こす（今の F101・G1〜G8 の手順のまま。実装役が直し、審査役が差分を修正案の項目どおりか見て、だめなら実装役に直させる。3 回まで）。

頭の段落が組み上がる指示の先頭に持つ 1 文（筋書き `fixtures/standalone.stubs.yaml` の `resolved-text-contains` が照らす）: 「You are the variant writer, a fixer.」

## 表 `src/render.py` の 3 つの定数

- `ORDER_WEAPON = "variant"`: 注文の `weapon` の語。注文の語が違えば `prep` が落ちる。
- `SPAWNS = True`: 下請けを起こすか。真なので AI の node の `allowed_tools` に `Agent` を足し、段落 `spawns`・`ask_variant` は真（`ask_variant` は、範囲の相談の節が入る周で真になる slots の `ask` が偽なら偽）で本体が slots に足す。段落 `g1` は slots の `subagents.owed`（下請けを起こす単位）が空でない周だけ真。下請けのファイルは本体が `prep` で block の place に書く（fix.md の 24.9）。実装役の指示 `g1-impl-<n>.md` には、この block の `head.md`（下の頭の段落）が `{weapon_rule}` の段落として渡る。この型の頭の段落は下請けの実装役の手順書の「試験を書け」とぶつからないが、本体の組み方は 5 つの型で同じ（型ごとの分岐を作らない）ので、この型の `head.md` も同じ道で渡る。
- `SUMMARY = False`: TDD の輪の要約を受けるか。偽なので、`summary_file` は足さない。

## 頭の段落 `prompts/parts/head.md` の出どころ

D2 の基の main（`05dbfa97`）の `workflows/fix/prompts/parts/variant.md` の、見出し `# Fixing (the writer's job)` と `<!-- end rules -->` の間の字を、字を変えずに移した物。頭の段落は 1 段落（役の定義）。字は `workflows/weapon-variant/prompts/parts/head.md`。型ごとの頭の文の照らしは `tests/workflows/test_weapon_assets.py`（頭の文の表の字が、D1 の基の main の commit の `parts/variant.md` の字に在ることと、組み上がった指示に在ること）。下請けの実装役の指示に型の決まりを渡す段落 `{weapon_rule}` に、この `head.md` を組んで差し込むのは段 2（下書きの 11.8 の決め。案 B）。

## この型の受け付けの義務の在処

受け付けの義務は修正の block に在り、型の block は義務の表を知らない（[fix.md](fix.md) の 22.4）。この型の義務は 2 か所から引かれる: 箱 change の `BOX_DUTIES`（`change_named_or_gone`。段 2 の PR F2。名指しの試験が起点の木で赤・返した木で緑であること。書かせる段落は属性 `paragraph` が名指す `rules_named`、書く欄は返答の `evidence.named`）と、型のモジュール `src/variant.py` の `DUTIES`（`sites_shape`・`unit_red`。段 2 の PR F1）。`sites_shape` は、判定が単位に付けた問い（`class_query`。同じ形の欠陥を全部探す）の在る単位に、次の 2 つを求める。(1) `sites`（同じ決まりを共有する所ごとの記録）の各行の `at`（直す前の当たりの場所 `path:line`）が、問いの当たりの行に在ること（問いを行で結べない単位は (1) を照らさず、その単位も (2) の重なりと `unit_red` は照らす）。(2) 各行の `fixed_by`（その所を直した行の範囲）が、注文の `since`（この型の段の頭の木）から書き手が返した木までの差分の塊と重なること。`unit_red` は単位ごとに赤を見た `sites` の行を求める。受け付けは箱の義務と型の義務の両方を満たす時だけ通す。周の全体の F135（返答の `fix_closure` を `clean` と書いたのに赤を見た記録が無い返答を拒む照らし）は残る。書かせる段落は属性 `paragraph` が名指す `rules_sites_at`・`rules_red_unit`。型の箱は `duties.BOXES`（`variant` は `change`）。赤を見ない clean を拒む照らし（F135）は `board.RED_WEAPONS` に入っている。指示の段落のうち義務の表から引く 8 つ（`rules_change`・`rules_sites`・`rules_red`・`conflict_change`・`rules_sites_at`・`rules_sites_test`・`rules_red_unit`・`rules_named`）も修正の block が `writer_slots` で組んで slots に入れる（[fix.md](fix.md) の 2.3）。

## 下請けの材料

slots の `subagents`（fix.md の 2.3）を、修正の block の `writer_slots` が型を問わず同じ組み方で渡す。この型の本体 `prep` がそれを読む。値の関数は `lib/subagents.py`、指示の md は `.shared/prompts/g1-*.md`・`seat-briefs.md`、ファイルを書く所は本体 `writerblock.subagent_items`（fix.md の 24.9）。この block の中に下請けのコードは置かない（2 つ以上の block が使う物は `lib/` と `.shared/`。憲法の 4）。

## 指示の md と試験

指示の md `prompts/variant.md` は `{shared:writer-top}`・`{part:head}` を含む枠・`{shared:writer}` を並べるだけで、書き手の型の block 全部（6 つ）で同じ字（[fix.md](fix.md) の 24.1）。試験は `tests/blocks/weapon_variant/test_variant.py`（`tests/blocks/kit.py` の `WriterBlockCase` に block の名を渡して継ぐだけ。24.8。下請けの段落が表の `SPAWNS` に従うことと、下請けのファイル 2 つが place に書かれることも、この組が照らす）。
