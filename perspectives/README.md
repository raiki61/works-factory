# 観点（`perspectives/`）

工場の block の AI への指示に埋まっている持ち主の観点（何を見るか・何を良しとするか・よくある失敗の型）を、工場の仕組みから切り離した文として残す置き場。将来は Claude Code のスキルとして工場の外でも使い回す前提で、1 観点を 1 フォルダにし、英語の `SKILL.md`（Agent Skills の形。frontmatter は `name`・`description`）と、同じ中身の日本語の `SKILL.ja.md` を置く。持ち主の決め `perspectives-apart`（`docs/owner-decisions.md`）。

- 工場（起動の殻・pack・共通の lib・見る道具）は、ここを読まない。ここを直しても工場の振る舞いは変わらない。ただし層の柵の試験（古い語の検査や見る道具への名指しの検査など）はここも照らすので、ここの字もその決まりに沿って書く。
- 工場の指示が変わっても、ここは自動では追いつかない。写した時の版を下の表に書き、写し直す時はその版からの差分を読む。
- 写す時に落とす物: 差し込み口（`{name}`）・port の名・JSON の出力の形の指示・ノードの順と次の段の名指し・機械の受け付けの検査の話。観点に流れ（次に何を呼べ）を書かない。
- 対象の言語やテストの実行器を名指さない（根の `AGENTS.md` の E13 の考え。ここは機械の照らしの外でも守る）。
- 1 つの指示に一緒に使わない観点が複数あれば分け、同じ観点を持つ指示が複数あれば 1 つにまとめる。共通の断片（`workflows/.shared/prompts/`）の観点も、それぞれ独立の観点にする。
- 観点どうしは名前で指さない。どれも単独で完結し、最後に「一緒に使うと良いもの」を一般の言葉で 1 行だけ添えてよい（命令の形にしない）。組み合わせは使う側の段取りが決める。下の一覧は、どの元の指示をどの観点に写したかを名で書く。

## 一覧

写した時の版は、どれも `7bbe3e43a25818dbb55dc23bf6a05bace2e683fc`（2026-11-16 の main。工場の物はその後も変わっていない）。

## 試しの 3 つ

### `check-against-practice` 依頼を、実務家の解き方と比べる

- 元の block: world（block の手本）
- 元の指示: `workflows/world/prompts/world-classes.md`（言い直しの役）・`workflows/world/prompts/parts/world-judge.md`（Web の役。`world-judge.md`・`world-judge-offline.md` はこれを差し込むだけ）・共通の断片 `workflows/.shared/prompts/query-rule.md`（別の観点 `outside-query-hygiene` として写した）
- 落とした物: 2 つの役への分け方（言い直しの役は道具を持たず、対象を見ない）は「対象を見る前に言い直す」の 1 行にした。機械が抜き書きを取り直して照らす話・字数の下限・判定の enum は落とした。外への問い合わせの決まりは別の観点にしたので本文から外し、落とし穴の「外への問い合わせに対象の名前を入れない」の 1 行と、定石を探す所の「一次情報を二次情報より先にする」の 1 行だけを残した（どちらも無いとこの観点が危ないか成り立たない）。共通の断片 `workflows/.shared/prompts/rejected.md`（3 本とも先頭で差し込む）は機械の受け付けの検査が断った時の出し直しの指示なので写していない。

### `silent-failure-lens` 変更に、黙ったまま終わる失敗が無いかを見る

- 元の block: lens
- 元の指示: `workflows/lens/prompts/parts/lens.md`（`silent-failure-hunter.md` はこれを差し込むだけ）
- 観点そのものは、利用者が入れた `pr-review-toolkit` のプラグインの `silent-failure-hunter` の agent の定義（工場は run の時にその本文を指示に貼る）。第三者の物なので写していない。ここに在るのは、それを変更に当てる時の持ち主の構え（新しい目・読むだけ・差分は起点で境ではない・指摘は変わったファイルの中だけ・場所と写しと「誰が気づけないか」）と、定義が無い時の仮置きの最低限（仮置きと本文に書いた）。

### `plan-pre-review` 変更を書く前に、計画を事前に審査する

- 元の block: plan-review
- 元の指示: `workflows/plan-review/prompts/` の下の `review.md`・`review-text.md`・`review-theme.md`（審査の 3 つの場面。`review.md` の「Review of a replan」の節を含む）と `parts/` の `role.md`・`other-eye.md`・`read-version.md`・`head.md`・`checks.md`・`plan-checks.md`・`theme-checks.md`・`design-ask.md`・`design-absent.md`（独立の設計が「目的の問いが成り立たない」と返した時と、無い時）・`means-ask.md`・`means-drift.md`・`prescription-ask.md`・`rereview-ask.md`（2 回目からの審査: 勧めを止めるへ上げない・前の回の中心の止める穴が残れば直しへ進まない）・`origin-ask.md`・`diff-ask.md`・`item-brief.md`・`synergy-brief.md`。共通の断片 `workflows/.shared/prompts/` の `role-judge.md`（別の観点 `judge-stance` として写した）・`query-rule.md`（`role-judge.md` と `item-brief.md` が差し込む。別の観点 `outside-query-hygiene` として写した）・`ask-cases.md`（別の観点 `when-to-ask-a-person` として写した）・`deviation-grounds.md`（別の観点 `ground-every-departure` として写した）・`recorded-policy.md` と `policy.md`（別の観点 `what-counts-as-policy` として写した）・`concept-map.md`（別の観点 `change-coherence-review` に写した。この観点の「考えの住処」は `head.md` の自分の文から写した）・`plain-ask.md`（別の観点 `write-a-decision-ask` として写した）
- 落とした物: 子のエージェントへの分け方と束ね方・答えのファイルの書き方・波及の一覧と独立設計との対応表の行の形・決まった見出しの字・機械の受け付けの検査・承認ノードの仕組み。共通の断片から写していた判定の役の構え（崩しに行く・自分の元だけ）・人に聞く 3 つの場合と何があっても人に回す物・一般の構造から離れる訳の 3 つは、それぞれ別の観点にしたので本文から外し、最後の「一緒に使うと良いもの」の 1 行に一般の言葉で書いた（この block 自身の文、`head.md`・`checks.md` の「人に回す前に世の中の解を調べる」「決めの項目を別に挙げる」と、`review.md` の「計画が書いた離れ方の訳を確かめる」は本文に残した）。試しの版（#1045）から引き継いだ物: 出し直しの計画の審査（裁きが指す事を直したかだけを見る・前の形が持っていた穴を挙げ直さない）・独立の設計が「目的の問いが成り立たない」と返した時（計画の審査ではそれを穴にしない。設計の案の審査では、案がその訳の否む物に寄っていれば穴）・2 回目からの審査の「勧めを止めるへ上げない」「前の回の中心の止める穴が 1 つでも残れば直しへ進まない」。この PR で足した物: 2 回目からの審査の「同じ穴に別の名を付けない」「試験 1 本で守れる止める穴は周辺へ下げてよい」と、決めの項目を勧め（計画の欠陥ではない）として挙げること・コードの注と docstring は決めでなく契約のずれとして挙げること（`head.md`）。
- 写さなかった物（この block）: `review-tree.md`（子のエージェントを立てて束ねる役の指示で、審査はしない。束ね方の仕組みだけ）・`review-fix.md`・`review-tree-fix.md`・`review-theme-fix.md`（機械の受け付けの検査が断った時に、断られた所だけを直して返す指示。共通の断片 `resubmit.md` と `query-rule.md`・`plain-ask.md` を差し込むだけで、審査の観点を持たない）・`parts/policy-example.md`・`parts/lib-docs.md`（共通の断片 `lib-docs.md` を差し込むだけ）・`parts/absorb-ask.md`・`parts/stuck-quote.md`（工場のつなぎだけ）・共通の断片 `workflows/.shared/prompts/rejected.md`・`resubmit.md`（出し直しの仕組み）・`lib-docs.md`（取り寄せた文書の置き場）。

## diagnose・verify

### `root-cause-triage` 修正の依頼を根の単位に仕分ける

- 元の block: diagnose
- 元の指示: `workflows/diagnose/prompts/diagnose.md`（判定の役）。差し込む共通の断片は、`workflows/.shared/prompts/role-judge.md`（判定の役の構え）・`ask-cases.md`（人に聞く 3 つの場合）・`recorded-policy.md`（記録された決め）・`policy.md`（人の方針）・`prior-failures.md`（前の run で通らなかった物）・`unknown-asks.md`（依頼の行ごとの分からない所）・`plain-ask.md`（人に聞く文の書き方）・`query-rule.md`（外への問い合わせの決まり。`role-judge.md` が差し込む）で、どれも別の観点として写した（ここには写していない。`diagnose.md` 自身が書く「人に聞く 3 つの場合」「コメントは決めではない」「前の断りは穴でない・独立の目の作り直しは穴」だけは本文に残した）
- 落とした物: 材料のファイルの鍵の名と、その読み方・出力の JSON の欄の名と形・受け付けの検査（作業ツリーの照合・字数の下限・検索を `git grep` で回す話・先例の出典の印の形・答えの結び `answer_ties` の 4 つの形）・問いの台帳の状態（held・decided・resolved・escalate）と R1〜R4 を出どころにする種類・勧めの印 `推し:`・出力の言語の指定・Bash を持たない役への読み替え。数える検索は、欄でなく考え（版に結ばない・欠陥か母集団か・例で試す）として残した

### `objection-rejudge` 判定への異議を判定し直す

- 元の block: diagnose
- 元の指示: `workflows/diagnose/prompts/rejudge.md`（判定し直しの役）。差し込む共通の断片 `workflows/.shared/prompts/role-judge.md`・`policy.md`・`query-rule.md`（別の観点として写した。方針と照らす 1 行だけ本文に残した）
- 落とした物: 読むファイルの一覧と差し込み口・答えの欄の名と判定の語（`採る`・`退ける`・`一部採る`）は「採る・退ける・一部採る」の考えだけにした・字数の下限・機械が空の事実を断る話・出力の言語の指定

### `triage-cut-check` 判定の役の、根の単位への切り方を確かめる

- 元の block: verify
- 元の指示: `workflows/verify/prompts/judge-verify.md` の子のエージェントの部分（単位ごとの確かめと、単位どうしの確かめ）。差し込む共通の断片 `workflows/.shared/prompts/query-rule.md`（別の観点として写した）
- 落とした物: 束ね役（子のエージェントを一度に立てて答えを集める仕組み）・答えのファイルの書き方と最後の 1 行の形・JSON Schema・判定の語の差し込み口（根・根でない・分からない、同じ・離れている、は考えとして残した）・出力の言語の指定

## fix

### `rule-on-fix-conflict` 曲げないと緑にならない直しを、読むだけの目で裁く

- 元の block: fix
- 元の指示: `workflows/fix/prompts/ruler.md`（裁きの役）・`workflows/fix/prompts/parts/ruling-promise.md`（裁きが次の回の直し手を何に縛るか）・`workflows/fix/prompts/parts/ruling-previous-reply.md`（裁きの後の回は答えを丸ごと出し直し、ほかの単位の直しを残す）・共通の断片 `workflows/.shared/prompts/plain-ask.md`（人に向けて書く形。別の観点 `write-a-decision-ask` として写した）・`workflows/.shared/prompts/query-rule.md`（外への問い合わせの決まり。別の観点 `outside-query-hygiene` として写した）・`workflows/.shared/prompts/rejected.md`（差し戻しの時は前の回の点も含め全部直して丸ごと出し直す。機械の受け付けの検査への出し直しの仕組みなので断片としては写さず、裁きの後の回の出し直しは `ruling-previous-reply.md` から本文に写した）
- 落とした物: 裁きの enum と JSON の形・`limits` と `grounds` の書き方・3 回の出し直しで人に渡る機械の受け付けの検査・宣言の記録や判定のファイルの欄の名・裁き手が読むファイルの置き場。「欠陥を数える照らし」は判定の `class_query` を道具に依らない言葉にした物。`ruling-promise.md` の決まった見出しの字（「範囲」「裁定」など）は落とした。

### `merge-parallel-fixes` 並べて作った直しを、先に合わせた直しと両立させる

- 元の block: fix
- 元の指示: `workflows/fix/prompts/parts/clash.md`（合わせ手と、裁きの後の合わせ手。`clash-fix.md`・`clash-ruled.md` はこれを差し込むだけ）・共通の断片 `workflows/.shared/prompts/sandbox-shell.md`（殻の中でのコマンドの書き方。工場の囲いの決まりなので写さない）・`workflows/.shared/prompts/rejected.md`（差し戻しの出し直しの仕組みなので写していない）
- 落とした物: 素材の JSON の欄の一覧・印の長さと 4 つの頭の機械の照らし・答えの JSON の形・3 回の差し戻しで裁き手へ渡る流れ。食い違いの印の側の名（「今の作業ツリー」「当てる差分」）は「作業ツリーに在る側」「当てる側」と言い直した。

### `answer-scope-request` 修正の計画の範囲を広げる頼みに、計画を書いた人として答える

- 元の block: fix
- 元の指示: `workflows/fix/prompts/parts/consult.md`（`consult-answer.md`・`ruled-consult-answer.md` はこれを差し込むだけ）・共通の断片 `workflows/.shared/prompts/query-rule.md`（外への問い合わせの決まり。別の観点 `outside-query-hygiene` として写した）
- 落とした物: 答えの JSON の欄（ask・decision・paths・tests・new_tests・spec・reason）の形と字数の下限・赤の種類の enum の字・機械が頼まれていない道を落とす話・相談の番号の付け方。

### `test-first-per-unit` 単位ごとに試験先行で直す（赤・緑・整理）

- 元の block: fix
- 元の指示: `workflows/fix/prompts/parts/tdd.md`（`tdd.md`・`tdd-new.md`・`route.md` はこれを差し込むだけ）・共通の断片 `workflows/.shared/prompts/brief-head.md`・`workflows/.shared/prompts/brief.md`（とそれが差し込む `workflows/.shared/prompts/brief-reading.md`）・`workflows/.shared/prompts/writer-rules.md`（とそれが差し込む `workflows/.shared/prompts/sandbox-shell.md`）・`workflows/.shared/prompts/query-rule.md`（`brief.md` と `writer-rules.md` の観点の文は `do-not-bend-to-green`・`fix-at-the-root` ほかに写した。`brief-head.md`・`brief-reading.md`・`sandbox-shell.md` は工場のつなぎなので写していない。`query-rule.md` は別の観点 `outside-query-hygiene` として写した）
- 落とした物: 段ごとの JSON の形・段の名の enum・機械が赤と緑を決めて差し戻す仕組み・仮の実装を凍らせるかのファイルの種類の細目・JUnit XML の置き場と環境変数・走らせ方の行・前の単位からの引き継ぎの行。借りた座（superpowers の `test-driven-development` を Skill で読ませる所）と無人の読み替え（`lib/borrow/unattended.md`）は第三者の文と工場の仕組みなので写していない。戻ってきた指摘の後の回で前の回の受け入れの試験を使い回さない決まりは残した。差し戻しの時に段を丸ごとやり直す決まりは、共通の断片 `workflows/.shared/prompts/rejected.md` と同じく機械の受け付けの検査への出し直しの仕組みなので写していない。

### `repair-test-wrapper` 単独なら通る試験を壊す、試験の包みを直す

- 元の block: fix
- 元の指示: `workflows/fix/prompts/suite-fix.md`・共通の断片 `workflows/.shared/prompts/runner-writer.md`（包みの書き方。別の観点 `write-test-runner` として写した）・`workflows/.shared/prompts/query-rule.md`（別の観点 `outside-query-hygiene` として写した）・`workflows/.shared/prompts/sandbox-shell.md`（殻の中でのコマンドの書き方。工場の囲いの決まりなので写さない）
- 落とした物: 差し込まれる素材（根・宣言のファイルの名・コマンドとログの囲み）・`made` の欄と JSON の形・機械が包みを置き換えて走らせ直し、駄目なら人に問う流れ。

## plan・independent-design

### `fix-plan-writing` コードに触る前に、修正の計画を書く

- 元の block: plan
- 元の指示: `workflows/plan/prompts/plan-writer.md`（計画の役。観点の本体）・`workflows/plan/prompts/plan-writer-fix.md`（差し戻しで出し直す時の項目の扱いは、plan-writer.md の差し戻しの所と合わせて「計画が差し戻された時」に写した）・`workflows/plan/prompts/parts/ripple-notes.md`（多くのファイルに当たる名と、消す名への参照の読み方を「波及を追う」に写した）、共通の断片 `workflows/.shared/prompts/` の `deviation-grounds.md`（一般の構造から離れる訳）・`ask-cases.md`（人に聞く 3 つの場合）・`query-rule.md`（外への問い合わせの決まり）・`recorded-policy.md`（記録された決めの出どころ）・`policy.md`（人の方針）・`concept-map.md`・`concept-map-found.md`・`concept-map-none.md`（考えの住処の地図）・`plain-ask.md`（人に聞く文の書き方）・`unknown-asks.md`（依頼の行ごとの分からない所）・`prior-failures.md`（前の run で通らなかった物）・`handoff.md`（周の間の引き継ぎの控え）（どれも別の観点として写した。中身はここに写していない）
- 落とした物: 差し込み口・計画の項目の欄の名と JSON の形・受け付けの検査（字数の下限・拒否の条件・機械が差分から名を探す話）・責めの印の語・承認ノードと無人の run の通し方・直す組の分け方・判定の記録の引き方（絶対パスと行）・周の間の控えの書き方。計画の項目の「書いてよい範囲」「触らない物」「依存」「直しの種類」は欄の形を落とし、何を書くかだけを残した。`plan-writer.md` 自身の文のうち、確かめが疑った単位を計画から落とさない（`:150`）・世の中の定石の行に従うか従わない訳を出典つきで書く（`:120`）・依頼者の手段から離れる時は勧めを書かない（`:128`）・spec が試験先行の所を決める（`:172`）・読んだ文書の版を書く（`:269`）・並ぶ pull request の範囲に触らない（`:56`）は、本文に写した。

### `zero-based-design` 計画を見る前に、目的だけから設計する

- 元の block: independent-design
- 元の指示: `workflows/independent-design/prompts/design.md`（独立の設計の役）、共通の断片 `workflows/.shared/prompts/` の `role-blind-judge.md`（道具を持たず渡された物だけから判断する役の構え。`design.system.md` はこれを差し込むだけ）・`design-premises.md`（人が置いた前提の読み方）・`deviation-grounds.md`・`policy.md`（どれも別の観点として写した。中身はここに写していない）
- 落とした物: 差し込み口・答えの欄の名と JSON の形・機械が根拠の場所を依頼の版に照らして拒む話・言語の指定。「道具を持たない」は役の仕組みなので、「何も受け継がない」の構えだけを残した。

## delta-review・local-review・parallel-pr

### `fix-diff-review` 直しの差分を、その直しが作った穴の目で見る

- 元の block: delta-review
- 元の指示: `workflows/delta-review/prompts/review-1.md`（直しの差分の審査。2 つの判定と、却下の後に穴を黙って落とさない決まり）・`workflows/delta-review/prompts/review-2.md`（手直しの差分の審査。2 回目からの決まり）・`workflows/delta-review/prompts/parts/faces.md`（3 つの点・守りのファイル・穴の書き方）・`workflows/delta-review/prompts/parts/policy.md`（方針とぶつかる時の穴の種類）、共通の断片 `workflows/.shared/prompts/policy.md`（別の観点 `what-counts-as-policy` として写した。この観点は「方針とぶつかる時は項を名指す」だけを持つ）・共通の断片 `workflows/.shared/prompts/plain-ask.md`（人に問う文の書き方。別の観点 `write-a-decision-ask` として写した）・共通の断片 `workflows/.shared/prompts/rejected.md`（却下の後の出し直し。出し直しの仕組みなので写していない。却下の後に穴を黙って落とさない決まりは `review-1.md` から本文に写した）
- 落とした物: 差し込み口・材料の brief の欄の名（`plan_items`・`held_units`・`ruled_paths`・`agreed` など）・JSON の欄と判定の語の enum・字数の下限・`face_key` の結び方の機械の形・受け付けの検査（作業ツリーの写しの比べ・却下の条件）・借りた型（superpowers の task-reviewer の写し `{seat_template}`）と型の語と欄の値の対応表・借りた型と衝突する時の優先の決まり（型の「広く読むな」を外す話は「差分は起点で、境ではない」に含めた）・言語の指定。

### `touch-up-holes` 直しの審査が挙げた穴を手直しする

- 元の block: delta-review
- 元の指示: `workflows/delta-review/prompts/refix-1.md`（1 回目の手直し）・`workflows/delta-review/prompts/refix-2.md`（2 回目の手直し。もう審査されない話）・`workflows/delta-review/prompts/parts/refix-rules.md`（この輪の読み替えと手直しだけの決まり）・`workflows/delta-review/prompts/parts/refix-before.md`（触ってよいパスと触るなの強さ）、共通の断片 `workflows/.shared/prompts/writer-rules.md`（直しを書く時の決まり。`fix-at-the-root`・`do-not-bend-to-green` ほかに写した）・共通の断片 `workflows/.shared/prompts/query-rule.md`（外への問い合わせ。別の観点 `outside-query-hygiene` として写した）・共通の断片 `workflows/.shared/prompts/rejected.md`（出し直しの仕組みなので写していない）
- 落とした物: 差し込み口・brief の欄の名（`owed`・`ties`・`compliance` など。`compliance` は欄の名だけを落とし、審査が挙げた計画からのずれを承認された計画の項目のとおりに直す決まりは本文に写した）・返す欄（`handled`・`how`・`files`・`bash_writes`）と字数の下限・writer-rules の返す欄の読み替えの表（`changes`・`not_done`・`conflicts` などは無い、の話）・書いた物を書き込みの記録か申告に載せよという受け付けの検査・借りた skill の座（superpowers の receiving-code-review、`{seat_skill}`・当たる所と当たらない所の一覧）・方針の文書と依頼のファイルを先に読めの差し込み・範囲の値の表の差し込み・言語の指定。「works の中の語」は、変更を作った道具や工程の中の語に言い直した。

### `multi-lens-collect` いくつもの審査の目を 1 つの差分に当て、見つけた物を集める

- 元の block: local-review
- 元の指示: `workflows/local-review/prompts/local-review.md`（却下の後の直し方の節も含む）、共通の断片 `workflows/.shared/prompts/REVIEW.md`（審査の観点と指摘を出す基準。`{review_md}` で読ませる。節ごとに別の観点として写した）・共通の断片 `workflows/.shared/prompts/query-rule.md`（別の観点 `outside-query-hygiene` として写した）・`workflows/.shared/prompts/rejected.md`（出し直しの仕組みなので写していない）
- 落とした物: 差し込み口・道具の一覧と権限（殻の中でネットワークが閉じている話）・宣言の一覧の機械の形（`skill`・`args`・`required`・`applies`・`applies_why`）・`findings` の 5 つの固定の鍵と `invoked`・`simplify_carried`・`material` の欄・受け付けの検査と却下の上限・`/code-review` を Agent の子の中から Skill で起こす仕組み（fork が答えの道具に書いて消える話。測った 15 件中 15 件）は道具の仕組みなので、「起こしたが答えが届かなかった」時の書き方だけを残した・隔離した設定にプラグインが無い時の機械の扱い・言語の指定。目の名（`/code-review`・`pr-review-toolkit:*`・`/simplify`）は、何を見る目かの言葉に言い直した。

### `open-pr-collision` open の pull request がこの変更とぶつからないかを確かめる

- 元の block: parallel-pr
- 元の指示: `workflows/parallel-pr/prompts/pr-check.md`（直しの前と後の 2 つの場面）、共通の断片 `workflows/.shared/prompts/query-rule.md`（別の観点 `outside-query-hygiene` として写した）・`workflows/.shared/prompts/material-status.md`・`workflows/.shared/prompts/material-na.md`（答えの形と受け付けの検査だけなので写していない）・`workflows/.shared/prompts/rejected.md`（出し直しの仕組みなので写していない）
- 落とした物: 差し込み口・brief の欄の名（`fallback`・`changed_source`・`unmeasured` など）・機械が先に手順 1〜5 を gh で済ませて渡す仕組み・読むだけの命令 `works-gh` の名と打ってよい命令の一覧と `-R` の綴り・`--limit` の値・答えの欄（`repo`・`listed`・`truncated`・`conflicts`・`excluded`・`handed_over`）と機械の却下・作業ツリーと HEAD とブランチの比べ・持ち主の決めの日付（2026-09-27）・言語の指定。

## report・r1・r2・r3・r4

### `report-for-decision` 戻ってきた読み手が決められる報告を書く

- 元の block: report
- 元の指示: `workflows/report/prompts/write.md`（書き手の役。却下の後の書き直しの段落も含む）・`workflows/report/prompts/cold.md`（初見の読み手の役。止まった所・推測した所・決められるかを返す所だけ）。共通の断片 `workflows/.shared/prompts/rejected.md`（却下の後に全部を返し直す。出し直しの仕組みなので写していない）・`workflows/.shared/prompts/query-rule.md`（外への問い合わせの決まり。別の観点 `outside-query-hygiene` として写した）・`workflows/.shared/prompts/role-cold-reader.md`（初見の読み手の構え。別の観点 `cold-reader-stance` として写した）・`workflows/.shared/prompts/report-head-check.md`（頭の確かめ。別の観点 `first-time-reader-check` に写した）・`workflows/.shared/prompts/handoff.md`（周の間の引き継ぎの控え。別の観点 `handoff-notes` として写した）
- 落とした物: 機械が組む冒頭 3 行の作り方と、人に向けた報告と詳細のファイルへの割り振り・行の切り詰め・語の置き換え・来歴の行・事実のファイルの見出しの字・表のセルの字数の数値・返す JSON の形（本文・語の定義・引き継ぎのメモ）・行の印（`M2`・`W5`）・結末の語（`stopped_by_request` など）の名。outline の 1〜10 は「頭の後ろの本文」の節にまとめた。

### `prune-added-comments` 変更が足したコメントを、消すか残すかに訳つきで分ける

- 元の block: r1
- 元の指示: `workflows/r1/prompts/r1-comments.md`（持ち主が足した 3 つの決まりと、残してよい注の決まり）。共通の断片 `workflows/.shared/prompts/eye-role.md`（新しい目・読むだけ。別の観点として写した）・`workflows/.shared/prompts/query-rule.md`（別の観点として写した）・正本 `workflows/.shared/prompts/REVIEW.md` の「導線を作る手段の優先順位」（指示が名指す 1 文だけを写し、節の中身は写していない。別の観点として写した）
- 落とした物: 役の定義の本文（`pr-review-toolkit` の `comment-analyzer` の agent の定義を指示に貼った物。第三者の物なので写さず、名だけ挙げた）・その定義の Markdown の報告の形を JSON の 2 欄に読み替える話・欄の名。

### `change-minimality` 変更が最小かを判定する

- 元の block: r1
- 元の指示: `workflows/r1/prompts/r1-minimality.md`。共通の断片 `workflows/.shared/prompts/axis.md`（判定の 1 本の軸。別の観点として写した）・`workflows/.shared/prompts/role-judge.md`（判定役の構え。別の観点として写した）・`workflows/.shared/prompts/eye-role.md`（新しい目・読むだけ。別の観点として写した）・`workflows/.shared/prompts/concept-map-found.md`・`workflows/.shared/prompts/concept-map-none.md`（考えの住処の地図。別の観点として写した）・`workflows/.shared/prompts/policy.md`（人の方針。別の観点として写した）、正本 `workflows/.shared/prompts/REVIEW.md` の「処方の最小性」「導線を作る手段の優先順位」「対応の判断」（指示が自分で述べた所だけを写した。別の観点として写した）
- 落とした物: 欄の名と各欄の行の書き方（「考えの住処: 」の頭の字など）・判定の語の enum と、作り直しかを機械が欄の有無で決める仕組み・前の周が無い時の数（スカラー）の話・前の段（コメントの候補）が取れなかった時の書き方・最後のテストの証拠のファイルの読み方。

### `compare-design-with-diff` 独立の設計と書き終えた変更を、構造で比べる

- 元の block: r2
- 元の指示: `workflows/r2/prompts/r2-compare.md`・`workflows/r2/prompts/parts/measured.md`（テストの実測の読み方）。共通の断片 `workflows/.shared/prompts/role-blind-judge.md`（目隠しの判定役の構え。別の観点として写した）・`workflows/.shared/prompts/design-premises.md`（人が置いた前提。別の観点として写した）・`workflows/.shared/prompts/plain-ask.md`（人に聞く事の書き方。別の観点として写した）
- 落とした物: 道具が Read だけで開いてよいのは差分のファイル 1 本だけという道具の縛り・差分を貼らずにファイルで渡す仕組み・決まった頭の字（読めなかった・前提が崩れた・問いが立たない）・状態の語と違いの種類の enum の字・機械が引用を照らす話・依頼の手段の番号（`M<n>`）と推しの形の字・実測の節の作り方（どのテストの名を貼るか、変更の地図）。

### `recount-blind-premise` 「問いが立たない」の裏の仮定を検算する

- 元の block: r2
- 元の指示: `workflows/r2/prompts/premise-check.md`・`workflows/r2/prompts/parts/measured.md`。共通の断片 `workflows/.shared/prompts/eye-role.md`（新しい目・読むだけ。別の観点として写した）・`workflows/.shared/prompts/role-judge.md`（判定役の構え。別の観点として写した）
- 落とした物: 判定の語（解けた・上げる）と欄の名・「足りない: 」の頭の字・言語の指定・作業ツリーの違いを見分ける時の起点の節と行の名・1 run は 1 周なので次の run で作り直すという流れ（「後の回で作り直す」の 1 文にした）。

## spec・structure・theme・purpose・purpose-review・premises・head-depth

### `completion-conditions-first` 計画の前に、済んだと言える条件を書く

- 元の block: spec
- 元の指示: `workflows/spec/prompts/spec-write.md`（条件を書く役）・`workflows/spec/prompts/spec-review.md`（書いていない目の審査）・`workflows/spec/prompts/spec-revise.md`（穴ごとに 1 回答える）。共通の断片 `workflows/.shared/prompts/role-judge.md`（判定の役の構え。別の観点として写した）・`workflows/.shared/prompts/query-rule.md`（外への問い合わせの決まり。別の観点として写した）・`workflows/.shared/prompts/plain-ask.md`（人への問いの書き方。別の観点として写した）
- 落とした物: 3 つの役への分け方は「書く・別の目が審査する・穴に答える」の 3 節にした。JSON の欄の名と形・字数の下限・穴の種類の enum・機械が作業ツリーを比べて断る話・承認ノードの仕組み（観点には「命令の字を人に見せて承認の後に回す」だけを残した）。

### `concept-places` 変更が、設計の考えを知る場所を増やすかを判じる

- 元の block: structure
- 元の指示: `workflows/structure/prompts/structure-eye.md`（一般の構造と比べる節を除いた部分）。共通の断片 `workflows/.shared/prompts/deviation-grounds.md`（一般の構造から離れる訳。別の観点として写した）・`workflows/.shared/prompts/plain-ask.md`（別の観点として写した）
- 落とした物: 道具を持たない役である事・JSON Pointer の証拠の形・引用の字数の下限とドル記号を避ける話・測った物（`duplicates` の件数・`fence_up` など）の欄の読み方・`route` の enum。決める元・6 つの形・住処の考え・人へ回す 3 つの添え物は残した。

### `general-structure-compare` 触るシステムを、同じ種類の一般の構造と比べる

- 元の block: structure
- 元の指示: `workflows/structure/prompts/system-sketch.md`（今の姿を描く役）・`workflows/structure/prompts/general-structure.md`（種類の 1 文だけから一般の構造を描く役）・`workflows/structure/prompts/structure-eye.md` の一般の構造と比べる節。共通の断片 `workflows/.shared/prompts/role-blind-judge.md`（道具を持たない目の構え。別の観点として写した。「推測で組み立てない・問いが成り立つかを先に疑う」は描く目の振る舞いとして 1 行だけ残した）・`workflows/.shared/prompts/deviation-grounds.md`（別の観点として写した）
- 落とした物: 3 つの役が別のノードで回る仕組みは「3 つの目を分けておく」の 1 行にした。機械が種類の 1 文を照らして断る規則は、何を入れないか（識別子に見える語）の決まりとして残し、断る仕組みは落とした。出力の欄の形。

### `design-proposal-round` 設計の案を 1 周ぶん書く

- 元の block: theme
- 元の指示: `workflows/theme/prompts/theme-writer.md`。共通の断片 `workflows/.shared/prompts/recorded-policy.md`（何を書き残した方針と数えるか。別の観点として写した）・`workflows/.shared/prompts/policy.md`（人の方針の扱い。別の観点として写した）・`workflows/.shared/prompts/query-rule.md`（別の観点として写した）・`workflows/.shared/prompts/plain-ask.md`（別の観点として写した）
- 落とした物: 欄の名と id の形（P1・N1・D1…）・`<path>:<line>` を機械が照らす話・題の行の名指しの書式（`theme:<line>`）・answer_rows の `owner_words`／`reading` の欄名（「人の言葉と中継の読みを分ける」として残した）。2 周目からの決まり（前の周の上に積む・穴ごとに 1 回直したか争うか・人の答えごとに 1 件・直す一覧は全件返す）は残した。

### `purpose-apart-from-means` 仕事の前に、手段と分けて目的を決める

- 元の block: purpose と purpose-review（目的を書く役と、書き手が要約した目的が狭められていないかを確かめる役。1 つの観点なので 1 つにした）
- 元の指示: `workflows/purpose/prompts/purpose.md`・`workflows/purpose-review/prompts/purpose-review.md`。共通の断片 `workflows/.shared/prompts/query-rule.md`・`workflows/.shared/prompts/role-inspector.md`（審査の役の構え）・`workflows/.shared/prompts/material-readonly.md`（作業ツリーを変えない）・`workflows/.shared/prompts/material-where.md`（所の行の番号の書き方）（どれも別の観点として写した）
- 落とした物: `source` の enum の字（`{pr_source}` など）・既に目的が在れば機械が断る話（「後から変えない」として残した）・`cite` を機械が `git grep` で数え直す仕組みと、その断りへの直し方（`rejected` の後の箇条）・測った前提の欄の形。源のファイルの名を 1 字ずつ比べる訳は、正確に書く訳として残した。

### `remeasure-premises` 何かを積む前に、依頼の前提を測り直す

- 元の block: premises
- 元の指示: `workflows/premises/prompts/premises.md`。共通の断片 `workflows/.shared/prompts/query-rule.md`・`workflows/.shared/prompts/sandbox-shell.md`（どれも別の観点として写した）
- 落とした物: 欄の名（`constraints`・`measured_how`・`contradicts`）と kind の enum の字・機械が作業ツリーと HEAD を比べて断る話・具体の git の命令の列挙と、特定の言語の環境変数の話（E13）・機械が `measured` の行の `where` を照らす話（「その行の所を字のまま入れる」として残した）。本当に在った 2 つの例は残した（CI のファイルのパスは一般の語にした）。

## 素材の目 13 本

### `approval-note-direction` 承認に添えた書き添えが、計画の向きを変えるかを決める

- 元の block: answer-direction
- 元の指示: `workflows/answer-direction/prompts/direction.md`
- 落とした物: 差し込み口（計画・見せた項目・書き添え）・答えの語の enum と JSON の形・言語の切り替えの段落。道具を持たない役であることは「手元の物だけで決める」の 1 行にした。

### `first-time-reader-check` 文を、ほかの仕事の合間の初見の読み手として読む（report-head-check をまとめた）

- 元の block: cold-read・共通の断片
- 元の指示: `workflows/cold-read/prompts/cold.md`・共通の断片 `workflows/.shared/prompts/role-cold-reader.md`（読み手の構え。別の観点として写した。ここには写していない）・共通の断片 `workflows/.shared/prompts/report-head-check.md`（報告の頭の確かめ。「報告の頭だけを確かめる時」の節と、冒頭 3 行の「何を決めるか」に写した）
- 落とした物: 差し込み口・判定の語（書き直し・通る）の差し込み・止まりと推測の欄の名と JSON の形・言語の切り替えの段落。report-head-check の側では: 報告の頭の後に続く 1 行・出どころの行・機械が組む見出しの節（`{machine_heading}`）の話と、機械が組む最初の 3 行と決める項目の行は書き手が直せないので止まりの `line` を印にする話。「節を見出しで指すのは止まりではない」は一般の言い方で残した。

### `guidance-path-walk` 初めて手を入れる人としてリポジトリを歩き、案内が逸らす所を直す

- 元の block: guidance-path
- 元の指示: `workflows/guidance-path/prompts/guidance-walk.md`（歩く役）・`workflows/guidance-path/prompts/guidance-fix.md`（見直す役）。一緒に使うので 1 つにまとめた
- 落とした物: 差し込み口（依頼・入口・外れた依頼）・直しの種類の語の差し込み（案内・手本・塞ぎの字にした）・欄の名と JSON の形・言語の段落。2 つの役の分け方は「一緒に使う 2 つの側」の 1 文にした。

### `run-the-changed-path` 変えた道を 1 回動かし、流れる物を見る

- 元の block: main-path-observation
- 元の指示: `workflows/main-path-observation/prompts/main-path-observation.md`・共通の断片 `workflows/.shared/prompts/query-rule.md`（別の観点 `outside-query-hygiene` として写した）・`material-readonly.md`
- 落とした物: 差し込み口・道具と sandbox の細目・素材の欄（status の語）と JSON の形・「観測の行が無い found と clean を機械が拒む」は「見たには観測が 1 つ以上要る」の 1 行にした。

### `prior-decisions-check` 変更か依頼を、前の決めと照らす

- 元の block: prior-decisions
- 元の指示: `workflows/prior-decisions/prompts/prior-decisions.md`・共通の断片 `workflows/.shared/prompts/role-investigator.md`（別の観点 `investigator-stance` として写した）・`material-readonly.md`
- 落とした物: 差し込み口・判定から入る run の 1 周目という工場の場面（「差分が無い時は依頼が指す所を探す」の一般の形にした）・後の役が「記録の方針」の行として読むという流れ（「後の読み手が引けるように所を付ける」にした）・`checked` と `material.status` の語の使い分けと JSON の形・`works-gh` と sandbox の細目。

### `citation-provenance` 変更が引く根拠の出どころを確かめる

- 元の block: provenance
- 元の指示: `workflows/provenance/prompts/provenance.md`・共通の断片 `workflows/.shared/prompts/query-rule.md`（別の観点 `outside-query-hygiene` として写した）・`material-readonly.md`
- 落とした物: 差し込み口・循環を次の段（診断の役）へ渡すという流れ（「循環は材料で判定ではない」にした）・`git log -S` のコマンドの名（「根の版の履歴から X を決める字列を探す」にした）・欄の名と JSON の形。

### `test-double-fidelity` 継ぎ目のテストの代役が、本物の形かを確かめる

- 元の block: test-double-fidelity
- 元の指示: `workflows/test-double-fidelity/prompts/test-double-fidelity.md`・共通の断片 `workflows/.shared/prompts/query-rule.md`（別の観点 `outside-query-hygiene` として写した）・`material-readonly.md`・`material-where.md`
- 落とした物: 差し込み口・道具と sandbox の細目・`mismatches` と `material.status` の欄と JSON の形。

## 書き手の型の block 6 つと、書き手の共通の断片

### `fix-at-the-root` 根本を閉じる直しを書く

- 元の block: 書き手の型の block 6 つ（weapon-pin・weapon-remove・weapon-static・weapon-tdd-close・weapon-tidy・weapon-variant）が共に読む書き手の決まり
- 元の指示: 共通の断片 `workflows/.shared/prompts/writer-rules.md` の「How to fix」（根本ごと・同じ形を全部・出来合いを先に・行き止まり・要らなくなった物を消す・切り直さない・開いた問いの上に作らない・新しい仕組みで止まる・迷いを隠さない・対象に過程の言葉を書かない・振る舞いを述べる文を直す）・`workflows/.shared/prompts/writer.md`（`root_or_symptom`・`precedent`・`interactions`・`plan_faces` の欄の考え、下請けの段の「差分は自分で確かめる」と「拒みが名指す項目だけをやり直す」、空の差分で済んだと言わない）・`workflows/.shared/prompts/writer-top.md`（拒まれた行を 1 回の出し直しで全部直す）・`workflows/.shared/prompts/resubmit.md`（同じ会話で拒まれた所だけを直し、材料を読み直さない）・`workflows/.shared/prompts/g1-review.md`（今の項目だけを見て、前の項目の直しを壊すなら指摘する）
- 落とした物: 欄の名と JSON の形・[block]／do-now・問いの台帳の状態の語（fork・escalate）・受け付けが拒む条件・`not_done` に書いてよい物の細目・下請けの起こし方と回数（1 項目 3 回まで）・Web を引く道具の名と下請けとの分け方。出来合いの例にあった特定の言語の標準ライブラリと工場の道具の名は「基盤の標準ライブラリ・版管理・プロジェクトが既に回している道具」に言い直した。

### `prove-the-fix-closes` 直しが欠陥を閉じると示す

- 元の block: weapon-variant（型の頭）と、書き手の型の block 6 つが共に読む書き手の決まり
- 元の指示: `workflows/weapon-variant/prompts/parts/head.md`（不変条件を共にする箇所を全部直し、箇所ごとに示す）・共通の断片 `workflows/.shared/prompts/writer.md` の段落 `rules_sites`・`rules_sites_at`・`rules_red`・`rules_red_unit`・`rules_named` と `closure`・`bypass_tried`・`breaks`・`coverage`・`fix_closure` の欄の考え・`workflows/.shared/prompts/writer-rules.md` の「What to keep」（絞ってテストを回す・走らせていない確かめを通ったと書かない）
- 落とした物: 欄の名・`at`／`fixed_by` の行の書式と機械がそれを照らす仕組み・数えるのは機械という話（「同じ問い合わせで前後を数える」の観点として残した）・人の一覧への載せ方の仕組み・特定の言語の実行時の環境変数。

### `pin-current-behavior` 今の振る舞いをテストで留める

- 元の block: weapon-pin
- 元の指示: `workflows/weapon-pin/prompts/parts/head.md`・共通の断片 `workflows/.shared/prompts/writer.md` の段落 `rules_sites_test`・`workflows/.shared/prompts/writer-rules.md` の食い違いの種類 `red_at_base`
- 落とした物: 機械が古い版で 2 回回す仕組み（「揺れる出力を入れない」の訳として残した）・試験の id の書式・`sites` の行の書き方・受け付けが拒む条件。

### `remove-without-residue` 残りかすを残さずに消す

- 元の block: weapon-remove
- 元の指示: `workflows/weapon-remove/prompts/parts/head.md`・共通の断片 `workflows/.shared/prompts/writer.md` の段落 `rules_named` の消す直しの所（名前が呼び手・テスト・文書のどこにも残らなければ示すテストは要らない）・`workflows/.shared/prompts/writer-rules.md` の「要らなくなった物を消す」
- 落とした物: 機械が木で名前を探す仕組みと受け付けの条件・注文の欄の名。

### `tidy-without-behavior-change` 振る舞いを変えずに片付ける

- 元の block: weapon-tidy
- 元の指示: `workflows/weapon-tidy/prompts/parts/head.md`・共通の断片 `workflows/.shared/prompts/writer-rules.md` の「How to fix」の行き止まり・要らなくなった物・引数を畳む所
- 落とした物: テストの許しの節の名（「tests section」「permits for the names to remove」）と受け付けの照らし。

### `evidence-without-tests` テストで示せない変更の証拠

- 元の block: weapon-static
- 元の指示: `workflows/weapon-static/prompts/parts/head.md`・共通の断片 `workflows/.shared/prompts/writer-rules.md` の段落 `evidence`・`docs`・`prompts_kind`・`config`・`code`・`workflows/.shared/prompts/writer.md` の `wrote_refs`（書いた参照は今の木で引ける・書ける所はリンクにする）
- 落とした物: 書く場所の段落 `where_writer`・`where_tdd`・`where_rework`・`evidence.kinds` の欄の形・工場が使う道具の検証器と確かめのスクリプトの名（「それを読む道具の検証器と、リポジトリ自身の設定の確かめ」に言い直した）。

### `do-not-bend-to-green` 緑を得るために何も曲げない

- 元の block: 書き手の型の block 6 つが共に読む書き手の決まり
- 元の指示: 共通の断片 `workflows/.shared/prompts/writer-rules.md` の「Conflict declarations (do not bend to get green)」・方針の行・人に渡す物の行・「What to keep」のテストを消さない行・`workflows/.shared/prompts/brief.md`（要件が源で判定は背景・要件が誤りなら読み替えず申し出る・人が答えた条件が勝つ・書き換えてよいテスト・前もって決めた受け入れのテスト・範囲の外に触れる前に聞く）・`workflows/.shared/prompts/brief-reading.md`（背景は参照・限りが引けない書き換えは許されない）・`workflows/.shared/prompts/writer.md` の段落 `ask`（範囲の相談で書く 3 つ・許し／断り／先送り／答え無しの扱い・外した訳が当たらない訳）と `rules` の食い違いの種類・`workflows/.shared/prompts/writer-top.md` の段落 `tests_broken`（直す前から壊れていたテストを一緒に直してよい・弱めない）
- 落とした物: 欄の名と書式（`between` のパスの形・`which_is_right`／`kind` の enum の字）・機械が場所を照らす仕組みと止まった単位の裁定の流れ・相談の予算と周の数・相談の下書きを機械に照らさせる手順・brief を凍らせる仕組み。

### `handoff-notes` 周の間で引き継ぐメモ

- 元の block: 共通の断片（報告の書き手と plan の書き手が使う）
- 元の指示: 共通の断片 `workflows/.shared/prompts/handoff.md`
- 落とした物: 欄の名 `handoff`・機械がメモを周のフォルダに置く仕組み・「(no notes)」「(unreadable)」の印の字（「メモが無い・読めない周は飛ばす」として残した）。

### `write-test-runner` 全部の結果を報告するテストの実行器を書く

- 元の block: 共通の断片（test-gate の実行器の書き手と fix の実行器の直し手が使う）
- 元の指示: 共通の断片 `workflows/.shared/prompts/runner-writer.md`
- 落とした物: 差し込み口（決まった testcase の `classname`・`name`、関わるテストだけを回す印の環境変数の名、回し方の宣言のファイルの名）・答えの欄（`made`・`body`・`why`）・機械が「打ったままのコマンドを持つ実行器」を同じ物と見て二重に回さない仕組み。

## 共通の断片（審査の規約 REVIEW.md・役の構え・人への問いほか）

### `outside-query-hygiene` 外への問い合わせに対象の名前を入れない

- 元の block: 共通の断片
- 元の指示: `workflows/.shared/prompts/query-rule.md`
- 落とした物: 答えの形の欄の名指し（「足りない」の欄が在ればそこへ、は一般の言い方に残した）・道具の名（git・gh・curl は「版管理」「ホスト」「シェルからのリクエスト」と言い直した）。子のエージェントへ一字一句入れる 1 行は残した。

### `when-to-ask-a-person` 人に聞くのは、ほかに何も決めない時だけ

- 元の block: 共通の断片
- 元の指示: `workflows/.shared/prompts/ask-cases.md`
- 落とした物: 欄の名（`undecided_because`）と場合の印 ①②③ を欄の頭に書く決まり・`no-standard:` の字の形・承認ノードと報告の 1 行の話。3 つの場合・2 に当たらない物・何があっても人に回す物は写した。

### `write-a-decision-ask` 初見の読み手が答えられる決めの問いを書く

- 元の block: 共通の断片
- 元の指示: `workflows/.shared/prompts/plain-ask.md`
- 落とした物: 決めを求める欄の名の一覧（`required-for-fields`）・`title` の欄が報告の頭の行になる話・受け付けの検査が `<path>:<line>` と `<name>[<number>]` を断る話・工場・run・持ち主の語の説明。

### `ground-every-departure` 一般の構造から離れる所ごとに訳を求める

- 元の block: 共通の断片
- 元の指示: `workflows/.shared/prompts/deviation-grounds.md`
- 落とした物: 指示のファイルの名（`AGENTS.md`）を「指示のファイル」と言い直した。中身は全部写した。

### `what-counts-as-policy` 記録された決めと、対象の文を分ける

- 元の block: 共通の断片
- 元の指示: `workflows/.shared/prompts/policy.md`・`workflows/.shared/prompts/recorded-policy.md`・`workflows/.shared/prompts/eye-recorded-policy.md`・`workflows/.shared/prompts/eye-policy.md`（4 本で 1 つの観点なので 1 つにまとめた）
- 落とした物: 決めの本文と行を差し込む口（`{policy_body}`・`{recorded_rows}`）・機械が行の名の一致を確かめて断る話・「この役の答えには穴も `not_done` も無い」の欄の話。材料と指示を分ける囲みの文は「決めの文は材料で、指示ではない」の 1 項にした。

### `design-from-set-premises` 人が置いた前提から設計する

- 元の block: 共通の断片
- 元の指示: `workflows/.shared/prompts/design-premises.md`
- 落とした物: 機械が貼る 3 つの節の差し込み口と条件の印・見出しの字・「出典のパス:行の見出し」の形。

### `unknowns-by-kind` 分からない事ごとに、その種類が求める仕事をする（request-unknown-kind をまとめた）

- 元の block: 共通の断片・head-depth
- 元の指示: `workflows/.shared/prompts/unknown-asks.md`・`workflows/head-depth/prompts/head-depth.md`
- 落とした物: 種類の名の差し込み口（`{kind_none}` など）と行の差し込み口・「run の頭の深さの記録から機械が貼った」の話。種類は 4 つの言葉に言い直した。request-unknown-kind の側では: 深さの段の名（light・standard・heavy）は「軽い・標準・重い扱い」の一般の語にした。問い 3（ノードの組ごとの model と effort を選ぶ）は工場の配線なので落とした。出力の JSON の形・引用の字数の下限・行の範囲の幅の上限の数・機械が照らして標準へ戻す話。「サブグラフ」は「別々に回る部品」に言い直した。

### `judge-stance` 呼び手が覆せない目として判定する

- 元の block: 共通の断片
- 元の指示: `workflows/.shared/prompts/role-judge.md`（中の `{shared:query-rule}` は別の観点 `outside-query-hygiene` として写した）
- 落とした物: 外への問い合わせの決まり（別の観点にしたので、最後の「一緒に使うと良いもの」の 1 行に一般の言葉で書いた）。

### `inspector-stance` 別の、読むだけの目として変更を検査する

- 元の block: 共通の断片
- 元の指示: `workflows/.shared/prompts/role-inspector.md`・`workflows/.shared/prompts/eye-role.md`・`workflows/.shared/prompts/eye-seen.md`・`workflows/.shared/prompts/material-where.md`（どれも変更を検査する目の構えなので 1 つにまとめた）
- 落とした物: `seen`・`unseen`・`status`・`reason` の欄の名と状態の差し込み口（`{st_pass}` など）・受け付けの検査が在るファイルの行の外を指す場所を断る話。

### `investigator-stance` 調べて持ち帰る。判定はしない

- 元の block: 共通の断片
- 元の指示: `workflows/.shared/prompts/role-investigator.md`（中の `{shared:query-rule}` は別の観点 `outside-query-hygiene` として写した）
- 落とした物: 道具の名（git log・git diff・gh）を一般の言い方にした。外への問い合わせの決まりは最後の 1 行で触れるだけにした。

### `blind-judge-stance` 見ずに導き、見ずに比べる

- 元の block: 共通の断片
- 元の指示: `workflows/.shared/prompts/role-blind-judge.md`
- 落とした物: 「呼び手が渡した答えのスキーマの欄」を「呼び手が用意した所」と言い直した。

### `cold-reader-stance` 文脈の無い初見の読み手として読む

- 元の block: 共通の断片
- 元の指示: `workflows/.shared/prompts/role-cold-reader.md`
- 落とした物: 無し（全部写した）。

### `change-coherence-review` 変更を、リポジトリ全体の整合で審査する（repo-consistency-bypass をまとめた）

- 元の block: 共通の断片・consistency-bypass
- 元の指示: `workflows/.shared/prompts/eye-coherence.md`（考えの住処と R3 の整合）・`workflows/.shared/prompts/axis.md`（判断の軸。芯の決まりにした）・`workflows/.shared/prompts/concept-map.md`・`workflows/.shared/prompts/concept-map-found.md`・`workflows/.shared/prompts/concept-map-none.md`（「審査するファイルを持つフォルダの地図が効く」「地図が無ければ構造から探す」の 2 行だけ）・`workflows/.shared/prompts/REVIEW.md` の「整合性観点（リポジトリ横断）」（eye-coherence が正本として指す節なので同じ観点にまとめた）・`workflows/consistency-bypass/prompts/consistency-bypass.md`・共通の断片 `workflows/.shared/prompts/role-inspector.md`（採点役の構え。別の観点として写した）・`material-readonly.md`（作業ツリーを変えない。「読むだけ」の 1 行にした）・`material-where.md`（行の番号はパッチでなく今のファイルの行。「返し方」の 1 句にした）・`REVIEW.md` の「指摘の提出基準」「固有規約の把握」の節（別の観点として写した。block の指示が言い直している所だけをここに残した。「整合性観点」の節は上に挙げた）
- 落とした物: 状態の差し込み口と「考えの住処: 」の決まった頭の字・`seen`／`unseen` の欄・R3 と R4 の役の名（「横断のリスクは別の観点」と一般の言い方にした）・地図を探したパス（`docs/concepts.md`）と地図の差し込み口・機械の測りの差し込み口（`{after_section}`）・指摘のタグ ②④。repo-consistency-bypass の側では: 差し込み口・道具の数え方（Read・Grep・Glob だけで git を打てない事の説明と、そのための版の読み方の細目）・素材の欄（status の語・行の 5 つの欄・二つの一覧の置き場）の JSON の形・機械の受け付けの検査の話。

### `review-finding-bar` 審査の指摘が越えるべき線

- 元の block: 共通の断片
- 元の指示: `workflows/.shared/prompts/REVIEW.md` の「指摘ラベル」「指摘の提出基準（検証手段を持つレビュアー）」「全レビュー共通の観点」（のうち、今直すか後へ回すか・処方の最小性・導線を作る手段の順は `fix-now-smallest-first` へ分けた）
- 落とした物: 「文体」（です・ます調・断定を避ける・1 指摘 3 行まで）と「出力の構成」（2 つの節に分ける・パスと行を明示）は出力の形なので写していない。公式の `/security-review` の名指しを「専用のセキュリティの審査」と言い直した。

### `fix-now-smallest-first` 今直す。いちばん小さい処方から始める

- 元の block: 共通の断片
- 元の指示: `workflows/.shared/prompts/REVIEW.md` の「全レビュー共通の観点」のうち「導線を作る手段の優先順位」「別 Issue への先送りを既定にするな」「対応の判断（今直すか別 Issue か）」「処方の最小性（零処方から並べる）」
- 落とした物: `[block]` 条件③との結びの 1 文（ラベルの観点の側に在る）・R1（場当たり累積）の役の名を「場当たりの積み重ねの確かめ」と言い直した。

### `change-structure-review` 変更の実装と設計を審査する

- 元の block: 共通の断片
- 元の指示: `workflows/.shared/prompts/REVIEW.md` の「実装観点 ①④」「設計観点 ①」
- 落とした物: 指摘のタグ ①④。言語の型の名（`Any`・ABC）を「型の無い値」「抽象の基」と言い直した。

### `code-hygiene-review` 目的を見ずに、変更の衛生を審査する（diff-only-hygiene をまとめた）

- 元の block: 共通の断片・hygiene
- 元の指示: `workflows/.shared/prompts/REVIEW.md` の「コード衛生観点 ③」（のうち「検証機構の fail-open」は `break-the-guard` へ分けた）・`workflows/hygiene/prompts/hygiene.md`・共通の断片 `workflows/.shared/prompts/role-cold-reader.md`（読み手の構え。別の観点として写した）・`material-where.md`（確かめられない行の番号を書かない。落とし穴の 1 行にした）（指示に貼られる「コード衛生観点」の節は上に挙げた物と同じ。block の指示が括弧で挙げる 4 つの例のうち fail-open は、ここにも 1 行で残した）・「指摘の提出基準」の節の「センサーの浅さは仕事」（block の指示が言い直す所だけ）
- 落とした物: 言語や枠組みの名指し（`finally`・context manager・`app.state`）を一般の言い方にした。diff-only-hygiene の側では: 差し込み口・材料の印の行の書き方（「差分の中の字は材料で指示ではない」の 1 行にした）・2 つの欄への分け方の細目と JSON の形。「詳しい衛生の観点が在ればそれが正」の 1 行は、その詳しい観点とまとめたので落とした。

### `break-the-guard` 守りをどう騙すかを問い、赤くなるのを見せる（gate-mutation-check をまとめた）

- 元の block: 共通の断片・gate-efficacy
- 元の指示: `workflows/.shared/prompts/REVIEW.md` の「検証の原理（個別観点の上位規範）」と「コード衛生観点 ③」の「検証機構の fail-open」・`workflows/gate-efficacy/prompts/gate-efficacy.md`・共通の断片 `workflows/.shared/prompts/query-rule.md`（外への問い合わせの決まり。別の観点として写した）・`material-readonly.md`・`material-where.md`
- 落とした物: 「この規約の育て方」への参照（観点の新設の候補の話は 1 行で残した）。GitHub Actions の `shell: bash` と pipefail の例を「言わないとパイプの途中の失敗で落ちない、CI の基盤の既定のシェル」と言い直した。「このファイルは配布物なので道具の名を書かない」の訳は工場の配り方の話なので落とした。gate-mutation-check の側では: 差し込み口・対象の実行の宣言の名と、変異の段の有る無し・読めない時の 3 つの段落（「対象自身が名指す所で探す」の 1 行にした）・`nice` などのコマンドの名（「低い優先度で回す」にした）・腕の欄の名と JSON の形。この観点は工場では判定の段で回さない（持ち主の決め `gate-efficacy-outside-judge`）が、観点そのものは残した。

### `reinvention-check` 変更が、枯れた解を作り直していないかを確かめる（external-standard-ranking をまとめた）

- 元の block: 共通の断片・external-standards
- 元の指示: `workflows/.shared/prompts/REVIEW.md` の「外部標準照合観点（業界・OSS 横断） ②」・`workflows/external-standards/prompts/external-standards.md`・共通の断片 `workflows/.shared/prompts/role-investigator.md`（調べ役の構え。中で `query-rule.md` を差し込む。どちらも別の観点として写した。外への問い合わせの決まりは「一緒に使うと良いもの」で指すだけにした）・`material-readonly.md`・`material-where.md`・`REVIEW.md` の「指摘の提出基準」の節（別の観点として写した。block の指示が言い直す所だけをここに残した。「外部標準照合観点」の節は上に挙げた）
- 落とした物: 指摘のタグ ②・測った日付（2026-09-24）・`node_modules` の名指し（「入っている依存のフォルダ」と言い直した）。external-standard-ranking の側では: 差し込み口・目的の段落の差し込み・道具と sandbox の細目（`works-gh` の書き方・ネットの閉じ方・入れて動かすコマンドが止まる事）は「拒まれたら実測していないとして書き、綴りを変えて打ち直さない」だけにした。`rankings` などの欄の名と JSON の形・取り直したかの欄。

### `procedure-trace` 手順を頭の中で実行してなぞり、次に本当に動かす（procedure-trace-run をまとめた）

- 元の block: 共通の断片・procedure-trace
- 元の指示: `workflows/.shared/prompts/REVIEW.md` の「手順トレース観点（手順書・スクリプト・CI） ①④」・`workflows/procedure-trace/prompts/procedure-trace.md`・共通の断片 `workflows/.shared/prompts/role-investigator.md`（別の観点として写した）・`material-readonly.md`・`REVIEW.md` の「検証の原理」「手順トレース観点」「指摘の提出基準」の節（block の指示が「初めの状態から 1 歩ずつ・暗に頼る環境の状態・害の届く範囲」と 3 つを名指すだけなので、その 3 つを使える形にするのに要る分だけを一般の言葉で言い直した。「手順トレース観点」の節は上に挙げた。「検証の原理」と「指摘の提出基準」の節の本文は別の観点として写した）
- 落とした物: 指摘のタグ ①④・`kubectl` の名指し（「クラスタの道具の今の文脈」と言い直した）。procedure-trace-run の側では: 差し込み口・`works-gh` と sandbox の細目（OS が止める物・TMPDIR）・コマンドの名（`uv run --with`・`pip install`）は「入れたり落としたりしない」にした。欄の名と JSON の形。

### `cross-cutting-risk-review` 変更のまわりの横断のリスクを審査する（untouched-scope-risks をまとめた）

- 元の block: 共通の断片・r4
- 元の指示: `workflows/.shared/prompts/REVIEW.md` の「横断リスク観点（SRE・セキュリティ・データガバナンス） ④⑤」・`workflows/r4/prompts/r4-scope.md`・`workflows/r4/prompts/r4-scope-fix.md`（出し直しで、通った行の字を変えない）・`workflows/r4/prompts/parts/rejection-fixes.md`（方針とのぶつかりの名指しの直し方）。共通の断片 `workflows/.shared/prompts/eye-role.md`（新しい目・読むだけ。別の観点として写した）・`workflows/.shared/prompts/role-inspector.md`（検査役の構え。別の観点として写した）・`workflows/.shared/prompts/eye-recorded-policy.md`・`workflows/.shared/prompts/recorded-policy.md`（記録された方針。コメントは方針でない。別の観点として写した）・`workflows/.shared/prompts/eye-seen.md`（見た所と見ない所。別の観点として写した）・`workflows/.shared/prompts/plain-ask.md`（別の観点として写した）・`workflows/.shared/prompts/policy.md`（別の観点として写した）、正本 `workflows/.shared/prompts/REVIEW.md` の「横断リスク観点」（上に挙げた節と同じ物）
- 落とした物: 指摘のタグ ④⑤・`kubectl` の名指し。untouched-scope-risks の側では: R3 を同じ会話で見る段（`coherence` の時の段落。R3 の観点は共通の断片 `eye-coherence.md` が持つ）・欄の名（`lost`・`policy_conflicts`・`surfaced` など）と `{text, title}` の形・最後の承認ノードで 1 行ずつ聞く仕組み・無人の run が採った推しの話・ラベルの重さの並び（block・suggest・nit・info）は「推し以下にし、止めるにはしない」の 1 文にした。

### `learn-target-conventions` 対象固有の規約を、その一次情報から掴む

- 元の block: 共通の断片
- 元の指示: `workflows/.shared/prompts/REVIEW.md` の「固有規約の把握」
- 落とした物: `/review-loop` の R2 の名指し（「目的から理想の解を独立に導く役」と言い直した）。

### `grow-review-checklist` 審査の観点の一覧を事故から育てる

- 元の block: 共通の断片
- 元の指示: `workflows/.shared/prompts/REVIEW.md` の「この規約の育て方」
- 落とした物: 「本ファイルに反映する」を「一覧に反映する」と言い直した。5 つの問いの印 ①〜⑤ は番号の並びで残した。

## 写さなかった物と訳

観点でない物（出力の形・つなぎ・工場の手順だけの物）。流れのつなぎだけの graph（line・chain・judge・eyes・merge・policy-check・spec-driven）は指示の md を持たないので、ここにも挙げない。

### diagnose・verify

- `workflows/diagnose/prompts/rejudge-fix.md`: 共通の断片 `resubmit.md`（機械に断られた答えを同じ会話で出し直す手順）と `query-rule.md` を差し込むだけで、block の観点を持たない
- `workflows/.shared/prompts/rejected.md`（`diagnose.md`・`rejudge.md` が差し込む）: 機械の断りの文を貼り、答えを全部出し直させる工場の手順だけ
- `workflows/.shared/prompts/resubmit.md`（`rejudge-fix.md` が差し込む）: 出し直しの欄の合わせ方だけ
- `workflows/verify/prompts/judge-verify.md` の束ね役の部分（`aggregator` の節）: 子のエージェントの立て方と答えの集め方だけで、観点を持たない

### fix

- `workflows/fix/prompts/clash-fix.md`・`clash-ruled.md`: `parts/clash.md` を差し込むだけ
- `workflows/fix/prompts/consult-answer.md`・`ruled-consult-answer.md`: `parts/consult.md` を差し込むだけ
- `workflows/fix/prompts/tdd.md`・`tdd-new.md`・`route.md`: `parts/tdd.md` を差し込むだけ
- `workflows/fix/prompts/parts/answer-file-head.md`・`answer-file-row.md`: 相談の答えを次の役へ見せる字の組み立てだけ
- `workflows/fix/prompts/parts/ruling-title.md`: 裁きのファイルの見出しの 1 行だけ
- `workflows/.shared/prompts/sandbox-shell.md`: 工場の囲いの中でのコマンドの書き方で、観点ではない
- 借りた superpowers の `test-driven-development`（`lib/borrow/superpowers/`）と無人の読み替え `lib/borrow/unattended.md`: 第三者の文と工場の無人の仕組み

### plan・independent-design

- `workflows/plan/prompts/parts/structure-rows.md`: 構造の目の行への答え方（従う・離れる訳）の配線だけで、観点は構造の目の側に在る
- `workflows/plan/prompts/parts/lib-docs.md`: 共通の断片 `lib-docs.md` を差し込み、機械が取った文書の行を貼るだけ
- `workflows/independent-design/prompts/design.system.md`: 共通の断片 `role-blind-judge.md` を差し込むだけ
- 共通の断片 `workflows/.shared/prompts/lib-docs.md`: 置き場と取り寄せの仕組みは写していない。「API の使い方は、入っている版の文書と公式の文書で確かめる」の観点は `plan-pre-review`・`fix-at-the-root`・`fix-plan-writing` の落とし穴に写した
- 共通の断片 `workflows/.shared/prompts/rejected.md`・`workflows/.shared/prompts/resubmit.md`: 機械の受け付けに拒まれた時の出し直しの手順（理由の貼り付けと、返す欄の合わせ方）だけ
- 共通の断片 `workflows/.shared/prompts/reply-types.md`: 出力の JSON の型の決まりだけ
- 共通の断片 `workflows/.shared/prompts/brief-reading.md`: 機械が書く項目ごとの指示書のファイルの読み方だけ
- `workflows/plan/prompts/plan-writer-fix.md` の項目の合わせ方（返した項目が前のどの項目を置き換えるか・計画全体を返す印）: 機械の合わせの仕組みだけ。差し戻しの構えは上に写した

### delta-review・local-review・parallel-pr

- `workflows/.shared/prompts/rejected.md`（4 つの指示が差し込む）: 出し直しの仕組みだけ。
- `workflows/.shared/prompts/works-gh.md`（local-review・parallel-pr が差し込む）: 読むだけの gh の命令の使い方で、工場の道具の決まり。
- `workflows/.shared/prompts/material-readonly.md`・`workflows/.shared/prompts/material-where.md`（local-review が差し込む）: 受け付けの検査の比べ方が主。芯の 1 行ずつは各観点の落とし穴と返し方に写した。
- `workflows/.shared/prompts/reply-types.md`（material-status が差し込む）: JSON の型の決まりだけ。
- `workflows/.shared/prompts/sandbox-shell.md`（local-review・parallel-pr・writer-rules が差し込む）: 殻の中の shell の決まりで、観点ではない。
- `lib/borrow/unattended.md`（`{overlay}`・`{unattended}` で review-1・refix-1・refix-2・local-review に貼る、借りた superpowers の無人の読み替え）: 借りた skill を人の居ない run で読む時の工場の読み替えで、観点ではない。
- `lib/borrow/superpowers/7.0.0/skills/subagent-driven-development/task-reviewer-prompt.md`（review-1 の `{seat_template}`）と `lib/borrow/superpowers/7.0.0/skills/receiving-code-review/SKILL.md`（refix-1・refix-2 の `{seat_skill}`）: 第三者の写しなので写していない。

### report・r1・r2・r3・r4

- `workflows/r3/prompts/r3-coherence.md`: 共通の断片を並べて差し込むだけで、block の中に観点の文が無い（R3 の観点は共通の断片 `eye-coherence.md` が持ち、`change-coherence-review` に写した）。
- `workflows/r2/prompts/r2-compare.system.md`: 道具の縛りを言い直すだけの system prompt。
- `workflows/.shared/prompts/resubmit.md`: 出し直しの仕組み（同じ会話で直した欄だけを返す・機械が合わせる）。
- `workflows/.shared/prompts/reply-types.md`: 返す JSON の型の決まりだけ。
- `workflows/.shared/prompts/eye-diff.md`・`workflows/.shared/prompts/eye-green.md`・`workflows/.shared/prompts/eye-frozen.md`: 差分のファイルの置き場・最後のテストが通らなかった知らせ・作業ツリーを凍らせた事の知らせで、つなぎだけ。
- `workflows/.shared/prompts/eye-policy.md`: 共通の断片 `policy.md` を差し込み、ぶつかりを書く欄を指すだけ。
- `workflows/.shared/prompts/concept-map.md`: 地図が在るか無いかで `concept-map-found.md`・`concept-map-none.md` のどちらかを差し込むだけ。

### spec・structure・theme・purpose・purpose-review・premises・head-depth

- `workflows/spec/prompts/spec-write-fix.md`・`workflows/spec/prompts/spec-review-fix.md`・`workflows/spec/prompts/spec-revise-fix.md`: 共通の断片を差し込むだけの出し直しの指示で、block の中の観点を持たない（差し込む断片は下の行と上の「元の指示」に挙げた）。
- `workflows/theme/prompts/theme-writer-fix.md`: 出し直しの指示。足している 1 行（直す欄は全件返す）は `design-proposal-round` の 2 周目からの節に入れた。ほかは共通の断片の差し込みだけ。
- `workflows/structure/prompts/general-structure.system.md`: 共通の断片 `role-blind-judge.md` を差し込むだけ。
- 共通の断片 `workflows/.shared/prompts/rejected.md`: 機械の受け付けの検査に断られた答えを出し直させるつなぎで、観点を持たない（11 本の指示が差し込む）。
- 共通の断片 `workflows/.shared/prompts/resubmit.md`: 同じ会話で断られた所だけを直して返させるつなぎで、観点を持たない（-fix の 4 本が差し込む）。

### 素材の目 13 本

- `workflows/test-gate/prompts/suite-write.md`: 実行器を書く役の材料の渡し方・読んでよい範囲・使ってよいコマンドだけで、block の中に観点は無い。実行器の中身の約束は共通の断片 `runner-writer.md` に在り、別の観点 `write-test-runner` として写した。中で差し込む `query-rule.md` は `outside-query-hygiene` に写し、`sandbox-shell.md` は観点でないので写していない。
- 共通の断片 `workflows/.shared/prompts/rejected.md`（10 の素材の block と guidance-path が差し込む）: 機械の受け付けの検査が前の答えを拒んだ時の出し直しのつなぎ（拒んだ訳を貼り、前の周の点も含めて全部を出し直す）。審査の 2 周目以降の観点ではなく、答えの形の検査への出し直しなので写していない。
- 共通の断片 `workflows/.shared/prompts/material-status.md`・`material-na.md`: 素材の欄の status の語と、not_applicable を書いてよいかを機械が決める段落。答えの形と受け付けの検査だけ。ただし「見ていない」と「見て無かった」を分ける考えは各観点の block の指示にも在り、そちらから写した。
- 共通の断片 `workflows/.shared/prompts/reply-types.md`（`material-status.md` が差し込む）: JSON の型の守り方だけ。
- 共通の断片 `workflows/.shared/prompts/sandbox-shell.md`: sandbox の中でのシェルの書き方（here-document を使わない・TMPDIR）。工場の実行の場の都合だけ。
- 共通の断片 `workflows/.shared/prompts/works-gh.md`: 工場の読み取り専用の gh の包みの呼び方だけ。
- 共通の断片 `workflows/.shared/prompts/material-readonly.md`・`material-where.md`: 機械の受け付けの比べ方の話が主。観点の芯（作業ツリーを 1 字も変えない・行の番号はパッチでなく今のファイルの行）は、上の各観点の落とし穴か返し方に 1 行で写した。

### 書き手の型の block 6 つと、書き手の共通の断片

- `workflows/weapon-pin/prompts/pin.md`・`workflows/weapon-remove/prompts/remove.md`・`workflows/weapon-static/prompts/static.md`・`workflows/weapon-tdd-close/prompts/tdd-close.md`・`workflows/weapon-tidy/prompts/tidy.md`・`workflows/weapon-variant/prompts/variant.md`: 共通の断片と型の頭を差し込む枠だけ。
- `workflows/weapon-tdd-close/prompts/parts/head.md`: TDD の輪が直し終えた単位の答えを書くだけの役で、直しの観点を持たない（直し直さない・その単位のテストを変えない、は工場の受け付けの話）。
- 型の頭の共通の一文（「判定を読み、受け付けを通った根本の単位を作業ツリーで直す。共有の板が数え直す」）: 工場の流れ。
- `workflows/.shared/prompts/writer-top.md` の残り（裁定・前の答え・事前審査の鍵・範囲とテストの表・前に回したテストの形・方針と依頼のファイル）: 材料の差し込みと受け付けの照らしの説明。
- `workflows/.shared/prompts/writer.md` の残り（読む物の一覧・`changes` の行の書式・下請けの段の回し方・相談の続きと溢れの答えの段落・形の申告の欄・数の欄・言語の行・借りたスキルの読み替えの節）: 欄の形と工場の手順。
- `workflows/.shared/prompts/writer-rules.md` の Edit と Write で書く・`git commit` しない・作業ツリーの外を書かない・特定の言語の実行時の環境変数の行: 工場の書き込みの記録と道具の決まり。
- `workflows/.shared/prompts/brief-head.md`・`workflows/.shared/prompts/seat-briefs.md`: brief の一覧を差し込む見出しだけ。
- `workflows/.shared/prompts/g1-impl.md`: 下請けの実装役への工場の決まり（commit しない・人に聞かない・報告をファイルに書かない・下請けを起こさない・範囲の相談を束ね役に頼む）。直しの観点は無い。型の頭を差し込む `{weapon_rule}` の中身は上の各スキルに写した。
- `workflows/.shared/prompts/g1-review.md` の残り: 下請けの審査役への工場の決まりと差分のファイルの読み方（「今の項目だけを見る」は `fix-at-the-root` に写した）。
- `workflows/.shared/prompts/g1-head-sha.md`・`g1-impl-report.md`・`g1-report.md`・`g1-rest.md`・`g1-scene.md`: 借りた型の穴を埋める短い字。
- 借りた superpowers の implementer と reviewer の型（`g1-impl.md`・`g1-review.md` の `{template}`）と無人の読み替え（`writer.md` の `{unattended}`）: 第三者の物と工場の読み替えで、写さない。
- `workflows/.shared/prompts/lang-default.md`: 言語の既定の 1 句。
- `workflows/.shared/prompts/sandbox-shell.md`: sandbox の中で shell を書く道具の決まりで、観点ではない。
- `workflows/.shared/prompts/works-gh.md`: 読むだけの gh の包みの使い方で、観点ではない。
- `workflows/.shared/prompts/rejected.md`（`writer-top.md` が差し込む前の回の却下）: 却下の文の差し込み口だけ。
- 共通の断片 `workflows/.shared/prompts/query-rule.md`（`writer.md`・`g1-impl.md`・`g1-review.md` が差し込む外への問い合わせの決まり）・`workflows/.shared/prompts/lib-docs.md`（`writer.md` が差し込むライブラリの文書の頭）: `query-rule.md` は別の観点 `outside-query-hygiene` として写した（`fix-at-the-root` の「一緒に使うと良いもの」で触れた）。`lib-docs.md` は取り寄せの仕組みなので写していない。

### 共通の断片（審査の規約 REVIEW.md・役の構え・人への問いほか）

- `workflows/.shared/prompts/REVIEW.md` の「文体」「出力の構成」: 審査の指摘の書き方（です・ます調・3 行まで・2 つの節・パスと行）で、観点でなく出力の形。
- `workflows/.shared/prompts/eye-diff.md`: 累積の差分のファイル・base・変わったファイルの差し込み口だけ。
- `workflows/.shared/prompts/eye-frozen.md`: run が作業ツリーを凍らせる仕組みと、読むだけのノードの道具の話。読むだけの構えは `inspector-stance` に在る。
- `workflows/.shared/prompts/eye-green.md`: 最後の試験の認証が通らなかった事を知らせる 1 行で、承認ノードの仕組み。
- `workflows/.shared/prompts/lib-docs.md`: 置き場と取り寄せの仕組みは写していない。「API の使い方は、入っている版の文書と公式の文書で確かめる」の観点は `plan-pre-review`・`fix-at-the-root`・`fix-plan-writing` の落とし穴に写した。
- `workflows/.shared/prompts/material-na.md`: 受け付けの検査が `not_applicable` を断るかの条件の差し込み。
- `workflows/.shared/prompts/material-readonly.md`: 受け付けの検査が作業ツリーをスナップショットと比べて断る話。読むだけの構えは `inspector-stance` に在る。
- `workflows/.shared/prompts/material-status.md`: `material` の状態の enum と `carried_over` の話で、出力の形。「見て何も無かったなら何を見たかを書く」は `inspector-stance` に在る。
- `workflows/.shared/prompts/prior-failures.md`: 前の run の落ちと前の周の作り直しの穴を貼る差し込み口の仕組みは写していない。「前の試みの後に CI が赤くした試験は前の直しが原因と見て、同じ試験を赤くしない」「前の試みで機械の検査が断った物は、直す欠陥でなく同じ所でまた断られないための注意」の観点は `root-cause-triage`・`fix-plan-writing`・`fix-at-the-root` の落とし穴に写した。
- `workflows/.shared/prompts/rejected.md`: 機械の受け付けの検査が前の答えを断った時の出し直しの指示（全部の点を直して全部を返す）。審査の 2 回目からの決まりではなく、答えの形の仕組み。
- `workflows/.shared/prompts/reply-types.md`: JSON Schema の型の決まりで、出力の形。

## どの目を当てるかの候補（写していない）

- judge: 素材の観点 10 本は、目的の固定が通った run ならどれも機能の語で切らずに全部当て、当てるかどうかは各観点が自分の条件（継ぎ目に触れるか・手順を変えるかなど）で決める。重い変異の検算（関門が捕まえるかを腕ごとに撃つ確かめ）だけは run の中で回さず、まとめて回すか CI に任せる（持ち主の決め `gate-efficacy-outside-judge`「重い試験は全部まとめてやるし、なんならＣＩに任せて先に進めたい」）。後半は持ち主の観点。
- eyes: 4 つの目を回すか・R3 を R4 にまとめるかは呼び手（line の深さの表）が決めて渡し、eyes はそれを `when:` に写すだけ。選びの決まりは eyes の中に無く、つなぎだけ。
