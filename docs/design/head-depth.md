# block の設計書: head-depth（run の頭の深さ）

- 何の話か: 依頼の行ごとに「まだ決まっていない事の種類」（未知の種類）を引用つきで AI に選ばせ、その種類から run 全体の深さの段（軽量・標準・重厚）を機械が引く観点を、単独で呼べる block `blocks/head-depth/` にする設計。型は [README.md](README.md) に、形は手本の [world.md](world.md) に従う。
- 決めたこと: 今の judge の 4 つの node（head-depth-prep・head-depth-reject・head-depth・head-depth-accept）を、5 つの node の block にする。入力は依頼の行・機械の確かめの有無・段の名指し・仕様の段・設計だけ・言語の 6 つの port だけで、始めの記録と止めの記録を読まない。指示は英語の md 1 本（`prompts/head-depth.md`）にまとめ、今の材料のファイル `depth-head-brief.md` を Read させる形をやめて、材料を指示の中に入れる。lib の Python に在った群の節の見出しと「記録だけ」の 1 文は md へ出す。未知の種類 → 段の表（今の `headdepth.UNKNOWNS`）と受け付けは、この block の `src/` に置く。振る舞いは変えない。
- 持ち主に求めること: なし。読み手は、この block を作る実装の役（この文書だけで作れる細かさにした）と、その PR の審査。

この文書の語は README の頭の物を使う。ほかに:

- 持ち主: このリポジトリの owner（決めを下す人）。「持ち主の決め `<名>`」は `docs/owner-decisions.md` の決めの名。
- line: 工場（works-factory。この repo の Archon の workflow 群）のメイングラフ。始めの記録（run の起動の時の入力の記録）を書き、block に port の値を配る。judge のまとめ（`blocks/judge/`）は判定の block を `include:` で並べる graph で、line がそれを include する。
- 土台の PR: README の 11.1 の 0 の PR（`blocks/.shared/ports.py`・`prompt.py`・共通の指示の断片 `rejected.md`・`query-rule.md`・起動の殻の口を置く）。この block の PR より先に入る。この文書が「土台に合わせる」と書く名は、そこで決まる。
- 源と bun: 試験が Archon を起こすのに要る、止めた版の Archon のソース（`bin/_lib/place.archon_source` が取る）と JavaScript の実行環境 bun。無い手元では、その試験を名前つきで見送る（`tests/AGENTS.md`）。
- keep-essence: 元の works が守る 12 の仕組み（README の 10 節）。9 は「独立設計と R1〜R4」で、R1〜R4 は修正の後に別の目が見る 4 つの確かめ（R1 最小性・R2 独立設計との比べ・R3 全体の整合・R4 見えていない範囲）。12 は「世界の解に照らす」。
- 1 つ目の commit・2 つ目の commit: この block の PR の中の 2 つの commit（README の 11.4）。1 つ目は指示の md を日本語のまま置いて今の指示と同じ字かを試験で照らし、2 つ目で英語にする。2.3 の md の本文は 2 つ目の物。
- 深さの役（head-depth）: 依頼の行ごとに未知の種類を 1 つ選び、依頼の字とリポジトリの行の引用で示す AI の役。道具は Read・Grep・Glob だけ。
- 未知の種類: `無し`・`原因`・`形`・`範囲` の 4 語（今の `lib/headdepth.py:66` の `NONE`・`CAUSE`・`SHAPE`・`SCOPE`）。種類 → 段は `無し` → 軽量、`原因`・`形` → 標準、`範囲` → 重厚（`lib/headdepth.py:67`）。
- 段: 軽量・標準・重厚の 3 語（今の `lib/depth.py:58-60`）。段 → 回す物の表（`lib/depth.py:85` の `TIERS`）は line の物で、この block は持たない。
- 機械の止め: 役を起こす前に、機械が段を決めてしまう道（名指し・仕様の段・設計だけ・依頼の行が無い・機械の確かめが無い）。今の `headdepth.gate`（`lib/headdepth.py:93-102`）。
- 群の選び: 役が「この群の模型か effort を既定から替えるべき」と返す行。記録に残すだけで、走りには効かない（持ち主の決め `head-choice-record-only`）。
- 控え: place の `depth-head.json`。形は今の `lib/headdepth.py:173` の `record`（`{depth, why, items, facts, groups}`）のまま。
- 例の run: 本物の run `df5e111f-ea97-409b-8066-2245d32746ab`（対象 raiki61/works-factory。置き場 `~/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/artifacts/runs/df5e111f-…/judge/`）。`depth-head-brief.md`・`depth-head.json`・`request.json`・`start.json` から骨組みの値を取った。この run は 1 回目で通り、拒みの控え `rejects-head-depth.json` は無い。

## 1 block の全体

### 1.1 役

依頼の各行について、原因と直す所がもう分かっているか・形の選びが要るか・公開の約束を変えるかを、依頼の字とリポジトリの行の引用で示させる。引用が依頼とリポジトリに字のまま在るかを機械が照らし、通った行の一番重い種類から run の段を引く。照らしが通らない・役が走らない・機械の止めに当たる時は、標準（呼ぶ人が段を名指した時はその段）に倒す。あわせて、AI の node の群のうち既定の模型か effort を替えるべき群を訳つきで選ばせ、照らして記録に残す（走りには効かせない）。

### 1.2 port

入力（YAML の `inputs:`）:

- `request`（必須）: `json(request.schema.json): 依頼の行の配列 [{where, text, mechanism?, measured?, false_positive_if?}]。それを findings の欄に持つオブジェクトでもよい（工場の依頼のファイルの形）。空の配列は依頼の行の無い run（役を起こさず標準）`
- `has_checks`: `flag: 機械の確かめ（試験のコマンドか TDD の実行器）が在るか。false なら役を起こさず標準`。既定 `false`。
- `thickness`: `choice(自動|軽量|標準|重厚): 呼ぶ人の段の名指し。自動（空も同じ）は役が依頼の行から選ぶ。ほかは役を起こさずその段`。既定 `自動`。
- `spec`: `flag: 仕様の段を挟む run か。true なら役を起こさず標準`。既定 `false`。
- `design_only`: `flag: 設計だけの run か。true なら役を起こさず標準`。既定 `false`。
- `lang`: `text: 人に見せる欄（why・groups[].why）の言語。空は依頼の行の言語`。既定 `""`。

出力（`returns: finish`、`outcome_field: ok`）:

- `ok`: boolean。`status` が `ok` か。
- `status`: `ok` か `failed`。`ok` は、段が役の受けた返答か機械の止めで決まった時。`failed` は、intake が落ちた・役が 3 回拒まれた・役が走らなかった（返答が受け付けに届かない）時で、段は標準に倒れている。
- `reason`: 日本語の 1 行。`failed` の訳（`ok` の時は空の字）。
- `tier`: `軽量`・`標準`・`重厚` のどれか。どの道でも必ず在る。
- `why`: 段の根拠の日本語の文（今の判定の出力の `depth_why` と同じ中身。控えの `why`）。
- `rows`: 受けた返答の行の配列 `[{item, unknown, cause_quote, where?, code_quote?}]`（今の控えの `items`）。受けた返答が無ければ `[]`。
- `record`: pointer（place の `depth-head.json`）。`lib/headdepth.py` の `read_file`・`cited_files`・`groups_lines` がそのまま読む形。どの道でも必ず書く。
- `report`: 報告の行の配列。1 行だけ: `run の頭の深さ: <tier>（根拠: <why>）`。

今との違い: 今は入力を `judge/request.json` と始めの記録のポインタ（`INPUTS_START`。`lib/headdepth.py:82-90` の `facts` が `test_cmd`・`tdd_suite`・`input.spec`・`design_only`・`thickness` を読む）と止めの記録 `judge/stop.json`（`workflows/judge/scripts/head_depth_prep.py:25-29`）から読み、出口は judge の返す節の欄 `depth`・`depth_why`・`depth_record`（`lib/judge_accept.py:3995-4003` の `head_depth`）だった。止めの記録の確かめは無くし、回すかは graph の `when:` が決める（README の 4.3）。報告の行の「省く物・足した物」（今の `headdepth.report_line` の後半。`lib/headdepth.py:266-272`）は段 → 回す物の表から引く物なので line が組み、この block の `report` には段と根拠だけを置く（8 節の自分で決めた 3）。

### 1.3 node の並び（`blocks/head-depth/works-factory-head-depth.yaml`）

1. `intake`（script `intake.py`。`mutates_checkout: false`）: port を読み、place の中のこの block のファイルを名で引いて消し（place そのものは消さない。README の 13 章）、事実を測って機械の止めを通し、標準（か止めの段）の控えを先に書く。`intake.json` を書く。返り `{due, reason}`。
2. `head-depth-loop`（`loop_group`、`max_iterations: 3`、`fresh_context: false`、`until_bash: done=$head-depth-accept.output.done; test "$done" = true`。`depends_on: [intake]`・`when: $intake.output.due == true`）
   - `head-depth-prep`（script `depth_prep.py`。`mutates_checkout: false`・`with: {reason: "$LOOP_PREV.head-depth-accept.output.reason"}`）: 指示を組む。返り `{prompt}`。
   - `head-depth`（AI。`depends_on: [head-depth-prep]`・`prompt: "$head-depth-prep.output.prompt"`・`model: '@wf-judge-materials'`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`idle_timeout: 1728000000`・`mutates_checkout: false`・`retry: {max_attempts: 2, on_error: all}`。`output_format` は今のまま。2.4）
   - `head-depth-accept`（script `depth_accept.py`。`depends_on: [head-depth]`・`mutates_checkout: false`・`with: {reply: $head-depth.output}`）: 返り `{ok, done, reason}`。
3. `finish`（script `finish.py`。`depends_on: [intake, head-depth-loop]`・`trigger_rule: all_done`・`mutates_checkout: false`）: 控えを読み、出力を返す。どの段が落ちても落ちない。

どの script の node も `runtime: uv`。今の `head-depth-reject`（`reject.py`。前の回の理由と言語の 1 行を返すだけの node）は無くす。理由は prep の `with:` で受け、言語は port `lang` で受ける。

script の名は `lib/` のモジュールの名と重ねない（README の 7.1 の 9）。`depth.py` は `lib/depth.py` と重なるので、`depth_prep.py`・`depth_accept.py` にした。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、line から judge のまとめを通して include された時は `$ARTIFACTS_DIR/judge/head-depth/`）の下に書く。名は `src/steps.py` だけが持つ。

- `intake.json`: `{facts, due, failed, reason, lang}`。`facts` は 3.1 の形。`failed` は intake が落ちた時だけ true。
- `depth-head.json`: 控え。今の `judge/depth-head.json` と同じ名・同じ形。
- `head-depth-prompt-<n>.md`: 組んだ指示（`<n>` は loop の何回目か）。
- `rejects-head-depth.json`: 拒みの控え（`rolekit.accept_round` が書く。今と同じ名）。

今の `judge/depth-head-brief.md` は書かない（材料は指示の中に入る）。

### 1.5 コードの置き場

- `blocks/head-depth/src/__init__.py`: 空。
- `blocks/head-depth/src/steps.py`: 今の `lib/headdepth.py` の `facts`・`gate`・`brief`（材料の行を組む部分だけ）・`_place`・`_squash`・`_known`・`tier_of`・`_check_item`・`check` と、定数 `NONE`・`CAUSE`・`SHAPE`・`SCOPE`・`UNKNOWNS`・`WHERE_SPAN`・`NO_ROWS`・`NO_REPLY`・`NOT_ACCEPTED`・機械の止めの訳の字（`lib/depth.py:75` の `UNCHECKED` と `lib/depth.py:207` の `named_why` の字の写し）を写した物。place のファイルの名（`INTAKE_FILE = "intake.json"`・`RECORD_FILE = "depth-head.json"`・`ROLE = "head-depth"`）もここだけが持つ。`facts` は始めの記録でなく port の値を受ける（3.1）。
- `blocks/head-depth/src/report.py`: `report_line(tier, why) -> str`。`f"run の頭の深さ: {tier}" + (f"（根拠: {why}）" if why else "")`。
- `blocks/head-depth/schemas/request.schema.json`: 5 節の形。
- 使う `lib/`:
  - `headdepth`（KEEP。段の語と控え）: `LIGHT`・`STANDARD`・`record`・`read_file`。
  - `depth`（作り直しの間だけ）: `HEAVY`・`HEADS`（段の重さの順）。今の `lib/headdepth.py` が `HEAVY`・`HEADS` を自分の名で出していないため。組み込みで `lib/headdepth` に段の語の 4 つ（`LIGHT`・`STANDARD`・`HEAVY`・`HEADS`）を移したら、そちらを読むように 1 行直す（8 節の README へ返す問題 1）。
  - `cite`（KEEP）: `CITE`・`QUOTE_MIN`・`problem`・`file_problem`・`quoted_in`・`resolved`（番地の規則と引用の照らし）。
  - `launchgroups`（KEEP）: `GROUPS`・`MODELS`・`EFFORTS`・`choices`。`brief_section` と `RECORD_ONLY`・`SECTION_HEAD` は使わない（文は md へ）。
  - `rolekit`（KEEP）: `accept_round`・`given_up_reason`。
  - `jsonfile`・`oneline`。
- 作り直しの間は `lib/headdepth.py` の `facts`・`gate`・`brief`・`check` などを消さない（今の judge が使う）。組み込みで、`lib/headdepth.py` から未知の種類 → 段の表と受け付けを消し、`section`・`ASKS`・`UNKNOWN_HEAD` は読み手の block（diagnose・plan）へ移す（README の 9.2・9.3）。

### 1.6 つなぎ方（graph の側。block には書かない）

- judge のまとめ（`blocks/judge/`）: `include: works-factory-head-depth`。`when:` は「再審の道でない」（今の `head-depth-prep` の `when: $intake.output.go == true && $intake.output.mode == 'judge'`）。`with:` は `request: $<依頼の pointer>`・`has_checks: <始めの記録の test_cmd か tdd_suite が空でない>`（今の `depth.has_checks`）・`thickness: <始めの記録の thickness。空なら 自動>`・`spec: <始めの記録の input.spec>`・`design_only: <始めの記録の design_only が "true">`・`lang: <始めの記録の lang>`。値は line が始めの記録から引いて judge のまとめに配る。
- 判定の裏取り（verify）と根本の診断（diagnose）は、この block の後に回す（今の `test_verify_waits_on_the_head_depth`。`tests/workflows/test_judge.py:929-940`）。判定のまとめの `depends_on` に置く。
- 読み手:
  - line: `tier`（段 → 回す物の表を引く）・`why`・`record`（修正の後の上げ直しが `headdepth.cited_files` で引用の外を数える。報告の `## 模型` の節が `headdepth.groups_lines` で群の選びの行を組む）。
  - diagnose の `row_asks`（`$head-depth.output.rows`）。plan も同じ行を受ける（今の `lib/planfile.py:677` の `headdepth.section`）。種類ごとの指示の文（今の `lib/headdepth.py:210-216` の `ASKS`）は、2 つの読み手の md が使う共通の断片 `blocks/.shared/prompts/unknown-asks.md` に移す（8 節の自分で決めた 4）。
  - report の `sections`（`$head-depth.output.report`）。
- `status` が `failed` でも、graph は止めない。今と同じく、段は標準で先へ進む（深さは判定を止めない。`workflows/judge/scripts/head_depth_prep.py:7`）。
- 再審の道の段は、今と同じく line が「標準・再審の判定」（今の `headdepth.REJUDGE_WHY`）と決める。この block は再審の道で回らない。

## 2 node の設計シート: head-depth（深さの役）

### 2.1 役

依頼の各行に残っている未知の種類を 1 つ、依頼の字とリポジトリの行の引用で示す。あわせて、既定の模型か effort を替えるべき群だけを訳つきで選ぶ。段は返さない。

### 2.2 port

`intake.json` の `facts.items`（← port `request` の行と、番地の実在を機械が測った物）・`facts.test_cmd`（← port `has_checks`。役が起きる時は必ず true）、群の表（← `lib/launchgroups.py` の `GROUPS`・`MODELS`・`EFFORTS`）、前の回の拒みの理由（← loop の `$LOOP_PREV.head-depth-accept.output.reason`）、`lang`（← port `lang`）。リポジトリは run の作業ツリー（Archon の cwd）で、役が Read・Grep・Glob で読む。

### 2.3 組み立ての順（`prompts/head-depth.md`）

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: 前の回の accept の理由が空でない。断片の中の `{rejection}` ← 前の回の拒みの理由（prep の `with: reason` の値のまま。今と同じく前の回の 1 つだけ。8 節の自分で決めた 5）。
2. 役の定義（決まった文）: 新しい会話で起きていること・行ごとに種類を 1 つ引用で示す・段は機械が引く・群の選び。差し込み口 `{light}`・`{standard}`・`{heavy}`（← `lib/headdepth.py` の `LIGHT`・`STANDARD` と `lib/depth.py` の `HEAVY`）。
3. 段の意味（決まった文）。差し込み口 `{light}`・`{standard}`・`{heavy}`・`{cause}`。
4. 読むだけの決まり（決まった文）。
5. `## Input` の 2 行（決まった文）: 対象のリポジトリ・材料は機械が測った物・この run には機械の確かめが在る。
6. 材料の行: 頭の 1 文と `{row_count}`（← `facts.items` の数）・`{rows}`（← `src/steps.py` の `rows_text(facts)` が組む材料の行。3.2）。
7. `## Node groups …` の節（決まった見出しと文）と `{models}`・`{efforts}`（← `launchgroups.MODELS`・`EFFORTS` を `, ` でつないだ字）・`{groups}`（← `src/steps.py` の `groups_text()` が組む群の行。3.2）。記録だけの 1 文（決まった文）。
8. `## Questions`（決まった文）。問い 1・2・3 と、軽量にしない 4 つの場合。差し込み口 `{none}`・`{cause}`・`{shape}`・`{scope}`（← `src/steps.py` の `NONE`・`CAUSE`・`SHAPE`・`SCOPE`）・`{standard}`。
9. `## Output`（決まった文）。返す JSON の形の例と、行の種類ごとの書き方と照らし。差し込み口 `{none}`・`{cause}`・`{shape}`・`{scope}`・`{standard}`・`{quote_min}`（← `cite.QUOTE_MIN`）・`{where_span}`（← `src/steps.py` の `WHERE_SPAN`）・`{lang}`。

md の本文（英語。この block の PR の 2 つ目の commit でこのまま置く）:

````markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

You are the run-depth role, started in a new conversation. For each line of a person's fix request, name the one kind of unknown that is still left, with a quote from the request's text and a quote from the repository's lines (questions 1 and 2). The depth tier ({light}, {standard}, or {heavy}) is taken by the machine from the heaviest kind among the lines; you do not return a tier. Also pick, with reasons, only the node groups whose default model or effort should change (question 3).

What the tiers mean: a {light} run is only for a request where the place to fix and the way to fix it are known on every line. If a run is wrongly made {light}, holes that should be found before the fix stay hidden until after the fix. {standard} runs every check as before; a run wrongly made {standard} only costs more and does no harm. {heavy} adds to {standard} a second check of the judgment and a per-item tree in the review of the plan, and costs much more. So give a lighter kind only where you can show it with quotes, and when in doubt choose `{cause}` (which gives {standard}).

You **only read**. Your tools are Read, Grep, and Glob. Do not change a single character of the working tree.

## Input

- The target repository is the current working directory. Read the working tree as it is now.
- The material below was measured by the machine: each request line's number, text, and location, and whether the file and the line range of the location exist. This run has machine checks (a test command). At the end there is a section of node groups: the group names, their roles, their default pairs, and the allowed model and effort words (weakest first).

{row_count} request lines:

{rows}

## Node groups and their default model and effort (in question 3, choose only the groups whose default you change)

Allowed models (weakest first): {models}
Allowed efforts (weakest first): {efforts}

{groups}

Whether a choice raises or lowers, it is only kept in the record. It does not take effect in this run, in child runs, or in the next round.

## Questions

1. For each request line, name the one kind of unknown that is still left, with a quote from the request's text and a quote from the repository's lines. How much the requester investigated is not a reason to raise or lower the tier (even if the requester did not name the cause and the place to fix, choose `{none}` if you can show the place to fix with the repository's lines).
2. There are four kinds.
   - `{none}`: you can show the cause and the place to fix with quotes from the request's text and the repository's lines.
   - `{cause}`: there is only a symptom and the cause is unknown (the cause is not visible in the code).
   - `{shape}`: a choice is needed: which shape to take, or what to add.
   - `{scope}`: the change alters a public contract (types, configuration keys, the shape of input and output with the outside), or spans more than one subgraph (a part that holds a separate graph). If this applies, choose `{scope}` even when a choice is also needed.

Do not make a line light (do not give it `{none}`) if any one of these applies:

- The line is ambiguous (you cannot read what happens or where to fix).
- It asks for a design choice (which shape to take or what to add). Choose `{scope}` if the definition of `{scope}` above applies, otherwise `{shape}`.
- The cause is not visible in the code (no line in the repository matches the written symptom). Choose `{cause}`.
- It changes a public contract (types, configuration keys, the shape of input and output with the outside). Choose `{scope}`.

When a line is ambiguous or you are unsure of its kind, choose `{cause}` (the tier falls to {standard}). When in doubt, make it {standard}.

3. From the group section above, pick only the groups whose default model or effort should change, and return for each the model, the effort, and the reason. Copy the group names, models, and efforts exactly as they appear in the section (a word not in the lists is put back to the default by the machine). Write the reason for raising or for lowering from the kinds of unknown of the request lines or from facts you can show with quotes. Do not list a group you do not change. If you change nothing, return an empty list. One row per group. This choice does not take effect in this run; it is only kept in the record (it is not mixed into the tier).

## Output

Return only JSON of this shape.

```text
{"why": "1 to 2 sentences on why you gave each line its kind",
 "items": [{"item": <1-based number of the request line>, "unknown": one word of "{none}", "{cause}", "{shape}", "{scope}",
            "cause_quote": "<part of the text of that request line>",
            "where": "<path from the repository root>:<line>" or "<path>:<line>-<line>", "code_quote": "<part of the text in that line range>"}],
 "groups": [{"group": "<a group name from the group section>", "model": "<one allowed model>", "effort": "<one allowed effort>",
             "why": "<1 to 2 sentences on why you change it>"}]}
```

- Whatever tier your answer gives, list every request line in `items` exactly once. `cause_quote` is a copy of the text of that request line (whitespace differences do not count; at least {quote_min} characters after removing whitespace). The machine checks that the copy is in the text word for word and rejects the answer if it is not. If the check does not pass, the run is treated as {standard}.
- `{none}` lines: write `where` and `code_quote`. `code_quote` is a copy of text inside the line range of `where` (at least {quote_min} characters after removing whitespace). The line range of `where` is at most {where_span} lines and names the place to fix. The machine checks that the file and the line range exist and that `code_quote` is there word for word.
- `{shape}` and `{scope}` lines: write `where` and `code_quote`, and they are checked, the same way as for `{none}`, except that the width of the line range is not limited. In `why`, say which applies: a design choice, a change to a public contract, or spanning more than one subgraph.
- `{cause}` lines: `cause_quote` alone is enough (the cause is not visible in the code, so `where` and `code_quote` are optional). If you write `where`, also write `code_quote`. The machine checks `where` and `code_quote` the same way as for `{shape}` and `{scope}`.
- `groups`: the answer to question 3. `[]` if you change no group. The machine checks that the group name, the model, and the effort are in the lists of the section, and puts back to the default only the rows that are not, and the second row of the same group (if the check of `items` passes, the tier is not lowered).
- Write `why` and each `why` in `groups` in {lang}. Keep keys, enum values, identifiers, paths, quoted text, and commands as they are.
````

`{"why": …}`・`{"item": …}`・`{"group": …}` は差し込み口の形（`{` の直後が小文字の名で `}` で閉じる）に合わないので、そのまま字として残る（world.md の 3.3 の注と同じ）。`"{none}"` などは差し込み口で、値の語が入る。

### 2.4 返す形

今の `output_format` のまま（`workflows/judge/works-factory-judge.yaml:75-97`）:

```yaml
type: object
additionalProperties: false
required: [why, items, groups]
properties:
  why: {type: string, minLength: 1, pattern: '\S'}
  groups:
    type: array
    items: {type: object, additionalProperties: false, required: [group, model, effort, why], properties: {group: {type: string, minLength: 1}, model: {type: string, minLength: 1}, effort: {type: string, minLength: 1}, why: {type: string, minLength: 1}}}
  items:
    type: array
    items:
      type: object
      additionalProperties: false
      required: [item, unknown, cause_quote]
      properties:
        item: {type: integer, minimum: 1}
        unknown: {type: string, enum: [無し, 原因, 形, 範囲]}
        cause_quote: {type: string, minLength: 1}
        where: {type: string, minLength: 3}
        code_quote: {type: string, minLength: 1}
```

`unknown` の enum は `src/steps.py` の `UNKNOWNS` の鍵と同じ並び（試験が結ぶ。7.2）。人に見せる欄は `why` と `groups[].why`（報告の「run の頭の深さ」の行と `## 模型` の節に載る）で、言語は `{lang}`。`cause_quote`・`code_quote` は写しなので訳さない。

### 2.5 描いた骨組み（例の run の値）

```markdown
You are the run-depth role, started in a new conversation. … The depth tier (軽量, 標準, or 重厚) is taken by the machine from the heaviest kind among the lines; …

What the tiers mean: a 軽量 run is only for a request where … when in doubt choose `原因` (which gives 標準).

You **only read**. …

## Input

- The target repository is the current working directory. …
- The material below was measured by the machine: …

1 request lines:

- Line 1: 出口の語 deliver=pr の run で PR 用の commit を積む時、commit のフックに渡す環境を作る hook_env は、…（約 380 字）
  - Location: workflows/merge/scripts/pr_commit.py の hook_env（73 行あたり） (file missing, line range outside or unreadable)

## Node groups and their default model and effort (in question 3, choose only the groups whose default you change)

Allowed models (weakest first): haiku, sonnet, opus
Allowed efforts (weakest first): low, medium, high, max

- `@wf-judge-materials`: 判定の素材集めと、読むだけで結論を返す判定の役 (default sonnet, medium)
- `@wf-judge-spec`: 判定の仕様の役 (default opus, medium)
- …（群 15 行）
- `@wf-test-gate`: 試験の関門の CI の役 (default sonnet, medium)

Whether a choice raises or lowers, it is only kept in the record. …

## Questions

1. … choose `無し` if you can show the place to fix …
2. There are four kinds.
   - `無し`: …
   - `原因`: …
   - `形`: …
   - `範囲`: …
…

## Output

Return only JSON of this shape.

（JSON の形の例）

- … at least 4 characters after removing whitespace. …
- `無し` lines: … The line range of `where` is at most 30 lines …
- …
- Write `why` and each `why` in `groups` in the language of the request lines. …
```

例の run の値: 依頼の行は 1 つで、番地は「…の hook_env（73 行あたり）」という字なので機械の測りは「ファイル 無い・行の範囲 外か読めない」になった（`depth-head-brief.md` の行と同じ）。役は `where` を `workflows/merge/scripts/pr_commit.py:73-76` と自分で引いて `無し` を返し、段は軽量になった（`depth-head.json`）。`lang` は空で、`{lang}` に既定の文が入った形。却下の段落は入らない。

### 2.6 今の指示との差

今の指示は `workflows/judge/commands/head-depth.md`（61 行）と、役に Read させる材料のファイル `depth-head-brief.md`（`lib/headdepth.py:105-110` の `brief` と、`lib/launchgroups.py:103-107` の `brief_section` が組む）の 2 か所に在る。

- 移した: 材料のファイルを Read させる行（md:21「材料: `$head-depth-prep.output.brief_file`（まず Read せよ）…」）をやめ、材料を指示の中に入れた。材料の題「# run の頭の深さの材料（機械が測った）」（`lib/headdepth.py:109`）は `## Input` の 1 文に、行の数の頭「依頼の行 N 個:」は md の 1 文と `{row_count}` に、群の節の見出し `SECTION_HEAD`（`lib/launchgroups.py:48`）と許す語の 2 行の札（:106）と記録だけの 1 文 `RECORD_ONLY`（:46-47）は md の決まった文にした。lib の Python に残るのは、行ごとの短い札（「Line n:」「Location:」「file exists/missing」）と群ごとの札（「default」）だけ（README の 5.3）。
- まとめた: 材料の 1 行「機械の確かめ（試験のコマンド）: 在る/無い」（`lib/headdepth.py:110`）は、役が起きる run では必ず「在る」（機械の止め `gate` が「無い」run で役を起こさない。`lib/headdepth.py:99`）ので、`## Input` の決まった 1 文「This run has machine checks (a test command).」にした。
- まとめた: md に字で書いていた lib の値を差し込み口にした。種類の 4 語（md:28-31・50・58-60）は `{none}` など、段の 3 語（md:13・15・40）は `{light}` など、引用の字数の下限 4（md:57-58。`cite.QUOTE_MIN`）は `{quote_min}`、範囲の上限 30（md:58。`WHERE_SPAN`）は `{where_span}`。今の試験 `test_prompt_states_the_lib_limits`（`tests/workflows/test_judge.py:942-946`）が字の一致を縛っていた物で、差し込み口にすれば縛りが要らない。
- 消した: 頭の拒みの節（md:3-9）と区切り（md:11）。共通の断片 `{shared:rejected}` の 1 回にした。末尾の言い回し「下の理由が空なら、これは 1 回目の返答で、拒まれていない」は、拒みが無い時は段落ごと入れない形にして要らなくした。決まりは今と同じ「丸ごと出し直せ」。
- 移した: 言語の 1 行（md:1。`rolekit.LANG_RULE` を `$head-depth-reject.output.lang_line` で入れていた物）を、`## Output` の最後の 1 文に。汎用の欄の並び（reason・how・what・why・異議…）は、この node の人に見せる欄（`why`・`groups` の `why`）の名指しに替えた。
- 消した: 記録だけの 1 文の括弧書き「（止めた版 a972888a は run の中で後のノードの模型を付け替えられず、子の run は親の模型の設定を受け継ぐ）」（`lib/launchgroups.py:47`）。役が知るべきなのは「効かない」ことだけで、訳の Archon の版の事実は持ち主の決め `head-choice-record-only` と `docs/polyfills.md` に在る。
- 消した: ほかの node の id（`$head-depth-reject.output.*`・`$head-depth-prep.output.brief_file`）。
- 並べ替えた: `## 入力` の 2 行（材料・対象のリポジトリ）を、対象のリポジトリ・材料の説明の順にし、材料の本文をその後に置いた。材料の説明の文（md:21 の「機械が測った物で、依頼の行ごとの番号・字・番地と…末尾に群のセクションが在り…」）は残した。
- 足した物は無い。2 つ目の commit で英語にした（#764）。役の名「run の頭の深さの役」は "the run-depth role"。1 つ目の commit（日本語）では、材料の札は今の字（「行 n:」「番地:」「ファイル 在る・行の範囲 ファイルの中」「既定 sonnet・medium」）のまま、2 つ目の commit で 3.2 の英語の札にする。

### 2.7 元の works と graphloops の同じ場面

元の works には、run の頭で AI が深さを選ぶ役が無い。入口の入力 `thickness`（`自動`・`軽量`・`標準`。`重厚` は受けない。`works/.shared/core/entry.py:549-553`）を人が名指し、単位ごとの深さを機械が修正案の項目の形から決めた（`works/darkfactory/lib/depth.py` の `unit_depth`・`decide_doc`）。graphloops も同じで、段（`thickness.tiers`）は依頼する人が `loop.py init --thickness` で名指し（誰が決めたかを `--decider` に残す）、走りの途中で `loop.py thicken` で上げるだけ（下げは拒む。`graphloops/scripts/loop.py:19`・`:161`）。

工場が足した物（どれも工場の git の履歴に記録が在る）:

- 軽い依頼の run の頭で深さを決める役（#517。`3e7287dd`）と、根拠の薄い軽量を受けない照らし（#547）。
- 3 段にして重厚を足す（#561。`9407b441`）。元の works が受けなかった `重厚` を工場は受ける。
- 段を依頼の行ごとの未知の種類で選ぶ（#627。`f7d6e81b`）と、`形` を重厚でなく標準に引く（#648。`ad88e48a`）。
- 群の模型と effort の選び（#628。`d0b086a2`）と、選びは上げも下げも記録だけ（#659。`398f3e5d`、持ち主の決め `head-choice-record-only`）。

工場に無い物・違う物:

- 人が名指した段の記録の欄（graphloops の `thickness_decider`）: 工場は欄を持たず、控えの `why` の字「入力 thickness の名指し（<段>）」で同じ事を言う。この block も同じ（足さない）。
- 走りの途中の段の上げ（graphloops の `thicken`・元の works の `raise_doc`）: 工場では line の修正の後の上げ直し（`lib/latedepth.py`）が持つ。この block の外（README の 1.2 の D）。

graphloops と元の works には、この役の受け付けに当たる物（引用が依頼とリポジトリに字のまま在るかを機械が照らし、照らせない行を軽くしない）が無い。この block はそれを残す。

### 2.8 受け付け

- 却下の決まり（`src/steps.py` の `check(reply, rows, repo)`。今の `lib/headdepth.py:148-170` と `_check_item`（:124-145）の写し。訳の字も今のまま）:
  - 返答が object でない → 「返答が object でない」。
  - `why` が空 → 「why が空」。
  - 依頼の行が無い → `NO_ROWS`「依頼の行が無い（行ごとの未知の種類を引けない）」。
  - `items` が依頼の行をちょうど 1 度ずつ指していない → 「items が依頼の行 N 個をちょうど 1 度ずつ指していない（指した行: […]）」。
  - 行ごと: `unknown` が 4 語のどれでもない、`cause_quote`（と照らす時は `code_quote`）が空白を除いて `cite.QUOTE_MIN` 字より短い、`cause_quote` が依頼のその行の字の部分でない、`where` が `cite.problem` に通らない、`無し` の行の範囲が `WHERE_SPAN`（30）行より広い、`code_quote` が `where` の字に無い。`無し` は範囲の幅を照らし、`形`・`範囲` は幅を問わない。`原因` は `where` を書いた時だけ `where` と `code_quote` を照らす。
- 受けた時（`src/steps.py` の `take`。今の `workflows/judge/scripts/head_depth_accept.py:36-44`）: `groups = launchgroups.choices(reply["groups"])` で群の選びを照らし、控えを `headdepth.record(tier_of(items), reply["why"].strip(), items=items, facts_doc=facts, groups=groups)` で書き直す。群の行の外れは拒みにせず、その行だけ既定に戻す（`launchgroups.choices` の振る舞い）。
- 拒んだ時（`refuse`。今の :29-33）: 控えを `headdepth.record(STANDARD, NOT_ACCEPTED.format(why=kept), facts_doc=facts)` で書き直す。`kept` は拒みの訳を `／` でつないだ物に、返答の `why` が在れば `／役の訳: <why>` を足した物。群は空（既定のまま）。
- 回数: `rolekit.accept_round(place, "head-depth", raw, take, reject=refuse)`。3 回目の拒み（`rolekit.GIVE_UP_AFTER`）で `done` が true になり loop を抜ける。run は止めない。
- 諦めた時に出口へ書く物: `finish` が `status: failed`、`reason` に `rolekit.given_up_reason(place, "head-depth")`（最後の拒みの文）、`tier` に控えの段（標準）、`why` に控えの `why`（拒みの訳と役の訳）を返す。

### 2.9 試験

7 節に全部を書いた。この node に当たる物: standalone の fixture（`standalone.stubs.yaml`・`gave-up.stubs.yaml`）・指示の比べ（7.3）・受け付けの振る舞いの試験（7.2 の `CheckCase`・`AcceptCase`）。守る keep-essence の番号は 7.4。

## 3 script の node

### 3.1 `intake.py`

1. `request`・`has_checks`・`thickness`・`spec`・`design_only`・`lang` を `os.environ.get("INPUTS_REQUEST")` などの字のままで読み、`ports.json(raw, "request.schema.json")`・`ports.flag(raw)`・`ports.choice(raw, ("自動", "軽量", "標準", "重厚"))`・`ports.text(raw)` に渡す（口の名は土台の PR の `ports.py` に合わせる。world.md の 4 節と同じ前提）。`thickness` が空の字なら `自動` と読む。
2. place の中のこの block のファイル（`src/` の定数が名を持つ物と `<node-id>-prompt-*.md`）を名で引いて消す。place そのものと、ほかの物は消さない（単独の run では place が run directory の根。README の 13 章）。
3. 依頼の行 `rows` は、値が配列ならそれ、object なら `findings` の欄。
4. `facts = steps.facts(rows, has_checks=…, spec=…, design_only=…, thickness=…, repo=Path.cwd())`。形は今の控えの `facts` と同じ鍵: `{"items": [{item, text, where, path_ok, lines_ok}], "test_cmd": has_checks, "spec": spec, "design_only": design_only, "forced": <thickness が 軽量・標準・重厚 ならその語、自動なら "">}`。`items` の作り方と `_place` は今の `lib/headdepth.py:74-90` のまま。
5. `go, tier, why = steps.gate(facts)`。今の `lib/headdepth.py:93-102` と同じ順: `forced` → `(False, forced, "入力 thickness の名指し（<forced>）")`、`spec` → `(False, 標準, "仕様の段を挟む run")`、`design_only` → `(False, 標準, "設計だけの run")`、行が無い → `(False, 標準, "依頼の行が無い（差分だけの run）")`、`test_cmd` が偽 → `(False, 標準, "機械の確かめが無い（tdd_suite も test_cmd も空）——代わりの最後のテストが測れない")`、どれでもない → `(True, "", "")`。
6. 控えを先に書く: `headdepth.record(tier or 標準, why or NO_REPLY, facts_doc=facts)` を `depth-head.json` に（今の `head_depth_prep.py:30`）。役が走らずに終わっても、控えが標準と訳で残る。
7. `intake.json` に `{facts, due: go, failed: false, reason: why, lang}` を書き、`{due: go, reason: why}` を返す。
8. 1〜7 のどこかで例外が出たら（読めない port・在らない pointer を含む）、落ちずに、控えを `headdepth.record(標準, "run の頭の深さの支度が落ちた（<型>: <訳>）")` で書き、`intake.json` に `failed: true` と同じ訳を書き、`{due: false, reason: <訳>}` を返す（今の `head_depth_prep.py:34-37`）。place を作れない時も返りだけは返す。

### 3.2 `depth_prep.py`

1. `with: reason`（`INPUTS_REASON`）を読む。`intake.json` を読む。
2. 値を組んで `prompt.render("head-depth", values, when)` を呼び、`{prompt}` を返す。`when = {"rejected": reason が空でない}`。
3. `values`（全部の差し込み口。5 節）:
   - `rejection`: `reason`（`rejected` が真の時の断片の中の口）。
   - `row_count`: `len(facts["items"])` の字。
   - `rows`: `steps.rows_text(facts)`。行ごとに 2 行。英語の形: `f"- Line {n}: {text}\n  - Location: {where or '(none)'} (file {'exists' if path_ok else 'missing'}, line range {'inside the file' if lines_ok else 'outside or unreadable'})"`。行を `\n` でつなぐ。
   - `groups`: `steps.groups_text()`。`launchgroups.GROUPS` の並びのまま、群ごとに `f"- `{name}`: {what} (default {model}, {effort})"`。`\n` でつなぐ。
   - `models`・`efforts`: `", ".join(launchgroups.MODELS)`・`", ".join(launchgroups.EFFORTS)`。
   - `none`・`cause`・`shape`・`scope`: `steps.NONE` など。
   - `light`・`standard`・`heavy`: `headdepth.LIGHT`・`headdepth.STANDARD`・`depth.HEAVY`。
   - `quote_min`: `str(cite.QUOTE_MIN)`。`where_span`: `str(steps.WHERE_SPAN)`。
   - `lang`: `intake.json` の `lang`。空なら土台の口が入れる既定の文（world と同じ。英語の "the language of the request lines"）。
4. 組んだ指示は `prompt.render` が place の `head-depth-prompt-<n>.md` に書く（README の 5.2）。

### 3.3 `depth_accept.py`

`INPUTS_REPLY` を読み、`intake.json` の `facts` と `facts.items` から依頼の行（`{text, where}` の並び）を組んで、2.8 の `rolekit.accept_round` を呼ぶ。返り `{ok, done, reason}`。`check` の `rows` 引数には `facts.items` を渡す（`text` の欄で `cause_quote` を照らす。今の `judge/request.json` の行と同じ字）。

### 3.4 `finish.py`

1. `intake.json` と、`headdepth.read_file(place / "depth-head.json")` の控えを読む（読めない・無い時は `read_file` が標準と `NO_RECORD` を返す）。
2. `status` を決める: `intake.json` の `failed` が真 → `failed`（`reason` は `intake.json` の `reason`）。`due` が真で控えの `items` が空 → `failed`（`reason` は `rolekit.given_up_reason(place, "head-depth")`、それが空なら控えの `why`。役が 3 回拒まれたか、役が走らず返答が受け付けに届かなかった）。ほかは `ok`（`reason` は空）。
3. 返り: `{ok: status == "ok", status, reason, tier: doc["depth"], why: doc["why"], rows: doc["items"], record: ports.pointer(place / "depth-head.json"), report: [report.report_line(doc["depth"], doc["why"])]}` を `ports.returns` で返す。
4. どこで例外が出ても落ちず、`{ok: false, status: failed, reason: "<型>: <訳>", tier: 標準, why: <同じ訳>, rows: [], record: <控えを標準で書き直した pointer>, report: [同じ形の 1 行]}` を返す。

`finish` の `output_format`:

```yaml
type: object
additionalProperties: false
required: [ok, status, reason, tier, why, rows, record, report]
properties:
  ok: {type: boolean}
  status: {type: string, enum: [ok, failed]}
  reason: {type: string}
  tier: {type: string, enum: [軽量, 標準, 重厚]}
  why: {type: string}
  rows:
    type: array
    items:
      type: object
      additionalProperties: false
      required: [item, unknown, cause_quote]
      properties:
        item: {type: integer, minimum: 1}
        unknown: {type: string, enum: [無し, 原因, 形, 範囲]}
        cause_quote: {type: string}
        where: {type: string}
        code_quote: {type: string}
  record:
    type: object
    additionalProperties: false
    required: [type, run_id, path]
    properties:
      type: {type: string, enum: [archon_artifact]}
      run_id: {type: string}
      path: {type: string}
  report: {type: array, items: {type: string}}
```

`intake` の返り `{due: boolean, reason: string}`・`depth_prep` の返り `{prompt: string}`・`depth_accept` の返り `{ok: boolean, done: boolean, reason: string}` は、どれも `additionalProperties: false` で全部の欄を `required` にする。

## 4 作るファイルと触るファイル

作る:

- `blocks/head-depth/works-factory-head-depth.yaml`
- `blocks/head-depth/prompts/head-depth.md`
- `blocks/head-depth/scripts/intake.py`・`depth_prep.py`・`depth_accept.py`・`finish.py`（どれも uv の頭の宣言 `# /// script` を持つ）
- `blocks/head-depth/src/__init__.py`・`src/steps.py`・`src/report.py`
- `blocks/head-depth/schemas/request.schema.json`
- `blocks/head-depth/fixtures/standalone.stubs.yaml`・`gate.stubs.yaml`・`gave-up.stubs.yaml`
- `tests/blocks/head_depth/__init__.py`・`test_head_depth.py`・`test_fixtures.py`・`test_prompt_compare.py`（1 つ目の commit だけ。2 つ目の commit で消す）
- `docs/design/head-depth.md`（この文書。直す時）

触らない: `lib/`（読むだけ）・`workflows/`・ほかの block。共通の断片 `blocks/.shared/prompts/rejected.md` は土台の PR が置く物を使う。`unknown-asks.md` はこの block では作らない（読み手の diagnose か plan の PR が、最初に要った方で足す。1.6）。

`tests/blocks/head-depth/` でなく `tests/blocks/head_depth/` にするのは、Python の package の名に `-` を使えず、unittest が見つけないため（8 節の自分で決めた 1）。

`schemas/request.schema.json` の中身（world の物と同じ中身の写し）:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "row": {
      "type": "object",
      "required": ["where", "text"],
      "additionalProperties": false,
      "properties": {
        "where": {"type": "string"},
        "text": {"type": "string"},
        "mechanism": {"type": "string"},
        "measured": {"type": "string"},
        "false_positive_if": {"type": "string"}
      }
    }
  },
  "oneOf": [
    {"type": "array", "items": {"$ref": "#/$defs/row"}},
    {
      "type": "object",
      "required": ["findings"],
      "additionalProperties": false,
      "properties": {
        "findings": {"type": "array", "items": {"$ref": "#/$defs/row"}},
        "pr": {}, "issue": {}, "answers": {}, "prior_failures": {}, "constraints": {}
      }
    }
  ]
}
```

行の欄の型は今の `lib/judge_accept.py:376-382` の `REQUEST_SCHEMA` の `findings` の行と同じ。容器の鍵は今の `lib/carry.py` の `parts` が許す 6 つ。

## 5 差し込み口の一覧（`prompts/head-depth.md`）

| 口 | 値の出どころ |
|---|---|
| `rejection` | prep の `with: reason`（前の回の accept の `reason`） |
| `light`・`standard` | `lib/headdepth.py` の `LIGHT`・`STANDARD` |
| `heavy` | `lib/depth.py` の `HEAVY`（組み込みの後は `lib/headdepth`） |
| `none`・`cause`・`shape`・`scope` | `src/steps.py` の `NONE`・`CAUSE`・`SHAPE`・`SCOPE` |
| `row_count` | `intake.json` の `facts.items` の数 |
| `rows` | `src/steps.py` の `rows_text(facts)` |
| `models`・`efforts` | `lib/launchgroups.py` の `MODELS`・`EFFORTS` |
| `groups` | `src/steps.py` の `groups_text()`（`launchgroups.GROUPS`） |
| `quote_min` | `lib/cite.py` の `QUOTE_MIN` |
| `where_span` | `src/steps.py` の `WHERE_SPAN` |
| `lang` | port `lang`（空なら土台の既定の文） |

選ぶ段落の名: `rejected`（前の回の理由が空でない）。

## 6 単独で呼ぶ

```sh
bin/works-factory <読ませるフォルダを blocks/ にする引数（名は土台の PR で決める）> workflow run works-factory-head-depth \
  --input request='[{"where":"stats.py:4","text":"mean は 2 でなく 3 を返す"}]' \
  --input has_checks=true
```

出力は `workflow get <run>` の `finish` の返り。始めの記録は要らない。`has_checks` を渡さないと既定の false で、役を起こさず標準が返る（機械の止め）。

## 7 試験と、済んだと言える条件

### 7.1 standalone の fixture（`blocks/head-depth/fixtures/`）

- `standalone.stubs.yaml`: `fixture.inputs` は `request: '[{"where": "stats.py:4-5", "text": "mean は 2 でなく 3 を返す"}]'`・`has_checks: 'true'` だけ。`expect: completed`・`reached: [intake, head-depth-prep, head-depth-accept, finish]`。stub は `intake: {due: true, reason: ''}`・`head-depth-prep: {prompt: 筋書きの指示}`・`head-depth: {why: 筋書きの役は原因が残る行を返す, items: [{item: 1, unknown: 原因, cause_quote: mean は 2 でなく 3 を返す}], groups: []}`・`head-depth-accept: {ok: true, done: true, reason: ''}`・`finish: {ok: true, status: ok, reason: '', tier: 標準, why: 筋書きの役は原因が残る行を返す, rows: [{item: 1, unknown: 原因, cause_quote: mean は 2 でなく 3 を返す}], record: {type: archon_artifact, run_id: fixture-run, path: depth-head.json}, report: ['run の頭の深さ: 標準（根拠: 筋書きの役は原因が残る行を返す）']}`。
- `gate.stubs.yaml`: `fixture.inputs` は `request`（同じ 1 行）・`thickness: 標準`。`reached: [intake, finish]`。`intake: {due: false, reason: 入力 thickness の名指し（標準）}`、loop は `when:` で飛ぶ。
- `gave-up.stubs.yaml`: 入力は standalone と同じ。`head-depth-accept: {ok: false, done: true, reason: 行 1: cause_quote が依頼のその行の字の部分でない}`・`finish: {ok: false, status: failed, …, tier: 標準}`。`expect: completed`（run は止まらない）。

### 7.2 `tests/blocks/head_depth/test_head_depth.py`

script を子のプロセスで回す（今の `tests/workflows/test_judge.py:695-704` の `Run.run` と同じ形: `subprocess.run([sys.executable, <script>], cwd=<使い捨ての git のリポジトリ>, env=hermetic.child_env(ARTIFACTS_DIR=…, WORKFLOW_ID=…, WORKS_FACTORY_ROOT=…, PYTHONDONTWRITEBYTECODE="1", INPUTS_…=…))`）。始めの記録は置かない。リポジトリには `stats.py`（5 行。4-5 行目に `return sum(xs) / (len(xs) - 1)`）を commit して置く。

- `GateCase`（元: `lib/tests/test_headdepth.py::GateTest` と `tests/workflows/test_judge.py::HeadDepthTest.test_prep_stops_without_waking_the_role`・`test_prep_writes_the_brief_and_a_standard_record`）: `has_checks` false・`thickness` 標準・`thickness` 重厚・`spec` true・`design_only` true・依頼が `[]` のそれぞれで、`intake` が `due: false` を返し、控えの `depth` が名指しの段か標準で、`facts` が今と同じ鍵を持つ。何も止めない時は `due: true` で、控えが標準と `NO_REPLY` の訳。`facts` の `path_ok`・`lines_ok` が番地の実在どおり。
- `PromptCase`: `depth_prep` の返りの `prompt` に、行の札（`- Line 1:`）・群の 15 行・`haiku, sonnet, opus` が在り、`{` で始まる埋まらない差し込み口が無い。`with: reason` が空でない時だけ却下の段落が入る。
- `CheckCase`（元: `lib/tests/test_headdepth.py::CheckTest` の全部）: 引用の通った `無し`・`範囲` が通る、標準は訳だけで足りる、外れた引用を拒む、引用の字数の下限の訳、範囲の上限ちょうどは通る、依頼の行の無い軽量を拒む、段は一番重い種類、種類ごとの照らしの決まり、標準の行も照らす、`原因` の `where` を照らす。`src.steps` を直に import して呼んでよい（block の中の試験なので）。
- `AcceptCase`（元: `tests/workflows/test_judge.py::HeadDepthTest` の `test_accept_takes_a_quoted_light_reply`・`test_accept_refuses_a_quote_the_code_lacks_and_keeps_standard`・`test_accept_records_the_tier_and_row_kinds`・`test_accept_records_group_choices_without_changing_the_tier`・`test_refused_reply_keeps_the_role_why`）: `intake` → `depth_accept` を子で回し、控えの段・`items`・`groups`・拒んだ時の `why`（`NOT_ACCEPTED` の頭・拒みの訳・`役の訳: …`）を照らす。
- `FinishCase`（元: `test_verdict_returns_the_recorded_depth`・`test_verdict_without_record_is_standard`）: 受けた時は `status: ok` と控えの段と `rows`、3 回拒まれた時は `status: failed` と標準と最後の拒みの文、機械の止めの時は `status: ok` と止めの段、`intake` が落ちた時は `status: failed`。どれも `record` の先が `headdepth.read_file` で読め、`report` が 1 行。
- `ShapeCase`（元: `test_role_kinds_are_the_lib_kinds`・`test_depth_words_are_the_lib_words`）: YAML の `head-depth` の `output_format` の `unknown` の enum が `list(steps.UNKNOWNS)`、`finish` の `tier` の enum が `list(depth.HEADS)`、`output_format` に段の欄が無い、`required` が `[why, items, groups]`、loop の `max_iterations` が `rolekit.GIVE_UP_AFTER`。AI の node の鍵（モデルの群・`settingSources`・道具・sandbox・`idle_timeout`・`mutates_checkout`・`retry`）が 1.3 のとおり（元: `test_roles_keep_the_old_settings` の head-depth の行）。
- 写さない試験: `lib/tests/test_headdepth.py::SectionTest`（`section` は読み手の block の試験へ）・`RecordTest`（KEEP の lib の試験として残る）・`ReportLineTest`（`groups_lines` は lib に残り、`report_line` の後半は line へ）・`tests/workflows/test_judge.py::HeadDepthTest.test_heavy_record_does_not_cut_the_verify`・`test_verify_waits_on_the_head_depth`（verify と judge のまとめの試験へ）・`test_prompt_states_the_lib_limits`（差し込み口で要らない）・`test_unreadable_start_pointer_degrades_in_every_lang_line_script`（始めの記録を読まない）。

### 7.3 指示の比べ（README の 11.4）

- 1 つ目の commit: md を日本語のまま置く。中身は、今の md の並びのまま、今の md の字（`$…` を `{name}` に替えた物）と今の材料の字を写した物（材料の行は `{rows}`、群の行は `{groups}`、許す語は `{models}`・`{efforts}` を `・` でつないだ値、「機械の確かめ（試験のコマンド）: 在る」は決まった字）。節の並べ替え（2.6 の「並べ替えた」）は 2 つ目の commit で行う。`tests/blocks/head_depth/test_prompt_compare.py` が、例の run の値（`depth-head.json` の `facts` と同じ `facts`、拒みなし、`lang` 空）で `depth_prep` を回して組んだ指示と、次の手で組んだ「今の指示」を、空白と改行の違いを除いて同じ字か照らす:
  1. `workflows/judge/commands/head-depth.md` の字から、1 行目（言語の 1 行）と 3〜11 行目（拒みの節と区切り）を除く。
  2. 21 行目（材料を Read させる行）を、`lib/headdepth.py` の `brief(facts)` の字から 1 行目の題を除いた物に替える。
  3. `## 出力` の最後に、新しい言語の 1 文（日本語の md に置いた字）を足す。
- 2 つ目の commit: md を英語にし、`test_prompt_compare.py` を消す。今の指示（上の手の 1〜3 の前の、今の md と材料のファイルをそのまま並べた物）と新しい指示を同じ値で組んで並べた物を PR の本文に載せ、2.6 の差の一覧どおりかを審査が見る。

### 7.4 keep-essence の番号

12 の仕組みのどれも、この block が直に担う物ではない（README の 10 節）。間に関わるのは 9（独立の目 R1〜R4）: 軽量の run は R1〜R4 と差分の審査を省く（持ち主の決め `dynamic-depth`）ので、引用で示せない行を軽量にしない受け付けが、R1〜R4 を黙って省かせない守りになる。守るのは 7.2 の `CheckCase`（照らせない引用を拒む・迷ったら標準）と `FinishCase`（拒まれたら標準）。e2e の照らしの表 `tests/e2e/evidence.json` には、この block の place のファイルを直に見る行が無い（`L-W51`・`L-D13`・`R74` は line の深さの行で、line の設計書が直す）。

### 7.5 済んだと言える条件（PR ごと。README の 11.2）

```sh
uv run --isolated python3 -m unittest tests.blocks.head_depth.test_head_depth
uv run --isolated python3 -m unittest tests.blocks.head_depth.test_fixtures        # archon workflow test（源と bun が無ければ見送る）
uv run --isolated python3 -m unittest tests.blocks.head_depth.test_prompt_compare  # 1 つ目の commit だけ
uv run --isolated python3 -m unittest tests.layers.test_block_shape
uv run --isolated python3 tests/changed.py
```

`test_fixtures.py` は、`tests/archon.py` の使い捨ての木に `blocks/` を pack として置く口（土台の PR が足す）で `archon workflow test works-factory-head-depth --json` を回し、3 本の筋書きが全部通ることと、`archon validate workflows` が警告なしで通ることを照らす。最後に、6 節の命令で本物の単独の run を 1 回回す（費用のかかる試しは聞かずに回してよい）。

## 8 根拠を書いて自分で決めた事

1. 試験のフォルダを `tests/blocks/head_depth/` にした。根拠: Python の package の名に `-` は使えず、unittest の discover が見つけない（`tests/AGENTS.md` の「`__init__.py` が無いと黙って見つけない」と同じ種類の黙った漏れ）。README の 3 節は `tests/blocks/<block>/` と書くので、`-` を `_` に替える決まりを README に足すのがよい。
2. 材料のファイル（`depth-head-brief.md`）を Read させる形をやめ、材料を指示の中に入れた。根拠: 材料の題と群の節の見出しと記録だけの 1 文は lib の Python が持つ決まった文で、憲法の 2（Python は指示の文を持たない）に当たる。README の 5.2 は `prompt:` に指示を直に入れる形を決めていて、world も材料を指示に入れている。役の道具（Read）はリポジトリを読むために残る。
3. 報告の行を、段と根拠（この block）と、省く物・足した物（line）に割った。根拠: 「省く物・足した物」は段 → 回す物の表（`lib/depth.py` の `TIERS`。line へ MOVE）から引く字で、この block は表を持たない（README の 1.2 の D）。報告の文は事実を持つ block が組む（README の 4.1）ので、段の表の事実は line が組む。群の選びの行（`## 模型` の節）も、ノードごとの実際の模型の事実と並ぶ節なので、line（か report）が `record` の pointer から `headdepth.groups_lines`（KEEP）で組む。
4. 種類ごとの指示の文（`lib/headdepth.py:210-216` の `ASKS`）は、読み手 2 つ（diagnose・plan）の md が使う共通の断片 `blocks/.shared/prompts/unknown-asks.md` に移す。この block は種類の語と行（`rows`）を出力で渡すだけにする。根拠: `ASKS` は受け手の役に向けた指示の文で、憲法の 2 で md へ出す。読み手が 2 つの block なので README の 5.1 の決まりで `blocks/.shared/prompts/` に置く。断片は、最初に要った PR（diagnose か plan）が足す（README の 11.1 の並べ方）。
5. 却下の段落に入れる理由は、今と同じく前の回の 1 つだけ（prep の `with: reason`）にした。world は控えの拒みを古い順に全部入れる（#351）が、この役は今まで前の回の理由だけで、`fresh_context: false` の同じ会話の中なので前の理由は会話に残っている。振る舞いを変えない。
6. `has_checks` の既定を `false` にした。根拠: 渡し忘れた時に役を起こさず標準に倒れる（誤って軽量にする害は大きく、誤って標準にする害は費用だけ。役の md の段の意味の文と同じ向き）。
7. `ok` は「段が設計どおりに決まったか」にし、役が 3 回拒まれた・走らなかった時は `false` にした。graph はこの欄で止めない（今も深さは判定を止めない）。根拠: Archon の `outcome_field` は単独の run の成否（true → succeeded・false → failed）を決めるだけで、include の先へは伝わらない（`A/.archon/workflow-language-constitution.md:90`）。単独で回した人には、標準に倒れた訳が失敗として見える方がよい。

## 9 README へ返す問題

下の 7 つは README に当てた（3 節・5.3・6 節の 9・7.1 の 10・8.1・9.2・9.3・11.2・11.3・13 章）。

1. 段の語の住処: README の 9.3 は `headdepth` の KEEP を「段の語と控えの読み」と書くが、段の語は今 `lib/depth.py:58-60`（`LIGHT`・`STANDARD`・`HEAVY`）と `:91`（`HEADS`）に在り、`lib/headdepth.py` は `LIGHT`・`STANDARD` だけを写している。`depth` は line へ MOVE（9.2）なので、組み込みで段の語 4 つを `lib/headdepth` へ移す手を 11.3 に書く必要がある。この block は作り直しの間 `lib/depth.py` の `HEAVY`・`HEADS` を読む。
2. 報告の「run の頭の深さ」の 1 行（`headdepth.report_line`）は、段と根拠（head-depth）と省く物・足した物（line の表）にまたがる。README の 8.1 と 4.1 はどちらが組むかを書いていない。この設計書は 8 節の 3 で割った。
3. 種類ごとの指示の文 `ASKS` の行き先が README の 9 節に無い（`headdepth` の KEEP にも、head-depth の MOVE にも書かれていない）。この設計書は 8 節の 4 で共通の断片にした。
4. `tests/blocks/<block>/` に `-` を含む block の名（head-depth・plan-review・delta-review など）がそのまま使えない（8 節の 1）。
5. 依頼の port の形 `request.schema.json` は world・purpose・premises・head-depth・spec・parallel-pr・diagnose の 7 つの block が同じ中身を持つことになる。7.1 の 5 は schema を block の `schemas/` に置けと縛るので、写しが 7 つになる。2 つ以上の block が使う物は 1 か所という憲法の 4 と合わない。`blocks/.shared/schemas/` を許すか、写しの一致を試験で縛るかを README で決めるのがよい。
6. 人に見せる欄の言語の既定の英語の文（README の 5.3）の住処が決まっていない（world.md にも無い）。全部の block が使うので、土台の `prompt.py` か `ports.py` の 1 か所に置く必要がある。
7. README の 6 節の 9 と 11.2 が「指示の比べ（10.3）」を指すが、指示の比べは 11.4 に在る。

## 10 未確認

- 起動の殻で `blocks/` を読ませる引数の名と、6 節の命令の正確な形（world.md と同じ）。
- `ports.py` の口の名（`json`・`flag`・`choice`・`text`・`pointer`・`returns`・`place`）。土台の PR の名に合わせる。
- `archon workflow test` の筋書きで、`when:` で飛んだ loop の後の `trigger_rule: all_done` の `finish` が `reached` に入るか（今の judge の筋書きは同じ形で通っている）。
