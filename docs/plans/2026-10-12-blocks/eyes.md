<!-- coldwrite:skip 計画（issue の本文）。語は works-factory の docs/design.md の「語」の節で定義 -->
# eyes: 独立の目のブロックを中身ごと作る（workflows/eyes/ と、それだけが使う lib/ の部品と試験）

works-factory は、修正依頼を受けて確かめ済みの変更と報告を返す工場を、Archon（AI の工程を YAML で書いて回す道具）の上に作り直しているリポジトリ。前の形の「今の works」（公開リポジトリ raiki61/claude-plugins の `works/`。移す元の版は `pack.json` の `works.commit` = `2aa7c66cf7abe1fe09699ac2942d107123214168`）は、判定・計画・修正・確かめ・報告をつないだ工場で、その能力を 1 つも落とさずに、線（`workflows/line/`。ブロックを並べる 1 本の工程）・8 つのブロック（`workflows/<名>/`）・助け手（`lib/`。Archon を知らない Python）に移している。この issue は、そのうちのブロック `eyes` を、フォルダの中身ごと 1 つの PR で作る。8 つのブロックは別々の run で同時に作られ、線とはブロックの返りの約束（`docs/design.md` の「ブロックの返りの約束」）だけでつながる。元のファイルは `https://raw.githubusercontent.com/raiki61/claude-plugins/2aa7c66cf7abe1fe09699ac2942d107123214168/<パス>` で読める（本文の「元」の欄の `<パス>`）。ASF は Archon の作者が作った、issue から PR までの工程の束（`docs/design.md` の「語」）。

## 読む物

- 根の `AGENTS.md`（リポジトリの形・E8〜E11・E13・E14・E18）、`workflows/AGENTS.md`（E1・E2・E4〜E7・E12・E16・E17）、`lib/AGENTS.md`（E3）、`tests/AGENTS.md`。決まりの番号 E1〜E18 の中身はそれらの文書に在る。
- `docs/design.md`: 「ブロック」の `eyes` の節・「ブロックの返りの約束」の `eyes` の返り・「能力の棚卸し」の `eyes` の行・「受け入れの一覧」・「Archon の分かっていること」と未決 U1〜U8・「作りの順」の段 2 の `eyes` の個別の行。
- `docs/plans/2026-10-12-lib-port.md` の「移し方」1〜6（この issue で `lib/` に持ってくる部品も同じ移し方に従う）。
- `docs/owner-decisions.md` のうち本文が引く決め。
- Archon の振る舞いは、止めた Archon（`docs/design.md` の「語」。ASF と同じ Archon の源（`coleam00/Archon` の commit `d97d00ef15cce4b15d39e42635e4e86996ec1351`。持ち主の決め `archon-same-as-asf`）。版は `factory/pack.json` の 1 か所。自分の工程は家に置かず `--workflow-source` で読ませる）の文書 `packages/docs-web/src/content/docs/`（特に `guides/script-nodes.md`・`guides/authoring-workflows.md`・`reference/cli.md` の dry-run と `workflow test`）で確かめる。ASF の工程は同じ commit の `.archon/workflows/sdlc/`（本文の `W`）。
- ブロックの分（元はどれも 2aa7c66c の `works/` から）:
  - `blk-eyes/blk-eyes.yaml`（目の並びと筋。R4 は R1・R2 の筋の後で `trigger_rule: all_done`）、`blk-eyes/lib/eyes.py`（支度・受け付け・出口。全部が今の works の工程の状態（盤面）の上）、`blk-eyes/commands/*.md`（6 本の包み）、`blk-eyes/fixtures/pass.stubs.yaml`・`give-up.stubs.yaml`。
  - 役の指示書の本文: `.shared/core/gl-prompts/prompts/review-loop/r1.comment_candidates.md`・`r1.minimality.md`・`r2.compare.md`・`r3.coherence.md`・`r4.hidden_scope.md`・`stop.premise_check.md`（graphloops 0.21.0 の写し）と `.shared/core/gl-prompts/prompts/policy-paste.md`・`policy.md`。
  - 役の返りの型・読む物・起こす条件: `.shared/core/graphloops/graphs/review-loop.json` の節 `r1.comment_candidates`・`r1.minimality`・`r2.compare`・`r3.coherence`・`r4.hidden_scope`・`stop.premise_check`・`r4.human_gate`・`p4.assemble`・`p4.scalars`（`schema`・`reads`・`forbidden_inputs`・`cond`）と `.shared/core/graphloops/rules/review-loop.py`（条件 1212-1250 行・`r4_inventory` 2993 行・`R4_ROWS` と `_r4_gate_items` 4103-4111 行・unverifiable の扱い 1958-1975 行）。
  - 役の前付け（模型・effort・道具）: `.shared/core/agents/judge.md`・`inspector.md`・`blind-judge.md`、`.shared/core/stage-models.json` の `blk-eyes/r1-comments`。
  - 直しの後の構造の実測: `blk-structure/blk-structure.yaml` の `stage-b`、`blk-structure/scripts/stage_b.py`・`measure.py`、`darkfactory/lib/line_edge.py` の `after_edge`（456 行から）、`.shared/core/structmark.py`（`write_after`・`after_counts`）・`concepthome.py`（`R1_HEAD`・`R3_HEAD`・`section`）。
  - 守りのパス: `.shared/core/protect.py`・`protected.json`。修正前の関所で人が通した行を R4 に渡す所: `.shared/core/gatemarks.py` の `CARRIED_HEAD`・`CARRIED_ASK`・`carried_section`・`r4_gate_items`。
  - ASF: `W/review/archon-review.yaml`:118-127（読むだけのレンズを並べる）・:207-213（`trigger_rule: all_done` の柵）・:214-236（有効だったレンズの返りが無ければ穴を名指して ready を false にする）・`W/review/commands/review-synthesize.md`。

## 目的と引き継ぐ能力

直しを作った役と別の新しい会話で、読むだけで直しを確かめる。R1 最小性（コメントの削除候補 → 問いの台帳の監査 → 累積差分が最小か）・R2 独立設計との比較（道具は累積差分を読むだけ。独立設計が「問いが立たない」と言えば前提の検算）・R3 全体の整合・R4 見えていない範囲（運用・セキュリティ・データの横断の危うさと消えた能力。人への問い）。R1・R2・R3 を並べ、R4 は R1・R2 の後。直した後の構造の実測と、守りのパスの当たりも出す（`docs/design.md` の eyes の節）。

能力の棚卸しの行（元 2aa7c66c → 新しい置き場）:
- 独立の目 R1〜R4 と前提の検算 — `blk-eyes`（`lib/eyes.py`・`commands/*`）と `gl-prompts/prompts/review-loop/{r1.*,r2.compare,r3.coherence,r4.hidden_scope,stop.premise_check}.md` → `workflows/eyes/` の YAML と `commands/r1-comments.md`・`r1-minimality.md`・`r2-compare.md`・`r3-coherence.md`・`r4-scope.md`・`premise-check.md`
- 直した後の構造の実測 — `blk-structure` の `stage-b`（`scripts/stage_b.py`・`measure.py`）と `line_edge.after_edge` → `workflows/eyes/` の script の節 `structure-after`（計測の中身は`docs/plans/2026-10-12-blocks/prereq.md` の issue が置く `lib/stage_b.py`・`lib/measure.py`、控えは `lib/structmark.py`）
- 守りのパス — `.shared/core/protect.py` → `lib/protect.py`（`docs/plans/2026-10-12-blocks/prereq.md` の issue が置く。merge と共有）を呼ぶ script の節 `protected`
- 規模の数値（旧 `p4.scalars`）と目の入口の数え（旧 `p4.assemble` の 1 周目の分）— `rules/review-loop.py` の builtin → script の節 `prep`（数えは新しく書く `lib/eyeverdict.py`）
- 目の結果を 1 つにまとめる出口（旧 `eyes.collect`・`fallen`・`fell_text`）— `blk-eyes/lib/eyes.py` → 返す節 `verdict`（まとめ方は `lib/eyeverdict.py`）

`lib-port` の「移し方」3 のとおり、ブロックの部品 `blk-eyes/lib/eyes.py` は lib/ に持ってこない。その仕事は次の Archon の機能に置き換わる（今の works の自前の仕組みは持ち込まない）:
- 盤面の錠（`eyes.locked`。fcntl の flock）・目ごとの route/prep/accept の輪 → Archon の `depends_on`・`when:`・`output_format` の照らし・`mutates_checkout: false`・`retry`。錠も記録の帳簿も持たない（持ち主の決め `no-queue`・`simple-software`）。
- 3 回拒まれたら諦める（`GIVE_UP_AFTER = 3`）→ 役の節の `retry: {max_attempts: 2, on_error: all}`（合計 3 回。Archon は `output_format` に合わない返りの節を落とす）。コメントの削除候補だけは諦めても R1 を止めない（`GIVE_UP_SKIPS`）→ `r1-minimality` を `trigger_rule: all_done` にする。
- 作業ツリーの写しを撮って役の後に比べる受け付け（`entry.take` の snapshot）→ 全部の役の節の `mutates_checkout: false`（Archon が作業ツリーを変えた節を落とす。E7）。
- Archon の節が落ちた筋の見分け（`fallen`）→ ASF の `review-complete` と同じ `bash: "true"`・`trigger_rule: all_done` の柵と、返す節が有効だった目の返りの欠けを名指す形。
- 版を git で読めという指示書の文（`GIT_SHOW_SENTENCE`）を、止めた作業ツリーを Read で読めという文（`FROZEN_READ`）に替える読み替え → 役の指示書を書く時に一度だけ替えて書く（目に shell を持たせない）。
- 累積差分を本文に貼らずファイルで渡す（`DIFF_ASK`。run d7b7a712 で 1.1MB の指示書に役が返さなかった）→ `commands/r2-compare.md` の本文に `DIFF_ASK` の文を移し、置き場は `$prep.output.diff_file`。

受け入れの一覧（review-graph の節）のうちこのブロックが持つ物: `r1.comment_candidates`・`r1.minimality`、`r2.compare`（禁: 調査の経緯・判定の一覧）、`r3.coherence`、`r4.hidden_scope`・`r4.human_gate`（問いを返りの `questions` に載せる。関所そのものは線の最後の関所）、`stop.premise_check`、`p4.scalars`・`p4.assemble` の 1 周目の分（R1・R2 の再発火は 1 run 1 周（持ち主の決め `carry`）なので「1 周目は必ず回す」だけが残る）。`r2.design` は plan-review が作り、このブロックは返り `design` を受ける。
keep-essence の 12（今の works の `works/docs/keep-essence.md`）のうち: 独立設計（R2 の比較の側）・守りのファイルで最後の関所（当たりを返す）。持ち主の決め `independent-verdict`（禁じた入力が届かないことを試験で縛る）・`clean-whole`（直した後の実測）・`protected-target`・`small-core`（R2 の作り直しの判定）・`decision-records`（人が通した行を聞き直さない）。

## 作る物

### ブロックのフォルダ `workflows/eyes/`

- `works-factory-eyes.yaml`（工程の名も `works-factory-eyes`。E9）。`interactive:` は書かない（人の関所を持たない。R4 の問いは返りに載り、線の最後の関所が聞く）。節:
  1. `structure-after`（script `structure_after`・`mutates_checkout: false`・`timeout: 1728000000`）: 始めの記録の `base_rev` と今の作業ツリーの差分を `lib/stage_b.py` の `run(root, base)` で測り、計画の指し札 `plan` の欄から `lib/planmarks.py` の `deviations` で外れの訳を引き、`lib/structmark.py` の `write_after(<置き場>, status=…, reason=…, after=…, deviations=…)`（status から後は名前つきでしか受けない） で `$ARTIFACTS_DIR/eyes/` に `structure-after.json` を書く。返り `{after: 指し札, status: ok|failed, reason}`。測れなくても節は落とさず status: failed と理由（今の works の `after_edge` と同じ。線を止めない）。
  2. `prep`（script `prep`・`mutates_checkout: false`・`timeout: 1728000000`・`depends_on: [structure-after]`）: 入力の指し札を開き、目の指示書に差し込む値を返す。返り（`output_format` に書く）: `run_eyes`（boolean。`docs/plans/2026-10-12-blocks/prereq.md` の issue が置く `lib/depth.py` の `skip_reason(doc)`（元 `darkfactory/lib/depth.py:186`。`doc` は `{units: {<unit_id>: 行}}`。入力 `depth` の配列 `{unit_id, depth, why}` を `unit_id` で並べ替えて渡す）が `""` の時 true）・`compare_due`（独立設計が問いは立つと言い、目的の文が在る）・`premise_due`（独立設計が問いは立たないと言った。旧 `r2_premise_invalid`）・`purpose_text`・`design_text`・`premise_invalid_reason`・`diff_file`（fix の返り `diff` の指し札を `boundary.resolve` で開いた絶対パス。写し直さない）・`diff_lines`・`changed_files`・`scalars`（規模の数値の 1 文）・`cwd`・`base_rev`・`review_md`（`boundary.lib_root()/REVIEW.md` のパス）・`policy_path`（方針の文書の置き場。始めの記録の欄 `policy_md`（今の works の `start.schema.json` の欄。始めの記録に在る）を読み、無ければ `""`（方針の文書が無い run と同じ文を役に渡す）。ブロックの入力は足さない）・`after_counts`（`structmark.after_counts(<置き場>)`。無ければ旧 `eyes.NO_AFTER` の文）・`concept_map`（`concepthome.section(cwd)`）・`candidates_file`（`$ARTIFACTS_DIR/eyes/r1-comments.json` の絶対パス）・`judgment_file`・`units_text`・`fixes_text`（`fix_units` の行）・`premises_text`（R2 の頭の「設計の後に分かった前提」の本文: 人の関所の答え・前提のずれの申告の有無（`changed.premise_drift`）・記録の制約（`judgment` の指し札の隣の `premises.json` の `constraints`））・`carried`（修正前の関所で人が通した行。旧 `gatemarks.carried_section` と同じ見出し `CARRIED_HEAD`・頼み `CARRIED_ASK`・行の形）・`r4_context`（波及の一覧と定石の行の置き場）・`green_line`（`green_ok` が false なら「最後のテストの認証が通っていない（赤は最後の関所で人が見る）」、true なら `""`）。eyes が読む緑の認証は入力 `green_ok` だけで、作業ツリーの指紋（`fingerprint`）は受けず、`lib/green_cert.py` も呼ばない（指紋を照らすのは merge）。
  3. `r1-comments`（command `r1-comments`・`context: fresh`・`mutates_checkout: false`・`allowed_tools: [Read, Grep, Glob, WebSearch, WebFetch]`・`model: sonnet`・`effort: medium`・`idle_timeout: 1728000000`・`retry: {max_attempts: 2, on_error: all}`・`when: "$prep.output.run_eyes == true"`）: `output_format` は graph の `r1.comment_candidates` の `schema` を字のまま。旧の役は `pr-review-toolkit:comment-analyzer`（skills required）。Archon の `skills:` で同じ技を名指せるかを源の文書で確かめ、名指せればそうし、名指せなければ PR に書く（役の指示書の本文で comment-analyzer の観点を持つ）。
  3b. `r1-comments-save`（script `save_reply`・`depends_on: [r1-comments]`（既定の `trigger_rule`。r1-comments が返った時だけ走る）・`mutates_checkout: false`・`timeout: 1728000000`・`with: {name: "r1-comments", out: "$r1-comments.output"}`）: 返りを `$ARTIFACTS_DIR/eyes/r1-comments.json` に書く。落ちた節の返りへの `with:` は `if_skipped` を書いても誤りで止まる（止めた Archon の `packages/workflows/src/dag-executor.ts`:519-534）ので、並べた役の返りを後ろで集める時は、返った時だけ走る節がファイルに書き、集める側はそのファイルを読む。
  4. `r1-minimality`（command・`depends_on: [prep, r1-comments-save]`・`trigger_rule: all_done`・`when: "$prep.output.run_eyes == true"`・`with:` は書かない（削除候補は指示書が `$prep.output.candidates_file`（`$ARTIFACTS_DIR/eyes/r1-comments.json` の絶対パス）を Read する。無ければ「削除候補は取れなかった」として進む。旧 `GIVE_UP_SKIPS`）・judge の前付け（`model: opus`・`effort: high`・`allowed_tools: [Read, Grep, Glob, WebSearch, WebFetch]`）・`context: fresh`・`mutates_checkout: false`・`idle_timeout: 1728000000`・`retry` は上と同じ）: `output_format` は graph の `r1.minimality` の `schema`。
  5. `r2-compare`（command・`depends_on: [prep]`・`when: "$prep.output.run_eyes == true && $prep.output.compare_due == true"`・blind-judge の前付け（`model: opus`・`effort: high`）に Read を 1 つだけ足す `allowed_tools: [Read]`・`context: fresh`・`mutates_checkout: false`・`idle_timeout: 1728000000`・`retry`）: `output_format` は graph の `r2.compare` の `schema`。指示書が読む値は `$prep.output.purpose_text`・`design_text`・`premises_text`・`diff_file`・`diff_lines`・`changed_files` の数だけ（下の「禁じた入力」）。
  6. `premise-check`（command・`depends_on: [prep]`・`when: "$prep.output.run_eyes == true && $prep.output.premise_due == true"`・judge の前付け・`context: fresh`・`mutates_checkout: false`・`idle_timeout: 1728000000`・`retry`）: `output_format` は graph の `stop.premise_check` の `schema`。
  7. `r3-coherence`（command・`depends_on: [prep]`・`when: "$prep.output.run_eyes == true"`・inspector の前付け（`model: sonnet`・`effort: medium`・`allowed_tools: [Read, Grep, Glob]`）・`context: fresh`・`mutates_checkout: false`・`idle_timeout: 1728000000`・`retry`）: `output_format` は graph の `r3.coherence` の `schema` に、`concepthome.R3_HEAD` が求める `seen`・`unseen`（文字列の配列）を足した物（旧は schema が `additionalProperties` を閉じていない所に返させていた。足した欄は PR に書く）。
  8. `r4-scope`（command・`depends_on: [prep, r1-minimality, r2-compare, premise-check]`・`trigger_rule: all_done`（旧 `LANE_AFTER`。前の筋が落ちても R4 を飛ばさない）・`when: "$prep.output.run_eyes == true"`・inspector の前付け・`context: fresh`・`mutates_checkout: false`・`idle_timeout: 1728000000`・`retry`）: `output_format` は graph の `r4.hidden_scope` の `schema` に `seen`・`unseen` を足し、旧の post_check `r4_inventory`（`capability_inventory.fired` が true なのに `lost` が無ければ拒む）を JSON Schema の `if`/`then` で書く。Archon の照らしが `if`/`then` を受けないと分かったら、返す節の `verdict` が照らして r4 を `unverifiable`（理由つき）にする。
  - 役の節（3〜8）は全部、今の works の `blk-eyes/blk-eyes.yaml` の同じ役の節から `settingSources: [user]`（対象の CLAUDE.md を読ませない）・`sandbox: {enabled: true, allowUnsandboxedCommands: false}` を写し、`context: fresh` を書く（止めた Archon は節ごとに受ける）。
  8b. 目ごとの型つきの成果物の節 `r1-minimality-verdict`・`r2-compare-verdict`・`premise-check-verdict`・`r3-coherence-verdict`・`r4-scope-verdict`（どれも script `eye_verdict`・`mutates_checkout: false`・`timeout: 1728000000`・`output_type: eye-verdict`・`depends_on: [<目>]`（既定の `trigger_rule`。目が返った時だけ走る）・`with: {eye: "<r1|r2|r3|r4|premise-check>", out: "$<目>.output"}`）: 目の返りの全体を `$ARTIFACTS_DIR/eyes/<eye>.json`（`r1.json`・`r2.json`・`r3.json`・`r4.json`・`premise-check.json`）に書き、型つきの成果物 `eye-verdict` を返す。形は 8 つのブロックで揃えた `{eye, status, reason}`（`eye` は `r1`・`r2`・`r3`・`r4`・`premise-check` のどれか。premise-check の `status` は `verdict` の値 `resolved`・`escalate`）。役の節の返りは役の型のままなので、成果物は役の節に `output_type` を付けず、この小さな script の節が出す（report が `$TYPED_ARTIFACTS_FILE` から include の頭と `loopGroupPath` で引く。E5）。落ちた目は成果物もファイルも出さず、返す節の r1〜r4 が落ちた事を名指す。
  9. `protected`（script `protected`・`mutates_checkout: false`・`timeout: 1728000000`）: `lib/protect.py` の `touched(cwd, base_rev)` で、run の始めの版から今の作業ツリーまでの差分のうち守りの一覧に当たる物を出す。返り `{hits: [パス], lines: [protect.lines の文], broken: ""}`。節は落とさない（落ちると線が先へ進めない）。一覧か git が読めない（`protect.Broken`）時は、確かめられなかった印の 1 行を当たりとして返す `{hits: ["?: 守りのファイルを確かめられなかった（差分が一覧に触れていないとは言えない）: <理由>"], lines: [], broken: "<理由>"}`（黙って空にしない。持ち主の決め `no-silent-loosen`。文は今の works の `darkfactory/lib/line_edge.py`:111・660 の `PROTECTED_UNKNOWN` の向きで、merge の `seal.unknown_row` と同じくパスの欄を `?` にして当たりに数えさせる。頭の字は `lib/eyeverdict.py` の定数 `PROTECTED_UNKNOWN_ROW`）。返りは `$ARTIFACTS_DIR/eyes/protected.json` にも書く。
  10. `eyes-complete`（`bash: "true"`・`timeout: 1728000000`・`mutates_checkout: false`・`depends_on: [r1-comments, r1-comments-save, r1-minimality, r2-compare, premise-check, r3-coherence, r4-scope, r1-minimality-verdict, r2-compare-verdict, premise-check-verdict, r3-coherence-verdict, r4-scope-verdict]`・`trigger_rule: all_done`）: ASF の `review-complete` と同じ柵。落ちた目が在っても出口へ進む。
  11. `verdict`（script `verdict`・返す節・`mutates_checkout: false`・`timeout: 1728000000`・`depends_on: [eyes-complete, prep, structure-after, protected]`・`trigger_rule: all_done`）: どの節にも `with:` で結ばない（落ちた節への結びは誤りで止まる）。`prep`・`structure-after`・`protected` も目と同じく、返った時に `$ARTIFACTS_DIR/eyes/` に書いたファイル（`prep.json`・`structure-after.json`・`protected.json`）を読む。無いファイルは「その節が落ちた」と読み、ok を false にして理由に名指す。目の返りは `$ARTIFACTS_DIR/eyes/<eye>.json` を読む（`prep` が起こすと決めた目にファイルが無ければ、その目の節が落ちた）。`lib/eyeverdict.py` の `collect(...)` で返りを組む。返す節は決して落ちない（落ちると線が先へ進めない）: script の中で全部の例外を捕まえ、`ok: false`・r1〜r4 を `unverifiable`（reason に捕まえた誤りの 1 行）・`questions: []`・`premise_check: null`・`structure_after: null`・`protected_hits` は読めた物か `[]` の、`output_format` に合う返りを出して終了の値 0 で終える（黙って通さない。ok は false）。自分の目の返りをファイルで読むので、型つきの成果物の一覧（`$TYPED_ARTIFACTS_FILE`）は読まない（E5。一覧を読むのは report だけ）。
- `commands/`（役の指示書。元の包み `blk-eyes/commands/<名>.md` の文と、本文 `gl-prompts/prompts/review-loop/<節>.md` を 1 つにし、graphloops の穴 `{{…}}` を Archon の書き方に替える）:
  - `r1-comments.md`（元 `r1-comments.md` + `r1.comment_candidates.md`）・`r1-minimality.md`（元 `r1-minimality.md` + `r1.minimality.md`。頭に `concepthome.R1_HEAD` の文と `$prep.output.after_counts`、続けて `$prep.output.concept_map`・`$prep.output.scalars`・`$prep.output.green_line`、方針の節（元 `policy-paste.md`・`policy.md`。本文を貼らず `$prep.output.policy_path` を Read させる））・`r2-compare.md`（元 `r2-compare.md` + `r2.compare.md`。頭に旧 `eyes.DIFF_ASK`・`PREMISE_ASK`・`LATE_ASK` の文と `$prep.output.premises_text`）・`premise-check.md`（元 `premise-check.md` + `stop.premise_check.md`）・`r3-coherence.md`（元 `r3-coherence.md` + `r3.coherence.md`。頭に `concepthome.R3_HEAD` の文と `after_counts`・`concept_map`・`green_line`・方針の節）・`r4-scope.md`（元 `r4-scope.md` + `r4.hidden_scope.md`。頭に `$prep.output.carried`・`$prep.output.r4_context`・`green_line`・方針の節）。
  - 直す所は次だけ: (1) 旧の包みの「受け付けが拒んだ理由の節が在れば出し直せ」の文は落とす（拒否の文を足して同じ会話で出し直させる口が Archon に無い。出し直しは `retry`。この違いを PR に書く）。(2) `{{loop.diff_file}}`・`{{file:loop.diff_file}}` → `$prep.output.diff_file`、`{{out.p0.purpose.purpose_text}}` → `$prep.output.purpose_text`、`{{out.r2.design.design}}` → `$prep.output.design_text`、`{{inputs.review_md}}` → `$prep.output.review_md`、`{{inputs.cwd}}` → `$prep.output.cwd`、`{{record.base}}` → `$prep.output.base_rev`、`{{loop.changed_files}}` → `$prep.output.changed_files`、`{{record.units}}`・`{{record.questions}}` → `$prep.output.units_text` と `$prep.output.judgment_file`（Read させる）、`{{record.process.fixes}}` → `$prep.output.fixes_text`、`{{out.r1.comment_candidates}}` → `$prep.output.candidates_file`（Read させる。無ければ取れなかったと書く）、`{{record.process.human_items}}` → `$prep.output.carried`、`{{record.process.constraints}}` → `$prep.output.premises_text` の制約の節。前の周の値（`loop.prev_scalars`・`loop.lines_ratio`）は 1 run 1 周なので「前の周は無い」と書く。(3) 版を git で読めという文（旧 `eyes.GIT_SHOW_SENTENCE`）は旧 `eyes.FROZEN_READ` の文に替える。(4) 対象の言語・テストの実行器の名を書かない（E13）。
- `scripts/`（どれも頭は下の「共通の書き方」の形。確かめの中身は lib/ の関数を呼ぶだけ）:
  - `structure_after.py`: `stage_b.run`・`planmarks.deviations`・`structmark.write_after`（`$ARTIFACTS_DIR/eyes/structure-after.json`。`verdict` は在ればこのファイルの指し札を `boundary.pointer` で組んで `structure_after` に入れ、無ければ null）・`boundary.pointer`。
  - `prep.py`（返りを `$ARTIFACTS_DIR/eyes/prep.json` にも書く）: `boundary.resolve`（入力の指し札）・`depth.skip_reason`・`eyeverdict.r2_compare_due`・`eyeverdict.r2_premise_invalid`・`eyeverdict.scalars`・`eyeverdict._human_passed`・`structmark.after_counts`・`concepthome.section`・`design.claims_*` の見出しの定数・`gatemarks.CARRIED_HEAD`・`CARRIED_ASK`。
  - `protected.py`: `protect.touched`・`protect.lines`。`protect.Broken` を捕まえて `eyeverdict.PROTECTED_UNKNOWN_ROW` の行を返す。
  - `verdict.py`: `eyeverdict.collect`・`boundary.returns`。
  - `eye_verdict.py`: 目の返りを `$ARTIFACTS_DIR/eyes/<eye>.json` に書き、`{eye, status, reason}` を組んで `boundary.returns`（欄を写すだけ）。
  - `save_reply.py`: 役の返りを `$ARTIFACTS_DIR/eyes/<name>.json` に書いて `{saved: true}` を返す（r1-comments 用）。
- `fixtures/<筋書き>.stubs.yaml`（Archon の `workflow test`。筋書きは配線だけを確かめる。止めた Archon の dry-run の事実: 人の関所の節は自ら済む・`until_bash` は走らせず輪は済んだと見なす・差し替えは節ごとに 1 つの値・届く `workflow:` の節が `fan_out:` を持つと筋書きが落ちる・`exec-code` の script は空の `ARTIFACTS_DIR`・`TYPED_ARTIFACTS_FILE=''`・`WORKFLOW_ID=dry-run` で走る。だから目の返りのファイルを読む `verdict` の振る舞い（落ちた目・問いの外し）は筋書きでなく下の「試験」の script の起こしで確かめる）:
  - `pass.stubs.yaml`: 目が全部起きる配線。`fixture: {expect: completed, reached: [structure-after, prep, r1-comments, r1-comments-save, r1-minimality, r2-compare, r3-coherence, r4-scope, r1-minimality-verdict, r2-compare-verdict, r3-coherence-verdict, r4-scope-verdict, eyes-complete, protected, verdict]}`。`premise-check` は飛ぶ。返す節の差し替えの `ok` が true（`authoredOutcome: succeeded`）。
  - `redesign.stubs.yaml`: 返す節の差し替えの `ok` が false で、run は completed・`authoredOutcome: failed`（run の終わりと仕事の結末が別の事実であることの配線）。
  - `premise.stubs.yaml`: prep が `premise_due: true`・`compare_due: false`。`reached` に `premise-check`・`premise-check-verdict`、`r2-compare` は飛ぶ。
  - `all-light.stubs.yaml`: prep が `run_eyes: false`。目の役と `<目>-verdict` は全部飛び、`structure-after`・`protected`・`eyes-complete`・`verdict` は走る（`reached`）。
  - `protected-hit.stubs.yaml`: `protected` の差し替えが当たりを返し、`verdict` まで届く（`resolved-text-contains` で `verdict` の解いた文に当たりのパスが在る）。

### lib/ に持ってくる部品（このブロックだけが使う物）

- このブロックだけが使う、今の works から持ってくる部品は無い。`blk-eyes/lib/eyes.py` は全部が盤面か役の起こし方（`rolekit`・`node_marker`・`accept.role_schema`）で、lib-port の「移し方」3（ブロックの部品は持ってこない）に当たる。
- `docs/plans/2026-10-12-blocks/prereq.md` の issue（ブロックの前の共有の部品。本文の「依存」の前に入る物）が lib/ に置く物を読むだけにする（このブロックでは作らない・変えない。下の「依存」）: `protect.py`・`protected.json`・`design.py`・`REVIEW.md`・`stage_b.py`・`measure.py`・`eye.py`・`conceptfence.py`・`depth.py`（`skip_reason` を書き直さずにそのまま呼ぶ）。
- 盤面に届く能力の扱いは、8 つのブロックで同じ 2 つの形だけ: (a) 継ぎ目の直し（持ってきたファイルの中の盤面・Archon・持ってこない部品への 1 つの呼び出しを、引数か lib/ の部品の呼び出しに替える。関数の名とほかの行は変えない。直した行を PR に並べる）、(b) 書き直し（関数の中身がほとんど盤面の読みの時、元の関数の名のまま、値かファイルのパスを引数で受ける形に新しい lib/ のファイルで書き直す。docstring に元の `<パス>:<行>` を書き、試験は元の試験の場合を写す。PR に並べる）。このブロックは (b) だけを使う。
- (b) 書き直しのファイル `lib/eyeverdict.py`（ブロックの名の新しいファイル。Archon を知らない。E3・E18）。関数は元の名のまま（元は 2aa7c66c の `works/` から）:
  - `r2_compare_due(design: dict, purpose_text: str) -> bool`（元 `.shared/core/graphloops/rules/review-loop.py:1228`。1 run 1 周なので再発火は「1 周目は必ず」だけ）・`r2_premise_invalid(design: dict) -> bool`（元 同 :1248。旧は記録の `reviews.R2.status == premise-invalid`、立てたのは独立設計の `question_stands: false`）。`design` が `{"missing": "<理由>"}`（独立設計が無い）の時は両方 false。
  - `scalars(diff_text: str) -> dict`（元 同 :2153 の builtin `scalars`）: 差分から数えられる規模の数値（足した行・消した行・変わったファイルの数）。測れない値は 0 にせず欠けの理由で返す（元と同じ）。
  - `_human_passed(questions: list, answer: dict | None) -> dict`（元 `.shared/core/gatemarks.py:1244`）: 修正前の関所の答えが通す語（`approve`・`continue`。語は `lib/answer.py` から引く）なら、そこで聞いた行のうち `gatemarks.NARROW_HEAD`・`FACE_HEAD` に当たる物を `{(種類, 頭と推しの尾 `gatemarks.PUSH_TAIL` を外した本文): 1}` で返す（元と同じ照らし。1 run 分。`stop`・`reject`・null は空）。
  - `r4_gate_items(r4: dict | None, passed: list) -> list[str]`（元 `.shared/core/gatemarks.py:1266` と `.shared/core/graphloops/rules/review-loop.py:4103-4111` の `R4_ROWS`・`_r4_gate_items`）: 「R4 が BASE から消えたと見た能力: 」+ lost（種類 regression）と「R4 が見た人の方針とのぶつかり: 」+ policy_conflicts（種類 policy）の行から、通した行と種類も頭を除いた本文も同じ物を外す（頭の文は `R4_ROWS` の字のまま。種類が違えば聞き直す）。
  - `fell_text(fell: list, ran: str = "") -> str`（元 `blk-eyes/lib/eyes.py:307`。盤面を読まないので中身はそのまま）。
  - `collect(*, eyes_dir, run_eyes: bool, compare_due: bool, premise_due: bool, design: dict, after_ptr, protected_hits: list, passed: dict) -> dict`（元 `blk-eyes/lib/eyes.py:489` と `fallen` :291）: 目の返りを `eyes_dir/<eye>.json` から読み、約束の欄を組む。目ごとに `{status, reason}`（省いた目は null）。起こすと決めた目のファイルが無い（節が落ちた）時は、その目を `unverifiable` にし、reason を `fell_text` の文で始める（ASF の synthesize と同じく黙って通さない）。独立設計が無い run（`{"missing": …}`）の r2 は `unverifiable`・reason「独立設計が取れなかった: <理由>」（旧 `eyes.collect` の `design.missing` の止め）。独立設計が問いは立たないと言った run は前提の検算の道で、r2 は `unverifiable`・reason「前提不成立: <理由>」、判定は `premise_check` が運ぶ（R2 の作り直しの判定 `redesign-needed` には数えない）。r2 の `unverifiable` は約束の変え（R2 の status に `unverifiable` を足す。前に入る人の直し H8）に依る。`ok` は省いていない目が全部 `pass` で、前提の検算が走っていず、守りのパスを確かめられた（`protected.json` が在り `broken` が空）時だけ true。守りのパスを確かめられない時は `protected_hits` に `PROTECTED_UNKNOWN_ROW` で始まる行を載せ、ok を false にする（r1〜r4 は目の値のまま）。`questions` は `r4_gate_items`。`premise_check` は前提の検算が走った時 `{verdict, reason}`、走らなければ null。
  - reason の頭の 3 つ（「前提不成立: 」「独立設計が取れなかった: 」と `fell_text` の「の筋が落ちた」）は定数 `R2_PREMISE_HEAD`・`R2_MISSING_HEAD`・`FELL_MARK` にする。r2 の `redesign-needed` は比較役が本当に作り直しと言った時だけで、merge はそれだけを人の答えに関わらず置かない（持ち主の決め `small-core`）。`unverifiable` の 3 つの場合は人に回る（merge の約束 H8 と揃う）。

### 試験

- `lib/tests/test_eyeverdict.py`（新しく書く）: `r2_compare_due`・`r2_premise_invalid`（問いが立つ・立たない・`{"missing": …}`・目的の文が空）、`r4_gate_items` と `_human_passed`（元 `works/tests/test_plan_gate.py` の `R4GateCase`（`test_r4_does_not_reask_narrow_the_human_passed`・`test_r4_reasks_other_kind_or_unpassed`）と `test_gate_drafts.py` の `R4PushTailCase`（`test_r4_does_not_reask_when_the_asked_row_had_a_push_tail`）の場を、盤面でなく値で写す。approve・continue・stop・reject・null）、`fell_text`（元 `test_blk_eyes_lanes.py` の文の場合）、`collect`（全部 pass で ok・R2 redesign で ok が false・省いた run で r1〜r4 が null で ok が true・ファイルの無い目が unverifiable で reason の頭・独立設計が無い r2・前提不成立の r2 と premise_check・問いから通した行が外れる）。`lib/` を `sys.path` の後ろに足す形は `tests/AGENTS.md` のとおり。
- `tests/workflows/test_eyes.py`（ブロックの YAML の形。PyYAML で読み、Archon を起こさない）:
  - `test_every_role_node_is_read_only`: 役の節（`command:`）が全部 `mutates_checkout: false` と `context: fresh` を持つ。script と bash の節も `mutates_checkout: false`（E7）。
  - `test_no_eye_has_shell_or_writer_tools`: どの役の `allowed_tools` にも `Bash`・`Write`・`Edit`・`NotebookEdit` が無い。`r2-compare` は `[Read]` だけ。
  - `test_r2_compare_gets_no_forbidden_input`（持ち主の決め `independent-verdict`）: `r2-compare` の節に `with:` が無く、`commands/r2-compare.md` が読む `$<節>.output.<欄>` と `$INPUTS.<名>` が `prep` の `purpose_text`・`design_text`・`premises_text`・`diff_file`・`diff_lines`・`changed_files` だけ（判定の一覧 `units_text`・`judgment_file`・`fixes_text`・`r4_context`・計画・波及は読まない）。
  - `test_r4_waits_for_r1_and_r2_lanes`: `r4-scope` の `depends_on` が `r1-minimality`・`r2-compare`・`premise-check` を含み、`trigger_rule: all_done`。
  - `test_barrier_before_verdict`: `eyes-complete` が全部の目と `r1-comments-save`・`<目>-verdict` に依り `trigger_rule: all_done`。`verdict` の `depends_on` が `eyes-complete`・`prep`・`structure-after`・`protected` だけで `trigger_rule: all_done`、`with:` を持たない（落ちた節への結びは誤りで止まる）。`r1-minimality` にも `with:` が無い。
  - `test_eye_verdict_typed`: `output_type: eye-verdict` を持つ節がちょうど `r1-minimality-verdict`・`r2-compare-verdict`・`premise-check-verdict`・`r3-coherence-verdict`・`r4-scope-verdict` の 5 つで、どれも `output_format` が `{eye, status, reason}`（全部 required）で、`with:` の `eye` の値が順に `r1`・`r2`・`premise-check`・`r3`・`r4`。役の節には `output_type` が無い。
  - `test_frozen_read_in_commands`: どの `commands/*.md` にも `git -C`・`git show`・`git grep` の指示が無く、元の 4 本（r1-comments・r1-minimality・r3-coherence・r4-scope）が旧 `FROZEN_READ` の文を持つ（旧 `FrozenReadCase` の置き換え）。
  - `test_role_schemas_match_graph`: 各役の `output_format` が、元の `review-loop.json` の同じ節の `schema` と同じ（足した `seen`・`unseen` と R4 の `if`/`then` を除く）。元の graph はリポジトリに入れず、試験の中に元のパスと版を書いた期待の表を置く。
  - `test_fixtures_pass_in_archon`: `tests/archon.py` の使い捨ての木で `archon workflow test` を走らせ、`fixtures/` の筋書きが全部通る（Archon の源が無ければ見送る）。
  - `test_returns_contract`: `returns: verdict`・`outcome_field: ok`、返す節の `output_format` の `required` が約束の欄ちょうど・`additionalProperties: false`。
  - `test_retry_gives_three_tries`: 役の節の `retry.max_attempts` が 2（合計 3 回。旧 `GIVE_UP_AFTER`）。
  - `test_role_settings_copied`: 役の節が全部 `settingSources: [user]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false}`・`context: fresh` を持つ。
  - `test_no_workflow_level_composed_keys`: 工程の頭に `interactive`・`worktree`・`container`・`evidence_policy`・`mutates_checkout` が無い（include で差し込まれるブロックでは読み込みの警告つきで落とされる。止めた Archon の `guides/authoring-workflows.md` の「Composed behaviour」）。
  - script の起こしの試験（`scripts/*.py` を一時の `ARTIFACTS_DIR`・`WORKFLOW_ID`・`INPUTS_*` で subprocess で走らせる。Archon は起こさない）: `test_verdict_names_fallen_eye`（`prep` が起こすと決めた `r1` の `r1.json` が無い → r1 が unverifiable・reason が落ちた筋の文・ok が false。旧 `test_blk_eyes_lanes.py` の `FallenLaneCase`）、`test_verdict_drops_passed_questions`（`r4.json` が lost 2 行・policy_conflicts 1 行、入力 `answers` が continue で `plan_questions` に同じ能力の行 1 つ → `questions` が 2 行）、`test_verdict_carries_protected_hits`、`test_protected_broken_is_a_hit`（守りの一覧が壊れた場で `protected.py` が終了の値 0 で `?:` で始まる当たりと `broken` を返し、続く `verdict.py` が ok を false・`protected_hits` にその行）、`test_verdict_never_fails`（`INPUTS_*` が壊れた JSON・目のファイルが JSON でない・`ARTIFACTS_DIR` が無い場で走らせ、終了の値 0 で、`output_format` に合う `ok: false` と理由の JSON が出る）、`test_eye_verdict_writes_file_and_returns_row`、`test_prep_resolves_diff_pointer`（`diff_file` が fix の指し札の先のパスそのもの）、`test_prep_all_light_turns_eyes_off`（`depth` が全部軽量 → `run_eyes: false`）。
- 元の試験の扱い: `works/tests/test_blk_eyes.py`・`test_blk_eyes_lanes.py` は盤面の上の試験なので持ってこない（`SectionShapeCase`・`AnchorCase` は `design.py` の試験で、`docs/plans/2026-10-12-blocks/prereq.md` の issue が持ってくる。`R4AfterR1R2Case`・`FallenLaneCase` の場は上の YAML の形の試験と script の起こしの試験で写す）。`works/tests/test_gate_head.py` の `FinalHeadCase` のうち、守りのパスと目の status から最後の関所の頭の 3 行を組む場（`test_protected_named_in_the_first_line`・`test_unknown_eye_status_opens_when_needed` ほか）は線の最後の関所の物なので、PR の本文に「線へ渡す場」として名を並べる（eyes はその材料の `protected_hits`・r1〜r4・`questions` を返すところまで）。`test_blk_structure.py` の `AfterCase`・`test_concept_change.py`・`test_protect.py` は`docs/plans/2026-10-12-blocks/prereq.md` の issue が持ってくる。持ってこない試験の名と理由を PR に並べる。

## 返りの約束（`docs/design.md`「ブロックの返りの約束」の `eyes` の返りのまま）

- 返す節 `verdict`・`outcome_field: ok`（今の works の `eyes-exit.ok`）
- 入力（`with:`）:
  - `units`・`judgment`・`purpose`・`world` ← `$judge.output.<同じ名>`
  - `plan`・`ripple` ← `$plan.output.<同じ名>`
  - `depth` ← `$redepth.output.depth`（plan の深さを直した後に上げ直した物）
  - `design` ← `$plan-review.output.design`
  - `diff`・`changed` ← `$fix.output.<同じ名>`、`fix_units` ← `$fix.output.units`
  - `green_ok` ← `$test-gate-final.output.ok`
  - 加えて、始めの記録 `start` ← `$start.output.record`（約束の「線の始めの節 start の返り」は「→ 全ブロック」。eyes の入力の一覧には無いので「人が入れる前提の直し」1 に書く）と、既定 `null` の任意の入力 `plan_questions` ← `$plan-review.output.questions`・`answers` ← `{ from: "$gate-before-fix.output", if_skipped: null }`（同 2。線が渡さない間は R4 の頭の「人が通した行」が空になり、問いを外さない）。
- 返り:
  - `ok`（boolean）: R1〜R4 が全部 pass。深さで省いた目は数えない → 線 10・merge
  - `r1`・`r2`・`r3`・`r4`（object・null 可）: 目ごとの `{status, reason}`。status は `pass`・`redesign-needed`・`unverifiable`（R2 の `unverifiable` は前に入る人の直し H8 の約束の変え。節が落ちた・独立設計が無い・前提の検算の道の時だけ）。省いた目は null → report
  - `questions`（array of string）: R4 の人への問い → 線 11
  - `premise_check`（object・null 可）: 前提の検算 `{verdict, reason}`、verdict は `resolved`・`escalate`。走らなければ null → 線 11・report
  - `structure_after`（指し札・null 可）: 直した後の構造の実測 → report
  - `protected_hits`（array of string）: 差分が当たった守りのパス → report
- 型つきの成果物: 目ごとに `output_type: eye-verdict`（中身は `{eye, status, reason}`。8 つのブロックで揃えた形で、`docs/design.md` に書くのは 人の直し H5（本文の「依存」））。目ごとの節 `<目>-verdict` が出す。
- 入力の指し札の中身は、約束が名指す今の works のファイルと同じ形（8 つのブロックで揃えた決め）: `plan` → `plan-fields.json`、`design` → `design.json`（独立設計が無い run は `{"missing": "<理由>"}` を持つファイル。指し札は null にならない）、`judgment` → `judgment.json`、`purpose` → `purpose.json`、`ripple` → `ripple.json`、`world` → 定石の行の並び。
- 返す節の `output_format` は、上の欄をちょうど持つ（全部 `required`・`additionalProperties: false`）。欄を足す・名を変える・型を変える・欄を落とすのは線との約束を変えることなので、この PR ではしない。要ると分かったら PR の本文の「約束を変える頼み」に書き、約束どおりの形で作り終える。
- 入力は Archon の工程の `inputs:` に宣言する（値は字。指し札・配列・object は JSON の字で届くので `json.loads` で読む）。`if_skipped: null` で届く値は字 `null`。

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
- 外への書き込み（GitHub・対象のリポジトリの main・人に見える所）は、このブロックでは無い。書くのは run の置き場（`$ARTIFACTS_DIR/eyes/`）だけ。
- ブロックの YAML と script は、ほかのブロックのフォルダを指さない（E4）。ほかのブロックの返りは `with:` の入力として受けるだけ。
- 筋書き（fixture）は Archon の `workflow test` の形（`fixtures/<名>.stubs.yaml`。予約の鍵 `fixture:`（`expect`・`fail-node`・`reached`・`inputs`・`resolved-text-contains`）と `exec-code:`、残りの鍵は節の id → 差し替えの出力）。script の中身まで通したい筋書きは `exec-code: true`。
- ブロックの YAML の形の試験（`tests/workflows/test_<名>.py`）は PyYAML で YAML を読み、Archon を起こさない。筋書きを Archon で回す試験も同じ `tests/workflows/test_eyes.py` に書く（`test_fixtures_pass_in_archon`）: issue #47（P0）の `tests/archon.py` で、`workflows/eyes/` と `workflows/.shared/` だけを `.archon/workflows/works-factory/` に置いた使い捨ての git の木を作り、使い捨ての `ARCHON_HOME` と `WORKS_FACTORY_ROOT` で `archon workflow test` を走らせる。Archon の源が無ければ `tests/archon.py` が `skipTest("Archon の源が無い: ...")` で見送る。共有の筋書きの試験のファイルは無い。

## Archon で書けない所

- 拒否の文を足して同じ会話で出し直させる（旧の目の輪の `fresh_context: false` と「前の回の受け付けが拒んだ理由」の節）: Archon の `retry` は新しい試みで、拒否の文を役に渡す口が無い。`output_format` の照らしで落ちた返りを `retry` が出し直すので、型の誤りは同じく 3 回で止まる。旧の照らしのうち型の外の物は `r4_inventory` だけで、`if`/`then` か返す節の照らしで持つ。埋めは要らない（`docs/polyfills.md` に足す行は無い）。違いは PR に書く。
- 指し札は同じ run の中だけ（`docs/design.md` の「Archon の分かっていること」）。前のブロックの指し札は線が同じ run で渡すので、このブロックは困らない。
- 落ちた節の返りへの `with:` の結びは `if_skipped` を書いても誤りで止まる（`dag-executor.ts`:519-534）。並べた目の返りは、返った時だけ走る script の節がファイルに書き、出口はファイルを読む（今の works の作業ファイルの形と同じ。新しい埋めは要らない）。
- 同じブロックを 2 度差し込む所は無い（U2 に当たらない）。

## E11 の 3 つの答え

1. Archon が持っているか: 並べ（同じ層の節）・順（`depends_on`）・飛ばし（`when:`）・落ちても進む柵（`trigger_rule: all_done`）・読むだけの縛り（`mutates_checkout: false`）・新しい会話（`context: fresh`）・道具の絞り（`allowed_tools`）・返りの型の照らしと出し直し（`output_format`・`retry`）・型つきの成果物（`output_type`）を持つ。今の works の錠・route・prep・accept の輪・作業ツリーの写しの比べは、これらで置き換えて持ち込まない。
2. ASF が持っているか: `W/review/archon-review.yaml` の読むだけのレンズを並べる形（:118-127）・`all_done` の柵（:207-213）・有効だったレンズの返りの欠けを名指して通さない出口（:214-236）。違い: ASF は合わせ役（synthesize）が AI の判断で ready を決めるが、eyes は目ごとの status を機械（`lib/eyeverdict.py`）がまとめる（今の works と同じ。R2 の verdict を確定するのは比較役で、まとめ役は書き換えない）。
3. 本当に要るか: 能力の棚卸しの「独立の目 R1〜R4 と前提の検算」「直した後の構造の実測」「守りのパス」と、受け入れの一覧の `r1.*`・`r2.compare`・`r3.coherence`・`r4.*`・`stop.premise_check`・`p4.scalars`・`p4.assemble`。

## 受け入れ

1. 試験を先に入れて赤を見る（lib/ の部品が無い・YAML が無い）。その後で部品と YAML を入れて緑。赤と緑の出力の要約を PR に書く。
2. リポジトリの根からの全部の試験 `uv run --isolated python3 -m unittest discover -s . -t .` が緑。`tests/layers/` の層の試験（その時に在る物全部）も緑のまま。
3. Archon の実行ファイル（か源）が在る所で `archon workflow test workflows/eyes` の筋書きが全部通る。在る所で `archon validate workflows` に `works-factory-eyes` の誤りも警告も無い。Archon が無い所では、筋書きを回す試験 `test_fixtures_pass_in_archon` は名前つきで見送られる（`tests/archon.py` の `skipTest("Archon の源が無い: ...")`）。PR には、Archon で回した結果か、回せなかった訳を書く。
4. 持ってきた lib/ のファイルを元と比べた差分が、lib-port の「移し方」1〜5 で決めた直しだけ（このブロックは持ってくる物が無いので、新しく書いた `lib/eyeverdict.py` だけ。これは元に無い物として PR に書く）。
5. PR の本文に次を並べる（守りのパスの文書に書く代わり。土台の持ち主が `docs/design.md`・`docs/asf-notes.md` に写す）:
   - lib-port の「移し方」6 の 4 つ（元のパス → 置いた先・外した物と理由・言い換えた行・盤面の物を引数で受ける関数の一覧）。このブロックでは「持ってこなかった物（`blk-eyes/lib/eyes.py` の全部の関数と、その仕事を置き換えた Archon の機能）」の表にする。
   - 採った ASF の型（`docs/asf-notes.md` の「書き方」の 4 行の形）: `W/review` の読むだけのレンズの並べと `all_done` の柵と欠けを名指す出口。
   - 「能力の棚卸し」と「受け入れの一覧」のこのブロックの行ごとの、証の試験か筋書きの名。
   - 約束を変える頼み・使いたかった埋め（あれば）。少なくとも次を書く: `start`・`plan_questions`・`answers` の入力（下の「人が入れる前提の直し」）、r2 の値（前提不成立・独立設計が無い・節の落ちを `unverifiable` と reason の頭で表した事。約束の変え H8 に依る）、`world`・`ripple`・`green_ok` の読み手を R4 と目の頭に置いた事（今の works の目には読み手が無く、最後の関所が読んでいた）、`docs/design.md` の段 2 の eyes の行「型つきの成果物を自分の include の分だけ数える」を E5 に合わせて「自分の節の返りを `with:` で受ける」で満たした事。
6. ブロックの分（`docs/design.md` の段 2 の eyes の行）:
   - R1〜R4 と前提の検算と直した後の構造の実測の配線（筋書き `pass`・`premise`・`redesign`）と、返りの組み方（`lib/tests/test_eyeverdict.py`）。
   - 全部の役が `mutates_checkout: false`（`test_every_role_node_is_read_only`）。
   - R2 の禁じた入力が届かない（`test_r2_compare_gets_no_forbidden_input`）。
   - R4 の問いと守りのパスの当たりが返りに載る（`test_verdict_drops_passed_questions`・`test_verdict_carries_protected_hits`・筋書き `protected-hit`）。
   - 型つきの成果物 `eye-verdict` を目ごとに出し、返す節は自分の節の返りだけを数える（`test_eye_verdict_typed`・`test_barrier_before_verdict`）。
   - 全部の単位が軽量の run は R1〜R4 を省き、r1〜r4 が null・ok が true（筋書き `all-light`。持ち主の決め `dynamic-depth`）。
   - 目の節が落ちても R4 と出口が走り、落ちた目を名指して ok を false にする（`test_r4_waits_for_r1_and_r2_lanes`・`test_barrier_before_verdict`・`test_verdict_names_fallen_eye`）。

## 範囲

- 作るのは `workflows/eyes/` の下・本文の「lib/ に持ってくる部品」の lib/ のファイル（`lib/eyeverdict.py`）・本文の「試験」のファイル（`lib/tests/test_eyeverdict.py`・`tests/workflows/test_eyes.py`）だけ。
- 触らない（守りのパス。ASF の merge が人の手に残す）: `workflows/line/**`・`workflows/.shared/**`・`docs/design.md`・`docs/owner-decisions.md`・全部の `AGENTS.md`・`pack.json`・`README.md`・`MISSION.md`・`engineering.md`・`.github/**`・`harness/**`・`factory/**`・`.factory/**`。
- 触らない（同じ時に別の run が作る）: ほかの 7 つのブロックのフォルダ（`workflows/<ほかの名>/`）と、それらの issue が名指す lib/・試験のファイル。ほかの PR と同じファイルを作らない。
- 触らない（前に入る物）: lib-port と`docs/plans/2026-10-12-blocks/prereq.md` の issue で入った lib/ のファイル（本文の「依存」に並べた物）とその試験、`tests/workflows/__init__.py`・`tests/archon.py`、`pyproject.toml`、`docs/`（PR の本文に書く。上の受け入れ 5）。持ってきた部品の中で前提の部品に直しが要ると分かったら、直さず PR の本文に書く。
- 決めた範囲で能力を落とす直しが要ると分かったら（持ち主の決め `superset`・`no-narrow`）、止めて PR の本文に書く。
- 作るファイルの全部（これ以外を作らない。どの名も `factory`・`FACTORY`・`harness`・`.factory`・`archon-` で始まらない。E18）:
  ```
  workflows/eyes/**
  lib/eyeverdict.py
  lib/tests/test_eyeverdict.py
  tests/workflows/test_eyes.py
  ```
  `workflows/eyes/**` の中身: `works-factory-eyes.yaml`、`commands/r1-comments.md`・`r1-minimality.md`・`r2-compare.md`・`premise-check.md`・`r3-coherence.md`・`r4-scope.md`、`scripts/structure_after.py`・`prep.py`・`protected.py`・`save_reply.py`・`eye_verdict.py`・`verdict.py`、`fixtures/pass.stubs.yaml`・`redesign.stubs.yaml`・`premise.stubs.yaml`・`all-light.stubs.yaml`・`protected-hit.stubs.yaml`。

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

- 前に入る人の直し H8（merge と共有）: `docs/design.md` の eyes の返りの `r1`〜`r4` の行の「（R2 は `unverifiable` を持たない）」を消し、R2 の `unverifiable` は「R2 の比較の節が落ちた・独立設計が無い・独立設計が問いは立たないと言った（判定は `premise_check`）」の時だけと書く。このブロックはそれが入った約束で書く。
- main に在る物（lib-port の PR と`docs/plans/2026-10-12-blocks/prereq.md` の issue）: `lib/structmark.py`・`lib/concepthome.py`・`lib/planmarks.py`・`lib/gatemarks.py`・`lib/promptsection.py`・`lib/startrec.py`（lib-port）と、`lib/answer.py`（lib-port）と、`lib/protect.py`・`lib/protected.json`・`lib/design.py`・`lib/REVIEW.md`・`lib/stage_b.py`・`lib/measure.py`・`lib/eye.py`・`lib/conceptfence.py`・`lib/depth.py`（`docs/plans/2026-10-12-blocks/prereq.md` の issue（ブロックの前の共有の部品）。本文の「依存」の前に入る物）、`tests/workflows/__init__.py`（`docs/plans/2026-10-12-blocks/prereq.md` の issue）、`workflows/.shared/boundary.py`。
- issue #47（P0）（この issue より前に main に入る）: `bin/_lib/place.py` の `workflow_source` の pack の形（`.archon/workflows/works-factory/<ブロック>/`）、未決 U5 の決め（`boundary.lib_root()` が `WORKS_FACTORY_ROOT` を読み、無ければリポジトリの中の `lib/`）、試験の助け `tests/archon.py`（止めた Archon の源と bun を見つけ、名指したブロックのフォルダと `.shared/` だけの使い捨ての木で Archon を走らせる。無ければ見送る）、CI が Archon の源と bun を取ること、層の試験の `archon validate`。
- 置き場は P0 が決める: 自分の工程を Archon の packaged の形（`.archon/workflows/works-factory/<ブロック>/`。pack は works-factory、工程のフォルダはブロック）で読ませる殻と、`boundary.lib_root()` が run の時に lib/ を見つける形（未決 U5）。このブロックは packaged の形を前提に `script:`・`command:` を自分のフォルダから名指し、lib/ は `boundary.lib_root()` だけで見つける。
- 守りのパスの文書の共通の直し（`tests/workflows/` の木・段 2 の共通 4・5 を PR の本文へ・揃えた形 H5 ほか）は 人の直し H1〜H5（本文の「依存」）。このブロックだけの直しは下の節。
- ほかのブロック: 待たない。ほかのブロックの返りは線の `with:` で入力として届くだけで、このブロックの試験はその形の入力を筋書きと試験の中で作る。入力の指し札の中身は約束が名指す今の works の形で読む（`plan` は `plan-fields.json` の欄の並び・`design` は `r2.design` の返り・`judgment` は `judgment.json`、記録の制約は `judgment` の指し札のファイルと同じフォルダの `premises.json`（この名ちょうど。ほかの隣のファイルは開かない）の欄 `constraints`。無ければ「渡っていない」の 1 行を頭に書き、落とさない）。

## 人が入れる前提の直し

`docs/design.md` の「ブロックの返りの約束」の「### eyes の返り」の「入力（`with:`）」の箇条の末尾に、次の 2 行（入力 3 つ）を足す（線を書く人がこの名で渡す。eyes は 3 つとも既定 `null` で受けるので、入るまでも動く）:

```
  - `start` ← `$start.output.record`（直した後の実測の数える版・守りのパスの当たり・方針の文書の置き場）
  - `plan_questions` ← `$plan-review.output.questions`、`answers` ← `{ from: "$gate-before-fix.output", if_skipped: null }`（修正前の関所で人が通した行を R4 に渡し、同じ行を聞き直さない。持ち主の決め `decision-records`）
```

同じ節の `plan-review` の返り `questions` の読み手（「→ 線 6」）に「・eyes」を足す（E5 の読み手の目録）。

`docs/design.md` の「作りの順」の段 2 の個別の行（587 行）の `eyes` の文のうち「型つきの成果物を自分の include の分だけ数える。」を、次に替える（E5 は `$TYPED_ARTIFACTS_FILE` を読むのを report だけにしている。eyes は自分の目の返りを `with:` で受けるので、ほかの include・ほかの run の物を数える道が初めから無い）:

```
型つきの成果物 `eye-verdict`（`{eye, status, reason}`）を目ごとに出す。返す節は自分の目の返りを `with:` で受けてまとめ、型つきの成果物の一覧は読まない（読むのは report だけ。E5）。
```

