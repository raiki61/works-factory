# 線の配線: 線とブロックのつなぎで落ちた今の works の能力を、行ごとに試験で縛って戻す（7 つの issue に分けて出す）

## 冒頭

- 何の話か: 修正の工場 works-factory の線（PR #74）と 8 つのブロック（PR #66・#69・#67・#75・#73・#68・#76・#94・#100）は、どれも ASF の審査を通った。それでも持ち主の側の目は毎回、元の工場（下の「今の works」）から黙って落ちた能力を見つけた。原因は、issue に「今の works の能力の一覧（元の file:line と縛る試験）」と「Archon で繰り返し踏む落とし穴」が書かれていなかったこと。この文書はその 2 つを書き、線とブロックのつなぎに当たる能力を 7 つの issue（部分 0・A・B1・B2・C・D1・D2）で戻させる。
- この文書でする事: 部分ごとに「閉じる行」（能力の棚卸しの行の ID）を全部閉じる。行ごとに名指した試験を先に入れて赤を見てから直す。落とし穴 K1〜K20 は名指した試験で縛る。狭めてよいのは Archon で不可と源の行で示せる物だけ。
- 読者に求める物: ASF（実装と審査の役）には、各部の「閉じる行」と「受け入れ」がこの issue の約束で、審査はそれと照らす。持ち主には、末尾の「持ち主の答え待ち」に挙げた物だけ。

## 語（初見の人へ）

- works-factory: このリポジトリ。元の工場の能力を 1 つも落とさずに（持ち主の決め `superset`。能力を削る直しは人に上げる `no-narrow`。どちらも `docs/owner-decisions.md`）、Archon（AI の工程を YAML で書いて回す道具）の上に作り直す。設計の正本は `docs/design.md`。
- 今の works: 元の工場。公開リポジトリ raiki61/claude-plugins の commit `2aa7c66cf7abe1fe09699ac2942d107123214168` の `works/`（`pack.json` の `works.commit`）。下の「元」の file:line は全部この版。
- 線: `workflows/line/works-factory-line.yaml` と `workflows/line/scripts/`。8 つのブロックを `include:` で順に差し込み、人の関所 4 つ（`gate-start`・`gate-before-fix`・`gate-replan`・`gate-final`）と計画の往復と報告を持つ。
- ブロック: `workflows/<名>/`。judge（判定）・plan（計画）・plan-review（事前審査）・fix（修正）・test-gate（試験の関門）・eyes（独立の目）・merge（取り込み）・report（報告）。ブロックはほかのブロックを知らず、入力（`inputs:` と線の `with:`）と返り（返す節の `output_format`）だけで線とつながる。
- 返りの約束: `docs/design.md` の「ブロックの返りの約束」。ブロックごとの入力・返りの欄と、「隣のファイル」（返りの指し札が指すファイルと同じフォルダに置く、名の決まった控え。ほかのブロックが名で開いてよい物）を決める。
- 指し札: Archon の `{type: "archon_artifact", run_id, path}`。run の置き場の中のファイルを指す。
- 受け皿: 線がブロックごとに置く `<include の id>-out` の節。`collect` はブロックの返りをここからだけ読む。
- 層の決まり: 各階層の `AGENTS.md` の決まり E1〜E18 と、それを照らす `tests/layers/`（走査器 `tests/layers/scan.py`）。この文書では「層の E3」のように書き、能力の棚卸しの区分 E の行（独立の目の行。ID の一覧の中の E17 など）と分ける。
- 能力の棚卸し: この文書と一緒に置く `docs/plans/2026-10-13-capabilities/`（`README.md` と 6 ファイル: `line.md` 区分 L と線への申し送り S、`judge.md` 区分 J、`plan.md` 区分 P、`fix.md` 区分 F、`tail.md` 区分 T・E・R・M、`pitfalls.md` 区分 K）。1 行 = 1 つの能力で、欄は 5 つ:
  - 元: 今の works の file:line と関数
  - 今: works-factory の住処（file:line と関数）か「無し」
  - 証: その能力を外すと赤になる試験の名と assert の行。無ければ「要追加: <試験の名> — <何を照らすか>」
  - 本物の run: 本物の run の記録のどこで見えるか、か「筋書きでのみ」
  - 狭め: 「無し」か、どの PR が狭めたかと「Archon で不可（源の行）」か「不可でない → 戻す」
  - 「今」の行番号は main `4e0e18d` と、線は PR #74 の head `824dee3` の物。#74 の 5 回目の直しで線の行番号はずれるので、関数と節の id で引く。
- 行の印（この文書の「閉じる行」の頭）: 〔無〕今の住処が無い・〔戻〕狭めたが Archon で不可でない・〔試〕証の試験が無いか弱い・〔縛り済み〕証が在る（壊さない）。閉じる行の文は棚卸しの行の頭の 1 文の写しで、詳しい元と試験は棚卸しのその行。
- 止めた Archon: `factory/pack.json` の commit `d97d00ef15cce4b15d39e42635e4e86996ec1351` の源（CI と同じ取り方。`bin/_lib/place.py` の `archon_folder`）。下の Archon の file:line はその `packages/` からの相対。
- 段 1: 段 1 の計画 `docs/plans/2026-10-13-stage1-walking-skeleton.md`。本物の役で線を通しで回し、能力の行を run の記録で照らす（照らしの表 `tests/e2e/evidence.json`）。

## 置き方と issue の切り方（運び役へ）

1. 能力の棚卸しを `docs/plans/2026-10-13-capabilities/` に、この文書を `docs/plans/2026-10-13-line-wiring.md` に置く。
2. issue を 7 つ立てる。本文は「この文書の冒頭から『部分 0』の前まで（共通の節）」と、その部分の節と、末尾の「この文書の外」の写し。どれも GitHub の本文の上限（65,536 字）の半分に収まる。
3. 順: 部分 0 → 部分 A → 段 1 → 部分 B1 → B2 → C → D1 → D2。1 つずつ、前が main に入ってから次を起こす（同じファイル `workflows/line/scripts/ask_final.py`・`collect.py`・`lib/runreport.py` を触るので並べて回さない）。issue #101（`bin/apply`・`tests/e2e/make_target.py`）は触るファイル（`bin/`・`tests/e2e/`）が部分 0・A と重ならないので並べてよく、段 1 の前に main に入れる（段 1 の依存で、部分 C の前提 3 も満たす）。段 1 の計画の置き換えは #101 の merge の後（段 1 の計画の「置く先」）。
4. 運び役は 7 つの部分と同じ時に、「ブロックの中だけの穴」（末尾）を区分ごとに 1 つの issue（J・P・F・T・E・R・M の 7 つ）に立てる。本文はこの文書の共通の節と、その区分の行の ID の一覧と、始める条件。始める条件は 2 つ。(1) 部分 0 が main に入っている: 区分の issue は部分 0 が足す機械（K1〜K20）を通し、部分 0 が `ALLOWED["E3"]`・`ALLOWED["E4"]` に名指して許した自分のブロックの行を外す（K7・K8）。部分 0 の 0-d が S の行の行き先を変えたら、それも読む。(2) 同じブロックのファイルを触る部分（B1〜D2）と並べて回さない。M の issue は M39〜M52 を issue #101 に任せ、残りの行だけを持つ。立てるのを部分 0 の後に延ばさない訳: 行は棚卸しの ID で引くので部分 0 の直しの後も変わらず、先に立てておけば行が黙って忘れられない（この文書が直そうとしている落ち方そのもの）。

## 始める前の前提

この文書の issue は、次が main に入った後に始める。

1. 線の PR #74（5 回目の直しの後。代わりのブロック `workflows/line/fixtures/stub-blocks/` が無く、本物の 8 ブロックと組んでいる）
2. 修正のブロック #94・判定と報告の輪の直し #100（どちらも merge 済み）
3. 部分 C だけ: issue #101（`bin/apply`）。報告に当てる 1 行を出すため

部分 0 の PR は、本文の頭に次の 4 つの確かめの結果を書く（#74 の merge の時の形が、この文書を書いた時に分からないため）。

- 0-a 線に代わりのブロックが残っていないか。全部の include が本物で、`archon validate` が誤りも警告も無く通るか（同梱の skill の警告は `tests/archon.py` の `counted` の例外だけ）。
- 0-b 線の `report` への `with:` の鍵と、report の `inputs:` が合っているか（#74 の 4 回目の直しの後は report の 17 の宣言に合わせてある）。
- 0-c 線の `plan`・`replan` の `with:` に `prior_failures: $start.output.prior_failures`、eyes に `start_answers` が在るか（#74 の 3 回目の直し）。
- 0-d 棚卸しの `line.md` の「線への申し送り」S01〜S68 のうち「済み」と書いた物が、merge された線でも済んでいるか。違えば、その行をこの文書のどの部分で閉じるかを PR 本文に書く。

## どの部分にも共通の決まり

1. 行ごとに試験が先: 「閉じる行」の行ごとに、棚卸しのその行の「証」の試験を先に足して赤を見てから直す。試験の名は棚卸しの名を使う（変えるなら PR 本文に「行 ID: 旧の名 → 新の名」）。PR 本文に行ごとに 1 行: `<行 ID> <試験の名> 赤: <commit か出力の 1 行> 緑: <commit>`。
2. 縛りは「外すと赤」: 足した試験は、その能力の行を消すか元の字に戻すと赤になる物でなければならない（形だけの照らしは足りない）。PR 本文に、行ごとに「どこを消すと赤になるか」を 1 句で書く（持ち主の側は毎回、手で変異を当てて確かめている。K17）。
3. 狭めてよい物: 戻せない行は、Archon の源の file:line で不可を示せる時だけ狭めとして PR 本文に名指す。示せない物は直さずに止めて PR 本文に書き、持ち主の答えを待つ。黙って外さない。
4. 棚卸しの直し: 行の事実（元の行番号・今の住処・試験の名・本物の run の置き場）が違えば、同じ PR で棚卸しのその行を直し、PR 本文に「行 ID: 旧 → 新」で並べる。閉じた行は「今」と「証」を新しい住処と試験に書き換える。行を消すのは「元に無い」と元の file:line で示せた時だけ。「元」の欄は、元の file:line で誤りを示せた時だけ直す。
5. 縛り済みの行は壊さない: 触ったファイルの行で「証」が既に在る物は、その試験を消さず弱めない。
6. 触ってよい所: この文書は線と返りの約束を直す仕事なので、部分が名指したファイルは、共有のファイル（`harness/harness.config.json` の `protected_paths`。`workflows/line/**`・`workflows/.shared/**`・`**/AGENTS.md`・`docs/design.md`・`README.md`・`pack.json` ほか）でも直してよい。merge queue が人の手に残す（それが守り）。`docs/design.md` の「作りの順」の段 2 の「共有のファイルは土台の持ち主だけが変える」は、並べて回すブロックの issue が約束を黙って変えないための決まりで、この文書は土台の持ち主（運び役）が変える所を名指した物なので、その変えを ASF が字のとおりに入れ、`protected_paths` が merge を人の手に残す（ASF の型 A7。段 2 と同じ守り）。名指していない共有のファイルの変えが要れば、止めて PR 本文に書く。返りの約束の欄・隣のファイル・入力を足す・変える時は、同じ PR で `docs/design.md` の「ブロックの返りの約束」を直す（約束とコードを食い違わせない）。層の機械を足す時は `tests/layers/scan.py` の今の決まりに行や語を足し、その `AGENTS.md` の「機械」の行も同じ PR で直す。決まりを緩める・行を消すのは、この文書が名指した時だけ。触らない: `docs/owner-decisions.md`・`MISSION.md`・`FACTORY.md`・`FACTORY_RULES.md`・`harness/`・`factory/`・`.github/`・`bin/`・Archon の源。
7. 写した指示書と役の定義（`workflows/*/commands/**`・`lib/agents/*.md`）を触る時は、`tests/workflows/test_prompt_contracts.py` の 4 つの約束を保つ。今の形に合わせて直す字は「元の字 → 写しの字」の組で試験に持たせる（K9）。持ち主の決め `prompts-coldread`（2026-10-12、`docs/owner-decisions.md`）で、初見の読み手での書き直しも元の字に戻さず、許した直しとして組に足す。
8. 期限・タイムアウトを新しく足さない（持ち主の決め `no-timeouts`。層の E12）。
9. 試験は `WORKS_FACTORY_ARCHON_REQUIRED=1 uv run --isolated python3 -m unittest discover -s . -t .` が全部緑（層の試験 `tests/layers/` と筋書き `tests/e2e/test_line_scenarios.py` を含む）。`archon validate` は線と全部のブロックで誤りも警告も無い。
10. 段 1 の照らしの表: 照らしの表が main に入った後の部分（A〜D2）は、`tests/e2e/evidence.json` で自分の「閉じる行」が `waits-part` の物を、`seen`（置き場と照らしを書く）か `scenario-only`・`seed-cannot`（訳つき）に移す。

## 落とし穴の確かめ（K1〜K20。どの部分の PR も全部に答える）

各行の詳しい根拠と穴は棚卸しの `pitfalls.md`。部分 0 が機械を足し、部分 A〜D2 は自分の差分がそれを通ることを PR 本文に 1 行ずつ書く（「K<n>: 当たる所が無い」も書く）。層の決まりに住処の在る物は、新しい試験のファイルを作らず `tests/layers/scan.py` の今の決まりへ足す（同じ決まりを 2 か所に持たない。持ち主の決め `concept-home`）。

- K1 返す節と、返す節が結ぶ節は落ちない。lib と境の口の import は返す節の守った `main` の中で読み、読めない時も標準ライブラリだけで約束の形を返す。Archon は落ちた節の出力を結んだ節を `trigger_rule: all_done` でも落とす（`workflows/src/dag-executor.ts` 495-533 行 `resolveBindingDirective`・`output-ref.ts` 590-597 行）。
  - 今の機械: ブロックごと（`test_judge.py::VerdictNeverFailsTest.test_lib_out_of_reach` ほか、`pitfalls.md` の K1 に 9 本）と、線の `test_line.py::FallbackCase`・`BrokenLibCase`
  - 部分 0 が足す: `tests/workflows/test_returns_never_fail.py::ReturnScriptCase.test_every_returns_script_runs_alone_and_fits_its_output_format`（全ブロックと線の返す節の script を `.shared` も lib も無い一時のフォルダに単独で写して走らせ、終了 0 と `output_format` に合う JSON）と `ReturnScriptCase.test_return_node_binds_only_never_failing_nodes`（返す節が `with:`・`when:`・本文で読む `$<id>.output` の `<id>` が、試験の表 `NEVER_FAIL` に在り、表の各行が「その節を lib 無しで走らせる試験の名」を持つ）
- K2 `runtime: uv` の script は頭に PEP 723 の 4 行を持つ。Archon は `scripts/` の 1 段下まで探す（`workflows/src/script-discovery.ts` 71・107-111 行）。
  - 今の機械: `tests/workflows/test_uv_scripts.py::HeaderTest.test_every_script_declares_itself`（1 段下を見ない。issue #96）
  - 部分 0 が足す: `HeaderTest.test_every_named_script_archon_can_find_declares_itself`（1 段下まで探し、YAML の `script:` の名が全部当たり、直に書いた `script:` が無い）。issue #96 を閉じる
- K3 作業ツリーを変えない節は `mutates_checkout: false`。Archon は `loop:` の節ではこの鍵を無視する（`workflows/src/schemas/dag-node.ts` 1024-1031 行）ので、読むだけの役は `loop:` で書かない。
  - 今の機械: 層の E7（`tests/layers/test_readonly_nodes.py`・`scan.py` の `_readonly_nodes`。役のブロック 5 つと名の表 `READONLY_NODES`・`JUDGE_WRITERS` だけ。fix・test-gate・merge の役は `test_role_nodes_of_other_blocks_are_free` で自由）と、ブロックごとの試験
  - 部分 0 が直す（層の E7 の決まりそのものを直す。2 つ目の住処は作らない）: 役の節の印を道具から導く（`allowed_tools` に Bash・Edit・Write が無い役は `false` 必須、在る役が `false` を書けば赤。元 `works/tests/test_yaml_rules.py` の `test_pack_read_only_ai_nodes_do_not_mutate_checkout`・`test_changer_node_with_mutates_checkout_false_is_red`）。全ブロックに当て、`test_role_nodes_of_other_blocks_are_free` を `test_role_node_mark_follows_its_tools` に置き換える。`test_loop_node_is_not_asked_for_the_mark` は「読むだけの役を `loop:` で書くと赤」に置き換える。script の節は `READONLY_NODES` に judge の 36 個ほか読むだけの節を足し、YAML に `false` を書く
- K4 skill や agent を借りる役の節は `skills:`・`plugins:` で名指す。Archon は名指した物しか渡さない（`providers/src/claude/provider.ts` 627-638 行）。同梱の skill は `tests/archon.py` の `BUILTIN_SKILLS` で警告を数えない。
  - 今の機械: `tests/layers/test_archon_validate.py::ArchonValidateTest.test_only_builtin_and_borrowed_skill_warnings_go_uncounted`・`test_judge.py::RoleSettingsTest`・`test_fix.py::RolesCase.test_borrowed_skills_sit_on_the_seat_roles`
  - 部分 0 が足す: `tests/workflows/test_role_texts.py::RoleSkillsCase.test_prompt_naming_a_skill_or_agent_declares_it`（役の指示書が借りる skill・同梱の skill・`pr-review-toolkit` を名指すなら、節の `skills:`・`plugins:` が名指す。説明だけの言及は試験の表で行ごとに許す。今の食い違い `workflows/judge/commands/material-local-review.md` 91-93 行は、元の字のままなら表に載せ、訳を書く）
- K5 `loop_group` の中の役の節は自分の `with:` を結ばない。前の周の値は輪の頭の script の節が `$LOOP_PREV` で結んで返し、役はその出力を読む（PR #100。`workflows/src/include-expander.ts` 566・579・596・627 行）。
  - 今の機械: `tests/layers/test_archon_validate.py::ArchonValidateTest.test_every_block_loads_when_included`（Archon が要る。`loop_group` の中で include する形は見ない）
  - 部分 0 が足す: 層の決まりとして `scan.py` に「`loop_group.nodes` の中の `prompt:`・`command:` の節に `with:` が無い」の照らしを足し（Archon 無しで字で照らす。置く決まりは層の E5 か E16 の近い物。PR 本文に置いた所を書く）、`test_every_block_loads_when_included` に `loop_group` の中で include する形を足す
- K6 周ごとの値（`$LOOP_PREV`）は本物の run でしか確かめられない。`archon workflow test` の筋書きは周を回すが、前の周の出力を渡さない（`workflows/src/dry-run.ts` 795 行の `loopPrevOutput: ''`・1053-1085 行。stub は毎周同じ値）。
  - 今の機械: 無し
  - 部分 0 が足す: `tests/workflows/test_fixture_claims.py::FixtureClaimsCase.test_fixtures_do_not_claim_per_round_values`（筋書きの注記・`resolved-text-contains` が「周ごとに違う値」「前の周の理由」を確かめたと言っていれば赤。「3 回とも拒んだ」のように同じ値の周の数を言う注記は正しいので赤にしない）。本物の確かめは段 1
- K7 層の E3（lib は Archon を知らない）・層の E4（script は lib と境の口を呼ぶだけ・ほかのブロックを指さない）・層の E13（`commands/` と lib は対象の言語を知らない）。
  - 今の機械: `tests/layers/test_lib_blind.py`・`test_block_paths.py`・`test_lang_neutral.py`
  - 部分 0 が直す: 層の E3 の語の表（`scan.py` の `ARCHON_WORDS`）に `INPUTS_`・`WORKFLOW_ID`・`$LOOP_PREV`・`loop_group`・`$<id>.output` の形を足す。今 lib に在る物（少なくとも `lib/stage_a.py:21`・`lib/stage_b.py:5・35`・`lib/tree_run.py:28・416・418`・`lib/judge_accept.py:2011・3363`・`lib/rolekit.py:62`・`lib/refixrules.py:6`・`lib/report_roles.py:52`・`lib/boardview.py:81`・`lib/specblk.py:8・48`）は `ALLOWED["E3"]` に行ごとに名指して許す（PR で数え直して全部載せる。`lib/planfile.py:115` の `UNREAD_INPUTS_HEAD` のような誤検知は語の形で外す）
- K8 script から script を import しない。lib に、読む順で落ちる循環 import を作らない。
  - 今の機械: 循環は `lib/tests/test_judge_accept.py::VerifyPrepCase.test_judgeverify_loads_before_judge_accept` の 1 組だけ
  - 部分 0 が足す: 層の E4 の照らし（`scan.py` の `_block_paths`）に「`scripts/*.py` の import の名が同じ `scripts/` の別のファイルの名なら赤」を足す。線の分はこの部分で 0 にする（部分 0 のやる事 5）。ブロックの今の物（fix の `fixio`・`prep`、report の `place`・`typed`）は `ALLOWED["E4"]` に名指して許し、ブロックの区分の issue（末尾）で外す。循環は `lib/tests/test_imports.py::LibImportCase.test_every_module_imports_first_in_a_fresh_interpreter`
- K9 役の指示書と役の定義は元の字のまま写し、許した直しだけを「元の字 → 写しの字」で持つ試験で縛る（強い形: `tests/workflows/test_plan.py::ShapeCase.test_fix_plan_command_is_the_original_with_only_the_allowed_edits`）。
  - 決めとの両立: 持ち主の決め `prompts-coldread`（2026-10-12、`docs/owner-decisions.md`）で、役の指示書は初見の読み手で書き直してよい。書き直しは元の字に戻さず、台帳の許した直しとして足す（`tests/workflows/copied_rewrites.json`）。4 つの約束は `tests/workflows/test_prompt_contracts.py` が別に照らす。
  - この文書の範囲: 部分が触る指示書は、その形の試験を同じ PR で足す。部分 D1 の `workflows/fix/commands/fix-rules/direct.md` は `tests/workflows/test_fix.py::ShapeCase.test_direct_rules_are_the_original_with_only_the_allowed_edits`。全部の指示書の台帳は区分の issue（末尾）
- K10 どの関所の `reject` も `stop` も run の取り消しにせず報告へ流す。Archon は `decisions` に `reject` が無い関所の reject を run の取り消しにする（`core/src/operations/workflow-operations.ts` 1625-1700 行）。
  - 今の機械: `test_line.py::GateDecisionsCase.test_gates_take_the_words_their_text_prints`・`test_judge.py::GateTest.test_spec_gate_is_an_approval_with_the_four_words`
  - 部分 0 が足す: 層の E16 の照らし（`scan.py` の `_gates`）に「全工程の `approval:` の節が `decisions` に `reject` を持ち、`on_reject` を持たない」を足す
- K11 ブロックに入力を足す時は既定値を付ける（既定値の無い入力は include する全部の工程の読み込みを落とす。`workflows/src/include-expander.ts` 576-580 行）。既定値つきの入力は、線が渡さないと黙って既定値のまま。
  - 今の機械: `test_line.py::LineWiringCase.test_includes_pass_only_what_the_real_block_declares`（required の入力だけ）
  - 部分 0 が足す: 行 L-W67 の試験（部分 0 のやる事 2）と `tests/workflows/test_line.py::LineWiringCase.test_block_inputs_outside_the_contract_have_defaults`（`docs/design.md` の約束の入力の外は既定値を持つ）
- K12 ブロックの新しい入力と隣のファイルは、どれも読み手を持ち、配線の試験で縛る。
  - 今の機械: 層の E5（`tests/layers/test_block_returns.py`。返りの欄だけ）・`test_line.py::LineWiringCase.test_with_keys_are_what_the_script_reads`
  - 部分 0 が足す: 層の E5 の照らしに「ブロックの `inputs:` の名が、そのブロックの script の `INPUTS_<名>` か指示書の `$INPUTS.<名>` に在る」を足す。`tests/workflows/test_line.py::LineWiringCase.test_every_contract_neighbour_file_has_a_writer_and_a_reader`（試験の中の表 `NEIGHBOURS = {ファイルの名: (書き手のブロック, 読み手)}` の各行で、書き手が止めの道と lib の無い道でもそのファイルを書き、読み手の lib か script がその名を開く。表と `docs/design.md` の隣のファイルの一覧が同じことも照らす。部分 B1〜D2 が隣のファイルを足す時は、同じ PR で表と `docs/design.md` の両方に足す）
- K13 返りの指し札の先は在って空でない。無い・空だと Archon が節を落とす（`workflows/src/artifact-pointer.ts` 141-153 行）。
  - 部分 0 が足す: `tests/workflows/test_returns_never_fail.py::ReturnScriptCase.test_every_pointer_in_a_fallback_return_names_a_nonempty_file`
- K14 同じブロックを 1 つの run で 2 度差し込む所（judge と rejudge・plan と replan・fix と refix・test-gate の base と final・merge の seal と apply）で、2 度目が 1 度目の置き場の物を今回の物として拾わない。1 度目の物が要る時は入力で渡す（部分 D1 の refix の 1 回目の裁定）。
  - 部分 0 が足す: `tests/workflows/test_line.py::LineWiringCase.test_twice_included_blocks_use_their_own_place`（各ブロックの置き場を決める関数〔fix の `fixgates` の place・judge の place・report の include の頭の取り方ほか〕に、線の 2 つの include の id を渡して、違うフォルダが返ることを assert する。関数の名は PR 本文に並べる）
- K15 読めない入力を黙って空や当たりにせず、「読めない」と名指す（持ち主の決め `no-silent-loosen`）。
  - 部分 0 が足す: `tests/workflows/test_unread_named.py::UnreadNamedCase.test_every_pointer_input_unreadable_is_named`（各ブロックの指し札の入力を 1 つずつ壊れた先にして入口の script を走らせ、返りか材料にその入力の名が載る）
- K16 返りの JSON は `allow_nan=False`（Archon は返りを JSON として読む）。
  - 今の機械: `test_eyes.py::ScriptCase.test_verdict_returns_strict_json`（eyes だけ）
  - 部分 0 が足す: 返りを標準出力へ出す道を境の口 `boundary.returns`（と線の同じ口）の 1 つにそろえ、`tests/workflows/test_returns_never_fail.py::ReturnScriptCase.test_returns_leave_only_through_the_boundary`（`scripts/` で標準出力へ JSON を書く `print(`・`sys.stdout.write(` が境の口の外に無い）で縛る。今の外の口（少なくとも `workflows/plan/scripts/plan_collect.py:89`・`round.py:67`・`workflows/merge/scripts/merge.py:101`・`workflows/plan-review/scripts/pass_open.py:80`・`result.py:58`・`workflows/test-gate/scripts/result.py:145`・`workflows/eyes/scripts/verdict.py:54`・`workflows/judge/scripts/verdict.py:58`・`workflows/fix/scripts/collect.py:157`）を直す
- K17 戻した能力には同じ PR で「外すと赤」の試験を置く。共通の決まり 1・2 がこれ。
- K18 役の節の決まり（`settingSources: [user]`・閉じた `sandbox`・`allowed_tools` は表の中だけ・`loop_group` の本体に `approval:` を置かない・`loop:` の節を作らない）を全ブロックで照らす（元 `works/tests/test_yaml_rules.py` 1-48 行の決まりの一覧と違反の見本 `works/tests/yaml_bad/`）。
  - 部分 0 が足す: 層の E7 か E16 の近い決まりとして `scan.py` に照らしを足し、違反の見本を `tests/layers/seeds/` に 1 本 1 違反で置く（置いた決まりを PR 本文に書く）
- K19 script の名を lib のモジュールの名と同じにしない（script のフォルダが `sys.path` の頭に来る）。
  - 部分 0 が足す: 層の E4 の照らしに「全ブロックと線の `scripts/*.py` の名 ∩ `lib/*.py` の名 = 空」を足す（今の `test_plan.py`・`test_plan_review.py` の同じ試験は残してよい）
- K20 同じ定数や関数を 2 か所に持たない（持ち主の決め `concept-home`。2 か所目に出たら部品へ寄せる）。
  - 部分 0 が足す: `lib/tests/test_constants.py::ConstantsCase.test_same_file_name_literal_is_defined_once`（lib と `workflows/*/scripts/` で、`*.json`・`*.md`・`*.txt`・`*.diff` で終わる字の定数の定義が 1 か所。落ちた時の逃げ道の写しは試験の表で名指して許す）。部分 B1 の当ての式・部分 C の再審の比べもこれで縛る

## 線への申し送りの行き先（S01〜S68）

各ブロックの PR の「約束を変える頼み」「申し送り」「後の issue に渡す物」「人が入れる直しの頼み」と、線の PR #74 の「今の works から狭めた物」・運び役のコメントを 1 件 1 行にした物が、棚卸しの `line.md` の「線への申し送り」に在る。この文書での行き先:

- 部分 0: S48 の止めの語の住処（L-G54）・S67（#74 が済ませた事の確かめ。0-a）・S06（test-gate が落ちる筋書き `test-gate-failed`）
- 部分 A: S24（方針の文書を run の始めで固める。issue #84）・S56（版の控え）・S68（始めの記録の置き場。issue #89）
- 部分 B1: S18（関所の答えで直す義務に戻す単位）・S20（plan が読む他のブロックの鍵）・S21・S22（plan-review の `conflicts`・`gate_answers`）・S46（関所の答えの `asked`）・S58 の頭の 2 つ（`answer_ties`・素材の出どころの結び）
- 部分 B2: S27（元の試験 3 本を元の名で写す）・S55（申し出を人に回した行だけ数える）
- 部分 C: S25（目的の監査 `purpose_review`。issue #83）・S30・S48〜S53（report の入力）・S31 の `world-state.json`・S32 の受け付けの最後の拒否の本文・S34（`conflicts.json` の欄の名）・S41（`local-review-lenses.json`・`pr-downgrades.json`）
- 部分 D1: S01・S02（#94 の 3 つの頭の 2 つ）・S09・S10（`x_scalars`・`premise_drift_note`）・S44（`only_items`）・S58 の 3 つ目（`_notes` の 3 つ目）
- 部分 D2: S03（`breaks.accepted`）・S12・S14（eyes の材料・`facts_to_add`）・S28・S29（閉鎖の数え直し・手直しの穴の名札）
- 済み（0-d で確かめるだけ）: S11・S15・S16・S17・S26・S27 の関所の頭の 2 つ・S33・S38 の機械・S42・S47・S63・S64・S65 の 1・2・S66
- 区分の issue（末尾の「ブロックの中だけの穴」と同じに、運び役が立てる issue）へ: S04（`lib/protect.py` の `touched`・`lib/accept.py` の `touched_files` が index の印の付いた変更を見落とす。issue #72）・S45（`rolekit.compose` の写しと使われない lanes の関数。区分 F の issue）
- 守りの文書だけの直し（この文書の部分が `docs/design.md` を直す時に一緒に、か運び役）: S13・S39・S43
- 決めた物（末尾の「決めた物」）: S07（区分 T の issue）・S19・S40（会話を継がない狭めで確定）・S23（PR #105 で決まった）・S35・S36（段 1 の本物の run で見る）・S54（固定材料の独立の issue）・S57（改名を認める）・S59（段 3 の鎖の issue）・S60（`stop-at-gates` で持ち込まない）・S61（S09 と同じで部分 D1）
- 持ち主の答え待ち（末尾）: S37（`gates_deferred`。変異の検算と一緒に段 3 で聞く）

#94 で名指された 3 つの元の在り処（部分 D1・D2 で戻す）:

- 2 度目の修正が 1 回目の申し出と裁定を見られない: 元 `works/.shared/core/conflict.py:411-414` `second_pass`・`works/blk-fix/lib/fixgates.py:103`。今は `refix` が自分の置き場 `fix/refix/` に書き、fix の入力にも線の `refix` の `with:` にも 1 回目の物が無い
- fix が事前審査の返答を受けない: 元 `works/.shared/core/graphloops/rules/review-loop.py:3115-3128` `_plan_face_errors`（呼び元 :2803）と差分の審査役の材料 `out.p2.plan_review`（`works/.shared/core/graphloops/graphs/review-loop.json:4163`・`works/blk-delta/commands/delta-review.md:8`）。今は `workflows/fix/scripts/delta_cut.py:45`・`refix_prep.py:48`・`refix2_prep.py:48` が `plan_review=None`
- `breaks.accepted` を人に回す道が無い: 元 `works/.shared/core/report.py:304-314` `handoff_lines`・`works/darkfactory/lib/line_edge.py:814-815`（`_final_needs`）・`:719-723`・`:868`。今は fix の返りに欄が無く、`ask_final` も report も読まない。修正役の指示書 `workflows/fix/commands/fix-rules/common.md:10` は今も「機械が人に見せる一覧に載せる」と書く

## 部分 0 配線の網と落とし穴の機械

目的: これより後の部分（と後のブロックの直し）で、能力が黙って落ちたら試験が赤になる網を先に張る。振る舞いは変えない（線の script の import の付け替えと、K3・K16 の今の違反の直しだけ）。

閉じる行:

- L-W67〔無・戻・試〕ブロックが宣言した入力は全部が「線から渡る」か「渡さない訳を名指した一覧に在る」かのどちらか（既定値つきの入力が黙って未配線で残らない）
- L-W05〔試〕判定の単位と判定を後ろの段へ運ぶ
- L-W11〔試〕修正案と波及の一覧と深さを修正へ渡す
- L-W12〔試〕計画の往復（plan → plan-review を 3 往復まで。事前審査の返答を次の周の plan に渡す）
- L-W43〔試〕再審の後は、独立の目と最後の関所が再審の判定を読む
- L-W50〔試〕単位ごとの深さを修正へ渡し、修正の後の信号で上げ直して独立の目が省くかを決める
- L-W58〔試〕判定・始めの関所の答え・前の失敗を、それを宣言するブロックへ渡す
- L-E54〔試〕線の inputs: の名と、start が読む INPUTS_<名> が同じ
- L-G54〔無・戻・試〕pack が足す止めの語は字の定数で、名ごとに持ち主は 1 つ。表の語の字は変えない。住処の外に語の写しを置かない柵

やる事:

1. 上の「落とし穴の確かめ」の「部分 0 が足す」「部分 0 が直す」を全部入れる。今の木で赤になる物は、K3（読むだけの節の印）・K16（返りの出口）・K8 の線の分を直して緑にし、それ以外の今の違反は `scan.py` の `ALLOWED` か試験の中の表に行ごとに名指して許す（各行に「区分の issue で外す」と書く。表に無い新しい違反は赤）。
2. 行 L-W67: `tests/workflows/test_line.py::LineWiringCase.test_every_declared_block_input_is_wired_or_listed`。線が include する各ブロックの `inputs:` の全部が、線の `with:` に在るか、試験の表 `UNPASSED = {(include の id, 入力): 訳}` に在る。表の行が宣言に無いか、`with:` に在る入力が表にも在れば赤。今の表の行と訳:
   - `merge-seal` の `answer`・`r2`・`sealed_hash`: apply だけの入力
   - `fix`・`refix` の `mode`・`group`・`from_tree`・`out_dir`: 組の子の run だけの入力
   - `fix` の `only_items`: 1 回目は全部の項目
   - `plan-review-run`（往復の中）の `conflicts`: 修正の前なので申し出が無い
   - `plan-review-run` の `gate_answers`: 修正前の関所より前に走る
   - `replan-review` の `conflicts`・`gate_answers`: 部分 B1 で配線する（B1 で表から消す）
   - `eyes` の `x_scalars`: 部分 D1 で配線する（D1 で表から消す）
3. 受け渡しの表: `tests/workflows/test_line.py::HandoffCase.test_handoff_table`。今の works の線が段から段へ渡した値（元 `works/darkfactory/darkfactory.yaml` の各節の入力と `works/darkfactory/lib/line_edge.py` の境の節）を表にし、線の `with:` がその値を同じ源から渡すことを照らす（行 L-W05・L-W11・L-W12・L-W43・L-W50・L-W58）。表の 1 行 = 「元の受け手の節 → 今の include の id と入力 → 今の源の `$…`」。元に在って今の線に無い受け渡しは、閉じる部分の名を訳に書いて表に置く。
4. 行 L-G54: 線が足す止めの語（`works:start-refused`・`works:needs-human`・`works:line-script`）と人の止めの頭 `human:` を `lib/stopby.py` に置き、線の script と report が同じ定数を引く（今は `workflows/line/scripts/linekit.py` 25-33 行にだけ在る）。人待ちの語かの印も lib に持たせる。関所の決めの語（`GO_WORDS`・`REJECT`・筋書きの `approved`）は、関所の答えの行を組む `lib/answer.py` に置く。試験: `lib/tests/test_stopby.py::LineWordsCase.test_line_words_live_in_stopby_only`（線の script に止めの語の字の写しが無い）。
5. 線の script どうしの import（K8）を無くす。行き先は次のとおり（層の E3 により、節の id・流れ・ブロックの間で渡す物の型は lib に置かない）:
   - `linekit.py` の出入りの口（`guarded_imports`・`run`・`value`・`field`・`text`・`flag`・`items`）: 境の口 `workflows/.shared/boundary.py` へ（層の E2: `.shared/` は境の口と埋めだけ）
   - 止めの語と関所の語: 上の 4
   - `replan_answer.py` が `gate_answer` から借りる答えの組み立て: `lib/answer.py` へ（答えの行の組み立てはそこが住処）
   - `returned.py` が `plan_out`・`fixed` から借りる欄の一覧: `returned` は欄の名を自分の `with:` の鍵（`INPUTS_*`）から読み、一覧を持たない
   - `ask_before_fix.py` が `plan_out` から借りる `ROUND_LIMIT`: 線の YAML から `with:` で渡す（`test_round_limit_is_the_loop_limit` が `max_iterations` と同じ値を縛る）
   - `collect.py` が `plan_out` から借りる物: 上と同じく `with:` の鍵から読む
6. 筋書き `workflows/line/fixtures/test-gate-failed.stubs.yaml`（S06）: `test-gate-final` の節 `run` を型に合わない stub で落とし、`collect` と `report` が走って `test-gate-final` の返りが null で届く。

受け入れ（部分 0）:

1. 共通の決まり 1〜10 と、K1〜K20 への 1 行ずつの答えが PR 本文に在る。
2. 「部分 0 が足す」「部分 0 が直す」が全部入り、許しの表の行がそれぞれ訳を持つ。足した決まりの照らしごとに、違反の見本で赤になる試験が在る。
3. 振る舞いの変化が無い: 線の筋書きが全部、変える前と同じ結末で通る。

## 部分 A 入口・始めの記録・今壊れている物・線の返り

目的: 入口と始めの記録の能力を戻し、今の線が元より危ない側に倒れている所（再審が止まっても先へ進む・spec の拒みが効かない・認証の要らない起動の判定が効かない・PR の本文が目的の役に届かない・始めの記録の置き場が 2 つ・案の直しの後も目が古い案を照らす）を直す。段 1 と issue #101 の `bin/apply` が読む線の返りの欄を足す。

閉じる行:

- L-E02〔戻・試〕依頼が「読めない」「JSON として読めない」「形が違う」の 3 つを別の文で拒む
- L-E03〔試〕依頼の answers を始めの記録の answers に置く（後で問いに答えたかを決める元）
- L-E04〔試〕answers・prior_failures の形が違う依頼を拒む
- L-E06〔試〕依頼の相対パスは対象の根から読み、request_file は絶対パスで残す
- L-E09〔試〕base を名指せば base と HEAD の merge-base を差分の根にし、label を「base <名>」にする
- L-E10〔試〕引けない base・番号でない pr を名を言って拒む
- L-E11〔試〕名指した PR・issue を run の中で gh で読み、置き場の根の github.json に 0600 で置く。在れば読み直さない
- L-E12〔試〕PR の差分の根は GitHub の baseRefOid と HEAD の merge-base。label は「PR #N「題」」
- L-E13〔試〕PR の head が対象の HEAD と違えば止める。PR の base の版が無ければ「fetch してから」と言って止める
- L-E15〔戻・試〕認証の要らない起動で PR・issue を名指せば、gh を呼ばずに「認証を使う起動で回す」と止める
- L-E16〔試〕依頼の文（request_text）: 依頼と PR の両方なら「## 依頼」「## PR #N の題と本文」の見出しつき、片方ならその文、無ければ「変更（label）の審査」
- L-E17〔無・戻・試〕PR の題と本文が目的の役に「①PR 説明」として届く
- L-E18〔試〕依頼の欄 issue・pr で名指した番号も読む（named）
- L-E19〔試〕入口の入力の形 input {base, head_rev, diff, requests, request_file, pr, spec} を 1 つにそろえる（どの入口でも鍵が同じ）
- L-E24〔試〕始めの記録の置き場は 1 つで、全部の読み手が同じ口で読む（置き場が割れて機能の切り替えが黙って変わった 8dfebca6 の柵）
- L-E25〔試〕thickness は空・自動・軽量・標準を受け、重厚は「足す工程がまだ無い」、ほかは「知らない値」で拒む
- L-E27〔試〕spec の語（空か on）を確かめ、on は input.spec を真にする
- L-E29〔無・戻・試〕spec=on なのに依頼の文（依頼も PR の題と本文も）が無ければ止める
- L-E33〔試〕機能の切り替えがブロックに届く（今はブロックが記録の features_cut を読む）
- L-E34〔試〕呼び直しで機能・test_cmd・入口の形・base_rev を替えない
- L-E38〔試〕test_cmd・tdd_suite を記録し、test-gate と fix が読む
- L-E45〔無・試〕分からない版の値は null にし、unknown に理由を書く
- L-E46〔試〕拒む run でも版の控えと設定の写しを残す
- L-E48〔試〕起動の関所の文: 冒頭 3 行・入口の文・機能・最後の関所の開き方・答え方の 2 行
- L-E49〔無・戻・試〕頭の行に段（thickness と（既定））・gates・機能・このラインに無い節の数・downgrades・修正前のテストの任せ先の注を並べる
- L-E55〔無・戻・試〕入口の種類（依頼・base・PR）を知るのは入口の変換だけ（柵 entry-kind）
- L-G03〔試〕知らない答えの語を通さない（元は BoardGap で落とした。今は通す語でない物を全部止めと読む）
- L-G07〔無・戻・試〕stop の一言が空なら、既定の文（「関所で止めた」「最後の関所で止めた」）を止めの理由にする
- L-G09〔試〕始めの関所の文（冒頭 3 行・入口の語・機能・最後の関所の開き方・答えの行）を AI の前に見せる
- L-D48〔無・戻・試〕再審が止まった run（3 回拒まれた・支度ができない）は試験の関門・独立の目・merge へ進めない
- L-D51〔試〕形の合わない前の失敗の行は入口で拒む
- L-D54〔戻〕CI の赤の試験 id を次の依頼の prior_failures に足す口 carry-ci（同じ行は 2 度足さず、形が違えば exit 2）
- L-W56〔戻・試〕独立の目が照らす修正案と波及は、案の直しの後に差し替えた承認済みの物
- L-W60〔戻・試〕報告はいつも走る（前の段が落ちても、ブロックの返す節そのものが落ちても）。Archon の resume でも報告を回し直す（always_run）
- P216〔戻・試〕方針の文書は run の始め（盤面を作る時）に固めた。今は事前審査の最初の差し込みで固めるので、run の始めから計画の終わりまでの書き換え（判定・修正案が読んだ版との食い違い）は変化として見えない
- P192〔戻・試〕貼る方針は run で固めた版の写し（元は record.process.policy.copy から貼った）。今は固めた版でなく、その時の文書のパスを読んで貼る
- J04〔無・戻・試〕依頼のファイルを名指したのに行が空なら（始めの記録が依頼 1 件以上と言う run）欠けとして止める
- L-E37〔戻・試〕lang を記録し、全部の役の文に言語の 1 行を足す

やる事（行の詳しい元と試験は棚卸し。ここは形の決め）:

1. 始めの記録の置き場を 1 つにする（L-E24。issue #89）: `start` が書く置き場と、lib の読み手（`lib/startrec.py` の `path`・`REL`、`lib/gatemarks.py`・`lib/depth.py`・`lib/boardview.py`）が読む置き場を `lib/startrec.py` の 1 つの口にそろえる。fix の `workflows/fix/scripts/prep.py:63` の写し直しも消す。
2. 再審が止まった run を止める（L-D48）: `workflows/line/scripts/judged.py` の `judged()`（今は再審の返りの止めを捨てて `""` を返す）が、再審の返り（`ready: false`・止めの語 `works:rejudge`）を `stop_reason` で返し、`test-gate-final` 以降を飛ばして `collect`・`report` へ進める。筋書き `rejudge-stop` を足す。
3. 目に渡す案（L-W56）: 案の直しが通った run では、eyes の `plan`・`ripple` を `replan` の物にする（線の `fixed` か同じ形の返しの節で選ぶ。元 `works/darkfactory/lib/line_edge.py:1058-1064`）。
4. 方針の文書を run の始めで固める（P216・P192。S24・issue #84）: `start` が `policy_md` の版（sha256 と写しのパス）を始めの記録に置き、plan と plan-review は固めた写しを貼る。変化の行（`policy_changed`）は固めた版と比べる。修正前の関所で方針の変化を通した時に固め直す今の能力（`lib/boardview.py` の `_frozen_policy` と `take_gate_answers`）は残し、固め直した版を後の段も読む。元 `works/.shared/core/policy_input.py:61` `resolve`。
5. 版の控え（L-E45・L-E46。S56）: 分からない値は null にし `unknown` に訳。拒む run でも控えを残す。今の `versions` の欄（Archon の commit と Claude Code の版）に、元の `works/.shared/core/versions.py` の欄のうち Archon の上でも取れる物を足す。取れない物は欄ごとに訳を書く（Archon で不可なら源の行）。
6. 認証の要らない起動の名（L-E15）: `lib/entryshape.py` の `NO_AUTH_ENV` を、殻が立てる `WORKS_FACTORY_NO_AUTH`（`bin/_lib/launcher.py:50`・`bin/_lib/auth_launch.py:155`）に合わせる（殻 `bin/` は触らない）。
7. spec の拒み（L-E29）と PR の本文（L-E17）: `request_text` の既定の文で空を隠さない。PR の題と本文は始めの記録の `input.pr` に載せ、judge の目的の材料が読む。
8. 報告はいつも走る（L-W60）: 前の段とブロックの返す節が落ちても報告が回る。resume で報告の節が回し直されるかは筋書きで確かめられないので、試験は YAML の節の条件を照らし、本物の確かめは段 1 に書き送る。
9. 線の返りに欄を足す（issue #101 の `bin/apply` と段 1 が読む）: 線の返す節 `result` に `apply`（`merge-apply` の返りの `ok`・`hash`・`diff`・`reason`。飛ばされたら null）・`sealed`（`merge-seal` の `ok`・`hash`・`diff`。飛ばされたら null）・`r2_status`（eyes の `r2.status`。省いた・飛ばされたら null）・`report`（report の返りの `report`）・`final_answer`（`answer-final` の `answer`。関所が開かなかったら null。`bin/apply` の M43）。`result` は `$collect.output.<欄>` だけを読み、`collect` に無い欄は足す（`result` から `merge-*` を直に読むと線の返りが落ちる道が増える）。筋書き `standard` は `apply.ok` が真で `sealed.hash` と `apply.hash` が同じ、`final-stop` は `apply` が null で `sealed` が在ることを照らす（今ある筋書きに照らしを足す）。`docs/design.md` の約束に「線の返り」の節を足す。
10. CI の赤を次の依頼へ運ぶ口（L-D54。元 `carry-ci`）: `lib/carry.py` の `carry_ci` を口として呼べるようにし、同じ行は 2 度足さず形が違えば止める。呼ぶのは人なので、`README.md` の使い方に 1 行。
11. 役の文の言語の 1 行（L-E37）: 始めの記録の `lang` を、判定の役（judge の全部の役の節）と報告の書き手の役にも届け、今の works の 1 行（人が読む欄〔関所と報告に載る文〕だけその言語で書き、key・enum・識別子・パスはそのまま。元 `works/.shared/core/rolekit.py:67-68` `LANG_RULE`・`:147-150` `lang_line`）を役の文の頭に足す。plan・eyes・fix が今読む口と同じ口を使い、写しを作らない（K20）。持ち主の決め `lang-one`（人と話す所だけその人の言語）の当て方そのもので、言語を選ぶ仕組みは足さない（`lang` が空なら依頼文の言語。元 `works/.shared/core/board.py:96`）。試験は棚卸しの L-E37 の証と、report の書き手に同じ照らし。

受け入れ（部分 A）: 共通の決まりと、閉じる行の全部が PR 本文の行の表に在る。筋書き `rejudge-stop`（新しく足す）・`standard`・`final-stop`（今ある物に照らしを足す）が通る。

## 部分 B1 関所の答えと直す義務

目的: 関所の答えの形を 1 つにし、答えた問い・答えていない問いで直す義務を戻し・外す数えを今の works に戻す。無人の run の止まり方と、plan-review への配線を戻す。

閉じる行:

- L-G27〔試〕無人で設計だけの run は、関所で止まって報告へ進む
- L-G29〔戻・試〕定石から外れた項目と、構造の目が上げた設計の問いは関所で 1 度だけ聞き、人が continue した同じ文は聞き直さない
- L-G32〔無・戻・試〕関所で答えた問いの出どころ・depends は直す義務に戻り、修正役に「答えで直す義務に戻った単位」の行（returned_lines）が届く
- L-G33〔無・戻・試〕答えの無い問いの出どころは直す義務から外す（withheld）。無人の run でもそうして修正へ進む
- L-G34〔戻〕依頼の answers は、key か出どころの字の一致で 1 つの問いだけに当たる時に答えとして数える。判定の結び（answer_ties）と測れていない素材の名も読む
- L-G38〔戻〕無人の run は台帳の問いだけでは修正前の関所を開かない（問いは報告へ回す）
- L-G39〔戻〕無人の run で関所を開くはずの時は、開かずに止めて報告へ進む（元は殻が stop を答えた）
- L-G40〔戻・試〕無人の run の修正前の関所は、聞くはずだった項目（狭め・事前審査の穴・方針の文書の変化）を見落とさずに止まる
- L-W14〔戻・試〕修正前の関所の一言を字のまま修正役に届け、関所で答えた問いで直す義務に戻った単位も届ける
- L-W45〔無・戻・試〕案の直しの事前審査に申し出と裁定・修正前の関所の答えを貼り、通した行を聞き直さない
- L-D24〔試〕案の直しの役に、裁かれた項目（ruling）と申し出・裁定の文（conflicts）を渡す
- L-D25〔無・戻・試〕案の直しの事前審査（replan-review）に申し出と裁定の行（conflicts）を渡す
- L-D26〔無・戻・試〕事前審査に修正前の関所の答え（gate_answers）を渡し、通した行を聞き直さない
- P001〔戻〕判定の開いた単位（block か、suggest で do-now）から、答えていない関所の問い（held・escalate の fork と、escalate の問い）の出どころ・depends を除いた物を「直す義務の単位」にする。
- P002〔無・戻・試〕修正前の関所で人が答えた問い（gatemarks.returned）の出どころを義務に戻し、直す裁定でない裁定（held_by_rulings）の単位を義務から外す。
- P010〔戻〕必ず入れるのに開いていない単位（行き止まり）が在れば、役を起こさずに止め、理由 PLAN_STUCK に no と key を書く。
- P139〔戻・試〕案の直しの事前審査の申し出と裁定の行は、線が渡す conflicts（fix の conflicts.json）から引く
- P152〔試〕線が conflicts と gate_answers を渡さない（#74 の head の線は plan-review の 2 つの差し込みのどちらにも渡していない）ので、案の直しの事前審査に申し出と裁定の文が載らず、修正前の関所で人が通した行が次の差し込みで聞き直される
- P236〔戻〕無人の run では台帳の問いの行を関所に載せない（問いだけで関所を開かず、修正を飛ばさない）。狭めの在る関所は今どおり開く
- P240〔戻・試〕escalate の問いも fork と同じ 1 つの決まりで、答える前は出どころを直す義務から外し、無人の run でも外し、保留の問いと答えた問いが同じ出どころを持てば戻した単位を保留の行の「答えが無いと直さない単位」に並べない。関所の項目が名指す単位・外れる単位・戻る単位が同じ
- P241〔戻・試〕直す義務の数え（開いた単位 − 答えの無い問いの出どころ・depends ＋ 関所で答えた問いの出どころ・depends − 直さない裁定の単位）が、関所の continue を受けると戻る
- P243〔戻・試〕素材の名で答えた依頼の答え: field の問いは素材の名で答えられ、key の頭の一致は語の境と測れていない素材を要し、問いの無い素材への答えは名指しの対象にしない。命令と出力つきの答えは素材を「人が手元で確かめた」と閉じ、複数の問いに当たれば閉じない。測れている素材への答えは名指す
- P244〔試〕修正前の関所の答え（入力 gate_answers {decision, text, asked}）を gatemarks が読む human_items の行に積み（approve は continue に揃え、同じ行は積み増さない、種類は前の差し込みが返した項目の控え gate-asked.json から引く）、人が continue で通した行（狭め・穴・世界の解の外れ・構造の設計の問い・設計だけの行・止まりの行・台帳の問い）を次の差し込みで聞き直さない
- P250〔戻・試〕関所の項目の種類（regression・policy・policy_changed・fork・escalate・world・design・design_only）を関所の文の冒頭（何の項目が何件か）・台帳の問いへの答え方の段落（ASK_GATE_HEAD）・無人の run の振る舞いに使う
- F225〔戻・試〕関所の continue を問いへの答えに数えるには、関所の答えに「人が見た関所の行」（asked）が要る。線はこれを fix の answers に付けて渡す
- F226〔縛り済み〕直す裁定でない裁定（ask_human・fix_plan_item）を受けた単位は、決まり 1 つ（held_by_rulings）で直す義務から外し、理由を並べる。人に回した単位を直そうとした返答は外れた理由を名指して拒む
- R77〔無・戻・試〕判定の answer_ties（依頼の答えを問いや単位に結ぶ行）と、単位に結んだ答えを修正役へ渡す行・結ばないと判定が名乗った答えの訳の行（answer_tie_lines）
- J109〔無・試〕依頼の答えの結び answer-ties.json を報告が読み、どの問いにも当たらなかった答え・判定が単位にしなかった作り直しの行（none の訳）を人に出す

やる事:

1. 関所の答えの形を 1 つにする（S46・S22・P241・P244・F225）: 返しの節 `gate_answer` の返りを `{decision, text, asked}` にする。`asked` は、その関所が人に見せた項目の行（`ask-before-fix` が組んだ行。項目を持たない関所と開かなかった関所は `[]`）。fix の `answers`・plan-review の `gate_answers`・eyes の `answers` に同じ形を渡す。答えに `asked` が無い時の読み方を読み手ごとに持たない（今の `lib/boardview.py` の `take_gate_answers` が `asked` の無い答えを別に読む道は消す）。
2. 直す義務の戻しと除き（L-G32・L-G33・P001・P002・P010・P240・P241。S18）: 答えの無い問いの出どころと depends は直す義務から外し（無人の run でも）、関所で答えた問いと依頼の answers が当たった問いの出どころは戻す。この数えを lib の 1 つの口（元 `works/.shared/core/gatemarks.py` 1149-1169 行 `pending`・`withheld`・`returned`）に置き、plan（1 回目の周の直す義務と行き止まり `stuck_reason`）と fix（`lib/fixboard.py` の `fix_duty`）が同じ口を呼ぶ。plan に関所の答えは要らない（行き止まりの判定は 1 回目の周で走り、届くのは始めの記録の依頼の answers だけ。plan は始めの記録を既に受ける）。plan と fix の義務の集合が食い違うと fix の受け付け `check_opened_units` が NOT_OPENED で拒むので、両方を同じ入力で照らす試験 `lib/tests/test_gatemarks.py::DutyCase.test_plan_and_fix_get_the_same_duty` を置く。
3. 依頼の答えの当て（L-G34・R77・J109・P243）: 同じ当ての式が今 4 か所に在る（`lib/gatemarks.py` の `answer_binds`・`origin_of`・`unmeasured`、`lib/outcome.py` の `answer_binds`・`origin_of`・`material_answer`・`measured_materials`、`lib/judge_accept.py` の `answer_binds`・`origin_of`、線の `ask_final.py` の `binds`）。`lib/gatemarks.py` を、問い・結びの行・素材の状態を値で受ける 1 本に直し、ほかは呼ぶだけにする（K20。judge の受け付けは今の `answer_rows=()` の呼び方を保つ）。判定の `judgment` の隣の `answer-ties.json`（`{"rounds": {"1": [...]}}`）と `materials.json` を読む。再審の `judgment` の隣には `answer-ties.json` が無いので、`ask-final` に judge の差し込みの指し札を渡す `with:` を足す（`ties_judgment: $judge.output.judgment`）。結びの宛て先の key が再審の後の問いに無い時は字の一致に落とし、当たらなかった結びを関所の文に 1 行出す。`answer-ties.json` が無い run では今の字の一致のまま（落ちない）。
4. 無人の run（L-G38・L-G39・L-G40・P236・P250・L-G27・L-G29）: 無人の run は台帳の問いだけでは関所を開かず報告へ回すが、狭め・事前審査の穴・方針の文書の変化・事前審査の諦めが在れば止まる（`works:needs-human`）。そのため plan-review の返り `questions` の行に項目の種類を残す（今は落ちる。棚卸し P250）。返りの欄の形を変えるので `docs/design.md` も直す。
5. plan-review への配線（L-D24・L-D25・L-D26・L-W45・P139・P152。S21・S22）: `replan-review` に `conflicts: $fix.output.conflicts` と `gate_answers: $answer-before-fix.output.answer` を渡す。往復の中の `plan-review-run` には渡さない（修正前の関所より前に走るので、答えはまだ無い）。部分 0 の `UNPASSED` の表から `replan-review` の 2 行を消す。
6. 他のブロックの鍵の照らし（S20）: `lib/tests/test_cross_block_keys.py::CrossKeysCase.test_plan_reads_what_judge_review_fix_write`。judge・plan-review・fix の書き手の関数で作ったファイルを plan の読み手（`lib/planfile.py`）に通す。合わない鍵は直す。

受け入れ（部分 B1）: 共通の決まりと閉じる行の表。新しい筋書き `unattended-questions`（問いだけの無人の run で、出どころの単位が直す義務に入らず修正へ進む）・`unattended-policy-change`（方針の文書の変化だけの無人の run が止まる）を足して通す。今ある筋書き `replan` に、`replan-review` に申し出の指し札と関所の答えが届く照らし（`resolved-text-contains`）を足す。

## 部分 B2 修正前と最後の関所の文

目的: 修正前の関所と最後の関所に並べる物・開ける理由を今の works の並びに戻す。

閉じる行:

- L-G19〔戻・試〕聞かずに通した行（と R4 で聞き直さなかった行）を、報告と最後の関所の文の両方に 1 件 1 行で載せる
- L-G21〔戻・試〕関所の項目の種類（regression・policy・policy_changed・fork・escalate・design・world・design_only）を平易な名で頭に並べ、台帳の答え方（ASK_GATE_HEAD）は台帳の問いが在る時だけ出す
- L-G23〔試〕問いの文は記録のまま引用し、読み替えの行（QUOTE_NOTE）を添える
- L-G25〔戻・試〕関所の文と報告の主語は平易な名で、盤面の節・目・状態の語は括弧に回す
- L-G31〔戻・試〕key を拾えなかった「保留」の文を「読めなかった保留」として報告の冒頭と最後の関所に並べる
- L-G37〔戻・試〕最後の関所と報告に、答えた問い（ANSWERED_HEAD）とどの問いにも当たらなかった依頼の答えを並べる
- L-G44〔戻・試〕案の直しの関所の文: 項目ごとに約束の欄の変化・人に聞く穴・申し出の文・裁定の文・前と後の項目の JSON
- L-G45〔戻〕無人の run は範囲を広げるだけの直しを聞かずに通し、足した・外した glob を trace と報告に残す
- L-G47〔戻〕2 度目の修正には、修正前の関所の条件と案の直しの関所の一言を見出しの下に並べて渡す
- L-G48〔戻〕最後の関所を開ける理由の列（1 件 1 句）。開くかと 1 行目は同じ列から作る
- L-G49〔戻〕守りのパスに当たった・確かめられなかった時と申し出は、開き方に依らず最後の関所を開き、1 行目と最初の節で名指す
- L-G50〔試〕守りのパスか申し出が在るのに最後の関所が開かなかった run は、差分を当てずに止める
- L-G51〔戻・試〕最後の関所の文の本文（テストの一式とログ・修正前のテスト・手元で回さなかった試験・差分の審査の穴・手直しの結果・再審で決着した結果・往復・残りの件数・例で試していない単位・数え直しの表・案の直しの項目の行）
- L-W24〔試〕申し出は人に回した行（ask_human と案の直しを諦めた行）だけを数え、関所の文に単位ごとの行（conflict.human_lines）を並べる
- L-W28〔無・戻・試〕最後の関所の文に、最後のテストの一式・修正前のテスト（baseline_line）・ログ・走れなかった理由・作業ツリー・手元で回さなかった試験・赤緑を確かめずに通した回を並べる
- L-W29〔無・試〕最後の関所の文に、差分の審査の穴の数（1・2 回目）・穴と目の行の枝の名札・手直しの結果を並べる
- L-W30〔無・戻・試〕最後の関所の文に、決着した再審の結果（rejudge_lines）を並べる
- L-W31〔戻・試〕最後の関所の文に、直した後の実測（数・柵の増え・新しい名・修正案の外れの訳）を並べる
- L-W32〔無・戻・試〕最後の関所の文に、修正前の関所で通した項目（gatemarks.lines）と事前審査の往復（converge.lines）を並べる
- L-W33〔試〕最後の関所の文に、独立の目の行（平易な名）と R2 に渡した前提・渡していない物・「渡されていない」と言われた物・独立設計の後に来た答え・落ちた筋を並べる
- L-W34〔無・戻・試〕最後の関所の文に、clean が消したファイル・レンズ・仕組みの異常・残りの件数・持ち越した単位（split_line）・例で証明できない単位・数え直しの表・止まった単位・同じ run で直した案の項目（replan.AMEND_HEAD）を並べる
- L-W35〔戻・試〕最後の関所の文に、人に聞いている問いを記録のまま引き「この関所の答えは問いに答えない」と添える
- L-W36〔戻・試〕保留の問いと答え方を並べ（開ける理由には数えない）、答えた問い・当たらなかった依頼の答え・読めなかった保留も並べる
- L-W37〔試〕最後の関所の文の控えを置き場に残し（final-gate.md）、message はそのパスを名指す
- L-D19〔戻・試〕壁打ちが止まった案は修正前の関所を必ず開け、行は 1 つで尾に止まった理由（続いた block の key と往復の数）を付ける
- L-D31〔戻・試〕案の直しの関所の文に、項目ごとの申し出の文・裁定の文・前と後の項目（JSON）を見せる
- P238〔戻・試〕key を拾えなかった「保留」の文と並べ書きの打ち間違いの key を「読めなかった保留: …（答えたものとして推しで直す問い: …）」の行にして、報告の冒頭と最後の関所の文に並べる（直す義務は変えない）
- P249〔試〕関所に載る行は 1 件 1 行で重ならない（設計だけの行と止まりの行は 1 行、決め手の揃わない行の訳は行の尾に 1 度）
- P255〔戻・試〕最後の関所の文と報告の冒頭に、関所で答えていない台帳の問い（fork でない awaiting も）を「無い」と書かずに並べ、関所で答えた問いは保留の件数に数えず答えた行に並べ、決め手で通した行も並べる
- F426〔戻・試〕最後の人の関所に、人に回した食い違いの申し出（ask_human と、案の直しを諦めた fix_plan_item）だけを、裁定の文・名指し・種類・正しいと見た側・id の 1 行ずつで並べ、それが在る時だけ関所を開ける
- T35〔無・戻・試〕一式の行と修正前のテストの行を、最後の人の関所の文と報告の冒頭に字のまま出す（何を根拠にした緑か・最後の赤が修正前から在りうるかを、ファイルを開かずに人が見る）。
- T41〔無・戻・試〕自己申告の緑・走らせなかった CI を人に諮る時、「engine が走らせた結果ではない。走らせる語を宣言 .review-checks.json に書けば次から engine が走らせる」と次の手を添え、確かめて続けるか止めるかを聞く。
- M29〔無・戻・試〕守りのパスの節に、差分の見方（`git -C <作業ツリー> diff <起点> -- <パス>`）と一覧の置き場を書く
- M30〔無・戻・試〕承認済みの案と裁定が書き換えを許したテストのファイル（許したテストの変更）を触った run も、守りのパスと同じに扱う: 関所を開き方に関わらず開き、答えが無ければ置かない
- M38〔無・戻・試〕差分の中で消えるファイルを、当てる前に 1 本ずつ名指す（「取り込むと消えるファイル: <パス>」）

やる事:

1. 最後の関所の開ける理由と 1 行目（L-G48〜L-G50）: 開ける理由の列と 1 行目を同じ列から作る（元 `works/darkfactory/lib/line_edge.py` の `_final_needs`）。守りのパスに当たった・確かめられなかった・書き換えを許したテストに触った run は、開き方に依らず開き、答えが無ければ差分を置かない（M30・L-G50）。
2. 申し出（L-W24・F426。S55）: `lib/conflict.py` の `asked(<フォルダ>)` で人に回した行だけ数え、文は `human_lines(<フォルダ>)` をそのまま使う（1 回目と 2 度目の修正の両方の控え）。読めない控えは黙って 0 にせず、訳を関所の文と開ける理由に出す。
3. 最後の関所の本文（L-G51・L-W28〜L-W37・T35・T41・M29・M38・P238・P255）: 棚卸しの各行の元の節の並びに戻す（一式と修正前のテストの行・手元で回さなかった試験・再審の結果・修正前の関所で通した行・独立の目の行・人に聞いている問い・保留と答えた問い・控え `final-gate.md`）。
4. 修正前の関所の文（L-G19〜L-G25・L-G31・L-G37・L-G44・L-G45・L-G47・L-D19・L-D31・P249）: 棚卸しの各行の元の文の形に戻す（項目の種類の平易な名・問いの引用・読めなかった保留・案の直しの関所の項目ごとの行・無人の run で聞かずに通した直し）。
5. 元の試験を元の名で写す（S27）: `test_branch_rows_in_final_text_and_head`・`test_held_questions_are_listed_not_none`・`test_answered_question_is_not_counted_as_held`（元 `works/tests/test_plan_gate.py`）を `tests/workflows/test_gate_head.py` へ。元の試験が今の形で呼べない所は、写した字の差を PR 本文に並べる。

受け入れ（部分 B2）: 共通の決まりと閉じる行の表。今ある筋書き `conflict-ask` に照らしを足す: 裁定が直す裁定だけの申し出では最後の関所が開かず、`ask_human` の行が 1 つ在れば開いて文にその行が出る。

## 部分 C 報告へ届ける物・深さ・往復・判定の隣のファイル

目的: 線とブロックが持っているのに報告に届かない値を届け、深さの上げ直しと往復と案の直しの行を報告と最後の関所に戻す。

閉じる行:

- L-W39〔戻・試〕無人の run では、関所を開くはずの時に止め（needs-human）、問いと聞かずに通した直しを報告へ回す
- L-W42〔戻・試〕再審の前後の比べ（後に開いた単位・block から下げた単位・異議が名指さずに変わった単位）を報告へ渡す
- L-W51〔無・戻・試〕深さを上げ直した行を報告の冒頭 2 に出す
- L-D04〔試〕計画の段の深さを修正へ、2 度目の修正には直した案の深さを渡す
- L-D08〔戻・試〕上げる信号「答えていない問い」（元は gatemarks.pending で問いごと、判定の保留の問いも含む）
- L-D10〔戻・試〕run 全体の広さで上げる（計画の allowed_paths と実際の差分のファイルの和集合とテストの本数。数えた数と起点を counted に残す。軽量の名指しでも上げる）
- L-D11〔試〕全部の単位が軽量のままの run は、独立の目の削除候補と R1〜R4 を省く
- L-D12〔試〕全部の単位が軽量のままの run は、差分の審査とレンズ・手直しを省く
- L-D13〔戻・試〕報告の冒頭 2 に深さの行（単位ごとの数・標準へ上げた信号・run の広さの数え・軽量で省いた物）
- L-D15〔戻・試〕案の直しの後の深さ（元は全部の単位の控えを残して上げた）
- L-D17〔試〕2 周目の plan は前の周の事前審査の返り（review）を受けて案を直す
- L-D22〔無・戻・試〕往復ごとの行（何往復か・抜け方・続いた block・suggest に下げた key）を報告に出す
- L-D29〔戻・試〕無人の run は範囲を広げるだけの直しを聞かずに通し、trace（WIDEN_OP）と報告の行（WIDEN_LINE）に残す
- L-D39〔無・戻・試〕同じ run で直した項目ごとの結果（承認・聞かずに通した・無人で広げた・諦めた理由・未完了）を最後の関所と報告の冒頭 1 に出す
- P119〔戻・試〕往復の報告の行（何往復・抜け方の語・続いた block・往復ごとの block と答えの数・項目の閉じた/開いた/保留・相乗りの block）を報告の冒頭に載せる
- P145〔戻・試〕無人の run で範囲を広げるだけの直しを聞かずに通した時、trace に `replan_widened_unattended` を 1 度だけ書き、報告に「直した——無人の run なので人に聞かずに範囲を広げた（…）」の行を載せる
- P146〔無・戻・試〕報告と最後の関所の文に、案の直しの項目ごとの 1 行（直した——人が承認した／聞かずに通した（手段の欄だけ）／直さずに諦めた: 訳／未完了）を見出し AMEND_HEAD の下に並べる
- P161〔戻・試〕目的の監査が「狭めている」と言い、その findings が全部裏取りの柵（cite）を通っている時は独立設計を回さない（素の文字列の findings では止めない）
- R5b〔無・戻・試〕線の節が返す止めの語（works:line-script・works:needs-human・redepth の止め）を結末に入れる
- R14〔戻〕独立の目の阻害（redesign-needed・unverifiable）を目ごとに 1 行。深さで省いた目（null）は数えず、目のブロックが ok: false で数えた目が無ければ 1 行
- R20〔無・戻・試〕残りの件数の行を結末に依らず常に出す（0 件も。走っていない目・結果の無い目の注記つき）
- R24〔無・戻・試〕同じ run の中で直した修正案の項目の行
- R35〔無・戻・試〕事前審査の壁打ちの往復の行（往復の数・結末・残った key と、往復ごとの block・fixed・disputed・下げた key・項目の閉じ・開き・保留）
- R36〔無・戻・試〕独立設計が問いは立たないと返したのに根拠にパス:行の名指しが無い 1 行
- R41〔無・戻・試〕段（thickness）・機能の on/off（features_off・features_on と既定）・決めた人（関所の答えの数）・forge が無い時の並行 PR の条件外
- R74〔無・戻・試〕直した後の深さの上げ直しの行（depth_lines）
- R75〔無・戻・試〕方針の文書が始めに固定した版から変わったまま終わった run の行（書き手の指示書の構成 2 の 3 つ目）
- R76〔無・戻・試〕再審の行の往復の数と周の名（rejudge-exit.json の verdicts の並び）
- R78〔無・戻・試〕受け付けの最後の拒否の本文を前の失敗に運ぶ（元 accept-last.json の reason_file）
- R79〔無・戻・試〕世界の解の段が落ちた訳と落とした抜き書きの数（world-state.json の reason・dropped）
- R80〔無・戻・試〕並行 PR の担当への申し送りの下書き（conflicts[].note。投稿していない）
- J41〔無・戻・試〕並行 PR を投稿しない形に下げたことを宣言し（`downgrades.json` の p0.parallel_pr と r2.design）、報告の頭に「下げている所: N 個」を出す
- J110〔無・戻・試〕局所レビューで見ていないレンズ（local-review-lenses.json）を報告の「未確認のレンズ」の節に出す
- J111〔無・戻・試〕並行 PR の申し送りの下書き（pr-downgrades.json）を報告の冒頭に出す（担当の PR に人が渡す）
- J112〔試〕世界の解の段の控え world-state.json の status・reason・dropped を報告に出す（段が落ちた訳・網が無かった・落とした抜き書きの数）
- T45〔無・戻・試〕3 回とも拒まれて諦めた時、最後の拒否の文を人に見える所に出す（元は盤面の止まりの理由「<節> の返答が 3 回とも受け付けで拒まれた（最後の拒否: …）」）。
- M37〔無・戻・試〕報告（か run の終わりの案内）に、差分を対象へ当てる 1 行（`bin/apply <run-id>`）を出す。記録が止まりの run には生の `git apply` の行を出さず、止まりの 1 行（結末の語・止めた人・一言）を出す
- R82〔無・戻・試〕受け止めた落ちの決め方（元は線の YAML の [optional] の宣言と出口の印。今は落ちた後にほかの節が始まったか）

やる事:

1. report の入力（S30・S48〜S53・R5b・L-W39・L-W42・L-W51）: report に既定値つきの入力を足し（K11）、線の `collect` が渡す: 線の止めの語（部分 0 の `lib/stopby.py` の定数で `outcome.decide_outcome` に入れる。`works:start-refused` → `stopped_by_line`、`works:needs-human` → `needs_human`、`human:<関所>` → `stopped_by_human`）・`prior_failures`・`deferred`・`widened`・`final_reasons`・`judged`・`redepth`・`refix`（2 度目の段の行。`fixed` が 1 回目と合わせた物）。
2. 再審の前後の比べは判定の書いた物を読む（K20。R76）: 同じ数え（`new_open_units`・`lowered`・`unnamed_changed`）が今 3 か所に在る（線の `judged`、`lib/runreport.py` の `rejudge_lowered`・`rejudge_changes`、`lib/judge_accept.py` の `diff_units`・`rejudge_collect`。最後の物が再審の置き場の `rejudge-exit.json` を書く）。`rejudge-exit.json` を再審の `judgment` の隣の約束のファイルにし、線の `judged` と report はそれを読むだけにして、自分の数えを消す。往復の数と周の名も同じファイルから出す。
3. 深さ（L-D04〜L-D15・R74・L-W51）: 上げる信号を元に戻し（L-D08 答えていない問い・L-D10 run の広さ）、報告の冒頭 2 に深さの行（元 `depth_lines`）を出す。
4. 往復と案の直しの行（L-D22・L-D29・L-D39・P119・P145・P146・R24・R35）: 報告の冒頭と最後の関所に戻す。
5. 判定の隣のファイル（J41・J110・J111・J112・R79・R80・P161。S25・S31・S41）: `judgment` の隣の約束のファイルに `world-state.json`・`purpose-review.json`（目的の監査。今は `lib/judge_accept.py:3015` が役の材料の中にだけ置く）を足し、judge は止めた時も空の形で書く。`answer-ties.json`・`local-review-lenses.json`・`pr-downgrades.json` と合わせて読み手を置く: report（見ていないレンズ・並行 PR の下書き・下げている所・世界の解の段が落ちた訳）と plan-review（目的の監査で独立設計を止める決まり `purpose_unusable`）。部分 0 の `NEIGHBOURS` の表と `docs/design.md` に足す。
6. `conflicts.json` の欄の名（S34）: `lib/runreport.py`・`lib/outcome.py` が自分の定数で読む所を `lib/conflict.py` から引く。
7. 残りの報告の行（R14・R20・R36・R41・R75・R78・T45・M37）: 棚卸しの各行の元の形に戻す。M37 の当てる 1 行は `bin/apply <run-id>`（issue #101）を名指し、止まった run には生の `git apply` の行を出さない。
8. 受け止めた落ちの決め方（R82）: 元の形（線の YAML で受け止める段を宣言し、宣言の外の落ちと出口の印の欠けた run の落ちは全部 `interrupted`。元 `works/.shared/core/report.py:533` `_optional`・`:545` `split_fallen`）に戻す。宣言の置き場は線の YAML の 1 か所（受け止める段の id の並びを report の既定値つきの入力で渡す。K11）にし、`lib/runreport.py:173-175` の「落ちた後にほかの節が始まったか」で決める道を消す。

受け入れ（部分 C）: 共通の決まりと閉じる行の表。今ある筋書き `start-refused`・`unattended-needs-human`・`final-stop` を本物の report で回し、結末の語が上の期待になる照らしを足す。

## 部分 D1 2 度目の修正と修正の入力

目的: 2 度目の修正が 1 回目の申し出と裁定を見られない・fix が事前審査の返答を受けない・機械の申し送りが 2 度目の修正に届かない・規模の数値と前提のずれが eyes に届かない、を直す。

閉じる行:

- L-W17〔戻〕案の直しの後の 2 回目の修正に、戻った単位だけ・差し替えた承認済みの案・直した項目から作り直した波及（無ければ 1 回目の一覧）・関所の条件と一言・採った項目の事前審査の穴を渡す
- L-W18〔無・戻・試〕2 回目の修正（refix）が 1 回目の申し出と裁定を見る（conflict.second_pass）。1 回目に裁定 fix_test_scope で直したテストを 2 回目の関門が許す
- L-W19〔無・戻・試〕修正役が事前審査の返答（faces・shrink）に plan_faces で key ごとに 1 度だけ答え、答えない key を機械が拒む。差分の審査役も out.p2.plan_review を受ける
- L-W48〔戻・試〕2 回目の修正の段で新しく fix_plan_item と裁いた行は、段を抜ける時に「諦めた行」にし、最後の関所の申し出に並べる（replan.settle）
- L-W57〔無・試〕eyes に修正役の規模の数値 x_scalars と前提のずれの申告文を渡す
- L-D35〔無・戻・試〕採った項目の事前審査の穴のうち人に聞く種類でない物（FACES_HEAD）を 2 度目の修正へ渡す
- L-D36〔試〕2 度目の修正の直す義務は、案を直して戻った項目だけ
- L-D38〔試〕2 度目の修正でまた案の誤りと裁かれたら、案の段には戻らずに諦め（CLOSE_WHY）、人に回す行にする
- L-D42〔無・戻・試〕2 度目の修正（refix）が出した異議も、再審と最後の関所に届ける
- F018〔戻・試〕輪をまたぐ凍結: 2 回目の修正の段（案の直しの後）の修正役も、1 回目の段の輪が凍らせたテストを変えられない。ただし案を直した項目の単位の、前の輪の受け入れのテストの関数の中だけは通す
- F023〔戻・試〕案を直して直す義務に戻った単位が、また TDD の確認の上限まで落ちたら、裁定に回さず ask_human（by tdd-repeat）で人に上げる（2 回目の機械の諦め）
- F044〔戻〕2 回目の修正の段の事後の関門は、1 回目の段の裁定 fix_test_scope の範囲の直しをいつも許す（conflict.second_pass で引く）
- F216〔戻・試〕2 回目の修正（線の include `refix`）が 1 回目の修正の申し出と裁定を見る（conflict.second_pass）: 1 回目の段で fix_test_scope の範囲として許したテストの変更を 2 回目の段の事後の関門と凍結も許す、2 回目の段で新しく fix_plan_item と裁いた行に「最後の人の関所で決める」の約束（LATE_REPLAN_PROMISE）を出す、直した項目の単位の前の輪の受け入れのテストを許す（AMENDED_TEST_ID）
- F130〔無・戻・試〕修正案の事前審査の穴（faces）と別案（shrink）に、修正役が plan_faces で key ごとに 1 度だけ答え（absorbed / declared）、答えない key・余る key・重複を機械が拒む（元 `_plan_face_errors`）
- F302〔戻・試〕差分の審査役の材料の `out.p2.plan_review`（事前審査が予測した穴 faces・別案 shrink）が、本物の run では常に null。そのため 1 回目の審査の検算（修正役が absorbed と答えた事前審査の穴が差分で本当に塞がったか。checks）は 1 件も起きず、手直しの brief の名札（hole_ties）からも事前審査の穴が落ちる
- P144〔戻・試〕2 度目の修正に渡す答えの文: 修正前の関所で人が答えた条件・案の直しの関所の一言に加え、採った項目の事前審査の穴のうち人に聞く種類でない物を見出しつきで渡す
- E17〔戻・試〕修正役が足した x_ の数値（x_scalars）を規模の数値に足し、形の外の欄（x_ で始まらない名・数でない値・object でない）は名指して落とす。
- E42〔戻・試〕前提のずれの申告の本文（premise_drift_note）を比較役の頭に貼る。

やる事:

1. 2 度目の修正が 1 回目の申し出と裁定を見る（L-W18・F018・F023・F044・F216。S01）: fix に入力 `prior_conflicts`（既定 `"null"`）を足し、線の `refix` に `prior_conflicts: $fix.output.conflicts` を渡す。fix は `conflict.second_pass` と凍結・2 回目の機械の諦め（`ask_human` の `tdd-repeat`）・事後の関門をこの入力で引く。1 回目の置き場のファイルをパスで開かない（K14・層の E4）。
2. fix が事前審査の返答を受ける（L-W19・F130・F302。S02）: fix に入力 `plan_review`（既定 `"null"`。plan-review の返りの `review` の指し札）を足し、線の `fix` に `$plan-rounds.output.review`、`refix` に `$replan-review.output.review` を渡す。fix の受け付けに `_plan_face_errors`（元 `review-loop.py:3115-3128`。事前審査に無い key・答えの無い key・重複を拒む）を戻し、差分の審査役の材料 `out.p2.plan_review` を埋める（`delta_cut.py`・`refix_prep.py`・`refix2_prep.py` の `plan_review=None` を消す）。修正役の指示書 `workflows/fix/commands/fix-rules/direct.md` の 10・95 行（元の字）が言う事前審査の返答の読み方を戻し、`tests/workflows/test_fix.py::ShapeCase.test_direct_rules_are_the_original_with_only_the_allowed_edits` と `tests/workflows/prompt_contracts.json` の direct.md の約束で縛る（K9。初見の読み手での書き直しは、元の字に戻さず許した直しとして足す。持ち主の決め `prompts-coldread`）。
3. 2 度目の修正に渡す機械の申し送り（L-W17・L-D35・L-D36・L-D38・L-W48・P144。S58 の 3 つ目）: 案の直しの事前審査の穴のうち人に聞く種類でない物（`lib/boardview.py` の `HUMAN_FACE_KINDS` の外）を、直した項目ごとの見出し「## 直した項目 {item}（単位 {units}）の事前審査の穴」の下に `- [kind] key（where）: why` で並べる（元 `works/.shared/core/replan.py` の `_notes` の 3 つ目）。人の答え `fix_answers` には混ぜない（fix は `answers` の `text` を人の関所の条件として読む）。`answer-replan` に返りの欄 `fix_notes`（無ければ `""`）を足し、fix に入力 `notes`（既定 `""`。修正役の材料に機械の申し送りとして貼る）を足して `refix` に渡す。`replan-review` が飛ばされた・読めない時は訳を 1 行書く。出すのは今の works と同じく採った項目だけ（関所の答えは今の works でも 1 つの語で、聞いた項目の全部に効く: 元 `works/.shared/core/replan.py:734` の `taken` は、聞かない項目と、continue の時の聞いた項目）。項目ごとの諦め（計画の役・事前審査の諦めと答えの無い項目。P142）は区分 P の issue が戻すので、それが入るまでは直した項目の全部が採った項目になる。`refix` の `only_items` が JSON の配列として読めることを筋書き `replan` で縛る（S44）。
4. 規模の数値と前提のずれ（L-W57・E17・E42。S09・S10）: fix の返りに `x_scalars`（object。`x_` で始まる名 → 数。無ければ `{}`。組ごとの値は名ごとに足す）を足し、`changed` に `premise_drift_note`（string。無ければ `""`。組の順に改行でつなぐ）を足す。線の `fixed` で 2 度目の値を優先して合わせ、eyes に `x_scalars: $fixed.output.x_scalars` を渡す。部分 0 の `UNPASSED` から消す。`docs/design.md` の fix の返りに 2 つの欄を足す。
5. 再審への異議（L-D42）: `refix` が出した異議も、再審と最後の関所に届ける。

受け入れ（部分 D1）: 共通の決まりと閉じる行の表。今ある筋書き `replan` に、2 度目の修正に `prior_conflicts`・`plan_review`・`notes` が届く照らし（`resolved-text-contains`）を、`standard` に eyes の prep に `x_scalars` が届く照らしを足す。

## 部分 D2 修正の隣のファイルと目の材料を関所と報告へ

目的: fix と eyes の置き場には在るのに人に届かない物（受け入れた壊れ・数え直し・手直しの名札・レンズ・回さなかった試験・目の前提の材料）を、最後の関所と報告に届ける。

閉じる行:

- L-W07〔無・戻・試〕直す物が無い周も周を締める（独立設計だけを作り、最後のテストを走らせ、R2 で「直す物が無い」判定を確かめる）
- L-W08〔戻〕判定の開いた単位を構造の目の入力 {id, paths, summary} に写し、パスの取れない単位・捨てたパスを記録に残す
- L-W09〔無・戻・試〕構造のブロックが落ちても計画は進み、最後の関所に「構造のブロックが落ちた（理由）」と出す
- L-W10〔試〕判定の単位の裏取りの申し送り（judge-verify.json）を修正案の役の指示書に貼る
- L-W20〔無・戻・試〕修正役が受け入れた壊れ（breaks.accepted）を人に回す（最後の関所を開け、節に並べ、報告の冒頭にも出す）
- L-W21〔無・戻・試〕「直した」という申告と機械の数え直しが合わない単位が在れば最後の関所を開ける
- L-W54〔戻・試〕直した後の構造の実測が落ちても線を止めず、failed と理由を残して最後の関所と報告に出す
- F013〔無・戻・試〕回さなかった試験を名前で残す: 受け付けが手元で回さなかった試験（ci_left）・最後のテストの段に任せた試験（final_left・final_far）を、受けた回の trace に載せ、最後の人の関所と報告に並べる（keep-essence 6 の後半）
- F041〔無・戻・試〕事後の関門が確かめずに受けた理由（unchecked。義務の外を除く）を、受けた回の trace の SKIPPED_OP の行に載せ、報告と最後の人の関所が「受け付け N 回・理由（同じ理由は 1 度）」で数える
- F312〔無・戻・試〕差分の審査の穴の名札を、報告と最後の人の関所に枝ごとの行として出す（report.branch_rows・holeties.count_line・holeties.lines）
- F329〔無・戻・試〕レンズの結果を報告に出す: 走ったか・読めたか・採った／採らなかった指摘の数・落ちたレンズ。落ちたレンズは次の run の依頼に「再実行の要あり」で運ぶ。見ていない観点の見出し（UNSEEN_LENS_HEADING）を立てる
- F427〔無・戻・試〕修正役が「壊すと分かって受け入れた」理由（changes[].breaks.accepted）を、報告の冒頭と最後の人の関所に 1 件 1 行で届け、在れば関所を開ける
- F428〔無・戻・試〕修正の受け付けの数え直しが修正役の申告と合わない単位（閉鎖の表の食い違い）が在れば、最後の人の関所を開けてその行を見せる
- E37〔戻・試〕検算で仮定が偽（resolved）なら、問いの一文 key を台帳に held で残し、実測 facts_to_add を制約に足して、次で R2 を回し直す。
- E45〔戻・試〕比較役が「渡されていない」と書いた文と、そのうち実は渡していた物（claims_given）と、R2 の 2 つの役に渡した前提の控えを、最後の関所の R2 の行の下に並べる。
- E66〔戻・試〕人が通したので R4 の問いから外した行を、通した印つきで残し、最後の関所と報告が「人が通した行」として並べる。
- E73〔戻・試〕実測の数の 1 文と、増えた所・新しい名・外れの訳を最後の関所と報告に並べる。柵の増えは関所を開ける理由にし、結末を fixed にしない残りに数える。
- R16〔無・戻・試〕判定の開いた単位が閉じたかを機械が数え直し、閉じていない単位（閉鎖の表の closed が偽）を残りに数える
- R23〔無・戻・試〕修正役が人に回した物（changes[].breaks.accepted。壊すと分かって通した理由）を人が決めることに数え、1 件 1 行で出す
- R29〔無・試〕修正の後に判定の問いで数え直した閉鎖の行（数が減っていない単位を先に・申告と合わない単位）
- R37〔無・戻・試〕修正の受け付けの事後の関門の束が赤緑を確かめずに通した回・はみ出しを相談で認めた／戻した・関所の条件の相談で認めた新しいテスト・守りのテスト、と範囲の相談の 1 問 1 答（回数と答えごとの数）
- R38〔無・戻・試〕clean が消したファイル（走らせていない・読めないを 0 件と分ける）・レンズ（見た・採った・捨てた・落ちたレンズ）・仕組みの異常の件数を結末に依らず常に
- R39〔無・戻・試〕落ちたレンズを次の依頼に「再実行の要あり」で運ぶ（控えが読めなければそれも）と、報告の「未確認のレンズ」の節（局所レビューの戻した・見ていないレンズを先に）
- R72〔無・戻・試〕盤面の trace から閉鎖を数え直す行（querytest.closure_lines・STUCK_HEAD）
- R73〔無・戻・試〕手直しの穴の名札（branch_rows・eye_ties・_tie_notes）と、手直しの handled の declared・2 回目の fixed の次の依頼の行

やる事:

1. fix の隣のファイル（L-W20・L-W21・F013・F041・F312・F329・F427・F428・R16・R23・R29・R37・R38・R39・R72・R73。S03・S28・S29）: 返りの欄は増やさず、fix の返りの `diff` の隣の約束のファイルにする: `handoffs.json`（修正役が受け入れた壊れ `breaks.accepted` の行）・`closure.json`（修正の後に判定の問いで数え直した閉鎖の表と、申告と合わない単位）・`delta-holes.json`（差分の審査の穴の名札と手直しの `handled` の行）・`lenses.json`（レンズの結果と落ちたレンズ）・`accept-trace.json`（受け付けの回ごとの選んだ試験の行 `[{op: "fix_tests_selected", node, pass, attempt, note, ci_left, final_left, final_far}]`。組の子の行は `group_id` も持つ。書き手は #121（PR #233）が足した。確かめずに受けた訳 `SKIPPED_OP` の行はまだ無い）。fix は止めた時も lib が読めない時も空の形で書く（K13）。読み手は最後の関所（開ける理由: 受け入れた壊れが在る・申告と数え直しが合わない単位が在る）と report。部分 0 の `NEIGHBOURS` と `docs/design.md` に足す。修正役の指示書 `common.md:10` の約束が本当になることを試験で縛る。
2. 目の材料（E37・E45・E66・E73。S12・S14）: eyes の返りに `notes`（指し札・null 可。eyes の置き場の `premise-inputs.json`）を足し、隣の `gate-passes.json`・`premise-check.json` を約束の隣のファイルにする（plan-review の `review` の隣の同じ名の `gate-passes.json` とは別物と `docs/design.md` に書く）。線の `ask-final` と `collect` を通して report まで届かせ、関所の文に「R2 に渡した前提と、渡されていないと言われた物」「人が通したので R4 で聞き直さなかった行」の節を足す。前提の検算の `facts_to_add`（実測の制約）と、偽と分かった仮定の問いの key（E37）は、最後の関所の文と報告に出す。`facts_to_add` は次の run の制約へも運ぶ（E37 の後半。S14）: 次の依頼 `next-request.json` に欄 `constraints`（`[{text, measured_how, kind: "実測"}]`。今の works が盤面の制約に足した行の形のまま: `works/.shared/core/graphloops/rules/review-loop.py:253-257`）を足す。書き手は report（`lib/carry`）、読み手は次の run の `start`（`lib/carry.py` の `parts` の鍵に足す。`findings`・`answers`・`prior_failures` と同じ 1 つの口）。judge はそれを前提の実測の制約（`premises.json` の `constraints`）に足し、eyes が R2 を省く道が在れば、運ばれた制約の在る run では省かない（元の `r2_refire_forced`）。`findings`（直す穴。依頼の入口で単位になる）にも `prior_failures`（最後まで通らなかった物）にも混ぜない。`lib/next-request.schema.json` と `docs/design.md` の約束を同じ PR で直す。
3. 構造のブロックが落ちた時（L-W09・L-W54）と直す物が無い周（L-W07・L-W08・L-W10）: 棚卸しの各行の元の形に戻す。

受け入れ（部分 D2）: 共通の決まりと閉じる行の表。新しい筋書き `refix-handoff`（受け入れた壊れが在ると最後の関所が開き、文に行が出る）を足して通す。

## この文書の外（触らない・広げない）

### 決めた物（この文書の PR は触らない。行き先で当てる）

前の決め・定石・今の works のどれかで 1 つに決まった物。根拠を行ごとに書く。

- 会話を継ぐか（持ち主の決め `persona`。L-W41・L-D43・J101・P117・F218・F222・L-D18・S19・S40）: 継がない。保存した返答を読む新しい会話で回す。持ち主が推しで決めた（`docs/owner-decisions.md` の「2026-10-11 の決めから導いた事」の「再審・案の直し・範囲の相談の答えは新しい会話で回す」。2026-10-12「おすすめでやっておいて」）。Archon は `loop_group` の中で会話を継げない（`workflows/src/loader.ts` 1173-1175 行）。狭めとして確定し、戻さない。再審で 1 回目の判定が無ければ止める今の形（`workflows/judge/scripts/rejudge_prep.py`）は残す。
- 関所の間で走っている run を報告つきで止める札（L-G55・L-W64・R2 の止め札の行・M18・S60）: 持ち込まない。持ち主の決め `stop-at-gates`（報告つきで止めるのは関所の `stop`・`reject` だけ。関所の間は Archon の `workflow cancel`。「関所の間の報告つきの止め」が落ちることを狭めとして認めた）。関所の答えの文が `request:` で始まる止め（`stopped_by_request`）は今の形のまま。
- 包み `adapter` の語と包みの確かめ・起動の印 `launch_mark`（L-E39・L-W04・L-E41）: 落としても能力は落ちない。役は Archon の役の節が起こし（持ち主の決め `archon-base`。`docs/design.md` の能力の棚卸しの包みの行）、包みを通らずに役が起きる道が無いので確かめる物が無い。起動の印は前の殻が自分の起こした run を一覧から結ぶための物（元 `works/dev/use.sh:1149`・`:1170-1171`）で、今は人が Archon の命令をそのまま打ち（`one-launcher`）、`workflow run` が run の id を返す。包みが取っていた読んだ証拠と書き込みの記録は `docs/design.md` の未決 U6（段 1）。
- 固定材料から始める道（L-E42・L-E43・L-W65・S54）: 戻す（`superset`。Archon で不可の証は無い。`docs/design.md` の能力の棚卸しも「線の始め」へ移すと書く）。今の works の用途は、同じ依頼を同じ起点（判定と承認済みの修正案が済み、修正を待つ所）から回し直して比べること（元 `works/.shared/core/fixture.py:1-2`）。大きいので独立の issue にし、運び役が部分 D2 の後に立てる（`start`・fix・線を触るので部分と並べない）。
- 案の直しの関所で項目ごとに採るか（P142）: 人の答えは今のまま 1 つの語。今の works も 1 つの答えを聞いた項目の全部に当てた（`works/.shared/core/replan.py:699-744` の `answer`。関所の文の答えの行は continue と stop の 2 つだけ: `:658-659`）。落ちたのは機械の側の項目ごとの扱い（計画の役・事前審査の諦めと答えの無い項目を訳つきで人への行に載せ、ほかの項目は採る）で、区分 P の issue で戻す。
- 役の文の言語の 1 行（L-E37）: 戻す（部分 A のやる事 11）。今の works の 1 行は「人が読む欄だけその言語、key・enum・識別子はそのまま」（`works/.shared/core/rolekit.py:67-68`）で、`lang-one` の当て方そのもの。言語を選ぶ仕組みは足さない。
- 周の鎖（L-D55〜L-D58・R69・S59）と、鎖の最後の差分 `final.diff` を当てる口（M53）: 段 3 の鎖の issue（`docs/design.md` の能力の棚卸しの「周の鎖」の行: 線の後ろに置く推しを段 3 で確かめる）。M53 はその issue の受け入れに入れる（落とさない）。鎖がまだ無いので、今 `bin/apply` に足しても当てる物が無い。
- test-gate が依頼の where を範囲の照らしに足す（T16・S07）: 戻す（`superset`。落ちるのは速さだけでも元の能力。依頼は始めの記録に在り、Archon で不可でない）。区分 T の issue。
- 同じ run の中の試験の結果の使い回し（T62・T63）: 戻す。持ち主の決め `reuse-results`（「使い回すのは入力が変わらない時だけ」「最後のテストは省かない」）に当たる。#69 が理由にした `no-queue` は修正の並べの決め。区分 T の issue。
- 任せ先の CI の役の書き込みの守り（T49）: 戻す。Archon の役の節に `sandbox.filesystem.denyWrite` が在る（`workflows/src/schemas/dag-node.ts` 109 行）。run ごとの作業ツリーを書けないと実測で分かった時だけ、源の行を示して狭めにする（共通の決まり 3）。区分 T の issue。
- 2 回目の修正の段の控え（F136・P148）: 1 回目の返答を失わない能力は、線の `fixed` が 1 回目と 2 回目を束ねる形で残る（`tests/workflows/test_line.py` の `test_refix_is_merged_without_losing_the_first`）。2 回目が 1 回目の申し出と裁定を見る所は部分 D1 のやる事 1。死んだ読み口（`lib/conflict.py` の `held_reply` ほか）は区分 F の issue で消す（K20）。
- 受け止めた落ちの決め方（R82）: 戻す（部分 C のやる事 8）。
- test_cmd の形の確かめ（T70）と関所の答えの行の頭（L-E50・L-G08。issue #86）: どちらも入口の殻の物で、1 つの bin の issue にする（運び役が #86 に T70 を足すか、#86 の後に立てる）。T70 の住処は `bin/_lib/testcmd_check.py`（元 `works/dev/testcmd_check.py` の名と中身のまま。元の `works/dev/` の物を `bin/_lib/` に置く今の形〔`toolset.py`〕と同じで、持ち主の決め `lib-port-as-is`・`bring-launch`）。殻 `bin/_lib/launcher.py` が `workflow run` の `--input test_cmd=…` を Archon を起こす前に照らす（元 `works/dev/use.sh:1020-1044` と同じ位置。止める形は Archon を起こさずに止め、許しの環境変数で通す）。層の E13 は `commands/` と `lib/` だけを照らす（`tests/layers/scan.py` の `_lang_neutral`）ので、E13 の例外は要らない。試験 24 本は `tests/bin/` に元の名で写す。
- `bin/apply`（issue #101）の M43・M45・M46: 運び役が #101 の本文に当てる。
  - M43: 戻す。止まった run を拒む 1 行に人の一言を載せる（元 `works/dev/use.sh:420`。`answer-final` の答えの文は `collect` に届く）。
  - M45（止まりかを記録で言えない run）: `bin/apply` は当てずに拒み、拒む 1 行に差分のファイルのパスと「確かめずに当てるなら `git apply <パス>`」を書く。今の works の「1 行で『確かめられなかった』と言って当てる」能力（元 `works/dev/use.sh:414-416`・`:429`）は、素の `git apply` で残る。新しい旗は足さない。
  - M46（封じる前に止まった run）: 能力の狭めに当たる（今の works は許しが在れば、どこで止まった run でも作業ツリーから組んだ差分を当てた: `works/dev/use.sh:950-971`・`:423-427`）。M45 と同じに、拒む 1 行に run の作業ツリーのパスと「`git -C <作業ツリー> diff <基>` の出力を `git apply` に渡せば当たる」を書いて残す（持ち主の決め `carry`「止まった run の差分も捨てない」）。R2 が作り直しと言った run（`small-core`）には、この道を書かない。
- 止めの語の改名（S57）: 認める。人の止めを `human:<関所>` で返すのは `docs/design.md` の「ブロックの返りの約束」の決まりで、結末の語（`stopped_by_human`）は変わらず、どの関所かが増える。
- 項目の id の形（S23。issue #82）: PR #105 で決まった（`replan_items` は承認済みの修正案の `plan[]` の 1 から数えた位置の字）。
- S35・S36（会話の続きと周ごとの値を本物の run で見る）: 段 1 の目的 4。

### 持ち主の答え待ち

答えが前の決め・定石・今の works のどれでも 1 つに決まらない物。この文書の PR は今の形を変えない。

- 機械全体の試験の枠（T64）: 今の works は run をまたいで試験の同時の数を絞り、待った秒を出した（`works/.shared/core/tree_run.py:779` `slotted_run`）。#69 は `no-queue`（「待ち行列はいらない」）を理由に外した。`no-queue` の当て方は修正の並べの決めだが、枠の待ちも待ち行列なので、決めがどちらにも読める。推し: 戻す（並べすぎで機械が詰まるのを防ぐ柵で、修正の並べの列ではない）。
- コードとコメントの比（E16）: 今の works は測って R1 に渡した（`works/.shared/core/graphloops/rules/review-loop.py:2128-2150`）。#67 は言語の知識を理由に外した（`lang-neutral`）。戻すと、持ち主が「この 6 つに限って」と決めた層の E13 の例外を広げることになる。推し: 戻す（測れない言語は unmeasured と訳を残し、E13 の例外と同じ「掃除の段で言語の知識を外へ出す」条件で）。
- 入力 `gates` の語と `gates_deferred`（L-E40・R71・S37）: 変異の検算（`p3.delta_gates`・`p4.final_gates`）を戻すかと一緒に、段 3 で持ち主に聞く（`docs/design.md` の「作りの順」の段 3 の 5）。この文書の外。

### ブロックの中だけの穴（区分の issue）

棚卸しには、線とのつなぎに当たらない、ブロックの中だけの穴（〔無〕〔戻〕〔試〕の行）も在る。この文書の PR はそれらを直さないが、触ったファイルの中のそれらの行を今より悪くしない（試験を消さない・能力を外さない）。運び役が 7 つの部分と同じ時に区分ごとの issue を立て、部分 0 が main に入った後に始める（「置き方と issue の切り方」の 4）。数: J 32・P 76・F 55・T 21・E 23・R 7・M 25（M のうち M39〜M52 は issue #101 の `bin/apply`。M53 は段 3 の鎖の issue）。行の ID:

- J: J03・J05・J13・J17・J20・J37・J40・J45・J47・J48・J49・J50・J51・J55・J56・J57・J59・J65・J66・J67・J68・J69・J70・J71・J73・J74・J75・J80・J85・J88・J95・J99
- P: P005・P007・P008・P012・P013・P015・P022・P023・P024・P025・P027・P028・P031・P033・P034・P035・P036・P037・P038・P042・P043・P046・P049・P055・P056・P057・P058・P059・P064・P065・P066・P067・P068・P069・P072・P073・P076・P080・P081・P083・P084・P085・P086・P087・P088・P100・P105・P109・P110・P114・P116・P118・P120・P121・P122・P126・P134・P135・P137・P138・P140・P142・P169・P173・P180・P184・P185・P187・P194・P211・P212・P213・P218・P222・P226・P245
- F: F014・F016・F022・F026・F028・F032・F033・F034・F042・F101・F102・F105・F106・F107・F111・F113・F117・F120・F127・F129・F134・F136・F138・F139・F147・F149・F202・F203・F205・F206・F207・F208・F212・F213・F232・F304・F306・F313・F317・F319・F320・F321・F324・F325・F328・F403・F411・F412・F418・F419・F424・F425・F429・F431・F433
- T: T7・T8・T9・T13・T15・T16・T19・T30・T31・T38・T47・T49・T53・T55・T60・T61・T62・T63・T67・T68・T69
- E: E2・E3・E7・E9・E12・E13・E14・E20・E21・E23・E25・E28・E36・E38・E41・E43・E51・E65・E67・E68・E70・E71・E74
- R: R12・R40・R42・R46・R49・R53・R81
- M: M10・M12・M16・M28・M31・M32・M33・M36・M39・M40・M41・M42・M43・M44・M45・M46・M47・M48・M49・M50・M51・M52・M61・M62・M63

## 出典

- 能力の棚卸し `docs/plans/2026-10-13-capabilities/`（この文書と一緒に置く）。各行の元の file:line は raiki61/claude-plugins @ `2aa7c66c`。
- 線の PR #74（本文の「今の works から狭めた物」「約束を変える頼み」と、運び役のコメント 1〜5 回目）、ブロックの PR #66・#69・#67・#75・#73・#68・#76・#94・#100 の本文とコメント（「マージ前の独立の目（5 つ）の指摘への直し」）。
- 止めた Archon の源 `d97d00ef`。
