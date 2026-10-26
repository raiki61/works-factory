# 直し方の型の段 1・PR A の実装の控え（受付 20261025-023207-a42ccb）

- 何の話か: 設計の下書き [2026-10-24-fix-weapons.md](2026-10-24-fix-weapons.md)（以下「下書き」）の 4.4 の作る物 1〜8・10・11・12 を、修正の block の中で作る PR A の、実装の部署の控え。作る物 9（修正役の指示の移し）は PR B で、この PR は指示の観点の文を移さず消さない。
- この控えに書く物: 下書きが黙っていた所・PR A の字の制約（指示を移さない）とぶつかった所で実装の部署が決めた事と、どの commit で何を閉じたか。会話は納品のたびに空になるので、続きはここと PR の本文から読み直す。

## 1 PR A の境目（実装の部署の決め。持ち主が覆せる）

頼みの「PR A ではアセットを減らさない」（指示の md の観点の文を移さず消さない・修正役の返答の形の必須の欄を減らさない）と「守りを弱めない」を、下書きの 4.4 の字より先に置いた。そのために次の 3 つを決めた。

1. 書き手は修正役のまま 1 つ: 型ごとの書き手の指示（variant・static・tidy・pin・remove）は作る物 9 で修正役の指示を仕分けて作る物で、PR A には無い。PR A の組の子は、tdd の輪と、修正役の輪（`fix-loop`）の 2 つの輪を `orders` の真偽で `when:` に並べ、修正役が tdd 以外の型の注文を全部受ける。修正役は今と同じく tdd の輪が緑にした単位の行も `changes` に写す（下書き 3.1 の「輪が自分で changes を書く」は tdd の役の指示の直しが要るので PR B）。
2. 書き手の返す証拠が要る照らしは PR B で効かせる: 返しの `evidence.named`・`evidence.kinds`・`sites` の `at`・`fixed_by`・`test`・`na` は、修正役の指示が書かせていない欄で、指示なしに求めると拒否が続いて単位が諦めに倒れる。PR A は形（schema）と義務の表の行と照らしの関数を置き、機械が自分で決められる照らしだけを受け付けで効かせる。効かせる物と待つ物の表は 3 節。
3. 古い照らしは残して新しい照らしを足す: 凍ったファイル・試験の変更の許し・試験の無い時の止め方は、PR A で新しい口（`returns/`・注文の `permits`・`no-suite`）を足しても、今の照らし（輪の状態の凍結・`conflict.test_permits`）を外さず、両方を通る物だけを通す（どちらか厳しい側）。読み手を替えたのは、同じ値を同じ形で持つ置き場に替えた所だけ（例: 元の結末を輪の状態から `base.json` へ）。

## 2 置き場（下書き 2.1 のとおり。ここは名だけ）

- `base.json`・`accept.json`（組の置き場・親の置き場・確かめ直しの `<name>/`）・`returns/<k>.json`・`bases/<k>/`・`orders/<weapon>.json`・`orders.json`。名は `workflows/fix/src/files.py` だけが持つ。
- 振り分けの段の状態は別のファイルにせず、後の TDD の輪と同じ輪の状態のファイル `tdd-<k>/state.json` に段 `route` で置く（下書き 4.1 の 3 の「回数と会話」の、輪の回数の上限と申し出の数えを今と同じに続けるため。`route-go` が置き、`route-step` が段を `routed` にし、`orders` が tdd の単位の並びを置いて段を `test` にする）。

## 3 照らしの効かせ方（PR A）

B とした物の行き先は 6 節。

| 照らし | PR A | 待つ物 |
| --- | --- | --- |
| tdd の型の義務 | 今のまま（輪の中） | なし |
| F135（赤を見ない clean を拒む） | variant・remove・pin の単位に当てる | 単位ごとにするのは B |
| static の義務 1〜3 | 効かせる | 4（kinds）は B |
| keep の同じ結果の照らし | tidy・pin に効かせる | なし |
| pin の義務 1・2 | 効かせる | 3（sites の test）は B |
| variant の sites の 2 つの照らし | 関数と試験だけ | 受け付けは B |
| change の箱の義務（名指しの赤緑か gone） | 関数と試験だけ | 受け付けは B |
| na | 置かない（必須の欄を減らす向き） | B |
| 返しの控えの凍ったファイル | 効かせる（`duties.frozen_by_returns`。注文の `permits` の範囲だけを許す。今の `facts.check_frozen` と並べる） | なし |
| 受け付けの名指し | 注文の `units[].tests`・`permits` の `rewrite` と、輪の状態の今の名指しの和（狭めない） | 返しの `evidence.named`・`added`・`rewritten` は B |

- 4.4 の 4 の「直す所」（修正役の返答の形の YAML の `changes` の `required`・`precedent` の `allOf`・`bypass_tried` と `breaks` の `minLength`・`sites` の行の形、`recount._reply_shape_problems` の差分のパスの引数、`unitrows._unpathed` と `sites` の並べ替え、筋書き `standalone.stubs.yaml:18`、`sites` の行を組む受け付けの試験）は、どれも `na` と `sites` の新しい欄（`at`・`fixed_by`・`test`）を入れるための直しで、上の表の `na` と `sites` の行と一緒に B へ回す。`na` は欄を欠けてよい形にする（緩める向き）ので、PR A は返答の形を変えない。
- 4.4 の 5 の申し出の種類 `red_at_base` と、その裁定を `fix_plan_item`・`ask_human` に絞る yes/no は B へ回す。訳: 種類を出すのは下ごしらえの書き手で、PR A には居ない（1 の 1）。種類の一覧 `conflict.DIV_KINDS` に足すと、共通の断片 `writer-rules.md` と TDD の役の指示 `tdd.md` が一覧の全部の語を言うことを縛る試験（`tests/blocks/fix/test_prompts.py` の DIV_KINDS の照らし・`tests/blocks/delta_review/test_prompts.py` の 6 つの数え）のために、指示の既存の文（「6 つの場面の語」など）を書き換えることになり、頼みの「足してよい文は 4.4 の 6 が名指す 1 文ずつだけ」の外になる。PR A の 5 で作るのは、裁定の後の注文（`orders.write_ruled`。`checked_as`・段の番 2n・裁定の範囲を入れた `permits`）、裁定の控えの欄 `stage`（`ruling.seen_stage`）、`checked_as` で義務を引く受け付け、裁定の後の段で F135 を返答の全部の行で見ること、2 回目の block の組の子が段の番 3 を数えるための空の `prior/`（`board.adopt_inputs`）。
- 4.4 の 6 の下ごしらえの指示の md への 1 文（在る設定のファイルは書き換えない）は B へ回す。訳: 下ごしらえの書き手の指示の md は作る物 9 で修正役の指示を仕分けて作る物で、PR A には無い（1 の 1）。修正役の指示に足すと、頼みの「足してよい文は 4.4 の 6 が名指す 1 文ずつ」の置き場の外になる。機械の照らし（`pin.tests_only` の設定のファイルの例外と、拒んだパスを 0 件の止めの訳に載せる所）は PR A で効かせる。
- 4.4 の 6 の止め `no-suite` は 3 か所で決める: 組の頭（`orders.no_suite_why`。実行器が無く元の結末が取れず、計画の語が static でない単位が在る）・TDD のループ（実行器が結末を返さない。`tdd._abort` の段 runner が輪の状態に印）・受け付け（`board.no_suite_at_accept`。型の義務より前）。止めた印は `tdd-start.json` か輪の状態に置き、`fix-prep` は印が在れば修正役を起こさない（`board.no_suite_stop`）。輪が済まずに抜けた組でも、組の出口は印を落とさない（`group_end.tdd_exit`）。今まで実行器の無い組を修正役に直に回していた試験と筋書き（`fixtures/standalone.stubs.yaml`・`consult.stubs.yaml`）には、試験の実行器を渡して同じ所まで届かせた（止まる形そのものは `tests/blocks/fix/test_no_suite.py`）。
- 4.4 の 8 の出力の欄 `removed_tests`・`untested` は、返しの控え `returns/` から組む（`finish.returned_rows`）。下書きの 4.3 は「消した試験を「書き換えを許したテストを触った」の数えから外す」と書くが、許しの行はパスごとで試験の id を持たないので、試験を消しただけで足しも書き換えもしなかったファイル（`only_removed`）だけを外す（同じファイルで書き換えもした物は数えに残す。厳しい側）。消した試験は開き方に依らず開ける理由（must）。試験を求めなかった直しは節に並べ、種類 code のファイルを触った時だけ開き方で開く理由にした（下書きは理由にするかを書いていない。実装の部署の決め）。
- 注文の形（`weapon-order.schema.json`）の欄 `run`・`asks_answered`・`orders.<weapon>`（下書き 2.1）は PR A で外した。main の #861 が中身を宣言しない形の欄を拒むようになり、PR A にはこの 3 欄の書き手が居ない（中身を決める型ごとの書き手の指示は PR B）。外しても今の注文は 1 つも拒まれない（書いていない欄）。PR B で書き手と一緒に形を書いて足す。返しの形（`weapon-return.schema.json`）の `frozen`・`evidence.before`・`after`・`compared`・`asks` は、下書き 2.2 の字のとおりに中身を宣言した。
- 輪の状態の無い組（static だけの組など。元の結末は取ったが TDD の輪を開かない組）の受け付けは、今は試験を走らせなかった（`selected_problems` に状態が無い）。PR A は元の結末 `base.json` で選んで走らせる（`board.accept_base`。厳しい側）。

## 4 進み（commit ごと）

- [x] 下書きの穴 5 つ（第 9 版の続き 5）: d7aab849
- [x] 7 計画の route の語: b6cf2500
- [x] 12 宣言の `list` と `tree_run.run` の `setup`（lib の分）: 1257faee。`basecase` の一覧の走らせは 2・3 の commit
- [x] 1 口の形: b7f90846
- [x] 2・3 型のモジュール・元の結末・振り分けの輪・注文: 部品の分けと node は f6af387d。組の結果の `base` の欄・`bases/<k>/` と `returns/` の引き継ぎ・諦めた単位の variant の注文への書き直しは cea0f8c1（返しの控えを書くのは 4 の受け付け）
- [x] 4 共通の受け付けと義務の表: d6c37bf1
- [x] 5 裁定の後の注文: 0f6d92c3
- [x] 6 止めの語 `no-suite`: 665df082
- [x] 10・11 持ち主の決めの写しと設計書: e21fd105
- [x] 8 出力の欄と最後の承認の節: feb82fcb
- [x] main（#861）の取り込み: 形のファイルに中身を宣言し、注文の 3 欄を外した（3 節）
- [x] PR #869 のレビューの続き（受付 20261025-074047-6d9c7a）: 5 節

## 5 PR #869 のレビューの続き（受付 20261025-074047-6d9c7a）

この節は、PR #869 のレビューで直した物と後に回した物の控え（済んだ事の記録）。読み手に頼む作業は無い。持ち主が覆したい物は「窓口の決め」と「後に回した nit」の行。

レビューの全文は窓口の受け箱（受付 20261025-074021-7ba548 の返し）。止める指摘 6 つと nit のうち PR A のコードの物を直した。

- 窓口の決め（持ち主が覆せる）: 前の返しの問い 1（下ごしらえの指示の md の 1 文）と 2（申し出の種類 `red_at_base`）は PR B に回す（3 節の 3・4 項目の訳のとおり）。問い 3（持ち主の決めの写しの字）はそのままにし、レビューの nit の字だけ直した。
- 止める指摘:
  - 1・3（906ce3cf）: 起動スクリプトの書き直しの後のやり直し（`suitefix.retry`）も、組の頭と同じ口 `suitefix.settle_start` で no-suite の止めを当てる。工場（AI）が書いた実行器（試験を走らせる起動スクリプト）を、後の run で使い回すために取り置く（`suitewrite.keep_runner`）のは、元の結末（直す前の試験の結果）が取れた組だけにする。取れたかの印は `base.json` の `taken`。`retry` の返りの `tdd`（TDD の輪を回すか）も、取り置くかと同じこの印 `taken` で決める（`taken` が真なら回し、偽なら回さない。組の頭が書く `tdd-start.json` の `no_suite` の印では決めない）。
  - 2（0ae251fc）: 受け付けの止め `no_suite_at_accept` は、試験を選ぶ側と同じ元の結末（`board.accept_base`。裁定の後の置き場は `bases/<k>/base.json`）を読む。
  - 4（9ae374c1）: 申し送り `carry` と返し `weapon-return` の形の `frozen` の値に null を許す。
  - 5（340ff1da）: 型ごとの注文（その許し `permits` も）は段の頭で 1 度しか書かないので、段の途中で取れた範囲の相談の合意は注文の許しに入らない（そのままでは、下の凍結の照らしがその合意の範囲を許さない）。直し: 注文の索引 `orders.json` に、段の頭に在った合意の見分けの字 `agreed`（`<group_id>:<id>` の並び）を書く。凍結の照らし `frozen_by_returns`（変更が、前の型・前の段の返しが凍らせたファイル〔`returns/` の `frozen`〕に触れていないかを、注文の `permits` の範囲だけを許して照らす）は、`agreed` に無い合意（段の頭の後に取れた物。`orders.later_agreed` が引く）の範囲も許しに足す。相談はその時の凍結を見て許したので。段の頭に在った合意の扱いは変えない: 注文を書く時、その範囲が前の返しの凍ったファイルに当たれば `permits` から外す（`docs/plans/2026-10-24-fix-weapons.md` の 2.1 の `permits`・`docs/design/fix.md` の「前の型の物を引く」）。諦めた単位を `variant` の注文に書き直す `regive` は、段の頭の `agreed` をそのまま引き継ぐ。
  - 6（e8328f88）: 受け付け（`fix-accept`）を通して、返しの控えの凍結の照らしと注文の名指しが効くことを縛る試験（`tests/blocks/fix/test_weapons.py` の `AcceptWiringCase`）。
- nit で直した物: 親へ写す `base.json` の `exe` の引き直し（d2d74063）・static の種類の照らしの素通り（aee4b823。計画から種類が引けない時は拒む）・`precheck` の `frozen_by_returns`（3ac40115）・返しの `asks` の語と注文の `base` の空の字（0c66195c）・持ち主の決めの字 3 つ（dda2c259）。
- 後に回した nit（訳つき）:
  - 下ごしらえ（pin）を keep の組の前に挟む所（`orders.compute`）: PR B。下ごしらえの書き手が PR A に居ない（1 節の 1）。今は挟まずに受け付けで止まる（fail closed。`pin.tests_only` と 0 件の止め）。
  - 守れない依存 `unsatisfied` を報告に出す: PR B。PR A は tdd の輪の後に残りの型を修正役の 1 つの返答で受けるので、守れない対は「後の単位が tdd」の時だけ起き、索引 `orders.json` に名で残す。型を 1 回ずつ回す並びが入る PR B で、組の結果と報告の節を一緒に足す。
  - 注文の `since` が全部の型で同じ木: PR B。PR A は型の注文を同じ段の頭で 1 度に書き、修正役が 1 つの返答で受けるので、前の型の返しの `tree` はまだ無い。型を順に回す PR B で、後の型は前の型の返しの `tree` を使う。
  - 返しの形の `jitter` と読み手 `rebuild.py` の `noisy` のずれ: rebuild を作る時（作らない物）。今は読み手が回らないので害が無い。
  - 消した試験 `removed_tests` を拾うのが `.py` だけ: 後。試験の id を引く口（`scope._test_ids`）が Python の構文木で読むため。他の言語の試験の id を引く言語に依らない口（例: 対象の宣言の一覧 `list` の行）を決める時に直す。E13 は `src/` に当たらない。
  - `test_cmd` が走らない時の名乗り（`tdd.py` の `_CmdDown` が `_RunnerDown` の子で no-suite を名乗る）: 後。止めの語を分けると報告と finish の止めの語の表が変わるので、別の変更で決める。
  - `plan-writer.md:156`（仕様の道の節）の「static・tidy・pin を取ってよい」の 1 文: PR B。4.4 の 7 を仕様の道に広げた文で、4.4 は名指していない。指示の文を移す PR B で、残すか消すかを決める（PR A では指示の文を消さない）。

## 6 PR B で手を付けなかった物の行き先（受付 20261025-211611-0333bc）

3 節と 5 節が「B で」とした物のうち PR B（#872）が手を付けなかった物は、段 2（下書きの 4.2。型を block に上げる段）へ回す。済んだ事の記録として、3 節と 5 節の「B」「PR B」の字は書き換えない。訳は共通で、書き手の返す証拠が要る照らしは、書き手の指示がその欄を書かせてから効かせる（1 節の 2。指示なしに求めると拒否が続いて単位が諦めに倒れる）。段 2 は型の返しが block の出力になる段なので、返しの形と照らしを一緒に決める。

- static の義務 4 `kinds_rows`（`workflows/fix/src/static.py` の docstring とコメント）: 段 2。訳: 返しの `evidence.kinds` に種類ごとの行を書かせる指示は PR B で入ったが、行を求める照らしは、段 2 で static の返しの形を決める時に一緒に足す。
- pin の義務 3 `sites_per_test`（`workflows/fix/src/pin.py`）: 段 2。訳: sites の行の `test` を書かせる指示が無いまま求めると拒否が続くので、pin の返しの形と一緒に足す。
- variant の `sites_shape`・`unit_red`（`workflows/fix/src/variant.py`）: 段 2。訳: sites の `at`・`fixed_by` を書かせる指示が無いまま求めると拒否が続くので、variant の返しの形と一緒に足す。
- change の箱の義務 `change_named_or_gone`（`workflows/fix/src/duties.py`）: 段 2。訳: 名指しの赤緑か gone を返しに書かせる指示が無いまま求めると拒否が続くので、change の返しの形と一緒に足す。
- `na`（3 節の表の行と、表の下の 4.4 の 4 の「直す所」の段落。返答の形に `na` と sites の新しい欄 `at`・`fixed_by`・`test` を入れる直し）: `na` は作らない（持ち主の決め `no-na`。計画の 11.12 の 4）。sites の新しい欄 `at`・`fixed_by`・`test` は F1（計画の 11.6 の F1 の作る物の 7）。
- 返しの `evidence.named`（と同じ行の `added`・`rewritten` を受け付けの名指しに足す所。`workflows/fix/src/orders.py` の `named_tests`）: 段 2。訳: 返しが名指す試験を書き手に書かせてから名指しに足す。先に足すと、書かれない欄を求めることになる。
- 守れない依存 `unsatisfied` を報告に出す（5 節の「後に回した nit」の行）: 段 2。訳: PR B は型を順に回す並びを入れたが、依存の辺で並べ替えず（`docs/plans/2026-10-25-fix-weapons-stage1-b.md` の 1 節の 2）、守れない対は今も索引 `orders.json` に名で残る。報告の節は段 2 で組の結果の形と一緒に足す。
- 注文の形の欄 `run`・`asks_answered`・`orders.<weapon>`（`workflows/fix/schemas/weapon-order.schema.json` の description。3 節の最後から 2 つ目の段落）: 段 2。訳: 中身を決める書き手の指示は PR B で入ったが、PR B はこの 3 欄を書かせていない。段 2 で注文が型の block の port になる時に、形と書き手を一緒に足す。

上の 8 項目の置き場は、段 2 の設計の下書き `docs/plans/2026-10-24-fix-weapons.md` の 11.12（第 13 版。main に入る前の、設計の部署の枝 `work/design-seat` の commit dafa015f の版。段 2 の章は別の PR で main に入る）が決める。項目ごとの置き場（F1・F2・F3・E1 の `orders.tdd`、`na` は作らない（持ち主の決め `no-na`。計画の 11.12 の 4））と訳は 11.12 を見る。

上の 8 項目のほかに 1 つ、PR #874 の再レビュー（受付 20261025-230146-c09c8f）の nit も段 2 へ回す。付録 A の F21 の行の残り（「You are the fixer. … and fix the units you owe a fix on the working tree.」）を型ごとに言い直した頭（`workflows/fix/prompts/parts/static.md:6` などの「You are the <型> writer, a fixer. …」）は、観点の表の照らし（`tests/blocks/fix/test_assets.py`）で照らしていない（言い直した頭の文が減っても赤にならない）。F135 の行の残りと同じ形（表の行の `rest` を全部の書き手で照らす）では塞げない。TDD の書き手 `tdd-close` の頭が別の字で言い直しているためで、型ごとの字を表に持つ形が要る。段 2 で型ごとの頭が型の block の指示に移る時に、型ごとの頭の字を照らす形を一緒に決める。
