# block の設計書: local-review（局所レビュー）

- 何の話か: 対象差分に、宣言したレビューのレンズ（組み込みの skill 3 本と pr-review-toolkit の agent 4 本）を 1 本ずつ起こして所見を集める素材の観点「局所レビュー」を、単独で呼べる block `workflows/local-review/` にする設計。素材の観点の族の 1 本で、族の共通の形は [materials.md](materials.md)、手本の書き方は [prior-decisions.md](prior-decisions.md) に従う。型は [README.md](README.md)。
- 決めたこと: 今の judge の `material-route` の 1 列と `local-review-loop`（prep・役・accept）を、5 つの node の block にする。入力は族の共通の 3 つ（`base`・`entry`・`lang`）だけ。レンズの一覧（今の `LOCAL_REVIEW_SKILLS`）・見ていないレンズの印（今の `lib/diverted.py`）・必須のレンズの照らし（今の `_lens_gap`）・レンズと行の照らし（今の `local_review_covers_lenses`）は block の `src/lenses.py` 1 か所に置く。レンズごとの注意の文（今の一覧の `note`）は Python から md へ移す。見ていないレンズは出力の `report` の行で返し、報告の「未確認のレンズ」の元になる。振る舞いは変えない。
- 持ち主に求めること: なし。
- 読む人と使い方: この block を作る実装者（1〜4 節の名と順をそのまま作る）。素材の観点の残り 9 本と同じ時に作る（README の 11.1 の 1 波目）。

この文書の語は README・materials.md・prior-decisions.md の頭の物を使う。ほかに:

- 判定から入る run と `entry`: 差分が空で、人の依頼の行が 1 件以上ある run（既存のコードへの「これを直して」から始まる run。materials.md の頭）。line がそれと決めた時だけ、port `entry` に出どころの文（例「人の依頼（/path/req.json）」）を入れて渡す。`entry` が空なら差分のある通常の run。この観点は通常の run でだけ回り、判定から入る run では回らない（修正が入るまで依頼の外を見る P1 の役を起こさない。今の `not_request_entry`）。
- 土台: README の 11.1 の 0 の PR（`blocks/` の骨組み・`ports.py`・`prompt.py`・共通の断片・起動の殻の引数を作る、この作り直しの最初の PR）。
- 局所レビューの役（local-review）: 宣言したレンズを Skill と Agent で 1 本ずつ起こし、レンズごとに 1 行の所見を返す AI の役。採点もラベルの確定もしない。道具は Read・Grep・Glob・Bash・WebSearch・WebFetch・Skill・Agent。Bash は網の閉じた sandbox の中で走る。
- レンズ: 1 本の検出器（skill `/code-review`・`/simplify`・`/security-review` と、agent `pr-review-toolkit:code-reviewer`・`silent-failure-hunter`・`type-design-analyzer`・`pr-test-analyzer`）。宣言は `src/lenses.py` の `LENSES`。`required` が偽のレンズ（`/security-review`）は条件 `applies_cond` を持つ。
- 見ていないレンズ: fork（下請けの会話）で走るレンズ（今は `/code-review` だけ）の行が、起こしたのに所見 0 件で返った物。所見が親に届かなかった形と見分けられないので、「所見なし」でなく「見ていない」と印を付けて受ける（`lib/diverted.py` の docstring の実測、run f57a5374）。
- 例の run: 本物の run `53e71318-ac9f-4468-ae72-5f6ed569a667`（対象 <owner>/<repo>。置き場 `~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-…/judge/`）。差分の在る通常の run。局所レビューの役は 1 回目が所見の場所で拒まれ（`rejects-local-review.json` の 1 件）、2 回目で通った（`material-local-review.json` の `materials.local_review.status` が `found`・`count` 21。`/code-review` の行が見ていないと印され、`local-review-lenses.json` が `{"round": 1, "unseen": ["/code-review"]}`）。骨組みの値はここから取った。同じ対象の run `17ee8ecc-717a-4dc7-92b6-25ecd08fa15b` も同じ形。

## 1 block の全体

### 1.1 役

対象差分に、宣言した 7 本のレンズを名指しで 1 本ずつ起こし、レンズごとに 1 行（起こしたか・所見・起こせなかった訳）と素材の状態を返させる。機械が、作業ツリーを変えていないか・必須のレンズを起こしたか・宣言の 1 本に行が 1 本あるか・所見の場所がファイルに在るか・素材の欄が決まりに合うかで受け付ける。fork で走るレンズの空の行は拒まずに「見ていない」と印を付ける。判定から入る run では役を起こさず、理由つきの素材を機械が書く。

### 1.2 port

入力（YAML の `inputs:`）: materials.md の 1.2 の共通の 3 つだけ。`lang` の説明は `text: 人に見せる欄（material の detail・checked・reason、findings の行の failed と items の text・mechanism・measured・false_positive_if）の言語。空は依頼の言語`。

足す入力は無い。今の材料の穴（`MATERIAL_HOLES['local-review']`、`lib/judge_accept.py:1725-1726`）は差分・根・変更ファイル・観点の正本・レンズの宣言で、どれも作業ツリーと `lib/` と block の定数から作れる。レンズの条件 `security_surface_touched` は、今も機械が真に倒している（1.5 の `applies`）ので入力にしない。

出力（`returns: finish`、`outcome_field: ok`）: materials.md の 1.2 の 5 欄だけ。`material.json` の `reply` は受けた返答（`material`・`findings`・`simplify_carried`。見ていないレンズの印を付けた後の写し）、`materials` は `{"local_review": <返答の material>}`。`report` は materials.md の 2.10 の素材の 1 行の後ろに、見ていないレンズごとに 1 行（1.5 の `report_lines`）。

今との違い: 今は `material-route` が `not_request_entry` で回すかを決め、受けた返答を `judge/material-local-review.json` に、見ていないレンズを `judge/local-review-lenses.json` に書き、判定の出力の欄 `review_lenses` が後者のパスを外へ出していた（`lib/judge_accept.py:3885`、`lib/runreport.py:1478-1481` が読む）。新しい形では見ていないレンズは出力の `report` の行で出る（README の 4.1 の「報告の文は事実を持つ block が組む」）。

### 1.3 node の並び（`workflows/local-review/works-factory-local-review.yaml`）

materials.md の 1.3 の雛形の `<観点>` を `local-review` にした物。

1. `intake`（script `intake.py`）: port を読み、対象差分を取り、回すか（判定から入る run でないか）を決め、作業ツリーを写す。返り `{due, reason}`。
2. `local-review-loop`（`loop_group`、最大 3 回、`fresh_context: false`、`until_bash: done=$local-review-accept.output.done; test "$done" = true`、`when: $intake.output.due == true`）
   - `local-review-prep`（script `role_prep.py`。`with:` を持たない）: 指示を組む。返り `{prompt}`。
   - `local-review`（AI）。`prompt: "$local-review-prep.output.prompt"`・`depends_on: [local-review-prep]`。起こし方は今の `net_closed_launch`（`workflows/judge/works-factory-judge.yaml:464-480`）を字のまま展開し（注記 3 行も写す）、今の node が錨の後ろに足して上書きしている 3 つの鍵（`allowed_tools`・`skills`・`plugins`。`:1072-1075`）を今のまま置く。展開した後の鍵の全部: `model: '@wf-judge-materials'`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob, Bash, WebSearch, WebFetch, Skill, Agent]`・`skills: [code-review, simplify, security-review]`・`plugins: [pr-review-toolkit@works-local]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false, failIfUnavailable: true, excludedCommands: ['works-gh:*'], network: {allowedDomains: []}, filesystem: {denyWrite: ['~/../archon-home']}}`・`idle_timeout: 1728000000`。`retry: {max_attempts: 2, on_error: all}`。`mutates_checkout:` は今と同じく置かない。`output_format` は今のまま（2.4）。錨を展開するので、`allowed_tools` は 1 回だけ書く（今は錨の値を後の鍵が上書きする形）。
   - `local-review-accept`（script `role_accept.py`。`with: {reply: $local-review.output}`）: 返り `{ok, done, reason}`。
3. `finish`（script `finish.py`。`depends_on: [intake, local-review-loop]`・`trigger_rule: all_done`）: `material.json` を書き、出力を返す。どの段が落ちても落ちない。

### 1.4 place のファイル

materials.md の 1.4 の名（`intake.json`・`view.json`・`diff.patch`・`changed-files.txt`・`tree.json`・`local-review-prompt-<n>.md`・`rejects-local-review.json`・`rejects-local-review.md`・`accepted.json`・`material.json`）に、この観点だけの控えを 1 つ足す:

- `lenses.json`: 受けた返答の見ていないレンズ `{"round": 1, "unseen": [<レンズの名>…]}`（今の `local-review-lenses.json` と同じ中身）。accept が受けた回だけ書く（拒んだ回・諦めた回は書かない。今のまま）。名は `src/lenses.py` の `LENS_FILE` だけが持つ。ほかの block はこのファイルを読まない（見ていないレンズは `report` の行と `material.json` の `reply` の印で外へ出る）。

1 つ目の commit（2.9 の指示の比べの間）だけ、`material-local-review-brief.md`（今の材料のファイルと同じ字）も書く。

### 1.5 コードの置き場

- `workflows/local-review/src/__init__.py`（空）。
- `workflows/local-review/src/lenses.py`（この観点だけの部品。docstring の頭に `lib/diverted.py` の docstring の「なぜ要るか」の段を写す）:
  - `LENSES: tuple[dict, ...]`: レンズの宣言。今の `LOCAL_REVIEW_SKILLS`（`lib/judge_accept.py:1697-1706`）の 7 本を同じ順で、欄 `skill`・`args`（在る物だけ）・`required`・`applies_cond`（在る物だけ）に絞って写す。`note` は写さない（文は md の 2.3 の `## Notes per lens` へ移す）。
    ```python
    LENSES = (
        {"skill": "/code-review", "args": "high", "required": True},
        {"skill": "pr-review-toolkit:code-reviewer", "required": True},
        {"skill": "/simplify", "required": True},
        {"skill": "/security-review", "required": False, "applies_cond": "security_surface_touched"},
        {"skill": "pr-review-toolkit:silent-failure-hunter", "required": True},
        {"skill": "pr-review-toolkit:type-design-analyzer", "required": True},
        {"skill": "pr-review-toolkit:pr-test-analyzer", "required": True},
    )
    ```
  - `SIMPLIFY_LENS = "/simplify"`。
  - `SECURITY_COND = "security_surface_touched"`、`SECURITY_WHY = "差分が認証・データの取り扱い・外部との入出力に触れる"`（今の `_security_declared` が真の時の字。`:1476-1487` の `_touched` の文）。
  - `applies(cond: str) -> tuple[bool, str]`: `cond == SECURITY_COND` なら `(True, SECURITY_WHY)`。ほかは `ValueError(f"知らないレンズの条件: {cond!r}")`。今の `due_view`（`:1354-1358`）は `touches_security_surface` を真に倒すので、`security_surface_touched` は 1 run = 1 周ではいつも真で、理由はこの字（例の run の `applies_why` と同じ）。
  - `skills() -> list[dict]`: `LENSES` の各要素の写しに、`applies_cond` を持つ物だけ `applies`・`applies_why`（`applies(…)` の返り）を足した並び。今の `_skills`（`:1989-2000`）から `note` を除いた物。
  - `FORK_LENSES = ("/code-review",)`、`UNSEEN_TAG = "【works: 所見を受け取れていない——このレンズは見ていないのと同じに扱え】"`: 写す元 `lib/diverted.py:28-29`（字のまま）。
  - `LENS_FILE = "lenses.json"`。
  - `mark_unseen(reply, skills) -> tuple[dict, dict]`: 写す元 `diverted.mark_unseen`（`lib/diverted.py:32-49`。字のまま）。
  - `unseen(reply) -> list[str]`: `reply["findings"]` の行のうち、`failed` が字で `UNSEEN_TAG` で始まる行の `skill` を順に並べた物（印を付けた後の返答から、`mark_unseen` の控え `notes["unseen"]` と同じ物を取り直す口）。
  - `unseen_lines(names) -> list[str]`: `[f"局所レビューの {n}: 所見を受け取れていない（fork の返答が届かなかった）——見ていないのと同じ" for n in names]`（写す元 `diverted.report_lines`、`:52-60` の行の字）。
  - `installed_plugins() -> set | None`: 写す元 `_installed_plugins`（`lib/judge_accept.py:2424-2433`。環境変数 `CLAUDE_CONFIG_DIR` の下の `plugins/installed_plugins.json`）。
  - `lens_gap(skills, reply) -> tuple[str, bool] | None`: 写す元 `_lens_gap`（`:2435-2460`）。違いは 3 つ（どれも振る舞いは同じ）: 持ち越しの判定 `carry_ok` は変数ごと外し、`simplify_carried` は不足を免じない（今も `carry_ok = False` で同じ）。`/simplify` の不足の文の尾は「（simplify_carried: true の持ち越しはこの run では受けない——1 run は 1 周で、前の周の版が無い）」にする。プラグインの欠けの尾の入れ直しの道を、今の字の `dev/toolset.py`（工場に無いパス）から `bin/_lib/toolset.py install`（起動の殻 `bin/_lib/launcher.py:361-364` が run の頭に打つ物）に直す。
  - `covers_lenses(skills, reply) -> str | None`: 写す元 `local_review_covers_lenses`（`:2186-2220`）。`Reject` を上げる代わりに拒む文を返す（通れば None）。文の違い: 宣言の外の名の文の「正本は graph の skills（…）。名指しを増やしたいなら graph を直せ（役が勝手に増やした名前は数えられない）」を「正本は宣言のレンズ（…）。役が足した名は数えられない」に、`skills` が空の文の「graph に宣言を書け」を外す（block は graph を名指さない。materials.md の 10 節）。ほかの文は字のまま。
- `workflows/local-review/src/viewpoint.py`: materials.md の 5.1 の宣言。中身:
  - `NAME = "local-review"`
  - `MATERIALS = ("local_review",)`
  - `GUARDED = False`（作業ツリーの照らしを外すのではなく、Archon が節の前後の git status を照らさない役なので、accept が `porcelain` も含む全部の欄を比べる、の意味。AI の node が `mutates_checkout: false` を持たない。今の accept の `with: {status_guarded: false}`。`workflows/judge/works-factory-judge.yaml:1123`）
  - `NA = "never"`、`NA_REASON = ""`（今の `MATERIAL_NODES['p1.local_review']` が `applies_cond` を持たず `na_self_ok: False`。`lib/judge_accept.py:1644-1648`。graphloops の `na_reason_note`「差分が在る限り常に対象」）
  - `due(view, values)`: `return materialkit.not_entry_due(view, values, "P1 の役")`。判定から入る run の周（`materialkit.is_entry_run`: `entry` が空でなく、対象差分が空）だけ `entry_skip`、それ以外は `normal_run`。族の決め（materials.md の 5.1・`lib/judge_accept.py` の `request_entry`）に従う。差分が出来た run は `entry` が在っても通常の run。
  - `fill(view, values, due)`: `{"local_review": materialkit.fill_entry(values["entry"], None)}`（回さないのは判定から入る run だけ。今の `_fill_one` の 1 つ目の枝）。
  - `applies(view, values)`: `raise NotImplementedError`。
  - `judged_na(view, values)`: `return False`。
  - `values(view, values)`: `own, theirs = materialkit.review_md_paths(view.repo)` として、`{"diff_file": view.diff_file, "base": view.base, "changed_files_file": view.changed_files_file, "review_md": own, "skills": dump(lenses.skills()), "unattended": seat.overlay_body(seat.OVERLAY_KINDS["local-review"])}`。`theirs` が空でなければ `"repo_review_md": theirs` も足す（入る段落の中の口だけに値を渡す。materials.md の 2.11）。`dump` は `json.dumps(x, ensure_ascii=False, indent=1)`。
  - `when(view, values)`: `{"spawns": True, "repo_review": bool(theirs)}`（`spawns` は外への検索の決まりの断片の段落。この役は Agent を持つ）。
  - `before(view, values, reply, place)`: `skills = lenses.skills()`、`got, _ = lenses.mark_unseen(reply, skills)`、`gap = lenses.lens_gap(skills, got)`。`gap` が在れば `return gap[0], got, gap[1]`、無ければ `return None, got, False`（今の `material_take` の `:2593-2599` の順。印を付けてから必須のレンズを照らす）。
  - `after(view, values, reply, place)`: `return lenses.covers_lenses(lenses.skills(), reply)`。
  - `after_accept(reply, place)`: `jsonfile` で `place / lenses.LENS_FILE` に `{"round": 1, "unseen": lenses.unseen(reply)}` を書く（今の `:2595`・`:2620-2621`）。
  - `materials_of(reply)`: `{"local_review": reply["material"]} if isinstance(reply.get("material"), dict) else {}`（今の `writes` の `materials.local_review ← material`）。
  - `report_lines(doc)`: `reply` が null なら `[]`。在れば `[f"  - {s}" for s in lenses.unseen_lines(lenses.unseen(doc["reply"]))]`（字下げ 2 つ。materials.md の 2.10 の素材の 1 行の下に並ぶ）。
- `workflows/local-review/src/oldbrief.py`（1 つ目の commit だけ）: 今の材料のファイルを同じ字で組む `brief(view, values) -> str`。レンズの一覧は今の `LOCAL_REVIEW_SKILLS` の `note` つきの字をこのファイルに写して持つ（`lib/judge_accept.py` は import しない）。2 つ目の commit で消す。
- 使う `lib/`: `materialkit`・`rolekit`・`jsonfile`・`oneline`・`seat`（`overlay_body` と `OVERLAY_KINDS`。KEEP。README の 9.3）。`lib/diverted.py` は import しない（README の 9.2 で local-review へ MOVE した物）。

### 1.6 つなぎ方（graph の側。block には書かない）

- 判定のまとめ（`workflows/judge/`）: `include: works-factory-local-review`、`depends_on` は materials.md の 1.6。`with:` は `base`・`entry`・`lang` の共通の 3 つだけ（作り手は materials.md の 1.6）。
- 読み手:
  - diagnose の `materials`（11 本の `material` の配列の 1 つ）。素材 `local_review` は `materialkit.assemble` が 15 欄にそろえる。判定役の材料の「局所の findings」（今の `_diagnose_ctx` の `process.local_findings ← reply.findings`、`lib/judge_accept.py:2769-2773`）は、diagnose が同じ配列の `role == "local-review"` の `materialkit.read` の返りの `reply["findings"]` から取る（読み方は diagnose の設計書が決める）。
  - 報告の「未確認のレンズ」の節（今の `runreport._unseen_lens_lines` が `review_lenses` の先を `diverted.report_lines` で読んだ物）: この block の `report` の欄の、素材の 1 行の後ろの行。report.md の 1.6 は「未確認のレンズ → local-review」とする。修正の後のレンズの行（今の `fixbeside.lens_lines`）を同じ節に並べるのは line の決め。
- 判定の出力の欄 `review_lenses`（今の line の YAML の `:190`・`:801`）は、組み込みで要らなくなる（読み手は報告だけで、行で届くため）。

## 2 node の設計シート: local-review（局所レビューの役）

### 2.1 役

宣言した 7 本のレンズを、対象差分に名指しで 1 本ずつ起こし、レンズごとに 1 行の所見と素材の状態を返す。所見を集めるだけで、採点もラベルの確定もしない。

### 2.2 port

`intake.json` の `view`（← port `base` と作業ツリー。`diff_file`・`base`・`changed_files_file`・`repo`）・`values.lang`（← port `lang`）、レンズの宣言（← `src/lenses.py`）、観点の正本のパス（← `materialkit.review_md_paths`）、借りたスキルの読み替え（← `lib/borrow/unattended.md` を `seat.overlay_body` で絞った字）、拒否の控え（← accept が place に積んだ物）。

### 2.3 組み立ての順（`prompts/local-review.md`）

materials.md の 3.1 の並び。

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: `rejects-local-review.json` に拒否が 1 件以上。`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "local-review"))`。
2. 役の定義の断片は置かない（今の md の頭は外への検索の決まりの塊だけ。materials.md の 5.2）。
3. `{shared:query-rule}`。断片の中の `<!-- if spawns -->` には `spawns: true`（Agent で子を起こす役。今の md:3 の「子への指示に下の塊をそのまま含めよ」）。
4. 役の 1 段落（決まった文）。
5. 道具の段落（決まった文）、`{shared:works-gh}`、`{shared:material-readonly}`。
6. `## Materials` と差し込み口: `{diff_file}` ← `view.diff_file`（絶対パス）、`{base}` ← `view.base`、`{changed_files_file}` ← `view.changed_files_file`（絶対パス）、`{review_md}` ← `review_md_paths` の 1 つ目、`<!-- if repo_review -->` `{repo_review_md}` ← 2 つ目 `<!-- end repo_review -->`（条件: 対象の根に `REVIEW.md` が在る）、`{skills}` ← `dump(lenses.skills())`（JSON の配列の字）。
7. `## What to do`・`## Notes per lens`・`## When a lens call fails`・`## How /code-review returns`（決まった文）: 今の graphloops の指示の段（md:39-60）と、works の受け付けの読み替え 2 つ（md:65-77）を英語にした物。
8. `{shared:material-status}`。
9. `## Whether you may write not_applicable` と `{shared:material-na}` — 扱いは `never`（`na_never` だけが真）。
10. `## Where to point` と `{shared:material-where}`。
11. `## Reading borrowed skills` と決まった頭の 1 文、`{unattended}` ← `seat.overlay_body(seat.OVERLAY_KINDS["local-review"])`（今の md:89-166 と同じ字。日本語のまま）。
12. 言語の 1 文と `{lang}`。
13. 結びの 1 文。

md の本文（英語。この block の 2 つ目の commit でこのまま置く）:

```markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{shared:query-rule}

You are the local-review role. Your only job is to start each review lens declared below on the target diff, one by one and by name, and to collect what each lens finds. Do not score the findings or settle their labels. You are given neither the request nor any other material.

Your tools are Read, Grep, Glob, Bash, WebSearch, WebFetch, Skill (to start a skill), and Agent (to start an agent). Bash runs inside a sandbox, and its network is closed: it cannot reach any destination.

{shared:works-gh}

{shared:material-readonly}

## Materials

- Target diff: {diff_file} (a copy of the diff from the base commit `{base}` to the version frozen for this run; new untracked files are included).
- List of changed files: {changed_files_file} (one file per line; Read only what you need).
- Review viewpoints: {review_md}. Read it. Labels and viewpoints come from here.
<!-- if repo_review -->
- The target repository's own review viewpoints: {repo_review_md}. Read it too.
<!-- end repo_review -->

The lenses to start (this list is the source of truth; the machine filled it from the declaration, it is not a hand-made copy):

{skills}

## What to do

How to read the list: `skill` is the name, and `args` are the arguments to pass (if present, always pass them). An element whose `required` is false has `applies_cond`, and whether it applies is decided by `applies`, which the machine evaluated for this run (the reason is in `applies_why`). **If `applies` is true, you must start it. If it is false, you need not.** Start the built-in skills with Skill and the pr-review-toolkit agents with Agent.

**Return exactly one row in `findings` for each declared lens, without exception.** If you started it and it found nothing, leave `items` empty and write in `failed` that it was started and found nothing, and what it looked at. If you did not start it, or it does not apply, write why in `failed`. A lens with `required: false` also needs its row. In each row, set `invoked` to whether you started that lens. A row whose element has `applies` true and whose `invoked` is not true is rejected by the acceptance step, except when `material` is `awaiting_human` (see the section on failed calls). **Do not leave out a row**: if rows could be left out, a lens that was never started would pass in the same form as "looked and found nothing" (measured 2026-09-15: the type-design lens was not started three rounds in a row, and nothing in the record turned red). Write `findings[].skill` with exactly the spelling of `skill` above; the acceptance step counts this array one to one against the list, so a different spelling fails. **Do not add names that are not in the list**; names you add are not counted.

**Pass the target to every detector explicitly.** If you do not, each one rebuilds its own default target, and empty findings about something else enter the record in the same form as "looked and found nothing". How to pass it differs by tool; the notes per lens below are the source. Pass `{diff_file}` as it is to the agent lenses.

**Only collect the findings; do not score them or settle their labels.** This node does not take the verdict of `/code-review`'s own verification: an item of `findings` has five fixed keys and no place for it. Adding a key breaks the schema, and leaving it out keeps it from reaching the judgment. Do not work around this by putting the verdict into the text either. Weeding out false positives is the job of the judgment's refutation later in this run.

**Do not put the umbrella agent `pr-review-toolkit:review-pr` in between. Start the lenses one by one, by name.** Its prose routing depends on the shape of the diff (try/except, type definitions, presence of tests), but the classes the lenses above catch (checks silently disabled, guards that became always true, designs that hold invariants in flat values, gaps in behavior coverage) appear regardless of that shape. Do not call `pr-review-toolkit:code-simplifier`: it applies fixes instead of reporting them. **This node must not change the working tree.** Call any tool that can go as far as fixing only in a form that forbids fixing.

In the prompt you give each skill, impose the submission criteria of the review viewpoints (the section on the criteria for submitting a finding); writing them in the viewpoints file does not make them reach the skill: the mechanism (one sentence on the cause in the code), the measurement (run what can be run; if you cannot, say "not measured" and submit it as a hypothesis), self-refutation before submitting (if it cites a rule, check whether the rule's condition applies, read the surrounding facts, and submit only what you could not refute), and the estimate of false positives (one line on when it would be wrong).

This run is the first round, so carrying `/simplify` over from an earlier round is not accepted: start `/simplify`, set `invoked` to true, and set `simplify_carried` to false.

## Notes per lens

- `/code-review`: built in (a plugin of the same name exists separately). Pass the target as the **file paths** listed in the list of changed files; a ref range does not include the working tree. Pass no flags other than its `args`: no flag that posts comments and no flag that applies fixes.
- `pr-review-toolkit:code-reviewer`: the general lens that covers both compliance and bug detection. **Do not drop it.**
- `/simplify`: **call it only in a form that forbids fixing** (the real skill rewrites the working tree by default). Start each of its four viewpoints (reuse, simplification, efficiency, altitude) and have them return findings only.
- `pr-review-toolkit:silent-failure-hunter`: looks at checks that are silently disabled and failures that are swallowed.
- `pr-review-toolkit:type-design-analyzer`: looks at designs that hold invariants in flat values; prose routing does not reach this class.
- `pr-review-toolkit:pr-test-analyzer`: the lens for behavior coverage; no other node looks at it.

## When a lens call fails

If the call of a skill itself fails (permissions, runtime errors), do not stop: write it in that row's `failed`. **Do not turn something missing into `not_applicable`.**

- A lens with `required: false`: if its call fails, write it in `failed`, set `material.status` to `awaiting_human`, and write the reason in `material.reason` (`material` is the top-level field, separate from the rows of `findings`).
- A lens with `required: true`: if its call fails, start it again within this answer and write `invoked: true`. If you return without having started it, write the reason in `failed` and do not set `material` to `awaiting_human`. The acceptance step rejects the answer and asks you to start it again in the same conversation; the answer goes to a person only when the rejections reach the limit, or when the lens's plugin is missing from the isolated settings. Handing it to a person is the machine's job, not yours: even when you find that the plugin is missing, do not set `material` to `awaiting_human`; write in that row's `failed` the call you made and the error it returned.

## How /code-review returns

`/code-review` runs in a separate conversation (a fork). If it returns its findings in its text, copy them into the `items` of the `/code-review` row; drop none. If the Skill result is only "Skill execution completed" with no findings text, the fork wrote its findings to another channel and they did not reach you; the acceptance step then reports this row as "not seen". In either case, do not start `/code-review` again (it returns in the same form and only costs time). For a row whose text did not arrive, leave `items` empty, set `invoked: true`, and write in `failed` that the text did not arrive and what target you passed. Do not write "started and found nothing": that makes something not seen look like zero findings.

Do not write the spelling of a flag in `args`, not even inside a sentence that says not to use it: the skill reads it as a flag (measured: in "attach neither the comment flag nor the fix flag" written with the spellings, the fix flag was taken). Forbid fixing with the sentence "do not change the working tree".

{shared:material-status}

## Whether you may write not_applicable

{shared:material-na}

## Where to point

{shared:material-where}

## Reading borrowed skills

When you read a borrowed skill (superpowers), follow the reading rules below. They are direct instructions to you and win over the skill's text. If you start a helper with Agent, include this whole section in its prompt as it is; this section does not reach the helper otherwise.

{unattended}

Write `material.detail`, `material.checked`, `material.reason`, and, in each row of `findings`, `failed` and the `text`, `mechanism`, `measured`, and `false_positive_if` of each item in {lang}. Keep keys, enum values, identifiers, paths, commands, skill names, and quoted text as they are.

Return only JSON that matches the output schema.
```

md の中に `$` の字は無い（今の道具の段の「`$(…)`」は `{shared:works-gh}` の中で "a command substitution" になった）。差し込み口のほかに `{` は無い（`{skills}` と `{unattended}` の値の中の `{` は値で、口ではない）。

言語: `{lang}` は materials.md の 2.11 のとおり。`{skills}` の中の `applies_why` と `{unattended}` は日本語の値のまま入る（機械の事実の字と、借りた物の写しの台帳 `lib/borrow/COPIED_FROM` が持つ字。自分で決めた。7 節）。

会話: 役は `fresh_context: false` で、拒まれた後の回は同じ会話の続き（各回に Archon の `retry`）。

### 2.4 返す形

今の `output_format` のまま（`workflows/judge/works-factory-judge.yaml:1077-1117`）:

- `material`: 族の共通の形（prior-decisions.md の 2.4 と同じ欄・`additionalProperties: false`・`required: [status]`）。
- `simplify_carried`: boolean。
- `findings`: `[{skill, items, invoked?, failed?}]`・各行 `additionalProperties: false`・`required: [skill, items]`。`items` は `[{where, text, mechanism?, measured?, false_positive_if?}]`・`additionalProperties: false`・`required: [where, text]`。
- 全体 `additionalProperties: false`・`required: [material, findings, simplify_carried]`。

人に見せる欄は `material.detail`・`material.checked`・`material.reason`・行の `failed`・`items` の `text`・`mechanism`・`measured`・`false_positive_if`（判定の材料と報告に載る）で、言語は `{lang}`。`where` と `skill` は名指しなので字のまま。`items` の行は `where` と `text` を持つので、所見の場所の照らし（`materialkit.where_rows`）に当たる。

### 2.5 描いた骨組み（例の run の値）

例の run では、今の指示は 2 か所に在った: `workflows/judge/commands/material-local-review.md`（166 行。`$local-review-prep.output.lang_line`・`.reason`・`.brief_file`・`.review_md`・`.repo_review_md` を Archon が入れた物）と、役が Read した `judge/material-local-review-brief.md`（74 行）。新しい指示は 1 本にする。2 回目（1 回目が所見の場所で拒まれた後）の骨組み:

```markdown
{shared:rejected の本文。{rejection} に次の字:
受け付けがこれまでに拒んだ理由の全部（古い順に 1 件。前の回の拒否も直したままにする）。

1 回目の拒否:
所見の場所の行がファイルに無い（差分の行番号を書いていないか。作業ツリーのファイルの行で書き直せ）:
  - frontend/composition/chat/views/__tests__/thread-list-pin.test.tsx:1413: 名指し 'frontend/composition/chat/views/__tests__/thread-list-pin.test.tsx:1413' の行がファイルに無い（256 行しか無い）}

{shared:query-rule の本文（spawns の段落つき）}

You are the local-review role. …

Your tools are Read, Grep, Glob, Bash, WebSearch, WebFetch, Skill (to start a skill), and Agent (to start an agent). …

{shared:works-gh の本文}

{shared:material-readonly の本文}

## Materials

- Target diff: ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-ac9f-4468-ae72-5f6ed569a667/judge/local-review-run/diff.patch (a copy of the diff from the base commit `7defb7ec5fac098b7302f5bfc11a02f151f4d262` to …)
- List of changed files: ~/.local/state/works-factory/targets/316e3bbc/…/runs/53e71318-…/judge/local-review-run/changed-files.txt (…)
- Review viewpoints: ~/.cache/works-factory-plugin/56032b5a88e2add0e1bda0949986271e1f649ea6/lib/REVIEW.md. …
- The target repository's own review viewpoints: ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/worktrees/archon/task-works-factory-line-1792307529854/REVIEW.md. Read it too.

The lenses to start (…):

[
 {
  "skill": "/code-review",
  "args": "high",
  "required": true
 },
 {
  "skill": "pr-review-toolkit:code-reviewer",
  "required": true
 },
 …
 {
  "skill": "/security-review",
  "required": false,
  "applies_cond": "security_surface_touched",
  "applies": true,
  "applies_why": "差分が認証・データの取り扱い・外部との入出力に触れる"
 },
 …（7 本）
]

## What to do
…（決まった文 6 段）

## Notes per lens
…（7 行のうち 6 行。/security-review は注意を持たない）

## When a lens call fails
…

## How /code-review returns
…

{shared:material-status の本文}

## Whether you may write not_applicable

This viewpoint has no condition under which it does not apply, so the acceptance step rejects `not_applicable`. …

## Where to point

Write the `<path>:<line>` of a location (`where`) as a line number in the current file in the working tree. …

## Reading borrowed skills

When you read a borrowed skill (superpowers), …

# 借りた superpowers のスキルを無人の役で読むときの読み替え
…（今の md:91-166 と同じ字）

Write `material.detail`, … in the language of the request (the user's language). …

Return only JSON that matches the output schema.
```

place のパスは、line → 判定のまとめ（include の id `judge`）→ この block（include の id `local-review`）と include された時の物。`lang` は空で、`{lang}` に既定の文が入った形。`{skills}` の字は、今の材料のファイルの「## 材料: node.skills」の節の字（字下げ 1 つの JSON）から `note` の欄を抜いた物と同じ。

### 2.6 今の指示との差

prior-decisions.md の 2.6 の族に共通の差（材料のファイルを指示に入れた・`{shared:material-na}`・`{shared:rejected}` に 1 回・`{shared:material-readonly}`・`{shared:works-gh}`・`{shared:material-status}`・`{shared:material-where}`・言語の 1 文・元の指示書との境の見出しと `---` を消した・「同じ時に別の素材集めの役も走っている」の断定を消した・英語にした）は、この観点にもそのまま当たる。この観点だけの差:

- 移した: 外への検索の決まりの塊（md:3-10）を `{shared:query-rule}` に。頭の「Agent で子を起こすなら、子への指示に下の塊をそのまま含めよ」は断片の `spawns` の段落が言う。
- 移した: レンズごとの注意の文（今の `LOCAL_REVIEW_SKILLS` の `note`。Python の定数の中の指示の文）を、md の `## Notes per lens` に。`{skills}` の値は宣言の欄（`skill`・`args`・`required`・`applies_cond`・`applies`・`applies_why`）だけになる。訳: 憲法の 2（Python は指示の文を持たない）と README の 5.3（md と受け付けが同じ字を持つべき値だけを Python が入れる）。今の md の「道具ごとの渡し方は上の `note` が正本」は「the notes per lens below are the source」にした。
- 変えた: `/code-review` の注意の「--comment も --fix も付けるな」を、旗の綴りを書かない文（"no flag that posts comments and no flag that applies fixes"）に。訳: 同じ md の `/code-review` の返し方の段（今の md:77）が、否定の文の中の旗の綴りも skill が旗と読むと実測で言っている。今は注意が値の中に在り、その段の決まりに自分で外れていた。役に届く決まりは同じ。
- まとめた: `/simplify` の持ち越しの 2 か所（md:60 の「直前の周から…持ち越してよい」と md:69 の「狭めて読め…1 周目は起こせ」）を、1 文「この run は 1 周目なので持ち越しは受けない。起こして `invoked: true`、`simplify_carried` は false」に。訳: 1 run = 1 周（持ち主の決め carry）で、受け付けは持ち越しをいつも受けない（今の `_lens_gap` の `carry_ok = False`）。役に届く求めは今の 2 つを合わせた物と同じ。
- まとめた: 呼び出しの失敗の 2 か所（md:60 の「material を awaiting_human にして理由を書け」と、それを必須のレンズでは外す読み替えの段 md:67）を、`## When a lens call fails` の 2 つの箇条（`required` が偽のレンズと真のレンズ）に。読み替えの段が上の文を指して直す形をやめた。
- 移した: 「1. まず材料を Read で読め」（md:26）と「観点の正本を Read せよ」（md:33）を、`## Materials` の行の中の "Read it" に。材料のファイルが無くなったので前者の手順は要らない。
- 移した: 道具の段（md:28）を、道具の 1 段落・`{shared:works-gh}`・`{shared:material-readonly}` に（prior-decisions と同じ割り方）。「組み込みの skill は Skill で、agent のレンズは Agent で」（md:29）は `## What to do` の 1 段落目の尾に。
- 消した: 「素材の書き方」の尾の「欄と値の正本は受け付けが使う検証器 review-record.py だが…」（md:61）。役が開かない物の名指し（prior-decisions と同じ）。
- 消した: 「engine の post_check が拒む」「engine が P1 の前後で突き合わせる」の engine・post_check・P1・P2 の名指し（md:50・54・56）。"the acceptance step" と "the judgment … later in this run" に替えた（役が見ない仕組みの名）。
- 残した: 実測の訳（2026-09-15 の型設計のレンズが 3 周起きなかった・旗の綴りが旗に取られた）。役が行を省かない・綴りを書かない訳として、返答の形を決めるため。
- 移した: 借りたスキルの読み替え（md:89-166）の頭の 1 文を英語の決まった文に、本文を `{unattended}` の値に。本文は今も `seat.overlay_body` が `lib/borrow/unattended.md` から組む字で（今の試験 `tests/workflows/test_judge.py:521-530` がそれと md の末尾の一致を見ていた）、新しい形では写しを md に置かず、源から入れる。置く所を結びの前に移した（3.1 の並びの言語の 1 文と結びの 1 文を最後に保つため）。
- 変えた: 断片 `material-where` の尾の文を、受け付けが照らす範囲（`where` と `text` を持つ行だけ。ほかの行は照らさない）に合わせて狭めた。
- 役の名「局所レビューの役」は "the local-review role"。

### 2.7 元の works と graphloops の同じ場面

族の形の差は materials.md の 9 節。この観点だけの差:

- 元の works の `works/blk-material/commands/local-review.md`（8 行）は、engine が描いた graphloops の指示書のファイル（`prompt_file`）を Read で読ませる薄い md だった。工場は graphloops の指示書を md の中に写し、値を材料のファイルにした（#76）。新しい形は値も指示の中に入れる。
- 元の works は局所レビューの役を包みの旗 `text-reply` で起こし（`works/blk-material/blk-material.yaml:480` の `works-node: local-review no-tree-write text-reply`）、返答の型を返答の道具に任せず本文で受けた。旗の訳は、fork で走る `/code-review` が返答の道具を継いで所見を親に返さなくなる形を塞ぐこと（`lib/diverted.py` の docstring）。工場は包みを持ってこず、返答の型は Archon の `output_format` が担う（`docs/concepts.md` の `replycontract` の行。#269 が記録した。包みを落とした決めは `docs/design.md`（#765 で消した。`cbc7297` の版で読める）。PR の番号の記録は無い（未確認））。その代わりに、見ていないレンズの印（`mark_unseen`）を受け付けに置いた（#76）。この block も印を持つ。
- 元の works と graphloops は `/simplify` の持ち越し（`simplify_carried`。前の周の頭の版から 1 ファイルも変わっていない周だけ受ける `_simplify_carry_ok`、`works/blk-material/lib/material.py:421`）を持つ。工場は 1 run = 1 周と決めて持ち越しを受けない（#76 の `carry_ok = False`、持ち主の決め carry）。この block も受けない。返答の型の欄 `simplify_carried` は今のまま残す（型を変えない）。
- graphloops の今の指示書（`~/src/claude-plugins/graphloops/prompts/review-loop/p1.local_review.md`）は、工場の写し（graphloops 0.21.0）の後の 0.23.0（`921fe1b7`）で、呼び出しの失敗の段を「engine が起こした子」と「会話が回す時」に割った。engine の子の枝は、必須のレンズを起こし直させる所は工場の読み替えの段（md:67）と同じだが、`applies` が真の `required: false` のレンズが起こせなかった時は `failed` に書くだけで material を `awaiting_human` にしない（engine が報告に「未確認のレンズ」として並べる）。工場は今も `awaiting_human` にさせ、受け付けも `invoked` が真でない条件つきのレンズを `awaiting_human` の時だけ通す（`local_review_covers_lenses`）。工場の履歴に、この足しを入れない決めの記録は無い（（未確認）: 写した版がこの足しより前だった）。振る舞いを変える足しなので、この作り直しには入れない。
- graphloops の node の宣言（`graphs/review-loop.json` の `p1.local_review`）は、レンズの一覧の正本を `skills` の配列 1 か所に置き、`note` は「役に毎周貼られる面なので指示だけを置き、根拠は node の `note` に置く」と決めている。この block は一覧の正本を `src/lenses.py` の 1 か所に置き、指示の文（`note`）を md に置き、根拠は md の実測の 2 文と `src/lenses.py` の docstring に置く。
- 元の works の受け付け（`material.py` の take）と工場の受け付けは同じ順（作業ツリー・見ていないレンズの印・必須のレンズ・所見の場所・レンズと行の照らし・素材の欄）。元の works の 0.2.46 の拾い戻し（包みのフックが下請けの返答を残し受け付けが戻す `diverted.recover`）は、元の works 自身が 2026-10-09 の掃除で外した（`lib/diverted.py:12-13`）。工場にも無い。

この block が両方より良く、残す物: 宣言の 1 本に行 1 本を機械が数える（graphloops と同じ）・fork のレンズの空の行を「所見なし」でなく「見ていない」と印を付けて報告に出す（工場と元の works の足し）・必須のレンズを起こすまで同じ会話で出し直させ、プラグインが無い時だけ 1 回目で人に渡す（元の works の足し）・作業ツリーと所見の場所を機械が照らす。

### 2.8 受け付け

materials.md の 4 節の順。観点の前の照らし（4 節の 3）と後の照らし（4 節の 5）を持つ。

- 作業ツリー（4 節の 2）: 役を起こす前の `tree.json` と比べ、`porcelain` を含む全部の欄のどれかが変わっていれば拒む（`GUARDED` が偽）。
- 前の照らし（`viewpoint.before`）:
  1. 見ていないレンズの印: `FORK_LENSES` の行（`/code-review`）が `items` 空・`invoked` 真なら、`failed` の頭と `material` の `checked`・`detail`・`reason` に `UNSEEN_TAG` を付けた写しを、以後の照らしと `accepted.json` に使う。拒まない（起こし直しても同じ形で返るため）。
  2. 必須のレンズ（`lens_gap`）: `required` が真で `invoked` が真でないレンズが在れば拒む。文は今の `_lens_gap` の字（1.5 の 2 つの違いを当てた物）:
     - レンズごとに `f"'{s}' は必須のレンズなのに invoked が true でない——必須のレンズを起こした行だけを受け付ける。/ で始まるレンズは Skill で、<plugin>:<役> は定義の置き場を Read で読ませた汎用の子（Agent）で起こし直せ"`（`/simplify` は尾に「（simplify_carried: true の持ち越しはこの run では受けない——1 run は 1 周で、前の周の版が無い）」）。
     - `material.status` が `awaiting_human` なら `"必須のレンズが起きていない返答は material を awaiting_human にできない——起こし直して invoked: true を書け（拒みが上限に届けば人に渡る）"`。
     - 欠けたレンズの `<plugin>:` が `installed_plugins()` に無ければ `f"隔離した設定（{CLAUDE_CONFIG_DIR}）にプラグイン {'・'.join(absent)} が入っていない——起こし直しても毎回落ちるので出し直さずに人に渡す（bin/_lib/toolset.py install で入れ直してから続ける）"`。この時は `give_up` 真（1 回目で `done`）。`installed_plugins()` が None（環境変数が無い・読めない）なら欠けを判じず、出し直させる（今のまま）。
     - 全体は `"宣言したレンズと findings の行が合わない:\n" + "\n".join("  - " + e for e in errs)`。
- 所見の場所（4 節の 4）: `findings[].items[]` の `where`（`text` を持つ行）と、`material` の字の中の `<パス>:<行>`。例の run の 1 回目はここで拒まれた。
- 後の照らし（`viewpoint.after` = `covers_lenses`。`accept.in_repo(repo)` の中）: 宣言の 1 本に行が 1 本か。拒む文は今の `local_review_covers_lenses` の字（1.5 の違いを当てた物）: 同じ skill の行が 2 本・宣言に無い skill の行・宣言の行が無い・`items` も `failed` も持たない行・条件が真のレンズの行の `invoked` が真でない（`material` が `awaiting_human` の時は免じる）。頭は `"宣言したレンズと findings の行が合わない:\n"`。
- 素材（4 節の 6）: `local_review` が無い・`carried_over`・`not_applicable`（`never`）・知らない status・status ごとの要る欄の欠け。
- 受けた後（4 節の 7）: `after_accept` が `lenses.json` を書く。
- 3 回目の拒否で諦める。プラグインの欠けは 1 回目で諦める。どちらも run は止めず、`finish` が `status: gave_up`・`reason` に `rolekit.given_up_reason` の字・素材 `local_review` に `not_run` と同じ訳を書く。
- 拒みの文は日本語（materials.md の 3.3）。

### 2.9 試験

- standalone の fixture（`workflows/local-review/fixtures/`）:
  - `standalone.stubs.yaml`: `fixture.inputs` は `base: ""`・`entry: ""`・`lang: ""`。AI の node `local-review` だけを台本の返答（`material.status: clean`・`checked` 1 文・`simplify_carried: false`・`findings` は 7 本のレンズに 1 行ずつ、`items: []`・`invoked: true`・`failed: "起こしたが所見なし（差分を見た）"`。ただし `/code-review` の行は `items` に 1 件〔`where` は fixture の作業ツリーに在るファイルの 1 行目〕を持たせ、見ていない印が付かない形にする）で差し替え、script は本物（`--exec-code`）。`reached` に `finish`。`finish` の `status` が `ran`。
  - `gave-up.stubs.yaml`: 台本の返答が 3 回とも `material.status: not_applicable`（ほかは standalone と同じ）。`finish` の `status` が `gave_up`、run は `completed`。
  - `skipped.stubs.yaml`: `entry: "人の依頼（standalone）"`。AI の node に届かず、`finish` の `status` が `skipped`、`reason` が `materialkit.entry_skip("P1 の役").why` の字。
- `tests/blocks/local_review/test_local_review.py`: materials.md の 8 節の block の試験（使い捨ての `ARTIFACTS_DIR` と git のリポジトリ、port の値だけ）。写す元は `lib/tests/test_judge_accept.py` の `MaterialCase`:
  - `test_local_review_rows_cover_the_declared_lenses`: 行の欠け・宣言の外の名・同じレンズの 2 行・`items` も `failed` も無い行を、それぞれ拒む（宣言の外の名の文は「正本は宣言のレンズ」）。
  - `test_missing_required_lens_is_refused`: 必須のレンズを起こしていない返答と、それを `awaiting_human` にした返答を拒み、プラグインが入っていれば `done` が偽（`CLAUDE_CONFIG_DIR` を使い捨ての設定に向ける）。
  - `test_absent_plugin_gives_up_at_once`: プラグインが無ければ 1 回目で `done`。続けて `finish` を回し、`status` が `gave_up`、素材 `local_review` の `reason` がプラグインの名を言う（今の `fill_materials` の照らしを `finish` の照らしに替えた）。
  - `test_local_review_unseen_lens_is_marked`: `/code-review` の行が `items` 空で受けられ、`material.json` の `reply` の行の `failed` が `UNSEEN_TAG` で始まり、`lenses.json` が `{"round": 1, "unseen": ["/code-review"]}`、`finish` の `report` に「局所レビューの /code-review: 所見を受け取れていない」の行が在る。
  - 足す: `entry` が空でない run で `intake` の `due` が偽、`finish` の `status` が `skipped`、素材が `fill_entry` の字（件数の句は「渡されていない」）。
  - 足す: prep が組んだ指示の `{skills}` の値の `/security-review` の要素が `applies: true`・`applies_why: "差分が認証・データの取り扱い・外部との入出力に触れる"` を持ち、どの要素も `note` を持たない。対象の根に `REVIEW.md` が無い時は `repo_review` の段落が入らない。
  - 足す（起こし方の照らし）: block の YAML の AI の node の `model`・`allowed_tools`・`skills`・`plugins`・`sandbox`・`idle_timeout`・`retry` が、今の `tests/workflows/test_judge.py:89-90` の表の local-review の行（`"sonnet", "medium", [*INVESTIGATE, "Skill", "Agent"], CLOSED, …, LOCAL_REVIEW_SKILLS, LOCAL_REVIEW_PLUGINS`）が照らす物と同じ。
- `tests/blocks/local_review/test_lenses.py`: `lib/tests/test_diverted.py`（README の 9.5 で local-review へ MOVE する物）を `src/lenses.py` の `mark_unseen`・`unseen`・`unseen_lines` に向けて写す。足す: `LENSES` の `skill`・`args`・`required`・`applies_cond` が今の `lib/judge_accept.py` の `LOCAL_REVIEW_SKILLS` と同じ（1 つ目の commit だけ。組み込みで今の定数が消える時に、この照らしも消す）。`applies` が知らない条件で `ValueError`。
- `tests/blocks/local_review/test_viewpoint.py`: materials.md の 8 節のとおり。
- 指示の比べ（README の 11.4）: `tests/blocks/local_review/test_prompts.py`。
  - 1 つ目の commit: `prompts/local-review.md` を、今の `workflows/judge/commands/material-local-review.md` の `$local-review-prep.output.<欄>` の 5 つ（`lang_line`・`reason`・`brief_file`・`review_md`・`repo_review_md`）を `{<欄>}` に替えた日本語の字で置く（末尾の借りたスキルの読み替えも今の字のまま）。prep は 1 つ目の commit だけその 5 つの値を入れる（`reason` は最後の拒否の文か空、`brief_file` は `src/oldbrief.py` が書いた `material-local-review-brief.md` の絶対パス）。試験は例の run の値（`base`・差分と変更ファイルのパス・観点の正本のパス 2 つ・1 回目の拒否の文）で、(a) 組んだ指示が今の md に同じ 5 つの値を入れた字と同じ、(b) `oldbrief.brief` の字が例の run の `judge/material-local-review-brief.md` と同じ（パスは試験の物に置き換えて比べる）ことを照らす。
  - 2 つ目の commit（英語）: 1 つ目の試験と `src/oldbrief.py` を消し、例の run の値で組んだ新しい指示と、今の md と材料のファイルを並べた物を PR に載せ、2.6 の差の一覧どおりかを審査に出す。
- 読み手の側の試験はそれぞれの block に残す: 報告の「未確認のレンズ」（今の `lib/tests/test_runreport.py:2352` の J110）は、report の試験が line から渡る行で照らす形に替える（report の設計書が決める）。
- 守る keep-essence の番号: 無い（README の 10 節の 12 の仕組みにこの観点は出てこない）。守るのは「宣言のレンズが黙って起きないまま『所見なし』で通らない」と「fork のレンズの消えた所見を『見ていない』と報告に出す」で、上の照らしが見る。
- 終わりの条件の命令（1 モジュールずつ）:

```sh
uv run --isolated python3 -m unittest lib.tests.test_materialkit
uv run --isolated python3 -m unittest discover -s tests/blocks/local_review -t .
uv run --isolated python3 -m unittest tests.layers.test_block_shape
uv run --isolated python3 -m unittest tests.blocks.local_review.test_prompts
```

## 3 script の node

materials.md の 6 節の雛形のまま。この block だけの物:

- `intake.py` が読む入力は `INPUTS_BASE`・`INPUTS_ENTRY`・`INPUTS_LANG` の 3 つ（どれも `ports.text`）。値の dict の鍵は `base`・`entry`・`lang`。
- `role_accept.py` は、`lens_gap` が `CLAUDE_CONFIG_DIR` を読むので、Archon が node に渡す環境をそのまま使う（環境変数を足さない・消さない）。
- 1 つ目の commit だけ、`role_prep.py` が `src.oldbrief.brief(view, values)` を place の `material-local-review-brief.md` に書いてから組む。

## 4 受け付けの文

materials.md の 2.8 と 4 節の文に、2.8 の前の照らしと後の照らしの文（`src/lenses.py` の `lens_gap`・`covers_lenses` が組む日本語の字）を足す。どれも今の `lib/judge_accept.py:2186-2220`・`:2435-2460` の字で、1.5 に書いた違い（持ち越しの尾・入れ直しのパス・graph の名指しを外した）だけを当てる。

## 5 単独で呼ぶ

```sh
bin/works-factory workflow run works-factory-local-review \
  --input base=<差分の根の commit。空なら HEAD>
```

作業ツリーは Archon の cwd（対象のリポジトリ）。出力は `workflow get <run>` の `finish` の返り。始めの記録は要らない。役の起こしに pr-review-toolkit のプラグインが隔離した設定に要るので、起動の殻（`bin/works-factory`）から起こす（殻が `bin/_lib/toolset.py install` を打つ）。`entry` を空でなくすると役を起こさず `skipped` で返る。

## 6 未確認

- 土台の `query-rule` の断片が `spawns` の段落を持つか（materials.md の 3.1 の 3 が前提にする形）。
- `seat` が import する `promptsection` は README の 9.1 で DELETE になる。組み込みで `seat` を軽くする時に、`overlay_body` がこの block から呼べる形のまま残るか（`seat` の使い手の fix・delta-review の設計書と合わせる）。
- 借りたスキルの読み替え `lib/borrow/unattended.md` を英語にするか（今は日本語の写しで、写しの台帳 `lib/borrow/COPIED_FROM` と `seams.json` の錨の試験が字を縛る）。この block は字をそのまま入れる。
- 報告の「未確認のレンズ」の節に、この block の `report` の行のどれを載せるか（素材の 1 行も載るか、見ていないレンズの行だけか）。line と report の配線の決め（materials.md の 1.6 の「報告」）。
- 土台の `ports` の口の名と、5 節の命令の正確な形（prior-decisions.md の 6 節と同じ）。

## 7 自分で決めた事（この block だけ）

- レンズごとの注意の文（`note`）を Python の定数から md に移し、`{skills}` の値を宣言の欄だけにする。訳: 憲法の 2 と README の 5.3。skill の名・`required`・`applies_cond` は md と受け付けが同じ字を持つべき値なので定数に残し、文は md にだけ置く。役に届く中身は変わらない。
- `/code-review` の注意の旗の綴りを、綴りを書かない文に替える。訳: 同じ md の実測の決まり（否定の文の中の綴りも旗に取られる）に、今の値が外れていた。役への求め（旗を付けない）は同じ。
- 借りたスキルの読み替えは、md に写さず値 `{unattended}` で `seat.overlay_body` から入れ、日本語のまま入れる。訳: 源は `lib/borrow/unattended.md` で、版・錨・試験は `lib/borrow/` の台帳が持つ（README の 9.3 の `borrow/`・`seat` は KEEP）。md に英語の写しを置くと源が 2 つになる。読み替えは借りた物の写しの手直しで、この block の決まった文ではない。新しい共通の断片は足さない（使い手の fix・delta-review は種類の節が違うので、同じ字の断片にならない）。
- 読み替えの段を結びの 1 文の前に移す。訳: materials.md の 3.1 の並び（言語の 1 文と結びの 1 文を最後）を守る。今は返答の形の 1 行の後ろに在った。
- 回す時の `due` の字は materialkit の `normal_run`（「判定から入る run でない（入力 entry が空か、対象差分が空でない）——通常の run のため、P1 の役を起こす」）。block 独自の字は持たない。
- `security_surface_touched` を block の入力にせず、`src/lenses.py` の `applies` がいつも真と決まった字を返す。訳: 今も機械は `touches_security_surface` を判定せず真に倒している（`due_view` の docstring「機械は差分の柵を決められないので役を起こす側に倒す」）。読まない入力を足さない（README の 1.2 の P）。
- 見ていないレンズの控えの名を `lenses.json` にする（今は `local-review-lenses.json`）。訳: place は観点ごとに分かれるので、観点の名を前に付ける要が無い。ほかの block は読まない。控えは残す（materials.md の 4 節の 7 が求め、resume や後の調べで受けた回の印を見られる）。
- 見ていないレンズを報告へ渡すのを、`lenses.json` の pointer でなく `report` の行にする。訳: README の 4.1（報告の文は事実を持つ block が組む）と、出力を族の 5 欄にそろえる materials.md の 1.2。report.md の 1.6 も「未確認のレンズ → local-review」とする。
- プラグインの欠けの拒みの文の入れ直しの道を `bin/_lib/toolset.py install` に直す。訳: 今の字の `dev/toolset.py` は元の works の置き場で、工場には無い（`bin/_lib/launcher.py:361-364` が `bin/_lib/toolset.py install` を打つ）。拒みの文は人に見せる文なので、在る道を名指す。
- `lens_gap` から持ち越しの変数 `carry_ok` を外す。訳: 今もいつも偽で、1 run = 1 周では真にならない。読む人に「真になる周が在る」と誤らせない。
- 試験のフォルダの名を `tests/blocks/local_review/` にする（materials.md の 10 節と同じ訳）。
- 実装で決めた事（main の決まりが設計書と食い違った所）:
  - `repo_review_md` の値は、対象の根に `REVIEW.md` が無い回も空の字で渡す。訳: 設計書の 1.5 は「空でなければ足す」と言うが、土台の `prompt.render` は選ばれない段落の中の差し込み口も数え、値が無ければ落ちる（materials.md の 2.11 と同じ決まり）。段落の真偽 `repo_review` が入る・入らないを決める。
  - md の役の 1 段落を `You are the local-review role.` にし、「started in a new conversation」を外した。訳: この輪は `fresh_context: false` で、拒まれた後の回は同じ会話の続きになる。1 回目だけ新しい会話という文は 2 回目以降に嘘になる（調整役の指摘）。fixture の `resolved-text-contains` もこの文に合わせた。
  - `intake` の `due` は materials.md に従い `materialkit.not_entry_due`（`entry` が空でなく差分が空の時だけ回さない）で決める。
  - `covers_lenses` の「宣言したレンズが空」の文は `skills` が空の枝として残した（graph への求めだけを外した）。`LENSES` は空にならないので試験は見ない。
  - 起こし方の照らしは、今の `tests/workflows/test_judge.py` の表を import せず、`tests/blocks/local_review/test_local_review.py` の `LAUNCH` に値を写した（今の定数が消えても残る）。
  - 1 つ目の commit の `oldbrief.py` は、対象の根に `REVIEW.md` が無い回は「対象リポジトリ側」の節を出さない。今の `material_prep` はその回に穴が解けず落ちる（`?` を外して描く）ので、字を比べられるのは `REVIEW.md` が在る回だけ。
