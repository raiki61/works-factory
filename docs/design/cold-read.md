# block の設計書: cold-read（初見の読み手）

- 何の話か: 文脈を持たない読み手が本文を 1 回読み、どこで止まったか・何を推測で埋めたか・本文だけで決められるかを返す観点「初見の読み手」を、単独で呼べる汎用の block `blocks/cold-read/` にする設計。型は [README.md](README.md)、書き方は [world.md](world.md) に従う。
- 決めたこと: 今の報告（report）の中の初見の読み手（cold-prep・cold）の、報告に依らない芯を、3 つの node の block にする。入力は読ませる本文のファイルと言語の 2 つの port だけで、報告の中身も報告の頭の決まりも知らない。指示は英語の md 1 本（`prompts/cold.md`）。役の定義は共通の断片 `role-cold-reader` で、report の block が自分の中に持つ初見の読み手の node と同じ断片を使う。
- 読む人: この block を作る実装の役（この設計書だけで作れるように書いた）。急ぎではない（README 11.1 の 1 波目。ほかの block と並べて作る）。
- 持ち主に求めること: なし。自分で決めた事は 10 節に集めた。

この文書の語は README の頭の物を使う。ほかに:

- 初見の読み手の役（cold）: 道具を持たず、貼られた本文だけを読む AI の役。英語の名は "the cold reader"（土台の役の定義の断片 `role-cold-reader` の役）。
- 止まった所（stops）・推測で埋めた所（guessed）: 役の返答の欄。1 つでもあれば判定の語は `redesign-needed`、無ければ `pass`。
- 始めの記録: line（メイングラフ）が run の頭に書く記録（言語・試験のコマンド・入口の差分など）。block は読まず、要る値は line が port で渡す（README 4.2）。
- 例の run: 本物の run `df5e111f-ea97-409b-8066-2245d32746ab`（対象 raiki61/works-factory）。今の報告の初見の読み手は 3 回とも `redesign-needed` を返した（置き場の `report/rejects-report.md`）。読ませた本文は Archon の記録（`archon-home/archon.db` の `remote_agent_workflow_events` の `report__write-loop.cold-prep` の `node_output`）に在る。骨組みの値は 1 回目（約 11 KB）から取った。この block は報告の頭の決まりを持たないので、骨組みは同じ本文をただの本文として読ませた形で描く。

## 1 block の全体

### 1.1 役

渡された本文を、文脈を持たない初見の読み手に 1 回だけ読ませ、意味が取れずに止まった所・推測で埋めた所・本文だけで決められるかを返す。読み手は複数の作業を切り替えながら読む人として、冒頭の 3 行だけで「何の話か・自分に関係あるか・急ぐか」が言えるかも確かめる。書き直させるかは決めない（呼んだ側が返りの欄で決める）。

### 1.2 port

入力（YAML の `inputs:`）:

- `text`（必須）: `file: 読ませる本文のファイル（字のまま読み手に貼る）`
- `lang`: `text: 人に見せる欄（stops・guessed の字）の言語。空は本文の言語`。既定 `""`。

出力（`returns: finish`、`outcome_field: ok`）:

- `ok`: boolean。`status` が `ok` か（読み手の返答を読めたか）。
- `status`: `ok`（返答を読めた）か `failed`（本文が読めない・役が落ちた・返答を読めない）。
- `verdict`: `pass`・`redesign-needed` か `""`（返答を読めない時）。
- `pass`: boolean。`verdict` が `pass` か。
- `stops`・`guessed`: 字の配列（役の返答のまま）。`decidable`: boolean（役の返答のまま。読めなければ false）。
- `stuck`: 書き直す側へ渡す 1 件ずつの行の配列。`止まった所: <stop>` と `推測で埋めた所: <guess>` を並べた物。返答を読めなければ `初見の読み手の返答を読めない（判定の語が無い）` の 1 行。`redesign-needed` なのに 2 つの欄が空なら `（止まった所・推測の欄が空）` の 1 行。`pass` で欄が空なら空の配列。今の `runreport._cold_lines` と `_cold_reason` の中身と同じ字。
- `reason`: 日本語の 1 行。`failed` の訳。`ok` なら空。
- `report`: 報告の行の配列（9 節）。

今との違い: 今の初見の読み手は報告の中にしか無く、読ませる本文を cold-prep が報告の置き場と書き手の返答から組み、返答を書き手の受け付けが読んでいた。この block は本文のファイルを受けて読ませるだけで、報告の頭の決まり（頭の後ろに付く物・機械が組む行）を言わない。報告の中の読み手は report の block が持ち続ける（1.6）。

### 1.3 node の並び（`blocks/cold-read/works-factory-cold-read.yaml`）

1. `cold-prep`（script `cold_prep.py`）: port を読み、place を作り直し、指示を組む。返り `{due, prompt, reason}`。本文が読めない時は `due: false` と訳（指示は空の字）。
2. `cold`（AI。`depends_on: [cold-prep]`・`when: "$cold-prep.output.due == true"`・`prompt: "$cold-prep.output.prompt"`・`context: fresh`・`allowed_tools: []`・`settingSources: [user]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`mutates_checkout: false`・`model: '@wf-report'`・`idle_timeout: 1728000000`・`retry: {max_attempts: 2, on_error: all}`・`output_format` は今の `cold` の物を字のまま）
3. `finish`（script `finish.py`。`depends_on: [cold-prep, cold]`・`trigger_rule: all_done`・`with: {prep: {from: "$cold-prep.output", if_skipped: null}, reply: {from: "$cold.output", if_skipped: null}}`）: 返答を読んで出力を返す。どの段が落ちても落ちない。

script の node はどれも `runtime: uv`・`mutates_checkout: false`。受け付けの loop は置かない（4 節）。`context: fresh` は今の読み手と同じ（新しい会話で起きる）。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、include された時は `$ARTIFACTS_DIR/<include の道>/`）の下に書く。名は `src/files.py` だけが持つ:

- `cold-prompt-1.md`: 組んだ指示。
- `reply.json`: 役の返答（`finish` が写す。役が飛ばされた・落ちた回は書かない）。
- `read.json`: 出口の返りの写し。

`cold-prep` が place の中を全部消してから書く（world の intake と同じ）。block は 1 回の include で 1 回だけ読むので、回の番号は要らない。

### 1.5 コードの置き場と、作る・触るファイル

作るファイル（この block の PR が触るのはこれと `tests/blocks/cold_read/` と、この設計書だけ）:

- `blocks/cold-read/works-factory-cold-read.yaml`
- `blocks/cold-read/prompts/cold.md`（2 節）
- `blocks/cold-read/scripts/cold_prep.py`・`finish.py`
- `blocks/cold-read/src/__init__.py`（空）
- `blocks/cold-read/src/files.py`: place のファイルの名（1.4）。
- `blocks/cold-read/src/reply.py`: 返答の読み。今の `lib/runreport.py` の `_cold_of`（:1912-1917）・`COLD_UNREADABLE`・`COLD_EMPTY`（:1920-1921）・`_cold_lines`（:1924-1928）の写しと、`VERDICTS = ("pass", "redesign-needed")`（今の `runreport.COLD_SCHEMA` の `verdict` の enum。md の `{passed}`・`{redesign}` と `output_format` の enum が同じ字を持つ。試験が YAML の enum と突き合わせる）。`stuck(c)` は 1.2 の決まり。
- `blocks/cold-read/src/report.py`: 報告の行（9 節）。
- `blocks/cold-read/fixtures/standalone.stubs.yaml`・`redesign.stubs.yaml`・`unreadable.stubs.yaml`（11 節）。
- `tests/blocks/cold_read/__init__.py`・`test_cold_read.py`・`test_prompt_compare.py`（11 節。Python の package の名は `-` を持てないので `_`）。

使う `lib/`（KEEP）: `jsonfile`・`oneline` だけ。`lib/runreport.py`・`lib/report_roles.py` は import しない（どちらも report の物）。

共通の指示の断片: `role-cold-reader`（土台の役の定義の断片）だけ。報告の頭に特有の決まりは report の PR が足す断片 `report-head-check` に在り、この block は使わない。

作り直しの間は `lib/runreport.py` の `_cold_*` を消さない（今の report が使う）。どこへ移すかは report の設計書の決め。

### 1.6 つなぎ方（graph の側。block には書かない）

- report の書き手の往復（書く → 読む → 通らなければ書き直す、3 回まで）は、report の block が自分の中に持つ。report の中の初見の読み手の node は、この block を include せず（block は `include:` を持てない）、同じ断片 `{shared:role-cold-reader}` に report の断片 `{shared:report-head-check}` を足した自分の md で組む。訳（report の設計書の決め）: 書き手の回ごとの受け付けが同じ回の読み手の判定で決まる・読み手の後に受け付けの node を graph に置くと憲法の 3 に触れる・report を単独で回した時にも初見の確かめが要る。
- だから、初見の読み手の役の定義（道具なし・正当化しない・判断できる事とできない事を分ける・無言の省略を作らない）は断片 `role-cold-reader` の 1 か所に在り、この block と report の両方が差し込む。複数の作業を切り替える読み手の段落と返し方は、この block の md と report の md の両方に在る（2.6 の「写した」）。
- この block の使い道: 工場が人に見せる文（承認ノードの文・PR の本文・設計書の草稿など）を、どの graph からでも、または単独で初見の確かめに通す。今そういう配線は無い。`with:` は `text` ← 確かめる本文のファイル・`lang` ← 始めの記録の lang。
- 読み手: 呼んだ graph（`pass`・`stuck`・`stops`・`guessed`）と報告の事実の行（`report`）。

## 2 node の設計シート: cold（初見の読み手の役）

### 2.1 役

貼られた本文だけを読み、意味が取れずに止まった所・推測で埋めた所・本文だけで決められるかを返す。「この用途なら妥当」と正当化しない。

### 2.2 port

port `text` のファイルの本文・`lang`。ほかの block の出力も run の記録も読まない。

### 2.3 組み立ての順（`prompts/cold.md`）

1. `{shared:role-cold-reader}`（土台の役の定義の断片。道具を持たない・正当化しない・判断できる事とできない事を分ける・無言の省略を作らない・出力の形と語は呼んだ側の指示に従う）。
2. 複数の作業を切り替えながら読む読み手の段落（決まった文）: 冒頭の 3 行で何の話か・関係あるか・急ぐかが言えるか・本文の外に頼る参照・中身を言わない記号と略語とパス。
3. 文脈を持たない読み手として本文だけを読めという 1 文（決まった文）。
4. `## Text` と、区切りの 2 行で挟んだ `{text}` ← port `text` のファイルの本文（字のまま。末尾の改行だけを 1 つに揃える）。
5. `## How to answer`（決まった文）と差し込み口 `{passed}`・`{redesign}`（← `src/reply.py` の `VERDICTS`）・`{lang}`。
6. 結びの 1 文（決まった文）。

差し込み口の一覧（値の出どころ）: `{text}` ← port `text`・`{passed}`・`{redesign}` ← `src/reply.py` の `VERDICTS`・`{lang}` ← port `lang`（空なら `the language of the text`。`rolekit.LANG_DEFAULT` と同じ意味の英語の文。README 5.3）。差し込むかを選ぶ段落は無い。

md の本文（英語。この block の PR でこのまま置く）:

```markdown
{shared:role-cold-reader}

The person who reads this text reads it while switching between several tasks. Check also whether the first 3 lines alone let that reader say what this is about, whether it concerns them, and whether it is urgent. If they do not, write in `stops` where that became impossible. Also write in `stops`, as places you stopped, every reference that relies on something outside the text or on context before or after it (such as "the earlier one"), and every place that shows only a symbol, an abbreviation, or a path without saying what it is.

You are a first-time reader with no context. You have been given nothing about where this text came from or what it is for. Read only the text below.

## Text

==== from here ====
{text}
==== to here ====

## How to answer

Return (1) where you stopped because you could not take the meaning (`stops`), (2) what you filled in by guessing (`guessed`), and (3) whether a decision can be made from this text alone (`decidable`). If there is even one stop or one guess, `verdict` is `{redesign}`; if there is none, `{passed}`.

- Each entry in `stops` and `guessed` is one sentence that names the place in the text.
- Write `stops` and `guessed` in {lang}. Keep quoted words from the text, identifiers, and paths as they are.

Return only JSON that matches the output schema.
```

### 2.4 返す形

今の `cold` の `output_format` のまま（`works-factory-report.yaml:284-292`）: `verdict`（`pass`・`redesign-needed`）・`stops`（字の配列）・`guessed`（字の配列）・`decidable`（boolean）。全部必須。人に見せる欄は `stops`・`guessed` で、言語は `{lang}`。

### 2.5 描いた骨組み（例の run の値）

```markdown
This role is the cold reader …（{shared:role-cold-reader} の本文）

The person who reads this text reads it while switching between several tasks. …（決まった文）

You are a first-time reader with no context. … Read only the text below.

## Text

==== from here ====
# 報告（run df5e111f-ea97-409b-8066-2245d32746ab）

起きたこと: 決めた判定から確かめまでの一巡の数のうちに直しきれずに止まった（round_limit）。TDD の実行器を作れなかった（…）
差分を当ててよいか: PR を作った: https://github.com/raiki61/works-factory/pull/759（下書きの PR #759。…）
人が決めること: 15 件——許したテストの変更 13 件・直しきれずに残った物 2 件（…）
- 許したテストの変更: lib/tests/test_runreport.py
…（1 件 1 行の 15 行）

## 人が決めること
…（書き手の要約。A・B の 2 節）

## 語の定義（機械が付けた。本文の外）

- outside_env: lib/tree_run.py の関数。…
==== to here ====

## How to answer

Return (1) … If there is even one stop or one guess, `verdict` is `redesign-needed`; if there is none, `pass`.

- …
- Write `stops` and `guessed` in the language of the text. …

Return only JSON that matches the output schema.
```

例の run の今の読み手（報告の頭の決まりつき）の 1 回目の返答は `redesign-needed`・止まった所 10・推測で埋めた所 5。この block で同じ本文を読ませると、報告の頭の決まり（詳しい節に任せた所を止まりにしない）が無いので、止まった所は同じか多くなりうる。報告の初見の確かめは report の中の読み手が続けて持つ。

### 2.6 今の指示との差

今の指示は `workflows/report/commands/cold-check.md`（21 行）に在り、本文は `$cold-prep.output.body` で入る。

- 移した: 役の定義の 7 行（md:1-7）を、土台の役の定義の断片 `{shared:role-cold-reader}` に。字の違いは最後の箇条だけ（今「下の指示に従え」、断片「呼び出し側の指示に従え」。`lib/agents/cold-reader.md` と同じ字）。意味は同じ。report の中の読み手も同じ断片を差し込む。
- 写した: 複数の作業を切り替えながら読む読み手の段落（md:9）と、返し方（md:19・md:21）。report の中の読み手の md にも同じ段落が残る（2 つの block が別々に持つ）。
- 外した: 報告の頭に特有の 2 段落（md:11 の頭の後ろに付く物と機械が組む行の決まり、md:13 の「レビューの最終報告のうち、人に決めてもらうところ」）。報告に特有の決まりは report の断片 `report-head-check` が持ち、この block は報告を知らない。代わりに「本文の出どころも用途も知らされていない」の 1 文を足した。
- 移した: 判定の語（md:19 と md:21 の `pass`・`redesign-needed`）を差し込み口 `{passed}`・`{redesign}` に（README 5.3。値は `src/reply.py` の 1 か所、YAML の enum と試験で突き合わせる）。
- まとめた: 返し方の 2 か所（md:19 の ①②③ と md:21 の JSON の形の 1 行）を `## How to answer` の 1 か所に。JSON の形は出力の schema が持つので、結びの 1 文で足りる。
- 足した: 言語の 1 文（`{lang}`。#764）と、`stops`・`guessed` の 1 件を「本文のどこかを名指す 1 文」にする箇条。後者は今の返答の実物（例の run の 3 回とも、どの行も所を名指す 1 文）に合わせた書き方で、受け付けは照らさない。
- 替えた: 区切りの字の日本語（「==== ここから ====」「==== ここまで ====」）を英語に。区切りは本文が資料であることの境なので残す。
- 英語にした（#764）。

1 つ目の commit（日本語の md。README 11.4）の作り方: 今の `cold-check.md` の md:1-9 と md:15-21 を字のまま写し（md:11-13 の報告の頭の 2 段落は写さない）、md:16 を `{text}` に替える（役の定義の 7 行は、この commit では断片にせず字のまま置く）。比べは例の run の 1 回目の本文で、組んだ指示が、今の `cold-check.md` から md:11-13 を除いて本文を差し込んだ字と同じになることを照らす。2 つ目の commit で上の英語の md に替え、この節の差の一覧どおりかを並べて審査に出す。

## 3 script の node

- `cold_prep.py`: `os.environ.get("INPUTS_TEXT")`・`INPUTS_LANG` を字のままで読み、`ports` の口（`file`・`text`。名は土台の `ports.py` に合わせる）に渡す。place の中を全部消す。
  - 本文のファイルが読めない（在らない・UTF-8 でない）→ `due: false`・`prompt: ""`・`reason: 読ませる本文のファイルを読めない（<パス>: <型の名>）`。
  - 本文が空白だけ → `due: false`・`reason: 読ませる本文が空`。
  - ほかは `prompt.render("cold", values, when)` で組み、`cold-prompt-1.md` に書き（口が書く作りなら口に任せる）、`{due: true, prompt, reason: ""}` を返す。
  - 落ちない（中の誤りは捕まえて `due: false` と `<型>: <文>`）。
- `finish.py`: `with:` の `prep`（`cold-prep` の返り。null は prep が落ちた）と `reply`（役の返答。飛ばされた・落ちた時は null）を受ける。
  - prep が null → `status: failed`・`reason: 支度の node が落ちた`。
  - prep の `due` が偽（prep が止めた）→ `status: failed`・`reason` は prep の訳・`verdict: ""`・`pass: false`・`stops`/`guessed` は空・`decidable: false`・`stuck` は空。
  - 返答が null（役が落ちた・飛ばされた）→ `status: failed`・`reason: 初見の読み手の役が返答を返さなかった（役が落ちたか飛ばされた）`・`stuck: [初見の読み手の返答を読めない（判定の語が無い）]`。
  - 返答を `src/reply.py` の `read(reply)`（`_cold_of` の写し）で読む。`verdict` が語のどれでもなければ `status: failed`・`reason: 初見の読み手の返答を読めない（判定の語が無い）`・`stuck` はその 1 行。
  - 読めれば `status: ok`・`reason: ""`、`verdict`・`pass`・`stops`・`guessed`・`decidable`・`stuck` を返す。
  - 返答を `reply.json` に、返りを `read.json` に書く。どの道でも `report`（9 節）を付ける。落ちない。

## 4 受け付け

受け付けの loop は置かない（今と同じ。今も読み手の返答は `output_format` の型だけで受け、中身の照らしは書き手の受け付けがしていた）。訳:

- 読み手の返答に、機械で照らせる事実が無い（止まった所が本文に在るかは、所を名指す 1 文でも字の一致では照らせない）。
- 出し直させると、読み手が同じ本文を 2 回読むことになり、「初見」が崩れる。
- 型に合わない返答は Archon が落とし、`retry`（2 回）が起こし直す。読めない返答は `finish` が `failed` と名指す（黙って `pass` にしない。今の `COLD_UNREADABLE`）。

## 5 単独で呼ぶ

```sh
bin/works-factory <読ませるフォルダを blocks/ にする引数（名は実装で決める）> workflow run works-factory-cold-read \
  --cwd <対象> --input text=docs/README-draft.md
```

出力は `workflow get <run>` の `finish` の返り。始めの記録は要らない。殻の引数の名は（未確認）（world の 7 節と同じ）。

## 6 元の works と graphloops の同じ場面

元の works は `works/blk-report/`（`blk-report.yaml:114-123` の初見の読み手・`commands/report-write-cold.md`・`lib/report_roles.py`）、graphloops は `prompts/review-loop/report.cold_check.md` と `rules/review-loop.py:3619-3626`。ほかに convergence-loops の `agents/cold-reader.md`（汎用の初見の読み役）と gates の `hooks/coldread-gate.py`（投稿の前の初見の確かめ）。どれも `~/src/claude-plugins/` の下。

同じ物（この block が持つ）: 新しい会話・道具なし・判定の語と 4 つの欄（元の works・graphloops と同じ JSON）・冒頭の 3 行の確かめ（元の works・gates と同じ。graphloops は書き手の指示にしか無い）。

この block に無い物・違う物と、その訳:

1. 書き手を拒んで書き直させる関門と、3 回目の受け取り（元の works の `GIVE_UP_AFTER`、工場の `runreport.accept`）: report の block の中に残る（1.6）。この block は判定を返すだけ。最後の回の扱い（元の works は報告の頭に「初見の確かめを通っていない」を置き、工場は機械の事実の拒みの数の行の尾に置く。`84ea9ca9`、issue #495 の 4。本流には #503 `217826cb` の道で入った。merge の道は（未確認））も report の決め。
2. 読ませる本文の組み立て（工場は機械の報告の冒頭・書き手の頭・書き手の語の定義を、pack の語を平易な言い方に替えてから読ませる。#660 `9d8472cc`、機械の冒頭は #693 `427b679c`）: report の中に残る。この block は受けたファイルを字のまま読ませる。
3. 読み手の模型: 元の works は読み手の node に sonnet・medium を直に書いた。工場は書き手と同じ群 `@wf-report`（#658 `d0b086a2`、issue #628）。この block も `@wf-report`（群の表 `lib/launchgroups.py` を替えれば読み手だけの群を作れる。振る舞いを変える提案なので作り直しの外）。
4. 所見の種類を 5 つに分ける（gates の詰まり・なぞり・冗長・疑問・補完。止めるのは詰まりとなぞりだけ）: 工場に無い（（未確認）: `git log -S` で語が見つからず、外した記録も無い）。この block にも足さない（振る舞いの変更）。
5. 2 回目からの読み手に前の回の所見と直しの差分を渡す（gates）: 工場に無い（（未確認））。この block は 1 回だけ読むので当たらない。
6. `decidable` を何にも使わない: 元の works も同じ。この block も返すだけ。
7. 道具: convergence-loops の読み役は呼び手が渡す 1 本のファイルを Read できる。工場と元の works は使わない。この block も道具なし（本文は指示に貼る）。

この block が今より良くする物: 初見の確かめを報告の外の文にも使える汎用の block にする（今は報告の中にしか無い）・役の定義を断片 `role-cold-reader` の 1 か所にし、report の中の読み手と共に使う・読めない返答を通らなかった事として名指す（`COLD_UNREADABLE`。今のまま）・起動の誤りの `retry`（今のまま。元の works の読み手の node には無かった）。

## 7 守る keep-essence

12 の仕組み（README 10 節。元の works の `docs/keep-essence.md` の、作り替えでも外さない仕組みの一覧）のどれも担わない。

## 8 試験の前の値（fixture と試験が共に使う）

`tests/blocks/cold_read/values.py` に、例の run の 1 回目の本文（DB の `node_output.body` を写した約 11 KB の字）と、台本の返答 2 つ（`pass` と、止まった所 2・推測 1 の `redesign-needed`）を置く。

## 9 報告の行（`src/report.py`）

- `pass` でない時だけ 1 行: `初見の読み手が通さなかった: <stuck を「；」でつないだ 1 行>`（`oneline.one_line` で畳む。今の `runreport._cold_facts` と同じ形の字）。
- `failed` の時は 1 行: `初見の読み手: 読めなかった（<reason>）`。
- `pass` なら行を返さない。

## 10 自分で決めた事

1. この block を報告に依らない汎用の初見の読み手にし、報告の書き手との往復と報告の頭の決まりは report の block の中に残す（調整役の決め。report の設計書の決めに合わせた）。根拠: 書き手の回ごとの受け付けが同じ回の読み手の判定で決まる・読み手の後に受け付けの node を graph に置くと README 2 節の憲法の 3（block は宣言した port だけで受け渡し、ほかの block を名指さない）に触れる・report を単独で回した時にも初見の確かめが要る。同じ役が 2 か所に在る分は、役の定義を断片 `role-cold-reader` の 1 か所に置くことで、定義の直しが 1 本で閉じる（README 1.2 の I）。
2. 受け付けの loop を置かない（今と同じ）。根拠は 4 節。
3. 前の回の所見を読み手に渡さない（今と同じ）。根拠: 初見の確かめは毎回まっさらに読むことが芯。gates の形（6 節の 5）に替えるのは振る舞いを変える提案なので、作り直しの外。

## 11 試験

- standalone の fixture（`blocks/cold-read/fixtures/`。script の node も差し替え、配線を見る）:
  - `standalone.stubs.yaml`: 入力は `text: README.md` だけ。`cold-prep` を `{due: true, prompt: "…", reason: ""}`、`cold` を `{verdict: pass, stops: [], guessed: [], decidable: true}`、`finish` を `status: ok` の返りで差し替える。`expect: completed`・`reached: [cold-prep, cold, finish]`。
  - `redesign.stubs.yaml`: `cold` が `redesign-needed` と止まった所 1 つ、`finish` の返りの `pass: false`・`stuck` 1 行。
  - `unreadable.stubs.yaml`: `cold-prep` が `{due: false, prompt: "", reason: 読ませる本文が空}`、`reached: [cold-prep, finish]`（`cold` は飛ばされる）、`finish` が `status: failed`、run は `completed`。
- `tests/blocks/cold_read/test_cold_read.py`（script を子のプロセスで回す。始めの記録の無い使い捨ての `ARTIFACTS_DIR` と git のリポジトリで、port の値だけを渡す）:
  - `cold_prep` が組んだ指示に、断片 `role-cold-reader` の本文と本文の字が入り、報告の頭の決まりの字（「頭の後ろ」「機械が組んだ事実」）が入らない。
  - 本文の字がそのまま指示に入る（`$x.output.y` の形の字と `{name}` の形の字を含む本文で、置き換わらずに残る。今の test-gate の `test_reject_with_a_reference_reaches_the_prompt_verbatim` と同じ確かめ）。
  - 本文のファイルが無い・空 → `due: false` と訳。
  - `finish`: `pass` の返答 → `pass: true`・`stuck: []`。`redesign-needed` → `stuck` が `止まった所: …`・`推測で埋めた所: …` の順。`redesign-needed` で欄が空 → `（止まった所・推測の欄が空）`。壊れた返答・語の外 → `failed` と `初見の読み手の返答を読めない（判定の語が無い）`（今の `lib/tests/test_runreport.py:1721-1725` の `_cold_of` の確かめの写し）。null → `failed`。
  - `src/reply.py` の `VERDICTS` が YAML の `cold` の `output_format` の `verdict` の enum と同じ（yes/no）。
- `tests/blocks/cold_read/test_prompt_compare.py`（README 11.4）: 8 節の値で、1 つ目の commit では日本語の md で組んだ指示が、2.6 の「1 つ目の commit の作り方」の字と同じになる（空白と改行の違いは除く）。2 つ目の commit でこの照らしを消し、並べた物を PR に載せて 2.6 の差の一覧どおりかを審査が見る。
- この block の外に残る試験（report の block と、その試験）: `tests/workflows/test_report.py::ShapeCase.test_cold_reader_is_told_the_machine_heading`・`ColdPrepScriptCase`・`AcceptScriptCase.test_cold_redesign_three_times`、`lib/tests/test_runreport.py` の `ColdBodyCase`・`test_cold_rejects_twice_then_takes_with_mark`。
- e2e の `tests/e2e/evidence.json` に、この block の行は無い（報告の初見の確かめの印は report の行が持つ）。

## 12 未確認

- 起動の殻で `blocks/` を読ませる引数の名と、5 節の命令の正確な形。
- `prompt.render` が値の中の `{…}` を差し込み口として読み直さないか（土台の `prompt.py` の決まり。11 節の試験で縛る）。
