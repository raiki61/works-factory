# block の設計書: delta-review（差分の審査と手直し）

- 何の話か: 修正の直後に、修正だけの差分を読むだけの審査役に見せて修正が新しく作った穴を挙げさせ、書く役に同じ周のうちに直させる（審査と手直しを 2 往復まで）観点を、単独で呼べる block `blocks/delta-review/` にする設計。型は [README.md](README.md)、形は手本の [world.md](world.md) に従う。
- 決めたこと: 今の fix の中の 12 の node（delta-cut・delta-loop・refix-loop・review2-loop・refix2-loop とその中身）を、AI の node 4 つ（review-1・refix-1・review-2・refix-2）と script の node の block にする。深さで審査を省くか・戻せない組が在るか・変更の確かめが通ったかは line の `when:` に移し、差分が空で検算する物も無い時だけ block が自分で審査を飛ばす。入力は README の 3 つ（`base`・`plan`・`lens_rows`）に、修正役の返答・テストの変更の許し・事前審査の返答・方針・依頼・言語を足した 9 つ。修正の段の値は、fix の設計書が決めた fix の返りの欄（`start_tree`・`scope`・`reply`・`allowed_tests`）をそのまま受ける。指示は 4 本の英語の md と block の中の断片 2 本にし、Python が持っていた決まった文（範囲の節の頭・座の頭・始めの記録の 2 行・言語の行）は md へ出す。書く役の決まりの正本（今の `fix-rules/common.md`）は fix と共に使うので共通の断片 `writer-rules` にする。受け付けの照らしと書く順は今のまま。
- 持ち主に求めること: 1 つ。書く役の決まりの正本の置き場を、下の 2 案のどちらに揃えるか（2 つの block の PR を入れる前に）。ほかは無い。読み手は、この block を作る実装の役と、その PR の審査。fix の設計書（README の 11.1 の作る順の 3 波目。この block と同時に作る）と食い違う所が 1 つ在る: 書く役の決まりの正本を、この設計書は共通の断片 `writer-rules` に、fix の設計書は fix の中の断片に置く。13 節の 1 つ目に置いた（どちらかに揃えるまで、両方の PR を入れない）。

この文書の語は README の頭の物を使う。ほかに:

- line: 工場のメイングラフ（README の 8.7）。block を並べ、どの block をいつ回すか（`when:`）と、渡す値（`with:`）を決める。
- 深さ: run と直す単位ごとの厚み。軽量・標準・重厚の段がある。run の頭の深さ（頭）は run の始めに決まり、単位ごとの深さは修正案が決める。上げ直し: 修正の後の信号（食い違いの申し出・止めた単位など）で、軽量の単位を標準に上げること（今は fix の中、新しい形は line が fix と差分の審査の間で 1 回行う）。頭が軽量で上げ直しの後も全部の単位が軽量の run は、差分の審査を省く（持ち主の決め `dynamic-depth`）。
- 戻せない組: 修正を組ごとに子の run で直して親の作業ツリーへ戻す時に、戻せず当たったままになった組。作業ツリーが信用できないので、在れば先へ進まない。
- 案の直し: 修正の段の裁定が「修正案の項目が誤り」とした時に、同じ run の中で修正案を直して 2 度目の修正の段を回すこと。
- 今: 作り直す前の、今動いている工場（`workflows/fix/` と `lib/`）。元の works: 工場の移植元（README の頭の語）。graphloops: 工場の形の元。
- 審査役（review-1・review-2）: 修正（2 回目は手直し）だけの差分と作業ツリーの今の姿を読み、修正が新しく作った穴（faces）と、塞いだと言われた穴の検算（checks）を返す AI の役。読むだけ（Read・Grep・Glob）。1 回目は承認済みの修正案の項目への準拠（compliance）と品質（quality）の 2 判定も返す。
- 手直しの役（refix-1・refix-2）: 審査が挙げた穴と塞がっていなかった検算（義務 owed）の全部に 1 度ずつ、直す（fixed）か残す（declared）かで答え、直す AI の役。作業ツリーを書く（Edit・Write・Bash）。
- 往復: 審査 1 回と手直し 1 回の組。1 往復目は修正の差分、2 往復目は 1 回目の手直しだけの差分を見る。3 往復目は無い（今と同じ）。
- 義務（owed）: 手直しが答える行 `{key, from, text}`。審査の穴の全部と、検算で `closed: false` の行。
- 機械の穴: 受け付けが、その往復の差分の足した行に見つけた works の内側の語（`lib/report.py` の `INNER_WORD`）の穴。`kind` は `inner_word`。審査役の穴の後ろに機械が足し、義務になる。
- 名札（ties）: 義務の穴ごとに、機械が修正案のどの項目（枝）の直しから出たかを結んだ印（`lib/holeties.py`）。
- 座: 借りた superpowers の部品を役に載せる節（`lib/seat.py`）。審査役には型 `task-review`（superpowers の task-reviewer の写し）、手直しの役にはスキル `receiving-code-review`。
- 範囲の欄: 承認済みの修正案の項目に、範囲の相談の合意のパスと裁定で外れた印（`held`・`held_units`）を足した並び `plan_items` と、直す裁定が足したパス `ruled_paths`・相談の合意の行 `agreed` の組（今の `fixboard.scope_brief` の返り）。作り手は修正の block（その返りの `scope`）で、この block は port `plan` で受ける。
- 例の run: 本物の run `fed2db95-cb8e-41ff-913b-92c056872040`（対象は工場自身のリポジトリ。置き場は `<run の置き場>/fix/fix/`）。1 往復目の審査が穴 3 件と塞がっていない検算 1 件（義務 4）を出し、手直しが 1 件を直し 3 件を残し、2 往復目の審査が穴 0 件で通った。2 回目の手直しは走っていない。骨組みの値はここから取った。

## 1 block の全体

### 1.1 役

修正だけの差分（修正の前の版から今の作業ツリーまで。未追跡の新しいファイルも入れ、Archon の写しの置き場 `.archon/` の下は除く）を読むだけの審査役に見せ、修正が足した物の写し・塞がない入口・宣言と実装のずれ（と、届かない道・頼まれていない広げ）を穴として挙げさせ、修正役が塞いだと言った事前審査の穴を 1 件ずつ検算させる。1 往復目は、承認済みの修正案の項目どおりに直したか（準拠）と品質を、行から決まる判定の語で書かせる。穴と塞がっていない検算を義務にし、書く役に同じ周のうちに全部 1 度ずつ答えさせる。直したと答えた穴が在れば、手直しだけの差分に 2 回目の審査を当て、残りをもう 1 度手直しさせる。手直しの変更は、承認済みの修正案の範囲・書き込みの記録と申告で機械が照らす。修正が作った穴を次の周まで持ち越さないための block（今の `commands/delta-review.md` の「実測 2026-09-24: 3 周目の指摘のうち 8 件が 2 周目の修正の産物」）。

### 1.2 port

入力（YAML の `inputs:`）:

- `base`（必須）: `text: 修正の前の作業ツリーの姿の git の版（木か commit の sha）。差分はこの版から今の作業ツリーまでを切る`
- `plan`: `file: 範囲の欄の JSON のファイル {plan_items, ruled_paths, agreed}（plan_items は承認済みの修正案の項目〔lib/planmarks.py の approved_items の行の形 {item, unit_keys, approach, files, tests, rewrite_tests, allowed_paths, out_of_scope, …}〕に範囲の相談の合意と裁定で外れた印 held・held_units を足した並び）。項目の並びだけの配列でもよい（合意と裁定が無い）。空は修正案の無い run`。既定 `""`。
- `lens_rows`: `file: 修正の差分に当てたレンズの行（lib/lens.py の控えの形 {rows: [{lens, agent, go, reason, state, findings, dropped}]}）の JSON のファイル。空はレンズを走らせていない run`。既定 `""`。
- `fix_reply`: `json(fix-reply.schema.json): 修正役が受け付けられた返答をまとめた {changes, not_done, plan_faces}。plan_faces の absorbed の行が、審査の検算する穴。null は直す返答が無い`。既定 `null`。
- `permits`: `json(permits.schema.json): テストの変更の許しの行 [{path, permit, source}]（パスの字の配列でもよい）。手直しの範囲の照らしで、項目の範囲の外でも変えてよいパスになる。空の配列は許しが無い`。既定 `[]`。
- `plan_review`: `json(plan-review.schema.json): 事前審査の返答（faces・shrink を持つ object）。null は事前審査の無い run`。既定 `null`。
- `policy`: `file: 人が run に固めた方針の文書。空は方針の文書が無い`。既定 `""`。
- `request`: `json(shared:request.schema.json): 依頼の行の配列か、それを findings の欄に持つオブジェクト。手直しの役が先に全部読む。空の配列は依頼の文が無い`。既定 `[]`。
- `lang`: `text: 人に見せる欄（審査役の why・faces_none・checks の why・compliance の read と行の why・quality の why、手直しの役の how・bash_writes の why）の言語。空は依頼の行の言語`。既定 `""`。

`schemas/` の形（`KNOWN_KEYWORDS` だけで書く。`blocks/.shared/AGENTS.md`）:

- `fix-reply.schema.json`: `{"type": ["object", "null"], "properties": {"changes": {"type": "array", "items": {"type": "object"}}, "not_done": {"type": "array", "items": {"type": "object"}}, "plan_faces": {"type": "array", "items": {"type": "object", "required": ["key", "handled"], "properties": {"key": {"type": "string"}, "handled": {"type": "string"}}}}}}`
- `permits.schema.json`: `{"type": "array"}`（行は object か字。行の形は `src/materials.py` の `permit_paths` が見る）
- `plan-review.schema.json`: `{"type": ["object", "null"]}`（fix の設計書の同じ名の形と同じ字）

出力（`returns: finish`、`outcome_field: ok`）:

- `ok`: boolean。`status` が `failed` でない（block の仕事が最後まで回った。役が諦めた `gave_up` も回った内に入る）。
- `status`: `ok`・`gave_up`・`failed`。`gave_up` はどれかの役が 3 回拒まれて諦めた（run は先へ進んでよい。今も止めなかった）。`failed` は段が壊れた（port が読めない・版が読めない・git が落ちた・指示が組めない・借りた写しが固定と違う・控えを書けない）。今は fix の node が非 0 で落ちて run が止まった所で、line は `ok` が false なら今と同じく止める（1.6）。
- `reason`: 日本語の 1 行（人に見せる）。飛ばした訳・諦めた役の最後の拒否・壊れた段と訳。どれでもなければ空の字。
- `rounds`: 0〜2 の整数。審査の輪が回った往復の数（受け付けた控えか拒否の控えの在る往復）。
- `pass`: boolean。最後に回った審査の義務が 0 で、諦めていない。審査を飛ばした時は true（今の `fixboard.delta_review` の `{rounds: 0, pass: true}`）。
- `holes`: pointer（`holes.json`。今の `delta-holes.json` と同じ形 `{ties: {"1": [名札] か組めない訳の字, "2": …}, handled: {"1": [手直しの行], "2": …}}`）か null（審査を飛ばした・入口で壊れた）。
- `diff`: pointer（`delta.diff`。`base` から手直しの後の今の作業ツリーまでの累積の差分）か null（差分が空・入口で壊れた）。
- `carry`: `[{where, text}]`。次の run の依頼に渡す行（今の `fixbeside.next_items` の手直しの行: 手直しが declared で残した穴と、2 回目の手直しが fixed と言った穴〔3 回目の審査が無いので検算が要る〕。名札の字を添える。レンズの行が読めなかった時の「再実行の要あり」の行）。
- `report`: 日本語の行の配列（6 節の 9）。

今との違い: 今は fix の place の中で、修正の段のファイル（`groups.json`・`join.json`・`conflicts.json`・`trace.jsonl` の相談の行・`plan-fields.json` と凍結の印・`fix-plan-reply.json`・`judgment.json`・`p2.plan_review.json`・`depth.json`・`assert-changed.json`・始めの記録）を名で開き、返りは fix の出力の `delta_review {rounds, pass}` と `delta_holes`・`lenses`（pointer）だった。この block は、それらのうち差分の審査が読む物だけを port の値で受ける。範囲の相談・裁定・テストの許しの読み分け（`conflict.agreed`・`ruled_paths`・`held_by_rulings`・`test_permits`）は修正の block の事実で、fix の返りの `scope`・`allowed_tests`・`reply` を、それぞれ 1 つの port で受ける（どれも fix がもう別々の pointer で返す欄で、受け手が組み直す物は無い。README の 4.2 の「3 つ以上の欄は 1 つの pointer」は、作り手の返りの欄を 1 つの object として読む時の決まりで、ここでは別々のファイル）。

### 1.3 node の並び（`blocks/delta-review/works-factory-delta-review.yaml`）

どの script の node も `runtime: uv`・`mutates_checkout: false`（どれも作業ツリーを変えない。7.1 と E7）。

1. `intake`（script `intake.py`）: port を読み、この block が名を持つファイルを消し、書き込みの記録を空で開き（`writelog.open_here`）、材料を写し、審査が要るかを決め、要れば 1 回目の差分を切って材料と作業ツリーの写しを置く。返り `{due, reason}`。落ちない。
2. `review-1-loop`（`loop_group`・`max_iterations: 3`・`fresh_context: false`・`until_bash: done=$review-1-accept.output.done; test "$done" = true`。`depends_on: [intake]`・`when: $intake.output.due == true`）
   - `review-1-prep`（script `review_prep.py`・`with: {n: 1}`）: 指示を組む。返り `{prompt}`。
   - `review-1`（AI。`prompt: "$review-1-prep.output.prompt"`・`depends_on: [review-1-prep]`・`model: '@wf-fix-review'`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob]`・`mutates_checkout: false`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`idle_timeout: 1728000000`・`retry: {max_attempts: 2, on_error: all}`。`output_format` は今の delta-review のまま。2.4）
   - `review-1-accept`（script `review_accept.py`・`depends_on: [review-1]`・`with: {n: 1, reply: $review-1.output}`）: 返り `{ok, done, reason}`。
3. `owed-1`（script `owed.py`・`with: {n: 1}`・`depends_on: [review-1-loop]`・`trigger_rule: all_done`）: 1 回目の審査が義務を出したかを決め、出していれば手直しの材料と段の頭の木を置く。返り `{due, reason}`。落ちない。
4. `refix-1-loop`（`max_iterations: 3`・`fresh_context: false`・`until_bash: done=$refix-1-accept.output.done; test "$done" = true`。`depends_on: [owed-1]`・`when: $owed-1.output.due == true`）
   - `refix-1-prep`（script `refix_prep.py`・`with: {n: 1}`）: 返り `{prompt}`。
   - `refix-1`（AI。`prompt: "$refix-1-prep.output.prompt"`・`depends_on: [refix-1-prep]`・`model: '@wf-fix-writers'`・`settingSources: [user]`・`skills: [receiving-code-review]`・`allowed_tools: [Read, Grep, Glob, Edit, Write, Bash, WebSearch, WebFetch, Skill]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`idle_timeout: 1728000000`・`retry: {max_attempts: 2, on_error: all}`。`mutates_checkout` は書かない。`output_format` は今の refix のまま。3.4）
   - `refix-1-accept`（script `refix_accept.py`・`depends_on: [refix-1]`・`with: {n: 1, reply: $refix-1.output}`）: 返り `{ok, done, reason}`。
5. `cut-2`（script `cut2.py`・`depends_on: [owed-1, refix-1-loop]`・`trigger_rule: all_done`）: 1 回目の手直しが fixed と答えた穴が在る時だけ、手直しだけの差分を切り、2 回目の材料と写しを置く。返り `{due, reason}`。落ちない。
6. `review-2-loop`（2 と同じ形で `review-2-prep`〔`with: {n: 2}`〕・`review-2`・`review-2-accept`〔`with: {n: 2, reply: $review-2.output}`〕。`depends_on: [cut-2]`・`when: $cut-2.output.due == true`。AI の鍵は review-1 と同じ。`output_format` は今の review2 のまま。4.4）
7. `owed-2`（`owed.py`・`with: {n: 2}`・`depends_on: [review-2-loop]`・`trigger_rule: all_done`）
8. `refix-2-loop`（4 と同じ形で `refix-2-prep`・`refix-2`・`refix-2-accept`。`depends_on: [owed-2]`・`when: $owed-2.output.due == true`）
9. `finish`（script `finish.py`・`depends_on: [intake, review-1-loop, owed-1, refix-1-loop, cut-2, review-2-loop, owed-2, refix-2-loop]`・`trigger_rule: all_done`）: 往復の控えを読んで `holes.json`・`delta.diff` を書き、出力を返す。どの段が落ちても落ちない。

輪の中はどれも prep → 役 → accept の 1 本の並び（README の土台の決め。`fresh_context: false` の輪の中の役の直前に 2 つ以上の node の層を置かない）。輪を回すかは輪の外の script（`owed-n`・`cut-2`）の返りで `when:` に決め、輪の中に「起こさない」の道を持たない（今は `refix-prep` が `go: false` を返し、役の `when:` と受け付けの `if_skipped: null` で飛ばしていた）。

今の node から無くす物: `delta-cut`（入口と `cut-2` へ割る。深さ・戻せない組・変更の確かめの決めは line へ。7 節）・`lens-prep`・`lens`・`lens-reply`・`lens-collect`（lens の block へ）・柵の node `nodes-ok`（block の外の決まり。返りの `ok` と `status` で替える）。

script の名は `lib/` のモジュールの名と重ねない（README の 7.1 の 9）。`lib/refix.py` が在るので `refix.py` の名の script は置かない。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、line から include された時は `$ARTIFACTS_DIR/delta-review/`）の下に書く。名は `src/files.py` だけが持つ。入口は下の名のファイルと `review-*-prompt-*.md`・`refix-*-prompt-*.md` だけを名で引いて消す（place は消さない）。

| 中身 | 新しい名 | 今の名（`fix/fix/` の下） |
|---|---|---|
| 入口の控え | `intake.json` | （無い） |
| 材料の写し | `scope.json`・`fix-reply.json`・`permits.json`・`plan-review.json`・`request.json`・`lens.json` | `fix-plan-reply.json` など・`fix-reply.json`・（無い）・`p2.plan_review.json`・（無い）・`lens.json` |
| 審査を飛ばした印 | `skipped.json` | `delta/skipped.json` |
| n 回目の差分 | `delta-1.patch`・`delta-2.patch` | `fix-delta.patch`・`fix-delta2.patch` |
| n 回目の差分の値 | `cut-1.json`・`cut-2.json` | `loop-fix_delta.json`・`loop-fix_delta2.json` |
| 審査役の材料 | `review-1-brief.json`・`review-2-brief.json` | `review1-brief.json`・`review2-brief.json` |
| 審査役の前の作業ツリーの写し | `review-1-tree.json`・`review-2-tree.json` | `review1-snapshot.json`・`review2-snapshot.json` |
| 受けた審査の返答 | `review-1-reply.json`・`review-2-reply.json` | `out-p3.delta_review.json`・`out-p3.delta_review2.json` |
| 審査の控え | `review-1.json`・`review-2.json` | `delta/review-1.json`・`delta/review-2.json` |
| 2 判定の控え | `verdicts.json` | `delta-verdicts.json` |
| 手直しの材料 | `refix-1-brief.json`・`refix-2-brief.json` | `refix1-brief.json`・`refix2-brief.json` |
| 手直しの段の頭の木 | `refix-1-head.json`・`refix-2-head.json` | `refix1-head.json`・`refix2-head.json` |
| 受けた手直しの返答 | `refix-1-reply.json`・`refix-2-reply.json` | `out-p3.delta_fix.json`・`out-p3.delta_fix2.json` |
| 却下の控え | `rejects-review-1.json` など 4 つ | `rejects-delta-accept.json`・`rejects-review2-accept.json`・`rejects-refix-accept.json`・`rejects-refix2-accept.json` |
| 名札と手直しの結果 | `holes.json` | `delta-holes.json` |
| 累積の差分 | `delta.diff` | `fix.diff` |
| 段が壊れた訳 | `errors.json` | （無い。node が落ちた） |
| 機械の行 | `trace.jsonl` | `trace.jsonl` |

`intake.json` は `{due, failed, reason, base, lens_error}`。`errors.json` は `[{node, reason}]`（壊れた段の script が積む。`finish` が読む）。座の写しのファイル（今の `review1-seat.md`）は作らない（座は指示の中の節にした。2.3）。`trace.jsonl` の行の語は今のまま（`delta_verdicts_saved`・`refix_accepted`・`refix_rejected`・`writes_unrecorded_run`）。

e2e の照らしの表 `tests/e2e/evidence.json` の差分の審査の行（L-W29・L-D12 など）は、組み込みで上の新しい名と node の id に合わせる（README の 11.4）。

### 1.5 コードの置き場（`lib/fixboard.py` などから写す範囲の割り当て）

README の 11.1 の 3 のとおり、fix と同じ波で `lib/fixboard.py` の中身を写す。写す範囲が重ならないよう、この block が写すのは下に名指す物だけ。ほかの `fixboard` の関数は fix の物。

- `blocks/delta-review/src/__init__.py`: 空。
- `src/files.py`: 1.4 の名・往復の数 `ROUNDS = (1, 2)`・役の名（`REVIEW = {1: "review-1", 2: "review-2"}`・`REFIX = {1: "refix-1", 2: "refix-2"}`）・除くパスの頭 `SKIP = (ports.RUNTIME_COPY_PREFIX,)`・比べる欄 `TREE_KEYS = accept.status_keys("true")`（今の `with: {status_guarded: true}`。読むだけの役の node は `mutates_checkout: false` で Archon が `git status` を照らすので `porcelain` を比べから外す）。
- `src/materials.py`（port の読みと材料の写し）: `scope(raw)`（`ports.file` の先の JSON を読み、object なら `plan_items`・`ruled_paths`・`agreed`、配列なら `{plan_items: <配列>, ruled_paths: [], agreed: []}`。項目は object で `item` が 1 以上の整数。`planmarks.scoped(plan_items)` が偽なら `plan_items` を `[]` にする〔今の `scope_brief` が `planrange.scope` の `None` を `[]` にしたのと同じ〕。読めない・形が違えば理由を名指す `ValueError`）・`fix_reply(raw)`（`ports.json(raw, "fix-reply.schema.json")`）・`permit_paths(raw)`（`ports.json(raw, "permits.schema.json")` の行から `path` か字を取り、重ねずに並べる）・`policy_brief(path)`（今の `fixboard.policy_brief` と `policy.brief` の写し。path が空なら `{paste: "", path: ""}`、在れば `{paste: policy._capped(<バイト>, path), path}`。読めなければ `ValueError`）・`lens_copy(place, raw)`（先の JSON を place の `lens.json` に写し `lens.read(place)` で形を照らす。読めない・形が違えば写しを消して訳の字を返す。今の `lens_error` の道）・`request_copy(place, raw)`（`requestrows.parts` で照らした値を `request.json` に書き、パスを返す。行が 0 なら書かずに空の字）。
- `src/cut.py`（差分と材料。写す元 `lib/refix.py` の `_cut_delta`・`cut`・`snapshot_name`・`_drop_stale` の要る所と `fixboard.run_diff`・`delta_review_due`・`claimed_closed`・`snapshot`・`_fix_report`）:
  - `due(repo, base, reply)`: (審査が要るか, 訳)。`base` から今の作業ツリーへの差分（`SKIP` の下を除く）が空でないか、`reply.plan_faces` に `absorbed` の行が在れば要る。訳の字は今の `delta_review_due` のまま。
  - `cut(place, n, repo, rev)`: 今の `_cut_delta`（`leftovers.snapshot`・`unittrees.pathspec_without(SKIP)`・`leftovers.git(… text=False)`・`leftovers.git_names`）。`delta-<n>.patch` と `cut-<n>.json`（`{file, files, rev, base}`）を書く。
  - `brief(place, n, repo, base, scope, reply, plan_review, policy)`: 1.4 の審査役の材料を書く（2.2 と 4.2 の欄）。`protected_files` は `protect.hits(files, protect.merged(repo, base))`、`protect.Broken` なら `[]` と `protected_files_error`。
  - 作業ツリーの写しは `jsonfile.write(place / f"review-{n}-tree.json", accept.tree_state(repo))`。
- `src/review.py`（審査の受け付け。写す元 `fixboard.delta_review_problems`・`claimed_closed`・`_keys_once`・`take`・`tree_moved_since`・`READONLY_MOVED`・`HUMAN_FACE_KINDS`・`PLAN_ONLY_FACE_KINDS`・`NONE_MIN` と `refix.accept_review`・`inner_faces`・`_added_text`・`_owed`）。2.8 と 4.8。
- `src/verdicts.py`（2 判定。写す元 `lib/deltamarks.py`）: `COMPLIANCE`・`QUALITY`・`KINDS`・`FAIL_KINDS`・`MIN_WHY`・`KEYS`・`FIELD_SCHEMA`・`REJECT`・`malformed`・`gaps`・`split`・`save`・`read`・`fail_rows`。`marks` に頼る所（`NODES`・`marks.split`・`marks.write`・`marks.load`）は、欄 2 つを外す dict の写しと `jsonfile` の読み書きに書き直す（`marks` は README の 9.1 で消す。返答の型は node の `output_format` が正本）。`save` は今どおり `trace.jsonl` に `delta_verdicts_saved` の行を足す。
- `src/touchup.py`（手直し。写す元 `fixboard._owed_rows`・`prep_fix`・`tie_items`・`hole_ties`・`delta_fix_problems`・`undeclared_refix`・`undeclared_writes`・`touched_since`・`UNDECLARED`・`stage_head` の要る所と `refix.accept_fix`・`SCOPE_REJECT`・`brief_ties`・`scope_text`）。3.8 と 5 節。範囲の照らしは `planrange.outside(scope["plan_items"], paths, permits + scope["ruled_paths"], hint=False)`（今の `planrange.check_paths(ruled=True)` の値: 合意を足した項目と、テストの変更の許しのパスと直す裁定のパス。置き場から読まずに port の値で受ける。fix の返りの `allowed_tests` は `conflict.test_permits` の範囲の行と相談で許した新しいテストのファイルで、新しいテストのファイルは合意を足した項目の `tests` にも入っているので、照らしの結果は今と同じ）。ほかに、答えの語 `HANDLED = ("fixed", "declared")`（YAML の enum と同じ並び）・義務の行 `owed_rows(place, n)`（今の `_owed_rows`）・範囲の節の行 `scope_lines(plan_items, permits)`（3.3 の `scope_items`・`scope_permits` の値。今の `planrange.scope_text` の行の値を、見出しと決まりの文を除いて英語の札で並べる）を持つ。`src/review.py` は穴の語 `FACE_KINDS = ("copy", "entrance", "contract_drift", "dead_path", "scope_creep")` と、塞いだと言われた答えの語 `CLAIMED = {1: "absorbed", 2: "fixed"}`（今の `claimed_closed` の語）を持つ。
- `src/borrowed.py`（座の材料）: `seat.pinned()`（写しが固定と違えば `ValueError`）・型の本文 `seat.fill("task-review", 穴)`・判定の語の表の行（`spseam.load_seams()["task-review"]["words"]` と `seat.VERDICT_WORDS` から `| <型の語> | <works の語> | `<欄>.verdict`: `<値>` |` の行を並べる。今の `seat.words_table` の行の組み方。見出しと注の 2 行は md）・スキルの名と効く所・効かない所（`seat.skill_of`・`seams.json` の `applies`・`not_applies` を `- ` の行に）・読み替えの本文 `seat.overlay_body(seat.OVERLAY_KINDS[<review か refix>])` と在りか `spseam.BORROW_DIR / spseam.OVERLAY_FILE`。座の文の決まった字（今の `seat.HEAD`・`WINS`・`SKILL_LEAD`・`APPLIES`・`NOT_APPLIES`・`PROMPT_HEAD`・`WORDS_HEAD`・`NOTE_ROWS`・`OVERLAY_HEAD`）は使わず md に置く。
- `src/summary.py`（出口。写す元 `fixboard.delta_review`・`fixbeside._ties`・`branch_rows`・`branch_head`・`handled_head`・`BRANCH_HEAD`・`next_items` の手直しの行・`always_rows` のレンズの行・`line/scripts/ask_final.py` の `delta_lines`）: 6 節の 9。
- 使う `lib/`（どれも KEEP。変えない）: `accept`（`tree_state`・`tree_moved`・`TREE_SCHEMA`・`status_keys`）・`gatemarks`（`HANDLED_WORDS`）・`holeties`・`jsonfile`・`lens`・`leftovers`・`oneline`・`planmarks`（`scoped`・`test_paths`）・`planrange`（`outside`・`globs`・`LIFTED`。`OOS_ANY` の字は md へ）・`policy`（`_capped`・`POLICY_KIND`）・`protect`・`report`（`inner_word_hits`・`target_uses`・`INNER_FACE_KIND`）・`rolekit`・`seat`・`spseam`・`unittrees`（`pathspec_without`）・`writelog`・`writes`・`graphloops/engine/schema.py`（`validate_schema`）・`graphloops/engine/util.py`（`READ_CAP`・`read_capped`）。`fixboard`・`refix`・`refixrules`・`deltamarks`・`fixbeside`・`rulebook`・`fixrules` は import しない（写す）。
- 作り直しの間は `lib/deltamarks.py`・`lib/refix.py`・`lib/refixrules.py` と `fixboard` の写した部分を消さない（今の fix が使う）。組み込みで消す（README の 9.2）。

### 1.6 つなぎ方（graph の側。block には書かない）

- line: fix の後、lens の後に `include: works-factory-delta-review`。`when:` は今 `delta-cut` が決めていた 3 つ: 修正の段の変更の確かめが通った（今の `assert-changed.json` の `ok`）・戻せず当たったままの組が無い（今の `fixboard.held`。fix の止めの語 `stopby.UNRESTORED` が空）・修正の後の上げ直しの後も「頭が軽量で全部の単位が軽量」でない（今の `fixboard.redepth` の `depth.skip_reason`。README の 1.2 の D と形の直し 5）。lens にも同じ `when:` を置く。
- `with:`: `base: $fix.output.start_tree`・`plan: $fix.output.scope`・`lens_rows: $lens.output.rows`・`fix_reply: $fix.output.reply`・`permits: $fix.output.allowed_tests`・`plan_review: <最後の事前審査の返答。fix に渡したのと同じ>`・`policy: <始めの記録の方針の写しのパス>`・`request: <依頼の pointer>`・`lang: <始めの記録の lang>`（fix の返りの欄の名は fix の設計書の 1.2。`when:` の `checked.ok` と `stop_reason` も同じ所）。
- 読み手:
  - line: 修正の段が済んだかを、今の `collect` と同じく「変更の確かめが通った ∧（審査を飛ばした ∨ `pass`）∧ 戻せない組が無い」で決める。`ok` が false なら止める（今は delta の node が非 0 で落ちて run が止まった）。`status` が `gave_up` なら止めない（今も止めなかった）。最後の承認ノードは `report` の行（差分の審査の回数と名札と手直しの結果）を載せ、`holes` を読む。
  - report: `sections` に `$delta-review.output.report`（今の報告の「差分の審査の穴の枝」と「未確認のレンズ」の数えの行）。次の run の依頼は line が `carry` を `facts` の `carry.findings` に入れる。結末の残りの行「差分の審査が通っていない」（今の `lib/outcome.py:347`）は line が `pass` から `facts.left` に入れる。
  - 累積の差分の読み手: 今 fix の返りの `diff`（手直しの後の姿）を読んでいた所は、この block が回った時は `$delta-review.output.diff` を読む（line の設計書で決める）。
- 案の直しの後の 2 度目の修正の段（今の `refix-run`）は、2 度目の fix の後にこの block をもう 1 回 include する（place は include の道で分かれる。README の 4.4）。

## 2 node の設計シート: review-1（1 回目の審査役）

### 2.1 役

修正の直後に、この周の修正だけの差分を読み、修正が新しく作った穴を挙げ、修正役が塞いだと言った事前審査の穴を 1 件ずつ検算し、承認済みの修正案の項目への準拠と品質の 2 判定を行から決まる語で書く。読むだけ。

### 2.2 port

指示の値: `cut-1.json` の `file`・`files`（← port `base` と作業ツリー）・`review-1-brief.json` のパス・前の回までの却下（← place の `rejects-review-1.json`。`rolekit.rejected`）・座の材料（← `lib/borrow/`）・`lang`。

`review-1-brief.json` の欄（役が Read する。今の `review1-brief.json` から `node`・`reads`・`seat_file` を外し、`reads` の中身を上の段に上げた）:

- `diff_file`・`files`・`rev`（固めた修正後の姿）・`base`
- `plan_review`: ← port `plan_review` の JSON のまま（今の `reads.out.p2.plan_review`）。無ければ null。
- `plan_faces`: ← port `fix_reply` の `plan_faces`（今の `reads.out.p3.fix.plan_faces`）。無ければ `[]`。
- `protected_files`（と、読めない時の `protected_files_error`）
- `lens`: ← port `lens_rows` の行の `lens.brief_rows`（`{lens, state, reason, findings}`）。渡されていなければ `[]`、読めなければ `[]` と `lens_error`。
- `plan_items`・`ruled_paths`・`agreed`: ← port `plan`（範囲の欄のまま。1.5 の `materials.scope`）。
- `fix_report`: ← port `fix_reply` の `changes`・`not_done`（無ければ `{}`）。
- `policy`: ← port `policy`（`{paste, path}`）。

### 2.3 組み立ての順（`prompts/review-1.md`）

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: 却下の控えに拒否が在る。`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "review-1"))`。
2. 役の定義（決まった文。頭の 1 文は `You are the inspector for the diff of this round's fix.` で、筋書きが照らす）: この周の修正だけの差分を見て、修正が新しく作った穴を同じ周のうちに見つける・読むだけで、書く・消す・git を動かすことはしない・受け付けは役を起こす前に撮った作業ツリーの写しと今の作業ツリーを比べて拒む。「新しい会話」とは書かない（`fresh_context: false` の輪。拒まれた回は同じ会話の続き）。
3. `## Material`（決まった文）と差し込み口 `{diff_file}`・`{files}`（← `cut-1.json` の `files` の JSON の字）・`{brief_file}`。材料の欄ごとの説明（2.2 の欄の順。`protected_files`・`lens`・`plan_items`・`ruled_paths`・`agreed`・`fix_report` の読み方と義務）は決まった文。`lens` の段落に差し込み口 `{failed}`・`{not_routed}`（← `lens.STATES` の語）。
4. 読むのは作業ツリーの今の姿・cite は今の姿で引かれる（決まった文）。
5. `{part:faces}`（審査の 2 本が共に使う断片。下の「断片」）。
6. 検算の段落（決まった文）: 修正役が `{absorbed}` と答えた穴を 1 件ずつ検算する・`closed` の意味・手直しが同じ key で答える・漏れは拒まれる。`{absorbed}` ← `"absorbed"`（`src/review.py` の `CLAIMED[1]`）。
7. `## Two verdicts (compliance first, then quality)`（決まった文）: 準拠の行の語 `{missing}`・`{extra}`・`{misunderstood}`・`{unverifiable}`（← `verdicts.KINDS`）、判定の語 `{pass_word}`・`{fail_word}`・`{not_applicable}`（← `verdicts.COMPLIANCE`）、穴の語との結び（`{scope_creep}`・`{contract_drift}`）、字の下限 `{min_why}`（← `verdicts.MIN_WHY`）。
8. `## How to answer (the verdict fields)`（決まった文）: compliance と quality を必ず書く・落ちた行は face_key で結ぶ・行と語が合わなければ拒まれる。
9. `<!-- if rejected -->` 拒まれた穴を黙って消さない・where か cite が合わなかったなら変わったファイルの今の姿を Read し直して正しく引く `<!-- end rejected -->`。
10. `## Borrowed template`（決まった文）: 型の手順で審査する・ぶつかる所はこの指示が勝つ（返す JSON の形・読む義務〔読む側・呼び元・作業ツリーの今の姿〕。型の "Do not crawl the broader codebase" と「変わったファイルを別に Read しない」は効かない・判定の欄の値は 7 の決まりで行から決まる・`plan_items` が空なら型が何と言っても `{not_applicable}`・準拠の行に結ばれない穴が在れば quality は `{fail_word}`）。続けて `### Sub-agent template (superpowers' {seat_file}, wrapped in works' sections)` と `{seat_template}`（← `borrowed` の型の本文）、`### Verdict words` の見出しと説明の 1 文・表の頭の行・`{seat_words}`（← 表の行）・注の 2 行（決まった文。`plan_items` が空 → `{not_applicable}`、結ばれない穴 → `{fail_word}`）、読み替えの頭の 1 文（直の指示でスキルの文より勝つ・Agent で下請けを起こすなら `{overlay_path}` を Read せよと書く）と `{overlay}`。
11. `{part:policy}`（審査の 2 本が共に使う方針の段落）。
12. 言語の 1 文: 人に見せる欄（`why`・`faces_none`・`checks` の `why`・`compliance.read`・`compliance.items` の `why`・`quality.why`）を `{lang}` で書く。key・enum の値・パス・識別子はそのまま。
13. 結びの 1 文: 出力の schema に合う JSON だけを返す。

断片 `prompts/parts/faces.md`（review-1 と review-2 が `{part:faces}` で入れる）:

1. 見るのは 3 点（決まった文）: 写し `{copy}`・入口 `{entrance}`・宣言と実装のずれ `{contract_drift}` の定義。`<!-- if first -->` 加えて品質の観点（下の判定の節）`<!-- end first -->`。
2. 使えない語（決まった文）: `{regression}`・`{policy_kind}`・`{precedent}` は修正の前の事前審査だけの語で、ここでは受け付けない。修正の後の後退は後の段が人に上げる。
3. 差分は起点であって境ではない。読む側・呼び元まで読む。
4. `protected_files` の段落（決まった文）: 変わったファイルのうち守りのファイル・検査を緩めていないか（試験を消す・弱める・期待を書き換える・柵や受け付けを外す）・緩めていれば穴（`kind` は 5 つの語のどれか）・守りのファイルは最後の承認ノードにも必ず出る。
5. 穴の行の書き方（決まった文）: `key`（`{min_key}` 字以上・穴を一意に呼ぶ名）・`kind`（3 点の語と `{dead_path}`〔足したのにどこからも届かない道〕・`{scope_creep}`〔頼まれていない所まで広げた変更〕）・`where`（変わったファイルのパスだけ・一覧の字のまま・行番号や関数名は `why` に・受け付けはパスの完全一致・変わっていないファイルの穴はここでは挙げない）・`cite`（そのファイルの今の姿に在る字列そのまま・`{min_cite}` 字以上・言い換え・要約・省略をしない）・`why`（`{min_why}` 字以上）。`<!-- if first -->` レンズの指摘から採った穴だけ `lens` に出どころのレンズの名を足し、ほかは省く `<!-- end first -->`。
6. 穴が無い時（決まった文）: `faces` を空にし、`faces_none` に何を読んで無いと言えるか（`{min_none}` 字以上。読んだファイル・読む側・呼び元の名）を書く。

断片 `prompts/parts/policy.md`（review-1 と review-2）: 人の方針の段落（決まった文）。本文は材料の `policy.paste`（空なら方針は無い。長くて切り詰めた時は末尾に続きの置き場が在り、写しの置き場は `policy.path`）・在れば先に全部読む・方針は対象の本文でなく、この指示の発行者が守らせる制約・審査は方針に照らして行う・ぶつかる修正はどの項とぶつかるかを穴の `why` に書く（`kind` は 5 つの語のうち一番近い物、どれにも当たらなければ `{contract_drift}`）・方針の文書は書き換えない。

差し込み口の値（`src/review.py` の定数。md と受け付けが同じ字を持つ）: `copy`・`entrance`・`contract_drift`・`dead_path`・`scope_creep`（← `FACE_KINDS`。YAML の `kind` の enum と同じ並び。試験が結ぶ）・`regression`・`policy_kind`・`precedent`（← `HUMAN_FACE_KINDS = ("regression", policy.POLICY_KIND)` と `PLAN_ONLY_FACE_KINDS` の残り `"precedent"`）・`min_key`（8）・`min_cite`（4）・`min_why`（20）・`min_none`（`NONE_MIN` の 20）。段落の名: `rejected`・`first`（review-1 は true、review-2 は false）。

md の本文の正本は `blocks/delta-review/prompts/`（設計書は本文を写さない）。

### 2.4 返す形

今の `delta-review` の node の `output_format` のまま（`workflows/fix/works-factory-fix.yaml:983-1044`）: `faces [{key (8 字以上), kind (copy|entrance|contract_drift|dead_path|scope_creep), where, cite (4 字以上), why (20 字以上), lens?}]`・`faces_none`・`checks [{key, closed, why}]`・`compliance {verdict (pass|fail|unverifiable|not_applicable), items [{item, kind (missing|extra|misunderstood|unverifiable), face_key, why}], read}`・`quality {verdict (pass|fail), why}`。人に見せる欄は 2.3 の 12 の欄（`{lang}`）。

### 2.5 描いた骨組み（例の run の値）

```markdown
You are the inspector for the diff of this round's fix. …（読むだけ・作業ツリーの写しとの比べ）

## Material

- The diff of the fix: `<place>/delta-1.patch` (Read it. …untracked new files are in it. …)
- Changed files: ["docs/design.md", "docs/works-parity.md", "lib/gatemarks.py", …（20 本）]
- The brief: `<place>/review-1-brief.json` (Read it. JSON.)
  - `plan_review`: … 　- `plan_faces`: … 　- `protected_files`: … 　- `lens`: … `failed`, `not_routed` …
  - `plan_items`: … `held` … `held_units` … 　- `ruled_paths`: … 　- `agreed`: … 　- `fix_report`: …

Read the current state of the work tree. …

Look at three points only …: 1. copy … 2. entrance … 3. contract_drift …
`regression`, `policy`, and `precedent` are words of the review before the fix …
…（守りのファイル・穴の行の書き方・faces_none）

Check every hole the fixer answered `absorbed` one by one …

## Two verdicts (compliance first, then quality)
1. Compliance … `missing` … `extra` … `misunderstood` … `unverifiable` …
2. Quality …

## How to answer (the verdict fields)
…

## Borrowed template
…this prompt wins …
### Sub-agent template (superpowers' skills/subagent-driven-development/task-reviewer-prompt.md, wrapped in works' sections)
## What Was Requested …（型の本文。約 170 行）
### Verdict words
| Template word | works word | Field value |
| ✅ Spec compliant | compliance_pass | `compliance.verdict`: `pass` |
…（5 行と注の 2 行）
When you read a borrowed skill (superpowers), follow the reinterpretation below. …
# 借りた superpowers のスキルを無人の役で読むときの読み替え …（読み替えの本文）

## Human policy
…

Write `why`, `faces_none`, … in the language of the request (the user's language). …
Return only JSON that matches the output schema.
```

例の run の値: 変わったファイル 20 本・守りのファイル 3 本（`tests/layers/*.py`）・レンズの行 1 本（silent-failure-hunter、`ran`、発見 4 件）・承認済みの項目 5 つ（裁定で外れた項目が在る）・範囲の相談の合意 2 行・事前審査の穴 16 件・修正役の `plan_faces` 17 行（うち `absorbed` 16）・方針の文書は無い。役は 1 回目で通り（`rejects-delta-accept.json` が無い）、穴 3 件（うちレンズから採った物 1 件）・検算 16 件（`closed: false` 1 件）・準拠 `pass`（行 0）・品質 `fail` を返した。今の指示は command の md で、置き場に組んだ指示のファイルが無い。骨組みは今の md に例の run の値を入れて描いた（座の本文は今の `review1-seat.md` 〔約 22 KB〕と同じ物が入る）。

### 2.6 今の指示との差

作り直しの時の、古い指示との差の記録。今の指示は `workflows/fix/commands/delta-review.md`（62 行）と、役が Read する `review1-seat.md`（`seat.section("review", …)` が組む）の 2 か所に在る。

- 移した: 材料の 3 行の `$delta-cut.output.diff_file`・`files`・`brief_file` を差し込み口に。
- 替えた: 材料の欄の名 `reads` の下の `out.p2.plan_review`・`out.p3.fix.plan_faces` を、上の段の `plan_review`・`plan_faces` に（材料の `reads` の入れ子は、写した graph の節の reads の名残で、役のする事に関わらない）。md の欄の説明も同じ名にした。
- まとめた: 材料の `seat_file`（別のファイルを Read させ、その中に型と判定の語の表）を、指示の中の節 `## Borrowed template` にした。今の md の `seat_file` の行のぶつかりの決まり（返す形・読む義務・判定の欄の値の決め方・`plan_items` が空・結ばれない穴）は、その節の頭に移した。座の頭の「役の指示書 commands/delta-review.md の約束…は借りた文に勝つ」（`seat.WINS_OF["review"]`）は、座が指示の中に入ったので「この指示が勝つ」にした。座の文の決まった字（`seat.HEAD`・`PROMPT_HEAD`・`WORDS_HEAD`・`NOTE_ROWS`・`OVERLAY_HEAD`）は md へ出した（README の 9.3 の `seat`「文を md へ出す」）。
- まとめた: 「## 前の返答が拒まれたとき」（md:55-59。理由のファイルを `$LOOP_PREV.delta-accept.output.reason_file` で名指して Read させた）を、共通の断片 `{shared:rejected}`（理由の全部を古い順に貼る）と、拒まれた穴を黙って消さない 1 段落にした。
- まとめた: 3 点の定義・使えない語・穴の行の書き方・守りのファイル・方針の段落を、review-2 と共に使う断片 `parts/faces.md`・`parts/policy.md` に 1 回ずつ。方針とぶつかる穴の `kind` は、今の review2.md の「一番近い物、どれにも当たらなければ contract_drift」の書き方に揃えた（今の delta-review.md は「上の 5 つのどれか」で、選び方を言わなかった。言っている事は同じ）。
- 移した: 穴の語・準拠の行の語・判定の語・字の下限を差し込み口に（受け付けと YAML の enum と同じ字。README の 5.3）。
- 消した: ほかの node の id（`$delta-cut.output.*`・`$LOOP_PREV.delta-accept.output.reason_file`）と、ほかの役の名（「手直しの役が同じ key で答える」の手直しの役は「the touch-up step」と言い、node の名を書かない）。
- 足した: 言語の 1 文。今の md は言語を言わなかったが、日本語の md だったので日本語で返っていた。英語の md にすると返答の言語が変わるので、人に見せる欄を名指して `{lang}` で書けと言う（README の 5.3）。
- 英語にした（#764）。役の名「審査役」は "the inspector"。

### 2.7 元の works と graphloops の同じ場面

- graphloops の `prompts/review-loop/p3.delta_review.md`（18 行。block `blocks/review-loop/delta/` の `p3.delta_review`）: 3 点と検算と穴の行の書き方は同じ。違い: graphloops は検算の key を engine が振った番号 `no` の整数で指させ（「写すな」）、工場は key を一字も変えずに写させる（工場の受け付けが key の集合で照らすので、番号の道は要らない。今のまま）。graphloops に無く工場に在る物（2 判定・レンズ・座・守りのファイル・方針・範囲の欄・修正の報告）は、この block も全部持つ。graphloops の「修正の後の後退は R4 が BASE と比べて人に上げる」は、工場では「後の段が人に上げる」（独立の目を名指さない）。
- graphloops の `p3.delta_gates`（周の版に変異を撃って見逃しに答える並行の線）: 工場に無い。持ち主の決め `no-mutation-in-graph`（2026-10-13。`docs/owner-decisions.md:208`）で戻さない。この block も持たない。
- 元の works の `works/blk-delta/`: 入力 `base_rev` 1 つ・出口 `{ok, faces, review_file, diff_file, owed, fix_rev}`。審査の後の「読んだ証拠」の node `review-reads`（受け付けの条件にしない記録 `reads-review.json`）が在った。工場の fix には無い（`git log -S review-reads` は事前審査の物だけに当たり、差分の審査で外した記録は見つからない。（未確認））。この block にも足さない（読んだ証拠は受け付けの条件でなく、今の工場の報告も読まない）。
- 2 判定（準拠と品質）・座・レンズ・守りのファイル・範囲の照らしは、工場が足した物（依頼 218・#94 など）。この block は全部残す。

### 2.8 受け付け（`review_accept.py` と `src/review.py`。n = 1）

照らす順と却下の字は今のまま（`fixboard.delta_review_problems`・`refix.accept_review`・`deltamarks.gaps`）。

1. 返答が読めない・object でない: `rolekit.accept_round` の拒否（今は `ValueError` で node が落ちて run が止まった。ほかの block と同じく拒否にする。Archon の `output_format` が JSON を約すので、実際には当たらない）。
2. `delta_review_problems`（どれか 1 つでも在れば「差分の審査の返答の照らしに通らない:」と行の並びで拒む）:
   - `faces` の key の重なり（「faces[i] の key が重複」）。
   - `kind` が `regression`・`policy`（「事前審査だけの語——修正の後の後退・方針とのぶつかりは後の段が人に聞く」）か `precedent`（「事前審査だけの語——判定者の先行例はこのノードに渡っていない」）。
   - `where` が `cut-1.json` の `files` に無い。
   - `cite` が `where` の今の姿（`read_capped(…, READ_CAP)` のバイト）に無い・空。
   - 穴が無いのに `faces_none` が `NONE_MIN`（20）字に満たない。
   - `checks` の key の重なり・塞いだと言われた穴（`plan_faces` の `absorbed` の key）に無い key・塞いだと言われた穴に検算が無い。
3. 2 判定（`verdicts.malformed` が偽の時だけ）: `verdicts.gaps(reply, plan_items)` に行が在れば `verdicts.REJECT` と行で拒む。行の決まりは今の `deltamarks.gaps` のまま（欄の型・項目が無い run は `not_applicable` と空の行・項目が在れば `not_applicable` にしない・項目の番号の範囲・裁定で外れた項目の落ちた行を拒む・落ちた行は `faces` の key に結ぶ・`unverifiable` の行は結ばない・行から決まる判定・結ばれない穴が在れば品質は `fail`）。`malformed` が真（`faces` が key を持つ object の並びでない）なら 2 判定を照らさず、欄を外して 4 へ。
4. 欄を外した返答（`verdicts.split`）の `faces` の後ろに機械の穴（`inner_faces(place, 1, repo, base)`。`report.inner_word_hits` を 1 回目の差分に当て、`report.target_uses(repo, base, 語)` で対象が修正の前から使う語を除く。key は `inner_word <パス>:<行>`）を足し、作業ツリーの写し `review-1-tree.json` と今の作業ツリーを `TREE_KEYS` で比べる（変わっていれば `READONLY_MOVED` の文で拒む。写しが無い・形が違えば訳を名指して拒む）。
5. 受けた時の書く順: `review-1-reply.json`（機械の穴を足した返答）→ `verdicts.json`（2 判定。書けなければ受けた後に控えの無いまま先へ進ませないので、段が壊れた訳を `errors.json` に積み、`{ok: false, done: true}`）→ `review-1.json`（`{pass: 義務の数 == 0, owed: 義務の数, reply_file}`。この控えが済んだ印）。
6. 回数: `rolekit.accept_round(place, "review-1", raw, take)`。3 回目の拒否で `done`。諦めた時は `review-1.json` に `{pass: false, owed: 0, reply_file: "", gave_up: true, reason: rolekit.given_up_reason(place, "review-1")}` を書く（今のまま）。loop は `fresh_context: false` なので、2 回目からは同じ会話の続きで役が起き、指示の頭に却下の段落が入る。
7. 諦めた時に出口へ書く物: `status: gave_up`・`reason` に諦めた文・`rounds: 1`・`pass: false`。手直しは起こさない（`owed-1` が `due: false`）。

### 2.9 試験

10 節に全部を書いた。この node に当たる物: 筋書き `standalone`・`two-rounds`・`gave-up`・受け付けの試験（10.2 の `ReviewAcceptCase`・`VerdictsCase`）・古い指示の残す決まり（10.3 の review-1 の行）。守る keep-essence は 9 節。

## 3 node の設計シート: refix-1（1 回目の手直しの役）

### 3.1 役

1 回目の審査が挙げた穴（機械の穴を含む）と塞がっていなかった検算の全部に 1 度ずつ、直す（fixed）か残す（declared）かで答え、承認済みの修正案の範囲の中で同じ周のうちに直す。

### 3.2 port

指示の値: 方針の写しのパス（← port `policy`）・依頼のファイル（← port `request` を写した `request.json`）・範囲の節の行（← port `plan` と `permits`）・`refix-1-brief.json` のパス・`cut-1.json` の `file`・前の回までの却下（← `rejects-refix-1.json`）・座の材料・`lang`。

`refix-1-brief.json` の欄（今の `refix1-brief.json` から `node`・`reads` を外した物）: `diff_file`・`owed`（`[{key, from, text}]`。`from` は `review-1` か `review-1.checks`。`text` は今の `_owed_rows` の字）・`ties`（`touchup.brief_ties(hole_ties(…))`。組めなければ `[]` と `ties_error`）・`policy`・`plan_items`・`ruled_paths`・`agreed`・`compliance`（`verdicts.fail_rows(verdicts.read(place))`）。

### 3.3 組み立ての順（`prompts/refix-1.md`）

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->`。
2. `{part:refix-before}`（手直しの 2 本が共に使う断片）:
   - `<!-- if policy -->` 方針の文書の 1 行（`{policy_path}`。先に全部読む）`<!-- end policy -->` と `<!-- if not policy -->` 方針の文書は無い `<!-- end policy -->`。
   - `<!-- if request -->` 依頼の文のファイルの 1 行（`{request_file}`。先に全部読む）`<!-- end request -->` と `<!-- if not request -->` 依頼の文のファイルは無い `<!-- end request -->`。
   - `<!-- if scope -->` `## Paths you may change and things you must not touch (the acceptance checks against these values)` と決まった文（受け付けはこの値で照らし外れを拒む・今の `planrange.OOS_ANY` の決まりの文・範囲の相談で許されたパスとテストの許しもここに入っている）と `{scope_items}`（← 項目ごとの行。1.5 の `touchup.scope_lines`）と許しの行の頭（決まった文）と `{scope_permits}` `<!-- end scope -->` — 条件: 範囲の欄の在る承認済みの項目が在る（今の `scope_text` が空でない時）。
3. 役の頭（決まった文。頭の 1 文は `You are the writer who touches up the holes the diff review raised.`）: 審査役が挙げた穴と、機械が差分の足した行に見つけた works の内側の語の穴（`kind` が `{inner_word}`）と、塞がっていなかった検算を同じ周のうちに直す。材料 `{brief_file}` の欄ごとの説明（`owed`・`diff_file`・`plan_items`〔`held`・`held_units` に向けて直さない〕・`ruled_paths`・`agreed`・`compliance`・`ties`）と、修正の差分 `{diff_file}`、方針の段落。このノードが在る理由の 1 段落。
4. `{part:refix-rules}`（手直しの 2 本が共に使う断片）:
   1. `{shared:writer-rules}`（書く役の決まりの正本。今の `fix-rules/common.md`。段落 `conflict`〔今の `core-conflict`〕は false、証拠の種類の段落 `docs`・`prompts_kind`・`config`・`code` は true。段落の名は fix の設計書の 2.3.1 の物に揃えた）。
   2. `{shared:query-rule}`（段落 `spawns` は false）。
   3. `## Reinterpretation for this loop (this wins over the rules above)`（今の `refix-remap` の 5 つの箇条）。
   4. `## Rules for the touch-up only`（今の `refix-keep`）。
   5. `## Borrowed skill seat`（決まった文: Skill の道具で `{seat_skill}` を読み、その手順で進める・この指示の約束と下の読み替えが勝つ・効く所の頭と `{seat_applies}`・効かない所の頭と `{seat_not_applies}`・読み替えの頭の 1 文と `{overlay_path}` と `{overlay}`）。
   6. `## Reply (as the output_format says)`（今の `refix-reply`）。差し込み口 `{fixed}`・`{declared}`（← `touchup.HANDLED`。YAML の enum と同じ並び）・`{min_how}`（20）。
   7. 言語の 1 文: 人に見せる欄（`handled` の `how`・`bash_writes` の `why`）を `{lang}` で書く。
5. 返答の後に当たる物（決まった文。今の `refix-tail-1`）: fixed と答えた穴には、手直しだけの差分に 2 回目の審査が当たり、直したと言う穴を 1 件ずつ検算する。
6. 結びの 1 文。

差し込み口の値: `rejection`・`policy_path`（← port `policy` の絶対パス。無ければ空の字）・`request_file`（← `request.json` の絶対パス。無ければ空の字）・`scope_items`・`scope_permits`（範囲が無ければ空の字）・`brief_file`・`diff_file`・`inner_word`（← `report.INNER_FACE_KIND`）・`seat_skill`・`seat_applies`・`seat_not_applies`・`overlay_path`・`overlay`・`fixed`・`declared`・`min_how`・`lang`。段落の名: `rejected`・`policy`・`request`・`scope`・`conflict`・`docs`・`prompts_kind`・`config`・`code`・`spawns`。

`scope_items` の行（材料の札。英語にする。今の `planrange.scope_text` の行と同じ値）: 項目ごとに `- Item <n> (units: <unit_keys を、で>)`・`  - allowed_paths: <glob を、で。無ければ none>`・`  - test files (ids in tests and rewrite_tests): <…>`・`  - out_of_scope: <glob（why）を、で>`・在れば `  - paths lifted from out_of_scope by a scope consultation: <…>`。`scope_permits` は port `permits` のパスと範囲の欄の `ruled_paths` の和（無ければ none）。パスは字のまま `` ` `` で囲む。

### 3.4 返す形

今の `refix` の node の `output_format` のまま（`workflows/fix/works-factory-fix.yaml:1092-1121`）: `handled [{key (8 字以上), handled (fixed|declared), how (20 字以上), files?}]`（1 行以上）・`bash_writes [{path, why (10 字以上)}]`。人に見せる欄は `how`・`bash_writes` の `why`（`{lang}`）。

### 3.5 描いた骨組み（例の run の値）

```markdown
Human policy document: none.

Request file: `<依頼のファイル>` (read it all first)

## Paths you may change and things you must not touch (the acceptance checks against these values)

The acceptance checks the paths you change against these values and rejects what falls outside. `out_of_scope` is stronger than the scope …

- Item 1 (units: tests/layers/scan.py:_line_reads — …)
  - allowed_paths: `tests/layers/scan.py`, `tests/layers/test_block_returns.py`, `workflows/AGENTS.md`, `docs/design.md`
  - test files (ids in tests and rewrite_tests): `tests/layers/test_block_returns.py`
  - out_of_scope: none
  - paths lifted from out_of_scope by a scope consultation: `tests/layers/scan.py`, `tests/layers/test_block_returns.py`
- Item 2 …（5 項目）
- Permits for every item (test-change permits and paths added by fix rulings; they do not beat out_of_scope): none

You are the writer who touches up the holes the diff review raised. …
- The brief: `<place>/refix-1-brief.json` (Read it. JSON.)
  - `owed`: … `inner_word` … 　- `diff_file`: … 　- `plan_items`: … 　- `ruled_paths`: … 　- `agreed`: … 　- `compliance`: … 　- `ties`: …
- The fix's diff: `<place>/delta-1.patch`
…（方針の段落・このノードが在る理由）

## How to fix …（writer-rules の本文: 直し方・テストで赤→緑を示せない直しの証拠 4 種・守ること）
{shared:query-rule の本文}
## Reinterpretation for this loop (this wins over the rules above) …
## Rules for the touch-up only …
## Borrowed skill seat
Read `receiving-code-review` with the Skill tool …
Where it applies:
- 審査の指摘を受けて、確かめてから直すか反論する仕事
Where it does not apply (do not follow):
- 審査の指摘を出す仕事
- GitHub のスレッドへの返信（外へ書き込まない）
… `<lib>/borrow/unattended.md` …
# 借りた superpowers のスキルを無人の役で読むときの読み替え …
## Reply (as the output_format says) …
Write `how` … in the language of the request (the user's language). …
For holes you answer `fixed`, a second review is run on the touch-up-only diff …
Return only JSON that matches the output schema.
```

例の run の値: 義務 4（穴 3・塞がっていない検算 1。機械の穴は無し）・名札 4（1 件は「項目 1（裁定で外れた項目だけ: ask_human の裁定 c1-1）」）・承認済みの項目 5・範囲の相談の合意 2・準拠の落ちた行 0・方針の文書は無い。役は 1 回目で通り、1 件を fixed（2 ファイル）、3 件を declared で返した。今の組んだ指示 `prompt-p3.delta_fix.md`（39 KB）の頭の機械の行と、2 行目の「依頼の文のファイル」のパスは置き場の外のファイルだった（新しい形では `request.json` の写し）。

### 3.6 今の指示との差

今の指示は `lib/fixboard.py` の `refix_prompt`（:1616-1643）が `rulebook.render` で組む 1 本で、文は `commands/fix-rules/refix.md`（節 `refix-head-1`・`refix-remap`・`refix-keep`・`refix-reply`・`refix-tail-1`）・`commands/fix-rules/common.md`（`core-conflict` を除く全部）・`seat.section("refix")`・`fixrules.start_lines`・`refix.scope_text`（`planrange.scope_text`）・`rolekit.LANG_RULE` に在る。

- 消した: 1 行目の機械の行 `<!-- works-prompt {role, iteration, rules_sha, sections} -->`（`rulebook.HEADER`）。読むのは `lib/tests/test_fix_rules.py`・`test_fix_seams.py` だけで、役にも報告にも要らない。載せた節は md の組み立てで決まる。
- まとめた: 1 行目の拒否の理由のファイルの名指し（`rolekit.REJECT_LINE`）を `{shared:rejected}`（理由の全部を貼る）に。
- 移した: 始めの記録の 2 行（`fixrules.POLICY_LINE`・`NO_POLICY_LINE`・`REQUEST_LINE`・`NO_REQUEST_LINE`）を、差し込むかを選ぶ段落に。範囲の節の見出し（`planrange.SCOPE_HEAD`）・頭の文・決まりの文（`OOS_ANY`）・許しの行の頭を md に。項目ごとの行は材料の札として Python に残した（英語の札）。
- 移した: 書く役の決まりの正本 `common.md` を共通の断片 `writer-rules` に（fix の役も使うので 2 つの block の断片。12 節の 1）。今の `refixrules.NOT_HERE`（`core-conflict` を載せない）は段落 `conflict` の false にした。
- 移した: 座の決まった文（`seat.HEAD`・`SKILL_LEAD`・`WINS`・`APPLIES`・`NOT_APPLIES`・`OVERLAY_HEAD`）を md へ。効く所・効かない所の箇条と読み替えの本文は、借りた写し（`lib/borrow/`）の字のまま値で入れる。
- 移した: 言語の 1 行（`rolekit.LANG_RULE` の汎用の欄の並び「reason・how・what・why・異議…」）を、この node の人に見せる欄（`how`・`bash_writes` の `why`）の名指しに。
- 移した: 穴の語 `inner_word`・答えの語 `fixed`・`declared`・字の下限を差し込み口に。
- 足した: `{shared:query-rule}`。この役は WebSearch・WebFetch を持つのに、今の指示は外への検索の決まり（対象の名を検索語に載せない）を持たなかった。共通の断片の決まり（`.shared/AGENTS.md`「役が web を引く時の決まりはここ」）に合わせた。
- 替えた: 材料の欄 `reads`（`loop.delta_owed`・`loop.fix_delta`）を材料から外した。md は `owed`・`diff_file` の上の段の欄だけを名指していた（今と同じ）。
- 消した: ほかの node の名（審査役は "the diff review"、2 回目の審査は "a second review" と言う）。
- 英語にした。役の名「手直しの役」は "the writer who touches up"。

### 3.7 元の works と graphloops の同じ場面

- graphloops の `p3.delta_fix.md`（14 行）: 義務の全部に 1 度ずつ fixed か declared で答える・足さずに消す形を先に考える・退行を注入して赤を見てから戻す、は同じ。違い: graphloops は義務を番号 `no` で指させ、旧い盤面の時の読み方の段落を持つ（工場は key を字のまま写させ、旧い盤面は無い）。graphloops に無く工場に在る物（書く役の決まりの正本・範囲の照らしと節・書き込みの出どころの突き合わせ・座・方針・名札・機械の穴・準拠の行）は、この block も全部持つ。
- 元の works の `works/blk-refix/`（2 往復の手直しと 2 回目の審査を 1 つのブロックに持ち、`refix-reads` で読んだ証拠を残した）: 工場は fix の中に 2 往復を置いた（#94）。この block は元と同じく 2 往復を 1 つの block に持つ。`refix-reads` は工場に無い（2.7 と同じ。（未確認））。
- 書き込みの出どころの突き合わせ（`bash_writes`・書き込みの記録）は、元の works が包みの書き込みの記録で縛った物を、工場が受け付けで照らす形にした（U6 の狭め）。この block も残す（keep-essence の 5）。

### 3.8 受け付け（`refix_accept.py` と `src/touchup.py`。n = 1）

1. 返答が読めない: 拒否（2.8 の 1 と同じ）。
2. 「手直しの返答の照らしに通らない:」と行の並びで拒む物（今の `delta_fix_problems` と `undeclared_refix`）:
   - `handled` の key の重なり・義務（`review-1-reply.json` から組む `owed_rows`）に無い key・答えの無い義務・fixed なのに `files` が空。
   - 段の頭の木（`refix-1-head.json` の `tree`）から変わったパス（`SKIP` の下を除く）が、`handled[].files` にも `bash_writes` の `path` にも無い（`UNDECLARED` の文）。
3. 範囲（今の `accept_fix` の 1 段目）: `base` から今までに変わったパス（`writes.changed`）のうち 1 回目の差分の `files` に無い物を、`planrange.outside(plan_items, paths, permits + ruled_paths, hint=False)` で照らし、外れが在れば `SCOPE_REJECT` と行で拒む。範囲の欄の無い run（`plan_items` が空）は照らさない。
4. 書き込みの出どころ（2 段目）: `writes.check(reply, repo, paths, log, skip=SKIP)`（`log` は `writelog.log_here()`、無ければ place の `writelog.LOG`）の `problems` が在れば拒む。
5. 受けた時の書く順: `refix-1-reply.json`（`bash_writes` を外した返答）→ `writes.trace(place, "refix-1", got)`（記録の無い run の知らせ）→ `trace.jsonl` に `refix_accepted`（`node`・`iteration`・`done`）。拒んだ時は `refix_rejected`。
6. 回数: `rolekit.accept_round(place, "refix-1", raw, take)`。3 回目で諦める。諦めた時は作業ツリーの手直しを戻さない（今も戻さない。受け付けの node `refix-1-accept` に `mutates_checkout: false` を書けるのはこれによる。手直しの役の node `refix-1` は作業ツリーを書くので書かない。13 節の 2 つ目）。2 回目の審査は回らない（`cut-2` が `refix-1-reply.json` を見つけず `due: false`）。
7. 諦めた時に出口へ書く物: `status: gave_up`・`reason` に諦めた文・`pass: false`（1 回目の審査の義務が残る）。

### 3.9 試験

10 節。この node に当たる物: 筋書き `two-rounds`・`RefixAcceptCase`・`RefixPromptCase`・10.3 の refix-1 の行。keep-essence の 5（9 節）。

## 4 node の設計シート: review-2（2 回目の審査役）

1. 役: 1 回目の手直しの直後に、手直しだけの差分を読み、手直しが新しく作った穴を挙げ、手直しが fixed と答えた穴を 1 件ずつ検算する。3 回目は無い。読むだけ。
2. port: `cut-2.json` の `file`・`files`・`review-2-brief.json`（欄 `diff_file`・`files`・`rev`・`base`・`handled`〔← `refix-1-reply.json` の `handled`。今の `reads.out.p3.delta_fix.handled`〕・`protected_files`・`policy`）・却下の控え `rejects-review-2.json`・`lang`。レンズの行と範囲の欄は載せない（手直しの差分にはレンズが当たらない。今のまま）。
3. 組み立ての順（`prompts/review-2.md`）: `{shared:rejected}`（条件 `rejected`）→ 役の定義（頭の 1 文 `You are the inspector for the diff of the touch-up.`・2 回目・3 回目は無い・読むだけ・写しとの比べ）→ `## Material`（`{diff_file}`〔修正後に固めた姿と手直し後の姿の差。修正の行は載っていない〕・`{files}`・`{brief_file}`〔`handled` の fixed・declared の意味。declared は検算しない〕・守りのファイルの段落は `{part:faces}` の中）→ 作業ツリーの今の姿 → `{part:faces}`（段落 `first` は false）→ 検算の段落（`{fixed}` と答えた穴を 1 件ずつ。key は `handled` の `{fixed}` の行から一字も変えずに写す・塞がっていなければ `closed: false`・2 回目の手直しが同じ key で答える・漏れは拒まれる）→ ここで挙げた穴への手直しはもう 1 度は審査されず、直したと言う物は次の run の依頼の下書きに載って次の run の判定で検算される（決まった文）→ `<!-- if rejected -->` 拒まれた所を直して丸ごと出し直す `<!-- end rejected -->` → `{part:policy}` → 言語の 1 文（`why`・`faces_none`・`checks` の `why`）→ 結び。
4. 返す形: 今の `review2` の `output_format` のまま（`workflows/fix/works-factory-fix.yaml:1160-1193`。`faces`・`faces_none`・`checks`。2 判定は無い）。
5. 描いた骨組み（例の run の値）: 変わったファイル 2 本（`tests/workflows/test_line.py`・`workflows/line/scripts/returned.py`）・`handled` 4 行（fixed 1・declared 3）・守りのファイル 0。役は穴 0 件・検算 1 件（`closed: true`）・`faces_none`（「fix-delta2.patch の 2 ファイル…」）で通った。骨組みは 2.5 の頭の 4 節と同じ形で、`## Two verdicts`・`## Borrowed template` の節が無い。
6. 今の指示との差: 今の `workflows/fix/commands/review2.md`（26 行）から、2.6 と同じ移し・まとめ（材料の差し込み口・`reads` の欄の名・却下の段落・断片 `faces`・`policy`・語の差し込み口・言語の 1 文）。方針の段落の見出し「付録: 人の方針」は、review-1 と同じ断片にしたので付録の語を外した。「次の run の依頼の下書き（報告の `next-request.json`）」はファイルの名を外し「次の run の依頼の下書き」にした（ほかの block の place のファイルの名を書かない）。
7. 元の works と graphloops の同じ場面: graphloops の `p3.delta_review2.md`（13 行）と元の works の `blk-refix` の review2。違いは 2.7 と同じ（番号の key・工場が足した物）。
8. 受け付け: 2.8 の 1・2・4・5・6 と同じで n = 2（2 判定は無い。塞いだと言われた穴は `refix-1-reply.json` の `handled` の fixed の key。機械の穴は `base` から 2 回目に固めた姿まで、修正か手直しが触ったファイルの差分に当てる〔今の `_added_text` の n = 2〕。拒否の字の頭は今のまま）。書く順は `review-2-reply.json` → `review-2.json`。諦めた時は `status: gave_up`・`rounds: 2`・`pass: false`。
9. 試験: 筋書き `two-rounds`・`ReviewAcceptCase` の 2 回目の行・10.3 の review-2 の行。

## 5 node の設計シート: refix-2（2 回目の手直しの役）

1. 役: 2 回目の審査の穴（機械の穴を含む。修正と手直しを合わせた差分の足した行に見つけた内側の語で、1 回目の手直しが直したと答えて残った語も入る）と塞がっていなかった検算の全部に答えて直す。
2. port: `refix-2-brief.json`（欄 `diff_file`〔手直しの差分〕・`owed`・`ties`〔1 回目の名札と 1 回目の手直しの `handled` から `holeties.earlier` で結ぶ〕・`policy`。範囲の欄と準拠の行は載せない。今のまま）・方針・依頼・範囲の節の行（今も n によらず貼った）・却下の控え・座・`lang`。
3. 組み立ての順（`prompts/refix-2.md`）: `{shared:rejected}` → `{part:refix-before}` → 役の頭（頭の 1 文 `You are the writer who touches up the holes the second diff review raised.`・材料の欄 `owed`・`diff_file`・`ties`・方針の段落）→ `{part:refix-rules}` → 返答の後に当たる物（今の `refix-tail-2`: ここで直した物はこの run ではもう差分の審査が当たらず、直したと言う物は次の run の依頼の下書きに載り、次の run の判定が 1 件ずつ振り分ける）→ 結び。
4. 返す形: 今の `refix2` の `output_format` のまま（refix と同じ形）。
5. 描いた骨組み: 記録の在る run のどれでも 2 回目の手直しは走っていない（置き場に `prompt-p3.delta_fix2.md` の在る run が無い）。例の run の 2 回目の審査が仮に `closed: false` の検算を 1 件返したとして描く（仮の値: 義務 1 `returned-silent-fallthrough-to-got-path`・手直しの差分 `<place>/delta-2.patch`・名札 1「項目 2」）。節の並びは 3.5 から範囲の欄の説明と準拠の行を除いた物。
6. 今の指示との差: 3.6 と同じ（節 `refix-head-2` と `refix-tail-2`）。今の `refix-head-2` の材料の行で `diff_file` が 2 回並んでいた（「材料」の中の `diff_file` と「手直しの差分: <<diff_file>>」）のを 1 回にした。
7. 元の works と graphloops の同じ場面: graphloops の `p3.delta_fix2.md`（9 行）・元の works の `blk-refix` の refix2。3.7 と同じ。
8. 受け付け: 3.8 と同じで n = 2（義務は `review-2-reply.json` から・段の頭の木は `refix-2-head.json`・範囲の照らしで除くのは 1 回目の差分の `files`〔今の `accept_fix` は n によらず 1 回目の差分の files を除いた〕）。書く順は `refix-2-reply.json` → `writes.trace` → `trace.jsonl`。諦めた時は `status: gave_up`。3 回目の審査は無いので、受けた fixed の行は `carry` の「検算が要る」の行になる。
9. 試験: 筋書き `two-rounds`・`RefixAcceptCase` の 2 回目の行・10.3 の refix-2 の行。

## 6 script の node

1. `intake.py`:
   1. place を作り、1.4 の名のファイルと指示のファイル（`review-*-prompt-*.md`・`refix-*-prompt-*.md`）だけを名で引いて消す。
   2. port を `os.environ.get("INPUTS_BASE")` などの字のままで読む: `base` は `ports.text` の後に `git rev-parse --verify <base>^{tree}`（読めなければ「入力 base: 版として読めない」）、`plan` は `materials.scope`、`lens_rows` は `materials.lens_copy`、`fix_reply` は `materials.fix_reply`、`permits` は `materials.permit_paths`、`plan_review` は `ports.json(raw, "plan-review.schema.json")`、`policy` は `ports.file` の先を `materials.policy_brief`、`request` は `materials.request_copy`、`lang` は `prompt.lang` に渡す。読めない port は、どの port かを頭に付けた理由（「入力 plan: …」）で `intake.json` に `{failed: true, due: false, reason}` を書き、`{due: false, reason}` を返す。
   3. 写し: `scope.json`（範囲の欄。修正案が無ければ `{plan_items: [], ruled_paths: [], agreed: []}`）・`fix-reply.json`（null でない時）・`permits.json`（パスの並び）・`plan-review.json`（null でない時）・`request.json`・`lens.json`。
   4. `writelog.open_here()`（記録の根が在れば、作業の場の書き込みの記録を空で作る。在れば触らない。今の fix の `prep.py` と同じ）。
   5. `cut.due(repo, base, <fix-reply.json の値>)` が偽なら `skipped.json` に `{reason}` を書き、`intake.json` に `{due: false, failed: false, reason}`、返り `{due: false, reason}`。
   6. `cut.cut(place, 1, repo, base)` → `cut.brief(place, 1, …)` → 作業ツリーの写し `review-1-tree.json` → `intake.json` に `{due: true, failed: false, …}`。返り `{due: true, reason: ""}`。
   7. 2〜6 のどこかの例外は落ちずに `errors.json` に `{node: "intake", reason}` を積み、`intake.json` に `failed: true` を書いて `{due: false, reason}` を返す（`ports.run` の fallback）。
2. `review_prep.py`（`INPUTS_N` は `1` か `2`。ほかは字で名指して落ちる）: `intake.json`・`review-<n>-brief.json`・`cut-<n>.json`・却下の控えを読み、2.3（n = 2 は 4 節の 3）の値と `when` で `prompt.emit(f"review-{n}", values, when, prompt.round_of(f"review-{n}"))` を呼び `{prompt}` を返す。n = 1 は座の材料を `borrowed` から組む（写しが固定と違えば落ちる）。組めなければ `errors.json` に node と訳を積んでから非 0 で落ちる（輪が落ち、`finish` が訳を名指す。world の `prompt-error.json` と同じ働き）。
3. `review_accept.py`（`n`・`reply`）: 2.8。`ports.run` の fallback は `errors.json` に積んで `{ok: false, done: true, reason}`。
4. `owed.py`（`n`）: `review-<n>.json` が無い・`pass` が真・`gave_up` なら `{due: false, reason}`（訳は「<n> 回目の審査が直す義務を出していない」など）。義務が在れば `refix-<n>-head.json` に `{tree: leftovers.snapshot(repo)}`、`refix-<n>-brief.json`（3.2・5 節の 2）を書き `{due: true, reason: ""}`。名札が組めなければ `ties: []` と `ties_error` を置いて先へ（今のまま）。ほかの例外は `errors.json` に積んで `{due: false}`。
5. `refix_prep.py`（`n`）: 3.3（n = 2 は 5 節の 3）の値と `when` で `prompt.emit(f"refix-{n}", …)`。範囲の節の行は n によらず `touchup.scope_lines(plan_items, permits + ruled_paths)`。組めなければ 2 と同じ。
6. `refix_accept.py`（`n`・`reply`）: 3.8。
7. `cut2.py`: `refix-1-reply.json` の `handled` に fixed の行が無ければ `{due: false, reason: "1 回目の手直しが fixed と答えた穴が無い"}`。在れば `cut.cut(place, 2, repo, <cut-1.json の rev>)` → `cut.brief(place, 2, …)` → `review-2-tree.json` → `{due: true}`。1 回目の差分の控えが無い・git が落ちる時は `errors.json` に積んで `{due: false}`。
8. どの script も、Archon の環境変数を名を組んで読まない（`INPUTS_N`・`INPUTS_REPLY` などを字のまま）。
9. `finish.py`（落ちない。`ports.run` の fallback は標準ライブラリで `{ok: false, status: failed, …}` を返す）:
   1. `intake.json` が無い・`failed` → `status: failed`・`reason` はその訳・`rounds: 0`・`pass: false`・`holes`・`diff` は null。
   2. `skipped.json` が在る → `status: ok`・`rounds: 0`・`pass: true`・`reason` はその訳・`holes: null`・`diff` は累積の差分（空なら null）。
   3. ほかは往復ごとに: `review-<n>.json` が在れば回った往復。無くて `rejects-review-<n>.json` に拒否が在れば、受け付けずに輪が終わった往復（`gave_up` に数え、`reason` は諦めた文か最後の拒否の文）。`rounds` はその数、`pass` は最後の往復の控えの `pass`（控えが無ければ false）。
   4. `errors.json` に行が在れば `status: failed`（`reason` は最初の行の node と訳）。在らず、どれかの往復の審査か手直しが諦めていれば `gave_up`。回るはずの輪（`intake` が `due` を返した）の控えも拒否も無ければ `failed`（「審査の受け付けの控えが無い（役が走らなかったか落ちた）」）。ほかは `ok`。
   5. `holes.json`: 往復ごとに `ties[n]` = `touchup.hole_ties(place, n, …)`（組めなければ `"<型>: <訳>"` の字）・`handled[n]` = `refix-<n>-reply.json` の `handled`（無ければ `[]`）。今の `fixbeside._ties` と同じ形。
   6. `delta.diff`: `base` から今の作業ツリーの姿まで（`cut._cut_delta` と同じ手続き。空なら書かずに null）。
   7. `carry` と `report`: `src/summary.py` が組む（下）。
   8. 返り: `{ok: status != "failed", status, reason, rounds, pass, holes, diff, carry, report}`。

`report` の行（日本語。今の字のまま）:

1. 頭の 1 行: 回った時は「差分の審査: <rounds> 回（最後の審査は通った|通らなかった）」、飛ばした時は「差分の審査: 回っていない（<飛ばした訳>）」、入口で壊れた時は「差分の審査: 落ちた（<訳>）」（今の `ask_final.delta_lines` の頭。「審査を省いたか、変更の確かめが通らなかった」の訳は line の行になる）。
2. 往復ごとの名札と手直しの結果（今の `fixbeside.branch_rows` の字: 1 往復目の頭は「差分の審査の穴の枝（機械が修正案の項目に結んだ名札。手直しの役にも同じ名札を渡した）」、2 往復目は「2 回目の審査の穴の枝」、件数の行 `holeties.count_line`・穴ごとの行 `holeties.lines` を `  - ` で、「手直しの結果（<n> 件）:」「2 回目の手直しの結果（<n> 件）:」と `  - <key>: <HANDLED_WORDS の語>（<handled>）——<how の 1 行>`。組めない名札は「…: 組めない（<訳>）」）。
3. 諦めた役が在れば「<差分の審査|手直し>（<n> 回目）が 3 回拒まれて諦めた: <最後の拒否の 1 行>」。
4. レンズの数え: `lens_rows` が渡された時は `lens.count_line(lens.summary(place, <review-1-reply.json か None>))` と、レンズごとの「  - <lens>: 採った <a>・採らなかった <b>・形の誤りで捨てた <d>（出した発見 <f>）」（今の `fixbeside.always_rows` のレンズの行）、読めなかった時は「レンズの控えが読めない（<訳>）。どのレンズが見たかを確かめられない」。どちらにも `lens.REFIX_NOTE`（「手直しの差分にはレンズが当たらない（最後のテストで守る）」）を足す。渡されていない時は「レンズを走らせていない（控えが無い）」。

`carry` の行（今の `fixbeside.next_items` の手直しの部分の字）: 往復ごとの `handled` の行のうち declared は `{where: <files の頭か key>, text: "<key>（手直しが declared で残した穴: <how>）（枝: <名札>）"}`、2 往復目の fixed は `{where, text: "<key>（手直し 2 回目が fixed と言ったが、3 回目の審査は無い——検算が要る: <how>）（枝: <名札>）"}`。レンズの控えが読めなかった時は `{where: "レンズ", text: "レンズの控えが読めない——再実行の要あり: <訳>"}`。

`finish` の `output_format`: `required` は全部の欄。`status` は `enum: [ok, gave_up, failed]`、`rounds` は `{type: integer, minimum: 0, maximum: 2}`、`holes`・`diff` は `type: [object, "null"]` に pointer の 3 つの欄、`carry` は `{where, text}` の object の配列、`report` は字の配列。ほかの script の node の返りは、どれも `additionalProperties: false` で全部の欄を `required` にする。

## 7 今の工場との比べ（確かめ・守り・落ちた時・書く順）

今の fix の差分の審査の段が持つ物を 1 つずつ、どこに置くかを書いた。

1. 戻せず当たったままの組が在れば審査を回さない（`fixboard.held`）→ line の `when:`（1.6）。fix の止めの語の事実。
2. 変更の確かめ（`assert-changed.json`）が ok でなければ回さない → line の `when:`。
3. 修正の後の信号で深さを上げ、頭が軽量で全部の単位が軽量なら省く（`fixboard.redepth`・`depth-raised.json`・`skipped.json`）→ line（README の形の直し 5）。省いた印は line の記録になり、この block には来ない。
4. 差分が空で塞いだと言う穴も無ければ審査役を起こさない（`delta_review_due`）→ この block の `intake`（6 節の 1 の 5）。訳の字も同じ。
5. 審査を回さない時のレンズの集め役の事実（`LENS_NOT_DUE`）→ line が lens を include しないので要らない。報告の「レンズは起こさない」の行は line が `when:` の訳から組む。
6. 前の試みの自分の出力を消す（`_drop_stale`・`lenses.json` の頭の消し）→ `intake` が名で引いて消す。
7. 差分の起点が無い・差分を切れない・修正案の欄の控えが壊れた → 今は node が非 0 で run が止まる。新しい形は `status: failed`・`ok: false` で、line が止める（同じ結果）。修正案の欄の凍結の印との食い違い（`planmarks.FieldsBroken`）は、項目を作る側（line が渡す pointer の作り手）の照らしになり、この block は渡された項目の形だけを照らす。
8. 読むだけの役の前の作業ツリーの写しと、受け付けでの比べ（`snapshot`・`take`・`READONLY_MOVED`・比べる欄 `BEYOND_STATUS`）→ `intake`・`cut2` と `src/review.py`（同じ）。
9. 材料の欄（差分・変わったファイル・事前審査・修正役の答え・守りのファイルと読めない訳・レンズの行と読めない訳・承認済みの項目と `held`・`held_units`・裁定のパス・相談の合意・修正の報告・方針）→ 2.2（欄の名の入れ子だけ替えた）。
10. 座の写しが固定と違えば止める（`seat.pinned`）→ `review_prep`・`refix_prep` が落ちて `failed`。
11. 審査の照らし（key の重なり・事前審査だけの語・where・cite・faces_none・検算の過不足）→ 2.8 の 2（同じ字）。
12. 2 判定の照らしと、受けた時だけ控える・控えが書けなければ進ませない → 2.8 の 3・5。
13. 機械の穴（内側の語）を受ける返答に足す・対象が前から使う語は数えない → 2.8 の 4。
14. 審査の控え `{pass, owed, reply_file}` と諦めの控え → 2.8 の 5・6（同じ形）。
15. 3 回拒まれたら諦める（`rolekit.accept_round`）→ どの受け付けも同じ。
16. 手直しを起こすのは義務が在る時だけ（`refix-prep` の `go`）→ `owed-n` と輪の `when:`。
17. 手直しの段の頭の木を 1 回目に控える（`REFIX_HEAD_FILE`）→ `owed-n`。
18. 手直しの材料（義務・差分・名札と組めない訳・方針・範囲の欄・準拠の落ちた行）→ 3.2・5 節の 2。
19. 手直しの指示の組み立て（始めの記録の 2 行・範囲の節・役の頭・正本・読み替え・手直しだけの決まり・座・返答・返答の後・拒否・言語）→ 3.3（3.6 の差のとおり）。
20. 起こさなかった手直しの受け付けは done（`not_launched`）→ 輪ごと `when:` で飛ぶので要らない。
21. 手直しの照らし（義務への答えの過不足・fixed の files・申告の無い書き込み・範囲・書き込みの記録）と書く順 → 3.8（同じ）。
22. 2 回目の差分は fixed が在る時だけ切る・起点は 1 回目に固めた姿 → `cut2.py`。
23. `{rounds, pass}` の数え（控えの数と最後の pass・飛ばした時は `{0, true}`）→ `finish`（同じ。輪が受け付けずに終わった往復も数える所だけ足した。6 節の 9 の 3）。
24. 名札と手直しの結果の控え（`delta-holes.json`。組めなければ訳）→ `holes.json`（同じ形）。
25. 報告・最後の承認ノード・次の依頼の行（`branch_rows`・レンズの数え・`next_items`・`delta_lines`）→ この block の `report`・`carry`（README の 4.1: 報告の文は事実を持つ block が組む）。
26. 書き込みの記録を空で開く（`writelog.open_here`）→ `intake`。
27. 柵の node `nodes-ok`（どれかの節が落ちた run で fix の出口に落ちを出す）→ 要らない。`finish` が `errors.json`・控えの無さから `status: failed` を返す。
28. 返答が JSON として読めない時に run を止める → 拒否にする（2.8 の 1。ほかの block と同じ）。

落とした物は無い。替えたのは 7（止める所が node の落ちから line の `ok` の読みへ）と 28（止めずに拒む）。

## 8 単独で呼ぶ

```sh
WORKS_FACTORY_FOLDER=blocks bin/works-factory workflow run works-factory-delta-review --cwd <対象> \
  --input base=<修正の前の木か commit> \
  --input plan=<承認済みの項目の JSON のファイル> --input lens_rows=<レンズの行のファイル>
```

出力は `workflow get <run>` の `finish` の返り。始めの記録は要らない。`plan` を渡さなければ準拠は `not_applicable` で範囲は照らさない。`fix_reply` を渡さなければ検算する穴は無く、差分が空なら審査を飛ばす。

## 9 守る keep-essence と、ほかの block との約束

- 5（書き込みの出どころの突き合わせ）: 手直しの受け付け（3.8 の 2 の申告の無い書き込み・4 の `writes.check`）。`lib/writes.py` は KEEP。
- 3（テストの凍結と、許す道は 1 本）: テストの変更の許しを数えるのは修正の block だけ（`conflict.test_permits`）。この block はその結果のパスを port `permits`（fix の返りの `allowed_tests`）で受けて範囲の照らしに使うだけで、許しを自分で数えない（「1 本」が block をまたいで 2 本にならない）。
- 10（守りのファイルに触れたら最後の承認ノードを開く）: 担うのは merge。この block は審査役の材料に守りのファイルを載せ、検査を緩める変更を穴にさせる（今のまま）。
- 11（直す単位ごとの記録が報告に届く）: この block の `report` と `holes` が、差分の審査の分を報告と最後の承認ノードに運ぶ。

## 10 試験と、済んだと言える条件

### 10.1 standalone の fixture（`blocks/delta-review/fixtures/`）

どれも `exec-code: true`・prep を差し替えない・AI の node の返答だけを差し替える。入力の `base` は `HEAD`（筋書きの作業ツリーは commit した直後で、差分は空）、`fix_reply` は `'{"changes": [], "not_done": [], "plan_faces": [{"key": "claimed-closed-hole", "handled": "absorbed", "how": "The fix says it closed this hole."}]}'`（塞いだと言う穴が在るので、差分が空でも審査が回る）。

- `standalone.stubs.yaml`: `expect: completed`・`reached: [intake, review-1-prep, review-1, review-1-accept, owed-1, finish]`。`resolved-text-contains` の `review-1` は `You are the inspector for the diff of this round's fix.`。審査役の返答: `faces: []`・`faces_none`（20 字以上）・`checks: [{key: claimed-closed-hole, closed: true, why: (20 字以上)}]`・`compliance: {verdict: not_applicable, items: [], read: (20 字以上)}`・`quality: {verdict: pass, why: (20 字以上)}`。
- `two-rounds.stubs.yaml`: 4 つの役に届く。審査役 1 回目は同じ key を `closed: false` で返し（義務 1）、手直しの役 1 回目は `handled: [{key: claimed-closed-hole, handled: fixed, how: (20 字以上), files: [README.md]}]`、審査役 2 回目は `checks: [{key: claimed-closed-hole, closed: false, why}]`・`faces: []`・`faces_none`、手直しの役 2 回目は declared。`reached` に `review-1`・`refix-1`・`cut-2`・`review-2`・`refix-2`・`finish`。`resolved-text-contains` は 4 つの役の md の頭の 1 文（2.3・3.3・4 節の 3・5 節の 3）。
- `gave-up.stubs.yaml`: 審査役 1 回目が `where` に変わっていないファイルを書いた穴を返す。dry-run の輪は 1 周なので拒否は 1 回で、`finish` が `status: gave_up`（6 節の 9 の 3）を返し、run は `completed`。3 回で諦める数えは `ReviewAcceptCase` が見る。
- 筋書きは完了・`reached`・指示の字だけを見る（`blocks/AGENTS.md`）。

### 10.2 `tests/blocks/delta_review/`（`kit.Run` で script を子のプロセスで回す。始めの記録は置かない）

使い捨ての git のリポジトリに数本のファイルを commit し、`base` にその commit を渡して、作業ツリーのファイルを書き換えてから回す。

- `IntakeCase`: 読めない port ごとの `failed` と、port の名を頭に付けた訳・`base` が版でない時・差分が空で検算も無ければ `skipped.json` と `due: false`・差分が空でも `absorbed` が在れば回る・`.archon/` の下の変更は差分に載らない・未追跡の日本語の名のファイルが差分に載る・前の回の自分のファイルを消し、ほかの名のファイルは消さない・材料の欄（`plan_items` の `held`・`held_units`・合意を足した `allowed_paths`・`out_of_scope_lifted`・`ruled_paths`・`agreed`・`fix_report`・`plan_review`・`plan_faces`・守りのファイルと対象が宣言した守りのファイル・レンズの行と読めない訳）。元: `lib/tests/test_blk_tests_delta.py` の `TestDeltaPlace` の cut の全部・`test_blk_refix.py::test_cut_leaves_out_the_runtime_copy`・`test_blk_lens.py` の `test_cut_brief_carries_lens_rows`・`test_cut_brief_without_lens_run_and_broken_file`・`test_review2_brief_has_no_lens`・`tests/workflows/test_fix.py::DeltaScriptsCase.test_delta_cut_passes_the_plan_review_to_the_brief`。
- `ReviewAcceptCase`: 2.8 の照らしの全部（事前審査だけの語の 3 つ・where・cite・faces_none・検算の過不足）・作業ツリーが変わったら拒む・写しが無ければ拒む・機械の穴が義務になる（1 回目の差分の足した行・2 回目に 1 回目の手直しが足した語・直したと答えて残った語）・3 回目で諦めて控えに `gave_up`。元: `test_fix_seams.py::DeltaSeamCase` の `test_delta_review_problems_check_where_cite_and_checks`・`test_delta_review_rejects_every_plan_only_kind`、`test_blk_tests_delta.py` の `test_review_readonly_tree_changed`・`test_accept_review_needs_the_snapshot`、`test_blk_refix.py` の `test_inner_word_*` の 3 本・`test_owed_rows_come_from_the_accepted_review`・`test_review_none_owes_nothing`、`test_fix.py::DeltaScriptsCase.test_delta_accept_fails_the_pass_on_an_inner_word`。
- `VerdictsCase`: `src/verdicts.py` の `gaps` の決まりの全部と、受けた時だけ控える・控えが書けなければ `errors.json`。元: `lib/tests/test_delta_marks.py` の全部・`test_blk_tests_delta.py` の `test_accept_review_strips_and_saves_verdicts`・`test_accept_review_rejects_missing_verdicts`・`test_old_plan_fields_accept_not_applicable`・`test_missing_on_held_item_is_rejected`・`test_unsaved_verdicts_raise`。
- `RefixAcceptCase`: 3.8 の全部（義務への答えの過不足・fixed の files・申告の無い書き込みを拒み申告した書き込みを通す・記録の無い run の知らせ・範囲の外・`out_of_scope`・範囲の中・裁定のパスを通す・修正の段のファイルは照らさない・範囲の欄の無い run は照らさない・書き込みの記録のファイルを読む）。元: `test_blk_refix.py::RefixCase` の `test_refix_*` の 8 本、`test_fix.py` の `test_refix_undeclared_write_is_rejected`・`test_refix_accepts_read_the_recorder_log`・`test_cut_review_refix_rejects_outside_the_range_then_accepts`、`test_fix_seams.py::DeltaSeamCase.test_delta_fix_problems_answer_every_owed_key_once`。
- `RefixPromptCase`: 組んだ指示に方針の写しのパス（無い時は無いと言う文）・依頼の写しのパス・範囲の節の項目の行（受け付けが照らす値と同じ値: `test_fix_seams.py::test_refix_scope_text_lists_what_check_paths_lets_through` の写し）・却下の理由の全部（3 回目は 2 件とも。`test_fix.py::test_third_refix_prompt_names_every_reject_of_the_loop`）・`writer-rules` の段落 `conflicts` が入らない・座のスキルの名・言語の文。名札が義務の穴に結ばれる（`test_fix.py::test_refix_preps_tie_holes_through_the_plan_review`・`test_blk_refix.py::test_compliance_fail_reaches_ties`・`test_review2_then_ties2`）。
- `RoundsCase`: `cut2` は fixed が無ければ回さない・2 回目の差分は手直しだけ（`test_blk_refix.py::test_cut2_is_refix_only_diff`・`test_cut2_needs_the_first_cut`）・declared だけなら 2 回目を回さない（`test_fix.py::test_declared_only_refix_skips_review2`）・3 往復目が無い（`test_no_third_pass`）。
- `FinishCase`: 6 節の 9 の `status`・`rounds`・`pass` の全部の道・`holes.json` の形（組めない名札は訳の字）・`delta.diff` と空の時の null・`carry` の行・`report` の行（頭・名札・手直しの結果・諦め・レンズの数えと採った件数〔`test_blk_lens.py::test_summary_counts_adopted_by_lens_field`・`test_count_line_always_names_failed_lens_count` の写し〕）。include された時は place が include の道に分かれる。元: `test_fix_seams.py::test_delta_review_counts_rounds`。
- `ShapeCase`: YAML の `kind` の enum が `src/review.py` の `FACE_KINDS` の並び・`compliance` と `quality` の enum が `verdicts.COMPLIANCE`・`QUALITY`・`handled` の enum が `touchup.HANDLED`・輪の `max_iterations` が `rolekit.GIVE_UP_AFTER`・AI の node の鍵（群・`settingSources`・道具・`skills`・sandbox・`idle_timeout`・`mutates_checkout`・`retry`）が 1.3 のとおり・輪の中が prep → 役 → accept の 1 本。
- `PortsCase`: 3 つの形のファイルが `KNOWN_KEYWORDS` だけで書かれている（形の検査も見る）・入力の鍵がちょうど 1.2 の 9 つ・`plan` に項目の配列だけを渡しても、範囲の欄の object を渡しても同じ照らしになる・`permits` に行の配列を渡しても字の配列を渡しても同じパスになる。
- 写さない試験（古い中身だけを見る）: `test_fix.py::test_lens_nodes_match_the_lens_table`・`test_refix_rounds_share_one_script`・`test_refix_texts_are_unchanged_for_both_rounds`（日本語の節の字）・`test_delta_cut_skips_an_all_light_run`・`test_delta_cut_reviews_an_all_light_run_under_a_standard_head`・`test_delta_cut_raises_the_depth_before_skipping`・`test_delta_cut_does_not_mark_a_failed_change_check_as_light`（line の上げ直しの試験へ）・`test_delta_review_reads_the_seat_file`（座は指示の中の節になった。`RefixPromptCase` と review-1 の指示の座の節の照らしで替える）・`test_fix_seams.py` の `test_refix_prompt_fills_the_head_and_names_the_reject_file`・`test_refix_prompt_names_the_policy_and_ends_with_the_language_line`（`rulebook` の頭の行と日本語の字。`RefixPromptCase` で替える）・`test_blk_tests_delta.py::test_broken_plan_fields_name_the_stage`（凍結の印の照らしは項目の作り手へ）・`test_blk_tests_delta.py::test_cut_writes_the_seat_file`（座のファイルは作らない）。
- 指示の比べの試験（日本語の md で同じ字）は作らない（wave 2 の持ち主の決め「速さ」。審査が 10.3 の一覧で新旧を並べて見る）。

### 10.3 英語の md が残す古い指示の一覧（審査が 1 つずつ照らす）

審査は、古い指示（今の md と `fix-rules/` と座）と新しい md を同じ値で組んで並べ、下の行が新しい md に在るかを 1 つずつ見る。ここに無い差は 2.6・3.6・4 節の 6・5 節の 6 の物だけ。

review-1（今の `commands/delta-review.md` と座）:

1. 審査役で、修正の直後にこの周の修正だけの差分を見て、修正が新しく作った穴を同じ周のうちに見つける。
2. 読むだけで、ファイルを書く・消す・git を動かすことはしない。受け付けは役を起こす前に撮った作業ツリーの写しと今の作業ツリーを比べ、変わっていれば返答を拒む。
3. 修正の差分は Read する。周の頭に固めた版と同じ手続きで固めた修正後の姿の差で、未追跡の新規ファイルも載る。日本語のパスは git の引用の形で出るので、名前は一覧の字を使う。
4. 材料は Read する JSON。事前審査で予測された穴（null なら事前審査は無い）と、その穴への修正役の答え（absorbed は塞いだと言う・declared は残す）。
5. 守りのファイルの段落（緩める変更の 4 つの例・穴にする・`kind` は 5 つの語・最後の承認ノードにも必ず出る）。
6. レンズの段落（利用者が入れた pr-review-toolkit の agent を 1 本ずつ独立に起こした局所レビューの行・無検算で写さない・差分と今の姿で確かめる・当たっていれば穴にし `lens` にレンズの名を一字も変えずに写す・機械が採った件数を数える・`failed`・`not_routed` の観点は誰も見ていない・空なら走らせていない・`lens_error`）。
7. `plan_items` の欄の説明（項目の番号・単位・やり方・files の op と symbols と why・受け入れのテスト・書き換えてよいテスト・範囲・触らない物・空なら修正案は無い・`held`・`held_units` の扱い・合意を足した `allowed_paths`・`out_of_scope_lifted`）。
8. `ruled_paths`（範囲が広がるのはこのパスと合意だけ）・`agreed`（行の欄・`agreed` の tests は許しで義務ではない・空なら合意は無い）・`fix_report`（主張であって証拠ではない）。
9. 型の手順で審査する・ぶつかる所はこの指示が勝つ（返す形・読む義務・"Do not crawl the broader codebase" と「変わったファイルを別に Read しない」は効かない・判定の欄の値は行で決まり、表と行が食い違えば行・`plan_items` が空なら `not_applicable`・結ばれない穴が在れば `fail`）。
10. 読むのは作業ツリーの今の姿。周の頭に固めた版には修正が載っていない。cite は今の姿で引かれる。
11. 今まで修正が作った穴は次の周の全体レビューで初めて見つかり、次の周の修正がまた穴を作った（実測 2026-09-24: 3 周目の指摘のうち 8 件が 2 周目の修正の産物）。
12. 見るのは 3 点と品質の観点だけ。後退・方針・先行例は事前審査だけの語で受け付けない。修正の後の後退は後の段が人に上げる。
13. 写し・入口・宣言と実装のずれの定義（読む側の例: プロンプトの案内・拒否文・文書・テスト・docstring）。
14. absorbed と答えた穴を 1 件ずつ検算する・塞がっていなければ `closed: false`・手直しが同じ key で答える・faces に書き直さなくてよい・漏れは拒まれる。
15. 差分は起点であって境ではない。読む側・呼び元まで読む。
16. 先に準拠、次に品質の順で判じ、準拠の外れを品質の穴と混ぜない。
17. 準拠は `fix_report` を信じずに差分と今の姿を読む・外れを 1 件ずつ 1 行・`missing`・`extra`・`misunderstood`・`unverifiable` の定義。
18. `held` の項目と `held_units` の単位には落ちた行を書かない（受け付けが拒む）・`ruled_paths` と合意のパスの変更は `extra` にしない・`agreed` の tests は `missing` にしない。
19. 落ちた行は穴にも挙げ（`extra` は `scope_creep`、ほかは `contract_drift`）、key を `face_key` に一字も変えずに写す・触っていないファイルの `missing` は項目の変わったファイルのうち最も近い物を `where` に・変わったファイルが無ければ `unverifiable`・`unverifiable` の `face_key` は空の字で鍵は省かない。
20. 判定は行から決まる（落ちた行が在れば fail・無くて unverifiable が在れば unverifiable・無ければ pass・項目が空なら not_applicable と空の行）・`read` に何を読んで判じたか（20 字以上）。
21. 品質は 3 点に加え、足したテストが本物の経路を通るか（mock の戻り値を断言していないか・文言の比べに寄っていないか）と保守のしやすさ・テストの形と保守性の穴は `contract_drift`・結ばれない穴が在れば fail・`why` に見た所（20 字以上）。
22. 穴の行の書き方（key 8 字以上で一意・kind の 5 語と `dead_path`・`scope_creep` の定義・`lens` はレンズから採った穴だけ）。
23. `where` は変わったファイルのパスだけ（行番号・関数名・何か所かは `why`）・受け付けはパスの完全一致・変わっていないファイルの穴は挙げない。
24. `cite` はそのファイルの今の姿に在る字列そのまま（4 字以上）・言い換え・要約・省略をしない。
25. `checks` の key は absorbed の行の key を一字も変えずに写す・無ければ空。
26. 穴が無いなら `faces` を空にし `faces_none` に何を読んで無いと言えるか（20 字以上。読んだファイル・読む側・呼び元の名）。
27. compliance と quality を必ず書く・落ちた行は face_key で結ぶ・結ばない外れは拒まれる・判定の語と行が合わなければ拒まれる。
28. 拒まれた時は、理由を読み、挙がった所を直した返答を丸ごと出し直す・拒まれた穴を黙って消さない・where か cite が合わないなら今の姿を Read し直して正しく引く。
29. 人の方針の段落（run をまたいで効く・本文は `policy.paste`・切り詰めと続きの置き場・`policy.path`・先に全部読む・発行者が守らせる制約・方針に照らす・ぶつかる項を `why` に・方針の文書を書き換えない）。
30. 座: 型の本文・判定の語の表と注の 2 行・読み替えの頭の 1 文（直の指示でスキルより勝つ・下請けには読み替えのファイルを Read せよと書く）と本文。

refix-1（今の `refix.md` の節と `common.md` と座と組み立ての口の文）:

1. 方針の文書のパス（先に全部読む）か「無い」・依頼の文のファイルのパス（先に全部読む）か「無い」。
2. 範囲の節: 受け付けは変えたパスをこの値で照らし外れを拒む・`out_of_scope` は範囲より強く許しにも勝つ・どの項目の `out_of_scope` も変えた全部のパスに当たる（相談で外したパスだけはその項目で当たらない）・相談で許されたパスとテストの許しもここに入る・項目ごとの単位・範囲・テストのファイル・触らない物（理由つき）・外したパス・全部の項目に効く許し（テストの変更の許しと直す裁定が足したパス。out_of_scope には勝たない）。
3. 役の頭: 手直しの役（writer）で、差分の審査が挙げた穴（審査役の穴と機械の内側の語の穴）と塞がっていなかった検算を同じ周のうちに直す。
4. `owed` は答える義務の全部（key・from・text）・内側の語の行は `text` と `key` の頭にその語・足した行の字を対象の読み手に通じる言い方に言い換えて fixed で答える・declared で残すと審査が通らないまま残り、run は fixed で終われない。
5. `diff_file` は周の頭に固めた版と修正後の姿の差。
6. `plan_items`: 準拠の外れの義務は項目どおりに直す・`held` の項目に向けて直さない（declared で残し、`how` に `held` を写す）・`held_units` の単位も同じ（理由を写す）。
7. `ruled_paths`: 範囲の外で変えてよいのは範囲の節に載るパスだけ・範囲の相談はできない・ほかに範囲の外が要る穴は declared と理由・受け付けが修正の段の触ったファイルの外を範囲の和と `out_of_scope` で照らし外れを拒む・試験を回して出来たファイルも消す。
8. `agreed` の行の欄と、`agreed` の tests は許しで義務ではない・空なら合意は無い。
9. `compliance`: 審査が外れたと見た行・`face_key` が義務の key と同じ行は、その項目への準拠として答える。
10. `ties`: 穴ごとの枝の名札・機械が穴の場所と範囲と変更から結んだ・直す時にその項目の範囲と約束を先に読む手がかり・答え方は変えない（義務の全部に答える）。
11. 方針: 在れば先に全部読む・方針に反する物・方針を変えないと成り立たない物を自分の判断で通さない・ぶつかる穴は declared でどの項とぶつかるかを `how` に・方針の文書を書き換えない。
12. このノードが在る理由（持ち越すと次の周の全体レビューが新しい指摘として挙げ、次の修正がまた穴を作る。同じ周のうちに閉じる）。
13. `writer-rules` の全文（今の `common.md` の `core-fix`・`evidence` と 4 種・`core-keep`。`core-conflict` は入れない）。
14. 読み替えの頭: 上の決まりは判定の単位を直す役の欄と受け付けを所与に書いてあり、この役は違うので読み替える。
15. 読み替え 1: 判定の単位と直す義務の単位は `owed` の行・`text` が名指す穴を根として塞ぐ・同じ形は自分で検索して全部引く（`class_query` は無い）・問いの台帳・修正案・事前審査の穴は無い。
16. 読み替え 2: 返答の欄 `changes`・`not_done`・`closure`・`coverage`・`breaks`・`bypass_tried`・`root_or_symptom`・`rejudge_requested` は無い・そこに書けと言うこと（検索・試験と結果・破りに行った入力）は `how` に・Bash で書いたファイルは `bash_writes` にパスと理由を 1 件ずつ・記録にも申告にも無い変更は拒まれる・「changes に 1 行」は fixed と files・直さない穴は declared と理由。
17. 読み替え 3: 食い違いの申し出・人への問い・判定への異議の出口は無い・曲げるくらいなら declared と、食い違う所（`<パス>:<行>` を 2 つ以上）・なぜ両方は成り立たないか・どれが正しいか（request・test・code・unknown）を `how` に・テストを緩める・期待値を実装に合わせる・依頼を読み替える・特定の入力だけを通す枝を足す、のどれもしない。
18. 読み替え 4: Edit・Write で書く決まりはそのまま・記録の無い起動だけは突き合わせずに通し、報告に出る。
19. 読み替え 5: 受け付けは試験を選んで回さない・直した穴に当たる試験を絞って自分で回し緑を確かめてから返す。
20. 手直しだけの決まり: 足さずに消す・まとめる形を先に考える・直した行は退行を注入して赤を見てから戻す。
21. 座: Skill の道具で `receiving-code-review` を読みその手順で進める・この指示の約束（返す JSON・機械の関門・段の順）と読み替えが借りた文に勝つ・効く所と効かない所・読み替えの頭の 1 文と本文。
22. 返答: 義務の全部に 1 度ずつ `handled` の 1 行・key を一字も変えずに写す・一覧に無い key・同じ key の 2 行・1 件の欠けは拒まれる・fixed は `how`（20 字以上）と `files`（根からの相対パス。空は拒まれる）・declared は残す理由（誤検知なら現物のどこで誤りと言えるか）。
23. 返答の後: fixed と答えた穴には手直しだけの差分に 2 回目の審査が当たり、直したと言う穴を 1 件ずつ検算する。
24. 人が読む文の欄を言語の値で書く・key・enum の値・識別子・パス・コマンド・エラー文はそのまま（key は周をまたいで突き合わせるので訳さない）。

review-2（今の `commands/review2.md`）: review-1 の 2・5・10・12〜15・22〜26・28・29 と同じ行に加えて、

1. 手直しの直後に手直しだけの差分を見る・2 回目で 3 回目は無い。
2. 手直しの差分は修正後に固めた姿と手直し後の姿の差で、修正の行は載っていない。
3. 材料の `handled` が手直しの応答（fixed は直したと言う・declared は残すと言う）・declared の行は検算しない。
4. fixed と答えた穴を 1 件ずつ検算する・key は fixed の行から一字も変えずに写す・塞がっていなければ `closed: false`・2 回目の手直しが同じ key で答える・漏れは拒まれる。
5. ここで挙げた穴への手直しはもう 1 度は審査されない・直したと言う物は次の run の依頼の下書きに載り、次の run の判定で検算される。
6. 方針とぶつかる時の `kind` は 5 つの語のうち一番近い物・どれにも当たらなければ方針も守る約束の 1 つとして `contract_drift`。

refix-2（今の `refix-head-2`・`refix-tail-2`）: refix-1 の 1・2・11・13〜22・24 と同じ行に加えて、

1. 手直しの差分の審査（2 回目）が挙げた穴（審査役の穴と、修正と手直しを合わせた差分の足した行に機械が見つけた内側の語の穴。1 回目の手直しが直したと答えて残った語も入る）と塞がっていなかった検算を同じ周のうちに直す。
2. `owed` の説明（2 回目の審査の穴と、手直しが直したと言ったのに塞がっていなかった検算・内側の語の行の答え方は 1 回目と同じ）・`diff_file` は修正後に固めた姿と手直し後の姿の差・`ties` は 1 回目の名札と手直しが変えたファイルから結んだ物で、答え方は変えない。
3. ここで直したものは、この run ではもう差分の審査が当たらない・直したと言う物は次の run の依頼の下書きに載り、次の run の判定が直したと言う行も含めて 1 件ずつ振り分ける。

### 10.4 済んだと言える条件（PR ごと。README の 11.2）

```sh
PYTEST_XDIST_AUTO_NUM_WORKERS=4 WORKS_FACTORY_ARCHON_CACHE=<Archon の源の置き場> nice -n 19 python3 -m pytest -q tests/blocks/delta_review tests/layers
```

`tests/blocks/delta_review/` が振る舞いを、`tests/layers/test_block_shape.py` が形の検査と 3 本の筋書きと `archon validate` を照らす（源と bun が無ければ見送る。CI は赤）。最後に、8 節の命令で本物の単独の run を 1 回回す（小さな対象に変更を 1 つ入れ、`plan` を渡さずに）。

## 11 根拠を書いて自分で決めた事

1. 入力を README の 3 つから 9 つにした。根拠: 今の審査役と手直しの役が読む材料（事前審査の穴と修正役の答え・修正の報告・範囲の相談と裁定・テストの許し・方針・依頼のファイル）を受けないと、検算・準拠の外れた項目の扱い・範囲の照らし・方針の決まりが落ちる（元の能力を削らない。リポジトリの決まり）。修正の段の値は、fix の設計書が別々の pointer で返すと決めた欄（`start_tree`・`scope`・`reply`・`allowed_tests`）をそのまま受け、この block の側で束ねる形を作らない。`plan` は README の名のまま、中身を範囲の欄（合意と裁定の印を足した項目）にした（項目だけを受けると、合意と裁定を読むために fix の place を開くことになる）。
2. 深さで省く・戻せない組・変更の確かめの 3 つの決めは line の `when:` に、差分が空で検算も無い時の飛ばしは block に置いた。根拠: 前の 3 つは修正の段と深さの表の事実（README の 1.2 の D・U、形の直し 5）。最後の 1 つは「審査する物が在るか」で、この block の port の値だけで決まる（README の 4.3 の「役を起こすかは block の intake が自分の port の値で決める」）。
3. 状態の語に `gave_up` を足し、`ok` を `failed` でない時にした。根拠: 今、役が諦めた時は run を止めず（`pass: false` のまま先へ）、段が壊れた時は node が落ちて run が止まった。手本の world は諦めを `failed` にしたが、この block で同じにすると、line が `ok` で止めるか `pass` で進むかを決められない。止めるかは line が決める（README の 4.3）ので、2 つを語で分けて渡す。
4. 輪を回すかを輪の外の script（`owed-n`・`cut-2`）で決め、輪の中の `go` の道と受け付けの `if_skipped: null` をやめた。根拠: 輪の中を prep → 役 → accept の 1 本にでき（README の土台の決め）、起こさなかった回の受け付けの道（今の `not_launched`）が要らなくなる。
5. 座を別のファイル（今の `review1-seat.md`）にせず、指示の中の節にした。根拠: 座の決まった字（頭・勝つ決まり・表の見出しと注）は Python の定数で、別のファイルに書くと憲法の 2（AI に届く決まった文は md だけ）を外れる。中の型の本文と読み替えは借りた写しのファイルの字なので、値で入れる。指示は約 30 KB になる（今の手直しの指示は 39 KB をファイルで Read させた。README の未確認「大きい指示の上限」に当たりうる。13 節）。
6. 書く役の決まりの正本（今の `fix-rules/common.md`）を共通の断片 `writer-rules` にした。根拠: fix の 4 つの役と、この block の手直しの役（2 つの block）が共に使う（憲法の 4・README の 5.1）。README の形の直し 3 は fix の中の断片と書いたが、手直しの役が fix の外の block になったので、2 つの block の断片になる（12 節の 1）。fix の設計書はこの文を fix の中の断片に置くと書いており、食い違う（13 節の 1 つ目）。
7. 座の決まった字を、審査と手直しの md に 1 回ずつ書いた（共通の断片にしない）。根拠: fix の座（修正役の型・TDD のスキル・下請けを回す節）とは並びも文も違い、共に使う字は見出しと「勝つ」の 1 文だけ。fix の設計書が同じ字を断片にするなら、組み込みで寄せる（13 節）。
8. 手直しの役に外への検索の決まり `{shared:query-rule}` を足した。根拠: この役は WebSearch・WebFetch を持つ。共通の断片の決まり（`.shared/AGENTS.md`）と今の試験 `test_roles_that_reach_outside_carry_the_query_rule` の考え（外へ出る役は検索語の決まりを持つ）に合わせた。
9. 返答が JSON として読めない時は拒否にした（今は node が落ちた）。根拠: ほかの block（world・purpose）と同じ `rolekit.accept_round` の道。Archon の `output_format` が JSON を約すので、実際の振る舞いは変わらない。
10. place のファイルの名を新しくした（1.4 の表）。根拠: 今の名は写した graph の節の名（`p3.delta_review`）と fix の中の置き場の事情（`delta/` の下）を持ち、この block の中でしか読まれない。名の持ち主は `src/files.py` 1 つ（README の 4.4）。e2e の照らしの表は組み込みで合わせる。
11. 承認済みの修正案の項目の凍結の印の照らし（今の `conflict.fields_broken` の道）を、この block では持たない。根拠: 項目は port で値として受け、凍結の印と控えは作り手の place に在る（README の 4.3: block は port の値が指すファイルのほかは開かない）。項目の形が壊れていれば入口が `failed` にする。
12. 指示の比べの日本語の commit と試験は作らない。根拠: 持ち主の 2 波目の決め（速さ）。審査は 10.3 の一覧で新旧を並べて見る。
13. 2 回目の手直しの指示にも範囲の節を貼る。根拠: 今もそうしていた（`refix_prep.py` の docstring「n によらず貼る」）。受け付けも n によらず範囲を照らす。

## 12 README へ返す問題

1. 書く役の決まりの正本 `fix-rules/common.md` は、fix と delta-review の 2 つの block が使う。README の 1.3 の形の直し 3 と 5.1 の例は fix の中の断片 `prompts/parts/` と書くが、共通の断片 `blocks/.shared/prompts/writer-rules.md` になる（11 節の 6）。`.shared/AGENTS.md` の名の一覧にも足す。
2. `lib/leftovers.py` は README の 9 節のどの区分にも無い。fix（後始末）と delta-review・lens（作業ツリーの姿を木に固める `snapshot`・`git`）が使うので KEEP。
3. `lib/unittrees.py` は MOVE（fix）だが、`pathspec_without` を delta-review と lens も使う。KEEP の部分に入れる。
4. `lib/gatemarks.py` の `HANDLED_WORDS`（手直しの答えの語の人向けの字）は、報告の行を組むのがこの block になったので、この block だけが使う。組み込みで delta-review の `src/` へ移す。
5. `lib/fixbeside.py`（9.1 で DELETE）の報告の行の組み方（`branch_rows`・`next_items` の手直しの行・`always_rows` のレンズの行）は、この block の `src/summary.py` に写した。line の最後の承認ノードは、この block の `report` を読む形にする（line の設計書）。

## 13 未確認

- 書く役の決まりの正本（今の `fix-rules/common.md`）の置き場が、fix の設計書と食い違う。この設計書は共通の断片 `blocks/.shared/prompts/writer-rules.md`（段落 `conflict`・`docs`・`prompts_kind`・`config`・`code`）にし、fix の設計書（2.3.1・1.5.4）は fix の `prompts/parts/` の `core-fix.md`・`evidence.md`・`conflict.md`・`keep.md` に置いて「共通の断片は足さない」と書く。両方をそのまま作ると同じ文が 2 つの block に在る（憲法の 4 に反し、片方だけ直すと手直しの役と修正役の決まりがずれる）。この設計書の推し: 共通の断片 1 本（2 つの block が使う物。README の 5.1）。fix の側の段落の選び（`rules` など）は断片の段落に足す。どちらに揃えるかを決めてから、2 つの PR の後の方が合わせる。
- `start_tree`・`scope`・`reply`・`allowed_tests` の欄の名と形は、fix の設計書の 1.2 の書きかけの版に合わせた。fix の設計書が変われば 1.2 と 1.6 を直す。
- 表 `tests/layers/scan.py` の `CHANGE_CHECKOUT` は今の `refix-accept` を「3 回目の拒否で手直しを戻す（refix.accept_fix）」と書くが、今の `refix.accept_fix` と `fixboard.accept_out` は戻さない。この block は今のコードの振る舞い（戻さない）に合わせ、受け付けに `mutates_checkout: false` を書く。諦めた手直しの変更を戻すべきかは、振る舞いを変える話なので作り直しの外。
- 審査役の指示（座を含めて約 30 KB）と手直しの指示（約 40 KB）を `$<prep>.output.prompt` で入れて、Archon の出力の大きさの上限に当たらないか（README の未確認と同じ）。当たるなら、座の型の本文だけを place のファイルにして Read させる形に戻す。
- 元の works の読んだ証拠の node（`review-reads`・`refix-reads`）を工場が持たない訳（2.7）。
