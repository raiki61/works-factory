# block の設計書: test-double-fidelity（代役の忠実性）

- 何の話か: 対象差分が外部との継ぎ目（別プロセス・別サービス・ブラウザ・外部 API・プロトコル）に触れる時に、テストの代役（モック・スタブ・フェイク）の形が実物と合うかを、実物から取った値 1 件で確かめる素材の観点「代役の忠実性」を、単独で呼べる block `workflows/test-double-fidelity/` にする設計。族の共通の形は [materials.md](materials.md)、写す手本は [prior-decisions.md](prior-decisions.md)。
- 決めたこと: 今の judge の `material-route` の 1 列と `test-double-fidelity-loop`（prep・役・accept）を、materials.md の 5 つの node の block にする。入力は共通の 3 つ（`base`・`entry`・`lang`）だけ。判定から入る run では役を起こさず、出どころつきの `not_applicable` を機械が書く。『条件に当たらない』の扱いは `cond` で、当たる条件はいつも真（機械は継ぎ目かを決められないので触れる側に倒す。今と同じ）。観点の前と後の照らしは無い。指示は 1 本の英語の md にし、材料のファイルを無くす。振る舞いは変えない。
- 持ち主に求めること: なし。
- 読む人と使い方: この block を作る実装者（1〜3 節の名と順をそのまま作る）。素材の観点の残りの 10 本の 1 本（README の 11.1 の 1 波目の「残りの 10 本を同時に作る」）。急ぎの度合い: 族の部品（`lib/materialkit.py`）と 1 本目の観点 prior-decisions を入れる PR の後なら、ほかの観点を待たずにいつ作ってもよい（ほかの block はこの block を待たない。読み手の diagnose は 2 波目）。

この文書の語は README・materials.md・prior-decisions.md の頭の物を使う（「判定から入る run」〔差分が空で依頼が 1 件以上の run。line が始めの記録から決め、port `entry` に出どころの文を入れて知らせる。空でない `entry` がその印〕・「周」は materials.md の頭）。ほかに:

- line と始めの記録: line は工場のメイングラフ。run の始めに、差分の根（`diff_base`）・言語・依頼の件数・判定から入る run かを「始めの記録」（`start.json`）に書き、block には port の値として配る。この block は始めの記録を読まず、line が配った `base`・`entry`・`lang` だけを受ける。

- P3: 元の graphloops の段の名で、修正の段（工場の fix）。今の条件の「前の周の P3 が何かを直した周」は、前の周の修正が触れたファイルが在る周のこと。工場は 1 run = 1 周なので、いつも 0 件。

- 代役の役（test-double-fidelity）: 対象差分が触れる継ぎ目の代役を実物と突き合わせ、不一致の行と素材の状態を返す AI の役。道具は Read・Grep・Glob・Bash・WebSearch・WebFetch。Bash は網の開いた sandbox の中で走り、写しは一時の置き場に作る（今の `test_run_launch`）。
- 不一致の行: 返答の `mismatches` の 1 行 `{where, text, mechanism?, measured?, false_positive_if?}`。`where` と `text` を持つので、所見の場所の照らし（`materialkit.where_rows`）に当たる。
- 例の run: 本物の run `53e71318-ac9f-4468-ae72-5f6ed569a667`（対象 <owner>/<repo>。置き場 `~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-…/judge/`）。差分の在る run（23 ファイル）で、代役の役は 1 回目で受け付けを通った（`material-test-double-fidelity.json` の `materials.test_double_fidelity.status` が `clean`、`mismatches` は空。`rejects-test-double-fidelity.json` は無い）。同じ対象の run `17ee8ecc-717a-4dc7-92b6-25ecd08fa15b` も同じ形の材料を持つ。

## 1 block の全体

### 1.1 役

対象差分が触れる外部との継ぎ目について、テストの代役の入力と出力の形を、実物から取った値 1 件と突き合わせる。不一致があれば行にして `found`、無ければ何と何を比べたかを書いて `clean`。機械が、作業ツリーを変えていないか・不一致の行の場所がファイルに在るか・素材の欄が決まりに合うかで受け付ける。判定から入る run では役を起こさない。

### 1.2 port

入力（YAML の `inputs:`）: materials.md の 1.2 の共通の 3 つだけ。

- `base`・`entry`: materials.md の 1.2 の字のまま。
- `lang`: `text: 人に見せる欄（material の detail・checked・reason と、mismatches の text・mechanism・measured・false_positive_if）の言語。空は依頼の言語`。既定 `""`。

足す入力は無い。今の材料の穴（`MATERIAL_HOLES['test-double-fidelity']`、`lib/judge_accept.py:1734`）は `loop.diff_file`・`loop.changed_files_file`・`inputs.cwd` の 3 つで、どれも `view`（対象差分の見方）から入る。

出力（`returns: finish`、`outcome_field: ok`）: materials.md の 1.2 の 5 欄だけ。`material.json` の `reply` は受けた返答（`material`・`mismatches`）、`materials` は `{"test_double_fidelity": <返答の material>}`。

今との違い: 今は入力を `judge/start.json`（差分の根・入口の印）から名で開き、回すかを `material-route` が決め（`test_double_fidelity_due`）、回さない時の埋めは `material-route.json` の `fill` から diagnose-prep の `fill_materials` が写した。受けた返答は `judge/material-test-double-fidelity.json` に書き、判定役は返答の全体を `out.p1.test_double_fidelity` の穴で読んだ（`lib/judge_accept.py:2764-2795` の `_diagnose_ctx`）。

### 1.3 node の並び（`workflows/test-double-fidelity/works-factory-test-double-fidelity.yaml`）

materials.md の 1.3 の雛形の `<観点>` を `test-double-fidelity` にした物。

1. `intake`（script `intake.py`）: port を読み、対象差分を取り、回すかを決め（判定から入る run でなければ回す）、回す時は作業ツリーを写す。返り `{due, reason}`。
2. `test-double-fidelity-loop`（`loop_group`、最大 3 回、`fresh_context: false`、`until_bash: done=$test-double-fidelity-accept.output.done; test "$done" = true`、`when: $intake.output.due == true`）
   - `test-double-fidelity-prep`（script `role_prep.py`。`with:` を持たない）: 指示を組む。返り `{prompt}`。
   - `test-double-fidelity`（AI）。`prompt: "$test-double-fidelity-prep.output.prompt"`・`depends_on: [test-double-fidelity-prep]`。起こし方は今の `test_run_launch`（`workflows/judge/works-factory-judge.yaml:1494-1510`）を字のまま展開する: `model: '@wf-judge-materials'`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob, Bash, WebSearch, WebFetch]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false, failIfUnavailable: true, enableWeakerNetworkIsolation: true, network: {allowedDomains: ['*'], allowLocalBinding: true}, filesystem: {allowWrite: [/], denyWrite: ['~/../archon-home']}}`（今の注記 `# denyWrite は pr-check の注釈と同じ` は、展開した先に pr-check が無いので、`net_closed_launch` の注記 3 行〔`:475-477`〕を写して置き替える）・`idle_timeout: 1728000000`。`retry: {max_attempts: 2, on_error: all}`。`mutates_checkout:` は今と同じく置かない。`output_format` は今のまま（2.4）。
   - `test-double-fidelity-accept`（script `role_accept.py`。`with: {reply: $test-double-fidelity.output}`）: 返り `{ok, done, reason}`。
3. `finish`（script `finish.py`。`depends_on: [intake, test-double-fidelity-loop]`・`trigger_rule: all_done`）: `material.json` を書き、出力を返す。どの段が落ちても落ちない。

### 1.4 place のファイル

materials.md の 1.4 の名だけ: `intake.json`・`view.json`・`diff.patch`・`changed-files.txt`・`tree.json`・`test-double-fidelity-prompt-<n>.md`・`rejects-test-double-fidelity.json`・`rejects-test-double-fidelity.md`・`accepted.json`・`material.json`。観点だけの控えは無い。

1 つ目の commit（README の 11.4 の比べの間）だけ、`material-test-double-fidelity-brief.md`（今の材料のファイルと同じ字）も書く（2.9）。2 つ目の commit で書かなくなる。

### 1.5 コードの置き場

- `workflows/test-double-fidelity/src/__init__.py`（空）。
- `workflows/test-double-fidelity/src/viewpoint.py`: materials.md の 5.1 の宣言。中身:
  - `NAME = "test-double-fidelity"`
  - `MATERIALS = ("test_double_fidelity",)`
  - `GUARDED = False`（AI の node が `mutates_checkout: false` を持たない。今の accept の `with: {status_guarded: false, …}`。`works-factory-judge.yaml:1621`）
  - `NA = "cond"`、`NA_REASON = "対象差分は外部との継ぎ目（別プロセス・別サービス・ブラウザ・外部 API・プロトコル）に触れていない"`（今の `MATERIAL_NODES['p1.test_double_fidelity']['na_reason']`、`lib/judge_accept.py:1681-1685` の字のまま）。当たる条件がいつも真なので今は使われない（`fill_na` を呼ぶ道が無い）が、`applies` が偽を返せるようになった時に `materialkit.fill_na` と md の `na_cond_false` の段落が使う
  - `NOUN = "代役の忠実さの確かめ"`（今の `_deep_due` に渡した名詞。`:1573-1574`）
  - `due(view, values)`: `materialkit.is_entry_run(view, values)`（`entry` があり、かつ対象差分が空。族の決め。materials.md の 2.6）が真なら `materialkit.entry_skip(NOUN)`。偽（`entry` が空、または修正が入って差分がある）なら `materialkit.Due(True, "代役の忠実さの確かめは、判定から入る run でなければ run ごとに 1 回回す（1 run は 1 周で、いつも初回。差分が外部との継ぎ目に触れるかは機械が決められないので、触れる側に倒す）")`（自分で決めた。7 節）。
  - `fill(view, values, due)`: `{"test_double_fidelity": materialkit.fill_entry(values["entry"], None)}`。`due` が偽になるのは判定から入る run だけなので、埋めはこの 1 通り（今の `_fill_one` の 1 つ目の枝。`:1937-1941`）。
  - `applies(view, values)`: `materialkit.Due(True, "差分が外部との継ぎ目に触れる")`（今の `seams_touched` が、機械が真に倒した `touches_external_seams` で返す字。`:1474-1485`・`due_view` の `:1356`）。
  - `judged_na(view, values)`: `return False`。
  - `values(view, values)`: `{"diff_file": view.diff_file, "changed_files_file": view.changed_files_file, "repo": str(view.repo)}`。役は Read を持つので、差分と一覧はパスで渡す（materials.md の 3.1 の 6）。
  - `when(view, values)`: `{"spawns": False}`（外への検索の決まりの断片の段落。この役は Agent の道具を持たない）。
  - `before(view, values, reply, place)`: `return None, reply, False`。
  - `after(view, values, reply, place)`: `return None`（今の `MATERIAL_NODES` にこの観点の `post_check` は無い）。
  - `after_accept(reply, place)`: 何もしない。
  - `materials_of(reply)`: `{"test_double_fidelity": reply["material"]} if isinstance(reply.get("material"), dict) else {}`（今の `writes` の `materials.test_double_fidelity ← material`）。
  - `report_lines(doc)`: `reply` の `mismatches` の行ごとに `f"  - 代役の不一致: {oneline(text)}（{where}）"`。`reply` が null か行が無ければ `[]`。
- `workflows/test-double-fidelity/src/oldbrief.py`（1 つ目の commit だけ。2.9）: 今の材料のファイルを同じ字で組む `brief(view) -> str`。2 つ目の commit で消す。
- schema のファイルは無い（json の入力を持たない）。
- 使う `lib/`: `materialkit`・`rolekit`・`oneline`。

### 1.6 つなぎ方（graph の側。block には書かない）

- 判定のまとめ（`workflows/judge/`）: `include: works-factory-test-double-fidelity`、`depends_on` は materials.md の 1.6。`with:` は `base: <line が始めの記録から引いた diff_base>`・`entry: <line が始めの記録から引いた出どころの文。判定から入る run でなければ空>`・`lang: <始めの記録の lang>`。
- 読み手: diagnose だけ。
  - port `materials`（11 本の `material` の配列の 1 つ）を `materialkit.assemble` で 15 欄にそろえ、素材 `test_double_fidelity` を読む。
  - 判定役の材料の「代役の忠実性」の穴（今の `{{?out.p1.test_double_fidelity}}`、`DIAGNOSE_EXCERPT` の `:2717`）は返答の全体（`material` と `mismatches`）だった。新しい形では同じ `material.json` の `reply` の欄から取る（`_reply_of` が `material-<役>.json` の `reply` を読んでいた形のまま）。どう描くかは diagnose の設計書が決める。
- ほかに返答の欄を読む物は無い（`lib/` と `workflows/` を `mismatches`・`test_double_fidelity` で探した）。

## 2 node の設計シート: test-double-fidelity（代役の役）

### 2.1 役

対象差分が触れる外部との継ぎ目の代役を、実物から取った値 1 件と突き合わせ、不一致の行と素材の状態を返す。

### 2.2 port

`intake.json` の `view`（← port `base` と作業ツリー。`diff_file`・`changed_files_file`・`repo`）・`values.lang`（← port `lang`）、拒否の控え（← accept が place に積んだ `rejects-test-double-fidelity.json`）。`values.entry` は intake の回すかの決めだけが読み、指示には入らない。

### 2.3 組み立ての順（`prompts/test-double-fidelity.md`）

materials.md の 3.1 の並び。

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: `rejects-test-double-fidelity.json` に拒否が 1 件以上。`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "test-double-fidelity"))`。
2. 役の定義の断片は置かない（今の md の頭は外への検索の決まりの塊だけ。materials.md の 5.2）。
3. `{shared:query-rule}`。`spawns: false`。
4. 役の 1 段落（決まった文）。
5. 道具の段落（決まった文。網が開いていることと一時の置き場）と `{shared:material-readonly}`。works-gh は置かない（今の md に無い。網が開いているので要らない）。
6. `## Materials` と 3 つの差し込み口: `{diff_file}` ← `view.diff_file`、`{changed_files_file}` ← `view.changed_files_file`、`{repo}` ← `view.repo`。
7. `## What to do`（決まった文）: 今の graphloops の指示の段（`material-test-double-fidelity.md:38`）を英語にした物。
8. `{shared:material-status}`。
9. `## Whether you may write not_applicable` と `{shared:material-na}` — 扱いは `cond`。当たる条件はいつも真なので、入るのはいつも `na_cond_true` の段落。`{na_why}` ← `applies` の why（「差分が外部との継ぎ目に触れる」）。
10. `## Where to point` と `{shared:material-where}`。前置きは無い（`mismatches` の行が `where` を持つ）。
11. 言語の 1 文と `{lang}`。
12. 結びの 1 文。

md の本文（英語。この block の 2 つ目の commit でこのまま置く）:

```markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{shared:query-rule}

You are the test-double-fidelity role. Your only job is to check whether the test doubles at the seams the target diff touches have the same shape as the real thing. You are given neither the local findings nor any other material.

Your tools are Read, Grep, Glob, Bash, WebSearch, and WebFetch. Bash runs inside a sandbox, and its network is open. Make any copy you need for running things in a temporary folder (create it with `mktemp -d`); the wrapper stops writes to the target's working tree.

{shared:material-readonly}

## Materials

- Target diff (Read it): {diff_file}
- List of changed files (one file per line; Read only what you need): {changed_files_file}
- Repository: {repo}

## What to do

If the target diff touches a seam with the outside (another process, another service, a browser, an external API, a protocol), check whether the shape of each test double (mock, stub, fake) matches the real thing, **using one value taken from the real thing**. A double is judged not by how faithfully it reproduces the real thing but by whether an error in the implementation can be observed through it. A double whose input shape differs from the real thing cannot observe the error: the test turns green on a shape that only the double accepts.

- Put the mismatches in `mismatches`. `mismatches` is a top-level field of the answer, separate from `material`. Write one row per mismatch, with `where` and `text` (and, if useful, `mechanism`, `measured`, and `false_positive_if`).
- If there are mismatches, set `material.status` to `found`, with the number of `mismatches` rows in `count` and a summary in `detail`.
- If there are none, leave `mismatches` empty, set `material.status` to `clean`, and say in `checked` what you compared with what.

{shared:material-status}

## Whether you may write not_applicable

{shared:material-na}

## Where to point

{shared:material-where}

Write `material.detail`, `material.checked`, `material.reason`, and the `text`, `mechanism`, `measured`, and `false_positive_if` of each `mismatches` row in {lang}. Keep keys, enum values, identifiers, paths, commands, and quoted text as they are.

Return only JSON that matches the output schema.
```

md の中に、`$` の直後に英字か `{` が続く字は無い（materials.md の 3.1 の終わり）。`{diff_file}` などの差し込み口のほかに `{` は無い。

会話と retry: prior-decisions.md の 2.3 の終わりと同じ。

### 2.4 返す形

今の `output_format` のまま（`workflows/judge/works-factory-judge.yaml:1587-1615`）:

- `material`: prior-decisions.md の 2.4 と同じ形（`status` の 6 語・`count`・`detail`・`checked`・`reason`・`from_round`。`required: [status]`）。
- `mismatches`: `[{where, text, mechanism?, measured?, false_positive_if?}]`・各行 `additionalProperties: false`・`required: [where, text]`。
- 全体 `additionalProperties: false`・`required: [material, mismatches]`。

人に見せる欄は `material.detail`・`material.checked`・`material.reason`・`mismatches` の `text`・`mechanism`・`measured`・`false_positive_if`（判定の材料に載る）で、言語は `{lang}`。`where` は名指しなので字のまま。

### 2.5 描いた骨組み（例の run の値）

例の run では、今の指示は 2 か所に在った: `workflows/judge/commands/material-test-double-fidelity.md`（47 行。`$test-double-fidelity-prep.output.lang_line`・`.reason`・`.brief_file` を Archon が入れた物）と、役が Read した `judge/material-test-double-fidelity-brief.md`（19 行）。新しい指示はこの 2 つを 1 本にする:

```markdown
{shared:query-rule の本文: Rules for queries to outside services …（7 行）}

You are the test-double-fidelity role. …（決まった文）

Your tools are Read, Grep, Glob, Bash, WebSearch, and WebFetch. Bash runs inside a sandbox, and its network is open. …

{shared:material-readonly の本文: Do not change a single character of the target's working tree, …}

## Materials

- Target diff (Read it): ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-ac9f-4468-ae72-5f6ed569a667/judge/diff.patch
- List of changed files (one file per line; Read only what you need): ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-ac9f-4468-ae72-5f6ed569a667/judge/changed-files.txt
- Repository: ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/worktrees/archon/task-works-factory-line-1792307529854

## What to do

If the target diff touches a seam with the outside …（決まった文と箇条 3 つ）

{shared:material-status の本文: How to write `material`: `status` is one of the following. …}

## Whether you may write not_applicable

The condition of this viewpoint holds for this run (差分が外部との継ぎ目に触れる), so the acceptance step rejects `not_applicable`. …

## Where to point

Write the `<path>:<line>` of a location (`where`) as a line number in the current file in the working tree. …

Write `material.detail`, … in the language of the request (the user's language). …

Return only JSON that matches the output schema.
```

例の run は 1 回目で通ったので、却下の段落は入らない。`lang` は空で、`{lang}` に既定の文が入った形。差分と一覧のパスは今の `judge/` の物を描いた。新しい形では block の place の `diff.patch`・`changed-files.txt`（判定のまとめから include された時は `$ARTIFACTS_DIR/<judge の include の id>/test-double-fidelity/` の下）を指す。『条件に当たらない』の段落の `{na_why}` の字は、今の材料のファイルの末尾の節「このノードの条件 `seams_touched` はこの周に真（差分が外部との継ぎ目に触れる）なので…」の括弧の中と同じ。

### 2.6 今の指示との差

族の共通の差（却下の段落・外への検索の決まり・作業ツリーを変えるな・素材の書き方・所見の場所・言語の 1 行・元の graphloops の指示書との境の見出し・材料のファイルの頭の 2 行と「［材料: 〜］」の穴と Read の手順）は prior-decisions.md の 2.6 と同じに扱う。この観点だけの差:

- 移した: 材料のファイルの 3 つの節（`loop.diff_file`・`loop.changed_files_file`・`inputs.cwd`）を、`## Materials` の 3 行に。今の md の 36 行目「対象差分: ［材料: loop.diff_file］　変更ファイルの一覧: …（1 行 1 ファイル。要る所だけ Read）　リポジトリ: …」の括弧の説明は、行の札に移した。
- 移した: 材料のファイルの尾の『条件に当たらない』の節（`seams_touched` が真で拒む、の 1 文）を `{shared:material-na}` の `na_cond_true` の段落に。
- 消した: 指示の段の尾「…か、継ぎ目に触れない差分なら not_applicable（reason）」（md:38）。訳: 当たる条件がいつも真なので、受け付けは `not_applicable` をいつも拒み、同じ指示の材料の節も「受け付けが拒む」と言っていた。食い違う 2 文のうち、受け付けと同じ側（`{shared:material-na}`）だけを残した。受け付けの決まりは変わらない（自分で決めた。7 節）。
- 消した: 道具の段の「同じ時に別の素材集めの役も走っている」の断定（prior-decisions.md の 2.6 と同じ。`{shared:material-readonly}` の「走りうる」）。
- 足した: 道具の段の「its network is open」。今の md は網を言わないが、起こし方（`network: {allowedDomains: ['*']}`）の事実を役に伝える 1 句で、prior-decisions の「網は閉じている」と対になる。
- 残した: `mismatches` は頭の欄で `material` と別・1 件 1 行・`found` の時の `count` は行の数（#221 が足した段）。返答の形を決める文なので残した。
- 変えた: 断片 `material-where` の尾の文を、受け付けが照らす範囲（`where` と `text` を持つ行だけ。ほかの行は照らさない）に合わせて狭めた。
- 英語にした（#764）。役の名「代役の忠実性の役（任せ先）」は "the test-double-fidelity role"。「任せ先」（元の graphloops の `run_by: writer` の委任の印）は、block の中に任せる元が無いので訳さない。

### 2.7 元の works と graphloops の同じ場面

族の形の差は materials.md の 9 節。この観点だけの差:

- 元の works の `works/blk-material/commands/test-double-fidelity.md`（7 行）は、engine が描いた graphloops の指示書（`prompt_file`）を Read させる薄い md だった。工場は graphloops の指示書を md の中に写し、値だけを材料のファイルにした（#76）。新しい形は値も指示の中に入れる。
- 元の graphloops の指示書（`~/src/claude-plugins/graphloops/prompts/review-loop/p1.test_double_fidelity.md`）と元の works の写し（`works/.shared/core/gl-prompts/prompts/review-loop/p1.test_double_fidelity.md`）の違いは、材料の名（`hist.snapshot.*` と `loop.*`）と語（「ノード」と「節」）だけ。工場はそこに `mismatches` の書き方の段を足し、「線を引く」を「区切る」にした（どちらも #221）。新しい形も持つ。
- graphloops の節の宣言（`graphs/review-loop.json` の `p1.test_double_fidelity`）が持ち、工場に無い物:
  - `escalate_note`（同じ欠陥の類〔判定役が欠陥ごとに付ける class〕が周をまたいで直っては戻る run を「昇格した run」とし、その周は回す条件に関わらず走る）と、`test_double_fidelity_due` の昇格の枝: 工場は `loop.escalated` をいつも偽にした（#76。`due_view` の docstring、`lib/judge_accept.py:1337-1345`）。1 run = 1 周なので周をまたぐ戻りが無い。新しい形は枝ごと持たない。
  - `carry_reason`（代役の形に変更が無い周は前の確認を持ち越す）と「前の周の P3 が何かを直した周」の枝: 1 run = 1 周（持ち主の決め carry）で、工場の `prev_fix_touched` はいつも 0 件（#76）。新しい形は持たない。
  - `optional: true`（人が engine の `skip` で節を省ける。`graphloops/engine/commands.py:1842`）: 工場に無い（（未確認）: 工場の履歴に外した記録は見つからない）。新しい形は、判定のまとめの `when:` で機能を切る run に外す形（materials.md の 1.6）だけを持つ。
  - `delegate.model: sonnet`: 工場は群の名 `'@wf-judge-materials'`（今の試験の表で sonnet・medium。`tests/workflows/test_judge.py:96`）。同じ。
- 元の works の受け付け（`works/blk-material/lib/material.py` の take）と工場の受け付けは同じ順で、この観点に `post_check` は無い（graphloops も持たない）。

この block が両方より良く、残す物: `mismatches` の書き方（頭の欄・1 件 1 行・数と行の数を合わせる）を指示が言う（#221）・不一致の行の場所がファイルに在るかを機械が照らす・判定から入る run で回さない素材に出どころつきの理由を書く。

### 2.8 受け付け

materials.md の 4 節の順のまま。観点の前の照らしと後の照らしは無い。

- 拒む物: JSON のオブジェクトでない返答・役が作業ツリーを変えた（`GUARDED` が偽なので、比べる欄は `porcelain` を含む `TREE_KEYS` の全部。役は一時の置き場に写しを作って走らせるので、写しを作業ツリーの中に作れば拒まれる）・不一致の行の `where` の `<パス>:<行>` がファイルの行の外・素材 `test_double_fidelity` が無い・`carried_over`・`not_applicable`（`cond_true`）・知らない status・status ごとの要る欄の欠け。
- 返答の形（`output_format`）の外れは Archon が node の段で拒む（今のまま）。
- 拒みの文は materials.md の 2.8 と 4 節の字（日本語）。
- 3 回目の拒否でループを抜ける。run は止めず、`finish` が `status: gave_up`・`reason` に最後の拒否の文・素材 `test_double_fidelity` に `not_run` と同じ訳を書く。
- 所見の場所の外れは、3 回目の回は拒まずに `where` の尾に印（`LOCATION_MARK`）を付けて受ける（今のまま）。

### 2.9 試験

- standalone の fixture（`workflows/test-double-fidelity/fixtures/`）:
  - `standalone.stubs.yaml`: `fixture.inputs` は `base: ""`・`entry: ""`・`lang: ""`。AI の node `test-double-fidelity` だけを台本の返答（`material.status: clean`・`checked` 1 文・`mismatches: []`）で差し替え、script は本物（`--exec-code`）。`reached` に `finish`。`finish` の出力の `status` が `ran`。
  - `gave-up.stubs.yaml`: 台本の返答が 3 回とも `material.status: not_applicable`（`cond_true` で拒まれる）。`finish` の `status` が `gave_up`、run は `completed`。
  - `skipped.stubs.yaml`: `entry: "人の依頼（standalone）"`。AI の node に届かず（`reached` に `test-double-fidelity` が無い）、`finish` の `status` が `skipped`。
- `tests/blocks/test_double_fidelity/test_test_double_fidelity.py`: materials.md の 8 節の block の試験。始めの記録の無い使い捨ての `ARTIFACTS_DIR` と git のリポジトリで、port の値だけを渡す。
  - 写す元 `lib/tests/test_judge_accept.py::MaterialCase.test_test_double_fidelity_reply_is_taken_or_refused`: `carried_over` は拒まれ、拒みの文が「素材 'test_double_fidelity'（観点 test-double-fidelity）は今の周に走ったのに carried_over」を言う。`clean` の返答は通り、`material.json` の `materials` が `{"test_double_fidelity": <返答の material>}`。
  - 足す: `not_applicable` は拒まれ、拒みの文が「条件が真で走ったのに not_applicable」を言う。組んだ指示に `na_cond_true` の段落と「差分が外部との継ぎ目に触れる」の字が入り、ほかの 3 つの `na_*` の段落が入らない。
  - 足す: `mismatches` の行の `where` がファイルの行の外なら 1・2 回目は拒まれ、3 回目は `LOCATION_MARK` を付けて受ける（`MaterialCase.test_location_beyond_the_file_is_sent_back_then_marked` の形を、この観点の返答で）。
  - 足す: `entry` が在れば `intake` の `due` が偽で、`finish` が `status: skipped`・素材 `test_double_fidelity` が `not_applicable` で、`reason` に出どころの字と「件数は渡されていない」の句が入る。
  - 足す: `report` に `mismatches` の行ごとの「代役の不一致」の行が出る。
  - 足す（起こし方の照らし）: block の YAML の AI の node の `model`・`allowed_tools`・`sandbox`・`idle_timeout`・`retry` が、今の `tests/workflows/test_judge.py:96` の行（`"sonnet", "medium", INVESTIGATE, DELEGATE, …`）が照らす物と同じ。
- 指示の比べ（README の 11.4）: `tests/blocks/test_double_fidelity/test_prompts.py`。
  - 1 つ目の commit: `prompts/test-double-fidelity.md` を、今の `workflows/judge/commands/material-test-double-fidelity.md` の `$test-double-fidelity-prep.output.lang_line` を `{lang_line}` に、`.reason` を `{reason}` に、`.brief_file` を `{brief_file}` に替えた日本語の字で置く。prep は 1 つ目の commit だけ、この 3 つを値に入れる（prior-decisions.md の 2.9 と同じ作り）。試験は例の run の値（`diff_file`・`changed_files_file`・リポジトリのパス）で、(a) 組んだ指示が今の md に同じ 3 つの値を入れた字と同じ、(b) `oldbrief.brief` の字が例の run の `judge/material-test-double-fidelity-brief.md` と同じ（パスは試験の物に置き換えて比べる）ことを照らす。材料のファイルの末尾の『条件に当たらない』の節は、今の `_na_note` が組んだ字（`seams_touched` が真）をそのまま写す。
  - 2 つ目の commit（英語）: 1 つ目の試験と `src/oldbrief.py` を消し、例の run の値で組んだ新しい指示と、今の md と材料のファイルを並べた物を PR に載せ、2.6 の差の一覧どおりかを審査に出す。
- 守る keep-essence の番号: 無い（keep-essence は元の works が「作り替えで外さない」と決めた 12 の仕組み〔`works/docs/keep-essence.md`、README の 10 節〕で、この観点はそのどれにも当たらない）。
- 終わりの条件の命令（1 モジュールずつ）:

```sh
uv run --isolated python3 -m unittest discover -s tests/blocks/test_double_fidelity -t .
uv run --isolated python3 -m unittest tests.layers.test_block_shape
uv run --isolated python3 -m unittest tests.blocks.test_double_fidelity.test_prompts
```

## 3 script の node

materials.md の 6 節の雛形のまま。この block だけの物:

- `intake.py` が読む入力は `INPUTS_BASE`・`INPUTS_ENTRY`・`INPUTS_LANG` の 3 つ。どれも `ports.text(…)`。値の dict の鍵は `base`・`entry`・`lang`。
- 1 つ目の commit だけ、`role_prep.py` が `src.oldbrief.brief(view)` を place の `material-test-double-fidelity-brief.md` に書いてから組む。

## 4 受け付けの文

materials.md の 2.8 と 4 節の文だけを使う。この観点が足す拒みの文は無い。

## 5 単独で呼ぶ

```sh
bin/works-factory workflow run works-factory-test-double-fidelity \
  --input base=<差分の根の commit>
```

作業ツリーは Archon の cwd（対象のリポジトリ）。出力は `workflow get <run>` の `finish` の返り。始めの記録は要らない。`entry` を渡すと役を起こさずに `skipped` を返す。

## 6 未確認

- 土台の `prompt.render` が、入らない段落（`na_never`・`na_cond_false`・`na_judged`）の中の差し込み口を「使われない値」に数えるか（materials.md の 11 節）。

## 7 自分で決めた事（この block だけ）

- 回す時の訳を、今の `_deep_due` の字（「差分が外部との継ぎ目に触れていて初回の周、または前の周の P3 が何かを直した周——成り立つ（round=1・差分が外部との継ぎ目に触れる・前の周の P3 が触ったファイルは 0 件）」）でなく、「代役の忠実さの確かめは、判定から入る run でなければ run ごとに 1 回回す（…触れる側に倒す）」にする。訳: 1 run = 1 周で、前の周と P3 の枝はいつも効かない。prior-decisions の `due` が同じ替え方をした（prior-decisions.md の 1.5）。報告と `intake.json` に出る字が変わるだけで、回すかの真偽は今と同じ。
- `NA` を materials.md の 5.2 のとおり `cond` にする（当たる条件はいつも真）。訳: `never` にすると md に入る段落が「この観点には当たらない条件が無い」になり、`NA_REASON`（継ぎ目に触れない差分）という意味を持つ観点の言い方として誤る。`cond` なら、機械が継ぎ目を決められるようになった時に `applies` だけを替えれば済む。受け付けの拒みは `never` と `cond_true` のどちらでも同じく `not_applicable` を拒む。
- 指示から「継ぎ目に触れない差分なら not_applicable」を消す。訳: 受け付けがいつも拒む書き方を指示が勧めると、役が 1 回拒まれる道が残る。材料の節と受け付けの側に合わせた（2.6）。
- `report_lines` に不一致の行を 1 行ずつ足す。訳: prior-decisions が決着済みの論点を足したのと同じく、素材の 1 行（件数と detail の要約）だけでは、どの継ぎ目のどこかが報告から辿れない。
- `test_run_launch` の注記「denyWrite は pr-check の注釈と同じ」を、`net_closed_launch` の注記 3 行の写しに替える。訳: 錨を展開した block の YAML に pr-check は無く、名指す先が無い注記になる（block はほかの block を名指さない。憲法の 3）。
- 実装で決めた事（materials.md の 10.1 と同じ扱い）:
  - `fill` は `materialkit.fill_entry(entry, None)`（件数は渡されていない、と言う）。訳: 1.5 の `0` だと「依頼 0 件」と言い切るが、この block は依頼の件数を受けない。2.9 の試験の句（「件数は渡されていない」）と、受けない事実に合わせた。
  - 役の 1 段落の頭を「You are the test-double-fidelity role.」にし、「started in a new conversation」を外した。訳: 輪が `fresh_context: false` で、2 回目からは同じ会話が続くので、新しい会話と言うと事実と違う（調整役の指摘）。2.3 の本文もこの文に揃えた。固定の文（筋書きの `resolved-text-contains`）もこの文。
  - 輪の中は prep → 役 → accept の 1 本線で、同じ層に node を 2 つ置かない（会話を続ける役の前に複数 node の層を作ると Archon が会話を切るため）。
  - `intake.py` は `request` の port を持たない（この block の入力は `base`・`entry`・`lang` の 3 つだけ）。
