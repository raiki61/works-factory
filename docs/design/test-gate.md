# block の設計書: test-gate（試験の関門）

- 何の話か: 対象のテストを機械で走らせ、直す前の結末を控え、修正の後に赤の原因を分けて緑を作業ツリーの指紋つきで認証する観点「試験の関門」を、単独で呼べる block `workflows/test-gate/` にする設計。TDD の実行器の書き手の役も含む（機械が走らせ方を決められない時の任せ先の CI の役は 14 節で外した）。型は [README.md](README.md)、書き方は [world.md](world.md) に従う。
- 2026-10-20 の追記（14 節。持ち主の決め `related-tests-only`）: 走らせ方が決まらない対象（`test_cmd` も `.review-checks.json` も無い道。以下「(3) の道」）では、全部の試験でなく変更に関わる試験だけを走らせる。任せ先の CI の役の輪（`ci-loop`）は外した。2〜3 節と 5・6 節の `ci-*` の記述は、外す前の形（git の履歴）で、今は 14 節が正本。
- 決めたこと: 今の `workflows/test-gate/` の 11 の node を、入口の 1 つと出し直しの指示を組む prep の 1 つを足した 13 の node の block にする（11 節の 12）。始めの記録の代わりに 11 の port で受け、TDD の実行器を始めの記録に結ぶ代わりに出力の欄 `suite` で返す。指示は英語の md 3 本（`prompts/ci.md`・`prompts/ci-fix.md`・`prompts/suite-write.md`）に置き、指示書のファイルを役に Read させる道（拒まれた後の出し直しと書き手の材料）は、指示に値を貼る形に替える。振る舞いは変えない。
- 読む人: この block を作る実装の役（この設計書だけで作れるように書いた）。急ぎではない（README 11.1 の 1 波目。ほかの block と並べて作る）。
- 持ち主に求めること: なし。keep-essence の 1・2・6 の守りの割り当ては 9 節、自分で決めた事は 11 節に集めた。

この文書の語は README の頭の物を使う。ほかに:

- line: メイングラフ（README の 8.7）。この block を include し、始めの記録（run の頭に書く記録。試験のコマンド・言語・差分の根など）の値を port で配る。
- Archon: 工場が上で動く workflow の実行器。script の node に入力を環境変数 `INPUTS_<名>` で渡し、読み込みの時に script の源の `INPUTS_<名>` の字を、結ばれた入力と照らす（`scanEnvironmentReads`）。
- 依頼の行の `where`: 修正依頼の 1 行が名指す所（パスか、パスと行の目安の字）。
- 入口の差分: run を起こした時に依頼と一緒に渡された差分（入口の差分の根から修正前の HEAD まで）。判定から入る run（依頼の文だけの run）では空。
- 利用者の環境に戻す: 起動の殻（`bin/works-factory`。Archon を隔離した HOME で起こす）が隔離したまま、対象のテストのコマンドだけは利用者の HOME・XDG に戻して起こす事。戻して起こした時に置く印のファイル（`user-env-ran`）の置き場が `user_env_dir`。置き場が空のまま戻そうとする run は、印を置けないので止まる（`lib/userenv.py`）。
- 包み・柵（埋め fence）: 起動の殻が読むだけの役の claude を起こす直前に、作業ツリーと共有の `.git` への書き込みを塞ぐ部品（`workflows/.shared/fence.py`）。包みを通る run は、起動の記録のパスを `WORKS_FACTORY_FENCE_RECORDS` で宣言し、受け付けはその記録で柵が掛かったかを確かめる。
- 宣言: 対象の根の走らせる段の宣言 `.review-checks.json`（graphloops の `engine/declared.py` の形）と、範囲の宣言 `.works-checks.json`（段ごとの `paths_ignore`）。
- 走らせ方の語 `by`: `engine`（機械が宣言の段を走らせた）・`role`（機械が test_cmd を走らせた。宣言が無いか、宣言の段から落とした）・`role_needed`（宣言も test_cmd も無く、機械が走らせられない。14 節の道: AI が書いた実行器で変更に関わる試験だけを走らせる。以前は任せ先の CI の役が素材を書いた）。`lib/declared_checks.py` の `RUN_WORDS`。
- 素材（material）: 走らせた結果の札 `{status, count?, detail?, checked?, reason?, systems?}`。`status` は `found`・`clean`・`not_applicable`・`awaiting_human`・`not_run`。
- 赤の原因 `red_cause`: `introduced`（直しが起こした）・`inherited`（元から赤）・`environment`（環境）・`interaction`（語として在るが今は返らない。8 節の 1）・`incomplete`（確かめが終わらない）・空（緑）。`lib/green_cert.py` の `RED_CAUSES`。
- 指紋: 作業ツリーの `{head, diff_hash}`。走らせる前・後・認証の時の 3 つが合う時だけ緑を認証する。
- TDD の実行器（runner）: 第 1 引数の書き先に試験の 1 件ごとの結末を JUnit XML で書く実行ファイル。人が `tdd_suite` で渡すか、この block の base が用意する（取り置きから使うか、書き手の役が書く）。
- 取り置き: 照らしを通った実行器を test_cmd の字ごとに run と対象をまたいで置く所（起動の殻が環境変数 `WORKS_FACTORY_SUITE_KEEP` で渡す）。
- 例の run: 任せ先の CI の役は本物の run `92f4ca04-e0e9-4301-841c-beec00f86cf2`（対象 <owner>/<repo>。`~/.local/state/works-factory/targets/10ac16be/archon-home/workspaces/<owner>/<repo>/artifacts/runs/92f4ca04-…/test-gate/`。base は `awaiting_human`、final は `clean`）。実行器の書き手は本物の run `df5e111f-ea97-409b-8066-2245d32746ab`（対象 raiki61/works-factory。`…/targets/6c76444e/…/runs/df5e111f-…/test-gate/suite/writer-brief.md`。書き手は `made: false` を返した）。どちらも役の指示は Archon が `$ci-prep.output.*` を差し込んだ物でファイルに残らないので、骨組みは node の返り（Archon の記録 `archon-home/archon.db` の `remote_agent_workflow_events` の `node_output`）と今の md から描いた。

## 1 block の全体

### 1.1 役

対象のテストの走らせ方を機械で決めて走らせる（宣言の段と test_cmd）。決められなければ（宣言も test_cmd も無い）AI が書く TDD の実行器で、変更に関わる試験だけを機械が走らせる（14 節。以前はここで任せ先の CI の役が CI を丸ごと再現した）。base は直す前の結末（段ごとの結末と、JUnit の報告が在れば 1 件ごとの結末）を控え、実行器を人が渡していなければ用意する。final は一式を走らせ、赤の原因を機械が分け（元の結末との 1 件ごとの突き合わせ）、緑を指紋つきで認証する。赤は原因が何でも認証せず、AI が書いた実行器の緑も認証しない。

### 1.2 port

入力（YAML の `inputs:`。12 個）:

- `mode`（必須）: `choice(base|final): 形。base は直す前の結末を控える（判定の前）。final は修正の後に一式を走らせ、赤の原因を分けて緑を認証する`
- `test_cmd`: `text: 人が渡したテストのコマンド（対象の根で走らせる 1 行。字のまま）。空は渡されていない`。既定 `""`。
- `tdd_suite`: `text: TDD の実行器のパス（人が渡した物か、base の出力の suite）。空は無い（base では用意する）`。既定 `""`。
- `base`: `text: 修正前の版（範囲の照らしの起点。関わる試験の選びの起点の版にもなる）。空は起点なし（範囲の照らしは依頼の where だけ）`。既定 `""`。
- `entry_base`: `text: 入口の差分の根（変更の起点の版）。関わる試験の選びが、ここから今の作業ツリーまでに触ったファイルを起点にする。空は修正前の版（base）`。既定 `""`。
- `request`: `json(shared:request.schema.json): 依頼の行の配列か、それを findings の欄に持つオブジェクト（where だけを読む）。空の配列は無い`。既定 `[]`。
- `request_scope`: `flag: 真なら base の形で依頼の行の where を範囲の照らしの変更に足す（入口の差分が空の run）`。既定 `false`。
- `baseline`: `file: final の時、base の出力の baseline のファイル。空は無い（1 件ごとの比べをしない）`。既定 `""`。
- `reuse_dir`: `text: 同じ run の中の試験の結果の控えの置き場の絶対パス。base の時だけ引いて置く。空は使い回さない`。既定 `""`。
- `reuse_key`: `text: 控えに書いて引く時に照らす run の名。空はこの run の id`。既定 `""`。
- `user_env_dir`: `text: 利用者の HOME・XDG に戻して起こした印を置く置き場の絶対パス。空は置き場が無い（戻す run では止まる）`。既定 `""`。
- `lang`: `text: 人に見せる欄（実行器の書き手の why）の言語。空は依頼の言語`。既定 `""`。

port でない環境（起動の殻が渡す。今と同じ）: 取り置きの根 `WORKS_FACTORY_SUITE_KEEP`・包みの起動の記録 `WORKS_FACTORY_FENCE_RECORDS`（埋め fence の `RECORDS_ENV`）・引かずに走らせる旗 `GRAPHLOOPS_RERUN_CHECKS`（`tree_run.RERUN_ENV`）。

出力（`returns: result`、`outcome_field: ok`）: 今の `result` の 15 欄（`mode`・`ok`・`green`・`red_cause`・`ran_steps`・`baseline`・`fingerprint`・`test_outcomes`・`evidence`・`by`・`suites_line`・`log`・`baseline_line`・`reason`・`optional`）を字のまま保ち、4 欄を足す:

- `suite`: 字。この後の段が使う TDD の実行器のパス。base: port `tdd_suite` が在ればそれ、無ければ照らしを通った実行器（place の `suite/runner` の絶対パス）、作れなければ `""`。final: port `tdd_suite` のまま。
- `suite_note`: 字。実行器を取り置きから使った・書いた・作れなかったの 1 行（`suitewrite.head_note` の字）。用意しなかった run は `""`。
- `related`: 関わる試験の選び `{applied, whole, files, left, far, reasons, ran}`（14 節）。道 (1)(2) は `applied: false`。
- `report`: 報告に載せる日本語の行の配列（10 節）。

`ok` の意味は今のまま: base は直す前の結末を控えて鎖を進めてよいか、final は緑を認証したか。`baseline`・`evidence` の pointer の `path` は place の中の相対のパス（`<include の道>/baseline.json` など）。

今との違い: 今は入力を `start`（始めの記録の pointer。`test_cmd`・`tdd_suite`・`base_rev`・`run_id`・入口の差分が空か・依頼のファイルを読む）・`mode`・`baseline`・`reuse_dir`・`user_env_dir` で受け、TDD の実行器を始めの記録の `tdd_suite` に書き込んで後ろの段に渡していた（`lib/suitewrite.py` の `settle`）。block は始めの記録を読まず書かない（README 4.2・4.3）。実行器は出力の `suite` で返し、line が fix と final の test-gate の `tdd_suite` に配る。

### 1.3 node の並び（`workflows/test-gate/works-factory-test-gate.yaml`）

1. `intake`（script `intake.py`）: port を読み、place の中を `logs/` のほかは消し、`intake.json` と実行器の控え `suite-state.json` を書く。返り `{ok, reason}`。
2. `run`（script `run.py`。`depends_on: [intake]`・`when: "$intake.output.ok == true"`）: 走らせる前の指紋・`declared_checks.run_ci`・`tdd_suite` が在れば一式を 1 回（走らせ方が決まらない道は関わる試験だけ。14.4）・走らせた後の指紋。`run.json` に全部、返りは今の `output_format`（`suite_owed` を含む）のまま。
3. `suite-loop`（`depends_on: [run]`・`when: "$run.output.suite_owed == true"`・`loop_group`: `max_iterations: 2`・`fresh_context: true`・`until_bash: done=$suite-try.output.done; test "$done" = true`）
   - `suite-prep`（script `suite_prep.py`）: 取り置きを使うか、書き手の指示を組む。返り `{write, prompt}`。
   - `suite-write`（AI。`depends_on: [suite-prep]`・`when: "$suite-prep.output.write == true"`・`prompt: "$suite-prep.output.prompt"`・下の起こし方・`output_format` は今の `suite-write` の物を字のまま）
   - `suite-place`（script `suite_place.py`。`depends_on: [suite-write]`・`with: {reply: {from: "$suite-write.output", if_skipped: null}}`）: 返り `{made, why}`。
   - `suite-try`（script `suite_try.py`。`depends_on: [suite-prep, suite-place]`・`trigger_rule: all_done`）: 返り `{done, ok, why}`。
4. `result`（script `result.py`。`depends_on: [run, suite-loop]`・`trigger_rule: all_done`・`output_type: green-cert`・`with: {optional: '[{"node": "suite-loop", "bare": false}, {"node": "suite-write", "bare": true}]'}`）: 出力を返す。落ちない。

AI の node（`suite-write` だけ）の起こし方: `model: '@wf-test-gate'`・`mutates_checkout: false`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob, Bash, WebSearch, WebFetch]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false, failIfUnavailable: true, enableWeakerNetworkIsolation: true, network: {allowedDomains: ['*'], allowLocalBinding: true}, filesystem: {allowWrite: ['/'], denyWrite: ['~/../archon-home']}}`・`idle_timeout: 1728000000`・`retry: {max_attempts: 2, on_error: all}`。YAML のコメントに埋めの振る舞い（包みが印を読んで足す物。#217・#309）を書かない（README 1.3 の歩かせ 8）。

script の node はどれも `runtime: uv`。`run` のほかは `mutates_checkout: false`（`run` は対象のテストを走らせるので、今と同じく書かない）。

今との違い: `intake` を足した（今は `run`・`ci-prep`・`result`・`suite-*` の 5 つの script がそれぞれ始めの記録を開いていた）。後ろの script は port を読まず `intake.json` を読むので、`with:` に `$INPUTS` を書かず、Archon の入力の照らし（`scanEnvironmentReads`）が見る字は `intake.py` に集まる。`run` が place を消していた所（今の `fresh_gate`）は `intake` に移した（`run` は落ちうる node なので、消すのは落ちない入口でする）。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、line から include された時は `$ARTIFACTS_DIR/test-gate-base/` か `$ARTIFACTS_DIR/test-gate-final/`。今の `test-gate/base/`・`test-gate/final/` と `test-gate/suite/` の代わり）の下に書く。名は `src/files.py` だけが持つ:

- `intake.json`: port を読んだ値。
- `suite-state.json`: 実行器の控え `{test_cmd, tdd_suite, suite_written?}`。`lib/suitewrite.py` の関数の `start_file` に渡すファイル（11 節の 2）。照らしが通ると `tdd_suite` に実行器の絶対パスが入る。
- `run.json`・`logs/a<k>/`（`<k>` は空いた最初の番号。前の走りのログを上書きしない）・`junit/`（宣言の段の JUnit の報告）。
- `impact/`（関わる試験の選びの地図の控え。`lib/related.pick` の `cache_dir`）。`run.json` の `related` が選びの結果と走らせたか（`ran`）を持つ。
- `suite/runner`（照らす実行器）・`suite/writer-brief.md`（`suitewrite.prepare` が書く。読み手は無いが、lib を変えないので残る）・`suite-write-prompt-<n>.md`・`suite-suite.log`・`suite-suite-again.log`・`junit-suite.xml`（`baseline_red.run_suite` が書く）。
- `baseline.json`（base だけ）・`evidence.md`・`failure.txt`（証拠の文が書けない時だけ）。

### 1.5 コードの置き場と、作る・触るファイル

作るファイル（この block の PR が触るのはこれと `tests/blocks/test_gate/` と、この設計書だけ）:

- `workflows/test-gate/works-factory-test-gate.yaml`
- `workflows/test-gate/prompts/suite-write.md`（4 節）
- `workflows/test-gate/scripts/intake.py`・`run.py`・`suite_prep.py`・`suite_place.py`・`suite_try.py`・`result.py`
- `workflows/test-gate/src/__init__.py`（空）
- `workflows/test-gate/src/files.py`: place のファイルの名（1.4）・`LOGS = "logs"`・`fresh_place(place)`（今の `run.fresh_gate` の消す部分）・`log_dir(place)`（今の `fresh_gate` の `a<k>` を決める部分）。
- `workflows/test-gate/src/scope.py`: 今の `workflows/test-gate/scripts/run.py` の `changed`（:39-48）と `request_wheres`（:51-61）を port の値で受ける形にした物。`request_wheres(request, mode, request_scope)` は、`mode` が `base` で `request_scope` が真の時だけ依頼の行の `where`（字の物）の並びを返す。
- `workflows/test-gate/src/certify.py`: 今の `result.py` の `suite_exit`・`test_outcomes`・`gate_fields`・`evidence`・`role_systems`・`certified`・`failed`（:24-190）の写し。始めの記録の代わりに `intake.json` と `suite-state.json` を読む。`RUN_ROW`・`LOG_ROW`・`INNER_ERROR` もここ（証拠の文の行の頭。e2e の照らしの表が引く）。
- `workflows/test-gate/src/suite.py`: 実行器の控えの読み書き（`suite-state.json` を作る・読む）と、出力の `suite`・`suite_note` の組み方。
- `workflows/test-gate/src/prompts.py`: md に渡す値の組み立て（4.3 の差し込み口の一覧）。
- `workflows/test-gate/src/report.py`: 報告の行（10 節）。
- `workflows/test-gate/fixtures/` の 7 本（12 節）。
- `tests/blocks/test_gate/__init__.py`・`test_test_gate.py`・`test_prompt_compare.py`（12 節）。
- 共通の指示の断片（土台に無い物。この block が最初に要るので、この block の PR が足す）: `workflows/.shared/prompts/resubmit.md`（3 節。拒まれた後に同じ会話の続きで拒まれた欄だけを返させる役の全部が使う）。

使う `lib/`（どれも README 9.3 の KEEP）: `declared_checks`（`run_ci`・`role_material_problems`・`suites_line`・`baseline_line`・`gate_values`・`run_how`・`drop_copy`・`CI_ROLE`・`COPY_PREFIX`・`DECL_NAME`・`MODES`・`ROLE_NEEDED`・`RUN_FILE`・`NO_ADAPTER_NOTE`・`SELF_REPORTED_NOTE`・`STATUSES`・`CiRefused`）・`green_cert`（`fingerprint`・`classify`・`certify`・`ran_steps`・`RED_CAUSES`・`RAN_BY_CAUSE` ほか）・`baseline_red`（`run_suite`・`write_baseline`・`read_baseline`・`test_outcomes`・`OUTCOMES`・`ONLY_ENV`）・`suitewrite`（`need`・`prepare`・`place`・`pending`・`settle`・`head_note`）・`tree_run`（`reuse_place`・`RERUN_ENV`・`Stopped`）・`checkscope`（`request_files`）・`accept`（`tree_state`・`tree_moved`・`status_keys`・`TREE_KEYS`・`touched_files`・`Reject`）・`rolekit`（`accept_round`・`round_outcome`・`resubmitted`・`merge_fields`・`resubmitting`・`rejected`・`rejects_text`・`candidate_path`・`attempt`・`given_up_reason`・`GIVE_UP_AFTER`・`LANG_DEFAULT`）・`graphloops/engine/util.py`（`repo_root`・`copy_worktree`）・`gatemarks`（`BASELINE_NOT_RUN`・`MATERIAL_WORDS`。報告の行）・`oneline`・`jsonfile`。`lib/carry.py` は import しない（始めの記録を読まない。依頼の容器の読みは土台の `shared:request.schema.json` の形と `requestrows.findings`・`src/scope.py` で替える）。`lib/startrec.py` は `src/suite.py` が `suite-state.json` の読み書き（`load`・`save`）にだけ import する。根拠: `lib/suitewrite.py` を変えずに使うため、控えを始めの記録と同じ口で読み書きする（11 節の 2。`load`・`save` は形を問わない JSON の読み書きで、始めの記録そのものは読まない）。

埋め: `fence`（`bad_declaration`・`fenced_since`・`RECORDS_ENV`）。作り直しの間に block から埋めを import する口は土台の `ports.py` の決め（README 3 節は埋めを組み込みで `workflows/.shared/` へ移すと書くだけで、それまでの import の道を決めていない。11 節の 6）。

土台の `ports.py` に要る口（今の `workflows/.shared/boundary.py` に在り、この block が使う）: `drop_runner_env(user_env_dir)`（Archon の変数を落とし、利用者の環境の印の置き場を立てる）・`suite_keep()`（`WORKS_FACTORY_SUITE_KEEP` の読み）・`RUNTIME_COPY_PREFIX`（Archon が作業ツリーに置く工程の写し `.archon/`）・`pointer(path)`・`items(raw)`。土台に無ければ、この block の PR が `ports.py` に足す（merge と fix も使うので block の `src/` には置かない。11 節の 6）。

### 1.6 つなぎ方（graph の側。block には書かない）

- line: 今と同じ 2 か所に include する。`test-gate-base`（`mode: base`。判定の前）と `test-gate-final`（`mode: final`。修正の後）。
- `with:` の出どころ: `test_cmd`・`reuse_dir`・`user_env_dir`・`lang` ← line の始めの記録・`base` ← 始めの記録の `base_rev`（修正前の HEAD）・`request` ← 依頼のファイル（`json` の form で読めるファイルの pointer か値）・`request_scope` ← 始めの記録の「入口の差分が空」（今の `startrec.diff_empty`）・`reuse_key` ← line の run の id（fix の TDD の輪の頭が同じ控えを同じ名で引く）・base の `tdd_suite` ← 人が渡した `tdd_suite`・final の `tdd_suite` ← `$test-gate-base.output.suite`・final の `baseline` ← `$test-gate-base.output.baseline`。
- 読み手: fix（`baseline`・`suite`）・line の修正前の承認ノードと最後の承認ノード（`by`・`suites_line`・`log`・`baseline_line`・`ran_steps`・`red_cause`・`ok`・`green`・`test_outcomes`）・r1〜r4 と eyes（`ok`・`test_outcomes`・`evidence`）・merge（`fingerprint`・`ok`）・report（`report`。型つきの成果物 `green-cert` の一覧も今のまま）。
- 実行器を書く AI の手番を起動の承認ノードで知らせる 1 行（`suitewrite.GATE_NOTE`）は line の始めの記録の側に残る。

## 2 node の設計シート: ci（任せ先の CI の役）——外した（2026-10-20）

持ち主の決め `related-tests-only` で、任せ先の CI の役 `ci` とその指示 `prompts/ci.md` を外した。全体の CI は工場が再現せず、CI と人に任せる。外す前の指示と設計は git の履歴（commit `e87f40a` の版）で読める。走らせ方が決まらない道は 14 節。

## 3 node の設計シート: ci-fix（任せ先の CI の役の出し直し）——外した（2026-10-20）

2 節と同じ訳で、`ci-fix`・`ci-fix-prep` と指示 `prompts/ci-fix.md` を外した。共通の断片 `workflows/.shared/prompts/resubmit.md` はほかの block も使うので残す。

## 4 node の設計シート: suite-write（TDD の実行器の書き手）

### 4.1 役

人が実行器を渡さなかった run で、対象のテストを走らせて 1 件ごとの結末を JUnit XML に書く小さな実行ファイルの本文を書いて返す。置くのも走らせるのも機械（持ち主の決め `suite-by-ai`。#516）。

### 4.2 port

`intake.json` の `test_cmd`（← port `test_cmd`）・作業ツリーの根・根に宣言が在るか・`lang`。

### 4.3 組み立ての順（`prompts/suite-write.md`）

1. 役の定義（決まった文）。
2. `## Material` と `{root}`、`<!-- if declared -->` 宣言が在る 1 行 `<!-- end declared -->` と `<!-- if not declared -->` 宣言が無い 1 行 `<!-- end declared -->`（`{decl_name}`）— 条件: 根に `declared_checks.DECL_NAME` のファイルが在る。
3. `<!-- if test_cmd -->` 囲いの中の `{test_cmd}`（囲いの字 `{fence}`）`<!-- end test_cmd -->` と `<!-- if not test_cmd -->` 渡されていない 1 行 `<!-- end test_cmd -->` — 条件: `test_cmd` の前後の空白を除いた字が空でない。
4. 読んでよい物と、してはいけない事（決まった文）。
5. `## The runner's contract`（決まった文）と `{only_env}`。
6. `## How to write it`（決まった文）。
7. `## How to answer`（決まった文）と `{lang}`。
8. 結びの 1 文。

差し込み口の一覧（値の出どころ）: `{root}` ← 作業ツリーの根（`Path.cwd()` の解いた絶対パス。今の `suitewrite._brief` と同じ）・`{decl_name}` ← `declared_checks.DECL_NAME`・`{test_cmd}` ← port `test_cmd`（字のまま）・`{fence}` ← `` "`" * max(3, <test_cmd の中の ` の最長の並び> + 1) ``（今の `suitewrite._brief` の囲いの決め）・`{only_env}` ← `baseline_red.ONLY_ENV`・`{lang}` ← port `lang`（空なら 2.3 と同じ文）。差し込むかを選ぶ名: `declared`・`test_cmd`。

md の本文（英語）:

```markdown
You are the TDD runner writer, started in a new conversation. In a run where the person did not give a runner (the input tdd_suite), you write and return the body of a small executable that runs the target repository's tests and writes each test's outcome to JUnit XML. The machine puts it in a file and runs it; you only return the body. The machine runs the body you return once; if JUnit XML comes out with one or more tests, it uses the runner, and it reuses it in other runs with the same test command.

## Material

- The target root: {root}
<!-- if declared -->
- The target root has the run declaration `{decl_name}`.
<!-- end declared -->
<!-- if not declared -->
- The target root has no run declaration `{decl_name}`.
<!-- end declared -->
- The test command the person gave (test_cmd), exactly as typed:

<!-- if test_cmd -->
{fence}text
{test_cmd}
{fence}
<!-- end test_cmd -->
<!-- if not test_cmd -->
None (the person did not give one).
<!-- end test_cmd -->

You may read only this material, the root's `{decl_name}` (if it exists), the CI definitions (files such as `.github/workflows`), and the test configuration files they name. Do not search further. Use Bash only for short commands that print a test tool's usage, to check whether it has an option to write JUnit XML. Do not run the tests, do not install dependencies, and do not write files.

## The runner's contract

- It is started with the target root as its working directory.
- Its first argument is where to write the JUnit XML (an absolute path). It writes each test's outcome there as JUnit XML.
- It exits with the test tool's exit code as it is (non-zero if any test is red).
- Arguments may follow the first argument (test files, test names, filter expressions), and the environment variable `{only_env}=1` may be set. When the person gave no test command and the root has no run declaration, the machine runs only the tests related to the change by passing their file paths here, so pass them to the tool as they are whenever it can take them (that is what keeps the run short). If the tool cannot take them, drop them and run the whole suite (running the whole suite checks the same thing).

## How to write it

1. If there is a test_cmd, write it into the runner without changing a single character, and add after it the option that makes the tool write JUnit XML to the first argument. The machine treats a runner that contains the test_cmd as typed as the same thing as the test_cmd, and does not run the test_cmd twice in the later TDD loop.
2. If there is no test_cmd, decide the command that runs the tests from the CI definitions and `{decl_name}`.
3. Make the first line of the body a `#!` line (the machine does not place a body that does not start with `#!`).
4. If you cannot decide how to make it write JUnit XML, or what to run, do not return a body for form's sake: set `made` to false and write in `why`, in one line, what you read and what was missing. Do not assume green.

## How to answer

- `made`: true if you wrote a runner, false if not.
- `body`: the runner's body (an empty string when `made` is false).
- `why`: why `made` is false (an empty string when it is true).
- Write `why` in {lang}. Keep commands, option names, file names, and paths as they are.

Return only JSON that matches the output schema.
```

### 4.4 返す形

今の `suite-write` の `output_format` のまま: `made`（boolean）・`body`（字）・`why`（字）。全部必須。人に見せる欄は `why`（作れなかった訳として報告の冒頭の 1 行目と、最後の承認ノードに載る）で、言語は `{lang}`。

### 4.5 描いた骨組み（例の run `df5e111f-…` の値）

~~~markdown
You are the TDD runner writer, started in a new conversation. …（決まった文）

## Material

- The target root: ~/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/worktrees/archon/task-works-factory-line-1792348017642
- The target root has no run declaration `.review-checks.json`.
- The test command the person gave (test_cmd), exactly as typed:

```text
env WORKS_FACTORY_ARCHON_CACHE=~/.cache/works-factory PYTEST_XDIST_AUTO_NUM_WORKERS=4 uv run --isolated python3 tests/changed.py --base origin/main
```

You may read only this material, …

## The runner's contract
…
- … the environment variable `TDD_SUITE_ONLY=1` may be set. …

## How to write it
…

## How to answer
…
- Write `why` in the language of the person's request. …

Return only JSON that matches the output schema.
~~~

例の run の書き手は `made: false`（「test_cmd は tests/changed.py → tests/shard.py の unittest TextTestRunner（点の出力のみ）で、JUnit XML を書く指定も xmlrunner の依存も無く…」）を返し、`suite-try` が `done: true`・`ok: false` で輪を閉じた。

### 4.6 今の指示との差

今の指示は `workflows/test-gate/commands/suite-write.md`（27 行）と、役が Read する材料の文 `test-gate/suite/writer-brief.md`（`lib/suitewrite.py` の `_brief`、:91-97）の 2 か所に在る。

- 移した: 材料の文の中身（対象の根・宣言が在るか・test_cmd の囲い）を md の `## Material` の節に直に入れた。材料の文のファイルを Read させる道（md:5-7「材料の文: $suite-prep.output.brief_file」「まずこのファイルを Read で全部読め」）をやめた。材料の文の見出しと札（「# 実行器を書く材料」「- 対象の根:」「- 対象の根の宣言 …: 在る・無い」「## test_cmd（人が渡したテストのコマンド。字のまま）」「無い（人が渡していない）」、:93-97）は md の決まった文になった。lib の `_brief` は組み込みで、読み手が無くなるので外せる（`suitewrite` は KEEP）。
- 移した: 実行器の約束の環境変数の名（md:16 の `TDD_SUITE_ONLY`）を差し込み口 `{only_env}` に（`baseline_red.ONLY_ENV` と同じ字）。宣言の名も `{decl_name}` に。
- まとめた: 「返す形」（md:25-27 の JSON の形の 1 行）を `## How to answer` の箇条と結びの 1 文に。
- 足した: 役の定義の「started in a new conversation」（この node は `fresh_context: true` で、新しい会話で起きる。今の指示には無かった）。
- 足した: 言語の 1 文。
- 英語にした。役の名「TDD の実行器の書き手」は "the TDD runner writer"。

1 つ目の commit の作り方: 今の `suite-write.md` を字のまま写し、md:5-7 の材料の文の指しを残したまま `{brief_file}` を差し込む（読ませる道はこの commit では変えない）。比べは例の run の値で、組んだ指示が今の `suite-write.md` に `suite-prep` の返りを差し込んだ字と同じになることを照らす。2 つ目の commit で材料を直に入れる形と英語に替え、この節の差の一覧どおりかを並べて審査に出す。

## 5 script の node

- `intake.py`: `os.environ.get("INPUTS_MODE")`・`INPUTS_TEST_CMD`・`INPUTS_TDD_SUITE`・`INPUTS_BASE`・`INPUTS_REQUEST`・`INPUTS_REQUEST_SCOPE`・`INPUTS_BASELINE`・`INPUTS_REUSE_DIR`・`INPUTS_REUSE_KEY`・`INPUTS_USER_ENV_DIR`・`INPUTS_LANG` を字のままで読み、`ports` の口に渡す。`mode` が `declared_checks.MODES` の外なら `ok: false`・`reason: mode は base・final のどれか: <値>`。`baseline` は final の時だけ読む（base で渡されても読まない）。読めない port は `ok: false` と、読めなかった port と訳。通れば `src/files.fresh_place(place)` で place の中を `logs/` のほかは消し、`intake.json`（port の値。`request` は行の配列に揃えた物、`baseline` はパスか空）と `suite-state.json`（`{test_cmd, tdd_suite}`）を書いて `{ok: true, reason: ""}`。落ちない。
- `run.py`: 今の `run.py` と同じ順（:81-118）。値は `intake.json` から: `test_cmd`・`tdd_suite`・`base`（今の `base_rev`）・`reuse`（`tree_run.reuse_place(reuse_dir, reuse_key or os.environ["WORKFLOW_ID"], rerun=bool(os.environ.get(tree_run.RERUN_ENV)))`、base だけ）・`wheres`（`src/scope.request_wheres`）。ログの置き場は `src/files.log_dir(place)`。テストを起こす前に `ports.drop_runner_env(user_env_dir)`。止められたら木を止めてから 128+信号で抜ける・走らせられない（`CiRefused`・`ValueError`）は 1 で抜けて理由を標準エラーに 1 行（今のまま。`result` が拾う）。返りの `suite_owed` は `suitewrite.need(<suite-state.json の dict>, mode)`。 2026-10-20: 走らせ方が決まらない道（`by` が `role_needed`）では、`tdd_suite` の一式を関わる試験だけにし、`run.json` に `related` を置く（14.4）。
- `suite_prep.py`: `suitewrite.prepare(<suite-state.json>, <place>/suite, ports.suite_keep(), Path.cwd())` を呼ぶ（取り置きが在れば写して `write: false`、無いか前の周で取り置きが照らしを通らなければ控えに悲観の印を置いて `write: true`）。`write` が真なら `prompt.render("suite-write", …)`（4.3）を組んで `{write: true, prompt}`、偽なら `{write: false, prompt: ""}`。読めない入力は落ちずに `write: false`。
- `suite_place.py`: `suitewrite.place(<suite-state.json>, <place>/suite, <reply を値に戻した物>)` を返す（今のまま。読めない入力は `made: false` と訳）。
- `suite_try.py`: 今の `suite_try.py`（:29-55）と同じ。`suitewrite.pending(<suite-state.json>)` が在れば `baseline_red.run_suite` で 1 回走らせ（書き直しの周は `suite-again` の名でログを分ける）、`suitewrite.settle` で照らす。走らせた後の指紋は通らなくても `run.json` の `fingerprint_after` に、通れば `suite` と 1 件ごとの結末を `run.json` に足す。走らせる前に `ports.drop_runner_env(user_env_dir)`（`user_env_dir` は `intake.json` から）。止められたら 128+信号で抜ける。ほかの誤りは `done: true`・`ok: false` と訳。 2026-10-20: `run.json` の `related`（`run` が選んだ物）で、選んだ試験のファイルだけを渡して走らせる。選べなかった・関わる試験が無い時は一式（14.4）。
- `result.py`: `src/certify.py` の `certified` を呼んで返す。今の `result.py` と同じく、`run.json` と（任せ先の役の run なら）`ci-material.json` を読み、`green_cert.classify` で赤の原因と証拠を出し、`green_cert.certify` で認証する（final で任せ先の役が書いた緑は自己申告として認証しない）。base は `baseline.json` を `baseline_red.write_baseline` で書く（`suite` は `suite-state.json` の `tdd_suite`、`test_cmd` は `intake.json` から）。final は port `baseline` のファイルを `baseline_red.read_baseline` で読み、`test_outcomes` と修正前のテストの行を足す。`evidence.md` を書く。任せ先の役の run で包みの記録が無ければ証拠に `NO_ADAPTER_NOTE`。残った写しを消す。足した 3 欄: `suite`・`suite_note` は `src/suite.py` が `intake.json` と `suite-state.json` から組み（1.2）、`report` は `src/report.py`（10 節）。中の誤りは全部捕まえて、終了の値 0 で `ok: false`・`green: false`・`red_cause: incomplete` と誤りを名指した証拠の pointer を返す（今の `failed`。`suite` は port `tdd_suite`、`suite_note` は空、`report` は 10 節の誤りの 1 行）。 2026-10-20: `ci-material.json` は読まない。`by` が `role_needed` の素材は `src/certify.py` の `runner_material` が実行器の結果から組み、`related` を欄に載せる（14.5）。

## 6 受け付け

- suite-place と suite-try: 書き手の返答の照らしは機械の事実だけ（本文の頭が `#!`・JUnit XML が出たか・試験が 1 件以上か。`suitewrite`）。拒んで出し直させず、作れなかった訳を控えに残して、実行器の無い run の道を通る（今のまま）。2 周目は取り置きが照らしを通らなかった時の書き直しだけ。

## 7 単独で呼ぶ

```sh
bin/works-factory workflow run works-factory-test-gate \
  --cwd <対象> --input mode=base --input test_cmd='python3 -m unittest -v'
```

final は `--input mode=final --input baseline=<base の run の baseline.json の絶対パス> --input tdd_suite=<base の出力の suite>`。出力は `workflow get <run>` の `result` の返り。始めの記録は要らない。殻の引数の名は（未確認）（world の 7 節と同じ）。

## 8 元の works と graphloops の同じ場面

元の works は `works/blk-ci/`（`blk-ci.yaml`・`commands/ci.md`・`prompts/p0.local_checks.md`・`prompts/p4.ci.md`・`scripts/`）と `works/blk-tests/`、`.shared/core/`（`entry.py` の `run_ci`・`tree_run.py`・`board.py`）。graphloops は `prompts/review-loop/p0.local_checks.md`・`p4.ci.md` と `engine/declared.py`。

同じ物（工場がそのまま持つ）: 宣言の段を機械が走らせる・素材の 5 語・範囲の宣言 `paths_ignore`。（決められない時の任せ先の役・役の前後の作業ツリーの比べ・終わるまで待つ・3 回で諦めるは、14 節で任せ先の役ごと外した。）

工場に無い物・違う物と、その訳:

1. 赤の原因の語 `interaction`: 語の一覧（`green_cert.RED_CAUSES`）と出力の enum には在るが、`green_cert.classify` は返さない（`lib/green_cert.py:32` の注記）。語は #69 で ASF の語の一覧から入り、#544 `9ff164bf` で語の持ち主に寄せた。返さないと決めた記録は無い（（未確認））。この block は語を enum に残し、返さない今のままにする。
2. 素材の札の `carried_over`・`from_round`（元の works の `blk-ci.yaml:120-146`）: 工場は意図して外した（#69 `01d1a09c`「盤面の欄 carried_over と from_round を外した」）。block は周を持たないので要らない。
3. 機械全体の試験の枠（元の works の `tree_run.slotted_run` の `slotwrap.sh`）: 持ち主の決めで持たない（`f2abe872`（#118）・#202 `3aa6ba83`）。同じ run の中の試験の結果の使い回しは #202 で戻した（この block の `reuse_dir`・`reuse_key`）。
4. 拒まれた後の出し直し: 元の works は毎回新しい会話（`blk-ci.yaml:72` の `fresh_context: true`）で丸ごと出し直させた。工場は同じ会話の続きで拒まれた欄だけを返させ、機械が合わせる（#588 `249c88ea`、#571）。この block も同じ（3 節）。
5. 包みの宣言の確かめ: 元の works は別の node `ci-fence`（`blk-ci.yaml:22-41`）。工場は `ci-prep`（役を起こさずに諦める）と `ci-accept`（柵が掛かったか）に畳んだ（#364 `28ed9456`）。この block も同じ。
6. 任せ先の自己申告の緑: 元の works と graphloops は人への問いに回した（元の `review-loop.py:950,2093-2095` の `_ci_by_engine`）。工場は認証しない（`green_cert.certify` の `self_reported`。#69）。最後の承認ノードと報告がそれを言う（`SELF_REPORTED_NOTE`）。この block も同じ。
7. TDD の実行器: 元の works は test_cmd が pytest の 1 つのコマンドの時だけ起動の殻が `--junitxml` で包んだ（`skills/works/references/start.md:20`）。工場は取り置きか AI の書き手で、どの test_cmd にも用意し、機械が事実だけを照らす（#516 `2a48db54`）。この block も同じ。実行器を始めの記録に結ぶ所だけを、出力の欄 `suite` に替えた（1.2）。

この block が両方より良く、残す物: 指紋つきの緑の認証（走らせる前・後・認証の時が合う時だけ。#69）・1 件ごとの JUnit の元の結末と、それによる元から赤と直しが起こした赤の分け・`test_outcomes`（#69）・走った系統と走らせられなかった系統の名の分け `systems`（#518 `7938ccb8`）と、言いすぎない言い方（`green_cert.py:159-183`）・同じ会話の続きの出し直しと欄ごとの合わせ（#588）・どの test_cmd にも AI が書いて機械が照らす実行器と取り置き（#516）・出力の node が落ちない（誤りは `incomplete` と名指す）。

## 9 守る keep-essence

README 10 節の割り当てのうち、この block が担う物と読む物:

- 1 赤緑の機械の判定（担うのは fix。この block は材料を出す）: TDD の輪が赤緑を JUnit の結末で判じるための実行器（`suite`）を用意し、機械が「JUnit XML が出て試験が 1 件以上」を照らしてから渡す。役が書いた実行器を照らさずに渡す道は無い（`suitewrite.settle`）。final の緑も JUnit と終了コードから機械が決め、役の自己申告の緑は認証しない。守りの試験: `SuiteLoopCase.test_written_runner_feeds_the_red_green_check`（書いた実行器が 1 件ごとの結末を元の結末に入れ、`suite` が実行器の絶対パス）・`ResultScriptCase.test_final_role_green_is_self_reported_and_not_certified`。
- 2 元から赤のテストの区別（この block が担う）: base が 1 件ごとの結末を `baseline.json` に控え（`baseline_red.write_baseline`）、final がそれと今の結末を 1 件ずつ突き合わせて、元から赤（`inherited`）と直しが起こした赤（`introduced`）を機械が分ける（`green_cert.classify`）。どちらの赤も認証しない。守りの試験: `ResultScriptCase` の `test_final_inherited_red_is_not_certified`・`test_final_introduced_red_is_not_certified`・`test_final_returns_every_test_with_its_base_and_final_outcome`・`test_test_outcomes_are_not_compared_when_either_side_has_no_per_test_results`・`test_tdd_suite_cases_go_into_the_baseline`（`tests/blocks/test_gate/` へ作り直す）と `lib/tests/test_baseline_red.py`（KEEP）。
- 6 当たる試験を選んで回し、回さなかった試験を名で残す（担うのは fix。この block は読み手）: 範囲の宣言の `paths_ignore` で回さなかった段を `skipped_steps` に、走らせられなかった段を `ran_steps.unran` に名で返す。最後の承認ノードと報告がそれを並べる。守りの試験: `RunScriptCase.test_base_reads_request_where_as_change`・`test_scope_declaration_without_review_declaration_stops`・`ResultScriptCase.test_partly_startable_steps_are_named_not_not_ran`。
- 封じた差分（merge の設計書の 8 節）の土台: final の緑の認証の指紋 `fingerprint` を返す。merge は封じる時と置く時に、この指紋が今の作業ツリーと合うかを照らす（試験の後に木が変われば封じない・置かない）。守りの試験: `ResultScriptCase.test_final_green_is_certified_with_fingerprint_and_tree_change_voids_it`。

e2e の `tests/e2e/evidence.json` の L-E38・L-W28・T1・T6・T18・T29・T30・T33・T34・T40・T41・T42・T66 は、node の id と place のパス（`parent/test-gate/base/…` → `parent/test-gate-base/…`）を新しい物に合わせる。

## 10 報告の行（`src/report.py`）

今の `lib/runreport.py` が試験の関門の返りから組む行を、この block の返りの値だけで組む（node の id の札は外す。block は line の中の名を知らない）。字は今と同じ。

- base:
  1. `直す前のテスト: <語>`。語は今の `runreport._base_word`（:1611-1630）の写し（`緑`・`走らせられなかった（<cause>）——<gatemarks.BASELINE_NOT_RUN>——<訳>`・`<素材の語>（<status>）——<訳>`・`赤（赤の原因 <cause>）`）。素材は place の `baseline.json` から読む。
  2. `直す前のテストの走らせ方: <suites>`・`直す前のテストのログ: <log>`（今の `_evidence_lines` の 2 行。値は `declared_checks.gate_values(<返り>)`）。
  3. `試験の関門（base）: <緑・緑でない>・ok <ok>`（赤の原因が在れば `・赤の原因 <cause>`、`ok` が真で原因が `inherited`・`environment` なら `——赤のまま通した（<cause> の赤。直しが起こした赤でないと認証が見た）`）。今の `_green_lines` の 1 行。
  4. `suite_note` が空でなければその 1 行。
- final:
  1. `最後のテストの走らせ方: <suites>`・`最後のテストのログ: <log>`・`最後のテストの<baseline_line>`（今の `_evidence_lines`）。
  2. `最後のテストの一式: <suites>・ログ <log>`（今の `_tests_head_lines` の 1 行目）。`by` が `role_needed` なら `declared_checks.SELF_REPORTED_NOTE`。
  3. `試験の関門（final）: …`（base の 3 と同じ形）。
- 出力の node の中の誤り（`by` が空）: `試験の関門（<mode>）: 出力ノードの中の誤り（工場の不具合）——<証拠のパス>` の 1 行だけ（今の `green_cert.GATE_BROKE_BY` の読みと同じく、試験が走らなかったとは言わない）。

どの行を報告のどの節に載せるか（冒頭の句・人が決めること・緑の認証の節）は report の決め。冒頭の句が読む値（`by`・`ran_steps`・`suites_line`・`baseline_line`・`suite_note`）は欄のまま返す。

## 11 自分で決めた事

1. 実行器を始めの記録に結ぶ代わりに、出力の欄 `suite` で返す（`suite_note` も）。根拠: README 4.2・4.3（block は始めの記録を読まず書かない）。読み手（fix の TDD の輪・final の試験の関門・報告の冒頭の句）には line が port で配る。人が渡した実行器と書いた実行器が同じ道で届く今の性質（`suitewrite` の docstring）は、`suite` が両方を同じ欄で返すことで続く。
2. `lib/suitewrite.py` を変えずに使うため、place に始めの記録の形の小さな控え `suite-state.json`（`{test_cmd, tdd_suite}` と印）を置き、`start_file` としてそれを渡す。根拠: README 11.1（block の PR は lib を変えない）。`suitewrite` は控えのファイルの `test_cmd`・`tdd_suite`・`suite_written` の 3 つの欄だけを読み書きする（`startrec.load`・`save` は形を問わない JSON の読み書き）。組み込みで `suitewrite` の引数の名を `state_file` などに直すのは、`suitewrite` の使い手（この block と line）の都合で決める。
3. 入口の node `intake` を足し、後ろの script は port でなく `intake.json` を読む。根拠: 今は 5 つの script が始めの記録を開いていた。port を読む口を 1 つにすると、Archon の入力の照らし（`scanEnvironmentReads`）が 1 つの script を見るだけで済み、落ちうる `run` の前に place を消せる。
4. port `request_scope`（flag）を足す。根拠: 今の `run.py` は始めの記録の「入口の差分が空」の時だけ依頼の where を範囲に足す。block は始めの記録を読まないので、その真偽を port で受ける。base の時の作業ツリーの差分（`base` からの触ったファイル）は入口の差分（入口の差分の根から修正前の HEAD まで）と違うので、block の中で代わりに数えられない。
5. port `reuse_key` を足す。根拠: 今は始めの記録の `run_id` を控えの run の名にしていた。fix の TDD の輪の頭は組の子の run（別の run の id）から同じ控えを引くので、名は line の run の id を port で揃える。空ならこの run の id（単独の run）。
6. 土台の `ports.py` に `drop_runner_env`・`suite_keep`・`RUNTIME_COPY_PREFIX` を求め、無ければこの block の PR が足す。埋め `fence` の import の道も土台の決めに従う。根拠: 今の `boundary.py` に在り、merge と fix も使う（憲法の 4。2 つ以上の block が使う物は共通の置き場）。README 3 節は `ports.py` を `boundary.py` の後継と書くが、口の一覧と、作り直しの間の埋めの import の道を書いていない。
7. 言語の既定の文を、README 5.3 どおり `the language of the person's request` にする。根拠: README の決め。ただしこの block の役は依頼の文を見ないので、この既定は役には分からない。line が始めの記録の lang を必ず渡す（空なら依頼の言語を line が決めて渡す）形が要る。README の 5.3 に書いた。
8. 拒まれた後の出し直しと書き手の材料を、指示書のファイルを Read させる道から、指示に値を貼る道に替える。根拠: README 5.2（指示は prep が組んで `prompt` で返す）。読ませる道は、Read を持つ役にしか使えず、指示の在りかが 2 つになる。今の振る舞い（同じ会話の続き・拒まれた欄だけ）は変わらない。
9. 出し直しの断片の囲いを `~~~` にする。根拠: 却下の理由の字は Python が組み、受け付けの文に `` ``` `` が入りうる（素材の detail の写しなど）。今の `` ``` `` の囲いはそれで閉じる。

10. place の作り直しで消すのは、この block の名の在るファイルとフォルダだけにする（`src/files.py` の `fresh_place`）。1.3 の「place の中を `logs/` のほかは消し」は、単独の run では place が run directory の根なので、ほかの block のファイルまで消す。根拠: 土台の決め「block が消してよいのは、自分が名を持つファイルだけ」。`logs/a<k>/` は消さない（今と同じ）。拒否の控え・合わせた答えの控えの名は `rolekit` が組むので、`rejects`・`candidate` の関数で引く。
11. port `request` の形は、`workflows/test-gate/schemas/request.schema.json`（1.5 の `anyOf`）でなく、土台の `shared:request.schema.json` で受け、読みは `requestrows.findings`。根拠: `anyOf` は `KNOWN_KEYWORDS` に無く、`ports.json` も形の検査も拒む。同じ名の形のファイルを 2 か所に置くことも検査が拒む（形の名は pack の中で 1 か所）。空の依頼（`[]`・空の字）は `[]` として読む。
12. （14 節で `ci-loop` ごと外した。以下は外す前の決め）node `ci-fix-prep`（script `ci_fix_prep.py`）を足して 13 の node にし、出し直しの役 `ci-fix` の指示をこの prep が組む（`ci-prep` は出し直しの周は `prompt` を `""` で返す）。根拠: 形の検査 `check_standalone_renders` は、AI の node ごとに「その node の prep を差し替えず、`reached` に在り、`exec-code: true` の筋書き」で指示の字を照らすが、輪（`loop_group`）の 2 周目は dry-run で回らない（`until_bash` は動かず、1 周で終わる）ので、`ci-prep` が `resubmit: true` を返す周を本物の script では作れない。prep を分ければ、筋書きは `ci-prep` を差し替えて出し直しの周を作り、`ci-fix-prep` は本物で指示を組める。振る舞いは変わらない（出し直しの周だけ `ci-fix-prep` が回る）。
13. （`ci-*` の部分は 14 節で外した。今の `standalone` は AI の `suite-write` だけ差し替える）筋書き（12 節）は検査の決まりに合わせて作る。`standalone` は `exec-code: true` で script を本物に回し、AI の 2 つ（`ci`・`suite-write`）だけ差し替える（宣言も test_cmd も無い作業ツリーなので任せ先の輪と実行器の輪が回る）。`base-resubmit` は `exec-code: true` で `ci-prep`・`ci-fix`・`ci-accept` を差し替える。ほかの 5 本（`base-engine`・`base-suite-kept`・`base-suite-written`・`final-green`・`final-red`）は配線だけを見るので script も差し替える。12 節の `standalone`（engine の形）は `base-engine` に、`base-role` は `standalone` に寄せた。根拠: 検査が `standalone` の `exec-code: true` と、AI の node ごとの本物の prep を求める。
14. `ports.items(raw)` は足さず、入力 `optional`（`[{node, bare}]` の JSON の字）は `src/certify.py` の `optional_items` で読む。`drop_runner_env`・`suite_keep`・`RUNTIME_COPY_PREFIX`・`pointer` は土台の `ports.py` に既に在るので、土台は触らない。根拠: 1.5 の「土台に無ければ足す」は、`items` だけが無く、使い手がこの block の 1 か所だけ。
15. md の字の `}}` は差し込みの口が `}` 1 つにする（`{{`・`}}` は字の波括弧の書き方）。`{"material": {...}}` の終わりの `}}` は 1 つに縮むので、md には `{"material": {...}}}}` と書く（2.3 の注の「字として残る」は `{...}` と `{}` に限る）。
16. （14 節で `ci_accept.py` と一緒に外した。`src/inputs.py` は無い）script が `with:` で受けた入力の字を値に戻す口は、`src/inputs.py` の `value`（JSON でなければ字のまま）。根拠: 読めない返答を `rolekit.resubmitted` が「JSON として読めない」と拒める。`ports.parsed` は JSON でない字を落とす。
17. 報告の行（10 節）の final の 2 は、元の `_tests_head_lines` の 1 行目だけ（修正前のテストの行は 1 で出す）。
18. 返す node の誤り（`certify.failed`）は、lib を読めなくても返せるよう、`src/files.py`・`src/certify.py` の頭で lib を import しない（lib は関数の中で読む）。`run.json` の名は `files.RUN` に字で持ち、`declared_checks.RUN_FILE` と同じことを試験が縛る。誤りの回の `suite` は intake.json の port `tdd_suite`（読めなければ `""`）。

19. 言語の既定の文は、2.3 の `the language of the person's request` でなく、土台の `prompt.lang`（共通の断片 `lang-default` の `the language of the request (the user's language)`）を使う。根拠: 土台が既定の文を 1 か所に持ち、`prompt.lang` が port の空を埋める。11 節の 7 の「この既定は役には分からない」は変わらない（line が必ず lang を渡す形が要る）。
20. 英語の md の `{lang}`（今は `suite-write.md` だけ。`ci.md`・`ci-fix.md` は 14 節で外した）の値は `prompt.lang(intake["lang"])`。`ci-fix.md` の `{lang}` は `ci-fix-prep` が intake.json の lang から入れる。出し直しの断片 `resubmit.md` は言語を持たない。

## 12 試験

2026-10-20: 任せ先の CI の役を外したので、`ci-*` の筋書き（`base-resubmit`）・試験（`CiRoleCase`・`PromptCase` の ci の 3 つ・`ResultScriptCase` の任せ先の素材の試験）は外した。今の試験は 14.9。以下は外す前の設計。

- standalone の fixture（`workflows/test-gate/fixtures/` の 7 本。今の入力から `start` を外し、port の値に替える。11 節の 13）:
  - `standalone.stubs.yaml`: `exec-code: true`。入力は `mode: base` だけ。宣言も test_cmd も無い作業ツリーなので script が本物に回り、任せ先の輪と実行器の輪が回る。AI の `ci`・`suite-write` だけ差し替え、指示の字を `resolved-text-contains` で照らす。
  - `base-resubmit.stubs.yaml`: `exec-code: true`。`ci-prep`・`ci-fix`・`ci-accept` を差し替えて出し直しの周を作り、`ci-fix-prep` が本物で指示を組む。
  - `base-engine.stubs.yaml`: 機械が走らせた（`by: engine`）ので任せ先の輪と実行器の輪が飛ぶ。
  - `base-suite-kept.stubs.yaml`・`base-suite-written.stubs.yaml`: 実行器の輪（取り置きを使う・書き手が書く）。`result` の返りに `suite`・`suite_note` が入る。
  - `final-green.stubs.yaml`・`final-red.stubs.yaml`: 入力に `mode: final`・`baseline`・`tdd_suite`。
  - 配線だけの 5 本（`base-engine`・`base-suite-kept`・`base-suite-written`・`final-green`・`final-red`）は script も差し替えるが、残す。見るのは script の中身でなく YAML の配線で、node の返りの値に応じて `when`・`trigger_rule` がどの輪を起こしどれを飛ばすか（`reached` の並び）と、`mode: final` の入力の鍵が通ることを Archon の workflow test で照らす。`exec-code: true` の 2 本は、宣言の無い作業ツリーの base の道と出し直しの周しか通らないので、機械が走らせた道・取り置きの実行器の道・final の道の配線はこの 5 本だけが見る。
- `tests/blocks/test_gate/test_test_gate.py`（script を子のプロセスで回す。始めの記録の無い使い捨ての `ARTIFACTS_DIR` と、試験の対象の git のリポジトリで、port の値だけを渡す。今の `tests/workflows/test_test_gate.py` の `ScriptCase` の始めの記録の組み立てを、`intake.py` を port の値で回す形に替える）:
  - YAML の形（今の `YamlCase` から）: `test_name_inputs_and_return`（入力の鍵が 1.2 の 11 個）・`test_result_output_format_is_the_contract`（`suite`・`suite_note`・`report` を足した 18 欄。`result` の `with:` は `optional` だけ）・`test_role_node_reads_only`（`command` の代わりに `prompt: "$ci-prep.output.prompt"`）・`test_runner_writer_is_launched_like_the_ci_role_and_its_fall_is_declared`・`test_runner_loop_rewrites_only_after_a_kept_runner_fails`・`test_role_cannot_write_the_checkout`・`test_run_material_is_the_material_schema_or_null`・`test_loop_matches_give_up`・`test_loop_does_not_paste_previous_reject_by_loop_prev`・`test_script_inputs_match_with`（`INPUTS_` を読むのは `intake.py` だけ）・`test_readonly_nodes`・`test_scripts_write_nothing_outward`。
  - `RunScriptCase` の全部（`test_base_reads_request_where_as_change` は `request_scope: true` で）・`CiRoleCase` の全部（`test_prep_copies_tree_and_passes_reject` は「却下の文が `ci-prompt-<n>.md` に入る」に、`test_resubmit_returns_only_the_rejected_fields` は「`ci-fix-prompt-<n>.md` に最後の却下と控えのパスが入る」に替える。`test_reject_with_a_reference_reaches_the_prompt_verbatim` は指示の字で照らす）・`ResultScriptCase` の全部・`SuiteLoopCase` の全部（実行器の控えは `suite-state.json` で、`test_written_runner_feeds_the_red_green_check` は出力の `suite` が実行器のパスであることも照らす）。
  - `EvidenceRowsCase`: 試験と e2e の照らしの表が証拠の行の頭を `src/certify.py` の `RUN_ROW`・`LOG_ROW` から引く。
  - 足す: base で実行器を作れなかった時に `suite` が空で `suite_note` が `suitewrite.NOT_MADE` で始まる・final の `suite` が port `tdd_suite` のまま・`report` の行（10 節の base・final・誤りの 3 通り）・`intake` が `mode` の外の語で `ok: false`・md の差し込み口の素材の語が `declared_checks.STATUSES` と同じ（yes/no）。
- `tests/blocks/test_gate/test_prompt_compare.py`（README 11.4）: 2.6・3.6・4.6 の「1 つ目の commit の作り方」の 3 つの照らし。2 つ目の commit で消し、並べた物を PR に載せる。
- 写さない試験: `CopiedTextsCase.test_every_command_is_its_original_with_only_ledgered_edits`（写しの台帳。README 9.4）・`YamlCase.test_ci_command_keeps_the_rules`（日本語の md の字の照らし。決まりが残ることは 11.4 の比べと 2.6 の一覧で審査が見る）・`YamlCase.test_role_node_matches_works_blk_ci`（元の works の YAML との突き合わせ。sandbox の値は `test_role_cannot_write_the_checkout` が縛る）・`FixtureCase.test_fixtures_pass_in_archon` は block の fixture の照らし（7.1 の 4 と 11.2）に替わる。
- keep-essence の守りの試験は 9 節。

## 13 未確認

- 7 節の命令の正確な形。
- 作り直しの間に block から埋め `fence` を import する道（1.5）。
- `output_type: green-cert` の型つきの成果物の一覧が、include の中の node でも今と同じ形で `$TYPED_ARTIFACTS_FILE` に載るか（今も include の中の node なので載ると見るが、block の名が変わる時の札の字は未確認）。

## 14 関わる試験だけ走らせる（2026-10-20。持ち主の決め `related-tests-only`）

### 14.1 決めと範囲

- 持ち主の言葉: 「自分に関係のあるやつだけでいいんじゃないかな。もう工場としては。全体テストとかはCIや人間たちに任せる？全部試験賭けるのは重いしね」。
- 実地（2026-10-20）で、(3) の道（`test_cmd` が空で、対象の根に `.review-checks.json` が無い run。`run.json` の `by` が `role_needed`）は、AI が書いた全試験の実行器を 3 回（base の `suite-try`・fix の group-start・final の `run`。1 回 40〜48 分）と、任せ先の CI の役を 2 回（1 回 36〜74 分）走らせて 256〜300 分かかった。`test_cmd` を渡した run は 25〜90 分。
- 変える物:
  1. (3) の道で全試験の実行器を走らせる 3 か所を、変更に関わる試験だけにする（14.2〜14.4）。fix の group-start は `docs/design/fix.md` の 17 節。
  2. 任せ先の CI の役の輪（`ci-loop`: `ci-prep`・`ci`・`ci-fix-prep`・`ci-fix`・`ci-accept`）と、その指示 `prompts/ci.md`・`prompts/ci-fix.md` を外す。全体の CI は工場が再現せず、CI と人に任せる（14.5）。
- 変えない物: 道 (1)（`test_cmd`）と道 (2)（`.review-checks.json`）の振る舞い。利用者が走らせ方を決めた物なので、絞らない。
- 残す守り（3 つ）: 直す前から赤だった試験と直しで壊した試験を分けて数える（`green_cert.classify` の `inherited`・`introduced`）・赤は原因が何でも認証しない・機械でない者が決めた緑を認証しない（14.5 の (3) の道の final は、緑でも認証しない）。変えた物は 14.7 に書いた。

### 14.2 関わる試験の選び（`lib/related.py`）

test-gate と fix の 2 つの block が使うので `lib/` に置く（憲法の 4）。言語・実行器の名を持たない（E13）。

- `applies(root, test_cmd)`: 走らせ方が決まらない対象か。`test_cmd` の前後の空白を除いた字が空で、`declared_checks.checks_plan(root)` が `fallback`（宣言が無い）を返す時だけ真。fix が (3) の道かを自分で決めるのに使う（`by` を fix へ運ばない）。
- `pick(repo, *, rev, seeds, cache_dir)` → `{whole, reasons, files, left, far}`:
  - `impact.map(repo, rev=rev, seeds=seeds, diff=True, cache_dir=cache_dir)` で `rev` から作業ツリーまでに触ったファイルと `seeds` を起点にした地図を引き、`impact.select_tests(m, direct_only=True)` で選ぶ。fix の受け付けが回す試験の選び（`selected_problems`）と同じ決め（直に関わる試験だけ。起点か深さ 1）。
  - `whole`: 真なら選べない。地図が引けない（git の誤りなど）か、分からない物が直に関わる所に在る（`select_tests` の `run_all`）時で、今までどおり一式を走らせる。理由は `reasons`。
  - `files`: 回す試験のファイル（根からの相対）。作業ツリーに在る物だけ。`left`: 届いただけで直には関わらず回さない試験。`far`: 深さ 2 以上の分からない物（理由の形）。
- `args(repo, picked)`: `files` を絶対パスにした並び。TDD の実行器の約束（4.3・`baseline_red.run_suite` の `args`）の「第 1 引数の後ろに足す試験のファイル」と、環境変数 `TDD_SUITE_ONLY=1`（`only=True`）で走らせる。引数を解かない実行器は一式を走らせる（実行器の書き手の指示が決めている。同じ事を確かめる）。
- `lines(picked, ran)`: 報告の行（14.6）。

### 14.3 起点

関わる試験の起点は、base と final で同じ決めにして、final の選びが base の選びを含むようにする（base の元の結末に無い試験が final で落ちると `introduced` と読まれるのを、直しが触った所に限るため）。

- 起点の版 `rev` は新しい port `entry_base`（入口の差分の根）。空なら port `base`（修正前の版）。そこから今の作業ツリーまでに触ったファイル（未追跡を含む）が起点。base では入口の差分、final では入口の差分と直し。
- 加えて、`request_scope` が真の run（入口の差分が空）は、依頼の行の `where` が名指す追跡中のパスも起点（`src/scope.py` の `request_wheres`。今は base だけが範囲の宣言に使う物を、関わる試験の選びでは base と final の両方に足す）。

### 14.4 当てる所

- `run`（final を含む）: `by` が `role_needed` で `tdd_suite` が在る時、一式を 1 回でなく `pick` の選びで走らせる。`whole` なら今までどおり一式。`files` が空なら走らせず、`run.json` の `suite` を `null`・`related` に選びの結果を置く。
- `suite-loop`: `suite_owed` を、(3) の道で関わる試験が 1 件も無い（`files` が空で `whole` でない）時は偽にする（走らせる試験が無いのに書き手を起こさない）。`suite-try` の 1 回は、`run.json` の `related`（`run` が選んだ結果。`suite-loop` は `run` の後なので同じ物）で走らせる。選びが `whole` なら一式。実行器の照らし（JUnit XML が出て試験が 1 件以上）は、走らせた試験の上で変わらない。
- 選びを `run.json` の `related` に 1 回だけ置き、`suite-try` と `result` は引き直さない（base の中で 2 度引いて食い違わない）。

### 14.5 任せ先の CI の役の輪を外した後の (3) の道

- 素材（`material`）は機械が実行器の結果から組む（`src/certify.py` の `runner_material`）:
  - 実行器が走り、結末が取れた: 終了コード 0 なら `clean`（`checked` に走らせた試験の数）、そうでなければ `found`（`count` は落ちた件数）。
  - 関わる試験が無く走らせなかった: `not_applicable`（`reason`: 変更に関わる試験が無い。全体の試験は CI と人に任せる）。
  - 実行器が無い・走らなかった・結末が取れない: base は `awaiting_human`、final は `not_run`。`reason` に訳（実行器を作れなかった理由は `suite_note`）。base を `awaiting_human` にするのは、任せ先の役が走らせられなかった時の base と同じ扱い（鎖を止めず、判定の台帳に載せる）。
- 認証: (3) の道の final は、緑（`clean`）でも認証しない（`green_cert.certify` の `held`。訳は「AI が書いた実行器が、関わる試験だけを走らせた緑——機械は実行器の中身を照らしていない」）。今までの「任せ先の自己申告の緑を認証しない」を、任せ先の役が無くなっても緩めない。認証するかは持ち主の選び（納品の残った疑問）。
- 赤の原因の分け（`classify`）と `test_outcomes` は、実行器の 1 件ごとの結末で今までどおり。(3) の道の `ran_steps` は `{ran: ["関わる試験の実行器"], unran: []}`（走らなかった時は `unran` に入れる）。`by` は `role_needed` のまま（語は変えない。意味は「走らせ方が決まらず、AI が書いた実行器で関わる試験を走らせる道」）。
- 止め方は変わらない: 実行器が作れなかった base は止めず（`awaiting_human`）、判定の台帳の問いに載る。final は `not_run`・`incomplete` で認証せず、最後の承認ノードが人に回す。

### 14.6 報告

- test-gate の出力に欄 `related` を足す: `{applied, whole, files, left, far, reasons}`（道 (1)(2)・選びを引かない run は `applied: false`）。
- 報告の部品は line の `src/sections.py`: 節「走らせなかった範囲（CI と人に任せた物）」を足す。base と final の `related` から、走らせた試験の数・走らせなかった試験（`left` の名・`far`）・「全体の試験は CI と人に任せた」・`whole` で一式を走らせた理由を並べる。道 (1)(2) の run は、範囲の宣言で回さなかった段（`skipped_steps`）を載せる（今は `suites_line` に在る物を同じ節に集める）。
- test-gate の `report` の行は、(3) の道で `SELF_REPORTED_NOTE` の代わりに `held` の訳を出す。

### 14.7 変えた守り

- 「任せ先の自己申告の緑を認証しない」: 任せ先の役を外したので、対象が無くなった。代わりに (3) の道の final の緑は認証しない（14.5）。(3) の道の final はこれまでも認証されなかったので、認証の結果は変わらない。
- 「直す前から赤だった試験と直しで壊した試験を分ける」: 変えない。ただし元の結末は関わる試験だけなので、元の結末に無い試験が final で落ちると `introduced`（`_must_pass` の決め）と読まれる。14.3 で final の選びを base の選びを含む形にして減らす。
- 「赤は認証しない」: 変えない。

### 14.8 自分で決めた事

1. 選んだ試験の走らせ方（案 A を採った）: AI が書く実行器に試験のファイルを引数で渡す（TDD の実行器の約束。fix の TDD の輪・受け付けが同じ口で使っている。`baseline_red.run_suite` の `args`・`only`）。案 B（書き手の役に、選んだ試験を実行器の本文に埋め込ませる）は採らない。根拠: 元と同じ（作り直しの前の工場の fix が同じ口で使っている）・実行器は取り置きして使い回すので、run ごとに変わる選びを本文に埋めると取り置きが使えない・約束を解かない実行器は一式を走らせるので、絞れない対象でも壊れない（遅いだけ）。
2. `by` の語 `role_needed` は変えない。根拠: 読み手（line の最後の関所・報告・通しの照らし）が多く、語を替える利益が無い。意味は 14.5 の通り。
3. 任せ先の CI の役を外した後、実行器が作れない対象では (3) の道は試験を走らせない。根拠: 持ち主の決めが「CI を丸ごと再現するのはやめる」。走らせなかった事は `not_run`・`awaiting_human` と報告の節で言い、緑を仮定しない。
4. `lib/` の任せ先の役の部品（`declared_checks` の `role_material_problems`・`CI_ROLE`・`drop_copy`・`NO_ADAPTER_NOTE`、`rolekit` ほか）は、この PR で消さない。ほかの block も読む物で、掃除は別の変更。
5. 新しい port `entry_base`: 14.3 の根拠。line が始めの記録の入口の差分の根（`start.output.ports.base`。judge に渡す物と同じ値）を渡す。

### 14.9 試験

- `lib/tests/test_related.py`: `applies`（test_cmd と宣言が利用者の道を絞らない）・`pick`（直に関わる試験だけを選び、届いただけの試験を `left` に名前で残す・関わる試験が無いのは空の `files`・読めない物が近くに在る/地図が引けないのは `whole` と理由）・`args`・`lines`。
- `tests/blocks/test_gate/test_test_gate.py` の `RelatedCase`: 実行器に渡す引数と `TDD_SUITE_ONLY`（`run` の final・`suite-try`）・入口の差分の根から選ぶ・関わる試験が無ければ実行器を起こさない・`whole` は一式・`test_cmd` と宣言の道は絞らない・書き手の実行器の照らし（関わる試験が無い時だけ一式を 1 回）・`result` の素材（緑は `RUNNER_HELD` で認証しない・元から赤は `inherited`・直しが起こした赤は `introduced`・実行器が無い base は `awaiting_human` で鎖を止めない・実行器が無い final は `not_run`）。
- `tests/blocks/fix/test_tdd.py` の `RelatedStartCase` と `test_group.py`: fix の輪の頭（17 節）。
- `tests/blocks/line/test_collect.py` の `SectionsCase`: 報告の節「走らせなかった範囲」。
