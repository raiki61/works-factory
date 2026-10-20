# block の設計書: procedure-trace（手順トレース）

- 何の話か: 対象差分が変えた手順書・スクリプト・CI 定義を、読むだけでなく動かして確かめる素材の観点「手順トレース」を、単独で呼べる block `workflows/procedure-trace/` にする設計。素材の観点の族の 1 本で、族の共通の形は [materials.md](materials.md)、書き方の手本は [prior-decisions.md](prior-decisions.md) に従う。型は [README.md](README.md)。
- 決めたこと: 今の judge の `material-route` の 1 列と `procedure-trace-loop`（prep・役・accept）を、5 つの node（intake・prep・役・accept・finish）の block にする。入力は差分の根・判定から入る run の出どころ・言語の 3 つの port だけ。回すかは intake が対象差分の変更ファイルを今の `PROCEDURE_PATTERNS` に当てて決め、当たらなければ役を起こさずに今と同じ字の `not_applicable` を書く。指示は 1 本の英語の md（`prompts/procedure-trace.md`）にし、今は別のファイルに描いて役に Read させた材料を指示に直に入れる。所見の行（`findings`）は今と同じ形で `material.json` の `reply` に残り、判定役が今と同じ値を読む。振る舞いは変えない。
- 持ち主に求めること: なし。
- 読む人と使い方: この block を作る実装者（1〜3 節の名と順をそのまま作る）。素材の観点の残り 10 本と同じ PR に束ねてよい（README の 11.1 の 1 波目）。

この文書の語は README・materials.md・prior-decisions.md の頭の物を使う。ほかに:

- 手順トレースの役（procedure-trace）: 変更された手順書・スクリプト・CI 定義の全文を読み、初期状態から上から順に動かしたと仮定して前提の欠け・暗黙の環境状態・誤爆半径を確かめる AI の役。道具は Read・Grep・Glob・Bash・WebSearch・WebFetch。Bash は網の閉じた sandbox の中で走り、既にある計器（テスト一式・計器の台本）を動かせる。
- 手順のファイル: 変更ファイルのうち、`PROCEDURE_PATTERNS`（今の `lib/judge_accept.py:1303-1304`。`README`・`.md`・`.sh`・`scripts/`・`.github/workflows/`・`Makefile`・`Dockerfile`・`.yml`/`.yaml`・`commands/`・`hooks/`）のどれかに当たる物。
- 未実測: 実機で確かめられなかった箇所を、仮説として返す行（返答の `unmeasured`）。
- 例の run: 本物の run `53e71318-ac9f-4468-ae72-5f6ed569a667`（対象 <owner>/<repo>。置き場 `~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-…/judge/`）。差分の在る通常の run で、変更ファイル 23 件に手順のファイルが無く、この観点は回らなかった（`material-route.json` の `fill.procedure_trace` が `not_applicable`）。記録の在る 148 本の run のどれでも、この観点は一度も回っていない（どの `material-route.json` も `roles.procedure-trace.run` が偽）。骨組みの値は、この run の値に仮の変更ファイル 1 件を足して描いた（2.5。自分で決めた。7 節）。

## 1 block の全体

### 1.1 役

対象差分が手順のファイルに触れる run で、変更された手順書・スクリプト・CI 定義の全文を読み、状態を変えない範囲で動かして確かめる。確かめた所見（機構・実測・誤検出の見積もりつき）と、確かめられなかった箇所（未実測の仮説）を返す。手順のファイルに触れない run では役を起こさず、理由つきの `not_applicable` を機械が書く。機械が、作業ツリーを変えていないか・所見の場所がファイルに在るか・素材の欄が決まりに合うかで受け付ける。

### 1.2 port

入力（YAML の `inputs:`）: materials.md の 1.2 の共通の 3 つ（`base`・`entry`・`lang`）だけ。`lang` の説明は `text: 人に見せる欄（material の detail・checked・reason、findings の text・mechanism・measured・false_positive_if、unmeasured）の言語。空は依頼の言語`。

出力（`returns: finish`、`outcome_field: ok`）: materials.md の 1.2 の 5 欄だけ。`material.json` の `reply` は受けた返答（`material`・`findings`・`unmeasured`）、`materials` は `{"procedure_trace": <返答の material>}`。

今との違い: 今は差分の根と入口の印を `judge/start.json` から、変更ファイルを `judge/material-view.json` から名で開き、回すかを `material-route` の `procedure_trace_due`（`lib/judge_accept.py:1546-1569` の `_deep_due` が作る）が、回さない時の素材を diagnose-prep の `fill_materials` が `material-route.json` の `fill` から埋めた。受けた返答は `judge/material-procedure-trace.json` に書き、判定役の材料が `_diagnose_ctx`（`:2764-2777`）で `findings` を `record.process.procedure_findings` として読んだ。

### 1.3 node の並び（`workflows/procedure-trace/works-factory-procedure-trace.yaml`）

materials.md の 1.3 の雛形の `<観点>` を `procedure-trace` にした物。

1. `intake`（script `intake.py`）: port を読み、対象差分を取り、変更ファイルを手順のファイルに当てて回すかを決め、回すなら作業ツリーを写す。返り `{due, reason}`。
2. `procedure-trace-loop`（`loop_group`、最大 3 回、`fresh_context: false`、`until_bash: done=$procedure-trace-accept.output.done; test "$done" = true`、`when: $intake.output.due == true`）
   - `procedure-trace-prep`（script `role_prep.py`。`with:` を持たない）: 指示を組む。返り `{prompt}`。
   - `procedure-trace`（AI）。`prompt: "$procedure-trace-prep.output.prompt"`・`depends_on: [procedure-trace-prep]`。起こし方は今の `net_closed_launch`（`workflows/judge/works-factory-judge.yaml:464-480`）を字のまま展開する（prior-decisions.md の 1.3 と同じ字。注記 3 行も写す）。`retry: {max_attempts: 2, on_error: all}`。`mutates_checkout:` は今と同じく置かない。`output_format` は今のまま（2.4）。
   - `procedure-trace-accept`（script `role_accept.py`。`with: {reply: $procedure-trace.output}`）: 返り `{ok, done, reason}`。
3. `finish`（script `finish.py`。`depends_on: [intake, procedure-trace-loop]`・`trigger_rule: all_done`）: `material.json` を書き、出力を返す。どの段が落ちても落ちない。

### 1.4 place のファイル

materials.md の 1.4 の名だけ: `intake.json`・`view.json`・`diff.patch`・`changed-files.txt`・`tree.json`（回す時だけ）・`procedure-trace-prompt-<n>.md`・`rejects-procedure-trace.json`・`rejects-procedure-trace.md`・`accepted.json`・`material.json`。観点だけの控えは無い。

1 つ目の commit（11.4 の比べの間）だけ、`material-procedure-trace-brief.md`（今の材料のファイルと同じ字）も書く（2.9）。

### 1.5 コードの置き場

- `workflows/procedure-trace/src/__init__.py`（空）。
- `workflows/procedure-trace/src/viewpoint.py`: materials.md の 5.1 の宣言。中身:
  - `NAME = "procedure-trace"`
  - `MATERIALS = ("procedure_trace",)`
  - `GUARDED = False`（AI の node が `mutates_checkout: false` を持たない。今の accept の `with: {status_guarded: false, …}`。`workflows/judge/works-factory-judge.yaml:1458`）
  - `NA = "cond"`、`NA_REASON = "対象差分に手順書・スクリプト・CI 定義の変更が無い"`（今の `MATERIAL_NODES['p1.procedure_trace']['na_reason']`。`lib/judge_accept.py:1668-1673`）
  - `PROCEDURE_PATTERNS`: 今の `lib/judge_accept.py:1303-1304` の 10 個の正規表現を字のまま写す（名も同じ）。`lib/judge_accept.py` の元は、組み込みまで今の judge のために残す（materials.md の 1.5 の終わり）。
  - `procedure_files(view) -> list[str]`: `sorted({f for f in view.changed_files for p in PROCEDURE_PATTERNS if re.search(p, f)})`（今の `touches_procedures`、`:1393-1398` の中身）。
  - `applies(view, values)`: `hit = procedure_files(view)`、`materialkit.Due(bool(hit), f"差分に手順書・スクリプト・CI 定義が {len(hit)} 件" if hit else "差分に手順書・スクリプト・CI 定義が無い")`（今の `touches_procedures` の訳の字のまま）。
  - `due(view, values)`:
    1. `materialkit.is_entry_run(view, values)`（`entry` が在り、対象差分が空）なら `materialkit.entry_skip("手順の追跡")`（今の `_deep_due` の入口の枝の名詞。例の run とは別の判定から入る run `df5e111f-…` の `material-route.json` の `roles.procedure-trace.why` と同じ字になる）。
    2. `ok, why = applies(view, values)`。`ok` なら `Due(True, f"対象差分に手順書・スクリプト・CI 定義の変更が在る（{why}）——手順の追跡を回す")`、偽なら `Due(False, f"{NA_REASON}（{why}）——手順の追跡を起こさない")`。今の `_because` の字（「差分に手順書…があって初回の周、または前の周の P3 が何かを直した周——成り立たない（round=1・…・前の周の P3 が触ったファイルは 0 件）」）は使わない（自分で決めた。7 節）。
  - `fill(view, values, due)`: いつも `{"procedure_trace": materialkit.fill_na(NA_REASON, applies(view, values).why)}`。回さないのは、手順のファイルに触れない時と、判定から入る run の周（差分が空）の時で、後者も差分が空なので触れない文が入る（今の `_fill_one`〔`:1934-1950`〕が入口の run でも条件外の文を入れるのと同じ結果）。`fill_entry` の枝は置かない（7.1）。
  - `judged_na(view, values)`: `return False`。
  - `values(view, values)`: `own, theirs = materialkit.review_md_paths(view.repo)` として `{"repo": str(view.repo), "diff_file": view.diff_file, "changed_files": dump(list(view.changed_files)), "review_md": own}`、`"repo_review_md": theirs` も、対象の `REVIEW.md` が無く空の字の時も渡す（指示を組む口は選ばれない段落の中の差し込み口にも値を要る。7.1）。`dump` は materials.md の 3.3。
  - `when(view, values)`: `{"spawns": False, "repo_review": bool(theirs)}`（`theirs` は上と同じ値）。
  - `before(view, values, reply, place)`: `return None, reply, False`。
  - `after(view, values, reply, place)`: `return None`（今の `MATERIAL_NODES` にこの観点の `post_check` は無い）。
  - `after_accept(reply, place)`: 何もしない。
  - `materials_of(reply)`: `{"procedure_trace": reply["material"]} if isinstance(reply.get("material"), dict) else {}`（今の `writes` の `materials.procedure_trace ← material`）。
  - `report_lines(doc)`: `reply` が null なら `[]`。ほかは `findings` の行ごとに `f"  - 所見: {oneline(where)}: {oneline(text)}"`、続けて `unmeasured` の行ごとに `f"  - 未実測: {oneline(行)}"`（自分で決めた。7 節）。
- `workflows/procedure-trace/src/oldbrief.py`（1 つ目の commit だけ。2.9）: 今の材料のファイルを同じ字で組む `brief(view, values) -> str`。
- `schemas/` は置かない（json の入力が無い）。
- 使う `lib/`: `materialkit`・`rolekit`・`oneline`。

### 1.6 つなぎ方（graph の側。block には書かない）

- 判定のまとめ（`workflows/judge/`）: `include: works-factory-procedure-trace`、`depends_on` は materials.md の 1.6。`with:` は `base: <line が始めの記録から引いた diff_base>`・`entry: <line が始めの記録から引いた出どころの文。判定から入る run でなければ空>`・`lang: <始めの記録の lang>`。
- 読み手: diagnose の `materials`（11 本の `material` の配列の 1 つ）。
  - 素材 `procedure_trace` は `materialkit.assemble` で 15 欄の 1 つになる（今の `fill_materials` と同じ）。
  - 所見の行: 今の判定役の材料は `findings` を「手順トレース: {{?record.process.procedure_findings}}」（`lib/judge_accept.py:2717` の `DIAGNOSE_EXCERPT`、値は `:2777`）で読む。新しい形では diagnose が `materialkit.read` で開いた `material.json` の `reply.findings` を同じ欄に入れる（読み方は diagnose の設計書が決める。この block は `reply` を今の返答のまま置くだけ）。
  - `unmeasured` は今どの読み手にも届いていない（`_diagnose_ctx` は返答の全部を `out.p1.procedure_trace` に入れるが、`DIAGNOSE_EXCERPT` に穴が無い。graphloops の `writes` にも無い）。新しい形でも `reply` に在るだけで、届けるかは diagnose の設計書が決める。この block の `report` の行には出す（1.5）。

## 2 node の設計シート: procedure-trace（手順トレースの役）

### 2.1 役

対象差分が変えた手順書・スクリプト・CI 定義の全文を読み、初期状態から逐次に動かしたと仮定して確かめ、所見・未実測の仮説・素材の状態を返す。

### 2.2 port

`intake.json` の `view`（← port `base` と作業ツリー。`repo`・`diff_file`・`changed_files`）・`values.lang`（← port `lang`）、観点の正本のパス（← `materialkit.review_md_paths(view.repo)`）、拒否の控え（← accept が place に積んだ `rejects-procedure-trace.json`）。

### 2.3 組み立ての順（`prompts/procedure-trace.md`）

materials.md の 3.1 の並び。

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: `rejects-procedure-trace.json` に拒否が 1 件以上。`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "procedure-trace"))`。
2. `{shared:role-investigator}`。
3. （置かない。外への検索の決まりは `{shared:role-investigator}` の中から入る。段落 `spawns` の真偽は `false` を渡す）
4. 役の 1 段落（決まった文）: 手順トレースだけをすること・局所の所見もほかの素材も渡していないこと。
5. 道具の段落（決まった文）、`{shared:works-gh}`、`{shared:material-readonly}`。
6. `## Materials` と差し込み口: `{repo}` ← `view.repo`、`{diff_file}` ← `view.diff_file`（Read を持つ役なのでパス）、`{changed_files}` ← `view.changed_files`（JSON の配列の字）、`{review_md}` ← `review_md_paths` の 1 つ目。`<!-- if repo_review -->` `{repo_review_md}` ← 2 つ目 `<!-- end repo_review -->` — 条件: 対象の根に `REVIEW.md` が在る。
7. `## What to do`（決まった文）: 今の md の「元の graphloops の指示書」の段（`material-procedure-trace.md:46-53`）を英語にした物。
8. `{shared:material-status}`。
9. `## Whether you may write not_applicable` と `{shared:material-na}` — 扱いは `cond`。役が起きる時は当たる条件がいつも真なので、`na_cond_true` が真で `{na_why}` ← `applies` の訳（例「差分に手順書・スクリプト・CI 定義が 1 件」）。`na_cond_false` の段落は、回す条件と当たる条件が同じ事実なので block の中では入らない（族の扱いを変えないため、宣言はそのまま `cond` にする）。
10. `## Where to point` と `{shared:material-where}`（前置きは無い。`findings` の行は `where` と `text` を持つので、受け付けが照らす）。
11. 言語の 1 文と `{lang}`。
12. 結びの 1 文。

md の本文（英語。この block の 2 つ目の commit でこのまま置く）:

```markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{shared:role-investigator}

You are the procedure-trace role. Your only job is to trace the procedures that the target diff changes: confirm them by running, not only by reading. You are given neither the local findings nor any other material.

Your tools are Read, Grep, Glob, Bash, WebSearch, and WebFetch. Bash runs inside a sandbox, and its network is closed: it cannot reach any destination.

{shared:works-gh}

{shared:material-readonly}

## Materials

- Repository: {repo}
- Target diff (Read it): {diff_file}
- Files the target diff touches: {changed_files}
- Review guide (Read it; it defines the labels and the viewpoints): {review_md}
<!-- if repo_review -->
- The target's own review guide (Read it as well): {repo_review_md}
<!-- end repo_review -->

## What to do

Confirm by running rather than by reading (the principle in the section 「検証の原理」 of the review guide). Follow the section 「手順トレース観点」 of the review guide: execution step by step from the initial state, implicit environment state, and blast radius.

Read the full text of every changed procedure document, script, and CI definition, then follow that viewpoint. You forbid yourself any run that changes state, so return each place you could not confirm on a real machine in `unmeasured`, as a hypothesis marked "unmeasured".

- Where the OS sandbox is available, your Bash runs inside it and can run the instruments that already exist (the test suite, instrument scripts). The OS stops writes to the working tree, to `.git`, and to other working trees, and stops outbound traffic; only the temporary directory (the one the TMPDIR environment variable names) is writable. Runs that fetch and install packages (for example `uv run --with` or `pip install`) stop because there is no network; run things with the tools already installed.
- Read GitHub only through `works-gh` in the form described above. Issues and searches do not pass even through `works-gh`; read them with WebFetch and WebSearch.
- Where the sandbox is not available, only the built-in read-only commands (`git log`, `git diff`, and the like) and the read-only forms of `works-gh` pass, and running instruments is refused by permissions. For each place you were refused or stopped and could not confirm, return it as unmeasured, with the command you ran and how it was refused. Do not respell a command to get it through.
- Submit a finding only when it meets the standard in the section 「指摘の提出基準」 of the review guide: the mechanism (one sentence on the causal chain in the code), the measurement (run what can be run; if you cannot, say "unmeasured" and present it as a hypothesis), self-refutation before submitting (if you cite a rule, check that its condition applies and read the surrounding reality; submit only the findings you could not kill), and an estimate of false positives (one line on when the finding would be wrong).
- Do not create files yourself, not even inside the temporary directory. "Only the temporary directory is writable" means that the OS leaves a place where the instruments you run (the test suite and the like) can put their temporary files; it does not allow you to write.

{shared:material-status}

## Whether you may write not_applicable

{shared:material-na}

## Where to point

{shared:material-where}

Write `material.detail`, `material.checked`, `material.reason`, the `text`, `mechanism`, `measured`, and `false_positive_if` of each `findings` row, and the entries of `unmeasured` in {lang}. Keep keys, enum values, identifiers, paths, commands, and quoted text as they are.

Return only JSON that matches the output schema.
```

md の中に、`$` の直後に英字か `{` が続く字は無い（今の md の `$TMPDIR` は「the temporary directory (the one the TMPDIR environment variable names)」に言い換えた。materials.md の 3.1 の終わり）。REVIEW.md の節の名（「検証の原理」「手順トレース観点」「指摘の提出基準」）は、引いた字なので日本語のまま置く（正本の `lib/REVIEW.md:22`・`:29`・`:109` の見出しの字）。

言語・会話・`{` の扱いは prior-decisions.md の 2.3 の終わりと同じ。

### 2.4 返す形

今の `output_format` のまま（`workflows/judge/works-factory-judge.yaml:1420-1452`）:

- `material`: prior-decisions.md の 2.4 と同じ形。
- `findings`: `[{where, text, mechanism?, measured?, false_positive_if?}]`・各行 `additionalProperties: false`・`required: [where, text]`。
- `unmeasured`: 字の配列（未実測の仮説）。
- 全体 `additionalProperties: false`・`required: [material, findings, unmeasured]`。

人に見せる欄は `material.detail`・`material.checked`・`material.reason`・`findings` の `text`・`mechanism`・`measured`・`false_positive_if`・`unmeasured`（判定の材料と報告に載る）で、言語は `{lang}`。`where` は場所の名指しなので字のまま。

### 2.5 描いた骨組み（例の run の値に、仮の変更ファイル 1 件を足した物）

この観点は記録の在るどの run でも回っていないので、今の指示の 2 か所（`workflows/judge/commands/material-procedure-trace.md`〔62 行〕と、`material_prep` が描くはずの `judge/material-procedure-trace-brief.md`）は本物の run の物が無い。例の run `53e71318-…` の値（リポジトリ・観点の正本・対象の `REVIEW.md`・変更ファイル 23 件）に、仮に `README.md` の変更を 1 件足した値で描いた（自分で決めた。7 節）。

```markdown
{shared:role-investigator の本文: This role is an investigator. It investigates and brings things back; …}

You are the procedure-trace role. …（決まった文）

Your tools are Read, Grep, Glob, Bash, WebSearch, and WebFetch. …

{shared:works-gh の本文: To read GitHub pull requests and repositories, run the read-only command `works-gh` …}

{shared:material-readonly の本文: Do not change a single character of the target's working tree, …}

## Materials

- Repository: ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/worktrees/archon/task-works-factory-line-1792307529854
- Target diff (Read it): ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-ac9f-4468-ae72-5f6ed569a667/judge/procedure-trace/diff.patch
- Files the target diff touches: [
 "README.md",
 "backend/app/api/model/schemas.py",
 …（例の run の変更ファイル 23 件のまま）
 "frontend/messages/ja.json"
]
- Review guide (Read it; it defines the labels and the viewpoints): ~/.cache/works-factory-plugin/56032b5a88e2add0e1bda0949986271e1f649ea6/lib/REVIEW.md
- The target's own review guide (Read it as well): ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/worktrees/archon/task-works-factory-line-1792307529854/REVIEW.md

## What to do

Confirm by running rather than by reading …（決まった文と箇条 5 つ）

{shared:material-status の本文: How to write `material`: `status` is one of the following. …}

## Whether you may write not_applicable

The condition of this viewpoint holds for this run (差分に手順書・スクリプト・CI 定義が 1 件), so the acceptance step rejects `not_applicable`. …

## Where to point

Write the `<path>:<line>` of a location (`where`) as a line number in the current file in the working tree. …

Write `material.detail`, …, and the entries of `unmeasured` in the language of the request (the user's language). …

Return only JSON that matches the output schema.
```

`Target diff` のパスは、判定のまとめの include の id を `judge`・`procedure-trace` と置いた時の新しい place（materials.md の 1.4）。例の run の対象の根には `REVIEW.md` が在る（例の run の consistency-bypass の材料のファイルの「## 材料: inputs.repo_review_md」に同じパス）ので `repo_review` の段落が入る。拒否の控えが無いので却下の段落は入らない。

回さない道（例の run の本物の値）: 変更ファイル 23 件に手順のファイルが無いので `intake` の `due` が偽、`finish` の `status` が `skipped`、`reason` が「対象差分に手順書・スクリプト・CI 定義の変更が無い（差分に手順書・スクリプト・CI 定義が無い）——手順の追跡を起こさない」、`material.json` の `materials.procedure_trace` が `{"status": "not_applicable", "reason": "対象差分に手順書・スクリプト・CI 定義の変更が無い（差分に手順書・スクリプト・CI 定義が無い）"}`（例の run の `material-route.json` の `fill.procedure_trace` と同じ字）。

### 2.6 今の指示との差

今の指示は `workflows/judge/commands/material-procedure-trace.md`（62 行）と、`lib/judge_accept.py` の `material_prep`（`:2116-2135`）が描く材料のファイルの 2 か所に在る。prior-decisions.md の 2.6 と同じ移し方（材料の節 → `## Materials`、『条件に当たらない』の節 → `{shared:material-na}`、却下の段落の 2 回 → `{shared:rejected}` の 1 回、役の定義 → `{shared:role-investigator}` と `{shared:query-rule}`、works-gh の段 → `{shared:works-gh}`、作業ツリーを変えるな → `{shared:material-readonly}`、素材の書き方 → `{shared:material-status}`、所見の場所 → `{shared:material-where}`、言語の 1 行 → md の 1 文、graphloops のノードの名指しと区切りを消した）。この観点だけの差:

- 移した: 観点の正本の行（md:40。`$procedure-trace-prep.output.review_md` と `.repo_review_md`）を `## Materials` の 2 行に。対象の `REVIEW.md` が無い時に今は空のパス（「対象リポジトリ側: ``」）が入っていたのを、段落ごと入れない形（`repo_review`）にした。今の穴（`MATERIAL_HOLES['procedure-trace']`）は `?inputs.repo_review_md` を持たず、対象の側のパスは md の頭の行だけが渡していた。値の出どころは変わらない（`review_md_paths`）。
- 移した: md:49 の観点の正本の注（「手順トレース観点」——初期状態からの逐次実行・暗黙の環境状態・誤爆半径）を `## What to do` の頭の文に。
- まとめた: md:51 の GitHub を読む口の文（「GitHub を読む口は上の手順 3 のとおりで…issue と検索は `works-gh` でも通らない」。#221）を、`{shared:works-gh}` を指す 1 箇条に。sandbox の外へ出る形の説明は断片が言うので繰り返さない。issue と検索の 1 文だけ残した（断片の「Read issues, searches, and web pages with WebFetch and WebSearch」と同じ意味だが、手順トレースの役は「打てば通る」と試しがちな所なので、今の md が 2 回言っていた物を 1 回残す）。
- 言い換えた: `$TMPDIR`（md:51・md:53）を「the temporary directory (the one the TMPDIR environment variable names)」に。Archon が `prompt:` の値の中の `$…` を置き換え直すため（materials.md の 3.1 の終わり）。
- まとめた: md:53 の「ファイルの作成・編集・削除を自らに禁じる」は、役の定義の Bash の箇条と `{shared:material-readonly}` が言うので消し、続く「$TMPDIR の中も同じで…書くことを許すものではない」（#221 の足し）だけを箇条に残した。
- 移した: md:52 の指摘の提出基準を箇条 1 つに（字の中身は同じ）。
- 消した: md:34 の手順 1 の「書いてよいとあり、差分が当たらないと判じたなら not_applicable で返してよい。書いてよいとない時は…手順を続けよ」。扱いの文は `{shared:material-na}` が回ごとに 1 つだけ入れる。
- 変えた: 断片 `material-where` の尾の文を、受け付けが照らす範囲（`where` と `text` を持つ行だけ。ほかの行は照らさない）に合わせて狭めた。
- 英語にした（#764）。役の名「手順トレースの役」は "the procedure-trace role"。

### 2.7 元の works と graphloops の同じ場面

族の形の差は materials.md の 9 節。この観点だけの差:

- 元の works の `works/blk-material/commands/procedure-trace.md`（7 行）は、engine が描いた graphloops の指示書のファイル（`prompt_file`）を Read で読ませる薄い md だった。工場は graphloops の指示書を md の中に写し、値だけを材料のファイルにした（#76）。新しい形は値も指示の中に入れる。
- 元の graphloops の指示書（元の works の写し `works/.shared/core/gl-prompts/prompts/review-loop/p1.procedure_trace.md`）の GitHub の文は「gh は読むだけの物（issue・pr の list と view・pr diff・search・repo view）を単独で打てば sandbox の外で通る」だった。工場は読むだけの口 `works-gh`（pr list・pr view・pr diff・repo view だけ）に替え、issue と検索を WebFetch・WebSearch に回した（#221）。この block も工場の形を持つ。
- 工場が足した物: 一時ディレクトリに役が自分で書かない、の 1 文（#221）。この block も持つ。
- graphloops の今の指示書（`~/src/claude-plugins/graphloops/prompts/review-loop/p1.procedure_trace.md`）は元の works の写しと字の言い回しだけが違う。graphloops の今の graph（`graphs/review-loop.json` の `p1.procedure_trace`）は、元の works の写しより後の 0.23.0（`921fe1b7`、2026-09-28）で 2 つを足した: 読む値に方針のパスと検査の宣言（`record.process.policy.path`・`record.process.checks`）と依頼（`inputs.request`）、指示の尾に「依頼の守ること」（`prompts/review-loop/request-scope.md`。テスト一式や検査を走らせる前に依頼の本文の守ることを読み、手元で回さないと書かれた物は回すな）。元の works にも工場にも無い（（未確認）: 工場の履歴に外した記録は無い。写した版がこの足しより前だった）。振る舞いを変える足しなので、この作り直しには入れず、後に別に扱う。
- graphloops は節ごとに新しい会話で起こす（`fresh_context: true`）。工場は拒まれた後も同じ会話で出し直す（`fresh_context: false`。#571）。この block も工場の形。
- 返答の型（`material`・`findings`・`unmeasured`）と書き先（素材と `process.procedure_findings`）は、元の works・graphloops・工場で同じ。`unmeasured` はどれでも書き先を持たない。
- 受け付け: この観点に `post_check` は無い（graphloops の `MATERIAL_NODES` も持たない）。当たる条件 `touches_procedures` と `na_reason` は 3 つで同じ字。

この block が両方より良く、残す物: 作業ツリーを機械が照らす（役が計器を動かすので、役の自制の外の担保が要る）・所見の場所の行を照らす・`works-gh` の口だけを網の外に出す。

### 2.8 受け付け

materials.md の 4 節の順のまま。観点の前の照らしと後の照らしは無い。

- 拒む物: JSON のオブジェクトでない返答・役が作業ツリーを変えた（`GUARDED` が偽なので `porcelain` を含む `TREE_KEYS` の全部。計器が作業ツリーに試験の控えを書いた時も当たる。今の `test_test_caches_count_like_any_change` の振る舞い）・`findings` の行の `where` の行がファイルに無い・素材 `procedure_trace` が無い・`carried_over`・`not_applicable`（`cond_true`。役が起きる時はいつも当たる条件が真）・知らない status・status ごとの要る欄の欠け。
- 3 回目の拒否でループを抜け、`finish` が `status: gave_up`・素材 `procedure_trace` に `not_run` と訳を書く（materials.md の 2.10 の 4）。所見の場所の外れは、3 回目の回だけ拒まずに、外れた行の `where` の尾に印 `materialkit.LOCATION_MARK`（「（works の受け付け: この行はファイルに無い——差分の行番号の疑い）」）を付けて受ける（materials.md の 2.5）。

### 2.9 試験

- standalone の fixture（`workflows/procedure-trace/fixtures/`）:
  - `standalone.stubs.yaml`: `fixture.inputs` は `base: "HEAD~1"`・`entry: ""`・`lang: ""`。fixture の木（`tests/archon.py` の `blocks_tree` が置く木）は、対象の入口のファイル（`README.md`・`AGENTS.md`）を 2 つ目の commit に置くので、`HEAD~1` から作業ツリーまでの差分に手順のファイル（`README.md`）が入る。`intake` の `due` が真になり、AI の node `procedure-trace` を起こす道を通り（`reached` に `procedure-trace-prep`・`procedure-trace`・`procedure-trace-accept`・`finish`）、役の返答は差し替えで `clean`。指示が md から組まれたことを md の決まった文で照らす。回さない道（`status: skipped`）は `tests/blocks/procedure_trace` の試験が見る。
  - `skipped.stubs.yaml` は置かない（`standalone.stubs.yaml` がその道。materials.md の 8 節の「回す条件を持つ観点は skipped」を満たす）。
  - `gave-up.stubs.yaml`: 入力は standalone と同じ（`base: "HEAD~1"`）。役の返答が受け付けを通らない（手順のファイルに触れる run で `not_applicable`）道。筋書きでは輪が 1 周で終わるので、3 回で諦めて `status: gave_up` を返す数えは、下の子のプロセスの試験が見る。
- `tests/blocks/procedure_trace/test_procedure_trace.py`: materials.md の 8 節の block の試験（使い捨ての `ARTIFACTS_DIR` と git のリポジトリ、port の値だけ）。
  - 写す元 `lib/tests/test_judge_accept.py::MaterialCase.test_procedure_trace_reply_is_taken_or_refused`: 作業ツリーに `run.sh` を足した木で回し、`not_applicable` の返答は拒まれる（`cond_true`）。見た返答（`clean`）は受け、`material.json` の `materials` が `{"procedure_trace": <返答の material>}`。今の試験の「条件が偽なら not_applicable を受ける」の枝は、block では役が起きないので、`intake` が `due` 偽で `not_applicable` を機械が書く照らしに替える。
  - 写す元 `DueCase.test_procedure_trace_needs_procedure_files`: 変更ファイルが `src/a.txt` だけなら `due` が偽で、`finish` の `status` が `skipped`・素材の `reason` が `fill_na` の字。
  - 写す元 `DueCase.test_run_with_a_diff_runs_them` の procedure-trace の部分と `test_na_note_for_each_kind_of_node` の procedure-trace の 2 行: `run.sh` を足した木で `due` が真、組んだ指示に `na_cond_true` の段落と `{na_why}` の字「差分に手順書・スクリプト・CI 定義が 1 件」が在り、`na_cond_false` の段落が無い。
  - 写す元 `DueCase.test_empty_diff_run_with_requests_runs_only_prior_decisions` の procedure-trace の部分: `entry` が在り差分が空なら `due` が偽で、`finish` の `reason` が `entry_skip("手順の追跡")` の字、素材が条件外の `not_applicable`（入口の文でない。1.5 の `fill`）。
  - 足す: `entry` が在っても対象差分が在れば回す（`due` が真）。
  - 足す: 対象の根に `REVIEW.md` が在れば `repo_review` の段落が入り、無ければ入らない（値 `repo_review_md` も渡さない）。
  - 足す: 拒まれる返答 3 回で `gave_up`（`run.sh` を足した木で）。
  - 足す（起こし方の照らし）: block の YAML の AI の node の `model`・`allowed_tools`・`sandbox`・`idle_timeout`・`retry` が、今の `tests/workflows/test_judge.py:94` の表の procedure-trace の行（`"sonnet", "medium", INVESTIGATE, CLOSED, False, …`）が照らす物と同じ。
- `tests/blocks/procedure_trace/test_viewpoint.py`: materials.md の 8 節の物に、`PROCEDURE_PATTERNS` が `lib/judge_accept.PROCEDURE_PATTERNS` と同じ字（組み込みまで 2 つ在るので、ずれを照らす。組み込みで lib の側が消える時にこの照らしを消す）を足す。
- 指示の比べ（README の 11.4）: `tests/blocks/procedure_trace/test_prompts.py`。prior-decisions.md の 2.9 と同じ 2 つの commit の形。1 つ目の commit の値の口は `lang_line`・`reason`・`brief_file`・`review_md`・`repo_review_md`（今の md が `$procedure-trace-prep.output.<欄>` で読む 5 つ）。値は 2.5 の仮の値（例の run の値に `README.md` を足した物）で、今の `material_prep` が同じ値で描く材料のファイルと `oldbrief.brief` の字が同じことを照らす（本物の run の材料のファイルが無いので、今のコードで描いた字と比べる。自分で決めた。7 節）。
- 守る keep-essence の番号: 無い。守るのは「手順のファイルに触れない run で役を起こさず、理由つきの `not_applicable` を書く」と「計器を動かした役の作業ツリーの変化を拒む」で、上の試験が見る。
- 終わりの条件の命令: materials.md の 8 節の 4 行の `<観点の package の名>` を `procedure_trace` にした物。

## 3 script の node

materials.md の 6 節の雛形のまま。`intake.py` が読む入力は `INPUTS_BASE`・`INPUTS_ENTRY`・`INPUTS_LANG` の 3 つで、どれも `ports.text(…)`。値の dict の鍵は `base`・`entry`・`lang`。1 つ目の commit だけ、`role_prep.py` が `src.oldbrief.brief(view, values)` を place の `material-procedure-trace-brief.md` に書いてから組む。

## 4 受け付けの文

materials.md の 2.8 と 4 節の文だけを使う。この観点が足す拒みの文は無い。

## 5 単独で呼ぶ

```sh
bin/works-factory workflow run works-factory-procedure-trace \
  --input base=origin/main
```

作業ツリーは Archon の cwd。差分（`base` から作業ツリーの今の姿まで）が手順のファイルに触れなければ、役を起こさず `status: skipped` で返る。始めの記録は要らない。

## 6 未確認

- prior-decisions.md の 6 節の 2 つ（役の定義の断片の名・起動の殻の引数）。
- 他の観点の block の fixture も、`blocks_tree` の 2 つ目の commit に置いた対象の入口のファイルで `base: HEAD~1` を使えるか（この block の試験は通した。ほかは各 block の設計書が見る）。
- `materialkit.review_md_paths` の引数（materials.md の 5.2 の終わりは `(repo)`、写す元 `lib/judge_accept.py:1765` は `(lib_dir, repo)`）。この block は `(view.repo)` で呼ぶと書いた。

## 7 自分で決めた事（この block だけ）

- 回す時と回さない時の `Due` の訳を、今の `_because` の字（「…初回の周、または前の周の P3 が何かを直した周——成り立つ（round=1・…・前の周の P3 が触ったファイルは 0 件）」）でなく、当たる条件の事実だけの字にする。訳: 1 run = 1 周（持ち主の決め carry）で、前の周の枝はいつも効かない。効かない枝の名を人に見せる `reason` に残すと、読む人が「前の周」が在ると取り違える。prior-decisions.md の 1.5 の `due` も同じ決め方。判定役に届く素材の字（`fill_na` の字）は今と同じにした（例の run の `fill.procedure_trace` と同じ）ので、判定の材料は変わらない。入口の訳は族の `entry_skip` の字で、今の字と同じ。
- `fill` で当たる条件を入口より先に見る。訳: 今の `_fill_one` は、入口の印を外しても条件が真の時だけ入口の文を選ぶ。手順トレースでは「入口でなくても回った」とは「手順のファイルに触れる」ことなので、当たる条件を先に見ると同じ結果になる。判定から入る run の差分は空なので、今も入口の run では条件外の文が入っている（判定から入る run `df5e111f-…` の `fill.procedure_trace`）。
- `report_lines` に所見と未実測の行を足す。訳: 判定役の材料に届かない `unmeasured` を、少なくとも報告の素材の節で人が見られるようにする（1.6）。報告に載せるかは line と report の配線の決め（materials.md の 1.6）なので、行を返すだけにする。
- 2.5 の骨組みと 1 つ目の commit の比べの値を、例の run の値に仮の変更ファイル `README.md` を足した物にする。訳: 記録の在る 148 本の run のどれでもこの観点は回っておらず、本物の指示の字が無い。例の run は材料の値（リポジトリ・観点の正本・対象の `REVIEW.md`）が全部そろった run で、手順のファイルを 1 件足すだけで回す条件が真になる。`README.md` は `PROCEDURE_PATTERNS` の頭の型に当たる、いちばん多い手順書の名。
- fixture は `base: HEAD~1` で、対象の入口のファイルを 2 つ目の commit に置いた木（`blocks_tree`）の差分を対象にし、役を起こす道を通す。回さない道と諦める数えは子のプロセスの試験に置く。訳: fixture の入力は port の値だけ（README の 7.1 の 4）なので、作業ツリーの変更は作れないが、他の条件つきの観点と同じく `base` で差分は作れる。
- 試験のフォルダの名を `tests/blocks/procedure_trace/` にする（materials.md の 10 節と同じ訳）。

### 7.1 実装で決めた事（main の決まりに合わせた所）

- md に `{shared:query-rule}` を置かず、役の 1 段落の「started in a new conversation」を外した。訳: 役の定義の断片が中に `query-rule` を持つ（prior-decisions と同じ。materials.md の 10.1）。輪は `fresh_context: false` で、2 回目からは同じ会話を続けるので、「新しい会話」と書くと嘘になる。役の node は prep だけに依り（直前の層は 1 node）、会話が切れない。
- `values` は `repo_review_md` を、対象の `REVIEW.md` が無い時も空の字で渡す。訳: 指示を組む口は選ばれない段落の中の差し込み口にも値を要る（materials.md の 10.1 の `rejection`・`na_why` と同じ）。
- 判定から入る run の周は `materialkit.is_entry_run`（`entry` が在り、対象差分が空）で決める。`entry` が在っても差分が在れば回す。訳: 今の `request_entry` は差分の事実で決め、族の部品も同じ（prior-decisions の 10.1）。差分が空なら手順のファイルは無いので、`fill` はいつも `fill_na`（条件外の字）になる。`fill_entry` の枝は到達しないので置かない。1.5 の `due` の 1 と `fill` の `fill_entry` の枝、2.9 の「`entry` ありで `run.sh` の変更も在れば `fill_entry`」の試験は、この決めで置き換えた（`entry` ありで差分が在れば回す、の試験）。
- 筋書きの木（`blocks_tree`）は、対象の入口のファイルを 2 つ目の commit に置き、筋書きが `base: HEAD~1` を渡して手順のファイルに触れる差分を作る。port `base` を、この block だけ広げることはしない（共有の入力の意味を変えない）。訳: 形の検査 `check_standalone_renders` は、どの AI の node も `exec-code: true` の筋書きで起こして md の決まった文を照らすことを求める。2.9 の standalone と gave-up の筋書きがこれで役を起こす道を通る。
- `test_viewpoint` の例の run の値を、実機の run が無いので、今の `material_prep` を同じ値で動かした字との比べにした（1 つ目の commit の `test_prompts`）。
