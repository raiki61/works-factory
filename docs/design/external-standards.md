# block の設計書: external-standards（外部標準照合）

- 何の話か: 対象差分が解いている問題を一般の問題の類に言い直し、リポジトリの外の一次情報（公式文書・標準・当該 OSS の issue と PR・ソース）で、枯れた定番解からの逸脱・定番解の劣化変種・手元の依存の使い残しを見る素材の観点「外部標準照合」を、単独で呼べる block `blocks/external-standards/` にする設計。族の共通の形は [materials.md](materials.md)、1 本目の手本は [prior-decisions.md](prior-decisions.md)。型は [README.md](README.md)。
- 決めたこと: 今の judge の `material-route` の 1 列と `external-standards-loop`（prep・役・accept）を、materials.md の 5 つの node の block にする。入力は差分の根・固めた目的・判定から入る run の出どころ・言語の 4 つの port。判定から入る run では役を起こさず、出どころつきの `not_applicable` を書く。今は別のファイルに描いて役に Read させた材料と、prep の出力で入れていた観点の正本のパスを、指示の中に直に入れる。順位の行の照らし（今の `external_rankings`）は block の `src/` に写す。振る舞いは変えない。
- 持ち主に求めること: なし。
- 読む人と使い方: この block を作る実装者（1〜4 節の名と順をそのまま作る）。素材の観点の残り 10 本と同じ PR の束に入る（README の 11.1 の 1 波目）。

この文書の語は README・materials.md・prior-decisions.md の頭の物を使う。ほかに:

- 外部標準照合の役（external-standards）: 対象差分・変更ファイル・目的の文・自覚済みの弱点・観点の正本を渡され、web と手元の依存を当たって定番解からの逸脱を返す AI の役。役の定義は investigator。道具は Read・Grep・Glob・Bash・WebSearch・WebFetch（prior-decisions と同じ起こし方。Bash は網の閉じた sandbox の中）。
- 順位の行: 返答の `rankings` の 1 行 `{problem, source, ranked, diff_at, why_not_higher?}`。一般化した問題ごとに、一次情報が選択肢に付けた順位（`ranked`、上位から）と、差分が乗る選択肢（`diff_at`。`ranked` のどれかの字のまま）と、最上位でない時に上位を採れない理由。
- 観点の正本: 工場の `lib/REVIEW.md` の節「外部標準照合観点」と「指摘の提出基準」（と、在れば対象の根の `REVIEW.md`）。パスは `materialkit.review_md_paths(repo)`（materials.md の 5.2 の終わり）。
- 例の run: 本物の run `53e71318-ac9f-4468-ae72-5f6ed569a667`（対象 <owner>/<repo>。置き場 `~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-…/judge/`）。差分の在る run（23 ファイル）で、役は 1 回目に拒まれ（`rejects-external-standards.json` の 1 件。`diff_at` が `ranked` の字に無い）、2 回目で受け付けを通った（`material-external-standards.json` の `materials.external_standards.status` が `found`、`count` 2、`rankings` 1 行）。骨組みの値はここから取った。

## 1 block の全体

### 1.1 役

差分が解いている問題を一般の問題の類にし、外の一次情報で、その類の定番解・順位・既知の落とし穴を確かめ、差分がどの順位に乗るか・手元に宣言済みの依存で済むのに自作していないかを返す。見た範囲と見ていない範囲も返させる。機械が、作業ツリーを変えていないか・所見の場所がファイルに在るか・順位の行の差分の乗る所が順位の字に在り、最上位でなければ訳が在るか・素材の欄が決まりに合うかで受け付ける。判定から入る run では役を起こさない。判定から入る run かは port `entry` だけで決める: line（メイングラフ。run の始めに始めの記録を書き、判定のまとめを通して block に port の値を配る）は差分が空で人の依頼が在る run にだけ `entry` に出どころの文を入れて渡し、block は差分と依頼から推し直さない（prior-decisions と同じ。materials.md の 10 節）。単独の run でも `materialkit.is_entry_run`（`entry` が空でなく、かつ block が測った対象差分が空）で決め、差分が在る run は `entry` に字を入れても回す（2.9 の `skipped.stubs.yaml` はこれで回さない道を確かめる）。

### 1.2 port

入力（YAML の `inputs:`）:

- `base`・`entry`: materials.md の 1.2 の字のまま（`base` は対象差分の根の commit。空は HEAD。`entry` は判定から入る run の出どころの文。空はそうでない run。1.1）。
- `purpose`: materials.md の 1.2 の字のまま（`json(purpose.schema.json)`。既定 `null`）。schema の中身は [purpose-review.md](purpose-review.md) の 1.5 と字のまま同じ物を `blocks/.shared/schemas/purpose.schema.json`（`shared:purpose.schema.json`）に置く。
- `lang`: `text: 人に見せる欄（material の detail・checked・reason、findings の text・mechanism・measured・false_positive_if、seen・unseen、rankings の problem・ranked・diff_at・why_not_higher、rankings_none）の言語。空は依頼の言語`。既定 `""`。

出力（`returns: finish`、`outcome_field: ok`）: materials.md の 1.2 の 5 欄だけ。`material.json` の `reply` は受けた返答（`material`・`findings`・`seen`・`unseen`・`web_refetched`・`rankings`・`rankings_none?`）、`materials` は `{"external_standards": <返答の material>}`。

今との違い: 今は目的を `judge/purpose.json` から名で開き、無ければ目的の文の欄に「目的の文はこの run に無い…」の文（`PURPOSE_MISSING`、`lib/judge_accept.py:1219-1220`）を入れた（`_purpose_or_missing`、`:2078-2080`）。観点の正本のパスは prep の出力の欄 `review_md`・`repo_review_md` で md に入れた（`workflows/judge/commands/material-external-standards.md:41`）。受けた返答は `judge/material-external-standards.json` に書いた。

### 1.3 node の並び（`blocks/external-standards/works-factory-external-standards.yaml`）

materials.md の 1.3 の雛形の `<観点>` を `external-standards` にした物。

1. `intake`（script `intake.py`）: port を読み、対象差分を取り、回すかを決め（判定から入る run でなければ回す）、回す時は作業ツリーを写す。返り `{due, reason}`。
2. `external-standards-loop`（`loop_group`、最大 3 回、`fresh_context: false`、`until_bash: done=$external-standards-accept.output.done; test "$done" = true`、`when: $intake.output.due == true`）
   - `external-standards-prep`（script `role_prep.py`）: 指示を組む。返り `{prompt}`。
   - `external-standards`（AI）。`prompt: "$external-standards-prep.output.prompt"`・`depends_on: [external-standards-prep]`。起こし方は今の `net_closed_launch`（`workflows/judge/works-factory-judge.yaml:464-480`）を字のまま展開する（中身は prior-decisions.md の 1.3 の 2 と同じ。注記 3 行も写す）。`retry: {max_attempts: 2, on_error: all}`。`mutates_checkout:` は今と同じく置かない。`output_format` は今のまま（2.4）。
   - `external-standards-accept`（script `role_accept.py`。`with: {reply: $external-standards.output}`）: 返り `{ok, done, reason}`。
3. `finish`（script `finish.py`。`depends_on: [intake, external-standards-loop]`・`trigger_rule: all_done`）: `material.json` を書き、出力を返す。

### 1.4 place のファイル

materials.md の 1.4 の名だけ: `intake.json`・`view.json`・`diff.patch`・`changed-files.txt`・`tree.json`・`external-standards-prompt-<n>.md`・`rejects-external-standards.json`・`rejects-external-standards.md`・`accepted.json`・`material.json`。

1 つ目の commit（2.9 の指示の比べの間）だけ、`material-external-standards-brief.md`（今の材料のファイルと同じ字）も書く。2 つ目の commit で書かなくなる。

### 1.5 コードの置き場

- `blocks/external-standards/src/__init__.py`（空）。
- `blocks/external-standards/src/viewpoint.py`: materials.md の 5.1 の宣言。中身:
  - `NAME = "external-standards"`
  - `MATERIALS = ("external_standards",)`
  - `GUARDED = False`（AI の node が `mutates_checkout: false` を持たない。今の accept の `with: {status_guarded: false}`。`workflows/judge/works-factory-judge.yaml:1382`）
  - `NA = "never"`、`NA_REASON = ""`（今の `MATERIAL_NODES['p1.external_standards']` が `applies_cond` を持たず `na_self_ok: False`。`lib/judge_accept.py:1661-1667`）
  - `STANDARDS_SECTION = "外部標準照合観点"`、`CRITERIA_SECTION = "指摘の提出基準"`（観点の正本の見出しの字。md と正本の字が合うべき値。README の 5.3）
  - `due(view, values)`: `values["entry"]` が空でなければ `materialkit.entry_skip("外部標準の照合")`（今の `external_standards_due` の入口の枝の字。`:1521-1524`）。空なら `materialkit.Due(True, "外部標準の照合は、判定から入る run でなければ run ごとに 1 回回す（1 run は 1 周で、いつも初回）")`。今の `:1525-1527` は「初回か、機構を足した／変えた周か、前の周の P3 が何かを直した周——成り立つ（round=1・前の周の P3 が触ったファイルは 0 件）」を返す（例の run の `material-route.json` の `roles.external-standards.why`）。P3 は graphloops の段の名で修正の段。1 run = 1 周なので「前の周の P3」と「機構を変えた周」の枝はいつも効かず、成り立つのは「初回」の枝だけなので、効かない枝の名を外した字にした（自分で決めた。7 節。prior-decisions.md の 1.5 と、ほかの P1 の観点の設計書と同じ替え方）。
  - `fill(view, values, due)`: `{"external_standards": materialkit.fill_entry(values["entry"], None)}`（`due` が偽になるのは `materialkit.is_entry_run(view, values)` が真の時〔判定から入る run〕だけ。依頼の行の port `request` を持たないので、依頼の件数には `None` を渡し、materials.md の 2.6 の「件数は渡されていない」の句になる）。
  - `applies(view, values)`: `raise NotImplementedError`。
  - `judged_na(view, values)`: `return False`。
  - `values(view, values)`: 次の dict。`dump` は materials.md の 3.3 の `json.dumps(x, ensure_ascii=False, indent=1)`。`own, theirs = materialkit.review_md_paths(view.repo)`。
    - いつも: `"diff_file": view.diff_file`・`"changed_files": dump(list(view.changed_files))`・`"repo": str(view.repo)`・`"review_md": own`・`"standards_section": STANDARDS_SECTION`・`"criteria_section": CRITERIA_SECTION`。
    - `values["purpose"]` が null でない時だけ中身を入れる（null の時は空の字）: `"purpose_text": values["purpose"]["purpose_text"]`・`"known_weaknesses": dump(values["purpose"]["known_weaknesses"])`。
    - `"repo_review_md": theirs`（いつも渡し、段落が入らない時は空の字）。
  - `when(view, values)`: `_, theirs = materialkit.review_md_paths(view.repo)` を自分で呼び直し、`{"spawns": False, "purpose": values["purpose"] is not None, "repo_review": bool(theirs)}` を返す（`values` の中の `theirs` は `when` から見えないので、同じ口を 2 回呼ぶ。口はファイルの在りを見るだけで副作用が無い）（`spawns` は外への検索の決まりの断片の段落。この役は Agent の道具を持たない）。
  - `before(view, values, reply, place)`: `return None, reply, False`。
  - `after(view, values, reply, place)`: `return src.rankings.problem(reply)`（4 節）。
  - `after_accept(reply, place)`: 何もしない。
  - `materials_of(reply)`: `{"external_standards": reply["material"]} if isinstance(reply.get("material"), dict) else {}`（今の `writes` の `materials.external_standards ← material`。`:1665`）。
  - `report_lines(doc)`: `reply` が null なら `[]`。在れば `rankings` の行ごとに `f"  - 順位: {oneline(problem)}——差分は {k} 位／{len(ranked)} 位中（{oneline(diff_at)}）"`（`k` は `ranked.index(diff_at) + 1`。受け付けを通った返答では `diff_at` はいつも `ranked` に在る）。`rankings` が空なら `f"  - 順位: 付けられる問題なし（{oneline(rankings_none)}）"` の 1 行。字下げ 2 つで、materials.md の 2.10 の素材の 1 行の下に並ぶ。
- `blocks/external-standards/src/rankings.py`: 順位の行の照らし。公開の名は `problem(reply) -> str | None` だけ。写す元（`lib/judge_accept.py`）: `external_rankings`（`:2146-2157`。`Reject` を上げる代わりに拒む文を返し、通れば `None`）・`blank`（`:248-251`）・`EMPTY`（`:244-245`。字のまま）。
- `blocks/.shared/schemas/purpose.schema.json`（`shared:purpose.schema.json`）: [purpose-review.md](purpose-review.md) の 1.5 の字のまま。
- 使う `lib/`: `materialkit`・`rolekit`・`oneline`。

### 1.6 つなぎ方（graph の側。block には書かない）

- 判定のまとめ（`blocks/judge/`）: `include: works-factory-external-standards`、`depends_on` は materials.md の 1.6。`with:` は `base`・`entry`・`lang` を materials.md の 1.6 のとおり、`purpose: $purpose.output.purpose`（目的の block の `purpose.json` の pointer。目的の block が `failed` の run は、目的の block の設計書のとおり graph が判定の前で止めるので、ここに null が来るのは単独の run と目的の block を外した run だけ）。
- 読み手: diagnose の `materials`（11 本の `material` の配列の 1 つ。素材 `external_standards` の欄）。判定役の材料の「外部標準」の所見の行（今の `record.process.external_findings`。`lib/judge_accept.py:2770`・`:2776`）は、`role` が `external-standards` の doc の `reply.findings` から取る（diagnose の設計書の決め）。
- `rankings` は今どの役の材料にも入っていない（graphloops の `writes` の `process.external_rankings` を工場は写したが、`_diagnose_ctx` は読まない）。新しい形も `reply` に残し、報告の行（1.5 の `report_lines`）だけが読む。

## 2 node の設計シート: external-standards（外部標準照合の役）

### 2.1 役

差分の問題の類を外の一次情報で確かめ、定番解からの逸脱・劣化変種・依存の使い残しの所見と、順位の行と、見た範囲・見ていない範囲・素材の状態を返す。

### 2.2 port

`intake.json` の `view`（← port `base` と作業ツリー。`repo`・`diff_file`・`changed_files`）・`values.purpose`（← port `purpose`。`purpose_text`・`known_weaknesses`）・`values.lang`（← port `lang`）、観点の正本のパス（← `materialkit.review_md_paths(view.repo)`）、拒否の控え（← accept が place に積んだ `rejects-external-standards.json`）。

### 2.3 組み立ての順（`prompts/external-standards.md`）

materials.md の 3.1 の並び。

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: `rejects-external-standards.json` に拒否が 1 件以上。`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "external-standards"))`。
2. `{shared:role-investigator}`。
3. 役の 1 段落（決まった文）: 外部標準照合だけ・局所の所見を渡していない訳（所見に寄ると問題の類の取り出しがそこへ寄る）。
4. 道具の段落（決まった文）、`{shared:works-gh}`、`{shared:material-readonly}`。
5. `## Materials` と差し込み口: `{diff_file}` ← `view.diff_file`（Read させるパス）、`{changed_files}` ← `view.changed_files`（JSON の配列の字）、`{repo}` ← `view.repo`、`<!-- if purpose -->` `{purpose_text}` ← `values.purpose.purpose_text`・`{known_weaknesses}` ← `values.purpose.known_weaknesses`（JSON の配列の字）`<!-- end purpose -->`、`<!-- if not purpose -->` 目的の文の無い run の 1 文（決まった文）`<!-- end purpose -->`、`{review_md}`・`{standards_section}`・`{criteria_section}` ← 2.2、`<!-- if repo_review -->` `{repo_review_md}` `<!-- end repo_review -->` — 条件 `repo_review`: 対象の根に `REVIEW.md` が在る。
6. `## What to do`（決まった文）: 今の graphloops の指示の段（`material-external-standards.md:47-59`）を英語にした物。
7. `{shared:material-status}`。
8. `## Whether you may write not_applicable` と `{shared:material-na}` — 扱いは `never`。
9. `## Where to point` と `{shared:material-where}`。
10. 言語の 1 文と `{lang}`。
11. 結びの 1 文。

md の本文（英語。この block の 2 つ目の commit でこのまま置く）:

```markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{shared:role-investigator}

You are the external-standards role. Your only job is to check the target diff against external standards: look outside the repository (the web, official documentation, the issues, pull requests, and source of the open-source projects involved) for deviations from the established solutions of the ecosystem, and for dependencies already at hand that the diff leaves unused. You are not given the local findings: if you saw them, your choice of problem classes would drift toward them.

Your tools are Read, Grep, Glob, Bash, WebSearch, and WebFetch. Bash runs inside a sandbox, and its network is closed: it cannot reach any destination.

{shared:works-gh}

{shared:material-readonly}

## Materials

- Target diff (Read it): {diff_file}
- Files the target diff touches: {changed_files}
- Repository: {repo}
<!-- if purpose -->
- Original purpose: {purpose_text}
- Weaknesses already known and accepted: {known_weaknesses}
<!-- end purpose -->
<!-- if not purpose -->
- Original purpose: no purpose text is given in this run. Do not guess the purpose to fill it in; draw the problem classes from the diff and the dependencies.
<!-- end purpose -->
- The viewpoint's source of truth: Read the section "{standards_section}" of {review_md} and follow it: extracting the problem class, confirming with primary sources, granularity, "no established solution" as a valid conclusion, checking accepted weaknesses again, and dependencies at hand left unused. Labels and viewpoints are defined there.
<!-- if repo_review -->
- The target repository's own source of truth: Read {repo_review_md} as well.
<!-- end repo_review -->

## What to do

Read the dependencies the diff imports first: it is a set you can derive mechanically, so you can start quickly. Do not stop there. What this repository declares as a dependency (not only language packages, but also declared plugins and tools) is where to look for "already at hand but unused", even if nothing imports it (measured: a role that the plugin itself declared as a dependency fell outside the set, and "no reinvention of an established solution" came back for three rounds). Take every primary source you need to confirm a point; you may drop only redundant sources and duplicate secondary sources. Say in `web_refetched` whether you fetched the sources again.

**Go as far as the ranking (`rankings`).** For each generalized problem, write the order that the primary source gives the options (from the top), in `ranked` (`ranked` holds only the option names; the quotation goes in `source`); write in `diff_at` which option the diff is on, spelled exactly as in `ranked`; and if it is not the top one, write in `why_not_higher` why the higher ones cannot be taken. **Do not judge the diff the same as the standard only because the features match** (for example "does not go through a shell, uses an allow list"): degraded variants appear exactly in a form whose features match (measured 2026-09-24: three rounds in a row returned clean as "the same as the OWASP standard", but the diff was not on what OWASP ranks higher, "separate data and command by structure", but on the lower "validate the string"). For a problem with no ranking, `ranked` may hold a single option. If there is no generalized problem that can be ranked, leave `rankings` empty and say why in `rankings_none`.

Return the range you looked at and the range you did not look at (`seen` and `unseen`). If you stopped because of volume or time, write where you stopped: if "looked and found nothing" and "did not look" turn into the same "none", a silent omission is mistaken for "none". The diff is where to start looking, not where to stop. Read dependencies, the neighborhood, and callers as far as you need to understand.

The criteria for a finding (the section "{criteria_section}" of the source of truth): the mechanism (one sentence on the causal chain in the code); a measurement (run what can be run; if you cannot, say "not measured" and give it as a hypothesis); self-refutation before you submit (if you cite a rule, check that its conditions apply, read the actual code around it, and submit only the findings you could not kill); and an estimate of false positives (one line on when the finding would be wrong). Write them in `text`, `mechanism`, `measured`, and `false_positive_if` of each `findings` row.

Do not create, edit, or delete files; use Bash only to read. Where the operating system's sandbox is available, Bash runs inside it and can run the instruments already present (the test suite and instrument scripts). Writing to the working tree, to `.git`, or to other working trees, and talking to the network, are stopped by the operating system; you can write only to the temporary directory that the TMPDIR environment variable names. Commands that download and install (such as `uv run --with` or `pip install`) stop because there is no network: run with the tools already installed. Where the sandbox is not available, only the built-in read-only commands (such as `git log` and `git diff`) and the read-only forms of `works-gh` pass, and running instruments is refused by permissions. For anything refused or stopped so that you could not check it, return it as "not measured", with the command you ran and how it was refused. Do not respell the command to get it through.

{shared:material-status}

## Whether you may write not_applicable

{shared:material-na}

## Where to point

{shared:material-where}

Write `material.detail`, `material.checked`, `material.reason`, the `text`, `mechanism`, `measured`, and `false_positive_if` of each `findings` row, `seen`, `unseen`, the `problem`, `ranked`, `diff_at`, and `why_not_higher` of each `rankings` row, and `rankings_none` in {lang}. Keep `diff_at` spelled exactly as one entry of `ranked`. Keep keys, enum values, identifiers, paths, commands, URLs, and quoted text (including the quotation in `source`) as they are.

Return only JSON that matches the output schema.
```

md の中に `$` の字は無い（今の `$TMPDIR` は「TMPDIR 環境変数が名指す一時ディレクトリ」と言い換えた。materials.md の 3.1 の終わり）。`<!-- if not purpose -->` と `<!-- if purpose -->` は同じ名 `purpose` の 2 つの段落で、入れ子にしない（README の 5.1）。会話と retry は prior-decisions.md の 2.3 の終わりと同じ。

### 2.4 返す形

今の `output_format` のまま（`workflows/judge/works-factory-judge.yaml:1328-1376`）:

- `material`: prior-decisions.md の 2.4 と同じ素材の状態の形。
- `findings`: `[{where, text, mechanism?, measured?, false_positive_if?}]`・各行 `additionalProperties: false`・`required: [where, text]`。
- `seen`・`unseen`: 字。`web_refetched`: boolean。
- `rankings`: `[{problem (4 字以上), source (4 字以上), ranked (1 字以上の字の配列、1 つ以上), diff_at (1 字以上), why_not_higher?}]`・各行 `additionalProperties: false`・`required: [problem, source, ranked, diff_at]`。
- `rankings_none`: 字（任意）。
- 全体 `additionalProperties: false`・`required: [material, findings, seen, unseen, web_refetched, rankings]`。

人に見せる欄は 1.2 の `lang` の説明の欄（判定の材料・報告に載る）で、言語は `{lang}`。`findings` の `where` は名指し、`rankings` の `source` は一次情報の引用と URL なので、字のまま。

### 2.5 描いた骨組み（例の run の値）

例の run では、今の指示は 2 か所に在った: `workflows/judge/commands/material-external-standards.md`（68 行。`$external-standards-prep.output.lang_line`・`.reason`・`.brief_file`・`.review_md`・`.repo_review_md` を Archon が入れた物）と、役が Read した `judge/material-external-standards-brief.md`（55 行）。新しい指示はこの 2 つを 1 本にする。2 回目（1 回拒まれた後）の形:

```markdown
{shared:rejected の本文（土台の断片）。中の {rejection} に:
受け付けがこれまでに拒んだ理由の全部（古い順に 1 件。前の回の拒否も直したままにする）。

1 回目の拒否:
観点 external-standards: rankings[0] の diff_at '3 位（フィールドごとに別 commit で逐次適用）' が ranked に無い——一次情報が推す選択肢のどれに乗るかを、ranked の綴りのまま書け}

{shared:role-investigator の本文: This role is an investigator. It investigates and brings things back; …}

You are the external-standards role. …（決まった文）

Your tools are Read, Grep, Glob, Bash, WebSearch, and WebFetch. …

{shared:works-gh の本文}

{shared:material-readonly の本文}

## Materials

- Target diff (Read it): ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-ac9f-4468-ae72-5f6ed569a667/judge/diff.patch
- Files the target diff touches: [
 "backend/app/api/model/schemas.py",
 "backend/app/api/routers/threads.py",
 …（23 行）
 "frontend/messages/ja.json"
]
- Repository: ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/worktrees/archon/task-works-factory-line-1792307529854
- Original purpose: 会話スレッドにピン留めの印を付けてサイドバーの「ピン留め」と「最近のスレッド」の枠に分ける変更（PR #2109）について、…（目的の文の字のまま）
- Weaknesses already known and accepted: []
- The viewpoint's source of truth: Read the section "外部標準照合観点" of ~/.cache/works-factory-plugin/56032b5a88e2add0e1bda0949986271e1f649ea6/lib/REVIEW.md and follow it: …

## What to do

Read the dependencies the diff imports first: …（決まった文の 5 段落）

{shared:material-status の本文}

## Whether you may write not_applicable

This viewpoint has no condition under which it does not apply, so the acceptance step rejects `not_applicable`. …

## Where to point

Write the `<path>:<line>` of a location (`where`) as a line number in the current file in the working tree. …

Write `material.detail`, `material.checked`, … in the language of the request (the user's language). …

Return only JSON that matches the output schema.
```

例の run の差分のパスは、新しい形では block の place の `diff.patch` になる（判定のまとめから include された時は `…/<judge の include の id>/external-standards/diff.patch`）。拒否の文の頭は、今の `p1.external_standards: ` をこの文書の 4 節の替えで `観点 external-standards: ` にした字。対象の根に `REVIEW.md` が無かったので（今の prep の出力の `repo_review_md` が空）、`repo_review` の段落は入らない。`lang` は空。

### 2.6 今の指示との差

今の指示は `workflows/judge/commands/material-external-standards.md`（68 行）と、`material_prep`（`lib/judge_accept.py:2116-2135`）が描く材料のファイルの 2 か所に在る。prior-decisions.md の 2.6 と同じ移し方（材料の節を `## Materials` の行に・『条件に当たらない』の節を `{shared:material-na}` に・却下の段落 2 か所を `{shared:rejected}` 1 回に・役の定義と外への検索の決まりを `{shared:role-investigator}` と `{shared:query-rule}` に・作業ツリーを変えるなの句を役の定義の Bash の箇条と `{shared:material-readonly}` に・works-gh の段を `{shared:works-gh}` に・素材の書き方を `{shared:material-status}` に・所見の場所の段を `{shared:material-where}` に・言語の 1 行を md の 1 文に・元の指示書との境の文と見出しと区切りを消す・「同じ時に別の素材集めの役も走っている」の断定を消す）はここに繰り返さない。この観点だけの差:

- 移した: 材料の 6 つの節（`loop.diff_file`・`loop.changed_files`・`inputs.review_md`・`out.p0.purpose.purpose_text`・`out.p0.purpose.known_weaknesses`・`inputs.cwd`）と、md:41 の観点の正本の段（prep の出力の `review_md`・`repo_review_md`）を、`## Materials` の行に。md:41 と md:52 で 2 回言っていた観点の正本は 1 行にまとめた（見出しの名指しと、従う中身の並びは md:52 の物）。対象の正本の行は、在る時だけ入れる（今は空でも「空でなければそれも Read せよ」と空のパスを見せた）。
- 移した: 手順 4（md:37。目的の文が無い run では目的を推し量らず、差分と依存から問題の類を引く）と、目的の文の欄に入れていた `PURPOSE_MISSING` の文を、`<!-- if not purpose -->` の 1 行にまとめた。今は「目的の欄に『目的の文はこの run に無い』と書かれていたら…」と、Python が入れた文を md が名指して読ませていた（README の憲法の 2）。
- 移した: 観点の正本の見出しの名「外部標準照合観点」「指摘の提出基準」を差し込み口 `{standards_section}`・`{criteria_section}` に（正本は日本語のままで、英語の md の中に字を持たない）。
- 足した: 指摘の提出基準の 4 つを `findings` の `text`・`mechanism`・`measured`・`false_positive_if` に書けの 1 句。今の返答の形がこの 4 欄を持ち、md が欄の名を言っていなかった（返答の形は変わらない）。足した: `rankings` が空の時は `rankings_none` に訳を書けの 1 句。今の受け付けが拒む決まり（`external_rankings` の 1 つ目の照らし）を、md が言っていなかった。
- 言い換えた: `$TMPDIR`（md:59）を「TMPDIR 環境変数が名指す一時ディレクトリ」に（materials.md の 3.1 の終わり）。
- 消した: md:59 の「GitHub を読む口は上の手順 3 のとおりで…issue と検索は works-gh でも通らないので WebFetch・WebSearch で読め」。`{shared:works-gh}` が同じ事を言う。
- 消した: 素材の書き方の尾（md:60）の「欄と値の正本は受け付けが使う検証器 review-record.py だが…」（prior-decisions.md の 2.6 と同じ）。
- 変えた: 断片 `material-where` の尾の文を、受け付けが照らす範囲（`where` と `text` を持つ行だけ。ほかの行は照らさない）に合わせて狭めた。
- 足した: `rankings` の `ranked`（選択肢の名だけ）と `source`（原文の引用）の書き分け。消した: gh の参照と、works-gh の断片の結びの 1 文。
- 英語にした（#764）。役の名「外部標準照合の役」は "the external-standards role"。

### 2.7 元の works と graphloops の同じ場面

族の形の差は materials.md の 9 節。この観点だけの差:

- 元の works の `works/blk-material/commands/external-standards.md`（8 行）は、graphloops の指示書のファイルを Read させる薄い md で、works-gh の段と手順 4（目的の文が無い run）を持った。手順 4 と `PURPOSE_MISSING` は元の works の `blk-material/lib/material.py:176`・`:320-330`（目的の段の無い盤面を埋める）からで、工場は #76 で写した。この block も持つ（`<!-- if not purpose -->`）。
- 元の graphloops の指示書は、元の works も工場も a1202d0 の写し。graphloops の Bash の段は「gh の読むだけの物（issue・pr の list と view・pr diff・search・repo view）を単独で打てば sandbox の外で通る」と書いた。元の works と工場は、包みが通す形を `works-gh`（pr list・pr view・pr diff・repo view）に絞り、issue と検索を WebFetch・WebSearch に回した（元の works から写した。工場の履歴では #76 の写しと #221 の書き直し）。この block も同じ（`{shared:works-gh}`）。
- 工場が #221 で替えた所: 役の定義の Bash の箇条の「既にある計器の実行」を「リポジトリに既にある検査のスクリプトや試験のうちファイルを書き換えない物の実行」に・「打ち切った線」を「打ち切った境目」に。この block の英語は替えた後の意味で書いた。
- graphloops の今の指示書（`~/src/claude-plugins/graphloops/prompts/review-loop/p1.external_standards.md`）は、a1202d0 の後に語の言い換え（c63c2ae3）と穴の名の替え（`hist.snapshot.*`）だけを受けた。意味の差は無い。
- graphloops の節の宣言（`graphs/review-loop.json` の `p1.external_standards`）は、2 周目から「機構を足した／変えた周」「依存の宣言のファイルが変わった周」に引き直し、体裁だけの周は前の判定を流用する（`refire_when`・`carry_reason`）。工場は 1 run = 1 周（持ち主の決め carry）なので 1 周目の枝だけが効き、流用の語 `carried_over` は拒む。新しい形も同じ。宣言の注記 `na_reason_note`（「外部依存が無いのは『見たが無かった』＝clean」）は指示に入っていない（元の works も工場も同じ。（未確認）: 外した記録は無い）が、`{shared:material-na}` の `never` の段が `not_applicable` を拒み `found`・`clean` で書けと言うので、役に届く決まりは同じ。
- graphloops は `rankings` を盤面の `process.external_rankings` に書く（`writes`）が、graphloops の判定役の指示書もそれを読まない（`prompts/` に名指しが無い）。工場も新しい形も `reply` に残すだけ。
- 受け付けの順（作業ツリー・所見の場所・`post_check` の `external_rankings`・素材の欄）は元の works・graphloops・工場で同じ。

この block が両方より良く、残す物: 順位の行の照らしで「特徴の一致で同型」の clean を止める（graphloops と同じ）・作業ツリーと所見の場所を機械が照らす・目的の文が無い run で目的を作らせない・観点の正本の在る時だけ対象の正本を見せる。

### 2.8 受け付け

materials.md の 4 節の順のまま。観点の前の照らしは無く、後の照らしはこの文書の 4 節の 1 つ。

- 拒む物: JSON のオブジェクトでない返答・役が作業ツリーを変えた（`GUARDED` が偽なので、比べる欄は `porcelain` を含む `TREE_KEYS` の全部）・所見の場所の行がファイルに無い（`findings` の行の `where`。`where` と `text` を両方持つので `where_rows` に当たる）・`rankings` が空で `rankings_none` が空同然・`diff_at` が `ranked` の字に無い・最上位でないのに `why_not_higher` が空同然・素材 `external_standards` が無い・`carried_over`・`not_applicable`（`never`）・知らない status・status ごとの要る欄の欠け。
- 「空同然」は `blank(s, 10)`（10 字未満か、`EMPTY` の語）。今のまま。
- 3 回目の拒否でループを抜ける。`finish` が `status: gave_up`・`reason` に最後の拒否の文・素材 `external_standards` に `not_run` と同じ訳を書く。

### 2.9 試験

- standalone の fixture（`blocks/external-standards/fixtures/`）:
  - `standalone.stubs.yaml`: `fixture.inputs` は `base: ""`・`purpose: '{"purpose_text":"…目的の文…","source":"①PR 説明","known_weaknesses":[],"source_files":[]}'`・`entry: ""`・`lang: ""`。AI の node `external-standards` だけを台本の返答（`material.status: clean`・`checked` 1 行・`findings: []`・`seen`・`unseen` 1 行ずつ・`web_refetched: true`・`rankings` 1 行〔`ranked` 1 つ、`diff_at` が同じ字〕）で差し替える。`finish` の `status` が `ran`。
  - `gave-up.stubs.yaml`: 台本の返答が 3 回とも `diff_at` が `ranked` に無い。`finish` の `status` が `gave_up`、run は `completed`。
  - `skipped.stubs.yaml`: `entry: "人の依頼（standalone）"`。AI の node は走らず、`finish` の `status` が `skipped`、`material.json` の素材 `external_standards` が `not_applicable` で、`reason` が出どころ「人の依頼（standalone）」と「件数は渡されていない」の句を含む。
- `tests/blocks/external_standards/test_external_standards.py`（materials.md の 8 節の block の試験）:
  - 写す元 `lib/tests/test_judge_accept.py::MaterialCase.test_accept_rules` の external-standards の場合（`diff_at` が最上位でなく `why_not_higher` が無い返答を拒み、`material.json` を書かない）。足す: `rankings` が空で `rankings_none` が無い返答を拒む・`diff_at` が `ranked` に無い返答を拒み、文が「ranked に無い」を含む・`rankings` が空でも `rankings_none` に訳が在る `clean` を受ける・拒みの文の頭が `観点 external-standards: `。
  - 写す元 `test_missing_purpose_is_said_not_invented`: `purpose` が null の run で組んだ指示が目的の文の無い 1 文を含み、`Original purpose: ` の後に目的の文を持たず、`prompt_inputs` の値に `purpose_text`・`known_weaknesses` が無い。
  - 写す元 `DueCase.test_empty_diff_run_with_requests_runs_only_prior_decisions` の external-standards の部分: 差分が空で `entry` が在れば `due` が偽で、素材が `materialkit.fill_entry` の字。`entry` が空なら真。
  - 足す: 対象の根に `REVIEW.md` を置いた run と置かない run で、`repo_review` の段落の有無と `repo_review_md` の値の有無が合う。
  - 足す（起こし方の照らし）: AI の node の `model`・`allowed_tools`・`sandbox`・`idle_timeout`・`retry` が、今の `tests/workflows/test_judge.py:93` の external-standards の行（`"sonnet", "medium", INVESTIGATE, CLOSED, False, …`）が照らす物と同じ。
  - 足す（字の照らし）: `STANDARDS_SECTION`・`CRITERIA_SECTION` が `lib/REVIEW.md` の `## ` の見出しの頭に在る（見出しの名を正本が替えたら落ちる）。
- 指示の比べ（README の 11.4）: `tests/blocks/external_standards/test_prompts.py`。
  - 1 つ目の commit: `prompts/external-standards.md` を、今の md の `$external-standards-prep.output.lang_line`・`.reason`・`.brief_file`・`.review_md`・`.repo_review_md` を `{lang_line}`・`{reason}`・`{brief_file}`・`{review_md}`・`{repo_review_md}` に替えた日本語の字で置く。prep は 1 つ目の commit だけこの 5 つを値に入れ（prior-decisions.md の 2.9 と同じ作り方。`review_md`・`repo_review_md` は `materialkit.review_md_paths`）、`src/oldbrief.py` の `brief(view, values)` で `material-external-standards-brief.md` を書く。試験は例の run の値（差分の根・変更ファイルの 23 行・目的の文・`known_weaknesses: []`）で、(a) 組んだ指示が今の md に同じ 5 つの値を入れた字と同じ、(b) `oldbrief.brief` の字が例の run の `judge/material-external-standards-brief.md` と同じ（リポジトリ・差分・`REVIEW.md` のパスは試験の物に置き換えて比べる）。
  - 2 つ目の commit（英語）: 1 つ目の試験と `src/oldbrief.py` を消し、例の run の値で組んだ新しい指示と、今の md と材料のファイルを並べた物を PR に載せ、2.6 の差の一覧どおりかを審査に出す。
- 守る keep-essence の番号: 無い。守るのは「特徴の一致だけで定番と同型と言わせない（順位の行の照らし）」で、上の受け付けの試験が見る。
- 終わりの条件の命令（1 モジュールずつ。materials.md の 8 節と同じ）:

```sh
uv run --isolated python3 -m unittest lib.tests.test_materialkit
uv run --isolated python3 -m unittest discover -s tests/blocks/external_standards -t .
uv run --isolated python3 -m unittest tests.layers.test_block_shape
uv run --isolated python3 -m unittest tests.blocks.external_standards.test_prompts
```

## 3 script の node

materials.md の 6 節の雛形のまま。この block だけの物:

- `intake.py` が読む入力は `INPUTS_BASE`・`INPUTS_PURPOSE`・`INPUTS_ENTRY`・`INPUTS_LANG` の 4 つ。`purpose` は `ports.json(os.environ.get("INPUTS_PURPOSE"), "shared:purpose.schema.json")`、ほかは `ports.text(…)`。値の dict の鍵は `base`・`purpose`・`entry`・`lang`。
- 1 つ目の commit だけ、`role_prep.py` が `src.oldbrief.brief(view, values)` を place の `material-external-standards-brief.md` に書いてから組む。

## 4 受け付けの文（観点の後の照らし `src/rankings.py`）

今の `external_rankings` の字のまま。頭の `"{nid}: "`（`p1.external_standards: `）は `"観点 external-standards: "` に替え、照らしの文を `; ` でつなぐ（materials.md の 2.8 の「ノード {nid}」→「観点 {name}」と同じ替え）:

- `rankings が空なのに rankings_none（順位を付けられる一般化した問題が無い理由）が無い——空の順位で clean を名乗らせない`
- `rankings[<i>] の diff_at '<diff_at の頭 40 字>' が ranked に無い——一次情報が推す選択肢のどれに乗るかを、ranked の綴りのまま書け`
- `rankings[<i>]: 差分は最上位（<ranked[0] の頭 40 字>）でなく '<diff_at の頭 40 字>' に乗るのに、上位を採れない理由（why_not_higher）が無い`

## 5 単独で呼ぶ

```sh
bin/works-factory <読ませるフォルダを blocks/ にする引数（名は土台の PR で決める）> workflow run works-factory-external-standards \
  --input purpose=/path/to/purpose.json --input base=<差分の根の commit>
```

作業ツリーは Archon の cwd（対象のリポジトリ）。`purpose` を省くと目的の文の無い run として照合する。`entry` を空でなくすると役を起こさず `status: skipped` で返る。

## 6 未確認

- 土台の `prompt.render` が `<!-- if purpose -->` と `<!-- if not purpose -->` を同じ md に並べて書けるか（README の 5.1 は逆の条件の書き方を決めているが、同じ名を 2 回使う例は無い）。書けなければ `not purpose` の段落を名 `no_purpose` にし、`when` に `"no_purpose": values["purpose"] is None` を足す。
- 土台の `prompt.render` が、差し込んだ値（目的の文・自覚済みの弱点）の中の `{…}` と `$…` を置き換え直さないか（[purpose-review.md](purpose-review.md) の 6 節と同じ）。
- 起動の殻で `blocks/` を読ませる引数の名と、5 節の命令の正確な形。

## 7 自分で決めた事（この block だけ）

- 観点の正本の見出しの名を md に字で書かず、`src/viewpoint.py` の定数から差し込む。訳: 正本（`lib/REVIEW.md`）は日本語で、見出しの字は正本と md が合うべき値（README の 5.3）。英語の md に日本語の字を置かずに済み、正本が見出しを替えた時に試験が名指して落ちる。
- 対象の正本（`repo_review_md`）の行を、在る時だけ入れる。訳: 今は空のパスを見せて「空でなければ」と役に判じさせていた。在るかは機械の事実で、段落の真偽で渡せる（README の 5.3 の「段落を差し込むかの真偽」）。役に届く中身は、在る時は今と同じ、無い時は読む物が無いので同じ。
- 目的の文が無い run の文を、目的の欄の値（`PURPOSE_MISSING`）でなく md の段落にする。訳: 今の文は Python の定数で、md の手順 4 がその字を名指して読ませていた。憲法の 2（Python は指示の文を持たない）。
- 指摘の提出基準の 4 つを `findings` の 4 欄に書けと md に足す。訳: 返答の形がこの欄を持ち、判定役の材料（`external_findings`）に載るのに、今の md は欄の名を言っていない。返答の形と受け付けは変わらない。同じく `rankings_none` の 1 句は、今の受け付けが拒む決まりを先に言うだけ。
- 拒みの文の頭を `観点 external-standards: ` にする。訳: [purpose-review.md](purpose-review.md) の 7 節と同じ（graph の節の id は新しい形に無い）。
- `purpose` の schema を purpose-review と同じ字で置く。訳: materials.md の 1.2 の「同じ意味の入力は同じ名と同じ形」。中身は purpose-review.md の 1.5 で決めた。
- 回す時の `due` の訳を、今の `external_standards_due` の字でなく「外部標準の照合は、判定から入る run でなければ run ごとに 1 回回す（1 run は 1 周で、いつも初回）」にする。訳: 1 run = 1 周（持ち主の決め carry）で、前の周の P3 と機構を変えた周の枝はいつも効かない。効かない枝の名を人に見せる `reason` に残すと、読む人が「前の周」が在ると取り違える。prior-decisions.md の 1.5 と、ほかの P1 の観点（test-double-fidelity・main-path-observation など）と同じ決め方。回すかの真偽は今と同じ。
- 実装時に決めた事（#765 の実装）:
  - `fill` は `materialkit.fill_entry(values["entry"], None)`。訳: 1.5 は `0` を渡すと書くが、`fill_entry` は `0` を「依頼 0 件」と書き、`None` が「件数は渡されていない」の句になる（materials.md の 2.6）。この観点は port `request` を持たないので `None` が書いた意図に合う。
  - `purpose` の形 `purpose.schema.json` は `blocks/.shared/schemas/` に 1 つ置く（`shared:purpose.schema.json`）。訳: 1.2 は block ごとの写しを書くが、`tests/layers/test_block_shape.py` の入力の形の検査が「形のファイルの名は pack の中で 1 か所。2 つ以上の block が使う形は `.shared/schemas/`」と決める。`$schema` の鍵は `KNOWN_KEYWORDS` に無いので外した。
  - 役の md の頭の文から「started in a new conversation」を外した（`You are the external-standards role. Your only job …`）。訳: 輪は `fresh_context: false` で、2 回目からは同じ会話を続けるので、「新しい会話」と言うと誤る。standalone の筋書きの決まった文もこの頭の文に合わせた。
  - `NA_PARAGRAPH = True` を宣言に足した（共通の試験が要る名。1.5 は書いていない）。
  - 1 つ目の commit の材料のファイル `src/oldbrief.py` は、本物の run の物が手元に無いので、今の `judge_accept.material_prep` の字（見出し・節の名・『条件に当たらない』の段）を `lib/judge_accept.py` の定数から組み直して書いた。本物の run の物との字の比べ（2.9 の (b)）はしていない。2 つ目の commit で消した。
  - 試験は 2.9 のとおり。起こし方の照らしは `tests/workflows/test_judge.py` の行を `ShapeCase.LAUNCH` に字で写した。
  - `values` は目的の値と `repo_review_md` を、段落が入らない時は空の字で渡す。訳: 1.5 は「在る時だけ」と書くが、`blocks/.shared/AGENTS.md` の決め（指示を組む口は選ばれない段落の中の `{name}` も数える。prep はいつも同じ組の値を渡す）が勝つ。
