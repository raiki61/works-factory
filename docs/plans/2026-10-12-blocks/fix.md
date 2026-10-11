<!-- coldwrite:skip ASF の役が読む作業の計画（issue の本文）。語は works-factory の docs/design.md の「語」の節で定義 -->
# fix: 修正のブロックを中身ごと作る（workflows/fix/ と、それだけが使う lib/ の部品と試験）

works-factory は、修正依頼を受けて確かめ済みの変更と報告を返す工場を、Archon（AI の工程を YAML で書いて回す道具）の上に作り直しているリポジトリ。前の形の「今の works」（公開リポジトリ raiki61/claude-plugins の `works/`。移す元の版は `pack.json` の `works.commit` = `2aa7c66cf7abe1fe09699ac2942d107123214168`）は、判定・計画・修正・確かめ・報告をつないだ工場で、その能力を 1 つも落とさずに、線（`workflows/line/`。ブロックを並べる 1 本の工程）・8 つのブロック（`workflows/<名>/`）・助け手（`lib/`。Archon を知らない Python）に移している。この issue は、そのうちのブロック `fix` を、フォルダの中身ごと 1 つの PR で作る。8 つのブロックは別々の run で同時に作られ、線とはブロックの返りの約束（`docs/design.md` の「ブロックの返りの約束」）だけでつながる。元のファイルは `https://raw.githubusercontent.com/raiki61/claude-plugins/2aa7c66cf7abe1fe09699ac2942d107123214168/<パス>` で読める（本文の「元」の欄の `<パス>`）。ASF は Archon の作者が作った、issue から PR までの工程の束（`docs/design.md` の「語」）。

8 つの中で一番大きい。PR は 1 つだが、下の「commit の順」で波ごとに積む。

## 読む物

- 根の `AGENTS.md`（リポジトリの形・E8〜E11・E13・E14・E18）、`workflows/AGENTS.md`（E1・E2・E4〜E7・E12・E16・E17）、`lib/AGENTS.md`（E3）、`tests/AGENTS.md`。決まりの番号 E1〜E18 の中身はそれらの文書に在る。
- `docs/design.md`: 「ブロック」の `fix` の節・「ブロックの返りの約束」の `fix` の返り・「能力の棚卸し」の `fix` の行・「受け入れの一覧」・「Archon の分かっていること」と未決 U1〜U8・「作りの順」の段 2 の `fix` の個別の行・「線」の「繰り返し」。
- `docs/plans/2026-10-12-lib-port.md` の「移し方」1〜6（この issue で `lib/` に持ってくる部品も同じ移し方に従う。足す直しは下の「盤面に届く能力の扱い」の (a)・(b) だけ）。
- `docs/owner-decisions.md` のうち本文が引く決め（`no-queue`・`parallel`・`lib-port-as-is`・`tdd`・`refactor-same`・`light-in-loop`・`planner-talk`・`cross-check`・`drift-in-loop`・`declared-io`・`persona`・`unit-sessions`・`impact-first`・`code-review-lens`・`dynamic-depth`・`lang-neutral`・`superset`・`no-narrow`・`no-timeouts`・`model-effort`・`injected-map`・`fix-quality`）。
- Archon の振る舞いは、ASF と同じ Archon の源（止めた Archon。`docs/design.md` の「語」。`coleam00/Archon` の commit `d97d00ef15cce4b15d39e42635e4e86996ec1351`）の文書 `packages/docs-web/src/content/docs/`（特に `guides/script-nodes.md`・`guides/authoring-workflows.md`・`guides/approval-nodes.md`・`reference/cli.md` の dry-run と `workflow test`）と源 `packages/workflows/src/` で確かめる。ASF の工程は同じ commit の `.archon/workflows/sdlc/`（本文の `W`）。
- このブロックの分:
  - 元の工程: `works/blk-fix/blk-fix.yaml`（2082 行。節の並びと各節の注釈が、移す振る舞いの正本）・`works/blk-delta/blk-delta.yaml`・`works/blk-lens/blk-lens.yaml`・`works/blk-refix/blk-refix.yaml`、元の線での差し込み方 `works/darkfactory/darkfactory.yaml` の 624・805・947・954・1007 行。
  - 元の部品: `works/blk-fix/lib/*.py`・`works/blk-fix/scripts/*.py`・`works/blk-fix/rules/*.md`・`works/blk-fix/fixtures/`、`works/blk-delta/`・`works/blk-lens/`・`works/blk-refix/` の `lib/`・`scripts/`・`commands/`・`rules/`・`schemas/`・`fixtures/`、`works/.shared/core/` の下の本文が名指すモジュール、`works/.shared/core/writerules/common.md`、`works/.shared/core/stage-models.json`・`works/.shared/core/agents/`、`works/blk-entry/schemas/start.schema.json`（始めの記録の欄）。
  - 元の試験: `works/tests/` の本文が名指すファイル。
  - 今の works の計画の文書: `works/docs/plans/2026-10-06-parallel-units.md`・`2026-10-07-lane-nodes.md`・`2026-10-07-fix-lane-nodes.md`・`2026-10-06-ask-planner.md`、`works/docs/keep-essence.md`。
  - ASF: `W/implement/archon-implement.yaml`（`loop:` と `until_field: done`・節 `assert-changed` が `$implement.execution.checkoutStart` と比べる・`outcome_field: green`。26 行の「Run success ≠ green」）、`W/implement/scripts/assert-changed.ts`、`W/deliver/archon-deliver.yaml` の 268〜390 行（review → `corrections` の `loop_group`）。
  - Archon: `guides/authoring-workflows.md` の「Launching a Separate Governed Run with `workflow:`」（`isolation:`・「Running sub-runs side by side」・「Fanning out over a list with `fan_out:`」）と 270〜300 行（`context: {resume: …}`）と「Composed behaviour」、`guides/hooks.md`（YAML の `hooks:` は固定の応答だけ）、`guides/loop-nodes.md`、源の `executor.ts`:1291-1311（子の run の循環の照らしと深さの上限）・`dry-run.ts`:1221-1256（dry-run は届く `workflow:` の `fan_out:` の節を落とす）・`dag-executor.ts`:519-534（落ちた節への `with:` の束ねは `if_skipped` が在っても投げる）。

## 目的と引き継ぐ能力

単位ごとに直す。TDD の輪（名指しのテストが failure で落ち、直して通ることを JUnit の XML で機械が見る。役が引いた失敗の文が結末に在るかを照らす）・テストの凍結・修正案の範囲の照らしと相談・書き込みの出どころの突き合わせ・当たる試験の選び・3 回で諦める・食い違いの申し出と読むだけの裁定役・組ごとの並べ・後始末・差分の審査とレンズ（silent-failure-hunter）と手直し 2 往復を、1 つのブロックの中で閉じる（差分の審査を fix に置く訳は `docs/design.md` の fix の節）。

能力の棚卸しの行（元 2aa7c66c → 新しい置き場）:

- TDD の輪と赤の判定 — `blk-fix/lib/tddloop.py`（`red_check`・`step`）と `.shared/core/graphloops/rules/review-loop-tdd.py`（`red_problems`・`green_problems`・`parse_junit`・`match_case`）→ `lib/tddloop.py`（赤緑の判定の芯は`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/baseline_red.py` を読む）・役 `tdd`（指示書は `commands/fix-rules/tdd.md` から script の節が組む）
- 元から赤のテストの区別 — `tddloop.py`（`_base_reds`・`temp_tree`・`rev_id`・`selected_problems`）→ `lib/tddloop.py`（元の名のまま。赤緑の判定と元の結末のファイルの読み書きは `lib/baseline_red.py`）
- テストの凍結と許しの 1 本道 — `.shared/core/conflict.py`（`test_permits` ほか）・`blk-fix/lib/fixgates.py`・`tddloop.py`（`frozen_problems`・`frozen_asks`）→ 同じ名で `lib/`
- 範囲の照らしと相談 — `.shared/core/planrange.py`・`blk-fix/lib/planscope.py`・`blk-fix/lib/consult.py` → 同じ名で `lib/`・相談の答えの役 `consult-answer`
- 書き込みの出どころ — `.shared/core/writes.py`（と包みの記録 `record-write.py`）→ `lib/writes.py`（記録の取り方は未決 U6。下の「Archon で書けない所」）
- 当たる試験の選び・テストのファイルの見分け — `.shared/core/impact.py`（`select_tests`・`is_test_file`）と `changemap.py` → `docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/impact.py`・`lib/changemap.py`。fix はそれを読む
- 欠陥の探し方の数え直し（keep-essence の 7。受け付けの時の数え直し）— `.shared/core/recount.py`（`accept_fix`・`collect`・`fix_reply`）と `querytest.py` → `lib/recount.py`（fix が持ってくる）・`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/querytest.py`
- 3 回で諦める — `blk-fix/lib/parking.py`・`fixlanes.GIVE_UP_AFTER`・写しの rules の `RETRY_MAX` → `lib/parking.py`・`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/rolekit.py` の `GIVE_UP_AFTER`（3）
- 食い違いの申し出と裁定 — `.shared/core/conflict.py`・`blk-fix/lib/ruling.py`・`blk-fix/rules/ruler.md`・`principles.md` → `lib/conflict.py`・`lib/ruling.py`・役 `ruler`（読むだけ）
- 並べの枝 — `lanekit.py`・`fixlanes.py`・`tddlanes.py`・`unitlanes.py`・`.shared/core/unittrees.py`（`docs/plans/2026-10-12-blocks/prereq.md` の issue）→ この YAML の `fan_out:`（並べ・集め）と、組の作り・戻す順の当て（`lanekit.groups`・`merge_in_order`・`unittrees.apply`・`unitlanes.overlap`）と `lib/groups.py`（`docs/design.md` の能力の名 `lib/groups`。親の姿を子の作業ツリーに写す・子の差分を取る）。固定の枝の数（`lanekit.MAX_LANES` と `*-lane-loop-1..3`）・待ちの列・錠（`lanekit.queue_lock`・`queue_put`・`take`・`taken`・`pending`。今の works の commit `ab9b9f17`）は持ち込まない（持ち主の決め `no-queue`「待ち行列はいらない。」）
- 後始末 — `.shared/core/leftovers.py`（`record_ignored`・`remove_new_ignored`）と節 `ignored-before`・`clean`・`assert-changed` → `lib/leftovers.py`（継ぎ目の直し）・この YAML の節
- 修正の決まりと借りた superpowers の節 — `seat.py`・`spseam.py`・`.shared/core/rulebook.py`・`blk-fix/rules/*.md`・`.shared/core/writerules/common.md` → `commands/fix-rules/`・`lib/rulebook.py`・`lib/fixrules.py`。superpowers の技は役の節の `skills:`（`seat.py` は持ってこない）
- 差分の審査・レンズ・手直し — `blk-delta`・`.shared/core/deltamarks.py`・`blk-lens`・`.shared/core/lens.py`・`blk-lens/lib/lenses.py`・`blk-refix`・`.shared/core/refix.py`・`blk-refix/lib/refixrules.py` → この YAML の節・`commands/delta-review.md`・`commands/review2.md`・`commands/lens-silent-failure-hunter.md`・`commands/fix-rules/refix.md`・同じ名の `lib/`

受け入れの一覧（review-graph の節）のうち fix が持つ物: `p1.worktree_before`・`p1.worktree_after`（後始末の控えと assert-changed）・`p3.lane_merge`（組の差分を重ね、当たらない物は次に見せる）・`p3.fix`（単位ごとに直す。不変条件を共にする箇所を全部挙げ、1 か所ずつ赤 → 緑。仕組みを新しく作ることになったら止める）・`p3.fix_delta`・`p3.delta_review`・`p3.delta_owed`・`p3.delta_fix` とその 2 回目。

keep-essence の 12（今の works の `works/docs/keep-essence.md`）のうち fix が持つ物: 赤緑の機械の判定・元から赤の区別・テストの凍結・3 回で諦める・書き込みの出どころ・当たる試験の選び・欠陥の探し方の数え直し（受け付けの時）・食い違いの申し出・単位ごとの記録が報告に届く（型つきの成果物 `tdd-unit`）。

今の works の観点の正本 `REVIEW.md` は、今の works で盤面の入力 `review_md` として graphloops の指示書（`p1.*`・`p2.*`・`r*` の 12 本）にだけ差し込まれていた（`works/.shared/core/board.py`:728、`works/.shared/core/gl-prompts/prompts/review-loop/` を `review_md` で grep）。修正の段の指示書（`blk-fix/rules/*.md`・`fixrules`・`blk-delta/commands/delta-review.md`・`blk-refix/commands/review2.md`・`blk-lens`）には差し込まれていないので、fix は `REVIEW.md` を読まない（落とす能力は無い）。

## 作る物

### ブロックのフォルダ `workflows/fix/`

#### `works-factory-fix.yaml`（工程の名も `works-factory-fix`。E9）

1 つの YAML が 2 つの形で走る。入力 `mode` が空（線が include する形。既定）か `group`（組ごとの子の run）。Archon の packaged workflow（`docs/plans/2026-10-12-blocks/prereq.md` の issue が決める置き場で、pack `works-factory` の下のブロックのフォルダ）はフォルダに YAML 1 つ（`guides/authoring-workflows.md` の 62 行）で、E9 は名を `works-factory-<フォルダ>` に決めるので、組の子を別の工程にできない。だから形 `""` の節 `groups-par`・`groups-seq` が自分を `workflow: works-factory-fix` で子の run として起こす。止めた Archon は子の run を起こす前に、子の工程の名が先祖の run の工程の名に在れば「Sub-run cycle detected」で拒む（`executor.ts`:1291-1306。深さの上限は 1307-1311）。fix を線が include した run の名は `works-factory-line` なので、子の `works-factory-fix` は先祖に居ない。fix を単独の run で起こすと、子の起こしが循環で落ちる。だから形 `""` は線の include の中でだけ回し、単独で回すのは形 `group` だけ（試験と筋書きもそう作る）。返す節は両方の形で同じ `fix`。

工程の頭に `interactive`・`worktree`・`container`・`evidence_policy`・`mutates_checkout` を書かない（include された時に落とされ、読み込みで警告が出る。`guides/authoring-workflows.md` の「Composed behaviour」）。

入力（`inputs:`）: 約束の 9 つ（`start`・`baseline`・`units`・`judgment`・`world`・`plan`・`ripple`・`depth`・`answers`。値は線の `with:` が渡す JSON の字）と、約束に無い 5 つ（どれも既定 `""`。線はまだ渡さない。下の「人が入れる前提の直し」）: `only_items`（案の直しの後の 2 回目の修正（線の include `refix`）で直す計画の項目の id の JSON 配列。空は直す義務の単位の全部）・`mode`・`group`（組 1 つの JSON）・`from_tree`（親の作業ツリーの姿の木の sha。空なら親の作業ツリーをそのまま使う子）・`out_dir`（子が詳しい結果を書く、親の run の置き場の中の絶対パス）。始めの記録の欄（`tdd_suite`・`test_cmd`・`policy_md`・`request_file`・`features_cut` ほか）は入力にせず、`start` の指し札の先から読む（無い欄は下の既定で読む）。

節（id・種類・何をするか。期限の鍵は全部 `1728000000`）。`mode` の分かれは `when:` で書く。役の節は今の works の同じ役の節の `settingSources`・`sandbox`・`context: fresh` を写す（止めた Archon は節ごとに受ける）。

形 `""`（ブロック。線の include の中だけ）:

1. `prep`（script `prep`・`mutates_checkout: false`）: 入力を読み、run の置き場の下 `fix/<include の名>/`（今の works の盤面の dir に当たる置き場。以下「置き場」。include の名は環境変数 `ARCHON_NODE_EXECUTION` の `path` の最初の `__` より前。`fix` と `refix` で分かれる。include の名 `refix` は線の案の直しの後の 2 回目の修正で、このブロックの中の手直しの節 `refix`・`refix-loop` と `lib/refix.py` とは別の物。include の中の節の id は `refix__refix-loop` のように頭が付くので当たらない）に、判定・修正案・波及・深さ・人の関所の答え（`answers`）・始めの記録の写しを書く。修正案は入力 `plan` の指し札の先（plan ブロックの `plan/r<k>/plan-fields.json`）を読み、計画役の返答（やり方・項目・狭める能力）が要る時だけ、同じフォルダの `p2.fix_plan.json` をこの名で開く（ほかの隣のファイルは開かない）。`only_items` が空でなければ、その項目に載る単位だけを直す義務にする。`leftovers.record_ignored` で修正役の前の git が無視するファイルを控え（`p1.worktree_before`）、`leftovers.snapshot` で始めの木を取る。単位と修正案の項目から組を作る（`lanekit.groups`。項目を共にする単位は同じ組。組は分けない。戻す順も決める）。返り `{groups: [{group_id, unit_ids, items}], count, par, start_tree, out_dir}`。`par` は組が 2 つ以上で、始めの記録の `features_cut`（今の works の機能の切り替えの実効で off の語。`works/.shared/core/entry.py`:421-440）に `fix_lanes` も `tdd_lanes` も無い時だけ真（欄が無ければ空で読む。今の works はこの 2 語で TDD の輪の並べと修正役の並べを別々に切れたが、新しい形は組の子の run が両方を回すので、どちらかが在れば並べない）。
2. `groups-par`（`workflow: works-factory-fix`・`fan_out: {items: $prep.output.groups, as: group, max_parallel: 5}`・`isolation: worktree`・`when: $prep.output.par == true`）: 組ごとに子の run を起こし、子ごとに Archon が作業ツリーを切る。`with:` は約束の 9 つをそのまま、`mode: group`・`from_tree: $prep.output.start_tree`・`out_dir: $prep.output.out_dir`。`max_parallel` は Archon の既定の 5 を見えるように書く（並べの数の上限だけ。列ではない）。`join` は既定の `all_done`（落ちた子は `{archon_failed: true, …}` の印で入る）。
3. `groups-seq`（`workflow: works-factory-fix`・`fan_out: {items: $prep.output.groups, as: group, max_parallel: 1}`・`isolation` を書かない・`when: $prep.output.par == false`）: 並べない run は、子を親の作業ツリーで 1 つずつ回す（Archon の作業ツリーの錠は先祖と子孫を除くので親と子は当たらない。文書「Running sub-runs side by side」）。`from_tree` は `""`。
4. `join`（script `join`・`trigger_rule: all_done`）: `with:` で子の返りを受けず（落ちた子への束ねは投げる。`dag-executor.ts`:519-534）、子が `out_dir/<group_id>/result.json` に書いた結果を組の順に読む。`groups-par` の時は子の終わりの木と `from_tree` の差分を、決めた順に親の作業ツリーへ当てる（`groups.diff_since`・`docs/plans/2026-10-12-blocks/prereq.md` の issue の `unittrees.apply`（3 方向・試験のファイルの union）・`lanekit.merge_in_order`）。当てた後に、その組で赤 → 緑を確かめた名指しを親の木で走らせ直す（`tddloop.selected_problems`。今の works の `tdd-join` の確かめ直し）。結果のファイルが無い（子が落ちた）・当たらない・確かめ直しが赤の組は、その組の差分を戻し、`returned: false` と理由を残し、その組の単位を `not_done` にする（`p3.lane_merge`。戻せなかった組は報告と次の run へ回す。`docs/design.md` の「繰り返し」）。`groups-seq` の時は子が親の木で直したので当てない（結果のファイルが在れば `returned: true`）。
5. `tdd-unit`（script・`output_type: tdd-unit`・`mutates_checkout: false`）: 子の結果から、組ごとの TDD の輪の結果を 1 つの成果物にして出す（下の「型つきの成果物 `tdd-unit` の形」）。子の run の型つきの成果物は子の run の物で親の一覧に載らないので、親の節で出す。
6. `conflict-check`（script）: 子と `join` が集めた食い違いの申し出の名指し（`<パス>:<行>`）が現物に在るかを照らす（`conflict` の申し出の照らし・`cite`）。在る申し出を置き場の `conflicts.json` に書く。
7. `rule-loop`（`loop_group`・`max_iterations: 3`・`when:` 申し出が在る時）: `rule-prep`（script。`ruling` と `fixrules` で指示書を組む）→ `ruler`（役・読むだけ・`mutates_checkout: false`・模型は今の works の役 judge の前付けの `opus`・`high`）→ `rule-accept`（script。`ruling` の照らし。裁定は `fix_test_scope`・`fix_code_as`・`ask_human`・`replace_query`・`fix_plan_item`）。
8. `fix-ruled-loop`（`loop_group`・`max_iterations: 12`・`when:` 直す裁定が在る時）: `fix-ruled-prep` → `fix-ruled`（役。`sonnet`・`high`。裁定の文のファイルを読んで直す）→ 範囲の相談の 3 節（下の 15 と同じ形）→ `fix-ruled-accept`。今の works は修正役の会話の続きで起こした。Archon の `context: {resume: …}` は `loop_group` の体の中で使えないので、修正役の返答と裁定を機械が保存したファイルで渡す新しい会話にする（下の「Archon で書けない所」の狭め）。
9. `clean`（script）: 控えに無かった git が無視するファイルだけを消す（`leftovers.remove_new_ignored`。除くパスとして Archon の工程の置き場 `.archon/` を script が渡す）。
10. `assert-changed`（script）: 申告したファイルが run の始めの版から本当に変わったか（今の works の `blk-fix/scripts/assert_changed.py`。ASF の `assert-changed` と同じ考え。`p1.worktree_after`）。直す義務の単位が残らず、外れた単位だけの run は空の申告を通す（`conflict.nothing_owed_but_excused`）。
11. 差分の審査（全部の単位が軽量の run は飛ばす。持ち主の決め `dynamic-depth`）:
    - `delta-cut`（script）: 修正だけの差分を切り、審査役の材料を書く（`refix.cut`）。
    - `delta-loop`（`loop_group`・`max_iterations: 3`）: `delta-review`（役・読むだけ・`mutates_checkout: false`・今の works の役 inspector の `sonnet`・`medium`・指示書 `commands/delta-review.md`）→ `delta-accept`（script。`refix.accept_review` と `deltamarks` の照らし）。
    - `lens-prep`（script。`lenses.render` で、利用者が入れた silent-failure-hunter の役の定義の本文（`docs/plans/2026-10-12-blocks/prereq.md` の issue の `rolekit.agent_def`）から指示書を組む）→ `lens`（役・読むだけ・`mutates_checkout: false`・`context: fresh`・`sonnet`・`medium`・指示書 `commands/lens-silent-failure-hunter.md`。`delta-loop` と並べる）→ `lens-collect`（script。`lenses` の集め。`lens` の返りを `with:` で受けず、`lens` が書いた置き場のファイルを読む）。
    - `refix-loop`（`loop_group`・`max_iterations: 3`・`when:` 審査が直す義務を出した時）: `refix-prep` → `refix`（役・`sonnet`・`high`）→ `refix-accept`（script。`refix.accept_fix`。範囲の外の変更は `planrange.check_paths` で拒み、書き込みの出どころを `writes` で照らす）。
    - `review2-loop`（`loop_group`・`max_iterations: 3`・`when:` 1 回目の手直しが走った時）: `cut2` → `review2`（役・読むだけ・`sonnet`・`medium`・`commands/review2.md`）→ `review2-accept`。
    - `refix2-loop`（`loop_group`・`max_iterations: 3`・`when:` 2 回目の審査が直す義務を出した時）: `refix2-prep` → `refix2` → `refix2-accept`。
12. `fix`（script `collect`・返す節・`trigger_rule: all_done`。前の節が落ちても飛ばされても走る）: 前の節の返りを `with:` で束ねず、各節が置き場に書いたファイルを読んで、下の「返りの約束」の欄を組んで返す。累積差分（run の始めの版から。未追跡を含む）を置き場に書いて指し札にする。この節は落ちない: 中の誤りは全部捕まえ、`done: false`・理由（`units` の `reason` と `groups` の `reason` に載せる）・ほかの欄は空の値（`[]`・`""`・`null`・印は全部 false・`delta_review` は `{rounds: 0, pass: false}`）で `output_format` を通る返りを返し、終了の値は 0（返す節が落ちると線が先へ進めない）。累積差分が書けない時の `diff` は、理由を書いた置き場のファイルの指し札にする。

形 `group`（組ごとの子の run。親の `workflow:` が起こす。単独の run でも回る）:

13. `group-start`（script）: `from_tree` が在れば、自分の作業ツリーを親の姿に写す（`groups.adopt_tree`。中は `git read-tree -u --reset <from_tree>`。子の worktree は同じ clone の worktree なので git の物を親と共有する見込み。U8 で実測する所）。控え（`record_ignored`）と始めの木を取る。`tddloop.start` で輪の状態を置き場に置く。テストの実行器は始めの記録の `tdd_suite`（今の works の線の入力 `tdd_suite` と同じ約束。空は実行器の無い run）で、元の結末（どのテストが元から赤か）は入力 `baseline` の指し札を`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/baseline_red.py` の読む口で読んだ `cases`・`exit` を使う。輪の頭で一式を 1 回走らせる今の works の振る舞いはそのまま残す（作業ツリーが base の時と同じだと始めの記録と元の結末から言えない限り、使い回さない）。
14. `tdd-loop`（`loop_group`・`max_iterations: 40`・`until_bash: test $tdd-step.output.done = true`・`when:` 実行器が在る時）: `tdd-prep`（script。`tddloop.prep` → `fixrules` で指示書を組んでファイルに書く）→ `tdd`（役。`sonnet`・`high`・`skills: [test-driven-development]`・`prompt:` は「指示書を Read で読み、その指示に従え」の 1 行）→ `tdd-step`（script。`tddloop.step`。段は route → 単位ごとに test（赤）→ fix（緑）→ refactor（持ち主の決め `refactor-same`。同じ会話）。段ごとに 3 回目の拒否で諦め、その単位を単位の頭の木に戻して食い違いの申し出で止める）。単位が替わる周は新しい会話にする（持ち主の決め `unit-sessions`。下の「Archon で書けない所」）。
15. `fix-loop`（`loop_group`・`max_iterations: 12`・`until_bash: test $fix-accept.output.done = true`）: `fix-prep`（script）→ `fixer`（役。返す節の id `fix` と分けた名。`sonnet`・`high`）→ 範囲の相談 `consult-check`（script。`consult` の頼みの照らし）→ `consult-answer`（役・読むだけ・`mutates_checkout: false`・`opus`・`medium`・`when:` 頼みが在る時。修正案の指し札と波及を読む新しい会話の計画役。持ち主の決め `planner-talk`）→ `consult-accept`（script）→ `fix-accept`（script。受け付けの照らし: `factchecks`・`fixgates`（凍結・範囲・赤緑の事後の照らし）・`writes`（書き込みの出どころ）・`recount.accept_fix`（受け付けの時の数え直し。keep-essence の 7）・`tddloop.selected_problems`（当たる試験だけを走らせる。持ち主の決め `light-in-loop`）。3 回目の拒否で、名指しの単位だけを段の頭の木に戻して諦め、ほかは先へ）。
16. `group-end`（script）: 終わりの木（`leftovers.snapshot`）・単位ごとの結末・TDD の輪の結果（`tddloop.exit_fields`）・申し出・異議（修正役の返答の欄 `rejudge_requested`）・修正役の印（`changed` の 6 つ）・許したテストの変更・後始末の件数を、`out_dir/<group_id>/result.json` に書く（`out_dir` が空の単独の run は自分の置き場に書く）。
17. `fix`（12 と同じ節。子の形では自分の組の行だけを約束の形で返す）。

指示書に始めの記録の値を差し込む所: 人の方針の文書（始めの記録の `policy_md`）と依頼の文のファイル（`request_file`）を、今の works と同じく `fixrules`・`refixrules` が組む指示書に載せる。欄が無い・空の時は、指示書に「人の方針の文書は無い」「依頼の文のファイルは無い」と 1 行ずつ書く（黙って抜かない）。

#### `commands/`

- `fix-rules/common.md`（元 `.shared/core/writerules/common.md`）・`fix-rules/brief.md`・`direct.md`・`principles.md`・`ruler.md`・`tdd.md`（元 `blk-fix/rules/`）・`fix-rules/refix.md`（元 `blk-refix/rules/refix.md`）: 修正の決まり。script の節が `fixrules`・`refixrules`・`rulebook` で読んで指示書を組む（持ち主の決め `injected-map`）。中身は元のまま。言い換えてよいのは 2 行だけ: `common.md` の 69 行（実行器の名。E13。例「実行器の絞り方（試験の id か名前で絞る）」）と 70 行（包みが Edit・Write を記録する前提。新しい形では記録が無いので「受け付けが版からの変更を返答の申告と突き合わせる」に。下の U6）。
- `delta-review.md`（元 `blk-delta/commands/delta-review.md`）・`review2.md`（元 `blk-refix/commands/review2.md`）・`lens-silent-failure-hunter.md`（元 `blk-lens/commands/lens-silent-failure-hunter.md`）: 読むだけの役の指示書。盤面・包みの事情（盤面のパス・`works-node:` の印・包みの記録）だけを Archon の書き方（`$INPUTS.<名>`・`$<節>.output`・指し札）に直す。
- 役 `tdd`・`fixer`・`fix-ruled`・`refix`・`refix2`・`ruler`・`consult-answer` は、今の works と同じく script の節が組んだ指示書のファイルを `prompt:` の 1 行で読ませる（指示書は run ごと・段ごとに替わるので `commands/` の固定の文にしない）。`docs/design.md` の fix の節の役の名（`tdd`・`fix`・`ruler`・`delta-review`・`lens`・`refix`）は能力の名で、ファイルの名は元の名にする（E18）。

#### `scripts/`

どれも「共通の書き方」の頭で境の口と lib/ を読み、lib/ の関数を呼ぶだけ（29 本）: `prep.py`・`join.py`・`tdd_unit.py`・`conflict_check.py`・`rule_prep.py`・`rule_accept.py`・`fix_ruled_prep.py`・`fix_ruled_accept.py`・`clean.py`・`assert_changed.py`・`delta_cut.py`・`delta_accept.py`・`lens_prep.py`・`lens_collect.py`・`refix_prep.py`・`refix_accept.py`・`cut2.py`・`review2_accept.py`・`refix2_prep.py`・`refix2_accept.py`・`collect.py`・`group_start.py`・`tdd_prep.py`・`tdd_step.py`・`fix_prep.py`・`consult_check.py`・`consult_accept.py`・`fix_accept.py`・`group_end.py`。名は元の `blk-fix/scripts/`・`blk-delta/scripts/`・`blk-lens/scripts/`・`blk-refix/scripts/` の同じ仕事の物に合わせる（元に無い物だけ新しい名）。Archon に届く事（`ARTIFACTS_DIR`・`ARCHON_` で始まる環境変数・`.archon/` の置き場・`INPUTS_` の名）は script の側だけが持ち、lib/ へは値を引数で渡す（E3）。決まりの文の置き場は script が import の後に `fixrules.RULES_DIR`・`fixrules.SHARED`・`fixrules.PROMPT_DIRS`・`refixrules.RULES`・`rulebook.CANON` を `workflows/fix/commands/fix-rules/` の下に置き替える（lib/ の字にグラフのパスを書かない）。

#### `fixtures/`（`tests/workflows/test_fix.py` が `tests/archon.py` の使い捨ての木で `archon workflow test` を回す。道のつながりだけを確かめる）

止めた Archon の dry-run の事実（`reference/cli.md` の 405-413 行・`dry-run.ts`）: 承認の節は自ずと通る・`until_bash` は走らない（輪は済んだと見なす）・差し替えの出力は節ごとに 1 つ・届く `workflow:` の節に `fan_out:` が在ると模擬は落ちる（`dry-run.ts`:1221-1256）・`exec-code` の節は空の `ARTIFACTS_DIR` と `TYPED_ARTIFACTS_FILE=''`・`WORKFLOW_ID=dry-run` で走る。だから形 `""` の道（並べ・`join`・審査・`collect`）は筋書きで通せない。それらの振る舞いは `tests/workflows/test_fix.py` の script の試験と `lib/tests/` で確かめ、形 `""` を通しで回すのは下の「Archon で書けない所」の U8 の実測（線か使い捨ての親の工程の include の中）。

- `group-tdd.stubs.yaml`（`fixture.inputs.mode: group`）: 実行器が在る → `group-start`・`tdd-loop`・`fix-loop`・`group-end`・`fix` が `reached`、形 `""` の節（`prep`・`groups-par`・`groups-seq`・`join`・審査）は飛ぶ。
- `group-no-suite.stubs.yaml`（`mode: group`）: 実行器が無い → `tdd-loop` が飛び、`fix-loop` だけで直す（今の works と同じ）。
- `group-consult.stubs.yaml`（`mode: group`）: 修正役が範囲の相談を頼む → `consult-answer` が `reached`。
- `block-stops-at-fanout.stubs.yaml`（`mode` 空）: `prep` の差し替えが `par: false` → `groups-seq` で模擬が落ちる（`expect: failed`・`fail-node: groups-seq`）。`prep` の入力の束ね（約束の 9 つと `only_items`）が解けることだけを確かめる。

### lib/ に持ってくる部品（このブロックだけが使う物）

移し方は lib-port の「移し方」1〜6。置き場は `works/.shared/core/<名>` → `lib/<名>`、`works/blk-*/lib/<名>` → `lib/<名>`。元のファイルが自分で `sys.path` に足す行（`_CORE = …/.shared/core` など）はそのまま残す（lib/ の中では効かない行になるが、移し方 1 のとおり変えない。PR に並べる）。2 つ以上のブロックが読む部品は、ブロックの前の`docs/plans/2026-10-12-blocks/prereq.md` の issue（ブロックの前の共有の部品）が入れる。この PR は`docs/plans/2026-10-12-blocks/prereq.md` の issue の部品を読むだけで、作らない・変えない（下の「依存」）。

#### 盤面に届く能力の扱い（8 つの計画で同じ文）

次の 2 つの形だけを許す。

- (a) 継ぎ目の直し: 持ってきたファイルの中で、盤面・Archon・持ってこない部品の一覧のモジュールへの 1 か所の呼び出しを、引数か lib/ のモジュールの呼び出しに替える（例: tddloop の `_failure_attrs` → `baseline_red` から import）。関数の名とほかの行は変えない。継ぎ目の行は全部 PR の本文に並べる。
- (b) 書き直し: 関数の殆どが盤面の読みの時は、元の関数の名のまま、値かファイルのパスを引数で受ける形に書き直し、新しい lib/ のファイル（`docs/design.md` の能力の名 `outcome`・`baseline_red`・`green_cert`・`seal`・`gate_axes` …、無ければブロックの名の付いた名）に置く。docstring に元の `<パス>:<行>` を書き、試験は元の試験の場合を写す。PR の本文に 1 つずつ並べる。
- ブロックをまたいで使う偽の盤面は作らない（ブロックの中だけの合わせ口は、そのブロックの中にだけ置く）。
- 持ってこない物: graphloops の記録の検証器（`scripts/review-record.py`・`record_common.py`。形は Archon の `output_format` が照らし、中身の決まりは (b)）。`reads.py`・`record-read.py`（未決 U6 を待つ。穴として書き、持ってこない）。

fix は主に (a) を使う。継ぎ目の見込み（字の照らしで出した物。実際の行は PR に並べる）:

- 盤面の物 `b` を受ける関数のうち、`b` から使うのが作業のファイルの置き場（`b.work(<名>)`）だけの物: `b.work(<名>)` を `pathlib.Path(b) / <名>`（`b` は置き場のフォルダのパス）に替える 1 か所の直し。当たる見込み: `conflict._path`（`conflicts.json`。これで `items`・`asked`・`ruled_fix`・`waiting`・`park`・`apply_rulings` ほかの読み書きが置き場の JSON で回る）・`lens.py` の `LENS_FILE` の 2 か所・`deltamarks.py` の `VERDICTS_FILE`・`fixrules.py` の `G1_IMPL`・`G1_REVIEW`。`conflict` の `_board.BoardGap` の送出は、同じ文の `ValueError` に替える（呼び手の script が捕まえる）。
- `b` から盤面の記録・状態（`b.record`・`b.trace`・`b.state`・`b.output_of_round`）も読む関数: 読む値を `prep`・`group-start` が置き場に書いたファイル（判定・修正案・始めの記録の写し）のパスで受ける形に替える。当たる見込み: `tddloop._duty`・`plan_contract`・`_briefs`、`fixrules.item_ranges`・`briefs_or_halt`、`planbrief.cut_at`・`by_unit_at`、`planrange.approved`・`check_paths`、`refix.cut`・`accept_review`・`accept_fix`・`_table`・`_pass`・`fix_delta`・`hole_ties`、`recount.fix_reply`・`accept_fix`・`collect`・`_fix_output`・`_coverage`。1 か所で済まない関数は (b) で `lib/groups.py` でなく元の名のまま同じファイルに残せないので、そのファイルの中で外し、(b) の書き直しを新しいファイル `lib/fixboard.py`（fix の置き場の読み書き。ブロックの名の付いた名）に置く。どちらにしたかを関数ごとに PR に並べる。`refix.cut`・`accept_review`・`accept_fix` と `planrange.check_paths` は、どちらの形でも能力を残す（`delta_accept.py`・`refix_accept.py` が呼ぶ）。
- `tddloop.py`:
  - `docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/baseline_red.py` に移った物（test-gate も読む物）の定義を、持ってくる `lib/tddloop.py` から外し、頭で `from baseline_red import _failure_attrs, run_suite` と読む（`run_suite` の呼び手の引数は変えない。`docs/plans/2026-10-12-blocks/prereq.md` の issue の `run_suite` に無い引数（`nice`・使い回しの `note`）を渡す所は、その引数を外す直しを (a) として並べる）。外した定義と、それにしか使わない `NO_FAILURE` などを PR に並べる。`temp_tree`・`rev_id`・`_base_reds`・`selected_problems` とその助け（`_args`・`_by_test_file`・`_left_to_ci`・`REV_CACHE`・`exe_id`・`load_json`・`save_json`・`ACCEPT_RUN`・`NO_SELECTED`・`PYTEST_FILE`）は `lib/tddloop.py` に元の名のまま残す。
  - `rules()`: `board.rules_module(board.graph_path(RULES_GRAPH))` を、`baseline_red` のモジュールを返す形に替える（`red_check` の `rules().red_problems`・`rules().match_case`・`rules().parse_junit`、緑の確かめの `rules().green_problems` がそのまま `baseline_red` に届く）。写しの rules（`works/.shared/core/graphloops/rules/review-loop-tdd.py`）は持ってこない。
  - `retry_max()`: `rules().RETRY_MAX` を`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/rolekit.py` の `GIVE_UP_AFTER`（3）に替える（今の works の `review-loop-tdd.py` の `RETRY_MAX = 3` と同じ値）。
  - `snapshot`・`touched`・`restore*`: `leftovers` の残る関数（`snapshot`・`git`・`git_names`）を読むので、下の `leftovers.py` を持ってくれば直しは要らない。
  - `_cmd_run`（`test_cmd` を走らせる口）: `docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/tree_run.py` に在る口を呼ぶ。`docs/plans/2026-10-12-blocks/prereq.md` の issue で外れた口（`slotted_run` など）に届く行は、`baseline_red.run_suite` と同じ起こし方の口に替える。子に渡す環境から Archon の変数を落とす所は script の側が持ち、`env` で渡す。
  - `prep` の `adapter.session_key_path`・`seat`: 外す（会話の切り方は下の「Archon で書けない所」）。
- `import board` の行で graphloops の小道具の置き場（`lib/graphloops`）が `sys.path` に載っていたファイル（`engine.` を使う `deltamarks`・`refix`・`unitrows`・`fixrules` ほか）は、その `import board` の行を `lib/graphloops` を `sys.path` に足す 1 行に替える（lib-port の部品 `carry.py` と同じ足し方）。
- `.archon/` の決まり（E3 で lib/ と `lib/tests/` に `archon` の字を書けない）: `leftovers.ARCHON_PREFIX`・`archon_digests`・`archon_changes` は外し、`parking._ours`・`writes.SKIP`・`leftovers.remove_new_ignored` などが `ARCHON_PREFIX`・`SKIP` を読む 1 か所を、後ろに既定値 `()` の引数「除くパスの頭」で受ける形に替える。script の節（`clean.py`・`assert_changed.py`・`fix_accept.py`・`join.py`）が `(".archon/",)` を渡す。`lib/tests/` の試験は中立の頭（例 `"vendored/"`）で確かめる。
- `leftovers.py`: lib-port の移し方 3 は `leftovers` を持ってこない部品に挙げるが、それは lib-port の範囲の話で、後始末は fix の能力（棚卸し「後始末: leftovers.py → fix」）なのでこの issue で扱う。`_board_path` の `script_io.scope_dir(board)` を `pathlib.Path(board)` に替える（置き場は呼び手が渡す。`fix` と `refix` の分けは `prep` の置き場の名で付く）。
- `lenses.render`: `rolekit` の盤面の口に届く 1 か所を、`docs/plans/2026-10-12-blocks/prereq.md` の issue の `rolekit.agent_def`（役の定義の本文を読む口）に替えて残す（`lens-prep` が呼ぶ）。
- `planscope.py`・`writes.py`・`parking.py`・`lanekit.py`（`merge`・`revert_strays`）: `leftovers` の盤面の控えに届く 1 か所を、置き場のパスの引数に替える。
- 外すだけの物: `adapter`（包みの会話の鍵・書き込みの記録の置き場）・`seat`（借りた superpowers の座。Archon の `skills:` に替わる）・`rolekit` のうち`docs/plans/2026-10-12-blocks/prereq.md` の issue に無い物（指示書の頭と返答の受け付けの包み。Archon の `output_format` に替わる）・`node_marker`（`recount.fix_output_format` の印の足し。役の返答の型はこの YAML の `output_format` が持つ）・`graphmap`・`script_io`（`main`・`last_reject` などの節の口。ブロックの script に替わる）・`reads`（U6）・待ちの列と固定の枝の数（`no-queue`）。

#### 部品の一覧（元 → 置いた先。どれも fix だけが作る）

- `.shared/core/conflict.py` → `lib/conflict.py`: 上の継ぎ目。保存の形は元のまま `conflicts.json` = `{"items": [行…]}`。行の欄のうちほかのブロックが読むのは `unit_key`・`kind`・`between`・`ruling`（`{decision, text, limits}`。`decision` は `fix_test_scope`・`fix_code_as`・`ask_human`・`replace_query`・`fix_plan_item`）・`replan`（`fix_plan_item` の行に `apply_rulings` が置く欄）。
- `.shared/core/planrange.py` → `lib/planrange.py`: `approved`・`check_paths`・`permit_paths` は上の継ぎ目で残す。
- `.shared/core/recount.py` → `lib/recount.py`: 残す `v1_changes`・`SITE_PATH`・`PRECEDENT_MIN_LEN`・`_precedent_conditions`・`CHANGES_FILE` ほか。`fix_reply`・`accept_fix`・`collect`・`_fix_output`・`_coverage` は上の継ぎ目か `lib/fixboard.py` の書き直しで残す（受け付けの時の数え直し。keep-essence の 7）。外す `fix_output_format`・`FIX_OUTPUT_FORMAT`・`RULED_OUTPUT_FORMAT`（`node_marker`）・`main_accept`（節の口）・`READS`（reads）。
- `.shared/core/refix.py` → `lib/refix.py`: `cut`・`accept_review`・`accept_fix`・`fix_delta`・`hole_ties` は上の継ぎ目か (b) で残す。外す `RECEIVES`・`output_format`・`prep_fix`・`main_accept_*`・`route`・`collect_*`・`must`・`reads_all`・`script_main`（seat・rolekit・reads・節の口）。
- `.shared/core/lens.py` → `lib/lens.py`・`.shared/core/deltamarks.py` → `lib/deltamarks.py`: `b.work` の継ぎ目だけ。
- `.shared/core/leftovers.py` → `lib/leftovers.py`: 上の継ぎ目。
- `.shared/core/rulebook.py` → `lib/rulebook.py`: 外す `render`（rolekit の盤面の口）。
- `.shared/core/writes.py` → `lib/writes.py`: 外す `sink`（adapter）。`SKIP` の継ぎ目。`base_test_texts`・`changed`・`changed_from` は leftovers の継ぎ目で残す見込み。
- `blk-fix/lib/tddloop.py` → `lib/tddloop.py`: 上の継ぎ目。
- `blk-fix/lib/` の `consult.py`（外す `answer_format`・`receives`・`RECEIVES`・`items_of`・`alias`・`ask`・`place_of`）・`factchecks.py`（盤面の受け付けの口 `named_reply`・`check_*`・`precheck`・`main` の盤面の読みは上の継ぎ目で置き場のパスに替え、替えられない物は外す）・`fixgates.py`（tddloop の継ぎ目で残る物以外の盤面の口を外す）・`fixrules.py`（上の継ぎ目）・`parking.py`（`_ours` の継ぎ目）・`planbrief.py`・`planscope.py`・`ruling.py`（外す `RULE_OUTPUT_FORMAT`・`check`・`_last_reject`・`prep`・`problems`・`accept_rule` の節の口。裁定の語と照らしの芯は残す）・`unitrows.py`（外す `take`）・`unitlanes.py`（外す物の見込み無し）→ `lib/` の同じ名。
- `blk-fix/lib/lanekit.py` → `lib/lanekit.py`: 残す `groups`・`relocate`・`plant`・`tree_ok`・`merge_in_order`・`shared`・`carry`・`remove`・`JOINED`・`MERGED`・`BACK`・`merge`・`revert_strays`。外す `MAX_LANES`・`node_names`・`fork_out`（固定の枝の数）・`queue_lock`・`_locked`・`_queue`・`queue_put`・`take`・`taken`・`pending`（待ちの列と錠。持ち主の決め `no-queue`「待ち行列はいらない。」）・`mark`（adapter）・`claim_problems`・`park`（盤面）。
- `blk-fix/lib/tddlanes.py`・`blk-fix/lib/fixlanes.py` → `lib/` の同じ名: 枝の輪（固定 3 本・待ちの列）の関数（`lane_prep`・`lane_step`・`_take`・`fork`・`join`・`plan`・`_park` など）が外れ、残るのは枝の中の確かめの関数（子の run の `tdd-step`・`fix-accept` が読む物）だけの見込み。残る物が無ければファイルを置かず、PR に訳を書く。
- `blk-lens/lib/lenses.py` → `lib/lenses.py`（`render` は上の継ぎ目で残す。外す `RECEIVES`・`route`・`collect`・`exit_` の節の口）・`blk-refix/lib/refixrules.py` → `lib/refixrules.py`（外す `RECEIVES`・`parts`・`build`（seat）。指示書の組みは `fixrules` と同じ形で script の節が組む）。
- 新しい `lib/groups.py`（`docs/design.md` の能力の名 `lib/groups`。元に無い所だけ。組の作りそのものは `lanekit.groups` を呼ぶ）: `adopt_tree(repo, tree)`（作業ツリーを木 `tree` の姿にする。`git read-tree -u --reset`）・`end_tree(repo)`（`leftovers.snapshot`）・`diff_since(repo, from_tree, end_tree)`（`docs/plans/2026-10-12-blocks/prereq.md` の issue の `unittrees.diff` を呼ぶ）。
- 新しい `lib/fixboard.py`（上の (b) が要った時だけ。fix の置き場の読み書き）。

持ってこない: `.shared/core/graphloops/rules/review-loop-tdd.py`（`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/baseline_red.py` が持つ）・`reads.py`・`record-read.py`・`record-write.py`（U6）・`replan.py`（plan）・`design.py`・`impact.py`・`changemap.py`・`tree_run.py`・`unittrees.py`・`holeties.py`・`policy.py`・`protect.py`・`querytest.py`・`libdocs*.py`・`depth.py`（`docs/plans/2026-10-12-blocks/prereq.md` の issue）・`report.py`（report）・`seat.py`・`adapter.py`（落とす包み）。

### 試験

- `lib/tests/` に元の試験を元の名で持ってくる（移し方 5）。見込み（下の「範囲」の一覧と同じ）: `test_unitlanes.py`・`test_lanekit.py`・`test_writes.py`・`test_delta_marks.py`・`test_plan_scope.py`・`test_plan_brief.py`・`test_consult.py`・`test_fix_gates.py`・`test_fix_rules.py`・`test_fix_units.py`・`test_fix_duty.py`・`test_duty_sets.py`・`test_conflict_kinds.py`・`test_fix_precheck.py`・`test_fix_accept_all.py`・`test_tdd_frozen.py`・`test_tdd_frozen_function_span.py`・`test_tdd_outside.py`・`test_tdd_lanes.py`・`test_fix_lanes.py`・`test_blk_fix.py`・`test_blk_fix_tdd.py`・`test_blk_fix_conflict.py`・`test_blk_lens.py`・`test_blk_refix.py`・`test_blk_tests_delta.py`。盤面（`board`・`entry`・写しの rules・`GateBase`）・包み・`works/blk-*/` の YAML・`darkfactory/` を使う試験の関数とクラスは外す。`docs/plans/2026-10-12-blocks/prereq.md` の issue の部品（`baseline_red`・`impact`・`tree_run` ほか）だけを縛る試験の関数も外す（`docs/plans/2026-10-12-blocks/prereq.md` の issue が持つ）。特に `test_blk_fix_tdd.py` の `parse_junit`・`red_problems`・`green_problems`・`_failure_attrs`・`run_suite` の場合は、`docs/plans/2026-10-12-blocks/prereq.md` の issue が `lib/tests/test_baseline_red.py` に写すので外し、同じ場合を 2 つのファイルに持たない（外した名を PR に並べる）。外して 0 本になるファイルは置かず、PR に名前を並べる。`lib/` と `lib/tests/` に `archon` の字を書かない（E3。`.archon/` は中立の頭に替える）。残る数の見込みは立てない（盤面で回す試験が多い）。外した試験が縛っていた能力は、下の 2 つの新しい試験で縛り直す（どれで縛ったかを PR に書く）。
- `lib/tests/test_fix_seams.py`（新しい名。継ぎ目の直しと `lib/groups.py`（と在れば `lib/fixboard.py`）の試験）: 継ぎ目の直しをした関数ごとに 1 本以上。盤面を使わず、`tests/bin/gitkit.py` と `tests/e2e/target-seed/` の写しで小さなリポジトリを作る。少なくとも:
  - `tddloop.red_check` が `baseline_red` の `red_problems` に届く: 名指しが failure で落ちる JUnit XML で問題なし／error・居ない・もう通る・飛ばされたで拒む／名指しの外の元の緑が赤で拒む／引用が失敗の文に無いと拒む／照らす先が空なら `unchecked` に返る。
  - `tddloop.retry_max() == 3`。`tddloop._failure_attrs`・`tddloop.run_suite` が `baseline_red` の物と同じ物。`tddloop._base_reds`・`selected_problems` が `lib/tddloop.py` に在り、版の写しで赤の試験を外す。
  - `leftovers.record_ignored` と `remove_new_ignored`: 控えに無かった無視されるファイルだけを消し、前から在った無視されるフォルダの中は残し、除くパスの頭（`"vendored/"`）の下は消さない。既定の `()` では除かない。`parking._ours`・`writes` の除きも同じ。
  - `conflict` の申し出の読み書きが置き場の `conflicts.json`（`{"items": [...]}`）で回る（書いた申し出を読み、裁定を当てると直す義務から外れ、`fix_plan_item` の行に `replan` の欄が付く）。
  - `planrange.check_paths` と `refix.accept_fix`: 承認済みの修正案の項目の範囲の外を変えた手直しを拒む（範囲の拒みの場合）。範囲の中なら通す。
  - `refix.cut`・`accept_review`: 置き場の材料で審査の材料を書き、`deltamarks` の欄の欠けを拒む。
  - `recount.accept_fix`: 受け付けの時に数え直しの欄を照らす（今の works の `test_conflict_kinds.py`・`test_fix_accept_all.py` の場合を写す）。
  - `lenses.render` が役の定義の本文から指示書を組む。
  - `lanekit.groups`: 項目を共にする単位は同じ組（推移的）・組の順は入力の順。`lanekit` に `MAX_LANES`・`queue_put`・`take` が無い。
  - `groups.adopt_tree`・`diff_since`: 同じ clone の 2 つの worktree の間で、親の姿の木を子の作業ツリーに写し、子の変更の差分を取り、`docs/plans/2026-10-12-blocks/prereq.md` の issue の `unittrees.apply` で 2 つの組の差分を順に当てる。2 つ目が当たらない時に 1 つ目が残り、2 つ目は当たらないと返る（U8 の git の側の前提）。
- `tests/workflows/test_fix.py`（ブロックの形と script の振る舞いの試験。PyYAML で YAML を読み、script は subprocess で起こす。Archon は起こさない）:
  - 返す節 `fix` が在り `outcome_field: done`。`output_format` の欄がちょうど約束の 10（`done`・`units`・`groups`・`conflicts`・`replan_items`・`objection`・`diff`・`allowed_test_changes`・`changed`・`delta_review`）で、全部 `required`・`additionalProperties: false`。入れ子の形（`units` の項目の 4 つ・`status` の enum 3 つ・`groups` の項目の 4 つ・`changed` の 6 つ・`delta_review` の 2 つ・指し札の 3 つの欄・`conflicts` が null 可）も約束のとおり。
  - `inputs:` に約束の 9 つと `only_items`・`mode`・`group`・`from_tree`・`out_dir`（どれも既定 `""`）が在る。工程の頭に `interactive`・`worktree`・`container`・`evidence_policy`・`mutates_checkout` が無い。
  - 組の並べ: `workflow: works-factory-fix` の節がちょうど 2 つ（`groups-par` に `isolation: worktree` と `fan_out.items`、`groups-seq` に `fan_out.max_parallel: 1` と `isolation` 無し）で、どちらも `when:` で `mode` が `group` の時に届かない。節の id に `-lane-<数>` の形が無い（固定の枝の数を持たない）。`scripts/` の字に語の境の正規表現 `\b(queue|lock)\b|\btake\(` が当たらない（`no-queue`）。
  - 型つきの成果物 `tdd-unit` を出す節が 1 つで、形 `""` の道の上に在る。
  - 読むだけの役（`ruler`・`delta-review`・`review2`・`lens`・`consult-answer`）に `mutates_checkout: false`。役の節の `model:`・`effort:` と `settingSources`・`sandbox`・`context` が今の works の同じ役の節の値と同じ（本文の各節に書いた値と、元の YAML の値の表を試験の中に持つ）。
  - 輪の `max_iterations` が今の works の値（`tdd-loop` 40・`fix-loop` 12・`fix-ruled-loop` 12・`rule-loop` 3・`delta-loop` 3・`refix-loop` 3・`review2-loop` 3・`refix2-loop` 3）。
  - `join`・`tdd-unit`・`collect`・審査の受け付けが前の節の返りを `with:` で束ねない（置き場のファイルを読む）。
  - YAML が名指す `scripts/<名>.py` と、`commands/fix-rules/` の 7 つ・`commands/` の 3 つが全部在る。
  - script の振る舞い（一時の対象のリポジトリと一時の置き場を作り、`ARTIFACTS_DIR`・`WORKFLOW_ID`・`INPUTS_<名>`・`ARCHON_NODE_EXECUTION` を立てて script を起こし、標準出力の JSON を読む）:
    - `prep.py`: 組 2 つで `par: true`、`features_cut` に `fix_lanes` が在れば `par: false`。`only_items` を渡すと、その項目の単位だけの組になる。include の名が `refix` の時は置き場が `fix/refix/` で、`fix/fix/` を上書きしない（案の直しの後の 2 回目の修正）。
    - `join.py`: 2 つの組の結果のファイルと木を置き、両方当たれば `returned: true`。2 つ目が当たらなければ 1 つ目が残り 2 つ目は `returned: false` と理由。結果のファイルが無い組（子が落ちた）は `returned: false`・その組の単位は `not_done`（約束の `groups`・`units` の形で確かめる）。
    - `tdd_unit.py`: 組の結果から 1 つの成果物の本文（下の形）を書く。
    - `collect.py`: 全部の単位が軽量で審査の節が走らなかった置き場で `delta_review` が `{rounds: 0, pass: true}`。`assert-changed` が拒んだ置き場で `done: false`。裁定 `fix_plan_item` が在れば `replan_items` が空でない。異議が在れば `objection` が空でない。返りが約束の `output_format` を通る（PyYAML で読んだ YAML の `output_format` で照らす）。
    - `fix_accept.py`: 修正役の返答を 3 回拒むと、名指しの単位だけを段の頭の木に戻して諦め、ほかは先へ進む。
    - `clean.py`・`assert_changed.py`: `.archon/` の下を数えない・消さない。
    - `collect.py` は落ちない: 壊れた入力（`INPUTS_START` が JSON でない・指し札の先が無い・置き場が空・子の結果のファイルが壊れている）のどれでも、終了の値 0 で、`done: false` と理由を持ち、`output_format` を通る JSON を出す。
    - 筋書き: `tests/archon.py` の使い捨ての木（`workflows/fix` と `.shared/` だけ）で `archon workflow test` を回し、4 本の結末（`group-*` は `completed`、`block-stops-at-fanout` は `groups-seq` で `failed`）を確かめる。源が無ければ名前つきで見送る。

## 返りの約束（`docs/design.md`「ブロックの返りの約束」の `fix` の返りのまま）

- 返す節 `fix`・`outcome_field: done`
- 組ごとの並べ（`fan_out:`）は fix の中に置く。組は `lib/groups`（ファイルは `lib/lanekit.py` ほか元の名と `lib/groups.py`）が単位と計画から作り、返りは組を集めた後の 1 つ。
- 入力（`with:`）:
  - `start` ← `$start.output.record`
  - `baseline` ← `$test-gate-base.output.baseline`
  - `units`・`judgment`・`world` ← `$judge.output.<同じ名>`
  - `plan`・`ripple`・`depth` ← `$plan.output.<同じ名>`
  - `answers` ← `{ from: "$gate-before-fix.output", if_skipped: null }`
- 返り:
  - `done`（boolean）: 直しを作業ツリーに入れ終え、差分の審査を通した。諦めた単位が在っても true → 線 8・report
  - `units`（array）: 単位ごとの結末。項目は `{unit_id, group_id, status, reason}`、status は `fixed`・`given_up`・`not_done` → eyes・report
  - `groups`（array）: 組ごとの結果。項目は `{group_id, unit_ids, returned, reason}`（returned は親の木へ戻せたか）→ report
  - `conflicts`（指し札・null 可）: 申し出と裁定（`lib/conflict` の形）。無ければ null → 線 11・report
  - `replan_items`（array of string）: 裁定が誤りとした計画の項目の id。空でなければ線が案の直しを 1 度差し込む → 線 7・plan
  - `objection`（string）: 修正役の異議。空でなければ線が再審を 1 度差し込む → 線 7・judge
  - `diff`（指し札）: 累積差分（run の始めの版から）→ eyes・merge
  - `allowed_test_changes`（array of string）: 許したテストの変更のパス → 線 11
  - `changed`（object）: review-graph の `p3.fix` の印。`mechanism_changed`・`premise_drift`・`gates_changed`・`seams_changed`・`security_surface_changed`・`path_changed`（どれも boolean）→ eyes（R4・前提の検算）
  - `delta_review`（object）: 差分の審査 `{rounds: integer, pass: boolean}`。軽量で省いた時は `{rounds: 0, pass: true}` → report
- 型つきの成果物: `output_type: tdd-unit`（返りではない。report だけが一覧から読む。E5）。この PR では節 `tdd-unit` が 1 つ出す（形は下）。

- 返す節の `output_format` は、上の欄をちょうど持つ（全部 `required`・`additionalProperties: false`）。欄を足す・名を変える・型を変える・欄を落とすのは線との約束を変えることなので、この PR ではしない。要ると分かったら PR の本文の「約束を変える頼み」に書き、約束どおりの形で作り終える。
- 欄の値の作り方: `done` は `assert-changed` の ok かつ（審査を省いた か 審査が通った）。`units[].status` は子の結果と `join` の結果から（戻せなかった組・落ちた子の組の単位は `not_done`、理由に組の理由）。`conflicts` は置き場の `conflicts.json` の指し札（申し出が無ければ null）。`replan_items` は裁定 `fix_plan_item` の項目の id。`objection` は修正役の返答の欄 `rejudge_requested`（今の works の `blk-fix/rules/direct.md` の 97 行）を集めた文（無ければ `""`）。`allowed_test_changes` は裁定 `fix_test_scope` の `limits` と範囲の相談で許したテストのパス。`changed` は修正役の返答の 6 つの印の論理和。`delta_review.rounds` は走った審査の回数（0〜2）。
- 子の run（`mode: group`）の `fix` の返りも同じ形で、自分の組の行だけを持つ。親は子の返りでなく `out_dir` の結果のファイルを読む（子の指し札は子の run の物で、親では引けない。`docs/design.md` の「Archon の分かっていること」の「指し札は同じ run の中だけ」）。
- 約束に無い入力 `only_items`・`mode`・`group`・`from_tree`・`out_dir` は既定 `""` で宣言し、返りの約束は変えない。PR の本文に「約束に無い入力を 5 つ足した」と書く。

### 直す前の結末（入力 `baseline`）と型つきの成果物 `tdd-unit` の形

- 直す前の結末: `baseline` の指し札の先のファイルは test-gate（base）が書き、fix と test-gate（final）が読む。書くのも読むのも`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/baseline_red.py` の読み書きの口だけを通し、形は `{suite, test_cmd, rev, exit, cases}`（`suite` は始めの記録の `tdd_suite` と同じ実行器のパス。空は実行器の無い run。`cases` は `parse_junit` の形）。fix はこのファイルを自分で開かず、使うのは `cases`・`exit` だけ（実行器は始めの記録の `tdd_suite` から取る）。
- 型つきの成果物 `tdd-unit`: 本文は組ごとの TDD の輪の結果の配列 `[{group_id, ran, reason, suite, reused, units: [...]}]`。`ran`・`reason`・`suite`・`reused`・`units` は今の works の blk-fix の出口の欄 `tdd`（`tddloop.exit_fields`。`works/blk-fix/blk-fix.yaml`:2072-2075 の注釈の形）のまま、`units` の項目は単位の行 `{unit_key, route, why, tests, test_files, red, green, refactor, gave_up, problems, red_quotes, quote_unchecked, stub_files, test_cmd, refactor_why}`。実行器の無い組は `ran: false`・`units: []`。report はこの形を欄の名で読む。

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
- 始めの記録は入力 `start`（指し札）で受け、`boundary.resolve` で開いて JSON で読む。欄の形は `lib/startrec.py` と今の works の `works/blk-entry/schemas/start.schema.json`。無い欄は既定で読む（`tdd_suite`・`test_cmd`・`policy_md`・`request_file` は `""`、`features_cut` は `[]`）。
- 期限: 期限を持つ節（`script:`・`bash:` の `timeout`、`prompt:`・`command:` の `idle_timeout`、`loop:` の `idle_timeout` と `timeout`、`loop_group:` の `timeout`、`approval:` の `idle_timeout`）には全部 `1728000000` を書く（E12）。
- 役の節の `model:`・`effort:` は今の works の `works/.shared/core/stage-models.json` と役の前付け（`works/.shared/core/agents/`）の値を写し、`settingSources`・`sandbox`・`context: fresh` も今の works の同じ役の節から写す（持ち主の決め `model-effort`）。
- 役の指示書（`commands/`）と `lib/` に、対象の言語・テストの実行器の名を書かない（E13）。持ち主の環境の字（`raiki61`・`/Users/` など）を書かない（E14）。
- 外への書き込み（GitHub・対象のリポジトリの main・人に見える所）は、このブロックでは無い。作業ツリーへの書き込みは役 `tdd`・`fixer`・`fix-ruled`・`refix`・`refix2` と script の節 `join`・`clean`・`group-start`（と `tddloop` が単位の頭の木に戻す時）だけ。
- ブロックの YAML と script は、ほかのブロックのフォルダを指さない（E4）。ほかのブロックの返りは `with:` の入力として受けるだけ。落ちうる前の節の返りを `with:` で束ねない（落ちた節への束ねは `if_skipped` が在っても投げる。`dag-executor.ts`:519-534）。集める節は前の節が成功の時に書いたファイルを読む。
- 筋書き（fixture）は Archon の `workflow test` の形（`fixtures/<名>.stubs.yaml`。予約の鍵 `fixture:`（`expect`・`fail-node`・`reached`・`inputs`・`resolved-text-contains`）と `exec-code:`、残りの鍵は節の id → 差し替えの出力）。筋書きが確かめるのは道のつながりだけ。
- ブロックの形と script の振る舞いの試験（`tests/workflows/test_<名>.py`）は PyYAML で YAML を読み、script は subprocess で起こす。筋書きも同じ試験のファイルが回す: issue #47（P0） の `tests/archon.py` が、このブロックのフォルダと `.shared/` だけを `.archon/workflows/works-factory/` に置いた使い捨ての git の木を作り、止めた Archon の源で `archon workflow test` を回す（源が無ければ `skipTest("Archon の源が無い: ...")`）。ほかのブロックの筋書きは回さない。

## Archon で書けない所

- 組ごとの作業ツリー（未決 U8。`docs/polyfills.md` の「候補（まだ埋めでない）: fan_out の子ごとの作業ツリー」）: この PR は `workflow:` + `fan_out:` + `isolation: worktree` で書く。Archon の文書と源で確かめた事: 子ごとに worktree が切られる・子の worktree は canonical の `origin/<baseBranch>` から切られ、親の未 commit も親の commit も見えない・何も merge で戻らない・worktree と枝は子が終わっても残る（`archon isolation cleanup` で消す）・子の工程の名が先祖の run に在れば循環で拒む（`executor.ts`:1291-1306。線の include の中の fix は先祖が `works-factory-line` なので通る）・dry-run は届く `workflow:` の `fan_out:` を落とす（`dry-run.ts`:1221-1256）。だから親の姿は木の sha で渡して子が写し、子の差分は木の sha と `out_dir` のファイルで戻す。実物で確かめる所（PR に結果を書く。形 `""` の通しの証はここだけ）: 使い捨ての親の工程（リポジトリに入れない。`works-factory-fix` を `include:` する 1 節だけの工程を、`tests/archon.py` が作るのと同じ形の使い捨ての木に置く）か、在れば線で、小さな対象のリポジトリ（`tests/e2e/target-seed/` の写し）に組 2 つの直しを回し、(1) 子 `works-factory-fix` が起きるか、(2) 子の worktree が親の run の worktree と git の物を共有し `groups.adopt_tree` で写せるか、(3) 子が親の run の置き場の絶対パスに書けるか、(4) `join` が 2 つの組を当てて `fix` の返りが約束を通るか、(5) 対象のリポジトリに `origin` が無い時に子の worktree が切れるか。どれかが駄目なら、`groups-seq`（親の作業ツリーで 1 つずつ）だけで全部の組が回る形を残し、並べられなかった訳を PR に書く。待ちの列・錠・自前の worktree の管理は作らない（`no-queue`）。新しい埋めが要るなら下の「人が入れる前提の直し」に書く。
- 書き込みの記録（未決 U6）: 今の works は包みが Edit・Write の書き込みを記録した（`record-write.py`）。Archon の YAML の `hooks:` は固定の応答しか返せない（`guides/hooks.md`「Workflow YAML has no executable hook types」）ので、記録は Claude の設定の hook（`bin/` が隔離した設定に置く）でしか取れない。この PR は `record-write.py` を持ってこず、記録が無い時の照らし（版からの変更が全部、返答の申告 `changes[].files` か `bash_writes` に在る。在らなければ拒む）で書き込みの出どころを縛る。記録を取る口は `bin/` の issue（U6）。
- 読んだ証拠（今の works の `reads.py`・`record-read.py`・節 `fix-reads`・`refix-reads`・`review-reads`）: 包みが取っていた。未決 U6 を待ち、この PR では持ってこない（穴。PR の本文に書く）。
- 前の役の会話の続き（持ち主の決め `planner-talk`・`persona`）: 今の works は範囲の相談の答え（`plan-answer`）を修正案を書いた役の会話の続きで、裁定の後の修正役（`fix-ruled`）を修正役の会話の続きで起こした。Archon の `context: {resume: <節>}` は同じ run の上流の節だけを名指し、`loop_group` の体の中では使えない（`guides/authoring-workflows.md` の 270〜300 行）。plan ブロックの節を名指すのは E4 にも当たる。だから `consult-answer` は修正案と波及の指し札を読む新しい会話、`fix-ruled` は修正役の返答と裁定の保存したファイルを読む新しい会話にする。これは狭め（持ち主の決め `no-narrow`）として PR の本文に書き、`persona` の決め「引き継ぎは会話の再開か機械が保存した返答で渡す」と、その当て方「再審は判定役の会話を継ぐ」の両方を引く（会話を継ぐか、保存した返答を読む新しい会話にするかは持ち主が決める所で、この PR は後者で作る）。
- 単位ごとに会話を切る（持ち主の決め `unit-sessions`）: `loop_group` の `fresh_context: false` は周をまたいで会話を続ける。単位が替わる周だけ新しくする口が Archon の文書に無ければ、`fresh_context: true` にして前の周の引き継ぎを `tddloop.handoff_lines`（指示書の引き継ぎの節）で渡す。どちらにしたかを PR に書く。

## E11 の 3 つの答え

1. Archon が持っているか: 組の並べは `workflow:` + `fan_out:` + `isolation: worktree`（自前の枝の数・列・錠は作らない）。輪は `loop_group` と `until_bash`・`max_iterations`。返りの型は `output_format`、TDD の記録は `output_type`。読むだけの役は `mutates_checkout: false`。前の役の会話の継ぎと書き込みの記録は Archon に無い（上の節）。
2. ASF が持っているか: `W/implement/archon-implement.yaml` の `loop:` + `until_field: done` と `assert-changed`（`checkoutStart` と比べる）、`W/deliver/archon-deliver.yaml` の review → `corrections` の輪。ASF は TDD の赤緑の機械の判定・テストの凍結・申し出と裁定・組の並べを持たない（今の works の強み。keep-essence）。
3. 本当に要るか: 能力の棚卸しの fix の 13 行全部と、受け入れの一覧の `p1.worktree_before`・`p1.worktree_after`・`p3.lane_merge`・`p3.fix`・`p3.fix_delta`〜`p3.delta_fix2`。

## commit の順（1 つの PR の中）

1. 波 A（依存の無い物）: `leftovers`・`lens`・`deltamarks`・`rulebook`・`writes`・`unitlanes`・`groups`。試験を先に入れて赤 → 部品で緑。
2. 波 B: `conflict`・`planrange`・`recount`・`planscope`・`planbrief`・`consult`・`parking`・`lanekit`・`refix`・`refixrules`・`lenses`（と要れば `fixboard`）。
3. 波 C: `tddloop`・`fixgates`・`factchecks`・`ruling`・`unitrows`・`fixrules`・`tddlanes`・`fixlanes`（と `tests/layers/scan.py` の 1 行）、と `lib/tests/test_fix_seams.py`。
4. `tests/workflows/test_fix.py`（赤）→ `works-factory-fix.yaml`・`commands/`・`scripts/`（緑）。
5. `fixtures/` と、Archon で `archon workflow test workflows/fix`・`archon validate workflows` を回した結果、U8 の実測の結果。

各 commit に元のパスと版（`2aa7c66c`）を書く。

## 受け入れ

1. 試験を先に入れて赤を見る（lib/ の部品が無い・YAML が無い）。その後で部品と YAML を入れて緑。赤と緑の出力の要約を PR に書く。
2. リポジトリの根からの全部の試験 `uv run --isolated python3 -m unittest discover -s . -t .` が緑。`tests/layers/` の層の試験（その時に在る物全部）も緑のまま。
3. 止めた Archon の源が在る所で `archon workflow test workflows/fix` の筋書き 4 本が全部通る（形 `group` の 3 本は `completed`、`block-stops-at-fanout` は `groups-seq` で `failed`）。`archon validate workflows` に `works-factory-fix` の誤りも警告も無い。筋書きは `tests/workflows/test_fix.py` が `tests/archon.py` の使い捨ての木（`workflows/fix` と `.shared/` だけ）で回し、源が無い所では名前つきで見送る（`skipTest("Archon の源が無い: ...")`）。形 `""` の通し（並べ・`join`・審査・`collect`）は筋書きでは確かめられないので、上の U8 の実測を回して結果を PR に書く（回せなかったら訳と、どこまで回ったか）。
4. 持ってきた lib/ のファイルを元と比べた差分が、lib-port の「移し方」1〜5 で決めた直しと、本文の「盤面に届く能力の扱い」の (a)・(b) だけ。
5. PR の本文に次を並べる（守りのパスの文書に書く代わり。土台の持ち主が `docs/design.md`・`docs/asf-notes.md` に写す）:
   - lib-port の「移し方」6 の 4 つ（元のパス → 置いた先・外した物と理由・言い換えた行・盤面の物を引数で受ける関数の一覧）と、(a) の継ぎ目の行・(b) の書き直しの一覧
   - 採った ASF の型（`docs/asf-notes.md` の「書き方」の 4 行の形）
   - 「能力の棚卸し」と「受け入れの一覧」のこのブロックの行ごとの、証の試験か筋書きの名
   - 狭め: 前の役の会話の続きを、保存した返答を読む新しい会話にした所（`consult-answer`・`fix-ruled`）と、`fix_lanes`・`tdd_lanes` の 2 語を 1 つの並べの切り替えにした所
   - 約束を変える頼み・使いたかった埋め・U6 と U8 の実測の結果
6. ブロックの分（`docs/design.md` の段 2 の fix の行）:
   - 赤緑の機械の判定（`red_check`・緑の確かめ。JUnit XML の failure と、引いた失敗の文の照らし）・元から赤の区別（元で赤だったテストを問わない・版の写しで赤なら外す）・凍結（輪で緑になったテストのファイルを後の修正役が変えたら拒む。裁定 `fix_test_scope` の範囲だけを通す）・範囲の照らしと相談・書き込みの出どころ（申告の無い変更を拒む）・受け付けの時の数え直し・3 回で諦める（その単位を単位の頭の木に戻し、ほかの単位は先へ）・申し出と裁定・差分の審査と手直し 2 往復が、`lib/tests/` か `tests/workflows/test_fix.py` のどれかで縛られている（PR に対応表）。
   - 組は `fan_out:` で並べ、幅は計画の組の数（`$prep.output.groups` の長さ）から run の時に決まり、組は分けない（項目を共にする単位は同じ組）。並べの数の上限（`max_parallel`）は持つが、固定の枝の数・待ちの列・錠は持たない（`tests/workflows/test_fix.py` が縛る）。
   - 戻せなかった組と落ちた子の組は `groups[].returned: false` と理由で返り、その組の単位は `not_done`（`tests/workflows/test_fix.py` の `join.py` の試験）。
   - 全部の単位が軽量なら差分の審査を省き、`delta_review` が `{rounds: 0, pass: true}`（`collect.py` の試験）。
   - 案の直しの後の 2 回目の修正（include `refix`）は `only_items` の項目の単位だけを直し、置き場が 1 回目と分かれる（`prep.py` の試験）。
   - TDD の輪の結果が型つきの成果物 `tdd-unit` 1 つで親の run に出る（`tdd_unit.py` の試験と U8 の実測）。

## 範囲

- 作るのは `workflows/fix/` の下・本文の「lib/ に持ってくる部品」の lib/ のファイル・本文の「試験」のファイルだけ（下の一覧）。
- 触らない（守りのパス。ASF の merge が人の手に残す）: `workflows/line/**`・`workflows/.shared/**`・`docs/design.md`・`docs/owner-decisions.md`・全部の `AGENTS.md`・`pack.json`・`README.md`・`MISSION.md`・`engineering.md`・`.github/**`・`harness/**`・`factory/**`・`.factory/**`。
- 触らない（同じ時に別の run が作る）: ほかの 7 つのブロックのフォルダ（`workflows/<ほかの名>/`）と、それらの issue が名指す lib/・試験のファイル。ほかの PR と同じファイルを作らない。
- 触らない（前に入る物）: lib-port と`docs/plans/2026-10-12-blocks/prereq.md` の issue で入った lib/ のファイル（本文の「依存」に並べた物）とその試験、`tests/workflows/__init__.py`・`tests/archon.py`、`pyproject.toml`、`docs/`（PR の本文に書く。上の受け入れ 5）、`bin/`（書き込みの記録の hook の口は U6）。持ってきた部品の中で前提の部品に直しが要ると分かったら、直さず PR の本文に書く。
- 決めた範囲で能力を落とす直しが要ると分かったら（持ち主の決め `superset`・`no-narrow`）、止めて PR の本文に書く。
- `tests/layers/scan.py` は、`ALLOWED["E13"]` に `"lib/tddloop.py"` と `"lib/fixrules.py"` の 2 つを足す（`tddloop` の `import unittest`・`_CLASS_HOOKS`、`fixrules` の `CODE_SUFFIXES` の拡張子の表と `import unittest` は、`.py` の試験のファイルにだけ効く精度の上げと多くの言語を並べた表で、1 つの言語に縛る物ではない。コードの値なので言い換えない）。`docs/plans/2026-10-12-blocks/prereq.md` の issue の後でこのファイルを変えるのは fix だけで、変えるのは `ALLOWED["E13"]` の行だけ（ほかの行・決まりの関数は変えない）。足すのは人の直し H4（E13 の例外を `lib/impact.py`・`lib/changemap.py`・`lib/tddloop.py`・`lib/fixrules.py`・`lib/libdocs.py`・`lib/libdocs_local.py` の表の値に限って許す）が main に入った後で、入っていなければこの PR は H4 を待つ（E13 の試験が赤になる。値を言い換えて逃げない）。
- このファイル名のどれも、パスの部分が `factory`・`FACTORY`・`harness`・`.factory`・`archon-` で始まらない（E18 の機械の行）。

作る・変えるファイルの一覧（1 行に 1 つ）:

```
workflows/fix/**（works-factory-fix.yaml・commands/fix-rules/common.md・brief.md・direct.md・principles.md・ruler.md・tdd.md・refix.md・commands/delta-review.md・review2.md・lens-silent-failure-hunter.md・scripts/ の本文の 29 本・fixtures/ の本文の 4 本）
lib/conflict.py
lib/planrange.py
lib/recount.py
lib/refix.py
lib/lens.py
lib/leftovers.py
lib/deltamarks.py
lib/rulebook.py
lib/writes.py
lib/tddloop.py
lib/consult.py
lib/factchecks.py
lib/fixgates.py
lib/fixrules.py
lib/parking.py
lib/planbrief.py
lib/planscope.py
lib/ruling.py
lib/unitrows.py
lib/unitlanes.py
lib/lanekit.py
lib/tddlanes.py（残る関数が無ければ置かない）
lib/fixlanes.py（残る関数が無ければ置かない）
lib/lenses.py
lib/refixrules.py
lib/groups.py
lib/fixboard.py（(b) の書き直しが要った時だけ）
lib/tests/test_unitlanes.py
lib/tests/test_lanekit.py
lib/tests/test_writes.py
lib/tests/test_delta_marks.py
lib/tests/test_plan_scope.py
lib/tests/test_plan_brief.py
lib/tests/test_consult.py
lib/tests/test_fix_gates.py
lib/tests/test_fix_rules.py
lib/tests/test_fix_units.py
lib/tests/test_fix_duty.py
lib/tests/test_duty_sets.py
lib/tests/test_conflict_kinds.py
lib/tests/test_fix_precheck.py
lib/tests/test_fix_accept_all.py
lib/tests/test_tdd_frozen.py
lib/tests/test_tdd_frozen_function_span.py
lib/tests/test_tdd_outside.py
lib/tests/test_tdd_lanes.py
lib/tests/test_fix_lanes.py
lib/tests/test_blk_fix.py
lib/tests/test_blk_fix_tdd.py
lib/tests/test_blk_fix_conflict.py
lib/tests/test_blk_lens.py
lib/tests/test_blk_refix.py
lib/tests/test_blk_tests_delta.py
lib/tests/test_fix_seams.py
tests/workflows/test_fix.py
変える（作らない）: tests/layers/scan.py（ALLOWED["E13"] に "lib/tddloop.py"・"lib/fixrules.py" の 2 つ。H4 の後）
```

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

- main に在る物（lib-port の PR）: `lib/promptsection.py`・`lib/marks.py`・`lib/cite.py`・`lib/stopby.py`・`lib/startrec.py`・`lib/gatepolicy.py`・`lib/planmarks.py`・`lib/worldmark.py`・`lib/structmark.py`・`lib/concepthome.py`・`lib/converge.py`・`lib/accept.py`・`lib/gatemarks.py`・`lib/answer.py`・`lib/carry.py`・`lib/webget.py`・`lib/graphloops/engine/`（`util`・`schema`・`pointers`・`render`）、`tests/bin/gitkit.py`・`tests/e2e/target-seed/`、`workflows/.shared/boundary.py`。
- main に在る物（`docs/plans/2026-10-12-blocks/prereq.md` の issue（ブロックの前の共有の部品））: `lib/baseline_red.py`（赤緑の判定 `parse_junit`・`match_case`・`_id_parts`・`_key`・`_must_pass`・`_broken_others`・`red_problems`・`green_problems`、`tddloop` から移った `_failure_attrs`・`run_suite`、直す前の結末のファイルの読み書きの口 `write_baseline`・`read_baseline`）・`lib/impact.py`・`lib/changemap.py`・`lib/tree_run.py`・`lib/unittrees.py`・`lib/holeties.py`・`lib/policy.py`・`lib/protect.py`・`lib/querytest.py`・`lib/libdocs.py`・`lib/libdocs_local.py`・`lib/libdocs_web.py`・`lib/rolekit.py`（`GIVE_UP_AFTER`・`agent_def` ほか盤面に届かない助け）・`lib/REVIEW.md` とそれらの試験、`tests/workflows/__init__.py`。
- main に在る物（issue #47（P0））: 置き場の形（`--workflow-source` の置き場の `.archon/workflows/works-factory/<ブロック>/`。pack `works-factory` の下のブロックのフォルダが packaged workflow になる）・script から lib/ に届く道（未決 U5。`boundary.lib_root()` が環境変数 `WORKS_FACTORY_ROOT` を読む）・`tests/archon.py`（止めた Archon の源と bun を探し、無ければ「Archon の源が無い: …」で見送る。名指したブロックのフォルダと `.shared/` だけの使い捨ての git の木と使い捨ての `ARCHON_HOME`・`WORKS_FACTORY_ROOT` で Archon を回す）・CI が Archon の源と bun を取ってくる事・`archon validate` と変換しない事の層の試験。この PR は `boundary.lib_root()` と `tests/archon.py` を呼ぶだけ。
- Archon は ASF と同じ源から起こす止めた Archon（`docs/design.md` の「語」）で、自分の工程は `--workflow-source` で読ませる（Archon の家に置かない）。組の子の run は、その置き場の pack `works-factory` の下の工程 `works-factory-fix` を `workflow:` で名指す。
- ほかのブロック: 待たない。ほかのブロックの返りは線の `with:` で入力として届くだけで、このブロックの試験はその形の入力を試験の中で作る。直す前の結末のファイルは test-gate が書くが、読み書きは`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/baseline_red.py` の口だけで、test-gate の run とは口でだけつながる。

## 人が入れる前提の直し

本文の「依存」の頭に並べた人の直しは、この issue より前に入る。fix だけの物（この PR は待たない。入るまでは既定値で動く）:

1. 案の直しの後の 2 回目の修正の段。`docs/design.md` の「ブロックの返りの約束」の線の id に、この段が無い。今の works は線 `works/darkfactory/darkfactory.yaml` の 805 行で blk-fix を 2 度目に include し（include の名 refitting）、裁定 `fix_plan_item` で外れた単位を案の直しの後に直していた。fix は `replan_items` を返すが、直された案の項目を直す段が線に無いと、その単位は直されずに終わる（能力が落ちる）。足す文（`docs/design.md` の「ブロックの返りの約束」の「線の中の id」の include の行を次に置き替える）:

   > - include: `test-gate-base`・`judge`・`plan`・`plan-review`・`fix`・`rejudge`（judge の再審）・`replan`・`replan-review`（案の直し）・`refix`（案の直しの後の 2 回目の修正。fix のブロックを 1 度だけ差し込む）・`test-gate-final`・`eyes`・`merge-seal`・`merge-apply`・`report`

   と、「fix の返り」の「入力（`with:`）」の後に次の 2 項を足す:

   > - `refix` の時: `only_items` ← `$fix.output.replan_items`（直す計画の項目の id。fix はその項目に載る単位だけを直す）、`plan`・`ripple`・`depth` ← `$replan.output.<同じ名>`、`answers` ← `{ from: "$gate-replan.output", if_skipped: null }`、ほかは `fix` と同じ。fix は include の名ごとに run の置き場の下の別のフォルダを使うので、`refix` は `fix` の控えを上書きしない。返りは fix と同じ形で、線の節 `fixed` が `fix` と `refix` の返りをまとめて後の段に渡す。
   > - 約束に無い入力（線は渡さない。既定 `""`）: `only_items`（`fix` では空）・`mode`（`""` はブロック、`group` は組ごとの子の run）・`group`（組 1 つの JSON）・`from_tree`（親の作業ツリーの姿の木の sha）・`out_dir`（子が結果を書く、親の run の置き場の中の絶対パス）。fix は組ごとの並べのために自分（pack `works-factory` の `works-factory-fix`）を `workflow:` と `fan_out:` で子の run として起こす（未決 U8）。

   線は自分の節 `fixed` で `fix` と `refix` の返りを 1 つにまとめて後の段（test-gate（final）・eyes・merge・report）に渡すので、report の入力は足さない。
2. U8 の実測で `workflow:` の自分呼び・子の worktree への写しが駄目と分かった時の埋めは、この PR では作らない（`workflows/.shared/` は守りのパス）。PR に結果を書き、土台の持ち主が `docs/polyfills.md` の「候補（まだ埋めでない）: fan_out の子ごとの作業ツリー」の行を埋めの行にするかを決める。
