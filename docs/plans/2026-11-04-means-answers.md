<!-- coldwrite:skip 設計の下書き。語は 0 章と docs/design/README.md の頭の語の一覧で定義 -->
# 頼みの解き方と独立設計が食い違う時に、修正の前の承認ノードで人に聞く設計の下書き（受付 20261104-111958-4c5bdc。PR 1 = 案 3-A・3-B）

## 冒頭

- 何の話か: 頼みがはっきり指定した解き方（means）と、目的の 1 文だけから作った独立設計が食い違うと、今は独立設計の側が黙って勝つ。勝たせているのは計画の事前審査（plan-review の design-ask）と、修正の後の R2。持ち主は「どちらも自動では優先せず、推しつきの問いにして修正の前の承認ノードに出す。無人の run は推しを採って記録する」を選んだ（2026-11-04「おしで」。決め `means-ask`）。
- 一言で: 計画の項目の今の欄 `structure` の答える先に、頼みの解き方の鍵 `means`（`M1`…）を足す。従うなら `{means: M<n>, follows: true}`、外れるなら `{means: M<n>, deviation}`（計画の役は外れの訳だけを書く）。推しは別の目の事前審査が書く: 計画の外れの行の推しは新しい欄 `means_departs`、計画が頼みどおりなのに独立設計と食い違う所は新しい欄 `means_drifts` に書く。どちらも、修正の前の承認ノードの新しい種類の項目「頼みの解き方」にする。道は世界の解の外れ（`deviations` の `source: world`）と同じで、違いは項目が役の書いた推しの尾を持つこと（無人の run は推しで抜ける）。
- 範囲: この PR 1 は案 3-A と 3-B。R2 の比べ役の `request_conflicts`（案 1-A）は PR 2 で、並ぶ PR #969 が main に入った後に作る（6 章）。独立設計には means を渡さない（今のまま）。
- 読む人: 窓口は 1 章（E11）・2 章（決め）・5 章（試験）・7 章。実装の部署は 3 章と 4 章から。
- 版: 初めの下書き（head 24678640）への審査の指摘 8 つ（受付 20261104-113804-bb12f4）を受けて直し、2 回目の審査の指摘 5 つと参考（受付 20261104-115537-380483。head 69d55465 への審査）でさらに直した。初めの下書きの根の欄 `means_answers` と口 `means_gaps` は、今の欄 `structure` の答えの仕組みに替えた（7 章の 5）。

## 0 語

- 頼みの解き方（means）: 目的の役が目的の文から外して足し欄 `means` に 1 文ずつ並べた物（`lib/worldmark.py` の「依頼の解き方」の節）。line は `$judge.output.means` で運ぶ。番号は並びの順の 1 始まりで、`structure` の鍵の値と指示では `M1`・`M2`… と書く。
- 修正の前の承認ノード: line の `gate-before-fix`（項目は `workflows/line/src/gates.py` の `before_fix` が組む）。
- 世界の解の外れの道: 計画の項目の欄 `structure` の `{world, deviation}` → 事前審査の `deviations`（`workflows/plan-review/src/gate.py` の `world_items`）→ line の `before_fix` が種類 `gatemarks.WORLD_KIND` の項目にする。
- 答えの要る行の表（Need）: `lib/planmarks.py` の `Need`。`structure_gaps(plan, tables)` が表ごとに、どの項目も答えていない id を拒む。今の表は構造の目の汚れる行（`design_need`）と世界の解の行（`worldmark.need`）の 2 つ。

## 1 E11 の 3 つの答え

1. Archon が持っているか → 持っていない。Archon の承認ノード（`interactive`）は問いを出す口だけで、頼みの指定と別の目の食い違いを見分ける物は無い（`docs/design/archon.md`）。
2. ASF が持っているか → 持っていない。ASF の `.archon/workflows/sdlc/` の計画と審査の役は、頼みの文を前提に置くだけで、独立の設計と突き合わせる段が無い（`docs/asf-notes.md` にも該当の型は無い）。
3. 本当に要るか → 要る。keep-essence の 9（独立設計と R1〜R4。目的だけから作る独立を保つ）と 12（世界の解。頼みの解き方を疑い、外れる時は人に聞く）の間の抜け。世界の解の関所は「計画が定石から外れる時」だけ人に聞く。だから頼みの解き方が定石と同じ（`versus.verdict: same`）でも独立設計が別の形を推すと、計画は独立設計に合わせて頼みから外れ、誰にも見せずに通る（調べの 3 の run の `pr-unit-diverges-from-closer`）。その run で世界の解の関所が捕まえなかったのは、関所が計画の役の書いた世界の解の行への答えを読むだけで、`follows: true` の答えの中身を頼みの解き方と比べないため（`worldmark.world_ok` は `follows: true` なら通す）。定石の類は粗く、独立設計に合わせた形でも定石に従うと答えられるので、頼みから外れたことはどの行にも出ない。足す物は新しい仕組みにしない。答えは今の `structure` の答えの仕組み（Need の表を 1 つ足す）で照らし、人に聞くのは今の世界の解の外れの道（種類を 1 つ足す）で行う。読み方の決まり「仕組みで照らせないかを見る」にも当たる。

## 2 決め（`docs/owner-decisions.md` の `means-ask` に書いた）

1. 頼みの解き方と独立設計（とそれに合わせた計画）が食い違う時、どちらも自動では優先しない。修正の前の承認ノードに推しつきの項目で出す。
2. 無人の run では推しを採って進み、採った推しを記録する（今の `answer.PUSHED` の道。報告の冒頭と次の依頼の下書きに載る）。推しは役が書いた物だけで、機械は推しを作らない（決め `unattended`）。
3. `think`（持ち主の言葉も鵜呑みにしない）は変えない。計画の役が頼みの解き方を疑って外れるのは今どおりで、外れを人が見るようになる。
4. 独立設計には means を渡さない（`purpose.md` の「同じ解き方の枠に落ちる」を避ける今の形のまま）。これは窓口の読みで、持ち主への問いには無かった（決めの本文にもそう書いた）。

## 3 仕組み

### 3.1 計画（plan の block。案 3-A）

1. port `means` を足す（`json(shared:stated-means.schema.json)`。既定 `[]`）。line では、往復の中の `include: works-factory-plan`（`plan-rounds` の中の node `plan`）に `means: "$judge.output.means"` を、案の直しの `replan` に `means: "$fix-in.output.means"` を渡す。仕様駆動の道の `spec-plan` には渡さない（世界の解の行も渡していない。仕様駆動の道は目的の役を通らない）。
2. 形の住処を寄せる: 同じ中身の形が world（`means.schema.json`）・plan-review（`stated-means.schema.json`）・plan の 3 つになるので、`workflows/.shared/schemas/stated-means.schema.json` に 1 つにし、2 つの block の写しを消して `shared:` で読む（plan-review の設計書 19 の「2 つ以上の block が同じ中身を持つ物は、組み込みで共通の形に寄せるかを決める」）。
3. 答えの鍵: `lib/planmarks.py` の `ANSWER_KEYS` に `means` を足す。`structure` の行は今の決まりのまま、答える先の鍵がちょうど 1 つ・`follows: true` か `deviation` のちょうど 1 つ（「follows は true だけ。外れは deviation に書く」も今のまま）。足すのは次の 2 つ。
   - 計画の役は推し（`recommend`）を書かない。推しは事前審査の役が書く（3.2 の 2。7 章の 2）。`structure` の行の形は今のまま `recommend` を持たない。
   - 鍵 `means` の外れの文（`deviation`）は承認ノードに字のまま載るので、人に聞く文の決まり（`workflows/.shared/prompts/plain-ask.md`・`lib/plainask.py`）で照らす。
   - 照らしの住処: 形の照らし（鍵・follows と deviation）は `planmarks._structure_row_problem`。外れの文の字の照らしは plan の `src/take.py` に置き、`plainask.gaps` を呼ぶ。
   - 同じ鍵の足しは、項目の行を見分ける欄 `converge._ROW_IDS`（`lib/converge.py:485`）にも要る。`ANSWER_KEYS` と一緒に `means` を足す（足さなければ `converge.sentences` が行の場所を見分けない）。
4. 答えの要る行の表: `lib/worldmark.py` に口 `means_need(means) -> planmarks.Need` を足す（means の欄の意味の住処が既にここ）。key は `means`、hints は `{M<n>: 文}`、of は空（項目に場所で結ばない。`worldmark.need` と同じ）、missing はどの項目も答えていない `M<n>`。plan の `src/take.py` の `accept` が組む表の並び（今は `design_need` と `worldmark.need`）に足す。means の無い周は表が空なので何も求めない。
   - 今の仕組みのまま付いてくる物: 往復をまたいだ答えの持ち越し（出し直しで直さない項目の `structure` は `converge.splice` が残す）と、案の直しで直した項目の新しい外れの拾い（`plan_errors` が `structure_gaps` を同じ表で呼ぶ）。
   - 形 replan の照らしの範囲（窓口の決め）: 世界の解の表も means の表も、「どの項目も答えていない」（missing）は、直した項目を差し替えた案の全体で数える。
     - 今の事実: `plan_errors`（`workflows/plan/src/take.py`）は `structure_gaps` を直した項目の返答（`reply["plan"]`）だけに当て、世界の解の表の missing もその中で数える。そのため、直さない項目だけが答えた世界の解の行を、答えていないと誤って拒みうる。この形を試す試験は無い（`tests/blocks/plan/test_steps.py:323` は表を空で渡す）。
     - 口の形: 行の照らし（鍵・follows と deviation・知らない id）は今のまま返答の項目に当て、missing だけを `_replaced(whole, rows, plan)` に当てる。
     - 世界の解の側の直しは不具合の直しとして、同じ実装の PR の中で別の commit にする。直しを外すと落ちる試験を先に置く（5 章の 3）。
5. 文: `planmarks` の `structure` の 1 行の文（`deviations` の行の文の口）に鍵 `means` の枝を足す（「頼みの解き方 M<n>」と呼ぶ）。誤りの文の「row か prescription か world のどれか 1 つ」も 4 つにする。
6. 指示（`workflows/plan/prompts/plan-writer.md`）: means が在る時だけの節「The request's means」を足し、機械が `M<n>: <文>` を並べる。頼みは次の 1 段: 頼みの解き方の 1 文ごとに、どれかの項目の `structure` に `{means: "M<n>", follows: true}` か `{means: "M<n>", deviation, recommend}` を書く。外れは、計画がその解き方を採らない時（独立設計・定石・リポジトリの決まりに合わせて外す時を含む）。外れの行は修正の前に人に聞くこと、`deviation` が承認ノードに字のまま載ること、推しは書かない（別の目が書く）ことを書く。出し直しの指示（`plan-writer-fix.md`）は拒まれた欄だけを返す今の形のまま。
7. 役の型と共通の形: `structure` の行の形の住処は `lib/plan-item-fields.schema.json:142`（`planmarks.FIELD_SCHEMA` がここから引き、`planmarks.gaps` が照らす。行は `additionalProperties: false`）。ここと、`works-factory-plan.yaml` の `&plan_reply` の `structure` の行の写しの両方に、鍵 `means`（字。`^M[1-9][0-9]*$`）を同じに足す（`tests/blocks/plan/test_shape.py` が両方の一致を縛る）。欄 `recommend` は足さない（3.1 の 3）。根の欄も足さない。

### 3.2 事前審査（plan-review の block。案 3-A の項目と 3-B）

1. 材料（`src/material.py`）: means が在る時、節「The request's means and the plan's answers」に `M<n>: <文> — plan: follows（項目 <i>）| departs（項目 <i>）— <deviation>` を並べる（答えは控えの欄 `structure` から読む）。
2. 推しの欄 `means_departs`（3-A の推し。窓口の決め）: 計画の `structure` の鍵 `means` の外れの行（follows でない答え）ごとに、事前審査の役が根の欄 `means_departs` の行 `{means: "M<n>", why, recommend}` を書く（`recommend` は `gatemarks.RECOMMEND_SHAPE`〔`{answer: continue|stop, note, why}`〕。計画のまま進めるなら continue・頼みどおりに直すべきなら stop）。形は `means_drifts` と同じ欄の形から引用の 2 つを除いた物。この段は形 plan と形 replan の両方に入れる（案の直しで直した項目の新しい外れにも推しが要る）。
   - 外れを選んだ役が自分で推しを書くと stop はほぼ出ず、無人の run では外れた側がいつも通り、決め means-ask の「どちらも自動では優先しない」が形だけになる。事前審査は `means_drifts` の推しを既に書くので、同じ別の目に書かせる。
3. 指示（`prompts/parts/design-ask.md`）に 1 段を足す（3-B）: 独立設計との食い違いのうち、計画の行が頼みの解き方のどれかに従う（`structure` の `{means, follows: true}`）所の食い違いは、`faces` の block にせず、新しい根の欄 `means_drifts` の行 `{means: "M<n>", design_quote, plan_quote, why, recommend}` に書く（`recommend` は `gatemarks.RECOMMEND_SHAPE`）。引用の決まりは今の design-ask と同じ（「」は独立設計と計画の行の字のまま）。計画が頼みの解き方から外れて独立設計に合わせた所は、計画の `deviation` の行が既に人に回すので、何も書かない。
   - 段を入れるのは形 plan だけ。形 replan（案の直しの事前審査）の指示には入れない（3.4 の 2）。今の条件の札 `design_stands`（`prompts/review.md:32`）は形 plan と replan の両方に入るので、形 plan で means が在る時だけ立つ新しい条件の札を `src/material.py` が渡す。
   - 2 往復目からの材料に、前の往復までに積んだ `means_drifts` の行を貼る。審査役は貼った行ごとに「残す」（同じ鍵 `(means, plan_quote)` の行を `means_drifts` に書き直す）か「取り下げる」（根の欄 `means_drifts_dropped` の行 `{means, plan_quote, why}`）のどちらかを答える。どちらにも無い貼った行は受け付けが拒む。これで、解けた食い違いの残りと、言い換えで黙って消える行の両方が閉じる。
4. 役の型: `means_drifts`・`means_drifts_dropped`・`means_departs` を、事前審査の役の型の 2 つ（単独の組の `review` と出し直しの `review-fix`。#832 のキャッシュのため同じ物を両方に書く）と、共通の形 `.shared/schemas/plan-review-reply.schema.json` に足す。木の形は 3.2 の 7。
5. 受け付け（`src/take.py`）が照らす（yes/no）。`means_departs`: 番号が計画の鍵 `means` の外れの行を指す・計画の外れの行の全部に行が在る・`recommend` の形（`gatemarks._recommend_gap`）・`why` と `recommend` の文が人に聞く文の決まりに合う（`plainask.gaps`）。`means_drifts`: 番号が範囲に在る・その番号を計画のどれかの項目が `follows: true` で答えている・`design_quote` が独立設計の字に、`plan_quote` が今の案の字に字のまま在る・`recommend` の形（`gatemarks._recommend_gap`）・`why` と `recommend` の文が人に聞く文の決まりに合う（`plainask.gaps`）。同じ食い違いを `faces` の頭 `design.DRIFT_HEAD`・`UNPAIRED_HEAD` の block にも書いた行（`means_drifts` の `plan_quote` と同じ引用を持つ block）は拒む（1 つの食い違いの住処を 1 つにする）。
   - 引用の照らしの口: `design.quote_gaps` は穴の `why` の「…」を照らす口で、`design_quote`・`plan_quote` の欄はそのまま渡せない。`lib/design.py` に欄の字を照らす口を足す。「今の案の字」は案の行の `design.ROW_QUOTE_KEYS` の欄で読む（`design.quote_gaps` と同じ読み方）。
6. 往復をまたぐ積み: 事前審査は 2 往復目から差分だけを比べる（`prompts/review.md`）ので、最後の往復の返答だけでは前の往復の `means_drifts` が消える（line の `scripts/plan_out.py` は最後の事前審査の `deviations` だけを運ぶ）。そこで往復の記録に積む。
   - 往復の行（`.shared/schemas/plan-converge.schema.json` の `passes[]`。閉じた形）に欄 `means_drifts` と `means_departs` を足し、書き手の `lib/converge.py` の `add_pass`（と line の `src/rounds.py` の `record_pass`）が受け付けた行を書く。
   - 鍵は `(means, plan_quote)`。次の 2 つを、この鍵で後勝ちに合わせる: 往復の記録の作業の写しに在る前の往復までの行（`src/steps.py:388-391` が写す `passes`）と、今の返答 `review` の `means_drifts`（`src/steps.py:579` で `gate.deviations` に渡る）。合わせなければ、最後の往復の `means_drifts` が外れの行から抜ける。取り下げた行（3.2 の 3）は合わせの後に落とす。`means_departs` も鍵 `means` で同じに積む。
   - `src/gate.py` は、積んだ全部の往復の行から外れの行を組む。そのうち `plan_quote` が今の案の字に無い行（計画が直して食い違いの元が消えた行）と、その番号を今の案が `follows: true` で答えていない行は落とす。
7. 木の形（項目ごとの下請け。`src/tree.py`）: 項目の下請けがその項目の分の `means_drifts` と `means_departs` を書く。
   - `item_schema` に欄 `means_drifts` と `means_departs`（3.2 の 2・3 と同じ行の形。必須にしない）を足す。今は `additionalProperties: False` なので、足さなければ拒まれる。
   - `check_item` が 3.2 の 5 の照らしを項目の答えに当てる（`plan_quote` はその項目の字に限る）。
   - `tree_merge` が開いた項目の答えの `means_drifts`・`means_departs` を並べて `review` の同じ名の欄にする（今は faces と shrink だけを拾い、ほかを捨てる）。
   - 相乗りの審査の下請け（`synergy_schema`）には足さない（項目をまたぐ食い違いは今どおり `faces`）。
   - 項目の下請けの指示に 3.2 の 2・3 の段を入れる。
8. 外れの行（`src/gate.py` の `deviations`）に `source: "means"` の行を足す。2 つの元:
   - 計画の `structure` の `{means, deviation}` の行。文は `修正案 <i> は頼みの解き方 M<n>「<文>」に従わない——<deviation>`。`mark` は `{decided_by: <deviation>, recommend: <積んだ means_departs の同じ番号の行の recommend>}`。
   - 積んだ `means_drifts` の行。文は `修正案は頼みの解き方 M<n>「<文>」に従うが、独立設計と食い違う——<why>`。`mark` は `{decided_by: <why>, recommend: <役の recommend>}`。
   - どちらも `why`（人に聞く訳）は「頼みの解き方と独立の目の食い違い（どちらも自動では優先しない。決め means-ask）」の 1 つ。世界の解の外れと違い、聞かずに通す道は無い（決めの 1）。
9. 返す事実の形: `deviations` の行の `source` の enum（`works-factory-plan-review.yaml` の出力の型。今は `[world, design]`）に `means` を足す。足さなければ `ports.returns` が `ShapeError` で拒む。行のほかの欄は世界の解の行と同じ（`item`・`text`・`mark`・`why`。`means_drifts` の行は `item` を持たない）。line の受け口（`works-factory-line.yaml` の `deviations` の型は `source` だけを名指し、enum を持たない）はそのまま。

### 3.3 修正の前の承認ノード（line と lib/gatemarks.py）

1. `lib/gatemarks.py` に種類 `MEANS_KIND = "means"` と、項目の種類の名の表（`WORLD_KIND` と並ぶ所）に「頼みの解き方と独立の目が食い違う修正案の項目」を足す。
2. `workflows/line/src/gates.py` の `before_fix`: `deviations` の `source == "means"` の行を項目にする。文は `text` に `（人に聞く訳: <why>）` と推しの尾 `gatemarks._push(mark)` だけを付けて組む。`gates._item` は使わない（`gatemarks.FIELDS` に `decided_by` が在るので、`_item` が呼ぶ `gatemarks._world` が「（世界の解: 役が書いていない）」の尾を付けてしまう）。前に continue で通した同じ文の行は聞き直さない（`_continued`）。軸の行（`gather`）には足さない（外れの住処はこの項目の 1 つ）。
3. 無人の run: 今の `passage(texts, row_push)` がこの項目の推しの尾を読む。項目の全部が通す推しを持てば推しで抜け、採った推しは `answer.PUSHED` で記録に残る（決めの 2）。推しが stop か読めない時は止まる。新しい分岐は足さない。
4. 人の答えの届く先: 修正の前の承認ノードの答えは、独立設計には届かない（独立設計に届くのは始めの承認ノード `answer-start` の答えだけ。`works-factory-line.yaml` の 225 行と 608 行の `answers: "$answer-start.output.answer"`）。R2 は承認ノードの答えを `design.human_answers` で受け、聞いた文 `asked` は写さない。PR 2 の R2 の `request_conflicts` は、この答えに加えて、承認ノードに出なかった頼みどおりの違い（計画の審査を素通りした所）を受ける。
5. 案の直し（`ask-replan`）: 聞く行を組むのは `workflows/line/scripts/ask_replan.py` の `ask`（`gates.replan_asks` ではない）。`ask_replan.py:32` の `REVIEW`（案の直しの事前審査 `replan-review` の出力から拾う欄）に `deviations` を足し、`ask` が、その `deviations` のうち `source == "means"` で直した項目（`replan` の行の `item`）の行を聞く行に足す（形 replan の照らしが拾った新しい外れを人に見せる。3.1 の 4）。直さない項目の行は修正の前の承認ノードで答え済みなので足さない。直した項目でも、外れの文が前と同じで修正の前の承認ノードが continue で通した行は聞き直さない（`gates._continued`）。

### 3.4 足さない物

1. 独立設計の block（`workflows/independent-design/`）は変えない。
2. 形 replan の事前審査には 3-B の段（`means_drifts`）を入れない（推しの段 `means_departs` は入れる。3.2 の 2）。案の直しは裁かれた項目だけを直す狭い直しで、独立設計との食い違いは修正の前の承認ノードで答え済みのため。直した項目の頼みの解き方からの新しい外れは、3-A の答え（3.1 の 4）と 3.3 の 5 で拾う。
3. 世界の解の行・関所の軸（`worldmark.world_ok`）は変えない。世界の解の外れと頼みの解き方の外れが同じ計画の項目で重なっても、項目は別々に出る（問いが違う: 定石と比べてか、頼みと比べてか）。
4. 新しい置き場・層・常駐の仕組みは足さない。足す形のファイルは、寄せた `.shared/schemas/stated-means.schema.json` の 1 つ（消す 2 つと引き換え）。

## 4 触るファイル

- `docs/owner-decisions.md`: 決め `means-ask`（この PR で書いた）。
- 形の寄せ（7 章の 4）:
  - `workflows/.shared/schemas/stated-means.schema.json`（足す）・`workflows/world/schemas/means.schema.json`・`workflows/plan-review/schemas/stated-means.schema.json`（消す）。
  - 読む口: world の `src/steps.py`・`works-factory-world.yaml`、plan-review の `src/steps.py`・`works-factory-plan-review.yaml`。
  - 形の一覧と設計書: `workflows/.shared/AGENTS.md` の形の一覧に `stated-means.schema.json` を足す。`docs/design/world.md` の 26 行（port `means` の form）と 64 行（形の置き場）、`docs/design/plan-review.md` の 45 行（port `means` の form）・163 行（形の置き場）・846 行（19 の「この block の `schemas/` に置く」）を `shared:` に直す。
  - `tests/blocks/shared/test_ports.py` の `test_schema_is_read_from_the_caller_block` の docstring と例（`means.schema.json` を block の形の例に使っている。block に残る別の形に替える）。
- `lib/plan-item-fields.schema.json`（`structure` の行の鍵 `means`）・`workflows/.shared/schemas/plan-review-reply.schema.json`（`means_drifts`・`means_drifts_dropped`・`means_departs`）・`plan-converge.schema.json`（`passes[]` の `means_drifts`）。
- `lib/planmarks.py`（`ANSWER_KEYS`・`_structure_row_problem`・行の文 `answer_line`）・`lib/worldmark.py`（`means_need`）・`lib/gatemarks.py`（`MEANS_KIND`）・`lib/converge.py`（`_ROW_IDS` に `means`・`add_pass` の `means_drifts` と `means_departs`）・`lib/design.py`（`means_drifts` の引用の欄を照らす口）と `lib/tests/` の試験。
- structure: `src/survey.py:155`（`planmarks.deviations` の読み手）の外れの行の文に、`answer_line` の means の枝を足す。
- plan: `works-factory-plan.yaml`（port `means`・`&plan_reply` の `structure` の行の写し）・`prompts/plan-writer.md`・`src/steps.py`（port と指示の値）・`src/take.py`（表に `means_need`・外れの文の字の照らし・形 replan の missing の範囲〔世界の解の表の直しは別の commit〕）・fixtures。
- plan-review: `works-factory-plan-review.yaml`（役の型 `review` と `review-fix` の両方に `means_drifts`・`means_drifts_dropped`・`means_departs`・出力の `deviations` の `source` の enum に `means`）・`prompts/parts/design-ask.md`（`means_drifts` の段）と `means_departs` の段の置き場・`prompts/review.md`（新しい条件の札）・`src/material.py`（札・前の往復の `means_drifts` の貼り）・`src/steps.py`（積みの合わせ）・`src/take.py`・`src/tree.py`（`item_schema`・`check_item`・`tree_merge`・項目の下請けの指示の値）・`src/gate.py`・fixtures。
- line: `works-factory-line.yaml`（node `plan`〔`plan-rounds` の中〕と `replan` の include に `means`）・`src/gates.py`（`before_fix`）・`scripts/ask_replan.py`（`REVIEW` に `deviations`・`ask` の聞く行）・`src/rounds.py`（`record_pass` の `means_drifts` と `means_departs`）。
- 設計書: `docs/design/plan.md`・`docs/design/plan-review.md`・`docs/design/line.md` の該当の節。

## 5 試験（直しを外すと落ちる物を先に置く）

1. `lib/tests/test_plan_fields.py`（`structure_gaps` の試験の今の置き場）: means 2 文の表で、`M1` にだけ答えた案を拒み、2 文に答えれば通る。`{means: M1, follows: false}` を今の文「follows は true だけ」で拒む。`{means, deviation, recommend}` を型で拒む（推しは計画の役が書かない）。means の無い表では何も求めない。
2. `lib/tests/test_worldmark.py`: `means_need` の hints と missing。
3. `tests/blocks/plan/`: means 2 文の周の受け付けが、答えの欠けと、外れの文に run の中の参照（`<パス>:<行>`）を持つ行を拒む。通った答えが `p2.fix_plan.json` の `structure` に残る。形 replan で、直した項目が `M1` から外れる答えを書けば通り、直さない項目の `M2` の答えは承認済みの案から数える。世界の解の表も同じ: 直さない項目だけが答えた世界の解の行を持つ表で `plan_errors` が拒まない（今のコードで落ちる試験を、世界の解の直しの commit の前に置く。`tests/blocks/plan/test_steps.py` の `plan_errors` の試験の並び）。
4. `tests/blocks/plan_review/test_gate.py`: `{means, deviation}` の行と同じ番号の `means_departs` の行が、`deviations` の `source: means` の行になり、`mark` に `means_departs` の `recommend` を持つ。`follows: true` だけなら行は出ない。出力の型が `source: means` を通す（`ports.returns`）。
5. `tests/blocks/plan_review/`: `means_drifts` の照らし（番号が `follows: true` の答えを指さない・引用が無い・同じ食い違いを block にも書いた・前の往復の貼った行に「残す」も「取り下げる」も無い、をそれぞれ拒む）。`means_departs` の照らし（計画の外れの行に推しが無い・番号が外れの行を指さない、を拒む）。1 往復目の `means_drifts` が、2 往復目で「残す」と答えれば `deviations` に残り、取り下げるか `plan_quote` が案から消えれば落ちる。1 往復で抜けた run（往復の記録の行が無く、今の返答だけに `means_drifts` が在る）の `means_drifts` が `deviations` に在る。木の形で、項目の下請けの `means_drifts` が `item_schema` を通り、`tree_merge` の後の返答に在る。design-ask の指示に `means_drifts` の段が在り、形 replan の指示に無い。`means_departs` の段は両方の形に在る（指示の字の試験の今の形で）。
6. `tests/blocks/line/`: `before_fix` が `source: means` の行を種類 `means` の項目にし、文に「世界の解:」の尾が無い。無人の run が推しで抜けて `pushed` に残る。推しが stop なら止まる。`ask_replan.ask` が直した項目の `source: means` の行を聞き、直さない項目の行と、前に continue で通した同じ文の行を聞かない。
7. 指示の組み立ての既存の試験（`tests/workflows/` の指示の比べの JSON）を、足した節の分だけ更新する。

試験は `uv run --isolated python3 tests/changed.py` だけ。本物の Claude と Archon の run は起こさない。

## 6 PR 2（案 1-A）との境

- PR 2 は R2 の比べ役（`workflows/r2/prompts/r2-compare.md`）に port `means` を足し、違いのうち差分が頼みの解き方どおりの物を `request_conflicts` に出して `status` に数えない（形は R4 の `policy_conflicts` と同じ。字は機械が照らす）。並ぶ PR #969（r2 の結末の名を絞る）が r2 の指示と結果の名を触るので、#969 が main に入った後に作る。
- この PR 1 の `structure` の `means` の答えは PR 2 の入力にしない（R2 は修正の後の差分を頼みと比べる。計画の答えではない）。

## 7 決めた細目と、窓口に見てほしい所

1. 案の直し（形 replan）: 答えは `structure` の行なので、直さない項目の答えは承認済みの案の項目と一緒に持ち越す（`take_replan` は承認済みの案の全体を写して直した項目だけを差し替える）。直した項目の答えは `plan_errors` が同じ表で照らし、新しい外れは `ask-replan` が聞く（3.3 の 5）。3-B の段は形 replan に入れない（3.4 の 2）。
2. 計画の外れの推しは、事前審査の役（別の目）が `means_departs` の行ごとに `recommend` に書く（2 回目の審査の案 2。窓口の決め）。計画の役は外れの訳（`deviation`）だけを書き、推しは書かない。外れを選んだ役が自分で推しを書くと stop はほぼ出ず、無人の run では外れた側がいつも通り、決めの 1「どちらも自動では優先しない」が形だけになるため。事前審査は `means_drifts` の推しを既に書くので、同じ欄の形で書かせる。形は `gatemarks._recommend_gap`、字は人に聞く文の決まりで照らす。機械は推しを作らない（決め `unattended`・line の設計書の L-G24・`gates.passage`）はそのまま守る。審査役が continue を書けば無人の run は計画のまま進み、stop を書けば止まる。初めの下書きの「機械が決まった文で continue を作る」も、1 回目の直しの「計画の役が推しを書く」も、同じ訳で採らない。人が頼みどおりを選んだ時の計画の直しは、承認ノードの一言での修正役への指示になる。これは世界の解の外れと同じ限りで、この PR では広げない。
3. `means_drifts` を `faces` の suggest でなく別の欄にしたのは、`faces` の suggest は開いた項目で次の往復の答えを求める（`converge.owed_faces`）ため。頼みどおりの食い違いは計画の役でなく人が答える問いなので、計画の役に答えを求めない。往復をまたいで消えないよう、往復の行には積む（3.2 の 6）。2 往復目からは審査役に貼った行を残すか取り下げるかを答えさせる（3.2 の 3）が、計画の役には答えを求めない。
4. 形 `stated-means.schema.json` を `workflows/.shared/schemas/` に寄せ、world と plan-review の写しを消す（3.1 の 2。寄せに要る直しは 4 章）。
5. 3-A の答えを根の欄 `means_answers` でなく `structure` の鍵 `means` にした（初めの下書きからの替え）。今の仕組み（`Need`・`structure_gaps`・`worldmark.need`）で照らせ、どの項目が従うかが分かり（3-B の照らしに要る）、往復の持ち越し（`converge.splice`）と案の直しの新しい外れの拾い（`plan_errors`）も付いてくる。`follows: false` を使わずに済み、今の決まり「follows は true だけ。外れは deviation に書く」とも合う。
