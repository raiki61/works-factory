<!-- coldwrite:skip ASF から採った型の控え。語は docs/design.md の「語」の節で定義 -->
# ASF から採った型の控え

- ASF（AI software factory）: Archon の作者が `coleam00/Archon` の枝 `factory/sdlc-on-dev` の `.archon/workflows/sdlc/` に置く、SDLC（作業の受け付けから merge まで）の工程の束。
- ASF には LICENSE のファイルが無い。だからコードは写さず、型（なぜその形か）だけを採る（`engineering.md` の E8）。
- 見る版は `pack.json` の `asf.commit` で止める。今は `d97d00ef15cce4b15d39e42635e4e86996ec1351`。`bin/` が run の時にその版を Archon の家の `workflows/asf/` に置くので、横に並べて読める。
- 下のパスは ASF のリポジトリの根からの相対。`W` は `.archon/workflows/sdlc` の略。

## 書き方

型を 1 つ採るたびに 1 節を足す。

```
### A<番号> <型の短い名>
- ASF: <commit の頭 8 字> の <ファイル>:<行>（短い引用）
- なぜその形か: ASF がその形を選んだ訳（ASF の文書かコメントから。無ければ自分の読みと書く）
- 採った先: <このリポジトリのブロック・ファイル>
- 違い: ASF と違う所と、その訳
```

ASF の版を進めた時は、各節の行を新しい版で読み直し、変わった所を節に書き足す。

## 採った型

### A1 返りは 1 つの節の構造体（returns）

- ASF: d97d00ef の `W/triage/archon-triage.yaml`:41-43（`returns: verdict`）。呼び手は `$triage.output.route` の形で読む（`W/ship/archon-ship.yaml`:79）。
- なぜその形か: 呼び手が子の中の節の名を知らずに、決まった 1 つの型だけを読める。
- 採った先: 全ブロック（`engineering.md` の E5）。型の正本は返す節の `output_format`。
- 違い: 無し（写しの型を別に持たない。持ち主の決め `io-in-output-format`）。

### A2 仕事の結末の欄（outcome_field）

- ASF: d97d00ef の `W/implement/archon-implement.yaml`:22-23（`returns: implement` / `outcome_field: green`）。26 行のコメント「Run success ≠ green」。
- なぜその形か: run が終わったことと、仕事がうまくいったことは別の事実。「直す物は無い」も正しい終わり方として返せる。
- 採った先: 全ブロック。線の結末は今の works の結末の語（10 語）を運ぶ。
- 違い: 無し。

### A3 緑の認証（gate-green）

- ASF: d97d00ef の `W/deliver/archon-deliver.yaml`:525-537 の節 `gate-validated`（`script: gate-green`・`output_type: green-gate`）。本体 `W/deliver/scripts/gate-green.ts`。赤のうち `introduced`（今回入れた）と原因の無い赤と `incomplete` を拒み、`inherited`（元から）と `environment`（環境）は証拠の要約つきで記録して通す。使い回しの指紋は `W/.shared/validation-evidence.ts`:11（HEAD と追跡ファイルの差分）。
- なぜその形か: 「緑と言った」でなく、赤の原因を分けた記録を 1 つの script が確かめて通す。後の段は判定でなく認証の記録を読む。
- 採った先: `workflows/test-gate/`（試験の関門）。赤の分けは今の works の「元から赤のテストの区別」（`lib/baseline_red`）。
- 違い: 認証に作業ツリーの指紋（HEAD と差分の hash）を必ず入れ、独立の目と merge はその指紋が今の木と同じ時だけ認証を使う。今の works の赤緑の判定は JUnit の結末の XML を機械が読むので、役の分類だけには頼らない。

### A4 型つきの成果物を型で引く

- ASF: d97d00ef の `W/.shared/report.ts`:141-206（`artifactsByType['green-gate']` を読み、`envelope.errors` を 1 件ずつ注意として出す）。役の側は `W/review/commands/review-synthesize.md`:18（「Match the artifacts' node identities to that mode node's include prefix (`path`) and their `loopGroupPath` to its `invocation.loopPath`; never count another include, iteration or run.」）。
- なぜその形か: 置き場の名前の決まりを知らずに、型の名だけで集まりを引ける。ほかの include・ほかの周の物を数えない。
- 採った先: 境の口 `workflows/.shared/`（型で引く口 1 つ）。使うのは eyes（R1〜R4 の結果）・report・fix（枝の結果）。
- 違い: 絞りと `errors` の扱いを境の口 1 か所に置き、ブロックの script は口を呼ぶだけにする（`engineering.md` の E5）。

### A5 外への書き込みは 1 つの script の節

- ASF: d97d00ef の `W/README.md`:82-93（「Public writes belong to a script」「fails unless the result reads back」）。実例 `W/review/archon-review.yaml`:264-270 の `publish`（コメント「this node owns the one public write」）、`W/merge-queue/scripts/merge-action.ts`:337-369（merge の後に `gh pr view` で `MERGED` を確かめる）。
- なぜその形か: 書き込みの場所が 1 つなら、監査も再試行もそこだけ見ればよい。forge は書き込みを受けて黙って当てないことがあるので、終了の値 0 を証拠にしない。
- 採った先: merge（main への取り込みと PR）・report（人に見える報告）。`engineering.md` の E6。
- 違い: 無し。

### A6 merge の計画の封印

- ASF: d97d00ef の `W/merge-queue/scripts/merge-action.ts`:214（「The gate seals the plan: its digest of the file, taken here right after the assessment, is what approval and execution bind to.」）と :281（`if (gated.plan_digest !== current.digest) { stop(..., 'approved merge plan changed');`）。承認の文に digest が入る（`W/merge-queue/archon-merge-queue.yaml`:182）。
- なぜその形か: 人が承認した物と、実際に当てる物が同じだと縛る。承認の後に中身が変われば止まる。
- 採った先: merge（最後の関所で人が通した差分の hash を封じ、取り込む前に照らす）。
- 違い: 封じる物は、今の works の取り込みの単位（run の差分と始めの版）。

### A7 守りのパス（protected paths）

- ASF: d97d00ef の `W/merge-queue/archon-merge-queue.yaml`:40-43（入力の説明「A match holds the PR: a human must make that change.」）と :73-81 の節 `path-policy`。拒みは `W/merge-queue/scripts/merge-action.ts`:178。理由は `W/merge-queue/README.md`:34-35（「a reviewed delivery once rewrote one and merged unflagged.」）。
- なぜその形か: 審査を通っても、決まった所の変更は人がする。
- 採った先: 2 か所。(1) merge: 対象のリポジトリの守りのパスに当たる差分は人に回す（今の works の `protected.json` と最後の関所）。(2) このリポジトリ自身: 共有のファイル（`workflows/.shared/`・`workflows/line/`）を守りのパスとして ASF の lifecycle に渡し、土台の持ち主の手に残す（`docs/design.md` の作りの順の段 2）。
- 違い: 無し。

### A8 engineering.md を横に置き、役が引く

- ASF: d97d00ef の `W/README.md`:148-159。実装役 `W/implement/commands/implement.md`:40（「If the repository has an `engineering.md` or a direction document ..., read them before writing code」）。審査役 `W/review/commands/review-code.md`:5（「a preference one of them states is a finding you cite, and one none of them states is taste you leave out.」）。
- なぜその形か: 審査の指摘を、書いてある決まりに縛る。書いてない好みは指摘しない。
- 採った先: (1) このリポジトリの `engineering.md`（ASF の lifecycle でこのリポジトリを作る時に、ASF の役が読む）。(2) works-factory の計画・修正・独立の目の役も、対象のリポジトリに `engineering.md` か方向の文書が在れば読み、引いて書く。
- 違い: 決まりに番号（`E1` など）を振り、指摘は番号で引く。
