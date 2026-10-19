# block の設計書: purpose-review（目的の監査）

- 何の話か: この block を作る実装者が、そのまま作るための設計書。目的の文を役（writer）が自分で要約した run で、その目的の文が実装に都合よく狭められていないかを別の目に見させる素材の観点「目的の監査」を、単独で呼べる block `blocks/purpose-review/` にする設計。族の共通の形は [materials.md](materials.md)、1 本目の手本は [prior-decisions.md](prior-decisions.md)。型は [README.md](README.md)。
- 決めたこと: 今の judge の `material-route` の 1 列と `purpose-review-loop`（prep・役・accept）を、materials.md の 5 つの node の block にする。入力は差分の根・固めた目的・判定から入る run の出どころ・言語の 4 つの port。回すかは block の intake が目的の出典の語（`③writer の要約`）で決める。素材の欄は書かず（素材 0 個）、受けた返答 `{verdict, reason, findings}` を `material.json` の `reply` に置く。判定の語 `問題なし`・`狭めている` は今の字のまま（読み手が字で比べるため）。根拠の数え直し（今の `purpose_findings_cited`）は block の `src/` に写す。振る舞いは変えない。
- 持ち主に求めること: なし。
- 読む人と使い方: この block を作る実装者（1〜4 節の名と順をそのまま作る）。素材の観点の残り 10 本と同じ PR の束に入る（README の 11.1 の 1 波目）。読み手の block（diagnose・plan-review）の設計書の書き手は 1.6 を読む。

この文書の語は README・materials.md・prior-decisions.md の頭の物を使う。ほかに:

- 目的の監査の役（purpose-review）: 固めた目的の文と、読む版（作業ツリーを固めた commit）を渡され、目的の文が実装の範囲に合わせて縮められていないかを判じる AI の役。役の定義は inspector。道具は Read・Grep・Glob だけ（Bash を持たないので git を打てない）。
- 判定の語: 返答の `verdict` の 2 語 `問題なし`・`狭めている`（今の `output_format` の enum。`workflows/judge/works-factory-judge.yaml:1017-1019`）。
- 根拠の行: 返答の `findings` の 1 行 `{text, cite, hits}`。`cite` は `git grep -F` で引ける字、`hits` はその字が現れる行の数。機械が読む版に対して数え直す。
- 出典の語 `③writer の要約`: 目的の block（[purpose.md](purpose.md)）の出力の `source` の 4 語の 1 つ（今の `workflows/judge/works-factory-judge.yaml:673-675` の enum。新しい形では `blocks/purpose/src/steps.py` の `WRITER_SOURCE`）。目的の役が、PR の説明も計画の文書も無く、自分で要約した時に書く。
- 例の run: 記録の在る 148 本の run（`~/.local/state/works-factory/targets/*/archon-home/workspaces/*/*/artifacts/runs/*/`）のどれでも、この役は走っていない（どの `judge/material-route.json` も `purpose-review` の `run` が偽で、`judge/purpose-review.json` はどれも `{}`）。骨組みは run `53e71318-ac9f-4468-ae72-5f6ed569a667`（対象 <owner>/<repo>。置き場 `~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-…/judge/`）の値に、出典の語だけを `③writer の要約` と仮に置いて描いた（自分で決めた。7 節）。

## 1 block の全体

### 1.1 役

目的の役が自分で要約した目的の文について、PR の実際の変更範囲・issue・計画に比べて、実装済みの範囲に合わせて縮んでいないか・実装で解けない要件が黙って落ちていないかを、別の context の inspector に判じさせる。判定には作業ツリーで引ける根拠（字とその行の数）を付けさせ、機械が読む版で数え直す。目的の出典が PR の説明か計画の文書なら（書き手と別の人が書いた物なので）役を起こさない。

### 1.2 port

入力（YAML の `inputs:`）:

- `base`・`entry`: materials.md の 1.2 の字のまま（`base` は対象差分の根の commit。空は HEAD。`entry` は判定から入る run〔差分が空で人の依頼が在る run〕の出どころの文。空はそうでない run）。`entry` はこの観点の回す条件にも埋めにも使わない（今の `purpose_review_due` は入口の印を読まない）が、族の共通の入力（`base`・`entry`・`lang`）として持つ（materials.md の 1.2「どの観点も次の 3 つを持つ」）。
- `purpose`: materials.md の 1.2 の字のまま（`json(purpose.schema.json): 固めた目的 {purpose_text, source, known_weaknesses, source_files}。null は目的の文がこの run に無い`。既定 `null`）。
- `lang`: `text: 人に見せる欄（reason、findings の text）の言語。空は依頼の言語`。既定 `""`。

出力（`returns: finish`、`outcome_field: ok`）: materials.md の 1.2 の 5 欄だけ。`material.json` の `reply` は受けた返答（`verdict`・`reason`・`findings`）、`materials` は `{}`（素材を書かない観点）。

今との違い: 今は目的を `judge/purpose.json` から名で開き（`lib/judge_accept.py:1887-1894` の `_purpose_of`）、受けた返答を `judge/material-purpose-review.json` に書き、判定の返す節（`verdict`）がその `reply` を `judge/purpose-review.json` に写して（`:3960-3963`）、判定の出力の欄 `purpose_review`（`PORTS`、`:3881-3882`）で外へ出していた。役が走らなかった run は `{}` を置いた（`_empty_public`、`:3903`）。

### 1.3 node の並び（`blocks/purpose-review/works-factory-purpose-review.yaml`）

materials.md の 1.3 の雛形の `<観点>` を `purpose-review` にした物。

1. `intake`（script `intake.py`）: port を読み、対象差分を取り（読む版 `review_rev` を固めるため）、回すかを決め、回す時は作業ツリーを写す。返り `{due, reason}`。
2. `purpose-review-loop`（`loop_group`、最大 3 回、`fresh_context: false`、`until_bash: done=$purpose-review-accept.output.done; test "$done" = true`、`when: $intake.output.due == true`）
   - `purpose-review-prep`（script `role_prep.py`）: 指示を組む。返り `{prompt}`。
   - `purpose-review`（AI）。`prompt: "$purpose-review-prep.output.prompt"`・`depends_on: [purpose-review-prep]`。起こし方は今の `read_launch`（`workflows/judge/works-factory-judge.yaml:67-72`）を字のまま展開する: `model: '@wf-judge-materials'`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`idle_timeout: 1728000000`。`mutates_checkout: false`（今の node に在る。`:1011`）。`retry: {max_attempts: 2, on_error: all}`。`output_format` は今のまま（2.4）。
   - `purpose-review-accept`（script `role_accept.py`。`with: {reply: $purpose-review.output}`）: 返り `{ok, done, reason}`。
3. `finish`（script `finish.py`。`depends_on: [intake, purpose-review-loop]`・`trigger_rule: all_done`）: `material.json` を書き、出力を返す。

### 1.4 place のファイル

materials.md の 1.4 の名だけ: `intake.json`・`view.json`・`diff.patch`・`changed-files.txt`・`tree.json`・`purpose-review-prompt-<n>.md`・`rejects-purpose-review.json`・`rejects-purpose-review.md`・`accepted.json`・`material.json`。

（実装では書かない: 7 節）材料のファイル `material-purpose-review-brief.md` は書かない。

### 1.5 コードの置き場

- `blocks/purpose-review/src/__init__.py`（空）。
- `blocks/purpose-review/src/viewpoint.py`: materials.md の 5.1 の宣言。中身:
  - `NAME = "purpose-review"`
  - `MATERIALS = ()`（今の `MATERIAL_NODES['p0.purpose_review']` が `materials` を持たない。`lib/judge_accept.py:1641-1643`）
  - `GUARDED = True`（AI の node が `mutates_checkout: false` を持つ。今の accept の `with: {status_guarded: true}`。`workflows/judge/works-factory-judge.yaml:1036`）
  - `NA = "never"`、`NA_REASON = ""`（`applies_cond` も `na_self_ok` も無い。素材を書かないので、`check_record` が照らす物は無い）
  - `WRITER_SOURCE = "③writer の要約"`（目的の block の出典の語の写し。照らしは 2.9 の試験）
  - `VERDICT_OK = "問題なし"`、`VERDICT_NARROWS = "狭めている"`、`VERDICTS = (VERDICT_OK, VERDICT_NARROWS)`（md と受け付けが同じ字を持つ値。README の 5.3。YAML の enum と同じ並び）
  - `due(view, values)`: 順に
    1. `values["purpose"]` が null なら `materialkit.Due(False, f"目的の文が渡されていない——監査するのは writer が要約した目的（{WRITER_SOURCE}）だけ")`。
    2. `src = values["purpose"]["source"]` が `WRITER_SOURCE` でなければ `materialkit.Due(False, f"目的テキストの出典が {src}——監査するのは writer が要約した目的（③）だけ")`（今の `purpose_review_due` の字。`:1600-1601`）。
    3. ほかは `materialkit.Due(True, "writer が要約した目的の 1 周目")`（今の `:1602-1603` の字。今の条件には 2 周目から効く枝が 2 つ在る〔前の周の修正が目的の出典のファイルを触った時と、前の周の監査の根拠の行が `cite` を持たない古い形の時に回し直す〕が、工場は 1 run = 1 周なので効かない）。
  - `fill(view, values, due)`: `return {}`（素材を書かない。materials.md の 2.6 の 3 の `fill` は空の dict になる）。
  - `applies(view, values)`: `raise NotImplementedError`。
  - `judged_na(view, values)`: `return False`。
  - `values(view, values)`: `{"purpose_text": values["purpose"]["purpose_text"], "repo": str(view.repo), "review_rev": view.review_rev, "verdict_ok": VERDICT_OK, "verdict_narrows": VERDICT_NARROWS}`。`due` が真の時だけ呼ばれるので `purpose` は null でない。
  - `when(view, values)`: `{}`（観点の段落の切り替えは無い。外への検索の決まりを差し込まないので `spawns` も無い）。
  - `before(view, values, reply, place)`: `return None, reply, False`。
  - `after(view, values, reply, place)`: `return src.cited.problem(reply, view.review_rev, VERDICT_NARROWS)`（4 節の照らし。`materialkit.accept` が `accept.in_repo(repo)` の中で呼ぶ）。
  - `after_accept(reply, place)`: 何もしない。
  - `materials_of(reply)`: `return {}`。
  - `report_lines(doc)`: `reply` が null なら `[]`。在れば `f"  - 判定: {verdict}（根拠 {len(findings)} 件）"` の 1 行と、根拠の行ごとに `f"  - 根拠: {oneline(text)}（{oneline(cite)} が {hits} 行）"`。字下げ 2 つで、materials.md の 2.10 の素材の無い観点の 1 行（`観点 purpose-review: ran`）の下に並ぶ。
- `blocks/purpose-review/src/cited.py`: 根拠の数え直し。公開の名は `problem(reply, rev, narrows) -> str | None` だけ。写す元（`lib/judge_accept.py`。中身を写し、引数を下のとおりに替える）:
  - `_repo_root`（`:2223-2225`）・`_grep_count`（`:2228-2234`）・`_count_in_version`（`:2378-2398`）を字のまま。
  - `_cite_errors`（`:2280-2375`）は、`findings` の道（`CITE_LABELS["findings"]`。指し先を持たない）だけを写した `_errors(rows, rev) -> list[str]`: 行が dict でない・`cite` が空・改行を含む・NUL を含む の 4 つの照らしと `_count_in_version`。`wrote_refs` の道（指し先と書いた場所・`hook_evidence` による読了の記録の照らし）は写さない（この観点は指し先を持たない行だけを出すので、その道に入らない。今も `jdir` はその道でしか使われない）。
  - `purpose_findings_cited`（`:2401-2410`）を `problem` に。`verdict == narrows` で `findings` が空なら拒む文、`_errors` が在れば拒む文を返し、無ければ `None`。数え直せない時の `Reject`（git が動かない・版を解決できない）も捕まえて、その字を返す。
  - 使う `lib/`: `graphloops/engine/util.py` の `git`・`_grep`・`repo_root`・`sum_counts`・`Reject`。
- `blocks/.shared/schemas/purpose.schema.json`: 固めた目的の形（下）。external-standards の block も使うので `.shared` に置く（materials.md の 1.2「同じ意味の入力は同じ名と同じ形」。置き場の決めは 7 節）。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": ["object", "null"],
  "additionalProperties": false,
  "required": ["purpose_text", "source", "known_weaknesses", "source_files"],
  "properties": {
    "purpose_text": {"type": "string", "minLength": 1, "pattern": "\\S"},
    "source": {"type": "string", "enum": ["①PR 説明", "②計画・タスク記述", "③writer の要約", "目的不明"]},
    "known_weaknesses": {"type": "array", "items": {"type": "string"}},
    "source_files": {"type": "array", "items": {"type": "string"}}
  }
}
```

  欄と enum は今の目的の役の `output_format`（`workflows/judge/works-factory-judge.yaml:667-681`）から `means` を外した物（目的の block は `means` を別のファイル `purpose-means.json` に分ける。[purpose.md](purpose.md) の頭の「目的の控え」）。
- 使う `lib/`: `materialkit`・`rolekit`・`oneline`・`graphloops/engine/util.py`。

### 1.6 つなぎ方（graph の側。block には書かない）

- 判定のまとめ（`blocks/judge/`）: `include: works-factory-purpose-review`、`depends_on` は materials.md の 1.6。`with:` は `base`・`entry`・`lang` を materials.md の 1.6 のとおり、`purpose: $purpose.output.purpose`（目的の block の `purpose.json` の pointer。[purpose.md](purpose.md) の 1.6 の読み手の行）。
- 回すかは block の intake が `purpose.source` で決める（materials.md の 10 節）。graph の `when:` は機能を切る run だけに置く。[purpose.md](purpose.md) の 1.6 の「目的の監査を回すかは、line が `$purpose.output.source` が `③writer の要約` かで決める」は、この block では採らない（回さない run にも `status: skipped` と訳を返すため。報告に書いた）。
- 読み手:
  - diagnose: `materials`（11 本の `material` の配列の 1 つ）。素材の 15 欄には何も足さない（`materialkit.assemble` は `materials` が空の doc を読み飛ばす）。判定役の材料の「目的の監査」の行（今の `record.process.purpose_review`。`lib/judge_accept.py:2780`）は、`role` が `purpose-review` の doc の `reply` から取る（diagnose の設計書の決め）。
  - plan-review（独立設計〔独立の目 R2 が、差分を見ずに目的の文だけから組む設計。keep-essence の 9〕を止めるかの決めと、裏取りを通っていない判定の行。`lib/boardview.py:199-212`・`:318-330`。今の入力 `purpose_review` は `workflows/plan-review/works-factory-plan-review.yaml:31-33`）: 判定のまとめが `$purpose-review.output.material` を返りの欄 `purpose_review` にして line へ返し、line が今と同じ配線で plan-review に渡す。中身は今の `purpose-review.json`（`{verdict, reason, findings}` か `{}`）でなく `material.json` なので、読み手は `materialkit.read(path)["reply"]` を読み、`reply` が null（`skipped`・`gave_up`・`failed`）なら今の `{}` と同じに読む。読み方の替えは plan-review の設計書が持つ（報告に書いた）。
- 諦めた時（`status: gave_up`）: 今は `materials_given_up`（`:2696-2699`）が目的の監査も数え、判定の前で line を止めた。新しい形も `status` を返すだけで、止めるのは diagnose（materials.md の 1.6）。

## 2 node の設計シート: purpose-review（目的の監査の役）

### 2.1 役

目的の役が自分で要約した目的の文が、実装に都合よく狭められていないかを判じ、判定の語・理由・作業ツリーで引ける根拠の行を返す。

### 2.2 port

`intake.json` の `view`（← port `base` と作業ツリー。`repo`・`review_rev`）・`values.purpose`（← port `purpose`。`purpose_text`）・`values.lang`（← port `lang`）、拒否の控え（← accept が place に積んだ `rejects-purpose-review.json`）。

### 2.3 組み立ての順（`prompts/purpose-review.md`）

materials.md の 3.1 の並び。素材の欄を持たないので 3 と 8・9 は飛ばす。

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: `rejects-purpose-review.json` に拒否が 1 件以上。`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "purpose-review"))`。
2. `{shared:role-inspector}`（役の定義）。
3. （飛ばす。web も外のコマンドも持たない）
4. 役の 1 段落（決まった文）: 目的の文の監査だけ・差分も局所の所見もほかの素材も渡していない。
5. 道具の段落（決まった文）: Read・Grep・Glob だけ、Bash が無いので git を打てない。`{shared:material-readonly}`。
6. `## Materials` と 3 つの差し込み口: `{purpose_text}` ← `values.purpose.purpose_text`（目的の文の字のまま）、`{repo}` ← `view.repo`、`{review_rev}` ← `view.review_rev`。
7. `## What to do`（決まった文）: 今の graphloops の指示の段（`material-purpose-review.md:35-52`）を英語にした物。差し込み口 `{verdict_ok}`・`{verdict_narrows}` ← `src/viewpoint.py` の定数。
8・9. （飛ばす。返答に `material` の欄が無い）
10. `## Where to point`、観点の前置き（根拠の行は `where` を持たない。決まった文）、`{shared:material-where}`。
11. 言語の 1 文と `{lang}` ← port `lang`（空なら `materialkit.LANG_DEFAULT`）。
12. 結びの 1 文。

`materialkit.prompt_inputs` は materials.md の 2.11 のまま `na_never` などの 4 つの真偽を足すので、（実装では要らなくなった: 7 節）この block の `role_prep.py` がその 4 つの鍵を `when` から外してから `prompt.render` に渡す形を最初は考えた（この md は `{shared:material-na}` を持たないので、外さないと `prompt.render` が「`when` の名が md に無い」で落ちる。`NA` が `never` なので `values` に `na_why` は入らない。hygiene と同じ扱い。自分で決めた。7 節）。

md の本文（英語。この block の 2 つ目の commit でこのまま置く）:

```markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{shared:role-inspector}

You are the purpose-review role. Your only job is to review the purpose text below. You are given neither the target diff, the local findings, nor any other material.

Your tools are Read, Grep, and Glob. You have no Bash, so you cannot run git.

{shared:material-readonly}

## Materials

- Purpose text (summarized by the writer itself, because there was neither a PR description nor a plan to take it from):

{purpose_text}

- Repository: {repo}
- Revision to read: {review_rev}

## What to do

Check whether this purpose text has been narrowed to suit the implementation. Against the actual scope of the change, the issue, and the plan: has the purpose shrunk to fit what is already implemented, and has a requirement that the implementation cannot meet been silently dropped? Write `verdict` as `{verdict_ok}` (no problem) or `{verdict_narrows}` (narrowed). These two values are fixed keys; write them exactly as shown, whatever language the other fields are in.

If the input is insufficient (the purpose text is empty, the files of the revision cannot be read, and so on): the reply shape of this role has no value or field that means "insufficient". So, as the role definition says, start `reason` with the "insufficient" marker and say what is missing. `verdict` cannot be empty, so write `{verdict_ok}`, and leave `findings` empty. The marker at the head of `reason` is the sign that you gave no verdict.

**Each finding must bring evidence that can be looked up in the working tree.** For each one, write `text` (the finding), `cite` (a string that `git grep -F` finds), and `hits` (**the number of lines on which that string appears**; the machine counts with `git grep -cI`, so a string that appears twice on one line counts as 1). **The machine counts the same string again against the revision fixed for this run, and rejects the whole answer if it finds no line, or a number different from yours.** Use strings that are in the files now, not ones from memory. A `cite` short enough to fit on one line makes the count easier to match.

**You may also point out an absence: processing that should exist but is nowhere.** The strongest evidence that a purpose has been narrowed to the implemented scope is often the absence itself. To write it, use as `cite` **a string that exists around the place where the thing is missing** (for example the definition line of the function where the processing should be), and write in `text` that X is missing there. The absence itself cannot be looked up, but the place of the absence can.

**If `verdict` is `{verdict_narrows}`, give at least one finding.** A verdict without evidence is rejected as a whole: a verdict with no evidence never passes the check.

**What you read is the revision fixed for this run**, not a live working tree. You cannot run git, so read the files of the working tree with Read, Grep, and Glob instead. The revision above was frozen from the working tree as it was before the material roles were started (untracked files included), and no material role may change the working tree (the acceptance step compares it before and after). So the files in the working tree have the same content as the fixed revision, and a line number you see with Read is the line number to write as `<path>:<line>` in `text`.

## Where to point

The rows of `findings` in this role have no `where` field: a row has `text`, `cite`, and `hits`, and the place is shown by the `cite` string. The rule below applies when you write a place as `<path>:<line>` inside `text`. You can Read, so you are a role that can read files.

{shared:material-where}

Write `reason` and the `text` of each `findings` row in {lang}. Keep `verdict` (one of the two fixed keys above), `cite` (it must match the file character for character), keys, identifiers, paths, commands, and quoted text as they are.

Return only JSON that matches the output schema.
```

md の中に `$` の字は無い。差し込み口のほかに `{` は無い。会話と retry は prior-decisions.md の 2.3 の終わりと同じ。

### 2.4 返す形

今の `output_format` のまま（`workflows/judge/works-factory-judge.yaml:1012-1030`）:

- `verdict`: 字、enum `[問題なし, 狭めている]`。
- `reason`: 字。
- `findings`: `[{text (1 字以上), cite (1 字以上), hits (0 以上の整数)}]`・各行 `additionalProperties: false`・`required: [text, cite, hits]`。
- 全体 `additionalProperties: false`・`required: [verdict, reason, findings]`。

人に見せる欄は `reason` と `findings` の `text`（判定の材料・plan-review の止めの訳・報告に載る）で、言語は `{lang}`。`verdict` は機械が字で比べる語（`lib/boardview.py:201`・`:211`）、`cite` は作業ツリーの字の写しなので、言語を替えない。

### 2.5 描いた骨組み（例の run の値）

この役が走った run の記録は無い（頭の「例の run」）。今の指示は `workflows/judge/commands/material-purpose-review.md`（62 行。`$purpose-review-prep.output.lang_line`・`.reason`・`.brief_file` を Archon が入れる）と、prep が描く材料のファイル `judge/material-purpose-review-brief.md`（`MATERIAL_HOLES['purpose-review']` の 3 つの節と『条件に当たらない』の節）の 2 か所に在る。run `53e71318-…` の値（`judge/material-view.json` の `review_rev`、作業ツリーのパス、`judge/purpose.json` の `purpose_text`。出典の語だけ仮に `③writer の要約`）で描いた新しい指示:

```markdown
{shared:role-inspector の本文: This role is an inspector. It scores in a context separate from the one that runs this loop; …（6 行）}

You are the purpose-review role. Your only job …（決まった文）

Your tools are Read, Grep, and Glob. You have no Bash, so you cannot run git.

{shared:material-readonly の本文: Do not change a single character of the target's working tree, …}

## Materials

- Purpose text (summarized by the writer itself, because there was neither a PR description nor a plan to take it from):

会話スレッドにピン留めの印を付けてサイドバーの「ピン留め」と「最近のスレッド」の枠に分ける変更（PR #2109）について、(1) PATCH /threads/{id} が title と pinned を同じ本文で受けたとき、…（目的の文の字のまま）

- Repository: ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/worktrees/archon/task-works-factory-line-1792307529854
- Revision to read: ca6a92176835a4eb5cdf516cb989ade948e5bc71

## What to do

Check whether this purpose text has been narrowed to suit the implementation. … Write `verdict` as `問題なし` (no problem) or `狭めている` (narrowed). …（決まった文の 6 段落）

## Where to point

The rows of `findings` in this role have no `where` field: …

Write the `<path>:<line>` of a location (`where`) as a line number in the current file in the working tree. …

Write `reason` and the `text` of each `findings` row in the language of the request (the user's language). …

Return only JSON that matches the output schema.
```

目的の文の中の `{id}` は値の字で、差し込み口ではない（`prompt.render` は値の中を置き換え直さない前提。6 節）。拒否が無い 1 回目の形。

### 2.6 今の指示との差

今の指示は `workflows/judge/commands/material-purpose-review.md`（62 行）と、`lib/judge_accept.py` の `material_prep`（`:2116-2135`）が描く材料のファイルの 2 か所に在る。prior-decisions.md の 2.6 と同じ移し方（材料の節を `## Materials` の行に・『条件に当たらない』の節を外す・却下の段落 2 か所を `{shared:rejected}` 1 回に・作業ツリーを変えるなの句を `{shared:material-readonly}` に・所見の場所の段を `{shared:material-where}` に・言語の 1 行を md の 1 文に・「graphloops のノード p0.purpose_review を、下の元の graphloops の指示書のとおりに行う」と見出しと区切りを消す）はここに繰り返さない。この観点だけの差:

- 移した: 役の定義（md:3-11）を `{shared:role-inspector}` に。今の md は外への検索の決まりを持たない（役が web も外のコマンドも持たない）ので、`{shared:query-rule}` は置かない。
- 移した: 材料の 3 つの節（`out.p0.purpose.purpose_text`・`inputs.review_rev`・`inputs.cwd`）を `## Materials` の 3 行に。md の「［材料: 〜］」の穴（md:38・40）と、材料のファイルを Read で読めという手順（md:27）は要らなくなった。
- 消した: 材料のファイルの『条件に当たらない』の節（`_na_note` の「このノードは条件（applies_cond）を持たず…not_applicable は受け付けが拒む」）。この役の返答は `material` の欄を持たず、`not_applicable` を書く所が無い。今も読ませて意味の無い節だった。
- 移した: 判定の語 2 つ（md:42・44・50 の `問題なし`・`狭めている`）を差し込み口 `{verdict_ok}`・`{verdict_narrows}` に。字は今のまま。足した: 「この 2 語は決まった鍵で、ほかの欄の言語によらず字のまま書け」の句（英語の指示の中に日本語の語が来るので、言い換えて返すのを止める。返答の形〔enum〕は変わらない）。
- 残した: 「足りない時の返し方」（md:44）。「`reason` を『足りない: 』で始めて」は「役の定義が言う『足りない』の印で始めて」にした（印の字は役の定義の断片が持つ。7 節）。
- 残した: 「この役は Bash を持たないので git を打てない。作業ツリーのファイルは固めた版と同じ中身」（md:52 の後半。#221 で足した）。graphloops の「`git -C <リポジトリ> show <版>:<パス>` のように版を指定して読め」（md:52 の前半）は、打てない道具の手順なので消した。
- 残した: 所見の場所の前置き（md:58。根拠の行は `where` を持たない）。受け付けの所見の場所の照らしは `where` と `text` を両方持つ行にだけ当たるので（`materialkit.where_rows`）、この役の返答には当たらない。断片の尾の「受け付けは…拒んで出し直させる」はこの役には起きないが、断片を字のまま使う（共通の断片を観点ごとに割らない）。
- 消した: md:29 の「同じ時に別の素材集めの役も走っている」の断定（prior-decisions.md の 2.6 と同じ）。
- 足した物は上の句 1 つだけ。英語にした（#764）。役の名「目的の審査の役」は "the purpose-review role"。

### 2.7 元の works と graphloops の同じ場面

族の形の差は materials.md の 9 節。この観点だけの差:

- 元の works の `works/blk-material/commands/purpose-review.md`（9 行）は、engine が描いた graphloops の指示書（`prompt_file`）を Read させる薄い md で、返す JSON の形も指示書に貼った。工場は指示書を md に写し、値を材料のファイルにした（#76）。新しい形は値も指示に入れる。
- 元の graphloops の指示書は、元の works も工場も a1202d0（0.21.0）の写し。工場はそこに 3 つを足した: 足りない時の返し方（`verdict` を `問題なし`・`findings` を空・`reason` の頭に印）・Bash を持たない役の読み方（作業ツリーのファイルを Read で読む。固めた版と同じ中身）・根拠の行は `where` を持たないの前置き（どれも #221 の書き直しで入った）。この block も持つ。
- graphloops の今の指示書（`~/src/claude-plugins/graphloops/prompts/review-loop/p0.purpose_review.md`）は、3f5a6a82（2026-10-19）で判定の語を ASCII の鍵 `ok`・`narrows` に替え、読む版の穴を `hist.snapshot.rev` にした。工場は替えていない（（未確認）: 工場の履歴に外した記録は無い。写した版がこの替えより前だった）。工場の読み手（`lib/boardview.py:201`・`:211`、`lib/design.py:77`）が日本語の字で比べるので、この作り直しでは語を替えない（7 節）。
- graphloops の節の宣言（`graphs/review-loop.json` の `p0.purpose_review`）は `optional: true`・`fresh_context: true`・回す条件 `purpose_review_due`（2 周目からは出典のファイルの変わりと記録の監査の形でも回す）。工場は 1 run = 1 周（持ち主の決め carry）なので 1 周目の枝だけが効き、新しい形も同じ。
- 受け付けの順（作業ツリー・所見の場所・`post_check` の `purpose_findings_cited`）は元の works・graphloops・工場で同じ。工場の数え直しは置き場を読了の記録の在りかに読み替えた（`_cite_errors` の `jdir`）が、指し先を持たない根拠の行はその道に入らないので、この block は読み替えごと持たない。

この block が両方より良く、残す物: 判定の根拠を、役を起こす前に固めた版で機械が数え直す（graphloops と同じ）・Bash を持たない役に読める道を正しく教える（graphloops の指示は打てない git を指していた）・回さない run にも理由つきの状態を返す。

### 2.8 受け付け

materials.md の 4 節の順のまま。観点の前の照らしは無く、後の照らしはこの文書の 4 節の 1 つ。

- 拒む物: JSON のオブジェクトでない返答・役が作業ツリーを変えた（accept が、役を起こす前の写し `tree.json` と今の作業ツリーを、`accept.status_keys(GUARDED)` の欄で比べる〔materials.md の 4 節の 2〕。`GUARDED` が真〔AI の node が `mutates_checkout: false` を持つ〕なので、Archon が node の前後の `git status --porcelain` を自分で照らす。だから accept は比べる欄から `porcelain` だけを外し、残りの欄〔HEAD・枝・git が無視するファイルなど〕を比べる）・`verdict` が `狭めている` なのに `findings` が空・根拠の行の形の外れ（dict でない・`cite` が空・改行や NUL を含む）・`cite` が読む版に 1 行も無い・`hits` が数え直しと違う・数え直せない（git が動かない・版を解決できない）。
- 所見の場所（4 節の 4）と素材の欄（4 節の 6）の照らしは、この返答には当たる物が無い（`where` を持つ行が無く、`MATERIALS` が空）。
- 返答の形（`output_format`）の外れは Archon が node の段で拒む。
- 3 回目の拒否でループを抜ける。`finish` が `status: gave_up`・`reason` に最後の拒否の文を書く。素材は書かない（`materials` は `{}`）。

### 2.9 試験

- standalone の fixture（`blocks/purpose-review/fixtures/`）:
  - `standalone.stubs.yaml`: `fixture.inputs` は `base: ""`・`purpose: '{"purpose_text":"…目的の文…","source":"③writer の要約","known_weaknesses":[],"source_files":[]}'`・`entry: ""`・`lang: ""`。AI の node `purpose-review` だけを台本の返答（`verdict: 問題なし`・`reason` 1 行・`findings: []`）で差し替える。`finish` の `status` が `ran`。
  - `gave-up.stubs.yaml`: 台本の返答が `verdict: 狭めている`・`findings: []`（台本は 1 周分。3 回の数えは単体の試験 `test_three_rejections_give_up` が見る）。`finish` の `status` が `gave_up`、run は `completed`。
  - `skipped.stubs.yaml`: `purpose` の `source` を `①PR 説明` にする。AI の node は走らず、`finish` の `status` が `skipped`、`reason` が「目的テキストの出典が ①PR 説明——…」。
- `tests/blocks/purpose_review/test_purpose_review.py`（materials.md の 8 節の block の試験）:
  - 写す元 `lib/tests/test_judge_accept.py::MaterialCase.test_purpose_review_findings_must_cite_the_version`: 4 つの返答（数の合う根拠・版に無い字・数の合わない申告・根拠の無い『狭めている』）で、1 つ目だけが `material.json` の `reply` に載り、ほかは拒みの文に今の字（「'どこにも無い字列' が現物に 1 件も無い」など）を含む。根拠の字は試験のリポジトリで固めた版に在る字にする。
  - 写す元 `DueCase.test_purpose_review_only_for_writer_summary`: 出典が `③writer の要約` なら `due` が真、`①PR 説明` なら偽。足す: `purpose` が null なら偽で、`reason` が「目的の文が渡されていない」で始まる。差分が空で `entry` の在る run でも、出典が ③ なら真（入口の印を読まない）。
  - 足す: `material.json` が `materialkit.read` を通り、`materials` が `{}`、`reply.verdict` が受けた語。`skipped` の道で `reply` が null。
  - 足す（語の照らし）: `VERDICTS` が block の YAML の AI の node の `verdict` の enum と同じ並び。`WRITER_SOURCE` が `shared:purpose.schema.json` の `source` の enum に在る。
  - 足す（起こし方の照らし）: AI の node の `model`・`allowed_tools`・`sandbox`・`idle_timeout`・`mutates_checkout`・`retry` が、今の `tests/workflows/test_judge.py:88` の purpose-review の行（`"sonnet", "medium", READ, BASE, True, …`）が照らす物と同じ。
- 指示の比べ（README の 11.4）: 実装では置かなかった（7 節。`test_prompts.py` と `src/oldbrief.py` は無い）。当初の案は次の 2 つの commit:
  - 1 つ目の commit: `prompts/purpose-review.md` を、今の md の `$purpose-review-prep.output.lang_line` を `{lang_line}` に、`.reason` を `{reason}` に、`.brief_file` を `{brief_file}` に替えた日本語の字で置く。prep は 1 つ目の commit だけ、この 3 つを値に入れ（prior-decisions.md の 2.9 と同じ作り方）、`src/oldbrief.py` の `brief(view, values)` で `material-purpose-review-brief.md` を書く。試験は (a) 組んだ指示が今の md に同じ 3 つの値を入れた字と同じ、(b) `oldbrief.brief` の字が、同じ試験のリポジトリと置き場で今の `judge_accept.material_prep(jdir, "purpose-review", repo, review_md)` が書いた材料のファイルと同じ（本物の run の材料のファイルが無いので、今の関数の出力と比べる。自分で決めた。7 節）。
  - 2 つ目の commit（英語）: 1 つ目の試験と `src/oldbrief.py` を消し、2.5 の値で組んだ新しい指示と、今の md と材料のファイルを並べた物を PR に載せ、2.6 の差の一覧どおりかを審査に出す。
- 守る keep-essence の番号: 無い。守るのは「目的の文の監査の判定に、固めた版で数え直した根拠が付く」と「裏取りを通った『狭めている』で独立設計を止める材料が plan-review に届く」で、上の数え直しの試験と、plan-review の側の試験（`tests/workflows/test_plan_review.py` の目的の監査を読む試験。読み手の block に残す）が見る。
- 終わりの条件の命令（1 モジュールずつ。materials.md の 8 節と同じ）:

```sh
uv run --isolated python3 -m unittest lib.tests.test_materialkit
uv run --isolated python3 -m unittest discover -s tests/blocks/purpose_review -t .
uv run --isolated python3 -m unittest tests.layers.test_block_shape
```

## 3 script の node

materials.md の 6 節の雛形のまま。この block だけの物:

- `intake.py` が読む入力は `INPUTS_BASE`・`INPUTS_PURPOSE`・`INPUTS_ENTRY`・`INPUTS_LANG` の 4 つ。`purpose` は `ports.json(os.environ.get("INPUTS_PURPOSE"), "shared:purpose.schema.json")`、ほかは `ports.text(…)`。値の dict の鍵は `base`・`purpose`・`entry`・`lang`。
- `role_prep.py`: 4 つの鍵を外す 1 行は要らない（7 節。`NA_PARAGRAPH = False` で `materialkit.prompt_inputs` が `na_*` を足さない）。
- 1 つ目の commit だけの材料のファイルの書きは、実装では置かなかった（7 節）。

## 4 受け付けの文（観点の後の照らし `src/cited.py`）

今の `purpose_findings_cited`・`_cite_errors`・`_count_in_version` の字のまま。頭の `"{nid}: "`（`p0.purpose_review: `）は `"観点 purpose-review: "` に替える（materials.md の 2.8 の「ノード {nid}」→「観点 {name}」と同じ替え）:

- `観点 purpose-review: 『狭めている』のに findings が空——**判定には作業ツリーで引ける根拠を 1 件以上付けろ**（欠落を指摘したいなら、欠けている場所の周辺に実在する字列を cite にして、そこに在るべき物が無いことを text に書く）`
- `観点 purpose-review: 指摘の根拠が作業ツリーで裏取りできない: ` + 行ごとの文の `; ` つなぎ。行ごとの文は今の字（`findings[<i>]: 素の文字列は受け取らない…`・`findings[<i>]: cite（作業ツリーで引ける字列）が空`・`findings[<i>]: cite に改行が入っている——数えは行単位の git grep なので…`・`findings[<i>]: cite / target / where に NUL が入っている…`・`findings[<i>]: '<cite の頭 40 字>' が現物に 1 件も無い…`・`findings[<i>]: '<cite の頭 40 字>' の件数の申告 <hits> が数え直し <n> と違う`）。
- 数え直せない時: `観点 purpose-review: 指摘の根拠を数え直せない（git が動かない）——確かめられないものを合格にはしない` ほか、今の `_count_in_version` の 3 通りの字。

『狭めている』の字は `VERDICT_NARROWS` から入れる。

## 5 単独で呼ぶ

```sh
bin/works-factory <読ませるフォルダを blocks/ にする引数（名は土台の PR で決める）> workflow run works-factory-purpose-review \
  --input purpose='{"purpose_text":"…目的の文…","source":"③writer の要約","known_weaknesses":[],"source_files":[]}' \
  --input base=
```

作業ツリーは Archon の cwd（対象のリポジトリ）。`purpose` は値そのものでも、`purpose.json` のパスでもよい（README の 4.2）。出典が `③writer の要約` でない目的を渡すと、役を起こさずに `status: skipped` で返る。

## 6 未確認

- 土台の役の定義の断片 `role-inspector` の英語の字で、「足りない」の印が何と書かれるか（2.3 の md はその字を名指さず「役の定義が言う印」と書いた）。
- 土台の `prompt.render` が、差し込んだ値の中の `{…}` と `$…` を置き換え直さないか（目的の文は人の字なので `{id}` や `$` を含みうる。2.5）。materials.md の 3.1 は値に `$` の直後の英字を置かないと書くが、人の字を入れる値の扱いは決めていない。
- 起動の殻で `blocks/` を読ませる引数の名と、5 節の命令の正確な形（prior-decisions.md の 6 節と同じ）。

## 7 自分で決めた事（この block だけ）

- 判定の語 `問題なし`・`狭めている` を今の日本語の字のまま残す。訳: 読み手が字で比べる（`lib/boardview.py:201`・`:211` の `"狭めている"`、`lib/design.py:77`）。graphloops は 3f5a6a82 で ASCII の鍵に替えたが、替えると読み手の lib と YAML の enum を同時に替えることになり、この作り直しの「振る舞いを変えない」と「`lib/` は読むだけ」（README の 11.1）に触れる。英語の md には `{verdict_ok}`・`{verdict_narrows}` で入れ、字のまま書けと言う。ASCII に替えるのは後に別に扱う。
- 骨組みを、役が走っていない run の値と仮の出典の語で描く。訳: 記録の在る 148 本の run のどれでもこの役は走っておらず、本物の指示が無い。値の形（目的の文・作業ツリーのパス・固めた版）は本物の run の物を使い、仮に置いたのは出典の語だけにした。
- 1 つ目の commit の材料のファイルの比べを、本物の run の物でなく、今の `judge_accept.material_prep` が同じ試験の置き場で書いた物と比べる。訳: 比べる本物の材料のファイルが無い。今の関数は作り直しの間は残る（materials.md の 1.5）ので、同じ値から今と同じ字が出ることを直に照らせる。
- 『条件に当たらない』の 4 つの真偽を、族の部品の口（`materialkit.prompt_inputs`）を変えずに、この block の `role_prep.py` で `when` から外す。訳: この md は素材の書き方も `{shared:material-na}` も持たない（返答に `material` の欄が無い）。materials.md の 2.11 のとおり真偽を足したまま渡すと、土台の `prompt.render` が「`when` の名が md に無い」で落ちる（README の 5.2）。hygiene も返答に `material` の欄を持たず同じ所に当たるので、2 本の扱いを hygiene.md の 3 節の形（殻の 1 行）にそろえた。族の部品の口を変える直し（`material` の欄を持たない観点には足さない）は materials.md の 2.11 の直しとして報告に書いた。
- `purpose` が null の時の回さない訳を「目的の文が渡されていない——監査するのは writer が要約した目的（③writer の要約）だけ」にする。訳: 今の `purpose_review_due` は目的の文が無いと出典を `None` と書いた（「目的テキストの出典が None——」）。block は port で受けるので、渡されていないことをそのまま言う方が直せる。回さない決めは今と同じ。
- 数え直しの部品を `lib/` に置かず、block の `src/cited.py` に写す。訳: 指し先を持たない根拠の行を版で数える道を使うのはこの観点だけ（`wrote_refs` の道は fix の側。README の 9.2 で `judge_accept` を割る）。憲法の 4。
- 根拠の拒みの文の頭を `観点 purpose-review: ` にする。訳: 今の頭はコピーした graph の節の id（`p0.purpose_review`）で、新しい形に graph の節は無い。materials.md の 2.8 の替えと同じ。
- 固めた目的の schema（`purpose.schema.json`）の中身をここで決め、`blocks/.shared/schemas/` に置く（external-standards も同じ字を使う）。訳: materials.md の 1.2 は名と欄だけを書き、中身を決めていない。欄と出典の語は今の目的の役の `output_format` のまま（`means` は目的の block が別のファイルにする）。出典の語を enum で縛るので、目的の block が語を替えれば読みの段で名指して落ちる（黙って `skipped` にならない）。
- 「足りない」の印の字を md に書かず、役の定義の断片の言い方に任せる。訳: 印は inspector の役の定義の決まり（今の `lib/agents/inspector.md` の 3 つ目の箇条）で、機械はこの印を読まない（`lib/` と `workflows/` に「足りない: 」を比べる所は無い）。字を md に写すと、断片の英語の字と食い違いうる。
- 実装で main の決まりに合わせた事（実装者が決めた）:
  - `blocks/.shared/schemas/purpose.schema.json` から `$schema` を外し、`description` を足した。訳: `ports.json` が照らしの知らない語 `$schema` を拒む（`KNOWN_KEYWORDS` に無い）。
  - `role_prep.py` に 4 つの鍵を外す 1 行は要らなかった。訳: main の `materialkit.prompt_inputs` が `NA_PARAGRAPH` が偽の観点には `na_*` を足さない。`viewpoint.NA_PARAGRAPH = False`（`tests/blocks/materials/test_viewpoints.py` が名を要る）。
  - 英語の md の「started in a new conversation」を外した。訳: 輪が `fresh_context: false` で、2 回目からは同じ会話を続ける。「新しい会話」と書くと事実に反する（調整役の知らせ）。輪は prep → 役 → accept の 1 本道で、同じ層に 2 つの node は並ばない。
  - 「purpose」の port の既定は文字列 `"null"`。訳: `ports.json` は空の字を拒み、Archon は省いた入力に既定を入れる。
  - `skipped.stubs.yaml` は AI の node を `reached` に入れない。status と reason の字は `tests/blocks/purpose_review` が見る。
