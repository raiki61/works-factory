<!-- coldwrite:skip 埋めの名簿。語は docs/design.md の「語」の節で定義 -->
# Archon の埋め（polyfill）の名簿

- 埋め（polyfill）: Archon v0.11.1 に無い物を、このリポジトリの側で補う小さな部品。Archon の中は直さない。
- `workflows/.shared/` のファイルは、境の口（Archon との出入りのモジュール 1 つ）か、この名簿の行のどれかに当たる（`engineering.md` の E2。試験 `tests/layers/test_polyfills_listed.py` が照らす）。
- 埋めの一部は入口 `bin/` に置く物もある。置き場の欄に書く。
- Archon の新しい版で穴が塞がったら、外す条件を確かめて埋めを消し、行を「外した」の節へ移す。

## 書き方

```
### P<番号> <穴の短い名>
- 穴: Archon でできないこと（1〜2 文）
- 証拠: v0.11.1 の文書かソースの引用と在り処
- 埋め: 何を置くか（置き場のパス。予定なら「予定」）
- 使うブロック: 
- 外す条件: Archon のどの振る舞いが入ったら消せるか
```

## 今の行

### P1 並べの枝の数が固定で、待ちの列を Archon が持たない

- 穴: 修正を互いに触らない組に分け、空いた枝が待ちの列から次の組を取る形（今の works の修正の並べ）を、YAML の節の数を run ごとに変えずに書けない。Archon の YAML は節を字で並べる。
- 証拠: 今の works は枝の節を `<段>-lane-loop-1..3` と字で 3 本並べ、試験で枝の数 `MAX_LANES` と縛っている（works `docs/concepts.md` の `lanes`）。Archon の `fan_out:` は子の数を run の時に決められるが、子の作業ツリーの決め方は P2 の穴を持つ。
- 埋め: `workflows/.shared/lanes`（予定）。待ちの列の控え（組の目録と各組の状態）を run の置き場に置き、枝の節がそれぞれ「次の組を取る → 直す → 返す」を繰り返す。使う枝の数は機械が組の数から決める（持ち主の決め `parallel`）。YAML に並べる枝の節の数は Archon の制約から来る上限で、設計の上限ではない。上限は 1 か所の定数で持ち、YAML の節の数と試験で縛る。使わない枝の節は飛ばす。
- 使うブロック: fix
- 外す条件: 子ごとに作業ツリーの起点を決められる `fan_out:`（P2 の外す条件）が入り、空いた子が次の項目を取る形が書けたら。v0.11.1 の `fan_out:` と `isolation: worktree` で足りるかは `docs/design.md` の未決 U8 で確かめる

### P2 fan_out の子ごとに作業ツリー（cwd）を決められない

- 穴: `fan_out:` の子は、親の作業ツリーを共にするか、`isolation: worktree` で子ごとに新しい作業ツリーと枝をもらうかのどちらか。「run の今の木から切った枝で、決めた順に親へ戻す」の起点を子ごとに名指せない。
- 証拠: v0.11.1 の文書 `packages/docs-web/src/content/docs/guides/authoring-workflows.md`（Isolation の節）の表「write to the repo | `isolation: worktree` on the **fan-out node** — every child gets its own worktree and branch, at the cost described above, multiplied by N」。子ごとに作業ツリーのパスを渡す欄は無い（2026-10-11 の binary の読み）。
- 埋め: P1 と同じ `workflows/.shared/lanes`。枝の作業ツリーは埋めが git worktree で切り、枝の節にパスを入力で渡す。戻すのも埋めが決めた順に行う。
- 使うブロック: fix
- 外す条件: `fan_out:` の子ごとに作業ツリーのパス（か起点の版）を入力で渡せる版が出たら

### P3 持ち主が居なくなった running の run を再開できない

- 穴: Archon を動かしていた process が落ちると、run は `running` のまま残り、`resume` できない。
- 証拠: v0.11.1 の binary の文「Cannot resume run with status 'running'. Only failed or paused runs can be resumed.」。同じ所の cancel の文は「If its process is gone, abandon the run to release it.」と、abandon を案内する。
- 埋め: `bin/show`・`bin/start`（予定）。持ち主の居ない `running` を見つけたら人に知らせ、abandon してから、終わった段の成果を持ち越して新しい run を起こす。持ち越しの形は歩く骨組み（`docs/design.md` の作りの順の段 1）で決める。
- 使うブロック: 線（入口）
- 外す条件: 持ち主の居ない `running` を Archon が自分で `failed` にするか、`resume` を受け付ける版が出たら

### P4 include の入力に if_skipped を通せない

- 穴: 線がブロックを `include:` で呼ぶ時、`with:` に `{from, if_skipped}` の束ねを書いても、飛ばされた前の節の代わりの値がブロックの中まで運ばれない。
- 証拠: 2026-10-11 の binary の読み。v0.11.1 のソース `packages/workflows/src/include-expander.ts` 620 行で、include の展開は `binding.if_skipped` の欄を置き換えずにそのまま残す（`if (slot.surface === 'binding_from' || slot.name === 'binding.if_skipped') return slot.value;`）。実物の振る舞いは歩く骨組みで確かめる。
- 埋め: 線の YAML の形の決まり（予定）。include の前に、飛ばされうる値を `if_skipped` で受けて明示の値（`null` など）で返す小さな `script:` の節を線の中に置き、ブロックにはその節の返りを渡す。script は `workflows/.shared/skip_value`（予定）。
- 使うブロック: 線
- 外す条件: include の `with:` に書いた `if_skipped` が子の中まで効く版が出たら

## 外した

（まだ無い）
