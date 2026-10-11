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
- 組ごとに別の作業ツリーが要る。`workflow:` と `fan_out:` の子の run がそれぞれ自分の作業ツリーを持ち、親の今の commit から切られ、差分を親に戻せるかを段 1 で確かめる（`docs/design.md` の未決 U8）。足りないと分かった時だけ、ここに埋めの行を足す。
- 2026-10-06 の判断「fan_out は子ごとに作業ツリー（cwd）を決められない」は、節の `fan_out:` だけを見ていたかもしれない。U8 で読み直す。

### P1 持ち主が居なくなった running の run を再開できない

- 穴: Archon を動かしていた process が落ちると、run は `running` のまま残り、`resume` できない。
- 証拠: `packages/core/src/operations/workflow-operations.ts` 948 行の文「Cannot resume run with status 'running'. Only failed or paused runs can be resumed.」（再開できるのは `failed`・`paused` だけ。`schemas/workflow-run.ts` 164-167 行）。cancel は、走らせている process が答えない時（`no_owner_answered`）に「If its process is gone, abandon the run to release it.」と abandon を案内する（同じファイル 1250-1251 行）。
- 範囲: 長い待ち（CI・人の答え）は Archon の `wait:` の節と承認の節で書く。Archon 0.10.0 から待ちは持ちこたえる（CHANGELOG [0.10.0]「The database owns suspension and resume claims, so process restarts … cannot reset a wait」。server が期限の来た run を再開する）。だからこの穴に当たるのは、節を走らせている途中で process が落ちた run だけ。
- 埋め: 置き場は未定（入口に Archon の命令の別名を作らない。持ち主の決め `one-launcher`）。止めた Archon の `workflow cancel`・`abandon` は持ち主の居ない run に abandon を案内し（`reference/cli.md` 921-1028 行）、`workflow run --adopt <run>` で続きを起こせる。それで足りるかを段 1 で確かめる。
- 使うブロック: 線（入口）
- 外す条件: 持ち主の居ない `running` を Archon が自分で `failed` にするか、`resume` を受け付ける版が出たら

### P2 include の入力に if_skipped を通せない

- 穴: 線がブロックを `include:` で呼ぶ時、`with:` に `{from, if_skipped}` の束ねを書いても、飛ばされた前の節の代わりの値がブロックの中まで運ばれない。
- 証拠: 2026-10-11 のソースの読み。`packages/workflows/src/include-expander.ts` 619 行で、include の展開は `binding.if_skipped` の欄を置き換えずにそのまま残す（`if (slot.surface === 'binding_from' || slot.name === 'binding.if_skipped') return slot.value;`）。実物の振る舞いは歩く骨組みで確かめる。
- 埋め: 線の YAML の形の決まり（予定）。include の前に、飛ばされうる値を `if_skipped` で受けて明示の値（`null` など）で返す小さな `script:` の節を線の中に置き、ブロックにはその節の返りを渡す。script は `workflows/.shared/skip_value`（予定）。
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
