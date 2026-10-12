# 繰り返し踏む落とし穴と、それを縛る機械の在り無し

読み方: 「今の機械」は works-factory の origin/main の写し（main（4e0e18d））か、線の PR #74 の頭（#74 の head（824dee3））に今在る試験。どちらに在るかを頭に書く。Archon の行は止めた源 `d97d00ef`（`packages/` から）。「要る試験」は名前だけの提案で、まだ無い。

- K1 ブロックの返す節（`returns:`）と、返す節が結ぶ節は落ちてはいけない（lib の import は守った main の中に置き、最後の逃げ道は標準ライブラリだけで返す）。落ちた節の出力を結んだ節は `trigger_rule: all_done` でも落ちる
  - 根拠: Archon `workflows/src/dag-executor.ts:495-533`（`resolveBindingDirective`。落ちた作り手は `if_skipped` に戻らず例外）・`:344-357`（`wholeRefLogicalValue`。素の `with:` の `$x.output` も同じ）・`:1443-1455`（指示書や script の本文に埋める時も同じ）・`condition-evaluator.ts:100-111`（`when:` も同じ）・`output-ref.ts:590-597`（`assertProducerNotFailed`）。`all_done` は前の節が終わっていれば走るだけ（`dag-executor.ts:2001-2005`）。PR の指摘: #69 の 1 回目の 3、#67 の 1 回目の 5、#73 の 1 回目の 1、#75 の 1 回目の 1・2（「返す節 `plan` が `$round.output.dir` を束ねている。Archon では落ちた節の出力を束ねた節は `all_done` でも落ちる」）、#68 の 1 回目の 3、#76 の 1 回目の 2、#94 の 1 回目の 10、#74 の 1 回目の 3・11
  - 今の機械（ブロックごとの試験。lib を読めない時に返す節が落ちないかを照らす。全部 main）:
    - judge: `tests/workflows/test_judge.py::VerdictNeverFailsTest.test_lib_out_of_reach`
    - plan: `tests/workflows/test_plan.py::SurvivesCase.test_round_and_return_node_survive_a_lib_that_does_not_load`。返す節が結ぶ `round` も一緒に照らす
    - plan-review: `tests/workflows/test_plan_review.py::FailSafeCase.test_result_without_the_lib_returns_the_failed_shape`
    - fix: `tests/workflows/test_fix.py::BlockScriptsCase.test_collect_returns_the_contract_when_the_boundary_cannot_be_read`。`collect.py` を単独で写して走らせ、境の口も lib も無い形まで照らすのはこれだけ
    - test-gate: `tests/workflows/test_test_gate.py::ResultScriptCase.test_lib_that_cannot_be_imported_returns_incomplete_without_failing`
    - eyes: `tests/workflows/test_eyes.py::ScriptCase.test_verdict_never_fails_when_lib_cannot_be_read`
    - merge: `tests/workflows/test_merge.py::NeverFailsTest.test_lib_missing`
    - report: `tests/workflows/test_report.py::CollectScriptCase.test_without_lib_still_returns`。返す節が結ぶ `facts` は `FactsCase.test_broken_inputs_and_missing_pointer_do_not_fall` が照らす
    - 線（#74 の head）: `tests/workflows/test_line.py::FallbackCase.test_every_fallback_fits_its_node_and_stops`（線の全 script の `fallback()` の返りが節の `output_format` に合う）と `BrokenLibCase.test_lib_import_failure_is_returned_not_raised`（空の lib/ で実際に走らせて終了の値 0。`guarded_imports` を持つ script が 5 本以上）
  - 穴:
    - ブロックを横に通す機械が無い。新しいブロックや返す節の差し替えは、そのブロックの試験を書いた人しか縛れない
    - 「返す節が結ぶ節も落ちない」を照らす試験も無い。今 `with:` で他の節を結ぶ返す節は plan（`$round.output.dir`）と report（`$facts.output`）の 2 つで、たまたま両方とも結ぶ先を縛る試験がある
    - fix 以外は境の口（`.shared/boundary.py`）を残したまま lib だけを消しており、境の口の import が落ちる形は照らしていない
    - FallbackCase と BrokenLibCase は線の script だけを見る
  - 要る試験:
    - `tests/layers/test_block_returns.py::BlockReturnsTest.test_return_node_binds_only_never_failing_nodes`: 各ブロックの返す節の `with:`・`when:`・本文が読む `$<id>.output` の `<id>` が、表（`NEVER_FAIL`）に載った節であることを字で照らす。表の各行は、その節を lib 無しで走らせる試験の名を持つ
    - `tests/workflows/test_returns_never_fail.py::ReturnScriptCase.test_every_returns_script_runs_alone_and_fits_its_output_format`: 全ブロックの返す節の script を `.shared` も lib も無い一時のフォルダへ単独で写し、入力無しで走らせる。終了の値 0 で、標準出力の JSON が節の `output_format` の `required` と型に合うことを確かめる（fix の `test_collect_returns_the_contract_when_the_boundary_cannot_be_read` を全ブロックに広げる形）

- K2 uv で走る script（`runtime: uv`）は、頭に PEP 723 の `# /// script` の宣言を持つ。無いと対象の `pyproject.toml` を拾って作業ツリーに `.venv`・`uv.lock` を作る
  - 根拠: issue #92（閉じた）・PR #95（merged）・issue #96（開いたまま）。Archon `workflows/src/script-discovery.ts:71`（`MAX_SCRIPT_DISCOVERY_DEPTH = 1`）・`:107-111`（`scripts/` の下 1 段のフォルダまで探す）・`:214`（pack の工程の `scripts/`）・`dag-executor.ts:3873-3877`（`uv run <パス>`）。PR の指摘: #73 の 1 回目の 2、#76 の 1 回目の 1、#68 の 3 回目の 1（main の試験が 7 件赤）
  - 今の機械（main と #74 の head で中身は同じ）: `tests/workflows/test_uv_scripts.py::HeaderTest.test_every_script_declares_itself`（`workflows/*/scripts/*.py` の頭の 4 行が `HEADER` と一致。:20・:38）と `UvRunTest.test_uv_run_leaves_the_tree_alone`（`pyproject.toml` を置いた種で `uv run` した前後の `git status --porcelain --ignored` が同じ。:57-69）。judge には `tests/workflows/test_judge.py::UvLaunchTest.test_read_only_script_leaves_a_python_project_untouched` もある
  - 穴:
    - 今も #96 のとおり。:20 の glob `workflows/*/scripts/*.py` は `scripts/<組>/x.py`（Archon が探す 1 段下）を見ない。今その形の script は 0 本
    - YAML の `script:` の名が、glob が見るファイルに当たるかは照らさない
    - 直に書いた（inline の）`script:` の本文も見ない。今は 0 本
    - `UvRunTest` は入力無しで起こすので、各 script の早い出口の道だけを通る
  - 要る試験: `tests/workflows/test_uv_scripts.py::HeaderTest.test_every_named_script_archon_can_find_declares_itself`。`workflows/*/scripts/**/*.py` を 1 段下まで探し、YAML の `runtime: uv` の `script:` の名が全部その中に当たることと、直に書いた `script:` の節が無いこと（在れば本文の頭に宣言があること）も照らす

- K3 作業ツリーを変えない節は `mutates_checkout: false` を書く。ただし Archon は `loop:` の節ではこの鍵を無視する
  - 根拠: Archon `workflows/src/schemas/dag-node.ts:1025-1031`（`LOOP_NODE_AI_FIELDS` に `mutates_checkout`。「Tree-integrity enforcement belongs to exec/agent nodes, not whole loops」）。PR の指摘: #74 の 1 回目の 5、#75 の 1 回目の 7（10 本の script の節）、#94 の 1 回目の 7（17 の script の節）
  - 今の機械（#74 の head だけ。main には E7 の機械が無く、`workflows/AGENTS.md` の E7 が名指す `tests/layers/test_readonly_nodes.py` は main に無い）: `tests/layers/test_readonly_nodes.py::ReadonlyNodesTest.test_real_tree_clean`。中身は `tests/layers/scan.py:489-536` の `_readonly_nodes` で、次を照らす
    - `ROLE_BLOCKS = (judge, plan, plan-review, eyes, report)`（:489）の役の節（`ROLE_KINDS = ("prompt", "command")`、:491）全部
    - ただし `JUDGE_WRITERS` の 12 の節（:493）は外す
    - そのほかは `READONLY_NODES` に名指した節だけ（:497。`line` の 25 の節だけ）
    - ブロックごとの試験も別に在る（main）: `test_fix.py::RolesCase.test_read_only_roles_declare_it`・`test_read_only_scripts_declare_it_and_no_other_node_does`、`test_test_gate.py::YamlCase.test_readonly_nodes`・`test_role_node_reads_only`、`test_plan.py::ShapeCase.test_role_nodes_are_read_only_and_isolated`・`test_scripts_are_read_only_uv_scripts`、`test_plan_review.py::YamlCase.test_ai_and_script_nodes_are_read_only`、`test_eyes.py::ShapeCase.test_every_role_node_is_read_only`、`test_report.py::ShapeCase.test_every_node_leaves_the_checkout_alone`、`test_judge.py::RoleSettingsTest.test_roles_keep_the_old_settings`（役だけ）
  - 穴:
    - `test_readonly_nodes.py::ReadonlyNodesTest.test_loop_node_is_not_asked_for_the_mark`（:56-58）は、`loop:` の形の読むだけの役を緑にする。Archon はその節の作業ツリーを守らないので、読むだけの役を `loop:` で書くと守りが黙って消える。今の木に `loop:` の節は 0 本
    - E7 の走査はブロックの script の節を見ない
    - judge の script の節 36 個（`spec-accept`・`*-prep`・`*-accept`・`world-*`・`diagnose-accept`・`rejudge-accept` など）は `mutates_checkout: false` を持たず、どの試験も求めない。読むだけかの見極めは要る
    - fix・test-gate・merge は `ROLE_BLOCKS` の外で、表にも無い。ブロックの試験しか縛らない
    - 元の works の `works/tests/test_yaml_rules.py::…test_pack_read_only_ai_nodes_do_not_mutate_checkout`・`test_changer_node_with_mutates_checkout_false_is_red` は、道具（Bash・Edit・Write の有無）から読むだけかを導いていた。今は名の表なので、新しい節は表に足さない限り縛られない
  - 要る試験:
    - `tests/layers/test_readonly_nodes.py::ReadonlyNodesTest.test_read_only_role_as_loop_node_is_red`: 今の `test_loop_node_is_not_asked_for_the_mark` を置き換え、`ROLE_BLOCKS` の `loop:` の節を赤にする（`loop_group` で書かせる）
    - `ReadonlyNodesTest.test_mark_follows_the_tools`: `allowed_tools` に Bash・Edit・Write が無い役の節は `mutates_checkout: false` を必須にし、在る節が `false` を書けば赤にする（元の決まりを全ブロックに）
    - `READONLY_NODES` に judge・fix・test-gate・merge の読むだけの script の節を足す

- K4 skill や agent を借りる役の節は `skills:`・`plugins:` で名指す（Archon はワークフローの節に、名指した skill とプラグインしか渡さない）。同梱の skill は名指してもディスクに無い警告が出るので、表で数えない
  - 根拠: Archon `providers/src/claude/provider.ts:627-638`（「Workflow nodes are declared-only capability boundaries … exclude ambient skills, MCP and plugins unless the workflow names them explicitly」。`options.skills = nodeConfig.skills ?? []`・`namedPlugins`）・`:691`（同梱の skill の警告の文）。PR の指摘: #76 の 1 回目の 5・2 回目の 1・2（`validator.ts:698-768`・`provider.ts:633-634`・`plugins.ts:179-180`）、#94 の 1 回目の 5
  - 今の機械（main）:
    - `tests/layers/test_archon_validate.py::ArchonValidateTest.test_only_builtin_and_borrowed_skill_warnings_go_uncounted`: 数えない警告は `tests/archon.py:34` の `BUILTIN_SKILLS` と `:35-36` の `BORROWED_SKILLS` だけ。ほかの名は赤
    - `tests/workflows/test_judge.py::RoleSettingsTest.test_roles_keep_the_old_settings`: judge の各役の `(skills, plugins)` を表 `ROLES` と比べる。局所レビューは `[code-review, simplify, security-review]` と `[pr-review-toolkit@works-local]`
    - `tests/workflows/test_fix.py::RolesCase.test_borrowed_skills_sit_on_the_seat_roles`
    - #74 の head の `tests/archon.py` はまだ `BORROWED_SKILLS` を持たない（rebase で入る）
  - 穴:
    - 役の指示書が skill や agent を使えと書くことと、節の宣言が合うかを照らす試験は無い
    - 今の食い違いの見本: `workflows/judge/commands/material-local-review.md` は 91-93 行（`unattended.md` の写し）で、superpowers の借りる skill を読む役だと書く。節 `local-review` は同梱の 3 本しか名指さない
    - `workflows/fix/commands/delta-review.md:11` は pr-review-toolkit の agent に触れる（材料の説明で、起こせとは言わない）
    - 元の works の `works/tests/test_yaml_rules.py` の「skills は借りる一覧の中だけ・同梱の 3 本は局所レビューだけ」（`user_skills_not_pinned`・`test_bundled_skills_only_in_local_review`）は、ブロックを横に通す機械として移っていない
  - 要る試験:
    - `tests/layers/test_role_skills.py::RoleSkillsTest.test_prompt_naming_a_skill_or_agent_declares_it`: 役の指示書（`commands/` と、直に書いた `prompt:`）に借りる skill の名（`BORROWED_SKILLS`）・同梱の名（`BUILTIN_SKILLS`）・`pr-review-toolkit` の字があれば、その節の `skills:`・`plugins:` が名指す。説明だけの言及は試験の中の表で行ごとに許す
    - `RoleSkillsTest.test_skills_are_borrowed_or_builtin_in_named_nodes`: 元の決まりを全ブロックに

- K5 `loop_group`（輪）の中の役の節は自分の `with:` を結ばない。前の周の値は、輪の頭に置いた script の節が `$LOOP_PREV` で結んで返し、役はその節の出力を読む
  - 根拠: PR #100（merged）。Archon `workflows/src/include-expander.ts:566`（自分の `with:` で結んだ名を外すのは節の指示書だけ）・`:579`・`:596`（足りない入力は読み込みの誤り）・`:627`（`agent.prompt` だけを守る）・`:584`（入力に宣言すると include の時に既定の字で固まる）・`template-walker.ts:266-283`（輪の中の節も同じ走査に入る）。PR #74 本文の「止まっている所」
  - 今の機械（main）:
    - `tests/layers/test_archon_validate.py::ArchonValidateTest.test_every_block_loads_when_included`（:54-75）: 各ブロックを 1 つずつ include するだけの親の工程を足し、宣言の既定値の無い入力に仮の字 `"x"` を渡して `archon validate` が誤りも警告も出さないかを見る。CI は `WORKS_FACTORY_ARCHON_REQUIRED=1` なので見送らない
    - ブロックごとの形の試験: `test_judge.py::LoopTest.test_roles_receive_the_reject_reason_through_the_reject_node`、`test_report.py::ShapeCase.test_writer_receives_the_reject_file_through_the_reject_node`、`test_test_gate.py::YamlCase.test_prep_takes_previous_reject`
    - #74 の head にはまだこの試験が無い（rebase で入る）
  - 穴:
    - 親の工程はブロックを一番上の段に include するだけ。線のように `loop_group` の中で include する形（線の `plan-rounds` の中の plan-review）は照らさない
    - Archon と bun が要る。字だけで見られる決まり（輪の中の役の節に `with:` が無い）としては持っていない
  - 要る試験:
    - `tests/layers/test_loop_roles.py::LoopRolesTest.test_no_role_in_a_loop_group_binds_its_own_with`: `loop_group.nodes` の中の `prompt:`・`command:` の節に `with:` があれば赤にする。Archon 無しで走る
    - `ArchonValidateTest.test_every_block_loads_when_included_inside_a_loop_group`: 親の工程の `loop_group` の中で include する形も足す

- K6 周ごとの値（`$LOOP_PREV`）は本物の run でしか確かめられない。`archon workflow test` の筋書き（dry-run）は前の周の出力を渡さない
  - 根拠: Archon `workflows/src/fixture-runner.ts:20-22`（筋書きを走らせるのは `dryRunWorkflow` だけ）、`dry-run.ts:1053-1058`（`simulateLoopGroup` は周ごとに `new Map(outputs)` を作り、前の周の出力を持ち越さない）・`:795`（script に渡す `loopPrevOutput: ''`）・`:958-963`（stub は節ごとに 1 つで周で変わらない）・`:906`（`until_bash` は走らせず「assumed complete」）。`dry-run.ts` には `$LOOP_PREV.` を解く箇所が 1 つも無い（grep で 0 件）。本物の run で解くのは `dag-executor.ts:1516-1561`。PR #100 本文（「本物の run（haiku）で理由が空→1 周目→2 周目と替わった」。手で確かめただけ）
  - 今の機械: 無し。在るのは配線の形の試験（K5 のブロックごとの試験。`$LOOP_PREV.<accept>.output.reason` を結ぶ字を照らす）と、`test_plan_review.py::YamlCase.test_no_loop_prev_reaches_a_role` だけ
  - 穴:
    - 周ごとに値が替わることを照らす試験は無い
    - 筋書きの注記が、確かめていない周の振る舞いを書いている: `workflows/plan/fixtures/give-up.stubs.yaml:1`（「受け付けが 3 回とも拒んで諦めた周」）・`workflows/plan-review/fixtures/review-give-up.stubs.yaml:1`（「3 回とも拒んだ後の姿」）。どちらも受け付けの stub が 1 周目から `give_up: true` を返すので、輪は 1 周で抜ける
  - 要る試験:
    - 段 1 の本物の run で確かめる行（どの輪の `<役>-reject` の節の出力が 1 周目は空、2 周目は前の受け付けの `reason` か、を run の記録の節の出力で見る。ただし種の run で拒みが起きるとは限らない）
    - 筋書きの側: `tests/workflows/test_fixture_claims.py::FixtureClaimsCase.test_fixture_comments_do_not_claim_more_than_one_round`（筋書きの頭の注記に「N 回」「N 周」があれば赤）

- K7 層の決まり E3・E4・E13
  - 根拠: `lib/AGENTS.md`（E3）・`workflows/AGENTS.md`（E4）・`AGENTS.md`（E13）。PR の指摘:
    - E4: #66 の 1 回目の 1（`merge.py` の numstat を lib へ）、#69 の 1 回目の 6（script どうしの import）、#68 の 1 回目の 7、#74 の 1 回目の 11
    - E3: #73 の 1 回目の 3（`lib/boardview.py` が節の id と YAML の並びを読む）、#76 の 1 回目の 10（`lib/specblk.py:56` の `RUN_ID_ENV = "WORKFLOW_ID"`）
  - 今の機械（main。走査器は `tests/layers/scan.py`）:
    - E3「lib/ は Archon を知らない」: `tests/layers/test_lib_blind.py::LibBlindTest.test_real_tree_clean`。`scan.py:21` の `ARCHON_WORDS`（`archon`・`ARTIFACTS_DIR`・`TYPED_ARTIFACTS_FILE`・`output_type`）と、`:22` の `LAYER_IMPORT`（`from|import workflows|bin`）を `lib/` の全部に当てる
    - E4「ブロックはほかのブロックのファイルを指さない」: `tests/layers/test_block_paths.py::BlockPathsTest.test_real_tree_clean`。`scan.py:253-285` の `_block_paths` が、ブロックの `scripts/`（下のフォルダも）とブロックのフォルダ直下の YAML の字から、ほかのブロックを指すパスと、`scripts/` から `lib/`・`.shared/`・自分の外への相対パスを探す
    - E13「対象の言語を知らない」: `tests/layers/test_lang_neutral.py`。`scan.py:358-360` の `_lang_neutral` が、ブロックの `commands/` と `lib/` に `LANG_WORDS`（`:55`。`python` は入れない決まり）を当てる。`ALLOWED["E13"]` の 8 行は外す
  - 穴:
    - E3:
      - 字の表が `INPUTS_`・`WORKFLOW_ID`・`$LOOP_PREV`・`loop_group`・`$<id>.output` を持たない。今 lib に在るもの: `lib/stage_a.py:21`（`"INPUTS_UNITS"`）・`lib/stage_b.py:35`（`"INPUTS_BASE_REV"`）・`lib/tree_run.py:416`（`INPUTS_CMD`）・`lib/judge_accept.py:2011`（`$material-route.output`）・`lib/rolekit.py:62`・`lib/refixrules.py:6`（`$LOOP_PREV`）・`lib/report_roles.py:52`（`loop_group`）
      - 「役の指示書を持たない」は照らさない。`lib/agents/*.md` の 5 本は役の定義そのもの（元と同じバイト）
      - 節の id は字で見分けられない（`scan.py` の頭の注記）
    - E4:
      - 後半の「script は lib と境の口を呼ぶだけで、確かめの中身を持たない」は照らさない
      - script どうしの import も照らさない。今 main に在るもの: fix の 30 本が `fixio`（`workflows/fix/scripts/fixio.py`。`subprocess` を持つ助け）を、`group_start.py` が `prep` を、report の `collect.py`・`facts.py`・`report_accept.py` が `place`・`typed` を import する。#74 の head では線の 15 本が `linekit`・`plan_out`・`fixed`・`gate_answer` を import する
      - `commands/` と `.shared/` も見ない
    - E13:
      - 直に書いた `prompt:`（fix の `fix-ruled`・`refix`・`refix2`・`tdd`・`fixer`・`consult-answer` など）を見ない
      - `python` を表に入れないので、役の指示書の「Python」「`PYTHONDONTWRITEBYTECODE=1`」「`.py`」を通す: `workflows/fix/commands/fix-rules/common.md:6・69・70`・`tdd.md:28`・`principles.md:9`・`ruler.md:31`
  - 要る試験:
    - `tests/layers/test_lib_blind.py::LibBlindTest.test_runtime_names_are_red`: `INPUTS_`・`WORKFLOW_ID`・`$LOOP_PREV`・`loop_group`・`\$[\w-]+\.output` を赤にする。今の 7 か所は直すか、行ごとの許しに載せる
    - `tests/layers/test_block_paths.py::BlockPathsTest.test_scripts_do_not_import_sibling_scripts`: `scripts/*.py` の import の名が、同じ `scripts/` の別のファイルの名なら赤。共有の助けを残すなら `.shared/` の埋めか lib へ移す
    - `tests/layers/test_lang_neutral.py::LangNeutralTest.test_role_texts_carry_no_language_word`: `commands/` と直に書いた `prompt:`・`systemPrompt:` に、`LANG_WORDS` と `python`・`pip`・`\.py\b`・`PYTHON[A-Z_]*` の表を当てる

- K8 script から script を import しない（script は lib を境の口から読むだけ）。lib の中に読み込みの順で落ちる循環 import を作らない
  - 根拠: PR #69 の 1 回目の 6（「`ci_accept.py:25` の `from ci_prep import …`（script どうしの import。E4）をやめ」）。PR #76 の本文 480-483 行と 2 回目の 3（`lib/judge_accept.py:316,324` が読み込み時に `jv.VERIFY_FILE` を引き、`judgeverify` を先に import すると AttributeError）
  - 今の機械:
    - script どうし: 無し（K7 の E4 の穴）
    - 循環: `lib/tests/test_judge_accept.py::VerifyPrepCase.test_judgeverify_loads_before_judge_accept`（:392。`judgeverify, judge_accept` の 1 組だけを新しい interpreter で読む）
  - 穴:
    - script どうしの import は今 main で 35 か所、#74 の head の線でさらに 24 か所ある（K7 に列挙）
    - 循環は 1 組しか見ない。lib/ の 91 本のどれかを最初に読んだ時に落ちる循環は照らさない
  - 要る試験:
    - `tests/layers/test_block_paths.py::BlockPathsTest.test_scripts_do_not_import_sibling_scripts`（K7 と同じ）
    - `lib/tests/test_imports.py::LibImportCase.test_every_module_imports_first_in_a_fresh_interpreter`: lib/ の各モジュールを、新しい interpreter で 1 本ずつ最初に `import` し、全部が終了の値 0 になること

- K9 役の指示書と役の定義は、元の works から字のまま写す。写しの文を縛る試験を置く（許した直しだけを差として持つ）
  - 置き換わった: K9 は持ち主の決め `prompts-coldread`（2026-10-12、`docs/owner-decisions.md`）で置き換わった。役の指示書は元の字に戻さず、`tests/workflows/test_prompt_contracts.py` の 4 つの約束（約束の表 `tests/workflows/prompt_contracts.json`）で縛る。下の「今の機械」の字の一致の試験は消え、「要る試験」の `test_copied_texts` は作らない。下は歴史として読む。
  - 根拠:
    - 能力の落ち: PR #67 の 1 回目の 3（comment-analyzer の定義が 1 文の要約に）・2 回目の 2（「戻した指示書の文に、消すと赤になる試験を足す」）、#73 の 1 回目の 7・3 回目の 2（「今は外しても緑」）、#75 の 1 回目の 6・2 回目の 2（「`commands/fix-plan.md` を元の `p2.fix_plan.md` と突き合わせる試験を足す」。写しの台帳 `bin/_lib/copyledger.py` の `!` の行で許した直しを書ける形）、#68 の 1 回目の 5、#76 の 1 回目の 9、#94 の 1 回目の 5（`delta-review.md` の落ちた 1 行）・2 回目の 2
    - 根の決まり: `AGENTS.md` の E18（元と同じファイル名で置く）
  - 今の機械（main。ブロックごとに 1 本から数本の手で書いた試験）:
    - `tests/workflows/test_plan.py::ShapeCase.test_fix_plan_command_is_the_original_with_only_the_allowed_edits`（許した直しを逆に当てると元の sha256 に戻る。いちばん強い形）
    - `tests/workflows/test_eyes.py::ShapeCase.test_r1_comments_carries_the_comment_analyzer_definition_verbatim`（sha256）
    - `tests/workflows/test_plan_review.py::PortedMaterialCase.test_units_line_is_the_original_instruction_line`
    - `tests/workflows/test_judge.py::RoleSettingsTest.test_roles_that_reach_outside_carry_the_query_rule`・`test_dropped_sentences_are_back`
    - fix は `lib/tests/test_fix_rules.py` などで一部
    - 写しの台帳は `bin/_lib/COPIED_FROM.changemap` と `bin/_lib/borrow/superpowers/COPIED_FROM` だけで、指示書の台帳は無い
  - 穴:
    - 45 本の指示書（`workflows/*/commands/**/*.md`）を、元の works の同じ名のファイルと比べた
      - バイトが同じ: 6 本（`plan/commands/structure-eye.md`、`fix/commands/fix-rules/` の `brief`・`principles`・`refix`・`ruler`・`tdd`）
      - 同じ名の元はあるがずれている: 23 本
      - 元の名で辿れない: 16 本（judge の `material-*` 11 本・`judge-verify`・`spec`、`plan-review.md`、`fix-plan.md`〔元 `p2.fix_plan.md`〕、`cold-check.md`）
    - 許した直しとの差を照らすのは `fix-plan.md` と `r1-comments.md` の 2 本だけ。残りは字の一部を見るか、何も見ない
    - `lib/agents/*.md` の 5 本は元とバイトが同じだが、それを縛る試験は無い
    - 字のまま写した中に、元の works の古いパスが残る: `material-local-review.md:91-93`（`.shared/borrow/…`・`dev/toolset.py`・`blk-*/commands/*.md`・`tests/test_sp_skills.py`）
  - 要る試験: `tests/workflows/test_copied_texts.py::CopiedTextsCase.test_every_role_text_is_its_original_with_only_ledgered_edits`。台帳（`workflows/<ブロック>/commands/COPIED_FROM` か `copyledger` の形）の各行に、写しのパス・元のパス・元の sha256（`pack.json` の `works.commit` で）・許した直しの組（元の字、写しの字）を書く。直しを逆に当てると元の sha256 に戻ることを全行で照らし、台帳に無い `commands/*.md` と `lib/agents/*.md` は赤にする

- K10 どの関所の `reject` も `stop` も、run の取り消しにせず報告へ流す。Archon は `decisions` に `reject` が無い関所の reject を run の取り消しとして扱う
  - 根拠: Archon `core/src/operations/workflow-operations.ts:1625-1640`（`willResolveNewMode` は `decisions` に `reject` が在り `on_reject` が無い時だけ）・`:1665-1677`（`{decision: 'reject'}` で関所を終える）・`:1690-1700`（それ以外は `resolveAndCancelApprovalGate` で run を取り消す）。PR #74 の 1 回目の 1（「Archon は decisions に無い `reject` を取り消しとして扱う。`workflow-operations.ts:1638-1700`」）・本文「計画とずれた所」1
  - 今の機械:
    - #74 の head: `tests/workflows/test_line.py::GateDecisionsCase.test_gates_take_the_words_their_text_prints`（:660-673。線の 4 つの関所の `decisions` が `GO_WORDS ∪ VERBS ∪ {reject}` と等しい）と `GateAnswerCase.test_reject_stops_like_stop`（:199。`gate_answer` が reject を止めと読む）
    - main: `tests/workflows/test_judge.py::GateTest.test_spec_gate_is_an_approval_with_the_four_words`（:142-145。judge の `spec-gate` が `[approve, continue, stop, reject]`）
  - 穴:
    - 関所を横に通す決まりが無い。E16 の走査（#74 の head `scan.py:542` の `_gates`）は `interactive` と頭の鍵だけを見て、`decisions` の `reject` と `on_reject` の有無を見ない。新しいブロックに関所を足すと、どの試験にも掛からない
    - 線の筋書きは関所の答えの節（`answer-*`）を stub で差すので、Archon の reject から報告までを通しで走らせた筋書きは無い（`workflows/line/fixtures/` に `reject` は 0 件）
  - 要る試験:
    - `tests/layers/test_gates.py::GatesTest.test_every_gate_declares_reject_and_no_on_reject`: 全工程の `approval:` の節が `decisions` に `reject` を持ち、`on_reject` を持たない
    - 段 1 の本物の run で、1 回は関所に `reject` を答えて report まで届くかを見る行（筋書きでは作れない）

- K11 ブロックに入力を足す時は既定値をつける（既定値の無い入力を足すと、そのブロックを include する全部の工程が読み込みで落ちる）。既定値つきで足した入力は、線が渡さない限り黙って既定値のままになる
  - 根拠: Archon `workflows/src/include-expander.ts:576-580`（「missing always fails the load」）。PR #73 の 1 回目の 8・9（「8・9 の入力は既定値つきなので線は壊れない」）・3 回目（`conflicts`・`gate_answers` は既定値 `"null"`）、#74 の 3 回目の 1（plan の `prior_failures` を線から渡す）・4 回目の 1（judge の `reject_reason`）・本文 82 行（eyes の `x_scalars` を渡していない）
  - 今の機械:
    - 入力の宣言の形（main。どれも名の一覧を固定するだけ）: `test_judge.py::ReturnsShapeTest.test_inputs_are_the_contract_and_prior_failures`・`test_plan_review.py::YamlCase.test_inputs_are_the_contract_and_the_added_defaults`・`test_fix.py::InputsCase.test_contract_inputs_and_extra_inputs_default_empty`・`test_merge.py::ShapeTest.test_inputs_are_the_contract`・`test_report.py::ShapeCase.test_inputs_are_the_contract`・`test_plan.py::ShapeCase.test_name_inputs_and_return`・`test_test_gate.py::YamlCase.test_name_inputs_and_return`
    - 線の側（#74 の head）: `tests/workflows/test_line.py::LineWiringCase.test_includes_pass_only_what_the_real_block_declares`（渡す鍵 ⊆ 宣言。`required` の入力は全部渡す。report には全部を渡す）・`test_blocks_get_the_start_answers_and_prior_failures`（`prior_failures`・`start_answers` の 2 つだけ）、`tests/e2e/test_line_scenarios.py::LineScenariosTest.test_line_validates_without_errors_or_warnings`
  - 穴:
    - `test_every_block_loads_when_included`（K5）は、既定値の無い入力に仮の字を渡すので、この落とし穴を隠す
    - 線が main に無い間は、ブロックの PR が既定値の無い入力を足しても main は緑のまま
    - 既定値つきで足した入力を線が渡さないことは、どの試験も赤にしない。#74 の head の線と main のブロックを比べると、渡していない宣言済みの入力は次のとおり
      - plan-review（`plan-review-run`・`replan-review`）の `conflicts`・`gate_answers`
      - eyes の `x_scalars`
      - merge-seal の `answer`・`r2`・`sealed_hash`
      - fix・refix の `mode`・`group`・`from_tree`・`out_dir`（fix は `only_items` も）
      - 組の子の入力のように、わざと渡さない物も混ざっている
  - 要る試験: `tests/workflows/test_line.py::LineWiringCase.test_every_declared_input_is_passed_or_named_unpassed`。線が include する各ブロックの宣言のうち、線が渡さない入力は、表（`UNPASSED = {(include の id, 入力): 訳}`）に名指した物だけ。表の行が宣言に無ければ赤。あわせて `tests/layers/test_block_inputs.py::BlockInputsTest.test_inputs_outside_the_contract_have_defaults`（`docs/design.md` の約束の入力の外は既定値を持つ）

- K12 ブロックの新しい入力と「隣のファイル」（返りの指し札の横に名で置き、ほかのブロックが名で開くファイル）は、どれも読み手を持ち、配線の試験で縛る
  - 根拠: `docs/design.md:162`（約束の隣のファイルの一覧: `judgment` の隣の `premises.json`・`judge-verify.json`・`pr-excluded.json`・`materials.json`、`plan` の隣の `p2.fix_plan.json`、`structure` の隣の `design.jsonl`、`review` の隣の `gate-passes.json`）。PR の指摘: #67 の 1 回目の 3（`design-premises.json`・`premise-inputs.json`・`gate-passes.json`）、#73 の 1 回目の 5（落ちた時も `failed/gate-passes.json` を書く。report が名で開く）、#68 の本文 152-168 行（`answer-ties.json`・`world-state.json` が約束の隣でないので読めない）、#74 の 2 回目の 2（`LineWiringCase.READERS` に `ask-final` を足し、`structure_after`・`judgment`・`before_fix_answer` の配線の欠けを赤に）
  - 今の機械:
    - E5（#74 の head だけ）: `tests/layers/test_block_returns.py::BlockReturnsTest.test_real_tree_clean`。中身は `scan.py:427-470` の `_block_returns` で、照らすのは返りの欄だけ
      - 各ブロックに `returns:`・`outcome_field:` が在る
      - 返す節が `output_format` を持ち、`outcome_field` がその `required` に在る
      - 返りの欄のどれもが、線の YAML のどこかで `$<include の id>.output.<欄>`（`$LOOP_PREV.` つきも。`:383`）として字で現れる
    - 配線（#74 の head）: `tests/workflows/test_line.py::LineWiringCase.test_with_keys_are_what_the_script_reads`。`READERS` の 5 つの節（`plan-out`・`judged`・`fixed`・`collect`・`ask-final`）と受け皿の節で、`with:` の鍵 = script が読む `INPUTS_<名>`
    - 隣のファイルの書き手（main）: judge だけ。`tests/workflows/test_judge.py::StopPathTest` が `StopPathFilesMixin.assert_pointers_filled`（:489-502）で `judge_accept.PUBLIC_FILES` の 4 本が在り、空でなく、JSON であることを止めの道でも照らす
    - plan と plan-review の落ちた時の名は `test_plan.py::ShapeCase.test_fallback_names_match_lib`・`test_plan_review.py::FailSafeCase.test_script_literals_match_the_lib` が照らす
  - 穴:
    - E5 は返りの欄しか見ない。隣のファイルも、ブロックの入力も見ない
    - 返りの欄の「読み手」は、線の YAML に字が現れることだけを見る。受け皿が受けて `collect` が report に渡した後に report の lib が使うかは見ない
    - 隣のファイルを横に通す機械は無い（`docs/design.md:162` の一覧と、書き手のブロック・読み手のブロックの対応を照らさない）。judge 以外の隣のファイル（`p2.fix_plan.json`・`design.jsonl`・`gate-passes.json`・`design-premises.json`）の「止めの道でも書く」と「誰かが読む」は、ブロックごとの試験に散る
    - ブロックの宣言した入力に、ブロックの中の読み手（script の `INPUTS_<名>` か指示書の `$INPUTS.<名>`）が在るかは、report（`test_report.py::ShapeCase.test_facts_reads_every_input_by_its_own_name`）と plan-review（逆向きの `YamlCase.test_scripts_read_only_declared_inputs`）しか見ない
  - 要る試験:
    - `tests/layers/test_block_returns.py::BlockReturnsTest.test_every_declared_input_has_a_reader_in_its_block`: 各ブロックの `inputs:` の名が、そのブロックの script の字（`INPUTS_<UPPER>`）か、指示書・YAML の `$INPUTS.<名>` に現れる
    - `tests/workflows/test_line.py::LineWiringCase.test_every_contract_neighbour_file_has_a_writer_and_a_reader`: 試験の中の表（`docs/design.md:162` と同じ。一致も照らす）の各ファイルについて、書き手のブロックが止めの道と lib の無い道でもそのファイルを書くこと（筋書きか script の実行）と、読み手のブロックの lib か script がその名の定数を開くことを照らす

- K13 （一覧に無い物）返りの指し札の先は在って空でないこと。無い・空だと Archon が節の終わりに節を落とし、K1 を破る
  - 根拠: Archon `workflows/src/artifact-pointer.ts:141-142`（「refers to a file that does not exist」）・`:149-153`（「refers to an empty file; a pointer must name evidence」）。PR #76 の 1 回目の 4（世界の解が 0 行の時は空のファイルを指さず `world` を null に）、#73 の 1 回目の 5
  - 今の機械（main）: judge の `StopPathFilesMixin.assert_pointers_filled`（上）と、plan の `tests/workflows/test_plan.py:257`（`CollectCase` が使う照らし「指し札の先が無いか空」）。ほかのブロックは返りの型だけを見る試験が多い
  - 穴: ブロックを横に通す「全部の返りの道（止め・落ち・lib 無し）で、指し札の欄の先が在って空でない」の試験が無い
  - 要る試験: `tests/workflows/test_returns_never_fail.py::ReturnScriptCase.test_every_pointer_in_a_fallback_return_names_a_nonempty_file`（K1 の単独の実行の返りの全部の指し札の欄を `boundary.resolve` で解き、在って空でないこと）

- K14 （一覧に無い物）同じ run の中のやり直しで、前の回の材料や結末を今回の物として返さない
  - 根拠: PR #66 の 1 回目の 4（古い `merge/apply.diff` を消す）、#69 の 1 回目の 4・5（落ちた役の写し・拒んだ回の `ci-material.json`）、#73 の 1 回目の 4（前の差し込みの `open.json`・`review.json` を今回の結末として返さない）
  - 今の機械（main。ブロックごと）: `test_plan_review.py::ResultCase.test_failed_open_drops_the_previous_material`・`FailSafeCase.test_open_without_the_lib_drops_the_previous_material`、`test_test_gate.py` の `test_rejected_reply_leaves_no_material_the_role_wrote`・`test_rerun_in_the_same_run_does_not_read_the_earlier_material`・`test_copy_left_by_a_fallen_role_is_removed`（PR #69 本文の「受け入れの一覧の行ごとの証」）
  - 穴: 同じブロックを 1 つの run で 2 度差し込む線の形（judge→rejudge、plan→replan、fix→refix、test-gate の base と final、merge の seal と apply）で、2 度目が 1 度目の置き場の物を拾わないことを、線の側で照らす試験が無い
  - 要る試験: `tests/workflows/test_line.py::LineWiringCase.test_twice_included_blocks_use_their_own_place`（同じブロックの 2 つの差し込みの id で、置き場の頭が別になることを、各ブロックの置き場を決める関数で照らす）

- K15 （一覧に無い物）読めない入力を黙って空や「当たり」として扱わず、「読めない・確かめられない」と名指す
  - 根拠: PR #66 の 1 回目の 3（守りの一覧が読めない時は「確かめられない」と書き分ける）、#74 の 2 回目の 4（`fenced_rows` は黙って空を返さず訳を返す）、#73 の `REQUEST_UNREAD`（本文 237 行）、#68 の 1 回目の 5（`runreport.pack_terms` は語の一覧が読めない時に元どおり例外）。持ち主の決め `no-silent-loosen`
  - 今の機械: 場面ごと。たとえば #74 の head の `test_line.py::AskFinalReadsCase.test_unreadable_judgment_is_said`・`test_unreadable_structure_after_is_said`・`AfterFixAndJudgedCase.test_unreadable_judgments_are_said`、main の `test_plan.py::CollectCase.test_unreadable_pointer_inputs_are_not_absent`・`test_report.py::FactsCase.test_unreadable_or_missing_conflicts_are_record_invalid`・`test_merge.py::SealTest.test_broken_manifest_is_an_unknown_hit_and_blocks_apply_without_answer`
  - 穴: 指し札を受ける入力を全部並べ、その先が読めない時に返りか材料に名指されることを横に照らす試験は無い。新しい指し札の入力は黙って空に倒れうる
  - 要る試験: `tests/workflows/test_unread_named.py::UnreadNamedCase.test_every_pointer_input_unreadable_is_named`（各ブロックの宣言の入力のうち指し札の型の物を 1 つずつ壊れた先にして入口の script を走らせ、返りか書いた材料にその入力の名が載ること）

- K16 （一覧に無い物）返りの JSON は `allow_nan=False` で書く。Archon は返りを `JSON.parse` で読むので、NaN が混じると節が落ちる
  - 根拠: PR #67 の 2 回目の 3（「`verdict.py` の最後の print に `allow_nan=False` を戻す」）。`workflows/.shared/boundary.py` の `returns` の docstring
  - 今の機械: `tests/workflows/test_eyes.py::ScriptCase.test_verdict_returns_strict_json`（:742。eyes だけ）
  - 穴: 境の口を通さずに直に `print(json.dumps(…))` する返りが、`allow_nan=False` 無しで残る。`workflows/plan/scripts/plan_collect.py:89` と `round.py:67` は通常の道で、`merge.py:101`・`plan-review/scripts/pass_open.py:80`・`result.py:58`・`test-gate/scripts/result.py:145` は落ちた時の道
  - 要る試験: `tests/layers/test_block_paths.py::BlockPathsTest.test_scripts_print_returns_only_through_strict_json`（`scripts/` の `json.dumps(` が `allow_nan=False` を持つか、`boundary.returns` を使う）

- K17 （一覧に無い物）戻した能力に「外すと赤になる試験」を同じ PR で置く（戻しても縛りが無いと、次の直しで黙って消える）
  - 根拠: PR #67 の 2 回目の 2、#73 の 3 回目の 2（「戻した物を縛る試験を足す（今は外しても緑）」）、#68 の 2 回目の 3（「取り戻した物で、壊しても落ちない所に試験を足す」）、#94 の 2 回目の 2（「外しても赤にならない配線 6 つ」）、#75 の 2 回目の 2。持ち主の側は毎回、手で変異を当てて確かめている（#73 の「26 通りの変異」、#94 の「32 本の変異のうち 26 本が赤」）
  - 今の機械: 無し（CI に変異の確かめは無い。ASF の `harness/mutations/` は #74 の head に在るが、ASF の取り付けの物で E8 により手を加えない）
  - 穴: 能力の棚卸しの行ごとに「その能力を外すと赤になる試験の名と assert の行」を持つ決まりが、仕様（issue）の側に無い
  - 要る試験: 試験でなく仕様の形で塞ぐ。能力の行ごとに、試験の名と assert の行を必ず書く（この棚卸しの行の形どおり）。機械で縛るなら `tests/layers/test_capability_rows.py::CapabilityRowsTest.test_every_row_names_an_existing_test`（`docs/design.md` の能力の棚卸しの各行が名指す `file::Class.test` が実在する）

- K18 （一覧に無い物）元の works がブロックを横に通して照らした YAML の決まりが、新しい木ではブロックごとの表に割れた
  - 照らしていた決まり: 役の節の `settingSources: [user]`、閉じた `sandbox`、`allowed_tools` は表の中だけ、`skills` は借りる一覧の中だけ、`loop_group` の本体に `approval:` を置かない、`loop:` の種類は禁止、道具から `mutates_checkout` を導く
  - 根拠: `works/tests/test_yaml_rules.py:1-48`（決まりの一覧）・`:167-188`（`BAD_EXPECT`。違反の見本 20 本 `works/tests/yaml_bad/`）。`approval` を輪の本体に置かない訳は同じファイルの 43-45 行（Archon #3532: 本体が関所で終わる輪の再開は会話を引き継がない）。新しい側は E12 だけを横に通した（`scan.py` の `NODE_KINDS` は `loop:` を許す）
  - 今の機械（main）: ブロックごとの表の試験。`test_judge.py::RoleSettingsTest.test_roles_keep_the_old_settings`、`test_fix.py::RolesCase.test_roles_keep_the_original_model_and_session_settings`、`test_eyes.py`・`test_plan.py`・`test_plan_review.py`・`test_report.py`・`test_test_gate.py` の形の試験（`settingSources`・`allowed_tools`・`sandbox` を 4〜7 か所で見る）。今の木の役の節は全部 `settingSources: [user]`・`allowed_tools`・`sandbox` を持つ（確かめた）
  - 穴: ブロックを横に通す機械が無い。新しい役の節は、そのブロックの表に足さない限りどの決まりにも掛からない。`approval:` を輪の本体に置くこと（今は 0 件）と、`loop:` の節（今は 0 件）は、どの試験も赤にしない
  - 要る試験: `tests/layers/test_role_nodes.py::RoleNodesTest.test_every_role_node_follows_the_pack_rules`（元の `check_file` の決まりを全ブロックに。違反の見本は `tests/layers/seeds/` に 1 本 1 違反で置き、文面で照らす）と、`RoleNodesTest.test_no_approval_inside_a_loop_group_body`

- K19 （一覧に無い物）script の名を lib のモジュールの名と同じにしない。script のフォルダが `sys.path` の頭に来るので、`import <名>` が自分を読む
  - 根拠: PR #74 本文「計画とずれた所」2（線の script `answer` が `lib/answer.py` とぶつかるので `gate_answer` にした）
  - 今の機械（main）: `tests/workflows/test_plan.py::ShapeCase.test_script_names_differ_from_lib_modules`・`tests/workflows/test_plan_review.py::YamlCase.test_script_names_do_not_hide_lib_modules`（この 2 ブロックだけ）
  - 穴: ほかの 6 ブロックと線は照らさない（今の木にぶつかりは 0 件。確かめた）
  - 要る試験: `tests/layers/test_block_paths.py::BlockPathsTest.test_script_names_do_not_hide_lib_modules`（全ブロックと線の `scripts/*.py` の名 ∩ `lib/*.py` の名 = 空）

- K20 （一覧に無い物）同じ定数や関数を 2 か所に持たない（写しの値がずれる）
  - 根拠: PR #68 の 2 回目の 4（封じの確かめの重複・`place.UNWRITTEN` の 1 つに）、#75 の 2 回目の 3（`planfile.DROPPED_OP` をやめて `converge.DROPPED_OP`）、#94 の 2 回目の 3（`recount.precedent_gap` → `judge_accept._precedent_gap` ほか 5 件）、#76 の 1 回目の 12（ファイル名の定数の 2 重定義）、#69 の 1 回目の 8（`MODES` を 1 か所に）
  - 今の機械: 無し（場面ごとに、片方を相手の値と比べる試験がある。たとえば `test_plan.py::ShapeCase.test_fallback_names_match_lib`）
  - 穴: 横に通す機械が無い。意味の重なりは字で決めにくい（持ち主の決め `facts-by-machine-meaning-by-judgment`）ので、人が見る所として残る
  - 要る試験: 字で決められる部分だけ。`lib/tests/test_constants.py::ConstantsCase.test_same_file_name_literal_is_defined_once`（lib/ と `workflows/*/scripts/` で、`*.json`・`*.md`・`*.txt`・`*.diff` で終わる字の定数の定義が 1 か所。落ちた時の逃げ道の写しは表で名指して許す）

## 数

- 一覧の 12 件（K1〜K12）と、一覧に無い 8 件（K13〜K20）。合わせて 20 件
- 今の機械が横に通して足りる物は 0 件。どれも穴が在る。ブロックごとの試験はあるが横に通す機械が無い物は K1・K3・K4・K9・K10・K13・K14・K15・K18・K19
- 機械が全く無い物は 4 件: K6（周ごとの値）・K8 の script どうしの import・K17（戻した能力の縛り）・K20
- main に無く #74 の head にだけ在る機械: E5・E6・E7・E16 の走査（`test_block_returns.py`・`test_outward_write.py`・`test_readonly_nodes.py`・`test_gates.py`）と、線の `FallbackCase`・`BrokenLibCase`・`GateDecisionsCase`・`LineWiringCase`。根の `AGENTS.md` の「機械」の行が名指す `tests/layers/test_layout.py` はどちらにも無い
- 持ち主に聞く事:
  - K3: judge の script の節 36 個に `mutates_checkout: false` を足すか（読むだけかの見極めが要る）
  - K7: 役の指示書の Python の言及（`fix-rules/common.md` ほか 6 か所）を E13 の例外にするか直すか。script どうしの import（fix の `fixio`、report の `place`・`typed`、線の `linekit`）を E4 違反として直すか、決まりの側を変えるか
  - K11: 線が渡していない、宣言済みで既定値つきの入力のうち、どれが今の works から落ちた能力か（plan-review の `conflicts`・`gate_answers`、eyes の `x_scalars`、merge-seal の `answer`・`r2`・`sealed_hash`）

## 部分 0 で足した機械（線の配線の部分 0。上の「今の機械」「要る試験」より新しい）

- K1・K13・K16: `tests/workflows/test_returns_never_fail.py::ReturnScriptCase`（返す節の単独の実行・表 `NEVER_FAIL`・落ちた時の指し札の先・境の口の外の標準出力の表 `LIBLESS_EXITS`）
- K2: `tests/workflows/test_uv_scripts.py::HeaderTest.test_every_named_script_archon_can_find_declares_itself`（issue #96）
- K3・K18: 層の E7（`tests/layers/scan.py` の `_readonly_nodes`・`_role_settings`。印を道具から導き、表 `KEEP_CHECKOUT`・`ROLE_TOOLS`。`loop:` の節は赤。種 `tests/layers/seeds/k18-*`・`k3-*`）。script・bash の節は全部印を書き、外れは表 `CHANGE_CHECKOUT` の 11 節（訳つき。judge の `spec-freeze` は人が通した受け入れ条件を作業ツリーで走らせる（`lib/judge_accept._spec_run`）ので印を持たない）
- K4: `tests/workflows/test_role_texts.py::RoleSkillsCase.test_prompt_naming_a_skill_or_agent_declares_it`
- K5: 層の E5（`_loop_roles`。種 `k5-loop-role-with`）と `tests/layers/test_archon_validate.py::ArchonValidateTest.test_every_block_loads_when_included_inside_a_loop_group`
- K6: `tests/workflows/test_fixture_claims.py::FixtureClaimsCase.test_fixtures_do_not_claim_per_round_values`
- K7: 層の E3 の語の表 `ARCHON_WORDS` と `ALLOWED["E3"]` の `<パス>#<字>` の行
- K8: 層の E4（`_script_imports`。今の物は `ALLOWED["E4"]` に script を 1 本ずつ）・線の script どうしの import は 0・`lib/tests/test_imports.py::LibImportCase.test_every_module_imports_first_in_a_fresh_interpreter`
- K10・K18 の関所: 層の E16（`_gate_words`。種 `k10-*`・`k18-gate-in-loop`）
- K11・K12・K14: `tests/workflows/test_line.py::LineWiringCase` の `test_every_declared_block_input_is_wired_or_listed`・`test_block_inputs_outside_the_contract_have_defaults`・`test_every_contract_neighbour_file_has_a_writer_and_a_reader`・`test_twice_included_blocks_use_their_own_place` と、層の E5 の入力の読み手（`_inputs_read`）
- K15: `tests/workflows/test_unread_named.py::UnreadNamedCase.test_every_pointer_input_unreadable_is_named`
- K19: 層の E4（`_script_names`）
- K20: `lib/tests/test_constants.py::ConstantsCase.test_same_file_name_literal_is_defined_once`
