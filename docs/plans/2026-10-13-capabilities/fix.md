# 修正のブロック（fix）の能力の棚卸し（ID の頭 F）

- 元 = raiki61/claude-plugins @ 2aa7c66c の works/（行の番号はその版）。証 = works-factory の main の名（指しの形は README.md の「指しの形」）。「今」は印（「表」か「無し（表）」、住処を書かなかった行は「無し」か空）だけを持ち、住処の字は docs/works-parity.md の「前の棚卸しの今」が持つ。
- 節: A（F001〜）TDD の輪と事後の関門、B（F100〜）修正役と修正の受け付け、C（F200〜）食い違いの申し出・裁定・範囲の相談・人の関所の答え、D（F300〜）差分の審査・レンズ・手直し、E（F400〜）組の並べ・後始末・変更の確かめ・返りの約束と人に届く物。
- 「本物の run」の置き場: 親の run の成果物の置き場の `fix/fix/`（2 回目の修正の include は `fix/refix-run/`）、組の子の run は子の run の成果物の置き場の `fix/fix/` と、親の置き場の `<out_dir>/<group_id>/result.json`。種 tests/e2e/target-seed は実行器（tdd_suite）を持たないので、TDD の輪の行（A）は実行器を種に足して渡さない限り本物の run では見えない（A の頭の注）。
- 持ち主に要る判断は末尾の「穴の要約」の「持ち主へ」にまとめた。

## A. TDD の輪と事後の関門（F001〜）

前提（この節の「本物の run」の読み方）:
- 組の子は Archon の `workflow:` で起きる別の run なので、子の置き場は「子の run の artifacts/fix/fix/」。子の TDD の輪の状態はそこの `tdd-1/`（`state.json`・`next.md`・`summary.md`・`junit-<n>.xml`・`suite-<n>.log`・`test-cmd-0.log`）、確かめの拒否の文は `tdd-step-reject-<n>.md`、輪の頭の返りは `tdd-start.json`。
- 親の置き場は `<run artifacts>/fix/fix/`（2 回目の include は `fix/refix-run/`）。join が子の輪の状態を `tdd-<k>/state.json` に写し（欄 `adopted_from`）、`tdd-unit` 節が `tdd-unit.json` と型つきの成果物 `tdd-unit` を出す。組の結果は `<prep の out_dir>/<group_id>/result.json` の `tdd`。
- TDD の輪が回るのは、線の入力 `tdd_suite`（JUnit XML を第 1 引数に書く実行器。#74 の head `workflows/line/scripts/start.py:50`）を渡した run だけ。種 `tests/e2e/target-seed/` は実行器を持たないので、本物の run の仕様は実行器を種に足して渡す前提で書く（足さなければ下の行の殆どは観察できない）。種の `test_stats.py` は修正前から赤のテスト（`test_mean_of_three` ほか）を持つので、元から赤の区別は健全な run で観察できる。

- F001 赤の判定を機械が JUnit XML で行う: 名指しのテストが failure で落ちた時だけ赤とし、error・一式に居ない・もう通る・飛ばされたは拒む（役の自己申告に頼らない。keep-essence 1）
  - 元: works/blk-fix/lib/tddloop.py:383 `red_check`、写しの rules の `red_problems`（review-loop-tdd.py）
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestRedCheck.test_error_and_missing_are_not_red_and_carry_facts_only、lib/tests/test_baseline_red.py::JudgeCase.test_red_problems、lib/tests/test_baseline_red.py::JudgeCase.test_parse_junit_outcomes
  - 本物の run: 子の `tdd-1/state.json` の `units.<key>.red` = "ok"（`junit-<n>.xml` は読んだ直後に消える。lib/baseline_red.py の run_suite）、`tdd-unit.json` の `units[].red`
  - 狭め: 無し

- F002 赤の時の失敗の文の引用と理由を役に書かせ、引用がその回の結末（failure の文・本文、無ければその回のログ）に在ることを機械が照らす。短すぎる引用（3 字未満）・短い理由（10 字未満）は拒み、照らす先が無い名指しは quote_unchecked に残す
  - 元: works/blk-fix/lib/tddloop.py:358 `_quote_target`・:369 `_quote_problem`・:1267 `_quotes_of`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestRedCheck.test_quote_absent_from_failure_is_rejected・lib/tests/test_blk_fix_tdd.py::TestRedCheck.test_quote_checked_against_log_when_failure_has_no_text・lib/tests/test_blk_fix_tdd.py::TestRedCheck.test_nothing_to_quote_is_recorded_unchecked・lib/tests/test_blk_fix_tdd.py::TestRedCheck.test_short_why_and_trivial_quote_are_rejected、lib/tests/test_blk_fix_tdd.py::TestPlanContract.test_red_quotes_are_required_and_recorded
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 子の `tdd-1/state.json` の `units.<key>.red_quotes`・`quote_unchecked`、親の `tdd-unit.json` の `units[].red_quotes`（報告は lib/report.py:164 が読む））
  - 狭め: 無し

- F003 赤の種類（red_kind）は役に見せるだけで機械は種類で拒まない（AttributeError・NameError・例外の failure も引用が在れば赤）
  - 元: works/blk-fix/lib/tddloop.py:5 の docstring（「後者は役に見せるだけで機械は照らさない」）
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestPlanContract.test_red_rejects_wrong_kind・lib/tests/test_blk_fix_tdd.py::TestPlanContract.test_name_error_red_with_assertion_plan_rejected
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F004 緑の判定を機械が JUnit XML で行う（名指しが通る・元で通っていた試験が赤にならない・元の一式が 0 で終わっていれば終了コード 0）
  - 元: works/blk-fix/lib/tddloop.py:1346 `_green`（写しの `green_problems`）
  - 今: 表
  - 証: lib/tests/test_baseline_red.py::JudgeCase.test_green_problems、lib/tests/test_tdd_outside.py::TestLoopRunsOnlyWhatItChecks.test_regression_in_reached_test_is_caught_at_green
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 子の `tdd-1/state.json` の `units.<key>.green` = "ok"）
  - 狭め: 無し

- F005 元から赤のテストの区別: 輪の頭で一式を 1 回走らせて元の結末を取り、元で赤だった試験は赤になっても新しい赤に数えない（keep-essence 2）
  - 元: works/blk-fix/lib/tddloop.py:565 `start`（baseline）・写しの `red_problems` の baseline 引数
  - 今: 表
  - 証: lib/tests/test_baseline_red.py::MustPassCase.test_baseline_failure_is_not_asked・lib/tests/test_baseline_red.py::JudgeCase.test_red_problems_reads_others_against_baseline、lib/tests/test_blk_fix_tdd.py::TestStart.test_baseline_and_first_prompt
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 子の `tdd-1/state.json` の `baseline`（種の `test_mean_of_three` が "failure"）と `baseline_exit`。健全な run で観察できる）
  - 狭め: 無し。ただし子ごとに一式を走らせ直す（線の `test-gate-base` の baseline を使い回さない。workflows/fix/scripts/group_start.py:82）。並べた組の数だけ一式が走る（負荷の話。能力は落ちない）

- F006 受け付けの変更に当たる試験で、元の結末に無い試験の赤は、版を一時の置き場に写して同じ試験を回し、版でも赤なら外して件数と名を知らせに出す
  - 元: works/blk-fix/lib/tddloop.py の `selected_problems`（docstring 105-116 行）
  - 今: 表
  - 証: lib/tests/test_tdd_outside.py::TestAcceptOutsideTier.test_base_reds_left_out_are_named_in_note・lib/tests/test_tdd_outside.py::TestAcceptOutsideTier.test_base_copy_runs_once_per_rev_and_args
  - 本物の run: 筋書きでのみ（選んだ試験が版でも赤の時だけ）
  - 狭め: 無し（ただし知らせの文は F013 のとおり捨てられる）

- F007 名指しの外のテストのファイルへの書き込みを test の段で拒み、テストでないファイルへの仮の実装は拒まずに stub_files に残す。走る前の失敗（一式に居ない・error）は NOT_RAN の 1 行を足して直させる
  - 元: works/blk-fix/lib/tddloop.py:1282 `_test`・:354 `NOT_RAN`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestUnitLoop.test_red_rejects_touching_outside_test_files、lib/tests/test_blk_fix_tdd.py::TestPlanContract.test_missing_named_test_then_stub_outside_test_files_passes（stub_files の assert）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F008 赤の段で、もう通るテストを名指した返答を拒む（書き換えの名指しが通ったままでも拒む）
  - 元: works/blk-fix/lib/tddloop.py:383 `red_check`（もう通る）
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestUnitLoop.test_red_rejects_already_passing_test、lib/tests/test_blk_fix_tdd.py::TestPlanRewrites.test_rewrite_still_green_is_rejected
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F009 段の順（route → 単位ごとに test → fix →（申告した単位だけ）refactor）を機械が持ち、今の単位でない unit_key の返答を拒む
  - 元: works/blk-fix/lib/tddloop.py:1528 `step`・:130 `PHASES`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestUnitLoop.test_happy_path・lib/tests/test_blk_fix_tdd.py::TestUnitLoop.test_red_rejects_wrong_unit
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 子の `tdd-1/state.json` の `calls[]`（n・phase・unit_key・ok））
  - 狭め: 無し

- F010 振り分けの段: 直す義務の単位を全部 1 度だけ tdd か direct（理由 10 字以上）に振る。修正案の約束で tdd の単位は direct に振れず、direct_why でも渡せない（出口は申し出）。3 回拒まれたら全部 direct にして抜ける
  - 元: works/blk-fix/lib/tddloop.py:1023 `_route`・:1060 `_plan_tdd`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestRoute.test_route_gives_up_after_retry_max_to_all_direct、lib/tests/test_blk_fix_tdd.py::TestPlanContract.test_plan_tdd_unit_cannot_be_routed_direct・lib/tests/test_blk_fix_tdd.py::TestPlanContract.test_plan_tdd_unit_cannot_hand_off_by_direct_why
  - 本物の run: 子の `tdd-1/state.json` の `units.<key>.route`・`why`
  - 狭め: 無し

- F011 約束の在る単位は、受け入れのテストの id と案が名指した書き換えを全部名指させ（走らせる前に見る）、名指しの外の既存のテストの本体の書き換えを走らせる前に拒む
  - 元: works/blk-fix/lib/tddloop.py:1075 `_plan_tests`・:1080 `_plan_rewrites`・:1085 `_unnamed_edits`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestPlanContract.test_test_phase_must_name_plan_tests、lib/tests/test_blk_fix_tdd.py::TestPlanRewrites.test_unnamed_edit_rejected_before_running
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F012 当たる試験の選び（keep-essence 6）: 輪の赤の回は名指しだけ、緑の回は名指しと単位の頭からの変更に直に関わる元の一式の試験のファイル（impact.select_tests の direct_only）を合図 TDD_SUITE_ONLY=1 で走らせ、地図が引けなければ一式。受け付けは直に関わる試験だけを走らせ、遠い試験は最後のテストの段に任せる
  - 元: works/blk-fix/lib/tddloop.py:930 `_reached`・:911 `_run`、`selected_problems`、works/.shared/core/impact.py `select_tests`
  - 今: 表
  - 証: lib/tests/test_tdd_outside.py::TestLoopRunsOnlyWhatItChecks.test_red_runs_only_the_named_tests・lib/tests/test_tdd_outside.py::TestLoopRunsOnlyWhatItChecks.test_green_runs_named_and_reached_files_of_the_baseline・lib/tests/test_tdd_outside.py::TestLoopRunsOnlyWhatItChecks.test_map_failure_runs_the_whole_suite、lib/tests/test_tdd_outside.py::TestDirectOnly.test_accept_runs_only_direct_tests_and_leaves_far_ones_to_final_stage
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 子の `tdd-1/suite-<n>.log` と実行器の起動の引数（junit の後ろに足した試験）。実行器を渡した run なら健全な run で観察できる）
  - 狭め: 無し

- F013 回さなかった試験を名前で残す: 受け付けが手元で回さなかった試験（ci_left）・最後のテストの段に任せた試験（final_left・final_far）を、受けた回の trace に載せ、最後の人の関所と報告に並べる（keep-essence 6 の後半）
  - 元: works/blk-fix/scripts/accept.py:708 `tb.trace(TESTS_OP, … ci_left=…, final_left=…, final_far=…)`、works/darkfactory/lib/line_edge.py:274 `_ci_left`・:572-581（最後の関所の文）
  - 今: 表
  - 証: tests/workflows/test_fix.py::FixLoopScriptsCase.test_accept_traces_tests_left_to_ci_and_final_stage・tests/workflows/test_fix.py::BlockScriptsCase.test_collect_writes_the_accept_trace_beside_the_diff・tests/workflows/test_fix.py::GroupChildScriptsCase.test_group_end_writes_the_result・tests/workflows/test_line.py::AskFinalReadsCase.test_fix_beside_files_reach_the_final_gate・lib/tests/test_runreport.py::FixBesideLinesCase.test_fix_trace_rows_are_listed
  - 本物の run: 置き場の `trace.jsonl` の TESTS_OP の行（今は出ない）
  - 狭め: #94 で落ちた（能力の狭めの欄に書かれていない）。Archon で不可でない → 戻す → 部分 D2 で戻した

- F014 受け付けで選んだ試験が 1 件も走らなければ「新しい赤なし」と言わず知らせる（fail-open にしない）
  - 元: works/blk-fix/lib/tddloop.py の `selected_problems`（docstring 116 行）
  - 今: 表
  - 証: lib/tests/test_tdd_outside.py::TestAcceptOutsideTier.test_zero_selected_cases_are_not_reported_as_no_new_red（accept_reply の tests_trace の呼び出しを消すと赤）・tests/workflows/test_fix.py::GroupChildScriptsCase.test_group_end_carries_permits_mismatches_and_accept_notices_to_the_parent_collect（group-end の accept_trace・collect の子の行の集めを消すと赤）
  - 本物の run: 筋書きでのみ
  - 狭め: → #121 で戻した。読み手（最後の関所と報告）は配線の部分 D2（#211）

- F015 テストの凍結（輪の中）: 緑の後、その単位のテストのファイルの hash を控え、直し・整えの段でテストのファイル（ほかの単位の既存の test 関数の本体、.py 以外は消した・置き換えた行）を変えたら拒む。テストを飛ばした・消したも拒む（keep-essence 3）
  - 元: works/blk-fix/lib/tddloop.py:286 `hashes`・:1341 `_frozen_moved`・:1183 `_other_test_edits`・:1239 `_vanished_problems`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestUnitLoop.test_fix_rejects_frozen_test_change、lib/tests/test_blk_fix_tdd.py::TestFixPhaseFreezesOtherTests.test_fix_phase_edit_of_other_test_rejected、lib/tests/test_blk_fix_tdd.py::TestPlanVanishedTests.test_skipped_in_setup_rejected
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 子の `tdd-1/state.json` の `frozen`（パス → hash））
  - 狭め: 無し

- F016 テストの凍結（輪の後）: 輪の後の修正役が、輪で緑にした単位のテストのファイルを変えたら受け付けが拒む。許すのは conflict.test_permits の 1 本道（裁定 fix_test_scope の範囲の行・承認済みの修正案の rewrite_tests・相談の合意）だけで、範囲は輪が済んだ木の行で見る。既存の文を変えずに足しただけ（新しい関数・クラス・import）は数えない
  - 元: works/blk-fix/lib/tddloop.py:1662 `frozen_problems`・:1679 `_frozen_rows`・:1976 `_without_additions`、works/blk-fix/scripts/accept.py の 1b `check_frozen`
  - 今: 表
  - 証: tests/workflows/test_fix.py::GroupChildScriptsCase.test_fix_accept_rejects_a_change_to_a_loop_frozen_test（accept_reply の note("frozen", check_frozen) を消すと赤）
  - 本物の run: 筋書きでのみ（修正役が凍ったテストを触った時だけ）
  - 狭め: 無し（配線の試験だけ欠ける）

- F017 凍結の範囲を関数の幅で読む: 裁定の範囲の 1 行は、その行を含む関数（デコレータ・コメント・def・本体）に広げ、隣の関数・クラスの行・明示の範囲は広げない。.py 以外と読めない旧い文は 1 行のまま
  - 元: works/blk-fix/lib/tddloop.py:2026 `_function_span`
  - 今: 表
  - 証: lib/tests/test_tdd_frozen_function_span.py::FunctionSpanCase.test_neighbour_function_is_rejected・lib/tests/test_tdd_frozen_function_span.py::FunctionSpanCase.test_def_line_allows_decorator_comment_def_and_body
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F018 輪をまたぐ凍結: 2 回目の修正の段（案の直しの後）の修正役も、1 回目の段の輪が凍らせたテストを変えられない。ただし案を直した項目の単位の、前の輪の受け入れのテストの関数の中だけは通す
  - 元: works/blk-fix/lib/tddloop.py:1816 `test_spans`・:1834 `frozen_source`、works/blk-fix/scripts/accept.py の 1b（盤面の tdd-<k> を run の全部の輪として読む）
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestCrossLoopFreeze.test_second_place_sees_the_first_place_loops（2 回目の置き場と組の子の置き場の両方で、tdd-1 の凍ったテストの書き換えを拒む）と同じ類の既存の 2 本。部分 0 の時の証（そのまま残す）: lib/tests/test_blk_fix_tdd.py::TestCrossLoopFreeze.test_second_pass_cannot_touch_first_loop_frozen_tests・lib/tests/test_blk_fix_tdd.py::TestCrossLoopFreeze.test_amended_units_old_test_span_is_not_frozen は同じ置き場に 2 つの輪を作るので、include が分かれても緑のまま（外しても赤にならない形の穴）
  - 本物の run: `fix/refix-run/` の受け付けの拒否の文（今は出ない）。筋書きでのみ（案の直しと 2 回目の修正が要る）
  - 狭め: #94 で狭めた（置き場を include ごとに分けた結果。#94 の本文は `conflict.second_pass` が偽になる件だけを「約束を変える頼み 2」に書き、凍結は書いていない）。Archon で不可でない（fix の入力に 1 回目の置き場の指し札か輪の状態を足せば読める）→ 戻す。約束の変更なので持ち主の確かめが要る → 部分 D1 で戻した（入力 prior_conflicts の指し札の隣の輪の状態を写す。docs/design.md の隣のファイル）

- F019 修正案が書き換えを名指した既存のテストも赤 → 緑を通し、輪で赤 → 緑を確かめた書き換えは後の単位で名指しを強いず、書き換えさせない。輪の後の許しからも外す（skip_ids）
  - 元: works/blk-fix/lib/tddloop.py:1108 `_verified`・:1114 `verified_rewrites`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestPlanRewrites.test_rewrite_red_then_green_then_frozen、lib/tests/test_blk_fix_tdd.py::TestRewriteSharedAcrossUnits.test_verified_rewrite_not_forced_in_later_unit・lib/tests/test_blk_fix_tdd.py::TestRewriteSharedAcrossUnits.test_verified_rewrite_frozen_in_later_unit
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F020 同じ修正案の項目の単位は「一緒に直す単位」として同じ指示書に並べ、前の単位で受け入れのテストが全部確かめ済みなら後の単位を機械が閉じる（covered_by）。確かめていなければ閉じない
  - 元: works/blk-fix/lib/tddloop.py:775 `together`・:981 `_close_covered`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestOneItemTwoUnits.test_step_does_not_hold_off_unit_of_same_item・lib/tests/test_blk_fix_tdd.py::TestOneItemTwoUnits.test_later_unit_is_not_closed_when_its_tests_are_not_verified
  - 本物の run: 子の `tdd-1/state.json` の `units.<key>.covered_by`
  - 狭め: 無し

- F021 3 回拒まれたら諦める（test・fix の段）: 作業ツリーを単位の頭に戻し（書いたテストと足したファイルを外す）、理由と最後の拒否を載せた機械の申し出（source tdd-gave-up・kind needs_context）1 件を裁定に回し、ほかの単位は先へ進む（keep-essence 4）
  - 元: works/blk-fix/lib/tddloop.py:1422 `_give_up`・:1501 `_park_cur`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestUnitLoop.test_green_give_up_parks_unit_for_ruling_and_moves_on・lib/tests/test_blk_fix_tdd.py::TestUnitLoop.test_green_gives_up_and_restores_unit_head、lib/tests/test_blk_fix_tdd.py::TestPlanContract.test_wrong_kind_three_times_gives_up_and_parks_for_ruling、tests/workflows/test_fix.py::GroupChildScriptsCase.test_tdd_step_takes_the_red_and_gives_up_on_the_third_refusal
  - 本物の run: 子の置き場の `conflicts.json` の `items[].source` = "tdd-gave-up"、`result.json` の `units[].status` = "given_up"。筋書きでのみ
  - 狭め: 無し

- F022 申し出の出どころを欄 source で見分ける（機械が止めた tdd-gave-up と、役が phase conflict で出した tdd を、理由の文の写しでなく欄で）。裁定役の指示書は source で名指す
  - 元: works/.shared/core/conflict.py:138-141 `FIX_SOURCE`・`TDD_SOURCE`・`GAVE_UP_SOURCE`、旧試験 works/tests/test_blk_fix_tdd.py:690 `test_red_give_up_parks_machine_claim_with_source`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestUnitLoop.test_role_claim_and_machine_give_up_carry_their_sources（tddloop.step の GAVE_UP_SOURCE・TDD_SOURCE を消すと赤）
  - 本物の run: `conflicts.json` の `items[].source`。筋書きでのみ
  - 狭め: 試験だけ落ちた（#94）。能力は残る

- F023 案を直して直す義務に戻った単位が、また TDD の確認の上限まで落ちたら、裁定に回さず ask_human（by tdd-repeat）で人に上げる（2 回目の機械の諦め）
  - 元: works/.shared/core/conflict.py:567-577 `park`（`amended_rows_by_unit`・`REPEAT_GAVE_UP`）、旧試験 works/tests/test_blk_fix_tdd.py:721 `test_second_machine_give_up_is_asked_to_human`
  - 今: 表
  - 証: tests/workflows/test_fix.py::RefixCase.test_second_give_up_after_replan_is_asked_to_human・tests/workflows/test_fix.py::GroupChildScriptsCase.test_refix_child_sees_the_first_pass_and_returns_only_its_rows
  - 本物の run: `fix/refix-run/conflicts.json` の `items[].ruling.by` = "tdd-repeat"。筋書きでのみ
  - 狭め: #94 で落ちた（能力の狭めの欄に無い）。Archon で不可でない → 戻す（C の `conflict.second_pass` の行と同じ根: 2 回目の段が 1 回目の申し出と裁定を見られない） → 部分 D1 で戻した

- F024 整えの段: 返答の refactor（declared と 10 字以上の理由）か約束の refactor が真の単位だけ整えへ進み、変えたら緑を確かめ直す。3 回拒まれたら緑の木に戻す（reverted）。申告が無ければ skipped で次の単位へ
  - 元: works/blk-fix/lib/tddloop.py:1405 `_refactor`・:1364 `_declared`・:1422 `_give_up`（refactor）
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestRefactorGate.test_fix_without_declaration_skips_refactor・lib/tests/test_blk_fix_tdd.py::TestRefactorGate.test_declared_without_why_rejected、lib/tests/test_blk_fix_tdd.py::TestUnitLoop.test_refactor_gives_up_back_to_green_tree・lib/tests/test_blk_fix_tdd.py::TestUnitLoop.test_refactor_rechecked
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 子の `tdd-1/state.json` の `units.<key>.refactor`・`refactor_why`）
  - 狭め: 無し

- F025 run の test_cmd の関門: 輪の頭で 1 回走らせ、緑なら on（直し・整えの緑の後に走らせて赤は拒む）、実行器と同じコマンドなら same_as_suite（2 度走らせない）、赤・走らないなら off と理由。既存のファイルを書き換える test_cmd はいつも赤で、書き換えた物は戻す。軽量の単位は緑の後に走らせない
  - 元: works/blk-fix/lib/tddloop.py:616 `_test_cmd_gate`・:637 `_cmd_run`・:661 `_test_cmd_problems`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestTestCmdGate.test_fix_rejected_when_test_cmd_red・lib/tests/test_blk_fix_tdd.py::TestTestCmdGate.test_baseline_red_test_cmd_turns_gate_off・lib/tests/test_blk_fix_tdd.py::TestTestCmdGate.test_rewriting_test_cmd_is_restored_and_not_excused・lib/tests/test_blk_fix_tdd.py::TestTestCmdGate.test_light_unit_does_not_run_test_cmd_after_green・lib/tests/test_blk_fix_tdd.py::TestTestCmdGate.test_same_command_as_suite_runs_once
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 子の `tdd-1/state.json` の `test_cmd_gate`・`test_cmd_note`、`tdd-unit.json` の `test_cmd`）
  - 狭め: 無し

- F026 手元の試験の起こし方: 実行器と test_cmd を nice -n 19 で起こし、機械全体の試験の枠（slotwrap）を通し、同じ run の中の元の結末と test_cmd の結果を使い回して出どころの句（reused）を残す
  - 元: works/blk-fix/lib/tddloop.py:296 `run_suite`（slotwrap・nice）・:565 `start`（reused）、旧試験 works/tests/test_blk_fix_tdd.py:2441 `TestRunSuiteSlot`・TestTestCmdGate の使い回しと nice の 5 本
  - 今: 表
  - 証: lib/tests/test_baseline_red.py::RunSuiteSeedCase.test_runner_is_niced・lib/tests/test_baseline_red.py::RunSuiteSeedCase.test_runner_without_nice_runs_bare_and_says_so、lib/tests/test_blk_fix_tdd.py::TestTestCmdGate.test_test_cmd_is_niced・lib/tests/test_blk_fix_tdd.py::TestTestCmdGate.test_shell_test_cmd_that_cannot_launch_is_not_run_under_nice（shell の形の先頭の語が無いコマンドは not_run）・lib/tests/test_blk_fix_tdd.py::TestTestCmdGate.test_command_only_on_the_uv_run_path_is_not_run（uv run の PATH の頭にしか無い語は、パイプの後ろが緑でも not_run）
  - 本物の run: 筋書きでのみ（プロセスの優先度は成果物に残らない）
  - 狭め: nice は戻した（#121）。試験の枠は持ち主の決め no-queue で戻さない。同じ run の中の使い回しは #202 が tree_run.reuse_run で戻した

- F027 実行器が無い・走らない run の扱い: tdd_suite が空・無い・実行できないなら輪を起こさず全部の単位を今どおり直す（go: false。置き場に何も書かない）。途中で実行器が JUnit を書かなくなったら残りを全部 direct（gave_up runner）にして抜ける
  - 元: works/blk-fix/lib/tddloop.py:141 `NO_SUITE`・:565 `start`・:1447 `_abort`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestNoSuite.test_start_without_suite_writes_nothing・lib/tests/test_blk_fix_tdd.py::TestNoSuite.test_missing_suite_file_falls_back_to_direct、lib/tests/test_blk_fix_tdd.py::TestUnitLoop.test_runner_failure_ends_loop_all_direct、tests/workflows/test_fix.py::ScenarioCase.test_fixtures_reach_their_expected_ends（group-no-suite）
  - 本物の run: 子の `tdd-start.json` の `go: false`・`reason`（実行器を渡さない種の run なら健全な run で観察できる）
  - 狭め: 無し

- F028 輪の回数の上限 40（max_iterations と同じ値）に届く周で、残りを direct（gave_up budget）にして done で抜ける（max_iterations に当てて run を落とさない）
  - 元: works/blk-fix/lib/tddloop.py:131 `MAX_ITERATIONS`、works/blk-fix/blk-fix.yaml:157 付近
  - 今: 表
  - 証: tests/workflows/test_fix.py::RolesCase.test_tdd_loop_bound_is_the_lib_budget（max_iterations と tddloop.MAX_ITERATIONS の一致と until_bash が tdd-step の done を読むこと）、lib/tests/test_blk_fix_tdd.py::TestUnitLoop.test_budget_ends_loop_before_max_iterations（上限の周で残りを direct にして抜ける lib の側。lib/tddloop.py の budget の _abort を消すと赤）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F029 段ごとの呼び出しの記録: step 1 回ごとに n・段（申し出は conflict、実行器の止まりは runner）・単位・合否・走らせた回数・秒を状態の calls に積み、出口に出す
  - 元: works/blk-fix/lib/tddloop.py:1528 `step`（calls）
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestRefactorGate.test_calls_recorded・lib/tests/test_blk_fix_tdd.py::TestRefactorGate.test_calls_mark_runner_down・lib/tests/test_blk_fix_tdd.py::TestRefactorGate.test_calls_mark_give_up
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 親の置き場の `groups/<group_id>/result.json` の `tdd.calls` と子の `tdd-1/state.json` の `calls`（`tdd-unit.json` は calls を載せない。実行器を渡した run なら健全な run で観察できる））
  - 狭め: 無し

- F030 拒んだ理由を次の指示書と理由のファイルに載せる（同じ段で出し直させる）
  - 元: works/blk-fix/lib/tddloop.py:807 `prep`、works/blk-fix/scripts/tdd_step.py（reason_file）
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestRoute.test_rejects_bad_routing_with_reason_in_next_prompt、tests/workflows/test_fix.py::GroupChildScriptsCase.test_tdd_step_takes_the_red_and_gives_up_on_the_third_refusal
  - 本物の run: 子の置き場の `tdd-step-reject-<n>.md`。筋書きでのみ（拒否が要る）
  - 狭め: 無し

- F031 引き継ぎの節: 指示書に前に済んだ単位（key・直したファイル・緑にしたテスト・整え）と、今の単位の前の段の結果（test の段の名指し・仮の実装・fix の直し・整えの理由・拒まれた回数）を機械が書く
  - 元: works/blk-fix/lib/tddloop.py:739 `handoff_lines`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestStart.test_tdd_prep_hands_off_finished_units・lib/tests/test_blk_fix_tdd.py::TestStart.test_tdd_prep_hands_off_the_current_units_earlier_phases
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 子の `tdd-1/next.md` の「前の単位の引き継ぎ」の節）
  - 狭め: 無し

- F032 同じ単位の段（test → fix → refactor）は同じ会話で続け、単位が替わる周だけ新しい会話にする
  - 元: works/blk-fix/blk-fix.yaml:142・:157（`fresh_context: false`）と包みが単位の鍵で会話を切る（works/blk-fix/lib/tddloop.py:880 `write_key`・adapter.KEYED_NODES）。旧試験 works/tests/test_blk_fix_tdd.py:128 TestYaml（`fresh_context` が False）
  - 今: 表
  - 証: tests/workflows/test_fix.py::RolesCase.test_tdd_role_continues_within_a_unit、lib/tests/test_blk_fix_tdd.py::TestStart.test_prep_marks_a_new_unit_only_when_the_unit_changes、tests/workflows/test_fix.py::GroupChildScriptsCase.test_tdd_prep_and_step_route_the_unit_change_between_the_two_roles
  - 本物の run: Archon の run の出来事（同じ単位の 2 周目の tdd 節の session の id が 1 周目と同じか）。健全な run で観察できる
  - 狭め: → #121 で戻した。源: 止めた Archon packages/workflows/src/schemas/loop.ts:83（fresh_context 既定 false）・dag-executor.ts:4778・:4831（前の周の会話を渡す）・:9583-9586（並びの層は会話を切る）・:10277-10284（context fresh）・:10662（完了した節だけ会話を進める）

- F033 借りたスキルの座: TDD の役に skills [test-driven-development] を付け、指示書に座の 1 文と無人の読み替えの全文を載せる。座を組めない（写しが固定と違う）時は座の無い指示書に逃げず止める（Broken）
  - 元: works/blk-fix/blk-fix.yaml:188（skills）、works/blk-fix/lib/tddloop.py:807 `prep`（seat.section）、旧試験 works/tests/test_blk_fix_tdd.py:536 `test_tdd_seat_failure_stops_with_broken`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestStart.test_seat_failure_stops_with_broken（tddloop.prep の raise Broken を消すと赤）
  - 本物の run: 子の `tdd-1/next.md` に座の節。健全な run で観察できる
  - 狭め: 止まりの試験だけ落ちた（#94）。能力は残る

- F034 TDD の役の書き込みの出どころ: 段の頭からの変更が Edit・Write の記録か返答の bash_writes に在るかを照らし、無い書き込みを拒む（keep-essence 5 の輪の側）
  - 元: works/blk-fix/lib/tddloop.py:1528 `step`（`writes.check`。包みが記録を書いた）
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::LaneChecksSeamCase.test_tdd_step_matches_writes_with_the_given_log。記録の無い run で輪の書き込みを縛る試験は無い。要追加: tests/workflows/test_fix.py::GroupChildScriptsCase.test_tdd_step_rejects_writes_outside_the_declared_files — 記録の無い子の run で、test の段に宣言の外のテストでないファイルを書いた返答を tdd_step が拒むか、拒まないなら狭めとして書くこと
  - 本物の run: 筋書きでのみ
  - 狭め: #94 で狭めた（U6 の節で TDD の輪の書き込みを申告に求めないと書いたが、能力の狭めの欄には無い）。Archon で不可でない（段 1b で U6 を決めた（docs/design.md の U6）: 役が自分で呼んだ Read・Edit・Write の `file_path` は Archon の `provider_event` から取れ、下請け（Agent）の中の呼びと読んだ時のファイルの sha は取れない。取れない分を取る道の候補は PostToolUse のフック（書き込みの記録は PR #178 でこの道の `bin/_lib/record-write.py` に戻った。読んだ証拠のフックは無い）か節の `hooks:`）→ 持ち主に聞く

- F035 resume で 1 周目から回し直された済んだ輪は、支度が役を起こさず go: false、確かめは返答 null で何も動かさず抜ける。済んでいない輪の空の返答は拒否に数える
  - 元: works/blk-fix/lib/tddloop.py:807 `prep`・:1528 `step`、旧試験 works/tests/test_blk_fix_tdd.py:2405 `test_scripts_on_resume`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestResume.test_done_loop_ends_without_the_role・lib/tests/test_blk_fix_tdd.py::TestResume.test_missing_reply_in_a_running_loop_is_refused、tests/workflows/test_fix.py::GroupChildScriptsCase.test_tdd_step_takes_the_red_and_gives_up_on_the_third_refusal
  - 本物の run: 筋書きでのみ（resume が要る）
  - 狭め: 無し

- F036 止めた申し出の積みが落ちても、状態の未送の並び（unsent）に残し、次の呼びでちょうど 1 件積み、2 度積まない
  - 元: works/blk-fix/lib/tddloop.py:1510 `flush_unsent`・:1517 `flush_claims`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TestResume.test_park_failure_then_next_call_parks_once
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F037 事後の関門（受け付けの最後）: 承認済みの修正案の受け入れのテストを、修正前の版（base）の写しで走らせて赤（failure）、今の木で緑を確かめる。base で通るテストは行にする（「base で緑は外れ」）。行は項目の単位を持ち、最後の回に単位へ結ぶ
  - 元: works/blk-fix/lib/fixgates.py `problems`・`_red_green`
  - 今: 表
  - 証: lib/tests/test_fix_gates.py::TestRedGreen.test_test_green_at_base_is_a_miss・lib/tests/test_fix_gates.py::TestRedGreen.test_not_green_now_is_a_miss・lib/tests/test_fix_gates.py::TestRedGreen.test_base_missing_and_non_failure_are_misses
  - 本物の run: 置き場の `fix-gates.json` の `rows[]`（gate red_green）。健全な run では行が無い（積む物が無ければ帳面を書かない。lib/tests/test_fix_gates.py:133）ので筋書きでのみ
  - 狭め: 無し

- F038 輪の赤の木で確かめ直す: base では一式に居ないテスト（仮の実装が要る）も、輪が残した赤の木で failure なら通し、赤の木で通るなら行（RED_TREE_HEAD）にする。走らせ直した一時の worktree は残さない
  - 元: works/blk-fix/lib/fixgates.py `_red_tree_probs`、works/blk-fix/lib/tddloop.py:421 `red_rerun`
  - 今: 表
  - 証: lib/tests/test_fix_gates.py::TestLoopRedTree.test_stub_red_rechecked_on_loop_red_tree・lib/tests/test_fix_gates.py::TestLoopRedTree.test_red_tree_that_passes_is_a_miss・lib/tests/test_fix_gates.py::TestLoopRedTree.test_sabotaged_red_tree_green_at_base_is_a_miss
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F039 名指しの外の既存のテストの本体の書き換えを事後の関門の行（test_edits）にし、範囲の相談の頼み（base の定義の行）に変えられる。許しは conflict.test_permits（rewrite_tests・removes・裁定の範囲・合意）だけ
  - 元: works/blk-fix/lib/fixgates.py `_test_edits`・`overflow_asks`
  - 今: 表
  - 証: lib/tests/test_fix_gates.py::TestTestEdits.test_unnamed_existing_edit_is_a_miss・lib/tests/test_fix_gates.py::TestTestEdits.test_test_edits_row_becomes_an_ask_on_base_lines・lib/tests/test_fix_gates.py::TestTestEdits.test_removes_permit_is_a_test_permits_row
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F040 実行器が無い・結末を出さない・base の木を作れない時は、事後の赤緑を確かめずに飛ばした理由を帳面に残す（拒まない）
  - 元: works/blk-fix/lib/fixgates.py `NO_SUITE`・`skipped`
  - 今: 表
  - 証: lib/tests/test_fix_gates.py::TestRedGreen.test_no_suite_skips_and_records・lib/tests/test_fix_gates.py::TestRedGreen.test_runner_without_junit_skips_and_records・lib/tests/test_fix_gates.py::TestRedGreen.test_base_tree_that_cannot_be_made_skips_and_records
  - 本物の run: 置き場の `fix-gates.json` の `skipped[]`（実行器を渡さない run なら健全な run で観察できる）
  - 狭め: 無し

- F041 事後の関門が確かめずに受けた理由（unchecked。義務の外を除く）を、受けた回の trace の SKIPPED_OP の行に載せ、報告と最後の人の関所が「受け付け N 回・理由（同じ理由は 1 度）」で数える
  - 元: works/blk-fix/scripts/accept.py:712-714（`tb.trace(fixgates.SKIPPED_OP, …)`）、works/.shared/core/report.py:1636-1640（`trace_rows(b, impact.ACCEPT_GATES_SKIPPED_OP)`）、旧試験 works/tests/test_fix_gates.py:740 `test_report_counts_unchecked_acceptances`
  - 今: 表
  - 証: tests/workflows/test_fix.py::FixLoopScriptsCase.test_accept_traces_skipped_gates・lib/tests/test_runreport.py::FixBesideLinesCase.test_fix_trace_rows_are_listed・tests/workflows/test_line.py::AskFinalReadsCase.test_fix_beside_files_reach_the_final_gate
  - 本物の run: 置き場の `trace.jsonl` の `op: fix_gates_skipped`（今は出ない。実行器を渡さない run なら健全な run で出るはずの行）
  - 狭め: #94 で落ちた（能力の狭めの欄に無い）。Archon で不可でない → 戻す → 部分 D2 で戻した

- F042 事後の関門の帳面は受け付けの回の印（pass・attempt）で行を持ち、同じ回に 2 度走っても積み増さない。前の回の守りのテストの結末（guards）を後の回が消さない
  - 元: works/blk-fix/lib/fixgates.py `_record`（元から guards を落とす不具合が在る）
  - 今: 表
  - 証: lib/tests/test_fix_gates.py::TestLedgerAndText.test_ledger_marks_the_attempt_and_does_not_repeat_rows。guards が残ることの試験は無い。要追加: lib/tests/test_fix_gates.py::TestLedgerAndText.test_later_attempt_keeps_earlier_guards — 1 回目に guards を書いた後に 2 回目を記録し、`fixgates.guards(b, pass_="first", attempt=1)` が空にならないこと（今は赤になるはず）
  - 本物の run: 置き場の `fix-gates.json` の `guards`。筋書きでのみ
  - 狭め: 元からの不具合（#97 に起票済み）。直す

- F043 事後の関門の base の結末を、鍵（版・実行器・名指し・テストのファイル）が同じなら受け付けの回をまたいで 1 度だけ走らせ、2 回目の修正の段も 1 回目の結末を使う
  - 元: works/blk-fix/lib/fixgates.py `_base_cache`（盤面の run の根）、旧試験 works/tests/test_fix_gates.py:432 `test_second_pass_reuses_first_pass_base`
  - 今: 表
  - 証: lib/tests/test_fix_gates.py::TestBaseCache.test_base_runs_once_across_attempts（同じ置き場の回の間だけ）。include をまたぐ使い回しは縛らない
  - 本物の run: 置き場の base の控え（`_base_cache` の下）。筋書きでのみ
  - 狭め: #94 で狭めた（置き場を分けた結果。2 回目の段で base を走らせ直すだけで判定は変わらない＝負荷だけの差）。Archon で不可でない。持ち主に聞く（小）

- F044 2 回目の修正の段の事後の関門は、1 回目の段の裁定 fix_test_scope の範囲の直しをいつも許す（conflict.second_pass で引く）
  - 元: works/blk-fix/lib/fixgates.py `problems`（`conflict.second_pass`）
  - 今: 表
  - 証: tests/workflows/test_fix.py::RefixCase.test_refix_sees_first_pass_rulings（写さない形は tests/workflows/test_fix.py::FixLoopScriptsCase.test_ruled_pass_allows_ruled_test_scope_and_first_does_not が拒む）・lib/tests/test_fix_gates.py::TestTestEdits.test_second_pass_keeps_first_pass_ruled_limit。部分 0 の時の証（そのまま残す）: lib/tests/test_fix_gates.py::TestTestEdits.test_second_pass_keeps_first_pass_ruled_limit は同じ置き場に裁定と AMENDED を作るので緑のまま（線の上で働かないことは縛れない）。線の上の穴は C の `conflict.second_pass` の行が扱う
  - 本物の run: `fix/refix-run/fix-gates.json` の `rows[]` に 1 回目に許したテストの test_edits の行が出る（出てはいけない）。筋書きでのみ
  - 狭め: #94 で狭めた（約束を変える頼み 2）。Archon で不可でない → 戻す（C の行と同じ直し） → 部分 D1 で戻した

- F045 盤面・包みだけが持っていた物（受け付けの最後の結果の控え accept-last.json に輪の拒否を書かない・開けない盤面で Broken・単位の鍵を包みに書く write_key・YAML の入力 tdd_suite・test_cmd・unit_depths を任意に持つ）
  - 元: 旧試験 works/tests/test_blk_fix_tdd.py:814 `test_step_script_leaves_no_accept_last_row`・:1631 `test_board_that_cannot_open_is_broken`・:128 TestYaml、works/blk-fix/lib/tddloop.py:880 `write_key`
  - 今: 表
  - 証: lib/tests/test_blk_fix_tdd.py::TddloopSeamsGoneCase.test_board_and_wrapper_seams_are_gone（無いことを縛る）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（能力でなく置き場の違い。会話の切り替えだけ F032 で扱う）

小計: 45 行 / 今が無し 3（F013・F026・F041）＋線の上で働かない 3（F018・F023・F044）/ 証が要追加 12（F013・F016・F018・F022・F023・F026・F028・F032・F033・F034・F041・F042）/ 狭め不可でない 9（F013・F018・F023・F026・F032・F034・F041・F043・F044）

## B. 修正役と修正の受け付け（F100〜）

置き場（本物の run の記録）の読み方: 組の子の run は自分の run の成果物の置き場の `fix/fix/` に書き（`workflows/.shared/boundary.py` `place`）、結果を親の置き場の `out_dir/<group_id>/result.json` に書く。裁定の後の修正（fix-ruled）は親の置き場 `fix/fix/` で回る。2 回目の修正（線の include `refix`）は `fix/refix-run/`。受け付けの拒否の理由は置き場の `reject-<節>-<k>.md`（`lib/fixboard.py` の `REJECT_NAME`）、trace の行は `trace.jsonl`（`lib/fixboard.py:38`）。種（`tests/e2e/target-seed`、stats.py の mean と clamp の 2 つの欠陥）の健全な run は、修正役が 1 回で受け付けを通る筋になりやすく、拒否・諦め・はみ出しの道は通らない。

- F100 修正役が出す前に使う事前の確かめのコマンド（受け付けと同じ口で範囲・書き込み・凍結を乾いた形で当て、置き場を書かない）を持つ
  - 元: works/blk-fix/lib/factchecks.py:218 `precheck`・:238 `main`（rules/direct.md が名指す）
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::FactchecksSeamCase.test_main_reads_the_plan_in_the_place、lib/tests/test_fix_seams.py::FactchecksSeamCase.test_scope_reject_listed_and_place_untouched
  - 本物の run: 修正役の会話の Bash の呼び出し（Archon の節 fixer のログ）にだけ現れる。置き場に跡は残らない → 筋書きでのみ
  - 狭め: 無し

- F101 範囲の相談の枠を使い切った後に修正役が出した consult の欄を、受け付けが「枠を使い切った」の行で拒み、欄を外して後の確かめに当てる
  - 元: works/blk-fix/scripts/accept.py:8-9（-4 の段）・:629-631 `accept_fix`
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_consult_after_budget_is_rejected_and_dropped（accept_reply の consult の枝を消すと赤）
  - 本物の run: 筋書きでのみ（枠 consult.BUDGET を使い切る run は健全な種では起きない）
  - 狭め: 無し（試験だけ欠け）

- F102 書き込みの出どころ: 版からの変更が、Edit・Write の記録か返答の bash_writes の申告（理由つき）のどちらかに在るかを照らし、無い変更を拒む（keep-essence の 5）
  - 元: works/.shared/core/writes.py `check`・works/.shared/core/record-write.py（PostToolUse の包みが記録を書く）・works/blk-fix/scripts/accept.py:12-17
  - 今: 表
  - 証: lib/tests/test_writes.py::TestProvenance.test_bash_write_without_record_is_rejected ほか 15 本（記録が在る時の照らし）
  - 本物の run: PR #178 の前は置き場の `writes.jsonl` が作られず（包みが無い）、全 run が「記録の無い run」（writes.NO_RECORD）になり、下の F103 の道だけが効いた。`trace.jsonl` に NO_RECORD の知らせの行。#178 の後の本物の run は確かめていない
  - 狭め: #94 で狭めた（当時は記録を取る仕組みが U6 待ち。PR #94「U6 の結果」）。Archon で不可でない: 節に `hooks:` を書ける（Archon packages/workflows/src/schemas/dag-node.ts:193 `hooks: workflowNodeHooksSchema.optional()`）。段 1b で U6 を決めた（docs/design.md の U6）: 役が自分で呼んだ Read・Edit・Write の `file_path` は Archon の `provider_event` から取れ、下請け（Agent）の中の呼びと読んだ時のファイルの sha は取れない。取れない分を取る道の候補は PostToolUse のフック（書き込みの記録は PR #178 でこの道の `bin/_lib/record-write.py` に戻った。読んだ証拠のフックは無い）か節の `hooks:`。Bash で書いたファイルは出来事にもフックの Edit・Write にも載らず、bash_writes の申告に残る → 書き込みの記録は PR #178 で戻した

- F103 記録の無い run では、段の頭の木からの変更が全部、修正役の申告（changes[].files と bash_writes）に在ることを求め、無い変更を拒む（TDD の輪と実行器が作ったファイルは修正役に求めない）
  - 元: 無し（元は記録が在る前提。記録の無い run は通して trace に 1 行だけ。works/blk-fix/scripts/accept.py:12-17）
  - 今: 表
  - 証: tests/workflows/test_fix.py::FixLoopScriptsCase.test_undeclared_change_is_rejected、tests/workflows/test_fix.py::FixLoopScriptsCase.test_tdd_loop_writes_are_not_the_fixers、lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_undeclared_writes_bind_to_changes_and_bash_writes
  - 本物の run: 修正役が申告外のファイルを書いた時だけ `reject-fix-accept-<k>.md` に UNDECLARED の行 → 健全な run では現れない（筋書きでのみ）。通った時は組の子の `fix/fix/` に `fix-head.json`（段の頭の木）が在る
  - 狭め: 無し（記録の代わりの縛り。上の F102 の狭めの埋め）

- F104 申告の bash_writes は、受けた返答・盤面に渡す返答から外す（拒む時も）。2 回目の修正の段は 1 回目に受けた返答の控えの bash_writes を申告に足す
  - 元: works/blk-fix/lib/factchecks.py:90 `check_writes`（conflict.held_writes を足す）・works/blk-fix/scripts/accept.py:16-17
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::FactchecksSeamCase.test_writes_use_the_log_and_skip（受けた返答に bash_writes の欄が無いこと。控えを読む試験 test_held_writes_join_the_declaration は #121 F136 で消した）
  - 本物の run: 筋書きでのみ（受けた返答 = 組の子の `fix/fix/fix-reply.json`。親の `groups/<group_id>/result.json` の reply_file が指す。bash_writes の欄が無いことは照らしで言えない）
  - 狭め: 控えの足し込みは書き手が無くなり死んだ（F136 と同じ。#94）

- F105 単位の行の照らし: 同じ unit_key を 2 行に分けた返答を拒む・直す義務にも外れた単位にも無い key を拒む・外れた単位（答え待ちの問いや直さない裁定）の key は外れた理由を名指して拒む
  - 元: works/blk-fix/scripts/accept.py:30-37 `check_unique_units`・`check_opened_units`・`check_excused_units`
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_accept_reply_rejects_duplicate_unknown_and_excused_rows（accept_reply の note duplicate・not_opened・excused のどれを消しても赤）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（配線の試験の欠け）

- F106 最後の回（3 回目）に、義務の外の単位にだけ結んだ拒否の行は数えず、その単位の行を changes から外し（直しは作業ツリーに残す）、残りで受ける（trace に ABSORBED_OP）
  - 元: works/blk-fix/scripts/accept.py:97 と :636-645 `settle`（:644 `absorbed`）・:725-726（ABSORBED_OP `fix_excused_dropped` :158）
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_last_turn_drops_only_the_excused_row・lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_last_turn_parks_the_duplicate_and_absorbs_the_excused_row
  - 本物の run: 筋書きでのみ（答え待ちの問いで外れた単位を修正役が 3 回直そうとする run）
  - 狭め: → #121 で戻した

- F107 .archon/ の下（自分食いの run の pack の写し）を申告した・変えた返答を拒む（check_pack_copy）
  - 元: works/blk-fix/scripts/accept.py:38 `check_pack_copy`・:653
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_pack_copy_change_is_rejected、tests/workflows/test_fix.py::GroupChildScriptsCase.test_fix_accept_rejects_a_change_under_the_skip_head・tests/workflows/test_fix.py::FixLoopScriptsCase.test_prep_snapshots_the_skip_head_before_marking_the_stage_head（控えを段の頭の印より先に書く）
  - 本物の run: 筋書きでのみ
  - 狭め: → #121 で戻した。控えの無い置き場（lib だけで呼ぶ時）は申告だけを見る（元は止めた）

- F108 承認済みの修正案の項目と差分を照らす（範囲 allowed_paths の外・out_of_scope・adds の識別子が差分に無い・canonical の外の同名の定義・removes の識別子が残る・tests に無いテストを足した・tests のテストが無い）
  - 元: works/blk-fix/lib/planscope.py `check`・works/blk-fix/scripts/accept.py:51-62
  - 今: 表
  - 証: lib/tests/test_plan_scope.py::ProblemsCase ほか 63 本（例 lib/tests/test_plan_scope.py::ProblemsCase.test_out_of_scope_wins_over_allowed・lib/tests/test_plan_scope.py::ProblemsCase.test_adds_identifier_must_appear_in_added_lines・lib/tests/test_plan_scope.py::ProblemsCase.test_removes_identifier_must_be_gone）、lib/tests/test_fix_seams.py::PlanrangeSeamCase.test_outside_the_items_range_is_rejected_inside_passes
  - 本物の run: 筋書きでのみ（planscope.SCOPE_OP の行を書く呼び手が無く、受けた回の範囲の照らしは置き場に跡を残さない）
  - 狭め: 無し

- F109 範囲の照らしは、範囲の相談で修正案を書いた役が許したパス・テスト（字のまま同じパスだけ out_of_scope から外す）と、裁定の後（ruled）の直す裁定の limits のパスだけで広がる
  - 元: works/.shared/core/planrange.py `permit_paths`・`check_paths`、works/blk-fix/lib/planscope.py の with_agreed
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::PlanrangeSeamCase.test_agreed_and_ruled_paths_widen_from_the_place、lib/tests/test_plan_scope.py::AgreedOverridesOutOfScopeCase.test_override_is_exact_path_only
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F110 範囲の外の変更と案の外のテスト（はみ出し）だけの回は拒まず、まだ聞いていない物を範囲の相談に積み（作業ツリーを変えない）、deny・defer・聞けない物は機械が段の頭の姿に戻して残りで通し直す。戻した物と認めた物を trace に名指す
  - 元: works/blk-fix/scripts/accept.py:72-85 `settle_overflow`・:684-694
  - 今: 表
  - 証: tests/workflows/test_fix.py::FixLoopScriptsCase.test_unasked_overflow_is_queued_for_the_next_consult_check、tests/workflows/test_fix.py::FixLoopScriptsCase.test_denied_overflow_is_reverted_by_the_machine、lib/tests/test_fix_seams.py::SettleOverflowSeamCase.test_denied_overflow_is_reverted_and_accepted
  - 本物の run: 筋書きでのみ（健全な種ではみ出しは出ない）。起きれば置き場の `consult-first.json` の行と trace.jsonl の impact.ACCEPT_OVERFLOW_OP の行
  - 狭め: 無し

- F111 はみ出しだけに見える回は、写しの照らし（数え直し）を乾いた形で先に当て、写しの拒否が出れば成り立たない行に足す（相談の周を無駄にしない）
  - 元: works/blk-fix/scripts/accept.py:675-681
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::SettleOverflowSeamCase.test_copy_reject_turns_overflow_into_a_reject
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F112 閉鎖の数え直し: 判定者の class_query（replace_query の裁定を受けた単位は置き換えた問い）を修正前の版と修正後の作業ツリーで機械が数え、単位ごとの表（closed と申告との食い違い）を置く。食い違いは拒否でなく記録
  - 元: works/blk-fix/lib/unitrows.py:218 `take`・works/blk-fix/scripts/accept.py:91-96
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_closure_reply_takes_the_replaced_query_and_the_zero_units、lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_accept_reply_saves_the_closure_table_it_recounted、lib/tests/test_fix_units.py::BuildCase ほか（例 lib/tests/test_fix_units.py::BuildCase.test_replaced_query_counts_and_names_the_ruling）
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 組の子の置き場 `fix/fix/fix-unit-rows.json`（lib/querytest.py:44 `CLOSURE_FILE`）。種の判定に class_query が在れば健全な run で必ず書かれる）
  - 狭め: 無し

- F113 判定の時に engine が 0 件と数えた単位（engine_zero）は、判定者の母数の照らし（問いを狭めている）から外す
  - 元: review-loop.py:2638 と :2776-2777（盤面の loop_state engine_zero）
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RecountSeamCase.test_zero_unit_is_not_rejected_as_narrowed
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F114 直す義務の単位（[block] と do-now）を changes に書かずに返した返答を、待ちの理由（not_done の why）を添えて拒む
  - 元: review-loop.py:2658-2673 `fix_covers_open_units`
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RecountSeamCase.test_rejects_uncovered_owed_unit
  - 本物の run: 筋書きでのみ（拒否は reject-fix-accept-<k>.md）
  - 狭め: 無し

- F115 修正が在るのに fix_closure が「黙って通る値」（判定の SILENT_STATUS の表から引く）なら拒む
  - 元: review-loop.py:2682
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RecountSeamCase.test_rejects_self_reports_the_machine_can_check
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F116 赤を一度も見ていないのに fix_closure=clean を名乗る返答を拒む
  - 元: review-loop.py:2786-2790
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RecountSeamCase.test_rejects_self_reports_the_machine_can_check
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F117 2 つ以上の修正が同じファイルを触った時、そのファイルを interactions に挙げ、checked に突き合わせの結果を書くことを求める
  - 元: review-loop.py:2690-2709
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RecountSeamCase.test_rejects_blank_interaction_check
  - 本物の run: 種は 2 つの欠陥が同じ stats.py に在るので、修正役が 1 組で両方を直せば健全な run でも interactions の照らしが走る（受けた返答 = 組の子の reply_file の interactions[]）。組が 2 つに分かれれば各組の返答は 1 行ずつで、同じファイルの照らしは走らない（組をまたぐ干渉は見る役が無い。E の行を参照）
  - 狭め: 無し

- F118 bypass_tried（修正を残したまま破りに行った入力と結果）が空同然の行を拒む
  - 元: review-loop.py:2719-2721
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RecountSeamCase.test_rejects_self_reports_the_machine_can_check
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 受けた返答の changes[].bypass_tried（健全な run でも欄は在る））
  - 狭め: 無し

- F119 breaks.result（壊しうる面を引いて確かめた結果）が空同然の行を拒む
  - 元: review-loop.py:2722-2724
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RecountSeamCase.test_rejects_self_reports_the_machine_can_check
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 受けた返答の changes[].breaks.result）
  - 狭め: 無し

- F120 precedent: from_judge_row なら判定者の先行例の行にその単位が在ることを、そうでなければ problem と source（not_found なら searched）を求める
  - 元: review-loop.py:2725-2732
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RecountSeamCase.test_rejects_precedent_without_problem_or_source
  - 本物の run: 受けた返答の changes[].precedent
  - 狭め: 無し

- F121 症状を塞ぐ修正（root_or_symptom.kind=symptom）に、なぜ今それで止めるかの理由（10 字以上）を求める
  - 元: review-loop.py:2733-2735
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RecountSeamCase.test_rejects_self_reports_the_machine_can_check
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 受けた返答の changes[].root_or_symptom）
  - 狭め: 無し

- F122 修正役が coverage.how を書かなければ判定者の class_query の how を補って返答に書き戻す（判定者の how を役に写させない）。どちらも無ければ拒む
  - 元: review-loop.py:2736-2747
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RecountSeamCase.test_accepts_real_fix_and_keeps_counts、lib/tests/test_fix_seams.py::RecountSeamCase.test_rejects_narrowed_query_and_unknown_direction
  - 本物の run: 組の子の置き場の `coverage-after.json` の items[].how（lib/recount.py:66）
  - 狭め: 無し

- F123 数える向き（defects / population）は判定者が決め、判定者の class_query が無い単位は coverage.counts を求める
  - 元: review-loop.py:2748-2753
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RecountSeamCase.test_rejects_narrowed_query_and_unknown_direction
  - 本物の run: coverage-after.json の items[].counts
  - 狭め: 無し

- F124 修正前・修正後の件数は engine が数え直す（修正前は判定者と同じ版、修正後は未追跡を含む作業ツリー）。sites が母数を超えれば拒み、母数より少なく remaining が無ければ拒む
  - 元: review-loop.py:2754-2775
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RecountSeamCase.test_rejects_sites_mismatch_unless_remaining_is_written
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 組の子の置き場の `coverage-after.json`（{round, items: [{unit_key, how, counts, total, closed, after}]}）。健全な run で mean と clamp の行）
  - 狭め: 無し

- F125 判定者が数えた母数より修正役の how が修正前の版で少なく数える（問いを狭めた）時、remaining が無ければ拒む
  - 元: review-loop.py:2776-2780
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RecountSeamCase.test_rejects_narrowed_query_and_unknown_direction
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F126 欠陥を数える問い（defects）で母数を全部塞いだと言うのに修正後も件数が残れば拒む
  - 元: review-loop.py:2781-2784
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RecountSeamCase.test_rejects_count_not_dropped
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば coverage-after.json の after が 0 であること（mean の行））
  - 狭め: 無し

- F127 数える問いを走らせる量に上限（1 周 300 回か 900 秒）を設け、修正前の版の数は置き場に取り置いて 2 度数えない
  - 元: review-loop.py:3304 `COUNT_BUDGET`・:3307 `_run_query`
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RecountSeamCase.test_budget_exhausted_is_a_reject_line
  - 本物の run: 置き場の `count-budget.json`・`count-cache.json`
  - 狭め: 無し

- F128 修正役が新しく書いた指し（wrote_refs）を、判定の指摘と同じ裏取り（指し先の中に引用が在るか）に通す。申告が空でも通す
  - 元: review-loop.py:2794
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RecountSeamCase.test_rejects_wrote_refs_and_added_links_that_do_not_resolve
  - 本物の run: 筋書きでのみ（拒否の時だけ文が残る）
  - 狭め: 元は次の周の判定役に読了の記録（loop_state.wrote_refs_reads）を渡していた（review-loop.py:2799）。今は `_cite_errors` の 2 つ目の返り値を捨てる（lib/recount.py:187 の `cites, _`）。線に周が無いので渡す先も無い。#94 は触れていない → 持ち主の確かめ待ち（判定のやり直し rejudge に渡す材料かどうか）

- F129 差分が足した Markdown のリンクを、申告に依らず差分から拾い、指し先のファイル（版に在る物）と見出しに届くかを確かめる
  - 元: review-loop.py:2804-2809・`_added_md_links` :2852・`_walk_as_written` :2896・`_md_link_errors` :2915
  - 今: 表
  - 証: lib/tests/test_recount_links.py::MdLinkCase（未追跡・symlink・綴りの大小・外・空ディレクトリ・囲いの中・URL の 7 本。綴りの大小の変異は大小を区別しないファイルシステムでだけ赤。10 件を超えた分の 1 行は縛っていない）、lib/tests/test_fix_seams.py::RecountSeamCase.test_rejects_wrote_refs_and_added_links_that_do_not_resolve（受け付けから md_link_errors を呼ぶ所を消すと赤）
  - 本物の run: 筋書きでのみ（種の修正は .md を足さない）
  - 狭め: 無し（試験の欠け）。起点の版が元の `b.record["base"]`（run の始め）から `base_rev` に変わった（lib/recount.py:190）。組の子では親の HEAD（base-rev.json）なので同じ意味

- F130 修正案の事前審査の穴（faces）と別案（shrink）に、修正役が plan_faces で key ごとに 1 度だけ答え（absorbed / declared）、答えない key・余る key・重複を機械が拒む（元 `_plan_face_errors`）
  - 元: review-loop.py:3115 `_plan_face_errors`・:2803、works/blk-fix/rules/direct.md:10・95
  - 今: 表
  - 証: tests/workflows/test_fix.py::FixAcceptCase.test_unanswered_plan_face_is_rejected・tests/workflows/test_fix.py::InputsCase.test_plan_review_is_an_input・tests/workflows/test_fix.py::CopiedTextsCase.test_every_command_is_its_original_with_only_ledgered_edits（許した直しは tests/workflows/copied_rewrites.json）
  - 本物の run: 受けた返答の plan_faces が常に [] であること（組の子の reply_file）。事前審査が穴を挙げた run でも修正役は答えない
  - 狭め: #94 で狭めた（「能力の狭め」の plan_faces の行、「約束を変える頼み」3）。Archon で不可でない（include の `with:` に入力を 1 つ足すだけ。Archon packages/workflows/src/schemas/dag-node.ts:1325-1330 の `with:` は include の入力の写像）→ 戻す（fix の入力と線の配線を足す） → 部分 D1 で戻した（組に分けた修正役は自分の単位の穴と単位の無い行に答える。元は 1 つの p3.fix が全部に答えた。裁定の後の受け付けは全部）

- F131 受け付けの確かめは返さずに表の id で積み、最後に 1 回だけ、見出しごとに並べた本文と行ごとの id で拒む（1 誤り 1 行。役が 3 回の枠を形の誤り 1 つずつで使い切らない）
  - 元: works/blk-fix/scripts/accept.py:5-6・`rejected`、review-loop.py:2658 の docstring
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_reject_text_follows_the_check_order
  - 本物の run: 拒否の時の置き場 `reject-fix-accept-<k>.md`（健全な run では現れないことが多い）
  - 狭め: 無し

- F132 拒否の理由をファイルに書き、輪の拒否の全部（古い順）を 1 つのファイルにまとめて次の回の指示書の 1 行目の後に名指す（役が Read で読む）
  - 元: works/blk-fix/lib/fixrules.py `last_reject`・REJECT_FN、works/.shared/core/rolekit.py:64 `REJECT_LINE`。元は最後の拒否だけを名指したが、拒まれた役は同じ会話の続きで起きた（works/.shared/core/graphloops/engine/role_run.py:19-20）
  - 今: 表
  - 証: tests/workflows/test_fix.py::FixLoopScriptsCase.test_third_reject_gives_up_only_the_named_unit、lib/tests/test_fix_seams.py::RulebookSeamCase.test_render_heads_rejects_and_lang、tests/workflows/test_fix.py::DeltaScriptsCase.test_third_refix_prompt_names_every_reject_of_the_loop（#345）
  - 本物の run: 拒否が在れば置き場の `reject-fix-accept-<k>.md`・`rejects-fix-accept.md` と次の回の修正役の指示書の 2 行目
  - 狭め: 無し

- F133 修正の受け付けの 3 回目の拒否: 拒否の行を単位に結び（申し出の行は申し出た単位、ほかは文が名指す単位・足跡・届く試験）、結んだ単位を足跡を共にする単位と一緒に段の頭の木へ戻して控えの patch に移し、ask_human の裁定つきで止め、残りの単位で頭から通し直す（keep-essence の 4 の後半）
  - 元: works/blk-fix/scripts/accept.py:91-105（docstring 末尾）・:378 `last_settle`・:434 `park_units`
  - 今: 表
  - 証: tests/workflows/test_fix.py::FixLoopScriptsCase.test_third_reject_gives_up_only_the_named_unit、lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_accept_reply_parks_the_bound_unit_on_the_last_turn
  - 本物の run: 筋書きでのみ。起きれば conflicts.json に source fix・ruling ask_human の行、trace.jsonl に conflict.ACCEPT_PARKED_OP（fix_bound_parked）、置き場に戻した直しの patch
  - 狭め: 無し

- F134 最後の回に止める単位が残らないのに写しの拒否が残れば、義務の残りを全部止めて通し直し、それでも残れば受けずに諦める（元は機械の空の返答を盤面に渡して盤面を止めなかった: hand_empty）
  - 元: works/blk-fix/scripts/accept.py:105-108・:454 `hand_empty`・:739
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_last_turn_without_bound_unit_parks_the_rest_or_gives_up
  - 本物の run: 筋書きでのみ
  - 狭め: hand_empty は #94 で外した（下の F136）。止めずに空の返答を渡す代わりに「受けずに諦める」になったので、返り units はその単位を not_done にする。線から見て結末は同じ（直らない）。不可でない

- F135 範囲の相談の周（修正役が consult を出し、答えの役が答えた周）は受け付けが返答を見ず、拒否を数えずに次の周の修正役が答えを読んで続ける
  - 元: works/blk-fix/scripts/accept.py:7-8
  - 今: 表
  - 証: tests/workflows/test_fix.py::FixLoopScriptsCase.test_consulted_turn_and_skipped_fixer
  - 本物の run: 筋書きでのみ（相談が起きる run）
  - 狭め: 無し

- F136 2 回目の修正の段の控え: 案の直しを待つ単位が在る時、受けた返答を盤面に渡さずに控え（fix-held-reply.json。bash_writes と渡す形の行つき）、2 回目の段の受け付けが控えの行を単位で合わせ（with_held）、控えの単位を書き直す返答を拒み（check_accepted_rows）、輪の最後でも控えの直しを戻さない（hold_fix・with_held・hand_empty）
  - 元: works/blk-fix/scripts/accept.py:86-90・:97-105・:454 `hand_empty`・:477 `hold_fix`・:656-660 `check_accepted_rows`・:772 `_shaped`、works/.shared/core/conflict.py:719-787
  - 今: 無し（表）
  - 証: 消すだけ。書き手 0 本（workflows/ と線の script に fix-held-reply の書き手が無い）。1 回目の返答を失わないことは tests/workflows/test_line.py::FixedCase.test_refix_is_merged_without_losing_the_first が縛る
  - 本物の run: 無し（置き場に fix-held-reply.json は現れない）
  - 狭め: #94 で狭めた（「能力の狭め」の hold_fix の行。代わりに裁定の後の返答を fix-ruled-reply.json に分けて collect が重ねる）。今の線は fix_plan_item の単位を 1 回目の fix の返り replan_items で外へ出し、2 回目は別の include（refix）で直すので、1 回目の段の中で「待つ」必要は無くなった。代わりに 2 回目の段は 1 回目の段の控えも裁定も読めない（C の conflict.second_pass の行）。Archon で不可でない（置き場のファイルなので、線が 1 回目の置き場のパスを refix に渡せば読める）→ 持ち主の確かめ待ち。少なくとも死んだ読み口（held_reply ほか）を残すか外すかを決める 決め: 1 回目の返答を失わない能力は線の fixed が持つ。死んだ読み口は区分 F の issue で消す（K20）（線の配線の文書の「この文書の外」の「決めた物」）

- F137 修正役の異議（rejudge_requested。判定のやり直しの頼み）を受けた時に線へ渡す
  - 元: review-loop.py:2811-2812（loop_state.rejudge_requested）
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_collect_plan_item_ruling_and_objection
  - 本物の run: 節 `fix` の出力の objection（健全な run では ""）。線は after-fix が読む（workflows/line/works-factory-line.yaml:400-401）
  - 狭め: 無し

- F138 修正役の 6 つの印（mechanism_changed・premise_drift・gates_changed・seams_changed・security_surface_changed・path_changed）を組の結果と裁定の後の返答の論理和で返す
  - 元: works/blk-fix/scripts/collect.py（盤面の p3.fix の欄を線が読む）
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::GroupScriptsSeamCase.test_changed_marks_or_over_groups_and_ruled
  - 本物の run: 節 `fix` の出力の changed
  - 狭め: 無し

- F139 修正役が「仕組みを新しく作ることになった」（mechanism_changed）と言った時に止める・深さを上げる道
  - 元: works/blk-fix/rules/direct.md の mechanism_changed の申告、works/darkfactory/lib/depth.py の修正の後の信号
  - 今: 表
  - 証: 無し（PR #94「受け入れの一覧」の p3.fix の行も「縛る試験は見つけられなかった」と書く）。要追加: 線の側で、changed.mechanism_changed が真の時の振る舞い（深さを上げる・関所を開く）を縛る試験（#74 の head の tests/workflows/test_line.py に置く）
  - 本物の run: 節 `fix` の出力 changed.mechanism_changed
  - 狭め: fix の範囲では狭めていない（元も申告と線の読みだった）。線との申し送り

- F140 修正役の指示書の組み立て: 始めの記録の 2 行（方針のファイル・依頼の文のファイル）→ 役の頭 → 決まり（共通の canon と種類ごとの証拠）→ brief の節 → 控えの節 → 人の関所の一言（notes_file）→ 座 → 言語の 1 行。同じ入力からは同じバイト
  - 元: works/blk-fix/lib/fixrules.py:681-767 `prep`・`fix_parts`、works/.shared/core/rulebook.py
  - 今: 表
  - 証: lib/tests/test_fix_rules.py::PrepCase.test_first_prompt_and_iterations、lib/tests/test_fix_rules.py::StartValuesCase.test_lines_sit_after_the_title_and_before_the_rules、lib/tests/test_fix_rules.py::TestCompose.test_same_inputs_same_bytes、lib/tests/test_fix_rules.py::TestLangLine.test_every_writer_prompt_ends_with_the_lang_line
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 組の子の置き場の修正役の指示書（fix-prep の出力 prompt_file））
  - 狭め: 無し

- F141 直す単位ごとの brief（承認済みの修正案の項目の約束）を凍らせて切り、修正役と TDD の役に渡す。控えが壊れた・書き換えられた・消えた時は直すか止める
  - 元: works/blk-fix/lib/planbrief.py `cut`・`_freeze`・`_restore`・`_ledger`
  - 今: 表
  - 証: lib/tests/test_plan_brief.py::BriefCase.test_cut_is_frozen_and_restores_edited_file、lib/tests/test_plan_brief.py::BriefCase.test_ledger_rewritten_consistently_is_broken、lib/tests/test_plan_brief.py::BriefCase.test_restore_does_not_write_through_symlink、lib/tests/test_plan_brief.py::TestRecutAfterAmend.test_recut_after_amend ほか 27 本
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 組の子の置き場の `briefs.json` と brief のファイル（修正案の在る run なら健全な run でも在る））
  - 狭め: 無し

- F142 直す義務の無い組・単位では修正役を起こさない（fix-prep が go: false）
  - 元: works/blk-fix/scripts/fix_prep.py（nothing_owed）
  - 今: 表
  - 証: tests/workflows/test_fix.py::FixLoopScriptsCase.test_fix_prep_writes_the_prompt_and_skips_without_duty
  - 本物の run: 直す義務の無い組だけ fixer の節が skipped（Archon の節の状態）。TDD の輪が緑にした単位も直す義務に残るので、種の組では修正役が起きる
  - 狭め: 無し

- F143 TDD の輪が緑にしていない単位があれば、修正役は項目ごとに下請け（実装役 implementer と審査役 task-reviewer）を Agent で起こし、実装役・審査役のファイル（g1-impl-<n>.md・g1-review-<n>.md）と差分のコマンド・works の決まり（下請け）・検索語の規律を渡す。全部緑なら implementer の座だけ（下請けの道）
  - 元: works/blk-fix/lib/fixrules.py の `SEAT_棚卸しの決まりS`・`g1_values`・`implementer_values`・`_g1_task`、works/.shared/core/seat.py の `g1_prompt`・`g1_section`
  - 今: 表
  - 証: tests/workflows/test_fix.py::FixLoopScriptsCase.test_fix_prep_writes_the_prompt_and_skips_without_duty、lib/tests/test_seat.py::SeatCase.test_g1_files_carry_the_works_rules_and_the_query_rule、lib/tests/test_fix_rules.py::BriefUnitsCase.test_dispatched_leaves_out_green_units、tests/workflows/test_fix.py::RolesCase.test_borrowed_skills_sit_on_the_seat_roles
  - 本物の run: 組の子の置き場の `g1-impl-1.md`・`g1-review-1.md`・`g1-1.patch`（TDD の輪が緑にしない単位が在る時。種に実行器が在れば輪が両方を緑にしやすく、下請けの道は通らないこともある）
  - 狭め: #94 で一度外し → マージ前の独立の目の指摘 8 で戻した（9a78226）。修正役の並べの枝の `REVIEW_EARLIER`・単位の worktree の引数は外したまま（枝が無い）。失う能力は無い

- F144 借りた superpowers の座（implementer・task-review・tdd・receiving-code-review）を、固定した写し（pin）と照らして指示書に埋め、無人の読み替え（unattended.md）を足す。写しが固定と違えば止める
  - 元: works/.shared/core/seat.py・works/.shared/core/spseam.py `pin_problems`・`fill`
  - 今: 表
  - 証: lib/tests/test_seat.py::SeatCase.test_copy_that_differs_from_the_pin_is_named、lib/tests/test_seat.py::SeatCase.test_fill_names_missing_holes、tests/bin/test_seat_borrow.py::SeatBorrowCase.test_pin_problems_match_the_launchers（lib の写しと起動の口が同じ行を返す）
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 修正役・TDD の役の指示書の座の節、run の隔離した設定の skills）
  - 狭め: 無し

- F145 借りた技（skills）を役に載せる: TDD の役に test-driven-development、手直しの役 2 つに receiving-code-review。載せた役は Skill の道具を持つ
  - 元: works/blk-fix/blk-fix.yaml:188、works/blk-refix/blk-refix.yaml:64・332
  - 今: 表
  - 証: tests/workflows/test_fix.py::RolesCase.test_borrowed_skills_sit_on_the_seat_roles
  - 本物の run: Archon の節の起動の記録（skills）
  - 狭め: 無し

- F146 役の模型・effort・会話の文脈（context）・設定の読み元・sandbox を元の works と同じにする
  - 元: works/blk-fix/blk-fix.yaml・blk-refix.yaml・blk-delta.yaml・blk-lens.yaml の各役
  - 今: 表
  - 証: tests/workflows/test_fix.py::RolesCase.test_roles_keep_the_original_model_and_session_settings
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば Archon の節の起動の記録（model））
  - 狭め: 無し

- F147 修正役が読んだ証拠（読んだファイルの記録 record-read.py と、読むべき物を読んだかの照らし reads.py・節 fix-reads）
  - 元: works/.shared/core/reads.py・record-read.py、works/blk-fix/scripts/reads.py、works/blk-fix/blk-fix.yaml:2029 の節 fix-reads
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_fix_reads_names_what_the_fixer_did_not_read・tests/workflows/test_fix.py::BlockScriptsCase.test_fix_reads_without_the_record_says_why_and_does_not_fail
  - 本物の run: 修正役の置き場の `reads-fix.json`・`reads-fix-ruled.json` と索引 `reads-fix-block.json`
  - 狭め: 元は collect の返りの reads_file で出口に出した。今は区分 P（plan-reads・review-reads）と同じく置き場に書くだけで、fix の出力に欄を足していない（読み手の報告は区分 R）

- F148 受け付けた changes と単位ごとの件数を置き場に書き、空の changes は外れた単位の無い置き場では止める（直す義務が残らず外れた単位だけの run だけ空を通す）
  - 元: works/.shared/core/recount.py:150 `collect`
  - 今: 無し（表）
  - 証: tests/workflows/test_fix.py::FixLoopScriptsCase.test_third_reject_gives_up_only_the_named_unit・lib/tests/test_fix_seams.py::RecountSeamCase.test_accepts_real_fix_and_keeps_counts・tests/workflows/test_fix.py::BlockScriptsCase.test_assert_changed_refuses_empty_declaration・lib/tests/test_fix_seams.py::GroupScriptsSeamCase.test_changed_problem_and_declared_files
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 組の子の置き場の `fix-reply.json`・`coverage-after.json`・`assert-changed.json`）
  - 狭め: 無し

- F149 修正役の返答の型（changes の行の欄・fix_closure・interactions・6 つの印・plan_faces・wrote_refs・conflicts・consult・bash_writes）を Archon の出力の型で照らす
  - 元: works/.shared/core/recount.py の `FIX_OUTPUT_FORMAT`・`fix_output_format`（節の写しの schema）
  - 今: 表
  - 証: tests/workflows/test_fix.py::RolesCase.test_fix_reply_shape_matches_the_original（元の欄は試験の定数 FIX_REPLY_ORIGINAL）
  - 本物の run: 節 fixer の出力
  - 狭め: 無し（試験の欠け）

B の数: 50 行 / 今が無し 5（F106・F107・F130・F136・F147）/ 証が要追加 17 / 狭め不可でない（戻す）2（F106・F130）、持ち主へ 4（F102・F107・F136・F147、F128 の読了の記録）

## C. 食い違いの申し出・裁定・範囲の相談・人の関所の答え（F200〜）

置き場: 組の子の run の申し出は子の置き場 `fix/fix/conflicts.json` に積まれ（`lib/fixboard.py:1557` `take_conflicts` → `conflict.park`）、親の節 conflict-check が組の結果を集めて親の置き場 `fix/fix/conflicts.json` に移す。裁定の文は親の置き場の `conflict-rulings.md`（`conflict.RULINGS_FILE`）、裁定役の指示書は `prompt-rule.md`・作業ツリーの控えは `rule-tree.json`（`lib/ruling.py:47-48`）、範囲の相談の状態は `consult-<pass>.json`・`consult.json`（`lib/consult.py:64・73`）、人の関所の一言は `human-notes.md`（`lib/fixboard.py` `NOTES_FILE`）。種（stats.py の mean・clamp）の健全な run では申し出・裁定・相談は起きにくく、ほとんどの行は筋書きでのみ見える。

- F200 修正役（と TDD の輪の役）は、緑にするためにテスト・依頼・コードを曲げる代わりに、食い違いの申し出（conflicts[]: unit_key・between・why_both_cannot_hold・which_is_right・kind）を返してよい。申し出は拒否に数えず、その単位だけを止め、ほかの単位は進む（keep-essence の 8）
  - 元: works/.shared/core/conflict.py:1-12（モジュールの頭）・:539 `park`、works/blk-fix/scripts/accept.py:18-24
  - 今: 表
  - 証: tests/workflows/test_fix.py::FixLoopScriptsCase.test_first_pass_conflict_leaves_the_loop_for_ruling、lib/tests/test_fix_seams.py::ConflictSeamCase.test_park_writes_and_reads_the_places_json
  - 本物の run: 筋書きでのみ（起きれば子と親の置き場の conflicts.json と trace.jsonl の conflict.PARK_OP の行）
  - 狭め: 無し

- F201 申し出の種類（kind）は 6 つ（brief_vs_judgment・unnamed_test_broke・not_red・scope_needed・query_hits_fixed・needs_context）のどれかで必須、which_is_right と対になる（query_hits_fixed ⇔ query、needs_context ⇔ unknown）
  - 元: works/.shared/core/conflict.py:112-120・:260 `_kind_problem`
  - 今: 表
  - 証: lib/tests/test_conflict_kinds.py::KindCase.test_kind_is_a_required_field、lib/tests/test_conflict_kinds.py::KindCase.test_kind_and_which_must_pair
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F202 申し出が名指した箇所（`<パス>:<行>`。依頼の行・テストの行・コードの行を 2 つ以上）が現物に在るかを機械が確かめ、無ければ申し出として扱わず普通の拒否（3 回の枠に数える）にする
  - 元: works/.shared/core/conflict.py:322 `_entry_problems`、works/blk-fix/scripts/accept.py:19-20
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_fake_citation_is_a_normal_reject
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（試験の欠け。#94 は ConflictBoardCase の子を外した）

- F203 直す義務の外の単位の申し出・申し出た単位を changes にも書いた返答を拒む
  - 元: works/.shared/core/conflict.py:322 `_entry_problems`（owed）、works/blk-fix/scripts/accept.py:19-20
  - 今: 表
  - 証: lib/tests/test_conflict_kinds.py::FixAcceptSeamCase.test_conflict_unit_also_in_changes_is_rejected
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F204 brief_vs_judgment の申し出は、その単位の brief の行を between に名指す（brief の無い run・単位なら拒む）
  - 元: works/.shared/core/conflict.py:275 `brief_cite_problem`・:294 `_brief_problem`
  - 今: 表
  - 証: lib/tests/test_conflict_kinds.py::BriefKindCase.test_brief_kind_needs_the_units_brief
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F205 which_is_right: query の申し出は correct_lines（直した後の正しい行の写し）を要し、判定者の問いが correct_lines に当たることを機械が試す
  - 元: works/.shared/core/conflict.py:247 `_correct_problem`（try_query）
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_fixer_query_claim_tries_the_judge_query
  - 本物の run: 筋書きでのみ
  - 狭め: → #121 で戻した

- F206 同じ申し出は積み増さない。裁定がもう外した単位の申し出は、出し直されても知っている申し出として確かめずに外す
  - 元: works/.shared/core/conflict.py:539 `park`、works/blk-fix/scripts/accept.py:22-23
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_resent_claim_on_a_ruled_unit_is_dropped
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F207 1 回目（first）に裁かれていない申し出が在れば、積んだ誤りが在っても修正の輪を抜けて裁定へ回す（申し出の回の返答は fix-parked-reply.json に控える）。裁定の後（ruled）の新しい申し出は機械が ask_human に裁いて積み、拒否の後も残す
  - 元: works/blk-fix/scripts/accept.py:18-24・:646-649
  - 今: 表
  - 証: tests/workflows/test_fix.py::FixLoopScriptsCase.test_ruled_new_claim_is_parked_as_ask_human（名を変えた: FixAcceptSeamCase は tests/workflows/test_fix.py に無い）
  - 本物の run: 筋書きでのみ（起きれば子の置き場の fix-parked-reply.json）
  - 狭め: 無し

- F208 組を戻した後、組の子の申し出を親の置き場に集め、名指した行が親の作業ツリーに無くなった申し出（ほかの組の直しで消えた行）は落として名指す。裁く申し出が在る時だけ裁定の輪を回す
  - 元: 無し（元は 1 つの盤面に直に積んだ。枝の申し出は tdd_join・fix_join が盤面へ。works/tests/test_blk_fix_conflict.py:508 test_join_script_parks_lane_conflicts）
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_conflict_check_gathers_child_claims_and_goes
  - 本物の run: 節 conflict-check の出力 go（健全な run は false）
  - 狭め: 無し

- F209 読むだけの裁定役が、裁いていない申し出に 1 件ずつちょうど 1 度、5 つの裁定（fix_test_scope・fix_code_as・ask_human・replace_query・fix_plan_item）のどれかで答える。fix_test_scope の範囲が現物に在る・ask_human の根拠は依頼の行か探した跡、を機械が照らす
  - 元: works/blk-fix/lib/ruling.py `problems`・`grounds_problems`・`limit_problem`、works/blk-fix/rules/ruler.md
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RulingSeamCase.test_accept_rule_applies_rulings_to_the_place、lib/tests/test_fix_units.py::GroundsCase.test_ask_human_needs_request_line_or_search・lib/tests/test_fix_units.py::GroundsCase.test_grounds_are_checked_against_the_tree
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F210 裁定役が作業ツリー・HEAD・枝・無視されるファイルを変えたら、その返答を拒む（読むだけの役を機械が照らす）
  - 元: works/blk-fix/lib/ruling.py の accept_rule（READONLY）
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RulingSeamCase.test_accept_rule_rejects_then_gives_up_to_the_human
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F211 裁定役の返答が通らなければ理由をファイルに書いて次の回の指示書に名指し、3 回目も通らなければ裁く申し出の全部を「決められない」として ask_human に裁いて人に回す
  - 元: works/blk-fix/lib/ruling.py の GIVE_UP_AFTER・accept_rule
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RulingSeamCase.test_accept_rule_rejects_then_gives_up_to_the_human、tests/workflows/test_fix.py::FixLoopScriptsCase.test_rule_loop_writes_the_reject_and_names_it_next、tests/workflows/test_fix.py::RolesCase.test_loops_keep_the_original_bounds（rule-loop の max_iterations）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F212 裁定 replace_query は、新しい問いを例（hits に全部当たる・misses に当たらない・申し出の correct_lines に当たらない）で機械に試させてから置き換える（Semgrep の規則の試験の形）。which_is_right が query の申し出だけに裁ける
  - 元: works/blk-fix/lib/ruling.py の query_problems
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RulingSeamCase.test_replace_query_is_tried_on_hits_misses_and_correct_lines
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（試験の欠け）

- F213 裁定 fix_plan_item（承認済みの修正案の項目そのものが誤り）: 範囲 limits を持たず、根拠にその単位の brief の行を名指し、機械が plan_items（brief の項目の番号）と plan_units（その項目に載る単位の全部）を足す。項目の単位の全部を直す義務から外し、案の直しを待つ（WAITING）
  - 元: works/.shared/core/conflict.py:103・146-151・585 `apply_rulings`、works/blk-fix/lib/ruling.py `plan_item_fix_problems`・`plan_item_units`
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::RulingSeamCase.test_fix_plan_item_needs_brief_grounds_and_no_limits
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（試験の欠け）

- F214 案の直しの状態の移りは 1 か所（set_replan）だけ: WAITING → AMENDED（項目を直した。単位は直す義務に戻る）か GAVE_UP（諦めた。ask_human の行として並ぶ）。違う移りは誤り、同じ状態は何もしない
  - 元: works/.shared/core/conflict.py:433 `set_replan`
  - 今: 表
  - 証: lib/tests/test_conflict_kinds.py::TestReplanState（9 本。例 lib/tests/test_conflict_kinds.py::TestReplanState.test_bad_transition_is_board_gap・lib/tests/test_conflict_kinds.py::TestReplanState.test_amended_rows_return_units_to_duty）、lib/tests/test_fix_seams.py::ConflictSeamCase.test_ask_human_is_asked_and_amended_returns_to_duty
  - 本物の run: 筋書きでのみ（案の直しは線が plan を回し直して refix の別の置き場で直し、その支度が 1 回目の段の待つ行を写す時に AMENDED へ移す: lib/conflict.py::adopt_prior）
  - 狭め: F216 を参照

- F215 fix_plan_item の裁定の項目の番号を返り replan_items で線へ返し、線が案の直しと 2 回目の修正（only_items の単位だけ）を差し込む
  - 元: works/.shared/core/replan.py（同じ run の中で案の役が項目だけを直し、事前審査と人の関所 replan-gate を通して 2 回目の修正の段へ）
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_collect_plan_item_ruling_and_objection、tests/workflows/test_fix.py::BlockScriptsCase.test_prep_only_items_keeps_their_units
  - 本物の run: 節 `fix` の出力 replan_items（健全な run では []）
  - 狭め: 無し（線との分担が変わった）

- F216 2 回目の修正（線の include `refix`）が 1 回目の修正の申し出と裁定を見る（conflict.second_pass）: 1 回目の段で fix_test_scope の範囲として許したテストの変更を 2 回目の段の事後の関門と凍結も許す、2 回目の段で新しく fix_plan_item と裁いた行に「最後の人の関所で決める」の約束（LATE_REPLAN_PROMISE）を出す、直した項目の単位の前の輪の受け入れのテストを許す（AMENDED_TEST_ID）
  - 元: works/.shared/core/conflict.py:411 `second_pass`・:641 `write_rulings`（LATE_REPLAN_PROMISE）・:915 `test_permits`（amended の許し）、works/blk-fix/lib/fixgates.py（second_pass で裁定の範囲を引く）
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_refix_place_reads_the_first_pass_rulings・tests/workflows/test_fix.py::RefixCase.test_refix_sees_first_pass_rulings・tests/workflows/test_fix.py::GroupChildScriptsCase.test_refix_child_sees_the_first_pass_and_returns_only_its_rows・tests/workflows/test_fix.py::InputsCase.test_plan_review_is_an_input（線の配線）。部分 0 の時の証（そのまま残す）: lib/tests/test_conflict_kinds.py::TestReplanWords.test_second_pass_new_replan_rows_promise_the_last_gate と lib/tests/test_fix_gates.py::TestTestEdits.test_ruled_limit_passes_after_ruling の second_pass の試験は、AMENDED の行を手で置いた盤面で回るので、線の上で働かないことを捕まえない
  - 本物の run: 筋書きでのみ（申し出 → fix_plan_item → 案の直し → refix-run の筋。refix-run の置き場 `fix/refix-run/conflicts.json` に 1 回目の行が無いことで見える）
  - 狭め: #94 で狭めた（「約束を変える頼み」2、PR #94 の 2 回目の直しのコメント「線との約束の変えなので線の後の issue で扱う」）。Archon で不可でない（入力を 1 つ足して `$fix.output.conflicts` の指し札を渡すだけ。#74 の head/workflows/line/works-factory-line.yaml:484-485 は replan に既に同じ値を渡している）→ 戻す → 部分 D1 で戻した

- F217 裁定の後の修正（fix-ruled）: 直す裁定（fix_test_scope・fix_code_as・replace_query）が在る時だけ起こし、裁定の文のファイルと申し出の回の返答（fix-reply.json）を指示書に名指す。受け付けは裁定の範囲で広げ、組の TDD の輪の状態で凍結と変更に当たる試験を見る
  - 元: works/blk-fix/blk-fix.yaml:1828-1990（fix-ruled-loop）、works/blk-fix/lib/fixrules.py の ruled の prep
  - 今: 表
  - 証: tests/workflows/test_fix.py::FixLoopScriptsCase.test_fix_ruled_prep_without_fix_ruling_does_not_launch、tests/workflows/test_fix.py::FixLoopScriptsCase.test_fix_ruled_prep_names_the_saved_reply_and_rulings、tests/workflows/test_fix.py::FixLoopScriptsCase.test_ruled_pass_allows_ruled_test_scope_and_first_does_not、tests/workflows/test_fix.py::GroupChildScriptsCase.test_ruled_accept_runs_the_tests_of_the_tdd_state_the_join_copied、lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_ruled_reply_line_once_after_the_title
  - 本物の run: 筋書きでのみ（起きれば親の置き場の fix-ruled-reply.json）
  - 狭め: 下の F218

- F218 裁定の後の修正役は、1 回目の修正役の会話の続きで起こす（元の印 `continue=fix`）
  - 元: works/blk-fix/blk-fix.yaml:1864-1885（節 fix-ruled の description「修正役の会話の続き」と印 `works-node: fix-ruled continue=fix`）、works/tests/test_blk_fix_conflict.py:619 TestYaml.test_fix_ruled_loop_continues_the_fixer
  - 今: 表
  - 証: tests/workflows/test_fix.py::FixLoopScriptsCase.test_fix_ruled_prep_names_the_saved_reply_and_rulings が代わりの道を縛る
  - 本物の run: 筋書きでのみ
  - 狭め: #94 で狭めた（「能力の狭め」1 行目）。Archon で不可: 継ぐ相手の修正役は組の子の run（別の run）の中で回り、fix-ruled は親の run の loop_group の中に在る。Archon の名指しの継ぎ（`context: {resume: <節>}`）は loop_group の中では使えない（Archon packages/workflows/src/loader.ts:1173-1175「context.resume inside a loop_group body, which is not supported」）うえ、継ぐ元は同じ static scope の上流の節に限る（:1176-1186）。保存した返答を読ませる今の形が取れる最も近い道 決め: 継がない。保存した返答を読む新しい会話で回す（docs/owner-decisions.md の「導いた事」の 2026-10-12 の推しの決め。Archon loader.ts:1173-1175）。狭めとして確定（線の配線の文書の「この文書の外」の「決めた物」）

- F219 範囲の相談: 修正役は承認済みの修正案の項目の範囲の外を consult の欄で頼める。機械が先に頼みを確かめ（項目が在る・根の外でない・もう範囲の中でない。案の out_of_scope に当たる物は名指して回す）、通った頼みだけを答えの役に聞く
  - 元: works/blk-fix/lib/consult.py の screen・question・ask（:556）、works/blk-fix/scripts/consult_check.py
  - 今: 表
  - 証: lib/tests/test_consult.py::ScreenCase.test_refusals、lib/tests/test_consult.py::ScreenCase.test_out_of_scope_is_forwarded、lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_consult_ask_screens_and_writes_the_question、tests/workflows/test_fix.py::FixLoopScriptsCase.test_consult_check_launches_the_answer_on_an_ask
  - 本物の run: 筋書きでのみ（起きれば子の置き場の consult-first.json の行と節 consult-answer の起動）。筋書き `group-consult`（workflows/fix/fixtures/group-consult.stubs.yaml）が通す
  - 狭め: 無し

- F220 答えの役は allow・deny・defer で答え、許すのは頼んだ物に切り詰めたパスとテスト（新しいテストは赤の種類つき）だけ。deny・defer は何も許さない。答えの形が崩れていれば無効。答えは trace に残り、合意は範囲の照らしとテストの変更の許しが読む
  - 元: works/blk-fix/lib/consult.py の judge・settle、works/.shared/core/conflict.py:874 `agreed`
  - 今: 表
  - 証: lib/tests/test_consult.py::JudgeCase.test_grant_is_cut_to_what_was_asked、lib/tests/test_consult.py::JudgeCase.test_deny_and_defer_grant_nothing、lib/tests/test_consult.py::JudgeCase.test_malformed_answers_are_invalid、lib/tests/test_consult.py::FlowCase.test_allow_round_trip、lib/tests/test_fix_seams.py::ConflictSeamCase.test_plan_asks_read_the_places_trace
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F221 範囲の相談の枠は段の輪ごとに決まった回数（consult.BUDGET）。使い切った後は聞かない（受け付けが拒む: F101）。相談の行に周の番号を書く。答えの役が答えられない・答えが無い行も記録する
  - 元: works/blk-fix/lib/consult.py の BUDGET・left
  - 今: 表
  - 証: lib/tests/test_consult.py::FlowCase.test_budget、lib/tests/test_consult.py::FlowCase.test_round_is_written_on_rows、lib/tests/test_consult.py::FlowCase.test_unavailable_rows_are_recorded、lib/tests/test_consult.py::FlowCase.test_missing_or_broken_answer、tests/workflows/test_fix.py::RolesCase.test_loops_keep_the_original_bounds（fix-loop の max_iterations 12 = 3 + 枠）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F222 範囲の相談に答える役は、修正案を書いた役の会話の続きで答える（元の印 `continue=fix-planner`。包みが修正案の役の会話の id を alias して --resume する）
  - 元: works/blk-fix/blk-fix.yaml:1628-1660（節 plan-answer の description「修正案を書いた会話の続き」）、works/blk-fix/lib/consult.py:8-11・:78 `PEER`・:450 `alias`、works/tests/test_consult.py の AliasCase・SelfResumeCase
  - 今: 表
  - 証: tests/workflows/test_fix.py::FixLoopScriptsCase.test_consult_check_launches_the_answer_on_an_ask が代わりの道を縛る
  - 本物の run: 筋書きでのみ
  - 狭め: #94 で狭めた（「能力の狭め」1 行目）。Archon で不可: 修正案の役は plan のブロック（線の別の include）に在り、consult-answer は fix-loop の loop_group の中（しかも組の子の run の中）に在る。Archon の名指しの継ぎは loop_group の中では使えない（Archon packages/workflows/src/loader.ts:1173-1175）うえ、継ぐ元は同じ static scope の上流に限る（:1176-1186）。元の継ぎは works の Claude の包み（adapter）の --resume で、Archon の上には同じ口が無い 決め: 継がない。保存した返答を読む新しい会話で回す（docs/owner-decisions.md の「導いた事」の 2026-10-12 の推しの決め。Archon loader.ts:1173-1175）。狭めとして確定（線の配線の文書の「この文書の外」の「決めた物」）

- F223 直す前の人の関所の続けの一言（条件）は、範囲の相談の頼みとして答えの役に聞く（出どころ gate）。前の周の一言も読める
  - 元: works/blk-fix/lib/consult.py:490 `gate_notes`・:498 `gate_asks`、works/darkfactory/lib/line_edge.py の h-fix
  - 今: 表
  - 証: lib/tests/test_consult.py::FlowCase.test_human_gate_condition_is_asked、lib/tests/test_fix_seams.py::GateItemsSeamCase.test_pass_word_with_text_becomes_a_note、lib/tests/test_fix_seams.py::GateItemsSeamCase.test_no_note_without_text_or_on_stop
  - 本物の run: 線の関所 gate-before-fix で人が一言を書いた時だけ（健全な無人の run では起きない）→ 筋書きでのみ
  - 狭め: 無し

- F224 直す前の人の関所の答えを直す義務に効かせる: 答えていない問い（fork・escalate）の出どころと depends を直す義務から外し（withheld_by）、答えた問いの出どころを戻し（returned）、一言と戻った単位の行を human-notes.md にして修正役と TDD の役の notes_file に渡す
  - 元: works/.shared/core/conflict.py:676 `owed_units_but_asked`、works/darkfactory/lib/line_edge.py:1218 の h-fix（notes_file）、works/.shared/core/gatemarks.py の withheld_by・returned・returned_lines
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_prep_takes_the_gate_answers_into_the_duty、lib/tests/test_fix_seams.py::ConflictSeamCase.test_withheld_and_returned_are_arguments、tests/workflows/test_fix.py::GroupChildScriptsCase.test_fix_prep_names_the_gate_notes、tests/workflows/test_fix.py::GroupChildScriptsCase.test_tdd_prep_names_the_gate_notes
  - 本物の run: 親の置き場の answers.json と human-notes.md（関所が開いた run だけ）
  - 狭め: 無し（fix の側）。線の側は F225

- F225 関所の continue を問いへの答えに数えるには、関所の答えに「人が見た関所の行」（asked）が要る。線はこれを fix の answers に付けて渡す
  - 元: works/darkfactory/lib/line_edge.py（盤面の human_items に関所の行を記録した）
  - 今: 表
  - 証: tests/workflows/test_line.py::FixWiringCase.test_gate_before_fix_answer_carries_asked（部分 B1）
  - 本物の run: 線の節 answer-before-fix の出力 answer に asked が無いこと（関所が開いた run）
  - 狭め: #94 の申し送り（「人が入れる直しの頼み」4 つ目）。線（#74）で直す。Archon で不可でない（script の返りに欄を足すだけ）→ 戻す → 部分 B1 で戻した

- F226 直す裁定でない裁定（ask_human・fix_plan_item）を受けた単位は、決まり 1 つ（held_by_rulings）で直す義務から外し、理由を並べる。人に回した単位を直そうとした返答は外れた理由を名指して拒む
  - 元: works/.shared/core/conflict.py:475 `held_by_rulings`・:696 `fix_duty`
  - 今: 表
  - 証: lib/tests/test_conflict_kinds.py::HeldByRulingsCase.test_one_rule_with_sorted_reasons、lib/tests/test_fix_seams.py::ConflictSeamCase.test_ruling_leaves_duty_and_fix_plan_item_gets_replan。拒む配線は B の F105
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F227 裁定の文のファイル（conflict-rulings.md）を、裁定ごとに約束の文（範囲の中だけで直す・人に回した単位の直しは条件つきで残す・諦めた行は最後の関所へ・2 回目の段の新しい案の直しは最後の関所へ）つきで書き、修正役に渡す。裁定の範囲は「足す道だけ」と言う
  - 元: works/.shared/core/conflict.py:607-675 `write_rulings`
  - 今: 表
  - 証: lib/tests/test_conflict_kinds.py::TestReplanWords（8 本。例 lib/tests/test_conflict_kinds.py::TestReplanWords.test_ask_human_promise_keeps_held_work_conditionally）、lib/tests/test_conflict_kinds.py::RulingLimitsTextCase.test_rulings_file_says_only_ruled_paths_widen
  - 本物の run: 筋書きでのみ（親の置き場の conflict-rulings.md）
  - 狭め: 無し

- F228 テストの変更の許しの道は 1 本（conflict.test_permits）: 承認済みの修正案の rewrite_tests と removes・範囲の相談の合意・裁定 fix_test_scope の範囲・案の直しで直した項目の単位。凍結の検査・事後の関門・範囲の照らし・最後の関所はここから引く。修正案の欄の控えが凍結の印と食い違えば許しを引かずに止める（keep-essence の 3 の許しの側）
  - 元: works/.shared/core/conflict.py:915 `test_permits`・:817 `fields_broken`・:848 `frozen_fields`
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::ConflictSeamCase.test_permits_read_the_frozen_fields_in_the_place、lib/tests/test_conflict_kinds.py::TestReplanState.test_permit_sources_are_read_in_one_place、lib/tests/test_fix_seams.py::FixgatesSeamCase.test_broken_fields_are_a_value_error、lib/tests/test_blk_fix_conflict.py::TestPermitsOnRawBoard.test_trailing_slash_id_names_the_class_at_plan_and_frozen_time、tests/workflows/test_fix.py::FixLoopScriptsCase.test_ruled_pass_allows_ruled_test_scope_and_first_does_not
  - 本物の run: 筋書きでのみ（修正案が rewrite_tests を名指した run なら許しが働く）
  - 狭め: 無し（凍結の照らしそのものは A の行）

- F229 許したテストの変更を理由つきで最後の人の関所に並べる → E の F429 で数える（ここでは数えない。lib/conflict.py の `ruled_test_doc` は残るが呼び手が無いことだけ書き添える）

- F230 人に回した申し出（ask_human と諦めた fix_plan_item）の行を裁定の文のまま最後の人の関所に並べ、その時だけ関所を開ける → E の F426 で数える（ここでは数えない）。報告の側は指し札を読んで件数・内訳・次の依頼の行を出す（lib/runreport.py:501-505・615-617、lib/outcome.py:199）ので、狭めは線の最後の関所だけ

- F231 人に回した単位は直す義務の外で、残りの単位で受け付けを進める（run は止めない）
  - 元: works/tests/test_blk_fix_conflict.py:334 test_asked_unit_is_not_owed_and_board_takes_the_rest
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::ConflictSeamCase.test_ask_human_is_asked_and_amended_returns_to_duty、tests/workflows/test_fix.py::BlockScriptsCase.test_collect_takes_units_fixed_after_ruling
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F232 範囲の相談の行の番号を振る錠（consult._id_lock）
  - 元: works/blk-fix/lib/consult.py:589 `_id_lock`（並べの枝が同じ盤面に書くため）
  - 今: 無し（表）
  - 証: tests/workflows/test_fix.py::GroupsCase.test_no_fixed_lanes_and_no_queue_in_scripts（錠と列が無いこと）
  - 本物の run: 無し
  - 狭め: 持ち主の決め no-queue による外し。守っていた物（同じ置き場への同時の書き）は今の形で起きないので能力は落ちない

- F233 申し出の数と種類・裁定の内訳を報告に出す
  - 元: works/.shared/core/conflict.py:517 `counts`・:529 `kind_counts`、works/.shared/core/report.py の `_conflict_line`
  - 今: 表
  - 証: lib/tests/test_conflict_kinds.py::KindRowsCase.test_park_keeps_kind_and_traces_it、lib/tests/test_conflict_kinds.py::KindRowsCase.test_rows_without_kind_still_read。報告の行は report のブロックの試験（lib/tests/test_runreport.py）の範囲
  - 本物の run: 報告の文の「申し出」の行（申し出の無い run では 0 件の行か無し）
  - 狭め: 無し

C の数: 32 行（F229・F230 は E への参照で数えない）/ 今が無し 3（F218・F222 は新しい会話で代わり、F232 は外し）/ 証が要追加 15 / 狭め不可でない（戻す）3（F205・F216・F225）、Archon で不可 2（F218・F222）

## D. 修正の差分の審査・レンズ・手直し（F300〜）

置き場（本物の run の記録）: 差分の審査・レンズ・手直しはブロックの形（mode ""）の親の run だけで回り、置き場は親の run の成果物の置き場の `fix/fix/`（2 回目の修正の include なら `fix/refix-run/`）。主なファイルは `loop-fix_delta.json`（1 回目の差分）・`review1-brief.json`（審査役の材料）・`review1-seat.md`（task-review の座）・`out-p3.delta_review.json`（受けた審査）・`delta-verdicts.json`（準拠と品質の 2 判定）・`delta/review-1.json`・`delta/review-2.json`（{pass, owed, reply_file}）・`delta/skipped.json`（軽量で省いた理由）・`depth-raised.json`・`lens.json`・`prompt-lens-<key>.md`・`refix1-brief.json`・`refix1-head.json`・`reject-<節>-<k>.md`。種（stats.py の 2 つの欠陥）を厚み「標準」で回すと、計画の深さが全部の単位で標準に固定される（lib/depth.py の forced の語。lib/tests/test_depth.py::DecideCase.test_forced_word_fixes_every_unit）ので、assert-changed が通れば差分の審査は健全な run でも必ず走る。手直し（refix）は審査役が穴を挙げた時だけ起きる。

- F300 修正だけの差分（run の始めの木 → 今の作業ツリー。未追跡を含み、.gitignore に当たる物・バイトコードは除き、日本語のファイル名も拾う）を切って置き場に置く
  - 元: works/.shared/core/graphloops/rules/review-loop.py:1567 `fix_delta`、works/blk-delta/scripts/cut.py
  - 今: 表
  - 証: lib/tests/test_blk_tests_delta.py::TestDeltaPlace.test_cut_writes_the_fix_only_diff_and_brief、lib/tests/test_blk_tests_delta.py::TestDeltaPlace.test_cut_untracked_japanese_bytecode、lib/tests/test_blk_tests_delta.py::TestDeltaPlace.test_cut_needs_the_start_rev
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 置き場の `loop-fix_delta.json`（{file, files, rev, base}）と差分のファイル。健全な run で files = ["stats.py"]）
  - 狭め: 無し

- F301 差分の審査役の材料（brief）に、差分・触ったファイル・守りのファイルに当たった物（protected_files）・承認済みの修正案の項目（案の直しを待つ項目は held の印つき）・裁定が広げたパス（ruled_paths）・修正役の報告（fix_report の changes と not_done）・人の方針・レンズの行・座のファイルを載せる
  - 元: works/.shared/core/refix.py `cut`（元 194）、works/blk-delta/scripts/cut.py
  - 今: 表
  - 証: lib/tests/test_blk_tests_delta.py::TestDeltaPlace.test_cut_brief_lists_protected_files、lib/tests/test_blk_tests_delta.py::TestDeltaPlace.test_cut_brief_carries_plan_items_and_fix_report、lib/tests/test_blk_tests_delta.py::TestDeltaPlace.test_cut_brief_marks_held_items_and_ruled_paths、tests/workflows/test_fix.py::DeltaScriptsCase.test_cut_review_refix_rejects_outside_the_range_then_accepts
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 置き場の `review1-brief.json` の protected_files・plan_items・ruled_paths・fix_report・lens・seat_file）
  - 狭め: 無し

- F302 差分の審査役の材料の `out.p2.plan_review`（事前審査が予測した穴 faces・別案 shrink）が、本物の run では常に null。そのため 1 回目の審査の検算（修正役が absorbed と答えた事前審査の穴が差分で本当に塞がったか。checks）は 1 件も起きず、手直しの brief の名札（hole_ties）からも事前審査の穴が落ちる
  - 元: works/.shared/core/graphloops/graphs/review-loop.json の p3.delta_review の reads（`out.p2.plan_review`・`out.p3.fix.plan_faces`）、review-loop.py:3129-3138 `_closed_keys`・`_claimed_closed`、works/.shared/core/holeties.py:94 `tie` の plan_faces
  - 今: 表
  - 証: tests/workflows/test_fix.py::DeltaScriptsCase.test_delta_cut_passes_the_plan_review_to_the_brief
  - 本物の run: `review1-brief.json` の reads["out.p2.plan_review"] が null、受けた審査 `out-p3.delta_review.json` の checks が [] であること（事前審査が穴を挙げた run でも）
  - 狭め: #94 で狭めた（「能力の狭め」の out.p2.plan_review の行、「約束を変える頼み」3）。Archon で不可でない（fix の include の `with:` に入力を 1 つ足し、線が `$plan-review.output` を渡すだけ。Archon packages/workflows/src/schemas/dag-node.ts:1325-1330）→ 戻す（B の F130 と同じ直しで両方が戻る） → 部分 D1 で戻した

- F303 差分の審査の返答の照らし: 穴の key は一意、where はこの往復の差分が触ったファイル、cite はそのファイルの今の姿に在る字列、穴を挙げないなら faces_none（下限の字数）に何を読んで無いと言えるかを書く
  - 元: review-loop.py:3141-3171 `delta_review_output`
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::DeltaSeamCase.test_delta_review_problems_check_where_cite_and_checks、tests/workflows/test_fix.py::DeltaScriptsCase.test_third_rejection_gives_up_and_unknown_keys_are_rejected
  - 本物の run: 拒否が在れば `reject-delta-accept-<k>.md`。健全な run は通って `out-p3.delta_review.json` が在る
  - 狭め: 無し

- F304 差分の審査の穴の kind が事前審査だけの語（regression・policy は後の工程が人に聞く、precedent は判定者の先行例が渡っていない）なら拒む
  - 元: review-loop.py:3152-3160（HUMAN_FACE_KINDS・PLAN_ONLY_FACE_KINDS）
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::DeltaSeamCase.test_delta_review_rejects_every_plan_only_kind
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（試験の欠け）

- F305 読むだけの審査役が作業ツリーを変えたら、受け付けが拒む（切りの時に撮った写しと比べる）
  - 元: works/.shared/core/entry.py:1228 `READONLY_MOVED`、works/blk-delta/scripts/accept.py
  - 今: 表
  - 証: lib/tests/test_blk_tests_delta.py::TestDeltaPlace.test_review_readonly_tree_changed、lib/tests/test_blk_tests_delta.py::TestDeltaPlace.test_accept_review_needs_the_snapshot
  - 本物の run: 筋書きでのみ
  - 狭め: 無し。ただし元の `TestSnapshotNestedRepo.test_untracked_nested_repo_does_not_crash`（works/tests/test_blk_tests_delta.py:916。作業ツリーに未追跡の入れ子のリポジトリが在っても写しが落ちず、入れ子の中身の変化を見る）は #94 で外れ、写し先が無い → 要追加: lib/tests/test_blk_tests_delta.py::TestDeltaPlace.test_untracked_nested_repo_does_not_crash_the_snapshot

- F306 1 回目の審査だけが準拠（compliance: 修正案の項目ごとの pass・fail・unverifiable）と品質（quality: 項目に結ばない穴が在れば fail）の 2 判定を返し、受け付けが項目と照らして欠け・食い違いを拒み、受けた時だけ欄を外して控える（修正案の無い run は not_applicable、案の直しを待つ項目は held で fail にできない）
  - 元: works/.shared/core/deltamarks.py（`gaps`・`split`・`save`）、works/.shared/core/refix.py の accept_review
  - 今: 表
  - 証: tests/workflows/test_fix.py::RolesCase.test_verdicts_only_on_the_first_review
  - 本物の run: 置き場の `delta-verdicts.json`（{round, compliance, quality}）
  - 狭め: 無し（試験の欠け）

- F307 手直しが答える義務 = 審査の穴（faces）と、塞いだと言われたのに差分で塞がっていない検算（checks の closed=false）。変異の検算の見逃しは入れない。義務が 0 件なら手直しの役を起こさない
  - 元: review-loop.py:569-579 `_owed_rows`・:582 `delta_owed`・:641 `delta_faces_open`
  - 今: 表
  - 証: lib/tests/test_blk_refix.py::RefixCase.test_owed_rows_come_from_the_accepted_review、lib/tests/test_blk_refix.py::RefixCase.test_review_none_owes_nothing、tests/workflows/test_fix.py::DeltaScriptsCase.test_not_launched_roles_are_done
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば `delta/review-1.json` の owed と、refix の節が起きたか（Archon の節の状態）。健全な run では審査役次第）
  - 狭め: 無し

- F308 手直しの返答は義務の key ごとに 1 度だけ答え（余り・欠け・重複を拒む）、fixed と答えた行は files を書く
  - 元: review-loop.py:3174-3184 `delta_fix_output`
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::DeltaSeamCase.test_delta_fix_problems_answer_every_owed_key_once
  - 本物の run: 手直しが起きた run の `reject-refix-accept-<k>.md`（拒否時）・`out-p3.delta_fix.json`
  - 狭め: 無し

- F309 手直しの変更のうち、修正の段が触ったファイル（1 回目の差分の files）の外を承認済みの修正案の項目の範囲で照らし、外れを拒む（修正の段の変更は手直しのせいにしない）
  - 元: works/.shared/core/refix.py:400 `accept_fix`
  - 今: 表
  - 証: lib/tests/test_blk_refix.py::RefixCase.test_refix_outside_plan_scope_rejected、lib/tests/test_blk_refix.py::RefixCase.test_refix_is_not_blamed_for_the_fix_files、lib/tests/test_blk_refix.py::RefixCase.test_refix_out_of_scope_glob_rejected、lib/tests/test_fix_seams.py::RefixSeamCase.test_accept_fix_rejects_change_outside_the_items_range、tests/workflows/test_fix.py::DeltaScriptsCase.test_cut_review_refix_rejects_outside_the_range_then_accepts
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F310 手直しの書き込みの出どころ: 変更が記録か bash_writes の申告に在るかを照らし、記録の無い run では段の頭の木からの変更が全部 handled[].files か bash_writes に在ることを求める
  - 元: works/.shared/core/refix.py:400 `accept_fix`（writes.check）
  - 今: 表
  - 証: lib/tests/test_blk_refix.py::RefixCase.test_refix_unrecorded_write_rejected_and_declared_write_passes、lib/tests/test_blk_refix.py::RefixCase.test_refix_without_record_notes_the_run、tests/workflows/test_fix.py::DeltaScriptsCase.test_refix_undeclared_write_is_rejected
  - 本物の run: 筋書きでのみ（審査役が直す義務を出して手直しが起きた run だけ、置き場に `refix1-head.json` を書く。書き込みの記録は PostToolUse のフックが置き場の `writes.jsonl` に書き（PR #178）、記録の無い run の道は記録の根の無い起動だけ）
  - 狭め: 記録の包みは #94 で落ちた（当時は U6 待ち。段 1b の U6 の決めで記録はフックが要ると分かり → PR #178 で戻した。B の F102 と同じ）

- F311 手直しの brief の穴ごとの名札（hole ties）: 穴を修正案の項目・単位・修正の changes・準拠の落ちた行・前の往復の穴（2 回目）に結び、どの枝の直しかを手直しの役に見せる
  - 元: works/.shared/core/holeties.py:94 `tie`・:154 `note`、works/.shared/core/refix.py の tie_items・hole_ties
  - 今: 表
  - 証: lib/tests/test_holeties.py::TieCase、lib/tests/test_blk_refix.py::RefixCase.test_compliance_fail_reaches_ties、lib/tests/test_blk_refix.py::RefixCase.test_review2_then_ties2
  - 本物の run: `refix1-brief.json` の ties（手直しが起きた時）。事前審査の穴の名札は、事前審査が穴を挙げた run だけ
  - 狭め: 無し（事前審査の穴の分は F302）

- F312 差分の審査の穴の名札を、報告と最後の人の関所に枝ごとの行として出す（report.branch_rows・holeties.count_line・holeties.lines）
  - 元: works/.shared/core/report.py:1016・1530-1547 `branch_rows`
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_collect_writes_delta_holes_and_lenses_beside_the_diff・lib/tests/test_runreport.py::CarryCase.test_refix_declared_and_second_fixed_holes_are_carried
  - 本物の run: 無し（報告に差分の審査の穴が出ない）
  - 狭め: #94（返りの約束）と #68（報告）で狭めた。どちらの PR の狭めの欄にも書かれていない。Archon で不可でない（置き場のファイルを指し札で返せば読める）→ 戻す → 部分 D2 で戻した

- F313 2 回目の差分の審査は、1 回目の手直しが fixed と答えた穴が在る時だけ、手直しだけの差分（1 回目の差分の後から今まで）に当て、fixed と言われた穴を 1 件ずつ検算する。全部 declared なら 2 回目の審査を回さない
  - 元: review-loop.py:628 `delta_review2_due`・:655 `delta_fixed`、works/blk-refix/scripts/cut2.py
  - 今: 表
  - 証: tests/workflows/test_fix.py::DeltaScriptsCase.test_declared_only_refix_skips_review2
  - 本物の run: 置き場の `loop-fix_delta2.json`・`delta/review-2.json`（手直しが fixed を返した時だけ）
  - 狭め: 無し

- F314 2 回目の手直しは 2 回目の審査が義務を出した時だけ起き、3 回目の往復は無い
  - 元: review-loop.py:551-552 `DELTA_PASSES`（2 回まで）・:648 `delta2_faces_open`
  - 今: 表
  - 証: lib/tests/test_blk_refix.py::RefixCase.test_no_third_pass、lib/tests/test_blk_refix.py::RefixCase.test_review2_then_ties2、tests/workflows/test_fix.py::DeltaScriptsCase.test_not_launched_roles_are_done
  - 本物の run: refix2 の節の状態
  - 狭め: 無し

- F315 審査・手直しの受け付けは拒否の理由をファイルに置いて次の回に名指し、3 回目の拒否で諦める（審査なら delta/review-<n>.json に pass: false・gave_up、手直しの支度は以後 go: false）。輪の回数の上限は元と同じ 3
  - 元: works/blk-delta/blk-delta.yaml・works/blk-refix/blk-refix.yaml の loop の max_iterations と give_up、review-loop.py の 3 回目の give_up
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::DeltaSeamCase.test_accept_out_writes_reasons_and_gives_up_on_the_third、tests/workflows/test_fix.py::DeltaScriptsCase.test_third_rejection_gives_up_and_unknown_keys_are_rejected、tests/workflows/test_fix.py::RolesCase.test_loops_keep_the_original_bounds
  - 本物の run: 筋書きでのみ（拒否 3 回は健全な run で起きない）
  - 狭め: 無し

- F316 fix の返りの delta_review は {rounds（走った審査の数 0〜2）, pass（最後の審査に義務が無い）}。全部の単位が軽量で省いた run は {0, true}、審査が走らなかった・落ちた run は {0, false}。done は審査を省いたか通った時だけ真
  - 元: works/blk-delta/scripts/collect.py・works/blk-refix/scripts/collect.py（盤面の review の出力）
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_collect_light_run_skips_review、tests/workflows/test_fix.py::BlockScriptsCase.test_collect_counts_review_rounds、tests/workflows/test_fix.py::BlockScriptsCase.test_collect_failed_or_missing_review_is_not_done、tests/workflows/test_fix.py::BlockScriptsCase.test_collect_after_a_failed_change_check_reports_no_review、lib/tests/test_fix_seams.py::GroupScriptsSeamCase.test_delta_review_counts_rounds
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 節 `fix` の出力 delta_review。厚み標準の健全な run で {rounds: 1 か 2, pass: true}）
  - 狭め: 無し

- F317 組の子の run（mode group）は差分の審査を回さず、返りの delta_review は {rounds: 0, pass: false}。親は子の返りのこの欄を読まない
  - 元: 無し（元は組の子が無い。並べの枝は盤面の中）
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_collect_group_mode_returns_no_review
  - 本物の run: 組の子の run の節 `fix` の出力 delta_review
  - 狭め: 無し（新しい形）

- F318 全部の単位が軽量（持ち主の決め dynamic-depth）の run は差分の審査を省き、省いた理由を置き場に残す。変更の確かめが通らない run は軽量と扱わない
  - 元: works/darkfactory/lib/depth.py:186 `skip_reason`・線の h-redepth、review-loop.py の条件
  - 今: 表
  - 証: tests/workflows/test_fix.py::DeltaScriptsCase.test_delta_cut_skips_an_all_light_run、tests/workflows/test_fix.py::DeltaScriptsCase.test_delta_cut_does_not_mark_a_failed_change_check_as_light
  - 本物の run: 厚み標準の run では `delta/skipped.json` が無いこと（省かない）
  - 狭め: 無し

- F319 審査を省く前に、修正の後の信号で軽量の単位を標準へ上げる: 申し出の在る単位・受け付けが最後の回に止めた単位・組の結末 given_up・答えていない修正前の関所の問い・同じ run の案の直し（2 回目の修正）・修正役の異議・実際の差分の広さ（修正案の allowed_paths でなく修正の差分で数える）。控えが読めなければ上げる側へ倒す
  - 元: works/darkfactory/lib/depth.py:262 `signals`・:289 `_actual_diff`・:302 `raise_`（線の h-redepth の replanned・rejudged）
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::DeltaSeamCase.test_redepth_raises_on_parked_given_up_unanswered_and_broken_store
  - 本物の run: 置き場の `depth-raised.json`（units ごとの depth と why、counted の 1 行）
  - 狭め: 無し（試験の欠け）

- F320 軽量で省いた・深さを上げた事実を報告に出す（何を省いたかを名指す行）
  - 元: works/darkfactory/lib/depth.py:192 `lines`（works/tests/test_depth.py の LinesCase）を報告が読んだ
  - 今: 表
  - 証: lib/tests/test_depth.py::LinesCase.test_light_run_names_what_it_skipped（lib の口だけ）。報告に届く配線の試験は無い → 要追加: 線か報告の試験で「fix が審査を省いた run の報告に省いた理由の行が在る」
  - 本物の run: 厚み標準の run では起きない（筋書きでのみ）
  - 狭め: 報告への届きは #94・#68 のどちらにも書かれていない。Archon で不可でない → 持ち主の確かめ待ち（線の redepth と fix の redepth の二重を 1 つにする直しと合わせて）

- F321 差分が空で、塞いだと言われた穴も無い run は、差分の審査を起こさない
  - 元: review-loop.py:604 `fix_delta_nonempty`・:617 `delta_review_due`
  - 今: 表
  - 証: tests/workflows/test_fix.py::DeltaScriptsCase.test_empty_diff_without_claims_does_not_launch_the_review
  - 本物の run: 筋書きでのみ（健全な run は差分が在る）
  - 狭め: → #121 で戻した

- F322 前の試みの審査の材料・控え（brief・座・受けた審査・判定の控え）を切りの時に消し、前の往復の穴を義務に混ぜない
  - 元: works/.shared/core/refix.py `_drop_stale`
  - 今: 表
  - 証: lib/tests/test_blk_tests_delta.py::TestDeltaPlace.test_cut_removes_stale_outputs
  - 本物の run: 置き場（resume した run で前の控えが残らない）→ 筋書きでのみ
  - 狭め: 無し

- F323 承認済みの修正案の欄の控えが凍結の印と食い違えば、差分の審査の段の印（stopby.DELTA）で控えを名指して止める
  - 元: works/.shared/core/conflict.py:817 `fields_broken`、works/blk-delta/scripts/cut.py
  - 今: 表
  - 証: lib/tests/test_blk_tests_delta.py::TestDeltaPlace.test_broken_plan_fields_name_the_stage、lib/tests/test_blk_tests_delta.py::TestDeltaPlace.test_unsaved_verdicts_raise
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- F324 1 回目の審査役は superpowers の task-review の座（型を埋めた座のファイル review1-seat.md）を読んで審査する。2 回目には座が無い
  - 元: works/.shared/core/seat.py（task-review）、works/blk-delta/commands/delta-review.md:15（seat_file の行）
  - 今: 表
  - 証: lib/tests/test_blk_tests_delta.py::TestDeltaPlace.test_cut_writes_the_seat_file
  - 本物の run: 置き場の `review1-seat.md` と `review1-brief.json` の seat_file
  - 狭め: 無し（試験の欠け）

- F325 手直しの役の指示書: 始めの記録の 2 行 → 役の頭（brief の名指し）→ 手直しだけの決まり → 共通の直し方（core-fix。申し出の決まりは載せない）→ receiving-code-review の座 → 返す形 → 言語の 1 行。前の回の拒否は 1 行目で名指す。借りた技 receiving-code-review は B の F145
  - 元: works/blk-refix/rules/refix.md、works/blk-refix/lib/refixrules.py `build`、works/blk-refix/scripts/prep.py
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::DeltaSeamCase.test_refix_prompt_names_the_policy_and_ends_with_the_language_line（名を変えた: 手直しの役は方針を貼らず policy_path で名指す。貼った方針で閉じるのは元の review2.md）
  - 本物の run: 手直しが起きた run の手直しの指示書（refix-prep の出力 prompt_file）
  - 狭め: 無し（試験の欠け）

- F326 レンズ（silent-failure-hunter）の振り分け: 差分に変わったファイルが在れば起こし、利用者が入れた役の定義の本文（前付けを剥がした物）から指示書を組む。定義が引けない・変わったファイルが無ければ起こさず、理由を lens.json に残す
  - 元: works/blk-lens/lib/lenses.py:81 `route`、works/blk-lens/scripts/route.py
  - 今: 表
  - 証: tests/workflows/test_fix.py::DeltaScriptsCase.test_lens_prep_without_the_role_definition_is_go_false、tests/workflows/test_fix.py::DeltaScriptsCase.test_lens_prep_with_the_role_definition_and_collect、lib/tests/test_fix_seams.py::LensesSeamCase.test_render_builds_prompt_from_the_role_definition。元の LensBoardCase.test_route_rule_false_is_not_routed（route が偽なら起こさない）の写しは無い（今のレンズは 1 本で route が変更の有無だけ）
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 置き場の `lens.json` の行（state ran / not_routed と reason）と `prompt-lens-silent-failure-hunter.md`。pr-review-toolkit の無い環境では not_routed）
  - 狭め: 無し。「言語での振り分け」は元にも無い（lang は指示書の言語の 1 行だけ）

- F327 レンズの返りを集め、指摘にレンズの名を付け、落ちた・起きなかったレンズは理由の行を残し（レンズが落ちても run を止めずに先へ進む）、形の崩れた指摘は数えて落とす。集めた行を 1 回目の審査役の材料に足す（2 回目には載せない）
  - 元: works/blk-lens/lib/lenses.py `collect`、works/.shared/core/lens.py `collect`・`brief_rows`
  - 今: 表
  - 証: lib/tests/test_blk_lens.py::LensPlaceCase.test_collect_records_failed_lens_and_succeeds、tests/workflows/test_fix.py::DeltaScriptsCase.test_a_failed_lens_leaves_a_failed_row_and_the_collector_goes_on、tests/workflows/test_fix.py::RolesCase.test_a_failed_lens_is_recorded_and_the_block_goes_on、tests/e2e/test_fix_halt_resume.py::FixHaltResumeCase.test_failed_lens_is_recorded_and_the_line_goes_on（止めた Archon で、レンズが落ちても集め役から後ろが走る）、lib/tests/test_blk_lens.py::LensPlaceCase.test_findings_keeps_valid_and_counts_dropped、lib/tests/test_blk_lens.py::LensPlaceCase.test_cut_brief_carries_lens_rows、lib/tests/test_blk_lens.py::LensPlaceCase.test_review2_brief_has_no_lens、tests/workflows/test_fix.py::DeltaScriptsCase.test_lens_prep_with_the_role_definition_and_collect、lib/tests/test_fix_seams.py::TestLensPlace.test_routes_collect_and_summary
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば `lens.json` の行と `review1-brief.json` の lens）
  - 狭め: 無し

- F328 レンズの集め役が落ちた・ok でない時は run を止める（観点を誰も見ていないまま先へ進ませない）
  - 元: works/blk-lens/scripts/exit.py（lenses.exit_。盤面を by works:lens で止める）
  - 今: 表
  - 証: tests/workflows/test_fix.py::DeltaScriptsCase.test_lens_collect_failure_is_reported_not_silent、tests/workflows/test_fix.py::GroupsCase.test_a_failed_node_halts_the_block_for_resume、tests/workflows/test_line.py::CollectAndResultCase.test_stopping_stages_beside_an_absorbed_one_are_not_absorbed（報告は集め役と支度の落ちを受け止めた落ちに載せない）
  - 本物の run: 筋書きでのみ
  - 狭め: → #594 で戻した（集め役は ok: false と理由を書いてから落ち、落ちても止めないレンズの段（レンズとその返りの中継）のほかの、修正のサブグラフのどのノードの落ちでも run が止まる。#121 の止めずに知らせる形は外した）。読み手（最後の関所と報告）は配線の部分 D2（#211）

- F329 レンズの結果を報告に出す: 走ったか・読めたか・採った／採らなかった指摘の数・落ちたレンズ。落ちたレンズは次の run の依頼に「再実行の要あり」で運ぶ。見ていない観点の見出し（UNSEEN_LENS_HEADING）を立てる
  - 元: works/.shared/core/report.py:777 `lens_next_items`・:1567 の lens.summary の行・:2069（lens.report_lines）、works/.shared/core/lens.py `summary`・`report_lines`
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_collect_writes_delta_holes_and_lenses_beside_the_diff・lib/tests/test_runreport.py::DecisionsCase.test_always_rows_name_clean_lens_and_not_run・lib/tests/test_runreport.py::CarryCase.test_failed_lens_is_carried_as_rerun
  - 本物の run: 無し（報告にレンズの行が出ない）
  - 狭め: #94（返りの約束にレンズが無い）と #68（報告）で狭めた。どちらの狭めの欄にも無い。Archon で不可でない → 戻す → 部分 D2 で戻した

- F330 写しの柵（copyfence）と写しの台帳（copyledger）
  - 元: works/.shared/core/copyfence.py・copyledger.py（works 自身の試験がリポジトリの中の写しと台帳 COPIED_FROM を数える道具。修正のブロックの run の中では使わない）
  - 今: 表
  - 証: fix の行としては要らない（棚卸しの範囲外として明記するだけ）
  - 本物の run: 無し（run の能力でない）
  - 狭め: fix の能力ではないので無し。リポジトリの柵としての扱いは別の棚卸し（テストの層）へ

D の数: 31 行 / 今が無し 5（F312・F321・F329 と、本物の run で働かない F302・F320）/ 証が要追加 14（F302・F304・F305・F306・F312・F313・F317・F319・F320・F321・F324・F325・F328・F329）/ 狭め不可でない 5（戻す: F302・F312・F321・F329、持ち主へ: F320）

## E. 組の並べ・後始末・変更の確かめ・返りの約束と人に届く物（F400〜）

置き場（本物の run の記録）: 親（線の include `fix`）の置き場は `<run の成果物>/fix/fix/`。prep が `groups.json`（{groups, count, par, start_tree, out_dir}）・`base-rev.json`・`fix-ignored-before.json` と入力の写しを書き、子は `out_dir/<group_id>/result.json`、join が `join.json` と `join/<group_id>.diff`、戻せた組の TDD の状態を `tdd-<k>/`、assert-changed が `assert-changed.json`、clean が `fix-removed.json`、tdd-unit が `tdd-unit.json`（型つきの成果物 tdd-unit）。2 回目の修正（include `refix`）は `fix/refix-run/`。返りは節 `fix` の出力。種（stats.py の mean と clamp）の健全な run の見込み: 修正案が 2 つの欠陥を別の項目にすれば組は 2 つ（`fixboard.fix_groups` は項目を共にする単位だけをつなぐ。同じファイルでも項目が別なら別の組）。Archon は run の作業ツリーを切るのに remote を要する（下の F404）ので、本物の run の対象には remote が在り、組が 2 つなら並べ（groups-par）、1 つなら 1 つずつ（groups-seq）になる。

- F400 直す義務の単位を、承認済みの修正案の項目を共にする物どうし（推移的）の組に分け、組の中と組の並びは義務の順にする。項目の無い単位は 1 つで 1 組
  - 元: works/blk-fix/lib/tddlanes.py:126・131 `items_of`・`groups`、works/blk-fix/lib/lanekit.py `groups`
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::LanekitSeamCase.test_groups_units_sharing_items_transitively_in_input_order、lib/tests/test_fix_seams.py::GroupScriptsSeamCase.test_fix_groups_join_units_through_items、tests/workflows/test_fix.py::BlockScriptsCase.test_prep_two_groups_run_side_by_side
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 親の置き場の `groups.json` の groups[]（unit_ids・items）と節 prep の出力）
  - 狭め: 無し

- F401 直す義務の単位は、開いた単位（block と do-now の suggest）から、人に諮っている fork の出どころと depends を除いた物
  - 元: review-loop.py:2645 `_owed_units`、works/.shared/core/conflict.py:696 `fix_duty`
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::GroupScriptsSeamCase.test_owed_keys_are_open_units_without_forks
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば groups.json の unit_ids の和が判定の開いた単位と同じ（健全な run で 2 単位））
  - 狭め: 無し

- F402 案の直しの後の 2 回目の修正（線の include `refix`）は、入力 only_items の項目に載る単位だけを組にし、置き場を 1 回目と分ける（fix/refix）
  - 元: works/darkfactory/darkfactory.yaml の 2 回目の修正の段（同じブロックの 2 度目の include。scope の周の置き場を分けた）
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_prep_only_items_keeps_their_units、tests/workflows/test_fix.py::BlockScriptsCase.test_prep_under_refix_writes_its_own_place
  - 本物の run: 筋書きでのみ（fix_plan_item の裁定が出る run だけ `fix/refix-run/` が在る）
  - 狭め: 置き場が分かれたので 2 回目は 1 回目の申し出・裁定・TDD の凍結を読めない（C の conflict.second_pass の行、A の F018・F023・F044）。この行の範囲では無し

- F403 組を並べるのは、組が 2 つ以上・始めの記録の features_cut に並べの切り替え（fix_lanes か tdd_lanes）が無い・対象に git の remote が在る時だけ。どれかが欠ければ組を 1 つずつ親の作業ツリーで回す
  - 元: works/blk-fix/scripts/fix_fork.py・tdd_fork.py（features_cut の fix_lanes と tdd_lanes を別々に読み、TDD の輪の並べと修正役の並べを別々に切れた）
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::GroupScriptsSeamCase.test_parallel_needs_two_groups_no_lane_switch_and_a_remote、tests/workflows/test_fix.py::BlockScriptsCase.test_prep_without_remote_runs_in_order、tests/workflows/test_fix.py::BlockScriptsCase.test_prep_lane_switch_off_runs_in_order
  - 本物の run: 節 prep の出力 par と、groups-par か groups-seq のどちらが走ったか（Archon の節の状態）
  - 狭め: #94 で狭めた 2 つ: (1) 切り替え 2 語を 1 つの並べの切り替えにした（「能力の狭め」2 行目。子の run が TDD と修正役の両方を回すので分けられない。計画どおり）。(2) remote の無い対象では並べない（「能力の狭め」4 行目・U8）。(2) は Archon で不可: 作業ツリーの隔離は remote を要する（Archon packages/isolation/src/providers/worktree.ts:1302-1305 `no git remote is configured`）。(1) は Archon で不可ではないが、子の run の形を変えずに戻す道が無い → 持ち主の確かめ待ち（PR #94 本文に記載済み）

- F404 並べる数は Archon の既定の上限 5（max_parallel）だけで、待ちの列も錠も持たない（組は分けない）
  - 元: works/blk-fix/lib/lanekit.py の `MAX_LANES`（固定 3 本の枝）・`queue_put`・`take`・`queue_lock`（あふれた組は列に並び、空いた枝が錠の中で取る。2aa7c66c の直前の commit ab9b9f17）
  - 今: 表
  - 証: tests/workflows/test_fix.py::GroupsCase.test_no_fixed_lanes_and_no_queue_in_scripts、lib/tests/test_fix_seams.py::LanekitSeamCase.test_no_queue_and_no_fixed_lane_count
  - 本物の run: groups-par の子の run の数 = 組の数（5 を超える組は Archon が 5 つずつ起こす）
  - 狭め: 無し（持ち主の決め no-queue。枝の数の上限が 3 から 5 になり、列の代わりに Archon が順に起こす）

- F405 子の run は親の作業ツリーの姿（未 commit・未追跡を含む木の sha）を写してから直す。並べない子は親の作業ツリーをそのまま使う
  - 元: works/.shared/core/unittrees.py（単位の worktree が run の作業ツリーの未 commit の直しを見る `test_uncommitted_run_edits_visible_in_unit`）
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::TestGroups.test_adopt_copies_parent_shape_and_diffs_apply_in_order、tests/workflows/test_fix.py::GroupChildScriptsCase.test_group_start_adopts_the_parent_tree_and_skips_tdd_without_runner
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 子の run の作業ツリーで、親の直前の姿が見えること（子の置き場の始めの木 = groups.json の start_tree））
  - 狭め: 無し

- F406 子は親の置き場から入力の写し（始めの記録・判定・修正案の欄の控え）を写し、修正案の欄の凍結の印を子の trace に置き直す
  - 元: 無し（元は 1 つの盤面を全部の枝が読んだ）
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::GroupChildSeamCase.test_adopt_inputs_copies_the_parent_and_refreezes_the_fields、tests/workflows/test_fix.py::BlockScriptsCase.test_prep_writes_only_copies_the_children_adopt
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 子の置き場の `judgment.json`・`plan-fields.json`・`r1/start.json`）
  - 狭め: 無し

- F407 並べた子の修正前の版は親の HEAD（prep が base-rev.json に控え、子が写す）。子の worktree は Archon が origin の枝から切るので子の HEAD を使わない
  - 元: works/.shared/core/writes.py:88 `base_rev`（盤面の 1 つの版）
  - 今: 表
  - 証: tests/workflows/test_fix.py::GroupChildScriptsCase.test_side_by_side_child_measures_from_the_parent_head
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 親の置き場の `base-rev.json` の rev = 線の始めの HEAD。子の数え直し（coverage-after.json の total）がこの版で数えられる）
  - 狭め: 無し

- F408 子は組の結果（始めの木・終わりの木・単位ごとの結末・TDD の輪の結果と状態のパス・申し出・異議・6 つの印・許したテストの変更・受け付けた返答のファイル）を out_dir/<group_id>/result.json に書く。単独の run（out_dir が空）は自分の置き場の groups/<group_id>/ に書く
  - 元: 無し（元は枝の状態を盤面の lanes に積んだ。works/blk-fix/lib/tddlanes.py・fixlanes.py）
  - 今: 表
  - 証: tests/workflows/test_fix.py::GroupChildScriptsCase.test_group_end_writes_the_result、tests/workflows/test_fix.py::GroupChildScriptsCase.test_group_end_alone_writes_into_its_own_place、lib/tests/test_fix_seams.py::GroupChildSeamCase.test_group_result_shape
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 親の置き場の `groups/<group_id>/result.json`（prep の out_dir の下））
  - 狭め: 無し

- F409 並べた run の join: 子の差分（始めの木 → 終わりの木）を組の順に親の作業ツリーへ 3 方向で当て、試験のファイルの挿しだけの食い違いは合わせ（union）、差分を join/<group_id>.diff に控える
  - 元: works/blk-fix/lib/lanekit.py `merge`・`merge_in_order`、works/.shared/core/unittrees.py `apply`（union）、works/blk-fix/lib/tddlanes.py:455 `settle`
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_join_applies_both_groups_in_order、lib/tests/test_fix_seams.py::GroupScriptsSeamCase.test_join_group_applies_and_check_reverts、lib/tests/test_unittrees.py（24 本。例 lib/tests/test_unittrees.py::UnitTrees.test_insert_only_conflict_in_a_union_file_is_merged_in_order）
  - 本物の run: 親の置き場の `join/g1.diff`・`join/g2.diff` と `join.json` の groups[].returned（種で組が 2 つなら、2 つの差分が同じ stats.py の別の所と同じ test_stats.py に当たる）
  - 狭め: 無し

- F410 当たらない組（先の組と同じ行を変えた）は当てず、先の組を残して後の組を returned: false と理由にする
  - 元: works/.shared/core/unittrees.py（test_same_line_second_does_not_apply_and_tree_keeps_first）、works/blk-fix/lib/tddlanes.py（TestSettle.test_clashing_apply_goes_back_to_serial）
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_join_keeps_first_when_second_clashes
  - 本物の run: 筋書きでのみ（種の 2 つの直しは別の行）
  - 狭め: 元は戻した枝の単位を順の輪（直列の修正の輪）でもう一度直した（tddlanes の「back to serial」）。今は当たらない組の単位は not_done で返り、同じ run の中で直し直す道が無い（裁定の後の修正 fix-ruled は申し出のある単位だけ）。#94 は列と順の輪を外すと書くが、戻した組を直し直さないことは「能力の狭め」に無い。Archon で不可でない（join の後に 1 つずつの子の run を起こす fan_out をもう 1 つ置ける）→ 持ち主の確かめ待ち

- F411 当てた後に、前の組とも重なったファイルの名指しのテストの中身が子の終わりの木と同じかを照らし、その組で赤 → 緑を確かめた名指しと変えたファイルに当たる試験を親の木で走らせ直す。走らない・名指しが結末に居ない・赤なら、その組の当てたパスを戻して returned: false
  - 元: works/blk-fix/lib/tddlanes.py:688 `_green_after`（当てた単位の名指し全部と変更に直に関わる試験。重なりのファイルが在れば地図が届く試験の全部も足す。test_cmd の関門が on なら test_cmd も 1 回）
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::GroupScriptsSeamCase.test_rerun_problem_names_red_unrunnable_and_unreported_tests、tests/workflows/test_fix.py::BlockScriptsCase.test_join_reruns_fixer_only_group_against_the_earlier_group・tests/workflows/test_fix.py::BlockScriptsCase.test_join_does_not_carry_a_backed_out_groups_named_tests（戻した組の名指しを持ち越さない）
  - 本物の run: 親の置き場の `rerun-<group_id>/`（走らせ直しの状態とログ）と join.json の reason
  - 狭め: (1)(2) は戻した（#121）。(3) 当てた後の赤で今の組だけを戻す形は残し、持ち主の答え待ち

- F412 組をまたぐ干渉（2 つの組が同じファイルを触る）を見る役と照らし
  - 元: 1 つの修正役の返答の中なら review-loop.py:2690-2709 の interactions（B の F117）。枝どうしは F411 の _green_after の広げと「意味の食い違い」で後の枝を戻す（元 tests/test_tdd_lanes.py:828 test_semantic_clash_backs_out_only_the_later_lane）
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_join_backs_out_the_later_group_on_a_semantic_clash
  - 本物の run: 種で組が 2 つなら、mean と clamp の直しが同じ stats.py に当たるので本物の run で起きうる。join.json の returned と rerun-<group_id>/ のログで見える
  - 狭め: → #121 で戻した（F411 の (1)(2) で埋まる）

- F413 子の結果のファイルが無い（子が落ちた）組は当てず、単位を not_done・組を returned: false と理由にする（issue #576 から、子が落ちると組の節が落ちて join は走らず、それでも結果の無いか読めない組が在れば join は作業ツリーを変えずに落ちて run を止める。返す節の行の既定 NO_RESULT は残る）
  - 元: works/blk-fix/lib/tddlanes.py（TestSettle.test_unfinished_lane_goes_back_to_serial）、fixlanes.py（TestJoin.test_unfinished_lane_goes_back）
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_join_stops_on_a_group_without_a_readable_result、lib/tests/test_fix_seams.py::GroupScriptsSeamCase.test_usable_result_is_the_one_group_rule、lib/tests/test_fix_seams.py::GroupScriptsSeamCase.test_join_rows_keep_child_status_only_for_returned_groups
  - 本物の run: 筋書きでのみ（子の run が落ちた時は組の節が落ちて nodes-ok が飛び、join.json は書かれない）
  - 狭め: F410 と同じく、元は順の輪で直し直した。今は not_done で返すだけ

- F414 1 つずつ回す run で結果を書かずに落ちた子が親の作業ツリーに残した変更を、子の始めの木に戻す（issue #576 まで join が戻した。今は組の子が落ちると組の節が落ちて join は走らず、次の組の group-start は前の組の分を戻さずに止まり、自分の組の前の試みの分だけを戻す）
  - 元: 無し（元の枝は単位の worktree で直し、run の作業ツリーへの迷い書きは機械が戻した: works/blk-fix/lib/lanekit.py `revert_strays`、tests/test_tdd_lanes.py:483 test_stray_write_of_run_tree_is_reverted）
  - 今: 表
  - 証: tests/workflows/test_fix.py::GroupChildScriptsCase.test_group_start_in_order_drops_its_own_earlier_attempt、tests/workflows/test_fix.py::GroupChildScriptsCase.test_group_start_in_order_stops_while_an_earlier_child_is_halted、lib/tests/test_fix_seams.py::GroupScriptsSeamCase.test_halted_groups_and_drop_unreturned_follow_the_rule
  - 本物の run: 筋書きでのみ（自分の組の前の試みの変更は親の作業ツリーで戻すだけで、置き場に控えを書かない）
  - 狭め: 無し

- F415 戻せた組の子の TDD の輪の状態を親の置き場の tdd-<k>/ に写し、実行器のパス exe を親の作業ツリーで解き直す（裁定の後の修正の受け付けが凍結と変更に当たる試験に使う）
  - 元: works/blk-fix/lib/tddloop.py の `states`（盤面の tdd-<k> を全部の輪が共有した）
  - 今: 表
  - 証: tests/workflows/test_fix.py::GroupChildScriptsCase.test_ruled_accept_runs_the_tests_of_the_tdd_state_the_join_copied、tests/workflows/test_fix.py::GroupChildScriptsCase.test_join_resolves_a_relative_runner_in_the_parent_tree
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 親の置き場の `tdd-1/state.json`（実行器の在る run なら健全な run でも在る））
  - 狭め: 無し

- F416 組ごとの TDD の輪の結果を、型つきの成果物 tdd-unit 1 つ（組ごとに {group_id, ran, reason, suite, reused, units}）にまとめ、結果の無い組は ran: false と理由
  - 元: works/blk-fix/scripts/collect.py の出口の欄 tdd（tddloop.exit_fields）
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_tdd_unit_writes_one_body_for_all_groups、tests/workflows/test_fix.py::GroupsCase.test_one_tdd_unit_artifact_on_block_path、lib/tests/test_fix_seams.py::GroupScriptsSeamCase.test_tdd_units_fill_groups_without_a_loop
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 親の置き場の `tdd-unit.json` と Archon の型つきの成果物 tdd-unit（健全な run で組ごとに units の行））
  - 狭め: 元の欄の test_cmd（関門の結果）・calls（回ごとの呼び出しの数と秒）は子の tdd の欄に載る限り写る（tddloop.exit_fields の形）。この行では無し

- F417 後始末の前段: 修正役が走る前に、git が無視するファイルとフォルダと HEAD の木を置き場に控える
  - 元: works/blk-fix/scripts/ignored_before.py、works/.shared/core/leftovers.py `record_ignored`
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::TestLeftovers.test_record_writes_before_into_the_place
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 親の置き場の `fix-ignored-before.json`（{ignored, ignored_dirs, dirs, head_tree}））
  - 狭め: 無し

- F418 後始末: 修正役が残した、git が無視するファイルのうち控えに無かった物だけを消す（前から在ったフォルダの中身・空のフォルダと .archon/ の下は残す）。全件は置き場のファイルに、件数だけを返す
  - 元: works/blk-fix/scripts/clean.py、works/.shared/core/leftovers.py `remove_new_ignored`
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::TestLeftovers.test_keeps_files_inside_old_ignored_dirs_and_empty_dirs
  - 本物の run: 親の置き場の `fix-removed.json`（種の run では __pycache__ などが消える）
  - 狭め: 無し（試験の欠け）。消した件数（元の出口の欄 removed {count, file}）は返りの約束に無く、報告に届かない（F427）

- F419 変更の確かめ（p1.worktree_after）: 戻せた組の受け付けた返答と裁定の後の返答の changes[].files が、run の始めの木から本当に変わったかを照らす。申告が空なら拒む（直す義務が残らず外れた単位だけの run は通す）。.archon/ の下は変わった物に数えない。通らなくても落ちず ok: false と理由を書く
  - 元: works/blk-fix/scripts/assert_changed.py
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_assert_changed_reads_japanese_and_untracked_names
  - 本物の run: 親の置き場の `assert-changed.json`（健全な run で {ok: true, reason: ""}）
  - 狭め: 無し（試験の欠け）

- F420 返りの約束: 返す節 fix は約束の 12 欄（done・units・groups・conflicts・replan_items・objection・diff・allowed_test_changes・changed・delta_review・handoffs・mismatched）だけを、全部必須・追加の欄なしで返す。outcome_field は done
  - 元: works/blk-fix/blk-fix.yaml:2046-2082 の collect（ok・files・changes_file・removed・tdd・fix_file・not_done・coverage・reads_file・reason）
  - 今: 表
  - 証: tests/workflows/test_fix.py::ContractCase.test_exact_fields_all_required_and_closed、tests/workflows/test_fix.py::ContractCase.test_returns_fix_with_outcome_done
  - 本物の run: 節 fix の出力
  - 狭め: 元の欄のうち removed・coverage・not_done・fix_file・reads_file は約束に無い（下の F427・F428 で個別に）

- F421 返す節は前の節が落ちても飛ばされても走り（all_done）、中の誤り・境の口が読めない時も stdlib だけで約束の形を組んで done: false と理由で返す（落ちない）
  - 元: works/blk-fix/scripts/collect.py（入力の誤りは 2 で落ちた）
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_collect_never_fails、tests/workflows/test_fix.py::BlockScriptsCase.test_collect_returns_the_contract_when_the_boundary_cannot_be_read
  - 本物の run: 落ちた run の節 fix の出力 diff.path が `fix/fix/fix-collect-error.txt`
  - 狭め: 無し（上位互換）

- F422 返りの units は単位ごとの結末 fixed・given_up・not_done と理由。戻せた組は子の結末、戻せない組は not_done と組の理由。裁定の後の修正の結末は fixed でない行にだけ重ねる
  - 元: works/blk-fix/scripts/collect.py の not_done（数だけ）と盤面の単位の行
  - 今: 表
  - 証: lib/tests/test_fix_seams.py::GroupScriptsSeamCase.test_join_rows_keep_child_status_only_for_returned_groups、tests/workflows/test_fix.py::BlockScriptsCase.test_collect_takes_units_fixed_after_ruling、tests/workflows/test_fix.py::BlockScriptsCase.test_collect_group_mode_returns_its_own_row
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 節 fix の出力 units（健全な run で 2 単位とも fixed））
  - 狭め: 無し

- F423 返りの done は、変更の確かめが通り、差分の審査を省いた（全部軽量 {rounds: 0, pass: true}）か通った時だけ真。確かめが通らない run は審査を回さず {rounds: 0, pass: false}
  - 元: works/blk-delta・blk-refix の collect（盤面の p3.delta_* の結末）と works/blk-fix/scripts/collect.py の ok
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_collect_light_run_skips_review、tests/workflows/test_fix.py::BlockScriptsCase.test_collect_counts_review_rounds、tests/workflows/test_fix.py::BlockScriptsCase.test_collect_failed_or_missing_review_is_not_done、tests/workflows/test_fix.py::BlockScriptsCase.test_collect_after_a_failed_change_check_reports_no_review、tests/workflows/test_fix.py::BlockScriptsCase.test_collect_refused_change_is_not_done
  - 本物の run: 筋書きでのみ（本物の通しの照らしの外。在れば 節 fix の出力 done と delta_review（深さ 標準の種では審査が走り rounds 1 か 2））
  - 狭め: 無し

- F424 返りの diff は run の始めの木から今の作業ツリーへの累積差分（.archon/ を除く）の指し札。差分が無ければ空の差分のファイルを指す
  - 元: 盤面の fix_delta（review-loop.py:1567）と線の差分
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_collect_diff_holds_every_returned_group
  - 本物の run: 節 fix の出力 diff.path が指すファイル（健全な run で stats.py と test_stats.py の差分）
  - 狭め: 無し

- F425 返りの conflicts（申し出と裁定の置き場 conflicts.json の指し札。行が無ければ null）と replan_items（fix_plan_item が誤りとした項目の番号）
  - 元: works/.shared/core/conflict.py の盤面の作業ファイル（線が読む）
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_collect_conflicts_pointer_only_with_rows
  - 本物の run: 節 fix の出力 conflicts（健全な run で null）
  - 狭め: 下の F426 を参照

- F426 最後の人の関所に、人に回した食い違いの申し出（ask_human と、案の直しを諦めた fix_plan_item）だけを、裁定の文・名指し・種類・正しいと見た側・id の 1 行ずつで並べ、それが在る時だけ関所を開ける
  - 元: works/.shared/core/conflict.py:1004 `human_lines`、works/darkfactory/lib/line_edge.py:790・852（最後の関所の文と開ける理由）
  - 今: 表
  - 証: tests/workflows/test_line.py::FinalGateCase.test_final_gate_lists_asked_lines_not_pointers・tests/workflows/test_line.py::AskFinalReadsCase.test_only_asked_conflict_rows_open_and_are_named、tests/e2e/test_line_scenarios.py::ConflictGateTest。fix 側の要追加 tests/workflows/test_fix.py::BlockScriptsCase.test_collect_returns_asked_lines は、返りに欄を足さない道を採ったので置かない
  - 本物の run: 筋書きでのみ（申し出が出る run）。起きれば最後の関所の文（線の ask-final の出力 text）
  - 狭め: #94 と #74 の約束の形で狭めた → 部分 B2 で戻した

- F427 修正役が「壊すと分かって受け入れた」理由（changes[].breaks.accepted）を、報告の冒頭と最後の人の関所に 1 件 1 行で届け、在れば関所を開ける
  - 元: works/.shared/core/report.py:301-314 `handoff_lines`、works/darkfactory/lib/line_edge.py:720・803・868（関所の文と開ける理由）、report.py:906・991（報告の冒頭）
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_collect_returns_accepted_breaks・tests/workflows/test_fix.py::HandoffCase.test_common_rules_breaks_promise_reaches_the_decisions・tests/workflows/test_line.py::AskFinalCase.test_accepted_breaks_open_and_are_listed・tests/e2e/test_line_scenarios.py::RefixHandoffTest
  - 本物の run: 無し（今は記録の上で人に届かない。修正役の返答 reply_file の changes[].breaks.accepted にだけ残る）
  - 狭め: #94 で狭めた（「能力の狭め」5 行目、「約束を変える頼み」1）。Archon で不可でない（返りの欄を 1 つ足すだけ）→ 戻す → 部分 D2 で戻した（返りの欄は足さず diff の隣の約束のファイル）

- F428 修正の受け付けの数え直しが修正役の申告と合わない単位（閉鎖の表の食い違い）が在れば、最後の人の関所を開けてその行を見せる
  - 元: works/darkfactory/lib/line_edge.py:818-819・866（querytest.closure_lines(b, mismatched_only=True)）
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_collect_writes_the_closure_beside_the_diff（棚卸しの名は test_collect_returns_closure_mismatches）・tests/workflows/test_line.py::AskFinalCase.test_recount_mismatch_is_a_reason
  - 本物の run: 組の子の置き場の `fix-unit-rows.json` にだけ残る
  - 狭め: #94（返りの約束）で狭めた。「能力の狭め」に無い。Archon で不可でない → 戻す（持ち主へ: 返りの約束の変更） → 部分 D2 で戻した（返りの欄は足さず diff の隣の約束のファイル）

- F429 許したテストの変更（承認済みの修正案の rewrite_tests・相談の合意・裁定 fix_test_scope の範囲）を、最後の人の関所に理由（許しの id と出どころ）つきで守りのファイルの行として並べる（keep-essence の 10）
  - 元: works/.shared/core/conflict.py `ruled_test_doc`、works/darkfactory/lib/line_edge.py:649（protect.touched で守りのファイルの行にした）
  - 今: 表
  - 証: tests/workflows/test_fix.py::BlockScriptsCase.test_collect_allowed_test_changes_from_rulings_and_groups、lib/tests/test_fix_seams.py::FixAcceptSeamCase.test_allowed_tests_take_rulings_and_agreements（plan・consult・ruling の行）、tests/workflows/test_fix.py::GroupChildScriptsCase.test_group_end_carries_permits_mismatches_and_accept_notices_to_the_parent_collect（子から親への写し）
  - 本物の run: 節 fix の出力 allowed_test_changes（健全な run で [] か、修正案の rewrite_tests のパス）と線の最後の関所の文
  - 狭め: 訳はブロックの側に戻した（#121）。最後の関所の文に並べるのは線（workflows/line/scripts/ask_final.py。守りのパス）で、持ち主の手に渡した

- F430 修正の後に対象が守ると宣言したファイル（protected.json）に触れたら最後の人の関所を開ける（keep-essence の 10）。fix の受け持ちは差分を残すことだけ
  - 元: works/darkfactory/lib/line_edge.py:640 `_protected`（protect.touched）
  - 今: 表
  - 証: tests/workflows/test_line.py::AskFinalCase.test_protected_hits_and_conflicts_open_in_every_mode（protected_hits が在れば開く）
  - 本物の run: 線の merge-seal の出力 protected_hits
  - 狭め: 無し（fix の範囲では）

- F431 直す単位ごとの記録（単位の結末・TDD の輪の行・閉鎖の数え直し・前後の件数）が報告と最後の関所に届く（keep-essence の 11）
  - 元: works/blk-fix/scripts/collect.py の出口の欄 tdd・coverage・not_done・fix_file、works/.shared/core/report.py（報告が盤面から単位ごとに読む）
  - 今: 表
  - 証: F422・F416 の試験。前後の件数が報告に届くことを縛る試験は無い → 要追加: tests/workflows/test_fix.py::BlockScriptsCase.test_collect_returns_unit_counts_before_and_after（または報告のブロックが子の置き場を読む試験）
  - 本物の run: 節 fix の出力 units、tdd-unit.json。前後の件数は組の子の置き場の coverage-after.json にだけ
  - 狭め: 前後の件数と閉鎖の表が報告に届かなくなった（#94 の返りの約束）。「能力の狭め」に無い。Archon で不可でない → 持ち主の確かめ待ち

- F432 線が 1 回目の fix と 2 回目の refix の返りを 1 つに合わせる（units・groups・allowed_test_changes は和、conflicts は走った方の指し札の配列）
  - 元: 無し（元は 1 つの盤面）
  - 今: 表
  - 証: tests/workflows/test_line.py::FixedCase.test_first_fix_alone・tests/workflows/test_line.py::FixedCase.test_refix_is_merged_without_losing_the_first（conflicts の配列と allowed_test_changes の和）
  - 本物の run: 筋書きでのみ（2 回目の refix が要る。在れば線の節 fixed の出力）
  - 狭め: 無し（線の範囲。ここでは F426・F429 の材料として挙げる）

- F433 並べた run の子の worktree と枝の片付け
  - 元: works/.shared/core/unittrees.py の `remove`・`sweep`（単位の worktree を枝の締めで消した。元 tests/test_unittrees.py の test_remove_and_sweep_clean_only_this_tree）
  - 今: 無し（表）
  - 証: 無し
  - 本物の run: 並べた run の後に Archon の worktree の一覧に子の worktree が残る
  - 狭め: #94 で狭めた（本文に記載。「能力の狭め」には無い）。Archon で不可でない（線の終わりに片付けの script の節を置ける）→ 持ち主の確かめ待ち

- F434 筋書き（fixtures）4 本が期待の結末に届く: group-tdd・group-consult・group-no-suite は completed で done 真、block-stops-at-fanout はブロックの形が fan_out で止まる
  - 元: works/blk-fix/fixtures/*.stubs.yaml（conflict・fix-lanes・no-change・pass・tdd-lanes・tdd の 6 本）
  - 今: 表
  - 証: tests/workflows/test_fix.py::ScenarioCase.test_fixtures_reach_their_expected_ends
  - 本物の run: 筋書きでのみ
  - 狭め: 元の conflict（申し出から裁定・裁定の後の修正まで）と no-change（直す物が無い run）の筋書きに当たる物が無い → 要追加: workflows/fix/fixtures/group-conflict.stubs.yaml と no-change.stubs.yaml（ScenarioCase の期待に足す）

- F435 読んだ証拠（reads.py・節 fix-reads）は B の F147、.archon/ の写しの拒否（check_pack_copy）は B の F107 に置く（この節では数えない）

E の数: 36 行（F400〜F435。F435 は参照だけ） / 今が無し 4（F427・F428・F433、F412 は照らしが無い） / 証が要追加 12（F411・F412・F418・F419・F424・F425・F426・F427・F428・F429・F431・F434） / 狭め不可でない（戻す）5（F411・F412・F426・F427・F428）、持ち主の確かめ待ち 5（F403 の (1)・F410・F429・F431・F433）、Archon で不可 1（F403 の (2)）

## 穴の要約

### 数

- 行の総数: 193（A 45・B 50・C 32・D 31・E 35。参照だけの C F229・F230・E F435 は数えない）
- 今が無し: 16（A F013・F026・F041／B F106・F107・F130・F136・F147／C F232（持ち主の決め no-queue による外し）／D F312・F321・F329／E F412・F427・F428・F433）
  - 加えて、関数は在るが線の上では一度も効かない物: 7（A F018・F023・F044、C F216、D F302・F320、B F136 の読み口）。根は 2 つ: 2 回目の修正の include の置き場が 1 回目と分かれて何も渡らない（A F018・F023・F044、C F216）、plan-review の返りが fix の入力に無い（B F130、D F302）
  - 修正役（fix-ruled）と範囲の相談の答えの役が前の会話を継がない（C F218・F222）は新しい会話で代わりを置いた（今が無しには数えない）
- 証が要追加（試験が無いか、外しても赤にならない）: 61（A 12・B 15・C 10・D 14・E 10）
- 狭めで Archon でも不可でない: 34
  - 戻す（持ち主の決めは要らない。元の能力が落ちていて、直し方が 1 つに決まる）: 19 — A F013・F018・F023・F041・F044／B F106・F130／C F205・F216・F225／D F302・F312・F321・F329／E F411・F412・F426・F427・F428
  - 持ち主へ（下の節）: 15
- Archon で不可: 3（C F218・F222: loop_group の中では `context.resume` を使えず、継ぐ相手は別の run か別の include の中。Archon packages/workflows/src/loader.ts:1173-1186／E F403 の (2): remote の無い対象では作業ツリーを切れない。Archon packages/isolation/src/providers/worktree.ts:1302-1305）

### 明示を頼まれた行の在りか

- 2 回目の修正が 1 回目の申し出と裁定を見られない（conflict.second_pass が線の上で常に偽）: C F216（凍結は A F018、2 回目の機械の諦めは A F023、事後の関門は A F044）
- `_plan_face_errors`・plan_faces を照らさない: B F130
- 差分の審査役の材料 out.p2.plan_review が常に null: D F302
- breaks.accepted を人に回す道が無い: E F427
- hold_fix・with_held・hand_empty が無くなった: B F136（hand_empty の代わりは B F134）
- 下請け（実装役と審査役を Agent で起こす道）: B F143（在る。試験も在る）
- consult-answer・fix-ruled が新しい会話: C F222・F218（Archon で不可。保存した返答を読む形で代わり）

### PR #94 の「能力の狭め」に書かれていない新しい穴（実装の issue に必ず載せる物）

- A F013・F041: 受け付けが回さなかった試験の名（ci_left・final_left・final_far）と、事後の関門が確かめずに受けた理由（SKIPPED_OP）が trace に書かれず、報告と最後の関所に届かない（keep-essence の 6 の後半）
- A F023: 案を直した後の 2 回目の機械の諦めを ask_human で人に上げる道が、AMENDED の行を書く所が無いので効かない
- B F106: 最後の回に、外れた単位の行だけで拒まれた時、元は行だけを外して受けた。今は義務の残りを全部止める（通るはずの単位まで止める退行）
- C F205: 修正役の query の申し出に判定者の問いを試さない（TDD の輪の道だけ試す）
- C F225: 線が修正前の関所の答えに asked を付けないので、関所の continue が問いへの答えに数えられない（fix の側は読む準備が在る）
- D F312・F329: 差分の審査の穴の名札とレンズの結果（落ちたレンズの再実行の頼みを含む）が報告に届かない
- D F321: 差分が空で塞いだと言う穴も無い run でも審査役を起こす
- E F411・F412: 組を戻した後の確かめ直しが TDD の名指しの在る組だけで、修正役だけが直した組と組をまたぐ同じファイルの干渉を誰も見ない。種（stats.py に 2 つの欠陥）で組が 2 つになれば本物の run で起きうる
- E F426・F428: 最後の関所が申し出の指し札のパスだけを並べ、直す裁定で済んだ申し出でも開く。数え直しの食い違いの行も関所に届かない

### 持ち主へ（答えが 1 つに決まらない物）

1. 書き込みの記録と読んだ証拠（U6）: Edit・Write の記録の包みと読了の記録を戻すか（B F102・F147、A F034、D F310）。Archon の節は `hooks:` を持てる（dag-node.ts:193）ので不可ではない。段 1b の U6 の決め: 役が自分で呼んだ道具は `provider_event` から取れ、下請けの中の呼びと読んだ時の sha はフックが要る
2. 返りの約束（docs/design.md「ブロックの返りの約束」）を広げるか: 人に回す申し出の行（E F426）・受け入れた壊れ（E F427 は戻す側に数えた）・数え直しの食い違い（E F428）・許したテストの変更の理由（E F429）・単位ごとの前後の件数（E F431）・差分の審査の穴とレンズの結果（D F312・F329）。どれも fix の置き場には在り、返りに載らないだけ
3. TDD の輪の同じ単位の段を同じ会話で続けるのを戻すか（A F032）。#94 は Archon で不可と書いたが、loop_group の fresh_context: false は前の周の会話を継ぐ（Archon dag-executor.ts:4773-4778、schemas/loop.ts:83）ので可能
4. 実行器の nice -n 19（A F026）、2 回目の修正の段の base の使い回し（A F043、負荷だけの差）
5. 自分食いの run の .archon/ の写しの拒否（B F107）
6. 1 回目に受け付けた返答の控え（B F136）: 書く道を戻すか、死んだ読み口（conflict.held_reply・with_held・held_writes と fixrules・factchecks・fixboard の読み）を外すか
7. 修正役が書いた指しの読了の記録（B F128）: 判定のやり直し（rejudge）に渡すか
8. 当たらなかった組・子が落ちた組の単位を同じ run で直し直すか（E F410・F413。元は順の輪で直した）
9. 並べの切り替えを 2 語から 1 語にした件（E F403 の (1)）と、並べた run の子の worktree の片付けを機械にするか（E F433）
10. 軽量で省いた・深さを上げた事実を報告に出すか（D F320）

### 本物の run（種と厚み 標準）で見えない物

- 種に実行器が無いので、A の行のほとんど（赤緑の判定・凍結・当たる試験の選び・3 回で諦める）は実行器を種に足して渡さない限り見えない。stage-1 の仕様で種に JUnit を書く実行器を足すかを決める
- 申し出・裁定・範囲の相談・はみ出し・3 回目の拒否・手直しの 2 往復は、健全な種では起きにくく筋書きでのみ。本物の run で必ず見えるのは groups.json・base-rev.json・join.json・assert-changed.json・coverage-after.json・fix-unit-rows.json・review1-brief.json・delta/review-1.json・節 fix の出力
