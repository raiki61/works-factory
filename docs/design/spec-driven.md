# 設計書（下書き）: spec-driven（仕様駆動の道）

- 何の話か: 人と固めた仕様のファイル 1 本を渡して実装させる別の graph（仕様駆動の道。issue #802）の設計書の下書き。今は issue の「進め方」の 1 だけを書く: 世の中の仕様駆動の 5 つの形を一次の出典で読み、項目ごとに採る・採らないを決め（1 章）、そこから仕様に入れる項目の案を出す（2 章）。graph の node の並び・port・試験は進め方の 6 で書き足す。
- 決めたこと: 仕様のファイルの行は計画の `files` の形（#568 で入った物）にそろえる。受け入れの条件は条件と振る舞いを欄に分けて書く。試験のコマンドは 1 本だけ書く。触らない物は計画の `out_of_scope` の形。あいまいな点は仕様に残さず、壁打ちで決めた事を仕様の中に記録する。実装の前の照らしは、AI を起こさない形の検査と、計画の審査の部品の 2 段にする。直し 1 件ごとの差分の仕様（OpenSpec の ADDED/MODIFIED/REMOVED）は採らない。
- 持ち主に求めること: 3 章の問い 3 つ（受け入れの条件の書き方・仕様のファイルの形・ファイルの行の必須の欄）を選ぶ。どれも勧める案を先頭に置いた。
- 読む人: 持ち主（形を選ぶ）と、進め方の 2〜6 を進める設計と実装の役。

この文書の語は [README.md](README.md) の頭の物を使う。ほかに:

- 仕様駆動の道: 人と固めた仕様を入力にして、判定と計画の往復を通らずに修正へ進む graph。名は `works-factory-spec-driven`（フォルダ `workflows/spec-driven/`）を仮に置く（4 章の 1）。
- 人の仕様: 持ち主（か利用者）が AI と会話で固め、仕様駆動の道に渡すファイル 1 本。
- 計画の行: 計画の部品 `workflows/plan/` の修正案の役が返す `plan[]` の項目（`workflows/plan/works-factory-plan.yaml` の `output_format`）。ファイルの行はその中の `files[]`（`path`・`op`・`responsibility`・`symbols`・`home`・`considered`）。
- 単位: 判定が出す直す単位（根本の欠陥 1 つ分）。計画の行は `unit_keys` で単位を指す。人の仕様では、人が分けた直しのまとまり 1 つを単位と呼ぶ。
- 候補の 5 つ: GitHub Spec Kit・OpenSpec・Kiro（AWS の IDE）の EARS 記法・superpowers の writing-plans・BMAD-METHOD。
- 判定: 本線（メイングラフ `works-factory-line`）の頭の段。依頼を直す単位に割り、決まっていない点を人に問い返す（graph `works-factory-judge`）。
- 憲法の 6・E9〜E11: 根の `AGENTS.md` の決まり。憲法の 6 は「機械の検査は yes/no の形の決まりだけにする」。E9 は「graph の名は `works-factory-<フォルダの名>`」、E10 は「新しい置き場や仕組みは、先に持ち主の決めを `docs/owner-decisions.md` に書いてから足す」、E11 は「仕組みを足す前に、Archon が持つか・ASF が持つか・本当に要るかの 3 つを確かめる」。

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

| 項目 | 決め | 元にした形 |
| --- | --- | --- |
| 目的 | 採る | writing-plans・OpenSpec |
| ファイルの行 | 採る | 工場の計画（#568） |
| 受け入れの条件 | 採る | G/W/T と EARS を欄に |
| 試験のコマンド | 採る | 工場の `test_cmd` |
| 触らない物 | 採る | 工場の計画・BMAD |
| あいまいな点 | 記録だけ採る | Spec Kit の Clarifications |
| 1 問ずつ聞く | 採らない | ― |
| 実装の前の照らし | 採る | OpenSpec・Spec Kit・工場 |
| 差分の仕様 | 採らない | ― |
| TDD の印 | 採る | 工場の `route` |
| 段ごとの期待の出力 | 採らない | ― |
| 要件の両向きの追跡 | 今は採らない | ― |

訳:

- 目的: 5 つのうち 4 つが 1〜2 文の目的を頭に置く。工場の独立設計と世界の解が `purpose` の 1 文で回るので、仕様の目的をそのまま渡せる（壁打ちの部品を単独で呼ぶ時の入力にもなる。1.5）。
- ファイルの行: 修正の部品が計画と仕様を同じに読めることが要る（issue の本文）。世の中の形は writing-plans と BMAD の本流が「パス・作る/直す・受け持ち」まで、Spec Kit と Kiro は作業の文の中、OpenSpec は自由な文で、工場の形（#568 で業界のファイル構成に置き換えた物）がいちばん欄が多い。新しい形を作らず計画の `files[]` をそのまま使う。人に全部の欄を書かせるかは問い 3（3 章）。
- 受け入れの条件: 4 つの形はどれも「前提・出来事 → 振る舞い」の 2〜3 つの部分を持ち（G/W/T・WHEN/THEN・EARS の WHEN/SHALL）、1 件を 1 本の試験に直せると言う。違いは英語のかぎの語を文の中に書くか（EARS・OpenSpec）、欄に分けるか。人の仕様は日本語で書くので、英語のかぎの語で文を縛る形は合わない。欄に分ければ、空でないかを機械が yes/no で確かめられる（憲法の 6）。形の選びは問い 1。
- 試験のコマンド: 仕様の中に書く形を持つのは writing-plans（段ごと）と BMAD（`Verification`）だけ。工場は既に line の `test_cmd` 1 行で受け、試験の段が赤と緑を事実で照らすので、仕様にも 1 行だけ持たせて試験の段へ渡す。
- 触らない物: 書く形を持つのは BMAD（Non-Goals・Never）と OpenSpec（任意）。工場の計画は `out_of_scope`（glob と訳）を持ち、修正の部品が範囲の外を書く前に止まるので、その形で持つ。
- あいまいな点: 持ち主は、仕様は人と壁打ちして固めてから入れると決め、問いを 1 つずつ聞き続ける進め方を好まない（issue #802 の本文）。そこで、固める話し合いの進め方は工場で縛らず（Spec Kit の 1 問ずつの `clarify` も採らない）、渡された仕様に決まっていない印（「TBD」など）を残さない（writing-plans・OpenSpec の「resolve it now」）。話し合いで決めた事は、Spec Kit の `## Clarifications` と同じく問いと答えの組で仕様の中に残す（2 章の `decisions`）。後で人が「なぜこう決めたか」を引け、issue のコメントの「部品が出した指摘のうち、仕様に入れた物と入れなかった物の記録」もここに置ける。
- 実装の前の照らし: 世の中は形の照らし（OpenSpec の `validate`）と中身の照らし（Spec Kit の `analyze`・Kiro・BMAD の readiness）を分けて持つ。工場もこの 2 段にする。1 段目は AI を起こさない schema の検査で、崩れていれば止める（issue の受け入れ）。2 段目は計画の審査の部品を人の仕様に当てる。Spec Kit の `analyze` は助言だけで実装を止めないが、工場は人の仕様を黙って書き換えないと決めている（issue の案の 2）ので、食い違いが出たら止めて人に返す（BMAD の FAIL と同じ向き）。
- 差分の仕様: OpenSpec の形は、対象のリポジトリに本体の仕様の置き場（`openspec/specs/`）が在り、直しのたびに合わせ込むことが前提。工場はどの対象にも本体の仕様を持たず、人の仕様は 1 回の run の入力で終わる。作る/直す/消すはファイルの行の `op` が持つ。差分の仕様を入れるには、対象に仕様の置き場を足す新しい仕組みが要り（E10・E11）、5 つのうち持つのは 1 つだけで、今の困りごと（判定と計画の往復を通り直す）を解かない。
- TDD の印: 既定は direct、人が危ない行にだけ TDD を書く形は issue の案の 3 で決めてある。Kiro の任意の印と向きは逆（Kiro は試験を任意に落とす。工場は TDD を名指して足す）。字は計画の行の `route`（`tdd`・`direct`）にそろえ、単位ごとに書く。
- 段ごとの期待の出力: writing-plans の「コマンドと期待の出力」は、人が先に出力を書く形。工場は試験の段と TDD の役が赤と緑を実行の事実で照らすので、人に出力を書かせない。
- 要件の両向きの追跡: Spec Kit の網羅の穴と BMAD の「orphans in both directions」は、受け入れの条件とファイルの行を結ぶ欄（Kiro の「_Requirements: 5.1, 5.2_」）があって初めて機械で照らせる。計画の `files[]` にその欄は無く、足すと計画と仕様の形がずれる。2 段目の計画の審査が穴を挙げるので、今は足さない。

### 1.4 工場の今の形との合わせ

- 計画の行（`workflows/plan/works-factory-plan.yaml` の `&plan_reply`）は、人の仕様にそのまま要る欄（`files`・`route`・`out_of_scope`）と、計画の役が自分で書く欄（`approach`・`shrink_first`・`narrows`・`tests`・`rewrite_tests`・`refactor`・`allowed_paths`・`structure`・`depends_on`）に分かれる。後の物を人の仕様からどう作るか（機械が作るか、空で渡せるか）は進め方の 3〜4 で決める。例: `allowed_paths` はファイルの行のパスから機械が作れる見込み。
- 修正の部品は計画の `files[]` を指示に表で貼る（`lib/planbrief.py` の `_files_table`）。`home` と `considered` が無い行は空の欄として貼るので、人の仕様が 3 つの欄だけでも修正の部品は読める（問い 3 の勧める案の裏づけ）。必須の照らし（`lib/planmarks.py` の `FILES_SCHEMA`）は計画の役の返答に当てる物で、人の仕様には別の schema を当てる。
- 仕様の部品 `workflows/spec/`（名 `works-factory-spec`）は、判定の中で依頼から要件と受け入れの試験を書かせる別の物で、この道ではない。受け入れの条件を Given/When/Then で書く所は同じ向き。
- 持ち主の決め `three-tiers` の「計画の壁打ち（plan と plan-review の往復）はどの段でも省かない」は line の段の決めで、この道は壁打ちを人との会話で済ませてから入る。この道が計画の往復を通らない事は、進め方の 2 で持ち主の決めとして書く。

### 1.5 仕様の下書きを叩く時に使う部品

issue #802 のコメントの案では、人との話し合いの中で会話の AI が工場の部品を単独の run で呼び、返りから仕様の下書きと、決めが要る点ごとの選択肢（勧める案を先頭に）を作って人に出す。使う部品は計画の審査（`proposal` に下書きを渡す）・世界の解（`request`）・独立設計（`purpose` に 2 章の目的の 1 文を渡す）・前提の実測（`request`）・前の決めの確かめ（入力なし）の 5 つ。部品が出した指摘のうち仕様に入れた物と入れなかった物は、2 章の `decisions` に残す。呼び方・1 回の時間と費用・詰まりの記録は進め方の 6 で決める。

## 2 仕様に入れる項目の案

1 章の採る物を、計画の行の字にそろえて並べた。欄の名は計画の行と同じ物はそのまま、新しい物は英語の短い名を仮に置く。

頭の欄（仕様に 1 つ）:

- `purpose`（必須）: 目的の 1〜2 文。何が困っていて、何が良くなるか。
- `test_cmd`（任意）: 対象の根で走らせるテストのコマンド 1 行。空なら今の line と同じく工場が用意する。
- `out_of_scope`（任意）: `[{glob, why}]`。計画の行と同じ形。触らない物と訳。
- `decisions`（任意）: `[{question, answer, by}]`。壁打ちで決めた事。`by` は決めた人か、指摘を出した部品の名（1.5）。入れなかった指摘は `answer` に入れなかった訳を書く。
- `units`（必須・1 件以上）: 下の単位の配列。

単位の欄（`units[]` の 1 件）:

- `key`（必須）: 単位の名。計画の `unit_keys` に写す。
- `files`（必須・1 件以上）: 計画の行の `files[]` と同じ形。必須の欄は問い 3。
- `acceptance`（必須・1 件以上）: 受け入れの条件。1 件が 1 本の試験になる。形は問い 1（勧める案は `{key, given?, when, then}`）。
- `route`（任意）: `direct`（既定）か `tdd`。`tdd` の単位は、受け入れの条件から先に試験を書いて赤を見る。

機械が AI を起こす前に確かめる事（どれも yes/no）:

- 仕様のファイルが schema に合う（必須の欄が在る・`op` が 4 つの語のどれか・`route` が 2 つの語のどれか）。
- 決まっていない印を残していない（何を印と見るかは進め方の 6 で決める）。
- `files[].path` が、`op` が `modify`・`delete` なら作業ツリーに在り、`create` なら無い（`rename` は `from` が在り `path` が無い）。

入れなかった物: 要件の文（Spec Kit の `FR-001`・OpenSpec の Requirement）は、受け入れの条件と目的で足りると見て別の欄にしない。差分の仕様・段ごとの期待の出力・要件の両向きの追跡は 1.3 の訳で入れない。

## 3 持ち主への問い

### 問い 1: 受け入れの条件の書き方

- A（勧める）: 前提・出来事・振る舞いを欄に分ける（`given` は任意・`when`・`then`）。訳: Spec Kit・BMAD の G/W/T と、OpenSpec の WHEN/THEN、Kiro の EARS の WHEN/SHALL を、どれも同じ欄に写せる。日本語で書けて、空でないかを機械が yes/no で照らせる。
- B: EARS の 1 文（「WHEN ＜条件＞ THE SYSTEM SHALL ＜振る舞い＞」）を字のまま書く。訳: Kiro と同じで 1 文で読めるが、英語のかぎの語で縛るので日本語の仕様と混ざり、形の照らしが字の検査になる。
- C: 試験の名（`path::名`）を人が書く。訳: writing-plans に近く修正の部品が迷わないが、試験の置き場と名を人が先に決める重さが乗る。

### 問い 2: 仕様のファイルの形

- A（勧める）: YAML 1 本を schema で縛る。訳: 工場の port の形は JSON schema（`workflows/*/schemas/`）で、YAML は読み込めばそのまま照らせ、修正の部品へ計画と同じ JSON で渡せる。人は会話の AI と固めるので、YAML を書くのは会話の AI。
- B: 決まった見出しの Markdown（OpenSpec の形）。訳: 人が読みやすいが、見出しを読み取る部品を新しく書くことになる。OpenSpec 自身が「Scenarios MUST use exactly 4 hashtags」と注意するほど、見出しの字の崩れに弱い。
- C: Markdown の本文と、頭の YAML の欄。訳: 欄は照らせて文も書けるが、同じ事を本文と欄の 2 か所に書ける形になり、どちらが正かがずれる。

### 問い 3: ファイルの行の必須の欄

- A（勧める）: `path`・`op`・`responsibility`（rename なら `from`）だけを必須にし、`symbols`・`home`・`considered` は任意。訳: 世の中の形（writing-plans・BMAD の本流）は「パス・作る/直す・受け持ち」まで。修正の部品は欠けた欄を空として読む（1.4）。`home` と `considered`（考えの住処と退けた置き場）は工場が写しを防ぐための欄で、計画の審査が 2 段目で穴を挙げられる。
- B: 計画の行と同じ 6 つの欄を全部必須にする。訳: 計画と仕様が字のまま同じになり照らしは 1 つで済むが、人の仕様の書き手（と会話の AI）に、退けた置き場まで毎回書かせる。

## 4 自分で決めた事

1. 置き場と名: issue の案の名 `works-factory-spec` と設計書 `docs/design/spec.md` は、判定の中の仕様の部品（`workflows/spec/`）が既に使っている。E9（graph の名は `works-factory-<フォルダの名>`）で同じ名は置けないので、この道は `spec-driven` の名で書いた（「仕様駆動」の訳）。名を変えるなら、進め方の 6 でフォルダを作る前に変える。
2. この下書きは 1 章と 2 章だけで、README の 6 章の型（node ごとの設計シート）はまだ当てない。graph の node の並び・port・試験・E11 の 3 つの答えは進め方の 2 と 6 で書き足す。

## 未確認の一覧

- EARS の元の論文（1.1）。
- 計画の役が書く欄（1.4 の 1 つ目）を、人の仕様からどう作るか。進め方の 3〜4。
- 決まっていない印をどの字で見るか（2 章）。進め方の 6。
