<!-- coldwrite:skip AI 向けの決まり。語は docs/design/README.md の頭の語の一覧で定義 -->
# pack の共通の部品（`workflows/.shared/`）の決まり

block の script と `src/` が Archon と出入りする口と、2 つ以上の block が使う指示の断片と port の形を置く。設計は `docs/design/README.md` の 4 章と 5 章。

## 口を通さずに書けない物

- 入力の読み: script は `os.environ.get("INPUTS_<名>")` を字のまま読み、`ports` の form の口（`text`・`flag`・`choice`・`json`・`file`）に渡す。名を組んで読まない。依頼の行は `requestrows.findings(raw)`（形の照らしと、知らない鍵・下書きの行の拒みまで）。
- place: `ports.place()` だけ。run directory の根（Archon の環境変数）を script と `src/` に書かない。place は作るだけで消さない。block が消してよいのは、自分が名を持つファイルだけ（名で引く。`rejects-*.json` のような広い形で消さない）。ほかの block に渡すファイルは `ports.pointer(path)` で出力に入れる。
- 指示: prep は `prompt.emit(node_id, values, when, prompt.round_of(node_id))`（組むだけなら `prompt.render`）だけで組む。md のパスも文も渡さない。前の回の却下は `with:` の `$LOOP_PREV` で受けず、place の却下の控え（`lib/rolekit` の `rejected(place, <名>)`）から全部を読む。`prompt.render` は md の全部の `{name}` に値を要る（選ばれない段落の中の `{name}` も、system の md の物も数える）。prep はいつも同じ組の値を渡し、入らない段落の `{name}` には空の字を渡す。
- node の出力: `ports.returns(obj)`。落ちない node は `ports.run(compute, fallback)`。

## `.shared` と `lib/` の分け

- 2 つ以上の block が使う助けのうち、Archon の pointer（`{type: archon_artifact, run_id, path}`）・`INPUTS_`・place・node の実行の記録を解く所は、ここの口（`ports.py` か、ここの小さなモジュール）に置く。試験は `tests/blocks/shared/`。
- 解いた後のパスや値を受けて中身（行・欄の意味）を返す所は `lib/` に置く（`lib/` は Archon を知らない。`lib/AGENTS.md` の E3）。試験は `lib/tests/`。`lib/` の今のモジュールは変えない。2 つ以上の block が使う新しいモジュールは足してよい（例 `lib/materialkit.py`）。
- pointer の JSON を読んで行を返す助けは、pointer を解く所が `ports.json`・`ports.file` に既に在るので、ここに新しい口を足さない。script は `ports.json(raw, schema)` の値を渡し、行を取り出す所だけを `lib/` の新しいモジュールに置く（試験は `lib/tests/`）。
- JSON を読む口は、先に `ports.json`・`lib/jsonfile.py` に無いかを見る。

## 口の一覧

- `ports.py`: `text(raw)`・`flag(raw)`・`choice(raw, words)`・`json(raw, schema)`（schema は block の `schemas/` の名か `shared:<名>`）・`file(raw)`・`parsed(raw)`・`picked(raw, names, optional=())`（names の欄が作り手の出力に無ければ `KeyError`。無くてよい欄は optional）・`unknown_keywords(shape)`・`place()`・`pointer(path)`・`returns(obj)`・`run(compute, fallback)`・`lib_root()`・`inside(rel, root)`（置き場 root からの相対パスの照らし。`..` と先頭・末尾の `/` を拒む）・`shared_cache()`（run をまたぐ控えの根。`STATE_DIR` の下の `works-factory/`、渡されなければ None）。import すると `lib/` が読めるようになる。
- `ports.py` の、対象のコマンドを起こす block の口（`workflows/.shared/boundary.py` と同じ約束）: `RUNTIME_COPY`・`RUNTIME_COPY_PREFIX`・`RUNNER_PREFIXES`・`RUNNER_NAMES`・`drop_runner_env(user_env)`・`suite_keep()`。
- 埋め: `ports.polyfill(name)`（`fence`・`childsweep`・`skip_value`。`ports.py` の隣のファイルを読む）。`child_pointer` は chain が直に import する。役の書き込みの柵（`fence`）は起動の殻が役の claude を包むので、block が import する物ではない（読むだけの役は YAML の `sandbox.filesystem.denyWrite` に印を書く。根の `workflows/AGENTS.md` の E7）。
- `prompt.py`: `render(node_id, values, when)`・`render_part(name, values, when)`（AI の node でない物の指示を `prompts/parts/<name>.md` から組む。束ね役が起こす下請けが Read する指示のファイルなど）・`emit(node_id, values, when, n)`・`round_of(node_id)`・`lang(raw)`・`PromptError`。
- `requestrows.py`: `parts(raw)`・`findings(raw)`。依頼の行の port を読む口。

## 置く物

- `prompts/<name>.md`: 2 つ以上の block が使う指示の断片。md から `{shared:<name>}` で入れる。今在る名:
  - `rejected`: 前の回の却下（中の口 `{rejection}`）。
  - `query-rule`: 外への検索と出典の決まりの全部（名を出さない・どの出典を先に読むか）。役が web を引く時の決まりはここに足す。段落 `spawns` の真偽が要る（下請けを起こさない役は `spawns: false`）。役の定義と node の md は検索の決まりを書き直さず `{shared:query-rule}` で受け、断片を変えた時に取り込む md は直さない。断片の文だけを直す依頼は `prompts/query-rule.md` 1 本で閉じる。この一覧の行は断片の名や段落（`spawns`）が変わる時だけ直す。`tests/blocks/` に断片の字を照らす試験は無い（`tests/workflows/test_judge.py` の `QUERY_RULE` は旧の `lib/agents/judge.md` を照らす物で、作り直しの間は触らない）。
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
  - `writer-rules`: 作業ツリーを直す書き手の役の決まり（直し方・テストで赤→緑を示せない直しの証拠・食い違いの申し出・守ること）。段落 `conflict`（食い違いの申し出）・`evidence`（証拠の頭。4 つの種類のどれかが真の時）・`docs`・`prompts_kind`・`config`・`code`（証拠の 4 つの種類）・`where_fixer`・`where_tdd`・`where_rework`（証拠を書く場所。使う役の 1 つだけを真にする）の真偽が要る。
  - 素材の観点の族（docs/design/materials.md の 3.2）: `material-status`・`material-na`（段落 `na_never`・`na_cond_true`・`na_cond_false`・`na_judged`、中の口 `{na_why}`）・`material-where`・`material-readonly`。
  - 目の外の block も使う物（docs/design/r1.md の 0.6）: `axis`（判断の 1 軸の 1 文）・`concept-map`（考えの住処の地図。段落 `maps_found` の真偽が要る。中は次の 2 本を選ぶだけ）・`concept-map-found`（中の口 `{concept_maps}`）・`concept-map-none`（中の口 `{map_tail}`）。値は `lib/eyekit.py` の `maps` が組む。`concept-map-found`・`concept-map-none` は段落の印を持たないので、段落の中に地図を置く md（r4 のまとめた形）はこの 2 本を自分の段落で選ぶ。
  - 独立の目の族（docs/design/r1.md の 0.6。r1〜r4 だけが使う。どれも段落の印を持たないので、段落の中に置ける）: `eye-role`（役の 2 行目と 3 行目）・`eye-diff`（累積差分の 1 段落。中の口 `{diff_file}`・`{base}`・`{changed_files}`・`{repo}`。値は `eyekit.diff_values`）・`eye-frozen`（読むのはこの run に固定した作業ツリー）・`eye-green`（最後のテストの認証が通っていない 1 文。md は `<!-- if not green -->` の中に置く）・`eye-seen`（seen と unseen・status の 3 語。中の口 `{st_pass}`・`{st_redesign}`・`{st_unverifiable}`）・`eye-coherence`（R3 の観点の全部。`axis`・`eye-seen` を中に持ち、中の口 `{home_prefix}`・`{after_section}`・`{review_md}`・`{repo_review_md}`。地図は持たない）・`eye-policy`（`policy` とこの役の書く先 reason。md は `<!-- if policy -->` の中に置く）・`eye-recorded-policy`（目の 1 文と `recorded-policy`。段落の外に置く）。
- 取り置いた断片の名（まだ置かない。最初に要った PR が、この名で足す）: 今は無い。
- `schemas/<name>.schema.json`: 2 つ以上の block が使う port の形。今在る物: `request.schema.json`（依頼の行）・`constraints.schema.json`（前提の実測の行）・`purpose.schema.json`（固めた目的）・`units.schema.json`（判定が切った根本の単位の目録）・`plan-verdict.schema.json`（事前審査の最後の往復の結論）・`gate-answers.schema.json`（承認ノードの人の答え `{start, before_fix}`）・`pushes.schema.json`（無人の run が採った推しの文）・`fix-marks.schema.json`（修正の印）・`judgment.schema.json`（受け付けた判定。欄 `units`・`questions`）・`prior-failures.schema.json`（前の run で通らなかった物の行 `[{where, text}]`）。
  - 形は `lib/graphloops/engine/schema.py` の `KNOWN_KEYWORDS` の語だけで書く（`type`・`enum`・`const`・`required`・`properties`・`patternProperties`・`additionalProperties`・`items`・`minItems`・`maxItems`・`minimum`・`maximum`・`minLength`・`maxLength`・`pattern`・`note`・`description`）。`anyOf`・`oneOf`・`format`・`$ref` などは照らしが効かないので、`ports.json` も形の検査も拒む。
  - `required` は値が object の時だけ効く（`request.schema.json` は行の配列 `[]` を通す。空の依頼の扱いは block が決める）。
  - 1 つの block の不具合は、その block の `src/` と `tests/blocks/<block>/` で閉じ、共通の形は直さない。
- 埋め（Archon に無い物を外から補う部品）: `fence.py`・`childsweep.py`・`skip_value.py`・`child_pointer.py`。読み方は上の口の一覧の「埋め」。
- 機械: `tests/layers/test_block_shape.py`・口の試験は `tests/blocks/shared/`。
