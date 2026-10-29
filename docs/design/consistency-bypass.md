# block の設計書: consistency-bypass（整合性と標準機構の迂回）

- 何の話か: 対象差分がリポジトリの近傍の機構と食い違っていないか（整合性）と、近傍が使う標準の機構を迂回していないか（迂回）を、互いに独立に見る素材の観点を、単独で呼べる block `workflows/consistency-bypass/` にする設計。素材の観点の族の 1 本で、族の共通の形は [materials.md](materials.md)、写す手本は [prior-decisions.md](prior-decisions.md)。型は [README.md](README.md)。
- 決めたこと: 今の judge の `material-route` の 1 列と `consistency-bypass-loop`（prep・役・accept）を、5 つの node（intake・prep・役・accept・finish）の block にする。入力は族の共通の 3 つ（`base`・`entry`・`lang`）だけ。1 つの観点が素材を 2 つ（`consistency`・`bypass`）書き、所見の行も 2 系統（`findings`・`bypass_findings`）返す。指示は 1 本の英語の md（`prompts/consistency-bypass.md`）にし、今は材料のファイル（`material-consistency-bypass-brief.md`）に描いて Read させた値を指示に直に入れる。対象リポジトリの REVIEW.md が無い run では、その行を段落ごと入れない。振る舞いは変えない。
- 持ち主に求めること: なし。
- 読む人と使い方: この block を作る実装者（1〜4 節の名と順をそのまま作る）。materials.md と並べて読む前提で、共通の形はこの文書に繰り返さない。族の共通の部品（`lib/materialkit.py`）と 1 本目の観点 prior-decisions の PR の後に作る、残り 10 本の PR の 1 つ（README の 11.1 の 1 波目。急ぎの度合いはその順で決まり、期限は無い）。

この文書の語は README・materials.md・prior-decisions.md の頭の物を使う。よく出る物だけ、ここでも短く書く:

- 素材: 判定の役が読む 15 の欄の 1 つで、値は状態 `{status, count?, detail?, checked?, reason?}`。この観点は `consistency` と `bypass` の 2 つを書く（materials.md の頭）。
- 判定から入る run と `entry`: 差分が空で、人の修正の依頼だけで始まる run。工場の本線の workflow（line。この観点の block を include でつなぐ側）が、run の始めにそう決めた時だけ、依頼の出どころの文（例「人の依頼（/path/req.json）」）を port `entry` に入れる。`entry` が在り、かつ対象差分が空なら、この観点の役は起こさず、機械が 2 つの素材に理由つきの `not_applicable` を書く（役の返答の受け付けは通らない）。単独で呼ぶ時も、`entry` に字を入れればこの道を通る（5 節）。
- P1 の役: 元の graphloops の段の名で、修正の前に差分を見る素材の観点（prior-decisions と purpose-review の 2 本〔P0〕のほかの 9 本）。今のコードの名 `p1.consistency_bypass` はこの段の節の名。
- 穴: 今の指示の md が持つ「［材料: 〜］」の差し込み所（`MATERIAL_HOLES`）。新しい形の `{name}` の差し込み口に当たる。
- 作業ツリーの照らしと `GUARDED`: 受け付け（accept の script）が、役を起こす前に写した作業ツリーの姿（`tree.json`）と今の姿を比べ、違えば拒む。`GUARDED` は観点の宣言の 1 つで、AI の node が `mutates_checkout: false` を持つ時に真。その時は Archon 自身も node の前後の `git status --porcelain` を照らすので、受け付けは比べる欄からその 1 つ（`porcelain`）だけを外し、HEAD・枝・git が無視するファイルなどの残りの欄で比べる（materials.md の 5.1・4 節の 2）。
- `{shared:<名>}`: 2 つ以上の block が使う指示の断片（`workflows/.shared/prompts/<名>.md`）を差し込む記法。この文書が使う断片の本文は materials.md の 3.2 と土台の PR が置く（README の 5.1）。
- diagnose: 素材を全部読んで根本を診断する判定の役の block（README の 8.1）。この観点の出力の読み手。
- `#76`・`#221`・`#764`: このリポジトリの PR と issue（judge を作った PR・指示の書き直しの PR・指示を英語にする issue）。

- 整合性と迂回の役（consistency-bypass）: 対象差分と、その依存先・近傍・呼び元を読み、リポジトリ横断の整合性と、標準の機構の迂回を独立に見る AI の役。道具は Read・Grep・Glob だけ（Bash も web も無い）。ほかの役の所見を受けない。
- 固めた版: intake が対象差分を取る時に、作業ツリーの今の姿（未追跡のファイルも入る）を固めた commit（`View.review_rev`）。今の「読む版」（`inputs.review_rev`）と同じ物。
- 観点の正本: 工場の `lib/REVIEW.md`（日本語）と、対象のリポジトリの根の `REVIEW.md`（在れば）。値は `materialkit.review_md_paths(repo)`（materials.md の 5.2 の終わり）。
- 例の run: 本物の run `53e71318-ac9f-4468-ae72-5f6ed569a667`（対象 <owner>/<repo>。置き場 `~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-…/judge/`）。差分の在る run（変更ファイル 23 件）で、役は 1 回目で受け付けを通った（`material-consistency-bypass.json` の `consistency.status` が `found`〔1 件〕、`bypass.status` が `clean`、`findings` 1 行・`bypass_findings` 0 行）。拒否の控え `rejects-consistency-bypass.json` は無い。骨組みの値はここから取った。同じ対象の run `17ee8ecc-717a-4dc7-92b6-25ecd08fa15b` も同じ形。

## 1 block の全体

### 1.1 役

対象差分を起点に、依存先・近傍・呼び元まで読み、(1) リポジトリ横断の整合性（宣言と使用・界面の追従・近傍の規約との食い違い）と、(2) 近傍が実際に使っている標準の機構の迂回を、互いに独立に見て、2 つの素材の状態と 2 系統の所見の行と、見た範囲・見ていない範囲を返す。役は何も動かせないので、所見はどれも未実測の仮説として出させる。判定から入る run（`entry` が在り、かつ対象差分が空）では役を起こさず、2 つの素材に理由つきの `not_applicable` を書く。機械が、作業ツリーを変えていないか・所見の場所がファイルに在るか・2 つの素材の欄が決まりに合うかで受け付ける。

### 1.2 port

入力（YAML の `inputs:`）: materials.md の 1.2 の共通の 3 つだけ。`lang` の説明は `text: 人に見せる欄（consistency と bypass の detail・checked・reason、findings と bypass_findings の行の text・mechanism・measured・false_positive_if、seen、unseen）の言語。空は依頼の言語`。

足す入力は無い。今の材料の穴（`MATERIAL_HOLES['consistency-bypass']`、`lib/judge_accept.py:1727-1728`）は、どれも対象差分（`view`）と作業ツリーと工場の置き場から引ける。

出力（`returns: finish`、`outcome_field: ok`）: materials.md の 1.2 の 5 欄だけ。`material.json` の `reply` は受けた返答（`consistency`・`bypass`・`findings`・`bypass_findings`・`seen`・`unseen`）、`materials` は `{"consistency": <返答の consistency>, "bypass": <返答の bypass>}`。

今との違い: 今は差分の根・入口の印を `judge/start.json` から名で開き、受けた返答を `judge/material-consistency-bypass.json` に書いた。回すかは `material-route` が `not_request_entry` で決めた（`lib/judge_accept.py:1650-1656`）。

### 1.3 node の並び（`workflows/consistency-bypass/works-factory-consistency-bypass.yaml`）

materials.md の 1.3 の雛形の `<観点>` を `consistency-bypass` にした物。

1. `intake`（script `intake.py`）: port を読み、対象差分を取り、回すかを決め、回すなら作業ツリーを写す。返り `{due, reason}`。
2. `consistency-bypass-loop`（`loop_group`、最大 3 回、`fresh_context: false`、`until_bash: done=$consistency-bypass-accept.output.done; test "$done" = true`、`when: $intake.output.due == true`）
   - `consistency-bypass-prep`（script `role_prep.py`。`with:` を持たない）: 指示を組む。返り `{prompt}`。
   - `consistency-bypass`（AI）。`prompt: "$consistency-bypass-prep.output.prompt"`・`depends_on: [consistency-bypass-prep]`。起こし方は今の `read_launch`（`workflows/judge/works-factory-judge.yaml:67-72`）を字のまま展開する: `model: '@wf-judge-materials'`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`idle_timeout: 1728000000`。今の node と同じく `mutates_checkout: false` を置く（`:1160`）。`retry: {max_attempts: 2, on_error: all}`。`output_format` は今のまま（2.4）。
   - `consistency-bypass-accept`（script `role_accept.py`。`with: {reply: $consistency-bypass.output}`）: 返り `{ok, done, reason}`。
3. `finish`（script `finish.py`。`depends_on: [intake, consistency-bypass-loop]`・`trigger_rule: all_done`）: `material.json` を書き、出力を返す。どの段が落ちても落ちない。

### 1.4 place のファイル

materials.md の 1.4 の名だけ: `intake.json`・`view.json`・`diff.patch`・`changed-files.txt`・`tree.json`・`consistency-bypass-prompt-<n>.md`・`rejects-consistency-bypass.json`・`rejects-consistency-bypass.md`・`accepted.json`・`material.json`。観点だけの控えは無い。

1 つ目の commit（2.9 の指示の比べの間）だけ、`material-consistency-bypass-brief.md`（今の材料のファイルと同じ字）も書く。2 つ目の commit で書かなくなる。

### 1.5 コードの置き場

- `workflows/consistency-bypass/src/__init__.py`（空）。
- `workflows/consistency-bypass/src/viewpoint.py`: materials.md の 5.1 の宣言。中身:
  - `NAME = "consistency-bypass"`
  - `MATERIALS = ("consistency", "bypass")`（今の `MATERIAL_NODES['p1.consistency_bypass']['materials']` の順。`lib/judge_accept.py:1650-1656`）
  - `GUARDED = True`（AI の node が `mutates_checkout: false` を持つ。今の accept の `with: {status_guarded: true}`。`workflows/judge/works-factory-judge.yaml:1224`）
  - `NA = "never"`、`NA_REASON = ""`（今の節は `applies_cond` を持たず `na_self_ok: False`）
  - `due(view, values)`: `materialkit.not_entry_due(view, values, "P1 の役")`（`values["entry"]` が在り、かつ対象差分が空の時だけ `entry_skip` の訳で回さない）（今の `not_request_entry` の訳「…のため、P1 の役を起こさない」。`:1511-1516`）。空なら `materialkit.Due(True, "判定から入る run でない（port entry が空）——通常の run")`。
  - `fill(view, values, due)`: `{m: materialkit.fill_entry(values["entry"], None) for m in MATERIALS}`（回さないのは判定から入る run の時だけ。今の `_fill_one` の 1 つ目の枝。`request` の port を持たない観点は件数に None を渡し、「件数は渡されていない」と書かれる〔materials.md の 2.6。判定から入る run は依頼の行が 1 件以上ある時だけなので 0 件は偽〕）。
  - `applies(view, values)`: `raise NotImplementedError`。
  - `judged_na(view, values)`: `return False`。
  - `values(view, values)`: `{"repo": str(view.repo), "review_rev": view.review_rev, "base": view.base, "diff_file": view.diff_file, "changed_files": dump(list(view.changed_files)), "review_md": own}` に、`"repo_review_md": theirs` を（空の字の回も含め）常に足した物。`own, theirs = materialkit.review_md_paths(view.repo)`。`dump` は `json.dumps(x, ensure_ascii=False, indent=1)`。
  - `when(view, values)`: `{"repo_review": bool(theirs)}`（対象リポジトリの REVIEW.md の行の段落。`theirs` は `values` と同じく `review_md_paths` から）。外への検索の決まりの断片を入れないので `spawns` は置かない。
  - `before(view, values, reply, place)`: `return None, reply, False`。
  - `after(view, values, reply, place)`: `return None`（この観点に `post_check` は無い）。
  - `after_accept(reply, place)`: 何もしない。
  - `materials_of(reply)`: `{m: reply[m] for m in MATERIALS if isinstance(reply.get(m), dict)}`（今の `writes` の `materials.consistency ← consistency`・`materials.bypass ← bypass`。`:1653-1654`）。片方が無ければ `check_record` が「素材 'bypass' が返答に無い」で拒む。
  - `report_lines(doc)`: `reply` が null なら `[]`。在れば、`unseen` が空でない字の時だけ `[f"  - 見ていない範囲: {oneline(unseen)}"]`（字下げ 2 つ。materials.md の 2.10 の素材の 2 行の下に並ぶ）。所見の件数と中身は素材の行（`found` の `count`・`detail`）が言うので足さない。
- 使う `lib/`: `materialkit`・`oneline`。

### 1.6 つなぎ方（graph の側。block には書かない）

- 判定のまとめ（`workflows/judge/`）: `include: works-factory-consistency-bypass`、`depends_on` は materials.md の 1.6。`with:` は `base`・`entry`・`lang` を materials.md の 1.6 のとおりに。
- 読み手（どれも diagnose。今は置き場の `material-consistency-bypass.json` を名で開いた）:
  - 判定の材料の 15 欄: `materialkit.assemble` が `materials` の `consistency`・`bypass` を取る。
  - 判定の材料の「隔離フレームからの観察——整合性／標準機構の迂回」: 今は `_diagnose_ctx` が `reply` の `findings` を `process.consistency_findings` に、`bypass_findings` を `process.bypass_findings` に入れた（`lib/judge_accept.py:2769-2775`）。新しい形では diagnose が port `materials` の配列の中の `role` が `consistency-bypass` の `material.json` を `materialkit.read` で読み、`reply.findings`・`reply.bypass_findings` を取る（欄の名と形は今のまま）。返答の全部（今の `out.p1.consistency_bypass`）も同じ `reply` から取れる。
  - 目的の外の行の照らし（今の `material_rows`、`:701-717`）: P1 の観点の `reply` の中の `where`・`text` を持つ行を全部辿る。`findings` と `bypass_findings` の行がこれに当たる。出どころの名（今の `p1.consistency_bypass`）の付け方は diagnose の設計書が決める。
- 局所の所見・決着済みの論点・前の周の規約を、この block の port に配線しない。graphloops の `forbidden_inputs`（局所の findings・前の周の固有規約の把握・決着済み論点）を、port の形そのもので守る（2.7）。

## 2 node の設計シート: consistency-bypass（整合性と迂回の役）

### 2.1 役

対象差分を起点に依存先・近傍・呼び元まで読み、整合性の素材と標準機構の迂回の素材を独立に決め、2 系統の所見の行（未実測の仮説）と、見た範囲・見ていない範囲を返す。

### 2.2 port

`intake.json` の `view`（← port `base` と作業ツリー。`repo`・`base`・`review_rev`・`diff_file`・`changed_files`）・`values.lang`（← port `lang`）、観点の正本のパス（← `materialkit.review_md_paths(view.repo)`。port ではなく工場の置き場と作業ツリーの事実）、拒否の控え（← accept が place に積んだ `rejects-consistency-bypass.json`）。

### 2.3 組み立ての順（`prompts/consistency-bypass.md`）

materials.md の 3.1 の並び。

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: `rejects-consistency-bypass.json` に拒否が 1 件以上。`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "consistency-bypass"))`。
2. `{shared:role-inspector}`（役の定義。決まった文）。
3. 外への検索の決まりは入れない（web も外のコマンドも持たない。今の md にも無い）。
4. 役の 1 段落（決まった文）: 役の名と・2 つを独立に見ること・ほかの役の所見を受けていないことと、その訳。
5. 道具の段落（決まった文）と `{shared:material-readonly}`。
6. `## Materials` と差し込み口: `{repo}` ← `view.repo`、`{review_rev}` ← `view.review_rev`、`{diff_file}` ← `view.diff_file`（Read させるパス）、`{base}` ← `view.base`、`{changed_files}` ← `view.changed_files`（JSON の配列の字）、`{review_md}` ← `review_md_paths` の 1 つ目。`<!-- if repo_review -->` の 1 行と `{repo_review_md}` ← 2 つ目 `<!-- end repo_review -->` — 条件: 対象の根に `REVIEW.md` が在る。
7. `## What to do`（決まった文）: 今の graphloops の指示の段（`material-consistency-bypass.md:44-50`・`:53`）を英語にした物。
8. `## How to write consistency and bypass`: 2 つの素材を同じ形で書けという前置きの 1 文（決まった文）と `{shared:material-status}`。
9. `## Whether you may write not_applicable` と `{shared:material-na}` — 扱いは `never`（`na_never` だけが真）。
10. `## Where to point`、`{shared:material-where}`、この役が Read を持つことの 1 段落（決まった文。今の md:61）。
11. 言語の 1 文と `{lang}`。
12. 結びの 1 文。

md の本文（英語。この block の 2 つ目の commit でこのまま置く）:

```markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{shared:role-inspector}

You are the consistency-bypass role. You do two checks, independently of each other: consistency across the repository, and bypasses of standard mechanisms. **You are not given any other role's findings.** The local findings are kept from you on purpose: when findings are shared, every reviewer anchors on that frame and stops noticing a mechanism that the neighbouring code bypasses.

Your tools are Read, Grep, and Glob. You have no Bash, so you cannot run git or any other command.

{shared:material-readonly}

## Materials

- Repository: {repo}
- Version to read: `{review_rev}` (the working tree, including untracked new files, frozen into a commit before the material roles were started)
- Target diff: {diff_file} (Read it. It is the diff from the base commit `{base}` to that version; untracked new files are included.)
- Files the target diff touches: {changed_files}
- Review viewpoints: {review_md}. Follow its section "整合性観点" (consistency). It is the source of the labels and the viewpoints, and its sections "指摘の提出基準" (how to submit a finding) and "固有規約の把握" (learning the target's own conventions) apply below.
<!-- if repo_review -->
- The target repository's own review viewpoints: {repo_review_md}. Read it too.
<!-- end repo_review -->

## What to do

Learn the target's own conventions afresh from its primary sources: the README, lint settings, package manifests, CI definitions, and the neighbouring code. Look at the mechanism the neighbouring code actually uses, not the ideal a document describes; a mismatch between the two is a finding in itself.

- Return the range you looked at in `seen` and the range you did not look at in `unseen`, each as a string at the top level of the answer (not inside each material). If you stopped because of volume or time, say where you stopped. If "did not look" and "looked and found nothing" become the same "none", a silent omission is mistaken for "none".
- The diff is where you start looking, not where you stop. Read dependencies, neighbouring code, and callers as far as you need to understand the change.
- Submission criteria (from "指摘の提出基準" in the review viewpoints): the mechanism (one sentence on the causal chain in the code), the measurement (run what can be run; if it cannot be run, say it was not measured and submit it as a hypothesis), self-refutation before you submit (if you cite a rule, check that its condition applies, and read the actual neighbouring code; submit only the findings you could not kill), and an estimate of false positives (one line on when the finding would be wrong).
- You have only Read, Grep, and Glob, and cannot run anything. So nothing "can be run": submit every finding as a hypothesis that was not measured, and say so in the `measured` field of each row. Running things to confirm a finding is the job of the other material roles that have Bash, and of the diagnosing role that reads the materials and verifies them.
- Answer with the consistency material in `consistency` and the bypass material in `bypass`. Keep the finding rows in two separate lists: consistency rows in `findings`, bypass rows in `bypass_findings`. Both lists are top-level fields of the answer, not fields inside `consistency` or `bypass`. A row has only these five fields: `where` (required; the location, written as described under "Where to point"), `text` (required; what is wrong), `mechanism` (the one-sentence mechanism), `measured` (for this role, that it was not measured), and `false_positive_if` (the one-line estimate of when it is a false positive).
- If the input is not enough (for example, you cannot read the target diff), set the `status` of both `consistency` and `bypass` to `not_run`, and say in each `reason` what is missing.

**Read the version fixed for this run**, not a moving working tree. A role that can run git would read with the version named, such as `git -C <repository> show <version>:<path>`, so that what it sees does not move even if someone edits the files; the machine also counts evidence in that same version. **You cannot run git.** Read the files of the working tree with Read, Grep, and Glob instead. The version above was frozen from the working tree just before the material roles were started, and no material role may change the working tree (the acceptance step compares it before and after). So the files in the working tree have the same contents as that version, and the line numbers you see with Read are the line numbers to write in `where`.

## How to write consistency and bypass

`consistency` and `bypass` each take the shape of `material` described below.

{shared:material-status}

## Whether you may write not_applicable

{shared:material-na}

## Where to point

{shared:material-where}

You have Read, so you are a role that can read files. The files in the working tree have the same contents as the version above, so write the line number you confirmed with Read.

Write the `detail`, `checked`, and `reason` of `consistency` and `bypass`, the `text`, `mechanism`, `measured`, and `false_positive_if` of each row of `findings` and `bypass_findings`, and `seen` and `unseen` in {lang}. Keep keys, enum values, identifiers, paths, commands, and quoted text as they are.

Return only JSON that matches the output schema.
```

md の中に `$` の字は無い。`{` は差し込み口と断片だけ。見出しの「整合性観点」などは `lib/REVIEW.md` の見出しの字（日本語）で、役がそのファイルの中で探す名なので、訳さずに引く。

言語・会話・retry: prior-decisions.md の 2.3 の終わりと同じ。

### 2.4 返す形

今の `output_format` のまま（`workflows/judge/works-factory-judge.yaml:1162-1218`）:

- `consistency`・`bypass`: どちらも `{status (found|clean|carried_over|not_applicable|awaiting_human|not_run), count? (0 以上の整数), detail?, checked?, reason?, from_round? (1 以上の整数)}`・`additionalProperties: false`・`required: [status]`。
- `findings`・`bypass_findings`: `[{where, text, mechanism?, measured?, false_positive_if?}]`・各行 `additionalProperties: false`・`required: [where, text]`。
- `seen`・`unseen`: 字。
- 全体 `additionalProperties: false`・`required: [consistency, bypass, findings, bypass_findings, seen, unseen]`。

人に見せる欄は 1.2 の `lang` の説明の欄（判定の材料と、目的の外の行・報告に載る）で、言語は `{lang}`。`where` は名指しなので字のまま。

### 2.5 描いた骨組み（例の run の値）

例の run では、今の指示は 2 か所に在った: `workflows/judge/commands/material-consistency-bypass.md`（63 行。`$consistency-bypass-prep.output.lang_line`・`.reason`・`.brief_file`・`.review_md`・`.repo_review_md` を Archon が入れた物）と、役が Read した `judge/material-consistency-bypass-brief.md`（59 行）。新しい指示はこの 2 つを 1 本にする:

```markdown
{shared:role-inspector の本文: This role is an inspector. …（6 行）}

You are the consistency-bypass role. You do two checks, independently of each other: … （決まった文。実物は prompts/consistency-bypass.md）

Your tools are Read, Grep, and Glob. You have no Bash, …

{shared:material-readonly の本文: Do not change a single character of the target's working tree, …}

## Materials

- Repository: ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/worktrees/archon/task-works-factory-line-1792307529854
- Version to read: `25e7ad718467e26133cdf9359f427e8774a06c7a` (…)
- Target diff: ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-ac9f-4468-ae72-5f6ed569a667/judge/diff.patch (Read it. It is the diff from the base commit `7defb7ec5fac098b7302f5bfc11a02f151f4d262` to that version; …)
- Files the target diff touches: [
 "backend/app/api/model/schemas.py",
 "backend/app/api/routers/threads.py",
 …（23 行）
 "frontend/messages/ja.json"
]
- Review viewpoints: ~/.cache/works-factory-plugin/2eff50966651bb961c234169d7381fc86fc756be/lib/REVIEW.md. Follow its section "整合性観点" …
- The target repository's own review viewpoints: ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/worktrees/archon/task-works-factory-line-1792307529854/REVIEW.md. Read it too.

## What to do

Learn the target's own conventions afresh from its primary sources: …（決まった文と箇条 6 つと、固めた版の段落）

## How to write consistency and bypass

`consistency` and `bypass` each take the shape of `material` described below.

{shared:material-status の本文: How to write `material`: …}

## Whether you may write not_applicable

This viewpoint has no condition under which it does not apply, so the acceptance step rejects `not_applicable`. …

## Where to point

Write the `<path>:<line>` of a location (`where`) as a line number in the current file in the working tree. …

You have Read, so you are a role that can read files. …

Write the `detail`, `checked`, and `reason` of `consistency` and `bypass`, … in the language of the request (the user's language). …

Return only JSON that matches the output schema.
```

例の run は 1 回目で通ったので、却下の段落は入らない。`lang` は空（始めの記録の `lang` が null）で、`{lang}` に既定の文が入った形。対象の根に REVIEW.md が在ったので `repo_review` の段落が入った。値の字は、今の材料のファイルの「## 材料: inputs.cwd」「inputs.review_rev」「loop.diff_file」「record.base」「loop.changed_files」「inputs.review_md」「inputs.repo_review_md」の節の字と同じ（`review_md` は、新しい形では run の起動の殻が置いた工場の写しの `lib/REVIEW.md`。例の run ではプラグインの写しの置き場だった）。

### 2.6 今の指示との差

今の指示は `workflows/judge/commands/material-consistency-bypass.md`（63 行）と、`material_prep` が描く材料のファイルの 2 か所に在る。prior-decisions.md の 2.6 と同じ差（材料の節を指示に入れた・`MATERIAL_BRIEF_HEAD` と頭の 2 行を消した・『条件に当たらない』の節を `{shared:material-na}` に・却下の段落の 2 回を `{shared:rejected}` の 1 回に〔中身は前の 1 回の理由から拒否の全部に〕・作業ツリーを変えるなを `{shared:material-readonly}` に・素材の書き方と所見の場所を断片に・言語の 1 行を md の 1 文に・「元の graphloops の指示書」の境と見出しを消した・「同じ時に別の素材集めの役も走っている」を「走りうる」に）は繰り返さない。この観点だけの差:

- まとめた: 役の定義の段（md:3-11）を `{shared:role-inspector}` に。今は md の頭と、md:25「この役は整合性と標準機構の迂回を見る役（inspector）」と、graphloops の段の頭（md:39「この役は inspector。」）の 3 か所で inspector と言っていた。役の定義の断片 1 つと、役の 1 段落の役の名 "the consistency-bypass role" にした。
- 移した: 観点の正本の段（md:33。`review_md` と `repo_review_md` のパスを Read せよ）と、graphloops の段の「観点の正本: ［材料: inputs.review_md］（「整合性観点」のセクションに従え。対象リポジトリ側の観点: ［材料: inputs.repo_review_md］）」（md:42）を、`## Materials` の 2 行（`Review viewpoints` と `<!-- if repo_review -->` の行）にまとめた。同じパスを 2 回言っていた。
- 変えた: 対象リポジトリの REVIEW.md が無い run の書き方。今は空の値を入れて「空でなければそれも Read せよ」（md:33）と言い、材料のファイルでは省略可の穴の語「（この周には無い）」（`render.ABSENT`）になった。新しい形は段落ごと入れない（`repo_review` が偽）。役が読む物は同じ（無い物は読まない）。
- 移した: 「指摘の提出基準」の段（md:47）、「Read・Grep・Glob しか持たず、所見は未実測の仮説」（md:48。#221）、返答の欄の段（md:50。#221 が足した「一番上の欄で、consistency・bypass の中には入れない」と行の 5 つの欄）、見た範囲・見ていない範囲（md:45。#221 が足した「一番上の階層の欄に、素材ごとには書かない」）を、`## What to do` の箇条に。中身は変えない。
- 移した: 入力が足りない時の決まり（md:51 の尾「consistency と bypass の status をどちらも not_run にし、reason を『足りない: 』で始めて」）を `## What to do` の箇条に。印の字「足りない: 」は言わず、「何が足りないかを言え」にした。訳: この字を機械は読まない（`lib/`・`workflows/*/scripts/` に照らす所が無い）。`reason` は人に見せる欄で `{lang}` で書くので、日本語の印の字を英語の md に置くと言語の決まりと食い違う。役の定義の断片が「足りない」の書き方を持つ（今の `lib/agents/inspector.md` の 3 つ目の箇条）。
- 移した: 素材の書き方の段（md:51）を `{shared:material-status}` に。この観点の素材は `material` の欄でなく `consistency` と `bypass` の 2 欄なので、断片の前に「2 つとも下の `material` の形で書け」の 1 文と見出しを足した（今は段の中で「素材（material）」と言い、2 欄に当てるのは役に任せていた）。
- 移した: 固めた版の段（md:53。#221 が Bash の無い役に書き直した物）を `## What to do` の終わりの段落に。中身は変えない。
- 残した: 所見の場所の段の尾の「この役は Read を持つので、上の『ファイルを読める役』に当たる…」（md:61）を、`{shared:material-where}` の後の 1 段落に（materials.md の 3.1 の 10 の「観点ごとの前置き」。この観点では後ろに置く。断片の中の分かれ道のどちらに当たるかを言う文なので、断片の後でないと指す先が無い）。
- 消した: md:27 の手順 1（材料のファイルを Read せよ・末尾の『条件に当たらない』も読め）と、md:29 の手順 3 の道具の名の句（道具の段落に入れた）。
- 変えた: 断片 `material-where` の尾の文を、受け付けが照らす範囲（`where` と `text` を持つ行だけ。ほかの行は照らさない）に合わせて狭めた。
- 英語にした（#764）。役の名「整合性と迂回の役」は "the consistency-bypass role"。

### 2.7 元の works と graphloops の同じ場面

族の形の差は materials.md の 9 節。この観点だけの差:

- 元の works の `works/blk-material/commands/consistency-bypass.md`（7 行）は、engine が描いた graphloops の指示書のファイル（`prompt_file`）を Read させる薄い md だった。工場は graphloops の指示書を md の中に写し、値だけを材料のファイルにした（#76）。新しい形は値も指示の中に入れる。
- 元の graphloops の指示書は、元の works も工場も graphloops の版 a1202d0 の写し（`works/.shared/core/gl-prompts/prompts/review-loop/p1.consistency_bypass.md`）。今の graphloops（`~/src/claude-plugins/graphloops/prompts/review-loop/p1.consistency_bypass.md`）との違いは語の置き換え（節→セクション・欄→フィールド、`c63c2ae3`、2026-10-19）と、差分と版の穴の名（`hist.snapshot.*`。同じ物を指す）だけで、能力の差は無い。
- 工場がこの写しに足した物（どれも #221）: 所見は未実測の仮説として `measured` に書く（Bash の無い役が「動かせるものは動かす」を満たせないため）・`seen` と `unseen` は返答の一番上の欄・行の 5 つの欄の名指し・入力が足りない時は 2 つの素材を `not_run`・git の無い役の固めた版の読み方（作業ツリーを Read し、その行番号を `where` に書く）。この block も持つ。
- graphloops の `graphs/review-loop.json` の `p1.consistency_bypass` は `forbidden_inputs` に局所の findings・前の周の固有規約の把握・決着済み論点を挙げる（`:2007-2011`）。graphloops は engine の `reads` の柵で守った。工場は役の材料の穴にそれらを入れないことで守った（`MATERIAL_HOLES`）。新しい形は block の port がそれらを持たないことで守る（1.6）。
- 元の works と工場の受け付けは同じ順（作業ツリー・所見の場所・素材の欄）で、この観点に `post_check` は無い（graphloops の `MATERIAL_NODES` も持たない）。

この block が両方より良く、残す物: 所見の行が未実測であることを役に書かせ、検証の役（diagnose）が読み分けられる・`seen`/`unseen` の欄の置き場を名指して、見ていない範囲の欠けを返答の形で防ぐ・作業ツリーと所見の場所を機械が照らす・ほかの役の所見を port の形で入れない。

### 2.8 受け付け

materials.md の 4 節の順のまま。観点の前の照らしと後の照らしは無い。

- 拒む物: JSON のオブジェクトでない返答・役が作業ツリーを変えた（`GUARDED` が真なので、比べる欄から `porcelain`〔`git status --porcelain` の字〕を外す。`accept.status_keys(True)`。`mutates_checkout: false` の node は Archon 自身が node の前後の git status を照らすので、同じ欄を 2 度比べない。今の YAML の `status_guarded: true` と同じ）・所見の場所の行がファイルに無い（`findings` と `bypass_findings` の行は `where` と `text` を持つので `where_rows` が拾う。素材の `detail` の中の `<パス>:<行>` も今と同じく拾う物だけ）・素材 `consistency` か `bypass` が無い・どちらかが `carried_over`・どちらかが `not_applicable`（`never`）・知らない status・status ごとの要る欄の欠け（2 つの素材のそれぞれに当てる）。
- 拒みの文は materials.md の 2.8 と 4 節の字。素材の名は `consistency`・`bypass` のどちらかが入る（例「素材 'bypass' が返答に無い」）。
- 3 回目の拒否で諦める。数えるのは受け付けの拒否で、node が落ちた時の Archon の起こし直し（`retry`、最大 2 回）は数えない（prior-decisions.md の 2.3 の終わり）。`finish` は `status: gave_up`・`reason` に最後の拒否の文・2 つの素材のどちらにも同じ `not_run` の訳を書く。
- 所見の場所の外れは、3 回目の回は拒まずに印を付けて受ける（今のまま）。

### 2.9 試験

- standalone の fixture（`workflows/consistency-bypass/fixtures/`）:
  - `standalone.stubs.yaml`: `fixture.inputs` は `base: ""`・`entry: ""`・`lang: ""`。AI の node `consistency-bypass` だけを台本の返答（`consistency: {status: clean, checked: "呼び手を見た"}`・`bypass: {status: clean, checked: "標準の口を見た"}`・`findings: []`・`bypass_findings: []`・`seen: "差分の全部"`・`unseen: "無し"`）で差し替え、script は本物。`reached` に `finish`。`finish` の `status` が `ran`。
  - `gave-up.stubs.yaml`: 台本の返答が 3 回とも `consistency.status: not_applicable`。`finish` の `status` が `gave_up`、run は `completed`。
  - `skipped.stubs.yaml`: `entry: "人の依頼（standalone）"`。AI の node に届かず（`reached` に `consistency-bypass` が無い）、`finish` の `status` が `skipped`。
- `tests/blocks/consistency_bypass/test_consistency_bypass.py`（materials.md の 8 節の block の試験）:
  - 写す元 `lib/tests/test_judge_accept.py::MaterialCase.test_consistency_bypass_reply_is_taken_or_refused`（`:1447-1457`）: `bypass` の無い返答は「素材 'bypass' が返答に無い」で拒まれ、2 つを書いた返答は受けて、`material.json` の `materials` が `{"consistency": …, "bypass": …}`。
  - 写す元 `DueCase.test_empty_diff_run_with_requests_runs_only_prior_decisions`（`:1124-1130`）のうちこの観点の部分: `entry` が在れば `intake` の `due` が偽で訳を言い、`finish` が `status: skipped`・2 つの素材が `not_applicable`（`reason` が `entry` の字を含む）。`DueCase.test_run_with_a_diff_runs_them`（`:1136-1139`）の部分: `entry` が空なら `due` が真。
  - 足す: 対象の根に `REVIEW.md` が在れば組んだ指示にそのパスの行が入り、無ければその段落ごと無い（`repo_review` の両方の値）。`MATERIALS` の 2 つのどちらかで `found` の `count` が欠けた返答を拒む。`report_lines` が `unseen` の行を足し、`reply` が null の時は足さない。
  - 足す（起こし方の照らし）: block の YAML の AI の node の `model`・`allowed_tools`・`sandbox`・`idle_timeout`・`retry`・`mutates_checkout` が、今の `tests/workflows/test_judge.py:91` の表の consistency-bypass の行（`"sonnet", "medium", READ, BASE, True, …`）が照らす物と同じ。
- 指示の比べ（README の 11.4）: `tests/blocks/consistency_bypass/test_prompts.py`。
  - 1 つ目の commit: `prompts/consistency-bypass.md` を、今の `workflows/judge/commands/material-consistency-bypass.md` の `$consistency-bypass-prep.output.<欄>` を `{lang_line}`・`{reason}`・`{brief_file}`・`{review_md}`・`{repo_review_md}` に替えた日本語の字で置く。prep は 1 つ目の commit だけこの 5 つ（`lang_line` は `rolekit.lang_line({"lang": values["lang"]})`、`reason` は最後の拒否の文か空、`brief_file` は `src/oldbrief.py` が書いた `material-consistency-bypass-brief.md` の絶対パス、`review_md`・`repo_review_md` は `review_md_paths` の 2 つ〔無ければ空〕）を値に入れる。`src/oldbrief.py` の `brief(view, values)` は今の材料のファイルを同じ字で組む: 頭（`MATERIAL_BRIEF_HEAD` の字と、「素材集めの役 consistency-bypass（graphloops のノード p1.consistency_bypass）の指示書の…」の 1 行）、7 つの「## 材料: <穴>」の節（穴の名は `MATERIAL_HOLES` の順で `?` を外した字、配列は `dump`、`repo_review_md` が空なら「（この周には無い）」）、『条件に当たらない』の見出しと `na_self_ok` の無い時の文（`_na_note` の `ap is None` の枝）、を `"\n\n"` でつなぎ、尾に改行 1 つ。試験は使い捨てのリポジトリ（ファイル 1 つを直した差分）で、(a) 組んだ指示が今の md に同じ 5 つの値を入れた字と同じ、(b) `oldbrief.brief` の字が、同じリポジトリと同じ差分で今の `judge_accept.material_prep(jdir, "consistency-bypass", repo, review_md, repo_review_md)["brief"]` が返す字と同じ（試験は今の lib を import してよい。block は import しない）ことを照らす。例の run の材料のファイルとは比べない（自分で決めた。7 節）。
  - 2 つ目の commit（英語）: 1 つ目の試験と `src/oldbrief.py` を消し、例の run の値で組んだ新しい指示と、今の md と材料のファイルを並べた物を PR に載せ、2.6 の差の一覧どおりかを審査に出す。
- 振る舞いの試験の残り: 族の部品の試験（`lib/tests/test_materialkit.py`）が、作業ツリー・所見の場所・素材の欄の照らしと『条件に当たらない』の扱いの語（今の `test_na_note_for_each_kind_of_node` の consistency-bypass の行）を見る。
- 守る keep-essence の番号: 無い。守るのは「ほかの役の所見を受けない独立の目」で、port の形（`base`・`entry`・`lang` だけ）がそれを担い、形の検査（`inputs:` の鍵）が変われば試験の fixture の入力の鍵が変わるので見える。
- 終わりの条件の命令（1 モジュールずつ）:

```sh
uv run --isolated python3 -m unittest discover -s tests/blocks/consistency_bypass -t .
uv run --isolated python3 -m unittest tests.layers.test_block_shape
uv run --isolated python3 -m unittest tests.blocks.consistency_bypass.test_prompts
```

  最後の行は 1 つ目の commit の間だけ回す（2 つ目の commit で `test_prompts.py` を消す）。

## 3 script の node

materials.md の 6 節の雛形のまま。この block だけの物:

- `intake.py` が読む入力は `INPUTS_BASE`・`INPUTS_ENTRY`・`INPUTS_LANG` の 3 つ。どれも `ports.text(…)`。値の dict の鍵は `base`・`entry`・`lang`。
- 1 つ目の commit だけ、`role_prep.py` が `src.oldbrief.brief(view, values)` を place の `material-consistency-bypass-brief.md` に書いてから組む。

## 4 受け付けの文

materials.md の 2.8 と 4 節の文だけを使う。この観点が足す拒みの文は無い。

## 5 単独で呼ぶ

```sh
bin/works-factory workflow run works-factory-consistency-bypass \
  --input base=<差分の根の commit。空なら HEAD>
```

作業ツリーは Archon の cwd（対象のリポジトリ）。差分は `base` から作業ツリーの今の姿まで。`--input entry='人の依頼（手で起こした run）'` を足すと役を起こさず、`status: skipped` で返る。出力は `workflow get <run>` の `finish` の返り。始めの記録は要らない。

## 6 未確認

- 土台の役の定義の断片の名 `role-inspector`（materials.md の 11 節）。断片が「入力が足りない時の書き方」を今の `lib/agents/inspector.md` のまま持つか（2.6 で印の字をそちらに任せた）。
- `materialkit.review_md_paths(repo)` の形（materials.md の 5.2 の終わりに名だけが在り、2 節の口の一覧に無い）。この文書は「(工場の `lib/REVIEW.md` の絶対パス, 対象の根の `REVIEW.md` の絶対パスか空)」を返す口と読んだ。
- 5 節の命令の正確な形。

## 7 自分で決めた事（この block だけ）

- 回す時の `due` の訳を「判定から入る run でない（port entry が空）——通常の run」にする。訳: 今の字「入口の印（process.request_entry）が無い——通常の run」は、block が持たない記録の名を言う。訳は intake の返りの `reason` と `intake.json` にだけ出て、判定にも素材にも入らない。
- 対象リポジトリの REVIEW.md の行を `when` の段落（`repo_review`）で入れ外しする。訳: 空の値を差し込むと「空でなければ読め」という役の判断が要り、materials.md の 2.11 は入らない段落の口の値を渡さない形を決めている。今の省略可の穴の語（「（この周には無い）」）は engine の描き方の都合で、役が読む物は変わらない。
- 「足りない: 」の印の字を md に置かない（2.6）。訳: 機械が読まない字で、`reason` の言語の決まり（`{lang}`）と食い違う。
- 1 つ目の commit の材料のファイルの比べを、例の run のファイルでなく、試験のリポジトリで今の `material_prep` が返す字と比べる。訳: 例の run の対象は別の組織のリポジトリ（<owner>/<repo>）で、その変更ファイルの名と置き場のパスを試験に入れたくない。今の関数は作り直しの間は残る（materials.md の 1.5）ので、同じ値で組んだ字を直に比べられ、置き換えるパスの字の扱いも要らない。
- `report_lines` に `unseen` の 1 行だけを足す。訳: この観点は「見ていない」と「無かった」を分けることを返答の形で求める観点で、素材の 2 行（status と count・detail か checked）は見ていない範囲を言わない。所見の行は素材の `detail` が言う。
- `due` は `materialkit.not_entry_due(view, values, "P1 の役")` を使う（entry が在り、かつ対象差分が空の時だけ回さない）。訳: main の部品が今の `not_request_entry` の写しで、修正が入って差分が出来た run は入口の周でない。1.5 の「entry が空でなければ」は差分が空の前提を落とした書き方だった。訳の字は部品のもの。
- `NA_PARAGRAPH = True`。訳: md が共通の断片 `material-na` を差し込むので、`na_*` の段落と `na_why` が要る。
- `values` は `repo_review_md` を、対象に REVIEW.md が無い回も空の字で渡す。訳: 指示を組む口（`workflows/.shared/prompt.py`）は選ばれない段落の中の差し込み口にも値を要求する。1.5 の「`theirs` が空でない時だけ足す」は main の口と合わない。
- 役の 1 段落から「started in a new conversation」を外した。訳: 輪は `fresh_context: false` で会話を継ぐので、2 回目以降の回で嘘になる。
- 1 つ目の commit の `role_prep.py` は `materialkit.prompt_inputs` を通らず、今の指示の 5 つの値で直に組む（2 つ目の commit で雛形に戻す）。
