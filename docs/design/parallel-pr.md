# block の設計書: parallel-pr（並行 PR）

- 何の話か: 開いている PR とこの run の変更ファイルの交差を見て、ぶつかる hunk を run の範囲から外し、担当への申し送りの下書きを作る観点「並行 PR」を、単独で呼べる block `blocks/parallel-pr/` にする設計。型は [README.md](README.md) に従い、形は [world.md](world.md) を写した。
- 決めたこと: 今の judge の 5 つの node（pr-scan・pr-check-loop の 3 つ・pr-check-reads）を、6 つの node の block にする。入力は依頼の行・差分の根・変更ファイル・言語の 4 つの port だけで、始めの記録と `judge/` の置き場を読まない。指示は 1 本の英語の md（`prompts/pr-check.md`）にまとめる。振る舞いは変えない（違いは 6 節に全部書いた）。
- 持ち主に求めること: なし。この block を作る人（実装の役）は、この設計どおりに作る。自分で決めた事は 10 節に集めた（記録として置く。持ち主の確認は待たない）。

この文書の語は README の頭の物を使う（line・graph・block・port・place・prep・accept・Archon・元の works・graphloops など）。ほかに:

- 判定の道・再審の道: 今の judge の 2 つの道。判定の道は依頼から判定を作る 1 回目、再審の道は修正役の異議を受けて判定をやり直す道（`objection` が空でない run）。並行 PR は判定の道でだけ回る。
- 仕様の段: 依頼の要件と受け入れテストを書いて人が承認する段（[spec.md](spec.md)）。始めの記録が選んだ run でだけ回る。
- 周: 1 回の修正と確かめの巡り。工場は 1 run を 1 周とし、周をまたぐのは周の鎖（chain）が起こす次の run。graphloops は 1 run の中で周を重ねた。
- pointer: run directory の中のファイルを指す Archon の値 `{type: archon_artifact, run_id, path}`。

- 機械の道: 役を起こさずに、gh の読みだけで交差を数えて決める道（今の `judge_accept.pr_scan`）。交差が無い・remote が GitHub でない・変更ファイルが空・一覧が打ち切られた、のどれかなら機械が決める。
- 任せ先の役（pr-check）: 機械が決められなかった時（交差が在った・gh が無い・remote から owner/repo を導けない）だけ起きる AI の役。読むだけで、道具は Read・Grep・Glob・Bash・WebSearch・WebFetch。
- 外す hunk: ぶつかる PR が主導する変更の、今の作業ツリーでの行の範囲。run の後の役に触らせない範囲として出力で渡す。
- 申し送りの下書き: ぶつかる PR の担当に渡す文の下書き。投稿しない（持ち主の決め 2026-09-27）。人が読んで渡す。
- 素材の札: 判定の素材の status の語（found・clean・carried_over・not_applicable・awaiting_human・not_run）。diagnose が素材として読む。
- 例の run: 本物の run `df5e111f-ea97-409b-8066-2245d32746ab`（対象 raiki61/works-factory。置き場 `~/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/artifacts/runs/df5e111f-…/judge/`）。#756 と 1 件交差し、役が起きて found を返した run。骨組みの値はここから取った。

## 1 block の全体

### 1.1 役

この run が触るファイルを、開いている PR が触っていないかを確かめる。触っていれば、どの hunk がぶつかるかを読み、ぶつかる所はその PR の物として run の範囲から外し、担当への申し送りの下書きを作る。GitHub へは書き込まない。確かめられなかった時は、確かめられなかったと言う（clean と書かない）。

### 1.2 port

入力（YAML の `inputs:`）:

- `request`: `json(request.schema.json): 依頼の行の配列 [{where, text, mechanism?, measured?, false_positive_if?}]。それを findings の欄に持つオブジェクトでもよい。changed が空で base からも変更ファイルが取れない時だけ、行の where が名指す追跡中のファイルを変更ファイルにする`。既定 `[]`。
- `base`: `text: 差分の根の commit（今の始めの記録の diff_base）。空なら差分から変更ファイルを取らない`。既定 `""`。
- `changed`: `json(changed.schema.json): 変更ファイルのパスの配列（作業ツリーの根からの相対）。空の配列なら base から取る`。既定 `[]`。
- `lang`: `text: 人に見せる欄（material の detail・checked・reason、conflicts の note、excluded の why）の言語。空は依頼の行の言語`。既定 `""`。

変更ファイルの決め方（`src/scan.py` の `changed_files`。この順で最初に空でない物）:

1. port `changed` の値。
2. `base` が空でなければ、`lib/accept.py` の `touched_files(<作業ツリー>, base)`（`git diff --name-only <base>` と未追跡のファイル）。`Reject` は空として扱う（今の `_pr_files` のまま）。
3. `git ls-files -z` の追跡中のパスのうち、`request` の行の `where` の字に含まれる物（名の順）。

出力（`returns: finish`、`outcome_field: ok`）:

- `ok`: boolean。`stop_reason` が空か（役が 3 回とも拒まれず、段が落ちなかった）。素材の札が `awaiting_human`・`not_run` でも `ok` は真（確かめられなかったことは `status` が言う。今も run を止めない）。
- `status`: 素材の札（`found`・`clean`・`not_applicable`・`awaiting_human`・`not_run`）か `failed`（役を諦めた・出口の誤り）。
- `stop_reason`: 空か `works:pr`（`lib/stopby.py` の `PR`。役が 3 回とも拒まれた）。run を止めるかは line が決める（今は judge がこの語で止める）。
- `reason`: 日本語の 1 行（人に見せる）。機械が決めた訳・役に任せた訳・諦めた訳。
- `material`: 素材の札のオブジェクト `{status, count?, detail?, checked?, reason?}`（今の `material-pr-check.json` の `materials.parallel_pr` と同じ中身）。diagnose の `materials` に入る。
- `excluded`: pointer（`pr-excluded.json`。`{node, head, excluded: [{pr, file, start, end, why, text, sha256}]}`）。機械が決めた時も空の `excluded` で書く。
- `drafts`: pointer（`pr-downgrades.json`。`[{pr, files, note}]`）か null（役が起きなかった・下書きが無い）。
- `reads`: pointer（`reads-pr-check.json`）か null（役が起きなかった・読んだ証拠を集められなかった）。
- `downgrades`: この block が元の能力から下げている所の宣言 `[{what, versus}]`（日本語。`src/files.py` の定数 1 行: `{what: "担当の PR へ申し送りを投稿しない（下書きを報告に載せる）", versus: "review-graph は任せ先の役が gh で投稿する"}`。今の `lib/downgrades.json` の p0.parallel_pr の行の字）。
- `report`: 報告の節「並行 PR」の日本語の行の配列（8 節）。

今との違い: 今は差分の根を `judge/start.json`（`start_view` の `diff_base`）から、依頼の行を `judge/request.json` から、止めの控えを `judge/stop.json` から名で開き（`lib/judge_accept.py:3547-3584`）、役の前の作業ツリーの写しは judge の入口（か仕様の承認の後）が置いた `judge/judge-tree.json` を使っていた（`:3622`）。出口は判定の出力の欄 `pr_excluded`・`pr_drafts` と `materials` の中だった。止めの控えの確かめは無くし（回すかは graph の `when:`。README の 4.3）、作業ツリーの写しはこの block が自分で取る。

### 1.3 node の並び（`blocks/parallel-pr/works-factory-parallel-pr.yaml`）

1. `scan`（script `scan.py`）: port を読み、place を作り直し、役の前の作業ツリーの写し `tree.json` を取り、機械の道を回す。返り `{go_role, reason}`。
   - `output_format`: `{type: object, additionalProperties: false, required: [go_role, reason], properties: {go_role: {type: boolean}, reason: {type: string}}}`。
2. `pr-check-loop`（`loop_group`、`max_iterations: 3`、`fresh_context: false`、`until_bash: 'done=$pr-check-accept.output.done; test "$done" = true'`、`when: "$scan.output.go_role == true"`）
   - `pr-check-prep`（script `prep.py`。`mutates_checkout: false`）: 指示を組む。返り `{prompt}`（`output_format` は `prompt` の string だけ）。
   - `pr-check`（AI。`prompt: "$pr-check-prep.output.prompt"`。下の鍵は今の `&net_closed_launch` のまま写す: `model: '@wf-judge-materials'`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob, Bash, WebSearch, WebFetch]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false, failIfUnavailable: true, excludedCommands: ['works-gh:*'], network: {allowedDomains: []}, filesystem: {denyWrite: ['~/../archon-home']}}`・`idle_timeout: 1728000000`・`retry: {max_attempts: 2, on_error: all}`。Bash を持つので `mutates_checkout:` は書かない〔E7〕。`output_format` は 2.4 の形）。sandbox の YAML のコメント（今の `:479-482` の #293・#309 の訳）は消す（block は埋めの振る舞いを書かない。README 1.3 の歩かせ 8）。
   - `pr-check-accept`（script `take.py`。`with: {reply: $pr-check.output}`。`mutates_checkout: false`）: 返り `{ok, done, reason}`（3 つとも required）。
3. `pr-check-reads`（script `read_proof.py`。`depends_on: [scan, pr-check-loop]`・`trigger_rule: one_success`・`when: "$scan.output.go_role == true"`・`mutates_checkout: false`）: 役が渡し物を読んだ証拠を集める。受け付けの条件にしない。返り `{ok, missing, index_file, reason}`（今のまま）。
4. `finish`（script `finish.py`。`depends_on: [scan, pr-check-loop, pr-check-reads]`・`trigger_rule: all_done`・`mutates_checkout: false`）: 出力を組んで返す。どの段が落ちても落ちない（今の落とし穴 K1・K13 の決まり）。`output_format` は 1.2 の出力の欄の全部を required にし、`excluded`・`drafts`・`reads` は `{type: [object, "null"]}`（pointer の object か null）、`material` は `{type: object}`、`report` は `{type: array, items: {type: string}}`、`downgrades` は `{type: array, items: {type: object, required: [what, versus], properties: {what: {type: string}, versus: {type: string}}}}`。

script の名は `lib/` のモジュールの名と重ねない（README の 7.1 の 9）。今の `pr_reads.py` は `lib/reads.py` と字が近いので `read_proof.py` に、受け付けは `lib/accept.py` と重ならないよう `take.py` にした。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、line から judge のまとめを通して include された時は `$ARTIFACTS_DIR/judge/parallel-pr/`）の下に書く。名は `src/files.py` だけが持つ:

- `tree.json`（役の前の作業ツリーの写し。今の `judge/judge-tree.json` の役目のうち、この block の分）
- `pr-brief.json`（役への渡し物。今のまま `{node, cwd, base, changed_files, request_wheres, fallback}`）
- `material-pr-check.json`（素材の控え。今のまま `{role, reply, materials: {parallel_pr}}`）
- `pr-excluded.json`・`pr-downgrades.json`（今と同じ名と形）
- `rejects-pr-check.json`（`rolekit` の却下の控え）
- `pr-check-prompt-<n>.md`（組んだ指示）
- `reads-pr-check.json` と、その索引（`reads.index_name("pr-check")` の名）

`node` の欄の値は今の `prcheck.NODE`（`p0.parallel_pr`）のまま書く（読み手が古い控えと同じ形で読めるように）。

### 1.5 コードの置き場

- `blocks/parallel-pr/src/files.py`: place のファイルの名（1.4）と `ROLE = "pr-check"`・`NODE = "p0.parallel_pr"`・`PR_LIMIT = 100`。
- `blocks/parallel-pr/src/scan.py`: 今の `lib/judge_accept.py` の `_github_repo`（:3453）・`_pr_files`（:3469。1.2 の 3 段の決め方に替える）・`parallel_pr_plan`（:3485）・`parallel_pr_scan`（:3500）・`parallel_pr_reply`（:3523）・`_pr_material`（:3541）・`pr_scan`（:3547）の写し。`start_view`・`read_stop`・`_requests` の読みは消し、port の値を引数で受ける。
- `blocks/parallel-pr/src/take.py`: 今の `check_no_post`（:3593）・`prcheck_drafts`（:3602）・`prcheck_take`（:3610）・`pr_accept`（:3636）・`NO_POST` の写しと、今の `lib/prcheck.py` の `_anchored`・`check_excluded`・`_write`・`EXCLUDED_FIELD`。`_moved_since`・`_tree_snapshot` は自分の `tree.json` を読む形の写し（`lib/accept.py` の `tree_state`・`tree_moved`・`type_errors`・`TREE_SCHEMA` を呼ぶ）。`prcheck._write` が使う `marks.write` は消す（`marks` は README の 9.1 で DELETE）ので、`jsonfile.write` で書く。
- `blocks/parallel-pr/src/proof.py`: 今の `pr_reads`（:3646）の写し（`lib/reads.py` の `collect`・`index_name`・`stamp`・`log_here`・`guarded` を呼ぶ）。
- `blocks/parallel-pr/src/report.py`: 報告の行（8 節）。今の `prcheck.draft_lines` の写しを持つ。
- `blocks/parallel-pr/schemas/request.schema.json`（world の物と同じ形の写し。block どうしでファイルを共に使わない）・`changed.schema.json`（`{type: array, items: {type: string, minLength: 1}}`）。
- 使う `lib/`: `materialkit`（`STATUS`・`check_record`）・`forge`（`detect`・`reason`・`repo_of`・`redact`・`_git`・`GITHUB`）・`ghreads`（`_gh`。gh の読む口）・`accept`（`touched_files`・`tree_state`・`tree_moved`・`type_errors`・`TREE_SCHEMA`・`Reject`）・`reads`・`rolekit`（`accept_round`・`rejected`・`rejects_text`・`given_up_reason`）・`stopby`（`PR`）・`jsonfile`・`oneline`。
- 素材の札の語と照らし: 素材の観点の族の共通の部品 `lib/materialkit.py`（[materials.md](materials.md) の 2 節）の `STATUS`・`check_record`。この block の `material` は diagnose が素材の 1 欄（`parallel_pr`）として読むので、同じ語と同じ照らしを使う（自分で決めた。10 節の 2）。この block の PR は、そのモジュールと断片 `works-gh`・`material-status`・`material-na` を置く PR（素材の観点の 1 本目）の後に出す。
- 作り直しの間は `lib/prcheck.py` と `lib/judge_accept.py` の並行 PR の部分を消さない（今の judge が使う）。組み込みで消す（README の 9.2）。`lib/downgrades.json` と `prcheck.downgrades`・`head_downgrades` はこの block に写さない（6 節の 6）。

### 1.6 つなぎ方（graph の側。block には書かない）

- judge のまとめ（`blocks/judge/`）: `include: works-factory-parallel-pr`。`when:` は今の pr-scan の条件「判定の道（再審の道でない）で、仕様の段が止めていない」を line が引いた真偽。`with:` は `request: $<依頼の pointer>`・`base: <始めの記録の diff_base>`・`changed: "[]"`・`lang: <始めの記録の lang>`。仕様の段を挟む run では、今と同じく仕様の承認の後に回す（承認で書いた受け入れテストのファイルを、役の前の写しに入れるため。今の `spec_answer` が写しを取り直していた事の替わり）。
- 読み手: diagnose の `materials`（`$parallel-pr.output.material`）と再審の材料（`excluded`）・plan と plan-review と案の直し（`excluded`。今の `planblk.head` の「外す hunk」の節）・report の `sections`（`$parallel-pr.output.report`）と下げた物（`downgrades`）・line（`stop_reason` で止めるか）。fix には今も渡らない（6 節の 5）。

## 2 node の設計シート: pr-check（任せ先の役）

### 2.1 役

機械が決められなかった時に起き、開いている PR とこの run の変更ファイルの交差を 6 段で確かめ直し、ぶつかる hunk を外し、担当への申し送りの下書きを書く。投稿しない。

### 2.2 port

`pr-brief.json`（← `scan` が port `base`・`changed`・`request` から組んだ渡し物）・前の回までの却下の理由（← `rejects-pr-check.json`）・`lang`（← port `lang`）。リポジトリは run の作業ツリーで、port ではない。

### 2.3 組み立ての順（`prompts/pr-check.md`）

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: 却下の控えが空でない。断片の中の `{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "pr-check"))`（古い順に全部。日本語。4 節）。
2. `{shared:query-rule}`（外への検索の決まり）。断片の `spawns` には `false` を渡す（この役は Agent の道具を持たない）。
3. 役の定義と読むだけの決まり（決まった文）。
4. 渡し物の 1 行と `{brief_file}` ← `src/files.py` の `pr-brief.json` の place の絶対パス。
5. `{shared:works-gh}`（読むだけの口の使い方。materials の設計書の 3.2 が決めた断片）と、口が無い時の 1 文（決まった文）。
6. 渡し物の欄の説明（決まった文）。
7. 6 段（決まった文）と差し込み口 `{limit}`（← `src/files.py` の `PR_LIMIT`）。
8. 動かしてはいけない語と、決めてはいけない事（決まった文）。
9. `## How to answer`（決まった文）と差し込み口 `{lang}`。
10. `{shared:material-status}`（素材の書き方。materials の 3.2）。
11. `## Whether you may write not_applicable` と `{shared:material-na}`（同じ。`na_never: true`）。
12. 結びの 1 文（決まった文）。

md の本文（英語。この block の PR でこのまま置く）:

```markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{shared:query-rule}

You are the parallel-PR role, started in a new conversation. Your job is to check whether open pull requests in the target repository touch the same files as this run's change, to take the hunks that collide out of this run's scope, and to draft a hand-over note for the owner of each colliding pull request. Work through the 6 steps below in order. Do not skip a step.

You only read. Do not write or delete files, and do not move the git state (HEAD, branch, stash). The machine compares the working tree, the HEAD sha, and the branch from before you started with the ones after you answer, and rejects the answer if they changed.

The machine's hand-off file: `{brief_file}` (read it; it is JSON).

{shared:works-gh}

If `command -v works-gh` prints nothing, the command is missing and you cannot read GitHub: return `material` with status `not_run` and a reason that says the read-only command is missing.

- `cwd`: the target repository. `base`: the root of the diff (the commit fixed at the start of the run).
- `fallback`: why the machine handed this check to you. The machine tries to finish steps 1 to 5 with gh reads only, and hands over when there was an intersection, when gh is missing, or when it cannot derive owner/repo from the remote. When the remote is not GitHub (no origin, a local path, or another host), the machine marks the check `not_applicable` (no_forge) and does not start you.
- `changed_files`: the set of changed files the machine took. In a run whose diff is empty, these are the tracked files named in the request's places (`request_wheres`).

**You receive this prompt only when the machine could not finish steps 1 to 5, or found an intersection.** Even when it handed over because of an intersection, check steps 1 to 5 again yourself before step 6.

1. Resolve the target repository: derive owner/repo from `git remote get-url <upstream remote>` (the upstream is `git rev-parse --abbrev-ref @{u}`; if there is none, origin). Pass `-R <owner/repo>` to every later `works-gh`. **Do not use the value of `gh repo view` for this check** (it resolves from the cwd's remote, so the check would always pass). If you cannot derive it, the rest is "could not be checked" (`awaiting_human`). Do not write "no collision" from a list you might have taken from the wrong repository.
2. Leave out your own pull request: list with `works-gh pr list -R <owner/repo> --limit {limit} --json number,headRefName,headRefOid`, and remove first the pull request whose headRefOid equals `git rev-parse HEAD` (if you do not, the review target itself goes out of scope, a self-referential misjudgment). Do not match by branch name; on a detached HEAD it is empty.
3. Check whether the list was cut: if the number returned equals the `--limit`, the list may have been cut. Then set `truncated` to true and `material` to `awaiting_human`. Do not write "no collision" from a cut list.
4. The set of changed files is `changed_files` in the hand-off file. **If the set is empty, do not write `clean`**: an intersection with an empty set checks nothing. Return `not_run` with a reason that says what was empty.
5. The changed files of each remaining pull request: `works-gh pr view <n> -R <owner/repo> --json files --jq '.files[].path'`. A pull request whose files intersect the set is a parallel pull request touching the same file.
6. Hand the colliding places to the pull request that owns them, without posting: read the hunks with `works-gh pr diff <n> -R <owner/repo>`. For each place where a collision or overlap is found, treat that change as belonging to the pull request that leads it and take it out of this run's scope (one row per hunk in `excluded`). Write a draft of the note for that pull request's owner in `conflicts[].note`: which pull request, which file, which hunk, which change of this run it collides with, and a question asking which should go in first. Return `handed_over: false`. This block does not post to pull requests (owner's decision 2026-09-27); a person reads the drafts and passes them on.

**Do not type commands that move HEAD or the branch** (`git checkout`, `git switch`, `git stash`, `git reset`). The read-only command refuses writing gh commands; the only gh commands you may type are `works-gh pr list -R <owner/repo>`, `works-gh pr view <n> -R <owner/repo>`, and `works-gh pr diff <n> -R <owner/repo>`. If you return even one row with `handed_over: true`, the machine rejects the answer.

Do not decide yourself whether the remote is GitHub (whether there is a host that holds pull requests). The machine decides that, and in runs where it applies you do not receive this prompt. If the sandbox refuses gh's network access and you cannot check, you may return `not_run` with the refused command and its output as the reason. **Do not write an unchecked result as `clean`.**

## How to answer

- `repo`: the owner/repo you derived in step 1. `listed`: the number returned in step 2 (before removing your own pull request). `truncated`: step 3.
- `conflicts`: one row per intersecting pull request, `{pr, files, handed_over: false, note}`. `pr` is the pull request number as a string, `files` the intersecting files, `note` the draft from step 6.
- `excluded`: one row per hunk you take out of this run's scope in step 6, `{pr, file, start, end, why}`. `pr` is a pull request in `conflicts`, `file` a file in that row's `files`, `start` and `end` the line range **in the current working tree** of that file (1-based, both ends included), and `why` what it collides with. A pull request that has a hunk to take out needs a `note`. Do not take out a pull request whose hunks do not collide, even if it touches the same file. If there is nothing to take out, return `excluded: []`.
- `material`: written as below.
- Write `material.detail`, `material.checked`, `material.reason`, `conflicts[].note`, and `excluded[].why` in {lang}. Keep keys, enum values, pull request numbers, paths, commands, and their output as they are.

{shared:material-status}

## Whether you may write not_applicable

{shared:material-na}

Return only JSON that matches the output schema.
```

`@{u}` と `{pr, files, handed_over: false, note}`・`{pr, file, start, end, why}` は差し込み口の形（`{` の直後が小文字の名で `}` で閉じる）に合わない字を含むので、そのまま字として残る。`material-na` の断片には `na_never: true`（ほかの 3 つは偽）を渡す（この役は『条件に当たらない』を名乗れない。remote が GitHub でない run は機械が決めて役を起こさない）。

### 2.4 返す形

今の `output_format` のまま: `{material: {status (found|clean|carried_over|not_applicable|awaiting_human|not_run), count?, detail?, checked?, reason?, from_round?}, repo, listed (0 以上の整数), truncated (boolean), conflicts: [{pr, files, handed_over, note?}], excluded: [{pr, file, start (1 以上), end (1 以上), why}]}`（全部 required。`excluded` の行の字の欄は `minLength: 1`・`pattern: '\S'`）。`carried_over` と `from_round` は素材の札の共通の形に合わせて残す（受け付けが拒む。4 節）。人に見せる欄は `material.detail`・`checked`・`reason`・`conflicts[].note`・`excluded[].why`（報告と人に載る）で、言語は `{lang}`。

### 2.5 描いた骨組み（例の run の値）

例の run の役は今の `workflows/judge/commands/pr-check.md` を Archon が置き換えた指示を受けた（組んだ指示はファイルに残っていない）。下は同じ値を新しい md に入れた骨組み（値は例の run の `judge/pr-brief.json` と、`rejects-pr-check.json` が無いこと〔1 回目で通った〕から）。

```markdown
Rules for queries to outside services …（{shared:query-rule} の本文。spawns が false なので下請けの段落は入らない）

You are the parallel-PR role, started in a new conversation. …（決まった文）

You only read. …

The machine's hand-off file: `~/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/artifacts/runs/df5e111f-ea97-409b-8066-2245d32746ab/judge/parallel-pr/pr-brief.json` (read it; it is JSON).

{shared:works-gh の本文: To read GitHub pull requests and repositories, run the read-only command `works-gh` …}

If `command -v works-gh` prints nothing, … status `not_run` …

- `cwd`: …
- `fallback`: … marks the check `not_applicable` (no_forge) …
- `changed_files`: …

**You receive this prompt only when …**

1. Resolve the target repository: … (`awaiting_human`) …
2. Leave out your own pull request: list with `works-gh pr list -R <owner/repo> --limit 100 --json number,headRefName,headRefOid`, …
3. … `material` to `awaiting_human` …
4. … do not write `clean` … Return `not_run` …
5. …
6. …

**Do not type commands that move HEAD or the branch** …

## How to answer

- `repo`: …
- `material`: written as below.
- Write `material.detail`, … in the language of the request lines. …

How to write `material`: `status` is one of the following. …（{shared:material-status}）

## Whether you may write not_applicable

This viewpoint has no condition under which it does not apply, so the acceptance step rejects `not_applicable`. …（{shared:material-na} の na_never の段）

Return only JSON that matches the output schema.
```

渡し物の中身（例の run）: `cwd` は run の作業ツリー、`base` は `4428f368d229f2d4f4343122c620c3fdeb334184`、`changed_files` は `["workflows/merge/scripts/pr_commit.py"]`、`request_wheres` は `["workflows/merge/scripts/pr_commit.py の hook_env（73 行あたり）"]`、`fallback` は「並行 PR と 1 件交差した（['756']）——交差した hunk を読んで担当の PR に申し送る 6 段は役」。place のパスは include の道（`judge/parallel-pr/`）が入った形で書いた。役は 1 回目で通り、`material.status: found`・`conflicts` 1 行（#756）・`excluded: []` を返した。

### 2.6 今の指示との差

今の指示は `workflows/judge/commands/pr-check.md`（41 行）1 本で、lib の Python は指示の文を組んでいない。値は Archon の置き換え（`$pr-check-reject.output.*`・`$ARTIFACTS_DIR`）で入っていた。

- 移した: 却下の段落（md:16-24）を共通の断片 `{shared:rejected}` に。今は前の回の理由 1 つだけ（`reject.py` が `$LOOP_PREV` の理由を返す）だったが、world と同じく古い順に全部を渡す（`rolekit.rejects_text`。#345 で他の loop に入れた形）。拒まれた回の指示が増えるだけで、1 回目は同じ。
- 移した: 外への検索の決まりの塊（md:3-14）を `{shared:query-rule}` に。頭の「works の包みより」は消した（world と同じ）。
- 移した: 読むだけの口の段落（md:30）を、素材の観点と共に使う断片 `{shared:works-gh}` に（`$(…)` は断片の中で「a command substitution」と言い換えてある。materials の 3.1 の `$` を置かない決まり）。口が無い時の 1 文はこの役だけの物なので md に残した。
- 移した: 素材の書き方の段落（md:54）を断片 `{shared:material-status}` と `{shared:material-na}`（`na_never`）に。素材の札の語は断片が字で持つ。
- 移した: 言語の 1 行（md:1 の `$pr-check-reject.output.lang_line`。`rolekit.LANG_RULE` の汎用の欄の並び）を、この役の人に見せる欄を名指す 1 文に（`How to answer` の最後の箇条）。
- 替えた: 渡し物のパス `$ARTIFACTS_DIR/judge/pr-brief.json` を `{brief_file}`（place の絶対パス）に。上限 100 を `{limit}` に（`src/files.py` の `PR_LIMIT` と受け付けの打ち切りの決めが同じ字を持つ。README の 5.3）。
- 消した: 見出し「# P0-5 並行 PR 衝突チェック」の段の番号（graphloops の段の名で、この block は知らない）。
- 消した: 6 段の括弧の中の「外した hunk は後の役——判定・修正案・修正——に触らない範囲として渡る」「下書きは報告の冒頭に載り」（下流の block の振る舞いを役に前提として伝えていた。world の 3.6 と同じ決め）。「人が読んで渡す」だけを残した。
- 足した物は無い。英語にした（#764）。役の名「任せ先の役」は "the parallel-PR role"。

## 3 script の node

- `scan.py`: `INPUTS_REQUEST`・`INPUTS_BASE`・`INPUTS_CHANGED` を `os.environ.get("INPUTS_REQUEST")` などの字のままで読み、`ports.json(…, "request.schema.json")`・`ports.text(…)`・`ports.json(…, "changed.schema.json")` に渡す（口の名は土台の PR の `ports.py` に合わせる）。place を作り直し（中のファイルを全部消す）、`tree.json` に `accept.tree_state(<作業ツリー>)` を書く。それから今の `pr_scan` と同じ順: `forge.reason(forge.detect(repo))` が空でなければ `not_applicable` の素材、そうでなければ `parallel_pr_plan`（`fallback` なら役へ、`blocked` なら `not_run`）、数えを `parallel_pr_scan` で回して `parallel_pr_reply`。渡し物 `pr-brief.json` はどの道でも書く。機械が決めた時は `material-pr-check.json` と空の `pr-excluded.json`（`{node, head, excluded: []}`）を書く。中の誤りは今の `pr_check.py` と同じく捕まえて役に任せる（`go_role: true`、`reason` は「機械の道が落ちた（<型>: <文>）——役に任せる」）。
- `prep.py`: 却下の控えを `rolekit.rejected(place, "pr-check")` で読み、`prompt.render("pr-check", values, when)` で組んで返す。`values` は `brief_file`・`limit`・`lang`（空なら README の 5.3 の既定の英文）・`rejection`（却下が在る時）・`na_why`（空の字。`material-na` の断片の差し込み口）。`when` は `{"rejected": <却下が在るか>, "na_never": True, "na_cond_true": False, "na_cond_false": False, "na_judged": False}`。query-rule の断片の `spawns` は `False`。
- `take.py`: `rolekit.accept_round(place, "pr-check", INPUTS_REPLY, take, on_give_up=…)`。`take` は 4 節の順で照らす。諦めた時の控えは別に書かず、`finish` が `rolekit.given_up_reason(place, "pr-check")` を読む（今の止めの控え `write_stop(stopby.PR, …)` の替わり）。
- `read_proof.py`: 今の `pr_reads.py` と同じく落ちない（中の誤りは `{ok: false, missing: [], index_file: "", reason}` で返す）。`reads.guarded(lambda: src.proof.collect(place, reads.log_here(), repo), owner="pr-check", place=place)`。
- `finish.py`: 素材の控えを読み、`ok`・`status`・`stop_reason`・`reason`・`material`・3 つの pointer・`report` を組んで返す。決め:
  - 役を諦めた（`rolekit.given_up_reason` が空でない）: `status: failed`・`stop_reason: works:pr`・`reason` は諦めの文・`material` は `{status: not_run, reason: <諦めの文>}`。
  - 素材の控えが無い（scan が落ちて役も起きなかった・役の loop が回らなかった）: `status: failed`・`stop_reason: ""`・`material` は `{status: not_run, reason: "並行 PR の確かめが走らなかった（<訳>）"}`。`ok` は真のまま（今も止めない）。（自分で決めた。今は素材の欄が空のまま判定に進み、diagnose が「明示返答を欠く」と見る。block の出口で not_run と名指すほうが無言の空を作らない）
  - ほか: `status` は素材の札、`reason` は scan の `reason`（機械が決めた時）か空。
  - pointer は `ports.pointer(<ファイル>)`。在らないファイルは null。

## 4 受け付け（pr-check）

- 照らす順（今の `prcheck_take` の順に、6 節の 3 で落ちた照らしを 4・5 として戻した）:
  1. 返答が JSON のオブジェクト。
  2. 投稿していない: `conflicts[].handed_over` が真の行が無い。在れば `NO_POST` の文と PR の番号で拒む。
  3. 読むだけの役が作業ツリーを変えていない: `tree.json` と今の作業ツリーを `accept.tree_moved`（`TREE_KEYS` の全部）で比べる。写しが無い・読めない時も拒む（`Reject` の文）。
  4. 素材の欄: `materialkit.check_record("pr-check", ("parallel_pr",), {"parallel_pr": reply["material"]}, "never")`（素材の札の語のどれか・`carried_over` を拒む・`not_applicable` を拒む・札ごとの要る欄。今は札の語だけを見ていた。6 節の 3）。外れれば「素材の欄が記録の決まりに合わない: …」で拒む（materials の設計書の 4 節の 6 と同じ字）。
  5. 外す hunk: 今の `prcheck.check_excluded` の 5 つ（start <= end・PR が conflicts に在る・ファイルがその行の files に在る・ファイルが今の作業ツリーに在り end が行の数を超えない・note が在る）。
- 通れば: 外す hunk を `_anchored`（行の中身 `text` と `sha256` を足す）で `pr-excluded.json` に、下書き（note を持つ交差だけ）を `pr-downgrades.json` に、素材を `material-pr-check.json` に書く。拒めば何も書かない。
- 却下の理由の文は Python（`src/take.py`）が組む日本語のまま（README の 5.3）。
- 3 回目の却下で loop を抜ける（`rolekit.GIVE_UP_AFTER`）。`finish` が `status: failed` と `stop_reason: works:pr` を返す。

## 5 単独で呼ぶ

```sh
bin/works-factory <読ませるフォルダを blocks/ にする引数（名は実装で決める）> workflow run works-factory-parallel-pr \
  --cwd <対象> --input base=<差分の根の commit> \
  --input changed='["path/to/file.py"]'
```

`request` を渡せば、`changed` が空で `base` からも取れない時に行の `where` が名指すファイルを使う。remote が GitHub でない対象では役を起こさず `not_applicable` を返す。出力は `workflow get <run>` の `finish` の返り。始めの記録は要らない。殻の引数の名は（未確認）（world の 7 節と同じ。土台の PR で決める）。

## 6 元の works と graphloops の同じ場面

元の works の `works/blk-pr/`（pr-snap・pr-loop〔pr-check と pr-accept〕・pr-reads・collect）から、工場はほぼ同じコードを写した（#76 `0c4a6793`）。graphloops の `prompts/review-loop/p0.parallel_pr.md`（`graphs/review-loop.json:1833-1975`）は書き手が自分で回す節で、任せ先に落ちるのは機械が決められない時だけ。工場に無い物・違う物と、その訳:

1. 担当の PR へ投稿する（graphloops の 6 段は `handed_over: true` で投稿する）: 工場と元の works は下書きだけ。持ち主の決め 2026-09-27（元の works の `docs/specs/2026-09-29-darkfactory-single-run-design.md:33,402` の「案 (a)」）。工場の `docs/owner-decisions.md` にはこの決めの行が無く、跡は `NO_POST` の字と md だけ（（未確認）: 工場の台帳に書き写さなかった訳の記録は無い）。この block は下書きのまま。
2. 周の条件（graphloops の `parallel_pr_due`。1 周目か、判定から入る run の最初の修正の次の周で回し直し、変更ファイルの集合をその周に固めた版から取り直す）: 工場は写したが使っていない（`lib/judge_accept.py:1612` の関数を名指す節が無い。judge の `pr-scan` は判定の道で 1 回だけ走る）。（未確認）: 外した記録は無い。block は周を知らないので、回し直すかは line の `when:` の決め（line の設計書で扱う）。この block は呼ばれれば今の作業ツリーで数える。
3. 素材の札ごとの要る欄の照らし（graphloops の `check_record`〔`rules/review-loop.py:4316`〕と元の works の `b.done`。found は count と detail、clean は checked、ほかは reason が要る。carried_over を走った役が書くのを拒む）: 工場は `status` が語のどれかしか見ない（`judge_accept.py:3621-3623`）。md は「流用と書いても拒まれる」と言うのにコードは拒まない。（未確認）: 外した記録は無い。この block の受け付けで戻す（4 節の 4）。graphloops の `na_self_ok: false` に当たる「役は not_applicable を名乗れない」も戻す。
4. 役の前の作業ツリーの写し（元の works は役の直前に `pr-snap` が取った）: 工場は judge の入口か仕様の承認の後の写し `judge/judge-tree.json` と比べる（#76 から。（未確認）: 訳の記録は無い）。この block は元の works と同じく役の直前（`scan`）で取る。
5. 外す hunk の読み手: 元の works は判定・修正案・修正に渡す作りだったが配線が無く報告にだけ届いた（`darkfactory.yaml:483,689`）。graphloops は書き手の会話の記憶だけ。工場は plan・plan-review・案の直しと事前審査の頭（`planblk.head`。#699 `10535024`）・再審の材料（`judge_accept.py:3231`）・報告（`runreport.pr_lines`）・`boardview`・`pass_open` が読む。fix と diagnose には渡らず、外した範囲を直したら拒む機械の関門は無い（`fixboard.JUDGE_COPIES` に無い）。`text`・`sha256` の印を読む物はどちらのリポジトリにも無い。この block は形を変えずに出す（読み手を足すかは各 block と line の決め）。
6. 下げた物の宣言 `lib/downgrades.json`（2 行。p0.parallel_pr の投稿しない事と r2.design の作り直さない事）: 読むのは報告の頭の「下げている所: K 個」だけ（`runreport._downgrade_lines`、#264 `86c3f28c`）。`docs/nodes.json:191-199` の 7 行の一覧と数も字も合っていない。元の works は宣言の node が graph に在るかも照らした（元 `prcheck.py:322`。工場で落ちた。（未確認））。2 つの block の事を 1 つのファイルに持つ形は block の独立に合わないので、この block は自分の行だけを出力の欄 `downgrades` で返す（10 節の 8）。ファイルと読み手の組み直しは report の設計書の決め。
7. 機械の道が落ちた時（元の works の `run_helper` は 1 回やり直して、AI の前に `Refused` で止めた）: 工場は役に任せる（`pr_check.py:18-21`。持ち主の台帳 J32「起こし直しは当たらない」`docs/plans/2026-10-13-capabilities/judge.md:213`）。この block も役に任せる。
8. 拒まれた後の出し直し（元の works は理由のファイルを読ませ「名指された所だけ直せ」）: 工場は理由を貼って丸ごと出し直させる（#76・#191）。この block も丸ごと（理由は古い順に全部。2.6）。
9. 読むだけの口 `works-gh` と網の閉じた sandbox: 元の works と同じ（#21 `f1a419d4`・#103 `7cd46ab2`・持ち主の決め `roles-read-only-gh`）。工場は役の環境から GitHub のトークンを外す（#103・#152 `58ed7d4a`）と、Archon の家への書き込みの禁止（#591 `0b1afae3`）を足した。どちらも YAML のまま写す。

この block が両方より良く、残す物: `-R HOST/OWNER/REPO` のホストまで書く読み（#203 `36be5332`。GHES を取り違えない）・機械の道が落ちても役に任せる・外への検索の決まり・外す hunk が案と事前審査と再審に届く（#699）・役のトークンを外す（#103・#152）・読んだ証拠の node（#363 `22c70be3`）。

## 7 試験

- standalone の fixture（`blocks/parallel-pr/fixtures/`）:
  - `standalone.stubs.yaml`: 入力は `changed: '["a.py"]'` だけ（`request`・`base` は既定）。`scan` を `{go_role: false, reason: 機械が決めた: clean（…）}` で差し替え、`reached: [scan, finish]`。`finish` は差し替えない（`archon workflow test` が script を走らせない時は、`finish` も既定の形で差し替える。（未確認）: 筋書きが script を本当に走らせるかは今の筋書きに合わせる。今の judge の筋書きは script の node も差し替えている〔`spec-on.stubs.yaml`〕ので、それに倣って全部を差し替え、配線だけを見る）。
  - `role.stubs.yaml`: `scan` が `go_role: true`、`pr-check` が交差 1 件・外す hunk 1 件の返答、`pr-check-accept` が `{ok: true, done: true, reason: ""}`、`reached: [pr-check, pr-check-accept, pr-check-reads, finish]`。
  - `gave-up.stubs.yaml`: `pr-check-accept` が 3 回 `{ok: false, done: <3 回目だけ true>, reason: …}`、`finish` の返りの `stop_reason` が `works:pr`、run は `completed`。
- `tests/blocks/parallel_pr/test_parallel_pr.py`（試験のフォルダの名は block の名の `-` を `_` にした物。Python の package の名に `-` を使えないため）: script を子のプロセスで回す。始めの記録の無い使い捨ての `ARTIFACTS_DIR` と、remote を GitHub の URL にした git のリポジトリで、port の値だけを渡す。gh は試験の偽の口（今の `_PrBase` の `gh` の差し替えと同じく、`PATH` の頭に置いた偽の `gh` か、`src/scan.py` の口の引数）で返す。回す筋:
  - 交差なし → `scan` が `go_role: false`・`finish` が `status: clean`・`excluded` の中身が空。
  - 交差あり → `scan` が `go_role: true` → `prep` の指示に `{brief_file}` の絶対パスが入る → 台本の返答 → `take` が通す → `finish` の `drafts` の中身が `[{pr, files, note}]`、`excluded` の行に `text`・`sha256`。
  - 役が作業ツリーのファイルを 1 つ変えた返答 → `take` が拒む。
  - remote がローカルのパス → `not_applicable`、役を起こさない。
  - `changed` が空で `base` も空、`request` の `where` が追跡中のファイルを名指す → 渡し物の `changed_files` がそのファイル。
- 指示の比べ（README の 11.4。この block の PR を 2 つの commit に分ける。1 つ目は今の指示の日本語の字のまま md を置き、今の指示と同じ字になることを試験で照らす。2 つ目で md を英語にし、1 つ目の試験を消す）: 例の run の `judge/pr-brief.json` と同じ値で、1 つ目の commit では日本語の md で組んだ指示が、今の `pr-check.md` に `$pr-check-reject.output.reason` を空・`lang_line` を例の run の値・`$ARTIFACTS_DIR` を place の親に置き換えた字と同じになることを照らす（2.6 で替えた所〔渡し物のパス・却下の段落の 1 回目の文〕は、1 つ目の commit では今の字に合わせて書く）。2 つ目の commit（英語）では、2.6 の差の一覧どおりかを並べて審査に出す。
- 振る舞いの試験（今の試験から写す。`judge/` のパスを place に、`ja.pr_scan(jdir, repo)` を `src.scan.scan(place, repo, request=…, base=…, changed=…)` の形に替える）:
  - `lib/tests/test_judge_accept.py` の `PrScanCase` の全部（`test_no_crossing_is_decided_by_machine`・`test_crossing_falls_back_to_role`・`test_diff_files_win_over_request_wheres`・`test_gh_missing_falls_back`・`test_no_forge_is_not_applicable`・`test_empty_set_is_not_run`・`test_truncated_and_unreadable_wait_for_human`・`test_github_repo_redacts_token`・`test_github_repo_reads_the_url_with_forge`・`test_github_repo_takes_the_tracked_remote_first`）と `PrAcceptCase` の全部（`test_check_no_post`・`test_handed_over_true_rejected`・`test_handover_draft_accepted_with_anchor`・`test_no_conflicts_reply_accepted`・`test_excluded_checked`・`test_fallback_role_reads_only`・`test_head_move_and_ignored_paths_are_refused`）。`test_stopped_run_does_not_go` は写さない（止めの控えを読まない。4.3）。
  - `tests/workflows/test_judge.py` の `ParallelPrThroughReadOnlyGhTest.test_parallel_pr_scan_passes_the_read_only_gh`（gh の打ち方が読むだけの口の許しの表に合う）・`test_pr_check_reply_outside_the_type_is_rejected`・`test_pr_check_must_read_its_brief`・`test_pr_reads_returns_the_same_with_or_without_the_parents_config_dir`・`test_pr_check_reads_runs_after_the_role_on_the_roles_rounds`・`test_pr_check_reads_without_record_does_not_fail`。
  - 足す: `carried_over` の素材を拒む・`not_applicable` を拒む・found に count が無い返答を拒む（4 節の 4）・役を諦めた時の `stop_reason: works:pr`・素材の控えが無い時の `not_run`（3 節の `finish`）。
- 読み手の側の試験はそれぞれの block と line に残す（diagnose の素材の読み・plan と fix の外す hunk の照らし・report の行）。
- keep-essence の 12 の仕組みのうち、この block が担う物は無い（README の 10 節の割り当てに並行 PR は無い）。守るのは、外す hunk の控えの形を崩さないこと（plan・plan-review・再審の材料が読む）: `pr-excluded.json` の形（`{node, head, excluded: [{pr, file, start, end, why, text, sha256}]}`）を今と同じに保つ試験（`test_handover_draft_accepted_with_anchor` の写し）で縛る。e2e の `tests/e2e/evidence.json` の J33・J36・R80 は、node の id と place のパス（`judge/parallel-pr/…`）を新しい物に合わせる。

## 8 報告の行（`src/report.py`）

- 頭の 1 行: `並行 PR: <status の語>（<reason か detail か checked の 1 行>）`。`status` が `failed` なら `並行 PR: 確かめが終わらなかった（<reason>）`。
- 下書きの行: 今の `prcheck.draft_lines` と同じ字（`並行 PR #<pr> の担当への申し送りの下書き（<files>。投稿していない）: <note>`）。
- 読んだ証拠が欠けた時: `並行 PR の役が渡し物を読んだ記録が無い（<missing>）`。今は報告の索引で出ていた事を、この block の行で出す（自分で決めた。README の 4.1「報告の文は事実を持つ block が組む」）。

## 9 未確認

- 起動の殻で `blocks/` を読ませる引数の名と、5 節の命令の正確な形。
- `archon workflow test` が script の node を走らせるか、差し替えを要るか（7 節の fixture の書き方）。

## 10 自分で決めた事

1. 出力に `material`（素材の札）・`stop_reason`・`reads` を足した（README の 8.1 は `excluded`・`drafts` だけ）。根拠: diagnose は素材の 15 欄の 1 つとして並行 PR の札を読み（`judge_accept.py` の materials）、役を諦めた時は今 run が `works:pr` で止まる。どちらも無いと元の能力が落ちる。止めるかは line が決め、block は事実の語を返す。
2. 素材の札の語と照らしは、素材の観点の族の共通の部品 `lib/materialkit.py`（materials の設計書）から引き、断片 `works-gh`・`material-status`・`material-na` も同じ族の物を使う。この block の PR はその後に出す。根拠: 札の語は diagnose と 12 の作り手が共に読む行の形で、README の 4.1 は作り手の出力ごとに `lib/` の 1 モジュールに置くと決めた。写しを持つと 2 か所目の知る場所になる。
3. 役の前の作業ツリーの写しを、この block の `scan` が自分で取る。根拠: README の 4.3（block は自分の place だけを開く）。今は judge の入口と仕様の承認の後が取った写しを使っていたので、仕様の段が書いた受け入れテストを「役が変えた」と数えないために仕様の後に取り直していた（`spec_answer` の `snap_tree`）。block が役の直前に取れば、その取り直しは要らない。
4. 却下の理由を古い順に全部渡す（今は前の回の 1 つ）。根拠: world と同じ共通の断片を使う。#345 で他の loop に入れた形で、3 回目の役が 1 回目の誤りを繰り返すのを止める。
5. `carried_over` を受け付けで拒む（今は通る）。根拠: md が書くなと言い、block は周を持たない。
6. 素材の控えが無いまま出口に来た時に `not_run` を名指す。根拠: 無言の空を作らない（持ち主の決め `no-silent-loosen`）。
7. 読んだ証拠の欠けを、この block の報告の行で出す。根拠: README の 4.1。
8. 下げた物の宣言を、この block の出力の欄 `downgrades` で自分の行だけ返す（`lib/downgrades.json` を写さない）。根拠: ファイルは 2 つの block の事を持ち、読み手は報告の頭だけ（6 節の 6）。block はほかの block の事を持たない（憲法の 3）。
9. 素材の欄の照らし（`carried_over` と `not_applicable` の拒み・札ごとの要る欄）を受け付けに戻す（4 節の 4）。根拠: graphloops（`check_record`・`na_self_ok: false`）と元の works が持ち、工場で記録なく落ちた。md が既に「拒まれる」と言っているので、指示とコードを揃える。照らしは素材の観点の族と同じ `materialkit.check_record` を使い、`mode` は `never`（この役は『条件に当たらない』を名乗れない）。
