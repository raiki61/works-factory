# block の設計書: premises（前提の実測）

- 何の話か: 依頼に書かれた数値・規模・件数・在る/無いの主張を、AI の役に作業ツリーで測り直させ、制約の一覧にする観点を、単独で呼べる block `blocks/premises/` にする設計。型は [README.md](README.md) に、形は手本の [world.md](world.md) に従う。
- 決めたこと: 今の judge の 3 つの node（premises-reject・premises・premises-accept）と、judge の入口が代わりに持っていた支度（依頼の行の控え・作業ツリーの写し・前の run が運んだ実測の控え）を、6 つの node の block にする。入力は依頼の行・前の run が運んだ実測・言語の 3 つの port だけで、始めの記録と止めの記録を読まない。指示は英語の md 1 本（`prompts/premises.md`）にまとめ、`$ARTIFACTS_DIR/judge/request.json` を Read させる形をやめて、依頼の行を指示の中に入れる。報告の行（依頼の実測を測り直せなかった行）はこの block が組む。振る舞いは変えない。
- 持ち主に求めること: なし。読み手は、この block を作る実装の役（この文書だけで作れる細かさにした）と、その PR の審査。

この文書の語は README の頭の物を使う。ほかに:

- 持ち主: このリポジトリの owner（決めを下す人）。「持ち主の決め `<名>`」は `docs/owner-decisions.md` の決めの名。
- line: 工場（works-factory。この repo の Archon の workflow 群）のメイングラフ。始めの記録（run の起動の時の入力の記録）を書き、block に port の値を配る。judge のまとめ（`blocks/judge/`）は判定の block を `include:` で並べる graph で、line がそれを include する。
- 土台の PR: README の 11.1 の 0 の PR（`blocks/.shared/ports.py`・`prompt.py`・共通の指示の断片 `rejected.md`・`query-rule.md`・起動の殻の口を置く）。この block の PR より先に入る。この文書が「土台に合わせる」と書く名は、そこで決まる。
- 源と bun: 試験が Archon を起こすのに要る、止めた版の Archon のソース（`bin/_lib/place.archon_source` が取る）と JavaScript の実行環境 bun。無い手元では、その試験を名前つきで見送る（`tests/AGENTS.md`）。
- keep-essence: 元の works が守る 12 の仕組み（README の 10 節）。9 は「独立設計と R1〜R4」で、R1〜R4 は修正の後に別の目が見る 4 つの確かめ（R1 最小性・R2 独立設計との比べ・R3 全体の整合・R4 見えていない範囲）。12 は「世界の解に照らす」。
- 1 つ目の commit・2 つ目の commit: この block の PR の中の 2 つの commit（README の 11.4）。1 つ目は指示の md を日本語のまま置いて今の指示と同じ字かを試験で照らし、2 つ目で英語にする。2.3 の md の本文は 2 つ目の物。
- 実測役（premises）: 依頼の主張を作業ツリーでコマンドを走らせて測り、制約の行 `{text, measured_how, kind, measured_output?}` を返す AI の役。道具は Read・Grep・Glob・Bash・WebSearch・WebFetch。Bash は sandbox の中。
- 制約の行の `kind`: `実測`（コマンドと出力を示せる）か `仮説`（示せない）の 2 語。
- 依頼の実測: 依頼の行の `measured` の欄（依頼者が「測った」と書いた値）。この行の `where` を字のまま `text` に含む制約が要る。
- 運ばれた実測: 前の run の報告が次の依頼に書いた制約の行（`lib/carry.py` の `carried_constraints`。今の `judge/carried-constraints.json`）。受け付けを通った返答に足して返す。
- 作業ツリーの写し: 役を起こす前の作業ツリーの姿（`lib/accept.py` の `tree_state`。HEAD・枝・git が無視するファイルも見る）。受け付けが今の姿と比べ、変わっていれば拒む。
- 例の run: 本物の run `df5e111f-ea97-409b-8066-2245d32746ab`（対象 raiki61/works-factory。置き場 `~/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/artifacts/runs/df5e111f-…/judge/`）。`request.json`・`premises.json`・`carried-constraints.json` から骨組みの値を取った。この run は 1 回目で通り、拒みの控え `rejects-premises.json` は無い。

## 1 block の全体

### 1.1 役

依頼の各行から数値・規模・件数・在る/無い・「〜が来うる」の類の主張を拾い、この作業ツリーで測った値かファイルを名指しできる事実にして、制約の一覧を返す。依頼者の `measured` は信じずに測り直させる。`kind: 実測` には走らせたコマンドと出力を必ず付けさせ、示せない物は `仮説` に落とさせる。役が作業ツリーや履歴を変えていないかを機械が写しと比べる。前の run が運んだ実測を返答に足して返す。

### 1.2 port

入力（YAML の `inputs:`）:

- `request`（必須）: `json(request.schema.json): 依頼の行の配列 [{where, text, mechanism?, measured?, false_positive_if?}]。それを findings の欄に持つオブジェクトでもよい（工場の依頼のファイルの形）。空の配列は依頼の行の無い run（測る主張は無い）`
- `carried`: `json(constraints.schema.json): 前の run が運んだ前提の実測の行の配列 [{text, measured_how, kind, measured_output?}]。空の配列は運ばれていない。空で request が容器の形なら、容器の constraints の欄を使う`。既定 `[]`。
- `lang`: `text: 人に見せる欄（text・measured_how）の言語。空は依頼の行の言語`。既定 `""`。

出力（`returns: finish`、`outcome_field: ok`）:

- `ok`: boolean。`status` が `ok` か。
- `status`: `ok` か `failed`。`failed` は、依頼が読めない・作業ツリーの写しが取れない・役が 3 回拒まれた・役が走らなかった時。
- `reason`: 日本語の 1 行（人に見せる）。`failed` の訳。`ok` の時は空の字。
- `constraints`: pointer（place の `premises.json`。中身は `{"constraints": [...]}` で、受けた返答の制約に運ばれた実測を足した物）か null（`failed` の時）。
- `measured`・`hypotheses`: `premises.json` の制約のうち `kind` が `実測`・`仮説` の行の数（`failed` の時は 0）。
- `report`: 報告の行の配列。依頼が `measured` を持っていたのに制約が `仮説` でしか書けなかった行ごとに `依頼の実測を測り直せなかった（前提は仮説）: <where>——<制約の text>`。`failed` の時は `前提の制約: <reason>` の 1 行。どちらも無ければ `[]`。

今との違い: 今は依頼の行を judge の入口が `judge/request.json` に置き（`lib/judge_accept.py:3832-3868` の `intake`）、作業ツリーの写しも入口が `judge/judge-tree.json` に取り、運ばれた実測も入口が `judge/carried-constraints.json` に置いていた。役は `$ARTIFACTS_DIR/judge/request.json` を Read し（`workflows/judge/commands/premises.md:38`）、受け付けは `judge/premises.json` に書き、諦めた時は止めの記録 `judge/stop.json`（`stopby.PREMISES`）を置いた（`workflows/judge/scripts/premises_accept.py:21-24`）。出口は judge の返す節の欄 `premises`（pointer）で、報告の行は `lib/runreport.py:1026-1046` の `premise_lines` が依頼のファイルと控えを読み直して組んでいた。この block は、支度を自分で持ち、止めの記録の代わりに `status` を返し、報告の行を自分で組む。`measured`・`hypotheses` の数は、元の works の出口が持っていた数（2.7）のうち、読み手が使える 2 つを戻した物（8 節の自分で決めた 4）。

### 1.3 node の並び（`blocks/premises/works-factory-premises.yaml`）

1. `intake`（script `intake.py`。`mutates_checkout: false`）: port を読み、place の中のこの block のファイルを名で引いて消し（place そのものは消さない。README の 13 章）、依頼の行と運ばれた実測を `intake.json` に書き、作業ツリーの写しを `tree.json` に取る。返り `{due, reason}`。
2. `premises-loop`（`loop_group`、`max_iterations: 3`、`fresh_context: false`、`until_bash: done=$premises-accept.output.done; test "$done" = true`。`depends_on: [intake]`・`when: $intake.output.due == true`）
   - `premises-prep`（script `measure_prep.py`。`mutates_checkout: false`。前の回までの却下は `with:` で受けず place の拒みの控えから読む）: 指示を組む。返り `{prompt}`。
   - `premises`（AI。`depends_on: [premises-prep]`・`prompt: "$premises-prep.output.prompt"`・`model: '@wf-judge-materials'`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob, Bash, WebSearch, WebFetch]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false, filesystem: {denyWrite: ['~/../archon-home']}}`・`idle_timeout: 1728000000`・`mutates_checkout` は書かない（Bash を持つ役に `mutates_checkout: false` を書くと機械の検査 E7 が拒む。今の node も書いていない。受け付けが全欄の写しと比べる）・`retry: {max_attempts: 2, on_error: all}`。`output_format` は今のまま。2.4）
   - `premises-accept`（script `measure_accept.py`。`depends_on: [premises]`・`mutates_checkout: false`・`with: {reply: $premises.output}`）: 返り `{ok, done, reason}`。
3. `finish`（script `finish.py`。`depends_on: [intake, premises-loop]`・`trigger_rule: all_done`・`mutates_checkout: false`）: 出力を返す。どの段が落ちても落ちない。

どの script の node も `runtime: uv`。今の `premises-reject`（`reject.py`）は無くす（理由は prep が place の拒みの控え `rejects-premises.json` から読み、言語は port `lang` で受ける）。sandbox の `denyWrite` は今の値のまま（`workflows/judge/works-factory-judge.yaml:586-591`。役の claude を起こす直前に、Archon に無い物を補う部品（埋め）`fence.py` がこの `denyWrite` の値を「書き込みを塞ぐ役」の目印として読み、塞ぐ先に cwd・共通の `.git`・worktree の根を足す。#293・#309）。

script の名は `lib/` のモジュールの名と重ねない（README の 7.1 の 9）。`premises.py`・`accept.py`・`measure.py` は lib と重なるので、`measure_prep.py`・`measure_accept.py` にした。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、line から judge のまとめを通して include された時は `$ARTIFACTS_DIR/judge/premises/`）の下に書く。名は `src/steps.py` だけが持つ。

- `intake.json`: `{findings, carried, lang, failed, reason}`。intake が消してよいのは、自分が名を持つこの節のファイルだけ（`intake.json`・`tree.json`・`premises.json`・`rejects-premises.json`・`premises-prompt-*.md`）。`findings` は依頼の行の配列、`carried` は運ばれた実測の行の配列。`failed` は intake が落ちた時だけ true で、`reason` はその訳（ほかは空の字）。
- `tree.json`: 作業ツリーの写し（`accept.tree_state` の形）。今の `judge/judge-tree.json` に当たる。
- `premises-prompt-<n>.md`: 組んだ指示。
- `rejects-premises.json`: 拒みの控え（`rolekit.accept_round` が書く。今と同じ名）。
- `premises.json`: 受けた返答に運ばれた実測を足した物（今と同じ名・同じ形）。

### 1.5 コードの置き場

- `blocks/premises/src/__init__.py`: 空。
- `blocks/premises/src/steps.py`: 今の `lib/judge_accept.py` の `check_claims`（:1163-1168）・`measured_needs_output`（:1171-1182）・`PREMISES_RULE`（:1184）・`with_carried`（:1187-1192）・`check_premises`（:1195-1215）と、作業ツリーの比べ `_tree_snapshot`・`_moved_since`・`_tree_unchanged`（:1121-1160）の写し、今の `lib/premises.py` の `claims`（:25-29）の写し。place のファイルの名（`INTAKE_FILE`・`TREE_FILE = "tree.json"`・`PREMISES_FILE = "premises.json"`・`ROLE = "premises"`）と、`kind` の語 `MEASURED = "実測"`・`HYPOTHESIS = "仮説"` もここだけが持つ。`_tree_unchanged` は写しが在る道だけを残す（写しは `intake` が必ず取る。無ければ今と同じく「作業ツリーの写し … が無い」で拒む）。
- `blocks/premises/src/report.py`: `lines(findings, constraints) -> list`。今の `lib/runreport.py:1026-1046` の `premise_lines` の、依頼の行と制約を値で受ける形の写し（3.4）。
- 形のファイルはこの block に置かない。依頼の行は `blocks/.shared/schemas/request.schema.json`（`requestrows` の口）、運ばれた実測は `blocks/.shared/schemas/constraints.schema.json`（`shared:constraints.schema.json`）を使う（4 節・8 節の 3）。
- 使う `lib/`: `accept`（KEEP。`tree_state`・`tree_moved`・`type_errors`・`TREE_SCHEMA`・`TREE_KEYS`・`guard`・`in_repo`）・`rolekit`（KEEP。`accept_round`・`given_up_reason`）・`graphloops/engine/util.py`（KEEP。`Reject`）・`jsonfile`・`oneline`。
- 作り直しの間は `lib/premises.py` と `lib/judge_accept.py` の前提の部分を消さない（今の judge が使う）。組み込みで消す（README の 9.2）。

### 1.6 つなぎ方（graph の側。block には書かない）

- judge のまとめ（`blocks/judge/`）: `include: works-factory-premises`。並びは今と同じく並行 PR の block の後（今の `premises-loop` の `depends_on: [pr-scan, pr-check-loop]`。`workflows/judge/works-factory-judge.yaml:561-563`）。`when:` は judge の入口で依頼が読めた時。`with:` は `request: $<依頼の pointer>`・`carried: <依頼の容器の constraints の欄。line が依頼のファイルから引く>`・`lang: <始めの記録の lang>`。
- `status` が `failed` の時: 今は止めの記録で目的の役と判定役を起こさず、judge の返りが `stop_reason: works:premises` になった（`lib/judge_accept.py:3914-3921` の `_missing_stage`）。graph は `$premises.output.ok == true` を目的の block と diagnose の `when:` に置き、judge のまとめの返りの止めの語に `works:premises` を入れる。
- 読み手: 目的の block の `constraints`（`$premises.output.constraints`）・diagnose の `constraints`・独立設計の役の前提（今は plan-review の入力 `premises`。`workflows/plan-review/works-factory-plan-review.yaml:22-24`）・report の `sections`（`$premises.output.report`）。

## 2 node の設計シート: premises（実測役）

### 2.1 役

依頼の主張を作業ツリーで測り直し、走らせたコマンドと出力を付けた制約の一覧を返す。作業ツリーは変えない。

### 2.2 port

`intake.json` の `findings`（← port `request`）、前の回までの拒みの理由の全部（← place の拒みの控え `rejects-premises.json`）、`lang`（← port `lang`）。リポジトリは run の作業ツリー（Archon の cwd）。運ばれた実測（← port `carried`）は役に見せず、受け付けが返答に足す（今と同じ）。

### 2.3 組み立ての順（`prompts/premises.md`）

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: 拒みの控えが空でない。断片の中の `{rejection}` ← 前の回までの拒みの理由の全部（`rolekit.rejects_text`。8 節の自分で決めた 7）。
2. `{shared:query-rule}`（外への検索の決まり）。断片の中の `<!-- if spawns -->` には `spawns: false` を渡す（この役は Agent の道具を持たない）。
3. 役の定義（決まった文）: 新しい会話・依頼の主張を測り直して制約にする・後の役が所与として読む。
4. `## Tools and what you must keep`（決まった文）: 道具・作業ツリーを変えない・`$TMPDIR`・git の禁止・戻し方 2 つ。
5. `## Input`（決まった文）: 依頼の行の説明（空の配列の時の決まりを含む）・対象のリポジトリ。続けて ```` ```json ```` の囲みと `{request}`（← `intake.json` の `findings` を `json.dumps(findings, ensure_ascii=False, indent=1)` にした字）。
6. `## Steps`（決まった文）: 手順 1〜6 と実例 2 つ。差し込み口 `{measured}`・`{hypothesis}`（← `src/steps.py` の `MEASURED`・`HYPOTHESIS`）。
7. `## Output`（決まった文）: 欄の説明・対象の名前が要るので引かなかった調べの書き方・受け付けが拒む 2 つの場合・言語の 1 文。差し込み口 `{measured}`・`{hypothesis}`・`{lang}`。

md の本文（英語。この block の PR の 2 つ目の commit でこのまま置く）:

````markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{shared:query-rule}

You are the measuring role. Before the request is grouped into root-cause units, measure again in this working tree every claim the request makes about numbers, sizes, counts, "exists / does not exist", and "X can arrive", and turn them into a list of constraints. Later roles read your constraints as given, so if you hand over a wrong fact here, every judgment and fix built on it goes off.

## Tools and what you must keep

- Your tools are Read, Grep, Glob, Bash, and WebSearch and WebFetch for the web. Bash runs inside a sandbox. You may run commands to measure (`grep -c`, `wc -c`, `ls`, `git log`, running tests, and so on).
- **Do not change a single character of the working tree.** The machine compares the state of the working tree it recorded before you were started with the working tree now, and rejects your answer if it changed (what you measured would mix into the diff of the later fix).
  - If you write output, write it outside the working tree (`$TMPDIR`). If you run Python, set `PYTHONDONTWRITEBYTECODE=1`.
  - Do not move the working tree or the history with `git add`, `git commit`, `git stash`, `git reset`, or `git checkout` (the machine also checks that HEAD did not move; a commit is rejected too).
  - If you created something by mistake, remove it yourself before you answer. There are only two ways back:
    - Remove untracked things (output files, caches) with `rm`.
    - If you rewrote a tracked file, restore it with `git restore -- <path>` (this puts only the working-tree file back to its HEAD content; HEAD, the index, and the history do not move). This is allowed as an exception to the rule above.

## Input

- The request lines: the JSON array below, whose shape the machine has checked. Each line has `where` and `text`, and optionally `mechanism`, `measured`, and `false_positive_if`. If the array is empty, this run has no request lines (it only reviews the target's diff) and there are no claims to measure: return `constraints` as an empty array.
- The target repository: the current working directory (the run's working tree).

```json
{request}
```

## Steps

1. From each line's `text`, `mechanism`, and `false_positive_if`, pick up every claim about numbers, sizes, counts, exists / does not exist, "X can arrive", and "X turns red".
2. **Do not trust each line's `measured` (a value the requester says they measured) as written.** The requester's measurement may come from another version, another working tree, or a path that is gone. Measure it again in this working tree, and if it does not match, write the value you measured in the constraint (also write the difference from the request's value in `text`).
   - For every line that has `measured`, write at least one constraint, and put that line's `where` in its `text` exactly as written (not one character changed). The machine rejects the answer if no constraint has in its `text` the `where` of a line with `measured`.
   - If you cannot measure it again in this working tree (production input, things outside the target), give it `kind: {hypothesis}` and write the `where` and why it cannot be measured in `text`. Do not copy the requester's value as `kind: {measured}`.
3. Write a claim as a constraint only after you have made it **a value measured in this working tree or a fact that names a file.** Do not hand over memory, an earlier measurement, or a general statement as a constraint. Later roles take it as given and derive the ideal solution from it, so a wrong premise still passes their judgment.
   - A fact that names a file also needs a command that shows it (`ls`, `git ls-files`, `grep -n`, and so on): run it and attach its output to make it `kind: {measured}` (step 5). If you cannot show the command and its output, make it `kind: {hypothesis}`.
   - A real case: in "the body is up to about 4MB", the 4MB was measured on a path that the same PR deleted. The real size was 5,411 bytes, and five rounds of work were built on that wrong premise.
4. Add `measured_how` (how you measured) to every constraint.
5. **To `kind: {measured}`, add `measured_output`: the command you ran and its output itself** (only the needed lines if it is too long; start command lines with `$ `). Give `kind: {hypothesis}` to anything for which you cannot show a command and its output.
   - Only the `{measured}` label is promoted to a trusted value without a recheck, so a wrong fact reaches, as a given, the roles that question everything from zero. A real case: "the repository has no CI definition" was frozen as measured, but `.github/workflows/test.yml` existed. Even when another node of the same run wrote on that premise, the constraint was not corrected.
   - When you write "does not exist", paste where you looked and the command in `measured_output` (an empty output of `ls`, `git ls-files`, or `grep -r` is also output).
6. If the request has no claim to measure, `constraints` may be an empty array.

## Output

Return one JSON object that matches the output schema. Its only field is `constraints`, and each row has:

- `text`: the constraint (a measured value or a fact that names a file; if it differs from the request's value, both)
- `measured_how`: how you measured it
- `kind`: `{measured}` (you can show the command and its output) or `{hypothesis}` (you cannot)
- `measured_output`: required for `kind: {measured}`. The command you ran and its output itself

A search you did not run because it needs the target's names (under the rules for queries at the top) is returned as one `kind: {hypothesis}` constraint row: in `text`, write "a search not run because it needs the target's names" and what you wanted to confirm (the `where` of the request line), and in `measured_how` write "not run (needs the target's names)". This reply has no field for "missing" or "unverifiable", so this row is the mark that sends it to a person.

The machine rejects the answer if a `kind: {measured}` row has no `measured_output` (whitespace only counts as none), and if no constraint has in its `text` the `where` of a request line with `measured`.

Write `text` and `measured_how` in {lang}. Keep keys, enum values, identifiers, paths, commands, command output, and error messages as they are.
````

### 2.4 返す形

今の `output_format` のまま（`workflows/judge/works-factory-judge.yaml:594-611`）:

```yaml
type: object
required: [constraints]
additionalProperties: false
properties:
  constraints:
    type: array
    items:
      type: object
      required: [text, measured_how, kind]
      additionalProperties: false
      properties:
        text: {type: string}
        measured_how: {type: string}
        kind: {type: string, enum: [実測, 仮説]}
        measured_output: {type: string, minLength: 1, pattern: '\S'}
```

`kind` の enum は `src/steps.py` の `(MEASURED, HYPOTHESIS)` と同じ並び（試験が結ぶ。7.2）。人に見せる欄は `text`・`measured_how`（後の役の材料と、報告の「依頼の実測を測り直せなかった」の行に載る）で、言語は `{lang}`。`measured_output` はコマンドの出力なので訳さない。

### 2.5 描いた骨組み（例の run の値）

```markdown
{shared:query-rule の本文: Rules for queries to outside services …（spawns の段落は入らない）}

You are the measuring role. Before the request is grouped into root-cause units, …

## Tools and what you must keep

- Your tools are Read, Grep, Glob, Bash, …
- **Do not change a single character of the working tree.** …（決まりの箇条と戻し方 2 つ）

## Input

- The request lines: the JSON array below, …
- The target repository: the current working directory (the run's working tree).

```json
[
 {
  "where": "workflows/merge/scripts/pr_commit.py の hook_env（73 行あたり）",
  "text": "出口の語 deliver=pr の run で PR 用の commit を積む時、commit のフックに渡す環境を作る hook_env は、…（約 380 字）"
 }
]
```

## Steps

1. From each line's `text`, …
2. **Do not trust each line's `measured` …** …
   - … do not copy the requester's value as `kind: 実測`.
…

## Output

…
- `kind`: `実測` (you can show the command and its output) or `仮説` (you cannot)
…

Write `text` and `measured_how` in the language of the request lines. …
```

例の run の依頼の行は `measured` を持たない 1 行で、役は `kind: 実測` の制約 4 行を返して 1 回目で通った（`premises.json`）。運ばれた実測は空（`carried-constraints.json` が `[]`）。却下の段落は入らない。

### 2.6 今の指示との差

今の指示は `workflows/judge/commands/premises.md`（68 行）に在り、役が Read する依頼の行のファイル `judge/request.json` は judge の入口が置いていた。

- 移した: 依頼の行を Read させる行（md:38「人の修正依頼の行: `$ARTIFACTS_DIR/judge/request.json`（…**まず Read せよ**）」）をやめ、依頼の行の JSON を指示の中に入れた。行の説明（各行の欄・空の配列の時の決まり）は残した。
- 移した: 外への検索の決まりの塊（md:3-10。元は `lib/agents/judge.md:16-22`）を共通の断片 `{shared:query-rule}` に（world.md の 3.6 と同じ）。塊の頭の「works の包みより」と「Agent で子を起こすなら…含めよ」は、断片の `spawns` の段落の外に出ない（この役は Agent を持たない）。
- 消した: 頭の拒みの節（md:14-20）と区切り（md:12・22）と、`## 入力` の拒みの行（md:40「前の回の受け付けが拒んだ理由は、この指示書の頭のセクションに在る…」）と、末尾の 1 文（md:68「拒んだ理由が次の回の指示書の頭に届く。」）。共通の断片 `{shared:rejected}` の 1 回にした。決まりは今と同じ「丸ごと出し直せ」。入る理由は前の回の 1 つから回の全部に変わる（8 節の自分で決めた 7）。
- 移した: 言語の 1 行（md:1。`$premises-reject.output.lang_line`）を `## Output` の最後の 1 文に。汎用の欄の並びは、この node の人に見せる欄（`text`・`measured_how`）の名指しに替えた。
- まとめた: md に字で書いていた `kind` の 2 語（md:47-53・63）を差し込み口 `{measured}`・`{hypothesis}` にした。
- 替えた: 「判定役が人の修正依頼を根本の単位にまとめる前に」「判定役はこの役の制約を所与として読む」（md:24）と「判定役はそれを所与として理想解を導く」（md:48）の「判定役」を、「後の役」（Later roles）にした。この block はほかの block を名指さない（憲法の 3）。言っている事（後の役が所与として読むので、誤った事実を渡すと全部ずれる）は同じ。
- 替えた: 作業ツリーの写しの説明（md:29「依頼を受け付けた時に取った作業ツリーの姿」）を「役を起こす前に取った姿」に。写しを取る所が judge の入口からこの block の `intake` に移ったため（3.1）。
- 消した: ほかの node の id（`$premises-reject.output.*`）と `$ARTIFACTS_DIR` の字。
- 足した物は無い。2 つ目の commit で英語にした（#764）。役の名「実測役」は "the measuring role"。
- 今の md の「この役は新しい会話で起きている」は英語に写さなかった。輪は `fresh_context: false` で、2 回目からは同じ会話の続きになるため（レビューの指摘）。

### 2.7 元の works と graphloops の同じ場面

元の works の `works/blk-premises/`（入力 `request`〔依頼のファイルのパス〕・`base_rev`、出口 10 欄の独立したブロック）から、工場は判定のブロックの中に写した（#76。`docs/plans/2026-10-12-blocks/judge.md:30`・`:62`）。graphloops の同じ場面は `prompts/review-loop/p0.premises.md`（`p0.premises`。4 行の短い指示）と、写しの rules の `measured_needs_output`。

- 独立したブロックの形（入力だけで動く）: 工場は judge の中に直に置き、`judge/request.json` を読む形にした（#76）。この block で元の形に戻す。
- 出口の要約 `constraints_summary`（判定役に貼る 1 行 1 制約の文）と数（`constraints`・`measured`・`hypotheses`・`claims`・`claims_hypothesis`）と `reads_file`: 工場は #232 で `lib/premises.py` の `collect` を「届かない関数」として消した（`d91c4b49`。工場の線では判定役の支度が `premises.json` を直に読むため）。この block は、数のうち `measured`・`hypotheses` を戻す（読み手が pointer を開かずに「実測が在るか」を見られる。8 節の自分で決めた 4）。要約の文は戻さない（読み手の md の材料の組み方なので、読み手の block が組む）。`reads_file` は元の works でも「まだ無い（空）」の欄だった。
- 入力 `base_rev`（受け付けが HEAD がその版のままかを見る）: 工場は写しが在る時は写しと比べるだけで、版を受けない（`lib/judge_accept.py:1139-1160` の `_tree_unchanged`。写しが無い時だけ `rev` を見る）。元の works も写しを必ず取ったので、版は写しの無い時の守りだった。この block は写しを `intake` で必ず取るので、版の入力は要らない。意図して外した記録は（未確認）。
- 依頼の型の確かめを使い捨ての置き場で通すだけで積まない（元の intake）: この block も積まない（place に `intake.json` を書くだけ）。依頼の型は `request.schema.json` が確かめる。
- 3 回とも拒まれたら、元の works のメイングラフの共有の記録（盤面）に止めの印を置いて、後ろの判定役を起こさない（元の `collect`。元の works の裁定の番号 R50）: 工場は止めの記録 `stopby.PREMISES` を置く形にした。この block は `status: failed` を返し、止めるかは graph が決める（1.6）。
- 前の run の前提の検算の実測を足す（元 `review-loop.py:3751-3755` の finalize の `facts_to_add`。graphloops では `stop.premise_check` の役が足した）: 工場は run をまたいで依頼の容器の `constraints` で運ぶ形にした（#264。`86c3f28c`）。この block は port `carried` で受ける。
- graphloops の `p0.premises` に無く工場が持つ物（元の works から）: 依頼の `measured` の行の `where` を字のまま含めさせる照らし・作業ツリーの写しとの比べ・戻し方 2 つ・「無い」と書く時のコマンドの出力。この block は全部残す。

### 2.8 受け付け

- 却下の決まり（`src/steps.py` の `check(reply, place, repo, findings, carried)`。今の `lib/judge_accept.py:1195-1215` の写しで、照らす順と訳の字も今のまま）:
  1. 依頼の `measured` の行の `where` を `text` に含む制約が無い → 「依頼の実測を測り直した制約が無い: <where>・…。text に where をそのまま入れよ（この作業ツリーで測り直せなければ kind: 仮説 に落とし、text に where と測れない理由を書く）」。
  2. 作業ツリーが写し `tree.json` から変わった（`accept.tree_moved`。比べる欄は `accept.TREE_KEYS` の全部。今と同じ）→ 「役を起こした後から作業ツリーが変わった——実測役は作業ツリーを変えてはいけない（HEAD・枝・git が無視するファイルも）。作った物（出力のファイル・キャッシュ）は rm で消し、書き換えた追跡中のファイルは git restore -- <path> で戻してから出し直せ（出力は $TMPDIR に置く）（<変わった所>）」。写しが無い・読めない時も拒む（今の `_moved_since`）。
  3. `kind: 実測` の行に `measured_output` が無い（空白だけも同じ）→ 「p0.premises: kind=実測 なのに measured_output（実行したコマンドと出力）が無い制約がある: [<text の頭 60 字>…]——コマンドと出力を示せないものは kind=仮説 に落とせ」。
  - どれも `Reject` を `accept.guard` が `{ok: false, reason}` にする。
- 受けた時: `premises.json` に `with_carried(reply, carried)` を書く（運ばれた実測の行のうち、返答に同じ `text` の行が無い物を後ろに足す。今の `lib/judge_accept.py:1187-1192`。運ばれた実測は `intake.json` の `carried` から読む）。
- 回数: `rolekit.accept_round(place, "premises", raw, take)`。3 回目の拒みで `done` が true になり loop を抜ける。run は止めない。
- 諦めた時に出口へ書く物: `finish` が `status: failed`・`constraints: null`・`reason` に `rolekit.given_up_reason(place, "premises")`（諦めた文。回数に届かずに輪が終わった時は最後の拒みの文）・`report` に `前提の制約: <reason>` を返す。

### 2.9 試験

7 節に全部を書いた。この node に当たる物: standalone の fixture・指示の比べ（7.3）・受け付けの振る舞いの試験（7.2 の `AcceptCase`）。この block が直に担う keep-essence の番号は無い（間に関わる 9 との関わりは 7.4）。

## 3 script の node

### 3.1 `intake.py`

1. `request`・`carried`・`lang` を `os.environ.get("INPUTS_REQUEST")` などの字のままで読み、`requestrows.parts(raw)`（形は `shared:request.schema.json`）・`ports.json(raw, "shared:constraints.schema.json")`・`ports.text(raw)` に渡す。
2. この block のファイルを名で消す（1.4 の 5 つ。place の中のほかのファイルは消さない。今の judge の入口は前の控えを残さなかった）。
3. 依頼の行 `findings` は `requestrows.parts` の `findings`。運ばれた実測 `carried` は、port の値が配列ならそれ、`{"constraints": [...]}` ならその欄（運ばれた行は前の run の検算の実測で `実測` の行も `measured_output` を持たないので、ここでは出力を求めない）。それが空で、依頼が object で `constraints` の欄を持てば、その欄（今の judge の入口が依頼の容器から `carried-constraints.json` を置いたのと同じ。`lib/judge_accept.py:3862`）。
4. `intake.json` に `{findings, carried, lang, failed: false, reason: ""}` を書く。
5. 作業ツリーの写しを `tree.json` に書く（`accept.tree_state(Path.cwd())`）。
6. `{due: true, reason: ""}` を返す。
7. 1〜5 のどこかで例外が出たら（読めない port・在らない pointer・git が効かない）、落ちずに `{due: false, reason: "<何が>読めない（<型>: <訳>）"}` を返し、`intake.json` に `{findings: [], carried: [], lang: "", failed: true, reason}` を書く（place を作れない時は返りだけを返す）。

### 3.2 `measure_prep.py`

1. `intake.json` を読む。前の回までの却下は `rolekit.rejected(place, "premises")` で place の控えから全部読む。
2. `prompt.emit("premises", values, when, prompt.round_of("premises"))` を呼び、`{prompt}` を返す。`when = {"rejected": 控えが空でない, "spawns": False}`（`spawns` は共通の断片 `query-rule` の中の段落の名。world.md の 3.3 と同じ渡し方）。
3. `values`: `rejection`（`rolekit.rejects_text(控え)`。前の回までの却下の全部）・`request`（`json.dumps(findings, ensure_ascii=False, indent=1)`）・`measured`（`steps.MEASURED`）・`hypothesis`（`steps.HYPOTHESIS`）・`lang`（`intake.json` の `lang`。空なら土台の既定の文）。

### 3.3 `measure_accept.py`

`INPUTS_REPLY` を読み、`intake.json` の `findings`・`carried` と place の `tree.json` で、2.8 の `rolekit.accept_round` を呼ぶ。返り `{ok, done, reason}`。`check` は `accept.in_repo(Path.cwd())` の中で回す（今と同じ）。

### 3.4 `finish.py`

1. `intake.json` を読む。`failed` が真なら `status: failed`・`reason` はその訳。
2. ほかは `premises.json` を読む。在れば `status: ok`。無ければ `status: failed`、`reason` は `rolekit.given_up_reason(place, "premises")`、それも空なら控えの最後の拒みの文、それも無ければ「前提の実測を受け付けた控えが無い（役が走らなかったか落ちた）」（今の `lib/judge_accept.py:3919` の訳と同じ向き）。
3. `report`: `ok` の時は `report.lines(findings, constraints)`。中身は今の `premise_lines` と同じ: 制約のうち `kind` が `仮説` の行を `hyp` とし、依頼の行で `measured` と `where` を持つ物ごとに、`where` を `text` に含む最初の `hyp` の行が在れば `依頼の実測を測り直せなかった（前提は仮説）: <where>——<その行の text>`。`failed` の時は `[f"前提の制約: {reason}"]`。
4. 返り: `{ok, status, reason, constraints: ports.pointer(place / "premises.json") か None, measured: <実測の数>, hypotheses: <仮説の数>, report}`。
5. どこで例外が出ても落ちず、`{ok: false, status: failed, reason: "<型>: <訳>", constraints: null, measured: 0, hypotheses: 0, report: ["前提の制約: <訳>"]}` を返す。

`finish` の `output_format`:

```yaml
type: object
additionalProperties: false
required: [ok, status, reason, constraints, measured, hypotheses, report]
properties:
  ok: {type: boolean}
  status: {type: string, enum: [ok, failed]}
  reason: {type: string}
  constraints:
    type: [object, "null"]
    properties:
      type: {type: string, enum: [archon_artifact]}
      run_id: {type: string}
      path: {type: string}
  measured: {type: integer, minimum: 0}
  hypotheses: {type: integer, minimum: 0}
  report: {type: array, items: {type: string}}
```

null を許す欄の書き方 `type: [object, "null"]` は、今の `workflows/chain/works-factory-chain.yaml:359-361` と同じ。

`intake` の返り `{due: boolean, reason: string}`・`measure_prep` の返り `{prompt: string}`・`measure_accept` の返り `{ok: boolean, done: boolean, reason: string}` は、どれも `additionalProperties: false` で全部の欄を `required` にする。

## 4 作るファイルと触るファイル

作る:

- `blocks/premises/works-factory-premises.yaml`
- `blocks/premises/prompts/premises.md`
- `blocks/premises/scripts/intake.py`・`measure_prep.py`・`measure_accept.py`・`finish.py`（どれも uv の頭の宣言 `# /// script` を持つ）
- `blocks/premises/src/__init__.py`・`src/steps.py`・`src/report.py`
- `blocks/premises/fixtures/standalone.stubs.yaml`・`gave-up.stubs.yaml`・`bad-request.stubs.yaml`
- `tests/blocks/premises/__init__.py`・`test_premises.py`・`test_prompt_compare.py`（1 つ目の commit だけ）。筋書きを Archon で回すのは `tests/layers/test_block_shape.py` が全 block を回すので、`test_fixtures.py` は作らない（8 節の自分で決めた 9）
- `docs/design/premises.md`（この文書。直す時）

触らない: `lib/`（読むだけ）・`workflows/`・ほかの block。共通の断片 `blocks/.shared/prompts/rejected.md`・`query-rule.md` は土台の PR が置く物を使う。

形のファイル: この block は `schemas/` を持たない。`blocks/.shared/schemas/constraints.schema.json`（運ばれた実測の行の配列か `{constraints: [...]}`。行の欄は役の `output_format` の `constraints` の行と同じ）を `shared:constraints.schema.json` で使い、同じ名のファイルを block に置かない（同じ名が 2 か所にあると形の検査が赤くなる）。`実測` の行に `measured_output` を求める決まりは形に書かず、`src/steps.py` の受け付け（`measured_needs_output`）が役の返答に対して照らす（8 節の自分で決めた 3）。

## 5 差し込み口の一覧（`prompts/premises.md`）

| 口 | 値の出どころ |
|---|---|
| `rejection` | place の拒みの控え `rejects-premises.json`（前の回までの却下の全部） |
| `request` | `intake.json` の `findings`（← port `request`）の JSON の字 |
| `measured`・`hypothesis` | `src/steps.py` の `MEASURED`・`HYPOTHESIS` |
| `lang` | port `lang`（空なら土台の既定の文） |

選ぶ段落の名: `rejected`（前の回の理由が空でない）・`spawns`（共通の断片 `query-rule` の中。いつも false）。

## 6 単独で呼ぶ

```sh
bin/works-factory <読ませるフォルダを blocks/ にする引数（名は土台の PR で決める）> workflow run works-factory-premises \
  --input request='[{"where":"stats.py:4","text":"mean は 2 でなく 3 を返す","measured":"3"}]'
```

出力は `workflow get <run>` の `finish` の返り。`constraints` の pointer の先は、その run の `premises.json`。始めの記録は要らない。

## 7 試験と、済んだと言える条件

### 7.1 standalone の fixture（`blocks/premises/fixtures/`）

- 筋書きは `exec-code: true` で script を本当に走らせ、差し替えるのは AI の node `premises` の返答だけ（`tests/layers/test_block_shape.py` の約束）。
- `standalone.stubs.yaml`: `fixture.inputs` は `request: '[{"where": "stats.py:4", "text": "mean は 2 でなく 3 を返す", "measured": "3"}]'` だけ。`expect: completed`・`reached: [intake, premises-prep, premises, premises-accept, finish]`。`resolved-text-contains` の `premises` は md の決まった文。`premises` の返答は `where` を `text` に含む `kind: 実測` の 1 行（`measured_output` 付き）。
- `gave-up.stubs.yaml`: 入力は同じ。`premises` の返答は `where` を含まない `仮説` の行で、受け付けが拒み（筋書きは輪が 1 周で終わる）、`finish` が `status: failed` を返す。3 回で諦める数えは 7.2 の試験が確かめる。
- `bad-request.stubs.yaml`: `fixture.inputs` は `request: '{"rows": []}'`（容器の鍵でない）。`reached: [intake, finish]`（`intake` が本当に `due: false` を返し、役は起きない）。

### 7.2 `tests/blocks/premises/test_premises.py`

script を子のプロセスで回す（今の `tests/workflows/test_judge.py:695-704` の `Run.run` と同じ形。`hermetic.child_env` で `ARTIFACTS_DIR`・`WORKFLOW_ID`・`WORKS_FACTORY_ROOT`・`PYTHONDONTWRITEBYTECODE=1`・`INPUTS_…` を渡す）。始めの記録は置かない。使い捨ての git のリポジトリに `stats.py` を commit して置く。

- `IntakeCase`: 配列の依頼・容器の依頼で `intake.json` の `findings` が同じ。`carried` が空で容器が `constraints` を持てばそれを使う。`tree.json` が `accept.TREE_SCHEMA` に合う。読めない依頼・容器でない鍵で `due: false`。
- `PromptCase`: `measure_prep` の `prompt` に依頼の行の JSON が在り、`$ARTIFACTS_DIR` と `judge/request.json` の字が無く、埋まらない差し込み口が無い。拒みの理由が空でない時だけ却下の段落が入る。外への検索の決まりの断片が入る（元: `tests/workflows/test_judge.py::test_roles_that_reach_outside_carry_the_query_rule` の premises の行）。
- `AcceptCase`（元: `lib/tests/test_judge_accept.py::PremisesCase` の全部〔:928-985〕）: 実測なのに出力が無い制約を拒む・仮説は出力が要らず通った返答が `premises.json` に書かれる・依頼の実測は測り直させる・役が作業ツリーを変えたら拒む・バイトコードも変更と数える。元の `tests/workflows/test_judge.py::test_premises_reply_outside_the_type_is_rejected`（:194-198）は、`output_format` の照らしを Archon が持つので、YAML の `output_format` で同じ 3 つの返答が拒まれることを `engine.schema.validate_schema` で照らす形にする。
- `CarriedCase`（元: `lib/tests/test_judge_accept.py::CarriedConstraintsCase.test_carried_constraints_join_the_premises`〔:907-926〕と `tests/workflows/test_judge.py::CarriedConstraintsCase.test_carried_rows_fit_the_premises_shape`〔:2086-2093〕）: 運ばれた実測が返答に足される（同じ字は 2 度足さない）。`carry.carried_constraints` の行が `constraints.schema.json` と役の `output_format` の両方に通る。
- `FinishCase`: 受けた時は `status: ok` と pointer と数。3 回拒まれた時は `status: failed`・`constraints: null`・諦めた文。`measured` を持つ依頼の行に `仮説` の制約が当たる時だけ `report` に行が載る（元: `lib/tests/test_runreport.py` の `premise_lines` を見る試験の行。報告の行は block の試験へ移る）。
- `ShapeCase`: YAML の `premises` の `output_format` の `kind` の enum が `[steps.MEASURED, steps.HYPOTHESIS]`、loop の `max_iterations` が `rolekit.GIVE_UP_AFTER`、AI の node の鍵（群・`settingSources`・道具・sandbox と `denyWrite`・`idle_timeout`・`mutates_checkout`・`retry`）が 1.3 のとおり（元: `test_roles_keep_the_old_settings` の premises の行）。
- 写さない試験: `tests/workflows/test_judge.py::test_missing_premises_or_purpose_stops_even_with_an_accepted_judgment`（judge のまとめの `when:` と返りの試験へ）・`test_roles_receive_the_reject_reason_through_the_loop_head`・`test_unreadable_start_pointer_degrades_in_every_lang_line_script`（reject の node と始めの記録が無くなる）。

### 7.3 指示の比べ（README の 11.4）

- 1 つ目の commit: md を日本語のまま置く。`tests/blocks/premises/test_prompt_compare.py` が、例の run の値（`request.json` と同じ `findings`、拒みなし、`lang` 空）で `measure_prep` を回して組んだ指示から共通の断片 `query-rule` の字を除いた物と、次の手で組んだ「今の指示」を、空白と改行の違いを除いて同じ字か照らす:
  1. `workflows/judge/commands/premises.md` の字から、1 行目（言語の 1 行）・3〜10 行目（外への検索の決まりの塊）・12〜22 行目（区切りと拒みの節）・40 行目（拒みの行）と、68 行目の末尾の 1 文「拒んだ理由が次の回の指示書の頭に届く。」を除く。
  2. 38 行目を、次の字に替える: 「- 人の修正依頼の行: 下の JSON の配列（機械が型を確かめた依頼の行）。各行は `where`・`text` と、任意の `mechanism`・`measured`・`false_positive_if`。空の配列なら依頼の行の無い run（対象の差分だけを審査する）で、測る主張は無い——`constraints` は空の配列にせよ。」。39 行目の後に ```` ```json ````・依頼の行の JSON の字・```` ``` ```` を足す。
  3. 29 行目の「依頼を受け付けた時に取った作業ツリーの姿」を「役を起こす前に取った作業ツリーの姿」に替える。
  4. 末尾に、新しい言語の 1 文（日本語の md に置いた字）を足す。
  5. 「判定役」を「後の役」に替える（2.6 の「替えた」。この block はほかの block を名指さない）。
- 2 つ目の commit: md を英語にし、`test_prompt_compare.py` を消す。今の指示（今の md の字に例の run の値を入れた物と `judge/request.json` の字）と新しい指示を同じ値で組んで並べた物を PR の本文に載せ、2.6 の差の一覧どおりかを審査が見る。

### 7.4 keep-essence の番号

12 の仕組みのどれも、この block が直に担う物ではない（README の 10 節）。この block の出力（制約）は、独立設計の役（9）と根本の診断に所与として渡る材料で、`実測` の札に出力を求める照らし（`AcceptCase` の `test_measured_without_output_rejected` の写し）が、誤った事実を独立の目に所与として渡さない守りになる。e2e の照らしの表 `tests/e2e/evidence.json` の `J09`（依頼の実測の測り直し。今は筋書きでのみ）は、node の id と place のパス（`judge/premises/`）を新しい物に合わせる。

### 7.5 済んだと言える条件（PR ごと。README の 11.2）

```sh
uv run --isolated python3 -m unittest tests.blocks.premises.test_premises
uv run --isolated python3 -m unittest tests.blocks.premises.test_fixtures        # archon workflow test（源と bun が無ければ見送る）
uv run --isolated python3 -m unittest tests.blocks.premises.test_prompt_compare  # 1 つ目の commit だけ
uv run --isolated python3 -m unittest tests.layers.test_block_shape
uv run --isolated python3 tests/changed.py
```

`test_fixtures.py` は `tests/archon.py` の使い捨ての木に `blocks/` を置いて `archon workflow test works-factory-premises --json` を回し、3 本の筋書きが全部通ることと、`archon validate workflows` が警告なしで通ることを照らす。最後に、6 節の命令で本物の単独の run を 1 回回す。

## 8 根拠を書いて自分で決めた事

1. 依頼の行を Read させる形をやめ、指示の中に JSON で入れた。根拠: README の 4.3（block は自分の place と port の値が指すファイルのほかは開かない）と 5.2（指示は `prompt:` に直に入れる）。役が Read したのは同じ JSON の字なので、役に届く中身は変わらない。
2. 作業ツリーの写しを、judge の入口でなくこの block の `intake` で取る。根拠: 写しを取る所が block の外に在ると、単独で回せない（憲法の 5）。写しを取る時が並行 PR の役の後に移るが、並行 PR の役も読むだけの役で、その受け付けが同じ写しで作業ツリーが変わっていないことを確かめている（今の `TREE_FILE` の注。`lib/judge_accept.py:3764`）ので、比べの範囲は狭まらない。loop の中の prep で取り直さないのは、1 回目に変えて拒まれた役の変更が 2 回目の写しに入り、比べが緩むのを避けるため。
3. 運ばれた実測の形は、土台の PR が置いた共通の `blocks/.shared/schemas/constraints.schema.json` を使い、この block に同じ名の形のファイルを置かない。「`実測` の行は `measured_output` を持つ」は形に書かず、`src/steps.py` の受け付け（`measured_needs_output`）が役の返答に照らす。根拠: 共通の形は `KNOWN_KEYWORDS` の語だけで書け（`$schema`・`$defs`・`$ref`・`oneOf`・`if`/`then` は照らしが飛ばすので `ports.json` が拒む）、外の容器は開けたままにする決まり。同じ名の形を 2 か所に置くと形の検査（`check_input_forms`）が赤くなる。`measured_output` を port の `carried` で求めないのは、運ばれる行（`carry.carried_constraints`）が `kind: 実測` で `measured_output` を持たない（前の run の検算の実測）ので、求めると今の judge が通す行を拒み、運ぶ能力が落ちるため。出力を求めるのは、役が自分で測った返答だけ（今の受け付けの決まり 3 と同じ）。
4. 出力に `measured`・`hypotheses` の数を置いた。根拠: 元の works の出口が持っていた数で、#232 は「届かない関数」として消した（工場の線に読み手が無かった）。block の出力では、読み手が pointer を開かずに「実測が 1 つでも在るか」を見られ、報告と承認ノードの材料になる。欄を足すだけで振る舞いは変えない。読み手が要らないと決まれば消してよい。
5. 依頼の行が空の配列の run でも役を起こす（今と同じ）。根拠: 振る舞いを変えない。役の md が「空なら `constraints` を空の配列に」と決めていて、今の judge もこの道で役を起こしている。AI の 1 回を省く変更は、この作り直しの外で扱う。
6. 依頼の型の確かめは共通の口 `requestrows.parts` に任せ、この block に `request.schema.json` を置かない。根拠: 共通の形が土台の PR に既にあり、容器の知らない鍵・下書きの行の拒みまで同じ口が持つ。
7. 却下の段落に入れる理由は、前の回の 1 つでなく回の全部（`rolekit.rejects_text`）にした。前の回の理由は `with: $LOOP_PREV` で受けず、place の拒みの控えから読む。根拠: `blocks/.shared/AGENTS.md`（prep は `$LOOP_PREV` で却下を受けず控えから全部読む）。主な効き目は、会話が継がれない役が前の回の誤りを繰り返さないこと。拒みを減らす方向の変更で、拒みの決まりは変わらない。
8. intake は place のファイルを全部は消さず、この block が名を持つ 5 つだけを名で消す。根拠: `blocks/.shared/AGENTS.md`（block が消してよいのは自分が名を持つファイルだけ）。include されると place は graph のほかの block と同じ run directory の下に在る。前の `premises.json` を残すと、役が走らなかった run が前の結果を `ok` で返すので、これは消す。
9. `test_fixtures.py` を作らない。根拠: 筋書きを Archon で回す検査は `tests/layers/test_block_shape.py` が全 block に対して持つ（`archon validate` も）。block ごとの写しを増やさない。AI の node だけを差し替える筋書き（`exec-code: true`）の約束も同じ検査が決める。
10. 出口の諦めの理由は、`given_up_reason` が空なら控えの最後の拒みの文、それも無ければ「受け付けた控えが無い」の順にした。根拠: 筋書きのように輪が回数に届かず終わる時に、本当の理由（最後の拒み）を返すため。目的の block と同じ順。
11. 役の node に `mutates_checkout: false` を書かない（1.3 の字から変えた）。根拠: Bash を持つ役に書くと機械の検査 E7（作業ツリーを変える道具を持つ役）が赤くなり、今の node も書いていない。実行基盤の状態の照らしが無い分、受け付けが全欄（`porcelain` も含む `accept.TREE_KEYS`）を写しと比べる（目的の block は読むだけの役で `mutates_checkout: false` を書き、`porcelain` を外している。この block は逆）。


## 9 README へ返す問題

下の 3 つは README に当てた（8.2・10 節の 9・9.3・13 章）。

1. 独立設計（independent-design）の入力は README の 8.2 で `purpose` だけだが、今の独立設計の役は実測した制約も貼られている（`lib/boardview.py:714-750` の `r2_prompt` が入力 `premises` の `constraints` を貼る。plan-review の入力 `premises`）。README の 10 節の 9 は「入力は `purpose` だけ」を yes/no で縛るとしているので、このままだと独立設計が今持つ「実測した制約を所与にする」能力が落ちる。independent-design の port に `constraints` を足すか、落とすと決めるかを README で決める必要がある。
2. （解決済み）制約の行の形は共通の `blocks/.shared/schemas/constraints.schema.json` に 1 つ在り、premises はそれを使う。その形は `if`/`then` を持てないので、`実測` の行の `measured_output` は受け付けが照らす。ただし purpose の `steps.constraint_rows` は port の `constraints` にも `measured_output` を求めており、運ばれる行（`carry.carried_constraints`。`実測` で `measured_output` が無い）を拒む。purpose 側で直す必要があるかを確かめる。
3. 前提の実測が落ちた時に judge のまとめが止まる語 `works:premises`（今の `stopby.PREMISES`）を誰が持つか（judge のまとめの `src/` か `lib/stopby`）が README の 9 節に無い。`stopby` は KEEP（line・report・chain）なので、judge のまとめも読み手に足すのがよい。

## 10 未確認

- 起動の殻で `blocks/` を読ませる引数の名と、6 節の命令の正確な形（world.md と同じ）。土台の PR で `WORKS_FACTORY_FOLDER=blocks bin/works-factory workflow run works-factory-premises --cwd <対象> --input request=<値>` に決まった。
- 入力の `base_rev`（元の works）を工場が外した時の意図の記録（2.7）。
