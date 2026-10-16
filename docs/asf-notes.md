<!-- coldwrite:skip ASF から採った型の控え。語は docs/design.md の「語」のセクションで定義 -->
# ASF から採った型の控え

- ASF（AI software factory）: Archon の作者が `coleam00/Archon` の `.archon/workflows/sdlc/` に置く、SDLC（作業の受け付けから PR まで）のグラフの束。下の行の多くが引く `d97d00ef` は枝 `factory/sdlc-on-dev` の commit で、upstream の dev から消えたグラフ（lifecycle・merge-queue・verify-runtime など 8 本）を含む。
- ASF には LICENSE のファイルが無い。だからコードは写さず、型（なぜその形か）だけを採る（`AGENTS.md` の E8）。
- 見る版は止めた Archon（`docs/design.md` の「語」）（Archon の本体と同じ源。持ち主の決め `archon-same-as-asf`）。今は upstream の dev の `355f1867a1dceb6e913c368bab817ac4d9aa4add`（持ち主の決め `asf-follows-dev`）。`bin/` が取ったその源の `.archon/workflows/sdlc/` を横に並べて読む。下の行の commit は、その型を採った時の版。
- 下のパスは ASF のリポジトリの根からの相対。`W` は `.archon/workflows/sdlc` の略。

## 書き方

型を 1 つ採るたびに 1 セクションを足す。

```
### A<番号> <型の短い名>
- ASF: <commit の頭 8 字> の <ファイル>:<行>（短い引用）
- なぜその形か: ASF がその形を選んだ訳（ASF の文書かコメントから。無ければ自分の読みと書く）
- 採った先: <このリポジトリのサブグラフ・ファイル>
- 違い: ASF と違う所と、その訳
```

ASF の版を進めた時は、各セクションの行を新しい版で読み直し、変わった所をセクションに書き足す。

## 採った型

### A1 出力は 1 つのノードの構造体（returns）

- ASF: d97d00ef の `W/triage/archon-triage.yaml`:41-43（`returns: verdict`）。呼び手は `$triage.output.route` の形で読む（`W/ship/archon-ship.yaml`:79）。
- なぜその形か: 呼び手が子の中のノードの名を知らずに、決まった 1 つの型だけを読める。
- 採った先: 全サブグラフ（`workflows/AGENTS.md` の E5）。型の正本は出力ノードの `output_format`。
- 違い: 無し（写しの型を別に持たない。持ち主の決め `io-in-output-format`）。

### A2 仕事の結末の欄（outcome_field）

- ASF: d97d00ef の `W/implement/archon-implement.yaml`:22-23（`returns: implement` / `outcome_field: green`）。26 行のコメント「Run success ≠ green」。
- なぜその形か: run が終わったことと、仕事がうまくいったことは別の事実。「直す物は無い」も正しい終わり方として返せる。
- 採った先: 全サブグラフ。メイングラフの結末は今の works の結末の語（10 語）を運ぶ。
- 違い: 無し。

### A3 緑の認証（gate-green）

- ASF: d97d00ef の `W/deliver/archon-deliver.yaml`:525-537 のノード `gate-validated`（`script: gate-green`・`output_type: green-gate`）。本体 `W/deliver/scripts/gate-green.ts`。赤のうち `introduced`（今回入れた）と原因の無い赤と `incomplete` を拒み、`inherited`（元から）と `environment`（環境）は証拠の要約つきで記録して通す。使い回しの指紋は `W/.shared/validation-evidence.ts`:11（HEAD と追跡ファイルの差分）。
- なぜその形か: 「緑と言った」でなく、赤の原因を分けた記録を 1 つの script が確かめて通す。後の段は判定でなく認証の記録を読む。
- 採った先: `workflows/test-gate/`（試験の関門）。赤の分けは今の works の「元から赤のテストの区別」（`lib/baseline_red`）。
- 違い: 認証に作業ツリーの指紋（HEAD と差分の hash）を必ず入れ、独立の目と merge はその指紋が今の木と同じ時だけ認証を使う。今の works の赤緑の判定は JUnit の結末の XML を機械が読むので、役の分類だけには頼らない。

### A4 型つきの成果物を型で引く

- ASF: d97d00ef の `W/.shared/report.ts`:141-206（`artifactsByType['green-gate']` を読み、`envelope.errors` を 1 件ずつ注意として出す）。役の側は `W/review/commands/review-synthesize.md`:18（「Match the artifacts' node identities to that mode node's include prefix (`path`) and their `loopGroupPath` to its `invocation.loopPath`; never count another include, iteration or run.」）。
- なぜその形か: 置き場の名前の決まりを知らずに、型の名だけで集まりを引ける。ほかの include・ほかの周の物を数えない。
- 採った先: report サブグラフの中の `workflows/report/scripts/facts.py`（`workflows/AGENTS.md` の E5「型つきの成果物の一覧を読むのは report サブグラフだけ」「読む部品は report サブグラフの中に置く」）。
- 違い: 絞りと `errors` の扱いを report の中の 1 か所に置く。include の名を決め打たず、一覧に在る include の頭で組に分ける。

### A5 外への書き込みは 1 つの script ノード

- ASF: d97d00ef の `W/README.md`:82-93（「Public writes belong to a script」「fails unless the result reads back」）。実例 `W/review/archon-review.yaml`:264-270 の `publish`（コメント「this node owns the one public write」）、`W/merge-queue/scripts/merge-action.ts`:337-369（merge の後に `gh pr view` で `MERGED` を確かめる）。
- なぜその形か: 書き込みの場所が 1 つなら、監査も再試行もそこだけ見ればよい。forge は書き込みを受けて黙って当てないことがあるので、終了の値 0 を証拠にしない。
- 採った先: merge の出力ノード `merge`。書き先は run の置き場の `merge/sealed.diff`・`merge/apply.diff`・`merge/refused.diff` だけで、`lib/seal.py` の `write_readback` が書いて読み戻し、合った時だけ置く。report は run の置き場の `report/` に置くだけで外へ書かない。`workflows/AGENTS.md` の E6・E17。
- 違い: ASF は PR と main へ書く。works-factory の既定は対象のリポジトリにも GitHub にも書かない（E17。持ち主の決め `diff-only-to-target`）。対象へ当てるのは人で、`bin/apply`（中身は `bin/_lib/apply.py`）が封じた hash を照らしてから当てる。PR を作る・merge する道は、使う人が選んだ時だけ働く足しとして後で足し、その時にこの型（1 つの script ノード・読み戻し）を当てる（`docs/design.md`:413）。

### A6 merge の計画の封印

- ASF: d97d00ef の `W/merge-queue/scripts/merge-action.ts`:214（「The gate seals the plan: its digest of the file, taken here right after the assessment, is what approval and execution bind to.」）と :281（`if (gated.plan_digest !== current.digest) { stop(..., 'approved merge plan changed');`）。承認の文に digest が入る（`W/merge-queue/archon-merge-queue.yaml`:182）。
- なぜその形か: 人が承認した物と、実際に当てる物が同じだと縛る。承認の後に中身が変われば止まる。
- 採った先: merge（最後の承認ノードで人が通した差分の hash を封じ、取り込む前に照らす）。
- 違い: 封じる物は、今の works の取り込みの単位（run の差分と始めの版）。

### A7 守りのパス（protected paths）

- ASF: d97d00ef の `W/merge-queue/archon-merge-queue.yaml`:40-43（入力の説明「A match holds the PR: a human must make that change.」）と :73-81 のノード `path-policy`。拒みは `W/merge-queue/scripts/merge-action.ts`:178。理由は `W/merge-queue/README.md`:34-35（「a reviewed delivery once rewrote one and merged unflagged.」）。
- なぜその形か: 審査を通っても、決まった所の変更は人がする。
- 採った先: 2 か所。(1) merge: 対象のリポジトリの守りのパスに当たる差分は人に回す（今の works の `protected.json` と最後の承認ノード）。(2) このリポジトリ自身: 共有のファイル（`workflows/.shared/`・`workflows/line/`）を守りのパスとして ASF の lifecycle に渡し、土台の持ち主の手に残す（`docs/design.md` の作りの順の段 2）。(2) は dev の ASF に lifecycle も merge-queue も無いので当てていない（`asf-follows-dev`）。
- 違い: 無し。

### A8 engineering.md を横に置き、役が引く

- ASF: d97d00ef の `W/README.md`:148-159。実装役 `W/implement/commands/implement.md`:40（「If the repository has an `engineering.md` or a direction document ..., read them before writing code」）。審査役 `W/review/commands/review-code.md`:5（「a preference one of them states is a finding you cite, and one none of them states is taste you leave out.」）。
- なぜその形か: 審査の指摘を、書いてある決まりに縛る。書いてない好みは指摘しない。
- 採った先: (1) このリポジトリの `engineering.md`（ASF でこのリポジトリを作る時に、ASF の役が読む）。(2) works-factory の計画・修正・独立の目の役も、対象のリポジトリに `engineering.md` か方向の文書が在れば読み、引いて書く。
- 違い: 決まりに番号（`E1` など）を振り、指摘は番号で引く。

### A9 どの道でも自分の 1 つの出力を返す出力ノード（if_skipped で飛ばされた子を null で受ける）

- ASF: d97d00ef の `W/ship/archon-ship.yaml`:58-59（`returns: outcome` / `outcome_field: delivered`）と 139-148（`trigger_rule: none_failed_min_one_success`、`delivered: { from: "$deliver.output.pr_url", if_skipped: null }`）。
- なぜその形か: 子を飛ばす正しい道（止め・直す物が無い）でも、グラフの出力は 1 つの型で人と呼び手に届く。飛ばされた子は null で受け、落ちた子は受けない（落ちたノードの名が run の記録に残る）。
- 採った先: メイングラフ（`workflows/line/works-factory-line.yaml`）の出力ノード `result` と、中継のノード `answer-*`・`collect`（埋め P2）と、`judged`・`fixed`（飛ばされうる再審・2 度目の修正の出力を `if_skipped: null` で受けて合わせる）。
- 違い: メイングラフの報告はどの道でも出すので、集めるノード `collect`・`report`・`result` は `trigger_rule: all_done`（前の段が落ちても走る）。include の `with:` に束ねが書けないので、サブグラフへ渡す前にメイングラフの `script:` のノードで受け直す（ship は出力ノードだけで受ける）。

### A10 承認ノードは決めの語（decisions）と when: で道を分ける

- ASF: d97d00ef の `W/merge-queue/archon-merge-queue.yaml`:176-187（`approval:` の `decisions` に `approve`・`hold`、`when:` で承認ノードを開くかを決める）と 225 行（後ろのノードが `{ from: "$approval.output", if_skipped: null }` で答えを受ける）。
- なぜその形か: 決めの語はどれも承認ノードを終えるだけで、どこへ進むかはグラフの配線が決める（Archon の `cancel` に頼ると後ろのノードが走らない）。
- 採った先: メイングラフの 4 つの承認ノード（`gate-start`・`gate-before-fix`・`gate-replan`・`gate-final`）。`decisions` は `approve`・`continue`・`stop`・`reject`（`reject` は `stop` と同じ）。
- 違い: 承認ノードを開くかと見せる文はメイングラフの script（`ask-*`）が決め、答えは中継のノード（`answer-*`）が `{go, answer, stop_reason}` にして後ろの `when:` に渡す。`stop` は後ろを飛ばして報告へ進む（結末 `stopped_by_human`）。

### A11 include を展開した id に stub を置き、自分の script を走らせる筋書き

- ASF: d97d00ef の `W/ship/fixtures/planned-delivered.stubs.yaml`（`deliver__impl__implement` のように include を展開した id に stub を置き、`exec-code: true` で stub の無い `outcome` の script を本当に走らせる）。
- なぜその形か: 役（AI）を起こさずに、グラフの道筋と自分の script の決めを確かめる。stub は出力ノードの形を守らされる（`dry-run.ts` の `assertAuthoredStubSatisfiesSchema`）。
- 採った先: メイングラフの筋書き `workflows/line/fixtures/*.stubs.yaml`。
- 違い: メイングラフと本物の 8 つのサブグラフを置いて回し（`tests/e2e/test_line_scenarios.py`）、サブグラフのノードには、そのノードの `output_format` に合う stub を置く。dry-run の制約と、それに合わせた stub の置き方は `docs/design.md` の U3。

### A12 頭の振り分けの AI が根拠つきで道を決め、後ろの段を when で飛ばす

- ASF: d97d00ef の `W/ship/archon-ship.yaml`（頭の `triage` が `route` を返し、`deliver` の道では計画のノード `planned` を `when: "$triage.output.route == 'plan'"` で飛ばす）と `W/triage/archon-triage.yaml`（triage ノードの注: 根拠の無い道は出さない）。
- なぜその形か: 易しい依頼に重い段を通さない。飛ばすのは Archon の `when` で、飛ばしたノードは run の記録に skipped で残る。
- 採った先: judge の `head-depth-*`（run の頭の深さを決める役と受け付け）。
- 違い: ノードは深さの `when` で飛ばさない（E20）。頭の決めは軽量・標準・重厚の 3 段で、役の引用を機械が照らし、通らなければ標準。段が足す機能は `docs/design.md` の「深さの段の表」（`lib/depth.py` の `TIERS`）に置く。計画の壁打ちはどの段でも省かない。
