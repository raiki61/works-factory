<!-- coldwrite:skip ASF の役が読む作業の計画。語は works-factory の docs/design.md の「語」の節で定義 -->
# 前提: 8 つのブロックの前に、2 つ以上のブロックが読む lib/ の部品と、ブロックの試験の置き場と、工程の読み込みの形を入れる

works-factory は、修正依頼を受けて確かめ済みの変更と報告を返す工場を、Archon（AI の工程を YAML で書いて回す道具）の上に作り直しているリポジトリ。前の形の「今の works」（公開リポジトリ raiki61/claude-plugins の `works/`。移す元の版は `pack.json` の `works.commit` = `2aa7c66cf7abe1fe09699ac2942d107123214168`）の能力を、線（`workflows/line/`）・8 つのブロック（`workflows/<名>/`）・助け手（`lib/`。Archon を知らない Python）に移している。8 つのブロック（judge・plan・plan-review・fix・test-gate・eyes・report・merge）は、この後に 1 つずつ別の run で同時に作る。同時に作るので、2 つ以上のブロックが読む部品をどれか 1 つのブロックの PR に置くと、ほかのブロックがその PR を待つか、同じファイルを 2 つの PR が作ることになる。この issue は、それを避けるために共有の物を先に 1 つの PR で入れる。lib-port の計画（`docs/plans/2026-10-12-lib-port.md`）の 3A が「plan-review と report の 2 つのブロックが読むので、ブロックの issue より先に lib に置く」とした形を、残りの共有の部品に当てる。元のファイルは `https://raw.githubusercontent.com/raiki61/claude-plugins/2aa7c66cf7abe1fe09699ac2942d107123214168/<パス>` で読める。

## 読む物

- 根の `AGENTS.md`・`workflows/AGENTS.md`・`lib/AGENTS.md`・`tests/AGENTS.md`・`bin/AGENTS.md`（決まり E1〜E18）。
- `docs/plans/2026-10-12-lib-port.md` の「移し方」1〜6（この issue の 1 の部品は全部この移し方）。
- `docs/design.md` の「語」・「ブロックの返りの約束」・「能力の棚卸し」・「Archon の分かっていること」と未決 U5。
- Archon の振る舞いは止めた Archon（`factory/pack.json` の commit `d97d00ef15cce4b15d39e42635e4e86996ec1351`）の源の `packages/docs-web/src/content/docs/guides/authoring-workflows.md`（packaged workflow の形 `.archon/workflows/<pack>/<workflow>/`）・`guides/script-nodes.md`（「Share code within a pack」「Named Script Resolution」）・`reference/cli.md`（dry-run・`workflow test`・写し取った源 captured source）と `packages/workflows/src/fixture-runner.ts`。

## 作る物

### 1. 2 つ以上のブロックが読む lib/ の部品（lib-port の「移し方」1〜6 のまま）

元 → 置いた先（ファイルの名は元のまま）。どのブロックが読むかを括弧に書く。外す物（盤面・Archon・lib-port が持ってこない部品に届く関数）は移し方 2・3 で機械で出し、PR に並べる。

- `works/.shared/core/impact.py`・`changemap.py` → `lib/`（plan・fix・plan-review の design 経由・eyes。changemap は `bin/_lib/changemap.py` と同じ元だが、lib/ は bin/ を import できない（E3）ので lib/ にも置く。2 つが同じバイトなら、同じであることを縛る試験を 1 本足す。`impact.py`:96 の値 `"archon-plugin.json"`（今の works 自身のプラグインの名。E3 に当たる）は移し方 4 で外し、PR に書く）
- `works/darkfactory/lib/depth.py` → `lib/depth.py`（plan の `decide_doc`、線の `raise_doc`・`run_wide`。`WIRING_FILES = (scopes.MANIFEST,)` は下の「継ぎ目の直し」で値を引数か定数に替える）
- `works/.shared/core/design.py` → `lib/`（plan-review・eyes）
- `works/.shared/core/protect.py`・`protected.json` → `lib/`（eyes・merge・fix）。`protected.json` の行は今の works 自身のパス（`works/...`）で、works-factory には当たる物が無い。元の行を 1 行ずつ、今 main で追跡されている works-factory の同じ役目のファイル（層の試験・境の口・受け付けの口）に読み替え、当たる物が無い行は外す（どちらも元の行との対応を PR に表で書く）。元より広い行（`tests/**` のような）は作らない（元の `test_protect.py`:83 はふつうの試験を守らない）。`workflows/line/**` の行は線の PR が足す。一覧の形と `protect.py` の中身は変えない。元の試験のうち今の works のパス・`dogfood.sh` を決め打つ物（`test_named_guards_are_protected`・`test_copies_are_made_where_named`）は移し方 5 で外し、PR に名を書く
- `works/.shared/core/conceptfence.py` → `lib/`（plan・eyes）。`leftovers.ARCHON_PREFIX` の import は E3 に当たるので、継ぎ目の直しで値を引数で受ける形にする（値はブロックの script が渡す）
- `works/blk-structure/lib/eye.py`・`context.py` → `lib/`、`works/blk-structure/scripts/measure.py`・`stage_a.py`・`stage_b.py` → `lib/`（plan の段 A・eyes の段 B。`stage_a`・`stage_b` の `main`（`ARTIFACTS_DIR`・`INPUTS_*`・script_io を読む所）は外し、ブロックの script が代わる。試験の `test_blk_structure.py` が段 A と段 B を 1 本で持つので、両方をここで入れる）
- `works/blk-plan/lib/planblk.py`・`ripple.py` → `lib/`（plan・plan-review）。planblk が import する `replan`・`planrange`・`writes` は plan・fix の PR が同時に作る物なので、それに届く関数は移し方 2 で外す（この PR は 8 本を待たない）。plan-review が使う planblk・design・policy の関数（下の「plan-review が読む関数」）は、盤面の引数を受けるだけで持ってこない部品に届かない限り残し、届く物は名指しの継ぎ目で残す。`ripple.py`:43 の値 `(".archon",)`（E3）は conceptfence と同じ継ぎ目で、値を引数で受ける形にする（値はブロックの script が渡す）
  plan-review が読む関数（盤面の引数 `b` は plan-review のブロックの中だけの読む見え方が渡す。この PR はそれを作らない）。次を残し、名指しの継ぎ目の直しをする:
  - planblk.tree_part(b, …) — 呼び先 answers_dir（adapter.run_place_of → seam: `pathlib.Path(b.dir)`）・brief_head → _review_rules（rolekit.render_body・BoardGap → seam: `getattr(b, "review_body", "")`）・item_schema/_faces_schema → output_format（accept.role_schema（lib-port で外した）・node_marker.mark → seam: 型は `b.faces_schema` から読む。plan-review の見え方が自分の YAML の役の節の `output_format` から渡す。型の写しのファイルは作らない（持ち主の決め `io-in-output-format`））・role_node（BoardGap → lib の例外）。書く: b.work(ITEMS_DIR) に下請けのファイル。
  - planblk.tree_merge(b, …) — 呼び先 check_item・design_gaps（_names → b.pointer_rows）・precedent_plan・_ripple_of（b.work("ripple/pass-<k>.json")）・synergy_file（answers_dir の seam）。書く: b.trace(SURPLUS_OP)。
  - planblk.check_item・item_answer_gaps・design_gaps・carried_hits・precedent_checks・precedent_plan・save_precedents（b.scope_root に書く）・_tree_off・_opened — 持ってこない部品への届きは answers_dir・output_format 経由だけ。
  - planblk.design_section(b) — b.stop（盤面を止める）・BoardGap → seam: stop の呼び出しを外し BoardGap（lib の例外）を上げるだけ。中で planmarks.review_section（b.dir の plan-fields.json と trace.jsonl の凍結の印）と design_only（design.made・design.missing・design.anchor_note）。
  - planblk.design_only(b) — design.missing（rolekit.given_up_reason → seam: 前提の lib/rolekit.py の同じ名）。
  - design.human_answers(b)（b.record）・named_sections(b, repo)（b.state.inputs.request・b.rules.MD_LINK・_md_lines・_md_slugs）・repo_map(repo)・unusable(b)（b.rules.purpose_unusable）・made・read_design・stands・quote_gaps・anchor_misses・anchor_note・claims_unpassed・claims_given — 持ってこない部品への届きは無し（b.rules は見え方が rules の写しを持つ）。premises(b, repo) は BoardGap を捕まえるので、plan-review は呼ばず 3 つを順に呼ぶ（この PR は `premises` を外してよい）。
  - policy.brief(b)（b.record.process.policy.copy）— 持ってこない部品への届きは無し。import board は engine の sys.path の副作用だけ → seam: carry.py と同じ graphloops の sys.path の行。
  - rolekit: with_reject・rejected・given_up_reason・GIVE_UP_AFTER（受け付けの拒みの積みと諦め）。
  - plan-review が自分で写す（boardview.rules。(b)）: rules/review-loop.py の MD_LINK(:2822)・_md_lines(:2827)・_md_slugs(:2837)・purpose_unusable(:403)・purpose_findings_vetted(:398)・HUMAN_FACE_KINDS(:4084)。
- `works/.shared/core/policy.py`・`holeties.py`・`querytest.py` → `lib/`（plan-review・fix・judge）。`recount.py` は fix の PR が持ってくる（fix の `conflict`・`writes` を import するため）
- `works/.shared/core/libdocs.py`・`libdocs_local.py`・`libdocs_web.py` → `lib/`（plan・fix）。入口の `section(board, …)`（libdocs.py:411）が盤面を受け、盤面は `_cached` → `scopes.all_rounds`（285-305）でしか使わない。`_cached`・`_official`・`section` の盤面の引数を、控えの置き場のパスの引数に替える継ぎ目の直しで残す（外すとライブラリの文書の節が黙って消える）。`libdocs.py`:154 の `SKIP_DIRS`・`libdocs_local.py`:40 の `PY_ENV_GLOBS` の `.tox`・`.nox` は E13 に当たるので、人の直し H4 の例外に入れる
- `works/.shared/core/tree_run.py`・`unittrees.py` → `lib/`（test-gate・fix）。tree_run は lib-port が持ってこない一覧に入れていたが、テストを自分のプロセスグループで走らせ孫まで止める能力（今の works の `blk-tests`）がここにしか無い。持ってこない一覧に入れた訳（`script_io`・置き場の枠・使い回しの控え・`slotwrap.sh` の錠）に当たる関数（`slotted_run`・控えと枠の関数）だけを外す。錠は持ち主の決め `no-queue` によっても持ち込まない。元から在る起こせるかの確かめの上限（`PROOF_TIMEOUT`・`PS_TIMEOUT`・`KILL_GRACE`）は新しく足す期限ではないので元のまま残し、PR に名を並べる（持ち主の決め `no-timeouts` は新しく足さない決め）
- `works/.shared/core/rolekit.py` → `lib/rolekit.py`（受け付けの輪を持つブロックと fix のレンズ）。lib-port は rolekit を持ってこない一覧に入れたが、それは盤面と役の起こし方（包み）の部分の訳で、盤面を知らない出し直しの小道具（`with_done`・`rejected`・`given_up_reason`・`with_reject`・`GIVE_UP_AFTER`、盤面を読まない `parse_reply`）と、役の前付けの本文を引く `agent_def`（fix のレンズ silent-failure-hunter の本文）は judge・plan・plan-review・fix が読む。これらだけを残し、ほかは外す。`agent_def` は engine の `validator.agent_def`・`env_root` を呼ぶので、`works/.shared/core/graphloops/engine/validator.py` を `lib/graphloops/engine/validator.py` に、`agent_def`・`env_root`・`find_plugin_path` とそれだけが使う物を残して持ってくる（lib-port が validator を持ってこない一覧に入れた訳は工程の記録の検証器の部分で、`.rules` の `hook` に届く関数とその import は移し方 2 で外す）。`agent_def` が引く役の前付け（`works/.shared/core/agents/` の silent-failure-hunter ほか）の置き場も合わせて持ってくるかを、元の `rolekit.agent_def` の探し方から決めて PR に書く。`agent_def` の試験（在る役の本文が返る・無い役は None）を足す
- `works/.shared/core/REVIEW.md` → `lib/REVIEW.md`（judge の診断と素材・plan の修正案・plan-review の事前審査・fix の TDD の役・eyes が読む観点の正本。今の works は `{{inputs.review_md}}` でこれらの役に差し込んでいた。データとして置く。`lib/next-request.schema.json` と同じ扱い）
- 試験: 上の部品を確かめる今の works の試験を元の名で `lib/tests/` に置く（`test_impact.py`・`test_depth.py`・`test_protect.py`・`test_concept_change.py`・`test_concept_fences.py`・`test_blk_structure.py`・`test_structure_eye.py`・`test_ripple.py`・`test_policy.py`・`test_holeties.py`・`test_libdocs.py`・`test_libdocs_local.py`・`test_libdocs_web.py`・`test_tree_run.py`・`test_unittrees.py`・`test_rolekit.py`、`test_blk_eyes.py` の design の部分（SectionShapeCase・AnchorCase）、`test_blk_plan.py` の planblk・ripple の部分、querytest を確かめる部分）。lib-port の「移し方」5 のとおり、lib に無い物を使う試験の関数とクラスは外す

### 2. 新しく書く lib/ の部品（今の works に同じファイルが無い能力）

盤面に届く能力を持ってくる時の 2 つの形（8 つのブロックと同じ決まり）:
- 継ぎ目の直し: 持ってきたファイルの中の、盤面・Archon・持ってこない部品への 1 か所の呼び出しを、引数か lib/ の関数の呼び出しに替える。関数の名とほかの行は変えない。直した行を全部 PR に並べる。
- 書き直し: 関数のほとんどが盤面を読む時は、元の関数の名のまま、値かファイルのパスを引数に取る形で新しい lib/ のファイルに書く。ファイルの名は `docs/design.md` の能力の名。各関数の docstring に元の `<パス>:<行>` を書き、元の試験の筋を写した試験を付ける。PR に並べる。

新しく書くのは次の 2 つ（test-gate・fix・merge が読む。どちらも上の「書き直し」の形）。

#### `lib/baseline_red.py`（新）

置く物（元の名のまま字のとおり写す。元は `works/` からのパス、2aa7c66c）:

- `parse_junit(text)` ← `.shared/core/graphloops/rules/review-loop-tdd.py`:41-49（JUnit XML → `[{classname, name, outcome}]`。outcome は passed・failure・error・skipped。読めなければ `ET.ParseError`）
- `_id_parts(test_id)` ← 同:52-57
- `match_case(test_id, cases)` ← 同:60-68
- `_key(c)` ← 同:92-93（`f"{classname}::{name}"`）
- `_must_pass(c, baseline)` ← 同:96-99（元の結末で通っていた物と元に無かった物だけ。元から落ちていた・飛ばされていた物は問わない）
- `_broken_others(cases, baseline, hit)` ← 同:102-104
- `red_problems(named, cases, exit_code, baseline=None)` ← 同:107-129
- `green_problems(named, cases, exit_code, baseline=None, baseline_exit=0)` ← 同:132-147
- `NO_FAILURE`・`_failure_attrs(text)` ← `blk-fix/lib/tddloop.py`:336-351（failure の message と本文。名指しの赤の引用の照らし先）
- `run_suite(exe, repo, work, n, args=(), only=False)` ← `blk-fix/lib/tddloop.py`:296-333 から、`nice -n 19` の頭と控え（`tree_run.slotted_run` の note・`reuse_phrase`・`wait`）を外し、`tree_run.run` で走らせる物（継ぎ目の直し）。`rules().parse_junit` は同じファイルの `parse_junit` に、`_unique` は tddloop:449-452 を写す。`ONLY_ENV = "TDD_SUITE_ONLY"`（tddloop:144）も写す。返り `(cases | None, exit, problems)`。cases の各行は `{classname, name, outcome, fail_message, fail_text}`
- `temp_tree`・`rev_id`・`_base_reds`・`selected_problems` は fix だけが使うので、ここには置かない（fix の PR が `lib/tddloop.py` に元のまま持ってくる）。test-gate が読むのは `parse_junit`・`_key`・`_must_pass`・`_broken_others`・`run_suite`・`write_baseline`・`read_baseline`・`outcomes` だけ。fix は自分の `lib/tddloop.py` から、ここに置いた関数（`parse_junit` ほか review-loop-tdd の物・`_failure_attrs`・`run_suite`）の定義を外し、ここから import する継ぎ目の直しをする
- 元の結末のファイルの口（新しい関数）:
  - `write_baseline(path, *, suite, test_cmd, rev, exit, cases, **extra) -> None`: 必須の欄 `{"suite": str, "test_cmd": str, "rev": str, "exit": int | None, "cases": [{classname, name, outcome, …}]}` を JSON で書く（cases は `parse_junit` の並びの形。`_unique` で同じ鍵は最初の 1 つ）。`extra` は呼び手だけが読む欄で、必須の欄と同じ名なら `ValueError`。test-gate は `by`・`material`・`runs`・`skipped_steps`・`exit_codes`（段の名 → 終了コード）・`junit_steps`（JUnit の報告を宣言して走った段の名の並び）・`fingerprint` を渡す。`suite` は始めの記録の `tdd_suite`（JUnit の実行器）の実行ファイルのパス（無ければ `""`。宣言の段の出どころはここに書かず、test-gate が extra の `junit_steps` に置く）、`test_cmd` は始めの記録の test_cmd、`rev` は書いた時の HEAD の sha、`exit` は cases を取った一式の終了コード（宣言の段から取った時は 0 でない最初の段の終了コード、全部 0 なら 0、走らなければ None）
  - `read_baseline(path) -> dict`: 必須の欄が在り型が合うかを照らして dict を返す（extra の欄もそのまま）。無い・読めない・欄が欠けた・型が違えば `ValueError`（文にパスと欠けた欄）。tddloop の状態の `baseline`（{鍵: outcome}）・`baseline_exit` が要る呼び手は `{_key(c): c["outcome"] for c in cases}`・`exit` で作る（口 `outcomes(cases) -> dict` を置く）
- 試験 `lib/tests/test_baseline_red.py`: 元の試験から写す（`works/tests/test_blk_fix_tdd.py` の parse_junit・red_problems・green_problems・_failure_attrs の場合と、`works/.shared/core/graphloops/` の外の試験で review-loop-tdd の関数を直に呼ぶ場合。在る物を名で並べる）。足す場合: `write_baseline` → `read_baseline` が同じ dict に戻る（extra の欄も）・必須の欄の欠けと型の違いが `ValueError`・extra が必須の欄の名と重なれば `ValueError`・`outcomes` が同じ鍵の最初の 1 つを取る・`_must_pass` が元で failure の物を問わない・元に無い物を問う。`run_suite` は `tests/e2e/target-seed/` の写しで、JUnit を書く小さな実行ファイル（試験の中で作る）を走らせ、書かない時と XML が壊れた時の problems の文。

#### `lib/green_cert.py`（新）

- `fingerprint(repo) -> {"head": str, "diff_hash": str}`: `head` は `git rev-parse --verify HEAD^{commit}`。`diff_hash` は `unittrees.fresh_tree(repo)`（追跡のファイルと .gitignore に当たらない未追跡のファイルの中身・実行ビット・シンボリックリンクの木。本物の index・HEAD は動かさない）と HEAD の木の間の `git diff --binary --no-renames --no-ext-diff HEAD <その木>` のバイトの sha256 の 16 進。差分が無ければ空のバイトの sha256。git の木でない・HEAD が引けなければ `ValueError`。ASF の `W/.shared/validation-evidence.ts`:1-23（HEAD と追跡ファイルの binary の差分）に、未追跡を足した物（修正は新しいファイルを足すので）。.gitignore に当たるファイル（テストが作るキャッシュ）は入らない
- `matches(cert_fingerprint, repo) -> bool`: `cert_fingerprint` が dict で `head`・`diff_hash` が今の `fingerprint(repo)` と同じ時だけ真。None・形の違い・git の誤りは偽（後の段が認証を使う時の口。呼ぶのは merge の apply。eyes は返りの `ok` を読むだけで呼ばない）
- `classify(*, material, runs, cases, baseline_cases, junit_steps, junit_unran) -> (red_cause, summary)`: 事実だけで分ける。引数: `material` は素材 `{status, …}`、`runs` は段ごとの行 `{name, exit, …}`、`cases` は今の 1 件ごとの結末（`parse_junit` の並び）、`baseline_cases` は元の結末の `cases`（呼び手は、元の結末のファイルの `exit` が None の時と、1 件ごとの結末の出どころが無い時（`suite == ""` で `junit_steps` が空）に None を渡す）、`junit_steps` は JUnit の報告を宣言して走った段の名の並び、`junit_unran` はそのうち走らなかった段の名の並び（`declared_checks._junit_unran` が理由を返した段）。順:
  1. status が clean → `("", "")`
  2. 赤の段（runs の exit が 0 でない物）が全部起こせない段（`tree_run.launch_kind(exit) == "broken"`）で、1 つ以上在る → `environment`（今の works の `entry.env_only_red`、`entry.py`:768-772。素材が not_run でもこちらが先）
  3. status が not_run・awaiting_human・not_applicable、または `junit_unran` が空でない → `incomplete`
  4. `baseline_cases` が None でなく、`cases` の落ちた物（failure・error）のうち `baseline_red._must_pass(c, baseline_red.outcomes(baseline_cases))` が真の物が 1 つでも在る → `introduced`
  5. `baseline_cases` が None でなく、落ちた物が 1 つ以上在って全部が元でも落ちていて、赤の段（broken を除く）が全部 `junit_steps` に在る → `inherited`
  6. ほか（JUnit の無い赤の段・shell の test_cmd の赤・`baseline_cases` が None）→ `""`（原因の無い赤）
  `interaction` は返さない（enum にだけ在る。ASF が組の合わせに使う語）。summary は証拠の文（赤の段の名・今回落ちて元で通っていた鍵か元でも落ちていた鍵の頭 10 件・何と比べたか）。原因の無い赤の summary は「1 件ごとの事実が無い」に `gatemarks.BASELINE_UNVERIFIED` を添える
- `certify(*, mode, material_status, green, before, after, now) -> (ok, reason)`（約束の `ok` の字のとおり）:
  - base: material_status が clean・found・not_applicable なら `(True, "")`、not_run・awaiting_human・素材が無いなら `(False, 理由)`（緑を仮定しない）
  - final: `before`・`after`・`now` の指紋が揃わなければ偽（どれが違ったかを reason に）→ green でなければ偽（reason は「緑でない」。原因は呼び手が `red_cause` と証拠で別に返す）→ ほかは真。赤は原因が何でも認証しない（ASF の `W/deliver/scripts/gate-green.ts` は inherited・environment を PR の CI で確かめ直す前提で通すが、works-factory の既定は差分を置くだけで後ろに CI が無い。今の works も最後のテストが緑でなければ最後の関所を開いた）
- 試験 `lib/tests/test_green_cert.py`: 指紋が同じ木で 2 度同じ・追跡のファイルの書き換え・未追跡のファイルの追加・HEAD の移動（commit）で変わる・.gitignore に当たるファイルの追加では変わらない・git の木でなければ `ValueError`。`matches` の None と形の違い。`classify` の 6 つの道と、起こせない段だけの赤は素材が not_run でも environment・introduced と inherited が混じれば introduced・`baseline_cases` が None なら `""`・JUnit の無い赤の段が混じれば inherited にしない。`certify` の順（指紋の食い違いが先・inherited と environment の赤も final は偽・base の awaiting_human は偽・base の found は真）。対象のリポジトリは `tests/e2e/target-seed/` を `tests.bin.gitkit.committed_copy` で写す
- 依存: `lib/unittrees.py`（`docs/plans/2026-10-12-blocks/prereq.md` の issue）・`lib/baseline_red.py`・`lib/tree_run.py`（launch_kind）・`lib/gatemarks.py`（lib-port）

追記（差分の組み方を 1 か所に）: `lib/green_cert.py` に `diff_bytes(repo, rev) -> bytes` を置く。`unittrees.fresh_tree(repo)`（追跡と .gitignore に当たらない未追跡のファイルの木。本物の index と HEAD は動かさない）と `rev` の間の `git diff --binary --no-renames --no-ext-diff <rev> <その木>` のバイト。`fingerprint` の `diff_hash` はこの関数の `HEAD` に対するバイトの sha256 で作り、merge の封印と fix の累積差分も同じ関数を使う（差分の組み方を 3 か所に写さない）。試験に、未追跡のファイルが入る・.gitignore に当たるファイルが入らない・本物の index が動かない、を足す。

### 3. ブロックの試験の置き場

- `tests/workflows/__init__.py`（空）だけを置く。ブロックの YAML の形と筋書きの試験（`tests/workflows/test_<ブロック>.py`）は各ブロックの PR が足し、筋書きはissue #47（P0）の `tests/archon.py` の使い捨ての木に自分のブロックだけを置いて回す。置き場の決まりは人の直し H1 が根の `AGENTS.md` と `tests/AGENTS.md` に書く。
- 工程の読み込みの形（pack の形）・script が lib/ を見つける道（U5。`boundary.lib_root()` が `WORKS_FACTORY_ROOT` を読む）・Archon の要る試験の助け `tests/archon.py`・CI の Archon の源は、issue #47（P0）の issue が持つ。この PR では作らない。

### 4. E4 の機械を pack の形に合わせる

issue #47（P0）の後、Archon が読む所は `.archon/workflows/works-factory/<ブロック>/`（pack `works-factory` の下のブロックのフォルダ）になる。今の E4 の機械（`tests/layers/scan.py` の `_block_paths`）はこの形のほかのブロックへのパスを見落とす。`workflows/AGENTS.md` の E4 の「機械」の行は、人の直しで pack の形（pack の段 `works-factory` は飛ばして見る）に直してある。

- `_pointed_block`（相対パスの `..` の後の最初の名）: `WORKFLOW_FOLDER`（`.archon/workflows`）の頭を飛ばした後に、pack の段（`pack.json` の `ours.pack`。P0 が足す）も飛ばす。今は `../.archon/workflows/works-factory/plan/` の最初の名を `works-factory` と読み、ほかのブロックと見ない。
- 名指しのパスの正規表現（`workflows/(<ほかのブロック>)/`）: `workflows/` と名の間に pack の段 `works-factory/` が挟まる形（`.archon/workflows/works-factory/plan/`）も当てる。
- 試験（`tests/layers/test_block_paths.py` に足す。先に赤）: `workflows/judge/scripts/a.py` の字 `"$SRC/.archon/workflows/works-factory/plan/out.json"` と `"../../.archon/workflows/works-factory/plan/out.json"` が赤・自分のブロック（`.archon/workflows/works-factory/judge/`）を指す字は赤にしない・YAML の直に書いた script の `../works-factory/plan/out.json` が赤。
- 決まりの関数のほかの行と、ほかの決まりは変えない。

## 受け入れ

1. 持ってきた試験と新しい試験を先に入れて赤（モジュールが無い）を見て、置いた後に緑。
2. 根からの `uv run --isolated python3 -m unittest discover -s . -t .` が緑。`tests/layers/` の層の試験（E2・E3・E4・E8・E9・E12・E13・E14・E18 ほか全部）も緑。E13 に当たる `lib/impact.py`・`lib/changemap.py`・`lib/libdocs.py`・`lib/libdocs_local.py` の表の値は、人の直し H4 が入った後に `tests/layers/scan.py` の `ALLOWED["E13"]` に 1 行ずつ足して通す（表を外すと当たる試験の選び・変わった所の地図・手元の文書の探し方が落ちる。持ち主の決め `superset`）。表の外の字（注釈など）は移し方 4 で言い換える。
3. 持ってきたファイルを元と比べた差分が、移し方 1〜5 と 2 の継ぎ目の直しだけ。
4. PR の本文に lib-port の「移し方」6 の 4 つと、継ぎ目の直し・書き直しの一覧。

## 範囲

- 作る・変える: 上の 1〜3 の `lib/`・`lib/tests/` のファイルと `tests/workflows/__init__.py`、`tests/layers/scan.py` の `ALLOWED["E13"]` の 4 行（受け入れ 2）と、4 の E4 の機械の直し（`tests/layers/scan.py` の `_pointed_block` と名指しのパスの正規表現・`tests/layers/test_block_paths.py`）。
- 触らない: `workflows/` の全部（8 つのブロックと線の PR が作る）、`bin/`・`tests/archon.py`・`.github/`（issue #47（P0） が持つ）、`docs/`（直す文は PR の本文に書く）、各 `AGENTS.md`、`pack.json`。
- 8 つのブロックの PR はこの PR の物を読むだけで、作り直さない。

## 依存

- main に在る物: lib-port の PR（issue #30・PR #34）の lib/ の全部（`carry`・`promptsection`・`forge`・`ghreads`・`marks`・`cite`・`stopby`・`startrec`・`gatepolicy`・`webget`・`outpurpose`・`planmarks`・`worldmark`・`structmark`・`concepthome`・`converge`・`accept`・`gatemarks`・`answer`・`graphloops/engine/` の小道具）と `tests/e2e/target-seed/`。
- 先に入る人の直し（守りのパスの文書。中身はリポジトリのそこを読む）: H1（`tests/workflows/` をリポジトリの形の木に載せる。根の `AGENTS.md`・`tests/AGENTS.md`）・H4（E13 の表の例外。根の `AGENTS.md`）。
- issue #47（P0）が main に入ってから始める（P0 も `tests/layers/scan.py` に足すので、同じ時に回すとぶつかる）。8 つのブロックの PR は、この PR が main に入ってから始める。

## E11 の 3 つの答え

1. Archon が持っているか: 持たない。lib/ の部品は Archon に無い確かめの中身（エッセンスの助け手）で、Archon の名を知らない（E3）。
2. ASF が持っているか: 緑の認証（ASF の型 A3。`W/deliver/scripts/gate-green.ts`・`W/.shared/validation-evidence.ts`）だけは型が在り、`green_cert.py` がそれに倣う。ほかの部品の中身は ASF に無い。
3. 本当に要るか: 「能力の棚卸し」の当たる試験の選び・テストのファイルの見分け・守りのパス・構造の目・独立設計・人の方針の文・欠陥の探し方の数え直し・元から赤の区別・緑の認証の行。8 つのブロックの計画がこれらを読む。
