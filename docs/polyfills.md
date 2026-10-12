<!-- coldwrite:skip 埋めの名簿。語は docs/design.md の「語」の節で定義 -->
# Archon の埋め（polyfill）の名簿

- 埋め（polyfill）: Archon（止めた Archon（`docs/design.md` の「語」））に無い物を、このリポジトリの側で補う小さな部品。Archon の中は直さない。
- `workflows/.shared/` のファイルは、境の口（Archon との出入りのモジュール 1 つ）か、この名簿の行のどれかに当たる（`workflows/AGENTS.md` の E2。試験 `tests/layers/test_polyfills_listed.py` が照らす）。
- 埋めの一部は入口 `bin/` に置く物もある。置き場の欄に書く。
- Archon の新しい版で穴が塞がったら、外す条件を確かめて埋めを消し、行を「外した」の節へ移す。

## 書き方

```
### P<番号> <穴の短い名>
- 穴: Archon でできないこと（1〜2 文）
- 証拠: 止めた版の Archon の文書かソースの引用と在り処
- 埋め: 何を置くか（置き場のパス。予定ならパスの直後に「（予定）」）
- 使うブロック: 
- 外す条件: Archon のどの振る舞いが入ったら消せるか
```

## 今の行

### 候補（まだ埋めでない）: fan_out の子ごとの作業ツリー

- 修正の組の並べは Archon の `fan_out:` で書く（持ち主の決め `no-queue`。埋めは要らない）。
- 組ごとに別の作業ツリーが要る。`workflow:` と `fan_out:`（`isolation: worktree`）の子の run は組ごとに起き、子ごとに作業ツリーが切られる。子の作業ツリーは親の姿を写せ、子は親の run の置き場に結果を書ける（止めた Archon で 2026-10-12 に実測。PR #94 の「組を並べて回せるか（計画の U8）の実測」。`docs/design.md` の U8）。
- remote（`origin`）の無い対象のリポジトリでは、子の作業ツリーが切れない（`no git remote is configured`。親の run そのものも remote が無いと作業ツリーを切れない）。fix は remote が在る時だけ組を並べ、無い時は親の作業ツリーで 1 つずつ回す（`groups-seq`）。埋めは要らない。
- 2026-10-06 の判断「fan_out は子ごとに作業ツリー（cwd）を決められない」は、節の `fan_out:` だけを見ていたかもしれない。U8 で読み直す。

### P1 持ち主が居なくなった running の run を再開できない

- 穴: Archon を動かしていた process が落ちると、run は `running` のまま残り、`resume` できない。
- 証拠: `packages/core/src/operations/workflow-operations.ts` 948 行の文「Cannot resume run with status 'running'. Only failed or paused runs can be resumed.」（再開できるのは `failed`・`paused` だけ。`schemas/workflow-run.ts` 164-167 行）。cancel は、走らせている process が答えない時（`no_owner_answered`）に「If its process is gone, abandon the run to release it.」と abandon を案内する（同じファイル 1250-1251 行）。
- 範囲: 長い待ち（CI・人の答え）は Archon の `wait:` の節と承認の節で書く。Archon 0.10.0 から待ちは持ちこたえる（CHANGELOG [0.10.0]「The database owns suspension and resume claims, so process restarts … cannot reset a wait」。server が期限の来た run を再開する）。だからこの穴に当たるのは、節を走らせている途中で process が落ちた run だけ。
- 埋め: `bin/apply`（#101。続けられない run の差分を取り出して対象に当てる。今の works の apply と同じ能力）。Archon の命令だけでは足りない: 下の実測のとおり `abandon` は書きかけごと作業ツリーを消し、`--adopt` は最初の節からやり直すので、持ち主の決め `carry`（止まった run の差分も捨てない。`docs/owner-decisions.md`）を満たさない。手放しと続きの起こしは止めた Archon の命令をそのまま打つ（入口に別名を作らない。持ち主の決め `one-launcher`）。
  - 足りない残り: 節の途中で持ち主が落ちた run の、commit していない書きかけ。`bin/apply` は終わっていない run（`terminal_record` が null。手放す前の `running`）を拒み、手放した後は作業ツリーが消えている（commit 済みの物は残った枝に在る）。だから今は、手放す前に人が `workflow get <run> --json` の `working_path` で作業ツリーの変更（新しいファイルを含む）を取り出しておく。
  - 持ち主に聞く項にしない: 持ち主の決め `carry` と既にある `bin/apply` で答えが 1 つに決まる（運び役の決め。PR #182 の 1 回目の修理）。
- 実測（段 1b、2026-10-12。止めた Archon に AI の無い使い捨ての工程。節 `write` が書きかけのファイルを書いて眠り、後ろに `trigger_rule: all_done` の節 `tail`。run `4300fc39121ab1838cc25c38fcf83e98`）: `write` が走っている間に `--detach` の子のプロセスを pid で止めた（`kill -9`）。run の記録は使い捨ての Archon の家と一緒に消え、id から読み戻せない（下の「再現」で回し直す）。
  - `workflow get` は `running` のまま。`workflow wait --json` は終了の値 0 で `"result": "owner_lost"`・`"observedStatus": "running"`。
  - `workflow resume <run> --json` は拒む（「Cannot resume run with status 'running'. Only failed or paused runs can be resumed.」）。`workflow run --adopt <run>` も手放す前は拒む（「it is still running. … abandon it first」）。
  - `workflow abandon <run> --json` は `owner.outcome: no_owner_answered` と記録した pid を出し、run を `cancelled` にし、run が作った作業ツリーを書きかけのファイルごと消す（`releasedWorktrees`）。枝は残る。
  - その後の `workflow run <工程> --adopt <run> --detach --json` は新しい id の run（`a21aee649292b6b07be27e96aa8e6496`。`adopted_from_run_id` が前の run）を起こし、残った枝で同じパスに作業ツリーを作り直し、最初の節からやり直す（前の run の終わった節を飛ばさない）。後ろの `all_done` の節 `tail` は走った。
  - 持ち主を `kill -9` で止めても、走っていた節の子のプロセス（`bash -c …` と `sleep`）は残って走り続けた（親が 1 になる）。`abandon` は持ち主が答えない時はプロセスを止めない（「Nothing decides the run is dead from its age or pid」）。手放す前に、残った子を pid で止める。
  - 線は `interactive: true` なので、線の `--adopt` は `--detach` を付けずに打つ（`docs/design.md` の「Archon の分かっていること」）。線の報告の節が `--adopt` の run で走るか（棚卸しの L-W60 の resume の半分）は、AI の役を起こす認証が要るので運び役の確かめ待ち。
- 再現（AI の役も認証も要らない。工程は `tests/e2e/owner-lost-probe/`。プロセスを止めるので試験にせず手で回す。形だけは `tests/e2e/test_resume_probe.py` が validate で照らす）:
  1. 使い捨ての git の木に工程を `.archon/workflows/works-factory/owner-lost-probe/` の形で置いて commit し、空の bare のリポジトリを `origin` に足して push する（`remote` が無いと Archon は作業ツリーを切れずに落ちる）。`ARCHON_HOME` も使い捨てにする。
  2. `workflow run works-factory-owner-lost-probe --detach --json` を打ち、`workflow get <run> --json` の `working_path` に `half-written.txt` が出るのを待つ。
  3. `ps` を使い捨ての木のパスで絞って `workflow run … --internal-detached-run-id …` の持ち主の pid を見つけ、`kill -9 <pid>`。
  4. `workflow wait <run> --json --timeout 10`（`owner_lost`）・`workflow resume <run> --json`（拒む）・`workflow run works-factory-owner-lost-probe --adopt <run> --detach --json`（拒む）を見る。
  5. 残った節の子（`bash -c echo half > half-written.txt; sleep 600` と、それを親に持つ `sleep`）を pid で止め、`workflow abandon <run> --json` を打ち、作業ツリーが消えたことを見る。
  6. `workflow run works-factory-owner-lost-probe --adopt <run> --detach --json` で新しい run を起こし、`write` が最初から走ることを見る。その `sleep` の pid と新しい持ち主の pid を止め、使い捨ての木と家を消す。
- 使うブロック: 線（入口）
- 外す条件: 持ち主の居ない `running` を Archon が自分で `failed` にするか、`resume` を受け付ける版が出たら

### P2 include の入力に if_skipped を通せない

- 穴: 線がブロックを `include:` で呼ぶ時、`with:` に `{from, if_skipped}` の束ねを書いても、飛ばされた前の節の代わりの値がブロックの中まで運ばれない。
- 証拠: 止めた Archon の `packages/workflows/src/schemas/dag-node.ts` 270-282 行（束ね `{from, if_skipped}` は `command:`・`script:` の `with:` だけの形で、「Include/workflow `with:` maps have no directive, so objects there stay ordinary JSON literals.」）と、`packages/workflows/src/include-expander.ts` 619 行（include の展開は `binding.if_skipped` の欄を置き換えずにそのまま残す。`if (slot.surface === 'binding_from' || slot.name === 'binding.if_skipped') return slot.value;`）。書いた束ねは黙って JSON の値として渡り、書けたように見えて効かない。
- 埋め: 線の返しの節。飛ばされうる値を、線の `script:` の節の `with:` で欄ごとに `{from: "$<節>.output.<欄>", if_skipped: null}` で受け、明示の値で返し直す。ブロックにはその節の返りを渡す。P2 のために在る返しの節は `workflows/line/works-factory-line.yaml` の `answer-*`（関所の答えを fix・merge に渡す）と `collect`（全部の返りを report に渡す）だけ。Archon が `INPUTS_<名>` に渡した字を値に戻す部品は `workflows/.shared/skip_value.py`。
- 使うブロック: 線
- 外す条件: include の `with:` に書いた `if_skipped` が子の中まで効く版が出たら

### P3 --workflow-source が任意のフォルダを読まない

- 穴: `--workflow-source <dir>` は `<dir>/.archon/workflows/` しか読まない。自分の工程のフォルダ（リポジトリの `workflows/`）を直に渡せない。
- 証拠: 止めた Archon の `packages/cli/src/cli.ts` 805-825 行と `packages/paths/src/archon-paths.ts` 378 行。
- 埋め: `bin/_lib/place.py` の `workflow_source`。キャッシュの中に置き場を作り、その `.archon/workflows/works-factory`（pack の形。名は `pack.json` の `ours.pack`）からリポジトリの `workflows/` へ symlink を張る。
- 使うブロック: 線（入口）
- 外す条件: `--workflow-source` に任意のフォルダを渡して、その中の工程を読める版が出たら

## 外した

（まだ無い）
