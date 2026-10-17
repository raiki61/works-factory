<!-- coldwrite:skip AI 向けの決まり。語は docs/design.md の「語」のセクションで定義 -->
# グラフ（`workflows/`）の決まり

メイングラフとサブグラフの YAML・役の指示書・ノードの script・境（`.shared/`）を書く時に読む。リポジトリ全体の決まりは根の `AGENTS.md`。

## E1 YAML は変換せずに Archon に渡す

- `workflows/` の YAML は手で書き、`bin/` は写さずに Archon に読ませる（`--workflow-source` に渡す置き場の `.archon/workflows/works-factory` がこのフォルダを指す pack の形。名前の script と `.shared/` は pack の形の時だけ効く。`bin/_lib/place.py`）。Archon は run の始めにその中身をバイトのまま写し取る。生成・前処理・鍵の削りをしない。
- 作りの規則は Archon の `workflow-language-constitution.md`（Archon の源の `.archon/workflow-language-constitution.md`。要点「YAML coordinates. Code computes. Agents judge.」）。YAML はノードの順・承認ノード・ループ・入出力の配線だけを持つ。値の計算は `script:` のノードか役の指示書に置く。
- Archon の確かめ（`archon validate workflows`）が警告なしで通る。数えない警告は 1 つの形だけ: Claude Code に同梱の skill（`tests/archon.py` の `BUILTIN_SKILLS`。`code-review`・`simplify`・`security-review`）と、借りる superpowers の skill（`tests/archon.py` の `BORROWED_SKILLS`。`bin/_lib/borrow/borrow.json` の `superpowers.skills`）をノードの `skills:` に名指した時の「Claude skill '<名>' not found on disk — expected for built-in…」の警告（level が warning・field が `skills`・文がこの形・名が 2 つの一覧のどちらかに在る、の全部が当たる物。照らしは `tests/archon.py` の `counted` の 1 か所）。同梱の skill はディスクに `SKILL.md` が無く、借りる skill は起動の時に run の隔離した設定へ入るので確かめの使い捨ての木には無い。止めた Archon の `packages/workflows/src/validator.ts` 698-768 行は名指すたびにこの警告を出す。一方で止めた Archon はノードの `skills:` に名指した skill しか役に渡さない（`packages/providers/src/claude/provider.ts` 631 行）ので、名指さないと judge の局所レビューの役がレンズを起こせない。2 つの一覧に無い名の警告と、同梱の名でも別の置き場に入っていて届かない時の誤り（installed elsewhere）は今までどおり数える。`validate` は `--workflow-source` を受けず黙って捨て、`--cwd` は git の木しか受けないので、`.archon/workflows/works-factory/` にグラフのフォルダと `.shared/` を写した使い捨ての git の木（`tests/archon.py`）を `--cwd` に渡す。
- 機械: `tests/layers/test_no_conversion.py`（Archon が読む所と `workflows/` のバイト一致）・`tests/layers/test_archon_validate.py`（確かめの結果に誤りも警告も無い。上の同梱の skill と借りる skill の警告だけは `tests/archon.py` の `counted` で数えない。種 `tests/layers/seeds/e1/workflows/skills/` で、一覧に無い名の警告と installed elsewhere の誤りが数えられることを縛る）。

## E2 境の中身は全部、名簿に載せる

- `workflows/.shared/` のファイルは 2 種類だけ。Archon との出入りの口（境の入出力のモジュール。1 つ）と、埋め（polyfill。Archon に無い物を外から補う部品）。`bin/_lib/` には埋めと入口の部品（`bin/AGENTS.md` の E15）が並ぶので、埋めでない入口の部品は `tests/layers/scan.py` の `ALLOWED["E2"]` に 1 行ずつ置いて外す。
- 埋めは `docs/polyfills.md` に 1 行ずつ載せる。載せる欄は、穴・Archon の証拠の引用・外す条件。YAML の型の埋め（メイングラフの受け皿のノードなど）や、期限の値のような置き場を持たない埋めも載せる。
- 機械: `tests/layers/test_polyfills_listed.py`（`workflows/.shared/` と `bin/_lib/` のファイルが、境の口・`ALLOWED["E2"]` の行・名簿の `- 埋め:` の行の頭の欄が名指す物のどれかに当たる。行の説明の文にだけ名が出る部品は数えない。木に在るかの照らしは頭の欄に限らず行の全部のパスに掛かり、名簿の `- 埋め:` の行が名指す `workflows/`・`bin/`・`lib/`・`tests/` の下のパスが木に無い行も赤。ただし置き場のパスの直後に「（予定）」と書いた行は、木に無くてよい）。

## E4 サブグラフはほかのサブグラフのファイルを指さず、入力の説明で作り手を名指さない

- サブグラフ（`workflows/<名>/`）の script は、ほかのサブグラフのフォルダへのパスを組まない。受け取りは `with:` の入力・前のノードの出力・ポインタ（`archon_artifact`）・型つきの成果物（`output_type`）だけ。
- サブグラフの script は `lib/` と境の口を呼ぶだけで、確かめの中身を持たない。
- グラフ（`workflows/` の script・境・YAML に直に書いた script）は `bin/` の物を import しない。Archon の上で動く物は、Archon の外の起動の殻に頼らない。殻の事実（Archon の起こし方など）が要る時は、殻が組んだ物を env で渡し、その名は読む側の埋めが持つ（殻は `bin/_lib/place.py` の `shared` で埋めを読んで名を取る。`workflows/.shared/childsweep.py` の `CLI_ENV`）。
- script は同じ `scripts/` の別の script を import しない（共に使う物は lib か境の口に置く）。script の名を lib のモジュールの名にしない（script のフォルダが `sys.path` の頭に来るので、`import <名>` が lib の物でなく script を読む）。
- サブグラフの `inputs:` の `description:` は受け取る値の形（型・意味・空や null の時の意味・ポインタなら先のファイルの名）を書き、作り手（ほかのサブグラフ・メイングラフ・周の鎖のノード）を名指さない。結びはメイングラフの `with:` だけが持ち、説明に写すとずれる（持ち主の決め `io-in-output-format`）。そのサブグラフ自身の YAML の兄弟ノードの `$<id>.output` は作り手の名指しに数えない。
- 機械: `tests/layers/test_block_paths.py`（サブグラフの `inputs:` の `description:`（YAML の値として読むので、flow の形も `>-`・`|` の複数行の形も覆う）に、作り手の名指しが無い。名指しは 4 つの型: `$<id>.output`（自分の YAML のノードの id は除く）・語「メイングラフ」・ほかのサブグラフの名（`works-factory-` の頭が付いてもよい）・一番上のグラフ（メイングラフと周の鎖）のノードの id のうち `-` を含む物。`-` の無い id は普通の語と重なるので語としては数えない。一番上のグラフ自身の入力は見ない。サブグラフの `scripts/` とサブグラフの YAML（直に書いた script）の字に、ほかのサブグラフを指すパス（`workflows/<名>/`・Archon が読む所の `.archon/workflows/works-factory/<名>/`（pack の形。pack の段 `works-factory` は飛ばして見る）・`../<名>/`）が無い。`scripts/` の字には `lib/`・`workflows/.shared/`・自分のサブグラフの外への相対パスも無い。`scripts/*.py` の import の名が同じ `scripts/` の別のファイルの名でない。メイングラフとサブグラフの `scripts/*.py` の名と `lib/*.py` の名が重ならない。`workflows/` の `.py`・`.yaml` に `bin` の import の行が無い）。

## E5 サブグラフの出力は 1 つのノードの構造体

- サブグラフの YAML は `returns:` で 1 つのノードを名指す。サブグラフの間で渡す物の型の正本は、そのノードの `output_format`（素の JSON Schema）と、メイングラフの `with:` だけ。写しの型は持たない（持ち主の決め `io-in-output-format`）。
- 大きい中身はファイルに置き、出力にはポインタ `{type: archon_artifact, run_id, path}` を入れる。
- サブグラフの間は `with:` と出力の構造体だけで渡す。飛ばされうる段の出力は、受ける側の `with:` に `{ from: "$<id>.output.<欄>", if_skipped: null }` を書く（ASF の `W/ship/archon-ship.yaml`:148）。出力をまるごとで受ける時は、script のノードの `with:` に `{ from: "$<id>.output", if_skipped: null }`（飛ばされない段は字のまま `"$<id>.output"`）を書き、script は読む欄を `boundary.picked(os.environ.get("INPUTS_<鍵>"), <欄の名の並び>)` で名指して読む（欄の名の並びはモジュールの頭の字の tuple か lib の部品の定数。受け皿は運ぶ欄の名を YAML の `with:` の `names:` に空白区切りで宣言し、`boundary.picked(env.get("INPUTS_GOT"), boundary.text(env.get("INPUTS_NAMES")).split())` で受ける。口は宣言した欄しか持たず、宣言の外の名を読むと KeyError で止まる）。受け手が include の時は、メイングラフの中継のノード（`script:` のノード）で受けてから渡す（埋め P2。Archon は include の `with:` に書いた束ねを黙って JSON の値として渡すので、書けたように見えて効かない）。並べた物の集まりは `fan_out:` の出力（入力の順の配列）で受ける。
- 型つきの成果物の一覧（`$TYPED_ARTIFACTS_FILE`）を読むのは report サブグラフだけ。ループの出力は最後の 1 周しか残らないので、全部の周の記録（試験の関門の認証・認めた元からの赤・範囲の外の所見）を拾うのに使う（ASF の `W/.shared/report.ts`:130-140 と同じ）。引く時は include の頭（`<include の id>__`）と `loopGroupPath` で自分の分だけに絞り、一覧の `errors` を捨てない（読めた分と一緒に返す）。読む部品は report サブグラフの中に置く。
- 仕事の結末を表す欄は `outcome_field:` で名指す。run が終わったことと仕事がうまくいったことは別の事実。
- サブグラフの `inputs:` の入力は、どれもサブグラフの中に読み手（script の `INPUTS_<名>` か、役の指示書（`commands/` と YAML の `prompt:`）の `$INPUTS.<名>`）を持つ。YAML の `with:` で script へ渡すだけの字は読み手でない。逆向きに、script が `INPUTS_{…}` を組んで回す lib の部品の名の並び（`fixboard.PREP_INPUTS` の形）の名は、どれもサブグラフの `inputs:` に在る（宣言の無い名は Archon が渡さず、script は空の字を黙って読む）。ループ（`loop_group`）の中の AI ノードは自分の `with:` を結ばない。前の周の値はループの頭の script のノードが `$LOOP_PREV` で結んで返し、役はその出力を読む（Archon は include の時に役の `with:` を既定の字で固める。PR #100）。
- 機械: `tests/layers/test_block_returns.py`（全サブグラフに `returns:` と `outcome_field:` が在り、出力ノードが `output_format` を持ち、`outcome_field` の欄がその `required` に在る。出力の欄のどれも、メイングラフの `$<include の id>.output.<欄>`（入れ子の道 `.<欄>.<…>` は頭の欄）にも、まるごとの参照 `$<include の id>.output` を受ける script の口 `boundary.picked` の宣言した名にも無ければ赤（出力の欄 ⊆ 読みの和）。読み手の無い入力（今の物は `ALLOWED["E5"]` に名指し、区分の issue で外す）と、`inputs:` に無い名を回す lib の名の並びと、ループの中で `with:` を結ぶ AI ノードも赤）。メイングラフが欄つきの参照で読む欄が出力ノードの `output_format` に在るかは Archon の `validate`（`tests/layers/test_archon_validate.py`。E1）が照らす。validate はまるごとの参照の読む欄を見られないので、そこは E5 が照らし、次も赤にする: 宣言した名が `output_format` に無い（宣言した名 ⊆ 出力の欄）、口の名の並びが読める 3 つの形（module の頭で 1 度だけ置く字の tuple の名・lib の部品の字の tuple の定数 `<部品>.<定数>`・ノードの `with:` の `names:` の字を読む上の形）の外（解かずに赤）、口が 1 つの呼びでない・口の 1 つ目の引数が `os.environ.get("INPUTS_<鍵>")` か `os.environ["INPUTS_<鍵>"]` そのものでない（まるごとの値を別の名に取っておけない）・`INPUTS_<鍵>` の字が口の呼びの外に在る、script の `with:` の外のまるごとの参照（受けてよい置き場は script のノードの `with:<鍵>` の直の字か `with:<鍵>.from` の字だけで、ほかは置き場を並べずに全部赤）。宣言の外の欄は口が値として返さない。まるごとの参照を受ける script は環境変数を字のままの鍵（`os.environ.get("<字>")`・`os.environ["<字>"]`・`os.getenv("<字>")`）でだけ読み、名を組んで読む・回す・写す・ほかの名へ渡す読みは、値の流れを解かずに形で赤にする。

## E6 外への書き込みは 1 つの script のノードで、書いた後に読み戻す

- GitHub・対象のリポジトリの main・人に見える所への書き込みは、サブグラフごとに 1 つの `script:` のノードだけが行う。書いた後に読み戻し、読めた値で返る。終了の値 0 は書けた証拠にしない。
- 機械: `tests/layers/test_outward_write.py`（`gh`・`git push`・`git merge` を呼ぶノードがサブグラフに 1 つ以下。名簿は試験の中の表）。読み戻しの有無は人が見る。

## E7 読むだけのノードは mutates_checkout: false を書く

- 作業ツリーを変えないノード（読むだけの役と、読むだけの script）は `mutates_checkout: false` を書く。script・bash のノードは全部書き、外れは作業ツリーを変えるノード（`tests/layers/scan.py` の表 `CHANGE_CHECKOUT`。訳つき）だけ。Archon は書いたノードが作業ツリーを変えたら、そのノードを落とす。AI ノード（`prompt:`・`command:`）の印は道具から決まる: `allowed_tools` に Bash・Edit・Write が無い役は書き、在る役は書かない（今の works の `works/tests/test_yaml_rules.py` と同じ）。Bash を持つ読む役（judge の素材集めの役など）は、今の works と同じく受け付けの script が作業ツリーの姿を比べ、変えた返答を拒む。外れは変える道具を持つが作業ツリーを変えない役（`tests/layers/scan.py` の表 `KEEP_CHECKOUT`。訳つき）だけ。Bash を持ち Edit・Write を持たない役は `sandbox.filesystem.denyWrite` に `~/../archon-home`（`scan.py` の `NO_TREE_WRITE`。起動が隔離した HOME の隣の Archon の家）を書き、作業ツリーへの書き込みそのものを止める（`'.'` は cwd を塞がない。実測 2026-10-13。issue #293）。この値は包み（`workflows/.shared/fence.py`。埋め P5）の印も兼ね、包みは起こす直前に cwd・共通の `.git`・全部の worktree の根などを `denyWrite` に足す（issue #309）。
- `loop:` のノードを作らない（Archon は `loop:` のノードの `mutates_checkout` を無視して警告を出す。止めた Archon の `packages/workflows/src/schemas/dag-node.ts` 1025-1030 行）。読むだけの役の繰り返しは `loop_group` で書く。
- AI ノードは `settingSources: [user]`・閉じた `sandbox`（`enabled: true`・`allowUnsandboxedCommands: false`）・道具の表（`scan.py` の `ROLE_TOOLS`）の中の `allowed_tools` を持つ（今の works の `works/tests/test_yaml_rules.py` の決まり）。
- 役の `model` は群の名（`lib/launchgroups.py` の `GROUPS` の `'@wf-<群>'`）を書き、`effort` を書かない。グラフの根にも `effort`・`modelReasoningEffort` を書かない。止めた Archon はノードの `effort` を別名の `effort` より先に採り、グラフの根の `effort` は `effort` の無いノードへ写る（`include-expander.ts`・`loader.ts`）ので、どちらも run ごとの `--model @wf-<群>=…` の付け替えを黙って効かなくする。
- 機械: `tests/layers/test_readonly_nodes.py`（全部のサブグラフとメイングラフの AI ノードの印が道具に合う。script・bash のノードは表 `CHANGE_CHECKOUT` の外の全部に在り、表のノードには無い。`loop:` のノードが無い。AI ノードが上の 3 つの鍵を持つ。役の `model` が `GROUPS` の群の名で、役にもグラフの根にも `effort`・`modelReasoningEffort` が無いこと（`test_role_model_names_a_group_without_effort`）。Bash を持つ読むだけの役の denyWrite に `NO_TREE_WRITE` が在り `'.'` が無いこと（`test_bash_reader_without_no_tree_write_is_red`）。値は `isolate.DIRS` の置き場の名から引き、`isolate()` が組む HOME から解くと隔離した Archon の家を指すことは `test_no_tree_write_names_the_isolated_archon_home`。包みがこの値を印と読み、一覧を足すことは `tests/shared/test_fence.py`。違反の見本は `tests/layers/seeds/e7`・`k18-*`・`k3-*` に 1 本 1 違反）。
- `runtime: uv` の script は頭に uv の script の宣言（PEP 723 の 4 行 `# /// script`・`# requires-python = ">=3.12"`・`# dependencies = []`・`# ///`）を置く。Archon は script のノードを対象の作業ツリーを cwd にして `uv run <ファイル>` で起こすので、宣言が無いと対象に `pyproject.toml` が在る時に uv が作業ツリーに `.venv`・`uv.lock` を作り、読むだけのノードが落ちる（issue #92）。機械: `tests/workflows/test_uv_scripts.py`（`workflows/*/scripts/` から Archon と同じく 1 段下のフォルダまでの `.py` の頭の 4 行・YAML の `script:` の名が全部その中のファイルに当たり、直に書いた `script:` が無いこと・`pyproject.toml` の在る種で走らせても作業ツリーが変わらないこと）。

## E12 期限・タイムアウトを置かない

- YAML のノードにも script にも期限を置かない。止める時は止め札で止める。持ち主の決め `no-timeouts`。
- Archon は鍵を書かないノードにも既定の期限を当てる（`script:` のノードは 2 分で打ち切る。Archon の文書 `packages/docs-web/src/content/docs/guides/script-nodes.md` の `timeout`「Default: `120000` (2 min)」）。だから期限を外すには、期限を持つノードに実質無しの値 `1728000000`（ミリ秒で 20 日。今の works と同じ値。埋め P9）を書く。期限を持つノードと鍵は次のとおり（止めた Archon（`docs/design.md` の「語」）の `packages/workflows/src/schemas/dag-node.ts`・`dag-executor.ts` で確かめた）。
  - `script:`・`bash:` の `timeout`
  - `prompt:`・`command:` の `idle_timeout`
  - `loop:` の `idle_timeout`（1 周ごと）と `timeout`（`until_bash` の確かめ。無いと 120000 ms で打ち切る）
  - `loop_group:` の `timeout`（`until_bash` の確かめ）
  - `approval:` の `idle_timeout`（`on_reject` の直しの役が受け継ぐ。承認ノードは `approval:` で書かない（E16））
  - `wait:` の中の `deadline_ms`（`event` を待つ時）。`attention` の待ち（承認ノード）は期限を持たない（Archon の文書 `guides/authoring-workflows.md` の「An attention wait has no deadline」）
  - `cancel:`・`include:`・`workflow:` は期限を持たない（`include:`・`workflow:` の先のノードは自分の鍵を持つ）
- 機械: `tests/layers/test_no_timeouts.py`（`workflows/` の YAML のノードが全部上の種類のどれかで（知らない種類は赤）、期限を持つノードに上の鍵が在り、`timeout`・`idle_timeout`・`deadline_ms` が全部 `1728000000`）。

## E16 承認ノードと並べは最新の ASF の形で書く

- 承認ノード: `wait:` の `attention`（見せる文）を `form: select` で書き、選び肢を `options` に並べる。後ろのノードはその答え `{decision, text}` を `{ from: "$<承認ノード>.output", if_skipped: null }` で受ける（ASF の `d97d00ef` の `W/merge-queue/archon-merge-queue.yaml`:8・179-225 の形を、止めた Archon 355f1867 が非推奨にした `approval:` から書き換えた物）。持ち主の決め `asf-way-gates-fanout`。
- `approval:` と、グラフの頭の `interactive:` は書かない。止めた Archon は読み込みで非推奨の警告を出し（`packages/workflows/src/loader.ts` の `LEGACY_PAUSE_REPLACEMENTS` と「workflow-level 'interactive:' is deprecated and has no effect」）、`interactive:` は効かない。
- 筋書き（`fixtures/*.stubs.yaml`）が承認ノードを通る時は、その承認ノードの答えを stub に書く（`<承認ノード>: {decision: approve, text: ''}`）。止めた Archon の dry-run は、答えの stub の無い `wait:` で止まる（`packages/workflows/src/dry-run.ts`）。
- 並べ: `fan_out:`（`items`・`as`・`max_parallel`・`join`）で書く（ASF の `d97d00ef` の `W/verify-runtime-suite/archon-verify-runtime-suite.yaml`:27-34）。作業ツリーに書く並べ（fix の組）は、組ごとに子の run を起こして作業ツリーを分ける。子の run が自分の作業ツリーを持つかは段 1 で実測する（`docs/design.md` の U8）。待ちの列・固定の枝の数・錠は持たない（持ち主の決め `no-queue`）。
- どの承認ノードも `options` に答えの語（`lib/answer.py` の `GO_WORDS`・`STOP_WORDS`。`STOP_WORDS` は `REJECT` を含む）を全部持つ（止めた Archon は `options` に無い答えを拒み、run は承認ノードで止まったまま。`workflow respond <run> continue|stop|approve|reject` と `workflow approve`・`reject` は、どれも `{decision, text}` を返して run を続ける。実測 2026-10-16）。ループ（`loop_group`）の本体に承認ノードを置かない（本体が承認ノードで終わるループの再開は会話を引き継がない。今の works の `works/tests/test_yaml_rules.py` 43-45 行）。
- 機械: `tests/layers/test_gates.py`（全グラフの承認ノードが `wait:` の `attention` で `form: select` を持ち、`options` に `lib/answer.py` の答えの語を全部持つ。`approval:` のノードが無い。ループの本体に承認ノードが無い。どのグラフも頭に `interactive` を書かない。include されるサブグラフはグラフの頭に `worktree`・`container`・`evidence_policy`・`mutates_checkout` を書かない（一番上のグラフ（メイングラフ・周の鎖）は書いてよい））。筋書きの stub は `workflow test` が照らす（答えの stub の無い承認ノードで止まると赤）。並べの形は人が見る。

## E17 対象のリポジトリには差分を置くだけ

- merge サブグラフの既定は、封じた差分を run の置き場に置くだけ。対象のリポジトリに当てるのは人で、`bin/apply` が封じた hash を照らしてから当てる。PR を作る・merge する動きは、使う人が選んだ時だけ働く道にする。対象のリポジトリごとにレビューと merge の決まりと権限が違うため（持ち主の決め `diff-only-to-target`・`others-may-use`）。
- ASF が PR を merge するのは、ASF がこのリポジトリ（works-factory）を作る時だけ。
- 人が見る。

## E19 AI ノードの出し直しは Archon の retry で持つ

- AI ノード（`prompt:`・`command:`。`loop_group` の本体の中も）は `retry: {max_attempts: 2, on_error: all}` を持つ（eyes と同じ形）。構造化出力の一過性の失敗 1 つで run 全体が落ちないため。工場の側に自前の出し直しを作らない。回数と、どの失敗で出し直すか（`on_error`）は Archon の機能で、工場はどのノードに付けるかと外す理由だけを持つ。
- 止めた Archon は、`retry` を書かない AI ノードにも既定の出し直しを当てるが、`on_error: transient` なので、種類が `unknown` の失敗は出し直さない（`packages/workflows/src/dag-executor.ts` の `getEffectiveNodeRetryConfig`・`retryableFailureClass`）。だから `on_error: all` を書く。`loop_group` のノードそのものには書かない（`packages/workflows/src/schemas/dag-node.ts` 1687-1693 行が誤りにする）。本体の AI ノードに書けば、本体の中でも出し直す。
- 2 回走ると困るノード（外への書き込みを持つ物など）だけ外し、ノードの頭の行の真上に `# retry なし: <理由>` を 1 行で書く。
- 機械: `tests/layers/test_role_retry.py`（全部のグラフの AI ノードが `retry` をこの形（`scan.py` の `ROLE_RETRY`）で持つか、真上に理由の在る外しの行を持つ。両方在るのも赤。照らしは `tests/layers/scan.py` の `_role_retry`）。

## E20 深さの段は表 1 か所に置き、when の句で飛ばさない

- run の頭の深さ（judge の `depth`）の段（軽量・標準・重厚）の定義は `lib/depth.py` の `TIERS` 1 か所。`docs/design.md` の「深さの段の表」（段・省く物・足す物・理由の 4 欄）はその写しで、行は `TIERS` と等しくなければならない。深さの語・段が省く物・重厚が足す機能・報告の行はどれも `TIERS` から引き、字を写さない。持ち主の決め `depth-by-reason`。
- ノードを深さの値で飛ばさない: どのノードの `when` も、出力の深さの欄を読む句（`$<ノード>.output.<名に depth を含む欄>`）を持たない。計画の壁打ち（plan と plan-review の往復）はどの段でも省かない。段の足しは、機能の切り替えの式（`lib/entry.py` の `feature_words`・`switch` の `adds`）を通して効かせる。
- 機械: `tests/layers/test_depth_skip.py`（どのノード〔メイングラフ・サブグラフの頭の段・ループの中〕の `when` も深さの欄を読む句を持たない・表の行が `depth.TIERS` と等しい。照らしは `tests/layers/scan.py` の `_depth_when`）。
