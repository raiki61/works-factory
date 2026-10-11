<!-- coldwrite:skip ASF の役が読む作業の計画（issue の本文）。語は works-factory の docs/design.md の「語」の節で定義 -->
# plan-review: 事前審査のブロックを中身ごと作る（workflows/plan-review/ と、それだけが使う lib/ の部品と試験）

works-factory は、修正依頼を受けて確かめ済みの変更と報告を返す工場を、Archon（AI の工程を YAML で書いて回す道具）の上に作り直しているリポジトリ。前の形の「今の works」（公開リポジトリ raiki61/claude-plugins の `works/`。移す元の版は `pack.json` の `works.commit` = `2aa7c66cf7abe1fe09699ac2942d107123214168`）は、判定・計画・修正・確かめ・報告をつないだ工場で、その能力を 1 つも落とさずに、線（`workflows/line/`。ブロックを並べる 1 本の工程）・8 つのブロック（`workflows/<名>/`）・助け手（`lib/`。Archon を知らない Python）に移している。この issue は、そのうちのブロック `plan-review` を、フォルダの中身ごと 1 つの PR で作る。8 つのブロックは別々の run で同時に作られ、線とはブロックの返りの約束（`docs/design.md` の「ブロックの返りの約束」）だけでつながる。元のファイルは `https://raw.githubusercontent.com/raiki61/claude-plugins/2aa7c66cf7abe1fe09699ac2942d107123214168/<パス>` で読める（本文の「元」の欄の `<パス>`）。ASF は Archon の作者が作った、issue から PR までの工程の束（`docs/design.md` の「語」）。

## 読む物

- 根の `AGENTS.md`（リポジトリの形・E8〜E11・E13・E14・E18）、`workflows/AGENTS.md`（E1・E2・E4〜E7・E12・E16・E17）、`lib/AGENTS.md`（E3）、`tests/AGENTS.md`。決まりの番号 E1〜E18 の中身はそれらの文書に在る。
- `docs/design.md`: 「ブロック」の `plan-review` の節・「ブロックの返りの約束」の `plan-review` の返り・「能力の棚卸し」の `plan・plan-review` の行・「受け入れの一覧」・「Archon の分かっていること」と未決 U1〜U8・「作りの順」の段 2 の `plan-review` の個別の行。
- `docs/plans/2026-10-12-lib-port.md` の「移し方」1〜6（この issue で `lib/` に持ってくる部品も同じ移し方に従う）。
- `docs/owner-decisions.md` のうち本文が引く決め。
- Archon の振る舞いは、ASF と同じ Archon の源（`coleam00/Archon` の commit `d97d00ef15cce4b15d39e42635e4e86996ec1351`。持ち主の決め `archon-same-as-asf`）の文書 `packages/docs-web/src/content/docs/`（特に `guides/script-nodes.md`・`guides/authoring-workflows.md`・`reference/cli.md` の dry-run と `workflow test`）で確かめる。ASF の工程は同じ commit の `.archon/workflows/sdlc/`（本文の `W`）。
- このブロックの元（全部 `works/` の下）:
  - 工程: `blk-plan/blk-plan.yaml` の節 `r2-design-snap`・`r2-design-loop`（独立設計）と `converge-loop` の中の `review-ripple`・`plan-review-snap`・`plan-review-loop`・`converge-check`（事前審査と壁打ちの決め）。同じファイルの `plan-loop`・`plan-revise-loop`（修正案と案の直し）は plan ブロックの物で、ここでは作らない。
  - 指示書: `.shared/core/gl-prompts/prompts/review-loop/p2.plan_review.md`（本流 graphloops の事前審査。見ること 1〜8 と返し方）・`.shared/core/gl-prompts/prompts/review-loop/r2.design.md`（独立設計）・`blk-plan/commands/r2-design.md`（貼る殻）。
  - 役の前付け: `.shared/core/agents/blind-judge.md`（独立設計）・`.shared/core/agents/judge.md`（事前審査）。
  - 部品: `blk-plan/lib/planblk.py`（事前審査の木・独立設計の節・先行例の控え）・`blk-plan/lib/ripple.py`・`.shared/core/design.py`・`.shared/core/policy.py`・`.shared/core/converge.py`・`.shared/core/gatemarks.py`（後の 2 つは lib-port で lib/ に在る）。
  - 筋書き: `blk-plan/fixtures/pass.stubs.yaml`・`give-up.stubs.yaml`・`plan-rejected.stubs.yaml`。
  - 試験: `tests/test_blk_plan.py`（YamlCase・ScriptCase・ConvergeReviewCase・QuoteFoldCase・TreeReviewCase・PlanReviewFrozenFieldsCase の事前審査と独立設計の側）・`tests/test_plan_gate.py`・`tests/test_gate_drafts.py`・`tests/test_policy.py`。
- ASF: `W/review/archon-review.yaml`（:61-62 の `returns: publish`・`outcome_field: ready`、:122-202 の読むだけのレンズの節の `mutates_checkout: false`、:236-240 の `synthesize`）。

## 目的と引き継ぐ能力

書く前に修正案を叩く。目的の文だけから作る独立設計（R2）を修正案より先に 1 度だけ作り、修正案と構造で突き合わせ、写し・塞がない入口・契約のずれ・死んだ道・範囲の膨張・後退・方針とのぶつかり・先行例の出典の当たりを、書かれる前に予測する。1 回の差し込みが計画の往復（線の `loop_group` の plan → plan-review）の 1 往復で、block（直しへ進めない穴）が無ければ通し、同じ所で 2 度続けて止めたら止めた（stalled）と返す。修正前の関所（線 6）に載せるかを 4 つの軸（自明・世界の解・汚くない・やりすぎでない）で決め、人への問いを返す。

能力の棚卸しの行（元のパスは `works/` から。2aa7c66c）:

- 独立設計 R2 — `blk-plan` の `r2-design-loop`・`.shared/core/design.py` → `commands/r2-design.md`・`scripts/r2_prep.py`・`scripts/r2_accept.py`・`lib/design.py`（`docs/plans/2026-10-12-blocks/prereq.md` の issue）
- 事前審査（項目ごとの木）— `blk-plan` の `plan-review-loop`・`blk-plan/lib/planblk.py` の木の部分 → `commands/plan-review.md`・`scripts/review_prep.py`・`scripts/review_accept.py`・`lib/planblk.py`・`lib/ripple.py`（棚卸しの行は `holeties.py` を挙げているが、holeties は差分の審査の穴の名札で fix と report が読む物。このブロックは使わない。PR の本文に書く）
- 壁打ちの往復 — `.shared/core/converge.py`（lib/ に在る）→ 線の往復と、このブロックの往復の決め（`scripts/result.py`）
- 修正前の関所の 4 つの軸 — `.shared/core/gatemarks.py`（lib/ に在る）→ `scripts/result.py`・新しい `lib/gate_axes.py`（軸ごとに分ける）
- 人の方針の文 — `.shared/core/policy.py` → `lib/policy.py`（`docs/plans/2026-10-12-blocks/prereq.md` の issue）

受け入れの一覧（review-graph の節）のうちこのブロックが持つ物: `p2.plan_review`（写し・塞がない入口・契約のずれ・後退・方針とのぶつかりを予測する）・`p2.human_gate` の材料（狭め・後退・方針の穴があれば直す前に人に聞く。関所そのものは線 6）・`r2.design`（禁: 実装・リポジトリ・履歴・累積差分・決着済みの論点）。keep-essence の 12（今の works の `works/docs/keep-essence.md`）のうち: 独立設計・世界の解（先行例の出典の当たりと 4 つの軸の世界の解）。

持ち主の決め: `doubt-always`（R2 の独立設計と定石の段を外せない段にする）・`independent-verdict`（禁じた入力が届かないことを試験で縛る）・`close-in-round`（審査と往復は 1 回目で出し切らせ、2 回目からは開いた所見と波及だけを見る）・`obvious`・`gates`・`ask-shape`・`dirty-area`・`unattended`・`no-narrow`・`tell-downstream`・`one-axis`・`model-effort`。

## 作る物

### ブロックのフォルダ `workflows/plan-review/`

- `works-factory-plan-review.yaml`（工程の名も `works-factory-plan-review`。E9）。`returns: review`・`outcome_field: pass`。工程の頭に `interactive`・`worktree`・`container`・`evidence_policy`・`mutates_checkout` を書かない（include で差し込まれるブロックでは Archon が読み込みの警告つきで捨てる。`guides/authoring-workflows.md` の「Composed behaviour」）。入力（`inputs:`。値は字。指し札と配列は JSON の字）: `units`・`judgment`・`purpose`・`world`・`plan`・`structure`・`ripple`（約束のとおり）と、約束に無いがこのブロックが要る `start`（`default: "null"`）・`answers`（`default: "null"`）・`ruling`（`default: "[]"`）。後の 3 つは線がまだ渡さなくても動くように既定を持ち（既定の時の振る舞いは下の「既定の時」）、約束への足しを「人が入れる前提の直し」1 に書く。節（AI の節は全部 `mutates_checkout: false`。script の節も作業ツリーを変えないので全部 `mutates_checkout: false`）:
  1. `open`（script `pass_open`）: 入力の指し札を開き、この差し込みの番号 k（指し札 `plan` の先の `plan-fields.json` の `round`）と形（`ruling` が空でなければ `replan`、空なら `review`）を決め、`p2.fix_plan.json` の narrows の決め手の欄を `gatemarks.split("p2.fix_plan", reply)` で外して `gatemarks.save(<plan-review/>, "p2.fix_plan", 1, rows)` で置き（自明の軸の決め手 `decided_by` などが `gatemarks` に届く。`output_of_round("p2.fix_plan", 1)` は欄を外した返答を返す）、`lib/boardview.py` の読むだけの見え方の材料を run の置き場 `plan-review/` に置く（見え方の `dir`・書き先 `place()`・`gate-marks.json`・往復の控えは全部この 1 つのフォルダ。下の「盤面の見え方」）。独立設計を回すか（`r2_go`: 同じ run で `plan-review/design.json` が無く、`design.unusable` が目的を使えると言う時だけ）と、事前審査を木にするか（`tree`: 始めの記録の機能の切り替え `review_tree` の on・off・auto。auto は開いた項目が 2 つ以上）を返す。`timeout: 1728000000`。
  2. `r2-design-loop`（`loop_group`。`when: "$open.output.r2_go == true"`・`max_iterations: 3`・`fresh_context: false`・`until_bash: test $r2-accept.output.done = true`・`timeout: 1728000000`）:
     - `r2-prep`（script `r2_prep`）: 目的の文（`purpose`）・実測した制約（`judgment` の指し札の先の隣の `premises.json` の `constraints` だけ。`judgment.json` の中身は読まない）・人の関所の答え（`answers`）・依頼が名指した設計書の節と対象の根の地図（`start` の依頼のファイルと固めた版）を `lib/design.py` の `human_answers`・`named_sections`・`repo_map` で組み、`r2.design.md` の指示書の本文を `prompt` に返す。前の回の受け付けの拒みの文を頭に貼る。貼った物の控え（`{given, withheld, seen}`）を `plan-review/design-premises.json` に書く。役を起こす前の作業ツリーの控えを `lib/accept.py` の `snapshot_tree` で `plan-review/r2-tree.json` に置く。読む環境変数は `INPUTS_PURPOSE`・`INPUTS_JUDGMENT`・`INPUTS_START`・`INPUTS_ANSWERS`・`ARTIFACTS_DIR`・`WORKFLOW_ID` だけ（Archon は工程の入力を全部の script に `INPUTS_*` で渡すので、禁じた入力を読まないことは script の字で縛る）。
     - `r2-design`（command `r2-design`。`model: opus`・`effort: high`（`blind-judge` の前付け）・`allowed_tools: []`・`settingSources: [user]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`context: fresh`・`mutates_checkout: false`・`idle_timeout: 1728000000`。今の works の節 `r2-design` のまま）。`output_format` は今の works の節 `r2-design` の型（`question_stands`・`reason`・`premise_invalid_reason`・`design`）。
     - `r2-accept`（script `r2_accept`）: 作業ツリーが役の前と同じか（`accept.tree_moved`。今の works の `design.check_design` の比べ）・`design.anchor_misses`（問いが立たない根拠の名指し `パス:行` を固めた版で検算）・`design.claims_unpassed`・`claims_given` を当て、通れば `plan-review/design.json`。拒みは `rolekit.with_reject` の形で `plan-review/r2-rejects.json` に積み、3 回目で `done: true`・`give_up: true`（`rolekit.given_up_reason`。諦めても止めない。事前審査は設計なしで進む）。
  3. `review-loop`（`loop_group`。`max_iterations: 3`・`fresh_context: true`・`until_bash: test $review-accept.output.done = true`・`timeout: 1728000000`。`depends_on: [open, r2-design-loop]`・`trigger_rule: all_done`。輪の中の節は前の節の出力を `with:` で結ばず、`plan-review/` のファイルを読む（落ちた節への `with:` の結びは `if_skipped` があっても投げる）。`open` が落ちた時は `review-prep` が見え方の材料が無いことを見て受け付けを諦めにする）:
     - `review-prep`（script `review_prep`）: 事前審査の材料のファイル `plan-review/pass-<k>/prompt.md` を書き、役を起こす前の作業ツリーの控えを `plan-review/pass-<k>/tree.json` に置く（`accept.snapshot_tree`）。材料は `p2.plan_review.md` の差し込みの部分（修正案（`p2.fix_plan.json` の `plan[]`）・単位（番号つき）・判定の見立て `framing`・`one_shot`・先行例・対象のリポジトリと読む版・観点の正本 `lib/REVIEW.md` のパス（`boundary.lib_root() / "REVIEW.md"`。元の `{{inputs.review_md}}`）・方針の文（`policy.brief`）・独立設計の節と修正案の項目の works の欄（`planblk.design_section`。設計が無ければその訳）・波及の一覧・2 往復目からは前の往復の block と修正案の役の答え（`converge.review_section`）と項目ごとの差分）。`tree` が真なら項目ごとの下請けのファイルと束ね役の頼み（`planblk.tree_part`）も書く。形 `replan` では、裁かれた項目（`ruling`）だけを開いた項目にする。
     - `plan-review`（command `plan-review`。`model: opus`・`effort: high`（`judge` の前付け）・`allowed_tools: [Read, Grep, Glob, WebSearch, WebFetch, Agent, Write]`・`settingSources: [user]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`context: fresh`・`mutates_checkout: false`・`idle_timeout: 1728000000`）。`Write` は下請けが run の置き場の答えのファイルに書く口だけ（作業ツリーは変えない。変えれば Archon が節を落とす）。`output_format` は今の works の節 `plan-review` の型（`faces`・`shrink`・`reason`・`faces_none`・`resolved`・`items`・`design_map` と、faces の行の決め手の欄 `decided_by`・`undecided_because`・`fences`・`world`・`recommend`・`no_narrow`）。
     - `review-accept`（script `review_accept`）: 作業ツリーが役の前と同じか（`accept.tree_moved`。Archon の `mutates_checkout` は git の様子だけを比べるので、今の works の受け付けの比べ（porcelain・差分・無視するパス・HEAD・枝）を残す）。木なら下請けの答えのファイルを `planblk.tree_merge` で faces・shrink にまとめ、`planblk.check_item`・`item_answer_gaps`・`design_gaps`（`design.quote_gaps`）・`converge.resolved_gaps`・`gatemarks.recommend_gaps`・入口の穴の `no_add` の欠けで照らす。通れば: 決め手の欄を `gatemarks.split` で外して `gatemarks.save(<plan-review の置き場>, "p2.plan_review", 1, rows)` で本物のファイルに置き、返答を `plan-review/pass-<k>/review.json` に書き、形 `review` なら往復の控えに積む（書き手の口: `converge.note_plan`（毎回、`p2.fix_plan.json` の項目）・`converge.note_answers`（2 往復目から、`p2.fix_plan.json` の `block_answers`）・`converge.record_pass`。どれも `boardview.place(<plan-review の置き場>)` の書き先に書く。見え方は渡さない）。拒みは `rolekit.with_reject` の形で `plan-review/pass-<k>/rejects.json` に積み、3 回目で `done: true`・`give_up: true`。
  4. `review`（script `result`。返す節。`depends_on: [review-loop]`・`trigger_rule: all_done`・`timeout: 1728000000`。前の節の出力を `with:` で結ばず、`plan-review/` のファイル（往復の控え・`pass-<k>/review.json`・`design.json`・拒みの控え）だけを読む）: 往復の控えから `converge.decide` で抜け方を決め、`gatemarks.plan_gate_items`（見え方を渡す。中の聞かずに通した行の記録 `_record` はファイルに書かず見え方の手元の `state` の辞書に積むだけなので、`result` が `gatemarks.passes(見え方)` を `plan-review/pass-<k>/gate-passes.json` に書く）で関所の項目と聞かずに通した行を作り、`lib/gate_axes.py` で 4 つの軸を軸ごとに分け、返りの約束の欄で返す（下の「返りの決め方」）。事前審査を 3 回とも拒まれた時は `pass: false`・`stalled: true`、`questions` と `review` の指し札に諦めた訳を載せる（関所で人が見る。欄は足さない）。返す節は落ちない: 中の全部の例外を捕まえ、`pass: false`・`stalled: false`・`ask_human: true`・`questions` に落ちた訳を名指す 1 行・`gate_axes` は 4 つとも `{ok: false, note: <訳>}`・`review` と `design` は置き場の代わりのファイル（`plan-review/failed/review.json` に `{faces: [], shrink: [], reason: <訳>}`、`plan-review/failed/design.json` に `{"missing": <訳>}`）を指す札で、終了の値 0 で返す（線は落ちた返す節の先へ進めないため）。
- `commands/r2-design.md`: 元 `blk-plan/commands/r2-design.md`（殻）に `r2.design.md` の本文を合わせた物。描いた本文は `$r2-prep.output.prompt` で貼る（役は道具を持たないので読めない）。盤面・engine・包みの事情の文（「engine と同じ描き方で描いた」など）は Archon の書き方に直す。
- `commands/plan-review.md`: 元 `p2.plan_review.md` の決まりの全部（見ること 1〜8・shrink・返し方・根拠は読む版で取る・6 と 7 は人に回すので代償として通すかを決めない）と、planblk の頭の決まり（`HEAD["plan-review"]`・`REUSE_REVIEW`・`HANDOFF_REVIEW`・`DESIGN_ASK`）。材料は `$review-prep.output.prompt_file` を Read で読ませる。`{{…}}` の差し込みは使わない（材料のファイルに入る）。
- `scripts/pass_open.py`・`scripts/r2_prep.py`・`scripts/r2_accept.py`・`scripts/review_prep.py`・`scripts/review_accept.py`・`scripts/result.py`: 頭は「共通の書き方」の形。各々 lib/ の関数を呼び、`boundary.returns` で返すだけ。
- `fixtures/<筋書き>.stubs.yaml`（配線だけを確かめる、全部 stub の筋書き。止めた Archon の dry-run の事実: `until_bash` は回さず輪は済んだと見る・stub は節ごとに 1 つの値・`exec-code` の script は空の `ARTIFACTS_DIR` と `WORKFLOW_ID=dry-run` で走る（`reference/cli.md` の dry-run の節）。だから出し直しの 3 回・諦め・往復の決めは下の試験が script を子のプロセスで回して確かめる）:
  - `pass.stubs.yaml`: 独立設計が 1 回で通り、事前審査が block 無し → `review` が `pass: true`・`ask_human: false`。`fixture.reached: [r2-design, plan-review, review]`。
  - `block.stubs.yaml`: block の穴が在る 1 往復目 → `pass: false`・`stalled: false`（線が次の往復へ）。
  - `stalled.stubs.yaml`: 前の往復と同じ block → `pass: false`・`stalled: true`・`ask_human: true`。
  - `ask-human.stubs.yaml`: 決め手の揃わない regression の穴 → `pass: true`・`ask_human: true`・`questions` が 1 行以上。
  - `r2-skipped.stubs.yaml`: `open` が `r2_go: false`（同じ run に設計の控えが在る・目的が使えない）→ `r2-design-loop` は飛び、事前審査は走る。
  - `r2-give-up.stubs.yaml`: 独立設計の受け付けが 3 回とも拒む（dry-run は until を回さないので、受け付けの stub は諦めの後の姿 `done: true`・`give_up: true`）→ 事前審査は走る。
  - `review-give-up.stubs.yaml`: 事前審査の受け付けが諦める → `review` が `pass: false`・`stalled: true`。
  - 各筋書きの `expect: completed`。`outcome_field` の真偽で Archon の `authoredOutcome` も見える。

### lib/ に持ってくる部品（このブロックだけが使う物）

このブロックは今の works のファイルを lib/ に持ってこない。事前審査と独立設計が読む今の works の部品（`design.py`・`policy.py`・`planblk.py`・`ripple.py`・`impact.py`・`changemap.py`・`rolekit.py` の出し直しの小道具）は、`docs/plans/2026-10-12-blocks/prereq.md` の issue（ブロックの前の共有の部品）が lib-port の移し方で main に置く（下の「依存」）。このブロックはそれを読むだけで、作らない・直さない。

盤面に届く能力の扱いは、8 本の計画で共通の 2 つの形だけにする:
- (a) 継ぎ目の直し: 持ってきたファイルの中の、盤面・Archon・持ってこない部品への 1 か所の呼び出しを、引数か lib/ のモジュールの呼び出しに替える。関数の名とほかの行は変えない。直した行を全部 PR の本文に並べる。
- (b) 書き直し: 中身の大半が盤面の読みの関数は、元の関数の名のまま、値かファイルのパスを引数で受ける形で、新しい lib/ のファイル（`docs/design.md` の能力の名か、ブロックの名を付けた名）に書き直す。docstring に元の `<パス>:<行>` を書き、元の試験の場面を写す。PR の本文に並べる。
- ブロックをまたいで共有する偽の盤面は作らない。このブロックの見え方（下の `lib/boardview.py`）はこのブロックだけが使う。

このブロックが新しく作る lib/ のファイル（どちらも元に無い）:

- `lib/gate_axes.py`（元に無い新しい部品。(a)・(b) のどちらでもない: 元の関数を書き直すのでなく、元に無い「軸ごとの分け」を足す。能力の名 `gate_axes`）: 修正前の関所の 4 つの軸を軸ごとの `{ok, note}` に分ける（`split(b, mark, units) -> dict`・`gather(b) -> dict`。`b` はこのブロックの読むだけの見え方）。中は `gatemarks` の `decided`・`_cite_check`・`_world_rows`・`_design_rows`・`structmark.dirty`・`_answered_rows`・`_plan_keys`・`world_items`・`design_items` を `gatemarks.axes`（`works/.shared/core/gatemarks.py`:576）と同じ順に呼ぶだけで、軸の決まりは書き足さない。自明＝決め手の出どころが揃い現物に在る、世界の解＝world か URL か世界の段の行に従う、汚くない＝構造の目が人に上げた・汚れる行に答えが在る、やりすぎでない＝柵の印が無く案の単位の外を名指さない（`gatemarks.py` の頭の文と今の works の CHANGELOG の 2026-10-09 の行）。全部の行で軸が全部 ok の時だけ `gatemarks.axes` が空になることを試験で縛る（2 か所が食い違えば赤）。
- `lib/boardview.py`（このブロックだけの読むだけの見え方。ほかのブロックは使わない。書き手には渡さない）:
  - `view(folder, inputs) -> SimpleNamespace`: 盤面の物を引数で受ける lib の関数（`gatemarks`・`converge` の読み・`design`・`planblk`・`policy`）に渡す、今の works の盤面と同じ形の見え方。欄は `round`（いつも 1。`converge.read` は控えの周が見え方の周と違うと控えを捨てるので、同じ run の往復と案の直しを通して同じ周の値にする）・`dir`（`plan-review/` の本物の置き場。書き手が書いた控えをそのまま読む）・`work(name)`・`scope`（空）・`scope_root`（`plan-review/`）・`record`（`units`・`questions`・`materials`（`judgment` の指し札の先の隣の `materials.json`。素材の名 → `{status, reason}`）・`process.human_items`（`answers` から）・`process.policy.copy`（始めの記録の `policy_md`。無ければ無し））・`state`（`inputs.cwd`・`inputs.request`（始めの記録の依頼の本文。`design.named_sections` が読む）・`inputs.policy_md`・`works: {}`。`gatemarks._record` が手元で積む）・`rules`（下の写し）・`output_of_round(node, round)`（`p2.fix_plan` は `p2.fix_plan.json`、`p2.plan_review` は今の往復の受けた返答）・`latest_output("p0.purpose")`（`purpose.json`）・`pointer_rows(node)`（単位の名の並び。`planblk._names` が読む形）・`review_body`（`commands/plan-review.md` の審査の決まりの本文。`docs/plans/2026-10-12-blocks/prereq.md` の issue の `planblk._review_rules` の継ぎ目が読む）・`faces_schema`（このブロックの YAML の節 `plan-review` の `output_format` の `properties` の `faces`・`shrink`。`open` が YAML を読んで渡す。`docs/plans/2026-10-12-blocks/prereq.md` の issue の `planblk._faces_schema` の継ぎ目が読む。型の写しのファイルは作らない）。`stop` は持たない（呼ばれたら誤り）。ほかのブロックの指し札の先には書かない（材料は写してから読む）。ただし前提の `planblk` の木の関数（`tree_part` が下請けのファイルを `work(...)` に書く・`tree_merge` が `trace` に行を足す・`save_precedents` が `scope_root` に控えを書く）は 1 つの `b` で読みと書きを行うので、見え方の `work(name)`・`scope_root`・`trace(op, **row)` は `plan-review/` の本物のファイルを指す（`place` と同じ置き場）。`dir` の下に置く材料: `r1/start.json`（`startrec.REL`。始めの記録の写し）・構造の目の控え（`structmark.STATE_FILE`。指し札 `structure` の先の `structure-state.json` を写し、その `design_file` を同じフォルダの名指しの隣のファイル `design.jsonl` の本物のパスに向ける）・世界の解の段の控え（指し札 `world` の先）・波及の一覧（`ripple/pass-<n>.json`。n は `converge.pass_no`。指し札 `ripple` の先の写し。`planblk._ripple_of` が読む）・修正案の欄の控え `plan-fields.json` と、`open` の時のそのバイトで書いた凍結の印の行（`trace.jsonl` の `planmarks.SAVED_OP`）。
  - `rules`: `docs/plans/2026-10-12-blocks/prereq.md` の issue が持ってこない写しの rules（今の works の `.shared/core/graphloops/rules/review-loop.py`）のうち、`design` が `b.rules` で読む物だけを元の名のまま写す（(b) の形）: `MD_LINK`（:2822）・`_md_lines`（:2827）・`_md_slugs`（:2837）・`purpose_unusable`（:403）と、それが呼ぶ `purpose_findings_vetted`。ほかに `HUMAN_FACE_KINDS = ("regression", "policy")`（:4084）。docstring に元の行を書く。
  - `place(folder) -> SimpleNamespace`: 書き手（`converge.note_plan`・`note_answers`・`record_pass`・`stash_rejects`）の書き先。`round`（1）・`dir`・`work(name)`・`trace(op, **row)`（`plan-review/trace.jsonl` に 1 行足す）だけを持ち、本物のファイルに書く。見え方とは別の物。
  - 今の works の試験 `tests/test_plan_gate.py` の `GateBase.gate` が組む偽の盤面と同じ形。Archon の名を書かない（E3）。

### 試験

- `lib/tests/test_design.py`・`test_policy.py` などの前提の部品の試験は`docs/plans/2026-10-12-blocks/prereq.md` の issue が持つ。このブロックでは書かない。
- `lib/tests/test_gate_axes.py`（新）: 軸ごとの訳（決め手の欄が無い → obvious が false・world が無い → world が false・構造の目が人に上げた単位 → clean が false・柵の印・案の単位の外 → not_overkill が false）と、`gatemarks.axes` との食い違いが無いこと（今の works の `tests/test_plan_gate.py` の `FourAxesCase` の場面を全部通す）。
- `lib/tests/test_boardview.py`（新）: 見え方の上で `startrec.read`・`structmark.read`・`worldmark.stage_rows`・`planmarks.read`・`marks.path_of("gate", b)` が置いた物を読むこと。
- `tests/workflows/test_plan_review.py`（YAML の形の試験と、script を子のプロセスで回す試験。Archon を起こさない。子のプロセスの環境は `INPUTS_<名>`・`WORKFLOW_ID`・`ARTIFACTS_DIR`（一時の置き場）を置き、入力の指し札の先のファイルを一時の置き場に書いて作る）:
  - YAML: 返す節が `review`・`outcome_field` が `pass`・返す節の `output_format` が約束の欄をちょうど持ち全部 `required`・`additionalProperties: false`。工程の `inputs:` が約束の入力と前提の直しの入力ちょうど。AI の節と script の節が全部 `mutates_checkout: false`。`r2-design` の `allowed_tools` が `[]`。`r2-design` と `plan-review` の `settingSources`・`sandbox`・`context: fresh` が上の値。工程の頭に `interactive`・`worktree`・`container`・`evidence_policy`・`mutates_checkout` が無い。2 つの `loop_group` の `max_iterations` が 3 で `until_bash` が受け付けの `done`。
  - 禁じた入力が R2 に届かない（持ち主の決め `independent-verdict`・`premises-purpose`）: Archon は工程の入力を全部の script に `INPUTS_*` で渡すので、`scripts/r2_prep.py` の字を読み、読む環境変数が `INPUTS_PURPOSE`・`INPUTS_JUDGMENT`・`INPUTS_START`・`INPUTS_ANSWERS`・`ARTIFACTS_DIR`・`WORKFLOW_ID` だけで、`INPUTS_PLAN`・`INPUTS_STRUCTURE`・`INPUTS_RIPPLE`・`INPUTS_UNITS`・`INPUTS_WORLD`・`INPUTS_RULING` の字が無いこと（`os.environ` を名で組んで読む書き方も無いこと）を縛る。`commands/r2-design.md` が読む節の出力は `$r2-prep.output.prompt` だけ。子のプロセスで、全部の `INPUTS_*` を置いた環境で `r2_prep` を回し、目的の文と制約の印の字が `prompt` に在り、修正案・単位の label・判定の `framing`・`one_shot`・波及の印の字が無い（入力の指し札の先にそれらを置いても届かない）。
  - 独立設計: 根拠の名指しが固めた版に無い返答を拒む・3 回目で諦めても `done`・同じ run で 2 度目の差し込み（往復の 2 回目・`replan-review`）では `open` が `r2_go: false`・目的不明か狭めている目的では回さない（元 ScriptCase の `test_design_*`・`test_independent_design_input_has_no_means`・`test_design_skipped_when_purpose_unusable`）。
  - 事前審査の受け付け: 入口の穴に `no_add` が無いと拒む・推しの形の崩れを拒む・独立設計との食い違いの穴に両方の引用が無いと拒む・design_map の欠け（元 ScriptCase・ConvergeReviewCase の `test_design_*`・QuoteFoldCase）・木の答えのまとめと項目ごとの差し戻し・束ね役の返答は要約だけ・全部 clean の往復は相乗りが要る・先行例の出典は run に 1 度だけ・余った当たりの行は捨てる・review_tree の on・off・auto（元 TreeReviewCase の事前審査の側の全部）。
  - 作業ツリーの比べ: 役の前後で作業ツリーが変わった返答を `r2_accept`・`review_accept` が拒む（元 ScriptCase の `test_readonly_tree_changed_rejected`・`test_design_tree_change_rejected`）。
  - 往復の決め（`review_accept` と `result` を往復ごとに子のプロセスで続けて回し、`converge.note_plan`・`note_answers`・`record_pass` が本物のファイルに積むのを通す）: 1 往復目の block → `pass: false`・`stalled: false`。2 往復目に同じ block（見え方の `round` はいつも 1 なので控えが捨てられない）→ `stalled: true` で関所に設計の行（`gatemarks.design_item` の止まりの行）。2 往復目に前の block の行き先（`resolved`）が書かれていない返答は拒む。3 往復目に別の block が残る → `stalled: true`（UNSETTLED）。block が消えれば `pass: true`。形 `replan`（`ruling` が空でない）は壁打ちを回さず 1 回で返り、`stalled` はいつも false で、残った block は `questions` に載る（元 `blk-plan/lib/planblk.py`:25 の「replan では壁打ちを回さない」）（元 ConvergeReviewCase の `test_persisted_review_taken_and_gate_opens_design_item`・`test_rereview_must_account_for_every_previous_block`・`test_rereview_prompt_carries_previous_blocks_and_answers`）。
  - 関所の材料（`gatemarks.plan_gate_items` を見え方で直に回す。元 `tests/test_plan_gate.py` の `GateBase` の偽の盤面を `lib/boardview.py` の見え方に置き換えて移す）: PlanGateCase・FourAxesCase・WorldGateCase の全部、LedgerAsksCase と EscalateAsksCase のうち問いが項目に載る・載らない（無人）の所、DesignOnlyCase・ConvergeGateCase、PlainSubjectCase の `test_plan_gate_text_subjects_are_plain`、QuotedQuestionCase の `test_plan_gate_quotes_mainline_question`、RequestAnswersCase・MaterialAnswersCase（`tests/test_plan_gate.py`:1025。素材の状態は見え方の `record.materials`）、`tests/test_gate_drafts.py` の PushCase。聞かずに通した行は `questions` に載らず、`review` の指し札の隣の `gate-passes.json` に出どころつきで載る。
  - 返りが返す節の `output_format` を満たす（欄と型を試験の中で照らす）。
  - 修正案の決め手が関所に届く: `p2.fix_plan.json` の narrows の行に `decided_by` などが在る時、`open` の後に `gatemarks.plan_gate_items(見え方)` がその行を聞かずに通し（自明の軸が揃う）、欄の無い行は聞く（元 PlanGateCase の `test_decided_narrow_passes_and_is_recorded`・`test_undecided_narrow_asks` を `p2.fix_plan.json` から回す）。
  - 見え方の `faces_schema` が YAML の節 `plan-review` の `output_format` の `faces`・`shrink` と同じ物。
  - 返す節が落ちない: 壊れた入力（読めない指し札・空の字・JSON でない字・ほかの run の札・在らない先・`open` も受け付けも走らず `plan-review/` が空）で `result` を子のプロセスで回し、終了の値が 0 で、`pass: false`・`ask_human: true`・訳を名指す `questions` の、`output_format` を満たす JSON を返す。
  - 筋書き: `tests/archon.py` の使い捨ての木で `archon workflow test` を回し、`fixtures/` の筋書きが全部通る（Archon の源が無ければ名前つきで見送り）。

## 返りの約束（`docs/design.md`「ブロックの返りの約束」の `plan-review` の返りのまま）

- 返す節 `review`・`outcome_field: pass`
- 入力（`with:`）:
  - `units`・`judgment`・`purpose`・`world` ← `$judge.output.<同じ名>`
  - `plan`・`structure`・`ripple` ← `$plan.output.<同じ名>`
  - （「人が入れる前提の直し」1 が入った後）`start` ← `$start.output.record`、`answers` ← `{ from: "$gate-start.output", if_skipped: null }`、`ruling` ← `$fix.output.replan_items`（`replan-review` の時だけ。`plan-review` では `[]`）
- 返り:
  - `pass`（boolean）: 止める指摘が無い（通し）→ 線 5（往復を抜ける）
  - `stalled`（boolean）: 同じ所で 2 度続けて止めた（`lib/converge`）→ 線 5（往復を止める）・report
  - `review`（指し札）: 項目ごとの指摘（review-graph の `p2.plan_review` の `faces`・`shrink`・`reason`）→ plan（次の周）・report
  - `design`（指し札）: 独立設計 R2（review-graph の `r2.design` の `question_stands`・`design`。今の works の `design.json`）→ eyes（R2 の比較）
  - `gate_axes`（object）: 4 つの軸。鍵は `obvious`（自明）・`world`（世界の解）・`clean`（汚くない）・`not_overkill`（やりすぎでない）、各 `{ok: boolean, note: string}` → 線 6
  - `ask_human`（boolean）: 修正前の関所を開くか → 線 6
  - `questions`（array of string）: 人への問い → 線 6
- 返す節の `output_format` は、上の欄をちょうど持つ（全部 `required`・`additionalProperties: false`）。欄を足す・名を変える・型を変える・欄を落とすのは線との約束を変えることなので、この PR ではしない。要ると分かったら PR の本文の「約束を変える頼み」に書き、約束どおりの形で作り終える。
- 型つきの成果物: 無し（約束に無い）。

### 返りの決め方

- `pass` = この往復の抜け方が `converge.CLEAN`（block の穴が無い）。
- `stalled` = 抜け方が `converge.STUCK`（`PERSISTED`＝前の往復の block と重なる・`UNSETTLED`＝柵の 3 往復目でも block が消えない）か、事前審査の受け付けが諦めた。柵の数は `converge.decide(passes, fence=3)`（線の `loop_group` の 3 回と同じ数）。
- 差し込みの番号 k は指し札 `plan` の先の `plan-fields.json` の `round`（置き場 `plan-review/pass-<k>/` の名に使う）。往復の控え（`converge` の `plan-converge.json`）は `plan-review/` に本物のファイルとして置き、見え方と書き先の `round` はいつも 1（同じ run の往復を 1 つの控えに積む）。run をまたいで持たない（同じ run の置き場の中だけ。待ちの列・台帳ではない）。
- 形 `replan`（`ruling` が空でない。線の `replan-review`）: 壁打ちを回さない（往復の控えに積まない）。`pass` は block が無いこと、`stalled` は false。残った block と関所の項目は `questions` に載り、線の案の直しの関所で人が見る（元 `blk-plan/lib/planblk.py`:25）。
- `review` の指し札の先（`plan-review/pass-<k>/review.json`）: 事前審査の返答の形（上の「盤面の見え方と指し札の中身の形」）。受け付けが諦めた往復は、最後の拒みの訳を `reason` に置いた同じ形（`faces`・`shrink` は空）。聞かずに通した行は隣の `plan-review/pass-<k>/gate-passes.json`（report が読む）、関所の項目の文と往復の行（`converge.lines`）は `plan-review/pass-<k>/gate.json`（このブロックの中だけ）。
- `design` の指し札の先: `plan-review/design.json`（通った返答）。無い時（諦めた・目的が使えない・回していない）は `{"missing": "<訳>"}`（訳は前提の `lib/design.py` の外した `missing` と同じ文の決まり: 諦めた・目的が使えない・控えが無い）。指し札は null にしない（約束は null 可でない）。
- `gate_axes` = `lib/gate_axes.py` の `gather(見え方)`。項目の無い軸は `{ok: true, note: ""}`。
- `questions` = `gatemarks.plan_gate_items(見え方)` の項目の文の並び（世界の解の外れ・構造の目が人に上げた問い・台帳の問い（無人の run では載せない）・設計だけの行・止まりの行を含む）。`ask_human` = `questions` が空でない。

### 既定の時（線が約束に無い入力をまだ渡さない間）

- `start` が `null`: 無人でない・設計だけでない・依頼のファイル無し（依頼の引用「…」の決め手は照らせないので人に回る）・方針の文書無し・`review_tree` は `auto`・R2 の名指しの節と地図は「渡っていない」の 1 行を貼る（`design-premises.json` の `withheld` に訳を残す）。
- `answers` が `null`: R2 に貼る人の答えは無し（`withheld` に訳）。
- `ruling` が `[]`: 開いた項目を全部審査する。
- 既定で動いた事実は `review_prep` が材料の頭に 1 行書き、PR の本文にも書く（黙って緩めない。持ち主の決め `no-silent-loosen`）。

### 盤面の見え方と指し札の中身の形

gatemarks・converge・design・planblk・policy の関数は、今の works の盤面（`b`）を引数で受ける（lib-port は書き直さずに持ってきた）。このブロックは盤面を持たないので、`open` が入力の指し札の中身から `lib/boardview.py` で同じ形の読むだけの見え方を組み、script はそれを渡すだけにする。見え方の `dir`・書き先 `place()` の `dir`・決め手の控え `gate-marks.json`・往復の控え `plan-converge.json` は全部 run の置き場の `plan-review/` の 1 つのフォルダ（書き手が書いた控えを見え方がそのまま読む）。

指し札の中身は、約束が名指す今の works のファイルの形のまま（8 本の計画で共通の決め。新しい入れ物の形を作らない。今の works が別のファイルに置いた物は、作ったブロックの置き場の同じフォルダの 2 つ目のファイルに置き、ほかのブロックは約束の指し札が名指すファイルだけを読む）:

- 受ける物: judge の `judgment` は `judge/judgment.json`（頭の欄 `units`・`questions`・`framing`・`one_shot`・`precedents`）と、同じフォルダの名指しの隣のファイル `premises.json`（実測した制約 `constraints`）と `materials.json`（素材の状態。今の works の記録の `materials`。人の直し H5（本文の「依存」））。`purpose` は `purpose.json`（`purpose_text`・`source_files`。隣のファイルは読まない）。`world` は world-row の行の並び（`worldmark.rows` が読む形）。plan の `plan` は `plan/r<k>/plan-fields.json`（`{round, fields, amended?}`。`planmarks` が読む形）と、同じフォルダの名指しの隣のファイル `p2.fix_plan.json`（修正案の役の返答。`plan[]` の `unit_keys`・`approach`・`adds`・`removes`・`shrink_first`・`narrows`（関所の決め手の欄つき）と、2 往復目からの `block_answers`）。隣のファイルは指し札の先のファイルの横にこの名で在る物だけを開き、ほかの隣のファイル（`gate-marks.json`・`replan.json` など plan の中の物）は読まない（8 本の計画で共通の決め。人の直し H5（本文の「依存」））。`structure` は `plan/.../structure-state.json`（構造の目の控え。`structmark.read` が読む形）と、同じフォルダの名指しの隣のファイル `design.jsonl`（design-row の行。`structmark.rows` が読む）。`ripple` は `ripple.json`。
- 出す物: `review` の指し札の先は p2.plan_review の返答の形（`faces`・`shrink`・`reason`・`faces_none`・`resolved`・`items`・`design_map`。faces の行の決め手の欄は残す）の `plan-review/pass-<k>/review.json`。聞かずに通した行（`gate_passes`。出どころつき。今の works の報告の冒頭に並ぶ物）は同じフォルダの隣のファイル `plan-review/pass-<k>/gate-passes.json` に置く。これは約束の一部で、report がこの名で開く（人の直し H5（本文の「依存」））。関所の項目の文・往復の控え（`converge` の `plan-converge.json`）・下請けの答えは `plan-review/` の下のほかのファイルに置き、このブロックの中だけが読む。`design` の指し札の先は `plan-review/design.json`（今の works の `design.json`。設計が無い時は `{"missing": "<訳>"}`。指し札は null にしない）。R2 に貼った物の控えは隣の `plan-review/design-premises.json`（このブロックの中だけ）。
- 修正案の核を読む訳: 事前審査（見ること 1〜8・design_map の照らし・壁打ちの block への答え）と関所の材料（narrows）は、`plan-fields.json` に無い修正案の核を読む。だから `p2.fix_plan.json` を開く（人の直し H5（本文の「依存」） が約束の `plan` の行に書き足す）。

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
- 役の節の `model:`・`effort:` は今の works の `works/.shared/core/stage-models.json` と役の前付け（`works/.shared/core/agents/`）の値を写す（持ち主の決め `model-effort`）。
- 役の指示書（`commands/`）と `lib/` に、対象の言語・テストの実行器の名を書かない（E13）。持ち主の環境の字（`raiki61`・`/Users/` など）を書かない（E14）。
- 外への書き込み（GitHub・対象のリポジトリの main・人に見える所）は、このブロックでは無い（E6）。
- ブロックの YAML と script は、ほかのブロックのフォルダを指さない（E4）。ほかのブロックの返りは `with:` の入力として受けるだけ。
- 筋書き（fixture）は Archon の `workflow test` の形（`fixtures/<名>.stubs.yaml`。予約の鍵 `fixture:`（`expect`・`fail-node`・`reached`・`inputs`・`resolved-text-contains`）と `exec-code:`、残りの鍵は節の id → 差し替えの出力）。script の中身まで通したい筋書きは `exec-code: true`。
- ブロックの YAML の形の試験（`tests/workflows/test_<名>.py`）は PyYAML で YAML を読み、Archon を起こさない。筋書きは同じ `tests/workflows/test_plan_review.py` が、issue #47（P0） の `tests/archon.py` で回す（`workflows/plan-review/` と `.shared/` だけを置いた使い捨ての木で `archon workflow test`。止めた Archon の源が無ければ `tests/archon.py` が `skipTest("Archon の源が無い: ...")` で名前つきで見送る）。

## Archon で書けない所

- 束ね役が下請けを本当に起こしたかの読んだ証拠（今の works の `reads` の trace の起動の数。元 TreeReviewCase の `test_reads_trace_agent_launches_against_item_files`）は、今の works の包みが取っていた。Archon の役の節で取れるかは未決 U6。この PR は、項目ごとの答えのファイルが在り機械の照らしを通ることだけを縛り、起動の数の照らしは「U6 待ち」と PR に書く。
- 独立設計の隔離: 今の works の包みは道具ゼロの役を Git の外の置き場で起こし、作業ツリーの git の様子（枝・最近の commit）を役の system prompt に入れなかった（`r2.design` の禁: リポジトリ・履歴）。この PR は今の works の `settingSources: [user]`・`sandbox`・`context: fresh` を写す。それで作業ツリーの git の様子まで外れるかを止めた Archon の源で確かめる。外せなければ埋めの候補で、`workflows/.shared/` は守りのパスなので作らず、PR の本文の「使いたかった埋め」に書く（`docs/polyfills.md` の行の形で）。
- 項目ごとの並べ: 項目の数は run の時に決まるが、`fan_out:` は `include:`・`workflow:` の節の欄で、1 つのフォルダに工程は 1 つ（E9・Archon の packaged workflow）なので、役の節を項目ごとに並べられない。今の works と同じく束ね役が Agent の道具で下請けを並べる（埋めは要らない）。

## E11 の 3 つの答え

1. Archon が持っているか: 型の照らし（`output_format`）・読むだけの守り（`mutates_checkout: false`）・受け付けの出し直しの輪（`loop_group` と `until_bash`）・道具の制限（`allowed_tools`）は Archon で書く。往復の決め・4 つの軸・独立設計の引用の照らし・木の答えのまとめは Archon に無いので lib/ の関数。
2. ASF が持っているか: `W/review/archon-review.yaml` の読むだけのレンズ → まとめ役の形と `returns`・`outcome_field`。項目ごとの下請けと独立設計は ASF に無い（今の works の能力）。
3. 本当に要るか: 能力の棚卸しの「独立設計 R2」「事前審査（項目ごとの木）」「壁打ちの往復」「修正前の関所の 4 つの軸」「人の方針の文」の行と、受け入れの一覧の `p2.plan_review`・`r2.design`・`p2.human_gate`。

## 受け入れ

1. 試験を先に入れて赤を見る（lib/ の部品が無い・YAML が無い）。その後で部品と YAML を入れて緑。赤と緑の出力の要約を PR に書く。
2. リポジトリの根からの全部の試験 `uv run --isolated python3 -m unittest discover -s . -t .` が緑。`tests/layers/` の層の試験（その時に在る物全部）も緑のまま。
3. Archon の実行ファイル（か源）が在る所で `archon workflow test workflows/plan-review` の筋書きが全部通る。在る所で `archon validate workflows` に `works-factory-plan-review` の誤りも警告も無い。Archon が無い所では、筋書きを回す試験は名前つきで見送られる（`tests/workflows/test_plan_review.py` が `tests/archon.py` を通して `skipTest("Archon の源が無い: ...")`）。PR には、Archon で回した結果か、回せなかった訳を書く。
4. このブロックは今の works のファイルを lib/ に持ってこない。新しく書いた `lib/gate_axes.py`・`lib/boardview.py` は docstring に元の `<パス>:<行>` を書き、(b) の形として PR に並べる。
5. PR の本文に次を並べる（守りのパスの文書に書く代わり。土台の持ち主が `docs/design.md`・`docs/asf-notes.md` に写す）:
   - 書き直し（(b) の形）の一覧: `lib/gate_axes.py`・`lib/boardview.py` の関数ごとの元の `<パス>:<行>`
   - 採った ASF の型（`docs/asf-notes.md` の「書き方」の 4 行の形）
   - 「能力の棚卸し」と「受け入れの一覧」のこのブロックの行ごとの、証の試験か筋書きの名
   - 約束を変える頼み・使いたかった埋め（あれば）
6. design.md の段 2 の plan-review の個別の行: R2 の独立設計は道具なしで目的の文だけを受ける（禁じた入力が届かないことを `tests/workflows/test_plan_review.py` で縛る）。4 つの軸と人への問いを返す。往復の止め（同じ止めが 2 度・3 往復の柵）が `stalled` として働く（3 回の上限そのものは線の `loop_group`）。
7. 今の works の試験のうち、上の「試験」で名指したクラスの場面が全部、盤面なしの形で戻っている（名の対応表を PR に書く）。plan-review の外に置いた場面（R4GateCase・R4PushTailCase・FinalHeadCase・AskGateCase・ReportHeadCase・DraftsCase・答えで直す義務に戻る単位）は、このブロックでは持ってこず、渡し先を PR の本文に名指す: R4GateCase・R4PushTailCase・FinalHeadCase → eyes と線（最後の関所）、AskGateCase の関所の文の頭の 3 行 → 線 6、ReportHeadCase・DraftsCase → report、答えで直す義務に戻る単位（LedgerAsksCase・EscalateAsksCase の一部）→ fix（conflict）。

## 範囲

- 作るのは `workflows/plan-review/` の下・本文の「lib/ に持ってくる部品」の lib/ のファイル・本文の「試験」のファイルだけ。
- 触らない（守りのパス。ASF の merge が人の手に残す）: `workflows/line/**`・`workflows/.shared/**`・`docs/design.md`・`docs/owner-decisions.md`・全部の `AGENTS.md`・`pack.json`・`README.md`・`MISSION.md`・`engineering.md`・`.github/**`・`harness/**`・`factory/**`・`.factory/**`。
- 触らない（同じ時に別の run が作る）: ほかの 7 つのブロックのフォルダ（`workflows/<ほかの名>/`）と、それらの issue が名指す lib/・試験のファイル。ほかの PR と同じファイルを作らない。
- 触らない（前に入る物）: lib-port と`docs/plans/2026-10-12-blocks/prereq.md` の issue で入った lib/ のファイル（本文の「依存」に並べた物）とその試験、`tests/workflows/__init__.py`・`tests/archon.py`、`pyproject.toml`、`docs/`（PR の本文に書く。上の受け入れ 5）。持ってきた部品の中で前提の部品に直しが要ると分かったら、直さず PR の本文に書く。
- 決めた範囲で能力を落とす直しが要ると分かったら（持ち主の決め `superset`・`no-narrow`）、止めて PR の本文に書く。

- このブロックが作るファイル（ちょうどこれだけ）:
  ```
  workflows/plan-review/**
  lib/gate_axes.py
  lib/boardview.py
  lib/tests/test_gate_axes.py
  lib/tests/test_boardview.py
  tests/workflows/test_plan_review.py
  ```
  `workflows/plan-review/` の中身: `works-factory-plan-review.yaml`・`commands/r2-design.md`・`commands/plan-review.md`・`scripts/pass_open.py`・`scripts/r2_prep.py`・`scripts/r2_accept.py`・`scripts/review_prep.py`・`scripts/review_accept.py`・`scripts/result.py`・`fixtures/pass.stubs.yaml`・`fixtures/block.stubs.yaml`・`fixtures/stalled.stubs.yaml`・`fixtures/ask-human.stubs.yaml`・`fixtures/r2-skipped.stubs.yaml`・`fixtures/r2-give-up.stubs.yaml`・`fixtures/review-give-up.stubs.yaml`。名の頭は `factory`・`FACTORY`・`harness`・`.factory`・`archon-` のどれでもない（E18 の機械の行）。script の名は lib のモジュールの名と同じにしない（script のフォルダが `sys.path` の頭に来るので、同じ名だと lib の物を隠す）。
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

- `docs/plans/2026-10-12-blocks/prereq.md` の issue（ブロックの前の共有の部品。このブロックより先に main に入る）: `lib/design.py`・`lib/policy.py`・`lib/planblk.py`・`lib/ripple.py`・`lib/impact.py`・`lib/changemap.py`・`lib/rolekit.py`（出し直しの小道具 `with_done`・`rejected`・`given_up_reason`・`with_reject`・`GIVE_UP_AFTER` だけ）と、それらの試験・`tests/workflows/__init__.py`。issue #47（P0）（`docs/plans/2026-10-12-blocks/prereq.md` の issue より先に main に入る）: `tests/archon.py`（止めた Archon の源と bun を見つけ、無ければ名前つきで見送り、名指した工程のフォルダと `.shared/` だけを `.archon/workflows/works-factory/` に置いた使い捨ての git の木で、使い捨ての `ARCHON_HOME` と `WORKS_FACTORY_ROOT` で Archon を回す）・`place.workflow_source` の pack の置き方・U5（`boundary.lib_root()` が `WORKS_FACTORY_ROOT` を読む）・CI での Archon の源と bun の取り寄せ。P0 と`docs/plans/2026-10-12-blocks/prereq.md` の issue は、このブロックのフォルダが Archon の packaged workflow（pack `works-factory`・工程のフォルダ `plan-review/`）として読まれる置き方（`--workflow-source` に渡す置き場）と、未決 U5（止めた Archon が run の始めに写した工程の源から script を走らせる時に、`boundary.lib_root()` で lib/ に届くこと）を、本物の `--dry-run --exec-code` で lib のモジュールを読んで決める。このブロックの script は `boundary.lib_root()` を呼ぶだけで、置き方を知らない。`docs/plans/2026-10-12-blocks/prereq.md` の issue は、このブロックが呼ぶ盤面を受ける関数を次の継ぎ目つきで残す（無ければこのブロックを回さない）: `planblk.answers_dir` の `adapter.run_place_of(...)` → `pathlib.Path(b.dir)`・`planblk._review_rules` の `rolekit.render_body(...)` → 見え方の `review_body`・`planblk.design_section` の `b.stop(...)` を外して `BoardGap` を上げるだけ・`planblk` と `design` の `BoardGap`（`board` の例外）→ lib の例外・`planblk._faces_schema` の `output_format("plan-review")`（`accept.role_schema` と `node_marker`）→ 見え方の `b.faces_schema`・`design.missing` の `rolekit.given_up_reason` → 前提の `lib/rolekit.py` の同じ名。
- main に在る物（lib-port の PR）: `lib/gatemarks.py`・`lib/answer.py`・`lib/converge.py`・`lib/marks.py`・`lib/planmarks.py`・`lib/structmark.py`・`lib/concepthome.py`・`lib/worldmark.py`・`lib/cite.py`・`lib/startrec.py`・`lib/gatepolicy.py`・`lib/carry.py`・`lib/promptsection.py`・`lib/stopby.py`・`lib/accept.py`・`lib/graphloops/engine/`（util・schema・pointers・render）・`lib/tests/test_plan_gate.py`（定数）・`lib/tests/test_gate_drafts.py`。`workflows/.shared/boundary.py`。
- 人の直し: 下の「人が入れる前提の直し」1・2 と、全部のブロックに共通の直し（人の直し H1〜H5（本文の「依存」）。`tests/workflows/` を木に載せる H1、`plan` の指し札の隣の `p2.fix_plan.json` と `review` の指し札の隣の `gate-passes.json` を約束に書く H5）。H5 が main に入ってから回す（修正案の核を読む形が約束になるため）。
- ほかのブロック: 待たない。ほかのブロックの返りは線の `with:` で入力として届くだけで、このブロックの試験はその形の入力を筋書きと試験の中で作る。指し札の中身の形（「盤面の見え方と指し札の中身の形」の節）は judge と plan の issue と同じ今の works のファイルの形。

## 人が入れる前提の直し

全部のブロックに共通の直しは 本文の「依存」の前に入る物（H1〜H5）。このブロックだけの物:

1. `docs/design.md` の「ブロックの返りの約束」の「plan-review の返り」の「入力（`with:`）」に次の 3 行を足す（線の `plan-review`・`replan-review` の include も同じ入力を渡す）。この直しの前でもブロックは既定の値で動く（上の「既定の時」）:
   ```
     - `start` ← `$start.output.record`（無人の印・設計だけ・依頼のファイル・方針の文書・事前審査の木の既定・固めた版。関所の材料と R2 の名指しの節が読む）
     - `answers` ← `{ from: "$gate-start.output", if_skipped: null }`（R2 に貼る人の関所の答え）
     - `ruling` ← `$fix.output.replan_items`（`replan-review` の時だけ。`plan-review` では `[]`。裁かれた項目だけを審査する）
   ```
   訳: 今の works の事前審査と修正前の関所の材料は、始めの記録（`gatepolicy.unattended`・`design_only`・依頼のファイルの引用の照らし `gatemarks._cite_check`・方針の写し `policy.brief`・`review_tree`）と人の関所の答え（R2 の `design.human_answers`）を読む。無いと、無人の run で問いを載せない決まり・設計だけの run・依頼の引用の決め手・方針とのぶつかり（kind=policy）・R2 の名指しの節と人の答えが落ちる（持ち主の決め `superset`）。
2. `docs/design.md` の「能力の棚卸し」の「plan・plan-review」の行「事前審査（項目ごとの木）: `blk-plan` の `plan-review-loop`・`holeties.py` → plan-review・`commands/plan-review`」を「事前審査（項目ごとの木）: `blk-plan` の `plan-review-loop`・`blk-plan/lib/planblk.py` の木の部分 → plan-review・`commands/plan-review`」に直し、「fix」の「差分の審査・レンズ・手直し」の行の元に `holeties.py` を足す（holeties は差分の審査の穴の名札で、refix と report が読む）。回すのは止めない。
