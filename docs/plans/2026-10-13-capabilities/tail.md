# 能力の棚卸し: 試験の関門（T）・独立の目（E）・報告（R）・取り込みと差分の当て（M）

前の works（raiki61/claude-plugins @ 2aa7c66c の works/）の能力を、作り直しの works-factory（main＝origin/main の写し、線だけ #74 の head＝PR #74 の頭）と 1 行ずつ照らした。行の数と、今に無い行・照らす試験が無いか弱い行・狭めた行の数は末尾の「穴の要約」（数え方は README.md の「穴の数え方」）。
持ち主に要るのは、末尾の「穴の要約」の「持ち主に聞く物」。bin/apply の行は M39〜M53（M39〜M52 は #114 で入った bin/_lib/apply.py と tests/bin/test_apply.py。M53 は周の鎖と一緒に段 3 で作る）。

読み方（4 つの領域で共通）:
- 元: works/ の下のパスと行（@2aa7c66c）。「今」は印（「表」か「無し（表）」、住処を書かなかった行は「無し」か空）だけを持ち、住処の字は docs/works-parity.md の「前の棚卸しの今」が持つ。証: 能力を消すと赤になる試験の名。要追加は試験の案。
- 本物の run: 種（tests/e2e/target-seed/。stats.py に欠陥 2 つ、厚さ 標準、最後の関所はいつも開く）を Archon で回した時に、どの置き場・節・欄で見えるか。健やかな種で起きない道は「筋書きでのみ」。
- 狭め: どの PR が狭めたか。Archon の源（archon/d97d00ef…/packages/workflows/src/ の下）で不可と示せる物だけが「Archon で不可」。それ以外は「戻す」か、決まらない物は「持ち主」。
- 各領域の頭に、その領域だけの前置き（観察先の名の付け方など）を残した。各領域の終わりに、その領域の穴を残した。


## T: 試験の関門（test-gate）の能力の棚卸し

読み方: 「元」は今の works（raiki61/claude-plugins @ 2aa7c66）のパス。「証」は works-factory の main の名（README.md の「指しの形」）。「今」は印（「表」か「無し（表）」、住処を書かなかった行は「無し」か空）だけを持ち、住処の字は docs/works-parity.md の「前の棚卸しの今」が持つ。
本物の run は、種 tests/e2e/target-seed/（stats.py・test_stats.py。.review-checks.json は無い）を前提に書いた。種には宣言が無いので、
engine の段・JUnit・範囲の宣言は種のままでは本物の run に出ない。test_cmd を渡すかで道が分かれる（渡す run は by role、渡さない run は
任せ先の CI の役）。run の置き場の物は `<ARTIFACTS_DIR>/test-gate/<base|final>/…`、節は include の名つきの `test-gate-base__<節>`・`test-gate-final__<節>`。

### A 走らせ方の決め

- T1 対象の宣言 `.review-checks.json` の段を shell を通さずに走らせ、全部 0 なら clean、赤の段が在れば found（count は赤の段の数、detail に赤の段ごとの末尾）にする。
  - 元: works/.shared/core/graphloops/rules/review-loop.py:2236 `checks_reply`・works/.shared/core/board.py:1320 `run_engine`
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::RunEngineCase.test_red_suite_found・lib/tests/test_declared_checks.py::RunEngineCase.test_ran_green_step_is_clean
  - 本物の run: 筋書きでのみ（種に宣言が無い。種に足せば test-gate/base/run.json の by=engine・runs）
  - 狭め: 無し

- T2 test_cmd が在れば、宣言が在っても捨てずに宣言の段の後に test_cmd の段を足し、両方が緑の時だけ clean にする（AND の合成。runner は 1 回で呼ぶ）。
  - 元: works/.shared/core/entry.py:750 `_with_test_cmd`・:858 `run_ci`
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::RunCiTestCmdRulesCase.test_declared_and_red_test_cmd_is_found・lib/tests/test_declared_checks.py::RunCiTestCmdRulesCase.test_declared_and_green_test_cmd_runs_both_in_one_runner_call
  - 本物の run: 筋書きでのみ（宣言と test_cmd の両方が要る）
  - 狭め: 無し

- T3 test_cmd が宣言の段と同じコマンド（直に起こす形で argv が同じ）なら 1 度だけ走らせ、same_as にその段の名を置き、一式の行に「宣言の段 X と同じコマンドなので 1 度だけ走らせた」と書く。
  - 元: works/.shared/core/entry.py:742 `_same_step`・:819 `suites_line`
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::RunCiTestCmdRulesCase.test_same_command_as_declared_step_runs_once
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T4 段ごとのログは段の番号で分け（test_cmd の段が宣言の段を上書きしない）、全段の標準出力と標準エラーを段の見出しつきで 1 本のログ checks.log に並べる。走らせなかった回は理由を書く。
  - 元: works/.shared/core/entry.py:716 `_engine_log`・works/.shared/core/board.py:379 `tree_runner`
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::RunCiTestCmdRulesCase.test_different_command_runs_both_with_separate_logs・lib/tests/test_declared_checks.py::RunEngineCase.test_broken_declaration_is_blocked_without_running
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば test_cmd を渡す run は test-gate/base/logs/a<k>/test_cmd.log・test-gate/final/logs/a<k>/test_cmd.log。checks.log は宣言の在る run だけ（logs/a<k>/checks.log））
  - 狭め: 無し

- T5 宣言が無く test_cmd が在れば test_cmd だけを走らせ（by role）、0 は clean・ほかは found（count 1）にする。
  - 元: works/.shared/core/entry.py:925 `_ci_by_cmd`・:650 `local_checks_material`
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::RunEngineCase.test_no_declaration_runs_test_cmd_by_role
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば test_cmd を渡す run の test-gate/base/run.json の by="role"・material.status="found"（種は 3 件中 2 件赤）と、直した後の test-gate/final/run.json の material.status="clean"）
  - 狭め: 無し

- T6 宣言も test_cmd も無ければ何も走らせず by role_needed・素材 null を返し（前の結果を緑に使わない）、任せ先の CI の役の輪だけがその時に回る。
  - 元: works/.shared/core/entry.py:858 `run_ci`（role_needed）・works/blk-tests/scripts/run_tests.py:67-68・works/blk-ci/blk-ci.yaml
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::RunEngineCase.test_no_declaration_falls_back・tests/workflows/test_test_gate.py::YamlCase.test_loop_matches_give_up
  - 本物の run: test_cmd を渡さない run の test-gate/base/run.json の by="role_needed" と、節 test-gate-base__ci-loop.ci が走ること
  - 狭め: 無し

- T7 宣言の書式の誤りは走らせず、走らせられない素材（判定の前の base は awaiting_human・修正の後の final は not_run）の reason に宣言の名と誤りを書く。
  - 元: works/.shared/core/graphloops/rules/review-loop.py:2199 `checks_plan`（blocked）・:2236
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::RunEngineCase.test_broken_declaration_is_blocked_without_running（判定の前の awaiting_human と後の not_run の両方。#122）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T8 宣言が計画の後に変わったら（宣言の sha の照合）1 度だけ計画し直し、2 度目も変われば CiRefused で止める。
  - 元: works/.shared/core/entry.py:886-890 `run_ci`（relaunch）・works/.shared/core/graphloops/engine/commands.py:522 `engine_run_refusal`
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::RunEngineCase.test_declaration_changed_after_plan_is_replanned_once・lib/tests/test_declared_checks.py::RunEngineCase.test_declaration_changing_twice_is_refused
  - 本物の run: 筋書きでのみ
  - 狭め: #69 で外した（PR の「外した物」の盤面の部分）。Archon で不可でない → 戻すか、計画と走りが同じ関数の中で続くので目的が消えたことを持ち主に諮る → #122 で戻した（走らせた後に宣言が変われば 1 度だけ計画し直す）

- T9 engine が組んだ素材を受け付けの規則で照らし、通らなければ任せ先に落とす。その時 engine が既に走らせた test_cmd の段の結果を使い、test_cmd を 2 度走らせない。
  - 元: works/.shared/core/board.py:1145 `_accept_engine_reply`・:1413 `_fall_back`・works/.shared/core/entry.py:925 `_ci_by_cmd`（ran）・works/tests/test_ci_test_cmd.py:113 test_fallback_after_run_reuses_test_cmd_result
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::RunEngineCase.test_engine_material_meets_material_problems・lib/tests/test_declared_checks.py::RunEngineCase.test_engine_material_that_breaks_the_rules_falls_back_without_rerunning_test_cmd
  - 本物の run: 筋書きでのみ
  - 狭め: #69 で外した（盤面の部分）。Archon で不可でない → 戻す（少なくとも engine の素材にも material_problems を当てる） → #122 で戻した

### B 範囲の宣言 `.works-checks.json`

- T10 範囲の宣言を読む。無ければ絞らない。書式は {段の名: {"paths_ignore": [ルートからの相対パス, …]}} だけで、空・絶対・`..` を含む・ルート丸ごとは拒み、宣言の名を出す。
  - 元: works/.shared/core/board.py:456 `read_scope`
  - 今: 表
  - 証: lib/tests/test_checkscope.py::ReadScopeCase.test_absent_declaration_scopes_nothing・lib/tests/test_checkscope.py::ReadScopeCase.test_good_declaration_maps_step_to_ignored_paths・lib/tests/test_checkscope.py::ReadScopeCase.test_bad_shapes_are_named
  - 本物の run: 筋書きでのみ（種に宣言が無い）
  - 狭め: 無し

- T11 範囲の宣言が `.review-checks.json` に無い段を名指したら、何も走らせる前に止める。文は両方の宣言の名と知らない段の名を出し、節 run は終了 1 で標準エラーに「テストを走らせられない: …」の 1 行を出す。
  - 元: works/.shared/core/board.py:476・works/.shared/core/entry.py:858 `run_ci`（CiRefused）・works/blk-tests/scripts/run_tests.py:99-101
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::ScopedStepsCase.test_scope_naming_an_undeclared_step_stops_before_running・lib/tests/test_checkscope.py::ReadScopeCase.test_undeclared_step_name_is_named
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（線への申し送り: run が 1 で落ちると線の run 全体が failed で終わる。#69 の「線への申し送り」）

- T12 範囲の宣言が在るのに `.review-checks.json` が無い時は、任せ先に落とさず（範囲が黙って効かなくならないように）走らせる前に止める。
  - 元: works/.shared/core/entry.py:858 `run_ci`（冒頭の CiRefused）
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::ScopedStepsCase.test_scope_without_review_declaration_stops・tests/workflows/test_test_gate.py::RunScriptCase.test_scope_declaration_without_review_declaration_stops
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T13 run の変更が全部ある段の paths_ignore の下（glob でなくパスの頭の一致。ファイルかフォルダ）に在れば、その段を回さない。外に 1 本でも在れば全段を回す。
  - 元: works/.shared/core/board.py:481 `skipped_steps`
  - 今: 表
  - 証: lib/tests/test_checkscope.py::SkippedStepsCase.test_change_all_under_ignored_skips_step_and_names_it・lib/tests/test_checkscope.py::SkippedStepsCase.test_change_outside_ignored_runs_every_step・lib/tests/test_checkscope.py::SkippedStepsCase.test_ignored_path_matches_file_or_folder_head・lib/tests/test_checkscope.py::SkippedStepsCase.test_sibling_with_same_prefix_is_not_under（#122）・lib/tests/test_declared_checks.py::ScopedStepsCase.test_final_skips_step_whose_ignored_paths_hold_every_change・lib/tests/test_declared_checks.py::ScopedStepsCase.test_final_runs_step_when_change_touches_outside_ignored
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T14 変更が測れない（base_rev が無い・git の誤り・空）なら絞らない。全段が外れる時も絞らない（1 段も回さない緑を作らない）。範囲を持つ段が無ければ変更を測りに行かない。
  - 元: works/.shared/core/board.py:481-494 `skipped_steps`
  - 今: 表
  - 証: lib/tests/test_checkscope.py::SkippedStepsCase.test_unmeasured_change_runs_every_step・lib/tests/test_checkscope.py::SkippedStepsCase.test_every_step_out_of_scope_runs_them_all・lib/tests/test_checkscope.py::SkippedStepsCase.test_changed_is_not_asked_without_scoped_step
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T15 範囲と照らす変更は base_rev から今の作業ツリーまでに触ったファイル（追跡の変更・消した物・未追跡）で、Archon が作業ツリーに置く `.archon/` の下は数えない。
  - 元: works/.shared/core/entry.py:907 `scope_changed`・works/tests/test_blk_tests_delta.py:364 test_final_does_not_count_archon_workspace_as_change
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::RunScriptCase.test_archon_workspace_is_not_a_change（#122）
  - 本物の run: 筋書きでのみ（種に範囲の宣言が無い）
  - 狭め: 無し（試験だけが欠け）

- T16 判定から入る run の入口の確かめでは、依頼の where が名指す追跡中のパスも変更に足して範囲と照らす（works だけを直す依頼で、works を見ない段を入口から回さない）。
  - 元: works/.shared/core/entry.py:907-922 `scope_changed`（b.rules._pr_files）
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::RunScriptCase.test_base_reads_request_where_as_change
  - 本物の run: 筋書きでのみ
  - 狭め: #69 で狭めた（PR の「能力の狭め」2 つ目）。Archon で不可でない（依頼は始めの記録に在る）。落ちるのは速さだけで確かめは減らない → 持ち主の確かめ 決め: 戻すと決めた（superset）。区分 T の issue（線の配線の文書の「この文書の外」の「決めた物」） → #122 で戻した

- T17 回さなかった段を素材の文（clean の checked・found の detail・走らせられない reason）の末尾に「範囲の外で回さなかった段: <名>（変更が全部 <範囲> の下で、段が見ない所）」と名指す。
  - 元: works/.shared/core/board.py:507 `_skipped_note`・:497 `scope_word`・:502 `skipped_text`
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::ScopedStepsCase.test_final_skips_step_whose_ignored_paths_hold_every_change・lib/tests/test_declared_checks.py::ScopedStepsCase.test_red_material_names_skipped_step_too・lib/tests/test_checkscope.py::WordsCase.test_scope_word_and_skipped_text
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T18 回さなかった段を、一式の行の「走らせなかった」と run の返りの skipped_steps（名と範囲）に出す。
  - 元: works/blk-tests/scripts/run_tests.py:77・works/.shared/core/entry.py:819 `suites_line`・works/blk-tests/blk-tests.yaml:52-61
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::SuitesLineCase.test_skipped_steps_are_named_with_their_ignored_paths・lib/tests/test_declared_checks.py::ScopedStepsCase.test_final_skips_step_whose_ignored_paths_hold_every_change
  - 本物の run: 筋書きでのみ（宣言の在る run なら test-gate/final/evidence.md の「- 走らせ方:」の行）
  - 狭め: 無し（人の前に出るかは T35）

- T19 test_cmd が範囲で外した段と同じコマンドなら、外さずに test_cmd の段として走らせる（入力で名指した一式は外さない）。
  - 元: works/.shared/core/entry.py:858 `run_ci` の docstring（範囲の項）
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::ScopedStepsCase.test_test_cmd_same_as_skipped_step_still_runs（#122）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

### C 起こし方・環境・木ごと止める

- T20 test_cmd の起こし方を起こす所で 1 度だけ決め（単純な語は direct、シェルの記号は bash -c で shell）、走った行・素材の文・ログ・証拠に載せ、読む所で規則から作り直さない。
  - 元: works/.shared/core/entry.py:650・:750・works/.shared/core/tree_run.py:129 `command_argv`
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::LaunchHowRecordedCase.test_launch_wrapper_stamps_how_on_rows_it_ran・lib/tests/test_declared_checks.py::LaunchHowRecordedCase.test_engine_runs_carry_how_decided_at_launch・lib/tests/test_declared_checks.py::LaunchHowRecordedCase.test_role_material_reads_how_decided_at_launch・lib/tests/test_declared_checks.py::CmdMaterialCase.test_test_cmd_callers_launch_by_command_argv・tests/workflows/test_test_gate.py::ResultScriptCase.test_shell_test_cmd_names_how_it_was_launched
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば test_cmd を渡す run の test-gate/base/run.json の material.checked か detail の「（起こし方 direct）」と、test-gate/base/evidence.md の「走らせた: test_cmd（direct）」）
  - 狭め: 無し

- T21 起こせない test_cmd（先頭の語が無い・実行できないファイル・env の前置きの後・パイプの中）は起こす前に確かめて not_run（環境の失敗）にし、直に起こした回は bash -c で包む手がかり（DIRECT_HINT）を添える。
  - 元: works/.shared/core/entry.py:689 `_cmd_material`・works/.shared/core/tree_run.py:164 `prove_launchable`
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::LaunchProofCase（4 本）・lib/tests/test_declared_checks.py::CmdMaterialCase.test_material_of_unlaunched_cmd_is_not_run・lib/tests/test_declared_checks.py::CmdMaterialCase.test_unlaunched_material_names_how_to_wrap_in_bash
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T22 終了コード 126・127 はコードの赤（found）として読み、起こせなかった扱いにしない。段の名やシェルかどうかで判じない。
  - 元: works/.shared/core/tree_run.py:199 `launch_kind`
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::CmdMaterialCase.test_material_of_exit_126_127_is_code_red・lib/tests/test_declared_checks.py::CmdMaterialCase.test_material_of_direct_same_as_step_127_is_code_red・lib/tests/test_declared_checks.py::SuitesLineCase.test_suites_line_reads_shell_exit_127_as_code_red・lib/tests/test_declared_checks.py::SuitesLineCase.test_suites_line_does_not_judge_shell_by_step_name
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T23 test_cmd の赤は found のまま、試験の報告を宣言できないので「走ったかは確かめていない」（gatemarks.BASELINE_UNVERIFIED）を添える。空の test_cmd は起こさずに not_run。
  - 元: works/.shared/core/entry.py:689-703・:650-662
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::CmdMaterialCase.test_test_cmd_red_says_unverified・lib/tests/test_declared_checks.py::CmdMaterialCase.test_empty_test_cmd_is_not_run_without_launching
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば test_cmd を渡す run の test-gate/base/run.json の material.detail の末尾（種の 2 件の赤））
  - 狭め: 無し

- T24 テストは別のプロセスグループで、標準入力は空・期限なし・uv run が足した環境（VIRTUAL_ENV・UV_* と PATH の頭）を外し PYTHONDONTWRITEBYTECODE=1 を立てて走らせる。段の行は {name, argv, out, err, started, exit, wall_s, tail}、起こせない段は exit None と error。
  - 元: works/.shared/core/board.py:379 `tree_runner`・works/.shared/core/tree_run.py:77 `outside_env`
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::TreeRunnerCase.test_tree_runner_strips_uv_env・lib/tests/test_declared_checks.py::TreeRunnerCase.test_tree_runner_shape
  - 本物の run: 筋書きでのみ（環境は記録に残らない）
  - 狭め: 無し

- T25 run が止められたら（SIGINT・SIGTERM・SIGHUP・直下の親の消失）テストが背景に起こした孫まで木ごと止め、返りを出さずに 128+信号で抜け、標準エラーに「止められた（信号 N）。テストは木ごと止めた」を出す。
  - 元: works/blk-tests/scripts/run_tests.py:105-107・works/.shared/core/tree_run.py:372 `run`
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::RunScriptCase.test_stopped_run_exits_without_output・lib/tests/test_tree_run.py::TreeRunCase.test_sigterm_stops_grandchildren・lib/tests/test_tree_run.py::TreeRunCase.test_parent_death_stops_tree
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T26 起こせない段（exit None）だけから来た赤は「環境で起こせなかった（コードの赤ではない）」と名指し、コードの赤と分ける（赤の原因 environment）。
  - 元: works/.shared/core/entry.py:768 `env_only_red`・:819 `suites_line`
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::SuitesLineCase.test_unlaunchable_step_is_named_apart_from_code_red・lib/tests/test_declared_checks.py::SuitesLineCase.test_code_red_is_not_env・lib/tests/test_declared_checks.py::SuitesLineCase.test_missing_command_127_is_red_like_the_material・lib/tests/test_green_cert.py::ClassifyCase.test_environment_only_broken_steps
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

### D JUnit の報告と「走ったか」

- T27 JUnit の報告を宣言した段は、終了コードでなく件数で走ったかを決める。報告が無い・段の起動より古い・XML として読めない・0 件・全部 error なら、赤でなく走らせられない status（base は awaiting_human・final は not_run）にし、reason に「基準の検査が走らなかった」と訳を書く。
  - 元: works/.shared/core/graphloops/rules/review-loop.py:2215 `_junit_unran`・:2236
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::RunEngineCase.test_unran_step_is_not_found
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T28 報告に走った試験と failure が在る段は終了コードが何でも found。報告を宣言していない赤の段の found には「走ったかは確かめていない（試験の報告の宣言が無い段: X）」を添える。
  - 元: works/.shared/core/graphloops/rules/review-loop.py:2236-2271
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::RunEngineCase.test_ran_red_step_is_found・lib/tests/test_declared_checks.py::RunEngineCase.test_red_step_without_report_says_unverified
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T29 走らせる前に無かった JUnit の報告は、読み終えたら（止められた時も）対象の木から消し、run の置き場の junit/<段の番号>.xml に写す。前から在った報告は消さない。段の名にパスの区切りが在っても落ちない。走らせたことで作業ツリーの指紋が変わらない。
  - 元: 無し（#69 で足した新しい能力。元は控えへの書き戻しだけ）
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::JunitReportCase・tests/workflows/test_test_gate.py::RunScriptCase.test_run_leaves_no_new_junit_report_in_the_tree
  - 本物の run: 筋書きでのみ（宣言の在る run なら test-gate/<mode>/junit/1.xml）
  - 狭め: 無し

### E 人に見せる行

- T30 一式の行が、任せ先の役の素材に合わせて書き分ける: clean・found なら「走らせた: 任せ先の CI の役 blk-ci が選んだ一式（素材の status X）」、ほかは「走らせなかった: 宣言の段・test_cmd（任せ先の CI の役 blk-ci が走らせなかった: 素材の status X）」、宣言が読めない engine は「宣言が読めないので engine が走らせなかった」、test_cmd が無ければ「test_cmd（渡されていない）」。
  - 元: works/.shared/core/entry.py:819 `suites_line`・works/tests/test_line_a.py:324
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::SuitesLineCase.test_role_status_words（#122）
  - 本物の run: test_cmd を渡さない run の test-gate/final/evidence.md の「- 走らせ方: role_needed・走らせた: 任せ先の CI の役 blk-ci が選んだ一式（…）」
  - 狭め: 無し

- T31 clean の checked に、走らせた宣言の sha の頭 12 字と段ごとの終了コードと秒を書く（何を根拠にした緑かを残す）。
  - 元: works/.shared/core/graphloops/rules/review-loop.py:2271
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::RunEngineCase.test_clean_names_declaration_sha_and_steps（#122）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

### F 直す前の結末と修正前のテストの行

- T32 base は直す前の結末 test-gate/base/baseline.json を、必須の欄 {suite, test_cmd, rev, exit, cases} と自分の欄（by・material・runs・skipped_steps・exit_codes・junit_steps・fingerprint）で書き、指し札で返す。final は入力 baseline の指し札から読み、""・null は「無い」と読む。
  - 元: 盤面の記録 process.baseline_checks（works/.shared/core/entry.py:792 `baseline_line` が読む）
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::ResultScriptCase.test_final_inherited_red_is_not_certified（base の中の assert は tests/workflows/test_test_gate.py::ResultScriptCase.base）・lib/tests/test_baseline_red.py::BaselineFileCase.test_round_trip_with_extra・lib/tests/test_baseline_red.py::BaselineFileCase.test_missing_field_is_value_error
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば test-gate/base/baseline.json（rev は種の HEAD、material.status、exit_codes）と節 test-gate-base__result の baseline の指し札）
  - 狭め: 無し

- T33 始めの記録の tdd_suite が在れば、一式を 1 回走らせて 1 件ごとの結末と終了コードを元の結末に置く。結末を返さずに落ちた一式は exit を残さず、final はそれを「元の結末が無い」と読んで今の赤を今回入れた物に数えない。
  - 元: works/.shared/core/graphloops/rules/review-loop-tdd.py:96 `_must_pass`（TDD の輪の元の結末）
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::ResultScriptCase.test_tdd_suite_cases_go_into_the_baseline・tests/workflows/test_test_gate.py::ResultScriptCase.test_suite_without_cases_leaves_no_baseline_exit
  - 本物の run: 筋書きでのみ（tdd_suite を持つ run なら baseline.json の suite・cases）
  - 狭め: 無し

- T34 final の証拠に「修正前のテスト」の 1 行を出す。記録が無い・素材が無い・壊れている・赤（段ごとの終了コードと「最後のテストの赤は修正前から在りうる」）・緑（「修正の後に出た赤でありうる。同じ一式とは限らない」）・走らせなかった（BASELINE_NOT_RUN）を分け、赤には範囲の外で回さなかった段も足す（文でなく記録の一覧から読む）。
  - 元: works/.shared/core/entry.py:792 `baseline_line`
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::BaselineLineCase（7 本）・tests/workflows/test_test_gate.py::ResultScriptCase.test_final_evidence_names_the_tests_before_the_fix
  - 本物の run: test-gate/final/evidence.md の「- 修正前のテスト: 赤（…）——最後のテストの赤は修正前から在りうる」（種は直す前が赤）
  - 狭め: 無し

- T35 一式の行と修正前のテストの行を、最後の人の関所の文と報告の冒頭に字のまま出す（何を根拠にした緑か・最後の赤が修正前から在りうるかを、ファイルを開かずに人が見る）。
  - 元: works/darkfactory/lib/line_edge.py:569-571 `_final_text`・報告の冒頭（entry.baseline_line・suites_line）
  - 今: 表
  - 証: tests/workflows/test_gate_head.py::FinalSectionsCase.test_final_text_carries_suites_and_baseline_lines・tests/workflows/test_line.py::AskFinalReadsCase.test_final_text_lists_suites_baseline_and_left_tests・tests/workflows/test_report.py::FactsCase.test_green_cert_section_carries_the_baseline_line・lib/tests/test_runreport.py::LinesCase.test_tests_head_lines_and_deleted_files（報告の冒頭）
  - 本物の run: 最後の関所の文（ask-final の text。置き場の控えは部分 B2 の final-gate.md。gates/gate-final.json は人の答え）に行が在るか。report/report.md の「試験の記録（最後）」の指し札
  - 狭め: #69 と #74 の間 → 部分 B2 で戻した。報告では冒頭でなく緑の認証の節に出す（報告の冒頭の並びは部分 C）

### G 赤の原因と緑の認証

- T36 final の赤の原因の順: 素材が clean なら ""。赤の段が全部起こせない段なら environment（素材が not_run でもこちらが先）。素材が not_run・awaiting_human・not_applicable なら incomplete。JUnit を宣言した段が走らなかった時は、走った赤の段（declared_checks.ran_reds）が無ければ incomplete、在れば走った赤が勝つ（どちらも元の結末と比べるより先）。
  - 元: 無し（新。元は修正前のテストの行で人に見分けさせた）
  - 今: 表
  - 証: lib/tests/test_green_cert.py::ClassifyCase.test_clean・lib/tests/test_green_cert.py::ClassifyCase.test_environment_wins_over_not_run・lib/tests/test_green_cert.py::ClassifyCase.test_incomplete・lib/tests/test_green_cert.py::ClassifyCase.test_incomplete_comes_before_the_baseline・lib/tests/test_green_cert.py::ClassifyCase.test_broken_mixed_with_red_is_not_environment・lib/tests/test_green_cert.py::ClassifyCase.test_ran_red_wins_over_an_unran_step・tests/workflows/test_test_gate.py::ResultScriptCase.test_final_not_run_is_incomplete
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 節 test-gate-final__result の red_cause（種で直しが通れば ""））
  - 狭め: 無し

- T37 元の結末の 1 件ごとの結末と比べ、今落ちた試験に元で通っていたか元に無かった物が在れば introduced、落ちた物が全部元でも落ちていて赤の段が全部 JUnit の段なら inherited、ほか（JUnit の無い赤の段・shell の test_cmd の赤・元の結末が無い）は原因の無い赤 "" と BASELINE_UNVERIFIED。
  - 元: works/.shared/core/graphloops/rules/review-loop-tdd.py:96 `_must_pass`（判定の部品）
  - 今: 表
  - 証: lib/tests/test_green_cert.py::ClassifyCase.test_introduced・lib/tests/test_green_cert.py::ClassifyCase.test_case_absent_from_baseline_is_introduced・lib/tests/test_green_cert.py::ClassifyCase.test_inherited・lib/tests/test_green_cert.py::ClassifyCase.test_introduced_and_inherited_mixed_is_introduced・lib/tests/test_green_cert.py::ClassifyCase.test_no_baseline_is_causeless・lib/tests/test_green_cert.py::ClassifyCase.test_red_step_without_junit_is_not_inherited・tests/workflows/test_test_gate.py::ResultScriptCase.test_final_inherited_red_is_not_certified・tests/workflows/test_test_gate.py::ResultScriptCase.test_final_introduced_red_is_not_certified
  - 本物の run: 筋書きでのみ（種に JUnit の宣言が無いので、test_cmd の赤は ""。種に .review-checks.json と junit を足せば inherited を本物で見られる）
  - 狭め: 無し

- T38 赤の原因の要約に落ちた試験の鍵を 10 件まで並べ、超えた分は「ほか N 件」と数える。
  - 元: 無し（新）
  - 今: 表
  - 証: lib/tests/test_green_cert.py::ClassifyCase.test_summary_lists_ten_keys_and_counts_the_rest（#122）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T39 final の緑は、走らせる前・後・返す時の 3 つの指紋（HEAD と差分の hash。差分は追跡のファイルと .gitignore に当たらない未追跡のファイル）が揃う時だけ認証する。違えばどれが違ったかを理由に書く。赤は原因が何でも認証しない。green は bool の True だけ。
  - 元: 無し（新。ASF の型 A3）
  - 今: 表
  - 証: lib/tests/test_green_cert.py::CertifyCase・lib/tests/test_green_cert.py::FingerprintCase・tests/workflows/test_test_gate.py::ResultScriptCase.test_final_green_is_certified_with_fingerprint_and_tree_change_voids_it
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 節 test-gate-final__result の ok と fingerprint、test-gate/final/evidence.md の「- 指紋: 走らせる前 …・後 …」）
  - 狭め: 無し

- T40 final で任せ先の役が書いた緑は、機械が走らせていない自己申告として認証しない（ok false。証拠に「任せ先の自己申告の緑（機械が走らせていない）」）。役の指示書にも「自己申告として人に諮られる」と書く。
  - 元: works/.shared/core/graphloops/rules/review-loop.py:950 `_ci_by_engine`・:2093-2105・works/blk-tests/scripts/run_tests.py:67-68
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::ResultScriptCase.test_final_role_green_is_self_reported_and_not_certified・lib/tests/test_green_cert.py::CertifyCase.test_final_self_reported_green_is_not_certified
  - 本物の run: test_cmd を渡さない run の節 test-gate-final__result の ok=false・green=true と test-gate/final/evidence.md の「- ok: false（任せ先の自己申告の緑（機械が走らせていない））」
  - 狭め: 無し

- T41 自己申告の緑・走らせなかった CI を人に諮る時、「engine が走らせた結果ではない。走らせる語を宣言 .review-checks.json に書けば次から engine が走らせる」と次の手を添え、確かめて続けるか止めるかを聞く。
  - 元: works/.shared/core/graphloops/rules/review-loop.py:2093-2115（ask ci_unverified）
  - 今: 表
  - 証: tests/workflows/test_gate_head.py::FinalSectionsCase.test_self_reported_green_names_how_to_declare・lib/tests/test_runreport.py::LinesCase.test_tests_head_lines_and_deleted_files（報告）
  - 本物の run: test_cmd を渡さない run の最後の関所の文（置き場の控えは部分 B2 の final-gate.md）
  - 狭め: #69 と #74 の間で落ちた → 部分 B2 で戻した。報告の側は部分 C

- T42 base の認証: 素材が clean・found・not_applicable・awaiting_human なら ok（直す前の赤と、走らせられなかった系統は控えるのが仕事。awaiting_human は #495 で ok に足した。T69）、not_run・carried_over・素材が無いなら ok false（緑を仮定しない）。base の任せ先の緑は ok にする。
  - 元: works/blk-ci/prompts/p0.local_checks.md（awaiting_human）・works/.shared/core/ci_role.py:331 `collect`
  - 今: 表
  - 証: lib/tests/test_green_cert.py::CertifyCase.test_base・lib/tests/test_green_cert.py::CertifyCase.test_final_self_reported_green_is_not_certified・tests/workflows/test_test_gate.py::ResultScriptCase.test_base_without_material_is_not_ok・tests/workflows/test_test_gate.py::ResultScriptCase.test_base_that_cannot_run_is_kept_and_names_why・tests/workflows/test_test_gate.py::ResultScriptCase.test_role_clean_material_written_by_ci_accept_is_read
  - 本物の run: 節 test-gate-base__result の ok（種は found なので true）
  - 狭め: 無し

- T43 返す節は落ちない。境の口・lib の import・入力の誤り（start が JSON でない・ほかの run の指し札・baseline の先が無い・壊れた baseline・知らない形・run.json が無い）を全部捕まえ、終了 0 で ok false・red_cause incomplete と、誤りを名指した証拠（書けなければ failure.txt）の指し札を返す。
  - 元: works/blk-tests/scripts/run_tests.py:82-109（元は終了 2 で落ちる）
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::ResultScriptCase.test_broken_inputs_return_incomplete_without_failing・tests/workflows/test_test_gate.py::ResultScriptCase.test_lib_that_cannot_be_imported_returns_incomplete_without_failing
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T44 任せ先の役が素材を渡さなかった（輪が回らなかった・拒み続けた）時、base も final も red_cause incomplete で緑を仮定しない。
  - 元: works/.shared/core/ci_role.py:349-356 `collect`
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::ResultScriptCase.test_base_without_material_is_not_ok
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T45 3 回とも拒まれて諦めた時、最後の拒否の文を人に見える所に出す（元は盤面の止まりの理由「<節> の返答が 3 回とも受け付けで拒まれた（最後の拒否: …）」）。
  - 元: works/.shared/core/ci_role.py:349-356 `collect`
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::ResultScriptCase.test_given_up_role_names_last_reject
  - 本物の run: 筋書きでのみ
  - 狭め: #69 で落ちた（挙げていない）。Archon で不可でない → 戻す → 部分 C で戻した

- T46 同じ run で同じ形をもう 1 度差し込んだ時、前の回の素材と拒否を読まずに今の木で走らせ直す（前の任せ先の素材で今の木を認証しない）。
  - 元: 無し（元は周ごとの置き場 r<N>）
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::ResultScriptCase.test_rerun_in_the_same_run_does_not_read_the_earlier_material
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T47 止められた後の呼び直し（resume）で、前の走りのログを上書きしない（空いた番号の置き場 runs/r<N>/<節>.a<k>/）。
  - 元: works/.shared/core/board.py:1404 `_log_dir`・works/tests/test_board_engine_run.py:321 test_rerun_keeps_earlier_logs
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::RunScriptCase.test_rerun_keeps_earlier_logs
  - 本物の run: 筋書きでのみ
  - 狭め: #69 で落ちた（T46 の副作用。挙げていない）。Archon で不可でない → 戻す（ログだけ番号で分ける） → #122 で戻した

### H 任せ先の CI の役

- T48 任せ先の CI の役は by role_needed の時だけ起こす。道具は読むだけとテストを走らせる Bash（Read・Grep・Glob・Bash・WebSearch・WebFetch。Edit・Write 無し）、模型は sonnet・medium、settingSources [user]、新しい会話（拒まれた後は出し直しの役 ci-fix が同じ会話の続きで拒まれた欄だけを返す。#571）。sandbox は元と同じ形（網は全部・localhost・allowWrite ['/']・failIfUnavailable・allowUnsandboxedCommands false）。
  - 元: works/blk-ci/blk-ci.yaml:87-105
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::YamlCase.test_role_node_reads_only・tests/workflows/test_test_gate.py::YamlCase.test_role_node_matches_works_blk_ci・tests/workflows/test_test_gate.py::YamlCase.test_loop_matches_give_up
  - 本物の run: test_cmd を渡さない run の節 test-gate-base__ci-loop.ci・test-gate-final__ci-loop.ci の記録
  - 狭め: 無し

- T49 本物の作業ツリーへの書き込みを、包み（adapter）が印の旗 no-tree-write を見て起動ごとに denyWrite に足して塞ぐ。切符の無い起動は起こさない。包みを宣言した run は受け付けが包みの起動の記録で柵が掛かったかを見て、無ければ止める。包み無しの run は知らせ NO_ADAPTER_NOTE を出す。宣言が読めなければ役を起こさずに止める。
  - 元: works/.shared/core/ci_role.py:150 `fence`・:274-298 `take`・:76 NO_ADAPTER_NOTE・works/blk-ci/blk-ci.yaml:28-42
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::YamlCase.test_role_cannot_write_the_checkout・tests/workflows/test_test_gate.py::YamlCase.test_role_node_matches_works_blk_ci・tests/shared/test_fence.py（一覧の組み方・印の読み方と、本物の claude で書き込みが止まること。claude の無い所では見送る）・tests/bin/test_launcher.py::LauncherTest.test_executing_launch_puts_the_fence_before_claude・tests/bin/test_launcher.py::LauncherTest.test_fence_denies_what_later_launches_run_outside_the_sandbox・tests/bin/test_launcher.py::LauncherTest.test_env_file_naming_claude_bin_path_stops_the_run・tests/bin/test_launcher.py::LauncherTest.test_env_file_naming_the_fence_records_stops_the_run・tests/shared/test_fence.py::MainTest.test_marked_launch_is_recorded_with_its_cwd・tests/shared/test_fence.py::MainTest.test_unwritable_record_stops_before_claude・tests/shared/test_fence.py::FencedSinceTest.test_missing_old_or_elsewhere_launches_are_not・tests/shared/test_fence.py::FencedSinceTest.test_rows_written_by_the_fence_are_read_back・tests/workflows/test_test_gate.py::CiRoleCase.test_declared_run_with_a_relative_record_path_stops_before_the_role・tests/workflows/test_test_gate.py::CiRoleCase.test_declared_run_without_a_fenced_launch_stops_at_once・tests/workflows/test_test_gate.py::CiRoleCase.test_declared_run_ignores_launches_before_prep・tests/workflows/test_test_gate.py::CiRoleCase.test_declared_run_with_a_fenced_launch_is_accepted・tests/workflows/test_test_gate.py::ResultScriptCase.test_role_run_without_the_fence_declaration_carries_the_note
  - 本物の run: 筋書きでのみ
  - 狭め: #69 で狭めた（PR の「能力の狭め」1 つ目）。Archon で不可でない（packages/workflows/src/schemas/dag-node.ts:109 に sandbox.filesystem.denyWrite が在る。節の値は固定の YAML なので、run ごとに違う共有の .git・対象の本体の作業ツリー・worktree.path を替えた対象の作業ツリーは名指せず、書ける——実測 2026-10-13・#293。起動の直前に一覧を組む包みを #309 で戻した）→ 持ち主の確かめ 決め: 戻すと決めた。run ごとの作業ツリーを denyWrite で塞げないと実測で分かった時だけ源の行つきで狭め。→ 残りの受け付けが包みの起動の記録で柵が掛かったかを見て止める所と知らせ NO_ADAPTER_NOTE と、宣言が読めない（絶対パスでない）run を役を起こす前に止める所は #360 で戻した（包みを通らない起動にも固定の値は残る）。区分 T の issue（線の配線の文書の「この文書の外」の「決めた物」）

- T50 役はテストを作業ツリーの写し（同じ commit に未コミットの変更と未追跡のファイルを載せた独立の clone。一時の置き場の直下の works-factory-ci-*）の上で走らせ、一時の置き場 tmp も渡す。
  - 元: works/.shared/core/ci_role.py:177 `_make_copy`・:189 `snapshot`
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::CiRoleCase.test_prep_copies_tree_and_passes_reject
  - 本物の run: test_cmd を渡さない run の節 test-gate-base__ci-loop.ci-prep の copy_dir・tmp_dir
  - 狭め: 無し

- T51 受け付けは役を起こす前の本物の作業ツリーの姿（porcelain・HEAD からの差分・git が無視するパス・HEAD・枝）と今を比べ、変わっていれば変わった物を名指して「読むだけの役が作業ツリーを変えた…写しの上で走らせ直せ」と拒む。元に戻せば通る。
  - 元: works/.shared/core/ci_role.py:299-304 `take`
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::CiRoleCase.test_tree_change_rejected・tests/workflows/test_test_gate.py::CiRoleCase.test_branch_switch_rejected
  - 本物の run: 筋書きでのみ（木を変えない健全な役では拒否が出ない）
  - 狭め: 無し

- T52 出し直しの回も、役を起こす前の最初の姿を残す（役が変えた後の姿で置き換えない）。写しが消えていれば作り直す。
  - 元: works/.shared/core/ci_role.py:189-201 `snapshot`
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::CiRoleCase.test_retry_keeps_the_first_snapshot
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T53 前の回の拒否の理由を次の回の指示書の頭に置き、「理由のところを直した返答を丸ごと出し直せ」と言う。拒否の文の中の `$<節>.output.<欄>` を Archon が置き換え直して輪が落ちないように渡す（元の裁定 R44: $LOOP_PREV で指示書に直に貼らない）。
  - 元: works/.shared/core/ci_role.py:236-241 `prep`（REJECT_HEADING）
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::YamlCase.test_loop_does_not_paste_previous_reject_by_loop_prev（旧 test_prep_takes_previous_reject）・tests/workflows/test_test_gate.py::CiRoleCase.test_reject_with_a_reference_reaches_the_prompt_verbatim・tests/workflows/test_test_gate.py::CiRoleCase.test_prep_copies_tree_and_passes_reject
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（形を変えた。落ちないかは未確かめ）

- T54 3 回目の拒否で done・give_up にして輪を抜ける（max_iterations で落とさない）。試行の番号 1・2・3 を指示書に渡し、諦めた時も写しを消し、受け付けていない素材を残さない。
  - 元: works/.shared/core/ci_role.py:256-264 `_reject`・:75 GIVE_UP_AFTER
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::CiRoleCase.test_gives_up_after_three_rejections・tests/workflows/test_test_gate.py::YamlCase.test_loop_matches_give_up
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T55 読めない返答（JSON でない・オブジェクトでない）は受け付けの拒否として数え、理由を次の回へ渡す。
  - 元: works/.shared/core/ci_role.py:313 `refuse`・works/tests/test_blk_ci.py:570 test_unreadable_reply_is_a_reject
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::CiRoleCase.test_unreadable_reply_is_a_reject（#122）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（試験だけが欠け）

- T56 役の素材の決まり: 形（status は found・clean・not_applicable・awaiting_human・not_run の 5 語。count は 0 以上の整数。carried_over・from_round は拒む）、status ごとに要る欄（found は count と detail、clean は checked、ほかは reason。空の文も拒む）、形ごとの走らせられない時の status（base は awaiting_human・final は not_run。逆は拒む）。拒否の文は「素材の欄を直した返答を丸ごと出し直せ: …」。
  - 元: works/blk-ci/blk-ci.yaml:108-141（写しの schema）・写しの graph の post_check・works/.shared/core/scripts/review-record.py:140-151
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::MaterialProblemsCase・tests/workflows/test_test_gate.py::CiRoleCase.test_gives_up_after_three_rejections
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T57 役の節の output_format の素材は lib の MATERIAL_SCHEMA と同じ物で、節 run の material はそれに null を足した物。
  - 元: works/.shared/core/ci_role.py:74 OUTPUT_FORMAT
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::YamlCase.test_role_node_matches_works_blk_ci・tests/workflows/test_test_gate.py::YamlCase.test_run_material_is_the_material_schema_or_null
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T58 写しの後始末: 通った時と諦めた時は ci-accept が、役の節が落ちて ci-accept が回らなくても返す節が、写しの置き場を消す。消すのは一時の置き場の直下の頭の合うフォルダだけで、symlink は辿らない（役が書ける snapshot の top が別の所を指しても消さない）。
  - 元: works/.shared/core/ci_role.py:321-328 `_drop_copy`・works/tests/test_blk_ci.py:347 test_drop_copy_only_own_temp_dirs
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::CiRoleCase.test_done_removes_only_its_own_copy_folder・tests/workflows/test_test_gate.py::ResultScriptCase.test_copy_left_by_a_fallen_role_is_removed・tests/workflows/test_test_gate.py::CiRoleCase.test_gives_up_after_three_rejections
  - 本物の run: test_cmd を渡さない run の後に、一時の置き場に works-factory-ci-* が残らないこと
  - 狭め: 無し

- T59 拒んだ回は、役が run の置き場に自分で置いた ci-material.json を消す（返す節が受け付けていない素材を読まない）。
  - 元: 無し（#69 の独立の目の直し 5）
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::CiRoleCase.test_rejected_reply_leaves_no_material_the_role_wrote
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- T60 役の指示書の決まり: 走らせられなければ緑を仮定しない（base は awaiting_human・final は not_run）。実行器が起動を拒んだ・試験が 0 件・起動の前のエラーは走っていない扱いで、走ったかは件数で決める。終わるまで待つ（572 件の途中の 537 件で clean と書いた実測）。複数の系統は全部走らせ、checked に系統ごとの終了コード。結果は自己申告として人に諮られる。本物を 1 文字も変えない。
  - 元: works/blk-ci/prompts/p0.local_checks.md・works/blk-ci/prompts/p4.ci.md・works/blk-ci/commands/ci.md・works/tests/test_blk_ci.py:176 test_command_is_thin_and_prompts_keep_the_rules
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::YamlCase.test_ci_command_keeps_the_rules（#122）・tests/workflows/test_test_gate.py::CopiedTextsCase.test_every_command_is_its_original_with_only_ledgered_edits（元の 3 つと台帳 5 組）
  - 本物の run: test_cmd を渡さない run の節 test-gate-base__ci-loop.ci の指示書（Archon の記録）
  - 狭め: 無し（字は在る。縛る試験が無い）

- T61 修正の後の役の指示書に、前の周で人へ諮った答えと、台帳の kind=awaiting・origin=local_checks の未決の問いを渡し、未決の問いが在る間は CI を走らせても awaiting_human のまま書かせる（人に諮っている最中の欄を clean で上書きしない）。
  - 元: works/blk-ci/prompts/p4.ci.md:7-11・works/.shared/core/ci_role.py:205-227 `render`
  - 今: 無し（表）
  - 証: 要追加（問いの台帳に当たる物を線が持った時）: tests/workflows/test_test_gate.py::CiRoleCase.test_final_prompt_carries_open_questions
  - 本物の run: 筋書きでのみ
  - 狭め: #69 の計画で落とした。Archon で不可でない → 持ち主の確かめ（台帳ごと無い。同じ能力を線の問いで持つか）

### I 使い回し・試験の枠

- T62 同じ run の中で、同じ作業ツリーの木・同じ命令・同じ環境の緑の一式の結果を使い回す（一式の全段が当たった時だけ子を起こさずに全段を使い、JUnit も書き戻す。走らせている間に木が変わった回は置かない。run をまたがない）。直す前の確かめと TDD の輪の頭が同じ test_cmd を 2 度走らせない。
  - 元: works/.shared/core/tree_run.py:670 `replay_group`・:750 `keep_group`・:779 `slotted_run`・works/.shared/core/board.py:379-433・works/CHANGELOG.md:30・:53（0.2.64）
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::ReuseCase.test_same_tree_same_suite_runs_once・lib/tests/test_declared_checks.py::ReuseCase.test_other_run_or_moved_tree_is_not_reused・lib/tests/test_declared_checks.py::ReuseCase.test_tdd_head_test_cmd_reads_the_base_keep・lib/tests/test_declared_checks.py::ReuseCase.test_reused_suite_writes_its_junit_back・lib/tests/test_declared_checks.py::TestModesCase.test_final_never_reads_reuse_store・lib/tests/test_tree_run.py::ReuseRunCase・tests/workflows/test_test_gate.py::RunScriptCase.test_base_rerun_reuses_the_green_suite_and_final_does_not・tests/workflows/test_fix.py::GroupChildScriptsCase.test_tdd_head_reuses_the_test_gate_base_test_cmd・lib/tests/test_blk_fix_tdd.py::TestStart.test_head_reuses_the_green_baseline_of_the_same_run・tests/shared/test_archon_contract.py::ArchonContractTest（script の節に立つ変数の名）
  - 本物の run: 筋書きでのみ
  - 狭め: #69 で外した。PR は持ち主の決め no-queue を理由に挙げるが、no-queue（docs/owner-decisions.md:62-66）は修正の並べの待ちの列の決めで、使い回しは reuse-results（:263-268「使い回すのは入力が変わらない時だけ」「最後のテストは省かない」）に当たる。Archon で不可でない → 持ち主の確かめ 決め: 戻すと決めた（reuse-results）。区分 T の issue（線の配線の文書の「この文書の外」の「決めた物」） → #122 で戻した

- T63 使い回した段の出どころ（run・時刻・鍵）を素材の checked・段の行・報告に出し、使い回さなかった理由（reuse_off）を段の行・trace に出す。旗 GRAPHLOOPS_RERUN_CHECKS=1 で必ず走らせる。
  - 元: works/.shared/core/board.py:436 `_reused_note`・works/.shared/core/entry.py:706 `_reused_material`・works/.shared/core/tree_run.py:433 RERUN_ENV・:496 `note_fields`・:501 `reused_text`
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::ReuseCase.test_reused_steps_named_in_material_and_rows・lib/tests/test_declared_checks.py::ReuseCase.test_rerun_flag_runs_again
  - 本物の run: 筋書きでのみ
  - 狭め: T62 と同じ 決め: 戻すと決めた（reuse-results）。区分 T の issue（線の配線の文書の「この文書の外」の「決めた物」） → #122 で戻した

- T64 機械全体の試験の枠（slotwrap.sh・TESTSLOT_N）を通してテストを走らせ、枠を待った秒 wait_s を段の行に、待ちを状態の表示と herdr に見せる（並べすぎない）。
  - 元: works/.shared/core/tree_run.py:779 `slotted_run`・works/tests/test_tiers.py:923 RunSlotCase・:987 SlotWaitShownCase
  - 今: 無し（表）
  - 本物の run: 筋書きでのみ
  - 狭め: #69 で外した。absent: 戻さない（持ち主の決め `no-queue`。docs/owner-decisions.md の 2026-10-12 の決め。#118）
  - 証: 要らない（戻さないと決めた能力）

- T65 最後のテストは同じ run の中の前の結果を使い回さない（同じ木で 2 度呼べば 2 度走らせる）。
  - 元: works/blk-tests/scripts/run_tests.py:49-66（RERUN_ENV）
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::TestModesCase.test_final_never_reads_reuse_store
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

### J 線と入口

- T66 最後のテストの赤で run を止めず、赤を最後の人の関所と報告に見せる（ブロックの返す節は落ちずに ok false を返し、線は独立の目・関所・報告へ進む）。
  - 元: works/blk-tests/blk-tests.yaml:4-5・works/blk-tests/scripts/run_tests.py:78
  - 今: 表
  - 証: lib/tests/test_declared_checks.py::TestModesCase.test_final_red_suite_is_ok・tests/workflows/test_test_gate.py::FixtureCase.test_fixtures_pass_in_archon・tests/workflows/test_gate_head.py::FinalHeadCase.test_three_lines_and_reasons
  - 本物の run: 筋書きでのみ（種は最後のテストが緑の見込みで、赤で止めずに進む道を通らない。在れば節 test-gate-final__result の ok・green・red_cause と gates/gate-final.json）
  - 狭め: 無し

- T67 最後の関所の 1 行目のテストの語が、緑・赤（原因）・認証できなかった（原因）を区別する。
  - 元: works/darkfactory/lib/line_edge.py:567（rest.tests_word）
  - 今: 表
  - 証: tests/workflows/test_gate_head.py::FinalHeadCase.test_three_lines_and_reasons。弱い: final_got の既定 tests_ok=True と green=False の組は test-gate の final が返さない（final の赤は必ず ok false）。本物の赤は「認証できなかった（introduced）」と出て「赤」にならず、「赤」の枝は届かない。要追加: tests/workflows/test_gate_head.py::FinalHeadCase.test_red_final_says_red — tests_ok=False・green=False・red_cause=introduced で 1 行目が「テストは赤（introduced）」
  - 本物の run: 最後の関所の文の 1 行目（置き場の控えは部分 B2 の final-gate.md）
  - 狭め: 無し（字の誤り）

- T68 報告の「直す前のテスト」の行が、走らせられなかった base（incomplete）を「赤」と言わない（元は MATERIAL_WORDS で状態の語を出した）。
  - 元: works/.shared/core/entry.py:792 `baseline_line`（gatemarks.MATERIAL_WORDS）
  - 今: 表
  - 証: lib/tests/test_runreport.py::BuildCase.test_unrun_base_is_not_called_red
  - 本物の run: report/report.md の「直す前のテスト:」の行（種は found なので「赤」で正しい）
  - 狭め: 無し（字の誤り。#354 で直した）

- T69 直す前に走らせられない時（awaiting_human）は緑を仮定せずに人に聞き、人が確かめて続けられる。
  - 元: works/blk-ci/prompts/p0.local_checks.md（awaiting_human）・写しの graph の start の人待ち
  - 今: 表
  - 証: tests/workflows/test_test_gate.py::ResultScriptCase.test_base_that_cannot_run_is_kept_and_names_why・lib/tests/test_green_cert.py::CertifyCase.test_base・lib/tests/test_outcome.py::ReadingCase.test_base_with_unrunnable_ci_reaches_fixed_needs_check_naming_the_reason・lib/tests/test_runreport.py::BuildCase.test_awaiting_human_base_names_what_could_not_run
  - 本物の run: 筋書きでのみ
  - 狭め: #74 の線の形（base の ok が偽なら judge を飛ばした）→ #495 で戻した

- T70 入口が test_cmd を Archon に渡す前に、worktree で効かない形を分けて知らせる。対象の手元を絶対パスで指す・対象を editable で入れた外の仮想環境を使う形は、黙った偽の緑になるので止める。git が無視する物を相対で指す形は注意だけ。確かめの殻が落ちたら止める。WORKS_USE_ALLOW_TESTCMD（今は WORKS_FACTORY_ALLOW_TESTCMD）で通せる。
  - 元: works/dev/testcmd_check.py・works/dev/use.sh:1020-1044・works/tests/test_testcmd_check.py（24 本）
  - 今: 表
  - 証: tests/bin/test_testcmd_check.py::TestCmdCheck.test_absolute_reference_to_the_checkout_stops・tests/bin/test_testcmd_check.py::TestCmdCheck.test_relative_ignored_path_is_named・tests/bin/test_testcmd_check.py::TestCmdCheck.test_activated_virtualenv_with_editable_target_is_named_unless_uv_run（元の 24 本の写し）・tests/bin/test_launcher.py::LauncherTest.test_test_cmd_running_the_checkout_stops_before_archon・tests/bin/test_launcher.py::LauncherTest.test_test_cmd_check_that_fails_stops_unless_allowed
  - 本物の run: 筋書きでのみ（入口の出力。種の test_cmd は相対で手元を指さない）
  - 狭め: どの PR も挙げていない（黙って落ちた）。Archon で不可でない → #495 で戻した（入口 bin/ の住処） 決め: 住処は bin/_lib/testcmd_check.py（元の名と中身。殻が Archon を起こす前に照らす）。E13 の例外は要らない。L-E50・L-G08 と同じ bin の issue（線の配線の文書の「この文書の外」の「決めた物」）

- T71 run の後の CI の赤（run が見ない重い試験）を、次の run の依頼の prior_failures の行に載せる。
  - 元: works/.shared/core/carry.py:265 `carry_ci`
  - 今: 表
  - 証: lib/tests/test_carry_ci.py::CarryCase.test_ids_become_prior_failures_rows
  - 本物の run: 筋書きでのみ（run の外の CI が赤を言った後）
  - 狭め: 無し

### PR #69 の証の照らし（本文の対応表を main で確かめた結果）

- 本文が挙げた試験は全部 main に在り、上の行に assert の行を書いた。
- 字や形だけを見て、能力を外しても赤にならない物は 2 つ。test_prep_takes_previous_reject は YAML の字だけで、R44 の落ち方は照らさない（T53）。test_role_node_reads_only は ci.md の決まりの中身を見ない（T60）。
- 「移さなかった試験」のうち次の 6 つは、外した仕組みでなく残った仕組みを縛っていた。移すべき物: test_ci_test_cmd.py の test_fallback_after_run_reuses_test_cmd_result（T9）、test_board_engine_run.py の test_rerun_keeps_earlier_logs（T47）、test_blk_tests_delta.py の test_final_does_not_count_archon_workspace_as_change（T15）、test_blk_ci.py の test_unreadable_reply_is_a_reject（T55）と test_command_is_thin_and_prompts_keep_the_rules（T60）、test_line_a.py:324 の役の一式の字（T30）。

### T の穴

数:

- 行の総数: 71
- 今: 無し: 2（T61・T64）。T69・T70 は #495 で、T8・T9・T16・T47・T62・T63 は #122 で、T35・T41・T45 は線の配線の部分 B2・C で戻した
- 証が要追加か弱い: 2（T61・T67）。T69・T70 は #495 で、T68 は #354 で、T7・T13・T15・T19・T30・T31・T38・T53・T55・T60 は #122 で試験を足して閉じた
- 狭めたのに Archon が強いていない: 2（T61・T64）。T69・T70 は #495 で、T49 は #309・#360 で戻した。Archon のせいで不可と言える行は 1 つも無い
- 字の誤り（狭めではない）: 1（T67）。T68 は #354 で直した

- 持ち主に聞く物（前の決め・定石・元の作りのどれでも 1 つに決まらない）
  1. T62・T63・T64 同じ run の中の使い回しと機械全体の試験の枠。→ 決めた: T62・T63 は戻す（reuse-results）。T64 は戻さない（`no-queue`。#118）
  2. T49 任せ先の役の書き込みの守り（包みの柵）。→ 決めた: 戻す（denyWrite で塞げないと実測で分かった時だけ源の行つきで狭め）
  3. T16 依頼の where を入口の範囲の照らしに足す。→ 決めた: 戻す（superset）
  4. T61 人に諮っている最中の CI の欄を clean で上書きさせない決まり。台帳が無いので、線の問いで持つか
  5. T69 直す前に走らせられない run を、人に聞いて続けられるようにするか、止めて報告に回すままか。→ 決めた: 続ける（#495。今の works と同じく、一部でも全部でも止めない）
  6. T8・T9 宣言の sha の照合と engine の素材の受け付け。計画と走りが同じ関数の中に入って目的が消えたと見てよいか（T9 の material_problems を engine の素材にも当てるのは聞かずに足してよい）
- 聞かずに戻す物（どの PR も挙げずに黙って落ちた）: T35・T41（線と報告に試験の行と次の手を出す）、T45（諦めた時の最後の拒否の文）、T47（resume で前のログを残す）、T70（test_cmd の形の確かめ。偽の緑を防ぐ入口の柵）。T35・T41・T45 は線の配線の部分 B2・C で、T47 は #122 で、T70 は #495 で戻した
- 本物の run の注意: 種には `.review-checks.json` が無い。engine の段・JUnit・赤の原因 inherited・introduced・範囲の宣言は、種のままでは本物の run に出ない。段 1 の本物の run で見るなら、種に JUnit を書く宣言を足すか、test_cmd を渡す run と渡さない run を 1 本ずつ回す。渡す run は T5・T20・T23・T39、渡さない run は T6・T40・T48・T50・T58 を見られる
- 元にも無かった物: 揺れる（flaky）試験の走らせ直しは、元の試験の関門にも無い。狭めではない

## E: 独立の目（eyes）の能力の棚卸し

範囲: 元の works/blk-eyes・blk-structure の直した後の実測（元の段 B）と構造の目の行の形・前提の検算と前提の入力・review-loop.py の目の機械の照らし。今は main の workflows/eyes/・lib/eyeverdict.py・lib/stage_b.py・lib/structmark.py・lib/eye.py と、線（PR #74 の頭）の受け手。

読み方: 「元」は works/ の下（2aa7c66c）、「証」は main の名（README.md の「指しの形」）。「今」は印（「表」か「無し（表）」、住処を書かなかった行は「無し」か空）だけを持ち、住処の字は docs/works-parity.md の「前の棚卸しの今」が持つ。PR #67 の「行ごとの証」に挙がった試験は全部 main に在ることを確かめた。挙がっていない能力と、形だけで赤にならない試験は「要追加」にした。

本物の run の欄は、seed（tests/e2e/target-seed: stats.py に 2 つの欠陥、厚さ 標準、最後の関所はいつも開く）を Archon で回した時に見える所。置き場は run の artifacts の下、節の id は include の頭付き（線の筋書き workflows/line/fixtures/standard.stubs.yaml の `eyes__verdict` などと同じ形）。

### 役の節の形

- E1 目の役の節は全部、読むだけ（作業ツリーを変えない宣言）で、1 回目は毎回新しい会話で起きる（R4 の受け付けに拒まれた後は、出し直しの役 r4-scope-fix が同じ会話の続きで拒まれた欄だけを返す。#571）。
  - 元: works/blk-eyes/blk-eyes.yaml:133-143 `r1-comments`（ほかの目も同じ形。輪の 1 回目は新しい会話）・works/blk-eyes/lib/eyes.py:474 `accept`
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_every_role_node_is_read_only
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 節 eyes__r1-minimality・eyes__r2-compare・eyes__r3-coherence・eyes__r4-loop.r4-scope が completed（Archon の checkout の照らしに当たっていない））
  - 狭め: 無し

- E2 役ごとの道具は元の表のとおり: 最小性と前提の検算（judge）と削除候補（comment-analyzer）は Read・Grep・Glob・WebSearch・WebFetch、R3・R4（inspector）は Read・Grep・Glob、比較役は Read だけ。書く道具と shell は持たない。
  - 元: works/blk-eyes/lib/eyes.py:78-81 `TOOLS`・`NODE_TOOLS`、works/tests/test_tool_parity.py:41 `NARROWED`
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_eye_tools_are_the_role_tools
  - 本物の run: 筋書きでのみ（YAML の静的な事実）
  - 狭め: 無し

- E3 役ごとのモデルと effort は元の表のとおり（削除候補 sonnet/medium、最小性・比較役・前提の検算 opus/high、R3・R4 sonnet/medium）。
  - 元: works/blk-eyes/blk-eyes.yaml:135-136,292-293,452-453,602-603,753-754,888-889、works/tests/test_tool_parity.py:312 `RoleModelCase`
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_role_model_and_effort_match_the_works_table
  - 本物の run: 節 eyes__r1-minimality などの記録のモデル名
  - 狭め: 無し

- E4 役は利用者の設定だけを読み（対象の CLAUDE.md を読まない）、sandbox を有効にして抜けを許さない。
  - 元: works/blk-eyes/blk-eyes.yaml:139,296,456,606,757,892（`settingSources: [user]`・sandbox）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_role_settings_copied
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- E5 比較役（R2）は既定の system prompt（cwd と git status の写しを持つ）を使わない（元の旗 isolated）。
  - 元: works/blk-eyes/lib/eyes.py:82-84 `ISOLATED_RUN_BY`・`ISOLATED_FLAG`、:187-190 `output_format`
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_r2_compare_runs_without_the_default_system_prompt
  - 本物の run: 筋書きでのみ（PR #67 も「モデルを本当に走らせた回ではまだ見ていない」と書く。seed の run で eyes__r2-compare の返りが git の状態に触れていないかを見る）
  - 狭め: 無し（→ Archon の packages/workflows/src/schemas/dag-node.ts:226 の systemPrompt で戻した）

- E6 比較役に届くのは目的・独立設計・設計の後に分かった前提・累積差分（と行数・変わったファイル・言語の 1 行）だけで、調査の経緯と判定の一覧は渡さない。
  - 元: works/.shared/core/graphloops/graphs/review-loop.json:4887 `r2.compare` の forbidden_inputs と reads
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_r2_compare_gets_no_forbidden_input
  - 本物の run: 筋書きでのみ（節 eyes__r2-compare に送った本文）
  - 狭め: 無し

- E7 累積差分は本文を貼らず、ファイルの置き場・行の数・変わったファイルを名指し、Read で最後の行まで読み切らせる。開いてよいのはそのファイルだけで、読めなければ推し量らずに reason に書かせる。
  - 元: works/blk-eyes/lib/eyes.py:109 `DIFF_ASK`、:363 `diff_section`
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_r2_compare_reads_the_whole_diff_file、tests/workflows/test_eyes.py::CopiedTextsCase.test_every_command_is_its_original_with_only_ledgered_edits
  - 本物の run: eyes/prep.json の diff_file・diff_lines・changed_files（seed では stats.py）
  - 狭め: 無し

- E8 R4 は R1・R2 の筋（最小性・比較・前提の検算）の後に起き、前の筋が落ちても飛ばない。
  - 元: works/blk-eyes/lib/eyes.py:72-74 `LANE_AFTER`、works/blk-eyes/blk-eyes.yaml:815-826 `r4-scope-route`（all_done）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_r4_waits_for_r1_and_r2_lanes、lib/tests/test_eyeverdict.py::CollectCase.test_fallen_r2_lane_still_runs_r4_and_is_named
  - 本物の run: 筋書きでのみ（前の筋が落ちても R4 が飛ばない道は種で通らず、節の順は nodes[] で照らせない。在れば節 eyes__r4-loop.r4-scope の始まりが eyes__r1-minimality と eyes__r2-compare の終わりより後）
  - 狭め: 無し

- E9 R1 の前段・比較役・前提の検算・R3 は互いを待たず、支度の後に並んで走る。
  - 元: works/blk-eyes/lib/eyes.py:26-27（並び）、works/tests/test_blk_eyes.py:1134 `test_four_eyes_in_parallel_processes`
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_eyes_run_side_by_side
  - 本物の run: 節 eyes__r1-comments・eyes__r2-compare・eyes__r3-coherence の走った時間が重なる
  - 狭め: 無し

### R1（コメントの削除候補と最小性）

- E10 コメントの削除候補が取れなくても R1 の本体を止めない（verdict を not_run に倒さない）。候補はファイルで渡り、無ければ前段は取れなかったと読み、candidates_note に訳を書かせる。
  - 元: works/blk-eyes/lib/eyes.py:85-88 `GIVE_UP_SKIPS`・:453-468 `_reject`（3 回拒まれたら省く）、review-loop.json:4574 `r1.comment_candidates` の does
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_r1_minimality_runs_without_the_comment_candidates、tests/workflows/test_eyes.py::ScriptCase.test_save_reply_writes_the_reply、tests/workflows/test_eyes.py::ScriptCase.test_prep_names_the_file_r1_comments_save_writes
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば eyes/r1-comments.json（候補と kept）、eyes/r1.json の candidates_note（前段が落ちた時））
  - 狭め: 無し

- E11 削除候補の役の定義は comment-analyzer の元の本文のまま（版 ce721c1f の sha256）。
  - 元: works/blk-eyes/lib/eyes.py:440 `rolekit.with_role_definition`（plugin の agents/comment-analyzer.md を頭に置く）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_r1_comments_carries_the_comment_analyzer_definition_verbatim
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- E12 削除候補の役に 3 つの指示を足す: 削る物は同じ内容の在り処を名指す、残す物も運ぶ事実を一文で言う、コメントアウトしたコード・編集の実況・名前の言い直しを引き金として探す。
  - 元: review-loop.json:4574 `r1.comment_candidates` の inputs「追加の 3 指示」
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_r1_comments_keeps_the_three_added_asks、tests/workflows/test_eyes.py::CopiedTextsCase.test_every_command_is_its_original_with_only_ledgered_edits
  - 本物の run: eyes/r1-comments.json の candidates[].same_content_at・kept[].fact
  - 狭め: 無し

- E13 最小性の役は、修正の返答の breaks.accepted の行が人に見せる一覧に載ることを知り、台帳に無いことだけを逃げ道の理由にしない（中身で見る）。
  - 元: works/blk-eyes/commands/r1-minimality.md（描いた写しの頭）、works/tests/test_blk_eyes.py:1414 `test_minimality_knows_where_handoffs_go`
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_minimality_knows_where_handoffs_go、tests/workflows/test_eyes.py::CopiedTextsCase.test_every_command_is_its_original_with_only_ledgered_edits
  - 本物の run: eyes/r1.json の ledger_audit
  - 狭め: 無し

- E14 最小性の役は問いの台帳を監査する（split の origin が目的の内側、fork に零処方が無いまま人に回した → redesign-needed）。台帳は判定の judgment.json の questions。
  - 元: review-loop.json:4672 `r1.minimality` の does・reads（record.questions）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ScriptCase.test_r1_minimality_reads_the_question_ledger、tests/workflows/test_eyes.py::CopiedTextsCase.test_every_command_is_its_original_with_only_ledgered_edits
  - 本物の run: eyes/prep.json の judgment_file、eyes/r1.json の ledger_audit
  - 狭め: 無し

- E15 最小性の役に規模の数値（足した行・消した行・文書の足した行・変わったファイル）を渡す。hunk の中の `----`・`+++i;` の行も数え、日本語名の引用されたパスも読む。
  - 元: works/.shared/core/graphloops/rules/review-loop.py:2153-2178 `scalars`（doc_lines は numstat）
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::ScalarsCase.test_counts_lines_and_files_from_the_diff、lib/tests/test_eyeverdict.py::ScalarsCase.test_hunk_lines_that_look_like_file_heads_are_counted、lib/tests/test_eyeverdict.py::ScalarsCase.test_quoted_non_ascii_path_is_read
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば eyes/prep.json の scalars（seed では stats.py の足した行と消した行））
  - 狭め: 無し（コードとコメントの比は E16）

- E16 コードとコメントの比（comment_lines・comment_ratio_pct）を測って R1 に渡す。
  - 元: works/.shared/core/graphloops/rules/review-loop.py:2128-2150 `SCALARS_FIXED`・`_comment_ratio`（comment-ratio.sh）
  - 今: 無し
  - 本物の run: eyes/prep.json の scalars に comment_ratio_pct が無い
  - 狭め: #67 で狭めた。absent: 戻さない（持ち主の決め `no-comment-ratio`。docs/owner-decisions.md の 2026-10-12 の決め。#118）
  - 証: 要らない（戻さないと決めた能力）

- E17 修正役が足した x_ の数値（x_scalars）を規模の数値に足し、形の外の欄（x_ で始まらない名・数でない値・object でない）は名指して落とす。
  - 元: review-loop.py:2175-2176（p3.fix の x_scalars）、review-loop.json:4077 p3.fix の x_scalars の patternProperties
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::ScalarsCase.test_fix_x_scalars_are_added、lib/tests/test_eyeverdict.py::ScalarsCase.test_x_scalars_outside_the_graph_shape_are_named、tests/workflows/test_eyes.py::ScriptCase.test_prep_pastes_the_premises_and_names_the_target_review_md。線の配線: tests/workflows/test_line.py::FixedCase.test_eyes_gets_the_fix_x_scalars・tests/workflows/test_fix.py::BlockScriptsCase.test_changed_carries_the_premise_drift_note_and_the_x_scalars・tests/e2e/test_line_scenarios.py::RefixInputsTest.test_eyes_get_the_fix_x_scalars（部分 D1）。部分 0 の時の証（そのまま残す）: lib/tests/test_eyeverdict.py::ScalarsCase.test_fix_x_scalars_are_added、lib/tests/test_eyeverdict.py::ScalarsCase.test_x_scalars_outside_the_graph_shape_are_named、tests/workflows/test_eyes.py::ScriptCase.test_prep_pastes_the_premises_and_names_the_target_review_md。線の配線は要追加: tests/workflows/test_line.py::…test_eyes_gets_the_fix_x_scalars — 線の eyes の with に x_scalars が在り、fix の返りの型に x_scalars が在る
  - 本物の run: eyes/prep.json の scalars（部分 D1 で fix の返り x_scalars → 線の fixed → eyes の with: x_scalars をつないだ）
  - 狭め: #67 の「約束を変える頼み 1」が fix と線（#74）で未だ。Archon で不可でない → 戻す → 部分 D1 で戻した

- E18 測れなかった規模の値は 0 にせず unmeasured に訳を置き、測れた分は返す。
  - 元: review-loop.py:2160-2178（process.scalars_unmeasured）
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::ScalarsCase.test_unreadable_diff_is_named_not_zero、lib/tests/test_eyeverdict.py::ScalarsCase.test_part_measured_returns_the_measured_part
  - 本物の run: 筋書きでのみ（eyes/prep.json の scalars の「（測れなかった: …）」）
  - 狭め: 無し

- E19 前の周の規模の数値と累積差分の行数の伸びを R1 に渡し、相殺の無い単調増の増分ごとに正当化を求める。
  - 元: review-loop.json:4672 `r1.minimality` の reads（loop.prev_scalars・loop.lines_ratio）、works/.shared/core/scripts/review-record.py:964-967
  - 今: 表
  - 証: 無し（1 run 1 周では値が無い）
  - 本物の run: 筋書きでのみ
  - 狭め: 1 run 1 周の決めから来た狭め。Archon で不可でない → run をまたいで規模の推移を運ぶかを持ち主に

### R1・R3・R4 の頭と観点

- E20 R1・R3 の頭に考えの住処の観点（concepthome.R1_HEAD・R3_HEAD）を貼り、そこに直した後の実測の数の 1 文（structmark.after_counts。控えが無ければ NO_AFTER）を入れる。
  - 元: works/blk-eyes/lib/eyes.py:90-93 `CONCEPT_HEADS`・`NO_AFTER`、:437-439 `prep`
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ScriptCase.test_r1_head_carries_after_counts
  - 本物の run: eyes/prep.json の r1_head・r3_head（seed では「柵の表は無い（知る場所の増えは数えていない）」と「変わったファイル 1 本」）
  - 狭め: 無し

- E21 考えの地図の節（concepthome.section）は R1・R3 にだけ、観点の後ろに貼る。R2・R4 には貼らない。
  - 元: works/blk-eyes/lib/eyes.py:91-92 `CONCEPT_FLAG`、works/tests/test_blk_eyes.py:480 `test_heads_only_on_r1_minimality_and_r3`
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_concept_map_only_on_r1_and_r3
  - 本物の run: eyes/prep.json の concept_map（seed は地図が無い形の節）
  - 狭め: 無し

- E22 目の指示書は版を git で読ませず、止めた cwd を Read・Grep・Glob で読ませる。
  - 元: works/blk-eyes/lib/eyes.py:142-151 `GIT_SHOW_SENTENCE`・`FROZEN_READ`
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_frozen_read_in_commands
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- E23 同梱の観点の正本 REVIEW.md（処方の最小性・導線を作る手段の優先順位・横断リスク観点）を R1 の前段・R1・R3・R4 に名指す。
  - 元: works/.shared/core/graphloops/rules/review-loop.py:35-38 `review_md_path`・:46-48 `on_init`
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ScriptCase.test_prep_names_the_bundled_review_md
  - 本物の run: eyes/prep.json の review_md
  - 狭め: 無し

- E24 R3 に対象のリポジトリの REVIEW.md（在ればパス、無ければ無いと書いた文）を渡す。
  - 元: review-loop.py:47-48 `on_init`（repo_review_md）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_r3_names_the_target_repo_review_md、tests/workflows/test_eyes.py::ScriptCase.test_prep_pastes_the_premises_and_names_the_target_review_md
  - 本物の run: eyes/prep.json の repo_review_md（seed に REVIEW.md は無いので「無い」の文）
  - 狭め: 無し

- E25 R1・R3・R4 に人の方針の文書を読ませ、方針とぶつかる物を役が自分で通さない。R4 はぶつかりを policy_conflicts に挙げ、status に数えない。R2 と前提の検算には貼らない。
  - 元: review-loop.json:4672,4973,5036 の prompt_append（policy-paste.md・policy.md）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_policy_section_on_r1_r3_r4、tests/workflows/test_eyes.py::CopiedTextsCase.test_every_command_is_its_original_with_only_ledgered_edits
  - 本物の run: eyes/prep.json の policy_path（seed は空）
  - 狭め: 無し

- E26 どの指示書も言語の 1 行（人が読む欄は始めの記録の lang、key・enum の値は訳さない）で終わり、返りは JSON だけと言う。
  - 元: works/.shared/core/rolekit.py:67 `LANG_RULE`・:147 `lang_line`
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_every_command_binds_the_language_and_returns_json、lib/tests/test_eyeverdict.py::PromptTextsCase.test_lang_line_keeps_keys_untranslated、tests/workflows/test_eyes.py::ScriptCase.test_prep_pastes_the_premises_and_names_the_target_review_md
  - 本物の run: eyes/prep.json の lang_line
  - 狭め: 無し

### 役の返りの型と出し直し

- E27 役の返りの型は元の graph の schema のとおり（R3・R4 には見た範囲と見ていない範囲 seen・unseen を足した）。R1 の削除の where は空文字を許さない。
  - 元: review-loop.json:4574,4672,4887,4973,5036,5189 の各節の schema
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_role_schemas_match_graph
  - 本物の run: eyes/r1.json・r2.json・r3.json・r4.json の欄
  - 狭め: 無し

- E28 R4 の棚卸しが発火したら（fired: true）、消えた能力 lost を必ず明示させる（元の post_check r4_inventory）。
  - 元: review-loop.py:2993-2996 `r4_inventory`
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_r4_inventory_requires_lost
  - 本物の run: eyes/r4.json の capability_inventory.fired・lost
  - 狭め: 無し

- E29 型に外れた返り・JSON でない返りは、拒んだ理由を同じ会話に返して出し直させ、3 回目で諦める。
  - 元: works/blk-eyes/lib/eyes.py:85 `GIVE_UP_AFTER`・:412-485 `_reject`・`accept`、works/blk-eyes/blk-eyes.yaml:92-99（loop_group、fresh_context: false、until_bash）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_retry_gives_three_tries は回数だけ
  - 本物の run: 筋書きでのみ（Archon の node_retry_scheduled の事象。健やかな seed では起きにくい）
  - 狭め: #67 で狭めた（拒んだ理由が役に渡らない）。Archon の retry は同じ run() を呼び直すだけ（packages/workflows/src/dag-executor.ts:1055）で、Claude の構造化出力は reask しない（同 :2341-2348）。ただし元の blk-eyes 自身が同じ Archon の loop_group で同じ会話の出し直しをしていた（works/blk-eyes/blk-eyes.yaml:92-99）ので不可でない → 持ち主の決め（owner-decisions の仮の判断）

- E30 読むだけの役が作業ツリーを変えたら、その返りを受けない。
  - 元: works/blk-eyes/lib/eyes.py:482 `entry.take`（入口の写しと比べて拒み、出し直させる）、works/tests/test_blk_eyes.py:975 `test_tree_change_is_rejected`
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_every_role_node_is_read_only、lib/tests/test_eyeverdict.py::CollectCase.test_missing_eye_file_is_unverifiable_and_named
  - 本物の run: 筋書きでのみ
  - 狭め: #67 で狭めた（出し直しが無くなった）。Archon で不可: packages/workflows/src/dag-executor.ts:1243-1249（checkout の照らしの違反は retry の外で、出し直さない）

### R2（比較役と前提の検算）

- E31 比較役を回すのは、独立設計が在り、問いが立ち（question_stands: true）、目的の文が空でない時だけ。
  - 元: review-loop.py:1228-1235 `r2_compare_due`
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::DueCase.test_compare_is_due_only_when_the_question_stands_and_purpose_is_known
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば eyes/prep.json の compare_due、eyes/r2.json が在ること）
  - 狭め: 無し

- E32 独立設計が「問いは立たない」と言った時は比べず、別の judge が前提を実態で検算する。
  - 元: review-loop.py:1248-1251 `r2_premise_invalid`・:2988-2990 `r2_design`
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::DueCase.test_premise_is_invalid_only_when_the_design_says_no_question、筋書き workflows/eyes/fixtures/premise.stubs.yaml（tests/workflows/test_eyes.py::FixtureCase.test_fixtures_pass_in_archon。Archon の源が無ければ見送る）
  - 本物の run: 筋書きでのみ（seed の依頼は問いが立つ）
  - 狭め: 無し

- E33 前提の検算の役に、独立設計の返答の全体・目的・記録の制約・リポジトリを渡し、仮定を実態で検算させる（偽と示せたら resolved、真か反証できないなら escalate）。この run では R2 を回し直さないと言う。
  - 元: review-loop.json:5189 `stop.premise_check` の reads・does
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_restored_command_sentences_stay、tests/workflows/test_eyes.py::ScriptCase.test_prep_pastes_the_premises_and_names_the_target_review_md
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- E34 前提不成立の道では r2 を unverifiable にし、訳は「前提不成立: 」＋独立設計の premise_invalid_reason（無ければ reason）。検算の結果 {verdict, reason} を返りに載せる。
  - 元: review-loop.py:2988-2990 `r2_design`（reviews.R2 を premise-invalid に）
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::CollectCase.test_premise_path_makes_r2_unverifiable_and_carries_the_check、lib/tests/test_eyeverdict.py::DueCase.test_premise_reason_prefers_the_named_field_then_the_reason
  - 本物の run: 筋書きでのみ（節 eyes__verdict の r2・premise_check）
  - 狭め: 無し（元の語 premise-invalid は訳の頭に移した。約束 docs/design.md:287 のとおり）

- E35 前提の検算の節が落ちた・判定の語が約束の外なら escalate にし、落ちた筋を名指す（R4 を回した後なら「まま R4 を回した」）。
  - 元: works/blk-eyes/lib/eyes.py:291-310 `fallen`・`fell_text`
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::CollectCase.test_fallen_premise_check_escalates
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- E36 前提の検算が escalate なら、他の阻害に依らず人に聞く。
  - 元: review-loop.json:5189 `stop.premise_check` の does（件数に依らず止めて聞く）、works/.shared/core/scripts/review-record.py:183
  - 今: 表
  - 証: tests/workflows/test_line.py::AskFinalCase.test_escalated_premise_check_opens_the_final_gate
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（止める代わりに最後の関所で人が決める）

- E37 検算で仮定が偽（resolved）なら、問いの一文 key を台帳に held で残し、実測 facts_to_add を制約に足して、次で R2 を回し直す。
  - 元: review-loop.py:1310-1331 `premise_question`、:3751-3755 `finalize`（facts_to_add を記録へ）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ScriptCase.test_premise_facts_reach_the_report・tests/workflows/test_eyes.py::ScriptCase.test_carried_constraints_keep_the_eyes・lib/tests/test_judge_accept.py::CarriedConstraintsCase.test_carried_constraints_join_the_premises・tests/workflows/test_line.py::AskFinalReadsCase.test_final_gate_lists_the_r2_premise_inputs
  - 本物の run: 筋書きでのみ（eyes/premise-check.json の facts_to_add）
  - 狭め: #67 で狭めた（「約束を変える頼み 6」が未決）。Archon で不可でない → 戻す 決め: 後半の次の run への運びも部分 D2 で行う（next-request.json の欄 constraints）（線の配線の文書の「この文書の外」の「決めた物」） → 部分 D2 で戻した（次の run への運びも）

- E38 比較役の頭に、独立設計の後に分かった前提を元の並びで貼る（人の関所の答え・依頼が名指した設計書の節・対象のリポジトリの地図・独立設計の後に来た答え・前提のずれの申告・記録の制約）。どれかが設計の前提を崩していれば、比べずに redesign-needed にし「設計の前提が変わった: 」で始めて書かせる。
  - 元: works/blk-eyes/lib/eyes.py:96-101 `PREMISE_HEAD`・`PREMISE_ASK`、:389-409 `premise_section`
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_r2_compare_says_premise_changed、lib/tests/test_eyeverdict.py::PremiseSectionCase.test_pastes_every_premise_in_the_original_order、tests/workflows/test_eyes.py::CopiedTextsCase.test_every_command_is_its_original_with_only_ledgered_edits
  - 本物の run: eyes/prep.json の premises_text、eyes/r2.json の reason
  - 狭め: 無し

- E39 人の答えのうち、独立設計の控えの seen.count より後に来た物だけを「独立設計の後に来た人の答え」に分けて貼り、設計の漏れに数えさせない。人の答えの行は独立設計の控えと同じ形（始めの関所 → 修正前の関所の順）。
  - 元: works/blk-eyes/lib/eyes.py:115-117 `LATE_HEAD`・`LATE_ASK`、:399-405
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::PremiseSectionCase.test_only_answers_after_the_design_are_late、lib/tests/test_eyeverdict.py::PremiseSectionCase.test_human_answer_rows_are_design_human_answers_rows、tests/workflows/test_eyes.py::ScriptCase.test_prep_pastes_the_premises_and_names_the_target_review_md
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば eyes/r2-premises.json の after_design（seed で修正前の関所に答えが無ければ空））
  - 狭め: 無し

- E40 渡せなかった前提は黙らず書く（依頼のファイルが無い・修正の印が無い・申告の文が無い・記録の制約が無い）。依頼が名指したのに引けなかった設計書の節も名指す。
  - 元: works/blk-eyes/lib/eyes.py:389-409、works/.shared/core/design.py の premises（依頼の節が引けない時）
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::PremiseSectionCase.test_says_what_was_not_passed、lib/tests/test_eyeverdict.py::PromptTextsCase.test_constraints_text_says_when_not_passed、tests/workflows/test_eyes.py::ScriptCase.test_prep_pastes_the_premises_and_names_the_target_review_md（「依頼が名指したが引けなかった」）
  - 本物の run: eyes/prep.json の premises_text、eyes/r2-premises.json の withheld
  - 狭め: 無し

- E41 依頼の文の Markdown の名指し（リンクの節のアンカー・コードの囲いの外だけ）を元の読みで引く。
  - 元: review-loop.py:2822-2850 `MD_LINK`・`_md_lines`・`_md_slugs`、works/tests/test_blk_eyes.py:736 `test_md_named_section_skips_fence_with_info_string`
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::PremiseSectionCase.test_link_anchor_finds_the_heading_by_its_slug と lib/tests/test_eyeverdict.py::PremiseSectionCase.test_heading_inside_a_code_fence_is_not_an_anchor（名指された文書の囲い（情報文字列つきを含む）の中の # 行はアンカーにならず、節も切らない）。#123 で名を test_link_inside_a_code_fence_is_not_named から替えた（元も依頼の文の囲いの中のリンクは名指しに数える）
  - 本物の run: eyes/r2-premises.json の given の named_section（seed の依頼は設計書を名指さない）
  - 狭め: 無し

- E42 前提のずれの申告の本文（premise_drift_note）を比較役の頭に貼る。
  - 元: review-loop.py:1848（loop.drift_notes）、works/blk-eyes/lib/eyes.py:395
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::PremiseSectionCase.test_pastes_every_premise_in_the_original_order（「入口は 2 つあった」）、tests/workflows/test_eyes.py::ScriptCase.test_prep_pastes_the_premises_and_names_the_target_review_md。fix の返りの changed の premise_drift_note: tests/workflows/test_fix.py::BlockScriptsCase.test_changed_carries_the_premise_drift_note_and_the_x_scalars・tests/workflows/test_fix.py::ContractCase.test_nested_shapes・lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_reply_marks_or_over_the_previous（部分 D1）。部分 0 の時の証（そのまま残す）: lib/tests/test_eyeverdict.py::PremiseSectionCase.test_pastes_every_premise_in_the_original_order（「入口は 2 つあった」）、tests/workflows/test_eyes.py::ScriptCase.test_prep_pastes_the_premises_and_names_the_target_review_md。fix の返りの型は要追加: tests/workflows/test_fix.py::…test_changed_carries_the_premise_drift_note — fix の返りの changed に premise_drift_note が在る
  - 本物の run: eyes の比較役の頭（部分 D1 で fix の返りの changed に premise_drift_note を足した）
  - 狭め: #67 の「約束を変える頼み 2」が fix で未決。Archon で不可でない → 戻す → 部分 D1 で戻した

- E43 記録の制約（判定の隣の premises.json の constraints）を、比較役の頭と前提の検算に同じ字で渡す。
  - 元: works/blk-eyes/lib/eyes.py:396-397（record.process.constraints）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ScriptCase.test_prep_reads_constraints_next_to_the_judgment、lib/tests/test_eyeverdict.py::PremiseSectionCase.test_constraints_read_the_same_in_the_compare_head_and_the_premise_check
  - 本物の run: eyes/prep.json の constraints_text（judge/premises.json から。再審の run は rejudge/premises.json から）
  - 狭め: 無し

- E44 比較役に貼った前提の控え（given・withheld・seen・after_design）を eyes/r2-premises.json に残す。
  - 元: works/blk-eyes/lib/eyes.py:136 `PREMISES_NAME`・:430-431
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::PremiseSectionCase.test_ledger_lists_what_was_given_and_withheld、tests/workflows/test_eyes.py::ScriptCase.test_prep_pastes_the_premises_and_names_the_target_review_md
  - 本物の run: eyes/r2-premises.json
  - 狭め: 無し

- E45 比較役が「渡されていない」と書いた文と、そのうち実は渡していた物（claims_given）と、R2 の 2 つの役に渡した前提の控えを、最後の関所の R2 の行の下に並べる。
  - 元: works/blk-eyes/lib/eyes.py:527-533（出口の premise_inputs）、works/darkfactory/lib/line_edge.py:529-557 `_r2_inputs`
  - 今: 表
  - 証: tests/workflows/test_line.py::AskFinalReadsCase.test_final_gate_lists_the_r2_premise_inputs・lib/tests/test_runreport.py::FixBesideLinesCase.test_eyes_gate_passes_are_listed。部分 0 の時の証（そのまま残す）: lib/tests/test_eyeverdict.py::WriteNotesCase.test_writes_premise_inputs_and_gate_passes、tests/workflows/test_eyes.py::ScriptCase.test_verdict_writes_the_notes_for_the_final_gate、lib/tests/test_blk_eyes.py::PathCase。関所に出ることは
  - 本物の run: eyes/premise-inputs.json は書かれるが、最後の関所の文（gate-final の message）には出ない
  - 狭め: #67 は読み手を線と report に頼んだ（「約束を変える頼み 4」）が、#74 でも未だ。Archon で不可でない → 戻す → 部分 D2 で戻した

### 支度の文

- E46 目の指示書に、単位の目録・この run の修正の結末・波及と定石の置き場・修正の印（R4 の r4_context）を渡す。
  - 元: review-loop.json:4672 `r1.minimality` の reads（record.units・record.process.fixes）、:5036 `r4.hidden_scope`
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::PromptTextsCase.test_units_fixes_and_context_are_listed
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば eyes/prep.json の units_text・fixes_text・r4_context）
  - 狭め: 無し

- E47 最後のテストが認証されていない時だけ、目の指示書に「赤は最後の関所で人が見る」の 1 行を足す。
  - 元: なし（今で足した物。元は目を回す前に緑を待った）
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::PromptTextsCase.test_green_line_only_when_not_certified
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば eyes/prep.json の green_line（seed は緑なので空））
  - 狭め: 無し

- E48 全部の単位が軽量の run は目を起こさず、r1〜r4 は null。ok は守りのパスを確かめられた時だけ true。
  - 元: works/blk-eyes/blk-eyes.yaml:22-24 `skip_optional`、works/darkfactory/darkfactory.yaml:1201、works/.shared/core/scripts/review-record.py:179（skipped は理由つき）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ScriptCase.test_prep_all_light_turns_eyes_off、lib/tests/test_eyeverdict.py::CollectCase.test_light_run_has_null_eyes_and_is_ok、lib/tests/test_eyeverdict.py::CollectCase.test_light_run_with_an_unconfirmed_protected_check_is_not_ok、筋書き all-light
  - 本物の run: 筋書きでのみ（seed は標準の厚さ）
  - 狭め: 省いた理由（元の reviews の skipped の reason）は eyes の返りに無い（約束 docs/design.md:287「省いた目は null」）。理由が報告に出るか（redepth の返りから）を要確かめ。Archon で不可でない

### 出口（返す節）

- E49 出口の ok は、省いていない目が全部 pass で、前提の検算の道でなく、守りのパスを確かめられた時だけ true。どれか 1 つでも redesign-needed・unverifiable なら false。
  - 元: works/blk-eyes/lib/eyes.py:489-535 `collect`、review-record.py:167-180（blocks）
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::CollectCase.test_all_pass_is_ok、lib/tests/test_eyeverdict.py::CollectCase.test_any_redesign_eye_is_not_ok、lib/tests/test_eyeverdict.py::CollectCase.test_r2_redesign_is_not_ok、筋書き pass・redesign
  - 本物の run: 節 eyes__verdict の ok（線の eyes-out の got.ok。最後の関所の「独立の目が阻害を返した」）
  - 狭め: 無し

- E50 返りが無い・読めない・JSON の object でない目は unverifiable にし、落ちた筋と状態を名指す（R4 の後なら「まま R4 を回した」）。
  - 元: works/blk-eyes/lib/eyes.py:291-310 `fallen`・`fell_text`、:516-519
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::CollectCase.test_missing_eye_file_is_unverifiable_and_named、lib/tests/test_eyeverdict.py::CollectCase.test_unreadable_eye_file_is_unverifiable、lib/tests/test_eyeverdict.py::FellTextCase、tests/workflows/test_eyes.py::ScriptCase.test_verdict_names_fallen_eye
  - 本物の run: 筋書きでのみ（落ちた目が在る run の eyes__verdict の rN.reason）
  - 狭め: 無し

- E51 判定の語が約束の外の返りは「返りの判定の語が約束の外」と名指して unverifiable にする。
  - 元: works/.shared/core/scripts/review-record.py:443-454（status が不正なら落とす）
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::CollectCase.test_off_contract_status_is_named
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- E52 独立設計が無い・読めない・object でない時、r2 は unverifiable で「独立設計が取れなかった: <訳>」。
  - 元: works/blk-eyes/lib/eyes.py:513-515（盤面を止めて『独立の目 R2: 独立設計が取れなかった…』）
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::CollectCase.test_missing_design_makes_r2_unverifiable、lib/tests/test_eyeverdict.py::DesignReadCase.test_missing_or_unreadable_design_names_why
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（元は run を止め、今は ok: false で最後の関所が人に聞く。止めるかは線の決め）

- E53 R2 を比べなかった時（目的の文が空・問いが立つかの欄が無いか真偽でない）は、どちらの訳かを分けて unverifiable にする。
  - 元: review-loop.py:1228-1235（比べない訳を条件の文で返す）
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::CollectCase.test_r2_not_compared_names_which_input_was_missing
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（約束 docs/design.md:287 に無い場合を足した。#67 の「約束を変える頼み 5」）

- E54 返す節は落ちない。入力が壊れていても、lib を読めなくても、置き場が無くても、NaN が混じっても約束の形で ok: false を返す。
  - 元: works/blk-eyes/lib/eyes.py:539-542（配線の誤りは終了コード 2）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ScriptCase.test_verdict_never_fails、tests/workflows/test_eyes.py::ScriptCase.test_verdict_never_fails_when_lib_cannot_be_read、tests/workflows/test_eyes.py::ScriptCase.test_verdict_returns_strict_json、lib/tests/test_eyeverdict.py::CollectCase.test_unverified_fills_the_contract_shape
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- E55 支度の節が落ちた時は r1〜r4 を「支度の節…が落ちた」で unverifiable にし、守りのパスの確かめはそのまま運ぶ（確かめた空は空のまま）。
  - 元: なし（今の形で足した物）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ScriptCase.test_verdict_without_prep_keeps_a_clean_protected_check_empty、lib/tests/test_eyeverdict.py::CollectCase.test_unverified_keeps_a_clean_protected_check_empty、lib/tests/test_eyeverdict.py::CollectCase.test_unverified_fallen_or_malformed_protected_is_a_hit
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- E56 目が落ちても柵（eyes-complete、all_done）で待ち合わせてから、返す節がファイルを読んでまとめる（落ちた節への with: を持たない）。
  - 元: works/blk-eyes/blk-eyes.yaml:991-997 `eyes-collect`（all_done）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_barrier_before_verdict
  - 本物の run: 節 eyes__eyes-complete の後に eyes__verdict
  - 狭め: 無し

- E57 目ごとに型つきの成果物 eye-verdict {eye, status, reason} を出し、返りの全体を eyes/<目>.json に書く。目の名と判定の語は YAML と lib で同じ。
  - 元: なし（今で足した物）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_eye_verdict_typed、tests/workflows/test_eyes.py::ScriptCase.test_eye_verdict_writes_file_and_returns_row、tests/workflows/test_eyes.py::ShapeCase.test_eye_names_and_status_words_match_eyeverdict
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば Archon の型つきの成果物 eye-verdict、eyes/r1.json〜r4.json）
  - 狭め: 無し

- E58 ブロックの返りは ok・r1〜r4・questions・premise_check・structure_after・protected_hits の固定の並び。
  - 元: works/blk-eyes/lib/eyes.py:152-155 `EXIT_FIELDS`（ok・reason・reviews・premise_inputs）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_returns_contract
  - 本物の run: 節 eyes__verdict の返り（線の eyes-out の got）
  - 狭め: 無し（premise_inputs はファイルに移した。読み手の穴は E45）

### 守りのパス

- E59 始めの版から今の作業ツリーまで（未追跡を含む）の差分が守りの一覧に当たれば、当たったパスと行を返す。
  - 元: works/darkfactory/lib/line_edge.py:640-651 `_protected`（protect.touched）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ScriptCase.test_protected_names_touched_guarded_paths、筋書き protected-hit
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば eyes/protected.json の hits（seed の直しは stats.py だけなので []）。最後の関所が使うのは merge-seal の protected_hits（workflows/line/works-factory-line.yaml:799））
  - 狭め: 無し（承認したテストの変更の許しの範囲の当て（元 conflict.ruled_test_doc）は M の範囲）

- E60 一覧・git・始めの記録が読めない時、守りの節が落ちた時、返りの形が崩れた時は、黙って空にせず「確かめられなかった」の行（seal.unknown_row）を当たりにし、ok を false にする。
  - 元: works/darkfactory/lib/line_edge.py:651-652（fail closed）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ScriptCase.test_protected_broken_is_a_hit、lib/tests/test_eyeverdict.py::CollectCase.test_unverified_protected_is_a_hit_and_not_ok、lib/tests/test_eyeverdict.py::CollectCase.test_fallen_protected_node_is_a_hit
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- E61 守りのパスに当たっても目の ok は落とさない（当たりは返りで運び、関所が人に聞く）。
  - 元: works/darkfactory/lib/line_edge.py:786-794（関所で人に聞く）
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::CollectCase.test_protected_hits_are_carried_without_failing_the_eyes、tests/workflows/test_eyes.py::ScriptCase.test_verdict_carries_protected_hits
  - 本物の run: 節 eyes__verdict の protected_hits
  - 狭め: 無し

### R4 の問いと人の通し

- E62 R4 が見た消えた能力（lost）と方針とのぶつかり（policy_conflicts）を、頭（「R4 が BASE から消えたと見た能力: 」「R4 が見た人の方針とのぶつかり: 」）を付けた人への問いにする。
  - 元: review-loop.py:4103-4110 `R4_ROWS`・`_r4_gate_items`、:4116-4131 `human_gate`
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::R4GateCase.test_rows_carry_the_r4_heads、lib/tests/test_eyeverdict.py::R4GateCase.test_no_r4_asks_nothing
  - 本物の run: 節 eyes__verdict の questions（seed で lost が無ければ空）、最後の関所の文の「- 問い: 」（workflows/line/scripts/ask_final.py:108）
  - 狭め: 無し（元は周の途中で止めて聞き、今は最後の関所で聞く）

- E63 修正前の関所で人が通した（approve・continue）狭まりと事前審査の穴と、種類も本文も同じ R4 の行は聞き直さない。stop・reject・答え無しは何も通さず、種類が違えば聞き直す。
  - 元: review-loop.py:4107、works/.shared/core/gatemarks.py:1244-1281
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::R4GateCase.test_r4_does_not_reask_narrow_the_human_passed、lib/tests/test_eyeverdict.py::R4GateCase.test_r4_reasks_other_kind_or_unpassed、lib/tests/test_eyeverdict.py::HumanPassedCase、lib/tests/test_eyeverdict.py::CollectCase.test_questions_drop_the_rows_the_human_passed、tests/workflows/test_eyes.py::ScriptCase.test_verdict_drops_passed_questions
  - 本物の run: 筋書きでのみ（seed では修正前の関所に通す行が出にくい）
  - 狭め: 無し

- E64 関所の項目の推しの尾（「／推し…」）を外した本文で照らし、R4 が尾の無い本文を写しても聞き直さない。
  - 元: works/.shared/core/gatemarks.py:1244（PUSH_TAIL）、works/tests/test_gate_drafts.py `R4PushTailCase`
  - 今: 表
  - 証: lib/tests/test_eyeverdict.py::R4PushTailCase.test_r4_does_not_reask_when_the_asked_row_had_a_push_tail
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- E65 R4 の頭に人が通した行を貼り、同じ物を見たらその本文をそのまま写させる。
  - 元: works/blk-eyes/lib/eyes.py:435-436（gatemarks.carried_section）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ScriptCase.test_prep_pastes_passed_rows_at_the_r4_head、lib/tests/test_eyeverdict.py::R4GateCase.test_carried_section_lists_passed_rows_under_the_gatemarks_head
  - 本物の run: eyes/prep.json の carried
  - 狭め: 無し

- E66 人が通したので R4 の問いから外した行を、通した印つきで残し、最後の関所と報告が「人が通した行」として並べる。
  - 元: works/.shared/core/gatemarks.py:1276-1281、works/darkfactory/lib/line_edge.py:604-607（_final_text の gatemarks.lines）
  - 今: 表
  - 証: lib/tests/test_runreport.py::FixBesideLinesCase.test_eyes_gate_passes_are_listed・tests/workflows/test_line.py::AskFinalReadsCase.test_final_gate_lists_the_r2_premise_inputs。部分 0 の時の証（そのまま残す）: lib/tests/test_eyeverdict.py::WriteNotesCase.test_writes_premise_inputs_and_gate_passes、tests/workflows/test_eyes.py::ScriptCase.test_verdict_writes_the_notes_for_the_final_gate。読み手は
  - 本物の run: eyes/gate-passes.json は書かれるが、報告と最後の関所には出ない
  - 狭め: #67 の「約束を変える頼み 4」が #74・report で未決。Archon で不可でない → 戻す → 部分 D2 で戻した

- E67 修正の後の関所で、方針の文書が始めに固定した版（sha256 と写し）から変わっていれば人に聞き、通したらその版で固定し直す。
  - 元: review-loop.py:66 `on_init`（方針の版の固定）、:4116-4123 `human_gate`（policy_changed）、:4134-4143 `human_gate_answered`
  - 今: 無し（表）
  - 証: 要追加: tests/workflows/test_line.py::…test_policy_doc_change_after_fix_is_asked — 始めの記録の方針の版と今の文書が違えば、最後の関所を開ける理由に入る
  - 本物の run: 筋書きでのみ
  - 狭め: どの PR で落ちたかは PR 本文に無い（#67 は触れていない）。Archon で不可でない → 戻す（住処は線か始めの記録で、E の外かもしれない）

### 直した後の構造の実測（元の段 B）

- E68 直した後の構造を、始めの版から今の作業ツリーまでの差分で測る（変わったファイル・柵の表で住処の外の知る場所の増え・新しい名・増えた写しの塊・直しが変えた表）。柵は直しの前の版の表で数え、表の無い対象は数えず作らない。run の作業ツリーの実行基盤の写し（.archon/）は数えない。UTF-8 でないファイルも落とさない。
  - 元: works/blk-structure/scripts/stage_b.py:100 `run`、works/darkfactory/lib/line_edge.py:456-480 `after_edge`
  - 今: 表
  - 証: lib/tests/test_stage_b.py::AfterCase の 6 本: lib/tests/test_stage_b.py::AfterCase.test_after_stage_counts_real_diff・lib/tests/test_stage_b.py::AfterCase.test_no_table_reports_only・lib/tests/test_stage_b.py::AfterCase.test_non_utf8_diff_is_measured・lib/tests/test_stage_b.py::AfterCase.test_runtime_copy_is_not_measured・lib/tests/test_stage_b.py::AfterCase.test_table_widened_by_fix_still_counts・lib/tests/test_stage_b.py::AfterCase.test_unknown_base_does_not_stop_the_line（元 works/tests/test_blk_structure.py と同じ照らし）
  - 本物の run: eyes/structure-after.json の after.changed（seed では ["stats.py"]）・tables（[]）・fence_up（[]）・new_names・dup_blocks_added
  - 狭め: 無し（試験だけが欠けた）

- E69 実測が落ちても線を止めない（status: failed と理由を返す）。
  - 元: works/blk-structure/scripts/stage_b.py:92-120（failed と reason）、works/darkfactory/lib/line_edge.py:456-459
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ScriptCase.test_structure_after_never_fails_the_line
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 節 eyes__structure-after の status・reason、eyes/structure-after.json）
  - 狭め: 無し

- E70 実測の控えに、修正案の外れの訳（構造の目の避け方と処方から外れた訳）を並べる。
  - 元: works/darkfactory/lib/line_edge.py:456-479 `after_edge`（deviations）、works/.shared/core/structmark.py:172,184
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ScriptCase.test_structure_after_carries_plan_deviations
  - 本物の run: eyes/structure-after.json の deviations
  - 狭め: 無し

- E71 全部の単位が軽量の run でも、直した後の実測と守りのパスの照らしは省かない。
  - 元: works/tests/test_structure_eye.py:295-312 `AfterWiringCase.test_light_run_still_measures`
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ShapeCase.test_structure_after_runs_in_a_light_run
  - 本物の run: eyes/structure-after.json が軽い run でも在る（seed は標準なので筋書きでのみ）
  - 狭め: 無し

- E72 返す節は直した後の実測の控えを指し札で返し、控えが無ければ null。
  - 元: works/blk-structure/blk-structure.yaml:73-81（after_file の指し札）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ScriptCase.test_verdict_points_at_the_structure_measured_after_the_fix
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 節 eyes__verdict の structure_after（eyes/structure-after.json））
  - 狭め: 無し

- E73 実測の数の 1 文と、増えた所・新しい名・外れの訳を最後の関所と報告に並べる。柵の増えは関所を開ける理由にし、結末を fixed にしない残りに数える。
  - 元: works/darkfactory/lib/line_edge.py:603（_final_text の structmark.after_lines）、:820（after_rows）
  - 今: 表
  - 証: tests/workflows/test_line.py::AskFinalReadsCase.test_final_gate_shows_the_after_counts・tests/workflows/test_line.py::AskFinalReadsCase.test_final_text_lists_new_names_and_deviations・lib/tests/test_runreport.py::LinesCase.test_structure_rows_and_after
  - 本物の run: 報告の構造の節に「直しの後の実測」、最後の関所の文には柵の増えだけ
  - 狭め: #74 で最後の関所の文が after_lines の数・新しい名・外れの訳を落とした。Archon で不可でない → 戻す → 部分 B2 で戻っていた。部分 D2 で縛った

- E74 実測にかかった時間（timing の wall_s）を控えに残す。
  - 元: works/blk-structure/scripts/stage_b.py:150（eye.stamp）
  - 今: 表
  - 証: tests/workflows/test_eyes.py::ScriptCase.test_structure_after_stamps_wall_time
  - 本物の run: eyes/structure-after.json の after.timing.wall_s
  - 狭め: #67 で黙って落ちた（小）→ #123 で戻した

### 構造の目の行の形（design-row。直す前の構造の目。P の範囲と重なる）

- E75 構造の目の返答は単位と 1 対 1、verdict は汚れる・汚れない、faces は形の番号 1〜6、evidence は見せた JSON の中の在る欄を指し、汚れる行は避け方 chosen と訳 chosen_reason が要る。
  - 元: works/blk-structure/lib/eye.py（problems）、works/tests/test_structure_eye.py:64-84
  - 今: 表
  - 証: lib/tests/test_structure_eye.py::EyeAcceptCase.test_good_rows_pass、lib/tests/test_structure_eye.py::EyeAcceptCase.test_bad_rows_are_named、lib/tests/test_structure_eye.py::EyeAcceptCase.test_evidence_indexes_the_units_the_prompt_showed
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば plan の置き場の design.jsonl（構造の目は直す前に走る））
  - 狭め: 無し

- E76 人に上げる行は決まらない訳 undecided_because（20 字以上）と捨てた案 rejected が要り、受け付けた行は design-row.schema.json の形で route_reason をつけて書く。3 回目の拒否で諦め、行を書かない。
  - 元: works/blk-structure/lib/eye.py（accept）、works/blk-structure/design-row.schema.json
  - 今: 表
  - 証: lib/tests/test_structure_eye.py::EyeAcceptCase.test_route_up_needs_reason、lib/tests/test_structure_eye.py::EyeAcceptCase.test_route_up_row_written、lib/tests/test_structure_eye.py::EyeAcceptCase.test_third_rejection_gives_up
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば plan の置き場の design.jsonl・eye.json）
  - 狭め: 無し

- E77 構造の目に見せる写しの塊の一致は先頭 5 件に切り、全件の数を duplicates_total に置く（支度の出力が実行基盤の上限を越えないように）。
  - 元: works/blk-structure/lib/eye.py（_cut）、works/tests/test_structure_eye.py:135
  - 今: 表
  - 証: lib/tests/test_structure_eye.py::EyeAcceptCase.test_long_duplicates_are_cut_with_the_total
  - 本物の run: 筋書きでのみ（seed の stats.py は小さい）
  - 狭め: 無し

### E の穴（穴の要約）

数:

- 行の総数: 77（E1〜E77）
- 今: 無し: 2（E16・E67）。E16 はコードとコメントの比、E67 は方針の文書の変化を聞く仕組み。E74（実測の時間）は #123 で戻した
- 今は在ったが本物の run に届かなかった（配線か読み手が無かった）6 行（E17 x_scalars、E37 前提の検算の key と facts_to_add、E42 前提のずれの申告の本文、E45 R2 の前提の材料、E66 人が通した R4 の行、E73 最後の関所の実測の数の行）は、線の配線の部分 B2・D1・D2 で届くようにし、受け手の試験を足した
- 証が要追加か弱い: 1（E67）。要追加だった E16 は戻さないと決めて要らなくなり（#118）、E37 は線の配線の部分 D2 で試験を足し、残りの要追加 12 行と弱い 10 行は下の #123 で閉じた
- 狭めたのに Archon が強いていない: 5（E16・E19・E29・E48・E67）。うち持ち主の決めが要る物 4（E16・E19・E29・E48。E16 は戻さないと決めた）。E17・E37・E42・E45・E66・E73 は線の配線の部分 B2・D1・D2 で、E74 は #123 で戻した
- Archon に強いられた狭め: 1（E30。packages/workflows/src/dag-executor.ts:1243-1249）
- #123 で閉じた: 22（E2・E3・E7・E9・E12・E13・E14・E20・E21・E23・E25・E28・E36・E38・E41・E43・E51・E65・E68・E70・E71・E74。E74 は戻し、ほかは外すと赤になる試験を足した。指示書の字は写しの台帳 tests/workflows/test_eyes.py::CopiedTextsCase が縛る）。E16 は戻さない（持ち主の決め `no-comment-ratio`。#118）

持ち主に聞くこと:

1. E16 コードとコメントの比を戻すか（#67 は言語依存を理由に外した）。→ 決めた: 戻さない（`no-comment-ratio`。#118）
2. E29 型に外れた返りを、拒んだ理由つきで同じ会話に出し直させる元の形を戻すか（元の blk-eyes は同じ Archon の loop_group でやっていたので Archon の制約ではない。owner-decisions の仮の判断のまま行くか）。
3. E19 規模の数値の推移（前の周の値と行数の伸び）を run をまたいで運ぶか（1 run 1 周で値が無い）。
4. E48 軽い run で省いた目の理由を、eyes の返りか報告のどちらかに残すか（今は null だけ）。
5. E67 方針の文書の変化を修正の後に聞く仕組みの住処（線・始めの記録・eyes のどこに置くか）。

線・fix・report の側で直す物（eyes のブロックは約束どおりだが本物の run に届かなかった）: E17（fix の返りと線の with に x_scalars）、E42（fix の返りの changed に premise_drift_note）、E37（premise_check に key と facts_to_add を運ぶ形）、E45・E66（eyes/premise-inputs.json・eyes/gate-passes.json の読み手を最後の関所と報告に）、E73（最後の関所に after_lines）。どれも #67 の「約束を変える頼み」1・2・4・6 で頼み、線の配線の部分 B2・D1・D2 で直した。壊れる余地だけ在った E43（再審の後の judgment の隣に premises.json が無い道）は #123 で閉じた。

## R（報告のブロック report）の能力の棚卸し

この文書の語（棚卸しの決まり.md の語と同じ）:

- 元: 前の修正工場 works（raiki61/claude-plugins の commit `2aa7c66c` の `works/`）。パスは `works/...`
- 今: 印（「表」か「無し（表）」、住処を書かなかった行は「無し」か空）だけを持ち、住処の字は docs/works-parity.md の「前の棚卸しの今」が持つ
- 線: 8 つのブロックを並べる工程 works-factory-line。まだ main に無く、PR #74 の先頭の写し（#74 の head）を読む
- 関所: 人が答える節（Archon の approval）。答えの語は通す approve・continue と止める stop・reject
- 本物の run: 種の対象（tests/e2e/target-seed/。stats.py に欠陥 2 つ）を標準の厚さで回し、最後の関所は開いて通す run。報告の置き場は `$ARTIFACTS_DIR/report/`（`workflows/report/scripts/facts.py` の `OUT = "report"`）、返す節は `report__report`
- #68: 報告のブロックを入れた PR（本文と、持ち主側の独立の目の指摘のコメント 3 つ）。#100: 書き手の輪の拒否の訳を script の節で渡す直しの PR
- U6・U8: docs/design.md の「未決」の節の問い（U6 は前の包みが取っていた読んだ証拠と書き込みの記録をどこで取るか。段 1b で決めた。U8 は分かった）
- 「約束の隣のファイル」: docs/design.md:162 が名指す、返りの指し札の先と同じフォルダに置き、ほかのブロックも開いてよいファイル

種の run では結末は `fixed` か、判定の素材が not_run なら `fixed_needs_check` になる見込み。止め・落ち・申し出・再審は起きないので、その行は「筋書きでのみ」。

### 結末の 10 語と決め方

- R1 結末の語は元の 10 語（字も並びも同じ）で、どの語にも平易な言い方がある
  - 元: works/.shared/core/report.py:109 `OUTCOMES`・:861 `OUTCOME_WORDS`
  - 今: 表
  - 証: lib/tests/test_outcome.py::WordsCase.test_outcomes_are_the_original_ten_words・lib/tests/test_outcome.py::WordsCase.test_every_outcome_has_plain_words・tests/workflows/test_report.py::ShapeCase.test_return_fields_are_the_contract
  - 本物の run: 節 `report__report` の出力 `outcome`、report/report.md の「## 3. 止めたか」の「結末: …（<語>）」
  - 狭め: 無し

- R2 stopped_by_request: 関所の止める語（stop・reject）で文が `request:` で始まるか、返りの `stop_reason` が `request:` で始まる
  - 元: works/.shared/core/report.py:636 `stop_outcome`（盤面 state.stop.by が request:）・:648 `stopped_run`
  - 今: 表
  - 証: lib/tests/test_outcome.py::TableCase.test_1_request_stop_and_human_stop・tests/workflows/test_report.py::FactsCase.test_request_stop_with_dry_run_environment
  - 本物の run: 筋書きでのみ（種の run は関所を通す）
  - 狭め: 関所の間で走っている run を報告つきで止める止め札（元 works/.shared/core/halt.py と stop.sh。報告の「止め札で止めた（置いた人）…止めた境の節」の行。元 works/.shared/core/report.py:1365-1368）は今に無い。docs/design.md:428 が「Archon に口が無く持ち主の答えを待つ」と書くが、Archon の源の行で不可を示していない → 持ち主の確かめ待ち（R46 と同じ扱い） 決め: 止め札は持ち込まない（stop-at-gates）（線の配線の文書の「この文書の外」の「決めた物」）

- R3 stopped_by_human: 関所の止める語（文が request: でない）か、返りの stop_reason が `human:` で始まる
  - 元: works/.shared/core/report.py:636 `stop_outcome`（halted.by answer か by human:）
  - 今: 表
  - 証: lib/tests/test_outcome.py::TableCase.test_1_request_stop_and_human_stop
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- R4 stopped_by_line: 線の止めの語（人待ちの conflict・replan・tdd-repeat を除く）・事前審査の stalled・計画の ready: false（直す単位が在り、直す義務 0 件で役を起こさなかった周でない時）・merge-seal / merge-apply の ok: false
  - 元: works/.shared/core/report.py:644 `stopby.is_line(by)`（盤面の by が works:）
  - 今: 表
  - 証: lib/tests/test_outcome.py::TableCase.test_2_line_stops・lib/tests/test_outcome.py::ReadingCase.test_plan_not_ready
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（ただし線の script が返す止めの語は報告に届かない。R5b）

- R5 needs_human: 人に回した申し出（途中で落ちていない run では案の直しを待つ行も諦めた行として）・返りの人待ちの語・前提の検算の escalate・関所が開かなかった事前審査の ask_human
  - 元: works/.shared/core/report.py:689 `pending_human or _asked(b)`、:2025 `replan.close_at`
  - 今: 表
  - 証: lib/tests/test_outcome.py::TableCase.test_3_needs_human・lib/tests/test_outcome.py::ReadingCase.test_conflicts_single_list_and_none・lib/tests/test_outcome.py::ReadingCase.test_waiting_replan_is_closed_unless_interrupted
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- R5b 線の節が返す止めの語（works:line-script・works:needs-human・redepth の止め）を結末に入れる
  - 元: works/.shared/core/report.py:328 `_stop_info`（線の境の節は盤面の state.stop に書き、どの節の止めも結末が読んだ）
  - 今: 表
  - 証: tests/workflows/test_line.py::CollectAndResultCase.test_line_stop_reasons_reach_report・lib/tests/test_outcome.py::LineStopCase.test_line_stop_words_reach_the_outcome・tests/workflows/test_report.py::FactsCase.test_line_values_reach_the_outcome_and_the_report・tests/e2e/test_line_scenarios.py::ReportOutcomeTest.test_real_report_names_the_outcome
  - 本物の run: 筋書きでのみ
  - 狭め: #74（線）と #68 の境で落ちた。Archon で不可でない（線の with: で集めれば足りる）→ 戻す → 部分 C で戻した

- R6 record_invalid: 始めの記録が読めない・結果を名乗れない訳（入力が JSON でない・申し出と裁定が読めない・知らない答えの語・開けないと名乗れない指し札が開けない）が在る
  - 元: works/.shared/core/report.py:376 `gate_record`・:691（検証器の accepted と round_closed）
  - 今: 表
  - 証: lib/tests/test_outcome.py::TableCase.test_4_record_invalid・lib/tests/test_outcome.py::OrderCase.test_unknown_answer_word_is_a_record_problem・lib/tests/test_outcome.py::ReadingCase.test_unreadable_conflicts_are_record_problems・tests/workflows/test_report.py::FactsCase.test_unreadable_or_missing_conflicts_are_record_invalid
  - 本物の run: 筋書きでのみ
  - 狭め: 検証器（盤面の記録）は設計で無い（docs/design.md のブロックの返りの約束）。その代わりの判定。元の「検証器の出力の末尾と痕跡」の行は検証器が無いので対象が無い

- R7 interrupted: run の記録で最後が node_error でその後ほかの節が始まっていない節か、返りの続きの切れ目（判定が無い・判定 ready で計画無し・計画 ready で修正無し・修正が在って最後のテスト無し・最後のテスト ok で封じ無し）
  - 元: works/darkfactory/scripts/report.py:79-84 `unreached`・:111-121、works/.shared/core/report.py:2033
  - 今: 表
  - 証: lib/tests/test_outcome.py::TableCase.test_5_interrupted・lib/tests/test_outcome.py::TableCase.test_nothing_fixed_is_not_fixed・lib/tests/test_outcome.py::TableCase.test_fix_without_final_test_or_seal_is_not_fixed
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（元に無い行を足した上位）

- R8 no_fix_needed: 判定（再審が在ればそちら）が ready でなく止めの語も無いか、直す単位が 0
  - 元: works/.shared/core/report.py:406 `_no_fix`
  - 今: 表
  - 証: lib/tests/test_outcome.py::TableCase.test_6_no_fix_needed・lib/tests/test_outcome.py::ReadingCase.test_later_judge_and_plan_are_read_first
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- R9 fixed_needs_check: 残りが測れていない素材の行だけで、最後のテストの ok・green と封じの ok が真
  - 元: works/.shared/core/report.py:696-697
  - 今: 表
  - 証: lib/tests/test_outcome.py::ReadingCase.test_unmeasured_materials_only_is_fixed_needs_check・lib/tests/test_runreport.py::DecisionsCase.test_checks_left_are_counted_as_decision
  - 本物の run: 判定の素材が not_run なら `report__report.output.outcome == "fixed_needs_check"`、report/report.md の冒頭 2 行目「人が確かめる物 N 件」
  - 狭め: 無し

- R10 round_limit: 残りが在るか、直したと名乗れる証（最後のテストの ok・green と封じの ok）が無い
  - 元: works/.shared/core/report.py:698
  - 今: 表
  - 証: lib/tests/test_outcome.py::TableCase.test_7_residue・lib/tests/test_outcome.py::TableCase.test_seal_without_ok_is_left
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- R11 fixed: 上のどれにも当たらず、証が揃い残りが 0。返す節の ok は fixed・fixed_needs_check・no_fix_needed の時だけ true
  - 元: works/.shared/core/report.py:700
  - 今: 表
  - 証: lib/tests/test_outcome.py::TableCase.test_8_fixed・lib/tests/test_outcome.py::ReadingCase.test_ok_outcomes・tests/workflows/test_report.py::CollectScriptCase.test_ok_is_passed_through_from_facts
  - 本物の run: `report__report.output.outcome == "fixed"`・`ok == true`、線の返す節 `result.output.fixed == true`
  - 狭め: 無し

- R12 決め方の順（止め札 → 人の止め → 線の止め → 人待ち → 結果を名乗れない → 途中で終わった → 直す物無し → 残り）
  - 元: works/.shared/core/report.py:670-700（needs_human を record_invalid の前に置く訳は :682-686）
  - 今: 表
  - 証: lib/tests/test_outcome.py::OrderCase.test_request_before_line_stop・lib/tests/test_outcome.py::OrderCase.test_human_stop_before_interrupted・lib/tests/test_outcome.py::OrderCase.test_record_invalid_before_interrupted・lib/tests/test_outcome.py::OrderCase.test_needs_human_before_record_invalid（人に回した申し出と start_ok: false を同時に渡して needs_human。decide_outcome の人待ちと記録の誤りの段を入れ替えると赤）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

### 残り（fixed を名乗らせない行）

- R13 最後のテストが ok・green でない時の残りの行（赤の原因つき）
  - 元: works/.shared/core/report.py:597-598 `rest_outside_validator`・:476 `tests_word`
  - 今: 表
  - 証: lib/tests/test_outcome.py::TableCase.test_7_residue
  - 本物の run: 筋書きでのみ
  - 狭め: 元の語（環境で起こせなかった・走れなかった・CI の役の状態）は赤の原因の字に替わった。CI の役のブロックは今の線に無いので対象が無い

- R14 独立の目の阻害（redesign-needed・unverifiable）を目ごとに 1 行。深さで省いた目（null）は数えず、目のブロックが ok: false で数えた目が無ければ 1 行
  - 元: works/.shared/core/report.py:506 `eye_counts`・:599-602（blocked・not_run・missing の 3 欄。missing は「結果が無い——再実行の要あり」）
  - 今: 表
  - 証: lib/tests/test_outcome.py::TableCase.test_7_residue・lib/tests/test_outcome.py::TableCase.test_eyes_not_ok_without_counted_eyes_is_left・lib/tests/test_outcome.py::ReadingCase.test_skipped_eyes_are_not_left ・lib/tests/test_outcome.py::TableCase.test_missing_eye_of_a_standard_run_is_left・lib/tests/test_runreport.py::LinesCase.test_missing_eye_is_named_apart_from_the_skipped・tests/workflows/test_report.py::FactsCase.test_missing_eye_of_a_standard_run_is_not_fixed
  - 本物の run: report/report.md「## 独立の目」の R1〜R4 の行
  - 狭め: 元は結果の無い目（missing）と走っていない目（not_run）も残りに数えた。今は null を「深さで省いた」と読み、落ちた目と省いた目を分けない（目のブロックが ok: true のまま目が null なら黙る）。#68 で狭めた。Archon で不可でない（eyes の返りに省いた訳を足すか、深さの返り R42 と照らせば分けられる）→ 戻す → 部分 C で戻した（深さの返り redepth と照らす。返りが届かない run は前のまま数えない）

- R15 修正の段の単位の given_up・not_done、done: false、差分の審査の pass: false を残りに
  - 元: works/.shared/core/report.py:613-622（検証器の阻害の行）・:819-821（next_request の not_done）
  - 今: 表
  - 証: lib/tests/test_outcome.py::TableCase.test_7_residue
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- R16 判定の開いた単位が閉じたかを機械が数え直し、閉じていない単位（閉鎖の表の closed が偽）を残りに数える
  - 元: works/.shared/core/report.py:434 `_closed_units`・:613-622（検証器の「[block] 未解消: <key>」の行から閉じた単位だけを除く）
  - 今: 表
  - 証: lib/tests/test_outcome.py::ReadingCase.test_unit_not_closed_in_the_closure_table_is_left
  - 本物の run: 筋書きでのみ
  - 狭め: #68 で書かれずに落ちた（#68 の本文の「戻せない」一覧は表示の行だけを挙げ、結末への効きを書いていない）。Archon で不可でない（fix の返りに閉鎖の表の指し札を足す）→ 戻す → 部分 D2 で戻した

- R17 直した後の構造の実測が見た住処の外の知る場所の増えを残りに
  - 元: works/.shared/core/report.py:603 `structmark.after_rows`
  - 今: 表
  - 証: lib/tests/test_outcome.py::ReadingCase.test_after_rows_are_left
  - 本物の run: 筋書きでのみ（種は柵の表を持たない）
  - 狭め: 無し

- R18 測れていない素材を残りに。依頼が命令と出力つきで答えた素材は除く
  - 元: works/.shared/core/report.py:618-622 `gatemarks.measured_materials`・:701 `_unmeasured_row`
  - 今: 表
  - 証: lib/tests/test_outcome.py::ReadingCase.test_material_answered_with_command_and_output_is_not_left・tests/workflows/test_report.py::FactsCase.test_stamp_carries_the_plan_round_and_measured_answer_reaches_outcome
  - 本物の run: judge/materials.json の素材ごとの status、report/report.md「1. 人が決めること」の「人が確かめる物」の素材の行
  - 狭め: 無し

- R19 落ちたが線が受け止めた節を残りに（返りの在るブロックの中の落ちは重ねない）
  - 元: works/.shared/core/report.py:576 `absorbed_rows`（seen）
  - 今: 表
  - 証: lib/tests/test_outcome.py::ReadingCase.test_absorbed_fall_is_left_unless_its_block_returned
  - 本物の run: 筋書きでのみ
  - 狭め: 受け止めたかの決め方の違いは R82

- R20 残りの件数の行を結末に依らず常に出す（0 件も。走っていない目・結果の無い目の注記つき）
  - 元: works/.shared/core/report.py:1588-1591 `always_rows` の「残り: N 件」
  - 今: 表
  - 証: lib/tests/test_runreport.py::DecisionsCase.test_residue_count_is_always_shown
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば report/report.md「1. 人が決めること」）
  - 狭め: #68 で書かれずに落ちた。不可でない → 戻す → 部分 C で戻した（検証器の阻害は持たないので数えない）

### 報告の頭と「1. 人が決めること」

- R21 冒頭 3 行: 起きたこと（結末の平易な語と、組を止めて持ち越したら受けた単位と止めた単位の 1 文）・決めてほしいことの件数（無ければ次の run に渡す物の件数）・推し
  - 元: works/.shared/core/report.py:898 `head3`・:887 `split_line`
  - 今: 表
  - 証: lib/tests/test_runreport.py::DecisionsCase.test_nothing_to_decide_puts_next_items・lib/tests/test_runreport.py::DecisionsCase.test_decisions_are_counted・lib/tests/test_runreport.py::CarryCase.test_asked_conflicts_parked_groups_and_rejudge_reach_next_request
  - 本物の run: report/report.md の 3〜5 行目
  - 狭め: 元の split_line は止めた単位の直しの控えのパスを名指した。今は組の id だけ。軽い差

- R22 人が決めることの 11 の種類を件数（0 も）と 1 件 1 行で出し、round_limit の残りは直す義務に戻せなかった単位と重ねて数えない
  - 元: works/.shared/core/report.py:919 `head_decisions`・:898-904 `head3` の parts
  - 今: 表
  - 証: lib/tests/test_runreport.py::DecisionsCase.test_unreturned_unit_is_counted_as_decision・lib/tests/test_runreport.py::LinesCase.test_protected_hits_from_eyes_only・lib/tests/test_runreport.py::DraftsCase.test_held_ledger_question_is_drafted_in_attended_run_too
  - 本物の run: report/report.md「## 1. 人が決めること」の各「…: N 件」
  - 狭め: 下の R23・R24 の種類が無い

- R23 修正役が人に回した物（changes[].breaks.accepted。壊すと分かって通した理由）を人が決めることに数え、1 件 1 行で出す
  - 元: works/.shared/core/report.py:304 `handoff_lines`・:908（head3 の「修正役が人に回した物」）・:1003-1006
  - 今: 表
  - 証: lib/tests/test_runreport.py::DecisionsCase.test_accepted_breaks_are_counted_as_decision
  - 本物の run: 筋書きでのみ
  - 狭め: #68 で書かれずに落ちた（#68 の本文の一覧に無い）。Archon で不可でない（fix の返りに欄か指し札を足す）→ 戻す → 部分 D2 で戻した

- R24 同じ run の中で直した修正案の項目の行
  - 元: works/.shared/core/report.py:1075 `_amend_lines`
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_amended_items_are_listed（test_amended_plan_items_are_listed の名を変えた）
  - 本物の run: 筋書きでのみ
  - 狭め: #68 で書かれずに落ちた。不可でない → 戻す → 部分 C で戻した

- R25 申し出の件数と、裁定ごと（parked・fix_test_scope・fix_code_as・ask_human・unruled、在れば replace_query・fix_plan_item）と種類ごと（6 種と種類なし）の内訳
  - 元: works/.shared/core/report.py:1112 `_conflict_line`
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_conflict_counts_line・lib/tests/test_outcome.py::ReadingCase.test_conflict_counts_and_asked_units
  - 本物の run: report/report.md「食い違いの申し出: 0 件（…）」
  - 狭め: 無し

- R26 問いの台帳: 保留の行（答えが無いと直さない単位・答える時の answers の question）・答えた行と答えの出どころ・素材の答えた行・2 つ以上に当たる答え・どの問いにも当たらない答え・関所で答えたが単位に戻せなかった行
  - 元: works/.shared/core/gatemarks.py:1216 `held_lines`・:1226 `answered_lines`・:1036 `unmatched_answer_lines`
  - 今: 表
  - 証: lib/tests/test_runreport.py::LedgerCase.test_held_line_names_units_left_and_answer_key・lib/tests/test_runreport.py::LedgerCase.test_answered_lines_name_where_the_answer_came_from・lib/tests/test_runreport.py::LedgerCase.test_answer_hitting_two_questions_answers_neither・lib/tests/test_runreport.py::LedgerCase.test_answers_that_answer_nothing_are_named・lib/tests/test_runreport.py::LedgerCase.test_answered_but_unit_gone_is_held・lib/tests/test_runreport.py::LedgerCase.test_material_answer_lines
  - 本物の run: 筋書きでのみ（種の依頼は answers を持たない）
  - 狭め: 依頼の答えは字の一致だけで当てる。判定の結び answer_ties は R77

- R27 人の判断を待つ項目への答えの下書き（下書きの印 draft・source つき）: 無人の run で関所が開かなかった問い・推しの尾・狭めの決め手（recommend・no_narrow）・事前審査の穴の面・定石の外れ（1 行だけ）・保留の台帳の問い・問いの無い測れていない素材（reason つき）・最後の関所の R4 の問い。件数の行と next-request.json の answers
  - 元: works/.shared/core/gatemarks.py:991 `answer_drafts`・:1026 `draft_line`、works/.shared/core/report.py:2079 `next_doc`
  - 今: 表
  - 証: lib/tests/test_runreport.py::DraftsCase の 10 本
  - 本物の run: 筋書きでのみ（関所は人が答える）
  - 狭め: 無し

- R28 例で証明できない判定の問いの行（今の判定の judgment の units から出し直す）
  - 元: works/.shared/core/querytest.py:211 `unproven_lines`（works/.shared/core/report.py:986）
  - 今: 表
  - 証: lib/tests/test_runreport.py::CarryCase.test_unproven_queries_are_listed_from_the_current_judgment
  - 本物の run: report/report.md「例で証明できない判定の問い: N 件」（判定が例を出せない単位が在る時）
  - 狭め: 無し（#68 の 3 回目の直しで戻った）

- R29 修正の後に判定の問いで数え直した閉鎖の行（数が減っていない単位を先に・申告と合わない単位）
  - 元: works/.shared/core/querytest.py:254 `closure_lines`・`STUCK_HEAD`（works/.shared/core/report.py:990-997）
  - 今: 表
  - 証: lib/tests/test_runreport.py::FixBesideLinesCase.test_closure_recount_lines
  - 本物の run: 筋書きでのみ
  - 狭め: #68 の「戻せない」一覧の 2 つ目。判定は R72 → 部分 D2 で戻した

- R30 再審の結果の行（答えと異議）・再審が直す単位にした単位・block から下げた単位・単位の変化（足された・消えた・欄の変化。異議に名指された単位と争点でない単位を分ける）・再審されずに残った異議
  - 元: works/.shared/core/report.py:1181 `rejudge_lines`・:1127 `_rejudge_changes`・:1195 `_rejudge_next`
  - 今: 表
  - 証: lib/tests/test_runreport.py::CarryCase.test_asked_conflicts_parked_groups_and_rejudge_reach_next_request・lib/tests/test_runreport.py::CarryCase.test_rejudge_changes_and_opened_units・lib/tests/test_runreport.py::CarryCase.test_rejudge_lowered_block_units_are_shown_and_carried・lib/tests/test_runreport.py::CarryCase.test_objection_without_rejudge_is_carried
  - 本物の run: 筋書きでのみ（種は再審しない）
  - 狭め: 「異議に名指された」の判じ方が元（rejudge-diff.json の named の印。番号の正規表現）と違い、今は key の字が異議の文に含まれるか。線の judged（workflows/line/scripts/judged.py:36 `named_numbers`）とも食い違う。往復の数と並びは R76

- R31 判定の隣のファイルの行: 単位の裏取り（根本でない・決められない・証拠が無い・場所が違う・確かめられない・重複・順番。読めなければその旨）・並行 PR と重なるので外した範囲・依頼の実測を前提が仮説でしか書けなかった制約
  - 元: works/.shared/core/report.py:1225 `verify_lines`・:1282-1287（`_pr_lines` の後半）・:1209 `_premise_hypotheses`
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_verify_pr_excluded_and_premise_hypotheses・lib/tests/test_runreport.py::LinesCase.test_broken_verify_notes_say_so
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば judge/judge-verify.json、report/report.md「判定の単位の裏取り: N 単位とも根本・証拠・場所が合った…」）
  - 狭め: 無し（元は周ごと。今は 1 周の線なので同じ）

- R32 直しが対象に足した行の works の内側の語（対象が直す前の版で既に使う語は除く）
  - 元: works/.shared/core/report.py:1042 `inner_word_lines`
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_inner_words_in_added_lines
  - 本物の run: fix/fix/fix.diff と report/report.md「直しが対象に足した行に works の内側の語…」（種の直しが内側の語を足せば）
  - 狭め: 無し

- R33 守りのパスに当たった差分（封じと独立の目の両方から、重ねない）
  - 元: works/darkfactory/lib/line_edge.py の最後の関所の守りの当たりと、報告の冒頭 1
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_protected_hits_from_eyes_and_merge_reason・lib/tests/test_runreport.py::LinesCase.test_protected_hits_from_eyes_only
  - 本物の run: 筋書きでのみ（種は守りのパスを触らない）
  - 狭め: 無し

- R34 修正前の関所が聞かずに通した行（plan-review・replan-review の review の隣の gate-passes.json。読めない・無い時も 1 行）
  - 元: works/.shared/core/report.py:964 `gatemarks.lines`
  - 今: 表
  - 証: lib/tests/test_runreport.py::DecisionsCase.test_gate_passes_follow_decisions・lib/tests/test_runreport.py::DecisionsCase.test_gate_passes_missing_or_broken_is_one_line
  - 本物の run: plan-review/pass-<k>/gate-passes.json、report/report.md「修正前の承認ノードが聞かずに通した行（plan-review）: N 件」
  - 狭め: 無し

- R35 事前審査の壁打ちの往復の行（往復の数・結末・残った key と、往復ごとの block・fixed・disputed・下げた key・項目の閉じ・開き・保留）
  - 元: works/.shared/core/converge.py:593 `lines`（works/.shared/core/report.py:965）
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_converge_lines_reach_the_report（test_plan_review_passes_are_listed の名を変えた）
  - 本物の run: plan-review/ の往復の控えと report/report.md
  - 狭め: #68 で書かれずに落ちた。不可でない → 戻す → 部分 C で戻した

- R36 独立設計が問いは立たないと返したのに根拠にパス:行の名指しが無い 1 行
  - 元: works/.shared/core/report.py:1265 `_design_unanchored`
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_design_without_anchor_is_named
  - 本物の run: plan-review/ の独立設計のファイル
  - 狭め: #68 で書かれずに落ちた。不可でない → 戻す → 部分 C で戻した

- R37 修正の受け付けの事後の関門の束が赤緑を確かめずに通した回・はみ出しを相談で認めた／戻した・関所の条件の相談で認めた新しいテスト・守りのテスト、と範囲の相談の 1 問 1 答（回数と答えごとの数）
  - 元: works/.shared/core/report.py:1634 `gates_lines`・:1606 `plan_ask_lines`（冒頭 4）
  - 今: 表
  - 証: lib/tests/test_runreport.py::FixBesideLinesCase.test_fix_trace_rows_are_listed
  - 本物の run: fix/fix/trace.jsonl
  - 狭め: #68 で書かれずに落ちた（#68 の本文の一覧に無い）。不可でない（fix の diff の隣のファイル。約束の隣のファイルに足す）→ 戻す → 部分 D2 で戻した

- R38 clean が消したファイル（走らせていない・読めないを 0 件と分ける）・レンズ（見た・採った・捨てた・落ちたレンズ）・仕組みの異常の件数を結末に依らず常に
  - 元: works/.shared/core/report.py:1551 `always_rows`
  - 今: 表
  - 証: lib/tests/test_runreport.py::DecisionsCase.test_always_rows_name_clean_lens_and_not_run
  - 本物の run: fix/fix/fix-removed.json・fix/fix/lens.json
  - 狭め: #68 で書かれずに落ちた。clean とレンズは不可でない → 戻す。仕組みの異常は元の盤面の trace と包みの記録に頼ったので U6 に結ぶ → 持ち主 → 部分 D2 で clean とレンズを戻した。仕組みの異常は「取れない（U6）」と書く

- R39 落ちたレンズを次の依頼に「再実行の要あり」で運ぶ（控えが読めなければそれも）と、報告の「未確認のレンズ」の節（局所レビューの戻した・見ていないレンズを先に）
  - 元: works/.shared/core/report.py:774 `lens_next_items`・:2072-2073（diverted.report_lines・lens.report_lines）
  - 今: 表
  - 証: lib/tests/test_runreport.py::CarryCase.test_failed_lens_is_carried_as_rerun
  - 本物の run: fix/fix/lens.json
  - 狭め: #68 で書かれずに落ちた。不可でない → 戻す → 部分 D2 で戻した

### 「2. 入口・段・決めた人」

- R40 入口の文・最後の関所の開き方・始めの記録（run・元の版・テストの命令・TDD の実行ファイル・無人）・走った段と飛ばされた段・直す前のテスト
  - 元: works/.shared/core/report.py:1302 `head_entry`・entry.baseline_line（works/.shared/core/entry.py:792）
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_entry_gate_words・lib/tests/test_runreport.py::LinesCase.test_entry_lists_ran_and_skipped_stages_and_baseline（返りが null の段が「飛ばされた・返りの無い段」に、test-gate-base の赤の原因が「直す前のテスト: 赤（赤の原因 …）」に出る。3 行のどれを消しても赤）
  - 本物の run: start.json（run の置き場の直下）と report/report.md「## 2. 入口・段・決めた人」
  - 狭め: 下の R41

- R41 段（thickness）・機能の on/off（features_off・features_on と既定）・決めた人（関所の答えの数）・forge が無い時の並行 PR の条件外
  - 元: works/.shared/core/report.py:1308-1338 `head_entry`・:1339 `forge_line`
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_entry_names_thickness_and_features
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば start.json（run の置き場の直下）の thickness（標準）・features）
  - 狭め: #68 で書かれずに落ちた。不可でない → 戻す（元の「下げている所 downgrades.json」と「このラインに無い節」は線の形が変わったので対象が無い） → 部分 C で戻した（下げている所は J41。このラインに無い節は対象が無い）

- R42 線が渡した深さの行（単位ごとの深さ・標準へ上げた信号・軽量で省いた物）
  - 元: works/darkfactory/lib/depth.py:192 `lines`、works/darkfactory/scripts/report.py:126（INPUTS_DEPTH の lines）、works/.shared/core/report.py:1332
  - 今: 表
  - 証: 要追加: lib/tests/test_runreport.py::LinesCase.test_redepth_lines_reach_entry — redepth の返り（depth・raised・skip_optional）から depth.lines の行が入口の節に出る（元 works/tests/test_report.py::HeadCase.test_depth_lines_in_head_entry :1005）
  - 本物の run: 線の節 `redepth` の出力 depth・raised・skip_optional（workflows/line/works-factory-line.yaml:665-686）
  - 狭め: #68 の「戻せない」一覧の 4 つ目。判定は R74

- R43 TDD の輪を回していない修正の段（組）でテストの凍結が効いていないと理由つきで 1 行
  - 元: works/.shared/core/report.py:1984 `freeze_lines`
  - 今: 表
  - 証: lib/tests/test_report.py::TddLinesCase.test_head_names_stages_without_freeze・lib/tests/test_runreport.py::TddCase.test_groups_reach_tdd_lines_unchanged
  - 本物の run: report/report.md「テストの凍結: …で効いていない」（種で TDD の輪が回れば出ない）
  - 狭め: 無し

### 「3. 止めたか」

- R44 結末と止めた段の語・関所ごとの答え（開かなかったも）・merge-seal / merge-apply が ok でない訳・途中で落ちた節と誤りの 1 行目・続きで済んだ節（落ちた回と最後の誤り）・受け止めた落ち・返りの続きの切れ目・結果を名乗れない訳
  - 元: works/.shared/core/report.py:1346 `head_stop`
  - 今: 表
  - 証: lib/tests/test_runreport.py::BuildCase.test_stopped_by_request_still_writes_report・lib/tests/test_runreport.py::LinesCase.test_seal_not_ok_says_why・lib/tests/test_runreport.py::TranscriptCase.test_rows_give_cost_time_failed_and_retried・lib/tests/test_runreport.py::TranscriptCase.test_fall_the_line_went_past_is_absorbed_not_interrupted・tests/workflows/test_report.py::FactsCase.test_unknown_answer_word_is_record_invalid_with_its_reason
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば report/report.md「## 3. 止めたか」の「承認ノード gate-final: approve（…）」）
  - 狭め: 止め札の行は R2

- R45 run の記録の読み: 最後が node_error の節を、後にほかの節（自分の include を除く）が始まったかで落ち（failed）と受け止めた落ち（absorbed）に分け、node_error の後に済んだ節を retried に
  - 元: works/.shared/core/report.py:545 `split_fallen`、works/darkfactory/scripts/report.py:123-124（reads.retried_nodes）
  - 今: 表
  - 証: lib/tests/test_runreport.py::TranscriptCase.test_rows_give_cost_time_failed_and_retried・lib/tests/test_runreport.py::TranscriptCase.test_fall_the_line_went_past_is_absorbed_not_interrupted
  - 本物の run: `$LOG_DIR/<run>.jsonl`（Archon が script に LOG_DIR を渡す: packages/workflows/src/exec-environment.ts:42）
  - 狭め: 決め方の違いは R82

### 「4. 読んだ証拠と包み」「5. 見る所」

- R46 役ごとの読んだ証拠（渡した・読んだ跡の無い件数）・包みが通ったか・会話を継いだ起動の数・起動の即時の失敗
  - 元: works/.shared/core/report.py:1385 `head_reads`
  - 今: 表
  - 証: lib/tests/test_runreport.py::BuildCase.test_reads_section_shows_what_u6_can_take（節ごとの道具の呼び・reads-*.json の欠けと測れない訳・「取れない（U6）」の Bash の行）
  - 本物の run: report/report.md「## 4. 読んだ証拠と包み」
  - 狭め: 包み（前の起こし方の殻 adapter）を落としたので対象が変わった。U6（当時は未決）。段 1b で U6 を決めた（docs/design.md の U6）: 役が自分で呼んだ Read・Edit・Write の `file_path` は Archon の `provider_event` から取れ、下請け（Agent）の中の呼びと読んだ時のファイルの sha は `provider_event` に無いが、PostToolUse のフックで取れる（書き込みの記録は PR #178 で `bin/_lib/record-write.py` に、読んだ証拠は #120 で `bin/_lib/record-read.py` に戻った）。→ 読んだ証拠は #354 で戻した（U6 で取れる分。取れないのは Bash で読み書きしたファイルだけ）。包みが通ったかは T49（#348 の後）。会話を継いだ起動の数・起動の即時の失敗は戻していない

- R47 見る所: 判定・目的・定石・仕様・目的の外の所見・計画・構造の目・波及・事前審査・独立設計・差分・申し出と裁定・直す前と最後の試験の記録・直した後の構造・封じた差分・置いた差分のパス
  - 元: works/.shared/core/report.py:1706 `head_where`
  - 今: 表
  - 証: tests/workflows/test_report.py::FactsCase.test_returns_with_pointers_reach_the_report
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば report/report.md「## 5. 見る所」の「判定（judge.judgment）: …/judge/judgment.json」）
  - 狭め: 元の「run の作業ツリー」の行が無い（線の作業ツリーは Archon が持つ）。軽い差

### 本文の節

- R48 TDD の輪の単位ごとの結末（型つきの成果物 tdd-unit を include と周で修正の段に分け、組ごとに。赤の引用・仮の実装・照らせなかった名指し・控えから使った結果。成果物が無ければ fix の単位の行と訳）
  - 元: works/.shared/core/report.py:1961 `tdd_lines`・:1926 `_red_evidence`
  - 今: 表
  - 証: lib/tests/test_report.py::TddLinesCase.test_each_unit_gets_its_outcome・lib/tests/test_report.py::TddLinesCase.test_tdd_unit_shows_red_quotes_stub_files_and_unchecked・lib/tests/test_runreport.py::TddCase.test_second_fix_stage_is_named_apart・lib/tests/test_runreport.py::TddCase.test_units_without_artifact
  - 本物の run: 型つきの成果物の一覧の tdd-unit、report/report.md「## TDD のループの単位ごとの結末」の「修正の段（組 g1）: 2 単位（赤→緑 2…）」
  - 狭め: 無し

- R49 緑の認証（全部の周）: green-cert ごとに緑か・ok・赤の原因、認証が通した赤（inherited・environment）を名指す
  - 元: works/.shared/core/report.py:1042-1050 の最後のテストの行（entry.suites_line・ログ。works/.shared/core/entry.py:819）
  - 今: 表
  - 証: lib/tests/test_runreport.py::TypedCase.test_green_cert_names_red_let_through・lib/tests/test_runreport.py::TypedCase.test_green_cert_names_suites_and_log、tests/workflows/test_report.py::FactsCase.test_green_cert_section_reads_the_test_gate_evidence（受け皿の返りの欄を証拠の文を開かずに facts の節に通す）・tests/workflows/test_test_gate.py::ResultScriptCase.test_returned_values_are_the_evidence_rows（返りの欄と evidence.md の行が同じ値）
  - 本物の run: 型つきの成果物 green-cert と test-gate-base・test-gate-final の返り、report/report.md「## 緑の認証（全部の周）」
  - 狭め: → #124 で戻した（返りの欄の走らせ方とログ。元は最後のテストだけ、今は直す前のテストも同じ形で並べる）。修正前のテストとの並べ（baseline_line）は T35

- R50 独立の目の節: 目ごとの状態と理由（省いた目は「深さで省いた」）と型つきの成果物 eye-verdict（形の違う物は注意へ）
  - 元: works/darkfactory/lib/line_edge.py:505-523 の目の行
  - 今: 表
  - 証: lib/tests/test_runreport.py::TypedCase.test_eye_verdict_of_other_shape_is_a_note
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば report/report.md「## 独立の目」）
  - 狭め: 無し

- R51 構造の目の行と直した後の構造の実測
  - 元: works/.shared/core/report.py:2066-2068 `structmark.report_lines`
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_structure_rows_and_after
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば plan/ の design.jsonl、report/report.md「## 構造の目」）
  - 狭め: 無し

- R52 世界の解: 依頼の行ごとの定石・web で確かめたかの印・依頼の解き方との比べ・類の数。判定の world が null なら段が何も返さなかった 1 行
  - 元: works/.shared/core/worldmark.py:265 `report_lines`
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_world_rows_keep_mark_and_versus・lib/tests/test_runreport.py::LinesCase.test_world_null_says_the_stage_gave_nothing
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば judge/world.jsonl、report/report.md「## 世界の解」）
  - 狭め: 段が落ちた訳と落とした抜き書きの数は R79

- R53 判定が目的の外とした所見: 1 件ずつの行を本文の節に、行を次の依頼に（下書きの印つき）
  - 元: works/.shared/core/outpurpose.py:216 `report_lines`・:200 `next_items`・:229 `count_line`
  - 今: 表
  - 証: lib/tests/test_runreport.py::DecisionsCase.test_nothing_to_decide_puts_next_items・lib/tests/test_runreport.py::LinesCase.test_outside_purpose_rows_and_wrong_name（節の 1 件ずつの行・件数と置き場の 1 行の位置・名が違うファイルを読まない注意）
  - 本物の run: judge/out-of-purpose.json
  - 狭め: 無し（→ 件数と置き場の 1 行を戻した）

- R54 模型（節ごと、run の途中で替わったら印）と費用（自分の費用を言う行の和を「途中」として。言い直しの行・輪の和を数えない。費用の欄の無い行の件数。節ごとの時間）。記録が読めなければ「取れない（訳）」
  - 元: works/.shared/core/report.py:1769 `cost_rows`・:1806 `head_cost`・:1878 `head_models`
  - 今: 表
  - 証: lib/tests/test_runreport.py::TranscriptCase.test_none_transcript_cost_cannot_be_taken・lib/tests/test_runreport.py::TranscriptCase.test_rows_give_cost_time_failed_and_retried
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば report/report.md「## 費用」の「費用の合計: $X（途中。…」と「## 模型」）
  - 狭め: 元の「取れない節の理由（source unavailable の reason と Archon の版）」は件数だけになった。会話を継いだ起動の印は包みが無いので無い（U6）

- R55 注意（読めなかった物）: 型つきの一覧の errors と読めない一覧・開けなかった指し札・素材の状態が読めない・run の記録が読めない訳を 1 行ずつ。無ければ「無い」
  - 元: 元は読めない物を各行で言った（例 works/.shared/core/report.py:1592-1593）
  - 今: 表
  - 証: lib/tests/test_runreport.py::TypedCase.test_warnings_each_reach_notes・tests/workflows/test_report.py::TypedCase.test_errors_each_become_a_warning・tests/workflows/test_report.py::FactsCase.test_empty_inputs_are_record_invalid_and_exit_zero
  - 本物の run: report/report.md「## 注意（読めなかった物）」
  - 狭め: 無し（上位）

- R56 節の行は「- 」か字下げした内訳の行
  - 元: works/.shared/core/report.py:2045
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_every_line_is_a_bullet
  - 本物の run: report/report.md
  - 狭め: 無し

### 次の依頼と前の失敗

- R57 次の依頼 next-request.json: 残りの行（R2 の作り直しは前の失敗だけ。人に回した単位の修正の行はその単位の行が持つ）・目的の外の所見・戻せなかった組・再審の結果・再審されずに残った異議・再審が開いた／下げた単位・人に回した申し出の単位・途中で落ちた run の案の直しを待つ単位（未完了の印 PENDING_WHY）・答えの下書き。重ねない。中身が無ければ書かない。約束の Schema で照らす
  - 元: works/.shared/core/report.py:784 `next_request`・:2079 `next_doc`、works/.shared/core/carry.py:191 `compose`・:221 `save`
  - 今: 表
  - 証: lib/tests/test_runreport.py::BuildCase.test_writes_report_and_only_present_carries・lib/tests/test_runreport.py::CarryCase.test_asked_conflicts_parked_groups_and_rejudge_reach_next_request・lib/tests/test_runreport.py::CarryCase.test_waiting_replan_rows_are_carried_only_when_interrupted
  - 本物の run: report/next-request.json（種で素材が残れば answers の下書き）、`report__report.output.next_request`
  - 狭め: 手直しの穴（R73）・落ちたレンズ（R39）の行が無い

- R58 前の失敗 prior-failures.json: 修正の受け付けを通らなかった単位の理由・計画が修正案を出せなかった訳・止めの語で止めた段の語と意味・R2 の作り直しの訳。人待ちの語は数えない
  - 元: works/.shared/core/report.py:720 `prior_failures`・:756 `prior_lines`
  - 今: 表
  - 証: lib/tests/test_runreport.py::BuildCase.test_writes_report_and_only_present_carries・lib/tests/test_runreport.py::CarryCase.test_plan_give_up_is_a_prior_failure・lib/tests/test_runreport.py::CarryCase.test_line_stop_words_are_prior_failures
  - 本物の run: report/prior-failures.json（種では書かれない見込み）
  - 狭め: 受け付けの最後の拒否の本文は R78

- R59 run の後の CI が赤と言った試験の id を次の依頼の prior_failures に足す口（carry-ci）と、持ち越しの形（欄の名・下書きの印・Schema・役の材料に貼る節）
  - 元: works/.shared/core/carry.py:265 `carry_ci`・:244 `prior_section`
  - 今: 表
  - 証: lib/tests/test_carry_ci.py::CarryCase.test_ids_become_prior_failures_rows ほか 7 本・lib/tests/test_carry_home.py の 10 本（例 lib/tests/test_carry_home.py::Board.test_redesign_rows_get_their_own_fix_section）。弱い: 元の works/tests/test_carry_home.py の test_carry_names_live_in_carry（考えの住処の柵の表が carry-over の名の漏れを縛る）が移されていない。柵の機械は lib/conceptfence.py に在る。要追加: lib/tests/test_carry_home.py::CarryHomeCase.test_carry_names_live_in_carry（柵の領域の棚卸しと重なるなら、そちらで持つ）
  - 本物の run: 筋書きでのみ（run の後の手）
  - 狭め: 無し（能力は lib/carry.py に在る。移されていないのは試験だけで、証の欄に書く）

### AI の報告と初見の確かめ

- R60 書き手の輪: 書き手（読むだけの道具・sonnet・medium）→ 初見の確かめの本文 → 初見の読み手（道具なし・新しい会話）→ 受け付け。3 回まで。前の回の拒否の訳はファイルで script の節（write-reject）から渡す
  - 元: works/blk-report/blk-report.yaml（書き手の輪）、works/blk-report/lib/report_roles.py:290 `prep`・:328 `write_cold_prep`
  - 今: 表
  - 証: tests/workflows/test_report.py::ShapeCase.test_roles・tests/workflows/test_report.py::ShapeCase.test_writer_receives_the_reject_file_through_the_reject_node・tests/workflows/test_report.py::ShapeCase.test_loop_gives_up_with_the_roles_count
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 節 `report__write-loop.write`・`report__write-loop.cold`・`report__write-loop.accept` の出力、report/rejects-report.md（拒んだ回だけ））
  - 狭め: 無し（輪の頭の script の節は #100 の直し。Archon の include の読み込みが with: で結んだ名を入力の欠けと数えるため: packages/workflows/src/include-expander.ts:566-579）

- R61 受け付けの順: 読む → terms の型 → 表のセルの書式（「。」か 50 字超で拒む。`コード` は数えない）→ 初見の判定。拒否の行に種類（cold・format・answer）。3 回拒めば受け取れなかった訳。初見だけが通さない時は 3 回目に受け取り、通らなかった事実（`report_roles.NOT_PASSED`）を機械の事実の拒みの数の行に 1 行で残す（#495 で本文の頭から移した）
  - 元: works/blk-report/lib/report_roles.py:429 `accept`・:381 `format_problems`・:510 `count_rejects`
  - 今: 表
  - 証: lib/tests/test_runreport.py::AcceptCase.test_pass_is_taken・lib/tests/test_runreport.py::AcceptCase.test_cold_rejects_twice_then_takes_with_mark・lib/tests/test_runreport.py::AcceptCase.test_format_and_terms_rejected_first・lib/tests/test_report_roles.py::FormatCase・lib/tests/test_report_roles.py::RejectCountRowsCase.test_rows_without_kind_count_as_unknown・tests/workflows/test_report.py::AcceptScriptCase.test_cold_redesign_three_times
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば report/rejects-report.json・report/ai.json の not_passed）
  - 狭め: 元の「作業ツリーを変えた返答を拒む」は Archon の `mutates_checkout: false`（packages/workflows/src/dag-executor.ts:1244-1280。変えた節を落とす）と書き手の道具の制限に置き換わった。拒んで書き直させる代わりに輪が落ちて AI の報告が出ない。書き手は書く道具を持たない（works-factory-report.yaml:78）ので実害は無い

- R62 初見の読み手に貼る本文は書き手の頭（見出しの前と「人が決めること」の節）と語の定義の節だけ。読み手には機械の事実の見出しの名を知らせる
  - 元: works/blk-report/lib/report_roles.py:316 `head_of`・:328 `write_cold_prep`
  - 今: 表
  - 証: lib/tests/test_runreport.py::ColdBodyCase.test_head_and_glossary_only・lib/tests/test_runreport.py::ColdBodyCase.test_unreadable_reply_says_so・lib/tests/test_report_roles.py::HeadCase・tests/workflows/test_report.py::ShapeCase.test_cold_reader_is_told_the_machine_heading
  - 本物の run: 節 `report__write-loop.cold-prep` の出力 body、`report__write-loop.cold` の出力 verdict
  - 狭め: 無し

- R63 AI の報告: 来歴の 1 行・本文・語の定義・初見の拒否の回数（通っていなければ同じ行の尾に通らなかった事実と止まった所）・機械の事実（見出しを 1 段下げ、「人が決めること」を機械の数えの見出しに言い換えて節を 1 つに）。受け取れなかった時は訳と機械の事実。#660 で人に向けた報告（機械の冒頭・通らなかった事実の 1 行・書き手の頭・語の定義・置き場の 1 行）と、それ以外を持つ詳細のファイル report-detail.md に分けた
  - 元: works/blk-report/lib/report_roles.py:537 `collect`
  - 今: 表
  - 証: lib/tests/test_runreport.py::CollectCase.test_taken_reply_becomes_ai_report・lib/tests/test_runreport.py::CollectCase.test_not_passed_is_said_at_the_head・lib/tests/test_runreport.py::CollectCase.test_given_up_reply_still_reports・lib/tests/test_runreport.py::CollectCase.test_decisions_section_is_one_place
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば report/report-ai.md、`report__report.output.report_ai`）
  - 狭め: 無し

- R64 来歴の行: 工程の名・run・周（計画の round）・工程のファイルの sha256 の頭 12 字（読めなければ訳）
  - 元: works/blk-report/lib/report_roles.py:476 `stamp`（線・run・周・graph と規則の表の版）
  - 今: 表
  - 証: lib/tests/test_runreport.py::StampCase.test_stamp_names_workflow_run_and_version・tests/workflows/test_report.py::FactsCase.test_stamp_carries_the_plan_round_and_measured_answer_reaches_outcome
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 節 `report__facts` の出力 stamp、report/report-ai.md の最後の行と report/report-detail.md の 1 行目）
  - 狭め: 表の版と線の版は R81

- R65 語の定義の節: 書き手の terms のうち本文に現れる語だけ。pack の一覧は #660 で語の表（記録の名と人に向けた言い方の対）に変え、人に向けた報告で言い換える（定義しない）。pack の一覧が読めなければ例外
  - 元: works/blk-report/lib/report_roles.py:240 `glossary_section`・:236 `_pack_terms`
  - 今: 表
  - 証: lib/tests/test_runreport.py::GlossaryCase.test_only_terms_in_text・lib/tests/test_runreport.py::GlossaryCase.test_pack_terms_come_from_lib・lib/tests/test_runreport.py::StampCase.test_pack_terms_raise_when_unreadable
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば report/report-ai.md「## 語の定義（機械が付けた。本文の外）」）
  - 狭め: 無し

- R66 AI の報告は record_invalid でない run なら回す（途中で終わった run も）
  - 元: works/.shared/core/report.py:2031 `ai_go`（途中で終わった run は回さない）
  - 今: 表
  - 証: lib/tests/test_runreport.py::BuildCase.test_record_invalid_has_no_ai・lib/tests/test_runreport.py::BuildCase.test_writes_report_and_only_present_carries
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 節 `report__facts` の出力 ai_go == true と `report__write-loop.write` が走ったこと）
  - 狭め: 無し（上位）

### 落ちない・前の段が落ちても走る

- R67 報告のブロックは前の段が落ちても飛ばされても、止め札の run でも走り、返す節は落ちない（lib/ を読めない・置き場に書けない時も record_invalid と訳で返る。facts の機械の報告と持ち越しの指し札が在ればそれを指し、無ければ別の名 report-unwritten.md に書く）
  - 元: works/darkfactory/darkfactory.yaml:1314-1325（all_done・always_run）、works/darkfactory/scripts/report.py
  - 今: 表
  - 証: tests/workflows/test_report.py::ShapeCase.test_return_node_runs_whatever_came_before・tests/workflows/test_report.py::CollectScriptCase.test_fallen_keeps_facts_report_and_carries・tests/workflows/test_report.py::CollectScriptCase.test_fallen_without_facts_report_writes_another_name・tests/workflows/test_report.py::CollectScriptCase.test_without_lib_still_returns・tests/workflows/test_report.py::CollectScriptCase.test_unwritable_place_is_record_invalid・tests/workflows/test_report.py::FactsCase.test_unexpected_error_still_returns・tests/workflows/test_report.py::FixtureCase.test_all_empty_and_request_stop_reach_their_words。弱い: resume で前の試みの結果を使い回さないことを照らす物が無い。要追加: 本物の run の resume の筋書き（筋書きでのみ）
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 節 `report__report` の出力（どの run でも在る））
  - 狭め: 元の always_run（resume のたびに回し直す。元 works/darkfactory/darkfactory.yaml:1310-1313 の canary run 7d95d3bc で前の試みの interrupted が使い回された件の対策）は今の YAML に無い。Archon の resume で同じことが起きるかは確かめていない

- R68 返す節の約束の 7 欄（outcome・stop_reason・report・report_ai・next_request・prior_failures・ok）と入力の 17 の名
  - 元: works/darkfactory/darkfactory.yaml:1334-1350・:1373-1391（ok・outcome・judgment_file・review_file・diff_file・faces・report_file・next_request_file・prior_failures_file・tests_green・validator_exit・ai_report_go・export_input・machine_report_file・ai_report）、works/.shared/core/report.py:2085 `final_result`
  - 今: 表
  - 証: tests/workflows/test_report.py::ShapeCase.test_return_fields_are_the_contract・tests/workflows/test_report.py::ShapeCase.test_inputs_are_the_contract・tests/workflows/test_report.py::ShapeCase.test_facts_reads_every_input_by_its_own_name
  - 本物の run: 節 `report__report` の出力欄
  - 狭め: 元の欄の多くは設計の返りの約束（docs/design.md の report の返り）で外した。判定・差分のパスは「5. 見る所」に、AI の報告を選ぶ手は呼び手に移った。tests_green・validator_exit は検証器が無いので対象が無い。設計の決めの範囲

- R69 結末の語から周の鎖（頼まれたら run を何周もつなぐ仕組み）の種（閉じた・開いた・止めた・人・待ち）を引く表と、終わった周の結末・費用・分・止まりの事実
  - 元: works/.shared/core/report.py:113 `OUTCOME_KINDS`・:1853 `round_facts`・:1841 `header_outcome`
  - 今: 無し（表）
  - 証: 要追加（周の鎖を置く時）: 周の鎖の試験で 10 語すべてに種が在る（元 works/tests/test_report.py::OutcomeCase.test_every_outcome_has_a_chain_kind :463）
  - 本物の run: 筋書きでのみ
  - 狭め: 周の鎖は docs/design.md:431 で段 3 に置くと決めてある（設計の順）。報告の能力としては段 3 で戻す

- R70 差分を当てる前に記録の止まりを見る口（止めた run・最後の関所の stop・reject なら当てない）
  - 元: works/.shared/core/report.py:648 `stopped_run`（works/dev/lib.sh:631 が呼ぶ）
  - 今: 表
  - 証: tests/e2e/test_line_scenarios.py::LineScenariosTest.test_every_scenario_passes
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 節 `merge-apply__merge` が走ったか）
  - 狭め: 無し（線に置き換わった）

### #68 の「今の入力に読む先が無いので取り戻せない物」の 1 件ずつ

#68 の本文の最終の一覧（3 回目の直しで「再審が block から下げた単位」と「例で証明できない問い」を外した後）の 12 件を、今の線と各ブロックの置き場で 1 件ずつ確かめた。

- R71 書き手の指示書の gates_deferred の項（gates=merge の run は「合流した版を gates=merge 無しの run で回し、最後の関門を通す」を 1 項として必ず入れる）
  - 元: works/blk-report/prompts/review-loop/report.md:18（works/blk-report/prompts/COPIED_FROM の手直しの行）
  - 今: 無し（表）
  - 証: 要追加（変異の検算を戻す時）: tests/workflows/test_report.py::ShapeCase.test_writer_names_gates_deferred_item
  - 本物の run: 筋書きでのみ
  - 狭め: #68 の言うとおり、今の線の入力（workflows/line/scripts/start.py:165-173 の始めの記録）に gates が無く、変異の検算（p3.delta_gates・p4.final_gates）も今の線に無い。docs/design.md:528・:619「変異の検算を戻すかを持ち主に聞く」に結ぶ。Archon で不可ではない → 持ち主の確かめ待ち（判定: 今は読む先が無い・#68 は正しい） 決め: 段 3 で変異の検算と一緒に持ち主に聞く（線の配線の文書の「この文書の外」の「決めた物」）

- R72 盤面の trace から閉鎖を数え直す行（querytest.closure_lines・STUCK_HEAD）
  - 元: works/.shared/core/querytest.py:254 `closure_lines`
  - 今: 表
  - 証: lib/tests/test_runreport.py::FixBesideLinesCase.test_closure_recount_lines・tests/workflows/test_fix.py::BlockScriptsCase.test_collect_writes_the_closure_beside_the_diff・tests/workflows/test_fix.py::GroupChildScriptsCase.test_group_end_writes_the_result
  - 本物の run: 子の run の置き場の fix/fix/fix-unit-rows.json
  - 狭め: 判定: 今の入力からは取り戻せない（#68 は正しい）が、源は在る。group-end が組の結果（out_dir/<group_id>/result.json。workflows/fix/scripts/group_end.py:5）に表を載せるか、fix の返りに指し札を足せば戻せる。Archon で不可でない → 約束を変えて戻す → 部分 D2 で約束の隣のファイルにして戻した

- R73 手直しの穴の名札（branch_rows・eye_ties・_tie_notes）と、手直しの handled の declared・2 回目の fixed の次の依頼の行
  - 元: works/.shared/core/report.py:1528 `branch_rows`・:1513 `eye_ties`・:807-818（next_request の手直しの行）
  - 今: 表
  - 証: lib/tests/test_runreport.py::CarryCase.test_refix_declared_and_second_fixed_holes_are_carried
  - 本物の run: fix/fix/out-p3.delta_fix.json・out-p3.delta_fix2.json（手直しが走った時）
  - 狭め: 判定: 戻せる。#68 の「fix の返りに手直しの穴の行が無い」は返りの欄としては正しいが、手直しの返答は fix の置き場（fix.diff・conflicts.json と同じフォルダ）に `out-<節>.json` で残る（lib/fixboard.py:213 `OUT_NAME`・:428）。名札は lib/fixboard.py:410-430 `hole_ties` と lib/holeties.py で組める。約束の隣のファイルに足せば足りる。Archon で不可でない → 戻す → 部分 D2 で戻した

- R74 直した後の深さの上げ直しの行（depth_lines）
  - 元: works/darkfactory/scripts/report.py:126、works/darkfactory/lib/depth.py:192
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_depth_lines_name_raised_and_skipped・tests/workflows/test_line.py::CollectAndResultCase.test_deferred_widened_reasons_reach_report
  - 本物の run: 線の節 `redepth` の出力
  - 狭め: 判定: 戻せる。線（workflows/line/works-factory-line.yaml:665-686）が redepth の返り {depth, skip_optional, raised} を作る。線の collect（workflows/line/scripts/collect.py:31-42）と report の inputs に欄を足すだけ。Archon で不可でない → 戻す（線の issue に入れる） → 部分 C で戻した

- R75 方針の文書が始めに固定した版から変わったまま終わった run の行（書き手の指示書の構成 2 の 3 つ目）
  - 元: works/blk-report/prompts/COPIED_FROM の手直しの行（process.policy_change）
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_policy_change_is_named
  - 本物の run: plan-review/policy.json
  - 狭め: 判定: 戻せる（#68 の主張は誤り）。事前審査の差し込みが固めた版を run の置き場の plan-review/policy.json に書き（lib/boardview.py:432-433 `_frozen_policy`。plan-review の review と同じフォルダ）、変わったかは lib/boardview.py:543 `policy_change(folder, cwd)` が出す。始めの記録が policy_md を持つ（workflows/line/scripts/start.py:170）。Archon で不可でない → 戻す → 部分 C で戻した（機械の報告の入口の節に出す。書き手の指示書は触っていない）

- R76 再審の行の往復の数と周の名（rejudge-exit.json の verdicts の並び）
  - 元: works/.shared/core/report.py:1162 `_settled_rounds`・:1189
  - 今: 表
  - 証: lib/tests/test_runreport.py::CarryCase.test_rejudge_passes_and_verdicts_are_listed
  - 本物の run: 筋書きでのみ（rejudge/rejudge-exit.json）
  - 狭め: 判定: 戻せる（#68 の主張は誤り）。判定のブロックが再審の輪を抜ける時に rejudge/rejudge-exit.json {passes, verdicts, objection, new_open_units, lowered, …} と rejudge/rejudge-diff.json（named の印つき）を、再審の judgment.json と同じフォルダに書く（lib/judge_accept.py:3657・:3661-3695、workflows/judge/scripts/rejudge_accept.py:20-24）。今の線は 1 周なので周の名は要らず、往復の数と並びが要る。R30 の名指しの判じ方もこの named で揃う。Archon で不可でない → 戻す → 部分 C で戻した（線は 1 周なので周の名は出さない）

- R77 判定の answer_ties（依頼の答えを問いや単位に結ぶ行）と、単位に結んだ答えを修正役へ渡す行・結ばないと判定が名乗った答えの訳の行（answer_tie_lines）
  - 元: works/.shared/core/gatemarks.py:878 `answer_tie_lines`、works/.shared/core/report.py:2055
  - 今: 表
  - 証: lib/tests/test_runreport.py::LedgerCase.test_answer_ties_bind_answers（部分 B1）
  - 本物の run: judge/answer-ties.json（依頼が answers を持つ時）
  - 狭め: 判定: 戻せる。#68 の「約束の隣のファイルにも無い」は約束の一覧としては正しいが、判定のブロックは judge/answer-ties.json を judgment.json と同じフォルダに書く（lib/judge_accept.py:1015・:1034 `gatemarks.save_answer_ties(jdir, 1, …)`）。約束の隣のファイルに足せば足りる。Archon で不可でない → 戻す → 部分 B1 で戻した

- R78 受け付けの最後の拒否の本文を前の失敗に運ぶ（元 accept-last.json の reason_file）
  - 元: works/.shared/core/report.py:713 `_accept_last_files`・:732-749
  - 今: 表
  - 証: lib/tests/test_runreport.py::CarryCase.test_last_reject_text_is_a_prior_failure・lib/tests/test_runreport.py::CarryCase.test_line_stop_words_are_prior_failures
  - 本物の run: 筋書きでのみ（judge/・plan/・fix/fix/ の rejects-<節>.json の最後の行。前の版の run は reject-<節>-<回>.md）
  - 狭め: 判定: 戻せる。各ブロックの受け付けは拒否の訳を自分の置き場の rejects-<節>.json に積む（新しい run。前の版の run は reject-<節>-<回>.md。例 workflows/fix/scripts/fix_accept.py:10・workflows/fix/scripts/rule_accept.py:6）。置き場は返りの指し札（judgment・plan・diff）と同じフォルダ。名の決まりを約束の隣のファイルに足すか、返りに最後の拒否の指し札を足す。Archon で不可でない → 戻す → 部分 C で戻した（返りの指し札の先のフォルダの下を探す。名の決まりは各ブロックの受け付けのまま）

- R79 世界の解の段が落ちた訳と落とした抜き書きの数（world-state.json の reason・dropped）
  - 元: works/.shared/core/worldmark.py:265-277 `report_lines`（「類 N・落とした抜き書き M」）
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_world_state_reason_and_dropped
  - 本物の run: judge/world-state.json
  - 狭め: 判定: 戻せる（#68 の主張は誤り）。判定のブロックは world-state.json を world.jsonl と同じ judge/ に書く（workflows/judge/scripts/world_finish.py:5、lib/worldmark.py:115 `write`）。world が null の時も judgment の隣（同じ judge/）で読める。Archon で不可でない → 戻す → 部分 C で戻した

- R80 並行 PR の担当への申し送りの下書き（conflicts[].note。投稿していない）
  - 元: works/.shared/core/report.py:1274-1281（`_pr_lines` の前半）
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_parallel_pr_drafts_reach_the_head（test_parallel_pr_handover_drafts の名を変えた）
  - 本物の run: judge/material-pr-check.json（並行 PR が在る時。種では無い）
  - 狭め: 判定: 戻せる（#68 の主張は誤り）。判定のブロックが並行 PR の役の返答を judge/material-pr-check.json に書く（lib/judge_accept.py:3713 `MATERIAL_PR_FILE`・:3814、lib/prcheck.py:29 `ROLE = "pr-check"`。note の在ることは lib/prcheck.py:80-81 が照らす）。Archon で不可でない → 戻す → 部分 C で戻した

- R81 来歴の行の規則の表の版（と、graph の版が線の工程の版であること）
  - 元: works/blk-report/lib/report_roles.py:476 `stamp`
  - 今: 表
  - 証: lib/tests/test_runreport.py::StampCase.test_stamp_names_line_version、tests/workflows/test_report.py::FactsCase.test_stamp_carries_the_plan_round_and_measured_answer_reaches_outcome（facts の節が始めの記録を渡す）
  - 本物の run: report/report-ai.md の最後の行と report/report-detail.md の 1 行目
  - 狭め: 判定: 表の版は規則の表が無いので対象が無い（#68 は正しい）。線の版は report の側を入れた。線の始めの記録の versions.line（workflows/line/scripts/start.py の versions）は持ち主の手に渡した（#124）

- R82 受け止めた落ちの決め方（元は線の YAML の [optional] の宣言と出口の印。今は落ちた後にほかの節が始まったか）
  - 元: works/.shared/core/report.py:533 `_optional`・:545 `split_fallen`（宣言の外の落ちと、出口の印が欠けた run の落ちは全部中断）
  - 今: 表
  - 証: lib/tests/test_runreport.py::TranscriptCase.test_fall_outside_declared_optional_stays_interrupted・lib/tests/test_runreport.py::TranscriptCase.test_fall_the_line_went_past_is_absorbed_not_interrupted・tests/workflows/test_line.py::CollectAndResultCase.test_absorbed_stages_are_declared_by_each_block・tests/workflows/test_report.py::RealRunCase
  - 本物の run: `$LOG_DIR/<run>.jsonl`
  - 狭め: 判定: 狭め（#68 が書いたとおり）。今の決め方は Archon が依存の無い枝を先へ進めただけでも「受け止めた」と数え、宣言していない段の落ちを残り（round_limit）に回して interrupted を名乗らない。Archon で不可でない（線の節の description か報告の inputs に受け止める段の名を宣言すれば元の決め方になる）→ 持ち主の確かめ待ち（戻すなら宣言の置き場を線の issue で決める） 決め: 戻すと決めた。部分 C のやる事 8（線の配線の文書の「この文書の外」の「決めた物」） → 部分 C で戻した（出口の印: 報告は線の出口の後に走るので在るものと読む）

### R の穴

数:

- 行の総数: 83（R1〜R82 と R5b）
- 今: 無し: 2（R69・R71）。ほかに書いた時に無しと数えた 22 行（R5b・R16・R20・R23・R24・R29・R35・R36・R37・R38・R39・R41・R42・R72・R73・R74・R75・R76・R77・R78・R79・R80）は線の配線の部分 B1・C・D2 で戻した
- 証が要追加か弱い: 5（R42・R59・R67・R69・R71）。ほかに書いた時に数えた 22 行は線の配線の部分 B1・C・D2 で試験を足して閉じた（R12・R40・R49・R53・R81 は #124 で、R46 は #354 で試験を足した）
- 狭めたのに Archon が強いていない: 5（R2・R38・R46・R71・R81）。R38 は仕組みの異常の部分（clean とレンズは部分 D2 で戻した）、R81 は線の版の線の側。書いた時に戻すとした 21 件と R82 は線の配線の部分 B1・C・D2 で、R49 は #124 で戻した
- Archon で不可と言える狭め: 0（R60 の輪の頭の script の節と R61 の作業ツリーの確かめは置き換えで、能力は残る）

#68 の「取り戻せない」12 件の判定:

1. gates_deferred（R71）: 今は読む先が無い（正しい）。変異の検算を戻すかの持ち主の問い（docs/design.md:528・:619）に結ぶ → 持ち主
2. 閉鎖の数え直し（R72）: 今の入力からは届かない（正しい）が、源は組の子の run の置き場に在る → fix の返りか組の結果に載せて戻す
3. 手直しの穴の名札（R73）: 戻せる（fix の置き場の out-p3.delta_fix*.json）→ #68 の主張は狭すぎ
4. redepth（R74）: 戻せる（線の redepth の返り。collect と report の inputs に足す）→ 線の issue
5. 方針の文書の変化（R75）: 戻せる（plan-review/policy.json と boardview.policy_change）→ #68 の主張は誤り
6. 再審の往復の数と周の名（R76）: 戻せる（rejudge/rejudge-exit.json）→ #68 の主張は誤り
7. answer_ties（R77）: 戻せる（judge/answer-ties.json）→ 約束の隣のファイルに足す
8. 受け付けの最後の拒否の本文（R78）: 戻せる（各ブロックの置き場の rejects-*.json の最後の行（前の版の run は reject-*.md））→ 名の決まりか指し札を約束に足す
9. 世界の解の段の訳と落とした数（R79）: 戻せる（judge/world-state.json）→ #68 の主張は誤り
10. 並行 PR の申し送りの下書き（R80）: 戻せる（judge/material-pr-check.json）→ #68 の主張は誤り
11. 来歴の表の版（R81）: 表は対象が無い（正しい）。線の版は start で控えれば戻せる → 決めた: 報告の側（stamp が versions.line を読む）は #124 で入れた。線の側（workflows/line/scripts/start.py の versions に line を足す）は持ち主の手に渡した
12. 受け止めた落ちの決め方（R82）: 不可でない狭め → 持ち主（戻すなら宣言の置き場を決める）

一覧の外で #68 が書かずに落とした物（#68 の本文にも「約束を変える頼み」にも無い）: R5b（線の止めの語が報告に届かない）・R14（結果の無い目を省いた目と分けない）・R16（閉じていない単位が結末に効かない）・R20（残りの件数の常の行）・R23（修正役が人に回した物 breaks.accepted）・R24（同じ run の中で直した修正案の項目）・R35（事前審査の往復）・R36（独立設計の名指しなし）・R37（事後の関門の束・はみ出し・範囲の相談）・R38（clean・レンズ・仕組みの異常）・R39（落ちたレンズの持ち越し）・R41（段と機能）・R49（最後のテストの実行器とログ）。

持ち主に要る物:

- 止め札（関所の間で止める口）が無いこと（R2。docs/design.md:428）
- 読んだ証拠・包み・仕組みの異常（R46・R38 の一部。U6）
- gates_deferred と変異の検算（R71）
- 受け止めた落ちの決め方を元の宣言の形に戻すか（R82）
- 始めの記録の versions に線の版 line を足す線の側の直し（R81。報告の側は #124 で入れた。入るまで来歴の行は「始めの記録に無い」と出る）
- 上の「書かずに落とした物」を線の issue と報告の直しのどちらで戻すか（とくに R5b・R16・R23 は結末か人が決めることの件数を変える）

## M: merge ブロックと、run の差分を対象のリポジトリへ当てる所（能力の棚卸し）

読み方の前置き:
- 「wf」は main、「pr74」は #74 の head（線の PR #74 の頭）。元は works/ の下（@2aa7c66c）。
- `bin/apply`（人が run の封じた差分を対象へ当てる口。今の works の `use.sh apply` の後継）は #114 で入った。中身は `bin/_lib/apply.py`、試験は `tests/bin/test_apply.py`（tests/bin の既存の命名 `test_<部品>.py` と同じ）。
- 本物の run の観察先: 種（wf の tests/e2e/target-seed）は works-factory でない対象なので、`lib/protected.json` の行（works-factory 自身のパス）にはふつう当たらない。守りのパスの当たりは本物の run では `merge-seal.output.protected_hits == []` が見えるだけで、当たる道は筋書きでのみ。最後の関所はいつも開くので、本物の run は答え continue/approve → `merge-apply` が走る道を通る。
- 旧 `blk-pr`（works/blk-pr/）は並行 PR の確かめ（p0.parallel_pr）で、差分を封じたり包んだりしない。M の範囲の能力は持たないので行にしない。

### A. 封じる（merge-seal）

- M1 封じる差分は、始めの記録の base_rev（修正の前の HEAD）から今の作業ツリーまでの差で、commit 済み・未追跡を含み、.gitignore に当たる物とバイトコードは含まず、バイナリも載り、本物の index を動かさずに組む
  - 元: works/dev/lib.sh:565-617（`works_dev_show_run` の BRING_BACK の枝。一時の index で read-tree・add -A・diff --cached --binary <base>）
  - 今: 表
  - 証: tests/workflows/test_merge.py::SealTest.test_seal_hashes_the_written_diff・lib/tests/test_green_cert.py::DiffBytesCase.test_untracked_in_ignored_out_index_unmoved・lib/tests/test_green_cert.py::DiffBytesCase.test_rev_is_the_side_compared
  - 本物の run: run の置き場の `merge/sealed.diff`（中身が種の stats.py の直し）
  - 狭め: 無し

- M2 差分の起点は修正の前の HEAD で、変更から入る run（base・pr）でも merge-base を起点にしない（PR にもとからある変更を数えない）
  - 元: works/darkfactory/lib/line_edge.py:640-651 `_protected`（state.inputs.review_rev を起点）
  - 今: 表
  - 証: tests/workflows/test_line.py::StartCase.test_base_alone_is_a_change_entry
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば `start.json` の base_rev（`start.output.record` の先））
  - 狭め: 無し

- M3 封じた差分は書いた後に読み戻し、その sha256 を hash として返す。読み戻しが合わなければ書けたと言わず、前のファイルを残し一時ファイルも残さない
  - 元: works/dev/lib.sh:603-616（書けなかった時は前の差分を消さず終了コード 4。読み戻しは無かった）
  - 今: 表
  - 証: lib/tests/test_seal.py::WriteReadbackCase.test_readback_mismatch_is_not_a_write・lib/tests/test_seal.py::WriteReadbackCase.test_returns_hash_of_what_was_written・tests/workflows/test_merge.py::SealTest.test_seal_hashes_the_written_diff
  - 本物の run: `merge-seal.output.hash` が `merge/sealed.diff` の sha256 と同じ
  - 狭め: 無し

- M4 差分を組む git が落ちた時は、空の差分と取り違えず「組めない」と理由を返す（落ちない）
  - 元: works/dev/lib.sh:603-607（git の失敗は終了コード 4・前の差分を残す）・works/tests/test_use.py::UseShell.test_show_keeps_previous_diff_and_fails_when_git_diff_fails
  - 今: 表
  - 証: tests/workflows/test_merge.py::NeverFailsTest.test_checkout_not_git
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M5 差分が空なら封じない（ok: false・hash ""・diff null・理由「差分が空」）。0 バイトの差分を「修正なし」として置かない
  - 元: works/dev/lib.sh:608-612（空なら書かず、前の同名の差分を消し、取り込みの行も出さない）
  - 今: 表
  - 証: tests/workflows/test_merge.py::SealTest.test_empty_diff_is_null・筋書き workflows/merge/fixtures/empty-diff.stubs.yaml（形だけ）
  - 本物の run: 筋書きでのみ（種の run は直しが入る）
  - 狭め: 無し

- M6 緑の認証の指紋（test-gate final の {head, diff_hash}）が在って今の木と違えば、封じは ok: false と理由を返す（差分は置き場に書く）。指紋が無ければ照らさない
  - 元: 今の works の取り込みには無い（新しい強め。指紋の考えは works の test-gate の緑の認証）
  - 今: 表
  - 証: tests/workflows/test_merge.py::SealTest.test_changed_fingerprint_refuses_but_writes・lib/tests/test_seal.py::SealRefusalCase・lib/tests/test_green_cert.py::MatchesCase
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば `merge-seal.output.ok == true`・`reason == ""`（test-gate final の後に木が動いていない））
  - 狭め: 無し（計画の「今の木の指紋が取れない」の補足文は出なくなった。拒む事は同じ。PR #66 の「計画からのずれ」）

- M7 封じた差分の守りのパスの当たりを、置く差分のバイトそのもの（`git apply --numstat -z`）から数え、1 行ずつ「<パス>（+足した −消した）: 規則 <id>（<glob>）——<理由>」で返す
  - 元: works/.shared/core/protect.py:146-173 `touched`・`lines`（line_edge._protected が呼ぶ）
  - 今: 表
  - 証: tests/workflows/test_merge.py::SealTest.test_protected_hit_is_named・tests/workflows/test_merge.py::SealTest.test_index_marks_do_not_hide_a_protected_hit（「（+1 −1）」を照らす）・lib/tests/test_protect.py::TouchedCase.test_lines_name_file_stat_and_rule
  - 本物の run: 筋書きでのみ（種は守りのパスに当たらない。在れば `merge-seal.output.protected_hits`（種では `[]`））
  - 狭め: 無し

- M8 assume-unchanged・skip-worktree の印の付いた守りのファイルの変更も当たりとして数える（本物の index を通さない）
  - 元: 無し（元の protect.touched は印に目が届かなかった。PR #66 の discovery）
  - 今: 表
  - 証: tests/workflows/test_merge.py::SealTest.test_index_marks_do_not_hide_a_protected_hit
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（新しい強め）

- M9 利用者の git の設定 `apply.whitespace=error` で当たりを数える口が落ちない
  - 元: 無し
  - 今: 表
  - 証: lib/tests/test_seal.py::DiffFilesCase.test_user_whitespace_setting_does_not_break_the_count
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M10 バイナリのファイルは行数を数えず「行数なし（バイナリ・フォルダ）」と書く
  - 元: works/.shared/core/protect.py:167-173 `lines`
  - 今: 表
  - 証: lib/tests/test_seal.py::DiffFilesCase.test_counts_lines_and_binary（数の側）・lib/tests/test_protect.py::TouchedCase.test_lines_say_no_count_for_binary（文の側）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M11 守りの一覧が読めない・形が崩れている時は黙って空にせず、「守りのパスを確かめられない（差分が一覧に触れていないとは言えない）: <理由>」の 1 行を当たりとして返す（fail closed）
  - 元: works/darkfactory/lib/line_edge.py:651・670-675 `_protected_text`（PROTECTED_UNKNOWN）・works/tests/test_edge.py::ProtectedGateCase.test_broken_manifest_forces_gate
  - 今: 表
  - 証: tests/workflows/test_merge.py::SealTest.test_broken_manifest_is_an_unknown_hit_and_blocks_apply_without_answer・lib/tests/test_seal.py::UnknownRowCase.test_row_says_the_diff_may_touch_the_list
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M12 封じる差分が `git apply --numstat` で読めない時も、確かめられない行を当たりとして返す（ValueError の道）
  - 元: works/darkfactory/lib/line_edge.py:651（読めなければ理由で確かめられない扱い）
  - 今: 表
  - 証: lib/tests/test_seal.py::DiffFilesCase.test_unreadable_diff_is_value_error（lib の側）・tests/workflows/test_merge.py::SealTest.test_uncountable_diff_is_an_unknown_hit（偽の git で workflows/merge/scripts/merge.py が確かめられない行に変え、答え無しの apply が拒む）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M13 守りの一覧は run の作業ツリーでなく、走っている pack（WORKS_FACTORY_ROOT の lib/）から読む（修正役が作業ツリーの一覧を空にしても確かめは緩まない）
  - 元: works/.shared/core/protect.py:8（MANIFEST は pack の物）
  - 今: 表
  - 証: tests/shared/test_boundary.py::LibRootTest.test_lib_root_follows_works_factory_root・tests/workflows/test_merge.py::SealTest.test_broken_manifest_is_an_unknown_hit_and_blocks_apply_without_answer（root を差し替えて、cwd の木に無い一覧を読む）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

### B. 置く（merge-apply）の決まり

- M14 apply は始めに前の `merge/apply.diff` を消し、置くと決めた時だけ書く（同じ run のやり直しが拒んだ時、古い置いた差分が残らない）
  - 元: works/dev/use.sh:967-969（書き直せなければ前の差分を当てない）
  - 今: 表
  - 証: tests/workflows/test_merge.py::ApplyTest.test_refused_retry_removes_the_earlier_apply
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M15 拒む理由 1: 封じた hash が無い（seal が走っていない）
  - 元: works/dev/use.sh:969（差分が空か書けていなければ当てない）
  - 今: 表
  - 証: lib/tests/test_seal.py::ApplyRefusalOrderCase.test_1_no_sealed_hash
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M16 拒む理由 2: 今組み直した差分の hash が封じた hash と違う（封じた後に作業ツリーが動いた）。理由に両方の hash を書く。拒んだ差分は `merge/refused.diff` に置き、その hash を返す
  - 元: 無し（今の works は当てる時に差分を組み直すだけで、封じた物と照らさなかった。新しい強め）
  - 今: 表
  - 証: lib/tests/test_seal.py::ApplyRefusalOrderCase.test_2_hash_mismatch・lib/tests/test_seal.py::ApplyRefusalOrderCase.test_2_names_both_hashes・tests/workflows/test_merge.py::ApplyTest.test_tree_changed_after_seal_refuses
  - 本物の run: 筋書きでのみ（種の run では `merge-apply.output.hash == merge-seal.output.hash`）
  - 狭め: 無し

- M17 拒む理由 3: 最後の関所の答えが通す語（approve・continue）でない。stop・reject も知らない語も答えの語なしも「最後の関所で <語> と答えた」で拒む
  - 元: works/.shared/core/report.py:172・648-667 `stopped_run`（FINAL_GATE_STOPS）・works/dev/use.sh:409-426
  - 今: 表
  - 証: lib/tests/test_seal.py::ApplyAnswerCase.test_non_pass_words_refuse・lib/tests/test_seal.py::ApplyRefusalOrderCase.test_3_stop_answer・tests/workflows/test_merge.py::ApplyTest.test_stop_answer_refuses
  - 本物の run: 筋書きでのみ（本物の run では答えを continue にする。stop にすれば `merge-apply` は飛ぶ）
  - 狭め: 無し

- M18 答えの文が `request:` で始まる止める語は「止め札」と書き分ける
  - 元: works/.shared/core/report.py:173・639-640（止め札は盤面の state.stop.by の頭 `request:`）
  - 今: 表
  - 証: lib/tests/test_seal.py::ApplyAnswerCase.test_request_stop_card_refuses
  - 本物の run: 筋書きでのみ
  - 狭め: 元の止め札は「人が走っている run に置く札」（state.stop.by）で、関所の答えの文ではない。今の書き分けは関所の答えの文の頭を見るだけで、run の途中に置く止め札そのものは M の範囲に無い（止め札で止めた run は `merge-apply` が飛ぶので、置かない事は M38 で保たれる）。持ち主へ: 止め札の口をどこが持つかを線の範囲で確かめる 決め: 止め札は持ち込まない（stop-at-gates）（線の配線の文書の「この文書の外」の「決めた物」）

- M19 拒む理由 4: R2 が作り直し（redesign-needed）と言った run は、人が通しの答えを返しても置かない（部分を取り込まない）
  - 元: 今の works の use.sh apply には無い（持ち主の決め small-core から来た新しい強め）
  - 今: 表
  - 証: lib/tests/test_seal.py::ApplyRefusalOrderCase.test_4_r2_redesign_even_with_pass・lib/tests/test_seal.py::ApplyR2Case.test_r2_shapes・tests/workflows/test_merge.py::ApplyTest.test_redesign_r2_with_continue_refuses
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば `eyes.output.r2.status`（種の run では pass の見込み）と `merge-apply.output.ok`）
  - 狭め: 無し

- M20 拒む理由の順は上から 1→5 で最初の 1 つ（hash の食い違いは答えより先、答えは R2 より先）
  - 元: works/dev/use.sh:396-433（消す行 → 止まり → --check の順）
  - 今: 表
  - 証: lib/tests/test_seal.py::ApplyRefusalOrderCase.test_order_hash_before_answer・lib/tests/test_seal.py::ApplyRefusalOrderCase.test_order_answer_before_r2
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M21 拒む理由 5: 関所が開かず答えが無いのに、緑でない・目が通していない・緑の認証の指紋が今の木と違う、のどれかが在れば、在る物を全部「・」でつないで拒む
  - 元: 今の works の use.sh apply には無い（新しい強め。元は止まりの記録だけを見た）
  - 今: 表
  - 証: lib/tests/test_seal.py::ApplyNoAnswerCase.test_each_unchecked_fact_refuses・lib/tests/test_seal.py::ApplyRefusalOrderCase.test_5_no_answer_and_red・tests/workflows/test_merge.py::ApplyTest.test_no_answer_and_clean_run_applies_only_when_every_check_passed・tests/workflows/test_merge.py::ApplyTest.test_no_answer_and_red_refuses
  - 本物の run: 筋書きでのみ（本物の run は関所がいつも開く）
  - 狭め: 無し

- M22 拒む理由 5 の守りのパス: 答えが無いのに当たりが在れば「守りのパスに当たった（N 行）」、確かめられない行は「守りのパスを確かめられない」と書き分けて、どちらも拒む（通すのは人の通しの答えだけ）
  - 元: works/darkfactory/lib/line_edge.py:1186-1191（守りのファイルを触ったのに最後の関所の答えが無い → 止める）・works/tests/test_edge.py::ProtectedGateCase.test_no_gate_answer_stops・test_final_skipped_still_stops
  - 今: 表
  - 証: lib/tests/test_seal.py::ApplyNoAnswerCase.test_hit_and_unknown_are_named_apart・lib/tests/test_seal.py::ApplyNoAnswerCase.test_unknown_protected_row_refuses_as_unverified_not_hit・tests/workflows/test_merge.py::ApplyTest.test_no_answer_and_protected_hit_refuses
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M23 答えが通す語なら、赤でも・目の阻害でも・指紋が違っても・守りのパスに当たっても置く（人の通しが勝つ。superset）。R2 の unverifiable も人の答えに任せる
  - 元: works/dev/use.sh:396-433（止まりでなければ赤でも当てた）・works/tests/test_edge.py::ProtectedGateCase.test_continue_passes_and_marks_row
  - 今: 表
  - 証: lib/tests/test_seal.py::ApplyAnswerCase.test_pass_words_apply_even_when_red_or_eyes_blocked・tests/workflows/test_merge.py::ApplyTest.test_unverifiable_r2_with_approve_applies
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば `gates/gate-final.json` の decision と `merge-apply.output.ok == true`）
  - 狭め: 無し

- M24 置くと決めた差分は `merge/apply.diff` に書いて読み戻し、hash は封じた hash と同じ。merge は対象のリポジトリにも run の作業ツリーにも当てない（当てるのは人）
  - 元: works/dev/use.sh:950-971（run の差分は家の diffs/run-<id>.diff に書き、人が apply で当てた）
  - 今: 表
  - 証: tests/workflows/test_merge.py::ApplyTest.test_same_tree_applies_the_sealed_diff・tests/workflows/test_merge.py::ShapeTest.test_one_script_node・tests/workflows/test_merge.py::ScriptCase.run_script（全部の走りで作業ツリーの status が前後で同じ）
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば run の置き場の `merge/apply.diff` と `merge-apply.output.hash`）
  - 狭め: 無し

- M25 返す節は落ちない: 知らない mode・壊れた start・別の run の指し札・base_rev の無い記録・JSON でない answer/r2・lib が無い・git の木でない、のどれでも終了の値 0 で ok: false と理由を返す
  - 元: works/dev/use.sh:192-195 `refuse`（読める 1 行で止まる）
  - 今: 表
  - 証: tests/workflows/test_merge.py::NeverFailsTest（9 件）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

### C. 線の配線（最後の関所と merge）

- M26 守りのパスに当たった（確かめられなかった時も）run は、最後の関所を開き方（always・when_needed・protected_only）に関わらず開く
  - 元: works/darkfactory/lib/line_edge.py:34-35・788-794・880・works/tests/test_edge.py::ProtectedGateCase.test_touch_forces_gate_when_needed・test_protected_only_opens_just_for_protected_files
  - 今: 表
  - 証: tests/workflows/test_line.py::AskFinalCase.test_protected_hits_and_conflicts_open_in_every_mode
  - 本物の run: `ask-final.output.open == true`（種の run は always で開く。当たりで開く道は筋書きでのみ）
  - 狭め: 無し

- M27 守りのパスの当たりを冒頭 3 行の 1 行目で名指し（確かめられなかった時は別の語で）、2 行目の決めてほしいことで「守りのパスの変更は下の最初の節を確かめてから通す」と言う
  - 元: works/darkfactory/lib/line_edge.py（_final_head）・works/tests/test_gate_head.py::FinalHeadCase.test_protected_named_in_the_first_line・works/tests/test_edge.py::ProtectedGateCase.test_touch_named_in_three_lines_and_first_heading
  - 今: 表
  - 証: tests/workflows/test_gate_head.py::FinalHeadCase.test_protected_named_in_the_first_line
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M28 守りのパスの節を冒頭 3 行の直後の最初の見出しに置き、当たりの行（パス・行数・規則・理由）を全部並べる
  - 元: works/darkfactory/lib/line_edge.py:670-678 `_protected_text`・works/tests/test_edge.py::ProtectedGateCase.test_touch_forces_gate_when_needed（stats.py・+1 −・規則・理由を照らした）
  - 今: 表
  - 証: tests/workflows/test_gate_head.py::FinalHeadCase.test_final_edge_puts_the_head_before_the_sections・tests/workflows/test_gate_head.py::FinalHeadCase.test_protected_section_keeps_rule_and_count
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M29 守りのパスの節に、差分の見方（`git -C <作業ツリー> diff <起点> -- <パス>`）と一覧の置き場を書く
  - 元: works/darkfactory/lib/line_edge.py:676-678 `_protected_text`（「差分: git -C … diff <rev> -- <パス>（未追跡は新しいファイル）」「一覧: <MANIFEST>」）・確かめられない時は「理由」「一覧」の 2 行（:672-674）
  - 今: 表
  - 証: tests/workflows/test_gate_head.py::FinalSectionsCase.test_protected_section_says_how_to_see_the_diff
  - 本物の run: 筋書きでのみ
  - 狭め: #74 で狭めた → 部分 B2 で戻した

- M30 承認済みの案と裁定が書き換えを許したテストのファイル（許したテストの変更）を触った run も、守りのパスと同じに扱う: 関所を開き方に関わらず開き、答えが無ければ置かない
  - 元: works/darkfactory/lib/line_edge.py:640-651 `_protected`（`conflict.ruled_test_doc` を 2 つ目の一覧として `protect.touched` に通した）・works/.shared/core/conflict.py:983-1001 `ruled_test_doc`
  - 今: 表
  - 証: tests/workflows/test_line.py::AskFinalCase.test_allowed_test_changes_open_in_every_mode。lib/tests/test_seal.py の ApplyNoAnswerCase に test_allowed_test_change_refuses_without_answer は置かない（線が関所を必ず開き、開かなければ merge-apply が飛ぶので、merge-apply に渡す口を足さない道を採った）
  - 本物の run: 筋書きでのみ
  - 狭め: #74 で狭めた → 部分 B2 で戻した

- M31 無人の run（unattended）で守りのパスに当たり関所が開くはずなら、開かずに needs-human で止まり、merge-apply を飛ばす
  - 元: works/darkfactory/lib/line_edge.py:1186-1191（答えの無い守りの行で止める）
  - 今: 表
  - 証: tests/workflows/test_line.py::AskFinalCase.test_unattended_protected_hit_stops・tests/workflows/test_line.py::GateAnswerCase.test_skipped_gate_passes_the_decision_before_it・tests/workflows/test_line.py::AskFinalCase.test_unattended_stops_instead_of_opening（always の道）・筋書き workflows/line/fixtures/unattended-needs-human.stubs.yaml（tests/e2e/test_line_scenarios.py::LineScenariosTest.test_every_scenario_passes）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M32 最後の関所の文に封じた差分の hash を載せる（人は自分が通す差分を hash で名指せる）
  - 元: 無し（新しい強め。元の関所の文は差分の置き場を言った）
  - 今: 表
  - 証: tests/workflows/test_gate_head.py::FinalHeadCase.test_final_text_names_the_sealed_hash
  - 本物の run: `ask-final.output.text` の「封じた差分の hash:」の行が `merge-seal.output.hash` と同じ
  - 狭め: 無し

- M33 封じが ok でない（指紋の食い違い・差分が空）時は、最後の関所を開ける理由に「差分を封じられなかった（<訳>）」を入れる
  - 元: 無し（新しい強め）
  - 今: 表
  - 証: tests/workflows/test_line.py::AskFinalCase.test_unsealed_is_a_reason
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M34 merge-apply は関所の答えを受ける節の go が真の時だけ走る（stop・reject・needs-human の run は置かない）。merge-apply に関所の答え・封じた hash・R2・指紋・緑・目を渡す
  - 元: works/dev/use.sh:409-426（記録が止まりの run は当てない）
  - 今: 表
  - 証: 筋書き workflows/line/fixtures/final-stop.stubs.yaml（merge-apply の stub を持たず、走れば赤）と final-when-needed-green.stubs.yaml（reached に merge-apply__merge）を tests/e2e/test_line_scenarios.py::LineScenariosTest.test_every_scenario_passes が回す
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば `merge-apply` の節が completed（種の run は continue で通す））
  - 狭め: 無し

- M35 merge-seal・merge-apply が ok でない run は、報告で結末を stopped_by_line（<節>:not-ok）にし、止めの節に「<節> が ok でない: <理由>」を書く。守りのパスの当たりは報告の冒頭に数える
  - 元: works/.shared/core/report.py（守りの行は process.human_items から報告の冒頭 1）・works/darkfactory/lib/line_edge.py:741-761 `_record_protected`
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_protected_hits_from_eyes_and_merge_reason・lib/tests/test_runreport.py::LinesCase.test_seal_not_ok_says_why
  - 本物の run: 報告の止めの節（種の run では ok でない行が出ない）
  - 狭め: 無し

- M36 報告の置き場の節に、封じた差分と置いた差分の指し札を並べる
  - 元: works/dev/lib.sh:614（「修正の差分（…）: <パス>」）
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_where_lists_sealed_and_applied_diff
  - 本物の run: 報告の置き場の節の 2 行
  - 狭め: 無し

- M37 報告（か run の終わりの案内）に、差分を対象へ当てる 1 行（`bin/apply <run-id>`）を出す。記録が止まりの run には生の `git apply` の行を出さず、止まりの 1 行（結末の語・止めた人・一言）を出す
  - 元: works/dev/lib.sh:633-644（止まった run の 1 行・殻で取り込む行・止まり/判定不能の run には生の git apply を出さない）・works/tests/test_use.py::UseShell.test_show_hides_raw_apply_for_stopped_or_unjudgeable_run（assert: test_use.py:1419-1420）
  - 今: 表
  - 証: lib/tests/test_runreport.py::LinesCase.test_apply_line_names_bin_apply
  - 本物の run: 報告の「当てる」の行
  - 狭め: 不可でない（報告は run_id と merge の返りを持つ）→ 戻す（段 1 で `bin/apply` と一緒に足す） → 部分 C で戻した

- M38 差分の中で消えるファイルを、当てる前に 1 本ずつ名指す（「取り込むと消えるファイル: <パス>」）
  - 元: works/dev/lib.sh:595-597・622-623（`diff --cached --diff-filter=D --name-only`）
  - 今: 表
  - 証: tests/workflows/test_line.py::AskFinalReadsCase.test_deleted_files_named（前の lib/tests/test_runreport.py の LinesCase.test_deleted_files_named を最後の関所の側へ移した） ・lib/tests/test_runreport.py::LinesCase.test_tests_head_lines_and_deleted_files（報告）
  - 本物の run: 筋書きでのみ（種の直しは消さない）
  - 狭め: 不可でない → 戻す → 部分 B2 で戻した（最後の関所）。報告の置き場の節は部分 C

### D. 対象へ当てる（bin/apply。今の works の use.sh apply の後継）

- M39 run の差分を対象のリポジトリへ当て、commit しない。当てたファイルと「commit はしていない。テストを回してから commit する」を出して 0 で終わる
  - 元: works/dev/use.sh:432-433 `apply_checked`・works/tests/test_use.py::UseShell.test_apply_brings_run_diff_into_target（assert: test_use.py:1577-1579）
  - 今: 表
  - 証: tests/bin/test_apply.py::ApplyTest.test_apply_applies_sealed_diff
  - 本物の run: 段 1 の手順（計画 :166-167）: 当てる前に種の `python3 -m unittest` が 2 件落ち、`bin/apply <run> --cwd <target>` の後に全部通る
  - 狭め: 無し

- M40 当てる差分は、関所を通った run なら `merge/apply.diff`（記録の apply.hash が sealed.hash と同じ時だけ）。ファイルの sha256 を Archon の DB の記録の hash と照らし、違えば両方の hash を言って止まり対象を変えない（古い・書き換えた差分を当てない）
  - 元: works/dev/use.sh:964-969（当てる前に差分を書き直し、書き直せなければ「前の差分は当てない」で拒む）・works/tests/test_use.py::UseShell.test_apply_refuses_when_diff_rewrite_fails（assert: test_use.py:1729-1731）
  - 今: 表
  - 証: tests/bin/test_apply.py::ApplyTest.test_apply_refuses_changed_diff・tests/bin/test_apply.py::ApplyTest.test_apply_refuses_apply_hash_not_sealed
  - 本物の run: 段 1 の手順（計画 :166）: `merge/apply.diff` を 1 バイト変えて `bin/apply` が 1 で止まり対象が変わらない
  - 狭め: 無し（元より強い）

- M41 run の作業ツリーを片付けた後でも、置き場の差分から当てられる
  - 元: works/tests/test_use.py::UseShell.test_wait_completed_cleans_worktree_and_branch_after_diff_written（assert: test_use.py:1690-1693）
  - 今: 表
  - 証: tests/bin/test_apply.py::ApplyTest.test_apply_does_not_need_the_run_worktree
  - 本物の run: 段 1 の手順で、run の後に作業ツリーを消してから `bin/apply` を打つ（任意の確かめ）
  - 狭め: 無し

- M42 差分が対象のファイルを消すなら、許しが無い限り消すファイルを並べて止まり、許し方（今: `WORKS_USE_ALLOW_DELETE=1`、段 1: `--allow-delete`）を言う。許せば当てる
  - 元: works/dev/use.sh:401-404・works/tests/test_use.py::ChainShell.test_apply_show_clean_chain_id（assert: test_use.py:2439-2443）
  - 今: 表
  - 証: tests/bin/test_apply.py::ApplyTest.test_apply_refuses_delete_unless_allowed
  - 本物の run: 筋書きでのみ（種の直しは消さない）
  - 狭め: 無し（環境変数から旗へ。PR に名指す約束の変更）

- M43 記録が止まりを示す run（関所で stop・reject、止め札、線の止め、needs-human）の差分は、許しが無ければ当てずに 1 行で止まり、止まった訳（結末の語・止めた所・人の一言）と許し方を言う
  - 元: works/dev/use.sh:409-426・works/.shared/core/report.py:648-667 `stopped_run`・works/tests/test_use.py::UseShell.test_apply_refuses_run_stopped_by_record（assert: test_use.py:1608-1613。1 行・人の一言・許しの名・対象が変わらない）
  - 今: 表
  - 証: tests/bin/test_apply.py::ApplyTest.test_apply_stopped_run_needs_flag（旗なしの 1 行に結末の語・止めた所・人の一言・「--allow-stopped」、対象が変わらない）
  - 本物の run: 筋書きでのみ（種の run は continue で通す）。ただし段 1 で stop を答えた run を 1 本足せば `result` の `apply == null` が見える
  - 狭め: 計画は人の一言を言わない（結末の語だけ）。Archon で不可でない（`answer-final.output.answer.text` は collect に届く: works-factory-line.yaml:950）→ 戻す 決め: 戻すと決めた（superset）。#101（線の配線の文書の「この文書の外」の「決めた物」） → #114 で戻した

- M44 許し（今: `WORKS_USE_ALLOW_STOPPED=1`、段 1: `--allow-stopped`）が在れば止まった run の封じた差分を当て、止まった訳と「許しが在るので当てる」を 1 行出す。ただし R2 が作り直しと言った run は許しが在っても当てない
  - 元: works/dev/use.sh:427・works/tests/test_use.py::UseShell.test_apply_refuses_run_stopped_by_record（assert: test_use.py:1615-1618）
  - 今: 表
  - 証: tests/bin/test_apply.py::ApplyTest.test_apply_stopped_run_needs_flag・tests/bin/test_apply.py::ApplyTest.test_apply_stopped_run_refuses_redesign
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（R2 の拒みは新しい強め）

- M45 止まりかを記録で言えない run（止まりの記録が無い・読めない）は、今の works では 1 行で「確かめられなかった」と言って当てた
  - 元: works/dev/use.sh:414-416・429・works/tests/test_use.py::UseShell.test_apply_refuses_run_stopped_by_record（unknown の枝。assert: test_use.py:1634-1636）
  - 今: 表
  - 証: tests/bin/test_apply.py::ApplyTest.test_apply_refuses_unreadable_run
  - 本物の run: 筋書きでのみ
  - 狭め: 段 1 の計画で狭める予定。Archon で一部は強いられる（ブロックの節の出力は `workflow get --verbose` で 200 字に切られる: …/archon/d97d00ef…/packages/cli/src/commands/workflow.ts:3932-3934 `outputPreviewOf`。だから hash は線の `result` から読むしかない）。しかし「記録の無い run を当てない」こと自体は不可でない（作業ツリーから組み直して当てる道は残せる）→ 持ち主の確かめ待ち 決め: bin/apply は拒み、拒む 1 行に差分のパスと素の git apply の道を書いて能力を残す（新しい旗は足さない）。#101（線の配線の文書の「この文書の外」の「決めた物」）

- M46 封じていない差分（merge-seal より前で止まった run）は当てない
  - 元: works/dev/use.sh:950-971（止まりの許しが在れば、どこで止まった run の作業ツリーの差分でも当てた）
  - 今: 表
  - 証: tests/bin/test_apply.py::ApplyTest.test_apply_refuses_when_nothing_placed
  - 本物の run: 筋書きでのみ
  - 狭め: 段 1 の計画で狭める予定（README の約束「関所を通らなかった物は取り込まない」から）。Archon で不可でない → 持ち主の確かめ待ち 決め: 能力の狭めに当たる（元は許しが在れば止まった run の作業ツリーの差分を当てた: works/dev/use.sh:950-971）。拒む 1 行に作業ツリーと git -C <wt> diff <基> | git apply の道を書いて残す。R2 の作り直しには書かない。#101（線の配線の文書の「この文書の外」の「決めた物」）

- M47 `git apply --check` が通らなければ当てずに止まり、「対象の手元の変更とぶつかっていないかを見る」と言う（対象は変えない）
  - 元: works/dev/use.sh:431
  - 今: 表
  - 証: tests/bin/test_apply.py::ApplyTest.test_apply_refuses_when_check_fails
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M48 当てた後に `git apply -R --check` で、当てた物が対象に在ることを読み戻す。通らなければ「当てたが読み戻せない」
  - 元: 無し（新しい強め）
  - 今: 表
  - 証: tests/bin/test_apply.py::ApplyTest.test_apply_refuses_when_readback_fails・tests/bin/test_apply.py::ApplyTest.test_apply_applies_sealed_diff
  - 本物の run: 段 1 の手順の `bin/apply` の終了の値 0
  - 狭め: 無し

- M49 拒む時はどれも読める 1 行で、0 でない終了の値で止まり、対象の作業ツリーを変えない
  - 元: works/dev/use.sh:192-195 `refuse`（stderr に「use.sh: …」の 1 行・終了 2）・works/tests/test_use.py::UseShell.test_apply_refuses_run_stopped_by_record（assert: test_use.py:1609-1613）
  - 今: 表
  - 証: tests/bin/test_apply.py::ApplyTest.test_every_refusal_is_one_line_and_leaves_target
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（終了の値 2→1 は約束の変更として PR に名指す）

- M50 許しは 1 回の打ち込みだけに効き、後の周や後の呼び出しへ運ばれない（鎖の控えに WORKS_USE_ALLOW_DELETE・ALLOW_STOPPED を持たない。試験の殻もこの 2 つを消す）
  - 元: works/dev/use.sh:377-380 `chain_env_names`・works/tests/hermetic.sh:10
  - 今: 表
  - 証: tests/bin/test_apply.py::ApplyTest.test_apply_ignores_env_allowances
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M51 対象は打った所か `--cwd` の git の根で決め、同じ対象から殻と同じ家を引き、その対象の run だけを読む（別の対象の run id を渡しても見つけない）
  - 元: works/dev/use.sh:950-955（`cd "$TARGET"`・run_row）・works/tests/test_use.py::UseShell.test_wait_does_not_find_run_of_other_target（assert: test_use.py:1521-1522）
  - 今: 表
  - 証: tests/bin/test_apply.py::BinApplyTest.test_bin_apply_asks_launcher_for_get
  - 本物の run: 段 1 の手順の `bin/apply <run> --cwd <target>`
  - 狭め: 無し

- M52 指し札の run_id が記録の run と同じで、パスが置き場の下の普通のファイル（`..`・絶対パス・外へ出る symlink を拒む）
  - 元: 無し（新しい強め。今の works は家の diffs/ の決まった名を読んだ）
  - 今: 表
  - 証: tests/bin/test_apply.py::ApplyTest.test_apply_refuses_pointer_outside_root・tests/bin/test_apply.py::ApplyTest.test_apply_accepts_short_run_id
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M53 鎖（周を重ねる run）の id を渡せば、鎖が止まった時に書いた最後の差分 final.diff（元の基から、止まりと言われていない最後の周の結果まで）を同じ確かめで当てる。final.diff が無い・空なら別の文で拒む
  - 元: works/dev/use.sh:955-962・works/.shared/core/chain.py:210 `pick`・works/tests/test_use.py::ChainShell.test_apply_show_clean_chain_id（assert: test_use.py:2429-2452）・ChainShell.test_chain_round_result_on_start_base（assert: :2323-2325）・works/tests/test_chain.py::Pick.test_skips_stopped_last_round_and_names_it（assert: test_chain.py:195-198）
  - 今: 無し（表）
  - 証: 要追加（鎖を作る issue で）: tests/bin/test_apply.py::ChainApplyCase.test_chain_final_diff_goes_through_same_checks — 消す行・止まりの拒みが run の apply と同じに効き、final.diff の無い・空の時に別の文で拒む
  - 本物の run: 筋書きでのみ
  - 狭め: 段 1 の計画（:97）で外す予定。Archon で不可でない → 鎖の issue へ持ち越すことを持ち主が確かめる 決め: 段 3 の鎖の issue の受け入れに入れる（落とさない）（線の配線の文書の「この文書の外」の「決めた物」）

### E. 守りの一覧（protected.json と protect.py）

- M54 一覧のどの行も、このリポジトリで追跡しているファイルに 1 本以上当たる（古い行は赤）
  - 元: works/tests/test_protect.py::ManifestCase.test_every_rule_matches_a_tracked_file
  - 今: 表
  - 証: lib/tests/test_protect.py::ManifestCase.test_every_rule_matches_a_tracked_file
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M55 一覧の読みは git の `:(glob)` と同じ当たり方（** は 0 個以上のフォルダ、* ? [..] は / を跨がない。フォルダの名だけの行は赤）
  - 元: works/tests/test_protect.py::ManifestCase.test_match_agrees_with_git_glob・MatchCase.test_glob_words
  - 今: 表
  - 証: lib/tests/test_protect.py::ManifestCase.test_match_agrees_with_git_glob・lib/tests/test_protect.py::MatchCase.test_glob_words
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M56 一覧そのもの・確かめのモジュール・その試験は一覧に入る（行を消せば守りが黙って外れるのを防ぐ）
  - 元: works/tests/test_protect.py::ManifestCase.test_manifest_and_checker_are_protected
  - 今: 表
  - 証: lib/tests/test_protect.py::ManifestCase.test_manifest_and_checker_are_protected
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M57 赤と緑の判定（baseline_red・green_cert とその試験）は一覧に入る
  - 元: 無し（新しい行）
  - 今: 表
  - 証: lib/tests/test_protect.py::ManifestCase.test_red_and_green_judges_are_protected
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M58 ふつうの追跡ファイル（README・ふつうの lib・ふつうの試験）は守らない（広すぎる行を足すと赤）
  - 元: works/tests/test_protect.py::ManifestCase.test_ordinary_files_are_not_protected
  - 今: 表
  - 証: lib/tests/test_protect.py::ManifestCase.test_ordinary_files_are_not_protected
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M59 形の崩れた一覧（JSON でない・rules が無い・空・id や glob の重なり・理由の無い行・絶対パス・..・末尾の /・知らない鍵・copies の made_by が無い）は読み込みで拒む
  - 元: works/tests/test_protect.py::ShapeCase.test_bad_shapes_refused
  - 今: 表
  - 証: lib/tests/test_protect.py::ShapeCase.test_bad_shapes_refused・lib/tests/test_protect.py::ShapeCase.test_good_shape_loads
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- M60 run の差分の確かめ（touched）は、数える版からの変更・消した物・未追跡・commit した物を拾い、行数と当たった行を返す（独立の目の `protected` の節が使う）
  - 元: works/tests/test_protect.py::TouchedCase
  - 今: 表
  - 証: lib/tests/test_protect.py::TouchedCase.test_changed_deleted_untracked_committed・lib/tests/test_protect.py::TouchedCase.test_untouched_is_empty・lib/tests/test_protect.py::TouchedCase.test_default_manifest_used
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば run の置き場の `eyes/protected.json`（種では hits が空））
  - 狭め: 無し

- M61 持ち主が名指した守り（各ブロックの受け付けの節・ブロックの YAML・線の YAML と境の口・修正役の TDD の輪とその試験・修正役が木を変えたかの確かめ・試験の枠 tree_run・役の隔離の包みとその試験・写しの照らしの試験）が一覧に当たる
  - 元: works/.shared/core/protected.json の行 line-wiring・node-table・block-accept・block-yaml・fix-tdd・fix-changed・fix-tdd-test・test-slot・adapter・adapter-bin・adapter-ticket・adapter-reads・adapter-test・adapter-test-data・ticket-test・copy-test・copy-verbatim-test・accept-golden(-test)・entry-test・test-floor(-check)・downgrades・stop-flag(-test)・validator-copy（元 44 行 → 今 19 行）・works/tests/test_protect.py::ManifestCase.test_named_guards_are_protected
  - 今: 無し（表）
  - 証: 要追加: lib/tests/test_protect.py::ManifestCase.test_named_guards_are_protected — 上の works-factory のパス（と線の後は `workflows/line/works-factory-line.yaml`・`workflows/.shared/boundary.py`）が追跡ファイルに在り、`protect.hits` が空でない
  - 本物の run: 筋書きでのみ（自分食いの run でだけ当たる）
  - 狭め: prereq の lib の移し（「当たる物が無い行は外す」。その時はファイルが無かった）と #74 で狭めた。今はファイルが在るので、Archon で不可でない → 戻す

- M62 run の作業ツリーの中の pack の写しを守る行（copies の pack-copy と、その made_by の殻が置き場の字を書いているかの試験）
  - 元: works/.shared/core/protected.json の copies・works/tests/test_protect.py::ManifestCase.test_copies_are_made_where_named・works/dev/lib.sh（対象に pack の写しが在り修正が .archon/ に触れていれば取り込まないよう注意する 1 行）
  - 今: 無し（表）
  - 証: 置き換えで要らない（写しが作業ツリーに無い）。形の照らしは lib/tests/test_protect.py::ShapeCase.test_bad_shapes_refused の「copies の made_by が無い」が残る
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（守る物そのものが無くなった置き換え）

- M63 独立の目の守りのパスの数え方と merge の数え方が同じ（index の印の付いた守りのファイルを目の側も見落とさない）
  - 元: works/darkfactory/lib/line_edge.py:640-651（1 か所の `_protected` を最後の関所と報告が共に使った）
  - 今: 表
  - 証: 要追加: lib/tests/test_protect.py::TouchedCase.test_index_marks_do_not_hide_a_hit — `git update-index --assume-unchanged`・`--skip-worktree` を付けた守りのファイルを書き換えても `touched` が当たりを返す
  - 本物の run: 筋書きでのみ
  - 狭め: 今壊れているのではなく、壊れる余地（PR #66 が「前提の部品の直しの頼み」で持ち主に上げ、まだ直っていない）。不可でない → 戻す

### M の穴

数:
- 行の総数: 63
- 今: 無し: 3（M53・M61・M62）。M53 は周の鎖と一緒に段 3 で作る行で、M62 は置き換えで要らない行。bin/apply の M39〜M52 は #114 で入り、M29・M30・M37・M38 は線の配線の部分 B2・C で戻した
- 証が要追加か弱い: 3（M53・M61・M63）。M10・M12・M16・M28・M31・M32・M33・M36 は issue #125 で試験を足して閉じ、M39〜M52 は #114 の tests/bin/test_apply.py が縛る
- 狭めたのに Archon が強いていない: 2（M61・M63）。M29・M30・M37・M38 は線の配線の部分 B2・C で、M43 は #114 で戻した

持ち主に確かめてほしい物:
1. →決めた（線の配線の文書の「決めた物」）: M45・M46 は拒む 1 行に素の `git apply` の道を書いて能力を残し、M53 は段 3 の鎖の issue へ。元の問い: 段 1 の計画が `bin/apply` で狭める 3 点は、どれも Archon が強いていない。止まりかを言えない run を当てない（M45。Archon が強いるのは「hash は線の result から読む」までで、cli/src/commands/workflow.ts:3932-3934）、封じる前に止まった run の差分を当てない（M46）、鎖の最後の差分を当てる口を持たない（M53）。3 つとも計画のまま狭めてよいか。
2. 止まった run を拒む文に人の一言を載せるか（M43）。今の works は載せていた。計画は結末の語だけ。→ 決めた: 載せる（superset）
3. 守りの一覧が 44 行から 19 行に減った（M61）。今は main にファイルが在るのに外れている行を戻すか。線の PR #74 は `workflows/line/**` の行を足していない。
4. →戻した（線の配線の部分 B2）: 許したテストの変更を守りのパスと同じに扱う（関所を必ず開き、答えが無ければ置かない）こと（M30）。元の問い: 線で落ちているのを戻すか。
5. lib/seal.py の「止め札」の書き分け（M18）は関所の答えの文の頭を見るだけで、元の止め札（走っている run に置く札）とは別物。→ 決めた: 元の止め札は持ち込まない（持ち主の決め `stop-at-gates`）

## 穴の要約

数（4 つの領域の合計。各領域の内訳は各領域の終わりの節。数え方は README.md の「穴の数え方」）:
- 行の総数: 294（T 71・E 77・R 83〔R1〜R82 と R5b〕・M 63）
- 今: 無し: 9（T 2・E 2・R 2・M 3）。M の 3 のうち 1 は周の鎖と一緒に段 3 で作る bin/apply の行（M53。M39〜M52 は #114 で bin/_lib/apply.py と tests/bin/test_apply.py に入った）、1 は置き換えで要らない行（M62）
- 証が要追加か弱い: 11（T 2・E 1・R 5・M 3）
- 狭めたのに Archon が強いていない: 14（T 2・E 5・R 5・M 2）。どの PR も書かずに黙って落とした物のうち、まだ戻していないのは E67（T35・T41・T45・T47・T70、R5b・R14・R16・R20・R23・R24・R35〜R39・R41・R49 は戻した）
- Archon が強いた狭め: 1（E30。読むだけの役が作業ツリーを変えた時の出し直しが無くなった。dag-executor.ts:1243-1249 で、checkout の照らしの違反は retry の外）
- PR の対応表の照らし: #66（M）・#67（E）・#69（T）が挙げた試験は main に全部在り、該当の動きを assert していた。#68 の「取り戻せない」12 件のうち、今も読む先が無いのは gates_deferred（R71）と来歴の表（R81 の表の部分）だけ。閉鎖の数え直し（R72）は組の子 run に元データが在り、約束に足せば戻る。R73〜R80 の 8 件は今の置き場から戻せ、うち R75・R76・R79・R80 の 4 件は #68 の主張が誤り。R71・R81・R82 は持ち主に聞く

今壊れている物と、壊れる余地だけの物:
- 今壊れている: 書いた時に挙げた E17・E37・E42・E45・E66・E73（x_scalars・前提の検算の key と facts_to_add・premise_drift_note・eyes/premise-inputs.json・eyes/gate-passes.json・最後の関所の実測の行が、fix の返り・線・最後の関所・報告のどこにも届かなかった）と R5b・R16・R23（結末の語か「人が決めること」の件数が変わった）は、線の配線の部分 B2・C・D1・D2 で戻した（各行の狭めの欄）
- 壊れる余地だけ: 書いた時に挙げた E43（再審の後、judgment の指し札の隣に premises.json が無い道）は #123 で閉じた

持ち主に聞く物（前の決め・定石・元の作りのどれでも 1 つに決まらない物）:
1. T62〜T64 同じ run の中の試験の結果の使い回しと、機械全体の試験の枠。→ 決めた: T62・T63 は戻す（reuse-results）。T64 は戻さない（`no-queue`。#118）
2. T49 任せ先の CI の役の書き込みの守り → 決めた: 戻す（塞げないと実測で分かった時だけ狭め）
3. T16 依頼の where を範囲の照らしに足すか → 決めた: 戻す。T61 人に諮っている間の CI の欄を clean で上書きさせない決まりの住処。T69 直す前に試験を走らせられない run を人に聞いて続けるか。T8・T9 宣言の sha の照合と engine の素材の受け付け
4. E16 コードとコメントの比を戻すか（#67 は言語依存を理由に外した）→ 決めた: 戻さない（`no-comment-ratio`。#118）。E29 型に外れた返りを、拒んだ理由つきで同じ会話に出し直させる元の形を戻すか（元は同じ Archon の loop_group でしていた）。E19 規模の数値の推移を run をまたいで運ぶか。E48 軽い run で省いた目の理由をどこに残すか。E67 方針の文書の変化を修正の後に聞く仕組みの住処
5. R2 と M18 止め札（走っている run を関所の間で止める口）が無い。→ 決めた: 持ち込まない（持ち主の決め `stop-at-gates`）
6. R46・R38 の一部 読んだ証拠・包み・仕組みの異常（docs/design.md の U6。→ 読んだ証拠は #354 で戻した）。R71 gates_deferred と変異の検算。R82 受け止めた落ちの決め方を元の宣言の形に戻すか（→ 決めた: 戻す。線の配線の部分 C）。R71 は段 3 で変異の検算と一緒に聞く。R81 来歴に線の版を足すか（→ 決めた: 報告の側は #124 で入れた。線の側の start.py は持ち主の手に渡した）
7. 黙って落ちた報告の行（R5b・R14・R16・R20・R23・R24・R35〜R39・R41・R49）を、線の issue と報告の直しのどちらで戻すか → 決めた: 線の配線の文書が割り当てた（R5b・R14・R20・R24・R35・R36・R41 は部分 C、R16・R23・R37〜R39 は部分 D2、R49 は区分 R の issue）
8. M45・M46・M53・M43 → 決めた: M45・M46 は `bin/apply` が拒み、拒む 1 行に素の `git apply` の道を書いて能力を残す（M46 は元の能力の狭めに当たる）。M53 は段 3 の鎖の issue。M43 は人の一言を載せる
9. M61 守りのパスの一覧が 44 行から 19 行に減った（main にファイルが在るのに外れた行がある。#74 も線の行を足していない）。M30 書き換えを許したテストを守りのパスと同じに扱う動き（関所を必ず開く・答えが無ければ置かない）→ 戻した（線の配線の部分 B2）

聞かずに戻す物（どの PR も挙げずに黙って落ちた物。Archon の制約ではない）のうち、まだ戻していないのは E67（住処だけ持ち主に聞く）。T35・T41・T45・T47・T70（test_cmd が手元の clone を指していないかの入口の確かめ。#495）、E の 7 行（E17・E37・E42・E45・E66・E73・E74）、R の 21 行（R の穴の「戻す」の一覧）、M29・M37・M38 は戻した。

本物の run の注意: 種に .review-checks.json が無いので、試験の関門の engine の段・JUnit・赤の原因の分け（元から赤か、この直しで赤か）・範囲の宣言は、種のままでは本物の run に出ない。段 1 で見るなら、種に宣言を足すか、test_cmd を渡す run と渡さない run を 1 本ずつ回す（T の穴の節）。種は works-factory でない対象なので、守りのパスに当たる道も筋書きでのみ。
