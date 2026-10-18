# 止めた Archon の後の upstream を調べ、上げるかを決める材料（#636）

## 冒頭

- 何の話か: works-factory が止めて使う Archon（今は `64ec0c2e`）の後に、upstream（`coleam00/Archon`）の既定の枝 dev は 2026-10-18 の `a972888a` まで 24 commit 進んだ。その 24 commit が埋め・頼っている振る舞い・ASF の型に何をするかを調べ、#659（子の run ごとのモデル）と #671（名指しの会話）の前提を Archon の源で確かめた。issue #636 の本文が挙げた変化（#3961・#4029・#4218・#4220・#4129・#4221・#4179・#4235・#4189・#4188）は、どれも既に止めた版に入っている。
- 分かったこと: 24 commit は Archon の中のファイルの分け直し（本文が振る舞いを変えない移しと言う物）と ASF の merge queue・審査の直しで、埋め P1〜P14 は塞がらず、壊れもしない。上げると赤になるのは約束の試験の 2 行だけ。#659 が要る「子の run ごとにモデル・effort・設定を替える口」は止めた版にも upstream の頭にも無い。#671 の名指しの会話は、1 つの run の中ではループの周をまたいで続き、待ちで止まった run の resume でも続くが、落ちた run の resume では前の会話を捨てて元のノードから分かれ直し、run をまたいでは（周の鎖の次の周も）続かない。
- 読者に求める物: 持ち主に 1 点。推し「`asf-follows-dev` のとおり、別の issue で dev の頭へ上げる（下の手順）。#659 は Archon に口が無いので、周の鎖の作りを変えるかを決め直す」を採るか。

## 語

- 止めた版: `factory/pack.json` の `integration_revision_required` の `64ec0c2e25df1306b4692b4e4851079a32bccd9f`（package の版は 0.12.1）。下では「pin」と書く。
- 頭: 2026-10-18 に読んだ upstream の dev の `a972888a7a30a669a3a771e7caef512197de6ac4`（package の版は同じ 0.12.1）。下では「head」と書く。
- 引用の形: `<ファイル>:<行>` は Archon の源の根からの相対（`packages/workflows/src/` の下の物は `workflows/src/` を略して書く所がある）。pin と head で行が違う時は `pin:<行>`・`head:<行>` と分けて書く。片方だけの時は両方で同じ行。
- 名指しの会話（Named owner sessions）: `loop_group` の中の `command:`・`prompt:` のノードが `context: { resume: <ループの前のノード> }` で、ループの前のノードの会話を分けて（fork）続ける仕組み（upstream の #3961、`52eb18be8`）。

## 比べた元と調べ方

- 比べた元は止めた版 `64ec0c2e`。本文の `d97d00ef` からの 186 commit は、2026-10-16 の `355f1867` への上げ（#637）と 2026-10-18 の `64ec0c2e` への上げ（#716）で読み、名簿と `docs/design.md` に反映済み（`git log d97d00ef..64ec0c2e` は 273 commit）。本文の挙げた 10 の PR の commit は、どれも `git merge-base --is-ancestor <commit> 64ec0c2e` が真（#3961 `52eb18be8`・#4029 `ca501e324`・#4218 `355f1867a`・#4220 `54ec4fb7b`・#4129 `6e4f2a60a`・#4221 `c187c8fce`・#4179 `5744bdf79`・#4235 `f38d8a39b`・#4189 `4bb58d6ea`・#4188 `fcfeac400`）。
- 調べ方は `docs/polyfills.md` の「上流の確かめ方」の 4 段。`git log 64ec0c2e..a972888a -- <証拠のファイル>` を名簿の証拠のファイルの全部に当て、名簿の「」の引用 47 個が pin と head の両方でちょうど 1 か所に在ることを照らした。
- 24 commit の分け（題と本文を全部読んだ）:
  - Archon の中の分け直し（本文が振る舞いを変えない移しと言う物。字のとおり「No behavior change」か「Function bodies are unchanged」と書くのは `14de72582`・`d710c428a`・`50a9e0848` で、ほかは中身を「verbatim」に移す・順は前と同じ・呼び手の import は変わらない、と書く）: `14de72582`（#4487。`dag-executor.ts` から `dag/` の 5 ファイルへ）・`1472899c3`（#4491。CLI の `workflow.ts` から `workflow-list.ts`・`workflow-node-summaries.ts` へ）・`b24e39328`（#4473。`workflow-shared.ts` へ）・`7bd009122`（#4477）・`d710c428a`（#4493）・`50a9e0848`（#4509。`core/src/db/workflows.ts` を `workflow-run-*.ts` へ）・`07ee6c251`・`294f1f237`・`cbc231d08`（server の `api.ts` の分け）・`50f016b03`（#4483）・`144ee9395`・`cb3f0cd7a`・`19eeb7f59`（setup の分け）。
  - 試験の置き場と CI だけ: `1ad5e34fc`・`f9a324fe2`・`336d13f60`・`675e10eab`。
  - Archon の振る舞いの直し: `32baacecd`（#4513。file-store の錠の作業ファイルが、持ち主の落ちた後に空でも片付く）・`23338cfc2`（#4508。project の名の変更が大小文字違いの重なりを拒む）・`3909b402f`（#4506。会話の題を作る記録に本文を載せない）。どれも works-factory が頼る振る舞いに触れない。
  - ASF の直し: `55c249688`（#4500）・`bfe20c416`（#4488）・`a972888a7`（#4518）は merge queue、`37d19c953`（#4517）は審査の行き先。

## 求め 1: 埋めの名簿 P1〜P14 に照らす

| 埋め | head で塞がったか | 効き方が変わったか |
| --- | --- | --- |
| P1 | いいえ | いいえ |
| P2 | いいえ | いいえ |
| P3 | いいえ | いいえ |
| P4 | いいえ | いいえ |
| P5 | いいえ | いいえ |
| P6 | いいえ | いいえ |
| P7 | いいえ | いいえ |
| P8 | いいえ | いいえ |
| P9 | 既に外した（`docs/polyfills.md` の「外した」） | — |
| P10 | いいえ | いいえ |
| P11 | いいえ | いいえ |
| P12 | いいえ | いいえ |
| P13 | いいえ | いいえ |
| P14 | いいえ | いいえ |
| 候補: 後のノードのモデルの付け替え | いいえ | いいえ |

- 証拠のファイルのうち、24 commit が変えたのは `packages/workflows/src/dag-executor.ts`（P5・P8）と `packages/workflows/src/executor.ts`（候補）だけで、どちらも `14de72582` の分け直し。P5 の引用「sandbox: node.sandbox ?? workflowLevelOptions.sandbox,」・P8 の引用「A binding never falls back to 'if_skipped' for a failed producer」・候補の引用「Cannot supply model overrides when resuming an existing workflow run.」（`executor.ts` head:2100）は head にも 1 か所ずつ残る。
- ほかの証拠のファイル（`core/src/operations/workflow-operations.ts`・`schemas/workflow-run.ts`・`schemas/dag-node.ts`・`include-expander.ts`・`cli/src/cli.ts`・`paths/src/archon-paths.ts`・`guides/hooks.md`・`providers/src/claude/provider.ts`・`binary-resolver.ts`・`artifact-pointer.ts`・`guides/authoring-workflows.md`・`guides/loop-nodes.md`・`plugins.ts`・`template-walker.test.ts`・`schemas/run-config.ts`・`providers/src/claude/config.ts`・`core/src/services/run-owner-stop.ts`・`core/src/providers/process-provider.ts`・`exec-environment.ts`・`utils/idle-timeout.ts`・`model-validation.ts`・`cli/src/dispatch-guards.ts`）は `git log 64ec0c2e..a972888a` が 0 件。
- 証拠のファイルの外で塞いだ commit も無い（題と本文の全部を読み、上の分けのとおり）。P13 に近い `core/src/db/` の分け（`50a9e0848` の `cancelWorkflowRun` など）は「Function bodies are unchanged」。
- 名簿の各行の「上流（… dev の `64ec0c2e2` まで）」は、上げずに書き直すなら `a972888a` まで「塞がっていない」と書ける（この文書では名簿を書き換えない）。

## 求め 2: 「Archon の分かっていること」で変わった物

`docs/design.md` の「Archon の分かっていること」と U1〜U8 の項目のうち、24 commit で振る舞いが変わった物は無い。在り処が動いた物は次の 3 つで、どれも中身は同じ。

- `workflow:` の子の run の結果の読み（「`workflow:` のノードが起こした子の run の結果ごとに…」の項）: `childOutcomeFromRun` が `dag-executor.ts` pin:919 から `dag/child-run.ts` head:97 へ（`14de72582`）。
- U6 の `listRunEvents`: CLI の `commands/workflow.ts` pin:4143 から `commands/workflow-node-summaries.ts` head:203 へ（`1472899c3`）。design.md の在り処の字は上げる時に直す。
- `workflow get --verbose` のノードの一覧（`buildNodeSummaries`）も同じく `workflow-node-summaries.ts` へ。これは約束の試験が字で縛っているので、上げると赤になる（下の「上げる時の手順」の 2）。

`tests/shared/test_archon_contract.py` の `ARCHON_ROWS` 64 行を head の源に当てると、赤は次の 2 行だけ（同じ字は head の `packages/cli/src/commands/workflow-node-summaries.ts` で同じ値に当たる）。

- 「節が済んだ状態」（`case 'node_completed': {` の後の `state: 'completed'`）
- 「節の一覧の行の id と状態の鍵」（`summaries.set(<id>, { <id>, <状態の鍵>: 'completed'`）

ほかに、試験・lib・境のコメントが `dag-executor.ts` の行番号を書いている所（`tests/workflows/test_line.py` の 9716-9727 行・9664-9666 行、`tests/workflows/test_returns_never_fail.py` の 495-533 行）は、pin でも既に合っておらず、`14de72582` でさらにずれる（`bodyStepNamePrefix` が pin:4652 から head:4309、`getStaleCachedDependencies` が pin:9964 から head:9401）。字の照らしは無いので赤にはならない。

## 求め 3: ASF から採れる型

ASF（`.archon/workflows/sdlc/`）の変化のうち、works-factory の役の指示書とグラフに型として採れる物。根の `AGENTS.md` の E8 のとおり、字は写さず型だけ採る。どれも採るかは別の issue で決める。

- 周ごとの新しい会話と、commit と `Next session` の引き継ぎ（#4218、`355f1867a`。pin に在る）
  - ASF: `.archon/workflows/sdlc/implement/archon-implement.yaml`:31-38（`loop:` の `fresh_context: true`・`max_iterations: 5`）と `implement/commands/implement.md`:58-73。区切り（seam）でだけ会話を終え、`implementation.md` の `Next session` に「済んだ物・残り・決めとその訳・逸れ・次に読むファイル・回した確かめ」を書く。62 行「Where the handoff and the committed code disagree, the code decides.」。仕事を終える会話が `Next session` を消す（73 行）。
  - works-factory の今: 計画と報告の書き手は周ごとに新しい会話で、引き継ぎのメモ（`lib/handoff.py`、欄は `read`・`kept`・`set_aside`・`open`。埋め P10）を受け付けが控えに置く。
  - 採れる型: 「メモとコードが食い違えばコードが決める」の一文と、「区切りでだけ会話を終える」の決まりを、引き継ぎのメモの頼み（`handoff.ASK`）に足す。修正役が直しを複数の会話に分ける時の運び方にも使える。
- 審査は PR 自身の変更だけを見て、類ごと直す（#4220、`54ec4fb7b`。pin に在る）
  - ASF: `review/commands/review-scope.md`:53（続きの審査は、前の周の審査済みの commit から今の commit までの差のうち、base の merge で入った物を除いた「この変更の分」だけを見る）と `review/commands/review-synthesize.md`:47（同じ仕組みの指摘は、有限の類を今まとめて調べ、1 つの指摘にする）。
  - works-factory の今: 独立の目（`workflows/eyes/`）は累積の差分と試験の前後の結末を見る（`workflows/eyes/commands/r2-compare.md`:36）。修正の規則（`workflows/fix/commands/fix-rules/`）と判定の類（`workflows/judge/commands/world-classes.md`）は類の考えを持つ。
  - 採れる型: 再審と 2 度目の修正の目に「前の周から今までの、この変更の分だけ」を渡す。2 度目に出た同じ仕組みの指摘は、類の全部を一覧にして 1 つにする。
- 2 度目の指摘は類の一覧つきの直しへ、範囲の問いは人へ（#4517、`37d19c953`。head にだけ在る）
  - ASF: head の `review/commands/review-synthesize.md`:47（2 度目の指摘は「name the class and both raises, list every affected member you can find, and return `correct`」。pin:47 では `replan`）と :124-125（`replan` は設計を替える時だけ、範囲を越えるかの問いは `needs_human`）。`build-queue/commands/answer.md`:21 は、人の答えで解ける問いで止まった PR を計画し直さずに続ける。
  - works-factory の今: 事前審査と独立の目が計画のやり直し（承認ノード `gate-replan`）へ回す道を持つ。
  - 採れる型: 同じ指摘の 2 度目と範囲の問いを、計画のやり直しに回さずに分ける。commit の本文は 10-10 からの 31 回のやり直しのうち約 18 回がそれだったと言う。
  - もう 1 つの効き目: works-factory 自身を作る ASF の run（`factory/pack.json` の `entries`。この文書を書いた run もそれ）は、上げれば #4517 の審査の行き先で回る。
- 想像した危険に手を打たない（#4398、`9465b9536`。pin に在る）
  - ASF: `implement/commands/implement.md`:49・54 と `review/commands/review-synthesize.md`:80（「Models, you included, overrate imagined risks.」。今の支えられた道が届かない落ちに守り・確かめ・試験を足さない）。
  - 採れる型: 修正の規則と独立の目の指示書に、指摘は今そこへ届く道を名指す、という決まりを足す。

## (a) #659 のため: 子の run ごとにモデル・effort・設定を替える口

結論: pin にも head にも無い（関わるファイルは 24 commit で中身が変わらず、`executor.ts` は import の 1 行、`dag-executor.ts` は分け直しだけ）。周の鎖が `workflow:` のノードで起こす子の run は、親の run が記録した AI の設定の写しを、モデルの付け替え・群の別名ごと継ぐ。

- `workflow:` のノードの欄: `schemas/dag-node.ts`:1112-1122 の `workflowNodeSchema` が足すのは `kind`・`workflow`・`input`・`with`・`isolation`・`fan_out` だけ。土台の `model`・`effort` は書けるが、:2102-2109 の変換が「aiOnly / shared(retry) / exec-only base fields are dropped」で捨てる。捨てる一覧は :1294-1297 の `WORKFLOW_NODE_IGNORED_FIELDS`（:1185-1205 の `BASH_NODE_AI_FIELDS` に `model`・`effort`・`provider` が在る）。読み込みは誤りでなく警告だけ（`loader.ts`:805-825「is not supported on this node type … ignored at run time」）。
- 子の AI の設定の出どころ: 子を起こす所が `{ aiConfigurationRun: parentRun, inheritAiConfiguration: true }` と `modelOverrideLayer: { kind: 'resolved', overrides: resolvedModelOverrides }` を渡す（`executor.ts` pin:1489-1491・head:1490-1492）。`run-preflight.ts`:141-143 が親の記録の写しを読み、:159 の `restoreRunAiConfigurationDefaults` が `assistant`・`assistants` を親の物で置き換え、:172-173 が群の別名と tiers を `snapshot.baseAiProfile`（親の物）にし、:206-207 がモデルの付け替えを `snapshot?.modelOverrides`（親の物）にする。:144-158 の「Cannot override AI configuration inherited from a recorded run.」の拒みは `inheritAiConfiguration` の時は走らないが、写しが勝つので子の `--config` の層の `assistant`・`assistants`・`tiers`・`aliases` は効かない。
- 子を起こす引数そのものに AI の欄が無い: `RunChildWorkflowArgs`（pin の `dag-executor.ts`:855・head の `dag/child-run.ts`:33）。`fan_out:` の子も同じ写しを受ける。
- `with:` の入力でモデルを選べない: 置き換えの効く欄の一覧 `template-walker.ts`:77 の `SLOT_SPEC` に `model`・`effort` が無い。`effort:` は enum（`schemas/dag-node.ts`:255）なので `$INPUTS` を書けば読み込みで落ちる。
- 続きの run も付け替えを拒む: 「Cannot supply model overrides when resuming an existing workflow run.」「Cannot supply a run config when resuming an existing workflow run.」（`executor.ts` pin:2097-2103・head:2098-2104）。
- 子の YAML のノードが書いた `model:`・`effort:` は、継いだ写しの既定より先に効く（`model:` は `node-model-resolution.ts`:104-127 の `resolveNodeModel` がノードの字を先に読み、写しの `aiProfile` の別名の表で解く。`effort:` は `dag-executor.ts` pin:2193・head:1986 の `nodeConfig.effort ?? assistantEffort`）。ただし works-factory のノードは `model: '@wf-<群>'` の別名だけを書き（`workflows/AGENTS.md` の E7）、別名は親の写しで解ける。

#659 の求め 1（次の周の子の run に `--config` か `--model` で渡す）は、今の周の鎖の形（Archon の `workflow:` のノードで子を起こす）では Archon の口が無くて書けない。残る道は 3 つで、どれも持ち主の決めが要る。

1. 周の鎖を Archon の `workflow:` のノードで回すのをやめ、周ごとに殻が新しい run を `--config` つきで起こす。周の費用の合算・承認・再開を Archon の子の run に任せている今の作り（`docs/design.md` の「親のグラフ・子の run」、`workflows/chain/works-factory-chain.yaml` の頭のコメント）を変える。
2. メイングラフのノードを群ごとにモデルの字を書いた組で並べ、子の入力（`with:`）を `when:` で読んで 1 つを選ぶ。ノードが群の段の数だけ増え、E7（ノードはモデルの字を書かない）を変える。
3. 呼ぶ人の起動の時の `--model @wf-<群>=<spec>` だけで替える（今の形）。run の全部の周に効き、周ごとには替わらない。

## (b) #671 のため: 名指しの会話はどこまで続くか

結論: 下の 1・2a・3 で続き、2b・2c・4 で続かない。pin と head で振る舞いは同じ（`loader.ts`・`include-expander.ts`・`schemas/`・両方の文書は 24 commit で中身が同じ。`dag-executor.ts` は `14de72582` の分け直しだけ）。下の `dag-executor.ts` の行は pin:・head: で書く。

1. ループの周をまたぐ: 続く。
   - ループの体のうち `context.resume` を持つノードごとに、会話の位置（cursor）の表を `loop_group` の 1 回の呼びに 1 つ作り（pin:4689-4690・head:4346）、全部の周に同じ表を渡す（pin:5171・head:4828）。
   - 表に位置が在れば `owner-continuation` としてその会話を続け、無ければ（最初の周）元のノードの会話を分けて始める（pin:10775-10777・head:10186-10188）。
   - ノードが終わるたびに、`context.resume` を持つノードの位置だけを書き換える（pin:11169-11180・head:10580-10591）。`context: fresh` の読み手は書き換えない。
   - provider が会話の id を替えたらノードを落とす（pin:3172-3175・head:2908-2911「did not continue its private owner session」）。黙って新しい会話にはならない。
   - `fresh_context: true` が消すのはループの会話の流れ（`lastSequentialSession`、pin:5173・head:4830）だけで、名指しの会話は消さない。文書も同じことを言う（`guides/loop-nodes.md`:789-833、`guides/authoring-workflows.md`:321）。
   - 試験: `dag-executor.test.ts` pin:29066・head:29065「keeps the ${provider} owner branch across fresh reviews (fresh_context=…)」。
2. resume の後: 止まり方で分かれる。
   - 2a. ループの中の待ち（`wait:`・承認ノード）で止まった run の resume: 続く。止まる時に会話の位置を run の metadata（`bodySessionCursors`・`bodySessionCursorAncestry`。位置の形は `schemas/workflow-run.ts`:134 の `sessionCursorSchema`）に置き、resume が戻して止まった周の次から続ける（pin:4669-4741・head:4326-4392）。位置が読めなければ「cannot restore named owner sessions」で落ち（pin:4698・4724、head:4355・4381）、黙って新しい会話にしない。試験: `dag-executor.test.ts` pin:29111「restores private ownership from serialized interactive pause state in a new execution」・pin:29173・head:29172「snapshots and restores the owner at a terminal ${boundary}, including repeated suspension」。
   - 2b. 落ちた run の resume: 続かない。`loop_group` は 1 周目からやり直し、名指しの会話は元のノードの会話（DB の `remote_agent_workflow_run_node_sessions` から戻した物）から分かれ直す。前の試みの周で積んだ会話は捨てる（`guides/loop-nodes.md`:853-855「Failure resume … the loop_group node restarts from **iteration 1**」・`guides/authoring-workflows.md`:321「Failure resume still restarts the group at iteration 1」）。これを直に縛る試験は見つからなかった（コードの道筋と文書からの読み）。
   - 2c. `--adopt`（新しい run）: 続かない。`--adopt` は新しい id の run を起こし、前の run から継ぐのは作業ツリー・枝・成果物だけ（`packages/cli/src/help.ts`:804「Start a new run adopting a terminal run's worktree/branch + artifacts」、`docs/design.md` の U1）。ノードの会話の行を読み込むのは同じ run を resume する時だけ（`executor.ts` pin:1261-1263・head:1262-1264 の `listWorkflowRunNodeSessions(candidate.id)`。`candidate` は resume する run）。
3. 子の run の中: 続く。子の run は自分の YAML を自分で読み込む別の run で、子の中のループの前のノードと `loop_group` の間では 1・2a と同じに効く。`include:` の中の名指しは `<include の id>__` の頭ごと付け替わる（`include-expander.ts`:536-537）。入れ子の `loop_group` は呼びごとに別の位置を持つ（`dag-executor.test.ts` pin:29516「scopes nested sources and owner cursors to each enclosing invocation」）。子の run の中で続くことを直に縛る試験は見つからなかった。子の run も親と同じ実行の道を通る（`executor.ts` pin:3539・head:3540 の `runChildWorkflow` が pin:1701・head:1702 で `executeWorkflow` に入り直す）ことからの読み。
4. run をまたぐ（周の鎖の前の周の子の run、親の run のノード）: 続かない。名指せるのは同じ YAML のループの前のノードだけで（`loader.ts`:1309-1324。ループの前でなければ「is not an upstream dependency of the loop_group」、ほかの run の名は「references unknown node」）、ループの体は run をまたいで会話を持たない（pin:5155-5158・head:4812-4815 の `persistScope: undefined`・`workflowPersistSessions: false`、`guides/authoring-workflows.md`:1234「Cross-run persistence isn't wired for them in this release」）。

#671 への含み:

- 報告の書き手のループ（`workflows/report/works-factory-report.yaml`:182 の `loop_group`）は 1 つの run の中なので、ループの前に書き手のノードを置けば名指しで続けられる。名指せる元は `command:`・`prompt:`・`loop:` のノードだけで（`loader.ts`:1322-1324）、今のループの前の `facts` は script なので名指せない。
- 名簿 P10 の 3 つの場合のうち、外せるのは「ループの中で別の役のノードを挟む時」だけ。「`include` したサブグラフをまたぐ時」は同じ run の中でもループの前のノードしか名指せず、「別の run（周の鎖）をまたぐ時」は上の 4 で続かない。
- 落ちた run の resume（2b）では、書き手は前の試みの周を覚えていない。ただしループも 1 周目からやり直すので、拒まれた答えの周そのものも回し直しになる。#671 の受け入れ「前の周で拒まれた答えを次の周の書き手が知っている」は、1 回の試みの中の周についてなら満たせる。

## 求め 4: 推しと上げる時の手順

推し: 上げる。ただしこの issue では上げず、別の issue で dev の頭へ上げる。

- 訳: 持ち主の決め `asf-follows-dev`（`docs/owner-decisions.md`）は止めた版に留まる理由を持たないと決めている。24 commit は埋めを塞がず壊しもせず、壊れるのは約束の試験の 2 行だけで、上げの費用は小さい。得る物は ASF の #4517（works-factory 自身を作る run の審査の行き先）と、Archon の file-store の後片付け（#4513）。
- 上げても変わらない物: #659 の口は無いままで、#671 の答えも同じ。だから #659・#671 は版を待たずに進めてよい。

上げる時の手順（`c1ac36f8` の #716 と同じ形）:

1. `factory/pack.json` の `integration_revision_required` を読んだ dev の頭に替える。CI・試験・`bin/_lib/place.py` はここから源を読むので、版の字を替える所はここだけ。
2. 試験の段: まず `tests/changed.py` と層の柵、次に `tests/shared/test_archon_contract.py`。`ARCHON_ROWS` の「節が済んだ状態」と「節の一覧の行の id と状態の鍵」の 2 行の在り処を `packages/cli/src/commands/workflow.ts` から `packages/cli/src/commands/workflow-node-summaries.ts` に替える。最後に CI の全部の試験と、本物の Archon で回す試験（`tests/e2e/`）。
3. 埋めの外し: 今の dev の頭までに外せる埋めは無い。上げる日の dev で `docs/polyfills.md` の「上流の確かめ方」をやり直し、塞がった物が在れば名簿の決まり（「外した」へ移す）で外す。
4. 柵と文書の更新: 名簿の各行の「上流（`<止めた版>` の後の dev の `<読んだ dev>` まで）」の頭 8 字を新しい版に替える（替えないと `tests/layers/test_polyfill_evidence.py` が赤）。`docs/design.md` の「語」の止めた Archon の版の字と、U6 の `listRunEvents` の在り処、`docs/asf-notes.md` の見る版の字を替える。`docs/design.md` の `workflow:` の子の結果の読みの項（727 行）は、在り処を `dag-executor.ts` から `dag/child-run.ts` に替える。同じ文書の `dag-executor.ts` の行番号（125 行の 4363-4364、708 行の 5322、714 行の 7716-7719・7771-7790）は pin でも既に合っていない（例: 708 行の `executeLoopNode` は pin:5704・head:5361）ので、head の在り処で書き直す。
5. ASF の型を読み直す: `docs/asf-notes.md` の決まり（版を進めたら各セクションを読み直す）に従い、#4517 で変わった審査の行き先を確かめる。

## issue の本文と食い違った所

- 本文は比べる元を `d97d00ef` とし、186 commit を調べるとしている。その後に止めた版が `355f1867`（#637）と `64ec0c2e`（#716）へ上がり、本文が挙げた変化は全部止めた版に入った。この文書は今の止めた版 `64ec0c2e` から dev の頭 `a972888a` までの 24 commit を比べた。`d97d00ef..64ec0c2e` の変化は、名簿と `docs/design.md` の上げの時の書き直しに在る。
- #671 の本文は 355f1867 の文書の 783-813 行と書く。64ec0c2e と a972888a では同じ見出し「Named owner sessions」は `guides/loop-nodes.md`:789 から始まる。
