# block の設計書: provenance（根拠の出所検査）

- 何の話か: 対象差分の本文・説明・docstring が根拠に引く「正本は X」「規約は X」「合意済み」の X が、差分の外（差分の根の時点）に在るかを確かめる素材の観点「根拠の出所検査」を、単独で呼べる block `blocks/provenance/` にする設計。差分が自分で足した物を根拠に引く循環と、痕跡の無い外との合意を見つける。素材の観点の族の 1 本で、族の共通の形は [materials.md](materials.md)、書き方の手本は [prior-decisions.md](prior-decisions.md) に従う。型は [README.md](README.md)。
- 決めたこと: 今の judge の `material-route` の 1 列と `provenance-loop`（prep・役・accept）を、5 つの node（intake・prep・役・accept・finish）の block にする。入力は差分の根・判定から入る run の出どころ・言語の 3 つの port だけ。判定から入る run のほかはいつも回し、判定から入る run では役を起こさずに入口の理由つきの `not_applicable` を書く。指示は 1 本の英語の md（`prompts/provenance.md`）にし、今は別のファイルに描いて役に Read させた材料を指示に直に入れる。主張の行（`claims`）は今と同じ形で `material.json` の `reply` に残り、判定役が今と同じ値を読む。振る舞いは変えない。
- 持ち主に求めること: なし。
- 読む人と使い方: この block を作る実装者（1〜3 節の名と順をそのまま作る）。素材の観点の残り 10 本と同じ PR に束ねてよい（README の 11.1 の 1 波目）。

この文書の語は README・materials.md・prior-decisions.md の頭の物を使う。ほかに:

- 出所検査の役（provenance）: 対象差分から事実の主張を抜き出し、主張が根拠に引く物が差分の根の時点に在ったかを `git log -S` などで確かめる AI の役。道具は Read・Grep・Glob・Bash・WebSearch・WebFetch。Bash は網の開いた sandbox の中で走り、写しは作業ツリーの外の一時の置き場に作る（今の `test_run_launch`）。元の graphloops で回す側（writer）に任せた役（「任せ先」）の 1 つ。
- 主張の行: 返答の `claims` の 1 行 `{claim, exists_at_base, evidence}`。主張の文・根拠が差分の根の時点に在ったか・確かめた方法と結果。
- 循環: 差分が自分で足した物を根拠に引いていること（`exists_at_base` が偽の行で、根拠を足したのが同じ差分）。
- 例の run: 本物の run `53e71318-ac9f-4468-ae72-5f6ed569a667`（対象 <owner>/<repo>。置き場 `~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-…/judge/`）。差分の在る通常の run で、変更ファイル 23 件。出所検査の役は 1 回目で受け付けを通った（`material-provenance.json` の `materials.provenance.status` が `found`・`count` 4、`claims` が 17 行。`rejects-provenance.json` は無い）。骨組みの値はここから取った。

## 1 block の全体

### 1.1 役

対象差分の本文・PR の説明・docstring から事実の主張を抜き出し、主張が根拠に引く物が差分の根の時点に在ったかを確かめる。差分が自分で足した物を根拠に引く循環と、根の時点に痕跡の無い外との合意（未確認の前提）を、素材と主張の行で返す。判定から入る run（差分が空で依頼が在る run。materials.md の頭）では役を起こさず、block の出口の `status` を `skipped` にし、素材 `provenance` には入口の理由つきの `not_applicable`（`materialkit.fill_entry` の字）を機械が書く。機械が、作業ツリーを変えていないか・所見の場所がファイルに在るか・素材の欄が決まりに合うかで受け付ける。

### 1.2 port

入力（YAML の `inputs:`）: materials.md の 1.2 の共通の 3 つ（`base`・`entry`・`lang`）だけ。`lang` の説明は `text: 人に見せる欄（material の detail・checked・reason、claims の claim・evidence）の言語。空は依頼の言語`。

出力（`returns: finish`、`outcome_field: ok`）: materials.md の 1.2 の 5 欄だけ。`material.json` の `reply` は受けた返答（`material`・`claims`）、`materials` は `{"provenance": <返答の material>}`。

今との違い: 今は差分の根と入口の印を `judge/start.json` から名で開き、回すかを `material-route` の `provenance_due`（`lib/judge_accept.py:1529-1537`）が決め、判定から入る run の素材を diagnose-prep の `fill_materials` が `material-route.json` の `fill` から埋めた。受けた返答は `judge/material-provenance.json` に書き、判定役の材料が `_diagnose_ctx`（`:2764-2794`）で返答の全部を `out.p1.provenance` として読んだ。

### 1.3 node の並び（`blocks/provenance/works-factory-provenance.yaml`）

materials.md の 1.3 の雛形の `<観点>` を `provenance` にした物。

1. `intake`（script `intake.py`）: port を読み、対象差分を取り、回すかを決め（判定から入る run でなければ回す）、回すなら作業ツリーを写す。返り `{due, reason}`。
2. `provenance-loop`（`loop_group`、最大 3 回、`fresh_context: false`、`until_bash: done=$provenance-accept.output.done; test "$done" = true`、`when: $intake.output.due == true`）
   - `provenance-prep`（script `role_prep.py`。`with:` を持たない）: 指示を組む。返り `{prompt}`。
   - `provenance`（AI）。`prompt: "$provenance-prep.output.prompt"`・`depends_on: [provenance-prep]`。起こし方は今の `test_run_launch`（`workflows/judge/works-factory-judge.yaml:1494-1510`）を字のまま展開する: `model: '@wf-judge-materials'`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob, Bash, WebSearch, WebFetch]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false, failIfUnavailable: true, enableWeakerNetworkIsolation: true, network: {allowedDomains: ['*'], allowLocalBinding: true}, filesystem: {allowWrite: [/], denyWrite: ['~/../archon-home']}}`・`idle_timeout: 1728000000`。今の注記「denyWrite は pr-check の注釈と同じ」は、block の YAML に pr-check が無いので、`net_closed_launch` の `filesystem` の注記 3 行（prior-decisions.md の 1.3 が写す物）をそのまま写す形に替える。`retry: {max_attempts: 2, on_error: all}`。`mutates_checkout:` は今と同じく置かない。`output_format` は今のまま（2.4）。
   - `provenance-accept`（script `role_accept.py`。`with: {reply: $provenance.output}`）: 返り `{ok, done, reason}`。
3. `finish`（script `finish.py`。`depends_on: [intake, provenance-loop]`・`trigger_rule: all_done`）: `material.json` を書き、出力を返す。どの段が落ちても落ちない。

### 1.4 place のファイル

materials.md の 1.4 の名だけ: `intake.json`・`view.json`・`diff.patch`・`changed-files.txt`・`tree.json`（回す時だけ）・`provenance-prompt-<n>.md`・`rejects-provenance.json`・`rejects-provenance.md`・`accepted.json`・`material.json`。観点だけの控えは無い。

1 つ目の commit（11.4 の比べの間）だけ、`material-provenance-brief.md`（今の材料のファイルと同じ字）も書く（2.9）。

### 1.5 コードの置き場

- `blocks/provenance/src/__init__.py`（空）。
- `blocks/provenance/src/viewpoint.py`: materials.md の 5.1 の宣言。中身:
  - `NAME = "provenance"`
  - `MATERIALS = ("provenance",)`
  - `GUARDED = False`（AI の node が `mutates_checkout: false` を持たない。今の accept の `with: {status_guarded: false, …}`。`workflows/judge/works-factory-judge.yaml:1762`）
  - `NA = "never"`、`NA_REASON = ""`（今の `MATERIAL_NODES['p1.provenance']` が `applies_cond` を持たず `na_self_ok: False`。`lib/judge_accept.py:1692-1695`）
  - `due(view, values)`: `materialkit.is_entry_run(view, values)`（`values["entry"]` が在り、かつ対象差分が空）なら `materialkit.entry_skip("出典の確かめ")`（今の `provenance_due` の入口の枝の名詞。判定から入る run `df5e111f-…` の `material-route.json` の `roles.provenance.why` と同じ字になる）。そうでなければ `materialkit.Due(True, "根拠の出所検査は run ごとに 1 回回す（判定から入る run でない。1 run は 1 周で、いつも初回）")`。今の `_because` の字（「初回か、前の周の P3 が何かを直した周——成り立つ（round=1・前の周の P3 が触ったファイルは 0 件）」）は使わない（prior-decisions.md の 1.5 の `due` と同じ決め方。7 節）。
  - `fill(view, values, due)`: `{"provenance": materialkit.fill_entry(values["entry"], 0)}`（`due` が偽になるのは入口の時だけ。今の `_fill_one` の 1 つ目の枝）。
  - `applies(view, values)`: `raise NotImplementedError`。
  - `judged_na(view, values)`: `return False`。
  - `values(view, values)`: `{"repo": str(view.repo), "base": view.base, "diff_file": view.diff_file}`。
  - `when(view, values)`: `{"spawns": False}`（この役は Agent の道具を持たない）。
  - `before(view, values, reply, place)`: `return None, reply, False`。
  - `after(view, values, reply, place)`: `return None`（今の `MATERIAL_NODES` にこの観点の `post_check` は無い）。
  - `after_accept(reply, place)`: 何もしない。
  - `materials_of(reply)`: `{"provenance": reply["material"]} if isinstance(reply.get("material"), dict) else {}`（今の `writes` の `materials.provenance ← material`）。
  - `report_lines(doc)`: `reply` が null なら `[]`。ほかは `claims` のうち `exists_at_base` が偽の行ごとに `f"  - 差分の根に無い根拠: {oneline(claim)}"`（自分で決めた。7 節）。
- `blocks/provenance/src/oldbrief.py`（1 つ目の commit だけ。2.9）: 今の材料のファイルを同じ字で組む `brief(view, values) -> str`。
- `schemas/` は置かない（json の入力が無い）。
- 使う `lib/`: `materialkit`・`rolekit`・`oneline`。

### 1.6 つなぎ方（graph の側。block には書かない）

- 判定のまとめ（`blocks/judge/`）: `include: works-factory-provenance`、`depends_on` は materials.md の 1.6。`with:` は `base: <line が始めの記録から引いた diff_base>`・`entry: <line が始めの記録から引いた出どころの文。判定から入る run でなければ空>`・`lang: <始めの記録の lang>`。
- 読み手: diagnose の `materials`（11 本の `material` の配列の 1 つ）。
  - 素材 `provenance` は `materialkit.assemble` で 15 欄の 1 つになる。
  - 主張の行: 今の判定役の材料は返答の全部（`material` と `claims`）を「根拠の出所検査: {{?out.p1.provenance}}」（`lib/judge_accept.py:2717` の `DIAGNOSE_EXCERPT`、値は `:2783-2784` の `out`）で読む。新しい形では diagnose が `materialkit.read` で開いた `material.json` の `reply` を同じ欄に入れる（読み方は diagnose の設計書が決める。この block は `reply` を今の返答のまま置くだけ）。

## 2 node の設計シート: provenance（出所検査の役）

### 2.1 役

対象差分から事実の主張を抜き出し、主張が根拠に引く物が差分の根の時点に在ったかを確かめ、主張の行と素材の状態を返す。

### 2.2 port

`intake.json` の `view`（← port `base` と作業ツリー。`repo`・`base`・`diff_file`）・`values.lang`（← port `lang`）、拒否の控え（← accept が place に積んだ `rejects-provenance.json`）。

### 2.3 組み立ての順（`prompts/provenance.md`）

materials.md の 3.1 の並び。

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: `rejects-provenance.json` に拒否が 1 件以上。`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "provenance"))`。
2. 役の定義の断片は置かない（今の md の頭は外への検索の決まりの塊だけ。materials.md の 5.2）。
3. `{shared:query-rule}`。`spawns: false`。
4. 役の 1 段落（決まった文）: 自分が provenance の役であること・根拠の出所検査だけをすること。
5. 道具の段落（決まった文。網の開いた Bash と一時の置き場）と `{shared:material-readonly}`。works-gh は使わない（今の md も持たない。網が開いているので gh の口を分けない）。
6. `## Materials` と 3 つの差し込み口: `{diff_file}` ← `view.diff_file`（Read を持つ役なのでパス）、`{base}` ← `view.base`、`{repo}` ← `view.repo`。
7. `## What to do`（決まった文）: 今の md の「元の graphloops の指示書」の段（`material-provenance.md:34-38`）を英語にした物。
8. `{shared:material-status}`。
9. `## Whether you may write not_applicable` と `{shared:material-na}` — 扱いは `never`（`na_never` だけが真。`{na_why}` の値は渡さない）。
10. `## Where to point`、前置きの 1 文（この役の返答には `where` の欄が無い）、`{shared:material-where}`。
11. 言語の 1 文と `{lang}`。
12. 結びの 1 文。

md の本文（英語。この block の 2 つ目の commit でこのまま置く）:

```markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{shared:query-rule}

You are the provenance role. Your only job is to check where the grounds that the target diff cites come from.

Your tools are Read, Grep, Glob, Bash, WebSearch, and WebFetch. Bash runs inside a sandbox; make any copy in a temporary folder outside the target (for example one made with `mktemp -d`). The wrapper stops writes to the target's working tree.

{shared:material-readonly}

## Materials

- Target diff (Read it): {diff_file}
- Base commit: {base}
- Repository: {repo}

## What to do

From the body of the target diff, the pull request description, and the docstrings, extract the factual claims such as "the source of truth is X", "the convention is X", or "this was agreed". For each, check that X is not inside the target diff: look at whether X existed at the base commit (for example with `git log -S`).

- If the diff cites as grounds something that the diff itself adds, that is circular. Pass it on as material for the judgment step (the diagnose role of this run reads this answer): set `exists_at_base` of that `claims` row to false, write in `evidence` the proof of the circle (the place in the diff that adds X, and the result of the command you ran), set `material.status` to `found`, and write it in `count` and `detail`.
- Treat a claim of agreement with an outside party (another team, another system, an upstream source) as an unconfirmed premise when the base commit holds no trace of it.
- Write the claims in `claims`. `claims` is a top-level field, separate from `material`. Write one row per extracted claim: `claim` (the sentence of the claim), `exists_at_base` (whether X existed at the base commit; a boolean), and `evidence` (how you checked it and what you found).

{shared:material-status}

## Whether you may write not_applicable

{shared:material-na}

## Where to point

This role's answer has no `where` field. When `material.detail` or an `evidence` names a place in the current working tree, write it as below.

{shared:material-where}

Write `material.detail`, `material.checked`, `material.reason`, and the `claim` and `evidence` of each `claims` row in {lang}. Keep keys, enum values, identifiers, paths, commands, and quoted text as they are.

Return only JSON that matches the output schema.
```

md の中に、`$` の直後に英字か `{` が続く字は無い（materials.md の 3.1 の終わり）。

言語・会話・`{` の扱いは prior-decisions.md の 2.3 の終わりと同じ。

### 2.4 返す形

今の `output_format` のまま（`workflows/judge/works-factory-judge.yaml:1729-1756`）:

- `material`: prior-decisions.md の 2.4 と同じ形。
- `claims`: `[{claim, exists_at_base (boolean), evidence}]`・各行 `additionalProperties: false`・`required: [claim, exists_at_base, evidence]`。
- 全体 `additionalProperties: false`・`required: [material, claims]`。

人に見せる欄は `material.detail`・`material.checked`・`material.reason`・`claims` の `claim`・`evidence`（判定の材料と報告に載る）で、言語は `{lang}`。例の run の `claims` は 17 行とも日本語で、主張の文を言い換えて書いていた（字のまま引いた主張は「quoted text」としてそのまま残る）。

### 2.5 描いた骨組み（例の run の値）

例の run では、今の指示は 2 か所に在った: `workflows/judge/commands/material-provenance.md`（47 行。`$provenance-prep.output.lang_line`・`.reason`・`.brief_file` を Archon が入れた物）と、役が Read した `judge/material-provenance-brief.md`（19 行）。新しい指示はこの 2 つを 1 本にする:

```markdown
{shared:query-rule の本文: Rules for queries to outside services …}

You are the provenance role. …（決まった文）

Your tools are Read, Grep, Glob, Bash, WebSearch, and WebFetch. Bash runs inside a sandbox; make any copy in a temporary folder outside the target …

{shared:material-readonly の本文: Do not change a single character of the target's working tree, …}

## Materials

- Target diff (Read it): ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-ac9f-4468-ae72-5f6ed569a667/judge/provenance/diff.patch
- Base commit: 7defb7ec5fac098b7302f5bfc11a02f151f4d262
- Repository: ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/worktrees/archon/task-works-factory-line-1792307529854

## What to do

From the body of the target diff, the pull request description, and the docstrings, extract the factual claims …（決まった文と箇条 3 つ）

{shared:material-status の本文: How to write `material`: `status` is one of the following. …}

## Whether you may write not_applicable

This viewpoint has no condition under which it does not apply, so the acceptance step rejects `not_applicable`. …

## Where to point

This role's answer has no `where` field. …

Write the `<path>:<line>` of a location (`where`) as a line number in the current file in the working tree. …

Write `material.detail`, `material.checked`, `material.reason`, and the `claim` and `evidence` of each `claims` row in the language of the request (the user's language). …

Return only JSON that matches the output schema.
```

`Target diff` のパスは、判定のまとめの include の id を `judge`・`provenance` と置いた時の新しい place（今は `judge/diff.patch`。中身は同じ）。`Base commit` と `Repository` は例の run の材料のファイルの「## 材料: record.base」「## 材料: inputs.cwd」の節の字と同じ。例の run は 1 回目で通ったので却下の段落は入らない。`lang` は空（例の run の始めの記録の `lang` が無い）で、`{lang}` に既定の文が入った形。

回さない道（判定から入る run `df5e111f-ea97-409b-8066-2245d32746ab` の本物の値）: `intake` の `due` が偽、`finish` の `status` が `skipped`、`reason` が「判定から入る run の周（入口の印が在り、修正がまだ 1 ファイルも入っていない）のため、出典の確かめを起こさない」（その run の `roles.provenance.why` と同じ字）。素材は `fill_entry` の字で、今の `fill.provenance` の「この周の判定に届く人の依頼 1 件」の句だけが「この周の判定に届く人の依頼の件数は渡されていない」に替わる（materials.md の 2.6）。

### 2.6 今の指示との差

今の指示は `workflows/judge/commands/material-provenance.md`（47 行）と、`lib/judge_accept.py` の `material_prep`（`:2116-2135`）が描く材料のファイルの 2 か所に在る。prior-decisions.md の 2.6 と同じ移し方（材料の節 → `## Materials`、『条件に当たらない』の節 → `{shared:material-na}`、却下の段落 → `{shared:rejected}`、作業ツリーを変えるな → `{shared:material-readonly}`、素材の書き方 → `{shared:material-status}`、所見の場所 → `{shared:material-where}`、言語の 1 行 → md の 1 文、graphloops のノードの名指しと区切りを消した）。この観点だけの差:

- 移した: 頭の外への検索の決まりの塊（md:3-10。「Agent で子を起こすなら…含めよ」の前置きつき）を `{shared:query-rule}` に。前置きは断片の `<!-- if spawns -->` の段落に当たり、この役は Agent を持たないので入らない。
- 移した: md:28 の道具の段（網の開いた Bash・写しは `mktemp -d` の一時の置き場・作業ツリーへの書き込みは包みが止める）を道具の段落に。尾の「対象の作業ツリー…を 1 文字も変えるな…同じ時に別の素材集めの役も走っている」は `{shared:material-readonly}` の「走りうる」に。
- 消した: md:34 の見出し「# P1 根拠の出所検査（writer が実行）」。段の名（P1）と回す側（writer）は元の graphloops の型の名残で、役の振る舞いを変えない。
- 言い換えた: md:38 の「素材として P2 へ渡す（P2 は素材を読んで判定する段で、この run では診断の役 diagnose がこの役の返答を読む」（#221 の足し）を「Pass it on as material for the judgment step (the diagnose role of this run reads this answer)」に。段の名 P2 は役が知らなくてよい名なので落とし、読み手の言い方だけを残した。渡し方（`exists_at_base` 偽・`evidence` に循環の証拠・`found`）と `claims` の欄の説明（どちらも #221 の足し）は字の中身のまま箇条にした。
- 足した: `## Where to point` の前置きの 1 文（この役の返答には `where` の欄が無く、`material.detail` と `evidence` が場所を名指す時に下の書き方に従う）。訳: 今の md は所見の場所の段を前置きなしで置いていて、`where` の欄を持たない役が段の当て先を推すことになっていた。受け付けの照らしは今も新しい形も `where` と `text` を持つ行だけを見るので、この役の返答には当たらない（2.8）。materials.md の 3.1 の 10 が名指す「観点ごとの前置きの文」に当たる。
- 移した: md:39 の素材の書き方（尾の「欄と値の正本は review-record.py」は消した。役が開かない物の名指し）。
- 英語にした（#764）。役の名「根拠の出所検査の役（任せ先）」は "the provenance role"（「任せ先」は元の graphloops の回す側の割り当ての名で、役の振る舞いを変えない）。

### 2.7 元の works と graphloops の同じ場面

族の形の差は materials.md の 9 節。この観点だけの差:

- 元の works の `works/blk-material/commands/provenance.md`（7 行）は、engine が描いた graphloops の指示書のファイル（`prompt_file`）を Read で読ませる薄い md だった。工場は graphloops の指示書を md の中に写し、値だけを材料のファイルにした（#76）。新しい形は値も指示の中に入れる。
- 元の graphloops の指示書（元の works の写し `works/.shared/core/gl-prompts/prompts/review-loop/p1.provenance.md`、6 行）と graphloops の今の指示書（`~/src/claude-plugins/graphloops/prompts/review-loop/p1.provenance.md`）は、差分のファイルの穴の名（`loop.diff_file` と `hist.snapshot.diff_file`）と語の言い回しだけが違う。工場はそこに、循環を判定役へ渡す渡し方と `claims` の欄の説明を足した（#221）。この block も持つ。
- graphloops の graph（`graphs/review-loop.json` の `p1.provenance`）は回す側（`run_by: writer`）に任せ、任せる先の模型を `delegate: {model: sonnet}` で決めた。工場は素材の群の名 `'@wf-judge-materials'`（今の `tests/workflows/test_judge.py:98` の表で sonnet・medium）で起こす。模型は同じ。
- graphloops の graph は `na_reason_note`「正当な not_applicable は無い: 事実の主張が無いのは『見たが無かった』＝clean」を持つ。指示書には無く、engine も役に渡さない（graph の注記）。工場と新しい形は `NA = "never"` と `{shared:material-na}` の `na_never` の段落（「見た結果を found か clean で書け」）で同じ事を役に伝える。
- 返答の型（`material`・`claims`）と書き先（素材 `provenance`）は、元の works・graphloops・工場で同じ（graphloops の `blocks/review-loop/material/exit.schema.json` の `p1.provenance` と今の `output_format` は同じ欄）。`claims` は graphloops の `writes` に無く、判定役は節の出力（`out.p1.provenance`）で読む。
- 受け付け: この観点に `post_check` は無い（graphloops の `MATERIAL_NODES` も持たない）。

この block が両方より良く、残す物: 循環の渡し方を役に名指す（#221。graphloops は「素材として P2 へ渡す」だけ）・網の開いた役の作業ツリーの変化を機械が照らす。

### 2.8 受け付け

materials.md の 4 節の順のまま。観点の前の照らしと後の照らしは無い。

- 拒む物: JSON のオブジェクトでない返答・役が作業ツリーを変えた（`GUARDED` が偽なので `porcelain` を含む `TREE_KEYS` の全部。今の `test_material_role_changed_the_tree_rejected` が provenance で照らす振る舞い）・素材 `provenance` が無い・`carried_over`・`not_applicable`（`never`）・知らない status・status ごとの要る欄の欠け。
- 所見の場所の照らし（materials.md の 4 節の 4）は通るが、この役の返答は `where` と `text` を両方持つ行を持たない（`claims` の行は `claim`・`exists_at_base`・`evidence`）ので、拒む物は出ない。今と同じ（`lib/judge_accept.py:2463-2471` の `_where_rows`）。
- 3 回目の拒否でループを抜け、`finish` が `status: gave_up`・素材 `provenance` に `not_run` と訳を書く（materials.md の 2.10 の 4）。

### 2.9 試験

- standalone の fixture（`blocks/provenance/fixtures/`）:
  - `standalone.stubs.yaml`: `fixture.inputs` は `base: ""`・`entry: ""`・`lang: ""`。AI の node `provenance` だけを台本の返答（`material.status: clean`・`checked` 1 行・`claims: []`）で差し替え、script は本物（`--exec-code`）。`reached` に `finish`。`finish` の出力の `status` が `ran`。差分が空でも回す（今の `provenance_due` も差分を見ない）。
  - `gave-up.stubs.yaml`: 台本の返答が 3 回とも `material.status: carried_over`（`from_round: 1`・`reason` つき。今の `test_accept_rules` の provenance の返答と同じ形）。`finish` の `status` が `gave_up`、run は `completed`。
  - `skipped.stubs.yaml`: `entry: "人の依頼（standalone）"`。AI の node に届かず、`finish` の `status` が `skipped`、素材が `fill_entry` の字。
- `tests/blocks/provenance/test_provenance.py`: materials.md の 8 節の block の試験（使い捨ての `ARTIFACTS_DIR` と git のリポジトリ、port の値だけ）。
  - 写す元 `lib/tests/test_judge_accept.py::MaterialCase.test_accept_rules` の provenance の行: 走った観点の `carried_over` は拒まれる（拒みの文は materials.md の 2.8 の「観点 provenance」の字）。
  - 写す元 `MaterialCase.test_material_role_changed_the_tree_rejected`（provenance で回す今の試験）: 役が作業ツリーにファイルを足した回は拒まれ、拒みの文が「変えたのがこの役とは限らない」を言う。族の部品の試験にも同じ照らしが在るが、網の開いた起こし方のこの観点で block を通して 1 回回す。
  - 写す元 `DueCase.test_run_with_a_diff_runs_them` と `test_empty_diff_run_with_requests_runs_only_prior_decisions` の provenance の部分: `entry` が空なら `due` が真、在れば偽で `finish` の `reason` が `entry_skip("出典の確かめ")` の字。
  - 足す: 見た返答（`found`・`count`・`detail`・`claims` 2 行）は `material.json` の `reply.claims` に字のまま載り、`materials` が `{"provenance": <返答の material>}`。`report` に `exists_at_base` が偽の行だけが出る。
  - 足す（起こし方の照らし）: block の YAML の AI の node の `model`・`allowed_tools`・`sandbox`・`idle_timeout`・`retry` が、今の `tests/workflows/test_judge.py:98` の表の provenance の行（`"sonnet", "medium", INVESTIGATE, DELEGATE, False, …`）が照らす物と同じ。
- 指示の比べ（README の 11.4）: `tests/blocks/provenance/test_prompts.py`。prior-decisions.md の 2.9 と同じ 2 つの commit の形。1 つ目の commit の値の口は `lang_line`・`reason`・`brief_file`（今の md が `$provenance-prep.output.<欄>` で読む 3 つ）。値は例の run の値（`base`・リポジトリのパス・差分のパス）で、`oldbrief.brief` の字が例の run の `judge/material-provenance-brief.md` と同じ（リポジトリと差分のパスは試験の物に置き換えて比べる）ことを照らす。
- 守る keep-essence の番号: 無い（README の 10 節の 12 の仕組みにこの観点は出てこない。keep-essence の 5 の「書き込みの出どころ」は `lib/writes.py` の別の仕組みで、この観点ではない）。
- 終わりの条件の命令: materials.md の 8 節の 4 行の `<観点の package の名>` を `provenance` にした物。

## 3 script の node

materials.md の 6 節の雛形のまま。`intake.py` が読む入力は `INPUTS_BASE`・`INPUTS_ENTRY`・`INPUTS_LANG` の 3 つで、どれも `ports.text(…)`。値の dict の鍵は `base`・`entry`・`lang`。1 つ目の commit だけ、`role_prep.py` が `src.oldbrief.brief(view, values)` を place の `material-provenance-brief.md` に書いてから組む。

## 4 受け付けの文

materials.md の 2.8 と 4 節の文だけを使う。この観点が足す拒みの文は無い。

## 5 単独で呼ぶ

```sh
bin/works-factory <読ませるフォルダを blocks/ にする引数（名は土台の PR で決める）> workflow run works-factory-provenance \
  --input base=origin/main
```

作業ツリーは Archon の cwd。`base` から作業ツリーの今の姿までの差分の主張を、`base` の時点で確かめる。始めの記録は要らない。

## 6 未確認

- prior-decisions.md の 6 節の 2 つ（起動の殻の引数。この観点は役の定義の断片を使わない）。
- query-rule の断片の「足りない」の欄の文（world.md の 10 節）を、その欄を持たないこの役に残してよいか。この役は `evidence` に「引いていない」と書いてきた（例の run の `claims` の 1 行「この回は引いていない。人か P2 の確認に回す」）ので、今と同じ振る舞いで足りると見た。

## 7 自分で決めた事（この block だけ）

- 回す時の `Due` の訳を、今の `_because` の字でなく「run ごとに 1 回回す」の字にする。訳: 1 run = 1 周（持ち主の決め carry）で、前の周の P3 の枝はいつも効かない。prior-decisions.md の 1.5 と同じ決め方。判定役に届く素材の字は入口の埋め（`fill_entry`）だけで、それは族の部品が決める。
- 起こし方の注記「denyWrite は pr-check の注釈と同じ」を、`net_closed_launch` の注記 3 行の写しに替える。訳: block の YAML の中に pr-check は無く、注記が指す先を読めない。block はほかの block を名指さない（憲法の 3）。
- `## Where to point` に前置きの 1 文を足す。訳: 2.6。役の返答の形も受け付けも変わらない。
- md の「P2」「writer」の段の名を落とす。訳: 役が自分の返答を決めるのに要らない graphloops の型の名で、残すと役が「P2」を探す。読み手が判定役であることは残した。
- `report_lines` に差分の根に無い根拠の行を足す。訳: 循環と未確認の前提は人が報告で見て直す物で、`claims` の 17 行の全部を出すと素材の節が長くなる。`exists_at_base` が偽の行だけにした（例の run では 17 行のうち 7 行）。報告に載せるかは line と report の配線の決め（materials.md の 1.6）。
- 試験のフォルダの名を `tests/blocks/provenance/` にする（`-` を持たない名なのでそのまま）。
- 実装で決めた事（#765 の実装）:
  - `fill` の `fill_entry` に渡す件数は `None`（「依頼の件数は渡されていない」）にする。訳: この観点は `request` の入力を持たず、materials.md の 2.6 が「`request` を持たない観点は `None`」と決めている。1.5 の `0` は 2.5 の「句が替わる」と食い違っていた。
  - 役の 1 段落から「started in a new conversation」を外し、「You are the provenance role.」にする。訳: 輪は `fresh_context: false` で、2 回目からは同じ会話の続きに指示が届くので、新しい会話とは言えない（調整役の注意）。fixture の決まった文もこの文にした。
  - 輪の中の node の `depends_on` は雛形のまま（prep は先頭で、役は prep だけに依る）。訳: 出し直し専用の prep が無く、役の直前に同じ層の node が 2 つ並ぶ形が無い。
  - 指示の比べ（1 つ目の commit）の日本語の md は共通の断片を使わず、今の md の字をそのまま置いた（断片は英語のため）。値の口は `lang_line`・`reason`・`brief_file`。`lang_line` には port `lang` の値（空なら既定の言語の英語の文）を入れた。
