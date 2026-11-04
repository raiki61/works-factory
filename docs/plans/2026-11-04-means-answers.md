<!-- coldwrite:skip 設計の下書き。語は 0 章と docs/design/README.md の頭の語の一覧で定義 -->
# 頼みの解き方と独立設計が食い違う時に、修正の前の承認ノードで人に聞く設計の下書き（受付 20261104-111958-4c5bdc。PR 1 = 案 3-A・3-B）

## 冒頭

- 何の話か: 頼みがはっきり指定した解き方（means）と、目的の 1 文だけから作った独立設計が食い違うと、今は独立設計の側が黙って勝つ。勝たせているのは計画の事前審査（plan-review の design-ask）と、修正の後の R2。持ち主は「どちらも自動では優先せず、推しつきの問いにして修正の前の承認ノードに出す。無人の run は推しを採って記録する」を選んだ（2026-11-04「おしで」。決め `means-ask`）。
- 一言で: 計画の役に、頼みの解き方の 1 文ごとの答え `means_answers`（`{means, follows, why}`）を書かせ、受け付けが全部の文への答えを照らす。従わない文と、計画が頼みどおりなのに独立設計と食い違う所（事前審査の新しい欄 `means_drifts`）を、修正の前の承認ノードの新しい種類の項目「頼みの解き方」にする。道は世界の解の外れ（`deviations` の `source: world`）と同じで、違いは項目が推しの尾を持つこと（無人の run が推しで抜ける）。
- 範囲: この PR 1 は案 3-A と 3-B。R2 の比べ役の `request_conflicts`（案 1-A）は PR 2 で、並ぶ PR #969 が main に入った後に作る（6 章）。独立設計には means を渡さない（今のまま）。
- 読む人: 窓口は 1 章（E11）・2 章（決め）・5 章（試験）。実装の部署は 3 章と 4 章から。

## 0 語

- 頼みの解き方（means）: 目的の役が目的の文から外して足し欄 `means` に 1 文ずつ並べた物（`lib/worldmark.py` の「依頼の解き方」の節）。line は `$judge.output.means` で運ぶ。番号は並びの順の 1 始まりで、指示では `M1`・`M2`… と書く。
- 修正の前の承認ノード: line の `gate-before-fix`（項目は `workflows/line/src/gates.py` の `before_fix` が組む）。
- 世界の解の外れの道: 計画の項目の欄 `structure` の `{world, deviation}` → 事前審査の `deviations`（`workflows/plan-review/src/gate.py` の `world_items`）→ line の `before_fix` が種類 `gatemarks.WORLD_KIND` の項目にする。

## 1 E11 の 3 つの答え

1. Archon が持っているか → 持っていない。Archon の承認ノード（`interactive`）は問いを出す口だけで、頼みの指定と別の目の食い違いを見分ける物は無い（`docs/design/archon.md`）。
2. ASF が持っているか → 持っていない。ASF の `.archon/workflows/sdlc/` の計画と審査の役は、頼みの文を前提に置くだけで、独立の設計と突き合わせる段が無い（`docs/asf-notes.md` にも該当の型は無い）。
3. 本当に要るか → 要る。keep-essence の 9（独立設計と R1〜R4。目的だけから作る独立を保つ）と 12（世界の解。頼みの解き方を疑い、外れる時は人に聞く）の間の抜け。世界の解の関所は「計画が定石から外れる時」だけ人に聞くので、頼みの解き方が定石と同じ（`versus.verdict: same`）でも独立設計が別の形を推すと、計画は独立設計に合わせて頼みから外れ、誰にも見せずに通る（調べの 3 の run の `pr-unit-diverges-from-closer`）。足す物は新しい仕組みでなく、今の世界の解の外れの道に種類を 1 つ足す形にする。

## 2 決め（`docs/owner-decisions.md` の `means-ask` に書いた）

1. 頼みの解き方と独立設計（とそれに合わせた計画）が食い違う時、どちらも自動では優先しない。修正の前の承認ノードに推しつきの項目で出す。
2. 無人の run では推しを採って進み、採った推しを記録する（今の `answer.PUSHED` の道。報告の冒頭と次の依頼の下書きに載る）。
3. `think`（持ち主の言葉も鵜呑みにしない）は変えない。計画の役が頼みの解き方を疑って外れるのは今どおりで、外れを人が見るようになる。
4. 独立設計には means を渡さない（`purpose.md` の「同じ解き方の枠に落ちる」を避ける今の形のまま）。

## 3 仕組み

### 3.1 計画（plan の block。案 3-A）

1. port `means` を足す（`json(shared:stated-means.schema.json)`。既定 `[]`）。line の `plan-rounds` と設計の相談の往復の `include: works-factory-plan` に `means: "$judge.output.means"` を渡す。形 replan（案の直し）には渡さない（7 章の 1）。
2. 形の住処を寄せる: 同じ中身の形が world（`means.schema.json`）・plan-review（`stated-means.schema.json`）・plan の 3 つになるので、`workflows/.shared/schemas/stated-means.schema.json` に 1 つにし、2 つの block の写しを消して `shared:` で読む（plan-review の設計書 19 の「2 つ以上の block が同じ中身を持つ物は、組み込みで共通の形に寄せるかを決める」）。
3. 指示（`workflows/plan/prompts/plan-writer.md`）: means が在る時だけの節「The request's means」を足し、機械が `M<n>: <文>` を並べる。頼みは次の 1 段: 文ごとに `means_answers` の行 `{means: <n>, follows: true|false, why: <20 字以上>}` を書く。`follows: false` は、計画がその解き方を採らない時（独立設計・定石・リポジトリの決まりに合わせて外す時を含む）。`why` は外れなら外れる訳と出どころ、従うなら従う訳。外れの行は修正の前に人に聞くことと、`why` が承認ノードの推しの訳に字のまま載ることを書く。出し直しの指示（`plan-writer-fix.md`）は拒まれた欄だけを返す今の形のまま。
4. 役の型（`works-factory-plan.yaml` の `&plan_reply`）と共通の形（`.shared/schemas/fix-plan.schema.json`）に根の欄 `means_answers` を足す（`required` には入れない。means の無い run が書かずに済むように。要るかは受け付けが見る）。
5. 受け付け（`workflows/plan/src/take.py`）: means が 1 文以上の周で、次のどれかなら拒む（理由を全部 1 回で並べる今の形）。
   - 番号 1〜n のどれかに答えが無い。
   - 範囲の外の番号・同じ番号が 2 行。
   - `follows` が真偽でない・`why` が 20 字に足りない。
   means の無い周の `means_answers` は拒まずに捨てる。通った `means_answers` は修正案の返答（`p2.fix_plan.json`）に残す（事前審査が `proposal` の pointer で読む）。照らしの住処は `lib/worldmark.py` の新しい口 `means_gaps(answers, means)` にする（means の欄の意味の住処が既にここ。plan と plan-review の 2 つの block が読む）。

### 3.2 事前審査（plan-review の block。案 3-A の項目と 3-B）

1. 材料（`src/material.py`）: means が在る時、節「The request's means and the plan's answers」に `M<n>: <文> — plan: follows|departs — <why>` を並べる。
2. 指示（`prompts/parts/design-ask.md`）に 1 段を足す（3-B）: 独立設計との食い違いのうち、計画の行が頼みの解き方のどれかに従う（`means_answers` の `follows: true`）所の食い違いは、`faces` の block にせず、新しい根の欄 `means_drifts` の行 `{means: <n>, design_quote, plan_quote, why, recommend}` に書く（`recommend` は今の `gatemarks.RECOMMEND_SHAPE`）。引用の決まりは今の design-ask と同じ（「」は独立設計と計画の行の字のまま）。計画が頼みの解き方から外れて独立設計に合わせた所は、計画の `follows: false` が既に人に回すので、何も書かない。
3. 受け付け（`src/take.py`）が `means_drifts` を照らす（yes/no）: 番号が範囲に在る・その番号の計画の答えが `follows: true`・引用が字のまま在る（`design.quote_gaps` の照らしを使う）・`recommend` の形（`gatemarks.recommend_gaps`）。同じ食い違いを `faces` の頭 `design.DRIFT_HEAD`・`UNPAIRED_HEAD` の block にも書いた行（`means_drifts` の `plan_quote` と同じ引用を持つ block）は拒む（1 つの食い違いの住処を 1 つにする）。
4. 外れの行（`src/gate.py` の `deviations`）に `source: "means"` の行を足す。2 つの元:
   - 計画の `means_answers` の `follows: false` の行。文は `頼みの解き方 M<n>「<文>」: 修正案は従わない——<why>`、推しは `{answer: continue, note: 修正案のまま M<n> から外れて進める, why: <計画の why>}`。
   - `means_drifts` の行。文は `頼みの解き方 M<n>「<文>」: 修正案は従うが独立設計と食い違う——<why>`、推しは役の `recommend`。
   どちらも `mark` に `decided_by`（計画の why か役の why）と `recommend` を置き、`why`（人に聞く訳）は「頼みの解き方と独立の目の食い違い（どちらも自動では優先しない。決め means-ask）」の 1 つ。世界の解の外れと違い、聞かずに通す道は無い（決めの 1）。
5. 返す事実の形（`deviations` の行 `{source, ...}`）は変えない。line の受け口（`works-factory-line.yaml` の `deviations` の型は `source` だけを名指す）もそのまま。

### 3.3 修正の前の承認ノード（line と lib/gatemarks.py）

1. `lib/gatemarks.py` に種類 `MEANS_KIND = "means"` と、項目の種類の名の表（`WORLD_KIND` と並ぶ所）に「頼みの解き方と独立の目が食い違う修正案の項目」を足す。
2. `workflows/line/src/gates.py` の `before_fix`: `deviations` の `source == "means"` の行を、世界の解の行と同じ形で項目にする（文に `（人に聞く訳: …）` と、`gates._item` の推しの尾 `gatemarks._push(mark)` を付ける）。前に continue で通した同じ文の行は聞き直さない（`_continued`）。軸の行（`gather`）には足さない（外れの住処はこの項目の 1 つ）。
3. 無人の run: 今の `passage(texts, row_push)` がこの項目の推しの尾を読む。項目の全部が通す推しを持てば推しで抜け、採った推しは `answer.PUSHED` で記録に残る（決めの 2）。新しい分岐は足さない。
4. 人の答えは、今の承認ノードの答えとして独立設計と R2 の前提の節「Answers at the approval nodes」（`workflows/.shared/prompts/design-premises.md`）に届く。PR 2 の R2 の `request_conflicts` は、この答えに加えて、承認ノードに出なかった頼みどおりの違い（計画の審査を素通りした所）を受ける。

### 3.4 足さない物

- 独立設計の block（`workflows/independent-design/`）は変えない。
- 世界の解の行・関所の軸（`worldmark.world_ok`）は変えない。世界の解の外れと頼みの解き方の外れが同じ計画の行で重なっても、項目は別々に出る（問いが違う: 定石と比べてか、頼みと比べてか）。
- 新しい置き場・層・常駐の仕組みは足さない。足す形のファイルは、寄せた `.shared/schemas/stated-means.schema.json` の 1 つ（消す 2 つと引き換え）。

## 4 触るファイル

- `docs/owner-decisions.md`: 決め `means-ask`（この PR で書いた）。
- `workflows/.shared/schemas/stated-means.schema.json`（足す）・`workflows/world/schemas/means.schema.json`・`workflows/plan-review/schemas/stated-means.schema.json`（消す）と、読む口の `world` の `src/steps.py`・`works-factory-world.yaml`・plan-review の `src/steps.py`・`works-factory-plan-review.yaml`。
- `workflows/.shared/schemas/fix-plan.schema.json`。
- `lib/worldmark.py`（`means_gaps`）・`lib/gatemarks.py`（`MEANS_KIND`）と `lib/tests/` の試験。
- plan: `works-factory-plan.yaml`・`prompts/plan-writer.md`・`src/steps.py`（port と指示の値）・`src/take.py`・fixtures。
- plan-review: `works-factory-plan-review.yaml`（役の型に `means_drifts`）・`prompts/parts/design-ask.md`・`src/material.py`・`src/take.py`・`src/gate.py`・fixtures。
- line: `works-factory-line.yaml`（plan の include 2 か所に `means`）・`src/gates.py`。
- 設計書: `docs/design/plan.md`・`docs/design/plan-review.md`・`docs/design/line.md` の該当の節。

## 5 試験（直しを外すと落ちる物を先に置く）

1. `tests/blocks/plan/`: means 2 文の周で、`means_answers` が 1 文だけの返答を受け付けが拒む。2 文に答えれば通り、`p2.fix_plan.json` に残る。means の無い周は欄が無くても通る。
2. `lib/tests/test_worldmark.py`: `means_gaps` の欠け・範囲の外・重なり・短い why。
3. `tests/blocks/plan_review/test_gate.py`: `follows: false` の行が `deviations` の `source: means` の行になり、推しの尾の材料（`recommend`）を持つ。`follows: true` だけなら行は出ない。
4. `tests/blocks/plan_review/`: `means_drifts` の行の照らし（番号が `follows: false` を指す・引用が無い・同じ食い違いを block にも書いた、をそれぞれ拒む）と、通った行が `deviations` に出ること。design-ask の指示に `means_drifts` の段が在る（指示の字の試験の今の形で）。
5. `tests/blocks/line/`: `before_fix` が `source: means` の行を種類 `means` の項目にし、無人の run が推しで抜けて `pushed` に残る。推しが stop なら止まる。
6. 指示の組み立ての既存の試験（`tests/workflows/` の指示の比べの JSON）を、足した節の分だけ更新する。

試験は `uv run --isolated python3 tests/changed.py` だけ。本物の Claude と Archon の run は起こさない。

## 6 PR 2（案 1-A）との境

- PR 2 は R2 の比べ役（`workflows/r2/prompts/r2-compare.md`）に port `means` を足し、違いのうち差分が頼みの解き方どおりの物を `request_conflicts` に出して `status` に数えない（形は R4 の `policy_conflicts` と同じ。字は機械が照らす）。並ぶ PR #969（r2 の結末の名を絞る）が r2 の指示と結果の名を触るので、#969 が main に入った後に作る。
- この PR 1 の `means_answers` は PR 2 の入力にしない（R2 は修正の後の差分を頼みと比べる。計画の答えではない）。

## 7 決めた細目と、窓口に見てほしい所

1. 形 replan（修正の段が計画の項目の誤りを申し出て、裁かれた項目だけ直す案の直し）では `means_answers` を求めない。承認済みの案の答えを持ち越す（承認ノードが人の決定を聞き直さない `decision-records` の向き）。直した項目が頼みの解き方から新しく外れる場合は拾えない。拾うなら replan にも port を渡す（推しは今の範囲のまま）。
2. 計画の外れの推しは continue（計画のまま）にした。推しの訳は計画の役の why。逆の推し（頼みどおりに直させる）は、承認ノードの continue の一言で修正役へ渡る（今の世界の解の外れの答えと同じ）。修正の前の承認ノードに「計画を直す」語は無いので、人が頼みどおりを選んだ時の計画の直しは、一言での修正役への指示になる。これは世界の解の外れと同じ限りで、この PR では広げない。
3. `means_drifts` を `faces` の suggest でなく別の欄にしたのは、`faces` の suggest は開いた項目で次の往復の答えを求める（`converge.owed_faces`）ため。頼みどおりの食い違いは計画の役でなく人が答える問いなので、往復の記録に入れない。
