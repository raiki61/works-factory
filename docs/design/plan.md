# block の設計書: plan（修正案）

- 何の話か: 判定が切った直す単位を、直す前に設計として固める観点「修正案」を、単独で呼べる block `workflows/plan/` にする設計。修正案の役が項目ごとに書いてよい範囲・受け入れテスト・定石と構造の目の行への答えを書き、機械が受け付けで照らし、波及の一覧（変える名の呼び出し元と試験）を機械が出す。承認済みの案の一部の項目を直す「案の直し」も同じ block の形 replan で書く。型は [README.md](README.md)、手本は [world.md](world.md)。
- 決めたこと: 今の `workflows/plan/` の 8 つの node（round・ripple-units・plan-loop〔plan-prep・plan-writer・plan-writer-fix・plan-accept〕・ripple-items・plan-reads・plan）を、頂の 5 つ（intake・ripple-units・plan-loop・ripple-items・finish）の block にする。輪の本体は prep 2 つ・AI の役 2 つ・受け付け 1 つ。AI の node は 2 つ（`plan-writer`・`plan-writer-fix`）。事前審査との往復の記録と止めは line が持ち、この block は前の周を port `prior` で受けて 1 周分の案を作って返す（README の 1.3 の形の直し 6）。始めの記録は読まず、要る値は 22 の port で受ける。指示は英語の md 2 本（`prompts/plan-writer.md`・`prompts/plan-writer-fix.md`）と、2 つ以上の block が使う共通の断片（今在る `rejected`、1 波目の PR が足す `policy`・`resubmit`・`handoff`、取り置いた `unknown-asks`、この設計書で名を決める `recorded-policy`・`concept-map`・`prior-failures`）に置き、`lib/planfile.py`・`lib/planblk.py`・`workflows/plan/commands/fix-plan.md` と KEEP の lib の文の定数に散っていた指示の文を md に 1 回だけ書く。単位ごとの深さ（今の返りの `depth`）は line へ移す。振る舞いは変えない（変えた所は 10 節に名指す）。
- 読む人と使い方: この block を作る実装者（1〜5 節の名と順をそのまま作る）と、新旧の指示を比べる審査役（2.6・3.6・9.3）。

この文書の語は README の頭の物を使う（block・graph・port・place・prep・accept・pointer・Archon、`loop_group` などの Archon の YAML の鍵、form の書き方）。keep-essence の番号は README の 10 章。ほかに:

- line: 工場のメイングラフ（README の 8.7）。block を並べ、承認ノード・計画の往復・無人の方針を持つ graph で、この block を include する。
- 判定: 前段の根本の診断が返す、直す単位と問いの台帳（port `judgment`）。
- 事前審査: 修正案に別の目が当てる審査（別の block）。指摘の重さは block（直しへ進めない穴）と suggest（提案）の 2 語で、この文書で「block 5 件」のように数える block はこの重さの語。単位の label の block も同じ字。
- 承認ノード: 人の答えを待って止まる node（line が持つ）。
- 世界の解の行と定石: 世界の解の block が返す行（依頼の行ごとの問題の類・世の中の実務家の解き方〔定石〕・出典の抜き書き・依頼の解き方との比べ）。修正案は答えの要る行ごとに、定石に従うか従わない訳を書く。
- 構造の目の行: 構造の目の block が単位ごとに返す行（直しが設計の考えを知る場所を増やすか〔汚れる・汚れない〕と避け方）。汚れる行の単位を持つ項目は、避け方に従うか訳を書く。
- 頭の深さ: 依頼の行ごとに、何が分かっていないか（未知の種類 無し・原因・形・範囲）を引用つきで決めた控え。
- 始めの記録: run の始めに line が書く記録（言語・方針・版など）。block は読まない。
- 訳: 理由のこと（翻訳でない）。
- 作り直し・組み込み: 新しい block を `blocks/` に並べて作る段と、line を新しい block に切り替えて古いサブグラフを消す段（README の 11 章）。1 波目・2 波目は作り直しの中で同時に作る PR の群。
- 周: line の計画の往復の 1 回と、案の直しの 1 回。周ごとに、この block を 1 回 include する。番号 `round` は、前の周の番号 + 1（前の周が無ければ 1）。
- 形: `plan`（判定の単位から案の全体を書く）と `replan`（承認済みの案の、裁定が名指した項目だけを直す）。port `ruling` が空でなければ `replan`。
- 修正案の役（plan-writer）: 案を書く AI の役。読むだけ（Read・Grep・Glob・WebSearch・WebFetch）。
- 出し直しの役（plan-writer-fix）: 受け付けに拒まれた後、修正案の役の会話の続きで、拒まれた所だけを返す AI の役（#588・#571）。機械が前の答えの控え `candidate-plan.json` と合わせてから全体を照らす。
- 直す義務の単位: 開いた単位（label が block か、suggest で disposition が do-now）から、人の答え待ちの問い（fork・escalate）の出どころと depends を除き、依頼の answers・無人の run が採った推しが答えた問いの出どころと depends を戻した物（`lib/gatemarks.py:1302` の `duty`）。
- 往復の記録: 事前審査の往復ごとの行（`lib/converge.py` の控えの形 `{round, passes, outcome, open, plan}`）。line が持ち、`prior` の欄 `record` で渡す。
- 例の run: 本物の run `df5e111f-ea97-409b-8066-2245d32746ab`（対象はこの工場のリポジトリ自身。置き場 `<run の置き場>/plan/r2/`。2 周目で、前の周の案と事前審査の block 5 件・答えの要る suggest 4 件を受けた）。出し直しは本物の run `821e6fab-9ca4-404e-9dac-51132a8881c6` の `plan/r2/brief-2.md`（対象の名は伏せる）。形 replan は、記録の在る run のどれでも走っていない（2026-10-19 に `plan/r*/round.json` の `mode` を探した）。

## 1 block の全体

### 1.1 役

判定の直す義務の単位を全部、項目のどれかにちょうど 1 度入れた修正案を、直す前に書かせる。項目ごとに、何をどう変えるか・新しく生まれる物と消す物のファイルの行（住処と退けた置き場つき）・足さずに閉じる形を先に考えた結果・今ある能力を狭める物とその決め手・直し方の道と受け入れテスト・書き換えるテスト・書いてよいパスと触らない物・項目の間の依存・構造の目の行と世界の解の行と判定の処方への答えを書かせる。機械が受け付けで全部を照らし、拒否は理由を全部 1 回で返す。通った案を、修正が読む欄（plan-fields）と、事前審査が読む役の返答（p2.fix_plan）に分けて置き、項目ごとの波及の一覧を作る。2 周目からは前の周の事前審査の block に答えさせ、閉じた項目は機械が前の周の行のまま差し込む。形 replan では、裁定が名指した項目だけを直させ、約束の欄が変わったかを事実として残す。どの段が落ちても、出口は落ちずに形を守った返りを返す。

### 1.2 port

入力（YAML の `inputs:`。22 個。どれも run の記録を読まない）:

- `judgment`: `json(shared:judgment.schema.json): 受け付けた判定（欄 units・questions・framing・one_shot・one_shot_closes・precedents を読む）。pointer・パス・値のどれか。空の字は判定が無い（形 plan では役を起こさない。形 replan では処方とライブラリの文書と項目の brief だけに使う）`。既定 `""`。
- `units`: `json(unit-catalog.schema.json): 直しの単位の目録の配列 [{id, paths, summary}]。空の配列は目録が無い`。既定 `[]`。
- `answer_ties`: `file: 依頼の答えを判定の問いと単位に結んだ行のファイル（answer-ties.json の形）。空は結びが無い（答えを字の一致だけで数える）`。既定 `""`。
- `materials`: `file: 判定の素材の状態のファイル（素材の名 → {status, …}）。空は素材の状態が無い`。既定 `""`。
- `answers`: `json(request-answers.schema.json): 依頼の answers の行の配列 [{question, text, …}]。空の配列は答えが無い`。既定 `[]`。
- `takes_push`: `flag: 判定が保留にした分かれ道の問いの推しを、答えとして数えるか（無人の run の方針。直す義務の数えに効く）`。既定 `false`。
- `verify`: `file: 判定の単位の裏取りの申し送り（{units: [...], synergy: {...}}）。空は申し送りが無い`。既定 `""`。
- `excluded`: `file: 並行 PR と重なるので外した範囲のファイル。空は外した範囲が無い`。既定 `""`。
- `depth_record`: `file: run の頭の深さの控え（行ごとの未知の種類と引用。lib/headdepth.py の read_file が読む形）。空は控えが無い`。既定 `""`。
- `decisions`: `file: 決定記録の突合の返答（reply.settled が決着済みの論点）。空は突合が無い`。既定 `""`。
- `world_rows`: `file: 世界の解の行の JSON Lines（lib/worldmark.py の行の形）。空は行が無い`。既定 `""`。
- `structure`: `file: 構造の目の控え（{status, reason, design_file, skipped, …}。lib/structmark.py が読む形）。空は構造の目の行が無い`。既定 `""`。
- `spec`: `file: 固めた仕様（requirements・acceptance を持つ JSON。JSON でなければ字のまま貼る）。空は仕様が無い`。既定 `""`。
- `policy`: `file: 人の方針の文書の固めた写し。空は方針の文書が無い`。既定 `""`。
- `prior_failures`: `json(shared:prior-failures.schema.json): 前の run で最後まで通らなかった物の行の配列 [{where, text}]。空の配列は無い`。既定 `[]`。
- `prior`: `json(plan-prior.schema.json): 前の周（形 plan では直前の計画の周と、それへの事前審査。形 replan では直す元の承認済みの案の周）。pointer・パス・値のどれか。空の字は前の周が無い（1 周目）`。既定 `""`。
- `ruling`: `json(replan-items.schema.json): 案の直しで直す項目の番号（1 始まり。整数か数字の字）の配列。空の配列は案の直しでない（形 plan）`。既定 `[]`。
- `conflicts`: `file: 修正の段の申し出と裁定の行のファイル（{items: [...]}）。形 replan だけが読む。空は行が無い`。既定 `""`。
- `base`: `text: 修正前の HEAD の版（受け入れテストの定義と修正前のテストの中身を引く版）。空は HEAD`。既定 `""`。
- `review_rev`: `text: 役が読む版。空は base、それも空なら HEAD`。既定 `""`。
- `diff_base`: `text: 材料の BASE（入口の差分の根）。空は base、それも空なら読む版`。既定 `""`。
- `routes`: `choice(auto|spec): 行の route の決め方。auto は今の指示のまま。spec は固めた仕様（入力 spec）の「TDD で直す所」が名指す行だけを tdd にし、ほかを direct にする`。既定 `auto`。spec の時だけ、修正案の役の指示に段落 `routes_spec` が出る（[spec-driven.md](spec-driven.md) の 7 章の 2）。知らない語は読めない入力として指示に名指し、auto で読む。
- `lang`: `text: 人に見せる欄（approach・shrink_first・各 why・why_not・no_narrow・undecided_because・world・deviation・narrows の what・recommend の note と why・block_answers の how・handoff）の言語。空は依頼の言語`。既定 `""`。

形のファイル:

- `workflows/.shared/schemas/judgment.schema.json`（新しく足す。判定を読む block は plan のほかに plan-review・verify・fix が在る）: `{"type": "object", "required": ["units"], "properties": {"units": {"type": "array", "items": {"type": "object", "required": ["key"], "properties": {"key": {"type": "string", "minLength": 1}, "label": {"type": "string"}, "disposition": {"type": "string"}, "prescriptions": {"type": "array", "items": {"type": "string"}}}}}, "questions": {"type": "array", "items": {"type": "object"}}}}`。作る時に同じ名の形が `.shared/schemas/` に在れば、それを使い、足さない。
- `workflows/plan/schemas/unit-catalog.schema.json`: structure の block の `schemas/units.schema.json`（structure.md の 1.5）と同じ形。作った時の決め: structure の側のファイルと YAML を直さず（block は自分の名のファイルしか消さない）、名を替えて plan の側に置いた。`.shared/schemas/` へ寄せるのは組み込みの時（10 節の 6）。
- `workflows/.shared/schemas/prior-failures.schema.json`（新しく足す。読み手は plan と diagnose）: `{"type": "array", "items": {"type": "object", "required": ["where", "text"], "properties": {"where": {"type": "string"}, "text": {"type": "string"}}}}`。同じ名の形が在れば使う。
- `workflows/plan/schemas/request-answers.schema.json`: `{"type": "array", "items": {"type": "object"}}`（行の欄は `policy.recorded` と `gatemarks.ledger` が読む物だけを使い、ここでは縛らない。今と同じ）。
- `workflows/plan/schemas/replan-items.schema.json`: `{"type": "array", "items": {"type": ["integer", "string"]}}`（番号の照らしは `planmarks.handed` のまま）。
- `workflows/plan/schemas/plan-prior.schema.json`:

```json
{
  "type": "object",
  "required": ["round", "reply", "fields"],
  "properties": {
    "round": {"type": "integer", "minimum": 1},
    "reply": {"type": ["object", "string"]},
    "fields": {"type": ["object", "string"]},
    "fix_plan": {"type": ["object", "string", "null"]},
    "ripple": {"type": ["object", "string", "null"]},
    "review": {"type": ["object", "string", "null"]},
    "record": {"type": ["object", "null"]},
    "handoffs": {"type": "array", "items": {"type": "object", "required": ["round"],
                 "properties": {"round": {"type": "integer", "minimum": 1}, "handoff": {"type": ["object", "string", "null"]}}}}
  }
}
```

`prior` の欄の意味（`reply`・`fields`・`fix_plan`・`ripple`・`review`・`handoffs[].handoff` は、どれも pointer か、パスの字か、中身の値そのもの〔`archon_artifact` の `type` を持たない object〕）:

- `round`: 前の周の番号。この周の番号は `round + 1`。
- `reply`: 前の周の受け付けた案の全体（この block の出力 `reply` の先。`plan` の欄を持つ）。形 replan では直す元の承認済みの案。
- `fields`: 前の周の修正案の項目の欄（出力 `plan` の先。`{round, fields, amended?}`）。
- `fix_plan`: 前の周の修正案の役の返答（出力 `fix_plan` の先）。null は無い。
- `ripple`: 前の周の項目ごとの波及の一覧（出力 `ripple` の先）。null は無い。
- `review`: 前の周の案への事前審査の返答。null は受けていない（形 replan では読まない）。
- `record`: 往復の記録（`converge.read` の形）。今の `planfile.converge_record(plan_dir)` がこの周を開く時に組む物と同じ中身（受けた事前審査ごとの `converge.add_pass` の行と、最後の受け付けた案の `converge.plan_rows`）。null は記録が無い（1 往復目の前と形 replan）。
- `handoffs`: 前の周までの全部の受け付けた周の引き継ぎのメモ（古い順。`handoff` が null の周はメモが無い）。

出力（`returns: finish`、`outcome_field: ok`）:

- `ok`: boolean。`status` が `ok` か（今の `ready`）。
- `status`: `ok`（受け付けを通った案が在る）・`nothing_owed`（直す義務の単位が 0 件で役を起こさなかった。諦めでない）・`held`（役を起こさなかった: 判定・前の周・世界の解の行が読めない、行き止まりの単位が在る、直す元の案が無い、ruling の番号が案に無い）・`gave_up`（役が回数を使い切った: 受け付けが網の回まで拒み続けた）・`failed`（機械の故障と node の誤り: 拒否の控えが扱えない〔rolekit が読めない・書けない〕、受けた案の控えを置けなかった〔書き込みが失敗し続ける。`round.json` に `halt: true` と訳を残す〕、node の中の誤り、指示が組めない、輪が回らなかった）。`gave_up` は役の側の使い切りだけで、機械の側の書き込みの失敗は `failed`。
- `reason`: 日本語の 1 行。`ok` でない訳（今の `why_not_ready`）。`ok` なら空。
- `mode`: `plan` か `replan`。`round`: この周の番号。
- `owed`: 直す義務の単位の key を判定の順に（今の `planfile.owed_order`。line が単位ごとの深さを決める）。形 replan と判定の無い周は空。
- `plan`: pointer（`r<k>/plan-fields.json`）。いつも在って空でない（案が無ければ `{round, fields: []}`）。
- `fix_plan`: pointer（`r<k>/p2.fix_plan.json`）か null。`reply`: pointer（`r<k>/reply.json`）か null。`handoff`: pointer（`r<k>/handoff.json`）か null。`replan`: pointer（`r<k>/replan.json`。形 replan で受けた時）か null。
- `ripple`: pointer（`r<k>/ripple.json`）。いつも在って空でない（案が無ければ `{items: [], error: <訳>}`）。
- `rejects`: この周の受け付けの拒否の行 `[{at, reason, kind?}]`（`rolekit.reject_rows`）。
- `gave_up`: 形 replan で役が諦めた時の項目ごとの行 `[{item, why, ruling}]`。ほかは null。
- `report`: 報告の節「修正案」の日本語の行の配列（4 節の `finish.py` の報告の行）。

`output_format` の nullable は `type: [object, "null"]` で書き、`anyOf` を使わない（今の `fix_plan`・`gave_up` の `anyOf` を替える）。

今との違い: 今は始めの記録の pointer `start` から `policy_md`・`thickness`・`test_cmd`・`tdd_suite`・`base_rev`・`review_rev`・`input.base.rev`・`lang`・`answers`・無人の印を読み（`plan_prep.py:40`・`planfile.read_judgment`）、置き場を `$ARTIFACTS_DIR/plan/` に決め打ち、周のフォルダ `plan/r<k>/` を数えて周の番号と前の周を決め（`planfile.next_round`・`latest`）、受けた事前審査を周のフォルダに写して往復の記録を組み直していた（`planfile.open_round`・`converge_record`）。新しい形では、始めの記録の値は port に、前の周と往復の記録は `prior` に替わり、周の番号は `prior.round + 1` で決まる。返りの `depth`（単位ごとの深さ）と `nothing_owed`・`ready` は、`owed`（line が深さを決める元）と `status` に替わる。

### 1.3 node の並び（`workflows/plan/works-factory-plan.yaml`）

1. `intake`（script `intake.py`）: 全部の port を読み、周を開く（4 節）。返り `{go, mode, round, reason}`（4 つとも required。`mode` は `plan|replan` の enum、`round` は 1 以上の整数）。落ちない（`ports.run`。誤りは `go: false`・`status` の元になる訳を `round.json` に残す）。
2. `ripple-units`（script `ripple_units.py`。`depends_on: [intake]`・`when: "$intake.output.go == true && $intake.output.mode == 'plan'"`）: 案の前の波及の一覧 `ripple-units.json` を書く。返り `{ok}`。
3. `plan-loop`（`loop_group`。`depends_on: [intake, ripple-units]`・`trigger_rule: none_failed_min_one_success`・`when: "$intake.output.go == true"`・`max_iterations: 20`〔`rolekit.NET_AFTER` と同じ数。試験が突き合わせる〕・`fresh_context: false`・`until_bash: 'done=$plan-accept.output.done; test "$done" = true'`）。本体:
   - `plan-prep`（script `plan_prep.py`。`with: {prev: "$LOOP_PREV.plan-accept.output.ok"}`）: 役を起こす前の作業ツリーの姿を `tree.json` に置き直し、出し直しかを決め、出し直しでなければ修正案の役の指示を組む。返り `{prompt, resubmit}`（`prompt` は字。出し直しの回は空の字）。
   - `plan-writer`（AI。`prompt: "$plan-prep.output.prompt"`・`depends_on: [plan-prep]`・`when: "$plan-prep.output.resubmit != true"`。鍵は錨 `&writer_launch`: `model: '@wf-plan-writer'`・`allowed_tools: [Read, Grep, Glob, WebSearch, WebFetch]`・`settingSources: [user]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`mutates_checkout: false`・`idle_timeout: 1728000000`・`retry: {max_attempts: 2, on_error: all}`。`output_format` は今の `&plan_reply` を 1 字も変えずに写す〔`workflows/plan/works-factory-plan.yaml:146-478`〕）。
   - `plan-fix-prep`（script `fix_prep.py`。`depends_on: [plan-prep, plan-writer]`・`trigger_rule: none_failed_min_one_success`・`when: "$plan-prep.output.resubmit == true"`）: 出し直しの役の指示を組む。返り `{prompt}`（`minLength: 1`）。
   - `plan-writer-fix`（AI。`prompt: "$plan-fix-prep.output.prompt"`・`depends_on: [plan-prep, plan-fix-prep]`・`when: "$plan-prep.output.resubmit == true"`・`<<: *writer_launch`。`output_format` は修正案の役と同じ `*plan_reply`（#832。型が違うと会話の続きの最初の要求でキャッシュが効かない）。型の根（一番外の object）は `required: []` で、根の要る欄 `src/files.py` の `REQUIRED` は受け付けが `rolekit.resubmitted` で確かめ、欠ければ拒む。出し直しの役だけが書く `whole_plan: {type: boolean}` も `&plan_reply` に在り、1 回目の答えに在れば受け付けが拒む）。
   - `plan-accept`（script `plan_accept.py`。`depends_on: [plan-writer, plan-writer-fix]`・`trigger_rule: none_failed_min_one_success`・`with: {reply: {from: "$plan-writer.output", if_skipped: null}, fix_reply: {from: "$plan-writer-fix.output", if_skipped: null}}`）: 返り `{ok, done, give_up, reason, attempt}`（5 つとも required）。
4. `ripple-items`（script `ripple_items.py`。`depends_on: [intake, plan-loop]`・`trigger_rule: all_done`）: 受け付けた案の項目ごとの波及の一覧 `ripple.json` を書く。案が無い周も `{items: [], error: <訳>}` を書く。返り `{ok}`。
5. `finish`（script `finish.py`。`depends_on: [intake, ripple-items]`・`trigger_rule: all_done`）: 出力を組む（4 節）。落ちない。

輪の本体の層は `plan-prep` → `plan-writer` → `plan-fix-prep` → `plan-writer-fix` → `plan-accept` で、どの層も node 1 つ（`fresh_context: false` の輪で、続きの役の直前に 2 つ以上の node の層を置かない）。出し直しの役は、前の回に修正案の役が起きた会話の続きで起きる（今の `plan-writer-fix` と同じ。#588）。`plan-fix-prep` は役に依るので `depends_on: [plan-prep, plan-writer]` と `trigger_rule: none_failed_min_one_success` を持つ。

`with:` に `$LOOP_PREV` を書くのは `plan-prep` の `prev`（前の回の受け付けの `ok` の真偽）だけ。却下の文は運ばず、prep が place の却下の控えから読む（README の 13 章）。`prev` が空の回（輪の 1 周目と、resume で輪が 1 周目から回り直した回）は出し直しにせず、修正案の役を全部の材料で起こし、前の回までの却下の全部を `{shared:rejected}` で貼る（今の `rolekit.resubmitting` と `REJECT_LINE` の振る舞い）。

script の名は `lib/` のモジュールの名と重ねない（README の 7.1 の 9）。`intake`・`ripple_units`・`plan_prep`・`fix_prep`・`plan_accept`・`ripple_items`・`finish` はどれも `lib/` に無い。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`。line の往復の輪から include された時は、輪の回をまたいで同じ `$ARTIFACTS_DIR/<include の id>/`）の下に書く。周ごとのファイルは周のフォルダ `r<k>/`（k は `round`）に置き、前の周のファイル（`prior` の pointer の先）を消さない。

- place の直下: `current-round.json`（`{round}`。intake が書き、後ろの script が今の周のフォルダを引く）・`plan-writer-prompt-<n>.md`・`plan-writer-fix-prompt-<n>.md`（`prompt.emit`。`n` は `prompt.round_of` で、周をまたいで数え続ける）・`libdocs/` と `libdocs.json`（ライブラリの文書の控え。今の `plan/libdocs/`）。
- `r<k>/`: `intake.json`（読んだ port の値と、値で受けた物の写しのパス）・`round.json`（`{round, mode, go, why, items}`）・`slots.json`（案に入れてよい単位の key の並び）・`judgment.json`（`judgment` を値で受けた時だけの写し）・`prior-reply.json`・`prior-fields.json`・`prior-fix-plan.json`・`prior-ripple.json`・`prior-review.json`（`prior` の欄を値で受けた時だけの写し）・`prior-failures-in.json`（`carry.PRIOR_IN_FILE`）・`ripple-units.json`・`tree.json`・`rejects-plan.json`・`candidate-plan.json`・`reply.json`・`p2.fix_plan.json`・`plan-fields.json`・`handoff.json`（`handoff.path_of` の名）・`replan.json`（`replan.TRIP_FILE`）・`replan-gave-up.json`・`item-brief-<no>.md`・`ripple.json`・`trace.jsonl`（`planmarks.append_trace`）・`prompt-error.json`（指示が組めなかった node と訳）・`finish-error.txt`（出口の中の誤りの訳）。

名は `src/steps.py` だけが持つ（`p2.fix_plan.json`・`plan-fields.json`・`trace.jsonl`・`handoff.json`・`replan.json` は今の lib の字と同じで、`planmarks.FIELDS_FILE`・`handoff.path_of`・`replan.TRIP_FILE` が書く物はその口を通す）。intake は、今の周のフォルダが既に在れば（同じ周を開き直した時）、その中の上の名のファイルだけを名で引いて消す。place の直下の指示のファイルと、ほかの周のフォルダは消さない（往復の輪の回をまたいで place が同じなので、前の周の指示の記録と `prior` の先を残す。10 節の 3）。

### 1.5 コードの置き場

- `workflows/plan/src/steps.py`: ファイルの名・周を開く（今の `planfile.read_round`・`open_round` の周の部分・`round_inputs`）・直す義務と案に入れてよい単位（`is_open`・`_owed_units`・`slots`・`plan_slots`・`held_why`・`stuck_reason`〔どれも `lib/judgmark.py` の名の受け直し。下の項〕・`_shut`・`not_allowed`・`named`・`fix_plan_covers_units`・`owed_order`・`round_slots`）・判定の処方（`prescriptions`）・入れ子の値の解き（`nested_file(v)`: pointer の object は `ports.file(json.dumps(v))`、字は `ports.file(v)`、ほかの値は周のフォルダに写しを書いてそのパス）・出口（`collect` の受けた案の有無・`note_gave_up`・`why_not_ready`・`placeholders`・`returned`・`nothing_owed`）。`planblk` の修正案の役の部分のうち受け付けと出口の文と名（`NO_NARROW_REJECT`・`RECOMMEND_REJECT`・`NOT_OWED_REJECT`・`ANSWERS_REJECT`・`CLOSED_REJECT`・`READONLY_MOVED`・`NO_TREE`・`PLAN_GAVE_UP_WHY`・`unit_name`）と、`planfile` の `COVERS_REJECT`・`MALFORMED_REJECT`・`REPLAN_REJECT`（`lib/replan.py` と同じ字。案の直しの拒否の頭）・`NO_PLAN`・`NO_ROWS`・`WHOLE_PLAN`・`ROLE = "plan"`・`BASE_TESTS_UNREAD_OP` もここに写す。
- `workflows/plan/src/take.py`: 受け付け（今の `planfile.take_plan`・`take_replan`・`take.plan_errors`・`_replaced`・`revised_fields`・`conflict_rows`・`ruling_text`・`_save`・`moved`・`snap_tree`・`base_test_texts`・`exists_at`・`merge_plan_items`・`merge_resubmit`・`merge_replan_resubmit`）。今の `marks.split`（README の 9.1 で消える部品）は使わず、返答から欄 `whole_plan` と `handoff` を外す小さな関数を置く（中身は「鍵が在れば pop して `{鍵: 値}` を返す」で、今の `marks.split` の返りと同じ形）。
- `workflows/plan/src/brief.py`: 修正案の役の md に入れる値と段落の真偽を組む（2.3 の 1〜29 の値と真偽の全部）。今の `planfile.write_brief`・`units_section`・`prescription_section`・`repo_line`・`replan_section`・`item_brief`・`_prior_section`・`prior_section`、`planblk.verify_part`・`_verify_row`・`_relation_label`、`converge.revise_section`・`_face_text`・`_owed_suggest_text`、`structmark.plan_section`・`_state_rows`・`_bullets`・`_row_line`、`worldmark.section`・`_mark`・`_versus`、`headdepth.section`・`_row`、`concepthome.section`、`policy._section`、`carry.prior_section`、`handoff.section`、`ripple.units_section`・`section`・`item_text`・`_names_text` のうち、材料の行を組む部分だけを写す。決まった文（見出し・頼み・決まり）は持たず md に置く。材料の中で項目ごとに繰り返す短い札は英語にして Python に残す（README の 5.3。札の英語は 2.3 の終わりの札の一覧）。`converge.held`・`owed_faces`・`planned_units` など文を持たない読み口は import して使う。
- 直す義務と周が役を起こすかの決め（`LEDGER`・`NOTHING_OWED`・`PLAN_STUCK`・`STUCK_WHY`・`is_open`・`with_ledger`・`owed_units`・`units_of`・`slots`・`plan_slots`・`plan_stuck_reason`・`held_why`）は plan と line（node `owed`）が共に引くので、写さず `lib/judgmark.py` に置いた（統合の設計書の持ち主の決め。`converge` は `gatemarks` を import しない決まりで、`gatemarks.duty` を呼ぶ決めは置けない）。`steps.py` は名を受け直し、`with_ledger(ctx, doc)` だけが port の値を渡す薄い包み。line の `src/rounds.py` の写しは組み込みで消して同じ名を import する。
- `workflows/plan/src/ripple.py`: 今の `lib/ripple.py` の写し（README の 9.2 の MOVE）。`HEAD`・`UNITS_HEAD`・`SCOPE_ASK`・`COMMON_NOTE`・`ERROR_NOTE` の文は持たず md に置き、`units_section`・`section` は材料の行（単位ごと・項目ごとの行、項目どうしの重なりの行、誤りの訳）を返す関数にする。`REMOVED_MARK` は項目ごとに繰り返す札なので英語にして残す。
- `workflows/plan/schemas/`: 1.2 の 3 つ。
- 使う `lib/`（どれも README の 9.3 の KEEP。変えずに import する）: `accept`（`tree_state`・`tree_moved`・`status_keys`・`TREE_KEYS`）・`carry`（`place_prior`・`is_redesign`・`PRIOR_IN_FILE`）・`concepthome`（`tracked_names`・`pick_maps`・`MAX_MAPS`・`MAP_NAME`）・`conflict`（`replan_rows`）・`converge`（`add_pass` を除く、文を持たない読み口: `held`・`owed_faces`・`filled_units`・`splice`・`answer_gaps`・`fixed_unchanged`・`split`・`plan_keys`・`planned_units`・`plan_rows`・`PLAN_MARKS`・`ANSWERS`・`RESOLVED`・`DROPPED_OP`・`FACE_KEYS`・`REACH`・`CLOSED`・`HELD`）・`gatemarks`（`ledger_files`・`duty`・`narrow_gaps`・`recommend_gaps`・`split`・`joined`）・`handoff`（`FIELD`・`save`・`path_of`・`unreadable`）・`headdepth`（`read_file`・`NONE`・`CAUSE`・`SHAPE`・`SCOPE`・`NO_RECORD`・`STANDARD`・`record`）・`impact`（`is_test`）・`jsonfile`・`libdocs`（`unit_files`・`section`）・`oneline`・`planbrief`（`render`）・`planmarks`（`gaps`・`home_gaps`・`depends_gaps`・`structure_gaps`・`split`・`save`・`renumber`・`append_trace`・`line_in`・`handed`・`contract_diff`・`widened`・`design_need`・`FIELDS_FILE`・`AMENDED_KEY`・`CORE_KEYS`・`AMEND_OP`・`REJECT`・`DEPENDS_REJECT`・`STRUCTURE_REJECT`・`NODE`）・`policy`（`recorded`・`brief`）・`replan`（`new_item`・`bare`・`_malformed`・`TRIP_KEYS`・`TRIP_FILE`）・`judgmark`（上の項）・`rolekit`（`accept_round`・`current_round`・`round_outcome`・`attempt`・`rejected`・`rejects_text`・`reject_rows`・`given_up_reason`・`candidate_path`・`resubmitting`・`resubmitted`・`merge_fields`・`BoardGap`・`NET_AFTER`）・`structmark`（`read`・`rows`・`note`・`skipped`・`dirty`・`DIRTY`。節の文は持たず `prompts/parts/structure-rows.md`）・`worldmark`（`rows`・`need`・`VERDICT_WORDS` の鍵・`WEB`・`DIFFERS`）。`lib/planfile.py`・`lib/planblk.py`・`lib/ripple.py`・`lib/startrec.py`・`lib/depth.py`・`lib/marks.py`・`lib/reads.py`・`lib/promptsection.py` は import しない。
- 共通の口に 1 つ足す: `workflows/.shared/ports.py` に `shared_cache()`（今の `workflows/.shared/boundary.py:279-283` の写し。Archon の `STATE_DIR` の下の `works-factory/`。渡されなければ None）。ライブラリの文書の run をまたぐ控えに使う（今の `boundary.shared_cache`）。`workflows/.shared/AGENTS.md` の口の一覧に足し、試験を `tests/blocks/shared/` に足す（10 節の 7）。波及の一覧の飛ばすフォルダは `src/steps.py` の `RUNTIME_COPY_DIRS = ((ports.RUNTIME_COPY,),)`（今の `boundary.RUNTIME_COPY_DIRS` と同じ値）。
- 共通の断片（2.3。作る時に無ければこの PR が足し、`workflows/.shared/AGENTS.md` の名の一覧に足す）: `resubmit`（取り置き。test-gate か spec の PR が先に足していればそれを使う）・`handoff`（取り置き。本文は report.md の 2.3 で決まっている）・`policy`（independent-design の PR が足す。本文は independent-design.md の 2.3）・`unknown-asks`（取り置き。本文はこの設計書の 2.3 の 11）・`recorded-policy`・`concept-map`・`prior-failures`（この設計書で名を決める。本文の元は 2.3）。

### 1.6 つなぎ方（graph の側。block には書かない）

- line の計画の往復の輪（今の `plan-rounds`）: `include: works-factory-plan`。`with:` は `judgment`・`units` ← 根本の診断の出力の `judgment`・`units`、`answer_ties`・`materials` ← 判定のまとめが返す結びと素材の状態の pointer、`answers` ← 始めの記録の `answers`、`takes_push` ← line の無人の方針（今の `gatepolicy.unattended_of(start)`）、`verify` ← 判定の裏取りの出力、`excluded` ← 並行 PR の出力の `excluded`、`depth_record` ← 頭の深さの出力の `record`、`decisions` ← 先行議論の突合の出力の `material`、`world_rows` ← 世界の解の出力の `rows`、`structure` ← 構造の目（before）の出力の `structure`、`spec` ← 仕様の出力の `spec`、`policy` ← 始めの記録の方針の写し（今の `policy.frozen_copy(start)`）、`prior_failures` ← 始めの記録の前の失敗の行、`base`・`review_rev`・`diff_base` ← 始めの記録の `base_rev`・`review_rev`・`input.base.rev`、`lang` ← 始めの記録の `lang`、`prior` ← line が往復ごとに書く前の周のファイル（1 周目は空の字）、`ruling: []`。
- line の案の直し（今の `replan`）: 同じ `include:`。`with:` は上と同じ値に、`ruling` ← 修正の出力の直す項目、`conflicts` ← 修正の出力の申し出と裁定、`prior` ← 承認済みの案の周（最後に受け付けた計画の周の `reply`・`fields`・`fix_plan`・`ripple` と、それまでの全部の周の `handoff`。`review` と `record` は null）。
- `prior` のファイルは line が書く（往復の記録は line が持つ。README の 1.2 の D）。`record` は、受けた事前審査ごとに `converge.add_pass` を当て、最後の受け付けた案の行を `converge.plan_rows` で置いた物（今の `planfile.converge_record` の中身）。line の設計書で、事前審査の port `prior` と同じファイルにできるかを決める（11 節）。
- 読み手: 事前審査（案の `plan`・`fix_plan`・`ripple`・`rejects`）・line の修正前の承認ノード（`fix_plan` の narrows の行。今の `runreport._fix_plan_rows` と `gatemarks` の読み）・line の単位ごとの深さ（`plan` の欄と `owed`）・修正（`plan`）・構造の目の after（`plan`）・line の止め（`status`・`reason`）・報告（`report`。`gave_up` は前の失敗の行の元）。
- 往復の止め時・安全の上限・事前審査を回すか・案の直しを回すかは line が決める。この block は止めない。

## 2 node の設計シート: plan-writer（修正案の役）

### 2.1 役

直す義務の単位を全部、項目のどれかにちょうど 1 度入れた修正案を、ファイルの行・狭める物の決め手・works の欄・構造と世界の解と処方への答えつきで書く。2 周目からは前の周の事前審査の block と答えの要る suggest に key ごとに答え、変えた項目だけを返す。形 replan では、貼った項目だけを、裁定の文が名指した所を直して返す。読むだけで、まだ手を動かさない。

### 2.2 port

`intake.json` の値（← 1.2 の全部の port）・`ripple-units.json`（← 作業ツリーを `git grep` した機械の一覧）・作業ツリー（← 修正案の役が Read・Grep で読む。port ではない）・前の回までの却下（← place の控え `rejects-plan.json`）・`lang`。

### 2.3 組み立ての順（`prompts/plan-writer.md`）

md は英語。上から次の節を並べる。`<!-- if … -->` の名は prep が `when` で渡す真偽で、入れ子にしない（README の 5.1）。形 replan の周は、形 plan だけの節の真偽を全部偽にする。中に段落の印を持つ節（断片を含む）は `if not replan` で囲まない（囲むと入れ子になる）。中に印を持たない決まった文の段落だけは `<!-- if not replan -->` … `<!-- end replan -->` で囲んでよい（`prompt.py` の閉じの印は `if` と `if not` のどちらも `<!-- end <名> -->`）。

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: この周の却下の控えが 1 件以上（`rolekit.attempt(round_dir, "plan") > 1`。resume で輪が 1 周目から回り直した回）。`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(round_dir, "plan"))`（古い順に全部。今の `REJECT_LINE` は全部の理由のファイルを名指していた。中身を貼る形に替える）。
2. 役の定義（決まった文。今の `planblk.HEAD["plan"]` の 1 段落目）: 修正案の役で読むだけ・道具は Read・Grep・Glob・WebSearch・WebFetch だけ・作業ツリーを 1 字も変えない（受け付けは起こす前の写しと比べ、変わっていれば拒む）・この指示に従い出力の schema に合う JSON だけを返す。新しい会話で起きたとは書かない（輪の `fresh_context: false`）。
3. この工程が在る理由（決まった文。今の `fix-plan.md:5-8`）。
4. `<!-- if not replan -->` やること（決まった文。今の `fix-plan.md:12`）: 直す義務の単位を全部どれかの項目に入れる・どの単位が義務かは「直す単位」の節の行ごとの印が正本（必ず入れる・入れてもよい・機械が差し込む）・入れてはいけない単位は拒まれる・1 つの項目で複数の単位を閉じてよいのは根を共にする時（下の項目の組み方の決まり）`<!-- end replan -->`。
5. 項目の欄の書き方（決まった文。今の `fix-plan.md:13-25` の 1〜6: `unit_keys`・`approach`・`files`〔新しく生まれる物を全部・行の欄・`symbols`・`home`・`considered`・書き落とした物は審査されない〕・消す物〔`why`・`replaced_by`〕・`shrink_first`・`narrows`〔BASE の能力の棚卸しの基準は観点の正本の「移行退行の棚卸し」の項。代償として採るかを自分で決めない〕）と結びの 1 文（今の `fix-plan.md:27`「まだ手を動かすな。案は別の目が審査し、予測した穴への応答を後で求められる」）。
6. works の欄（決まった文。今の `planmarks.HEAD`）。
7. 項目の組み方・既にある物を先に探す・対象の文を前の決定に使わない・判断の 1 軸と考えの住処（決まった文。今の `planblk.ITEMS_RULE`・`REUSE_RULE`・`TARGET_TEXT_PLAN`・`concepthome.PLAN_RULE`）。
8. 承認ノードの項目の決め手と、狭めない案を先に探す（決まった文。今の `gatemarks.HEAD["p2.fix_plan"]` の 2 段落）。
9. `<!-- if excluded -->` 並行 PR の範囲の 1 文（決まった文）と `{excluded_file}` ← port `excluded` のパス `<!-- end excluded -->` — 条件: `excluded` が在る。
10. `{lib_docs}` ← `libdocs.section(place, repo, files, shared=ports.shared_cache())`（`files` は `libdocs.unit_files(repo, <判定のファイル>, keys)`。`keys` は判定の案に入れてよい単位の key、判定が無ければ None。判定のファイルが無ければ空の並びと訳「判定のファイルが無い」の 1 行を足す。今の `planfile.lib_section`）。`libdocs.section` は材料の行（文書の控え・引けない訳）だけを返し、見出しと「自分で引け」の文は md `prompts/parts/lib-docs.md` が持つ（`prompt.render_part("lib-docs", {"rows": …})`。#764）。
11. `{shared:prior-failures}`（断片の中の段落 `prior_notes`・`prior_redesign` と口 `{prior_notes}`・`{prior_redesign}`。値は `carry.prior_section` の行の組み方の写し: 前の run の行のうち作り直しでない行と作り直しの行〔`carry.is_redesign`〕を 1 件 1 行 `- <where>: <text>`）。行の形が違えば節を出さず、27 の読めなかった入力に `prior_failures: <訳>` を足す（今のまま）。
12. `{shared:recorded-policy}`（断片の中の段落 `recorded_none` と口 `{recorded_rows}`）。値は `policy.recorded({"policy_md": <policy のパスか空>, "answers": <answers>}, <decisions のパスか None>, human_items=None)` の行を、今の `policy._section`（`lib/policy.py:295-314`）の行の組み方で英語の札にした物。承認ノードの答えの行はいつも「この役には渡っていない」（今のまま。plan に承認ノードの答えは届かない）。名指しの字（`name`）は変えずに入れる（受け付けと承認ノードが字で照らす）。
13. `{shared:concept-map}`（断片の中の段落 `maps_found` と口 `{concept_maps}`・`{map_tail}`）。値は `concepthome.tracked_names(repo)` と `pick_maps` から、今の `concepthome.section` の行（`- <パス>`、超えた分は `- and <n> more`）と、見つからない時の尾（木を読めなかった訳）。
14. `{shared:handoff}`（report.md の 2.3 の本文。段落 `handoff_rounds`・口 `{handoff_rounds}`）。条件: `prior.handoffs` が 1 件以上。値は 1 周 1 行 `- r<round>: <パス> (Read it)`、メモの無い周は `- r<round>: (no notes)`、読めない周は `- r<round>: (unreadable)`（今の `handoff.section` の行。札は report と同じ）。
15. 直す単位（形 plan）: `<!-- if units -->` 見出しと頼み（今の `planfile.UNITS_HEAD`）、`{units}` ← 単位ごとの行（`- no <n> \`<key>\`: label=<label>・disposition=<disposition か none>・<義務の札>` と `  - paths: …`・`  - summary: …`）、`<!-- end units -->`。続けて `<!-- if filled -->` 機械が差し込む no の 1 文と `{filled}` `<!-- end filled -->`、`<!-- if units -->` 入れてはいけない単位の 1 文と `{shut}`（無ければ `none`）`<!-- end units -->`、`<!-- if skipped -->` 構造の目が見ていない単位の 1 文と `{skipped}` `<!-- end skipped -->`、`<!-- if questions -->` 問いの台帳の 1 文と `{questions}`（JSON の 1 行）`<!-- end questions -->`、`<!-- if view -->` 判定者の見立ての 1 文と `{view}` `<!-- end view -->`、`<!-- if precedents -->` 判定者の先行例の 1 文と `{precedents}` `<!-- end precedents -->`。今の `planfile.units_section`。
16. `<!-- if units -->` リポジトリの行（決まった文の札と `{repo}`・`{read_rev}`・`{diff_base}`・`{review_md}`）`<!-- end units -->`。`repo` は作業ツリーの絶対パス、`read_rev` は port `review_rev`（空なら `base`、それも空なら `HEAD`）、`diff_base` は port `diff_base`（空なら `base`、それも空なら `read_rev`）、`review_md` は `ports.lib_root() / "REVIEW.md"`（今の観点の正本。組み込みで `workflows/.shared/prompts/` へ移る時に直す）。今の `planfile.repo_line`。形 replan の周には出さない（今も形 plan の材料だけに在る）。
17. `<!-- if prescriptions -->` 判定の処方の見出しと頼み（今の `planblk.PRESCRIPTION_HEAD`・`PRESCRIPTION_ASK`）、判定の記録の 1 文と `{judgment_file}`、`{prescriptions}` ← 単位ごとの `### <key>` と番号つきの処方 `<!-- end prescriptions -->` — 条件: 案に入れる単位に処方が在る。
18. 構造の目の行: `<!-- if structure_missing -->` 見出しと `{structure_note}`（`structmark.note` の訳。字のまま）`<!-- end structure_missing -->`、`<!-- if structure_dirty -->` 見出しと頼み（今の `structmark.PLAN_HEAD`・`PLAN_ASK`）と `{dirty_rows}` `<!-- end structure_dirty -->`、`<!-- if structure_clean_only -->` 見出しと汚れる行が無い 1 文（今の `PLAN_NONE`）`<!-- end structure_clean_only -->`、`<!-- if structure_clean -->` 汚れないと見た行の見出し（今の `PLAN_CLEAN_HEAD`）と `{clean_rows}` `<!-- end structure_clean -->`。行は今の `structmark._row_line` の組み方（判定の語 `汚れる`・`汚れない` は字のまま。札は英語）。今の `structmark.plan_section`。4 つの段落は `prompts/parts/structure-rows.md`（`{part:structure-rows}`）に在り、修正案の役の指示と、案の直しの項目の brief（`item-brief-<n>.md`。`planbrief.render` へ渡す構造の節。`brief.structure_section` が `prompt.render_part` で組む）が同じ文を使う。値と真偽は `brief.structure_parts`。
19. `<!-- if world -->` 世界の解の行の見出し（今の `worldmark.HEAD`）、`{world_rows}`（今の `worldmark.section` の行の組み方。web で確かめていない行の印は `({not_web})`）、答えの頼み（今の `worldmark.PLAN_ASK`。中の「web で確かめていない」は `{not_web}`）`<!-- end world -->` — 条件: 世界の解の行が 1 行以上。`{not_web}` は `src/brief.py` の定数 `NOT_WEB = "not checked on the web"` 1 つ（md と行の印が同じ字を持つ）。
20. `<!-- if ripple_units -->` 案の前の波及の一覧の見出しと頼み（今の `ripple.UNITS_HEAD`・`SCOPE_ASK`）と `{ripple_units}`（単位ごとの `### Unit <key>` と名と当たりの行）`<!-- end ripple_units -->`、`<!-- if ripple_units_error -->` 同じ見出しと作れなかった 1 文（今の `ERROR_NOTE`）と `{ripple_units_error}` `<!-- end ripple_units_error -->`。
21. `<!-- if verify -->` 裏取りの申し送りの見出しと頼み（今の `planblk.VERIFY_HEAD`・`VERIFY_ASK`）と `{verify_rows}`（単位ごとの行と相乗りの行。今の `planblk.verify_part` の行の組み方）`<!-- end verify -->`、`<!-- if verify_unreadable -->` 同じ見出しと読めない 1 文と `{verify_file}` `<!-- end verify_unreadable -->`。
22. `{shared:unknown-asks}`（11 の節の本文はこの節の終わり。段落 `unknown_rows`・`unknown_none`、口 `{kind_none}`・`{kind_cause}`・`{kind_shape}`・`{kind_scope}`・`{unknown_rows}`・`{unknown_why}`）。条件: 形 plan で判定が在る（今の `headdepth.section(...) if judgment_file`）。行は `- line <item> (<kind>): request text 「<cause_quote>」・place <where>「<code_quote>」`（番地が無ければ `place: none (the cause is not visible in code)`）。種類の語は `headdepth.NONE` などの字のまま。行の無い時は `unknown_none` と `{unknown_why}` ← 控えの `why`（無ければ `headdepth.NO_RECORD`）。
23. `<!-- if spec -->` 仕様の見出しと頼み（今の `planfile.SPEC_HEAD`）と `{spec}`（`src/brief.py` の `_json_block` の JSON の囲み。JSON でなければ字のまま）`<!-- end spec -->`。
24. 前の周（形 plan の 2 周目から）: `<!-- if prior -->` 前の周の見出し（今の `PRIOR_HEAD`）と、前の周の案の 1 文と `{prior_fix_plan}`・`{prior_fields}` `<!-- end prior -->`、`<!-- if prior_review -->` 事前審査の指摘の 1 文と `{prior_review}` `<!-- end prior_review -->`、`<!-- if no_prior_review -->` 受けていない 1 文 `<!-- end no_prior_review -->`、`<!-- if revise -->` 答えの頼み（今の `converge.REVISE_ASK`）と `{revise_blocks}`（返した block ごとの `### <key>` と `- kind: …` などの行。今の `converge._face_text`）`<!-- end revise -->`、`<!-- if owed_suggests -->` `{revise_pass}` 往復目の答えの要る suggest の見出しと `{owed_suggests}` `<!-- end owed_suggests -->`、`<!-- if revise_notes -->` 参考の suggest の 1 文（今の `NOTES_HEAD`）と `{revise_notes}` `<!-- end revise_notes -->`、`<!-- if revise_keys -->` suggest の key の 1 文と `{suggest_keys}` `<!-- end revise_keys -->`、`<!-- if closed_items -->` 閉じた項目の 1 文（今の `CLOSED_ASK`）と `{closed_items}` `<!-- end closed_items -->`、`<!-- if held_items -->` 保留の項目の 1 文（今の `HELD_NOTE`）と `{held_items}` `<!-- end held_items -->`、`<!-- if prior_ripple -->` 項目ごとの波及の一覧の見出しと頼み（今の `ripple.HEAD`・`SCOPE_ASK`）と `{prior_ripple}`（項目ごとの行と重なりの行）`<!-- end prior_ripple -->`、`<!-- if prior_ripple_error -->` 同じ見出しと作れなかった 1 文と `{prior_ripple_error}` `<!-- end prior_ripple_error -->`。条件: `prior` が在る形 plan。`revise` は事前審査を受けていて `converge.held(record)` が None でない時（`held` は最後の往復の行が修正案へ返す〔抜け方の語が again の〕時にその行を返し、ほかは None。今の `_prior_section` と `revise_section`）。
25. `<!-- if policy -->` `{shared:policy}` `<!-- end policy -->` — 条件: 形 plan で port `policy` のファイルが読める（形 replan には今も貼っていない）。`{policy_body}` ← `policy.brief({"policy_md": <パス>})["paste"]`（`PASTE_CAP` まで。超えた分は続きのパスの 1 行。今の `policy._capped`）。10 節の 5。
26. `<!-- if replan -->` 案の直しの頼み（今の `replan.REPLAN_ASK`）と `{replan_items}` ← 直す項目ごとの節（`## Item to fix <n> (its number in the approved plan)`・`- unit_keys (copy this text as is): <JSON>`・`- Brief of this item: <パス>`・`### The previous item (approved; pasted by the machine)` と JSON の囲み・申し出と裁定の行ごとの `### Objection and ruling from the fixing step (<id>)` と 6 つの札の行、行が無ければ `NO_ROWS` の英語の 1 文。今の `planfile.replan_section`）`<!-- end replan -->`。項目の brief は `planbrief.render` で `item-brief-<no>.md` に書く（今の `planfile.item_brief`。10 節の 4 の例外）。
27. `<!-- if unread -->` 読めなかった入力の見出し（今の `UNREAD_INPUTS_HEAD`）と `{unread}`（`- <port の名>: <訳>`）`<!-- end unread -->`。
28. 言語の 1 文（決まった文）と `{lang}` ← `prompt.lang(port lang)`: 1.2 の port `lang` の説明が名指す欄を `{lang}` で書く・key・enum の値・コードの識別子・パス・コマンド・誤りの文はそのまま（key は周をまたいで照らすので訳さない）。
29. 結びの 1 文（決まった文）: 出力の schema に合う JSON だけを返す。

md の本文の正本は `workflows/plan/prompts/plan-writer.md`。この設計書は組み立ての順だけを持ち、本文を写さない。md の中の `{world: <類の id>, follows: true}` などの JSON の例は差し込み口の形に合わないので字として残る。合う形の字を書く時は `{{`・`}}` で書く。

prep が渡す値はいつも同じ組（入らない段落の口には空の字）で、`when` の名は上の全部（`rejected`・`replan`・`excluded`・`prior_notes`・`prior_redesign`・`recorded_none`・`maps_found`・`handoff_rounds`・`units`・`filled`・`skipped`・`questions`・`view`・`precedents`・`prescriptions`・`structure_missing`・`structure_dirty`・`structure_clean_only`・`structure_clean`・`world`・`ripple_units`・`ripple_units_error`・`verify`・`verify_unreadable`・`unknown_rows`・`unknown_none`・`spec`・`prior`・`prior_review`・`no_prior_review`・`revise`・`owed_suggests`・`revise_notes`・`revise_keys`・`closed_items`・`held_items`・`prior_ripple`・`prior_ripple_error`・`policy`・`unread`）。

この PR が足す共通の断片の本文の元（英語にして足す。名と口と段落は上のとおり）:

- `workflows/.shared/prompts/recorded-policy.md`: 見出し（今の `policy.RECORDED_HEAD`）・決まり（`policy.RECORDED_RULE`）・`<!-- if recorded_none -->` 名指せる行が無い 1 文（`RECORDED_NONE`）`<!-- end recorded_none -->`・`{recorded_rows}`。
- `workflows/.shared/prompts/concept-map.md`: `<!-- if maps_found -->` 見出し（`concepthome.MAP_FOUND_HEAD`）と `{concept_maps}` と結びの 1 文（「審査するファイルを含むフォルダの地図を正とする」）`<!-- end maps_found -->`・`<!-- if not maps_found -->` 見出しと「無い（探した形: 追跡されたファイルの docs/concepts.md。根とどのフォルダの下でも）」と `{map_tail}` `<!-- end maps_found -->`（今の `MAP_NONE_HEAD`）。
- `workflows/.shared/prompts/prior-failures.md`: `<!-- if prior_notes -->` 今の `carry.PRIOR_HEAD` と `{prior_notes}` `<!-- end prior_notes -->`・`<!-- if prior_redesign -->` 今の `carry.REDESIGN_HEAD` と `{prior_redesign}` `<!-- end prior_redesign -->`。
- `workflows/.shared/prompts/unknown-asks.md`（head-depth.md の 8 節の 4 の取り置き。種類ごとの指示を行ごとでなく種類ごとに 1 回書く）:

```markdown
<!-- if unknown_rows -->
## Unknowns per request line, and what to do (per request line; the machine pasted them from the record of the run's head depth)

For each line below, do what its kind asks:

- `{kind_none}`: Check first that the quoted place is really the place to fix. If it is off, do not widen silently; name in your answer, with quotes, why it is off and the real place to fix.
- `{kind_cause}`: Follow the quotes from the line of the symptom to the line of the cause, and find the cause.
- `{kind_shape}`: Lay out two or more shapes, and write why you chose one and why you set the others aside.
- `{kind_scope}`: List the contracts you touch (types, setting keys, input and output shapes, subgraphs) and name the effect on each. When a choice is needed, lay out two or more shapes, and write why you chose one and why you set the others aside.

{unknown_rows}
<!-- end unknown_rows -->
<!-- if unknown_none -->
## Unknowns per request line, and what to do (per request line; the machine pasted them from the record of the run's head depth)

The unknowns per line are not decided (why: {unknown_why}).
<!-- end unknown_none -->
```

材料の札の英語（Python が組む行の頭。値は字のまま入れる）:

- 義務の札: `must be in the plan`・`may be in the plan (origin or depends of a question that waits for a person's answer; may be left out)`・`the machine fills in the previous pass's row (you need not write it if unchanged; do not write closed items)`。
- 記録された方針の行: `- Policy document: name \`<name>:<line>\` (lines 1–<n>; original place: none)`（元の置き場は port に無いので `none`。10 節の 5）・`- Policy document: none`・`- answers of the request: none`／`  - name \`<q>\`: <頭 120 字>`・`- Answers a person gave at approval nodes: not given to this role`・`- Settled points (from the decision records): none`／`  - name \`<where>\`: <topic>——<decision>`／`  - (no where, so it cannot be named) <text>`。
- 裏取りの行: 判じの語 `root`→`the root`・`not_root`→`not the root`（`(real root: <real_root>)`）・`unsure`→`cannot tell if it is the root`、`evidence found`/`evidence missing`、`place matches`/`place differs`、相乗りの `duplicate`・`related (same place)`・`related (different place)`・`order: \`<first>\` first, then \`<then>\``、確かめられなかった単位 `could not be checked (<errors>)`。
- 世界の解の行: `- Class <class_id> (request line <finding>・<where>): <problem> (activity: <activity>)`・`  - Practice: <practice>`・`  - Source <id>: <url>「<excerpt>」`・`  - Applies: <applies または none (a row that needs no answer)>`（`／Does not apply: <not_applies>`）・比べの語 `the same as the practice`・`different from the practice`・`the request shows no way to solve it`（`The request's way 「<proposed>」 is <語>——<challenge>`）。
- 構造の目の行: `<unit_id>: <verdict> (forms <faces>・grounds <evidence>)——<reason>`、避け方 `. Way to avoid: <chosen> (<chosen_reason>)`。
- 波及の行: `### Unit <key>`・`### Item <n> (unit_keys: <keys>)`・`- <name>: hits in <n> files`（多い名は `(<COMMON_NOTE の英語>)`）・`  - body <at>`・`  - test <at>`・`Names changed and their hits:`・`Hits not covered:`・`- <id>: <kind> <at> (name <name>)` と消す名の印 ` (a hit of a name to remove: a reference that breaks after removal)`・`- no name of it exists in the target`・`Overlaps between items (files that appear in the scope or hits of two or more items):`・`- <at>: items <n>, <m>`。
- 案の直しの申し出の札: `- Unit of the objection:`・`- Named by the objection (between):`・`- Reason of the objection (why_both_cannot_hold):`・`- Kind of the objection (kind):`（無ければ `(none)`）・`- Side judged right (which_is_right):`・`- Text of the ruling (<decision>):`。

### 2.4 返す形

今の `output_format`（`&plan_reply`）のまま。必須は `plan`（項目 1 つ以上。項目の必須は `unit_keys`・`approach`・`files`・`shrink_first`・`narrows`・`route`・`tests`・`rewrite_tests`・`refactor`・`allowed_paths`・`out_of_scope`。任意は `route_why`・`structure`・`depends_on`）。任意の頭の欄は `block_answers`（`converge.ANSWER_SCHEMA` の写し）と `handoff`（`handoff.SCHEMA` の写し）。欄の型は `planmarks.FIELD_SCHEMA`・`FILES_SCHEMA`・`gatemarks.MARK_SCHEMA`・`NO_NARROW_SCHEMA` の写しで、型の元のモジュールとの一致は試験が見る（今の `test_role_schemas_match_their_lib_owners`）。人に見せる欄は 1.2 の `lang` の説明に並べた欄（承認ノード・報告・事前審査に載る）で、言語は `{lang}`。

### 2.5 描いた骨組み（例の run の値。2 周目の 1 回目）

```markdown
You are the planning role, and you only read. Your tools are Read, Grep, Glob, WebSearch, and WebFetch; do not change a single character of the working tree (the check compares it with the copy taken before you started, and rejects the answer if it changed). …

**Why this step exists**: until now every step that judges a fix came after the fix. … Have a different reviewer hit the plan before writing, and fold the predicted holes into the plan before writing — this node produces that plan.

## What to do

Put every unit you owe a fix into one of the plan's items. …

1. `unit_keys` — …（項目の欄の 1〜6）

Do not touch anything yet. …

Works fields of a plan item: …（今の planmarks.HEAD）

How to group items: … / Look for what already exists first: … / … / One axis of judgment: … / Use the homes of concepts: …

The deciding source of each approval item: … / Look first for a plan that does not narrow: …

Range of parallel pull requests. Do not touch it, and do not put it in a unit: <run の置き場>/judge/pr-excluded.json (Read it first. …)

## ライブラリの文書（手元の版・公式）
…（KEEP の libdocs が組む日本語の材料。PyYAML 6.0.3 の 1 件）

## Recorded policy
…（決まり）
- Policy document: none
- answers of the request: none
- Answers a person gave at approval nodes: not given to this role
- Settled points (from the decision records):
  - name `docs/owner-decisions.md の deliver-via-archon-pr の「導いた事」の 4 つ目（390 行）と「決め」の 2 つ目（384 行）`: pr-commit は対象の commit のフックを飛ばさず、…
  - …（3 件）

## Map of the homes of concepts (the machine found it among the tracked files. Read it first)

- docs/concepts.md

…

## Notes handed over between rounds
…
- r1: <place>/r1/handoff.json (Read it)

## Units to fix in this round (pasted by the machine from the judgment; point to them in unit_keys by the no below)

- no 1 `workflows/merge/scripts/pr_commit.py hook_env: commit のフックの環境が、…`: label=block・disposition=do-now・the machine fills in the previous pass's row (…)
  - paths: workflows/merge/scripts/pr_commit.py
  - summary: 事実（実測）: …
The machine fills in these numbers (…): [1]
Units you must not put in (the check rejects them): none
The judge's view: {"framing": "根は 1 つで、…"}
The judge's precedents (world solution): [{"key": …, "verdict": "adapt", …}]

Repository: <run の作業ツリー> (version read: `4428f368…`)  BASE: `4428f368…`  Viewpoint source: <工場の lib>/REVIEW.md

## Prescriptions of the judgment (…)
…
Judgment record: <run の置き場>/judge/judgment.json

### workflows/merge/scripts/pr_commit.py hook_env: …

1. 零処方の検討: …
…（7 件）

## Rows of the structure eye (…)

No row was seen as dirtying the structure (…).

### Rows seen as not dirtying (for reference. …)

- workflows/merge/scripts/pr_commit.py hook_env: …: 汚れない (forms なし・grounds /units/0/summary・…)——…

## Rows of the world solution (…)

- Class w-459d38b29048 (request line 1・workflows/merge/scripts/pr_commit.py の hook_env（73 行あたり）): 自動化ツールが…（activity: …）
  - Practice: 子プロセスへは、…
  - Source x1: https://git-scm.com/docs/githooks「Environment variables, …」
  - …
  - The request's way 「フック用の環境は、…」 is the same as the practice

For each row that has a place it applies to (a row that needs an answer), …

## Ripple list before the plan (…)
…
### Unit workflows/merge/scripts/pr_commit.py hook_env: …
- no name of it exists in the target

## Notes from the check of the judgment's units (…)
…
Synergy between units: could not be checked (判定の裏取りは機能の切り替えで切（始めの記録の features_cut に judge_verify が在るか、頭の深さの段の足しが無い）)

## Unknowns per request line, and what to do (…)
…
- line 1 (無し): request text 「hook_env を tree_run.outside_env(os.environ) に寄せ」・place workflows/merge/scripts/pr_commit.py:73-76「userenv.read_gh_first(env)」

## The previous round's plan and the review's findings (pasted by the machine)

- Plan of the previous round: <place>/r1/p2.fix_plan.json and <place>/r1/plan-fields.json (Read them. …)
- Review findings: <run の置き場>/plan-review/…/review.json

The review (a different reviewer) raised the blocks below against the plan. …

### narrows-malformed-record-stop
- kind: regression
…（block 5 件）

## Suggests that need an answer, from pass 1

### gitfailed-mark-overclaims
…（4 件）

## Ripple list (…)
…
### Item 1 (unit_keys: workflows/merge/scripts/pr_commit.py hook_env: …)
…
- h26: test tests/workflows/test_line.py::… (name user_env_dir)
- h30: removed lib/runbranch.py:9 (name hook_env) (a hit of a name to remove: …)

Write the sentences people read (…) in the language of the request (the user's language). …

Return only JSON that matches the output schema.
```

例の run は 1 回目で通ったので却下の段落は入らない。方針の文書は無い run で、方針の節も入らない。`lang` は空で、`{lang}` に既定の文が入った形。事前審査の指摘のパスは、line が `prior.review` に渡す事前審査の出力の先（今は周のフォルダの写し `plan/r2/review/p2.plan_review.json`）。

### 2.6 今の指示との差

作り直しの時の、古い指示との差の記録。後の指示の変更では、ここに足さない。

今の指示は、node の `command: fix-plan`（`workflows/plan/commands/fix-plan.md`。27 行）と、それが Read させる材料のファイル `brief-<n>.md`（`planfile.write_brief` が `planblk.head`・`HEAD["plan"]`・`gatemarks.HEAD["p2.fix_plan"]` と、KEEP の lib の 12 のモジュールの文の定数から組んだ物）の 2 か所に在る。

- 移した: 材料のファイルの全部の決まった文（見出し・頼み・決まり）を md へ。lib の Python に残るのは材料の行と値だけ（2.3 の札の表は英語にした）。
- 移した: `fix-plan.md` の本文（理由・やること・欄の 1〜6・結び）を md の頭へ。材料のファイルを先に Read させる 1 行目（「新しい会話で起きている」「材料のファイル `$plan-prep.output.brief` を Read で読め」）は消した。指示は prep が組んで `prompt` で直に渡す（README の 5.2）。輪は `fresh_context: false` なので「新しい会話で起きている」と言わない。
- まとめた: 2 か所に在った「指示書の JSON Schema に合う JSON だけを返せ」（`planblk.HEAD["plan"]` と `fix-plan.md` の作り）を結びの 1 文に。
- 替えた: `fix-plan.md:12` の「材料のファイルに『## 案に入れてよい単位の no』のセクションが在ればそれが正本」は、工場の材料に無い節（元の works の `PLAN_SLOTS_HEAD`）を名指していた。直す単位の節の行ごとの義務の札を正本と言う形に替えた（今の材料が実際に持つ物。意味は同じ）。
- 替えた: 形 replan の周で、`fix-plan.md:12` の「直す義務の単位を全部、案に入れろ」を出さない（`<!-- if not replan -->`）。形 replan の材料には単位の一覧が無く、`REPLAN_ASK`（貼った項目だけを直せ）とぶつかっていた。
- 替えた: 前の回の却下（resume で輪が 1 周目から回り直した回）を、全部の理由を書いたファイルを名指す 1 行（`rolekit.REJECT_LINE`）から、全部の理由を貼る共通の断片 `{shared:rejected}` に（README の 13 章。役はファイルを Read せずに受け取れる）。
- 替えた: 方針の文書を、置き場を名指して「先に全部読め」と言う段落（`planfile.POLICY_PART`）から、本文を貼る共通の断片 `{shared:policy}` に（10 節の 5）。
- 替えた: 頭の深さの行ごとの指示（`headdepth.ASKS` を行ごとに貼っていた）を、共通の断片 `unknown-asks` の種類ごとの 1 回に。行は種類の語を名指す。
- 消した: 下流の node の名と、ほかの block の振る舞いの名指し（「P3 の `plan_faces`」・「修正役・TDD の役」・「事前審査の下請けが答える」・「修正前の承認ノードで人に回る」の node の名・「修正の段へ申し送られる」・「承認ノードが読む」）。この役が書く欄の効き目（人に聞かれる行・聞かずに通る行・拒まれる物）は、名を出さずに「the run asks a person before fixing」「a later review」の形で残した（10 節の 8）。
- 消した: 「包みが system prompt に足す」（`concepthome.PLAN_RULE` の中。今の包みは地図の節を足していない。地図の節はこの md が入れる）。「写しの指示書はこの欄を知らないが」（`planmarks.HEAD` の頭。写しの指示書は無くなった）。「共有ボード」（`libdocs` の外の文。この block の言葉でない）。
- 移した: 言語の 1 行（`rolekit.LANG_RULE`）を md の 1 文に。汎用の欄の並びは、この node の人に見せる欄の名指しに替えた。
- 足した物は無い。英語にした。役の名「修正案の役」は "the planning role"。

### 2.7 元の works と graphloops の同じ場面

7 節にまとめた。

### 2.8 受け付け

5 節。

### 2.9 試験

9 節。

## 3 node の設計シート: plan-writer-fix（出し直しの役）

### 3.1 役

受け付けに拒まれた後、修正案の役の会話の続きで、拒まれた所だけを直して返す。材料とリポジトリは会話の中で読んだ物のまま。

### 3.2 port

最後の却下の理由（← `rolekit.rejected(round_dir, "plan")` の最後の 1 件）・機械が合わせた前の答えの控え（← `rolekit.candidate_path(round_dir, "plan")` の絶対パス）・形（← `intake.json` の `mode`）。

### 3.3 組み立ての順（`prompts/plan-writer-fix.md`）

1. `{shared:resubmit}`（共通の断片。作る時に在る断片の口の名に値を入れる: 最後の却下の理由と、控えの絶対パス。断片が無ければ、この PR が test-gate.md の 3.3 の本文と口の名〔`{rejection}`・`{candidate}`〕で足す。11 節）。
2. `<!-- if not replan -->` `plan` の欄の合わせ方（決まった文。今の `planfile.RESUBMIT_RULES` の 2 行目からの英語）: `plan` には拒否に挙がった項目だけを前と同じ型の丸ごとの項目で返す・`unit_keys` が 1 つでも重なる前の項目は返した項目に置き換わる（no と単位の名のどちらでも同じ単位。2 つの項目をまとめる・単位を隣の項目へ移す時は関わる項目を全部返す）・どの前の項目とも重ならない項目は後ろに足される・今の周に直す単位を 1 つも持たない前の項目は、`plan` を返すと消える・`block_answers` と `handoff` は直す時に全部を返す（欄ごと置き換わる）・項目を消す時だけ `{whole_plan}` に true を書き、閉じた項目を除く案の全部を返す（この後の出し直しもこの全部の案に合わせる）。段落の頭の 1 文で「断片の『返した欄は前の欄を丸ごと置き換える』は、`plan` の欄には当てず、この段落の決まりで合わせる」と言う。段落は `<!-- end replan -->` で閉じる。
3. `<!-- if replan -->` 形 replan の合わせ方（決まった文。今の `REPLAN_RESUBMIT_RULES`）: `plan` を直す時は貼った項目の全部を貼った順に返す（丸ごと置き換わる）・`handoff` を直す時は全部を返す `<!-- end replan -->`。

`{whole_plan}` ← `src/steps.py` の `WHOLE_PLAN = "whole_plan"`（md と受け付けが同じ字を持つ）。言語の 1 文は入れない（今の出し直しの指示書にも無い。言語は会話の頭の指示に在る）。`when` は `{replan}` だけ。

### 3.4 返す形

修正案の役と同じ `&plan_reply`（`required: []`。`whole_plan`（boolean）を持つ。#832）。人に見せる欄と言語は 2.4 と同じ。

### 3.5 描いた骨組み（本物の run `821e6fab-…` の `plan/r2/brief-2.md` の値）

```markdown
Your previous answer was rejected by the machine's check. In this same conversation, fix only what was rejected and return it. …

The reason the check rejected it (verbatim):

~~~text
修正案の項目の works の欄 structure に欠けか誤りが在る（構造の目が汚れると見た単位を持つ項目は、…）。拒んだ行:
  - plan[0].structure[0].row（1）: 構造の目が汚れると見た行の単位でない（在るのは [<単位の key 2 つ>]）
  - …
~~~

The whole previous answer, as the machine merged it: <place>/r2/candidate-plan.json (you can Read it; …).

How to answer:

- …

For `plan`, the rule above does not apply. Return in `plan` only the items the rejection names, as whole items of the same type as before. …
```

却下の理由は受け付けが組む日本語の文のまま入る（README の 5.3）。

### 3.6 今の指示との差

作り直しの時の、古い指示との差の記録。後の指示の変更では、ここに足さない。

今の指示は YAML の `prompt:` の 1 行（「前の回の返答は受け付けで拒まれた。この会話の続きで直す。指示書を Read で全部読み…」）と、それが Read させる指示書（`rolekit.RESUBMIT_ASK` に `planfile.RESUBMIT_RULES`〔形 replan は `REPLAN_RESUBMIT_RULES`〕を入れた物）の 2 か所に在る。

- 移した: 指示書の本文を共通の断片 `resubmit` と md の 2 つの段落に。YAML の 1 行（指示書を Read で読め）は要らなくなった（README の 5.2）。
- 替えた: `RESUBMIT_RULES` の 1 行目「直す所の無い欄は書くな」は、断片の「直す欄だけを書く」と同じなので、断片の 1 回に。`plan` の合わせ方は、断片の欄ごとの置き換えの決まりの例外として、md の段落で言う（今は `{rules}` の差し込みで決まりを丸ごと替えていた。断片は 2 つ以上の block が使うので、役ごとの決まりを断片の外に置く）。
- 足した物は無い。英語にした。

## 4 script の node

- `intake.py`: `INPUTS_JUDGMENT` などを `os.environ.get("INPUTS_<名>")` の字のままで読み（INPUTS_ を読むのは intake と accept の `reply`・`fix_reply`・prep の `prev` だけ）、1.2 の form の口に渡す。`judgment`・`prior` と `prior` の入れ子の欄は、pointer かパスならそのパス、値なら周のフォルダに写しを書いてそのパスを使う（`steps.nested_file`。役に名指すパスと受け付けの出どころの照らしに要る）。周の番号 `k = prior.round + 1`（`prior` が無ければ 1）を決め、`r<k>/` を作り（在れば 1.4 の名のファイルを消す）、`current-round.json` を書く。形は `ruling` が空でなければ `replan`。読めない port の扱い:
  - 形 plan で `judgment`、どちらの形でも `world_rows`・`prior`・`ruling` が読めない（形の照らしに落ちた・ファイルが無い・JSON でない）: 役を起こさない（`go: false`。訳は「<port の名>が読めない（<訳>）」を「。」で繋いだ物）。今の `round_inputs`（start・review・world・判定）と同じ決まり: 後の node が同じ入力を「無い」と読んで既定で進むので、読めない入力で役を起こさない。
  - ほかの port が読めない: 役は起こし、`intake.json` の `unread` に `- <port の名>: <訳>` を残す（2.3 の 27）。今の `plan_prep` の `unread`。
  - 形 plan: 判定から `gatemarks.ledger_files(judgment, ties_file=answer_ties, materials_file=materials, answers=answers, takes_push=takes_push)` を組んで直す義務を数え（今の `read_judgment`）、`held_why`（判定が読めない・`NOTHING_OWED`・行き止まり）が空なら `slots.json` を書く。
  - 形 replan: `prior.reply` の `plan` の項目の数で `planmarks.handed(ruling, n)` を当て、渡す項目と訳を決める。直す元の案が無ければ「直す元の承認済みの修正案が無い」。
  - `round.json` に `{round, mode, go, why, items}` を書く。返り `{go, mode, round, reason: why}`。誤り（import の失敗を含む）は `ports.run` の fallback が標準ライブラリだけで `round.json` を `go: false`・訳つきで書き（周のフォルダが無ければ作る）、`{go: false, mode: "plan", round: k, reason}` を返す（今の `round.py` の `failed`）。
- `ripple_units.py`: 今の `planfile.ripple_units`（案に入れてよい単位と直す義務の単位の key の名を `ripple.for_units` で引く。`skip_dirs=RUNTIME_COPY_DIRS`）。
- `plan_prep.py`: `prev`（`ports.parsed(os.environ.get("INPUTS_PREV"))`）と控えで `rolekit.resubmitting(round_dir, "plan", prev)` を見る。真なら `tree.json` を置き直して `{prompt: "", resubmit: true}`。偽なら `brief.values(round_dir)` で 2.3 の値と真偽を組み、`prompt.emit("plan-writer", values, when, prompt.round_of("plan-writer"))` で組んで、`tree.json` を置き直して `{prompt, resubmit: false}`（今の `plan_prep.py` と `snap_tree` を両方の道で置く順）。形 replan では `item-brief-<no>.md` をここで書く。`prompt.PromptError` は周のフォルダの `prompt-error.json` に node と訳を書いてから上げる（node が落ち、輪が落ち、出口が `failed` と訳を返す）。
- `fix_prep.py`: 最後の却下の理由と控えのパスで `prompt.emit("plan-writer-fix", …, {"replan": mode == "replan"}, prompt.round_of("plan-writer-fix"))`。誤りの扱いは `plan_prep.py` と同じ。
- `plan_accept.py`: 今の `plan_accept.py` の順のまま: 周を読む → `rolekit.current_round` が拒否の控えを読めなければ照らさずに `done` の拒否（`attempt: 0`）→ `rolekit.resubmitted`（形 plan は `merge_resubmit`〔`slot_list` は `round_slots`〕、形 replan は `merge_replan_resubmit`）→ `take`（形 plan は `take_plan`、形 replan は `take_replan`。`keys = accept.status_keys("true")`〔今の `with: status_guarded: true`〕・`base_rev = port base`・`tables = planmarks.design_need(structmark.dirty(structure)), worldmark.need(world_rows)`）→ `rolekit.accept_round(round_dir, "plan", None, lambda _: out, net=True)` → `attempt = n - (1 if out.get("halt") else 0)`。返り `{**rolekit.round_outcome(got), attempt}`。誤りは `ports.run` の fallback で `{ok: false, done: true, give_up: true, reason: "受け付けが落ちた（<訳>）", attempt: 0}`。
- `ripple_items.py`: 今の `planfile.ripple_items`（受け付けた案の欄が在れば `ripple.build`、無ければ `{items: [], error: why_not_ready}`）。
- `finish.py`: 今の `plan_collect.py` の中身を 1 つにした物。受けた案の有無（`accepted_fields`）・形 replan で諦めた時の `note_gave_up`（項目ごとの行を `replan-gave-up.json` に置く）・`why_not_ready`・`placeholders`（`plan-fields.json`・`ripple.json` を在って空でない形に）・`returned`（`fix_plan`・`reply`・`handoff`・`replan` の pointer と `rejects`）・`owed`（`owed_order`）・`status`（1.2）・`report`（下の報告の行）を組んで返す。誤りは `ports.run` の fallback が標準ライブラリだけで `finish-error.txt` に訳を書き、`plan-fields.json`（`{round, fields: []}`）と `ripple.json`（`{items: [], error}`）を空でない形で置いて、`{ok: false, status: failed, reason, mode: "plan", round, owed: [], plan, ripple, fix_plan: null, reply: null, handoff: null, replan: null, rejects: [], gave_up: null, report: [<訳の 1 行>]}` を返す（今の `plan_collect.failed`）。周の番号は `current-round.json` から読み、読めなければ 1。
- `finish.py` の報告の行（`report`。報告の節「修正案」に並ぶ日本語の行。`src/steps.py` の `report_lines` が値から組む）:
  - `ok`: `修正案: 周 <round>（<案を書く|案の直し>）・項目 <n> 件・受け付けの拒否 <m> 回`。形 replan では続けて `案の直しで直した項目: <番号の並び>`。
  - `nothing_owed`: `修正案: 周 <round>・直す義務の単位が無いので修正案の役を起こさなかった（<reason>）`。
  - `held`・`gave_up`・`failed`: `修正案: 周 <round>・修正案を出せなかった（<status>）: <reason>`。形 replan で諦めた時は、項目ごとに `案の直しを終えられなかった 項目 <item>: <why>。裁定の文: <ruling>`。
  - 狭める能力の行と承認ノードの文は、ここに組まない（`fix_plan` を読む line が組む）。

## 5 受け付け

- 却下の理由の文は Python（`src/take.py`・`src/steps.py` と、KEEP の `planmarks`・`gatemarks`・`converge` の照らし）が組む。日本語のまま（網の回まで拒まれた時に `reason` を通って報告に載り、出し直しの役の指示に字のまま入る。README の 5.3）。
- 形 plan（今の `take_plan` のまま）: 役が作業ツリーを動かしていれば、それだけで先に拒む（`moved`。`tree.json` が無ければ `NO_TREE`）→ 返答から `whole_plan` と `handoff` を外す → 返答の形が崩れていれば `MALFORMED_REJECT` → 往復の記録（`prior.record`。無ければ `{round: 0, passes: [], outcome: None, open: {}}`。案の行 `row` は事前審査が `planmarks.joined` で欄の行を重ねた物なので、機械が足した `rewrite_tests[].limit` を外し〔#845〕、事前審査が `converge.PLAN_MARKS` に添えた `narrows` の行の決め手の欄を行に戻して〔#849〕、`hash` を付け直した写し `bare_record` を使う。受けた案の項目は記録の行から戻した形と字のまま同じになる）で `converge.split` と `named` と `converge.splice`（`whole_plan` なら差し込まない。`whole_plan` の返答は閉じた項目を除く案の全部なので、返答に無い開いた項目は消す意図で、前の周の行を戻すと消せない。閉じた項目の行だけは差し込む）→ 往復の行が在れば合わせた案の全体を `candidate-plan.json` に書く → 次の 9 つの理由を全部 1 回で並べる: 答えの要る穴への答え（`converge.answer_gaps`・`fixed_unchanged`）・閉じた項目・狭めない案の欠け（`gatemarks.narrow_gaps`）・推しの形（`recommend_gaps`）・義務の無い単位（`not_allowed`。入れてよい no の並びつき）・単位の網羅（`fix_plan_covers_units`。入れてはいけない単位を外して数える）・項目の欄（`planmarks.gaps`・`home_gaps`）・依存（`depends_gaps`）・構造の目と世界の解の行への答え（`structure_gaps`）。通れば修正前の版のテスト（`base_test_texts(repo, base or "HEAD")`。読めなかった物は trace に `BASE_TESTS_UNREAD_OP`）で `planmarks.split` し、`p2.fix_plan.json` → `plan-fields.json` → `reply.json` → `handoff.json` の順に置く（往復の行が在れば `block_answers` も控えと返答に）。どれかを置けなければ置いた物を消し、`round.json` の `why` に訳を残して `{ok: false, halt: true, count: false, give_up: true}`（拒否に数えずに輪を止める）。置けたら捨てた閉じた項目の id を trace に `converge.DROPPED_OP` で残す。
- 形 replan（今の `take_replan` のまま）: 作業ツリー → `handoff` を外す → 直す元の案が無ければ `REPLAN_REJECT` と訳 → 渡した項目の行（`replan.TRIP_KEYS`）→ `take.plan_errors`（項目の数・`unit_keys` の字・項目の欄〔修正前の版の木の `exists_at`。版が引けなければその訳〕・直した番号の所に返答を差し替えた並びに当てる依存と考えの住処・構造と世界の解・狭めない案・推し）→ 通れば `new`・`new_marks`・`contract_changed`・`widened`（事実だけ）→ 修正前の版のテスト → `revised_fields`・`amended` → 案の全体を置く（`_save` の順と halt は形 plan と同じ）→ trace に `planmarks.AMEND_OP` → `replan.json`。
- 輪は拒否の回数では諦めない。受け付けの網 `rolekit.NET_AFTER`（20。輪の `max_iterations` と同じ。届けば工場の不具合）の回の拒否で `done`・`give_up` にして輪を抜ける（`max_iterations` で落とさない）。拒否の控えが読めない・書けない時は、落ちずに `done`・`give_up` の拒否（理由「拒否の控えが扱えない」。読めない時は返答を照らさず、案のファイルを書かない）。
- 受けた案の控えを置けない周（halt）は役の諦めでなく機械の故障なので、出口は `status: failed` と、置けなかった控えの名を含む訳を返す（`round.json` の `halt: true`）。
- 諦めた時に出口へ書く物: `status: gave_up`・`reason` は `rolekit.given_up_reason`（網の回なら `NET_WHY` を添えた最後の理由）か `round.json` の `why`。形 replan では項目ごとの `gave_up` の行（`PLAN_GAVE_UP_WHY` と裁定の文を字のまま）。
- 拒否を足す道: 返答の形で決まる拒否は `src/take.py` の `take_plan`・`take.plan_errors` の理由の並びに 1 行足す。md には同じ変更で 1 段落を足す。理由は `rolekit.accept_round` が控えに積み、次の回の出し直しの指示（最後の理由）と、resume の回の `{shared:rejected}`（全部）に載る。試験は `tests/blocks/plan/test_accept.py`。

## 6 今の工場の計画との比べ（能力ごとの行き先）

今の `workflows/plan/` と `lib/planfile.py`・`lib/planblk.py`（修正案の役の部分）・`lib/ripple.py` が持つ確かめ・守り・落ちない道・やり直し・書く順・指示を全部並べ、block のどこに在るか、外すならその訳を書く。指示の文の行き先は 2.6・3.6。

### 6.1 周を開く（今の `round`）

- 周の番号を往復と案の直しを通して数える → `prior.round + 1`（4 節）。前の周の数え方だけが変わり、通しの番号は同じ（line が `prior` を順に渡す）。
- ruling が空でなければ形 replan → 同じ。ruling が JSON でなければ役を起こさない → `ruling` の json の form が落ちれば `go: false`。
- 線が渡した pointer（start・review・world・判定）が読めなければ役を起こさない → 4 節の intake（`judgment`・`world_rows`・`prior`）。start は無くなった。
- 判定が読めない・直す義務 0 件・行き止まり → `held_why` を写して同じ。0 件は `status: nothing_owed`、ほかは `held`。
- 形 replan で直す元の案が無い・ruling の番号が外れ → 同じ（直す元は `prior.reply`）。
- 受けた事前審査を周のフォルダに写す（`review/p2.plan_review.json`）→ 外す。往復の記録は line が組んで `prior.record` で渡し、指摘のパスは `prior.review` をそのまま名指す（写しの読み手は `converge_record` だけだった）。値で受けた時だけ写しを書く。
- `slots.json`（案に入れてよい単位の並び。受け付けと出し直しの合わせが読む）→ 同じ。
- `round.json` の `at`（読んだ証拠の記録を切る時刻）→ 外す（読んだ証拠の node を外すため。6.6）。
- 周を開く途中で落ちても、標準ライブラリだけで `go: false`・訳つきの周を開いて返す（半ば開いた周のフォルダを使う）→ intake の fallback（4 節）。同じ周のフォルダが在れば名のファイルを消して使う。

### 6.2 波及の一覧（今の `ripple-units`・`ripple-items`）

- 案の前に単位の key の名の呼び出し元と試験を `git grep` で引く（形 replan では作らない）→ 同じ。
- 受け付けた案の項目ごとに、変える名・消す名の当たりを本体と試験に分け、覆っていない当たりに id を振る。多い名は数だけ・文書と生成物は捨てる・消す名は設計書の当たりも数える・項目どうしの重なり → `src/ripple.py`（MOVE。中身は今のまま）。
- 作業ツリーに写された工程の置き場（`.archon/`）を飛ばす → `RUNTIME_COPY_DIRS`。
- git が無い・リポジトリでない時は一覧の `error` に訳を書き、例外で止めない → 同じ。指示には「作れなかった」の段落（2.3 の 20・24）。
- 案が無い周も `{items: [], error: <訳>}` を書く → 同じ。

### 6.3 指示を組む（今の `plan-prep`）

- 前の回が拒まれ、合わせた答えの控えが在れば出し直しの役を起こす。resume で輪が 1 周目から回り直した時は 1 回目の役を全部の材料で起こす → `plan-prep` の `resubmitting` と `plan-fix-prep`（1.3）。
- 役を起こす前の作業ツリーの姿を回ごとに置き直す（受け付けが比べる）→ `plan-prep` が両方の道で置く。
- 材料の節の全部（2.3 の 1〜29）→ md と `src/brief.py`。節を出す条件は今の `write_brief`・各 lib の `section` の条件のまま（2.3 の各行）。
- 読めなかった入力を名指す節（黙って「無い」に見せない）→ 2.3 の 27。
- 前の run の失敗の行を周のフォルダに約束の形を照らして置く・形が違えば読めなかった入力に名指す → 2.3 の 11（`carry.place_prior`）。
- 判定の処方の出どころとして判定の記録の絶対パスを名指す → 2.3 の 17。判定を値で受けた時は周のフォルダの写しのパス。
- ライブラリの文書を手元の版と公式から取り、置き場と run をまたぐ控えに置く。網の切り替え `WORKS_LIBDOCS_WEB` → `libdocs.section` のまま（控えの根は place と `ports.shared_cache()`）。
- 2 往復目から、前の周の案のファイル・事前審査の指摘・答えの要る穴・閉じた項目と保留の項目・前の周の波及の一覧を名指す → 2.3 の 24。
- 形 replan で、直す項目ごとに承認済みの項目と申し出と裁定の文（字のまま）と、修正の段と同じ部品で切った項目の brief を名指す → 2.3 の 26。
- 前の周までの引き継ぎのメモを古い順に全部名指す・メモの無い周と読めない周を名指す → 2.3 の 14。
- 指示の材料を `brief-<n>.md` に書き、役に Read させる → 外す。prep が組んで `prompt` で渡し、組んだ字は place の `plan-writer-prompt-<n>.md` に残る（README の 5.2）。

### 6.4 受け付け（今の `plan-accept`）

5 節に全部を並べた（作業ツリーの比べを先に・形の崩れ・往復の答え・閉じた項目・狭めない案・推し・義務の無い単位・網羅・欄・依存・構造と世界の解・修正前の版のテスト・置く順と巻き戻し・halt・捨てた項目の trace・形 replan の照らしと事実の欄・網の回で諦める・控えが扱えない時）。どれも今のまま。

- `with: status_guarded: true`（Archon の状態の照らしと重なる git status の行は比べない）→ 受け付けの中の定数 `accept.status_keys("true")`。入力でなくした（いつも同じ値だった）。
- 出し直しの答えを前の答えと合わせる（形 plan は項目を unit_keys で、形 replan は丸ごと。`whole_plan` は一度立てば控えに残る）→ `src/take.py` の写し。
- 合わせた答えを控えに書く（次の出し直しを合わせる元）→ `rolekit.resubmitted` のまま。

### 6.5 出口（今の `plan`）

- 落ちない: 境の口と lib の import から先の誤りも捕まえ、標準ライブラリだけで返す → `finish` の fallback（4 節）。
- 返りの pointer の先がいつも在って空でない（`plan-fields.json`・`ripple.json`）→ 同じ。
- 単位ごとの深さ `depth`（`depth.decide_doc`。始めの記録の `thickness` と機械の確かめの有無）→ 外して line へ。この block は直す義務の単位の並び `owed` を返し、line が案の欄と段の表から決める（README の 1.2 の D・8.7）。
- 形 replan で諦めた時の項目ごとの諦めの行 → 同じ（`gave_up` と `replan-gave-up.json`）。
- `nothing_owed`・`ready` → `status`（1.2）。
- `require_ports`（この版より前に走った計画の返りを resume で受けたかを line が照らす）→ 外す。line の受け皿の照らしで、line の設計書が決める。

### 6.6 読んだ証拠（今の `plan-reads`）

- 修正案の役が、機械が渡したパス（`brief-*.md`・前の回の拒否の理由のファイル・方針の文書の写し）を読んだかを、隔離した設定のフックの記録から集めて周のフォルダに書く（受け付けの条件にしない。落ちない）→ 外す。訳: 役の会話を見分ける錨が「この周の `brief-*.md` を読んだ session」で（`reads.collect` の `own`）、指示を直に渡す形では読ませるファイルが無い。拒否の理由と方針の本文も指示に貼るので、読ませるパスが残らない。この証拠を読む物は工場に無い（`index_name` の読み手は `planfile`・`boardview`・`fixboard`・`judge_accept` の書き手だけ）。外すと決めた（10 節の 13）。

### 6.7 YAML の鍵

- 修正案の役と出し直しの役が同じ模型・道具・設定（錨）→ 同じ。
- 輪の `max_iterations: 20` と `fresh_context: false`・出し直しの役は修正案の役の後ろの層 → 同じ（1.3）。
- AI の node の `idle_timeout: 1728000000`（約 20 日。短い期限を置かない決まり E12 の形で、実際には期限として効かない）・`retry: {max_attempts: 2, on_error: all}`（E19）・読むだけの印（`mutates_checkout: false`・`sandbox`。E7）・`settingSources: [user]` → 同じ。
- `command: fix-plan` と `prompt:` の文 → `prompt: "$<prep>.output.prompt"`（README の 7.1 の 1）。

## 7 元の works と graphloops の同じ場面

- 元の works の `works/blk-plan/`（`blk-plan.yaml`・scripts の prep・accept・collect・converge・reads・ripple・snap、`lib/planblk.py`・`ripple.py`）は、独立設計・修正案・事前審査の 3 つの役と壁打ちの往復を 1 つのブロックに持っていた。工場は計画（`workflows/plan/`）と事前審査（`workflows/plan-review/`）のサブグラフに割り、往復を line の輪に移した（#75 `26d6f2b0`）。この block は計画の 1 周分で、往復の記録は line が持つ（README の形の直し 6）。
- graphloops の `prompts/review-loop/p2.fix_plan.md`（36 行）にあって、この block の形が違う物:
  - `adds`（新しく生まれる物と `canonical`）・`removes`: 工場はファイルの行 `files`（`op`・`symbols`・`home`・`considered`）に替えた（#622 `45e649f3`。考えの住処と退けた置き場を持たせ、canonical と kind の列挙をやめた）。この block も `files` のまま。
  - 前の周に人が通した狭めを 1 字も変えずに写す決まりと、判定者が名指した狭め `named`（`named_narrowings`）: 元の works にも工場にも無い（（未確認）: 意図して外した記録は見つからなかった。`git log -S named_narrowings` は何も返さない）。振る舞いを変えるので足さない。
  - 人の承認ノードの答えの記録（`record.process.human_items`）を材料に貼る: 工場は記録された方針の行の「承認ノードの人の答え: この役には渡っていない」にしている（案の直しの周も同じ）。（未確認）: 意図の記録なし。この block も今のまま。
- この block が両方より良く、残す物: 直す義務を問いの台帳から機械が数え、受け付けと材料が同じ述語を読む（#583 の寄せ）・works の欄（直し方の道・受け入れテスト・書き換えるテスト・範囲・整えの申告）と、それを修正の要求の正本にする（keep-essence の 3 の許しの出どころ）・承認ノードの項目の決め手と柵と推し・狭めない案を先に探させて受け付けが縛る・構造の目の行と世界の解の行と判定の処方への行ごとの答えを受け付けが縛る（keep-essence の 12）・項目の間の依存と循環の拒み・考えの住処の重なりの拒み・波及の一覧（変える名と消す名の当たり）・受け付けに拒まれた後の同じ会話での出し直し（#588）・周をまたぐ引き継ぎのメモ（#590 `bbe7cf9a`）・並行 PR の外した範囲（#699 `10535024`）・裏取りの申し送り・頭の深さの未知の種類・前の run の失敗の行・ライブラリの文書・案の直しで約束の欄が変わったかの事実を残す。

## 8 単独で呼ぶ

```sh
bin/works-factory workflow run works-factory-plan --cwd <対象> \
  --input judgment='{"units": [{"key": "stats.py mean: 分母が 1 少ない", "label": "block", "disposition": "do-now"}], "questions": []}' \
  --input units='[{"id": "stats.py mean: 分母が 1 少ない", "paths": ["stats.py"], "summary": "mean は 2 でなく 3 を返す"}]'
```

出力は `workflow get <run>` の `finish` の返り。2 周目を単独で回す時は、1 周目の `reply`・`plan` の pointer の先のパスと事前審査の返答のパスを `--input prior='{"round": 1, "reply": "<パス>", "fields": "<パス>", "review": "<パス>", "record": {…}}'` で渡す。始めの記録は要らない。

## 9 試験

### 9.1 standalone の筋書き（`workflows/plan/fixtures/`。どれも `exec-code: true` で AI の node だけを差し替える。筋書きは `expect: completed` と `reached` と指示の字だけを見る）

- `standalone.stubs.yaml`: 入力は `judgment`（開いた単位 1 つ。JSON の字）と `units` だけ。`plan-writer` の台本は項目 1 つ（`files` の `path` は使い捨ての木の根に在る `README.md` の modify。`tests/archon.py` の `TARGET_FILES`）。`reached: [intake, ripple-units, plan-prep, plan-writer, plan-accept, ripple-items, finish]`。`resolved-text-contains: {plan-writer: <2.3 の 2 の役の定義の md の一続きの字>}`。
- `nothing-owed.stubs.yaml`: `judgment` の単位が全部 label nit。`reached: [intake, ripple-items, finish]`（輪は `when` で飛ぶ）。
- `replan.stubs.yaml`: 入力は `ruling: [1]`・`judgment`・`prior`（`reply` と `fields` を値で。項目 1 つ）。`reached: [intake, plan-prep, plan-writer, plan-accept, ripple-items, finish]`（`ripple-units` は飛ぶ）。`resolved-text-contains: {plan-writer: <2.3 の 26 の REPLAN_ASK の英語の一続きの字>}`。
- `resubmit.stubs.yaml`: 出し直しの役の md を本当の prep で組んだと照らす筋書き。dry-run の輪は 1 周で、`$LOOP_PREV` は 1 周目に空なので、本当の `plan-prep` は出し直しにならない。そこでこの筋書きだけ `plan-prep` を `{prompt: "", resubmit: true}` で差し替え、`plan-fix-prep` は本当に走らせる（10 節の 9）。`reached: [plan-fix-prep, plan-writer-fix, plan-accept, finish]`。`resolved-text-contains: {plan-writer-fix: <3.3 の 2 の段落の英語の一続きの字>}`。受け付けは合わせる元の控え `candidate-plan.json` が無いので拒む。この拒否は 1 件目で網の 20 回に届かず、`done` は偽のまま（dry-run は `until_bash` を走らせず、輪を 1 周で終わったと見なす）。受けた案も諦めも無いので、出口は `status: failed`（訳 `NO_PLAN`）で、run は completed。`gave_up` になるのは網の回に届いた時と、拒否の控えそのものが読めない・書けない時だけ（5 節）。

### 9.2 `tests/blocks/plan/`

script を子のプロセスで回す。始めの記録の無い使い捨ての `ARTIFACTS_DIR` と git のリポジトリ（`stats.py` と `test_stats.py` を持つ）で、port の値だけを渡す。

- `test_shape.py`（今の `tests/workflows/test_plan.py::ShapeCase` から）: 入力の鍵がちょうど 1.2 の 22 個・`finish` の `output_format` がちょうど 1.2 の 15 欄で `anyOf` を持たない・AI の node が読むだけで隔離されている（`test_role_nodes_are_read_only_and_isolated`）・出し直しの役が修正案の役の後ろの層で、層がどれも node 1 つ（`test_resubmit_role_continues_the_writer_conversation`）・出し直しの役の型が修正案の役の型と同じ物（`test_resubmit_schema_is_the_writer_schema`）・役の型が lib の持ち主と同じ（`test_role_schemas_match_their_lib_owners`・`test_writer_files_schema_is_the_planmarks_owner`・`test_writer_output_carries_works_fields_and_gate_marks`）・輪の `max_iterations` が `rolekit.NET_AFTER`（`test_loops_give_up_in_the_body_before_max_iterations`）・AI の node の期限が 20 日で ほかに期限が無い・`$LOOP_PREV` を書く `with:` は `plan-prep` の `prev` だけ・`INPUTS_` を読む script は intake・prep（`prev`）・accept（`reply`・`fix_reply`）だけ・script が uv の読むだけの script（`test_scripts_are_read_only_uv_scripts`）・script の名が lib と重ならない・2 つの md の本文（断片を入れる前の `prompts/plan-writer.md`・`prompts/plan-writer-fix.md` の字）に「started in a new conversation」の字が無い（断片 `handoff` の「次の周の自分は新しい会話で起きる」と、事前審査が新しい会話で掛かるという文は、この役の会話のことでないので数えない）。
- `test_accept.py`（今の `tests/workflows/test_plan.py` の `AcceptCase`・`ReplanCase`・`ReplanWithoutPlanCase`・`OwedAnswersCase`）と `test_rounds.py`（`CollectCase`・`SurvivesCase`・`BriefCase`）。次の・`SurvivesCase`・`BriefCase` を、`start` の pointer を port に、`plan/r<k>/` を place の `r<k>/` に、`brief-<n>.md` を `plan-writer-prompt-<n>.md` に替えて写す）: 案の受け付け（受けた案のファイル・依存・網羅・義務の無い単位・欄の欠け・構造と世界の解の答え・狭めない案・推し・作業ツリーの動き・status_guarded の行・置けない時の halt・メモを置けない時の halt・控えが扱えない時・網の回の諦め・波及の一覧）・出し直し（最後の拒否と合わせた答えのパスが指示に入る・resume の回は全部の拒否が `{shared:rejected}` で入る・部分の出し直しが 1 回の形に合わさる・空の出し直しは前の答えを照らし直す・`whole_plan` が項目を消す）・形 replan（余分の項目と変えた key を拒んで直す・網の回の諦めで直さない・作業ツリーの動き・項目の brief を名指す・作業ツリーが動いた後も同じ構造の控えを読む・直す元の案のメモを名指す・案の外の ruling は役を起こさない・直す元が無い）・周（2 周目が前の周を受ける〔`prior` で〕・前の周のメモを古い順に全部名指す・メモの無い周を名指す・出し直しでメモを保つ・メモの無い返答が古いメモを消す・2 周目に独立設計が入らない・閉じた項目を変えたら拒む・変えた項目だけを返す・2 周目の拒否を数える・人に上げる構造の行でも ok・構造の目が落ちた印が指示に入る・`status` と `rejects`・0 件で役を起こさない・行き止まりで役を起こさない・読めない pointer を「無い」と読まない）・直す義務（答えた fork の出どころが義務に戻る・開いていない答えの出どころは行き止まり・無人の推しが唯一の単位を義務にする・保留の出どころの推しは保留のまま。`takes_push` の port で）・落ちない（lib が読めない時も intake と finish が約束の形を返す・半ば開いた周を使う・depends が配列でない問い）・指示（方針・地図・前の失敗が入る・方針の写しのパス・控えの根を渡す・方針も前の失敗も無い時はどちらの節も無い・構造の行・処方・役の頭・目録と台帳と見立て・リポジトリの行・外した範囲・ライブラリの文書・言語の 1 文が最後・仕様・単位の波及・paths の無い単位・形の違う前の失敗）。
- `test_steps.py`（今の `lib/tests/test_planfile.py` から、`src/steps.py`・`src/take.py`・`src/brief.py` に向けて写す）: `OwedCase`・`SlotsCase`・`CoversCase`・`ReplanErrorsCase`・`PrescriptionCase`・`RepoLineCase`（値の組み方に）・`BaseTestsCase`・`ConvergeCase`（`filled_units`・`splice`・`answer_gaps`・`revise_section` の値。`converge_record` の照らしは line へ）・`UnitsSectionCase`・`ReplanInputsCase`・`WorldRowsCase`・`PriorFailuresCase`・`VerifyNeighborCase`・`HeadDepthNeighborCase`・`RevisedFieldsCase`・`TakePlanCase`・`WholePlanTakeCase`・`ReplanModuleCase`・`ResubmitMergeCase`（`test_rules_name_the_whole_plan_field` は md の字 `{whole_plan}` と `WHOLE_PLAN` の照らしに）・`RippleItemsCase`。`RoundCase`（周のフォルダを数える）は `prior.round + 1` の照らしに替える。
- `test_ripple.py`: 今の `lib/tests/test_ripple.py` の全部を `src/ripple.py` に向けて写す（`test_section_names_uncovered_and_asks_scope` は行の値の照らしに替え、頼みの文は md の照らしで見る）。
- `test_blk_plan.py` から写す物（`test_rounds.py` の `BriefCase`）: `ScriptCase.test_head_asks_no_narrow_first`（md に狭めない案の段落が在る）・`ConceptRuleCase.test_plan_head_has_concept_rule`（md に考えの住処の段落が在る）。`ReviewHead…`・`DesignReadCase`・`QuoteFoldCase` は事前審査の物で写さない。
- 写さない試験: `ShapeCase.test_writer_command_reads_only_its_prep`・`test_fix_plan_command_is_the_original_with_only_the_allowed_edits`・`CopiedTextsCase`（写しの台帳。README の 9.4）・`test_composed_block_declares_no_run_owned_keys`（`start` が無い）・`test_reads_roles_are_the_role_nodes_by_their_tools` と `ReadsCase` の全部（読んだ証拠の node を外す。6.6）・`test_fallback_names_match_lib`（出口の字の写しは `src/steps.py` 1 か所になる）・`CollectCase.test_depth_follows_start_thickness_and_checks`（深さは line へ）・`FixtureCase`（block の筋書きの照らしは README の 7.1 の 4 と 11.2）・`test_blk_plan.py::RejectHeadOwnerCase`（拒否の頭の住処は `src/steps.py`）。
- `tests/blocks/shared/test_ports.py` に `shared_cache` の試験（`STATE_DIR` が在れば `<STATE_DIR>/works-factory`、無ければ None）を足す。
- 足す: `test_rounds.py` に、intake が値で受けた `judgment` と `prior` の欄を周のフォルダに写し、そのパスを指示に名指す試験・2 つの include の place が分かれ、往復の輪の回をまたいで前の周のフォルダが消えない試験・`status` の 5 つの語がそれぞれの道で出る試験・`owed` が判定の順の直す義務の単位である試験。

### 9.3 英語の md が残すべき今の指示（審査が 1 つずつ照らす一覧）

指示の比べは審査が古い指示と新しい指示を並べて見る（作り手は英語の md を直に書き、日本語の字の一致の試験は作らない）。次の決まりが英語の md（と共通の断片）に意味を変えずに在ることを、1 行ずつ照らす。

- `fix-plan.md`:5-8: 直した後でしか見ていなかった・修正が次の穴を作った実測（2026-09-24、3 周目の指摘 8 件）・書く前の案を別の目に叩かせ、予測された穴を取り込んでから書く。
- `fix-plan.md`:12: 直す義務の単位を全部どれかの項目に入れる・入れてよい/入れてはいけないの正本・1 つの項目で複数の単位を閉じてよい（一撃の原理）。
- `fix-plan.md`:15-25: `unit_keys` は no で指し key を写さない・`approach` は関数・欄・文書の名で具体的に・`files` は新しく生まれる物を全部 1 ファイル 1 行・`op` の 4 語と rename の `from`・`responsibility`・`symbols` の `name`（パスや拡張子で終わる字を書かない）と `change`・新しく生まれる物の見本の並び・`home` と `considered`（1 件以上・`why_not` 10 字以上）を op を問わず全部の行に・書き落とした物は審査されない・消す物は delete/rename と remove の symbol・消す側の `why`（10 字以上）と `replaced_by`・足す側に `why`・`replaced_by` を書かない・`shrink_first`（足さずに閉じる形を先に。柵を足す直しは次の指摘の種）・`narrows`（BASE の能力が消える・狭まる物を全部・基準は観点の正本の移行退行の棚卸し・反復の速さ・デバッグ手段・観測・既定の安全装置も能力・1 件でも書けば修正の前に人に聞く・代償として採るかを自分で決めない・書き落とせば審査が後退として挙げる）。
- `fix-plan.md`:27: まだ手を動かさない。
- `planblk.HEAD["plan"]`: 読むだけ・道具・作業ツリーを 1 字も変えない（受け付けが写しと比べる）・schema に合う JSON だけ。
- `planmarks.HEAD`: works の欄の全部（`route` の 2 語と `route_why` の 10 字・`tests` の欄と id の形・赤の数え方〔宣言した名の失敗だけを赤に数える〕・既存のテストの置き方に合わせる・`rewrite_tests` の欄と期待値を実装に合わせる書き換えを書かない・`refactor`・承認された案が修正役の要求の正本になる〔名は出さずに「the fixing step」〕・名指さない既存のテストは変えられない・`allowed_paths`〔glob の形・テストのファイルは範囲に入る・移す/消すファイルの元のパス・付いてくる文書・丸ごとの許しを拒む〕・`out_of_scope`・`files` の 5 つの照らし・機械が差分で名を探す・消す物の `why` と `replaced_by`・消す名を名指すファイルを `allowed_paths` に・`depends_on` の書き方と拒まれる物・`structure` の 3 種の答え〔構造の目の行・処方・世界の解の行〕と 20 字・出どころの書き方と run の置き場のファイルは絶対パス:<行>・答えていない行は拒まれる）。
- `planblk.ITEMS_RULE`: 項目をまとめるのは同じ根・同じ行か塊の時だけ・依存する直しは分けて `depends_on`・同じファイルの別の所だけではまとめない・一撃の原理は根を共にする単位の話。
- `planblk.REUSE_RULE`: 新しい機構を足す前に触るファイルと兄弟を Grep で探す・在れば使う・新設するなら `considered` に当たった物と退けた訳（当たらなければ探し方）・新しいモジュールは op=create の行・書いていない新設は審査が挙げる。
- `planblk.TARGET_TEXT_PLAN`: 記録された方針に無い対象の文（コメント・docstring・テストの説明）は持ち主の決めでない・`out_of_scope` の why と `decided_by` に使わない・食い違うなら書き換えを案に入れる。
- `concepthome.PLAN_RULE`: 判断の 1 軸（目的・守る仕組み・簡潔さは考えを知る場所の数）・考えの住処を先に探す（地図の節・README・モジュールの境・同じ語の定数）・住処を変え写さない・新しい所に知らせるなら `considered` に住処の行・住処の無い考えは既に知る所に寄せる。
- `gatemarks.HEAD["p2.fix_plan"]` の 1 段落目: `decided_by` の出どころの 5 種と、対象の同じ場面にコメントの意図を含めない・記録された方針の名指しを字のまま・機械が現物を照らし照らせない行は人に回る・run の置き場のファイルは絶対パス:<行>・`undecided_because`（書けないなら空）・`fences` の 5 語・聞かずに通る行の条件の全部（決め手・柵なし・現物・世界の解の軸・構造の目・単位の外を名指さない）と出どころつきで報告に並ぶ・人に回す前に世界の解の行を使い、無い問いだけ自分で標準・著名 OSS・公式を引く・依頼の解き方は決め手にならない・定石で決まるなら自分で決める・どの行にも `world`・人に回す行には `recommend`（2 語・note と why の 4 字）・無人の run では推しが全部通すなら通り、note が修正への一言になり、止めるなら次の run の答えの下書きになる。
- 同 2 段落目: 狭めない案を先に当たる（直したい場合だけに新しい動き・当てられない場合は BASE の動きを残し黙らずに名指す）・在れば narrows に書かない・無い時だけ `no_narrow`（20 字以上）・欠けと短さは拒まれ、承認ノードの項目にそのまま載る。
- `planblk.head` の並行 PR の行: 触らず単位に入れない・先に Read・ほかの PR が扱う。
- `carry.PRIOR_HEAD`・`REDESIGN_HEAD`: 受け付けの拒否の行は直す穴でなく同じ所で落ちない注意・作り直しの行は直す穴でこの周の先頭で直す。
- `policy.RECORDED_RULE`・`RECORDED_NONE`: 出どころは 4 つと無人の推しだけ・対象の文は方針でない・食い違う対象の文は書き換える・方針とぶつかると言う時は名指しを字のまま写す（機械が照らし、当たらなければ拒む）。
- `concepthome.MAP_FOUND_HEAD`・`MAP_NONE_HEAD`・結び: 先に Read・審査するファイルを含むフォルダの地図を正とする・無い時は探した形と読めなかった訳。
- `handoff.ASK`・`HEAD`・`USE`・`NONE`・`UNREADABLE`: report.md の 2.3 の断片の本文で照らす。
- `planfile.UNITS_HEAD` と義務の札・`FILLED_LINE`・入れてはいけない単位・構造の目が見ていない単位・問いの台帳（fork の出どころ・depends の単位は待ってよい）・見立て・先行例。
- `planfile.REPO_LINE`: リポジトリ・読む版・BASE・観点の正本。
- `planblk.PRESCRIPTION_HEAD`・`PRESCRIPTION_ASK`・`PRESCRIPTION_SOURCE`: 処方を採る・採らない処方は `structure` に `{prescription, deviation}`・処方の関係と条件を黙って落とさない・決め手に挙げる時は判定の記録の絶対パス:<行>。
- `structmark.PLAN_HEAD`・`PLAN_ASK`・`PLAN_NONE`・`PLAN_CLEAN_HEAD`: 汚れる行の単位を持つ項目は行ごとに従うか訳・汚れない行に答えると拒まれる。
- `worldmark.HEAD`・`PLAN_ASK`: 答えの要る行は行ごとにどれかの項目が従うか訳・答えていない行は拒まれる・依頼の解き方は疑う案で決め手でない・依頼を出どころにした外れは修正の前に人に回る・web で確かめていない行も同じに答える。
- `ripple.UNITS_HEAD`・`HEAD`・`SCOPE_ASK`・`COMMON_NOTE`・`ERROR_NOTE`: 案を書く前に読む・覆っていない当たりの定義・直しが触る物は `allowed_paths` か `rewrite_tests` に入れる・案に入れた物は相談なしで書ける・範囲の外は相談しか無い・触らない物は入れない（審査が当たりごとに確かめる）・多い名は数だけ・作れなかったら自分で引く。
- `planblk.VERIFY_HEAD`・`VERIFY_ASK`: 単位は義務で申し送りでは減らない・根本でないと出た単位も外せない（拒まれる）・本当の根の項目にまとめるか `approach` に答え・重複・同じ所の関わり・順番は項目の組み方に・別の所の関わりではまとめない・確かめられなかった単位は判定のまま。
- `headdepth.UNKNOWN_HEAD`・`ASKS`・`NO_KINDS`: 2.3 の 22 の断片の本文で照らす。
- `planfile.SPEC_HEAD`: 受け入れテストはその単位を持つ項目の `tests` に入れる。
- `planfile.PRIOR_HEAD` と前の周の 2 行: 前の周の案を Read で読む・閉じた項目は変えない・指摘を受けていない時はそう名指す。
- `converge.REVISE_ASK`・`CLOSED_ASK`・`NOTES_HEAD`・`HELD_NOTE`・`OWED_HEAD`: block ごとに fixed か disputed と how を `block_answers` に 1 行（key を変えない）・変えた項目の行だけを返す・閉じた項目は書かない・変えない開いた項目と保留の項目は書かなくてよい（機械が差し込む）・fixed と答えた block の項目は変えた行を返す・答えの要る suggest にも 1 行・suggest は止め時に数えない・直した案は新しい会話の審査に掛かり、中央の block が残れば修正の前に止まる・端だけなら先へ進み申し送られる・参考の suggest は答えなくてよく項目を開き直さない・保留の項目は直さなくてよい。
- `planfile.POLICY_PART`（共通の断片 `policy` で照らす）: 方針は発行者が守らせる制約・方針に照らして案を書く・反するものを自分の判断で通さない・どの項とぶつかるかを書く・方針の文書を書き換えない。
- `replan.REPLAN_ASK`・`ITEM_HEAD`・`OLD_HEAD`・`ROW_HEAD`・`NO_ROWS`: 貼った項目だけを直す・申し出と裁定の文を読み裁定が名指した所を直す・同じ数・同じ順・`unit_keys` を字のまま・`depends_on` の unit も字で・ほかの項目を返さない・直した項目は審査に掛かり、約束の欄を変えると承認ノードに出る。
- `planfile.UNREAD_INPUTS_HEAD`: 読めなかった入力の節はその材料に無い。
- `rolekit.LANG_RULE`: 人が読む欄の言語・key・enum・識別子・パス・コマンド・誤りの文はそのまま・key は周をまたいで照らすので訳さない。
- `rolekit.RESUBMIT_ASK`・`planfile.RESUBMIT_RULES`・`REPLAN_RESUBMIT_RULES`（3.3）: 会話の続きで拒まれた所だけ・材料とリポジトリは読み直さない（拒否の確かめに要る所だけ）・拒否の理由は字のまま・合わせた答えの全体のパス・返さない所はそのまま残る・直す欄だけを書く（直さずにファイルだけ直したなら `{}`）・合わせた後に全体をもう 1 度照らす・`plan` の項目の合わせ方の全部・`block_answers` と `handoff` は全部を返す・`whole_plan`・形 replan は貼った項目の全部を貼った順に。

### 9.4 keep-essence

- 3（テストの凍結と許す道は 1 本）: この block は許しの出どころの 1 つ（承認済みの案の `rewrite_tests`・`allowed_paths`・`tests` と、案の直しで直した項目）を作る。守る試験は `test_accept.py` の受けた案のファイル（`plan-fields.json` の欄が `planmarks.split` の形）と、形 replan の `amended` と `contract_changed`。許しの数え（`test_permits`）は fix の試験。
- 12（世界の解に照らす）: 修正案は定石ごとに従うか外れの訳を書き、欠けは受け付けが拒む。守る試験は `test_accept.py` の `test_world_row_needs_answer` の写しと、md に 9.3 の `worldmark.PLAN_ASK` の行が在ること。依頼を出どころにした外れを人に回すのは事前審査と line。
- e2e の `tests/e2e/evidence.json` の P で始まる計画の行（P030 など）は、node の id と place のパスを新しい物に合わせる（組み込みの時）。

## 10 根拠を書いて自分で決めた事

1. port を 22 個にする（README の 8.2 は `judgment`・`purpose`・`structure`・`world_rows`・`spec`・`policy`・`prior`・`ruling`）。根拠: 今の計画は目録・結び・素材の状態・依頼の答え・無人の方針・裏取り・外した範囲・頭の深さ・決着済みの論点・前の失敗・申し出と裁定・3 つの版・言語を読んでいて、どれかを外すと材料の節か直す義務の数えが落ちる（6 節）。`purpose` は持たない: 今の計画の役は目的の文を受けていない（`write_brief` に無い）。足すのは振る舞いの変更になる。README の 4.2（作り手の欄を 3 つ以上読むなら pointer 1 つ）には当てない: 作り手が根本の診断・判定のまとめ・裏取り・並行 PR・頭の深さ・突合・世界の解・構造の目・仕様・修正・line に散っていて、1 つの作り手の欄を 3 つ以上読む所が無い（根本の診断の出力の形がまだ決まっていない。決まって 3 つ以上を読むなら、その時に 1 つの pointer に寄せる。11 節）。
2. 前の周は port `prior` 1 つで、往復の記録 `record` を line が組んで渡す。根拠: README の形の直し 6（往復の記録は line、block は前の周を port で受ける）。今の `planfile.converge_record` は周のフォルダを数えて組んでいたが、include ごとに place が分かれるので、案の直しの周（別の include）は承認済みの案を名で開けない。前の周の pointer を port で受ければ、どちらの形も同じ道になる。
3. 周のファイルを place の中の `r<k>/` に分け、前の周のファイルと指示の記録を消さない。根拠: 往復の輪の回をまたいで place が同じ（include の道は輪の id を含まない。README の 13 章）。前の周の `prior` の pointer の先を消すと、次の周が読めない。README の 13 章の「入口は自分が名を持つファイルを消す」は、今の周のフォルダの中だけに当てる。
4. ライブラリの文書の節（`libdocs.section`）は材料の行だけを lib が返し、見出しと指示の文は md `prompts/parts/lib-docs.md` が持つ（#764 で出した）。案の直しの項目の brief（`planbrief.render`）の行は lib が組む材料のまま入れる（brief ファイルの見出しと行から指示の語尾を外し、読み方は fix の `brief.md` が持つ。#764）。
5. 方針の文書は共通の断片 `{shared:policy}` で本文を貼る（今は置き場を名指して「先に全部読め」）。根拠: 方針を受ける全部の block が同じ断片を使う（independent-design.md の 2.3）。今の役も全部を読めと言われていたので、受け取る中身は同じ。上限を越えた分は続きのパスを名指す（`policy.brief`）。記録された方針の行の「元の置き場」は port に無いので `none` と書く（名指しの字は写しのパスで、受け付けの照らしは今と同じ）。
6. 単位の目録の形は plan の `schemas/unit-catalog.schema.json` に置く（structure の `units.schema.json` と同じ形）。根拠: 作る時の main の決まりは、block が消してよいのは自分の名のファイルだけ（形のファイルの名は pack の中で 1 か所、README の 7.1 の 5 なので、同じ名を `.shared/` に置くには structure の側のファイルと YAML と src を直す要る）。2 つの block が同じ形を持つ状態は組み込みで `.shared/schemas/` の 1 つに寄せる。
7. `ports.shared_cache()` を共通の口に足す。根拠: Archon の `STATE_DIR` を解く所は `.shared` の口に置く決まり（`workflows/.shared/AGENTS.md` の「`.shared` と `lib/` の分け」）。今の `boundary.shared_cache` の写しで、ライブラリの文書の run をまたぐ控えを今と同じに使う。
8. 下流の node の名と振る舞いの名指しを md から外し、役が書く欄の効き目は名を出さずに残す。根拠: README の憲法の 3（block はほかの block を名指さない）と world の 3.6 の同じ決め。ただし `decided_by`・`recommend`・`narrows` を書く理由は効き目（人に聞かれる・聞かずに通る・拒まれる）なので、それを消すと役が欄を書く手掛かりが落ちる。world は効き目を変えない 1 文だけを消した。
9. 出し直しの役の指示を組む prep を `plan-fix-prep` として分け、その md を照らす筋書きだけ `plan-prep` を差し替える。根拠: 形の検査（README の 13 章「どの AI の node も、prep を差し替えない筋書きのどれかで reached に在る」）は node ごとに prep を見る。dry-run の輪は 1 周で `until_bash` を走らせず（`dry-run.ts` の `simulateLoopGroup`）、`$LOOP_PREV` は 1 周目に空なので、本当の `plan-prep` が出し直しを選ぶ筋書きは書けない。出し直しの役の prep（`plan-fix-prep`）は本当に走るので、その md を組めることは照らせる。1 波目の学び「筋書きは AI の node だけを差し替える」の外し。層は全部 node 1 つのまま（1 波目の学び 2）。
10. `status` を返し、`ready`・`nothing_owed` を替える。根拠: README の 4.1（`outcome_field:` と、仕事の結果を語で返す形。world の `status`）。今の line は `ready` と `nothing_owed` と単位の有無から「計画が諦めた」を読み分けていた（`outcome.plan_gave_up`）。語にすれば line が読み分けずに済む。
11. 単位ごとの深さを返さず、直す義務の単位の並び `owed` を返す。根拠: README の 1.2 の D（段 → 回す物と単位ごとの深さは line）。line が深さを決めるには案の欄と義務の単位の並びが要り、義務の数えは問いの台帳を読むこの block に在る。
12. 頭の深さの指示を、行ごとでなく種類ごとに 1 回書く共通の断片 `unknown-asks` にする。根拠: 種類ごとの指示は決まった文で（憲法の 2）、行ごとに貼ると同じ文が行の数だけ繰り返す。行は種類の語を名指すので、役が引く指示は今と同じ。
13. 読んだ証拠の node `plan-reads` を外す（持ち主の決め済み。元の問い: 残すか）。根拠: 材料（拒否の理由・方針の文）を指示に直に貼るので読むファイルが無く、「役が材料を見た」は形そのもので保たれる。この証拠を読む物は工場に無い（6.6）。
14. 名と、標準ライブラリだけの落ちない道は `src/files.py` に置く（設計書は `src/steps.py` だけと書いた）。根拠: `steps.py` は lib の import を持つので、lib が読めない時に intake と finish の fallback が同じ字を使えない。independent-design・spec の `files.py` と同じ分け。`steps.py` は `files.py` を import する。
15. 周を開く途中で落ちた周は `round.json` に `error: true` を足し、出口が `failed` と読む（`held` との見分け）。
16. 波及の一覧の行の関数（`ripple.units_rows`・`rows`）は、誤りの時と一覧が空の時に空の字を返し、誤りの訳は呼び手（`brief.py`）が `doc["error"]` から口 `{ripple_units_error}`・`{prior_ripple_error}` へ渡す（設計書の 1.5 は行の関数が訳も返すと読めた）。
17. 判定を値で受けた時の写し `judgment.json` のパスを、処方の段落の口 `{judgment_file}` にいつも渡す（今のコードは判定のファイルが無ければその行を出さない。形 plan では判定が必ず在る）。
18. 指示の結びの「出力の schema に合う JSON だけを返す」は、2.6 のとおり結びの 1 文に 1 回だけ（2.3 の 2 の役の定義には入れない）。
19. 共通の断片 `resubmit` の口は main に在る `{rejection}`・`{candidate}` を使った。`unknown-asks`・`recorded-policy`・`concept-map`・`prior-failures` は、この設計書の本文と口でこの PR が足した（他の設計書が別の名を決めていれば、先に入る PR に揃える）。
20. 周の番号は `files.next_round` が intake と intake の fallback で同じ式で決める（`prior` が読めれば `prior.round + 1`、空なら 1、空でないのに読めなければ在る周の一番大きい番号 + 1）。`current-round.json` は lib を読む前に書く。根拠: 落ちた周が前の周のフォルダを開き直すと、前の周の `reply.json`・`plan-fields.json`・`handoff.json`（`prior` の pointer の先）を消し、出口が前の案を ok と返す。出口は `error` の印を先に読み、`fields` があっても failed を返す。
21. 読めない `world_rows` は、形 plan でも形 replan でも役を起こさない（今の `planfile.round_inputs` と同じ）。
22. `prior.review` と `prior.handoffs[].handoff` のファイルが無い時は、読めない `prior` にせず「指摘を受けていない」「メモ無し」と読んで進む（今と同じ）。`reply`・`fields` が無い時は `prior` が読めない。
23. 前の周の修正案の役の返答 `prior.fix_plan` が null の時は、指示の「前の周の案」の行を出す段落 `prior_fix_plan` を偽にし、欄 `prior_fields` の行だけを出す。
24. 受けた案の控えを置けない周（halt）は、機械の故障として出口が `failed` を返す。`gave_up` は役が回数を使い切った時だけ。
25. 拒否の控えが扱えない周（rolekit が読めない・書けない）も機械の故障として出口が `failed` を返し、訳に「拒否の控えが扱えない」を含める。24 と同じ決めで、`gave_up` に残っていた最後の 1 件。

## 11 未確認

- 共通の断片 `resubmit` の口の名が、test-gate.md（`{rejection}`・`{candidate}`）と spec.md（`{resubmit_reason}`・`{candidate_file}`）で割れている。先に足した PR の名に揃える。この block は作る時に在る断片の名を使う。
- 共通の断片 `unknown-asks` は diagnose の設計書と同じ本文・口にする必要がある（2 波目で同時に書く）。食い違えば、先に作る PR の物に揃える。`recorded-policy`・`concept-map`・`prior-failures` も、plan-review・diagnose の設計書が別の名を決めていれば揃える。
- line が書く `prior` のファイルを、事前審査の port `prior` と同じ 1 つにできるか（line の設計書で決める）。
- 根本の診断の出力の欄が決まった時、`judgment`・`units`・`answer_ties` を 1 つの pointer で受ける形（README の 4.2）に寄せるか。
- 波及の一覧の読み口（`ripple.uncovered`・`item_text`）は事前審査も読む。README の 9.2 は `ripple` を plan へ MOVE とするが、2 つの block が読む行の形なら `lib/` の行の形のモジュール（README の 4.1）に置く方が合う。plan-review の設計書で決める。
- 人の承認ノードの答えを修正案の役（特に案の直しの周）に渡さない今の形が意図か（7 節。graphloops は渡す）。
- dry-run が include の中の輪の本体の node に include の道を渡さない（README の 13 章）ので、line の筋書きでこの block の輪の本体を走らせると place を取り違える。line の筋書きは本体を差し替える。
- `prompt:` に入る指示の大きさ（例の run の材料は 63 KB。Archon の出力の大きさの上限に当たらないか。README の未確認の一覧と同じ）。
