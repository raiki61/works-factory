<!-- coldwrite:skip ASF の役が読む issue の本文（plan ブロック）。語は works-factory の docs/design.md の「語」の節で定義 -->
# plan: 計画のブロックを中身ごと作る（workflows/plan/ と、それだけが使う lib/ の部品と試験）

works-factory は、修正依頼を受けて確かめ済みの変更と報告を返す工場を、Archon（AI の工程を YAML で書いて回す道具）の上に作り直しているリポジトリ。前の形の「今の works」（公開リポジトリ raiki61/claude-plugins の `works/`。移す元の版は `pack.json` の `works.commit` = `2aa7c66cf7abe1fe09699ac2942d107123214168`）は、判定・計画・修正・確かめ・報告をつないだ工場で、その能力を 1 つも落とさずに、線（`workflows/line/`。ブロックを並べる 1 本の工程）・8 つのブロック（`workflows/<名>/`）・助け手（`lib/`。Archon を知らない Python）に移している。この issue は、そのうちのブロック `plan` を、フォルダの中身ごと 1 つの PR で作る。8 つのブロックは別々の run で同時に作られ、線とはブロックの返りの約束（`docs/design.md` の「ブロックの返りの約束」）だけでつながる。元のファイルは `https://raw.githubusercontent.com/raiki61/claude-plugins/2aa7c66cf7abe1fe09699ac2942d107123214168/<パス>` で読める（本文の「元」の欄の `<パス>`）。ASF は Archon の作者が作った、issue から PR までの工程の束（`docs/design.md` の「語」）。

## 読む物

- 根の `AGENTS.md`（リポジトリの形・E8〜E11・E13・E14・E18）、`workflows/AGENTS.md`（E1・E2・E4〜E7・E12・E16・E17）、`lib/AGENTS.md`（E3）、`tests/AGENTS.md`。決まりの番号 E1〜E18 の中身はそれらの文書に在る。
- `docs/design.md`: 「ブロック」の `plan` の節・「ブロックの返りの約束」の `plan` の返り・「能力の棚卸し」の `plan・plan-review` の行・「受け入れの一覧」・「Archon の分かっていること」と未決 U1〜U8・「作りの順」の段 2 の `plan` の個別の行。
- `docs/plans/2026-10-12-lib-port.md` の「移し方」1〜6（この issue で `lib/` に持ってくる部品も同じ移し方に従う）。
- `docs/owner-decisions.md` のうち本文が引く決め（`superset`・`no-narrow`・`impact-first`・`close-in-round`・`planner-talk`・`dirty-area`・`concept-home`・`clean-whole`・`model-effort`・`persona`・`unit-sessions`・`reuse-results`・`injected-map`・`io-in-output-format`・`lib-port-as-is`・`lang-neutral`）。
- Archon の振る舞いは、止めた Archon（`docs/design.md` の「語」。ASF と同じ源 `coleam00/Archon` の commit `d97d00ef15cce4b15d39e42635e4e86996ec1351` を `bun` で起こし、自分の工程は置かずに `--workflow-source` で読ませる。持ち主の決め `archon-same-as-asf`）の文書 `packages/docs-web/src/content/docs/`（特に `guides/script-nodes.md`・`guides/authoring-workflows.md`・`guides/loop-nodes.md`・`reference/cli.md` の dry-run と `workflow test`）で確かめる。ASF の工程は同じ commit の `.archon/workflows/sdlc/`（本文の `W`）。
- ブロックの分（元の works。パスは `works/` から）:
  - 計画: `blk-plan/blk-plan.yaml`（節 plan-snap・plan-ripple・plan-loop（plan-prep・plan・plan-accept）・collect。plan の役の `output_format` は 260〜510 行）・`blk-plan/lib/planblk.py`（HEAD・ITEMS_RULE・REUSE_RULE・prep・take・with_plan_fields・revise_take・collect・make_ripple・replan_ripple・verify_part・prescription_section・world_part）・`blk-plan/lib/ripple.py`・`blk-plan/fixtures/`（pass・plan-rejected・give-up）
  - 修正案の指示書の元: `.shared/core/gl-prompts/prompts/review-loop/p2.fix_plan.md`
  - 案の直し: `.shared/core/replan.py`（REPLAN_ASK・REPLAN_REJECT・prep・_take・_plan_errors・gate の決まり）
  - 構造の目: `blk-structure/blk-structure.yaml`（段 A・構造の目の輪・collect。段 B は eyes の物で、このブロックでは作らない）・`blk-structure/commands/structure-eye.md`・`blk-structure/scripts/stage_a.py`・`eye_prep.py`・`eye_accept.py`・`collect.py`・`blk-structure/lib/context.py`・`eye.py`・`blk-structure/design-row.schema.json`
  - 深さ: `darkfactory/lib/depth.py`（`decide_doc`・`unit_depth`）
  - 受け付けの写しの決まり: `.shared/core/graphloops/rules/review-loop.py` の `fix_plan_covers_units`（3077 行）
  - 試験: `tests/test_blk_plan.py`・`test_ripple.py`・`test_replan.py`・`test_blk_structure.py`・`test_structure_eye.py`・`test_plan_fields.py`
  - 段と模型: `.shared/core/stage-models.json`（`blk-plan/plan` = plan_writer）・`.shared/core/agents/blind-judge.md`（構造の目）
- ASF: `W/plan/archon-plan.yaml`（`returns: plan`・`outcome_field: ready`・ready: false も正しい終わり・`mutates_checkout: false`）と `W/plan/fixtures/blocked.stubs.yaml`・`W/implement/fixtures/*.stubs.yaml`（構造つきの差し替え）。

## 目的と引き継ぐ能力

判定（judge）が切った単位を、直す前に設計として固める。単位が名指すファイルを機械で実測して構造の目（道具なしの別の会話）が「直しが構造を汚すか」を判定し、修正案の役が項目ごとに書いてよい範囲・受け入れテスト・定石と構造の行への従うか外れの訳を書き、受け付けが機械で照らし、波及の一覧（変える名の呼び出し元と試験）を機械で出す。案の直し（fix の裁定の後の 1 度）も同じブロックを `ruling` の入力つきで差し込む。事前審査（plan-review）との往復は線が持ち、このブロックは 1 回の案を作って返す。

能力の棚卸しの行（元のパスは 2aa7c66c の `works/` から）:

- 構造の目 — `blk-structure`・`structmark.py`・`concepthome.py` → plan・`commands/structure-eye`（段 A の実測は `lib/stage_a.py`・`lib/context.py`、目の支度と受け付けは前提の `lib/eye.py`、実測の CLI は前提の `lib/measure.py`）
- 修正案 — `blk-plan`・`planmarks.py` → plan・`commands/fix-plan`・`lib/plan_fields`（ファイルは `lib/planmarks.py`。lib-port で入っている）
- 波及の一覧 — `blk-plan/lib/ripple.py`・`impact.py` → plan・`lib/impact`（どちらも`docs/plans/2026-10-12-blocks/prereq.md` の issue で入る）
- 案の直し — `replan.py` → plan（裁定の後の 1 度。`lib/replan.py`）
- 単位ごとの深さ — `darkfactory/lib/depth.py` → 返り `depth`（`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/depth.py` の `decide_doc`。上げ直しは線）

受け入れの一覧（review-graph の節）のうち、このブロックが持つ物:

- `p2.fix_plan` 全部の単位を案に入れ、生まれる物（adds）・消す物（removes）・狭める能力（narrows）を先に書く
- `p2.human_gate` の材料: narrows の行の「狭めない案を探した結果」と関所の項目の推し（gatemarks の欄）を受け付けで照らし、案の指し札に置く（関所を開くかは plan-review と線）
- 構造の目（keep-essence の「独立設計」と並ぶ、修正の前に案が汚くなる一手かを見る目。持ち主の決め `clean-whole`・`dirty-area`）
- 世界の解（keep-essence の 12。定石の行ごとに従うか外れの訳を書かせ、欠けを拒む）
- 当たる試験の選び（keep-essence。波及の一覧が呼び出し元と試験を引く。持ち主の決め `impact-first`）

## 作る物

### ブロックのフォルダ `workflows/plan/`

- `works-factory-plan.yaml`（工程の名も `works-factory-plan`。E9。`interactive:` は書かない。人の関所はこのブロックに無い）
  - `inputs:`（値は線の `with:` が JSON の字で渡す。既定は「無い」を表す字にそろえる）: `start`（指し札。既定 `""`）・`units`（配列。既定 `"[]"`）・`judgment`（指し札。既定 `""`）・`world`（指し札か null。既定 `"null"`）・`spec`（指し札か null。既定 `"null"`）・`review`（指し札。往復の 2 回目から。1 回目は線が空の字 `''` を渡す。既定 `""`。空の字と `null` のどちらも「事前審査がまだ無い」と読む）・`ruling`（文字列の配列。案の直しの時だけ空でない。既定 `"[]"`）・`conflicts`（指し札か null。案の直しの時だけ。約束に無い入力なので既定 `"null"` で宣言し、線が渡す前から動くようにする。約束に足す文は下の「人が入れる前提の直し」1）。始めの記録の欄（`policy_md`・`thickness`・`test_cmd`・`tdd_suite`・`base_rev`・`lang`）は入力にせず `start` から読み、無ければ空として読む。
  - 節（順に）:
    1. `round`（`script: round`・`runtime: uv`・`timeout: 1728000000`）: この include の周の番号 k を決め、置き場 `plan/r<k>/` を作る。k は run の置き場の中の `plan/r*/` の数 + 1（同じ run の中で往復と案の直しを通して数える。返り `round` の正本）。入力 `ruling` が空でなければ形 `replan`、空なら `plan`。返り `{round, mode, dir}`。
    2. `structure-measure`（`script: structure_measure`）: 単位の目録 `units` のうち `paths` が空でない単位だけを `plan/structure/<鍵>/units.json` に書き（judge は開いた単位を全部返し、`paths` が空の単位も在る。前提の `stage_a.read_units` は空の `paths` を形の誤りとして全部を落とすので、測る前に外す。外した単位の id は同じフォルダの `skipped-units.json` に書き、修正案の役の材料に「構造の目が見ていない単位」として載せる）、`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/stage_a.py` の `read_units`・`measure_unit` と `lib/context.py` で段 A の実測をして `structure.json` と 0 バイトの `design.jsonl` を置く。鍵は単位の目録と対象の HEAD の sha256 の頭 12 字で、同じ鍵の `structure-state.json` が在れば測り直さず目も起こさない（持ち主の決め `reuse-results`: 入力が同じ時だけ使い回す。往復の 2 回目で構造の目を起こし直さない）。案の直し（形 `replan`）は、修正の後でも作業ツリーの差分を鍵に入れず、1 回目の案の実測と目の行をそのまま使う（今の works も構造のブロックは修正案の前に 1 度だけ走り、案の直しは同じ控えを読んだ。わざとそうする。直した後の構造は eyes が測る）。方針の文書のパスは始めの記録の `policy_md`（無ければ空）。返り `{structure_file, design_file, eye, reused}`。実測が落ちても節は落とさない（今の works と同じ。structure.json の status: failed と reason）。
    3. `structure-eye-loop`（`loop_group`・`max_iterations: 3`・`fresh_context: false`・`until_bash: test $structure-eye-accept.output.done = true`・`timeout: 1728000000`。`when: "$structure-measure.output.eye == true"`）:
       - `structure-eye-prep`（`script: eye_prep`）: 前提の `lib/eye.py` の `prep(structure_file)`。返り `{prompt, prompt_file, attempt}`
       - `structure-eye`（`command: structure-eye`・`model: opus`・`effort: high`・`allowed_tools: []`・`settingSources: [user]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`mutates_checkout: false`・`idle_timeout: 1728000000`。役の節ごとの `settingSources`・`sandbox` は元の `blk-structure.yaml` の値を写す。元に `context:` は無いので書かない。`output_format` は元の `blk-structure.yaml` の structure-eye の物（rows の行 unit_id・verdict・faces・evidence・reason・chosen・rejected・chosen_reason・route・undecided_because））
       - `structure-eye-accept`（`script: eye_accept`）: `eye.accept(structure_file, design_file, reply)`。返り `{ok, done, give_up, reason, attempt}`
    4. `structure-state`（`script: structure_state`・`trigger_rule: all_done`）: 前提の `lib/structmark.py` の `write(<鍵のフォルダ>, status, reason, design_file, wall_s)` で構造の目の控え `structure-state.json` を書く（目が飛んだ・落ちた・3 回拒まれた周は status: failed と理由。今の works の `blk-structure/scripts/collect.py` と同じ分け方）。返り `{state_file}`。返り `structure` の指し札の先はこの `structure-state.json`（いつも書くので在って空でない。`structmark.read`・`dirty`・`plan_section` はこの控えから読む）。設計の行は同じフォルダの `design.jsonl`（今の works の design-row の形。目が行を出さなかった周は 0 バイトのまま）で、控えの `design_file` がそれを名指す。ほかのブロックが行を読む時は、指し札のフォルダのこの名のファイルを開く（約束への書き込みは「依存」の H5）。
    5. `ripple-units`（`script: ripple_units`）: 前提の `lib/ripple.py` の `for_units(repo, <単位の id>)` で単位の名の波及を `plan/r<k>/ripple-units.json` に書く（修正案の役が案を書く前に読む）。形 `replan` では作らない。
    6. `plan-loop`（`loop_group`・`max_iterations: 3`・`fresh_context: true`・`until_bash: test $plan-accept.output.done = true`・`timeout: 1728000000`。元の `plan-loop` と同じ）:
       - `plan-prep`（`script: plan_prep`）: 機械が貼る材料を 1 つのファイル `plan/r<k>/brief-<attempt>.md` に組む（持ち主の決め `injected-map`: 役に貼る節は script の節が組む）。返り `{brief, attempt}`。中身は下の「修正案の役に渡す材料」。
       - `plan-writer`（修正案の役。`command: fix-plan`・`model: opus`・`effort: medium`・`allowed_tools: [Read, Grep, Glob, WebSearch, WebFetch]`・`settingSources: [user]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`mutates_checkout: false`・`idle_timeout: 1728000000`。`settingSources`・`sandbox` は元の `blk-plan.yaml` の plan の役の値。元に `context:` は無い。`output_format` は元の `blk-plan.yaml` の plan の役の物を字のまま（`plan[]` の項目の欄と works の欄 route・route_why・tests・rewrite_tests・refactor・allowed_paths・out_of_scope・structure、narrows の行の関所の欄）。`description` の印 `works-node: …` は包みの物なので書かない）
       - `plan-accept`（`script: plan_accept`）: 下の「受け付け」。返り `{ok, done, give_up, reason, attempt}`。拒否の数え方は前提の `lib/rolekit.py` の `with_done(plan/r<k>/, "plan", out)`・`rejected`・`given_up_reason`・`GIVE_UP_AFTER`（3）をそのまま使い（拒否の控えは `plan/r<k>/` の下）、次の `plan-prep` は `rejected` の最後の理由を頭に貼る。3 回目の拒否で `done: true`・`give_up: true`（輪を `max_iterations` で落とさずに抜けるため。今の works の `blk-plan/blk-plan.yaml` の `plan-loop` の `until_bash` の注記と同じ）。
    7. `ripple-items`（`script: ripple_items`・`trigger_rule: all_done`）: 受け付けた案の欄で `ripple.build(repo, fields)` を `plan/r<k>/ripple.json` に書く。形 `replan` では直した項目を差し替えた欄で作り直す（今の works の `planblk.replan_ripple`）。案が無い（諦めた）周は `{"items": [], "error": "<理由>"}` を書く（指し札の先をいつも空でなくする）。
    8. `plan`（返す節。`script: plan_collect`・`trigger_rule: all_done`）: 下の「返りの約束」の欄を組む。**この節は落ちない**（線は落ちた返す節の先へ進めない）: 中で起きた誤りは全部捕まえ、`ready: false` と、在って空でない置き場の札のファイル（`plan/r<k>/plan-fields.json` に `{round, fields: []}`、`structure-state.json` に status: failed と理由、`ripple.json` に `{"items": [], "error": "<理由>"}`）と、`depth: []`・`round` を返して 0 で終える（返りは `output_format` に合う）。理由は `plan/r<k>/collect-error.txt` に書く。行き止まり（`lib/planfile.py` の `stuck_reason` が空でない）の周は役を起こさずに `ready: false`。深さは前提の `lib/depth.py` の `decide_doc(fields, <単位の id>, forced=<始めの記録の thickness>, checked=<始めの記録の test_cmd か tdd_suite が空でない>)` を `{unit_id, depth, why}` の並びにする（why は理由の並びを「・」でつないだ 1 文）。
  - 節の id `plan` は役の節とぶつかるので、役の節の id は `plan-writer`、返す節の id を `plan` にする（約束の「返す節 `plan`」）。
- `commands/structure-eye.md`: 元 `blk-structure/commands/structure-eye.md`。差し込みを `$structure-eye-prep.output.prompt` のまま使う（Archon の書き方で書かれている）。
- `commands/fix-plan.md`: 元 `.shared/core/gl-prompts/prompts/review-loop/p2.fix_plan.md` の本文（「この工程が在る理由」「やること」1〜6）と、`planblk.HEAD["plan"]` が足していた役の定義（読むだけ・道具・作業ツリーを変えない）・`planmarks.HEAD`・`ITEMS_RULE`・`REUSE_RULE`・`concepthome.PLAN_RULE`・`gatemarks.HEAD["p2.fix_plan"]`（これらは lib の定数なので、指示書には写さず `plan-prep` が材料のファイルの頭に貼る。指示書は「材料のファイル `$plan-prep.output.brief` を Read で読み、その指示に従え」と返し方だけを持つ）。engine の雛形（`{{record.units}}` など）と「no の整数で指せ」は、単位の id（`units[].id`）を字のまま書く形に直す。
- `scripts/`: `round.py`・`structure_measure.py`・`eye_prep.py`・`eye_accept.py`・`structure_state.py`・`ripple_units.py`・`plan_prep.py`・`plan_accept.py`・`ripple_items.py`・`plan_collect.py`。どれも入力を読み、lib の関数を呼び、`boundary.returns` で返すだけ（E4）。**script の名を lib のモジュールの名と同じにしない**（script のフォルダが `sys.path` の頭に来るので、`import stage_a` が自分を読む。だから段 A の script は `structure_measure.py`）。
- `fixtures/`（下の「試験」）。

#### 修正案の役に渡す材料（`plan-prep` が組む。元の `planblk.prep` の plan の枝と同じ節）

1. 役の定義（`planblk.HEAD["plan"]` 相当の lib の定数と `gatemarks.HEAD["p2.fix_plan"]`）
2. 前の回の受け付けの拒否の理由（在れば。`rolekit.rejected` の最後の行。指示書に字のまま貼らずファイルを名指す 1 行にするのは今の works の `planblk.py` の `REVISE_PROMPT` の周りの注記と同じ。`rolekit.REJECT_LINE` の文）
3. 案に入れてよい単位と必ず入れる単位（`lib/planfile.py` の `plan_slots(judgment)`。開いた単位に 1 から番号を振り、役は今の works と同じく番号で単位を指す。番号と id の対応は `plan/r<k>/slots.json` に置き、受け付けが id に戻す）と、`units` の paths・summary、判定の見立て・問いの台帳・先行例（`judgment` の中身から）。`paths` が空で構造の目が見ていない単位（`skipped-units.json`）もここに書く
4. 観点の正本のパスとリポジトリの版（元の `p2.fix_plan.md` の 1 行「リポジトリ: … BASE: … 観点の正本: {{inputs.review_md}}」と同じ。観点の正本は`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/REVIEW.md` で、パスは `boundary.lib_root() / "REVIEW.md"` を script が組んで材料に書き、役が Read で読む。narrows の比べの基準「移行退行の棚卸し（BASE 能力インベントリ）」はこの文書に在る。BASE と読む版は始めの記録の `base_rev`）
5. 判定の処方の節（`judgment` の単位ごとの処方。今の works の `planblk.prescription_section` と同じ見出しと頼み `PRESCRIPTION_HEAD`・`PRESCRIPTION_ASK`）
6. 前の run の失敗の行（始めの記録に前の失敗の行が在れば `carry.prior_section` の形。今の始めの記録の欄に無いので、無ければこの節を作らない）
7. 構造の目の行（`structmark.plan_section(<鍵のフォルダ>)`）
8. 世界の解の行（`world` の行を `worldmark.section` と `worldmark.PLAN_ASK`）
9. 単位の名の波及の一覧（`ripple.units_section`）
10. 判定の裏取りの申し送り（`judgment` の指し札のファイルと同じフォルダの `judge-verify.json` を `planblk.verify_part` に渡す）・並行 PR の外した範囲（同じフォルダの `pr-excluded.json` を名指す `EXCLUDED_HEAD` の行）。どちらも judge が外に出す約束の隣のファイル（「依存」の H5）で、この名で開く。無ければその節を作らない
11. ライブラリの文書の節（前提の `lib/libdocs.py` の、盤面を受けない口。無ければ PR の本文の「使いたかった物」に書き、この節を作らない）
12. 仕様（`spec` が在れば、要件と受け入れテスト。受け入れテストは案の `tests` に入れる物として見せる）
13. 往復の 2 回目から: 前の周の案（自分の置き場の一番新しい `plan/r*/` の `p2.fix_plan.json` と `plan-fields.json`）と事前審査の指摘（`review` の中身。今の works の `p2.plan_review` の返答の形で、項目の状態は持たない）と、このブロックが組んだ項目の状態（開いた・閉じた・保留。下の「受け付け」6 の前の段）。頼みは今の works の直しの役（plan-revise）と同じ「開いた項目を直し、block ごとに答え（block_answers）を書き、閉じた項目は変えない」。`review` の中身は今の works の `p2.plan_review` の返答の形（「依存」の H5）。
14. 案の直し（形 `replan`）: 直す項目（`ruling` の id）と、その項目の承認済みの形（前の周の案）と、申し出と裁定の文（`conflicts` の中身のうち、その項目の行）だけ。頼みは `replan.REPLAN_ASK`。

#### 受け付け（`plan-accept`。拒否の理由は全部を 1 回で並べる）

1. 形の崩れ（dict でない・plan が配列でない。`planblk._plan_malformed`）
2. 単位の網羅（`lib/planfile.py` の `fix_plan_covers_units` と `not_allowed`。写しの rules と同じ）: 役の返した番号を `slots.json` で id に戻し、直す義務の単位（`_owed_units`: 開いた単位から、人に諮っている fork の問いの出どころと depends を除いた物）が全部どれかの項目にちょうど 1 度入る・開いていない単位と知らない番号が無い（入れてよい no の一覧を理由に添える）。形 `replan` では、返す項目が渡した項目に限られ、各項目の `unit_keys` が承認済みの物と字のまま同じ（`lib/planfile.py` の `_plan_errors`。`replan` の REPLAN_REJECT）
3. 狭めない案を探した結果（`gatemarks.narrow_gaps`）と関所の項目の推しの形（`gatemarks.recommend_gaps`）
4. 項目の works の欄の欠けと誤り（`planmarks.gaps(reply, repo, exists=)`。受け入れテストが既に在るかは、形 `replan` では始めの記録の base_rev の木で引く）
5. 構造と世界の解の行への答え（`planmarks.structure_gaps(plan, [planmarks.design_need(structmark.dirty(<鍵のフォルダ>)), worldmark.need(<world の行>)])`。今の works の `planrange.answer_tables` と同じ表を、`planrange` を使わずに structmark と worldmark を直に呼んで組む）
6. 往復の 2 回目から（項目の状態はこのブロックが自分で組む。`review` の指し札には求めない）: 受けた `review` は届くたびに `plan/r<k>/review/p2.plan_review.json` に写して周ごとのフォルダに残し、これまでの周の案（`plan/r*/p2.fix_plan.json`）と受けた review の全部から、今の works の `converge` の控え（`converge.read` の形）を `lib/planfile.py` の `converge_record(dir)` で組み直す（項目ごとに開いた・閉じた（block が無く案が変わっていない）・保留（同じ block が続いた）。決め方は `converge._item_states`・`converge.decide` と同じ）。その上で、block への答えの欠けと誤り（`converge.split` と、`lib/planfile.py` の `answer_gaps`）と、閉じた項目を変えていない（`lib/planfile.py` の `splice`。項目の同じさは `converge.item_hash`。今の works の `revise_take` の CLOSED_REJECT）
7. 通れば: 番号を id に戻した返答を `planmarks.split(reply, repo, base_tests=<修正前の版のテストの中身>)` で works の欄と分け、`plan/r<k>/` に今の works と同じ形のファイルを書く（「依存」の H5。新しい入れ物を作らない）:
   - `plan-fields.json`: 今の works の `planmarks.save` が書く形 `{round, fields}`（形 `replan` では、直した項目を差し替えた欄の並びと、`amended` に直した項目の核の欄 `planmarks.CORE_KEYS`。今の works の `planmarks.amend` と同じ）。返り `plan` の指し札の先。
   - 同じフォルダの `p2.fix_plan.json`（役の返答から works の欄だけを外した物。今の works の盤面の `p2.fix_plan` の出力の形に、narrows の行の関所の決め手の欄（`gatemarks` の欄）を外さずに残す。plan-review がその欄で修正前の関所を組むため。2 往復目からは役の `block_answers` も）: `plan-fields.json` と合わせて 1 つの修正案で、外に出す約束の一部。plan-review・fix・eyes は `plan` の指し札のフォルダのこの名のファイルだけを開いてよい（約束への書き込みは「依存」の H5）。今の works は決め手の欄を `gate-marks.json` に分けて置いたが、ここでは分けない（同じ欄を 2 か所に置かない）。
   - このブロックの中だけが読む横のファイル（今の works が盤面に別のファイルで持っていた物）: `slots.json`（番号と id）・`replan.json`（形 `replan` の時。今の works の `replan.TRIP_FILE` の行の形 `item`・`old`・`new`・`contract_changed`（`planmarks.contract_diff`）・`widened`（`planmarks.widened`））。関所を開くかは plan-review と線が決めるので、ここでは事実だけを置く。

作業ツリーが変わっていないかの照らし（今の works の snap と `accept.tree_moved`）は役の節の `mutates_checkout: false` に替わる（Archon が節を落とす。E7・持ち主の決め `declared-io`）。

### lib/ に持ってくる部品（このブロックだけが使う物）

盤面に届く能力の扱いは 2 つの形だけ: (a) 継ぎ目の直し（持ってきたファイルの中の、盤面・Archon・持ってこない部品への 1 つの呼び出しを、引数か lib/ のモジュールの呼び出しに替える。関数の名とほかの行は変えない）、(b) 書き直し（ほとんどが盤面の読みの関数は、元の関数の名のまま、値かファイルのパスを引数で受ける形で、新しい lib/ のファイルに書き直す。docstring に元の `<パス>:<行>` を書き、試験は元の試験の場合を写す）。どちらも PR の本文に 1 つずつ並べる。

- `works/.shared/core/replan.py` → `lib/replan.py`（lib-port の「移し方」1〜6）。外す物（見込み）: 盤面（`b`・`board_dir` を開く物）に届く関数の全部（`close`・`_stop_of`・`close_at`・`hand_held`・`settle`・`read_trip`・`_write_trip`・`_closed`・`_sync_closed`・`_read_synced`・`material`・`_handed`・`snap`・`_rejects`・`revised_fields`・`prep`・`_start_tree`・`_plan_errors`・`_take`・`accept_reply`・`collect`・`human_kinds`・`_give_up`・`_gave_up_reason`・`_widen_traced`・`gate`・`_record_human`・`_notes`・`answer`・`lines`）と、それにしか使わない import（`entry`・`conflict`・`recount`・`accept`・`rolekit`・`leftovers`・`answer`・`gatemarks`・`converge` のうち残る物が使わない物）。残るのは文の定数（`REPLAN_ASK`・`REPLAN_REJECT`・`ITEM_HEAD`・`OLD_HEAD`・`ROW_HEAD`・`NEW_HEAD`・`TRIP_KEYS` など）と、項目の形の小道具（`new_item`・`_role_item`・`_bare`・`_units`・`_json_block`・`_malformed`・`_type_lines` のうち盤面を受けない物）。言い換え: 55・667・702 行（Archon）。fix・report・線の元の部品も `replan` を import していたが、使っていたのは盤面の関数だけで、外した後の残りを読むのは plan だけ。
- 新しい `lib/planfile.py`（書き直しの形。ブロックの名の部品）: plan が要る、盤面を読む関数の書き直し。元の関数の名のまま、値かパスを引数で受ける。
  - `_owed_units(judgment)`（元 `works/.shared/core/graphloops/rules/review-loop.py:2645`。盤面の記録の代わりに `judgment` の中身の `units` と `questions` を読む。開いた単位の述語は元 `works/.shared/core/scripts/review-record.py:624` の `is_open`（label が block か、suggest で disposition が do-now）を、人に諮っている状態は同じファイルの 343 行の `ASKING`（held・escalate）を写す。検証器そのものは持ってこない）
  - `plan_slots(judgment)`・`stuck_reason(judgment)`・`not_allowed(judgment, reply)`（元 `works/blk-plan/lib/planblk.py:316`・`:366`・`:407`。返り値の形は元のまま。番号は `slots.json` の並び）
  - `fix_plan_covers_units(plan, owed, opened)` → 拒否の行（元 `works/.shared/core/graphloops/rules/review-loop.py:3077`。例外の代わりに行を返す）
  - `_plan_errors(rows, reply, repo, exists)` → 拒否の行（元 `works/.shared/core/replan.py:478`）
  - `prescriptions(judgment)` → `{単位の id: [処方]}`（元 `works/.shared/core/planmarks.py:804`。判定の返答は `judgment` の中身）と `prescription_section(units, given)`（元 `works/blk-plan/lib/planblk.py:356`）
  - `base_test_texts(repo, rev)` → `{パス: 中身}`（元 `works/.shared/core/writes.py:93`。テストのファイルの見分けは前提の `lib/impact.py` の `is_test`、git の読みは `subprocess` で直に。読めなかったパスは返りの 2 つ目に返し、script が拒否の理由の頭に書く。これは元の関数の写しで、`writes.py` を持つ fix と同じ物が 2 か所に在る。`writes.py` を`docs/plans/2026-10-12-blocks/prereq.md` の issue に移すと fix だけの部品まで連れてくるので今は写しのまま置き、最後の掃除の段で 1 つにする。docstring と PR の本文にそう書く）
  - `converge_record(dir)`（元 `works/.shared/core/converge.py:214` の `read` と `:373` の `record_pass`。盤面の控えを読む代わりに、自分の置き場の周ごとの `p2.fix_plan.json` と `review/p2.plan_review.json` の並びから同じ形の控えを組み直す。項目の状態の決め方は lib の `converge._item_states`・`converge.decide` を呼ぶ）
  - `answer_gaps(record, answers)`・`splice(record, rows)`（元 `works/.shared/core/converge.py:437`・`:333`。盤面の代わりに `converge_record` の控えを受ける）
  - `revised_fields(fields, rows, repo)`（元 `works/.shared/core/replan.py:365`。直した項目の欄を `planmarks.split` で作り直して差し替えた並び）
  - ブロックの名の小道具（元は無い）: `next_round(dir)`（`plan/r*/` の数 + 1）・`latest(dir)`（一番新しい周のフォルダ）・`structure_key(units, head)`（使い回しの鍵）

### 試験

- `lib/tests/test_planfile.py`（新しい。上の書き直しの試験）: 上の `planfile` の関数ごとに、元の試験の場合を写す。`answer_gaps`・`splice` は元 `tests/test_plan_gate.py`・`test_converge.py` の場合のうち盤面を使わずに書ける物（閉じた項目を変えた直しを拒む・開いた項目の行が欠けた直しを拒む・block に答えない直しを拒む・同じ block が 2 度続いた項目が保留になる）。`converge_record` は 2 周分の案と review のファイルを置いて、元の控えと同じ項目の状態になることを見る。例: 単位の書き落とし・2 つの案に入った単位・知らない番号を名指して拒む（元 `rules/review-loop.py` の `fix_plan_covers_units`）。人に諮っている fork の出どころと depends は義務から外れる・開いていない単位（nit・defer）を入れた案を入れてよい no を添えて拒む・義務なのに開いていない単位で行き止まりの理由が出る（元 `_owed_units`・`planblk.not_allowed`・`stuck_reason`。元 `tests/test_duty_sets.py`・`test_blk_plan.py` の当たる場合を写す）。案の直しの返答が渡した項目に限られ、unit_keys の字を変えたら拒み、誤りを 1 回で全部並べる（元 `tests/test_replan.py` の `test_reply_limited_to_handed_items`・`test_all_errors_in_one_rejection`）。修正前の版のテストの中身が版の木から引ける・読めないファイルは含めない（元 `writes.base_test_texts`）。周の番号が同じ置き場の 2 度目の include で 2 になる。
- `lib/tests/test_replan.py` は持ってこない（元 `tests/test_replan.py` は全部が盤面（`ReplanCase`）を使い、外した後の `replan.py` の残りを縛る場合が無い。残りの小道具は `test_planfile.py` と `tests/workflows/test_plan.py` の案の直しの試験が通す）。`test_blk_plan.py` も持ってこない（盤面と元のブロックの YAML）。段 A・構造の目・波及の一覧の部品の試験（元 `test_blk_structure.py`・`test_structure_eye.py`・`test_ripple.py`）は`docs/plans/2026-10-12-blocks/prereq.md` の issue が部品と一緒に持ってくる。持ってこない訳を PR に書く。
- `tests/workflows/test_plan.py`（ブロックの YAML と script の試験。PyYAML で YAML を読み、script は子のプロセスで、`INPUTS_*`・`ARTIFACTS_DIR`・`WORKFLOW_ID` を一時の置き場に向けて走らせる。対象のリポジトリは `tests/e2e/target-seed/` を一時のフォルダに写して git にした物（`tests.bin.gitkit`））:
  - 形: 工程の名 `works-factory-plan`・`inputs` の名が本文の 8 つちょうど・`returns: plan`・`outcome_field: ready`・返す節の `output_format` の `required` が `[ready, plan, structure, ripple, depth, round]` ちょうどで `additionalProperties: false`・指し札の欄が `{type: archon_artifact, run_id, path}` の形・`depth` の項目が `{unit_id, depth（enum 軽量・標準）, why}`。
  - 役の節（`structure-eye`・`plan-writer`）が全部 `mutates_checkout: false` で、`settingSources: [user]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}` が元の YAML と同じ。ブロックの工程の頭に `interactive`・`worktree`・`container`・`evidence_policy`・`mutates_checkout` を書いていない（include された時に警告つきで落ちるため。止めた Archon の `guides/authoring-workflows.md` の「Composed behaviour」）。`structure-eye` の `allowed_tools` が空で、指示書が `$structure-eye-prep.output` のほかの入力（`$INPUTS.*`・ほかの節の出力）を読まない（構造の目は道具なしの独立の会話）。`plan-writer` の `allowed_tools` が `[Read, Grep, Glob, WebSearch, WebFetch]` ちょうど。模型と effort が `stage-models.json` と役の前付けの値（opus・medium、opus・high）。期限の鍵が全部 `1728000000`。
  - 段 A（元 `test_blk_structure.py` の `BlockCase`・`EyeInputsCase` を写す）: 単位を測って `structure.json` と 0 バイトの `design.jsonl` を書く・実測が落ちた単位でも節は 0 で終わり status: failed・読めない単位のファイルでも 0・地図と柵の表の在る対象で単位のパスに当たる考えの行が目に見える・同じ単位と HEAD の 2 度目は `reused: true` で測り直さない。
  - 受け付け: 単位の書き落とし・works の欄の欠け（route・tests・allowed_paths…）・構造の目が汚れると見た行への答えの欠け・世界の解の行への答えの欠け・narrows の狭めない案の欠けを、それぞれ名指して拒む。3 回目の拒否で `done: true`・`give_up: true`（元 `test_blk_plan.py` の `test_give_up_ends_loop` と同じく、Archon と同じ順で script を回し `until_bash` の式を sh で評価して見る）。通った案の `plan-fields.json` が今の works の形 `{round, fields}` で、`fields` の形が `planmarks.split` の物。横の `p2.fix_plan.json` の narrows の行に関所の決め手の欄が残る。役が番号で返した単位が id に戻っている。`paths` の空な単位が測られず `skipped-units.json` に載る。
  - 案の直し: `ruling` つきの include で、渡していない項目を返した・unit_keys を変えた返答を拒み、通った時に `plan-fields.json` の `amended` に直した項目の核の欄が在り、横の `replan.json` の行に `contract_changed`・`widened` が在り、`ripple.json` が直した項目で作り直される。
  - 返す節が落ちない: 壊れた入力（読めない `start`・形の違う `units`・在らない指し札・置き場の `plan/` を消した後）を渡して子のプロセスで `plan_collect.py` を回し、終了の値が 0 で、標準出力の JSON が返す節の `output_format` に合い、`ready: false` で、指し札の先が全部在って空でない。
  - 1 回目の入力: `review` が空の字 `''` でも `null` でも、往復の 1 回目として回る（`plan-prep` が前の周の案と指摘の節を作らない）。
  - 返す節: 諦めた周は `ready: false` で、`plan`・`structure`・`ripple` の指し札の先が全部在って空でない。同じ置き場で 2 度回すと `round` が 1・2。構造の目が「人に上げる」とした行が在っても `ready` は true のまま（下の「人が入れる前提の直し」2）。目が行を出さなかった周も `structure-state.json` が在り status: failed。行き止まりの単位が在る周は役を起こさずに `ready: false`。
- `fixtures/`（Archon の `workflow test`。筋書きが確かめるのは配線だけ。止めた Archon の dry-run は `until_bash` を回さず輪を済んだとみなし、差し替えは節ごとに 1 つの値で、`exec-code` の節には空の `ARTIFACTS_DIR` と `WORKFLOW_ID=dry-run` が渡る（`reference/cli.md` の dry-run の節）。だから輪の拒否・3 回の諦め・行き止まりは上の `tests/workflows/test_plan.py` が script を子のプロセスで回して見る）:
  - `ready.stubs.yaml`: 全部の節を差し替え、返す節が `ready: true`。`fixture: {expect: completed, reached: [round, structure-eye, plan-writer, plan]}`
  - `give-up.stubs.yaml`: 受け付けが諦めた姿（`plan-accept: {done: true, give_up: true…}`）で返す節が `ready: false`。`expect: completed`（ready: false も正しい終わり。ASF の `W/plan/fixtures/blocked.stubs.yaml`）
  - `eye-skipped.stubs.yaml`: `structure-measure` が `eye: false`（使い回し）で構造の目の輪が飛び、`structure-state` と返す節には届く
  - `replan.stubs.yaml`: `fixture.inputs` に `ruling: '["1"]'` を入れ、`ripple-units` が飛び、返す節に届く

## 返りの約束（`docs/design.md`「ブロックの返りの約束」の `plan` の返りのまま）

- 返す節 `plan`・`outcome_field: ready`（ASF の `W/plan/archon-plan.yaml`。ready が false も正しい終わり）
- 入力（`with:`）:
  - `start` ← `$start.output.record`
  - `units`・`judgment`・`world`・`spec` ← `$judge.output.<同じ名>`
  - `review` ← `$plan-review.output.review`（往復の 2 回目から。1 回目は線が空の字 `''` を渡す）
  - `ruling` ← `$fix.output.replan_items`（`replan` の時だけ。`plan` では `[]`）
  - （約束に無い入力。既定 `"null"` で宣言し、「人が入れる前提の直し」1 で約束に足す）`conflicts` ← `$fix.output.conflicts`（`replan` の時だけ。`plan` では null）
- 返り:
  - `ready`（boolean）: 修正案ができた（受け付けを通った）。false は 3 つ: 受け付けが 3 回とも拒んだ時・直す義務の単位が無い時・行き止まりの単位が在る時。構造の目が「人に上げる」とした行は false にせず、`structure` で plan-review に渡り修正前の関所の問いになる（今の works と同じ）。返りに false の訳を分ける語は持たない（欄を足さない）: 3 回の拒否と行き止まりは report がどちらも `stopped_by_line` にし、義務の単位が無い時は report が judge の返り（`units` が空）から `no_fix_needed` にする → 線 5・report
  - `plan`（指し札）: 修正案（`plan/r<k>/plan-fields.json`。今の works の `plan-fields.json` と同じ形 `{round, fields, amended?}`。項目ごとの書いてよい範囲・受け入れテスト・定石と構造の行ごとの従うか外れの訳。同じフォルダの `p2.fix_plan.json`（役の返答。approach・adds・removes・shrink_first・narrows（決め手の欄つき）・block_answers）も同じ修正案の一部で、読み手はこの名で開く。約束への書き込みは「依存」の H5）→ plan-review・fix・eyes
  - `structure`（指し札）: 構造の目の控え（`plan/structure/<鍵>/structure-state.json`。今の works の `structmark` の控えの形。設計の行は同じフォルダの `design.jsonl`（今の works の design-row の形。名で開く隣のファイル。「依存」の H5））→ plan-review
  - `ripple`（指し札）: 波及の一覧（`plan/r<k>/ripple.json`。今の works の `ripple.json`）→ plan-review・fix・eyes
  - `depth`（array）: 単位ごとの深さ。項目は `{unit_id, depth, why}`、depth は `軽量`・`標準`（今の works の `lib/depth`）→ 線（深さの決め）・fix
  - `round`（integer）: 何回目の案か（往復と案の直しを通して数える）→ report
- 型つきの成果物: 無し（`output_type` を書かない。型つきの成果物の一覧は report だけが読み、plan の物は約束に無い）。

- 返す節の `output_format` は、上の欄をちょうど持つ（全部 `required`・`additionalProperties: false`）。欄を足す・名を変える・型を変える・欄を落とすのは線との約束を変えることなので、この PR ではしない。要ると分かったら PR の本文の「約束を変える頼み」に書き、約束どおりの形で作り終える。

## 共通の書き方

- script の節は名指しの script（`script: <名>`・`runtime: uv`・ファイルは `scripts/<名>.py`）。頭で境の口と lib/ を次の形で読む（Archon の `guides/script-nodes.md` の「Share code within a pack」の Python の形。パスの字に `../` を書かないので E4 の照らしに当たらない）:
  ```python
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
  import boundary
  sys.path.append(str(boundary.lib_root()))
  ```
  入力は `os.environ["INPUTS_<名>"]` を字のまま読む（名前を組まない。issue #11）。返りは `boundary.returns(...)`、指し札は `boundary.pointer(...)`・`boundary.resolve(...)`。確かめの中身は書かず、lib/ の関数を呼ぶだけ（E4）。
- 始めの記録は入力 `start`（指し札）で受け、`boundary.resolve` で開いて JSON で読む。欄の形は `lib/startrec.py`。
- 期限: 期限を持つ節（`script:`・`bash:` の `timeout`、`prompt:`・`command:` の `idle_timeout`、`loop:` の `idle_timeout` と `timeout`、`loop_group:` の `timeout`、`approval:` の `idle_timeout`）には全部 `1728000000` を書く（E12）。
- 役の節の `model:`・`effort:` は今の works の `works/.shared/core/stage-models.json` と役の前付け（`works/.shared/core/agents/`）の値を写す（持ち主の決め `model-effort`）。
- 役の指示書（`commands/`）と `lib/` に、対象の言語・テストの実行器の名を書かない（E13）。持ち主の環境の字（`raiki61`・`/Users/` など）を書かない（E14）。
- 外への書き込み（GitHub・対象のリポジトリの main・人に見える所）は、このブロックでは無い（E6）。書くのは run の置き場の `plan/` の下だけ。
- ブロックの YAML と script は、ほかのブロックのフォルダを指さない（E4）。ほかのブロックの返りは `with:` の入力として受けるだけ。
- 筋書き（fixture）は Archon の `workflow test` の形（`fixtures/<名>.stubs.yaml`。予約の鍵 `fixture:`（`expect`・`fail-node`・`reached`・`inputs`・`resolved-text-contains`）と `exec-code:`、残りの鍵は節の id → 差し替えの出力）。script の中身まで通したい筋書きは `exec-code: true`。
- ブロックの試験（`tests/workflows/test_plan.py`）は 2 つを持つ: YAML を PyYAML で読む形の試験と script を子のプロセスで回す試験（Archon を起こさない）、それと筋書きを回す試験。筋書きは、issue #47（P0）の `tests/archon.py` が作る使い捨ての木（`.archon/workflows/works-factory/` の下に `plan/` と `.shared/` だけ）で `archon workflow test` に回す。止めた Archon の源が無い所では `tests/archon.py` が `skipTest("Archon の源が無い: ...")` で見送る。
- このブロックの置き場の決まり: run の置き場の中で書くのは `plan/` の下だけ。周ごとの物は `plan/r<k>/`、使い回す構造の実測は `plan/structure/<鍵>/`。読むのも自分が書いた `plan/` の下と、入力の指し札の先だけ。

## Archon で書けない所

- 会話の続き（持ち主の決め `persona`。持ち主に聞いている所）: 今の works の直しの役（plan-revise）は修正案の役の会話の続きで起きた。新しい形では往復が線の `loop_group` の中の include で回るので、include をまたいで役の会話を続けられるかは分からない（`docs/design.md` の U4 と同じ所）。このブロックは、前の周の案と事前審査の指摘を保存したファイルで渡し、新しい会話で直させる（今の works の案の直しの役 replan と同じ渡し方）。これは能力を狭める直しとして PR の本文に書く（持ち主の決め `no-narrow`）。根拠と食い違いを並べる: `persona` の決め「引き継ぎは会話の再開か機械が保存した返答で渡す」には保存した返答で渡す形として合い、同じ決めの当て方「再審は判定役の会話を継ぐ」が示す会話の続きの形とは違う。どちらにするかは持ち主の答え待ちで、この PR では新しい会話の形で作る。埋めは作らない。
- 読んだ証拠（今の works の `plan-reads`）: 未決 U6。このブロックでは作らない（今の works でも受け付けの条件ではなかった。`blk-plan/blk-plan.yaml` の `plan-reads` の注記）。
- 埋めの名簿は `docs/polyfills.md`。このブロックが使う行は無い。
- ほかは無し（輪は `loop_group`、受け付けの拒否で出し直すのは `until_bash`、作業ツリーの照らしは `mutates_checkout: false`、型は `output_format`）。

## E11 の 3 つの答え

1. Archon が持っているか: 輪（`loop_group` の `max_iterations`・`until_bash`・`fresh_context`）・型の照らし（役の節と script の節の `output_format`）・読むだけの節の作業ツリーの照らし（`mutates_checkout: false`）・指し札の先の照らし（節の終わり）は Archon の物を使う。単位の網羅・works の欄・構造と世界の解の答えの照らし・波及の一覧・構造の実測・深さは Archon に無い（中身の確かめなので lib/）。
2. ASF が持っているか: `W/plan/archon-plan.yaml` の返りの形（`returns: plan`・`outcome_field: ready`・ready: false を正しい終わりにする・`mutates_checkout: false`）を採る。ASF の plan は 1 つの役だけで、受け付けの輪・構造の目・波及の一覧を持たない。
3. 本当に要るか: 能力の棚卸しの「構造の目」「修正案」「波及の一覧」「案の直し」「単位ごとの深さと上げ直し（決めの側）」の行と、受け入れの一覧の `p2.fix_plan`。

## 受け入れ

1. 試験を先に入れて赤を見る（lib/ の部品が無い・YAML が無い）。その後で部品と YAML を入れて緑。赤と緑の出力の要約を PR に書く。
2. リポジトリの根からの全部の試験 `uv run --isolated python3 -m unittest discover -s . -t .` が緑。`tests/layers/` の層の試験（その時に在る物全部）も緑のまま。
3. 止めた Archon の源が在る所で、`tests/workflows/test_plan.py` の筋書きの試験（`tests/archon.py` の使い捨ての木で `archon workflow test`）が全部通る。`archon validate` の層の試験（P0）に `works-factory-plan` の誤りも警告も無い。源が無い所では、筋書きの試験は名前つきで見送られる（`skipTest("Archon の源が無い: ...")`。`tests/AGENTS.md`）。PR には、Archon で回した結果か、回せなかった訳を書く。
4. 持ってきた lib/ のファイルを元と比べた差分が、lib-port の「移し方」1〜5 で決めた直しだけ。
5. PR の本文に次を並べる（守りのパスの文書に書く代わり。土台の持ち主が `docs/design.md`・`docs/asf-notes.md` に写す）:
   - lib-port の「移し方」6 の 4 つ（元のパス → 置いた先・外した物と理由・言い換えた行・盤面の物を引数で受ける関数の一覧）
   - 採った ASF の型（`docs/asf-notes.md` の「書き方」の 4 行の形）
   - 「能力の棚卸し」と「受け入れの一覧」のこのブロックの行ごとの、証の試験か筋書きの名
   - 約束を変える頼み・使いたかった埋め（あれば）
6. ブロックの分（`docs/design.md` の段 2 の `plan` の行）:
   - 構造の目と修正案と波及の一覧が動く（`tests/workflows/test_plan.py` の段 A・受け付け・返す節の試験と `ready.stubs.yaml`）。
   - 項目ごとに書いてよい範囲・受け入れテスト・定石と構造の行への従うか外れの訳が無ければ受け付けが拒む（受け付けの試験。欠けごとに 1 つ）。
   - 案の直しの入力（`ruling`）で 2 度目を差し込める（案の直しの試験と `replan.stubs.yaml`）。
   - 受け付けが 3 回拒めば諦めて `ready: false` で返り、指し札の先は全部在る（`tests/workflows/test_plan.py` の輪の試験と返す節の試験。`give-up.stubs.yaml` は配線だけ）。
   - PR の本文に、能力を狭める直しとして「直しの役を修正案の役の会話の続きでなく新しい会話で起こす」を書く（上の「Archon で書けない所」の `persona` の行の文を写す）。
   - `round` が往復と案の直しを通して数えられる。

## 範囲

- 作るのは下の「作るファイル」だけ。
- 触らない（守りのパス。ASF の merge が人の手に残す）: `workflows/line/**`・`workflows/.shared/**`・`docs/design.md`・`docs/owner-decisions.md`・全部の `AGENTS.md`・`pack.json`・`README.md`・`MISSION.md`・`engineering.md`・`.github/**`・`harness/**`・`factory/**`・`.factory/**`。
- 触らない（同じ時に別の run が作る）: ほかの 7 つのブロックのフォルダ（`workflows/<ほかの名>/`）と、それらの issue が名指す lib/・試験のファイル。ほかの PR と同じファイルを作らない。
- 触らない（前に入る物）: lib-port と`docs/plans/2026-10-12-blocks/prereq.md` の issue で入った lib/ のファイル（本文の「依存」に並べた物）とその試験、`tests/workflows/__init__.py`・`tests/archon.py`、`pyproject.toml`、`docs/`（PR の本文に書く。上の受け入れ 5）。持ってきた部品の中で前提の部品に直しが要ると分かったら、直さず PR の本文に書く。
- 決めた範囲で能力を落とす直しが要ると分かったら（持ち主の決め `superset`・`no-narrow`）、止めて PR の本文に書く。
- `lib/planrange.py` は使わない（fix の部品。受け付けの表は structmark と worldmark を直に呼ぶ）。

作るファイル（これ以外は作らない・変えない）:

```
workflows/plan/**
lib/replan.py
lib/planfile.py
lib/tests/test_planfile.py
tests/workflows/test_plan.py
```

`workflows/plan/**` の中身: `works-factory-plan.yaml`・`commands/structure-eye.md`・`commands/fix-plan.md`・`scripts/round.py`・`scripts/structure_measure.py`・`scripts/eye_prep.py`・`scripts/eye_accept.py`・`scripts/structure_state.py`・`scripts/ripple_units.py`・`scripts/plan_prep.py`・`scripts/plan_accept.py`・`scripts/ripple_items.py`・`scripts/plan_collect.py`・`fixtures/ready.stubs.yaml`・`fixtures/give-up.stubs.yaml`・`fixtures/eye-skipped.stubs.yaml`・`fixtures/replan.stubs.yaml`。

## 依存

- issue #47（P0）（ブロックより先に main に入る）: 自分の工程の置き方（`.archon/workflows/works-factory/<ブロック>/`。packaged workflow）・script から lib/ への届き方 U5（`boundary.lib_root()` が `WORKS_FACTORY_ROOT` を読む）・`tests/archon.py`（止めた Archon の源と bun を探し、無ければ `skipTest("Archon の源が無い: ...")`、名指したブロックのフォルダと `.shared/` だけの使い捨ての git の木を作り、使い捨ての ARCHON_HOME で Archon を回す）・CI が Archon の源と bun を取ること・`archon validate` と変換しないことの層の試験。
- 前に入る人の直し（守りのパスの文書。この issue より前に main に入るので、中身はリポジトリのそこを読む）:
  - H1: `tests/workflows/`（ブロックの YAML の形と筋書きの試験の置き場）をリポジトリの形の木に載せる（根の `AGENTS.md`・`tests/AGENTS.md`）。
  - H2: report の返す節に boolean の `ok` を足し、`outcome_field: ok` にする。結末の 10 語 `outcome` は別の string の欄のまま（`docs/design.md` の「report の返り」。止めた Archon の `outcome_field` は `required` の boolean しか受けない）。
  - H3: 段 2 の共通の受け入れ 4・5（ASF の型・証の名）を「PR の本文に書き、土台の持ち主が `docs/` に写す」に直す（`docs/design.md` の「作りの順」）。
  - H4: E13 の例外。拡張子と言語の対応・テストのファイルの名の慣習の表と、その表を作る標準ライブラリの import を、`lib/impact.py`・`lib/changemap.py`・`lib/tddloop.py`・`lib/fixrules.py`・`lib/libdocs.py`・`lib/libdocs_local.py` に限って許す（根の `AGENTS.md`。機械の表 `tests/layers/scan.py` の `ALLOWED["E13"]` には、そのファイルを入れる PR が 1 行ずつ足す）。
  - H5: ブロックをまたぐ形（`docs/design.md` の「ブロックの返りの約束」の「書き方の決め」）。
    - 指し札の先は今の works の同じ名のファイルの形。次の隣のファイルだけは約束の一部で、ほかのブロックも名で開く: `judgment`（`judgment.json`）の隣の `premises.json`・`judge-verify.json`・`pr-excluded.json`・`materials.json`、`plan`（`plan-fields.json`）の隣の `p2.fix_plan.json`、`structure`（`structure-state.json`）の隣の `design.jsonl`、`review` の隣の `gate-passes.json`。ほかの隣のファイルは作ったブロックの中だけで読む。
    - 直す前の結末のファイル: 必須の欄 `{suite, test_cmd, rev, exit, cases}`（`suite` は始めの記録の `tdd_suite` の実行ファイル。`cases` は JUnit の 1 件ごとの結末の並び）。読み書きは `lib/baseline_red.py` だけ。test-gate は自分の欄を足してよい。
    - fix の `conflicts` の先は `conflicts.json` = `{"items": […]}`（今の works の `conflict.py` の形）。
    - 型つきの成果物: `green-cert` は test-gate の返す節の出力。`tdd-unit` は fix の 1 回の差し込みに 1 つで、中身は組ごとの段の物 `[{group_id, ran, reason, suite, reused, units}]`（今の works の blk-fix の `tdd` の出口。走らなかった組も `ran: false` で載る）。`eye-verdict` は `{eye, status, reason}`（`eye` は `r1`・`r2`・`r3`・`r4`・`premise-check`）。
    - 人の関所（`approval:`）の `decisions` は `approve` を含む（Archon の決まり）。通す語は `approve`・`continue`、止める語は `stop`・`reject`。止め札は止める語で、文が `request:` で始まる物。ブロックの `stop_reason` は人の止めを `human:<所>`、止め札を `request:<所>` の形で返す。
    - 約束に無い入力は、ブロックの YAML の `inputs:` に既定値（`""`・`"null"`・`"[]"`）つきで宣言し、線が渡す前も動く形にする。返りの欄は足さない。
    - 返す節は落ちない。中の誤りを全部捕まえ、そのブロックの偽の結末（`ok: false` など）と訳を、`output_format` に合う形で返す（線は落ちた返す節の先へ進めない）。
  - H7: 始めの記録に `tdd_suite`（TDD の輪と 1 件ごとの結末に使う実行ファイルのパス。無ければ `""`）を載せる（`docs/design.md` の「線の始めの節 `start` の返り」）。
  - H8: R2 の `status` に `unverifiable`（R2 の比べの節が落ちた・独立設計が無い。前提が崩れた時は `premise_check` にも載る）を足し、merge の入力に `r2` を足し、merge の返り `diff` を null 可にする（`docs/design.md` の eyes と merge の返り）。merge は `redesign-needed` だけを人の答えに関わらず拒み、`unverifiable` は人に回す。
  - H10: E16 の機械の行を「`approval:` の節を持つ工程を起こす一番上の工程（線）に `interactive: true` が在る。差し込まれるブロックは工程の頭に `interactive`・`worktree`・`container`・`evidence_policy`・`mutates_checkout` を書かない」に直す（`workflows/AGENTS.md`。差し込まれた工程の頭のこれらの鍵は Archon が読み込みの警告つきで捨てる）。
- 前に入る PR: issue #47（P0。工程の読み込みの pack の形 `.archon/workflows/works-factory/<ブロック>/`・script が lib/ を見つける道 `boundary.lib_root()`（`WORKS_FACTORY_ROOT`。未決 U5）・Archon の要る試験の助け `tests/archon.py`・CI の Archon の源）と、`docs/plans/2026-10-12-blocks/prereq.md` の issue（2 つ以上のブロックが読む lib/ の部品と `tests/workflows/__init__.py`）。

- main に在る物（lib-port の PR）: `lib/planmarks.py`・`lib/structmark.py`・`lib/concepthome.py`・`lib/worldmark.py`・`lib/gatemarks.py`・`lib/converge.py`・`lib/marks.py`・`lib/promptsection.py`・`lib/carry.py`・`lib/cite.py`・`lib/stopby.py`・`lib/startrec.py`・`lib/accept.py`・`lib/graphloops/engine/`・`tests/e2e/target-seed/`・`tests/bin/gitkit.py`。
- main に在る物（`docs/plans/2026-10-12-blocks/prereq.md` の issue（ブロックの前の共有の部品）。2 つ以上のブロックが使うので先に入る。読むだけで、作らない・変えない）: `lib/ripple.py`・`lib/planblk.py`（盤面を外した残り。plan は `HEAD` の文の定数・`ITEMS_RULE`・`REUSE_RULE`・`NO_NARROW_REJECT`・`RECOMMEND_REJECT`・`NOT_OWED_REJECT`・`PRESCRIPTION_HEAD`・`PRESCRIPTION_ASK`・`EXCLUDED_HEAD`・`verify_part`・`_plan_malformed` を読む）・`lib/impact.py`・`lib/changemap.py`・`lib/depth.py`・`lib/measure.py`・`lib/stage_a.py`・`lib/context.py`・`lib/eye.py`・`lib/conceptfence.py`・`lib/libdocs.py`・`lib/libdocs_local.py`・`lib/libdocs_web.py`・`lib/REVIEW.md`（観点の正本。データ）・`tests/workflows/__init__.py`。`lib/rolekit.py`（拒否の数え方の純な助けだけ: `with_done`・`rejected`・`given_up_reason`・`GIVE_UP_AFTER`・`REJECT_LINE`）も`docs/plans/2026-10-12-blocks/prereq.md` の issue。`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/planblk.py` は、`replan`・`planrange`・`writes` の import を外して入る（それらに頼る関数ごと外れる）ので、plan はそれらを `planblk` 越しに読まない。`docs/plans/2026-10-12-blocks/prereq.md` の issue で外された関数に plan の要る振る舞いが在れば、上の書き直しの形で `lib/planfile.py` に書き直す（前提の部品は直さない）。
- 置き方と lib/ への届き方はissue #47（P0） で決まる（上）。このブロックは pack（`works-factory`）の中のブロックのフォルダとして読まれ、名指しの `command:`・`script:` はこのブロックの `commands/`・`scripts/` から引かれ、script は `<pack>/.shared/` を import し、lib/ へは `boundary.lib_root()` を呼ぶだけ。
- ほかのブロック: 待たない。ほかのブロックの返りは線の `with:` で入力として届くだけで、このブロックの試験はその形の入力を筋書きと試験の中で作る。
  - 指し札の中身の字は、出す側の issue と合わせる（型の正本は持たない。持ち主の決め `io-in-output-format`）: `judgment` の中の単位ごとの処方の鍵と、同じフォルダの `judge-verify.json`・`pr-excluded.json`（judge の issue。「依存」の H5）、`review` の中の block の行（plan-review の issue。項目の状態は `review` に求めず、このブロックが受けた review の並びから組む）、`conflicts` の中の申し出と裁定の行（fix の issue）。このブロックはそれらを「在れば読む、無ければその節を作らない」で読み、読めなかった鍵を PR の本文に書く。plan が出す指し札の中身は今の works のファイルと同じ形（H5）: `plan` は `plan-fields.json`、`structure` は `structure-state.json`、`ripple` は `ripple.json`。ほかのブロックは指し札が名指すファイルと、名で開く隣のファイル（`plan` の `p2.fix_plan.json`・`structure` の `design.jsonl`）だけを読み、`slots.json`・`replan.json`・`skipped-units.json` は読まない。

## 人が入れる前提の直し

共通の前提（H1〜H5・H7）は「依存」の頭に並べた物。このブロックだけが要る物（どちらも、入れる前からブロックは動く。1 は宣言した入力の既定 `"null"` で、2 は今の works の振る舞いで作る）:

1. `docs/design.md` の「ブロックの返りの約束」の「plan の返り」の入力に 1 行足す（このブロックは YAML の `inputs:` に既定 `"null"` で宣言済み。線が渡すのはこの行が入った後。案の直しの役に裁定の文を渡すため。今の works の `replan.py` の REPLAN_ASK は「誤りと裁かれた項目・申し出・裁定の文」を渡していて、`ruling` の項目の id だけでは落ちる。持ち主の決め `superset`）。足す行（`ruling` の行の直後）:
   ```
     - `conflicts` ← `$fix.output.conflicts`（`replan` の時だけ。`plan` では null。裁定の文を案の直しの役に渡す）
   ```
   同じ所の「fix の返り」の `conflicts` の読み手に `plan` を足す: 「→ 線 11・report」を「→ 線 11・plan（replan）・report」に。
2. `docs/design.md` の「plan の返り」の `ready` の文を、今の works の振る舞いに合わせる（構造の目の「人に上げる」行で false にすると、線 5 から report へ進み、修正前の関所で聞く道が消える。今の works では案は続き、関所の問いになる）。直す前: 「`ready`（boolean）: 修正案ができた。構造の目が人に上げると決めた時などは false → 線 5・report」。直した後:
   ```
     - `ready`（boolean）: 修正案ができた（受け付けを通った）。false は 3 つ: 受け付けが 3 回とも拒んだ時・直す義務の単位が無い時・行き止まりの単位が在る時。構造の目が「人に上げる」とした行は false にせず、`structure` で plan-review に渡り修正前の関所の問いになる（今の works と同じ）。返りに false の訳を分ける語は持たない（欄を足さない）: 3 回の拒否と行き止まりは report がどちらも `stopped_by_line` にし、義務の単位が無い時は report が judge の返り（`units` が空）から `no_fix_needed` にする → 線 5・report
   ```
