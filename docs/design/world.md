# block の設計書: world（世界の解）

- 何の話か: 依頼の各行を業界の定石と照合する観点「世界の解」を、単独で呼べる block `workflows/world/` にする設計。あわせて、方針の文だけを入れてこの観点（と事前審査）で評価する入口の workflow `workflows/policy-check/` の設計も書く。型は [README.md](README.md) に従う。ほかの block の設計書の手本でもある。
- 決めたこと: 今の judge の 9 つの node（world-intake〜world-finish）を、頂の 5 つ（intake・言い直しの輪・pick・web の役の輪・finish。輪は本体の prep・役・受け付けを 1 つと数える）の block にする。土台の審査の後、web が off の run のための輪を 1 つ足して 6 つになった（9.1 の 7）。入力は依頼の行・目的の文・依頼が示した解き方・web の切り替え・言語の 5 つの port だけで、run の記録を読まない。指示は 2 本の英語の md（`prompts/world-classes.md`・`prompts/world-judge.md`）にまとめる。lib の Python に在った「返し方」の文と、md と lib に二重に書いていた 11 の決まりは md に 1 回だけ書く。振る舞いは変えない（変えた所は 9.1 に名指す: `ok` の意味・web が off を道具で守る・下書きの行の拒みを配列の形にも当てる）。
- 持ち主に求めること: なし。

この文書の語は README の頭の物を使う（block・graph・port・place・prep・accept・pointer・Archon と、`returns`・`outcome_field`・`loop_group` などの Archon の YAML の鍵、form の書き方 `json(…)`・`choice(a|b)` は README の頭の語と 4 章。K の番号は今の落とし穴の一覧、keep-essence の番号は README の 10 章）。ほかに:

- 言い直す役（world-classes）: 依頼の行を、依頼が示した解き方と対象の名を外した「問題の類」に言い直し、検索語を作る AI の役。道具を持たない。
- web の役（world-judge）: 問題の類ごとに一次の出典を web で探して抜き書きを運び、定石と、依頼の解き方との比べ（same・differs・none）を決める AI の役。道具は WebSearch と WebFetch だけ。
- 抜き書きの照らし: web の役が運んだ抜き書きを、機械が同じ URL から取り直した本文に字のまま在るかで確かめること（keep-essence の 12）。
- 例の run: 本物の run `df5e111f-ea97-409b-8066-2245d32746ab`（対象 raiki61/works-factory。置き場 `~/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/artifacts/runs/df5e111f-…/judge/world/`）。骨組みの値はここから取った。

## 1 block の全体

### 1.1 役

依頼の各行について、世の中の実務家がその問題の類をどう解いているか（実践・慣習・標準）を、一次の出典の原文の抜き書きつきで集める。抜き書きが出典に字のまま在ることを機械が確かめる。依頼の解き方が定石と違えば、違いを名指して定石を推す。web に出られない run でも止めず、行を模型の知識だけで書いて、そう印を付ける。

### 1.2 port

入力（YAML の `inputs:`）:

- `request`（必須）: `json(shared:request.schema.json): 依頼の行の配列 [{where, text, mechanism?, measured?, false_positive_if?}]。それを findings の欄に持つオブジェクトでもよい（工場の依頼のファイルの形）`
- `purpose`: `text: 依頼の目的の 1 文。空は渡されていない`。既定 `""`。
- `means`: `json(means.schema.json): 依頼が示した解き方の文の配列。空の配列は示していない`。既定 `[]`。
- `web`: `choice(on|off): web で出典を探すか。off なら検索も取得もせず、行は知識だけで書く`。既定 `on`。
- `lang`: `text: 人に見せる欄（problem・activity・proposed・practice・applies・not_applies・challenge）の言語。空は依頼の行の言語`。既定 `""`。

出力（`returns: finish`、`outcome_field: ok`）:

- `ok`: boolean。`status` が `ok` か。
- `status`: `ok` か `failed`。どこかの段が落ちた・役が受け付けを通らなかった時は `failed`。空の依頼（行が 0）は飛ばした結果として `status: ok`・`rows: null`・`reason` は「依頼の行が無い」（飛ばしたことは新しい status の値でなく、この形。9.1 の 1）。
- `reason`: 日本語の 1 行（人に見せる）。落ちた段・web に出られなかった・類の上限を越えた行など。
- `rows`: pointer（`world.jsonl`。1 行が依頼の 1 行）か null。行の欄は今の `lib/worldmark.py` の `FIELDS`（finding・where・class_id・problem・activity・practice・sources・applies・not_applies・versus・basis）のまま。
- `classes`: 取った問題の類の数。`dropped`: 照らしで落とした抜き書きと、上限を越えて取らなかった抜き書きの数。
- `report`: 報告の節「世界の解」の日本語の行の配列（今の `worldmark.report_lines` が組む物と同じ中身）。

今との違い: 今は入力を `judge/request.json`・`judge/purpose.json`・`judge/purpose-means.json`・`judge/start.json`（`features_cut`）・`judge/stop.json` から名で開き（`lib/judge_accept.py:3664-3698`）、出口は `{ok, status, reason}` だけで、行と控えは `judge/world.jsonl`・`judge/world-state.json` に書いて判定の出力の欄で外へ出していた。止めの記録の確かめは無くし、回すかは graph の `when:` が決める（README の 4.3）。

### 1.3 node の並び（`workflows/world/works-factory-world.yaml`）

1. `intake`（script `intake.py`）: port を読み、place の中のこの block のファイルを名で引いて消し（place そのものは消さない。単独の run では place が run directory の根なので。README の 13 章）、`intake.json` を書く。返り `{due, findings, reason}`。
2. `world-classes-loop`（`loop_group`、最大 3 回、`fresh_context: false`、`until_bash` は accept の `done`。`when: $intake.output.due == true`）
   - `world-classes-prep`（script `restate_prep.py`。`with:` を持たない。前の回までの却下は place の控えから読む。9.1 の 6）: 指示を組む。返り `{prompt}`。
   - `world-classes`（AI。`prompt: "$world-classes-prep.output.prompt"`・`allowed_tools: []`・`mutates_checkout: false`・model `@wf-judge-core`・閉じた sandbox・`retry`・`idle_timeout: 1728000000`。`output_format` は今の `classes` のまま）
   - `world-classes-accept`（script `restate_accept.py`。`with: {reply: $world-classes.output}`）: 返り `{ok, done, reason}`。
3. `pick`（script `pick.py`。`trigger_rule: all_done`）: 取る類を `MAX_CLASSES`（5）まで決めて `plan.json` に書く。返り `{due, web, reason}`（`web` は入口が読んだ port `web` が on か。下の 2 つの輪のどちらを回すかを決める）。
4. `world-judge-loop`（同じ形。`when: $pick.output.due == true && $pick.output.web == true`）と `world-judge-offline-loop`（`when: … && $pick.output.web == false`。本体は `world-judge-offline-prep`〔script `offline_prep.py`〕・`world-judge-offline`〔AI。`allowed_tools: []`。返す形は `world-judge` と同じ〕・`world-judge-offline-accept`〔script `web_accept.py`〕）。web が off の run は道具を持たない役の輪だけが回る（9.1 の 7）
   - `world-judge-prep`（script `web_prep.py`）・`world-judge`（AI。`allowed_tools: [WebSearch, WebFetch]`・model `@wf-judge-materials`。`output_format` は今の `rows`・`excerpts` のまま）・`world-judge-accept`（script `web_accept.py`。抜き書きを取り直して照らす）。
5. `finish`（script `finish.py`。`trigger_rule: all_done`）: 行を `world.jsonl` に、段の控えを `state.json` に書き、出力を返す。どの段が落ちても落ちない（今の落とし穴 K1・K13 の決まり）。

script の名は `lib/` のモジュールの名と重ねない（README の 7.1 の 9）。今の `world_judge_accept.py` は `lib/judge_accept.py` と字が近いので `web_accept.py` にした。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、line から judge のまとめを通して include された時は `$ARTIFACTS_DIR/judge/world/`）の下に、今の `judge/world/` と同じ名で書く（`state.json` だけは今の `world-state.json` の代わり）: `intake.json`・`classes.json`・`plan.json`・`judge-input.json`・`judged.json`・`verified.json`・`rejects-classes.json`・`rejects-judge.json`・`world-classes-prompt-<n>.md`・`world-judge-prompt-<n>.md`・`world-judge-offline-prompt-<n>.md`・`prompt-error.json`（指示が組めなかった node と訳）・`world.jsonl`・`state.json`。名は `src/steps.py` だけが持つ。

### 1.5 コードの置き場

- `workflows/world/src/steps.py`: 今の `lib/worldblk.py` の中身（入口・言い直しの材料と受け付け・類の決め・web の役の材料と受け付け・出口）。指示の文（`classes_prep` の「## 返し方」と `judge_prep` の「## 返し方」）は持たず、材料の行と値だけを組む。今の `worldblk.place()`（判定の盤面のフォルダ `judge/board` の隣に `judge/world/` を組む口）は消し、置き場は `ports.place()` が決める。
- `workflows/world/src/excerpts.py`: 今の `lib/worldcheck.py`（正規化・依頼の識別子の取り出し・抜き書きの照らし）。
- `workflows/world/src/report.py`: 報告の行を値から組む（今の `worldmark.report_lines` を、控えのファイルでなく値で受ける形にした写し）。
- `workflows/world/schemas/means.schema.json`。依頼の行の形 `request.schema.json` は 2 つ以上の block が使うので `workflows/.shared/schemas/` に置く（README の 13 章）。
- 使う `lib/`: `worldmark`（行の欄と語 `FIELDS`・`VERDICTS`・`BASES`・`NOT_WEB`。ほかの block も読む行の形の正本）・`rolekit`（loop の数え・却下の控え・諦め。`accept_round`・`rejected`・`given_up_reason`）・`webget`（取り直しの口）・`oneline`・`jsonfile`。依頼の容器の読み（今の `carry.parts`）は `request.schema.json` の形で替える。

### 1.6 つなぎ方（graph の側。block には書かない）

- judge のまとめ（`workflows/judge/`）: `include: works-factory-world`、`depends_on: [purpose]`、`when:` は line が始めの記録から引いた「世界の解を回すか」。`with:` は `request: $<依頼の pointer>`・`purpose: $purpose.output.purpose_text`・`means: $purpose.output.means`・`web: <始めの記録の features_cut から line が引いた on|off>`・`lang: <始めの記録の lang>`。
- 読み手: diagnose の `world_rows`、plan の `world_rows`、plan-review の `world_rows`、line の修正前の承認ノード（定石からの外れを人に回す行。今の `gatemarks` の `WORLD_KIND` と `worldmark.world_ok`）、report の `sections`（`$world.output.report`）。
- 今の「run で 1 回」は、judge のまとめが world を 1 回だけ include し、再審の道（diagnose の `objection`）が world を通らないことで続く。

## 2 node の設計シート: world-classes（言い直す役）

### 2.1 役

依頼の各行を、依頼が示した解き方と対象の名を外した問題の類に言い直し、実務家がその類をどう解いているかを問う検索語を作る。

### 2.2 port

`intake.json` の `findings`（← port `request`）・`purpose_text`（← `purpose`）・`means`（← `means`）、前の回の却下の理由（← place の却下の控え `rejects-classes.json`。9.1 の 6）、`lang`。

### 2.3 組み立ての順（`prompts/world-classes.md`）

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: 前の回の accept の理由が空でない。断片の中の `{rejection}` ← 却下の理由（Python が組む日本語の文。5 節）。
2. 役の定義（決まった文）: 道具を持たないこと・対象を読ませない訳。
3. 芯の 1 文（決まった文、太字）。
4. 決まりの箇条（決まった文）: 1 段上の作業の種類に上がる・解き方は `proposed` へ写す・対象の名を書かない（機械が照らして拒む）・検索語の書き方・2 つにまたがる行。
5. `## Request lines` と `{findings}` ← `src/steps.py` が組む材料（番号つきの行。`where`・`text`・`mechanism`・`measured`・`false_positive_if`）。
6. `## Purpose` と `{purpose}` ← port `purpose`（空なら「(not given)」の値）。
7. `<!-- if means -->` 依頼が示した解き方の頭の 1 文と `{means}`（箇条の行）`<!-- end means -->` — 条件: `means` が空でない。
8. `## How to answer`（決まった文）と差し込み口 `{finding_count}`・`{max_queries}`（← `src/steps.py` の `MAX_QUERIES`）・`{lang}`。
9. 結びの 1 文（決まった文）: 出力の schema に合う JSON だけを返す。

md の本文の正本は `workflows/world/prompts/world-classes.md`。この設計書は上の組み立ての順だけを持ち、本文を写さない（写しがあると直す所が 2 か所になる）。

### 2.4 返す形

今の `output_format` のまま: `classes: [{finding (1 以上の整数), problem (空でない字), activity (空でない字), proposed (字), queries (字の配列)}]`。人に見せる欄は `problem`・`activity`・`proposed`（報告と承認ノードに載る）で、言語は `{lang}`。

### 2.5 描いた骨組み（例の run の値）

```markdown
You are the restater. …（決まった文）

One core rule: **do not ask about … Ask how practitioners do this kind of work.**

- Step up one level …（決まりの箇条 5 つ）

## Request lines

These were taken by the machine from the request. They are all you are given.

1. where: workflows/merge/scripts/pr_commit.py の hook_env（73 行あたり）
   text: 出口の語 deliver=pr の run で PR 用の commit を積む時、commit のフックに渡す環境を作る hook_env は、…（約 470 字）

## Purpose

出口の語 deliver=pr の run が PR 用の commit を積むとき、commit のフックが、…（約 230 字）

Means the request proposed (split from the purpose):

- hook_env を tree_run.outside_env(os.environ) に寄せる。
- 読むだけの gh を PATH の頭に置く今の形は保つ。

## How to answer

- In `classes`, give one entry for every request line above. `finding` is the line number, 1 to 1.
- …
- `queries`: 1 to 3 search queries per line …
- Write `problem`, `activity`, and `proposed` in the language of the request lines. …

Return only JSON that matches the output schema.
```

例の run は 1 回目で通ったので、却下の段落は入らない（`rejects-classes.json` が無い）。`lang` は空で、`{lang}` に既定の文が入った形。

### 2.6 今の指示との差

作り直しの時の、古い指示との差の記録。後の指示の変更では、ここに足さない。

今の指示は `workflows/judge/commands/world-classes.md`（29 行）と、`$world-intake.output.prompt` に入る `lib/worldblk.py` の `classes_prep`（:177-193）が組む本文の 2 か所に在る。

- 移した: 「## 返し方」の 6 行（`lib/worldblk.py:183-192`）と見出し 3 つ（`FINDINGS_HEAD`・`PURPOSE_HEAD`・`REPLY_HEAD`、:172-174）を md へ。lib の Python に残るのは材料の行（`_finding_lines`）と値（`MAX_QUERIES`・行の数）だけ。
- まとめた: md と lib に二重に書いていた 4 つの決まりを 1 回に（対象の名の並び md:20 と lib:185、機械が識別子を照らして拒む md:20 と lib:192、`proposed` の写し方 md:19 と lib:187-189、検索語は実践・慣習・標準を問う md:21 と lib:190）。
- まとめた: 同じ md の中で 2 回言っていた却下の段落（md:5 と md:23）を、共通の断片 `{shared:rejected}` の 1 回に。末尾の言い回し「1 回目の返答である」（4 通りに割れていた物の 1 つ）は、却下が無い時は段落ごと入れない形にして要らなくした。決まりは今と同じ「丸ごと出し直せ」。
- 移した: 言語の 1 行（`rolekit.LANG_RULE` を `$world-classes-reject.output.lang_line` で入れていた物）を md の 1 文に。汎用の欄の並び（reason・how・what・why・異議…）は、この node の人に見せる欄（problem・activity・proposed）の名指しに替えた。
- 消した: ほかの node の id（`$world-classes-reject.output.*`・`$world-intake.output.prompt`）と、差し込んだ本文の区切り「=====指示書ここから=====」「=====指示書ここまで=====」。本文は md の節になったので区切りが要らない。
- 消した: 役の定義の「新しい会話で起きている」と、後の役の名（今の指示は、後の役が web の役だと名指していた）。
- 足した物は無い。
- 英語にした（#764）。役の名「言い直す役」は "the restater"。

## 3 node の設計シート: world-judge（web の役）

### 3.1 役

問題の類ごとに一次の出典を web で探して原文の抜き書きを運び、その抜き書きから、定石がこの依頼にどう当たるかと、依頼の解き方が定石と同じか違うかを決める。

### 3.2 port

`judge-input.json`（← 言い直す役の受け付けを通った行と `pick` が取った類。依頼の行の本文は渡さない）・`intake.json` の `web`（← port `web`）・前の回の却下の理由・`lang`。

### 3.3 組み立ての順（`prompts/world-judge.md` と、その部品 `prompts/parts/world-judge.md`）

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: 前の回の却下の理由が空でない。
2. `{shared:query-rule}`（外への検索の決まり）。道具を持つ `world-judge` の md だけが持ち、道具の無い `world-judge-offline` の md には置かない（検索をしない役に検索の決まりを渡さない）。部品 `world-judge` の外（node の md）に在る。断片の中の `<!-- if spawns -->`（下請けを起こすなら、下請けへの指示にこの決まりを含めよ）には `spawns: false` を渡す（この役は Agent の道具を持たない）。
3. 役の定義（決まった文）。道具の文は web に合わせて 2 通り: `<!-- if web -->`「Your only tools are web search and web fetch」`<!-- end web -->`、`<!-- if not web -->`「You have no tools」`<!-- end web -->`（道具の無い world-judge-offline に、持たない道具を言わない）。
4. 決まりの箇条（決まった文）: 原文のまま写す・取得したページだけ・一次の情報を先に・抜き書きから定石を言う・解き方を所与にしない（「依頼は X、定石は Y」の形）・当たらない所・対象の名を書かない。
5. `## Problem classes` と `{classes}` ← `src/steps.py` が組む材料（類ごとの見出し `### Class <id>` と、問題の類・作業・検索語・依頼の行ごとの解き方の行）。
6. `## How to answer` の頭に `<!-- if web -->`（検索と取得・`excerpts` の書き方・上限 `{max_excerpts}`・下限 `{min_excerpt}`）`<!-- end web -->` と `<!-- if not web -->`（web は off。検索も取得もせず知識だけで書く）`<!-- end web -->` — 条件: port `web` が `on`。
7. 返し方の残り（決まった文）と差し込み口 `{same}`・`{differs}`・`{none}`（← `lib/worldmark.py` の `VERDICTS`）・`{min_challenge}`（← `src/steps.py` の `MIN_CHALLENGE`）・`{lang}`。
8. 結びの 1 文。

md の本文の正本は `workflows/world/prompts/parts/world-judge.md`（`prompts/world-judge.md` と `prompts/world-judge-offline.md` はどちらも、却下の段落と `{part:world-judge}` を持つ。`world-judge.md` だけが間に `{shared:query-rule}` を持つ。9.1 の 7）。この設計書は上の組み立ての順だけを持ち、本文を写さない。

md の中の `{id, url, excerpt}` は差し込み口の形（`{` の直後が小文字の名で `}` で閉じる）に合わないので、そのまま字として残る。合う形の字を書く時は `{{`・`}}` で書く（`prompt.py` の決まり）。

### 3.4 返す形

今の `output_format` のまま: `rows: [{finding, practice (空でない字), sources (字の配列), applies, not_applies, verdict (same|differs|none), challenge}]`・`excerpts: [{id, url, excerpt}]`。人に見せる欄は `practice`・`applies`・`not_applies`・`challenge`（報告と承認ノードに載る）で、言語は `{lang}`。`basis`（web か knowledge）は役が返さず、機械が付ける。

### 3.5 描いた骨組み（例の run の値）

```markdown
{shared:query-rule の本文: Rules for queries to outside services …（7 行）}

You are the web role. …（決まった文）

- Copy each excerpt word for word …（決まりの箇条 7 つ）

## Problem classes

These were taken by the machine from the restater's answer. They are all you are given.

### Class w-459d38b29048

- Problem class: 自動化ツールが利用者のリポジトリにコミットを作るとき、git のフックがツール自身の実行環境のまま走っている。…
- Activity: 自動化ツールから子プロセスや git のフックを走らせる時の実行環境の作り方
- Query: virtualenv leaking into git hooks when a tool commits via subprocess
- Query: restore user's original environment for child processes launched from an isolated tool runtime
- Query: best practice running git hooks from automation with the same environment as the developer's shell
- Means of request line 1: フック用の環境は、利用者のコマンド用の環境を作るただ 1 か所の関数を通して組み立てる。…

## How to answer

- Search for the practice with the queries …
- At most 6 excerpts in total. Each is at least 20 characters, …
- …
- `verdict`: `same` if …, `differs` if …, `none` if …
- `challenge`: only for `differs`, … of at least 20 characters. Empty otherwise.

Return only JSON that matches the output schema.
```

例の run は web が on で、取った類が 1 つなので抜き書きの上限は 6（6 × 取った類の数。5 節）。取り直しで 3 本の抜き書きが残った（`verified.json` の `kept` が x1〜x3、`dropped` は空）。材料の札（`Problem class:`・`Query:` など）は、今の日本語の札（「問題の類:」「検索語:」）を英語にした物で、Python の材料の中の短い札として残す（README の 5.3）。

### 3.6 今の指示との差

作り直しの時の、古い指示との差の記録。後の指示の変更では、ここに足さない。外への検索と出典の決まり（一次の出典を先に読む）は、土台の後に共通の断片 `query-rule` へ移した（9.1 の 8）。

今の指示は `workflows/judge/commands/world-judge.md`（41 行）と、`$world-plan.output.prompt` に入る `lib/worldblk.py` の `judge_prep`（:290-325）の 2 か所に在る。

- 移した: 「## 返し方」（`lib/worldblk.py:305-324`）を md へ。web の on と off の 2 通り（:306-314）は、差し込むかを選ぶ段落にした。見出し `PROBLEMS_HEAD`・`CLASS_HEAD`（:279-280）のうち、類ごとに繰り返す `### Class <id>` だけを Python に残した。
- まとめた: md と lib に二重に書いていた 7 つの決まりを 1 回に（原文のまま写す・機械が取り直して落とす md:27 と lib:309-310、取得したページだけ md:28 と lib:311、検索語を足してよいが名は入れない md:29 と lib:307、印は機械が付ける md:30 と lib:317-318、web が off md:31 と lib:313、「依頼は X、定石は Y」md:32 と lib:322、当たらないなら applies は空 md:33 と lib:319）。
- まとめた: 同じ md の中で 2 回言っていた却下の段落（md:16 と md:35）を共通の断片の 1 回に。
- 移した: 外への検索の決まりの塊（md:3-10。元は `lib/agents/judge.md:16-22` で、21 本の md に写されていた）を共通の断片 `workflows/.shared/prompts/query-rule.md` に。写しが字のまま在ることを縛る今の試験（`tests/workflows/test_judge.py:507-519`）は、断片が 1 つになるので要らない。
- 消した: 塊の頭の「works の包みより」（元の works の包みの名残。この block は包みを知らない）。
- 消した: md:30 の「web で確かめていない定石として名指される」（下流の承認ノードと報告の振る舞いを、この役に前提として伝えていた）。印を機械が付ける事だけを残した。
- 残した: 断片の中の「名前が要る調べは引かず、返答の型に『足りない』などの欄があればそこに書け」。この役の返答の型にはその欄が無いので、今と同じく条件の文のまま効かない（（未確認）: 欄を足すかは振る舞いを変えるので、この作り直しの外）。
- 移した: 言語の 1 行（2 項と同じ）。
- 消した: 役の定義の「新しい会話で起きている」と、Agent で子を起こす文（この役は Agent の道具を持たない）。
- 変えた: web が off の node（`world-judge-offline`）には、道具の文を「You have no tools」に替え、外への検索の決まり（`query-rule`）を渡さない（道具の無い役に、持たない道具の文と検索の決まりを渡すと、指示の中で食い違う）。
- 足した物は無い。英語にした。

## 4 script の node

- `intake.py`: `request`・`purpose`・`means`・`web` を `os.environ.get("INPUTS_REQUEST")` などの字のままで読み、`ports.json(…, "request.schema.json")` などに渡す。place の中のこの block のファイル（`src/steps.py` が名を持つ物と `world-*-prompt-*.md`）だけを消して `intake.json` を書く。place は作るだけで消さない（単独の run では place は run directory の根。README の 13 章）。依頼や目的が読めない時も落ちず、`due: false` と理由を返す（今のまま。出口は `status: failed` で、その理由を `reason` に書く）。
- `restate_prep.py`・`web_prep.py`: `rolekit.rejected` で place の却下の控えを全部読み（`$LOOP_PREV` は使わない。9.1 の 6）、`prompt.render("world-classes", values, when)` で組んで返す。今の `worldblk._prep` が `rolekit.with_reject` で頭に却下を貼っていた道（今の流れでは通らなかった。棚卸し `~/.cache/works-self/tmp/inventory-765.md` の 10.1）は無くなり、却下の段落は md の 1 か所に決まる。
- `restate_accept.py`・`web_accept.py`: 今の `judge_accept.world_accept` と同じく `rolekit.accept_round` で回の数えと諦めを持ち、`src/steps.py` の受け付けを呼ぶ。`web_accept.py` は取り直しの口 `webget` を使う（試験では差し替える）。
- `pick.py`: 今の `worldblk.plan`。
- `finish.py`: 今の `worldblk.finish` と `judge_accept.world_finish` を 1 つにした物。行と控えを place に書き、`rows` を pointer で、`report` を `src/report.py` で組んで返す。

## 5 受け付け（どちらの役も）

- 却下の理由の文は Python（`src/steps.py` の `class_problems`・`judge_problems`・`_excerpts`）が組む。日本語のまま（loop を諦めた時に `reason` を通って報告に載るため。README の 5.3）。中身は今のまま（依頼の行の数と番号・重なり・空の欄・検索語の数・依頼の識別子・`verdict` と `proposed` の食い違い・`differs` の `challenge` の長さ・`sources` が `excerpts` の id か）。
- 拒否を足す道: 返答の形で決まる拒否は `src/steps.py` の `class_problems`・`judge_problems` に、抜き書きを取り直した後で決まる拒否（残った抜き書きの数など）は `_take_judge` の `_check_excerpts` の後に `bad` として足す。理由は `rolekit.accept_round` が控えに積み、次の回の `{shared:rejected}` に載る。`scripts/web_accept.py` は `steps.accept` を呼ぶだけ（docstring の受け付けの説明も同じ変更で直す）。試験は `tests/blocks/world/test_steps.py` の Classes・Judge・Verify。
- 3 回目の却下でloop を抜ける（`rolekit.GIVE_UP_AFTER`）。run は止めず、`finish` が `status: failed` と、落ちた役の最後の却下の理由を `reason` に書く。
- 抜き書きの照らし: `web_accept.py` が、通った返答の抜き書きを同じ URL から取り直し、正規化した本文に字のまま無い物を落とし、それを指す `sources` も外す。根拠が残った行は `basis: web`、残らない行は `basis: knowledge`。上限（6 × 取った類の数）を越えた分は頭から取り、取らなかった数を残す（今のまま）。

## 6 元の works と graphloops の同じ場面

元の works の `works/blk-world/`（入力 3 つ・出口 6 欄の独立したブロック）から、工場はほぼ同じコードを写した。工場に無い物・違う物と、その訳:

- 独立したブロックの形: 工場は judge の中に直に置き、`judge/` の決まったファイルを読む形にした（#76。`消した計画（git の履歴。ab47a4d の版で読める）docs/plans/2026-10-12-blocks/judge.md:64`）。この block で元の形（入力だけで動く）に戻す。
- ループの回ごとの支度の node（元の world-classes-prep・world-judge-prep）: 工場は world-intake・world-plan に畳み、却下の理由を reject の node で渡す形にした（#100）。この block は、回ごとの prep に戻す（README の 5.2 の「AI の node ごとに prep 1 つ」の形）。働きは同じ。
- run で 1 回の歯止め（元の `line_edge.py:1027` は控えが在れば回さなかった）: 工場に無い（（未確認）: 意図の記録なし）。この block では 1.6 の配線（judge のまとめが 1 回だけ include する）で同じ事になる。
- 出口での行の検査（元の world_edge が行を読めるか確かめた）: 工場は読み手の `stage_rows` が弾く形にした（#334）。この block の `finish.py` は行を自分で書くので、書く前に `worldmark` の行の形で確かめる（読み手の確かめも残る）。
- 関所の判定に目的の文の出典 `source_files` を使っていた所: 工場は意図して外した（#365「目的の審査を走り直すための物で、意味が違う」）。この block は関わらない（判定は line の承認ノードの側）。
- 行の型のファイル `world-row.schema.json`: 工場に無い（#29、`docs/plans/2026-10-12-lib-port.md:180` が型を読む試験を外すと決めた）。この block では `lib/worldmark.py` の `FIELDS` を正本のまま使う。`lib/worldmark.py:5` の docstring に残る型ファイルの名は、組み込みで直す。
- web が off の道: 工場では機能を切ると段ごと飛ぶので、off の道には実際は届かなかった（`lib/judge_accept.py:3685`）。この block では port `web` で単独の run から off を選べるので、off の道が初めて実際に使える道になる。

graphloops の `prompts/review-loop/p1.external_standards.md` にあって、この block に無い物（順位 ranked・diff_at・why_not_higher、見た範囲と見ていない範囲、「定石は無い」という結論、一次情報とブログの区別、受容済みの弱点の照らし直し、機構を変えた周での回し直し、対象と依存を読むこと）: どれも工場の素材の観点 external-standards（`workflows/judge/commands/material-external-standards.md`）がそのまま持つ。世界の解は「対象を読まずに上の類に上がる」ための別の観点で、元の works の計画（5.2 節「対象の木は読まない」、5.4 節「1 回だけ」）が意図して持たせなかった。この block にも足さない。「定石は無い」と言える道と、一次情報とブログの区別は、振る舞いを変える提案なので、この作り直しの後に別に扱う。

この block が両方より良く、残す物: 抜き書きを機械が取り直して照らす（graphloops は役の自己申告だけ）・web の役に渡る 4 つの欄から対象の識別子を機械が弾く・根拠の印を機械が付ける・依頼の解き方を目的の文から分ける・下流で答えを強制する（修正案は行ごとに答える、承認ノードは外れを人に回す）・#365 の照らしの精度・却下の理由を古い順に全部渡す（#351）。

## 7 単独で呼ぶ

```sh
bin/works-factory workflow run works-factory-world --cwd <対象> \
  --input request='[{"where":"README","text":"…直したい事…"}]' \
  --input purpose='…' --input web=on
```

読ませるフォルダは起動の殻が `pack.json` の `ours.folder`（`workflows/`）から決める（README の 3 節）。出力は `workflow get <run>` の `finish` の返り。始めの記録は要らない。

## 8 試験

- standalone の fixture（`workflows/world/fixtures/`）:
  - `standalone.stubs.yaml`: 入力は `request`（JSON の字）・`purpose`・`means`・`web: off` だけ。`reached` に `finish`。
  - `web-on.stubs.yaml`: web が on の道（web の役の指示の on の段落まで。抜き書きは返さない。9.1 の 4）。
  - `gave-up.stubs.yaml`: 言い直す役の返答が受け付けを通らず、`finish` が `status: failed` を返し、run は `completed`（dry-run の輪は 1 周なので却下は 1 回。輪が終わった時に言い直しの行の控え `classes.json` が無いので、出口は諦めの数に届かなくても `failed` にし、最後の却下の理由を `reason` に書く。9.1 の 4）。
  - 筋書きは `expect: completed` と `reached` と指示の字だけを見る。受け付けが拒んでも出口は `status: failed` で run は completed なので、拒否を足しても筋書きは直さない。
- 0 行の依頼の試験は `tests/blocks/world/test_steps.py` の Intake。依頼の容器の拒み（知らない鍵・下書きの行）も同じ所と `tests/blocks/shared/test_requestrows.py`。空の依頼の不具合は world の `src/` と、この Intake か `test_world.py` の `FlowCase` で閉じる（共通の口と設計書は直さない）。
- `tests/blocks/world/test_world.py`: script を子のプロセスで回す。始めの記録の無い使い捨ての `ARTIFACTS_DIR` と git のリポジトリで、port の値だけを渡し、`intake` → `restate_prep` → 台本の返答 → `restate_accept` → `pick` → `web_prep` → 台本の返答と偽の取り直し → `web_accept` → `finish` と回し、`rows` の行と `report` の行を照らす。
- 指示の比べ（README の 11.4 の、block ごとの 2 つの commit の形。土台の PR では作っていない。9.1 の 11。作る時は）: 例の run の `intake.json`・`judge-input.json` と同じ値で、1 つ目の commit では日本語の md で組んだ指示が今の `classes-prompt-1.md`・`judge-prompt-1.md` と md の本文を合わせた物と同じ字になることを照らす。2 つ目の commit（英語）では、2.6 と 3.6 の差の一覧どおりかを並べて審査に出す。
- 振る舞いの試験（今の試験から写す）: `lib/tests/test_world_check.py` の全部（Verify・Banned）・`lib/tests/test_blk_world.py` の Classes・Plan・Verify・Judge・Intake の大半・`lib/tests/test_judge_accept.py` の `WorldStageCase`（`judge/` のパスを place に替える）・`tests/workflows/test_judge.py` の `test_world_stage_without_rows_returns_no_world` と `…_with_a_broken_row_…`。
- 写さない試験（古い中身だけを見る）: `lib/tests/test_blk_world.py` の `test_wording_flag_is_not_an_exception`・`test_reply_class_id_is_ignored`・`test_exit_has_no_cache_or_skip_counts`・`test_intake_has_no_cache_root` と、旧の引数に合わせる助け `accepted()`（:68）、`lib/tests/test_worldmark.py::Notes.test_no_unit_note_or_where_paths`、`tests/workflows/test_judge.py:1912-1923`（元の works の md の hash と node の名の置き換え）・:1239・:1248（`judge/` のパス）。
- 読み手の側の試験はそれぞれの block と line に残す: `tests/workflows/test_plan.py::AcceptCase.test_world_row_needs_answer`（plan）・`tests/workflows/test_plan_review.py::WorldGateCase`・`WorldGateRunCase`（plan-review と line）・`lib/tests/test_worldmark.py` の Files・Answers（KEEP）・`lib/tests/test_runreport.py` の world の 4 件（report の行は world の `src/report.py` の試験へ）。
- keep-essence の 12（世界の解に照らす）を守るのは: 抜き書きの照らし（Verify）・識別子の弾き（Classes・Banned）・`differs` の `challenge`（Judge）・行ごとの答えの強制（plan の試験）・依頼を出どころにした外れが人に回る（plan-review と line の試験）。e2e の `tests/e2e/evidence.json` の J05・J23・J112・R79・P030・P229・P233 は、node の id と place のパスを新しい物に合わせる。

## 9 入口の workflow: policy-check（方針の文だけを評価する）

#765 の目指す形 4。方針の文（直し方の案）だけを入れて、世界の解と事前審査の観点（案の欠陥を探す review）で評価し、結果を返す。graph なので `include:` を持つ。

port（入力）:

- `policy`（必須）: `text: 評価する方針の文（直し方の案）`。
- `problem`: `text: 何が困っているか（依頼の文）。空なら方針の文を依頼の行として使う`。既定 `""`。
- `purpose`: `text: 目的の 1 文。空は渡されていない`。既定 `""`。
- `web`: `choice(on|off)`。既定 `on`。`lang`: `text`。既定 `""`。

出力（`returns: result`、`outcome_field: ok`）: `ok`（どちらの観点も最後まで回ったか）・`world`（world の返り丸ごと）・`holes`（事前審査の欠陥）・`report`（日本語の行）。

node:

1. `policy-in`（script）: 依頼の行を組んで place に `request.json` を書く。`problem` が空でなければ行は `[{where: "依頼", text: problem}]`、空なら `[{where: "方針", text: policy}]`。解き方は `policy` を箇条の行ごとに割った配列（箇条が無ければ全体を 1 つ）。返り `{request (pointer), means, purpose, web, lang}`。値を include へ運ぶのはこの node だけにする（include の `with:` に `$INPUTS` を書けるかは（未確認）なので頼らない）。
2. `world`（`include: works-factory-world`）: `with:` は `request: $policy-in.output.request`・`means: $policy-in.output.means`・`purpose`・`web`・`lang` を `policy-in` の出力から。
3. `review-run`（`include: works-factory-plan-review`。`trigger_rule: all_done`。id は plan-review の中の役 `review` と分ける。judge-eyes.md の 1.3 の「include の id」）: plan-review の text の形（README の 8.2）。`with: {proposal: <policy の文>, purpose, world_rows: $world.output.rows, lang}`。土台の PR では置かず、plan-review の PR が足した（README の 11.1）。
4. `result`（script。`trigger_rule: all_done`）: world と review の返りをまとめ、`differs` の行（依頼は X、定石は Y）と欠陥を先頭に並べた `report` を組んで返す。`holes` は review が受けた返答の `faces`、`ok` は world と review の両方の `ok`（review が回らなければ偽）。

承認ノードは持たない。定石からの外れを人に回すのは line の修正前の承認ノードの仕事で、この入口は結果を返すだけ。

試験: `workflows/policy-check/fixtures/standalone.stubs.yaml`（入力は `policy` だけ）と、`tests/blocks/policy-check/` の `policy-in` の行の組み方の試験。

## 9.1 土台の PR で決めた事

1. `ok` は `status == "ok"`（1.2 のとおり）。今の `world-finish` はいつも `ok: true` だった。単独で呼ぶ人が `outcome_field:` で落ちを知れるようにする。空の依頼（行の配列が空）は今どおり `status: ok`・行なし（`rows: null`）で、`reason` は「依頼の行が無い」。
2. 行の無い出口は `rows: null`（空のファイルの pointer を返さない。Archon は返りの pointer の先が空でないかを照らす）。
3. port の読めない入力は、どの port かを頭に付けた理由（「入力 request: …」）で `reason` に残す。
4. 筋書き: `web-on.stubs.yaml` は web の役の指示の on の段落までを見る（抜き書きの取り直しは網に出るので、抜き書きを返さない）。抜き書きが残る道は `tests/blocks/world/test_steps.py` の Verify が、取り直しの口を差し替えて見る。`gave-up.stubs.yaml` は dry-run の輪が 1 周で終わるので却下は 1 回で、出口が最後の却下の理由で `status: failed` を返す所を見る。3 回で諦める数えは同じ試験の Plan が見る。
5. standalone の筋書きの依頼の字に `$ARTIFACTS_DIR` を入れ、組んだ指示の中で字のまま AI の node に届くことを照らす（README の 13 章）。
6. 前の回の却下は、prep が place の控え（`rejects-classes.json`・`rejects-judge.json`）から全部を読む。prep の `with:` に `$LOOP_PREV…reason` を書かない。止めた Archon は `with:` の値を読み直さないが（README の 13 章）、resume で輪が 1 周目から回り直しても却下の段落が抜けないようにする。
7. web が off の run は、指示の文（`<!-- if not web -->` の段落）だけでなく道具で web を断つ: `pick` が `web` を返し、web が on なら `world-judge-loop`（`WebSearch`・`WebFetch`）、off なら `world-judge-offline-loop`（道具なし）のどちらか 1 つが回る。2 つの役の指示は同じ md `prompts/parts/world-judge.md` から組む（node ごとの md は却下の段落と `{part:world-judge}`。外への検索の決まりは道具を持つ node の md だけ）。loop の本体の node の `when:` で外の node を読む形は使わない（本体は閉じた小さな DAG）。
8. 一次の出典を先に読む決まりは、world-judge の md から共通の断片 `query-rule` へ移した（役の定義 `role-investigator` の同じ文も）。外への検索と出典の決まりは断片 1 か所。
9. 依頼の容器は共通の口 `workflows/.shared/requestrows.py` で読む（形の照らしの後に `lib/carry.parts`）。今の `worldblk._findings` が拒んでいた知らない最上位の鍵と下書きの行を、ここでも拒む（下書きの行は行の配列の形でも拒む）。
10. 指示が組めない prep は `prompt-error.json` に node と訳を書いてから落ち、出口の `reason` がその訳を名指す。
11. 指示の比べ（8 節・README の 11.4 の 1 つ目の commit の日本語の md の字の一致）は、この PR では作らない。md は 2.3・3.3 の英語の本文をそのまま置いた。古い指示と新しい指示を同じ値で並べた物は、PR の審査に出す時に作る。

## 10 未確認

- include の `with:` に `$INPUTS.<名>` を書けるか（9 節では使わない）。
- dry-run は include の中の loop の本体の node に include の道を渡さない（README の 13 章）。policy-check の筋書きは world の言い直しの輪の本体を差し替える。
- query-rule の断片の「足りない」の欄の文を、欄の無い役に残してよいか（今と同じ振る舞い。3.6）。
- `prompt:` に入る指示の大きさの上限（この block の指示は約 3 KB で、今の `$world-intake.output.prompt` と同じ大きさ）。
