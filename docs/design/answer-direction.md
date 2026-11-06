# block の設計書: answer-direction（修正前の承認の一言の向きの判定）

- 何の話か: 人が修正前の承認ノードを `continue`（か `approve`）で通す時に添えた一言が、承認に掛けた計画と違う向きを選んでいても、前は誰も照らさず、計画のまま修正が走って誤った修正ができた。その一言の向きを計画と見せた項目に照らし、同じ向きか・違う向きか・向きが読めないかを返す葉の block `workflows/answer-direction/` の設計。型は [README.md](README.md)、書き方は [cold-read.md](cold-read.md) に従う（用意の script → 道具の無い AI の node → 返答の受け皿 → 返す node）。
- 決めたこと: 判断（一言の向き）は AI の役 1 回で block に置き、止めるかの決めは line の `gates.direction_stop` に置き、配線は line の YAML が include でつなぐ。block は向きの語（`aligned`・`redirected`・`unclear`）と真偽 `aligned` の決めを持ち、line は真偽 `aligned` だけを読む。照らすのは仕様駆動の道と写しの道だけで、通常の run（依頼の文・差分で入る本線）は変えない。
- 読む人: この block を作る・直す役。

この文書の語は README の頭の物を使う。ほかに:

- 承認の一言: 修正前の承認ノード `gate-before-fix`（仕様駆動の道は `spec-gate-before-fix`、写しの道は `fixture-gate-before-fix`）の答え `{decision, text}` の `text`。
- 計画: 承認に掛けた修正案（`plan` の出力 `fix_plan`。`{plan: [項目の行]}`）。見せた項目: 承認ノードで人に見せた項目の文（`ask-before-fix` の返り `asked`）。
- 向き: 一言が計画の向きを足すだけなら `aligned`、計画や見せた項目と違う振る舞い・やり方・範囲を選んでいれば `redirected`、どちらの向きか読めなければ `unclear`。

## 1 block の全体

### 1.1 役

承認の一言を、計画の各項目の approach と files の path・op の要約（`plan_lines`）と見せた項目に照らして、向きを 1 回だけ判じる。止めるかは決めない（呼んだ側が出力の欄 `aligned` で決める）。

### 1.2 port

入力（YAML の `inputs:`）:

- `answer`（必須）: `text: 承認ノードの答え {decision, text} の JSON の字`。決めの語が通す語（`lib/answer.py` の `GO_WORDS`）で一言が空でない時だけ役を起こす。読めない・`null` は判定が落ちた扱い。
- `asked`: `json(shown.schema.json): 承認ノードで見せた項目の文の配列`（形は block の `schemas/shown.schema.json`）。既定 `[]`。`null` は項目なし。
- `plan`: `json(shared:fix-plan.schema.json)`: 承認に掛けた計画の修正案の pointer（か値を読めるパス）。既定 `""`。一言があるのに空・読めない時は判定が落ちた扱い。
- `lang`: `text`: `why` の字の言語。空は一言の言語。

出力（`returns: finish`、`outcome_field: ok`）:

- `ok`: boolean。`status` が `failed` でないか。
- `status`: `ok`（役が読める返答を返した）・`skipped`（役を起こさなかった。一言が空か止める語の答え）・`failed`（支度が落ちた・答えか計画か見せた項目が読めない・返答が無いか読めない）。
- `reason`: `failed` の訳（日本語の 1 行）。ほかは空。
- `direction`: `aligned`・`redirected`・`unclear` か `""`（`skipped`・`failed`）。`why`: 役の返答の 1 文（`direction` が `""` なら空）。
- `aligned`: boolean。**真になるのは `direction` が `aligned` の時と `status` が `skipped` の時だけ。** `failed` は偽（判定が落ちたのを通さない）。
- `report`: 報告の行の配列。`redirected`・`unclear`・`failed` の時だけ 1 行（`aligned`・`skipped` は空）。

### 1.3 node の並び（`workflows/answer-direction/works-factory-answer-direction.yaml`）

1. `direction-prep`（script `direction_prep.py`）: port を読み、place の中のこの block のファイル（`direction-prompt-1.md`・`reply.json`）を名で引いて消し、`src/direction.py` の `due` で役を起こすかを決める。返り `{due, prompt, reason}`。`due` が偽で `reason` が空なら役が要らない（`skipped`）、`reason` が空でなければ読めなかった入力の名指し（`failed`）。起こす時は指示を `prompts/direction.md` に一言・見せた項目・`plan_lines` を入れて組む。
2. `direction`（AI。`depends_on: [direction-prep]`・`when: "$direction-prep.output.due == true"`・`context: fresh`・`model: '@wf-judge-materials'`・`allowed_tools: []`・`settingSources: [user]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`mutates_checkout: false`・`idle_timeout: 1728000000`・`retry: {max_attempts: 2, on_error: all}`）: `output_format {direction: aligned|redirected|unclear, why}`。道具を持たない。指示は英語の md 1 本（`prompts/direction.md`）。
3. `direction-save`（script `direction_save.py`。`depends_on: [direction]`・`with: {reply: $direction.output}`）: 役の返答の受け皿。返答を place の `reply.json` に写す。判定の向きと `why` の run の記録はこのファイル。役が落ちた・飛ばされた時はこの node も飛ぶ。
4. `finish`（script `finish.py`。`depends_on: [direction-prep, direction-save]`・`trigger_rule: all_done`）: `reply.json` を読んで `src/direction.py` の `outcome` で出力を返す。役の node は結ばない（落ちた node の出力を受けた node は `all_done` でも落ちるため、役が落ちた時に返す node が落ちず、`failed` の印が返りに出る）。

### 1.4 コードの置き場

- `src/direction.py`: `due`（起こすかと入力の読み）・`plan_lines`・`read_reply`・`outcome`・`failed`・place のファイルの名 `REPLY`・向きの語 `VERDICTS`（YAML の enum と同じ。試験が突き合わせる）。向きの語と `aligned` の真偽の決めはここ 1 か所。line に写さない。
- `scripts/`: `direction_prep.py`・`direction_save.py`・`finish.py`。`prompts/direction.md`。`schemas/shown.schema.json`（入力 `asked` の形）。`fixtures/`: `standalone.stubs.yaml`・`failed.stubs.yaml`・`plan.json`（単独の筋書きの計画）。

## 2 呼ぶ形

line が include する（[line.md](line.md) の 1.3 の 9・2 節の 2。仕様駆動の道は [spec-driven.md](spec-driven.md) の 6.2 の 12・13）:

- `spec-direction`・`fixture-direction`: `with: {answer: <同じ道の gate の出力>, asked: <同じ道の ask の asked>, plan: {from: <同じ道の ask の plan>, if_skipped: null}, lang}`。`when:` は仕様駆動の道が `from_spec == true` と `spec-ask-before-fix` の `open`、写しの道が `fixture_gate == true` と `fixture-ask-before-fix` の `open`。
- 受け皿 `spec-direction-out`・`fixture-direction-out`。答えの node `spec-answer-before-fix`・`fixture-answer-before-fix` が `direction`（受け皿の `got`）と `direction_due`（`true`）で返りを受け、`gates.direction_stop` に渡して止めるかを決める。本線の `answer-before-fix` は入力を足さない。
- 単独でも回る: `answer`・`asked`・`plan`（`fixtures/plan.json` のパス）を渡せば最後まで届く。

## 3 判定が落ちた時の止め（fail-closed）

次はどれも `status: failed`・`aligned` 偽で、line は修正の前に止める（止めの語 `works:answer-redirected`）:

- 答え `answer` が JSON でない・`null`・`decision` が字でない。見せた項目 `asked` が字の配列でない。計画 `plan` が `null`・空・読めない・形に合わない（一言が空か止める語の答えは、計画を読む前に `skipped` で返るので、計画が読めなくても止まらない）。
- 役が返答を返さなかった（落ちた・飛ばされた）。返答が JSON でない・向きの語の外・`why` が字でない。
- 支度の node が落ちた。

止めた時に人が下書きを見て答え直せば済む。確かめる処理が落ちた時に通すと、計画と逆の一言でも確かめないまま誤った修正へ進む穴になる。

## 4 照らさない入口

block は呼ばれた答えを照らすだけで、どの答えを照らすかは line が決める（[line.md](line.md) の 2 節の 2）。照らさない入口:

- 対話モードの合意だけで入る道（承認ノードが開かない）。合意の後に新しい行で開いた承認ノードで足される合意の一言（判定に掛かるのは承認ノードの出力そのもの）。合意への向きの変更は、設計の相談の承認ノード `gate-design` の `revise`・`redesign` が受ける。
- 無人の run の推しで進んだ答え。止める語の答え。
- 通常の run（本線）。

## 5 E11（仕組みを足す前の 3 つの問い）

1. Archon が持っているか: 持たない。承認ノード `wait:` は選び肢の語を返すだけで、添えた一言を計画と照らす仕組みは無い（[archon.md](archon.md)）。
2. ASF が持っているか: 持たない。世界の解（GitHub の Request changes や Terraform の saved plan）は承認を構造化した状態や承認された計画そのものに縛り、自由な付言は読まない。一言そのものを見て止めると決めているので、構造化した語を足すだけでは `continue` と書いて向きを変えた一言を拾えない。
3. 本当に要るか: 要る。`answer.taken` は決めの語しか読まず、一言は修正役へ条件として運ぶだけで、計画の向きとは照らさない。依頼の答えが、その時は修正の前に止めて聞き直すと決めている。AI の判断は line に置けない（[line.md](line.md) の冒頭）ので、葉の block にした。退けた形: 空でない一言を必ず止める（計画に沿う条件の一言まで止める）、修正の段の相談 `consult` に足す（通常の run も使う共有の block で、止まる所が修正の中になる）、`cold-read` に問いを足す（本文の読めなさを見る役で、問いが違う）。

## 6 試験

`tests/blocks/answer_direction/test_answer_direction.py`: `redirected`・`unclear`・同じ向き・空の一言・返答の欠け・読めない答え・読めない計画・指示の文に計画と一言と見せた項目が載ること。筋書きは `fixtures/`（`standalone`: 逆向きの一言で `aligned` が偽。`failed`: 役が落ちて `aligned` が偽）。line 側の縛りは `tests/blocks/line/test_gates.py`（`DirectionStopCase`・`ScriptCase`）・`test_scenarios.py`（`DirectionStopTest`）・`test_wiring.py`。
