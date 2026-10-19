# block の設計書: structure（構造の目）

- 何の話か: 直しの単位ごとに、直しが対象のリポジトリの構造を汚すか（設計の考えを知る場所を増やすか、書いた意図に反するか）を見る観点「構造の目」を、単独で呼べる block `blocks/structure/` にする設計。直す前（修正案の前に単位を見る）と直した後（差分を見る）の 2 つの時を `mode` で選ぶ。型は [README.md](README.md) に従い、形は [world.md](world.md) を写した。
- 決めたこと: 今の structure のサブグラフの node（`structure-measure`・loop の中の 3 つ・返す `structure`）と、eyes の `structure-after` の node を、6 つの node の block 1 つにする。比べる相手を、周りのコードでなく対象のリポジトリの書いた意図（根と、単位のファイルの上の各フォルダの `AGENTS.md`・`ARCHITECTURE.md`、人が run に固めた方針）にする（持ち主の 2026-10-19 の追加。README の 8.2・8.6）。汚れると見た行は、書いた意図の原文の抜き書きを付けさせ、機械が見せた本文に字のまま在るかを照らす。直した後の時も同じ役が差分を見る。指示は 1 本の英語の md（`prompts/structure-eye.md`）に書く。
- 持ち主に求めること: なし。この block を作る人（実装の役）は、この設計どおりに 1 本の PR（3 つの commit。7 節）で作る。自分で決めた事は 11 節に集めた（記録として置く。持ち主の確認は待たない）。

この文書の語は README の頭の物を使う（line・eyes〔独立の目のまとめの graph〕・graph・block・port・place・Archon・元の works・graphloops・keep-essence など）。ほかに:

- 工場と対象: 工場はこのリポジトリ（works-factory）の workflow。対象は工場が直すリポジトリ。構造の目が読む書いた意図は対象の物。例の run は工場が自分自身を対象にした run なので、名が重なる。
- 柵の表: 対象が自分で書いた表 `docs/concepts.json`（考えごとに、それを知ってよい所〔住処〕と、考えの語の字）。在れば、住処の外で語を書く行の数を機械が数えられる（`fence_up` はその数が直しで増えた所）。無い対象では数えない。
- `optional` の `bare`: line の collect が、落ちた node を記録の中で探す時に、include の id の頭（`<include の id>__`）を付けて探すか（false）、付けずに素の id で探すか（true。loop の中の node は記録に素の id で載る）。`node` が `-` で終わる物は頭の一致で読む。

- 単位: 判定が切った直しの単位 `{id, paths, summary}`（`summary` は判定の単位の理由）。
- 段 A: 直す前の実測。単位の `paths` を `lib/measure.py` で測り（行と伸び・変えた頻度・6 行の写しの塊・入口の数・環境変数の名）、考えの地図 `docs/concepts.md` の行と柵の表 `docs/concepts.json` の知る場所の数を足す（今の `lib/stage_a.py`・`lib/context.py`）。
- 段 B: 直した後の実測。直す前の版と今の作業ツリーの差分を測る（変わったファイル・住処の外の知る場所の増え `fence_up`・新しい名・増えた写しの塊。今の `lib/stage_b.py`）。
- 書いた意図: 対象のリポジトリが文で書いた憲法・決まり・設計（この block では、決まった名の文書 `AGENTS.md`・`ARCHITECTURE.md` と、port `intent` で渡された文書と、port `policy` の方針の文書）。
- 構造の目（structure-eye）: 道具を持たない AI の役。単位ごとに汚れるか汚れないかと、当たった形（6 つ）・根拠・避け方を返す。
- 設計の行: 構造の目の返答の 1 行（単位 1 つに 1 行）。`design.jsonl` に書く。形の読み口は `lib/structmark.py`（KEEP。plan・plan-review・eyes・line・report が読む）。
- 人に上げる行: `route` が「人に上げる」の行。line の修正前の承認ノードの項目になる。
- 例の run: 本物の run `df5e111f-ea97-409b-8066-2245d32746ab`（対象 raiki61/works-factory。置き場 `~/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/artifacts/runs/df5e111f-…/`）。直す前の目は `plan/structure/681f73b08c5a/`（この run の版では構造の目は plan の中に在った）、直した後の実測は `eyes/structure-after.json`。骨組みの値はここから取った。

## 1 block の全体

### 1.1 役

- before: 修正案より前に、判定が切った単位を測り、単位の直しが書いた意図に反するか・設計の考えを知る場所を増やすかを、道具を持たない別の目に判じさせる。汚れると見た単位には推しの避け方を書かせ、決め手を当たっても避け方が 1 つに決まらない単位だけを人に上げる行にさせる。
- after: 直した後の差分を測り（段 B）、同じ目に、差分が書いた意図に反するか・知る場所を増やしたかを判じさせる。修正案が構造の目の避け方から外れた訳（在れば）を並べて残す。PR の差分を単独で見る使い方（README の 8.6 の「入る時」）もこの mode。

どちらの時も、判じる基準は書いた意図で、周りのコードの今の書き方ではない（周りのコードが既に意図から崩れていれば、それを写す直しも汚れる）。書いた意図の文書が対象に 1 つも無い時だけ、今と同じく実測から知る場所の数で判じる。

### 1.2 port

入力（YAML の `inputs:`）:

- `mode`: `choice(before|after): before は直す前に単位を測って見る。after は base から今の作業ツリーまでの差分を測って見る`。既定 `before`。
- `units`: `json(units.schema.json): 直しの単位の配列 [{id, paths, summary}]。before では paths が空の単位は測らずに skipped に名指す。after では空の配列でよく、その時は差分の全体を 1 つの単位（id は diff）として見る`。既定 `[]`。
- `intent`: `json(intent.schema.json): 書いた意図の文書のパスの配列（作業ツリーの根からの相対）。空の配列なら決まった名で探す（3 節の intent）`。既定 `[]`。
- `policy`: `file: 人が run に固めた方針の文書（今の始めの記録の policy の写し）。空の字は、方針の文書が渡されていない`。既定 `""`。
- `base`: `text: after の時の直す前の版の commit。before では読まない`。既定 `""`。
- `plan`: `file: after の時の修正案の欄のファイル（plan-fields.json。欄 fields）。構造の目の避け方から外れた訳を読む。空の字は、修正案が渡されていない（外れの訳は空の並び）。before では読まない`。既定 `""`。
- `lang`: `text: 人に見せる欄（reason・chosen・chosen_reason・rejected・undecided_because）の言語。空は単位の summary の言語`。既定 `""`。

出力（`returns: finish`、`outcome_field: ok`）:

- `ok`: boolean。`status` が `ok` か。
- `status`: `ok` か `failed`。今の `structfile._outcome` の決め（実測が落ちた・目を起こす run なのに目の受け付けが済んでいない・3 回とも拒まれた・after で base が無い・段 B が落ちた）。
- `reason`: 日本語の 1 行（人に見せる）。
- `structure`: pointer（`structure-state.json`。`lib/structmark.py` の控えの形 `{status, reason, design_file, wall_s, skipped}`）か null（place に書けなかった）。どちらの mode も書く。
- `after`: pointer（`structure-after.json`。`structmark.write_after` の形 `{status, reason, after, deviations}`）か null（before）。
- `dirty`: 整数。汚れると見た行の数。`escalate`: 整数。人に上げる行の数。
- `optional`: `[{node, bare}]`。この block の中の node が落ちても line が先へ進めてよい宣言（今の `structure_collect.py` の返りのまま。11 節の 7）。
- `report`: 報告の節「構造の目」の日本語の行の配列（`structmark.report_lines` の行。8 節）。

今との違い: 今は始めの記録の pointer `start` から方針の写しを（`structure_measure.py:23-28`）、`$ARTIFACTS_DIR/structure/` を名で（`structure_collect.py`）、直した後は始めの記録の `base_rev` と修正案の pointer を eyes の node が読み（`structure_after.py:25-37`）、書いた意図は根の `ARCHITECTURE.md`・`AGENTS.md` だけを `HEAD` から読んで実測の JSON の `rules.maps` に貼っていた（`lib/context.py:36-51`）。直した後は目を起こさず機械の実測だけだった。

### 1.3 node の並び（`blocks/structure/works-factory-structure.yaml`）

1. `measure`（script `survey.py`。`mutates_checkout: false`）: port を読み、place を作り直し、書いた意図を探して読み、mode に応じて段 A か段 B を回し、目に見せる材料を `view.json` に書く。返り `{eye, reason}`（`eye` は構造の目を起こすか）。`output_format`: `{type: object, additionalProperties: false, required: [eye, reason], properties: {eye: {type: boolean}, reason: {type: string}}}`。
2. `structure-eye-loop`（`loop_group`、`max_iterations: 3`、`fresh_context: false`、`until_bash: 'done=$structure-eye-accept.output.done; test "$done" = true'`。`depends_on: [measure]`・`when: "$measure.output.eye == true"`）
   - `structure-eye-prep`（script `prep.py`。`mutates_checkout: false`）: 指示を組む。返り `{prompt, attempt}`。
   - `structure-eye`（AI。`prompt: "$structure-eye-prep.output.prompt"`・`depends_on: [structure-eye-prep]`・`model: '@wf-plan-structure'`・`allowed_tools: []`・`settingSources: [user]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`mutates_checkout: false`・`idle_timeout: 1728000000`・`retry: {max_attempts: 2, on_error: all}`。`output_format` は 2.4 の形）。
   - `structure-eye-accept`（script `take.py`。`depends_on: [structure-eye]`・`with: {reply: $structure-eye.output}`・`mutates_checkout: false`）: 返り `{ok, done, give_up, reason, attempt}`（今のまま）。
3. `finish`（script `finish.py`。`depends_on: [measure, structure-eye-loop]`・`trigger_rule: all_done`・`mutates_checkout: false`）: 控えを書き、出力を返す。落ちない（今の `structure_collect.py` のまま。境の口と lib の import から先の誤りは全部捕まえ、標準ライブラリだけで `status: failed` の控えを書く）。`output_format` は 1.2 の出力の欄を全部 required にし、`structure`・`after` は `{type: [object, "null"]}`、`dirty`・`escalate` は整数、`optional`・`report` は配列。

今の 4 つの node の id（`structure-measure`・`structure-eye-loop`・`structure`）のうち、`structure-measure` は `measure`、返す node `structure` は `finish` にした（block の名と同じ id の node を持たない。world と同じ）。script の名は `lib/` のモジュールと重ねない（lib に `measure.py`・`eye.py`・`stage_a.py`・`stage_b.py`・`context.py`・`accept.py`・`report.py` が在るので `survey.py`・`prep.py`・`take.py`・`finish.py`）。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、line から include された時は `$ARTIFACTS_DIR/<include の道>/`。before と after を line と eyes が別の include にするので place も分かれる）の下に書く。名は `src/files.py` だけが持つ（`AFTER_FILE` だけは読み手の口 `structmark.read_after` が持つ字 `structure-after.json` を引く）:

- `units.json`（paths の在る単位）・`skipped-units.json`（paths の空な単位の id）
- `intent.json`（見せた書いた意図 `[{path, rev, text, cut, reason}]`。3 節の intent）
- `structure.json`（before の段 A の実測。今のまま。ただし欄 `rules` は消え、書いた意図は `intent.json` に移る）
- `structure-after.json`（after の段 B。`structmark.write_after` の形）・`after.diff`（after の差分の全体）
- `view.json`（目に見せる JSON。根拠の JSON Pointer はこの中を指す）
- `design.jsonl`（設計の行。`measure` が 0 バイトで置き、受け付けが書く）
- `eye.json`（目の控え `{started_at, status, wall_s}`）・`rejects-structure-eye.json`
- `structure-eye-prompt-<n>.md`（組んだ指示。今の `eye-prompt-<n>.md`）
- `structure-state.json`（返す控え）

今の `structure-spare/`（place に書けない時の控えの置き場。place の外）は持たない（11 節の 6）。

### 1.5 コードの置き場

- `blocks/structure/src/files.py`: 1.4 の名・`OPTIONAL`（1.2 の `optional` の値: `[{"node": "measure", "bare": false}, {"node": "structure-eye-", "bare": false}, {"node": "structure-eye", "bare": true}, {"node": "structure-eye-", "bare": true}]`）・`NAME = "structure-eye"`（却下の控えの名）。
- `blocks/structure/src/intent.py`: 書いた意図を探して読む（3 節）。`TEXT_CAP = 6000`（今の `context.TEXT_CAP`）と切り方 `_cut` を持つ。
- `blocks/structure/src/stage_a.py`: 今の `lib/stage_a.py`（`read_units`・`measure_unit`）と `lib/context.py` の `find`・`concepts`・`_sections`・`_rel`・`HEADING` の写し（`context.rules` は `src/intent.py` に替わるので写さない）。`measure_unit` の `MEASURE` は `pathlib.Path(importlib.util.find_spec("measure").origin)`（`lib/measure.py` をコマンドとして起こす。import しない）。
- `blocks/structure/src/stage_b.py`: 今の `lib/stage_b.py` の写し（`MEASURE` は同じ探し方）。
- `blocks/structure/src/survey.py`: 今の `lib/structfile.py` の `_measured_units`・`_now`・`measure` を mode で 2 つに分けた物（`before(place, units, root, intent_docs)`・`after(place, units, root, base, plan_fields, intent_docs)`）と、目に見せる JSON を組む `view`（今の `eye.view`・`_cut`・`measured`・`due`）。
- `blocks/structure/src/eye.py`: 今の `lib/eye.py` の `prep`（指示の文の組み立て `render` は md に移り、材料の値だけを組む）・`_pointer`・`problems`（書いた意図の照らしを足す。7 節）・`accept`・`state`・`reset`・`_put`・`_load`・`ROUTES`・`ROUTE`・`ROUTE_UP`・`ROUTE_REASON`・`MIN_UNDECIDED = 20`・`VERDICTS`・`DIRTY`・`FORM_COUNT = 6`・`MIN_QUOTE = 20`。6 つの形の文（今の `FORMS`）は md に移す。
- `blocks/structure/src/state.py`: 今の `structfile._outcome`・`write_state`・`keep_state`（spare の道は消す）の写し。
- `blocks/structure/schemas/units.schema.json`（`{type: array, items: {type: object, required: [id], properties: {id: {type: string, minLength: 1}, paths: {type: array, items: {type: string, minLength: 1}}, summary: {type: string}}}}`）・`intent.schema.json`（`{type: array, items: {type: string, minLength: 1}}`）。
- 使う `lib/`: `measure`（コマンドとして）・`conceptfence`（`tables`・`places`・`changed`・`scan_change`）・`concepthome`（`tracked_names`・`pick_maps`・`base_of`・`TABLE_NAME`）・`design`（`MAP_NAMES` だけ。根の地図の文書の名）・`eye`（`stamp`・`wall`・`WALL`。ブロックの時間の欄。`structmark` も読む）・`structmark`（`write`・`read`・`rows`・`write_after`・`AFTER_FILE`・`report_lines`・`DIRTY`・`ROUTE_UP`）・`planmarks`（`deviations`）・`listcut`（`SHOWN`）・`rolekit`（`accept_round`・`current_round`・`round_outcome`・`rejected`・`rejects_text`・`rejects_path`）・`jsonfile`・`oneline`。
- `concepthome.EYE_ASK`・`AXIS` の文（構造の目の問い）は md に移す。`concepthome` の `AXIS` は R1・R3・plan・plan-review の文も使うので、lib の定数は組み込みまで消さない（README の 9.3 の「文は md へ」）。
- `lib/design-row.schema.json` は写さない。今は試験だけが読む（`tests/workflows/test_structure.py:116-131`・`lib/tests/test_structure_eye.py:158-161`。#232 `d91c4b49` から実行の時に読む物は無い）。行の型の正本は `structure-eye` の node の `output_format` と、受け付けが足す `route_reason`（11 節の 9）。
- 作り直しの間は `lib/structfile.py`・`lib/stage_a.py`・`lib/stage_b.py`・`lib/context.py` と `lib/eye.py` の目の部分を消さない（今の structure と eyes が使う）。組み込みで消す（README の 9.2）。

### 1.6 つなぎ方（graph の側。block には書かない）

- before: line が今の `structure` の所に `include: works-factory-structure` を置く。`when:` は今の `owed`（計画の 1 回目の周が修正案の役を起こす run）。`with:` は `mode: before`・`units: $judge.output.units`・`intent: "[]"`・`policy: <始めの記録の policy の写しのパス。今の policy.frozen_copy(start)>`・`lang`。
- before の読み手: plan（`structure`。案の頭の「構造の目の行」と、汚れる行への答えの照らし `planmarks.structure_gaps`）・plan-review（`structure`。写しと `boardview`）・案の直しと事前審査（同じ pointer。#560 のまま）・line の修正前の承認ノード（`structure` の人に上げる行。`gatemarks` の `design_items`）・report（`report`）。
- after: eyes のまとめ（`blocks/eyes/`）が今の `structure-after` の所に `include: works-factory-structure` を置く。`with:` は `mode: after`・`units: <判定の単位>`・`intent: "[]"`・`policy`（before と同じ）・`base: <始めの記録の base_rev>`・`plan: <修正案の欄の pointer>`・`lang`。
- after の読み手: r1・r3 の頭の直した後の実測の節（`after`。今の `eyeverdict.after_section` が `structmark.after_counts`・`deviation_lines` で読む）・最後の承認ノードと報告（`after`。`structmark.after_lines`・`after_rows`）・結末の残りの数え（`after`。`outcome.py:301-304`）・eyes のまとめの判定（`dirty`・`escalate`。汚れる行をまとめの判定でどう扱うかは eyes の設計書が決める）。
- 読み手は `after` の pointer の先のファイルの親のフォルダを `structmark.read_after` に渡す（`structmark` の口がフォルダを受ける形のため）。

## 2 node の設計シート: structure-eye（構造の目）

### 2.1 役

単位ごとに、直し（before は summary が述べる直し、after は差分がしたこと）が、対象の書いた意図に反するか・設計の考えを知る場所を増やすかを 1 つの問いで判じる。汚れると見た単位には推しの避け方を書き、決め手を当たっても避け方が 1 つに決まらない時だけ人に上げる行にする。道具を持たない。

### 2.2 port

`view.json`（← `measure` が port `units`・`base`・`plan` と段 A・段 B の実測から組んだ材料）・`intent.json`（← port `intent`・`policy` と決まった名の探し）・`after.diff`（← port `base`。after だけ）・前の回までの却下の理由（← `rejects-structure-eye.json`）・`lang`（← port `lang`）。

### 2.3 組み立ての順（`prompts/structure-eye.md`）

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: 却下の控えが空でない。`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "structure-eye"))`。
2. 役の定義（決まった文）と差し込み口 `{route_up}`。
3. `## Question` と判断の 1 軸（決まった文）。
4. `<!-- if intent -->` 書いた意図と比べる問い `<!-- end intent -->` と `<!-- if not intent -->` 実測で判じる問い（今の `EYE_ASK`）`<!-- end intent -->` — 条件: `intent.json` に本文の在る文書が 1 つ以上。
5. `<!-- if after -->` 直した後の時の段落 `<!-- end after -->` と `<!-- if not after -->` 直す前の時の段落 `<!-- end after -->` — 条件: port `mode` が `after`。
6. `## Forms (answer by number)` と 6 つの形（決まった文）。
7. `## How to answer`（決まった文）と差し込み口 `{dirty}`・`{clean}`（← `src/eye.py` の `VERDICTS`）・`{route_self}`・`{route_up}`（← `ROUTES`）・`{min_undecided}`・`{min_quote}`・`{shown}`（← `listcut.SHOWN`）・`{lang}`。中の `<!-- if intent -->`・`<!-- if not intent -->`・`<!-- if after -->` の段落。
8. `<!-- if intent -->` `## Written intent` と `{intent_docs}` ← `src/eye.py` が組む材料（文書ごとの見出し `### <path> (<rev>, lines 1-<n>)`、切った時の印の 1 行、本文）`<!-- end intent -->`。
9. `## Units and measurements` と `{view}` ← `view.json` の JSON（区切りの `,`・`:` だけの 1 行。今の `json.dumps(…, separators=(",", ":"))`）。
10. `<!-- if after -->` `## Diff` と `{diff}` `<!-- end after -->` — `{diff}` ← `after.diff` の先頭 `DIFF_CAP`（40000 バイト。11 節の 4）。切った時は値の末尾に `(cut: …)` の 1 行が入る（3 節の `prep.py`）。
11. 結びの 1 文（決まった文）。

md の本文（英語。この block の PR の 3 つ目の commit でこのまま置く。7 節の指示の比べ）:

````markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

You are the structure eye, started in a new conversation. Your job is to judge, for each unit of change below, whether the change dirties the structure of the target: whether it goes against what the target's written intent says, or makes more places know a design concept. Only for a unit you see as dirty, when the deciding sources (the target's written intent and the policy, the person's earlier decisions, the same situation elsewhere in the target, and practitioners' practice — whichever this prompt carries) still do not settle how to avoid it, make its row a question for a person. "Do not settle" means the ways to avoid it split and cannot be narrowed to one. Such a row has `route` set to `{route_up}`; how to write it is under How to answer.
You have no tools. You cannot open files or the repository; this prompt is everything you are given.

## Question

One axis of judgment: does the whole become simpler while the purpose is met and the protecting mechanisms keep working? Simplicity is measured not by the number of lines but by the number of places that know a design concept.

<!-- if intent -->
Judge each unit by one question: after this change, does the target go against what its written intent says, or know a design concept (a word, a field name, a value, or a decision rule) in more places than before? The written intent is the target's own constitution, rules, and design documents, and the policy for this run, shown under "Written intent" below. Judge against what is written there, not against how the surrounding code happens to look today: the surrounding code may already have drifted from the written intent, and a change that copies the drift is still dirty. Where the written intent names the home of a concept (the one place that holds it), a change that writes the concept outside its home is dirty. Where it names no home, write in `chosen` the form that gathers the concept into a place that already knows it. Where the measurements carry concept-map rows and known-place counts, take them as given. Use the other measurements (copied blocks, entry points, places where names appear) as evidence of where a concept is known. If nothing goes against the written intent and the number of places does not grow, the unit is clean. Use the form numbers to name which form the growth takes (form 2 only when the same concept is written in a second place).
<!-- end intent -->
<!-- if not intent -->
The target has no written intent documents: none was found under the fixed names, and none was given. Judge each unit by one question: after this change, does the target know a design concept (a word, a field name, a value, or a decision rule) in more places than before? Where the measurements carry concept-map rows and known-place counts, take them as given (a change that writes a concept that has a home outside its home is dirty; for a concept with no home, write in `chosen` the form that gathers it into a place that already knows it). Otherwise judge from the measurements (copied blocks, entry points, places where names appear). If the number of places does not grow, the unit is clean. Use the form numbers to name which form the growth takes (form 2 only when the same concept is written in a second place).
<!-- end intent -->

<!-- if after -->
The change is already made. Below are the diff from the version before the change to the current working tree, and what the machine measured on it (`after`: the changed files, the growth of places that know a concept outside its home `fence_up`, new names, and added copied blocks). Each unit names the files of one fix; judge what the diff did in those files. A unit with the id `diff` stands for the whole diff.
<!-- end after -->
<!-- if not after -->
Each unit below is a fix that is planned but not yet made: its `summary` says what the fix will change and why, and `paths` names the files. Judge the fix the summary describes.
<!-- end after -->

## Forms (answer by number)

1. Rewrites a shared thing per run or per caller
2. Splits one responsibility across two places
3. Bends an existing mechanism from the side
4. Crosses the boundary of a component (such as a module, block, or subgraph) and assumes the inside of another component
5. Adds a new name or entry point with no framework to hold it
6. Takes in the circumstances of an outside tool by naming it

## How to answer

- One row for every unit below (do not let a unit you see as clean pass in silence). Copy the unit's id into `unit_id` as it is.
- `verdict` is `{dirty}` or `{clean}`. `faces` are the numbers of the forms that apply (one or more if dirty).
- `evidence` is one or more JSON Pointers (RFC 6901, for example /units/0/summary) into the JSON under "Units and measurements", naming the fields you rest on. Do not point to a field that does not exist or is null.
- `reason` is the reason. For a unit you see as dirty, also write `chosen` (the way to avoid it you recommend) and `chosen_reason` (why you recommend it).
<!-- if intent -->
- For a unit you see as dirty, put in `intent` at least one written rule it goes against, or the written home it ignores: `path` is the path of a document under "Written intent", and `quote` is at least {min_quote} characters copied word for word from that document as shown. The machine checks each quote against the shown text and rejects the answer if it is not there. Pick a passage that has no dollar sign in it: the runner may rewrite words that follow a dollar sign in this prompt, so such a passage may not match the machine's copy. For a clean unit, `intent` may name the rules you checked.
<!-- end intent -->
<!-- if not intent -->
- Leave `intent` empty: no written intent was shown.
<!-- end intent -->
- If the unit's summary names practitioners' practice, make `chosen` of a dirty unit follow that practice, or write in `chosen_reason` why it does not.
- `route` is `{route_self}` (the default; you need not write it) or `{route_up}`. Use `{route_up}` only for a unit you see as dirty when the deciding sources (the written intent and the policy, the person's earlier decisions, the same situation in the target, practitioners' practice) still do not settle one way to avoid it. Then write your recommendation in `chosen`, at least one rejected option and its cost in `rejected`, and in `undecided_because` why it does not settle (at least {min_undecided} characters: what split against what).
- A unit's `concepts.rows` are the concept-map rows that apply to the unit's files; `concepts.places` counts the lines in the unit's files that carry a concept's word (`home` says whether the file is the home or a place allowed to know it; `known_places` is the number of places that know the concept).
- `duplicates` carries only the first {shown} entries. If `duplicates_total` is present, it is the full count.
<!-- if after -->
- `after.deviations` are the reasons the fix plan gave for not following an earlier eye's way to avoid. Read them as the plan's claims, not as facts.
<!-- end after -->
- Write `reason`, `chosen`, `chosen_reason`, `rejected[].option`, `rejected[].cost`, and `undecided_because` in {lang}. Keep keys, enum values (`verdict`, `route`), identifiers, paths, JSON Pointers, and quotes as they are.

<!-- if intent -->
## Written intent

The machine took these from the target (the version named in each heading). They are all the written intent you are given. They are listed from the repository root down; where two documents disagree, the one nearer to the unit's files (listed later) wins, and the policy for this run, when present, is listed last.

{intent_docs}
<!-- end intent -->

## Units and measurements

The machine took these from the measurements. They are all you are given.

```json
{view}
```

<!-- if after -->
## Diff

{diff}
<!-- end after -->

Return only JSON that matches the output schema.
````

（外の区切りの 4 つの ``` は設計書の code block の字で、md のファイルには入れない。）`{view}` に入る JSON の中の `{"units":…}` は差し込み口の形に合わないので字のまま残る（`prompt.py` は差し込む値の中を置き換えない。置き換えは md の字にだけ当たる）。

### 2.4 返す形

今の `output_format` に欄 `intent` を 1 つ足した物: `rows: [{unit_id (空白でない字), verdict (汚れる|汚れない), faces (1〜6 の整数の配列), evidence (字の配列), reason (空白でない字), chosen?, rejected?: [{option, cost}], chosen_reason?, route? (自分で決める|人に上げる), undecided_because?, intent?: [{path (1 字以上), quote (1 字以上)}]}]`（`rows` は required。行の required は `unit_id`・`verdict`・`faces`・`evidence`・`reason`。`additionalProperties: false`）。`verdict` と `route` の語は日本語のまま（読み手 `structmark`・`gatemarks`・plan の受け付けが同じ字を持つ。語を英語にするのは行の形の変更で、この作り直しの外）。人に見せる欄は `reason`・`chosen`・`chosen_reason`・`rejected[].option`・`rejected[].cost`・`undecided_because`（修正案の頭・承認ノード・報告に載る）で、言語は `{lang}`。

### 2.5 描いた骨組み（例の run の値）

before（例の run の `plan/structure/681f73b08c5a/eye-prompt-1.md` と同じ値。この run は 1 回目で通った）:

````markdown
You are the structure eye, started in a new conversation. …（決まった文。{route_up} は 人に上げる）

## Question

One axis of judgment: …

Judge each unit by one question: after this change, does the target go against what its written intent says, … under "Written intent" below. …

Each unit below is a fix that is planned but not yet made: …

## Forms (answer by number)

1. Rewrites a shared thing per run or per caller
…（6 つ）

## How to answer

- One row for every unit below …
- `verdict` is `汚れる` or `汚れない`. …
- For a unit you see as dirty, put in `intent` … at least 20 characters …
- `route` is `自分で決める` (the default; …) or `人に上げる`. … (at least 20 characters: …)
- `duplicates` carries only the first 5 entries. …
- Write `reason`, … in the language of the units' summaries. …

## Written intent

The machine took these from the target (…). They are all the written intent you are given. …

### AGENTS.md (4428f368d229, lines 1-153)

(cut: the first 6000 characters are shown; 14421 more were left out)

<!-- coldwrite:skip AI 向けの決まりの正本。… -->
# AGENTS.md（works-factory の AI 向けの決まり）
…

### workflows/AGENTS.md (4428f368d229, lines 1-…)

(cut: …)

…

## Units and measurements

The machine took these from the measurements. They are all you are given.

```json
{"units":[{"id":"workflows/merge/scripts/pr_commit.py hook_env: commit のフックの環境が、…","summary":"事実（実測）: workflows/merge/scripts/pr_commit.py:73-76 の hook_env は …","measure":{"env":{…},"paths":[{"duplicates":[…5 件…],"duplicates_total":…}],…},"concepts":{"rows":[],"places":[]}}],"timing":{"started_at":"2026-10-18T18:37:07+00:00","finished_at":"2026-10-18T18:37:09+00:00","wall_s":1.905}}
```

Return only JSON that matches the output schema.
````

例の run の目は書いた意図の節を見ていない（今の形では根の `AGENTS.md` が実測の JSON の `rules.maps` に 6000 字で入っていた）。上の骨組みの「Written intent」は、新しい探し方（3 節）を例の run の版 `4428f368` に当てた時に入る物で、単位のパス `workflows/merge/scripts/pr_commit.py` の上のフォルダの `workflows/AGENTS.md` が足される。`policy` は空（この run は方針の文書を固めていない）。

after（例の run の `eyes/structure-after.json` の値。この run では目は起きていない。新しい node の骨組み）:

````markdown
…（役の定義・Question・intent の段落は before と同じ）

The change is already made. Below are the diff from the version before the change to the current working tree, …

…（Forms・How to answer。after.deviations の箇条が入る）

## Written intent

### AGENTS.md (4428f368d229, lines 1-153)
…
### bin/AGENTS.md (4428f368d229, …)
…
### lib/AGENTS.md (…)
…
### tests/AGENTS.md (…)
…
### workflows/AGENTS.md (…)
…

## Units and measurements

```json
{"units":[{"id":"workflows/merge/scripts/pr_commit.py hook_env: …","summary":"…","paths":["workflows/merge/scripts/pr_commit.py"]}],"after":{"base_rev":"4428f368d229f2d4f4343122c620c3fdeb334184","changed":["bin/AGENTS.md","bin/_lib/launcher.py","docs/design.md","lib/tree_run.py","lib/userenv.py",…14 本…],"tables":["docs/concepts.json"],"tables_changed":[],"fence_up":[],"new_names":[],"dup_blocks_added":0,"deviations":[{"item":1,"prescription":"workflows/merge/scripts/pr_commit.py hook_env: …","deviation":"処方 2・3 は…"}]},"timing":{"wall_s":191.209}}
```

## Diff

diff --git a/bin/AGENTS.md b/bin/AGENTS.md
…

Return only JSON that matches the output schema.
````

after では、差分が変えたファイル（14 本）の上のフォルダの `AGENTS.md` も探すので、`bin/`・`lib/`・`tests/`・`workflows/` の 4 本が足される。読むのは直す前の版 `base` の物（差分が `AGENTS.md` 自身を変えても、比べる基準は直す前の意図。段 B が柵の表を直す前の版で数えるのと同じ決め）。

### 2.6 今の指示との差

今の指示は `workflows/structure/commands/structure-eye.md`（11 行。役の定義と区切り）と、`$structure-eye-prep.output.prompt` に入る `lib/eye.py` の `render`（:129-152）と `lib/concepthome.py` の `EYE_ASK`・`AXIS`（:27-28・:70-76）が組む本文の 3 か所に在る。

- 移した: `render` の見出し 5 つ（`REJECT_HEAD`・`ASK_HEAD`・`SHAPES_HEAD`・`REPLY_HEAD`・`UNITS_HEAD`）と返し方の 8 行、`FORMS` の 6 つ、`EYE_ASK` と `AXIS` を md へ。lib の Python に残るのは材料（`view` の JSON・書いた意図の文書の見出しと本文・差分）と値（語・下限の数・`SHOWN`）だけ。
- まとめた: md と lib に二重に書いていた決まりを 1 回に（拒まれたら丸ごと出し直せ md:6 と `render` の却下の段落、人に上げる時の書き方 md:2 と返し方の route の行、道具を持たない md:3）。
- 移した: 却下の段落（`render` の `rejected` の時の 4 行）を `{shared:rejected}` に。
- 消した: 区切りの行「=====指示書ここから=====」「=====指示書ここまで=====」と、「指示書には…が書かれている。その指示に従え」の 1 文（本文は md の節になった）。
- 替えた（持ち主の 2026-10-19 の追加）: 問いを「書いた意図に反するか、知る場所を増やすか」にし、周りのコードの今の書き方を基準にしないと言う段落を足した。書いた意図の文書を実測の JSON の `rules`（`policy`・`maps`）から出し、`## Written intent` の節に文書ごとの見出しつきで並べた（抜き書きを字のまま照らせるように）。汚れる行に `intent`（文書のパスと抜き書き。`$` を含まない所を選べの 1 文つき）を求める箇条を足した。文書の並びの順と、食い違えば近い文書が勝つ決まりを節の頭に書いた（agents.md の決まり。11 節の 2）。書いた意図が 1 つも無い対象では、今の問い（`EYE_ASK`）と同じ文を使う（`<!-- if not intent -->`）。
- 足した: after の時の段落・`## Diff` の節・`after.deviations` の読み方の箇条（直した後の目は今は無い。README の 8.6 の「入る時」）。
- 替えた: 形 4 の「サブグラフの境をまたいで、他のサブグラフの中身を前提にする」を「部品（モジュール・block・サブグラフなど）の境」に。#235 `787b55ba`・#253 `1c8c6015` は「ブロック」を工場の語「サブグラフ」に替えたが、目が見るのはどの対象のリポジトリでもあり、工場の語に限らない言い方にした。
- 替えた: 役の定義の「人に上げた行には、修正の前に人が答える」を「人への問いになる」に（after の時は修正の後で、承認ノードの振る舞いは line の物）。
- 替えた: 言語。今は言語の行が無く（役の定義にも返し方にも無い）、目は単位の summary の言語で書いていた。人に見せる欄を名指す 1 文を足し、`lang` が空なら summary の言語（README の 5.3 の既定と同じ意味）。
- 英語にした（#764）。役の名「構造の目」は "the structure eye"。

## 3 script の node

- `survey.py`（`measure`）: `INPUTS_MODE`・`INPUTS_UNITS`・`INPUTS_INTENT`・`INPUTS_POLICY`・`INPUTS_BASE`・`INPUTS_PLAN` を `os.environ.get("INPUTS_MODE")` などの字のままで読み、`ports` に渡す。place を作り直す（中を全部消す）。根は作業ツリー（`Path.cwd()`）。
  - intent（`src/intent.py` の `find(root, rev, paths, given, policy)`。返りは `[{path, rev, text, cut, reason}]` で `intent.json` に書く）:
    - 読む版 `rev`: before は `HEAD`、after は port `base`。
    - port `intent` が空でなければ、その各パス。空なら、`design.MAP_NAMES`（`ARCHITECTURE.md`・`AGENTS.md`）の根の物と、単位の `paths`（after では単位の `paths` と段 B の `changed` の和）の各ファイルの上の各フォルダ（根を除く。浅い順・名の順）に在る同じ名の物のうち、`rev` に追跡されている物（`git ls-tree -r --name-only <rev>`）。
    - 本文は `git show <rev>:<path>`。`rev` に無い・読めないパスで port `intent` が名指した物は作業ツリーのファイルを読み、それも読めなければ `text` を空にして `reason` に 1 文（目には「読めなかった」と見出しだけ見せる）。決まった名の探しで見つけた物は追跡されている物だけなので落ちない。
    - port `policy` が空でなければ、その本文を最後の 1 本として足す（`path` は渡された値、`rev` は `"policy"`）。
    - 本文は `TEXT_CAP`（6000 字）で切り、`cut` に切った字の数。
  - before: 今の `structfile.measure` と同じ（`units.json`・`skipped-units.json`・`structure.json` を書き、`design.jsonl` を 0 バイトで置き直し、目の控えを消す）。`structure.json` の欄 `rules` は書かない。`view.json` は今の `eye.view` の中身から `rules` を外した物（`{units: [{id, summary, measure, concepts?}], timing}`）。返り `eye` は今の `eye.due`（`structure.json` が ok で、測れた単位が 1 つ以上）。
  - after: `src/stage_b.run(root, base, skip_prefix=<実行基盤の写しのパスの頭>)`（今の `boundary.RUNTIME_COPY_PREFIX`。土台の `ports.py` の同じ値）を回し、`eye.stamp` で秒を残す。`plan` が空でなければ `planmarks.deviations(<fields>)`。`structmark.write_after(place, status, reason, after, deviations)` で `structure-after.json` を書く（今の `structure_after.py` と同じ中身）。差分の全体を `stage_b.patch_of` で `after.diff` に書く。単位は port `units` の paths の在る物、空なら `[{id: "diff", summary: "", paths: <changed>}]`。`view.json` は `{units: [{id, summary, paths}], after: {base_rev, changed, tables, tables_changed, fence_up, new_names, dup_blocks_added, deviations}, timing}`（`fence_up`・`new_names` は `listcut.SHOWN` 件で切り、全件の数を隣の `<名>_total` に置く。今の `eye._cut` と同じ形）。返り `eye` は段 B の `status` が ok で `changed` が空でない時。
  - 中の誤りは `structure.json`（before）か `structure-after.json`（after）の `status: failed` と `reason` に残し、`eye: false` を返す（落ちない）。
- `prep.py`: 却下の控えと回の数え（`rolekit.rejected`・`len + 1`）を読み、`prompt.render("structure-eye", values, when)` で組む。`values` は 2.3 の差し込み口と、`intent_docs`（`intent.json` の本文の在る文書ごとに `### <path> (<rev の頭 12 字>, lines 1-<行の数>)`・切った時は `(cut: the first <TEXT_CAP> characters are shown; <cut> more were left out)` の 1 行・本文。読めなかった文書は `### <path> (could not be read: <reason>)`。文書の間は空行 1 つ）・`view`（`view.json` を `separators=(",", ":")`・`ensure_ascii=False` で 1 行に）・`diff`（after。`after.diff` の先頭 `DIFF_CAP` バイトを UTF-8 で読み〔読めない字は置き換え〕、切った時は末尾に `(cut: the first <DIFF_CAP> bytes are shown; <n> more were left out)`）・`lang`（空なら README の 5.3 の既定の英文の、単位の summary の言語を言う形）。`when` は `{"rejected": …, "intent": <本文の在る文書が 1 つ以上>, "after": <mode が after>}`。目の控え `eye.json` を `pending` にする（今の `eye.prep` と同じ）。返り `{prompt, attempt}`（今の `prompt_file` の欄は無くす。組んだ指示は place の `structure-eye-prompt-<n>.md`）。
- `take.py`: 今の `eye.accept` と同じ（`rolekit.current_round`・`accept_round`・`round_outcome`。控えが読めなければ落ちずに done・give_up の拒否）。照らしは 7 節。通れば `design.jsonl` に行を書く（`route` の既定と `route_reason` を足す。今のまま）。
- `finish.py`: `src/state.write_state(place, mode)` で `structure-state.json` を書き（今の `_outcome` の決め。after では段 B の `status` が failed なら `failed`）、`dirty`・`escalate` を `design.jsonl` から数え、`report` を `structmark.report_lines(<state>, <after なら place>)` で組んで返す。書けなければ（`OSError`）`structure: null`・`status: failed`・`reason` に「構造の控えを書けない（<文>）」。境の口と lib の import から先の誤りは全部捕まえ、標準ライブラリだけで `status: failed` と 0 バイトの `design.jsonl` を書いて返す（今の `structure_collect.failed`）。`optional` はどの返りにも `src/files.py` の `OPTIONAL`。

## 4 受け付け（structure-eye）

- 今の `eye.problems` の照らし（単位と 1 対 1・同じ単位の 2 行目・汚れる行に形の番号・`evidence` が 1 つ以上で `view.json` の中の null でない欄を指す・`reason` が空でない・汚れる行に `chosen` と `chosen_reason`・人に上げる行は汚れる行だけで `undecided_because` が 20 字以上と `rejected` が 1 つ以上・ほかの行に `undecided_because` が無い・行の無い単位）は全部そのまま。after では「実測した単位」は `view.json` の `units` の id。
- 足す（書いた意図の照らし）:
  - `intent.json` に本文の在る文書が 1 つ以上の時: 汚れる行は `intent` を 1 つ以上持つ。どの行の `intent` も、`path` が本文の在る文書のどれか（policy は渡された値の字）で、`quote` が `MIN_QUOTE`（20）字以上で、空白の並びを空白 1 つにして前後を落とした `quote` が、同じようにした見せた本文（切った後の物）に字のまま在る。外れは「行 <i>（<unit_id>）: intent の <path> の抜き書きが、見せた本文に字のまま無い（頭: <40 字>）」など、どれに落ちたかを名指す。
  - 本文の在る文書が無い時: `intent` を持つ行を拒む（「書いた意図の文書は見せていない」）。
- 却下の理由の文は Python（`src/eye.py` の `problems`）が組む日本語のまま（README の 5.3）。
- 3 回目の却下で loop を抜ける（`rolekit.GIVE_UP_AFTER`）。`finish` が `status: failed` と「構造の目の返答が 3 回とも受け付けで拒まれた: <最後の理由>」を返す。線は止めない（修正案は構造の目の行なしで進む。今のまま）。

## 5 単独で呼ぶ

```sh
# 直す前: 単位を見る
bin/works-factory <読ませるフォルダを blocks/ にする引数（名は実装で決める）> workflow run works-factory-structure \
  --cwd <対象> --input units='[{"id":"u1","paths":["lib/a.py"],"summary":"…直す事…"}]'

# 直した後（PR の差分を書いた意図と比べる）: 作業ツリーを PR の枝にして
bin/works-factory <同じ引数> workflow run works-factory-structure \
  --cwd <対象> --input mode=after --input base=<PR の base の commit>
```

`intent` を渡せば、その文書だけと比べる。出力は `workflow get <run>` の `finish` の返り。始めの記録は要らない。殻の引数の名は（未確認）（world の 7 節と同じ）。

## 6 元の works と graphloops の同じ場面

元の works の `works/blk-structure/`（stage-a・stage-b・structure-eye-loop・collect。入力 `units`・`root`・`policy_path`・`base_rev`。line が「structuring」と「measuring-after」の 2 か所で include した）から、工場は目の文・6 つの形・受け付けを同じに写した。graphloops には構造の目も実測も考えの住処も無い（近いのは `p2.fix_plan.md:22-27` の `adds[].canonical`、`p2.plan_review.md:17-25` の copy・contract_drift の見方、`r3.coherence.md` の直した後の周りのコードとの整合。どれも道具を持つ役が周りのコードを読む）。工場に無い物・違う物と、その訳:

1. 1 つの block を 2 回 include する形（元の works は直す前と直した後の両方を 1 つの block で持った）: 工場は段 B を eyes の node `structure-after` に移した（`docs/plans/2026-10-12-blocks/plan.md:17`・`eyes.md:28,49`、#67 `bd5c8d89`）。この block で元の形（`mode` で 2 つの時を持つ）に戻す（README の 1.3 の形の直し 7）。
2. どの line からも include できる入力（`root`・`policy_path`・`base_rev`）: 工場は始めの記録の pointer `start` 1 つに替えた（#75 `26d6f2b0`、方針の写しは #84 `47c71757`・#163 `e9d6bc19`）。（未確認）: 「どの line からも include できる」を失うことを比べた文書は無い。この block は port（`policy`・`base`）に戻す。根は作業ツリー（Archon の cwd）で port にしない（README の 4.2）。
3. 出口の 3 つのファイル: 工場は控え 1 つの pointer にした（#75、#560 `ca19ba37`・#750）。この block は控え（`structure`）と直した後の控え（`after`）の 2 つ。
4. plan の中から外へ（工場の #560 `ca19ba37`・merge `13d0d0f9`〔#750〕。後の直し `ac7af0ad`・`a59844c9`・`c4ca79a8`・`b6dabb43`・`259c2889`）: この block も line が run に 1 回 include する（`owed` の when）。
5. 実行の時に行の型 `design-row.schema.json` を読む受け付け（元の works は知らない鍵・語・形の番号の範囲・route の語を型で照らした）: 工場は node の `output_format` に任せ、二重の型の照らしを外した（#232 `d91c4b49`）。この block も同じで、型のファイルは写さない（1.5）。
6. 回の数えの置き場（元の works は `eye.json`）: 工場は `rolekit` の却下の控え（resume を跨いで数える。#232）。この block も同じ。
7. 目を Git の外で起こす旗（元の works の `'works-node: structure-eye isolated'`。adapter が一時のフォルダで起こし、git status と対象の案内の文書が目に届かない。`.shared/core/adapter.py:70-71,283-290`）: 工場の目は旗も `systemPrompt` の替えも持たず、既定の system prompt に作業ツリーの cwd と git status が入る（r2 の 2 つの役は `systemPrompt` で替えている。`tests/workflows/test_eyes.py:556`）。（未確認）: 外した記録は無い（`docs/plans/2026-10-13-capabilities/plan.md:552-557` の P076 は旗に触れない）。この block は今のまま足さない（11 節の 8）。
8. 控えを書く前に設計の行が読めるかの確かめ（元の `line_edge.structure_edge`）: 工場の `write_state` は確かめない（読み手の `structmark._state_rows` が読めない行を落ちとして扱う）。（未確認）: 意図の記録は無い。この block は `take.py` が書いた行を書いた直後に `structmark.rows` で読み直し、読めなければ `status: failed` にする（11 節の 10）。
9. モデル（元の works は opus・high を直に）: 工場は群 `@wf-plan-structure`（#628・#658 `d0b086a2`）。retry（#476 `8bb804fd`）。この block も同じ。
10. 元の設計書（`docs/specs/2026-09-29-structure-block-design.md`）の block の中の設計の承認ノード（3 つの答え・全部の案を捨てた時の loop）と前例を探す役: 元の works にも工場にも無い（元の `eye.py:8` が「このブロックは関所を持たない」、設計書の 5 行目が blk-world に替えたと書く）。この block も持たない（人に上げる行は line の修正前の承認ノードが聞く）。
11. 比べる相手: 元の works の目も、見たのは書いた意図（方針の文書・根の `ARCHITECTURE.md`・`AGENTS.md`・考えの地図と柵の表）と機械の実測だけで、周りのコードを道具で読んだことは無い。ただし、根の地図は `rules.maps` に実測と並べて貼るだけで、問いは「知る場所が増えるか」で、書いた意図に反するかは問わず、抜き書きも求めなかった。この block で、書いた意図を基準にし、単位のファイルの上のフォルダの `AGENTS.md` まで探し、汚れる行に抜き書きを求めて照らす（持ち主の 2026-10-19 の追加）。

この block が両方より良く、残す物: paths の空な単位を名指して修正案に渡す（#75・#560）・読めない入力を `unread` に残す（#560）・返す node が落ちない（#560）・resume を跨ぐ回の数え（#232）・一過性の誤りの retry（#476）・修正案の頭で汚れる行と汚れない行を分ける（#566・#577）・長い一覧を切って名と件数と pointer を残す（#656・#717）・R1・R3 の頭に修正案の外れの訳と事前審査の受け入れを載せる（#353 `0440b970`）・事前審査が控えと行を自分の置き場に写す（#73）。新しく足す物: 書いた意図の抜き書きの機械の照らし（world の抜き書きの照らしと同じ形）・直した後の差分を目が見る。

## 7 試験

- standalone の fixture（`blocks/structure/fixtures/`）:
  - `standalone.stubs.yaml`: 入力は `units`（JSON の字 1 行）だけ。今の `measured.stubs.yaml` を写し（`measure` を `{eye: true, reason: ""}`、`structure-eye-prep` を `{prompt: "stub", attempt: 1}`、`structure-eye` を 1 行、`structure-eye-accept` を通す、`finish` を ok の返り）、`reached: [measure, structure-eye, structure-eye-accept, finish]`。
  - `eye-gave-up.stubs.yaml`・`eye-skipped.stubs.yaml`: 今の同じ名の筋書きを新しい node の id で写す。
  - `after.stubs.yaml`: 入力 `mode: after`・`base: <40 字の字>`。`measure` が `{eye: true}`、`finish` の返りに `after` の pointer、`reached` に `structure-eye-accept`。
- `tests/blocks/structure/test_structure.py`: script を子のプロセスで回す。始めの記録の無い使い捨ての `ARTIFACTS_DIR` と git のリポジトリ（根の `AGENTS.md` と、`pkg/AGENTS.md` と、`pkg/a.py` を commit した物）で、port の値だけを渡し:
  - before: `survey`（`mode: before`・単位 1 つ `pkg/a.py`）→ `intent.json` に `AGENTS.md` と `pkg/AGENTS.md` が浅い順で在る → `prep` の指示に `## Written intent` と両方の見出しが在る → 台本の返答（汚れる行・`intent` に `pkg/AGENTS.md` の本文の 20 字以上の抜き書き）→ `take` が通す → `finish` の `dirty: 1`・`structure` の pointer・`report` の行。
  - 抜き書きが本文に無い返答 → `take` が拒み、理由が文書のパスを名指す。汚れる行に `intent` が無い返答 → 拒む。
  - 書いた意図の文書が無いリポジトリ → 指示に `## Written intent` が無く、`intent` を持つ行を拒む。
  - after: 2 つ目の commit を作らずに作業ツリーで `pkg/a.py` を変え、`survey`（`mode: after`・`base` は HEAD）→ `structure-after.json` の `after.changed` に `pkg/a.py`・`after.diff` が在る → 指示に `## Diff` と単位 `diff` が在る → 台本 → `finish` の `after` の pointer。`AGENTS.md` を作業ツリーで書き換えても、指示に入るのは `base` の本文。
  - `base` が空の after → `eye: false`・`status: failed`。
  - `intent` を渡した時は、決まった名を探さずにその文書だけ。
- 指示の比べ（README の 11.4。この block は 3 つの commit に分ける。11 節の 3）:
  1. 1 つ目の commit: md を今の字のまま日本語で置き（`structure-eye.md` の役の定義と区切りと `render` の本文。before で、書いた意図を `rules` の JSON に入れる今の形）、例の run の `plan/structure/681f73b08c5a/structure.json` と同じ値で組んだ指示が、今の `eye-prompt-1.md` を区切りの行と役の定義で包んだ字と同じになることを照らす。
  2. 2 つ目の commit: 英語にする（2.6 の「移した」「まとめた」「消した」「言語」の差だけ）。並べて審査に出す。
  3. 3 つ目の commit: 書いた意図の節・`intent` の欄と照らし・after の目（2.6 の「替えた（持ち主の 2026-10-19 の追加）」「足した」「形 4」「役の定義」の差）。並べて審査に出す。
- 振る舞いの試験（今の試験から写す。`structure/` のパスを place に、`start` の pointer を port に替える）:
  - `tests/workflows/test_structure.py` の `EyeTypeCase`（3 本）・`StageACase`（`test_measures_units_and_writes_empty_design_rows`・`test_measure_failure_and_unreadable_units_do_not_stop`・`test_unit_without_paths_is_skipped_and_named`・`test_eye_sees_concept_rows_and_policy`〔policy は port から〕・`test_fresh_measure_drops_old_eye_state`・`test_concept_rows_only_for_unit_paths`・`test_no_map_no_table_measures_only`・`test_measure_records_timing`）・`CollectCase`（`test_clean_eye_gives_ok_state`・`test_route_up_row_reaches_the_state`・`test_eye_without_rows_leaves_failed_state`・`test_failed_measure_node_still_returns_a_failed_state`・`test_return_survives_a_lib_that_does_not_load`・`test_return_echoes_the_declared_optional`）・`ShapeCase` のうち `test_eye_is_a_toolless_isolated_role`・`test_eye_loop_gives_up_in_the_body_before_max_iterations`・`test_scripts_are_read_only_uv_scripts`・`test_script_names_differ_from_lib_modules`。
  - `lib/tests/test_structure_eye.py` の全部（`test_six_forms_match_the_design_doc` は md の 6 つの形と `FORM_COUNT` の照らしに、`test_prompt_*` は組んだ指示への照らしに替える）。
  - `lib/tests/test_structfile.py` の `StateCase`・`MeasureCase`・`KeepStateCase.test_writable_state_stays_in_the_place`。
  - `lib/tests/test_stage_b.py` の全部（`src/stage_b.py` に向け直す）。
  - 写さない: `test_eye_sees_root_map_and_cut_policy`・`test_measure_reads_the_frozen_policy_copy`（`rules.maps` と始めの記録の写しを見る。書いた意図の探しの試験に替わる）・`test_eye_command_reads_only_its_prep`・`test_eye_command_is_the_original`・`test_every_command_is_in_the_ledger`（`command:` と写しの台帳）・`test_eye_schema_is_the_design_row_owner`（型のファイルを写さない）・`test_fallback_names_match_lib`（名の住処）・`KeepStateCase.test_unwritable_state_goes_to_the_spare_folder`（spare を持たない。null を返す試験に替える）・`test_composed_block_declares_no_run_owned_keys`・`test_name_inputs_and_return`・`test_return_node_carries_exactly_the_contract`（入力と返りが変わる。7.1 の形の検査と新しい返りの試験に替える）。
  - `lib/tests/test_blk_structure.py` は `lib/measure.py`（KEEP）の試験なので `lib/tests/` に残す（README の 9.5 は structure へ MOVE と書くが、試す物が lib に残る）。
- 読み手の側の試験はそれぞれの block と line に残す（plan の `structure_gaps`・plan-review の写し・line の修正前の承認ノードの人に上げる行・eyes の `after_section`・report の行・`outcome` の残りの数え）。
- keep-essence の 12 の仕組みのうち、この block が担う物は無い（README の 10 節）。README の 1.3 の歩かせ 9 が割り当てた直した後の実測の能力の行（E68・E74）はこの block の after の試験で縛る: `structure-after.json` の `after.changed` と `after.timing.wall_s` が在る（上の after の試験）。e2e の `tests/e2e/evidence.json` の P061・P065・P067（`rules.maps` は `intent.json` の文書の行に替える）・P068・P079・P081・P082（`eye-prompt-2.md` は `structure-eye-prompt-2.md` に）・P083・P084・P093・P095・P099・P101・E68・E70・E74・L-W54 は、node の id と place のパスを新しい物に合わせる。

## 8 報告の行

`structmark.report_lines(<structure-state.json>, <after なら place、before なら None>)` の行のまま（判定の行か落ちの印・構造の実測と目で増えた時間・直した後の実測の行）。after で目の行が在れば、判定の行が直した後の目の行になる。block が組むのはこの呼び出しだけで、文の字は `structmark` が持つ（KEEP。最後の承認ノードと共に使う）。

## 9 未確認

- 起動の殻で `blocks/` を読ませる引数の名と、5 節の命令の正確な形。
- Archon は `prompt:` に入れた値の中の `$` に続く字を置き換え直す（materials の設計書の 3.1。`lib/rolekit.py` の `with_reject` の docstring）。書いた意図の文書と差分には対象の字の `$…` が入りうるので、役が見る字と機械の写しが食い違いうる。md で「`$` を含まない所を抜き書きに選べ」と言って避けた（11 節の 13）。置き換えを止める口が Archon に在るかは未確認。
- `prompt:` に入る指示の大きさ: after の指示は差分（最大 40000 バイト）と書いた意図（文書ごとに最大 6000 字）を持ち、今の目の指示（例の run で 21 KB、大きい run で 234 KB）と同じ桁。README の未確認の一覧と同じ。
- 目の既定の system prompt に作業ツリーの cwd と git status が入ること（6 節の 7）を、書いた意図と比べる見方の下で塞ぐか。塞ぐ形（Archon の `systemPrompt`）は YAML に指示の文を書くことになり、README の 5 節がその置き場を決めていない。

## 10 決めた所の図

```text
mode=before                          mode=after
  units ─┐                             base ─┬─ 段 B（差分・fence_up・新しい名）
         ├─ 段 A（measure.py・地図）    units ─┤  plan ─ 外れの訳
  intent ┤  （HEAD の版）               intent ┤  （base の版）
  policy ┘                             policy ┘
         └──── 書いた意図の節 + view.json (+ 差分) ────┐
                                                     ▼
                                   structure-eye（道具なし・3 回まで）
                                                     ▼
                         design.jsonl・structure-state.json（・structure-after.json）
```

## 11 自分で決めた事

1. 直した後の時にも構造の目（AI）を起こす。根拠: README の 8.6 は「入る時」の目を「PR の差分を書いた憲法と比べる」と決め、差分は直した後にしか無い。8.2 の port `base` も after の時の物。段 B の機械の実測だけでは、書いた意図の文に反するかは判じられない。
2. 書いた意図の決まった名を、根と、単位（after では差分のファイルも）の上の各フォルダの `ARCHITECTURE.md`・`AGENTS.md` にした。根拠: 今の目の根の地図の名（`lib/design.py` の `MAP_NAMES`。r2 も使う）と同じ名で、`AGENTS.md` は近いフォルダの物が効く決まり（https://agents.md の "the closest AGENTS.md to the edited file wins"）が業界の定石。対象の言語や道具に依らない。読む版は before が `HEAD`、after が `base`（直しが意図の文書を書き換えても、基準を緩めない。段 B の柵の表と同じ決め）。
3. 指示の比べを 3 つの commit に分けた（README の 11.4 は 2 つ）。根拠: この block は英語にするだけでなく見方を替える（持ち主の追加）。翻訳の差と見方の差を同じ commit で並べると、審査が「差の一覧どおりか」を分けて見られない。
4. after の差分を指示に入れる上限を 40000 バイトにした。根拠: 道具を持たない目に差分を読ませる道は指示しか無い。値は今 graph の指示を描く口が使う上限（`lib/graphloops/engine/render.py:27` の `FILE_CAP`。README の 9.1 が「使い手へ移す」と決めた定数）と同じ。切った時は印を付け、全体は `after.diff` に残す。
5. port `policy` と `plan` を足した（README の 8.2 は `mode`・`units`・`intent`・`base`）。根拠: 今の目は人が固めた方針の文書を見ていて（`context.rules`）、直した後の控えは修正案の外れの訳を持ち、R1・R3 の頭と最後の承認ノードが読む（`structmark.deviation_lines`）。無いと元の能力が落ちる。
6. place に書けない時の控えの置き場 `structure-spare/` を持たず、`structure: null` を返す。根拠: README の 4.3（block は自分の place のほかを開かない）。spare は place の外。読み手は null を「構造の目の行なしで計画した」と同じに扱える（今も構造が飛ばされた run は `structure-in` が null を渡す）。理由は `reason` と `report` に残る。
7. 出力に `optional` を残した。根拠: line の collect が、block の中の node が落ちた時に先へ進めてよいかをこの宣言で読み、報告がそれを分ける（`workflows/line/scripts/collect.py:31-33`）。宣言は自分の node の id だけで、ほかの block を名指さない。line の設計書が宣言の形を替えるなら、それに合わせる。
8. 目を Git の外で起こす旗（元の works）も、`systemPrompt` の替えも足さない。根拠: 今の振る舞いのまま。足すと YAML に指示の文が入り（`systemPrompt` は Archon の鍵で md から入れる口が無い）、README の憲法の 2 と食い違う。9 節の未確認に残した。
9. `lib/design-row.schema.json` を写さない。根拠: 実行の時に読む物が無く（#232 から）、行の型の正本は node の `output_format`（README の 4.1「写しを持たない」）。
10. 受け付けが書いた設計の行を、書いた直後に `structmark.rows` で読み直し、読めなければ `status: failed` にする。根拠: 元の works の `structure_edge` が持ち、工場で記録なく落ちた（6 節の 8）。行を書くのも読む口もこの block の内なので、1 か所で閉じる。
11. 6 つの形の文を md に移し、受け付けは形の数 `FORM_COUNT`（6）だけを持つ。根拠: 形の文は AI にだけ届く決まった指示の文（README の憲法の 2）。今の試験 `test_six_forms_match_the_design_doc` が設計書との一致を見ていたのは、文が Python に在ったため。
12. `verdict`・`route` の語は日本語のまま。根拠: 語は plan・plan-review・line・report・eyes が読む行の形（`structmark`・`gatemarks`・`planmarks` が持つ）で、この block の PR は `lib/` を変えない（README の 11.1）。
13. 抜き書きに `$` を含まない所を選ばせる（md の 1 文）。根拠: 9 節の Archon の置き換え。照らしを緩めずに、置き換えで食い違いうる所を役に避けさせる。
