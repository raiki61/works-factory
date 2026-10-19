# 素材の観点の族の設計書: 共通の形（materials）

- 何の話か: 判定の前に集める素材の観点 11 本（README の 8.1）を、1 本ずつ単独で呼べる block にする。その 11 本が共に従う形（intake → prep → 役 → accept → finish）、11 本が共に使う `lib/` の部品 `lib/materialkit.py`、指示の md の共通の節と共通の断片、観点の block の宣言の仕方を、この文書が決める。1 本目の観点 prior-decisions の設計は [prior-decisions.md](prior-decisions.md)。残りの 10 本の設計書はこの文書と prior-decisions.md を写して書く。型は [README.md](README.md)、手本は [world.md](world.md)。
- 決めたこと: 観点ごとに 5 つの node（intake・prep・役・accept・finish）の block にする。回すか（今の `material-route` の要否）と、回さない時の素材の状態（今の `material-route.json` の `fill`）は、観点の block の intake が自分で決める。block はどの道でも素材の状態を 1 つの `material.json` に書いて pointer で返す。対象差分の取り方・作業ツリーの写しと照らし・所見の場所の照らし・素材の欄の照らし・受け付けの流れは `lib/materialkit.py` の 1 か所に置き、観点の block は `src/viewpoint.py` の宣言（名・素材の名・回す条件・『条件に当たらない』の扱い・md の値・返答から素材への写し・観点だけの受け付け）だけを持つ。11 本の md が字のまま写している 4 つの段落（素材の書き方・所見の場所・『条件に当たらない』・作業ツリーを変えるな）と works-gh の段落は、共通の断片にする。振る舞いは変えない。
- 持ち主に求めること: なし。
- 読む人と使い方: 残りの 10 本の観点の設計書の書き手（この文書の 7 節の形で書く）と、族の部品 `lib/materialkit.py` と観点の block を作る実装者（2〜6 節の名と順をそのまま作る）。11 本の PR の前に要る（README の 11.1 の 1 波目）。

この文書の語は README の頭の物を使う。ほかに:

- 今: 今の工場の実装（`workflows/judge/` と `lib/judge_accept.py` など）。「新しい形」はこの作り直しの後の形。
- line: メイングラフ（README の頭の graph の 1 つ）。run の始めに「始めの記録」（run の入力・差分の根・言語・依頼の件数などを書いた `start.json`）を書き、block に port の値として配る。
- 周: graphloops の 1 回りの判定と修正。工場は 1 run = 1 周（持ち主の決め carry）なので、今の条件の「前の周の…」の枝はどれも効かない。
- 盤面: 元の works と graphloops が run の状態を置いた共有の記録（board）。工場には無い。

- 観点: 素材の観点 11 本の 1 本（prior-decisions・purpose-review・local-review・consistency-bypass・hygiene・external-standards・procedure-trace・gate-efficacy・test-double-fidelity・main-path-observation・provenance）。名は今の judge の `MATERIAL_ROLES`（`lib/judge_accept.py:1708-1720`）の鍵のまま。block のフォルダの名・YAML の名（`works-factory-<観点>`）・AI の node の id・`prompts/<観点>.md`・受け付けの控えの名（`rejects-<観点>.json`）が全部この名になる。
- 素材: 判定役（diagnose）が読む素材の 15 欄（`lib/judge_accept.py:104-120` の `MATERIALS`。`prior_decisions`・`local_review`・`consistency`・`bypass` など）の 1 つ。値は素材の状態 `{status, count?, detail?, checked?, reason?, from_round?}`。1 つの観点が 0〜2 個の素材を書く（purpose-review は 0、consistency-bypass は 2）。
- 回す条件: 観点の役を起こすか（今の `CONDS` の `cond`。例 `prior_decisions_due`）。偽なら役を起こさず、素材を埋める（今の `_fill_one`）。
- 当たる条件: 『条件に当たらない』（`not_applicable`）を役が名乗れるかを決める条件（今の `applies_cond`。例 `touches_procedures`）。
- 判定から入る run: 差分が空で依頼が 1 件以上の run（今の `request_entry`。`lib/judge_accept.py:1374-1382`）。修正が入るまで P1 の観点（prior-decisions と purpose-review のほかの 9 本）を起こさない。
- 族の部品: `lib/materialkit.py`（2 節）。

## 1 族の全体

### 1.1 役

観点ごとに 1 つの AI の役を起こし、対象差分（と観点ごとの材料）を見せて、その観点の素材の状態と観点の所見を返させる。機械が、役の返答を、作業ツリーを変えていないか・所見の場所がファイルに在るか・素材の欄が status ごとの決まりに合うか・観点だけの決まりに合うかで受け付ける。3 回拒まれたら諦める。回す条件に当たらない run では役を起こさず、理由つきの素材の状態を機械が書く。どの道でも、素材の状態と受けた返答を `material.json` に書いて返す（黙って欠けた素材を作らない。判定役の指示の「素材のどれかが明示返答を欠いているなら materials_missing」が、欠けを素材の不具合として扱うため）。

### 1.2 port

入力（YAML の `inputs:`）。どの観点も次の 3 つを持つ:

- `base`: `text: 対象差分の根の commit（対象差分は、この commit から作業ツリーの今の姿まで。未追跡の新しいファイルも入る）。空は HEAD`。既定 `""`。
- `entry`: `text: 判定から入る run の出どころの文（例「人の依頼（/path/req.json）」）。空は判定から入る run でない`。既定 `""`。
- `lang`: `text: 人に見せる欄（素材の detail・checked・reason と、観点ごとに設計書が名指す欄）の言語。空は依頼の言語`。既定 `""`。

観点ごとに要る物だけを足す（例: prior-decisions は `request`、purpose-review と external-standards は `purpose`、gate-efficacy は `gates`）。足す入力の名と形は各観点の設計書が決める。同じ意味の入力は同じ名と同じ形にする:

- `request`: `json(request.schema.json): 依頼の行の配列 [{where, text, mechanism?, measured?, false_positive_if?}]。それを findings の欄に持つオブジェクトでもよい（工場の依頼のファイルの形）。空の配列は依頼の行が無い`。既定 `[]`。schema は `blocks/world/schemas/request.schema.json` を字のまま写す。
- `purpose`: `json(purpose.schema.json): 固めた目的 {purpose_text, source, known_weaknesses, source_files}。null は目的の文がこの run に無い`。既定 `null`。

出力（`returns: finish`、`outcome_field: ok`）。どの観点も同じ 5 欄:

- `ok`: boolean。`status` が `ran` か `skipped` か。
- `status`: `ran`（役の返答を受けた）・`skipped`（回す条件に当たらず、役を起こさずに素材を埋めた）・`gave_up`（受け付けが 3 回拒んだか、出し直しても直らない拒みで 1 回目に諦めた）・`failed`（入力が読めない・対象差分が取れない・役の返答の記録が無い）のどれか。
- `reason`: 日本語の 1 行（人に見せる）。`ran` は空。ほかは訳（回さない理由・諦めた理由・読めなかった物）。
- `material`: `material.json` の pointer。書けなかった時だけ null。
- `report`: 日本語の行の配列（報告の節にする行。4.1）。素材ごとに 1 行と、観点の設計書が足す行。

`material.json` の中身（読み手は 2.10 の `materialkit.read` で読む）:

```json
{"role": "<観点>", "status": "ran|skipped|gave_up|failed", "reason": "<1 行>",
 "reply": <受けた返答の JSON か null>, "materials": {"<素材の名>": {"status": "...", "...": "..."}}}
```

欄 `role`・`reply`・`materials` は今の `judge/material-<役>.json`（`lib/judge_accept.py:2621` が書く）と同じ名で同じ形。今の読み手（`judge_accept._accepted`・`policy._settled_rows`）が読み方を変えずに読める。`status`・`reason` は足した欄。

今との違い: 今は 11 本が judge の中の 1 つの YAML に在り、要否を `material-route` がまとめて決め（`lib/judge_accept.py:1953-1986`）、差分と作業ツリーの写しを 1 度だけ `judge/` に置き、受けた返答を `judge/material-<役>.json` に書き、回さない素材の埋めと諦めの埋めは diagnose-prep の `fill_materials`（`:2654-2693`）がした。入力は始めの記録・`judge/request.json`・`judge/purpose.json`・`judge/stop.json` を名で開いた。新しい形では block が port だけを読み、自分の place に書き、素材の状態を自分で埋めて返す。止めの記録の確かめ（今の `material_route` の `read_stop`）は無くし、回すかは graph の `when:` が決める（README の 4.3）。

### 1.3 node の並び（雛形 `blocks/<観点>/works-factory-<観点>.yaml`）

`<観点>` を観点の名に替える。`<起こし方>` と `<返答の形>` は観点ごとに今の YAML の物をそのまま写す（5.2 の表）。

```yaml
name: works-factory-<観点>
description: >-
  <観点の 1〜2 行の日本語>。素材集めの観点の block（docs/design/materials.md の形）。単独の run でも、判定のまとめから include されても動く
inputs:
  base: {default: "", description: "text: 対象差分の根の commit（対象差分は、この commit から作業ツリーの今の姿まで。未追跡の新しいファイルも入る）。空は HEAD"}
  entry: {default: "", description: "text: 判定から入る run の出どころの文（例「人の依頼（/path/req.json）」）。空は判定から入る run でない"}
  lang: {default: "", description: "text: 人に見せる欄の言語。空は依頼の言語"}
  # ここに観点ごとの入力を足す
returns: finish
outcome_field: ok
nodes:
  - id: intake
    script: intake
    runtime: uv
    mutates_checkout: false
    output_format:
      type: object
      additionalProperties: false
      required: [due, reason]
      properties:
        due: {type: boolean}
        reason: {type: string}
  - id: <観点>-loop
    depends_on: [intake]
    when: $intake.output.due == true
    loop_group:
      max_iterations: 3
      fresh_context: false
      until_bash: done=$<観点>-accept.output.done; test "$done" = true
      nodes:
        - id: <観点>-prep
          script: role_prep
          runtime: uv
          mutates_checkout: false
          output_format:
            type: object
            additionalProperties: false
            required: [prompt]
            properties:
              prompt: {type: string}
        - id: <観点>
          prompt: "$<観点>-prep.output.prompt"
          depends_on: [<観点>-prep]
          <起こし方>
          retry: {max_attempts: 2, on_error: all}
          output_format: <返答の形>
        - id: <観点>-accept
          script: role_accept
          runtime: uv
          mutates_checkout: false
          depends_on: [<観点>]
          with: {reply: $<観点>.output}
          output_format:
            type: object
            additionalProperties: false
            required: [ok, done, reason]
            properties:
              ok: {type: boolean}
              done: {type: boolean}
              reason: {type: string}
  - id: finish
    script: finish
    runtime: uv
    mutates_checkout: false
    depends_on: [intake, <観点>-loop]
    trigger_rule: all_done
    output_format:
      type: object
      additionalProperties: false
      required: [ok, status, reason, material, report]
      properties:
        ok: {type: boolean}
        status: {type: string, enum: [ran, skipped, gave_up, failed]}
        reason: {type: string}
        material:
          type: [object, "null"]
          required: [type, run_id, path]
          properties:
            type: {const: archon_artifact}
            run_id: {type: string}
            path: {type: string}
        report: {type: array, items: {type: string}}
```

- `max_iterations: 3` は `rolekit.GIVE_UP_AFTER`（3）と同じ数（今の試験が YAML と突き合わせる決まりを続ける）。
- prep は `with:` を持たない（自分で決めた。10 節）。却下の段落の中身は accept が place に積んだ控え（`rejects-<観点>.json`）から組む。
- 4 本の script の名（`intake`・`role_prep`・`role_accept`・`finish`）は 11 本で同じにする。どれも `lib/` のモジュールの名と重ならない（README の 7.1 の 9。`accept` と `prep` は `lib/accept.py` と字が重なりうるので使わない）。名は block のフォルダの中で探されるので、11 本が同じ名を持っても重ならない（README の 3 節の `discoverPackScripts`）。
- AI の node の `<起こし方>` は、今の YAML の錨（`&read_launch`・`&net_closed_launch`・`&test_run_launch`）の中身を、その block の YAML に字のまま展開して書く（錨は 1 本の YAML の中でしか効かないため）。`model:` は今の群の名 `'@wf-judge-materials'` のまま。`mutates_checkout: false` は、今その役の node に在る物だけに付ける（5.2 の表の「状態の照らし」）。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、判定のまとめから include された時は `$ARTIFACTS_DIR/<judge の include の id>/<観点の include の id>/`）の下に書く。名は `lib/materialkit.py` の定数だけが持つ（2.1）:

- `intake.json`: intake が読んだ port の値・対象差分の見方・回すかの決め・回さない時の素材の状態（2.6）。
- `view.json`・`diff.patch`・`changed-files.txt`: 対象差分（今の `judge/material-view.json`・`judge/diff.patch`・`judge/changed-files.txt` と同じ中身）。
- `tree.json`: 役を起こす前の作業ツリーの姿（今の `judge/material-tree.json` と同じ形）。在れば書き直さない（今の「最初の姿を残す」のまま）。
- `<観点>-prompt-<n>.md`: 組んだ指示（`<n>` は `rolekit.attempt(place, <観点>)`。1 回目は 1）。
- `rejects-<観点>.json`・`rejects-<観点>.md`: 拒否の控え（`rolekit.accept_round` が書く）。
- `accepted.json`: 受けた返答と素材の状態 `{role, reply, materials}`（accept が書く）。
- `material.json`: 出口の素材（finish が書く。1.2）。

intake は place の中のファイルを消さない（自分で決めた。10 節）。

### 1.5 コードの置き場

観点の block（`blocks/<観点>/`）:

- `works-factory-<観点>.yaml`（1.3）。
- `prompts/<観点>.md`（3 節の並び）。
- `scripts/intake.py`・`scripts/role_prep.py`・`scripts/role_accept.py`・`scripts/finish.py`（6 節。どれも 20 行ほどの薄い殻）。
- `src/__init__.py`（空）と `src/viewpoint.py`（5 節の宣言）。観点だけが使う受け付けの関数（例 local-review のレンズの照らし）も `src/` に置く。
- `schemas/<入力>.schema.json`（観点ごとの json の入力。`request.schema.json` など）。
- `fixtures/standalone.stubs.yaml` ほか（8 節）。

族の部品 `lib/materialkit.py`（2 節）と、その試験 `lib/tests/test_materialkit.py`。11 本の観点の block と、素材を読む block（diagnose）が使う。README の 9.3 の「素材の 11 本の共通の部品（新しい 1 モジュール。`judge_accept` の `material_*` から作る）」がこれ。

使う `lib/`（KEEP の物だけ）: `accept`（作業ツリーの姿・照らし・Reject・guard・`touched_files`・`copy_flag_free_index`）・`rolekit`（受け付けの回・控え・諦め）・`cite`（所見の場所の行の照らし）・`jsonfile`・`oneline`・`graphloops/engine/util.py`（`Reject`・`git`）。`lib/judge_accept.py` は import しない（README の 9.2 で割って消す側のため）。

作り直しの間は `lib/judge_accept.py` の `material_*` を消さない（今の judge が使う）。組み込みで消す。

### 1.6 つなぎ方（graph の側。block には書かない）

- 判定のまとめ（`blocks/judge/`）が 11 本を `include:` で並べる。`depends_on` は目的の固定（purpose）と世界の解（world）の後（今の `material-route` の `depends_on: [purpose-loop, world-finish]` と同じ順）。11 本は互いに依らず、並んで走る。
- `with:` は、`base` ← line が始めの記録から引いた差分の根（今の始めの記録の `diff_base`）、`entry` ← line が始めの記録から引いた出どころの文（今の `due_view` の `record.process.request_entry.origin`。判定から入る run でなければ空）、`lang` ← 始めの記録の `lang`、観点ごとの入力 ← 各設計書が名指す作り手の出力。
- `when:` は、機能を切る run（始めの記録の `features_cut`）で観点を外す時だけ置く。回す条件（今の `CONDS`）は graph に置かない。block が自分で決め、回さない時も素材の状態を返す（10 節）。
- 読み手: diagnose の port `materials`（11 本の `material` の pointer を、判定のまとめが 1 つの json の配列にして渡す）。diagnose は `materialkit.assemble`（2.10）で 15 欄にそろえる。prior-decisions の `material` は、記録された方針の決着済みの論点の出どころでもある（読み手と配線は [prior-decisions.md](prior-decisions.md) の 1.6）。
- 諦めた観点（`status: gave_up`）が 1 本でもあれば、判定の前で line を止める（今の `diagnose_prep` が `materials_given_up` で止めの語 `material`〔`lib/judge_accept.py:305`〕を置いて `go` 偽にした形。`:2862-2866`）。止めるのは diagnose の設計書が決める（読み手の決め。この族は `status` を返すだけ）。
- 報告: 判定のまとめは 11 本の `report` の欄を節「素材」にまとめて line に返してよい。載せるかは line と report の配線の決め（今の報告には素材の節が無く、測れていない素材だけが残りの行に出る）。

## 2 共通の部品 `lib/materialkit.py`

このモジュールの docstring の頭に「素材の観点の族の共通の部品（docs/design/materials.md の 2 節）」と、公開の名の一覧を書く（今の lib の docstring の書き方）。下の「写す元」は今の `lib/judge_accept.py` の行で、関数の中身を写し、名と引数を下のとおりに替える。

### 2.1 定数

- `FILES`: place のファイルの名。`INTAKE = "intake.json"`・`VIEW = "view.json"`・`DIFF = "diff.patch"`・`CHANGED = "changed-files.txt"`・`TREE = "tree.json"`・`ACCEPTED = "accepted.json"`・`MATERIAL = "material.json"` を、モジュールの定数として 1 つずつ置く（`FILES` は名の総称で、変数としては置かない）。
- `PROMPT_FILE = "{name}-prompt-{n}.md"`。
- `STATUSES = ("ran", "skipped", "gave_up", "failed")`、`OK_STATUSES = ("ran", "skipped")`。
- `Rule = collections.namedtuple("Rule", "fields blocks carryable observed")` と `STATUS`・`SILENT_STATUS`・`OBSERVED_STATUS`: 写す元 `:94`・`:122-131`（字のまま）。
- `MATERIALS`: 写す元 `:104-120`（15 の名と注記のまま）。
- `READONLY_MOVED`・`LOCATION_HEAD`・`LOCATION_MARK`: 写す元 `:1739-1741`。
- `SNAPSHOT_FALLBACK_IDENT`: 写す元 `:1749-1750`。
- `LANG_DEFAULT = "the language of the request (the user's language)"`: `{lang}` に入れる既定の英語の文（今の `rolekit.LANG_DEFAULT`「依頼文の言語（利用者の言語）」と同じ意味。README の 5.3）。
- `NA_MODES = ("never", "cond_true", "cond_false", "judged")`: 『条件に当たらない』の扱い（2.7）。

### 2.2 `View`（対象差分の見方）

`@dataclasses.dataclass(frozen=True) class View`: 欄 `repo: pathlib.Path`・`base: str`（引いた commit）・`review_rev: str`（作業ツリーを固めた commit）・`diff_file: str`（`diff.patch` の絶対パス）・`changed_files: tuple[str, ...]`・`changed_files_file: str`・`stat: str`・`commits: int`。`View.empty` は `not changed_files` を返す property。`View.as_dict()` は `view.json` に書く dict（今の `_take_diff` の返りと同じ欄の名。`repo` は字に）。`View.from_dict(repo, doc)` はその逆。

### 2.3 `take_view(place, repo, base) -> View`

写す元 `numstat_totals`（`:1771-1798`）・`_unfrozen`（`:1801-1804`）・`_worktree_tree`（`:1807-1827`）・`_snapshot`（`:1830-1842`）・`_take_diff`（`:1845-1869`）。違いは 2 つ: 差分の根は引数 `base`（空なら HEAD。今は始めの記録の `diff_base`）、書く先は place の `DIFF`・`CHANGED`・`VIEW`。版を固められない・根が引けない時は `Reject`（今のまま）。`numstat_totals`・`worktree_tree`・`snapshot` は公開の名にする（試験が直に呼ぶ）。

### 2.4 作業ツリーの写しと照らし

- `snap_tree(place, repo) -> pathlib.Path`: `TREE` が在れば書き直さずにそのパスを返し、無ければ `accept.tree_state(repo)` を書く。写す元 `snap_tree`（`:1113-1115`）に「在れば書き直さない」を足した物（今は呼び手の `material_route` が `is_file()` で見ていた。`:1977-1978`）。
- `moved_since(place, repo, keys) -> list[str]`: 写す元 `_tree_snapshot`・`_moved_since`（`:1118-1136`）。`keys` は `accept.status_keys(viewpoint.GUARDED)`。

### 2.5 所見の場所の照らし

`where_rows(node)`・`location_problems(reply, repo)`・`location_gap(place, name, reply, repo) -> (拒む文か None, 受ける返答)`: 写す元 `_where_rows`・`_location_problems`・`_location_gap`（`:2463-2502`）。`rolekit.is_last_attempt(rolekit.attempt(place, name))` の回は拒まずに `LOCATION_MARK` を付けて受ける（今のまま）。

### 2.6 回すかの決めと、回さない時の埋め

- `Due = collections.namedtuple("Due", "run why")`。
- `entry_skip(noun: str) -> Due`: `Due(False, f"判定から入る run の周（入口の印が在り、修正がまだ 1 ファイルも入っていない）のため、{noun}を起こさない")`（今の `request_entry` と `not_request_entry`・`*_due` の訳の字。`:1374-1382`・`:1512-1516`）。
- `fill_entry(entry: str, requests: int) -> dict`: 判定から入る run で回さない素材の状態。写す元 `_fill_one` の 1 つ目の枝（`:1937-1941`）の字。`origin` は port `entry`、件数は依頼の行の数（観点が `request` を持たない時は 0 を渡し、件数の句「この周の判定に届く人の依頼 0 件」を出す代わりに「この周の判定に届く人の依頼の件数は渡されていない」にする。自分で決めた。10 節）。
- `fill_na(na_reason: str, why: str) -> dict`: `{"status": "not_applicable", "reason": f"{na_reason}（{why}）"}`（写す元 `:1944-1945`）。
- `fill_not_run(why: str) -> dict`: `{"status": "not_run", "reason": why}`。
- `intake(viewpoint, place, repo, values: dict, unreadable: str = "") -> dict`: intake の node の本体。順:
  1. `unreadable` が空でなければ（script が port を読めなかった）、`status: failed`・`reason: f"入力が読めない（{unreadable}）——役を起こしていない"`・素材は全部 `fill_not_run(reason)` にして `INTAKE` に書き、`{due: False, reason}` を返す。
  2. `take_view(place, repo, values["base"])`。`Reject` なら `status: failed`・`reason: f"対象差分が取れない（{e}）——役を起こしていない"`・素材は全部 `fill_not_run(reason)`（今の `material_route` の `:1972-1975` と `fill_materials` の `:2677-2679` を合わせた字）。
  3. `due = viewpoint.due(view, values)`。`due.run` が偽なら `status: skipped`・`reason: due.why`・素材は `viewpoint.fill(view, values, due)`。
  4. `due.run` が真なら `snap_tree(place, repo)`。`status` はまだ決めない（`null`）。
  5. 返りの `reason` は、回さない時は 1〜3 の訳、回す時は `due.why`（例 prior-decisions は「先行議論の突合は run ごとに 1 回回す…」）。`INTAKE` に `{"values": values, "view": view.as_dict() か null, "due": {"run", "why"}, "status", "reason", "fill": {素材: 状態} か null}` を書き、`{"due": due.run, "reason": due.why か訳}` を返す。
  - 例外は捕まえない（1〜3 で落ちうる所は全部 `Reject` か値で受ける。それ以外の例外は不具合として node を落とす）。

### 2.7 『条件に当たらない』の扱い

`na_mode(viewpoint, view, values) -> (mode, why)`:

- `viewpoint.NA == "never"` → `("never", "")`。
- `viewpoint.NA == "cond"` → `ok, why = viewpoint.applies(view, values)`。`ok` が偽なら `("cond_false", why)`。真で `viewpoint.judged_na(view, values)` が真なら `("judged", why)`。ほかは `("cond_true", why)`。

写す元 `_na_note`（`:2053-2075`）の決め方。今の `na_self_ok`（graph が名乗れると宣言した物）は 11 本のどれも持たないので（`MATERIAL_NODES`、`:1633-1695`）、扱いを足さない（自分で決めた。10 節）。文は md の共通の断片 `material-na`（3.2）に移し、Python は扱いの語と理由の字だけを返す。

### 2.8 素材の欄の照らし

`check_record(name, wanted: tuple, mats: dict, mode: str) -> list[str]`: 写す元 `check_record`（`:2528-2560`）。照らすのは `wanted`（`viewpoint.MATERIALS`）の素材だけ。拒みの文は次の字にする（今の文の「ノード {nid}」を「観点 {name}」に、graph への宣言の求めを外した）:

- 返答に素材が無い: `f"観点 {name} は走ったが素材 '{mat}' が返答に無い"`
- 流用の語: `f"素材 '{mat}'（観点 {name}）は今の周に走ったのに {st}——自分で見たと主張しない値は走らなかった観点に機械が書く。今の周の判定を書け"`
- `mode` が `cond_true` で `not_applicable`: `f"素材 '{mat}'（観点 {name}）は条件が真で走ったのに not_applicable——機械が持つ事実と食い違う"`
- `mode` が `never` で `not_applicable`: `f"素材 '{mat}'（観点 {name}）は走ったのに not_applicable——この観点は『条件に当たらない』を名乗れない。今の周の判定を書け"`
- 知らない status: `f"素材 '{mat}' の status が不正: {st!r}"`
- status ごとの要る欄（`STATUS` の `fields`。`found` は `count`・`detail`、`clean` は `checked`、`carried_over` は `from_round`・`reason`、`not_applicable`・`awaiting_human`・`not_run` は `reason`）: `count`・`from_round` が整数でなければ `f"素材 '{mat}'（{st}）の '{f}' は数で書け"`、ほかの欄が空でない字か配列でなければ `f"素材 '{mat}'（{st}）に '{f}' が要る（何を見たかを書け）"`（今の `:2551-2559` の字）。

`material_from_findings(src) -> dict`: 写す元 `:2505-2512`（hygiene の写し方）。

### 2.9 受け付け `accept(viewpoint, place, repo, raw: str) -> dict`

`rolekit.accept_round(place, viewpoint.NAME, raw, take)` を呼び、`{ok, done, reason}` を返す。`take(reply)` の中は 4 節の順。`accept.guard` で `Reject` を `{ok: False, reason}` に写す（今の `material_take` の `core_accept.guard(run)`）。通れば `ACCEPTED` に `{role, reply, materials}` を書く。

### 2.10 出口と読み手の口

- `finish(viewpoint, place, pointer) -> dict`: finish の node の本体。`pointer` は script が渡す `ports.pointer`（place の中のパスから Archon の pointer を作る口）。順:
  1. `INTAKE` を読む。読めなければ `status: failed`・`reason: f"{INTAKE} が読めない（{e}）"`・素材は全部 `fill_not_run(reason)`。
  2. `INTAKE` の `status` が `failed` か `skipped` ならその `status`・`reason`・`fill` をそのまま使う。`reply` は null。
  3. `ACCEPTED` が在れば `status: ran`・`reason: ""`・その `reply` と `materials`。
  4. 無く、`rolekit.given_up_reason(place, NAME)` が空でなければ `status: gave_up`・`reason` はその字・素材は全部 `fill_not_run(f"{reason}——素材集めの役の返答を受けられなかった")`（今の `fill_materials` の `:2684-2686` の字）。
  5. どれでもなければ `status: failed`・`reason: f"観点 {NAME} の役の返答を受けた記録が無い（ループが落ちたか、走っていない）"`・素材は全部 `fill_not_run(reason)`。
  6. `MATERIAL` に書き、`{ok: status in OK_STATUSES, status, reason, material: pointer(パス), report: report_lines(doc) + viewpoint.report_lines(doc)}` を返す。書けなければ `material: None` と `reason` に書けない訳を足し、`status: failed`。
  - 素材の名は `viewpoint.MATERIALS` の順に並べる。
  - finish は落ちない: 1〜6 の外の例外も捕まえて `status: failed` と訳で返す（今の `world_finish` と同じ決まり。今の落とし穴の一覧 `docs/plans/2026-10-13-capabilities/pitfalls.md` の K1・K13: 返りの node が落ちると line が先へ進めない・落ちた段の訳が消える）。
- `report_lines(doc) -> list[str]`: 素材ごとに 1 行 `f"素材 {名}: {status}" + 尾`。尾は `found` なら `f"（{count} 件）: {oneline(detail)}"`、`clean` なら `f"（見た所: {oneline(checked)}）"`、ほかは `f"（{oneline(reason)}）"`。素材を書かない観点（purpose-review）は `f"観点 {NAME}: {status}"` の 1 行と `reason`（空でなければ）。
- `read(path) -> dict`: 読み手の口。`material.json` を読み、`role`（字）・`status`（`STATUSES` のどれか）・`materials`（dict）を確かめ、外れれば `ValueError`（訳を名指す）。返りは中身の dict。
- `assemble(docs: list, *, local_checks: dict | None, base: str, commits: int) -> dict`: 読み手（diagnose）が 15 欄にそろえる口。写す元 `fill_materials`（`:2654-2693`）。違いは、受けた素材を place のファイルでなく `docs`（`read` の返りの並び）から取ることと、回さない・諦めた素材の埋めは各 `docs` の `materials` に既に在ること（block が埋めて返すため）。`base_determination`・`fix_closure`・残りの `not_run` の埋めは今のまま。

### 2.11 指示の値の共通の口

`prompt_inputs(viewpoint, place) -> (values: dict, when: dict, n: int)`: prep の本体。`INTAKE` から `View` と `values` を戻し、次を足して返す。

- `values`: `viewpoint.values(view, ports_values)` に、`lang`（port が空なら `LANG_DEFAULT`）、`rejection`（拒否が在る時だけ。`rolekit.rejects_text(rolekit.rejected(place, NAME))`）、`na_why`（`mode` が `never` でない時だけ。2.7 の `why`）を足した物。
- `when`: `viewpoint.when(view, ports_values)` に、`rejected`（拒否が 1 件以上）と `na_never`・`na_cond_true`・`na_cond_false`・`na_judged`（2.7 の `mode` に当たる 1 つだけが真）を足した物。
- `n`: `rolekit.attempt(place, NAME)`。

`values` に入れるのは、差し込むと決まった段落の中に在る差し込み口の値だけにする（入らない段落の中の口の値は渡さない。自分で決めた。11 節の未確認）。

## 3 指示の md の共通の形（`prompts/<観点>.md`）

### 3.1 節の並び

どの観点の md もこの順に書く。観点が持たない節は飛ばす。

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: 拒否の控えが 1 件以上。断片の中の `{rejection}` ← 2.11。
2. `{shared:role-<種>}`（役の定義。種は 5.2 の表の「役の定義」。今の md が役の定義を持たない観点は置かない）。
3. `{shared:query-rule}`（外への検索の決まり）— web か外のコマンドを持つ役だけ。断片の中の `<!-- if spawns -->` には、役が Agent の道具を持てば `spawns: true`、持たなければ `false` を渡す。
4. 役の 1 段落（決まった文）: 新しい会話で起きていること・この役が何だけをするか・何を渡していないか。
5. 道具の段落（決まった文）: 道具の名と、Bash の sandbox と網。works-gh を使う役は `{shared:works-gh}`。作業ツリーを読む役は `{shared:material-readonly}`。
6. `## Materials` と、観点の差し込み口（今の `MATERIAL_HOLES`〔`:1722-1736`〕の穴ごとに 1 行。値の出どころは 5.2）。今は材料を別のファイル（`material-<役>-brief.md`）に描いて役に Read させたが、新しい形では値を指示に直に入れる。大きい値（差分の本文）は、Read を持つ役にはパスを、持たない役には本文を入れる（今の `file:` の穴と同じ分け）。
7. 観点の仕事の節（決まった文。今の「元の graphloops の指示書」の段を英語にした物）。
8. `{shared:material-status}`（素材の書き方）— 返答に `material` の欄を持つ観点だけ。
9. `## Whether you may write not_applicable` と `{shared:material-na}` — 返答に `material` の欄を持つ観点だけ。
10. `## Where to point`、観点ごとの前置きの文（在れば。例「この役の返答には where の欄が無い。…」）、`{shared:material-where}`。
11. 言語の 1 文（決まった文）: 観点の人に見せる欄を名指し、`{lang}` で書けと言う。key・enum の値・識別子・パス・コマンド・引いた字はそのまま。
12. 結びの 1 文: `Return only JSON that matches the output schema.`

md と値に、`$` の直後に英字か `{` が続く字（例 `$HOME`・`$ARTIFACTS_DIR`）を置かない。Archon は `prompt:` に入れた値の中の `$…` を置き換え直す（`lib/rolekit.py` の `with_reject` の docstring「前の周の値の差し込みで貼ると実行基盤が文の中の $… を置き換え直す」）。今の md が頼っていた `$ARTIFACTS_DIR` の置き換えは、prep が絶対パスを入れる形に替える。

### 3.2 共通の断片（`blocks/.shared/prompts/`。この族の PR が足す）

土台が置く断片（`rejected`・`query-rule`・役の定義 5 本）のほかに、この族が次の 5 本を足す。名と本文はここで決める（README の 11.1 の「同じ断片を 2 本の PR が同時に足さない」）。

`material-status.md`（今の 11 本の「素材（material）の書き方」の段。11 本で 4 通りに割れていた尾〔review-record.py の名指し〕を外した）:

```markdown
How to write `material`: `status` is one of the following.
- `found`: you found something. Give `count` (an integer) and `detail`.
- `clean`: you looked in this run and found nothing. Say in `checked` what you looked at.
- `not_applicable`: the viewpoint does not apply. Give `reason`. Whether you may write it is in the section on `not_applicable`.
- `awaiting_human`: it waits for a person to start something. Give `reason`.
- `not_run`: it should have been done, but you skipped it. Give `reason`.

`carried_over` (reusing an earlier round) is written by the machine for viewpoints that did not run. You ran, so write what you found in this run; an answer that says `carried_over` is rejected.
```

`material-na.md`（今の `_na_note` の 4 つの枝。`:2053-2075`）:

```markdown
<!-- if na_never -->
This viewpoint has no condition under which it does not apply, so the acceptance step rejects `not_applicable`. Write what you saw as `found` or `clean`; if you could not check, write `not_run` with the reason.
<!-- end na_never -->
<!-- if na_cond_true -->
The condition of this viewpoint holds for this run ({na_why}), so the acceptance step rejects `not_applicable`. Write what you saw as `found` or `clean`; if you could not check, write `not_run` with the reason.
<!-- end na_cond_true -->
<!-- if na_cond_false -->
The condition of this viewpoint does not hold for this run ({na_why}). You may write `not_applicable`, with the reason in `reason`.
<!-- end na_cond_false -->
<!-- if na_judged -->
The condition of this viewpoint holds for this run ({na_why}), but none of the facts the machine holds raise it, so the acceptance step takes your judgment. If you read the diff and judge that the viewpoint does not apply, you may write `not_applicable`, with the reason in `reason`.
<!-- end na_judged -->
```

`material-where.md`（今の 11 本の「所見の場所の書き方」の段の芯。観点ごとの前置きは各 md に残す）:

```markdown
Write the `<path>:<line>` of a location (`where`) as a line number in the current file in the working tree. Do not write a line number inside the diff (patch) file: lines of the diff are not lines of the file, and a person cannot open that place. For a finding you saw in the diff, if you can read files, Read the file and confirm the line before you write it; if you cannot read files, do not write a line number you cannot confirm, and write the path with a function name or similar instead. The acceptance step rejects a location that points outside the lines of an existing file and asks for the answer again.
```

`material-readonly.md`（今の md の道具の段の尾「対象の作業ツリー・HEAD・枝・git が無視するファイルを 1 文字も変えるな（受け付けは…比べ、変わっていれば拒む。同じ時に別の素材集めの役も走っている）」）:

```markdown
Do not change a single character of the target's working tree, HEAD, branch, or the files git ignores. The acceptance step compares the working tree with the snapshot taken before you were started, and rejects your answer if anything changed. Other roles may be running on the same working tree at the same time.
```

`works-gh.md`（今の prior-decisions・local-review・external-standards・procedure-trace と、並行 PR の `pr-check.md` が写している段。並行 PR の block〔parallel-pr〕も同じ断片を使う。parallel-pr の設計書はこの名を使い、断片を足さない）:

```markdown
To read GitHub pull requests and repositories, run the read-only command `works-gh` by its bare name, as a single command (for example `works-gh pr view 12 -R OWNER/REPO`). Only `pr list`, `pr view`, and `pr diff` (each with `-R <OWNER/REPO>`) and `repo view <OWNER/REPO>` pass, and only this form runs outside the sandbox. If you call it as `gh`, through a variable that holds its path, with a pipe, `&&`, `;`, or a command substitution, or with a variable assignment in front of it, it runs inside the sandbox and cannot reach the network. Read issues, searches, and web pages with WebFetch and WebSearch. The wrapper stops any gh command that writes.
```

（本文の中の「`$(…)`」は「a command substitution」と言い換えた。`$(` は 3.1 の置き換えの字ではないが、md に `$` を置かない決まりを単純に保つため。）

### 3.3 Python が持つ物

README の 5.3 のまま。この族では:

- 材料の値: `view` から（`repo`・`base`・`review_rev`・`diff_file`・`changed_files`・`changed_files_file`）、port から（依頼の行・目的の文）。配列の値は `json.dumps(値, ensure_ascii=False, indent=1)`（今の engine の描き方 `Renderer` と同じ字。例の run の `loop.request_wheres` の描き方）。
- md と受け付けが同じ字を持つべき値: 観点ごとに `src/viewpoint.py` の定数か `lib/materialkit.py` の定数から入れる。
- 却下の理由の文（日本語）: 2.8・4 節の文と、観点の `before`・`after` の文。

## 4 受け付けの共通の流れ（`materialkit.accept` の `take`）

今の `material_take`（`:2573-2624`）の順を写す。

1. 返答が JSON のオブジェクトでなければ拒む: `"返答が JSON のオブジェクトでない"`。
2. 作業ツリー: `moved_since(place, repo, accept.status_keys(viewpoint.GUARDED))` が空でなければ拒む: `f"{READONLY_MOVED}素材集めの役は対象の作業ツリー・HEAD・枝・git が無視するファイルを変えてはいけない（{'・'.join(moved)}）。同じ時にほかの役も走りうるので、変えたのがこの役とは限らない"`。今の `_peers_note`（同じ時に回すほかの役を `material-route.json` から名指した）は、block がほかの観点を知らないので、決まった句に替えた。
3. 観点の前の照らし: `why, got, give_up = viewpoint.before(view, values, reply, place)`。`why` が在れば `{"ok": False, "reason": why, "give_up": give_up}` を返す（local-review のレンズの照らし。今の `:2593-2599`。ほかの観点は `(None, reply, False)` を返す）。
4. 所見の場所: `location_gap(place, NAME, got, repo)`。拒む文が在れば拒む。
5. 観点の後の照らし: `why = viewpoint.after(view, values, got, place)`。在れば拒む（今の `post_check` の 5 つ。`:2603-2613`。`accept.in_repo(repo)` の中で呼ぶ）。
6. 素材: `mats = viewpoint.materials_of(got)`、`errs = check_record(NAME, viewpoint.MATERIALS, mats, mode)`（`mode` は 2.7）。在れば拒む: `"素材の欄が記録の決まりに合わない: " + "; ".join(errs)`。
7. `ACCEPTED` に `{"role": NAME, "reply": got, "materials": mats}` を書き、`{"ok": True, "reason": ""}`。観点が控えを足す時（local-review の見ていないレンズの控え）は `viewpoint.after_accept(got, place)` を呼ぶ（持たない観点は何もしない）。

諦め: 3 回目の拒否で `done`（`rolekit.GIVE_UP_AFTER`）。3 で `give_up` が真なら 1 回目で `done`。run は止めず、finish が `status: gave_up` を返す。

## 5 観点の宣言（`blocks/<観点>/src/viewpoint.py`）

### 5.1 宣言の欄

どの観点も、次の名を全部定義する（無い名を共通の口が既定で埋める形にしない。実装者が決める所を残さないため）。

- `NAME: str` — 観点の名（`"prior-decisions"` など）。
- `MATERIALS: tuple[str, ...]` — 書く素材の名（`materialkit.MATERIALS` の中の物。順は今の `MATERIAL_NODES` の `materials` の順）。
- `GUARDED: bool` — AI の node が `mutates_checkout: false` を持つか（Archon が節の前後の git status を照らす役か）。真なら作業ツリーの照らしの欄から `porcelain` を外す（`accept.status_keys`。今の YAML の accept の `with: {status_guarded: …}`）。
- `NA: str` — `"never"` か `"cond"`。
- `NA_REASON: str` — `NA == "cond"` の時の『条件に当たらない』の訳（今の `MATERIAL_NODES` の `na_reason`）。`"never"` の時は `""`。
- `def due(view, values) -> materialkit.Due` — 回す条件。
- `def fill(view, values, due) -> dict` — 回さない時の素材の状態 `{素材の名: 状態}`。
- `def applies(view, values) -> materialkit.Due` — `NA == "cond"` の時の当たる条件。`"never"` の時は `raise NotImplementedError`（呼ばれないことを試験が見る）。
- `def judged_na(view, values) -> bool` — 条件が真でも役の判定を受けるか。gate-efficacy のほかは `False` を返す。
- `def values(view, values) -> dict` — md の観点の差し込み口の値（2.11 が共通の値を足す）。
- `def when(view, values) -> dict` — md の観点の段落の真偽（2.11 が共通の真偽を足す）。
- `def before(view, values, reply, place) -> tuple` — 4 節の 3。
- `def after(view, values, reply, place) -> str | None` — 4 節の 5。
- `def after_accept(reply, place) -> None` — 4 節の 7。
- `def materials_of(reply) -> dict` — 受けた返答から素材の状態（今の `MATERIAL_NODES` の `writes` の `materials.*` と `material_from_findings`）。
- `def report_lines(doc) -> list[str]` — 2.10 の共通の行の後ろに足す、観点の報告の行。足さない観点は `[]`。

引数の `values` は intake が読んだ port の値の dict（鍵は入力の名）。

### 5.2 11 本の宣言の元（今のコードの事実）

各観点の設計書は、下の今の事実から宣言を書く（1 run は 1 周なので、`round` は 1、前の周の値はどれも無い。今の `due_view`〔`:1337-1365`〕と同じ見方）。「起こし方」は今の YAML の錨、「役の定義」は今の md の頭の役の名、「穴」は今の `MATERIAL_HOLES`。

- prior-decisions: 起こし方 `net_closed_launch`（Read・Grep・Glob・Bash・WebSearch・WebFetch。網は閉じ、works-gh だけ外へ）／状態の照らし 無し／役の定義 investigator／素材 `prior_decisions`／回す条件 いつも（`prior_decisions_due` は 1 周目に真）／`NA` never／後の照らし 無し／穴 `inputs.cwd`・`record.base`・`loop.changed_files`・`loop.request_wheres`／足す入力 `request`。設計は [prior-decisions.md](prior-decisions.md)。
- purpose-review: 起こし方 `read_launch`（Read・Grep・Glob）／状態の照らし 有り／役の定義 inspector／素材 無し（返答は `verdict`・`reason`・`findings`。今は `process.purpose_review` にだけ書いた）／回す条件 目的の出典が「③writer の要約」（`purpose_review_due`。1 周目なのでほかの枝は効かない）／`NA` never（`material` の欄が無いので素材の照らしは無い）／後の照らし `purpose_findings_cited`（`:2401-2410`。版は `view.review_rev`）／穴 `out.p0.purpose.purpose_text`・`inputs.review_rev`・`inputs.cwd`／足す入力 `purpose`。
- local-review: 起こし方 `net_closed_launch` に Skill・Agent・`skills: [code-review, simplify, security-review]`・`plugins: [pr-review-toolkit@works-local]`／状態の照らし 無し／役の定義 無し（今の md の頭は外への検索の決まりの塊だけ）／素材 `local_review`／回す条件 判定から入る run でない（`not_request_entry`）／`NA` never／前の照らし 見ていないレンズの印（`diverted.mark_unseen`）と必須のレンズ（`_lens_gap`、`:2435-2460`。プラグインが無ければ `give_up`）／後の照らし `local_review_covers_lenses`（`:2186-2220`）／受けた後 `diverted.LENS_FILE` の控え／穴 `loop.diff_file`・`record.base`・`loop.changed_files_file`・`inputs.review_md`・`?inputs.repo_review_md`・`node.skills`（`LOCAL_REVIEW_SKILLS`〔`:1697-1706`〕に条件 `security_surface_touched` の評価を足した物）。
- consistency-bypass: 起こし方 `read_launch`／状態の照らし 有り／役の定義 inspector／素材 `consistency`・`bypass`／回す条件 判定から入る run でない／`NA` never／穴 `loop.diff_file`・`loop.changed_files`・`record.base`・`inputs.review_md`・`?inputs.repo_review_md`・`inputs.review_rev`・`inputs.cwd`。
- hygiene: 起こし方 `allowed_tools: []`（道具なし）／状態の照らし 有り／役の定義 cold-reader／素材 `hygiene`（`material_from_findings`）／回す条件 判定から入る run でない／`NA` never（返答に `material` の欄が無いので、3.1 の 8・9 を差し込まない）／穴 `section:inputs.review_md#コード衛生観点`（REVIEW.md の見出しの節の本文）・`file:loop.diff_file`（差分の本文）。
- external-standards: 起こし方 `net_closed_launch`／状態の照らし 無し／役の定義 investigator／素材 `external_standards`／回す条件 判定から入る run でない（`external_standards_due`。1 周目に真）／`NA` never／後の照らし `external_rankings`（`:2146-2157`）／穴 `loop.diff_file`・`loop.changed_files`・`inputs.review_md`・`out.p0.purpose.purpose_text`・`out.p0.purpose.known_weaknesses`・`inputs.cwd`／足す入力 `purpose`。
- procedure-trace: 起こし方 `net_closed_launch`／状態の照らし 無し／役の定義 investigator／素材 `procedure_trace`／回す条件 判定から入る run でなく、変更ファイルに手順書・スクリプト・CI 定義が在る（`procedure_trace_due` と `touches_procedures`〔`PROCEDURE_PATTERNS`、`:1303-1304`〕）／`NA` cond（当たる条件 `touches_procedures`。`NA_REASON` は「対象差分に手順書・スクリプト・CI 定義の変更が無い」）／穴 `loop.diff_file`・`loop.changed_files`・`inputs.review_md`・`inputs.cwd`。
- gate-efficacy: 起こし方 `test_run_launch`（網は開き、作業ツリーの外に写しを作る）／状態の照らし 無し／役の定義 無し（今の md の頭は外への検索の決まりの塊だけ）／素材 `gate_efficacy`／回す条件 `gates` が `merge` でなく、判定から入る run でない（`gate_efficacy_due`。差分の形の申告 `touches_gates` は機械が真に倒す）／`NA` cond（当たる条件 `gates_touched` はいつも真。`judged_na` は `gate_signals`〔`:2027-2032`〕が空の時に真）／回さない時の埋め `gates` が `merge` なら `GATES_MERGE_WHY`（`:1946-1949`）／後の照らし `gate_arms_all_red`（`:2165-2183`）／穴 `loop.diff_file`・`loop.changed_files_file`・`record.base`・`inputs.cwd`・`loop.mutation_decl.text`（`mutation_decl`、`:2083-2096`）／足す入力 `gates`。
- test-double-fidelity: 起こし方 `test_run_launch`／状態の照らし 無し／役の定義 無し（外への検索の決まりだけ）／素材 `test_double_fidelity`／回す条件 判定から入る run でない（`touches_external_seams` は機械が真に倒す）／`NA` cond（`seams_touched`。いつも真）／穴 `loop.diff_file`・`loop.changed_files_file`・`inputs.cwd`。
- main-path-observation: 起こし方 `test_run_launch`／状態の照らし 無し／役の定義 無し（外への検索の決まりだけ）／素材 `main_path_observation`／回す条件 判定から入る run でない（`touches_user_path` は真に倒す）／`NA` cond（`user_path_touched`。いつも真）／後の照らし `main_path_observed`（`:2138-2143`）／穴 `loop.diff_file`・`loop.changed_files_file`・`inputs.cwd`。
- provenance: 起こし方 `test_run_launch`／状態の照らし 無し／役の定義 無し（外への検索の決まりだけ）／素材 `provenance`／回す条件 判定から入る run でない（`provenance_due`）／`NA` never／穴 `loop.diff_file`・`record.base`・`inputs.cwd`。

`inputs.review_md`・`inputs.repo_review_md` の値は `materialkit.review_md_paths(repo)`（写す元 `review_md_paths`、`:1765-1770`。工場の観点の正本 `lib/REVIEW.md` の絶対パスと、対象の根の `REVIEW.md` の絶対パスか空）から入れる。`lib/REVIEW.md` は README の 9.3 で共通の断片へ移す物だが、作り直しの間は今の置き場を指す（（未確認）: 組み込みで移した後の置き場は、REVIEW.md を移す PR が決める）。

## 6 script の node（4 本の雛形）

どれも uv の頭の宣言（`# /// script` … `# ///`、`requires-python = ">=3.12"`、`dependencies = []`）を持ち、`sys.dont_write_bytecode = True` を import より前に置き、`blocks/.shared/` と `lib/` と block のフォルダ（`src` を引くため）を `sys.path` に足す（足し方は土台の `ports` の口に従う。world の scripts と同じ）。docstring に node の役を 1〜2 行で書く。

- `scripts/intake.py`: port を 1 つずつ `os.environ.get("INPUTS_<名>")` の字のままで読み（名を組んで読まない。README の 4.2）、`ports` の口で値にする（`text` の form は `ports.text`、`json` の form は `ports.json(字, "<schema>")`）。読めない（`ValueError`）なら `unreadable` に `f"{名}: {e}"` を入れる。`ports.returns(materialkit.intake(viewpoint, ports.place(), Path.cwd(), values, unreadable))`。
- `scripts/role_prep.py`: `values, when, n = materialkit.prompt_inputs(viewpoint, ports.place())`、`text = prompt.render(viewpoint.NAME, values, when)`、`(place / materialkit.PROMPT_FILE.format(name=viewpoint.NAME, n=n)).write_text(text, encoding="utf-8")`、`ports.returns({"prompt": text})`。落ちる時は落とす（10 節）。
- `scripts/role_accept.py`: `ports.returns(materialkit.accept(viewpoint, ports.place(), Path.cwd(), os.environ.get("INPUTS_REPLY", "")))`。返りは `{ok, done, reason}` の 3 欄だけに絞る。
- `scripts/finish.py`: `ports.returns(materialkit.finish(viewpoint, ports.place(), ports.pointer))`。

`ports` の口の名（`text`・`json`・`place`・`pointer`・`returns`）は土台の PR が決める。ここでは world.md と同じ呼び方で書いた。

## 7 観点の設計書の書き方

各観点の `docs/design/<観点>.md` は world.md の形で、次を書く。

- 頭: 何の話か・決めたこと・持ち主に求めること。
- 1 block の全体: 1.1 役、1.2 port（1.2 の共通の 3 つと足す入力・出力の 5 欄）、1.3 node の並び（1.3 の雛形に入れる名と `<起こし方>`・`<返答の形>`）、1.4 place（1.4 の共通の名と観点だけの控え）、1.5 コードの置き場（`src/viewpoint.py` の宣言の全部の名と中身、観点だけの `src/` の関数の写す元）、1.6 つなぎ方（`with:` の各入力の作り手と、出力の読み手）。
- 2 node の設計シート（AI の node 1 つ。README の 6 節の 9 項）。
  - 組み立ての順は 3.1 の並びに沿い、各節の値の出どころ（`view` の欄か port か定数か）と、段落の条件を書く。
  - md の本文を英語で全部書く。
  - 描いた骨組みは本物の run の `judge/material-<観点>-brief.md` と `commands/material-<観点>.md` から、run の id を書く。
- 3 受け付け（4 節の 3・5 の観点の照らしと、その拒みの文）。
- 4 元の works と graphloops の同じ場面（9 節の族の形の差は繰り返さず、観点だけの差）。
- 5 単独で呼ぶ（命令の形）。
- 6 試験（8 節の共通の試験に足す物と、守る keep-essence の番号）。
- 7 未確認。

## 8 試験（族の共通）

- `lib/tests/test_materialkit.py`（族の部品の試験。この族の PR が作る）。元にする今の試験（`lib/tests/test_judge_accept.py`）:
  - `MaterialCase.test_diff_sees_files_hidden_by_index_marks`・`test_sparse_checkout_out_of_cone_files_are_not_changes`（`take_view`）。
  - `test_material_role_changed_the_tree_rejected`・`test_test_caches_count_like_any_change`・`test_tagged_environment_folder_is_still_watched`（`moved_since`）。
  - `test_route_keeps_the_first_tree_record`（`snap_tree` が在る写しを書き直さない）。
  - `test_location_beyond_the_file_is_sent_back_then_marked`（`location_gap`）。
  - `test_accept_rules`（`check_record`。拒みの文の「ノード」を「観点」に替える）。
  - `test_na_note_for_each_kind_of_node`（`na_mode` が 4 つの語を返す。文は md の断片へ移したので、文の字でなく語と理由を照らす）。
  - `test_materials_mark_not_run_and_given_up`・`test_materials_of_an_entry_run_are_not_applicable`（`finish` の 4・5 と `fill_entry`）。
  - `DueCase.test_view_values`（`View` の欄）。
  - `test_material_file_names_round_trip` は写さない（今の `material-<役>.json` の名の往復を見る試験で、place の名は族の部品の定数 1 つになった）。
  - `test_tree_change_names_the_peer_roles` は写さない（ほかの役を名指す文をやめた。4 節の 2）。代わりに「拒みの文が『変えたのがこの役とは限らない』を言う」を照らす。
  - `test_stop_turns_every_role_off` は写さない（止めの記録を読まない。README の 4.3）。
  - 足す: `finish` が 6 つの道（読めない intake・failed・skipped・ran・gave_up・記録なし）で `status` と素材を返し、どの道でも落ちない。`read` が形の外れた `material.json` を訳つきで落とす。`assemble` が今の `fill_materials` と同じ 15 欄を返す（受けた素材・回さない素材・諦めた素材・`base_determination`・`fix_closure`）。`prompt_inputs` が拒否の無い回に `rejection` を値に入れず、`never` の回に `na_why` を値に入れない。
- 観点の block ごとの `tests/blocks/<観点>/`:
  - `test_<観点>.py`: 使い捨ての `ARTIFACTS_DIR`（始めの記録を置かない）と git のリポジトリで、port の値だけを渡し、`intake` → `role_prep` → 台本の返答 → `role_accept` → `finish` を子のプロセスで回し、`material.json` と出力の 5 欄を照らす。拒まれる返答 3 回で `gave_up` になる道も回す。
  - `test_viewpoint.py`: `src/viewpoint.py` の宣言が 5.1 の名を全部持ち、`MATERIALS` が `materialkit.MATERIALS` の中に在り、`NA == "never"` の観点の `applies` が `NotImplementedError` を上げる。
  - `test_prompts.py`: 指示の比べ（README の 11.4）。1 つ目の commit は、日本語の md を今の `commands/material-<観点>.md` から作り（`$<観点>-prep.output.<欄>` を `{<欄>}` に替えた字）、本物の run の値で組んだ字が、今の md に同じ値を入れた字と同じになることを照らす。材料のファイル（今の `material-<観点>-brief.md`）は 1 つ目の commit でも prep が今と同じ字で書き、今の run の物と同じ字になることを照らす（各観点の設計書が値と照らし方を書く）。2 つ目の commit（英語。材料を指示に入れ、材料のファイルを無くす）でこの 2 つの試験を消し、新しい指示と古い指示（md と材料のファイル）を並べた物を PR に載せる。
  - `blocks/<観点>/fixtures/standalone.stubs.yaml`（8 節の終わりの命令で回す）: `fixture.inputs` は port の値だけ（pointer を持たない。README の 7.1 の 4）。AI の node だけを台本の返答で差し替え、script は本物を走らせる（`--exec-code`）。`reached` に `finish`。
  - `blocks/<観点>/fixtures/gave-up.stubs.yaml`: 役が 3 回拒まれ、`finish` が `status: gave_up` を返し、run は `completed`。
  - 回す条件を持つ観点は `skipped.stubs.yaml`: 役を起こさず `finish` が `status: skipped` を返す。
- 形の検査（README の 7.1）は族の block にもそのまま当たる。族だけの yes/no の検査は足さない（5.1 の名の有無は `test_viewpoint.py` が見る）。
- 終わりの条件の命令（PR ごと。どれも 1 モジュールずつ回す。手元で全部の試験は回さない）:

```sh
uv run --isolated python3 -m unittest lib.tests.test_materialkit
uv run --isolated python3 -m unittest discover -s tests/blocks/<観点の package の名> -t .
uv run --isolated python3 -m unittest tests.layers.test_block_shape
uv run --isolated python3 -m unittest tests.blocks.<観点の package の名>.test_prompts
```

  - `<観点の package の名>` は観点の名の `-` を `_` にした字（例 `prior_decisions`）。unittest は `-` を持つフォルダを package として import できないので、試験のフォルダは `tests/blocks/<観点の package の名>/` に置く（自分で決めた。10 節）。8 節のほかの所の `tests/blocks/<観点>/` もこの名と読む。

  - fixture は `tests/blocks/<観点>/test_fixtures.py`（今の `tests/workflows/test_report.py::FixtureCase` と同じ形。`archon.tree([...], workflows=<blocks の根>)` の中で `archon workflow test works-factory-<観点> --json` を回し、全部の fixture が通り、`archon validate workflows --json` の誤りと警告が 0）が回す。`tests/archon.py` が `blocks/` を置ける形は土台の PR が作る。
  - 本物の単独の run を 1 回（README の 11.2。費用のかかる試しは聞かずに回してよい）。

keep-essence の 12 の仕組みのうち、この族が担う物は無い（README の 10 節の割り当てに素材の観点は出てこない）。族が守るのは keep-essence に数えられていない今の能力（作業ツリーの照らし・所見の場所の照らし・素材の欄の照らし・回さない素材の理由つきの埋め・諦めで判定の前に止める材料）で、上の試験がそれを見る。

## 9 元の works と graphloops の同じ場面（族の形）

元の works の `works/blk-material/`（1 つの block に 11 本の役。`route`・`prep`・`accept`・`collect` の 4 本の script を役の名の `with:` で使い回した）から、工場は judge の中に直に置き換えた（#76）。新しい形はその間を取り、役ごとに block を分けて、共通の部品を lib の 1 モジュールにする。工場に無い物・違う物と、その訳:

- 共有の記録（盤面）が要否を決める形（元の `mat-route` は、盤面の上でどの観点の node が回せる状態かを読んだ）: 工場は値を渡す見方 `due_view` で、元の条件を 1 run = 1 周の値で評価した（#76。`lib/judge_accept.py:1337` の docstring）。新しい形は条件を観点の block に置く（graph の `when:` でなく。10 節）。
- 包みの切符（元の `adapter` の入力。Bash を持つ役の起こす前に切符を確かめた）: 工場は sandbox の `filesystem` と起こす直前の包み `fence.py` に替えた（#293・#309。今の YAML の `net_closed_launch` の注記）。新しい形も同じ埋めを使い、block は切符を持たない。
- 並んで走るほかの観点の 1 本が盤面を止めた（run を止める印を置いた）後に、残りの観点の支度が `stopped` を返して役を飛ばす形（元の `peer-stop` の筋書き）: 工場は `material-route` が止めの記録を読む形にした（今の `workflows/judge/fixtures/material-peer-stop.stubs.yaml`）。新しい形は止めの記録を読まず、line の `when:` が回すかを決める（README の 4.3）。並んで走るほかの観点が止まっても、この観点は最後まで走る。
- 支度が出力の在りかを見て役を飛ばす形（元の prep の返り `already`）: 工場に無い（（未確認）: 意図の記録なし）。Archon の resume が済んだ node を回し直さないので、新しい形も持たない。
- 目的の文の入力（元の `purpose_file`）: 工場は判定の置き場の `purpose.json` を読んだ。新しい形は要る観点だけが port `purpose` で受ける。
- 素材の出口（元の `collect` は `{ok, reason}` だけを返し、素材は盤面に在った）: 新しい形は観点ごとに `material.json` を返し、15 欄にそろえるのは読み手（`materialkit.assemble`）。

graphloops の `blocks/review-loop/` と `graphs/review-loop.json` は、素材の節を 1 本の graph の節として持ち、engine が条件（`cond`・`applies_cond`・`na_self_ok`）と書き先（`writes`）を宣言から読む。工場の `MATERIAL_NODES` はその写し（`lib/judge_accept.py:1632`）。新しい形は宣言を観点の block の `src/viewpoint.py` に置く。graphloops の engine が持つ周をまたぐ値（前の周の素材の流用 `carried_over`・前の周の修正の申告 `prev.p3.fix.*`・`loop.last_material`）は、工場が 1 run = 1 周（持ち主の決め carry）と決めて使わないので、新しい形も持たない。

この族が両方より良く、残す物: 役を起こす前と後の作業ツリーを機械が比べる・所見の場所の行が作業ツリーのファイルに在るかを機械が照らす（元の works の受け付けの足し）・判定から入る run で回さない素材に出どころつきの理由を書く・諦めた観点を判定の前で止める材料を返す。

## 10 自分で決めた事

- 回す条件と回さない時の埋めを、graph の `when:` でなく観点の block の intake に置く。訳: 回さない素材にも「なぜ回さないか」の状態（`not_applicable` と出どころ・`not_run` と条件）を書くのは、その観点の意味（`na_reason` と条件の訳）を知る所だけができる。graph が `when:` で飛ばすと素材の状態が欠け、読み手（diagnose）が 11 本の条件と訳を知ることになる（README の憲法の 3 と 4 に触れる）。README の 4.3 の「回すかは graph の when: が決め」は、block を include するか（機能を切る run）の決めとして残る。
- 共通の入力 `entry` を足す。訳: 判定から入る run かは始めの記録の事実（差分が空で依頼が在る）で、9 本の観点の回す条件と埋めの訳の字（出どころ）がそれを使う。観点の block が差分と依頼から推し直すより、line が 1 回決めた値を配る方が、出どころの字（依頼のファイルのパス）も今と同じになる。README の 8.1 の例「hygiene は base text だけ」は例で、この入力を足しても外れない。
- 観点が `request` を持たない時の `fill_entry` の件数の句を「この周の判定に届く人の依頼の件数は渡されていない」にする。訳: 件数のためだけに `request` を 9 本に足すと、読まない入力が増える（README の 1.2 の P）。
- `na_self_ok` の扱いを持ち込まない。訳: 11 本のどれも持たない（`MATERIAL_NODES`）。足すのは要る観点が出た時。
- prep は `with:` を持たず、却下の段落を place の控えから組む。訳: Archon は `with:` の値の中の `$x.output.y` を置き換え直すので、却下の理由（役の返答を引いた字を含みうる）を `$LOOP_PREV` で運ばない。また 控え（`rejects-<観点>.json`）は resume を跨いで回を数える正本（`rolekit.attempt` の docstring）で、`$LOOP_PREV` の値と 2 つの源を持たない。world は `with:` で理由を受けるが、組む中身は同じ控えなので、振る舞いは同じ。
- prep が落ちた時は node を落とす。訳: 今の `material_prep.py` は落ちた時に「material を not_run（この理由）で返せ」という指示の文を Python で組んで役に渡していた。憲法の 2（Python は指示の文を持たない）に触れる。新しい形では落ちうる所（port の読み・差分の取り・作業ツリーの写し）を intake が先に済ませて値と状態で返すので、prep の落ちは不具合で、黙って役に回さない（持ち主の決め `no-silent-loosen`）。finish は「役の返答を受けた記録が無い」で返す。
- intake は place の中のファイルを消さない。訳: 単独の run では place が run directory の根で、Archon の物も同じ所に在る。新しい run の place は空で、resume では拒否の控えと作業ツリーの写しを残すのが正しい（今の「最初の姿を残す」と回の数え）。
- 拒みの文のうち、ほかの役を名指していた句（`_peers_note`）を決まった句に替え、graph への宣言を求めていた句（「名乗れる理由を graph に宣言しろ」）を外した。訳: block はほかの観点も graph も名指さない（憲法の 3）。役が読んで直せるのは返答だけ。
- place のファイルの名を、観点の block の `src/` でなく族の部品 `lib/materialkit.py` の定数に置く。訳: 11 本で同じ名で、書くのも読むのも族の部品の関数。ほかの block はこの名を知らず、`material` の pointer で受ける（README の 4.4 の「ほかの block が読む物は pointer で」は守る）。
- 試験のフォルダの名は観点の名の `-` を `_` にした字（`tests/blocks/prior_decisions/`）。訳: unittest は `-` を持つフォルダを package として import できない。README の 3 節の `tests/blocks/<block>/` は、Python の package の名に直した字と読む。
- 族の部品の PR は `lib/` に新しいモジュールを足す。README の 11.1 の「lib/ は読むだけで変えない」の例外で、11.1 の「素材の観点は、共通の部品と 1 本目を 1 本の PR にし」が求める物。今あるモジュールは変えない。

### 10.1 実装で決めた事（族の部品と 1 本目の PR）

- `LANG_DEFAULT` を `lib/materialkit.py` に置かない。`prompt_inputs(viewpoint, place, lang)` の 3 つ目の引数に、port の字を言語の値にする口（block の script が渡す `prompt.lang`）を受ける。訳: 土台が `lang` の既定の文を共通の断片 `blocks/.shared/prompts/lang-default.md` に置き、`prompt.lang` だけが読む形にした（README の 13 章。憲法の 2: AI に届く決まった文は md だけ）。`lib/` が `.shared` の口を import すると層が逆になる。入る字は 2.1 の文と同じ。
- `prompt_inputs` は `rejection` をいつも（拒否が無い回は空の字で）渡し、`na_why` も `NA_PARAGRAPH` の観点にはいつも（`never` の回は空の字で）渡す。訳: 11 節の未確認の答え。土台の `prompt.render` は選ばれない段落の中の差し込み口も数え、値が無ければ落ちる（`tests/blocks/shared/test_prompt.py::SlotCase.test_slots_in_unselected_paragraphs_still_need_values`。値を渡せば「使われない値」には数えない）。同じ md の中に `<!-- if x -->` と `<!-- if not x -->` を両方置ける（`ParagraphCase.test_if_and_if_not_select_and_drop_marks`）。2.11 の終わりの「入らない段落の口の値は渡さない」は、この形に替えた。
- 宣言の名 `NA_PARAGRAPH: bool` を 5.1 に足す。真なら `prompt_inputs` が `na_why` と `na_never`・`na_cond_true`・`na_cond_false`・`na_judged` を足す。訳: 返答に `material` の欄を持たない観点（hygiene・purpose-review）の md は `{shared:material-na}` を差し込まないので、いつも足すと `prompt.render` が「when の名が md の段落に無い」「使われない値」で落ちる（残りの 10 本の設計書の書き手の指摘）。どの観点の md が断片を入れるかは観点だけが知るので、宣言に置く。
- `fill_entry(entry, requests)` の件数を渡さない時は `None` にする（2.6 の「0 を渡す」を替えた）。訳: 本当に 0 件の時と、件数を渡されていない時を分ける（同じ指摘）。
- 回す時の訳の共通の口 `normal_run(noun) -> Due` と、判定から入る run でない時だけ回す決め `not_entry_due(values, noun) -> Due`（`entry` が在れば `entry_skip(noun)`、無ければ `normal_run(noun)`）を `entry_skip` の隣に足す。訳: 9 本の観点が同じ条件（今の `not_request_entry`）を持つので、訳の字を観点ごとに書かせない（同じ指摘）。
- `review_md_paths(repo, lib_dir=None)` を公開の名にする（5.2 の終わり）。`lib_dir` の既定はこのモジュールの在る `lib/`。訳: 写す元 `judge_accept.review_md_paths(lib_dir, repo)` の、試験が一時のフォルダを指せる形を残す（同じ指摘）。
- prep の script は `prompt.render` と自分の書き込みでなく `prompt.emit(NAME, values, when, n)` で組む。訳: `blocks/.shared/AGENTS.md` の「prep は `prompt.emit` だけで組む」。書く先の名 `<NAME>-prompt-<n>.md` は `PROMPT_FILE` と同じ字。
- intake の 4（回す時の作業ツリーの写し）で `Reject` が出たら（HEAD が引けないなど）、`status: failed`・`reason: f"役を起こす前の作業ツリーの姿が取れない（{e}）——役を起こしていない"` で返す。訳: 2.6 の「落ちうる所は全部 `Reject` か値で受ける」を 4 にも当てた。
- finish の落ちた道の素材の埋めは、観点の宣言そのものが壊れていても落ちない（素材を名指せなければ空）。訳: 2.10 の「finish は落ちない」。
- 観点の入力 `request` の形は、block の `schemas/` に写さず、土台の共通の形 `json(shared:request.schema.json)` で名指す（1.2 の「`blocks/world/schemas/request.schema.json` を字のまま写す」を替えた）。訳: 土台が依頼の行の形を `blocks/.shared/schemas/request.schema.json` に 1 つ置き、world もそれを名指す。同じ名の形が pack の 2 か所に在ると形の検査（README の 7.1 の 5）が赤。
- 役の定義の断片 `role-investigator`・`role-judge` は中に `{shared:query-rule}` を持つので、その役の md は 3.1 の 3 を置かない（11 節の未確認の答え。`spawns` の真偽は役の定義の中の段落のために渡す）。
- 筋書き `gave-up.stubs.yaml` は、Archon の dry-run が輪を 1 周で終えるので、拒否 1 回で出口まで届くことだけを見る。3 回で諦めて `status: gave_up` を返す数えと、出口の `status` の照らしは `tests/blocks/<観点>/test_<観点>.py` が見る（筋書きは node の返りの欄を照らせない。world の筋書きと同じ分け）。

## 11 未確認

- 土台の `prompt.render` が、差し込まないと決まった段落の中の差し込み口を「使われない値」に数えるか。この族は数えない（入る段落の中の口だけに値を渡す）前提で 2.11 を書いた。数える形なら、`prompt_inputs` は `na_why` と `rejection` をいつも渡す形に替える。
- 土台の役の定義の断片 5 本の名。この族は `role-investigator`・`role-inspector`・`role-cold-reader` と書いた。土台の名が違えば、その名に合わせる。役の定義の断片が外への検索の決まりを含むなら、3.1 の 3 を外す（今の `lib/agents/investigator.md` は検索の決まりを中に持つが、world.md は検索の決まりを別の断片 `query-rule` にした）。
- 土台の `ports` の口の名（6 節）と、`lib/` と block のフォルダを `sys.path` に足す形。
- 判定のまとめが 11 本の `material` の pointer を 1 つの json の配列にする組み方（Archon の `with:` で配列を組めるか。組めなければ judge のまとめの script の node が組む）。
- 工場の観点の正本 `lib/REVIEW.md` を共通の断片へ移した後の、`inputs.review_md` の値（5.2 の終わり）。
