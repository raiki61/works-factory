<!-- coldwrite:skip 埋めの名簿。語は docs/design.md の「語」のセクションで定義 -->
# Archon の埋め（polyfill）の名簿

- 埋め（polyfill）: Archon（止めた Archon（`docs/design.md` の「語」））に無い物を、このリポジトリの側で補う小さな部品。Archon の中は直さない。
- `workflows/.shared/` と `bin/_lib/` のファイルは、境の口（Archon との出入りのモジュール 1 つ）か、入口の部品（`tests/layers/scan.py` の `ALLOWED["E2"]` が 1 行ずつ名指す物）か、この名簿の `- 埋め:` の行の頭の欄が名指す物のどれかに当たる（`workflows/AGENTS.md` の E2。試験 `tests/layers/test_polyfills_listed.py` が照らす）。行の説明の文にだけ名が出る部品は数えない。
- 頭の欄は `- 埋め:` の直後に、部品のパスを `、` 区切りで並べる（予定ならパスの直後に「（予定）」）。欄は「（予定）」と `、` 以外の最初の字で終わる。部品を持たない埋め（値の埋め・YAML の型の埋め）は、頭が文で始まり欄は空。埋めの一部は入口 `bin/` に置く物もある。それも頭の欄に書く。
- 証拠の在り処は、止めた Archon（`factory/pack.json` の `integration_revision_required`）の源のファイルと、そのファイルで探せる引用で書く。行番号は版で動くので書かない（証拠の「12-14 行」の形も、項目のどこかの `ファイル:数字` の形も）。`- 証拠:` の下の字下げした行は 1 行に 1 つのファイルで、頭にファイルのパスを置き、その行の「」の中の字はどれもそのファイルにちょうど 1 か所だけ字のまま在る（2 か所に当たる時は 1 か所に決まるまで字を伸ばす）。行の説明に「」を使わない。候補の項目も、証拠を書くなら同じ形で書く。試験 `tests/layers/test_polyfill_evidence.py` が照らす。「外した」の項目は、源の引用と版の照らしから外す（外した時の版の字のまま残す）。
- 各行の `` - 上流（`<止めた版の頭 8 字>` の後の dev の `<読んだ dev の commit の頭 8 字以上>` まで）: `` に、止めた版より後の upstream の dev で穴が塞がったかの確かめの結果を書く。「塞がった」と書く時は、塞いだ upstream の commit（`` ` `` で囲んだ頭 8 字以上）か PR（`#<番号>`）を添える。版を上げたら書き直す（頭の 8 字が止めた版と違うと試験が赤）。読んだ日が古くなっても赤にはしない。
- 上流の確かめ方（upstream の Archon `https://github.com/coleam00/Archon` の clone で）:
  1. `git fetch origin dev` の後、`git rev-parse --short=9 origin/dev` が読んだ dev の commit。上流の行にそれを書く。
  2. `git log --oneline <止めた版>..origin/dev -- <証拠のファイル>` で、証拠のファイルを変えた commit を出す。1 つも無ければ、その証拠の振る舞いは変わっていない。
  3. 変えた commit が在れば、`git show <読んだ dev の commit>:<証拠のファイル>` で引用の字を探し、`git show <commit>` で変わった所を読む。引用の字が残り、変わった所が穴の振る舞い（「穴:」の文）に触れていなければ「塞がっていない」と書く。
  4. 証拠のファイルの外で塞がることもあるので、`git log --oneline <止めた版>..origin/dev` の題を全部読み、穴に触れそうな commit は `git show` で読む。塞いだ commit を見つけたら「塞がった」と書き、その commit か PR を添える。
- 埋めや回り道を出す前に、upstream の Archon と ASF の、止めた版より後の commit で、その穴が塞がっていないかを確かめる（塞がっていれば、埋めを作らずに版を上げる方で足りる）。
- Archon の新しい版で穴が塞がったら、外す条件を確かめて埋めを消し、行を「外した」のセクションへ移して `- 埋め:` の頭を `- 外した埋め:` に書き換える（`- 埋め:` の行に消したファイルの名が残ると、名簿の古びとして赤になる）。

## 書き方

```
### P<番号> <穴の短い名>
- 穴: Archon でできないこと（1〜2 文）
- 証拠: （引用で足りない説明が要る時だけ、ここに文）
  - `<止めた Archon の源のパス>` の「<そのファイルに字のまま在る引用>」（説明）
- 上流（`<止めた版の頭 8 字>` の後の dev の `<読んだ dev の commit>` まで）: 塞がったか（塞がったなら塞いだ commit か PR）
- 埋め: `<パス>`、`<パス>`（予定）。何を置くか
- 使うサブグラフ: 
- 外す条件: Archon のどの振る舞いが入ったら消せるか
```

## 今の行

### 候補（まだ埋めでない）: fan_out の子ごとの作業ツリー

- 修正の組の並べは Archon の `fan_out:` で書く（持ち主の決め `no-queue`。埋めは要らない）。
- 組ごとに別の作業ツリーが要る。`workflow:` と `fan_out:`（`isolation: worktree`）の子の run は組ごとに起き、子ごとに作業ツリーが切られる。子の作業ツリーは親の姿を写せ、子は親の run の置き場に結果を書ける（止めた Archon で 2026-10-12 に実測。PR #94 の「組を並べて回せるか（計画の U8）の実測」。`docs/design.md` の U8）。
- remote（`origin`）の無い対象のリポジトリでは、子の作業ツリーが切れない（`no git remote is configured`。親の run そのものも remote が無いと作業ツリーを切れない）。fix は remote が在る時だけ組を並べ、無い時は親の作業ツリーで 1 つずつ回す（`groups-seq`）。埋めは要らない。
- 2026-10-06 の判断「fan_out は子ごとに作業ツリー（cwd）を決められない」は、ノードの `fan_out:` だけを見ていたかもしれない。U8 で読み直す。

### 候補（まだ埋めでない）: run の中で後のノードの模型と effort を付け替える口

- 穴: Archon 64ec0c2e に、run の中で後のノードの模型と effort を付け替える口が無い。`--model` は run を起こす時だけで続きの run には渡せず、`workflow:` のノードにも付け替えの欄が無い。run の頭の深さの役の群の選び（`groups`）は、今は控えに残すだけで効かない（`lib/headdepth.py`・`lib/launchgroups.py`）。上流に issue は出さない。
- 証拠:
  - `packages/workflows/src/model-validation.ts` の「Parse repeated CLI `name=spec` mappings into the shared transport shape.」（`--model` は run を起こす命令の字を受けるだけ）
  - `packages/workflows/src/executor.ts` の「Cannot supply model overrides when resuming an existing workflow run.」（続きの run は付け替えを拒む）
  - `packages/cli/src/dispatch-guards.ts` の「Error: --model cannot be used when continuing an existing workflow run.」（続きの run を起こす命令も `--model` を拒む）
  - `packages/workflows/src/schemas/dag-node.ts` の「export const workflowNodeSchema = dagNodeBaseSchema.extend({」（`workflow:` のノードの欄に、模型と effort の付け替えが無い）

### P1 持ち主が居なくなった running の run を再開できない

- 穴: Archon を動かしていた process が落ちると、run は `running` のまま残り、`resume` できない。
- 証拠:
  - `packages/core/src/operations/workflow-operations.ts` の「Only failed or paused runs can be resumed.」（`resumeWorkflow` が、再開できる status の一覧に無い run を拒む）
  - `packages/workflows/src/schemas/workflow-run.ts` の「export const RESUMABLE_WORKFLOW_STATUSES」（再開できるのは `failed`・`paused` だけ）
  - `packages/core/src/operations/workflow-operations.ts` の「If its process is gone, abandon the run to release it.」（cancel は、走らせている process が答えない時〔`no_owner_answered`〕に abandon を案内する）
- 上流（`64ec0c2e` の後の dev の `64ec0c2e2` まで）: 塞がっていない（止めた版が dev の頭。`355f1867..64ec0c2e2` の 87 commit で、証拠の字と、その辺りの振る舞いは変わっていない）。
- 範囲: 長い待ち（CI・人の答え）は Archon の `wait:` のノードと承認ノードで書く。Archon 0.10.0 から待ちは持ちこたえる（CHANGELOG [0.10.0]「The database owns suspension and resume claims, so process restarts … cannot reset a wait」。server が期限の来た run を再開する）。だからこの穴に当たるのは、ノードを走らせている途中で process が落ちた run だけ。
- 埋め: `bin/apply`、`bin/_lib/apply.py`（`bin/apply` の中身は `bin/_lib/apply.py`。#101。続けられない run の差分を取り出して対象に当てる。今の works の apply と同じ能力）。Archon の命令だけでは足りない: 下の実測のとおり `abandon` は書きかけごと作業ツリーを消し、`--adopt` は最初のノードからやり直すので、持ち主の決め `carry`（止まった run の差分も捨てない。`docs/owner-decisions.md`）を満たさない。手放しと続きの起こしは止めた Archon の命令をそのまま打つ（入口に別名を作らない。持ち主の決め `one-launcher`）。
  - 足りない残り: ノードの途中で持ち主が落ちた run の、commit していない書きかけ。`bin/apply` は終わっていない run（`terminal_record` が null。手放す前の `running`）を拒み、手放した後は作業ツリーが消えている（commit 済みの物は残った枝に在る）。だから今は、手放す前に人が `workflow get <run> --json` の `working_path` で作業ツリーの変更（新しいファイルを含む）を取り出しておく。
  - 持ち主に聞く項にしない: 持ち主の決め `carry` と既にある `bin/apply` で答えが 1 つに決まる（運び役の決め。PR #182 の 1 回目の修理）。
- 実測（段 1b、2026-10-12。止めた Archon に AI の無い使い捨てのグラフ。ノード `write` が書きかけのファイルを書いて眠り、後ろに `trigger_rule: all_done` のノード `tail`。run `4300fc39121ab1838cc25c38fcf83e98`）: `write` が走っている間に `--detach` の子のプロセスを pid で止めた（`kill -9`）。run の記録は使い捨ての Archon の家と一緒に消え、id から読み戻せない（下の「再現」で回し直す）。
  - `workflow get` は `running` のまま。`workflow wait --json` は終了の値 0 で `"result": "owner_lost"`・`"observedStatus": "running"`。
  - `workflow resume <run> --json` は拒む（「Cannot resume run with status 'running'. Only failed or paused runs can be resumed.」）。`workflow run --adopt <run>` も手放す前は拒む（「it is still running. … abandon it first」）。
  - `workflow abandon <run> --json` は `owner.outcome: no_owner_answered` と記録した pid を出し、run を `cancelled` にし、run が作った作業ツリーを書きかけのファイルごと消す（`releasedWorktrees`）。枝は残る。
  - その後の `workflow run <工程> --adopt <run> --detach --json` は新しい id の run（`a21aee649292b6b07be27e96aa8e6496`。`adopted_from_run_id` が前の run）を起こし、残った枝で同じパスに作業ツリーを作り直し、最初のノードからやり直す（前の run の終わったノードを飛ばさない）。後ろの `all_done` のノード `tail` は走った。
  - 持ち主を `kill -9` で止めても、走っていたノードの子のプロセス（`bash -c …` と `sleep`）は残って走り続けた（親が 1 になる）。`abandon` は持ち主が答えない時はプロセスを止めない（「Nothing decides the run is dead from its age or pid」）。手放す前に、残った子を pid で止める。
  - `d97d00ef` ではメイングラフが `interactive: true` だったので、メイングラフの `--adopt` は `--detach` を付けずに打った。`355f1867` から `interactive:` が効かないので、この縛りは無い（実測はまだ。`docs/design.md` の「Archon の分かっていること」）。
- 実測（段 1 の手順 6、2026-10-13。main `b5d9d8da` のメイングラフを本物の役で。run `ee0f15b7`）: 役のノード（`judge__world-judge-loop.world-judge`）が走る間に `--detach` の子のプロセスを pid で止めた。`workflow get` は `running` のまま（持ち主が居ないことは get からは分からない）・`workflow wait` は `owner_lost`・`workflow resume` は拒む・`workflow abandon` は `cancelled` にし、`releasedWorktrees` の作業ツリーを書きかけごと消す（枝は残る）。`workflow run --adopt` は新しい run `097c08dc`（`adopted_from_run_id` 付き、メイングラフの頭からやり直し）を起こし、閉じた時に報告のノードが全部走った（棚卸しの L-W60 の resume の半分。report.md 6082 バイト）。この埋め（`bin/apply` と Archon の命令）で足りる（埋めを足さない。上の「足りない残り」はそのまま）。
  - 気づき（不具合と決めていない）: 殻 `bin/works-factory` は出力の JSON が `"ok": false`・`owner_lost` でも終了の値が 0。親を失った役の claude は作業ツリーの中で約 20 秒走り続けてから自分で終わった。
- 再現（AI の役も認証も要らない。グラフは `tests/e2e/owner-lost-probe/`。プロセスを止めるので試験にせず手で回す。形だけは `tests/e2e/test_resume_probe.py` が validate で照らす）:
  1. 使い捨ての git の木にグラフを `.archon/workflows/works-factory/owner-lost-probe/` の形で置いて commit し、空の bare のリポジトリを `origin` に足して push する（`remote` が無いと Archon は作業ツリーを切れずに落ちる）。`ARCHON_HOME` も使い捨てにする。
  2. `workflow run works-factory-owner-lost-probe --detach --json` を打ち、`workflow get <run> --json` の `working_path` に `half-written.txt` が出るのを待つ。
  3. `ps` を使い捨ての木のパスで絞って `workflow run … --internal-detached-run-id …` の持ち主の pid を見つけ、`kill -9 <pid>`。
  4. `workflow wait <run> --json --timeout 10`（`owner_lost`）・`workflow resume <run> --json`（拒む）・`workflow run works-factory-owner-lost-probe --adopt <run> --detach --json`（拒む）を見る。
  5. 残ったノードの子（`bash -c echo half > half-written.txt; sleep 600` と、それを親に持つ `sleep`）を pid で止め、`workflow abandon <run> --json` を打ち、作業ツリーが消えたことを見る。
  6. `workflow run works-factory-owner-lost-probe --adopt <run> --detach --json` で新しい run を起こし、`write` が最初から走ることを見る。その `sleep` の pid と新しい持ち主の pid を止め、使い捨ての木と家を消す。
- 使うサブグラフ: メイングラフ（入口）
- 外す条件: 持ち主の居ない `running` を Archon が自分で `failed` にするか、`resume` を受け付ける版が出たら

### P2 include の入力に if_skipped を通せない

- 穴: メイングラフがサブグラフを `include:` で呼ぶ時、`with:` に `{from, if_skipped}` の束ねを書いても、飛ばされた前のノードの代わりの値がサブグラフの中まで運ばれない。
- 証拠: 書いた束ねは黙って JSON の値として渡り、書けたように見えて効かない。
  - `packages/workflows/src/schemas/dag-node.ts` の「Include/workflow `with:` maps have no directive, so」「objects there stay ordinary JSON literals.」（束ね `{from, if_skipped}` は `command:`・`script:` の `with:` だけの形）
  - `packages/workflows/src/include-expander.ts` の「if (slot.surface === 'binding_from' || slot.name === 'binding.if_skipped') return slot.value;」（include の展開は `binding.if_skipped` の欄を置き換えずにそのまま残す）
- 上流（`64ec0c2e` の後の dev の `64ec0c2e2` まで）: 塞がっていない（止めた版が dev の頭。`355f1867..64ec0c2e2` の 87 commit で、証拠の字と、その辺りの振る舞いは変わっていない）。
- 埋め: `workflows/.shared/skip_value.py`。メイングラフの中継のノードが使う。飛ばされうる値を、メイングラフの `script:` のノードの `with:` で欄ごとに `{from: "$<ノード>.output.<欄>", if_skipped: null}` で受け、明示の値で返し直す。サブグラフにはそのノードの出力を渡す。P2 のために在る中継のノードは `workflows/line/works-factory-line.yaml` の `answer-*`（承認ノードの答えを fix・merge に渡す）と `collect`（全部の出力を report に渡す）だけ。Archon が `INPUTS_<名>` に渡した字を値に戻す部品は `workflows/.shared/skip_value.py`。
- 使うサブグラフ: メイングラフ
- 外す条件: include の `with:` に書いた `if_skipped` が子の中まで効く版が出たら

### P3 --workflow-source が任意のフォルダを読まない

- 穴: `--workflow-source <dir>` は `<dir>/.archon/workflows/` しか読まない。自分のグラフのフォルダ（リポジトリの `workflows/`）を直に渡せない。
- 証拠:
  - `packages/cli/src/cli.ts` の「discoveryCwd: workflowSource,」「Point it at the checkout holding .archon/workflows/.」（`--workflow-source` は探す木の根を替えるだけ）
  - `packages/paths/src/archon-paths.ts` の「return ['.archon/workflows'];」（`getWorkflowFolderSearchPaths`。根の下で探すのは `.archon/workflows` だけ）
- 上流（`64ec0c2e` の後の dev の `64ec0c2e2` まで）: 塞がっていない（止めた版が dev の頭。`355f1867..64ec0c2e2` の 87 commit で、証拠の字と、その辺りの振る舞いは変わっていない）。
- 埋め: `bin/_lib/place.py` の `workflow_source`。キャッシュの中に置き場を作り、その `.archon/workflows/works-factory`（pack の形。名は `pack.json` の `ours.pack`）からリポジトリの `workflows/` へ symlink を張る。
- 使うサブグラフ: メイングラフ（入口）
- 外す条件: `--workflow-source` に任意のフォルダを渡して、その中のグラフを読める版が出たら

### P4 読んだ・書いた証拠のフックをノードに付けられない

- 穴: ノードの hooks: は固定の返事だけで、役が読んだ・書いたファイルの記録を残せない。
- 証拠:
  - `packages/docs-web/src/content/docs/guides/hooks.md` の「YAML `hooks:` are deliberately static.」と、見出し「## Choosing where hook logic lives」の下の行「Logic that inspects the hook input at runtime」（中身を見るフックは Claude の設定に置く）
- 上流（`64ec0c2e` の後の dev の `64ec0c2e2` まで）: 塞がっていない（止めた版が dev の頭。`355f1867..64ec0c2e2` の 87 commit で、証拠の字と、その辺りの振る舞いは変わっていない）。
- 埋め: `bin/_lib/record-read.py`、`bin/_lib/record-write.py`、`bin/_lib/toolset.py`。record-read.py は Read と、Agent・WebFetch・WebSearch を path の無い行で、record-write.py は Edit・Write・NotebookEdit の書いた記録を残す。toolset.py の install が隔離した設定の settings.json の hooks.PostToolUse に置く。
- 使うサブグラフ: plan・plan-review（区分 J・F の issue の後は judge・fix）
- 外す条件: ノードの hooks: が command の種類を受け、入力を見て書ける版が出たら

### P5 役の sandbox に起動ごとの値を渡せない

- 穴: ノードの `sandbox` は YAML の固定の値のまま SDK に渡るので、run ごとに違うパス（cwd・共通の `.git`・対象の本体の作業ツリー・`worktree.path` で置き場を替えた worktree）を読むだけの役の `denyWrite` に名指せない。固定の値 `~/../archon-home`（`tests/layers/scan.py` の `NO_TREE_WRITE`）は Archon の家の下しか塞がない。
- 証拠: 実測は issue #306（固定の値でも symlink の綴りでも、共有の `.git` と対象の本体の作業ツリーに書けた）。
  - `packages/workflows/src/dag-executor.ts` の「sandbox: node.sandbox ?? workflowLevelOptions.sandbox,」（同じ関数で `systemPrompt` などは `resolveAiText` で置き換えるが、`sandbox` は置き換えない）
  - `packages/providers/src/claude/provider.ts` の「options.sandbox = nodeConfig.sandbox as Options['sandbox'];」
  - `packages/providers/src/claude/binary-resolver.ts` の「const envPath = process.env.CLAUDE_BIN_PATH;」「`CLAUDE_BIN_PATH` environment variable (honored in both modes」（起こす claude の実行ファイルを環境変数 `CLAUDE_BIN_PATH` から読む。dev mode でも読む）
- 上流（`64ec0c2e` の後の dev の `64ec0c2e2` まで）: 塞がっていない（止めた版が dev の頭。`355f1867..64ec0c2e2` の 87 commit で、証拠の字と、その辺りの振る舞いは変わっていない）。
- 埋め: `workflows/.shared/fence.py`、`bin/_lib/launcher.py`。起動の殻（`bin/_lib/launcher.py` の `write_fence`）が、Archon を走らせる命令の時だけ包みの殻を書いて子の `CLAUDE_BIN_PATH` をそこへ向ける。包みは SDK が渡す `--settings` の `sandbox.filesystem.denyWrite` に固定の値（印）が在る起動だけ、起こす直前に cwd から組んだ一覧（cwd・`git rev-parse --git-common-dir`・`git worktree list` の全部の根・Archon の家・Claude の設定・殻が書いた口・後の役の起動と次の起動が sandbox の外で走らせる物〔それを起こす Python・本物の claude・取り置いた Archon の源・工場の checkout の根の全体（包み・版の止め、`bin/works-factory` が import の先頭に置く根の `.py` を含む）〕）を足して本物の claude を起こす。印の無い起動は argv を変えない。`--settings` が JSON の object でない起動は止める。形は包み `claude-adapter`（旗 `no-tree-write`）。試験は `tests/shared/test_fence.py`（本物の claude で書き込みが止まることも見る）。
  - 写した元（台帳）: 一覧の組み方 `_git`・`protected_paths` は、今の works（`raiki61/claude-plugins` の commit `2aa7c66cf7abe1fe09699ac2942d107123214168`）の `graphloops/engine/role_run.py` 141-172 行をそのまま写した。それを縛る元の試験（`graphloops/tests/simulate.py` の `test_tooled_launch_fence` の守る場所の 2 つの check と、`graphloops/tests/py/test_role_run_stop.py` の `test_protected_paths_is_undecided_when_git_answers_partly`）は `tests/shared/test_fence.py` の `ProtectedPathsCopiedTest` に写した。同じ元の `tooled_permission`（sandbox の形と道具の許しを組む）は写さない。ここでは役の sandbox の形と道具を YAML が持ち、層の柵 `tests/layers/scan.py` が縛る。
  - 起こす場所の `.env`・`.env.local`・`.env.development`・`.env.production`・`.archon/.env` か、Archon の家の `.env`（`archon setup` の既定の書き先）が `CLAUDE_BIN_PATH` を名指すと、Archon はその値で包みを置き換えるか消す（`packages/paths/src/strip-cwd-env.ts`・`packages/paths/src/env-loader.ts` の `loadArchonEnv`）。起動の殻はその時 Archon を起こさずに止める。同じファイルが `WORKS_FACTORY_FENCE_RECORDS`（下の宣言）を名指しても止める。
  - 起動の記録（今の works の包みの起動の記録と `ci_role.take`。`docs/plans/2026-10-13-capabilities/tail.md` の T49）: 包みは印の在る起動を、起こす前に `--records` の記録（家の `claude-fence/launches.jsonl`。`--own` の下で役は書き換えられない）へ時刻と cwd の 1 行で足し、書けなければ起こさない。起動の殻は同じパスを子の env `WORKS_FACTORY_FENCE_RECORDS` に置き、run が包みを通ると script のノードに宣言する。宣言が読めない（絶対パスでない）run は test-gate の `ci-prep` が落ち、CI の役を起こさない。宣言した run では test-gate の `ci-accept` が、`ci-prep` の後にその作業ツリーで柵の掛かった起動が記録に無ければ返答を受けずに諦める。宣言の無い run（殻を通らない起動。`tests/archon.py` が起こす Archon）は、test-gate の証拠に知らせ `NO_ADAPTER_NOTE` を出す。
  - 印を書かない役: Edit・Write を持つ役（直す役・書く役）は作業ツリーを変えるのが仕事で、cwd を禁じると仕事ができない。今の works の柵も道具に書き込みの無い役だけに掛けた（`graphloops/engine/role_run.py` の `tooled_permission` と `DELEGATE_TOOLS`）。
  - 役の PATH の頭（持ち主の決め `roles-read-only-gh`）: Archon はノードごとの環境を持たず、script のノードにも役の claude にも同じ環境（Archon の過程の env に設定の `env:` を重ねた物）を渡す（`packages/provider-contract/src/agent-provider.ts` の env の組み・`packages/workflows/src/dag-executor.ts` の script の env）。だから起動の殻は Archon の子の PATH の頭に利用者のログインを継ぐ gh の口（`bin/_lib/hostgh.py`）だけを置き（script のノードと、出口の語 `pr` の時に push と PR の作成をする `archon-pr` の publish が打つ）、包みは `--path-head` で名指された読むだけの口の置き場（`bin/_lib/no-post-bin/`）を、起こす claude の PATH の頭に足す（印の有無に依らない）。script のノードが起こす対象のコマンド（AI が書いた試験のコードも走る）には、起動の殻が同じ置き場を `WORKS_FACTORY_READ_GH`（`lib/userenv.py` の `READ_GH_ENV`）で渡し、`lib/tree_run.py` の `outside_env` が PATH の頭に足す。試験は `tests/shared/test_fence.py` の `test_path_heads_lead_the_path_of_claude_only` と `tests/bin/test_launcher.py` の `test_role_path_starts_with_read_only_gh`・`test_target_commands_hit_the_read_only_gh`。
  - 足りない残り: judge の読むだけの役の受け付けは起動の記録を見ない（今の works にも無い）。包みを通らない起動には固定の値だけが残る。
- 使うサブグラフ: judge・test-gate
- 外す条件: ノードの `sandbox` が run ごとの値（cwd・共通の `.git`・worktree の根）を受ける版が出たら

### P6 親が子の run のポインタを読めない

- 穴: `workflow:` のノードが起こした子の run の出力のポインタ（`{type: archon_artifact, run_id, path}`）を、親の run の script が読む口が無い。境の口 `workflows/.shared/boundary.py` の `resolve` は自分の run のポインタしか読まない。
- 証拠:
  - `packages/workflows/src/artifact-pointer.ts` の「A pointer naming any other run is rejected — a result may only point」（読む側は「in-workflow resolver, the terminal run record」で、読む時に symlink を辿った照らしは「not yet implemented (#3160)」）
  - `packages/paths/src/archon-paths.ts` の「return join(getStoragePathsForRoot(root).artifactsRoot, 'runs', workflowRunId);」（`getRunArtifactsDirForRoot`。子と親は同じ `runs/` の下に兄弟で並ぶ）
- 上流（`64ec0c2e` の後の dev の `64ec0c2e2` まで）: 塞がっていない（止めた版が dev の頭。`355f1867..64ec0c2e2` の 87 commit で、証拠の字と、その辺りの振る舞いは変わっていない）。
- 埋め: `workflows/.shared/child_pointer.py`。自分の置き場（`ARTIFACTS_DIR`）の隣の `<run_id>` を子の置き場とし、札の形・run の id の形（空・`..`・`/` を拒む）・相対のパスを照らして、symlink を辿った先が子の置き場の中に在ることを確かめてから返す。試験は `tests/shared/test_child_pointer.py`。
- 使うサブグラフ: 周の鎖（`workflows/chain/works-factory-chain.yaml` の `round-k-facts`）
- 外す条件: Archon の run の中から、ほかの run のポインタを読む口が入ったら

### P7 fan_out の子の作業ツリーが子の終わりで消えない

- 穴: `fan_out:` の子の run が作った作業ツリーと枝は、子が終わっても残る。
- 証拠:
  - `packages/docs-web/src/content/docs/guides/authoring-workflows.md` の「It is **not** removed when the child finishes」（`archon complete <branch>` で消す）
- 上流（`64ec0c2e` の後の dev の `64ec0c2e2` まで）: 一部が動いた。upstream の #4328（`8c741d891`。止めた版に入っている）で、終わった（`completed`）run は自分で作った作業ツリーを、変更が無く commit が全部 remote に在り枝を公開していない時だけ外す（枝は残す）。fix の子は push しないので、子の作業ツリーはたぶん残る（実測はまだ）。証拠の文は止めた版でも同じ。
- 埋め: `workflows/.shared/childsweep.py`。メイングラフの最後のノードから呼ばれ、この run の子だけを選んで止めた Archon の `complete --force` で消す。試験は `tests/shared/test_childsweep.py`。
- 使うサブグラフ: メイングラフ（`workflows/line/works-factory-line.yaml` の `sweep-children`）
- 外す条件: 子の run が終わった時に、その作業ツリーと枝を Archon が自分で消す版が出たら

### P10 周をまたいで同じ役の会話を続けられない

- 穴: 周をまたいで、同じ役の AI の会話を続けられない。当たるのは 3 つの場合: `include` したサブグラフをまたぐ時、別の run（周の鎖）をまたぐ時、ループの前に同じ役の AI のノードが無いループの中で、別の役のノードを挟む時。前の周の自分が読んだ所も考えも次の周の自分に届かないので、周ごとに新しい会話で起きる役には、書き置き（引き継ぎのメモ）で渡す。
- 証拠: 後ろの 2 つの引用の振る舞いは、`tests/shared/test_archon_contract.py` の `ARCHON_ROWS` の行 `名指しの続き context: resume` が `packages/workflows/src/loader.ts` の字でも縛る。
  - `packages/docs-web/src/content/docs/guides/authoring-workflows.md` の「`archon workflow run` starts a run without a conversation, so its `persist_session` nodes start fresh on every invocation」「Cross-run persistence isn't wired for them in this release」「Inside a `loop_group` body, the source must complete before entry into the group」（CLI の別の run は毎回新しい会話で、`loop_group` に run をまたぐ持続は無く、ループの中で続けられるのはループの前のノードだけ）
  - `packages/docs-web/src/content/docs/guides/loop-nodes.md` の「A command or prompt in the body can continue a statically named pre-loop session」（ループの中で続けられるのは、ループの前の `command:`・`prompt:` のノードを名指した時だけ）
- 上流（`64ec0c2e` の後の dev の `64ec0c2e2` まで）: 塞がっていない。`355f1867..64ec0c2e2` の 87 commit に、周をまたいで同じ役の会話を続けられるようにする物は無い。
- 埋め: `lib/handoff.py`。引き継ぎのメモの型・頼み・前の周のノードに貼るセクション・控えを置く。
- 使うサブグラフ: plan・report
- 外す条件: 場合に分ける。
  - 計画（plan）: `include` をまたぐか、CLI の別の run で同じノードの会話を続けられる版が出たら。外す前に、`docs/owner-decisions.md` の「計画の往復の周をまたぐ書き直し（#571。2026-10-15）」の行（前の周の会話を続けず新しい会話で始めると持ち主が選んだ）と、同じ文書の「再審・案の直し・範囲の相談の答えは新しい会話で回す」の行の訳（`d97d00ef` の `authoring-workflows.md` の「Addressable resume is not supported inside `loop_group` bodies」に頼っていて、`355f1867` の同じ所の「Inside a `loop_group` body, the source must complete before entry into the group」とはもう合わない）を持ち主に戻す。`docs/owner-decisions.md` はこの名簿からは書き換えない。
  - 報告（report）の `write-loop`: `355f1867` から、ループの前に書き手の AI のノードを置けば（今の `write-loop` の前は `facts` の script だけ）書き手の会話をループの中で続けられるので、既に外せる候補。作り直し（`write-loop` を名指しの持ち主の会話に替えて報告の引き継ぎのメモを外すか）は #671 で確かめる。
- 外す手順: 外す条件を満たしたら次を全部消し、役の会話を続ける形に替える。`lib/handoff.py` を import する物の全部（`grep -rn "import handoff" lib workflows tests`）も、取りこぼしの入口にする。
  - `lib/handoff.py` の全体。
  - `lib/planfile.py::write_brief`・`_save`・`take_plan`・`take_replan` の handoff の呼びと、`RESUBMIT_RULES`・`REPLAN_RESUBMIT_RULES` の `handoff.FIELD` の行（`accepted_rounds` は `latest` の絞りとして残す）。
  - `lib/report_roles.py::TEXT_SCHEMA` の handoff の欄。
  - `lib/runreport.py::NOTE_ROUND`・`handoff_part`・`_prior_rounds` と、`_carry_rejected` の前の周のメモの読み・置き（前の答えの控えに本文を置く所は残す）。
  - `workflows/report/scripts/reject.py` の出力の handoff。
  - YAML の handoff の欄: plan の `plan-writer`・`plan-writer-fix` の `output_format`（`workflows/plan/works-factory-plan.yaml`）、report の `write` と `write-reject` の `output_format`（`workflows/report/works-factory-report.yaml`）。
  - `workflows/report/commands/report.md` の `$write-reject.output.handoff` と、報告の 2 本の筋書きの stub（`workflows/report/fixtures/fixed.stubs.yaml`・`workflows/report/fixtures/stopped-by-request.stubs.yaml`）の handoff。
  - 指示書の約束の台帳 `tests/workflows/prompt_contracts.json` の `workflows/report/commands/report.md` の行と、写しの手直しの台帳 `tests/workflows/copied_rewrites.json` の `#589` の 2 行。
  - `docs/concepts.json`・`docs/concepts.md` の handoff の行と、`docs/concepts.md` の `marks` の行の持ち主の記述。
  - `lib/marks.py::KINDS` の種 `handoff`。
  - `lib/tests/test_handoff.py` の全体と、ほかの試験の handoff の分（残りの試験は import で赤になるので、黙っては残らない）。

### P11 ノードの plugins: で入っていないかもしれないプラグインを名指せない

- 穴: ノードの `plugins:` は、名指したプラグインが入っていないと最初の turn の前にノードを落とす。入っていれば載せる任意の形（`mcp:` の `optional: true` の類）は無く、値は literal。coldwrite（書く散文の初見検査のフック）は利用者の env の marketplace から取る任意の借り物で、入れていない利用者には入れる物が無い。
- 証拠:
  - `packages/providers/src/claude/plugins.ts` の「Fails when a named id is not installed, because Claude Code would skip it」（`buildClaudePluginSettings` は入っていない名指しを `misconfigured` で投げる）
  - `packages/docs-web/src/content/docs/guides/authoring-workflows.md` の「A named plugin brings its agents, hooks, LSP servers and commands」「The node fails before its first model turn when a named plugin is not installed」「An `mcp:` declared `optional: true` runs the node without its servers instead」「Your own settings, hooks, permissions and `CLAUDE.md` still load」（hooks だけは選べず、任意の形は `mcp:` にだけ在り、利用者の設定のフックは名指しなしで読む）
  - `packages/workflows/src/template-walker.test.ts` の「'plugins.*': { kind: 'literal'」（`plugins:` の値は literal）
- 上流（`64ec0c2e` の後の dev の `64ec0c2e2` まで）: 塞がっていない（止めた版が dev の頭。`355f1867..64ec0c2e2` で `plugins.ts` は変わらず、`template-walker.test.ts` の変更は試験の印の 1 行だけで、`authoring-workflows.md` の変更は plugins の所に触れていない）。
- 埋め: `bin/_lib/toolset.py`。hooked の道で、coldwrite の `hooks/hooks.json` の表を隔離した設定の `settings.json` の hooks に足す。`settingSources: [user]` のノードは利用者の設定のフックを読む（証拠の `authoring-workflows.md`）ので、全部の役で効く。coldwrite の取り元の env は `lib/borrow/borrow.json` の coldwrite の項が持ち、利用者の設定に無ければ借りずに見送る（`toolset.user_borrow`。持ち主の決め `others-may-use`・`AGENTS.md` の E14）。env の字はここに写さない。
- 使うサブグラフ: 書く役を持つ全部
- 外す条件: 2 つが揃った版が出たら。1 つは、`plugins:` に入っていなければ飛ばす形が入ること。もう 1 つは、名指したプラグインのうち hooks だけを載せられること（か coldwrite が hooks しか持たないこと）。`plugins:` は agents・hooks・LSP・commands をまとめて載せる。外す時は、hooked の物が隔離した設定にプラグインとして入らない（`toolset.py` の install が CLI で入れる物から外している）ので、coldwrite を works-local へ入れる道（`pr-review-toolkit` と同じ）に替える要る。

### P12 道具の拒みを run ごとに変えられない

- 穴: ノードの `denied_tools` は YAML の literal で、公開ベンチの run だけで拒むことを書けない。run 1 本ぶんの `--config` の層にも、`assistants.claude` の strict な形にも、道具を拒む鍵が無い。
- 証拠:
  - `packages/workflows/src/schemas/dag-node.ts` の「denied_tools: z.array(z.string()).optional()」（ノードの欄）
  - `packages/workflows/src/template-walker.test.ts` の「'denied_tools.*': { kind: 'literal'」（値は literal）
  - `packages/workflows/src/schemas/run-config.ts` の「Sparse configuration values whose consumers still run after dispatch」（run の設定の層 `workflowRunConfigLayerSchema`。鍵は `assistant`・`assistants`・`aliases`・`tiers`・`workflows`・`docsPath`・`envVars` だけの strict な形）
  - `packages/providers/src/claude/config.ts` の「install: z.strictObject(fields)」「run: z.strictObject(fields)」（`assistants.claude` は `model`・`settingSources`・`claudeBinaryPath` だけの strict な形）
- 上流（`64ec0c2e` の後の dev の `64ec0c2e2` まで）: 塞がっていない（止めた版が dev の頭。`355f1867..64ec0c2e2` の `run-config.ts` の変更〔#4338〕は使用量の上限の注意の文だけで、道具を拒む鍵は足していない）。
- 埋め: `bin/_lib/toolset.py`。埋めは run ごとの部分だけ。`toolset.DENY_WEB_ENV`（`tests/calibration/run.py` が立てる）が 1 の時、install が permissions に拒みを足す（`toolset.permissions`）。env の字はここに写さない。決めは持ち主の決め `public-bench-at-major`。
- 使うサブグラフ: 全部（公開ベンチの run だけで効く）
- 外す条件: `denied_tools` か run の設定の層で、道具の拒みを run ごとに書ける版が出たら。外した後も `toolset.DENY_WEB` の一覧は残る: ベンチが素の Claude Code にも使う（`tests/calibration/run.py` の `--disallowedTools`・`settings.json`・漏れの数え）ため。

### P13 run を cancel しても AI のノードのプロセスが残る

- 穴: `workflow cancel` が止めるのは、切り離した持ち主（`--detach`）のプロセスグループだけ。AI のノードの provider（Claude）は持ち主がノードごとに detached で起こす別のプロセスで自分のセッションに居るので、cancel の後も親が 1 になって残り、その下の claude と claude が起こしたプロセスも残る。子の run のノードも同じ持ち主の中で走るので同じ。前で起こした run（`--detach` の無い `workflow run`）は cancel が拒み、何も止めない。拒みの文が勧める前の命令の割り込みも、provider に届かない。
- 証拠:
  - `packages/core/src/services/run-owner-stop.ts` の「process.kill(-pid, 'SIGTERM');」（cancel は持ち主の番号のグループへだけ送る）
  - `packages/core/src/providers/process-provider.ts` の「detached: process.platform !== 'win32',」（provider のプロセスを持ち主のグループの外に起こす）
  - `packages/workflows/src/exec-environment.ts` の「WORKFLOW_ID: execution.runId,」（AI のノードのプロセスは run の id を env に持つ。番号のつながりの外の印はこれだけ）
  - `packages/core/src/operations/workflow-operations.ts` の「because it is not a detached run (a foreground CLI run, or an Archon server)」（前の run の cancel を拒む）
- 上流（`64ec0c2e` の後の dev の `64ec0c2e2` まで）: 塞がっていない（止めた版が dev の頭。`355f1867..64ec0c2e2` で `run-owner-stop.ts` を変えた commit は無い。`process-provider.ts` の変更〔#4310・#4422〕は版の食い違いの文と resume の案内だけで、detached の起こしは同じ。#4375〔`372a494c9`〕は `archon serve` の cancel が bash・script のノードの木を止める変更で、provider と切り離した持ち主には触れない）。
- 実測（2026-10-18、`355f1867` で、止めた Archon に偽の claude〔`CLAUDE_BIN_PATH`。自分と同じグループの子と、別のセッションの子を起こして眠る〕の AI のノードと、`workflow:` の子の run の AI のノードを並べた使い捨てのグラフ。試験 `tests/bin/test_runstop.py` のグラフと同じ形）:
  - `--detach` の run の `workflow cancel` は `"processStopped": true` を返すが、ノードごとの provider（`bun --no-env-file <源>/packages/providers/src/claude/plugin.ts`）が親 1 で残った。数秒の後に provider は claude を止めたが、provider 自身と claude の子（同じグループの物も別のセッションの物も）は 15 秒の後も残った。子の run のノードも同じ。
  - 前の run の `workflow cancel` は拒んで（終了の値 1）何も止めず、持ち主に SIGTERM を送る（割り込みと同じ）と、持ち主は抜けたが provider と claude の子が親 1 で残った。
  - 子の run だけの `workflow cancel` は根の持ち主が答えて子を止め、子の provider のグループは消えたが、claude が別のセッションに起こした子は残った。
- 埋め: `bin/_lib/runstop.py`。殻が `workflow cancel <run>` の時だけ Archon を子として起こし、前と後で run のプロセスを数えて残りを止める。印は 2 つ: run と、Archon の記録（`workflow runs` の `parent_run_id`）で辿れる子の run の完全な id（`workflow runs` が出す 8 字の短い id で打たれても、Archon の cancel と同じく `workflow get` で直す）を env の `WORKFLOW_ID` に持つ自分の利用者のプロセス（AI のノードも bash のノードも持つ。env は `ps -A -E -ww`〔macOS〕・`ps -A e -ww`〔Linux〕の args の後ろを読む）と、走っている根の run の生きた持ち主（`workflow get` の `execution_owner` で、この機械とこの利用者の物・`last_activity_at` より前に始まって Archon の本体の `workflow` の命令を走らせるプロセス）。どちらもその子孫を親子の鎖で拾い、cancel の前に数えた物の子孫は持ち主が消えた後も辿る。持ち主のグループとセッションでは拾わない（前の命令の持ち主はシェルのジョブの長で、`| tee` の相手が同じグループに居る）。cancel の後に、生きた物へ SIGTERM、`lib/tree_run.py` の `KILL_GRACE` 秒の後に SIGKILL を 1 本ずつ送る。cancel が拒んだ前の run の持ち主も止め（run は failed になる）、残りが無ければ 0 で抜ける。持ち主の木を数えない時（running でない・子の run・持ち主が別の機械・別の利用者・居ない・番号に別の物が居る・`last_activity_at` が読めない）はその訳を、env を読めない時はその訳と手で探す命令を 1 行で出す。止めた物と、止めた後も残った物（pid とコマンドの名）を 1 行ずつ出す。Archon の命令の別名は作らない（持ち主の決め `one-launcher`）。
  - 足りない残り: env の `WORKFLOW_ID` を外して起こされた子孫で、数える前に親子の鎖が切れた物（拾う印が無い）。env を読めない環境では、持ち主の木（走っている根の run の生きた持ち主の子孫）だけを止める。
- 使うサブグラフ: メイングラフ（入口）と周の鎖
- 外す条件: cancel が provider のプロセスの木ごと止め、前の run も止められる版が出たら

## Archon の決めに合わせた形

Archon の穴でなく、Archon が決めてそうしている振る舞いに合わせた埋め。版が上がっても外れる見込みは無い。行の形と照らしは「今の行」と同じ。


### P14 AI のノードに既定の無言の期限が当たる

- 穴: `idle_timeout` を書かない `prompt:`・`command:` のノードと `loop:` の 1 周に、Archon が provider から何も届かない 30 分で打ち切りを当てる。
- 証拠:
  - `packages/workflows/src/utils/idle-timeout.ts` の「export const STEP_IDLE_TIMEOUT_MS = 30 * 60 * 1000;」
  - `packages/docs-web/src/content/docs/guides/loop-nodes.md` の「`idle_timeout` — per-iteration timeout (default: 30 minutes)」
- 上流（`64ec0c2e` の後の dev の `64ec0c2e2` まで）: 塞がっていない（止めた版が dev の頭。#4355 が期限を外したのは `bash:`・`script:` と `until_bash` だけ）。
- 埋め: 既定の期限が当たる鍵に置く、実質無しの値（値の持ち主は `tests/layers/scan.py` の `NO_DEADLINE` と `workflows/AGENTS.md` の E12。この行はそこを指すだけ）。もとは P9 の埋めの一部。
- 使うサブグラフ: AI の役を持つ全部
- 外す条件: `idle_timeout` を書かない AI のノードに期限を当てない版が出たら
### P8 落ちたノードの出力を受け直せない

- 穴: 落ちたノードの出力は `{from, if_skipped}` でも読めず、読んだノードも落ちる。
- 証拠:
  - `packages/workflows/src/dag-executor.ts` の「A binding never falls back to 'if_skipped' for a failed producer」（`resolveBindingDirective` が、落ちた producer を `assertProducerNotFailed` で止める）
- 上流（`64ec0c2e` の後の dev の `64ec0c2e2` まで）: 塞がっていない（止めた版が dev の頭。`355f1867..64ec0c2e2` の 87 commit で、証拠の字と、その辺りの振る舞いは変わっていない）。
- 埋め: メイングラフの受け皿のノード（`<include の id>-out` の形。script `workflows/line/scripts/returned.py`、置き場 `workflows/line/works-factory-line.yaml`）。受けるノードの後ろに既定の `trigger_rule` で置き、受けるノードが落ちれば自分が飛ばされ、読む側（`collect`）は `if_skipped: null` に落とす。fix のレンズの出力の中継 `lens-reply`（script `workflows/fix/scripts/lens_reply.py`）も同じ形で、レンズが落ちても集め役 `lens-collect` が `if_skipped: null` で受けて先へ進む。merge の読み戻しのノード `pr-read`（script `workflows/merge/scripts/pr_read.py`）も同じ形で、PR を作る子の run（`pr-open`）が落ちれば飛ばされ、出力ノード `merge` が `if_skipped: null` で受けて作らずに止めた訳を返す。
- 使うサブグラフ: メイングラフ・fix・merge
- 外す条件: 見込みは無い（Archon が落ちたノードの出力を `if_skipped` に落とさないと決めている。上の証拠の文）。決めが変わって落ちたノードの出力を `if_skipped` の既定に落として読める版が出たら

## 外した

### P9 鍵を書かないノードにも既定の期限が当たる

- 穴: `timeout` を書かない `script:`・`bash:` のノードにも、Archon が既定の期限で打ち切りを当てる。
- 証拠:
  - `packages/docs-web/src/content/docs/guides/script-nodes.md` の「Hard kill after this many milliseconds. Default: `120000` (2 min)」（`timeout` の欄）
- 上流（`355f1867` の後の dev の `f906471c4` まで）: 塞がった（upstream の #4355、`1e2d8acc0`。`timeout` を書かない `bash:`・`script:` のノードと `until_bash` に期限を当てない）。その前の #4307（`7c287f52e`）は期限の来たノードの process の木ごと止める変更。
- 外した埋め: `script:`・`bash:` の `timeout` と、`loop:`・`loop_group:` の `timeout`（`until_bash` の確かめ）に置いていた実質無しの値 `1728000000`。2026-10-18 に止めた版を `64ec0c2e` に上げた時に外した。その版で `timeout` を書かない `bash:`・`script:`・`loop_group:` の `until_bash` を 130 秒走らせ、どれも打ち切られずに終わった。今は E12 が `timeout` を書かせない（`tests/layers/scan.py` の `UNSET_DEADLINE_KEY`）。AI のノードの `idle_timeout` の値は P14 に残した。
- 使うサブグラフ: 全部
- 外す条件: グラフの既定で期限を無しにできる版が出たら
