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
- 固めた版: 対象のリポジトリの HEAD の追跡ファイル（`lib/design.py` の `anchor_misses`）。名指し `<パス>:<行>` はこの版で照らす。起点の木（port `base`）とは別で、`base` を数えるのは作り変えの照らしだけ。物差しは 2 つに見えるが、line（工場のメイングラフ。下の語）はこの block の port `base` に、配る値の `base_rev`（run の始めの HEAD）を渡し、テーマの run は差分を持たない（入力 `base`・`pr` と組めない。line.md の 3.3 節）ので、line から回す時は 2 つの照らしが同じ版を数える。この block を単独で回して `base` に別の版を名指した時だけ分かれる（作り変えの照らしは、名指した版のファイルの空でない行の全部が `inventory` の `lines` に入るかを数え〔6.2 の 1〕、名指しの照らしは今の HEAD の行で照らす）。
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
| `answers` | `json(shared:human-answers.schema.json)` | `[]` |
| `world_rows` | `jsonl(lib:world-row.schema.json)` | 空 |
| `policy` | `file` | 空 |
| `recorded` | `json(shared:recorded.schema.json)` | `[]` |
| `base` | `text` | 空 |
| `lang` | `text` | 空 |

- `prior` は往復の記録。前の周までの審査の穴と答えを持つ。空は 1 周目。周の番号はこの往復の数 + 1。
- `prior_design` は前の周の設計の案。書き手は Read で読み、穴と答えが求めない所は保つ。
- `answers` の形は `workflows/.shared/schemas/human-answers.schema.json`（7 章。書く line と読むこの block の 2 つが使うので `.shared/`）。
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

## 7 人の答えの行（`workflows/.shared/schemas/human-answers.schema.json`）

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

1. 出し直しの役の指示を組む prep を `theme-fix-prep` として分けた（下書きの 4.1 の並びに無い node）。根拠: plan の block と同じ形（`docs/design/plan.md` の 1.3 と 11 章の 9）。分ける訳は、出し直しの役の md を筋書きで本当の prep から組めることを照らすため。筋書き（`fixtures/*.stubs.yaml`。AI の node を決まった返りに差し替えて YAML を通しで回す dry-run）の loop は 1 回りだけで、前の回の値 `$LOOP_PREV`（loop の前の回の node の返りを読む Archon の参照）が空なので、本当の `write-prep` が出し直しを選ぶ筋書きは書けない。そこで `write-prep` だけを `resubmit: true` に差し替え、別の node の `theme-fix-prep` を本当に走らせて md を組む（9 章の `resubmit.stubs.yaml`）。分けても、本体の層（同じ時に走る node の組）はどれも node 1 つのままにする（1.3 の 2）。出し直しの役は前の回の書き手の会話の続きで起きる（`fresh_context: false`）ので、その直前に 2 つ以上の node の層を置かないため。
2. 却下の数えは `rolekit.GIVE_UP_AFTER`（3 回）。plan の block の網（`NET_AFTER`）は使わない。根拠: 下書きの 4.1「却下 3 回で諦める」と keep-essence の 4。
3. 周ごとのフォルダ `r<k>/`（k は往復の記録の往復の数 + 1）。根拠: line は `theme-rounds` の loop の本体で同じ `include: works-factory-theme`（この block の取り込み。8 章）を何周も回し、place（block が自分のファイルを書くフォルダ。冒頭の語）が周をまたいで同じなので、却下の控えと出し直しの控えを周ごとに分けないと前の周の拒否を数える（plan の block と同じ形）。
4. 人の答えの行の形（7 章）の id を `H<n>` にした。根拠: 下書きは「番号」とだけ書き形を決めていない。`premises` の `from` で答えの番号とテーマの行（`theme:<行>`）を字で見分けるため、頭の字を付けた。初めは形を block の `schemas/` に置いたが、PR T3 で line の `theme-turn` が同じ形で行を書いて照らすので `workflows/.shared/schemas/` へ上げた（2 つが使う。憲法の 4。設計の案の形 `theme-design` の `answers_used[].answer` の `^H[0-9]+$` もこの形の決めに頼る）。
5. 書き手の道具は修正案の役と同じ（Read・Grep・Glob・WebSearch・WebFetch）にし、Agent を持たせない（下書きの 14 章の 8 の答え）。根拠: 下請けの審査役は往復ごとの事前審査の形 `theme` が担う。持たせるかは実走（PR T4）の後に見る。
6. 模型の群は修正案の役と同じ `@wf-plan-writer`。根拠: 同じ類の役（計画を書く）で、群を足す訳が無い。
7. 受け付けで、ほかに欄ごとの id の重なりと `changes` の `parts` の名指しを照らした（下書きの 4.4 の 9 つに無い）。根拠: `reuse`・`inventory`・`answers_used` の名指しの先を 1 つに決めるのに要る yes/no の照らしで、場面ごとの試験でなく形の照らし（`mechanism-over-tests`）。
8. `drop` の行が `narrows` に「同じ path と lines」を持つかは、`narrows` の `what` が `<path>:<始め>-<終わり>` の字を含むかで照らした。`narrows` に欄を足さない（下書きの 3 章の `narrows` の形のまま）。
9. 名指し `<パス>:<行>` は、下書きの 4.4 の 2 の「作業ツリー」でなく固めた版（HEAD）で照らした。根拠: 既存の `lib/design.py` の `anchor_misses` がこの版で照らすので、同じ部品を使う。`parts` の `where` は足す部品の置き場でまだ無いことがあるので、名指しが在る時だけ照らす。

## 12 未確認

- 本物の書き手の 1 往復の費用と時間: PR T4 の実走で測った（13 章）。1 本の run の値で、テーマが変われば変わる。
- 往復の記録 `plan-converge` に設計の案を項目 1 つとして入れて `converge` の止め時がそのまま回るか（下書きの 14 章の 3）。この block の側では、項目を持たない記録でも `converge.answer_gaps`・`owed_faces` が回ることを試験で確かめた（`test_7_block_answers_answer_the_holes`）。line の側の `rounds.decide`・`ask_again` は PR T3 で確かめる。
- 元の works と graphloops に同じ場面（設計の問いに案・推し・代償で答える役）が在ったか（未確認）。工場の git の履歴には、設計の段を外した記録は無い。

## 13 実走の記録（run 1471a930。PR T4 の real-measure）

本物の AI の役で、テーマの run を 1 本回した。テーマは run 19268881（下書きの 1.2）と同じ 2 行（機能を試験ごと消す依頼で TDD の輪が止まる・振る舞いを変えない整理を工場が単独で直せない）。対象は main の `38cced23`（PR T3 の後）。承認ノードは `gate-start` に continue、`gate-theme` に approve（設計の周 3 の案で降りる。問いは推しを採る）、計画の往復の `gate-design` に approve（計画の周 4 の案で進める）と答えた。修正前の承認ノード `gate-before-fix` は、`gate-design` の答えを合意として読んだので開かなかった（run の記録で `skipped`。`docs/design/line.md` の 2 章）。入力 `tdd_suite` は渡していない。

この章の語（下書き `docs/plans/2026-10-27-design-stage.md` の「語」・`docs/design/plan-review.md`・`docs/design/line.md` の物）:

- 承認ノードの答え: 承認ノード（`gate-*`。人の答えを待つ所）の選び肢は `approve`・`continue`・`stop`・`reject`（`docs/design/line.md` の 2 章）。`gate-start` の continue は起動をそのまま通す答え、`gate-theme` の approve はその周の設計の案を承認して降りる答え、`gate-design` の approve はその周の計画を承認して修正へ進む答え。
- 推し: 役が問いに添えた、選び肢を名指す勧めの答え（`docs/design/line.md` の語）。設計の案では `asks` の `pick`（3 章）。
- 穴・鍵: 穴は事前審査の役が返す指摘 1 件（返りの `faces` の 1 行）。鍵はその穴の識別子（key）で、周をまたいで同じ穴を同じ鍵で挙げ直す。穴の重さは `block`（直しへ進めない穴）か `suggest`。穴の及ぶ所は中央（設計のやり直しが要る）か端（後の段へ申し送れば済む）。
- 消えた: 審査役が返りの `resolved` に、前の周の鍵を「もう穴でない」として挙げたこと。
- fixed・disputed: 書き手が前の周の穴ごとに返す答え（`block_answers` の `handled`）。fixed は直した、disputed は穴でないと異を唱えた。
- clean・settled: 往復の止め時の語（`workflows/line/src/rounds.py` の `decide`）。clean は最後の周の block が 0、settled は 2 周目から最後の周の開いた block に中央が無い（端の block だけを申し送って進む）。

### 13.1 費用と時間

数えは run の記録の node ごとの `cost_usd`（loop の包みの行を外し、本体の node だけを足した）。合計 $57.47。

- 設計の段: $11.23・約 40 分。世界の解 $0.11・独立設計 $0.17。書き手は周ごとに $1.48・$1.57・$1.28（1 周 約 4.5〜7 分）、審査役（形 `theme`）は $1.93・$2.86・$1.84（1 周 約 5.5〜8 分）。1 往復は書き手と審査で約 $3.2〜4.4。
- 降りた後: 試験の起点 $0.07・判定 $4.22・独立設計 $0.17・構造の目 $0.59・計画の往復 4 周 $40.43（計画の役 $11.57・事前審査 $28.86。事前審査の 1 周目は審査の木〔review-tree〕を回して $17.71）・報告 $0.77。
- 下書きの 2.3 の 6 の見込み（書き手 $2〜4・審査 約 $4・3 往復で約 $20、降りた後に約 $16）と比べると、設計の段は見込みの約半分、降りた後は約 3 倍。降りた後の差の多くは事前審査の 1 周目の審査の木で、設計の段の作りではなく計画の往復の今の費用。

### 13.2 設計の段の往復

- 書き手は 3 周とも、問い（`asks`）・選び肢・推し・代償で答えた。問いは 4→5→5（推しは 5 つとも付いた）、変える所（`changes`）は 6→9→16、部署の決め（`decided`。決まりで決まるので持ち主に聞かない決め）は 3→4→5、前提は 6→7→8（うち持ち主の決め 2）。
- 審査役（形 `theme`）の穴は 3 周で違う鍵 14（block 7・suggest 7）。1 周目 block 4・suggest 4 → 2 周目 block 2・suggest 2 → 3 周目 block 1（端）・suggest 1 で `settled`。
- 2 周目の審査役は 1 周目の 8 鍵を全部「消えた」と照らし、書き手の答えは fixed 8・disputed 0。3 周目も 2 周目の 4 鍵を消えたと照らした。前の周から残った穴（`persists`）は 0。
- 往復ごとの控え（`talk/theme-<k>.md`）と `gate-theme` の文に、問いごとの選び肢・推し・代償が出た。

### 13.3 下書きの 1.2（run 19268881）との比べ

- 答える形: 1.2 は修正案の形で 3 往復とも 3 項目、設計の問いは `approach` と `files` に押し込まれた。この run は設計の案の形で、問い 5 つを選び肢・推し・代償で答えた。
- 「形が設計の問いに合わない」穴: 1.2 は `design-gap-*` が 3 つ（1 つは 3 往復残った）。この run の設計の段・計画の往復の鍵（35）には `design-gap` の類の鍵が 0。
- 鍵の数: 1.2 は 3 往復で 20（中央 5・端 15）。この run は設計の段 14・計画の往復 35。計画の往復は承認された設計の 16 の変える所を判定の 6 単位に降ろした後の審査で、1.2 の 3 項目の修正案より広い。
- 止め: どちらも 3 往復目で収まった（1.2 は clean、この run の設計の段は settled）。計画の往復は 4 周目で clean。

### 13.4 下書きの 16 章の未確認への答え

1. 書き手の 1 往復の費用: 約 $1.3〜1.6・約 4.5〜7 分（13.1）。審査役を足した 1 往復は約 $3.2〜4.4。
2. 形 `theme` の審査役が往復の記録を受けて穴の消えを照らせるか: 照らせた。2 周目・3 周目とも、前の周の鍵ごとに消えたかを返し、書き手の fixed と食い違わなかった（13.2）。ただし残った穴（`persists`）が 0 の run だったので、「残った」と照らす側は確かめていない。

### 13.5 この run で見た事（直していない）

- 修正の段は `works:no-suite` で止まった（差分は空）。`tdd_suite` は対象の試験を走らせる実行器を渡す入力で、渡さないと工場は試験の元の結末を取れない。修正の段は単位を組にまとめて直し、計画は単位ごとに直し方の型の語（`route`。試験の要らない直しは `static`）を付ける。組に `static` でない単位が在り、元の結末が取れない時は、直し方の型（tdd・variant など）を 1 つも回さずに組を止め、止めの語 `no-suite` を名乗る（`docs/plans/2026-10-24-fix-weapons.md` の 3.9 の「止め方」の 1・`workflows/fix/src/orders.py` の `no_suite_why`）。この run の組はこれに当たったので、今の決まりのとおり。設計の段と降りる道の確かめは修正の段の前で済むので、回し直していない。修正の段まで通すには `tdd_suite` を渡す。
- `gate-start` の文が入口を「依頼 0 件」と書き、テーマに触れない。表示がいま壊れている。run の進み方は壊れていない（テーマは設計の段へ運ばれた）。
- `gate-theme` の文の「往復ごとの案と審査:」の見出しが括弧の中で空になり、往復の行は次の行から「- - 1 往復目」の形で続く。中身は欠けておらず、並べ方が崩れている。表示がいま壊れている。
- `theme-converge.json` の `round` が 1 のまま（`passes` は 3）。設計の往復の `theme-out` の `round` は 1・2・3 と数えられ、往復の上限の判定（`workflows/line/src/talk.py` の `_capped`）は `theme-out` の `round` を読むので、上限は効く。`lib/converge.py` は記録の `round` と block の `round` が同じことを求めるので、1 のままなのは形 `theme` の作りどおりかもしれない。欠陥かどうかは未確認。
- 3 周目の `resolved`（審査役が消えたと挙げた鍵の並び）は 8 鍵で、2 周目の 4 鍵（block 2・suggest 2）に加えて、2 周目で既に消えたと照らした 1 周目の 8 鍵のうち 4 つが重ねて入った（8 = 2 周目の 4 ＋ 1 周目の 4）。1 周目のどの 4 鍵かは、この記録に控えていない。記録の数がいま違っている。往復の止め時など進み方への響きは確かめていない。
- 計画の役は、承認で採った推しを「持ち主の Qn の答え」（Qn は設計の案の問い `asks` の id `Q<n>`）として扱った（下書きの 8 章の降りる道のとおり。降りる時に問いの答えを依頼の `answers` の行にして計画へ運ぶ）。
