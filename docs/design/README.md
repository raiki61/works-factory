# 部品の作り直しの型（issue #765 の設計の正本）

- 何の話か: 工場（このリポジトリの Archon のワークフロー）の AI の役と観点を、単独で呼べる部品（block）に作り直す。その全部の block が従う型を、この文書が決める。block ごとの設計書は同じフォルダに 1 本ずつ置く。最初の 1 本は世界の解の [world.md](world.md) で、ほかの設計書はこれを写して書く。
- 決めたこと: block は新しい置き場 `blocks/`（2 つ目の pack）に横に並べて作る。block ごとに、それだけで回るかを確かめる。全部そろったら、1 回の組み込みで line を新しい block に切り替え、古いサブグラフを消す。指示は AI のノードごとに 1 本の英語の md に書き、Python は `{name}` に値を渡すだけにする。入力はポートとして、形と意味で宣言する。
- 持ち主に求めること: なし。持ち主の 2026-10-19 の決め・業界の定石・リポジトリの事実で決まらない物は残らなかった。自分で決めた事と根拠は 13 節。1 節の変更の種類の割り当ては履歴の分類から作った。1.3 の変更の歩かせは別の作業が埋める。

この文書の中の語（初出の物だけ。#763 の対訳に沿って英語の語はそのまま書く）:

- block: 観点 1 つ分のノードのまとまり。1 本の Archon の workflow（1 フォルダ・YAML 1 本）で、中に `include:` を持たない。単独の run としても、ほかの workflow から `include:` されても動く。
- graph: block を `include:` でつなぐ workflow。line（メイングラフ）・chain（周の鎖）・judge と eyes のまとめ・入口の workflow。graph は配線と小さな受け渡しの script だけを持ち、判断と計算は block に置く。
- port: block の入力（YAML の `inputs:`）と出力（`returns:` が名指すノードの `output_format`）。形（下の 4 節の form）と意味で述べる。
- place: block が自分のファイルを書く run directory の中のフォルダ。block ごと・include ごとに分かれる（4.4）。
- prep: AI のノードの直前の script のノード。材料を集め、md に値を入れて指示を組む。
- accept: AI のノードの直後の script のノード。返答を validation し、通さなければ却下の理由を返す。
- 今のサブグラフ: `workflows/<名>/` の今の 11 本（line・chain と 9 本）。作り直しの間は触らない。
- 元の works: `~/src/claude-plugins/works/`。工場の移植元で、参照するだけ（作り直しの目標ではない）。
- graphloops: `~/src/claude-plugins/graphloops/`。工場の形の元（`prompts/review-loop/p*.md` がノードごとに 1 本、`blocks/review-loop/<名>/block.json` と `exit.schema.json` が差し替えられる block）。
- Archon の源: `~/.local/state/works-factory/archon-src/d97d00ef…/`（`factory/pack.json` が止めた版）。以下 `A/` と書く。

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

- B 不具合直し → その block の `src/` と、その block の試験。fix の scripts と `lib/fixboard.py` の連動（74%）は、両方が fix の block の中に入って 1 か所になる。
- A 受け付けに確かめを足す → その block の `src/` の validation と、同じ block の `prompts/<node-id>.md` の 1 段落。どちらも 1 つの block のフォルダの中。
- I 指示の文を直す → その node の `prompts/<node-id>.md` 1 本。2 つ以上の node が使う文は `blocks/.shared/prompts/<name>.md` 1 本。
- N 観点を足す → 新しい block のフォルダ 1 つ。graph の配線の数行と、報告は block の出力の `report` の欄で済む（report の block は触らない）。
- P 入力を足す → 受け手の block の `inputs:` と `schemas/`（1 つの block）。graph の `with:` の 1 行は配線として必ず要る（ブロックはほかの block を名指さない、という持ち主の決めの代わりに払う物）。作り手は出力の欄を足すだけで、ほかの読み手の数だけ入力が増える形（drift-audit の 4 節）は、作り手ごとに出力を pointer 1 つで渡すことで止める。
- R 報告に 1 行足す → 事実を持つ block の `report` の欄だけ。`lib/runreport.py` が `gatemarks`・`fixboard`・`judge_accept`・`boardview` と連動して変わる形は、この置き方で無くなる。
- U 承認ノードと無人の方針 → line（graph）の `src/` だけ。承認ノードを持つのは line だけなので、方針の決め（今の `lib/gatepolicy.py`・`lib/gatemarks.py` の決めの部分）も line に置く。block は承認ノードの材料になる事実（欠陥・定石からの外れ・問い）を出力で返し、承認ノードを通すかは決めない。
- D 深さと往復の制御 → 深さの表（今の `lib/depth.py` の `TIERS`）と line の `src/`。block は「深さ」を知らず、line が表から引いた真偽（例 plan-review の `tree`・diagnose の `verify`）を port で受ける。往復の止め時（今の `lib/converge.py` の止めの部分）は、往復の loop を持つ line に置く。モデルと effort の群（`d0b086a2` の形）は、群の表 `lib/launchgroups.py` 1 つで、node の YAML は群の名を書くだけ（今のまま）。
- O 1 か所への寄せ → 種類そのものが減る。1 つの block だけの決めは block の `src/` に初めから 1 つ在り、2 つ以上の block の決めは `lib/` の 1 モジュールに置く（2 節の 4）。
- G 柵の保守・F run directory のファイル名 → 種類そのものが減る。名の住処と名の字の柵は消え（9 節）、形の検査は `tests/layers/test_block_shape.py` 1 本の yes/no（7 節）。place のファイルの名は block の `src/` だけが持つ。
- W 能力の戻しと縛り → その能力を持つ block の振る舞いの試験。能力の棚卸しの表（`docs/nodes.json`・`docs/works-parity.md`）と、それを照らす柵は消す（10 節の keep-essence の割り当てで替える）。
- `docs/design.md` の連動 → block ごとの設計書 `docs/design/<block>.md` 1 本。
- 1 か所に閉じない物（残る散らばり）:
  - S sandbox の node の鍵と V の全 node の鍵の足し（例 `8bb804fd` の retry）: Archon は鍵を node ごとに YAML に書くので、全部の block の YAML に及ぶ。7.1 の yes/no の検査が付け忘れを止める。共通の値を 1 か所に置く口は Archon に無い（（未確認）。Archon の workflow の頭の既定値で済む鍵があれば寄せる）。
  - C 較正は `tests/calibration/` の中で閉じていて、形に関わらない。

### 1.3 変更の歩かせ

> 予約。別の作業が、1.1 の代表の commit（`change-kinds.md` の 5 節の 12 件と、D の `d0b086a2`・`2351c7a4`）を新しい形の上で歩かせ、触るファイルを並べてここに書く（ATAM の変更容易性のシナリオの形。R. Kazman, M. Klein, P. Clements, "ATAM: Method for Architecture Evaluation", CMU/SEI-2000-TR-004, Software Engineering Institute, 2000）。2 か所以上に散る変更が残れば、形を直してからこの文書を確定する。

## 2 憲法

置き場: 組み込みの時に、根の `AGENTS.md` と `workflows/AGENTS.md` の頭に、下の 6 行だけを置く（作り直しの間は `blocks/AGENTS.md` の頭）。決まりの細目と試験の仕様は置かない（持ち主の決め `rules-tests-design-apart`）。

1. YAML はつなぐだけ。値はコードが計算し、判断は AI がする（Archon の憲法 `A/.archon/workflow-language-constitution.md` の "YAML coordinates. Code computes. Agents judge."）。
2. AI のノードの指示は、そのノードの md 1 本に英語で書く。Python は指示の文を持たず、md の `{name}` に値を渡す。
3. block は宣言した port だけで受け渡しし、ほかの block を名指さない。つなぐのは graph だけ。
4. 1 つの block だけが使うコードは、その block のフォルダに置く。`lib/` には 2 つ以上の block が使う物だけを置く。
5. どの block も、文とリポジトリだけで単独で回る。block ごとの standalone の fixture で確かめる。
6. 機械の検査は yes/no の形の決まりだけにする。数の上限や許す物の表では縛らず、間違った書き方を API と置き場の形で書けなくする。

## 3 置き場の形

```text
blocks/                          新しい pack（作り直しの間だけの置き場。組み込みで workflows/ に入れ替える）
├── AGENTS.md                    憲法 6 行と、手本の block（blocks/world/）を写せという案内
├── .shared/                     pack の共通の部品（Archon は dot のフォルダを workflow と見ない）
│   ├── ports.py                 port の読み・place・返り（今の workflows/.shared/boundary.py の後継）
│   ├── prompt.py                md に値を入れて指示を組む口（5 節）
│   ├── prompts/<name>.md        2 つ以上の node が使う指示の断片（外への検索の決まり・却下の段落・役の定義）
│   └── 埋め（fence.py など。組み込みの時に workflows/.shared/ から移す）
├── <block>/                     block 1 つ（例 world）。名は観点の名
│   ├── works-factory-<block>.yaml   YAML 1 本（グラフの名も同じ。E9）
│   ├── prompts/<node-id>.md     AI の node ごとの指示（英語。Archon は読まない。prep が読む）
│   ├── scripts/<name>.py        script の node（Archon が名で探す）
│   ├── src/                     この block だけが使う Python（package。scripts/ から import する）
│   ├── schemas/<port>.schema.json   json の port の形（4 節）
│   └── fixtures/                筋書き（standalone.stubs.yaml は必ず置く）
└── <graph>/                     graph（line・chain・judge・eyes・policy-check）。形は block と同じ（src/ も持てる）で、include を持てる
tests/blocks/<block>/            block の試験（今の tests/ の層ごとの鏡の形を続ける）
docs/design/<block>.md           block の設計書（この型に従う）
```

Archon の源で確かめた読み方（この形はこれに合わせた）:

- workflow は pack のフォルダの直下のフォルダ 1 つに YAML 1 本。YAML の無いフォルダ、dot で始まるフォルダ、`fixtures/` は workflow と見ない。2 本あれば誤り（`A/packages/workflows/src/workflow-discovery.ts` の `loadPackWorkflows`）。だから block は `blocks/` の直下に平らに並べる。入れ子の `blocks/judge/world/` は読まれない。
- `--workflow-source <dir>` の `<dir>/.archon/workflows/` の下の各フォルダが pack になる。workflow のファイルの名は pack をまたいで重なると誤り（同じファイルの `loadPackagedWorkflowsFromDir` の collision）。新しい block は最後の名（`works-factory-plan` など）をそのまま使うので、今の `workflows/` と同時には読ませない。作り直しの間は `blocks/` だけを pack にして回す。起動の殻 `bin/_lib/place.py` の `workflow_source` は `pack.json` の `ours.folder` を指すので、読ませるフォルダを選べるように引数を 1 つ足す（名は実装で決める）。
- `command:` の md は `<workflow のフォルダ>/commands/<名>.md` から探す（同じファイルの `resolveCommandContentForScan`）。block の指示の md は Archon に読ませず prep が読むので、`commands/` でなく `prompts/` に置く。生の型（`{name}` が埋まっていない物）が AI に届く道はこれで無くなる。
- 名の script は `<workflow のフォルダ>/scripts/` の 1 段下までの、知った拡張子のファイル全部で、名が重なると誤り（`A/packages/workflows/src/script-discovery.ts` の `MAX_SCRIPT_DISCOVERY_DEPTH = 1` と `discoverPackScripts`）。だから block の中の Python の部品は `scripts/` の下に置かず、`src/` に置く。
- Archon は run の始めに `.archon` の源を丸ごと写し取り、resume もその写しから走る（`A/packages/workflows/src/workflow-source.ts`）。`src/` と `prompts/` は写しに入るが、`lib/` は入らない（今の `boundary.lib_root` は環境変数 `WORKS_FACTORY_ROOT` から辿る）。block だけが使うコードを block に置くと、止まった run の resume が同じコードで続く、という利点もある。
- `include:` は読み込みの時の平らな展開。中の node の id は `<include の id>__<id>` になり、`returns:` の node が `$<include の id>.output` になる。`inputs:` に無い鍵と、欠けた必須の入力は読み込みの誤り（`A/packages/workflows/src/include-expander.ts` の頭の説明と、憲法の `inputs:` + `returns:` + `with:` の行）。

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
- どの block の返りにも、`outcome_field:` が名指す欄（block の仕事がうまくいったか）と、欄 `report`（報告に載せる日本語の行の配列）を置く。報告の文は事実を持つ block が組み、report の block は並べて継ぐだけにする。今の `lib/runreport.py` が lib の 43 モジュールを import する集め口になった崩れ（`~/.cache/works-self/tmp/drift-audit.md` の 3 節）を、この形で閉じる。

### 4.2 文とリポジトリだけで単独に呼ぶ

- 単独の run は Archon の `workflow run <名> --input <name>=<value>` で起こす（`A/packages/cli/src/help.ts` の `--input <name>=<value>`。入力ごとに繰り返す）。リポジトリは run の作業ツリー（Archon の cwd）で、port ではない。
- 工場の run の記録（今の始めの記録 `start` のポインタ）は、どの block も受けない。block が今その記録から読んでいる物（言語・web の切り替え・人の方針・試験のコマンド・差分の base commit など）は、block ごとに要る物だけを、既定の値つきの port にする。
- `ports.py` の読み手は、値を 3 通りの形で受ける: その run の pointer、ファイルの絶対パスか作業ツリーからの相対パス、値そのもの（`json` と `text` の form）。読めない pointer や在らないファイルは、空にせず理由を名指して落とす（今の落とし穴 K15 と持ち主の決め `no-silent-loosen`）。
- script は入力を `os.environ.get("INPUTS_<名>")` の字のままで読み、その値を `ports` に渡す。名を組んで読まない。Archon は uv の script の源のこの字の形を読み込みの時に照らし、結ばれていない入力を読む workflow を走る前に拒む（`A/packages/workflows/src/exec-input-validation.ts` の `scanEnvironmentReads`）。名を組むと、この照らしが効かなくなる。
- graph の中では、作り手の block の出力の欄を受け手の `with:` で渡す（今と同じ）。include の `with:` は値を JSON の字で運ぶ（埋め P2）ので、受け手は `json` の form で読む。
- 受け手が作り手の欄を 3 つ以上読む時は、欄ごとに入力を足さず、作り手の返りを丸ごと置いたファイルの pointer 1 つを `json` の入力 1 つで受け、読む欄は受け手の `src/` が名指す。作り手が欄を足すたびに読み手の数だけ入力が増える形（drift-audit の 4 節。サブグラフの入力の和が 85 から 142 に増えた）を止める。

### 4.3 run の記録を前提にしない

- block は自分の place と、port の値が指すファイルのほかは開かない。`ports.py` は run directory の根（`ARTIFACTS_DIR`）を script に渡さない。
- 前の段の失敗を伝えていた止めの記録（今の `judge/stop.json`）は使わない。block を回すかは graph の `when:` が決め、block は自分の結果を `outcome_field:` と出力の欄で返す。

### 4.4 place（block ごとの run directory）

- `ports.place()` は `$ARTIFACTS_DIR/<include の道>/` を返す。include の道は、自分の node の実行の記録（`ARCHON_NODE_EXECUTION`）の id から、最後の `__` より前を `/` でつないだ物（今の `boundary.own_prefix` と同じ読み）。単独の run では空で、`$ARTIFACTS_DIR/` になる。
- 同じ block を 2 回 include すれば、place も 2 つに分かれる。今の judge と plan-review が同じファイルを取り合う所（棚卸し `~/.cache/works-self/tmp/inventory-765.md` の 5 節）は、この形で無くなる。
- place の中のファイルの名は block の `src/` だけが持つ。ほかの block が読む物は、出力の欄の pointer で渡す。名の住処（`lib/*beside.py`・`lib/fixnames.py`）と、名の字を探す柵は要らなくなる。

## 5 指示の組み立て

### 5.1 md の書き方

- 1 つの AI の node に、`prompts/<node-id>.md` を 1 本置く。決まった指示の文は全部ここに英語で書く。
- 値の差し込み口は `{name}`（小文字・数字・`_`）。JSON の例の `{"a": 1}` は形が合わないので、差し込み口にならない。
- 2 つ以上の node が使う段落は `blocks/.shared/prompts/<name>.md` に 1 本だけ置き、`{shared:<name>}` で差し込む。今 21 本の md に写されている外への検索の決まり（`lib/agents/judge.md:16-22` が元）と、4 通りに割れた却下の段落は、ここで 1 つになる。
- 差し込むかを選ぶ段落は `<!-- if <name> -->` と `<!-- end <name> -->` で囲む。逆の条件は `<!-- if not <name> -->`。入れ子にはしない。

### 5.2 組み立ての口

- prep は `prompt.render(node_id, values, when)` だけで指示を組む。口は、呼んだ script の在る block の `prompts/<node_id>.md` を自分で探し、パスも文も受けない。
- 口は次の時に落ちる: 値の無い `{name}` が在る・使われない値を渡された・`when` の名が md に無い・md の `if` に `when` の値が無い・`{shared:…}` の先が無い。
- 組んだ指示は place の `<node-id>-prompt-<n>.md` に書く（`<n>` はloop の何回目か）。prep の出力の欄 `prompt` で返す。
- AI の node の YAML は `prompt: "$<prep の id>.output.prompt"` の 1 行だけにする。`command:` は使わない。道具を持たない役（world-classes など）も、指示をファイルから Read せずに受け取れる。
- 「Python は指示の文を持たない」は、この口の形で守る。AI に届く決まった文の在りかは md しか無く、審査は md を読めば済む。lib の Python の定数の長さを数える検査は置かない（持ち主の決め `shape-checks-only`）。

### 5.3 Python が持つ物と、md が持つ物

- md: 決まった指示の文の全部、決まった節の見出し、差し込むかを選ぶ段落の本文、差し込み口の名。
- prep（Python）:
  - 周ごとの材料（依頼の行・目的の文・前の回の返答・差分・人の答え）。
  - 材料の中で項目ごとに繰り返す短い見出しと札（例 `### Class w-459d38b29048`・`- Query:`）。
  - md と validation が同じ字を持つべき値（返答の欄の名・語・上限の数・目印の字）。定数は block の `src/` か `lib/` に 1 つだけ置き、md には `{name}` で入れる。
  - 段落を差し込むかの真偽。
  - 人に見せる欄の言語の値（port `lang`）。
- accept（Python）: 却下の理由の文。どの決まりに落ちたかで文が変わるので、Python に残す（#764 の求め 3）。却下の理由はloop を諦めた時に報告に載るので、人に見せる文として日本語のまま書く（#764 の「日本語に残す物」）。次の回の指示には `{shared:rejected}` の中の `{rejection}` として入る。
- 人に見せる欄の言語: md の中で、その node の人に見せる欄を名指し、`{lang}` で書けと言う。`lang` は port で受け、空なら今の既定（`lib/rolekit.py` の `LANG_DEFAULT`「依頼文の言語」）と同じ意味の英語の文を入れる。言語を自動で選ぶ仕組みは作らない（持ち主の決め）。

## 6 ノードごとの設計シートの型

block の設計書（`docs/design/<block>.md`）は、頭に block の全体（役・port・node の並び・place のファイル・コードの置き場・使う `lib/`）を書き、AI の node ごとに次の 9 項を書く。手本は [world.md](world.md)。

1. 役: 1〜2 行。
2. port: その node が読む物と、どの block の port から来るか。
3. 組み立ての順: md の節を上から並べる。節ごとに、決まった文か `{name}`（値の出どころ）か、差し込むかを選ぶ段落か（条件）かを書く。
4. 返す形: `output_format` の欄。人に見せる欄と、その言語。
5. 描いた骨組み: 本物の run の値を入れて描いた指示の骨組み（見出しと各節の頭の行）。run は `~/.local/state/works-factory/targets/<target>/archon-home/workspaces/<owner>/<repo>/artifacts/runs/<run>/` から選び、run の id を書く。
6. 今の指示との差: 移した物・まとめた物・消した物・足した物と、その訳。
7. 元の works と graphloops の同じ場面: 対応する物、工場に無い能力、消した時の PR（意図して外したかを工場の git の履歴で確かめ、PR の番号を引く。記録が無ければ（未確認））。
8. 受け付け: 却下の決まり、諦めるまでの回数、諦めた時に出口へ書く物。
9. 試験: standalone の fixture・指示の比べ（10.3）・振る舞いの試験・守る keep-essence の番号。

## 7 形の検査と案内

### 7.1 形の検査（どれも yes/no）

1. AI の node の `prompt:` は、同じ block の script の node の `$<id>.output.prompt` 1 つだけ。`command:` を持つ AI の node は無い。
2. AI の node ごとに `prompts/<node-id>.md` が在り、`prompts/` の md はどれもどれかの AI の node の物。
3. どの md も、その block の standalone の fixture の値で `prompt.render` が通る（埋まらない口も、使われない値も無い）。
4. どの block にも `fixtures/standalone.stubs.yaml` が在り、その `fixture.inputs` の鍵は block の `inputs:` の中にあって、pointer の値を持たない。
5. どの入力の `description` も `<form>: ` で始まり、`json(<schema>)` の `<schema>` が block の `schemas/` に在る。
6. block の YAML は `include:` と `workflow:` を持たない（graph だけが持つ）。
7. block の `scripts/` と `src/` に、字 `ARTIFACTS_DIR` と、ほかの block のフォルダへのパスが無い。
8. どの block の `returns:` の node の `output_format` にも、`outcome_field:` の欄と `report` の欄が在る。
9. `src/` の package の名は `src` で、`scripts/` の名と `lib/` のモジュールの名は重ならない（script のフォルダが `sys.path` の頭に来るため。今の E4 の決まりを続ける）。

今ある yes/no の検査は、`blocks/` にも当てて続ける: E1（`archon validate` が警告なしで通る）・E6（外への書き込みは 1 つの node）・E7（読むだけの node の印）・E12（期限を置かない）・E16（承認ノードの形）・E19（AI の node の retry）・uv の頭の宣言。数の表と許す物の表で縛る検査（`tests/layers/test_layer_map.py` の `known`・`ALLOWED` の表・名の住処の柵）は持ち込まない（9 節で消す）。

### 7.2 案内の AGENTS.md

直す人が立つ所に、短い AGENTS.md を置く。どれも決まりとパスだけを書き、設計の細目は `docs/design/` に置く。

- `blocks/AGENTS.md`: 憲法 6 行。「新しい block は `blocks/world/` を写して始める」。設計書の型はこの文書の 6 節。
- `blocks/.shared/AGENTS.md`: `ports.py` と `prompt.py` の口の一覧と、口を通さずに書けない物（入力の読み・place・指示）。
- `lib/AGENTS.md`: 「2 つ以上の block が使う物だけを置く。1 つの block だけが使う物は `blocks/<block>/src/`」。共通の部品の短い一覧（`jsonfile`・`oneline`・`rolekit`・`worldmark` など）。
- `tests/AGENTS.md`: block の試験は `tests/blocks/<block>/`。block の出力の見本は、block の `returns:` の `output_format` から作る助けで作る（今の試験ごとの写し `judgment(...)` の崩れ。drift-audit の 7 節）。
- 手本の block は 1 つ（world）にする。崩れたコードが「いちばん近い手本」にならないよう、古いサブグラフは組み込みで消す。

## 8 block の一覧

form は 4.1 の物。どの block も `lang`（`text`）を持つ物は書くのを省き、出力の `ok`（`outcome_field:`）と `report` も省く。詳しい port は各設計書で決める。

### 8.1 判定（今の judge を観点ごとに割る）

- world（世界の解）: 依頼の行を問題の類に言い直し、一次の出典の抜き書きで業界の定石と照合する。入力 `request` json（依頼の行）・`purpose` text・`means` json（依頼が示した解き方）・`web` choice(on|off)。出力 `rows`（pointer。行の形は `lib/worldmark.py`）・`status`・`reason`・`classes`・`dropped`。設計書 [world.md](world.md)。
- purpose（目的の固定）: run の元の目的を 1 文にし、依頼が示した解き方を分ける。入力 `request` json・`pr_text` text・`constraints` json（前提の実測。空でよい）。出力 `purpose`（purpose_text・source・known_weaknesses・source_files）・`means`。
- premises（前提の実測）: 依頼に書かれた数値・規模・在る/無いの主張を作業ツリーで測り直す。入力 `request` json・`carried` json（前の run が運んだ実測。空でよい）。出力 `constraints`。
- head-depth（run の頭の深さ）: 依頼の行ごとの未知の種類を引用つきで返し、機械が段を引く。入力 `request` json・`has_checks` flag・`thickness` choice・`spec` flag・`design_only` flag。出力 `tier`・`rows`。
- spec（仕様）: 要件と受け入れテストを書いて審査し、承認ノードの後に固める。中に人の承認ノードを持つ（単独で呼んでも人が答える）。入力 `request` json。出力 `spec`・`added_rows`（依頼に足す受け入れ条件の行）。
- parallel-pr（並行 PR）: 開いている PR と変更ファイルの交差を見て、ぶつかる所を外す。入力 `base` text・`changed` json・`request` json。出力 `excluded`・`drafts`。
- 素材の観点 11 本（prior-decisions・purpose-review・local-review・consistency-bypass・hygiene・external-standards・procedure-trace・gate-efficacy・test-double-fidelity・main-path-observation・provenance）: 1 本ずつ block にする。どれも同じ型（prep・役・accept）で、共通の部品は `lib/` の 1 モジュールに置く（11 本が使う）。入力は観点ごとに要る物だけ（例: hygiene は `base` text だけ、prior-decisions は `request`・`purpose`）。出力 `material`（pointer）。
- diagnose（根本の診断と再審）: 素材をまとめて直す単位を切る。`objection` が空でなければ再審の道を通る。再審は同じ block に置く（持ち主の決め `rejudge-cohabit` の訳「再審が判定の置き場を外から前提にする」は、前の判定を port で受ける形で起きなくなるが、置き場は変えない）。入力 `request`・`purpose`・`materials` json・`world_rows` file・`constraints`・`row_asks` json（頭の深さが行ごとに返した問い）・`answers`・`objection` text・`prior` file（再審の時の前の判定）。出力 `judgment`（pointer）・`units`・`questions`・`ready`。
- verify（判定の裏取り）: 開いた単位ごとに、本当に根本か・証拠は在るかを別の目で確かめる。入力 `judgment` file・`materials` json。出力 `verify`。

### 8.2 計画と事前審査

- structure（構造の目）: 直しの単位を測り、直しが設計の考えを知る場所を増やすかを見る。今の見方（周りのコードと比べる）から、対象のリポジトリの書いた意図（憲法・決まり・設計の文書）と比べる見方に変える（持ち主の 2026-10-19 の追加。8.6 の 3 つの時の 2 つ目）。入力 `units` json・`intent` json（対象の書いた意図の文書のパスの一覧。空なら決まった名で探す）。出力 `structure`（pointer）。
- independent-design（R2 の独立設計）: 目的の文だけから別の役が設計する。入力 `purpose` text。出力 `design`（pointer）。
- plan（修正案）: 修正案を書き、事前審査の指摘で書き直す。入力 `judgment` file・`purpose`・`structure` file・`world_rows` file・`policy` file・`prior` file（前の周の案と指摘。1 周目は空）・`ruling` file（案の直しの時）。出力 `plan`（pointer）。
- plan-review（事前審査）: 案の欠陥を探す。`proposal` を案の構造（項目・ファイル）か、方針の文だけ（text）のどちらでも受ける。text だけの時は、案の構造を前提にする確かめを飛ばし、8 種の確かめと欠陥の重さの定義だけを当てる（入口の workflow のため。棚卸しの 5 節）。入力 `proposal` file か text・`purpose`・`design` file・`world_rows` file・`structure` file・`policy` file・`tree` flag（項目ごとの下請けで木にするか。line が深さの表から引く）。出力 `holes`・`deviations`（定石や独立設計からの外れと、その出どころ）。承認ノードを聞かずに通してよいかは line が決める（1.2 の U）。

### 8.3 修正

- fix（修正）: 承認済みの案を項目ごとに直す。範囲の相談・食い違いの裁定・組どうしの合わせを含む。入力 `plan` file・`judgment` file・`policy` file・`test_cmd` text・`baseline` file。出力 `diff`（pointer）・`closure`・`conflicts`・`permits`。
- tdd（TDD のループ）: 単位ごとに赤から緑まで回し、赤緑を JUnit の結末で機械が判じる。入力 `brief` file・`test_cmd` text・`tdd_suite` text・`baseline` file・`permits` json。出力 `units`（単位ごとの記録）・`frozen`（テストの hash）。
- delta-review（差分の審査と手直し）: 差分を案の項目への準拠と品質で見て、2 往復まで手直しする。入力 `base` text・`plan` file・`lens_rows` file。出力 `holes`・`diff`。
- lens（黙った失敗のレンズ）: 利用者が入れた review のレンズで差分を見る。入力 `base` text・`lenses` json。出力 `rows`（pointer）。

### 8.4 独立の目と関門

- r1（最小性とコメント）・r2（独立設計との比べと前提の検算）・r3（全体の整合）・r4（見えていない範囲）: 1 本ずつ block。入力はどれも `base` text（差分の base commit）と、観点ごとに要る物（r2 は `design` file と `purpose`、r3 は `intent` json と `policy`、r4 は `plan` file と `policy`）。出力 `verdict`・`questions`（人に回す問い）。
- test-gate（試験の関門）: 直す前と後の結末を取り、元から赤のテストを分ける。入力 `mode` choice(base|final)・`test_cmd` text・`tdd_suite` text・`baseline` file（final の時）。出力 `baseline`（pointer）・`green`。
- merge（差分の確定と取り込み）: AI を持たない。入力 `mode` choice(seal|apply)・`diff` file・`deliver` choice。出力 `sealed`・`protected_hits`（守りのファイルに触れた一覧。13 節）・`pr`。

### 8.5 報告

- report（報告を書く）: block の `report` の欄を並べ、結末の語を決め、書き手の役が本文を書く。入力 `sections` json（block ごとの `report` の欄を graph が 1 つに集めた物）・`facts` json（結末を決める事実）。出力 `report`（pointer）。
- cold-read（初見の読み手）: 文脈を持たない読み手が本文を読み、詰まった所を返す。入力 `text` file。出力 `stuck`。

### 8.6 3 つの時の目（崩れを入る前・入る時・入った後で見る）

- 入る前: guidance-path（案内の道の目）。文脈を持たない AI に典型の変更の頼み（例「この AI の役に確かめを 1 つ足す」「観点の block を 1 つ足す」「この node が AI に言う事を変える」）だけを渡し、リポジトリの入口から案内（AGENTS.md・設計書）と手本だけを頼りに辿らせ、どこに変更を置くか・何を写したかを記録する。1 節の「変更が閉じる 1 か所」に置けば案内が効いている。違う所に置けば崩れの入口なので、案内の直し（直す人が立つ所に案内を足す・手本を替える・間違った道を置き場で塞ぐ）を出す。手本は convergence-loops の firstread-loop（`~/src/claude-plugins/convergence-loops/` の、用事だけを渡されて入口から自分で探す読み役）。入力 `requests` json（頼みと、それが閉じるべき 1 か所の組の一覧）・`entry` text（入口のファイル。空なら `README.md` と根の `AGENTS.md`）。出力 `paths`（頼みごとの辿った道・置いた所・写した物）・`fixes`（案内の直しの案）。回す時: block を作り始める前に新しい形で 1 回、その後は案内か置き場の形を変えるたび。
- 入る時: structure（8.2）。PR の差分を、周りのコードでなく書いた憲法と比べる。
- 入った後: drift-eye（崩れの目。後で足す）。リポジトリの今を、書いた意図・業界の定石・履歴の傾きと比べ、崩れがどこから入ったかを辿り、置き場と案内の直しを出す。見つけた入口は、guidance-path の頼みの例に足して返す。入力 `intent` json（書いた意図の文書の一覧）・`window` text（履歴を見る範囲）。出力 `drifts`・`fixes`・`new_requests`（guidance-path に足す頼み）。

### 8.7 graph

- line（メイングラフ）: block を並べ、承認ノード・計画の往復・一度だけの include（案の直し・2 度目の修正・再審）・深さの上げ直し・無人の方針を持つ。始めの記録はここだけが書き、block には port の値として配る。
- chain（周の鎖）: line を周ごとに子の run として起こす（今のまま）。
- judge（判定のまとめ）: 8.1 の block を `include:` で並べ、line から 1 つの include で呼べるようにする。Archon 同梱の sdlc の `deliver` が `implement`・`review` を include で組むのと同じ形（`A/.archon/workflows/sdlc/deliver/archon-deliver.yaml`）。
- eyes（独立の目のまとめ）: r1〜r4 を並べ、まとめの判定の script を持つ。
- policy-check（方針の文だけを入れる入口。#765 の目指す形 4）: 方針の文を world と plan-review（text の形）で評価して返す。設計は [world.md](world.md) の 9 節。

## 9 収束した形での lib/ と試験の仕分け

- 仕分けは、収束した形（全部の block が `blocks/` に入り、古いサブグラフが消えた後）で何が要るかで決めた。lib の import の向きを機械で読んだ（`ast` で各モジュールと各 script の import を数えた。lib の中に 33 モジュールの import の循環があるので、推移で辿ると全部が全部に届く。そこで、直に import する script と、それを import する lib のモジュールの直の使い手までを見て、残りは docstring とコードを読んで決めた）。
- DELETE は 1 件ずつ確かめずに消す（持ち主の決め）。能力は 10 節の keep-essence の割り当て・指示の比べ・e2e の筋書きと本物の run で守る。
- MOVE は block の `src/` へ。作り直しの間は写しを block に置き、lib の元は古いサブグラフのために残す。組み込みで lib の元を消す。
- KEEP は 2 つ以上の使い手（block か graph か `bin/`）を書く。指示の文を持つ物は、組み込みで文を md へ出して軽くする（「文は md へ」と書いた物）。

### 9.1 lib/ の DELETE

- 名の住処: `eyesbeside`・`fixnames`・`judgebeside`・`planreviewbeside`・`structbeside`・`fixbeside`（読み手と `PORTS`。閉鎖の表を書く関数は fix の `src/` へ）。
- 指示を lib で組むための仕組み: `promptsection`（見出しの宣言と受け渡しの表）・`graphloops/engine/render.py`（graph の reads から指示を描く。定数 `FILE_CAP` は使い手へ移す）。
- 写した graph の型が持てない欄を足す仕組み: `marks`（返答の型は node の `output_format` が正本になる）。
- 使う所が無い: `graphloops/engine/pointers.py`（import する物が無い）。
- 写した graph の規則: `graphloops/engine/validator.py`（役の返答の形は `output_format` と block の accept が持つ。判定の受け付けがこの規則に頼る所を割る時に確かめる。（未確認））。

### 9.2 lib/ の MOVE（行き先の block）

- world: `worldblk`・`worldcheck`
- purpose: `purpose`／premises: `premises`／spec: `specblk`／parallel-pr: `prcheck`・`downgrades.json`（（未確認））／local-review: `diverted`
- judge の芯 `judge_accept`: 観点ごとの部分を各 block（world・purpose・premises・head-depth・spec・parallel-pr・diagnose・verify）へ割る。素材の 11 本が共に使う部分は KEEP（新しい 1 モジュール）。`judge/` の決め打ちの包み（`world_intake` など）と `PORTS`・`FIRST_PORTS` は DELETE。
- verify: `judgeverify`
- structure: `context`・`stage_a`・`structfile`・`design-row.schema.json`（（未確認））
- plan: `planfile`・`ripple`
- plan-review: `boardview`（独立設計の部分は independent-design へ）・`planblk`（修正案の役の部分は plan へ）
- fix: `clash`・`consult`・`factchecks`・`fixboard`（TDD の部分は tdd、差分の審査の部分は delta-review、レンズの部分は lens へ）・`fixgates`・`fixrules`（TDD の部分は tdd へ）・`lanekit`・`parking`・`planscope`・`ruling`・`unitrows`・`unittrees`
- tdd: `tddloop`（fix が呼ぶ関数が残れば KEEP。fix の設計書で決める）
- delta-review: `deltamarks`・`refix`・`refixrules`
- lens: `lenses`
- eyes（graph）: `eyeverdict`（観点ごとの部分は r1〜r4 へ）・`stage_b`
- report: `outcome`・`report_roles`・`glossary.json`
- line（graph の `src/`）: `fixture`・`startrec`・`testcmd_check`・`versions`・`gatepolicy`・`gatemarks`（承認ノードの決めの部分。修正案と事前審査に渡していた文は md へ）・`depth`（深さの表。block には真偽を port で渡す）・`latedepth`・`gate_axes`

### 9.3 lib/ の KEEP（使い手）

- `accept`（作業ツリーの写しと返答の照らし。役を持つ block の多く。写した graph の規則の部分は割る）
- `answer`（line・chain・`bin/`）・`chain`（chain・`bin/`）・`entry`・`entryshape`・`runbranch`（line・chain・merge）
- `baseline_red`（test-gate・tdd・fix・report）・`green_cert`（test-gate・merge・line・chain）・`declared_checks`（test-gate・report・line）・`suitewrite`（test-gate・line）・`checkscope`（test-gate・素材の観点）
- `carry`（line・chain・report・test-gate）・`changemap`・`COPIED_FROM.changemap`（line と `impact` の使い手）・`impact`（fix・tdd・plan・structure）
- `cite`（fix・diagnose・head-depth・plan-review・line）・`conflict`（fix・tdd・plan・line・report）・`converge`（plan・plan-review・line。往復の止めの決めは line の `src/` へ）・`replan`（fix・plan・line）
- `concepthome`（plan・plan-review・structure・r1・r3。文は md へ）・`conceptfence`（structure・r3。対象のリポジトリの表に当てる道具として残す）・`measure`（structure・eyes。コマンドとして起こす）
- `headdepth`（head-depth・line）・`launchgroups`（`bin/`・head-depth）
- `design`（independent-design・r2・plan-review）・`eye`（structure・eyes）・`structmark`（structure・plan・plan-review・eyes・line・report）
- `forge`（merge・parallel-pr・line）・`ghreads`（line・purpose）
- `globs`（fix・plan・eyes・merge）・`protect`・`protected.json`（eyes・merge・line）・`seal`（merge・eyes・line・chain・`bin/`）・`listcut`（eyes・fix・merge・structure・`bin/`）
- `groups`・`holeties`・`planrange`（fix・delta-review）・`itemcommits`（fix・merge・line）・`planbrief`（fix・tdd）・`planmarks`（plan・plan-review・fix・eyes・line）・`recount`・`querytest`（diagnose・fix・delta-review・plan-review・line）
- `handoff`（plan・report）・`outpurpose`（diagnose・line・report）・`policy`（fix・tdd・delta-review・plan・structure・r1・r3・r4・line。文は md へ）
- `lens`（lens・delta-review）・`libdocs`・`libdocs_local`・`libdocs_web`（plan・plan-review・fix）・`webget`（world・libdocs の使い手）
- `rolekit`（役を持つ block の全部。loop の数え・諦め・却下の控え。言語の文と出し直しの文は md へ）・`rulebook`・`seat`（fix・tdd・delta-review）・`spseam`・`borrow/`（`bin/`・fix・tdd・delta-review）
- `reads`（fix・plan・plan-review・parallel-pr・`bin/`）・`writelog`（`bin/`・fix・tdd・delta-review）・`writes`（fix・tdd・delta-review）
- `report`・`runreport`（report・line・chain。block の中身を import しない形に軽くする）・`stopby`（line・report・chain）
- `tree_run`（test-gate・fix・tdd・merge・line・`bin/`）・`userenv`（`bin/`・report・`tree_run`）
- `worldmark`（world・diagnose・plan・plan-review・line。行の欄と語・読み・答えの照らし。`judgebeside` への import は外し、文は md へ。報告の行の組み立て `report_lines` は world の `src/` へ）
- `jsonfile`・`oneline`（ほぼ全部）
- 素材の 11 本の共通の部品（新しい 1 モジュール。`judge_accept` の `material_*` から作る）
- `graphloops/engine/util.py`・`schema.py`・`declared.py`（`accept`・test-gate・`tree_run`）
- `next-request.schema.json`・`prior-failures.schema.json`（`carry` と同じ使い手）
- 指示の断片へ移す物（md なので lib から出す）: `agents/*.md`（役の定義 5 本）・`REVIEW.md` は `blocks/.shared/prompts/` へ。

### 9.4 試験の DELETE

- `tests/layers/`: `test_layer_map.py`（既知の漏れの表と数の歯止め）・`test_block_paths.py`（名の字の柵と `NAME_HOMES`）・`test_concept_fences.py`（自分の許す表）・`test_scan_rules.py`・`scan.py` の大半（残る検査が使う小さな助けは、その試験へ移す）・`test_node_table.py`（`docs/nodes.json`）・`test_capability_pointers.py`・`test_restored_not_gaps.py`・`test_works_parity.py`・`test_design_roles.py`。これらが読む表（`docs/layers.json`・`docs/concepts.json`・`docs/nodes.json`・`docs/works-parity.md` の照らしの表）と `tests/layers/seeds/` の見本も一緒に消す。
- `tests/workflows/`: `test_prompt_contracts.py`・`prompt_contracts.json`（古い指示書の約束の表。組み立ての口の落ち方と指示の比べで替える）・`copied.py`・`copied_rewrites.json`（元の works の指示書の写しの台帳。指示は英語で書き直すので台帳を閉じる）。
- `lib/tests/`: `test_constants.py`（ファイル名の字の柵）・`test_cross_block_keys.py`（block をまたぐファイルの鍵。port で替える）・`test_promptsection.py`・`test_marks.py`・`test_concept_fences.py` の works-factory 自身の表の部分（道具の部分は `test_concept_change.py` に寄せる）。
- `tests/shared/test_boundary.py`（`boundary.py` が消えるので、`ports.py` の試験に替える）。
- 古いサブグラフの試験（下の 9.5 の MOVE の元）は、組み込みで消す。

### 9.5 試験の MOVE（新しい block の試験の元にする）

古いファイルは組み込みで消す。振る舞いを見る試験を `tests/blocks/<block>/` に作り直す時の元にする。

- `lib/tests/`: world へ `test_blk_world.py`・`test_world_check.py`／fix へ `test_blk_fix.py`・`test_blk_fix_conflict.py`・`test_clash.py`・`test_consult.py`・`test_fix_duty.py`・`test_fix_gates.py`・`test_fix_rules.py`・`test_fix_units.py`・`test_duty_sets.py`・`test_lanekit.py`・`test_plan_scope.py`・`test_unittrees.py`／tdd へ `test_blk_fix_tdd.py`・`test_tdd_frozen.py`・`test_tdd_frozen_function_span.py`・`test_tdd_outside.py`／lens へ `test_blk_lens.py`／delta-review へ `test_blk_refix.py`・`test_blk_tests_delta.py`・`test_delta_marks.py`／plan へ `test_blk_plan.py`・`test_planfile.py`・`test_ripple.py`／plan-review へ `test_boardview.py`・`test_gate_axes.py`・`test_plan_gate.py`／structure へ `test_blk_structure.py`・`test_structfile.py`・`test_structure_eye.py`／判定の各 block へ `test_blk_judge.py`・`test_judge_accept.py`／local-review へ `test_diverted.py`／eyes と r1〜r4 へ `test_blk_eyes.py`・`test_eyeverdict.py`・`test_stage_b.py`／report へ `test_outcome.py`・`test_report_roles.py`／line へ `test_fixture.py`・`test_startrec.py`・`test_testcmd_check.py`・`test_versions.py`。
- `tests/workflows/`: `test_judge.py`・`test_fix.py`・`test_eyes.py`・`test_plan.py`・`test_plan_review.py`・`test_report.py`・`test_structure.py`・`test_test_gate.py`・`test_merge.py` を各 block へ。`test_line.py`・`test_chain.py`・`test_gate_head.py`・`test_testcmd_head.py` を新しい line・chain へ。

### 9.6 試験の KEEP

- `lib/tests/` の残り全部（KEEP の lib のモジュールの試験。例 `test_accept.py`・`test_rolekit.py`・`test_worldmark.py`・`test_impact.py`・`test_baseline_red.py`・`test_writes.py`・`test_imports.py`〔lib の import の循環が解けたら yes/no の「循環が無い」に替える〕）。文を md へ出したモジュールの試験は、文の字への assert を符号と欄への assert に替える。
- `tests/layers/` の yes/no の検査: `test_archon_validate.py`・`test_readonly_nodes.py`・`test_no_timeouts.py`・`test_outward_write.py`・`test_gates.py`・`test_role_retry.py`・`test_depth_skip.py`・`test_names.py`・`test_no_asf.py`・`test_no_conversion.py`・`test_no_owner_env.py`・`test_hermetic_env.py`・`test_required_checks.py`・`test_test_commands.py`・`test_rule_index.py`・`test_polyfills_listed.py`・`test_polyfill_evidence.py`・`test_lib_blind.py`・`test_words.py`・`test_layout.py`（新しい木に書き直す）・`test_block_returns.py`（`returns:` と `outcome_field:` の有無の部分だけ。`ALLOWED` の表は外す）・`test_lang_neutral.py`（言語の表を 1 つのモジュールに寄せ、許すファイルの表をやめる）・`trees.py`。どれも `blocks/` にも当てる。7.1 の 9 つは新しい `tests/layers/test_block_shape.py` に置く。
- `tests/workflows/` の形の検査: `test_uv_scripts.py`・`test_nodeflags.py`・`test_loop_sessions.py`・`test_returns_never_fail.py`・`test_role_texts.py`・`test_reply_fields.py`・`test_reply_patterns.py`・`test_fixture_claims.py`・`test_script_imports.py`・`test_count_how_copies.py`・`test_input_reads.py`（`ports` の口に向け直す）・`test_unread_named.py`（同じ）。
- `tests/shared/`: `test_archon_contract.py`・`test_child_pointer.py`・`test_childsweep.py`・`test_fence.py`（埋めは残る）。
- `tests/e2e/` の全部（`test_line_scenarios.py` と line の筋書きは新しい line に書き直す）・`tests/bin/` の全部（`linescripts.py` は書き直す）・`tests/calibration/` の全部（`nodes.py` の node の id を新しい名に合わせる）・`tests/archon.py`（使い捨ての木に `blocks/` を置けるようにする）・`tests/changed.py`・`tests/shard.py`。

## 10 keep-essence の 12 の仕組みと、守る block と試験

元の works の `works/docs/keep-essence.md` の 12 の仕組み。block の試験の欄の「（作る）」は、今の守りが lib の中の関数を直に呼ぶ試験で、その中身を割ると試験ごと消えるので、block の振る舞いの試験として作り直す物。今の守りの名は、作り直しの元として書く。

1. 赤緑の機械の判定 → 持ち主 tdd（loop の中）と fix（受け付けの後の確かめ直し）。読み手 report。今の守り `lib/tests/test_blk_fix_tdd.py::TestRedCheck`・`lib/tests/test_fix_gates.py::TestRedGreen`・`tests/workflows/test_test_gate.py::SuiteLoopCase.test_written_runner_feeds_the_red_green_check`。新しい守り `tests/blocks/tdd/` の standalone の赤緑の試験（作る）。
2. 元から赤のテストの区別 → 持ち主 test-gate。読み手 tdd・fix。今の守り `lib/tests/test_baseline_red.py`・`tests/workflows/test_test_gate.py::ResultScriptCase`。新しい守り `tests/blocks/test-gate/`（作る）と `lib/tests/test_baseline_red.py`（KEEP）。
3. テストの凍結と、許す道は 1 本 → 持ち主 tdd（hash を取る）と fix（受け付けで確かめる）。許しを出すのは fix の裁定・plan・案の直し・範囲の相談。今は `lib/conflict.py::test_permits` の 1 つの関数が「1 本」を担う。block に割ると崩れる余地があるので、許しを 1 つの port（fix と tdd の入力 `permits`）にまとめ、許しの出どころを数える試験を作る（作る）。今の守り `lib/tests/test_tdd_frozen.py::FrozenRuledScopeCase`・`lib/tests/test_conflict_kinds.py::TestReplanState.test_permit_sources_are_read_in_one_place`。
4. 3 回拒まれたら諦める → 持ち主 tdd と fix（loop の数え `lib/rolekit.py` は KEEP）。今の守り `tests/workflows/test_fix.py::FixLoopScriptsCase.test_third_reject_gives_up_only_the_named_unit` ほか。新しい守り `tests/blocks/fix/`・`tests/blocks/tdd/`（作る）。
5. 書き込みの出どころの突き合わせ → 持ち主 fix・tdd・delta-review（`lib/writes.py` は KEEP）。フックを置くのは `bin/`。今の守り `lib/tests/test_writes.py::TestProvenance`・`tests/bin/test_record_write.py`（どちらも KEEP）。
6. 当たる試験を選んで回し、回さなかった試験を名で残す → 持ち主 fix。読み手 test-gate・line の最後の承認ノード・report。今の守り `lib/tests/test_impact.py`（KEEP）・`lib/tests/test_tdd_outside.py`（MOVE tdd）・`tests/workflows/test_line.py::AskFinalReadsCase.test_final_text_lists_suites_baseline_and_left_tests`（新しい line へ）。
7. class_query の数え直し → 探し方を作るのは diagnose、数え直すのは fix。今の守り `lib/tests/test_judge_accept.py::JudgeTakeCase`（MOVE diagnose）・`lib/tests/test_fix_units.py`（MOVE fix）・`lib/tests/test_fix_seams.py::RecountSeamCase`（KEEP。中の継ぎ目の試験なので、fix の振る舞いの試験に作り直す）。e2e の `tests/e2e/evidence.json` の J70・J71・F122・F123 は本物の run で見えている。
8. 食い違いの申し出と、読むだけの裁定役 → 持ち主 fix（tdd も申し出を出す）。読み手 line の最後の承認ノード・plan-review・report。今の守り `lib/tests/test_conflict_kinds.py`・`lib/tests/test_fix_seams.py` の 3 本・`tests/layers/test_readonly_nodes.py`（裁定役が読むだけ）・筋書き `workflows/line/fixtures/conflict-ask.stubs.yaml`。fix の振る舞いの試験（作る）。
9. 独立設計と R1〜R4 → 持ち主 independent-design（目的だけを受ける port の形そのものが独立の守りになる）。読み手 plan-review・r2。R1〜R4 は r1〜r4。今の守り `tests/workflows/test_plan_review.py::IsolationCase.test_r2_prep_reads_only_the_allowed_names`・`tests/workflows/test_eyes.py::ShapeCase`。新しい守りは `tests/blocks/independent-design/` の「入力は `purpose` だけ」の yes/no（作る）。
10. 守りのファイルに触れたら最後の承認ノードを開く → 当たりを見るのは merge（今は eyes の中。13 節）。読み手 line の最後の承認ノードと `bin/apply`。今の守り `tests/workflows/test_merge.py::ApplyTest.test_no_answer_and_protected_hit_refuses`・`lib/tests/test_protect.py`（KEEP）・筋書き `workflows/line/fixtures/eyes-failed-protected.stubs.yaml`。e2e の種は守りのパスに当たらないので、本物の run では通っていない。
11. 直す単位ごとの記録が報告と最後の承認ノードに届く → 書くのは tdd と fix、読むのは report と line。block をまたぐので、tdd の出力 `units` の形を試す試験と、report が `sections` で受ける試験を作る（作る）。今の守り `lib/tests/test_runreport.py::TddCase`・`tests/workflows/test_line.py::AskFinalReadsCase.test_fix_beside_files_reach_the_final_gate`。
12. 世界の解に照らす → 持ち主 world。読み手 diagnose・plan（行ごとに答えさせる）・plan-review（依頼を出どころにした外れを人に回す）・line の修正前の承認ノード。今の守り `lib/tests/test_world_check.py::Verify`・`lib/tests/test_blk_world.py::Classes`（MOVE world）・`tests/workflows/test_plan.py::AcceptCase.test_world_row_needs_answer`・`tests/workflows/test_plan_review.py::WorldGateCase.test_deviation_cited_to_request_goes_to_human`・筋書き `workflows/judge/fixtures/world-offline.stubs.yaml`。詳しくは [world.md](world.md) の 8 節。

## 11 作る順・並べ方・組み込み・確かめ

### 11.1 作る順

0. 土台と手本（1 本の PR。並べない）: guidance-path の目の block（8.6）・`blocks/` の pack の骨組み・`blocks/.shared/ports.py`・`prompt.py`・共通の指示の断片（外への検索の決まり・却下の段落・役の定義 5 本）・`blocks/AGENTS.md`・7.1 の形の検査・`tests/archon.py` と起動の殻で `blocks/` を pack として回す口・world の block・policy-check の入口（この時は world だけをつなぐ）。#765 の進め方 2 に当たる。土台の後、新しい形で guidance-path の目を 1 回回し、1 節の「変更が閉じる 1 か所」へ辿れない頼みがあれば、案内か手本を直してから次へ進む。
1. 1 波目（互いに独立。同時に作る）: purpose・premises・head-depth・parallel-pr・spec・structure・independent-design・cold-read・test-gate・merge・report（`sections` の形は土台で決めるので、ほかの block を待たない）。素材の観点は、共通の部品と 1 本目（prior-decisions）を 1 本の PR にし、残りの 10 本を同時に作る。
2. 2 波目（1 波目の出力の形を使う）: diagnose（再審を含む）・verify・plan・plan-review（text の形を足し、policy-check に include を足す）・r1〜r4・lens。
3. 3 波目（修正の族）: tdd・delta-review・fix。どれも `lib/fixboard.py` と `lib/tddloop.py` の中身を自分の `src/` へ写すので、lib は触らず、写す範囲が重ならないように各設計書で割り当てる。
4. graph: judge と eyes のまとめ。
5. 組み込み（1 本の PR。並べない。11.3）。
6. 組み込みの後: drift-eye を足す。

並べ方の決まり:

- 各 PR が触るのは、`blocks/<block>/`・`tests/blocks/<block>/`・`docs/design/<block>.md` だけ。`lib/` は読むだけで変えない（MOVE は写して置き、元は残す）。だから PR どうしは衝突しない。
- 共通の指示の断片は土台が先に置く。足りない断片は、最初に要った PR が足す。同じ断片を 2 本の PR が同時に足さないよう、設計書の段で名を決める。
- 1 本の PR は block 1 つ（素材の 10 本だけは束ねてよい）。持ち主の決め `overnight-speed` は、この作り直しの間だけ効かせる（大きい PR・聞かずに merge）。

### 11.2 block ごとの確かめ（PR ごと）

- standalone の fixture（`archon workflow test`）が、port の値だけで最後まで届く。
- `tests/blocks/<block>/` の、script を子のプロセスで回す試験。始めの記録の無い使い捨ての run directory と git のリポジトリで、port の値だけを渡して prep・accept・出口を回す。
- 指示の比べ（10.3）。
- 設計書の keep-essence の番号の試験。
- 本物の単独の run を 1 回（費用のかかる試しは聞かずに回してよい。リポジトリの決まり）。

### 11.3 組み込み

1. `blocks/line/` と `blocks/chain/` に新しい line と chain を書く。始めの記録を書き、block に port の値を配り、block の `report` の欄を集めて report に渡す。
2. line の筋書き（今の `workflows/line/fixtures/` の 36 本）を、新しい node の id に書き直す。
3. `workflows/` の古いサブグラフと `workflows/.shared/boundary.py` を消し、埋め（`fence.py`・`childsweep.py`・`child_pointer.py`・`skip_value.py`）を `blocks/.shared/` へ移す。
4. `blocks/` を `workflows/` に入れ替える（`git mv`）。`pack.json` の `ours.folder` はそのまま。
5. 9 節の DELETE と MOVE の元を lib と試験から消し、KEEP の物から文を md へ出す。
6. 根の `AGENTS.md` と `workflows/AGENTS.md` を、憲法 6 行と、決まりとパスだけの短い形に書き直す。決まりの中の試験の仕様は試験の docstring へ、設計の細目は `docs/design/` へ移す。`docs/design.md` は `docs/design/` に置き換える。

### 11.4 確かめ（組み込みの後）

- 指示の比べ: #764 の 2 つの commit の形を block ごとに使う。1 つ目の commit は、md を日本語のまま作り、同じ値で組んだ新しい指示が古い指示と同じ字になること（空白と改行の違いは除く）を試験で確かめる。この試験は 2 つ目の commit（英語にする）で消す。2 つ目の commit では、古い指示と新しい指示を同じ値で組んで並べた物を PR に載せ、設計書の「今の指示との差」の一覧どおりかを審査が見る。
- e2e の筋書き: `tests/e2e/test_line_scenarios.py`（AI の返答を台本で差し替えて line 全体を回す）が緑。
- 本物の run を 1 回: 小さな依頼を新しい line で回し、`tests/e2e/evidence.py check` で keep-essence の印を照らし、報告と承認ノードの文が日本語で出ることを確かめる。

## 12 持ち主の決めの変更

`docs/owner-decisions.md` の「2026-10-19 の決め」に、次の 5 件を書いた。

- `block-local-code`: 1 つの block だけが使うコードは block のフォルダに置き、`lib/` は 2 つ以上が使う物だけ。今の E4 の「script は lib と境の口を呼ぶだけ」を置き換える。
- `lib-port-ended`: `lib-port-as-is`（元の名と元の中身のまま持ってくる。要らない物は最後の掃除の段で消す）を終える。最後の掃除はこの作り直しの組み込みが担う。
- `rules-tests-design-apart`: 決まり・試験の仕様・設計を分けて書く。憲法は AGENTS.md の頭に数行。
- `shape-checks-only`: 数の歯止め・閾値・許す物の表を検査に使わない。機械の検査は yes/no の形の決まりだけ。
- `rebuild-speed`: `overnight-speed` はこの作り直しの間だけ効かせ、組み込みの後に外す。`simple-software` に沿って、層の検査のコードを置き場の形に置き換えて小さくする。

## 13 根拠を書いて自分で決めた事（持ち主に聞かない物）

- 作り直しの間の置き場を、2 つ目の pack `blocks/` として今の `workflows/` と別に読ませる。根拠: Archon は pack をまたいで workflow のファイルの名が重なると誤りにする（3 節）。別に読ませれば最後の名（`works-factory-plan` など）を初めから使え、組み込みは `git mv` で済む。仮の名で `workflows/` に並べると、組み込みで全部の名を付け替える手間が増える。払う物は、起動の殻の引数 1 つ。
- 再審は diagnose の block に同居させる。根拠: 持ち主の決め `rejudge-cohabit`。
- 守りのファイルに触れたかを見る所（keep-essence の 10）を、今の eyes から merge に移す。根拠: 守りの当たりは差分を確定する所の事実で、独立の目の観点ではない。最後の承認ノードと `bin/apply` の拒みが読む事実は変わらない。
- 報告の文は事実を持つ block が組んで出力の `report` の欄で返す。根拠: 持ち主の決め（block はほかの block を名指さない・1 つの block だけのコードは block に置く）の下では、report が各 block の中身を import する今の形を続けられない。drift-audit の 3 節の直し方 1 と同じ。

## 未確認の一覧

- `prompt:` に大きい指示（数十 KB）を `$<id>.output.prompt` で入れた時に、Archon の出力の大きさの上限に当たらないか。
- `graphloops/engine/validator.py` を消せるか（判定の受け付けが頼る所）。
- `lib/downgrades.json` と `lib/design-row.schema.json` の使い手。
- 1 節の変更の種類の数と、1.1 の変更の歩かせ（別の作業が書く）。
