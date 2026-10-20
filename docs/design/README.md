# 部品の作り直しの型（issue #765 の設計の正本）

- 何の話か: 工場（このリポジトリの Archon のワークフロー）の AI の役と観点を、単独で呼べる部品（block）に作り直す。その全部の block が従う型を、この文書が決める。block ごとの設計書は同じフォルダに 1 本ずつ置く。最初の 1 本は世界の解（依頼の各行を業界の定石と照らす観点。block `world`）の [world.md](world.md) で、ほかの設計書はこれを写して書く。
- 決めたこと: block は作り直しの間だけの置き場 `blocks/`（2 つ目の pack）に横に並べて作り、block ごとに、それだけで回るかを確かめた。1 回の組み込みで line を新しい block に切り替え、古いサブグラフを消し、`blocks/` を `workflows/` に入れ替えた（11.3）。今の pack は `workflows/` の 1 つだけ。指示は AI のノードごとに 1 本の英語の md に書き、Python は `{name}` に値を渡すだけにする。入力はポートとして、形と意味で宣言する。
- 持ち主に求めること: なし。持ち主の 2026-10-19 の決め・業界の定石・リポジトリの事実で決まらない物は残らなかった。自分で決めた事と根拠は 13 節。1 節の変更の種類の割り当ては履歴の分類から作り、1.3 で代表の commit 15 件を新しい形の上で歩かせて（その commit の変更を新しい形に当てたら、どこを触るかを紙の上で辿って数えて）確かめた（訳なく散った〔形の上の訳が無いのに触る所が 2 か所以上に分かれた〕9 件から、形を 8 か所直した）。
- 読む人: block と graph を作る・直す実装の役と、block の設計書の書き手。型を引く正本として読む（block ごとの細目は各設計書）。

この文書の中の語（初出の物だけ。#763 の対訳に沿って英語の語はそのまま書く）:

- block: 観点 1 つ分のノードのまとまり。1 本の Archon の workflow（1 フォルダ・YAML 1 本）で、中に `include:` を持たない（`workflow:` は自分の YAML を子の run として起こす時だけ。fix が直しの組ごとに使う）。単独の run としても、ほかの workflow から `include:` されても動く。
- graph: block を `include:` でつなぐ workflow。line（メイングラフ）・chain（周の鎖）・judge と eyes のまとめ・入口の workflow。graph は配線と流れの決め（どの block をいつ回すか・承認ノード・往復の止め・深さの表・無人の方針・まとめの判定）だけを持ち、観点の判断と計算（測る・照らす・AI の役）は block に置く。
- port: block の入力（YAML の `inputs:`）と出力（`returns:` が名指すノードの `output_format`）。形（下の 4 節の form）と意味で述べる。
- place: block が自分のファイルを書く run directory の中のフォルダ。block ごと・include ごとに分かれる（4.4）。
- prep: AI のノードの直前の script のノード。材料を集め、md に値を入れて指示を組む。
- accept: AI のノードの直後の script のノード。返答を validation し、通さなければ却下の理由を返す。
- 古いサブグラフ: 組み込みの前の `workflows/<名>/` の 11 本（line・chain と 9 本）。組み込みで消した。この文書の「今の」は、組み込みの前の形を指す（作り直しの元として書いた所）。
- `blocks/`: 作り直しの間の 2 つ目の pack の置き場。組み込みで `workflows/` に入れ替えた（11.3 の 4）。2 章から 9 章は入れ替えの後のパス（`workflows/<block>/`）で書き、1.3・11 章・13 章の記録はその時の名のまま残す。
- 元の works: `~/src/claude-plugins/works/`。このリポジトリの前の形の修正の工場（raiki61/claude-plugins の `works/`。根の README の「今の works」と同じ物）で、工場の移植元。参照するだけ（作り直しの目標ではない）。
- graphloops: `~/src/claude-plugins/graphloops/`。工場の形の元（`prompts/review-loop/p*.md` がノードごとに 1 本、`blocks/review-loop/<名>/block.json` と `exit.schema.json` が差し替えられる block）。
- Archon の源: `~/.local/state/works-factory/archon-src/d97d00ef…/`（`factory/pack.json` が止めた版）。以下 `A/` と書く。
- pack: Archon が workflow を読む置き場のフォルダ 1 つ（3 節）。
- 柵: `tests/layers/` の、置き場・名前・層の決まりを縛る CI の検査（layer check）。
- 止めた Archon: `factory/pack.json` が止めた版の Archon の源。工場が頼る振る舞いの記録は [archon.md](archon.md)。
- 埋め: Archon に無い物を外から補う部品（polyfill。`workflows/.shared/` の `fence.py`・`childsweep.py`・`child_pointer.py`・`skip_value.py`。名簿は `docs/polyfills.md`）。
- E1〜E22: AGENTS.md の決まりの番号（置き場の表は根の `AGENTS.md` の「決まりの置き場」）。K の番号は今の落とし穴の一覧（`docs/plans/2026-10-13-capabilities/pitfalls.md`）。
- 持ち主: リポジトリの owner（決めを下す人）。持ち主の決めは `docs/owner-decisions.md` に名（`overnight-speed` など）で書く。10 節で仕組みを担う block は「担う block」と書く。
- 起動の殻: 人が打つ入口 `bin/works-factory`（中身は `bin/_lib/`）。認証と隔離を整えて Archon を起こす。
- 始めの記録: line が run の頭に 1 度書く記録（[line.md](line.md) の語）。block はこれを読まない（4.3）。
- 段: run の頭の深さ 3 つ（軽量・標準・重厚）。上げ直し: 1 回目の修正の後に、修正の結果に出た印（止めた単位・修正役の異議・案の直しなど。line.md 5.3 の「上げる信号」）を見て、単位（判定が出した、根本の欠陥 1 つ分の直す単位）の深さを標準へ上げ直すこと（line が 1 回だけ持つ）。表は line.md の 5 節と 16 節。
- 再審: 修正役が判定に異議を出した時に、判定を考え直すこと（考え直す役 `rejudge` は diagnose の block の中）。
- 名の住処: 組み込みの前の `lib/` のモジュールのうち、1 つのサブグラフが自分の出力の隣に書くファイルの名（例 `world-judge.json`）の字をただ 1 つ持つ物。ほかのサブグラフはその名でファイルを開いていた（9 節で消す）。
- 守りのファイルと当たり: 守りのファイルは、人の確かめなしに変えてはならないパス（工場の `lib/protected.json` と対象の `.works-protected.json` が名指す）。当たりは、差分がそれに触れた件で、merge が差分を封じる（hash を取って固定する）時に数える。
- eyes: 独立の目（直しを作った AI と別の AI が観点 R1〜R4 で直しを確かめる段）をまとめる graph。

## 1 根拠から導く形（変更の種類と、変更が閉じる 1 か所）

型の決め方は、変わりやすい決めを 1 つずつ 1 つのモジュールに隠す情報隠蔽に従う（D. L. Parnas, "On the Criteria To Be Used in Decomposing Systems into Modules", Communications of the ACM 15(12), 1972, pp. 1053–1058）。よく起きる変更の種類が 1 か所で閉じれば、その分け方は合っている。散らばるなら分け方を直す。

材料は履歴の分類 `~/.cache/works-self/tmp/change-kinds.md`（別の作業が書いた。origin/main の first-parent 301 commit のうち 261 件を 17 の種類に手で分け、触ったファイル・lib のモジュール・サブグラフの数を数えた）。全体の中央値は約 10 ファイル。

### 1.1 種類ごとの数と、今の散らばり（中央値）

- B script・lib の不具合直し 34 件: 6 ファイル・1.5 モジュール・1 サブグラフ（例 `1148d56f`）
- O 1 か所への寄せ 33 件: 16 ファイル・4 モジュール。45% が柵も直す（例 `174defc0`・`3139aa8e`）
- C 較正・ベンチ 25 件: 6 ファイル・lib に触らない
- X 文書だけ 18 件: 1 ファイル
- G 柵・層・地図の保守 16 件: 5 ファイル。87% が柵（例 `294b2fe5`）
- P port（入出力の欄）15 件: 23 ファイル・7 モジュール・2 サブグラフ（例 `85912339`・`3adce5e5`）
- A 受け付け・検査 15 件: 11 ファイル・4 モジュール・1 サブグラフ（例 `2d9ce66b`）
- W 元の能力の戻しと縛り 15 件: 15 ファイル。60% が柵（例 `45b08032`）
- S sandbox・環境の隔離 14 件: 12.5 ファイル（例 `564a99d6`）
- N 新しい役・観点・機能 12 件: 24 ファイル・4 モジュール・3 サブグラフ（例 `a30d2566`）
- V Archon の境・版 12 件: 15.5 ファイル・1.5 サブグラフ（例 `8bb804fd`）
- U 無人・承認ノードの方針 12 件: 17.5 ファイル・4 モジュール（例 `2a21ac3b`）
- I 指示書の文 10 件: 17 ファイル・2.5 モジュール・2 サブグラフ（例 `e33d9e34`）
- R 報告・人向けの文 9 件: 14 ファイル・4 モジュール・2 サブグラフ（例 `427b679c`）
- D 深さ・往復の制御 9 件: 47 ファイル・9 モジュール・4 サブグラフ。いちばん散る（例 `d0b086a2`・`2351c7a4`）
- T 試験だけ 6 件・F run directory のファイルと pointer 6 件（21 ファイル）

一緒に変わる組の上位（40 ファイル以下の commit）: `lib/fixboard.py` と fix の scripts が 23 回（74%）、`lib/runreport.py` と line の scripts が 17 回、`lib/gatemarks.py` と `lib/runreport.py` が 15 回、`lib/boardview.py`・`lib/planfile.py`・`lib/planblk.py` が互いに 55% 前後。`docs/design.md` は全体の 23% の commit で一緒に変わる。

読み取り: 件数の 29%（O・G・W・V の 76 件）は機能でなく、決めの持ち主の整理・柵の保守・能力の戻しに使われている。今の形が決めの置き場を散らしている印。

### 1.2 種類ごとに、新しい形で閉じる 1 か所

- B 不具合直し → その block の `src/` と、その block の試験。fix の scripts と `lib/fixboard.py` の連動（74%）は、両方が fix の block の中に入って 1 か所になる。fix が直しの組ごとに自分を子の run として起こす形と、組の中の TDD の loop も fix の中に置くので（8.3）、組の子の結果の受け渡しも fix の中で閉じる。
- A 受け付けに確かめを足す → その block の `src/` の validation と、同じ block の `prompts/<node-id>.md` の 1 段落。どちらも 1 つの block のフォルダの中。
- I 指示の文を直す → その node の `prompts/<node-id>.md` 1 本。同じ block の 2 つ以上の node が使う文は、その block の `prompts/parts/<name>.md` 1 本。2 つ以上の block が使う文は `workflows/.shared/prompts/<name>.md` 1 本。
- N 観点を足す → 新しい block のフォルダ 1 つ。graph の配線の数行と、報告は block の出力の `report` の欄で済む（report の block は触らない）。
- P 入力を足す → 受け手の block の `inputs:` と `schemas/`（1 つの block）。graph の `with:` の 1 行は配線として必ず要る（ブロックはほかの block を名指さない、という持ち主の決めの代わりに払う物）。作り手は出力の欄を足すだけで、ほかの読み手の数だけ入力が増える形（drift-audit の 4 節）は、作り手ごとに出力を pointer 1 つで渡すことで止める。2 つ以上の block が読む行の形（欄・語・行を読む述語）は作り手の出力ごとに `lib/` の 1 モジュール（例 `worldmark`）に置くので、行の語を足す変更は作り手の block とそのモジュールの 2 か所で閉じる（4.1）。
- R 報告に 1 行足す → 事実を持つ block の `report` の欄だけ。`lib/runreport.py` が `gatemarks`・`fixboard`・`judge_accept`・`boardview` と連動して変わる形は、この置き方で無くなる。
- U 承認ノードと無人の方針 → line（graph）の `src/` だけ。修正の前と後の承認ノードを持つのは line だけなので（例外は仕様の承認ノードで、spec の block の中に置く。8.1）、方針の決め（今の `lib/gatepolicy.py`・`lib/gatemarks.py` の決めの部分）も line に置く。block は承認ノードの材料になる事実（欠陥・定石からの外れ・問い）を出力で返し、承認ノードを通すかは決めない。人へ回す問いの語と選び方（今の `gatemarks` の `ASKING`・`asks_human`）は diagnose も使う問いの行の形なので、line でなく `lib/` の行の形のモジュールに置く（4.1）。
- D 深さと往復の制御 → 表を 2 つに分ける。未知の種類 → 段（`lib/headdepth.py` の `UNKNOWNS`）は、未知の種類を読む diagnose・plan も使うので `lib/headdepth` に置き、その意味は head-depth の役の md が説明する。段 → 回す物（今の `lib/depth.py` の `TIERS`）・単位ごとの深さ・修正の後の上げ直し（`depth`・`latedepth`）は line の `src/`。block は「深さ」を知らず、line が表から引いた真偽や一覧（例 plan-review の `tree`・fix の `skip_rerun`）を port で受け、verify・delta-review・r1〜r4 を回すかは line の `when:` が決める。fix の中の上げ直し（今の `fixboard.redepth`）は無くし、line が fix と delta-review の間で 1 回だけ上げ直す。往復の記録と止め時（今の `lib/converge.py` の記録と止めの部分）は、往復の loop を持つ line に置き、plan-review には前の周を port `prior` で渡す。モデルと effort の群（`d0b086a2` の形）は、群の表 `lib/launchgroups.py` 1 つで、node の YAML は群の名を書くだけ（今のまま）。
- O 1 か所への寄せ → 種類そのものが減る。1 つの block だけの決めは block の `src/` に初めから 1 つ在り、2 つ以上の block の決めは `lib/` の 1 モジュールに置く（2 節の 4）。
- G 柵の保守・F run directory のファイル名 → 種類そのものが減る。名の住処と名の字の柵は消え（9 節）、形の検査は `tests/layers/test_block_shape.py` 1 本の yes/no（7 節）。place のファイルの名は block の `src/` だけが持つ。
- W 能力の戻しと縛り → その能力を持つ block の振る舞いの試験。能力の棚卸しの表（`docs/nodes.json`・`docs/works-parity.md`）と、それを照らす柵は消す（10 節の keep-essence の割り当てで替える）。
- `docs/design.md` の連動 → block ごとの設計書 `docs/design/<block>.md` 1 本。block の外の文書（根の README・`docs/owner-decisions.md`・`docs/polyfills.md`）は block・port・コマンド・環境変数の名までを書き、関数の名を書かない（7.2）ので、block の中の作り替えでは動かない。
- 1 か所に閉じない物（残る散らばり）:
  - S sandbox の node の鍵と V の全 node の鍵の足し（例 `8bb804fd` の retry）: Archon は鍵を node ごとに YAML に書くので、全部の block の YAML に及ぶ。7.1 の yes/no の検査が付け忘れを止める。共通の値を 1 か所に置く口は Archon に無い（（未確認）。Archon の workflow の頭の既定値で済む鍵があれば寄せる）。
  - C 較正は `tests/calibration/` の中で、T 試験だけの変更は `tests/` の中で閉じていて、形に関わらない。
  - V の版の上げそのものは `factory/pack.json` の版と `workflows/.shared/`・埋め・`tests/shared/test_archon_contract.py` で閉じる。block の中には届かない。

### 1.3 変更の歩かせ

1.1 の代表の commit を、新しい形の上で紙の上で歩かせ、触る所を数えた（ATAM の変更容易性のシナリオの形。R. Kazman, M. Klein, P. Clements, "ATAM: Method for Architecture Evaluation", CMU/SEI-2000-TR-004, Software Engineering Institute, 2000）。

- 歩かせた物: `change-kinds.md` の 5 節の 12 件と、D の 3 件（`d0b086a2`・`2351c7a4` と、D でいちばん大きい `9407b441`）の 15 件。中身は `git -C ~/src/works-factory show` の差分で確かめた。別々の直しを 1 つに束ねた commit（squash merge）は、直しごとに分けて歩かせた。
- 場所の数え方: 場所 1 つは、block 1 つ（`blocks/<block>/`・`tests/blocks/<block>/`・`docs/design/<block>.md` の組。11.1 で PR 1 本が触る範囲）・graph 1 つ（同じ組）・`lib/` のモジュール 1 つ・埋め 1 つ・起動の殻 `bin/_lib/`・block の外の文書 1 本（根の README・`docs/owner-decisions.md`・`docs/polyfills.md`）・`tests/calibration/`。試験は、試す物と同じ場所に数える。
- 今の数も同じ数え方（lib のモジュール・サブグラフ・`bin/`・柵〔`tests/layers/` と `docs/concepts.json`・`docs/nodes.json` などの表〕・文書）。
- 結果: 15 件のうち、1 か所で閉じる 6 件・2 か所（訳あり）8 件・散る 1 件（`d0b086a2`。Archon がモデルの鍵をノードごとに読むことによる 1 回きりの書き換えで、形の問題ではない）。これは下の「形の直し」8 つを当てた後の数。当てる前の形では 9 件が訳なく散った。

| commit | 種類 | 今（ファイル・場所） | 新しい形（場所） | 判定 |
|---|---|---|---|---|
| `1148d56f` | B | 6・3 | 1 | 1 か所 |
| `174defc0` | O | 16・8 | 直し 4 つが各 1 | 1 か所ずつ |
| `2d9ce66b` | A | 12・6 | 1 | 1 か所 |
| `3adce5e5` | P | 24・5 | 直し 2 つが各 2 | 2 か所 |
| `2a21ac3b` | U | 16・9 | 1 | 1 か所 |
| `a30d2566` | N | 25・8 | 2 | 2 か所 |
| `e33d9e34` | I | 16・8 | 2 | 2 か所 |
| `564a99d6` | S | 13・9 | 2 と文書 2 | 2 か所 |
| `45b08032` | W | 15・8 | 能力 22 行が各 1 | 1 か所ずつ |
| `294b2fe5` | G | 4・1 | 1 | 1 か所 |
| `8a7ed1ad` | B（bin） | 6・4 | 1 と文書 1 | 2 か所 |
| `dcc6909d` | C | 6・2 | 1 と文書 1 | 2 か所（形の外） |
| `d0b086a2` | D | 47・19 | 4 と全 block の YAML | 散る（訳あり） |
| `2351c7a4` | D | 32・17 | 直し 3 つが 2・2・1 | 2 か所 |
| `9407b441` | D | 100・21 | 直し 3 つが 2・2・1 | 2 か所 |

#### 歩かせの中身

1. `1148d56f`（B）受け付けていない組の子は許したテストを親へ運ばず、join と collect が同じ 1 つの欄から読む。
   - 新しい形で触る所: fix の `src/`（今の `fixboard.group_result`）・`scripts/group_end.py`・`scripts/join.py`・`tests/blocks/fix/`・`docs/design/fix.md`。
   - 判定: 1 か所。組の子の結果（`result.json`）は、fix が自分を子の run として起こす時の fix の中の受け渡し。当てる前の形（7.1 の 6 が block の `workflow:` を禁じ、tdd を別の block にした）では、組の子と親を別の block と graph に割るしかなく、`result.json` が block をまたぐ port になって 2〜3 か所に散った（形の直し 1・2）。
2. `174defc0`（O）別々の 4 つの寄せの束。
   - 承認済みの修正案の項目の読み口を 1 つに（#583）: fix の `src/` だけ（`factchecks` も `fixboard` も fix へ入る）。1 か所。
   - 人へ回す問いの選び方を 1 つに（#604）: 問いの行の形のモジュール 1 つ（今の `gatemarks` の問いの語と `asks_human`。形の直し 4）。diagnose の受け付けと line の承認ノードはそれを呼ぶだけ。1 か所。当てる前の形は `gatemarks` を丸ごと line の `src/` へ移していたので、diagnose が line の中身を import するか写しを持つかになった（散る）。
   - ベンチの bwrap の版の照らし（#596）: `tests/calibration/` だけ。1 か所。
   - 柵の名指しの語の当て方（#556）: 名指しの柵（`tests/layers/scan.py` の E2・E4）は 9.4 で消えるので、この直しは起きない。埋めの名簿の節の移しは `docs/polyfills.md` 1 本。
3. `2d9ce66b`（A）修正役の事前の確かめと受け付けを同じ木から読ませ、組の結果の読みの崩れを直す。
   - 新しい形で触る所: fix の `src/`（修正役が変え始めた木の読み口 `fixer_head`・組の子の結果の読み口・テストのファイルの要素の決まり `test_file`）・`scripts/`（fix_accept・fix_ruled_accept・join）・試験。
   - 起きなくなる分: E5 の柵の逆向きの照らし（lib が `INPUTS_{…}` の名を組む並び）は、4.2 で名を組んで読まないので要らない（Archon の `scanEnvironmentReads` と `test_input_reads.py` が照らす）。`workflows/AGENTS.md` の文も動かない。
   - 判定: 1 か所。テストのファイルの要素の決まりは、TDD の loop（書き手）と組の結果の読み（読み手）が共に使う。tdd を別の block にした形では、これが 2 つの block の間の port の形になり、lib のモジュールが 1 つ増えた（形の直し 2）。
4. `3adce5e5`（P）2 つの直しの束。
   - merge が読まない入力 `diff` をやめる: merge の block（`inputs:` と筋書き）と line（`with:` の 1 行）。2 か所。port を減らすので、受け手と配線の 2 か所は要る。
   - line の終わりに、組の子の作業ツリーの後始末のノードを置く: line（ノード・script・返りの欄 `children`・筋書き）と埋め `childsweep`。2 か所。埋めは Archon の穴を補う共通の部品なので、line と分かれるのが正しい。
   - 気づき: 今の `childsweep.reader_of` は fix の中のノードの名 `join` を持つ。新しい形では block の外が block の中の名を持つことになるので、「子を起こしたノードと同じ include の中のノードが全部 completed になるまで消さない」にする。名を持たずに済み、今より消すのが遅くなるだけで、閉じた側に倒れる。
   - 起きなくなる分: `docs/nodes.json` の行・層の網の許しの行・`test_unread_named.py` の表の行。
5. `2a21ac3b`（U）無人の run が承認ノードを推しで進むか止まるかの決めを 1 つの口に寄せる。
   - 新しい形で触る所: line の `src/`（今の `gatepolicy` と `gatemarks` の承認ノードの決めの部分と、計画の往復の記録の「上限で止めたか」。往復の記録は line が持つ。形の直し 6）・`scripts/ask_before_fix.py`・`ask_replan.py`・試験・`docs/design/line.md`。
   - 起きなくなる分: 住処の柵（`docs/concepts.json`）・`docs/concepts.md`・`docs/works-parity.md`。`docs/owner-decisions.md` の「当て方」の行は関数の名を書いていたので動いたが、block の外の文書は block と port の名までにする（形の直し 8）ので動かない。
   - 判定: 1 か所。
6. `a30d2566`（N）組を合わせて赤になった組を合わせ役が直し、直せなければ裁定へ回す（裁定の語 `rejudge` を足す）。
   - 新しい形で触る所: fix の block（`src/` の clash・ruling と申し出の積み方・`scripts/` の clash_prep・clash_accept・collect・join・fix_ruled_prep・YAML の 2 つの loop・`prompts/` の合わせ役の md と block の中の共通の断片 `prompts/parts/`〔裁定の拠り所の決まり。形の直し 3〕・筋書き・試験・fix の出力の `report` の欄の行）と、食い違いの申し出の行の形のモジュール（今の `conflict` の裁定の語 `DECISIONS`・出どころ `SOURCES`・人に諮る行の選び `asked_rows`・数え `counts_of`。形の直し 4）。
   - line は動かない: 裁定の文は修正の出力の `objection` に入り、今もある再審の道に乗る。
   - 起きなくなる分: AI のノードの数の歯止め・`prompt_contracts.json`・`copied_rewrites.json`・`docs/nodes.json`・`docs/concepts.md`。
   - 判定: 2 か所（作り手の block と、読み手が共に読む行の形）。新しい語を読み手（line の最後の承認ノード・report）が知る必要があるので、行の形のモジュールが動くのは正しい。
7. `e33d9e34`（I）修正役の指示に、受け付けが照らすテストの名を貼る。
   - 新しい形で触る所: fix の `prompts/` の修正役の md に節を 1 つ（決まった文と、足してよいテスト・本体を変えてよいテスト・その範囲・凍ったテストの差し込み口）、fix の `src/` に値の関数（受け付けと prep が同じ関数を呼ぶ）、試験。もう 1 か所は、fix と delta-review が共に使う `lib/recount` から、書いた指しの照らし `ref_problems` を切り出す所。
   - 起きなくなる分: 指示の節の文を lib の `planrange.tests_text` が組む形（文は md へ）・`copied_rewrites.json`。今 lib の 7 モジュールに散ったのは、指示の文と値と受け付けが lib の別々のモジュールに在ったため。
   - 判定: 2 か所（block と、共通の照らしのモジュール）。当てる前の形では、fix の node どうしが共に使う決まりの文（今の `fix-rules/common.md`・`brief.md`）を `blocks/.shared/prompts/` に置くしかなく、fix だけの直しが pack 全体の共通の置き場に及んだ（形の直し 3）。
8. `564a99d6`（S）読むだけの役の claude を起こす直前に、共有の `.git` と全部の作業ツリーの根まで書き込みを塞ぐ。
   - 新しい形で触る所: `bin/_lib/`（launcher・hostgh。包みを置く殻）・埋め `workflows/.shared/fence.py`・`docs/polyfills.md`（埋めの名簿）・根の `README.md`（環境変数 `CLAUDE_BIN_PATH` で殻が止まる条件）。
   - 起きなくなる分: judge と test-gate の YAML のコメント（block は埋めの振る舞いを書かない）・`workflows/AGENTS.md` の E7 の文（案内は決まりとパスだけ）・層の網の行。
   - 判定: 2 か所（殻と埋め）と文書 2 本。block には届かない。文書は利用者の使い方と埋めの名簿で、リポジトリの決まりが求める物。
9. `45b08032`（W）独立の目の能力 22 行を、名前つきの試験で縛る。
   - 新しい形で触る所: 行ごとに、その能力を持つ block の試験 1 か所。指示の文の行（E7・E12・E13・E38）は r1・r2 の md の比べ、port の行（地図は R1 と R3 だけ E21・方針は R1・R3・R4 だけ E25）は r1〜r4 の `inputs:` の yes/no、支度の出力の行（E14・E20・E23・E43・E65・E70）は各 r の prep の試験、直した後の実測の行（E68・E74）は structure の block（形の直し 7）、4 つの目が並んで走る・軽い run でも走る（E9・E71）は eyes の graph、escalate で最後の承認ノードが開く（E36）は line。
   - 起きなくなる分: 能力の棚卸しの表（`docs/nodes.json`・`docs/plans/2026-10-13-capabilities/` の 5 本）と、指示書の写しの台帳（`tests/workflows/copied.py`）。
   - 判定: 行ごとに 1 か所。commit 全体は 7 か所に触るが、22 行をまとめて縛った棚卸しだからで、形の問題ではない。当てる前の形では、直した後の実測 `stage_b` を eyes の graph の `src/` に置いていた（9.2）ので graph が計算を持ち、E68・E74 が graph に来た（形の直し 7）。
10. `294b2fe5`（G）修正の後の深さの上げ直しの数えの照らしを締める。
    - 新しい形で触る所: line の試験と、line の e2e の照らしの表 `tests/e2e/evidence.json` の書き手の行。上げ直しは line だけが持つ（形の直し 5）。
    - 起きなくなる分: 住処の柵の行（`docs/concepts.json`・`test_concept_fences.py`）。「fix と line が同じ控えを同じ決まりで読む」試験は、読み手が line 1 つになるので要らない。
    - 判定: 1 か所。当てる前の形では、fix の中の上げ直し（今の `fixboard.redepth`。差分の審査を省くかを決める）と line の上げ直しが `latedepth` を共に使うのに、9.2 で `latedepth` を line の `src/` へ移していたので、fix が line の中身を読むか写しを持つかになった（形の直し 5）。
11. `8a7ed1ad`（B、bin）封じた後のノードが落ちた run でも、`bin/apply` が封じのノードの出力から hash を照らして当てる。
    - 新しい形で触る所: `bin/_lib/apply.py`（と `tests/bin/`・Archon の出来事の名を照らす `tests/shared/test_archon_contract.py`）と根の `README.md`（旗 `--allow-failed`・`--allow-stopped`）。
    - 起きなくなる分: `docs/works-parity.md`。
    - 判定: 2 か所（殻と、利用者の使い方の文書）。`bin/apply` は line の受け皿のノードの id（`merge-seal-out` など）を名指すが、殻は line を起こす口なので line の名を知るのは正しい。block の中の名は知らない（今と同じ）。
12. `dcc6909d`（C）ベンチの sandbox の確かめを本物の claude に踏ませる。
    - 新しい形で触る所: `tests/calibration/`（と `tests/bin/sandbox_probe.py`・埋め fence の試験）と `docs/owner-decisions.md`（版の照らしを消すという決めの変更）。
    - 判定: 形の外で今と同じ 2 か所。block にも lib にも届かない。
13. `d0b086a2`（D）AI のノードのモデルと effort を群に分け、起動の時に群ごとに付け替える。
    - 新しい形で触る所: 群の表 `lib/launchgroups.py`・`bin/_lib/`（launcher・place。run 1 本分の設定の層）・head-depth の block（群を選ぶ問いの節と受け付け）・line（報告の「模型」の行。事実は始めの記録に在る）・全部の block の YAML の AI のノード（`model:` を群の名にする 1 回きりの書き換え）・`docs/owner-decisions.md`・`docs/polyfills.md`。
    - 判定: 散る。ただし訳がある: Archon はモデルの鍵をノードごとに YAML で読み（1.2 の「残る散らばり」）、書き換えは群を入れる時の 1 回だけ。入れた後の典型の変更（群のモデルを替える・ノードの群を替える）は、表 1 か所か、その block の YAML 1 か所で閉じる。付け忘れは、7.1 と一緒に続ける AI のノードの印の yes/no の検査が止める。
14. `2351c7a4`（D）事前審査の往復を、回数でなく開いた block の減り方で止める。3 つの直しの束。
    - 止め方と安全の上限、1 回目に出た所見の割合を報告に: line の `src/`（往復の記録・止め・上限。形の直し 6）と plan-review の block（2 往復目からの新しい穴の出自 missed・introduced・rephrased を申告させる md の節・受け付け・出力の欄）。2 か所（作り手が欄を足し、往復を持つ line が読む）。上限の数 `round_limit` を plan-review へ渡す配線は要らない（上限で止めたかは line が決める）。
    - 消す名の波及を審査の前に数える: plan の block（`src/` の ripple と、md の「消す名を名指すファイルは allowed_paths に入れよ」）と、修正案の項目の行の形 `lib/planmarks`（欄 `removes` と、名の読み方の決まり。fix の範囲の照らしも読む）。2 か所。
    - 持ち主の決めの補足: `docs/owner-decisions.md` 1 本。
    - 起きなくなる分: `gatemarks.PLAN_GATE_FILE` のような、2 つのモジュールが同じファイルの名を持つための寄せ（place のファイルの名は block の `src/` だけが持つ）・柵の許しの行・筋書きの注記の許しの行。
15. `9407b441`（D）run の深さを 3 段にし、重厚で判定の裏取りと木の事前審査を足す。3 つの直しの束。
    - 段を 1 つ足す: `lib/headdepth`（段の語と未知の種類 → 段の表。head-depth・line・diagnose・plan が共に読む）と head-depth の block（md の段の意味の文）と line（段 → 回す物の表）。
    - 重厚で木の事前審査を足す: plan-review の block の port `tree`（初めて足す時だけ）と line の表の 1 行。2 か所。その後、どの段で木にするかを替えるのは line の表 1 か所。判定の裏取りは verify の block を line が `when:` で回すかだけなので、line 1 か所。
    - 深さで事前審査を飛ばす道を外す: line の `when:` 1 か所。
    - 今との違い: 今の 100 ファイルのうち約 60 は筋書き（line・plan-review・judge）で、深さの語を始めの記録や返りに持つため。新しい形では block の筋書きは深さを知らず（port の真偽だけ）、動くのは line の筋書きだけ。

#### 共変更の組（change-kinds.md の 6 節）のうち、block をまたぐ物

- `lib/runreport.py` と line の scripts（51%）・line の YAML（54%）、`lib/gatemarks.py` と `lib/runreport.py`（62%）・line の scripts（50%）: 承認ノードの決めと、その報告の行（line の出力の `report` の欄）が line に入る。line 1 か所で一緒に変わる。
- `lib/fixboard.py`・`lib/judge_accept.py`・`lib/boardview.py` と `lib/runreport.py`（35〜41%）: 報告の行は事実を持つ block が組むので、fix・diagnose・plan-review の 1 か所ずつになり、`runreport` は動かない。
- `lib/fixboard.py` と fix の scripts（74%）、`lib/runreport.py` と report の scripts（75%）: どちらも 1 つの block の中。またがない。
- `lib/boardview.py`・`lib/planfile.py`・`lib/planblk.py`（互いに 55% 前後）: plan と plan-review の間の受け渡し（修正案の項目の形と、往復の控え）が 3 つに割れていた物。新しい形では、項目の形は `lib/planmarks` 1 つ、往復の記録は line、前の周の案と指摘は plan-review の port `prior`（形の直し 6）。項目の欄を足す変更は、作り手 plan・形 `planmarks`・読み手 plan-review の 3 か所まで動きうる。2 つの block の間の約束を変える変更なので、両側と約束の 1 か所が動くのは避けられない最小（欄が語や述語を持たない時は、形のモジュールは動かず 2 か所）。
- `bin/_lib` と `lib/runreport.py`（29%）: 殻の事実（群・利用者の環境）は始めの記録で line に入り、line の `report` の欄に載る。殻と line の 2 か所で、層が違うので正しい。
- `lib/boardview.py` と `lib/gatemarks.py`（41%）: 事前審査の穴・外れ・止まった時の推し（plan-review の出力）と、承認ノードの決め（line）。出力の欄が変われば 2 か所（port の変更）、承認ノードの方針だけなら line 1 か所。
- 文書との組: `docs/design.md`（23%）は block ごとの設計書に割れ、その block の場所に入る。`docs/works-parity.md` と `docs/nodes.json` は消した（#765）。`workflows/AGENTS.md` と `tests/layers/`（73%）は、新しい yes/no の決まりを足す時だけ 2 か所（決まりの 1 行と検査。持ち主の決め `rules-tests-design-apart` で分けて置く）。

#### 多い種類と、いちばん散る種類

- B 不具合直し（34 件）: 歩かせた 2 件とも 1 か所（fix の block、起動の殻）。block の中の直しは block の中で閉じる。
- O 1 か所への寄せ（33 件）: 歩かせた束の 4 つの直しは各 1 か所。2 つ以上の block が共に使う決めは、初めから `lib/` の 1 モジュール（行の形のモジュールを含む。形の直し 4）に在るので、寄せる直しそのものが減る。
- D 深さ・往復の制御（中央値 47 ファイル）: 典型の変更は 1 か所で閉じる。未知の種類 → 段（`ad88e48a`・`f7d6e81b` の形）は head-depth の block、段 → 回す物（`3e7287dd`・`1aa7cb83` の形）と、修正の後の上げ直し・往復の止め（`2351c7a4`・`0ed6ab46` の形）は line、群のモデル（`d0b086a2` の後）は `lib/launchgroups.py`。2 か所になるのは、段の語を足す時（head-depth と line）と、block に切り替えの port を初めて足す時だけ。

#### 形の直し（歩かせが訳なく散った所。13 節にも書いた）

1. block の YAML の `workflow:` を、自分の YAML を子の run として起こす形にだけ許す（7.1 の 6）。訳: fix は直しの組ごとに自分を子として起こし（#765 の本文が手本として残すと書いた形）、組の子の結果は fix の中の受け渡し。禁じると、組の子と親を別の block と graph に割ることになり、`result.json` が block をまたぐ port になる（歩かせ 1・3）。ほかの block を名指さないので、憲法の 3 に触れない。
2. tdd を独立の block にせず、fix の組の子の run の中の loop のままにする（8.3）。訳: block は `include:` を持てないので、組ごとの TDD の loop を別の block にすると fix から呼べない。テストの許しの「1 本」（keep-essence の 3）も、割れば 2 つの block の間の port になる（10 節が崩れる余地と書いた所）。TDD だけを単独で回すのは、今も単独で回る fix の組 1 つの形（`mode` が `group`）で足りる。
3. 同じ block の 2 つ以上の node が使う指示の断片は、その block の `prompts/parts/<name>.md` に置き、`{part:<name>}` で差し込む（3 節・5.1）。`workflows/.shared/prompts/` は 2 つ以上の block が使う物だけ。訳: fix の 4 つの役（修正役・TDD の役・裁定役・合わせ役）だけが使う決まり（今の `fix-rules/brief.md`・`principles.md`）を pack の共通の置き場に置くと、fix だけの直しが共通の置き場に及ぶ（歩かせ 6・7）。fix と delta-review の 2 つが使う書き手の決まり（今の `fix-rules/common.md`）は、共通の断片 `writer-rules` に置く（`docs/design/integration.md` の 4.4-E）。憲法の 4（1 つの block だけが使う物はその block に）と同じ決め方。
4. 2 つ以上の block が読む出力の行の形（欄の名・語・行を読む述語）は、作り手の出力ごとに `lib/` の 1 モジュールに置く（4.1。2 節の 4 の当てはめ）。手本は今の `worldmark`（world.md の 1.5）。当たる物: 問いの行（今の `gatemarks` の問いの語と `asks_human`。diagnose が作り、line が読む）・食い違いの申し出の行（今の `conflict` の語と読み口。fix が作り、plan・line・report が読む）・修正案の項目（`planmarks`）・頭の深さの出力（`headdepth` の段の語と控えの読み）。`gatemarks` と `conflict` は、行の形の部分を KEEP にし、決めの部分を line と fix へ割る（9.2・9.3）。訳: `gatemarks` を丸ごと line の `src/` に移すと、diagnose が line の中身を import するか写しを持つことになる（歩かせ 2・6）。
5. 深さの表を 2 つに割る（1.2 の D・8.1・8.3・8.7）。未知の種類 → 段（`headdepth.UNKNOWNS`）は `lib/headdepth`（diagnose・plan も読む）、段 → 回す物（今の `depth.TIERS`）・単位ごとの深さ・修正の後の上げ直し（`depth`・`latedepth`）は line。fix の中の上げ直し（今の `fixboard.redepth`。差分の審査を省くかの決め）は無くし、line が fix と delta-review の間で 1 回だけ上げ直して、delta-review を `when:` で回すか決める。fix は、緑の後の試験の走らせ直しを省く単位の一覧を port `skip_rerun` で受ける。訳: 上げ直しの読み手が fix と line の 2 つ在ると `latedepth` を line に置けず、2 つが同じ決まりで読むことを縛る試験（`294b2fe5`）が要り続ける。delta-review が fix の外の block になったので、決める所を line 1 つにできる。種類 → 段を head-depth の block の `src/` に置く案は、未知の種類を読む diagnose・plan も表を使うので採らず、`lib/headdepth` に残した（`ad88e48a` は `headdepth.py` と `head-depth.md` を一緒に直した。表を直す時は役の md の段の意味の文も合わせる）。
6. 計画の往復の記録（往復ごとの行・止め・安全の上限）は line が持ち、plan-review には前の周の案と指摘を port `prior` で渡す（8.2・8.7）。訳: 2 往復目からの穴の出自・続いた穴・約束の欄が変わった項目（`2351c7a4`・`86e69841`）は前の周を見ないと決まらないのに、plan-review の port に前の周が無かった。上限の数を line から plan-review へ写す配線（今の `round_limit`）も、上限で止めたかを line が決めれば要らない。
7. 直した後の実測（今の `stage_b`）は eyes の graph でなく structure の block に置き、structure は `mode` choice(before|after) を持つ（8.2・9.2）。あわせて graph の語の定義を「配線と流れの決め（どの block をいつ回すか・承認ノード・往復・深さ・無人の方針・まとめの判定）だけを持ち、観点の計算は持たない」に直す（頭の語の説明）。訳: graph の `src/` に計算を置くと、能力の行（`45b08032` の E68・E74）が graph に来る。line が承認ノードと深さの決めを持つ（1.2 の U・D）ことと、元の定義「判断と計算は block に置く」との食い違いも、ここで解いた。
8. block の外の文書（根の README・`docs/owner-decisions.md`・`docs/polyfills.md`）は、block・port・コマンド・環境変数の名までを書き、関数の名を書かない。関数を名指すのは block の設計書 `docs/design/<block>.md` だけ（7.2）。訳: `owner-decisions.md` の「当て方」が `gatemarks.pushed_answer` を名指していたので、中の作り替え（`2a21ac3b`）で block の外の文書が動いた。`docs/design.md` が 23% の commit で動いた理由の一部も同じ。

形の直しの後に当たる commit を歩かせ直した結果が、上の表と各項の判定。歩かせ直しで新しく散った物は無い。

## 2 憲法

置き場: 根の `AGENTS.md` と `workflows/AGENTS.md` の頭に、下の 6 行だけを置く。決まりの細目と試験の仕様は置かない（持ち主の決め `rules-tests-design-apart`）。

1. YAML はつなぐだけ。値はコードが計算し、判断は AI がする（Archon の憲法 `A/.archon/workflow-language-constitution.md` の "YAML coordinates. Code computes. Agents judge."）。
2. AI のノードの指示は、そのノードの md 1 本に英語で書く。Python は指示の文を持たず、md の `{name}` に値を渡す。
3. block は宣言した port だけで受け渡しし、ほかの block を名指さない。つなぐのは graph だけ。
4. 1 つの block だけが使うコードは、その block のフォルダに置く。`lib/` には 2 つ以上の block が使う物だけを置く。
5. どの block も、文とリポジトリだけで単独で回る。block ごとの standalone の fixture で確かめる。
6. 機械の検査は yes/no の形の決まりだけにする。数の上限や許す物の表では縛らず、間違った書き方を API と置き場の形で書けなくする。

## 3 置き場の形

```text
workflows/                       pack（作り直しの間は blocks/ に置き、組み込みで入れ替えた）
├── AGENTS.md                    憲法 6 行と、手本の block（workflows/world/）を写せという案内と、pack の決まり
├── .shared/                     pack の共通の部品（Archon は dot のフォルダを workflow と見ない）
│   ├── AGENTS.md                ports.py と prompt.py の口の一覧・共通の断片と形の名
│   ├── ports.py                 port の読み・place・返り（組み込みの前の境 boundary.py の後継。口の一覧は .shared/AGENTS.md）
│   ├── prompt.py                md に値を入れて指示を組む口（5 節）
│   ├── prompts/<name>.md        2 つ以上の block が使う指示の断片（外への検索の決まり・却下の段落・役の定義・lang の既定の文。名は .shared/AGENTS.md）
│   ├── schemas/<name>.schema.json   2 つ以上の block が使う port の形（json(shared:<name>) で名指す。13 章）
│   └── 埋め（fence.py・childsweep.py・child_pointer.py・skip_value.py。名簿は docs/polyfills.md）
├── <block>/                     block 1 つ（例 world）。名は観点の名
│   ├── works-factory-<block>.yaml   YAML 1 本（グラフの名も同じ。E9）
│   ├── prompts/<node-id>.md     AI の node ごとの指示（英語。Archon は読まない。prep が読む。system prompt は <node-id>.system.md）
│   ├── prompts/parts/<name>.md  同じ block の 2 つ以上の node が使う指示の断片（`{part:<name>}` で差し込む）
│   ├── scripts/<name>.py        script の node（Archon が名で探す）
│   ├── src/                     この block だけが使う Python（package。scripts/ から import する）
│   ├── schemas/<port>.schema.json   json の port の形（4 節）
│   └── fixtures/                筋書き（standalone.stubs.yaml は必ず置く）
└── <graph>/                     graph（line・chain・judge・eyes・policy-check）。形は block と同じ（src/ も持てる）で、include を持てる
tests/blocks/<block>/            block の試験（今の tests/ の層ごとの鏡の形を続ける。フォルダの名は block の名の - を _ にした物。例 tests/blocks/head_depth/。13 章）
docs/design/<block>.md           block の設計書（この型に従う）
```

Archon の源で確かめた読み方（この形はこれに合わせた）:

- workflow は pack のフォルダの直下のフォルダ 1 つに YAML 1 本。YAML の無いフォルダ、dot で始まるフォルダ、`fixtures/` は workflow と見ない。2 本あれば誤り（`A/packages/workflows/src/workflow-discovery.ts` の `loadPackWorkflows`）。だから block は `workflows/` の直下に平らに並べる。入れ子の `workflows/judge/world/` は読まれない。
- `--workflow-source <dir>` の `<dir>/.archon/workflows/` の下の各フォルダが pack になる。workflow のファイルの名は pack をまたいで重なると誤り（同じファイルの `loadPackagedWorkflowsFromDir` の collision）。作り直しの間は新しい block が最後の名（`works-factory-plan` など）を使ったので、古い `workflows/` と同時には読ませず、`blocks/` だけを pack にして回した（殻の環境変数 `WORKS_FACTORY_FOLDER`。組み込みで外した。13 章）。今は起動の殻 `bin/_lib/place.py` の `workflow_source` が `pack.json` の `ours.folder`（`workflows`）を pack にする。
- `command:` の md は `<workflow のフォルダ>/commands/<名>.md` から探す（同じファイルの `resolveCommandContentForScan`）。block の指示の md は Archon に読ませず prep が読むので、`commands/` でなく `prompts/` に置く。生の型（`{name}` が埋まっていない物）が AI に届く道はこれで無くなる。
- 名の script は `<workflow のフォルダ>/scripts/` の 1 段下までの、知った拡張子のファイル全部で、名が重なると誤り（`A/packages/workflows/src/script-discovery.ts` の `MAX_SCRIPT_DISCOVERY_DEPTH = 1` と `discoverPackScripts`）。だから block の中の Python の部品は `scripts/` の下に置かず、`src/` に置く。
- Archon は run の始めに `.archon` の源を丸ごと写し取り、resume もその写しから走る（`A/packages/workflows/src/workflow-source.ts`）。`src/` と `prompts/` は写しに入るが、`lib/` は入らない（`ports.lib_root` は環境変数 `WORKS_FACTORY_ROOT` から辿る）。block だけが使うコードを block に置くと、止まった run の resume が同じコードで続く、という利点もある。
- `include:` は読み込みの時の平らな展開。中の上の段の node の id は `<include の id>__<id>` になり、`returns:` の node が `$<include の id>.output` になる。loop_group の本体の中の `$<id>.output` は改められないので、include の id が block の中の node の id（本体の中の物も）と同じだと、本体の中の字が include の返す node を指してしまう（7.1 の 13）。`inputs:` に無い鍵と、欠けた必須の入力は読み込みの誤り（`A/packages/workflows/src/include-expander.ts` の頭の説明と、憲法の `inputs:` + `returns:` + `with:` の行）。

## 4 port

### 4.1 宣言の形

- 入力は YAML の `inputs:` に書く。Archon が受ける鍵は `required`・`default`・`description` の 3 つだけで、ほかの鍵は警告になる（`A/packages/workflows/src/schemas/workflow.ts` の `workflowInputSpecSchema`）。E1 は警告を許さないので、形は `description` の頭に書く: `<form>: <意味>`。
- form は 5 つ。
  - `text`: 字。空の時の意味を説明に書く。
  - `json(<schema>)`: JSON の値。値そのもの（JSON の字）か、値を入れたファイル（下の 4.2）で渡す。`<schema>` は block の `schemas/` のファイル名。
  - `file`: ファイル 1 つ（中身の形を問わない時）。
  - `flag`: true か false。
  - `choice(a|b|…)`: 決まった語のどれか。
- 出力は `returns:` が名指す node の `output_format`（素の JSON Schema）だけで述べ、写しを持たない（今の E5 と持ち主の決め `io-in-output-format` のまま）。大きい中身はファイルにし、出力には Archon の pointer `{type: archon_artifact, run_id, path}` を入れる（`A/packages/workflows/src/artifact-pointer.ts`。作り手の run の中のファイルだけを指せる）。
- 2 つ以上の block が読む出力の行の形（欄の名・語・行を読む述語）は、作り手の出力ごとに `lib/` の 1 モジュールに置き、作り手は書く時に、読み手は読む時にそれを使う。手本は `worldmark`（world.md の 1.5）。ほかに当たる物は、問いの行（diagnose が作る。今の `gatemarks` の問いの語と `asks_human`）・食い違いの申し出の行（fix が作る。今の `conflict` の語と読み口）・修正案の項目（plan が作る。`planmarks`）・頭の深さの出力（head-depth が作る。`headdepth` の段の語と控えの読み）・前提の実測の行（premises が作る。`kind` の語 `実測`・`仮説`。今は `carry.MEASURED` と `runreport.HYPOTHESIS` に割れている）・目的の出典の語（purpose が作る。`source` の語。今の `judge_accept.PURPOSE_UNKNOWN` の「目的不明」など。independent-design が読む）。欄の型の正本は `output_format` のままで、このモジュールは語の意味と述語を持つ。1 つの block だけが読む行の形は、作り手の block の `src/` に置く。
- どの block の返りにも、`outcome_field:` が名指す欄（block の仕事がうまくいったか）と、欄 `report`（報告に載せる日本語の行の配列）を置く。報告の文は事実を持つ block が組み、report の block は並べて継ぐだけにする。今の `lib/runreport.py` が lib の 43 モジュールを import する集め口になった崩れ（`~/.cache/works-self/tmp/drift-audit.md` の 3 節）を、この形で閉じる。
- block の中の node が落ちても line が先へ進めてよい時は、返りに欄 `optional`（`[{node, bare}]`。node は自分の node の id だけ）を置いて宣言する（無くてよい欄）。line の collect がこの宣言を読み、報告が落ちを分ける（今の `workflows/line/scripts/collect.py` の `optional`）。例は structure と merge の設計書。

### 4.2 文とリポジトリだけで単独に呼ぶ

- 単独の run は Archon の `workflow run <名> --input <name>=<value>` で起こす（`A/packages/cli/src/help.ts` の `--input <name>=<value>`。入力ごとに繰り返す）。リポジトリは run の作業ツリー（Archon の cwd）で、port ではない。
- 工場の run の記録（今の始めの記録 `start` のポインタ）は、どの block も受けない。block が今その記録から読んでいる物（言語・web の切り替え・人の方針・試験のコマンド・差分の base commit など）は、block ごとに要る物だけを、既定の値つきの port にする。
- `ports.py` の読み手は、値を 3 通りの形で受ける: その run の pointer、ファイルの絶対パスか作業ツリーからの相対パス、値そのもの（`json` と `text` の form）。読めない pointer や在らないファイルは、空にせず理由を名指して落とす（今の落とし穴 K15 と持ち主の決め `no-silent-loosen`）。
- script は入力を `os.environ.get("INPUTS_<名>")` の字のままで読み、その値を `ports` に渡す。名を組んで読まない。Archon は uv の script の源のこの字の形を読み込みの時に照らし、結ばれていない入力を読む workflow を走る前に拒む（`A/packages/workflows/src/exec-input-validation.ts` の `scanEnvironmentReads`）。名を組むと、この照らしが効かなくなる。
- graph の中では、作り手の block の出力の欄を受け手の `with:` で渡す（今と同じ）。include の `with:` は値を JSON の字で運ぶ（埋め P2）ので、受け手は `json` の form で読む。
- 受け手が作り手の欄を 3 つ以上読む時は、欄ごとに入力を足さず、作り手の返りを丸ごと置いたファイルの pointer 1 つを `json` の入力 1 つで受け、読む欄は受け手の `src/` が名指す。作り手が欄を足すたびに読み手の数だけ入力が増える形（drift-audit の 4 節。サブグラフの入力の和が 85 から 142 に増えた）を止める。

### 4.3 run の記録を前提にしない

- block は自分の place と、port の値が指すファイルのほかは開かない。`ports.py` は run directory の根（`ARTIFACTS_DIR`）を script に渡さない。ここで言う run の記録は工場の記録（始めの記録・run directory の根のファイル）のこと。Archon が node に渡す run の log（`$LOG_DIR/<WORKFLOW_ID>.jsonl`）は読んでよい（report が落ちた node・費用・模型を読む。report の設計書の 9 節）。
- 前の段の失敗を伝えていた止めの記録（今の `judge/stop.json`）は使わない。block を include するかは graph の `when:` が決め、block は自分の結果を `outcome_field:` と出力の欄で返す。include された block の中で役を起こすか（例 素材の観点が、変更ファイルや判定から入る run かで決める `due`）は、block の intake が自分の port の値で決める。

### 4.4 place（block ごとの run directory）

- `ports.place()` は `$ARTIFACTS_DIR/<include の道>/` を返す。include の道は、自分の node の実行の記録（`ARCHON_NODE_EXECUTION`）の id から、最後の `__` より前を `/` でつないだ物（組み込みの前の `boundary.own_prefix` と同じ読み）。単独の run では空で、`$ARTIFACTS_DIR/` になる。
- 同じ block を 2 回 include すれば、place も 2 つに分かれる。今の judge と plan-review が同じファイルを取り合う所（棚卸し `~/.cache/works-self/tmp/inventory-765.md` の 5 節）は、この形で無くなる。
- place の中のファイルの名は block の `src/` だけが持つ。ほかの block が読む物は、出力の欄の pointer で渡す。名の住処（`lib/*beside.py`・`lib/fixnames.py`）と、名の字を探す柵は要らなくなる。

## 5 指示の組み立て

### 5.1 md の書き方

- 1 つの AI の node に、`prompts/<node-id>.md` を 1 本置く。決まった指示の文は全部ここに英語で書く。
- 値の差し込み口は `{name}`（小文字・数字・`_`）。JSON の例の `{"a": 1}` は形が合わないので、差し込み口にならない。
- 同じ block の 2 つ以上の node が使う段落は、その block の `prompts/parts/<name>.md` に 1 本だけ置き、`{part:<name>}` で差し込む（例 fix の修正役・TDD の役・裁定役・合わせ役が共に使う fix だけの決まり。組み込みの前の `workflows/fix/commands/fix-rules/brief.md`・`principles.md`）。2 つ以上の block が使う段落は `workflows/.shared/prompts/<name>.md` に 1 本だけ置き、`{shared:<name>}` で差し込む（例 書き手の役の決まり `writer-rules`。fix と delta-review が使う。組み込みの前の `fix-rules/common.md`）。今 21 本の md に写されている外への検索の決まり（`lib/agents/judge.md:16-22` が元）と、4 通りに割れた却下の段落は、ここで 1 つになる。共通の断片 `query-rule` を入れる役は、一次の出典を先に読む決まり（組み込みの前の指示に無かった物）が指示に足される。`query-rule` を入れる役の全部に同じく足されるので、各 block の設計書の「今の指示との差」の一覧には書かず、ここに 1 度だけ書く。
- 差し込むかを選ぶ段落は `<!-- if <name> -->` と `<!-- end <name> -->` で囲む。逆の条件は `<!-- if not <name> -->`。入れ子にはしない。

### 5.2 組み立ての口

- prep は `prompt.render(node_id, values, when)`（place に書くなら `prompt.emit`）だけで指示を組む。口は、呼んだ script の在る block の `prompts/<node_id>.md` を自分で探し、パスも文も受けない。system prompt の文も md に置く: `prompts/<node-id>.system.md` が在れば、口が同じ値と `when` で組んで返す（13 章）。
- 口は次の時に落ちる: 値の無い `{name}` が在る（選ばれない段落の中の口も、system の md の口も数える。prep はいつも同じ組の値を渡す）・使われない値を渡された・`when` の名が md に無い・md の `if` に `when` の値が無い・`{shared:…}`・`{part:…}` の先が無い。
- 口は段落を選んだ後、値を入れる前に、3 つ以上続く改行を 2 つに畳む。だから空の値を入れた行は空行として残る（見た目だけ。消したい行は段落の `if` で選ぶ）。
- 組んだ指示は place の `<node-id>-prompt-<n>.md` に書く（`<n>` はloop の何回目か）。prep の出力の欄 `prompt`（system prompt は `system`）で返す。
- AI の node の YAML は `prompt: "$<prep の id>.output.prompt"` の 1 行だけにする（system prompt を持つ node は `systemPrompt: "$<prep の id>.output.system"` も）。`command:` は使わない。道具を持たない役（world-classes など）も、指示をファイルから Read せずに受け取れる。
- 「Python は指示の文を持たない」は、この口の形で守る。AI に届く決まった文の在りかは md しか無く、審査は md を読めば済む。lib の Python の定数の長さを数える検査は置かない（持ち主の決め `shape-checks-only`）。

### 5.3 Python が持つ物と、md が持つ物

- md: 決まった指示の文の全部、決まった節の見出し、差し込むかを選ぶ段落の本文、差し込み口の名。
- prep（Python）:
  - 周ごとの材料（依頼の行・目的の文・前の回の返答・差分・人の答え）。
  - 材料の中で項目ごとに繰り返す短い見出しと札（例 `### Class w-459d38b29048`・`- Query:`）。
  - md と validation が同じ字を持つべき値（返答の欄の名・語・上限の数・目印の字）。定数は block の `src/` か `lib/` に 1 つだけ置き、md には `{name}` で入れる。
  - 段落を差し込むかの真偽。
  - 人に見せる欄の言語の値（port `lang`）。
- accept（Python）: 却下の理由の文のうち、返答の中身（どの欄がなぜ駄目か）で変わる文。毎回同じ字の段落（直し方の決まり・戻し方の決まり）は run によらない決まった文なので、読む AI のノードの md に英語で置く（`{shared:rejected}` の頭書きと同じ扱い。#764 の決め 2）。憲法の 2 の「指示の文」は、返答ごとに変わる理由の文を含まない。理由の文はloop を諦めた時に報告に載るので、人に見せる文として日本語のまま Python が組み、次の回の指示には `{shared:rejected}` の中の `{rejection}` として入る。見分け方: 段落の字が、拒んだ返答の中身によらず毎回同じなら md、返答の欄の名や値が入るなら Python。この境は `tests/layers/test_no_prompt_text_in_python.py` が、定数に文を持つことと、指示を組む関数が文の定数を読むことで縛る。
- 人に見せる欄の言語: md の中で、その node の人に見せる欄を名指し、`{lang}` で書けと言う。`lang` は port で受け、空なら今の既定（`lib/rolekit.py` の `LANG_DEFAULT`「依頼文の言語」）と同じ意味の英語の文を入れる。その文は共通の断片 `workflows/.shared/prompts/lang-default.md` に 1 つ置き、`prompt.lang` が読む（13 章）。言語を自動で選ぶ仕組みは作らない（持ち主の決め）。
- 依頼を見ない役（例 test-gate の CI の任せ先・TDD の実行器の書き手）には「依頼の言語」の既定が意味を持たない。だから line は、block を include する時にいつも `lang` を渡す（始めの記録の言語。空なら line が依頼の言語を決めて渡す）。既定の文は、block を単独で回した時のためだけに在る。

## 6 ノードごとの設計シートの型

block の設計書（`docs/design/<block>.md`）は、頭に block の全体（役・port・node の並び・place のファイル・コードの置き場・使う `lib/`）を書き、AI の node ごとに次の 9 項を書く。手本は [world.md](world.md)。

1. 役: 1〜2 行。
2. port: その node が読む物と、どの block の port から来るか。
3. 組み立ての順: md の節を上から並べる。節ごとに、決まった文か `{name}`（値の出どころ）か、差し込むかを選ぶ段落か（条件）かを書く。
4. 返す形: `output_format` の欄。人に見せる欄と、その言語。
5. 描いた骨組み: 本物の run の値を入れて描いた指示の骨組み（見出しと各節の頭の行）。run は `~/.local/state/works-factory/targets/<target>/archon-home/workspaces/<owner>/<repo>/artifacts/runs/<run>/` から選び、run の id を書く。その node が本物の run で一度も走っていなければ、近い run の値に仮の値を足して描き、仮に置いた値を書く（purpose-review と procedure-trace は、記録の在る 148 本の run のどれでも走っていない。本物の指示の字は 11.2 の本物の単独の run で初めて見られる）。
6. 今の指示との差: 移した物・まとめた物・消した物・足した物と、その訳。
7. 元の works と graphloops の同じ場面: 対応する物、工場に無い能力、消した時の PR（意図して外したかを工場の git の履歴で確かめ、PR の番号を引く。記録が無ければ（未確認））。
8. 受け付け: 却下の決まり、諦めるまでの回数、諦めた時に出口へ書く物。
9. 試験: standalone の fixture・指示の比べ（11.4）・振る舞いの試験・守る keep-essence の番号。

## 7 形の検査と案内

### 7.1 形の検査（どれも yes/no）

1. AI の node の `prompt:` は、同じ block の script の node の `$<id>.output.prompt` 1 つだけ（`systemPrompt:` を持つ時は、同じ prep の `$<id>.output.system` 1 つだけ）。`command:` を持つ AI の node は無い。
2. AI の node ごとに `prompts/<node-id>.md` が在り（system prompt を持つ node は `prompts/<node-id>.system.md` も）、`prompts/` の直下の md はどれもどれかの AI の node の物で、`prompts/parts/` の md はどれも同じ block のどれかの md から `{part:…}` で差し込まれるか、同じ block の `scripts/`・`src/` の `prompt.render_part("<name>", …)` の呼びが名指す（AI の node でない物の指示。束ね役が起こす下請けが Read する指示のファイルなど）。
3. どの md も、その block の standalone の fixture の値で `prompt.render` が通る（埋まらない口も、使われない値も無い）。
4. どの block にも `fixtures/standalone.stubs.yaml` が在り、その `fixture.inputs` の鍵は block の `inputs:` の中にあって、pointer の値を持たない。
5. どの入力の `description` も `<form>: ` で始まり、`json(<schema>)` の `<schema>` が block の `schemas/` に在る。
6. ほかの workflow を名指す workflow（`include:` か、自分の外を指す `workflow:` を持つ物）は AI の node を持たない。AI の node を持つ block が `workflow:` で起こしてよいのは自分の YAML だけ（直しの組ごとに自分を子の run として起こす fix の形）。AI の node を持たない merge が、出口の語 pr の時に Archon 同梱の `archon-pr` を `workflow:` で起こすのは、この決まりの中で通る（持ち主の決め `deliver-via-archon-pr`。根の `AGENTS.md` の E8 の外し。merge の設計書の 10 節の 1）。
7. block の `scripts/` と `src/` に、字 `ARTIFACTS_DIR` と、ほかの block のフォルダへのパスが無い。
8. どの block の `returns:` の node の `output_format` にも、`outcome_field:` の欄と `report` の欄が在る。
9. `src/` の package の名は `src` で、`scripts/` の名と `lib/` のモジュールの名は重ならない（script のフォルダが `sys.path` の頭に来るため。今の E4 の決まりを続ける）。
10. どの block にも試験のフォルダ `tests/blocks/<block の名の - を _ にした物>/` が在り、`__init__.py` と `test_*.py` を持つ（13 章）。

11. YAML に指示の文を置く鍵（`loop:` の node・`agents:`・`on_reject` と `decisions` の `rework` の `prompt`）が無く、形のファイルは照らしの知らない語を持たない（13 章）。
12. AI の node の md（`{part:…}` と `{shared:…}` を入れた後）に `"欄":` の形で書いた欄が、その node の `output_format` のどこかの深さの `properties` に在る（返答の型が指示の欄を全部持つ。組み込みの前の `tests/workflows/test_reply_fields.py` の後継。`docs/design/integration.md` の 4.2-2）。
13. `include:` の node（loop_group の本体の中の物も）の id が、取り込む workflow の中のどの node の id（上の段も、どの深さの loop_group の本体も）とも違う。役と同じ名を持つ block は `<block の名>-run` で include する（judge-eyes.md の 1.3 の「include の id」）。

1 の `systemPrompt:`（`prompts/<node-id>.system.md`）・3 の照らし方（筋書きの `resolved-text-contains` が md の決まった文）・5 の `json(shared:<schema>)`・6 の block と graph の見分けは 13 章の土台の決め。検査は `tests/layers/test_block_shape.py` 1 本。

組み込みの前から在る yes/no の検査は、新しい pack にも当てて続ける: E1（`archon validate` が警告なしで通る）・E6（外への書き込みは 1 つの node）・E7（読むだけの node の印）・E12（期限を置かない）・E16（承認ノードの形）・E19（AI の node の retry）・uv の頭の宣言。数の表と許す物の表で縛る検査（`tests/layers/test_layer_map.py` の `known`・`ALLOWED` の表・名の住処の柵）は持ち込まない（9 節で消す）。

### 7.2 案内の AGENTS.md

直す人が立つ所に、短い AGENTS.md を置く。どれも決まりとパスだけを書き、設計の細目は `docs/design/` に置く。

- `workflows/AGENTS.md`: 憲法 6 行。「新しい block は `workflows/world/` を写して始める」。変更の種類ごとに閉じる所と pack の決まり（E1・E2・E4〜E7・E12・E16・E17・E19・E20）。設計書の型はこの文書の 6 節。
- `workflows/.shared/AGENTS.md`: `ports.py` と `prompt.py` の口の一覧（埋めの読み方 `ports.polyfill` を含む）と、口を通さずに書けない物（入力の読み・place・指示）、共通の断片と形の名、md を書く人の決まり。
- `lib/AGENTS.md`: 「2 つ以上の block が使う物だけを置く。1 つの block だけが使う物は `workflows/<block>/src/`」。共通の部品の短い一覧（`jsonfile`・`oneline`・`rolekit`・`worldmark` など）。
- `tests/AGENTS.md`: block の試験は `tests/blocks/<block の名の - を _ にした物>/`。block の出力の見本は、block の `returns:` の `output_format` から作る助けで作る（今の試験ごとの写し `judgment(...)` の崩れ。drift-audit の 7 節）。
- block の外の文書（根の README・`docs/owner-decisions.md`・`docs/polyfills.md`）は、block・port・コマンド・環境変数の名までを書き、関数の名を書かない。関数を名指すのは block の設計書だけ（1.3 の形の直し 8）。
- 手本の block は 1 つ（world）にする。崩れたコードが「いちばん近い手本」にならないよう、古いサブグラフは組み込みで消した。
- 根の `AGENTS.md`: 憲法 6 行・決まりの置き場の表・リポジトリの形の木・根の決まり（E8〜E11・E13・E14・E18・E22）。決まりの中の試験の細目は試験の docstring に置き、決まりには試験の名を 1 つ書く（持ち主の決め `rules-tests-design-apart`）。

## 8 block の一覧

form は 4.1 の物。どの block も `lang`（`text`）を持つ物は書くのを省き、出力の `ok`（`outcome_field:`）と `report` も省く。詳しい port は各設計書で決める。

### 8.1 判定（今の judge を観点ごとに割る）

- world（世界の解）: 依頼の行を問題の類に言い直し、一次の出典の抜き書きで業界の定石と照合する。入力 `request` json（依頼の行）・`purpose` text・`means` json（依頼が示した解き方）・`web` choice(on|off)。出力 `rows`（pointer。行の形は `lib/worldmark.py`）・`status`・`reason`・`classes`・`dropped`。設計書 [world.md](world.md)。
- purpose（目的の固定）: run の元の目的を 1 文にし、依頼が示した解き方を分ける。入力 `request` json・`pr_text` text・`constraints` json（前提の実測。空でよい）。出力 `purpose`（purpose_text・source・known_weaknesses・source_files）・`means`。
- premises（前提の実測）: 依頼に書かれた数値・規模・在る/無いの主張を作業ツリーで測り直す。入力 `request` json・`carried` json（前の run が運んだ実測。空でよい）。出力 `constraints`。
- head-depth（run の頭の深さ）: 依頼の行ごとの未知の種類を引用つきで返し、機械が段を引く。入力 `request` json・`has_checks` flag・`thickness` choice・`spec` flag・`design_only` flag。出力 `tier`・`why`・`rows`・`record`（pointer）。未知の種類 → 段の表（`headdepth.UNKNOWNS`）は、未知の種類を読む diagnose・plan も使うので、段の語と控えの読み（line も読む）と一緒に `lib/headdepth`（4.1）。段 → 回す物の表は line（1.2 の D）。報告の「run の頭の深さ」の行は割る: 段と根拠はこの block の `report`、省く物・足した物（段 → 回す物の表から引く字）は line の `report`（設計書 [head-depth.md](head-depth.md) の 8 節の 3）。
- spec（仕様）: 要件と受け入れテストを書いて審査し、承認ノードの後に固める。中に人の承認ノードを持つ（単独で呼んでも人が答える）。固めた仕様の受け入れテストが承認の版から変わったかの照らし（今の line の `spec-check`）も、`mode` check でこの block が持つ。入力 `mode` choice(write|check)・`request` json・`pr_text` text（依頼が名指す PR の題と本文）・`spec` file（check で照らす固めた仕様）・`user_env_dir` text。出力 `status`・`stop_reason`・`reason`・`spec`・`added_rows`（依頼に足す受け入れ条件の行）・`added_origin`（足した行の出どころの名）・`questions`（check の承認し直すかの問い）・`unchecked`。設計書 [spec.md](spec.md)。
- parallel-pr（並行 PR）: 開いている PR と変更ファイルの交差を見て、ぶつかる所を外す。入力 `base` text・`changed` json・`request` json。出力 `status`・`stop_reason`（役を諦めた時の止めの語。止めるかは line が決める）・`reason`・`material`（素材の札。diagnose の `materials` に入る）・`excluded`・`drafts`・`reads`・`downgrades`（この block が下げている所の自分の行）。設計書 [parallel-pr.md](parallel-pr.md)。
- 素材の観点 11 本（prior-decisions・purpose-review・local-review・consistency-bypass・hygiene・external-standards・procedure-trace・gate-efficacy・test-double-fidelity・main-path-observation・provenance）: 1 本ずつ block にする。どれも同じ型（prep・役・accept）で、共通の部品は `lib/` の 1 モジュールに置く（11 本が使う）。入力は観点ごとに要る物だけ（例: hygiene は `base` text と判定から入る run の出どころ `entry` text、prior-decisions は `base`・`request`〔行の `where` だけを読む〕・`entry`。`purpose` は持たない）。出力 `status`・`reason`・`material`（pointer）。
- diagnose（根本の診断と再審）: 素材をまとめて直す単位を切る。`objection` が空でなければ再審の道を通る。再審は同じ block に置く（持ち主の決め `rejudge-cohabit` の訳「再審が判定の置き場を外から前提にする」は、前の判定を port で受ける形で起きなくなるが、置き場は変えない）。入力 `request`・`purpose`・`materials` json・`world_rows` file・`constraints`・`row_asks` json（頭の深さが行ごとに返した問い）・`spec_rows` file（仕様が足した受け入れ条件の行。spec の `added_rows` と、行を分ける出どころの名 `added_origin`）・`answers`・`objection` text・`prior` file（再審の時の前の判定）。出力 `judgment`（pointer）・`units`・`questions`・`ready`。
- verify（判定の裏取り）: 開いた単位ごとに、本当に根本か・証拠は在るかを別の目で確かめる。入力 `judgment` file・`materials` json。出力 `verify`。

### 8.2 計画と事前審査

- structure（構造の目）: 直しの単位を測り、直しが設計の考えを知る場所を増やすかを見る。今の見方（周りのコードと比べる）から、対象のリポジトリの書いた意図（憲法・決まり・設計の文書）と比べる見方に変える（持ち主の 2026-10-19 の追加。8.6 の 3 つの時の 2 つ目）。直した後の実測（今の `stage_b`。差分が設計の考えを知る場所を増やしたか）もこの block に置く。入力 `mode` choice(before|after)・`units` json・`intent` json（対象の書いた意図の文書のパスの一覧。空なら決まった名で探す）・`policy` file（人が固めた方針の文書）・`base` text（after の時の直す前の版）・`plan` file（after の時の修正案の欄。構造の目の避け方から外れた訳を読む）。出力 `status`・`reason`・`structure`（pointer）・`after`（pointer。after の時）・`dirty`・`escalate`・`optional`。元の works は目を Git の外で起こして作業ツリーの git の様子を見せなかったが、工場はこの隔離を記録なしに落とした。system prompt を md から入れる口（13 章）で塞げるが、振る舞いを変えるので作り直しの外に置く（設計書 [structure.md](structure.md) の 11 節の 8）。
- independent-design（R2 の独立設計）: 目的の文と、人が決めた前提だけから別の役が設計する。修正案・判定・差分を運ぶ port を持たない（独立の守り）。入力 `purpose` text・`purpose_source` text・`purpose_review` json・`constraints` json（前提の実測。今の `boardview.r2_prompt` も貼っている）・`answers` json・`request` file・`policy` file・`base` text・`head` text（足した行の印を付ける版の組）。出力 `status`・`stands`・`design`（pointer）・`premises`（pointer）・`reason`・`downgrades`。設計書 [independent-design.md](independent-design.md)。
- plan（修正案）: 修正案を書き、事前審査の指摘で書き直す。入力 `judgment` file・`purpose`・`structure` file・`world_rows` file・`spec` file（固めた仕様。今の `plan_prep.py` の `INPUTS_SPEC`）・`policy` file・`prior` file（前の周の案と指摘。1 周目は空）・`ruling` file（案の直しの時）。出力 `plan`（pointer）。
- plan-review（事前審査）: 案の欠陥を探す。`proposal` を案の構造（項目・ファイル）か、方針の文だけ（text）のどちらでも受ける。text だけの時は、案の構造を前提にする確かめを飛ばし、今の事前審査の md（`workflows/plan-review/commands/plan-review.md`）が持つ 8 種の確かめと欠陥の重さの定義だけを当てる（入口の workflow のため。棚卸しの 5 節）。入力 `proposal` file か text・`purpose`・`design` file・`world_rows` file・`structure` file・`policy` file・`tree` flag（項目ごとの下請けで木にするか。line が深さの表から引く）・`prior` file（前の周の案と指摘。1 周目と方針の文だけの時は空。2 往復目からの穴の出自・続いた穴・約束の欄が変わった項目を決める）。往復の記録・止め・安全の上限は line が持つ（1.2 の D）。出力 `holes`・`deviations`（定石や独立設計からの外れと、その出どころ）。承認ノードを聞かずに通してよいかは line が決める（1.2 の U）。

### 8.3 修正

- fix（修正）: 承認済みの案を項目ごとに直す。範囲の相談・食い違いの裁定・組どうしの合わせと、組ごとの TDD の loop（単位ごとに赤から緑まで回し、赤緑を JUnit の結末で機械が判じる）を含む。直しの組ごとに自分を子の run として起こす（`workflow:` と `fan_out:`。#765 の本文が手本として残すと書いた形。7.1 の 6）。単独の run と standalone の fixture は組 1 つの形（`mode` が `group`。今も単独で回る）で回す。全体の形は、Archon が先祖と同じ名の子の run を循環として拒むので、graph から include された時だけ回る（今のまま）。入力 `mode` choice(whole|group)・`plan` file・`judgment` file・`policy` file・`test_cmd` text・`tdd_suite` text・`baseline` file・`skip_rerun` json（緑の後の試験の走らせ直しを省く単位。line が深さの表から引く）と、組の形の時の組・親の木・結果の置き場。出力 `diff`（pointer）・`closure`・`conflicts`・`permits`・`units`（単位ごとの記録）・`frozen`（テストの hash）。深さの上げ直しは持たない（line が fix と delta-review の間で行う）。
- tdd は独立の block にしない。組ごとの TDD の loop は fix の組の子の run の中に置く（block は `include:` を持てないので、別の block にすると fix から呼べない。1.3 の形の直し 2）。
- delta-review（差分の審査と手直し）: 差分を案の項目への準拠と品質で見て、2 往復まで手直しする。入力 `base` text・`plan` file・`lens_rows` file。出力 `holes`・`diff`。
- lens（黙った失敗のレンズ）: 利用者が入れた review のレンズで差分を見る。入力 `base` text・`lenses` json。出力 `rows`（pointer）。

### 8.4 独立の目と関門

- r1（最小性とコメント）・r2（独立設計との比べと前提の検算）・r3（全体の整合）・r4（見えていない範囲）: 1 本ずつ block。入力はどれも `base` text（差分の base commit）と、観点ごとに要る物（r2 は `design` file と `purpose`、r3 は `intent` json と `policy`、r4 は `plan` file と `policy`）。出力 `verdict`・`questions`（人に回す問い）。
- test-gate（試験の関門）: 直す前と後の結末を取り、元から赤のテストを分ける。入力 `mode` choice(base|final)・`test_cmd` text・`tdd_suite` text・`baseline` file（final の時）。出力 `baseline`（pointer）・`green`。
- merge（差分の確定と取り込み）: AI を持たない。差分は作業ツリーと根から組み直して指紋と照らすので、入力 `diff` は持たない（#266 `3adce5e5` で意図して外した。1.3 の歩かせ 4）。入力 `mode` choice(seal|apply|check)（check は chain の `hand` が使う）・`base` text・`fingerprint` json・`green_ok` flag・`eyes_ok` flag・`sealed_hash` text・`answer` json・`r2` json・`deliver` text・`request` file・`items` json・`user_env_dir` text。出力は今の欄の名のまま（line の最後の承認ノード・`bin/apply`・chain・報告が今の名で読む）: `mode`・`hash`・`diff`（pointer）・`protected_hits`（守りのファイルに触れた一覧。13 節）・`protected_count`・`reason`・`deliver`（PR を作った時の結果を含む）・`optional`。設計書 [merge.md](merge.md)。

### 8.5 報告

- report（報告を書く）: block の `report` の欄を並べ、結末の語を決め、書き手の役が本文を書く。書き手と初見の読み手の往復（回ごとの書き手の受け付けが、同じ回の読み手の判定で決まる）は、この block の中に置く。graph の loop で report と cold-read を並べると、受け付けの決まりを cold-read か graph が持つことになり（憲法の 3）、report を単独で回した時に初見の確かめが落ちる（憲法の 5）。入力 `sections` json（block ごとの `report` の欄を graph が 1 つに集めた物）・`facts` json（結末を決める事実。どの block の欄が止め・人待ち・残りに当たるかは line が読み分けて入れる）。出力 `outcome`・`stop_reason`・`machine`・`human`・`detail`（どれも報告のファイルの pointer）・`next_request`・`prior_failures`・`report`（ほかの block と同じ日本語の行の配列。4.1・7.1 の 8。pointer ではない）。設計書 [report.md](report.md)。
- cold-read（初見の読み手）: 文脈を持たない読み手が本文を 1 回読み、詰まった所を返す。報告に依らない素の読み手で、報告の頭の決まりは持たない（報告の中の読み手は report が持つ。役の定義は共通の断片 `role-cold-reader` 1 か所）。入力 `text` file。出力 `status`・`verdict`・`pass`・`stops`・`guessed`・`decidable`・`stuck`。設計書 [cold-read.md](cold-read.md)。

### 8.6 3 つの時の目（崩れを入る前・入る時・入った後で見る）

- 入る前: guidance-path（案内の道の目）。文脈を持たない AI に典型の変更の頼み（例「この AI の役に確かめを 1 つ足す」「観点の block を 1 つ足す」「この node が AI に言う事を変える」）だけを渡し、リポジトリの入口から案内（AGENTS.md・設計書）と手本だけを頼りに辿らせ、どこに変更を置くか・何を写したかを記録する。1 節の「変更が閉じる 1 か所」に置けば案内が効いている。違う所に置けば崩れの入口なので、案内の直し（直す人が立つ所に案内を足す・手本を替える・間違った道を置き場で塞ぐ）を出す。手本は convergence-loops の firstread-loop（`~/src/claude-plugins/convergence-loops/` の、用事だけを渡されて入口から自分で探す読み役）。入力 `requests` json（頼みと、それが閉じるべき 1 か所の組の一覧）・`entry` text（入口のファイル。空なら `README.md` と根の `AGENTS.md`）。出力 `paths`（頼みごとの辿った道・置いた所・写した物）・`fixes`（案内の直しの案）。回す時: block を作り始める前に新しい形で 1 回、その後は案内か置き場の形を変えるたび。
- 入る時: structure（8.2）。PR の差分を、周りのコードでなく書いた憲法と比べる。
- 入った後: drift-eye（崩れの目。後で足す）。リポジトリの今を、書いた意図・業界の定石・履歴の傾きと比べ、崩れがどこから入ったかを辿り、置き場と案内の直しを出す。見つけた入口は、guidance-path の頼みの例に足して返す。入力 `intent` json（書いた意図の文書の一覧）・`window` text（履歴を見る範囲）。出力 `drifts`・`fixes`・`new_requests`（guidance-path に足す頼み）。

### 8.7 graph

- line（メイングラフ）: block を並べ、承認ノード・計画の往復（往復の記録・止め・安全の上限）・一度だけの include（案の直し・2 度目の修正・再審）・深さの表（段 → 回す物）と修正の後の上げ直し（fix と delta-review の間で 1 回）・無人の方針を持つ。始めの記録はここだけが書き、block には port の値として配る。
  - 今の工場の穴（作り直しで直す。line の設計書で決める）: 並行 PR の確かめを回し直す条件（今の `judge_accept.parallel_pr_due`）は写したが名指す節が無い死んだコードで、最初の修正の後に並行 PR の確かめが走り直さない。fix は parallel-pr が外した hunk（`excluded`）を受け取らず、外した範囲を直しても拒む関門が無い（parallel-pr の設計書の 6 節の 2・5）。始めの記録に `gates` を書く物が無いので、ゲートの検算を合流した版に回す道（gate-efficacy の `gates` が `merge`）が今の run では走らない。その訳の字 `GATES_MERGE_WHY` は元の works の入口の入力（`init --input gates=merge`）を名指していて、工場の起動の殻に同じ入力は無い（gate-efficacy の設計書の 6 節）。
- chain（周の鎖）: line を周ごとに子の run として起こす（今のまま）。
- judge（判定のまとめ）: 8.1 の block を `include:` で並べ、line から 1 つの include で呼べるようにする。Archon 同梱の sdlc の `deliver` が `implement`・`review` を include で組むのと同じ形（`A/.archon/workflows/sdlc/deliver/archon-deliver.yaml`）。
- eyes（独立の目のまとめ）: r1〜r4 と structure（after）を並べ、まとめの判定の script を持つ。
- policy-check（方針の文だけを入れる入口。#765 の目指す形 4）: 方針の文を world と plan-review（text の形）で評価して返す。設計は [world.md](world.md) の 9 節。

## 9 収束した形での lib/ と試験の仕分け

- 仕分けは、収束した形（全部の block が pack に入り、古いサブグラフが消えた後）で何が要るかで決めた。lib の import の向きを機械で読んだ（`ast` で各モジュールと各 script の import を数えた。lib の中に 33 モジュールの import の循環があるので、推移で辿ると全部が全部に届く。そこで、直に import する script と、それを import する lib のモジュールの直の使い手までを見て、残りは docstring とコードを読んで決めた）。組み込みの PR を機械的にするために、一覧を 1 件ずつ今のコードで確かめて直した結果が [integration.md](integration.md)（4 節の 72 項目と「全体で決めた事」）で、この章はそれを当てた後の形。
- DELETE は 1 件ずつ確かめずに消す（持ち主の決め）。能力は 10 節の keep-essence の割り当て・指示の比べ・e2e の筋書きと本物の run で守る。
- MOVE は block の `src/` へ。作り直しの間は写しを block に置き、lib の元は古いサブグラフのために残した。組み込みで lib の元を消す。
- KEEP は 2 つ以上の使い手（block か graph か `bin/`）を書く。指示の文を持つ物は、組み込みで文を md へ出して軽くする（「文は md へ」と書いた物）。`promptsection` を import する KEEP のモジュールは全部、`Section` の文を md へ出してから import を外す（integration.md の 4.3-追加-1）。始めの記録を読む口は lib に残さず、KEEP の関数は値を引数で受ける（4.3-追加-6）。
- lib に新しく作るモジュールは 2 つだけ: `runlog`（run の記録の読み）と `judgmark`（判定の出力の行の形）。ほかは今ある KEEP のモジュールに口を足す。

### 9.1 lib/ の DELETE

- 名の住処: `eyesbeside`・`fixnames`・`judgebeside`・`planreviewbeside`・`structbeside`・`fixbeside`（読み手と `PORTS`。閉鎖の表を書く関数は fix の `src/` へ）。`leftovers` が借りていた `fixnames.REMOVED_FILE` は字を `leftovers` に直に書く（4.3-11）。
- 指示を lib で組むための仕組み: `promptsection`（見出しの宣言と受け渡しの表）・`graphloops/engine/render.py`（graph の reads から指示を描く。定数 `FILE_CAP` と `cap_bytes` は KEEP の `listcut` へ移し、役への文 `MATERIAL_NOTE` は共通の断片 `policy` へ。4.3-6）。
- 写した graph の型が持てない欄を足す仕組み: `marks`（返答の型は node の `output_format` が正本になる）。読み手 5 つ（`handoff`・`outpurpose`・`planmarks`・`querytest`・`worldmark`）は、`load`・`write`・欄の道を辿る読みを `jsonfile` の口に替え、控えの名と欄の道は各モジュールの定数で持つ（4.3-追加-2）。
- 使う所が無い: `graphloops/engine/pointers.py`（import する物が無い）。
- 写した graph の規則: `graphloops/engine/validator.py`。組み込みの後に呼ぶのは lens だけ（`agent_def`・`find_plugin_path`）なので、その 2 つを lens の `src/` へ写して消す（判定の受け付けは呼んでいない。4.4-J）。
- `runreport`: line だけが使う部分は line の `src/facts.py` へ写し、run の記録の読み（`transcript_facts` など）は新しい `lib/runlog.py` へ上げ（report と chain が使う）、`lib/runreport.py` は消す（4.5-2・4.5-4 の (f)）。報告の行は事実を持つ block が `report` の欄で組む（4.1）。

### 9.2 lib/ の MOVE（行き先の block）

- world: `worldblk`・`worldcheck`
- purpose: `purpose`／premises: `premises`／spec: `specblk`／parallel-pr: `prcheck`／local-review: `diverted`
- `downgrades.json`（下げている所の宣言。今は parallel-pr と independent-design の 2 つの block の行を 1 つのファイルに持ち、読むのは報告の頭の数だけ。`docs/nodes.json` の一覧とも合わない）: どの block にも移さない。下げている block が自分の行を出力の欄 `downgrades` で返し（parallel-pr の設計書の 6 節の 6・10 節の 8、independent-design の 1.2）、ファイルは組み込みで消す。報告の頭の「下げている所」の数をこの欄から組み直す形は、report と line の設計書で決める。
- judge の芯 `judge_accept`: 観点ごとの部分を各 block（world・purpose・premises・head-depth・spec・parallel-pr・diagnose・verify）へ割る。素材の 11 本が共に使う部分は KEEP の `materialkit`。指し先の綴りと版に在るかの照らし（`_resolve_target`・`_in_version` ほか）は KEEP の `cite` へ（4.3-4）。`judge/` の決め打ちの包み（`world_intake` など）と `PORTS`・`FIRST_PORTS` は DELETE。
- verify: `judgeverify`
- structure: `context`・`stage_a`・`stage_b`（直した後の実測）・`structfile`・`eye` の目の役の部分（時間の欄の 3 つは KEEP。9.3）。`design-row.schema.json` は実行の時に読む物が無い（#232 から）ので写さず DELETE（行の型の正本は node の `output_format`。structure の設計書の 11 節の 9）
- head-depth: `headdepth` の受け付け（段の語・控えの読み・未知の種類 → 段の表は、diagnose・plan も読むので KEEP）。種類ごとの受け手への指示の文（今の `headdepth.ASKS`）は、読み手の diagnose と plan の md が使う共通の断片 `unknown-asks` へ（head-depth の設計書の 8 節の 4）
- plan: `planfile`・`ripple`・`planblk` の修正案の役の部分
- plan-review: `boardview`（独立設計の部分は independent-design へ）・`planblk`（修正案の役の部分は plan へ）
- fix: `clash`・`consult`・`factchecks`（`declared_files` は KEEP の `itemcommits` へ。4.3-2）・`fixboard` の fix.md 1.5.2 の名の外（差分の審査の部分は delta-review、レンズの部分は lens へ。上げ直し `redepth` は消して line の上げ直しに寄せる。fix.md 1.5.2 の名は `fixboard` を削って KEEP。9.3）・`fixgates`・`fixrules`・`lanekit`・`parking`・`planscope`・`ruling`・`unitrows`・`tddloop`（全部 fix の `src/tdd.py` へ。語 `CMD_LIGHT` は KEEP の `report` へ。4.3-3・4.4-F・4.5-14）
- delta-review: `deltamarks`・`refix`・`refixrules`
- lens: `lenses`
- eyes（graph）: `eyeverdict`（観点ごとの部分は r1〜r4 へ）
- report: `outcome`（結末の 10 語と決める順。ほかの block の欄の名〔`stalled`・`premise_check`・`units` など〕を読む読み分けは report に持ち込まず、line が `facts` の欄〔止め・人待ち・残り〕に仕分けて渡す。report の設計書の 9 節）・`report_roles`・`glossary.json`
- line（graph の `src/`）: `fixture`・`startrec`（始めの記録を読む口。形を問わない JSON の読み書きは KEEP の `jsonfile` へ。4.3-9）・`testcmd_check`・`versions`・`gatepolicy`・`gatemarks` の承認ノードの決めの部分（`row_push`・`_as_push`、始めの記録を読む `design_only`・`request_answers` の道。4.5-4 の (a)(b)。問いの行の形と承認ノードの文の組み立ては KEEP。修正案と事前審査に渡していた文は md へ）・`depth`（段 → 回す物の表と単位ごとの深さ。block には真偽と一覧を port で渡す）・`latedepth`（修正の後の上げ直し。読み手は line だけ）・`headdepth.report_line`（4.5-6）・`converge` の往復の記録と止め・`gate_axes`・`runreport` の line だけが使う部分（`src/facts.py`。9.1）

### 9.3 lib/ の KEEP（使い手）

- `accept`（作業ツリーの写しと返答の照らし。役を持つ block の多く。写した graph の規則の部分は割る。作業ツリーの比べ `moved_since` もここに寄せ、block の写しは消す。4.4-H）
- `answer`（line・chain・`bin/`）・`chain`（chain・`bin/`）・`entry`・`entryshape`・`runbranch`（line・chain・merge）
- `baseline_red`（test-gate・fix・report）・`green_cert`（test-gate・merge・line・chain）・`declared_checks`（test-gate・report・line）・`suitewrite`（test-gate・line）・`checkscope`（test-gate・素材の観点）
- `carry`（line・chain・report・test-gate）・`changemap`・`COPIED_FROM.changemap`（line と `impact` の使い手）・`impact`（fix・plan・structure）
- `cite`（fix・diagnose・head-depth・plan-review・line）。指し先の綴りと版に在るかの照らし（今の `judge_accept` の `_resolve_target`・`_in_version` ほか。purpose・diagnose・`recount`）と、Markdown のリンクと見出しの読み（今の `boardview` の `MD_LINK`・`_md_lines`・`_md_slugs`。`recount`・independent-design・`design`）もここ（4.3-4・4.5-5）
- `conflict` の全部（申し出の行の語・出どころ・人に諮る行の選び・数え・直しの在りかと、申し出と裁定の積み方・テストの許し `test_permits`。fix・delta-review〔`planrange` 経由〕・plan・line・report。4.4-A・4.3-追加-4）・`converge`（plan・plan-review。往復の記録と止めは line の `src/` へ）・`replan`（fix・plan・line）
- `concepthome`（plan・plan-review・structure・r1・r3。文は md へ）・`conceptfence`（structure・r3。対象のリポジトリの表に当てる道具として残す）・`measure`（structure・eyes。コマンドとして起こす）
- `headdepth`（段の語と控えの読み、行ごとの未知の種類の語と種類 → 段の表 `NONE`・`CAUSE`・`SHAPE`・`SCOPE`・`UNKNOWNS`・`known`・`tier_of`。head-depth・line と、未知の種類を読む diagnose・plan の 4 つが使う。`report_line` は line へ）。段の語 4 つ（`LIGHT`・`STANDARD`・`HEAVY`・`HEADS`）は `lib/depth.py` からここへ移す（11.3）。名の字は `judgebeside` の import を外して直に書く（4.3-5）・`launchgroups`（`bin/`・head-depth）
- `design`（independent-design・r2・plan-review）・`eye` の時間の欄 `stamp`・`wall`・`WALL` だけ（structure・`structmark`。4.3-8・4.4-J）・`structmark`（structure・plan・plan-review・eyes・line・report）
- `forge`（merge・parallel-pr・line）・`ghreads`（line・purpose）
- `globs`（fix・plan・eyes・merge）・`protect`・`protected.json`（eyes・merge・line）・`seal`（merge・eyes・line・chain・`bin/`）・`listcut`（eyes・fix・merge・structure・`bin/`。`FILE_CAP`・`cap_bytes` もここ。4.3-6）
- `groups`・`holeties`・`planrange`（fix・delta-review）・`itemcommits`（fix・merge・line。`declared_files` もここ。4.3-2）・`planbrief`（fix・plan）・`planmarks`（plan・plan-review・fix・eyes・line）・`recount`・`querytest`（diagnose・fix・delta-review・plan-review・line）
- `handoff`（plan・report）・`outpurpose`（diagnose・line・report）・`policy`（fix・delta-review・plan・structure・r1・r3・r4・line。文は md へ。名の字は `judgebeside` の import を外して直に書く。4.3-5）
- `lens`（lens・delta-review）・`libdocs`・`libdocs_local`・`libdocs_web`（plan・plan-review・fix）・`webget`（world・libdocs の使い手）
- `leftovers`（fix・delta-review・lens。4.3-11・4.4-C）
- `rolekit`（役を持つ block の全部。loop の数え・諦め・却下の控え。言語の文と出し直しの文は md へ）・`rulebook`・`seat`（fix・delta-review。座の値の口だけに削り、`QUERY_RULE_SOURCE`・`query_rule`・`g1_section`・`G1_*` は消す。4.3-13）・`spseam`・`borrow/`（`bin/`・fix・delta-review）
- `reads`（fix・plan・plan-review・parallel-pr・`bin/`）・`writelog`（`bin/`・fix・delta-review）・`writes`（fix・delta-review）
- `report`（report・fix・line。語 `CMD_LIGHT` もここ。4.5-14）・`stopby`（line・report・chain・judge のまとめ。前提の実測と目的の固定が落ちた時に judge のまとめが止める語 `works:premises`・`works:purpose` もここに在り、止めるかは judge のまとめが決める）
- `runlog`（新しい 1 モジュール。run の記録の読み。report と chain。今の `runreport.transcript_facts` と report の `src/transcript.py` の `read`・`facts` ほか。4.5-2）
- `judgmark`（新しい 1 モジュール。判定の出力の行の形 `is_open`・`open_units`。diagnose・verify・fix。4.4-H）
- `tree_run`（test-gate・fix・merge・line・`bin/`）・`userenv`（`bin/`・report・`tree_run`）
- `unittrees` の全部（fix・delta-review・lens・independent-design・`green_cert`・`groups`・`tree_run`。4.3-10・4.4-B）
- `worldmark`（world・diagnose・plan・plan-review・line。行の欄と語・読み・答えの照らし。`judgebeside` への import は外し、文は md へ。報告の行の組み立て `report_lines` は world の `src/` へ）
- `gatemarks` の KEEP の部分: 問いの行の形（問いの語 `ASKING`・人へ回す問いの選び `asks_human`・項目の推しの尾の字の形 `push_rec`。diagnose・plan-review・line・report。4.1）・承認ノードの文の組み立て `gate_text`（line・spec）・定数 `BASELINE_NOT_RUN`・`BASELINE_UNVERIFIED`・`MATERIAL_WORDS`・`SPEC_CHANGED_LABEL` とそれが組む `KIND_WORDS`（test-gate・spec・`declared_checks`・`green_cert`。4.3-7）・決め手の欄を外す `split`（replan・plan・plan-review。4.3-追加-3）・問いと答えの行の札 `GATE_NODE`・`START_GATE_NODE`・`status_named`（r1〜r4・line・report。4.3-追加-5）
- `fixboard` を fix.md 1.5.2 の名だけに削った物（git の 3 つ `pr_revs`・`pr_diff`・`pr_added_lines` と trace の助け。fix・delta-review・independent-design・r2 と KEEP の `writes`・`conflict`・`planbrief`・`eyekit`。新しいモジュールは作らない。4.3-1）
- 前提の実測の行の形（`kind` の語 `実測`・`仮説`。premises・independent-design・diagnose・report）と目的の出典の語（`source` の語。purpose・independent-design・diagnose）。今 `carry`・`runreport`・`judge_accept`・`design` に割れている語を、作り手ごとの行の形のモジュールに寄せる（4.1。名は premises と purpose の設計書で決める）
- `jsonfile`・`oneline`（ほぼ全部。`jsonfile` は dict でなければ拒む読みと、書いたバイトを返す書きを足す。4.3-9・4.3-追加-2）
- `materialkit`（素材の 11 本の共通の部品。測れていない素材の状態 `UNMEASURED` は `STATUS` から導く。4.2-5）・`eyekit`（r1〜r4 の共通の部品）
- `graphloops/engine/util.py`・`schema.py`・`declared.py`（`accept`・test-gate・`tree_run`）
- `next-request.schema.json`・`prior-failures.schema.json`（`carry` と同じ使い手）
- 指示の断片へ移す物（md なので lib から出す）: `agents/*.md`（役の定義 5 本）・`REVIEW.md` は `workflows/.shared/prompts/` へ。

### 9.4 試験の DELETE

- `tests/layers/`: `test_layer_map.py`（既知の漏れの表と数の歯止め）・`test_block_paths.py`（名の字の柵と `NAME_HOMES`）・`test_concept_fences.py`（自分の許す表）・`test_scan_rules.py`・`test_node_table.py`（`docs/nodes.json`）・`test_capability_pointers.py`・`test_restored_not_gaps.py`・`test_works_parity.py`・`test_design_roles.py`。これらだけが読む表（`docs/nodes.json`・`docs/works-parity.md` の照らしの表）も一緒に消す。
- `tests/layers/scan.py` は丸ごと消さない。KEEP の検査が呼ぶ yes/no の規則（E1・E2・E6・E7・E12・E16・E19 ほか）と、その見本（`tests/layers/seeds/` の e*・k*）を残し、消える試験だけが使う部分（層の表の照らし・`NAME_HOMES`・考えの柵）と見本を消す（integration.md の 4.5-9）。
- 残す表: 層の地図 `docs/layers.json`（scan の block の名と、lib が頼ってはならない層の頭を読む）・考えの住処の表 `docs/concepts.json`（run の中で構造の目が対象の表として読む。KEEP の `lib/tests/test_concept_fences.py` も読む）・scan の外しの表 `ALLOWED`（E2・E3・E13・E21 の照らしが使う）。どれも生きている照らしが使うので残す。層の地図の数の歯止め（既知の漏れの表 `known`・緩めの訳 `loosened`）と名の住処の表（`beside`・`homes`）は、照らす試験と一緒に消した。
- 能力の棚卸しの指しの照らし（`test_capability_pointers.py`）は、keep-essence の 12 だけを照らす yes/no の `tests/layers/test_keep_essence.py` に縮めて残す（10 節の「新しい守り」の `path::名`。integration.md の 4.2-1a）。
- `tests/workflows/`: `test_prompt_contracts.py`・`prompt_contracts.json`（古い指示書の約束の表。組み立ての口の落ち方と指示の比べで替える）・`copied.py`・`copied_rewrites.json`（元の works の指示書の写しの台帳。指示は英語で書き直すので台帳を閉じる）・`test_reply_fields.py`（7.1 の 12 で替える。integration.md の 4.2-2）。
- `lib/tests/`: `test_constants.py`（ファイル名の字の柵）・`test_cross_block_keys.py`（block をまたぐファイルの鍵。port で替える）・`test_promptsection.py`・`test_marks.py`・`test_concept_fences.py` の works-factory 自身の表の部分（道具の部分は `test_concept_change.py` に寄せる）。
- `tests/shared/test_boundary.py`（`boundary.py` が消えるので、`ports.py` の試験 `tests/blocks/shared/test_ports.py` に替える）。
- 古いサブグラフの試験（下の 9.5 の MOVE の元）は、組み込みで消す。

### 9.5 試験の MOVE（新しい block の試験の元にする）

古いファイルは組み込みで消す。振る舞いを見る試験を `tests/blocks/<block>/` に作り直す時の元にする。

- `lib/tests/`: world へ `test_blk_world.py`・`test_world_check.py`／fix へ `test_blk_fix.py`・`test_blk_fix_conflict.py`・`test_clash.py`・`test_consult.py`・`test_fix_duty.py`・`test_fix_gates.py`・`test_fix_rules.py`・`test_fix_units.py`・`test_duty_sets.py`・`test_lanekit.py`・`test_plan_scope.py`・`test_blk_fix_tdd.py`・`test_tdd_frozen.py`・`test_tdd_frozen_function_span.py`・`test_tdd_outside.py`／lens へ `test_blk_lens.py`／delta-review へ `test_blk_refix.py`・`test_blk_tests_delta.py`・`test_delta_marks.py`／plan へ `test_blk_plan.py`・`test_planfile.py`・`test_ripple.py`／plan-review へ `test_boardview.py`・`test_gate_axes.py`・`test_plan_gate.py`／structure へ `test_structfile.py`・`test_structure_eye.py`・`test_stage_b.py`／判定の各 block へ `test_blk_judge.py`・`test_judge_accept.py`／local-review へ `test_diverted.py`／eyes と r1〜r4 へ `test_blk_eyes.py`・`test_eyeverdict.py`／report へ `test_outcome.py`・`test_report_roles.py`／line へ `test_fixture.py`・`test_startrec.py`・`test_testcmd_check.py`・`test_versions.py`・`test_depth.py`・`test_gatepolicy.py`・`test_line_inputs.py`。
- 割る物（KEEP の部分は lib/tests に残し、移る部分を block へ。integration.md の 4.2-9）: `test_gate_drafts`（line〔gatemarks の決めの部分〕と plan〔`planblk.RECOMMEND_REJECT`〕へ）・`test_gatemarks`・`test_headdepth`・`test_converge`（移る部分を line へ。headdepth の未知の種類は head-depth へ）・`test_libdocs`（`ComposerCase` の planblk の 2 本だけ plan へ）・`test_plan_brief`（planbrief の試験として残し、`fixboard.plan_view` の呼びを新しい住処に向け直す）。
- `lib/tests/test_runreport.py`: report の設計書（`report.md` の 444〜452 行）のとおり、report と作り手の block と line へ MOVE（`TddCase` は report の `SectionsCase` が keep-essence の 11 を継ぐ。integration.md の 4.2-8）。
- `tests/workflows/`: `test_judge.py`・`test_fix.py`・`test_eyes.py`・`test_plan.py`・`test_plan_review.py`・`test_report.py`・`test_structure.py`・`test_test_gate.py`・`test_merge.py` を各 block へ。`test_line.py`・`test_chain.py`・`test_gate_head.py`・`test_testcmd_head.py` を新しい line・chain へ。

### 9.6 試験の KEEP

- `lib/tests/` の残り（KEEP の lib のモジュールの試験。例 `test_accept.py`・`test_rolekit.py`・`test_worldmark.py`・`test_baseline_red.py`・`test_unittrees.py`・`test_blk_structure.py`〔名は structure だが、試すのは KEEP の `lib/measure.py`〕・`test_imports.py`〔lib の import の循環が解けたら yes/no の「循環が無い」に替える〕）。文を md へ出したモジュールの試験は、文の字への assert を符号と欄への assert に替える。
- 割って残す物（integration.md の 4.2-6・4.2-8）: `test_fix_seams`（KEEP のモジュールを試す `TestGroups`・`TestLeftovers`・`TestWritesSeams` は残し、ほかの class は fix の試験へ）・`test_writes`（`WritesLogNameCase` は fix と delta-review の試験へ、残りは KEEP。keep-essence の 5）・`test_impact`（`OverflowRowCase` は fix の `test_fix_accept.py` へ、残りは KEEP。keep-essence の 6）。
- `tests/layers/` の yes/no の検査: `test_archon_validate.py`・`test_readonly_nodes.py`・`test_no_timeouts.py`・`test_outward_write.py`・`test_gates.py`・`test_role_retry.py`・`test_depth_skip.py`・`test_names.py`・`test_no_asf.py`・`test_no_conversion.py`・`test_no_owner_env.py`・`test_hermetic_env.py`・`test_required_checks.py`・`test_test_commands.py`・`test_rule_index.py`・`test_polyfills_listed.py`・`test_polyfill_evidence.py`・`test_lib_blind.py`・`test_words.py`・`test_layout.py`（新しい木に書き直す）・`test_block_returns.py`（どの workflow の YAML にも、返す node を名指す `returns:` と仕事の結末の欄を名指す `outcome_field:` が在ること。加えて、誰も読まない欄があれば試験を落とす〔持ち主の決め `declared-io` の「読み手ゼロなら赤」〕: block の返す node の `output_format` の欄はどれも、呼ぶ graph の YAML が `$<include の id>.output.<欄>` と書いて読むか、返りまるごとを受けた script が `ports.picked`（`workflows/.shared/ports.py` の、返りまるごとから名指した欄だけを取り出す口）に渡す名の並びに入っている。block の `inputs:` の名はどれも、その block の YAML が `$INPUTS.<名>` と書くか、その block の `scripts/`・`src/` の Python が環境変数 `INPUTS_<名>` を読む。一番上のグラフ line（メイングラフ）・chain（line を子の run として最大 5 回つなぐ親のグラフ）と、どの graph にも呼ばれない workflow の返りは照らさない。その読み手は人（Archon の命令 `workflow get` で run の返りを見る）と起動の殻（`bin/` の works-factory・apply）で、graph の YAML の字に読みが現れないため。照らすかどうかは YAML の形（一番上のグラフか・どこかの graph が include か `workflow:` で呼ぶか）で決め、外す物の表は持たない。今の試験が持つ、照らしを免れるファイルの表 `ALLOWED["E5"]` も消す）・`test_lang_neutral.py`（言語の表を 1 つのモジュールに寄せ、許すファイルの表をやめる）・`test_keep_essence.py`（新しい。10 節）・`trees.py`。どれも新しい pack に当てる。7.1 の 12 の検査は `tests/layers/test_block_shape.py` に置く。決まりの文から移した試験の細目は、各試験の docstring に書く（`docs/plans/765-docstrings.md`）。
- `tests/workflows/` の形の検査: `test_uv_scripts.py`・`test_nodeflags.py`・`test_loop_sessions.py`・`test_returns_never_fail.py`・`test_role_texts.py`（pack の `prompts/` と `.shared/prompts/` に向け直す。integration.md の 4.2-4）・`test_reply_patterns.py`・`test_fixture_claims.py`・`test_script_imports.py`・`test_count_how_copies.py`・`test_input_reads.py`（`ports` の口に向け直す）・`test_unread_named.py`（同じ）。
- `tests/shared/`: `test_archon_contract.py`・`test_child_pointer.py`・`test_childsweep.py`・`test_fence.py`（埋めは残る。`boundary.py` の代わりに `ports.py` を読む。4.5-8）。
- `tests/e2e/` の全部（`test_line_scenarios.py` と line の筋書きは新しい line の筋書きの試験 `tests/blocks/line/` に置き換えて消す。`test_evidence.py` は棚卸しへの照らしの部分を消し、書き手の指し `writer` の `path::名` の照らしだけを残す。4.2-1f）・`tests/bin/` の全部（`linescripts.py` は書き直す。line の `src/` はパスで読む。4.5-7）・`tests/calibration/` の全部（`nodes.py` の node の id と判定の控えの道を新しい place に合わせる。4.3-15）・`tests/archon.py`（使い捨ての木に新しい pack を置く。`BLOCKS` の定数は `WORKFLOWS` に寄せる。4.5-11）・`tests/changed.py`・`tests/shard.py`。

## 10 keep-essence の 12 の仕組みと、守る block と試験

元の works の `works/docs/keep-essence.md` の 12 の仕組み。「今の守り」は組み込みの前の守り（作り直しの元として書く。組み込みで消えた物を含む）。「新しい守り」は組み込みの後の木に在る試験で、`path::名` の形で名指す（`tests/layers/test_keep_essence.py` が、どの項目も 1 つ以上の指しを持ち、その名が木に在ることを照らす。`docs/design/integration.md` の 4.2-1a）。

1. 赤緑の機械の判定 → 担う block fix（組の子の TDD の loop の中と、受け付けの後の確かめ直し）。読み手 report。今の守り `lib/tests/test_blk_fix_tdd.py` の `TestRedCheck`・`lib/tests/test_fix_gates.py` の `TestRedGreen`・`tests/workflows/test_test_gate.py` の `SuiteLoopCase`。新しい守り `tests/blocks/fix/test_tdd.py::TestUnitLoop.test_red_rejects_already_passing_test`・`tests/blocks/fix/test_fix_accept.py::TestLoopRedTree.test_red_tree_that_passes_is_a_miss`。
2. 元から赤のテストの区別 → 担う block test-gate。読み手 fix。今の守り `lib/tests/test_baseline_red.py`・`tests/workflows/test_test_gate.py` の `ResultScriptCase`。新しい守り `tests/blocks/test_gate/test_test_gate.py::ResultScriptCase.test_final_inherited_red_is_not_certified`・`lib/tests/test_baseline_red.py::JudgeCase`（KEEP）。
3. テストの凍結と、許す道は 1 本 → 担う block fix（TDD の loop が hash を取り、受け付けが確かめる）。許しを出すのは fix の裁定・plan・案の直し・範囲の相談。「1 本」は KEEP の `lib/conflict.py` の `test_permits` の 1 つの関数が担う（fix と、delta-review が使う KEEP の `planrange` の 2 つが呼ぶので lib に 1 つ。`docs/design/integration.md` の 4.3-追加-4・4.4-A）。今の守り `lib/tests/test_tdd_frozen.py` の `FrozenRuledScopeCase`・`lib/tests/test_conflict_kinds.py` の `TestReplanState`。新しい守り `tests/blocks/fix/test_frozen.py::PermitPathCase.test_permit_path_is_one`・`tests/blocks/fix/test_frozen.py::FrozenRuledScopeCase.test_change_outside_ruled_lines_is_rejected`。
4. 3 回拒まれたら諦める → 担う block fix（TDD の loop と修正の loop）と delta-review（手直しの loop）。loop の数え `lib/rolekit.py` は KEEP。今の守り `tests/workflows/test_fix.py` の `FixLoopScriptsCase` ほか。新しい守り `tests/blocks/fix/test_group.py::GroupChildScriptsCase.test_tdd_step_takes_the_red_and_gives_up_on_the_third_refusal`・`tests/blocks/delta_review/test_refix.py::RefixAcceptCase.test_gives_up_on_the_third_rejection_and_keeps_the_work_tree`。
5. 書き込みの出どころの突き合わせ → 担う block fix・delta-review（`lib/writes.py` は KEEP）。フックを置くのは `bin/`。今の守り `lib/tests/test_writes.py` の `TestProvenance`・`tests/bin/test_record_write.py`。新しい守り `lib/tests/test_writes.py::TestProvenance`（KEEP）・`tests/blocks/delta_review/test_refix.py::RefixAcceptCase.test_the_write_record_file_is_read_when_it_exists`。
6. 当たる試験を選んで回し、回さなかった試験を名で残す → 担う block fix。読み手 test-gate・line の最後の承認ノード・report。今の守り `lib/tests/test_impact.py`・`lib/tests/test_tdd_outside.py`・`tests/workflows/test_line.py` の `AskFinalReadsCase`。新しい守り `lib/tests/test_impact.py::ReverseImportCase`（KEEP）・`tests/blocks/fix/test_tdd.py::TestAcceptOutsideTier.test_tests_left_out_are_named_as_left_to_ci`・`tests/blocks/line/test_gates.py::AskFinalCase`（最後の承認ノードが回さなかった試験を名で並べる。元 `test_line.py` の `AskFinalReadsCase`）。
7. class_query の数え直し（判定役が欠陥ごとに書く探し方〔grep の型と対象のパス〕で、修正の前と後の件数を機械が数え直す）→ 探し方を作るのは diagnose、数え直すのは fix（KEEP の `lib/recount.py`）。今の守り `lib/tests/test_judge_accept.py` の `JudgeTakeCase`・`lib/tests/test_fix_units.py`・`lib/tests/test_fix_seams.py` の `RecountSeamCase`。新しい守り `tests/blocks/diagnose/test_judge.py::JudgeTakeCase.test_engine_recounts_the_class_query_total`・`tests/blocks/fix/test_ruling.py::RulingSeamCase.test_replace_query_is_tried_on_hits_misses_and_correct_lines`。通しの run の記録の照らしの表 `tests/e2e/evidence.json` の J70・J71・F122・F123 の行で、本物の run の記録に印が見えている。
8. 食い違いの申し出と、読むだけの裁定役 → 担う block fix（TDD の役も申し出を出す）。読み手 line の最後の承認ノード・plan-review・report。申し出の行の形は KEEP の `lib/conflict.py`。今の守り `lib/tests/test_conflict_kinds.py`・`lib/tests/test_fix_seams.py` の 3 本・`tests/layers/test_readonly_nodes.py`（裁定役が読むだけ）・筋書き `conflict-ask`。新しい守り `tests/blocks/fix/test_ruling.py::RulingSeamCase.test_accept_rule_rejects_then_gives_up_to_the_human`・`tests/blocks/fix/test_ruling.py::RulerTypeCase.test_decision_vocabulary_matches_output_format`（裁定役が読むだけなのは今も `tests/layers/test_readonly_nodes.py`）。
9. 独立設計と R1〜R4 → 担う block independent-design（修正案・判定・差分を運ぶ port を持たない形そのものが独立の守りになる。目的のほかに、前提の実測・人の承認ノードの答え・依頼が名指した節・人の方針・足した行の印は今の役も受けているので port に在る）。読み手 plan-review・r2。R1〜R4 は r1〜r4。今の守り `tests/workflows/test_plan_review.py` の `IsolationCase`・`tests/workflows/test_eyes.py` の `ShapeCase`。新しい守り `tests/blocks/independent_design/test_independent_design.py::PromptCase.test_prompt_carries_purpose_and_constraints_only`（組んだ指示が目的と前提の実測だけを運び、修正案・判定・差分を運ばない）・`tests/blocks/independent_design/test_independent_design.py::ShapeCase.test_inputs_carry_no_plan_judgment_or_diff`（入力の鍵の yes/no）。
10. 守りのファイルに触れたら最後の承認ノードを開く → 当たりを見るのは merge（seal の当たり）。読み手 line の最後の承認ノードと `bin/apply`。最後の承認ノードは組み込みの前も merge の当たりを読んでいた。eyes の写し（報告の落ちの控えだけ）は組み込みで消した（`docs/design/integration.md` の 4.5-13・4.5-18 の (c)）。今の守り `tests/workflows/test_merge.py` の `ApplyTest`・`lib/tests/test_protect.py`・筋書き `eyes-failed-protected`。新しい守り `tests/blocks/merge/test_merge.py::ApplyTest.test_no_answer_and_protected_hit_refuses`・`tests/blocks/merge/test_merge.py::SealTest.test_protected_hit_is_named`。通しの試験の小さな対象のリポジトリ（`tests/e2e/target-seed/`）は守りのファイルに触れない作りなので、この仕組みは本物の run ではまだ一度も通っていない。
11. 直す単位ごとの記録が報告と最後の承認ノードに届く → 書くのは fix（TDD の loop と修正の loop）、読むのは report と line。block をまたぐので、fix の出力 `units` の形と、report が `sections` で受ける形の両方を試す。今の守り `lib/tests/test_runreport.py` の `TddCase`・`tests/workflows/test_line.py` の `AskFinalReadsCase`。新しい守り `tests/blocks/fix/test_finish.py::CollectCase.test_tdd_unit_writes_one_body_for_all_groups`・`tests/blocks/report/test_sections.py::SectionsCase.test_unit_rows_reach_machine_and_detail_unchanged`・`tests/blocks/line/test_gates.py::AskFinalCase`（最後の承認ノードに単位ごとの記録が届く。元 `test_line.py` の `AskFinalReadsCase`）・`tests/blocks/line/test_gates.py::AskFinalCase.test_protected_hits_and_conflicts_open_in_every_mode`（守りのファイルの当たりと食い違いの申し出は、どの開き方でも最後の承認ノードを開く）。
12. 世界の解に照らす → 担う block world。読み手 diagnose・plan（行ごとに答えさせる）・plan-review（依頼を出どころにした外れを人に回す）・line の修正前の承認ノード。今の守り `lib/tests/test_world_check.py` の `Verify`・`lib/tests/test_blk_world.py` の `Classes`・`tests/workflows/test_plan.py` の `AcceptCase`・`tests/workflows/test_plan_review.py` の `WorldGateCase`・筋書き `world-offline`。新しい守り `tests/blocks/world/test_steps.py::Verify.test_verify_keeps_fetched_excerpt_and_caps_total`・`tests/blocks/plan/test_accept.py::AcceptCase.test_world_row_needs_answer`・`tests/blocks/plan_review/test_gate.py::WorldGateCase.test_deviation_cited_to_request_goes_to_human`。詳しくは [world.md](world.md) の 8 節。

## 11 作る順・並べ方・組み込み・確かめ

### 11.1 作る順

0. 土台と手本（1 本の PR。並べない）: guidance-path の目の block（8.6）・`blocks/` の pack の骨組み・`blocks/.shared/ports.py`・`prompt.py`・共通の指示の断片（外への検索の決まり・却下の段落・役の定義 5 本）・`blocks/AGENTS.md`・7.1 の形の検査・`tests/archon.py` と起動の殻で `blocks/` を pack として回す口・world の block・policy-check の入口（この時は world だけをつなぐ）。#765 の進め方 2 に当たる。土台の後、新しい形で guidance-path の目を 1 回回し、1 節の「変更が閉じる 1 か所」へ辿れない頼みがあれば、案内か手本を直してから次へ進む。
1. 1 波目（互いに独立。同時に作る）: purpose・premises・head-depth・spec・structure・independent-design・cold-read・test-gate・merge・report（`sections` の形は土台で決めず、report の PR が `schemas/sections.schema.json` を置く。ほかの block が守るのは 4.1 の `report` の欄だけなので、report を待たない）。素材の観点は、共通の部品と 1 本目（prior-decisions）を 1 本の PR にし、残りの 10 本を同時に作る。parallel-pr は素材の観点の共通の部品（素材の札の語と照らし）と断片 `works-gh`・`material-status`・`material-na` を使うので、その PR（共通の部品と prior-decisions）の後に作る（parallel-pr の設計書の 10 節の 2）。
2. 2 波目（1 波目の出力の形を使う）: diagnose（再審を含む）・verify・plan・plan-review（text の形を足し、policy-check に include を足す）・r1〜r4・lens。
3. 3 波目（修正の族）: delta-review・fix（TDD の loop を含む）。どちらも `lib/fixboard.py` の中身を自分の `src/` へ写す（`lib/tddloop.py` は fix だけ）ので、lib は触らず、写す範囲が重ならないように各設計書で割り当てる。
4. graph: judge と eyes のまとめ。
5. 組み込み（1 本の PR。並べない。11.3）。
6. 組み込みの後: drift-eye を足す。

並べ方の決まり:

- 各 PR が触るのは、`blocks/<block>/`・`tests/blocks/<block>/`・`docs/design/<block>.md` だけ。`lib/` の今のモジュールは読むだけで変えない（MOVE は写して置き、元は残す）。だから PR どうしは衝突しない。例外は、2 つ以上の block が使う新しいモジュールを `lib/` に足すこと（例 素材の観点の共通の部品 `lib/materialkit.py`）。足すのは最初に要った PR で、今のモジュールは変えない（`blocks/.shared/AGENTS.md` の `.shared` と `lib/` の分け）。
- 共通の指示の断片は土台が先に置く。足りない断片は、最初に要った PR が足す。同じ断片を 2 本の PR が同時に足さないよう、設計書の段で名を決める。
- 1 本の PR は block 1 つ（素材の 10 本だけは束ねてよい）。持ち主の決め `overnight-speed` は、この作り直しの間だけ効かせる（大きい PR・聞かずに merge）。

### 11.2 block ごとの確かめ（PR ごと）

- standalone の fixture（`archon workflow test`）が、port の値だけで最後まで届く。
- `tests/blocks/<block>/` の、script を子のプロセスで回す試験。始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡して prep・accept・出口を回す。
- 指示の比べ（11.4 の 1 つ目と 2 つ目の commit）。
- 設計書の keep-essence の番号の試験。
- 本物の単独の run を 1 回（費用のかかる試しは聞かずに回してよい。リポジトリの決まり）。

### 11.3 組み込み

組み込みの PR の前に、指示の新旧の比べを全部の node で 1 回通す。1 人の審査役が、全部の block の全部の AI の node について、古い指示と新しい指示を同じ値で組んで並べ、各設計書の「今の指示との差」の一覧どおりかを見る。block ごとの PR で 11.4 の 1 つ目の commit（日本語で同じ字）を作らなかった block（world・purpose）も、ここで比べる。指示の比べは、能力を守る 3 つ（keep-essence の割り当て・指示の比べ・e2e の筋書きと本物の run。9 節の頭）の 1 つなので省かない。

1. `blocks/line/` と `blocks/chain/` に新しい line と chain を書く。始めの記録を書き、block に port の値を配り、block の `report` の欄を集めて report に渡す。
2. line の筋書き（今の `workflows/line/fixtures/` の 36 本）を、新しい node の id に書き直す。
3. `workflows/` の古いサブグラフと `workflows/.shared/boundary.py` を消し、埋め（`fence.py`・`childsweep.py`・`child_pointer.py`・`skip_value.py`）を `blocks/.shared/` へ移す。`child_pointer` は `boundary` の代わりに `ports` の公開の口 `inside(rel, root)` を読む形に直し、chain が直に import する（integration.md の 4.5-1）。
4. `blocks/` を `workflows/` に入れ替える（`git mv`）。`pack.json` の `ours.folder` はそのまま。試験の `BLOCKS = ROOT / "blocks"` の定数は全部 `tests/archon.py` の `WORKFLOWS` に寄せ、2 つ目の pack を選ぶ環境変数 `WORKS_FACTORY_FOLDER` とその試験は消す（入れ替えの後に役が無い。integration.md の 4.5-11）。試験のフォルダ `tests/blocks/` の名はそのまま。
5. 9 節の DELETE と MOVE の元を lib と試験から消し、KEEP の物から文を md へ出す。段の語 4 つ（`lib/depth.py` の `LIGHT`・`STANDARD`・`HEAVY`・`HEADS`）は、`depth` を line へ移す前に `lib/headdepth` へ移す（9.3）。
6. 根の `AGENTS.md` と `workflows/AGENTS.md` を、憲法 6 行と、決まりとパスだけの短い形に書き直す。決まりの中の試験の仕様は試験の docstring へ、設計の細目は `docs/design/` へ移す。`docs/design.md` は `docs/design/` に置き換える。
7. `bin/_lib/apply.py` が持つ差分の決まったパス（`merge/apply.diff`・`merge/sealed.diff`）を、pointer の先の名の末尾（`apply.diff`・`sealed.diff`）の照らしに替える（place は include の道で決まる。merge の設計書の 7 節）。
8. `lib/protected.json` の行のうち、作り直しで消える・移るパス（`workflows/.shared/boundary.py`・`tests/shared/test_boundary.py`・`tests/layers/*.py`・`tests/layers/seeds/**` など）を直し、守りの関門の新しい住処を足す。行を足す・消すのは人だけ（`protected.json` の `about`）なので持ち主に諮り、5 行を直して 3 行を足す案に答えを得た（持ち主の決め `protected-rewrite-765`。integration.md の 4.3-14）。直さなければ `lib/tests/test_protect.py` が赤になる。

### 11.4 確かめ（組み込みの後）

- 指示の比べ: #764 の 2 つの commit の形を block ごとの PR で使う。1 つ目の commit は、md を日本語のまま作り、同じ値で組んだ新しい指示が古い指示と同じ字になること（空白と改行の違いは除く）を試験で確かめる。この試験は 2 つ目の commit（英語にする）で消す。2 つ目の commit では、古い指示と新しい指示を同じ値で組んで並べた物を PR に載せ、設計書の「今の指示との差」の一覧どおりかを審査が見る。英語にするだけでなく見方も変える block（例 structure。持ち主の 2026-10-19 の追加）は、3 つ目の commit を足してよい（1 つ目 日本語で同じ字・2 つ目 英語・3 つ目 新しい見方）。訳の差と見方の差を同じ commit で並べると、審査が差の一覧どおりかを分けて見られない（structure の設計書の 11 節の 3）。組み込みの前には、全部の node を通した比べをもう 1 度回す（11.3 の頭）。
- e2e の筋書き: line の筋書きの試験 `tests/blocks/line/`（AI の返答を台本で差し替えて line 全体を回す。組み込みの前の `tests/e2e/test_line_scenarios.py` の後継）が緑。
- 本物の run を 1 回: 小さな依頼を新しい line で回し、`tests/e2e/evidence.py check` で keep-essence の印を照らし、報告と承認ノードの文が日本語で出ることを確かめる。

## 12 持ち主の決めの変更

`docs/owner-decisions.md` の「2026-10-19 の決め」に、次の 7 件を書いた（最後の 2 件 `gate-efficacy-outside-judge`・`protected-rewrite-765` は組み込みで足した）。

- `block-local-code`: 1 つの block だけが使うコードは block のフォルダに置き、`lib/` は 2 つ以上が使う物だけ。今の E4 の「script は lib と境の口を呼ぶだけ」を置き換える。
- `lib-port-ended`: `lib-port-as-is`（元の名と元の中身のまま持ってくる。要らない物は最後の掃除の段で消す）を終える。最後の掃除はこの作り直しの組み込みが担う。
- `rules-tests-design-apart`: 決まり・試験の仕様・設計を分けて書く。憲法は AGENTS.md の頭に数行。
- `shape-checks-only`: 数の歯止め・閾値・許す物の表を検査に使わない。機械の検査は yes/no の形の決まりだけ。
- `rebuild-speed`: `overnight-speed` はこの作り直しの間だけ効かせ、組み込みの後に外す。`simple-software` に沿って、層の検査のコードを置き場の形に置き換えて小さくする。
- `gate-efficacy-outside-judge`: 試験と関門の効き目の計測（gate-efficacy）は判定の中で回さず、重い試験は run の外か CI に任せる。judge の graph は gate-efficacy を include せず、入力 `gates` も持たない。
- `protected-rewrite-765`: 守りのファイルの一覧 `lib/protected.json` を新しい置き場に合わせて書き換える（5 行を直し、3 行を足す。11.3 の 8）。

## 13 根拠を書いて自分で決めた事（持ち主に聞かない物）

- 作り直しの間の置き場を、2 つ目の pack `blocks/` として今の `workflows/` と別に読ませる。根拠: Archon は pack をまたいで workflow のファイルの名が重なると誤りにする（3 節）。別に読ませれば最後の名（`works-factory-plan` など）を初めから使え、組み込みは `git mv` で済む。仮の名で `workflows/` に並べると、組み込みで全部の名を付け替える手間が増える。払う物は、起動の殻の引数 1 つ（後に引数でなく環境変数 `WORKS_FACTORY_FOLDER` にし、組み込みで外した。下の「土台（11.1 の 0）で決めた事」の節）。
- 再審は diagnose の block に同居させる。根拠: 持ち主の決め `rejudge-cohabit`。
- 守りのファイルに触れたかを見る所（keep-essence の 10）は merge に置く。最後の承認ノードは組み込みの前も merge の封じの当たりを読んでいた。eyes の中に在った同じ数えの写し（読むのは、報告が落ちた時に機械が代わりに書く控えだけだった）は消す（integration.md の 4.5-13・4.5-18 の (c)）。根拠: 守りの当たりは差分を確定する所の事実で、独立の目の観点ではない。最後の承認ノードと `bin/apply` の拒みが読む事実は変わらない。
- 1.3 の変更の歩かせで訳なく散った所から、形を 8 か所直した（詳しい訳は 1.3 の「形の直し」）。根拠はどれも、持ち主の決め（block はほかの block を名指さない・1 つの block だけの物は block に・機械の検査は yes/no だけ）と、変わりやすい決めを 1 つのモジュールに隠す情報隠蔽（1 節の Parnas）と、#765 の本文。
  - block の `workflow:` は自分を子の run として起こす形だけ許す。根拠: #765 の本文が fix の自分を子として呼ぶ形を「手本として残す」と書いた。ほかの block を名指さない。
  - tdd は fix の中に置き、独立の block にしない。根拠: block は `include:` を持てない。keep-essence の 3 の「1 本」が block をまたがない。
  - 同じ block の node どうしの断片は block の `prompts/parts/` に。根拠: 憲法の 4 と同じ決め方。
  - 2 つ以上の block が読む行の形（block の出力の配列の 1 行ずつが持つ欄・語と、行を読む述語）は、作り手の出力ごとに `lib/` の 1 モジュール（手本 `worldmark`）。根拠: 憲法の 4。読み手が作り手の中身を import しない。
  - 深さの表を、未知の種類 → 段（`lib/headdepth`。head-depth・diagnose・plan が読む）と、段 → 回す物・上げ直し（line）に割り、fix の中の上げ直しを無くす。根拠: 上げ直しの読み手が 1 つになる。delta-review は fix の外の block。
  - 計画の往復の記録は line が持ち、plan-review は前の周を port `prior` で受ける。根拠: 往復の loop を持つのは line。前の周を見ないと決まらない確かめ（穴の出自〔審査が挙げた穴が、前の周の案の直しから生まれたか〕・続いた穴〔前の周の穴が直らずに残ったか〕）が plan-review に在る。
  - 直した後の実測は structure の block（`mode` after）に。graph は流れの決めだけを持つ。根拠: 観点の計算を graph に置くと、能力の棚卸し（`docs/plans/2026-10-13-capabilities/` の、能力ごとの行）の担い手が graph になり、graph が流れの決めだけを持つ形が崩れる。
  - block の外の文書は関数の名を書かない。根拠: block の中の作り替えで block の外の文書が動かない（`2a21ac3b` で `owner-decisions.md` が動いた）。
- 報告の文は事実を持つ block が組んで出力の `report` の欄で返す。根拠: 持ち主の決め（block はほかの block を名指さない・1 つの block だけのコードは block に置く）の下では、report が各 block の中身を import する今の形を続けられない。drift-audit の 3 節の直し方 1 と同じ。

### 土台（11.1 の 0）で決めた事

土台の PR で、文書のままでは決まらなかった所を、リポジトリの事実と Archon の源（`factory/pack.json` が止めた版 `a972888a`。取り置きは `~/.cache/works-factory/archon/a972888a…/`）で決めた。

- 起動の殻で `blocks/` を読ませる口は、環境変数 `WORKS_FACTORY_FOLDER=blocks`（根の直下のフォルダの名だけ受ける）。`bin/_lib/place.py` の `workflow_source` に引数 `folder` を足した。根拠: 殻は Archon の命令の別名と自分の旗を作らない（持ち主の決め `one-launcher`。旗は命令の前に置けない `require_command_first`）。殻の切り替えは今も環境変数（`WORKS_FACTORY_HOME`・`WORKS_FACTORY_NO_AUTH`）。続ける命令は run が始めに写し取った pack から走るので読まない。 組み込みの入れ替えの後は役が無いので外した（integration.md の 4.5-11）。
- block の試験のフォルダは `tests/blocks/<block の名の - を _ にした物>/`（例 `tests/blocks/guidance_path/`）。根拠: Python の package の名は `-` を持てず、unittest は package でないフォルダを黙って見つけない（`tests/AGENTS.md`）。名の写し方は `tests/blocks/kit.py` の `tests_of` 1 か所で、形の検査（7.1 に足した 10）がフォルダの在りかを照らす。
- 2 つ以上の block が使う port の形は `blocks/.shared/schemas/<名>` に 1 つ置き、入力の説明と `ports.json` で `json(shared:<名>)` と名指す（土台は `request.schema.json` を置いた。world が最初の使い手）。block だけの形は今どおり block の `schemas/`。同じ名の形のファイルが pack の 2 か所に在れば形の検査（7.1 の 5）が赤。根拠: 憲法の 4（2 つ以上の使い手は共通の住処）。断片の `{shared:…}` と同じ書き方にして、探す順の決まり（block を先に見るなど）を作らない。足りない共通の形（`constraints.schema.json` など）は、最初に要った PR が足す。
- `lang` が空の時の言語の文は、共通の断片 `blocks/.shared/prompts/lang-default.md` に 1 つ置き、`prompt.lang` がそれを読む。根拠: 憲法の 2（AI に届く決まった文は md だけ）。値の口 `{lang}` に入る文なので `{shared:…}` では入れない。
- 共通の断片の名は `blocks/.shared/AGENTS.md` に今在る物（`rejected`・`query-rule`〔段落 `spawns`〕・`lang-default`・役の定義 `role-judge`・`role-blind-judge`・`role-cold-reader`・`role-inspector`・`role-investigator`）と取り置いた物（`resubmit`・`policy`・`design-premises`・`works-gh`・`material-status`・`material-na`・`material-where`・`material-readonly`・`handoff`・`report-head-check`）を並べる。取り置いた物は最初に要った PR がその名で足す（11.1 の「同じ断片を 2 本の PR が足さない」）。役の定義のうち外への検索を持つ役（judge・investigator）は、断片の中で `{shared:query-rule}` を入れる（写しを持たない）。
- system prompt の文も md に置く: `prompts/<node-id>.system.md`。`prompt.render`・`emit` が同じ値と `when` で組み（値の有無は 2 本の和で数える）、prep の出力の欄 `system` で返し、YAML は `systemPrompt: "$<prep>.output.system"` だけ。根拠: 憲法の 2（今の r2 は YAML の `systemPrompt:` に文を持つ）。止めた Archon は `systemPrompt:` を `prompt:` と同じに解く（`dag-executor.ts` の「`systemPrompt:` and `agents.*` go straight to the provider, so they resolve exactly as a `prompt:` does (#2476)」）。形の検査（7.1 の 1・2）が片方だけの物を赤にする。
- `prompt:` に `$<prep>.output.prompt` で入れた指示の中の `$…`（対象の文の `$ARTIFACTS_DIR` など）は、止めた Archon が読み直さない。源で確かめた: `executor-shared.ts` の `substituteWorkflowVariables`「Every variable and every `options.references` grammar resolves in one scan of the template: a substituted value is inserted verbatim and never read as template syntax」、`output-ref.ts` の `substituteTemplate` は 1 回の走査。`with:` の値も同じ 1 回の走査（`dag-executor.ts` の `resolveValueTemplate`「in one pass」）。今の落とし穴 R44（読み直し）は、この版より前の Archon の振る舞い。だから指示をファイルに書いて役に Read させる形にはしない（道具を持たない役が受け取れなくなる）。world の standalone の筋書きが、依頼の字の `$ARTIFACTS_DIR` が字のまま AI の node に届くことを照らす（版の上げで崩れたら赤）。それでも、前の回の却下の文は `with: {reason: $LOOP_PREV…}` で運ばず、prep が自分の place の却下の控え（`lib/rolekit` の `rejects-<名>.json`）から全部を読む。根拠: resume で輪が 1 周目から回り直しても却下を数え直さず、#351 の「却下の理由を古い順に全部渡す」が 1 つの読み口で済む。
  - block の設計書のいくつか（independent-design・structure・report・gate-efficacy・hygiene・procedure-trace など）は土台より前に書かれ、Archon が値の中の `$…` を読み直す（R44）と書いている。止めた版ではこの確かめが勝ち、読み直しを避ける書き方（md の字から `$` を外す言い換え・抜き書きに `$` を含まない所を選ばせる文）は要らない。害は無いので、外すかは block を作る時に決めてよい。読み直しが版の上げで戻れば、world の standalone の筋書きが赤になる。
- place は作るだけで、消さない。block の入口は place の中の自分が名を持つファイル（`src/` の定数と `<node-id>-prompt-*.md`）だけを消す。根拠: 単独の run では place は run directory の根で、Archon とほかの node の物も同じ所に在る。今の `worldblk.intake` は自分だけのフォルダを丸ごと消していた。
- include の道は、`ARCHON_NODE_EXECUTION` の `path` の段（`.` 区切り）ごとの、最後の `__` より前を順に継ぐ。根拠: 止めた Archon は loop の本体の node の path を `<loop の id>.<node の id>` にし（`dag/run-context.ts` の `beginExecution` が `stepNamePrefix + node.id`）、include の展開は loop の本体の id に頭を付けない。今の `boundary.own_prefix` は最後の段だけを読むので、include の中の loop の本体の node の道を落とす。
- dry-run（`workflow test`）は `ARCHON_NODE_EXECUTION` の `path` に node の id だけを渡す（`dry-run.ts` の `path: node.id`）。だから graph の筋書きで、include した block の loop の本体の script を `exec-code` で走らせると place を取り違える。graph の筋書き（policy-check）はその本体を差し替えて配線だけを見て、block の中の道は block 自身の筋書きが見る。
- 7.1 の 3（md が standalone の値で組める）は、standalone の筋書きの形（`exec-code: true`・prep を差し替えない・AI の node を全部 `reached` に持つ）と、Archon の `workflow test` が全部の筋書きを通すことの 2 つで照らす。根拠: prompt の値は port の値から prep が組むので、md を値で組めるかは prep を本当に走らせないと決まらない。`resolved-text-contains` で、組んだ指示が AI の node に届いたことも照らせる。値の有無は段落の真偽に依らず md の全部の口で数える（prep はいつも同じ組の値を渡す）。
- 7.1 の 6 の「block」と「graph」の見分けは、ほかの workflow を名指すか（`include:` か、自分の外を指す `workflow:`）で決め、名指す物は AI の node を持たない、と検査する。根拠: 名の表で分けない（持ち主の決め `shape-checks-only`）。graph の定義（観点の判断は block に置く）をそのまま形にした。
- 今ある yes/no の検査（E6・E7・E12・E16・E19）は、`tests/layers/scan.py` を書き直さず、`blocks/` を `workflows/` の場所に写した一時の木に当てる。E1 は使い捨ての木で `archon validate` に通す。考えの住処の柵（`docs/concepts.json`）からは `blocks/**` を外した（表の `loosened` に訳）。根拠: 柵と既知の漏れの表は組み込みで消す（9.4）。新しい置き場は 7.1 の検査が縛る。
- block の返りの `ok`（`outcome_field:`）は「block の仕事が最後まで回ったか」。world では `status` が `ok` か（world.md の 1.2）。今の `world-finish` はいつも `ok: true` を返していたので、ここだけ振る舞いが変わる（judge のまとめが `ok` を読む時に決める）。
- guidance-path の読み手は、頼みごとに新しい会話（`loop_group` の `fresh_context: true`）で起こし、閉じるべき所を見せない。案内の直しは別の役（読み手と別の会話）が出す。設計は [guidance-path.md](guidance-path.md)。
- 設計の頭の語の「Archon の源」の置き場（`~/.local/state/works-factory/archon-src/d97d00ef…/`）は、`factory/pack.json` が今止める版（`a972888a`）と違う。土台はどれも `a972888a` の源で確かめた。

### 土台の審査（PR #770）と guidance-path の初めての本物の run（fb59418a。7 件のうち当たり 1）の後に決めた事

- YAML に指示の文を置く鍵を `blocks/` で禁じる: `loop:` の node（AI の役の指示を YAML に書く。`loop_group` と prep で足りる）・`agents:`・`on_reject` の `prompt`・`decisions` の `rework` の `prompt`。形の検査（7.1 に足した 11）が赤にする。根拠: 憲法の 2。今の 7.1 の 1 は `prompt:`・`command:` の node しか見ていなかった。
- 7.1 の 3 を締めた: どの AI の node も、`exec-code: true` で prep を差し替えない筋書きのどれかで `reached` に在り、その筋書きの `resolved-text-contains` が node の md の決まった文（断片を入れ、差し込み口と段落の印で割った一続き）の中に在る。standalone の筋書きの AI の node の `resolved-text-contains` は全部決まった文。根拠: prep が md を使わずに文を組んでも、前の検査は通った。値で照らす `resolved-text-contains`（world の `$ARTIFACTS_DIR` の照らし）は standalone の外の筋書き（`web-on`）に置く。「AI の node を全部 standalone の `reached` に」は外した: web の on と off で別の役が回る world のように、1 本の筋書きで全部の役に届かない block がある。
- `ports.json` は、形のファイルが照らし（`engine.schema.validate_schema`）の知らない語（`anyOf`・`oneOf`・`format`・`$ref` など。`KNOWN_KEYWORDS` の外）を持てば、語の在りかを名指して拒む。形の検査も pack の全部の形のファイルに同じ照らしを当てる。根拠: 照らしは知らない語を黙って飛ばすので、書いた形が効かないまま通る（持ち主の決め `no-silent-loosen`）。
- `ports.picked(raw, names, optional=())`: names の欄が作り手の出力に無ければ `KeyError`。無くてよい欄は optional に名指す。根拠: 欄の名の打ち違いと作り手の欄の消えを、黙って None にしない（今の `boundary.picked` は None にした）。
- `ports.place()` は `ARCHON_NODE_EXECUTION` が JSON でなければ落ちる（place を run directory の根と取り違えない）。`prompt.round_of(node_id)` は place の指示のファイルの数から輪の何回目かを返す（prep が回の数えを持たない）。
- world の web が off は道具で守る: `pick` が `web` を返し、`world-judge-loop`（web の検索と取得）と `world-judge-offline-loop`（道具なし）のどちらか 1 つだけを `when:` で回す。2 つの役の指示は同じ md（`prompts/parts/world-judge.md`）から組む。loop の本体の node の `when:` で外の node を読む形（双子の node を同じ輪に置く形）は取らない（本体は閉じた小さな DAG で、外の node の出力が見えるかを確かめていない）。
- 依頼の行の port は共通の口 `blocks/.shared/requestrows.py` で読む: 形（`shared:request.schema.json`）の後に `lib/carry.parts` を通し、知らない最上位の鍵・前の run の所見の下書きの行・pr と issue の番号の形を拒む（今の `worldblk._findings` の能力を戻した）。下書きの行は行の配列の形でも拒む（`carry.parts` は配列の形では見ないので、2 つの形で拒む物を揃える）。作り直しの間は `lib/` を変えないので `.shared` に置き、組み込みで `lib/` へ移すかを決める。依頼の行を読む後の block（purpose・premises・head-depth・spec・parallel-pr・diagnose など）はこの口を使う。
- guidance-path の読み手の隔離: 頼み（`requests`）は値そのものか pointer だけで受け、パスでは受けない（閉じるべき所を読み手の作業ツリーに置かない）。読み手の node は `denied_tools` の `Read(./<所>)` で、この目の block・試験・設計書と `.archon/` を読めない（Claude Code の Read の規則は Glob・Grep にも当たる。読み手は shell を持たない）。受け付けも、見せない所を開いたと言う返答と、見せない所を入口にする頼みを拒む。見せない所の並びは `src/steps.py` の `HIDDEN` と YAML の 2 か所で、試験が突き合わせる。
- guidance-path の `closes` に新しい block の名の口 `{new}`（試験のフォルダは `-` を `_` にした `{new_}`）を置ける。置いた所の全部で同じ 1 つの名に結ばれ、その名で埋めた所がまだ作業ツリーに無い時だけ当たる。根拠: 「観点を足す」（1.2 の N）の閉じる所は名がまだ無いフォルダで、`blocks/` と書くと既にある block の中に置いても当たりになった。
- guidance-path の入口は、place の中のこの block のファイルを名で引いて消す（頼みの id ごとの却下の控えも、前の intake と今の頼みの id から名を組む）。`rejects-*.json` のような広い形で消さない（上の「place は作るだけで、消さない」）。
- 本物の run の外れ 6 件の直し（案内の直し 15 件）は、`blocks/AGENTS.md`（変更の種類ごとに閉じる所・作り直しの間に触らない所・「全部の役」の意味）・`blocks/.shared/AGENTS.md`（`.shared` と `lib/` の分け・形の語・`query-rule` が検索と出典の決まりの全部）・共通の断片 `query-rule`（一次の出典を先に読む文を寄せた）・`lib/AGENTS.md`（7.2 の行）・根の README（`works-factory-world` が何か）・world.md（md の本文の写しを外し、空の依頼の返りと拒否を足す道を書いた）に当てた。設計書が md の本文を写さないのは、写しがあると直す所が 2 か所になり、読み手が設計書も直す慣わしと読んだため（1.2 の I は md 1 本で閉じる）。

## 未確認の一覧

- `prompt:` に大きい指示（数十 KB）を `$<id>.output.prompt` で入れた時に、Archon の出力の大きさの上限に当たらないか。
- dry-run が include の中の loop の本体の node に include の道を渡すようになるか（上の 13 章。なれば graph の筋書きでも本体を走らせられる）。
- Archon の workflow の頭に、全部の AI の node に効くモデルと effort の既定を書けるか（書ければ `d0b086a2` の形の 1 回きりの散らばりも 1 か所になる。1.2 の残る散らばり）。
- `archon workflow test` で、自分を子として起こす fix の全体の形を筋書きで通せるか（今は `fan_out` の所で落ちる。fix の standalone の fixture は組 1 つの形にする）。
