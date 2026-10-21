# block の設計書: diagnose（根本の診断と再審）

- 何の話か（読む人: この block の実装者・つなぐ graph の設計書の書き手・英語の md を照らす審査役。語と節の番号は [README.md](README.md) の物）: 素材・依頼の行・世界の解・前提の実測などを読み、人の修正依頼を根本の単位にまとめてラベルと disposition を確定させる判定役と、修正役が判定に異議を出した時に同じ block の中で判定を考え直す再審の役を、単独で呼べる block `workflows/diagnose/` にする設計。型は [README.md](README.md)、手本は [world.md](world.md)。
- 決めたこと: 今の judge の `diagnose-prep`・`diagnose-loop`・`rejudge-prep`・`rejudge-loop` と、返す節 `verdict` のうち判定と再審の分を、頂 4 つ（`intake`・診断の輪・再審の輪・`finish`）の block にする。AI の node は 2 つ（判定役 `diagnose`・再審の役 `rejudge`）。今の再審の輪の出し直しの役（`rejudge-fix`。拒まれた欄だけを返す）も置く（4 節・11 節の 5）。道は port `objection` が空か（README の 8.1）で分かれ、再審は同じ block に置く（持ち主の決め `rejudge-cohabit`）。判定役の材料は指示に直に入れず、値だけの JSON 1 本（`diagnose-input.json`）に書いて Read させ、鍵の意味は全部 md が持つ（Python は指示の文を持たない。11 節の 1）。受け付けの規則は今の `lib/judge_accept.py` の判定と再審の部分を `src/` に写す（README の 9.2 の MOVE）。振る舞いは変えない（変えた所は 11 節に名指す）。
- 持ち主に求めること: なし。
- 読む人と使い方: この block を作る実装者（1〜5 節の名と順をそのまま作る）と、つなぐ graph（judge のまとめ・line）の設計書の書き手（1.6）。README の 11.1 の 2 波目。審査役は 9.4 の「残す指示の一覧」で、英語の md を古い指示と 1 件ずつ照らす。

この文書の語は README の頭の物（block・graph・line・port・place・prep・accept・pointer・Archon・憲法〔README の 2 節〕・keep-essence〔README の 10 節〕・KEEP／MOVE／DELETE〔README の 9 節〕）と、[materials.md](materials.md) の頭の物（今・周・素材・観点）を使う。ほかに、この文書でよく出る物:

- 世界の解: 依頼の各行を業界の定石と照らした行（world の block の出力。[world.md](world.md)）。前提の実測: 依頼に書かれた数値・在る無いを作業ツリーで測り直した行（premises の block）。頭の深さ: 依頼の行ごとの未知の種類（`無し`・`原因`・`形`・`範囲`）と run の段（head-depth の block）。
- judge のまとめ: 判定の block（world・purpose・premises・素材の観点・diagnose・verify など）を include で並べる graph。line: メイングラフ。承認ノード: 人が答える node。
- 判定から入る run: 差分が空で依頼が 1 件以上の run（入口の印は始めの記録の `request_entry`）。
- P0・P1・R1〜R4: 元の graphloops の段の名（P0 は先行議論と目的の監査、P1 は差分を見る素材の観点、R1〜R4 は修正の後の独立の目）。出どころの名（`p1.local_review` など）に今も残る。
- 作り直しの行: 前の run の独立の目 R2 が「作り直しを要る」と言った行（`prior_failures` の中で `where` が `独立の目 R2` の行）。この block の作業そのもの（#765 の作り直し）とは別。
- 筋書き: block の standalone の fixture（`fixtures/*.stubs.yaml`）。Archon の `workflow test`（dry-run）が AI の node の返答だけを台本で差し替えて回し、`reached` の node に届いたかを見る。
- 2 波目: README の 11.1 の作る順の 2 番目の段（diagnose・verify・plan などを同時に作る）。土台: 11.1 の 0（`blocks/` の骨組みと手本の PR）。


- 判定役（diagnose）: 依頼の行と素材を読み、根本の単位を切ってラベルと disposition を確定させる AI の役。読むだけで、道具は Read・Grep・Glob・WebSearch・WebFetch。
- 再審の役（rejudge）: 修正役の異議を受けて、1 回目の判定を考え直す AI の役。道具は判定役と同じ。
- 単位: 判定の返答の `units` の 1 行。開いた単位は、ラベルが `block` か、`suggest` で disposition が `do-now` の単位（今の `is_open`）。
- 問いの台帳: 判定の返答の `questions`。人へ回す問いは `gatemarks.asks_human` が真の行（status が held か escalate の fork など）。
- 材料のファイル: 判定役に Read させる値の JSON `diagnose-input.json`（2.3 の 4）。今の `judge/diagnose-brief.md` の値の部分だけ。
- 例の run（判定）: 本物の run `df5e111f-ea97-409b-8066-2245d32746ab`（world.md と同じ run。判定から入る run で、差分は空・依頼の行は 1 件。判定役は 1 回目で受け付けを通った。`rejects-diagnose.json` が無い）。置き場は `<run の置き場>/judge/`。
- 例の run（再審）: 本物の run `82d22f4f-8090-45b3-abea-e2a9cdd8be2e`（対象は持ち主の非公開のリポジトリ。この文書には値の形だけを写す）。再審の役は 1 回目で通った（`rejudge-exit.json` の `passes` が 1・答え `一部採る`）。置き場は `<run の置き場>/rejudge/`。

## 1 block の全体

### 1.1 役

判定の道: 依頼の行・素材の観点の所見・世界の解の行・前提の実測・記録された方針を読み、人の修正依頼を根本の単位（コードの上の欠陥の形 1 つ）に切って、ラベル・disposition・処方・欠陥の数え方（class_query）・先行例・人に回す問いを返させる。機械が、作業ツリーを変えていないか・数え方の例が問いに合うか・先行例の出どころが世界の解の行に在るか・台帳の語彙と状態の決まり・目的の外の所見が材料の行に当たるか・依頼の答えと作り直しの行の結び・③ を名乗る問いが記録された方針を名指すかで受け付け、class_query の件数を機械が数え直す。3 回拒まれたら諦める。素材の観点が 1 つでも諦めていれば、判定役を起こさずに止めの語を返す。

再審の道: 修正役の異議と 1 回目の判定を読み、異議が挙げた事実を確かめさせ、採る・退ける・一部採るを決めて単位を返させる。機械が、作業ツリー・数え方の例・確かめた事実の長さで受け付け、単位の前後の差と出口を書く。

### 1.2 port

入力（YAML の `inputs:`）。説明の字は下のとおり書く（README の 4.1）。判定の道は「判定」、再審の道は「再審」の印の物だけを読み、ほかの入力は読まない（渡されても開かない）。

- `request`（判定）: `json(shared:request.schema.json): 依頼の行の配列 [{where, text, mechanism?, measured?, false_positive_if?}]。それを findings の欄に持つ依頼のファイルの形でもよい（その時は answers・prior_failures の欄も読む）。空の配列は依頼の行の無い run（対象差分だけを審査する）`。既定 `[]`。
- `request_origin`（判定）: `text: 依頼の行の出どころの名（判定役に見せる依頼のバッチの origin。例「人の依頼（/path/req.json）」）。空は「人の依頼（依頼の行）」`。既定 `""`。
- `objection`（両方）: `text: 修正役が判定に出した異議の文。空は判定の道、空でなければ再審の道`。既定 `""`。
- `base`（判定）: `text: 対象差分の根の commit（この commit から作業ツリーの今の姿まで。未追跡の新しいファイルも入る）。空は HEAD`。既定 `""`。
- `purpose`（両方）: `file: 固めた目的のファイル（purpose.json。{purpose_text, source, known_weaknesses, source_files}）。空は目的の文がこの run に無い`。既定 `""`。
- `constraints`（判定）: `json(shared:constraints.schema.json): 前提の実測の行の配列か、それを constraints の欄に持つオブジェクト。空の配列は実測が無い`。既定 `[]`。
- `materials`（判定）: `json(materials.schema.json): 素材の観点の block が返した material.json の pointer（かファイルのパス）の配列。空の配列は素材の観点が 1 つも回っていない`。既定 `[]`。
- `pr_material`（判定）: `json(pr-material.schema.json): 並行 PR の素材の札 {status, count?, detail?, checked?, reason?}。null か空は並行 PR の確かめが回っていない`。既定 `"null"`。
- `baseline`（判定）: `file: 直す前の試験の結末（試験の関門が直す前に書いた baseline.json）。素材 local_checks をここから写す。空は local_checks を not_run にする`。既定 `""`。
- `world_rows`（両方）: `file: 世界の解の行のファイル（world.jsonl。1 行が依頼の 1 行）。空は世界の解の行が無い`。既定 `""`。
- `row_asks`（判定）: `json(row-asks.schema.json): 頭の深さが依頼の行ごとに返した未知の種類の行 [{item, unknown, cause_quote, where?, code_quote?}]。空の配列は種類が決まっていない`。既定 `[]`。
- `depth_why`（判定）: `text: 頭の深さの段の根拠の文（行ごとの種類が決まっていない run で、その訳として役に見せる）。空は「run の頭の深さの控えが無い」`。既定 `""`。
- `spec_rows`（判定）: `file: 仕様が足した受け入れ条件の行のファイル（added-rows.json。依頼の行の配列）。空は足した行が無い`。既定 `""`。
- `spec_origin`（判定）: `text: 仕様が足した行の出どころの名（判定役に見せるバッチの origin）。spec_rows が在る時に要る`。既定 `""`。
- `answers`（判定）: `json(answer-rows.schema.json): 依頼者が前の run の問いに答えた行 [{question, text, command?, output?}]。空の配列は request の容器の answers を使う`。既定 `[]`。
- `prior_failures`（判定）: `json(shared:prior-failures.schema.json): 前の run が運んだ行 [{where, text}]（最後まで通らなかった物と、独立の目 R2 の作り直しの行）。request の容器の prior_failures の後ろに足す。空の配列は足す物が無い`。既定 `[]`。
- `pr_text`（判定）: `text: 依頼が名指す PR の番号・題・本文を並べた文。空は PR の無い run`。既定 `""`。
- `policy`（両方）: `file: 人の方針の文書を run の頭で固めた写し。空は方針が無い`。既定 `""`。
- `prior`（再審）: `json(shared:judgment.schema.json): 考え直す 1 回目の判定（judgment.json の中身か、その pointer）。null か空は 1 回目の判定が無い（再審せずに止める）`。既定 `"null"`。
- `prior_brief`（再審）: `file: 1 回目の判定役に渡した指示（組んだ指示のファイル。記録された方針・前の run の行・頭の深さの行・人の方針の本文を含む）。空は渡されていない`。既定 `""`。
- `prior_inputs`（再審）: `file: 1 回目の判定役が読んだ材料のファイル（diagnose-input.json）。空は渡されていない`。既定 `""`。
- `spec`（再審）: `file: 固めた仕様（spec.json）。空は仕様の段が無い`。既定 `""`。
- `verify`（再審）: `file: 判定の裏取りの結果。空は裏取りが無い`。既定 `""`。
- `excluded`（再審）: `file: 並行 PR の外す範囲（pr-excluded.json）。空は渡されていない`。既定 `""`。
- `request_files`（判定）: `json(request-files.schema.json): 依頼そのものを書いたファイルのパスの配列（対象のリポジトリの根からの相対パス）。単位の数える問いの探す所（`how.paths`）が全部この配列のファイルに当たる単位は、判定の返答の受け付けが拒む（数える問いが数えるのは直す所で、依頼の文ではない）。空の配列は照らさない`。既定 `"[]"`。仕様駆動の道が表と設計書のパスを渡す（[spec-driven.md](spec-driven.md) の 9 章）。比べ方は、`how.paths` の各項の頭の `./` と終わりの `/` を外した字が、依頼のファイルのどれかと同じか。paths が空・ディレクトリ・glob の単位は当たらないとして拒まない。名指した run だけ、判定役の指示に「依頼そのものを数えない」の段落が出る。
- `lang`（両方）: `text: 人に見せる欄の言語（2.4・3.4 が名指す欄）。空は依頼の行の言語`。既定 `""`。

出力（`returns: finish`、`outcome_field: ok`）。`finish` の `output_format` は `additionalProperties: false` で、下の欄を全部 `required` にする。pointer は `{type: archon_artifact, run_id, path}`、null を取る欄は `type: [object, 'null']`（`anyOf` は使わない。`workflows/.shared/AGENTS.md`）。

- `ok`: boolean。`status` が `ok` か。
- `status`: `ok`（判定か再審を受け付けた）・`stopped`（素材の観点が諦めていたので判定役を起こさなかった）・`failed`（入力が読めない・対象差分が取れない・役を諦めた・1 回目の判定が無い・どこかの段が落ちた）。
- `mode`: `judge` か `rejudge`（`objection` が空か）。
- `stop_reason`: `status` が `ok` なら空。ほかは次のどれか（どれも今の語。止めるかは graph が決める）: `works:request`（`request` が読めない）・`works:judge`（ほかの入力が読めない・対象差分が取れない・判定役を諦めた・受けた判定が無い）・`works:material`（素材の観点が諦めた）・`works:rejudge-session`（再審の道で `prior` が null）・`works:rejudge`（再審の道のそのほかの落ち）。
- `reason`: 日本語の 1 行（人に見せる）。`ok` なら空。
- `ready`: boolean。`status` が `ok` で、開いた単位が 1 つ以上か（今の `verdict` の `ready`）。
- `judgment`: pointer（place の `judgment.json`）。いつも在る。受けた判定（再審）が無ければ空の形（5.6 の `EMPTY_JUDGMENT`）を書いて指す（今の `_fill`。読み手が null を扱わずに済む）。
- `units`: 開いた単位の構造の目の入力の形 `[{id, paths, summary}]`（今の `structure_units`）。`status` が `ok` でなければ `[]`。
- `questions`: 受けた判定の台帳のうち人へ回す問いの行（`gatemarks.asks_human` が真の行。台帳の行の形のまま）。無ければ `[]`。
- `inputs`: pointer（`diagnose-input.json`）か null。判定の道で材料を書けた時だけ。再審の道の `prior_inputs` に渡す。
- `brief`: pointer（最後に組んだ判定役の指示 `diagnose-prompt-<n>.md`。`<n>` の最も大きい物）か null。判定の道で指示を組めた時だけ。再審の道の `prior_brief` に渡す（今の再審が Read させた「判定役の材料」`diagnose-brief.md` の代わり）。
- `materials`: pointer（`materials.json`。素材の 14 欄。11 節の 27）か null。判定の道で書けた時だけ。
- `out_of_purpose`: pointer（`out-of-purpose.json`）か null。判定を受け付けて、目的の外の行が在った時だけ（今の `outpurpose.save` が書く時）。
- `answer_ties`: pointer（`answer-ties.json`）か null。同じく結びの行が在った時だけ。
- `rejudge_verdict`: `採る`・`退ける`・`一部採る` か null（再審の道で受け付けた時だけ）。
- `rejudge_exit`: pointer（`rejudge-exit.json`）か null（再審の道で intake が通った時は必ず在る）。
- `rejudge_diff`: pointer（`rejudge-diff.json`）か null（再審を 1 回でも受け付けた時だけ）。
- `downgrades`: この block が元の能力から下げている所の宣言 `[{what, versus}]`。いつも次の 1 行（今の `docs/nodes.json:194`（#765 で消した） の字。11 節の 9）: `{what: "再審は判定役の会話を継がず、保存した返答を読む新しい会話で回す", versus: "review-graph と今の works は判定役の会話を継ぐ"}`。
- `report`: 報告に載せる日本語の行の配列（5.7）。

今との違い: 今は入力を `judge/start.json`・`judge/request.json`・`judge/premises.json`・`judge/purpose.json`・`judge/material-<役>.json`・`judge/world-state.json`・`judge/depth-head.json`・`judge/prior-failures-in.json`・`judge/stop.json` から名で開き（`lib/judge_accept.py:2764-2872`）、再審は同じ run の `judge/` を名で開いて 1 回目の判定と材料を読んだ（`:3312-3345`）。出口は judge 全体の返す節 `verdict` の 26 欄に混ざっていた（`:3938-3995`）。止めの記録の確かめは無くし（README の 4.3）、前の段の落ち（前提・目的が無い）で止めるのは graph の `when:` が決める。

### 1.3 node の並び（`workflows/diagnose/works-factory-diagnose.yaml`）

AI の node の起動の鍵（今の YAML の錨 `review_launch` のまま。`workflows/judge/works-factory-judge.yaml:227-234`）: `model: '@wf-judge-core'`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob, WebSearch, WebFetch]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`idle_timeout: 1728000000`・`mutates_checkout: false`・`retry: {max_attempts: 2, on_error: all}`。YAML の錨で 2 つの AI の node に配ってよい。script の node はどれも `runtime: uv`・`mutates_checkout: false`。

1. `intake`（script `intake.py`）: port を読み、道を決め、place の中のこの block のファイルを名で引いて消し、道ごとの支度をする（5.1）。返り `{due, mode, reason}`（`mode` は `judge|rejudge` の enum。3 つとも required）。
2. `diagnose-loop`（`depends_on: [intake]`・`when: "$intake.output.due == true && $intake.output.mode == 'judge'"`・`loop_group`・`max_iterations: 3`・`fresh_context: false`・`until_bash: 'done=$diagnose-accept.output.done; test "$done" = true'`）
   - `diagnose-prep`（script `diagnose_prep.py`。`with:` を持たない）: 指示を組む。返り `{prompt}`（`minLength: 1`）。
   - `diagnose`（AI。`prompt: "$diagnose-prep.output.prompt"`・`depends_on: [diagnose-prep]`・起動の鍵。`output_format` は今の物を字のまま写す: `workflows/judge/works-factory-judge.yaml:1814-1987`。2.4）。
   - `diagnose-accept`（script `diagnose_accept.py`。`depends_on: [diagnose]`・`with: {reply: $diagnose.output}`）: 返り `{ok, done, reason}`。
3. `rejudge-loop`（`depends_on: [intake]`・`when: "$intake.output.due == true && $intake.output.mode == 'rejudge'"`・同じ loop の形で `until_bash: 'done=$rejudge-accept.output.done; test "$done" = true'`）
   - `rejudge-prep`（script `rejudge_prep.py`。`with: {prev: "$LOOP_PREV.rejudge-accept.output.ok"}`）: 再審の役の 1 回目の指示を組む。前の周が拒まれて控えが在れば組まず `resubmit: true`。返り `{prompt, resubmit}`。
   - `rejudge`（AI。`prompt: "$rejudge-prep.output.prompt"`・`depends_on: [rejudge-prep]`・`when: resubmit != true`・起動の鍵。`output_format` は今の `&rejudge_reply` を字のまま: `:2084-2149`。3.4）。
   - `rejudge-fix-prep`（script `rejudge_fix_prep.py`）・`rejudge-fix`（AI。出し直しの役）: 4 節。
   - `rejudge-accept`（script `rejudge_accept.py`。`depends_on: [rejudge, rejudge-fix]`・`trigger_rule: none_failed_min_one_success`・`with: {reply, fix_reply}`）: 返り `{ok, done, reason}`。
4. `finish`（script `finish.py`。`depends_on: [intake, diagnose-loop, rejudge-loop]`・`trigger_rule: all_done`）: 出力を返す。どの段が落ちても落ちない（今の落とし穴 K1・K13。5.6）。

輪の中の層の決まり（1 波目を作った時の決め: `fresh_context: false` の輪で、続きの会話で起きる役の直前に 2 つ以上の node の層を置かない）: どちらの輪も `fresh_context: false` で、どの層も node 1 つ（prep → 役 → 受け付け）。拒まれた後の回で同じ会話の続きとして起きる役の直前の層は prep 1 つで、2 つ以上の node の層を置かない（Archon は並びの層で会話を切る）。

script の名は `lib/` のモジュールの名と重ねない（README の 7.1 の 9）。`intake`・`diagnose_prep`・`diagnose_accept`・`rejudge_prep`・`rejudge_accept`・`finish` は `lib/` に無い（`lib/accept.py` と重ねないため `accept.py` の名は使わない）。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、judge のまとめから include された時は `$ARTIFACTS_DIR/<judge の include の id>/diagnose/`、line が再審で include した時は `$ARTIFACTS_DIR/<その include の id>/`）の下に書く。名は `src/files.py` だけが持つ。intake はこの一覧の名だけを消す（`rejects-*.json` のような広い形で消さない。README の 13 章）。

- 両方: `intake.json`（`{mode, due, status, stop_reason, reason, values}`。`values` は読んだ port の値と、`file` の port の解いた絶対パス）・`tree.json`（役を起こす前の作業ツリーの姿。`materialkit.snap_tree` の形）・`judgment.json`・`structure-units-dropped.json`・`query-examples.json`・`prompt-error.json`（指示が組めなかった node と訳）。
- 判定の道: `view.json`・`diff.patch`・`changed-files.txt`（`materialkit.take_view` が書く）・`materials.json`・`diagnose-input.json`・`diagnose-prompt-<n>.md`・`rejects-diagnose.json`（`rejects-diagnose.md` はこの block のどこも書かない。前の版の控えが残っていれば intake が名で消す）・`count-cache.json`・`count-budget.json`・`out-of-purpose.json`・`answer-ties.json`。
- 再審の道: `first-judgment.json`（`prior` の中身の写し）・`units-before.json`・`rejudge-prompt-<n>.md`・`rejects-rejudge.json`（と `.md`）・`rejudge-reply.json`・`rejudge-diff.json`・`rejudge-exit.json`。

`query-examples.json`・`out-of-purpose.json`・`answer-ties.json` の名は `lib/marks.py` の種の表（KEEP の `querytest`・`outpurpose`・`gatemarks` が place を受けて書く）、`rejects-*` の名は `lib/rolekit.py` が持つ。`src/files.py` は消す時のためにこれらの名を写して並べ、試験が lib の名と突き合わせる（9.2 の `test_place_names_match_lib`）。

### 1.5 コードの置き場

- `workflows/diagnose/src/__init__.py`（空）。
- `workflows/diagnose/src/files.py`: place のファイルの名（1.4）・役の名 `DIAGNOSE_ROLE = "diagnose"`・`REJUDGE_ROLE = "rejudge"`・節の名 `REJUDGE_NODE = "p2.rejudge"`（`units-before.json` と差の行の `node` に書く今の字）・`GUARDED = True`（今の accept の `with: {status_guarded: true}`。`:1991`・`:2178`）・止めの語（下の 5.6）。
- `workflows/diagnose/src/judge.py`: 判定の受け付けの芯。`lib/judge_accept.py` から写す（MOVE）:
  - 表: `LABELS`（`:135`）・`Kind` と `QUESTION_KINDS` の `domain` と `fields`（`:233-257`。`note` の文は写さず md へ。2.6）・`QUESTION_FIELDS`・`UNIT_FIELDS`（`:273-274`）・`QUESTION_STATUS`（`:293-298`。`QUESTION_STATUS_NOTE` の文は md へ）・`NO_OPEN_ORIGIN`（`:319`）・`REVIEWS`（`:133`）・`EMPTY`・`ONE_LINE_FIELDS`（`:244-246`・`:388`）・`ASK_KEYS`（`:369-374`）・`COUNT_BUDGET`・`COUNT_CACHE_FILE`・`COUNT_BUDGET_FILE`（`:265-267`）・`PREMISE_THREE`・`_CASE_MARKS`（`:789-790`）。
  - 写さない物: 素材の欄の全体の表 `MATERIALS`（`judge_output` が読む `:630`）は `materialkit.MATERIALS` を import する（同じ字の組。統合の設計書 integration.md の 4.4-K）。この block が読むのは `files.MATERIALS`（そこから `gate_efficacy` を除いた 14 欄。11 節の 27）。`is_open`・`open_units` は共通の `judgmark`（下の「使う `lib/`」。統合の設計書の 4.4-H）から `from judgmark import …` で受け、`src/judge.py` の名で出し直して `rejudge.py` と試験が引く。
  - 関数: `origin_not_awaiting`・`targets`・`settled_state_errors`（`:195-241`）・`blank`・`_keys_once`（`:248-262`）・`_run_query`（`:270-299`）・`_head_at_rev`・`_judge_tree_unchanged`（`:414-449`。写しのファイルは `tree.json`、`_moved_since` は `materialkit.moved_since`）・`_precedent_gap`・`_precedent_errors`・`_awaiting_origins`（`:505-544`）・`judge_output`（`:547-658`。`prev_deletions`・`prev_questions`・`defer_ledger` の引数と、それに頼る `_carried_r1_accounted`・`_fork_moves_forward` は写さない。11 節の 4）・`_judged`（`:667-692`。世界の解の出どころの照らしは下の `world_ref_problems`）・`unmeasured`・`origin_of`・`answer_binds`・`answer_tie_problems`（`:726-786`。依頼の答えと作り直しの行と素材は引数で受ける）・`claims_premise_three`・`recorded_question_problems`（`:793-813`。記録された方針の行は引数で受ける）・`take`・`accept`（`:816-858`）・`_unit_file_paths`・`structure_units`（`:871-910`）。
  - 足す関数: `world_ref_problems(reply, rows) -> list`（今の `worldmark.ref_problems`〔`lib/worldmark.py:148-155`〕を、控えのフォルダでなく行の並び `rows` で受ける形にした写し。`known = {r["class_id"] for r in rows}`、`cite.ref_problem(s, worldmark.SOURCE_PREFIX, known)`）。
- `workflows/diagnose/src/rejudge.py`: 再審の芯。`lib/judge_accept.py` から写す: `REJUDGE_VERDICTS`・`ADOPTED`・`REJUDGE_SETTLED`・`REJUDGE_UNIT_FIELDS`・`_NUMBERS`（`:3214-3226`）・`rejudge_output`（`:3234-3242`）・`_named_numbers`・`diff_units`（`:3245-3292`）・`take`（今の `rejudge_take`、`:3348-3388`。1 回目の判定は place の `first-judgment.json` から読む）・`collect`（今の `rejudge_collect`、`:3391-3426`。止めの控えは書かず、出口の `ok`・`reason` だけを返す）・`verdict_of`（今の `rejudge_verdict`、`:3429-3439`）。`_rejudge_brief`（`:3295-3309`）は写さず、文は md、値は `src/inputs.py` の `rejudge_values` へ（3.3）。
- `workflows/diagnose/src/inputs.py`: port を読み、道ごとの支度をし、指示の値を組む（5.1〜5.4）。写す物: `baseline_local_checks`（`:2640-2651`）・`material_rows` の行の辿り方（`:701-717`。行は 5.1 の 7 の `material_rows`）・方針の本文の上限の切り方（今の `policy._capped`、`lib/policy.py:141-147`。independent-design の `policy_body(path)` と同じ写し。組み込みで 1 つに寄せる）。足す物: `request_batches`（5.1 の 6）・`assemble_materials`（5.1 の 4）・`input_doc`（5.1 の 7）・`diagnose_values`（2.3）・`rejudge_values`（3.3）。
- `workflows/diagnose/src/exit.py`: `finish` の本体（5.6）と `EMPTY_JUDGMENT`（今の `:3871-3872`）。
- `workflows/diagnose/src/report.py`: 報告の行（5.7）。
- `workflows/diagnose/schemas/`: `materials.schema.json`（`{type: array}`。要素の形は `src/inputs.py` が 1 つずつ照らす: dict の pointer か空でない字）・`pr-material.schema.json`（`{type: object, required: [status], properties: {status: {type: string, enum: [found, clean, carried_over, not_applicable, awaiting_human, not_run]}, count: {type: integer}, detail: {type: string}, checked: {type: string}, reason: {type: string}}}`）・`row-asks.schema.json`（行の配列。`required: [item, unknown, cause_quote]`・`item` は integer、ほかは string）・`answer-rows.schema.json`（行の配列。`required: [question, text]`、`command`・`output` は string）。どれも `KNOWN_KEYWORDS` の語だけで書く。null を取る `pr_material`・`prior` は、script が字の空と `null` を先に見て None にしてから `ports.json` に渡す（形は object だけを書く）。共通の形は `workflows/.shared/schemas/` の物を使う: `request.schema.json`・`constraints.schema.json`（在る）・`judgment.schema.json`・`prior-failures.schema.json`（本文は plan.md の 1.2。plan・verify と共に読む。この PR を作る時に main に無ければ、この PR がその本文で足す）。
- 指示: `prompts/diagnose.md`・`prompts/rejudge.md`。共通の断片は `rejected`・`role-judge`（中で `query-rule`）・`policy`・`recorded-policy`・`prior-failures`・`unknown-asks`。`policy`（本文は independent-design.md の 2.3）・`recorded-policy`・`prior-failures`・`unknown-asks`（本文と口と段落は plan.md の 2.3。plan と同じ物を使う）は、この PR を作る時に main に無ければ、この PR がその本文で足し、`workflows/.shared/AGENTS.md` の名の一覧に足す（README の 11.1）。断片の中の行の札（記録された方針の行・頭の深さの行）は plan.md の 2.3 の「材料の札の英語」と同じ字にする（11 節の 14）。
- 使う `lib/`（どれも KEEP。import するだけで変えない）: `accept`（`Reject`・`guard`・`in_repo`・`resolve_rev`・`snapshot_tree`・`tree_state`・`status_keys`・`_git`）・`materialkit`（`MATERIALS`・`take_view`・`snap_tree`・`moved_since`・`read`・`assemble`・`review_md_paths`）・`judgmark`（`is_open`・`open_units`。新しい lib のモジュール。verify・plan も読み、fix は組み込みの後に読む。統合の設計書の 4.4-H）・`rolekit`（`accept_round`・`rejected`・`rejects_text`・`given_up_reason`）・`querytest`・`outpurpose`・`gatemarks`（`ASKING`・`asks_human`・`split_answer_ties`・`save_answer_ties`・`_tie_row_problems`・`_squeeze`・`ANSWER_TIES`・`ANSWER_TIE_MIN`・`unmeasured_of`・`origin`・`binds`・`_fix_duty`）・`worldmark`（`rows`・`SOURCE_PREFIX`）・`cite`（`ref_problem`）・`carry`（`parts`・`is_redesign`・`row_key`・`ANSWERS`・`PRIOR`）・`policy`（`recorded`・`hits`・`RECORDED_TERM`）・`headdepth`（`NONE`・`CAUSE`・`SHAPE`・`SCOPE`）・`premises` の語（`仮説`。今は `lib/runreport.py` の `HYPOTHESIS` に在るので、作り直しの間は `src/files.py` の定数 `HYPOTHESIS = "仮説"` に置く。independent-design.md の 2.3 の 4 と同じ扱い）・`baseline_red`（`read_baseline`）・`stopby`・`oneline`・`jsonfile`・`graphloops/engine/util.py`（`Reject`・`run_count`・`repo_root`・`git`・`pick`）。`lib/judge_accept.py` は import しない（README の 9.2 で割って消す側）。

### 1.6 つなぎ方（graph の側。block には書かない）

- 判定の道: judge のまとめ（`workflows/judge/`）が `include: works-factory-diagnose` を置く（id `diagnose`）。`depends_on` は目的の固定・前提の実測・世界の解・頭の深さ・仕様（write）・並行 PR・素材の観点 11 本（今の `diagnose-prep` の `depends_on`、`:1773-1774`）、`trigger_rule: all_done`。`when:` は前提の実測と目的の固定が `ok`（premises.md・purpose.md の 1.6）。`with:`:
  - `request: $<依頼の pointer>`・`request_origin: <line が始めの記録から組んだ出どころの名。判定から入る run は入口の印の origin、ほかは「人の依頼（<依頼のファイル>）」。今の request_batches の字>`・`base: <始めの記録の diff_base>`
  - `purpose: $purpose.output.purpose`・`constraints: $premises.output.constraints`・`world_rows: $world.output.rows`・`row_asks: $head-depth.output.rows`・`depth_why: $head-depth.output.why`
  - `materials: <11 本の $<観点>.output.material を並べた JSON の配列>`（materials.md の 1.6）・`pr_material: $parallel-pr.output.material`（parallel-pr.md の 1.2 は `material` を札のオブジェクトで返す。11 節の 3）
  - `spec_rows: $spec.output.added_rows`・`spec_origin: $spec.output.added_origin`・`baseline: <line の試験の関門 base の baseline>`・`pr_text: <purpose の block と同じ値>`・`policy: <始めの記録の policy の写し>`・`prior_failures: <line の入力 prior_failures の行>`・`lang`。
- 判定の裏取り（verify）は diagnose の後に、`judgment: $diagnose.output.judgment` で回す。judge のまとめは diagnose の `ready`・`stop_reason`・`units`・`judgment`・`questions`・`inputs`・`brief`・`materials`・`out_of_purpose`・`answer_ties`・`report` を返りに載せる。`stop_reason` で止めるか（`works:material` など）は judge のまとめと line が決める。
- 再審の道: line が 2 度目の修正の後に `include: works-factory-diagnose` を直に置く（今の `rejudge-run`、`workflows/line/works-factory-line.yaml:784-792`。`when: $fixed.output.rejudge == true`）。`with:` は `objection: $fixed.output.objection`・`prior: $judge.output.judgment`・`prior_brief: $judge.output.brief`・`prior_inputs: $judge.output.inputs`・`world_rows`・`purpose`・`policy`・`spec: <仕様の spec>`・`verify: <裏取りの verify>`・`excluded: <並行 PR の excluded>`・`lang`。再審は run で 1 回（line が 1 回だけ include する。今と同じ）。
- line は再審の返りの `units`・`judgment`・`rejudge_verdict`・`rejudge_exit`・`rejudge_diff` を取り、`answer_ties`・`materials`・`out_of_purpose` は 1 回目の判定の物を使い続ける（今の `judged` の script が 1 回目の `answer_ties`・`materials` を持ち続ける形。`:806-842`）。再審の道の diagnose はこの 3 つを null で返す。
- 報告: `report` の欄を節にする（5.7）。再審が直す単位にした単位（修正が受けていない物）と「再審されずに残った異議」の行は、修正の事実と line の異議の文が要るので line が組む（今の `runreport.rejudge_opened`・`rejudge_lines` の `left`）。次の run の依頼の下書きへの運び（今の `outpurpose.next_items`）も line（`out_of_purpose` の pointer の親のフォルダを渡す）。
- 世界の解と目的と前提を回すのは run で 1 回: 再審の道はそれらの block を通らない（world.md・purpose.md の 1.6）。

## 2 node の設計シート: diagnose（判定役）

### 2.1 役

依頼の行・素材・所見・世界の解の行・前提の実測・記録された方針から、根本の単位を切り、ラベル・disposition・処方・class_query・先行例・人へ回す問い・目的の外の所見・依頼の答えの結びを返す。

### 2.2 port

`diagnose-input.json`（← `request`・`request_origin`・`spec_rows`・`spec_origin`・`answers`・`constraints`・`materials`・`pr_material`・`baseline`・`world_rows`。5.1 の 7）・`intake.json` の `values`（← `request` の容器と `prior_failures` の前の run の行・`row_asks`・`depth_why`・`policy` と `answers` と prior-decisions の素材の決着済みの論点から組んだ記録された方針の行）・`view.json`（← `base` と作業ツリー）・`purpose`・`pr_text`・`policy`（本文）・観点の正本のパス（`materialkit.review_md_paths(repo)`。port ではなく工場の置き場と作業ツリーの事実）・前の回までの却下（← place の `rejects-diagnose.json`）・`lang`。

### 2.3 組み立ての順（`prompts/diagnose.md`）

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: 却下の控えが 1 件以上。`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "diagnose"))`（古い順に全部。11 節の 6）。
2. `{shared:role-judge}`（役の定義と、中の `{shared:query-rule}`）。`spawns` は `False`（Agent を持たない）。
3. `## This role`（決まった文）: 根本の単位にまとめてラベルと disposition を確定させる判定役であること（直す側が覆せない拘束判断なので、直す側より上位のこの役が下す）・読むだけ（道具の名。受け付けが役を起こす前の作業ツリーの写しと比べて、変わっていれば拒む）・shell を持たないので git・gh は打てない（役の定義の git・gh の行は shell を持つ役の決まり。リポジトリは Read・Grep・Glob、ホストのページは WebFetch で読む）・「足りない」は `materials_missing` で返す（素材の欄が明示返答を欠けばその欄名、材料のファイルか観点の正本が読めなければ `inputs_file`・`review_md` と書き、手順の 1〜9 に入らず、ほかの欄は空。受け付けは拒み、run は止まる）・この役は同じ会話の続きで起きることがあり、却下の段落が在ればそこを直した返答を丸ごと出し直す。
4. `## Inputs`（決まった文と差し込み口）:
   - 材料のファイル `{inputs_file}`（← place の `diagnose-input.json` の絶対パス）: まず Read せよ。機械が書いた JSON のオブジェクト 1 つで、鍵ごとの意味を箇条で書く（鍵の名は 5.1 の 7 の表と字のまま同じ。値が null の鍵は「この run には無い」）。箇条ごとに今の決まりを持つ: `materials`（素材の 14 欄。起動しなかった欄は status と reason がそう言う。素材のどれかが明示返答を欠けば `materials_missing`）・P1 の所見の鍵 8 つ（反証の対象。所見が空ならその観点は走っていない——素材の status と reason を見よ）・`request_findings`（依頼のバッチ。出どころは人で役の観察ではない。仕様の受け入れ条件のバッチは本文の頭に出どころを持つ。反証の対象で、依頼の頼み方のずれも殺しにいけ。依頼の行が空の run は対象差分だけを審査し、所見を依頼の形に写し替えない）・`constraints`（前提の実測。`kind` が `{hypothesis}` の行を所与にしない。依頼の数字と測り直した値が違えば測り直した値を採り、違いを単位の `reason` に）・`world_rows`（7 項と 8 項で先に使う）・`answers`（出どころは人。`command`・`output` は人が手元で打った命令と出力。台帳の問いの key か出どころと字のまま等しい問いは機械が答え済みにする。当たらない答えは `answer_ties`）・`changed_files`（変更ファイル）・`diff_file`（対象差分のパス。下の対象差分と同じファイル）・`purpose_review`（目的の監査。「狭めている」なら目的の内と外の境をそのまま信用しない）・`prior_decisions`（決着済み論点の突合の返答）。
   - `<!-- if purpose -->` 凍結した元の目的 `{purpose_text}`（← port `purpose` の `purpose_text`）`<!-- end purpose -->`。`<!-- if not purpose -->` 目的の文がこの run に無い（目的の段が無く、目的のファイルも渡されていない。目的を作らない）の 1 文 `<!-- end purpose -->`。
   - 対象差分 `{diff_file}`（Read せよ。`git diff {base} {review_rev}`。作業ツリーを固めた版との差で、未追跡の新しいファイルも入る）・リポジトリ `{repo}`（読む版 `{review_rev}`）。← `view.json`。
   - 観点の正本 `{review_md}`（Read せよ。ラベルと「対応の判断」「処方の最小性」「導線を作る手段の優先順位」の正本。見出しは日本語の字のまま引く）。`<!-- if repo_review -->` 対象リポジトリ側の観点 `{repo_review_md}`（在れば Read せよ）`<!-- end repo_review -->`。
   - `<!-- if pr_text -->` 依頼が名指す PR の番号・題・本文 `{pr_text}` `<!-- end pr_text -->`。
   - 対象リポジトリは今の作業ディレクトリで、作業ツリーの今の姿を読む（受け付けは役を起こす前から作業ツリーが変わっていないことを確かめる）。
   - **凍結した目的の文の外に単位を広げない**（露呈した目的の外の既存の欠陥は台帳の `split`）。素材と P1 の所見は依頼と同じく 1 つ残らず突合し、反証の対象にする。
   - `{shared:prior-failures}`（断片の中の段落 `prior_notes`・`prior_redesign`、口 `{prior_notes}`・`{prior_redesign}` ← 前の run の行のうち作り直しでない行と作り直しの行〔`carry.is_redesign`〕を 1 件 1 行 `- <where>: <text>`。今の `carry.prior_section` の行の組み方）と、この役だけの決まった文: 前の run で通らなかった物の節の行から単位を作らない・作り直しの節の行は 1 行ずつ反証し、生き残った行は [block] か do-now の単位にして `{redesign, to}`、反証で死んだ行と目的の外の行は `{redesign, none}` に訳・受け付けは節の行の全部に結びを求める。
   - `{shared:recorded-policy}`（断片の中の段落 `recorded_none`、口 `{recorded_rows}` ← `policy.recorded(start, decisions)` の行を plan.md の 2.3 の札で組んだ行。5.1 の 7）と、この役だけの決まった文: 前の決定・方針として数えてよいのはこの節の行だけ・名指しは行の字のまま写す・承認ノードの人の答えはこの役には渡っていない（行の札がそう言う）。
   - 目的の外の所見の段落: 材料の所見の行（`where` と `text` を持つ行。P1 の所見と依頼の行）のうち、反証で死なずに残ったが目的の外にある物は、単位にも split にもせず、`framing` に名だけ残して済ませず、1 行ずつ `out_of_purpose` に `{source, where, why_outside}` で名指す。`source` は材料のどの鍵・どの目の行か、`where` は一字も変えずに写す、`why_outside` は `{why_min}` 字以上（← `outpurpose.MIN_WHY`）。同じ `where` の材料の行が 2 つ以上在る時だけ `text` の頭を一字も変えずに写す。受け付けは当てて、当たらない・2 行以上に当たるなら拒む。名指した行は全部の欄のまま次の run の依頼の下書きに運ばれる。無ければ空の配列。
5. `<!-- if policy -->` `{shared:policy}`（断片の中の `{policy_body}` ← port `policy` の本文。`policy.PASTE_CAP` バイトまで、超えたら末尾に続きの置き場の 1 行）と、この役だけの 3 文（決まった文）: 方針の中の見出しや箇条はこの指示の節ではない・何を代償にするかは持ち主が決めた物でこの役が決め直さない・方針とぶつかる単位は `reason` にどの行とぶつかるかを書き、方針を理由に単位を消さない（判断は人）`<!-- end policy -->` — 条件: port `policy` が空でない。
6. `{shared:unknown-asks}`（見出しは断片が持つ。段落 `unknown_rows`・`unknown_none`、口 `{kind_none}`・`{kind_cause}`・`{kind_shape}`・`{kind_scope}` ← `headdepth.NONE`・`CAUSE`・`SHAPE`・`SCOPE`、`{unknown_rows}` ← port `row_asks` の行を plan.md の 2.3 の 22 の札で組んだ行〔`- line <item> (<kind>): request text 「<cause_quote>」・place <where>「<code_quote>」`、番地が無ければ `place: none (the cause is not visible in code)`。種類の語は字のまま〕、`{unknown_why}` ← port `depth_why`〔空なら `headdepth.NO_RECORD`〕）。`unknown_rows` は行が 1 つ以上の時、`unknown_none` は行が無い時。
7. `## Steps`（決まった文）: 木探索の段落（止める目安・4 つの枝・全部の木を作ってから枝同士を並べる・同じ根の木は束ねる・上位で交わる原因は一撃の候補で束ねる理由にしない・ある木の実測が別の木を反証しないか）と手順 1〜9（9.4 の「残す指示の一覧」の 21〜42 を全部）。差し込み口は `{world_prefix}`（← `worldmark.SOURCE_PREFIX`）・`{undecided_min}`（← `src/judge.py` の `UNDECIDED_MIN = 10`。今の `_precedent_errors` の `blank(…, 10)`）。
8. `## Question ledger (questions)`（決まった文）: 書ける欄・kind ごとの出どころと要る欄と意味（今の `QUESTION_KINDS` の `note` と `ORIGIN_NOTE` の文を英語にした物。kind の語は字のまま）・status ごとの要る欄と意味（今の `QUESTION_STATUS_NOTE`）・split と rule の出どころの決まり・awaiting の決まり・問いは阻害要因を消さない・答えと同じ問いの key・field の key の頭を素材の名で始める・「測り方: `<命令>`」の決まり（9.4 の 43〜50）。今の md と材料の段の 2 か所に在った台帳の決まりを、この 1 か所にする。
9. `## How to write answer_ties`（決まった文）: 4 つの行の形と、受け付けが結びを求める答えと拒む場合（9.4 の 51〜55）。`{tie_min}` ← `gatemarks.ANSWER_TIE_MIN`（20）。
10. `## How to answer`（決まった文）: 欄の並び・`materials_missing` は全部の欄が明示返答を持つなら空・`carried_r1` は空の配列（この block には前の周の独立の目が届かない）・言語の 1 文と `{lang}`（← `prompt.lang(port lang)`）: `reason`・`origin_analysis`・`why_chain`・`prescriptions`・`framing`・`one_shot`・問いの `reason`・`resolution`・`options`・先行例の `problem`・`reason`・`searched`・`undecided_because`・`why_outside`・結びの `none`・class_query の `note`・`examples_unavailable`・`misses_omitted_why` を `{lang}` で書く。key・enum の値・コードの識別子・パス・コマンド・エラーの文はそのまま。写した key は訳さない（字の一致で突き合わせる）。
11. 結びの 1 文: `Return only JSON that matches the output schema.`

`when` の値は `{rejected, spawns: False, purpose, repo_review, pr_text, policy, prior_notes, prior_redesign, recorded_none, unknown_rows, unknown_none}`。値は上の差し込み口の全部を、段落が入らない回も空の字で渡す（README の 5.2）。md に `$` の直後に英字か `{` が続く字を置かない（materials.md の 3.1）。JSON の例の `{answer, to}` などは差し込み口の形に合わないので字のまま残る。合う形の字は `{{`・`}}` で書く。

md の本文の正本は `workflows/diagnose/prompts/diagnose.md`。この設計書は組み立ての順と、残す指示の一覧（9.4）だけを持つ。

共通の断片 `unknown-asks`・`recorded-policy`・`prior-failures` の本文は plan.md の 2.3 で決めた物を使い、この設計書には写さない（2 波目で plan と同時に書いた。食い違えば先に main に入った物に揃える）。

### 2.4 返す形

今の `output_format` のまま（`workflows/judge/works-factory-judge.yaml:1814-1987`）: `units`（`key`・`label` が必須。`disposition`・`reason`・`reopen_evidence`・`origin_analysis`・`why_chain`・`prescriptions`・`closed_note`・`class_query`〔`how`・`counts`・`total` が必須。`note`・`hits`・`misses`・`examples_unavailable`・`misses_omitted_why`〕）・`questions`・`framing`・`one_shot`・`materials_missing`・`carried_r1`・`router`・`reburn_causes`・`one_shot_closes`・`precedents`・`out_of_purpose`・`answer_ties`。必須は `units`・`questions`・`framing`・`one_shot`・`materials_missing`・`carried_r1`・`one_shot_closes`・`precedents`。`reburn_causes.cause` の enum の日本語の語（`コード`・`レビュアー`・`規約`・`前の周の修正`）も字のまま。人に見せる欄と言語は 2.3 の 10。

### 2.5 描いた骨組み（例の run `df5e111f-ea97-409b-8066-2245d32746ab` の値）

```markdown
You are the judge: you give a judgment the caller cannot overrule …（role-judge の断片 5 行）

Rules for queries to outside services and for the sources you use: …（query-rule の断片）

## This role

You are the judgment role of this run. You bundle the person's fix request into root-cause units and fix each unit's label and disposition. …
You only read. Your tools are Read, Grep, Glob, WebSearch, and WebFetch. …

## Inputs

- Materials file: <run の place>/diagnose-input.json. Read it first. …
  - `materials`: …
  - `request_findings`: …
  - …
- Frozen purpose: 出口の語 deliver=pr の run が PR 用の commit を積むとき、commit のフックが、…（約 230 字）
- Target diff: <run の place>/diff.patch (Read it; it is `git diff 4428f368d229f2d4f4343122c620c3fdeb334184 63c243e8cd9016d930eecfaae0d48962efc546c7` …). Repository: <run の作業ツリー> (read version 63c243e8cd9016d930eecfaae0d48962efc546c7).
- Review viewpoints: <工場の置き場>/lib/REVIEW.md. …
- …

（prior-failures の断片: 前の run の行も作り直しの行も無いので、どちらの段落も入らない）

（recorded-policy の断片の見出しと決まり）

- Policy document: none
- answers of the request: none
- Answers a person gave at approval nodes: not given to this role
- Settled points (from the decision records):
  - name `docs/owner-decisions.md の deliver-via-archon-pr の「導いた事」の 4 つ目（390 行）と「決め」の 2 つ目（384 行）`: pr-commit は対象の commit のフックを飛ばさず、…
  - …（3 行）

## Unknowns per request line, and what to do (…)

For each line below, do what its kind asks:

- `無し`: Check first that the quoted place is really the place to fix. …
- `原因`: …
- `形`: …
- `範囲`: …

- line 1 (無し): request text 「hook_env を tree_run.outside_env(os.environ) に寄せ」・place workflows/merge/scripts/pr_commit.py:73-76「userenv.read_gh_first(env)」

## Steps (steps 1–7 as a tree search …)

1. **Clustering**: …
…
9. **Stable keys**: …

## Question ledger (questions)

…

## How to write answer_ties

…

## How to answer

…
Return only JSON that matches the output schema.
```

例の run の `diagnose-input.json` の値（鍵の頭だけ）: `materials` は 14 欄（`base_determination` found・count 0、`local_checks` clean、`parallel_pr` found 1、`prior_decisions` found、P1 の観点 9 本は `not_applicable`〔判定から入る run〕、`procedure_trace` not_applicable、`fix_closure` not_applicable）・P1 の所見の鍵 9 つと `purpose_review` はどれも null・`prior_decisions` は突合の返答（決着済みの論点 3 行）・`request_findings` は 1 バッチ（origin「人の依頼（<依頼のファイル>）」・行 1 つ）・`constraints` は 1 行（`kind` 実測）・`world_rows` は 1 行（類 `w-459d38b29048`、依頼の解き方は定石と同じ）・`answers` は `[]`・`changed_files` は `[]`。`intake.json` の値は、`row_asks` が 1 行（行 1・`無し`・番地 `workflows/merge/scripts/pr_commit.py:73-76`）・前の run の行と作り直しの行は無い・記録された方針は `settled` の 3 行。PR・方針・対象の REVIEW.md は無いので、`pr_text`・`policy`・`repo_review` の段落は入らない。1 回目で通ったので却下の段落も入らない。`lang` は空で、`{lang}` に既定の文が入った形。

### 2.6 今の指示との差

- 足した差（新旧の指示の比べの納品。2026-10-19）: `undecided_min`（先行例の `undecided_because` の最小の字数。受け付けは前から照らしていた）を md に足した。
- 足した差（新旧の指示の比べの納品。2026-10-19）: 「推し:」の印を日本語の字に固定した（受け付けが読む字）。指示は見出しを写せと言う。
- 足した差（新旧の指示の比べの納品。2026-10-19）: 素材の欄から `gate_efficacy` と `gate_arms` を外した（11 節の 27）。素材の欄の欠けを言う訳の句は落ちた。
- 足した差（新旧の指示の比べの納品。2026-10-19）: 世界の解の行は札の文でなく素の JSON になったので、`basis: knowledge` は web で確かめていない・`versus.verdict` は依頼の解き方との比べ・`applies` が空の行は答えの要らない行、の意味を md の `world_rows` の箇条に 1 文ずつ足した（今の札の文と同じ意味）。

作り直しの時の、古い指示との差の記録。後の指示の変更では、ここに足さない。

今の指示は 3 か所に在る: `workflows/judge/commands/diagnose.md`（120 行。`$diagnose-reject.output.*` と `$diagnose-prep.output.*` を Archon が入れる）・役が Read した `judge/diagnose-brief.md`（`lib/judge_accept.py:2800-2832` の `brief` が組む。`DIAGNOSE_EXCERPT`〔`:2717`〕の「## 入力」の段と問いの台帳の段を graphloops の描き方で埋め、頭に世界の解の行と頭の深さの節、尾に依頼と PR・依頼の answers・前の run の行・記録された方針・人の方針）・材料の段の値の表（`PROMPT_TABLES`、`:180-192`）。

- 移した: 材料のファイルの決まった文（`BRIEF_HEAD`・`DIAGNOSE_EXCERPT` の各行の頭の説明・`ANSWERS_HEAD`・`LEDGER_HEAD`・`worldmark.HEAD`・`POLICY_HEAD`）を md の `## Inputs` の鍵ごとの箇条へ。材料のファイルには値の JSON だけが残る（11 節の 1）。
- 移した: 前の run の行の節の見出し（`carry.PRIOR_HEAD`・`REDESIGN_HEAD`）を共通の断片 `prior-failures` へ、記録された方針の節（`policy.RECORDED_HEAD`・`RECORDED_RULE`・`RECORDED_NONE` と行の札）を共通の断片 `recorded-policy` と行の英語の札へ（plan と同じ物。plan.md の 2.3）。節は材料のファイルでなく指示の中に入る（今と同じく行を貼る形）。
- 移した: 台帳の表の文（`QUESTION_KINDS` の `note`・`ORIGIN_NOTE`・`QUESTION_STATUS_NOTE`・`PROMPT_TABLES` の `no_open_origin`）を md の `## Question ledger` へ。Python に残るのは語と要る欄（受け付けが使う値）だけ。
- 移した: 頭の深さの種類ごとの指示（`headdepth.ASKS`・`CHOOSE`）と見出し（`headdepth.UNKNOWN_HEAD`）を共通の断片 `unknown-asks` へ（head-depth.md の 8 節の 4・plan.md の 2.3）。行ごとに指示を繰り返して貼る形（「- 行 N（種類）: …・指示: <ASKS>」）は、種類ごとに 1 回書いた指示と、種類の語を名指す行に替えた（役が引く指示は同じ）。種類が無い run の「決まっていない（訳: <控えの why>）」は、port `depth_why` で今と同じ訳を添える。
- まとめた: 台帳の決まりが md:95-105 と材料の段（`DIAGNOSE_EXCERPT` の末尾の「問いの台帳」）の 2 か所に在り、md が「ぶつかれば材料の方に従え」と言っていた物を、md の 1 か所にした。
- まとめた: 「素材のどれかが明示返答を欠くなら materials_missing」が md:48 と `DIAGNOSE_EXCERPT` の 2 か所に在った物を 1 回に。依頼の行を反証の対象とする文（md:40 と `DIAGNOSE_EXCERPT` の「修正依頼の入口」）も 1 回に。観点の正本の段（md:49 と `DIAGNOSE_EXCERPT` の「観点の正本」）も 1 回に。
- まとめた: 却下の段落（md:3-9 と md:54）を共通の断片 `{shared:rejected}` の 1 回に。却下の無い回は段落ごと入れない（「下の理由が空なら 1 回目」の文は要らない）。
- 変えた: 却下の理由を前の回の 1 件（今の `reject.py`、`LOOP_PREV` の `reason`）から、輪の却下の全部を古い順に（README の 13 章の決め。11 節の 6）。
- 移した: 役の定義の 12 行（md:13-26）を共通の断片 `{shared:role-judge}` へ（中の外への検索の決まりは `query-rule`）。
- 移した: 言語の 1 行（md:1。`rolekit.LANG_RULE`）を md の結びの言語の 1 文に。汎用の欄の並び（reason・how・what・why・異議…）は、この役の人に見せる欄の名指しに替えた。
- 移した: 人の方針の段（md:50-51 と材料の尾の `POLICY_HEAD` の本文）を、共通の断片 `{shared:policy}`（本文の貼り付けと方針の一般の決まり）と、この役だけの 3 文に。方針の本文の上限（`policy.PASTE_CAP`）と続きの置き場の 1 行は今のまま。
- 消した: 材料の段の、1 run = 1 周ではいつも「（この周には無い）」になる行（`DIAGNOSE_EXCERPT` の「前の周の独立の目が返したもの——R1 最小性・R3・R4」と「defer 台帳」）。今の `_diagnose_ctx` は `prev`・`loop.defer_ledger` を組まない（`:2764-2794`）ので、役は一度も値を見ていない。`carried_r1` を空にする文（md:120）は残す（欄が型に在る）。
- 消した: 「仕様の道の受け入れ条件と並行 PR の見逃しも同じ入口で届き」（`DIAGNOSE_EXCERPT`）の「並行 PR の見逃し」。工場では並行 PR は依頼の行を足さない（依頼の行に積むのは `spec_freeze` だけ。`:3102-3131`）。仕様の受け入れ条件のバッチは残る。
- 消した: 「元の graphloops の判定の指示書の同じ段」「共有ボードから描いた物」「engine と同じ描き方」など、元の仕組みの名（材料の頭と台帳の段の見出し）。役が知らなくてよい。
- 消した: ほかの node の id（`$diagnose-reject.output.*`・`$diagnose-prep.output.*`）。値は差し込み口に。
- 変えた: 目的の文が無い run の字。今は `PURPOSE_MISSING`（「目的の文はこの run に無い——目的のノード p0.purpose がこのラインに無く…」、`:1219-1220`）を目的の欄に入れた。新しい形は `<!-- if not purpose -->` の決まった 1 文（ノードの名 `p0.purpose` は落とす）。
- 変えた: 記録された方針の方針の文書の行の「元の置き場」（`alias`）。port `policy` は固めた写しのパスだけを運ぶので、名指しは写しのパス `<写し>:<行>` だけになる（11 節の 7）。
- 足した: `diagnose-input.json` の鍵の説明（今は材料の段の見出しが説明だった）。中身の決まりは足していない。
- 英語にした（#764）。役の名「判定役」は "the judgment role"。

### 2.7 元の works と graphloops の同じ場面

- 元の works の `blk-judge`（`works/blk-judge/`。`lib/judgebrief.py`・`judgetake.py`・`judgeverify.py`）: 工場はほぼ同じ受け付けを写した（#76 `0c4a6793`）。材料を engine の描き方で描いて Read させる形も同じ。この block は描き方を値の JSON と md に替える（11 節の 1）。
- graphloops の `prompts/review-loop/p2.diagnose.md`（48 行）: 手順 1〜9 と台帳の段の元。工場の md はこれに、世界の解の行を先に使う（keep-essence の 12）・目的の外の所見を `out_of_purpose` で名指す・依頼の答えの結び・③ の名乗りの照らし（#478 など）を足した。この block はそのまま持つ。
- graphloops の `p2.history.md`（周の 2 回目の判定）: 工場に無い。持ち主の決め `no-history-for-now`（`docs/nodes.json:23`（#765 で消した））。この block も持たない。
- `_carried_r1_accounted`・`_fork_moves_forward`（前の周の R1 の削除候補・前の周の fork）: 工場は 1 run = 1 周（持ち主の決め carry）で、受け付けはいつも空の前の周を渡すので働かない。この block では写さない（11 節の 4）。
- 両方より良く、残す物: class_query の件数を機械が数え直して置き換え、0 件は置き換えずに印を残す（keep-essence の 7）・class_query の例 hits と misses を同じ旗で問いに当てる・先行例の `world:<類の id>` が世界の解の行に在ることを照らす（keep-essence の 12）・目的の外の所見を材料の行に当てて次の run に運ぶ・③ を名乗る問いが記録された方針を名指すことを照らす。

### 2.8 受け付け（`src/judge.py` の `take`。順は今の `take`、`:816-851`）

1. 返答が JSON のオブジェクト。
2. `outpurpose.split` で `out_of_purpose`、`gatemarks.split_answer_ties` で `answer_ties` を外す。
3. `accept.in_repo` の中で、版 `rev = accept.resolve_rev(repo, "")`（今と同じく HEAD）。
4. 作業ツリー: place の `tree.json` が在れば `materialkit.moved_since(place, repo, accept.status_keys(GUARDED))` が空（違えば「判定役を起こした後から作業ツリーが変わった——…」）。無ければ作業ツリーが綺麗で HEAD が `rev` のまま（今の `_judge_tree_unchanged`、`:431-449`）。
5. `querytest.problems(units, is_open)`: 開いた単位の class_query の例が問いと合う。
6. `world_ref_problems(reply, world_rows)`: 先行例の `world:<id>` が世界の解の行に在る。
7. `querytest.split` で例を外した写しを `judge_output` に通す（`:547-658`）: 1 行の欄（`key`・`reason`）の改行を畳む・単位の key の重なり・ラベルの語・suggest の disposition と defer の理由・開いた単位の class_query と `total`・機械が問いを走らせて数え直し（`_run_query`。place の `count-cache.json`・`count-budget.json`。上限 300 回か 900 秒で、達したら件数を確かめられないとして拒む。0 件なら役の数を残して `note` に印、違えば置き換えて `note` に印）・開いた単位が在れば `one_shot_closes` が空でない・`one_shot_closes` の key が単位に在る・問いの知らない欄・kind と status の語・要る欄・fork の `options` が 2 つ以上・出どころ（`origin`・`depends`）の域（単位の key・素材の名・R1〜R4）・域が none の kind は出どころを持たない・`split` と `rule` は開いた単位を出どころにしない・決着した問いの状態が出どころの開きと合う・awaiting_human の素材ごとに awaiting の問い・`materials_missing` が空・先行例の key の重なりと出典（`not_found` は `searched`）・開いた単位と人へ回す問いごとに先行例の行・人へ回す問いの行の `undecided_because` が 10 字以上。拒否の文は「judge の返答が記録の語彙に合わない（judge に返させ直す）: …」（今の字のまま。`_name_hints` は写さない。11 節の 18）。
8. `_awaiting_origins`: awaiting の問いの出どころが今 awaiting_human の素材。
9. `outpurpose.problems(outside, material_rows)`: 目的の外の行が材料の行（P1 の所見と依頼のバッチの行）に 1 つだけ当たる。
10. `answer_tie_problems`: 結びの行の形・依頼の答えが返答の問いに 1 つだけ当たるか結ばれている・作り直しの行が全部結ばれている。
11. `recorded_question_problems`: 先行例の `undecided_because` の頭の印で ③（人に問う 3 つの場合のうち「記録された方針の行とぶつかる」。① は先例が割れる、② は優先の付け方で変わる。9.4 の 39）を名乗る人へ回す問いが、記録された方針の行を名指す（`policy.hits`）。
12. 通れば、例を `query-examples.json` に置き換えて書き（例の無い判定は前の例を消すだけ）、目的の外の行を当たった材料の行ごと `out-of-purpose.json`（周 1）に、結びを `answer-ties.json`（周 1）に書き、整えた返答に例と目的の外の行を戻して `judgment.json` に書く（書く順は今のまま。`:543-547`）。返り `{ok: True, reason: <置き換えの注記か空>}`。拒否の時は `judgment.json` を書かない。

- 回数: `rolekit.accept_round(place, "diagnose", raw, take)`。3 回目の却下で `done`（`rolekit.GIVE_UP_AFTER`）。諦めても止めの控えは書かない（今の `_give_up` の `write_stop` は無くし、finish が `works:judge` と `rolekit.given_up_reason` の字を返す。5.6）。
- 却下の理由の文は Python が組む日本語（README の 5.3）。中身は今のまま。

### 2.9 試験

9 節。keep-essence の 7（class_query の数え直し）と 12（世界の解に照らす）を守る。

## 3 node の設計シート: rejudge（再審の役）

### 3.1 役

修正役の異議と 1 回目の判定を読み、異議が挙げた事実を現物で確かめ、採る・退ける・一部採るを決め、変える必要のある単位だけを書き換えて今の周の単位の全部を返す。

### 3.2 port

`objection`・`first-judgment.json`（← `prior`）の `units`（`key`・`label`・`disposition` の写し）・`questions`（`key`・`kind`・`status` の写し）・`framing` と `one_shot`・読ませるファイル（← `first-judgment.json` と、`prior_brief`・`prior_inputs`・`world_rows`・`purpose`・`spec`・`verify`・`excluded` のうち空でない物の解いたパス）・`policy`（本文）・前の回までの却下（← place の `rejects-rejudge.json`）・`lang`。

### 3.3 組み立ての順（`prompts/rejudge.md`）

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: 却下の控えが 1 件以上。`{rejection}` ← 輪の却下の全部（今の `rejects.py` と同じ）。
2. `{shared:role-judge}`（`spawns: False`）。
3. `## This role`（決まった文）: この run の判定を考え直すために起きている・1 回目の判定はこの会話で書いた物ではなく、その判定と判定役が読んだ材料はファイルに在るので、ファイルから読む（会話の記憶に頼らない）・読むだけ（道具の名。受け付けが役を起こす前の作業ツリーの写しと比べ、変わっていれば拒む）・shell を持たないので git・gh は打てない。md は「新しい会話で起きた」と言わない（輪は `fresh_context: false` で、拒まれた後の回は同じ会話の続き。1 波目を作った時の決め）。
4. `## The objection`（決まった見出し）と `{objection}` ← port `objection`（字のまま）。
5. `## This round's units`（決まった見出し）と `{units}` ← `first-judgment.json` の `units` を `pick(…, ["key", "label", "disposition"])` した JSON（`json.dumps(…, ensure_ascii=False, indent=1)`）。
6. `## This round's ledger` と `<!-- if questions -->` `{questions}`（`pick(…, ["key", "kind", "status"])` の JSON）`<!-- end questions -->` `<!-- if not questions -->` 台帳が空の 1 文 `<!-- end questions -->`。
7. `## Your earlier view` と `<!-- if diagnosis -->` `{diagnosis}`（`framing` と `one_shot` の在る方の JSON）`<!-- end diagnosis -->` `<!-- if not diagnosis -->` 無いの 1 文 `<!-- end diagnosis -->`。
8. `## Files to Read`（決まった見出しと「Read して読め」の 1 文）と、1 行ずつの段落（決まった札と差し込み口）: 1 回目の判定（全部の欄）`{first_judgment_file}`（いつも）・`<!-- if prior_brief -->` 1 回目の判定役に渡した指示 `{prior_brief_file}`（記録された方針・前の run の行・頭の深さの行・人の方針の本文はこの中に在る）`<!-- end prior_brief -->`・`<!-- if prior_inputs -->` 1 回目の判定役が読んだ材料 `{prior_inputs_file}`（対象差分のパス〔鍵 `diff_file`〕・前提の制約・素材の状態・依頼の行は中に在る）`<!-- end prior_inputs -->`・`<!-- if world_rows -->` 世界の解の行 `{world_rows_file}` `<!-- end world_rows -->`・`<!-- if purpose -->` 凍結した目的 `{purpose_file}` `<!-- end purpose -->`・`<!-- if spec -->` 仕様 `{spec_file}` `<!-- end spec -->`・`<!-- if verify -->` 判定の裏取り `{verify_file}` `<!-- end verify -->`・`<!-- if excluded -->` 並行 PR の外す範囲 `{excluded_file}` `<!-- end excluded -->`。
9. `## Settling within the same round`（決まった文。今の md の「P2-9 同じ周の擦り合わせ」の段）: この node が在る訳（異議を自分で覆さず別の会話の役に再判定させる辺が graph に無かった。往復が記録に残らなかった実測 2026-09-13）・規律の 3 条（反論は新しい事実を伴う時だけ通る。事実を自分で確かめ `new_facts` に書く。確かめずに採るのも退けるのも禁じる。機械が空同然の `new_facts` を拒む／往復の数を数えるのはこの役の外で、この役には何回目かは渡らない。回数で返し方は変わらない／判定を確定する権限は移らない。単位を書き換えるのはこの役で、退けてよい）。
10. `## What to do`（決まった文）: 1 事実を現物で確かめる（該当行・記録の値を Read・Grep で照らすことが「実測の再現」。確かめられない事実は「確かめられない:」で始めて書き、採る根拠にしない。1 つも確かめられなければ `退ける` と「足りない:」）・2 `verdict` を決める・3 変える単位だけを書き換えるが `units` は今の周の全部を返す（返さない単位は消える）・ラベルを下げない（[block] から suggest は禁止）・4 `reason` に 1 行。入力が足りない時の返し方（`退ける`・単位を変えずに全部・`new_facts` と `reason` の頭に「足りない:」）。自分の処方の誤りに気づいたら書け（実例の 1 文）。`{facts_min}` ← `src/rejudge.py` の `FACTS_MIN = 20`（今の `rejudge_output` の `blank(…, 20)`）。
11. `<!-- if policy -->` `{shared:policy}` `<!-- end policy -->`（今の md:69-72 の「## 人の方針」は断片の本文と同じ中身）。
12. `## How to answer`（決まった文）と言語の 1 文 `{lang}`: `new_facts`・`reason`・単位の `reason`・`origin_analysis`・`why_chain`・`prescriptions`・class_query の `note`・`examples_unavailable`・`misses_omitted_why` を `{lang}` で。`verdict` の語（`採る`・`退ける`・`一部採る`）・key・識別子・パスはそのまま。
13. 結びの 1 文。

`when` の値は `{rejected, spawns: False, questions, diagnosis, prior_brief, prior_inputs, world_rows, purpose, spec, verify, excluded, policy}`。

### 3.4 返す形

今の `output_format` のまま（`&rejudge_reply`、`:2084-2149`）: `verdict`（`採る`・`退ける`・`一部採る`）・`new_facts`（20 字以上、空白だけでない）・`reason`・`units`（判定の単位と同じ形）。必須は `verdict`・`new_facts`・`units`。人に見せる欄と言語は 3.3 の 12。

### 3.5 描いた骨組み（例の run `82d22f4f-8090-45b3-abea-e2a9cdd8be2e` の値の形）

```markdown
You are the judge: you give a judgment the caller cannot overrule …（role-judge の断片）

## This role

You are woken to reconsider this run's judgment. You did not write the first judgment in this conversation; it and the materials the judgment role read are in files. …

## The objection

（修正役の異議の文。約 230 字。依頼の字のまま）

## This round's units

[
 {"key": "<単位の key 1>", "label": "block", "disposition": "do-now"},
 …（7 行。5 行が block・do-now、2 行が info）
]

## This round's ledger

[
 {"key": "<問いの key 1>", "kind": "fork", "status": "held"},
 {"key": "local_checks: <確かめの名>", "kind": "awaiting", "status": "held"}
]

## Your earlier view

{"framing": "根は 1 つ: …", "one_shot": "…"}

## Files to Read

- First judgment (all fields): <place>/first-judgment.json
- Instructions the first judgment role was given: <1 回目の place>/diagnose-prompt-1.md
- Materials the first judgment role read: <1 回目の place>/diagnose-input.json
- World rows: <世界の解の place>/world.jsonl
- Frozen purpose: <目的の place>/purpose.json
- Verification of the judgment: <裏取りの place>/…
- Parallel-PR excluded ranges: <並行 PR の place>/pr-excluded.json

## Settling within the same round
…
## What to do
…
## How to answer
…
Return only JSON that matches the output schema.
```

例の run は 1 回目で通ったので却下の段落は入らない。仕様と方針は無かったので、その段落も入らない。今の材料のファイルは「1 回目の判定・判定役の材料・対象差分・前提の制約・凍結した目的・素材の状態・世界の解の行・判定の裏取り・並行 PR の外す範囲」の 9 本を並べた（`judge/` の名のファイル）。新しい形では対象差分・前提の制約・素材の状態は判定役の材料の中に値かパスで在る（3.6）。

### 3.6 今の指示との差

- 足した差（新旧の指示の比べの納品。2026-10-19）: `facts_min`（`new_facts` の最小の字数）を足した。
- 足した差（新旧の指示の比べの納品。2026-10-19）: 印「足りない:」「確かめられない:」を英語にした（「推し:」は受け付けが日本語の字を読むので日本語のまま。扱いが割れる）。
- 足した差（新旧の指示の比べの納品。2026-10-19）: 方針が無い run では方針の段を出さない。
- 足した差（新旧の指示の比べの納品。2026-10-19）: 「この役は Bash を持たない」を足した。

今の指示は `workflows/judge/commands/rejudge.md`（77 行。`$rejudge-reject.output.*`・`$rejudge-prep.output.brief_file`）と、役が Read した `rejudge/brief.md`（`_rejudge_brief`、`:3295-3309`）の 2 か所に在る。

- 移した: 材料のファイルの見出しと段（「回す側の異議」「今の周のユニット」「今の周の台帳」「自分の見立て」「1 回目の判定と材料（Read して読む）」「人の方針」）を md の節へ。値（異議・単位・台帳・見立て・パス・方針の本文）は差し込み口に。材料のファイル `brief.md` は書かない。
- 変えた: 読ませるファイルの並び。今の「判定役の材料」（`diagnose-brief.md`）は、1 回目の判定役に渡した指示（`diagnose-prompt-<n>.md`。記録された方針・前の run の行・頭の深さの行・方針の本文を含む）と材料のファイル `diagnose-input.json` の 2 本になる。今の 9 本のうち、対象差分（`diff.patch`）・前提の制約（`premises.json`）・素材の状態（`materials.json`）は `diagnose-input.json` の中に在る（差分はそのパスを鍵 `diff_file` に、制約と素材は値）。1 回目の判定は place に写した `first-judgment.json`。在る物だけを並べる決まりは今のまま。
- 消した: 「新しい会話で起きている（判定役の会話は継がず…）」（md:20）。輪は `fresh_context: false` で、拒まれた後の回は同じ会話の続きなので、この字は 2 回目からの回で誤りになる（1 波目を作った時の決め）。「1 回目の判定はこの会話で書いた物ではなく、ファイルから読め」に言い換えた。
- 消した: 規律の 2 の「超えても決着しなければ、新しい別の judge が会話に参加して…判定する（`p2.rejudge_third`。常設ではなく、そのときだけ立つ）」。工場にも今の works にもその node は無い（`docs/nodes.json:57`（#765 で消した））ので、役に無い仕組みを在ると言っていた。「往復の数を数えるのはこの役の外で、回数で返し方は変わらない」は残す。
- 消した: 節の名「P2-9」「P2 で書いたもの」・「writes が units を丸ごと置き換える」の `writes`（元の仕組みの名）。「返さなかった単位は消える」の事実は残す。
- まとめた: 却下の段落（md:22-29）を `{shared:rejected}` に。拒まれた後の出し直しは、今のとおり出し直しの役（`rejudge-fix`。拒まれた欄だけ返す。4 節）が受ける。1 回目の役が再び起きる回（resume で輪が 1 周目から回り直した時）は、この段落を読んで丸ごと出し直す。
- 移した: 役の定義（md:3-16）を `{shared:role-judge}` へ、人の方針の段（md:69-72）を `{shared:policy}` へ。言語の 1 行（md:1）を結びの 1 文へ。
- 足した物は無い。英語にした。役の名「再審の役」は "the rejudge role"。

### 3.7 元の works と graphloops の同じ場面

- 元の works の `blk-rejudge`（`works/blk-rejudge/`）と graphloops の `p2.rejudge.md`: 判定役の会話の続き（`--resume`）で考え直させた。工場は会話を継がず、保存した判定を読む新しい会話にした（`docs/owner-decisions.md:412` の推しの決め。Archon は include をまたいで会話を継げない）。下げている所として出力 `downgrades` で宣言する（11 節の 9）。
- 元の works の `rejudge-session.json`（判定役の会話が見つからない時の止め）: 工場は「1 回目の判定が無い」時の止めに読み替えた（語 `works:rejudge-session`）。この block も同じ。
- graphloops の `p2.rejudge_third.md`（3 往復で決着しない時の第三の目）・`p2.rejudge2.md`・`p2.rejudge3.md`: 工場も今の works も持たない（再審は 1 周に 1 回。`docs/nodes.json:57`（#765 で消した））。この block も持たない。
- 両方より良く、残す物: 確かめた事実の長さを機械が照らす・単位の前後の差を異議の名指しで分けて報告に出す（争点でない単位の変化を見せる）・block から下げた単位を拒まずに名指す。

### 3.8 受け付け（`src/rejudge.py` の `take`。順は今の `rejudge_take`、`:3348-3388`）

1. 返答が JSON のオブジェクト。
2. 作業ツリーが place の `tree.json` から変わっていない（`materialkit.moved_since`。`accept.status_keys(GUARDED)`）。違えば「読むだけの役が作業ツリーを変えた: 再審の役は…」。
3. `units-before.json` が在る。
4. `querytest.problems(units, is_open)`。
5. `querytest.split` で例を外し、`rejudge_output`: `new_facts` が空同然でない（`EMPTY` の語でなく 20 字以上）。
6. 通れば: 例を `query-examples.json` に足す（置き換えない。今のまま）・`judgment.json` は `first-judgment.json` の全部の欄に、返答の単位を `REJUDGE_UNIT_FIELDS`（key・label・disposition・reason・reopen_evidence）で取った物を `units` に入れた物（今のまま。class_query は残らない。12 節の 4）・`rejudge-reply.json` に返答を足す・`rejudge-diff.json` に差の行 `{round: 1, pass: "rejudge", node: "p2.rejudge", verdict, changed, unnamed_changed, lowered}` を足す（`diff_units`）。
- 返答の形の誤り（`KeyError`・`TypeError`・`AttributeError`・`ValueError`）も拒否の文で返す（「p2.rejudge: 返答の形が違う（…）」。今の字）。
- 回数: `rolekit.accept_round(place, "rejudge", raw, take)`。3 回目の却下で `done`。拒まれた後の回は、同じ会話の続きで出し直しの役（`rejudge-fix`）に拒まれた欄だけを返させ、前の答えと欄ごとに合わせて照らす（4 節）。
- 輪を抜ける時（`done`）: `collect(place)` が `rejudge-exit.json` を書く（今の `rejudge_collect` の形 `{ok, reason, passes, verdicts, unsettled, objection, new_open_units, lowered, unnamed_changed, diff_file, reads_file}`）。受けた再審が無ければ `ok: false` と諦めの理由。止めの控えは書かない（finish が `works:rejudge` を返す）。書けない時の例外は捕まえて、accept は `{ok, done, reason}` を返す（finish が出口を書き直す。5.6）。

## 4 再審の出し直しの役: rejudge-fix（今の出し直しの役を残す）

今の再審の輪は、受け付けに拒まれた後の回で、出し直しの役 `rejudge-fix`（拒まれた欄だけを返させ、受け付けが控え `candidate-rejudge.json` と欄ごとに合わせる。#571 `b46ec691`・#588 `249c88ea`）を起こした。この block も置く（統合の設計書 integration.md の 4.1 の 4 の裁定。最初の版は dry-run が輪を 1 周しか回さないので置かない形にしたが、spec の block が筋書きで出し直しの役に届く形を持つので、同じ形で残す）。

- 輪の形（spec の `spec-write-*` と同じ）: `rejudge-prep`（`with: {prev: "$LOOP_PREV.rejudge-accept.output.ok"}`。返り `{prompt, resubmit}`）→ `rejudge`（`when: resubmit != true`）／`rejudge-fix-prep`（script `rejudge_fix_prep`。`depends_on: [rejudge-prep, rejudge]`・`trigger_rule: none_failed_min_one_success`・`when: resubmit == true`。返り `{prompt}`）→ `rejudge-fix`（`depends_on: [rejudge-prep, rejudge-fix-prep, rejudge]`・同じ trigger_rule と when。`output_format` は再審の役の物で `required: []`）→ `rejudge-accept`（`depends_on: [rejudge, rejudge-fix]`・`trigger_rule: none_failed_min_one_success`・`with: {reply: {from: $rejudge.output, if_skipped: null}, fix_reply: {from: $rejudge-fix.output, if_skipped: null}}`）。出し直しの道の 2 つの node は頭の prep と 1 回目の役の両方に依るので、続きの会話で起きる役の直前の層は 1 node になる。
- 出し直しに入る条件: 前の周の受け付けが拒み（`prev` が偽）、`candidate-rejudge.json` が在る（`rolekit.resubmitting`）。resume で輪が 1 周目から回り直した時は `prev` が空で、1 回目の指示を組む。
- 指示: `prompts/rejudge-fix.md` は共通の断片 `{shared:resubmit}` 1 つ（`rejection` は最後の 1 件、`candidate` は合わせた前の答えの控えのパス）。`rejudge_fix_prep` が `src/inputs.py` の `rejudge_fix_prompt` で組む。
- 受け付け: `rolekit.resubmitted(place, "rejudge", reply, fix_reply, rolekit.merge_fields)` で前の答えと欄ごとに合わせ、`rolekit.accept_parsed` に通す（`src/rejudge.py` の `accept_reply`）。判定役の輪は今も丸ごとの出し直し。
- 筋書き: `fixtures/rejudge-resubmit.stubs.yaml` が 1 周目の `rejudge-prep` の返りを `{prompt: '', resubmit: true}` に差し替え、出し直しの道の `rejudge-fix-prep`（本物が md から組む）・`rejudge-fix`・`rejudge-accept` に届かせる。控えが無いので受け付けは拒み、出口は `works:rejudge` で失敗を返す。
- 残る物: 拒まれた欄だけを返す手間の減り・拒まれた後も同じ会話の続き・却下の理由を古い順に全部渡す（#351。1 回目の役の指示の段落）・3 回で諦める。

## 5 script の node

どの script も `ports.run(compute, fallback)` で包み、落ちない（prep だけは、指示が組めなければ `prompt-error.json` に node と訳を書いてから落ちる。world の 9.1 の 10）。判定と再審の受け付け（`diagnose_accept`・`rejudge_accept`）の fallback は落ちた訳を `prompt-error.json` に `{node, reason}` で、intake の fallback は `intake.json` に `{status: failed, stop_reason, reason}` で残す（出口が訳を返せるように。審査の指摘）。入力は `os.environ.get("INPUTS_<名>")` を字のままで読み、`ports` の form の口に渡す（名を組んで読まない。README の 4.2）。

### 5.1 `intake.py`（`src/inputs.py` の `intake(place, repo, raw)`）

両方の道の頭:

1. place を作り、1.4 の名のファイルだけを消す。
2. `objection` を `ports.text` で読み、空なら `mode: judge`、空でなければ `mode: rejudge`。

判定の道（読む順。どれかが読めなければそこで止め、`status: failed`・`due: false`。理由は「入力 <名>: <訳>」）:

3. `request` を `requestrows.parts`（知らない鍵・下書きの行も拒む）で読む。字のままの空の配列 `[]` でない（ファイル・pointer・容器の形で渡した）のに行が空なら「入力 request: 依頼を渡したのに行が空…」で拒む（今の `check_request` の `minItems` 1。11 節の 29）。落ちれば `stop_reason: works:request`。ほかの入力の落ちは `works:judge`。
4. 素材をそろえる（`assemble_materials`）: `materials` を `ports.json(raw, "materials.schema.json")` で読み、要素ごとに `ports.file`（dict は `json.dumps` してから）で解き、`materialkit.read` で読む。`pr_material` が空か `null` の字でなければ `ports.json(raw, "pr-material.schema.json")` で読み、 `{"role": "parallel-pr", "status": "ran", "reply": null, "materials": {"parallel_pr": <札>}, "base": null, "commits": null}` を並びの後ろに足す。`baseline` が在れば `baseline_local_checks(path)`（読めない・形が違えば `not_run` と訳。今のまま）、無ければ `local_checks` を足さない（`materialkit.assemble` が `not_run`「走っていない…」で埋める）。`materialkit.assemble(docs, local_checks=…)` の 15 欄を `materials.json` に書く。
5. `view = materialkit.take_view(place, repo, base)`。`Reject` なら `works:judge`・「対象差分が取れない（<訳>）——判定役を起こさない」（今の字、`:2858`）。素材の `base_determination` が `not_run`（根を持つ素材の doc が 1 本も無い run）なら、今のとおり見方の根と commit の数で `{status: found, count: view.commits, detail: "<view.base>（始めの記録の差分の根。空なら HEAD）"}` に埋めてから `materials.json` に書く（`base_determination`。今の `lib/judge_accept.py` の素材の束ね）。
6. 依頼のバッチ（`request_batches`）: 人の依頼の行（`request` の行）を `{round: 1, origin: request_origin か「人の依頼（依頼の行）」, findings}`、仕様の行（`spec_rows` を `ports.file` → JSON の配列）を `{round: 1, origin: spec_origin, findings}`。行の無いバッチは置かない（今の `request_batches`、`:1901-1910`）。`spec_rows` が在って `spec_origin` が空なら「入力 spec_origin: spec_rows の出どころの名が要る」で落とす。
7. 材料のファイル（`input_doc`）を `diagnose-input.json` に書く。鍵と値:
   - `materials`: 4 の 14 欄（`files.MATERIALS`。11 節の 27）。
   - `local_findings` ← 素材の観点 `local-review` の `reply.findings`・`consistency_findings` ← `consistency-bypass` の `reply.findings`・`bypass_findings` ← `consistency-bypass` の `reply.bypass_findings`・`external_findings` ← `external-standards` の `reply.findings`・`procedure_findings` ← `procedure-trace` の `reply.findings`・`test_double_fidelity` ← `test-double-fidelity` の `reply`・`main_path_observation` ← `main-path-observation` の `reply`・`provenance` ← `provenance` の `reply`・`prior_decisions` ← `prior-decisions` の `reply`・`purpose_review` ← `purpose-review` の `reply`（今の `_diagnose_ctx` の `process` と `out`、`:2764-2794`。素材の doc が無い・`reply` が null・欄が無ければ null）。役の名と鍵の表は `src/files.py` の `REPLY_KEYS` 1 つに置く。`hygiene` の返答と `procedure-trace` の `unmeasured`・`external-standards` の `rankings` は今も判定役に届いていないので載せない（12 節の 2）。
   - `request_findings`: 6 のバッチ（無ければ `[]`）。
   - `constraints`: port `constraints` の行（オブジェクトの形なら `constraints` の欄）。
   - `world_rows`: `world_rows` が在れば `worldmark.rows(path)`（読めなければ「入力 world_rows: …」で落とす）、無ければ null。
   - `answers`: port `answers` が空でなければそれ、空なら `request` の容器の `answers`（どちらも `carry.parts` が照らした形）。
   - `changed_files`: `view.changed_files`。
   - `diff_file`: `view.diff_file`（place の `diff.patch` の絶対パス）。再審の役は 1 回目の材料のファイルからこのパスで差分に届く（3.6）。
   - 指示と受け付けが使い、材料のファイルに載せない値は `intake.json` の `values` に置く: `prior_rows`・`redesign`（`request` の容器の `prior_failures` に port `prior_failures` を足した行を `carry.is_redesign` で分けた 2 つ。今の `carry.place_prior` と `prior_section`）・`recorded`（`policy.recorded(start, decisions)`。`start` は `{"policy": {"named": "", "path": "", "sha256": None, "copy": <port policy のパスか None>}, "answers": <上の answers>}`、`decisions` は素材の観点 `prior-decisions` の `material.json` のパス〔無ければ None〕）・`row_asks`（port の行）・`depth_why`・`material_rows`（5.3 の行。受け付けが目的の外の行を当てる）。これらは組んだ指示の断片の節に入り、再審の役は組んだ指示のファイル（出力 `brief`）で読む。
   - ここで使う素材の観点の役の名（`local-review` など）は `material.json` の欄 `role` の値（素材の行の形の語。`lib/materialkit` の族の名）で、block の名を名指して呼ぶのではない（11 節の 2）。
8. `materialkit.snap_tree(place, repo)`。`Reject` なら `works:judge`・「役を起こす前の作業ツリーの姿が取れない（<訳>）——判定役を起こさない」。
9. 素材の doc のうち `status` が `gave_up` の物が在れば、`status: stopped`・`due: false`・`stop_reason: works:material`・`reason` は各 doc の `reason` を「／」でつないだ字（今の `materials_given_up` の名指し、`:2862-2866`）。材料のファイルは書いた後なので残る（今も材料を組んでから止めた）。
10. ほかは `due: true`・`reason: ""`。

再審の道:

3. `prior` を読む（字が空か `null` なら None、ほかは `ports.json(raw, "shared:judgment.schema.json")`）。None なら `status: failed`・`stop_reason: works:rejudge-session`・「1 回目の判定（judgment.json）が無い——判定の道を通っていない run。再審せずに止めた」（今の字、`:3326`）。読めない・形が違えば `works:rejudge` と訳。
4. `prior_brief`・`prior_inputs`・`world_rows`・`purpose`・`spec`・`verify`・`excluded`・`policy` を `ports.file` で解く（読めなければ `works:rejudge`）。
5. `accept.tree_state(repo)` を `tree.json` に（`Reject` なら `works:rejudge`）。
6. `first-judgment.json` に `prior` の中身を、`units-before.json` に `{node: "p2.rejudge", units, objection, numbered_keys: [単位の key の並び]}` を書く（今の `rejudge_prep`、`:3337-3341`）。
7. `due: true`。

どちらの道も `intake.json` に `{mode, due, status, stop_reason, reason, values}` を書き、`{due, mode, reason}` を返す。fallback（思わぬ例外）は `{due: false, mode: <2 で決めた物か judge>, reason: "判定役の材料を組めない（<型>: <訳>）"}`（今の `diagnose_prep.py` の字。再審の道は「再審の支度ができない（…）」）で、`intake.json` が無いまま finish が `works:judge`（再審は `works:rejudge`）を返す。

### 5.2 `diagnose_prep.py`（`src/inputs.py` の `diagnose_values(place)`）

`intake.json` と `view.json` から 2.3 の値と `when` を組み、`prompt.emit("diagnose", values, when, prompt.round_of("diagnose"))`。返り `{prompt}`。値の全部（2.3 の差し込み口: `rejection`・`inputs_file`・`purpose_text`・`diff_file`・`base`・`review_rev`・`repo`・`review_md`・`repo_review_md`・`pr_text`・`policy_body`・`hypothesis`・`world_prefix`・`why_min`・`undecided_min`・`tie_min`・`prior_notes`・`prior_redesign`・`recorded_rows`・`kind_none`・`kind_cause`・`kind_shape`・`kind_scope`・`unknown_rows`・`unknown_why`・`lang`）をいつも渡し、入らない段落の値は空の字。`purpose_text` は `purpose` のファイルの `purpose_text`（intake はファイルが在るかだけを見る。JSON として読めなければ prep が組めず、`prompt-error.json` に訳を書いて落ちる。5.5）。

### 5.3 `diagnose_accept.py`

`src/judge.py` の `accept(place, os.environ.get("INPUTS_REPLY", ""), Path.cwd(), world_rows, answers, redesign, recorded, materials, material_rows)`。値は `diagnose-input.json`（`world_rows`・`answers`・`materials`）と `intake.json` の `values`（`redesign`・`recorded`・`material_rows`）から読む（受け付けと指示が同じ値を見る）。`material_rows` は intake が組んで置いた P1 の素材の doc の `reply` を辿った行（`outpurpose._walk` と同じ辿り方。出どころは `p1.<役の名の - を _ にした物>`。`prior-decisions` と `purpose-review` の 2 つは辿らない。今の `MATERIAL_ROLES` の `p0.` と `p1.` の分け、`:1708-1720`）と依頼のバッチの行（出どころ `依頼（<origin>）`）。返り `{ok, done, reason}`。fallback は `{ok: False, done: True, reason: "受け付けが落ちた（<訳>）"}`（purpose の block と同じ）。

### 5.4 `rejudge_prep.py`・`rejudge_accept.py`

- `rejudge_prep.py`（`src/inputs.py` の `rejudge_values(place)`）: `prompt.emit("rejudge", values, when, prompt.round_of("rejudge"))`。返り `{prompt, resubmit}`（拒まれた後の回は `{prompt: "", resubmit: true}` で、出し直しの役の道に回す。4 節）。
- `rejudge_accept.py`: 3.8。fallback は `{ok: False, done: True, reason: "受け付けが落ちた（<訳>）"}` を返し、訳を `prompt-error.json` に `{node: "rejudge-accept", reason}` で残す。出口は、受け付けが `rejudge-exit.json` を書いていればその訳を先に、書いていなければ `prompt-error.json` の訳を返す（5.6）。

### 5.5 指示が組めない時

prep は `prompt.PromptError` と値の読み落ち（`intake.json` が読めない）で、`prompt-error.json` に `{node, reason}` を書いてから落ちる。輪が落ちて finish がその訳を `reason` に書く。

### 5.6 `finish.py`（`src/exit.py` の `finish(place, repo)`）

止めの語（`stopby`）: `works:judge` は `stopby.declare("judge", "受け付けを通った判定が無いままループを抜けた")`、`works:material` は `stopby.declare("material", "素材集めの役の返答を 3 回とも受けられなかった")`、`works:request` は `stopby.declare("request", "依頼の型が通らない・始めの記録が読めない")`（3 つとも今の `lib/judge_accept.py:302-306` と字のまま同じ意味の文。違う文で declare すると同じ過程で `lib/judge_accept` を読んだ時に `ValueError`）、`works:rejudge` と `works:rejudge-session` は表の語 `stopby.REJUDGE`・`stopby.REJUDGE_SESSION`。

順:

1. `intake.json` を読む。読めなければ `status: failed`・`stop_reason: works:judge`（`mode` は `objection` の port の字で決め、再審なら `works:rejudge`）・`reason: "intake.json が読めない（<訳>）"`。
2. intake の `status` が `failed` か `stopped` なら、その `status`・`stop_reason`・`reason`。
3. 判定の道で `judgment.json` が在れば `status: ok`。無ければ `status: failed`・`stop_reason: works:judge`・`reason` は `prompt-error.json` の訳 → `rolekit.given_up_reason(place, "diagnose")` → 最後の却下の理由（輪が諦めの数に届かずに終わった時。筋書きの 1 周） → 「判定役の返答を受けた記録が無い（ループが落ちたか、走っていない）」の順の最初の物。
4. 再審の道で `rejudge-exit.json` が無ければ `src/rejudge.py` の `collect(place)` で書く。出口の `ok` が真で `judgment.json` が在れば `status: ok`・`rejudge_verdict` は出口の最後の `verdicts`（`verdict_of`）。ほかは `status: failed`・`stop_reason: works:rejudge`・`reason` は出口の `reason`（無ければ 3 と同じ順の字で、役の名は `rejudge`）。
5. `judgment.json` が無ければ `EMPTY_JUDGMENT`（`{units: [], questions: [], framing: "", one_shot: "", materials_missing: [], carried_r1: [], one_shot_closes: [], precedents: []}`）を書く。
6. `status` が `ok` なら `units = judge.structure_units(judgment, repo, record=place / "structure-units-dropped.json")`・`questions` は台帳の `gatemarks.asks_human` の行・`ready = bool(units)`。ほかは `[]`・`[]`・`false`。
7. pointer は `ports.pointer(path)` で、1.2 の条件のとおりファイルが在る時だけ（`judgment` はいつも）。`downgrades` は 1.2 の 1 行。`report` は 5.7。
- 落ちない: 1〜7 の外の例外も捕まえ、`status: failed`・`stop_reason: works:judge`（再審なら `works:rejudge`）・`reason: "判定の出口が落ちた（<型>: <訳>）"`・`judgment` は place に `EMPTY_JUDGMENT` を書けた時だけ pointer（書けなければ fallback の返りの `judgment` は `{type: archon_artifact, run_id: <WORKFLOW_ID>, path: "judgment.json"}`）。今の `verdict.py` の `fallen`・`verdict_fallback` と同じ決まり（Archon は pointer の先が在るかを照らす）。出力が JSON に書けない（`allow_nan=False` で落ちる値）時も同じ fallback（今の `verdict.py` の終わり）。

### 5.7 報告の行（`src/report.py`）

- 判定の道: `status` が `ok` でなければ頭に `f"判定: {reason}"`。続けて `outpurpose.report_lines(place)`（判定が目的の外とした所見。今の `runreport._outside` の 2 つ目）と、例で証明できない問いの行（今の `runreport.unproven_lines`、`lib/runreport.py:691-696` の字。`querytest.unproven(judgment の units, gatemarks._fix_duty)` から `f"{querytest.UNPROVEN_HEAD}: {n} 件"` と 1 件 1 行）。
- 再審の道: `status` が `ok` でなければ頭に `f"再審: {reason}"`。続けて、出口の往復と答えと異議の 1 行（今の `runreport.rejudge_lines` の頭の行の字、`:735-741`）・block から下げた単位の行（今の `rejudge_lowered` の字。今のラベルは place の `judgment.json` から）・単位の前後の差の行（今の `rejudge_changes` の字、`:704-721`）。再審が直す単位にした単位の行（修正の事実が要る）と「再審されずに残った異議」の行は line（1.6）。

## 6 今の works との比べ（確かめ・守り・倒し・やり直し・書く順・指示の全部）

今の役が持っていた物を 1 つずつ、block のどこに在るか、消すなら訳と並べる。指示の文は 2.6・3.6・4 節と 9.4。

- 判定の支度（`diagnose_prep.py` と `diagnose_prep`、`:2843-2872`）:
  - 止めの控えが在れば組まない → 消す。前の段の落ちで回すかは graph の `when:`（README の 4.3）。
  - 対象差分を取り直す・取れなければ go 偽 → 5.1 の 5（同じ字）。
  - 素材の 15 欄をそろえる（`fill_materials`。回さない役の埋め・諦めの埋め・`base_determination`・`fix_closure`・残りの not_run）→ 埋めは素材の観点の block が返す（materials.md）。そろえるのは `materialkit.assemble`（5.1 の 4）。
  - `local_checks` を直す前の結末から写す（`baseline_local_checks`）→ 5.1 の 4（写し）。
  - 材料のファイルを組む（`brief`）→ `diagnose-input.json` と md（11 節の 1）。
  - 役を起こす前の作業ツリーの姿を置く → 5.1 の 8（`tree.json`）。
  - 素材の役が諦めていれば、材料を組んだ上で `works:material` で止める → 5.1 の 9。
  - 例外は go 偽と「判定役の材料を組めない（…）」→ 5.1 の fallback（同じ字）。
  - 観点の正本のパス（`review_md_paths`）→ `materialkit.review_md_paths`。
- 判定の輪の頭（`reject.py`）: 前の回の理由と言語の 1 行を返す・lib が読めなくても訳の 1 行を返す → 理由は prep が place から全部（11 節の 6）、言語は port `lang`。lib が読めなければ prep が落ち、finish がその訳を返す（黙った既定にしない）。
- 判定の受け付け（`diagnose_accept.py` と `accept`・`take`・`_judged`・`judge_output` ほか）→ 2.8 に 1 つずつ。`status_guarded: true` → `GUARDED = True`。諦めた時の止めの控え（`_give_up` の `write_stop`）→ finish の `works:judge`（5.6 の 3）。
- 判定の受け付けの前の周の照らし（`_carried_r1_accounted`・`_fork_moves_forward`・`defer_ledger`）→ 消す（11 節の 4）。
- 再審の支度（`rejudge_prep.py` と `rejudge_prep`、`:3312-3345`）:
  - 1 回目の判定が無ければ `works:rejudge-session` で止める → 5.1 再審の 3。
  - 判定の形・異議が空・作業ツリーの姿・始めの記録が読めなければ `works:rejudge` → 5.1 再審の 3〜5（異議が空なら判定の道になるので、この確かめは道の分かれ目に吸われる）。始めの記録は読まない（方針は port `policy`）。
  - 単位の前の写しは 1 回目の前だけ → intake で 1 回だけ書く（intake は輪の外）。
  - 材料のファイル `brief.md` → md（3.3）。
  - 例外は「再審の支度ができない（…）」で止める → 5.1 の fallback。
- 再審の輪の頭（`rejects.py`）: 輪の却下の全部・言語の 1 行・出し直しの指示書と `resubmit` → 却下は prep が place から、言語は port。出し直しの指示書は `rejudge-fix` の md（`{shared:resubmit}`。4 節）。
- 出し直しの役（`rejudge-fix`）と、受け付けの合わせ（`rolekit.resubmitted`・`merge_fields`・控え `candidate-rejudge.json`）→ 置く（4 節。`src/rejudge.py` の `accept_reply`）。
- 再審の受け付け（`rejudge_accept.py`・`rejudge_take`・`rejudge_collect`）→ 3.8。出口が書けない時の止めの控え → finish が出口を書き直し、それでも無ければ `works:rejudge`（5.6 の 4）。
- 返す節（`verdict.py`・`verdict`・`verdict_fallback`）:
  - 決して落ちない・lib が読めない時の約束の形・JSON に書けない時 → 5.6。
  - 判定と目的の pointer の先を空の形で置く → 判定は 5.6 の 5。目的の pointer は purpose の block の物（この block は返さない）。
  - 公開の隣のファイル（前提・裏取り・外す範囲・素材・目的の監査・深さの控え）を空の形で置く・再審の置き場へ写す → この block は自分の物（`materials.json`）だけを返す。前提・裏取り・外す範囲・深さは各 block、目的の監査（今の `verdict` が素材の返答から `purpose-review.json` を書いた所、`:3958-3961`）は purpose-review の block の `material` の `reply`（purpose-review.md の 1.6）。再審の道で写す要は無い（line が 1 回目の物を持ち続ける。1.6）。
  - `_missing_stage`（前提・目的が無ければ止める）→ judge のまとめ（premises.md・purpose.md の 1.6）。
  - 世界の解の pointer は行が在る時だけ → world の block の `rows`。
  - `structure_units` と捨てたパスの記録 → 5.6 の 6。
  - `ready` → 1.2。`rejudge_verdict` → 5.6 の 4。
  - `head_depth`（深さの欄）→ head-depth の block。`optional` の宣言（世界の解・頭の深さ）→ judge のまとめ（この block の node は落ちても line が先へ進めてよい物を持たないので、欄 `optional` を置かない）。
  - `require_ports`（前の版の判定の返りを受けたら止める）→ line（受け皿の側）。
- 入口（judge の `intake.py` と `intake`、`:3832-3868`）: 再審なら判定の置き場に触らない → 道は `objection`。依頼の行を型に通す・止めの語 `works:request` → 5.1 の 3（`requestrows`）。運ばれた制約 → premises の block。前の run の失敗の行を 1 度だけ置く → 5.1 の 7 の `prior_failures`・`redesign`。入口の作業ツリーの姿 `judge-tree.json` → 並行 PR と前提の block がそれぞれ取る。世界の解の切り替え → graph。
- YAML の鍵: `review_launch`・`retry`・`fresh_context: false`・`max_iterations: 3`・`until_bash`・`trigger_rule: none_failed_min_one_success`・`if_skipped: null` → 1.3（同じ）。`diagnose-prep` の `when`（判定の道だけ）・`verify-merge` の `when` → 道の `when`（1.3）と、裏取りは verify の block。
- 例の run の記録の照らし（`tests/e2e/evidence.json` の J67〜J82・J100・R76・L-D41・L-D44・L-W42）→ 組み込みで、`where` を新しい place（`parent/judge/diagnose-run/…`・再審の include の id の下）に、`writer` を `src/judge.py` の関数の名に替える。

## 7 単独で呼ぶ

```sh
bin/works-factory workflow run works-factory-diagnose --cwd <対象> \
  --input request='[{"where":"stats.py:4","text":"mean は 2 でなく 3 を返す。分母を len(xs) にする"}]'
```

素材・世界の解・前提は渡さなくても回る（素材は全部 not_run、世界の解の行は無い）。再審だけを回すには `--input objection='<異議>' --input prior=<judgment.json のパス>` を渡す。出力は `workflow get <run>` の `finish` の返り。始めの記録は要らない。

## 8 作るファイルと触るファイル

作る: `workflows/diagnose/`（YAML・`prompts/` 2 本・`scripts/` 6 本・`src/` 7 本・`schemas/` 4 本・`fixtures/` 3 本）・`tests/blocks/diagnose/`。main に無ければ足す: 共通の断片 `workflows/.shared/prompts/` の `policy.md`・`recorded-policy.md`・`prior-failures.md`・`unknown-asks.md`、共通の形 `workflows/.shared/schemas/` の `judgment.schema.json`・`prior-failures.schema.json`、`workflows/.shared/AGENTS.md` の名の一覧の行（足した名を「今在る名」へ移す 1 行ずつ）。触らない: `lib/`（読むだけ）・`workflows/`・ほかの block・graph（judge のまとめと line は後の PR）。

## 9 試験

### 9.1 standalone の fixture（`workflows/diagnose/fixtures/`。AI の node だけを差し替え、`exec-code: true`）

- `standalone.stubs.yaml`: 入力は `request`（JSON の字 1 行）だけ。`diagnose` を開いた単位の無い返答（`units: []`・`questions: []`・`framing: <1 文>`・`one_shot: ""`・`materials_missing: []`・`carried_r1: []`・`one_shot_closes: []`・`precedents: []`）で差し替える。`reached: [intake, diagnose-prep, diagnose, diagnose-accept, finish]`。`resolved-text-contains: {diagnose: <md の ## This role の 1 文目の決まった字>}`。finish は `status: ok`・`ready: false`・`stop_reason: ""`（今の `no-open-units.stubs.yaml` の道）。
- `gave-up.stubs.yaml`: 入力は `request` だけ。`diagnose` の返答の単位のラベルが `bogus`。輪は 1 周で終わり（dry-run は `until_bash` を走らせない）、finish は最後の却下の理由で `status: failed`・`works:judge`。run は `completed`。
- `rejudge.stubs.yaml`: 入力 `objection`（1 文）と `prior`（JSON の字。単位 1 つ `{key, label: block, disposition: do-now}`・ほかの欄は空）。`rejudge` を `{verdict: 退ける, new_facts: <20 字以上>, reason, units: <prior と同じ 1 行>}` で差し替える。`reached: [intake, rejudge-prep, rejudge, rejudge-accept, finish]`。`resolved-text-contains: {rejudge: <md の ## This role の 1 文目の決まった字>}`。
- どの筋書きも差し替えるのは AI の node だけ（script の node は本当に走る）。入力は pointer の値を持たない（README の 7.1 の 4。`prior` は値そのものの JSON）。`rejudge-session`（`prior` が null）の道は 9.2 の試験が見る（筋書きでは AI の node に届かない）。

### 9.2 `tests/blocks/diagnose/`

- `test_judge.py`（受け付け。写す元 `lib/tests/test_judge_accept.py`）: `JudgeTakeCase` の全部（`:154-620`。`take` の呼び方を `src/judge.py` の引数の形に、置き場 `judge/` を place に替える）・`DiagnoseGiveUpCase`（`:113-130`。止めの控えでなく `rolekit.given_up_reason` の字を照らす）・`StructureUnitsCase`（`:767-818`）・`TablesCase` のうち `LABELS`・`QUESTION_KINDS`・`QUESTION_STATUS` の照らし（`note` の字の照らしは md の試験へ）・`tests/workflows/test_judge.py` の `AcceptLoopTest`（`:998-1076`。`test_cache_left_by_a_material_role_is_not_the_judges` は、素材の観点の block が自分の place に写しを取るので、判定役の写しとは別の place になることの照らしに替える）・`ReplyTypeCase.test_diagnose_reply_outside_the_type_is_rejected`。keep-essence の 7 は `test_engine_recounts_the_class_query_total`・`test_defects_query_needs_misses_and_must_not_match_the_fixed_form`・`test_class_query_examples_that_do_not_match_are_rejected`、12 は `test_precedent_source_not_in_world_rows_is_rejected` を名で残す。
- `test_rejudge.py`（写す元 `lib/tests/test_judge_accept.py` の `RejudgeCase`・`RejudgeDiffCase`〔`:2123-2270`〕、`tests/workflows/test_judge.py` の `RejudgeTest`・`RejudgedVerdictTest`〔`:1162-1297`〕・`ReturnsShapeTest.test_rejudge_vocabulary_matches_output_format`〔YAML の enum と `REJUDGE_VERDICTS`〕・`ReplyTypeCase.test_rejudge_reply_outside_the_type_is_rejected`）。足す: 拒まれた後の回の prep が輪の却下の全部を古い順に `{shared:rejected}` に入れる（今の `LoopTest.test_third_fresh_spec_role_reads_every_reject_of_the_loop` の再審の形）。今の出し直しの試験（`LoopTest.test_spec_resubmit_returns_only_the_rejected_fields` の再審の分）は写さない（4 節）。
- `test_inputs.py`（支度。写す元 `tests/workflows/test_judge.py` の `BaselineTest`・`PriorFailuresTest`・`MaterialGiveUpTest`〔`:1299-1361`〕、`lib/tests/test_judge_accept.py` の `BriefCase` のうち値を見る物〔`test_brief_carries_the_head_depth_row_kinds`・`test_brief_pastes_out_replies_under_material_roles_nodes`・`test_brief_carries_the_human_policy_cut_at_the_paste_cap`・`test_diagnose_prep_stops_after_material_give_up`〕）: 素材の doc から 15 欄（並行 PR の札を含む）・役ごとの返答の鍵（`REPLY_KEYS`）・依頼のバッチ（人と仕様の origin）・容器と port の answers と prior_failures・作り直しの行の分け・記録された方針の行（`prior-decisions` の決着済みの論点が `settled` に）と、その英語の札が plan.md の 2.3 の字のとおり・頭の深さの行の札・行が無い時に `depth_why`（空なら `headdepth.NO_RECORD`）が訳に入る・`world_rows` が読めない時の落ち・`materials` の要素が読めない時の落ち（「入力 materials: …」）・`spec_rows` だけで `spec_origin` が空の時の落ち。
- `test_diagnose.py`（script を子のプロセスで回す。`tests/blocks/kit.py` の `Run`）: 判定の道を `intake` → `diagnose_prep` → 台本の返答 → `diagnose_accept` → `finish` と回し、開いた単位 1 つで `ready: true`・`units`・`questions`・pointer を照らす。開いた単位の無い返答で `ready: false`・`stop_reason: ""`（今の `StopPathTest.test_no_open_units_is_not_a_stop`）。3 回拒んで `works:judge`。素材の観点が諦めて `works:material`（役を起こさない）。`request` が読めなくて `works:request`。再審の道で `prior` が null なら `works:rejudge-session`、受け付けて `rejudge_verdict`・`rejudge_exit`・`rejudge_diff`・`judgment` が 1 回目の欄を持ち単位だけが替わる。finish が落ちない（壊れた `judgment.json`・`intake.json` が無い。今の `VerdictNeverFailsTest`）。指示が組めない時に `prompt-error.json` の訳が `reason` に出る。
- `test_prompts.py`: 2 本の md が 5.2・5.4 の値の全部で `prompt.render` を通る（段落の真偽の全部の組で）。md が `QUESTION_KINDS`・`QUESTION_STATUS`・`LABELS`・`REJUDGE_VERDICTS` の語を全部字のまま持つ。`diagnose-input.json` の鍵が全部 `prompts/diagnose.md` に `` `鍵` `` の形で在る。2 本の md と使う断片に「new conversation」の字が無い（輪が `fresh_context: false`。1 波目を作った時の決め）。
- `test_place_names_match_lib`: `src/files.py` が写した名が `lib/marks.py`・`lib/rolekit.py`・`lib/judgebeside.py` の名と同じ。
- 写さない試験（古い中身だけを見る）: `tests/workflows/test_judge.py` の `CopiedTextsCase`（元の works の字の台帳）・`BriefCase` の 3 本（言語の 1 行を始めの記録から引く今の形）・`LoopTest.test_roles_receive_the_reject_reason_through_the_loop_head`・`test_reject_script_returns_the_reason_as_is`（頭の node が無くなる）・`ScriptReturnsTest`（今の返す節の欄の名）・`lib/tests/test_judge_accept.py` の `VerdictPublicCase`・`VerdictPortsCase`・`PublicFileReadersCase`（judge 全体の返りの形。judge のまとめの試験へ）。
- 読み手の側の試験はそれぞれに残す: verify の block（`judgment` を読む）・line（再審の返りの受け皿・「再審されずに残った異議」・直す単位にした単位）・report（`report` の節を並べる）。

### 9.3 本物の単独の run

7 節の命令で、判定の道を 1 回（`request` だけ）と、その run の `judgment` を `prior` に渡した再審の道を 1 回回す（費用のかかる試しは聞かずに回してよい）。

### 9.4 残す指示の一覧（審査役が英語の md と古い指示を 1 件ずつ照らす）

古い指示を日本語のまま組んだ物と同じ字にする試験は置かない（持ち主の 2026-10-19 の速さの決め）。英語の md は次の指示を全部持つ。番号の後ろは古い所で、`md:N` は今の `workflows/judge/commands/diagnose.md`（57〜73 は `rejudge.md`）の行。消した物と変えた物は 2.6・3.6・4 節に在る。

判定役（`prompts/diagnose.md`）:

1. 判定役は依頼を根本の単位にまとめ、ラベルと disposition を確定させる。直す側が覆せない拘束判断なので、上位のこの役が下す（md:30）。
2. 読むだけ・道具の名・作業ツリーを 1 字も変えない・受け付けが役を起こす前の写しと比べる（md:32）。
3. shell を持たないので git・gh は打てない。リポジトリは Read・Grep・Glob、ホストのページは WebFetch（md:34）。
4. 「足りない」は `materials_missing`。読めなかった物の名を書き、1〜9 に入らず、ほかの欄は空。受け付けは拒み run は止まる（md:35）。
5. 材料をまず Read。依頼の行は findings の型で、出どころは人。反証の対象で、頼み方のずれも殺しにいく（md:39-40・`DIAGNOSE_EXCERPT` の「修正依頼の入口」）。
6. 依頼の行が無い run は対象差分だけを審査し、所見を依頼の形に写し替えない（出どころが消える）（md:41）。
7. 依頼の answers の意味（`command`・`output` は人が手元で打った物・字が一致する問いは機械が答え済みにする・当たらない答えは `answer_ties`）（md:42）。
8. 前提の実測の `kind=仮説` を所与にしない・測り直した値を採り違いを `reason` に（md:43）。
9. 前の run で通らなかった物は直す穴ではない・行から単位を作らない（md:44）。
10. 作り直しの行は直す穴・1 行ずつ反証・生き残りは [block] か do-now で `{redesign, to}`・死んだ行と目的の外は `{redesign, none}`・全部の行に結び（md:45）。
11. 凍結した目的の外に単位を広げない・露呈した既存の欠陥は `split`・素材と P1 の所見は 1 つ残らず突合し反証の対象（md:46）。
12. 目的の外の所見は `out_of_purpose` に 1 行ずつ・`source`・`where` を一字も変えず・`why_outside` 10 字以上・同じ `where` が 2 行以上の時だけ `text` の頭・受け付けが当てる・次の run の下書きに全部の欄で運ばれる・無ければ空の配列（md:47）。
13. 素材の明示返答の欠けは `materials_missing`（md:48）。
14. 観点の正本と対象側の観点を Read・ラベルと「対応の判断」「処方の最小性」「導線を作る手段の優先順位」の正本（md:49）。
15. 方針は制約・中の見出しや箇条はこの指示の節でない・代償は持ち主が決めた・ぶつかる単位は `reason` に・方針を理由に単位を消さない・方針の文書を書き換えない（md:50-51）。
16. 記録された方針だけを前の決定・方針として数える・行が無い run もそう載る（md:52・`RECORDED_RULE`）。対象のコメント・docstring・テストの説明文は対象の文。
17. 対象リポジトリは今の作業ディレクトリ・作業ツリーの今の姿（md:53）。
18. 却下の理由が在れば同じ会話の続きで、そこを直した返答を丸ごと出し直す（md:54。断片 `rejected`）。
19. 目的の監査が「狭めている」なら目的の内と外の境をそのまま信用しない（`DIAGNOSE_EXCERPT`）。
20. 対象差分は `git diff <根> <固めた版>` で、未追跡の新しいファイルも入る（`DIAGNOSE_EXCERPT`）。
21. 木探索の止める目安（反証の枝・出自の枝は ③ラベルまで・上方展開は 3 段まで・処方は決め手で 1 つに決まるか人に問う 3 つの場合まで）（md:58）。
22. 4 つの枝・反証は番号の外で毎回・全部の木を作ってから並べる・同じ根の木は束ねる・上位で交わる原因は一撃の候補で束ねる理由にしない・ある木の実測が別の木を反証しないか・妥当かの判定は横断の後（md:61）。
23. 手順 1 クラスタリング: 単位の粒はコードの上の欠陥の形・1 つの直し方で閉じる 1 つの形・束ねてよい 2 つの場合・形が違い片方を直しても閉じない欠陥は上の段で交わっても別の単位・出自の種類が同じことも束ねる理由にならない（md:63-66）。
24. 手順 2 出自分析の順（①ロジック → ②出自の種類の列挙 → ③ラベル）・導線の死・迂回・衛生違反・再発明は nit でない・依頼の行は 1 つ残らず突合・`origin_analysis`（md:67）。
25. 手順 3 上方展開は最大 3 段・文化が悪いに着地しない・`why_chain`（md:68）。
26. 手順 4 一撃は反証可能に・組み合わせも見る（互いを不要にする・含む・2 つ揃って閉じる）・`one_shot_closes` に key を名指す・交わる原因が無ければ最も多く閉じる単位の直しとその key・直す単位が 1 つでも在れば空を拒む・直す単位が無い時だけ空（md:69）。
27. 手順 5 ラベル 5 つ・生の finding 単独を [block] にしない・suggest は do-now か defer（既定 do-now・defer は構造的理由だけ・コスト感は理由にならない）・`reason` に事実と当てた反証（md:70）。
28. 手順 6 class_query は直す単位に必須・欄で書く（`how` の `patterns`・`paths`・`count` と任意の旗）・受け付けが git grep 1 本で走らせ shell もパイプも通らない（md:71-72）。
29. 版を書かない（受け付けが固めた版で数え、修正の後は作業ツリーで数え直す）（md:73）。
30. 直す site になる行を全部数える（md:74）。
31. `counts` の向き（defects と population）・population の当たりは全部修正が変える物・在るべき物が無い型は欠けている物を名指して数える（md:75）。
32. 欠陥の行と正しい行が同じ字なら向きを替えて population に・0 件にならないと分かる defects の問いを出さない（md:76）。
33. `hits` と `misses`・defects は直した後の行を misses に 1 つ以上・受け付けが同じ旗で当てる・`examples_unavailable` と `misses_omitted_why`・例の無い単位は拒まれないが「例で証明できない」印（md:77）。
34. 形の違う欠陥を `patterns` に並べるなら単位を分ける・当たらない場合（書き方の揺れ・1 つの直しで閉じる行・1 つの欠陥の直す site）（md:78）。
35. `total` は受け付けが数えた値に置き換わる・`paths` は 1 本ずつテキストのファイルに当たらなければ拒む・1 か所なら `total: 1`（md:79）。
36. 手順 7 処方は零処方から・零処方の次に決め手を順に当てる・決め手 4 つ（人の前の決定・人の方針・対象の同じ場面・世界の解。コメント・docstring・テストの説明文は (a)(b) に数えない・世界の解の行を先に使い、行の無い問いだけ一次情報を自分で引く）（md:80-81）。
37. 依頼と目的の文が示した解き方は人の前の決定に数えない・世界の解が「定石と違う」と名指せば黙って残さず定石を採るか外れる訳を書く（md:82）。
38. 1 つに決まるなら自分で決めて `prescriptions` に・出どころを添える（MADR の Chosen option の形）・世界の解なら `precedents` にも・世界の解・前の決定・方針・同じ場面で決まる物は人に回さない（md:83）。
39. 人に問うのは 3 つの場合だけ（①先例が割れる ②優先の付け方で変わる ③記録された方針の行とぶつかる）・対象の文とのぶつかりは ③ に当たらず、その文を直す site を処方に（md:84-85）。
40. fork は機構の新設・共有面の拡大で 3 つの場合に当たる物だけ・選択肢ごとに帰結と代償・零処方が落ちる訳・`reason` の末尾に「推し: <選択肢>——<訳>」（md:86）。BASE の能力を減らす処方は失う能力を `reason` に（修正案の narrows と事前審査を通って人に聞く）（md:87）。欠陥の key に修正場所を埋め込まない（md:88）。
41. 手順 8 先行例は直す単位と人へ回す問いの key ごとに 1 行・欄の意味と verdict の 4 語（md:89）。世界の解の行を先に使い `source` は `world:<類の id>`・受け付けが在るかを拒む（md:90）。一次情報は WebSearch・WebFetch・`not_found` は `searched` が要る（md:91）。人へ回す問いは `undecided_because` の頭に印 ①②③・③ は記録された方針の名指しを字のまま写す・本文の中の ③ は名乗りに数えない・書けないなら人に回さず処方に（md:92）。
42. 手順 9 安定キーは「ファイルパス＋シンボル名＋一文要約」・同じ欠陥は同じ字（md:93）。
43. 台帳: 書ける欄は 8 つだけ（md:98）。kind ごとの出どころと要る欄と意味（fork・split・rule・stuck・thrash・premise・unverifiable・awaiting・field。今の `QUESTION_KINDS` の `note` の全部。md:99 と `PROMPT_TABLES`）。
44. status 4 つの要る欄と意味（今の `QUESTION_STATUS_NOTE`）・この回に立てるなら held（md:100）。
45. split と rule は開いた単位を出どころにしない（defer にして構造的理由）（md:101）。
46. awaiting_human の素材ごとに awaiting の問い（md:102）。
47. 問いは阻害要因を消さない（md:103）。
48. 答えと同じ問いは key を答えの `question` の字のまま・違えば `answer_ties`・field の key の頭を素材の名で（md:104）。
49. field・awaiting で人が手元で打てば決まる命令は `reason` に「測り方: `<命令>`」・読み取りだけ・`options` に命令を書かない（md:105）。
50. 台帳の決まりはこの md の節が正本（md:97 の「材料の段が正本」を 1 か所にした。2.6）。
51. `answer_ties` の 4 つの行の形と意味（md:109-114）。
52. `none` は 20 字以上（md:112・114）。
53. 結びを求める答えと求めない答え（md:116）。
54. `to` が無い・defer の単位に作り直しの行を結ぶ・`none` が短いと拒む（md:116）。
55. 結びを確かめるのは判定の受け付けの時だけ・後の再審が単位を下げたら報告に名指される（md:116）。
56. 出力の欄の並び・`out_of_purpose` と `answer_ties` の空の配列・`materials_missing` は欠けが無ければ空・`carried_r1` は空の配列（md:120）。

再審の役（`prompts/rejudge.md`）:

57. この run の判定を考え直すために起きている・判定と材料はファイルに在る（md:20）。
58. まず材料を Read・並んだファイルも Read（md:22）。
59. 読むだけ・道具の名・受け付けが写しと比べる（md:23）。
60. 却下の理由が在れば丸ごと出し直す（md:25-31）。
61. 回す側が今の周に異議を出した・単位と台帳と見立ては材料に在る（md:35-38）。
62. この node が在る訳（md:40-43）。
63. 規律 1: 反論は新しい事実を伴う時だけ・自分で確かめ `new_facts` に・確かめずに採るのも退けるのも禁じる・機械が空同然を拒む（md:47-49）。
64. 規律 2: 往復を数えるのはこの役の外・何回目かは渡らない・回数で返し方は変わらない（md:50-52。第三の目の文は消す。3.6）。
65. 規律 3: 判定を確定する権限は移らない・退けてよい（md:53）。
66. やること 1: 現物で確かめる・コマンドを走らせられないので記録とコードを Read・Grep で照らす・確かめられない事実は「確かめられない:」・採る根拠にしない・1 つも確かめられなければ `退ける` と「足りない:」（md:57）。
67. やること 2: 採る・退ける・一部採る（md:58）。
68. やること 3: 変える単位だけを書き換え、`units` は全部返す（返さない単位は消える）・ラベルを下げない（md:59-61）。
69. やること 4: `reason` に 1 行（md:62）。
70. 入力が足りない時の返し方（`退ける`・単位を変えずに全部・`new_facts` と `reason` の頭に「足りない」）（md:64-67）。
71. 自分の処方が誤っていたと分かったら書く・実例の文（md:69-70）。
72. 人の方針の段（断片 `policy`。md:72-76）。
73. 決められた JSON の形だけを返す（md:77）。

今の出し直しの役の指示（`RESUBMIT_ASK`・`FIELD_RULES`）は、共通の断片 `resubmit` が持つ（4 節。`prompts/rejudge-fix.md` は断片 1 つ）。

## 10 済んだと言える条件（PR ごと。README の 11.2）

- 9.1 の 4 本の筋書きが `archon workflow test` で通り、`archon validate` が警告なしで通る（`tests/layers/test_block_shape.py`）。
- 9.2 の試験が緑（手元は `WORKS_TESTS=fast`。重い段は出荷の CI）。
- 9.3 の本物の単独の run を 2 回回した。
- 審査役が 9.4 の 73 件を英語の md と照らした。

## 11 根拠を書いて自分で決めた事

1. 判定役の材料を指示に直に入れず、値だけの JSON `diagnose-input.json` に書いて Read させる。鍵の意味は md の `## Inputs` が全部持つ。根拠: 憲法の 2（Python は指示の文を持たない）は、材料のファイルを Python が見出しつきの文で描く今の形を許さない。値を指示に直に入れる形（world・素材の観点）は、今の材料のファイルが例の run で 28 KB あり、方針の本文（40000 バイトまで）を足すと README の未確認の「`prompt:` に数十 KB を入れた時の上限」に当たりうる。JSON にしておくと、再審の役がそのまま 1 回目の判定役の材料として読める（port `prior_inputs`）。対象差分を Read させる形は今も同じ。短い節（前の run の行・記録された方針・頭の深さの行・方針の本文）は、plan と同じ共通の断片で指示の中に入れる（14）ので、再審の役には組んだ指示のファイル（出力 `brief`）も渡す。
2. 素材の観点の返答を、`material.json` の欄 `role` の値（`local-review` など）で引いて `diagnose-input.json` の鍵に写す。根拠: 素材の観点の設計書（consistency-bypass・hygiene・local-review・gate-efficacy・provenance・procedure-trace・test-double-fidelity・main-path-observation・external-standards・purpose-review）が、読み方は diagnose が決めると書き、`role` で引く形を前提にしている。`role` は素材の行の形（`lib/materialkit` の族の語）の値で、block を include して呼ぶ名指しではない（憲法の 3 が禁じるのは graph の外でほかの block を呼ぶこと）。表は `src/files.py` の `REPLY_KEYS` 1 つに置く。今判定役に届いていない返答（hygiene の `findings`・procedure-trace の `unmeasured`・external-standards の `rankings`）は足さない（振る舞いを変えない。12 節の 2）。
3. 並行 PR の素材は `materials` の配列に入れず、port `pr_material`（札のオブジェクト）で受ける。根拠: parallel-pr.md の 1.2 は出力 `material` を札のオブジェクトと決め、materials.md の 1.6 は「同じ material.json の形」と書いていて割れている。作り手の出力の形は作り手の設計書が決める（README の 4.1）ので、読み手が合わせる。札を `{"role": "parallel-pr", "materials": {"parallel_pr": 札}}` に包んでから `materialkit.assemble` に渡す。
4. `_carried_r1_accounted`・`_fork_moves_forward` と `judge_output` の `prev_*`・`defer_ledger` の引数は写さない。根拠: 工場は 1 run = 1 周（持ち主の決め carry）で、今の `accept` はいつも空を渡し（`:854-857`）、2 つの規則は一度も働かない。働かない規則は「目的を満たし、全体がより簡潔か」で外す（リポジトリの決まり）。欄 `carried_r1` は型に残し、md は空の配列を返せと言う。
5. 再審の輪に出し直しの役（今の `rejudge-fix`）を置く（最初の版は置かなかったが、統合の設計書の 4.1 の 4 の裁定で戻した）。根拠: spec の block が、1 周目の prep の返りを `resubmit: true` に差し替え、出し直しの役の自分の prep を本当に走らせる筋書き（`resubmit-write.stubs.yaml`）で、dry-run が輪を 1 周しか回さなくても出し直しの役に届く。README の 7.1 の 3 も満たす。keep-essence の 12 の仕組みと review-graph の同じ場面（拒まれたら新しい会話で丸ごと出し直させる）を、今の works のとおり拒まれた欄だけを返させる形で残す。判定役の輪は今も丸ごとの出し直し（今のまま）。
6. 判定役の却下の理由は、今の前の回の 1 件から、輪の却下の全部（古い順）にする。根拠: README の 13 章の決め（prep は place の控えから全部を読み、`with:` で `$LOOP_PREV` の理由を運ばない。resume で輪が 1 周目から回り直しても却下が抜けない）。再審の役は今も全部（`rejects.py`）なので同じ。
7. 記録された方針の方針の文書の行は、port `policy` の写しのパスだけで組み、元の置き場（`alias`）を持たない。根拠: README の 4.2 は始めの記録を block に渡さず、port `policy` は independent-design・structure と同じく写しのパスだけを運ぶ。名指しは行の札が示す写しのパス `<写し>:<行>` で当たる（`policy._hit` は `name` か `alias` のどちらかで当てる）ので、受け付けの照らしは働く。元の置き場で名指した返答だけが当たらなくなる。行の札の元の置き場は plan と同じく `none` と書く（plan.md の 10 節の 5）。
8. `request_origin` と `spec_origin` を port にする。根拠: 依頼のバッチの出どころの名は、今は始めの記録の依頼のファイルの名と入口の印から judge が組んだ（`request_batches`）。block は始めの記録を読まない（README の 4.2）ので、組む所は line（`request_origin`）と spec（`added_origin`。spec.md の 11 節の 4）。
9. 出力 `downgrades` に「再審は判定役の会話を継がない」の 1 行を返す。根拠: この下げは今 `docs/nodes.json:194`（#765 で消した） にだけ宣言されていて、その表は組み込みで消える（README の 9.4）。下げている block が自分の行を出力の欄で返す決め（README の 9.2 の `downgrades.json` の行・parallel-pr.md の 10 節の 8）に合わせないと、宣言が黙って消える。報告の「下げている所」の数に 1 件が足されるかは report と line の設計書の決め（今の報告は `downgrades.json` の 2 件だけを数える）。
10. 止めの語 `works:judge`・`works:material`・`works:request` は今の `lib/judge_accept.py` と同じ名と同じ意味の文で `stopby.declare` する。根拠: 読み手（line・report・chain）が今の語で読む。`stopby.declare` は同じ名を別の意味で足すと落ちるので、字のまま写す。
11. `ok` は `status == "ok"`（判定か再審を受け付けた）。開いた単位が無い判定も `ok: true`・`ready: false` で、止めではない（今の `test_no_open_units_is_not_a_stop`）。`stopped`（素材の観点が諦めた）は `ok: false`。根拠: world の 9.1 の 1 と同じく、単独で呼ぶ人が `outcome_field:` で落ちを知れる。
12. `judgment` の pointer はいつも返し、受けた判定が無ければ空の形を書いて指す。根拠: 今の `verdict` の `_fill` と同じ。読み手（verify・line・report）が null の枝を持たずに済む。ほかの任意の pointer は null（world の 9.1 の 2 と同じ。Archon は pointer の先が空でないかを照らす）。
13. 再審の道の `answer_ties`・`materials`・`out_of_purpose` は null。根拠: 再審は単位だけを考え直し、結び・素材・目的の外の行は 1 回目の物が正（今の line の `judged` も 1 回目の物を持ち続ける）。
14. 前の run の行・記録された方針・頭の深さの行の節は、plan.md が名と本文と口を決めた共通の断片 `prior-failures`・`recorded-policy`・`unknown-asks` を使い、行の英語の札も plan.md の 2.3 の字にそろえる。port の形 `judgment.schema.json`・`prior-failures.schema.json` も plan.md の 1.2 の物を `workflows/.shared/schemas/` に置いて共に使う。根拠: 2 つ以上の block が使う段落と形は `workflows/.shared/` に 1 つ（README の 5.1・13 章）。2 波目で plan と同時に書いたので、名を割らないよう先に書かれた方に合わせた。
15. 頭の深さの段の根拠を port `depth_why` で受ける。根拠: 今の判定役は、種類が決まっていない run で「決まっていない（訳: <控えの why>）」を見ていた（`headdepth.section`）。`row_asks` だけでは訳が落ちる。head-depth の出力 `why` がその字（head-depth.md の 1.2）。
16. 共通の形 `judgment.schema.json`・`prior-failures.schema.json` と断片 `unknown-asks`・`prior-failures` は plan の作業場（7d93fe30）の物を字のまま、断片 `recorded-policy` は r1 の作業場（6271e0bd）の物を字のまま置く（統合の指示。同じ道は同じ中身）。plan の `judgment.schema.json` は `units` の行の `key` だけを必須にし、`prescriptions`（字の配列）と `questions`（object の配列）の型を縛る。verify の block ごとの形との差は 2 つ: 共通の形は `label` を要らない（`judgmark.is_open` は `label` の無い単位を閉じた物と読む。verify は共通の形を読んだ後に `label` が字かを自分で確かめて拒む）・`prescriptions` が字・`questions` が字の配列の判定は共通の形が拒む（verify の形は通す）。diagnose が書く判定（`output_format` が型を保つ）は両方とも通る。試験 `test_judgment_schema.py` が差を名指しで固定する。
17. 入力 `answers` の形のファイルは `answer-rows.schema.json` と呼ぶ（最初の版の設計書の port の欄の名は `answers.schema.json` だった。1.2・1.5 は直した）。根拠: `tests/layers/test_block_shape.py` の「形のファイルの名は pack の中で 1 か所」が、independent-design の `answers.schema.json`（別の形）と重なる名を拒む。中身は port の説明のとおり（行の配列、`question`・`text` が必須）。
18. 判定の受け付けの `_name_hints` と `NUMBER_HINTS` は写さない。根拠: 言い換える相手の文は `_carried_r1_accounted` だけが書き（11 節の 4 で写さない）、この block ではどの拒否の文にも当たらない。働かない規則は外す（リポジトリの決まり）。
19. 再審の `take` は、返答の単位の行に空でない `key` が無ければ、`judgment.json` を書く前に拒む（今は書いた後の `diff_units` で `TypeError` が上がり、`judgment.json` が書かれたまま受け付けが落ちた）。根拠: 出口は `judgment.json` が在れば再審を受けたと読むので、拒んだ返答の判定が残ると受けたことになる。output_format が `key` を必須にしているので、通る返答の振る舞いは変わらない。
20. 筋書きは `standalone`・`gave-up`・`rejudge`・`rejudge-resubmit` の 4 本にする（10 節のとおり）。根拠: AI の node を差し替えて届く道は、判定の道の通り・判定の道の諦め・再審の道の通り・再審の出し直し（4 節）の 4 つ。4 本目に当たる `rejudge-session`（`prior` が null）は AI の node に届かないので 9.1 のとおり試験が見る（`test_rejudge.py` の `test_session_stop_when_there_is_no_first_judgment` と `test_diagnose.py` の `test_no_first_judgment_stops_the_session`）。`gave-up` の差し替えの返答は、ラベルの語が表の外の単位でなく（Archon が差し替えの返答を `output_format` に照らして拒む）、型に合って受け付けだけが拒む返答（開いた単位に `class_query` が無い）にする。ラベルの語の拒みは `test_judge.py` が見る。
21. 再審の `accept_reply` は輪を抜ける時（`done`）に出口 `rejudge-exit.json` を書き、書けなくても落ちない。`finish` は出口が無ければ `collect` で書き直す。根拠: 3.8 の「輪を抜ける時は `collect` が出口を書く」と 5.6 の 4 の両方を満たす。
22. 判定の道の出口は、素材の観点が諦めた時に `status: stopped`・`ok: false`・`stop_reason: works:material`・`reason` は各素材の `reason` を「／」でつないだ字で返す。材料のファイルと `materials.json` は書いてあるので `inputs`・`materials` の pointer は在る（1.2 のとおり）。`intake.json` の `values` は書く（再審の役は使わないが、読み手が止めた訳を引ける）。
23. 共通の断片 `recorded-policy` と `prior-failures` の本文は、今の `policy.RECORDED_HEAD`・`RECORDED_RULE`・`RECORDED_NONE` と `carry.PRIOR_HEAD`・`REDESIGN_HEAD` の文を英語にして足した。`unknown-asks` は plan の作業場の下書きの本文を字のまま写した。根拠: 14 のとおり、先に書かれた物に揃える。plan の PR が別の字で足していれば、main の物に合わせる（12 節の 5）。行の英語の札を組む Python は `src/inputs.py` の `recorded_text` と `unknown_lines`（12 節の 5 のとおり、plan と重なる）。
24. md の「Inputs」は、設計書の 2.3 の順のうち、断片が見出しを持つ物（前の run の行・記録された方針・人の方針・頭の深さ）を箇条の後ろに見出しつきの節として並べる。「前の run の行」の 2 つの節の読み方（直す穴か注意か）は、その段落が入る時だけ md が言う（段落 `prior_notes`・`prior_redesign` を md の側でも使う）。目的の外の所見の決まりは箇条にして、材料の鍵の説明の後に置く。
25. 報告の行（5.7）の字は今の `lib/runreport.py` の `unproven_lines`・`rejudge_changes`・`rejudge_lines` の頭と下げた単位の行をそのまま使い、再審が直す単位にした単位の行と「再審されずに残った異議」は書かない（line が組む）。
26. `COUNT_BUDGET`（数える問いを走らせる量の上限。300 回か 900 秒）は今の判定の受け付けが持つ数のまま写す。根拠: 振る舞いを変えない写しで、新しい期限ではない（同じ返答を出し直し続ける輪の網）。
27. 素材の欄から `gate_efficacy` を外す。この block が読む欄は `files.MATERIALS`（`lib/materialkit.MATERIALS` の 15 欄から `gate_efficacy` を除いた 14 欄）で、`materials.json`・材料のファイルの `materials` もその 14 欄。材料のファイルの鍵 `gate_arms` も無く、指示 md も `gate_arms`・`gate_efficacy` を言わない。受け付けの問いの出どころ（素材名）の域も 14 欄。gate-efficacy の block の素材が `materials` の port に来ても読まない。根拠: 持ち主の決め 2026-10-19 「重い試験は全部まとめてやるし、なんならＣＩに任せて先に進めたい」「その診断の…種類から外せばいいのでは」。`lib/materialkit.py` は変えない（gate-efficacy の block は単独で回り、素材の欄の照らしは全体の表を使う）。外した素材を回す graph を持つ時は、graph が `materials` に渡さない。
28. 材料のファイルに対象差分のパス `diff_file`（place の `diff.patch` の絶対パス）を置き、素材の `base_determination` は根を持つ素材の doc が無ければ見方の根で `found` に埋める（5.1 の 5 と 7）。根拠: 今の再審は `diff.patch` を材料として直に渡し（`lib/judge_accept.py` の `REJUDGE_MATERIALS`）、新の再審は 1 回目の材料のファイルを読むので、パスが無いと差分に届かない。`base_determination` は今の素材の束ねが見方で埋めていて、`not_run` のままだと `gatemarks.UNMEASURED` に入り、依頼の答えの結びの照らしが甘くなる。どちらも今の能力を残す直し（審査の指摘）。
29. 依頼を宣言した run（port `request` が字のままの空の配列 `[]` でない）で行が空なら、`works:request` で止める。根拠: 今の判定の入口は、始めの記録が依頼のファイルを名指した run では行が空でも `check_request` に通し、`minItems` 1 で拒んでいた（`lib/judge_accept.py` の `intake`）。block は始めの記録を読まないので、「宣言した」を port の値が `[]` の字でないことで見る（審査の指摘で落ちていたのを戻した）。
30. 世界の解の行（`world_rows`）と素材の要素（`materials` の pointer）が読めない時は、今の「無い」として進む形をやめ、「入力 <名>: <訳>」で `failed`・`works:judge` に止める（振る舞いの変更）。根拠: 読めない入力を「無い」と読むと、判定役は世界の解や素材の観点が走らなかった run と区別できず、黙って材料の欠けた判定を出す。止めて訳を出口に残す方が、承認ノードと報告で人が気づける。

## 12 未確認

1. 出し直しの役（`-fix`）を持つ block の筋書き: dry-run は輪を 1 周しか回さないので、そのままでは `-fix` の node に届かない。spec の `resubmit-*.stubs.yaml` が決めた形（1 周目の prep の返りを `resubmit: true` に差し替え、出し直しの役の自分の prep は本物を走らせる）を、この block の `rejudge-resubmit.stubs.yaml` も取った（4 節）。test-gate（`ci-fix`）・plan（`plan-writer-fix`）が同じ形で届くかは各 block の設計書の決め。
2. 判定役に届いていない返答（hygiene の `findings`・procedure-trace の `unmeasured`・external-standards の `rankings`）を届けるか。今と同じく届けない（素材の `detail` と各 block の `report` には載る）。届けるのは振る舞いの変更なので、この作り直しの外。
3. `lib/gatemarks.py` の `_tie_row_problems`・`_squeeze`・`_fix_duty` と `lib/outpurpose.py` の `_walk` は内向きの名（`_` で始まる）だが、今の `judge_accept` と同じく呼ぶ。組み込みで公開の名にするか。あわせて、KEEP の `querytest`・`outpurpose`・`gatemarks` は DELETE の `lib/marks.py`（README の 9.1）の `split`・`path_of` に頼っている。組み込みで `marks` を消すなら、この 3 つの読み口の作り替えが要る。
4. 再審の後の単位は `REJUDGE_UNIT_FIELDS` だけを持ち、class_query を落とす（今の `rejudge_take` のまま。修正の数え直し〔keep-essence の 7〕は再審の後の単位の class_query を読めない）。今の振る舞いを変えないので写すが、意図した形かは記録が無い（#76）。
5. 記録された方針の行と頭の深さの行を英語の札で組む Python（plan.md の 2.3 の札）は、plan と diagnose の 2 つの block が同じ物を持つことになる。2 つ以上の block が使うので `lib/` の新しい 1 モジュールが正しい置き場（憲法の 4）。先に入る PR がそのモジュールを足していればこの PR はそれを import し、足していなければ `src/inputs.py` に写して組み込みで寄せる。plan.md は 2 波目で同時に書かれた下書きで、断片の本文・口の名が main に入るまでに変われば、main の物に合わせる。
6. `materials` の配列を judge のまとめの `with:` で 11 本の pointer から組めるか（`with:` の値の中で `$<id>.output.material` を JSON の配列に並べる書き方。materials.md の 1.6 が決めたが、include の `with:` が JSON の字で運ぶ値の組み方は確かめていない）。
