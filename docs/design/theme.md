# block の設計書: theme（設計の案の書き手）

- 何の話か: 工場の対話モードの run に足す「設計の段」（issue #862）のうち、テーマ（コードに落とす前の設計の問い）から 1 周分の設計の案を書く役を、単独で呼べる block `workflows/theme/` にする設計。型は [README.md](README.md)、書き方は [world.md](world.md) に従う。設計の段の全体（入口・line の配線・事前審査の形 `theme`・降りる道・設計へ戻す道）は設計の下書き `docs/plans/2026-10-27-design-stage.md` が正本で、この設計書はそのうち書き手の block と設計の案の形と作り変えの照らし（下書きの 3・4・6 章）と、E11 の答え（同じく 11 章）を移した物。
- 読む人: この block を直す実装の役と、line の配線（下書きの 15 章の T3）を作る実装の役。
- 持ち主に求めること: なし。持ち主の決めは `theme-stage`（`docs/owner-decisions.md`）。この block で自分で決めた事は 11 章に集めた。
- 決めたこと: block は 3 つの頂の node（`intake`・`write-loop`・`finish`）で、loop の本体は prep 2 つ・AI の役 2 つ・受け付け 1 つ（形は plan の block と同じ）。返す設計の案の形は 2 つ以上の block が読むので `workflows/.shared/schemas/theme-design.schema.json` に置く。受け付けは yes/no の照らし 9 つ（4 章）と、作り変えの照らしの覆いの照らし（6 章）。3 回拒まれたら諦める。往復の記録と止めは line が持ち、この block は前の周を port `prior` で受けて 1 周分の案を返す。

この文書の語は README の頭の物と、下書きの「語」のセクションの物を使う。ほかに:

- テーマの md: テーマの文を書いた md 1 本。名指す設計書のセクションと、取り次ぐ会話が始めに頼んだ調べものの結果を書いてよい（下書きの 2.1 の 1）。line の `start` が run の置き場の `theme.md` に固めて、この block の port `theme` に渡す。
- 設計の案: 書き手が 1 周ごとに返す JSON（3 章。形の名 `theme-design`）。
- 人の答えの行: 承認ノードの答えの `text` の見出しのセクションと受け箱の行を、渡す側（line の `theme-turn`）が行ごとに分けて id `H<n>` を付けた物（7 章）。
- 持ち主: このリポジトリの owner（決めを下す人。README の語）。この文書の「人」は承認ノードに答える人で、ふつうは持ち主。人の答えの `by: owner` はその人が決めたことを指す。
- 取り次ぐ会話: 工場の外で持ち主と話す AI の会話（利用者が works-factory を呼ぶ Claude Code の会話など）。持ち主の言葉を読み取り、run への答えに整える。工場の機能ではない（下書きの語）。
- port・form: port は block が YAML の `inputs:` と出力で宣言する受け渡しの口。form はその値の形（`file`・`text`・`json(<形>)`・`jsonl(<形>)` など。README の 4 章）。形の名の頭の `shared:` は `workflows/.shared/schemas/`、`lib:` は `lib/` の下の形、頭の無い物は block の `schemas/` の形。
- 作り変え: 今在るファイルの本文を組み替える変更（`changes` の `op: rework`）。`edit` は今の本文に足す・一部を直す変更で、作り変えの照らし（6 章）は `rework` の行だけに当てる。
- 固めた版: 対象のリポジトリの HEAD の追跡ファイル（`lib/design.py` の `anchor_misses`）。名指し `<パス>:<行>` はこの版で照らす。起点の木（port `base`）とは別で、`base` を数えるのは作り変えの照らしだけ。
- `spawns`: 外への検索の決まりの断片 `query-rule` の中の、下請けの役を起こす役にだけ入れる段落の切り替え。書き手は下請けを起こさない（11.2 の 5）ので偽。
- 模型の群: AI の node の `model` に書く群の名（`lib/launchgroups.py`）。同じ群の役は同じ AI のモデルの割り当てで回る（`workflows/AGENTS.md` の E7）。
- 起点の木: port `base` が名指す版（空なら HEAD）のファイルの木。作り変えの照らしはこの木のファイルの行を数える。
- line: 工場のメイングラフ `works-factory-line`（README の語の graph）。設計の往復の loop `theme-rounds` の本体でこの block を周ごとに include して回し、往復の記録と止め時を持つ。
- place: block が自分のファイルを書くフォルダ。run の置き場（run ごとに成果物と記録を置くフォルダ）の中に、block ごと・include ごとに分かれて在る（README の語と 4.4）。
- 周と回: 周は設計の往復の 1 往復分（line の loop `theme-rounds` の 1 回り）。回はこの block の中の loop `write-loop` の 1 回り（書き手か出し直しの役が答え、受け付けが照らす 1 回）。拒否は周ごとに数え、1 つの周の中で 3 回拒まれたらその周を諦める。
- 頂の node: block の YAML の `nodes:` に直に並ぶ node（loop の本体の中の node でない物）。
- 降りる: 承認された設計から依頼の行を作り、同じ run のまま判定と計画の往復へ進むこと（下書きの 8 章）。
- keep-essence: 作り直しでも守る 12 の仕組みの一覧（README の 10 章）。この文書が引くのは 4（3 回拒まれたら諦める）・9（独立設計）・12（世界の解）。
- 独立設計: 目的の文と人が決めた前提だけから、案を見ずに別の役が設計する仕組み（block `independent-design`）。審査役はその設計と書き手の案を比べて外れを探す。
- 世界の解: 問題の類ごとに世の中の定石を一次の出典で調べる観点（block `world`）。その結果の行（類・定石・比べ）が port `world_rows` で届く。
- Archon・ASF: Archon は工場が載る、AI の処理をグラフにして YAML で書いて回す道具。ASF は Archon の作者が Archon のリポジトリの `.archon/workflows/sdlc/` に置くグラフの束で、工場は呼ばずに型だけを採る（根の `AGENTS.md` の E8）。
- E 番号・憲法: 根の `AGENTS.md` と `workflows/AGENTS.md` の決まり。E11 は仕組みを足す前に Archon・ASF・本当に要るかの 3 つを確かめる決まり、E13 は指示の md と `lib/` に特定の言語・試験の実行器の名を書かない決まり。
- MADR: 設計の決めを md に書く広く使われる書式（Markdown Architectural Decision Records）。
- PR T1〜T4: 下書きの 15 章の PR の番号。T1 がこの block、T3 が line の配線、T4 が本物の AI の役で回す実走。

## 1 block の全体

### 1.1 役

テーマの md と、前の周の設計の案・往復の記録・人の答え・世界の解の行・方針から、1 周分の設計の案を書かせる。設計の案は、問いの言い直し・前提（人が決めた物と仮の物）・今在る物・設計の中身・在る物で足りない訳・持ち主に聞く問い（案・推し・代償）・部署の決め・変える所・作り変えの照らし・前の穴と人の答えへの答えを持つ。受け付けが yes/no で照らし、通った案と、人と審査役に見せる md を返す。

### 1.2 port

入力（YAML の `inputs:`）:

| 名 | form | 既定 |
| --- | --- | --- |
| `theme` | `file` | 必須 |
| `prior` | `json(shared:plan-converge.schema.json)` | 空 |
| `prior_design` | `json(shared:theme-design.schema.json)` | 空 |
| `answers` | `json(human-answers.schema.json)` | `[]` |
| `world_rows` | `jsonl(lib:world-row.schema.json)` | 空 |
| `policy` | `file` | 空 |
| `recorded` | `json(shared:recorded.schema.json)` | `[]` |
| `base` | `text` | 空 |
| `lang` | `text` | 空 |

- `prior` は往復の記録。前の周までの審査の穴と答えを持つ。空は 1 周目。周の番号はこの往復の数 + 1。
- `prior_design` は前の周の設計の案。書き手は Read で読み、穴と答えが求めない所は保つ。
- `answers` の形は block の `schemas/human-answers.schema.json`（7 章）。
- 独立設計の返答は受けない。独立設計と案を比べるのは審査役（事前審査の形 `theme`）だけ（keep-essence の 9。下書きの 4.2）。

出力（`finish` の `output_format`。`returns: finish`・`outcome_field: ok`）: `ok`・`status`（`ok`・`gave_up`・`failed`）・`design`（pointer。`json(shared:theme-design.schema.json)`）・`design_md`（pointer。`file`）・`reason`・`report`。受けた案が無ければ 2 つの pointer は null。

### 1.3 node の並び（`workflows/theme/works-factory-theme.yaml`）

1. `intake`（script `intake.py`）: port を読み、周のフォルダ `r<k>/` を開く。読めない port（テーマの md が無いなど）は書き手を起こさない（`due: false` と訳）。落ちない。返答 `{due, round, reason}`。
2. `write-loop`（`loop_group`。`max_iterations: 3`・`fresh_context: false`・`until_bash` は `write-accept` の `done`）。本体の層はどれも node 1 つ（会話を続ける役の直前に 2 つ以上の node の層を置かない。plan の block と同じ）:
   1. `write-prep`（script `write_prep.py`。`with: {prev: "$LOOP_PREV.write-accept.output.ok"}`）: 前の回の受け付けが拒み、合わせた答えの控え（前の回に書き手が返した答えの控え。周のフォルダの `candidate-theme.json`。出し直しの役が返した欄はこれに合わせる）が在れば `{prompt: "", resubmit: true}`。なければ書き手の指示を組む。
   2. `theme-writer`（AI。`when: resubmit != true`）: 書き手。2 章。
   3. `theme-fix-prep`（script `fix_prep.py`。`when: resubmit == true`）: 出し直しの役の指示を組む。
   4. `theme-writer-fix`（AI。`when: resubmit == true`）: 書き手の会話の続きで、拒まれた欄だけを返す。型は書き手と同じ（#832）。
   5. `write-accept`（script `write_accept.py`）: 受け付け（4 章）。
3. `finish`（script `finish.py`。`trigger_rule: all_done`）: 出口。落ちない。

place の直下に `current-round.json`（`{round}`）と組んだ指示（`theme-writer-prompt-<n>.md`・`theme-writer-fix-prompt-<n>.md`）。周のフォルダ `r<k>/` の中に `intake.json`・`prior.json`・`prior-design.json`・`rejects-theme.json`・`candidate-theme.json`・`design.json`・`design.md`・`crash.json`・`finish.json`。名は `src/files.py` だけが持つ。line は同じ include を周ごとに回すので place は周をまたいで同じ。周のフォルダに分けて、拒否の数えを周ごとにする。

### 1.4 コードの置き場

- `workflows/theme/src/files.py`: place のファイルの名・周の番号。
- `workflows/theme/src/steps.py`: 入口・指示の値・受け付けの順・出口。
- `workflows/theme/src/check.py`: 受け付けの照らし（4 章と 6 章）。
- `workflows/theme/src/render.py`: 設計の案の md（問いは MADR と同じ並び）。
- 使う `lib/`: `converge`（`held`・`owed_faces`・`answer_gaps`）・`design`（`anchors`・`anchor_misses`）・`rolekit`（却下の控え・出し直し・諦め）・`worldmark`（`rows`）・`policy`（`PASTE_CAP`）・`jsonfile`・`oneline`。
- 共通の形: `workflows/.shared/schemas/theme-design.schema.json`（この block と line の `theme-descend` が読む）。

### 1.5 つなぎ方（graph の側。block には書かない）

line の `theme-rounds` の loop の本体で `include: works-factory-theme` を id `theme` で取り込む（下書きの 2.2 の 4。PR T3）。block の node の id に `theme` は無い（README の 7.1 の 13）。この block は葉の block（ほかの workflow を名指さず、入口の node `intake` は script）なので、line 以外の graph からも include できる（憲法の 3 の外し `leaf-include`）。

## 2 node の設計シート: theme-writer（書き手）

### 2.1 役

テーマから 1 周分の設計の案を書く。リポジトリを読み、web を引ける。ファイルは変えない。

### 2.2 port

`theme`・`prior`・`prior_design`・`answers`・`world_rows`・`policy`・`recorded`・`base`・`lang`（どれも block の port。`intake` が周のフォルダに固め、`write-prep` が読む）。

### 2.3 組み立ての順（`prompts/theme-writer.md`）

1. 却下（`rejected` の段落。前の回までの却下があれば `{shared:rejected}`。値 `{rejection}` は控えの全部）。
2. 役の頭（決まった文）。
3. テーマ（`{theme_file}`・行の番号つきの本文 `{theme_text}`）。前提の出どころを `theme:<行>` で名指せるように番号を付ける。
4. 前の周の案（`prior_design` の段落。`{prior_design_file}`）。
5. 答えの要る穴（`owed` の段落。`{owed_rows}` は `converge.owed_faces` の行。`block_answers` に 1 行ずつ答える）。
6. 人の答え（`answers` の段落。`{answer_rows}`。持ち主の言葉は字のまま運び、取り次ぐ会話の読みと分ける。`answers_used` に全部の id）。
7. 世界の解（`world` の段落。`{world_rows}`）。
8. 記録された方針（`{shared:recorded-policy}`。値 `{recorded_rows}`・段落 `recorded_none`）。
9. 方針（`policy` の段落。`{shared:policy}`）。
10. 外への検索の決まり（`{shared:query-rule}`。`spawns` は偽）。
11. 書き方（決まった文。下書きの 4.3 の観点を 10 の手順にした物）: 問いを言い直す → 前提（人が決めた物は出どころを名指す・仮の物は訳）→ 今在る物を先に挙げる → 設計（在る物に足す形を先に）→ 在る物で足りない訳 → 方針の文書が求める確かめに答える → 決まりで決まる物は聞かずに出どころつきで書き、聞く物は答えで動きが変わる物だけで推しを先に、捨てた案と代償 → 変える所 → 作り変えでは今の中身を 1 つずつ挙げて行き先を付け何も落とさない（起点の版 `{base_rev}`）→ 狭める所。
12. 答え方（決まった文と `{lang}`）。

特定の言語・試験の実行器・このリポジトリの決まりの名は書かない（E13）。対象の決まりが求める確かめ（このリポジトリなら E11 の 3 つ）は、方針の文書から読んで `checks` に答えさせる。

### 2.4 返す形

`theme-design`（3 章）。根の `required` は空にし（出し直しの役と同じ型にするため。#832）、根の要る欄は受け付けが `rolekit.resubmitted` の `required` で照らす。人に見せる欄（`question`・`purpose`・各 `what`・`why`・`why_not`・`answer`・`ask`・`pick_why`・`cost`・`gain`・`gist`・`how`・`declined_why`）は `{lang}`。

### 2.5 描いた骨組み（筋書きの値）

本物の run はまだ無い（PR T4 で回す）。standalone の筋書き（テーマの md は筋書きの作業ツリーの `README.md`、ほかの port は空）の値で描いた:

```text
You are the design writer. A person brought a theme: …
## The theme
The theme file is README.md. Its text, with line numbers …
   1  # Fixture target
## Recorded policy
…
Recorded policy: none (no row below can be named).
Rules for queries to outside services and for the sources you use: …
## How to write the design
1. Restate the question …
## How to answer
…
```

### 2.6 今の指示との差

新しい役で、今の指示の作り変えではない。観点は修正案の役（`workflows/plan/prompts/plan-writer.md`）の型を使い回した: 前の穴への `block_answers`（形は `lib/converge.py` の `ANSWER_SCHEMA` と同じ）・狭める所 `narrows`（計画の `narrows` の決め手の欄 `decided_by`・`undecided_because`）・共通の断片 `recorded-policy`・`policy`・`query-rule`・`rejected`・`resubmit`。計画の形の `files`・`tests` の行は持たない（書き換えの細目と試験は降りた後の計画の役が書く）。

## 3 設計の案の形（`workflows/.shared/schemas/theme-design.schema.json`）

欄の並びは「何を問うか → 何を前提にしたか → 今何が在るか → 何を足すか（在る物では足りない訳）→ 問い（案・推し・代償）と部署の決め → 変える所 → 作り変えの照らし → 前の穴と人の答えへの答え」。

- `question`・`purpose`: 字。
- `premises[]`: `{id: P<n>, what, by: owner|assumed, from}`。`owner` の `from` は人の答えの id `H<n>` か、テーマの md の行 `theme:<行>`・`theme:<始め>-<終わり>`。`assumed` の `from` は置いた訳。
- `current[]`: `{id: N<n>, what, where: <パス>:<行>}`。
- `parts[]`: `{id: D<n>, what, where, why}`。
- `reuse[]`: `{part: D<n>, existing: [N<n>…], enough: false, why_not}`。
- `checks[]`: `{rule: <パス>:<行>, answer, where}`。
- `asks[]`: `{id: Q<n>, ask, pick: A<n>, pick_why, options: [{id: A<n>, what, cost, gain}]}`（案は 2 つ以上）。
- `decided[]`: `{id: R<n>, what, by: <パス>:<行>, why}`。
- `changes[]`: `{id: C<n>, where, what, op: add|edit|rework|remove, parts: [D<n>…]}`。降りる時に依頼の行になる。
- `inventory[]`: `{path, lines: "<始め>-<終わり>", gist, to: keep|move|merge|drop, dest, why}`（6 章）。
- `narrows[]`: `{what, decided_by?, undecided_because?}`。
- `block_answers[]`: `{key, handled: fixed|disputed, how}`。
- `answers_used[]`: `{answer: H<n>, applied?: [<欄の id>…], declined_why?}`。

計画の形と分ける訳・MADR との対応の表と欄の名を自作のままにする訳は、下書きの 3 章のまま（ここに写さない）。人に見せる md（`design.md`）は、問いを MADR と同じ並び（問い → 案 → 案ごとの得と代償 → 推しと訳）で描く（`src/render.py`）。

## 4 受け付け（yes/no の照らし。憲法の 6）

`write-accept` が `src/check.py` の順で照らし、外れた所ごとに拒否の行を 1 つ返す。拒否の文は返答の中身で変わるので日本語のまま Python が組む（README の 5.3）。

1. 形（`shared:theme-design.schema.json`）。外れたら後の照らしをしない。
2. `<パス>:<行>` の名指しが固めた版に在る（`lib/design.py` の `anchor_misses`）。`current` の `where`・`decided` の `by`・`checks` の `rule` は名指しを 1 つ以上要る。`parts` の `where`・`checks` の `where` は、名指しが在ればそれを照らす（足す部品の置き場は今は無いので名指しを要らない）。
3. `asks` の各行の `pick` が案の id のどれか（案が 2 つ以上・`cost` と `gain` が空でないのは形が照らす）。
4. `decided` の各行の `by`（2 の名指し）。
5. `reuse` の各行の `part` が `parts` の id、`existing` が `current` の id（空なら `why_not`。形が空でない字を求める）。
6. 作り変えの照らし（6 章）。
7. `block_answers` が前の往復の答えの要る穴の全部の key に答える（`converge.answer_gaps`。往復の記録が無い 1 周目は照らさない）。
8. `answers_used` が渡された人の答えの全部の id を持ち、渡していない id を持たず、行ごとに `applied` か `declined_why` を持つ。
9. `premises` の `by: owner` の各行の `from` が、渡された人の答えの id か、テーマの md の空でない行を指す。

ほかに、欄ごとの id が重ならないこと・`changes` の `parts` が `parts` の id を指すことを照らす（名指しの先を 1 つに決めるため）。拒否は控え `rejects-theme.json` に積み、3 回目（`rolekit.GIVE_UP_AFTER`。loop の `max_iterations` と同じ数）で `done`・`give_up`。諦めた周の出口は `status: gave_up` と最後の拒否を返す（keep-essence の 4）。出し直しは `rolekit.resubmitted` が前の答えの控え `candidate-theme.json` と `rolekit.merge_fields` で合わせてから全体を照らす。

## 5 script の node

- `intake.py`: `INPUTS_THEME`・`INPUTS_PRIOR`・`INPUTS_PRIOR_DESIGN`・`INPUTS_ANSWERS`・`INPUTS_WORLD_ROWS`・`INPUTS_POLICY`・`INPUTS_RECORDED`・`INPUTS_BASE`・`INPUTS_LANG` を読む。`ports.run` で落ちない。
- `write_prep.py`: `INPUTS_PREV` を読む。指示を組めなければ `crash.json` に訳を残して落ちる（出口が訳を返す）。
- `fix_prep.py`: 入力を読まない。誤りの扱いは `write_prep.py` と同じ。
- `write_accept.py`: `INPUTS_REPLY`・`INPUTS_FIX_REPLY` を読む。落ちない。
- `finish.py`: 入力を読まない。落ちない。

## 6 作り変えの照らし

### 6.1 形

`inventory[]` の行 `{path, lines, gist, to, dest, why}`。手本は `docs/plans/2026-10-24-fix-weapons.md` の 1.4 と付録 A（段落か箇条 1 つずつ行番号つきで挙げ、行き先と入った訳を付けた）。

- `to`: `keep`（そのまま残す）・`move`（`dest` の所へ移す）・`merge`（`dest` の行とまとめる）・`drop`（消す。`why` が要り、`narrows` に同じ行を持つ）。
- 訳の分からない行は `drop` にせず `keep` か `move` にする（指示に書く）。

### 6.2 機械の照らし（4 章の 6）

1. `changes` の `op: rework` の各パス（`where` の頭のパス）が起点の木に在り、そのファイルの空でない行の全部が、`inventory` のその `path` の行の `lines` の和に入る（覆いの抜けが無い）。
2. 範囲がファイルの行の数の中で、同じファイルの範囲が重ならない。
3. `drop` の行は `why` が空でなく、`narrows` に同じ `path` と `lines`（`<path>:<始め>-<終わり>` の字）を `what` に名指す行が在る。
4. `move`・`merge` の行の `dest` が `parts` か `changes` の id を指す。

行の分け方（段落か箇条か）は書き手が決め、機械は覆いだけを照らす（段落を機械が割る道具を足さない。下書きの 13 章の 8）。行き先の正しさは審査役が見る（下書きの 5.2 の 4）。修正の後に機械で照らす形は下書きの 14 章の 4（後回し）。

## 7 人の答えの行（`workflows/theme/schemas/human-answers.schema.json`）

`[{id: H<n>, kind, text, ask?, pick?, from?}]`。`kind` は `owner_words`（持ち主の言葉。字のまま運ぶ）・`research`（調べものの結果）・`ask_answer`（問いへの答え。`ask: Q<n>` と `pick: A<n>`）・`reading`（取り次ぐ会話の読み）・`note`（見出しの無い一言）。承認ノードの `text` の見出しのセクション（下書きの 7.2）と受け箱の行を、line の `theme-turn` が行に分けて番号を付ける（PR T3）。この block は行を受けるだけで、`text` を読み分けない。

## 8 単独で呼ぶ

```text
bin/works-factory workflow run works-factory-theme --cwd <対象> --input theme=<テーマの md のパス>
```

答え・往復の記録・前の案を足す時は `--input answers='[{"id":"H1","kind":"owner_words","text":"…"}]'` などを足す。

## 9 試験

- standalone の筋書き（`fixtures/standalone.stubs.yaml`）: テーマの md だけで最後まで届く。書き手の返答だけを差し替え、受け付けを全部通る小さな案で `finish` まで。
- `fixtures/resubmit.stubs.yaml`: 出し直しの役の md を本当の `theme-fix-prep` で組む（`write-prep` だけを `resubmit: true` に差し替える。plan の block の筋書きと同じ形）。
- `fixtures/missing-theme.stubs.yaml`: テーマの md が無いと書き手を起こさず、出口が `failed` を返す。
- 振る舞いの試験 `tests/blocks/theme/test_theme.py`: 全部通る案が pointer と md で返る・周の番号が往復の数 + 1・3 回で諦める・出し直しが返した欄だけを合わせる・受け付けの照らしの 1〜9 と 6.2 の 1〜4 のどれも、全部通る案を 1 か所だけ崩すと拒む・起点の版の行を数える・書き手と出し直しの役の型が形 `theme-design` の写しで同じ物・loop の回数が `rolekit.GIVE_UP_AFTER`・node の id に `theme` が無い。
- 守る keep-essence: 4（3 回拒まれたら諦める）。9（独立設計）は、この block が独立設計の返答を受けない形で守る。

## 10 報告の行

- 受けた案が在る: `設計の案: 問い N・部署の決め N・変える所 N（作り変え N）・作り変えの照らしの行 N` の 1 行。
- 受けた案が無い: `設計の案: <reason>` の 1 行。

## 11 自分で決めた事（持ち主に聞かない物）と E11 の答え

### 11.1 E11 の 3 つの確かめ（下書きの 11.2 から移した）

1. Archon が持っているか: 往復の本体の唯一の終わりの承認ノードと、答えを次の周の頭で読む形は持つ（今の `plan-rounds` が使う）。承認ノードの答えは `{decision, text}` だけで、欄を持つ答えの形は無い。設計の段・問いの選び肢を運ぶ仕組みは無い。→ 承認ノードと loop は Archon の物を使い、答えのセクションは `text` の中の書き方で運ぶ（line の側。PR T3）。この block は人の答えを行で受けるだけ。
2. ASF が持っているか: `archon-plan`（`.archon/workflows/sdlc/plan-entry/archon-plan.yaml`）は「何を作るかは決まり、どう作るかが決まっていない」時の計画で、選んだ案と捨てた案と訳を書き、人にしか答えられない問いで止まって人の一言で計画し直す。→ 型を採る（捨てた案と訳・人の一言で設計し直す）。違い: ASF の計画は 1 本の役で、往復ごとに別の役が攻める目と、計画の後に同じ run で作り始める道を持たない。採った型は `docs/asf-notes.md` に 1 行足した（E8）。
3. 本当に要るか: 当たる失敗は run 19268881（修正案の形に設計の問いが押し込まれ、選び肢・推し・代償を出せなかった。下書きの 1.2）と、直し方の型の相談を工場の外で回した事（issue #862）。keep-essence の 9（独立設計）・12（世界の解）を設計の問いにも当てる。新しい役はこの書き手 1 つで、ほかは在る物の足し方（下書きの 1.3 の終わりの (a)）。

### 11.2 この block で決めた事

1. 出し直しの役の指示を組む prep を `theme-fix-prep` として分けた（下書きの 4.1 の並びに無い node）。根拠: plan の block と同じ形（`docs/design/plan.md` の 1.3 と 11 章の 9）。出し直しの役は書き手の会話の続きで起きるので本体の層はどれも node 1 つにし、出し直しの役の md を筋書きで本当の prep から組めるように prep を分ける。
2. 却下の数えは `rolekit.GIVE_UP_AFTER`（3 回）。plan の block の網（`NET_AFTER`）は使わない。根拠: 下書きの 4.1「却下 3 回で諦める」と keep-essence の 4。
3. 周ごとのフォルダ `r<k>/`（k は往復の記録の往復の数 + 1）。根拠: line は同じ include を loop で何周も回し、place が周をまたいで同じなので、却下の控えと出し直しの控えを周ごとに分けないと前の周の拒否を数える（plan の block と同じ形）。
4. 人の答えの行の形（7 章）を block の `schemas/` に置き、id を `H<n>` にした。根拠: 下書きは「番号」とだけ書き形を決めていない。`premises` の `from` で答えの番号とテーマの行（`theme:<行>`）を字で見分けるため、頭の字を付けた。形を読むのはこの block だけ（書くのは line）なので `.shared/` に置かない（憲法の 4）。
5. 書き手の道具は修正案の役と同じ（Read・Grep・Glob・WebSearch・WebFetch）にし、Agent を持たせない（下書きの 14 章の 8 の答え）。根拠: 下請けの審査役は往復ごとの事前審査の形 `theme` が担う。持たせるかは実走（PR T4）の後に見る。
6. 模型の群は修正案の役と同じ `@wf-plan-writer`。根拠: 同じ類の役（計画を書く）で、群を足す訳が無い。
7. 受け付けで、ほかに欄ごとの id の重なりと `changes` の `parts` の名指しを照らした（下書きの 4.4 の 9 つに無い）。根拠: `reuse`・`inventory`・`answers_used` の名指しの先を 1 つに決めるのに要る yes/no の照らしで、場面ごとの試験でなく形の照らし（`mechanism-over-tests`）。
8. `drop` の行が `narrows` に「同じ path と lines」を持つかは、`narrows` の `what` が `<path>:<始め>-<終わり>` の字を含むかで照らした。`narrows` に欄を足さない（下書きの 3 章の `narrows` の形のまま）。
9. 名指し `<パス>:<行>` は、下書きの 4.4 の 2 の「作業ツリー」でなく固めた版（HEAD）で照らした。根拠: 既存の `lib/design.py` の `anchor_misses` がこの版で照らすので、同じ部品を使う。`parts` の `where` は足す部品の置き場でまだ無いことがあるので、名指しが在る時だけ照らす。

## 12 未確認

- 本物の書き手の 1 往復の費用と時間（下書きの 2.3 の 6 は計画の役の類からの見込み）。PR T4 の実走で測る。
- 往復の記録 `plan-converge` に設計の案を項目 1 つとして入れて `converge` の止め時がそのまま回るか（下書きの 14 章の 3）。この block の側では、項目を持たない記録でも `converge.answer_gaps`・`owed_faces` が回ることを試験で確かめた（`test_7_block_answers_answer_the_holes`）。line の側の `rounds.decide`・`ask_again` は PR T3 で確かめる。
- 元の works と graphloops に同じ場面（設計の問いに案・推し・代償で答える役）が在ったか（未確認）。工場の git の履歴には、設計の段を外した記録は無い。
