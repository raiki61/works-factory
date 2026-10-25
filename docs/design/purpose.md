# block の設計書: purpose（目的の固定）

- 何の話か: run の「元の目的」を AI の役に 1 つの文にさせ、依頼が示した解き方（手段）を目的から分けて返す観点を、単独で呼べる block `workflows/purpose/` にする設計。型は [README.md](README.md) に、形は手本の [world.md](world.md) に従う。
- 決めたこと: 今の judge の 4 つの node（purpose-prep・purpose-reject・purpose・purpose-accept）を、6 つの node の block にする。入力は依頼・PR の説明の文・前提の実測・言語の 4 つの port だけで、始めの記録と止めの記録を読まない。指示は英語の md 1 本（`prompts/purpose.md`）にまとめ、材料のファイル `purpose-brief.md` を Read させる形をやめて、材料を指示の中に入れる。前の run の判断（依頼の `prior_failures`）を機械で外すこと、目的は 1 度固めたら変えないこと（once）、出典のファイルの照らしは今のまま残す。出力は目的の文・出典の語・解き方の並びを欄で返し、目的の控え全体を pointer で返す。振る舞いは変えない。
- 持ち主に求めること: なし。読み手は、この block を作る実装の役（この文書だけで作れる細かさにした）と、その PR の審査。

この文書の語は README の頭の物を使う。ほかに:

- 持ち主: このリポジトリの owner（決めを下す人）。「持ち主の決め `<名>`」は `docs/owner-decisions.md` の決めの名。
- line: 工場（works-factory。この repo の Archon の workflow 群）のメイングラフ。始めの記録（run の起動の時の入力の記録）を書き、block に port の値を配る。judge のまとめ（`workflows/judge/`）は判定の block を `include:` で並べる graph で、line がそれを include する。
- 土台の PR: README の 11.1 の 0 の PR（`workflows/.shared/ports.py`・`prompt.py`・共通の指示の断片 `rejected.md`・`query-rule.md`・起動の殻の口を置く）。この block の PR より先に入る。この文書が「土台に合わせる」と書く名は、そこで決まる。
- 源と bun: 試験が Archon を起こすのに要る、止めた版の Archon のソース（`bin/_lib/place.archon_source` が取る）と JavaScript の実行環境 bun。無い手元では、その試験を名前つきで見送る（`tests/AGENTS.md`）。
- keep-essence: 元の works が守る 12 の仕組み（README の 10 節）。9 は「独立設計と R1〜R4」で、R1〜R4 は修正の後に別の目が見る 4 つの確かめ（R1 最小性・R2 独立設計との比べ・R3 全体の整合・R4 見えていない範囲）。12 は「世界の解に照らす」。
- 1 つ目の commit・2 つ目の commit: この block の PR の中の 2 つの commit（README の 11.4）。1 つ目は指示の md を日本語のまま置いて今の指示と同じ字かを試験で照らし、2 つ目で英語にする。2.3 の md の本文は 2 つ目の物。
- 目的の役（purpose）: 依頼・PR の説明・計画の文書から、この run の元の目的を 1 文にし、出典の語と出典のファイルと自覚済みの弱点を返す AI の役。依頼の解き方は `means` に分けて並べる。道具は Read・Grep・Glob・WebSearch・WebFetch で、読むだけ。
- 出典の語: `①PR 説明`・`②計画・タスク記述`・`③writer の要約`・`目的不明` の 4 語（今の `output_format` の `source` の enum）。
- 解き方（means）: 依頼が示した手段の文の並び。目的の文から外して別に返す。世界の解の観点が定石と比べる（keep-essence の 12）。
- 目的の控え: place の `purpose.json`（`{purpose_text, source, known_weaknesses, source_files}`）と `purpose-means.json`（`{means: [...]}`）。名と形は今の `judge/` の物と同じ。
- 前の run の判断: 依頼の容器の `prior_failures` の欄（前の run で最後まで通らなかった物）。目的の役には見せない（持ち主の決め `premises-purpose` の当て方「目的の役に前の run の判断を見せないことを機械で縛る」）。
- 例の run: 本物の run `df5e111f-ea97-409b-8066-2245d32746ab`（対象 raiki61/works-factory。置き場 `~/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/artifacts/runs/df5e111f-…/judge/`）。`purpose-brief.md`・`purpose-request.json`・`purpose.json`・`purpose-means.json` から骨組みの値を取った。この run は 1 回目で通り、拒みの控え `rejects-purpose.json` は無い。

## 1 block の全体

### 1.1 役

この run の元の目的を、依頼・PR の説明・計画の文書のどれから取ったかを名指して 1 文にする。依頼が示した解き方は目的の文に混ぜず、別の欄に分ける（目的だけから設計する独立の目と、定石と比べる世界の解が、依頼の解き方の枠に揃わないため）。目的の出典にしたファイルを、作業ツリーの根からの相対の正規形で返させ、機械が版に在るかを照らす。役が作業ツリーを変えていないかを写しと比べる。目的は 1 度固めたら、同じ place では書き直さない。

### 1.2 port

入力（YAML の `inputs:`）:

- `request`（必須）: `json(request.schema.json): 依頼の行の配列 [{where, text, mechanism?, measured?, false_positive_if?}]。それを findings の欄に持つオブジェクトでもよい（工場の依頼のファイルの形。prior_failures の欄は役に見せない）。空の配列は依頼の行の無い run`
- `pr_text`: `text: PR の番号・題・本文を並べた文。空は PR の無い run`。既定 `""`。
- `constraints`: `json(constraints.schema.json): 前提の実測の行の配列か、それを constraints の欄に持つオブジェクト（前提の実測の block の出力の pointer の先の形）。空の配列は実測が無い`。既定 `[]`。
- `lang`: `text: 人に見せる欄（purpose_text・known_weaknesses・means）の言語。空は依頼の行の言語`。既定 `""`。

出力（`returns: finish`、`outcome_field: ok`）:

- `ok`: boolean。`status` が `ok` か。
- `status`: `ok` か `failed`。`ok` は、受けた目的か、place に既に固めた目的が在る時。`failed` は、port が読めない・作業ツリーの写しが取れない・役が 3 回拒まれた・役が走らなかった時。
- `reason`: 日本語の 1 行（人に見せる）。`failed` の訳。固めた目的を使った時は「目的は既に固めてある（purpose.json）」。ほかは空の字。
- `purpose`: pointer（place の `purpose.json`）か null（`failed` の時）。
- `purpose_text`: 目的の文（`failed` の時は空の字）。
- `source`: 出典の語（`failed` の時は空の字）。
- `means`: 依頼の解き方の文の配列（無ければ `[]`）。
- `report`: 報告の行の配列。`ok` の時は `[]`（今の報告に目的の節は無い。目的のファイルの在り処の行は report の block が pointer から組む）。`failed` の時は `目的の文: <reason>` の 1 行。

今との違い: 今は支度が始めの記録の依頼のファイルと PR（`lib/judge_accept.py:1258-1284` の `purpose_prep`）と `judge/premises.json` を読み、止めの記録 `judge/stop.json` を見て役を起こすかを決め（`workflows/judge/scripts/purpose_prep.py:19-24`）、受け付けは `judge/purpose.json`・`judge/purpose-means.json` に書き、諦めた時は止めの記録（`stopby.PURPOSE`）を置いた。出口は judge の返す節の欄 `purpose`・`purpose_means`（pointer）だった。この block は、PR の説明を文の port で、前提の実測を json の port で受け、止めの記録の代わりに `status` を返す。`purpose_text`・`source`・`means` を欄でも返すのは、読み手が 3 つ以上の欄を読まない時に pointer を開かずに済むため（世界の解の block は `purpose_text` と `means` を欄で受ける。world.md の 1.6）。

### 1.3 node の並び（`workflows/purpose/works-factory-purpose.yaml`）

1. `intake`（script `intake.py`。`mutates_checkout: false`）: place に固めた目的が在れば port を読まずに役を起こさない。無ければ port を読み、この block が名を持つファイルを消して、材料を `intake.json` に、作業ツリーの写しを `tree.json` に書く。返り `{due, reason}`。
2. `purpose-loop`（`loop_group`、`max_iterations: 3`、`fresh_context: false`、`until_bash: done=$purpose-accept.output.done; test "$done" = true`。`depends_on: [intake]`・`when: $intake.output.due == true`）
   - `purpose-prep`（script `purpose_prep.py`。`mutates_checkout: false`。`with:` は持たない）: 指示を組む。前の回までの却下は place の却下の控えから読む。返り `{prompt}`。
   - `purpose`（AI。`depends_on: [purpose-prep]`・`prompt: "$purpose-prep.output.prompt"`・`model: '@wf-judge-materials'`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob, WebSearch, WebFetch]`・`mutates_checkout: false`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`idle_timeout: 1728000000`・`retry: {max_attempts: 2, on_error: all}`。`output_format` は今のまま。2.4）
   - `purpose-accept`（script `purpose_accept.py`。`depends_on: [purpose]`・`mutates_checkout: false`・`with: {reply: $purpose.output}`）: 返り `{ok, done, reason}`。
3. `finish`（script `finish.py`。`depends_on: [intake, purpose-loop]`・`trigger_rule: all_done`・`mutates_checkout: false`）: 出力を返す。どの段が落ちても落ちない。

どの script の node も `runtime: uv`。今の `purpose-reject`（`reject.py`）は無くす。今の受け付けの node の `with: {status_guarded: true}`（`workflows/judge/works-factory-judge.yaml:690`）は、受け付けが比べる欄を `accept.BEYOND_STATUS` にする印だった。この block では `src/steps.py` の定数（`TREE_KEYS = accept.status_keys(True)`）にして `with:` から外す（この役の node は `mutates_checkout: false` で、Archon が node の前後の `git status` を照らすので、`porcelain` の欄は比べから外す。今と同じ）。

script の名は `lib/` のモジュールの名と重ねない（README の 7.1 の 9）。`purpose.py`・`accept.py` は lib と重なるので使わない。`purpose_prep.py`・`purpose_accept.py` は重ならない。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、line から judge のまとめを通して include された時は `$ARTIFACTS_DIR/judge/purpose-run/`）の下に書く。名は `src/steps.py` だけが持つ。

- `intake.json`: `{request, pr_text, constraints, lang, frozen, failed, reason}`。`request` は役に見せる依頼の写し（`prior_failures` を外した物）。
- `tree.json`: 作業ツリーの写し（`accept.tree_state` の形）。今の `judge/purpose-tree.json` に当たる。
- `purpose-prompt-<n>.md`: 組んだ指示。
- `rejects-purpose.json`: 拒みの控え（今と同じ名）。
- `purpose.json`・`purpose-means.json`: 目的の控え（今と同じ名・同じ形）。

今の `judge/purpose-brief.md`（材料）と `judge/purpose-request.json`（依頼の写し）は書かない。材料は指示の中に入り、依頼の写しは `intake.json` の `request` に在る。

### 1.5 コードの置き場

- `workflows/purpose/src/__init__.py`: 空。
- `workflows/purpose/src/steps.py`: 今の `lib/judge_accept.py` の `refuse_if_frozen`（:1224-1230）・`check_purpose`（:1233-1255）・`PURPOSE_RULE`（:1218）と、作業ツリーの比べ `_tree_snapshot`・`_moved_since`・`_tree_unchanged`（:1121-1160。写しの在る道だけ）の写し。`purpose_prep`（:1258-1284）は、材料の文を組む部分を md へ出し、依頼の写しの作り方（`carry.without_prior`）だけを `request_copy(doc)` として写す。place のファイルの名（`INTAKE_FILE`・`TREE_FILE = "tree.json"`・`PURPOSE_FILE = "purpose.json"`・`MEANS_FILE = "purpose-means.json"`・`ROLE = "purpose"`）と、出典の語 `PR_SOURCE = "①PR 説明"`・`PLAN_SOURCE = "②計画・タスク記述"`・`WRITER_SOURCE = "③writer の要約"`・`UNKNOWN_SOURCE = "目的不明"`、制約の `kind` の語 `MEASURED = "実測"`・`HYPOTHESIS = "仮説"` もここだけが持つ。解き方の分け（今の `worldmark.split_means`。`lib/worldmark.py:161-166`）は `split_means(reply)` として写す: 返答の写しから鍵 `means` を外し、`means` の中の空白だけでない字だけを並べる（今の `split_means` が頼る `lib/marks.py` は、README の 9.1 で消すと決まった部品なので使わない）。
- `workflows/purpose/src/sourcefiles.py`: 今の `lib/purpose.py:24-46` の `_source_files_errors` と、それが頼る `lib/judge_accept.py` の `_resolve_target`（:2250-2260）・`_in_version`（:2236-2247）の写し。根は `engine.util.repo_root(engine.util.git)`、git の向き先は `accept.in_repo(repo)`。拒みの訳の字は今のまま。
- block の `schemas/` は置かない。依頼の形は共通の `workflows/.shared/schemas/request.schema.json`（依頼の容器の照らしは土台の口 `requestrows.parts`）、前提の実測の形は共通の `workflows/.shared/schemas/constraints.schema.json`（行の欄は今の前提の役の `output_format` と同じで、行は `additionalProperties: false`、`measured_output` は空白だけでない字。容器の外側は閉じない。`実測` の行の `measured_output` の欠けは拒まない: 役の返りには在り、前の run から持ち越した行〔`lib/carry.py` の `carried_constraints`〕には無い）。
- 使う `lib/`: `accept`（KEEP。`tree_state`・`tree_moved`・`type_errors`・`TREE_SCHEMA`・`status_keys`・`guard`・`in_repo`）・`carry`（KEEP。`without_prior`）・`rolekit`（KEEP。`accept_round`・`rejected`・`rejects_text`・`given_up_reason`）・`graphloops/engine/util.py`（KEEP。`Reject`・`git`・`repo_root`）・`jsonfile`・`oneline`。

### 1.6 つなぎ方（graph の側。block には書かない）

- judge のまとめ（`workflows/judge/`）: `include: works-factory-purpose`。`depends_on: [premises]`・`when: $premises.output.ok == true`（今は前提の段が諦めると止めの記録で目的の役を起こさなかった。`workflows/judge/scripts/purpose_prep.py:19-21`）。`with:` は `request: $<依頼の pointer>`・`pr_text: <始めの記録の input.pr から line が組んだ文。PR の無い run は空>`・`constraints: $premises.output.constraints`・`lang: <始めの記録の lang>`。PR の文の組み方（今の `lib/judge_accept.py:1074-1081` の `pr_file_text`。番号・題・本文の見出し）は line の物。
- `status` が `failed` の時: 今は judge の返りが `stop_reason: works:purpose` になった（`lib/judge_accept.py:3920`）。graph は `$purpose.output.ok == true` を世界の解・素材・diagnose の `when:` に置き、judge のまとめの返りの止めの語に `works:purpose` を入れる。
- 読み手:
  - world: `purpose: $purpose.output.purpose_text`・`means: $purpose.output.means`（world.md の 1.6）。
  - independent-design（独立の目 R2 の設計）: `purpose: $purpose.output.purpose_text`（keep-essence の 9。目的だけを受ける）。
  - diagnose・plan・素材の観点（purpose-review ほか）・r2: `$purpose.output.purpose`（pointer）。目的の監査（purpose-review）を回すかは、line が `$purpose.output.source` が `③writer の要約` かで決める（今の `lib/judge_accept.py:1597-1602` の `purpose_review_due`）。
  - report: 目的のファイルの在り処の行（今の `lib/runreport.py:181` の `POINTERS` の「目的」）と、`$purpose.output.report`。
- 「目的は最初の修正の前に 1 度だけ固める」は、judge のまとめがこの block を 1 回だけ include し、再審の道（diagnose の `objection`）がこの block を通らないことで続く（今と同じ。world.md の 1.6 の「run で 1 回」と同じ形）。

## 2 node の設計シート: purpose（目的の役）

### 2.1 役

この run の元の目的を 1 つの文にし、出典の語・出典のファイル・自覚済みの弱点を返す。依頼の解き方は `means` に分ける。読むだけ。

### 2.2 port

`intake.json` の `request`（← port `request` から `prior_failures` を外した写し）・`pr_text`（← port `pr_text`）・`constraints`（← port `constraints` の行）、前の回までの拒みの理由の全部（← place の却下の控え `rejects-purpose.json`。`rolekit.rejected`）、`lang`（← port `lang`）。リポジトリは run の作業ツリー（Archon の cwd）で、役が計画の文書を探して読む。

### 2.3 組み立ての順（`prompts/purpose.md`）

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: 却下の控えに拒否が在る。断片の中の `{rejection}` ← 前の回までの拒みの理由の全部（`rolekit.rejects_text`。古い順）。
2. `{shared:query-rule}`（外への検索の決まり）。断片の中の `<!-- if spawns -->` には `spawns: false` を渡す。
3. 役の定義（決まった文）。
4. 目的と解き方を分ける決まり（決まった文、太字の頭）。
5. 読むだけの決まり（決まった文）。
6. `## What holds for this sentence`（決まった文）: 目的の文は後で依頼なしに読まれる決まった入力になる・事前登録（once）。この役の出力の性質だけを書き、後の役の振る舞いは書かない。
7. `## Input`（決まった文）: 対象のリポジトリ・材料の 3 節の頭の 1 文。
8. `### Request`（決まった文の説明）と ```` ```json ```` の囲みと `{request}`（← `intake.json` の `request` を `json.dumps(…, ensure_ascii=False, indent=1)` にした字）。差し込み口 `{plan_source}`・`{writer_source}`。
9. `### PR description`（決まった文の説明）と `<!-- if not pr -->`（PR の無い run の 1 文）`<!-- end pr -->` と `{pr_text}`（← port `pr_text`。空でもよい）— 条件 `pr`: `pr_text` が空白だけでない。差し込み口 `{pr_source}`。
10. `### Measured premises`（決まった文の説明）と ```` ```json ```` の囲みと `{constraints}`（← `intake.json` の `constraints` を `json.dumps(…, ensure_ascii=False, indent=1)` にした字。空なら `[]`）。差し込み口 `{measured}`・`{hypothesis}`。
11. `## Steps`（決まった文）: 手順 1〜5。差し込み口 `{pr_source}`・`{plan_source}`・`{writer_source}`・`{unknown_source}`。
12. `## Output`（決まった文）: 欄の並び・対象の名前が要るので引かなかった調べの書き方・言語の 1 文。差し込み口 `{pr_source}`・`{plan_source}`・`{writer_source}`・`{unknown_source}`・`{lang}`。

md の本文の正本は `workflows/purpose/prompts/purpose.md`（設計書は本文を写さない。`workflows/AGENTS.md` の変更の種類ごとに閉じる所）。

`{"findings": [...], …}` は差し込み口の形に合わないので字として残る。`"{unknown_source}: "` は差し込み口で、出典の語が入る。

### 2.4 返す形

今の `output_format` のまま（`workflows/judge/works-factory-judge.yaml:667-684`）:

```yaml
type: object
required: [purpose_text, source, known_weaknesses, source_files]
additionalProperties: false
properties:
  purpose_text: {type: string, minLength: 1, pattern: '\S'}
  source: {type: string, enum: [①PR 説明, ②計画・タスク記述, ③writer の要約, 目的不明]}
  known_weaknesses: {type: array, items: {type: string}}
  source_files: {type: array, items: {type: string}}
  means: {type: array, items: {type: string, minLength: 1, pattern: '\S'}}
```

`source` の enum は `src/steps.py` の `(PR_SOURCE, PLAN_SOURCE, WRITER_SOURCE, UNKNOWN_SOURCE)` と同じ並び（試験が結ぶ。7.2）。人に見せる欄は `purpose_text`・`known_weaknesses`・`means`（承認ノード・報告・ほかの役の材料に載る）で、言語は `{lang}`。`source_files` はパスなので訳さない。

### 2.5 描いた骨組み（例の run の値）

```markdown
{shared:query-rule の本文: Rules for queries to outside services …（spawns の段落は入らない）}

You are the purpose role. …

**Separate the purpose from the means.** …

You **only read**. …

## What holds for this sentence

- …（2 行）

## Input

- The target repository is the current working directory. …
- The material is the three sections below, …

### Request

A copy of the request file: … set `source` to `②計画・タスク記述` if the findings lines describe a plan or a task …

```json
{
 "findings": [
  {
   "where": "workflows/merge/scripts/pr_commit.py の hook_env（73 行あたり）",
   "text": "出口の語 deliver=pr の run で PR 用の commit を積む時、…（約 380 字）"
  }
 ]
}
```

### PR description

The PR's number, title, and body (a run without a PR says so). This is the source `①PR 説明` of step 1.

(This run has no PR.)

### Measured premises

Each row of `constraints` has … (`実測` or `仮説`) …

```json
[
 {
  "text": "workflows/merge/scripts/pr_commit.py の hook_env（73 行あたり）: 依頼どおり、hook_env は dict(os.environ) に …",
  "measured_how": "grep -n と sed で pr_commit.py を確認",
  "kind": "実測",
  "measured_output": "$ sed -n 73,76p workflows/merge/scripts/pr_commit.py\n…"
 },
 …（制約 4 行）
]
```

## Steps

1. **Look for sources in this order of priority** …
   - `①PR 説明`: …
   - `②計画・タスク記述`: …
   - `③writer の要約`: …
   - `目的不明`: … write "目的不明: " followed by …
…

## Output

… Write `purpose_text`, `known_weaknesses`, and `means` in the language of the request lines. …
```

例の run の値: 依頼のファイルが容器の形（`{"findings": [...]}`）で、`prior_failures` の欄は持たなかった（`purpose-request.json` は容器の写しのまま）。PR の無い run。前提の実測は 4 行（`premises.json` と同じ）。役は `source: ②計画・タスク記述`・`source_files: []` と解き方 2 文を返し、1 回目で通った（`purpose.json`・`purpose-means.json`）。却下の段落は入らない。

### 2.6 今の指示との差

今の指示は `workflows/judge/commands/purpose.md`（61 行）と、役に Read させる材料のファイル `purpose-brief.md`（`lib/judge_accept.py:1258-1284` の `purpose_prep` が組む）の 2 か所に在る。

- 移した: 材料のファイルを Read させる行（md:38「材料: `$purpose-prep.output.brief_file`（**まず Read せよ**）。機械が組んだ物で、次の 3 つが在る:」）をやめ、材料の 3 つを `## Input` の下の 3 つの節にした。材料の題「# 目的の役の材料（機械が組んだ物。前の run の判断は外してある）」（`lib/judge_accept.py:1276`）は `## Input` の 1 文に、材料の見出し「## 依頼（<パス>）」「## PR の説明」「## 前提の実測（premises.json の constraints）」（:1277-1281）は md の節の見出しにした（パスとファイルの名は外した。中身が指示の中に在るので要らない）。md:39-41 の材料ごとの説明は、それぞれの節の頭に移した。lib の Python に残るのは JSON の字にする所だけ。
- 替えた: 前提の実測が無い時の字「（前提の実測は無い）」（`lib/judge_accept.py:1282`）を、空の配列 `[]` と、節の説明の 1 文「An empty array means there are no measured premises.」にした。PR の無い時の字「（PR の無い run）」（:1280）は、差し込むかを選ぶ段落にした。
- まとめた: md に字で書いていた出典の 4 語（md:39・48-51・61）と `kind` の 2 語（md:41）を、差し込み口 `{pr_source}` などと `{measured}`・`{hypothesis}` にした。
- 移した: 外への検索の決まりの塊（md:3-10）を共通の断片 `{shared:query-rule}` に（world.md の 3.6 と同じ）。
- 消した: 頭の拒みの節（md:14-20）と区切り（md:12・22）と、`## 入力` の拒みの行（md:43）。共通の断片 `{shared:rejected}` の 1 回にした。
- 移した: 言語の 1 行（md:1。`$purpose-reject.output.lang_line`）を `## Output` の最後の 1 文に。この node の人に見せる欄（`purpose_text`・`known_weaknesses`・`means`）を名指した。
- 消した: 役の定義の 2 文目「graphloops の P0 ＞ 4「元の目的」をテキスト化（`p0.purpose`）と同じ仕事」（md:24）。写しの元の名で、役のする事を言わない（world.md の 3.6 の「works の包みより」を消したのと同じ）。
- 替えた: 節「この文が何に使われるか」（md:30-34）を「この文に成り立つ事」（`## What holds for this sentence`）にし、「ゼロベースの再導出（R2）に渡す唯一の入力」（md:32）と「判定役にも渡る（split・fork・resolved を決めるのに要る。…）」（md:33）を、「目的の文は後で依頼なしに読まれる決まった入力になる。目的だけで、何に達するか・いつ済むかが言えるように書く」の 1 行にした。手順 3 の「出典を後の周の修正が書き換えた周には目的の審査だけを走り直す」「列挙が無いと『狭めている』の判定が残り全周を縛る（実測 2026-09-13 …）」（md:53）は、「書いた名は run の全周で目的と一緒に固まり、後の周は修正が変えたファイルの名と字のまま比べる。列挙から漏れた出典は当たらず、後の変更に気づかれない」にした（後の役の振る舞いでなく、この役の出力の性質だけを書く。#772 の審査）。「R2 は unverifiable になる」（md:51）を「目的から作る設計を確かめられない」にした。この block はほかの block の名と、その返答の語（split・fork・resolved・unverifiable）を書かない（憲法の 3）。言っている事（唯一の入力なので混ぜ物を入れない・判定にも要る）は同じ。graphloops で渡し忘れた話は、この役のする事に関わらないので消した。
- 消した: ほかの node の id（`$purpose-reject.output.*`・`$purpose-prep.output.brief_file`）。
- 足した: `measured_output` を「when present」（在る時だけ）とした。
- 変えた: 調べを引いていない時の添え書きが決まった英語の字になり、{lang} で書く欄に混ざる。
- 消した: Agent で子を起こす文（この役は子を起こさない）。
- 2 つ目の commit で英語にした（#764）。役の名「目的の役」は "the purpose role"。

### 2.7 元の works と graphloops の同じ場面

元の works の `works/blk-purpose/`（入力 `request`〔依頼のファイルのパス〕・`constraints_file`・`base_rev`・`pr_file`、出口 `ok`・`purpose_file`・`purpose_text`・`source` の独立したブロック）から、工場は判定のブロックの中に写した（#76。`消した計画（git の履歴。ab47a4d の版で読める）docs/plans/2026-10-12-blocks/judge.md:31`・`:111`）。graphloops の同じ場面は `prompts/review-loop/p0.purpose.md`（`p0.purpose`。once の節）。

- 独立したブロックの形と、出口の `purpose_text`・`source`: 工場は judge の返す節の pointer `purpose` だけにした（#76）。この block は元の形（入力だけで動き、文と出典の語を欄で返す）に戻し、`means` も欄で返す。
- 入力の前提の実測を写しの型と post_check（`measured_needs_output`）に通す（元の intake の `check_constraints`）: 工場には無い。計画（`消した計画（git の履歴。ab47a4d の版で読める）docs/plans/2026-10-12-blocks/judge.md:111`）は「中身は (b) で `lib/judge_accept.py` へ」と書いたが、今の `lib/judge_accept.py` に無く、`git log -S "def check_constraints"` も工場の履歴に当たらない（#76 で写さなかった。意図の記録は（未確認））。元の judge は前提の役の受け付けの後に持ち越しの行を足し（`lib/judge_accept.py` の `with_carried`〔:1187-1192〕）、目的の役へ確かめずに貼った（:1274-1281）。持ち越しの行は `measured_output` を持たないので、この block も `実測` の行の欠けを拒まず、`constraints.schema.json` の形（知らない欄・空白だけの `measured_output`）だけを確かめる。役自身の返りの `measured_output` は前提の block が見る（[premises.md](premises.md) の 8 節の 3）。
- 入力 `base_rev`（写しが無い時の HEAD の照らし）: 工場は写しを必ず取るので受けない（[premises.md](premises.md) の 2.7 と同じ。意図の記録は（未確認））。この block も写しを `intake` で必ず取る。
- 依頼の `prior_failures` を外した写しを役に渡す（元の intake）: 工場も同じ（`carry.without_prior`。持ち主の決め `premises-purpose`）。この block も残す。
- 目的の監査（`p0.purpose_review`）をブロックに入れない（元の YAML の頭の注）: 工場も入れていない。この block も入れない（素材の観点 purpose-review の block と line の物）。
- graphloops の `p0.purpose` に無く工場が持つ物（元の works から）: 解き方を `means` に分ける（世界の解の入力。keep-essence の 12）・出典のファイルの正規形と版の照らし・作業ツリーの写しとの比べ・`目的不明` の時の書き方・対象の名前が要る調べの名指し。この block は全部残す。
- graphloops の `p0.purpose` が持ち、工場が別の形で持つ物: 「別の context の inspector が狭めていないかを見る」（`③writer の要約` の時の監査）は、素材の観点 purpose-review の block が持つ（line が `source` で回すかを決める。1.6）。

### 2.8 受け付け

- 却下の決まり（`src/steps.py` の `check(reply, place, repo)`。今の `lib/judge_accept.py:1233-1255` の写しで、照らす順と訳の字も今のまま）:
  1. place に `purpose.json` が既に在る → 「置き場に目的の文 purpose.json が既に在る（<パス>）——目的は最初の修正の前に 1 度だけ固め、以降は変えない（graph の p0.purpose の once）」（今の `refuse_if_frozen`）。
  2. 作業ツリーが写し `tree.json` から変わった（比べる欄は `accept.status_keys(True)` ＝ `accept.BEYOND_STATUS`。`porcelain` を除く `diff_sha256`・`ignored`・`head`・`ref`。今の `status_guarded: true` と同じ）→ 「役を起こした後から作業ツリーが変わった——目的の役は読むだけの役で、作業ツリー・HEAD・枝・git が無視するファイルを変えてはいけない（…）。作った物（出力のファイル・キャッシュ）は rm で消し、…出し直せ（出力は $TMPDIR に置く）（<変わった所>）」。写しが無い・読めない時も拒む。
  3. `source_files` に、作業ツリーの根からの相対の正規形で版に在るファイルでない物が在る（`src/sourcefiles.py` の `errors`）→ 「source_files に作業ツリーの根からの相対の正規形で版に在るファイルでない物が在る: [<名>…]——出典にしたリポジトリの中のファイルを、…（依頼のファイルなどリポジトリの外の物・git が無視するファイルは書かない）」。git が動かない時は「source_files を確かめられない（…）」で拒む（『分からない』を合格に倒さない）。
  - どれも `Reject` を `accept.guard` が `{ok: false, reason}` にする。照らしは `accept.in_repo(repo)` の中で回す。
- 受けた時: `split_means(reply)` で外した `means` の並びを先に `purpose-means.json` に `{"means": [...]}` で書き（並びが空でも書く。今の :1251-1254 と同じ結果）、最後に `means` を外した返答を `purpose.json` に書く（`purpose.json` が済んだ印）。
- 回数: `rolekit.accept_round(place, "purpose", raw, take)`。受けた時は 1 回目でも `done` が true、拒んだ時は 3 回目の拒みで `done` が true になり、loop を抜ける。loop は `fresh_context: false` なので、2 回目からは同じ会話の続きで役が起きる（md は「新しい会話で起きた」とは書かない。2 回目からは却下の段落が頭に入る）。run は止めない。
- 諦めた時に出口へ書く物: `finish` が `status: failed`・`purpose: null`・`purpose_text: ""`・`source: ""`・`means: []`・`reason` に `rolekit.given_up_reason(place, "purpose")`（最後の拒みの文）・`report` に `目的の文: <reason>` を返す。

### 2.9 試験

7 節に全部を書いた。この node に当たる物: standalone の fixture・指示の比べ（7.3）・受け付けの振る舞いの試験（7.2 の `AcceptCase`）。守る keep-essence の番号は 7.4。

## 3 script の node

### 3.1 `intake.py`

1. place に `purpose.json` が在れば（同じ place で前に固めた目的）、port を読まず、ほかのファイルも消さずに、`intake.json` に `{frozen: true, failed: false, reason: "目的は既に固めてある（purpose.json）", …}` を書き、`{due: false, reason: <同じ字>}` を返す（今の `purpose_prep` が port の材料を読む前に `refuse_if_frozen` で役を起こさなかった道。`lib/judge_accept.py:1264-1267`）。
2. `request`・`pr_text`・`constraints`・`lang` を `os.environ.get("INPUTS_REQUEST")` などの字のままで読む。`request` は `requestrows.parts(raw)` で照らし（形・知らない鍵・下書きの行）、写しの元は `ports.json(raw, "shared:request.schema.json")` の値。`constraints` は `ports.json(raw, "shared:constraints.schema.json")`、ほかは `ports.text(raw)`。
3. この block が名を持つファイル（`intake.json`・`tree.json`・`purpose-means.json`・`rejects-purpose.json`・`purpose-prompt-*.md`）を消す。ほかの名のファイルは消さない。
4. 役に見せる依頼の写し `request = steps.request_copy(doc)`: `carry.without_prior(doc)` が None でなければそれ（容器から `prior_failures` を外した物）、None なら `doc` のまま（今の :1268-1272）。
5. 制約の行 `constraints`: port の値が配列ならそれ、`{"constraints": [...]}` ならその欄。`実測` の行の `measured_output` の欠けは拒まない（持ち越しの行は持たない）。
6. `intake.json` に `{request, pr_text, constraints, lang, frozen: false, failed: false, reason: ""}` を書く。
7. 作業ツリーの写しを `tree.json` に書く（`accept.tree_state(Path.cwd())`。今の :1283 の `snap_tree`）。
8. `{due: true, reason: ""}` を返す。
9. 2〜7 のどこかで例外が出たら、落ちずに `intake.json` に `{failed: true, reason: "目的の役の支度が落ちた（<型>: <訳>）", …}` を書き、`{due: false, reason: <同じ字>}` を返す（今の `workflows/judge/scripts/purpose_prep.py:25-28` の訳の字）。place を作れない時は返りだけを返す。

### 3.2 `purpose_prep.py`

1. `intake.json` と、place の却下の控え（`rolekit.rejected(place, "purpose")`。古い順の全部）を読む。
2. `prompt.emit("purpose", values, when, prompt.round_of("purpose"))` を呼び、`{prompt}` を返す。`when = {"rejected": 却下が在る, "pr": pr_text が空白だけでない, "spawns": False}`。
3. `values`（全部の差し込み口。5 節）: `rejection`（`rolekit.rejects_text(却下の並び)`）・`request`（`json.dumps(request, ensure_ascii=False, indent=1)`）・`pr_text`（`intake.json` の `pr_text`。空でも渡す）・`constraints`（`json.dumps(constraints, ensure_ascii=False, indent=1)`。空なら `[]`）・`pr_source`・`plan_source`・`writer_source`・`unknown_source`（`steps` の出典の語）・`measured`・`hypothesis`（`steps.MEASURED`・`HYPOTHESIS`）・`lang`（空なら土台の既定の文）。

### 3.3 `purpose_accept.py`

`INPUTS_REPLY` を読み、place と `Path.cwd()` で 2.8 の `rolekit.accept_round` を呼ぶ。返り `{ok, done, reason}`。

### 3.4 `finish.py`

1. `intake.json` を読む。`failed` が真なら `status: failed`、`reason` はその訳。
2. ほかは `purpose.json` を読む。受け付けは `purpose-means.json` を先に、`purpose.json` を最後に書くので、`purpose.json` が済んだ印になる。在れば `status: ok`（`frozen` が真なら `reason` は「目的は既に固めてある（purpose.json）」、ほかは空の字）。`means` は `purpose-means.json` の `means`。その控えが無い・読めない・字の配列でなければ、空の並びにせず `status: failed`（「目的の解き方の控え purpose-means.json が無いか読めない（目的の控えが書きかけ）」）。`purpose.json` が無ければ `status: failed`、`reason` は `rolekit.given_up_reason(place, "purpose")`、それが空なら最後の拒否の文、それも無ければ「目的の文を受け付けた控えが無い（役が走らなかったか落ちた）」（今の `lib/judge_accept.py:3920` の訳と同じ向き）。
3. 返り: `{ok, status, reason, purpose: ports.pointer(place / "purpose.json", "json(shared:purpose.schema.json)") か None, purpose_text, source, means, report}`。`report` は 1.2 のとおり。
4. どこで例外が出ても落ちず、`{ok: false, status: failed, reason: "<型>: <訳>", purpose: null, purpose_text: "", source: "", means: [], report: ["目的の文: <訳>"]}` を返す。

`finish` の `output_format`:

```yaml
type: object
additionalProperties: false
required: [ok, status, reason, purpose, purpose_text, source, means, report]
properties:
  ok: {type: boolean}
  status: {type: string, enum: [ok, failed]}
  reason: {type: string}
  purpose:
    type: [object, "null"]
    properties:
      type: {type: string, enum: [archon_artifact]}
      run_id: {type: string}
      path: {type: string}
  purpose_text: {type: string}
  source: {type: string, enum: [①PR 説明, ②計画・タスク記述, ③writer の要約, 目的不明, ""]}
  means: {type: array, items: {type: string}}
  report: {type: array, items: {type: string}}
```

null を許す欄の書き方は、今の `workflows/chain/works-factory-chain.yaml:359-361` と同じ。`intake` の返り `{due: boolean, reason: string}`・`purpose_prep` の返り `{prompt: string}`・`purpose_accept` の返り `{ok: boolean, done: boolean, reason: string}` は、どれも `additionalProperties: false` で全部の欄を `required` にする。

## 4 作るファイルと触るファイル

作る:

- `workflows/purpose/works-factory-purpose.yaml`
- `workflows/purpose/prompts/purpose.md`
- `workflows/purpose/scripts/intake.py`・`purpose_prep.py`・`purpose_accept.py`・`finish.py`（どれも uv の頭の宣言 `# /// script` を持つ）
- `workflows/purpose/src/__init__.py`・`src/steps.py`・`src/sourcefiles.py`
- `workflows/.shared/schemas/constraints.schema.json`（共通の形。`.shared/AGENTS.md` の一覧にも足す）
- `workflows/purpose/fixtures/standalone.stubs.yaml`・`frozen.stubs.yaml`・`gave-up.stubs.yaml`
- `tests/blocks/purpose/__init__.py`・`test_purpose.py`
- `docs/design/purpose.md`（この文書。直す時）

触らない: `lib/`（読むだけ）・`workflows/`・ほかの block。共通の形 `request.schema.json` と口 `requestrows.py` は土台の物を使う。共通の断片 `workflows/.shared/prompts/rejected.md`・`query-rule.md` は土台の PR が置く物を使う。

## 5 差し込み口の一覧（`prompts/purpose.md`）

| 口 | 値の出どころ |
|---|---|
| `rejection` | place の却下の控えの全部（`rolekit.rejects_text(rolekit.rejected(place, "purpose"))`） |
| `request` | `intake.json` の `request`（← port `request` から `prior_failures` を外した写し）の JSON の字 |
| `pr_text` | port `pr_text`（空でもよい） |
| `constraints` | `intake.json` の `constraints`（← port `constraints`）の JSON の字 |
| `pr_source`・`plan_source`・`writer_source`・`unknown_source` | `src/steps.py` の出典の語 |
| `measured`・`hypothesis` | `src/steps.py` の `MEASURED`・`HYPOTHESIS` |
| `lang` | port `lang`（空なら土台の既定の文） |

選ぶ段落の名: `rejected`（却下の控えに拒否が在る）・`pr`（`pr_text` が空白だけでない。md は `if not pr` だけを使う）・`spawns`（共通の断片 `query-rule` の中。いつも false）。

## 6 単独で呼ぶ

```sh
bin/works-factory workflow run works-factory-purpose \
  --input request='[{"where":"stats.py:4","text":"mean は 2 でなく 3 を返す。分母を len(xs) にする"}]'
```

出力は `workflow get <run>` の `finish` の返り。始めの記録は要らない。前提の実測と PR の説明は渡さなくてよい（空の配列と空の文）。

## 7 試験と、済んだと言える条件

### 7.1 standalone の fixture（`workflows/purpose/fixtures/`）

- 形は README の 13 章のとおり、`exec-code: true` で script を本当に走らせ、AI の node の返答だけを差し替える。入力はどれも `request: '[{"where": "stats.py:4", "text": "mean は 2 でなく 3 を返す。分母を len(xs) にする"}]'` だけ。
- `standalone.stubs.yaml`: `expect: completed`・`reached: [intake, purpose-prep, purpose, purpose-accept, finish]`。prep は差し替えない。`resolved-text-contains` の `purpose` は md の決まった文（`You are the purpose role.`）。役の返答は `{purpose_text: 平均の関数が正しい値を返す, source: ②計画・タスク記述, known_weaknesses: [], source_files: [], means: [分母を len(xs) にする]}`。
- `frozen.stubs.yaml`: 筋書きの place は空なので、`intake: {due: false, reason: 目的は既に固めてある（purpose.json）}` と `finish`（`status: ok`）の返りを差し替えて、輪を通らずに出口へ届く配線だけを見る。`reached: [intake, finish]`。固めた目的を読む道は `FinishCase` が見る。
- `gave-up.stubs.yaml`: 役の返答だけを差し替え、`source_files` に版に無いファイルを返させる。`reached: [intake, purpose-prep, purpose, purpose-accept, finish]`・`expect: completed`。筋書きは輪を 1 周で終えるので、3 回で諦める数えは `FinishCase` が見る。

### 7.2 `tests/blocks/purpose/test_purpose.py`

script を子のプロセスで回す（今の `tests/workflows/test_judge.py:695-704` の `Run.run` と同じ形。`hermetic.child_env` で `ARTIFACTS_DIR`・`WORKFLOW_ID`・`WORKS_FACTORY_ROOT`・`PYTHONDONTWRITEBYTECODE=1`・`INPUTS_…` を渡す）。始めの記録は置かない。使い捨ての git のリポジトリに `README.md`・`docs/plan.md`・`sub/x.py`・git が無視するファイルを置く。

- `IntakeCase`（元: `lib/tests/test_judge_accept.py::PurposeCase.test_purpose_material_has_no_prior_failures`〔:1076〕・`test_prep_snapshots_the_tree_the_accept_compares`〔:1067〕と `tests/workflows/test_judge.py::test_purpose_prep_failure_writes_a_stop`〔:1264〕）: 容器の `prior_failures` が `intake.json` の `request` に無く、ほかの欄は字のまま。`tree.json` が取られる。place に `purpose.json` が在れば、読めない port でも `due: false` でほかのファイルも消さない。前の回の自分の控え（却下・指示）を消し、古い却下が次の指示に届かず、指示の回が 1 から数え直す。読めない port・前提の実測の行の形（知らない欄・空白だけの `measured_output`）で `due: false` と「目的の役の支度が落ちた」の訳。持ち越しの形（`実測` で `measured_output` の無い行）は通る。
- `PromptCase`（元: `PurposeCase.test_pr_body_reaches_purpose_brief`〔:1018〕と `tests/workflows/test_judge.py::test_purpose_role_does_not_see_the_prior_run`〔:501-506〕・`test_roles_that_reach_outside_carry_the_query_rule` の purpose の行）: `purpose_prep` の `prompt` に PR の文が在り、PR の無い run では「(This run has no PR.)」が在る。前提の実測の行が在る。容器に `prior_failures` を持つ依頼でも、`prompt` と YAML の `purpose` の node の欄に `prior_failures`・`prior-failures`・`judgment`・`PRIOR` の字が無い。外への検索の決まりの断片が入る。埋まらない差し込み口が無い。
- `AcceptCase`（元: `PurposeCase` の `test_good_reply_writes_purpose_and_means`・`test_purpose_role_changed_the_tree_rejected`・`test_source_files_outside_or_missing_rejected`・`test_source_files_nested_ignored_and_subdir`・`test_frozen_purpose_is_not_overwritten`〔:990-1066〕）: 通った返答が `purpose.json`（`means` を外した物）と `purpose-means.json` に書かれる・役が作業ツリーを変えたら拒む・リポジトリの外や無い名を拒む・入れ子・無視されるファイル・サブディレクトリで回した時の決まり・固めた目的を書き直さない。
- `FinishCase`: 受けた時は `status: ok` と pointer と `purpose_text`・`source`・`means`。固めた目的の時は `status: ok` と固めた中身。3 回拒まれた時は `status: failed` と null と諦めた文（「3 回とも」）と `report` の 1 行。1 回の拒みで輪が終わった時は最後の拒否の文。解き方の控えが無い・読めない時は `status: failed`。include された時は place が include の道に分かれる。
- `ShapeCase`: YAML の `purpose` の `output_format` の `source` の enum が `steps` の 4 語の並び、`finish` の `source` の enum がその 4 語と `""`、loop の `max_iterations` が `rolekit.GIVE_UP_AFTER`、AI の node の鍵（群・`settingSources`・道具・sandbox・`idle_timeout`・`mutates_checkout`・`retry`）が 1.3 のとおり（元: `test_roles_keep_the_old_settings` の purpose の行）。
- 写さない試験: `tests/workflows/test_judge.py::test_missing_premises_or_purpose_stops_even_with_an_accepted_judgment`（judge のまとめへ）・`PurposeCase` の `DueCase.test_purpose_review_only_for_writer_summary`（line と素材の観点へ）・`test_missing_purpose_is_said_not_invented`〔:1363〕と `test_verdict_places_purpose_review_sibling`〔:2793〕（diagnose・judge のまとめへ）。

### 7.3 指示の比べ（README の 11.4）

この PR では作らない（訳は 8 節）。今の指示と新しい指示を同じ値で組んで並べた物は、PR の審査に出す時に作る。

### 7.4 keep-essence の番号

- 9（独立設計）: 独立の目は目的の文だけから設計する。この block は、目的の文に依頼の解き方を混ぜさせない（md の「目的と解き方を分けよ」と、受け付けが `means` を外して別に置く）。守るのは `AcceptCase` の `test_good_reply_writes_purpose_and_means` の写し（`purpose.json` に `means` が無く、`purpose-means.json` に在る）と、`PromptCase` の前の run の判断を見せない試験（持ち主の決め `premises-purpose`）。
- 12（世界の解に照らす）: 世界の解は依頼の解き方を定石と比べる。その解き方の並びはこの block の `means`。守るのは `FinishCase`（`means` が出力の欄に載る）。読み手の側（world が `means` を受ける）は world の試験。
- e2e の照らしの表 `tests/e2e/evidence.json` の `J16`（作業ツリーの写し。今は `judge/purpose-tree.json`）と `J17`（`judge/purpose.json` の `source_files`）は、node の id と place のパス（`judge/purpose-run/tree.json`・`judge/purpose-run/purpose.json`）を新しい物に合わせる。

### 7.5 済んだと言える条件（PR ごと。README の 11.2）

```sh
PYTEST_XDIST_AUTO_NUM_WORKERS=4 WORKS_FACTORY_ARCHON_CACHE=<Archon の源の置き場> nice -n 19 python3 -m pytest -q tests/blocks tests/layers
```

`tests/blocks/purpose/test_purpose.py` が block の振る舞いを、`tests/layers/test_block_shape.py` が形の検査と、`ArchonCase` で 3 本の筋書きが Archon の `workflow test` で全部通ることと `archon validate` が警告なしで通ることを照らす（源と bun が無ければ見送る。CI は赤）。最後に、6 節の命令で本物の単独の run を 1 回回す。

## 8 根拠を書いて自分で決めた事

1. 材料のファイルを Read させる形をやめ、材料を指示の中に入れた。根拠は [head-depth.md](head-depth.md) の 8 節の 2 と同じ（材料の題と見出しは Python が持つ決まった文。README の 5.2）。
2. 固めた目的（place に `purpose.json` が在る）の時は役を起こさず、その目的を `status: ok` で返す。根拠: 今の支度も役を起こさず（`lib/judge_accept.py:1264-1267`）、judge の返りは在る `purpose.json` を指した（:3974-3976）。block の出力で同じ事をすると、固めた目的をそのまま返す形になる。受け付けの `refuse_if_frozen` も残す（1 回目の受けで loop を抜けるので当たらないが、once の決まりを受け付けの側でも縛る今の形を変えない）。
3. 前提の実測の空の時の字「（前提の実測は無い）」を、空の配列 `[]` と説明の 1 文にした。根拠: 空の時だけ囲みを外す組み方は、Python が囲みの字を持つか、差し込み口を選ぶ段落の中に置くかになる。空の配列は今の役が読む JSON と同じ形で、意味の説明を md に 1 回書けば済む。
4. PR の説明は README のとおり文の port `pr_text` で受け、番号・題・本文の見出しを組むのは line に残した。根拠: 単独の run で人が PR の本文をそのまま渡せる。見出しの組み方（`pr_file_text`）は始めの記録の `input.pr` の形を知る line の物。
5. 出力に `purpose_text`・`source`・`means` を欄で置き、目的の控え全体は pointer で返す。根拠: 世界の解と独立設計は `purpose_text`（と `means`）しか読まない（README の 4.2 の「3 つ以上の欄を読む時だけ pointer」）。素材の観点・diagnose・plan は 4 つの欄を読むので pointer。
6. 前の回までの却下の理由は、prep が place の却下の控えから全部を読む（`with: {reason: $LOOP_PREV…}` で前の回の 1 つだけを運ぶ形にしない）。根拠: README の 13 章と `.shared/AGENTS.md` の土台の決め（resume で輪が 1 周目から回り直しても数え直さない・#351 の「却下の理由を古い順に全部渡す」）と手本の world。
7. 依頼の形は共通の `shared:request.schema.json` を使い、前提の実測の形も共通の `workflows/.shared/schemas/constraints.schema.json` に置いて、block の `schemas/` は持たない。根拠: README の 13 章「同じ名の形のファイルが pack の 2 か所に在れば形の検査が赤」「足りない共通の形（`constraints.schema.json` など）は、最初に要った PR が足す」。形の行は今の前提の役の `output_format`（`workflows/judge/works-factory-judge.yaml:594-606`）と [premises.md](premises.md) の行の形に合わせ、`additionalProperties: false` と `measured_output` の `minLength`・`pattern` を持たせた（#772 の審査）。premises.md の形との違い: `if`/`then`・`oneOf`・`$ref`・`$defs` は `KNOWN_KEYWORDS` の外なので使わない（`実測` の行の `measured_output` の扱いは 8）。容器の外側（`{constraints: [...]}` のほかの欄）は閉じない（前提の実測の block の返りまるごとの pointer を受けるため）。依頼の容器の照らしは土台の口 `requestrows.parts` に通し、役に見せる写しは `ports.json` の値から `prior_failures` だけを外す（ほかの欄は字のまま）。
8. `実測` の行の `measured_output` の欠けは拒まない。根拠: 前の run から持ち越した行（`lib/carry.py:137-141` の `carried_constraints`・`lib/runreport.py:1814`）は `measured_output` を持たず、元の judge は前提の受け付けの後にそれを足して（`lib/judge_accept.py:1187-1192` の `with_carried`）目的の役へ確かめずに貼った（:1274-1281）。拒めば持ち越しの在る run が毎回ここで止まる。役自身の返りの `measured_output` は前提の block が見る。
9. 固めた目的の照らしを port の読みより先にした。根拠: 今の `purpose_prep` も材料を読む前に `refuse_if_frozen` で役を起こさないと決めた（`lib/judge_accept.py:1264-1267`）。固めた目的は port の値に依らないので、port が読めなくても固めた目的を返す（#772 の審査）。
10. 入口は place の中の、この block が名を持つファイルだけを消す（`purpose.json` は在れば固めた目的の道に入るので消さない）。根拠: README の 13 章と `.shared/AGENTS.md`「place は作るだけで消さない。消してよいのは自分が名を持つファイルだけ」。
11. 受け付けは `purpose-means.json` を先に、`purpose.json` を最後に書き、出口は解き方の控えが無い・読めない時に `means: []` にせず `failed` を返す。根拠: `purpose.json` が在れば両方が書き終わっている、と読めるようにする（書きかけの控えを、解き方の無い目的と取り違えない。#772 の審査）。
12. 出口が `purpose.json` を見つけられない時の訳は、諦めた文（`rolekit.given_up_reason`）→ 最後の拒否の文 → 「目的の文を受け付けた控えが無い」の順。根拠: 手本の world の `_why_failed` と同じ。筋書き（dry-run）は輪を 1 周で終えるので、諦めの数に届かない拒否の訳も残す。
13. 筋書きは README の 13 章の形（`exec-code: true`・prep を差し替えない・AI の node を `reached` に持つ・`resolved-text-contains` が md の決まった文）。根拠: script の返りを差し替える筋書きでは md が組めるかを照らせない（形の検査の `check_standalone_renders`）。`frozen` だけは筋書きの place が空なので入口と出口を差し替える。
14. 指示の比べ（日本語の md の 1 つ目の commit と `test_prompt_compare.py`）と `test_fixtures.py` は作らない。根拠: 手本の world.md の 8 節の 7 と同じ。筋書きは `tests/layers/test_block_shape.py` の `ArchonCase` が全部の block の分を回す。
15. `finish` の `purpose` の欄の null は `type: [object, "null"]` で書き、`anyOf` を使わない。根拠: 土台は `KNOWN_KEYWORDS` の外の語（`anyOf`・`oneOf`・`format` など）を拒む。この block は `ports.picked` を使わない。
16. 指示の md は、この役の出力の性質（目的の文は後で依頼なしに読まれる決まった入力になる・`source_files` の名は後の周に字のまま比べられる）だけを書き、後の役の振る舞いを書かない。根拠: 憲法の 3（ほかの block を名指さない）と #772 の審査。

## 9 README へ返す問題

1. 出典のファイルの照らしの部品（`_resolve_target`・`_in_version`。今は `lib/judge_accept.py:2236-2260`）を、purpose・diagnose（`_count_in_version` が使う。:2317-2355）・`lib/recount.py:263` の 3 つが使う。README の 9.2 は `judge_accept` を観点ごとに割るとだけ書き、この共通の部品の行き先が無い。この block は作り直しの間 `src/sourcefiles.py` に写すが、組み込みでは `lib/` の 1 モジュール（例 `lib/versioned.py`）に寄せるのがよい（憲法の 4）。
2. 制約の行の語（`実測`・`仮説`）は premises が作り、purpose・diagnose・report・`lib/carry.py`（`MEASURED`）が読む。出典の語（`③writer の要約`・`目的不明`）は purpose が作り、line（目的の監査を回すか）・diagnose（目的が無い時の字。`lib/judge_accept.py:2080`）が読む。README の 4.1 の「2 つ以上の block が読む行の形は作り手の出力ごとに `lib/` の 1 モジュール」に当たるが、README の 4.1 と 9.3 の一覧に無い。この block は作り直しの間 `src/steps.py` に語を置く。
3. 目的の段が落ちた時の止めの語 `works:purpose`（今の `stopby.PURPOSE`）の持ち主（[premises.md](premises.md) の 9 節の 3 と同じ）。

## 10 未確認

- 6 節の命令の正確な形（world.md と同じ）。
- `ports.py` の口の名（`json`・`text`・`pointer`・`returns`・`place`）。土台の PR の名に合わせる。
- 元の works の目的のブロックの intake が前提の実測を照らした `check_constraints` を、工場が #76 で写さなかった意図（2.7）。
