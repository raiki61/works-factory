# 設計書（下書き）: spec-driven（仕様駆動の道）

- 何の話か: 人と固めた仕様を渡して実装させる道（仕様駆動の道。issue #802）の設計書の下書き。1〜3 章は issue の「進め方」の 1 と 2（世の中の仕様駆動の 5 つの形との比べ・仕様に入れる物・持ち主の答え）。6〜9 章は進め方の 4〜6 の設計（本線への差し込み・修正の部品への入力・入口の確かめの細目・keep-essence の 7 の形）と、仕様を固める会話から部品を単独で呼ぶ形を本物の run で試した結果（2.5）。block のフォルダと試験のコードは、この設計書が main に入った後に書く。読む人は持ち主と実装の役。持ち主への問いは全部答えが出た（10 章）。
- 決めたこと: 仕様は #765 の組み直しの設計書くらいの粒度で、設計書（Markdown）と機械が確かめる表（目的・受け入れの条件・試験のコマンド・触らない物の 4 つだけ）の 2 つにする。ファイルごとの行は仕様に書かず、run の中で計画の AI が 1 回だけ起こす。計画と計画の審査の往復は、仕様を固める会話の中で部品を単独で必ず回し、その記録を表に添える。run の入口で機械が形と記録を yes/no で確かめ（記録は起動の殻が Archon の run の記録と照らす）、欠ければ AI を起こさずに止まる。この道は判定と計画の往復を飛ばす道ではなく、その繰り返しに人を混ぜる道で、会話の中で回した往復を工場の中で回し直さない（持ち主の決め `spec-driven-shape`）。道は別の graph にせず、本線 `works-factory-line` に入口を 1 つ足す。工場の中では、今の本線の判定と計画の往復（何周も回す形）を回さず、その代わりに、AI を持たない block `works-factory-spec-driven`・判定の役 diagnose・計画の部品 plan を 1 回ずつ通して修正の入口 `fix-in` へつなぐ（6 章）。新しい AI の役は作らない。直し 1 件ごとの差分の仕様（OpenSpec の ADDED/MODIFIED/REMOVED）は採らない。
- 持ち主に求めること: なし。前の版で聞いた 3 つは答えが出た。表の書式と block の形は工場窓口の答え（2026-10-21、受付 20261020-224412-ca616a）、審査の記録を本物の run の記録と照らすかは持ち主の答え（2026-10-21、案 A〔照らす〕。持ち主の決め `spec-driven-shape`）で決まった（10 章）。
- 読む人: 持ち主と、進め方の 4〜7 を進める設計と実装の役。設計と実装の役は、6〜9 章に沿って実装の PR を書き、末尾の未確認の一覧の物をその PR で決める。持ち主は、自分の答えがどう写ったかを 10 章で引く（求めることは無い）。

この文書の語は [README.md](README.md) の頭の物を使う。ほかに:

- 仕様駆動の道: 人と固めた仕様を入力にして修正へ進む道。判定と計画の往復を飛ばすのではなく、その繰り返しの中に人を混ぜる（持ち主の言葉「１と２を飛ばすんじゃなくて、１と２に人を混ぜる」。1 は判定、2 は計画と計画の審査の往復）。計画と計画の審査の往復は人と一緒に会話の中で回し、判定の役は工場の中で 1 回回し、工場の中で同じ事を 2 度回さない。本線 `works-factory-line` の入力 `spec_table` から入る（6 章）。道の入口の機械の確かめと、仕様とリポジトリの食い違いの照らしは block `works-factory-spec-driven`（フォルダ `workflows/spec-driven/`。5 章の 1）が持つ。計画と計画の審査の往復は、run の前の仕様を固める会話の中でする。
- 人の仕様: 持ち主（か利用者）が AI と会話で固め、仕様駆動の道に渡す物。設計書と機械が確かめる表の 2 つ（2 章）。
- 仕様を固める会話（壁打ち）: 人と会話の AI が人の仕様を固める会話。会話の AI が工場の部品を単独の run で呼んで仕様を審査させる（2.3）。
- 計画の行: 計画の部品 `workflows/plan/` の修正案の役が返す `plan[]` の項目（`workflows/plan/works-factory-plan.yaml` の `output_format`）。ファイルの行はその中の `files[]`（`path`・`op`・`responsibility`・`symbols`・`home`・`considered`）。
- `narrows`: 計画の行の欄。直しが今の能力を狭める所（機能を外す・許す範囲を減らすなど）を 1 行ずつ名指し、行ごとに、それを決めた所 `decided_by`（人の答えや設計書）か、まだ決まっていない訳 `undecided_because` を持つ（持ち主の決め `no-narrow`。[plan.md](plan.md)）。
- 目的の外の行: 判定の役が、表の目的と受け入れの条件の外にあると判断した依頼の行（返りの `out_of_purpose`）。表の「触らない物」（`out_of_scope`）とは別。
- 単位: 判定が出す直す単位（根本の欠陥 1 つ分）。計画の行は `unit_keys` で単位を指す。
- 候補の 5 つ: GitHub Spec Kit・OpenSpec・Kiro（AWS の IDE）の EARS 記法・superpowers の writing-plans・BMAD-METHOD。EARS は要件を「WHEN <きっかけ> THE SYSTEM SHALL <振る舞い>」のような決まった型の英語の 1 文で書く記法（1.2 の「受け入れの条件」）。
- 判定: 本線（メイングラフ `works-factory-line`）の頭の段。依頼を直す単位に割り、決まっていない点を人に問い返す（graph `works-factory-judge`）。
- 憲法の 3〜6: 根の `AGENTS.md` の憲法（[README.md](README.md) の 2 章）。3 は「block は宣言した port だけで受け渡しし、ほかの block を名指さない。つなぐのは graph だけ」、4 は「1 つの block だけが使うコードは、その block のフォルダに置く」、5 は「どの block も、文とリポジトリだけで単独で回る」、6 は「機械の検査は yes/no の形の決まりだけにする」。
- この文書が引く E の番号: E3 は「`lib/` は Archon を知らず、run の中の script のノードは外のパッケージを持たない」（`lib/AGENTS.md`）、E7 は「`runtime: uv` の script は依存を宣言しない（`dependencies = []`）」ほか（`workflows/AGENTS.md`）、E8 は「ASF と Archon 同梱の graph を呼ばない」、E9 は「graph の名は `works-factory-<フォルダの名>`」、E10 は「新しい置き場や仕組みは、先に持ち主の決めを `docs/owner-decisions.md` に書いてから足す」、E11 は「仕組みを足す前に、Archon が持つか・ASF が持つか・本当に要るかの 3 つを確かめる」、E22 は「層は `docs/layers.json` の地図に沿って頼る。殻の事実は殻が組んで env で渡す」（E8〜E11・E22 は根の `AGENTS.md`）。
- ASF: Archon の作者が作った、作業の受け付けから merge までの graph の束（[archon.md](archon.md) の語）。工場は横に並べて見比べるだけで、呼ばない（E8）。
- 工場窓口: 持ち主と会話して、工場への頼みを書いて渡し、持ち主に問いを取り次ぐ会話の AI。持ち主その人ではないので、工場窓口が書いた頼みや答えは持ち主の言葉と分けて書く。
- 部品: block の別の呼び名（README の頭の「単独で呼べる部品（block）」）。計画の部品は block `works-factory-plan`、修正の部品は `works-factory-fix`、計画の審査は `works-factory-plan-review`。
- 穴と重さ: 計画の審査が挙げる指摘 1 つを穴と呼び（返りの `faces` の 1 行）、重さ（`severity`）は `block`（直すまで修正へ進めない穴。部品の block とは別の語）か `suggest`（勧め）（[plan-review.md](plan-review.md) の語）。
- issue と PR の番号: #765 は部品の作り直し（[README.md](README.md) の型を決めた issue。「組み直しの設計書」はその時の `docs/design/<部品>.md`）、#802 はこの道の issue、PR #807 はこの文書の 1〜3 章と持ち主の決め `spec-driven-shape` を入れた前の PR、PR #809 はこの文書の 2.5・2.6・6〜10 章を足す PR（「この PR」と書く物）。
- 世界の解: block `works-factory-world`。依頼の各行と同じ類の問題を、世の中がどう解いているかを一次の出典で調べ、依頼の解き方と比べる（[world.md](world.md)）。返りの `versus.verdict` は定石と同じ（`same`）か違う（`differs`）か。
- keep-essence の N: [README.md](README.md) の 10 章の、作り直しで守ると決めた 12 の仕組みの N 番。7 は class_query の数え直し（5 章の 6）、12 は世界の解。

## 1 仕様の形の比べ

### 1.1 読んだ出典

どれも 2026-10-21 に読んだ。リポジトリは浅い clone か raw の取得で、コードは走らせていない。

- GitHub Spec Kit: commit `6ad208241af0b94b2dc22b5c0534a9a82465bf0a`。`templates/spec-template.md`・`plan-template.md`・`tasks-template.md`・`templates/commands/specify.md`・`clarify.md`・`analyze.md`・`implement.md`（関わる所）・`docs/guides/evolving-specs.md`。出典の頭は `https://github.com/github/spec-kit/blob/6ad208241af0b94b2dc22b5c0534a9a82465bf0a/`。
- OpenSpec: commit `c794978f4f8845ce59693373c9dd882ee776588c`。既定の流れ `schemas/spec-driven/schema.yaml` と `templates/`・検査 `src/core/validation/validator.ts`・`constants.ts`・合わせ込み `src/core/specs-apply.ts`・`docs/concepts.md`。出典の頭は `https://github.com/Fission-AI/OpenSpec/blob/c794978f4f8845ce59693373c9dd882ee776588c/`。
- Kiro: 文書 https://kiro.dev/docs/specs/ とその下（`feature-specs/`・`feature-specs/requirements-first/`・`analyze-requirements/`・`correctness/`・`best-practices/`・`bugfix-specs/`・`quick-spec/`。字は `.md` の版で読んだ）と、Kiro が自分のリポジトリで作った仕様の見本 https://github.com/kirodotdev/Kiro/tree/main/.kiro/specs/github-issue-automation 。EARS は https://alistairmavin.com/ears/ 。
- superpowers の writing-plans: commit `bb92a77741419a4ab5f06e711a283343f1ada0c3`（`lib/borrow/borrow.json` が止めた 7.0.0 と同じ。手元の写しに writing-plans は無いので上流を読んだ）。`skills/writing-plans/SKILL.md`・`skills/executing-plans/SKILL.md`・`skills/brainstorming/SKILL.md`。
- BMAD-METHOD: 本流 commit `61e01f82644c4bb533750cfa0d6d61ab61d2cc9b`（v7 の下書き）・v6.12.0 `05bfbd46d00766ec88eb9b42e76be2c575d64d7b`・v4.44.3 `4c4f6dc8534f95427e66e122ac5de47ac51b5f94`。版ごとに置き場と形が大きく変わったので 3 つとも読んだ。本流で消えた物（story の雛形・readiness の照らしなど）は v6 か v4 から引く。

読めなかった物:

- EARS の元の論文（Mavin ほか、RE'09）は読んでいない。EARS の型は著者のページから引いた。
- Kiro の文書は、生成される `requirements.md`・`design.md`・`tasks.md` の全文の見本を載せていない。全文の形は上の見本の仕様 1 つから引いた。
- BMAD の v6 の epic を作る流れ（受け入れの条件が Given/When/Then か）は読んでいない。

### 1.2 候補ごとの在る・無い

表の値の訳と、根拠にした一句は表の下に書く。「工場」は今の工場の同じ役の物。

| 項目 | Spec Kit | OpenSpec | Kiro | writing-plans | BMAD | 工場 |
| --- | --- | --- | --- | --- | --- | --- |
| 目的 | 散らばる | 在る | 在る | 在る | 在る | 在る |
| ファイルの行 | 作業の行の中 | 自由な文 | 作業の行の中 | 在る | 在る | 在る |
| 受け入れの条件 | G/W/T | WHEN/THEN | EARS | 試験のコード | G/W/T | G/W/T |
| 試験のコマンド | 無い | 無い | 無い | 段ごと | 在る | 在る |
| 触らない物 | 無い | 任意 | 無い | 無い | 在る | 在る |
| あいまいな点 | 1 問ずつ | 先に聞く | 承認の関門 | 書かせない | 1 件ずつ | 判定が問う |
| 実装の前の照らし | 助言だけ | 形だけ | 要件だけ | 自分で | 関門 | 計画の審査 |
| 差分の仕様 | 無い | 在る | 無い | 無い | 決めの行 | 無い |
| TDD の印 | 頼めば | 無い | 任意の印 | 全部 | 版による | 単位ごと |

G/W/T は Given/When/Then。

#### 目的

- Spec Kit: 仕様の雛形に目的の見出しは無く、依頼の文（`User description: "$ARGUMENTS"`）・話ごとの `Why this priority`・成功の基準（「These must be technology-agnostic and measurable.」`templates/spec-template.md`）に散る。
- OpenSpec: 提案の `Why`（「1-2 sentences on the problem or opportunity.」`schemas/spec-driven/schema.yaml`）。`validate --strict` が 50 字未満を短すぎると言う（`constants.ts` の `MIN_WHY_SECTION_LENGTH = 50`）。
- Kiro: 見本の仕様が `## Introduction` で始まり、要件ごとに「As a repository maintainer, I want …, so that …」の利用者の話を持つ（この形は文書には無く見本だけ）。
- writing-plans: 「**Goal:** [One sentence describing what this builds]」（`skills/writing-plans/SKILL.md`）。
- BMAD: 本流の PRD の `## 1. Vision`（「what this is, what it does for the user, why it matters」`skills/bmad-prd/assets/prd-template.md`）。v4 は `Goals and Background Context`。
- 工場: 独立設計（`works-factory-independent-design`）と世界の解（`works-factory-world`）の入力 `purpose`（目的の 1 文）。

#### ファイルの行

- Spec Kit: 仕様にパスを書かせない（「Avoid HOW to implement (no tech stack, APIs, code structure)」`specify.md`）。パスは作業の行の中だけ（「Include exact file paths in descriptions」`tasks-template.md`）で、作る/直すは動詞の字に埋もれ、ファイルごとの受け持ちは無い。
- OpenSpec: 提案の `Impact`（「Affected code, APIs, dependencies, or systems.」）。形は自由で、作る/直す/消すの印も検査も無い。
- Kiro: 作業の行がファイルの名を持つ（「2.1 Create data models module (`data_models.ts`)」見本の `tasks.md`）。作る/直すの印は無い。
- writing-plans: 冒頭のファイル構成（「map out which files will be created or modified and what each one is responsible for.」）と、作業ごとの `Create:`・`Modify: path:123-145`・`Test:` の行。
- BMAD: 本流の計画の雛形の `## Code Map`（「`FILE -- ROLE_OR_RELEVANCE`」`skills/bmad-build/plan-template.md`）と、作業の形「`FILE` -- ACTION -- RATIONALE」。v4 の story は実装の後に作った・直したファイルを `File List` に書く。
- 工場: 計画の行の `files[]`（`path`・`op` create/modify/delete/rename・`responsibility`・`symbols`・`home`・`considered`）。#568 で業界の「ファイル構成」の行に置き換えた物。

#### 受け入れの条件

- Spec Kit: 話ごとに番号つきの「**Given** [initial state], **When** [action], **Then** [expected outcome]」と、`FR-001` の「System MUST …」。「Each requirement must be testable」（`specify.md`）。
- OpenSpec: 要件は SHALL/MUST で書き、「Every requirement MUST have at least one scenario.」。場面は `#### Scenario:` の WHEN/THEN（`schema.yaml`）。場面が無い要件は `validate` の誤り（`constants.ts`）。「each scenario is a potential test case」。
- Kiro: 「WHEN [condition/event] THE SYSTEM SHALL [expected behavior]」と「Each requirement can be directly translated into test cases」（`feature-specs/`）。文書が示すのは出来事の型だけで、EARS の残りの型（While・Where・If/then・組み合わせ）は著者のページにある（「While <precondition(s)>, the <system name> shall …」）。
- writing-plans: 受け入れを試験のコードで書く（「**A test step:** the test's name and its assertions, as code, with the spec's exact values in them.」）。
- BMAD: 本流の ticket の雛形が要件の番号つきの Given/When/Then（「**Given** … **When** [the one action] **Then** …」`skills/bmad-agent-po/assets/ticket-template.md`）。v4 は番号だけで G/W/T でない。
- 工場: 仕様の部品 `workflows/spec/` が要件ごとの受け入れ条件を、中に Given/When/Then を持つ試験として対象に書かせる（[spec.md](spec.md) の 1.1）。計画の行の `tests[]` は `id`（`path::名`）・`behavior`・`red_kind`。

#### 試験のコマンド

- Spec Kit: 雛形に無い。計画の `Testing` は枠組みの名だけ（「**Testing**: [e.g., …]」`plan-template.md`）。
- OpenSpec: 無い。作業ごとに確かめ方を書かせるだけ（「Each task MUST state how to verify completion (a test, command, observable behavior, or delivered artifact).」）。
- Kiro: 仕様の文書に無い。
- writing-plans: 段ごとにコマンドと期待の出力（「**A verification step:** the command to run and the output that means it passed.」）。
- BMAD: 本流の計画の雛形の `## Verification` の「**Commands:** - `COMMAND` -- expected: SUCCESS_CRITERIA」。
- 工場: line の入力 `test_cmd`（人が渡すテストのコマンド 1 行）を試験の段（[test-gate.md](test-gate.md) の 1.2）が受ける。空なら工場が実行器を用意する。

#### 触らない物

- Spec Kit: 見出しは無い。前提の例の 1 行（「Mobile support is out of scope for v1」）と、clarify の照らしの分類「Explicit out-of-scope declarations」だけ。
- OpenSpec: 任意の `design.md` の `Non-Goals`（「What is explicitly out of scope」）。
- Kiro: 無い。不具合の仕様の「Unchanged Behavior (Regression Prevention)」が近い。
- writing-plans: 無い（「DRY. YAGNI. TDD. Frequent commits.」の標語だけ）。目標の外は brainstorming の設計の文書が持つ（「goals, non-goals, anti-goals」）。
- BMAD: 本流の PRD の `## 5. Non-Goals (Explicit)`（「prevents the 'let me also add this nearby thing' failure mode」）と、計画の雛形の「**Never:** NON_GOALS_AND_FORBIDDEN_APPROACHES」。
- 工場: 計画の行の `out_of_scope[]`（`glob`・`why`）と `allowed_paths[]`。修正の部品は範囲の外を書く前に相談させる（`workflows/fix/src/consult.py`）。

#### あいまいな点

- Spec Kit: 仕様を作る時は `[NEEDS CLARIFICATION: …]` を多くて 3 つ、まとめて選択肢の表で聞く（「Present all questions together before waiting for responses」`specify.md`）。`clarify` は多くて 5 問を 1 問ずつ聞き（「Present EXACTLY ONE question at a time」）、勧める答えを添え、答えを仕様の `## Clarifications` の `### Session YYYY-MM-DD` に「`- Q: <question> → A: <final answer>`」で書き戻す（`clarify.md`）。
- OpenSpec: 範囲・外から見える振る舞い・受け入れの条件を変えるあいまいさは、作る前に人に聞く（「ask the user before creating the change」`src/core/templates/workflows/propose.ts`）。`design.md` の Open Questions は先へ送れる物だけで、仕様を変える問いは「resolve it now」。
- Kiro: 段ごとの承認の関門（「Once you confirm the requirements, Kiro generates a `design.md`」）。Quick Spec は関門の代わりに問いを先に全部聞く。
- writing-plans: 決めない行を書かせない（「Lines that decide nothing ("TBD", …) are the opposite failure」）。
- BMAD: 本流の PRD の推測を `[ASSUMPTION: …]` で印し、前提の索引に集める。止める問いは「surfaced one at a time and resolved」（`skills/bmad-prd/SKILL.md`）。
- 工場: 判定が決まっていない点を人に問い返す。計画の `narrows`（能力を狭める物）は修正の前に人に聞く。

#### 実装の前の照らし

- Spec Kit: `analyze` は読むだけ（「**STRICTLY READ-ONLY**: Do **not** modify any files」）。重複・あいまい・書き足りない・決まりとのずれ・網羅の穴（作業の無い要件、要件の無い作業）・食い違いを CRITICAL〜LOW で出す。実装は止めない（`implement.md` は analyze を名指さない）。
- OpenSpec: `validate --strict` は文書の形と、本体の仕様との突き合わせ（MODIFIED が今の場面を落としていないか）だけ。コードとは照らさない。コードと照らす `/opsx:verify` は実装の後。
- Kiro: Analyze Requirements が設計の前に要件の「logical inconsistencies, ambiguities, conflicting constraints, and gaps」を問いにして返す。任意で、要件・設計・作業の突き合わせは無い。
- writing-plans: 書き手の自分の照らし（「**1. Spec coverage:** … Can you point to a task that implements it? List any gaps.」）。別の役は立てない（「not a subagent dispatch」）。
- BMAD: v6 の readiness の関門が PASS/CONCERNS/FAIL を出し、要件と story を両向きにたどる（「flag orphans in both directions」`src/bmm-skills/plan/bmad-sprint-planning/references/readiness-gate.md`）。
- 工場: 計画の審査（`works-factory-plan-review`）が写し・入口・契約のずれ・死んだ道・範囲の膨張・後退・方針・先行例の出典の 8 つの観点で、リポジトリと照らして穴を挙げる。

#### 差分の仕様

- Spec Kit: 無い。機能ごとにフォルダを作り（「You must only create one feature per … invocation」）、出した機能を直す形は 3 つの慣習を並べて「None is required or the default」（`docs/guides/evolving-specs.md`）。
- OpenSpec: 在る。直し 1 件のフォルダの差分の仕様に `## ADDED Requirements`・`MODIFIED`（「MUST include full updated content」）・`REMOVED`（「MUST include **Reason** and **Migration**」）・`RENAMED`（FROM:/TO:）を書き、終わったら「RENAMED → REMOVED → MODIFIED → ADDED」の順に本体の仕様 `openspec/specs/` へ合わせ込む（`src/core/specs-apply.ts`）。
- Kiro: 無い。仕様をその場で直し、作業の一覧を Sync Files で合わせる（`best-practices/`）。
- writing-plans: 無い。
- BMAD: 本流は差分の文書を作らず、日付つきの `Decision:` の行を残す（「No proposal file.」`skills/bmad-agent-po/references/replan.md`）。v4・v6 は Sprint Change Proposal を書いた。
- 工場: 無い。対象のリポジトリに本体の仕様の置き場を持たない。

#### TDD の印

- Spec Kit: 試験は頼まれた時だけ（「Tests are OPTIONAL - only include them if explicitly requested in the feature specification.」）。在れば先に書いて赤を見る。作業ごとの印は無い。
- OpenSpec: 既定の流れに TDD の語が無い。
- Kiro: 試験の作業に任意の印 `*` を付け（「Tasks marked with `*` are optional」見本の `tasks.md`）、Run all Tasks は必須の作業だけを回す。
- writing-plans: 全部の作業が TDD（「"Write the failing test" - step / "Run it to make sure it fails" - step / …」）。
- BMAD: v4 は実装の後に試験、v6 は赤・緑・整理、本流は開発の役の人柄の文にだけ在る。
- 工場: 計画の行ごとに `route`（`tdd`・`direct`）。今は TDD の役が単位ごとに振り分ける（[fix.md](fix.md)）。

### 1.3 採る・採らない

3 章の持ち主の答えの後の形で書く。答えの前の案から変えた所は、訳の終わりに「答えで変えた」と書いた。

| 項目 | 決め | 元にした形 |
| --- | --- | --- |
| 目的 | 採る（表） | writing-plans・OpenSpec |
| 設計の文 | 採る（設計書） | #765 の設計書 |
| ファイルの行 | 仕様に書かない | ― |
| 受け入れの条件 | 採る（表） | G/W/T を欄に |
| 試験のコマンド | 採る（表） | 工場の `test_cmd` |
| 触らない物 | 採る（表） | 工場の計画・BMAD |
| あいまいな点 | 残さない | writing-plans・OpenSpec |
| 1 問ずつ聞く | 採らない | ― |
| 実装の前の照らし | 採る（必ず） | BMAD・Spec Kit・工場 |
| 差分の仕様 | 採らない | ― |
| TDD の印 | 採る（設計書） | 工場の `route` |
| 段ごとの期待の出力 | 採らない | ― |
| 要件の両向きの追跡 | 今は採らない | ― |

「表」は機械が確かめる表（YAML）、「設計書」は仕様の設計書（Markdown）。2 章。

訳:

- 目的: 5 つのうち 4 つが 1〜2 文の目的を頭に置く。工場の独立設計と世界の解が `purpose` の 1 文で回るので、表の目的をそのまま渡せる。
- 設計の文: Spec Kit の `plan.md`・OpenSpec の `design.md`・BMAD の設計の文書のように、何をどう変えるかの文を持つ。工場では #765 の組み直しの設計書（`docs/design/<部品>.md`）が同じ役をし、その形で仕様を固めて実装させた実績がある（issue #802 の「何が困っているか」）。答えで足した。
- ファイルの行: 答えの前は、計画の `files[]` の形のまま仕様に書かせる案だった。持ち主が仕様の粒度を組み直しの設計書くらいと決めた（3 章）ので、仕様には書かない。run の中で計画の AI が設計書から 1 回だけ起こす（2.4）。修正の部品が計画と同じに読めることは、起こした行が計画の行の形であることで満たす。答えで変えた。
- 受け入れの条件: 4 つの形はどれも「前提・出来事 → 振る舞い」の 2〜3 つの部分を持ち（G/W/T・WHEN/THEN・EARS の WHEN/SHALL）、1 件を 1 本の試験に直せると言う。人の仕様は日本語で書くので、英語のかぎの語で文を縛る形は合わない。欄に分ければ、空でないかを機械が yes/no で確かめられる（憲法の 6）。
- 試験のコマンド: 仕様の中に書く形を持つのは writing-plans（段ごと）と BMAD（`Verification`）だけ。工場は既に line の `test_cmd` 1 行で受け、試験の段が赤と緑を事実で照らすので、表にも 1 行だけ持たせる。
- 触らない物: 書く形を持つのは BMAD（Non-Goals・Never）と OpenSpec（任意）。工場の計画は `out_of_scope`（glob と訳）を持ち、修正の部品が範囲の外を書く前に止まるので、その形で持つ。
- あいまいな点: 持ち主は、仕様は人と壁打ちして固めてから入れると決め、問いを 1 つずつ聞き続ける進め方を好まない（issue #802 の本文）。固める会話の進め方は工場で縛らず（Spec Kit の 1 問ずつの `clarify` も採らない）、渡された仕様に決まっていない点を残さない（writing-plans の「Lines that decide nothing」・OpenSpec の「resolve it now」）。会話で決めた事は設計書の「決めた事」に訳つきで書く。部品の指摘を持ち主が受け入れた記録は、表に添える審査の記録が持つ（2.3）。答えの前の案の `decisions` の欄は、この 2 つに分けて無くした。
- 実装の前の照らし: 世の中は形の照らし（OpenSpec の `validate`）と中身の照らし（Spec Kit の `analyze`・Kiro・BMAD の readiness）を分けて持つ。Spec Kit の `analyze` は助言だけで実装を止めないが、持ち主は「壁打ちの中で問題ないかはちゃんと見てほしい」と決めた（3 章）。そこで中身の照らしは、仕様を固める会話の中で部品を単独で必ず回し（2.3）、指摘が残った仕様は工場に入れない（BMAD の readiness の FAIL と同じ向き）。形の照らしと、照らしを回した事の確かめは run の入口で機械がする。答えで変えた（前は run の中で計画の審査を 1 回当てる案だった）。
- 差分の仕様: OpenSpec の形は、対象のリポジトリに本体の仕様の置き場（`openspec/specs/`）が在り、直しのたびに合わせ込むことが前提。工場はどの対象にも本体の仕様を持たず、人の仕様は 1 回の run の入力で終わる。差分の仕様を入れるには対象に仕様の置き場を足す新しい仕組みが要り（E10・E11）、5 つのうち持つのは 1 つだけで、今の困りごと（判定と計画の往復を通り直す）を解かない。
- TDD の印: 既定は direct、人が危ない所にだけ TDD を書く形は issue の案の 3 で決めてある。表は 4 つだけ（3 章）なので、印は設計書の「TDD で直す所」に書き、計画の AI がファイルの行を起こす時に計画の行の `route`（`tdd`・`direct`）へ写す。答えで変えた（前は表の単位ごとの欄だった）。
- 段ごとの期待の出力: writing-plans の「コマンドと期待の出力」は、人が先に出力を書く形。工場は試験の段と TDD の役が赤と緑を実行の事実で照らすので、人に出力を書かせない。
- 要件の両向きの追跡: Spec Kit の網羅の穴と BMAD の「orphans in both directions」は、受け入れの条件とファイルの行を結ぶ欄（Kiro の「_Requirements: 5.1, 5.2_」）があって初めて機械で照らせる。計画の `files[]` にその欄は無く、足すと計画の形が変わる。独立設計との突き合わせ（2.3）が抜けを挙げるので、今は足さない。

### 1.4 工場の今の形との合わせ

- 計画の行（`workflows/plan/works-factory-plan.yaml` の `&plan_reply`）は、run の中で計画の AI が設計書から 1 回だけ起こす（2.4）。形は今の計画の行のままなので、修正の部品・試験の段・レビューは今のまま読む。計画の AI が自分で書く欄（`approach`・`shrink_first`・`narrows`・`tests`・`allowed_paths` など）は、今の計画の部品の指示のまま、設計書と表を「固めた仕様」の節（計画の部品の入力 `spec`）として読んで埋める（6.3）。表の `out_of_scope` が計画の行の `out_of_scope` に写っていることと、`narrows` が設計書で決まっていることは、計画の後の機械の照らしが確かめる（6.4）。
- 仕様の部品 `workflows/spec/`（名 `works-factory-spec`）は、判定の中で依頼から要件と受け入れの試験を書かせる別の物で、この道ではない。受け入れの条件を Given/When/Then で書く所は同じ向き。
- 持ち主の決め `three-tiers` の「計画の壁打ち（plan と plan-review の往復）はどの段でも省かない」は、この道でも省かない。壁打ちを run の前の、仕様を固める会話の中で部品を単独で回してする（持ち主の決め `spec-driven-shape`）。

## 2 仕様に入れる物

### 2.1 全体

仕様は 2 つのファイルにする（持ち主の決め `spec-driven-shape`）。

- 設計書（Markdown）: 何のために・どの部品をどう変えるか・振る舞い・決めた事を文で書く。書き方は #765 の組み直しの設計書と同じ（2.2）。
- 機械が確かめる表（YAML 1 本。以下「表」）: 目的・受け入れの条件・試験のコマンド・触らない物の 4 つだけを書く。schema で縛る（2.3）。表を読むのは block の入口の script 1 本だけで、その script だけが外のパッケージ PyYAML を持つ（6.7）。

同じ事を 2 か所に書かせないため、表の 4 つは設計書に書かない。run の入力は表 1 本で、表が設計書のパスを名指す（issue #802 の受け入れ「仕様のファイル 1 本と対象のリポジトリだけで回せる」を保つ）。

### 2.2 設計書

置き場は対象のリポジトリの中（パスは表の `design` が名指す）。#765 の設計書の型（[README.md](README.md) の頭と、各設計書の頭の 3 行）に合わせ、次を持つ:

- 頭の 3 行: 何の話か・決めたこと・持ち主に求めること（工場に入れる時は「なし」）。
- 語: この設計書だけの語。
- 背景: 今何が困っているか（なぜこの直しが要るか）。目的の文そのものは表の `purpose` に書き、ここでは繰り返さない。
- どの部品をどう変えるか: 触るフォルダ・モジュールと、その中で変える物。ファイルごとの行の欄（計画の `files` の 6 つ）は書かない。
- 振る舞い: 変えた後にどう動くか。受け入れの条件は表に書き、ここでは表の `key` で指す。
- 決めた事: 会話で決めた事と訳。選ばなかった案と退けた訳もここ。
- TDD で直す所: 振る舞いを変える危ない所だけを名指す。無ければ書かない（既定は direct）。

書かない物: 表の 4 つ（目的・受け入れの条件・試験のコマンド・触らない物）を見出しに持たない。

### 2.3 機械が確かめる表

形（欄の名は仮。schema は実装の PR で `workflows/spec-driven/schemas/spec-table.schema.json` に置く。ファイルは YAML。読む所は 6.7）:

```yaml
design: docs/design/<名>.md        # 設計書のパス（対象の根から）
purpose: 何が良くなるかの 1〜2 文
acceptance:                        # 1 件以上。1 件が 1 本の試験になる
  - key: a1
    given: 前提（任意）
    when: きっかけ
    then: 振る舞い
test_cmd: ""                       # 任意。空なら今の line と同じく工場が用意する
out_of_scope:                      # 任意。計画の行と同じ形
  - glob: <触らないパスの glob>
    why: 触らない訳
reviews:                           # 仕様を固める会話で回した審査の記録（下）
  - part: works-factory-plan-review
    run: <単独の run の id>
    findings:                      # 最後に回した版で残った指摘だけ
      - key: <部品が付けた指摘の名>
        text: 指摘の 1 行
        handling: accepted
        owner_words: 持ち主が受け入れた言葉
```

`design` と `reviews` は仕様の中身でなく、表 1 本で run を回すための運ぶ欄。前の版の `spec_sha256`（審査した版の hash）は外した。審査した版と渡した版が同じことは、部品の run に Archon が残した入力を、今の仕様から組み直した入力と比べて確かめる（入口の確かめの 5。2.6）ので、表に hash を書かせる要が無い。

仕様を固める会話（壁打ち）の中で、会話の AI が工場に入れる前に部品を単独で必ず回す（持ち主の決め `spec-driven-shape`）:

- 必ず回す 5 つ: 計画の審査（`works-factory-plan-review`。8 つの観点。同じ処理を 2 か所に書く写しも見る）・独立設計（`works-factory-independent-design`。目的だけから別の役が設計を作り、設計書と突き合わせて抜けや思い込みを探す）・前提の実測（`works-factory-premises`）・前の決めの確かめ（`works-factory-prior-decisions`）・世界の解（`works-factory-world`。同じ類の問題を世の中がどう解いているかを一次の出典で調べる。持ち主の決め `step-up`・keep-essence の 12）。
- 指摘を受けて仕様を直したら、直した版で回し直す。直して消えた指摘は記録に書かない。最後の版で残った指摘は、持ち主が明示で受け入れた物だけを、受け入れた言葉つきで残してよい。それ以外が残っていれば工場に入れない。
- 部品ごとの呼び方・1 回の時間と費用・部品の指摘を `findings` に写す形・部品を本線の外から呼んで詰まった所は、本物の単独の run で試して 2.5 に書いた。

run の入口で機械が確かめる事（どれも yes/no。どれかが欠ければ AI を起こさずに止まり、欠けた物を名指して人に返す。細目は 2.6）:

1. 表が schema に合う（必須の欄が在る・`acceptance` が 1 件以上で `when` と `then` が空でない・`handling` が `accepted` で `owner_words` が空でない）。
2. `design` の設計書が対象に在る。
3. 設計書の見出しに表の 4 つの名が無い（照らす字は 2.6 の 1）。
4. `reviews` に必ず回す 5 つの部品が 1 つずつ在る。
5. どの `reviews` の `run` も本物の部品の run で、今の仕様を審査した物（2.6 の 2）。

### 2.4 run の中の流れ

1. 入口の機械の確かめ（2.3。block の形 entry が、試験の段〔AI の段を中に持つ〕より前に照らす。6.2・6.7）。
2. 判定の役（block `works-factory-diagnose`）を 1 回だけ回し、表と設計書から組んだ依頼の行で、直す単位と、単位ごとの探し方 `class_query` を作らせる（keep-essence の 7。9 章）。判定の役が問いを返したら、仕様が決めていない点として止まって人に返す。
3. 計画の AI（`workflows/plan/` の修正案の役）を 1 回だけ回し、設計書と表から計画の行（ファイルの行を含む）を起こす。設計書の「TDD で直す所」に当たる行の `route` を `tdd`、ほかを `direct` にする。計画の審査の往復は回さない。
4. 機械による仕様とリポジトリの食い違いの照らし（block `works-factory-spec-driven` の形 check。6.4）。例: ファイルの行の `op` が `modify`・`delete` ならパスが作業ツリーに在り、`create` なら無い（`rename` は `from` が在り `path` が無い）。計画の AI が能力を狭める行（`narrows`）を設計書で決まっていないまま返した時も、仕様を書き換えずに止まって人に返す。人が仕様を直したら、新しい run として最初から回す。
5. 修正（`workflows/fix/`。入力 `routes: plan` で計画の行の `route` に従う。7 章）・試験の段・レビュー・報告は今の部品のまま。ファイルの置き場の穴は、run の後のレビュー（最小性・全体の整合を見る役）で拾う。

本線のどの node をどう足し・どう変えるかは 6 章。

### 2.5 部品を単独で呼ぶ形（本物の run で試した結果）

2026-10-21 に、必ず回す 5 つと、6 章の形で run の中に入れる判定の役 diagnose を、本線の外から 1 回ずつ単独の run で回した。

試し方:

- 対象: works-factory の clone を commit `c0ce145`（#765 の設計書を置いた commit。block の `workflows/world/` はまだ無く、今の形は `lib/worldblk.py` と judge の中の node）で切り、枝に表の見本 1 本を足した物。起動は今の工場（この PR〔#809〕の元の main）の `bin/works-factory`。
- 仕様の見本: 設計書は `docs/design/world.md`（その commit の版。334 行）、表は手で書いた `docs/design/world.spec.yaml`（目的 1 文・受け入れの条件 4 件〔単独で回る・抜き書きの照らし・web off の道・言い直しの諦め〕・触らない物 2 件・`test_cmd` は空）。
- 部品に渡す入力は、表と設計書から機械的に組んだ（下の「部品ごとの呼び方」。block の入口の入力の組み立て〔6.7〕はこの組み方を写す）。

部品ごとの呼び方（計画の審査の「形 text」は、修正案の JSON でなく方針の文を字で渡す形。`<対象>` は対象のリポジトリの根。`<設計書>` は設計書の本文、`<表>` は表から `reviews` を除いた字、`<目的>` は表の `purpose`）:

```sh
# 計画の審査（形 text）。proposal は字で渡す（ファイルのパスは修正案の JSON と読まれて拒まれる）
bin/works-factory workflow run works-factory-plan-review --cwd <対象> \
  --input proposal="<設計書>

---
機械が確かめる表（<表のパス>）:

<表>" --input purpose="<目的>"
# 独立設計
bin/works-factory workflow run works-factory-independent-design --cwd <対象> --input purpose="<目的>"
# 前提の実測と前の決めの確かめ。request は「頭の行」と「節の行」（下）の JSON の配列
bin/works-factory workflow run works-factory-premises --cwd <対象> --input request='<頭の行と節の行>'
bin/works-factory workflow run works-factory-prior-decisions --cwd <対象> --input request='<頭の行と節の行>' \
  --input entry='仕様を固める会話（<設計書のパス> と <表のパス>）'
# 世界の解。request は「頭の行」と「受け入れの行」
bin/works-factory workflow run works-factory-world --cwd <対象> --input request='<頭の行と受け入れの行>' \
  --input purpose="<目的>" --input web=on
```

- 頭の行: `{where: <設計書のパス>, text: <設計書の頭の「何の話か」と「決めたこと」の 2 行>}`。
- 節の行: 設計書の 2 段目の見出し（`## `。Markdown のコードの囲み〔```〕の中は除く）ごとに `{where: "<設計書のパス>#<見出し>", text: <その節の本文>}`。world.md では 10 行。
- 受け入れの行: 表の `acceptance` 1 件ごとに `{where: "<表のパス>#<key>", text: "前提: <given>。きっかけ: <when>。振る舞い: <then>。"}`。
- 判定の役（run の中で回す形の試し）: `bin/works-factory workflow run works-factory-diagnose --cwd <対象> --input request='<頭の行と節の行と受け入れの行>' --input request_origin='人と固めた仕様（<表のパス>）' --input purpose=<目的のファイル>`（目的のファイルは `{purpose_text, source, known_weaknesses, source_files}`）。

1 回の時間と費用（時間は起動から終わりまでの壁の時計、費用は Archon の run の記録の `total_cost_usd`）:

| 部品 | run の id | 時間 | 費用 | 返り |
| --- | --- | --- | --- | --- |
| 計画の審査 | `abab34c9` | 9 分 50 秒 | $4.00 | 穴 12・別案 3 |
| 独立設計 | `89c8ef8e` | 61 秒 | $0.19 | 要素 8 |
| 前提の実測 | `5574c2b8` | 53 秒 | $0.23 | 制約 8 |
| 前の決めの確かめ | `fac6fefc` | 50 秒 | $0.26 | 論点 9 |
| 世界の解 | `e9c3ef35` | 85 秒 | $0.19 | 類 5 |
| 判定の役 | `a26fd71f` | 11 分 20 秒 | $3.18 | 単位 7・問い 1 |

run の id は頭の 8 字（全部の id と記録の置き場は PR #809 の本文）。必ず回す 5 つを並べると壁の時計は計画の審査の約 10 分で決まり、費用は 1 周で約 $4.9。計画の審査が費用の 8 割を持つ。判定の役は run の中で 1 回回す物（6 章）で、仕様駆動の run の中の判定と計画の費用は、判定の役の約 $3.2 と計画の部品（作り直しの前の run df5e111f で $4.12）を足した約 $7 の見込み（今の本線の判定と計画の往復は、同じ run df5e111f で約 $16。4 章の 3）。

部品の返りと、それを表の `findings` に写す形:

- 計画の審査: ファイルの行の無い設計書を形 text で渡して、審査として働いた。照らした先は設計書が名指す今のコード（`lib/worldblk.py`・`lib/worldmark.py`・`lib/runreport.py`・`lib/carry.py`・judge の YAML と md・試験）で、穴は 12（重さ block が 3・suggest が 9）、別案（`shrink`）が 3。block の 3 つ: 依頼の行の形を block ごとに写すと 7 つの写しになる（`request-shape-copy`）・報告の文の出典に使われていない関数を選んでいる（`report-source-dead-fn`）・web が off でも web の役が道具を持ったままで受け入れ a3 を機械で保てない（`web-off-not-enforced`）。1 つ目と 3 つ目は、後の本物の実装が同じ向きに直した（依頼の行の形は共通の `workflows/.shared/schemas/request.schema.json`、web off は道具の無い node `world-judge-offline-loop` に分けた）。返りの `holes` の先 `review.json` の `faces[]` が `{key, kind, where, why, severity}` を持つので、写す形は `findings: [{key: <faces の key>, text: <why の頭の 1 文>, handling: accepted, owner_words: …}]`。
- 世界の解: 類 5 つとも依頼の解き方は定石と同じ（`versus.verdict` が `same`）。1 つは web で出典を取れず知識だけ（`basis: knowledge`）。指摘に当たるのは `versus.verdict` が `differs` の行で、写す形は `{key: <class_id>, text: <challenge>}`。
- 前提の実測: 制約 8 つ（実測 7・仮説 1）。うち 1 つは設計書の誤り（「今の judge の 9 つの node を 7 つの node の block にする」と言うが、設計書 1.3 の並びを数えると 9 つ）。返りは測った事実の行で、「食い違い」の印の欄は無い。設計書と食い違う行を選ぶのは会話の AI で、写す形は `{key: "premises-<行の番号>", text: <行の text>}`。
- 前の決めの確かめ: 決着済みの論点 9 つ（`docs/owner-decisions.md` と README）を引き、食い違いは見つからなかった。issue と閉じた PR は読んでいない（`searched` の「見ていない」）。食い違いの行の欄は無く、`detail` の文に書かれる。写す形は前提の実測と同じく、会話の AI が選んだ物を `{key: "prior-<番号>", text: …}`。
- 独立設計: 問いは立つ（`question_stands`）。要素 D1〜D8 の設計を返した。設計書との突き合わせ（抜けと思い込み）は会話の AI がする。この試しでは、独立設計が新しい置き場 `blocks/` に持ち主の決めが要ると挙げた（D1。設計書には無い）。写す形は `{key: "design-<要素の id>", text: <設計書に無い要素の 1 文>}`。
- 判定の役（run の中の形の試し）: 素材を渡さなくても素材の欠けで止まらず（`materials_missing` が空）、直す単位 7 つ（do-now 6・info 1）を返した。目的の外とした行が 1 つ（設計書 9 節の入口の workflow policy-check。表の目的と受け入れの条件にその入口が無い）、問いが 1 つ（指示の md に値を入れる口を自前で作るか既製のテンプレートの道具に乗せるか。推しつきの分かれ道）。どちらも、会話で回した 5 つの部品が挙げなかった点で、設計書と表の食い違いと、設計書が決めていない点に当たる。探し方は、受け入れの行から作った 4 単位がどれも表の行そのもの（`- key: a1` を表のファイルで数える）を、設計書の節から作った 2 単位のうち 1 つが設計書の字を数える形で、コードを数える問いは 1 つ（`bin/_lib/place.py` の読ませるフォルダ）だけだった（9 章）。

詰まった所（部品やノードの作り直しの候補。issue #802 のコメントの「設計で決めること」の 4 つ目）:

1. 新しい対象に 5 つを同時に起動すると、全部が起動の殻の中で落ちた（Claude の設定の置き場に借りる skill とプラグインを置く所で、同じフォルダの名を 2 つの起動が同時に作り、`OSError: Directory not empty`。後の起動は「選んだ物の外が在る」で止まった）。1 つ目の起動が `Running workflow:` の行を出した後に残りを起こせば通る。殻の置き方（`bin/_lib/toolset.py`）を、同時の起動に耐える形にする候補。
2. 計画の審査の `proposal` は、設計書のパスを渡せない。改行の無い字は在るファイルなら JSON として読まれ、JSON でなければ拒まれる（`workflows/plan-review/src/steps.py` の `proposal_form` の (c)）。設計書の本文（この試しで 29 KB）を命令の行に字で載せた。在るファイルが JSON でなければ方針の文として読む形にする候補（ただし同じ所の「黙って方針の文にしない」の決めとの兼ね合いを先に決める）。
3. 部品ごとに入力の形が違う（字の `proposal`・目的の 1 文・依頼の行の配列）。会話の AI が同じ仕様から 3 つの形を組むことになる。組み方を 1 か所（6.7 の置き場）に置く（2.6 の 2 の版の照らしも同じ組み方を使う）。
4. 部品ごとに「指摘」の形が違う（上の写す形）。機械が指摘を数えられるのは計画の審査（`faces`）と世界の解（`versus.verdict`）だけで、前提の実測・前の決めの確かめ・独立設計は事実か設計を返し、食い違いを選ぶのは読み手。同じ事を 2 つの部品が別の形で返した例: 置き場 `blocks/` が今は無いことを、前提の実測は測った事実の行で、独立設計は設計の要素 D1（持ち主の決めを先に書く）で返した。前提の実測と前の決めの確かめに「仕様と食い違う」の印の欄を足す候補。
5. 設計書の見出しの照らし（入口の確かめの 3）を字の一致だけで作ると、見本の world.md は止まる。コードの囲みの中の指示の骨組みに `## Purpose` の見出しが在る。コードの囲みの中を除く（2.6 の 1）。
6. 部品の run の記録は、対象のパスから決まる Archon の家（`${XDG_STATE_HOME:-~/.local/state}/works-factory/targets/<対象のパスから作る 8 桁>/archon-home`）に入る。会話で回した部品の run を工場の run の入口で照らす（2.6 の 2）には、同じ対象のパス（か同じ `WORKS_FACTORY_HOME`）で回す。
7. 返りの読み方: `workflow run` は `finish` の返りを JSON 1 行で出すが、pointer の先のファイル（`review.json`・`world.jsonl`・`premises.json` など）は `workflow get <run> --json` の `terminal_record.artifacts.root` の下に在り、命令の出力には置き場が出ない。

詰まった所の行き先（工場窓口の答え。2026-10-21、受付 20261020-224412-ca616a）:

- #802 の実装の範囲に入れる物（仕様駆動の道に要る物）:
  - 2（計画の審査に設計書のパスを渡せない）: 計画の審査に入力 `proposal_file`（`file: 方針の文のファイル。在れば中身を形 text の方針の文として読む。proposal と一緒には名指さない`。既定 `""`）を足す。今の `proposal` の読み（在るファイルは JSON として読み、読めなければ拒む。黙って方針の文にしない）は変えない。入力を分けるので、字の形から読み替える緩めにならない。変更の種類は `workflows/AGENTS.md` の P。会話の AI は設計書と表から組んだ字をファイルに書いて渡す（2.5 の呼び方の `proposal` の字と同じ中身。版の照らし〔2.6 の 2 の d〕は、Archon の記録に残るのがファイルのパスになるので、そのファイルの中身の sha256 を `proposal_file` と並べて記録させる形を実装の PR で決める）。
  - 3（部品ごとに入力の形が違う）: 入力の組み立てを 1 か所に置く（6.7）。
  - 4（部品ごとに指摘の形が違う）: 前提の実測の行に任意の欄 `contradicts`（`where`。その行が食い違う依頼の行の `where`。食い違わなければ書かない）を、前の決めの確かめの返りに `conflicts`（`[{decision, where, why}]`。依頼の行とぶつかる決めの行。無ければ空の配列）を足す。どちらも任意の欄で、今の読み手は読まないので本線は変わらない（変更の種類は I と、返す形を足す所）。足した後は、入口の確かめの 2.6 の 2 の e に、この 2 つの部品の指摘（`contradicts` の在る行・`conflicts` の行）も数えて足す。独立設計は設計を返す部品で、指摘の形は持たせない（突き合わせは会話の AI）。
  - 5（見出しの照らしがコードの囲みの中で誤る）: 2.6 の 1 の決めで閉じる。
  - 6（部品の run の記録が入る Archon の家は対象のパスで決まる）: 会話から部品を呼ぶ手引き（works-factory のプラグインのスキル）に、工場の run と同じ対象のパスで回すことを書く（2.6 の 2 の照らしに要る）。
- #802 と別の issue にした物（仕様駆動の道に依らない、起動の殻の物）: 1（同時の起動で起動の殻の中でぶつかる）と 7（`workflow run` の出力に記録の置き場が出ない）。issue #810。

試していない事: 指摘を受けて仕様を直し、直した版で回し直す 2 周目。持ち主が指摘を受け入れる会話。工場の run の入口での照らし（コードがまだ無い）。

仕様を固める会話で AI が案を出す使い方（issue #802 のコメント 2026-10-20T04:51:44Z）の形:

1. 人は目的を言う。会話の AI が設計書と表の下書きを書く。
2. 会話の AI が 5 つの部品を起こす（1 つ目の起動の後に残りを並べる。詰まった所の 1）。速い 4 つ（1〜1.5 分）の返りが先に届くので、計画の審査（約 10 分）を待つ間に、前提の実測の食い違い・独立設計との差・前の決めとの当たりを、決めの要る点ごとの選択肢にして人に出す。選択肢は勧める案を先頭に置き、勧める訳を添える（「こんな感じでどうですか？」）。工場の run の中で止まる点（判定の役の問いと目的の外の行。9 章）を先に見たい時は、判定の役も単独で回す（任意。約 11 分・約 $3.2）。
3. 計画の審査の穴が届いたら、穴ごとに選択肢を出す。審査の別案（`shrink`）は、そのまま勧める案の候補になる（この試しの 3 つはどれも「設計の文を 1〜2 句消すだけ」の形だった）。
4. 人は勧める案で済めばそう答え、違えば直す。会話の AI が設計書と表を直す。
5. 直した版で回し直す。途中の周は、直した所に関わる部品だけでよい。工場に入れる前の最後の周は、5 つ全部を最後の版で回す（入口の確かめの 5 が、どの記録も今の版を審査した物かを照らす）。1 周で約 10 分・約 $4.9（この試しの値）。
6. 最後の周で残った指摘は、人が明示で受け入れた物だけを、受け入れた言葉つきで `reviews[].findings` に書く。それ以外が残っていれば工場に入れない。

呼び方と返りの読み方は、works-factory のプラグイン（claude-plugins の `works-factory/`）のスキルに書く（このリポジトリの外。工場の側が持つのは入力の組み立て〔6.7〕と、この節）。

### 2.6 入口の確かめの細目（PR #807 のレビューが後に回した 3 つのうち 2 つ）

1. 見出しの照らし（入口の確かめの 3）: 設計書の見出しは、ATX の見出し（行頭の `#` 1〜6 個と空白）と Setext の見出し（次の行が `===` か `---` だけ）。コードの囲み（行頭の ```` ``` ```` か `~~~` で挟んだ所）の中の行は見ない（2.5 の詰まった所の 5）。見出しの字から、頭の `#`・終わりの `#`・頭の節の番号（`1`・`2.3` のような数と `.` の並びと空白）・前後の空白・`` ` `` を除き、英字を小文字にした字が、次の名の 1 つと字のまま同じなら止める: 表の欄の名（`purpose`・`acceptance`・`test_cmd`・`out_of_scope`）と、その日本語の名（`目的`・`受け入れの条件`・`受け入れ条件`・`試験のコマンド`・`テストのコマンド`・`触らない物`・`触らないもの`）と英語の名（`acceptance criteria`・`test command`・`out of scope`・`non-goals`）。名の一覧は、表の欄の名と並べて 1 か所に置く（置き場は 6.7 の「入力の組み立てと照らしのコードの置き場」）。見出しの一部に含むだけ（例「目的の外の所見」）は止めない。訳: 持ち主の決めは「表の 4 つを設計書に書かない」で、その見出しを持たないことを yes/no で照らす（憲法の 6）。本文の文に目的の字が出ることまでは縛らない（背景の文が困りごとを書けば、目的に触れずには書けない）。
2. 審査の記録と部品の run の突き合わせ（入口の確かめの 5）: 入れる（持ち主の答え。持ち主の決め `spec-driven-shape`）。持ち主の「ある程度壁打ちの中で問題ないかはちゃんと見てほしい」を、表の書き写しだけで破れないようにする。`reviews` の行（欄 `part`・`run`・`findings` は 2.3 の表の形）ごとに、Archon の run の記録（`workflow get <run> --json`。2.5 の試しで、部品の名・結末・入力・返りを持つと確かめた）を読み、次を全部照らす:
   - a. 記録が在る（同じ Archon の家の run。2.5 の詰まった所の 6）。
   - b. 記録の `workflow_name` が、表のその行の `part`（部品の workflow の名。例 `works-factory-plan-review`）と同じ。
   - c. `status` が `completed`・`outcome` が `succeeded` で、返り（`terminal_record.returns.value`）の `ok` が真。
   - d. `metadata.inputs` が、今の設計書と表から入力の組み立て〔6.7〕が組む、その部品の入力と同じ（2.5 の呼び方の組み方。表の `reviews` は組む字に入れない）。これで審査した版と渡した版が同じことも照らせるので、前の版の `spec_sha256` は要らない。
   - e. 計画の審査と世界の解は、返りから機械が数えられる指摘（計画の審査の `faces[].key` の全部・世界の解の `versus.verdict` が `differs` の行の `class_id`。返りの形と `findings` への写し方は 2.5 の「部品の返りと、それを表の `findings` に写す形」）が、どれもその行の `findings` の `key` に在る。独立設計・前提の実測・前の決めの確かめは返りに指摘の形が無い（2.5）ので、a〜d だけを照らし、指摘は会話の AI が選んで書く。
   照らす所: 起動の殻（`bin/works-factory`。置き場は `bin/_lib/` の新しいモジュール）。照らすのは、本線を `spec_table` を名指して起動した時と、block `works-factory-spec-driven` を単独で `table` を名指して起動した時の 2 つ（下の「block の単独の run」）。殻は表を読み（表の読みと入力の組み立ては `lib/spectable.py`。6.7。殻がどの Python で読むかは 6.7 の「殻の側の読み」）、`reviews` の run の記録を `workflow get <run> --json` で読んで a〜e を照らし、結果（行ごとの a〜e の yes/no と、合わなかった物の名）をファイルに書いて、そのパスを env で run に渡す。どれかが合わなければ、殻は Archon を起こさずに止まる（AI を起こさずに止まる）。run の中の script と `lib/` は Archon の命令を呼ばず、Archon の run の記録の欄も読まない（E3。E22 の「殻の事実は殻が組んで env で渡す」）。block の形 entry は、env の結果ファイルが在り、全部の行が合っていることだけを yes/no で照らす。会話から部品を回す時は、工場の run と同じ対象のパスで回す（2.5 の詰まった所の 6）。
   block の単独の run（憲法の 5）: block を単独で回す正の入口は、ほかの block と同じく殻を通す `bin/works-factory workflow run works-factory-spec-driven --cwd <対象> --input mode=entry --input table=<表>`（`workflows/AGENTS.md` の「始め方」）。殻は本線の時と同じに照らすので、block は文とリポジトリ（と同じ対象の Archon の記録）だけで最後まで回る。殻を通さずに Archon の命令をそのまま打った run と、Archon の筋書き（`workflow test` の dry-run）は結果ファイルを持たないので、入口の確かめの 5 で `ok: false` を返して最後の段まで回り切る（落ちずに `status` で止めを返す。world の諦めの筋書きと同じ形）。止めの訳の字は「審査の記録を照らした結果が渡されていない（起動の殻を通して起動する）」。照らせない run を黙って通さないための形で、憲法の 5 の「単独で回る」は殻を通した run で満たす。照らしが通る道の試験は、block の試験（`tests/blocks/spec_driven/`）が一時フォルダに結果ファイルを置き、env で渡して script を回して照らす。
3. keep-essence の 7 の形: 9 章。

## 3 持ち主の答え

2026-10-21 に工場窓口が持ち主に 3 つの問いを聞いた。答えと持ち主の言葉は持ち主の決め `spec-driven-shape`（`docs/owner-decisions.md`）。

- 問い 1（受け入れの条件の書き方。A 前提・きっかけ・振る舞いを欄に分ける／B EARS の英語の 1 文／C 試験の名を人が書く）: A。2.3 の `acceptance`。
- 問い 2（仕様のファイルの形。A YAML 1 本を schema で縛る／B 決まった見出しの Markdown／C Markdown の本文と頭の YAML の欄）: A。その後の粒度の見直しで、機械が確かめる 4 つを YAML の表に、設計の文を Markdown の設計書に分けた。C の弱み（同じ事を 2 か所に書ける）は、表の 4 つを設計書に書かない決まりと、入口の確かめの 3（2.3）で塞ぐ。
- 問い 3（ファイルの行で人に必ず書かせる欄。A パス・作る/直す/消す・受け持ちの 3 つ／B 計画の行と同じ 6 つ全部）: B。
- 持ち主の言葉（問い 1〜3 に A・A・B で「はい」の後）: 「組みなおしぐらいの粒度でいいけどなどう思う」
- 持ち主の言葉（工場窓口が「計画の段を飛ばす」と説明したのへの訂正）: 「固める段階で、２と３の往復を混ぜるって話だったよね」（2 は計画を書く段、3 は計画の審査）
- 持ち主の言葉（工場窓口の案に）: 「ある程度壁打ちの中で問題ないかはちゃんと見てほしいけど」

問い 3 の経緯: 設計の AI は、人の書く手間を軽くするため A（3 つだけ必須）を勧め、持ち主は B（6 つ全部）を選んだ。続けて持ち主が、仕様の粒度は #765 の組み直しの設計書くらいでよいと言い、ファイルごとの行そのものを仕様から外した。6 つの欄を持つファイルの行は、run の中で計画の AI が設計書から 1 回だけ起こし（2.4）、置き場の穴は会話の中の計画の審査と run の後のレビューが拾う。そのため問い 3 の答えの B は、計画の AI が起こす行の形（今の計画の行の 6 つの欄のまま）に当たり、人が書く欄の数の問いは無くなった。

## 4 E11 の 3 つの確かめ

1. Archon が持っているか: 持たない。Archon は AI の処理を graph にして回す道具で、人の仕様を受けて工場の守りつきで実装させる道は持たない（[archon.md](archon.md)）。Archon に同梱の graph は呼ばない（E8）。
2. ASF が持っているか: 止めた版（`factory/pack.json` の `integration_revision_required` a972888a）の ASF では、`archon-deliver`（https://github.com/coleam00/Archon/blob/a972888a7a30a669a3a771e7caef512197de6ac4/.archon/workflows/sdlc/deliver-entry/archon-deliver.yaml 。中身は部品の `archon-deliver-block`、https://github.com/coleam00/Archon/blob/a972888a7a30a669a3a771e7caef512197de6ac4/.archon/workflows/sdlc/deliver/archon-deliver-block.yaml ）が最も近い。入力 `work` に計画のパスなどを受け（「What to deliver — a plan path, findings, a description」）、実装 `archon-implement`・下書きの PR・リスクに応じた深さのレビュー・整理・CI の役を回して、緑なら PR を ready にする（「Capped rounds of implement …, draft PR, and a review at the depth its risk earns」）。レビューと CI は在るので、「工場の守りが付かない」とは言えない。工場と違うのは次の 4 つ（どれも止めた版で読んで確かめた）:
   - 赤と緑の判定: `archon-implement` の緑は実装の役が自分で書く欄（「`green` — true only when the work is complete AND the focused checks on what you changed passed」https://github.com/coleam00/Archon/blob/a972888a7a30a669a3a771e7caef512197de6ac4/.archon/workflows/sdlc/implement/commands/implement.md ）。元から赤かどうかも役が証拠を添えて自分で書く（「`inherited`, the same check was already failing at this run's starting commit」）。工場は赤と緑と元から赤を機械が実行の事実で判定する（keep-essence の 1・2）。
   - TDD の印: 試験は要る所だけ書く形で（「Write a test only where a plausible edit could silently break behavior that matters … Many changes need no new test.」同じファイル）、行ごとに先に赤を見る道を名指す口は無い。工場は計画の行の `route` で単位ごとに TDD を選び、TDD の行は先に赤を見る（1.3・2.4）。
   - 入口の確かめ: 入力 `work` は形を縛らない字で、空なら run の頭の文を仕事として読む（「Empty means the run's trigger message is the work.」）。工場は表を schema で縛り、審査の記録の欠けも含めて、AI を起こす前に yes/no で止める（2.3）。
   - 呼べるか: Archon に同梱の graph は `include:` と `workflow:` で呼ばない（E8。外しは merge の `archon-pr` だけ）。`archon-deliver` そのものは呼べず、採るのは型だけ。
   `archon-implement`（https://github.com/coleam00/Archon/blob/a972888a7a30a669a3a771e7caef512197de6ac4/.archon/workflows/sdlc/implement/archon-implement.yaml 。渡された指示どおりに実装だけをする graph）は `archon-deliver` の中の実装の段で、上の 1 つ目と 2 つ目の違いはそのまま当たる。
3. 本当に要るか: 人と固め終えた仕様を渡しても、今の工場は人が会話で済ませた判定と計画の往復を、工場の中でもう 1 度回す。作り直しの前の本物の run の 1 本（run の id df5e111f。90 分・$24.56）では、計画の審査 $8.81・計画 $4.12・判定 $3.10 で、合わせて約 $16・約 40 分がこの段だった（issue #802）。新しい AI の役は作らず、本線に入口 1 つ（入力 `spec_table`）と、AI を持たない block 1 つ（入口の確かめと食い違いの照らし）を足し、今の判定の役と計画の部品を 1 回ずつ include し直すだけにする（6 章）。足す仕組みごとの 3 つの確かめは 6.6。keep-essence の 12 の仕組み（[README.md](README.md) の 10 章）との当たり:
   - 1〜6・8・10・11: 修正・試験の段・merge・報告を今のまま通すので守られる。
   - 9（独立設計と R1〜R4）: 独立設計は仕様を固める会話の中で必ず回し、入口で回した事を確かめる。R1〜R4 は run の後のレビューのまま。
   - 12（世界の解）: 仕様を固める会話の中で必ず回し、入口で回した事を確かめる（2.3）。
   - 7（class_query の数え直し）: この道でも判定の役 diagnose を 1 回だけ回し、今の本線と同じく diagnose が探し方を作る（9 章）。修正の部品の数え直しは今のまま。

## 5 自分で決めた事

1. 置き場と名: issue の案の名 `works-factory-spec` と設計書 `docs/design/spec.md` は、判定の中の仕様の部品（`workflows/spec/`）が既に使っている。E9 で同じ名は置けないので、この道は `spec-driven` の名で書いた（持ち主の決め `spec-driven-shape` がこの名を採った）。
2. 表に運ぶ欄 `design`・`reviews` を置き、run の入力を表 1 本にした。訳: issue #802 の受け入れ「仕様のファイル 1 本と対象のリポジトリだけで回せる」を保ち、審査の記録を版ごと仕様に結べる。
3. 設計書の「何のために」は「背景」（困りごと）として書き、目的の文は表だけに置いた。訳: 持ち主の決めの「設計書にこの 4 つを書かない」と、設計書が何のためにを持つことを両立させるため。
4. 審査の記録は、最後に回した版で残った指摘だけを書く。訳: 「指摘が残っている仕様は工場に入れない」を機械が yes/no で確かめられる形にするため。直した指摘を全部書かせると、直したかを機械が確かめられない。版は前の版では `spec_sha256` で結んだが、部品の run の入力と比べる形に替えた（2.3・2.6 の 2）。
5. TDD の印は設計書の「TDD で直す所」に書き、計画の AI が `route` に写す（1.3）。
6. keep-essence の 7（class_query の数え直し。欠陥ごとの探し方〔grep の型と対象のパス〕で、修正の前と後の件数を機械が数え直す。数え直すのは修正の部品が使う `lib/recount.py`）は、この道でも保つ。工場窓口の答え（2026-10-21、受付 20261020-201750-a1096f）。訳: [README.md](README.md) の 10 章の 12 の仕組みは、作り直しで守ると決めた物で、新しい道で 1 つだけ落とす訳が無い（元と同じにそろえる）。12 の仕組みのそれぞれが守りとして名指す試験が木に在るかは、`tests/layers/test_keep_essence.py` が確かめる。探し方を誰が作るかは 9 章で決めた（判定の役 diagnose を 1 回だけ回して作らせる）。前の版のこの文書は「落ちる」と書いていた。
7. 世界の解を、会話の中で必ず回す部品に入れた（2.3）。前の版のこの文書と持ち主の決め `spec-driven-shape` の最初の行は「要る時だけ」にしていた。この語は工場窓口が頼みの文に書いた物で、持ち主の言葉ではない。PR #807 のレビュー（2026-10-21）が前の決め `step-up` との食い違いを挙げ、工場窓口の答えで `step-up` と keep-essence の 12 にそろえた（決めの直した記録は `docs/owner-decisions.md` の `spec-driven-shape`）。

## 6 本線への差し込み（進め方の 6）

### 6.1 形: AI を持たない block と、本線が 1 回ずつ include する判定の役と計画の部品

工場窓口の頼み（2026-10-21）は「別の graph でなく block にし、本線の入口から include する。block の中身は入口の機械の確かめと、計画の AI を 1 回だけ回してファイルの行を起こす段」だった。訳は、本線の後ろ半分（修正から報告まで、約 900 行）を別の graph に写すと、本線を直すたびに 2 か所を直すことになるため。この訳には沿う（本線に入口を足し、後ろ半分は本線のまま通す）。

ただし block の中で計画の AI を回す所は決まりに当たる:

- block はほかの block を名指さない（憲法の 3）。block の中から計画の部品 `works-factory-plan` を include すると、その workflow は形の検査で graph と見なされ、graph は AI の node を持てない（[README.md](README.md) の 7.1 の 6 と 13 章の「block と graph の見分け」）。
- block の中に計画の AI を自前で置くと、計画の部品の指示（`workflows/plan/prompts/plan-writer.md`）と受け付けの照らし（`workflows/plan/src/`）を 2 か所に持つことになる。1 つの観点の正本は 1 つの block に置く（憲法の 4 と、設計の正本の README の 1.2）。

そこで、この設計では次の形にした（工場窓口の答え〔2026-10-21、受付 20261020-224412-ca616a〕で採った。10 章）:

- block `works-factory-spec-driven` は AI を持たない。形（入力 `mode`）を 2 つ持つ: `entry`（入口の確かめと、判定の役と計画の部品に渡す値を表と設計書から組む）と `check`（計画の後の、仕様とリポジトリの食い違いの照らし）。同じ block を形を替えて 2 度 include する前例は、試験の段（`mode` が `base` と `final`）と merge（封じると当てる）。
- 本線が、判定の役 `works-factory-diagnose` と計画の部品 `works-factory-plan` を 1 回ずつ include する。本線が計画の部品を往復の外で 1 回だけ include する前例は、案の直し `replan`。
- 本線の判定（graph `works-factory-judge`）と計画の往復（`plan-rounds`）は、仕様駆動の run では回らない。判定は、素材の観点の部品を除いて判定の役 diagnose だけを工場の中で 1 回回す。計画と計画の審査の往復は、人と一緒に会話の中で回し終えている。どちらも、判定と計画の繰り返しに人を混ぜ、同じ事を 2 度回さない形（持ち主の決め `spec-driven-shape`。10 章の 4）。

別の案として、judge のような小さな graph `works-factory-spec-driven`（中で判定の役と計画の部品を include し、本線がその graph を include する）も取れる。採らない訳: graph は判断と計算を持てない（README の頭の語の「graph」）ので、入口の確かめと食い違いの照らしの置き場に結局 block が要り、フォルダが 2 つになる。本線が直に include すれば 1 つで済む。

### 6.2 足す node と変える node

足す入力（`workflows/line/works-factory-line.yaml` の `inputs:`）:

- `spec_table`: `file: 仕様駆動の道の表（docs/design/spec-driven.md の 2.3）。相対なら対象の根から。名指すと、人と会話で回した計画の往復を工場の中で回し直さず、判定の役を 1 回回して表と設計書から修正へ進む。request・pr・base・spec・fix_fixture とは組めず、周の鎖の子では使えない`。既定 `""`。

変える node（依頼の文の run も通る node。6.5 で振る舞いが変わらないことを縛る）:

1. `start`: 出力に `from_spec`（boolean。`spec_table` を名指した run か）と `ports.spec_table`（字。表のパス。空は無い）と `ports.routes`（字。仕様駆動の run は `plan`、ほかは修正の部品の既定と同じ `auto`）を足す。`spec_table` を名指した run では、表のファイルが在ることと、組めない入力との組み合わせだけを照らして拒む（固定材料の拒みと同じ所）。表の中身（YAML）は読まない。訳: `start` はどの run でも回るので、ここで PyYAML を持つと依頼の文の run まで外のパッケージを入れることになる（6.7）。表の中身の確かめ（2.3 の 1〜5）は `spec-entry` が試験の段より前にする。「依頼の行か差分の少なくとも 1 つが要る」の照らしは、`spec_table` を入口の 1 つに数える。
2. `test-gate-base`: `depends_on` に `spec-entry` を足して `trigger_rule: none_failed_min_one_success` にし、`when:` を `"$answer-start.output.go == true && $start.output.from_fixture == false && $start.output.from_spec == false || $answer-start.output.go == true && $start.output.from_fixture == false && $spec-entry.output.ok == true"` にする。訳: 試験の段の中には AI の段（テストの実行器を書く `suite-loop`）が在るので、表の確かめが欠けた run はその前に止める（「欠ければ AI を起こさずに止まる」）。書き方の決まり（止めた Archon a972888a の源で確かめた）: `when:` は括弧を持てない（`packages/workflows/src/loader.ts` の `unsupportedConditionSyntax` が「Grouping parentheses are not supported」で読み込みを拒む。`condition-evaluator.ts` の頭「AND has higher precedence than OR. No parentheses.」）ので、OR-of-AND に展開して書く。評価は左から進み、`&&` も `||` も途中で打ち切る（`evaluateCondition`）。飛ばされた node の欄を実際に読むと、偽にならずに node を落とす（`output-ref.ts` の `producer-not-run`）。そのため、飛ばされうる `spec-entry` の出力を読む節は必ず `||` の後ろに置き、前の節を `from_spec == false` で終える。依頼の文の run では前の節が真になった所で打ち切り、`$spec-entry.output.ok` を読まないので、`answer-start` だけで今と同じに回る。仕様駆動の run では前の節が `from_spec == false` で偽になり、後ろの節で `spec-entry` の答えを読む。
3. `judge`: `when:` を `"$test-gate-base.output.ok == true"` から `"$test-gate-base.output.ok == true && $start.output.from_spec == false"` にする。判定の後ろの node（`judge-out`・`tiers`・`owed`・`structure`・`structure-in`・`independent-design`・`design-in`・`plan-rounds`・`plan-rounds-out`・`ask-before-fix`・`gate-before-fix`・`answer-before-fix`）は、`judge` が飛ばされると依る物が欠けて飛ぶ（今の `depends_on` と `trigger_rule` のまま。`when:` は足さない）。飛ぶことは 6.5 の筋書きで確かめる。
4. `fix-in`: `depends_on` に `spec-rounds`・`spec-answer-before-fix` を足し、`with:` に `spec: {from: "$spec-rounds.output", if_skipped: null}`・`spec_before_fix_go: {from: "$spec-answer-before-fix.output.go", if_skipped: null}`・`spec_before_fix_answer: {from: "$spec-answer-before-fix.output.answer", if_skipped: null}`・`spec_before_fix_policy: {from: "$spec-answer-before-fix.output.policy", if_skipped: null}`・`spec_deferred: {from: "$spec-ask-before-fix.output.deferred", if_skipped: null}`・`spec_passes: {from: "$spec-ask-before-fix.output.passes", if_skipped: null}` を足す。`workflows/line/scripts/fix_in.py` は、`spec` が在る時だけ、判定の部と往復の部を `spec-rounds` の返り（`judge`・`rounds`。今の `judge-out` と `plan-rounds-out` の受け皿の `got` と同じ形）から取り、修正前の承認の答えを `spec-` の付いた 4 つから取って、今と同じ式で平らな欄にする（`go` は修正前の承認を通ったか。今の通常の run と同じ）。ほかの run ではどれも null で、今の組み方のまま。
5. `fix`・`refix-run`: `with:` に `routes: "$start.output.ports.routes"` を足す（7 章）。
6. `after-fix`・`fixed`: 仕様駆動の run（`start` の `from_spec`）では、修正の段の異議から案の直し（`replan`）と再審（`rejudge-run`）へ進まず、異議を名指して止めて人に返す。訳: 案の直しは run の中で計画の審査を回す（`replan-review`）。持ち主の決め `spec-driven-shape` は run の中で計画の審査の往復をしない・食い違えば仕様を書き換えずに止まる、と決めた。
7. `collect`: `depends_on` に足す node を全部足し（修正前の承認ノードの記録は、`spec-` の付いた 3 つが在ればそちらを読む）、block `works-factory-spec-driven` の `report` を報告の節に渡す。

足す node（どれも仕様駆動の run だけで回る）:

1. `spec-entry`（`include: works-factory-spec-driven`。`depends_on: [answer-start]`・`when: "$answer-start.output.go == true && $start.output.from_spec == true"`）: `with: {mode: "entry", table: "$start.output.ports.spec_table", base: "$start.output.ports.base_rev", lang: "$start.output.ports.lang"}`。返り `{ok, stop_reason, reason, request, origin, purpose, spec, spec_files, tdd, out_of_scope, report}`（`out_of_scope` は表の触らない物の写しで、形 check が受ける。6.9 の 3。`spec_files` は表と設計書のパスの配列、`request` は判定の役に渡す依頼の行のファイルの pointer、`origin` はその出どころの名、`purpose` は目的のファイル `{purpose_text, source, known_weaknesses, source_files}` の pointer、`spec` は計画の部品に渡す「固めた仕様」のファイル〔設計書の本文と表〕の pointer、`tdd` は設計書に「TDD で直す所」の項目が在るか）。試験の段より前に置く訳: 表の中身の確かめ（2.3 の 1〜5）が欠けた run を、AI を起こす前に止める（試験の段は中に AI の段を持つ。6.2 の変える node の 2）。表を読むのはこの node の script だけ（6.7）。判定の役と修正が読む直す前の結末（`baseline`）は、試験の段の返りから直に受ける。
2. `spec-entry-out`（受け皿 `*receiver`）。
3. `spec-diagnose`（`include: works-factory-diagnose`。`depends_on: [spec-entry, test-gate-base]`・`when: "$spec-entry.output.ok == true && $test-gate-base.output.ok == true"`）: `with: {request: "$spec-entry.output.request", request_origin: "$spec-entry.output.origin", base: "$start.output.ports.base", purpose: "$spec-entry.output.purpose", request_files: "$spec-entry.output.spec_files", baseline: "$test-gate-base.output.baseline", policy: "$start.output.ports.policy", lang: "$start.output.ports.lang"}`（素材・世界の解の行・頭の深さの行は渡さない。既定の空。素材なしで止まらないことは 2.5 の試しで確かめた。入力 `request_files` は 9 章で足す）。
4. `spec-diagnose-out`（受け皿）。
5. `spec-plan`（`include: works-factory-plan`。`depends_on: [spec-entry, spec-diagnose]`・`when: "$spec-diagnose.output.ready == true"`）: `with: {judgment: "$spec-diagnose.output.judgment", units: "$spec-diagnose.output.units", answer_ties: "$spec-diagnose.output.answer_ties", materials: "$spec-diagnose.output.materials", spec: "$spec-entry.output.spec", routes: "spec", policy: "$start.output.ports.policy", base: "$start.output.ports.base_rev", review_rev: "$start.output.ports.review_rev", diff_base: "$start.output.ports.base", lang: "$start.output.ports.lang"}`（`prior` は空、`ruling` は `[]`。入力 `routes` は 7 章で足す）。
6. `spec-plan-out`（受け皿）。
7. `spec-check`（`include: works-factory-spec-driven`。`depends_on: [spec-entry, spec-diagnose, spec-plan]`・`trigger_rule: none_failed_min_one_success`・`when: "$spec-entry.output.ok == true"`）: `with: {mode: "check", tdd: "$spec-entry.output.tdd", out_of_scope: "$spec-entry.output.out_of_scope", out_of_purpose: {from: "$spec-diagnose.output.out_of_purpose", if_skipped: null}, ready: {from: "$spec-diagnose.output.ready", if_skipped: null}, plan: {from: "$spec-plan.output.plan", if_skipped: null}, plan_ok: {from: "$spec-plan.output.ok", if_skipped: null}, base: "$start.output.ports.base_rev", lang: "$start.output.ports.lang"}`。返り `{ok, stop_reason, reason, mismatches, report}`。
8. `spec-rounds`（script `spec_rounds`。line の `scripts/`。`depends_on: [spec-check, spec-diagnose-out, spec-plan-out]`・`when: "$spec-check.output.ok == true"`・`mutates_checkout: false`）: 判定の役と計画の部品の返りを、今の `judge-out` と `plan-rounds-out` の受け皿の `got` と同じ形に組み直す（受け皿は、include した graph の返りを欄 `got` に受けて後ろの node に渡す script `returned` の node。本線の YAML で `judge-out` は判定のまとめ `judge` の返りを、`plan-rounds-out` は計画の往復 `plan-rounds` の返りを受け、受ける欄の名は各 node の `names` に並ぶ。後ろの段は `$judge-out.output.got` などを読む）（判定の部は `fix_in.py` が読む欄を全部持ち、値は 6.8 の 1。往復の部は `ask_before_fix` が求める欄（`ROUNDS` の 21）を全部持つ。値: `plan`・`fix_plan`・`ripple`・`reply`・`owed` は計画の部品の返り、`done` と `ok` は真、`status` は計画の部品の返りの語（`nothing_owed` にしない。直す義務が 0 件なら形 check の 2 で止まっている）、`round` は 1、`plan_prior`・`record`・`review`・`gave_up` は null、`stalled`・`capped` は偽、`handoffs` は空の配列、`review_status` は `ok`（`workflows/line/src/gates.py` の表 `REVIEW_FELL` は、事前審査が諦めた `gave_up` と落ちた `failed` を鍵に持ち、`review_status` がそのどちらかの周だけ、事前審査を理由に承認ノードを開く。`ok` はどちらの鍵にも当たらないので、事前審査を理由には開かせない）、`review_reason` と `stop_reason` は空、`asks` は下の「narrows の項目」、`deviations` は空の配列（下の訳）。返り `{judge, rounds}`。組み直しを 1 か所に置き、修正前の承認ノードの前の段と `fix-in` が同じ値を読む。
   - narrows の項目（`asks`）: 今の本線では、計画の行の `narrows` を承認ノードの項目（「修正案 N が狭める能力: …」の行と、4 つの軸ごとの揃わない訳 `why`）に変えるのは計画の審査の block（PR #815 の前の `workflows/plan-review/src/gate.py` の `asks`・`_gate_rows`・`axis_reasons`）で、仕様駆動の run はその block を回さない。line から plan-review の `src/` を import するのは憲法の 3 と E22 に反する。そこで、行を作って軸の訳を付ける芯を `lib/gatemarks.py` に上げ（口 `narrow_asks`・`ask_row`・`axis_why` と材料の形 `AxisFacts`。PR #815 で上げた。下の「置き場」と 6.8 の 2）、計画の審査の block（今は `gate.py` の `asks` が `narrow_asks` を呼び、事前審査の穴の行は `_face_rows` と `ask_row` で作る）と `spec-rounds` の 2 か所が使う。`spec-rounds` は計画の部品の返りの `plan` を渡し、軸の訳の材料は仕様駆動の run の物で埋める: 決め手の出どころの照らし（`lib/cite.py` の `sources_problem`）は依頼の引用の元を表と設計書の本文にし、世界の解（依頼の各行を業界の定石と照らす観点。block `world`、[world.md](world.md)）の行は無い（今の本線の「世界の解の行の無い run」と同じ当たり方で、`world` も URL も無い narrows は軸 `world` が揃わない）、構造の目の行は無い（軸 `clean` の訳は付かない）。開くかを決めるのは今と同じ `gates.before_fix` なので、決まっていない narrows（`decided_by` が無いか `undecided_because` が在る・出どころが現物に無い）は今の本線と同じ条件で承認ノードに出る。無人の run の推し（役が問いに添えた、選択肢を名指す勧めの答え。無人の run はそれを答えとして採って進む。[line.md](line.md) の 6 節）の扱いも今と同じ。
   - 置き場（憲法の 4・E22。工場窓口の決め 2026-10-21、受付 20261021-032859-d0e839）: 芯は Archon の port を知らない（受けるのは計画の行の並び・入口が外した決め手の欄（計画の審査の block の入口 `intake` が、審査の役に見せる前に narrows の行から外して `plan_marks` に控える `decided_by` などの欄）・出どころの照らしの口・世界の解の行の有無・構造の目の単位の集まりの値だけで、place も `INPUTS_` も読まない）ので、`workflows/.shared/` でなく `lib/` に置く。既に narrows の決め手の欄の名（`FIELDS`）・`decided`・`AXES`・訳の字を持つ `lib/gatemarks.py` に足す。計画の審査の block の `gate.py` は、place から材料を集めて `narrow_asks` に渡す形に替え、事前審査の穴の行（`faces`）と `deviations` は今のまま block に残す。
   - 計画の審査の block の振る舞いが変わらないことの縛り: 今の `tests/blocks/plan_review/test_gate.py`（`test_narrows_and_human_faces_are_rows_with_the_gate_heads` ほか、`asks` の行と軸の訳を照らす試験）を 1 字も変えずに通す。`lib/tests/` に `narrow_asks` の試験を足し、計画の審査の block の筋書き（`workflows/plan-review/fixtures/`）も期待を変えずに通す。
   - `deviations` を空にする訳: 今の本線の `deviations` は、計画の行の欄 `structure` が世界の解の行から外れると答えた行（run の中の世界の解の行が要る）と、計画の審査の穴のうち独立設計との食い違い（run の中の計画の審査が要る）の 2 つから作る。仕様駆動の run の中ではどちらも回らない。世界の解と独立設計は仕様を固める会話の中で回し、その指摘（世界の解の `differs` の行など）は、持ち主が受け入れた物だけが受け入れた言葉つきで表の `reviews[].findings` に残り、入口の確かめ（2.6 の 2 の e）が全部受け入れ済みであることを照らす。人が会話の中で既に見て決めた物を、承認ノードでもう 1 度聞かない（同じ事を 2 度回さない）。表の `findings` から `deviations` を起こさないのは、表の欄を足さず（持ち主の決め `spec-driven-shape` の「表は 4 つだけ」と運ぶ欄 `reviews`）、受け入れ済みの物を承認ノードの軸 `world` の揃わない訳にしないため。
9. `spec-ask-before-fix`（今の `ask-before-fix` と同じ script `ask_before_fix`・同じ `output_format`。YAML の錨で本体を 1 か所にする。`depends_on: [spec-rounds]`）: `with: {rounds: "$spec-rounds.output.rounds", structure: null, judge: "$spec-rounds.output.judge", record: "$start.output.record", ports: "$start.output.ports"}`。
10. `spec-gate-before-fix`（今の `gate-before-fix` と YAML の錨で `wait:` の `form`・`options` を共有し、`attention` だけは `"$spec-ask-before-fix.output.text"` を読む。今の `gate-before-fix` の `wait.attention` は `$ask-before-fix.output.text` を読むので、`wait:` を丸ごとは共有できない。今の `gate-before-fix` に錨を付けると YAML の字は変わるが、振る舞いは変わらない。`depends_on: [spec-ask-before-fix]`・`when: "$spec-ask-before-fix.output.open == true"`）。
11. `spec-answer-before-fix`（今の `answer-before-fix` と同じ script `before_fix_answer`。`depends_on: [spec-ask-before-fix, spec-gate-before-fix]`・`trigger_rule: none_failed_min_one_success`）: `with:` は今の `answer-before-fix` の `ask-before-fix`・`gate-before-fix` を `spec-` の付いた物に替えた物。

修正前の承認ノードの扱い（工場窓口の答え。2026-10-21、受付 20261021-025739-b542bf）: 仕様駆動の run でも、今の本線と同じ条件で修正前の承認ノードを出す。開くかを決めるのは今と同じ script `ask_before_fix`（能力を狭める物 `narrows`・人に決めてほしい点・方針の変わり・無人の run の扱い）で、仕様駆動の run だけ、渡す値の出どころが `spec-rounds` になる。条件に当たらなければ出さない（今の本線と同じ）。依頼の文の run の `ask-before-fix`・`gate-before-fix`・`answer-before-fix` は変えない（`spec-` の付いた 3 つを別に置くのは、今の 3 つの `depends_on` と `trigger_rule` を変えずに済ませ、依頼の文の run の振る舞いを動かさないため）。訳: 元と同じにそろえる。持ち主の言葉「１と２のサイクルの中にはいればいいからどこでもいいと思うよ」は、計画の往復に人が入る場所を問わないという意味で、修正前の承認ノードを外す話ではない。計画の AI が工場の中で書いたファイルの行に狭める物や決めてほしい点が出れば、今の本線と同じに人に見せる。

### 6.3 計画の部品に渡す物

- `judgment`・`units`・`answer_ties`・`materials`: 判定の役の返り。計画の部品は判定が無いと役を起こさない（入力 `judgment` の説明「空の字は判定が無い（形 plan では役を起こさない）」）ので、判定の役を先に通す要がある。
- `spec`: block の形 entry が組む「固めた仕様」のファイル。中身は設計書の本文と表（`reviews` を除く）。計画の部品の指示は、この入力を「Spec (requirements and acceptance tests. Put each acceptance test in the tests of the item that holds its unit)」の節に字のまま貼る（JSON でない物は字のまま。入力 `spec` の説明）。表の受け入れの条件 1 件を、その単位を持つ計画の行の `tests` に置かせる所は、今の指示のまま当たる。
- 計画の部品の指示は変えない。変えるのは 7 章の `routes` の 1 段落だけ。

### 6.4 形 check の照らし（仕様とリポジトリの食い違い）

どれも yes/no。1 つでも当たれば `ok: false` で、当たった物を `mismatches` に名指して止める（人が仕様を直したら新しい run）。

1. （前の版の「判定の役が問いを返した」は外した。問いは今の本線と同じく修正前の承認ノードで人に見せる。6.2 の修正前の承認ノードの扱い）
2. 判定の役が直す単位を返さなかった（`ready` が偽）、か計画の部品が落ちた（`plan_ok` が偽）。
3. 計画の行のファイルの行で、`op` が `modify`・`delete` なのにパスが作業ツリー（`base` の版）に無い、`create` なのに在る、`rename` で `from` が無いか `path` が在る。
4. 表の `out_of_scope` の glob が、計画の行のどれの `out_of_scope` にも無い。
5. （前の版の「設計書で決まっていない `narrows`」は外した。能力を狭める行は今の本線と同じく修正前の承認ノードで人に見せる。持ち主の決め `no-narrow` の当て方と同じ）
6. 設計書に「TDD で直す所」の項目が無いのに `route` が `tdd` の行が在る、か項目が在るのに `tdd` の行が 1 つも無い（7 章）。
7. 判定の役が目的の外とした行（`out_of_purpose`）が在る: 設計書が表の目的と受け入れの条件の外の物を書いている（2.5 の判定の役の試しで、設計書 9 節の入口の workflow が当たった）。

人に聞くはずの物（判定の役の問い・能力を狭める行）は止めずに、今の本線と同じ条件で修正前の承認ノードに出す（6.2 の足す node の 9〜11）。形 check が止めるのは、仕様とリポジトリが食い違う物（2・3・4・6・7）だけ。番号は前の版のまま残した（2.5 と 8 章が番号で指すため）。

### 6.5 依頼の文の run の振る舞いが変わらないことの縛り

issue #802 の受け入れ「本線の振る舞いは変わらない」は、依頼の文（`request`）・差分（`base`・`pr`）・固定材料で入る run の振る舞いが変わらないことで守る。変えた node は `start`・`test-gate-base`・`judge`・`fix-in`・`fix`・`refix-run`・`after-fix`・`fixed`・`collect` の 9 つ（今の `ask-before-fix`・`gate-before-fix`・`answer-before-fix` は変えない）で、どれも `spec_table` が空なら今と同じ値で動く。縛る試験（実装の PR で足す）:

1. 今の本線の筋書き（`workflows/line/fixtures/*.stubs.yaml` の全部。`tests/blocks/line/test_scenarios.py`・`test_scenarios_gates.py`）を、期待（`reached`・`expect`・出力の値）を 1 字も変えずに通す。
2. `tests/blocks/line/test_scenarios.py` に、依頼の文の筋書きのどの dry-run の trace にも仕様駆動の道で足す node（id の並び `SPEC_DRIVEN_NODES`。頭の字 `spec-` では名指さない。前からの `spec-check-run` が依頼の文の run でも走るため。6.8 の末尾）が走らず、`judge` が走ることを照らす試験を足す。node が「走っていない」は trace の state が無いか `skipped` の時だけで、`failed` も走ったと読む。`SPEC_DRIVEN_NODES` の名が line の YAML に在ることも照らす（名がずれた時に何も照らさずに通らないため）。
3. `tests/blocks/line/test_fix_in.py` に、`spec_check`・`spec_judgment`・`spec_plan` が null の時の返りが、足す前の返りと全部の欄で同じことを照らす試験を足す（今の試験の入力をそのまま使う）。
4. `tests/blocks/line/test_start.py` に、`spec_table` が空の run の返りで `from_spec` が偽・`ports.spec_table` が空・`ports.routes` が `auto` で、ほかの欄が今と同じことを照らす試験を足す。
5. `tests/blocks/line/test_wiring.py` に、足す node（`SPEC_DRIVEN_NODES` の id の並び。2 と同じく頭の字では名指さない）の `when:` がどれも `from_spec == true` か `spec-entry` の出力を読む句を持つこと、`judge` の `when:` が `from_spec == false` を持つことを照らす試験を足す（yes/no。憲法の 6）。
6. 部品に足す入力（修正の部品の `routes`・計画の部品の `routes`・判定の役の `request_files`）は、どれも既定値で今の振る舞いのまま。それぞれの block の試験（`tests/blocks/fix/`・`tests/blocks/plan/`・`tests/blocks/diagnose/`）に、既定値の時に今と同じ返りになることと、名指した値の時の振る舞いを照らす試験を足す。本線の依頼の文の run は既定値しか渡さない（6.2 の変える node の 5 は `ports.routes` が `auto`）。
7. 仕様駆動の道の筋書き `workflows/line/fixtures/spec-driven.stubs.yaml`（通って修正まで届く）・`spec-refused.stubs.yaml`（入口の確かめで止まり、AI の node に届かない）・`spec-mismatch.stubs.yaml`（形 check で止まる）を足す。
8. 修正前の承認ノードが依頼の文の run と同じ条件で開くこと: `tests/blocks/line/test_wiring.py` に、`spec-ask-before-fix`・`spec-gate-before-fix`・`spec-answer-before-fix` が今の 3 つと同じ script・同じ `output_format`・同じ `wait:` の `form` と `options` を持ち（YAML の錨で本体が 1 つ）、`spec-gate-before-fix` の `attention` だけが `spec-ask-before-fix` を読むことを照らす試験を足す。筋書き `workflows/line/fixtures/spec-gate.stubs.yaml`（計画の部品が `decided_by` の無い能力を狭める行を返し、`spec-rounds` が `lib/gatemarks.py` の `narrow_asks` でそれを項目にし、`spec-ask-before-fix` の `open` が真になって `spec-gate-before-fix` が開く）と `spec-unattended.stubs.yaml`（無人の run で、今の本線の無人の筋書きと同じ結果になる。項目の全部が推しの尾を持てば推しで進み、そうでなければ開かずに止まる。[line.md](line.md) の 6 節）を足す。`tests/blocks/line/test_rounds.py` か新しい `test_spec_rounds.py` に、`spec-rounds` の返りが今の受け皿の `got` と同じ鍵を持ち、値が上の決め（`ok` が真・`status` が `nothing_owed` でない・`review_status` が `REVIEW_FELL` に当たらない・`deviations` が空）どおりで、`decided_by` の無い narrows が `asks` の行になることを照らす試験を足す。

### 6.6 足す仕組みの E11 の 3 つの確かめ

- 本線の入力 `spec_table` と block `works-factory-spec-driven`: 4 章の答えのとおり（Archon も ASF も、人の仕様を受けて工場の守りつきで実装させる道を持たない。要るのは持ち主の困りごとと決め `spec-driven-shape` から）。block は AI を持たず、機械の照らしだけ。
- 表の照らしと部品に渡す入力の組み立て（6.7）: Archon・ASF は表の形を持たない。要るのは入口の確かめを 1 か所にするため。
- 起動の殻が部品の run の記録を読んで run に渡す口（2.6 の 2）: Archon は run の記録を `workflow get <run> --json` で返す（持つ。これを使う）。ASF は持たない。要るのは持ち主の「ある程度壁打ちの中で問題ないかはちゃんと見てほしい」を、表の書き写しだけで破れないようにするため。殻に仕組みを足すので、持ち主の決めを先に `docs/owner-decisions.md` の `spec-driven-shape` に書いた（E10。この PR の commit `751d6b8`）。

### 6.7 表（YAML）を読む所

表は持ち主の決め `spec-driven-shape` どおり YAML 1 本にする（工場窓口の答え。10 章）。YAML は Python の標準ライブラリで読めないので、外のパッケージ PyYAML を使う。外のパッケージそのものは使ってよい（持ち主の決め `outside-packages-ok`。`lib/AGENTS.md` の E3）。縛っているのは、E3 の 1 文「Archon の `runtime: uv` の script のノードは `deps:` を持たず、標準ライブラリと `lib/` だけで書く」と、script の頭を `# dependencies = []` に固める試験（`tests/workflows/test_uv_scripts.py` の `HEADER`）の 2 つで、持ち主の決めではない。この 2 つに外しを 1 つだけ足す。

- 読む所: block `works-factory-spec-driven` の形 entry の入口の script 1 本（`workflows/spec-driven/scripts/intake.py`）。頭の宣言を `# dependencies = ["PyYAML==6.0.3"]` にする。表を読んで照らした後、中身を JSON にして place に置き、後ろ（形 check・判定の役・計画の部品・本線の `fix-in`）は JSON か出力の欄だけを読む。形 check の script は表を読み直さず、形 entry の出力（`tdd`・表の `out_of_scope` の写し）を受ける。
- 読む所を本線の `start` に置かない訳: `start` はどの run でも回るので、依頼の文の run まで uv が PyYAML を入れることになる（初めての run で取りに行き、取れない環境では落ちる）。表を読む所を仕様駆動の run だけで回る node に寄せる方が、外しが小さい。
- 表の中身の確かめ（2.3 の 1〜4）を起動の殻だけに置かない訳: 殻を通さない run（Archon の命令をそのまま打つ・筋書きの dry-run）で表の形が照らされず、block の入口の確かめが殻に頼ることになる。1〜4 は block の入口が自分で照らし、殻が要るのは Archon の記録を読む 5 だけにする（5 の扱いは 2.6 の 2 の「block の単独の run」）。
- 殻の側の読み（E14）: 殻（`bin/works-factory`）は `#!/usr/bin/env python3` の素の Python で動き、標準ライブラリと `bin/`・`lib/` だけを使う（今の `bin/` と `lib/` に `import yaml` は無い）。根の `pyproject.toml` の PyYAML は試験のための物で、殻を起こす時には入らない。普通の利用者（`claude /login` しただけの人など。持ち主の決め `others-may-use`）の環境に PyYAML は無いので、殻の Python で `lib/spectable.py` を import すると落ちる。そこで、殻は表を読む所だけを uv で起こす: `bin/_lib/` に PEP 723 の頭（`# dependencies = ["PyYAML==6.0.3"]`）を持つ小さな script を 1 本置き、殻が `uv run --script <その script> <表のパス>` で起こす。その script は `lib/spectable.py` で表を読み、`reviews` の run の id と、部品ごとに組んだ入力を JSON で標準出力に返すだけ。Archon の記録を読んで a〜e を照らすのは、殻の素の Python のまま（標準ライブラリだけ）。選んだ訳: uv は Archon の `runtime: uv` の script のノードを回すのに要るので、Archon を使う人は既に持つ（`others-may-use` の当て方）。殻のほかの起動（`spec_table` も `table` も名指さない起動）は uv を起こさず、今と何も変わらない。退けた案: 表の読みを殻の外へ出す（殻より前に表を読める所は無い。run の中の script は Archon の記録を読めない）。殻は PyYAML に頼らない（YAML の読みを自前で書くことになり、既製を先に当たる決め `reuse-first` に反する）。
- 版の縛り: PyYAML の版は、根の `pyproject.toml`・block の入口の script の頭・殻の表を読む script の頭の 3 か所に同じ字 `PyYAML==6.0.3` で書く。3 か所が同じことを、`tests/workflows/test_uv_scripts.py` に試験を足して縛る（殻の script は `workflows/` の外なので、その試験の照らす先に `bin/_lib/` のこの 1 本を名指して足す）。依存の宣言を 1 か所に置く E3 の向きは、2 か所目と 3 か所目を試験で 1 か所に結び直して崩さない。
- 決まりの直し（実装の PR）: E3 の上の 1 文に「外し: `workflows/spec-driven/scripts/intake.py` と、起動の殻が表を読む `bin/_lib/` の PEP 723 の script の 2 本は、表の YAML を読むため PyYAML を持つ」を足し、試験の `HEADER` の照らしに `workflows/` のこの 1 本の外しを名指して足す（ほかの script の頭は今のまま `dependencies = []`。殻の側の 1 本は版の縛りの試験が照らす）。[archon.md](archon.md) の「層の E3 の `deps:`」は「`deps:` を持つ script のノードは無い」と書いているので、同じ PR で直し、uv の宣言で PyYAML が入ることを通しで確かめる（今は未確かめ）。
- 表の読みと入力の組み立てのコードの置き場: block と起動の殻（2.6 の 2）の 2 か所が使うので `lib/spectable.py` に置く（憲法の 4）。Archon を知らない物（表の YAML を読み、schema で照らし、部品ごとの入力の字を組む）だけを置く。Archon の run の記録を読んで a〜e を照らす所は、Archon を知る殻の `bin/_lib/` に置く（E3）。`lib/spectable.py` は PyYAML を import する（外のパッケージは使ってよい。E3）。import する側はどれも PyYAML を宣言した uv の script（block の入口の script と、殻の表を読む script）で、殻の素の Python からは import しない。

### 6.8 実装の PR で決めた事（PR #809 の 3 回目のレビューの「後でよい物」）

工場窓口の頼み（2026-10-21、受付 20261021-050237-e8e64f）が、3 回目のレビューの「後でよい物」の 3 つをこの実装で決めて書くと決めた。

1. `spec-rounds` の返りの判定の部（`judge`）の値。`fix_in.py` が `ports.picked` で読む欄（`NAMES["judge"]` の 21）を全部持たせ、値は次のとおり。決め方は「今の本線で、その欄を作る段が回らなかった run と同じ値」にそろえる（判定の graph のまとめ `workflows/judge/src/verdict.py` の `build` が、段の返りが無い時に入れる値）。
   - 判定の役 diagnose の返りをそのまま運ぶ欄: `ready`・`units`・`judgment`・`answer_ties`・`out_of_purpose`・`materials`・`brief`・`inputs`（と `questions`。今の受け皿の `got` も持つ）。
   - `ok` は真、`stop_reason` は空。訳: `spec-rounds` は形 check を通った run（判定の役が直す単位を返し、計画の部品が落ちていない）だけで回るので、判定は止まっていない。`fix_in.py` の `no_fix` の式は `ok` が真・`ready` が真なので今と同じに偽を出す。
   - `purpose` は形 entry が組む目的のファイル（判定の役に渡した物と同じ pointer）、`purpose_text` は表の `purpose`、`means` は空の配列（依頼の解き方は目的の固定の段が依頼から拾う物で、仕様駆動の run では回らない）。
   - `tier` は、入力 `thickness` が段を名指せばその段（`ports.forced`）、名指さなければ `標準`（`headdepth.STANDARD`）。訳: run の頭の深さの段が回らなかった run で判定のまとめが入れる値と同じ。どちらも段の表の語なので、`tiers.switches` は「段の語が表に無い」の行を出さない。`tier_record` は null（頭の深さの段の記録が無い run と同じ）。
   - `constraints`（前提の実測）・`world`（世界の解の行）・`spec`（仕様の段）・`excluded`（並行 PR）・`decisions`（前の決めの確かめ）・`verify`（判定の単位の裏取り）は null。訳: どれも仕様駆動の run の中で回らない段の返りで、今の本線でもその段が回らない run は null になる。前提の実測・世界の解・前の決めの確かめは会話の中で回し、入口が記録を照らした（2.6 の 2）。判定の裏取りは 6.2 で入れない（判定の役を 1 回回すだけ）。`fix-in` の後で `verify` を読むのは案の直し（`replan`）と再審（`rejudge-run`）だけで、どちらも仕様駆動の run では回らない（6.2 の変える node の 6）。
   - 縛り: 6.5 の 8 の試験（`spec-rounds` の返りが今の受け皿の `got` と同じ鍵を持つ）に、この値を照らす行を足す。`tier` が段の表の語で、`fix-in` の返りの `switches.lines` に「段の語が表に無い」の行が無いことも照らす。
2. `lib/gatemarks.py` の `narrow_asks` が受ける材料。値だけを受ける形にし、place も Archon の port も読まない。
   - `narrow_asks(plan, marks, facts)`: `plan` は計画の行の並び（計画の部品の返りの `plan` の先の `plan[]`）、`marks` は計画の審査の block の入口 `intake` が narrows の行から外して控えた決め手の欄（`decided_by` などの欄。形は 2 重の並びで、`marks[i][j]` が計画の項目 `i` の `narrows` の `j` 番目の行から外した欄の dict。無ければ None で、行に残った欄を読む）、`facts` は 4 つの軸の材料 `AxisFacts`。
   - `AxisFacts`: 出どころの照らしの口 `cite_ok`・世界の解の行が在るか `world_rows`・構造の目が人に上げた単位 `ups`・汚れると見た単位 `dirty`・修正案の欄 `structure` に答えのある行の単位 `answered`（None は照らさない）・計画の単位 `planned`。レビューが挙げた「答えのある行の単位」と「計画の単位」は `answered` と `planned` に当たる。
   - 軸の訳を付ける所 `axis_why(facts, mark, units)` と、行 1 つを組む `ask_row(facts, kind, text, mark, node, units)` も `lib/` に置き、計画の審査の block は事前審査の穴の行（`faces`）にも同じ口で軸の訳を付ける（block に軸の訳の写しを残さない。憲法の 4）。盤面を読む古い口 `gatemarks.axis_reasons` も、盤面から材料を集めて `axis_why` を呼ぶ形にした（軸の決まりの持ち主は 1 か所）。
   - 仕様駆動の run の `spec-rounds` が渡す材料: `cite_ok` は依頼の引用の元を表と設計書の本文にした `cite.sources_problem`、`world_rows` は偽、`ups`・`dirty` は空、`answered` は None、`planned` は計画の行の単位（`converge.planned_units`）。
3. 独立の目に見せる事前審査の結論: 今のまま「読めない」（`verdict: unread`・訳「往復の記録が渡されていない」）と出す。`eyes-in` は変えない。
   - 訳: 独立の目の欄 `review` は「修正が使った修正案を審査した最後の往復の結論」（`shared:plan-verdict.schema.json`）。仕様駆動の run で修正が使う計画の行は、run の中で計画の AI が起こした物で、計画の審査は通っていない。表の `reviews` が持つのは、会話の中で設計書（方針の文）を審査した記録で、修正が使った計画の行の審査ではない。表から `accepted` などを組むと、審査していない行を審査済みと見せることになる。
   - `unread` は表示だけの事で、最後の承認ノードを開く理由（`final.py` の `unread`）には入らない（3 回目のレビューで確かめた）。訳の字「往復の記録が渡されていない」も、仕様駆動の run では字のとおり正しい。
   - 会話で回した審査の記録は、block `works-factory-spec-driven` の `report` が報告の節に載せる（6.2 の変える node の 7）。

PR の分け（頼みの 4。1 本ずつレビューに通せる大きさにするため、設計書の章の順で 3 本に分ける）:

1. 1 本目: `lib/` の口（`gatemarks.narrow_asks`・`axis_why`・`ask_row`・`AxisFacts`）と計画の審査の block の置き換え、依頼の文の run が変わらないことを縛る試験（6.5 の 2 と 3。足す前に書ける物）、この節。
2. 2 本目: block `works-factory-spec-driven`（形 entry と check・表の schema・筋書き）・`lib/spectable.py`・起動の殻の照らし（2.6 の 2）・計画の審査の入力 `proposal_file`（2.5 の詰まった所の 2）・E3 と E15 の外し・PyYAML の版の縛り（6.7）。
3. 3 本目: 部品に足す入力と返り（修正の部品と計画の部品の `routes`・判定の役の `request_files`・前提の実測の `contradicts` と前の決めの確かめの `conflicts`、と 2.6 の 2 の e への足し。7・9 章と 2.5）と本線の配線（6.2）・`spec-rounds`・6.5 の残りの試験と筋書き。

6.5 の 2 の試験は、足す node を頭の字 `spec-` でなく id の並びで名指す（`tests/blocks/line/test_scenarios.py` の `SPEC_DRIVEN_NODES`）。訳: 本線には前から仕様の段の照らし `spec-check-run` が在り、依頼の文の run でも走るので、頭の字で照らすと今の run が落ちる。

### 6.9 2 本目の PR で決めた事（block・表の読み・殻の照らし）

1. 表の schema の置き場: `lib/spectable.py` の `SCHEMA`（写しの engine の型検査 `validate_schema` で照らす）。前の版の仮の置き場 `workflows/spec-driven/schemas/spec-table.schema.json` は使わない。訳: 表を照らすのは block の入口と起動の殻の 2 か所で、`lib/` は `workflows/` の物を読まない（E22）。block の入力 `table` は形 `file:` で、入力の形の検査（README の 7.1 の 5）が schema のファイルを求めない。
2. block の node: `pick`（入力 `mode` を読む。標準ライブラリだけ）→ 形 entry の `intake`（表を読むただ 1 本。PyYAML を宣言）か形 check の `check` → `finish`（形の控え `entry.json`・`check.json` を読んで返す）。返りは 2 つの形の欄を併せ持ち、使わない形の欄は空の値。止めの語は `works:spec-entry`（入口の確かめ）と `works:spec-mismatch`（食い違いの照らし）。
3. 形 check の入力: 6.2 の足す node の 7 の `with:` から `table` と `questions` を外し、`out_of_scope`（形 entry の返りの、表の触らない物の写し）を足した。訳: 6.7 は「形 check の script は表を読み直さず、形 entry の出力（`tdd`・表の `out_of_scope` の写し）を受ける」と決めており、表のパスを渡すと PyYAML を持たない形 check が読めない。`questions` は 6.4 の 1 を外した後に読む物が無い。
4. 2.6 の 2 の d の比べ方（未確認の一覧の 1 つ目）:
   - 比べる鍵は、入力の組み立て（`lib/spectable.py` の `part_inputs`）が組んだ鍵だけ。Archon は直に起こした run の `metadata.inputs` に名指した入力だけを残し、既定値は残さない（止めた Archon の `packages/workflows/src/utils/workflow-requirements.ts` の `resolveTopLevelInputs`）。会話の AI がほかに名指した入力（世界の解の `web`・`lang` など）と、部品に後で足した入力は比べない。
   - 値が JSON（依頼の行の配列）なら、記録の字を JSON として読んで値で比べる（空白の違いで落とさない）。
   - パスは対象の根からの相対で組む（表と設計書の `where`・前の決めの確かめの `entry`）。
   - 計画の審査は、方針の文を入力 `proposal_file` で受けた記録だけを通す。比べるのはファイルのパスでなく中身で、計画の審査の返りに足した `proposal_sha256`（形 text で審査した方針の文の sha256。必須の欄にはしない。前からの筋書きの stub が持たないため）と、組んだ方針の文の sha256 を比べる。
   - 「表から `reviews` を除いた字」は `spectable.table_text`（YAML に書き直した字。欄の並びは表のまま）。会話の AI が同じ字を組む手段は、工場の側の命令 `uv run --script bin/_lib/spec-inputs.py <対象の根> <表> --proposal-out <ファイル>` で、部品ごとの `--input` の字（`args`）と方針の文のファイルを出す。殻もこの script で入力を組むので、2 つの組み方は 1 つ。
5. 殻が照らした結果のファイルと env の名（未確認の一覧の 1 つ）: ファイルは run の家の `spec-reviews/<中身の hash>.json`（`{table, table_sha256, design_sha256, problems, rows: [{part, run, ok, why}]}`）。名 `WORKS_FACTORY_SPEC_REVIEWS` は、殻が新しい run の設定の層の `env:` に載せる（Archon が起動の時に封じ、起動の承認ノードの後の `approve` などで続けても同じ値が戻る。子の環境だけに置くと、続ける起動で消える）。block の形 entry は、ファイルが今の表と設計書の物（2 つの sha256）で、行が表の `reviews` と同じ並びで、全部の行が合っていることを照らす。
6. 殻は、表の形と設計書の 1〜4 が欠けた時も Archon を起こさずに止める（記録を照らす前に表を読めないため）。block の形 entry も 1〜4 を自分で照らす（殻を通さない run のため。6.7）。殻が uv を見つけられない時は、uv を PATH に置けと言って止める。表を名指さない起動は表も記録も読まず、uv も起こさない（`tests/bin/test_launcher.py` が縛る。未確認の一覧の 6.5 の殻の試験）。
7. block の筋書き（未確認の一覧の最後の 1 つ）: 単独の run の筋書きは形 entry で見本の表を読み、照らした結果を持たないので入口の確かめの 5 で止めを返して最後まで届く物（`standalone.stubs.yaml`）と、形 check で判定が回らなかった物（`check.stubs.yaml`）の 2 本。照らしが通る道は block の試験（`tests/blocks/spec_driven/`）だけが照らす。筋書きは exec-code で intake を本当に走らせるので、uv の宣言で PyYAML が入ることも確かめる（[archon.md](archon.md) の「層の E3 の `deps:`」）。
8. 計画の審査の入力 `proposal` は必須を外し、既定 `""` にした（`proposal_file` と片方だけを名指すため。どちらも空なら入口が「審査する物が空」で止める）。変更の種類は `workflows/AGENTS.md` の P。

## 7 修正の部品に direct の道をまとめて選ぶ入力（進め方の 4）

今のコードで確かめた事:

- 計画の行の `route` は、修正の部品の TDD の loop が「約束」（承認済みの案の欄。`workflows/fix/src/tdd.py` の `plan_contract`・`_contract`）として読む。
- `tdd` の行は縛る: TDD の役が振り分けの段で、約束が `tdd` の単位を `direct` に振ると拒む（`tdd.py` の `_route` と `_plan_tdd`）。
- `direct` の行は縛らない: 約束が `direct` の単位を TDD の役が `tdd` に振っても拒まない。振り分けの段は AI の手番 1 回で、単位ごとに TDD の役が決め直す。
- TDD の loop は、テストの実行器（`tdd_suite`）が解けた時だけ回る（`tdd.py` の `start` の `NO_SUITE`）。

issue #802 の案の 3「既定は全部の単位を direct の道にし、人が TDD でと書いた行だけ TDD の道を通す」は、今のままでは守れない（TDD の役が direct の単位を tdd に振り直せる）。足す物:

1. 修正の部品に入力 `routes`: `choice(auto|plan): 単位ごとの道の決め方。auto は TDD の役が振り分ける（承認済みの案が tdd の単位は tdd に縛る）。plan は承認済みの案の route をそのまま使い、振り分けの段の AI を起こさない`。既定 `auto`。`plan` の時、振り分けの段は機械が約束から道を決め（単位を持つ行のどれかが `tdd` なら `tdd`、ほかは `direct`。`direct` の訳は行の `route_why`）、`tdd` の単位が 0 なら TDD の loop を回さない。今の run は `auto` で何も変わらない。変更の種類は `workflows/AGENTS.md` の P（入力を足す）。
2. 計画の部品に入力 `routes`: `choice(auto|spec): 行の route の決め方。auto は今の指示のまま。spec は固めた仕様の「TDD で直す所」が名指す行だけを tdd にし、ほかを direct にする`。既定 `auto`。指示は `workflows/plan/prompts/plan-writer.md` の 1 段落（`<!-- if routes_spec -->`）で、Python は真偽だけを渡す（憲法の 2）。変更の種類は P。
3. 本線: 仕様駆動の run だけ、計画の部品に `routes: spec`、修正の部品に `routes: plan` を渡す（6.2）。

設計書の「TDD で直す所」と計画の行の `route` が合うかは、形 check の 6（6.4）が粗く yes/no で照らす（項目の在る・無いと `tdd` の行の在る・無い）。どの行がどの項目に当たるかは機械で照らさない（設計書の文を機械が読み分けられない）。行ごとの当たりは、run の後のレビューと報告が人に見せる。

## 8 計画の審査に止めて人に返す形（進め方の 5）

PR #807 で決めた形（計画と計画の審査の往復を run の前の会話へ移す。1.3 の「実装の前の照らし」）の後では、計画の審査は run の中で回さない（持ち主の決め `spec-driven-shape`）。そのため、計画の審査の部品に「止めて人に返す形」を足す要は無くなった。足さない。

持ち主の決めの「仕様とリポジトリの食い違いの照らし（食い違えば仕様を書き換えずに止まって人に返す）」は、run の中の次の 3 か所がする:

1. 判定の役の問いと能力を狭める行: 止めずに、今の本線と同じ条件で修正前の承認ノードに出す（6.2）。人が答えれば進み、仕様を直すと答えれば止める。
2. 形 check の機械の照らし（6.4 の 2〜4・6・7）: 単位が無い・計画が落ちた・ファイルの行と作業ツリーの食い違い・触らない物の写し漏れ・TDD の印の食い違い・設計書が目的の外を書いている。計画の AI の返りに新しい欄は足さない（今の計画の行を読む）。
3. 修正の段の異議（6.2 の変える node の 6）: 直す役が「案と作業ツリーが合わない」と申し出たら、案の直しへ進まず止める。

計画の審査の部品は、仕様を固める会話の中で、形 text（方針の文だけ）で単独で回す（2.5）。

## 9 keep-essence の 7 の形（探し方を誰が作るか）

決め: 探し方（`class_query`。欠陥の形か、直す所の母数を全部引ける機械の問いと件数）は、人も計画の AI も書かない。仕様駆動の run の中で判定の役 diagnose を 1 回だけ回し、今の本線と同じく判定の役が単位ごとに作る（6.2 の `spec-diagnose`）。

訳:

- 持ち主の決めの範囲: 表は 4 つの欄だけ（`spec-driven-shape`）。探し方を表に書かせると欄が増える。設計書に書かせると、機械が Markdown の文から問いを読み分けることになり、yes/no で確かめられない（憲法の 6）。
- 計画の AI は書けない: 計画の行（`plan[]`）に探し方の欄は無く、足すと今の本線の計画の形が変わる。修正の部品の数え直し（`workflows/fix/src/board.py` の `closure_reply`）は判定の単位の `class_query` を読む。
- 判定の役なら今のまま当たる: 探し方の受け付け（判定の役が探し方に添えた例の行〔当たるべき行と外れるべき行〕を、作業ツリーを固めた版〔`review_rev`〕で探し方を走らせて照らす。`workflows/diagnose/src/judge.py`）も、修正の部品の数え直しも、今の本線と同じコードが同じ形で読む。新しい役も新しい照らしも要らない。
- 足す物だけの直し（新しいファイルを作るだけで、前の形が無い単位）は、今の本線と同じく判定の役が例を出せない訳（`examples_unavailable`）を書き、数え直しはその単位を飛ばす（`closure_reply` は `class_query.how` の無い単位を数えない）。仕様駆動の道で数え直しが弱まるのではなく、今の本線と同じ当たり方になる。
- 判定の役の費用: 本物の単独の run で測った（2.5。11 分 20 秒・$3.18）。

試しで見えた弱みと、その手当て:

- 2.5 の判定の役の試しでは、受け入れの行から作った単位の探し方が、表の行そのもの（`- key: a1`）を表のファイルで数える形になった。数え直しは、修正の後に同じ探し方で件数を数え直し、直す所が減ったかで単位が閉じたか（直し終えたか）を見る。修正は表のファイルを変えないので、修正がうまくいっても件数は修正の前と同じで、数え直しは「閉じていない」と出る見込み。つまりこの探し方では、数え直しが直したかどうかを見分けられない。今の本線の依頼は対象の外のファイルか、`where` がコードを指す行なので、この形は起きにくい。仕様駆動の道では依頼の出どころ（表と設計書）が対象の作業ツリーの中に在るので起きる。
- 手当て: 判定の役に入力 `request_files`（`json: 依頼そのものを書いたファイルのパスの配列（対象の根から）。探し方の paths がこれらだけを指す単位は受け付けが拒む。空の配列は照らさない`。既定 `[]`）を足し、判定の受け付け（`workflows/diagnose/src/judge.py` の探し方の照らし）に yes/no を 1 つ足す: 探し方の `paths` がどれも `request_files` の中なら拒んで出し直させる。数えるのは直す所で、依頼の文ではない。前の形が無い単位（足すだけの単位）は、今どおり例を出せない訳 `examples_unavailable` を書く道に寄る。既定の空の配列では今の本線の振る舞いは変わらない（変更の種類は `workflows/AGENTS.md` の P〔入力を足す〕と A〔受け付けに確かめを足す〕）。仕様駆動の run では block の形 entry が表と設計書のパスを渡す（6.2）。
- 判定の役の問いと目的の外の行は、形 check の 1 と 7 で止めて人に返す（6.4）。2.5 の試しでは両方が出たので、この見本の仕様はそのまま工場に入れると止まる。会話の中で判定の役も単独で回しておけば、工場の run で止まる前に直せる（必ず回す 5 つには入れない。持ち主の決めの 5 つを変えないため。2.5 の使い方の 2 で任意に回す）。

## 10 決めた事（持ち主と工場窓口への問いの答え）

工場窓口の答え（2026-10-21、受付 20261020-224412-ca616a）で決まった事:

1. 表の書式: 持ち主の決め `spec-driven-shape` どおり YAML のまま。前の版のこの章は「run の中の script は標準ライブラリだけで書く決まり（E3）なので YAML が読めない」として JSON を勧めたが、読み違いだった。E3 は外のパッケージを使ってよいと書いており（持ち主の決め `outside-packages-ok`）、縛っているのは E3 の 1 文と試験の `HEADER` だけ。読む所は 6.7。`docs/owner-decisions.md` は前の決めのまま。
2. block の形: block は AI を持たず、本線が判定の役と計画の部品を 1 回ずつ include する（6.1）。訳: [README.md](README.md) の 7.1 の 6（graph は AI を持たない）と憲法の 3（block はほかの block を名指さない）にそろえる。頼みの「block の中で計画の AI を回す」は書き方の誤り。

持ち主の答え（2026-10-21、工場窓口が聞いた。持ち主の決め `spec-driven-shape`）で決まった事:

3. 審査の記録を本物の run の記録と照らす（前の版で並べた案 A。照らさない案 B は採らない）。持ち主の言葉は「まあ記録しておいて特に損はない感じかな」。形は 2.6 の 2: 起動の殻が `reviews` の run の記録を読んで a〜e を照らし、結果をファイルにして env で run に渡す。照らせなければ AI を起こさずに止まる。
4. 判定と計画の往復に人を混ぜる: 持ち主の言葉「１と２を飛ばすんじゃなくて、１と２に人を混ぜる」「いや１と２のサイクルの中にはいればいいからどこでもいいと思うよ」（1 は判定、2 は計画と計画の審査の往復）。人がその繰り返しの中に入っていれば、どの段を会話で回し、どの段を工場で回すかは問わない。工場の中で同じ事を 2 度回さない。この設計の形（計画と計画の審査の往復は会話の中、判定の役 diagnose は工場の中で 1 回。6 章）は、これに当たる。

## 未確認の一覧

- EARS の元の論文（Mavin ほか、RE'09）を読んでいない。EARS の型は著者のページから引いたので、論文の型と同じかは確かめていない（1.1）。
- `judge` を飛ばした時に、その後ろの node（`structure-in`・`design-in` のように `trigger_rule: none_failed_min_one_success` と `when:` を持つ物を含む）が全部飛ぶか（6.2 の変える node の 3）。実装の PR で、仕様駆動の筋書きの dry-run の trace で確かめる。
- 判定の役の入力 `request_files` の照らし（9 章）を足した後に、足すだけの単位（直す前の形が無く、新しく足すだけの単位。9 章）で判定の役が `examples_unavailable` の道に寄るか、出し直しを繰り返すか。実装の PR の本物の run で見る。
- （6.9 の 5 で決めた）起動の殻が照らした結果のファイルの形と env の名（2.6 の 2）。
- 実装の PR で決める事（PR #809 のレビューの「後でよい物」）:
  - （6.9 の 4 で決めた）2.6 の 2 の d の比べ方: 前の版のこの行は「Archon は `metadata.inputs` に名指さなかった入力の既定値も詰めて残す」と書いたが、止めた Archon の源で確かめると、既定値を詰めて残すのは `workflow:` で起こした子の run だけで、直に起こした run は名指した入力だけを残す（6.9 の 4）。比べる鍵の範囲（組んだ鍵だけか、既定も含めるか）・`proposal_file` の一時のパス（中身の sha256 で比べる）・表と設計書のパスと `entry` の字を対象の根からの相対で組むこと・「表から `reviews` を除いた字」の作り方と、会話の AI が同じ字を組む手段（`lib/spectable.py` を呼ぶ命令を工場の側に置くか）を決める。
  - 9 章の `request_files` の照らしで、`class_query.how.paths`（git の pathspec。ディレクトリ・glob・絶対パスも来る）をどう正規化して比べるか。`paths` が空（根の全部を探す）の単位は、「`paths` がどれも `request_files` の中」には当たらないとして拒まない。
  - 7 章の `routes: plan` でも、テストの実行器が無い run では TDD の loop が回らず（`tdd.py` の `NO_SUITE`）、設計書の「TDD で直す所」が黙って direct になりうる。形 check の 6 で止めるか、報告で人に見せるか。
  - （6.9 の 6 で足した）6.5 に、殻（`bin/works-factory`）が `spec_table` も `table` も無い起動で審査の記録を読まず、uv も起こさず、振る舞いが変わらないことを縛る試験を `tests/bin/` に 1 つ足す。
  - （2 本目で書いた）`bin/AGENTS.md` の E15 は「殻は `--input test_cmd=` を照らさない」と書き、#678 で入力の照らしを殻から本線へ移した。殻が `--input spec_table=`・`--input table=` を読んで照らすのはこの向きの外しなので、E15 の文に外しを書く（持ち主の決め `spec-driven-shape` に殻で照らすと書いてあるので、E10 は満たしている）。
  - （2 本目で足した）新しい block を `docs/layers.json` の block の `names` に足す。
  - 報告の名の表 `workflows/line/src/nodenames.json` に `spec-` の 3 つの node の名を足し、`collect` が「`spec-` の 3 つが在ればそちらを読む」とした所と合わせる。
  - （6.9 の 7 で決めた）block `works-factory-spec-driven` の standalone の筋書きで、照らしが通る道も 1 本見せるか（筋書きは script の node を stub にできる。[archon.md](archon.md) の U3）。見せないなら、照らしが通る道は block の試験（`tests/blocks/spec_driven/`）だけが照らす。
- 計画の部品の指示に足す `routes` の段落（7 章）で、計画の AI が「TDD で直す所」を行に正しく写すか。実装の後の本物の run（進め方の 7）で見る。
- 2.5 の 2 周目（指摘を受けて直した版で回し直す）と、工場の run の入口の照らしの本物の通し。
