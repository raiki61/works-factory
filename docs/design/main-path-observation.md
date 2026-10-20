# block の設計書: main-path-observation（主経路の実行観測）

- 何の話か: 対象差分が利用者から見える経路か外部との継ぎ目を変える時に、その経路を実際に 1 回動かし、通った値を観測させる素材の観点「主経路の実行観測」を、単独で呼べる block `workflows/main-path-observation/` にする設計。族の共通の形は [materials.md](materials.md)、写す手本は [prior-decisions.md](prior-decisions.md)。
- 決めたこと: 今の judge の `material-route` の 1 列と `main-path-observation-loop`（prep・役・accept）を、materials.md の 5 つの node の block にする。入力は共通の 3 つ（`base`・`entry`・`lang`）だけ。判定から入る run では役を起こさず、出どころつきの `not_applicable` を機械が書く。『条件に当たらない』の扱いは `cond` で、当たる条件はいつも真（機械は経路かを決められないので触れる側に倒す。今と同じ）。観点の後の照らしは今の `main_path_observed`（見たと言う状態は観測した値を 1 つ以上持つ）を `src/viewpoint.py` に写す。指示は 1 本の英語の md にし、材料のファイルを無くす。振る舞いは変えない。
- 持ち主に求めること: なし。
- 読む人と使い方: この block を作る実装者（1〜3 節の名と順をそのまま作る）。素材の観点の残りの 10 本の 1 本（README の 11.1 の 1 波目）。急ぎの度合い: 族の部品（`lib/materialkit.py`）と 1 本目の観点 prior-decisions を入れる PR の後なら、ほかの観点を待たずにいつ作ってもよい（ほかの block はこの block を待たない。読み手の diagnose は 2 波目）。

この文書の語は README・materials.md・prior-decisions.md の頭の物を使う（「判定から入る run」〔差分が空で依頼が 1 件以上の run。line が始めの記録から決め、port `entry` に出どころの文を入れて知らせる。空でない `entry` がその印〕・「周」は materials.md の頭）。ほかに:

- line と始めの記録: line は工場のメイングラフ。run の始めに、差分の根（`diff_base`）・言語・依頼の件数・判定から入る run かを「始めの記録」（`start.json`）に書き、block には port の値として配る。この block は始めの記録を読まず、line が配った `base`・`entry`・`lang` だけを受ける。

- P3: 元の graphloops の段の名で、修正の段（工場の fix）。今の条件の「前の周の P3 が何かを直した周」は、前の周の修正が触れたファイルが在る周のこと。工場は 1 run = 1 周なので、いつも 0 件。

- 観測の役（main-path-observation）: 対象差分が変えた経路を動かして通った値を観測し、観測の行と素材の状態を返す AI の役。道具は Read・Grep・Glob・Bash・WebSearch・WebFetch。Bash は網の開いた sandbox の中で走り、写しは一時の置き場に作る（今の `test_run_launch`）。
- 観測の行: 返答の `observed` の 1 行 `{path, value}`（動かした経路と観測した値）。`where` を持たないので、所見の場所の照らし（`materialkit.where_rows`）には当たらない。
- 見たと言う状態: `materialkit.OBSERVED_STATUS`（`found` と `clean`。今の `lib/judge_accept.py:131`）。
- 例の run: 本物の run `53e71318-ac9f-4468-ae72-5f6ed569a667`（対象 <owner>/<repo>。置き場 `~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-…/judge/`）。差分の在る run（23 ファイル）で、観測の役は 1 回目で受け付けを通った（`material-main-path-observation.json` の `materials.main_path_observation.status` が `awaiting_human`。実 DB と実ブラウザが sandbox に無く、模擬の層までの試験 3 本と「未観測」の 1 行を `observed` に 4 行書いた。`rejects-main-path-observation.json` は無い）。同じ対象の run `17ee8ecc-717a-4dc7-92b6-25ecd08fa15b` も同じ形の材料を持つ。

## 1 block の全体

### 1.1 役

対象差分が変えた、利用者から見える経路か外部との継ぎ目を、作業ツリーの外の写しで実際に 1 回動かし、通った値を観測する。テストの緑は観測に数えない。動かせなければ人待ちの状態と、人が何を動かして何を見ればよいかを書かせる。機械が、作業ツリーを変えていないか・見たと言う状態が観測の行を持つか・素材の欄が決まりに合うかで受け付ける。判定から入る run では役を起こさない。

### 1.2 port

入力（YAML の `inputs:`）: materials.md の 1.2 の共通の 3 つだけ。

- `base`・`entry`: materials.md の 1.2 の字のまま。
- `lang`: `text: 人に見せる欄（material の detail・checked・reason と、observed の path・value）の言語。空は依頼の言語`。既定 `""`。block は依頼を受けないので、空の時に `{lang}` へ入るのは言語の名でなく、決まった英語の文 `materialkit.LANG_DEFAULT`（"the language of the request (the user's language)"）で、役がその文を読んで書く言語を決める（materials.md の 2.1・2.11）。

足す入力は無い。今の材料の穴（`MATERIAL_HOLES['main-path-observation']`、`lib/judge_accept.py:1735`）は `loop.diff_file`・`loop.changed_files_file`・`inputs.cwd` の 3 つで、どれも `view` から入る。

出力（`returns: finish`、`outcome_field: ok`）: materials.md の 1.2 の 5 欄だけ。`material.json` の `reply` は受けた返答（`material`・`observed`）、`materials` は `{"main_path_observation": <返答の material>}`。

今との違い: 今は入力を `judge/start.json` から名で開き、回すかを `material-route` が決め（`main_path_observation_due`）、回さない時の埋めは diagnose-prep の `fill_materials` が写した。受けた返答は `judge/material-main-path-observation.json` に書き、判定役は返答の全体を `out.p1.main_path_observation` の穴で読んだ（`lib/judge_accept.py:2764-2795` の `_diagnose_ctx`）。

### 1.3 node の並び（`workflows/main-path-observation/works-factory-main-path-observation.yaml`）

materials.md の 1.3 の雛形の `<観点>` を `main-path-observation` にした物。

1. `intake`（script `intake.py`）: port を読み、対象差分を取り、回すかを決め（判定から入る run でなければ回す）、回す時は作業ツリーを写す。返り `{due, reason}`。
2. `main-path-observation-loop`（`loop_group`、最大 3 回、`fresh_context: false`、`until_bash: done=$main-path-observation-accept.output.done; test "$done" = true`、`when: $intake.output.due == true`）
   - `main-path-observation-prep`（script `role_prep.py`。`with:` を持たない）: 指示を組む。返り `{prompt}`。
   - `main-path-observation`（AI）。`prompt: "$main-path-observation-prep.output.prompt"`・`depends_on: [main-path-observation-prep]`。起こし方は今の `test_run_launch`（`workflows/judge/works-factory-judge.yaml:1494-1510`）を字のまま展開する（中身は [test-double-fidelity.md](test-double-fidelity.md) の 1.3 と同じ。注記の替え方も同じ）。`retry: {max_attempts: 2, on_error: all}`。`mutates_checkout:` は今と同じく置かない。`output_format` は今のまま（2.4）。
   - `main-path-observation-accept`（script `role_accept.py`。`with: {reply: $main-path-observation.output}`）: 返り `{ok, done, reason}`。
3. `finish`（script `finish.py`。`depends_on: [intake, main-path-observation-loop]`・`trigger_rule: all_done`）: `material.json` を書き、出力を返す。どの段が落ちても落ちない。

### 1.4 place のファイル

materials.md の 1.4 の名だけ: `intake.json`・`view.json`・`diff.patch`・`changed-files.txt`・`tree.json`・`main-path-observation-prompt-<n>.md`・`rejects-main-path-observation.json`・`rejects-main-path-observation.md`・`accepted.json`・`material.json`。観点だけの控えは無い。

1 つ目の commit だけ、`material-main-path-observation-brief.md`（今の材料のファイルと同じ字）も書く（2.9）。2 つ目の commit で書かなくなる。1 つ目・2 つ目の commit は README の 11.4 の指示の比べの 2 段: 1 つ目は md を日本語のまま置いて今の指示と同じ字になることを試験で照らし、2 つ目で md を英語にしてその試験と `src/oldbrief.py` を消す。

### 1.5 コードの置き場

- `workflows/main-path-observation/src/__init__.py`（空）。
- `workflows/main-path-observation/src/viewpoint.py`: materials.md の 5.1 の宣言。中身:
  - `NAME = "main-path-observation"`
  - `MATERIALS = ("main_path_observation",)`
  - `GUARDED = False`（今の accept の `with: {status_guarded: false, …}`。`works-factory-judge.yaml:1691`）
  - `NA = "cond"`、`NA_REASON = "対象差分は利用者から見える経路・外部との継ぎ目を変えていない"`（今の `MATERIAL_NODES['p1.main_path_observation']['na_reason']`、`lib/judge_accept.py:1686-1691` の字のまま）。当たる条件がいつも真なので今は使われない（test-double-fidelity.md の 1.5 と同じ）
  - `NOUN = "主経路の観察"`（今の `main_path_observation_due` の訳の名詞。`:1578-1586`）
  - `due(view, values)`: `materialkit.is_entry_run(view, values)`（`entry` が在り、対象差分が空）なら `materialkit.entry_skip(NOUN)`。そうでなければ `materialkit.Due(True, "主経路の観察は、判定から入る run でなければ run ごとに 1 回回す（1 run は 1 周で、いつも初回。差分が利用者から見える経路に触れるかは機械が決められないので、触れる側に倒す）")`（自分で決めた。7 節）。
  - `fill(view, values, due)`: `{"main_path_observation": materialkit.fill_entry(values["entry"], None)}`（`due` が偽になるのは判定から入る run だけ）。
  - `applies(view, values)`: `materialkit.Due(True, "差分が利用者から見える経路に触れる")`（今の `user_path_touched` が、機械が真に倒した `touches_user_path` で返す字。`:1474-1486`・`due_view` の `:1357`）。
  - `judged_na(view, values)`: `return False`。
  - `values(view, values)`: `{"diff_file": view.diff_file, "changed_files_file": view.changed_files_file, "repo": str(view.repo)}`。
  - `when(view, values)`: `{"spawns": False}`。
  - `before(view, values, reply, place)`: `return None, reply, False`。
  - `after(view, values, reply, place)`: 今の `main_path_observed`（`:2138-2143`）の写し。`material = reply.get("material")`、`st = material.get("status") if isinstance(material, dict) else None`（`material` が object でなくても落ちない）、`st in materialkit.OBSERVED_STATUS and not reply.get("observed")` なら 3 節の文を返す。ほかは `None`。今は `Reject` を上げたが、宣言の口（materials.md の 5.1）は文を返す形なので、文を返す。
  - `after_accept(reply, place)`: 何もしない。
  - `materials_of(reply)`: `{"main_path_observation": reply["material"]} if isinstance(reply.get("material"), dict) else {}`（今の `writes` の `materials.main_path_observation ← material`）。
  - `report_lines(doc)`: `reply` の `observed` の行ごとに `f"  - 観測: {oneline(path)} → {oneline(value)}"`。`reply` が null か行が無ければ `[]`。
- `workflows/main-path-observation/src/oldbrief.py`（1 つ目の commit だけ）: 今の材料のファイルを同じ字で組む `brief(view) -> str`。
- schema のファイルは無い。
- 使う `lib/`: `materialkit`（`OBSERVED_STATUS` も）・`rolekit`・`oneline`。

### 1.6 つなぎ方（graph の側。block には書かない）

- 判定のまとめ（`workflows/judge/`）: `include: works-factory-main-path-observation`、`depends_on` は materials.md の 1.6。`with:` は `base`・`entry`・`lang`（[test-double-fidelity.md](test-double-fidelity.md) の 1.6 と同じ作り手）。
- 読み手: diagnose だけ。
  - port `materials` を `materialkit.assemble` で 15 欄にそろえ、素材 `main_path_observation` を読む。素材が `awaiting_human` なら、判定役は人への問い（`awaiting`）を必ず載せる（今の判定役の指示の「素材が awaiting_human なら awaiting を必ず載せろ」、`DIAGNOSE_EXCERPT` の `:2717`）。これが今の「人待ちが人に届く」道で、新しい形でも diagnose の設計書が持つ。
  - 判定役の材料の「主経路の実行観測」の穴（今の `{{?out.p1.main_path_observation}}`）は返答の全体（`material` と `observed`）だった。新しい形では同じ `material.json` の `reply` の欄から取る。
- ほかに返答の欄を読む物は無い（`lib/` と `workflows/` を `observed`・`main_path_observation` で探した。`docs/works-parity.md` の S042「問いが測れなかった素材の名なら問いが無くても当てる」は承認ノードの側の決めで、素材の名を読むだけ）。

## 2 node の設計シート: main-path-observation（観測の役）

### 2.1 役

対象差分が変えた経路を実際に 1 回動かし、通った値の観測の行と素材の状態を返す。動かせなければ人待ちと、人が何をすればよいかを返す。

### 2.2 port

`intake.json` の `view`（`diff_file`・`changed_files_file`・`repo`）・`values.lang`、拒否の控え（`rejects-main-path-observation.json`）。`values.entry` は intake だけが読む。

### 2.3 組み立ての順（`prompts/main-path-observation.md`）

materials.md の 3.1 の並び。

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: 拒否が 1 件以上。`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "main-path-observation"))`。
2. 役の定義の断片は置かない（今の md の頭は外への検索の決まりの塊だけ）。
3. `{shared:query-rule}`。`spawns: false`。
4. 役の 1 段落（決まった文）。
5. 道具の段落（決まった文）と `{shared:material-readonly}`。
6. `## Materials` と 3 つの差し込み口: `{diff_file}`・`{changed_files_file}`・`{repo}`（← `view`）。
7. `## What to do`（決まった文）: 今の graphloops の指示の段（`material-main-path-observation.md:38`）を英語にした物。
8. `{shared:material-status}`。
9. `## Whether you may write not_applicable` と `{shared:material-na}` — 入るのはいつも `na_cond_true` の段落。`{na_why}` ← 「差分が利用者から見える経路に触れる」。
10. `## Where to point`、前置きの 1 文（決まった文。この返答には `where` の欄が無い）、`{shared:material-where}`。
11. 言語の 1 文と `{lang}`。
12. 結びの 1 文。

md の本文（英語。2 つ目の commit でこのまま置く）:

```markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{shared:query-rule}

You are the main-path-observation role. Your only job is to run, once, the path that the target diff changes, and to observe the values that pass through it. You are given neither the local findings nor any other material.

Your tools are Read, Grep, Glob, Bash, WebSearch, and WebFetch. Bash runs inside a sandbox, and its network is open. Make any copy you need for running things in a temporary folder (create it with `mktemp -d`); the wrapper stops writes to the target's working tree.

{shared:material-readonly}

## Materials

- Target diff (Read it): {diff_file}
- List of changed files (one file per line; Read only what you need): {changed_files_file}
- Repository: {repo}

## What to do

If the target diff changes a path that users can see, or a seam with the outside, **actually run that path once and observe the values that passed through it**. What you observe is the real thing that flowed through the same path as in production, not a test turning green. Do not treat a path you did not run as verified: every other viewpoint reads the diff, and defects that only appear when the code runs (behavior specific to the runtime environment, values altered by a middle layer, rendering) do not appear however many times the diff is read.

- Put each path you ran, with the value you observed on it, in `observed` (`path` and `value`, one row per path).
- `found` and `clean` say that you observed something, so they need at least one row in `observed`; the acceptance step rejects them without one.
- If you cannot run the path (there is no environment, no permission, or it needs real hardware), write `awaiting_human`, and say in `material.reason` why, and what a person has to run and look at. It reaches a person, who decides whether there is really no way to run it.

{shared:material-status}

## Whether you may write not_applicable

{shared:material-na}

## Where to point

This answer has no `where` field. If you name a place in a file in `material.detail`, `material.checked`, or `material.reason`, write it as follows.

{shared:material-where}

Write `material.detail`, `material.checked`, `material.reason`, and the `path` and `value` of each `observed` row in {lang}. Keep keys, enum values, identifiers, paths, commands, and quoted text as they are.

Return only JSON that matches the output schema.
```

md の中に、`$` の直後に英字か `{` が続く字は無い。差し込み口のほかに `{` は無い。

会話と retry: prior-decisions.md の 2.3 の終わりと同じ。

### 2.4 返す形

今の `output_format` のまま（`workflows/judge/works-factory-judge.yaml:1660-1685`）:

- `material`: prior-decisions.md の 2.4 と同じ形。
- `observed`: `[{path, value}]`・各行 `additionalProperties: false`・`required: [path, value]`・`path` と `value` は `minLength: 1`。
- 全体 `additionalProperties: false`・`required: [material, observed]`。

人に見せる欄は `material.detail`・`material.checked`・`material.reason`・`observed` の `path`・`value`（判定の材料に載り、`awaiting_human` の `reason` は人への問いの元になる）で、言語は `{lang}`。`observed` の中のコマンドとパスは字のまま。

### 2.5 描いた骨組み（例の run の値）

例の run では、今の指示は `workflows/judge/commands/material-main-path-observation.md`（47 行）と、役が Read した `judge/material-main-path-observation-brief.md`（19 行）の 2 か所に在った。新しい指示はこの 2 つを 1 本にする:

```markdown
{shared:query-rule の本文: Rules for queries to outside services …（7 行）}

You are the main-path-observation role. Your only job is to run, once, the path that the target diff changes, and to observe the values that pass through it. You are given neither the local findings nor any other material.

Your tools are Read, Grep, Glob, Bash, WebSearch, and WebFetch. Bash runs inside a sandbox, and its network is open. …

{shared:material-readonly の本文: Do not change a single character of the target's working tree, …}

## Materials

- Target diff (Read it): ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-ac9f-4468-ae72-5f6ed569a667/judge/diff.patch
- List of changed files (one file per line; Read only what you need): ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-ac9f-4468-ae72-5f6ed569a667/judge/changed-files.txt
- Repository: ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/worktrees/archon/task-works-factory-line-1792307529854

## What to do

If the target diff changes a path that users can see, or a seam with the outside, …（決まった文と箇条 3 つ）

{shared:material-status の本文: How to write `material`: `status` is one of the following. …}

## Whether you may write not_applicable

The condition of this viewpoint holds for this run (差分が利用者から見える経路に触れる), so the acceptance step rejects `not_applicable`. …

## Where to point

This answer has no `where` field. …

Write the `<path>:<line>` of a location (`where`) as a line number in the current file in the working tree. …

Write `material.detail`, … in the language of the request (the user's language). …

Return only JSON that matches the output schema.
```

例の run は 1 回目で通ったので、却下の段落は入らない。`lang` は空。差分と一覧のパスは今の `judge/` の物を描いた（新しい形では block の place の物）。`{na_why}` の字は、今の材料のファイルの末尾の節「このノードの条件 `user_path_touched` はこの周に真（差分が利用者から見える経路に触れる）なので…」の括弧の中と同じ。

### 2.6 今の指示との差

族の共通の差は prior-decisions.md の 2.6 と同じに扱う。材料の 3 つの節と『条件に当たらない』の節の移し方と、「同じ時に別の素材集めの役も走っている」の断定を消した事・「its network is open」を足した事は [test-double-fidelity.md](test-double-fidelity.md) の 2.6 と同じ。この観点だけの差:

- 替えた: 「（台帳に載り、次の周の judge が『動かす手段が本当に無いか』を再審する）」（md:38）を「It reaches a person, who decides whether there is really no way to run it.」に。訳: 工場は 1 run = 1 周で、次の周も盤面の台帳も無い。今の工場で `awaiting_human` が届く先は、判定役が必ず立てる人への問い（1.6）。役に「書いた `reason` が人に読まれる」ことを伝え、`reason` に人が何をすればよいかを書かせる、という文の役目は残した。
- 足した: 「`found` と `clean` は `observed` に 1 行以上要り、無ければ受け付けが拒む」の箇条と、`awaiting_human` の `reason` に「人が何を動かして何を見ればよいか」を書けの句。訳: 今の md は「observed に経路と観測した値」とだけ言い、受け付けの `main_path_observed` の決まりを役が知らずに 1 回拒まれる道が在った。受け付けの決まりは変わらない（自分で決めた。7 節）。後の句は、例の run の役が自ら書いていた形（「人が、…を当てた DB で結合テストを走らせ、実画面で…を見る必要がある」）を指示の側に置いた。
- 足した: `## Where to point` の前置きの 1 文。訳: この返答の欄に `where` は無く、`{shared:material-where}` の「`where`」が何を指すかが役に分からない。今の md は前置き無しで同じ段を置いていた。
- 変えた: 断片 `material-where` の尾の文を、受け付けが照らす範囲（`where` と `text` を持つ行だけ。ほかの行は照らさない）に合わせて狭めた。
- 英語にした（#764）。役の名「主経路の実行観測の役（任せ先）」は "the main-path-observation role"。

### 2.7 元の works と graphloops の同じ場面

族の形の差は materials.md の 9 節。この観点だけの差:

- 元の works の `works/blk-material/commands/main-path-observation.md` は、engine が描いた graphloops の指示書を Read させる薄い md だった（test-double-fidelity と同じ形）。工場は指示書を md に写し、値を材料のファイルにした（#76）。
- 元の graphloops の指示書（`~/src/claude-plugins/graphloops/prompts/review-loop/p1.main_path_observation.md`）と元の works の写し（`works/.shared/core/gl-prompts/prompts/review-loop/p1.main_path_observation.md`）と工場の md の段は、材料の名と「ノード／節」の語のほかは同じ。工場はこの観点の指示に段を足していない。
- graphloops の節の宣言と条件が持ち、工場に無い物:
  - `main_path_observation_due` の「前の周に人待ちだった周」の枝（`loop.last_material.main_path_observation.status == "awaiting_human"` で、経路に触れる差分を 2 周目にもう一度観測させる）: 工場は `loop.last_material.*` をいつも None にした（#76。`due_view` の docstring、`lib/judge_accept.py:1337-1345`。試験 `DueCase.test_view_values` が None を縛る）。1 run = 1 周なので前の周が無く、人待ちは人への問いで人に渡る。新しい形は枝ごと持たない。
  - 「前の周の P3 が何かを直した周」の枝と `carry_reason`（経路を変えていない周は前の観測を持ち越す）: 1 run = 1 周（持ち主の決め carry、#76）で効かない。新しい形は持たない。
  - 指示書の「台帳に載り、次の周の judge が再審する」: 盤面の台帳（awaiting の行）と次の周の再審は工場に無い（#76 で 1 run = 1 周にした）。2.6 の替え方。
  - `delegate.model: sonnet`: 工場は群の名 `'@wf-judge-materials'`（今の試験の表で sonnet・medium。`tests/workflows/test_judge.py:97`）。同じ。
- `post_check: main_path_observed` は graphloops の宣言にも元の works にも在り、工場は字を写した（`lib/judge_accept.py:2138` の docstring「元 rules:2962」）。新しい形も持つ。

この block が両方より良く、残す物: 見たと言う状態に観測の行を機械が求める（graphloops と同じ）・受け付けの決まりを指示が先に言う・作業ツリーを機械が照らす・判定から入る run で回さない素材に出どころつきの理由を書く。

### 2.8 受け付け

materials.md の 4 節の順。観点の前の照らしは無く、後の照らしは 3 節の 1 つ。

- 拒む物: JSON のオブジェクトでない返答・役が作業ツリーを変えた（比べる欄は `porcelain` を含む全部）・見たと言う状態（`found`・`clean`）なのに `observed` が空・素材 `main_path_observation` が無い・`carried_over`・`not_applicable`（`cond_true`）・知らない status・status ごとの要る欄の欠け。
- 所見の場所の照らしは、この返答に `where` と `text` を両方持つ行が無いので、いつも何も拒まない（共通の流れの 4 は回るが当たらない）。
- 後の照らし（4 節の 5）は素材の欄の照らし（4 節の 6）より先に回る（今の `material_take` の順）。だから `clean` で `checked` も `observed` も無い返答は、観測の行の文で拒まれる。
- 3 回目の拒否でループを抜ける。`finish` が `status: gave_up`・最後の拒否の文・素材 `main_path_observation` に `not_run` と同じ訳を書く。

### 2.9 試験

- standalone の fixture（`workflows/main-path-observation/fixtures/`）:
  - `standalone.stubs.yaml`: `fixture.inputs` は `base: ""`・`entry: ""`・`lang: ""`。AI の node だけを台本の返答（`material.status: clean`・`checked` 1 文・`observed` 1 行）で差し替える。`reached` に `finish`。`finish` の `status` が `ran`。
  - `gave-up.stubs.yaml`: 台本の返答が 3 回とも `material.status: clean`・`observed: []`（後の照らしで拒まれる）。`finish` の `status` が `gave_up`、run は `completed`。
  - `skipped.stubs.yaml`: `entry: "人の依頼（standalone）"`。AI の node に届かず、`finish` の `status` が `skipped`。
- `tests/blocks/main_path_observation/test_main_path_observation.py`: materials.md の 8 節の block の試験。
  - 写す元 `lib/tests/test_judge_accept.py::MaterialCase.test_accept_writes_material_file`: `clean` と `observed` 1 行の返答が通り、`material.json` の `role` が `main-path-observation`、`materials` が `{"main_path_observation": <返答の material>}`。
  - 写す元 `MaterialCase.test_accept_rules` の main-path-observation の場合: `clean`・`observed: []` は拒まれ、`accepted.json` が書かれない。拒みの文が「main-path-observation: status=clean なのに観測した値（observed）が 1 つも無い」で始まる。
  - 足す: `found`・`observed: []` も同じく拒まれる。`awaiting_human`（`reason` つき）・`observed: []` は通る。`not_run`（`reason` つき）・`observed: []` も通る。
  - 足す: `not_applicable` は拒まれる（`cond_true`）。組んだ指示に `na_cond_true` の段落と「差分が利用者から見える経路に触れる」の字が入る。
  - 足す: `entry` が在れば `skipped` で、素材が出どころつきの `not_applicable`。
  - 足す: `report` に `observed` の行ごとの「観測」の行が出る。
  - 足す（起こし方の照らし）: block の YAML の AI の node が、今の `tests/workflows/test_judge.py:97` の行（`"sonnet", "medium", INVESTIGATE, DELEGATE, …`）が照らす物と同じ。
- 指示の比べ（README の 11.4）: `tests/blocks/main_path_observation/test_prompts.py`。作り方は [test-double-fidelity.md](test-double-fidelity.md) の 2.9 と同じで、元の md は `workflows/judge/commands/material-main-path-observation.md`、元の材料のファイルは例の run の `judge/material-main-path-observation-brief.md`（末尾の節は `user_path_touched` が真の字）。
- 守る keep-essence の番号: 無い（keep-essence は元の works が「作り替えで外さない」と決めた 12 の仕組み〔README の 10 節〕で、この観点はそのどれにも当たらない）。守るのは「動かしていない経路を見たと言わせない」（`main_path_observed`）で、上の受け付けの試験と `gave-up` の fixture が見る。
- 終わりの条件の命令（1 モジュールずつ）:

```sh
uv run --isolated python3 -m unittest discover -s tests/blocks/main_path_observation -t .
uv run --isolated python3 -m unittest tests.layers.test_block_shape
```

## 3 script の node

materials.md の 6 節の雛形のまま。この block だけの物:

- `intake.py` が読む入力は `INPUTS_BASE`・`INPUTS_ENTRY`・`INPUTS_LANG` の 3 つ。どれも `ports.text(…)`。
- 1 つ目の commit だけ、`role_prep.py` が `src.oldbrief.brief(view)` を place の `material-main-path-observation-brief.md` に書いてから組む。

## 4 受け付けの文

materials.md の 2.8 と 4 節の文に、観点の後の照らしの文を 1 つ足す（今の `main_path_observed` の字。「{nid}: 」を「観点 {NAME}: 」にした。ほかの観点の後の照らしの文と同じ頭）:

- `f"観点 {NAME}: status={st} なのに観測した値（observed）が 1 つも無い——動かして観測した経路と値を observed に書け。動かせなかったなら awaiting_human（何を待つか）か not_run（なぜ飛ばしたか）"`

## 5 単独で呼ぶ

```sh
bin/works-factory workflow run works-factory-main-path-observation \
  --input base=<差分の根の commit>
```

作業ツリーは Archon の cwd（対象のリポジトリ）。役は対象を作業ツリーの外に写して動かすので、動かすのに要る道具（言語の実行系・DB など）が無い PC では `awaiting_human` が返る。

## 6 未確認

- 土台の `prompt.render` が、入らない段落の中の差し込み口を「使われない値」に数えるか（materials.md の 11 節）。
- diagnose の設計書が、素材 `main_path_observation` の `awaiting_human` から人への問いを立てる今の決まり（1.6）を持ち続けるか。この block は素材の状態を返すだけで、問いは立てない。

## 7 自分で決めた事（この block だけ）

- 回す時の訳を、今の `main_path_observation_due` の字（「差分が利用者から見える経路を変え、初回か前の周に人待ちだった周、または前の周の P3 が何かを直した周——成り立つ（round=1・…）」）でなく、「主経路の観察は、判定から入る run でなければ run ごとに 1 回回す（…触れる側に倒す）」にする。訳: [test-double-fidelity.md](test-double-fidelity.md) の 7 節と同じ。前の周の人待ちの枝は 1 run = 1 周で効かない。
- `NA` を materials.md の 5.2 のとおり `cond` にする。訳は test-double-fidelity.md の 7 節と同じ。
- 後の照らしの拒みの文の頭を「観点 {NAME}: 」にする（今の「{nid}: 」の `p1.main_path_observation` を観点の名に）。訳: 節の id（`p1.*`）は写しの graph の名で、block には無い。
- 指示に「`found`・`clean` は `observed` が要る」と「`awaiting_human` の `reason` に人が何をすればよいか」を足す。訳: 受け付けの決まりを役が先に知れば、拒まれる回が減る（拒む決まりは変えない）。人待ちの `reason` は人への問いの本文の元になるので、人が動ける字にする。
- 「次の周の judge が再審する」を「人に届き、人が決める」に替える。訳: 工場に次の周が無く、今の工場で人待ちが届く先の事実に合わせた（1.6）。
- `## Where to point` に前置きを置く。訳: 返答に `where` の欄が無く、断片の「`where`」の指す先を役が取り違えうる。
- `report_lines` に観測の行を 1 行ずつ足す。訳: 素材の 1 行だけでは、何を動かして何を見たか（何を見ていないか）が報告から辿れない。例の run の 4 行目「実ブラウザ・実 DB を通るピン留め経路 → 未観測（環境が無い）」のような行が人の手当ての手がかりになる。
- （実装で決めた事・訳だけ。本文は 1.5・2.3 節）#765:
  - `fill` の件数は `0` でなく `None`（materials.md の 10 節・2.6 の決め。この観点は `request` を持たず、`0` だと「0 件」と誤って言う）。
  - `due` は `values["entry"]` の有無でなく `materialkit.is_entry_run`（`entry` が在り、対象差分が空）で入口の周を決める（materials.md の 10.1）。差分が在れば `entry` が在っても回す。
  - 指示の 1 段落の頭を `You are the main-path-observation role.` にし、`started in a new conversation` を外した。訳: 輪は `fresh_context: false` で、2 回目からは同じ会話の続きに出し直すので、「新しい会話」は事実に合わない。
  - `after` は `material` が object でない返答でも落ちず `None` を返す（後の素材の欄の照らしが「素材が無い」で拒む）。
  - 試験の `test_prompts` は、本物の run の材料のファイルの 3 つのパスを置き換え口（`<DIFF>` など）にして置き、private なパスをリポジトリに入れない。
