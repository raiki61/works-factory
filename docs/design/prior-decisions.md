# block の設計書: prior-decisions（先行議論の突合）

- 何の話か: 対象差分が触れる領域（差分が空なら依頼が指す場所）の決定記録を洗い、決着済みの論点を集める素材の観点「先行議論の突合」を、単独で呼べる block `blocks/prior-decisions/` にする設計。素材の観点の族の 1 本目で、族の共通の形は [materials.md](materials.md) に従う。型は [README.md](README.md)、手本は [world.md](world.md)。
- 決めたこと: 今の judge の `material-route` の 1 列と `prior-decisions-loop`（prep・役・accept の 3 つの node）を、5 つの node（intake・prep・役・accept・finish）の block にする。入力は差分の根・依頼の行・判定から入る run の出どころ・言語の 4 つの port だけで、run の記録を読まない。指示は 1 本の英語の md（`prompts/prior-decisions.md`）にし、今は別のファイル（`material-prior-decisions-brief.md`）に描いて役に Read させた材料を、指示の中に直に入れる。決着済みの論点の行（`settled`）は今と同じ形で `material.json` に残り、記録された方針の読み手（`policy.recorded`）が今の読み方のまま読む。振る舞いは変えない。
- 持ち主に求めること: なし。
- 読む人と使い方: この block を作る実装者（1〜3 節の名と順をそのまま作る）と、残りの 10 本の観点の設計書の書き手（写す手本）。素材の観点の族の共通の部品と同じ PR に入る（README の 11.1 の 1 波目）。

この文書の語は README と materials.md の頭の物を使う（line・始めの記録・今・周は materials.md の頭）。ほかに:

- 所見の場所: 返答の中の、`where`（字）と `text`（字）を両方持つ行の `where` に書いた `<パス>:<行>`（`materialkit.where_rows` が拾う物）。この役の返答では `settled` の行は `text` を持たないので当たらない。今の受け付けの照らしと同じ（`lib/judge_accept.py:2463-2487`）。

- 突合の役（prior-decisions）: 決定記録（ADR・意図的保留の台帳・issue や PR の棄却済み一覧・closed issue）を洗い、決着済みの論点を返す AI の役。道具は Read・Grep・Glob・Bash・WebSearch・WebFetch。Bash は網の閉じた sandbox の中で走る。
- 決着済みの論点: 返答の `settled` の 1 行 `{topic, decision, reason, revisit, where}`。後の役（判定・修正案・事前審査・修正・R3・R4）に「記録された方針」の行として渡り、`where` がその行の名指しになる（`lib/policy.py:186-208`）。
- 例の run: 本物の run `df5e111f-ea97-409b-8066-2245d32746ab`（対象 raiki61/works-factory。置き場 `~/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/artifacts/runs/df5e111f-…/judge/`）。判定から入る run で、差分は空、依頼の行は 1 件。突合の役は 1 回目で受け付けを通った（`material-prior-decisions.json` の `materials.prior_decisions.status` が `found`、`settled` が 3 行）。骨組みの値はここから取った。world.md と同じ run。

## 1 block の全体

### 1.1 役

対象差分が触れる領域の決定記録を洗い、決着済みの論点（決定・理由・再訪の条件・書いてある所）の一覧と、見た範囲・見ていない範囲を返す。差分が空の判定から入る run では、依頼が指す場所の決定記録を洗う。洗えなかった時は「決着済みなし」と書かせず、人待ちの状態と訳を書かせる。機械が、作業ツリーを変えていないか・所見の場所がファイルに在るか・素材の欄が決まりに合うかで受け付ける。

### 1.2 port

入力（YAML の `inputs:`）:

- `base`: `text: 対象差分の根の commit（対象差分は、この commit から作業ツリーの今の姿まで。未追跡の新しいファイルも入る）。空は HEAD`。既定 `""`。
- `request`: `json(request.schema.json): 依頼の行の配列 [{where, text, mechanism?, measured?, false_positive_if?}]。それを findings の欄に持つオブジェクトでもよい（工場の依頼のファイルの形）。空の配列は依頼の行が無い`。既定 `[]`。
- `entry`: `text: 判定から入る run の出どころの文（例「人の依頼（/path/req.json）」）。空は判定から入る run でない`。既定 `""`。
- `lang`: `text: 人に見せる欄（material の detail・checked・reason、searched、settled の topic・decision・reason・revisit）の言語。空は依頼の言語`。既定 `""`。

README の 8.1 の例は「prior-decisions は request・purpose」と書くが、`purpose` は持たない（自分で決めた。7 節）。

出力（`returns: finish`、`outcome_field: ok`）: materials.md の 1.2 の 5 欄（`ok`・`status`・`reason`・`material`・`report`）だけ。`material.json` の `reply` は受けた返答（`checked`・`searched`・`settled`・`material`）、`materials` は `{"prior_decisions": <返答の material>}`。

今との違い: 今は入力を `judge/start.json`（差分の根・入口の印）・`judge/request.json`（依頼の行）・`judge/stop.json` から名で開き（`lib/judge_accept.py:1882-1919`・`:1958-1962`）、受けた返答を `judge/material-prior-decisions.json` に書き、判定の出力の欄 `decisions` がそのパスを外へ出していた（`lib/judge_accept.py:3884` の `FIRST_PORTS`）。回すかは `material-route` が決めた（1 run = 1 周ではいつも回す）。

### 1.3 node の並び（`blocks/prior-decisions/works-factory-prior-decisions.yaml`）

materials.md の 1.3 の雛形の `<観点>` を `prior-decisions` にした物。

1. `intake`（script `intake.py`）: port を読み、対象差分を取り、回すかを決め（いつも回す）、作業ツリーを写す。返り `{due, reason}`。
2. `prior-decisions-loop`（`loop_group`、最大 3 回、`fresh_context: false`、`until_bash: done=$prior-decisions-accept.output.done; test "$done" = true`、`when: $intake.output.due == true`）
   - `prior-decisions-prep`（script `role_prep.py`）: 指示を組む。返り `{prompt}`。
   - `prior-decisions`（AI）。`prompt: "$prior-decisions-prep.output.prompt"`・`depends_on: [prior-decisions-prep]`。起こし方は今の `net_closed_launch`（`workflows/judge/works-factory-judge.yaml:464-480`）を字のまま展開する: `model: '@wf-judge-materials'`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob, Bash, WebSearch, WebFetch]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false, failIfUnavailable: true, excludedCommands: ['works-gh:*'], network: {allowedDomains: []}, filesystem: {denyWrite: ['~/../archon-home']}}`（今の注記 3 行も写す）・`idle_timeout: 1728000000`。`retry: {max_attempts: 2, on_error: all}`。`mutates_checkout:` は今と同じく置かない。`output_format` は今のまま（2.4）。
   - `prior-decisions-accept`（script `role_accept.py`。`with: {reply: $prior-decisions.output}`）: 返り `{ok, done, reason}`。
3. `finish`（script `finish.py`。`depends_on: [intake, prior-decisions-loop]`・`trigger_rule: all_done`）: `material.json` を書き、出力を返す。どの段が落ちても落ちない。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、判定のまとめから include された時は `$ARTIFACTS_DIR/<judge の include の id>/prior-decisions/`）の下に、materials.md の 1.4 の名で書く: `intake.json`・`view.json`・`diff.patch`・`changed-files.txt`・`tree.json`・`prior-decisions-prompt-<n>.md`・`rejects-prior-decisions.json`・`rejects-prior-decisions.md`・`accepted.json`・`material.json`。

指示の比べの 1 つ目の commit（`d05a8711`）だけ、今の材料のファイルと同じ字の `material-prior-decisions-brief.md` も書いた（2.9）。今の形では書かない。

### 1.5 コードの置き場

- `blocks/prior-decisions/src/__init__.py`（空）。
- `blocks/prior-decisions/src/viewpoint.py`: materials.md の 5.1 の宣言。中身:
  - `NAME = "prior-decisions"`
  - `MATERIALS = ("prior_decisions",)`
  - `GUARDED = False`（AI の node が `mutates_checkout: false` を持たない。今の accept の `with: {status_guarded: false}`。`workflows/judge/works-factory-judge.yaml:973`）
  - `NA = "never"`、`NA_REASON = ""`、`NA_PARAGRAPH = True`（返答が `material` を持ち、md が `material-na` を差し込む。今の `MATERIAL_NODES['p0.prior_decisions']` が `applies_cond` を持たず `na_self_ok: False`。`lib/judge_accept.py:1633-1641`）
  - `due(view, values)`: `materialkit.Due(True, "先行議論の突合は run ごとに 1 回回す（1 run は 1 周で、いつも初回）")`。今の `prior_decisions_due`（`:1588-1594`）は 1 周目にいつも真で、ほかの枝（前の周の修正・昇格）は 1 run = 1 周で効かない。
  - `fill(view, values, due)`: `raise NotImplementedError`（`due` がいつも真なので呼ばれない）。materials.md の 5.1 の「全部の名を定義する」を守り、呼ばれないことを試験が見る。
  - `applies(view, values)`: `raise NotImplementedError`。
  - `judged_na(view, values)`: `return False`。
  - `values(view, values)`: `{"repo": str(view.repo), "base": view.base, "changed_files": dump(list(view.changed_files)), "request_wheres": dump(request_wheres(view, values))}`。`dump` は `json.dumps(x, ensure_ascii=False, indent=1)`（materials.md の 3.3）。
  - `request_wheres(view, values) -> list[str]`: 判定から入る run の周（`materialkit.is_entry_run`: `values["entry"]` が在り、`view.empty`）でなければ `[]`。その周なら、依頼の行のうち `where` が字の物の `where` を順に並べた物（今の `request_wheres`、`:1913-1918`。今も入口の印〔差分が空で依頼が在る〕の周だけ）。依頼の行は `values["request"]`（`requestrows.findings` が読んだ配列）。
  - `when(view, values)`: `{"spawns": False}`（外への検索の決まりの断片の段落。この役は Agent の道具を持たない）。
  - `before(view, values, reply, place)`: `return None, reply, False`。
  - `after(view, values, reply, place)`: `return None`。
  - `after_accept(reply, place)`: 何もしない。
  - `materials_of(reply)`: `{"prior_decisions": reply["material"]} if isinstance(reply.get("material"), dict) else {}`（今の `writes` の `materials.prior_decisions ← material`。`:1636`）。無ければ空にし、`check_record` が「素材 'prior_decisions' が返答に無い」で拒む。
  - `report_lines(doc)`: `settled` の行ごとに `f"  - 決着済みの論点: {oneline(topic)}（{where か「書いてある所の記録が無い」}）"`。`reply` が null なら `[]`。行は字下げ 2 つで始め、materials.md の 2.10 の素材の 1 行の下に並ぶ形にする。
- 1 つ目の commit（`d05a8711`）だけ `src/oldbrief.py`（今の材料のファイルを同じ字で組む）を置き、2 つ目の commit で消した（2.9）。
- `schemas/` は置かない。`request` の形は土台の共通の形 `blocks/.shared/schemas/request.schema.json`（`json(shared:request.schema.json)`）で、読む口は `requestrows.findings`。
- 使う `lib/`: `materialkit`（族の部品の全部）・`rolekit`・`oneline`。決着済みの論点の行を読むのは `policy`（読み手の側。この block は import しない）。

### 1.6 つなぎ方（graph の側。block には書かない）

- 判定のまとめ（`blocks/judge/`）: `include: works-factory-prior-decisions`、`depends_on` は materials.md の 1.6。`with:` は `base: <line が始めの記録から引いた diff_base>`・`request: <依頼の pointer>`（world の `request` と同じ物）・`entry: <line が始めの記録から引いた出どころの文。判定から入る run でなければ空>`・`lang: <始めの記録の lang>`。
- 読み手:
  - diagnose の `materials`（11 本の `material` の配列の 1 つ）。
  - 記録された方針の読み手（今の判定の出力の欄 `decisions` を受けていた全部: diagnose の判定の材料と受け付け〔`lib/judge_accept.py:799-801`・`:2824`〕・plan・plan-review・fix・r3・r4）。判定のまとめが `$prior-decisions.output.material`（`material.json` を指す Archon の pointer。中身ではない）を返りの欄 `decisions` にして line へ返し、line が今と同じ配線で配る。読み手は `policy.recorded(start, decisions_file)` に、その pointer を開いたパスを渡す。`policy._settled_rows` は `doc["reply"]["settled"]` を読むので、`material.json` の形（`reply` の欄）のまま読める。
- 今の「run で 1 回」は、判定のまとめがこの block を 1 回だけ include し、再審の道（diagnose の `objection`）がこの block を通らないことで続く。

## 2 node の設計シート: prior-decisions（突合の役）

### 2.1 役

対象差分が触れる領域（差分が空なら依頼が指す場所）の決定記録を洗い、決着済みの論点の一覧と、見た範囲・見ていない範囲・素材の状態を返す。

### 2.2 port

`intake.json` の `view`（← port `base` と作業ツリー。`repo`・`base`・`changed_files`）・`values.request` と `values.entry`（← port `request`・`entry`。依頼が指す場所）・`values.lang`（← port `lang`）、拒否の控え（← accept が place に積んだ物）。

### 2.3 組み立ての順（`prompts/prior-decisions.md`）

materials.md の 3.1 の並び。

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: `rejects-prior-decisions.json` に拒否が 1 件以上。断片の中の `{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "prior-decisions"))`（拒否の文の全部、古い順。Python が組む日本語の文。4 節）。
2. `{shared:role-investigator}`（役の定義。決まった文）。
3. （置かない。7 節）外への検索の決まりは 2 の `{shared:role-investigator}` の中に `{shared:query-rule}` で入る。その断片の中の `<!-- if spawns -->` には `spawns: false`。
4. 役の 1 段落（決まった文）: 新しい会話で起きていること・突合だけをすること・局所の所見もほかの素材も渡していないこと。
5. 道具の段落（決まった文）、`{shared:works-gh}`、`{shared:material-readonly}`。
6. `## Materials` と 4 つの差し込み口: `{repo}` ← `view.repo`（作業ツリーの絶対パス）、`{base}` ← `view.base`（引いた commit）、`{changed_files}` ← `view.changed_files`（JSON の配列の字）、`{request_wheres}` ← `request_wheres(values)`（JSON の配列の字）。
7. `## What to do`（決まった文）: 今の graphloops の指示の段（`material-prior-decisions.md:42-48`）を英語にした物。
8. `{shared:material-status}`。
9. `## Whether you may write not_applicable` と `{shared:material-na}` — 扱いは `never`（`na_never` だけが真。`{na_why}` には空の字を渡す。選ばれない段落の中の口も値が要る。materials.md の 2.11）。
10. `## Where to point` と `{shared:material-where}`。
11. 言語の 1 文と `{lang}` ← `prompt.lang(port lang)`（空なら共通の断片 `lang-default` の文）。
12. 結びの 1 文。

md の本文（英語。この block の 2 つ目の commit でこのまま置く）:

```markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{shared:role-investigator}

You are the prior-decisions role. Your only job is to check the target against earlier decisions. You are given neither the local findings nor any other material.

Your tools are Read, Grep, Glob, Bash, WebSearch, and WebFetch. Bash runs inside a sandbox, and its network is closed: it cannot reach any destination.

{shared:works-gh}

{shared:material-readonly}

## Materials

- Repository: {repo}
- Base commit: {base}
- Files the target diff touches: {changed_files}
- Places the request points to (in a run that enters at the judgment; `[]` in a run with a diff): {request_wheres}

## What to do

Search the decision records of the area the target diff touches: ADRs, the ledger of deliberate deferrals, the lists of rejected issues and pull requests, and closed issues. **If the diff is empty, search the places the request points to.** In the first round of a run that enters at the judgment, the request aims at existing code, so an empty diff is normal, and what is about to change is the place the request points to. From the records, make the list of settled points and return it in `settled`: one entry per point, with `topic`, `decision`, `reason`, `revisit` (the condition for revisiting it), and `where` (where it is written).

- Comments, docstrings, and test descriptions in the target code are not decision records. If one of them names an issue or an ADR, read what it names, and list that in `settled` with `where` pointing there.
- Each `settled` row reaches later roles as a row of the "recorded policy" section, and its `where` becomes the name of that row. A row without `where` cannot be named.
- Read the area the diff touches first. This is advice on order, not a boundary.
- Return the range you looked at and the range you did not look at in `searched`.
- If you could not search the records, set `checked` to false and `material.status` to `awaiting_human`, with the reason in `material.reason`, and put what you did read in `searched`. Do not write an unchecked area as "no settled points" (`clean`). The top-level `checked` is a boolean that says whether you could search the decision records; it is not the string `checked` inside `material`.

{shared:material-status}

## Whether you may write not_applicable

{shared:material-na}

## Where to point

{shared:material-where}

Write `material.detail`, `material.checked`, `material.reason`, the entries of `searched`, and the `topic`, `decision`, `reason`, and `revisit` of each `settled` row in {lang}. Keep keys, enum values, identifiers, paths, commands, and quoted text as they are.

Return only JSON that matches the output schema.
```

md の中に `$` の字は無い（materials.md の 3.1 の終わり）。

言語: port `lang` が空の時に入る共通の断片 `lang-default` の文（"the language of the request (the user's language)"。`prompt.lang` が読む）は、1.2 の「空は依頼の言語」と同じ物。

会話: 1 回目は新しい会話で起きる。ループは `fresh_context: false` なので、拒まれた後の 2・3 回目は同じ会話の続きで出し直す（今と同じ）。ループの最大 3 回のそれぞれに、Archon の `retry`（node が落ちた時の起こし直し、最大 2 回）が別に掛かる（受け付けの拒否は retry に数えない）。`{repo}` などの差し込み口のほかに `{` は無い。

### 2.4 返す形

今の `output_format` のまま（`workflows/judge/works-factory-judge.yaml:934-966`）:

- `material`: `{status (found|clean|carried_over|not_applicable|awaiting_human|not_run), count? (0 以上の整数), detail?, checked?, reason?, from_round? (1 以上の整数)}`・`additionalProperties: false`・`required: [status]`。
- `checked`: boolean（決定記録を洗えたか）。
- `searched`: 字の配列（見た範囲と見ていない範囲）。
- `settled`: `[{topic, decision, reason, revisit, where?}]`・各行 `additionalProperties: false`・`required: [topic, decision, reason, revisit]`。
- 全体 `additionalProperties: false`・`required: [material, checked, searched, settled]`。

人に見せる欄は `material.detail`・`material.checked`・`material.reason`・`searched`・`settled` の `topic`・`decision`・`reason`・`revisit`（判定の材料・承認ノードの記録された方針・報告に載る）で、言語は `{lang}`。`where` は名指しなので、書いてある所の字のまま。

### 2.5 描いた骨組み（例の run の値）

例の run では、今の指示は 2 か所に在った: `workflows/judge/commands/material-prior-decisions.md`（57 行。`$prior-decisions-prep.output.lang_line`・`.reason`・`.brief_file` を Archon が入れた物）と、役が Read した `judge/material-prior-decisions-brief.md`（23 行）。新しい指示はこの 2 つを 1 本にする:

```markdown
{shared:role-investigator の本文: You are the investigator: … と、その中の {shared:query-rule} の本文 Rules for queries to outside services …}

You are the prior-decisions role. …（決まった文）

Your tools are Read, Grep, Glob, Bash, WebSearch, and WebFetch. …

{shared:works-gh の本文: To read GitHub pull requests and repositories, run the read-only command `works-gh` …}

{shared:material-readonly の本文: Do not change a single character of the target's working tree, …}

## Materials

- Repository: ~/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/worktrees/archon/task-works-factory-line-1792348017642
- Base commit: 4428f368d229f2d4f4343122c620c3fdeb334184
- Files the target diff touches: []
- Places the request points to (in a run that enters at the judgment; `[]` in a run with a diff): [
 "workflows/merge/scripts/pr_commit.py の hook_env（73 行あたり）"
]

## What to do

Search the decision records of the area the target diff touches: …（決まった文と箇条 5 つ）

{shared:material-status の本文: How to write `material`: `status` is one of the following. …}

## Whether you may write not_applicable

This viewpoint has no condition under which it does not apply, so the acceptance step rejects `not_applicable`. …

## Where to point

Write the `<path>:<line>` of a location (`where`) as a line number in the current file in the working tree. …

Write `material.detail`, `material.checked`, … in the language of the request (the user's language). …

Return only JSON that matches the output schema.
```

例の run は 1 回目で通ったので、却下の段落は入らない（`rejects-prior-decisions.json` が無い）。`lang` は空で、`{lang}` に既定の文が入った形。値の字（`changed_files` の `[]` と `request_wheres` の字下げ 1 つの配列）は、今の材料のファイルの「## 材料: loop.changed_files」「## 材料: loop.request_wheres」の節の字と同じ。

### 2.6 今の指示との差

今の指示は `workflows/judge/commands/material-prior-decisions.md`（57 行）と、`lib/judge_accept.py` の `material_prep`（`:2116-2135`）が描く材料のファイルの 2 か所に在る。

- 移した: 材料のファイルの 4 つの節（`inputs.cwd`・`record.base`・`loop.changed_files`・`loop.request_wheres`）を、指示の `## Materials` の 4 行に。md の「［材料: 〜］」の穴（md:44-46）と、材料のファイルを Read で読めという手順（md:34）は要らなくなった。材料のファイルの頭の 2 行（`MATERIAL_BRIEF_HEAD` と「指示書の［材料: 〜］は…」）も要らない。
- 移した: 材料のファイルの尾の『条件に当たらない』の節（`_na_note` が組む、`:2053-2075`）を、共通の断片 `{shared:material-na}` に。Python に残るのは扱いの語（`never`）だけ。
- まとめた: 同じ md の中で 2 回言っていた却下の段落（md:22-28 の節と md:35 の手順 2）を、共通の断片 `{shared:rejected}` の 1 回に。「下の理由が空なら、これは 1 回目の返答で、拒まれていない」（md:24）は、却下が無い時は段落ごと入れない形にして要らなくした。決まりは今と同じ「丸ごと出し直せ」。中身は今の「前の回の理由 1 つ」（`boundary.prev_reason`）から「拒否の全部、古い順」（`rolekit.rejected`。world と同じ。#351）に広がる。役に渡る文の量が増えるだけで、受け付けの決まりと回数は変わらない（冒頭の「振る舞いは変えない」はこの意味）。
- まとめた: 役の定義（md:3-18）を共通の断片 2 つ（`{shared:role-investigator}` と `{shared:query-rule}`）に。今は役の定義の中に外への検索の決まりが入っていた（`lib/agents/investigator.md` の写し）。
- まとめた: 作業ツリーを変えるなの決まり 3 か所（md:7 の役の定義の Bash の箇条・md:36 の手順 3 の尾・md:48 の「ファイルの作成・編集・削除を自らに禁じる。Bash は読み取りにだけ使え（前後の作業ツリーは engine が突き合わせる）」）を、役の定義の Bash の箇条と `{shared:material-readonly}` の 2 つに。md:48 の句は消した（同じ事を 2 つが言う）。
- 移した: works-gh の段（md:36 の手順 3 の中ほど）を `{shared:works-gh}` に。道具の名と網の 1 文は観点の md に残した。
- 移した: 素材の書き方（md:49）を `{shared:material-status}` に。尾の「欄と値はここに書いたもので足りる（元の graphloops では review-record.py が正本だったが、この役が開く物ではない）」は消した（役が開かない物の名指し）。
- 移した: 所見の場所の段（md:53-55）を `{shared:material-where}` に。見出しの「（works の受け付けより）」は消した（元の works の包みの名残）。
- 移した: 言語の 1 行（md:1。`rolekit.LANG_RULE` を `$prior-decisions-prep.output.lang_line` で入れていた物）を md の 1 文に。汎用の欄の並び（reason・how・what・why・異議…）は、この役の人に見せる欄の名指しに替えた。
- 消した: 「graphloops のノード p0.prior_decisions を、下の元の graphloops の指示書のとおりに行う」（md:32）と見出し「元の graphloops の指示書（ノード p0.prior_decisions）」（md:40）と区切りの `---`。指示は 1 本の md なので、元の指示書との境が要らない。「お前は」の言い換え（#221）は済んでいる。
- 消した: 「同じ時に別の素材集めの役も走っている」（md:36）の断定。block はほかの観点を知らないので、`{shared:material-readonly}` の「走りうる」にした。
- 残した: 「settled の行は後の役に記録された方針の行として渡り、where がその名指しになる」（md:48 の中ほど。#443）。後の役の振る舞いを伝える文だが、`where` を書く訳としてこの役の返答の形を決めるので残した（world.md の 3.6 で消した「web で確かめていない定石として名指される」は、役の返答の形を変えない伝えだった）。
- 足した物は無い。英語にした（#764）。役の名「先行議論の突合の役」は "the prior-decisions role"。

### 2.7 元の works と graphloops の同じ場面

族の形の差は materials.md の 9 節。この観点だけの差:

- 元の works の `works/blk-material/commands/prior-decisions.md`（8 行）は、engine が描いた graphloops の指示書のファイル（`prompt_file`）を Read で読ませる薄い md だった。工場は graphloops の指示書を md の中に写し、値だけを材料のファイルにした（#76）。新しい形は値も指示の中に入れる。
- 元の graphloops の指示書は、元の works も工場も graphloops の版 a1202d0（0.21.0、2026-09-26）の写し。工場はそこに 3 つを足した: 差分が空なら依頼が指す場所（`loop.request_wheres` の行と、その見方の文。#76 で元の works から写した）・コメントと docstring とテストの説明文は決定記録に数えず、名指された先を読む・`settled` の `where` が記録された方針の名指しになる（どちらも #443）・返答の頭の `checked` と material の中の `checked` の区別（#221）。この block も持つ。
- graphloops の今の指示書（`~/src/claude-plugins/graphloops/prompts/review-loop/p0.prior_decisions.md`）は、a1202d0 の後の 0.21.2（`09a9b39f`、2026-09-27）で 1 段落を足した: 決定記録の置き場は対象が宣言していればそこを、無ければ一般の慣例の置き場（`docs/adr/`・`docs/decisions/`・`doc/adr/` とその索引）を読み、`docs/` の下の設計文書と git log も洗う範囲に入れ、置き場が無ければ無かったことを `searched` に書く。元の works にも工場にも無い（（未確認）: 工場の履歴に外した記録は無い。写した版がこの足しより前だった）。振る舞いを変える足しなので、この作り直しには入れず、後に別に扱う。
- graphloops の返答の型は `settled` の行に `where` を持たない（記録された方針の名指しは工場の足し、#443）。
- 元の works の受け付け（`works/blk-material/lib/material.py` の take）と工場の受け付けは同じ順（作業ツリー・所見の場所・素材の欄）。この観点に `post_check` は無い（graphloops の `MATERIAL_NODES` も持たない）。

この block が両方より良く、残す物: 決着済みの論点に `where` を持たせ、後の役が記録された方針として名指せる（graphloops は論点を判定役に渡すだけ）・コメントや docstring を決定記録と取り違えない（#443 の較正の 2 件）・作業ツリーと所見の場所を機械が照らす・洗えなかった時の `clean` を指示で止める（元の graphloops と同じ）。

### 2.8 受け付け

materials.md の 4 節の順のまま。観点の前の照らしと後の照らしは無い。

- 拒む物: JSON のオブジェクトでない返答・役が作業ツリーを変えた（`GUARDED` が偽なので、比べる欄は `porcelain` を含む `TREE_KEYS` の全部）・所見の場所の行がファイルに無い（`material.detail` などの中の `<パス>:<行>` も、行の `where`〔`settled` の行は `text` を持たないので `where_rows` に当たらない〕も、`where_rows` が拾う物だけ）・素材 `prior_decisions` が無い・`carried_over`・`not_applicable`（`never`）・知らない status・status ごとの要る欄の欠け。
- 返答の形（`output_format`）の外れは Archon が node の段で拒む（今のまま）。
- 拒みの文は materials.md の 2.8 と 4 節の字（日本語）。
- 3 回目の拒否でループを抜ける（`rolekit.GIVE_UP_AFTER`）。run は止めず、`finish` が `status: gave_up`・`reason` に最後の拒否の文（`rolekit.given_up_reason`）・素材 `prior_decisions` に `not_run` と同じ訳を書く。
- 所見の場所の外れは、3 回目の回は拒まずに `where` の尾に印（`LOCATION_MARK`）を付けて受ける（今のまま）。

### 2.9 試験

- standalone の fixture（`blocks/prior-decisions/fixtures/`）:
  - `standalone.stubs.yaml`: `fixture.inputs` は `base: ""`・`request: '[{"where":"README.md","text":"…直したい事…"}]'`・`entry: "人の依頼（standalone）"`・`lang: ""`。AI の node `prior-decisions` だけを台本の返答（`material.status: clean`・`checked: true`・`searched` 1 行・`settled: []`）で差し替え、script は本物（`--exec-code`）。`reached` に `finish`、`resolved-text-contains` に md の決まった文（7 節）。`finish` の出力の `status` が `ran` になることは試験が照らす（筋書きは node の返りを照らせない）。
  - `gave-up.stubs.yaml`: 台本の返答が 3 回とも `material.status: not_applicable`。run は `completed`（dry-run は輪を 1 周で終えるので、3 回で `finish` が `status: gave_up` を返す数えは試験が照らす）。
  - 回す条件は持たない（いつも回す）ので `skipped.stubs.yaml` は置かない。
- `tests/blocks/prior_decisions/test_prior_decisions.py`: materials.md の 8 節の block の試験。始めの記録の無い使い捨ての `ARTIFACTS_DIR` と git のリポジトリで、port の値だけを渡す。
  - 写す元 `lib/tests/test_judge_accept.py::MaterialCase.test_prior_decisions_reply_is_taken_or_refused`: 見た返答は `material.json` の `materials` に `{"prior_decisions": <返答の material>}` で載り、`not_applicable` は拒まれ、`settled` の `where` が `policy.recorded(start, <material.json のパス>)` の `source: settled` の行の `name` に出る（読み手の口が新しいファイルの形のまま読めることの照らし）。
  - 写す元 `DueCase.test_empty_diff_run_with_requests_runs_only_prior_decisions` のうち prior-decisions の部分: 差分が空で `entry` の在る run でも `intake` の `due` が真。
  - 足す: `entry` が空なら `request_wheres` の値が `[]`、在れば依頼の行の `where` の並び（`findings` の欄に持つオブジェクトの形でも）。依頼が読めない字なら `finish` の `status` が `failed` で、`reason` が入力の名を言う。
  - 足す（起こし方の照らし）: block の YAML の AI の node の `model`・`allowed_tools`・`sandbox`・`idle_timeout`・`retry` が、今の `tests/workflows/test_judge.py:87` の表の prior-decisions の行（`"sonnet", "medium", INVESTIGATE, CLOSED, …`）が照らす物と同じ。
- 指示の比べ（README の 11.4）: 済み。1 つ目の commit（`d05a8711`）に `tests/blocks/prior_decisions/test_prompts.py` を置いて下の (a)・(b) を照らし、通した。2 つ目の commit（`f7f7e91b`）で消した。
  - 1 つ目の commit: `prompts/prior-decisions.md` を、今の `workflows/judge/commands/material-prior-decisions.md` の `$prior-decisions-prep.output.lang_line` を `{lang_line}` に、`.reason` を `{reason}` に、`.brief_file` を `{brief_file}` に替えた日本語の字で置く。prep は 1 つ目の commit だけ `lang_line`（`rolekit.lang_line({"lang": values["lang"]})`）・`reason`（最後の拒否の文。無ければ空）・`brief_file`（`src/oldbrief.py` が書いた `material-prior-decisions-brief.md` の絶対パス）を値に入れる。試験は例の run の値（`base`・`changed_files: []`・`request_wheres` の 1 行・リポジトリのパス）で、(a) 組んだ指示が今の md に同じ 3 つの値を入れた字と同じ、(b) `oldbrief.brief` の字が例の run の `judge/material-prior-decisions-brief.md` と同じ（リポジトリのパスは試験のリポジトリのパスに置き換えて比べる）ことを照らす。
  - 2 つ目の commit（英語）: 1 つ目の試験と `src/oldbrief.py` を消し、例の run の値で組んだ新しい指示と、今の md と材料のファイルを並べた物を PR に載せ、2.6 の差の一覧どおりかを審査に出す。
- 振る舞いの試験の残り: 族の部品の試験（`lib/tests/test_materialkit.py`。materials.md の 8 節）が、作業ツリー・所見の場所・素材の欄の照らしを見る。
- 読み手の側の試験はそれぞれの block に残す: `lib/tests/test_policy.py` の settled の行の読み（KEEP）・`tests/workflows/test_plan_review.py:1438` の `decisions` の入力（plan-review）。`lib/tests/test_policy.py::test_prior_decisions_file_is_the_material_file_of_its_role`（今のファイルの名 `material-prior-decisions.json` を縛る）は、組み込みで判定の出力の欄 `decisions` が新しい `material.json` を指すようになった時に消す。
- 守る keep-essence の番号: 無い（README の 10 節の 12 の仕組みにこの観点は出てこない）。守るのは「決着済みの論点が記録された方針として後の役に名指しで届く」（#443）で、上の `policy.recorded` の照らしが見る。
- 終わりの条件の命令（1 モジュールずつ）:

```sh
uv run --isolated python3 -m unittest lib.tests.test_materialkit
uv run --isolated python3 -m unittest discover -s tests/blocks/prior_decisions -t .
uv run --isolated python3 -m unittest tests.layers.test_block_shape
uv run --isolated python3 -m unittest discover -s tests/blocks/materials -t .
```

  `tests/blocks/prior-decisions/` の Python の package の名は字 `-` を持てないので、フォルダの名を `tests/blocks/prior_decisions/` にする（自分で決めた。7 節）。上の 2 行目の `discover -s` もその名で打つ。

## 3 script の node

materials.md の 6 節の雛形のまま。この block だけの物:

- `intake.py` が読む入力は `INPUTS_BASE`・`INPUTS_REQUEST`・`INPUTS_ENTRY`・`INPUTS_LANG` の 4 つ。`request` は `requestrows.findings(os.environ.get("INPUTS_REQUEST"))`（形の照らしと、下書きの行・知らない鍵の拒み）、ほかは `ports.text(…)`。値の dict の鍵は `base`・`request`・`entry`・`lang`。
- `role_prep.py` は materials.md の 6 節の雛形のまま（1 つ目の commit だけ、材料のファイルを書いてから組んだ）。

## 4 受け付けの文

materials.md の 2.8 と 4 節の文だけを使う。この観点が足す拒みの文は無い。

## 5 単独で呼ぶ

```sh
WORKS_FACTORY_FOLDER=blocks bin/works-factory workflow run works-factory-prior-decisions \
  --input request='[{"where":"docs/owner-decisions.md","text":"…直したい事…"}]' \
  --input entry='人の依頼（手で起こした run）' --input base=
```

作業ツリーは Archon の cwd（対象のリポジトリ）。出力は `workflow get <run>` の `finish` の返り。始めの記録は要らない。差分の在る作業ツリーで `entry` を空にすると、差分が触れるファイルの決定記録を洗う。

## 6 未確認

- 土台の役の定義の断片の名 `role-investigator` と、その断片が外への検索の決まりを含むか（materials.md の 11 節）。
- 起動の殻で `blocks/` を読ませる引数の名と、5 節の命令の正確な形（world.md の 10 節と同じ）。

## 7 自分で決めた事（この block だけ）

- `purpose` を入力に持たない。訳: 今の材料の穴（`MATERIAL_HOLES['prior-decisions']`、`lib/judge_accept.py:1723`）にも回す条件（`prior_decisions_due`）にも目的の文は出てこない。読まない入力を足すと、graph の配線が読まない値を運ぶ（README の 1.2 の P）。README の 8.1 の例の「request・purpose」は直す（報告に書いた）。
- `fill` と `applies` を `NotImplementedError` で定義する。訳: materials.md の 5.1 は全部の名を定義させる。この観点はいつも回し、『条件に当たらない』を名乗れないので、呼ばれた時に黙って既定の値を返すより、落ちて不具合を見せる方が正しい（持ち主の決め `no-silent-loosen`）。
- 試験のフォルダの名を `tests/blocks/prior_decisions/` にする。訳: unittest は package の名に `-` を持てない（`discover` の時に import できない）。README の 3 節の `tests/blocks/<block>/` の `<block>` は、Python の package の名に直した字と読む。
- （実装で決めた事・訳だけ。本文は 1.5・2.3・3 節）`request` を共通の形と `requestrows` で読む: 同じ名の形が pack の 2 か所に在ると形の検査が赤で、`requestrows` は下書きの行と知らない鍵を拒む（materials.md の 10.1）。
- （同）md に `{shared:query-rule}` を置かない: 土台の `role-investigator` が中に持つ（6 節の未確認の答え）。2 回入れると同じ決まりが 2 度届く。
- （同）`request_wheres` を `is_entry_run`（`entry` と空の差分）で決める: 今の `request_wheres` は入口の印（差分が空で依頼が在る）の周だけ並べた。差分は block が測れる事実なので測る。
- （同）筋書きは出口の `status` を照らせない（dry-run は輪を 1 周で終える）ので、`ran`・`gave_up` は `tests/blocks/prior_decisions/test_prior_decisions.py` が照らし、筋書きは md の決まった文を照らす（形の検査 7.1 の 3）。
- （同）起こし方の照らしは今の `tests/workflows/test_judge.py` を import せず、決まった期待の値で照らす: 組み込みで `workflows/` が消えると import が壊れる。
