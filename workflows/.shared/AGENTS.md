<!-- coldwrite:skip AI 向けの決まり。語は docs/design/README.md の頭の語の一覧で定義 -->
# pack の共通の部品（`workflows/.shared/`）の決まり

block の script と `src/` が Archon と出入りする口と、2 つ以上の block が使う指示の断片と port の形を置く。設計は `docs/design/README.md` の 4 章と 5 章。

## 口を通さずに書けない物

- 入力の読み: script は `os.environ.get("INPUTS_<名>")` を字のまま読み、`ports` の form の口（`text`・`flag`・`choice`・`json`・`file`）に渡す。名を組んで読まない。依頼の行は `requestrows.findings(raw)`（形の照らしと、知らない鍵・下書きの行の拒みまで）。
- place: `ports.place()` だけ。run directory の根（Archon の環境変数）を script と `src/` に書かない。place は作るだけで消さない。block が消してよいのは、自分が名を持つファイルだけ（名で引く。`rejects-*.json` のような広い形で消さない）。ほかの block に渡すファイルは `ports.pointer(path, form)` で出力に入れる（form は返すノードの pointer の欄の description と同じ字で、中身を照らしてから指す）。
- 指示: prep は `prompt.emit(node_id, values, when, prompt.round_of(node_id))`（組むだけなら `prompt.render`）だけで組む。md のパスも文も渡さない。前の回の却下は `with:` の `$LOOP_PREV` で受けず、place の却下の控え（`lib/rolekit` の `rejected(place, <名>)`）から全部を読む。`prompt.render` は md の全部の `{name}` に値を要る（選ばれない段落の中の `{name}` も、system の md の物も数える）。prep はいつも同じ組の値を渡し、入らない段落の `{name}` には空の字を渡す。
- node の出力: `ports.returns(obj)`。落ちない node は `ports.run(compute, fallback)`。

## `.shared` と `lib/` の分け

- 2 つ以上の block が使う助けのうち、Archon の pointer（`{type: archon_artifact, run_id, path}`）・`INPUTS_`・place・node の実行の記録を解く所は、ここの口（`ports.py` か、ここの小さなモジュール）に置く。試験は `tests/blocks/shared/`。
- 解いた後のパスや値を受けて中身（行・欄の意味）を返す所は `lib/` に置く（`lib/` は Archon を知らない。`lib/AGENTS.md` の E3）。試験は `lib/tests/`。2 つ以上の block が使う新しいモジュールは足してよい（例 `lib/materialkit.py`）。
- pointer の JSON を読んで行を返す助けは、pointer を解く所が `ports.json`・`ports.file` に既に在るので、ここに新しい口を足さない。script は `ports.json(raw, schema)` の値を渡し、行を取り出す所だけを `lib/` の新しいモジュールに置く（試験は `lib/tests/`）。
- JSON を読む口は、先に `ports.json`・`lib/jsonfile.py` に無いかを見る。

## 口の一覧

- `ports.py`: `text(raw)`・`flag(raw)`・`choice(raw, words)`・`json(raw, schema)`（schema は必須。block の `schemas/` の名・`shared:<名>`・`lib:<名>`。形に合わない値は `ShapeError`）・`file(raw, form)`（form は必須で入力の宣言と同じ字。json・jsonl の form は中身を照らしてからパスを返し、`file` は `.json`・`.jsonl` を拒む）・`carried_file(row)`（form を値と一緒に運ぶ行 `{ref, form}` の ref を行の form で照らしてパスを返す。種類の違うファイルを 1 つの欄で中継する値の読み）・`parsed(raw)`・`picked(raw, names, optional=())`（返す値まるごとだけを読み、pointer を開かない。names の欄が作り手の出力に無ければ `KeyError`。無くてよい欄は optional）・`form_of(description)`（form の語の住処）・`open_shapes(shape, …)`（中身を宣言しない所）・`is_pointer_shape(shape)`（pointer の欄の判別）・`shape_errors(value, schema)`・`unknown_keywords(shape)`・`place()`・`pointer(path, form)`（form は必須。中身を照らしてから指す）・`returns(obj)`・`run(compute, fallback)`・`lib_root()`・`inside(rel, root)`（置き場 root からの相対パスの照らし。`..` と先頭・末尾の `/` を拒む）・`shared_cache()`（run をまたぐ控えの根。`STATE_DIR` の下の `works-factory/`、渡されなければ None）。import すると `lib/` が読めるようになる。
- `ports.py` の、対象のコマンドを起こす block の口: `RUNTIME_COPY`・`RUNTIME_COPY_PREFIX`・`RUNNER_PREFIXES`・`RUNNER_NAMES`・`drop_runner_env(user_env)`・`suite_keep()`。
- 埋め: `ports.polyfill(name)`（`fence`・`childsweep`・`skip_value`。`ports.py` の隣のファイルを読む）。`child_pointer` は chain が直に import する。役の書き込みの柵（`fence`）は起動の殻が役の claude を包むので、block が import する物ではない（読むだけの役は YAML の `sandbox.filesystem.denyWrite` に印を書く。根の `workflows/AGENTS.md` の E7）。
- 道具に結びつく断片の印: `.shared/prompts/<name>.md` の頭の 1 行に `<!-- required-for-tools: <道具> <道具> -->` を置くと、どれかの道具を `allowed_tools` に持つ AI の node の指示がその断片を（段落に頼らずに）入れていることを、形の検査 7.1 の 14（`tests/layers/test_block_shape.py`）が照らす。`prompt.py` が差し込む時に印の行を落とす。別の対応表は置かない。道具に結びつかない断片（`works-gh` は gh を使う役、`lib-docs` は機械が控えを取った役、`writer-rules` は書き手の役だけが入れる）には印を付けない。
- `prompt.py`: `render(node_id, values, when)`・`render_part(name, values, when)`（AI の node でない物の指示を `prompts/parts/<name>.md` から組む。束ね役が起こす下請けが Read する指示のファイルなど）・`render_shared(name, values, when)`（`render_part` と同じ決まりで `.shared/prompts/<name>.md` を組む。2 つ以上の block が使う、AI の node でない物の指示。書き手の下請けのファイル）・`emit(node_id, values, when, n)`・`round_of(node_id)`・`lang(raw)`・`PromptError`。
- `requestrows.py`: `parts(raw)`・`findings(raw)`。依頼の行の port を読む口。
- `writerblock.py`: `prep(table)`・`save()`・`out()`・`paragraphs(table)`。書き手の型の block（`workflows/weapon-<型>/`）6 つの `scripts/writer_prep.py`・`writer_save.py`・`writer_out.py` の本体。型の名は呼んだ block のフォルダの名 `weapon-<型>`（`ports.caller_block()`）から引き、型ごとに違う物は block の `src/render.py` の表（定数 `ORDER_WEAPON`・`SPAWNS`・`SUMMARY`。欠ければ落ちる）だけ。`prep` は `INPUTS_ORDER`・`INPUTS_SLOTS` を `ports.json` で読み、型が持つ値（`first_prompt`・`unattended`・`overlay_file`・`summary_file`・`g1_items`）と段落（`spawns`・`g1`・`ask_variant`）を slots に足して `prompt.emit` で組む。表の `SPAWNS` が真の型は、slots の `subagents` から項目ごとの下請けのファイル（`g1-impl-<n>.md`・`g1-review-<n>.md`、brief の在る run は `seat-briefs.md`）をこの block の place に書く（`subagent_items`。値と借りた型の埋めは `lib/subagents.py`）。`save` は `INPUTS_REPLY` を形 `shared:writer-reply.schema.json` に照らして place の `reply-<n>.json` に書く（合わなければ落ちる）。`out` は入力を持たず落ちない（`ports.run`）: この周の `reply-<n>.json` を pointer で返し、prep か書き手か save が落ちた周は `ok: false` と `reason` を返す。返した物は、prep が落ちた周を除いて `out-<n>.json` にも書く。試験は `tests/blocks/shared/test_writerblock.py`。

## 置く物

- `prompts/<name>.md`: 2 つ以上の block が使う指示の断片。md から `{shared:<name>}` で入れる。今在る名:
  - `rejected`: 前の回の却下（中の口 `{rejection}`）。
  - `query-rule`: 外への検索と出典の決まりの全部（名を出さない・どの出典を先に読むか）。役が web を引く時の決まりはここに足す。段落 `spawns` の真偽が要る（下請けを起こさない役は `spawns: false`）。役の定義と node の md は検索の決まりを書き直さず `{shared:query-rule}` で受け、断片を変えた時に取り込む md は直さない。断片の文だけを直す依頼は `prompts/query-rule.md` 1 本で閉じる。この一覧の行は断片の名や段落（`spawns`）が変わる時だけ直す。頭の 1 行の印 `<!-- required-for-tools: WebSearch WebFetch -->` が、どちらかの道具を `allowed_tools` に持つ AI の node の指示に取り込まれているかを形の検査 7.1 の 14 が照らす（取り込み忘れは赤。出し直し用の `*-fix` の node も別の node なので取り込む）。`spawns` の値は YAML の node が `Agent` を持つ時だけ真（形の検査では照らさない）。断片の字を照らす試験は無い。
  - `lang-default`: `lang` が空の時の言語の文（`prompt.lang` が読む）。
  - `design-premises`: 人が決めた前提（承認ノードの答え・依頼が名指した設計書の部分・対象の地図。中の口 `{answers}`・`{named}`・`{map}`。段落 `answers`・`named` の真偽が要る）。独立設計と r2 の比べの役が共に差し込む。
  - `policy`: 人の方針（中の口 `{policy_body}`）。方針を受ける役の全部が、段落の中で差し込む。
  - `resubmit`: 拒まれた後に、同じ会話の続きで拒まれた欄だけを返させる役の指示（中の口 `{rejection}`・`{candidate}`）。
  - `handoff`: 引き継ぎのメモの頼みと前の周のメモのセクション（中の口 `{handoff_rounds}`。段落 `handoff_rounds` の真偽が要る。報告の書き手と、plan の書き手が使う）。
  - `recorded-policy`: 記録された方針（人か持ち主が決めた出どころの決まりと名指しの行。中の口 `{recorded_rows}`。段落 `recorded_none` の真偽が要る）。修正案の役が差し込む。目の外の block も使う（値は `lib/eyekit.py` の `recorded_rows_text` が組む）。
  - `prior-failures`: 前の run で最後まで通らなかった物の行（中の口 `{prior_notes}`・`{prior_redesign}`。段落 `prior_notes`・`prior_redesign` の真偽が要る）。
  - `unknown-asks`: 頭の深さの、依頼の行ごとの未知の種類と、種類ごとにすること（中の口 `{kind_none}`・`{kind_cause}`・`{kind_shape}`・`{kind_scope}`・`{unknown_rows}`・`{unknown_why}`。段落 `unknown_rows`・`unknown_none` の真偽が要る）。
  - `report-head-check`: 報告の頭の確かめの 2 段落（中の口 `{machine_heading}`。報告の block の初見の読み手だけが使う）。
  - 役の定義 5 本: `role-judge`・`role-blind-judge`・`role-cold-reader`・`role-inspector`・`role-investigator`。
  - `works-gh`: 読むだけの gh の口の使い方。
  - `lib-docs`: ライブラリの文書の欄の頭の文（控えを Read で読み、無い物は WebSearch・WebFetch で引く）。plan・plan-review・fix が使う。
  - `brief-reading`: brief ファイルの読み方の 2 句（背景は参照で食い違えば brief が勝つ・書き換えてよい範囲が「引けない」なら書き換えは許されない）。fix の `brief.md`・`g1-impl.md`・`g1-review.md` と plan の `plan-writer.md`（直し直す回）が差し込む。
  - `writer-rules`: 作業ツリーを直す書き手の役の決まり（直し方・テストで赤→緑を示せない直しの証拠・食い違いの申し出・守ること）。段落 `conflict`（食い違いの申し出）・`conflict_change`（その中の種類 `not_red`。変える段の書き手〔TDD の役・型 tdd・variant・remove の書き手〕だけ真）・`evidence`（証拠の頭。4 つの種類のどれかが真の時）・`docs`・`prompts_kind`・`config`・`code`（証拠の 4 つの種類）・`where_writer`・`where_tdd`・`where_rework`（証拠を書く場所。使う役の 1 つだけを真にする）の真偽が要る。
  - 書き手の型の block が共に使う指示の枠（D1。修正の block の TDD の役も `brief-head`・`brief` を使う）。字は修正の block の `prompts/parts/` から移した物:
    - `writer-top`: 書き手の指示の頭の材料の部分（brief・穴・範囲・テスト・却下・裁定・方針・依頼。中の口 `{rejection}`・`{rulings_file}`・`{saved_reply}`・`{faces_rows}`・`{scope_rows}`・`{tests_rows}`・`{tests_how}`・`{policy_path}`・`{request_file}`。段落 `briefs`・`faces`・`frozen_files`・`no_policy`・`no_request`・`policy`・`rejected`・`request`・`ruled_reply`・`rulings_first`・`scope`・`tests`・`tests_broken`・`tests_how`・`tests_new`・`tests_tail` の真偽が要る。中で `rejected`・`brief-head` を差し込む）。
    - `writer`: 書き手の決まりの本体（中の口 `{judgment_file}`・`{open_units}`・`{plan_file}`・`{notes_file}`・`{libdocs_rows}`・`{ripple_file}`・`{budget}`・`{draft}`・`{check_cmd}`・`{answer_file}`・`{left}`・`{lang}`・`{unattended}`・`{overlay_file}`・`{first_prompt}`・`{g1_items}`。段落 `ask`・`ask_ripple`・`ask_variant`・`g1`・`libdocs`・`overflow_answer`・`queued`・`resume`・`rules`・`rules_change`・`rules_named`・`rules_red`・`rules_red_unit`・`rules_sites`・`rules_sites_at`・`rules_sites_test` の真偽が要る。中で `brief`・`lib-docs`・`query-rule`・`writer-rules` を差し込む）。
    - `brief-head`: brief の部分の見出しと行（中の口 `{brief_rows}`）。
    - `brief`: brief の決まり 1〜8（段落 `rules`・`rules_change` の真偽が要る。中で `brief-reading` を差し込む）。
  - 書き手の型の block の下請けのファイル（D2。書き手が項目ごとに起こす実装役と審査役。本体 `writerblock` が `prompt.render_shared` で組んで書き手の block の place に書く。字は修正の block の `prompts/parts/` から移した物）:
    - `g1-impl`: 実装役の指示（中の口 `{template}`・`{check_cmd}`・`{weapon_rule}`。段落 `spawns`・`ask` の真偽が要る。中で `brief-reading`・`query-rule` を差し込む）。`{weapon_rule}` は works rules の見出しの下の 1 行だけの段落で、本体が、書き手の block の `prompts/parts/head.md`（型の決まりの頭の段落）を `prompt.render_part("head", {})` で組んで渡す（下請けを起こす型は、tdd の閉じの外の 5 つ全部。設計は fix.md の 24.9）。`{template}` は借りた superpowers の implementer の型を `lib/subagents.py` が埋めた字。
    - `g1-review`: 審査役の指示（中の口 `{template}`。段落 `spawns` の真偽が要る。中で `brief-reading`・`query-rule` を差し込む）。
    - `g1-scene`・`g1-rest`（中の口 `{keys}`）・`g1-report`・`g1-impl-report`・`g1-head-sha`: 借りた型の穴を埋める短い字。
    - `seat-briefs`: 直す義務の単位の brief を名指すファイル（中身は `{shared:brief-head}` の 1 行）。
  - 素材の観点の族（docs/design/materials.md の 3.2）: `material-status`・`material-na`（段落 `na_never`・`na_cond_true`・`na_cond_false`・`na_judged`、中の口 `{na_why}`）・`material-where`・`material-readonly`。
  - 目の外の block も使う物（docs/design/r1.md の 0.6）: `axis`（判断の 1 軸の 1 文）・`concept-map`（考えの住処の地図。段落 `maps_found` の真偽が要る。中は次の 2 本を選ぶだけ）・`concept-map-found`（中の口 `{concept_maps}`）・`concept-map-none`（中の口 `{map_tail}`）。値は `lib/eyekit.py` の `maps` が組む。`concept-map-found`・`concept-map-none` は段落の印を持たないので、段落の中に地図を置く md（r4 のまとめた形）はこの 2 本を自分の段落で選ぶ。
  - 独立の目の族（docs/design/r1.md の 0.6。r1〜r4 だけが使う。どれも段落の印を持たないので、段落の中に置ける）: `eye-role`（役の 2 行目と 3 行目）・`eye-diff`（累積差分の 1 段落。中の口 `{diff_file}`・`{base}`・`{changed_files}`・`{repo}`。値は `eyekit.diff_values`）・`eye-frozen`（読むのはこの run に固定した作業ツリー）・`eye-green`（最後のテストの認証が通っていない 1 文。md は `<!-- if not green -->` の中に置く）・`eye-seen`（seen と unseen・status の 3 語。中の口 `{st_pass}`・`{st_redesign}`・`{st_unverifiable}`）・`eye-coherence`（R3 の観点の全部。`axis`・`eye-seen` を中に持ち、中の口 `{home_prefix}`・`{after_section}`・`{review_md}`・`{repo_review_md}`。地図は持たない）・`eye-policy`（`policy` とこの役の書く先 reason。md は `<!-- if policy -->` の中に置く）・`eye-recorded-policy`（目の 1 文と `recorded-policy`。段落の外に置く）。
- 取り置いた断片の名（まだ置かない。最初に要った PR が、この名で足す）: 今は無い。
- `schemas/<name>.schema.json`: 2 つ以上の block が使う port の形。今在る物: `request.schema.json`（依頼の行）・`constraints.schema.json`（前提の実測の行）・`purpose.schema.json`（固めた目的）・`units.schema.json`（判定が切った根本の単位の目録）・`plan-verdict.schema.json`（事前審査の最後の往復の結論）・`gate-answers.schema.json`（承認ノードの人の答え `{start, before_fix}`）・`pushes.schema.json`（無人の run が採った推しの文）・`fix-marks.schema.json`（修正の印）・`judgment.schema.json`（受け付けた判定。欄 `units`・`questions`）・`prior-failures.schema.json`（前の run で通らなかった物の行 `[{where, text}]`）・`human-answers.schema.json`（設計の段の人の答えの行 `[{id: H<n>, kind, text, …}]`。書くのは line、読むのは theme）。
  - 書き手の型の block の形（修正の系。D1）: `weapon-order.schema.json`（修正の block が型の block に渡す注文 `{weapon, group, stage, since, base, units, scope, permits}`）。
  - 設計の段の形: `theme-design.schema.json`（設計の案の書き手の block theme が返す設計の案。line が降りる時に読む。docs/design/theme.md の 3 章）。
  - `writer-slots.schema.json`（書き手の指示の共通の値と段落の真偽 `{values, when, subagents, summary_file}`。`values`・`when` の鍵は全部 required）。
  - `writer-reply.schema.json`（書き手の返答。書き手の型の block の AI の node の `output_format` と同じ中身。`precedent` が `allOf`・`if`・`then`・`not` を使う）。
  - 形は中身を宣言する: object は `properties` か `patternProperties`、array は `items`、`type` に 6 つの型を全部並べない（`ports.open_shapes` が拒む）。中身の住処がほかの形に在る所は `description` の `json(<名>)` で名指す。include した block の出力は `json(returns:<workflow の名>)` で、include する workflow の node の `output_format` だけが名指す（`docs/design/README.md` の 4.1）。
  - 形は `lib/graphloops/engine/schema.py` の `KNOWN_KEYWORDS` の語だけで書く（`type`・`enum`・`const`・`required`・`properties`・`patternProperties`・`additionalProperties`・`items`・`minItems`・`maxItems`・`minimum`・`maximum`・`minLength`・`maxLength`・`pattern`・`allOf`・`if`・`then`・`not`・`note`・`description`）。`anyOf`・`oneOf`・`format`・`$ref` などは照らしが効かないので、`ports.json` も形の検査も拒む。
  - `required` は値が object の時だけ効く（`request.schema.json` は行の配列 `[]` を通す。空の依頼の扱いは block が決める）。
  - 1 つの block の不具合は、その block の `src/` と `tests/blocks/<block>/` で閉じ、共通の形は直さない。
- 埋め（Archon に無い物を外から補う部品）: `fence.py`・`childsweep.py`・`skip_value.py`・`child_pointer.py`。読み方は上の口の一覧の「埋め」。
- 機械: `tests/layers/test_block_shape.py`・口の試験は `tests/blocks/shared/`。
