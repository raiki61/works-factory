# 観点（`perspectives/`）

工場の block の AI への指示に埋まっている持ち主の観点（何を見るか・何を良しとするか・よくある失敗の型）を、工場の仕組みから切り離した文として残す置き場。将来は Claude Code のスキルとして工場の外でも使い回す前提で、1 観点を 1 フォルダにし、英語の `SKILL.md`（Agent Skills の形。frontmatter は `name`・`description`）と、同じ中身の日本語の `SKILL.ja.md` を置く。持ち主の決め `perspectives-apart`（`docs/owner-decisions.md`）。

- 工場（起動の殻・pack・共通の lib・見る道具）は、ここを読まない。ここを直しても工場の振る舞いは変わらない。ただし層の柵の試験（古い語の検査や見る道具への名指しの検査など）はここも照らすので、ここの字もその決まりに沿って書く。
- 工場の指示が変わっても、ここは自動では追いつかない。写した時の版を下の表に書き、写し直す時はその版からの差分を読む。
- 写す時に落とす物: 差し込み口（`{name}`）・port の名・JSON の出力の形の指示・ノードの順と次の段の名指し・機械の受け付けの検査の話。観点に流れ（次に何を呼べ）を書かない。
- 対象の言語やテストの実行器を名指さない（根の `AGENTS.md` の E13 の考え。ここは機械の照らしの外でも守る）。

## 一覧

写した時の版は、どれも `7bbe3e43a25818dbb55dc23bf6a05bace2e683fc`（2026-11-16 の main）。

### `check-against-practice` 依頼を、実務家の解き方と比べる

- 元の block: world（block の手本）
- 元の指示: `workflows/world/prompts/world-classes.md`（言い直しの役）・`workflows/world/prompts/parts/world-judge.md`（Web の役。`world-judge.md`・`world-judge-offline.md` はこれを差し込むだけ）・共通の断片 `workflows/.shared/prompts/query-rule.md`（外への問い合わせの決まり）
- 落とした物: 2 つの役への分け方（言い直しの役は道具を持たず、対象を見ない）は「対象を見る前に言い直す」の 1 行にした。機械が抜き書きを取り直して照らす話・字数の下限・判定の enum は落とした。

### `silent-failure-lens` 変更に、黙ったまま終わる失敗が無いかを見る

- 元の block: lens
- 元の指示: `workflows/lens/prompts/parts/lens.md`（`silent-failure-hunter.md` はこれを差し込むだけ）
- 観点そのものは、利用者が入れた `pr-review-toolkit` のプラグインの `silent-failure-hunter` の agent の定義（工場は run の時にその本文を指示に貼る）。第三者の物なので写していない。ここに在るのは、それを変更に当てる時の持ち主の構え（新しい目・読むだけ・差分は起点で境ではない・指摘は変わったファイルの中だけ・場所と写しと「誰が気づけないか」）と、定義が無い時の仮置きの最低限（仮置きと本文に書いた）。

### `plan-pre-review` 変更を書く前に、計画を事前に審査する

- 元の block: plan-review
- 元の指示: `workflows/plan-review/prompts/` の下の `review.md`・`review-text.md`・`review-theme.md`（審査の 3 つの場面）と `parts/` の `role.md`・`other-eye.md`・`read-version.md`・`head.md`・`checks.md`・`plan-checks.md`・`theme-checks.md`・`design-ask.md`・`means-ask.md`・`means-drift.md`・`prescription-ask.md`・`rereview-ask.md`・`origin-ask.md`・`diff-ask.md`・`item-brief.md`・`synergy-brief.md`、`parts/design-absent.md`（独立の設計が無い時・目的の問いが成り立たないと返った時）、共通の断片 `workflows/.shared/prompts/` の `role-judge.md`（判定の役の構え）・`query-rule.md`（外への問い合わせの決まり。`role-judge.md` と `item-brief.md` が差し込む）・`ask-cases.md`（人に聞く 3 つの場合）・`deviation-grounds.md`（一般の構造から離れる訳）・`recorded-policy.md`（記録された決めはどこから来るか。コードの注は決めでない）・`plain-ask.md`（人に問う文の書き方）
- 落とした物: 子のエージェントへの分け方と束ね方・答えのファイルの書き方・波及の一覧と独立設計との対応表の行の形・決まった見出しの字・機械の受け付けの検査・承認ノードの仕組み。`plain-ask.md` は「勧めの答えを 1 つ、そのまま写せる形で」の 1 行に縮めた（初めて読む人向けに、表題・今の状態・案・費用・勧めの順で書き、1 つの論点を 1 項目にする形と、run の中を指す字を書かない決まりは落とした）。出し直しの指示 `review-fix.md`・`review-tree-fix.md`・`review-theme-fix.md`、束ね役の `review-tree.md`（子のエージェントの起こし方と束ね方だけ）、機械が探した概念の住処の地図を貼る `workflows/.shared/prompts/concept-map.md`（住処を探す観点は本文の「考えの住処」に在る）と、`policy-example.md`・`lib-docs.md`・`absorb-ask.md`・`stuck-quote.md` は工場のつなぎだけなので写していない。
