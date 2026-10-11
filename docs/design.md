<!-- coldwrite:skip 設計の正本。語は冒頭の「語」の節で定義 -->
# works-factory の設計

状態: 2026-10-11 の初版。持ち主の決め（`docs/owner-decisions.md` の 2026-10-11 の行）から起こした。コードはまだ無い。

## 語

- Archon: AI の工程を YAML で書き、機械が順に回す道具。土台は公開版 v0.11.1。
- ASF（AI software factory）: Archon の作者が作った、作業の受け付けから merge までの工程の束（`coleam00/Archon` の枝 `factory/sdlc-on-dev` の `.archon/workflows/sdlc/`）。見る版は `pack.json` の `asf.commit`（`d97d00ef`）。
- 今の works: raiki61/claude-plugins の `works/`。工場 darkfactory を持つ。棚卸しは origin/main の 2026-10-11 の姿（待ちの列の commit `ab9b9f17` を含む）。
- review-graph: graphloops プラグインのレビューと修正の輪（`works/.shared/core/graphloops/graphs/review-loop.json`）。今の works の元。
- 線: ブロックを順に並べた 1 本の工程（`workflows/line/`）。
- ブロック: 線に `include:` で差し込む部品（`workflows/<名>/`）。ほかのブロックを知らない。
- 節: Archon の YAML の 1 つの node。
- 役: AI を起こす節。
- 人の関所: 人に答えを聞いて止まる節（Archon の承認の節）。
- 単位: 判定役が切った 1 つの欠陥。直す・拒む・諦めるの数え方の単位。
- 枝（レーン）: 単位の組を別の作業ツリーで直す並べの道。
- 待ちの列: 枝に入りきらない組を並べておく列。枝は自分の組を終えたら列から次の組を取る。
- エッセンス: 持ち主のグラフ（`workflows/`）。どの確かめと役が在り、各々が何をし、どの順でどうつながり、どこで人に聞くか。Archon の書き方（線とブロックの YAML・役の指示書 `commands/`・節の script `scripts/`）で書く。持ち主の言葉「で、私がエッセンスって呼んでるのはグラフの内容やグラフ全体の形かな。」（2026-10-11）
- lib: Archon を知らない Python の助け手（`lib/`）。script の節が呼ぶ（引用の照らし・TDD の赤の判定・元から赤の見分け・範囲の照らしなど）。エッセンスそのものではない。
- 境: Archon との出入りの口と、Archon に無い物を補う埋め（`workflows/.shared/`）。
- 埋め（polyfill）: Archon に無い物を外から補う部品。名簿は `docs/archon-polyfills.md`。
- 指し札: Archon の `{type: archon_artifact, run_id, path}`。run の置き場の中のファイルを指す。
- 型つきの成果物: 節の `output_type` で型の名を付けた出力。受け手は `$TYPED_ARTIFACTS_FILE` の一覧から型で引く。

## 目的

持ち主の自分版の工場を持つ。今の works の能力を 1 つも落とさず、作りは Archon と ASF に寄せて簡単にする。

- 持ち主の言葉（2026-10-11）: 「作りをASF参考にArchonに寄せたほうがいいのでは。確かめの中身とかはようはその上に載るエッセンスってことでしょ」
- 簡単にする訳: 「じゃないと後続がこうやって変換すればいいやって思っちゃうかもしれないでしょ」。だから YAML は変換しない（`engineering.md` の E1）。
- 今の works を直して寄せるのでなく、横に新しく作る（「横に自分のグラフつくりはじめるかんじでいいのではって思ってた」）。
- 最新の ASF を横に並べて見られる形にする（「その最新のソフト自動出荷工場を横目に見れる形じゃないとダメなのではという気がしてる」）。

## 4 つの層

```mermaid
flowchart TB
  entry["入口 bin/<br/>start・answer・show・apply"]
  subgraph home["Archon の家 $ARCHON_HOME/workflows/"]
    subgraph ours["works-factory/（workflows/ をそのまま置く。グラフ＝エッセンス）"]
      line["線 line/"]
      blocks["ブロック judge … merge"]
      shared["境 .shared/<br/>出入りの口・埋め"]
    end
    asf["asf/（ASF を run の時に置く。見るだけ）"]
  end
  lib["助け手 lib/<br/>Archon を知らない Python"]
  entry --> line
  line --> blocks
  blocks --> shared
  blocks --> lib
```

| 層 | 置き場 | 持つ物 | 知ってよい物 |
| --- | --- | --- | --- |
| 入口 | `bin/` | 人の打つ口・版の取り寄せと配置・埋めの一部 | `pack.json`・Archon の CLI |
| グラフ（エッセンス） | `workflows/` | 線とブロックの YAML・役の指示書・節の script・ブロックの間で渡す物の型（`output_format`） | 境の口・lib |
| 境 | `workflows/.shared/` | Archon の入出力の口 1 つ・埋め | Archon の変数と型 |
| 助け手 | `lib/` | Archon を知らない Python のモジュール | 標準ライブラリだけ |

- 言語は Python 3.12 以上の標準ライブラリ（`lib/`・境・ブロックの script・`bin/`・試験）。訳: 今の works の確かめが Python の標準ライブラリで書かれていて、移すだけで済む。下限は持ち主の決め `py-floor`。Archon v0.11.1 は `script:` の節を `runtime: uv` で Python として走らせる。ASF は TypeScript だが、コードを写さないので言語を揃える訳が無い。
- 層を足す時は `engineering.md` の E10。
- 別の実行の道具へ移る時（Archon の競合に移る危うさへの備え）: グラフをその道具の書き方で `docs/design.md` から書き直す。役の指示書（指示書の中の Archon の変数だけ書き換える）と `lib/` はそのまま持っていける。ブロックの間の入出力は、その時に `output_format` から取り出す（持ち主の決め `io-in-output-format`）。

## Archon・ASF・今の works との関係

- Archon: 土台。中は直さない。足りない所は埋め（`docs/archon-polyfills.md`）。開発元には連絡しない。
- ASF: 横に並べて見るだけ。`bin/` が同じ Archon の家の `workflows/asf/` に置き、工程の名（`archon-*` と `works-factory-*`）で選び分ける。v0.11.1 は家に置いた ASF の束を読む（40 本が並び、同じ名の同梱の工程を上書きする）。ASF の工程を走らせたことはまだ無い。採った型は `docs/asf-notes.md`。
- 今の works: 能力の正本。置き換えるまでは今の works が本番。能力を 1 つずつブロックと `lib/` へ移し、「能力の棚卸し」の表で追う。置き換えた後、claude-plugins の `works/` は `/works` の薄いスキルだけを残し、`bin/` を呼ぶ。

## pack.json

版の止めの正本。

- `archon`: 使う Archon の公開版（`v0.11.1`）と、取る実行ファイルの名ごとの sha256（今の works の `dev/archon.sh` と同じ値）。合わなければ止まる。
- `asf`: ASF の repo・枝・commit・フォルダ。`placed_at`（`workflows/asf`）は Archon の家の中の置き場。`committed_here: false` は、このリポジトリに入れないこと（LICENSE が無い）。
- `ours`: 自分の工程のフォルダ・置き場・名の頭（`works-factory-`）・線の名。

`bin/` は run の時に、`pack.json` の版の Archon と ASF を取り、`$ARCHON_HOME/workflows/asf/` と `$ARCHON_HOME/workflows/works-factory/` に置く。ほかの置き場には触らない。

## 線

```mermaid
flowchart TB
  start["始め（入力の形・始めの記録）"] --> g1{{"起動の関所"}}
  g1 --> tb["test-gate（base）"]
  tb --> judge
  judge --> loopP
  subgraph loopP["計画の往復（3 往復まで）"]
    plan --> pr["plan-review"]
  end
  loopP --> g2{{"修正前の関所"}}
  g2 --> fix
  fix --> tf["test-gate（final）"]
  tf --> eyes
  eyes --> ms["merge（seal）"]
  ms --> g3{{"最後の関所"}}
  g3 --> ma["merge（apply）"]
  ma --> report
```

### 順と関所

1. 始め（線の節）: 入口の入力を 1 つの形にそろえ、始めの記録を書く。差分も依頼の行も無ければ AI を起こす前に止める。
2. 起動の関所（人）: 何を始めるかを見せて止まる。
3. test-gate（base）: テストの走らせ方を見つけ、直す前の結末（元から赤のテスト）を控える。
4. judge: 前提・目的・定石・素材・判定。`--spec` の時は中に仕様の関所（人）を持つ。
5. 計画の往復: plan → plan-review を 3 往復まで。同じ所で 2 度続けて止められたら止める。
6. 修正前の関所（人）: 事前審査の 4 つの軸（自明・世界の解・汚くない・やりすぎでない）で人に聞く物がある時だけ開く。
7. fix: TDD の輪・並べの枝と待ちの列・修正役・裁定・差分の審査と手直し。裁定が計画の項目の誤りとした時は、1 run に 1 度だけ plan と plan-review をもう一度差し込み、案の直しの関所（人）を通る。修正役の異議は judge を再審の入力でもう一度差し込む（1 度）。
8. test-gate（final）: テスト一式と CI。緑を作業ツリーの指紋つきで認証する。
9. eyes: 独立の目 R1〜R4 と、直した後の構造の実測、守りのパスの当たり。
10. merge（seal）: 人に見せる差分を封じる（hash）。
11. 最後の関所（人）: 封じた差分の hash・R4 の問い・守りのパスの当たり・許したテストの変更・人に回した申し出を並べる。開くかは無人の方針（`final_gate`: always・when_needed・protected_only と `unattended`）で決まる。
12. merge（apply）: 封じた hash を照らしてから、外へ 1 度だけ書く（既定は差分を run の置き場に置き、人が `bin/apply` で当てる。今の works と同じ）。
13. report: いつも走る（前の段が落ちても）。結末の語・報告・次の run への持ち越し。

- どの段でも、外から止める札（止め札）を線の節が見て、後ろを飛ばして report へ進む。
- 単位がどれも軽量なら（深さの決め）、差分の審査と R1〜R4 を省く。直した後に標準へ上げ直す決めも線が持つ。
- 周の鎖（頼まれたら run を何周もつなぐ）は run の外で `bin/start --rounds` が持つ。

### 線が運ぶ物

型の正本は、出すブロックの返す節の `output_format` と線の `with:` だけ（持ち主の決め `io-in-output-format`）。下の表は何が渡るかの目録で、型の写しではない。

- 始めの記録（入口の入力の形を含む）: 線の始めの節が出す → 全部（境の口で読む）
- 直す前の結末: test-gate（base）→ fix・test-gate（final）
- 判定（単位の目録・判定の指し札・定石の行の指し札）: judge → plan・plan-review・fix・eyes
- 計画（修正案の指し札・波及の指し札・単位ごとの深さ）: plan → plan-review・fix・eyes
- 事前審査（止めか通しか・4 つの軸・人への問い）: plan-review → 線（関所と往復）・plan
- 修正（単位ごとの結末・申し出・諦めた単位・差分の指し札）と型つきの成果物 `tdd-unit`・`lane-result`: fix → test-gate・eyes・report
- 緑の認証（緑・赤の原因・作業ツリーの指紋）: test-gate（final）→ eyes・merge
- 独立の目と型つきの成果物 `eye-verdict`: eyes → merge・report
- 封じた差分（hash・守りのパスの当たり）: merge（seal）→ 最後の関所・merge（apply）
- 報告（結末の語・報告の指し札・持ち越しの指し札）: report → `bin/show`

受け渡しの決まりは `engineering.md` の E4・E5。

### 繰り返し

- 判定の受け付けが拒めば、判定役に 3 回まで出し直させる（judge の中の `loop:`）。
- 計画の往復は線の `loop_group`（plan と plan-review の 2 つの include）で 3 回まで。`loop_group` の中に include を置けるかは未決（下の U4）。置けなければ、plan-review が自分の `commands/` に案の直しの役を持つ形にする（plan ブロックは知らない）。
- 並べの枝: 単位を、判定の単位か計画の項目を共にする物で組にする。枝の数は機械が組の数から決める（持ち主の決め `parallel`。今の works の固定の 3 は持ち込まない）。YAML の節の数で上限が要る間は、その上限は Archon の制約として埋め P1・P2 に書く。最初は 1 本に 1 組を配り、入らない組は待ちの列に並べる。枝は自分の組を直し終えたら、錠の中で列から次の組を取る。申し出・実行器の止まり・回数の上限で止めた枝は列から取らない。当てる時は決めた順に親の木へ戻す。戻せなかった組と枝に入らない組だけ、順の輪が直す。今の works の commit `ab9b9f17`（2026-10-11）と同じ形。
- 修正役が 3 回拒まれた単位は、その単位を始めた時の版に戻し、理由を残して裁定に回し、ほかの単位は先へ進む。
- 差分の審査 → 手直しは 2 往復まで。

## ブロック

各ブロックのフォルダは `<名>.yaml`（工程の名は `works-factory-<名>`）・`commands/`（役の指示書の本文）・`scripts/`（`lib/` と境の口を呼ぶだけ）・`fixtures/`（Archon の筋書きの試験）を持つ。返りの型は `returns:` が名指す節の `output_format`。

### line（線）

- 目的: ブロックを並べ、関所・往復・止め札・深さ・無人の方針を持つ。
- ASF で読む物: `W/lifecycle/archon-lifecycle.yaml`（子の関所を子が持つ形・`returns: merge`）と `W/ship/archon-ship.yaml`（routes の合流と `trigger_rule: none_failed_min_one_success`、`if_skipped` で飛ばされた子を `null` で受ける `outcome`）。`W` は `.archon/workflows/sdlc`。
- 入力: 入口の入力。返り: report の返り。
- lib: `entry_shape`・`depth`・`gate_policy`・`halt`・`converge`・`stop_reasons`（止めの理由の語）・`features`（機能の切り替えの語）。
- 埋め: P3（持ち主の居ない running）・P4（include に if_skipped を通せない）。
- 持ち主: 土台の持ち主だけ（守りのパス）。

### judge（判定）

- 目的: 依頼を根本の単位にまとめる。前提の実測・目的の固定・定石（世界の解）・並行 PR とのぶつかり・素材集め・根本の診断・判定の裏取り・再審・目的の外の所見の持ち越し。`--spec` の時は仕様（要件と受け入れテスト）と仕様の関所。
- ASF で読む物: `W/triage/archon-triage.yaml`（今の木と突き合わせてから道を決める・`returns: verdict`・`outcome_field: ready`）と `W/investigate/`（根の問い）。
- 入力: 始めの記録・直す前の結末。再審の時は修正役の異議。
- 役（`commands/`）: `premises`・`purpose`・`world-classes`・`world-judge`・`material-*`（11 本）・`diagnose`・`pr-check`・`spec`。
- lib: `judge_accept`・`premises`・`purpose`・`world`（定石の行の形も持つ）・`webget`・`parallel_pr`・`class_query`・`out_of_purpose`・`cite`・`reads`。
- 埋め: 無し。

### plan（計画）

- 目的: 構造の目（単位が名指すファイルを実測し、直し方が構造を汚すか）と修正案（項目ごとの書いてよい範囲・受け入れテスト・定石と構造の行ごとに従うか外れの訳）と波及の一覧。案の直し（裁定の後の 1 度）も同じブロックを差し込む。
- ASF で読む物: `W/plan/archon-plan.yaml`（`returns: plan`・`outcome_field: ready`・`ready: false` も正しい終わり）。
- 入力: 判定・事前審査の指摘（往復の 2 回目から）。
- 役（`commands/`）: `structure-eye`・`fix-plan`。
- lib: `plan_fields`（修正案の項目の欄の照らし）・`impact`。
- 埋め: 無し。

### plan-review（事前審査）

- 目的: 書く前に案を叩く。独立設計 R2（道具なし、目的の文だけから設計）を作り、案と比べ、写し・塞がない入口・契約のずれ・後退・方針とのぶつかりを予測する。修正前の関所の 4 つの軸を決める。
- ASF で読む物: `W/review/archon-review.yaml`（並べたレンズ → `synthesize` の形・レンズの `mutates_checkout: false`・`output_type: review-lens`）。
- 入力: 判定・計画。
- 役（`commands/`）: `r2-design`・`plan-review`。
- lib: `gate_axes`・`converge`・`policy`。
- 埋め: 無し。

### fix（修正）

- 目的: 単位ごとに直す。TDD の輪（名指しのテストが failure で落ち、直して通ることを JUnit の XML で機械が見る。役が引いた失敗の文が結末に在るかを照らす）・テストの凍結・修正案の範囲の照らしと相談・書き込みの出どころの突き合わせ・当たる試験の選び・3 回で諦める・食い違いの申し出と読むだけの裁定役・並べの枝と待ちの列・後始末・差分の審査とレンズ（silent-failure-hunter）と手直し。
- 差分の審査と手直しを fix に置く訳: review-graph で同じ P3 の段（`p3.fix_delta`・`p3.delta_review`・`p3.delta_fix`）にあり、ブロックの中で輪が閉じる。ブロックの間の戻りを作らない。
- ASF で読む物: `W/implement/archon-implement.yaml`（`loop:` と `until_field: done`・`assert-changed` が `checkoutStart` と比べて本当に変わったかを見る・`outcome_field: green`）と `W/deliver/archon-deliver.yaml`（review → correct の輪）。
- 入力: 判定・計画・直す前の結末。型つきの成果物 `tdd-unit`・`lane-result` も出す。
- 役（`commands/`）: `tdd`・`fix`（修正の決まりを含む）・`ruler`・`delta-review`・`lens`・`refix`。
- lib: `red_check`・`baseline_red`・`test_freeze`・`plan_scope`・`write_provenance`・`impact`・`test_files`・`give_up`・`lanes`・`cite`・`conflict`（申し出の形）。
- 埋め: P1・P2（`workflows/.shared/lanes`）。

### test-gate（試験の関門）

- 目的: 2 つの形で差し込む。base はテストの走らせ方を見つけ、直す前の結末を控える。final はテスト一式と CI を走らせ、赤の原因（今回入れた・元から・環境）を分け、緑を作業ツリーの指紋（HEAD と差分の hash）つきで認証する。機械で走らせられない時は任せ先の役が回す。
- ASF で読む物: `W/validate/archon-validate.yaml`（`mode`・`discover`・`run`・`classify`・`result`、`outcome_field: green`）と `W/deliver/scripts/gate-green.ts`（認証）と `W/.shared/validation-evidence.ts`（指紋）。
- 入力: 形（base・final）・始めの記録。
- 役（`commands/`）: `ci`。
- lib: `baseline_red`・`test_files`・`green_cert`。
- 埋め: 無し。

### eyes（独立の目）

- 目的: 直しを作った役と別の新しい会話で、読むだけで確かめる。R1 最小性（コメントの削除候補 → 問いの台帳の監査 → 累積差分が最小か）・R2 独立設計との比較（道具は累積差分を読むだけ。前提が崩れたと言えば前提の検算）・R3 全体の整合（命名・規約・界面・文書の追従）・R4 見えていない範囲（運用・セキュリティ・データの横断の危うさと消えた能力。人への問い）。R1・R2・R3 を並べ、R4 は R1・R2 の後。直した後の構造の実測と、守りのパスの当たりも出す。
- ASF で読む物: `W/review/archon-review.yaml`（並べたレンズ・`coverage`・`synthesize` が include の頭と `loopGroupPath` で自分の分だけを数える）。
- 入力: 判定・計画・修正・緑の認証。型つきの成果物 `eye-verdict` も出す。
- 役（`commands/`）: `r1-comments`・`r1-minimality`・`r2-compare`・`r3-coherence`・`r4-scope`・`premise-check`・`structure-after`。
- lib: `protected`。
- 埋め: 無し。全部の役の節に `mutates_checkout: false`（E7）。

### report（報告）

- 目的: 結末の語（10 語）を決め、機械の報告と AI の報告を書き、段ごとの費用と時間を Archon の出来事の記録から作って載せ、文脈を持たない読み手に確かめさせる。次の run への持ち越し（次の依頼・前の失敗の行）を書く。人の関所の答えと TDD の単位の行（引用と理由）を載せる。
- ASF で読む物: `W/ship/scripts/outcome.ts`（どの道でも 1 つの返り）と `W/.shared/report.ts`（型つきの成果物の `errors` を注意として出す）。
- 入力: 全ブロックの返り（飛ばされた物は `null`）。
- 役（`commands/`）: `report`・`cold-check`。
- lib: `outcome`・`carry`。結末の 10 語は report の返す節の `output_format` の enum が正本で、`lib/outcome` は決め方だけを持つ。次の依頼と前の失敗の行の形（run をまたぐ控え）は `lib/carry` が持つ。
- 埋め: 無し。

### merge（取り込み）

- 目的: 2 つの形で差し込む。seal は人に見せる差分を封じ（hash）、守りのパスの当たりを出す。apply は封じた hash を今の差分と照らし、違えば止める。同じなら外へ 1 度だけ書き、読み戻す。既定の書き先は run の置き場の差分（人が `bin/apply` で当てる）。今の works には PR を出す口も main へ当てる口も無いので、それは置き換えの後の足し。
- ASF で読む物: `W/merge-queue/archon-merge-queue.yaml`（`path-policy`・`gate` の封印・`approval`・`refresh` → `execute`）と `W/merge-queue/scripts/merge-action.ts`（封印と読み戻し）。
- 入力: 修正・緑の認証・独立の目・始めの記録。
- lib: `seal`・`protected`。
- 埋め: 無し。

## 能力の棚卸し

今の works の能力ごとに、今の住処と新しい住処。パスは今の works は `works/` から。新しい方の `commands/<名>` は差し込むブロックの役の指示書、`lib/<名>` は助け手のモジュール（`lib/<名>.py`）。

### 線と入口

- 入口の入力の形（差分の根・差分・依頼の行・PR。空なら止める）: `blk-entry`・`.shared/core/entryshape.py`・`startrec.py` → line・`lib/entry_shape`
- 単位ごとの深さと上げ直し: `darkfactory/lib/depth.py` → line・`lib/depth`
- 機能の切り替え: `.shared/core/entry.py` の `FEATURES` → line・`lib/features`
- 止め札: `.shared/core/halt.py` → line・`lib/halt`。札を置く口は `bin/`
- 人の関所と無人の方針: `.shared/core/gatepolicy.py` → line・`lib/gate_policy`
- 止めの理由の語: `.shared/core/stopby.py` → `lib/stop_reasons`
- 周の鎖: `.shared/core/chain.py`・`dev/use.sh` → `bin/start --rounds`・`lib/chain`
- 固定材料から始める・版の控え: `.shared/core/fixture.py`・`versions.py` → line（始め）
- 部品の宣言と書き込みの照らし（manifest）: `.shared/core/scopes.py` → manifest は落とす。入出力の宣言は YAML の `with:`・`returns:` と型が持つ（E4・E5）。宣言の外の書き込みは、読むだけの節は `mutates_checkout: false`（E7。Archon が落とす）、書く役は書き込みの出どころの突き合わせ（fix）で落とす。読み手の無い返りの欄は層の試験で赤（持ち主の決め `declared-io`）
- 境の節（`h-*`）: `darkfactory/lib/line_edge.py` → line の `when:` と小さな script の節
- 工程の地図: `.shared/core/graphmap.py` → 落とす。Archon の YAML がそのまま地図
- AI の起こし方の包み（模型・effort・道具・隔離・返答の契約・system prompt の塊）: `.shared/core/adapter.py` ほか → 落とす。Archon の役の節の `model:`・`effort:`・`allowed_tools:`・`output_format:` で書く。包みが取っていた読んだ証拠と書き込みの記録をどこで取るかは未決（U6）
- 返答の足し欄: `.shared/core/marks.py` → 落とす。返りの欄は役の節の `output_format` に直に書く
- graphloops の写し（engine・rules・検証器）: `.shared/core/graphloops/` → 写さない。線は Archon が回し、検証器の中身は `lib/` に移す

### judge

- 並行 PR とのぶつかり: `blk-pr`・`prcheck.py`・`forge.py`・`ghreads.py` → `lib/parallel_pr`・`commands/pr-check`
- 前提の実測: `blk-premises`・`premises.py` → `commands/premises`・`lib/premises`
- 目的の固定と解き方の分け: `blk-purpose`・`purpose.py` → `commands/purpose`・`lib/purpose`
- 定石（世界の解）と web の取得: `blk-world`・`worldmark.py`・`webget.py` → `commands/world-classes`・`commands/world-judge`・`lib/world`・`lib/webget`
- 素材集め 11 本: `blk-material` → `commands/material-*`
- 仕様の段: `blk-spec` → judge（`--spec` の時）・`commands/spec`
- 根本の診断と受け付け: `blk-judge`・`.shared/core/accept.py` → `commands/diagnose`・`lib/judge_accept`
- 判定の裏取り: `blk-judge/lib/judgeverify.py` → judge
- 欠陥の探し方の試しと数え直し: `querytest.py`・`recount.py` → `lib/class_query`
- 目的の外の所見: `outpurpose.py` → `lib/out_of_purpose`
- 再審: `blk-rejudge`・`rejudge.py` → judge（再審の入力）
- 名指しと引用の照らし: `.shared/core/cite.py` → `lib/cite`
- 読んだ証拠: `reads.py`・`record-read.py` → `lib/reads`

### plan・plan-review

- 構造の目: `blk-structure`・`structmark.py`・`concepthome.py` → plan・`commands/structure-eye`
- 修正案: `blk-plan`・`planmarks.py` → plan・`commands/fix-plan`・`lib/plan_fields`
- 波及の一覧: `blk-plan/lib/ripple.py`・`impact.py` → plan・`lib/impact`
- 案の直し: `replan.py` → plan（裁定の後の 1 度）
- 独立設計 R2: `blk-plan` の `r2-design-loop`・`design.py` → plan-review・`commands/r2-design`
- 事前審査（項目ごとの木）: `blk-plan` の `plan-review-loop`・`holeties.py` → plan-review・`commands/plan-review`
- 壁打ちの往復: `converge.py` → line の往復・`lib/converge`
- 修正前の関所の 4 つの軸: `gatemarks.py` → `lib/gate_axes`
- 人の方針の文: `policy.py` → `lib/policy`

### fix

- TDD の輪と赤の判定: `blk-fix/lib/tddloop.py` → `lib/red_check`・`commands/tdd`
- 元から赤のテストの区別: `tddloop.py` → `lib/baseline_red`
- テストの凍結と許しの 1 本道: `conflict.py`・`fixgates.py` → `lib/test_freeze`
- 範囲の照らしと相談: `planrange.py`・`planscope.py`・`consult.py` → `lib/plan_scope`
- 書き込みの出どころ: `writes.py`・`record-write.py` → `lib/write_provenance`
- 当たる試験の選び: `impact.py` → `lib/impact`
- テストのファイルの見分け: `impact.py` の `is_test_file` → `lib/test_files`
- 3 回で諦める: `fixlanes.GIVE_UP_AFTER`・`parking.py` → `lib/give_up`
- 食い違いの申し出と裁定: `conflict.py`・`ruling.py` → `commands/ruler`・`lib/conflict`
- 並べの枝と待ちの列: `lanekit.py`・`fixlanes.py`・`tddlanes.py`・`unitlanes.py`・`unittrees.py` → `lib/lanes`（組の作りと取り）・埋め `workflows/.shared/lanes`（作業ツリーと固定の枝の節）
- 後始末: `leftovers.py` → fix
- 修正の決まりと借りた superpowers の節: `seat.py`・`spseam.py`・`rulebook.py`・`blk-fix/rules/*.md` → `commands/fix-rules`
- 差分の審査・レンズ・手直し: `blk-delta`・`deltamarks.py`・`blk-lens`・`lens.py`・`blk-refix`・`refix.py` → fix・`commands/delta-review`・`commands/lens`

### test-gate・eyes・report・merge

- CI とテスト一式・任せ先の役: `blk-tests`・`blk-ci`・`ci_role.py` → test-gate・`commands/ci`
- 緑の認証（新）: 無し → test-gate・`lib/green_cert`（ASF の型 A3）
- 独立の目 R1〜R4 と前提の検算: `blk-eyes` → eyes・`commands/r1-*`・`r2-compare`・`r3-coherence`・`r4-scope`・`premise-check`
- 直した後の構造の実測: `blk-structure`（`measuring-after`）→ eyes
- 守りのパス: `protect.py` → `lib/protected`（eyes と merge）
- 結末の 10 語: `report.py` の `OUTCOMES` → `lib/outcome`（語は report の `output_format` の enum）
- 報告と初見の確かめ: `darkfactory` の `report` 節・`blk-report` → report・`commands/report`・`commands/cold-check`
- 持ち越し: `carry.py` → `lib/carry`
- 差分の封印と外への書き込み（新）: 今は人が `dev/use.sh apply` で当てる → merge・`lib/seal`・`bin/apply`

### 受け入れの一覧（review-graph と同じ能力）

持ち主の決め（`docs/owner-decisions.md` の `superset`）: works は review-graph の能力を 1 つも落とさない。works-factory も同じ。下の行は全部、置き換えの前に試験か筋書き（fixture）の名で証を書く。今の works は graph の全部の節を表 `darkfactory/nodes.json` で `by`（役・機械・Archon・無し）に当て、`absent` は理由を持つ。同じ表をこのリポジトリでも持つ（段 3）。

- [ ] `p0.base` 差分の根を決める。未追跡は載せる
- [ ] `p0.local_checks` CI を手元で走らせる。走らなければ人待ち（緑を仮定しない）
- [ ] `p0.premises` 目的と制約の数値を実測する
- [ ] `p0.purpose` 出典の優先順で目的を決め、最初の修正の前に固定する
- [ ] `p0.purpose_review` 目的を都合よく狭めていないか審査する
- [ ] `p0.parallel_pr` 並行 PR との交差を申し送る（今は報告に載せる形に下げている）
- [ ] `p0.prior_decisions` 決着済みの論点の一覧（禁: 局所の所見・ほかの採点の素材）
- [ ] `p1.worktree_before`・`p1.worktree_after` 作業ツリーの前後を機械が突き合わせる
- [ ] `p1.local_review` 所見を集めるだけで採点しない
- [ ] `p1.consistency_bypass` 横断の整合と標準の仕組みの迂回（禁: 局所の所見・固有規約・決着済みの論点）
- [ ] `p1.hygiene` 用途を知らない目で衛生違反（禁: 元の目的・機能名・説明・近傍のコード）
- [ ] `p1.external_standards` 問題の類を web の一次情報で裏取り（禁: 局所の所見）
- [ ] `p1.procedure_trace` 動かして確かめる。確かめられない所は未実測の仮説（禁: 局所の所見）
- [ ] `p1.gate_efficacy` 腕ごとに退行を入れて赤、壊さない写しで緑（対照）
- [ ] `p1.test_double_fidelity` テストの代役を実物の値で照らす
- [ ] `p1.main_path_observation` 主経路を 1 回動かして観測する
- [ ] `p1.provenance` 「正本は X」の X が差分の内側に無いか
- [ ] `p2.diagnose` 反証・出自・上へ 3 段・処方の木（書き手は覆せない。禁: 履歴・前の周の台帳と判定）
- [ ] `p2.history` 台帳の再燃・問いの再審・膨張（今は 1 周の run で absent。周の鎖で受けるかを段 3 で決める）
- [ ] `p2.fix_plan` 全部の単位を案に入れ、生まれる物・消す物・狭める能力を先に書く
- [ ] `p2.plan_review` 写し・塞がない入口・契約のずれ・後退・方針とのぶつかりを予測する
- [ ] `p2.human_gate` 狭め・後退・方針の穴があれば直す前に人に聞く
- [ ] `p2.rejudge` 判定役が新しい事実を自分で確かめ、採るか退けるか
- [ ] `p3.lane_merge` 枝の差分を重ね、当たらない物は次に見せる
- [ ] `p3.fix` 単位ごとに直す。不変条件を共にする箇所を全部挙げ、1 か所ずつ赤 → 緑。仕組みを新しく作ることになったら止める
- [ ] `p3.fix_delta`・`p3.delta_review`・`p3.delta_owed`・`p3.delta_fix` 修正だけの差分の審査と手直し
- [ ] `p3.fix_delta2`・`p3.delta_review2`・`p3.delta_owed2`・`p3.delta_fix2` 2 回目
- [ ] `p3.gates_cut` 周の版を固める
- [ ] `p3.delta_gates`・`p4.final_gates` 変異の検算（今の works は absent と宣言して落としている。works-factory で戻すかを段 3 で持ち主に聞く）
- [ ] `p4.ci` CI を走らせ直す。赤なら戻る（今は次の run の下書き）
- [ ] `p4.scalars`・`p4.assemble` 規模の数値と R1・R2 の再発火を機械が数える
- [ ] `p4.record`・`converge` 周の記録と検証器。阻害が 2 周続けて無く CI が緑の時だけ収束、上限 5 周
- [ ] `r1.comment_candidates`・`r1.minimality` R1
- [ ] `r2.design`（禁: 実装・リポジトリ・履歴・累積差分・決着済みの論点）・`r2.compare`（禁: 調査の経緯・判定の一覧）R2
- [ ] `r3.coherence` R3
- [ ] `r4.hidden_scope`・`r4.human_gate` R4
- [ ] `stop.premise_check` 前提の検算
- [ ] `report.human_items`・`report.cold_check`（禁: 周の経緯・記録・差分）・`report`
- [ ] `spec.write`・`spec.review`・`spec.revise`・`spec.approve`・`spec.freeze`・`spec.check` 受け入れテストを承認の時点で固め、後で hash を照らす

今の works の強みの 12（works `docs/keep-essence.md`）も同じ扱い: 赤緑の機械の判定・元から赤の区別・テストの凍結・3 回で諦める・書き込みの出どころ・当たる試験の選び・欠陥の探し方の数え直し・食い違いの申し出・独立設計・守りのファイルで最後の関所・単位ごとの記録が報告に届く・世界の解。

## Archon の分かっていること

2026-10-11 に v0.11.1 の binary とソースを読み、手元で確かめた事実。

- `include:` は読み込みの時に展開され、子の節の id は `<include の id>__<子の id>` になる。
- `returns:` は 1 つの節の出力を `$<include の id>.output` として見せる。
- 型つきの成果物は、節の id と繰り返しの道（`loopGroupPath`）で鍵が付き、`$TYPED_ARTIFACTS_FILE` の一覧（`{runId, artifactsByType, errors}`）で引く。
- `loop:` の出力は最後の回の出力。
- `if_skipped` は include の入力を通して運べない（埋め P4）。
- 指し札は同じ run の中だけ。パスは相対で、在って空でない普通のファイルだけ。
- `script:` の節の `output_format` は標準出力の約束で、Archon が照らす（v0.11.1 の文書 `guides/script-nodes.md`「JSON Schema the node's stdout must satisfy」）。だからブロックの返りの型を自前で照らす口は要らない。
- `fan_out:` の子が承認の関所で止まると、その子は取り消される。関所は fan_out の前か後に置く。
- 持ち主の居ない `running` の run は `resume` できない（埋め P3）。
- v0.11.1 は `$ARCHON_HOME/workflows` に置いた最新の ASF の束を読む。40 本が並び、同じ名の同梱の工程を上書きする。`archon-merge-queue` は script のパスの警告を 2 つ出した。ASF の工程を走らせたことはまだ無い。
- 作りの規則は v0.11.1 の `.archon/workflow-language-constitution.md`（「YAML coordinates. Code computes. Agents judge.」）。

### 未決（歩く骨組みで決める）

- U1 `resume` の後の run の id は同じか。持ち越しと指し札（同じ run の中だけ）に効く。
- U2 型つきの成果物と `returns:` が、include ごとに分かれて見えるか（同じブロックを 2 度差し込む test-gate・merge・plan で要る）。
- U3 `archon workflow test` の筋書き（fixture）が v0.11.1 で使えるか。v0.11.1 の文書 `reference/cli.md` は `workflow test` の fixture を名指すが、手元の binary では走らせていない。
- U4 `loop_group` の中に `include:` の節を置けるか（計画の往復）。
- U5 ブロックの script が、置いた `lib/` をどのパスで見つけるか（E1 で YAML を変えないので、置き場の決めは `bin/` と境の口が持つ）。
- U6 今の works の包みが取っていた読んだ証拠と書き込みの記録を、Archon の役の節で取れるか（Archon の出来事の記録か、節の hooks か）。取れなければ埋めの行にする。
- U7 ASF の lifecycle を段 2 で使う時、必須の入力 `scenario`（動かして確かめる筋書き）に何を渡すか。
- U8 `fan_out:` と `isolation: worktree` の子の枝が、親の run の今の commit から切られるか。切られるなら、枝の数を run の時に決める形（`fan_out:`）に寄せ、埋め P1・P2 を小さくできる。

U1〜U3 は持ち主の挙げた物、U4〜U8 はこの文書を書く中で出た物。

## 作りの順

### 段 0 土台（土台の持ち主 1 人）

`pack.json`・`bin/`・境 `workflows/.shared/`・線の骨組み（ブロックの返す節の `output_format` を含む）・層の試験。手順は `docs/plans/2026-10-11-foundation.md`。

### 段 1 歩く骨組み

全部のブロックを中身の薄い形（型に合う返りを返すだけ）で線に並べ、小さな対象のリポジトリ（`tests/e2e/` の種）に 1 つの依頼を通しで回す。人の関所は `bin/answer` で答える。U1〜U7 を決め、結果を この文書と `docs/archon-polyfills.md` に書く。

### 段 2 ブロックごとの issue を並べて回す

- 1 つのフォルダに 1 つの issue。中身は「グラフのブロック 1 つ（YAML・役の指示書・script）と、それが呼ぶ `lib/` のモジュールを移す。筋書き（fixture）と `lib/` の試験を先に書く」。
- 回すのは最新の ASF の lifecycle（`archon-lifecycle`。1 run で 1 issue）。並べは issue ごとに run を起こして作る（lifecycle は自分では並べない）。
- 共有のファイル（`workflows/.shared/`・`workflows/line/`・`engineering.md`・`MISSION.md`・`pack.json`）は土台の持ち主だけが変える。lifecycle の入力 `protected_paths` にこれらを渡し、ASF の merge が人の手に残す（ASF の型 A7）。issue の中で共有のファイルの変更が要ると分かったら、止めて土台の持ち主に issue で頼む。

issue の一覧（受け入れの条件はどれも共通の 5 つ + 個別）:

共通:
1. 筋書き（`workflows/<名>/fixtures/`）と `lib/` の試験（`lib/tests/`）が先に赤で入り、後で緑。
2. 返す節の `output_format` を段 0 の骨組みの欄から狭めずに中身を入れ、線の `with:` が読む欄が全部在る（`tests/layers/test_block_returns.py`）。欄を足す・変えるのは線との約束を変えることなので、土台の持ち主に issue で頼む。
3. 層の試験（`tests/layers/`）と `archon validate workflows` が緑。
4. 採った ASF の型を `docs/asf-notes.md` に、使った埋めを `docs/archon-polyfills.md` に書いた。
5. 「能力の棚卸し」と「受け入れの一覧」のこのブロックの行に、証の試験か筋書きの名を書いた。

個別:

- `judge`: 前提・目的・定石・素材 11 本・診断・裏取り・再審・仕様の段が動く。受け付けが拒めば 3 回まで出し直す。定石の抜き書きが出どころに在ることを機械が照らす。目的の外の所見が持ち越しの行になる。
- `plan`: 構造の目と修正案と波及の一覧。項目ごとに書いてよい範囲・受け入れテスト・定石と構造の行への従うか外れの訳が無ければ受け付けが拒む。案の直しの入力で 2 度目を差し込める。
- `plan-review`: R2 の独立設計は道具なしで目的の文だけを受ける（禁じた入力が届かないことを試験で縛る）。4 つの軸と人への問いを返す。往復の止め（3 回・同じ止めが 2 度）が働く。
- `fix`: 赤緑の機械の判定・元から赤の区別・凍結・範囲の照らしと相談・書き込みの出どころ・3 回で諦める・申し出と裁定・差分の審査と手直し 2 往復。並べの枝が待ちの列から次の組を取り、止めた枝は取らない（今の works の `tests/test_fix_lanes.py`・`test_tdd_lanes.py` と同じ筋書きを通す）。
- `test-gate`: base と final の 2 つの形。赤の原因を 3 つに分け、今回入れた赤と原因の無い赤を拒む。緑の認証に作業ツリーの指紋が入り、木が変われば認証が使えない。
- `eyes`: R1〜R4 と前提の検算と直した後の構造の実測。全部の役が `mutates_checkout: false`。R2 の禁じた入力が届かない。R4 の問いと守りのパスの当たりが返りに載る。型つきの成果物を自分の include の分だけ数える。
- `report`: 結末の 10 語・機械の報告・AI の報告・初見の確かめ・持ち越し。前の段が落ちても飛ばされても走り、`errors` を注意として載せる。
- `merge`: seal と apply の 2 つの形。封じた hash と今の差分が違えば apply は止まる。外への書き込みは 1 つの script の節で、書いた後に読み戻す。守りのパスの当たりは人に回す。

### 段 3 合わせと同じ能力の確かめ

1. 線に全部の本物のブロックを並べ、`tests/e2e/` を通す。
2. 受け入れの一覧の全部の行に証を書く。graph の節の表（`by` と `absent` の理由）をこのリポジトリにも置き、試験で縛る。
3. 欠陥を仕込んだ較正（`tests/calibration/`）: 仕込んだ欠陥を、今の works と works-factory の両方が見つけるか比べる。
4. 同じ依頼を今の works と works-factory に回し、結末・単位・人への問い・費用を並べて比べる。違いは 1 行ずつ理由を書く。
5. 変異の検算（`p3.delta_gates`・`p4.final_gates`）と周の記録（`p2.history`）を戻すかを持ち主に聞く。

### 段 4 切り替え

1. claude-plugins の `works/` の `/works` を、works-factory の `bin/` を呼ぶ薄いスキルに替える。
2. 今の works の pack を退ける（消す前に、段 3 の比べの記録をこのリポジトリに残す）。
