<!-- coldwrite:skip 計画（issue の本文）。語は works-factory の docs/design.md の「語」の節で定義 -->
# judge: 判定のブロックを中身ごと作る（workflows/judge/ と、それだけが使う lib/ の部品と試験）

works-factory は、修正依頼を受けて確かめ済みの変更と報告を返す工場を、Archon（AI の工程を YAML で書いて回す道具）の上に作り直しているリポジトリ。前の形の「今の works」（公開リポジトリ raiki61/claude-plugins の `works/`。移す元の版は `pack.json` の `works.commit` = `2aa7c66cf7abe1fe09699ac2942d107123214168`）は、判定・計画・修正・確かめ・報告をつないだ工場で、その能力を 1 つも落とさずに、線（`workflows/line/`。ブロックを並べる 1 本の工程）・8 つのブロック（`workflows/<名>/`）・助け手（`lib/`。Archon を知らない Python）に移している。この issue は、そのうちのブロック `judge` を、フォルダの中身ごと 1 つの PR で作る。8 つのブロックは別々の run で同時に作られ、線とはブロックの返りの約束（`docs/design.md` の「ブロックの返りの約束」）だけでつながる。元のファイルは `https://raw.githubusercontent.com/raiki61/claude-plugins/2aa7c66cf7abe1fe09699ac2942d107123214168/<パス>` で読める（本文の「元」の欄の `<パス>`）。ASF は Archon の作者が作った、issue から PR までの工程の束（`docs/design.md` の「語」）。

## 読む物

- 根の `AGENTS.md`（リポジトリの形・E8〜E11・E13・E14・E18）、`workflows/AGENTS.md`（E1・E2・E4〜E7・E12・E16・E17）、`lib/AGENTS.md`（E3）、`tests/AGENTS.md`。決まりの番号 E1〜E18 の中身はそれらの文書に在る。
- `docs/design.md`: 「ブロック」の `judge` の節・「ブロックの返りの約束」の `judge` の返りと「書き方の決め」・「能力の棚卸し」の `judge` の行・「受け入れの一覧」・「Archon の分かっていること」と未決 U1〜U8・「作りの順」の段 2 の `judge` の個別の行。
- `docs/plans/2026-10-12-lib-port.md` の「移し方」1〜6（この issue で `lib/` に持ってくる部品も同じ移し方に従う）。
- `docs/owner-decisions.md` のうち本文が引く決め（`premises-purpose`・`judge-sees-all`・`world`・`step-up`・`spec-approval`・`persona`・`web-split`・`model-effort`・`beyond-diff`・`root-cause`・`report-on-stop`・`lib-port-as-is`・`io-in-output-format`・`asf-way-gates-fanout`・`no-queue`・`superset`・`no-narrow`・`carry`）。
- Archon の振る舞いは、止めた Archon（`docs/design.md` の「語」。ASF と同じ源 `coleam00/Archon` の commit `d97d00ef15cce4b15d39e42635e4e86996ec1351` を bun で起こす。版は `factory/pack.json` の 1 か所。持ち主の決め `archon-same-as-asf`）の文書 `packages/docs-web/src/content/docs/`（特に `guides/script-nodes.md`・`guides/authoring-workflows.md`（「Composed behaviour」・「Previous loop iteration」・named resume の段）・`guides/loop-nodes.md`・`guides/approval-nodes.md`・`reference/cli.md` の dry-run と `workflow test`）で確かめる。ASF の工程は同じ commit の `.archon/workflows/sdlc/`（本文の `W`）。
- ブロックの分（元の works。全部 `works/` の下）:
  - 旧ブロック 8 つ: `blk-spec/`・`blk-pr/`・`blk-premises/`・`blk-purpose/`・`blk-world/`・`blk-material/`・`blk-judge/`・`blk-rejudge/`（各々の YAML・`commands/`・`scripts/`・`lib/`・`schemas/`・`fixtures/`・`manifest.json`）。旧ラインでの並びは `darkfactory/darkfactory.yaml` の 174〜400 行（speccing → pr-checking → premising → purposing → worlding → gathering → judging）と 866 行（rejudging）。役の節ごとの `model`・`effort`・`allowed_tools`・`settingSources`・`sandbox`・`context`・`mutates_checkout` と、輪ごとの `fresh_context` は、この旧 YAML の値が正本（下の「役の節の設定」）。
  - 役の指示書の元: `.shared/core/gl-prompts/prompts/review-loop/`（`p2.diagnose.md`・`p2.rejudge.md`・`p0.prior_decisions.md`・`p0.purpose_review.md`・`p1.*.md` の 9 本）と `blk-spec/prompts/`（`spec.write.md`・`spec.review.md`・`spec.revise.md`）。役の前付けは `.shared/core/agents/`（`judge.md`・`investigator.md`・`inspector.md`）、模型の表は `.shared/core/stage-models.json`。観点の正本 `.shared/core/REVIEW.md`（`docs/plans/2026-10-12-blocks/prereq.md` の issue が `lib/REVIEW.md` に置く）。
  - 判定役の材料の組み方: `blk-judge/lib/judgebrief.py`（全部）と、それが読む `.shared/core/entryshape.py`:134-200（依頼と PR の題と本文の見出し `REQUEST_HEAD`・`PR_TEXT_HEAD`・`PR_TITLE`・`PR_SUBJECT_HEAD`・`PR_BODY_HEAD` と `request_text`）・`carry.py` の `PRIOR_HEAD`・`REDESIGN_HEAD`・`prior_section`・`gatemarks.request_answers`・`answer_note`。
  - 受け付けの規則の元: `.shared/core/graphloops/rules/review-loop.py`（`judge_output` 2497 行と、その助け 2359〜2496 行・`measured_needs_output` 3010・`purpose_findings_cited` 3274・`external_rankings` 2973・`main_path_observed` 2962・`gate_arms_all_red` 3023・`local_review_covers_lenses` 3214・`_cite_errors` 3471・`_count_in_version` 3612・`_run_query` 3307・`rejudge_output` 3186・`_spec_errors`〜`spec_freeze` 3908〜4043・依頼の型 `check_inputs` 67・`add` 124、素材の要否の条件と助けは下の「lib/ に持ってくる部品」の一覧）と、検証器 `.shared/core/scripts/review-record.py` のうち規則が引く表と関数。
  - core のモジュール: `.shared/core/accept.py`（`check_request` 456・`_judge_tree_unchanged` 481・`check_judge` 504）・`premises.py`・`purpose.py`・`prcheck.py`・`rejudge.py`・`diverted.py`・`board.py`:550（`base_output` の `touches_*` の既定）・`darkfactory/lib/line_edge.py`:361 の `structure_units` と `_unit_file_paths`（判定の単位を `{id, paths, summary}` に写す）・`blk-spec/lib/specblk.py`:79-84（関所の答えの語と止め札の頭）・`report.py`:173-174（止めの頭 `REQUEST_BY`・`HUMAN_BY`）。
  - 始めの記録の形: `blk-entry/schemas/start.schema.json`（`request_file`・`policy_md`・`features_cut`・`answers`・`gates`・`input`（`diff`・`requests`・`request_file`・`pr`・`spec`）ほか）。
  - 旧の試験: `tests/test_blk_judge.py`・`test_blk_premises.py`・`test_blk_purpose.py`・`test_blk_world.py`・`test_world_check.py`・`test_blk_material.py`・`test_blk_spec.py`・`test_blk_spec_gate.py`・`test_blk_rejudge.py`・`test_rejudge.py`・`test_judge_verify.py`・`test_diverted.py`・`test_structure_units.py`・`test_accept.py`（`TestJudge`・`TestIntake`）。
- ASF: `W/triage/archon-triage.yaml`:43-44（`returns: verdict`・`outcome_field: ready`）・:53（`mutates_checkout: false`）、`W/investigate/archon-investigate.yaml`:24-25・:37（根の問いの返りと読むだけの役）、`W/merge-queue/archon-merge-queue.yaml`:179-225（`approval:` の `message` と `decisions`）と :197・:218（`with:` に `$LOOP_PREV.<節>.output` を結ぶ形）。

## 目的と引き継ぐ能力

依頼を根本の単位にまとめる。前提の実測・目的の固定・定石（世界の解）・並行 PR とのぶつかり・素材集め 11 本・根本の診断と受け付け（拒めば同じ会話で 3 回まで出し直し）・判定の裏取り・再審・目的の外の所見の持ち越し。始めの記録が仕様の段を選んだ run では、仕様（要件と受け入れテスト）を書かせて審査し、人の関所（仕様の関所）で承認を取ってから受け入れテストを固める。

能力の棚卸しの行（元 → 新しい置き場）:

- 並行 PR とのぶつかり — `blk-pr/`・`.shared/core/prcheck.py`（`forge.py`・`ghreads.py` は lib/ に在る）→ `commands/pr-check.md`・`scripts/pr_check.py`・`scripts/pr_accept.py`・`lib/prcheck.py`
- 前提の実測 — `blk-premises/`・`.shared/core/premises.py` → `commands/premises.md`・`lib/premises.py`
- 目的の固定と解き方の分け — `blk-purpose/`・`.shared/core/purpose.py` → `commands/purpose.md`・`lib/purpose.py`
- 定石（世界の解）と web の取得 — `blk-world/`（`lib/worldblk.py`・`lib/worldcheck.py`）・`worldmark.py`・`webget.py`（lib/ に在る）→ `commands/world-classes.md`・`commands/world-judge.md`・`lib/worldblk.py`・`lib/worldcheck.py`
- 素材集め 11 本 — `blk-material/`（`lib/material.py`）→ `commands/material-*.md`（11 本）と `lib/judge_accept.py` の書き直し
- 仕様の段 — `blk-spec/`（`lib/specblk.py`・`prompts/`）→ `commands/spec.md`・`commands/spec-review.md`・`commands/spec-revise.md`・仕様の関所の `approval:`・`lib/specblk.py`
- 根本の診断と受け付け — `blk-judge/`（`lib/judgebrief.py`・`lib/judgetake.py`）・`.shared/core/accept.py` の `check_judge`・`check_request`（lib-port 2F で外した物）・写しの rules の `judge_output` → `commands/diagnose.md`・`lib/judge_accept.py`（能力の名 `lib/judge_accept` のファイル）
- 判定の裏取り — `blk-judge/lib/judgeverify.py` → `commands/judge-verify.md`・`lib/judgeverify.py`
- 欠陥の探し方の試し — `.shared/core/querytest.py`（試しの側。数え直しは修正の側）→ `docs/plans/2026-10-12-blocks/prereq.md` の issue（ブロックの前の共有の部品）が置く `lib/querytest.py` を読む
- 素材の局所レビューの受け取れなさの印 — `.shared/core/diverted.py` → `lib/diverted.py`
- 目的の外の所見 — `outpurpose.py`（lib/ に在る）→ 返り `out_of_purpose`
- 再審 — `blk-rejudge/`・`.shared/core/rejudge.py` → 同じブロックを入力 `objection` で差し込む道・`commands/rejudge.md`・`lib/judge_accept.py` の書き直し
- 名指しと引用の照らし — `cite.py`（lib/ に在る）
- 読んだ証拠 — `reads.py`・`record-read.py` → 未決 U6 の決めを待つ（下の「Archon で書けない所」）

受け入れの一覧（review-graph の節）のうち judge が持つ物: `p0.parallel_pr`・`p0.premises`・`p0.purpose`・`p0.purpose_review`・`p0.prior_decisions`・`p1.local_review`・`p1.consistency_bypass`・`p1.hygiene`・`p1.external_standards`・`p1.procedure_trace`・`p1.gate_efficacy`・`p1.test_double_fidelity`・`p1.main_path_observation`・`p1.provenance`・`p2.diagnose`・`p2.rejudge`・`spec.write`・`spec.review`・`spec.revise`・`spec.approve`・`spec.freeze`（`spec.check` は judge の後の段。下の「人が入れる前提の直し」の 2）。keep-essence の 12（今の works の `works/docs/keep-essence.md`）のうち judge が持つ物: 欠陥の探し方の数え直し（試しの側）・世界の解。

## 作る物

### ブロックのフォルダ `workflows/judge/`

- `works-factory-judge.yaml`（工程の名も `works-factory-judge`。E9）。`inputs:` に `start`・`baseline`・`objection`（約束のとおり）と `prior_failures`（約束に無い入力。既定 `"null"`。下の「人が入れる前提の直し」3）、`returns: verdict`・`outcome_field: ready`。工程の頭に `interactive`・`worktree`・`container`・`evidence_policy`・`mutates_checkout` を書かない（include で差し込まれるブロックでは読み込みの時に警告つきで落とされる。止めた Archon の `guides/authoring-workflows.md` の「Composed behaviour」）。仕様の関所の `approval:` は線の `interactive: true` で開く。
- 節（id・種類・何をするか。役の節は全部 `idle_timeout: 1728000000`、script の節は全部 `timeout: 1728000000`、`loop_group` は全部 `timeout: 1728000000`・`max_iterations: 3`・`until_bash: test $<受け付けの節>.output.done = true`、`fresh_context` は旧 YAML の値（仕様の 3 つの輪 `spec-loop`・`spec-review-loop`・`spec-revise-loop` と `rejudge-loop` は `true`、ほかは `false`））:
  1. `intake`（script・`mutates_checkout: false`）: 始めの記録を開き、依頼の行（始めの記録の `request_file`。無ければ `input.request_file`。今の works の `request.json` の形）の型を照らす（元 `accept.check_request` と写しの rules の `check_inputs`・`add` の規則）。入力 `objection` が空でなければ再審の道。機能の切り替えは始めの記録の `features_cut`（無ければ今の works の既定と同じ `["judge_verify"]`）から世界の解（元 `.shared/core/entry.py` の `FEATURES` の世界の解の語）と判定の裏取り（`judge_verify`）を、仕様の段は始めの記録の `input.spec`（無ければ false）から決め、作業ツリーの姿（`lib/accept.tree_state`）を置く。返り（`output_format`）: `go`・`mode`（`judge`・`rejudge`）・`spec`・`world`・`verify`・`reason`。依頼が型に通らなければ `go: false` で、AI を 1 つも起こさない。
  2. 仕様の段（`when: "$intake.output.spec == true"`。再審の道では走らない）:
     - `spec-loop`（loop_group）: `spec`（役。要件と受け入れテストを書く。テストのファイルだけを作業ツリーに書くので `mutates_checkout` を書かない（旧のとおり））→ `spec-accept`（script。元 `spec_write_output` の照らし: 鍵が一意・受け入れ条件が要件を指す・テストのファイルに名前と Given/When/Then が在る）
     - `spec-review-loop`（loop_group）: `spec-review`（役・`mutates_checkout: false`）→ `spec-review-accept`
     - `spec-revise-loop`（loop_group。審査の穴が開いている時だけ。元の条件 `spec_revise_due`）: `spec-revise`（役。`spec` と同じく書く）→ `spec-revise-accept`
     - `spec-ask`（script・`mutates_checkout: false`）: 関所に見せる文を組む（元 `specblk.gate_text`。要件・受け入れ条件・各テストのファイルと名前・承認の後に機械が走らせる `run` の字面）。
     - `spec-gate`（`approval:`・`idle_timeout: 1728000000`）: `message` は `$spec-ask.output.message`。`decisions` は通す語 `approve`・`continue` と止める語 `stop`・`reject`（止めた Archon は明示の `decisions` に `approve` を要る。`guides/approval-nodes.md`。語は今の works の `specblk.GATE_GO`・`GATE_STOP` と `lib/answer.py` の `VERBS`）。形は ASF の `W/merge-queue/archon-merge-queue.yaml`:179-225 に合わせる。
     - `spec-freeze`（script）: 関所の答えを `{ from: "$spec-gate.output", if_skipped: null }` で受ける（`{decision, text}`）。通す語なら各受け入れ条件の `run` を走らせて承認の時点の終了の値を取り、テストのファイルの sha256 を固め、仕様を `judge/spec.json`（今の works の記録の `process.spec` の形: `requirements`・`acceptance`（各 `key`・`requirement`・`file`・`name`・`run`・`sha256`・`exit_at_approval`）・`approval`）に書き、受け入れ条件を依頼の行として診断の材料に積む（元 `spec_freeze`）。止める語なら止める: 答えの文が `request:` で始まれば止め札（持ち主の決め `report-on-stop`）で、止めの理由は `request:spec-gate`（今の works の `specblk.FLAG_BY_PREFIX`・`report.REQUEST_BY` の頭）、ほかは人の止めで `human:spec-gate`（`report.HUMAN_BY` の頭）。2 つの語は分ける（report が `stopped_by_request` と `stopped_by_human` に分ける）。
  3. `pr-check`（script・`mutates_checkout: false`）: 開いている PR を `lib/ghreads`・`lib/forge` の読みだけで集め、この run の差分・依頼の場所との交差の hunk を出す（元の `p0.parallel_pr` の機械の道。元 `.shared/core/graphloops/scripts/parallel-pr.py`・写しの rules の `parallel_pr_plan`・`parallel_pr_reply`）。機械で決められない時だけ `go_role: true`。
     - `pr-check-loop`（loop_group。`when: "$pr-check.output.go_role == true"`）: `pr-check`（役。gh は読むだけ）→ `pr-check-accept`（元 `prcheck.check_excluded`）。外す hunk は `judge/pr-excluded.json`、申し送りの下書きは `judge/pr-downgrades.json`（gh に投稿しない。今の works と同じ）。
  4. `premises-loop`（loop_group）: `premises`（役）→ `premises-accept`（元 `measured_needs_output`: `kind=実測` の行は走らせたコマンドと出力が要る・作業ツリーが変わっていない）。受けた制約を `judge/premises.json` に書く。
  5. `purpose-prep`（script・`mutates_checkout: false`）→ `purpose-loop`（loop_group）: `purpose`（役）→ `purpose-accept`（元 `purpose.check_purpose` の中身と `_source_files_errors`）。目的の役には前の run の判断（前の失敗の行）を外した依頼の写しだけを渡す（`lib/carry` の `without_prior`。持ち主の決め `premises-purpose` の当て方「目的の役に前の run の判断を見せないことを機械で縛る」）。
  6. 世界の解（`when: "$intake.output.world == true"`）: `world-intake`（script）→ `world-classes-loop`（loop_group: `world-classes` 役 → `world-classes-accept`）→ `world-plan`（script）→ `world-judge-loop`（loop_group: `world-judge` 役。web の検索と取得だけ（持ち主の決め `web-split`）→ `world-judge-accept`: 抜き書きを `lib/webget` で取り直した本文と `lib/worldcheck.verify` で照らし、字のまま本文に無い抜き書きの根拠を外す）→ `world-finish`（script。世界の解の行を `judge/world.jsonl` に、段の控えを隣の `judge/world-state.json` に）。網が使えない run も止めない（持ち主の決め `world`「web は必須にしない」）。
  7. 素材集め: `material-route`（script・`mutates_checkout: false`。素材ごとの要否を元の `*_due` の条件で決める。条件が読む値の作り方は下の「lib/ に持ってくる部品」の `due_view`）→ 素材ごとの loop_group 11 本を同じ層に並べる（`<名>-loop`。各々 `when: "$material-route.output.<名> == true"`。本体は `<名>-prep`（script）→ `<名>`（役）→ `<名>-accept`（script））。11 本: `prior-decisions`・`purpose-review`・`local-review`・`consistency-bypass`・`hygiene`・`external-standards`・`procedure-trace`・`gate-efficacy`・`test-double-fidelity`・`main-path-observation`・`provenance`。受け付けの中身は元の写しの rules（`external_rankings`・`main_path_observed`・`gate_arms_all_red`・`purpose_findings_cited`・`local_review_covers_lenses`・`_cite_errors`）と `diverted.mark_unseen`（`/code-review` の所見を受け取れなかった時の印）。各々は自分の名のファイル（`judge/material-<名>.json`）にだけ書く。元の盤面の錠（`material._locked`）は持ち込まない（持ち主の決め `no-queue`）。並べた素材の輪は、後ろの節が `with:` で結ばずに、各々が通った時に書いたファイルを読む（落ちた節に結んだ `with:` は `if_skipped` でも例外になる。止めた Archon の `dag-executor.ts`:519-534）。
  8. `diagnose-prep`（script・`mutates_checkout: false`・`trigger_rule: all_done`。素材の 11 本の輪と前の段の後の合流で、どれかが落ちても組む。前の節の返りは `with:` で結ばず、各段が書いたファイルを読み、無いファイルは「走っていない」として材料に書く）: 判定役が読む材料を `judge/diagnose-brief.md` に組む（元 `blk-judge/lib/judgebrief.py` の書き直し。節の並びは下の「lib/ に持ってくる部品」の `brief`）。対象差分を `judge/diff.patch` に書く。
  9. `diagnose-loop`（loop_group）: `diagnose`（役・`command: diagnose`）→ `diagnose-accept`（script。作業ツリーと HEAD が変わっていない（元 `_judge_tree_unchanged`）→ class_query の例の試し（`querytest.problems`）→ 先例の出どころが世界の解の行に在る（`lib/worldmark.ref_problems`）→ 元 `judge_output` の規則 → 目的の外の所見を分ける（`lib/outpurpose`）→ 受けた判定を `judge/judgment.json` に書く）。
  10. 判定の裏取り（`when: "$verify-prep.output.go == true"`）: `verify-prep`（script。開いた単位が 2 つ以上で機能が入の時だけ go）→ `judge-verify`（役。単位ごとの裏取りと単位どうしの相乗りを `Agent` の下請けで並べる。元のまま）→ `verify-merge`（script。下請けの答えを `judge/judge-verify.json` にまとめる。単位は消さない）。
  11. 再審の道（`when: "$intake.output.mode == 'rejudge'"`。2〜10 は走らない）: `rejudge-prep`（script。同じ run の置き場にこのブロックが 1 回目に書いた `judge/judgment.json`・`judge/diagnose-brief.md` ほかを読み、入力 `objection` と並べて `rejudge/brief.md` を組み、単位の前の写しを置く）→ `rejudge-loop`（loop_group: `rejudge`（役）→ `rejudge-accept`（元 `rejudge_output` の規則と、単位の前後の差 `rejudge/rejudge-diff.json`））。再審の結果は `rejudge/judgment.json` に書き、1 回目の物を上書きしない。1 回目のファイルが無ければ（判定の道を通っていない run）、再審せずに止める（元の語 `rejudge-session`）。再審の役は新しい会話で起き、保存した 1 回目の判定と材料を読む（下の「Archon で書けない所」の狭め）。
  12. `verdict`（script・`mutates_checkout: false`・返す節。中で起きた誤りを全部捕まえ、落ちずに `ready: false` と訳の `stop_reason` を返す（線は落ちた返す節の先へ進めない）。`trigger_rule: all_done`。前の段が飛ばされても落ちても諦めても組む（`none_failed_min_one_success` は上の節が 1 つでも落ちると返す節ごと飛ばす。止めた Archon の `guides/authoring-workflows.md`:427-430・`dag-executor.ts`:1989-1997）。前の節の返りは `with:` で結ばず、run の置き場のファイルを読む）: 下の「返りの約束」の欄をちょうど返す。止めの道（`intake` の `go: false`・受け付けの諦め・仕様の関所の止め・再審の止め）でも、`judgment`・`purpose` の指し札が指す先と、公開の隣のファイルを空の形で書いてから返す（指し札は Archon が節の終わりに先が在って空でないかを照らすため）。
- 役の節の設定（旧 YAML の値を写す。`tests/workflows/test_judge.py` が表で縛る）:
  - `model`・`effort`: `diagnose`・`rejudge`・`judge-verify`・`world-classes`・`spec-review` は `opus`/`high`、`spec`・`spec-revise` は `opus`/`medium`、ほか（`pr-check`・`premises`・`purpose`・`world-judge`・素材 11 本）は `sonnet`/`medium`。
  - `settingSources: [user]` と `sandbox`: 全部の役。`sandbox` の中身は役ごとに旧 YAML のまま（`{enabled: true, allowUnsandboxedCommands: false}` が基本。`pr-check`・`prior-decisions`・`local-review`・`external-standards`・`procedure-trace` は `failIfUnavailable: true`・`excludedCommands`・`network.allowedDomains: []` を足した形、`gate-efficacy`・`test-double-fidelity`・`main-path-observation`・`provenance` は `enableWeakerNetworkIsolation: true`・`network.allowedDomains: ['*']`・`allowLocalBinding: true`・`filesystem.allowWrite: ['/']` を足した形）。`excludedCommands` の中の今の works の名（`works-gh:*`）は、works-factory の読むだけの gh の口の名（`bin/_lib/no-post-bin/works-gh`）に合わせる。
  - `context: fresh`: `judge-verify`・`rejudge`。
  - `allowed_tools`: 旧 YAML のまま（`world-classes` と `hygiene` は空の配列、`judge-verify` は `Agent`・`Write` を含む、`local-review` は `Skill`・`Agent` を含む）。
  - `mutates_checkout: false`: 旧 YAML で `false` だった役（`diagnose`・`judge-verify`・`rejudge`・`purpose`・`spec-review`・`world-classes`・`world-judge`・`purpose-review`・`consistency-bypass`・`hygiene`）。旧で書いていなかった役（`spec`・`spec-revise`・`pr-check`・`premises`・`prior-decisions`・`local-review`・`external-standards`・`procedure-trace`・`gate-efficacy`・`test-double-fidelity`・`main-path-observation`・`provenance`）は書かず、今の works と同じく受け付けの script が作業ツリーの姿（`lib/accept.tree_moved`）を比べて、書いた返答を拒む（下の「人が入れる前提の直し」1）。
- `commands/`（元の指示書を移し、盤面・包み（`works-node:` の印・写しの事情）・「指示書のファイルを Read せよ」の 2 段の描き方だけを、Archon の書き方（`$INPUTS.<名>`・`$<節>.output`・指し札のパスを Read）に直す。中身の規則は変えない）:
  - `diagnose.md`（元 `blk-judge/commands/diagnose.md` と `p2.diagnose.md` の手順・出力の決まり。材料は `$diagnose-prep.output.brief_file` を Read）
  - `rejudge.md`（元 `blk-rejudge/commands/rejudge.md` と `p2.rejudge.md`）
  - `judge-verify.md`（元 `blk-judge/blk-judge.yaml` の `judge-verify` の節の指示）
  - `premises.md`・`purpose.md`・`pr-check.md`・`world-classes.md`・`world-judge.md`（各旧ブロックの `commands/`）
  - `spec.md`・`spec-review.md`・`spec-revise.md`（元 `blk-spec/commands/spec-write.md` ほかと `blk-spec/prompts/spec.*.md`）
  - `material-prior-decisions.md`・`material-purpose-review.md`・`material-local-review.md`・`material-consistency-bypass.md`・`material-hygiene.md`・`material-external-standards.md`・`material-procedure-trace.md`・`material-gate-efficacy.md`・`material-test-double-fidelity.md`・`material-main-path-observation.md`・`material-provenance.md`（元 `blk-material/commands/<名>.md` と `p0.*`・`p1.*` の指示書）
  - 観点の正本: 元の指示書が `{{inputs.review_md}}` で観点の正本を読ませていた役（`diagnose` と素材の `local-review`・`consistency-bypass`・`hygiene`・`external-standards`・`procedure-trace`）には、`<名>-prep`（`diagnose` は `diagnose-prep`）が返す `review_md`（`boundary.lib_root()` の下の `REVIEW.md` の絶対パス）を Read させる。対象のリポジトリ側の観点（元 `{{?inputs.repo_review_md}}`）は、対象の根に `REVIEW.md` が在ればそのパスを渡す。
  - 役の前付けの本文（`agents/judge.md`・`investigator.md`・`inspector.md`）は、元が役に貼っていたとおり各指示書の頭に入れる。
  - 出し直しの頭: 受け付けが拒んだ理由は、役の節の `with:` に `"$LOOP_PREV.<受け付けの節>.output.reason"` を結んで `$INPUTS.reject_reason` で受け、指示書の頭に元 `rolekit.with_reject` の文で出す（`$LOOP_PREV` は `with:` に結べる。ASF の `W/merge-queue/archon-merge-queue.yaml`:197・218）。1 周目は空の字。
- `scripts/`: 上の script の節ごとに 1 本（`intake.py`・`spec_accept.py`・`spec_ask.py`・`spec_freeze.py`・`pr_check.py`・`pr_accept.py`・`premises_accept.py`・`purpose_prep.py`・`purpose_accept.py`・`world_intake.py`・`world_classes_accept.py`・`world_plan.py`・`world_judge_accept.py`・`world_finish.py`・`material_route.py`・`material_prep.py`・`material_accept.py`・`diagnose_prep.py`・`diagnose_accept.py`・`verify.py`・`rejudge_prep.py`・`rejudge_accept.py`・`verdict.py`。素材の 11 本は `material_prep.py`・`material_accept.py` を `with:` の `role` で共にする。仕様の 3 つの受け付けは `spec_accept.py` を `with:` の `role` で共にする）。どれも入力を読み、lib/ の関数を呼び、`boundary.returns` で返すだけ。受け付けの script の返りは `{ok, done, reason}`。拒否の数えは`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/rolekit.py` の `with_done`（拒否を `judge/rejects-<役>.json` に積み、`GIVE_UP_AFTER` 回目の拒否で `done: true`）。
- `fixtures/`（筋書き。`tests/workflows/test_judge.py` が `tests/archon.py` の使い捨ての木で `archon workflow test` で回す。筋書きが確かめるのは配線だけ: 止めた Archon の dry-run では関所の節は自ずと済み、`until_bash` は走らず輪は 1 周で済んだ扱い、差し替えは節ごとに 1 つの値、`exec-code` は空の置き場で走る。振る舞いは下の「試験」の子のプロセスの試験が持つ）:
  - `pass.stubs.yaml`: 判定の道を通しで。`reached` に `diagnose-accept`・`verdict`。`verdict` の差し替えが `ready: true`。
  - `bad-request.stubs.yaml`: `intake` が `go: false`。役の節が 1 つも `reached` に無く `verdict` に届く。
  - `judge-gave-up.stubs.yaml`: `diagnose-accept` の差し替えが 3 回目の拒否の後の状態（`ok: false`・`done: true`）。輪が落ちずに `verdict` まで届く。
  - `no-open-units.stubs.yaml`: 受けた判定に開いた単位が無い後の状態。`verdict` に届く。
  - `spec-on.stubs.yaml`: `intake` の `spec: true` で仕様の段の節が `reached` に在り、`spec-freeze` の後に判定の道へ進む。
  - `world-offline.stubs.yaml`: 世界の解が網なしで終わった後の状態でも判定まで進む。
  - `material-peer-stop.stubs.yaml`: 素材の 1 本が諦めた後の状態でも、ほかの素材の輪と判定に届く（元 `blk-material/fixtures/peer-stop.stubs.yaml` の訳）。
  - `rejudge.stubs.yaml`: 再審の道（入力 `objection` を `fixture.inputs` で与える）。判定の道の役が `reached` に無い。

### lib/ に持ってくる部品（このブロックだけが使う物）

lib-port の「移し方」1〜6 のとおり、元の名・元の中身のまま置き、盤面（`board`・`script_io`・`scopes`・`entry`・`adapter`・`rolekit` の盤面の側・`node_marker`・`flow_adapter`・`fixture`・`tree_run`・`seat`・`nodemeta`・`ticket`・`replycontract`・`graphmap`・`leftovers`・`versions`・`halt`・`chain`、`graphloops/engine` の `board`・`advance`・`commands`・`validator`・`record`・`role_run`・`rules`・`declared`）に届く物は、次の 2 つの形だけで扱う（8 つのブロックで同じ決め）:

- (a) 継ぎ目の直し: 持ってきたファイルの中で、盤面・Archon・持ってこない部品へ届く 1 か所の呼び出しを、引数か lib/ のモジュールの呼び出しに替える。関数の名とほかの行は変えない。直した行を全部 PR の本文に並べる。
- (b) 書き直し: 関数の中身がほぼ盤面の読みの時は、元の関数の名のまま、値かファイルのパスを引数で受ける形に書き直し、新しい lib/ のファイルに置く。docstring の頭に元（`<パス>:<行>`）を書き、試験は元の試験の場面を写す。全部 PR の本文に並べる。
- 盤面の偽物（盤面の形をまねた物）はブロックをまたいで持たない。どちらにも当たらない関数は、lib-port の「移し方」2 と同じに外す。下の「外す物」は見込みで、一覧の外でも届く物が見つかれば同じに扱って PR に足す。

元の名で持ってくる物:

- `works/blk-world/lib/worldblk.py` → `lib/worldblk.py`。外す見込み: `_switch`（script_io）。継ぎ目の直し: `_need` が投げる `board.BoardGap` を lib/ の例外（`worldblk` の中で定義済みの物が無ければ `ValueError`）に替える 1 行・拒否の控えの読み書き（`rolekit.rejected`・`with_done`・`given_up_reason`・`with_reject`）は`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/rolekit.py` を読む形のまま（同じ名なので行は変わらない）。`_prep`・`_close_round`・`_why_failed` は rolekit の純な口だけを使うなら残し、盤面の側に届けば外す。残る見込み: `place`・`class_id`・`_findings`・`_purpose`・`fetch`・`intake`・`classes_prep`・`class_problems`・`classes_accept`・`plan`・`_judge_rows`・`judge_prep`・`judge_problems`・`_excerpts`・`_check_excerpts`・`judge_accept`・`_rows`・`finish`。
- `works/blk-world/lib/worldcheck.py` → `lib/worldcheck.py`（外す物は無い見込み。`webget` だけを読む）。
- `works/.shared/core/premises.py` → `lib/premises.py`。外す見込み: `_tree_unchanged`・`check_premises`（DiskBoard・engine.rules。中身は (b) で `lib/judge_accept.py` へ）と頭の `from board`・`import script_io`・`from engine.rules`。残る見込み: `Broken`・`claims`・`request_items`・`_covering`・`_one_line`・`collect`。
- `works/.shared/core/purpose.py` → `lib/purpose.py`。外す見込み: `_post_check`・`refuse_if_frozen`・`check_constraints`・`_tree_unchanged`・`check_purpose`・`read_purpose`（中身は (b) で `lib/judge_accept.py` へ）。残る見込み: `_source_files_errors` と定数。
- `works/.shared/core/prcheck.py` → `lib/prcheck.py`。外す見込み: `_output_format`・`OUTPUT_FORMAT`（`accept.role_schema`）・`open_board`・`_waiting`・`run_helper`・`snapshot`・`take`・`_accepted`・`drafts`・`collect`・`_artifacts`・`main_snapshot`・`main_collect`。残る見込み: `Refused`・`_anchored`・`check_excluded`・`_write`・`downgrades`・`head_downgrades`（既定の読み先 `PACK` の `darkfactory/downgrades.json` は lib/ に無い。読み先を引数で渡す継ぎ目の直しで済まなければ 2 つとも外す）。言い換え: Archon の字のコメント。
- `works/blk-judge/lib/judgeverify.py` → `lib/judgeverify.py`。外す見込み: `answers_dir`（adapter）・`_halted`・`_clear`・`prep_on`・`merge_on`・`prep`・`merge`・`_check_unit`・`_check_synergy`（盤面の `b`。中身は (b) で `lib/judge_accept.py` へ）と、`answers_dir` にしか使われない `answer_file`・`synergy_file`。残る見込み: `output_format`・`unit_schema`・`synergy_schema`・`answer_in`・`open_units`・`_unit_row`・`_head`・`_initial`・`_load`・`_read_json`・`_write_json`。
- `works/blk-spec/lib/specblk.py` → `lib/specblk.py`。外す見込み: `_open`・`_stopped`・`_pending`・`route`・`render`・`prep`・`_rejects`・`_reject`・`take`・`refuse`・`ask`・`answer`・`_counts`・`collect`・`output_format`・`node_of`。残る見込み: `GATE_GO`・`GATE_STOP`・`GATE_STOP_NOTE`・`FLAG_BY_PREFIX` ほかの定数・`snapshot_name`・`_write_json`・`_read_json`・`gate_text`・`parse_gate`・`_head`。
- `works/.shared/core/diverted.py` → `lib/diverted.py`。外す見込み: `report_lines`（`scopes`）と頭の `import scopes`。残る見込み: `mark_unseen` と定数（`LENS_FILE`・`FORK_LENSES`・`UNSEEN_TAG`）。

持ってこない元のファイル（中身は (b) で `lib/judge_accept.py` に書き直すか、使わない）: `works/blk-judge/lib/judgebrief.py`・`judgetake.py`・`works/.shared/core/rejudge.py`・`works/blk-material/lib/material.py`（盤面を外すと、どの script も呼ぶ関数が残らない）、検証器 `works/.shared/core/scripts/review-record.py`・`record_common.py`（形は Archon の `output_format` が照らし、規則が引く表と関数は (b) で移す）、読んだ証拠 `reads.py`・`record-read.py`（未決 U6 を待つ）。`docs/plans/2026-10-12-blocks/prereq.md` の issue が置く物（`lib/querytest.py`・`lib/rolekit.py`・`lib/REVIEW.md` ほか。下の「依存」）は作らない・直さない。

新しく書く物（(b) 書き直し）: `lib/judge_accept.py`（`docs/design.md` の能力の名 `lib/judge_accept` のファイル）。元の関数の名のまま、値（受けた返答・依頼の行・素材の状態の dict・始めの記録・版・対象の根）かファイルのパスを引数で受ける形に書き直す。関数ごとに docstring の頭に元（`<パス>:<行>`）を書き、規則の中身（文・条件・数）は変えない。2 つの元が同じ名の関数を持つ時は、元のモジュールの名を頭に付ける（例 `material_prep`・`rejudge_prep`）。持つ物:

- 依頼: `check_request`（`accept.py`:456）と、それが通す写しの rules の `check_inputs`（67）・`add`（124）の型の規則。
- 判定: `check_judge`（`accept.py`:504）・`_judge_tree_unchanged`（481）・`judge_output`（rules 2497）と助け `_carried_r1_accounted`（2359）・`_fork_moves_forward`（2404）・`_precedent_gap`（2437）・`_precedent_errors`（2445）・`_awaiting_origins`（2468）・`_declared_route_errors`（2483）、受け付けの流れ `take`・`accept`・`_give_up`・`collect`（`judgetake.py`:74〜160）。
- 判定役の材料（`judgebrief.py` の書き直し）: `section`・`template`・`answers_section`・`brief`（judgebrief.py:60〜112）と `request_text`（`entryshape.py`:140 付近）。`brief` が組む節（この順。各節の見出しは元の定数の字のまま）:
  1. 頭 `judgebrief.HEAD`
  2. 世界の解の行（`lib/worldmark.section`。`judge/world.jsonl` が在る時）
  3. `p2.diagnose.md` の「## 入力」の節（「## 手順」の前まで）を、元が盤面から入れていた値で埋めた物: 素材 15 欄の状態（`judge/materials.json`）・局所の findings と整合性・迂回・外部標準・手順トレースの findings（素材のファイル）・修正依頼の入口（依頼の行と、仕様の受け入れ条件の行）・ゲートの実効性・代役の忠実性・主経路の観測・根拠の出所（素材のファイル）・先行議論の突合・凍結した目的の文（`judge/purpose.json` の `purpose_text`）と実測した制約（`judge/premises.json` の `constraints`）・目的の監査・対象差分（`judge/diff.patch` のパス。始めの記録の `base_rev` から今の HEAD までと未追跡の新規ファイル）と変更ファイル・リポジトリと読む版・観点の正本（`boundary.lib_root()` の下の `REVIEW.md`。対象の根に `REVIEW.md` が在ればそれも）・前の周の独立の目（1 run は 1 周なので「無い」）・defer 台帳（同じく「無い」）
  4. `p2.diagnose.md` の「問いの台帳（questions）」の段（「**前の周の R1 最小性」の前まで）を見出し `judgebrief.LEDGER_HEAD` で。`{{validator.*}}` の穴は下の検証器の表から描く
  5. 依頼と PR の題と本文（始めの記録の `input.pr` が在る時。見出し `REQUEST_HEAD`・`PR_TEXT_HEAD`・`PR_TITLE`・`PR_SUBJECT_HEAD`・`PR_BODY_HEAD`）
  6. 依頼の answers（始めの記録の `answers`。見出し `ANSWERS_HEAD`。`gatemarks.answer_note` で 1 行ずつ）
  7. 前の run の行（入力 `prior_failures` の先。`lib/carry.prior_section` が `PRIOR_HEAD` の節（注意）と `REDESIGN_HEAD` の節（直す穴）に分ける）
- 前提と目的: `check_premises`（`premises.py`:125）・`measured_needs_output`（rules 3010）・`check_purpose`（`purpose.py`:102）。
- 素材: 受け付け `external_rankings`（2973）・`main_path_observed`（2962）・`gate_arms_all_red`（3023）・`purpose_findings_cited`（3274）・`local_review_covers_lenses`（3214）、支度 `material_prep`（`material.py`:376 の `prep` と `render` の値の埋め方）・`_skills`（442）。
- 素材の要否: 条件 `not_request_entry`（1094）・`external_standards_due`（1101）・`provenance_due`（1112）・`_deep`（1121）・`_deep_due`（1129。`procedure_trace_due`・`gate_efficacy_due`・`test_double_fidelity_due` を作る）・`main_path_observation_due`（1162）・`prior_decisions_due`（1173）・`purpose_review_due`（1183）・`parallel_pr_due`（1198）・`spec_revise_due` と、助け `_entry_marked`（167）・`request_entry`（178）・`entry_first_fix`（194）・`touches_procedures`（372。`PROCEDURE_PATTERNS`）・`prev_fix_touched`（379）・`purpose_review_unvetted`（413）・`purpose_sources_changed`（439）・`gates_merge`（771）・`_first`（1028）・`_eq_true`・`_fix_says`（1042）・`_escalated`（1046）・`_because`（1050）・`_touched`（1055。`gates_touched`・`seams_touched`・`user_path_touched`）。条件はどれも見方 `v(鍵, 既定)` を引数に取るので、その見方を作る `due_view(start, purpose, changed_files)` を足す（このモジュールの中だけで使う。ほかのブロックへ渡さない）。鍵ごとの値: `round` は 1（1 run は 1 周。持ち主の決め `carry`）・`prev.*` は全部 None・`loop.escalated` は False・`record.process.request_entry` は始めの記録の `input.diff.empty` が真で `input.requests` が 1 以上の時だけ印の形（今の works の入口と同じ。差分の空の run で印が立つ）・`loop.request_fixed_at` は None・`out.p0.base.touches_gates`・`touches_external_seams`・`touches_user_path`・`touches_security_surface` は true（今の works の `board.py`:550 の `base_output` と同じ。機械は差分の柵を決められないので役を起こす側に倒す）・`loop.changed_files` は対象差分の変更ファイル（`lib/accept.touched_files`）・`loop.gates` は始めの記録の `gates`・`out.p0.purpose.source` は `judge/purpose.json` の `source`・`loop.last_material.*` は None。
- 再審: `rejudge_output`（rules 3186）と、再審の支度と受け付けの流れ `rejudge_prep`・`rejudge_take`・`rejudge_collect`（`rejudge.py` の `prep`・`take`・`collect`。単位の前の写しと前後の差 `rejudge-diff` を作る所。会話の続きを確かめる `session_ready` は持たない——下の「Archon で書けない所」）。
- 仕様: `_spec_errors`（3908）・`spec_write_output`・`spec_review_output`・`spec_revise_output`（3931〜3958）・`spec_freeze`（4010。記録に固める所と依頼の行を積む所）・`_file_sha`（3896）・`_spec_run`（3959）。
- 判定の裏取り: `prep_on`・`merge_on`・`_check_unit`・`_check_synergy`（`judgeverify.py`:202〜305）。
- 単位の目録: `structure_units`・`_unit_file_paths`（`darkfactory/lib/line_edge.py`:361 ほか）。開いた単位を全部 `{id, paths, summary}` にし、対象の根の中のファイルだけを `paths` に残す。`paths` が空になった単位も落とさない（`paths: []` で返す。構造の目に回すかは plan が決める）。
- 規則が使う助け: `_run_query`（3307）・`_cite_errors`（3471）・`_count_in_version`（3612）・`blank`（480）・`_keys_once`（3067）と、検証器 `review-record.py` の、規則が引く表と関数（`LABELS`・`QUESTION_KINDS`・`QUESTION_STATUS`・`QUESTION_FIELDS`・`ASKING`・`NO_OPEN_ORIGIN`・`MATERIALS`・`STATUS`・`REVIEWS`・`is_open`・`targets`・`origin_not_awaiting`・`settled_state_errors`）。表の字は元のまま写す。

### 試験

- `lib/tests/test_world_check.py`（元 `works/tests/test_world_check.py`。外す物は無い見込み。残る見込み 23）
- `lib/tests/test_blk_world.py`（元 `works/tests/test_blk_world.py`。worldblk の残る関数を見る試験だけ残す。stubfold・prepkit・blockblind・旧 YAML を回す試験と、外した関数の試験は外す）
- `lib/tests/test_diverted.py`（元 `works/tests/test_diverted.py`。`mark_unseen` を見る試験だけ残す。`material` と `report_lines` を使う試験は外す）
- `lib/tests/test_judge_accept.py`（新）: `lib/judge_accept.py` の関数ごとに、元の試験（`test_blk_judge.py`・`test_blk_premises.py`・`test_blk_purpose.py`・`test_blk_material.py`・`test_blk_spec.py`・`test_rejudge.py`・`test_judge_verify.py`・`test_structure_units.py`・`test_accept.py` の `TestJudge`・`TestIntake`）が盤面の上で確かめていた場面を、値を渡す形に写す。各試験の docstring に元の試験の名を書く。少なくとも: 単位のラベルが表の外なら拒む・開いた単位の why_chain が足りないと拒む・class_query の例が当たらないと拒む・先例の出どころが世界の解の行に無いと拒む・問いの種類と状態の欄の欠け・判定役が作業ツリーを変えたら拒む・`kind=実測` の制約にコマンドの出力が無いと拒む・受け入れ条件のテストに Given/When/Then が無いと拒む・再審の答えの語が 3 語の外なら拒む・判定の裏取りが単位を消さない・単位の目録（根の中のファイルだけを順に重ねずに残し、ディレクトリ・glob・絶対パス・根の外・無いファイルを捨て、`paths` が空の単位も残す）・素材の要否（差分の空で依頼の在る run は local-review・consistency-bypass・hygiene・external-standards・provenance・procedure-trace・gate-efficacy・test-double-fidelity・main-path-observation を回さない、prior-decisions は回す、purpose-review は目的の出典が writer の要約の時だけ回す、差分の在る run は回す）・`brief` が上の 7 つの節をこの順に出し、目的の役の材料には前の失敗の行の節が無い。
- 元の `test_blk_premises.py`・`test_blk_purpose.py`・`test_blk_spec.py`・`test_blk_spec_gate.py`・`test_judge_verify.py`・`test_rejudge.py`・`test_blk_judge.py`・`test_blk_material.py`・`test_blk_rejudge.py`・`test_structure_units.py` は、元の名では置かない（どれも盤面・stubfold・prepkit・linekit・旧 YAML を回す形か、持ってこない部品を読む形）。場面は `test_judge_accept.py` と `tests/workflows/test_judge.py` に写し、写した先を PR の本文に並べる。
- `tests/workflows/test_judge.py`:
  - 筋書き: issue #47（P0）の `tests/archon.py` の助けで、`workflows/judge/` と `workflows/.shared/` だけを置いた使い捨ての木を組み、`archon workflow test` で `fixtures/` の筋書きを全部回す（筋書きごとに名のある試験。止めた Archon の源か bun が無ければ `skipTest("Archon の源が無い: ...")`）。同じ木で `archon validate workflows` に `works-factory-judge` の誤りも警告も無い。
  - YAML の形（PyYAML で読み、Archon を起こさない）: 返す節 `verdict` の `output_format` が「返りの約束」の 10 欄をちょうど持ち、全部 `required`・`additionalProperties: false`・`outcome_field: ready`・`ready` は boolean。工程の頭に `interactive`・`worktree`・`container`・`evidence_policy`・`mutates_checkout` が無い。`spec-gate` が `approval:` で `decisions` に `approve`・`continue`・`stop`・`reject` を持ち、`spec-freeze` が答えを `if_skipped: null` で受ける。`loop_group` が全部 `max_iterations: 3` で `until_bash` が受け付けの `done` を見て、`fresh_context` が上の表のとおり。素材の輪がちょうど 11 本で `commands/material-<名>.md` と 1 対 1。役の節の `model`・`effort`・`settingSources`・`sandbox`・`context`・`allowed_tools`・`mutates_checkout` が、試験の中の表（上の「役の節の設定」。旧 YAML から写した値）と合う。目的の役（`purpose`）の節の `with:` と `commands/purpose.md` が、前の失敗の行・前の run の判定・`judgment` を参照しない。工程の `inputs:` が `start`・`baseline`・`objection`・`prior_failures` の 4 つで、`prior_failures` が既定 `"null"` を持つ。観点の正本を読む役の指示書が `review_md` を読む。
  - script の振る舞い（子のプロセスで `scripts/<名>.py` を走らせる。環境に `INPUTS_<名>`・一時の `ARTIFACTS_DIR`・`WORKFLOW_ID` を置き、`boundary.lib_root()` が届く形で起こす）:
    - 受け付けの輪: `diagnose_accept.py` に型の通らない返答を 3 回渡すと、1・2 回目は `{ok: false, done: false}`、3 回目は `{ok: false, done: true}` で、`judge/rejects-diagnose.json` に 3 行在る。各回の標準出力を `until_bash` の字（`test $X = true` の `$X` を返りの `done` に置き換えた物）として `sh -c` で走らせると、3 回目だけ終了の値 0。
    - 通る返答で `judge/judgment.json` が今の works の形で書かれ、`premises.json`・`judge-verify.json`・`pr-excluded.json`・`materials.json` が同じフォルダに在る。
    - `spec_freeze.py` に `{"decision": "stop", "text": "要らない"}` を渡すと止めの理由が `human:spec-gate`、`{"decision": "reject", "text": "request: 札"}` を渡すと `request:spec-gate`。`{"decision": "approve", "text": ""}` で `judge/spec.json` に `sha256` と `exit_at_approval` が入る。
    - `intake.py` に型の通らない依頼を渡すと `go: false`。続けて `verdict.py` を走らせると `ready: false`・`stop_reason` が依頼の語で、`judgment`・`purpose` の指し札の先のファイルと公開の隣のファイルが在り、空でない（空の形の JSON）。受け付けの諦めと仕様の止めの道でも同じ。
    - 開いた単位が無い判定で `verdict.py` が `ready: false`・`stop_reason: ""`。
    - 再審の道: 1 回目のファイルが無い時に `rejudge_prep.py` が止め（語 `rejudge-session`）、在る時に `rejudge/brief.md` を書く。
    - 素材の 1 本の受け付けが諦めても、`material_route.py` の後の `diagnose_prep.py` が残りの素材のファイルで材料を組む。
    - 返す節は落ちない: `verdict.py` に壊れた入力（`start` が JSON でない・指し札の先が無い・`judge/` が空・ファイルが壊れた JSON）を渡しても、終了の値 0 で、`output_format` に合う `ready: false` と訳の `stop_reason` を返す（線は落ちた返す節の先へ進めない）。

## 返りの約束（`docs/design.md`「ブロックの返りの約束」の `judge` の返りのまま）

- 返す節 `verdict`・`outcome_field: ready`（ASF の `W/triage/archon-triage.yaml` の形）
- 入力（`with:`。工程の `inputs:` に宣言する。値は字で届く。指し札と null は JSON の字）:
  - `start` ← `$start.output.record`（始めの記録。読む欄は今の works の `start.json` の欄（`blk-entry/schemas/start.schema.json`）。欄が無い時は既定の値で読む: `request_file` は `input.request_file`・`""`、`policy_md` は `""`、`features_cut` は `["judge_verify"]`、`input.spec` は false、`answers` は `[]`、`gates` は `""`）
  - `baseline` ← `$test-gate-base.output.baseline`
  - `objection` ← `$fix.output.objection`（`rejudge` の時だけ。`judge` では `""`）
  - 約束に無いが要る入力: `prior_failures`（前の run の持ち越しの前の失敗の行の指し札。既定 `"null"`。下の「人が入れる前提の直し」3）
- 返り:
  - `ready`（boolean）: 判定を受け付け、直す単位が 1 つ以上在る。false も正しい終わり → 線 5・report
  - `stop_reason`（string）: ready が false の訳。ready なら `""` → report。語: 機械の諦めと止めは `lib/stopby.py` の語（元の `judge`・`judge-verify`・`material`・`spec`・`premises`・`purpose`・`pr`・`rejudge`・`rejudge-session` と、依頼の型が通らない時に `lib/stopby.declare` で足す語。どれも頭が `works:`）。仕様の関所の人の止めは `human:spec-gate`、止め札は `request:spec-gate`（今の works の `report.py`:173-174 の頭）。開いた単位が無い時は止めでないので `""`。
  - `units`（array）: 単位の目録。項目は `{id, paths, summary}`。開いた単位を全部入れ、`paths` は空の配列でもよい（今の works の `structure-units` の写し方。`lib/judge_accept.structure_units`）→ plan・plan-review・fix・eyes
  - `judgment`（指し札）: `judge/judgment.json`（再審の時は `rejudge/judgment.json`）。中身は今の works の `judgment.json` と同じ形（受けた判定役の返答を `judge_output` が整え、class_query の例を戻した物。頂の欄は `units`・`questions`・`framing`・`one_shot`・`materials_missing`・`carried_r1`・`one_shot_closes`・`precedents`）。止めの道では同じ形の空（`units: []`・`questions: []`・文の欄は `""`・配列の欄は `[]`）→ plan・plan-review・fix・eyes
  - `purpose`（指し札）: `judge/purpose.json`（今の works の `purpose.json` と同じ形: `purpose_text`・`source`・`known_weaknesses`・`source_files`。止めの道では同じ形の空）→ plan-review・eyes
  - `world`（指し札・null 可）: `judge/world.jsonl`（世界の解の行。1 行に 1 つ、`lib/worldmark.rows` が読む形）。取れなかった時・機能が切の時は null → plan・plan-review・eyes
  - `spec`（指し札・null 可）: `judge/spec.json`（今の works の記録の `process.spec` の形）。仕様の段の無い run は null → plan
  - `out_of_purpose`（指し札・null 可）: 目的の外の所見（今の works の `out-of-purpose.json` の形。`lib/outpurpose`）→ report
  - `rejudge_verdict`（string・null 可）: 再審の答え `採る`・`退ける`・`一部採る`。再審でない時は null → 線 7・report
- 指し札の先は今の works のファイルと同じ形で、新しい入れ物の形を作らない。返りの欄は足さない。
- 公開の隣のファイル（ほかのブロックが名のちょうどで開く物）:
  - `judgment` の指し札のフォルダ（`judge/`。再審の時は `rejudge/`）に、今の works と同じ形の次の 4 つを必ず置く（無い時も空の形で置く。再審の時は 1 回目の物の写し）。plan・plan-review・eyes・report は `judgment` の指し札のフォルダからこの名で開く:
    - `premises.json`: 前提の制約 `{constraints: [{text, measured_how, kind, measured_output}]}`（前提の段が走らなかった時は `{constraints: []}`）
    - `judge-verify.json`: 判定の裏取り（今の works の `judge-verify.json` の形。裏取りを回さなかった時は今の works の「回さなかった」の形）
    - `pr-excluded.json`: 並行 PR の外す hunk（今の works の `pr-excluded.json` の形 `{node, excluded}`。外す物が無い時は `excluded: []`）
    - `materials.json`: 素材の状態（今の works の記録の `materials` の形。素材の名 → `{status, …}`、`status` は検証器の表 `STATUS` の語 `found`・`clean`・`carried_over`・`not_applicable`・`awaiting_human`・`not_run`。止めの道では `{}`）
- 内の隣のファイル（このブロックの中だけで読む）: `judge/purpose-means.json`（今の works の `purpose-means.json` の形 `{means: [...]}`）・`judge/world-state.json`・`judge/pr-downgrades.json`・`judge/material-<名>.json`・class_query の例・拒否の控え `judge/rejects-<役>.json`・診断の材料 `judge/diagnose-brief.md`・対象差分 `judge/diff.patch`・`rejudge/` の支度と前後の差。
- 再審の道の返りも同じ形。`purpose`・`world`・`spec`・`out_of_purpose` は 1 回目に書いたファイルを指す札をそのまま返し（同じ run の中の札なので使える）、`units`・`judgment` は再審の後の物。
- 型つきの成果物は無い（`output_type` を書かない）。
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
- 始めの記録は入力 `start`（指し札）で受け、`boundary.resolve` で開いて JSON で読む。入口の入力の形の読みは `lib/startrec.py`。
- 期限: 期限を持つ節（`script:`・`bash:` の `timeout`、`prompt:`・`command:` の `idle_timeout`、`loop:` の `idle_timeout` と `timeout`、`loop_group:` の `timeout`、`approval:` の `idle_timeout`）には全部 `1728000000` を書く（E12）。
- 役の指示書（`commands/`）と `lib/` に、対象の言語・テストの実行器の名を書かない（E13）。持ち主の環境の字（`raiki61`・`/Users/` など）を書かない（E14）。
- 外への書き込み（GitHub・対象のリポジトリの main・人に見える所）は、このブロックでは無い。並行 PR は gh を読むだけで、申し送りは報告の下書きのファイルにする（E6）。仕様の役が書くテストのファイルは作業ツリーへの書き込みで、外への書き込みではない。
- ブロックの YAML と script は、ほかのブロックのフォルダを指さない（E4）。ほかのブロックの返りは `with:` の入力として受けるだけ。
- 筋書き（fixture）は Archon の `workflow test` の形（`fixtures/<名>.stubs.yaml`。予約の鍵 `fixture:`（`expect`・`fail-node`・`reached`・`inputs`・`resolved-text-contains`）と `exec-code:`、残りの鍵は節の id → 差し替えの出力）。筋書きは配線を確かめる物で、振る舞い（3 回の出し直し・関所の止め・諦め・合流）は子のプロセスの試験と lib/ の試験が確かめる。
- Archon の実行ファイルか源が要る試験は、無ければ `skipTest("Archon の源が無い: ...")` で名前つきで見送る（`tests/AGENTS.md`）。
- このブロックが run の置き場に書くファイルは全部 `judge/` か `rejudge/` の下（入力 `objection` で分ける）。

## Archon で書けない所

- 再審の役は判定役の会話を継がない。Archon の会話の分岐（`context: { resume: <節> }`）は同じ工程の上流の節だけを名指せ、`loop_group` の本体では使えず（`guides/authoring-workflows.md` の named resume の段）、別の include（線の `judge` と `rejudge`）の節は名指せない（E4）。この PR は、新しい会話で保存した 1 回目の判定（`judge/judgment.json`）と材料を読ませる形で作る。これは能力の狭めとして扱う（持ち主の決め `no-narrow`）: 持ち主の決め `persona` の決めは「引き継ぎは会話の再開か機械が保存した返答で渡す」で、保存した返答で渡す形はその内に在るが、当て方は「再審は判定役の会話を継ぐ」で、今の works の `rejudge.py`:5-8 は「黙って新しい会話で回す道は無い」と、会話を確かめられなければ止めていた。どちらを取るかは持ち主に聞いている。PR の本文の「狭め」の節に、この 3 つの引用と、新しい会話の形で作ったことを書く。答えが「会話を継ぐ」なら、線が会話の印を渡す形か `docs/polyfills.md` の埋めを後で足す。
- 読んだ証拠（`reads.py`・`record-read.py`）: 未決 U6。この PR では入れない（持ってこない）。判定の役ごとに、元が読ませた必ず読む物の一覧（元 `prcheck.READS` ほか）を PR の本文に書く。
- 3 回で諦める数え: Archon の `loop_group` は周の数を本体の script に渡さない。今の works と同じく run の置き場の拒否の控え（`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/rolekit.py`）で数える（埋めではなく、元の仕組みのまま）。拒否の理由を役へ返すのは `with:` の `$LOOP_PREV`（上の「commands/」）。
- それ以外は無し（`docs/polyfills.md` の P1・P2 は線の物）。

## E11 の 3 つの答え

1. Archon が持っているか: 役と受け付けの出し直しは `loop_group`（`until_bash`・`max_iterations`・`fresh_context`・`$LOOP_PREV` の `with:`）、形の照らしは役の節の `output_format`、人の関所は `approval:`、読むだけの縛りは `mutates_checkout: false`、会話の分けは `context: fresh`。中身の規則（判定の受け付け・実測の出力・抜き書きの照らし・仕様の形・素材の要否）は Archon に無い → lib/。
2. ASF が持っているか: `W/triage`（今の木と突き合わせてから道を決める・`returns: verdict`・`outcome_field: ready`・読むだけの役）と `W/investigate`（根の問い）。素材 11 本・世界の解・前提・目的・再審は ASF に無い。
3. 本当に要るか: 能力の棚卸しの judge の行（並行 PR・前提・目的・定石と web・素材 11 本・仕様の段・根本の診断と受け付け・判定の裏取り・欠陥の探し方の試し・目的の外の所見・再審・名指しと引用・読んだ証拠）。

## 受け入れ

1. 試験を先に入れて赤を見る（lib/ の部品が無い・YAML が無い）。その後で部品と YAML を入れて緑。赤と緑の出力の要約を PR に書く。
2. リポジトリの根からの全部の試験 `uv run --isolated python3 -m unittest discover -s . -t .` が緑。`tests/layers/` の層の試験（その時に在る物全部）も緑のまま。
3. 止めた Archon の源が在る所で、`tests/workflows/test_judge.py` が `tests/archon.py` の使い捨ての木で回す筋書きが全部通り、`archon validate workflows` に `works-factory-judge` の誤りも警告も無い。源が無い所では、その試験は `skipTest("Archon の源が無い: ...")` で名前つきで見送られる。PR には、Archon で回した結果か、回せなかった訳を書く。
4. 持ってきた lib/ のファイルを元と比べた差分が、lib-port の「移し方」1〜5 と (a) 継ぎ目の直しで決めた直しだけ。
5. PR の本文に次を並べる（守りのパスの文書に書く代わり。土台の持ち主が `docs/design.md`・`docs/asf-notes.md` に写す）:
   - lib-port の「移し方」6 の 4 つ（元のパス → 置いた先・外した物と理由・言い換えた行・盤面の物を引数で受ける関数の一覧）と、(a) の継ぎ目の行・(b) の書き直しの関数ごとの元（パス・行・関数名）
   - 採った ASF の型（`docs/asf-notes.md` の「書き方」の 4 行の形）
   - 「能力の棚卸し」と「受け入れの一覧」のこのブロックの行ごとの、証の試験か筋書きの名
   - 「狭め」の節（上の「Archon で書けない所」の再審）
   - 約束を変える頼み・使いたかった埋め（あれば）
6. judge の個別（`docs/design.md` の作りの順の段 2）:
   - 前提・目的・定石・素材 11 本・診断・裏取り・再審・仕様の段が動く（各々に筋書きか試験が 1 つ以上ある）。
   - 受け付けが拒めば 3 回まで出し直す（`test_judge.py` の受け付けの輪の子のプロセスの試験）。
   - 定石の抜き書きが出どころに在ることを機械が照らす（`lib/tests/test_world_check.py` と `test_blk_world.py`）。
   - 目的の外の所見が持ち越しの行になる（返り `out_of_purpose` が `lib/outpurpose` の形のファイルを指す）。
   - 目的の役に前の run の判断が届かない（`test_judge.py`・`test_judge_accept.py`）。
   - 止めの道でも指し札の先が在る（`test_judge.py`）。

## 範囲

- 作るのは下の「作るファイル」だけ。
- 触らない（守りのパス。ASF の merge が人の手に残す）: `workflows/line/**`・`workflows/.shared/**`・`docs/design.md`・`docs/owner-decisions.md`・全部の `AGENTS.md`・`pack.json`・`README.md`・`MISSION.md`・`engineering.md`・`.github/**`・`harness/**`・`factory/**`・`.factory/**`。
- 触らない（同じ時に別の run が作る）: ほかの 7 つのブロックのフォルダ（`workflows/<ほかの名>/`）と、それらの issue が名指す lib/・試験のファイル。ほかの PR と同じファイルを作らない。
- 触らない（前に入る物）: lib-port・issue #47（P0）・`docs/plans/2026-10-12-blocks/prereq.md` の issue で入った物（本文の「依存」に並べた物）とその試験、`tests/archon.py`、`tests/workflows/__init__.py`、`tests/layers/`、`bin/`、`pyproject.toml`、`docs/`（PR の本文に書く。上の受け入れ 5）。持ってきた部品の中で前に入った部品に直しが要ると分かったら、直さず PR の本文に書く。特に `lib/accept.py` に、lib-port が外した `check_judge`・`check_request` を戻さない（中身は `lib/judge_accept.py` に書き直す）。
- 決めた範囲で能力を落とす直しが要ると分かったら（持ち主の決め `superset`・`no-narrow`）、止めて PR の本文に書く。再審の会話（上の「Archon で書けない所」）は、狭めとして PR の本文に書いた上で作り終える。
- ファイルとフォルダの名は、`factory`・`FACTORY`・`harness`・`.factory`・`archon-` で始めない（E18 の機械の行）。

作るファイル（これより多くも少なくも作らない。`workflows/judge/**` の中身は上の「作る物」のとおり）:

```text
workflows/judge/**
lib/worldblk.py
lib/worldcheck.py
lib/premises.py
lib/purpose.py
lib/prcheck.py
lib/judgeverify.py
lib/specblk.py
lib/diverted.py
lib/judge_accept.py
lib/tests/test_world_check.py
lib/tests/test_blk_world.py
lib/tests/test_diverted.py
lib/tests/test_judge_accept.py
tests/workflows/test_judge.py
```

## 依存

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

- main に在る物（lib-port の PR）: `lib/accept.py`（`tree_state`・`tree_moved`・`snapshot_tree`・`touched_files`）・`lib/carry.py`（`without_prior`・`prior_section`・`PRIOR_HEAD`・`REDESIGN_HEAD`）・`lib/cite.py`・`lib/marks.py`・`lib/outpurpose.py`・`lib/worldmark.py`・`lib/webget.py`・`lib/forge.py`・`lib/ghreads.py`・`lib/promptsection.py`・`lib/stopby.py`・`lib/startrec.py`・`lib/answer.py`（関所の答えの語）・`lib/gatemarks.py`（`answer_note`）・`lib/planmarks.py`（worldmark が読む）・`lib/graphloops/engine/`（`util`・`schema`・`pointers`・`render`）。
- main に在る物（`docs/plans/2026-10-12-blocks/prereq.md` の issue（ブロックの前の共有の部品））: `lib/querytest.py`（class_query の例の試し）・`lib/rolekit.py`（出し直しの輪の口 `with_done`・`rejected`・`given_up_reason`・`with_reject`・`GIVE_UP_AFTER`）・`lib/REVIEW.md`（観点の正本）・`tests/workflows/__init__.py`。
- ほかのブロック: 待たない。ほかのブロックの返りは線の `with:` で入力として届くだけで、このブロックの試験はその形の入力を筋書きと試験の中で作る。

## 人が入れる前提の直し

共通の物（H1〜H5・H10）は本文の「依存」の「前に入る人の直し」。judge だけの物:

1. `workflows/AGENTS.md` の E7 の「機械」の行: 「ブロック `judge`・`plan`・`plan-review`・`eyes`・`report` の役の節に全部在る」を、次に直す:
   ```
   ブロック `judge`・`plan`・`plan-review`・`eyes`・`report` の役の節に全部在る。ただし judge の役のうち、作業ツリーに書く役（受け入れテストのファイルを書く `spec`・`spec-revise`）と、対象のリポジトリでコマンドを走らせる役（`pr-check`・`premises`・`prior-decisions`・`local-review`・`external-standards`・`procedure-trace`・`gate-efficacy`・`test-double-fidelity`・`main-path-observation`・`provenance`）は書かない。後の 10 は、今の works と同じく受け付けの script が作業ツリーの姿を比べ、変えた返答を拒む。
   ```
   訳: 仕様の段は judge の中に在り（`docs/design.md` の judge の節「`--spec` の時は仕様（要件と受け入れテスト）と仕様の関所」）、今の works の仕様の書き手は Edit・Write でテストのファイルを書く（`works/blk-spec/blk-spec.yaml`:74・317）。コマンドを走らせる役は、今の works でも `mutates_checkout` を書かず（`works/blk-material/blk-material.yaml` ほか）、受け付けが `accept.tree_moved` で作業ツリーの変化を拒んでいた。テストを走らせると作業ツリーに捨ててよい物（キャッシュなど）が出ることがあり、`mutates_checkout: false` では Archon がその節を落とす。
2. `docs/design.md` の「能力の棚卸し」の「### test-gate・eyes・report・merge」の節に 1 行足す（`spec.check` の置き場。元 `works/.shared/core/graphloops/rules/review-loop.py`:4044 の `spec_check` は、承認の後に受け入れテストのファイルが変わっていないかを修正の後に照らし、変わっていれば人に聞く）:
   ```
   - 仕様の受け入れテストの改変の照らし（spec.check）: `graphloops/rules/review-loop.py` の `spec_check` → test-gate（final）。judge の返り `spec` の `acceptance[].sha256` と今の木を比べ、違えば最後の関所に載せる
   ```
   置き先を test-gate（final）にする訳: 修正の後で、緑の認証と同じ木の指紋の時点で照らせる。置き先を別にするなら、その行の矢印の先だけを替える。judge は `sha256` を固めて返す所まで持つ。この行は、置き先のブロックが決まって、そのブロックが作るまで入れない（今の 8 つの計画のどれも作らない）。
3. `docs/design.md` の「ブロックの返りの約束」の「### judge の返り」の「入力（`with:`）」に、次の 1 行を足す（judge が要るのに約束にも始めの記録にも無い入力。今の works は前の run の失敗の行を盤面の根の `prior-failures-in.json` で受けていた）:
   ```
     - `prior_failures` ← 前の run の持ち越しの前の失敗の行の指し札（`lib/carry`。今の works の `prior-failures-in.json`。無ければ null）
   ```
