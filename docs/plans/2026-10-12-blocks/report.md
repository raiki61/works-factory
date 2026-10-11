<!-- coldwrite:skip ASF の役が読む作業の計画（issue の本文）。語は works-factory の docs/design.md の「語」の節で定義 -->
# report: 報告のブロックを中身ごと作る（workflows/report/ と、それだけが使う lib/ の部品と試験）

works-factory は、修正依頼を受けて確かめ済みの変更と報告を返す工場を、Archon（AI の工程を YAML で書いて回す道具）の上に作り直しているリポジトリ。前の形の「今の works」（公開リポジトリ raiki61/claude-plugins の `works/`。移す元の版は `pack.json` の `works.commit` = `2aa7c66cf7abe1fe09699ac2942d107123214168`）は、判定・計画・修正・確かめ・報告をつないだ工場で、その能力を 1 つも落とさずに、線（`workflows/line/`。ブロックを並べる 1 本の工程）・8 つのブロック（`workflows/<名>/`）・助け手（`lib/`。Archon を知らない Python）に移している。この issue は、そのうちのブロック `report` を、フォルダの中身ごと 1 つの PR で作る。8 つのブロックは別々の run で同時に作られ、線とはブロックの返りの約束（`docs/design.md` の「ブロックの返りの約束」）だけでつながる。元のファイルは `https://raw.githubusercontent.com/raiki61/claude-plugins/2aa7c66cf7abe1fe09699ac2942d107123214168/<パス>` で読める（本文の「元」の欄の `<パス>`）。ASF は Archon の作者が作った、issue から PR までの工程の束（`docs/design.md` の「語」）。

## 読む物

- 根の `AGENTS.md`（リポジトリの形・E8〜E11・E13・E14・E18）、`workflows/AGENTS.md`（E1・E2・E4〜E7・E12・E16・E17）、`lib/AGENTS.md`（E3）、`tests/AGENTS.md`。決まりの番号 E1〜E18 の中身はそれらの文書に在る。
- `docs/design.md`: 「ブロック」の `report` の節・「ブロックの返りの約束」の `report` の返り・「能力の棚卸し」の `report` の行・「受け入れの一覧」・「Archon の分かっていること」と未決 U1〜U8・「作りの順」の段 2 の `report` の個別の行。
- `docs/plans/2026-10-12-lib-port.md` の「移し方」1〜6（この issue で `lib/` に持ってくる部品も同じ移し方に従う）。
- `docs/owner-decisions.md` のうち本文が引く決め。
- Archon の振る舞いは、ASF と同じ Archon の源（`coleam00/Archon` の commit `d97d00ef15cce4b15d39e42635e4e86996ec1351`。持ち主の決め `archon-same-as-asf`）の文書 `packages/docs-web/src/content/docs/`（特に `guides/script-nodes.md`・`guides/authoring-workflows.md`・`reference/cli.md` の dry-run と `workflow test`）で確かめる。ASF の工程は同じ commit の `.archon/workflows/sdlc/`（本文の `W`）。
- このブロックの分:
  - 元の works: `works/.shared/core/report.py`（結末の 10 語 `OUTCOMES`・決め方 `decide_outcome` の docstring・機械の報告 `build`・`tdd_lines`・`freeze_lines`・次の依頼 `next_request`・前の失敗 `prior_failures`・費用 `cost_rows`）、`works/blk-report/`（`blk-report.yaml`・`lib/report_roles.py`・`commands/report-write.md`・`commands/report-write-cold.md`・`glossary.json`・`prompts/review-loop/report.md`・`prompts/review-loop/report.cold_check.md`・`prompts/COPIED_FROM`（台帳の手直しの 3 行）・`scripts/`・`fixtures/`）、`works/darkfactory/darkfactory.yaml` の 1307-1391 行（線の `report`・`reporting`・`result`）、`works/darkfactory/scripts/report.py`（入力の読み方・途中で終わった run の見分け）、`works/.shared/core/carry.py`（次の依頼と前の失敗の形）、`works/.shared/core/agents/cold-reader.md`（初見の読み手の前付け）、`works/docs/keep-essence.md` の 1・3・11、試験 `works/tests/test_report.py`・`test_report_head.py`・`test_report_cold.py`・`test_blk_report.py`。
  - Archon: `guides/authoring-workflows.md` の `outcome_field`（1714-1717 行）と費用の数え方（2004-2027 行）、`guides/approval-nodes.md`（関所の答え `{decision, text}`。98-111 行）、`guides/loop-nodes.md`（`loop_group`・`$LOOP_PREV_OUTPUT`）、`packages/workflows/src/exec-environment.ts`（script の節に渡る `LOG_DIR`・`WORKFLOW_ID`・`TYPED_ARTIFACTS_FILE`・`ARCHON_NODE_EXECUTION`）、`packages/workflows/src/logger.ts`（run の記録の行の種類と欄）、`packages/paths/src/archon-paths.ts`:950-952（run の記録 `<logsDir>/<run-id>.jsonl`）と `packages/workflows/src/executor.ts`:518（`logDir` は対象のプロジェクトの置き場の `logsDir`。工程を `--workflow-source` で読ませても変わらないので、script の節は `LOG_DIR` だけを頼りにする）、`packages/workflows/src/artifacts-index.ts`（型つきの成果物の一覧の形）。
  - ASF: `W/ship/scripts/outcome.ts`（どの道でも 1 つの返り）、`W/.shared/report.ts`:100-206（型つきの成果物の一覧の読み方と `errors` の注意）、`W/review/commands/review-synthesize.md`:18（include の頭と `loopGroupPath` で自分の分だけを数える）。

## 目的と引き継ぐ能力

結末の語（10 語）を決め、機械の報告と AI の報告を書き、段ごとの費用と時間を Archon の run の記録から作って載せ、文脈を持たない読み手に AI の報告の頭を確かめさせる。次の run への持ち越し（次の依頼・前の失敗の行）を書く。人の関所の答えと TDD の単位の行（引用と理由）を載せる。前の段が落ちても飛ばされても走り、型つきの成果物の一覧の `errors` を注意として載せる（`docs/design.md` の report の節）。

能力の棚卸しの行:

- 結末の 10 語 — `works/.shared/core/report.py` の `OUTCOMES` → `lib/report.py`（元の名。語の正本は返す節の `output_format` の enum）と、決め方 `lib/outcome.py`（新しい部品。下の「lib/ に持ってくる部品」）
- 報告と初見の確かめ — `works/darkfactory/darkfactory.yaml` の `report` 節・`works/blk-report/` → `workflows/report/`・`commands/report`・`commands/cold-check`
- 持ち越し — `works/.shared/core/carry.py` → `lib/carry.py`（lib-port で在る。このブロックは呼ぶだけ）
- 型つきの成果物の一覧を読む — 元に無い（`workflows/AGENTS.md` の E5。読む部品は report の中）→ `workflows/report/scripts/typed.py`

受け入れの一覧（review-graph の節）のうちこのブロックが持つ物: `report.human_items`（人が決めることを冒頭の直後の 1 か所に集める。今の works は頭を書く段を書き手に畳んだ）・`report.cold_check`（禁: 周の経緯・記録・差分。初見の読み手は道具を持たず、書き手の頭だけを読む）・`report`。

keep-essence の 12 のうちこのブロックが持つ物: 11（直す単位ごとの記録が報告に届く）・1 の後半（赤の失敗の引用と理由が単位の行に載り、人が見る）・3 の報告の側（TDD の輪を回していない修正の段は「凍結が効いていない」と言う）。

持ち主の決めのうち、このブロックの形を決める物:

- `report-on-stop`「2: おしは？」への推し「出す」: 止め札で止めた run も報告を出す。止め札は「次の人の関所で止めると答えた扱い」。止め札の錠のファイル（今の works の `halt.py`）は持ち込まない。
- `carry`「じゃあ大きく治して、とまっても無駄にならないようにあなたがフォローしたり」: 止まった run の差分も捨てず、残りは次の run の依頼へ運ぶ。
- `projection`「1: おしで」: 履歴から作れる値（費用・時間）は保存せず、読む時に作る。
- `run-cost`: 段ごとの費用と時間を報告に載せる。
- `cold-read`「あとはcoldwriteとかcoldreaderは全然入れてもらっていいよ」: 初見の確かめを入れる。
- `ask-shape`: 人に上げる行は初見に通じる形で、推しと捨てた案と代償を書く。
- `stop-by-rate`: 収束しなくても未収束のまま報告で締める（結末の語に `round_limit` が在る）。
- `beyond-diff`: 目的の外の所見を次の依頼の下書きへ機械で運ぶ。
- `decision-records`: run が人に聞いた答えも次の run に持ち越す。
- `one-launcher`: 周の鎖（`chain.py`）の置き場は未決なので、このブロックは持たない。結末の語は線の返りを通して読まれるだけ。

## 作る物

### ブロックのフォルダ `workflows/report/`

- `works-factory-report.yaml`（工程の名も `works-factory-report`。E9）。節は次の順:
  1. `facts`（`script: facts`・`runtime: uv`・`timeout: 1728000000`・`mutates_checkout: false`）: 26 の入力・型つきの成果物の一覧・run の記録を読み、結末と止めの語を決め、機械の報告・次の依頼・前の失敗を run の置き場の `report/` に書く。返り（ブロックの外へは出ない中の型）: `{outcome, ok, stop_reason, report, next_request, prior_failures, ai_go, facts_file}`（`report`・`next_request`・`prior_failures` は指し札か null、`facts_file` は書き手に渡す事実のファイルの run の置き場からの相対のパス）。
  2. `write-loop`（`loop_group`。`depends_on: [facts]`・`when: "$facts.output.ai_go == true"`・`max_iterations: 3`・`fresh_context: false`・`until_bash` は `accept` の `done` が true か・`timeout: 1728000000`）。中の節:
     - `write`（`command: report`・`model: sonnet`・`effort: medium`・`allowed_tools: [Read, Grep, Glob, WebSearch, WebFetch]`・`settingSources: [user]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`（元の `blk-report.yaml` の `report-write` の値）・`mutates_checkout: false`・`idle_timeout: 1728000000`・`output_format` は `{text, terms}`（元の `report_roles.TEXT_SCHEMA` と `TERM_SCHEMA`））。書き手は同じ会話で出し直す（元の `fresh_context: false` と同じ）。前の回の拒否の訳は `$LOOP_PREV_OUTPUT` か前の回の `accept` の返りで受ける（どちらが使えるかを Archon の `guides/loop-nodes.md` で確かめて決め、PR に書く）。
     - `cold-prep`（`script: cold_prep`・`mutates_checkout: false`・`timeout: 1728000000`）: 書き手の返答の頭（`report_roles.head_of`）と、その後ろに付く語の定義の節を返す。
     - `cold`（`command: cold-check`・`context: fresh`・`allowed_tools: []`・`settingSources: [user]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`（元の `report-write-cold` の値）・`model: sonnet`・`effort: medium`（`works/.shared/core/agents/cold-reader.md` の前付け）・`mutates_checkout: false`・`idle_timeout: 1728000000`・`output_format` は `{verdict: pass|redesign-needed, stops, guessed, decidable}`）。毎回新しい会話で、貼られた頭だけを読む（禁: 周の経緯・記録・差分）。
     - `accept`（`script: report_accept`・`mutates_checkout: false`・`timeout: 1728000000`）: 書き手の返答の `terms` の型（`report_roles._terms_problems`）→ 表のセルの書式（`report_roles.format_problems`）→ 初見の読み手の判定、の順に見る。通らなければ訳を返して書き手に戻す。3 回目（`report_roles.GIVE_UP_AFTER`）は受け取り、「初見の確かめを通っていない」（`report_roles.NOT_PASSED`）の印を付ける。受け取った本文・語・初見の判定・種類ごとの拒否の回数（`report_roles.count_rejects` の形）を run の置き場の `report/ai.json` に書く。返り `{done, ok, reason, kind}`。3 回の拒否と諦めの振る舞いは筋書きでは確かめられない（dry-run は `until_bash` を走らせず、差し替えは節に 1 つの値だけ）ので、`tests/workflows/test_report.py` が `report_accept.py` を子のプロセスで 3 回走らせて確かめる。
  3. `report`（返す節。`script: collect`・`mutates_checkout: false`・`timeout: 1728000000`・`depends_on: [facts, write-loop]`・`trigger_rule: all_done`）: `report/ai.json` が在れば AI の報告 `report/report-ai.md`（1 行目の来歴・通っていなければ `NOT_PASSED` の 1 行・書き手の本文・語の定義の節・機械の事実（`report_roles.MACHINE_HEADING` の下に機械の報告をそのまま））を書く。無ければ `report_ai` は null。`facts` の返りと合わせて約束の欄を返す。AI の報告を作れなかった時（輪が落ちた・飛ばされた）も機械の報告は返す（元の `collect` の「黙らない」）。**返す節 `report` は落ちない**（線は落ちた返す節の先へ進めない）: `collect.py` は中の誤りを全部捕まえ、`facts` の返りが無い・読めない時も含めて、`ok: false`・`outcome: record_invalid`（今の works の「記録が検証器を通らない（結果を名乗れない）」の語）・`stop_reason` に `report:` と訳の 1 行・`report` に訳と読めた分を書いた機械の報告の指し札（書けなければ置き場に訳だけの 1 ファイルを書いて指す）・ほかの指し札は null を返し、終了の値 0 で終わる。返りは返す節の `output_format` に合う。
  - 工程の頭: 工程の段の鍵 `interactive`・`worktree`・`container`・`evidence_policy`・`mutates_checkout` は書かない（include された時に読み込みの警告つきで落とされる。Archon の `guides/authoring-workflows.md` の「Composed behaviour」）。`name: works-factory-report`・`description`・`inputs:`（下の「返りの約束」の 26 の入力。全部 `default: ""`。飛ばされた段は線から字の `null` か空で届く）・`returns: report`・`outcome_field: ok`（人の直し H2（本文の「依存」） が入った後の約束。下の「返りの約束」）。人の関所と並べは無い（E16 の `interactive: true` は要らない）。
- `commands/report.md`（元 `works/blk-report/commands/report-write.md` と `works/blk-report/prompts/review-loop/report.md` に `prompts/COPIED_FROM` の台帳の手直し 3 行を当てた物を 1 本にする）: 書き手の役。今の works の書式の決まり（冒頭 3 行で完結・人が決めることを冒頭の直後の 1 か所に集める・初出で「中身→記号」・表のセルに文を入れない・推しは判定の役が書いた物だけ）は字のまま残す。盤面の穴（`{{record.*}}`・`{{loop}}`・`$report-write-prep.output.*`）は、`$facts.output.facts_file`（機械の事実。報告の最後に機械がそのまま付ける）と、そこに並ぶ指し札のファイル（判定・計画・事前審査・差分・目の結果）を Read で読む形に直す。「記録の process.*」に頼る行（判定から入った run・依頼のバッチ・方針の文書の変わり）は、機械の事実の節の同じ行を読む形にする。graphloops の周をまたぐ指示（全ラウンドの推移）は今の works の台帳の手直しのとおり外したまま。
- `commands/cold-check.md`（元 `works/blk-report/commands/report-write-cold.md` と `works/blk-report/prompts/review-loop/report.cold_check.md`）: 初見の読み手。本文の差し込みは `$cold-prep.output.<欄>`。
- `scripts/`（どれも頭で境の口と lib/ を読み、lib/ の関数を呼ぶだけ。確かめの中身を書かない。E4）:
  - `facts.py`: 下の「返りの約束」の 26 の入力を `INPUTS_<欄の名を大文字に>`（`INPUTS_START`・`INPUTS_TEST_GATE_BASE`・…・`INPUTS_STOP_REASON`・…・`INPUTS_REDEPTH`）で字のまま読む（空と字の `null` は None。JSON でない・オブジェクトでない時も落とさず None にし、読めなかった事実を `outcome.decide` に渡す）。`start` の指し札は `boundary.resolve` で開く（開けなければ None と訳）。型つきの成果物は `typed.read_listing()`、run の記録は `os.environ.get("LOG_DIR", "")` と `os.environ.get("WORKFLOW_ID", "")` から `<LOG_DIR>/<WORKFLOW_ID>.jsonl` を行ごとに JSON で読む（どちらかが空・ファイルが無い・読めない時は None と訳。`workflow test` の dry-run では `WORKFLOW_ID` が `dry-run` で記録が無いので、この訳になる）。自分の include の行を除くため `ARCHON_NODE_EXECUTION` の `path` を `.get` で読んで渡す。その後 `outcome.decide_outcome(...)`・`runreport.build(...)` を呼び、`boundary.pointer` で指し札を組んで返す。**`facts.py` は 0 以外で終わらない**: 思わぬ誤りも捕まえて、結末 `record_invalid` と誤りの 1 行を `record_problems` に入れた機械の報告を書いて返す（落ちると線は報告の返りを受けられない。下の「Archon で書けない所」）。
  - `typed.py`（E5 の「読む部品は report ブロックの中」。節の script でなく、`facts.py` が import する部品）: `TYPED_ARTIFACTS_FILE` の一覧を読み、`{by_type: {型: [{include, loop, node, path, produced_at, body}]}, warnings: [文]}` を返す。`include` は `nodeId` の最初の `__` より前（無ければ空）、`loop` は `loopGroupPath` の `[(groupId, iteration)]`。include の名と型の名は決め打たず、一覧に在る物で組む。ほかの run の行（`runId` が違う）と自分の include の行は数えない。中身は `path` を run の置き場から読む。`TYPED_ARTIFACTS_FILE` が無い・空の字（`workflow test` の dry-run は空の字を渡す）・一覧が読めない・形が違う・`artifactsByType` の値が配列でない・中身が読めない、はどれも名前つきの限りとして `warnings` に入れ、読めた分と一緒に返す（ASF の `W/.shared/report.ts`:126-206）。一覧の `errors` は 1 件ずつ `warnings` に入れる（捨てない）。
  - `cold_prep.py`・`report_accept.py`（名を `accept` にしない。`lib/accept.py` を隠すため）・`collect.py`: 上の節の仕事。`report_roles` と `runreport` を呼ぶだけ。
- `fixtures/`（Archon の `workflow test` の筋書き。筋書きは配線だけを確かめる。dry-run では、承認の節は自ずと済み、`until_bash` は走らず輪は済んだと見なされ、差し替えは節ごとに 1 つの値、`exec-code` の節には空の `ARTIFACTS_DIR`・空の字の `TYPED_ARTIFACTS_FILE`・`WORKFLOW_ID=dry-run` が渡る（Archon の `reference/cli.md` の dry-run の節と `packages/workflows/src/fixture-runner.ts`）。拒否の繰り返し・書き手が落ちた時・止めの振る舞いは `tests/workflows/test_report.py` の子のプロセスの試験と lib/ の試験が持つ）:
  - `fixed.stubs.yaml`: 全部の節を差し替え、書き手が 1 回で通る。`expect: completed`・`reached: [facts, write, cold, accept, report]`。`report` の差し替えは約束の欄を全部持つ。
  - `no-ai-report.stubs.yaml`: `facts` が `ai_go: false`（`record_invalid` の run）。輪は飛ばされ、`report` は `report_ai: null` で返る。`reached: [facts, report]`。
  - `stopped-by-request.stubs.yaml`（`exec-code: true`）: `fixture.inputs` で `gate-final` に `{"decision":"stop","text":"request: 止め札"}`（人の直し H5（本文の「依存」） の印） を渡し、ほかの入力は空。`facts` と `report` の script が本当に走り、結末 `stopped_by_request` で返る（`resolved-text-contains` か `report` の出力で確かめる）。
  - `start-missing.stubs.yaml`（`exec-code: true`）: 全部の入力が空。`facts` が `record_invalid` を返し、輪は飛ばされ、`report` が返る。前の段が全部落ちても報告が出ることの確かめ。

### lib/ に持ってくる部品（このブロックだけが使う物）

lib-port の「移し方」1〜6 のとおり。外す物は機械で出した見込みで、一覧の外でも盤面・Archon・持ってこない部品（board・script_io・scopes・flow_adapter・entry・adapter・tree_run・fixture・rolekit・seat・nodemeta・ticket・replycontract・graphmap・node_marker・leftovers・versions・halt・chain、engine の board・advance・commands・validator・record・role_run・rules・declared）に届く物は同じに外して PR に足す。移し方 2 の「外した物にしか使われない名」は、この issue で新しく書く `lib/outcome.py`・`lib/runreport.py` から使われる名を消さない。

- `works/.shared/core/report.py` → `lib/report.py`
  - 外す物（見込み）: `OUTCOME_KINDS`（chain）・`line_graph`・`absorbed_falls`（graphmap）・`decide_outcome`・`residue`・`rest_outside_validator`・`stop_outcome`・`stopped_run`・`gate_record`・`trace_scan`・`trace_rows`・`next_request`・`next_doc`・`prior_failures`・`lens_next_items`・`head3`・`head_decisions`・`head_entry`・`head_stop`・`head_reads`・`head_where`・`head_models`・`head_cost`・`cost_rows`・`_live_launches`・`_launches`・`round_facts`・`declared_downgrades`・`build`・`final_result`・`final_gate_answer`・`handoff_lines`・`rejudge_lines`・`verify_lines`・`branch_rows`・`eye_ties`・`always_rows`・`anomalies`・`anomaly_lines`・`gates_lines`・`plan_ask_lines`・`inner_word_lines`・`fix_split`・`split_line`・`tests_word`・`eye_counts`・`Rest` ほか盤面（`b`）を受ける物の全部。続いて呼び手が外れて使われなくなる `_asked_units`・`split_fallen`・`carry_left`・`_validator_blockers` など（新しい部品が呼ぶなら残す）。import は `adapter`・`chain`・`changemap`・`cite`・`conflict`・`converge`・`design`・`diverted`・`impact`・`querytest`・`recount`・`replan`・`board`・`engine.rules`・`engine.validator`・`entry`・`fixture`・`forge`・`holeties`・`leftovers`・`lens`・`reads`・`refix`・`scopes`・`script_io`・`startrec`・`structmark`・`worldmark`・`writes`・`gatepolicy`・`outpurpose` が全部消える見込み。残る import は `carry`・`gatemarks`・`marks`・`promptsection`・`stopby` のうち残る名が使う物と標準だけ。
  - 残る見込み: `OUTCOMES`・`OUTCOME_WORDS`・見出しの `Section` の全部・`FOR_READERS`・`TDD_STAGES`・`FREEZE_OFF_HEAD`・`R2_REDESIGN`・`REQUEST_BY`・`HUMAN_BY`・`FINAL_GATE_STOPS`・`EYES`・`CHECKS_LEFT`・`EYES_WHERE`・`ABSORBED_WHERE`・`INTERRUPTED_HEAD`・`RETRIED_HEAD`・`ABSORBED_HEAD`・`AI_REPORT_KEYS`・`_one_line`・`_first_error`・`_r2_redesign`・`prior_lines`・`_time`・`_minutes`・`_tdd_unit`・`_red_evidence`・`_reused_line`・`tdd_lines`・`freeze_lines`・`_read_json`・`_write_json`・`_write_text`。
  - 言い換え（E3・E13・E14 に当たる字がコメント・docstring・人に見せる文だけに在る時。lib-port の移し方 4）: `ARCHON_VERSION = "Archon v0.11.1"`（今の works が使った版の字）はコードの値なので言い換えず、呼び手（`_event_cost`）ごと外れるなら外す。残るなら外して PR に書く。docstring の「Archon」は「実行基盤」に言い換える。
  - 中身の `COST_FIELD = ("spend", "costUsd")` は今の works が使った v0.11.1 の形で、止めた Archon（`docs/design.md` の「語」。d97d00ef）は `cost_usd`（`guides/authoring-workflows.md`:2004-2027）。元の中身は直さない（移し方 1）。新しい費用の読みは `lib/runreport.py` に書く。
- `works/blk-report/lib/report_roles.py` → `lib/report_roles.py`（今の works の `blk-*/lib/` の部品の置き場は lib-port の計画に無い。E3・E4 から lib/ に元の名で置く）
  - 外す物（見込み）: `route`・`prep`・`render`・`write_cold_prep`・`accept`・`collect`・`stamp`・`open_board`・`board_facts`・`facts_text`・`_note_invalid`・`_why_not`・`_read_json`（`BoardGap`）とそれに頼る `_pack_terms`・`glossary_section`・`_with_glossary`・`_run_terms`・`_cold_reply`・`_cold_block`・`_rejects`・`_reject`・`_keep_cold`・`_text_of`・`_file_of`・`_missing_reason`・`count_round_rejects`・`_reject_counts`・`script_main`・`output_format`・`_node`・`GLOSSARY`・`PROMPTS`・`COMMANDS` など盤面とブロックの置き場に届く物。頭の `sys.path` の行のうち `_CORE`（`.shared/core`）を足す行は、lib/ の中では自分の置き場なので残すか消すかを lib-port の移し方 1 に合わせて決め、PR に書く。import は `board`・`engine.rules`・`engine.util`・`accept`・`entry`・`node_marker`・`rolekit` が消える見込み。
  - 残る見込み: `_write_json`・`_count`・`_terms_problems`・`_snap_name`・`head_of`・`format_problems`・`count_rejects` と定数（`TERM_SCHEMA`・`TEXT_SCHEMA`・`GIVE_UP_AFTER`・`CELL_LIMIT`・`REJECT_KINDS`・`NOT_PASSED`・`DECISIONS_HEAD`・`MACHINE_HEADING`・`GLOSSARY_HEADING`・`FAILED_TITLE`・`REJECT_HEADING`・`CELL_REASON`・`WRITE`・`WRITE_COLD`）。
- `works/blk-report/glossary.json` → `lib/glossary.json`（部品のデータ。中身は元のまま。今の works の語「盤面」などは掃除の段で見直す）
- 新しい部品（元に無い。元の決め方と組み立てが盤面の上に立つので、移し方のままでは丸ごと外れるため。E18 の名の決まりに当たらない名）:
  （この 2 つは、決め方の行と盤面に届く能力の扱いの 2 つの形（継ぎ目の直し・書き直し）のうち「書き直し」に当たる: 盤面を読む関数を元の関数の名のまま、値とパスを引数で受ける形で、`docs/design.md` の能力の名の新しいファイルに書き直す。docstring に元の `<パス>:<行>` を書き、試験は元の試験の筋を写す。PR の本文に 1 つずつ並べる。偽の盤面は作らない。）
  - `lib/outcome.py`（`docs/design.md` の `lib/outcome`「決め方だけを持つ」）: `decide_outcome(returns: dict, gates: dict, facts: dict) -> tuple[str, str]`（元 `works/.shared/core/report.py`:670 の `decide_outcome` の書き直し。元は盤面 `b` と検証器の `gate` を受けた）。`returns` は include の id → 返りの dict か None、`gates` は関所の id → `{decision, text}` か None、`facts` は `{start_ok, record_problems, failed, retried, transcript_ok}`。返りは `(outcome, stop_reason)`。outcome は `report.OUTCOMES` のどれか。`stop_reason` は「止めた段と理由の語」で、止まらなければ `""`。形は `<段の id>:<語>`（語は関所の decision か `lib/stopby.py` の語）。順は元の `decide_outcome` の docstring の順を写す:
    1. 人の止め: 関所の答えのどれかの `decision` が止める語（`stop`・`reject`。`stop` は `lib/answer.py` の `VERBS` の語、`reject` は今の works の `report.FINAL_GATE_STOPS` の語）か、ブロックの返りの `stop_reason` が `report.HUMAN_BY`（`human:`）・`report.REQUEST_BY`（`request:`）で始まる（judge の中の仕様の関所の止めは judge の `stop_reason` で届く。judge の issue がその語を決める）: `text`（返りなら `stop_reason`）が `request:` で始まれば `stopped_by_request`、ほかは `stopped_by_human`。通す語は `approve`（Archon は `decisions` に `approve` を要る。`guides/approval-nodes.md`:98）と `continue` だけ。どちらの組にも無い `decision` は通しにも止めにも数えず、`facts.record_problems` に「知らない答えの語」と入れる（→ 4 の `record_invalid`）。関所の答えの語と止め札の印は 人の直し H5（本文の「依存」）。
    2. 返りの `stop_reason` が `stopby.is_line` の語で、人待ちの語（`stopby.CONFLICT`・`stopby.REPLAN`・`stopby.TDD_REPEAT`）でない、または `plan-review` の `stalled` が true（語は `stopby.PLAN_CONVERGE`）、または `plan` の `ready` が false で直す単位が在る（plan の受け付けが 3 回とも拒んだ諦めか、往復が進まない止まり。`stop_reason` は plan の返りに止めの語が在ればその語を `plan:<語>` で、無ければ `plan:give-up`。直す単位が無くて false の時は 6 の `no_fix_needed`。plan の issue の `ready` の意味と同じ）、または `merge-seal`・`merge-apply` の `ok` が false: `stopped_by_line`。
    3. 人待ち: `fixed` の `conflicts` に人に回した行が在る（入力 `fix` は 1 回目の修正の段の返りで、`conflicts` は指し札 1 つか null。1 回目と 2 度目の修正の段（`refix`）の申し出を合わせた物は入力 `fixed` の `conflicts`（段ごとの指し札の配列）に届くので、人待ちはそちらで数える。配列なら全部の先を読み、行を合わせて数える。元の `conflict.asked` の決まりを欄の名で読む: 行の `ruling.decision` が直す裁定（`fix_test_scope`・`fix_code_as`・`replace_query`）でも無しでもなく、行の `replan` の欄が `waiting`・`amended` でない行。ファイルの形は今の works の `conflicts.json` の包み `{"items": [<行>, …]}`（人の直し H5 の fix の `conflicts` の形）で、読む字（`items`・`ruling`・`decision`・`replan`・`fix_test_scope`・`fix_code_as`・`replace_query`・`waiting`・`amended`）を `lib/runreport.py` の定数に置く。`conflict.py` は import しない（同じ時に fix の PR が作るファイルで、このブロックの前には無い）。この字の写しは掃除の段で `lib/conflict.py` を引く形に寄せる物として PR の本文に書く）、返りの `stop_reason` が人待ちの語、`eyes` の `premise_check.verdict` が `escalate`、`plan-review` の `ask_human` が true なのに `gate-before-fix` の答えが無く `fix` も走っていない（無人の run が問いを残した）: `needs_human`。
    4. 結果を名乗れない: `start` を開けない・読めない（`facts.start_ok` が false）か `facts.record_problems` が在る: `record_invalid`。
    5. 途中で終わった: run の記録で最後の行が `node_error` の節が在る（`facts.failed`。自分の include の節は除く）。記録が読めない時は、返りの続きが切れている（`judge.ready` が true なのに `plan` が無い・`fix.done` が true なのに `test-gate-final` が無い など。止めの答えも線の止めも無い）: `interrupted`。
    6. 直す物が無い: `judge.ready` が false で `stop_reason` が `""`、または単位が 0: `no_fix_needed`。
    7. 残り（行の形は元の `rest_outside_validator` の `{where, text}`）: `test-gate-final` の `ok` か `green` が false・`eyes` の目のどれかの `status` が `redesign-needed` か `unverifiable`（今の works の検証器は確かめられなかった目を阻害に数えた。`works/.shared/core/scripts/review-record.py`:170-171）・`fix` の単位の `status` が `given_up` か `not_done`・`fix.done` が false・`fix.delta_review.pass` が false・今の周に測れていない素材の行（下）。R4 の `questions` だけは残りでない（人が決めることの節に出す）。残りが測れていない素材の行だけで `test-gate-final` が緑なら `fixed_needs_check`（元の `_unmeasured_row`。`works/.shared/core/report.py`:701-705）、ほかの残りが在れば `round_limit`。深さで省いた目（null）は数えない（`docs/design.md` の eyes の返り）。素材の測りの状態は、`judge` の `judgment` の指し札のファイルと同じフォルダの `materials.json`（約束の名指しの隣のファイル。形は `{<素材の名>: {status, …}}`。judge が止めた道では `{}`）の各素材の `.status` で読み、`not_run`・`awaiting_human` を測れていない素材とする（今の works の `gatemarks.unmeasured`。`works/.shared/core/gatemarks.py`:708-716）。ファイルが無い・読めない時は注意の行を出し、測れていない素材は無いと数える（judge の止めの道と同じ）。
    8. ほかは `fixed`。
    - 表の各行は元の docstring のどの語に当たるかを関数の docstring に書き、元と違う所（検証器の関所が無い・盤面の `pending_human` の代わりに返りを読む）を PR に書く。
  - `lib/runreport.py`: 機械の報告・次の依頼・前の失敗・費用と時間・語の定義の節を組む。
    - 元の名で書き直す関数（どれも元 `works/.shared/core/report.py` か `works/blk-report/lib/report_roles.py` の同じ名の書き直し。docstring に元の行）: `build`・`next_request`・`prior_failures`・`cost_rows`・`head_cost`・`glossary_section`。新しく足す関数は `transcript_facts` だけ。
    - `build(returns, gates, typed, transcript, outcome, stop_reason, *, out_dir) -> dict`: `out_dir` に `report.md`（`report.REPORT_FILE`）・`next-request.json`（`carry.NEXT_REQUEST_FILE`）・`prior-failures.json`（`carry.PRIOR_FAILURES_FILE`）・書き手に渡す事実のファイルを書き、パスと `ai_go`（outcome が `record_invalid` でない）を返す。次の依頼が空なら `next-request.json` を書かず None、前の失敗が空なら None。
    - 機械の報告の節（見出しは `report.py` の `Section` を使う。文は機械の定型だけ。AI は書かない）:
      1. 人が決めること: `plan-review.questions`・`eyes.questions`（R4）・`fix.conflicts`（指し札か指し札の配列）の人に回した行・`merge-seal.protected_hits`・`fix.allowed_test_changes`・`eyes.premise_check`（escalate）。0 件も「0 件」と出す。続けて、修正前の関所が人に聞かずに通した行（今の works の報告の頭が並べた物）: 入力 `plan-review` の `review` の指し札が指すファイルと同じフォルダの `gate-passes.json`（名はこの字ちょうど。人の直し H5（本文の「依存」） で約束に入る。plan-review のほかの隣のファイルは開かない）を読み、行ごとに出す。`plan-review` が飛ばされた（None）・指し札が無い・ファイルが無い・読めない時は「無い（訳）」の 1 行にして落ちない。案の直しの `replan-review` が在れば、その `review` の隣の `gate-passes.json` も同じに読む。
      2. 入口・段・決めた人: 始めの記録（`lib/startrec.py` の欄）・各段が走ったか飛ばされたか（返りが None の段の名）・`plan.depth` の深さ・`test-gate-base` の結末・`report.freeze_lines`（TDD の輪を回していない修正の段。段の物は上の TDD の節と同じ）。
      3. 止めたか: 結末の語と `report.OUTCOME_WORDS` の文・`stop_reason`・4 つの関所の答え（`{decision, text}`。飛ばされた関所は「開かなかった」）・落ちた節（`report.INTERRUPTED_HEAD`）・前の試みで落ちて後で済んだ節（`report.RETRIED_HEAD`）。
      4. 読んだ証拠: 未決 U6 のため「取れない（docs/design.md の U6）」と 1 行出す（黙らない）。
      5. 見る所: 返りに在る指し札（判定・目的・定石・計画・波及・事前審査・独立設計・差分・試験の記録・直した後の構造・封じた差分）を名と一緒に並べる。
      - TDD の輪の単位ごとの結末（`report.TDD_HEADING`。keep-essence の 11）: 型つきの成果物 `tdd-unit` の中身（人の直し H5（本文の「依存」）: fix が run に 1 つ出す成果物で、中身は組ごとの段の物の配列 `[{group_id, ran, reason, suite, reused, units: [<今の works の TDD の輪の単位の行>]}]`。今の works の修正のブロックの出口 `tdd` を組ごとにした物で、輪を回さなかった組も `ran: false` で載る）を、組ごとにそのまま `report.tdd_lines` と `report.freeze_lines` の段の物（`[(段の名, 段の物)]`。段の名は `report.TDD_STAGES` の語に組の id を添えた物）として渡し（中身を作り替えない。`works/.shared/core/report.py`:1961-1990）、赤の引用と理由（`red_quotes`）を載せる。案の直しの後の 2 度目の修正の段が在れば（include の頭か `loopGroupPath` が違う 2 つ目の成果物）、`report.TDD_STAGES` の 2 つ目の語で並べる。成果物が無く `fix` の返り `units` が在る時は、`units` の行（`unit_id`・`status`・`reason`）で出し、成果物が無い訳を 1 行出す。
      - 緑の認証（全部の周）: `green-cert` の中身（H5: test-gate の返す節 `result` の出力そのもの。`mode`・`ok`・`green`・`red_cause`・`fingerprint`・`evidence` ほか）ごとに、include の頭（base と final が別の頭）・緑か・赤の原因（`red_cause`）。`inherited`・`environment` の赤を通した物は「赤のまま通した」と名指す（ASF の `W/.shared/report.ts` の「Delivered on red」と同じ考え）。
      - 独立の目: `eyes` の `r1`〜`r4` と型つきの成果物 `eye-verdict` の中身（人の直し H5（本文の「依存」）: ちょうど `{eye, status, reason}`。`eye` は `r1`・`r2`・`r3`・`r4`・`premise-check`、`status` は eyes の返りと同じ語。eyes は目ごとの小さな script の節から出す）。読むのはこの 3 つの欄だけで、形が違う中身は注意の行にする。省いた目は「深さで省いた」。
      - 世界の解（`report.WORLD_HEADING`）・判定が目的の外とした所見（`report.OUTSIDE_HEADING`）: `judge.world`・`judge.out_of_purpose` の指し札の中身を `lib/worldmark.py`・`lib/outpurpose.py` の読み口で行にする（読めなければ訳を 1 行）。
      - 費用と時間（`report.COST_HEADING`）: run の記録の行から、節ごとの費用（自分の費用を報告する行の `cost_usd` の和。`data.aggregate` などの言い直しの行は数えない。Archon の `guides/authoring-workflows.md`:2004-2027 の数え方を行の欄の実物で確かめて書く）と時間（`node_start` から `node_complete`・`node_error` まで）。費用の無い行は 0 と数えず件数と訳を出す。記録が読めなければ「取れない（訳）」の 1 行。保存しない（読む時に作る。持ち主の決め `projection`）。
      - 模型（`report.MODEL_HEADING`）: 記録の行に模型の欄が在れば節ごとに出す。無ければ「記録に模型の欄が無い」。
      - 注意: 型つきの成果物の読みの `warnings` を 1 件ずつ（E5。捨てない）。
    - 次の依頼（`carry.compose(findings, prior, drafts)` の形）: findings は残りの行（`{where, text}`）・`fix` の諦めた単位・判定が目的の外とした所見（`outpurpose` の次の依頼の行）・答えを待つ問い（無人の run が残した `plan-review.questions` など。`carry.draft(row, source)` で下書きの印を付け、人が見直すまで次の run の目的にならない）。prior は前の失敗。書く時は `carry.errors(doc, carry.NEXT_SCHEMA)` が空であることを確かめる。
    - 前の失敗: `eyes.r2.status` が `redesign-needed` の訳（`carry.REDESIGN_WHERE`。持ち主の決め `small-core`）と、受け付けを最後まで通らなかった物（`fix` の諦めた単位の理由）を `[{where, text}]` で。`carry.PRIOR_SCHEMA` で照らす。
    - `glossary_section(text, terms, pack_terms)`: 本文と機械の事実に現れる語だけの定義の節（元の `report_roles.glossary_section` の振る舞い。元は盤面の `BoardGap` に届いて外れるので、ここに書き直したことを PR に書く）。`pack_terms` は `lib/glossary.json`。
    - run の記録の読み: `transcript_facts(rows, *, exclude_prefix) -> {failed, retried, cost, minutes, models, ok}`。行の種類と欄は d97d00ef の `packages/workflows/src/logger.ts` で確かめる。元の `reads.failed_nodes`・`retried_nodes` は今の works が使った v0.11.1 の DB の出来事の行（`event_type`・`step_name`）の形なので使わない。
    - lib/ の決まり（E3）: `archon`・`ARTIFACTS_DIR`・`TYPED_ARTIFACTS_FILE`・`ARCHON_` で始まる名・`output_type` の字を書かない。入力は引数（dict・行の list・パス）で受ける。

### 試験

- `lib/tests/test_report.py`（元 `works/tests/test_report.py`。lib-port の移し方 5）: 残る見込みは `TddLinesCase`（`test_each_unit_gets_its_outcome`・`test_stages_that_did_not_run_are_left_out`・`test_stage_without_loop_says_why`・`test_tdd_unit_shows_red_quotes_stub_files_and_unchecked`・`test_stage_line_names_reused_source`・`test_head_names_stages_without_freeze` など 6〜7 本）。外す: `ReportBase` を継ぐ全部（盤面の偽物 `RF.DeltaBoardCase`）・`HeadWhereDesignCase`・`CostCase`（`cost_rows`・`head_cost`・`round_facts`）・`NamesCase`（darkfactory・prcheck・rejudge・planblk）・`PriorFailuresUnitCase`（`prior_failures(b)`）と、頭の `accept`・`adapter`・`board`・`ci_role`・`converge`・`engine.util`・`entry`・`linekit`・`prcheck`・`reads`・`refix`・`rejudge` などの import。`OUTCOMES` の 10 語が元の字のままであることを縛る試験が残らなければ、`lib/tests/test_outcome.py` に足す。
- `lib/tests/test_report_roles.py`（元 `works/tests/test_blk_report.py` と `works/tests/test_report_cold.py` のうち、`format_problems`・`head_of`・`_terms_problems`・`count_rejects` を縛る試験だけ。元の 2 つの試験のファイルは盤面と boardreplay・prepkit・entry に頼る物が大半で、残りが少ないので 1 つにまとめる。元の試験の名と元のファイルを PR に並べる）。元に縛る試験が無い関数は新しく書く（例: `format_problems` が「。」を含むセルと 50 字を超えるセルを名指し、`コード` とコードの囲みの中は数えない）。
- `lib/tests/test_outcome.py`（新しい）: 上の決め方の表の 8 行を 1 行ずつ縛る（各行の最小の入力で、その語になる）。加えて: 順の確かめ（止め札と線の止めが同時なら `stopped_by_request`・人の止めと途中で終わったが同時なら `stopped_by_human`・`record_invalid` は `interrupted` より先）、深さで省いた目（null）を残りに数えない、全部の返りが None でも例外を出さず語を返す、`fix.conflicts` が指し札 1 つ・指し札の配列（段ごと。人に回した行が 2 つ目の段だけに在る場合も `needs_human`）・null のどれでも読める、`materials.json` の `not_run`・`awaiting_human` の素材だけが残りで最後のテストが緑なら `fixed_needs_check`・`{}` と無いファイルは測れていない素材 0 と数える、`plan.ready` が false で単位が在れば `stopped_by_line`（plan の止めの語が在れば `stop_reason` に載る）・単位が無ければ `no_fix_needed`、返る語が `report.OUTCOMES` に在る。
- `lib/tests/test_runreport.py`（新しい）: `build` が `report.md` と（在る時だけ）`next-request.json`・`prior-failures.json` を書き、`carry` の Schema を通る。`tdd-unit` が無く `fix.units` が在る時に単位の行と訳が出る。型つきの成果物の `warnings` が報告の注意の節に 1 件ずつ出る。run の記録が None の時に費用が「取れない」の 1 行になる。記録の見本の行（d97d00ef の `logger.ts` の形で作った物）から節ごとの費用・時間と落ちた節・後で済んだ節が出る。言い直しの行を合計に数えない。止め札の run（`stopped_by_request`）でも報告が書かれる（持ち主の決め `report-on-stop`）。`glossary_section` が本文に現れる語だけを出す。 `review` の隣の `gate-passes.json` の行が「人が決めること」の後に出て、`plan-review` が None・ファイルが無い・読めない時は訳の 1 行になり落ちない。`eye-verdict` の中身が `{eye, status, reason}` でない時は注意の行になる。`tdd-unit` の組ごとの段の物が `tdd_lines` に作り替えずに渡り、`ran: false` の組が「凍結が効いていない」の行になる。
  - 今の works の `works/tests/test_gate_head.py` の `ReportHeadCase` と `works/tests/test_gate_drafts.py` の `DraftsCase` のうち報告の側の場面を、返りの入力の形で書き直して持つ（元は盤面と関所の節で回す試験なので、元の試験の名を docstring に書き、場面だけを写す）: 決めることが無い run は人が決めることに次の依頼の件数を出す（`test_nothing_to_decide_puts_next_items`）・人が決めることの件数を数える（`test_decisions_are_counted`）・関所で答えたが直す義務に戻せなかった単位も数える（`test_unreturned_unit_is_counted_as_decision`。fix の返りの単位の `not_done` で読む）・`fixed_needs_check` の残りの確かめを数える（`test_checks_left_are_counted_as_decision`）・10 語の全部に平易な文が在る（`test_every_outcome_has_plain_words`）・無人の run で関所が開かなかった問いごとに下書きの印つきの答えの下書きが次の依頼に入る（`test_each_stopped_item_gets_a_marked_draft`）・定石からの外れの問いは 1 度だけ下書きになる（`test_world_deviation_drafted_once`）・中身の無い行も「無い」と言う下書きになる（`test_row_with_nothing_still_gets_a_draft_saying_so`）・人が答えた run（関所の答えが在る）は下書きを作らない（`test_attended_run_gets_no_gate_item_drafts`）。関所の文そのもの（最後の関所に並べる行）の場面は線の issue に渡す物として PR の本文に名で並べる。
- `tests/workflows/test_report.py`（ブロックの YAML の形。PyYAML で読み、Archon を起こさない）:
  - 工程の名が `works-factory-report`、`returns: report`。
  - 返す節 `report` の `output_format` の欄が約束の欄とちょうど同じ（全部 `required`・`additionalProperties: false`）。`outcome` の enum が `lib/report.py` の `OUTCOMES` と同じ並びと字。`outcome_field` の欄が `required` に在り `type: boolean`。
  - `inputs:` の名が約束の 26 個とちょうど同じ。
  - AI の節（`write`・`cold`）に `mutates_checkout: false`（E7）。`cold` は `allowed_tools: []` と `context: fresh`。`write` の道具が Read・Grep・Glob・WebSearch・WebFetch だけ。
  - script の節も全部 `mutates_checkout: false`（このブロックは作業ツリーを変えない）。
  - 返す節 `report` の `trigger_rule` が `all_done`（AI の報告が落ちても返る）。
  - `scripts/typed.py` を一時の一覧で回す: include の頭と `loopGroupPath` で組に分ける・同じ頭の別の周を両方残す・ほかの run の行と自分の include の行を数えない・`errors` を 1 件ずつ `warnings` に入れる・一覧が無い／読めない／`artifactsByType` が配列でない時に名前つきの限りが 1 行出て例外を出さない。
  - `scripts/facts.py` の入力の読み: 空と字の `null` が None、JSON でない値が落ちずに None と訳になる（環境変数を差し替えて関数を呼ぶ）。`TYPED_ARTIFACTS_FILE` が空の字・`LOG_DIR` が無い・`WORKFLOW_ID` が `dry-run` でも名前つきの限りになる。
  - 子のプロセスの試験（Archon を起こさない。一時の `ARTIFACTS_DIR` と環境変数で script を走らせる）: (1) `facts.py` が、壊れた入力・在らない指し札・思わぬ誤りでも終了の値 0 で JSON を 1 つ出す（`record_invalid`）。(2) `report_accept.py` を初見の読み手が `redesign-needed` の返答で 3 回走らせると、1・2 回目は `done: false` で訳を返し、3 回目は `done: true` で `report/ai.json` に `NOT_PASSED` の印が残る。表のセルの書式の破れと `terms` の型の破れも 1 回目に拒む。(3) `collect.py` が `report/ai.json` の無い置き場（書き手の輪が落ちた・飛ばされた）で `report_ai: null` と機械の報告を返す。 (4) `collect.py` に壊れた入力（`facts` の返りが空・JSON でない・欄が欠けた・指し札の先が無い・置き場に書けない）を渡しても、終了の値 0 で `ok: false`・`outcome: record_invalid`・訳の入った `stop_reason` の JSON を 1 つ出し、それが返す節の `output_format`（YAML から読んだ JSON Schema）に合う。
  - 役の節の鍵: `write` と `cold` の `settingSources`・`sandbox` が元の `blk-report.yaml` の値、`cold` の `context: fresh`。工程の段に `interactive`・`worktree`・`container`・`evidence_policy`・`mutates_checkout` が無い。

## 返りの約束（`docs/design.md`「ブロックの返りの約束」の `report` の返りのまま）

- 返す節 `report`・`outcome_field: ok`。今の `docs/design.md` の字は `outcome_field: outcome` だが、Archon（d97d00ef）は `outcome_field` が `required` の `type: boolean` の欄でないと工程の読み込みで落とす（`guides/authoring-workflows.md`:1714-1717・`packages/workflows/src/loader.ts`:172-202）。その直し（人の直し H2（本文の「依存」）: 欄 `ok` を足し `outcome_field: ok` にする。`outcome` は文字列の欄のまま残る）が main に入った後の約束で作る。**H2 が入るまではこの issue を始めない。** 線は自分の返す節 `result` で report の返りを受けて返す（線の `returns: result`）。
- 入力（`with:`）: 全部 `$collect.output.<欄>`（線の返しの節 `collect` が、飛ばされうる全部の返りを `{from, if_skipped: null}` で欄ごとに受けて組み直した物。飛ばされた include は null）。欄は次の名:
  - `start`（始めの記録の指し札）・`prior_failures`（依頼の前の失敗の行の指し札）
  - ブロックの返り（include の id の `-` を `_` にした名。返りの欄の object か null）: `test_gate_base`・`judge`・`rejudge`・`plan`・`plan_review`・`replan`・`replan_review`・`fix`・`refix`・`test_gate_final`・`eyes`・`merge_seal`・`merge_apply`
  - 人の関所の答え `{decision, text}` か null: `gate_start`・`gate_before_fix`・`gate_replan`・`gate_final`
  - 線の節の物: `stop_reason`（線が止めた理由の語。入口の拒み `works:start-refused`・人の止め `human:<関所>`・無人の run の `works:needs-human`・線の script の例外 `works:line-script`。止まらなければ `""`）・`deferred_questions`（無人の run で関所に載せず報告へ回した問い）・`widened`（無人の run で聞かずに通した範囲を広げるだけの直し）・`final_reasons`（最後の関所を開ける理由）・`judged`（`rejudged`・`new_open_units`・`lowered`）・`fixed`（`conflicts`・`refixed`）・`redepth`（`depth`・`skip_optional`・`raised`）
  - 型つきの成果物の一覧（`tdd-unit`・`green-cert`・`eye-verdict`）は `with:` でなく report の中で `$TYPED_ARTIFACTS_FILE` から読む（E5）
- 返り:
  - `outcome`（string）: 結末の語。enum は今の works の `report.py` の `OUTCOMES` の 10 語 `fixed`・`fixed_needs_check`・`no_fix_needed`・`round_limit`・`stopped_by_request`・`stopped_by_human`・`stopped_by_line`・`needs_human`・`record_invalid`・`interrupted` → 線の返り
  - `stop_reason`（string）: 止めた段と理由の語（`lib/stopby.py`）。止まらなければ `""` → 線の返り
  - `report`（指し札）: 機械の報告（今の works の `report.md`）→ 線の返り
  - `report_ai`（指し札・null 可）: AI の報告（今の works の `report-ai.md`）→ 線の返り
  - `next_request`（指し札・null 可）: 次の依頼（`lib/carry.py`。今の works の `next-request.json`）→ 線の返り
  - `prior_failures`（指し札・null 可）: 前の失敗の行（`lib/carry.py`。今の works の `prior-failures.json`）→ 線の返り
  - `ok`（boolean）: H2 の文のとおり（`outcome` が `fixed`・`fixed_needs_check`・`no_fix_needed` なら true、ほかは false）→ 線の返り
- 型つきの成果物: このブロックは出さない。読むだけ（E5）。

- 返す節の `output_format` は、上の欄をちょうど持つ（全部 `required`・`additionalProperties: false`）。欄を足す・名を変える・型を変える・欄を落とすのは線との約束を変えることなので、この PR ではしない。要ると分かったら PR の本文の「約束を変える頼み」に書き、約束どおりの形で作り終える。

## 共通の書き方

- script の節は名指しの script（`script: <名>`・`runtime: uv`・ファイルは `scripts/<名>.py`）。頭で境の口と lib/ を次の形で読む（Archon の `guides/script-nodes.md` の「Share code within a pack」の Python の形。パスの字に `../` を書かないので E4 の照らしに当たらない）:
  ```python
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
  import boundary
  sys.path.append(str(boundary.lib_root()))
  ```
  入力は `os.environ["INPUTS_<名>"]` を字のまま読む（名前を組まない。issue #11）。返りは `boundary.returns(...)`、指し札は `boundary.pointer(...)`・`boundary.resolve(...)`。確かめの中身は書かず、lib/ の関数を呼ぶだけ（E4）。
- 始めの記録は入力 `start`（指し札）で受け、`boundary.resolve` で開いて JSON で読む。欄の形は `lib/startrec.py`。
- 期限: 期限を持つ節（`script:`・`bash:` の `timeout`、`prompt:`・`command:` の `idle_timeout`、`loop:` の `idle_timeout` と `timeout`、`loop_group:` の `timeout`、`approval:` の `idle_timeout`）には全部 `1728000000` を書く（E12）。
- 役の節の `model:`・`effort:` は今の works の `works/.shared/core/stage-models.json` と役の前付け（`works/.shared/core/agents/`）の値を写す（持ち主の決め `model-effort`）。このブロックでは書き手 `blk-report/report-write` が `light`（sonnet・medium）、初見の読み手が前付け `cold-reader.md`（sonnet・medium）。
- 役の指示書（`commands/`）と `lib/` に、対象の言語・テストの実行器の名を書かない（E13）。持ち主の環境の字（`raiki61`・`/Users/` など）を書かない（E14）。
- 外への書き込み（GitHub・対象のリポジトリの main・人に見える所）は、このブロックでは無い。報告は run の置き場（`$ARTIFACTS_DIR/report/`）に書き、指し札で返すだけ（人は Archon の命令で run の置き場を見る。持ち主の決め `one-launcher`）。だから E6 の読み戻しの節を持たない。
- ブロックの YAML と script は、ほかのブロックのフォルダを指さない（E4）。ほかのブロックの返りは `with:` の入力として受けるだけ。
- 筋書き（fixture）は Archon の `workflow test` の形（`fixtures/<名>.stubs.yaml`。予約の鍵 `fixture:`（`expect`・`fail-node`・`reached`・`inputs`・`resolved-text-contains`）と `exec-code:`、残りの鍵は節の id → 差し替えの出力）。script の中身まで通したい筋書きは `exec-code: true`。
- ブロックの試験 `tests/workflows/test_report.py` は 2 つの部分を持つ。YAML の形の試験は PyYAML で YAML を読み、Archon を起こさない。筋書きを Archon で回す試験も同じファイルに書き、issue #47 の PR（P0）の `tests/archon.py` を使う: 使い捨ての git の木に `workflows/report/` と `workflows/.shared/` だけを `.archon/workflows/works-factory/` の下に置き、使い捨ての Archon の家で `archon workflow test` を回す。Archon の源か bun が無い所では `tests/archon.py` が `skipTest("Archon の源が無い: ...")` で見送る。共有の筋書きの試験のファイルは無い。

## Archon で書けない所

- 線の側の限り: Archon は落ちた節の返りを `with:` で渡そうとすると、`if_skipped` を書いても誤りにする（`packages/workflows/src/dag-executor.ts`:519-534）。だから前の段が落ちた run で report に何が届くかは線が決める（線の issue の事）。report は全部の入力が空・`null` でも返る形に作り、`facts.py` は 0 以外で終わらない。
- そのほかは Archon に在る物の上に作り、確かめが要る:
  - 型つきの成果物の一覧（`$TYPED_ARTIFACTS_FILE`）と run の記録（`$LOG_DIR/<WORKFLOW_ID>.jsonl`）の形は d97d00ef の源で確かめる（上の「読む物」）。
  - fix の組の並べが `workflow:` の子の run になる時（未決 U8）、子の run の型つきの成果物は親の一覧に載らない。fix の計画は親の run の節 `tdd-unit` で単位の行を出し直すので、report は親の一覧だけを読む。それでも成果物が無い run は fix の返り `units` で単位の行を出し、成果物が無い訳を出す。
  - include の返りが include ごとに分かれて見えるか（未決 U2）と、include の入力に `if_skipped` が通るか（埋め P2）は線の側の事。report は全部の入力が None でも動く形で作る。
- 読んだ証拠（未決 U6）は取れないので「取れない」と書く。埋めは作らない（`workflows/.shared/` は守りのパス）。

## E11 の 3 つの答え

1. Archon が持っているか: 結末の語・報告・持ち越しは持たない。持つ物はそのまま使う: どの道でも返る節（`trigger_rule: all_done`）、書き手の出し直しの輪（`loop_group` の `until_bash`・`max_iterations`）、初見の読み手の新しい会話（`context: fresh`・`allowed_tools: []`）、読むだけの役の柵（`mutates_checkout: false`）、型つきの成果物の一覧（`$TYPED_ARTIFACTS_FILE`）、run の記録の費用（`cost_usd`）、関所の答え（`{decision, text}`）。費用と時間を自前の控えに保存しない。
2. ASF が持っているか: `W/ship/scripts/outcome.ts`（どの道でも 1 つの返り）・`W/.shared/report.ts`（一覧の読み方・`errors` を注意として出す・読めない時は名前つきの限り）・`W/review/commands/review-synthesize.md`:18（include の頭と `loopGroupPath` で絞る）。型だけを採り、コードは写さない（E8）。
3. 本当に要るか: 能力の棚卸しの「結末の 10 語」「報告と初見の確かめ」「持ち越し」と、受け入れの一覧の `report.human_items`・`report.cold_check`・`report`、keep-essence の 11。

## 受け入れ

1. 試験を先に入れて赤を見る（lib/ の部品が無い・YAML が無い）。その後で部品と YAML を入れて緑。赤と緑の出力の要約を PR に書く。
2. リポジトリの根からの全部の試験 `uv run --isolated python3 -m unittest discover -s . -t .` が緑。`tests/layers/` の層の試験（その時に在る物全部）も緑のまま。
3. Archon の源が在る所で、`tests/workflows/test_report.py` の筋書きの試験（`tests/archon.py` の使い捨ての木で `workflows/report/fixtures/` を `archon workflow test` で回す）が全部通り、同じ木の `archon validate workflows` に `works-factory-report` の誤りも警告も無い。Archon の源が無い所では、その試験は `tests/archon.py` が名前つきで見送る（`skipTest("Archon の源が無い: ...")`）。PR には、Archon で回した結果か、回せなかった訳を書く。
4. 持ってきた lib/ のファイルを元と比べた差分が、lib-port の「移し方」1〜5 で決めた直しだけ。
5. PR の本文に次を並べる（守りのパスの文書に書く代わり。土台の持ち主が `docs/design.md`・`docs/asf-notes.md` に写す）:
   - lib-port の「移し方」6 の 4 つ（元のパス → 置いた先・外した物と理由・言い換えた行・盤面の物を引数で受ける関数の一覧）
   - 採った ASF の型（`docs/asf-notes.md` の「書き方」の 4 行の形）
   - 「能力の棚卸し」と「受け入れの一覧」のこのブロックの行ごとの、証の試験か筋書きの名
   - 約束を変える頼み・使いたかった埋め（あれば）
   - 新しく書いた `lib/outcome.py` の決め方の表と、元の `decide_outcome` との違い（行ごと）
6. このブロックの分（`docs/design.md` の段 2 の report の個別の行）:
   - 結末の 10 語（返す節の enum が元の `OUTCOMES` と字も並びも同じ）・機械の報告・AI の報告・初見の確かめ・持ち越し（次の依頼と前の失敗）が動く。
   - 前の段が落ちても飛ばされても走る: 全部の入力が空の筋書き（`start-missing`）と、書き手の輪が落ちた置き場の `collect.py` の子のプロセスの試験で `report` が返る。`facts.py` は壊れた入力でも 0 で終わる。
   - 型つきの成果物の一覧の `errors` を注意として報告に載せる（`tests/workflows/test_report.py` と `lib/tests/test_runreport.py`）。
   - 止め札で止めた run も報告を出し、結末は `stopped_by_request`（`stopped-by-request` の筋書き。持ち主の決め `report-on-stop`）。
   - TDD の単位の行に赤の引用と理由が載る（keep-essence の 11 と 1）。

## 範囲

- 作るのは `workflows/report/` の下・本文の「lib/ に持ってくる部品」の lib/ のファイル（`lib/report.py`・`lib/report_roles.py`・`lib/glossary.json`・`lib/outcome.py`・`lib/runreport.py`）・本文の「試験」のファイル（`lib/tests/test_report.py`・`lib/tests/test_report_roles.py`・`lib/tests/test_outcome.py`・`lib/tests/test_runreport.py`・`tests/workflows/test_report.py`）だけ。
- 触らない（守りのパス。ASF の merge が人の手に残す）: `workflows/line/**`・`workflows/.shared/**`・`docs/design.md`・`docs/owner-decisions.md`・全部の `AGENTS.md`・`pack.json`・`README.md`・`MISSION.md`・`engineering.md`・`.github/**`・`harness/**`・`factory/**`・`.factory/**`。
- 触らない（同じ時に別の run が作る）: ほかの 7 つのブロックのフォルダ（`workflows/<ほかの名>/`）と、それらの issue が名指す lib/・試験のファイル。ほかの PR と同じファイルを作らない。
- 触らない（前に入る物）: lib-port と`docs/plans/2026-10-12-blocks/prereq.md` の issue で入った lib/ のファイル（本文の「依存」に並べた物）とその試験、`tests/workflows/__init__.py`・`tests/archon.py`、`pyproject.toml`、`docs/`（PR の本文に書く。上の受け入れ 5）。持ってきた部品の中で前提の部品に直しが要ると分かったら、直さず PR の本文に書く。
- 決めた範囲で能力を落とす直しが要ると分かったら（持ち主の決め `superset`・`no-narrow`）、止めて PR の本文に書く。
- 持たない物: 周の鎖（`chain.py`。持ち主の決め `one-launcher` で置き場が未決）、止め札の錠（`halt.py`。持ち主の決め `report-on-stop`）、今の works の検証器と盤面（`record_invalid` は返りと始めの記録で決める）、機械の報告と AI の報告から最後の報告を選ぶ線の節（今の works の `result`。新しい形では `report`・`report_ai` の両方を返し、選ぶのは読み手）。

- 作るファイル（これだけ）:
  - `workflows/report/**`（`works-factory-report.yaml`・`commands/report.md`・`commands/cold-check.md`・`scripts/facts.py`・`scripts/typed.py`・`scripts/cold_prep.py`・`scripts/report_accept.py`・`scripts/collect.py`・`fixtures/fixed.stubs.yaml`・`fixtures/no-ai-report.stubs.yaml`・`fixtures/stopped-by-request.stubs.yaml`・`fixtures/start-missing.stubs.yaml`）
  - `lib/report.py`
  - `lib/report_roles.py`
  - `lib/glossary.json`
  - `lib/outcome.py`
  - `lib/runreport.py`
  - `lib/tests/test_report.py`
  - `lib/tests/test_report_roles.py`
  - `lib/tests/test_outcome.py`
  - `lib/tests/test_runreport.py`
  - `tests/workflows/test_report.py`

## 依存

- 前に入る人の直し（守りのパスの文書。この issue より前に main に入るので、中身はリポジトリのそこを読む）:
  - H1: `tests/workflows/`（ブロックの YAML の形と筋書きの試験の置き場）をリポジトリの形の木に載せる（根の `AGENTS.md`・`tests/AGENTS.md`）。
  - H2: report の返す節に boolean の `ok` を足し、`outcome_field: ok` にする。結末の 10 語 `outcome` は別の string の欄のまま（`docs/design.md` の「report の返り」。止めた Archon の `outcome_field` は `required` の boolean しか受けない）。
  - H3: 段 2 の共通の受け入れ 4・5（ASF の型・証の名）を「PR の本文に書き、土台の持ち主が `docs/` に写す」に直す（`docs/design.md` の「作りの順」）。
  - H4: E13 の例外。拡張子と言語の対応・テストのファイルの名の慣習の表と、その表を作る標準ライブラリの import を、`lib/impact.py`・`lib/changemap.py`・`lib/tddloop.py`・`lib/fixrules.py`・`lib/libdocs.py`・`lib/libdocs_local.py` に限って許す（根の `AGENTS.md`。機械の表 `tests/layers/scan.py` の `ALLOWED["E13"]` には、そのファイルを入れる PR が 1 行ずつ足す）。
  - H5: ブロックをまたぐ形（`docs/design.md` の「ブロックの返りの約束」の「書き方の決め」）。
    - 指し札の先は今の works の同じ名のファイルの形。次の隣のファイルだけは約束の一部で、ほかのブロックも名で開く: `judgment`（`judgment.json`）の隣の `premises.json`・`judge-verify.json`・`pr-excluded.json`・`materials.json`、`plan`（`plan-fields.json`）の隣の `p2.fix_plan.json`、`structure`（`structure-state.json`）の隣の `design.jsonl`、`review` の隣の `gate-passes.json`。ほかの隣のファイルは作ったブロックの中だけで読む。
    - 直す前の結末のファイル: 必須の欄 `{suite, test_cmd, rev, exit, cases}`（`suite` は始めの記録の `tdd_suite` の実行ファイル。`cases` は JUnit の 1 件ごとの結末の並び）。読み書きは `lib/baseline_red.py` だけ。test-gate は自分の欄を足してよい。
    - fix の `conflicts` の先は `conflicts.json` = `{"items": […]}`（今の works の `conflict.py` の形）。
    - 型つきの成果物: `green-cert` は test-gate の返す節の出力。`tdd-unit` は fix の 1 回の差し込みに 1 つで、中身は組ごとの段の物 `[{group_id, ran, reason, suite, reused, units}]`（今の works の blk-fix の `tdd` の出口。走らなかった組も `ran: false` で載る）。`eye-verdict` は `{eye, status, reason}`（`eye` は `r1`・`r2`・`r3`・`r4`・`premise-check`）。
    - 人の関所（`approval:`）の `decisions` は `approve` を含む（Archon の決まり）。通す語は `approve`・`continue`、止める語は `stop`・`reject`。止め札は止める語で、文が `request:` で始まる物。ブロックの `stop_reason` は人の止めを `human:<所>`、止め札を `request:<所>` の形で返す。
    - 約束に無い入力は、ブロックの YAML の `inputs:` に既定値（`""`・`"null"`・`"[]"`）つきで宣言し、線が渡す前も動く形にする。返りの欄は足さない。
    - 返す節は落ちない。中の誤りを全部捕まえ、そのブロックの偽の結末（`ok: false` など）と訳を、`output_format` に合う形で返す（線は落ちた返す節の先へ進めない）。
  - H7: 始めの記録に `tdd_suite`（TDD の輪と 1 件ごとの結末に使う実行ファイルのパス。無ければ `""`）を載せる（`docs/design.md` の「線の始めの節 `start` の返り」）。
  - H8: R2 の `status` に `unverifiable`（R2 の比べの節が落ちた・独立設計が無い。前提が崩れた時は `premise_check` にも載る）を足し、merge の入力に `r2` を足し、merge の返り `diff` を null 可にする（`docs/design.md` の eyes と merge の返り）。merge は `redesign-needed` だけを人の答えに関わらず拒み、`unverifiable` は人に回す。
  - H10: E16 の機械の行を「`approval:` の節を持つ工程を起こす一番上の工程（線）に `interactive: true` が在る。差し込まれるブロックは工程の頭に `interactive`・`worktree`・`container`・`evidence_policy`・`mutates_checkout` を書かない」に直す（`workflows/AGENTS.md`。差し込まれた工程の頭のこれらの鍵は Archon が読み込みの警告つきで捨てる）。
- 前に入る PR: issue #47（P0。工程の読み込みの pack の形 `.archon/workflows/works-factory/<ブロック>/`・script が lib/ を見つける道 `boundary.lib_root()`（`WORKS_FACTORY_ROOT`。未決 U5）・Archon の要る試験の助け `tests/archon.py`・CI の Archon の源）と、`docs/plans/2026-10-12-blocks/prereq.md` の issue（2 つ以上のブロックが読む lib/ の部品と `tests/workflows/__init__.py`）。

- main に在る物（lib-port の PR と`docs/plans/2026-10-12-blocks/prereq.md` の issue）: `lib/carry.py`（`compose`・`draft`・`errors`・`NEXT_REQUEST_FILE`・`PRIOR_FAILURES_FILE`・`NEXT_SCHEMA`・`PRIOR_SCHEMA`・`REDESIGN_WHERE`）と `lib/next-request.schema.json`・`lib/prior-failures.schema.json`・`lib/promptsection.py`・`lib/marks.py`・`lib/stopby.py`・`lib/startrec.py`・`lib/gatemarks.py`（`report.py` の `WHERE` を残すなら）・`lib/outpurpose.py`・`lib/worldmark.py`・`lib/graphloops/engine/schema.py`（`validate_schema`）。`workflows/.shared/boundary.py`。`docs/plans/2026-10-12-blocks/prereq.md` の issue の `tests/workflows/__init__.py`。
- issue #47 の PR（P0。ブロックより先に main に入る）: Archon が工程を読む置き方（`bin/_lib/place.workflow_source` の殻が `.archon/workflows/works-factory/<ブロック>/` の形でリポジトリの `workflows/` を見せ、ブロックが packaged workflow になる）・未決 U5（`boundary.lib_root()` が `WORKS_FACTORY_ROOT` を読み、無ければ元の決め方に戻る）・試験の助け `tests/archon.py`（止めた Archon の源と bun を見つけ、使い捨ての木と Archon の家で回す。無ければ名前つきで見送る）・CI が Archon の源と bun を取ること。
- 置き方と U5 は上の P0 で決まる。このブロックは `boundary.lib_root()` を呼ぶだけで、置き方を自分で決めない。
- 人の直し: 人の直し H2（本文の「依存」）（report の `outcome_field` を boolean の `ok` にする）が main に入っていること。H1（`tests/workflows/` の置き場）も同じ。
- `lib/conflict.py` は読まない（同じ時に fix の PR が作るファイル）。`fix.conflicts` の中身は欄の名で読む。
- ほかのブロック: 待たない。ほかのブロックの返りは線の `with:` で入力として届くだけで、このブロックの試験はその形の入力を筋書きと試験の中で作る。型つきの成果物の中身と関所の答えの語は 人の直し H5（本文の「依存」） の形で読み、合わない中身は読めない注意にして落とさない。

## 人が入れる前提の直し

- 共通の前提は 本文の「依存」の前に入る物（H1 `tests/workflows/` の置き場・H2 report の `outcome_field` を boolean の `ok` に・H3 段 2 の共通 4・5 を PR の本文へ・H5 ブロックの間の形（型つきの成果物の中身・関所の答えの語と止め札の印））。このブロックはとくに H2 が入ってから始める。
- このブロックだけの直し: **`docs/asf-notes.md` の A4 の「採った先」を E5 に合わせる。** 今の「採った先: 境の口 `workflows/.shared/`（型で引く口 1 つ）。使うのは eyes（R1〜R4 の結果）・report・fix（組ごとの TDD の行）。」と「違い: 絞りと `errors` の扱いを境の口 1 か所に置き、…」を、次に替える:「採った先: report ブロックの中の `workflows/report/scripts/typed.py`（`workflows/AGENTS.md` の E5「型つきの成果物の一覧を読むのは report ブロックだけ」「読む部品は report ブロックの中に置く」）。」「違い: 絞りと `errors` の扱いを report の中の 1 か所に置く。include の名を決め打たず、一覧に在る include の頭で組に分ける。」
