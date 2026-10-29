# block の設計書: spec（仕様）

- 何の話か: 依頼が完成と言える要件と、要件ごとの受け入れテストを書き、別の目で審査して直し、人の承認ノードで承認された物を固める観点「仕様」を、単独で呼べる block `workflows/spec/` にする設計。修正の後に、承認したテストが変わったかを照らす道（今の line の `spec-check`）も同じ block に置く。型は [README.md](README.md) に従い、形は [world.md](world.md) を写した。
- 決めたこと: 今の judge の仕様の 6 つの node の並び（3 つの loop・spec-ask・spec-gate・spec-freeze）と、line の `spec-check` を、`mode` choice(write|check) を持つ 1 つの block にする。入力は依頼の行・PR の題と本文・固めた仕様・印の置き場・言語の port だけで、始めの記録と `judge/` の置き場を読まない。人の承認ノードは block の中に置き、単独の run でも人が答える。指示は 6 本の英語の md（役 3 つと、拒まれた後の出し直し 3 つ）に書く。
- 持ち主に求めること: なし。この block を作る人（実装の役）は、この設計どおりに 1 本の PR で作る（README の 11.1 の 1 波目）。自分で決めた事は 11 節に集めた（記録として置く。持ち主の確認は待たない）。

この文書の語は README の頭の物を使う。ほかに:

- 書く役（spec-write）: 要件と受け入れ条件を書き、受け入れ条件を実行できるテストとして対象のリポジトリに書く AI の役。実装は書かない。
- 審査役（spec-review）: 書く役と別の目で、要件と受け入れ条件の抜け・曖昧さ・範囲の外を挙げる、読むだけの AI の役。
- 直す役（spec-revise）: 審査の穴に key ごとに 1 度だけ答え（absorbed か declared）、直した仕様の全体を返す AI の役。
- 出し直しの役（spec-write-fix・spec-review-fix・spec-revise-fix）: 受け付けに拒まれた後、同じ会話の続きで拒まれた欄だけを返す AI の役（#571。今の `<役>-fix`）。受け付けが前の答えと欄ごとに合わせる。
- 仕様の承認ノード（spec-gate）: 要件・受け入れ条件・審査の穴と答えを人に見せ、通すか止めるかを聞く `wait:` の node。
- 固める: 承認の後に、受け入れ条件の `run` のコマンドを走らせて終了コードを取り、テストのファイルの sha256 とともに `spec.json` に 1 度だけ書くこと。
- 例の run: 仕様の段を通った本物の run は無い（工場の 148 本の run の置き場のどれにも `spec-write.json` が無い。2026-10-19 に探した）。骨組みは、依頼の行を本物の run `df5e111f-ea97-409b-8066-2245d32746ab`（対象 raiki61/works-factory。置き場 `~/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/artifacts/runs/df5e111f-…/judge/request.json`。1 行）から、仕様の返答を今の筋書き `workflows/judge/fixtures/spec-on.stubs.yaml` から取って描いた。

## 1 block の全体

### 1.1 役

- write: 依頼が完成と言える条件を、修正案より前に 1 件ずつ書き、要件ごとの受け入れ条件を実行できるテスト（Given / When / Then の 3 語を中に持つ）として対象に書かせる。別の目で穴を挙げさせ、書き手に key ごとに答えさせ、人に承認を求める。承認されたら受け入れ条件を走らせて固め、受け入れ条件を依頼の行として返す（後の判定がほかの所見と同じく反証の対象にする）。
- check: 承認済みの仕様の受け入れ条件のテストのファイルが、承認の時の版から変わったかを sha256 で照らし、変わった所を承認し直すかの問いにする。照らせなかったら黙って 0 件にせず、照らせなかったと言う。

### 1.2 port

入力（YAML の `inputs:`）:

- `mode`: `choice(write|check): write は仕様を書いて審査し、承認ノードの後に固める。check は固めた仕様の受け入れ条件のテストが承認の版から変わったかを照らす`。既定 `write`。
- `request`: `json(request.schema.json): 依頼の行の配列 [{where, text, mechanism?, measured?, false_positive_if?}]。それを findings の欄に持つオブジェクトでもよい。check では読まない`。既定 `[]`。
- `pr_text`: `text: 依頼が名指す PR の題と本文（write の役に見せる）。空は PR が無い`。既定 `""`。
- `spec`: `file: check で照らす固めた仕様（write の出力 spec の pointer）。write では読まない。check で空なら、照らす仕様が無いという問いを返す`。既定 `""`。
- `user_env_dir`: `text: 受け入れ条件のコマンドを利用者の HOME・XDG に戻して走らせた印を置くフォルダの絶対パス。空なら place に置く`。既定 `""`。
- `lang`: `text: 人に見せる欄（requirements の text・out_of_scope・faces の why・handled の how）の言語。空は依頼の行の言語`。既定 `""`。

出力（`returns: finish`、`outcome_field: ok`）:

- `ok`: boolean。write は `status` が `approved`、check は `status` が `checked`。
- `status`: write は `approved`（承認されて固めた）・`stopped`（人が承認ノードで止めた）・`failed`（役を諦めた・仕様が揃わない・固められない・入力が読めない）。check は `checked`（照らせた。問いは 0 件でもよい）・`unchecked`（照らせなかった）。
- `stop_reason`: write の `stopped` は `human:spec-gate`（`lib/stopby.py` の `HUMAN` + `spec-gate`）か `request:spec-gate`（一言が `request:` で始まる）、`failed` は `works:spec`（`stopby.declare("spec", …)` の語。今の `SPEC_STOP`）。ほかは空。check はいつも空（承認し直すかの問いで run を人待ちにするかは line が決める。今の `works:spec-changed`）。
- `reason`: 日本語の 1 行（人に見せる）。止めた・落ちた訳。
- `spec`: pointer（`spec.json`。今の `judge/spec.json` と同じ形 `{requirements, acceptance: [{key, requirement, file, name, run, sha256, exit_at_approval, run_error?}], out_of_scope, approval}`）か null。
- `added_rows`: pointer（`added-rows.json`。依頼の行の配列で、受け入れ条件 1 件が 1 行。今 `spec_freeze` が `judge/request.json` に積んでいた行と同じ字）か null。
- `added_origin`: 字。足した行の出どころの名（今の `SPEC_ORIGIN`「仕様（人が承認した受け入れ条件。テストの本文は writer が書いた）」）。行が無ければ空。
- `questions`: 字の配列。check の承認し直すかの問い（1 ファイル 1 行）。write は空。
- `unchecked`: boolean。check で照らせなかったか（仕様が無い・読めない・落ちた）。write は偽。
- `report`: 報告の節「仕様」の日本語の行の配列（9 節）。

今との違い: 今は依頼の行・止めの控え・却下の控え・役の返答を `judge/` の決まった名で開き（`lib/judge_accept.py:2999-3175`）、言語の 1 行を始めの記録から引き（`rejects.py` の `INPUTS_START`）、固めた後に `judge/request.json` に行を積んで判定の残りに渡し、作業ツリーの写し `judge/judge-tree.json` を取り直していた。check は line の script が `judge_accept.spec_questions` を呼んでいた。行の積み・写しの取り直しは無くし、足した行は出力で返す（line が判定に渡す）。

### 1.3 node の並び（`workflows/spec/works-factory-spec.yaml`）

AI の node の起動の鍵（今の YAML の錨のまま写す）:

- 書く系（spec-write・spec-write-fix・spec-revise・spec-revise-fix）: `model: '@wf-judge-spec'`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob, Edit, Write, Bash, WebSearch, WebFetch]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`idle_timeout: 1728000000`・`retry: {max_attempts: 2, on_error: all}`。`mutates_checkout:` は書かない（Edit・Write・Bash を持つ。E7）。
- 審査系（spec-review・spec-review-fix）: `model: '@wf-judge-core'`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob, WebSearch, WebFetch]`・同じ sandbox・`mutates_checkout: false`・`idle_timeout: 1728000000`・`retry: {max_attempts: 2, on_error: all}`。

並び:

1. `intake`（script `intake.py`。`mutates_checkout: false`）: port を読み、mode を決める。write なら place の中のこの block のファイルを名で引いて消し（place そのものは消さない。README の 13 章）、依頼の行を `request.json` に書く。返り `{mode, go, reason}`（`mode` は `write`・`check`、`go` は先へ進むか）。
2. `spec-write-loop`（`loop_group`、`max_iterations: 3`、`fresh_context: false`、`until_bash: 'done=$spec-write-accept.output.done; test "$done" = true'`。`depends_on: [intake]`・`when: "$intake.output.go == true && $intake.output.mode == 'write'"`）
   - `spec-write-prep`（script `write_prep.py`。`with: {prev: "$LOOP_PREV.spec-write-accept.output.ok"}`）: 返り `{prompt, resubmit}`。
   - `spec-write`（AI。`prompt: "$spec-write-prep.output.prompt"`・`depends_on: [spec-write-prep]`・`when: "$spec-write-prep.output.resubmit != true"`・書く系の鍵。`output_format` は 2.4 の形）。
   - `spec-write-fix`（AI。`prompt: "$spec-write-prep.output.prompt"`・`depends_on: [spec-write-prep, spec-write]`・`trigger_rule: none_failed_min_one_success`・`when: "$spec-write-prep.output.resubmit == true"`・書く系の鍵。`output_format` は 2.4 と同じ物（#832。型が違うと会話の続きの最初の要求でキャッシュが効かない。型の根（一番外の object）は `required: []` で、根の要る欄は受け付けが `rolekit.resubmitted` で確かめ、欠ければ拒む））。
   - `spec-write-accept`（script `take.py`。`depends_on: [spec-write, spec-write-fix]`・`trigger_rule: none_failed_min_one_success`・`with: {role: write, status_guarded: false, reply: {from: "$spec-write.output", if_skipped: null}, fix_reply: {from: "$spec-write-fix.output", if_skipped: null}}`）: 返り `{ok, done, reason, revise}`（4 つとも required）。
3. `spec-review-loop`（同じ形。`depends_on: [spec-write-loop]`・`when: "$spec-write-loop.output.ok == true"`。中は `spec-review-prep`〔`review_prep.py`〕・`spec-review`・`spec-review-fix`〔審査系の鍵〕・`spec-review-accept`〔`take.py`、`role: review`・`status_guarded: true`〕）。
4. `spec-revise-loop`（同じ形。`depends_on: [spec-review-loop]`・`when: "$spec-review-loop.output.revise == true"`。中は `spec-revise-prep`〔`revise_prep.py`〕・`spec-revise`・`spec-revise-fix`〔書く系の鍵〕・`spec-revise-accept`〔`take.py`、`role: revise`・`status_guarded: false`〕）。
5. `spec-ask`（script `ask.py`。`depends_on: [intake, spec-write-loop, spec-review-loop, spec-revise-loop]`・`trigger_rule: all_done`・`when: "$intake.output.go == true && $intake.output.mode == 'write'"`・`mutates_checkout: false`）: 承認ノードを開くかと文。返り `{ask, message}`。
6. `spec-gate`（`depends_on: [spec-ask]`・`when: "$spec-ask.output.ask == true"`・`wait: {attention: "$spec-ask.output.message", form: select, options: [{id: approve}, {id: continue}, {id: stop}, {id: reject}]}`）: 今のまま。
7. `spec-freeze`（script `freeze.py`。`depends_on: [intake, spec-ask, spec-gate]`・`trigger_rule: all_done`・`when: "$intake.output.go == true && $intake.output.mode == 'write'"`・`with: {answer: {from: "$spec-gate.output", if_skipped: null}}`）: 答えを受けて固める。受け入れ条件のコマンドを走らせるので `mutates_checkout:` は書かない（今の試験 `test_spec_freeze_may_change_the_checkout`）。返り `{go, reason}`。
8. `spec-check`（script `check.py`。`depends_on: [intake]`・`when: "$intake.output.mode == 'check'"`・`mutates_checkout: false`）: 返り `{questions, unchecked}`。
9. `finish`（script `finish.py`。`depends_on: [intake, spec-ask, spec-freeze, spec-check]`・`trigger_rule: all_done`・`mutates_checkout: false`）: 出力を組んで返す。どの段が落ちても落ちない（K1・K13）。`output_format` は 1.2 の出力の欄を全部 required にし、`spec`・`added_rows` は `{type: [object, "null"]}`、`questions`・`report` は字の配列。

loop の出口を `$spec-write-loop.output.ok` で読むのは今の YAML と同じ形（loop の出力は最後の node の出力）。script の名は `lib/` のモジュールと重ねない（`accept.py`・`report.py` は lib に在るので `take.py`・`finish.py` にした）。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、line から include された時は `$ARTIFACTS_DIR/<include の道>/`。write と check を line が別の include にすれば place も分かれる）の下に書く。名は `src/files.py` だけが持つ。今の `judge/` の名をそのまま使う:

- `intake.json`・`request.json`（依頼の行。役が Read する）
- `spec-write.json`・`spec-review.json`・`spec-revise.json`（受け付けた返答）
- `candidate-spec-write.json` など（`rolekit.candidate_path`。出し直しを合わせる元）
- `rejects-spec-write.json`・`rejects-spec-review.json`・`rejects-spec-revise.json`
- `spec-snapshot-spec.review.json`（審査役の前の作業ツリーの写し。今の `specblk.snapshot_name("spec.review")`）
- `spec-ask.json`（承認ノードに見せた仕様と文）・`spec.json`・`added-rows.json`
- `stop.json`（block の中の止めの控え。最初に止めた node の物だけ残す。今の `write_stop` の形 `{stop_reason, reason}`。block の外は読まない）
- `<node-id>-prompt-<n>.md`（組んだ指示。`<node-id>` は 6 つの AI の node の id）
- 印 `user-env-ran`（`user_env_dir` が空の時。`lib/userenv.py` が置く）

### 1.5 コードの置き場

- `workflows/spec/src/files.py`: 1.4 の名と、役の名の表 `ROLES = {"write": "spec-write", "review": "spec-review", "revise": "spec-revise"}`・拒否の文の頭の節の名 `NODES = {"write": "spec.write", "review": "spec.review", "revise": "spec.revise"}`（今の `SPEC_ROLES`・`SPEC_NODES`）・`GWT = ("Given", "When", "Then")`・`STOP = stopby.declare("spec", "仕様のループが諦めた・固まらなかった")`・`GATE = "spec-gate"`。
- `workflows/spec/src/take.py`: 今の `lib/judge_accept.py` の `_spec_errors`（:2908）・`spec_write_output`（:2931）・`spec_review_output`（:2938）・`spec_revise_output`（:2948）・`spec_revise_due`・`spec_faces_open`・`spec_view`（:2962-2989。仕様の道かの条件 `spec_flow` は消し、block が呼ばれたら仕様の道）・`spec_now`（:2992）・`spec_take`（:2999）・`_keys_once`・`blank`・`read_capped`・`READ_CAP` の使う分の写し。`Reject` は `lib/accept.py` の物。
- `workflows/spec/src/gate.py`: 今の `spec_approve`（:3038）・`spec_ask`（:3062）・`spec_answer`（:3135）と、`lib/specblk.py` の `APPROVE`・`GATE_STOP_NOTE`・`FLAG_BY_PREFIX`・`gate_text`・`parse_gate` の写し（`RUN_ID_HOLE` は `gate_text` の中の字 `<id>`、`snapshot_name` は `files.py` の `snapshot_path` に移した）。`gate_text` は `lib/gatemarks.py` の `gate_text`（line の修正前の承認ノードと共に使う組み立て）を呼ぶ。
- `workflows/spec/src/freeze.py`: 今の `sha_file`・`sha_and_why`・`_file_sha`・`_spec_run`（:3089）・`spec_freeze`（:3102）の写しと、足した行の字 `ORIGIN`・`PROVENANCE`（今の `SPEC_ORIGIN`・`SPEC_PROVENANCE`、:2875-2876 の字のまま）。`spec_freeze` は依頼の行のファイルに積まず、`added-rows.json` に書く。
- `workflows/spec/src/check.py`: 今の `spec_check`（:3177）・`spec_questions`（:3195）の写しと、仕様が渡されない時の問いの字（今の `workflows/line/scripts/spec_check.py` の `NO_POINTER` を「照らす承認済みの仕様が渡されていない——受け入れ条件のテストが変わったかを照らせない」に）と、照らしが落ちた時の問いの字（今の `fallback` の字）。問いの頭の語は `lib/gatemarks.py` の `SPEC_CHANGED_LABEL`（問いの行の形。最後の承認ノードと報告も読む）。
- `workflows/spec/src/report.py`: 報告の行（9 節）。
- `workflows/spec/schemas/request.schema.json`（world と同じ形の写し）。
- 使う `lib/`: `accept`（`tree_state`・`tree_moved`・`TREE_KEYS`・`status_keys`・`Reject`）・`rolekit`（`accept_parsed`・`resubmitted`・`merge_fields`・`resubmitting`・`candidate_path`・`rejected`・`rejects_text`・`given_up_reason`・`attempt`・`BoardGap`）・`tree_run`（`run`・`outside_env`）・`userenv`（印）・`gatemarks`（`gate_text`・`SPEC_CHANGED_LABEL`）・`answer`（`GO_WORDS`・`STOP_WORDS`。`gate_text` の答え方の行）・`stopby`（`HUMAN`・`declare`）・`graphloops/engine/util.py`（`safe_name`）・`jsonfile`・`oneline`。

### 1.6 つなぎ方（graph の側。block には書かない）

- write: judge のまとめ（`workflows/judge/`）が `include: works-factory-spec` を置く。`when:` は line が始めの記録の `input.spec` から引いた真偽。`with:` は `mode: write`・`request: $<依頼の pointer>`・`pr_text: <依頼が名指す PR の題と本文。purpose の block の pr_text と同じ値>`・`user_env_dir: <始めの記録の user_env_dir>`・`lang`。仕様の段は今と同じく、直す前の試験の関門（test-gate base）の後、並行 PR の前に回す（赤い受け入れテストが直す前の結末を汚さないため。並行 PR の役の前の写しに受け入れテストを入れるため）。`status` が `approved` でなければ、line は今と同じく run を `stop_reason` で止める。
- write の出力の読み手: diagnose（`added_rows` と `added_origin`。今の `request_batches` が `SPEC_PROVENANCE` の頭で分けていたバッチ）・plan（`spec`。案の項目の `tests` に受け入れテストを入れる。今の `plan_prep.py:18` の `INPUTS_SPEC`）・再審の材料（`spec`）・report（`report`）・check の include（`spec`）。
- check: line が fix の後・最後の試験の前に `include: works-factory-spec` を置く（今の `spec-check` の node の所）。`when:` は「仕様の段を挟んだ run」（始めの記録の `input.spec`）。`with:` は `mode: check`・`spec: <write の出力の spec。無ければ空>`。line は `questions` が在れば `stop_reason` を `works:spec-changed` にし（今の `spec_check.py:43`）、`unchecked` を最後の承認ノードと報告に渡す。
- 無人の run と仕様の段の組みは、今と同じく line の入口が拒む（`lib/gatepolicy.py:61` の `check`。仕様の承認は承認ノードで、無人の run は承認ノードで止めるため）。block は無人の方針を知らない。

## 2 node の設計シート: spec-write（書く役）

### 2.1 役

依頼が完成と言える要件を 1 件ずつ書き、要件ごとの受け入れ条件を、Given / When / Then を中に持つ実行できるテストとして対象のリポジトリに書く。実装は書かない。

### 2.2 port

`request.json`（← port `request`。パスを渡して役が Read する）・`pr_text`（← port `pr_text`）・前の回までの却下の理由（← `rejects-spec-write.json`）・`lang`。リポジトリは run の作業ツリー。

### 2.3 組み立ての順（`prompts/spec-write.md`）

1. `<!-- if rejected -->` `{shared:rejected}` と、テストのファイルを先に直せの 1 文 `<!-- end rejected -->` — 条件: 却下の控えが空でない。`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "spec-write"))`。
2. `{shared:query-rule}`（`spawns: false`。この役は Agent の道具を持たない）。
3. 役の定義（決まった文）。
4. `# Write the spec` と読む物の箇条: `{request_file}`（← `src/files.py` の `request.json` の絶対パス）・`<!-- if pr_text -->` PR の題と本文の見出しと `{pr_text}` `<!-- end pr_text -->`・リポジトリ。
5. この node が在る訳（決まった文）。
6. `## What to do` の 3 項（決まった文）。
7. 書いてよい物の決まり（決まった文）。
8. `## How to answer` と `{lang}`。
9. 結びの 1 文。

md の本文（英語。この block の PR でこのまま置く）:

```markdown
<!-- if rejected -->
{shared:rejected}

If the rejection says a test file is missing, a test name is missing, or Given/When/Then is missing, fix the test file in the target repository first, then answer.
<!-- end rejected -->

{shared:query-rule}

You are the spec writer. Your job is to write, one by one, the requirements under which the request can be called complete, and to write the acceptance condition of each requirement into the target repository as an executable test. Do not write the fix (the implementation) yet.

# Write the spec

- Request: read `{request_file}` (the request lines; a person's fix request is here too).
- Repository: the current working directory (the root of the target repository's working tree).

<!-- if pr_text -->
## Pull request

The title and body of the pull request the request names:

{pr_text}
<!-- end pr_text -->

**Why this step exists**: conditions that the request does not state did not enter the fix plan, and surfaced only when the plan review raised them as holes. (Measured 2026-09-25: in a run that built a new entry point, the request listed 6 requirements but not "from the second round on, run the first checks as usual". The first plan kept those checks from coming back until the end of the run, and the plan review stopped it as must-fix.) **Before any plan, write one by one what must hold for the work to be complete.**

## What to do

1. `requirements`: one condition per entry under which the request is complete. `key` is short and unique (R1, R2, …); `text` is one sentence. Dig out and add the conditions the request needs even when it does not state them: the default behavior does not change, the behavior across rounds or stages, what happens on failure, what happens when nobody answers, and how to undo.
2. `acceptance`: for each requirement, at least one acceptance condition, **written into the target repository as an executable test (write it now, in this step)**. Inside the test, write the premise, the action, and the expectation with the three words Given / When / Then (in a docstring or a comment). **The test file is the source of the text.** In this answer write only where it is (`file`: relative to the repository root; `name`: the test's name) and the command that runs it (`run`). Do not copy the test's text into the answer. Put the test where the repository's test suite (what CI runs) picks it up. The fix is not in yet, so **it is correct for the test to be red now**. The machine shows a person the literal text of each `run` command and asks for approval; only after approval does it run the command and record the exit code. It does not run it before approval. If the test is already green at that point, that is recorded as "red was not seen".
3. `out_of_scope`: what you decided is outside the request's scope (empty if nothing).

In the working tree you may write test files only. Do not write the implementation yet: do not change a single character of implementation files. Nobody runs the `run` commands before approval (a person reads their literal text and approves, then the machine runs them).

## How to answer

- Write `requirements[].text` and `out_of_scope` in {lang}. Keep keys, file paths, test names, and commands as they are.

Return only JSON that matches the output schema.
```

### 2.4 返す形

今の `output_format` のまま（錨 `&spec_reply`）: `{requirements: [{key (1 字以上), text (4 字以上)}] (1 件以上), acceptance: [{key, requirement, file, name, run}（どれも 1 字以上）] (1 件以上), out_of_scope: [字]}`（3 つとも要る。ただし型の根は `required: []` で、3 つ（`src/files.py` の `REPLY_REQUIRED`）は受け付けが確かめる。出し直しの役は同じ型。#832。錨 `&spec_reply` 自体は 3 つを `required` に書いたまま持ち、この役の型が根で `required: []` に上書きする。直す役（4.4）の欄 `spec` は錨をそのまま入れるので、そこでは型が 3 つを求める）。人に見せる欄は `requirements[].text`・`out_of_scope`（承認ノードと報告に載る）で、言語は `{lang}`。

### 2.5 描いた骨組み（例の値）

```markdown
Rules for queries to outside services …（{shared:query-rule}。spawns が false）

You are the spec writer. …（決まった文）

# Write the spec

- Request: read `~/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/artifacts/runs/df5e111f-ea97-409b-8066-2245d32746ab/judge/spec/request.json` (the request lines; …).
- Repository: the current working directory (…).

**Why this step exists**: …

## What to do

1. `requirements`: …
2. `acceptance`: …
3. `out_of_scope`: …

In the working tree you may write test files only. …

## How to answer

- Write `requirements[].text` and `out_of_scope` in the language of the request lines. …

Return only JSON that matches the output schema.
```

例の run の依頼は 1 行（`where`: 「workflows/merge/scripts/pr_commit.py の hook_env（73 行あたり）」）で、PR を名指さないので `pr_text` の節は入らない。1 回目なので却下の段落も入らない。place のパスは line から judge のまとめを通して include された形（`judge/spec/`）で書いた。

### 2.6 今の指示との差

今の指示は `workflows/judge/commands/spec.md`（52 行）1 本。lib の Python は指示の文を組んでいない（値は Archon の置き換え）。

- 移した: 却下の段落（md:17-25）を `{shared:rejected}` に。テストのファイルを先に直せの 1 文はこの役だけの物なので md に残し、却下が在る時だけ入れる。「下の理由が空なら、これは 1 回目の返答で…読み飛ばしてよい」は、却下が無い時は段落ごと入れない形にして要らなくした（world と同じ）。
- 移した: 外への検索の決まりの塊（md:3-12）を `{shared:query-rule}` に。頭の「works の包みより」は消した。
- 移した: 言語の 1 行（md:1 の `$spec-reject.output.lang_line`）を、この役の人に見せる欄を名指す 1 文に。
- 替えた: 依頼のパス `$ARTIFACTS_DIR/judge/request.json` を `{request_file}` に。
- 足した: PR の題と本文の節（`<!-- if pr_text -->`）。元の works と graphloops の指示は依頼の本文（`{{inputs.request}}`。PR の題と本文を含む）を読んでいたが、工場の指示は依頼の行だけを読み、PR の題と本文だけで仕様の段を選んだ run（`workflows/line/scripts/start.py:257` が受ける）では役に何も届かなかった（7 節の 4）。`pr_text` が空なら今と同じ字。
- 替えた: この node が在る訳の実測の例の「2 周目以降は P1 を通常どおり走らせる」「P1 が run の最後まで戻らない」を、graphloops の段の名 P1 を外した言い方に（block は段の名を知らない）。
- 消した: 「同じテストが、後で TDD の『先に書く赤いテスト』になる」「その時点で緑なら『赤を見ていない』と判定役に渡る」の、後ろの block の振る舞いを前提として伝える部分（world の 3.6 と同じ決め）。「赤を見ていないと記録される」だけを残した。
- 消した: 見出しの括弧「（writer の仕事。仕様の道だけ）」と、役の札「writer」。
- 消した: 外への検索の決まりの頭の「Agent で子を起こすなら、子への指示に下の塊をそのまま含めよ」（この役は Agent の道具を持たない。断片の `spawns` の段落に `false` を渡して出さない）。
- 英語にした（#764）。役の名は "the spec writer"。

## 3 node の設計シート: spec-review（審査役）

### 3.1 役

仕様を書いていない目で、書かれた要件と受け入れ条件の抜け・曖昧さ・範囲の外を、修正案より前に挙げる。読むだけ。

### 3.2 port

`request.json`（← port `request`）・`pr_text`・`spec-write.json`（← 書く役の受け付けを通った返答。block の中）・前の回までの却下の理由（← `rejects-spec-review.json`）・`lang`。

### 3.3 組み立ての順（`prompts/spec-review.md`）

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->`。
2. `{shared:role-judge}`（役の定義 5 本のうち judge。今の `lib/agents/judge.md` の本文の、外への検索の決まりを除いた部分）。
3. `{shared:query-rule}`（`spawns: false`）。
4. 役の定義と読むだけの決まり（決まった文）。
5. `# Review the spec` と読む物: `{request_file}`・`<!-- if pr_text -->` `{pr_text}` `<!-- end pr_text -->`・`{spec_file}`（← `spec-write.json` の絶対パス）・リポジトリ。
6. この役が在る訳（決まった文）。
7. `## What to look at` の 3 項と差し込み口 `{missing}`・`{ambiguous}`・`{out_of_scope}`（← `src/files.py` の穴の種類の語。`output_format` の enum と同じ字）。
8. `## How to answer`（決まった文）と `{min_why}`・`{min_reason}`（← `src/files.py` の 20。今の `output_format` の `minLength: 20` と受け付けの `blank(…, 20)`）・`{lang}`。
9. 結びの 1 文。

md の本文（英語）:

```markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{shared:role-judge}

{shared:query-rule}

You are the spec reviewer. With eyes other than the writer's, raise the gaps, ambiguities, and out-of-scope items in the written requirements and acceptance conditions, before any fix plan exists.

You only read. Your tools are Read, Grep, Glob, and web search and fetch. Do not change a single character of the working tree: the machine compares a copy of the working tree taken before you started with the current one, and rejects the answer if it changed.

# Review the spec

- Request: read `{request_file}` (the request lines; a person's fix request is here too).
- The spec the writer wrote (requirements, and where the acceptance tests are): read `{spec_file}`.
- Repository: the current working directory. The text of each acceptance condition is the test `name` in each `file`; read it.

<!-- if pr_text -->
## Pull request

{pr_text}
<!-- end pr_text -->

**You are eyes that did not write the spec.** The writer will also write the fix later, so it may write only the conditions that suit its own plan. Your job is to find **gaps in the conditions for completion** before the plan. (Measured 2026-09-25: in a run that built a new entry point, "from the second round on, run the first checks as usual" was missing from the conditions, and the first plan kept those checks from coming back until the end of the run.)

## What to look at

1. **Missing conditions** (kind `{missing}`): conditions the request needs that are in neither the requirements nor the acceptance conditions. In particular: the default behavior (nothing changes when the option is not chosen), behavior across rounds and stages (not only the first time but the second and later), how it ends (stopped, failed, nobody answering), how to undo, and combination with other features that can be chosen at the same time.
2. **Ambiguity** (kind `{ambiguous}`): a sentence that does not settle to one condition under which the test holds; a test whose Then is weaker than the requirement (passes whatever is returned); a test that checks something other than the requirement; a test placed where the repository's test suite (CI) does not pick it up.
3. **Out of scope** (kind `{out_of_scope}`): requirements or acceptance conditions that go beyond the request's scope.

## How to answer

The answer is JSON with three top-level fields: `faces` (the array of holes; required), `faces_none` (a string, when there are no holes; optional), and `reason` (the reason for the whole judgment; required, at least {min_reason} characters). There is no dedicated field for "insufficient", "cannot be verified", or "not found"; write those, and "lookups not made because they need the target's names", in `reason` (and, as below, also raise what is missing as a hole in `faces`).

- `faces` has one entry per hole. Every hole has all four fields `key`, `kind`, `where`, `why` (all required). `key` is short and unique (at least 2 characters). `kind` says which of the views 1 to 3 above found it (`{missing}`, `{ambiguous}`, or `{out_of_scope}`). `where` is the key of a requirement or acceptance condition, or a file. `why` is the line of reasoning that makes it a hole (at least {min_why} characters).
- If you judge there are no holes, leave `faces` empty and write in `faces_none` what you checked that lets you say there are none.
- When input is insufficient (this is how to write "say it is insufficient" from the role definition above in this answer's form): if the request or the spec file cannot be read, or the test file of an acceptance condition does not exist, do not say there are no holes in `faces_none`. Raise one hole of kind `{missing}` for each thing that cannot be read or does not exist, with that thing (a file path or a requirement key) in `where`, and start `why` with "insufficient:" followed by what you could not check. Write "insufficient" in `reason` too.
- The writer answers each `key` in `faces` in the next step, saying whether it absorbed it or declared to leave it, and then a person approves the spec.
- Write `faces[].why`, `faces_none`, and `reason` in {lang}. Keep keys, enum values, paths, and test names as they are.

Return only JSON that matches the output schema.
```

「insufficient:」の頭の語は、今の日本語の「足りない:」の英語。`why` は人に見せる欄なので `{lang}` の言語で書かれ、`{lang}` が日本語なら頭の語も「足りない:」になる（md の字は英語のまま。受け付けはこの頭の語を照らさない。今も照らしていない）。

### 3.4 返す形

今の `output_format` のまま（錨 `&spec_review_reply`）: `{faces: [{key (2 字以上), kind (missing|ambiguous|out_of_scope), where (1 字以上), why (20 字以上)}], faces_none?: 字, reason (20 字以上)}`（要る欄は `faces`・`reason`。型の根は `required: []` で受け付けが確かめ、出し直しは同じ型。#832）。人に見せる欄は `faces[].why`・`faces_none`・`reason`（承認ノードに `why` の頭 200 字が載る）で、言語は `{lang}`。

### 3.5 描いた骨組み（例の値）

```markdown
{shared:role-judge の本文: You are the judge. …（役の定義 5 行）}

Rules for queries to outside services …

You are the spec reviewer. …

You only read. …

# Review the spec

- Request: read `…/runs/df5e111f-ea97-409b-8066-2245d32746ab/judge/spec/request.json` (…).
- The spec the writer wrote …: read `…/runs/df5e111f-ea97-409b-8066-2245d32746ab/judge/spec/spec-write.json`.
- Repository: …

**You are eyes that did not write the spec.** …

## What to look at

1. **Missing conditions** (kind `missing`): …
2. **Ambiguity** (kind `ambiguous`): …
3. **Out of scope** (kind `out_of_scope`): …

## How to answer

The answer is JSON with three top-level fields: … (… at least 20 characters). …
- `faces` …（at least 20 characters）…
- Write `faces[].why`, `faces_none`, and `reason` in the language of the request lines. …

Return only JSON that matches the output schema.
```

筋書きの値では、書く役の返答は `requirements: [{key: R1, text: mean は要素の数で割る}]`・`acceptance: [{key: A1, requirement: R1, file: test_spec.py, name: test_mean_divides_by_count, run: make test-mean}]`（`spec-write.json` の中身。指示には貼らない）。

### 3.6 今の指示との差

今の指示は `workflows/judge/commands/spec-review.md`（59 行）1 本。

- 移した: 役の定義の塊（md:17-31。`lib/agents/judge.md` の本文の写し）を `{shared:role-judge}` と `{shared:query-rule}` に割った（judge の本文の外への検索の決まりの部分が、query-rule の元と同じ字のため。役の定義の断片は検索の決まりを持たない）。
- 移した: 却下の段落（md:7-15）を `{shared:rejected}` に。言語の 1 行（md:1）を人に見せる欄を名指す 1 文に。
- 替えた: 依頼と書く役の返答のパスを `{request_file}`・`{spec_file}` に。穴の種類の語と 20 字の下限を差し込み口に（md と `output_format` と受け付けが同じ字を持つ。README の 5.3）。
- 足した: PR の題と本文の節（2.6 と同じ訳）。
- 替えた: 実測の例の P1 の名（2.6 と同じ）。
- 消した: 見出しの括弧「（judge。仕様の道だけ）」と、役の札「judge」の 2 度目（役の定義の断片が言う）。
- 並べ替えた: 却下の段落を頭に（world と同じ）。役の定義・検索の決まり・この役の文の順は今のまま。
- 足した: 「読むだけ」の段落（Read・Grep・Glob と web の検索と取得だけを持ち、作業ツリーを 1 字も変えない。機械が起こす前の写しと今を比べ、変わっていれば答えを拒む）。
- 消した: 外への検索の決まりの頭の「Agent で子を起こすなら、子への指示に下の塊をそのまま含めよ」（この役は Agent の道具を持たない。断片の `spawns` の段落に `false` を渡して出さない）。
- 英語にした。役の名は "the spec reviewer"。

## 4 node の設計シート: spec-revise（直す役）

### 4.1 役

審査の穴に key ごとに 1 度だけ答え（取り込んだか、残すと宣言したか）、直した仕様の全体を返す。足した受け入れ条件のテストは対象に書いてから返す。

### 4.2 port

`spec-write.json`・`spec-review.json`（← block の中の受け付けを通った返答）・`request.json`（← port `request`）・`pr_text`・前の回までの却下の理由（← `rejects-spec-revise.json`）・`lang`。

### 4.3 組み立ての順（`prompts/spec-revise.md`）

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->`。
2. `{shared:query-rule}`（`spawns: false`）。
3. 役の定義（決まった文）。
4. `# Revise the spec` と読む物: `{spec_file}`・`{review_file}`（← `spec-review.json` の絶対パス）・`{request_file}`・`<!-- if pr_text -->` `{pr_text}` `<!-- end pr_text -->`・リポジトリ。
5. 答え方の決まり（決まった文）と `{absorbed}`・`{declared}`（← `src/files.py` の語。`output_format` の enum と同じ字）・`{min_how}`（← 20）。
6. 書いてよい物の決まり（決まった文）。
7. `## How to answer` と `{lang}`。
8. 結びの 1 文。

md の本文（英語）:

```markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{shared:query-rule}

You are the spec reviser. Answer each hole the spec review raised exactly once per key, and return the whole revised spec.

# Revise the spec

- The spec as first written: read `{spec_file}`.
- The holes the spec review raised: read `{review_file}`.
- Request: read `{request_file}`.
- Repository: the current working directory (the root of the target repository's working tree).

<!-- if pr_text -->
## Pull request

{pr_text}
<!-- end pr_text -->

Answer the review's holes (`faces`) **exactly once per key** in `handled`. If you absorbed a hole, write `{absorbed}` and, in `how`, how you absorbed it (the keys of the requirements and acceptance conditions you added). If you do not absorb it, write `{declared}` and, in `how`, why you leave it (if the hole is wrong, where in the actual code or documents it is wrong). `how` is at least {min_how} characters. If any key is left unanswered, the machine rejects the answer.

Return the whole revised spec in `spec` (the same shape as the first spec). Write the tests of any acceptance conditions you added into the target repository before you answer. After this, the machine shows a person the spec, the review's holes, and your answers (including the literal text of each acceptance condition's `run` command) and asks for approval; it runs the `run` commands only after approval.

In the working tree you may write test files only. Do not change a single character of implementation files.

## How to answer

- Write `spec.requirements[].text`, `spec.out_of_scope`, and `handled[].how` in {lang}. Keep keys, enum values, file paths, test names, and commands as they are.

Return only JSON that matches the output schema.
```

### 4.4 返す形

今の `output_format` のまま（錨 `&spec_revise_reply`）: `{spec: <2.4 の形>, handled: [{key (2 字以上), handled (absorbed|declared), how (20 字以上)}]}`（要る欄は 2 つ。型の根は `required: []` で受け付けが確かめ、出し直しは同じ型。#832）。人に見せる欄は `spec.requirements[].text`・`spec.out_of_scope`・`handled[].how`（承認ノードに `how` の頭 200 字が載る）で、言語は `{lang}`。

### 4.5 描いた骨組み（例の値）

```markdown
Rules for queries to outside services …

You are the spec reviser. …

# Revise the spec

- The spec as first written: read `…/judge/spec/spec-write.json`.
- The holes the spec review raised: read `…/judge/spec/spec-review.json`.
- Request: read `…/judge/spec/request.json`.
- Repository: …

Answer the review's holes (`faces`) **exactly once per key** in `handled`. If you absorbed a hole, write `absorbed` … write `declared` … `how` is at least 20 characters. …

Return the whole revised spec in `spec` …

In the working tree you may write test files only. …

## How to answer

- Write … in the language of the request lines. …

Return only JSON that matches the output schema.
```

筋書きの値では、審査の返答は `faces: [{key: F1, kind: ambiguous, where: R1, why: 空の並びの時に何を返すかが書かれていない}]`、直す役の答えは `handled: [{key: F1, handled: declared, how: 空の並びは範囲の外と out_of_scope に宣言した}]`。

### 4.6 今の指示との差

今の指示は `workflows/judge/commands/spec-revise.md`（39 行）1 本。

- 移した: 却下の段落（md:17-25）・外への検索の決まり（md:3-12）・言語の 1 行（md:1）を、2.6 と同じ形に。
- 替えた: 3 つのパスを `{spec_file}`・`{review_file}`・`{request_file}` に。答えの語と 20 字を差し込み口に（今の md は 20 字を言っていなかった。`output_format` の `minLength: 20` を役が知らずに拒まれる道を塞ぐ。値は今と同じで、振る舞いは変えない）。
- 足した: PR の題と本文の節（2.6 と同じ訳）。
- 替えた: 「engine が … 人に見せて承認を求め」の engine を「the machine」に（graphloops の engine の名は block の外の物）。
- 消した: 見出しの括弧「（writer の仕事。仕様の道だけ）」と役の札「writer」。
- 消した: 外への検索の決まりの頭の「Agent で子を起こすなら、子への指示に下の塊をそのまま含めよ」（この役は Agent の道具を持たない。断片の `spawns` の段落に `false` を渡して出さない）。
- 英語にした。役の名は "the spec reviser"。

## 5 node の設計シート: spec-write-fix・spec-review-fix・spec-revise-fix（出し直しの役）

### 5.1 役

受け付けに拒まれた後、1 回目の役と同じ会話の続きで、拒まれた所だけを直して返す。材料とリポジトリは会話の中で読んだ物のまま。

### 5.2 port

最後の却下の理由（← `rolekit.rejected(place, <役の名>)` の最後の 1 件）・合わせた前の答えの控え（← `rolekit.candidate_path(place, <役の名>)`）。

### 5.3 組み立ての順（`prompts/spec-write-fix.md`・`prompts/spec-review-fix.md`・`prompts/spec-revise-fix.md`。3 本とも同じ本文）

1. `{shared:resubmit}`（拒まれた後の出し直しの段落。断片の中の `{rejection}` ← 最後の却下の理由、`{candidate}` ← 控えの絶対パス）。
2. `{shared:query-rule}`・`{shared:plain-ask}`（人に聞く文の決まり。8 節の人に聞く文の照らし）。今の md の本文は 3 本ともこの 3 行。

md の本文（3 本とも）:

```markdown
{shared:resubmit}
```

断片 `workflows/.shared/prompts/resubmit.md` の本文（英語。今の `lib/rolekit.py:419-425` の `RESUBMIT_ASK` と `FIELD_RULES`〔:435〕を 1 つにした物。仕様の 3 つの役と diagnose の再審の役が使うので、`workflows/.shared/` に置く。最初に要るのはどちらかの PR で、先に出す PR が足す）:

~~~~markdown
Your previous answer was rejected by the machine's check. In this same conversation, fix only what was rejected and return it. The material and the repository are as you already read them in this conversation (do not read them again; read only what you need to confirm the reason for the rejection).

The reason the check rejected it (verbatim):

~~~text
{rejection}
~~~

The whole previous answer, as the machine merged it: {candidate} (you can Read it; whatever you do not return stays in this form).

How to answer:

- Return JSON of the same type as before, with only the fields you fix (if you fixed only files in the repository and no field, return `{}`). A field you return replaces the previous field as a whole (for an array, return every row, including the rows you do not change); a field you do not return stays as it was.
- The machine checks the whole answer again after merging.
~~~~

（外の区切りの `~~~~` は設計書の code block の字で、断片のファイルには入れない。）

3 本を `prompts/parts/` の 1 本にしない訳: README の 7.1 の 2 は AI の node ごとに `prompts/<node-id>.md` を求める。3 本の本文は共通の断片の差し込み 1 行だけなので、写しの重さは無い。

### 5.4 返す形

1 回目の役と同じ `output_format`（2.4・3.4・4.4。#832）。人に見せる欄と言語は 1 回目の役と同じ（言語の文は会話の頭の指示に在る）。

### 5.5 描いた骨組み

例の run・筋書きのどちらにも、拒まれた後の出し直しの値は無い。今の `tests/workflows/test_judge.py::LoopTest.test_spec_resubmit_returns_only_the_rejected_fields` の値（拒否の理由「spec.write: acceptance 'A1' の … に Given/When/Then が無い」）で描くと:

~~~markdown
Your previous answer was rejected by the machine. In this same conversation, fix only what was rejected and answer again. …

The reason the machine gave (word for word):

```text
spec.write: acceptance 'A1' の test_spec.py に Given/When/Then が無い——受け入れ条件は Given/When/Then をテストの中に書く
```

The whole previous answer as the machine merged it: <place>/candidate-spec-write.json (…).

How to answer:
- Return JSON of the same type as before, with only the fields you fix (… return {}). …
- The machine checks the whole merged answer again.
~~~

### 5.6 今の指示との差

今は YAML の `prompt:` の 1 文（「前の回の返答は受け付けで拒まれた。…指示書 `$spec-reject.output.brief` を Read で全部読み…」）と、頭の node `rejects.py` が `rolekit.resubmit_brief` で書いた指示書のファイル（`resubmit-spec-write-<n>.md`。中身は `RESUBMIT_ASK`）の 2 段だった。

- 移した: 指示書の本文（`rolekit.RESUBMIT_ASK`・`FIELD_RULES`）を共通の断片に。指示はファイルを Read させずに `prompt:` で直に届ける（README の 5.2）。YAML の 1 文は要らなくなった。
- 消した: 指示書のファイル `resubmit-<名>-<n>.md`（組んだ指示は `<node-id>-prompt-<n>.md` として place に残る）。
- 英語にした。

## 6 script の node

- `intake.py`: `INPUTS_MODE`・`INPUTS_REQUEST`・`INPUTS_PR_TEXT`・`INPUTS_SPEC`・`INPUTS_USER_ENV_DIR` を `os.environ.get("INPUTS_MODE")` などの字のままで読み、`ports` に渡す。mode が `write` なら place の中のこの block のファイルを名で引いて消し（place そのものは消さない。README の 13 章）、依頼の行を `request.json` に書き（容器の形なら `findings` を取り出す。行の形の照らしは `request.schema.json`）、`intake.json` に `{mode, go, reason, pr_text}` を書く。依頼が読めない時は `go: false`・`stop.json` に `works:spec` と訳。mode が `check` なら place を消さず（check の include は自分の place を持つ）`go: true`。返り `{mode, go, reason}`。
- `write_prep.py`・`review_prep.py`・`revise_prep.py`: `INPUTS_PREV` を読み、`rolekit.resubmitting(place, <役の名>, prev)` が真なら `prompt.render("<役>-fix", {"rejection": <最後の却下>, "candidate": <控えのパス>}, {})` と `resubmit: true`、偽なら `prompt.render("<役>", values, when)` と `resubmit: false` を返す。`values` は 2.3・3.3・4.3 の差し込み口（`lang` が空なら README の 5.3 の既定の英文）。`when` は `{"rejected": <却下の控えが空でない>, "pr_text": <intake.json の pr_text が空でない>}`。query-rule の断片の `spawns` は `False`。今の `rejects.py` の `lang_line`・`reason`・`brief` の欄は無くなる。
- `take.py`: 今の `spec_accept.py` と同じ。`INPUTS_ROLE`・`INPUTS_STATUS_GUARDED`・`INPUTS_REPLY`・`INPUTS_FIX_REPLY` を読み、`rolekit.resubmitted(place, ROLES[role], reply, fix_reply, rolekit.merge_fields)` で合わせ、`rolekit.accept_parsed(place, ROLES[role], got, lambda r: src.take.take(place, role, r, <作業ツリー>, keys=accept.status_keys(<status_guarded>)))`。返り `{ok, done, reason, revise}`。
- `ask.py`: `src.gate.ask(place, <作業ツリー>, ports.run_id())`。中の誤りは `stop.json` に `works:spec` と「仕様の承認ノードの文を組めない（<型>: <文>）」を書き、`{ask: false, message: ""}`（今の `spec_ask.py` のまま）。
- `freeze.py`: `INPUTS_USER_ENV_DIR` が空なら place の絶対パスを、空でなければその値を、印の置き場にする（今の `boundary.aim_user_env` の替わりの `ports` の口。口の名は土台の PR に合わせる）。`src.gate.answer(place, <作業ツリー>, ports.json_or_none(INPUTS_ANSWER))`。中の誤りは `stop.json` に `works:spec` と「仕様を固められない（<型>: <文>）」。返り `{go, reason}`。今の `spec_answer` の最後の `snap_tree(jdir, TREE_FILE, root)` は消す（写しは読むだけの役を持つ各 block が自分で取る。parallel-pr の設計書の 10 節の 3）。
- `check.py`: `INPUTS_SPEC` が空なら `{questions: [<仕様が渡されていない問い>], unchecked: true}`。空でなければ `src.check.questions(<pointer の先>, <作業ツリー>)`。中の誤りは「照らしが落ちた——…（<訳>）」の問い 1 行と `unchecked: true`（今の line の `fallback`。止めの理由は line が決める）。
- `finish.py`: `intake.json`・`stop.json`・`spec.json`・`added-rows.json`・`spec-check` の返り（`with: {checked: {from: "$spec-check.output", if_skipped: null}}`）から 1.2 の出力を組む。write の決め:
  - `stop.json` の `stop_reason` が `human:` で始まるか `request:` で始まる: `status: stopped`。
  - `stop.json` が在る（ほかの語）か、`spec.json` が無い: `status: failed`・`stop_reason: works:spec`（控えが無い時の `reason` は「仕様の段が最後まで回らなかった」）。
  - `spec.json` が在る: `status: approved`。
  - pointer は在るファイルだけ（`spec`・`added_rows`）。今の「止めの道でも空の形の指しを置く」（J90）は、出力が null を明示する形で替わる（読み手は null を読む）。

## 7 元の works と graphloops の同じ場面

元の works の `works/blk-spec/`（3 つの loop・spec-ask・spec-gate・spec-answer・collect）と、その指示の元の graphloops の `prompts/review-loop/spec.write.md`・`spec.review.md`・`spec.revise.md`（`graphs/review-loop.json:5718-6117`・`rules/review-loop.py:4531-4750`）から、工場は書く・審査・直す・人の承認・固めるの 5 つを全部持つ。工場に無い物・違う物と、その訳:

1. 同じ run の中での承認し直し（graphloops の `spec.check` は修正の後の周ごとに sha256 を照らし、承認ノードで continue と答えれば新しい sha256 で固め直し、`process.spec.amendments` に積んだ）: 工場は問うだけで、run を人待ちで終え、承認し直すのは次の run の仕様の段（#510 `79f1fbc2`・#542 `2e593f13`。graphloops の engine が共有の記録〔盤面〕を問いの答えまで止めた形に替えて、差分の審査・最後の試験・独立の目を回し続け、最後の承認ノード・報告・次の依頼の下書きで問う。#554 `425abeda` で「照らせなかった」を分けた）。元の works にも無い。この block の check も問うだけ。
2. 書く役が名乗らずに変えたファイルの照らし（graphloops 0.22.0 `d1f043f2` の `declared_files: acceptance[].file` と `declared-files.md`。テスト以外を書いたら両側に記録して次の周の判定に渡す）: 元の works（a1202d0 の写し）にも工場にも無い。書く役・直す役の受け付けは作業ツリーを比べず、「テストのファイルだけ」は指示の文だけが言う（`spec.md:49`）。（未確認）: 工場は初めから持たない。この block も足さない（足すかは振る舞いの変更で、この作り直しの外）。
3. 受け入れ条件の `run` の 600 秒の期限（graphloops の `SPEC_RUN_TIMEOUT`）: 工場は期限を置かない（持ち主の決め `no-timeouts`。`docs/plans/2026-10-13-capabilities/judge.md:625`、#76 `37b7a693` の写しから）。この block も置かない。
4. 書く役・審査役・直す役が PR の題と本文を読む（元の works と graphloops は `{{inputs.request}}`、`entryshape.request_text` で PR の文を含む）: 工場の指示は依頼の行 `judge/request.json` だけを読む。PR の題と本文だけで仕様の段を選んだ run（`start.py:257` が受ける）では依頼の行が空で、PR の文は役に届かない（目的と判定の役には `pr_file_text` で届く）。（未確認）: #76 から在り、#529 `cce03fcf` は spec=on に依頼の行か PR の文を求めたが、役への配線はしていない。この block は port `pr_text` で戻す（2.6・11 節の 2）。
5. 止め札の確かめ（元の works の route と ask の `halt.seen`）: 工場は外した（持ち主の決め `stop-at-gates`・`report-on-stop`、#76 と `de3cfa7e`）。承認ノードの一言の頭 `request:` だけが残る。この block も同じ。
6. 元の works の collect の出口の欄（`tests[{file, sha}]`・`approved_by`・`approval_note`・`frozen_rev`・数の 4 つ）: 工場は `spec` の pointer だけ（読む物が無いので `_head` を消した。`de3cfa7e`、#76）。この block も同じ（中身は `spec.json` に在る）。
7. 拒まれた後の出し直し（元の works は `fresh_context: true` で新しい会話、最後の拒否 1 件だけ）: 工場は同じ会話の続きで拒まれた欄だけを返させ、受け付けが合わせる（#571 `b46ec691`・`ae823997`・`a14d3c4e`、#588 `3a2bf3f7`）。1 回目の役の再び起きる時には拒否を全部渡す（#345・#351 `a873a13a`・`f3b8b2e0`）。この block も同じ（5 節）。
8. 承認ノードの形（元の works は `approval:`）: 工場は `wait:`（attention・select・選び肢 4 つ。#637 `a6864142`、Archon の版上げ）。この block も同じ。
9. 審査役の前の作業ツリーの写しを取る時（元の works は審査役の prep の直前）: 工場は書く役の受け付けが通った時（間に何も走らないので同じ。#76）。この block も同じ。
10. block の筋書き（元の works の諦め・穴なし・承認ノードで止める）: 工場は単体の試験（`SpecGateCase`・`SpecTakeCase`・`SpecFreezeTest`）に移し、筋書きは `spec-on.stubs.yaml` と line の `spec-changed.stubs.yaml` だけ（（未確認）: 意図の記録なし、#76）。この block は standalone の筋書きを 4 本置く（10 節）。

この block が両方より良く、残す物: 承認したテストが変わったかを照らして run を止めずに最後の承認ノード・報告・次の依頼の下書き・`bin/apply` の注まで届ける（#554。「照らせなかった」を分ける・仕様の指しが無い時も問う）・固めた仕様を修正案に渡して受け入れテストを項目の `tests` に入れる（#75 `e730d351`）・仕様を選んだ run は頭の深さを標準にする（#517。head-depth の block の port `spec`）・受け入れ条件のコマンドを利用者の HOME・XDG に戻し、印を残し、`tree_run.outside_env` で走らせる（#512）・承認の後の作業ツリーの写しの取り直し（#275。この block では各 block が自分で取る形に替わる）・どの止めの道も出力を埋める（J90）・承認ノードに出す文を組む段（`ask.py`）と仕様を固める段（`freeze.py`）の中で誤りが出た時、node を落とさず `stop.json` に `works:spec` の止めを書く・モデルの群を起動の時に付け替えられる。

graphloops と元の works の仕様の段は、`p0.base` と `p0.local_checks`（直す前の CI の結末）の後に回す（赤いテストが基準を汚さないため）。工場も test-gate の base の後に judge を回す（`works-factory-line.yaml:175`）。この順は line が持ち続ける（1.6）。

## 8 受け付け

- 書く役（`role: write`）: 今の `_spec_errors` のまま（鍵が一意・受け入れ条件が要件を指す・要件は受け入れ条件を 1 件以上持つ・テストのファイルが読めてその名と Given・When・Then を含む）。通ったら審査役の前の作業ツリーの写しを `spec-snapshot-spec.review.json` に置く。
- 審査役（`role: review`）: 写しと今の作業ツリーを `accept.tree_moved`（`status_guarded: true` なので `accept.BEYOND_STATUS` の欄。書く役が書いたテストの未コミットの状態は比べない）で比べ、変わっていれば「読むだけの役が作業ツリーを変えた: …」で拒む。`faces` の鍵が一意・穴が無いなら `faces_none` が 20 字以上。通ったら `revise` は穴が 1 件以上か。
- 直す役（`role: revise`）: 審査の穴の鍵に 1 度ずつ答える（審査に無い鍵・答えの無い鍵を拒む）・直した仕様に `_spec_errors`。
- 人に聞く文の照らし（3 つの役とも）: 承認ノードの項目に字のまま載る欄（書く役と直す役の `requirements[].text`・審査役の `faces[].why`・直す役の `handled[].how`。`gate.approve` が並べる）が run の中を指す参照（`<パス>:<行>`・`<名>[<番号>]`。`lib/plainask.py`）を持てば拒む。指示は 3 つの役と出し直しの役が共通の断片 `{shared:plain-ask}` を段落の外で入れる（計画は `docs/plans/2026-10-29-plain-asks.md`）。
- どの役も: 返答が JSON のオブジェクトでない・形が違う（`KeyError`・`TypeError` など）時も、投げずに拒否として返す（`<節の名>: 返答の形が違う（<型>: <文>）`）。却下の理由の文の頭は `NODES` の名（`spec.write` など。今の字）。日本語のまま（README の 5.3）。
- 出し直しの役の返答は、`rolekit.resubmitted` で前の答えの控えと欄ごとに合わせてから同じ照らしに通す（空の出し直しは前の答えのまま）。
- 3 回目の却下で loop を抜ける（`rolekit.GIVE_UP_AFTER`）。`spec-ask` が `rolekit.given_up_reason` を見て、承認ノードを開かずに `stop.json` に `works:spec` と諦めの文を書き、`finish` が `status: failed` を返す。
- 承認ノードの答え（`spec-freeze`）: 開かなかった（null）→ `stop.json` が無ければ `works:spec`「仕様の承認ノードが開かなかった（仕様が固まっていない）」。止める語（`stop`・`reject`）→ 一言が `request:` で始まれば `request:spec-gate`、ほかは `human:spec-gate`（一言が空なら「承認ノードで止めた」）。通す語（`approve`・`continue`）→ `spec-ask.json` の仕様を固める（もう `spec.json` が在れば 2 度固めない）。知らない語・形の誤り → `works:spec`。

## 9 報告の行（`src/report.py`）

- write の `approved`: `仕様: 要件 <n> 件・受け入れ条件 <m> 件を人が承認した（<一言が在れば「一言: …」>）` と、受け入れ条件ごとに `- <key>（要件 <requirement>）: <file> の <name>——承認の時 <exit 0 なら「既に緑（赤を見ていない）」、走らなければ「走らない（<run_error>）」、ほかは「exit <n>」>`。
- `stopped`: `仕様: 人が承認ノードで止めた: <一言>`。`failed`: `仕様: 固まらなかった（<reason>）`。
- check: 問いが在れば `承認し直すかの問い <k> 件`（`unchecked` なら `受け入れ条件のテストが変わったかを照らせなかった`）と問いの行。無ければ `承認した受け入れ条件のテストは承認の版のまま`。
- 今の報告は `spec` の pointer を「仕様」の行で並べるだけ（`lib/runreport.py:182`）。上の行は事実を持つ block が組む形（README の 4.1）にした物で、中身は承認ノードの文と `spec.json` に今も在る事。

## 10 単独で呼ぶ・試験

### 10.1 単独で呼ぶ

```sh
bin/works-factory workflow run works-factory-spec \
  --cwd <対象> --input request='[{"where":"README","text":"…直したい事…"}]'
```

- 承認ノード: run は `spec-gate` で止まり、承認ノードの文（`spec-ask` の `message`。末尾に答え方の行）を出す。人は `bin/works-factory workflow respond <run> approve|stop [一言] --cwd <対象>` で答える（根の README の答え方と同じ。`<run>` はこの単独の run の id）。答えると `spec-freeze` から続く。止めれば `status: stopped` を返して run は `completed`。
- 照らす: `--input mode=check --input spec=<固めた spec.json のパスか pointer>`。承認ノードは開かない。
- 始めの記録は要らない。殻の引数の名は（未確認）（world の 7 節と同じ）。

### 10.2 試験

- standalone の fixture（`workflows/spec/fixtures/`。どれも入力は port の値だけで、始めの記録を持たない）:
  - `standalone.stubs.yaml`: 入力は `request`（JSON の字 1 行）だけ。今の `spec-on.stubs.yaml` の仕様の部分を写し、承認ノード `spec-gate` を `{decision: approve, text: ''}` で差し替える（今の筋書きと同じ。`archon workflow test` は `wait:` の node も台本で答える）。`reached: [spec-write-accept, spec-review-accept, spec-revise-accept, spec-ask, spec-gate, spec-freeze, finish]`。
  - `gate-stop.stubs.yaml`: `spec-gate` を `{decision: stop, text: 範囲が違う}`、`finish` の返りの `status` が `stopped`、run は `completed`。
  - `gave-up.stubs.yaml`: `spec-write-accept` が 3 回拒み、`spec-ask` が `{ask: false, message: ''}`、`spec-gate` が飛ぶ、`finish` が `status: failed`。
  - `check.stubs.yaml`: 入力 `mode: check`・`spec` は fixture の中のファイルのパス（pointer の値は持たない。README の 7.1 の 4）。`reached: [intake, spec-check, finish]`。
- `tests/blocks/spec/test_spec.py`: script を子のプロセスで回す。始めの記録の無い使い捨ての `ARTIFACTS_DIR` と git のリポジトリで、port の値だけを渡し、`intake` → `write_prep` → 台本の返答（テストのファイルも試験が書く）→ `take`（write）→ `review_prep` → 台本 → `take`（review）→ `revise_prep` → 台本 → `take`（revise）→ `ask` → 答えの値 → `freeze` → `finish` と回し、`spec.json` の sha256・`exit_at_approval`、`added-rows.json` の行の頭が `PROVENANCE`、`report` の行を照らす。check は `spec.json` を作ってテストのファイルを変え、`check` → `finish` の `questions` を照らす。
- 指示の比べ（README の 11.4）: 1 つ目の commit では、6 本の md を今の指示の日本語の字のまま（今の md の頭の言語の 1 行と、却下が無い時の「下の理由が空なら…」の段落を含む）置き、今の `spec.md`・`spec-review.md`・`spec-revise.md` の Archon の置き換え（`$spec-reject.output.reason` を空・`lang_line` を `rolekit.LANG_RULE` に既定の言語を入れた字・`$ARTIFACTS_DIR` を place の親）と同じ字になることを照らす。出し直しの md は、今の `rolekit.write_resubmit` が書く指示書と同じ字を照らす。2 つ目の commit（英語）では、2.6・3.6・4.6・5.6 の差の一覧どおりかを並べて審査に出す。
- 振る舞いの試験（今の試験から写す。`judge/` のパスを place に替える）:
  - `lib/tests/test_judge_accept.py` の `SpecErrorsCase`（`test_acceptance_without_gwt_rejected`・`test_missing_test_file_and_name_rejected`・`test_keys_unique_and_point_to_requirements`・`test_review_needs_faces_none`・`test_revise_answers_each_face_once`・`test_revise_due_only_with_faces`）・`SpecTakeCase`（`test_review_is_read_only`・`test_review_without_faces_skips_revise`・`test_bad_shape_is_a_reject_not_a_crash`・`test_revise_replaces_the_spec`）・`SpecGateCase`（`test_ask_message`・`test_ask_without_faces_has_no_face_lines`・`test_ask_after_give_up_stops`・`test_freeze_records_sha_and_exit`・`test_gate_stop_words`・`test_gate_skipped`・`test_gate_unknown_word`）・`SpecCheckCase`（`test_changed_acceptance_file_is_a_question`・`test_unchanged_is_no_question`・`test_deleted_file_says_gone`・`test_unmeasurable_file_says_why_not_gone`・`test_same_file_counted_once`・`test_unreadable_spec_is_a_question_not_silence`）・`SpecblkCase`（`test_gate_text_answer_lines`・`test_gate_text_subjects_are_plain_and_quote_the_question`・`test_parse_gate`）。
  - `tests/workflows/test_judge.py` の `GateTest`（`test_spec_gate_is_an_approval_with_the_four_words`・`test_spec_freeze_may_change_the_checkout`）・`LoopTest` の仕様の分（`test_third_fresh_spec_role_reads_every_reject_of_the_loop`・`test_spec_resubmit_returns_only_the_rejected_fields`・`test_spec_resubmit_after_fixing_only_the_file_returns_nothing`）・`SpecFreezeTest`（`test_stop_word_is_a_human_stop`・`test_request_flag_is_a_request_stop`・`test_approval_freezes_hashes_and_exit_codes`・`test_approval_in_users_env_leaves_the_marker`〔`user_env_dir` が空の時に place に印が置かれる場合を足す〕・`test_spec_stop_still_fills_pointers`〔出力が null を明示する形に〕）。
  - 足す: `pr_text` が在れば 3 つの役の指示に PR の節が入り、無ければ入らない。`mode: check` で `spec` が空なら「渡されていない」の問いと `unchecked: true`。
  - 写さない: `test_roles_after_approval_take_the_spec_tests_as_given`（判定の写しの取り直しを見る。写しは各 block が取る）。`lib/tests/test_judge_accept.py:877` の `test_features_cut_and_spec_set_the_stage_flags` の仕様の部分（段の切り替えは line）。
- 読み手の側の試験はそれぞれの block と line に残す: diagnose の受け入れ条件のバッチ（`request_batches` の写し）・plan の `SPEC_HEAD`・line の `spec-changed.stubs.yaml`・report の `answer_drafts`・`bin/apply` の注（`tests/bin/`）。
- keep-essence の 12 の仕組みのうち、この block が担う物は無い（README の 10 節の割り当てに仕様は無い）。受け入れテストは後で TDD の赤いテストとして使われうる（keep-essence の 1「赤緑の機械の判定」の材料）が、判じるのは fix。この block が守るのは、承認の時の終了コード `exit_at_approval` と sha256 を `spec.json` に残す形（`test_approval_freezes_hashes_and_exit_codes`）。e2e の `tests/e2e/evidence.json` の J92 と L-E27 は、node の id と place のパスを新しい物に合わせる。

## 11 自分で決めた事

1. line の `spec-check` を、この block の `mode: check` に入れた（README の 8.1 は入力 `request` と出力 `spec`・`added_rows` だけ）。根拠: 照らしは `spec.json` の形（`acceptance[].file`・`sha256`）を知る計算で、README の 2 の憲法の 1 と 1.3 の形の直し 7（観点の計算は graph に置かない）から line の `src/` には置けない。読み手を作り手の block の中に置けば、仕様の形の知る場所は 1 つで済む（structure の before|after・test-gate の base|final と同じ形）。
2. port `pr_text` を足した。根拠: 元の works と graphloops の役は PR の題と本文を読み、工場で記録なく落ちた（7 節の 4）。PR の文だけで仕様の段を選べる入口が今も在るので、無いと役が空の依頼で書く。
3. port `user_env_dir` を残し、空なら place に印を置く。根拠: 受け入れ条件のコマンドを利用者の環境で走らせる仕組み（#512）は、起動の殻を通った run では印の置き場が無いと `userenv.restore` が止まる。単独の run では line の置き場が無いので、block の place が置き場になる。
4. 足した行の出どころの名を出力の欄 `added_origin` で渡す。根拠: 今は diagnose が `SPEC_PROVENANCE` の字の頭で行を分けていて、2 つの block が同じ字を持つ。名を値で渡せば、読み手は作り手の字を持たずに済む（README の 4.1 の「行の形は作り手ごとに lib の 1 モジュール」を、字 1 つのために作らずに済ませる）。行の本文の頭の `PROVENANCE` は、判定の役が読む材料として今のまま残す。
5. 出力に `status`・`stop_reason`・`reason`・`questions`・`unchecked`・`added_origin` を足した。根拠: 今、仕様の段の止めは run を止め（`human:spec-gate` など）、check の問いは最後の承認ノードと報告と `bin/apply` に届く。どれも無いと元の能力が落ちる。止めるかは line が決め、block は語を返す。
6. 承認ノードの文の組み立て `gatemarks.gate_text` は `lib/` に残る物として使う。根拠: line の修正前の承認ノードと仕様の承認ノードの 2 つが使う（`lib/gatemarks.py:366` の docstring）。README の 9.2 は `gatemarks` の承認ノードの決めの部分を line の `src/` へ移すと書くが、`gate_text` は決めでなく文の組み立てで、2 つの使い手を持つ。
7. 出し直しの段落を共通の断片 `resubmit` にした。根拠: 仕様の 3 つの役と diagnose の再審の役（今の `rejudge-loop` の `rejudge-fix`）が同じ `RESUBMIT_ASK` を使う。README の 5.1 の決め（2 つ以上の block が使う段落は `workflows/.shared/prompts/`）。
8. 審査役の指示に `{shared:role-judge}` と `{shared:query-rule}` を並べた。根拠: 今の審査役の指示は `lib/agents/judge.md` の本文を写していて、その中に外への検索の決まりの塊が在る（world の query-rule の元 `lib/agents/judge.md:16-22`）。役の定義の断片に検索の決まりを持たせると 2 か所目の写しになる。断片の名 `role-judge` は、土台の PR が役の定義 5 本に付ける名に合わせる（`role-<役>` を仮の名にした）。

## 12 実装で決めた事（実装の役が書く。設計書と main の決まりが食い違った所・設計書が黙っていた所）

1. 入口が write の回の頭で消すのは、この block が名で持つファイルだけ（`src/files.py` の `own_files()`・`own_prompts()`）。今の judge の入口は place を作り直して中を全部消していたが、「block が消してよいのは自分が名を持つファイルだけ」（`workflows/.shared/AGENTS.md`）に合わせて替えた。ほかの物の名のファイルは残る。消すのは mode が write と分かった直後（依頼を読む前）で、依頼が読めなくても前の回のファイルは残らない。
2. 依頼の行の形は `shared:request.schema.json` を使い、block に写しを置かない（1.5 の「`workflows/spec/schemas/request.schema.json`（world と同じ形の写し）」を取り下げ）。形のファイルの名は pack の中で 1 か所にしか置けない（`tests/layers/test_block_shape.py` の 5）。
3. 出し直しの指示を組む node `spec-<役>-fix-prep` を役ごとに足した（script は 3 つで 1 本 `fix_prep.py`。`with: {role}`）。`spec-<役>-prep` は出し直すかと 1 回目の指示だけを返す（出し直しの時の `prompt` は空）。訳: 筋書きは輪を 1 周しか回さない（`until_bash` を仮定で満たす）ので、出し直しの役は 1 周目に届かない。出し直すかを決める prep の返りだけを筋書きで差し替え、出し直しの指示を組む prep は差し替えずに本物を回せば、出し直しの役の md を筋書きが照らせる（`check_standalone_renders` は、AI の node の prep を差し替えた筋書きを証にしない）。筋書きは `resubmit-write`・`resubmit-review`・`resubmit-revise` の 3 本を足した。
4. script は prep を 1 本 `prep.py`（`with: {role, prev}`）、受け付けを 1 本 `take.py` にした（設計書は prep 3 本）。違いは `role` だけで、`with:` に結ぶ入力が node ごとに揃う。
5. 承認ノードの文に入れる run の id は `ports.run_id()` でなく `ports.pointer(<place のファイル>, <form>)["run_id"]` で引く（`ports.py` にその口は無い。土台の `ports.py` は変えない）。
6. 筋書きの `reached` に AI の node を足した（`check_standalone_renders` は reached に在る AI の node を証にする）。受け入れ条件のテストのファイルは、筋書きの作業ツリーに在る筋書き自身（Given / When / Then の 3 語と、テストの名を中に持つ）にした。check の筋書きの仕様は `fixtures/approved-spec.json`（受け入れ条件のテストは作業ツリーの `README.md`）。
7. 出力: `stopped` で `stop_reason` が `human:spec-gate` か `request:spec-gate`、`failed` で `works:spec`。check の `ok` は `status` が `checked` の時だけ真（照らせなかった `unchecked` は偽）。照らしの node が返りを返さなかった時は、照らせなかった（問い 1 行・`unchecked`）として返す。
8. 入口が `mode` を読めない時は `mode` を空にして `go` 偽・`failed`（`works:spec`）で返す。write の止めの控え `stop.json` は、入口が読めなかった時にも書く。
9. `answer`（承認ノードの答え）が通す語で、`spec-ask.json` が無い時は、`stop.json` に `works:spec` と「`spec-ask.json` が無い・形が違う」を書く（今の `spec_answer` のまま。承認ノードが開かなかった時は null で別の道）。
10. 審査役の md は `{shared:role-judge}` の次に `{shared:query-rule}` を並べず、`{shared:role-judge}` だけにした（3.3 の本文から `{shared:query-rule}` の行を除いた）。訳: main の `workflows/.shared/prompts/role-judge.md` は末尾に `{shared:query-rule}` を持つので、並べると検索の決まりが 2 度入る（11 節の 8 は「役の定義の断片は検索の決まりを持たない」としていたが、main の断片は持つ）。段落 `spawns` の真偽は審査役の md でも `when` に渡す（断片の中の段落）。
11. 共通の断片 `workflows/.shared/prompts/resubmit.md` を足した（5.3 の本文。2 つ目の commit。口の名は `{rejection}`・`{candidate}`、`{}` は `` `{}` `` の字で書く。diagnose の再審の役と同じ断片）。`workflows/.shared/AGENTS.md` の取り置いた名の一覧から `resubmit` を今在る名に移した。出し直しの 3 本の md は `{shared:resubmit}` の 1 行。
12. `tests/layers` の E7 の表 `CHANGE_CHECKOUT` に行 `("spec", "spec-freeze")` を足し、表の行が指す node を探す `tests/layers/test_readonly_nodes.py` の試験が `workflows/<block>/` も探すようにした（`mutates_checkout: false` を書くと、受け入れ条件のコマンドが作業ツリーに書いた時に Archon が node を落とす。1.3 の「`mutates_checkout:` は書かない」と、main の E7 の「script の node は false か表の行」の食い違いを、表に行を足して解いた）。
