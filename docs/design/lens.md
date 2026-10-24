# block の設計書: lens（黙った失敗のレンズ）

- 何の話か: 修正の後の差分に、利用者が入れた review の agent（今は pr-review-toolkit の silent-failure-hunter）を 1 本ずつ独立の node として当て、指摘を出どころのレンズの名つきで返す観点を、単独で呼べる block `workflows/lens/` にする設計。型は [README.md](README.md)、形は手本の [world.md](world.md) に従う。指摘を確かめて穴にするのは差分の審査の block（[delta-review.md](delta-review.md)）で、この block は指摘を集めるだけ。
- 決めたこと: 今の fix の中の 4 つの node（lens-prep・lens・lens-reply・lens-collect）を、入口・レンズごとの 3 つの node（prep・役・受け取り）・出口の block にする。レンズを起こすかの振り分け（変わったファイルが在るか・定義が引けるか）は入口が決める。落ちたレンズは理由つきの行に残して先へ進み、集めが壊れた時だけ `ok: false` を返す（今と同じ）。入力は差分の版・レンズの一覧・言語の 3 つで、差分はこの block が自分で切る。指示は英語の断片 1 本（`prompts/parts/lens.md`）にし、今 Python が持つ文（役の定義の見出し・仕事と返し方の節）は md へ出す。返りの中継の埋め（P8 の `lens-reply`）は要らなくなる。
- 持ち主に求めること: なし。読み手は、この block を作る実装の役と、その PR の審査（README の 11.1 の作る順の 2 波目の block。急ぎの期限は無い）。

この文書の語は README の頭の物を使う。ほかに:

- line: 工場のメイングラフ（README の 8.7）。どの block をいつ回すか（`when:`）と、渡す値（`with:`）を決める。
- 今: 作り直す前の、今動いている工場（`workflows/fix/` と `lib/`）。元の works: 工場の移植元。
- 深さで省く・上げ直し・戻せない組・案の直し: 差分の審査と同じ条件の語。定義は [delta-review.md](delta-review.md) の頭の語。
- 依頼の行: run に渡された修正依頼の行（`workflows/.shared/schemas/request.schema.json` の形）。`lang` が空の時の既定の文は共通の断片 `lang-default`。
- レンズ: 利用者が入れた plugin の review の agent の定義（`agents/<役>.md` の本文）を指示に貼り、修正の後の差分をその観点だけで見させる AI の node。子（Agent）を起こさない。読むだけ（Read・Grep・Glob）。
- レンズの表: この block が知るレンズの並び（`src/lenses.py` の `LENSES`。今の `lib/lenses.py` の `LENSES` の写し）。行ごとに YAML の node が 3 つずつ在る。
- 振り分け: レンズごとに起こすか（`go`）と起こさない理由を決めること。
- レンズの行: `lib/lens.py` の控え `lens.json` の行 `{lens, agent, go, reason, state: pending|ran|failed|not_routed, findings: [{lens, where, cite, why}], dropped}`。
- 例の run: 本物の run `fed2db95-cb8e-41ff-913b-92c056872040`（対象は工場自身のリポジトリ。置き場は `<run の置き場>/fix/fix/`）。silent-failure-hunter が 1 本走り、発見 4 件を返した（差分の審査がそのうち 1 件を穴に採った）。

## 1 block の全体

### 1.1 役

修正の前の版から今の作業ツリーまでの差分（未追跡の新しいファイルも入れ、`.archon/` の下は除く）を切り、表のレンズのうち入力が名指した物ごとに、変わったファイルが在り、定義の本文が引ける時だけ node を起こす。各レンズは新しい会話で、定義の観点だけで差分と呼び元・読む側を読み、変わったファイルの中の指摘（場所・今の姿の字列・何が黙って失敗し誰が気づけないか）を返す。出口は、走ったレンズの指摘を出どころの名つきで集め、落ちたレンズ・起こさなかったレンズも理由つきで行に残す。持ち主の決め `lens-per-node`（局所レビューは観点ごとに node を分け、どれを起こすかは振り分けの node で決める）と `code-review-lens`（範囲が被る道具を理由なく落とさない）に沿う。

### 1.2 port

入力（YAML の `inputs:`）:

- `base`（必須）: `text: 修正の前の作業ツリーの姿の git の版（木か commit の sha）。差分はこの版から今の作業ツリーまでを切る`
- `lenses`: `json(lenses.schema.json): 当てるレンズの並び [{lens, agent?, body?}]。lens はこの block のレンズの表の名、agent は定義を引く <plugin>:<役>（省けば表の物）、body は定義の本文（在れば agent から引かない）。表に在って並びに無いレンズは起こさない`。既定 `[{"lens": "silent-failure-hunter"}]`。
- `lang`: `text: 人に見せる欄（findings の why・findings_none）の言語。空は依頼の行の言語`。既定 `""`。

`schemas/lenses.schema.json`:

```json
{"type": "array", "items": {"type": "object", "additionalProperties": false, "required": ["lens"],
  "properties": {"lens": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
                 "agent": {"type": "string", "pattern": "^[^:\\s]+:[^:\\s]+$"},
                 "body": {"type": "string", "minLength": 1}}}}
```

出力（`returns: finish`、`outcome_field: ok`）:

- `ok`: boolean。`status` が `ok` か。
- `status`: `ok` か `failed`。`ok` は、全部の行が終わりの状態（`ran`・`failed`・`not_routed`）で控えを書けた時（レンズが落ちても `ok`）。`failed` は、port が読めない・表に無いレンズの名・差分を切れない・控えを書けない時（今の集め役 `lens-collect` が落ちて run を止めた所）。
- `reason`: 日本語の 1 行（人に見せる）。`failed` の訳。ほかは空の字。
- `rows`: pointer（`lens.json`。`lib/lens.py` の控えの形 `{rows: [...]}`）か null（`failed` で控えが無い時）。
- `ran`・`failed`・`not_routed`: 行の状態ごとの数。
- `carry`: `[{where, text}]`。次の run の依頼に渡す行（落ちたレンズの「再実行の要あり」。今の `fixbeside.next_items` のレンズの行の字）。
- `report`: 日本語の行の配列（5 節）。
- `optional`: `[{node, bare}]`。落ちても line が先へ進めてよい node の宣言（レンズの役とその受け取りの node。今の fix の `collect` の `optional` の `lens`・`lens-reply` に当たる）。

今との違い: 今は fix の place の 1 回目の差分の控え（`loop-fix_delta.json`）と始めの記録（言語）を名で開き、行を fix の place の `lens.json` に書き、差分の審査の材料 `review1-brief.json` の `lens` の欄に足し（`fixboard.brief_lens`）、集め役の事実を `lenses.json` に書いた。この block は、差分を `base` から自分で切り、行を自分の place に書いて pointer で返す。差分の審査の材料に足すのは、差分の審査の block が port `lens_rows` で受けて行う。採った・採らなかった件数（差分の審査の返答の `lens` の欄で数える）は差分の審査の block の報告の行になる。

### 1.3 node の並び（`workflows/lens/works-factory-lens.yaml`）

script の node はどれも `runtime: uv`・`mutates_checkout: false`。レンズの表の 1 行ごとに、下の番号 2〜4 の 3 つの node（prep・役・受け取り）を置く（今は silent-failure-hunter の 1 行。node の id はレンズの名 `<lens>`、欄の名はその `-` を `_` にした `<key>`）。

1. `intake`（script `intake.py`）: port を読み、この block が名を持つファイルを消し、差分を切って振り分け、`lens.json` に振り分けの行を書く。返り `{due, reason, <key>_go…}`（今は `silent_failure_hunter_go` の 1 つ。元の works の `lens-route` の返りの欄の形）。落ちない。
2. `<lens>-prep`（script `lens_prep.py`・`with: {lens: <lens>}`・`depends_on: [intake]`・`when: $intake.output.<key>_go == true`）: そのレンズの指示を組む。返り `{prompt}`。
3. `<lens>`（AI。`prompt: "$<lens>-prep.output.prompt"`・`depends_on: [<lens>-prep]`・`context: fresh`・`model: '@wf-fix-review'`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob]`・`mutates_checkout: false`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`idle_timeout: 1728000000`・`retry: {max_attempts: 2, on_error: all}`。`output_format` は今の `lens` のまま。2.4）
4. `<lens>-take`（script `lens_take.py`・`with: {lens: <lens>, reply: $<lens>.output}`・`depends_on: [<lens>]`）: 返答を place の `reply-<key>.json` に書く。返り `{ok}`。レンズの node が落ちた時は、既定の `trigger_rule` で飛ぶ。
5. `finish`（script `finish.py`・`depends_on: [intake, <lens>-prep…, <lens>…, <lens>-take…]`・`trigger_rule: all_done`）: 受け取った返答で行を埋め（受け取りの無い `pending` の行は `failed`）、`lens.json` を書き、出力を返す。どの段が落ちても落ちない。

返りの中継（今の `lens-reply`。埋め P8）は置かない。今の中継は、Archon が落ちた node の出口を読んだ node を落とすので、集め役が `with:` でレンズの返りを読まずに済むように在った。この block の出口は `with:` でレンズを読まず、受け取りの node が place に書いたファイルを読むので、同じ事が中継なしで成り立つ（レンズが落ちれば受け取りが飛び、ファイルが無いので出口が `failed` の行にする）。

レンズを 1 つの輪で回す形（node 1 つでレンズの数だけ回す）は取らない。持ち主の決め `lens-per-node` と、元の works の `blk-lens` の「節ごとに model を持てる」を守る（9 節の 1）。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、line から include された時は `$ARTIFACTS_DIR/lens/`）の下。名は `src/files.py` だけが持ち、入口はこの名と `<lens>-prompt-*.md` だけを名で引いて消す。

- `intake.json`: `{base, files, lang, routes: {<lens>: {go, reason, agent, body}}, failed, reason}`（`body` は振り分けで引いた定義の本文。prep が読む）。
- `lens.diff`: 差分（今の `fix-delta.patch` に当たる）。
- `lens.json`: レンズの行（今と同じ名・同じ形。`lib/lens.py` の `LENS_FILE`）。
- `reply-<key>.json`: 受け取った返答。
- `<lens>-prompt-<n>.md`: 組んだ指示（今の `prompt-lens-<key>.md`）。
- `errors.json`: 段が壊れた訳 `[{node, reason}]`。

### 1.5 コードの置き場

- `workflows/lens/src/__init__.py`: 空。
- `src/lenses.py`: レンズの表 `LENSES = ({"lens": "silent-failure-hunter", "agent": "pr-review-toolkit:silent-failure-hunter"},)`・`key(name)`（`-` を `_` に）・振り分け `route(row, files)`（今の `_any_change`: 変わったファイルが無ければ `(False, "修正の差分に変わったファイルが無い")`）・定義の引き `definition(agent)`（今の `fixboard.lens_route` の引きの部分: `engine.validator.agent_def(agent)` を呼び、例外〔`SystemExit` を含む〕は「<agent> の定義を引けない（<型>: <訳>）」、`None` か本文が空なら「<agent> の定義が役の設定に無い（pr-review-toolkit が入っていない）」を起こさない理由にする）。写す元 `lib/lenses.py` の `LENSES`・`key`・`_any_change` と `fixboard.lens_route`。字の下限 `MIN_CITE = 4`・`MIN_WHY = 20`（YAML の `output_format` の `minLength` と同じ字）も持つ。`lenses.render` の文は md へ出し、ここに持たない。
- `src/files.py`: 1.4 の名と `SKIP = (ports.RUNTIME_COPY_PREFIX,)`。
- `src/steps.py`: 入口（差分を切る〔`leftovers.snapshot`・`unittrees.pathspec_without(SKIP)`・`leftovers.git(… text=False)`・`leftovers.git_names`。delta-review の `src/cut.py` の `cut` と同じ手続き〕・振り分け・`lens.write_routes`）・prep の値・受け取り・出口（`lens.collect(place, {<lens>: <reply-<key>.json の中身か None>})`・数え・`carry`・`report`）。
- 使う `lib/`（KEEP。変えない）: `lens`（`LENS_FILE`・`STATES`・`UNSEEN`・`write_routes`・`collect`・`read`）・`leftovers`・`unittrees`（`pathspec_without`）・`jsonfile`・`oneline`・`graphloops/engine/validator.py`（`agent_def`。README の 9.1 で DELETE の候補。10 節の 1）。

### 1.6 つなぎ方（graph の側。block には書かない）

- line: fix の後、差分の審査の block の前に `include: works-factory-lens`。`when:` は差分の審査の block と同じ（修正の段の変更の確かめが通った・戻せない組が無い・上げ直しの後も深さで省かない。[delta-review.md](delta-review.md) の 1.6）。回さない時の報告の行「差分の審査を回さないのでレンズは起こさない（<訳>）」（今の `fixboard.LENS_NOT_DUE`）は line が組む。
- `with:`: `base: $fix.output.start_tree`（差分の審査に渡すのと同じ、修正の段の始めの木。fix の設計書の 1.2）・`lenses` は書かない（既定の表）・`lang: <始めの記録の lang>`。
- 読み手:
  - 差分の審査の block: `lens_rows: $lens.output.rows`（審査役の材料の `lens` の欄・採った件数の数え）。
  - line: `ok` が false なら止める（今は集め役が落ちて run が止まった）。`optional` を読み、レンズの役と受け取りの node の落ちを先へ進めてよい落ちとして報告に分ける（今の fix の `optional`）。
  - report: `sections` に `$lens.output.report`（報告の「未確認のレンズ」の節のうち、レンズの block の行）。line が `carry` を `facts` の `carry.findings` に入れる。
- 案の直しの後の 2 度目の修正の段も、差分の審査と同じく、もう 1 回 include する。

## 2 node の設計シート: silent-failure-hunter（レンズ）

表の行が増えた時、どのレンズの node もこの節と同じ設計シートに従う（md は `{part:lens}` の 1 行）。

### 2.1 役

利用者が入れた review の agent の定義の観点だけで、修正が作った差分と、その呼び元・読む側を読み、変わったファイルの中で、失敗が黙って握りつぶされる所を指摘する。読むだけで、子を起こさない。

### 2.2 port

`intake.json` の `routes.<lens>`（← port `lenses` の行と表の行。`agent` と定義の本文 `body`）・`lens.diff` のパス・変わったファイル（← port `base` と作業ツリー）・`lang`（← port `lang`）。前の回の却下は無い（受け付けで拒まない。2.8）。

### 2.3 組み立ての順（`prompts/silent-failure-hunter.md` は `{part:lens}` の 1 行。本文は `prompts/parts/lens.md`）

1. `## Role definition ({agent})`（決まった見出し）と `{body}`（← 定義の本文。前付けを剥がした物）。
2. `---`（決まった区切り）。
3. `## Your task here`（決まった文。頭の 1 文は `You are a lens for a local review after the fix, started in a new conversation.` で、筋書きが照らす）: レンズの名 `{lens}`・上の定義の観点だけでこの周の修正が作った差分を見る・修正を書いた役の会話も判定の経緯も引き継いでいない・読むだけ（使えるのは Read・Grep・Glob だけで、作業ツリーを 1 文字も変えない）・子（Agent）は起こせない（定義がほかの道具や子に触れていても、自分で読んで答える）。新しい会話で起きると書いてよい（輪の外の node で `context: fresh`）。
4. 材料の 2 行（決まった文と差し込み口）: 修正の差分 `{diff_file}`（Read する。周の頭に固めた版と修正後の姿の差）・変わったファイル `{files}`（← `intake.json` の `files` の JSON の字）。
5. 決まった文: 差分は起点であって境ではない（呼び元・読む側まで読む）・指摘は変わったファイルの中の物だけを挙げる・指摘は別の審査役が確かめてから穴になる。
6. `## How to answer`（決まった文と差し込み口）: 指摘 1 件ごとに `findings` の 1 行（`where` は変わったファイルのパスで一覧の字のまま・`cite` はそのファイルの今の姿に在る字列そのまま `{min_cite}` 字以上・`why` は何が黙って失敗し誰が気づけないか `{min_why}` 字以上）・指摘が無ければ `findings` を空にし `findings_none` に何を読んで無いと言えるかを書く・返すのは JSON だけ。
7. 言語の 1 文: `why` と `findings_none` を `{lang}` で書く。パス・識別子・コマンド・エラー文はそのまま。

差し込み口の値: `agent`（← 行の `agent`。`body` で渡されて `agent` が無い時は表の物）・`body`・`lens`・`diff_file`・`files`・`min_cite`（4）・`min_why`（20）（← `src/lenses.py` の `MIN_CITE`・`MIN_WHY`。YAML の `output_format` の `minLength` と同じ字。試験が結ぶ）・`lang`。段落の選びは無い。

定義の本文 `{body}` は利用者の plugin の字（英語）のまま入る。本文の中の `{…}` は値の中の字なので差し込み口にならない（`prompt.py` は入れた値を読み直さない）。

md の本文の正本は `workflows/lens/prompts/parts/lens.md`（設計書は本文を写さない）。

### 2.4 返す形

今の `lens` の node の `output_format` のまま（`workflows/fix/works-factory-fix.yaml:922-939`）: `findings [{where (1 字以上), cite (4 字以上), why (20 字以上)}]`・`findings_none`（字。無くてよい）。人に見せる欄は `why`・`findings_none`（`{lang}`）。

### 2.5 描いた骨組み（例の run の値）

```markdown
## Role definition (pr-review-toolkit:silent-failure-hunter)

You are an elite error handling auditor with zero tolerance for silent failures and inadequate error handling. …（定義の本文。約 120 行。## Core Principles・## Your Review Process・## Your Output Format・## Your Tone・## Special Considerations）

---

## Your task here

You are a lens for a local review after the fix, started in a new conversation. … (silent-failure-hunter) …
You only read. You can use Read, Grep, and Glob only …

- The fix's diff: `<place>/lens.diff` (Read it. …)
- Changed files: ["docs/design.md", "docs/works-parity.md", "lib/gatemarks.py", …（20 本）]

The diff is a starting point, not a border: read the callers and the readers. …

## How to answer

- One row in `findings` for each finding: `where` …, `cite` … (at least 4 characters), `why` … (at least 20 characters).
- If there is no finding, leave `findings` empty and write in `findings_none` what you read …
- Return only JSON.

Write `why` and `findings_none` in the language of the request (the user's language). …
```

例の run の値: 変わったファイル 20 本（今の `prompt-lens-silent_failure_hunter.md` の 8.9 KB の大半は定義の本文）。役は発見 4 件を返し、形の誤りで捨てた物は 0 件（`lens.json` の `dropped`）。集め役の事実は `{collector: {ok: true}}`。

### 2.6 今の指示との差

作り直しの時の、古い指示との差の記録。今の指示は `workflows/fix/commands/lens-silent-failure-hunter.md`（5 行。組んだ指示のファイルを Read せよとだけ言う）と、`lib/lenses.py` の `render`（:32-53）が組む本文の 2 か所に在る。

- 移した: `render` の文の全部（役の定義の見出し `fixboard.ROLE_DEF_HEAD`・区切り・`TASK_HEAD`「## このセクションでの仕事」と仕事の 3 文・材料の 2 行・起点と境の 1 文・`REPLY_HEAD`「## 返答の書き方」と 3 つの箇条）を md へ。Python に残るのは値（定義の本文・差分のパス・変わったファイル・字の下限）だけ。
- 消した: 指示のファイルを Read させる command の md（5 行）。指示は `$<lens>-prep.output.prompt` で役に届く（README の 5.2）。
- 替えた: 「指摘は差分の審査役が検算してから穴にする」を「指摘は別の審査役が確かめてから穴になる」に（ほかの block の役の名を書かない。言っている事は同じ）。
- 移した: 言語の 1 行（`rolekit.lang_line(start)`。汎用の欄の並び「reason・how・what・why・異議…」）を、この node の人に見せる欄（`why`・`findings_none`）の名指しに。
- 移した: 字の下限（4・20。今は md の文と YAML に別々に在った）を差し込み口に。
- 足した物は無い。英語にした（#764）。役の名「レンズ」は "a lens"。

### 2.7 元の works と graphloops の同じ場面

- 元の works の `works/blk-lens/`（振り分け `lens-route` → レンズの節 → 集め役 → 境。出口 `{ok, reason, lens_file}`）: 形はこの block と同じ（振り分けが go を返し、レンズごとに節が在り、節ごとに model を持てる）。工場は fix の中に写した（#94）。この block は元の独立の形に戻す。違い: 元はレンズの節の model・effort を段に直に書いた（`sonnet`・`medium`）。工場は群 `@wf-fix-review`（同じ sonnet・medium）にした（`d0b086a2`）。この block も群のまま。元の境の node（集め役が終わらなければ盤面を止める）は、この block では出口の `ok: false` で、止めるかは line が決める。
- graphloops: 修正の後のレンズは無い（判定の前の局所レビューは素材の観点 local-review の物で、この block と触れない。元の works の `blk-lens` の頭の説明）。
- 持ち主の決め `lens-per-node`（2026-10-01）・`code-review-lens`（標準の /code-review を兵隊に入れ、精度の高い方を残す）: 今はレンズの表が 1 行で、/code-review のレンズは入っていない。表に足すのは振る舞いを変える話なので、この作り直しの外（11 節）。

### 2.8 受け付け

拒まない（今と同じ。輪も却下の控えも持たない）。返答の形は Archon の `output_format` が照らす。受け取った返答の `findings` を 1 件ずつ `lens._findings` の決まり（`where`・`cite`・`why` が空でない字）で検め、合わない行は捨てて `dropped` に数える。返答が無い（レンズの node が落ちた・受け取りが飛んだ）時は、その行を `failed`（理由「レンズのノードの出口が無い（落ちたか走らなかった）」）、`findings` が配列でない時は `failed`（「レンズのノードの出口の findings の形が違う: <頭の 200 字>」）にする。どれも `lens.collect` の今の字のまま。レンズの node の retry（2 回）は今のまま。

### 2.9 試験

8 節。この node に当たる物: 筋書き `standalone`・`PromptCase`・`FinishCase`・8.3 の行。

## 3 script の node

1. `intake.py`:
   1. place を作り、1.4 の名のファイルと `<lens>-prompt-*.md` だけを名で引いて消す（今の `lens_route` の「前の試みの控えを次の集め役に読ませない」と同じ働き）。
   2. port を `os.environ.get("INPUTS_BASE")`・`INPUTS_LENSES`・`INPUTS_LANG` の字のままで読む。`base` は `git rev-parse --verify <base>^{tree}` で照らす。`lenses` は `ports.json(raw, "lenses.schema.json")`。表に無い名・同じ名が 2 つ在れば「入力 lenses: 知らないレンズ <名>（この block のレンズは <表の名>）」「入力 lenses: レンズ <名> が 2 つ在る」。
   3. 差分を切って `lens.diff` に書き、変わったファイルを得る（`SKIP` の下を除く）。
   4. 表の行ごとに振り分ける: 並びに無い → 起こさない（「入力 lenses が名指していない」）・変わったファイルが無い → 起こさない（`route` の訳）・`body` が在る → 起こす・無ければ `definition(agent)` で引き、引けなければ起こさない（その訳）。
   5. `lens.write_routes(place, [{lens, agent, go, reason}…])`（`go` が偽の行は `not_routed`、真の行は `pending`）と `intake.json`（`routes` に定義の本文を含む）を書く。
   6. 返り `{due: どれかが go, reason: "", <key>_go: …}`。
   7. 2〜5 の例外は落ちずに `errors.json` に積み、`intake.json` に `failed: true` を書いて、全部の `<key>_go` を偽にして返す（`ports.run` の fallback）。
2. `lens_prep.py`（`INPUTS_LENS`）: `intake.json` の `routes.<lens>` を読み、2.3 の値で `prompt.emit(<lens>, values, None, prompt.round_of(<lens>))` を呼んで `{prompt}` を返す。組めなければ `errors.json` に積んでから非 0 で落ちる（レンズの node は起きず、出口がその行を `failed` にし、`status` は `failed`）。
3. `lens_take.py`（`INPUTS_LENS`・`INPUTS_REPLY`）: `ports.parsed(INPUTS_REPLY)` を `reply-<key>.json` に書き、`{ok: true}` を返す。書けなければ非 0 で落ちる（出口がその行を `failed` にする）。
4. `finish.py`（落ちない）:
   1. `intake.json` が無い・`failed` → `status: failed`・`rows: null`・数えは 0・`report` は「レンズ: 落ちた（<訳>）」の 1 行。
   2. ほかは `lens.collect(place, {<lens>: <reply-<key>.json の値か None>…})` で `pending` の行を埋めて `lens.json` を書き直す。控えが無い・読めない（`ValueError`）・書けない時は `status: failed`・`reason`「レンズの集め役が終わらなかった: <訳>」（今の `fixboard.LENS_NOT_DONE` の字）。
   3. `errors.json` に prep の行が在れば `status: failed`（行は `failed` のまま控えに残る）。
   4. 数え `ran`・`failed`・`not_routed`・`carry`・`report`（5 節）を組み、`{ok, status, reason, rows: ports.pointer(lens.json, "json(shared:lens-rows.schema.json)"), ran, failed, not_routed, carry, report, optional}` を返す。`optional` は `src/steps.py` の `OPTIONAL`（表の行ごとに `{node: <lens>, bare: false}` と `{node: <lens>-take, bare: false}`）。
   5. 例外は全部捕まえ、標準ライブラリだけで `{ok: false, status: failed, reason, rows: null, ran: 0, failed: 0, not_routed: 0, carry: [], report: [<訳の 1 行>], optional: OPTIONAL}` を返す。

`finish` の `output_format`: 全部の欄を `required`。`status` は `enum: [ok, failed]`、`rows` は `type: [object, "null"]` に pointer の 3 つの欄、数えは `minimum: 0` の整数、`carry` は `{where, text}` の object の配列、`report` は字の配列、`optional` は `{node, bare}` の object の配列。`intake` の返りは `additionalProperties: false` で `due`・`reason`・表の行ごとの `<key>_go` を全部 `required`。

## 4 単独で呼ぶ

```sh
bin/works-factory workflow run works-factory-lens --cwd <対象> --input base=<修正の前の木か commit>
```

定義を引くには、起動の隔離した設定に pr-review-toolkit が入っているか、`PR_REVIEW_TOOLKIT_ROOT` がその置き場を指す（`engine.validator.find_plugin_path` の探す順）。どちらも無い手元では、`--input lenses='[{"lens":"silent-failure-hunter","body":"<定義の本文>"}]'` で本文を渡せる。出力は `workflow get <run>` の `finish` の返り。

## 5 報告の行（日本語。今の字のまま）

- 起こさなかった・落ちたレンズごとに「<lens>: <`lens.UNSEEN` の語>（<理由。無ければ「理由の記録が無い」>）」、無ければ「なし（振り分けたレンズは全部走った）」（今の `lens.report_lines` の頭）。
- 走ったレンズごとに「<lens>: 出した発見 <n> 件・形の誤りで捨てた <d> 件」。
- `failed` の時は「レンズ: 落ちた（<訳>）」の 1 行だけ。
- 採った・採らなかった件数と「手直しの差分にはレンズが当たらない（最後のテストで守る）」の行は、差分の審査の block の行（それを数える事実を持つのは差分の審査の返答。README の 4.1）。

`carry` の行: `failed` の行ごとに `{where: "レンズ <lens>", text: "<lens>（再実行の要あり: 落ちて観点を誰も見ていない。理由: <理由の 1 行>）"}`（今の `fixbeside.next_items` の字）。

## 6 今の工場との比べ（確かめ・守り・落ちた時・書く順）

1. 差分の審査を回さない時はレンズを起こさず、集め役の事実に訳を置く（`LENS_NOT_DUE`）→ line が include しない。報告の行は line（1.6）。
2. 前の試みの控えを消す（`lens.json`・`lenses.json`）→ `intake` が名で引いて消す。
3. 1 回目の差分の控えが無ければ落ちる（「差分の審査の支度が走っていない」）→ 差分を自分で切るので起きない。版が読めなければ `failed`。
4. 変わったファイルが無ければ起こさない（`_any_change`）→ `src/lenses.py` の `route`（同じ字）。
5. 定義が引けない・本文が空・探しが出所の曖昧さで止まる（`SystemExit`）→ 起こさない理由にする（同じ字）。
6. 振り分けの行を書く（`lens.write_routes`）→ `intake`（同じ）。
7. 指示を組んで place に書く（`prompt-lens-<key>.md`）→ `<lens>-prep` が `prompt.emit` で `<lens>-prompt-<n>.md` に書く。
8. レンズは読むだけ・子を起こさない・新しい会話（`context: fresh`）・群・retry → 1.3 の 3（同じ）。
9. レンズが落ちても止めない（中継 `lens-reply` と `if_skipped: null`・`optional` の宣言）→ 受け取りの node が飛び、出口が `failed` の行にする。`optional` は出力の欄（1.3・3 の 4）。
10. 集め役が行を埋める（形の合わない発見を捨てて数える・出口の無いレンズは `failed`）→ `finish` が `lens.collect` を呼ぶ（同じ）。
11. 集めが ok でない・集め役が落ちる時は理由を書いてから run を止める（`lens_collector(False, LENS_NOT_DONE)`）→ `status: failed`・`ok: false`、止めるのは line（同じ結果）。
12. 差分の審査の材料に行を足す（`fixboard.brief_lens`）→ 差分の審査の block が `lens_rows` で受ける。
13. 報告の「未確認のレンズ」・最後の承認ノードの「仕組みの異常」の行・次の依頼の「再実行の要あり」→ `report`・`carry`（5 節）。採った件数の行は差分の審査の block。

落とした物は無い。替えたのは 9（中継の埋めをやめた）と 11（止める所が line の `ok` の読みへ）。

## 7 守る keep-essence

元の works の keep-essence の 12 の仕組み（README の 10 節。赤緑の機械の判定・書き込みの出どころなど）のどれも担わない（6 節の 13 項は今の工場のレンズの段の確かめで、keep-essence とは別の一覧）。差分の審査の block が指摘を確かめて穴にする時の材料を作る（keep-essence の外の、持ち主の決め `lens-per-node`・`code-review-lens`）。

## 8 試験と、済んだと言える条件

### 8.1 standalone の fixture（`workflows/lens/fixtures/`）

どれも `exec-code: true`・prep を差し替えない・AI の node の返答だけを差し替える。

- `standalone.stubs.yaml`: 入力 `base: 4b825dc642cb6eb9a060e54bf8d69288fbee4904`（git の空の木。筋書きの作業ツリーの `README.md`・`AGENTS.md` が変わったファイルになる）・`lenses: '[{"lens": "silent-failure-hunter", "body": "You look for errors that are swallowed without a trace."}]'`（筋書きの手元に pr-review-toolkit は無いので本文を渡す）。`expect: completed`・`reached: [intake, silent-failure-hunter-prep, silent-failure-hunter, silent-failure-hunter-take, finish]`。`resolved-text-contains` の `silent-failure-hunter` は `You are a lens for a local review after the fix, started in a new conversation.`。役の返答は `findings: []`・`findings_none`。
- `not-routed.stubs.yaml`: 入力 `base: HEAD`（差分が空）。`reached: [intake, finish]`。レンズは起きない。
- 筋書きは完了・`reached`・指示の字だけを見る。

### 8.2 `tests/blocks/lens/`（`kit.Run` で script を子のプロセスで回す。始めの記録は置かない）

- `IntakeCase`: 読めない port・表に無い名・同じ名の 2 つ・版でない `base` で `failed` と port の名の頭の訳・差分が空で `not_routed`・並びに無いレンズは `not_routed`・`body` が在れば定義を引かない・定義が引けない（差し替えた `agent_def` が `None`・空の本文・例外・`SystemExit`）で `not_routed` と今の字の理由・`.archon/` の下の変更は差分に載らない・前の回の自分のファイルを消し、ほかの名は消さない。元: `tests/workflows/test_fix.py::DeltaScriptsCase.test_lens_prep_without_the_role_definition_is_go_false`・`lib/tests/test_blk_lens.py::test_not_routed_lens_is_counted`。
- `PromptCase`: 組んだ指示に定義の本文・レンズの名・差分のパス・変わったファイル・字の下限・言語の文が在る・本文の中の `{…}` が字のまま残る・埋まらない差し込み口が無い。元: `lib/tests/test_fix_seams.py::LensesSeamCase`（`agent_def` が利用者の入れた plugin の `agents/<役>.md` から引いた本文が指示に入る）・`test_fix.py::test_lens_prep_with_the_role_definition_and_collect`。
- `FinishCase`: 受け取った返答の発見に出どころの名が付く・形の合わない発見を捨てて数える・受け取りの無いレンズは `failed` で `ok` のまま・振り分けの行が無ければ `failed`・控えが書けなければ `failed` と「レンズの集め役が終わらなかった」・`carry` の行・`report` の行・`optional`。include された時は place が include の道に分かれる。元: `test_blk_lens.py` の `test_collect_marks_findings_with_lens_name`・`test_collect_records_failed_lens_and_succeeds`・`test_collect_without_routes_is_not_ok`・`test_findings_keeps_valid_and_counts_dropped`、`test_fix.py` の `test_a_failed_lens_is_recorded_and_the_block_goes_on`・`test_a_failed_lens_leaves_a_failed_row_and_the_collector_goes_on`・`test_lens_collect_failure_is_reported_not_silent`。
- `ShapeCase`: レンズの表の行ごとに YAML に `<lens>-prep`・`<lens>`・`<lens>-take` が在り、`intake` の返りに `<key>_go` が在り、`finish` の `depends_on` と `OPTIONAL` に全部が在る（今の `test_lens_nodes_match_the_lens_table` の写し）・AI の node の鍵（群・`settingSources`・道具・sandbox・`idle_timeout`・`mutates_checkout`・`retry`・`context: fresh`）・`output_format` の `minLength` が `MIN_CITE`・`MIN_WHY`・`prompts/<lens>.md` がどれも `{part:lens}` の 1 行。
- 写さない試験: `test_blk_lens.py` の `test_count_line_always_names_failed_lens_count`・`test_summary_counts_adopted_by_lens_field`・`test_cut_brief_*` の 2 本・`test_review2_brief_has_no_lens`（差分の審査の block の試験へ。delta-review.md の 10.2）。
- 指示の比べの試験は作らない（2 波目の持ち主の決め）。審査は 8.3 の一覧で新旧を並べて見る。

### 8.3 英語の md が残す古い指示の一覧（審査が 1 つずつ照らす。今の `lenses.render`）

1. 役の定義の見出しに agent の名（`<plugin>:<役>`）を入れ、その下に定義の本文を字のまま置き、区切りの後に仕事の節が続く。
2. 修正の後の局所レビューのレンズ（名を言う）として、新しい会話で起きている。
3. 上の定義の観点だけで、この周の修正が作った差分を見る。
4. 修正を書いた役の会話も、判定の経緯も引き継いでいない。
5. 読むだけの役で、使えるのは Read・Grep・Glob だけ。作業ツリーを 1 文字も変えない。
6. 子（Agent）は起こせない。定義がほかの道具や子に触れていても、自分で読んで答える。
7. 修正の差分のパス（Read する。周の頭に固めた版と修正後の姿の差）と、変わったファイルの一覧。
8. 差分は起点であって境ではない。呼び元・読む側まで読む。
9. 指摘は変わったファイルの中の物だけを挙げる。
10. 指摘は審査役が確かめてから穴にする（2.6 の言い換えの後の字）。
11. 指摘 1 件ごとに `findings` の 1 行: `where`（変わったファイルのパス。一覧の字のまま）・`cite`（そのファイルの今の姿に在る字列そのまま。4 字以上）・`why`（何が黙って失敗し、誰が気づけないか。20 字以上）。
12. 指摘が無いなら `findings` を空にし、`findings_none` に何を読んで無いと言えるかを書く。
13. 返すのは JSON だけ。
14. 人が読む文の欄を言語の値で書き、key・パス・識別子・コマンド・エラー文はそのまま。

### 8.4 済んだと言える条件（PR ごと）

```sh
PYTEST_XDIST_AUTO_NUM_WORKERS=4 WORKS_FACTORY_ARCHON_CACHE=<Archon の源の置き場> nice -n 19 python3 -m pytest -q tests/blocks/lens tests/layers
```

最後に、4 節の命令で本物の単独の run を 1 回回す（小さな対象に変更を 1 つ入れ、pr-review-toolkit の入った設定で）。

## 9 根拠を書いて自分で決めた事

1. レンズは表の行ごとに YAML の node を置き、1 つの輪で回さない。根拠: 持ち主の決め `lens-per-node`（観点ごとに node を分け、どれを起こすかは振り分けの node で決める）と、元の works の `blk-lens` の「節ごとに model を持てる」。輪にすると node が 1 つになり、レンズごとの群を持てない。README の port `lenses` json は、表のどれを当てるかと、定義の引き先・本文を選ぶ値にした。
2. 返りの中継（埋め P8）を置かず、受け取りの node が place に書く形にした。根拠: 出口が `with:` でレンズの返りを読まなければ、落ちた node の出口を読む node が落ちる Archon の振る舞いに当たらない。埋めが 1 つ減る（`docs/polyfills.md` の P8 の使い手は組み込みで見直す）。
3. 入力 `lenses` の行に `body`（定義の本文）を置けるようにした。根拠: 憲法の 5（文とリポジトリだけで単独で回る）。筋書きと CI の手元に利用者の plugin は無く、本文を引けないと standalone の筋書きがレンズの node に届かない（形の検査の 7.1 の 3）。line は渡さない（既定の表の物を引く）。
4. 差分をこの block が `base` から自分で切る。根拠: 今はほかの段（差分の審査の支度）の控えを読んでいた。README の 4.3（block は port の値が指すファイルのほかは開かない）。差分の審査の block も同じ `base` から同じ手続きで切るので、両方が読むのは同じ差分（どちらも作業ツリーを変えない）。
5. 状態の語は `ok` と `failed` の 2 つにし、レンズが落ちても `ok`。根拠: 今もレンズの落ちは行に残して先へ進み、集めが壊れた時だけ run を止めた。
6. 採った・採らなかった件数と「手直しの差分にはレンズが当たらない」の行は、差分の審査の block の報告に置いた。根拠: 数える事実（審査の返答の `lens` の欄）と、手直しの差分を見る段を持つのは差分の審査の block（README の 4.1）。
7. 指示の比べ（README の 11.4: 1 つ目の commit で md を日本語のまま置いて古い指示と同じ字かを試験で照らし、2 つ目で英語にする）の 1 つ目の commit と試験は作らない。英語の md を直に書き、審査が 8.3 の一覧で新旧を見る（持ち主の、作り直しの 2 波目からの「速さ」の決め）。
8. `intake.json` に `lang`（port `lang` の字）も書く。根拠: `<lens>-prep` は `with:` で lens の名しか受けず、言語の文を組むには入口の控えから読むしかない（1.4 の形に足した）。
9. `finish` は `errors.json` に `<lens>-prep` の行が在れば `status: failed`・`ok: false`（3 節の 4 の 3）。`reason` は「レンズの指示が組めなかった: <node>（<訳>）」。入口が `errors.json` に積んだ行は入口の `failed` で先に処理される。
10. `base` が版として読めない時の訳は「入力 base: git の版（木か commit）として読めない: <値>」。`leftovers.Unreadable` を `ValueError` に替えて port の名を頭に付ける。
11. 入口の `ports.run` の fallback の返りの `<key>_go` は script の中に字で書いた（`silent_failure_hunter_go`）。落ちた先で `src` を import せずに返すため。表に足す時は script も直す（`ShapeCase` が YAML の欄と表を結ぶ）。
12. 試験は `tests/blocks/lens/test_lens.py` の 1 本に `IntakeCase`・`PromptCase`・`FinishCase`・`ShapeCase` を置いた。`finish.py` の逃げ道の `optional` も表の 1 行を字で持つ。
13. 筋書き `not-routed` は `base: HEAD` で、`reached: [intake, finish]`（レンズの 3 つの node は飛ぶ）。
14. `lens_prep.py` は `src` の import も try の中に置き、import が壊れても標準ライブラリだけで `errors.json` に積んでから落ちる（出口が `status: failed` にする。3 節の 2）。

## 10 README へ返す問題

1. `lib/graphloops/engine/validator.py` は README の 9.1 で DELETE（未確認つき）だが、`agent_def` と `find_plugin_path` はこの block が利用者の定義を引くのに使う（使い手はこの block 1 つ）。組み込みで消すなら、その 2 つを `workflows/lens/src/` へ移す。
2. `lib/leftovers.py`（README の 9 節に区分が無い）と `lib/unittrees.py` の `pathspec_without`（MOVE fix の中）を、この block と差分の審査の block も使う（delta-review.md の 12 節の 2・3）。

## 11 未確認

- 起動の隔離した設定（`CLAUDE_CONFIG_DIR`）が、block の script の node にも今の fix の `lens-prep` と同じく渡り、`agent_def` が利用者の plugin を引けるか（本物の単独の run で確かめる）。
- 持ち主の決め `code-review-lens`（標準の /code-review をレンズに入れる）の当て方は、今の表に入っていない。表に足すのは振る舞いを変える話で、この作り直しの外。
