<!-- coldwrite:skip 計画（ASF の issue の本文）。語は works-factory の docs/design.md の「語」の節で定義 -->
# test-gate: 試験の関門のブロックを中身ごと作る（workflows/test-gate/ と、それだけが使う lib/ の部品と試験）

works-factory は、修正依頼を受けて確かめ済みの変更と報告を返す工場を、Archon（AI の工程を YAML で書いて回す道具）の上に作り直しているリポジトリ。前の形の「今の works」（公開リポジトリ raiki61/claude-plugins の `works/`。移す元の版は `pack.json` の `works.commit` = `2aa7c66cf7abe1fe09699ac2942d107123214168`）は、判定・計画・修正・確かめ・報告をつないだ工場で、その能力を 1 つも落とさずに、線（`workflows/line/`。ブロックを並べる 1 本の工程）・8 つのブロック（`workflows/<名>/`）・助け手（`lib/`。Archon を知らない Python）に移している。この issue は、そのうちのブロック `test-gate` を、フォルダの中身ごと 1 つの PR で作る。8 つのブロックは別々の run で同時に作られ、線とはブロックの返りの約束（`docs/design.md` の「ブロックの返りの約束」）だけでつながる。元のファイルは `https://raw.githubusercontent.com/raiki61/claude-plugins/2aa7c66cf7abe1fe09699ac2942d107123214168/<パス>` で読める（本文の「元」の欄の `<パス>`）。ASF は Archon の作者が作った、issue から PR までの工程の束（`docs/design.md` の「語」）。

## 読む物

- 根の `AGENTS.md`（リポジトリの形・E8〜E11・E13・E14・E18）、`workflows/AGENTS.md`（E1・E2・E4〜E7・E12・E16・E17）、`lib/AGENTS.md`（E3）、`tests/AGENTS.md`。決まりの番号 E1〜E18 の中身はそれらの文書に在る。
- `docs/design.md`: 「ブロック」の `test-gate` の節・「ブロックの返りの約束」の `test-gate` の返り・「能力の棚卸し」の `test-gate` の行・「受け入れの一覧」・「Archon の分かっていること」と未決 U1〜U8・「作りの順」の段 2 の `test-gate` の個別の行。
- `docs/plans/2026-10-12-lib-port.md` の「移し方」1〜6（この issue で `lib/` に持ってくる部品も同じ移し方に従う）。
- `docs/owner-decisions.md` のうち本文が引く決め。
- Archon の振る舞いは、止めた Archon（`docs/design.md` の「語」。ASF と同じ Archon の源 `coleam00/Archon` の commit `d97d00ef15cce4b15d39e42635e4e86996ec1351`。持ち主の決め `archon-same-as-asf`）の文書 `packages/docs-web/src/content/docs/`（特に `guides/script-nodes.md`・`guides/authoring-workflows.md`・`reference/cli.md` の dry-run と `workflow test`）で確かめる。ASF の工程は同じ commit の `.archon/workflows/sdlc/`（本文の `W`）。
- ブロックの分:
  - 今の works: `works/blk-tests/`（`blk-tests.yaml`・`scripts/run_tests.py`・`fixtures/green.stubs.yaml`）、`works/blk-ci/`（`blk-ci.yaml`・`commands/ci.md`・`prompts/p0.local_checks.md`・`prompts/p4.ci.md`・`scripts/`・`fixtures/`）、`works/.shared/core/ci_role.py`・`entry.py`（L650〜1016 の CI の関数）・`board.py`（L379〜505 の `tree_runner` と範囲の宣言）・`graphloops/engine/declared.py`・`graphloops/rules/review-loop.py`（L2199〜2271 の `checks_plan`・`_junit_unran`・`checks_reply`）。試験 `works/tests/test_ci_test_cmd.py`・`test_board_engine_run.py`・`test_blk_tests_delta.py`（`TestTestsModes`）・`test_blk_ci.py`。
  - ASF: `W/validate/archon-validate.yaml`（節 discover・run・classify・result。`returns: result`）、`W/deliver/scripts/gate-green.ts`（緑の認証）、`W/.shared/validation-evidence.ts`（指紋と使い回しの決まり）、`docs/asf-notes.md` の A3。

## 目的と引き継ぐ能力

線に 2 つの形で差し込まれる関門。base（線 3。判定の前）は対象のテストの走らせ方を見つけて 1 度走らせ、直す前の結末（段ごとの結末と、JUnit の報告が在れば 1 件ごとの結末＝元から赤のテスト）を控える。final（線 8。修正の後）はテスト一式を走らせ、赤の原因を分けて証拠と一緒に返し、緑を作業ツリーの指紋（HEAD と差分の hash）つきで認証する（認証は緑で指紋が変わらない時だけ。赤は原因が何でも認証しない）。機械で走らせられない時は、任せ先の CI の役が CI の定義を読み、作業ツリーの写しの上で走らせる。

能力の棚卸しの行と行き先:

- CI とテスト一式・任せ先の役 — `works/blk-tests/`・`works/blk-ci/`・`works/.shared/core/ci_role.py`・`entry.py` の `run_ci` ほか → `scripts/run.py`・`scripts/ci_prep.py`・`scripts/ci_accept.py`・`commands/ci.md`・`lib/declared_checks.py`（新）・`lib/graphloops/engine/declared.py`（元の名）
- 範囲の宣言（`.works-checks.json`。変更が全部段の見ない所の下に在る段を外して名と範囲で報告する。今の works の commit `89c83871`）— `board.py` の `SCOPE_DECL`・`read_scope`・`skipped_steps`・`scope_word`・`skipped_text` → `lib/checkscope.py`（新）
- 木ごと止める殻と uv run の外の環境 — `works/.shared/core/tree_run.py` → `docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/tree_run.py` を読む
- 元から赤のテストの区別（test-gate の分: 元の結末を控え、final の赤を元からの赤と今回の赤に分ける）— `docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/baseline_red.py` を読む
- 緑の認証（新）— 無し（ASF の型 A3）→ `docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/green_cert.py` を読み、`scripts/result.py` が呼ぶ

受け入れの一覧（review-graph の節）のうち test-gate が持つ物:

- `p0.local_checks` CI を手元で走らせる。走らなければ人待ち（緑を仮定しない）→ base（走らせられない時は `ok: false`。人に聞くのは線 4）
- `p4.ci` CI を走らせ直す。赤なら戻る（今は次の run の下書き）→ final（赤の原因と証拠を返し、戻すか・次の run に回すかは線と report）

keep-essence の 12（今の works の `works/docs/keep-essence.md`）のうち test-gate が持つ物: 「元から赤の区別」（base が元の結末を控え、final が今回入れた赤と分ける。fix の赤緑の判定も同じ元の結末を読む）。

## 作る物

### ブロックのフォルダ `workflows/test-gate/`

- `works-factory-test-gate.yaml`（工程の名も `works-factory-test-gate`。E9）:
  - `inputs:` — `mode`（必須。`base`・`final`）・`start`（必須。始めの記録の指し札の JSON の字）・`baseline`（既定 `""`。final の時だけ base の返りの指し札の JSON の字。`""` と `null` は「無い」と読む）
  - `returns: result`・`outcome_field: ok`
  - 節:
    1. `run`（`script: run`・`runtime: uv`・`timeout: 1728000000`。`with:` に `mode`・`start`）: 走らせる前の指紋を取り、走らせ方を機械で決めて走らせ、走らせた後の指紋を取る。決め方は今の works の `entry.run_ci` と同じ順: (a) 対象の根に `.review-checks.json`（`lib/graphloops/engine/declared.py` の `read`）が在れば宣言の段を、範囲の宣言（`.works-checks.json`）で外れる段を除いて走らせ、始めの記録の `test_cmd` が在れば後ろに足す（宣言の段と同じコマンドなら 1 度だけ）。(b) 宣言が無く `test_cmd` が在れば `test_cmd` だけ。(c) どちらも無ければ何も走らせず `by: role_needed`。範囲の宣言が在るのに `.review-checks.json` が無い・宣言に無い段の名・宣言の書式の誤りは走らせずに止める（終了の値 1。理由を標準エラーに 1 行）。宣言の段が JUnit の報告（段の `junit`。対象の根からの相対パス）を対象の木の中に書いた時は、読んだ後に報告を run の置き場の `test-gate/<mode>/junit/<段の名>.xml` に写し、走らせる前に無かった報告だけを対象の木から消す（消さないと未追跡のファイルが増えて指紋が変わり、修正の差分にも紛れる。前から在った報告は消さない）。止められた（`tree_run.Stopped`）ら木を止め終えてから返りを出さずに `128+信号` で抜ける。返り（`output_format`）: `{by, material, runs, skipped_steps, same_as, log, junit_steps, fingerprint_before, fingerprint_after}`（by は `engine`・`role`・`role_needed`。runs は段ごとの `{name, exit, how, launch?}`。junit_steps は JUnit の報告を宣言して走った段の名の並び）。結果の全部（行・ログのパス・JUnit の 1 件ごとの結末）は run の置き場の `test-gate/<mode>/run.json` にも書く（このブロックの中だけが読む控え。持ち主の決め `io-in-output-format` に従い、ほかのブロックは読まない）。
    2. `ci-loop`（`loop_group`・`max_iterations: 3`・`fresh_context: true`・`until_bash: test $ci-accept.output.done = true`・`timeout: 1728000000`。`depends_on: [run]`・`when: "$run.output.by == 'role_needed'"`）: 任せ先の CI の役の出し直しの輪（今の works の `blk-ci` の `ci-loop`）。前の回の拒否の理由は `ci-prep` の `with: {reject: $LOOP_PREV.ci-accept.output.reason}` で受ける（止めた Archon の `guides/loop-nodes.md` の「Cross-iteration references」。1 回目は空）。何回目かは `ci-accept` が `test-gate/<mode>/ci-attempts.json` に数えて書く。中の節:
       - `ci-prep`（script `ci_prep`・`timeout: 1728000000`・`mutates_checkout: false`）: 作業ツリーの写し（`lib/graphloops/engine/util.py` の `copy_worktree`。一時の置き場の直下）を作り、役を起こす前の作業ツリーの姿（`lib/accept.py` の `tree_state`）を `test-gate/<mode>/ci-snapshot.json` に置き、入力 `reject`（前の回の拒否の理由。1 回目は空）を指示書の頭の節「前の回の受け付けが拒んだ理由」に載せる形で返す。返り `{copy_dir, tmp_dir, root, base_rev, mode, reject, attempt}`
       - `ci`（`command: ci`・`model: sonnet`・`effort: medium`（`stage-models.json` の `blk-ci/ci` = light）・`mutates_checkout: false`・`allowed_tools: [Read, Grep, Glob, Bash, WebSearch, WebFetch]`・今の works の `blk-ci.yaml` と同じ `settingSources: [user]`・`sandbox`（`enabled: true`・`allowUnsandboxedCommands: false`・`failIfUnavailable: true`・`enableWeakerNetworkIsolation: true`・網 `allowedDomains: ['*']`・`allowLocalBinding: true`・`filesystem.allowWrite: ['/']`）・`context: fresh`・`idle_timeout: 1728000000`・`output_format` は今の works の `blk-ci.yaml` の役の `{material: {status, count, detail, checked, reason}}` から盤面の欄 `carried_over`・`from_round` を外した物）
       - `ci-accept`（script `ci_accept`・`timeout: 1728000000`・`mutates_checkout: false`）: 役の前後の作業ツリーの姿を `lib/accept.py` の `tree_state`・`tree_change` で比べ（HEAD・枝・git が無視するパスも見る。Archon の `mutates_checkout` は `git status` しか見ない）、素材の欄の決まり（found は count と detail、clean は checked、ほかは reason。base で走らせられなければ awaiting_human、final では not_run、走らせる物が無ければ not_applicable）を照らす。拒めば理由を返し、`ci-attempts.json` の数が 3 になった拒否で `done: true`・`give_up: true`（輪を `max_iterations` で落とさない）。受けた素材は `test-gate/<mode>/ci-material.json` に書く。返り `{ok, done, give_up, reason}`
    3. `result`（script `result`・`timeout: 1728000000`・`mutates_checkout: false`・`depends_on: [run, ci-loop]`・`trigger_rule: all_done`・`output_type: green-cert`）: 返す節。`run.json` と（在れば）`ci-material.json` を読み、final は入力 `baseline` の指し札の先（元の結末のファイル）を `baseline_red.read_baseline` で読み、`green_cert.classify` で赤の原因と証拠を出し、今の指紋を取って `green_cert.certify` で認証する。`green` は素材の status が `clean` の時だけ真（今の works の `run_tests.run_final` の `material.get("status") == "clean"` と同じ。機械が走らせた時は `declared_checks.checks_reply` か `local_checks_material` の素材、任せ先の役の時は `ci-material.json` の素材。役が諦めた時は素材が無いので偽）。base は元の結末のファイル `test-gate/base/baseline.json` を `baseline_red.write_baseline` で書き（必須の欄の `suite` は始めの記録の `tdd_suite` の実行ファイルのパス（無ければ `""`）。必須の欄に加えて test-gate だけが読む欄 `by`・`material`・`runs`・`skipped_steps`・`exit_codes`・`junit_steps`・`fingerprint` を並べて置く）、両方とも証拠の文 `test-gate/<mode>/evidence.md` を書いて、約束の返りを返す。この節は落ちない: 中の全部の誤り（入力の欠け・指し札が開けない・元の結末のファイルが読めない・lib の例外・git の誤り）を捕まえ、終了の値 0 で `ok: false`・`green: false`・`red_cause: "incomplete"`・`evidence` は誤りを名指した証拠の文の指し札（書けなければ `test-gate/<mode>/failure.txt` に誤りの 1 行を書いた指し札）・ほかの欄は約束の形の値（`baseline`・`fingerprint` は null）を返す（返す節が落ちると線が先へ進めないため）。`run` が落ちた・飛ばされた時も `trigger_rule: none_failed_min_one_success` では届かないので、`result` の `trigger_rule` は `all_done` にし、`run.json` が無ければ同じ形の `ok: false` を返す。`result` の `with:` は `mode`・`start`・`baseline`（`$INPUTS` から）だけにし、`$run.output`・`$ci-accept.output` を束ねない（落ちた節への束ねは `if_skipped` が在っても誤りになる。止めた Archon の `dag-executor.ts`:519-534）。前の節の結果はファイル（`run.json`・`ci-material.json`）で読む。型つきの成果物 `green-cert` は、この返す節の出力そのもの（人の直し H5（本文の「依存」））。
  - 線が持つ物（止め札・関所・往復）は持たない。外への書き込みは無い。
- `commands/ci.md`: 元 `works/blk-ci/commands/ci.md` と `prompts/p0.local_checks.md`・`prompts/p4.ci.md` を 1 本にした役の指示書。走らせる場所は `$ci-prep.output.copy_dir`、本物は `$ci-prep.output.root`、前の拒否は `$ci-prep.output.reject`、形は `$ci-prep.output.mode`（base は修正前で、走らせられなければ awaiting_human。final は修正後で、走らせられなければ not_run。人待ちを新しく立てない）。盤面の台帳の人待ちの問い（`<<questions>>`・`<<answers>>`）と包みの柵の段落は落とす（盤面と包みは持ち込まない。代わりは `mutates_checkout: false` と受け付けの作業ツリーの比べ）。CI の定義の例の「Makefile・package.json の scripts・tox.ini・noxfile.py」は E13 の語の表に当たるので「CI の定義（`.github/workflows`・タスクの定義のファイルなど）」に言い換える。「走ったかは終了コードの数値や道具の名でなく、試験の件数で決めよ」「走らせたら終わるまで待て」「系統ごとの終了コードを checked に」の決まりは残す。
- `scripts/`（どれも「共通の書き方」の頭で境の口と lib/ を読み、確かめの中身は lib/ の関数を呼ぶだけ）:
  - `run.py`: `INPUTS_MODE`・`INPUTS_START` を読む → `boundary.resolve` で始めの記録を開く（`base_rev`・`test_cmd`。`tdd_suite` は `lib/startrec.py` に無い欄なので、在れば読み、無ければ空として扱う。本文の「依存」の H7）→ `green_cert.fingerprint` → `declared_checks.run_ci(root, test_cmd=…, log_dir=…, changed=…, report_dir=…)`（`changed` は `accept.touched_files(root, base_rev)` から Archon の置き場の頭 `.archon/` を除いた物。頭の字は lib に書けない（E3）ので script が渡す）→ `tdd_suite` が在れば `baseline_red.run_suite` で一式を 1 回走らせて 1 件ごとの結末を足す → `green_cert.fingerprint` → `boundary.returns`。
  - `ci_prep.py`・`ci_accept.py`: 上の節のとおり。受け付けの決まりの中身は `declared_checks.material_problems`（下）を呼ぶ。
  - `result.py`: `green_cert.classify`・`green_cert.certify`・`baseline_red.write_baseline`・`baseline_red.read_baseline` を呼び、`boundary.pointer` で指し札を組んで `boundary.returns`。
- `fixtures/`（Archon の `workflow test` の形。筋書きは配線だけを確かめる。止めた Archon の dry-run の事実: `until_bash` は走らず輪は 1 回で済んだ扱い・差し替えは節ごとに 1 つの値・承認の節は自分で済む（`reference/cli.md` の「Deterministic dry-run」と `guides/loop-nodes.md`）。だから 3 回の拒否・諦め・止められた時の振る舞いは筋書きでなく、`tests/workflows/test_test_gate.py` の script を子のプロセスで走らせる試験が確かめる）:
  - `base-engine.stubs.yaml`: mode base・`run` が `by: engine` → `ci-loop` が飛ばされ `result` に届く（`reached: [run, result]`）
  - `base-role.stubs.yaml`: `run` が `by: role_needed` → `ci-prep`・`ci`・`ci-accept` → `result`（`reached: [ci-prep, ci, ci-accept, result]`）
  - `final-green.stubs.yaml`: mode final・`baseline` を渡す → `result` が `ok: true`（authored outcome が succeeded）
  - `final-red.stubs.yaml`: mode final・`result` が `ok: false`・`red_cause: introduced`（authored outcome が failed。`expect: completed`）
  - 筋書きの入力は `fixture.inputs`（`mode`・`start`・`baseline` は字）。

### lib/ に持ってくる部品（このブロックだけが使う物）

lib-port の「移し方」1〜6 のとおり。盤面と Archon に届く所は、`docs/plans/2026-10-12-blocks/prereq.md` の issue と同じ 2 つの形（継ぎ目の直し・書き直し）だけで扱う: (a) 継ぎ目の直し（移したファイルの中で、盤面・Archon・持ってこない部品へ 1 か所だけ届く呼び出しを、引数か lib/ のモジュールの呼び出しに替える。関数の名とほかの行は変えない）、(b) 書き直し（ほとんどが盤面を読む関数を、元の関数の名のまま、値かファイルのパスを引数に受ける形で新しい lib/ のファイルに書き直す。docstring の頭に元の `<パス>:<行>`、試験は元の試験の場合を写す）。どちらも PR の本文に 1 行ずつ並べる。

- `lib/graphloops/engine/declared.py` ← `works/.shared/core/graphloops/engine/declared.py`。外す物は無し。lib-port の計画は engine の `declared` を「持ってこない」に挙げたが、中身は標準ライブラリだけで盤面に届かないので、この issue で持ってくる（PR にそう書く）。言い換え: 22 行の「pytest の段」→「試験の段」（E13）。
- `lib/checkscope.py`（新しいファイル。(b) の形だが中身は字のまま）← `works/.shared/core/board.py` の `SCOPE_DECL`・`read_scope`・`skipped_steps`・`scope_word`・`skipped_text`（L453〜505）。board.py は持ってこないので、盤面に届かない 5 つを元の名のまま写す。`read_scope` が読む `declared.DECL_NAME` は `lib/graphloops/engine/declared.py` から読む。
- `lib/declared_checks.py`（新しいファイル。(b) の書き直し。名は今の works の CI の節の語 `CI_BUILTIN = "declared_checks"`（`entry.py`:442）から）。元の関数を元の名で写し、盤面の引数 `b` と控え・枠・台帳を外す:
  - entry.py から字のまま写す物: `TEST_CMD_STEP`・`local_checks_material`（`tree_run.slotted_run` の呼び出しを `tree_run.run` に替える継ぎ目 1 か所。`launched` の使い回しの欄は書かない）・`_nice19`・`_launched`・`_cmd_material`・`_same_step`・`env_only_red`・`_suite_kind`・`suites_line`（`board.scope_word` を `checkscope.scope_word` に替える継ぎ目 1 か所）・`CiRefused`（`InputRefused` ごと）。
  - `_with_test_cmd(runner, test_cmd, note)` ← `entry.py`:750〜765。既定の runner を `board.tree_runner` から下の `tree_runner` に替える継ぎ目 1 か所。
  - `tree_runner(steps, cwd, log_dir) -> list` ← `board.py`:379〜450。段ごとに `tree_run.run`（`slotted_run` でなく）で走らせ、行 `{name, argv, out, err, started, exit, wall_s, tail, error?}` を返す。`replay_group`・`keep_group`・`note_fields`・`wait_s` は外す（同じ run の中の使い回しをしない。今の works でも最後のテストは控えを引かない）。`_tail` は `board.py` が読む `works/.shared/core/graphloops/engine/role_run.py`:513 の同じ名の関数を定数 `TAIL_LINES`・`TAIL_BYTES` ごと写す（role_run は持ってこない）。
  - `_engine_log(log_path, runs, why)` ← `entry.py`:716〜736 から `b.work`・`b.record` を引数に替えた物。
  - `_junit_unran(root, step, row)` ← `review-loop.py`:2215〜2233 を字のまま。docstring の「pytest の 5 は pytest だけの意味」は E13 の語の表に当たるので「ある実行器の終了の値 5 はその実行器だけの意味」に言い換える。
  - `checks_reply(launch, runs, root, *, after_judge)` ← `review-loop.py`:2236〜2271 から `_checks_note`・台帳の人待ち（`_awaiting_origins`）を外した物。返りは素材 `{status, count?, detail?, checked?, reason?}`。
  - `checks_plan(root)` ← `review-loop.py`:2199〜2208 の盤面の外の分（宣言を読み、無ければ fallback、誤りなら blocked）。
  - `run_ci(root, *, test_cmd, log_dir, changed) -> dict` ← `entry.py`:858〜904 の盤面の外の決まり（範囲の宣言の拒み・test_cmd を足す・same_as・skipped_steps・任せ先に落ちる時の by）を、盤面の `run_engine` の代わりに `checks_plan`・`checkscope.read_scope`・`checkscope.skipped_steps`・`tree_runner`・`checks_reply` で組んだ物。返り `{by, material, runs, skipped_steps, same_as, log, cases, junit_steps}`（cases は JUnit を宣言した段の 1 件ごとの結末。`baseline_red.parse_junit`。junit_steps はその段の名の並び）。引数 `report_dir` を受け、段が対象の木の中に書いた JUnit の報告を読んだ後にそこへ写し、走らせる前に無かった報告を対象の木から消す（上の節 `run`）。拒む時は `CiRefused`（文は元のまま）。範囲の宣言と照らす「変更」は引数 `changed` だけで受ける。今の works の `entry.scope_changed`（`entry.py`:907〜922）が足していた「差分が空の run で依頼の where が名指す追跡中のパス」（盤面の写しの rules の `_pr_files`）は持ってこない（判定の前の base では依頼の where を読む形が無い。変更が測れない時は絞らず全部の段を走らせる側に倒れるので、確かめは減らない。PR の本文に落とした物として書く）。
  - `material_problems(material, *, mode) -> list`（新しい関数）: `ci_role.take` の受け付けが写しの rules（schema・post_check）に任せていた素材の欄の決まりを、写しの `works/.shared/core/graphloops/graphs/review-loop.json` の `p0.local_checks`・`p4.ci` の schema から取って書いた物（どの欄をどこから取ったかを docstring に書く）。
- 持ってこない物: `works/.shared/core/ci_role.py`（全部が盤面か包み）・`works/blk-tests/scripts/run_tests.py`（盤面の殻）・`tree_run.py` の `slotted_run` と `slotwrap.sh`（機械全体の試験の枠は錠。持ち主の決め `no-queue`）。能力は YAML の `ci-loop`・script・`commands/ci.md`・`lib/declared_checks.py` に移る。

### 試験

- `lib/tests/test_declared.py`（新しい名。元に `declared.py` の単体の試験が無い）: `parse` の受ける形と拒む形（最上位の鍵・段の鍵・名の重なり・`junit` の相対パス）、`read` の無い・壊れた・`mutation_error`、`steps_sha` が鍵の順に依らない。
- `lib/tests/test_checkscope.py`（新）: `read_scope` の形の誤りと宣言に無い段の名、`skipped_steps` の「全段が外れる時と測れない時は絞らない」、`scope_word`・`skipped_text` の字。元の場合は `works/tests/test_ci_test_cmd.py` の `ScopeDeclarationShapeCase`・`RepoDeclarationScopeCase` と `test_board_engine_run.py` の `ScopedStepsCase`。
- `lib/tests/test_declared_checks.py`（新）: 元の試験の場合を盤面なしで書き直す。元の試験の名を各試験の docstring に書く（見比べられるように）。
  - `test_ci_test_cmd.py` の `RunCiTestCmdRulesCase`（宣言と赤の test_cmd は found・同じコマンドは 1 度・別のコマンドは別のログ）・`LaunchHowRecordedCase`・`OutOfScopeLineCase`・`EnvFailureLineCase`・`BaselineNotRunCase`・`LaunchKindCase`・`LaunchProofCase`
  - `test_board_engine_run.py` の `RunEngineCase` の `test_red_suite_found`・`test_unran_step_is_not_found`・`test_ran_red_step_is_found`・`test_ran_green_step_is_clean`・`test_red_step_without_report_says_unverified`・`test_junit_key_is_checked_by_parse`・`test_no_declaration_falls_back`、`ScopedStepsCase` の `test_scope_without_review_declaration_stops`・`test_scope_naming_an_undeclared_step_stops_before_running`、`TreeRunnerCase` の `test_tree_runner_shape`・`test_tree_runner_strips_uv_env`
  - `test_blk_tests_delta.py` の `TestTestsModes` の `test_final_red_suite_is_ok`（赤でも返りを出す）・`test_final_skips_step_whose_ignored_paths_hold_every_change`・`test_final_runs_step_when_change_touches_outside_ignored`・`test_final_empty_cmd_on_fallback_role_needed`・`test_final_never_reads_reuse_store`（使い回しの口が無いこと）
  - JUnit の報告の後始末: 走らせる前に無かった報告は対象の木から消えて `report_dir` に写しが在る・前から在った報告は残る・後始末の後の指紋が走らせる前と同じ
  - `material_problems` の欄の決まり（base の not_run は拒み awaiting_human を求める・final の awaiting_human は拒む・found に count が無ければ拒む ほか）
  - 対象のリポジトリは `tests/e2e/target-seed/` を `from tests.bin.gitkit import committed_copy` で写して使う。
- `tests/workflows/test_test_gate.py`（ブロックの YAML の形）:
  - 工程の名・入力 `mode`・`start`・`baseline`・`returns: result`・`outcome_field: ok`
  - `result` の `output_format` が下の「返りの約束」の欄をちょうど持ち（全部 `required`・`additionalProperties: false`）、`mode` の enum が `base`・`final`、`red_cause` の enum が 6 つ、`output_type: green-cert`
  - `ci` の節が `mutates_checkout: false`・`allowed_tools` に Edit・Write が無い・`model`・`effort` が今の works の `stage-models.json` の `blk-ci/ci` の値・`sandbox` の形
  - `ci-loop` の `max_iterations` が `scripts/ci_accept.py` の諦める回数と同じ
  - 各 script が読む `INPUTS_<名>` が、その節の `with:` の鍵とちょうど同じ（今の works の `test_blk_ci.py` の `test_script_inputs_match_with` と同じ確かめ）
  - `ci-prep`・`ci-accept`・`result` が `mutates_checkout: false`
  - `ci` の節の `settingSources: [user]`・`sandbox` の各欄・`context: fresh` が今の works の `blk-ci.yaml` の値と同じ
  - `ci-prep` の `with:` の `reject` が `$LOOP_PREV.ci-accept.output.reason`
  - script を子のプロセスで走らせる振る舞いの試験（環境 `INPUTS_*`・`ARTIFACTS_DIR`・`WORKFLOW_ID` を与え、`tests/e2e/target-seed/` の写しを対象にする。今の works の `test_blk_tests_delta.py` の `TestTestsModes`・`test_blk_ci.py` の `ScriptCase` と同じ形）: `run.py` が止められたら孫まで止めて返りを出さずに `128+信号` で抜ける（元 `test_stopped_run_exits_without_output`）・`run.py` の後で対象の木に新しい JUnit の報告が残らない・`ci_accept.py` が 3 回目の拒否で `done`・`give_up` を返す（元 `test_gives_up_after_three_rejections`）・役が作業ツリーを変えたら拒む（元 `test_tree_change_rejected`・`test_branch_switch_rejected`）・`result.py` が final の `inherited` の赤で `ok: false` と `red_cause: inherited` と証拠の指し札を返す・base で走らせられない時に `ok: false`・`result.py` に壊れた入力（`INPUTS_START` が JSON でない・ほかの run の指し札・`INPUTS_BASELINE` の先が無い・`run.json` が無い・壊れた元の結末のファイル）を与えると、どれも終了の値 0 で、返す節の `output_format` を満たす `ok: false`・`red_cause: "incomplete"` の JSON 1 つを出す（`output_format` は YAML から読んで照らす）
  - 筋書きを Archon で回す試験: `tests/archon.py` の使い捨ての木（`workflows/test-gate/` と `workflows/.shared/` だけ）で `archon workflow test` を `fixtures/` の全部に走らせ、全部通る
  - 外へ書く命令（`gh`・`git push`・`git merge`）がどの script にも無い

## 返りの約束（`docs/design.md`「ブロックの返りの約束」の `test-gate` の返りのまま）

- 返す節 `result`・`outcome_field: ok`（ASF の `W/validate/archon-validate.yaml` の `result` の形）
- 入力（`with:`）:
  - `mode`: `base`（`test-gate-base`）・`final`（`test-gate-final`）
  - `start` ← `$start.output.record`
  - `baseline` ← `$test-gate-base.output.baseline`（final だけ。base は null）
- 返り:
  - `mode`（string）: `base`・`final` → report
  - `ok`（boolean）: base は直す前の結末を控えられた。final は緑を認証した（`green` で、指紋が今の作業ツリーと合う）→ 線 4（base）・線 9（final）・merge
  - `green`（boolean）: テスト一式（final は CI も）が緑。base で赤でも `ok` は true になりうる → report
  - `red_cause`（string）: 赤の原因 `introduced`・`inherited`・`environment`・`interaction`・`incomplete`・`""`（ASF の enum。緑なら `""`）→ report
  - `baseline`（指し札・null 可）: 直す前の結末（テストの走らせ方と元から赤のテスト）。base だけ → judge・fix・test-gate（final）
  - `fingerprint`（object・null 可）: 作業ツリーの指紋 `{head, diff_hash}`。final だけ → merge（seal が照らす）
  - `evidence`（指し札）: 走らせた記録 → report
- 型つきの成果物: 返す節に `output_type: green-cert`（report が全部の周の認証を一覧から拾う。E5）。中身は返す節の出力そのもの（人の直し H5（本文の「依存」））。
- `baseline` の指し札の先は`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/baseline_red.py` が読み書きする元の結末のファイル（人の直し H5（本文の「依存」））。必須の欄は `{suite, test_cmd, rev, exit, cases}` で、`cases` は `baseline_red.parse_junit` の並びの形（`[{classname, name, outcome, …}]`）。fix はこの必須の欄だけを読む。test-gate は同じファイルに自分だけが読む欄 `by`・`material`・`runs`・`skipped_steps`・`exit_codes`・`junit_steps`・`fingerprint` を並べて置き、final はそこから base の段ごとの結末を読む。書くのも読むのも `baseline_red.write_baseline`・`read_baseline` だけ。`test-gate/<mode>/run.json` は節 `run` から `result` への同じ形の中の控えで、ほかのブロックは読まない。
- final の `ok` は約束の字のとおり「`green` で、走らせる前・後・返す時の指紋が揃う」時だけ真。赤は原因が何でも `ok: false` で、`red_cause` と `evidence` で原因と証拠を返す（`inherited`・`environment` も通さない。今の works は最後のテストが緑でない時はいつも最後の関所を開いた。その関所は線が開く）。ASF の型 A3 との違い（ASF は inherited・environment を PR の CI で確かめ直す前提で通す。works-factory の既定は差分を置くだけで後ろに CI が無いので通さない）は PR の本文の ASF の型の行に書く。
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
- 外への書き込み（GitHub・対象のリポジトリの main・人に見える所）は、このブロックでは無い。
- ブロックの YAML と script は、ほかのブロックのフォルダを指さない（E4）。ほかのブロックの返りは `with:` の入力として受けるだけ。
- 筋書き（fixture）は Archon の `workflow test` の形（`fixtures/<名>.stubs.yaml`。予約の鍵 `fixture:`（`expect`・`fail-node`・`reached`・`inputs`・`resolved-text-contains`）と `exec-code:`、残りの鍵は節の id → 差し替えの出力）。script の中身まで通したい筋書きは `exec-code: true`。
- ブロックの試験 `tests/workflows/test_<名>.py` は、YAML の形を PyYAML で読む試験と、筋書きを Archon で回す試験を持つ。筋書きはissue #47（P0） の `tests/archon.py` で、このブロックのフォルダと `workflows/.shared/` だけを入れた使い捨ての木を作り、その中で `archon workflow test` を走らせる。Archon の源が無ければ `tests/archon.py` が `skipTest("Archon の源が無い: ...")` で見送る。

このブロックの分:

- テストは対象の根で、`tree_run.outside_env(os.environ)` の環境（uv run が足した物を外し、`PYTHONDONTWRITEBYTECODE=1`）・自分のプロセスグループ・標準入力は空で走らせる。期限は持たない（E12）。止める時は木ごと止める（`tree_run.run`）。
- final は同じ run の中の前の結果を使い回さない（今の works の `run_tests.run_final` の「最後のテストは控えを引かない」）。認証を使い回すのは後の段（merge）で、`green_cert.matches` が真の時だけ（持ち主の決め `reuse-results`「使い回すのは入力が変わらない時だけ」「最後のテストは省かない」）。
- 外の CI（PR の checks）を待つ節は置かない。今の works の「CI」は対象の宣言と CI の定義を手元で走らせることで、既定は差分を置くだけ（E17）なので待つ物が無い。
- `.archon/` の頭（Archon の置き場）を変更から除くのは script（E3 で lib に字を書けない）。

## Archon で書けない所

- 無し。任せ先の役の書き込みの守りは今の works では包み（adapter）の柵だったが、包みは持ち込まない（`docs/design.md` の能力の棚卸し「AI の起こし方の包み → 落とす」）。代わりに役の節の `mutates_checkout: false`（Archon が節の前後の `git status` を比べて落とす）と受け付けの `tree_state` の比べを重ねる。読んだ証拠と書き込みの記録を役の節で取れるかは未決 U6（線と段 1 の物）。
- 線の側: final の入力 `baseline` を飛ばされうる値として運ぶのは線の埋め P2（`docs/polyfills.md`）。ブロックは `""` と `null` を「無い」と読むだけ。

## E11 の 3 つの答え

1. Archon が持っているか: 走らせる節（`script:`・`runtime: uv`・期限を外せる `timeout`）・出し直しの輪（`loop_group` の `fresh_context`・`until_bash`）・読むだけの守り（`mutates_checkout: false`）・認証の記録（`output_type`）は Archon の物を使う。対象の宣言を読む・走らせる・木ごと止める・赤の原因を分ける・指紋は Archon に無い。
2. ASF が持っているか: `W/validate/archon-validate.yaml`（走らせるのは script・判断の要る所だけ役・返りは `result` の 1 つ）・`W/deliver/scripts/gate-green.ts`（認証の順）・`W/.shared/validation-evidence.ts`（指紋）。コードは写さず型を採る（E8）。ASF の discover と classify の役は置かない（今の works の走らせ方は宣言と test_cmd を機械が決め、赤の区別は JUnit を機械が読む。持ち主の決め `machine-for-mechanics`）。
3. 本当に要るか: 能力の棚卸しの「CI とテスト一式・任せ先の役」「緑の認証（新）」と、fix の行「元から赤のテストの区別」の test-gate の分、受け入れの一覧の `p0.local_checks`・`p4.ci`。

## 受け入れ

1. 試験を先に入れて赤を見る（lib/ の部品が無い・YAML が無い）。その後で部品と YAML を入れて緑。赤と緑の出力の要約を PR に書く。
2. リポジトリの根からの全部の試験 `uv run --isolated python3 -m unittest discover -s . -t .` が緑。`tests/layers/` の層の試験（その時に在る物全部）も緑のまま。
3. Archon の源が在る所で `archon workflow test workflows/test-gate` の筋書きが全部通る。在る所で `archon validate workflows` に `works-factory-test-gate` の誤りも警告も無い。Archon が無い所では、筋書きを回す試験は名前つきで見送られる（`tests/workflows/test_test_gate.py` が `tests/archon.py` を通して `skipTest("Archon の源が無い: ...")`）。PR には、Archon で回した結果か、回せなかった訳を書く。
4. 持ってきた lib/ のファイルを元と比べた差分が、lib-port の「移し方」1〜5 で決めた直しだけ。
5. PR の本文に次を並べる（守りのパスの文書に書く代わり。土台の持ち主が `docs/design.md`・`docs/asf-notes.md` に写す）:
   - lib-port の「移し方」6 の 4 つ（元のパス → 置いた先・外した物と理由・言い換えた行・盤面の物を引数で受ける関数の一覧）と、継ぎ目の直し・書き直しの 1 行ずつ
   - 採った ASF の型（`docs/asf-notes.md` の「書き方」の 4 行の形）
   - 「能力の棚卸し」と「受け入れの一覧」のこのブロックの行ごとの、証の試験か筋書きの名
   - 約束を変える頼み・使いたかった埋め（あれば）
6. ブロックの分（`docs/design.md` の段 2 の `test-gate` の個別の行）:
   - base と final の 2 つの形が 1 つの返す節 `result` で返り、`mode` で分かれる（筋書き `base-*`・`final-*`）。
   - 赤の原因を `introduced`・`inherited`・`environment`・`incomplete`・`""` に分けて証拠と一緒に返し、どの赤も `ok: false`（今回入れた赤と原因の無い赤を認証しない。`result.py` の子のプロセスの試験と、筋書き `final-red`）。
   - 緑の認証に作業ツリーの指紋が入り、木が変われば認証が使えない（走らせる前・後・返す時の指紋が揃わなければ `ok: false`。指紋の取り方は`docs/plans/2026-10-12-blocks/prereq.md` の issue の `green_cert.fingerprint`）。
   - 走らせられない時は緑を仮定しない（base は awaiting_human で `ok: false`、final は not_run で `incomplete`）。任せ先の役が作業ツリーを変えたら拒み、3 回で諦める（`tests/workflows/test_test_gate.py` の子のプロセスの試験）。
   - 範囲の宣言で外した段は名と範囲で残り、全段が外れる時と変更を測れない時は絞らない（`test_checkscope.py`）。
   - 止められたら孫まで木ごと止め、返りを出さずに抜ける（`tests/workflows/test_test_gate.py` の子のプロセスの試験）。
   - 返す節 `result` は落ちない（壊れた入力でも終了の値 0 で `ok: false`・`red_cause: "incomplete"`。同じ試験）。
   - JUnit の報告が対象の木に残らず、指紋が走らせたことでは変わらない（`test_declared_checks.py`・`tests/workflows/test_test_gate.py`）。

## 範囲

- 作るのは `workflows/test-gate/` の下・本文の「lib/ に持ってくる部品」の lib/ のファイル・本文の「試験」のファイルだけ。
- 触らない（守りのパス。ASF の merge が人の手に残す）: `workflows/line/**`・`workflows/.shared/**`・`docs/design.md`・`docs/owner-decisions.md`・全部の `AGENTS.md`・`pack.json`・`README.md`・`MISSION.md`・`engineering.md`・`.github/**`・`harness/**`・`factory/**`・`.factory/**`。
- 触らない（同じ時に別の run が作る）: ほかの 7 つのブロックのフォルダ（`workflows/<ほかの名>/`）と、それらの issue が名指す lib/・試験のファイル。ほかの PR と同じファイルを作らない。
- 触らない（前に入る物）: lib-port と`docs/plans/2026-10-12-blocks/prereq.md` の issue で入った lib/ のファイル（本文の「依存」に並べた物）とその試験、`tests/workflows/__init__.py`、`tests/archon.py`、`tests/layers/scan.py`、`pyproject.toml`、`docs/`（PR の本文に書く。上の受け入れ 5）。持ってきた部品の中で前提の部品に直しが要ると分かったら、直さず PR の本文に書く。
- 決めた範囲で能力を落とす直しが要ると分かったら（持ち主の決め `superset`・`no-narrow`）、止めて PR の本文に書く。
- この PR が作るファイル（これ以外を作らない）:
  ```text
  workflows/test-gate/**
  lib/graphloops/engine/declared.py
  lib/checkscope.py
  lib/declared_checks.py
  lib/tests/test_declared.py
  lib/tests/test_checkscope.py
  lib/tests/test_declared_checks.py
  tests/workflows/test_test_gate.py
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

- main に在る物:
  - lib-port の PR: `lib/accept.py`（`tree_state`・`tree_change`・`touched_files`）・`lib/graphloops/engine/util.py`（`copy_worktree`・`repo_root`）・`lib/gatemarks.py`（`BASELINE_UNVERIFIED`・`BASELINE_NOT_RUN`・`MATERIAL_WORDS`）・`lib/startrec.py`・`lib/promptsection.py`・`tests/e2e/target-seed/`・`tests/bin/gitkit.py`
  - `docs/plans/2026-10-12-blocks/prereq.md` の issue（ブロックの前の共有の部品。本文の「依存」の前に入る物）: `lib/tree_run.py`（`run`・`Stopped`・`outside_env`・`command_argv`・`prove_launchable`・`launch_kind`・`DIRECT_HINT`）・`lib/unittrees.py`・`lib/baseline_red.py`（`parse_junit`・`_key`・`_must_pass`・`outcomes`・`run_suite`・`write_baseline`・`read_baseline`）・`lib/green_cert.py`（`fingerprint`・`matches`・`classify`・`certify`）と、その試験。`tests/workflows/__init__.py`
  - issue #47（P0）（ブロックの前に入る）: 自分の工程の置き方（`bin/_lib/place.py` の `workflow_source` が `.archon/workflows/works-factory/<ブロック>/` の形に置き、このブロックは pack `works-factory` の packaged workflow になる）・未決 U5 の決め（`boundary.lib_root()` が `WORKS_FACTORY_ROOT` を読み、無ければリポジトリの中の `lib/`）・`tests/archon.py`（止めた Archon の源と bun を見つけ、無ければ `skipTest("Archon の源が無い: ...")`。名指したワークフローのフォルダと `.shared/` だけを `.archon/workflows/works-factory/` に置いた使い捨ての git の木を作り、使い捨ての `ARCHON_HOME` と `WORKS_FACTORY_ROOT` で Archon を走らせる）・CI が Archon の源と bun を取ること・`archon validate` の層の試験
  - 境の口 `workflows/.shared/boundary.py`（`returns`・`pointer`・`resolve`・`lib_root`）
  - issue #47（P0） が決める置き方: 自分の工程は Archon の家に置かず `--workflow-source` で読ませ（PR #28）、P0 が `.archon/workflows/works-factory/<ブロック>/` の形にするので、このブロックは pack `works-factory` の packaged workflow（名指しの `command:`・`script:` は自分の `commands/`・`scripts/` から引かれ、script は pack の `.shared/` を読める）。script が lib/ を見つける道（未決 U5）も P0 が決め、ブロックは `boundary.lib_root()` を呼ぶだけ。
- ほかのブロック: 待たない。ほかのブロックの返りは線の `with:` で入力として届くだけで、このブロックの試験はその形の入力を筋書きと試験の中で作る。fix と merge が読む物（元の結末のファイル・指紋）は`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/baseline_red.py`・`lib/green_cert.py` の口が持つので、fix・merge の run とは口でだけつながる。

## 人が入れる前提の直し

無し（このブロックが頼る人の直しは、本文の「依存」の H1〜H5・H7）。
