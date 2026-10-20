# 設計書（下書き）: spec-driven（仕様駆動の道）

- 何の話か: 人と固めた仕様を渡して実装させる別の graph（仕様駆動の道。issue #802）の設計書の下書き。今は issue の「進め方」の 1 と 2 を書く: 世の中の仕様駆動の 5 つの形を一次の出典で読み、項目ごとに採る・採らないを決め（1 章）、仕様に入れる物（2 章）を、持ち主の答え（3 章）に合わせて書いた。graph の node の並び・port・試験は進め方の 6 で書き足す。
- 決めたこと: 仕様は #765 の組み直しの設計書くらいの粒度で、設計書（Markdown）と機械が確かめる表（YAML。目的・受け入れの条件・試験のコマンド・触らない物の 4 つだけ）の 2 つにする。ファイルごとの行は仕様に書かず、run の中で計画の AI が 1 回だけ起こす。計画と計画の審査の往復は、仕様を固める会話の中で部品を単独で必ず回してし、その記録を表に添える。run の入口で機械が形と記録を yes/no で確かめ、欠ければ AI を起こさずに止まる。直し 1 件ごとの差分の仕様（OpenSpec の ADDED/MODIFIED/REMOVED）は採らない。
- 持ち主に求めること: なし。3 つの問いの答えは 3 章と持ち主の決め `spec-driven-shape`（`docs/owner-decisions.md`）に入れた。
- 読む人: 持ち主と、進め方の 3〜6 を進める設計と実装の役。

この文書の語は [README.md](README.md) の頭の物を使う。ほかに:

- 仕様駆動の道: 人と固めた仕様を入力にして、判定と計画の往復を通らずに修正へ進む graph。名は `works-factory-spec-driven`（フォルダ `workflows/spec-driven/`。5 章の 1）。計画と計画の審査の往復は、run の前の仕様を固める会話の中でする。
- 人の仕様: 持ち主（か利用者）が AI と会話で固め、仕様駆動の道に渡す物。設計書と機械が確かめる表の 2 つ（2 章）。
- 仕様を固める会話（壁打ち）: 人と会話の AI が人の仕様を固める会話。会話の AI が工場の部品を単独の run で呼んで仕様を審査させる（2.3）。
- 計画の行: 計画の部品 `workflows/plan/` の修正案の役が返す `plan[]` の項目（`workflows/plan/works-factory-plan.yaml` の `output_format`）。ファイルの行はその中の `files[]`（`path`・`op`・`responsibility`・`symbols`・`home`・`considered`）。
- 単位: 判定が出す直す単位（根本の欠陥 1 つ分）。計画の行は `unit_keys` で単位を指す。
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

- 計画の行（`workflows/plan/works-factory-plan.yaml` の `&plan_reply`）は、run の中で計画の AI が設計書から 1 回だけ起こす（2.4）。形は今の計画の行のままなので、修正の部品・試験の段・レビューは今のまま読む。計画の AI が自分で書く欄（`approach`・`shrink_first`・`narrows`・`tests`・`allowed_paths` など）を設計書と表からどう埋めるかは、進め方の 3〜4 で決める。例: `out_of_scope` は表の物を写し、`allowed_paths` は起こしたファイルの行のパスから作れる見込み。
- 仕様の部品 `workflows/spec/`（名 `works-factory-spec`）は、判定の中で依頼から要件と受け入れの試験を書かせる別の物で、この道ではない。受け入れの条件を Given/When/Then で書く所は同じ向き。
- 持ち主の決め `three-tiers` の「計画の壁打ち（plan と plan-review の往復）はどの段でも省かない」は、この道でも省かない。壁打ちを run の前の、仕様を固める会話の中で部品を単独で回してする（持ち主の決め `spec-driven-shape`）。

## 2 仕様に入れる物

### 2.1 全体

仕様は 2 つのファイルにする（持ち主の決め `spec-driven-shape`）。

- 設計書（Markdown）: 何のために・どの部品をどう変えるか・振る舞い・決めた事を文で書く。書き方は #765 の組み直しの設計書と同じ（2.2）。
- 機械が確かめる表（YAML 1 本。以下「表」）: 目的・受け入れの条件・試験のコマンド・触らない物の 4 つだけを書く。schema で縛る（2.3）。

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

形（欄の名は仮。進め方の 6 で schema にする）:

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
    spec_sha256: <審査した版の設計書と表の 4 つの sha256>
    findings:                      # 最後に回した版で残った指摘だけ
      - key: <部品が付けた指摘の名>
        text: 指摘の 1 行
        handling: accepted
        owner_words: 持ち主が受け入れた言葉
```

`design` と `reviews` は仕様の中身でなく、表 1 本で run を回すための運ぶ欄。

仕様を固める会話（壁打ち）の中で、会話の AI が工場に入れる前に部品を単独で必ず回す（持ち主の決め `spec-driven-shape`）:

- 必ず回す 5 つ: 計画の審査（`works-factory-plan-review`。8 つの観点。同じ処理を 2 か所に書く写しも見る）・独立設計（`works-factory-independent-design`。目的だけから別の役が設計を作り、設計書と突き合わせて抜けや思い込みを探す）・前提の実測（`works-factory-premises`）・前の決めの確かめ（`works-factory-prior-decisions`）・世界の解（`works-factory-world`。同じ類の問題を世の中がどう解いているかを一次の出典で調べる。持ち主の決め `step-up`・keep-essence の 12）。
- 指摘を受けて仕様を直したら、直した版で回し直す。直して消えた指摘は記録に書かない。最後の版で残った指摘は、持ち主が明示で受け入れた物だけを、受け入れた言葉つきで残してよい。それ以外が残っていれば工場に入れない。
- 部品ごとの呼び方（`bin/works-factory workflow run <部品の graph> --cwd <対象> --input <名>=<値>`）・1 回の時間と費用・部品の指摘を `findings` に写す形・部品を本線の外から呼んで詰まった所の記録は、進め方の 6 で決める（issue #802 のコメント）。

run の入口で機械が確かめる事（どれも yes/no。どれかが欠ければ AI を起こさずに止まり、欠けた物を名指して人に返す）:

1. 表が schema に合う（必須の欄が在る・`acceptance` が 1 件以上で `when` と `then` が空でない・`handling` が `accepted` で `owner_words` が空でない）。
2. `design` の設計書が対象に在る。
3. 設計書の見出しに表の 4 つの名が無い。
4. `reviews` に必ず回す 5 つの部品が 1 つずつ在る。
5. どの `reviews` の `spec_sha256` も、今の設計書と表の 4 つから計算した値と同じ（審査した版と渡した版が同じ）。

### 2.4 run の中の流れ（案）

1. 入口の機械の確かめ（2.3）。
2. 計画の AI（`workflows/plan/` の修正案の役）を 1 回だけ回し、設計書と表から計画の行（ファイルの行を含む）を起こす。設計書の「TDD で直す所」に当たる行の `route` を `tdd`、ほかを `direct` にする。計画の審査の往復は回さない。
3. 機械による形の確かめ（今の計画の受け付けの照らし）と、仕様とリポジトリの食い違いの照らし。例: ファイルの行の `op` が `modify`・`delete` ならパスが作業ツリーに在り、`create` なら無い（`rename` は `from` が在り `path` が無い）。計画の AI が設計書とリポジトリの食い違いを見つけた時も、仕様を書き換えずに止まって人に返す。人が仕様を直したら、新しい run として最初から回す。
4. 修正（`workflows/fix/`）・試験の段・レビュー・報告は今の部品のまま。ファイルの置き場の穴は、run の後のレビュー（最小性・全体の整合を見る役）で拾う。

node の並び・port・試験は進め方の 6 で、README の 6 章の型（node ごとの設計シート）に合わせて書く。

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
3. 本当に要るか: 人と固め終えた仕様を渡しても、今は判定と計画の往復を通り直す。作り直しの前の本物の run の 1 本（run の id df5e111f。90 分・$24.56）では、計画の審査 $8.81・計画 $4.12・判定 $3.10 で、合わせて約 $16・約 40 分がこの段だった（issue #802）。新しい部品は作らず、今の部品をつなぎ直す graph 1 本と、入口の確かめを足すだけにする。keep-essence の 12 の仕組み（[README.md](README.md) の 10 章）との当たり:
   - 1〜6・8・10・11: 修正・試験の段・merge・報告を今のまま通すので守られる。
   - 9（独立設計と R1〜R4）: 独立設計は仕様を固める会話の中で必ず回し、入口で回した事を確かめる。R1〜R4 は run の後のレビューのまま。
   - 12（世界の解）: 仕様を固める会話の中で必ず回し、入口で回した事を確かめる（2.3）。
   - 7（class_query の数え直し）: 今の本線では探し方を作るのは判定の中の diagnose で、この道は判定を通らない。それでも保つ（5 章の 6）。探し方を誰が作るかの形は進め方の 6 で決める。

## 5 自分で決めた事

1. 置き場と名: issue の案の名 `works-factory-spec` と設計書 `docs/design/spec.md` は、判定の中の仕様の部品（`workflows/spec/`）が既に使っている。E9 で同じ名は置けないので、この道は `spec-driven` の名で書いた（持ち主の決め `spec-driven-shape` がこの名を採った）。
2. 表に運ぶ欄 `design`・`reviews` を置き、run の入力を表 1 本にした。訳: issue #802 の受け入れ「仕様のファイル 1 本と対象のリポジトリだけで回せる」を保ち、審査の記録を版ごと仕様に結べる。
3. 設計書の「何のために」は「背景」（困りごと）として書き、目的の文は表だけに置いた。訳: 持ち主の決めの「設計書にこの 4 つを書かない」と、設計書が何のためにを持つことを両立させるため。
4. 審査の記録は、最後に回した版で残った指摘だけを書き、版を `spec_sha256` で結ぶ。訳: 「指摘が残っている仕様は工場に入れない」を機械が yes/no で確かめられる形にするため。直した指摘を全部書かせると、直したかを機械が確かめられない。
5. TDD の印は設計書の「TDD で直す所」に書き、計画の AI が `route` に写す（1.3）。
6. keep-essence の 7（class_query の数え直し。欠陥ごとの探し方〔grep の型と対象のパス〕で、修正の前と後の件数を機械が数え直す。数え直すのは修正の部品が使う `lib/recount.py`）は、この道でも保つ。工場窓口の答え（2026-10-21、受付 20261020-201750-a1096f）。訳: [README.md](README.md) の 10 章の 12 の仕組みは、作り直しで守ると決めた物で、新しい道で 1 つだけ落とす訳が無い（元と同じにそろえる）。12 の仕組みのそれぞれが守りとして名指す試験が木に在るかは、`tests/layers/test_keep_essence.py` が確かめる。この道は判定の中の diagnose を通らないので、探し方を、仕様の設計書に人と会話の AI が書くか、run の中で計画を書く AI が設計書から起こすかの形は、進め方の 6 で決める。前の版のこの文書は「落ちる」と書いていた。
7. 世界の解を、会話の中で必ず回す部品に入れた（2.3）。前の版のこの文書と持ち主の決め `spec-driven-shape` の最初の行は「要る時だけ」にしていた。この語は工場窓口が頼みの文に書いた物で、持ち主の言葉ではない。PR #807 のレビュー（2026-10-21）が前の決め `step-up` との食い違いを挙げ、工場窓口の答えで `step-up` と keep-essence の 12 にそろえた（決めの直した記録は `docs/owner-decisions.md` の `spec-driven-shape`）。

## 未確認の一覧

- EARS の元の論文（1.1）。
- 計画の AI が自分で書く欄（1.4 の 1 つ目）を、設計書と表からどう埋めるか。進め方の 3〜4。
- 部品の指摘を `reviews[].findings` に写す形と、`spec_sha256` を計算する範囲の細目。進め方の 6。
- keep-essence の 7 の探し方を誰が作るか（5 章の 6）。進め方の 6。
