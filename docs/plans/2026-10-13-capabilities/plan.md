# 能力の棚卸し — 区分 P（計画 plan と事前審査 plan-review）

- 「元」は raiki61/claude-plugins @2aa7c66c の `works/`。「今」は works-factory の origin/main（4e0e18d）の相対のパス。線は PR #74 の頭（824dee3）。
- 本物の run の置き場は run の artifacts の下。計画のブロックは `plan/r<k>/`（周ごと）と `plan/structure/<鍵>/`（使い回す構造の実測）、事前審査のブロックは `plan-review/`（差し込みごとに `plan-review/pass-<k>/`）。
- 種（tests/e2e/target-seed）は stats.py の 2 つの欠陥（mean・clamp）、厚さ 標準、方針の文書も docs/concepts も無い。往復の 2 周目・案の直し・関所の答えの道は、健全な種の run ではほぼ「筋書きでのみ」。
- 行の番号 P001〜P257 は区分の中の通し番号。節は 5 つ（修正案を書く側・構造の実測と目・往復と案の直し・事前審査・修正前の関所の材料）。

## 修正案を書く側（計画のブロック: 直す義務・受け付け・材料・波及・返り）

読み方: 「元」は raiki61/claude-plugins @2aa7c66c の `works/`、「今」は main（4e0e18d）の相対のパス、線は PR #74 の頭（824dee3）。
本物の run の置き場は run の artifacts の下の `plan/r<k>/`（k は往復と案の直しを通した周の番号。標準の種の run では r1、往復が回れば r2…）。
種（tests/e2e/target-seed）は stats.py の 2 つの欠陥（mean の分母・clamp の上限の枝）で、方針の文書も docs/concepts も無い。

### 直す義務と単位の番号

- P001 判定の開いた単位（block か、suggest で do-now）から、答えていない関所の問い（held・escalate の fork と、escalate の問い）の出どころ・depends を除いた物を「直す義務の単位」にする。
  - 元: works/.shared/core/conflict.py:676 `owed_units_but_asked`（entry の CORE_OVERRIDES で写しの rules/review-loop.py:2645 `_owed_units` を差し替え）
  - 今: lib/planfile.py:246 `_owed_units`
  - 証: lib/tests/test_planfile.py::OwedCase.test_owed_is_open_units_minus_asking_fork_origin_and_depends（assert: lib/tests/test_planfile.py:94）・test_escalated_non_fork_excuses_origin_and_depends（:113）・test_decided_fork_and_held_non_fork_do_not_excuse（:103）・test_depends_that_is_not_a_list_is_not_read（:122）
  - 本物の run: plan/r1/brief-1.md の単位の行の「必ず案に入れる」（種では mean・clamp の 2 つ）と plan/r1/slots.json
  - 狭め: 無し（関所の答えで戻す部分は P002）

- P002 修正前の関所で人が答えた問い（gatemarks.returned）の出どころを義務に戻し、直す裁定でない裁定（held_by_rulings）の単位を義務から外す。
  - 元: works/.shared/core/conflict.py:676 `owed_units_but_asked`（returned・held_by_rulings の項）、試験 works/tests/test_blk_plan.py:557 ScriptCase.test_plan_slots_equal_copy_acceptance（answered_patch の q-back が must に入る）
  - 今: 無し（lib/planfile.py:246 の docstring が「扱わない」と書く）
  - 証: 要追加: tests/workflows/test_plan.py::OwedAnswersCase.test_answered_fork_origin_returns_to_duty — 入力に関所の答え（gate_answers の形）を渡すと、答えた fork の出どころが brief の「必ず案に入れる」に載り、外すと網羅の拒否になる
  - 本物の run: 筋書きでのみ（関所の答えが plan より前に来る run の形が要る）
  - 狭め: #75 で狭めた（Archon で不可でない → 戻すか持ち主の決め。線 workflows/line/works-factory-line.yaml:191-201 の plan の `with:` に答えを渡す口が無いだけで、Archon は節の出力を include の入力に渡せる。ただし今の線の順では関所 gate-before-fix は plan-rounds の後なので、戻すなら replan か fix の側の話になる。持ち主に: plan に関所の答えを渡すか、この能力を fix（conflict）だけに置くと決めるか）

- P003 案に入れてよい単位（開いた単位）に 1 から番号を振って周ごとに固め（slots.json）、役が no の整数で返した unit_keys を同じ並びで id に戻す。役の返答そのものは書き換えない。控え（plan-fields.json・p2.fix_plan.json）の unit_keys は名前。
  - 元: engine の pointers（works/.shared/core/graphloops/graphs/review-loop.json:3341 `pointers` の at plan[].unit_keys[] from record.units）と mark_launched の控え、works/blk-plan/lib/planblk.py:387 `_resolved`・:1236 `with_plan_fields`
  - 今: lib/planfile.py:261 `slots`・:303 `named`・:623 `open_round`（slots.json を書く）・:915 `take_plan`
  - 証: tests/workflows/test_plan.py::AcceptCase.test_accepted_plan_files（assert: tests/workflows/test_plan.py:519・:522・:525）・lib/tests/test_planfile.py::SlotsCase.test_named_turns_numbers_into_ids_and_keeps_unknown_numbers（:167）
  - 本物の run: plan/r1/slots.json（種では [mean の key, clamp の key]）・plan/r1/plan-fields.json の fields[].unit_keys
  - 狭め: 番号の振り方を変えた（元は判定の全部の単位に番号、今は開いた単位だけ。#75 本文「not_allowed の文」）。能力は落ちていない

- P004 直す義務の単位を 1 つでも書き落とした案を、単位を名指して拒む。
  - 元: works/.shared/core/graphloops/rules/review-loop.py:3077 `fix_plan_covers_units`（missing）、試験 works/tests/test_blk_plan.py:751 test_plan_missing_unit_rejected
  - 今: lib/planfile.py:316 `fix_plan_covers_units`・:915 `take_plan`（COVERS_REJECT :97）
  - 証: tests/workflows/test_plan.py::AcceptCase.test_missing_unit_rejected（assert: tests/workflows/test_plan.py:538・:539）・lib/tests/test_planfile.py::CoversCase.test_missing_unit_named（:184）
  - 本物の run: plan/r1/rejects-plan.json（役が書き落とした時だけ）。健全な run では起きにくいので筋書きでのみ
  - 狭め: 無し

- P005 1 つの単位を 2 つの項目に入れた案を拒む（1 単位は 1 案）。
  - 元: rules/review-loop.py:3077 `fix_plan_covers_units`（dup）、試験 works/tests/test_blk_plan.py:758 test_plan_dup_unit_rejected
  - 今: lib/planfile.py:316 `fix_plan_covers_units`
  - 証: lib/tests/test_planfile.py::CoversCase.test_unit_in_two_items_named（assert: :190）。ブロックの水準の試験は無い → 要追加: tests/workflows/test_plan.py::AcceptCase.test_unit_in_two_items_rejected — item(1,2) と item(2) の案で rejects-plan.json の理由に「2 つの案に入った単位」と clamp の key
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P006 今の周に無い key・範囲外の番号を名指して拒み、拒否文が入れてよい no の並びを示す。
  - 元: rules/review-loop.py:3077（unknown）、planblk.py:1134 `take` の NOT_OWED の allowed
  - 今: lib/planfile.py:316・:915（`{COVERS_REJECT} {allowed}`）
  - 証: tests/workflows/test_plan.py::AcceptCase.test_unknown_number_names_allowed_numbers（assert: tests/workflows/test_plan.py:543・:544）・lib/tests/test_planfile.py::CoversCase.test_unknown_key_and_number_named（:194）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P007 文字列の "1" は番号でなく名として扱って拒み、拒否文は「no で指せ」と案内する（key を写せと言い換えない）。
  - 元: works/tests/test_blk_plan.py:999 ScriptCase.test_plan_reply_by_number_string_rejected、文は rules/review-loop.py:3083
  - 今: lib/planfile.py:303 `named`（整数だけ戻す）・:322（「写さずに、貼られた単位の no で指せ」）
  - 証: 要追加: tests/workflows/test_plan.py::AcceptCase.test_string_number_is_a_name_and_asks_for_no — unit_keys ["1","2"] の案が拒まれ、理由に「no で指せ」が在り「key を字面のまま写せ」が無い
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（試験だけ欠け）

- P008 直す義務の無い単位（nit・info・suggest の defer・question）を案に入れた返答を、label（と disposition）を名指して拒み、入れてよい no を並べる。
  - 元: works/blk-plan/lib/planblk.py:407 `not_allowed`・:1134 `take`、試験 works/tests/test_blk_plan.py:455・:484・:695
  - 今: lib/planfile.py:296 `not_allowed`・:915（NOT_OWED_REJECT :94）
  - 証: tests/workflows/test_plan.py::AcceptCase.test_unit_without_duty_rejected_by_label（assert: tests/workflows/test_plan.py:549）・lib/tests/test_planfile.py::SlotsCase.test_not_allowed_names_label_of_unit_without_duty（:157）。info・defer・question の各 label の試験は無い → 要追加: AcceptCase.test_info_defer_question_rejected_by_label — 3 つの単位それぞれで理由に label=info・disposition=defer・label=question
  - 本物の run: 筋書きでのみ
  - 狭め: #75 で文を変えた（元「no N は label=…」→ 今「<key> は label=…」。番号を開いた単位にだけ振るため）。Archon で不可でない。能力（名指して拒む）は残る

- P009 人の答え待ちの問いの出どころ・depends の単位は、案に入れても入れなくてもよい（入れてよい no に並ぶ）。
  - 元: rules/review-loop.py:3083（opened は入れてよい）、planblk.py:328 `plan_slots_section`「入れてもよい no」
  - 今: lib/planfile.py:266 `plan_slots`・:783 `units_section`（「入れてもよい（人の答え待ちの…）」）
  - 証: lib/tests/test_planfile.py::CoversCase.test_every_owed_unit_once（assert: :180「人に諮っている単位は入れてもよい」）・SlotsCase.test_plan_slots_must_may_and_units（:138）
  - 本物の run: plan/r1/brief-1.md の単位の行（種に問いが無ければ現れない。筋書きでのみ）
  - 狭め: 無し

- P010 必ず入れるのに開いていない単位（行き止まり）が在れば、役を起こさずに止め、理由 PLAN_STUCK に no と key を書く。
  - 元: works/blk-plan/lib/planblk.py:366 `stuck_reason`・:379 `halt_if_stuck`・:1062 `snap`、試験 works/tests/test_blk_plan.py:590・:611
  - 今: lib/planfile.py:272 `stuck_reason`・:623 `open_round`（go: false・why）
  - 証: tests/workflows/test_plan.py::CollectCase.test_stuck_unit_skips_the_role（assert: tests/workflows/test_plan.py:791・:793）・lib/tests/test_planfile.py::SlotsCase.test_stuck_names_owed_unit_that_is_not_open（:150）。ただしブロックの試験は同じ key を開いた行と nit の行で 2 度持つ壊れた判定で道を通しているだけ（judge が重複の key を出さない限り本物では起きない）、lib の試験は `_owed_units` を mock で差し替えている
  - 本物の run: 筋書きでのみ（今の配線では届かない）
  - 狭め: #75 で狭めた（届かない道。owed は開いた単位からの引き算だけなので owed ⊆ opened が常に成り立つ。元は P002 の関所の答えで開いていない単位が義務に戻って起きた）。Archon で不可でない。持ち主の確かめ待ち（#75 本文の 2 つ目）: P002 を戻すか、この道を消すか

- P011 直す義務の単位が無い判定は、修正案の役も構造の実測も起こさずに抜ける。
  - 元: graphs/review-loop.json:3324 `cond: units_open`、planblk.py:1062 `snap`（go: false）・:1441 `collect`（ok: true・plan_file 空）、試験 works/tests/test_blk_plan.py:1074 test_no_fix_skips_both_loops
  - 今: lib/planfile.py:623 `open_round`（NOTHING_OWED :105）・workflows/plan/works-factory-plan.yaml:71・:213 の when
  - 証: tests/workflows/test_plan.py::CollectCase.test_nothing_owed_skips_the_role（assert: tests/workflows/test_plan.py:776・:777・:778・:781）
  - 本物の run: 種では起きない（筋書きでのみ）。起きた時は plan/r1/round.json の why と ripple.json の error
  - 狭め: 結末の形を変えた（元は ok: true で「直す物が無い」と「諦めた」を collect の ok・gave_up で分けた。今は両方 ready: false で、訳は ripple.json の error・round.json の why の字だけ）。docs/design.md:206 が「返りに訳を分ける語を持たない。report が judge の units が空から no_fix_needed にする」と決めた（持ち主の文書）。Archon で不可でない。持ち主に: 判定の units が nit だけ（空でない）の時、report は no_fix_needed と言えない（stopped_by_line になる）——訳の語を返りに足すか

### 受け付け（形と欄）

- P012 形の崩れた返答（plan が配列でない・行が object でない・narrows が配列でない）は例外にせず拒否にして出し直させる。
  - 元: works/blk-plan/lib/planblk.py:1127 `_plan_malformed`・:1134 `take`、試験 works/tests/test_blk_plan.py:506 test_take_malformed_plan_resubmits_not_raises
  - 今: lib/planfile.py:915 `take_plan`（MALFORMED_REJECT :98）、lib/replan.py `_malformed`
  - 証: lib/tests/test_planfile.py::ReplanModuleCase.test_malformed（assert: :494）は述語だけ。take_plan が MALFORMED_REJECT で返す試験は無い → 要追加: lib/tests/test_planfile.py::TakePlanCase.test_malformed_reply_is_a_rejection_not_an_exception — {"plan": "s"}・{"plan": ["x"]}・narrows が数、の 3 つで ok: false と MALFORMED_REJECT
  - 本物の run: 筋書きでのみ（役の節の output_format を Archon が先に照らすので本物では届きにくい）
  - 狭め: 無し

- P013 拒否の理由を全部 1 回の拒否に並べる（網羅・義務の無い単位・狭めない案・推し・works の欄・構造の答え・block への答え・閉じた項目）。
  - 元: 元は段ごとに最初の拒否で返した（planblk.py:1134 `take`・:1236 `with_plan_fields`・engine の post_check）。今は元より広い
  - 今: lib/planfile.py:915 `take_plan`（reasons の並び）
  - 証: 要追加: tests/workflows/test_plan.py::AcceptCase.test_every_reason_in_one_rejection — 単位の書き落としと tests の欠けを同時に持つ案で、1 つの理由に COVERS_REJECT と planmarks.REJECT の両方が在る（今の test_works_field_gaps_rejected は欄の中の複数だけ）
  - 本物の run: plan/r1/rejects-plan.json（拒否が起きた時）
  - 狭め: 無し（元より広い）

- P014 narrows（BASE から狭める能力）の行に、狭めない案を探した結果 no_narrow が無いか短ければ、行を名指して拒む。
  - 元: works/blk-plan/lib/planblk.py:1134 `take`（gatemarks.narrow_gaps・NO_NARROW_REJECT :112）、試験 works/tests/test_blk_plan.py:833 test_plan_narrows_without_no_narrow_rejected
  - 今: lib/planfile.py:915（NO_NARROW_REJECT :90）・役の型の required に no_narrow（workflows/plan/works-factory-plan.yaml の plan-writer）
  - 証: tests/workflows/test_plan.py::AcceptCase.test_narrow_without_no_narrow_rejected（assert: tests/workflows/test_plan.py:588）・ShapeCase.test_role_schemas_match_their_lib_owners（:389）
  - 本物の run: 種の修正は狭めを作らないので筋書きでのみ
  - 狭め: 無し

- P015 narrows の行の推し recommend の形の崩れ（answer が continue・stop でない など）を行を名指して拒む。
  - 元: planblk.py:1134 `take`（gatemarks.recommend_gaps・RECOMMEND_REJECT :114）、試験 works/tests/test_blk_plan.py:849
  - 今: lib/planfile.py:915（RECOMMEND_REJECT :92）
  - 証: lib/tests/test_gate_drafts.py::GapsCase.test_malformed_recommend_is_named（assert: lib/tests/test_gate_drafts.py:43）は gatemarks の述語だけ → 要追加: tests/workflows/test_plan.py::AcceptCase.test_malformed_recommend_rejected — answer「たぶん通す」の推しで rejects-plan.json の理由が RECOMMEND_REJECT と plan[0].narrows[0] を持つ
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P016 狭めの行の決め手の欄（decided_by・undecided_because・fences・world・recommend・no_narrow）を案と一緒に残し、関所の材料（事前審査のブロックと線）が読めるようにする。
  - 元: planblk.py:1134 `take`（gatemarks.split → gatemarks.save で盤面の gate-marks.json）
  - 今: lib/planfile.py:915（reply.json・p2.fix_plan.json に欄のまま置く）
  - 証: tests/workflows/test_plan.py::AcceptCase.test_accepted_plan_files（assert: tests/workflows/test_plan.py:524「narrows の行に関所の決め手の欄が残る」）・ShapeCase.test_role_schemas_match_their_lib_owners（:392・:393）
  - 本物の run: plan/r1/p2.fix_plan.json の plan[].narrows[]（種では空の配列）
  - 狭め: 置き場を変えた（gate-marks.json → 案の中）。読む側は PE

- P017 項目の works の欄（route・tests・rewrite_tests・refactor・allowed_paths・out_of_scope・adds の name）の欠けと誤りを、項目と欄を名指して拒む（tdd は受け入れテスト必須・direct は route_why・refactor の宣言は訳・同じ試験に 2 つの red_kind を拒む・型の誤り）。
  - 元: works/.shared/core/planmarks.py:593 `gaps`・planblk.py:1236 `with_plan_fields`、試験 works/tests/test_plan_fields.py::TestGaps・works/tests/test_blk_plan.py:1484 test_plan_without_fields_rejected_before_board
  - 今: lib/planmarks.py:593 `gaps`（元と字のまま）・lib/planfile.py:915
  - 証: tests/workflows/test_plan.py::AcceptCase.test_works_field_gaps_rejected（assert: tests/workflows/test_plan.py:559・:561）・lib/tests/test_plan_fields.py::TestGaps の 12 件（例 test_gaps_direct_item_needs_route_why :63・test_gaps_refactor_declared_needs_why :90・test_gaps_same_test_id_with_two_red_kinds_rejected :97・test_gaps_type_errors_are_named :102）
  - 本物の run: plan/r1/rejects-plan.json（拒否が起きた時）・plan/r1/plan-fields.json の fields[].route・tests
  - 狭め: 無し

- P018 書き換える既存のテスト rewrite_tests は今在るテストを名指さねばならず、受け入れの新しいテスト tests は今まだ無いテストでなければならない（在るなら rewrite_tests へ案内）。同じ id を tests と rewrite_tests の両方に書くのを拒む。
  - 元: planmarks.py:593 `gaps`、試験 works/tests/test_plan_fields.py:79・:90・:95
  - 今: lib/planmarks.py:593
  - 証: lib/tests/test_plan_fields.py::TestGaps.test_gaps_rewrite_must_name_an_existing_test（assert: :72）・test_gaps_new_test_must_not_exist_yet（:80）・test_gaps_same_id_in_tests_and_rewrites（:86）
  - 本物の run: plan/r1/plan-fields.json の fields[].tests・rewrite_tests
  - 狭め: 無し

- P019 試験の id のパスは根の中の相対だけ（逆斜線・絶対・根の外を拒む）。書いてよい範囲 allowed_paths は相対で狭く（字の無い glob は木の丸ごとで拒む）、out_of_scope は案が名指す試験に当たってはいけない。
  - 元: planmarks.py:593 `gaps`・:206 `glob_problem`、試験 works/tests/test_plan_fields.py::TestIdPaths・ScopeFieldsCase
  - 今: lib/planmarks.py:593・:206
  - 証: lib/tests/test_plan_fields.py::ScopeFieldsCase.test_gaps_allowed_paths_must_be_relative_and_narrow（assert: :406）・test_glob_without_a_literal_character_is_a_whole_tree_allowance（:415）・test_gaps_out_of_scope_must_not_hit_named_tests（:455）・TestIdPaths の 5 件・tests/workflows/test_plan.py::AcceptCase.test_works_field_gaps_rejected（:561 の allowed_paths[0]）
  - 本物の run: plan/r1/plan-fields.json の fields[].allowed_paths・out_of_scope
  - 狭め: 範囲の glob の当て方を守りのファイルの当て方と 1 つにする試験（元 works/tests/test_plan_fields.py:505 test_glob_match_is_the_protect_matcher）が無い → 要追加: lib/tests/test_plan_fields.py::ScopeFieldsCase.test_glob_match_is_the_protect_matcher — planmarks.glob_match と protect.match が 5 つの組で同じ値（lib/protect.py が在るので写せる）。Archon で不可でない

- P020 adds の行の名を、関数・欄（function・record_field）はファイルの中の名として照らし、ファイル名を名に書いた行を名指す。
  - 元: planmarks.py:593（_file_name）、試験 works/tests/test_plan_fields.py:124
  - 今: lib/planmarks.py:579・:593
  - 証: lib/tests/test_plan_fields.py::TestGaps.test_gaps_adds_symbol_kind_named_by_file（assert: :121）
  - 本物の run: plan/r1/p2.fix_plan.json の plan[].adds
  - 狭め: 無し

- P021 受け付けた案を works の欄と分けて、素の案（p2.fix_plan.json。核の 6 欄と決め手）・欄の控え（plan-fields.json {round, fields}）・番号を戻した全体（reply.json）に置く。
  - 元: planmarks.py:702 `split`・:846 `save`・planblk.py:1236 `with_plan_fields`、試験 works/tests/test_blk_plan.py:1496 test_plan_fields_saved_and_board_gets_bare_plan
  - 今: lib/planfile.py:909 `_save`・:915 `take_plan`
  - 証: tests/workflows/test_plan.py::AcceptCase.test_accepted_plan_files（assert: tests/workflows/test_plan.py:517・:518・:520・:523）・lib/tests/test_plan_fields.py::TestSplitAndBoard.test_split_strips_fields_and_resolves_limit（:174）
  - 本物の run: plan/r1/p2.fix_plan.json・plan/r1/plan-fields.json（返りの plan の指し札の先）・plan/r1/reply.json
  - 狭め: 無し

- P022 rewrite_tests の行に、書き換えてよい範囲 limit（既存のテストの <パス>:<行>）を受け付けで引いて控える。
  - 元: planmarks.py:702 `split`（_limit）、試験 works/tests/test_blk_plan.py:1504 test_rewrite_limit_resolved_on_accept
  - 今: lib/planmarks.py:456・:702
  - 証: lib/tests/test_plan_fields.py::TestSplitAndBoard.test_split_strips_fields_and_resolves_limit（assert: :174 以下の limit の断言）。ブロックの水準は無い → 要追加: tests/workflows/test_plan.py::AcceptCase.test_rewrite_limit_resolved — REWRITE の行を持つ案で plan-fields.json の rewrite_tests[0].limit が test_stats.py:<行>
  - 本物の run: plan/r1/plan-fields.json の fields[].rewrite_tests[].limit（役が書き換えを選んだ時）
  - 狭め: 無し

- P023 removes が名指す既存のテストを、修正前の版（BASE）の中身から permits として凍結する。修正前の版のテストが読めなければ trace に writes_base_tests_unread を残す。
  - 元: planmarks.py:362 `_naming_removes`・:702 `split(base_tests=)`、works/.shared/core/writes.py:93 `base_test_texts`（trace の行 :52）
  - 今: lib/planfile.py:353 `base_test_texts`・:915（`_trace(BASE_TESTS_UNREAD_OP)`）
  - 証: lib/tests/test_plan_fields.py::TestSplitAndBoard.test_split_freezes_tests_naming_removes_as_permits（同じ名で在る）・lib/tests/test_planfile.py::BaseTestsCase.test_texts_of_tests_at_rev（assert: :273）・test_unreadable_rev_names_rev（:279）。読めない時に trace に残す所の試験は無い → 要追加: lib/tests/test_planfile.py::TakePlanCase.test_unreadable_base_is_traced — base_rev に無い版を渡して受け付けると r1/trace.jsonl に op writes_base_tests_unread と rev
  - 本物の run: plan/r1/plan-fields.json の fields[] の permits（removes が試験を名指した時）・plan/r1/trace.jsonl
  - 狭め: 無し

- P024 欄の控えを置くたびに凍結の印（周と置いたバイトの sha256。op plan_fields_saved）を trace に書き、後の書き換え・消しを見破れるようにする。
  - 元: planmarks.py:846 `save`（SAVED_OP）・`frozen`、試験 works/tests/test_plan_fields.py::TestFrozenFields
  - 今: lib/planmarks.py:846（trace を渡さないので周のフォルダの trace.jsonl に直に書く）・lib/planfile.py:909
  - 証: lib/tests/test_plan_fields.py::TestFrozenFields の 6 件（例 test_save_writes_mark_with_round_and_sha :243・test_rewritten_after_save_is_broken :260）。ブロックが plan/r<k>/trace.jsonl に印を残す試験は無い → 要追加: tests/workflows/test_plan.py::AcceptCase.test_fields_are_frozen_in_the_round_trace — 受け付け後の plan/r1/trace.jsonl に op plan_fields_saved・round 1・plan-fields.json の sha256 が在る
  - 本物の run: plan/r1/trace.jsonl の op plan_fields_saved の行
  - 狭め: 無し（読む側の照らしは fix・plan-review）

- P025 拒まれた案は欄の控えを置かない（受けた時だけ置く）。受けた後に控えを置けなければ、欄の無い案のまま黙って進ませない。
  - 元: planblk.py:1236 `with_plan_fields`（盤面を止め BoardGap）、試験 works/tests/test_blk_plan.py:1523 test_rejected_by_board_leaves_no_fields・:1580 test_save_failure_after_board_took_plan_halts・:1591 test_round_read_once_at_head
  - 今: lib/planfile.py:909 `_save`（p2.fix_plan.json → plan-fields.json → reply.json の順。途中で落ちれば plan_accept の節が落ち、reply.json が無いので返りは ready: false）
  - 証: 拒否の側は tests/workflows/test_plan.py::AcceptCase.test_three_rejections_give_up_with_every_pointer（assert: tests/workflows/test_plan.py:599 の fields が空）。置けない時の試験は無い → 要追加: lib/tests/test_planfile.py::TakePlanCase.test_save_failure_leaves_no_accepted_plan — planmarks.save を OSError にすると take_plan が投げ、reply.json が無く accepted_fields が None
  - 本物の run: 筋書きでのみ
  - 狭め: 止め方を変えた（元は盤面を止めて理由に plan-fields.json を名指した。今は節が落ちて ready: false。理由の字は collect-error でなく why_not_ready の NO_PLAN になり、どの控えが置けなかったかが返りに残らない）。Archon で不可でない → 置けない訳を round.json の why か collect の reason に残すよう戻す

### 構造・世界の解・処方への答え

- P026 構造の目が汚れると見た単位を持つ項目は、行ごとに避け方に従う（follows）か外れの訳（deviation）を欄 structure に書かねば拒み、外れの訳は控えに残す。
  - 元: planmarks.py:763 `structure_gaps`・planblk.py:1236（planrange.answer_tables）、試験 works/tests/test_blk_plan.py:1435・:1445・:1451
  - 今: lib/planfile.py:754 `answer_tables`・:915・lib/planmarks.py:763
  - 証: tests/workflows/test_plan.py::AcceptCase.test_dirty_structure_row_needs_answer（assert: tests/workflows/test_plan.py:569）・lib/tests/test_plan_fields.py::TestStructure の 6 件（例 test_plan_without_structure_row_is_refused :677・test_plan_with_deviation_passes_and_is_recorded :711）
  - 本物の run: plan/r1/plan-fields.json の fields[].structure（構造の目が「汚れる」と見た時）・plan/structure/<鍵>/design.jsonl
  - 狭め: 無し

- P027 構造の目の行（汚れると見た行と避け方）を修正案の材料に貼り、従うか外れの訳を頼む。
  - 元: works/.shared/core/structmark.py:111 `plan_section`・planblk.py:1085 `prep`、試験 works/tests/test_blk_plan.py:1300 StructureHeadCase.test_design_rows_reach_plan_head
  - 今: lib/planfile.py:865（write_brief の structmark.plan_section）
  - 証: 要追加: tests/workflows/test_plan.py::BriefCase.test_dirty_structure_rows_reach_the_brief — eye_dirty の周の brief-1.md に structmark.PLAN_HEAD・PLAN_ASK・DIRTY_ROW の chosen が在り、「構造の目の行なしで計画した」が無い
  - 本物の run: plan/r1/brief-1.md の「構造の目の行」の節（目が汚れると見た時だけ行が出る）
  - 狭め: 無し（試験だけ欠け）

- P028 構造の目の行が無い周（実測が落ちた・目が 3 回拒まれた・目が走らなかった・控えが読めない）は、材料に「構造の目の行なしで計画した（理由）」と書き、行への答えを求めずに計画へ進む。
  - 元: structmark.py:78（MISSING）・darkfactory の h-structure、試験 works/tests/test_blk_plan.py:1311・:1318・:1328
  - 今: lib/structmark.py:33・:111・lib/planfile.py:732 `write_state`・:865
  - 証: tests/workflows/test_plan.py::CollectCase.test_eye_without_rows_leaves_failed_state（assert: tests/workflows/test_plan.py:770・:771）は控えが failed で ready: true なことだけ。材料に印が載るかは無い → 要追加: tests/workflows/test_plan.py::BriefCase.test_failed_structure_marks_the_brief — 目が行を返さない周の brief-1.md に「構造の目の行なしで計画した（理由: 」が在り、受け付けが structure の答えを求めない
  - 本物の run: 筋書きでのみ（健全な run では目が通る）
  - 狭め: 無し（試験だけ欠け）

- P029 paths の無い単位（構造の目が見ていない単位）を材料に名指す。
  - 元: 元は h-plan の structure_units_file の写しで同じ扱い（works/blk-structure/scripts/stage_a.py）
  - 今: lib/planfile.py:663 `_measured_units`・:783 `units_section`
  - 証: tests/workflows/test_plan.py::StageACase.test_unit_without_paths_is_skipped_and_named（assert: tests/workflows/test_plan.py:474）
  - 本物の run: plan/r1/brief-1.md（種の単位は paths を持つので出ない。筋書きでのみ）
  - 狭め: 無し

- P030 世界の解の行を材料に貼り、当たる行ごとにどれかの項目が従うか外れの訳を書かねば拒む。知らない類の id を名指す。
  - 元: planblk.py:424 `world_part`・worldmark.py:184 `section`・:59 `PLAN_ASK`、planmarks の world の表、試験 works/tests/test_blk_plan.py:1371・:1388・:1384
  - 今: lib/planfile.py:861（worldmark.section・PLAN_ASK）・:754 `answer_tables`
  - 証: tests/workflows/test_plan.py::AcceptCase.test_world_row_needs_answer（assert: tests/workflows/test_plan.py:576・:578）・lib/tests/test_plan_fields.py::TestWorldAnswers.test_unknown_world_class_is_named（:755）・test_world_row_no_item_answers_is_refused（:759）
  - 本物の run: plan/r1/brief-1.md の「## 世界の解の行」と plan/r1/plan-fields.json の fields[].structure の {world, follows|deviation}（judge が world の行を出した時）
  - 狭め: 世界の行を項目に場所で結ばない決まりの試験（元 works/tests/test_plan_fields.py:795 test_world_rows_bind_no_item_by_place）が無い → 要追加: lib/tests/test_plan_fields.py::TestWorldAnswers.test_world_rows_bind_no_item_by_place — planfile.answer_tables の世界の表で、範囲が重なる項目の of が空・答えの無い行が missing に残る

- P031 判定の処方を案に入れる単位ごとに材料に貼り、採らない処方は欄 structure の {prescription, deviation} で訳を書かせる（処方への答えは受け付けが通す）。
  - 元: planblk.py:356 `prescription_section`・planmarks.py:804 `prescriptions`、試験 works/tests/test_blk_plan.py:1464 test_plan_head_carries_prescriptions
  - 今: lib/planfile.py:334 `prescriptions`・:345 `prescription_section`・:863
  - 証: lib/tests/test_planfile.py::PrescriptionCase.test_section_lists_given_units_only（assert: :254）・lib/tests/test_plan_fields.py::TestStructure.test_prescription_answers_are_allowed（:706）。ブロックの材料に載るかは無い → 要追加: tests/workflows/test_plan.py::BriefCase.test_prescriptions_reach_the_brief — 判定の単位に prescriptions を持たせた周の brief-1.md に PRESCRIPTION_HEAD とその文
  - 本物の run: plan/r1/brief-1.md の「## 判定の処方」（judge が処方を書いた時）
  - 狭め: 無し（試験だけ欠け）

### 材料（修正案の役に渡す物）

- P032 修正案の役の指示書は元の p2.fix_plan.md の字のまま（許した 3 つの直し: 頭の 1 行・engine の雛形を外す・「材料の一覧の番号」）。
  - 元: works/.shared/core/gl-prompts/prompts/review-loop/p2.fix_plan.md（graphs/review-loop.json:3331）
  - 今: workflows/plan/commands/fix-plan.md
  - 証: tests/workflows/test_plan.py::ShapeCase.test_fix_plan_command_is_the_original_with_only_the_allowed_edits（assert: tests/workflows/test_plan.py:343・:345）・test_eye_command_reads_only_its_prep（:337）
  - 本物の run: plan-writer の節の会話（指示書の本文）。run の記録の node の prompt
  - 狭め: 無し

- P033 役の定義の頭: 読むだけ・JSON だけ・works の欄の書き方（planmarks.HEAD）・項目の組み方（ITEMS_RULE）・既にある物を先に探せ（REUSE_RULE）・考えの住処の決まり（concepthome.PLAN_RULE）・狭めない案を先に探せ（gatemarks.HEAD）。
  - 元: works/blk-plan/lib/planblk.py:243 `HEAD["plan"]`・:299 `head`
  - 今: lib/planblk.py:188・:222（前提の部品）・lib/planfile.py:842（write_brief が頭に置く）
  - 証: lib/tests/test_blk_plan.py::PlanFieldsCase.test_heads（assert: lib/tests/test_blk_plan.py:43）・ScriptCase.test_head_asks_no_narrow_first（:52）・ConceptRuleCase.test_plan_head_has_concept_rule（:115）。ITEMS_RULE・REUSE_RULE と、材料が頭を持つことは縛られていない → 要追加: tests/workflows/test_plan.py::BriefCase.test_brief_opens_with_the_role_head — brief-1.md が planblk.head("plan") で始まり ITEMS_RULE・REUSE_RULE を含む
  - 本物の run: plan/r1/brief-1.md の頭
  - 狭め: 無し。ただし頭の文「受け付けは起こす前の作業ツリーの写しと比べ、変わっていれば拒む」は今の受け付けに当たらない（P049）

- P034 単位の一覧（no・key・label・disposition・義務の区分・単位の paths・summary）と、問いの台帳・判定者の見立て（framing・one_shot・one_shot_closes）・判定者の先行例を材料に描く（元の engine の雛形の字）。入れてはいけない単位も label つきで並べる。
  - 元: p2.fix_plan.md の頭の雛形（{{record.units | pick …}} ほか）と planblk.py:328 `plan_slots_section`、試験 works/tests/test_blk_plan.py:717 test_slots_section_lists_must_may_and_shut・:951 test_prompt_rendered_from_mainline
  - 今: lib/planfile.py:783 `units_section`
  - 証: tests/workflows/test_plan.py::CollectCase.test_rounds_count_and_second_round_gets_review（assert: tests/workflows/test_plan.py:745）と lib/tests/test_planfile.py::UnitsSectionCase.test_filled_units_are_not_owed_in_the_brief（:388）は単位の行だけ。paths・summary・入れてはいけない単位・問いの台帳・見立て・先行例は縛られていない → 要追加: tests/workflows/test_plan.py::BriefCase.test_units_section_carries_catalog_ledger_and_view — 判定に nit の単位・fork の問い・precedents を持たせた周の brief-1.md に「paths: stats.py」「summary: mean の分母」「入れてはいけない単位（受け付けが拒む）: `<nit>`（label=nit」「問いの台帳」「判定者の見立て」「判定者の先行例」
  - 本物の run: plan/r1/brief-1.md の「## 今の周に直す単位」
  - 狭め: 無し（試験だけ欠け）

- P035 リポジトリ・読む版・BASE・観点の正本（REVIEW.md）の行を材料に描く。
  - 元: p2.fix_plan.md の雛形の行（inputs.cwd・inputs.review_rev・record.base・inputs.review_md）
  - 今: lib/planfile.py:108 `REPO_LINE`・:860
  - 証: 要追加: tests/workflows/test_plan.py::BriefCase.test_repo_line_names_base_and_review_md — brief-1.md に「リポジトリ: <対象>（読む版: `<base_rev>`）」と「観点の正本: …/REVIEW.md」
  - 本物の run: plan/r1/brief-1.md の「リポジトリ:」の行
  - 狭め: 読む版を BASE と同じ値にした（元は review_rev と base を別に持てた）。Archon で不可でない。差分の run（base と review の版が違う run）で効くかは持ち主に

- P036 並行 PR の外した範囲（判定の隣の pr-excluded.json）を頭で名指し、無ければ貼らない。
  - 元: planblk.py:299 `head`（EXCLUDED_HEAD :111）、試験 works/tests/test_blk_plan.py:1042 test_excluded_range_named
  - 今: lib/planfile.py:842（`_neighbor(judgment_dir, "pr-excluded.json")`）
  - 証: 要追加: tests/workflows/test_plan.py::BriefCase.test_excluded_range_named — judge/pr-excluded.json を置いた周の brief-1.md に planblk.EXCLUDED_HEAD とそのパス、置かない周に無い（plan-review 側は ReviewAcceptCase.test_excluded_range_named が在る）
  - 本物の run: plan/r1/brief-1.md（PR の入口の run だけ。種では筋書きでのみ）
  - 狭め: 無し（試験だけ欠け）

- P037 判定の単位の裏取りの申し送り（判定の隣の judge-verify.json）を修正案の役にだけ貼り、読めなければその 1 行、無ければ貼らない。
  - 元: planblk.py:550 `verify_part`・:1085 `prep`（入力 verify_file）、試験 works/tests/test_blk_plan.py:1055 test_verify_notes_pasted_for_plan_only
  - 今: lib/planblk.py:432 `verify_part`・lib/planfile.py:868
  - 証: 要追加: tests/workflows/test_plan.py::BriefCase.test_verify_notes_pasted — judge/judge-verify.json（not_root の行）を置いた周の brief-1.md に VERIFY_HEAD と real_root の字、置かない周に無い
  - 本物の run: plan/r1/brief-1.md の「## 判定の単位の裏取り」（標準の厚さで単位が 2 つ以上なら judge が judge/judge-verify.json を書くので、種の run で見える）
  - 狭め: 無し（試験だけ欠け）

- P038 判定の単位のファイルが使うライブラリの文書の節を頭に貼る（網に出ない時はその旨）。
  - 元: planblk.py:462 `lib_section`、試験 works/tests/test_blk_plan.py:951 test_prompt_rendered_from_mainline（「ライブラリの文書を取る物は無い（0 本）」）
  - 今: lib/planfile.py:226 `lib_section`・workflows/plan/scripts/plan_prep.py:38
  - 証: 要追加: tests/workflows/test_plan.py::BriefCase.test_brief_carries_lib_docs_section — 種の brief-1.md に libdocs.TITLE と「ライブラリの文書を取る物は無い（0 本）」（lib/tests/test_libdocs*.py は部品だけ）
  - 本物の run: plan/r1/brief-1.md の libdocs の節（種は標準ライブラリだけなので「0 本」）
  - 狭め: 無し（試験だけ欠け）

- P039 人の方針の段落（方針の文書の置き場と「方針に反するものを自分の判断で通すな」）を、方針の文書が在る時だけ貼る。
  - 元: p2.fix_plan の prompt_append（gl-prompts/prompts/policy-path.md・policy.md。graphs/review-loop.json の reads inputs.policy_md）
  - 今: lib/planfile.py:111 `POLICY_PART`・:871
  - 証: tests/workflows/test_plan.py::BriefCase.test_brief_carries_policy_concept_map_and_prior_failures（assert: tests/workflows/test_plan.py:861）・test_without_policy_or_prior_failures_neither_section（:870）
  - 本物の run: 種に方針の文書が無いので段落は出ない（無いことが plan/r1/brief-1.md で見える）
  - 狭め: 無し

- P040 考えの住処の地図（在れば地図、無ければ無い旨）を材料に貼る。
  - 元: 包みが旗 concept-map の役の system prompt に足した concepthome.section（works/.shared/core/concepthome.py:117）、試験 works/tests/test_blk_plan.py:1562 test_roles_carry_concept_map_flag
  - 今: lib/planfile.py:849
  - 証: tests/workflows/test_plan.py::BriefCase.test_brief_carries_policy_concept_map_and_prior_failures（assert: tests/workflows/test_plan.py:864）
  - 本物の run: plan/r1/brief-1.md の「## 考えの住処の地図」（種は地図が無い旨）
  - 狭め: 無し

- P041 前の run で最後まで通らなかった物（prior_failures）を材料に貼り、周のフォルダに写しを置く。形が違えば読めなかった入力として名指す。
  - 元: planblk.py:456 `prior_part`・carry.py:244 `prior_section`
  - 今: lib/planfile.py:893 `prior_section`・入力 prior_failures（workflows/plan/works-factory-plan.yaml の inputs）。線は渡す（workflows/line/works-factory-line.yaml:201・:486）
  - 証: tests/workflows/test_plan.py::BriefCase.test_brief_carries_policy_concept_map_and_prior_failures（assert: :862・:863）・test_prior_failures_of_wrong_shape_are_named_unread（:878・:879）・lib/tests/test_planfile.py::PriorFailuresCase（:433・:440）
  - 本物の run: 1 回目の run では無い。2 回目の run の plan/r1/prior-failures-in.json と brief-1.md の carry.PRIOR_HEAD（筋書きでのみ）
  - 狭め: 無し（入力を足した。#75 の約束を変える頼み 1 つ目は線が渡す形で済んでいる）

- P042 役に人が読む文の欄を書く言語を 1 行で縛る（始めの記録の lang。無ければ依頼文の言語）。
  - 元: works/.shared/core/rolekit.py:147 `lang_line`・:67 `LANG_RULE`
  - 今: lib/planfile.py:767 `lang_line`・:874
  - 証: 要追加: tests/workflows/test_plan.py::BriefCase.test_brief_ends_with_language_rule — start の lang「日本語」で brief-1.md の末尾の行が LANG_RULE.format(lang="日本語")、lang が空なら LANG_DEFAULT
  - 本物の run: plan/r1/brief-1.md の最後の行
  - 狭め: 無し（試験だけ欠け）

- P043 仕様（judge の spec）が在れば、要件と受け入れテストを材料に貼り、受け入れテストを項目の tests に入れさせる。
  - 元: 元の修正案の役には無い（仕様は判定への依頼として届いた）。今の方が広い
  - 今: lib/planfile.py:109 `SPEC_HEAD`・:869
  - 証: 要追加: tests/workflows/test_plan.py::BriefCase.test_spec_reaches_the_brief — spec の指し札を渡すと brief-1.md に SPEC_HEAD と本文、null なら無い
  - 本物の run: 種は spec を使わないので出ない
  - 狭め: 無し（元より広い）

- P044 読めなかった入力（world・spec・conflicts・prior_failures）を材料の「読めなかった入力」の節に名指し、その節を貼らずに進む。
  - 元: 元は盤面の入力の読み損ねを BoardGap で落とした。名指して進むのは今の足し
  - 今: lib/planfile.py:115・:872・workflows/plan/scripts/plan_prep.py:31
  - 証: tests/workflows/test_plan.py::BriefCase.test_prior_failures_of_wrong_shape_are_named_unread（assert: :878・:879）。world・spec・conflicts の場合は無い（world は P045 で役を起こさない側に倒れる）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P045 線が渡した指し札（start・review・world・判定）が読めない周は、既定の値で進まずに役を起こさず ready: false とし、訳（どの入力が読めないか・指し札の先）を残す。空の字と null だけが「無い」。
  - 元: 盤面の入力の読みの BoardGap（script が exit 2 で落ちる。works/tests/test_blk_plan.py:1227 test_scripts_exit_two_on_wiring）
  - 今: workflows/plan/scripts/round.py:34-43・lib/planfile.py:164 `pointed`
  - 証: tests/workflows/test_plan.py::CollectCase.test_unreadable_pointer_inputs_are_not_absent（assert: tests/workflows/test_plan.py:804・:807・:808・:812）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（落ちる代わりに訳つきで止まる形）

- P046 前の拒否の理由はファイル（reject-<n>.txt）に置き、次の回の材料の 1 行目がそのパスを名指す（理由の本文は貼らない）。
  - 元: rolekit.py:64 `REJECT_LINE`・:168 `compose`、試験 works/tests/test_blk_plan.py:1012 test_reject_reason_by_file（本文を貼らないことも断言）
  - 今: lib/planfile.py:100・:760 `compose`・:824 `write_brief`
  - 証: tests/workflows/test_plan.py::AcceptCase.test_narrow_without_no_narrow_rejected（assert: tests/workflows/test_plan.py:590）は 1 行目だけ。本文を貼らないことは縛られていない → 要追加: 同じ試験に「brief-2.md に拒否の理由の 1 行目（narrows の行に狭めない案を…）が無い」と「plan/r1/reject-1.txt が理由の全文」の断言を足す
  - 本物の run: plan/r1/reject-1.txt と plan/r1/brief-2.md の 1 行目（拒否が起きた時）
  - 狭め: 無し

### 輪・出口・返り

- P047 拒否の後は新しい会話で出し直し、3 回目の拒否で受け付けが done・give_up を出して輪を抜ける（max_iterations で落とさない）。返りは ready: false、訳は「3 回とも受け付けで拒まれた」。
  - 元: works/blk-plan/blk-plan.yaml:231 plan-loop（fresh_context: true・until_bash）・planblk.py:1441 `collect`（盤面を止める STOP_BY works:plan、gave_up・reason_file）、試験 works/tests/test_blk_plan.py:1024 test_give_up_ends_loop
  - 今: workflows/plan/works-factory-plan.yaml:210-218・workflows/plan/scripts/plan_accept.py:38-41・lib/planfile.py:1011 `why_not_ready`
  - 証: tests/workflows/test_plan.py::AcceptCase.test_three_rejections_give_up_with_every_pointer（assert: tests/workflows/test_plan.py:596・:598・:601）・ShapeCase.test_loops_give_up_in_the_body_before_max_iterations（:362・:364・:365）・筋書き workflows/plan/fixtures/give-up.stubs.yaml（FixtureCase :895）
  - 本物の run: plan-accept の節の出力 {ok, done, give_up, attempt}・plan/r1/rejects-plan.json・ripple.json の error（諦めた時だけ。健全な種では筋書きでのみ）
  - 狭め: 結末の形を変えた（元は盤面を止め、返りに gave_up と reason_file。今は ready: false と ripple.json の error の字だけ）。docs/design.md:206 の決め。P011 と同じ持ち主への問い

- P048 修正案の役は読むだけで、道具を絞り（Read・Grep・Glob・WebSearch・WebFetch）、利用者の設定だけを読み、sandbox の中で、opus・effort medium で走る。期限を足さない（20 日）。
  - 元: works/blk-plan/blk-plan.yaml:260-275（model・effort・settingSources・allowed_tools・mutates_checkout・sandbox・idle_timeout）、試験 works/tests/test_tool_parity.py・test_blk_plan.py:237
  - 今: workflows/plan/works-factory-plan.yaml:234-245
  - 証: tests/workflows/test_plan.py::ShapeCase.test_role_nodes_are_read_only_and_isolated（assert: tests/workflows/test_plan.py:323-330）・test_deadlines_are_all_twenty_days（:352-356）
  - 本物の run: run の記録の plan-writer の節の設定
  - 狭め: 無し

- P049 役が作業ツリーを変えた・commit して HEAD や枝を動かした返答を、受け付けが写しと比べて拒み、出し直させる。
  - 元: entry.take の作業ツリーの比べ（accept.tree_moved: porcelain・差分・HEAD・枝。READONLY_MOVED）・planblk.py:1062 `snap` の写し、試験 works/tests/test_blk_plan.py:765 test_readonly_tree_changed_rejected
  - 今: 無し（Archon の mutates_checkout: false に任せた）
  - 証: 要追加: tests/workflows/test_plan.py::AcceptCase.test_role_that_moved_the_tree_is_refused — plan-prep の後に対象を書き換えるか commit してから受け付けると拒まれる（plan-review は accept.tree_moved を残した: #73）
  - 本物の run: 筋書きでのみ
  - 狭め: #75 で狭めた（本文に書かれていない）。Archon で不可でない: Archon の比べは git status --porcelain だけで HEAD の動きを見ず（Archon packages/workflows/src/dag-executor.ts:1196-1215 `snapshotCheckout`）、違反は役に返さず節を落とす（同:1262-1280 `assertCheckoutUntouched`）。役の道具に Bash・Write・Edit が無いので今は起きにくいが、元の能力（出し直しの道と HEAD の比べ）は落ちている → plan-prep で accept.tree_state を置き plan-accept で accept.tree_moved を照らす形で戻す（plan-review と揃う）

- P050 1 回目の差し込みでは事前審査の指摘を空の字も null も「まだ無い」と読み、2 回目からは受けた事前審査を周のフォルダに写す。
  - 元: 盤面の converge の控え（往復は blk-plan の中）
  - 今: lib/planfile.py:623 `open_round`（review/p2.plan_review.json）
  - 証: tests/workflows/test_plan.py::CollectCase.test_first_round_reads_empty_and_null_review_alike（assert: tests/workflows/test_plan.py:724・:726・:727）・test_rounds_count_and_second_round_gets_review（:741）
  - 本物の run: 2 往復目の plan/r2/review/p2.plan_review.json（事前審査が止めた時だけ）
  - 狭め: 無し（2 往復目の中身は PB）

- P051 周の番号は往復と案の直しを通して数え、返りの round に載せる。
  - 元: 盤面の周（b.round）
  - 今: lib/planfile.py:593 `next_round`・:623
  - 証: tests/workflows/test_plan.py::CollectCase.test_rounds_count_and_second_round_gets_review（assert: tests/workflows/test_plan.py:731・:739）・ReplanCase.test_replan_rejects_extra_items_and_changed_keys_then_amends（:631）・lib/tests/test_planfile.py::RoundCase.test_next_round_counts_round_folders（:463）
  - 本物の run: plan の節の出力 round（種の 1 往復で 1）
  - 狭め: 無し

- P052 周を開く節は落ちない（lib が読めなくても周を go: false・訳つきで開き、途中で残った周のフォルダを引き継ぐ）。
  - 元: 元は snap が exit 2 で落ちた（盤面の外に周は無い）。今の足し
  - 今: workflows/plan/scripts/round.py:47-68
  - 証: tests/workflows/test_plan.py::SurvivesCase.test_round_and_return_node_survive_a_lib_that_does_not_load（assert: tests/workflows/test_plan.py:824・:826・:834）・test_round_takes_over_a_folder_left_half_open（:840）・ShapeCase.test_fallback_names_match_lib（:422）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P053 返す節は落ちない: どの誤りでも ready: false と、在って空でない指し札の先 3 つ（plan-fields.json・structure-state.json・ripple.json）を返し、訳を collect-error.txt に書く。
  - 元: planblk.py:1441 `collect`（ok・plan_file・ripple_file ほか）
  - 今: workflows/plan/scripts/plan_collect.py:57-90・lib/planfile.py:1056 `placeholders`
  - 証: tests/workflows/test_plan.py::CollectCase.test_broken_inputs_still_return_the_contract（assert: tests/workflows/test_plan.py:704・:705・:712・:717）・SurvivesCase（:828・:829・:833）
  - 本物の run: plan の節の出力の plan・structure・ripple の指し札（path が plan/r1/… を指す）
  - 狭め: 無し

- P054 返りの約束: ready・plan・structure・ripple の指し札（archon_artifact）・depth・round を、ちょうどこの 6 つで返す。
  - 元: works/blk-plan/blk-plan.yaml:995 collect の output_format（ok・plan_file・review_file・asks_human・gate_kinds・reads_file・gave_up・reason_file・ripple_file）
  - 今: workflows/plan/works-factory-plan.yaml:533-560
  - 証: tests/workflows/test_plan.py::ShapeCase.test_return_node_carries_exactly_the_contract（assert: tests/workflows/test_plan.py:299-310）・test_name_inputs_and_return（:294・:295）
  - 本物の run: plan の節の出力
  - 狭め: asks_human・gate_kinds・review_file は plan-review の返りへ移した（PE・PD）。gave_up・reason_file は P047。reads_file は P057

- P055 受け付けた案の項目ごとに、変える名の呼び出し元と試験の当たり（覆っていない当たりを含む）を波及の一覧 ripple.json に作って返す。案が無い周は {items: [], error: <訳>}。
  - 元: works/blk-plan/lib/planblk.py:478 `make_ripple`（stage items・RIPPLE_LATEST）・works/blk-plan/lib/ripple.py:171 `build`
  - 今: lib/planfile.py:1028 `ripple_items`・lib/ripple.py:171・workflows/plan/scripts/ripple_items.py
  - 証: tests/workflows/test_plan.py::ReplanCase.test_replan_rejects_extra_items_and_changed_keys_then_amends（assert: tests/workflows/test_plan.py:655 の request_ok.json:8 が 1 回目の覆っていない当たり）・AcceptCase.test_three_rejections_give_up_with_every_pointer（:600・:601）・lib/tests/test_ripple.py::RippleCase.test_literal_test_not_in_rewrite_is_uncovered（:92）・test_caller_outside_scope_is_uncovered（:101）。1 回目の差し込みで中身を見る試験は AcceptCase.test_accepted_plan_files の error が空（:528）だけで弱い → 要追加: AcceptCase.test_accepted_plan_has_item_ripple — 種の 1 回目の ripple.json の items[0] の uncovered に request_ok.json:8 が在る
  - 本物の run: plan/r1/ripple.json の items[].uncovered（返りの ripple の指し札の先）
  - 狭め: 無し

- P056 案を書く前に、単位の key が名指す名の呼び出し元と試験の一覧を作って材料に貼る（案の直しでは作らない）。文書・CHANGELOG・実行基盤の写し（.archon）は当たりに数えず、git が無くても落ちずに error を書く。
  - 元: planblk.py:478 `make_ripple`（stage units）・:574 `units_ripple_part`・ripple.py:184 `for_units`・:246 `units_section`
  - 今: lib/planfile.py:1003 `ripple_units`・:867・workflows/plan/scripts/ripple_units.py:17（SKIP_DIRS .archon）
  - 証: tests/workflows/test_plan.py::ReplanCase.test_replan_rejects_extra_items_and_changed_keys_then_amends（assert: :632 の ripple-units が飛ぶ）・lib/tests/test_ripple.py::RippleCase.test_units_have_hits_without_coverage（:137）・test_docs_and_generated_copies_are_not_hits（:85）・test_not_a_repo_gives_error_not_raise（:143）。材料に一覧が載るかは縛られていない → 要追加: tests/workflows/test_plan.py::BriefCase.test_units_ripple_reaches_the_brief — 種の brief-1.md に ripple.UNITS_HEAD と mean・clamp の当たり（元 works/tests/test_blk_plan.py:2215 test_units_ripple_reaches_plan_prompt）
  - 本物の run: plan/r1/ripple-units.json と plan/r1/brief-1.md の「## 波及の一覧（…単位の key が名指す名…）」
  - 狭め: 無し

- P057 この周に描いた役ごとに、機械が渡したパス（描いた指示書・方針の文書）を読んだ証拠を集めて索引に書く（受け付けの条件にはしない）。
  - 元: works/blk-plan/lib/planblk.py:1393 `collect_reads`・blk-plan.yaml:978 plan-reads、試験 works/tests/test_reads.py（25 件）
  - 今: 無し
  - 証: 要追加: tests/workflows/test_plan.py::ReadsCase.test_writer_reads_its_brief_are_recorded — run の記録の provider_event の Read の呼びから、plan-writer が brief-<n>.md（と方針の文書）を読んだかを plan/r<k>/reads.json に書く
  - 本物の run: Archon の run の記録 <logDir>/<run_id>.jsonl の type provider_event・step plan-writer の Read の行（今は誰も集めない）
  - 狭め: #75・#73 で狭めた（docs/design.md:436・:570 の U6「取れるか未決」）。Archon で不可でない: Archon は役の道具の呼びを step 名つきで run の記録に残す（packages/workflows/src/logger.ts:129-130 `getLogPath` が <logDir>/<runId>.jsonl、:298-310 `logProviderEvent`、packages/workflows/src/store.ts:156 provider_event、packages/core/src/db/workflow-events.ts:257-262 で tool_call {name, rawInput} に読める）→ U6 は「取れる」で決まる。戻す

- P058 工程の地図（旗 map で包みが system prompt に工程の地図とこの会話の居場所を足す）。
  - 元: planblk.py:105 `MAP_FLAG`・graphmap.render（works/.shared/core/graphmap.py）
  - 今: 無し
  - 証: 無し（落とした物）
  - 本物の run: 無し
  - 狭め: docs/design.md:435「落とす。Archon の YAML がそのまま地図」で落とした（持ち主の文書の決め）。Archon で不可ではない（節の systemPrompt に字で足せる）。持ち主の決めとして扱う

- P059 単位ごとの深さ（軽量・標準と訳）を、直す義務の単位だけについて、受け付けた案の欄と始めの記録の厚さ（thickness）・試験の命令の有無から決めて返す。案が無ければ空。
  - 元: works/darkfactory/lib/depth.py:244 `decide`（線の h-depth が h-fix.open_units で呼んだ。depth.json を書いた）
  - 今: lib/planfile.py:1041 `collect`・:1035 `owed_order`・workflows/plan/scripts/plan_collect.py:39-40
  - 証: tests/workflows/test_plan.py::AcceptCase.test_accepted_plan_files（assert: tests/workflows/test_plan.py:529）・SurvivesCase.test_question_with_depends_that_is_not_a_list（:849 の義務の単位だけ）・lib/tests/test_depth.py::DecideCase.test_forced_word_fixes_every_unit（:102）・BoardReadCase.test_decide_without_checks_is_standard（:207）。ブロックが start の thickness と test_cmd を渡すかは縛られていない → 要追加: tests/workflows/test_plan.py::CollectCase.test_depth_follows_start_thickness_and_checks — start の thickness「標準」で全部の単位が標準、test_cmd も tdd_suite も空なら軽量にならない（訳つき）
  - 本物の run: plan の節の出力 depth（種の厚さ 標準 なら全部 標準）
  - 狭め: depth.json の控え（深さの上げ直しが読む）はブロックが書かない。上げ直しは線（workflows/line/scripts/redepth.py）の持ち物なので PA の外


## 構造の実測（直しの前）と構造の目（計画のブロックの中）

- P060 判定の単位のうち paths の在る単位だけを、単位ごとに measure.py（子のプロセス 1 つの口）で測り structure.json に書く（単位の id・summary・paths・status・measure）
  - 元: works/blk-structure/scripts/stage_a.py:96 `main`・:76 `measure_unit`
  - 今: lib/planfile.py:679 `measure`・lib/stage_a.py `measure_unit`・workflows/plan/scripts/structure_measure.py `main`
  - 証: tests/workflows/test_plan.py::StageACase.test_measures_units_and_writes_empty_design_rows（assert: tests/workflows/test_plan.py:449-452 の status ok・単位の id の並び・design.jsonl 0 バイト・eye true）
  - 本物の run: `plan/structure/<鍵>/structure.json` の `status`=ok と `units[].id`=判定の単位の id、`units[].measure.schema`=`measure/1`
  - 狭め: 無し

- P061 paths が空の単位は測らずに skipped-units.json に名を残し、修正案の材料に「構造の目が見ていない単位」として名指す
  - 元: works/darkfactory/lib/line_edge.py `structure_units`（paths の無い単位も落とさない）と元の修正案の頭の構造の節
  - 今: lib/planfile.py:663 `_measured_units`・:695-696（units.json と skipped-units.json）・:783 `units_section`
  - 証: tests/workflows/test_plan.py::StageACase.test_unit_without_paths_is_skipped_and_named（assert: tests/workflows/test_plan.py:471-474）
  - 本物の run: `plan/structure/<鍵>/skipped-units.json`（種の 2 単位は stats.py を名指すので `[]`）。名指しの行は筋書きでのみ
  - 狭め: 無し

- P062 実測が落ちた（git の無い対象・measure.py の非 0 終了・出力が JSON でない）単位は structure.json の status: failed と reason に残し、線を止めない
  - 元: works/blk-structure/scripts/stage_a.py:76-88 `measure_unit`・:113-115
  - 今: lib/stage_a.py `measure_unit`・lib/planfile.py:706-708
  - 証: tests/workflows/test_plan.py::StageACase.test_measure_failure_and_unreadable_units_do_not_stop（assert: tests/workflows/test_plan.py:458-459）
  - 本物の run: 筋書きでのみ（健全な種では落ちない）
  - 狭め: 無し

- P063 単位の目録が読めない・形が違う時も structure.json を status: failed と訳つきで書き、構造の目を起こさない（eye: false）
  - 元: works/blk-structure/scripts/stage_a.py:52-70 `read_units`・:104-107
  - 今: lib/stage_a.py `read_units`・lib/planfile.py:701-703
  - 証: tests/workflows/test_plan.py::StageACase.test_measure_failure_and_unreadable_units_do_not_stop（assert: tests/workflows/test_plan.py:462-464）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P064 設計の行のファイル design.jsonl を毎回 0 バイトで置き直し（JSON Lines なので改行も書かない）、前の目の控え eye.json を消す
  - 元: works/blk-structure/scripts/stage_a.py:100-102
  - 今: lib/planfile.py:698-699
  - 証: tests/workflows/test_plan.py::StageACase.test_measures_units_and_writes_empty_design_rows（assert: tests/workflows/test_plan.py:451 の st_size == 0）。eye.json を消す所は 要追加: tests/workflows/test_plan.py::StageACase.test_fresh_measure_drops_old_eye_state — 鍵の置き場に前の eye.json を置いてから測ると消えていること
  - 本物の run: `plan/structure/<鍵>/design.jsonl`（目の受け付けの後は行が入る）
  - 狭め: 無し

- P065 対象の根に考えの地図（docs/concepts.md）と柵の表（docs/concepts.json）が在れば、単位のパスに当たる地図の行と、単位のファイルの知る場所の数（home・known_places）を単位の concepts に置く。当たらない考えの行は載せない
  - 元: works/blk-structure/lib/context.py:93 `concepts`・:71 `find`
  - 今: lib/context.py:93 `concepts`・:71 `find`（字のまま）
  - 証: tests/workflows/test_plan.py::StageACase.test_eye_sees_concept_rows_and_policy（assert: tests/workflows/test_plan.py:492-493。当たる行と known_places の在ることだけ）。弱い: 元 works/tests/test_blk_structure.py:609 EyeInputsCase.test_eye_sees_concept_rows_for_unit_paths が見ていた「当たらない考え（halt）の行を載せない」「places の (concept, path, home, known_places) の値」を見ない → 要追加: tests/workflows/test_plan.py::StageACase.test_concept_rows_only_for_unit_paths — 2 つの考えの表で単位に当たらない行が prompt に無いこと・places の値が `("outcome","src/edge.py",False,2)`
  - 本物の run: `plan/structure/<鍵>/structure.json` の `units[].concepts`（種は地図が無いので `{"rows":[],"places":[]}`）
  - 狭め: 無し

- P066 地図も柵の表も無い対象は実測だけで判じ、地図や表を作らない（concepts は空の並び）
  - 元: works/blk-structure/lib/context.py 冒頭の「作らない」・works/tests/test_blk_structure.py:625 `test_no_map_no_table_measures_only`
  - 今: lib/context.py:71 `find`・:93 `concepts`
  - 証: 要追加: tests/workflows/test_plan.py::StageACase.test_no_map_no_table_measures_only — 地図の無い種で `concepts == {"rows": [], "places": []}` かつ対象に docs/ が作られないこと
  - 本物の run: `plan/structure/<鍵>/structure.json` の `units[].concepts` が空（種に地図が無い）、対象の作業ツリーに docs/ が増えない
  - 狭め: 無し

- P067 方針の文書（始めの記録の policy_md）の中身と根の地図の文書（AGENTS.md など。design.repo_map の探し方）を structure.json の rules に置き、構造の目に見せる。長い文書は TEXT_CAP（6000 字）で切って印を付ける
  - 元: works/blk-structure/lib/context.py:40 `rules`
  - 今: lib/context.py:40 `rules`・lib/planfile.py:710（policy_path は start.policy_md。workflows/plan/scripts/structure_measure.py:24-25）
  - 証: tests/workflows/test_plan.py::StageACase.test_eye_sees_concept_rows_and_policy（assert: tests/workflows/test_plan.py:494 の方針の文）。弱い: 根の地図の文書（元 test_eye_sees_policy_text の「層は下へだけ依存する」）と切りの印を見ない → 要追加: tests/workflows/test_plan.py::StageACase.test_eye_sees_root_map_and_cut_policy — AGENTS.md の文が prompt に載り、6000 字を超える方針に「字を切った」の印が付くこと
  - 本物の run: `plan/structure/<鍵>/structure.json` の `rules.maps`・`rules.policy.path`
  - 狭め: 無し

- P068 段 A の時間を structure.json の timing（started_at・finished_at・wall_s）に残す
  - 元: works/blk-structure/scripts/stage_a.py:120 `eye.stamp`
  - 今: lib/planfile.py:711 `eye.stamp`
  - 証: 要追加: tests/workflows/test_plan.py::StageACase.test_measure_records_timing — structure.json の timing に wall_s（数）と started_at・finished_at が在ること（元 works/tests/test_blk_structure.py:516 が `_found(structure,"wall_s")` で見ていた）
  - 本物の run: `plan/structure/<鍵>/structure.json` の `timing.wall_s`
  - 狭め: 無し

- P069 構造の目は実測が ok で測れた単位が 1 つ以上の周だけ起こす（eye.due）。落ちた・測れた単位が無い周は目の会話を起こさない
  - 元: works/blk-structure/lib/eye.py:107 `due`・works/blk-structure/blk-structure.yaml:87
  - 今: lib/eye.py:107 `due`・workflows/plan/works-factory-plan.yaml:88 `when: "$structure-measure.output.eye == true"`
  - 証: tests/workflows/test_plan.py::StageACase.test_measure_failure_and_unreadable_units_do_not_stop（assert: tests/workflows/test_plan.py:464 の eye false）。弱い: due の 3 通りを元 works/tests/test_structure_eye.py:162 EyeLoopGateCase は値で縛った → 要追加: lib/tests/test_structure_eye.py::EyeLoopGateCase.test_due_needs_ok_and_a_measured_unit — `(eye.due(DOC), eye.due({**DOC,"status":"failed"}), eye.due({**DOC,"units":DOC["units"][1:]})) == (True, False, False)`
  - 本物の run: 節 `structure-measure` の出力 `eye`=true と節 `structure-eye-loop` が走った記録
  - 狭め: 無し

- P070 同じ単位の目録と同じ HEAD なら実測と構造の目を使い回す（plan/structure/<鍵>/。鍵は目録と HEAD の sha256 の頭 12 字）。2 往復目は測らず目も起こさない
  - 元: works/darkfactory/darkfactory.yaml:443-466（構造は run で 1 度、planning の前。往復の中で測り直さない）
  - 今: lib/planfile.py:605 `structure_key`・:671 `structure_dir`・:685-687（reused）
  - 証: tests/workflows/test_plan.py::StageACase.test_same_units_and_head_reuse_the_measure（assert: tests/workflows/test_plan.py:500-502）・lib/tests/test_planfile.py::RoundCase.test_structure_key_follows_units_and_head
  - 本物の run: 2 往復目の節 `structure-measure` の出力 `reused`=true と `structure-eye-loop` の skipped、`plan/r1/round.json` と `plan/r2/round.json` の `structure` が同じ（往復が起きた run だけ）
  - 狭め: 無し

- P071 役を起こさない周（直す義務の単位が無い・行き止まり・入力が読めない）は測らず目も起こさず、使い回す実測の控えを汚さずに周のフォルダの structure/ に「測らなかった訳」つきの failed の控えを書く
  - 元: works/darkfactory/lib/line_edge.py `structure_edge(plan_go=False)`・works/darkfactory/darkfactory.yaml:454-457
  - 今: lib/planfile.py:644-645（why の在る周の structure は `r<k>/structure`）・:732 `write_state(skipped=…)`・workflows/plan/scripts/structure_state.py
  - 証: tests/workflows/test_plan.py::CollectCase.test_nothing_owed_skips_the_role（assert: tests/workflows/test_plan.py:780-784）・lib/tests/test_planfile.py::ReplanInputsCase.test_round_without_role_gets_its_own_structure_folder
  - 本物の run: 筋書きでのみ（種は直す義務の単位が在る）
  - 狭め: 無し（元は控えを書かなかった。今は返りの指し札が空であってはならない約束のために訳つきの failed を書く。能力は落ちていない）

- P072 構造の目の指示書は、実測できた単位だけ・問い 1 つ（concepthome.EYE_ASK）・6 つの形の番号つきの一覧・返し方を貼る。測れなかった単位は見せない。前の回の拒否の理由が在れば頭に貼り「丸ごと出し直せ」と言う
  - 元: works/blk-structure/lib/eye.py:151 `render`・:51 `FORMS`
  - 今: lib/eye.py:151 `render`（字のまま）
  - 証: 要追加: lib/tests/test_structure_eye.py::EyeAcceptCase.test_prompt_carries_only_measured_units_and_the_forms — 元 works/tests/test_structure_eye.py:44 と同じく u-1 が在り u-2 が無い・EYE_ASK と `1. …`〜`6. …` が在る・拒否の理由つきで「前の回の受け付けが拒んだ理由」が在る（今の test_evidence_indexes_the_units_the_prompt_showed は u-1 の在ることしか見ない）
  - 本物の run: `plan/structure/<鍵>/eye-prompt-1.md` に問いと 6 つの形と stats.py の単位
  - 狭め: 無し

- P073 6 つの形の文は設計書の一覧と一字も違わない（faces の 1〜6 の意味の正本を 1 つにする）
  - 元: works/tests/test_structure_eye.py:39 `test_six_forms_are_the_design_doc_list`（設計書 structure-block-design の 4 節）
  - 今: lib/eye.py:51 `FORMS` だけ（main に設計書の 4 節の一覧が無い）
  - 証: 要追加: lib/tests/test_structure_eye.py::EyeAcceptCase.test_six_forms_match_the_design_doc — docs/design.md（か写した設計書）の番号つきの一覧と eye.FORMS が等しいこと。正本の文書を main に置くかは持ち主に聞く
  - 本物の run: 筋書きでのみ
  - 狭め: lib-port で正本の文書との照らしが外れた（#75・#73 ではない）。Archon で不可でない → 戻す（正本の置き場を決めて照らしを戻す）

- P074 指示書は単位の要約が世界の解（定石）を名指していれば、汚れる行の避け方 chosen をその作りに沿わせ、沿わないなら訳を chosen_reason に書けと頼む
  - 元: works/blk-structure/lib/eye.py:165-166
  - 今: lib/eye.py:165-166
  - 証: lib/tests/test_structure_eye.py::EyeAcceptCase.test_prompt_asks_chosen_to_follow_world_practice（assert: lib/tests/test_structure_eye.py:31-33）
  - 本物の run: `plan/structure/<鍵>/eye-prompt-1.md` の「定石」の行
  - 狭め: 無し

- P075 目に見せる duplicates は先頭 DUP_SHOWN（5）件に切り、全件の数を duplicates_total に置く（支度の出力が実行基盤の標準出力の上限を越えて線が落ちた事故の再発止め）
  - 元: works/blk-structure/lib/eye.py:91 `_cut`
  - 今: lib/eye.py:91 `_cut`
  - 証: lib/tests/test_structure_eye.py::EyeAcceptCase.test_long_duplicates_are_cut_with_the_total（assert: lib/tests/test_structure_eye.py:111-114）
  - 本物の run: 筋書きでのみ（種は小さい）
  - 狭め: 無し

- P076 構造の目は道具ゼロ・opus・effort high・設定は user だけ・sandbox 有効・作業ツリーを変えない独立の会話で、指示書は支度の節の出力だけを読む
  - 元: works/blk-structure/blk-structure.yaml:108-121
  - 今: workflows/plan/works-factory-plan.yaml:110-120・workflows/plan/commands/structure-eye.md（元と字のまま）
  - 証: tests/workflows/test_plan.py::ShapeCase.test_role_nodes_are_read_only_and_isolated（assert: tests/workflows/test_plan.py:323-330）・ShapeCase.test_eye_command_reads_only_its_prep（assert: tests/workflows/test_plan.py:335）。弱い: structure-eye.md の本文が元と同じことは縛らない → 要追加: tests/workflows/test_plan.py::ShapeCase.test_eye_command_is_the_original — 元 blk-structure/commands/structure-eye.md の sha256 と一致（fix-plan.md と同じ形）
  - 本物の run: 節 `structure-eye` の記録（道具の呼びが 0 回）
  - 狭め: 無し

- P077 構造の目の返答の型は設計の行の型（design-row.schema.json）から route_reason（受け付けが足す）と precedents を除き route を任意にした物で、持ち主の型とずれない
  - 元: works/blk-structure/blk-structure.yaml:123-151・works/blk-structure/design-row.schema.json
  - 今: workflows/plan/works-factory-plan.yaml:121-150・lib/design-row.schema.json
  - 証: tests/workflows/test_plan.py::ShapeCase.test_role_schemas_match_their_lib_owners（assert: tests/workflows/test_plan.py:399-402）
  - 本物の run: 節 `structure-eye` の出力が型を通った記録
  - 狭め: 無し

- P078 受け付けは返答を機械で照らす: 実測した単位と 1 対 1・同じ単位の 2 行・行の形に無い欄・verdict の語・faces が 1〜6 の整数（真偽は不可）・根拠が見せた JSON の中の在る（null でない）欄を指す RFC 6901 の Pointer（前に 0 の添字は不可）・reason が空でない
  - 元: works/blk-structure/lib/eye.py:213 `problems`・:193 `_pointer`
  - 今: lib/eye.py:213 `problems`・:193 `_pointer`
  - 証: lib/tests/test_structure_eye.py::EyeAcceptCase.test_bad_rows_are_named（assert: lib/tests/test_structure_eye.py:52-53）・test_good_rows_pass・test_evidence_indexes_the_units_the_prompt_showed（assert: :104-105）
  - 本物の run: `plan/structure/<鍵>/eye.json` の `status`=ok・`reason`=""
  - 狭め: 無し

- P079 汚れると見た行は当たった形の番号と、推しの避け方 chosen と chosen_reason が要る
  - 元: works/blk-structure/lib/eye.py:245-246・:254-255
  - 今: lib/eye.py 同じ行
  - 証: lib/tests/test_structure_eye.py::EyeAcceptCase.test_bad_rows_are_named（subTest「汚れるで避け方が無い」「汚れるで形が無い」。assert: lib/tests/test_structure_eye.py:53）
  - 本物の run: `plan/structure/<鍵>/design.jsonl` の汚れる行の `chosen`（種で汚れる行が出た時だけ）
  - 狭め: 無し

- P080 行き先「人に上げる」は汚れる行だけで、決まらない訳 undecided_because（20 字以上）と捨てた案と代償 rejected（1 つ以上）が要る。自分で決める行に undecided_because を書けば拒む
  - 元: works/blk-structure/lib/eye.py:256-270
  - 今: lib/eye.py 同じ行
  - 証: lib/tests/test_structure_eye.py::EyeAcceptCase.test_route_up_needs_reason（assert: lib/tests/test_structure_eye.py:61-65）。自分で決める行の undecided_because を拒む所は 要追加: 同クラス.test_own_decision_row_must_not_carry_undecided — route 無しの汚れる行に undecided_because を書くと problems が「人に上げる行だけに書く」を返す
  - 本物の run: 筋書きでのみ（種の直しは決め手で決まる）
  - 狭め: 無し

- P081 受け付けを通った行は route（既定「自分で決める」）と route_reason（上げた行は決まらない訳、ほかは既定の訳）を足して design.jsonl に書き、設計の行の型を通る
  - 元: works/blk-structure/lib/eye.py:288-292 `accept`
  - 今: lib/eye.py 同じ行
  - 証: lib/tests/test_structure_eye.py::EyeAcceptCase.test_route_up_row_written（assert: lib/tests/test_structure_eye.py:78-83）・tests/workflows/test_plan.py::CollectCase.test_route_up_row_keeps_ready（assert: tests/workflows/test_plan.py:761-763）。自分で決める行の既定の訳は 要追加: lib/tests/test_structure_eye.py::EyeAcceptCase.test_own_decision_row_gets_default_route — route を書かない行が `("自分で決める", eye.ROUTE_REASON)` で書かれること（元 works/tests/test_blk_structure.py:782 が route を見ていた）
  - 本物の run: `plan/structure/<鍵>/design.jsonl` の各行の `route`・`route_reason`
  - 狭め: 無し

- P082 拒んだ時は design.jsonl に行を書かず、理由を控え eye.json に置いて同じ会話（fresh_context: false）で出し直させ、3 回目の拒否で give_up して輪を抜ける（max_iterations で落とさない）
  - 元: works/blk-structure/lib/eye.py:280-287・works/blk-structure/blk-structure.yaml:88-91
  - 今: lib/eye.py 同じ行・workflows/plan/works-factory-plan.yaml:89-93
  - 証: lib/tests/test_structure_eye.py::EyeAcceptCase.test_third_rejection_gives_up（assert: lib/tests/test_structure_eye.py:127-130）・tests/workflows/test_plan.py::ShapeCase.test_loops_give_up_in_the_body_before_max_iterations（assert: tests/workflows/test_plan.py:362-365）
  - 本物の run: `plan/structure/<鍵>/eye.json` の `attempt`・`status`
  - 狭め: 無し

- P083 構造の目の控え structure-state.json（status・reason・design_file・wall_s）を、目が飛んだ・落ちた・3 回拒まれた周も必ず書く。失敗の訳は「実測が落ちた: …」「構造の目の返答が N 回とも受け付けで拒まれた: …」「構造の目の会話が落ちたか走らなかった」の 3 通り。目を起こさない周（eye.due が偽）は ok
  - 元: works/blk-structure/scripts/collect.py `outcome`・works/darkfactory/lib/line_edge.py `structure_edge`
  - 今: lib/planfile.py:719 `_outcome`・:732 `write_state`・workflows/plan/works-factory-plan.yaml:175-190（trigger_rule: all_done）
  - 証: tests/workflows/test_plan.py::CollectCase.test_eye_without_rows_leaves_failed_state（assert: tests/workflows/test_plan.py:769-770。status failed だけ）。弱い: 訳の 3 通りと ok の 2 通りを元 works/tests/test_structure_eye.py:192 CollectCase.test_each_failure_keeps_ok_and_names_the_reason は全部縛った → 要追加: lib/tests/test_planfile.py::StateCase.test_each_failure_names_the_reason — `_outcome` の 5 通り（ok・目を起こさない ok・会話が落ちた・3 回拒まれた・実測が落ちた）の status と reason の字
  - 本物の run: `plan/structure/<鍵>/structure-state.json` の `status`=ok・`reason`=""（返り `structure` の指し札の先）
  - 狭め: 無し

- P084 構造のブロックで増えた時間（実測の秒＋目の秒）を structure-state.json の wall_s に足して残す（報告が「構造のブロックで増えた時間」として読む）
  - 元: works/blk-structure/scripts/collect.py（wall の和）
  - 今: lib/planfile.py:752-753
  - 証: 要追加: lib/tests/test_planfile.py::StateCase.test_wall_adds_the_eye_time — structure.json の timing.wall_s 0.5 と eye.json の wall_s 2.25 で控えの wall_s が 2.75（元 works/tests/test_structure_eye.py:206）
  - 本物の run: `plan/structure/<鍵>/structure-state.json` の `wall_s`（0 より大きい）
  - 狭め: 無し

- P085 構造の境の中の失敗（実測が落ちた・目が落ちた・3 回拒まれた）は節の失敗にせず、構造の目の行なしで計画に進む。修正案の材料には「構造の目の行なしで計画した（理由: …）」を貼る
  - 元: works/darkfactory/darkfactory.yaml:452-466 `h-structure`・works/.shared/core/structmark.py `note`・`plan_section`
  - 今: workflows/plan/works-factory-plan.yaml:175-181（structure-state は all_done）・:210-212（plan-loop は none_failed_min_one_success）・lib/structmark.py `plan_section`
  - 証: tests/workflows/test_plan.py::CollectCase.test_eye_without_rows_leaves_failed_state（assert: tests/workflows/test_plan.py:771 の ready true）。材料の「行なしで計画した」の文は 要追加: tests/workflows/test_plan.py::CollectCase.test_failed_structure_note_reaches_the_brief — 目が 3 回拒まれた周の brief-1.md に structmark.MISSING と訳が在ること（元 works/tests/test_structure_eye.py:287 test_block_reason_reaches_the_mark）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P086 構造の控えを書けない（structure-state.json を書けない）周は、元は節の失敗にせず「控えを書けない」の訳で failed として計画に進んだ。今は structure-state の節が落ち、plan-loop が飛んで ready: false になる
  - 元: works/darkfactory/lib/line_edge.py `structure_edge`（OSError を訳にする）・works/tests/test_structure_eye.py:267 `test_unwritable_state_is_not_a_node_failure`
  - 今: workflows/plan/scripts/structure_state.py（try が無い）・lib/planfile.py:732 `write_state`
  - 証: 要追加: tests/workflows/test_plan.py::CollectCase.test_unwritable_state_still_plans — 鍵の置き場の structure-state.json をフォルダにして書けなくしても、役を起こし ready が true で、structure の指し札の先が訳つきで在ること
  - 本物の run: 筋書きでのみ
  - 狭め: #75 で狭めた（Archon で不可でない: script の中で OSError を捕まえて訳を返せば済む → 戻す）

- P087 構造の境の節そのものが落ちた周は、計画の落ちと同じく計画なしで修正へ進まない
  - 元: works/darkfactory/darkfactory.yaml:478-486（planning は h-structure に依る）・works/tests/test_structure_eye.py:255 `test_edge_failure_stops_like_plan_failure`
  - 今: workflows/plan/works-factory-plan.yaml:210-212（structure-state が落ちれば plan-loop は none_failed_min_one_success で飛ぶ）・返す節 plan は ready: false
  - 証: 要追加: tests/workflows/test_plan.py::CollectCase.test_failed_state_node_gives_not_ready — structure-state の状態を failed にした時 plan-loop が飛び返りが ready: false（線がそれで修正へ進まないのは線の試験の持ち物）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P088 修正案の材料に構造の目の行（判定・形・根拠・避け方）と「汚れる行の単位を持つ項目は欄 structure に従うか訳を書け」の頼みを貼る
  - 元: works/.shared/core/structmark.py `plan_section`・`PLAN_ASK`
  - 今: lib/structmark.py `plan_section`・lib/planfile.py:852 `structmark.plan_section(structure_dir_)`
  - 証: tests/workflows/test_plan.py::AcceptCase.test_dirty_structure_row_needs_answer（受け付けの側）。材料に貼られることは 要追加: tests/workflows/test_plan.py::BriefCase.test_brief_carries_structure_rows — 汚れる行の周の brief-1.md に structmark.PLAN_HEAD と PLAN_ASK と行の「避け方:」が在ること
  - 本物の run: `plan/r1/brief-1.md` の「## 構造の目の行」の節（種で行が在れば）
  - 狭め: 無し

- P089 返りの structure の指し札は structure-state.json を指し、隣の design.jsonl を名で開ける（後段＝事前審査・関所・報告が 1 つの控えだけを読む）
  - 元: works/blk-structure/blk-structure.yaml:174-200（出力 3 本だけを宣言）・works/.shared/core/structmark.py 冒頭
  - 今: workflows/plan/scripts/plan_collect.py `collected`・lib/planfile.py:1056 `placeholders`
  - 証: tests/workflows/test_plan.py::CollectCase.test_route_up_row_keeps_ready（assert: tests/workflows/test_plan.py:761 の隣の design.jsonl を開く）・ShapeCase.test_fallback_names_match_lib（assert: tests/workflows/test_plan.py:424-427）
  - 本物の run: 返す節 `plan` の出力 `structure.path`=`plan/structure/<鍵>/structure-state.json`
  - 狭め: 無し

- P090 実測（measure.py）の行数と伸び: 窓の始まりの commit の行数を改名をたどった名で数え、差を出す。窓は HEAD の日時から 90 日
  - 元: works/blk-structure/scripts/measure.py `growth`・`window_since`・`name_at`
  - 今: lib/measure.py（字のまま）
  - 証: lib/tests/test_blk_structure.py::MeasureCase.test_growth_counts_base_under_old_name・test_window_days_counts_back_from_head（元と同じ assert）
  - 本物の run: `plan/structure/<鍵>/structure.json` の `units[].measure.paths[].growth`
  - 狭め: 無し

- P091 実測の変更の頻度: パスごとに --follow・素・--no-merges の 3 つの数、複数のパスの和集合は 1 本ずつの和、素と --no-merges の差がマージの数
  - 元: works/blk-structure/scripts/measure.py `commits`
  - 今: lib/measure.py
  - 証: lib/tests/test_blk_structure.py::MeasureCase.test_follow_raw_no_merges_per_path・test_union_follow_is_sum_of_single_file_sets・test_raw_minus_no_merges_is_merge_count
  - 本物の run: `plan/structure/<鍵>/structure.json` の `units[].measure` の frequency・union
  - 狭め: 無し

- P092 浅い clone では頻度・伸び・和集合の数を出さず「測れない」と書く
  - 元: works/blk-structure/scripts/measure.py `is_shallow`・`growth`
  - 今: lib/measure.py
  - 証: lib/tests/test_blk_structure.py::MeasureCase.test_shallow_clone_is_unmeasurable
  - 本物の run: 筋書きでのみ（種は浅くない）
  - 狭め: 無し

- P093 写しの在りか: 空行を落とし空白を詰めた 6 行の塊のハッシュを追跡ファイル全体で引く（5 行の一致は拾わない）
  - 元: works/blk-structure/scripts/measure.py（duplicates）
  - 今: lib/measure.py
  - 証: lib/tests/test_blk_structure.py::MeasureCase.test_six_line_copy_found_five_line_not
  - 本物の run: `plan/structure/<鍵>/structure.json` の `units[].measure.paths[].duplicates`
  - 狭め: 無し

- P094 入口の数（ファイル名を名指す追跡ファイルの数と、うち実行できる物）と、環境変数の名・一番多い接頭辞（同数は辞書順）・3 つの数え方・書き込みの数
  - 元: works/blk-structure/scripts/measure.py（entrypoints・env）
  - 今: lib/measure.py
  - 証: lib/tests/test_blk_structure.py::MeasureCase.test_entrypoints・test_env_prefix_tie_is_broken_by_name_order・test_env_prefix_without_tie・test_env_three_counts_and_writes
  - 本物の run: `plan/structure/<鍵>/structure.json` の `units[].measure` の entrypoints・env
  - 狭め: 無し

- P095 読めない・大きすぎる・追跡されていないパスは skipped に理由つきで並べて続け、閾値で止めない。同じ入力なら同じ出力
  - 元: works/blk-structure/scripts/measure.py（skipped）
  - 今: lib/measure.py
  - 証: lib/tests/test_blk_structure.py::MeasureCase.test_skipped_with_reasons_and_continue・test_same_output_twice
  - 本物の run: `plan/structure/<鍵>/structure.json` の `units[].measure.skipped`
  - 狭め: 無し

- P096 差分の形（--diff。案の patch か名の一覧を一時の像に当てて前後の増減と新しい名の場所を出し、対象のリポジトリを動かさない）。直しの前の段では使わず、直しの後の実測（eyes の持ち物）と同じ lib を共有する
  - 元: works/blk-structure/scripts/measure.py（--diff）
  - 今: lib/measure.py
  - 証: lib/tests/test_blk_structure.py::MeasureCase.test_patch_before_after_delta ほか 8 件（同名で在る）
  - 本物の run: 筋書きでのみ（計画のブロックでは使わない。eyes の段 B で見える）
  - 狭め: 無し

- P097 考えの住処の地図の節（concepthome.section）: 追跡された地図を根と入れ子から上限つきで拾い、無ければ無いと言い、木が読めなければ名指す。修正案の材料と事前審査の材料に貼る
  - 元: works/.shared/core/concepthome.py `section`・`pick_maps`
  - 今: lib/concepthome.py（字のまま。包みの system prompt でなく材料の末尾に貼る、と文だけ直した）
  - 証: lib/tests/test_concepthome.py::SectionCase.test_section_without_map・test_section_lists_maps_and_rest・test_section_names_unreadable_tree・PickCase の 3 件
  - 本物の run: `plan/r1/brief-1.md` の「考えの住処の地図」の節（種は地図なしの文）
  - 狭め: 無し

- P098 判断の 1 軸と目・審査・修正案の問いの文（PLAN_RULE・REVIEW_ASK・R1_HEAD・R3_HEAD・EYE_ASK）は 1 か所が持ち、全部が軸の文で始まり印と差し込み口を持つ
  - 元: works/.shared/core/concepthome.py
  - 今: lib/concepthome.py
  - 証: lib/tests/test_concepthome.py::TextCase.test_texts_carry_prefix_and_slot・test_axis_heads_every_text
  - 本物の run: `plan/structure/<鍵>/eye-prompt-1.md` の問い（EYE_ASK の字）
  - 狭め: 無し

- P099 柵（conceptfence）: 考えの語の形が知ってよい所と除く所の外に何行あるかを数え、写しの束ねの行は数えず、壊れた束ねは拒み、増える向きだけ赤（ratchet）。単位のパスの知る場所の数（places）と、版の間の増え（scan_change。実行基盤の写しの置き場と入れ子のリポジトリは除く）
  - 元: works/.shared/core/conceptfence.py
  - 今: lib/conceptfence.py（`changed`・`scan_change` が skip_prefix を受ける形に変わった）
  - 証: lib/tests/test_concept_fences.py::Synthetic の 12 件・lib/tests/test_concept_change.py::ChangeCase の 5 件（同名で在る）
  - 本物の run: `plan/structure/<鍵>/structure.json` の `units[].concepts.places`（種は表が無いので空）
  - 狭め: 無し

- P100 工場自身のリポジトリの考えの地図と柵の表（地図と表の id・状態の揃い・住処ありの考えは柵を持つ・地図のパスが在る・柵が保たれる・main の表より増えない）を CI で照らす
  - 元: works/tests/test_concept_fences.py::MapAndTable の 6 件・FencesHold.test_every_fence・NotAboveMain の 2 件（works/docs/concepts.md・concepts.json）
  - 今: 無し（main に docs/concepts.md・concepts.json も、それを照らす試験も無い）
  - 証: 要追加: tests/layers/test_concept_fences.py::MapAndTable.test_ids_and_status_agree ほか元の 9 件 — main の地図と表を作った上で同じことを縛る
  - 本物の run: 筋書きでのみ（CI の関門）
  - 狭め: lib-port で外した（#75・#73 ではない）。Archon で不可でない → 戻すか、計画のブロックの外の関門として持ち主に置き場を聞く（持ち主の決め「同じ機械の関門（考えの住処の柵と数の歯止め）を CI で通す」に当たる）

- P101 構造の実測の単位の目録（id・paths・summary）は判定の単位から作り、paths は根の中に在るファイルだけ（ディレクトリ・glob・pathspec・絶対・根の外・無いファイルは捨てる）、無ければ key の頭のパス
  - 元: works/darkfactory/lib/line_edge.py `_unit_file_paths`・`structure_units`
  - 今: lib/judge_accept.py:1102 `_unit_file_paths`（judge の持ち物）
  - 証: lib/tests/test_judge_accept.py::StructureUnitsCase.test_drops_paths_that_are_not_files_under_root ほか 3 件（judge の区分。ここは参照だけ）
  - 本物の run: judge の出力 `units`（plan の入力）の `paths`=`["stats.py"]`
  - 狭め: 無し

## 計画と事前審査の往復（壁打ち）と案の直し（形 replan）

略記: 元 = works/（2aa7c66c）。今 = main（無印）か #74 の head（線）。WF = main。P74 = #74 の head。
本物の run の置き場: `<artifacts>/plan/r<k>/`（計画のブロックの周）、`<artifacts>/plan-review/`（事前審査のブロックの置き場。往復の控えは `plan-review/plan-converge.json`、差し込みごとは `plan-review/pass-<k>/`）。
種の run（stats.py の 2 つの欠陥・標準・最後の関所は開く）は、判定どおり 1 往復で事前審査が通るのが普通で、修正役が案の項目の誤りを申し出る（裁定 fix_plan_item）ことも普通は無い。このため往復の 2 周目と案の直しの行は、ほぼ「筋書きでのみ」。

### A. 計画と事前審査の往復（壁打ち）

- P102 往復の決め: 最後の往復に block（直しへ進めない穴）が無ければ clean、前のどれかの往復と同じ block が残れば persisted、柵（3 往復）に着けば unsettled、ほかは again。数の定数をモジュールに持たない
  - 元: works/.shared/core/converge.py:148 `decide`・:161 `_decide_items`
  - 今: lib/converge.py:148 `decide`（字のままの写し）。計画の側の写し lib/planfile.py:469 `_record_pass` も同じ decide を呼ぶ
  - 証: lib/tests/test_converge.py::DecideCase.test_no_block_is_clean（assert: lib/tests/test_converge.py:56）・test_block_from_any_earlier_pass_persists（:62）・test_fence_with_new_blocks_is_unsettled（:67）・test_module_has_no_count_constant（:71）
  - 本物の run: plan-review/plan-converge.json の `outcome`（種の run では `clean`）
  - 狭め: 無し

- P103 項目ごとの壁打ち: block の無い項目は閉じ（次の往復で審査も直しもしない）、前の往復と同じ block の項目は保留、閉じた項目でも block に名指されれば開き直す。どの項目にも重ならない穴は審査した全部の項目の物と数える
  - 元: works/.shared/core/converge.py:190 `_item_states`・:184 `_attributed`
  - 今: lib/converge.py:190（写し）。計画の側は lib/planfile.py:469 `_record_pass` が converge._item_states を呼ぶ
  - 証: lib/tests/test_converge.py::ItemsCase.test_persisted_item_is_held_and_others_go_on・test_synergy_block_reopens_named_closed_item（assert: :312-313）・test_face_naming_no_item_counts_for_every_reviewed_item（:319）。計画の側の写しは lib/tests/test_planfile.py::ConvergeCase.test_same_block_twice_holds_item（assert: lib/tests/test_planfile.py:319）
  - 本物の run: plan-review/plan-converge.json の `passes[-1].items[].state`
  - 狭め: 無し

- P104 往復の控えに往復ごとの行（blocks・faces・suggests・answers・resolved・persists・outcome）を積み、指示書と事前審査の返答を pass-<k>/ に写し、trace に `plan_converge` の行を書く
  - 元: works/.shared/core/converge.py:373 `record_pass`。写す物は元 works/blk-plan/lib/planblk.py:1178 `with_converge` が p2.fix_plan.json・p2.plan_review.json・plan-fields.json・指示書の 4 つを渡した
  - 今: lib/boardview.py:827 `_take` が converge.record_pass を呼ぶ。写すのは指示書（prompt.md）と木の下請けのファイルだけ（案・欄は計画のブロックの plan/r<k>/ に、審査は plan-review/pass-<k>/review.json に別に残る）
  - 証: lib/tests/test_converge.py::RecordCase.test_record_pass_keeps_every_pass_and_copies_files（assert: :95-110）・tests/workflows/test_plan_review.py::ConvergeCase.test_first_block_is_not_stalled（assert: tests/workflows/test_plan_review.py:872）
  - 本物の run: plan-review/plan-converge.json の `passes[0]`、plan-review/plan-converge/pass-1/prompt.md
  - 狭め: 写しの 4 つが 1 つに減ったが、中身は周のフォルダに在る（能力は落ちていない）。往復の行の `files` から案と審査のファイルを引けなくなっただけ

- P105 again の往復の後、計画の役に返す材料: REVISE_ASK・返した block の穴ごとの節・suggest の穴（NOTES_HEAD、答えなくてよい）・閉じた項目（CLOSED_ASK、書くな）・保留の項目（HELD_NOTE）
  - 元: works/.shared/core/converge.py:538 `revise_section`、元 works/blk-plan/lib/planblk.py:1281 `_revise_prep`
  - 今: lib/planfile.py:574 `revise_section`（盤面の代わりに控えを受ける写し）を lib/planfile.py:878 `_prior_section` が 2 周目の材料に貼る
  - 証: lib/tests/test_planfile.py::ConvergeCase.test_revise_section_names_blocks_and_closed_items（assert: lib/tests/test_planfile.py:371-374）・tests/workflows/test_plan.py::CollectCase.test_rounds_count_and_second_round_gets_review（assert: tests/workflows/test_plan.py:743-744）。suggest の節 NOTES_HEAD と保留の HELD_NOTE は planfile の写しでは照らされていない（lib/converge.py の本体の試験だけ）→ 要追加: lib/tests/test_planfile.py::ConvergeCase.test_revise_section_carries_suggest_notes_and_held_items — suggest の穴の本文と HELD_NOTE の項目が planfile.revise_section に載る
  - 本物の run: plan/r2/brief-1.md の「## 前の周の案と事前審査の指摘」節（2 周目が在る run だけ）。種の run では筋書きでのみ
  - 狭め: 無し

- P106 again の後の 2 周目の計画の材料に、前の周の案のファイル・受けた事前審査の写し・前の周の項目ごとの波及の一覧を貼る
  - 元: works/blk-plan/lib/planblk.py:1281 `_revise_prep`（ripple.section(前の往復の一覧)）
  - 今: lib/planfile.py:878 `_prior_section`、lib/planfile.py:623 `open_round` が受けた review を plan/r<k>/review/p2.plan_review.json に写す
  - 証: tests/workflows/test_plan.py::CollectCase.test_rounds_count_and_second_round_gets_review（assert: tests/workflows/test_plan.py:743・747）・test_first_round_reads_empty_and_null_review_alike（assert: :726）
  - 本物の run: plan/r2/review/p2.plan_review.json の在る無し・plan/r2/brief-1.md。種の run では筋書きでのみ
  - 狭め: 無し

- P107 2 周目の材料の単位の no の行で、閉じた・保留の項目の単位を「機械が差し込む（書かなくてよい）」に分け、差し込む no の並びを名指す
  - 元: works/blk-plan/lib/planblk.py:328 `plan_slots_section(filled=converge.filled_units(b))`
  - 今: lib/planfile.py:783 `units_section(filled=…)`・:776 `filled_units`
  - 証: lib/tests/test_planfile.py::UnitsSectionCase.test_filled_units_are_not_owed_in_the_brief（assert: lib/tests/test_planfile.py:390-393）・tests/workflows/test_plan.py::CollectCase.test_rounds_count_and_second_round_gets_review（assert: tests/workflows/test_plan.py:745-746）
  - 本物の run: plan/r2/brief-1.md の「機械が差し込む no」行。筋書きでのみ
  - 狭め: 無し

- P108 2 周目の計画の返答は、前の往復の block の全部に 1 行ずつ答える（block_answers: handled は fixed か disputed、how は 10 字以上、前の往復に無い key は拒む）。欠ければ ANSWERS_REJECT で拒む
  - 元: works/.shared/core/converge.py:437 `answer_gaps`、works/blk-plan/lib/planblk.py:1301 `revise_take`
  - 今: lib/planfile.py:515 `answer_gaps`（写し）、lib/planfile.py:915 `take_plan`
  - 証: lib/tests/test_planfile.py::ConvergeCase.test_answer_gaps_need_one_answer_per_open_block（assert: lib/tests/test_planfile.py:335-339）・test_no_answers_asked_on_first_round（:342-345）・tests/workflows/test_plan.py::CollectCase.test_rounds_count_and_second_round_gets_review（assert: tests/workflows/test_plan.py:748）
  - 本物の run: plan/r2/rejects の控え（rolekit の拒否の控え）。筋書きでのみ
  - 狭め: 無し

- P109 計画の返答に前の往復の閉じた・保留の項目を差し込んで案の全体を組む。閉じた項目を変えた・閉じた項目の単位を別の行に入れた・開いた項目の行が無い返答は CLOSED_REJECT で拒む。閉じた項目を前のまま書いた行は捨てて trace に `plan_converge_dropped` を残す
  - 元: works/.shared/core/converge.py:333 `splice`、works/blk-plan/lib/planblk.py:1301 `revise_take`
  - 今: lib/planfile.py:539 `splice`（写し）、lib/planfile.py:915 `take_plan`（DROPPED_OP は converge.DROPPED_OP を直に使う）
  - 証: lib/tests/test_planfile.py::ConvergeCase.test_splice_fills_closed_item_and_refuses_changed_one（assert: lib/tests/test_planfile.py:351-357）・test_splice_refuses_missing_open_item（:361-362）・tests/workflows/test_plan.py::CollectCase.test_rounds_count_and_second_round_gets_review（assert: tests/workflows/test_plan.py:750・752-753）。ブロックの水準で CLOSED_REJECT が拒みの本文に載ることは照らされていない → 要追加: tests/workflows/test_plan.py::CollectCase.test_second_round_changing_a_closed_item_is_rejected — 2 周目に閉じた項目の行を変えて返すと拒否の本文が planblk.CLOSED_REJECT で始まる
  - 本物の run: plan/r2/trace.jsonl の `plan_converge_dropped` 行・plan/r2/p2.fix_plan.json の `plan`。筋書きでのみ
  - 狭め: 無し

- P110 2 周目の計画の受け付けは block_answers を案から外して p2.fix_plan.json と reply.json の脇に残し、事前審査がそれを次の往復の answers として読む
  - 元: works/blk-plan/lib/planblk.py:1301 `revise_take`（converge.note_answers）・:1178 `with_converge`
  - 今: lib/planfile.py:915 `take_plan`（`extra = {block_answers}`）→ lib/boardview.py:392 `open_pass`（`converge.split("plan-revise", fix_plan)` → `converge.note_answers`）
  - 証: 計画の側 tests/workflows/test_plan.py::CollectCase.test_rounds_count_and_second_round_gets_review（assert: tests/workflows/test_plan.py:751）。審査の側 tests/workflows/test_plan_review.py::ConvergeCase.test_rereview_must_account_for_every_previous_block（assert: tests/workflows/test_plan_review.py:899）は試験が p2.fix_plan.json を手で置く。ブロックをまたぐ照らしが無い → 要追加: tests/e2e または tests/workflows/test_plan_review.py::ConvergeCase.test_answers_written_by_the_plan_block_reach_the_record — 計画のブロックが書いた plan/r2/ を指し札で渡すと、往復の控えの passes[1].answers に同じ行が入る
  - 本物の run: plan/r2/p2.fix_plan.json の `block_answers` と plan-review/plan-converge.json の `passes[1].answers`。筋書きでのみ
  - 狭め: 無し

- P111 again の後の再審は、前の往復の block の全部に行き先（resolved）を書く。欠ければ RESOLVED_REJECT で拒み、往復を積まない
  - 元: works/.shared/core/converge.py:462 `resolved_gaps`、works/blk-plan/lib/planblk.py:1178 `with_converge`
  - 今: lib/boardview.py:827 `_take`（converge.resolved_gaps）
  - 証: tests/workflows/test_plan_review.py::ConvergeCase.test_rereview_must_account_for_every_previous_block（assert: tests/workflows/test_plan_review.py:890・898）・lib/tests/test_converge.py::FieldsCase.test_resolved_gaps_need_every_previous_block_accounted
  - 本物の run: plan-review/pass-2/ の拒否の控え。筋書きでのみ
  - 狭め: 無し

- P112 再審の材料に REREVIEW_ASK と、前の往復ごとの block の穴と計画の役の答えを貼る。1 往復目は貼らない
  - 元: works/.shared/core/converge.py:555 `review_section`
  - 今: lib/boardview.py:750 `review_material`（converge.review_section）
  - 証: tests/workflows/test_plan_review.py::ConvergeCase.test_rereview_material_carries_previous_blocks_and_answers（assert: tests/workflows/test_plan_review.py:906-908）・test_first_material_has_no_rereview（:914）
  - 本物の run: plan-review/pass-2/prompt.md。種の run では pass-1/prompt.md に REREVIEW_ASK が無いことだけ見える
  - 狭め: 無し

- P113 again（1 往復目の block）では止めず関所も決めず、計画に返す。同じ block が 2 度続いた（persisted）・柵でも消えない（unsettled）時は止めて、修正前の関所に止まりの行（STUCK_ITEM と理由）と block の穴を載せる
  - 元: works/blk-plan/lib/planblk.py:1178 `with_converge`（again は rewind_roles）・:1341 `converge_check`、works/.shared/core/converge.py:571 `stuck_reason`
  - 今: lib/boardview.py:919 `collect`（stalled = outcome in STUCK）、P74 workflows/line/scripts/plan_out.py `plan_out`（done = ready 偽・pass・stalled・round ≥ 3）、P74 workflows/line/works-factory-line.yaml:182-237 の loop_group `plan-rounds`
  - 証: tests/workflows/test_plan_review.py::ConvergeCase.test_first_block_is_not_stalled（assert: :855-857）・test_same_block_again_stalls_with_a_design_item（:879-880）・test_other_block_on_the_fence_is_unsettled（:926）。線の側 P74 tests/workflows/test_line.py::PlanOutCase.test_done_rules（assert: P74 tests/workflows/test_line.py:413-416）・test_round_limit_is_the_loop_limit（:751）・筋書き P74 workflows/line/fixtures/plan-stalled.stubs.yaml・plan-unsettled.stubs.yaml
  - 本物の run: `$plan-rounds.output.stalled`・plan-review の返り `stalled`（種の run では false）
  - 狭め: 無し

- P114 往復の柵（3）を、事前審査の往復の数と線の loop_group の上限の両方で同じ数に縛る。上限に当たって落ちずに抜ける
  - 元: works/blk-plan/blk-plan.yaml:543（converge-loop の max_iterations 3）と works/tests/test_blk_plan.py::YamlCase.test_converge_loop_wraps_revise_and_review（GIVE_UP_AFTER と突き合わせ）
  - 今: lib/boardview.py:81 `FENCE = rolekit.GIVE_UP_AFTER`、P74 workflows/line/scripts/plan_out.py `ROUND_LIMIT = 3`、P74 works-factory-line.yaml:186 `max_iterations: 3`
  - 証: P74 tests/workflows/test_line.py::PlanOutCase.test_round_limit_is_the_loop_limit（assert: :751）。FENCE と ROUND_LIMIT の一致は照らされていない → 要追加: P74 tests/workflows/test_line.py::PlanOutCase.test_round_limit_is_the_review_fence — plan_out.ROUND_LIMIT == boardview.FENCE == rolekit.GIVE_UP_AFTER
  - 本物の run: plan/r*/ の数が 3 を越えない。筋書きでのみ
  - 狭め: 無し

- P115 往復の数え: 計画の周 r<k> は往復と案の直しを通して数え、事前審査の往復の控えは差し込みをまたいで 1 つの周（見え方の周はいつも 1）に積む。案の直しの周は往復に数えない
  - 元: works/.shared/core/converge.py:214 `read`（盤面の周ごと）・:236 `pass_no`
  - 今: lib/planfile.py:593 `next_round`・:491 `converge_record`（mode replan を飛ばす）、lib/boardview.py:248 `place`（round 1 固定）
  - 証: lib/tests/test_planfile.py::RoundCase.test_next_round_counts_round_folders・ConvergeCase.test_replan_rounds_are_not_passes（assert: lib/tests/test_planfile.py:326）・lib/tests/test_boardview.py::OpenCase.test_round_is_always_one_and_k_is_the_plan_round
  - 本物の run: plan/r1/round.json の `round`、plan-review/plan-converge.json の `round`=1
  - 狭め: 無し

- P116 往復の控えを、計画の側と事前審査の側の 2 か所で独立に組む（計画の側は周ごとの reply.json と受けた review から組み直す）。2 つが食い違わないこと
  - 元: 1 か所（盤面の plan-converge.json を両方の役が読む）
  - 今: lib/planfile.py:491 `converge_record`（計画の側の組み直し）と plan-review/plan-converge.json（lib/boardview.py の converge.record_pass）。#75 の discoveries R10（converge の往復の本体の写し・約 120 行）
  - 証: 2 か所の一致を照らす試験は無い → 要追加: tests/e2e（または tests/workflows/test_plan.py）::ConvergeAgreementCase.test_plan_side_record_matches_plan_review_record — 同じ 2 往復を両ブロックに通し、items の state・outcome が一致する
  - 本物の run: plan/r2 の材料の閉じた項目と plan-review/plan-converge.json の `passes[-1].items`。筋書きでのみ
  - 狭め: 能力は残るが写しの二重。#75 が「前提の lib を直せない」範囲の訳で残した（不可でない → 掃除で lib/converge.py を「控えを受ける本体」に分ければ消える）

- P117 2 周目の計画の役は、1 周目の計画の役の会話の続きで起きた（出し直しも同じ会話に積む）
  - 元: works/blk-plan/blk-plan.yaml:565-574（plan-revise-loop・fresh_context: false・印 continue=plan）、works/blk-plan/lib/planblk.py:100 `REVISE_ROLE`
  - 今: 無し。2 周目は新しい会話で、前の周の案と指摘をファイルで渡す（WF workflows/plan/works-factory-plan.yaml:217 plan-loop `fresh_context: true`）
  - 証: 要追加（持ち主の決めの後）。今の形を縛る試験は tests/workflows/test_plan.py::CollectCase.test_rounds_count_and_second_round_gets_review（材料のファイルで渡す）
  - 本物の run: 筋書きでのみ
  - 狭め: #75 で狭めた（Archon で不可）。名指しの会話の継ぎ（`context: {resume: <節>}`）は loop_group の中で禁じられ（Archon packages/workflows/src/loader.ts:1173-1174「context.resume inside a loop_group body, which is not supported」）、計画の役は線の loop_group `plan-rounds` の中・さらにブロックの plan-loop の中に在る。loop_group の fresh_context: false が継ぐのは「直前の周の最後の順の会話」（dag-executor.ts:4773-4778）で、plan-rounds では事前審査の会話になり計画の役の会話ではない。入れ子の loop の 1 周目はいつも新しい会話（dag-executor.ts:5665 `needsFreshSession = loop.fresh_context || i === 1`）。よって不可。持ち主の決め `persona`（保存した返答で渡すか）の答え待ちのまま 決め: 継がない。保存した返答を読む新しい会話で回す（docs/owner-decisions.md の「導いた事」の 2026-10-12 の推しの決め。Archon loader.ts:1173-1175）。狭めとして確定（線の配線の文書の「この文書の外」の「決めた物」）

- P118 again の時、計画の役は独立設計の節を受けない（修正案の役の頭と指示書は会話に在る）
  - 元: works/tests/test_blk_plan.py:1976 `test_revise_prompt_names_blocks_and_keys`（「=====独立設計ここから=====」が無い）
  - 今: lib/planfile.py:824 `write_brief`（形 plan の材料に独立設計の節は元から無い。2 周目は会話が新しいので planmarks.HEAD を含む頭を貼り直す）
  - 証: 要追加: tests/workflows/test_plan.py::CollectCase.test_second_round_brief_has_no_independent_design — 2 周目の brief に独立設計の節の頭（planblk.DESIGN_HEAD）が無い
  - 本物の run: plan/r*/brief-*.md。筋書きでのみ
  - 狭め: 無し（会話が新しいことは P117）

- P119 往復の報告の行（何往復・抜け方の語・続いた block・往復ごとの block と答えの数・項目の閉じた/開いた/保留・相乗りの block）を報告の冒頭に載せる
  - 元: works/.shared/core/converge.py:593 `lines`、works/.shared/core/report.py:949（`lines += converge.lines(b)`）
  - 今: lib/boardview.py:951 が plan-review/pass-<k>/gate.json の `converge` に書くだけで、報告（lib/runreport.py・lib/report.py）も線も読まない
  - 証: lib/tests/test_converge.py::TextCase.test_lines_summarize_passes（lib の水準だけ）。報告に届く試験は無い → 要追加: tests/workflows/test_report.py::ConvergeLinesCase.test_head_carries_plan_converge_lines — plan-review の返りの review の隣の gate.json の converge の行が報告の冒頭の決めの節に載る
  - 本物の run: plan-review/pass-1/gate.json の `converge`（種の run では「事前審査の壁打ち: 1 往復・抜け方は block が消えた…」の 1 行が在るはず）と report の本文（今は載らない）
  - 狭め: #73・#68 のどちらにも狭めの記載無し（不可でない → 戻す。報告が gate-passes.json と同じく review の隣を読めば足りる）

- P120 往復ごとの拒否の数え直し: again で次の往復に移ると、計画と事前審査の拒否の回数を 0 から数え直す（拒否の行は往復の行に残す）
  - 元: works/blk-plan/lib/planblk.py:1178 `with_converge`（converge.stash_rejects・rolekit.take_rejects）、works/tests/test_blk_plan.py:1751 `test_rejects_restart_per_pass`
  - 今: 拒否の控えが周ごと（plan/r<k>/）・差し込みごと（plan-review/pass-<k>/）に分かれるので自然に数え直す。往復の行の `rejects` には積まない（stash_rejects は呼ばれない）
  - 証: tests/workflows/test_plan.py::AcceptCase.test_three_rejections_give_up_with_every_pointer は 1 周の中だけ。周をまたいだ数え直しの試験は無い → 要追加: tests/workflows/test_plan.py::CollectCase.test_second_round_counts_its_own_rejections — 1 周目で 2 回拒まれた後でも 2 周目は 3 回まで出し直せる
  - 本物の run: plan/r<k>/ の拒否の控え。筋書きでのみ
  - 狭め: 往復の行の `rejects` が消えた（報告の材料の細り）。不可でない → 要るなら戻す（軽い）

- P121 往復の控えを書けなかった時に黙って進めない（元は盤面を止めて控えを名指す）
  - 元: works/blk-plan/lib/planblk.py:1178 `with_converge`（rolekit.halt_unsaved）、works/tests/test_blk_plan.py:1718
  - 今: lib/boardview.py:811 `take_review`（accept.guard が例外を拒否にし、3 回で give_up → 返す節が pass: false・stalled: true と訳を questions に載せる）
  - 証: tests/workflows/test_plan_review.py::FailSafeCase（返す節が落ちない）。控えの書き損じを名指す試験は無い → 要追加: tests/workflows/test_plan_review.py::FailSafeCase.test_unwritable_converge_record_is_named — plan-converge.json を書けない時、返りの questions に控えの名が載り pass が偽
  - 本物の run: 筋書きでのみ
  - 狭め: 盤面の止め（b.stop）は無い（#73「盤面の止め（b.stop）は無い」で記載）。能力（黙って進めない）は give_up の道で残る

- P122 盤面の巻き戻し（again で役の節を待ちに戻す・後ろの節が済んでいれば止める）
  - 元: works/blk-plan/lib/planblk.py:1164 `rewind_roles`、works/tests/test_blk_plan.py:1732
  - 今: 無し（盤面が無い。往復は線の loop_group）
  - 証: 当たらない（盤面の機構）
  - 本物の run: 当たらない
  - 狭め: #73 で外した（盤面が無いので当たらない。能力の目的「済んだ後ろの節を黙って戻さない」は、loop_group が往復の後にしか関所へ進まない形で満たす）

### B. 案の直し（形 replan）: 計画の側

- P123 案の直しは、修正役が案の項目そのものの誤りと申し出て裁定役が fix_plan_item と裁いた項目だけを、同じ run の中で 1 度直す（線が ruling に項目の番号を渡す）
  - 元: works/.shared/core/replan.py:291 `material`（待つ行を裁定の plan_items で束ねる）、works/darkfactory/darkfactory.yaml:643 `h-replan`・:687 `replanning`
  - 今: lib/planfile.py:611 `handed`・:623 `open_round`（ruling が空でなければ mode replan）、P74 works-factory-line.yaml:474-487 `replan`（ruling: $fix.output.replan_items・conflicts: $fix.output.conflicts）
  - 証: tests/workflows/test_plan.py::ReplanCase.test_replan_rejects_extra_items_and_changed_keys_then_amends（assert: tests/workflows/test_plan.py:629 の `(2, "replan")`）・筋書き WF workflows/plan/fixtures/replan.stubs.yaml・P74 workflows/line/fixtures/replan.stubs.yaml
  - 本物の run: plan/r2/round.json の `mode`=replan。種の run では筋書きでのみ
  - 狭め: 無し

- P124 渡す項目の番号が承認済みの案の外・番号でない・直す元の承認済みの案が無い時は、役を起こさずに ready: false と訳を返す
  - 元: works/.shared/core/replan.py:291 `material`（BoardGap: 番号でない・案の外・承認済みの案が無い）
  - 今: lib/planfile.py:611 `handed`・:623 `open_round`（go: false・why）
  - 証: tests/workflows/test_plan.py::ReplanCase.test_ruling_outside_the_plan_skips_the_role（assert: :676）・ReplanWithoutPlanCase.test_replan_without_an_accepted_plan_skips_the_role（assert: :685）
  - 本物の run: plan/r<k>/round.json の `go`・`why`、plan/r<k>/ripple.json の `error`。筋書きでのみ
  - 狭め: 無し（盤面の止めの代わりに ready: false）

- P125 案の直しの材料は REPLAN_ASK・項目ごとの節（番号・unit_keys を字のまま・前の項目の JSON）・申し出と裁定の行（単位・between・理由・種類・正しいと見た側・裁定の文を字のまま）だけ。fix_plan_item でない裁定の行・ほかの項目は渡さない
  - 元: works/.shared/core/replan.py:387 `_section`・:410 `prep`
  - 今: lib/planfile.py:431 `replan_section`・:422 `conflict_rows`・:824 `write_brief`（形 replan）
  - 証: tests/workflows/test_plan.py::ReplanCase.test_replan_rejects_extra_items_and_changed_keys_then_amends（assert: :638-640）・lib/tests/test_planfile.py::ReplanInputsCase.test_conflict_rows_are_fix_plan_item_rulings_only（assert: lib/tests/test_planfile.py:405）
  - 本物の run: plan/r2/brief-1.md。筋書きでのみ
  - 狭め: 下の P126

- P126 案の直しの材料に、その項目の brief（修正のブロックが項目ごとに書いた brief-<n>.md）のパスを名指す
  - 元: works/.shared/core/replan.py:291 `material`（棚卸しの決まり_NAME・scopes.each）・:387 `_section`（「この項目の brief」の行）、works/tests/test_replan.py:404 `test_prompt_has_only_the_item_and_texts`
  - 今: 無し（lib/planfile.py:431 `replan_section` に brief の行が無い。事前審査の側 lib/boardview.py:730 も外した）
  - 証: 要追加: tests/workflows/test_plan.py::ReplanCase.test_brief_of_the_item_is_named — 線が渡す修正の段の項目の brief の指し札が材料に名指される
  - 本物の run: 筋書きでのみ
  - 狭め: #73 で事前審査の側を外した（「brief は修正のブロックの置き場に在り、E4 で読まない」）。#75 は計画の側の欠けを書いていない。Archon で不可でない（fix の返りか線の with: で指し札を渡せば足りる）→ 戻す

- P127 返答は渡した項目に限る: 数が違う・unit_keys を一字でも変えた（番号で書いた）・works の欄の誤り・構造と世界の解の行への答えの欠け・狭めない案の欠け・推しの形の崩れを、全部並べて 1 回で拒む（REPLAN_REJECT）
  - 元: works/.shared/core/replan.py:478 `_plan_errors`・:511 `_take`
  - 今: lib/planfile.py:392 `_plan_errors`・:959 `take_replan`
  - 証: lib/tests/test_planfile.py::ReplanErrorsCase.test_reply_limited_to_handed_items・test_all_errors_in_one_rejection（lib/tests/test_planfile.py:213・219）・tests/workflows/test_plan.py::ReplanCase.test_replan_rejects_extra_items_and_changed_keys_then_amends（assert: :635-636）
  - 本物の run: plan/r2/ の拒否の控え。筋書きでのみ
  - 狭め: 元は返答の型の外れ（写しの schema で unit_keys は文字列だけ）も同じ拒否に並べた（`_type_lines`）。今は YAML の output_format が番号も通し、受け付けの unit_keys の字の照らしが代わりに拒む。能力は残る

- P128 受け入れのテストが既に在るかは、修正の起点の版（base_rev）の木で引く（作業ツリーに残った同じ id は拒まない・起点の版に在るテストは拒む・版が引けなければ「分からない」を在る/無いに倒さない）
  - 元: works/.shared/core/replan.py:442 `_start_tree`
  - 今: lib/planfile.py:371 `exists_at`・:959 `take_replan`
  - 証: lib/tests/test_planfile.py::ReplanErrorsCase.test_test_in_start_tree_is_rejected（:226）・test_test_only_in_work_tree_is_not_in_start_tree（:231）・test_unreadable_start_rev_raises（:240）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P129 通った返答は、項目の行を TRIP_FILE（replan.json）に置く（new は決め手の欄を外した形・new_marks は外した欄・contract_changed・widened）。決め手の欄は narrows の行ごとに戻せる
  - 元: works/.shared/core/replan.py:511 `_take`・:356 `new_item`
  - 今: lib/planfile.py:959 `take_replan`、lib/replan.py `new_item`
  - 証: tests/workflows/test_plan.py::ReplanCase.test_replan_rejects_extra_items_and_changed_keys_then_amends（assert: :651-652）・lib/tests/test_planfile.py::ReplanModuleCase.test_new_item_puts_marks_back_on_narrows
  - 本物の run: plan/r2/replan.json の `items[].contract_changed`・`widened`。筋書きでのみ
  - 狭め: 無し

- P130 直した項目を差し替えた案の全体を、その周の p2.fix_plan.json・plan-fields.json（amended に直した項目の核の欄）・reply.json に書き、trace に `plan_amended` を書く。直さない項目の欄は前の周のまま
  - 元: works/.shared/core/planmarks.py:981 `amend`（関所の答えの後）、works/.shared/core/replan.py:699 `answer`
  - 今: lib/planfile.py:959 `take_replan`・:411 `revised_fields`（受け付けで差し替える。採るかは線の関所）
  - 証: tests/workflows/test_plan.py::ReplanCase.test_replan_rejects_extra_items_and_changed_keys_then_amends（assert: :643-648）・lib/tests/test_planfile.py::RevisedFieldsCase.test_replaces_only_revised_items（:454-456）・lib/tests/test_plan_fields.py::TestAmend.test_amend_swaps_one_item_and_refreezes
  - 本物の run: plan/r2/plan-fields.json の `amended`・plan/r2/trace.jsonl の `plan_amended`。筋書きでのみ
  - 狭め: 無し（差し替える時が受け付けに早まったが、2 度目の修正が使うのは関所の後だけ: P74 works-factory-line.yaml:592-607 `refix` の when）

- P131 案の直しの後、波及の一覧を直した項目で作り直す（1 回目の一覧を使い回さない）。単位の前の一覧（ripple-units）は作らない
  - 元: works/blk-plan/lib/planblk.py:503 `replan_ripple`（replan.revised_fields）
  - 今: lib/planfile.py:1028 `ripple_items`（その周の案で作る）、WF workflows/plan/works-factory-plan.yaml:198（ripple-units は mode plan だけ）
  - 証: tests/workflows/test_plan.py::ReplanCase.test_replan_rejects_extra_items_and_changed_keys_then_amends（assert: :630 ripple-units skipped・:655-656）
  - 本物の run: plan/r2/ripple.json。筋書きでのみ
  - 狭め: 無し

- P132 案の直しは、修正の後の HEAD で測り直さず、直す元の周の構造の実測と構造の目の行を使う（構造の目を起こさない）
  - 元: works/darkfactory/darkfactory.yaml:687 `replanning`（blk-structure を通らない 2 度目の include）
  - 今: lib/planfile.py:671 `structure_dir(… source=prev)`・:623 `open_round`
  - 証: tests/workflows/test_plan.py::ReplanCase.test_replan_reuses_the_first_measure_after_the_tree_moved（assert: :667-669）・lib/tests/test_planfile.py::ReplanInputsCase.test_replan_structure_is_the_source_rounds（:413）
  - 本物の run: plan/r2/round.json の `structure` が plan/r1 と同じ置き場。筋書きでのみ
  - 狭め: 無し

- P133 案の直しの後の単位ごとの深さを、直した案で決め直し、2 度目の修正はそれを使う
  - 元: works/darkfactory/darkfactory.yaml:593（h-depth。replanned）
  - 今: lib/planfile.py:1041 `collect`（その周の案で depth）、P74 works-factory-line.yaml:604 `depth: $replan.output.depth`
  - 証: P74 tests/workflows/test_line.py::…test_replanned_depth_wins（P74 tests/workflows/test_line.py:521）
  - 本物の run: `$replan.output.depth`。筋書きでのみ
  - 狭め: 無し

- P134 案の直しの役も 3 回拒まれたら諦めて ready: false（諦めは run を止めず、後の段が読む）
  - 元: works/.shared/core/replan.py:544 `accept_reply`（GIVE_UP_AFTER）・:625 `gate`（PLAN_GAVE_UP_WHY で項目を諦める）
  - 今: WF workflows/plan/scripts/plan_accept.py（rolekit.with_done）、lib/planfile.py:1011 `why_not_ready`
  - 証: 形 plan では tests/workflows/test_plan.py::AcceptCase.test_three_rejections_give_up_with_every_pointer。形 replan の 3 回の拒否の試験は無い → 要追加: tests/workflows/test_plan.py::ReplanCase.test_three_rejections_give_up_without_amending — 3 回とも拒むと ready: false・plan-fields.json は前の周のまま・ripple.json の error に拒否の訳
  - 本物の run: 筋書きでのみ
  - 狭め: 下の P142（諦めた項目を人への行に載せる）を参照

- P135 案の直しの役が読んだ証拠（reads-replan-<役>.json の索引。1 回目の reads-plan-block.json を上書きしない）
  - 元: works/.shared/core/replan.py:114 `READS_INDEX`・:115 `READS_PREFIX`、works/tests/test_replan.py:650
  - 今: 無し
  - 証: 当たらない（取らない）
  - 本物の run: 無し
  - 狭め: #75・#73 で狭めた（U6「Archon の役の節でどこに取るかが未決」）。Archon の出来事の記録には道具の呼びの行が在る（packages/workflows/src/provider-events.ts:134 `case 'tool_call'`）ので、不可と言い切れない → 持ち主へ（PD の読んだ証拠の行と同じ根）

### C. 案の直し: 事前審査の側と関所

- P136 案の直しの事前審査は壁打ちを回さず 1 回で返る（stalled はいつも偽、往復を控えに積まない）。裁かれた項目は番号か項目の id で引く
  - 元: works/blk-plan/lib/planblk.py:1341 `converge_check`（控えの事実で 1 往復で done）、works/tests/test_blk_plan.py:2132 `test_replan_include_decides_by_record_facts`
  - 今: lib/boardview.py:392 `open_pass`（form replan）・:384 `_ruled`・:919 `collect`（`ok, stalled = not blocks, False`）
  - 証: tests/workflows/test_plan_review.py::ReplanCase.test_replan_is_one_shot（assert: tests/workflows/test_plan_review.py:1296・1299）・lib/tests/test_boardview.py::OpenCase.test_replan_form_records_no_pass（assert: lib/tests/test_boardview.py:132-138）
  - 本物の run: plan-review/pass-<k>/open の form。筋書きでのみ
  - 狭め: 無し

- P137 案の直しの事前審査の材料: 独立設計の節（design_only）・REVIEW_ASK_REPLAN・planmarks.REVIEW_ASK・裁かれた項目ごとに承認済みの前の形・申し出と裁定の行・直した形（決め手の欄つき）
  - 元: works/.shared/core/replan.py:410 `prep`（plan-review）・:387 `_section`
  - 今: lib/boardview.py:750 `review_material`・:484 `replan_items`・:730 `_replan_section`
  - 証: tests/workflows/test_plan_review.py::ReplanCase.test_replan_is_one_shot（assert: :1292-1295）・lib/tests/test_boardview.py::ReplanItemsCase.test_old_new_and_rows_per_ruled_item（assert: :357-364）。独立設計の節（DESIGN_HEAD）が載ることは照らされていない → 要追加: tests/workflows/test_plan_review.py::ReplanCase.test_replan_material_carries_the_independent_design — 設計が立つ run の形 replan の材料に planblk.DESIGN_HEAD
  - 本物の run: plan-review/pass-<k>/prompt.md。筋書きでのみ
  - 狭め: 下の P138・P139

- P138 案の直しの事前審査には、裁かれた項目だけを見せる（ほかの項目の案・欄を貼らない）
  - 元: works/.shared/core/replan.py:410 `prep`（「事前審査の役には…前後の項目だけを渡す」）、works/tests/test_replan.py:532 `test_review_role_sees_design_only_and_both_forms`（assertNotIn CLAMP・planmarks.REVIEW_HEAD）
  - 今: lib/boardview.py:750 `review_material` は形 replan でも「修正役の案: 」に案の全項目の JSON を貼る。lib/boardview.py:873 `_faces_of` は、どの直した項目とも単位が重ならない穴を全部の直した項目の物と数えるので、直していない項目への regression の穴でも人に聞く
  - 証: tests/workflows/test_plan_review.py::ReplanCase.test_replan_is_one_shot は ITEM_HEAD n=1 が無いことだけを見る（案の JSON の項目 1 は見ない）→ 要追加: tests/workflows/test_plan_review.py::ReplanCase.test_replan_material_shows_only_ruled_items — 形 replan の材料に直していない項目の unit_keys・approach が無い
  - 本物の run: plan-review/pass-<k>/prompt.md。筋書きでのみ
  - 狭め: #73 に記載無し。不可でない → 戻す

- P139 案の直しの事前審査の申し出と裁定の行は、線が渡す conflicts（fix の conflicts.json）から引く
  - 元: works/.shared/core/replan.py:387 `_section`（盤面の食い違いの控え）
  - 今: lib/boardview.py の open_pass(conflicts=…)。線の replan-review の with: に conflicts: $fix.output.conflicts
  - 証: lib/tests/test_boardview.py::ReplanItemsCase・tests/workflows/test_line.py::LineWiringCase.test_replan_review_gets_the_conflicts（部分 B1。旧 WiringCase.test_replan_review_gets_the_fix_conflicts）
  - 本物の run: plan-review/pass-<k>/prompt.md の「### 修正の段の申し出と裁定」節（今の線では出ない）。筋書きでのみ
  - 狭め: #74（線）の配線の欠け。不可でない → 戻す → 部分 B1 で配線を縛った

- P140 案の直しの事前審査の返答を受け付ける: 壁打ちと束ね役の任意の欄（resolved・items・synergy）は外してから照らし、独立設計が立つ時は穴の引用（DRIFT_HEAD）と design_map を直した項目の行と照らす
  - 元: works/.shared/core/replan.py:511 `_take`（plan-review: drop_fields・design.quote_gaps）
  - 今: lib/boardview.py:827 `_take`（converge.split・tree_split・planblk.design_gaps(items=ruled)）
  - 証: tests/workflows/test_plan_review.py::ReplanCase.test_replan_after_review_reads_the_revised_plan（assert: :1349）。DRIFT_HEAD の引用の照らしを形 replan で見る試験と、任意の欄を拒まない試験は無い → 要追加: tests/workflows/test_plan_review.py::ReplanCase.test_replan_drift_quotes_checked_and_extra_fields_dropped — 形 replan で引用の無い drift の穴は DESIGN_QUOTE_REJECT、resolved・items・synergy つきの返答は受けて review.json に items が無い
  - 本物の run: plan-review/pass-<k>/review.json。筋書きでのみ
  - 狭め: 無し

- P141 人に聞くかの決まり: 直した項目は、約束の欄（unit_keys・narrows・removes・allowed_paths・out_of_scope・rewrite_tests・tests の behavior。決め手の欄と rewrite_tests の limit は外して比べる）が承認済みと同じで、事前審査が人に聞く種類（regression・policy）の穴を挙げなかった時だけ聞かずに通す。無人の run では範囲を広げるだけの直し（allowed_paths に足す・out_of_scope から外す）も聞かずに通す。項目ごとの判じを pass-<k>/replan.json に置く
  - 元: works/.shared/core/replan.py:625 `gate`、works/.shared/core/planmarks.py:487 `contract_diff`・:511 `widened`
  - 今: lib/boardview.py:886 `replan_asks`、P74 workflows/line/scripts/ask_replan.py `ask`（線でもう一度 contract_diff・widened を当てる）
  - 証: tests/workflows/test_plan_review.py::ReplanCase.test_contract_change_or_human_face_asks（assert: :1311・1313・1321）・test_unattended_widen_only_is_not_asked（:1330）・lib/tests/test_plan_fields.py::TestContractFields・TestWidened・P74 tests/workflows/test_line.py::AskReplanCase（assert: P74 tests/workflows/test_line.py:264-283）
  - 本物の run: plan-review/pass-<k>/replan.json の `ask`・`contract_changed`。筋書きでのみ
  - 狭め: 無し（同じ決まりを 2 か所で当てる重ねは掃除の候補）

- P142 案の直しを終えられなかった項目（計画の役の諦め・事前審査の諦め・関所の答えが無い）は、項目ごとに諦めの訳をつけ、裁定の文を字のまま人への行（最後の関所と次の run の依頼）に載せる。ほかの項目は採れる
  - 元: works/.shared/core/replan.py:625 `gate`・:583 `_give_up`（PLAN_GAVE_UP_WHY・REVIEW_GAVE_UP_WHY・NO_GATE_WHY）・:256 `_sync_closed`、works/tests/test_replan.py:1032 `test_gave_up_paths_reach_ask_human_verbatim`
  - 今: 一部。lib/runreport.py:545 `prior_failures` が「計画が修正案を出せなかった」1 行を足すだけ。lib/outcome.py:171-181 は待つ行を CLOSE_WHY で締めるが、案の直しの諦めの訳（PLAN_GAVE_UP_WHY ほか）と項目ごとの扱いは無い。線は全部の項目で 1 つの go（P74 workflows/line/scripts/ask_replan.py）
  - 証: 要追加: tests/workflows/test_report.py::ReplanGiveUpCase.test_gave_up_replan_names_ruling_text_and_reason — replan が ready: false の run の報告と次の依頼に、裁定の文（字のまま）と諦めの訳が載る
  - 本物の run: 筋書きでのみ
  - 狭め: #75・#74 に記載無し。項目ごとに採る/諦めるは Archon で不可でない → 持ち主へ（全部か無しかに倒したかの確認） 決め: 人の答えは今の works と同じく 1 つの語（works/.shared/core/replan.py:699-744）。機械の側の項目ごとの諦めは戻すと決めた。区分 P の issue（線の配線の文書の「この文書の外」の「決めた物」）

- P143 案の直しの関所の答え: continue・approve で直した項目を使って 2 度目の修正へ、stop・reject で run を止める（1 回目の修正の差分は報告に残る）
  - 元: works/.shared/core/replan.py:699 `answer`・:151 `DECISIONS`・:138 `GATE_BY`
  - 今: P74 works-factory-line.yaml:570-600 `gate-replan`・`answer-replan`（gate_answer.answer）
  - 証: P74 tests/workflows/test_line.py::GateAnswerCase.test_reject_stops_like_stop・ReplanAnswerCase.test_answer_is_the_gate_answer_with_the_fix_answers・筋書き P74 workflows/line/fixtures/replan-stop.stubs.yaml
  - 本物の run: run の置き場 gates/gate-replan.json。筋書きでのみ
  - 狭め: 無し（線の棚卸しと重なる）

- P144 2 度目の修正に渡す答えの文: 修正前の関所で人が答えた条件・案の直しの関所の一言に加え、採った項目の事前審査の穴のうち人に聞く種類でない物を見出しつきで渡す
  - 元: works/.shared/core/replan.py:677 `_notes`（FIX_NOTES_HEAD・NOTE_HEAD・FACES_HEAD）
  - 今: P74 workflows/line/scripts/replan_answer.py `fix_answers`（前の 2 つだけ。FACES_HEAD の節が無い。refix の with: P74 works-factory-line.yaml:592-607 にも事前審査の返りが無い）
  - 証: P74 tests/workflows/test_line.py::ReplanAnswerCase.test_refix_answers_carry_the_before_fix_conditions_and_the_replan_note（assert: P74 tests/workflows/test_line.py:164-168）。穴の節は無い → 要追加: P74 tests/workflows/test_line.py::ReplanAnswerCase.test_refix_answers_carry_the_non_human_faces_of_taken_items — replan-review の review の人に聞く種類でない穴が FACES_HEAD の見出しの下で fix_answers の text に載る
  - 本物の run: 筋書きでのみ
  - 狭め: 不可でない → 戻す（#74 に記載無し）

- P145 無人の run で範囲を広げるだけの直しを聞かずに通した時、trace に `replan_widened_unattended` を 1 度だけ書き、報告に「直した——無人の run なので人に聞かずに範囲を広げた（…）」の行を載せる
  - 元: works/.shared/core/replan.py:152-154 `WIDEN_OP`・`WIDEN_LINE`・:761 `_widen_text`・:767 `lines`
  - 今: P74 workflows/line/scripts/ask_replan.py が `widened` を返すだけ（docstring に「report に受ける入力が無く、まだ報告には届かない」）
  - 証: P74 tests/workflows/test_line.py::AskReplanCase.test_unattended_passes_widening_only_and_records_it（assert: :280。返りに載るだけ）→ 要追加: tests/workflows/test_report.py::ReplanLinesCase.test_widened_without_asking_is_reported — `$ask-replan.output.widened` が報告の案の直しの節に載る
  - 本物の run: 筋書きでのみ
  - 狭め: #74 が自分で書いた未配線。不可でない → 戻す

- P146 報告と最後の関所の文に、案の直しの項目ごとの 1 行（直した——人が承認した／聞かずに通した（手段の欄だけ）／直さずに諦めた: 訳／未完了）を見出し AMEND_HEAD の下に並べる
  - 元: works/.shared/core/replan.py:767 `lines`・:144 `AMEND_HEAD`、works/tests/test_replan.py:1097-1124
  - 今: 無し（AMEND_HEAD・項目ごとの行の組み立ては main にも P74 にも無い。outcome.py は待つ行の締めだけ）
  - 証: 要追加: tests/workflows/test_report.py::ReplanLinesCase.test_each_replanned_item_has_one_line — replan の返りと関所の答えから、項目ごとの結末の行が報告に載る
  - 本物の run: 筋書きでのみ
  - 狭め: 記載無し（#68 report・#74 line のどちらか）。不可でない → 戻す

- P147 案の直しを待つ行の締め（落ちの無い run は CLOSE_WHY で諦めた行にし、途中で落ちた run は締めず未完了 PENDING_WHY と報告して resume で続ける）
  - 元: works/.shared/core/replan.py:159 `close`・:176 `close_at`・:202 `settle`
  - 今: lib/outcome.py:77-79・:171-181（報告の組み立てで締めた形に読む）、lib/runreport.py:501-514
  - 証: lib/tests/test_outcome.py・lib/tests/test_runreport.py（CLOSE_WHY・PENDING_WHY を照らす。report の棚卸しで照合）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（報告の側の行。report の棚卸しと重なる）

- P148 1 回目に受け付けた修正の返答の控え（待つ単位が在る間に盤面に渡さずに置いた物）を、修正の段を抜ける時に渡す・止まった盤面では渡さない・何度呼んでも 1 度だけ
  - 元: works/.shared/core/replan.py:184 `hand_held`・:202 `settle`、works/tests/test_replan.py:157-255（TestHold）
  - 今: 盤面が無いので形が変わった。1 回目と 2 回目の修正を線が束ねる（P74 workflows/line/scripts/fixed.py、works-factory-line.yaml:615-660 `fixed`）
  - 証: P74 tests/workflows/test_line.py::…test_refix_is_merged_without_losing_the_first（:487）・test_replan_without_the_second_fix_is_not_done（:478）
  - 本物の run: 筋書きでのみ
  - 狭め: 盤面の機構は当たらない（fix・線の棚卸しで照合） 決め: 線の fixed が 1 回目と 2 回目を束ねる形で能力は残る（線の配線の文書の「この文書の外」の「決めた物」）

- P149 2 度目の修正の段は、案の直しで返った単位だけを直す義務にし、1 回目の差分と束ねる（TestSecondPass・TestLineReplay の筋）
  - 元: works/tests/test_replan.py:1164-1465（TestSecondPass・TestLineReplay）
  - 今: P74 works-factory-line.yaml:592-607 `refix`（only_items: $fix.output.replan_items）・`fixed`
  - 証: P74 tests/workflows/test_line.py::…test_fix_is_the_first_and_second_fix_merged（:561）・筋書き P74 workflows/line/fixtures/replan-answers.stubs.yaml
  - 本物の run: 筋書きでのみ
  - 狭め: fix・線の棚卸しで照合（PB の外）


## 事前審査のブロック（独立設計 R2・項目ごとの木・受け付け・人の方針・読んだ証拠）

置き場の記法: 本物の run の `plan-review/…` は run の置き場（ARTIFACTS_DIR）の下。`pass-<k>` の k は修正案の周の番号（plan-fields.json の round）。

### ブロックの形と返りの約束

- P150 返す節は review・outcome_field は pass で、返りはちょうど 7 欄（pass・stalled・review・design・gate_axes・ask_human・questions。review と design は archon_artifact の指し札、gate_axes は 4 つの軸ごとの {ok, note}）
  - 元: works/blk-plan/blk-plan.yaml:995 `collect`（返りは {ok, plan_file, review_file, asks_human, gate_kinds, reads_file, gave_up, reason_file, ripple_file}）・works/blk-plan/lib/planblk.py:1441 `collect`
  - 今: workflows/plan-review/works-factory-plan-review.yaml:290-340 `review`・lib/boardview.py:919 `collect`
  - 証: tests/workflows/test_plan_review.py::YamlCase.test_returns_review_and_outcome_pass（assert: tests/workflows/test_plan_review.py:285）・YamlCase.test_return_output_format_is_exactly_the_contract（assert: :290-303）
  - 本物の run: 節 `review` の出力 7 欄。`review.path`=`plan-review/pass-1/review.json`
  - 狭め: 元の返りの reads_file（読んだ証拠の索引）が無い → P211 に回す

- P151 入力は約束の 7 つ（required）と、足した start・answers・ruling・conflicts・gate_answers（既定 "null"・"[]"）
  - 元: works/blk-plan/blk-plan.yaml の inputs（excluded_file・replan・verify_file・review_tree）と盤面
  - 今: workflows/plan-review/works-factory-plan-review.yaml:10-51
  - 証: tests/workflows/test_plan_review.py::YamlCase.test_inputs_are_the_contract_and_the_added_defaults（assert: :307-311）
  - 本物の run: 線の節 `plan-review-run` の with（workflows/line/works-factory-line.yaml:204-217）
  - 狭め: 無し（入力の置き換え。excluded_file は判定の隣の pr-excluded.json、review_tree は始めの記録の features から読む → P181・P197）

- P152 線が conflicts と gate_answers を渡さない（#74 の head の線は plan-review の 2 つの差し込みのどちらにも渡していない）ので、案の直しの事前審査に申し出と裁定の文が載らず、修正前の関所で人が通した行が次の差し込みで聞き直される
  - 元: works/darkfactory/darkfactory.yaml:687 `replanning`（盤面が conflicts と process.human_items を持った）
  - 今: lib/boardview.py の open_pass（conflicts・gate_answers を受ける口）・線の replan-review の with: の conflicts・gate_answers（plan-review-run は修正前の関所より前なので渡さない）
  - 証: tests/workflows/test_line.py::LineWiringCase.test_plan_review_gets_conflicts_and_gate_answers（部分 B1）
  - 本物の run: `plan-review/open.json` の `human_items` に修正前の関所の答えの行が在るか（今は無い）
  - 狭め: #74 の線（5 回目の直しの中）で未配線。Archon で不可でない → 線に足す → 部分 B1 で配線を縛った

- P153 全部の節（役も script も）が mutates_checkout: false。script は全部 uv の script の宣言を頭に持ち、対象に pyproject.toml が在っても .venv・uv.lock を作らない
  - 元: works/blk-plan/blk-plan.yaml（役の節の mutates_checkout: false）
  - 今: workflows/plan-review/works-factory-plan-review.yaml 全部の節・workflows/plan-review/scripts/*.py の頭
  - 証: tests/workflows/test_plan_review.py::YamlCase.test_ai_and_script_nodes_are_read_only（assert: :322）・ScriptHeadCase.test_every_script_declares_itself（:1517）・ScriptHeadCase.test_uv_run_leaves_a_python_project_untouched（assert: :1538-1540）
  - 本物の run: 節の記録に checkout 変化の失敗が無い
  - 狭め: 無し

- P154 返す節は落ちない: 壊れた入力・空の置き場・受け付けの無い差し込み・lib が読めない時も、終了 0 で pass: false・ask_human: true・訳を名指す questions と、在る指し札の先（failed/ の review.json・design.json・空の gate-passes.json）を返す
  - 元: works/blk-plan/scripts/collect.py（元は配線の誤りで 2 で止めた。works/tests/test_blk_plan.py:1227 `test_scripts_exit_two_on_wiring`）
  - 今: workflows/plan-review/scripts/result.py:53 `main`・lib/boardview.py:919 `collect`
  - 証: tests/workflows/test_plan_review.py::ResultCase.test_broken_inputs_never_fail_the_return_node（assert: :1419-1427）・test_empty_folder_never_fails_the_return_node（:1444-1448）・test_open_without_accepted_review_never_fails（:1454-1457）・FailSafeCase.test_result_without_the_lib_returns_the_failed_shape（:1479-1487）・test_failed_return_writes_the_passes_beside_the_review（:1494）
  - 本物の run: 筋書きでのみ（健全な種では落ちない）
  - 狭め: 無し（止めて 2 を返す形から、落ちない偽の結末へ替えた。能力は増えた）

- P155 差し込みの頭 open は最初に前の差し込みの open.json を消し、落ちた差し込みは前の差し込みの結末を今回の物として返さない
  - 元: 無し（盤面の周が分けていた）
  - 今: workflows/plan-review/scripts/pass_open.py:66 `main`
  - 証: tests/workflows/test_plan_review.py::ResultCase.test_failed_open_drops_the_previous_material（assert: :1435-1439）・FailSafeCase.test_open_without_the_lib_drops_the_previous_material（assert: :1503-1507）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P156 出し直しの輪は 3 回（rolekit.GIVE_UP_AFTER）で、until_bash は同じ輪の受け付けの done。独立設計の輪は fresh_context: false（拒まれた後は同じ会話）、事前審査の輪は true。輪の後の節は all_done
  - 元: works/blk-plan/blk-plan.yaml:79-190（r2-design-loop）・:701（plan-review-loop）。works/tests/test_blk_plan.py:215 `test_design_loop_first_and_tool_less`・:237 `test_loops_fresh_single_ai_and_give_up`
  - 今: workflows/plan-review/works-factory-plan-review.yaml:75-83・:146-155・:290-294
  - 証: tests/workflows/test_plan_review.py::YamlCase.test_loops_are_three_and_end_on_accept_done（assert: :359-365）
  - 本物の run: 節 `r2-accept`・`review-accept` の出力 `done`
  - 狭め: 無し

- P157 役に届く文に $LOOP_PREV が無く、役の指示書は自分の支度の出力だけを読み、{{…}} の差し込みを使わない。輪の中の id はほかのブロック・線と重ならない。script が読む INPUTS_* は宣言した物だけ
  - 元: works/tests/test_blk_plan.py:291 `test_no_loop_prev_reaches_a_prompt`・:305 `test_loop_ids_unique_across_blocks`・:271 `test_script_inputs_match_with`
  - 今: workflows/plan-review/commands/*.md・works-factory-plan-review.yaml
  - 証: tests/workflows/test_plan_review.py::YamlCase.test_no_loop_prev_reaches_a_role（:437）・test_loop_ids_unique_across_blocks（:450）・test_commands_read_only_their_prep（:403-405）・test_scripts_read_only_declared_inputs（:432）
  - 本物の run: 筋書きでのみ（形の試験）
  - 狭め: 無し

- P158 筋書き 8 本（pass・block・ask-human・stalled・review-give-up・r2-give-up・r2-skipped・open-failed）が止めた Archon の workflow test で通る
  - 元: works/blk-plan/fixtures/*.stubs.yaml（3 本）・works/tests/test_blk_plan.py:316 `test_fixtures`
  - 今: workflows/plan-review/fixtures/
  - 証: tests/workflows/test_plan_review.py::FixtureCase.test_fixtures_pass_in_archon（assert: :1664-1669）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

### 独立設計（R2）

- P159 独立設計は run で 1 度だけ、事前審査より前に作る。設計の控えが在る・壊れている（作り直さない）・3 回とも拒まれて諦めた時は起こさない
  - 元: works/.shared/core/design.py:492 `due`・:514 `snap`
  - 今: lib/boardview.py:611 `r2_due`・workflows/plan-review/works-factory-plan-review.yaml:77 `when: "$open.output.r2_go == true"`
  - 証: lib/tests/test_boardview.py::OpenCase.test_r2_due（assert: lib/tests/test_boardview.py:164-174）・tests/workflows/test_plan_review.py::DesignCase.test_design_accepted_and_reaches_the_review（assert: :560「設計を 2 度作らない」）・DesignCase.test_give_up_on_the_third_reject_still_done（assert: :584）
  - 本物の run: 節 `open` の出力 `r2_go`=true（1 往復目）・2 往復目は false、`plan-review/design.json` が 1 つ
  - 狭め: 無し（元の盤面の節の表と再発火の条件 loop.r2_refire は元の works でも design.json の在る run では効かなかった）

- P160 目的の出典が取れない（purpose.json の source が「目的不明」）時は独立設計を回さず、事前審査の材料に「目的の出典が取れない（目的不明）——独立設計を回さない」を載せる
  - 元: works/.shared/core/graphloops/rules/review-loop.py:403 `purpose_unusable`・works/.shared/core/design.py:67 `UNUSABLE`
  - 今: lib/boardview.py:183 `purpose_unusable`・lib/design.py:60 `UNUSABLE`
  - 証: tests/workflows/test_plan_review.py::DesignCase.test_skipped_when_purpose_unusable（assert: :611-613）
  - 本物の run: 筋書きでのみ（種の依頼は目的が取れる）
  - 狭め: 無し

- P161 目的の監査が「狭めている」と言い、その findings が全部裏取りの柵（cite）を通っている時は独立設計を回さない（素の文字列の findings では止めない）
  - 元: works/.shared/core/graphloops/rules/review-loop.py:398 `purpose_findings_vetted`・:403 `purpose_unusable`（record.process.purpose_review を読む）
  - 今: lib/boardview.py:177・:183（open.json の purpose_review。lib/boardview.py:436 は judgment.json の欄 `purpose_review` から取る）
  - 証: tests/workflows/test_plan_review.py::DesignCase.test_skipped_when_purpose_unusable（assert: :616-619。試験は judgment.json に purpose_review を手で置く）。本物の線では効かない → 要追加: tests/workflows/test_plan_review.py::DesignCase.test_purpose_review_from_the_judge_material_skips_r2 — judge が置く判定の隣の `material-purpose-review.json`（main lib/judge_accept.py:2860 `_accepted`・:3015）の reply が「狭めている」で cite つきなら r2_go が false
  - 本物の run: 筋書きでのみ
  - 狭め: #73 で狭めた（judge の judgment.json は purpose_review を持たない。lib/judge_accept.py:3015 は判定役の材料の中にだけ置く。Archon で不可でない → 判定の隣の材料のファイルを読む形に戻す）

- P162 独立設計の役は道具ゼロ・opus・effort high・設定は user だけ・sandbox 有効。既定の system prompt（作業ツリーの git の様子を入れる claude_code の preset）を役 blind-judge の本文に置き換える
  - 元: works/blk-plan/blk-plan.yaml:124-153（印 `works-node: r2-design isolated`。包みが Git の外の置き場で起こした）
  - 今: workflows/plan-review/works-factory-plan-review.yaml:95-126（systemPrompt。Archon の packages/providers/src/claude/provider.ts:825-826 が節の systemPrompt で既定 :954 を置き換える）
  - 証: tests/workflows/test_plan_review.py::YamlCase.test_role_nodes（assert: :329-342）・YamlCase.test_role_prefaces_are_the_ported_role_bodies（assert: :351）
  - 本物の run: 節 `r2-design` の記録に道具の呼びが 0 回
  - 狭め: 無し（隔て方を包みの起こし方から systemPrompt に替えた。cwd は作業ツリーのままだが道具ゼロで読めない）

- P163 独立設計に渡すのは元の目的と実測した制約（と人が決めた前提・方針）だけ。修正案・単位の label・判定の見立て（framing・one_shot）・波及・世界の解の行・リポジトリのパスは届かない。r2_prep が読む INPUTS_* の名を字で縛り、名を組んで読む書き方も無い
  - 元: works/.shared/core/graphloops/graphs/review-loop.json:4809-4900 `r2.design` の forbidden_inputs（実装・リポジトリ・コミット履歴・累積差分・決着済み論点）・works/tests/test_blk_plan.py:1145 `test_independent_design_input_has_no_means`
  - 今: lib/boardview.py:626 `r2_prompt`・workflows/plan-review/scripts/r2_prep.py
  - 証: tests/workflows/test_plan_review.py::IsolationCase.test_r2_prep_reads_only_the_allowed_names（assert: :459-463）・IsolationCase.test_prompt_carries_purpose_and_constraints_only（assert: :474-479）
  - 本物の run: `plan-review/r2-prompt.md` に目的の文と制約が在り、修正案の項目・stats.py のパスが無い
  - 狭め: 無し

- P164 目的の役が分けた依頼の解き方 means（purpose-means.json）は独立設計に渡らない
  - 元: works/tests/test_blk_plan.py:1145 `test_independent_design_input_has_no_means`
  - 今: lib/boardview.py:626 `r2_prompt`（purpose.json の purpose_text だけを読む）
  - 証: tests/workflows/test_plan_review.py::IsolationCase.test_purpose_means_do_not_reach_the_design（assert: :486-487）
  - 本物の run: `plan-review/r2-prompt.md` と `plan-review/design-premises.json` に means の文が無い
  - 狭め: 無し

- P165 人が決めた前提の節（人の関所の答え・依頼を固めた版のファイルから抜いた、依頼が名指した設計書の節だけ・対象のリポジトリの地図 ARCHITECTURE.md/AGENTS.md）を「渡すのは元の目的と制約だけ」の読み替えの文つきで頭に貼る
  - 元: works/.shared/core/design.py:432 `premises`・:379 `named_sections`・:402 `repo_map`・:82 `DESIGN_PREMISE_REREAD`・:528 `prep`
  - 今: lib/design.py:418 `premises`・lib/boardview.py:98 `DESIGN_PREMISE_REREAD`・:626 `r2_prompt`
  - 証: tests/workflows/test_plan_review.py::IsolationCase.test_human_answers_and_named_sections_are_pasted（assert: :531-536。名指さない節「定義どおり」は無い）
  - 本物の run: `plan-review/r2-prompt.md` の「## 人が決めた前提」（種の依頼は設計書を名指さず地図も無いので節は「渡っていない」の行だけになりうる）・`plan-review/design-premises.json` の given・withheld
  - 狭め: 無し

- P166 線が始めの記録・人の答えを渡さない時と、依頼のファイルが無い・UTF-8 でない時は、空として黙らず「渡っていない」「読めない（<型>）」を独立設計の本文と前提の控えの withheld と事前審査の材料の 1 行目に名指す
  - 元: 無し（盤面が必ず持った）
  - 今: lib/boardview.py:102-107（NOT_GIVEN_START・DEFAULT_START・DEFAULT_ANSWERS・REQUEST_UNREAD）・:372 `_request`・:722 `_defaults_line`
  - 証: tests/workflows/test_plan_review.py::IsolationCase.test_defaults_are_named_in_the_premises（assert: :492-495）・IsolationCase.test_unreadable_request_file_is_named（assert: :507-514）・lib/tests/test_boardview.py::OpenCase.test_defaults_are_named（assert: lib/tests/test_boardview.py:150-153）
  - 本物の run: `plan-review/design-premises.json` の withheld（線は start・answers を渡すので既定の行は無いはず）
  - 狭め: 無し（足した能力）

- P167 独立設計にも人の方針の節（前置き・本文・「方針に反するものを自分の判断で通すな」の段落）を貼る。方針の文書が無ければ節ごと貼らない
  - 元: works/.shared/core/graphloops/graphs/review-loop.json `r2.design` の prompt_append（policy-paste.md・policy.md）
  - 今: lib/boardview.py:653-654（policy.section）
  - 証: tests/workflows/test_plan_review.py::PortedMaterialCase.test_design_prompt_gets_the_policy（assert: :1622-1625）
  - 本物の run: 種に方針の文書が無いので `plan-review/r2-prompt.md` に「## 人の方針」が無い
  - 狭め: 無し

- P168 独立設計の受け付けは、道具ゼロの役でも起こす前の作業ツリーの姿（porcelain・差分・HEAD・枝）と比べ、変わっていれば拒んで design.json を書かない
  - 元: works/.shared/core/design.py:586 `check_design`（entry.tree_moved_since・READONLY_MOVED）・works/tests/test_blk_plan.py:1197 `test_design_tree_change_rejected`
  - 今: lib/boardview.py:664 `_moved`・:670 `check_design`
  - 証: tests/workflows/test_plan_review.py::DesignCase.test_tree_change_rejected（assert: :603-605）
  - 本物の run: `plan-review/r2-tree.json` が在り、節 `r2-accept` の ok=true
  - 狭め: 無し

- P169 独立設計の返答は JSON として読み、役の型（YAML の役の節の output_format を差し込みの頭が控えた物）で照らす。読めない・型に合わない返答は拒む
  - 元: works/.shared/core/design.py:586-601 `check_design`（accept.type_errors・accept.role_schema）・:603 `accept_reply`
  - 今: lib/boardview.py:670-694・workflows/plan-review/scripts/pass_open.py:22 `node_schema`
  - 証: tests/workflows/test_plan_review.py::DesignCase.test_give_up_on_the_third_reject_still_done（型に合わない返答が 3 回拒まれる。assert: :580-581）・YamlCase.test_scripts_read_role_formats_from_the_yaml（assert: :391-396）。弱い: 型の誤りの文を見ない → 要追加: DesignCase.test_off_schema_reply_names_the_type_error — `{"reason": "x"}` の拒みの reason に「独立設計の返答」と欠けた欄 question_stands が在ること
  - 本物の run: 節 `r2-accept` の reason が空
  - 狭め: 無し

- P170 問いが立たないと返した時、根拠に名指した `パス:行` が固めた版の追跡ファイルと行の範囲に当たらなければ拒む（名指しが無ければ拒まない）
  - 元: works/.shared/core/design.py:560 `anchor_misses`・:104 `PREMISE_MISS`
  - 今: lib/design.py:511 `anchor_misses`・lib/boardview.py:95・:686-688
  - 証: tests/workflows/test_plan_review.py::DesignCase.test_anchor_must_be_in_the_frozen_version（assert: :568-572）
  - 本物の run: 筋書きでのみ（種の問いは立つ）
  - 狭め: 無し

- P171 拒んだ理由は（役が道具を持たないので）次の本文の頭に文で貼り、3 回目の拒否で done・give_up して輪を抜ける。事前審査は設計なしで進み「独立設計は無い（独立設計が取れなかった: …）」を読む。返りの design は `{"missing": <訳>}` を指す
  - 元: works/.shared/core/design.py:528 `prep`（rolekit.with_reject）・:613 `missing`・works/tests/test_blk_plan.py:1170 `test_design_gave_up_does_not_stop_plan_review`
  - 今: lib/boardview.py:655-657・:696 `_done`・:947（design の控えが無ければ pass-<k>/design.json に missing）
  - 証: tests/workflows/test_plan_review.py::DesignCase.test_give_up_on_the_third_reject_still_done（assert: :580-594）
  - 本物の run: `plan-review/rejects-r2.design.json`（拒みが在れば）・返り `design.path`
  - 狭め: 無し

- P172 設計が「渡されていない」と書いた文を、前提の控えの渡した物（given）と並べて claims に控える（後の独立の目が突き合わせる）
  - 元: works/.shared/core/design.py:447 `claims_unpassed`・:454 `claims_given`
  - 今: lib/design.py:433・:440・lib/boardview.py:690-692
  - 証: tests/workflows/test_plan_review.py::DesignCase.test_unpassed_claims_are_paired_with_what_was_given（assert: :643-644）
  - 本物の run: `plan-review/design-premises.json` の claims（設計がそう書いた時だけ）
  - 狭め: 無し

- P173 独立設計の指示書の文は本線の r2.design.md の字のまま（許した直しだけ）。本線の行「前提のドリフト（あれば）」「裏取りを通っていない目的の判定（あれば）——この周の『狭めている』は…使えない」を持つ
  - 元: works/.shared/core/gl-prompts/prompts/review-loop/r2.design.md（loop.drift_notes・loop.purpose_review_stale を読む）
  - 今: workflows/plan-review/commands/r2-design.md（2 行が無く、「根拠に実物を名指すなら `<パス>:<行>`」を足した）
  - 証: 要追加: tests/workflows/test_plan_review.py::YamlCase.test_r2_command_is_the_original_with_only_the_allowed_edits — 元の r2.design.md の sha256 と、許した直しの一覧を逆に当てた本文が一致（plan の fix-plan.md の試験と同じ形）
  - 本物の run: `plan-review/r2-prompt.md`（指示書は command の側）
  - 狭め: #73 で狭めた（2 行の差し込みの元が盤面の周の控えで、このブロックに無い）。purpose_review_stale は判定の材料から作れるので Archon で不可でない → 戻すか持ち主に聞く。drift_notes は R2 が run の 1 周目に 1 度だけ走る今の形では元でも空だったかを持ち主に確かめる

- P174 問いが立たないと返した設計は事前審査で突き合わせず、穴にも挙げさせない（DESIGN_NOT_STANDS の文に、根拠の実物の名指しが無ければ印を添える）
  - 元: works/blk-plan/lib/planblk.py:443 `design_only`・works/tests/test_blk_plan.py:1157 `test_design_not_stands_is_not_a_face`
  - 今: lib/planblk.py:364 `design_only`
  - 証: tests/workflows/test_plan_review.py::DesignCase.test_not_stands_is_not_a_face（assert: :630-631）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P175 受けた設計は事前審査の材料の頭に、独立設計の節（DESIGN_HEAD・DESIGN_ASK・設計の役の理由・囲んだ設計の本文）として貼る
  - 元: works/blk-plan/lib/planblk.py:430 `design_section`・works/tests/test_blk_plan.py:1099 `test_design_before_plan_reaches_plan_review`
  - 今: lib/planblk.py:353 `design_section`・lib/boardview.py:767
  - 証: tests/workflows/test_plan_review.py::DesignCase.test_design_accepted_and_reaches_the_review（assert: :557-559）
  - 本物の run: `plan-review/pass-1/prompt.md` の「## 独立設計」と「=====独立設計ここから=====」
  - 狭め: 無し

- P176 DESIGN_ASK は、設計に対の無い仕組みと、項目の大きさの食い違いを名指して挙げよと頼む
  - 元: works/blk-plan/lib/planblk.py:200 `DESIGN_ASK`
  - 今: lib/planblk.py:144
  - 証: lib/tests/test_blk_plan.py::ScriptCase.test_design_ask_names_unpaired_mechanisms_and_item_size_gap（元と同名）
  - 本物の run: `plan-review/pass-1/prompt.md` の DESIGN_ASK の字
  - 狭め: 無し

- P177 「独立設計との構造の食い違い」「独立設計に対の無い仕組み」で始まる穴は、独立設計の文と案の行（approach・adds・allowed_paths・shrink_first）の両方に字のまま在る引用「…」が要る（幅と空白を畳み、字の 1 つ違いは見逃さない）
  - 元: works/.shared/core/design.py:674 `quote_gaps`・works/tests/test_blk_plan.py:1825・:1884
  - 今: lib/design.py:598 `quote_gaps`・lib/planblk.py:663 `design_gaps`
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_design_drift_face_needs_quotes_in_both（assert: :804-809）・QuoteFoldCase の 2 件（:1644-1656）・lib/tests/test_blk_plan.py::QuoteFoldCase の 2 件
  - 本物の run: `plan-review/pass-1/rejects-p2.plan_review.json` に DESIGN_QUOTE_REJECT（引用を誤った時だけ）
  - 狭め: 無し

- P178 design_map は案の adds の name ごとにちょうど 1 行、adds に無い行は誤り、design_quote は設計に字のまま在る（対が無いなら null）。受けた返答に design_map は残らない
  - 元: works/.shared/core/design.py:648 `_map_gaps`・works/tests/test_blk_plan.py:1849
  - 今: lib/design.py:572 `_map_gaps`
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_design_map_must_cover_every_added_name（assert: :828-834）
  - 本物の run: `plan-review/pass-1/review.json` に design_map が無い
  - 狭め: 無し

- P179 設計が無い run では引用の照らしをしない
  - 元: works/.shared/core/design.py:674（stands が None なら []）・works/tests/test_blk_plan.py:1870
  - 今: lib/design.py:598
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_design_quotes_not_checked_without_design（assert: :840）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P180 独立設計の控え design.json を後段に渡す（元は盤面の r2.design の節へ hand し、R2 の突き合わせと独立の目が読んだ。今は返り design の指し札）
  - 元: works/.shared/core/design.py `hand`（HANDED_OP・MISSING_OP の trace）
  - 今: lib/boardview.py:946-947・返り `design`
  - 証: tests/workflows/test_plan_review.py::ResultCase.test_result_matches_the_output_format（指し札の先が在る。assert: :1398-1400）・DesignCase.test_design_accepted_and_reaches_the_review（:556）。渡した・渡せなかったの trace（r2_design_handed・r2_design_missing）は 要追加: DesignCase.test_design_handoff_is_traced — 返す節が設計の有無を trace.jsonl に残すこと（元の報告がこの行を読んだかは report の区分で確かめる）
  - 本物の run: 返り `design.path`=`plan-review/design.json`・中の question_stands
  - 狭め: trace の行（HANDED_OP・MISSING_OP）が無い。Archon で不可でない → 読み手（report）が要るなら戻す。持ち主に確かめる

### 事前審査の材料（支度）

- P181 材料の頭は事前審査の役の定義（読むだけ・道具・作業ツリーを変えるな）・関所の決め手の頼み（gatemarks.HEAD）・既にある物を量ったか（REUSE_REVIEW）・人に回す物は人の口で（HANDOFF_REVIEW）・考えの住処の観点（concepthome.REVIEW_ASK）。修正案の入れてよい no の節は載せない
  - 元: works/blk-plan/lib/planblk.py:243 `HEAD`・:299 `head`・works/tests/test_blk_plan.py:736 `test_plan_review_head_unchanged`
  - 今: lib/planblk.py:186 `HEAD`・:222 `head`・lib/boardview.py:769
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_material_carries_the_mainline_inputs（assert: :745-749）・lib/tests/test_blk_plan.py::ConceptRuleCase.test_plan_head_has_concept_rule
  - 本物の run: `plan-review/pass-1/prompt.md` の頭
  - 狭め: 無し

- P182 材料の差し込み: 修正役の案・直す単位（番号つき。元の行「no の整数で指せ」を engine を機械に読み替えた字）・判定者の見立て（framing・one_shot）・先行例（在れば）・リポジトリと読む版と BASE と観点の正本（REVIEW.md）
  - 元: works/.shared/core/gl-prompts/prompts/review-loop/p2.plan_review.md:3-7・works/tests/test_blk_plan.py:951 `test_prompt_rendered_from_mainline`
  - 今: lib/boardview.py:127-128（UNITS_LINE・REPO_LINE）・:771-781
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_material_carries_the_mainline_inputs（assert: :745-750）・PortedMaterialCase.test_units_line_is_the_original_instruction_line（assert: :1582-1586）・PortedMaterialCase.test_material_carries_policy_base_units_and_concept_map（assert: :1570）
  - 本物の run: `plan-review/pass-1/prompt.md` の「## 差し込み」の節と `"no": 1`
  - 狭め: 無し

- P183 返答の unit_keys を no の整数で指してよく、受けた返答では単位の名に戻す
  - 元: works/blk-plan/lib/planblk.py の take（engine の番号の戻し）・works/tests/test_blk_plan.py:985 `test_plan_review_reply_by_number`
  - 今: lib/boardview.py:796 `named`
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_reply_by_number_is_named（assert: :688-690）
  - 本物の run: `plan-review/pass-1/review.json` の faces[].unit_keys が単位の key の字
  - 狭め: 無し

- P184 修正案の項目の works の欄（route・tests・rewrite_tests・refactor・allowed_paths・out_of_scope）を項目ごとの JSON で貼り、見る点を頼む
  - 元: works/.shared/core/planmarks.py:1069 `review_section`・works/tests/test_blk_plan.py:1543 `test_plan_review_prompt_carries_fields`
  - 今: lib/planmarks.py `review_section`・lib/planblk.py:353 `design_section`
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_material_carries_the_mainline_inputs（assert: :747 の planmarks.REVIEW_HEAD）。弱い: 欄の中身（受け入れテストの id・「本物の経路」）を見ない → 要追加: ReviewAcceptCase.test_material_carries_plan_fields — 欄の tests の id と route の字が材料に在ること（元 works/tests/test_blk_plan.py:1543-1548）
  - 本物の run: `plan-review/pass-1/prompt.md` の「## 修正案の項目の works の欄」
  - 狭め: 無し

- P185 構造の目の避け方・判定の処方・世界の解から外れた訳（欄 structure の deviation）を DEVIATION_HEAD の節で並べ、世界の解の類には依頼の解き方との比べの文を添えて、訳が成り立つかを見させる
  - 元: works/.shared/core/planmarks.py:1081 `review_section` の devs・works/tests/test_blk_plan.py:1455 `StructureFieldCase.test_plan_review_sees_deviations`・:1397 `WorldFieldCase.test_world_deviation_listed_for_review`
  - 今: lib/planmarks.py:1081・lib/planblk.py:356（worldmark.challenges を渡す）
  - 証: 要追加: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_material_lists_deviations — 欄 structure に deviation を持つ案で材料の REVIEW_HEAD より前に planmarks.DEVIATION_HEAD と訳の字が在り、世界の解の行の外れなら比べの文（元の WC-8841）も在ること
  - 本物の run: 筋書きでのみ（種の案が外れを書いた時だけ）
  - 狭め: 試験の欠けだけ（コードは在る）

- P186 置き場の修正案の欄の控えが凍結の印と食い違えば、支度は控え（plan-fields.json）を名指して落ち、書き換えた欄を審査に見せない
  - 元: works/blk-plan/lib/planblk.py:430 `design_section`（FieldsBroken → BoardGap で盤面を止める）・works/tests/test_blk_plan.py:1610 `test_tampered_fields_halt_plan_review_prep`
  - 今: lib/planblk.py:353-361・workflows/plan-review/scripts/review_prep.py
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_tampered_fields_stop_the_prep（assert: :772-773）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（落ち方は P187）

- P187 凍結の欄の食い違いで盤面を止めた（run を止める・止めた訳を残す）。今は支度の節が落ちるだけで、返す節は「review.json が無い」と返し、食い違いの訳は返りに載らない
  - 元: works/blk-plan/lib/planblk.py:107 `STOP_BY`・BoardGap → 盤面の stop
  - 今: lib/boardview.py:919 `collect`（review.json が無い時の Missing）・workflows/plan-review/scripts/result.py
  - 証: 要追加: tests/workflows/test_plan_review.py::ResultCase.test_tampered_fields_reason_reaches_the_return — 凍結の欄を書き換えた差し込みで、返り questions に planmarks.FIELDS_FILE の名と「凍結と食い違う」が在り pass: false
  - 本物の run: 筋書きでのみ
  - 狭め: #73 で狭めた（盤面の止めが無い）。Archon で不可でない（支度が訳をファイルに残し返す節が読めばよい）→ 戻す

- P188 判定の隣の並行 PR の外した範囲（pr-excluded.json）が在れば写して役の頭に名指す
  - 元: works/blk-plan/lib/planblk.py:299 `head`（入力 excluded_file）・works/tests/test_blk_plan.py:1042
  - 今: lib/boardview.py:411-413・lib/planblk.py:228-230
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_excluded_range_named（assert: :759-760）
  - 本物の run: 筋書きでのみ（種に並行 PR は無い）
  - 狭め: 無し

- P189 判定の単位のファイルが使うライブラリの文書の節を貼り、控えを置き場に置いて次の往復は網に出ずに読む
  - 元: works/blk-plan/lib/planblk.py:462 `lib_section`
  - 今: lib/planblk.py:383 `lib_section`・lib/boardview.py:770
  - 証: lib/tests/test_boardview.py::LibDocsCase.test_cache_is_reused_across_passes（assert: lib/tests/test_boardview.py:387-388）
  - 本物の run: `plan-review/pass-1/prompt.md` のライブラリの文書の節（stats.py は標準ライブラリだけ）
  - 狭め: 無し

- P190 考えの住処の地図（concepthome.section）を材料の末尾に貼る（元は包みが旗 concept-map の役の system prompt に足した）
  - 元: works/blk-plan/lib/planblk.py:106 `CONCEPT_FLAG`・works/tests/test_blk_plan.py:1562 `test_roles_carry_concept_map_flag`
  - 今: lib/boardview.py:783
  - 証: tests/workflows/test_plan_review.py::PortedMaterialCase.test_material_carries_policy_base_units_and_concept_map（assert: :1570-1571）
  - 本物の run: `plan-review/pass-1/prompt.md` の「## 考えの住処の地図」（種は地図なし）
  - 狭め: 無し

- P191 人の方針の節を材料の末尾と、木の下請けの決まりに足す。方針が無ければ節ごと無い。本文は PASTE_CAP（40000 バイト）で切って続きの置き場を書く
  - 元: works/.shared/core/gl-prompts/prompts/policy-paste.md・policy.md（p2.plan_review の prompt_append）・works/.shared/core/policy.py `brief`
  - 今: lib/policy.py `section`・`_capped`・lib/boardview.py:712・:783
  - 証: tests/workflows/test_plan_review.py::PortedMaterialCase.test_material_carries_policy_base_units_and_concept_map・test_no_policy_no_section（:1601-1602）・test_item_subagents_get_the_policy（:1613-1617）・lib/tests/test_policy.py::SectionCase の 2 件（assert: lib/tests/test_policy.py:26-31・:38-44）
  - 本物の run: 種に方針が無いので `plan-review/pass-1/prompt.md` に「## 人の方針」が無い
  - 狭め: 無し

- P192 貼る方針は run で固めた版の写し（元は record.process.policy.copy から貼った）。今は固めた版でなく、その時の文書のパスを読んで貼る
  - 元: works/.shared/core/policy.py `brief`（copy を読む）
  - 今: lib/boardview.py `review_material`（policy_copy）・`r2_prompt`（POLICY_FILE の copy）（部分 A で閉じた）
  - 証: tests/workflows/test_plan_review.py::PortedMaterialCase.test_material_pastes_the_frozen_copy
  - 本物の run: 筋書きでのみ
  - 狭め: #73 で狭めた（気づかれていない）。Archon で不可でない → 写しを貼る形に戻す → 部分 A で戻した

- P193 前の回の拒みの理由を次の材料の頭に貼る（REJECT_HEADING）
  - 元: works/blk-plan/lib/planblk.py の prep（拒みの理由のファイルを頭の 1 行で名指した。works/tests/test_blk_plan.py:1012 `test_reject_reason_by_file`）
  - 今: lib/boardview.py:784-786
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_reject_reason_pasted_in_the_next_material（assert: :731-732）
  - 本物の run: `plan-review/pass-1/prompt.md` の頭（拒まれた時だけ）
  - 狭め: 無し（ファイルの名指しから本文の貼りに替えた）

- P194 事前審査の指示書は役 judge の本文を字のまま頭に置き、続けて本線の p2.plan_review の決まり（見ること 1〜8・shrink・返し方・根拠は読む版で）を『リポジトリ: 』の行の後ろに持つ（許した直しは見出しの P2-11・P3 の言い換え・差し込みの行を材料へ）
  - 元: works/.shared/core/gl-prompts/prompts/review-loop/p2.plan_review.md・agents/judge.md（engine が前付けした）
  - 今: workflows/plan-review/commands/plan-review.md
  - 証: tests/workflows/test_plan_review.py::YamlCase.test_role_prefaces_are_the_ported_role_bodies（assert: :350）・YamlCase.test_review_command_carries_the_rules_after_the_repository_line（assert: :411-415。語の在る無しだけ）。弱い: 決まりの本文が 1 字ずれても緑 → 要追加: YamlCase.test_review_command_is_the_original_with_only_the_allowed_edits — 元の p2.plan_review.md の sha256 と、許した直しを逆に当てた本文の一致
  - 本物の run: 節 `plan-review` の指示書
  - 狭め: 無し

- P195 下請けに貼る決まりは指示書の『リポジトリ: 』の行から末尾までで、その行を run の値（対象・読む版・BASE・観点の正本）に置き換え、人の方針の節を足す
  - 元: works/blk-plan/lib/planblk.py:930 `_review_rules`（描いた指示書から切り出した）
  - 今: lib/boardview.py:702 `review_body`・lib/planblk.py:812 `_review_rules`
  - 証: lib/tests/test_boardview.py::RulesCase.test_review_body_names_the_run_values（assert: lib/tests/test_boardview.py:241-251）
  - 本物の run: `plan-review/plan-review-items/pass-1/item-1.md` の決まりの節（木の周だけ）
  - 狭め: 無し

### 事前審査の受け付け

- P196 役の型は本線の p2.plan_review の型に、関所の決め手の欄（gatemarks.MARK_SCHEMA・no_narrow）と壁打ちと束ね役の欄（resolved・items・design_map）を足した物。穴の種類はちょうど 8 つ（copy・entrance・contract_drift・dead_path・scope_creep・regression・policy・precedent）で、人の関所に回す種類（regression・policy）を含む
  - 元: works/blk-plan/lib/planblk.py:274 `output_format`・works/tests/test_blk_plan.py:134 `test_output_format_matches_graph`・rules の HUMAN_FACE_KINDS（review-loop.py:4084）・PLAN_ONLY_FACE_KINDS
  - 今: workflows/plan-review/works-factory-plan-review.yaml:178-269・lib/boardview.py:143
  - 証: tests/workflows/test_plan_review.py::YamlCase.test_role_formats_are_mainline_plus_marks（assert: :373-383）・KindsCase.test_role_kinds_are_exactly_the_eight_looked_at（assert: :1550-1551）
  - 本物の run: 節 `plan-review` の出力が型を通る
  - 狭め: 無し（本線の写しの型そのものとの照らしは、写しの graph が無いので 8 種と欄の持ち主で縛る）

- P197 役の前後で作業ツリー（porcelain・差分・HEAD・枝）が変われば拒み、往復を控えない。役が commit して HEAD を動かしても拒む
  - 元: works/blk-plan/lib/planblk.py:141 `take`（READONLY_MOVED）・works/tests/test_blk_plan.py:765・:1697
  - 今: lib/boardview.py:94・:833-835・pass-<k>/tree.json
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_read_only_tree_changed_rejected（assert: :699-705）
  - 本物の run: `plan-review/pass-1/tree.json`
  - 狭め: 無し

- P198 返答が JSON でなければ役に戻し、型（役の型）に合わなければ「事前審査の返答の型が合わない」で拒む
  - 元: works/blk-plan/lib/planblk.py:141 `take`（engine の型の照らし）
  - 今: lib/boardview.py:830-837
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_unreadable_reply_goes_back_to_the_role（assert: :710-711）・PortedMaterialCase.test_reply_out_of_the_role_format_is_rejected（assert: :1633-1634）
  - 本物の run: 節 `review-accept` の reason
  - 狭め: 無し

- P199 関所の項目の行の推し（recommend）の形が崩れていれば RECOMMEND_REJECT で拒む
  - 元: works/blk-plan/lib/planblk.py:114 `RECOMMEND_REJECT`・works/tests/test_blk_plan.py:849
  - 今: lib/boardview.py:86・:836-838
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_malformed_recommend_rejected（assert: :670-671）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P200 事前審査の穴は案の単位を指し（案に無い単位は拒む）、faces と shrink の key は一意、穴も別案も無いなら faces_none（20 字以上・空同然の語は不可）に何を確かめたかを書き、入口（entrance）の穴は no_add を併記する
  - 元: works/.shared/core/graphloops/rules/review-loop.py:3096 `plan_review_output`・:3067 `_keys_once`・:480 `blank`
  - 今: lib/boardview.py:201 `plan_review_output`・:191・:171
  - 証: lib/tests/test_boardview.py::RulesCase.test_plan_review_output（assert: lib/tests/test_boardview.py:213-217）・tests/workflows/test_plan_review.py::ReviewAcceptCase.test_entrance_needs_no_add（assert: :661-664）・ReviewAcceptCase.test_faces_none_and_units_and_keys（assert: :681-682）
  - 本物の run: `plan-review/pass-1/review.json` の faces_none か faces
  - 狭め: 無し

- P201 3 回とも拒まれたら done・give_up で輪を抜け、review.json に空の穴と最後の拒みの訳を書き、返す節は pass: false・stalled: true・ask_human: true と「事前審査の受け付けが諦めた: …」を questions に返す
  - 元: works/blk-plan/lib/planblk.py の main_accept（rolekit.with_done）・works/tests/test_blk_plan.py:1024 `test_give_up_ends_loop`
  - 今: lib/boardview.py:811 `take_review`・:130 `GIVEN_UP_FACES`・:931-933
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_give_up_on_the_third_reject（assert: :718-724）
  - 本物の run: `plan-review/pass-1/rejects-p2.plan_review.json`・返り stalled
  - 狭め: 無し

### 項目ごとの木の事前審査

- P202 木にするかは始めの記録の features の review_tree（on・off・auto。名指しが無ければ auto）で、auto は開いた項目が 2 つ以上の往復だけ木にする（1 項目は審査役 1 つで相乗りも無い）。知らない語は線の start が止める
  - 元: works/blk-plan/lib/planblk.py:128 `TREE_AUTO_MIN`・入力 review_tree・works/tests/test_blk_plan.py:2699-2768（unknown word は prep が止めた）
  - 今: lib/boardview.py:83・:362 `tree_word`・:604 `_tree_on`・#74 の head/workflows/line/scripts/start.py:70-75（features の語の照らし）
  - 証: tests/workflows/test_plan_review.py::TreeCase.test_review_tree_off_is_one_reviewer（:1227-1231）・test_review_tree_on_one_item_is_tree（:1237）・test_review_tree_auto_one_item_plan_is_one_reviewer（:1244-1246）・test_review_tree_auto_counts_open_items_per_pass（:1253-1263）・lib/tests/test_boardview.py::RulesCase.test_unattended_and_tree_words（:233-235）
  - 本物の run: 節 `open` の出力 `tree`（種は 2 単位なので案が 2 項目なら true）
  - 狭め: 無し（知らない語の止めは線の start へ移った。線の試験の持ち物）

- P203 木の往復では束ね役が、開いた項目ごとの下請けのファイルと相乗りのファイルを置き場（作業ツリーの外）に作り、Agent の道具で下請けを 1 つずつ起こす（subagent_type は全部 general-purpose）。下請けの答えは答えのファイルに書かせる
  - 元: works/blk-plan/lib/planblk.py:998 `tree_part`・:138 `SUBAGENT_TYPE`・:140 `AGG_ASK`
  - 今: lib/planblk.py:877 `tree_part`・:82・:84
  - 証: tests/workflows/test_plan_review.py::TreeCase.test_aggregator_spawns_item_subagents_and_synergy（assert: :970-981）
  - 本物の run: `plan-review/plan-review-items/pass-1/item-1.md`・`item-2.md`・`synergy.md` と、答え `plan-review/plan-review/r1/pass-1/item-<n>.json`
  - 狭め: 無し

- P204 下請けのファイルは審査の決まり・独立設計の節・自分の項目だけを持ち、項目の節より前は全部の項目で同じバイト（プロンプトのキャッシュ）
  - 元: works/blk-plan/lib/planblk.py:941 `brief_head`
  - 今: lib/planblk.py:820 `brief_head`
  - 証: tests/workflows/test_plan_review.py::TreeCase.test_brief_carries_only_its_item_inline（assert: :989-996）
  - 本物の run: `plan-review/plan-review-items/pass-1/item-1.md` と `item-2.md` の頭が同じ
  - 狭め: 無し

- P205 機械が下請けの答えを事前審査の返答にまとめ（束ね役の items は返答に残さない）、往復の控えに項目ごとの状態と当たりを積む
  - 元: works/blk-plan/lib/planblk.py:851 `tree_merge`
  - 今: lib/planblk.py:733 `tree_merge`・lib/boardview.py:843-845
  - 証: tests/workflows/test_plan_review.py::TreeCase.test_machine_merges_item_answers_into_review（assert: :1004-1014）
  - 本物の run: `plan-review/pass-1/review.json`（items が無い）・往復の控えの passes[].files に item-<n>.json
  - 狭め: 無し

- P206 誤った答えはその項目の下請けだけに戻す（済んだ下請けと起こし直す下請けを分けて名指し、下請けのファイルに前の答えの誤りを貼る）。項目の下請けの独立設計の引用の誤りもその項目だけを開き直す
  - 元: works/blk-plan/lib/planblk.py:823 `check_item`・:791 `item_answer_gaps`・:980 `_errors_part`
  - 今: lib/planblk.py:705・:673・:859
  - 証: tests/workflows/test_plan_review.py::TreeCase.test_invalid_answer_goes_back_to_its_item_only（assert: :1022-1034）・TreeCase.test_item_design_quotes_reopen_only_that_item（assert: :1050-1060）
  - 本物の run: 筋書きでのみ（下請けが誤った時だけ）
  - 狭め: 無し

- P207 開いた項目が全部 clean の往復は相乗りの下請けが要り、相乗りの引用は名指した項目の行と照らす。項目の下請けはほかの項目を名指せない。束ね役の返答は要約だけ（faces を自分で書けない）
  - 元: works/blk-plan/lib/planblk.py:150 `AGG_SYNERGY`・:186 `SUB_SYNERGY_ASK`
  - 今: lib/planblk.py
  - 証: tests/workflows/test_plan_review.py::TreeCase.test_all_clean_pass_needs_synergy（:1106-1110）・test_synergy_design_quotes_checked_against_named_items（:1079-1083）・test_item_answer_cannot_name_other_items（:1119-1120）・test_aggregator_reply_is_summary_only（:1091-1098）
  - 本物の run: `plan-review/plan-review/r1/pass-1/synergy.json`（全部 clean の時）
  - 狭め: 無し

- P208 2 往復目の下請けは前の往復からのその項目の案の差分と前の block の行き先だけを見て、前の往復で答えた当たりは機械が引き継ぐ。閉じた項目は審査しない
  - 元: works/blk-plan/lib/planblk.py:960 `_diff_part`・:973 `_carried_part`・:764 `carried_hits`
  - 今: lib/planblk.py:839・:852・:646
  - 証: tests/workflows/test_plan_review.py::TreeCase.test_second_pass_reviews_diff_and_carries_answers_and_notes（assert: :1131-1155）
  - 本物の run: 往復が 2 回の run だけ `plan-review/plan-review-items/pass-2/`
  - 狭め: 無し（往復の止めそのものは PB の区分）

- P209 判定者の先行例（adopt・adapt）の出典は run で 1 度だけ、1 つの項目の下請けが WebFetch で開いて確かめ、控え precedent-checks.json に置く。後の往復・ほかの項目には控えを貼って開かせない。確かめの行の欠けは拒む
  - 元: works/blk-plan/lib/planblk.py:660-742（precedent_checks・precedent_plan・save_precedents）
  - 今: lib/planblk.py:542-624
  - 証: tests/workflows/test_plan_review.py::TreeCase.test_precedent_sources_are_fetched_once_per_run（assert: :1163-1182）・TreeCase.test_missing_precedent_row_refused_without_surplus_lines（assert: :1219-1221）
  - 本物の run: `plan-review/precedent-checks.json`（判定が先行例を出した時）
  - 狭め: 無し

- P210 下請けの答えの余りの行（開く出典でない先行例の行・覆う当たりの無い hit）は拒まずに trace（plan_review_surplus）に残して捨てる
  - 元: works/blk-plan/lib/planblk.py:720 `_surplus`・:135 `SURPLUS_OP`
  - 今: lib/planblk.py:602・:79
  - 証: tests/workflows/test_plan_review.py::TreeCase.test_surplus_rows_dropped（assert: :1198-1205）
  - 本物の run: `plan-review/trace.jsonl` の op=plan_review_surplus（余りが出た時だけ）
  - 狭め: 無し

### 読んだ証拠（元の節 plan-reads）

- P211 役ごとに、機械が渡したパス（描いた指示書・材料のファイル・方針の文書）を役が本当に読んだかを、Archon の出来事の道具の呼び（tool_called の Read の file_path）と包みのフックの記録で集め、reads-<役>.json と索引 reads-plan-block.json に書き、欠けを報告の冒頭に出す（受け付けの条件にはしない）
  - 元: works/.shared/core/reads.py（collect・events_for・main_for）・works/blk-plan/blk-plan.yaml:978 `plan-reads`・works/blk-plan/lib/planblk.py:400 `collect_reads`・works/tests/test_reads.py の 25 件
  - 今: 無し
  - 証: 要追加: tests/workflows/test_plan_review.py::ReadsCase.test_reads_collected_from_archon_events — Archon の `workflow get <run> --verbose --events --json` の provider_event（tool_call の name=Read・rawInput.file_path）の見本の行から、事前審査の役が材料のファイルを読んだ・読まないを reads-plan-review.json に書くこと
  - 本物の run: 筋書きでのみ（今は記録が無い。戻せば `plan-review/reads-plan-review.json`）
  - 狭め: #73・#75 で狭めた（「Archon の出来事から役の道具の呼びを引く口が無い（U6）」）。Archon で不可でない: 止めた Archon は provider_event（packages/provider-contract/src/events.ts:30-44 の tool_call。name と rawInput を持つ）を run の出来事に積み、CLI の `workflow get --verbose --events --json` が生の行を出す（packages/cli/src/commands/workflow.ts:4076-4091 `listRunEvents` の rawEvents・packages/cli/src/help.ts:751 `--events`）→ 戻す

- P212 束ね役が下請けを本当に起こしたか（Agent の道具の呼びの数と subagent_type）を、下請けのファイルの数と突き合わせて trace（plan_review_agents）に残す
  - 元: works/.shared/core/reads.py `tool_count`・`tool_inputs`・works/blk-plan/lib/planblk.py:134 `AGENT_OP`・works/tests/test_blk_plan.py:2674 `test_reads_trace_agent_launches_against_item_files`
  - 今: 無し（答えのファイルが在り機械の照らしを通ることだけを縛る）
  - 証: 要追加: tests/workflows/test_plan_review.py::ReadsCase.test_agent_launches_counted_against_item_files — 出来事の見本の Agent の呼び 2 回・subagent_type general-purpose が、下請けのファイル 2 つと揃うと trace に {count: 2, files: 2} が載ること
  - 本物の run: 筋書きでのみ（戻せば `plan-review/trace.jsonl` の op=plan_review_agents）
  - 狭め: #73 で狭めた（U6 待ち）。Archon で不可でない（P211 と同じ出どころ）→ 戻す

- P213 役が web を引いた記録（WebFetch の URL・WebSearch の問い）を読んだ証拠のファイルに残す
  - 元: works/.shared/core/reads.py `web_fetches`・`web_searches`・works/tests/test_reads.py:227・:245・:254
  - 今: 無し
  - 証: 要追加: tests/workflows/test_plan_review.py::ReadsCase.test_web_calls_recorded — 出来事の見本の WebFetch・WebSearch の行から URL と問いが reads-plan-review.json の web に載ること
  - 本物の run: 筋書きでのみ（戻せば reads-plan-review.json の web。先行例の出典を開いた URL が見える）
  - 狭め: #73 で狭めた（U6）。Archon で不可でない（P211 と同じ）→ 戻す

### 人の方針の文書の固めと変化

- P214 方針の文書の置き場は始めの記録の policy_md の名指しか、無ければ git の共通の置き場の graphloops/policy.md。読んだ版を policy/<sha256>.md に写して policy.json に固める
  - 元: works/.shared/core/graphloops/rules/policy_input.py:22 `default_path`・:38 `snapshot`・:52 `locate`・:61 `resolve`
  - 今: lib/boardview.py:503 `_policy_path`・:518 `_policy_snapshot`・:532 `_frozen_policy`
  - 証: lib/tests/test_boardview.py::PolicyCase.test_default_location_is_read_when_not_named（assert: lib/tests/test_boardview.py:278-279）・OpenCase.test_policy_frozen_on_first_open_and_change_named（assert: :183-187）
  - 本物の run: `plan-review/policy.json`（種は方針が無いので sha256 が null）
  - 狭め: 無し（固める時期は P216）

- P215 固めた版から方針の文書が変わったら、前の版と今の版の写しと差分のファイルを置き、関所の行（policy_changed。置き場だけで本文を載せない）にする。固めた時に無く後で既定の置き場に置いた文書も変化に数え、固めた版の写しが消えていれば差分を作らず diff_missing を名指す
  - 元: works/.shared/core/graphloops/rules/policy_input.py:82 `change`・:105 `change_row`・:94（diff_missing）・works/tests/test_blk_plan.py:938 `test_policy_change_asks`
  - 今: lib/boardview.py:543 `policy_change`・:570 `change_row`・:939-941
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_policy_change_asks（assert: :784-785）・lib/tests/test_boardview.py::OpenCase.test_policy_frozen_on_first_open_and_change_named（assert: :189-190）・PolicyCase.test_document_placed_later_at_the_default_is_a_change（:285-290）・PolicyCase.test_lost_frozen_copy_is_named_not_diffed（:301-302）
  - 本物の run: 筋書きでのみ（run の中で方針を書き換えた時だけ）
  - 狭め: 無し

- P216 方針の文書は run の始め（盤面を作る時）に固めた。今は事前審査の最初の差し込みで固めるので、run の始めから計画の終わりまでの書き換え（判定・修正案が読んだ版との食い違い）は変化として見えない
  - 元: works/.shared/core/graphloops/rules/policy_input.py:61 `resolve`（盤面の on_init。record.process.policy）
  - 今: workflows/line/scripts/start.py `start`（record.policy = policy.freeze）→ lib/boardview.py `_frozen_policy`（始めの記録の版をそのまま置く）（部分 A で閉じた）
  - 証: tests/workflows/test_plan_review.py::PolicyCase.test_policy_frozen_at_run_start
  - 本物の run: `plan-review/policy.json` の sha256 と線の start の記録の版（今は記録に版が無い）
  - 狭め: #73 で狭めた（始めの記録が版を持たない）。Archon で不可でない（線の start が sha256 と写しを記録に置けばよい）→ 戻す（#73 が「約束を変える頼み」に挙げ済み） → 部分 A で戻した

### 区分の外への渡し（確かめだけ）

- P217 holeties（穴に修正案の項目か単位の枝の名札を付ける）は元でも事前審査でなく手直しと報告の部品で、事前審査のブロックは使わない
  - 元: works/.shared/core/holeties.py（使い手は refix.py・report.py）
  - 今: lib/holeties.py（使い手は lib/refix.py・lib/fixboard.py）
  - 証: lib/tests/test_holeties.py（fix の区分。ここは参照だけ）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（#73 の「holeties は使わない」は元の使い方と合う）


## 修正前の関所の材料（4 つの軸・人への問い・関所の答え）

- P218 関所の決め手の欄（decided_by・undecided_because・fences・world・recommend）と狭めない案（no_narrow）を、修正案の narrows の行と事前審査の faces の行の役の型にだけ足す。欄の型の持ち主は gatemarks.MARK_SCHEMA の 1 か所
  - 元: works/.shared/core/gatemarks.py:113 `MARK_SCHEMA`・:328 `with_marks`
  - 今: lib/gatemarks.py:111 `MARK_SCHEMA`・:313 `with_marks`・workflows/plan-review/works-factory-plan-review.yaml:195-215（faces の行）・workflows/plan/works-factory-plan.yaml（narrows の行）
  - 証: tests/workflows/test_plan_review.py::YamlCase.test_role_formats_are_mainline_plus_marks（assert: tests/workflows/test_plan_review.py:378）・tests/workflows/test_plan.py::ShapeCase.test_role_schemas_match_their_lib_owners（assert: tests/workflows/test_plan.py:396-397）。元 works/tests/test_gate_drafts.py:33 SchemaCase.test_gate_rows_have_the_recommend_field の「recommend は required に入れない」は見ない → 要追加: tests/workflows/test_plan_review.py::YamlCase.test_recommend_is_optional_on_both_roles — faces の行と narrows の行の required に recommend が無いこと
  - 本物の run: 節 `plan-review` の出力が型を通った記録、`plan-review/gate-marks.json`
  - 狭め: 無し

- P219 修正案と事前審査の役の頭に関所の決め手の頼み（gatemarks.HEAD）を貼る: 決め手の出どころの書き方・世界の解の行を使え・依頼が示した解き方は決め手にならない・推し recommend の書き方
  - 元: works/.shared/core/gatemarks.py:162 `HEAD`
  - 今: lib/gatemarks.py:160 `HEAD`
  - 証: tests/workflows/test_plan_review.py::PlanGateCase.test_rule_points_at_world_rows（assert: tests/workflows/test_plan_review.py:1765-1767）・lib/tests/test_gate_drafts.py::SchemaCase.test_rule_text_asks_for_recommend。材料に貼られることは PD と PA の行が持つ
  - 本物の run: `plan-review/pass-1/prompt.md` と `plan/r1/brief-1.md` に「関所の項目の決め手」の段落
  - 狭め: 無し

- P220 受け付けは返答から決め手の欄を外して控え gate-marks.json に置き、後段へは欄の無い形で渡す（推しも同じ道）
  - 元: works/.shared/core/gatemarks.py:388 `split`・:397 `save`
  - 今: lib/gatemarks.py:373 `split`・:382 `save`・lib/boardview.py:439-440（修正案の側）・:862-864（事前審査の側）
  - 証: lib/tests/test_gate_drafts.py::GapsCase.test_split_takes_recommend_off_and_save_keeps_it
  - 本物の run: `plan-review/gate-marks.json`
  - 狭め: 無し

- P221 推し recommend {answer: continue|stop, note, why} の形が崩れた返答は、受け付けがまとめて理由を言って拒む
  - 元: works/.shared/core/gatemarks.py:366 `recommend_gaps`
  - 今: lib/gatemarks.py:351 `recommend_gaps`・lib/boardview.py:836-838（RECOMMEND_REJECT）
  - 証: lib/tests/test_gate_drafts.py::GapsCase.test_malformed_recommend_is_named・test_review_faces_are_checked_too・tests/workflows/test_plan_review.py::ReviewAcceptCase.test_malformed_recommend_rejected
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P222 関所の決め手の濾しに掛ける行は、修正案の narrows の全部と、事前審査の穴のうち人に聞く種類（HUMAN_FACE_KINDS＝regression・policy）だけ。ほかの種類の穴（contract_drift など）は関所に載せない
  - 元: works/.shared/core/graphloops/rules/review-loop.py:4093 `_plan_gate_items`・:4084 `HUMAN_FACE_KINDS`・works/.shared/core/gatemarks.py:466 `_gate_rows`
  - 今: lib/gatemarks.py:451 `_gate_rows`・lib/boardview.py:143 `HUMAN_FACE_KINDS`
  - 証: tests/workflows/test_plan_review.py::PlanGateCase.test_decided_regression_face_passes・ConvergeCase.test_first_block_is_not_stalled（assert: tests/workflows/test_plan_review.py:870）・YamlCase.test_role_formats_are_mainline_plus_marks（assert: :383 の種類の部分集合）。弱い: 形 review で人に聞かない種類の block の穴が questions に載らないことを見ない → 要追加: tests/workflows/test_plan_review.py::GateFromPlanCase.test_non_human_face_kinds_are_not_asked — contract_drift の block の穴だけの返答で ask_human が偽・questions が空
  - 本物の run: `plan-review/pass-1/gate.json` の `items`（種の直しで regression の穴が無ければ空）
  - 狭め: 無し

- P223 決め手の揃った行（decided_by が在り undecided_because が空で fences が無く、4 つの軸が揃う）は人に聞かずに通し、出どころつきの「通した行」に残す（node・by: decided・item・decided_by）。返す節は pass-<k>/gate-passes.json に書き、報告がそれを読む
  - 元: works/.shared/core/gatemarks.py:625 `plan_gate_items`・:1239 `_record`・:1286 `passes`
  - 今: lib/gatemarks.py:610 `plan_gate_items`・:1224 `_record`・lib/boardview.py:950（PASSES_FILE）・lib/runreport.py:603（隣の gate-passes.json を読む）
  - 証: tests/workflows/test_plan_review.py::PlanGateCase.test_decided_narrow_passes_and_is_recorded（assert: tests/workflows/test_plan_review.py:1726-1729）・GateFromPlanCase.test_decided_narrow_passes_and_undecided_asks（assert: :1382-1385、ブロックを通して gate-passes.json を読む）・lib/tests/test_runreport.py::…test_gate_passes_follow_decisions
  - 本物の run: `plan-review/pass-1/gate-passes.json`（種では `[]` の見込み）と報告の「修正前の関所が聞かずに通した行（plan-review）: N 件」
  - 狭め: 無し

- P224 柵の印（external_write・irreversible・policy_doc・widen_protection・web_doubt）の在る行は、決め手が在っても聞く
  - 元: works/.shared/core/gatemarks.py:112 `FENCES`・`decided`
  - 今: lib/gatemarks.py:110 `FENCES`・:415 `decided`
  - 証: tests/workflows/test_plan_review.py::PlanGateCase.test_fenced_narrow_asks_even_if_decided（assert: :1741）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P225 undecided_because の在る行・決め手の欄の無い行は聞く。決め手の在る行と欄の無い行が並べば欄の無い行だけを聞き、在る行は通した行に残す
  - 元: works/.shared/core/gatemarks.py:625 `plan_gate_items`
  - 今: lib/gatemarks.py:610 `plan_gate_items`
  - 証: tests/workflows/test_plan_review.py::PlanGateCase.test_undecided_narrow_asks（assert: :1746）・test_mixed_rows_ask_only_the_undecided（assert: :1773-1776）・GateFromPlanCase（assert: :1389-1391）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P226 人に回す行の尾: 役が書いた世界の解の 1 文（書いていなければ「役が書いていない」、欄の無い行には付けない）・狭めない案の 1 文（no_narrow を書いた行だけ）・揃わない軸の訳「（人に聞く訳: …）」（決め手を書いた行だけ）
  - 元: works/.shared/core/gatemarks.py:436 `_world`・:444 `_no_narrow`・`_item`
  - 今: lib/gatemarks.py:421 `_world`・:429 `_no_narrow`・:469 `_item`
  - 証: tests/workflows/test_plan_review.py::PlanGateCase.test_asked_row_shows_what_the_world_does（assert: :1754-1758）・FourAxesCase.test_no_world_asks。狭めない案の尾は 要追加: tests/workflows/test_plan_review.py::PlanGateCase.test_asked_row_shows_the_no_narrow — no_narrow を書いた聞く行の項目に「（狭めない案: …）」が付き、書いていない行には付かない（関所の項目の側で縛る試験が無い。報告の下書きの側は lib/tests/test_runreport.py:403 だけ）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P227 人に回す行の尾の推し「／推し: 通す（continue）——<note>（理由: <why>）」。推しの文の「／」は「・」に替えて尾を 1 つの区切りで終える。推しの無い行は尾を付けない。関所の文の冒頭 3 行の推しに出す
  - 元: works/.shared/core/gatemarks.py:456 `_push`・`push_of`
  - 今: lib/gatemarks.py:441 `_push`・:279 `push_of`
  - 証: tests/workflows/test_plan_review.py::PushCase の 3 件（assert: :2553・:2563-2564・:2569）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し

- P228 軸「自明」: 決め手の出どころ（URL・<パス>:<行>・依頼の引用「…」・設計の決定の記録のパス）が現物に在る。依頼の引用は依頼の文（JSON の逃がしを解いた字も）と照らし、時刻やディレクトリの字は出どころに数えず、絶対パスの依頼の引用も読む
  - 元: works/.shared/core/gatemarks.py:528 `_cite_check`・:576 `axes`
  - 今: lib/gatemarks.py:513 `_cite_check`・:561 `axes`・lib/gate_axes.py:31 `_reasons`
  - 証: tests/workflows/test_plan_review.py::FourAxesCase.test_decided_by_must_exist・test_decided_by_url_passes・test_decided_by_file_line_passes・test_request_quote_must_be_in_request・test_sources_ignore_times_and_dirs_and_take_absolute_request_cites・lib/tests/test_gate_axes.py::SplitCase.test_decided_by_must_exist（assert: lib/tests/test_gate_axes.py:72-74）
  - 本物の run: 返す節 `review` の出力 `gate_axes.obvious`（種では `{ok: true}` の見込み）
  - 狭め: 無し

- P229 軸「世界の解」: 世界の解の段の行が在る run はこの軸で見ない（外れは P233 の項目が聞く）。行の無い run は world の 1 文か URL の決め手が要る
  - 元: works/.shared/core/gatemarks.py:576 `axes`
  - 今: lib/gatemarks.py:561 `axes`・lib/gate_axes.py:40-42・lib/boardview.py:578 `_copy_world`（world が null なら控えを消して今どおりの軸に戻す）
  - 証: tests/workflows/test_plan_review.py::FourAxesCase.test_no_world_asks・lib/tests/test_gate_axes.py::SplitCase.test_no_world_is_not_world・test_world_rows_take_the_axis_off_the_row（assert: lib/tests/test_gate_axes.py:110）
  - 本物の run: `plan-review/world-state.json` の在る無しと `gate_axes.world`
  - 狭め: 無し

- P230 軸「汚くない」: 行の単位に構造の目が人に上げた行が無く、構造の目が汚れると見た単位には修正案の欄 structure の答えが在る（控えが読めなければ照らさない）
  - 元: works/.shared/core/gatemarks.py:576 `axes`・`_answered_rows`
  - 今: lib/gatemarks.py:561 `axes`・:550 `_answered_rows`・lib/gate_axes.py:43-51・lib/boardview.py:590 `_copy_structure`
  - 証: tests/workflows/test_plan_review.py::FourAxesCase.test_clean_route_rows_do_not_block・lib/tests/test_gate_axes.py::SplitCase.test_route_up_unit_is_not_clean・test_dirty_unit_without_answer_is_not_clean（assert: lib/tests/test_gate_axes.py:130-134）
  - 本物の run: `gate_axes.clean`、`plan-review/structure/design.jsonl`（計画の design.jsonl の写し）
  - 狭め: 無し

- P231 軸「やりすぎでない」: 柵の印が無く、行が修正案の単位の外を名指さない
  - 元: works/.shared/core/gatemarks.py:576 `axes`
  - 今: lib/gatemarks.py:561 `axes`・lib/gate_axes.py:38-39・:52-54
  - 証: tests/workflows/test_plan_review.py::FourAxesCase.test_face_outside_plan_units_asks・lib/tests/test_gate_axes.py::SplitCase.test_fences_are_overkill・test_face_outside_plan_units_is_overkill
  - 本物の run: `gate_axes.not_overkill`
  - 狭め: 無し

- P232 4 つの軸を軸ごとの {ok, note} に分けて返す（返す節の gate_axes）。軸の決まりは gatemarks.axes と gate_axes._reasons の 2 か所が持つが、「全部の軸が ok ⇔ gatemarks.axes が空」と「全部の軸が ok ⇔ 関所の項目が無い」を試験が縛る。項目の無い軸は {ok: true, note: ""}、note は行の頭と訳
  - 元: works/.shared/core/gatemarks.py:576 `axes`（訳を 1 つの並びで返した。軸ごとの分けは元に無い）
  - 今: lib/gate_axes.py:56 `split`・:61 `gather`・lib/boardview.py:954
  - 証: lib/tests/test_gate_axes.py::AxesBase（assert: lib/tests/test_gate_axes.py:46 の全部 ok ⇔ axes が空）・GatherCase.test_gather_agrees_with_the_gate（assert: :183）・test_no_rows_is_all_ok・test_rows_name_their_text
  - 本物の run: 返す節 `review` の出力 `gate_axes`（4 つの鍵、種では全部 ok の見込み）
  - 狭め: 無し（決まりを 2 か所が持つのは #73 の申し送り。今壊れていない。gatemarks に軸ごとの訳の口を足せば 1 か所になる）

- P233 世界の解の外れ: 修正案の欄 structure の世界の解の答えのうち、従う行は聞かずに通し、外れは worldmark.world_ok が揃わなければ種類 world の関所の項目に 1 度だけ載せる（同じ外れを狭めの尾に重ねない）。依頼そのものを出どころにした外れ・web で確かめていない行からの外れは人に回す。知識の行も名指す。人が continue で答えた同じ文は聞き直さない
  - 元: works/.shared/core/gatemarks.py:546 `world_items`・:625 `plan_gate_items`
  - 今: lib/gatemarks.py:531 `world_items`・:616-619
  - 証: tests/workflows/test_plan_review.py::WorldGateCase の 6 件（元と同じ断言）
  - 本物の run: 筋書きでのみ（種の直しは定石から外れない見込み）。外れが出れば `plan-review/pass-1/gate.json` の kind world の行
  - 狭め: 無し（lib の水準。「continue で答えた行を聞き直さない」が run で効くかは P244 の配線の穴に依る）

- P234 構造の目が人に上げた行（route が人に上げる）は、種類 design の関所の項目（DESIGN_HEAD で始まり、決まらない訳・捨てた案と代償・推し＝chosen）になり、その単位の決め手の行は聞かずに通さない。無人の run でも同じ
  - 元: works/.shared/core/gatemarks.py:604 `design_items`
  - 今: lib/gatemarks.py:589 `design_items`
  - 証: tests/workflows/test_plan_review.py::FourAxesCase.test_eye_route_up_becomes_gate_item（assert: tests/workflows/test_plan_review.py:1830-1840）・lib/tests/test_gate_axes.py::GatherCase.test_world_deviation_and_route_up_rows
  - 本物の run: 筋書きでのみ（P080 と同じく種では上げない見込み）
  - 狭め: 無し

- P235 問いの台帳のうち人に聞く状態（held・escalate）の fork と、status が escalate の問いを、関所の項目に 1 件 1 行で載せる（問い・選択肢・推し〔無ければ「判定の役が書いていない」〕・答えが無いと直さない単位）。決着済みの問い・fork でない held の問いは載せない。この行は決め手の濾しに掛けない
  - 元: works/.shared/core/gatemarks.py:674 `asks`・:693 `ask_text`
  - 今: lib/gatemarks.py:659 `asks`・:678 `ask_text`・lib/boardview.py:223 `ASKING`
  - 証: tests/workflows/test_plan_review.py::LedgerAsksCase.test_held_fork_is_asked_with_options_and_recommendation・test_recommendation_missing_is_said・test_decided_or_non_fork_held_question_is_not_asked・test_escalate_is_asked（元と同じ断言）
  - 本物の run: 判定が fork を立てた時だけ `plan-review/pass-1/gate.json` に「問いの台帳の問い」の行（種では筋書きでのみ）
  - 狭め: 無し

- P236 無人の run では台帳の問いの行を関所に載せない（問いだけで関所を開かず、修正を飛ばさない）。狭めの在る関所は今どおり開く
  - 元: works/.shared/core/gatemarks.py:625 `plan_gate_items`（gatepolicy.unattended）
  - 今: lib/gatemarks.py:620-621・lib/boardview.py:403-404（始めの記録を置き場に写すので無人の印が届く）
  - 証: tests/workflows/test_plan_review.py::LedgerAsksCase.test_unattended_run_does_not_open_the_gate_for_questions_only（assert: :2143-2145）。弱い: 元の「出どころは直す義務から外したまま・ほかの単位は残る」（owed の数え）と「報告の冒頭に答えの無い問いが並ぶ」の断言を落とした（#73）。報告の側は lib/tests/test_runreport.py::LedgerCase.test_held_line_names_units_left_and_answer_key が保留の行を見る。義務の数えは P241 の穴
  - 本物の run: 筋書きでのみ
  - 狭め: #73 で試験の断言を外した（Archon で不可でない → P241 の試験で戻す）

- P237 一言の「保留: <key>」で名指した問いは答えに数えない。key は台帳の key を最長一致で拾い、key の後ろの言葉・区切りの字を含む key・並べた複数の key も読む。前後が key の字で続く一致は拾わない
  - 元: works/.shared/core/gatemarks.py:1118 `hold_keys`・`_hold_scan`・:1070 `answered`
  - 今: lib/gatemarks.py:1103 `hold_keys`・:1109 `_hold_scan`・:1055 `answered`
  - 証: tests/workflows/test_plan_review.py::LedgerAsksCase.test_hold_note_keeps_the_fork_origin_exempt（assert: :1996-1998）・test_hold_note_names_only_the_whole_key・test_hold_note_lists_several_keys・test_hold_note_with_words_after_the_key_keeps_the_fork_origin_exempt・test_hold_note_names_a_key_that_holds_a_separator・EscalateAsksCase.test_hold_note_keeps_the_escalate_origin_exempt。断言は owed の数えから withheld・returned・answered に替わったが、lib の決まりは縛る
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（lib の水準。run で効くかは P241 の配線の穴に依る）

- P238 key を拾えなかった「保留」の文と並べ書きの打ち間違いの key を「読めなかった保留: …（答えたものとして推しで直す問い: …）」の行にして、報告の冒頭と最後の関所の文に並べる（直す義務は変えない）
  - 元: works/.shared/core/gatemarks.py:1101 `unread_hold_lines`（報告の冒頭 1 と line_edge の最後の関所の文が読んだ）
  - 今: lib/gatemarks.py:1086 `unread_hold_lines`（関数は在る）。読む側は 無し（lib/runreport.py の ledger_state にも #74 の head の workflows/line/scripts/ask_final.py にも無い）
  - 証: tests/workflows/test_plan_review.py::LedgerAsksCase.test_unread_hold_is_shown_to_the_human・test_unread_hold_beside_a_read_key_is_shown（lib の行の在ることだけ。見せる側は縛らない）→ 要追加: lib/tests/test_runreport.py::LedgerCase.test_unread_hold_is_named_in_the_head — 修正前の関所の答えの文が「保留: q-typo」の時、報告の冒頭に「読めなかった保留」の行が在ること（最後の関所の側は #74 の head の tests/workflows/test_line.py に同じ形の 1 本）
  - 本物の run: 筋書きでのみ
  - 狭め: #73 が報告・線へ渡したが、渡し先（#68・#74）が持っていない。Archon で不可でない → 戻す

- P239 関所で答えた fork・escalate の問いの出どころ・depends（今の周の units に在る物だけ）は直す義務に戻り、修正役への約束の行（returned_lines）に載る。開いていない単位（suggest の defer）でも戻す。今の周の units に無い出どころは約束しない（戻せなかった単位の行に回す）。stop や別の関所の答えでは戻さない
  - 元: works/.shared/core/gatemarks.py:1172 `returned`・:1178 `returned_lines`・`unreturned_lines`
  - 今: lib/gatemarks.py `returned`・`returned_lines`・`unreturned_lines`（字のまま）・lib/fixboard.py:1849 `write_notes`（修正の側が約束の行を書く）
  - 証: tests/workflows/test_plan_review.py::LedgerAsksCase.test_continue_returns_the_fork_origin_to_the_owed_units（assert: :2067-2068）・test_continue_returns_a_deferred_origin_the_fixer_was_promised・test_origin_missing_from_the_round_units_is_not_promised・test_stop_or_another_gate_does_not_return_the_origin（assert: :2026）・EscalateAsksCase.test_continue_returns_the_escalate_origin
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（lib の水準。run で効くかは P241）

- P240 escalate の問いも fork と同じ 1 つの決まりで、答える前は出どころを直す義務から外し、無人の run でも外し、保留の問いと答えた問いが同じ出どころを持てば戻した単位を保留の行の「答えが無いと直さない単位」に並べない。関所の項目が名指す単位・外れる単位・戻る単位が同じ
  - 元: works/.shared/core/gatemarks.py:1154 `withheld_by`・`withheld`・:1216 `held_lines`
  - 今: lib/gatemarks.py:1139 `withheld_by`・:1151 `withheld`・`held_lines`
  - 証: tests/workflows/test_plan_review.py::EscalateAsksCase の 7 件。弱い: test_gate_item_exemption_and_return_name_the_same_units は「外れる単位」の突き合わせを落とした（assert: :2211 は named と returned だけ。元 works/tests/test_plan_gate.py:602 は exempt も縛った）→ 要追加: 同じ試験に `gatemarks.withheld(b)` を答える前に取り `{FORK_UNIT}` と等しいことを戻す
  - 本物の run: 筋書きでのみ
  - 狭め: #73 で断言を外した（Archon で不可でない → 戻す）

- P241 直す義務の数え（開いた単位 − 答えの無い問いの出どころ・depends ＋ 関所で答えた問いの出どころ・depends − 直さない裁定の単位）が、関所の continue を受けると戻る
  - 元: works/.shared/core/conflict.py:676 `owed_units_but_asked`（entry.CORE_OVERRIDES）が gatemarks.withheld・returned を読む・works/tests/test_plan_gate.py:340 `owed` を使う断言 15 か所
  - 今: lib/fixboard.py:79 `owed_units_but_asked`・:1826 `gate_view`・:1841 `gate_asks`・:1861 `gate_items`（修正の置き場の answers.json の `asked` で人が見た行を引く）。線は workflows/line/scripts/gate_answer.py:24-27 で答えを `{decision, text}` だけにし `asked` を渡さない（workflows/line/works-factory-line.yaml:325-343 の answer-before-fix）。そのため gatemarks._asked_in が偽になり、continue を受けても returned が空のまま、fork・escalate の出どころは直す義務から外れたまま
  - 証: 無し（owed の断言は #73 で全部外れ、lib/tests/test_fix_seams.py::…test_withheld_and_returned_are_arguments は値を引数で渡すだけ。gate_view・gate_asks を通す試験が無い）→ 要追加: lib/tests/test_fix_seams.py::GateAsksCase.test_continue_returns_the_fork_origin — 判定の写しに held の fork、answers.json に `{decision: "approve", text: "", asked: [gatemarks.ask_text(FORK)]}` で gate_asks の returned が `{FORK_UNIT}`・withheld_by が空。あわせて #74 の head の tests/workflows/test_line.py::GateAnswerCase.test_before_fix_answer_carries_the_asked_items — answer-before-fix の答えが関所に載せた項目の文を `asked` に持つ
  - 本物の run: 筋書きでのみ（種の判定は fork を立てない見込み）
  - 狭め: #73 が修正のブロックへ渡したが、線が `asked` を運ばず今の main と #74 の組で能力が落ちている（今壊れている。fork のある run で人が continue しても出どころが直されない）。Archon で不可でない（関所の前の節が項目の文を出し、返しの節がそれを答えに足せば済む）→ 戻す

- P242 依頼の answers（始めの記録の欄）が問いの key か出どころ origin と字のまま等しく、その問いだけに当たる時は答えた扱い（関所を飛ばし、出どころを直す義務に戻す、答えの文で直させる）。命令と出力つきの答えはそれを見せる。どの問いにも当たらない・複数の問いに当たる・決着済みの問いに当たる答えは答えた扱いにせず名指す。判定の answer_ties が問いの key・単位・none に結ぶ
  - 元: works/.shared/core/gatemarks.py:923 `request_answer`・:731 `answer_binds`・:1036 `unmatched_answer_lines`
  - 今: lib/gatemarks.py:908 `request_answer`・:716 `answer_binds`・:1021 `unmatched_answer_lines`・lib/boardview.py:403-404（始めの記録の写しから読む）
  - 証: tests/workflows/test_plan_review.py::RequestAnswersCase の 9 件。名指しの文（「依頼の答えに当たる問いが台帳に無い」「複数の問いに当たった」「決着済みの問いに当たった答え」・ANSWERED_HEAD）の断言は外れ、lib/tests/test_runreport.py::LedgerCase.test_answers_that_answer_nothing_are_named・test_answered_lines_name_where_the_answer_came_from が報告の側で持つ（報告は gatemarks を呼ばず書き直した写し lib/runreport.py:228 `ledger_state`）
  - 本物の run: 筋書きでのみ（種の request_ok.json は answers を持たない）
  - 狭め: 無し（報告の側の写しは字の一致だけで answer_ties の結びを読まない、と lib/runreport.py:234 が自ら書く。報告の区分の行）

- P243 素材の名で答えた依頼の答え: field の問いは素材の名で答えられ、key の頭の一致は語の境と測れていない素材を要し、問いの無い素材への答えは名指しの対象にしない。命令と出力つきの答えは素材を「人が手元で確かめた」と閉じ、複数の問いに当たれば閉じない。測れている素材への答えは名指す
  - 元: works/.shared/core/gatemarks.py:893 `material_answer`・:901 `measured_materials`・`origin_of`
  - 今: lib/gatemarks.py:878・:886・:704
  - 証: tests/workflows/test_plan_review.py::MaterialAnswersCase の 6 件・lib/tests/test_runreport.py::LedgerCase.test_material_answer_lines（文の側）。元 works/tests/test_plan_gate.py:1081 test_material_row_matches_the_validator（報告の素材の行の頭と写しの検証器の字の照らし）は 無し → 要追加: lib/tests/test_runreport.py::MaterialRowCase.test_material_row_matches_the_judge_words — 報告が素材の行を見分ける字と判定の素材の行の字が揃うこと（報告の区分）
  - 本物の run: 筋書きでのみ
  - 狭め: #73 が報告へ渡した照らしが報告に無い（Archon で不可でない → 報告の区分で戻す）

- P244 修正前の関所の答え（入力 gate_answers {decision, text, asked}）を gatemarks が読む human_items の行に積み（approve は continue に揃え、同じ行は積み増さない、種類は前の差し込みが返した項目の控え gate-asked.json から引く）、人が continue で通した行（狭め・穴・世界の解の外れ・構造の設計の問い・設計だけの行・止まりの行・台帳の問い）を次の差し込みで聞き直さない
  - 元: works/.shared/core/graphloops/rules/review-loop.py:4134 `human_gate_answered`（盤面の record.process.human_items に積んだ）
  - 今: lib/boardview.py の take_gate_answers・_note_asked・workflows/plan-review/scripts/pass_open.py（入力 gate_answers）。線の replan-review の with: に gate_answers: $answer-before-fix.output.answer
  - 証: lib/tests/test_boardview.py::GateAnswersCase.test_continued_rows_are_not_asked_again・tests/workflows/test_plan_review.py::PortedMaterialCase.test_gate_answers_reach_the_lib_through_the_open_script・tests/workflows/test_line.py::LineWiringCase.test_replan_review_gets_the_before_fix_answer（部分 B1。旧 WiringCase.…）
  - 本物の run: `plan-review/gate-answers.json`（今の線では書かれない。直れば案の直しの run で見える）
  - 狭め: #73 は入力を足したが、#74 の線が渡さない。今の線で同じ run の 2 度目の差し込みは案の直しの事前審査だけで、そこでは方針の変化の行を聞き直す（P246）。Archon で不可でない → 線に配線する → 部分 B1 で配線を縛った

- P245 返した関所の項目の種類と方針の変化を gate-asked.json に積み、関所の項目の全部と壁打ちの行を pass-<k>/gate.json に残す（次の差し込みが通した行の種類を引く・人が読む控え）
  - 元: 盤面の state.pending_human（{node, kinds, items}）と loop_state.policy_change
  - 今: lib/boardview.py:912 `_note_asked`・:951（GATE_FILE）
  - 証: 要追加: tests/workflows/test_plan_review.py::ResultCase.test_gate_files_carry_kinds_and_items — 狭め 1 件と方針の変化 1 件の差し込みの後、gate.json の items が `[{kind: "regression", …}, {kind: "policy_changed", …}]` で、gate-asked.json が 2 つの文を種類つきで持ち、方針の行だけ policy_change を持つ（今は lib の試験が `_note_asked` を直に呼ぶだけで、collect が書くことを見ない）
  - 本物の run: `plan-review/pass-1/gate.json`・`plan-review/gate-asked.json`
  - 狭め: 無し

- P246 方針の文書が固めた版から変わった事実を種類 policy_changed の関所の行にする（差分のファイルと前後の版の写しの置き場だけを載せ、本文は載せない。固めた版の写しが消えていれば差分を作らず名指す）。人が continue で通せば、その版を固め直して amendments に一言つきで残す（stop では固め直さない）
  - 元: works/.shared/core/graphloops/rules/review-loop.py:4116 `human_gate`（policy_input.change・change_row）・:4134-4142 `human_gate_answered`
  - 今: lib/boardview.py:543 `policy_change`・:570 `change_row`・:943-945（collect が行を足す）・:332-358 `take_gate_answers`（固め直し）
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_policy_change_asks（assert: :784-785）・lib/tests/test_boardview.py::GateAnswersCase.test_continue_past_policy_change_refreezes（assert: lib/tests/test_boardview.py:333-338）・diff_missing の試験（assert: :301-302）。方針の固め方そのもの（最初の差し込みで固める・既定の置き場）は PD の行
  - 本物の run: `plan-review/policy.json`（種は方針の文書が無いので sha256 が null）
  - 狭め: 固め直しは P244 の配線の穴で run では起きない。元は固め直しで後段の役が読む方針の文書のパス（state.inputs.policy_md）も替えた。今は plan-review の置き場の中だけ（後段へ届かない）。Archon で不可でない → 線に配線して固めた版を後段へ渡す

- P247 設計だけの run（始めの記録の design_only）は項目の有無に関わらず関所を設計だけの行で開け、無人の run でも開け、その行の全文に continue を受けた後は 2 度聞かない
  - 元: works/.shared/core/gatemarks.py:649 `design_item`・`_design_only_answered`
  - 今: lib/gatemarks.py:634 `design_item`・:643 `_design_only_answered`・lib/boardview.py:403-404（始めの記録の写し）
  - 証: tests/workflows/test_plan_review.py::DesignOnlyCase の 2 件（assert: :2226-2234・:2243-2244）
  - 本物の run: 筋書きでのみ（種の run は設計だけでない）
  - 狭め: 無し（線との継ぎ目の重なりは P249）

- P248 事前審査の壁打ちが止まった（persisted・unsettled）案は、修正に進まない行で関所を開け、尾に止まった理由（converge.stuck_reason）を付け、設計だけの run と名乗らない。設計だけの run と重なっても行は 1 つ。無人の run でも載る。同じ理由に continue を受けたら 2 度聞かず、理由が変われば聞き直す
  - 元: works/.shared/core/gatemarks.py:649 `design_item`
  - 今: lib/gatemarks.py:634 `design_item`・lib/boardview.py:937-939（stalled）
  - 証: tests/workflows/test_plan_review.py::ConvergeGateCase の 6 件・ConvergeCase.test_same_block_again_stalls_with_a_design_item（assert: :878-881、ブロックを通して questions に止まりの行）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し（線との継ぎ目の重なりは P249）

- P249 関所に載る行は 1 件 1 行で重ならない（設計だけの行と止まりの行は 1 行、決め手の揃わない行の訳は行の尾に 1 度）
  - 元: works/.shared/core/graphloops/rules/review-loop.py:4116 `human_gate`（plan_gate_items の行をそのまま項目にした）
  - 今: workflows/line/scripts/ask_before_fix.py:37-51 が plan-review の questions（gatemarks の設計だけの行・止まりの行を既に含む）に、自分で STUCK_ITEM・DESIGN_ONLY_ITEM の行と、軸ごとの「…の軸が通らない: <行の頭>: <訳>」の行を足す。設計だけの run と止まりの案は同じ事実が 2〜3 行、決め手の揃わない狭めは項目の行と軸の行の 2 回並ぶ
  - 証: 要追加: tests/workflows/test_line.py::AskBeforeFixCase.test_plan_review_rows_are_not_repeated — questions に `gatemarks.STUCK_ITEM + "。理由: x"` と design_only が在る時、関所の文の項目に止まり・設計だけの行が 1 行だけ（元 ConvergeGateCase.test_design_only_and_stuck_give_one_line の線の側）
  - 本物の run: 筋書きでのみ
  - 狭め: #74（線）で重なった。Archon で不可でない → 線は plan-review が出した行を足し直さない

- P250 関所の項目の種類（regression・policy・policy_changed・fork・escalate・world・design・design_only）を関所の文の冒頭（何の項目が何件か）・台帳の問いへの答え方の段落（ASK_GATE_HEAD）・無人の run の振る舞いに使う
  - 元: works/.shared/core/graphloops/rules/review-loop.py:4122-4124（ask.kinds）・works/.shared/core/gatemarks.py:301 `gate_text`（KIND_WORDS・ASK_GATE_HEAD は kinds に fork・escalate が在る時だけ）
  - 今: plan-review の返りの questions は文の並びだけで種類を落とす（workflows/plan-review/works-factory-plan-review.yaml の返す節 review の output_format・lib/boardview.py:946）。種類は置き場の pass-<k>/gate.json に在るが、線は読まず、#74 の head/workflows/line/scripts/ask_before_fix.py:43 が全部の問いを fork として並べる。その結果、狭め・方針の変化の行にも「判定の役が人に聞くと保留にした問い（fork）」の頭と ASK_GATE_HEAD が付く。無人の run では :42 が questions を全部「報告へ回す台帳の問い」として退け、関所を開かずに修正へ進む（台帳の問いは plan-review が無人の run では既に外しているので、ここで退くのは方針の変化の行などの人が決める行。元は無人の殻が関所で stop を返した）
  - 証: 要追加: tests/workflows/test_plan_review.py::ResultCase.test_questions_carry_their_kinds（約束を変えるなら返りに種類を足す）か、#74 の head/tests/workflows/test_line.py::AskBeforeFixCase.test_kinds_come_from_the_gate_record — 方針の変化の行だけの返りで、関所の文の冒頭が「人の方針の文書が変わった（policy_changed）」を名乗り ASK_GATE_HEAD を含まない。無人の run で方針の変化の行が在れば stop_reason が needs-human
  - 本物の run: 線の節 `ask-before-fix` の出力 `text` の 1 行目
  - 狭め: #73 の返りの約束（questions は字の並び）と #74 の線の読みの組で狭めた（Archon で不可でない: 返りに kinds を足すか、線が隣の gate.json を読めば済む）→ 戻す。持ち主に「返りの約束に種類を足すか」を聞く

- P251 関所の文: 冒頭 3 行（起きたこと・決めてほしいこと・推し）を平易な名で書き、内部の名は括弧に回し、問いの文を引用（> の行）で載せ読み替えの 1 行を添え、答え方の continue は 1 通りだけ
  - 元: works/.shared/core/gatemarks.py:301 `gate_text`・works/darkfactory/lib/line_edge.py `gate_text`
  - 今: lib/gatemarks.py:286 `gate_text`・#74 の head/workflows/line/scripts/ask_before_fix.py:57 `gate_text`（線の持ち物）
  - 証: tests/workflows/test_plan_review.py::PlainSubjectCase.test_plan_gate_text_subjects_are_plain・QuotedQuestionCase.test_plan_gate_quotes_mainline_question（lib の水準）・#74 の head の tests/workflows/test_gate_head.py（線の水準）
  - 本物の run: 線の節 `ask-before-fix` の出力 `text`（種では関所が開かない見込み。最後の関所は常に開く）
  - 狭め: 元の問いの文（「役は代償として決めない——人が決める…方針の文書の変更を通すと、その版を固定し直す…stop は直す向きを決めてから新しい run で」）は、線の QUESTION（workflows/line/scripts/ask_before_fix.py:24）の短い文に替わった。線の区分の行として持ち主に渡す

- P252 返す節の関所の材料: gate_axes（4 つの鍵）・ask_human（questions が 1 つ以上）・questions（関所の項目の文。受け付けが諦めた往復は諦めた訳を足す）を、どんな誤りでも約束の形で返す（入力が読めない・open が落ちた・置き場が空なら、全部の軸を ok: false、ask_human: true、訳を名指す questions）
  - 元: works/.shared/core/graphloops/rules/review-loop.py:4116 `human_gate`（盤面の節。落ちれば盤面が止まった）
  - 今: lib/boardview.py:919 `collect`・workflows/plan-review/scripts/result.py
  - 証: tests/workflows/test_plan_review.py::ResultCase の 5 件（assert: :1425-1427・:1438-1439・:1447-1448）・ReviewAcceptCase（assert: :720-721 の GIVEN_UP_FACES）
  - 本物の run: 返す節 `review` の出力 `gate_axes`・`ask_human`・`questions`（種では ask_human: false・questions: [] の見込み）
  - 狭め: 無し

- P253 関所の材料は修正の義務が在る周だけに作る（直す義務が 0 件・計画が無い周は関所を開かず修正もしない）
  - 元: works/.shared/core/gatemarks.py 冒頭（直す義務が 0 件の周は関所の節が走らない）
  - 今: workflows/line/works-factory-line.yaml:203-206（plan-review は plan の ready でだけ走る）・#74 の head/workflows/line/scripts/ask_before_fix.py:33-34
  - 証: tests/workflows/test_line.py::AskBeforeFixCase.test_no_plan_goes_nowhere
  - 本物の run: 線の節 `ask-before-fix` の出力 `open`・`go`
  - 狭め: 無し

- P254 修正前の関所で人が通した狭め・穴と同じ行は、修正の後の関所（R4）で聞き直さず、通した行に by human で残す。R4 の役にも「人が通した狭まり」の節を貼る
  - 元: works/.shared/core/gatemarks.py `r4_gate_items`・`_human_passed`・`carried_section`
  - 今: lib/eyeverdict.py:145 `r4_gate_items`・`_human_passed`（eyes の持ち物。plan-review の questions と線の answer-before-fix の答えを読む）
  - 証: lib/tests/test_eyeverdict.py::R4GateCase の 2 件・R4PushTailCase（eyes の区分。ここは参照だけ）
  - 本物の run: eyes の区分
  - 狭め: 無し（eyes の区分の行）

- P255 最後の関所の文と報告の冒頭に、関所で答えていない台帳の問い（fork でない awaiting も）を「無い」と書かずに並べ、関所で答えた問いは保留の件数に数えず答えた行に並べ、決め手で通した行も並べる
  - 元: works/.shared/core/gatemarks.py:1216 `held_lines`・`answered_lines`・:1298 `lines`（line_edge._final_text と report.head_decisions が読んだ）
  - 今: lib/runreport.py:228 `ledger_state`・:600-612（通した行）・#74 の head/workflows/line/scripts/ask_final.py:134（保留の問い）。最後の関所の文に決め手で通した行（gatemarks.lines）は 無し
  - 証: lib/tests/test_runreport.py::LedgerCase の 6 件・test_gate_passes_follow_decisions・#74 の head/tests/workflows/test_line.py::…test_held_questions_are_every_asking_question_not_answered。最後の関所の通した行は 要追加: tests/workflows/test_line.py::AskFinalCase.test_final_gate_lists_gate_passes — plan-review の隣の gate-passes.json に 1 行在る時、最後の関所の文にその行が在ること（元 works/tests/test_plan_gate.py:397・:515・:575 の final_text の断言）
  - 本物の run: 最後の関所の文（種では常に開く）と報告の冒頭
  - 狭め: #73 が報告・線へ渡し、報告は持つが線の最後の関所は通した行を持たない（Archon で不可でない → 線の区分で戻す）

- P256 無人の run で関所に止まった項目と保留の台帳の問い・問いの無い測れていない素材に、答えの下書き（draft: true・出どころつき）を作り、次の依頼の answers に置く
  - 元: works/.shared/core/gatemarks.py `answer_drafts`・`draft_line`
  - 今: lib/runreport.py:356 `answer_drafts`（報告の持ち物。plan-review の questions と隣の p2.fix_plan.json を読む）
  - 証: lib/tests/test_runreport.py::DraftsCase（報告の区分。ここは参照だけ。元 works/tests/test_gate_drafts.py の DraftsCase のうち 7 件は同名が無い——報告の区分の在庫で照らす）
  - 本物の run: 報告の区分
  - 狭め: 無し（報告の区分の行）

- P257 事前審査の受け付けを 3 回拒んで諦めた往復は、pass: false・stalled: true で、諦めた訳を「事前審査の受け付けが諦めた: …」として questions に載せ、関所に回す
  - 元: 盤面の give_up で輪を抜けた後、h-gate が止まりの行を聞いた（works/blk-plan/blk-plan.yaml の plan-review-loop）
  - 今: lib/boardview.py:933-936・:947-948（GIVEN_UP_FACES）
  - 証: tests/workflows/test_plan_review.py::ReviewAcceptCase.test_give_up_on_the_third_reject（assert: :720-721）
  - 本物の run: 筋書きでのみ
  - 狭め: 無し


## 穴の要約

### 数

- 行の総数: 257（修正案を書く側 59・構造 42・往復と案の直し 48・事前審査 68・関所の材料 40）
- 今に無い（「今: 無し」か一部が無い）: 15 — P002・P049・P057・P058・P100・P117・P122・P126・P135・P146・P211・P212・P213・P238・P255
  - うち P122（盤面の巻き戻し）は盤面が無いので当たらない、P117 は Archon に強いられた、P058（工程の地図）は持ち主の文書 docs/design.md:435 の決めで落とした。実際に戻す物は 12
- 試験が無いか弱い（要追加を書いた行）: 94（修正案を書く側 30・構造 18・往復と案の直し 20・事前審査 14・関所の材料 12）
  - 重い所: 修正案の材料の節（構造の行・処方・裏取り・外した範囲・libdocs・単位の一覧・言語）がブロックの水準で 1 つも縛られていない（P033〜P046）。構造の目の控えの訳の 5 通りと時間の和（P084・P085）。関所の台帳の問いの数えの断言（P240・P241・P243）
- 狭めて Archon に強いられていない（戻す）: 37 — P002・P010・P025・P049・P057・P073・P086・P100・P119・P120・P126・P135・P138・P139・P142・P144・P145・P146・P152・P161・P173・P180・P187・P192・P211・P212・P213・P216・P236・P238・P240・P241・P243・P244・P249・P250・P255
- Archon に強いられた狭め: 1 — P117（2 周目の計画の役を前の会話の続きで起こせない。loop_group の中の `context.resume` を loader.ts:1173-1174 が禁じる）

### 今壊れている・壊れる余地

- 今壊れている: P241。線の answer-before-fix が関所の答えに `asked`（人が見た関所の項目の文）を運ばないので、関所で continue を受けた fork・escalate の出どころが修正のブロックで直す義務に戻らない
- 壊れる余地: P250。plan-review の返り `questions` が項目の種類を落とすので、線は全部の行を台帳の問いとして扱う。無人の run で方針の文書の変化だけが在ると、元は関所で止まったのに今は修正へ進む

### 同じ根でまとめると

1. 読んだ証拠（元の plan-reads・U6）: P057・P135・P211・P212・P213。#73・#75 は「Archon から役の道具の呼びを引く口が無い」としたが、止めた版の Archon は道具の呼びを run の記録と出来事に残す（packages/workflows/src/logger.ts:129-130・:298-310、packages/workflows/src/provider-events.ts:134、packages/cli/src/commands/workflow.ts:4076-4091 の `workflow get --events --json`）。不可ではない
2. 線（#74）の配線の欠け: P139・P152（plan-review に conflicts を渡さない）、P244（gate_answers を渡さない）、P241（`asked` を運ばない）、P002・P010（plan に関所の答えが届かず、行き止まりの道が届かない）、P249（関所の行の二重）
3. 方針の文書の固め: P216（run の始めでなく事前審査の最初の差し込みで固める）、P192（固めた版の写しでなく今の文書を貼る）、P246（関所で通した変化の固め直しが後段へ届かない）
4. 判定が `purpose_review` を出さない: P161。「目的を狭めている」で独立設計を止める決まりは本物の線では一度も効かない（試験は手で欄を置いた判定で緑）
5. 渡し先（report・線）に受け手が無い: P119（往復の報告の行）・P145・P146（案の直しの報告の行）・P238（読めなかった保留）・P243・P255（最後の関所の通した行）
6. 受け付けの作業ツリーの比べ: P049。plan の受け付けは HEAD と枝の動きを見ない（Archon の比べは `git status --porcelain` だけ。dag-executor.ts:1196-1215）。plan-review は `accept.tree_moved` で残した
7. lib-port で外れた照らし: P073（6 つの形と設計書の一致）・P100（工場自身の考えの地図と柵の CI）

### 持ち主に聞くこと

1. P117: 2 周目の計画の役を新しい会話で起こし、前の周の案と指摘を保存したファイルで渡す形で、持ち主の決め persona を満たすと読んでよいか（Archon では会話の続きは不可と確かめた）→ 決めた: よい（2026-10-12 の推しの決め）
2. 読んだ証拠（U6）: Archon で取れると分かったので戻すか（P057・P135・P211〜P213）
3. P002・P010: plan に関所の答えを渡して「答えた問いの出どころを義務に戻す」と行き止まりの道を戻すか、道を消してこの能力を fix（conflict）の側だけに置くか
4. P241・P244・P250: 修正前の関所の答えの形を `{decision, text, asked}` に決め、線が修正・事前審査・目の 3 か所へ同じ形で渡すか（→ 決めた: 渡す。fix の読み手 `lib/fixboard.py` の `gate_items` が既にこの形を読み、今の works も人が見た行 `asked` を残した。線の配線の部分 B1 のやる事 1）。plan-review の返りに項目の種類を足すか（線が隣の gate.json を読むか）
5. P216: 方針の文書を run の始め（線の start）で固めるか → 決めた: 固める（線の配線の部分 A のやる事 4。issue #84）
6. P161: 判定の約束に `purpose_review` を足すか、判定の隣の材料のファイルを読む形にするか
7. P011: 判定の単位が nit だけの時、report が no_fix_needed と言えない。返りに訳の語を足すか
8. P035: 材料の「読む版」を BASE と分けるか（差分の run で効く）
9. P142: 案の直しの関所を全部の項目で 1 つの go にした（元は項目ごとに採る／諦める）のを認めるか → 決めた: 人の答えは今の works も 1 つの語（replan.py:699-744）。機械の側の項目ごとの諦めは戻す（区分 P）
10. P173: 独立設計の指示書から外れた「前提のドリフト」「裏取りを通っていない目的の判定」の 2 行を戻すか
11. P073・P100: 6 つの形の正本の文書と、工場自身の考えの地図と柵の CI の置き場をどこにするか
