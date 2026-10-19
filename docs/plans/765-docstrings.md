# #765 組み込み: 決まりの文から試験の docstring へ移す細目（組み立ての陣が当てる）

- 読む人と頼み: 組み立ての陣。入れ替えの後に、下の各節の字を、見出しの試験のファイルの頭の docstring に当てる。ほかの読み手は、決まりの「機械」の行の細目を探す時に読む。
- 陣: #765 の組み込みを分けて進める作業の組。この文書を書いた文書の陣（文書だけを直す）・削除と試験の陣（古い物を消し、試験を直す）・組み立ての陣（入れ替え `git mv blocks workflows` を当てる）。
- 何の話か: 根の `AGENTS.md` と `workflows/AGENTS.md`（作り直しの間は `blocks/AGENTS.md`）を「憲法 6 行（`docs/design/README.md` の 2 節）と決まりとパス」に縮めた（`docs/design/README.md` の 11.3 の 6・持ち主の決め `rules-tests-design-apart`）。決まりの「機械」の行に在った試験の細目は、その試験のモジュールの docstring に置く。文書の陣は `tests/` を持たないので、ここに試験のファイルごとの docstring の案を書く。組み立ての陣が、入れ替え（`git mv blocks workflows`）の後に各ファイルの頭の docstring をこの字に替える。
- 決まりの番号は変えていない（E1〜E22。置き場は根の `AGENTS.md` の表）。番号を引く試験と文書は直さなくてよい。決まりの置き場が `workflows/AGENTS.md` の物は、入れ替えの後のパスで書いた。
- 下の各節の見出しがファイルのパス、本文が docstring の全文（字下げの無い段落と箇条）。試験のコードが案と違う振る舞いをしていれば、コードを正にして案を直す（案は今の決まりの文と、削除と試験の陣の枝の試験を読んで書いた）。
- 載せない試験: docstring が既に細目を持ち、決まりの文から移す物が無い試験（`tests/layers/test_block_shape.py` の 7.1 の箇条・`tests/layers/test_keep_essence.py`・`tests/layers/test_polyfill_evidence.py`・`tests/layers/test_block_loop_sessions.py`）。これらは頭の行の「決まりの置き場」だけ合っているかを見る（`test_block_shape.py` の頭の `blocks/` は `workflows/` に替える）。

## tests/layers/test_layout.py

根の直下のファイルとフォルダが、根の `AGENTS.md` の「リポジトリの形」の木に在る物だけ（根の `AGENTS.md` の機械の行）。

- 木の名は AGENTS.md から読み、ここに写さない。木は「リポジトリの形」の ```text の中の行で、1 行は `├── 名   説明` の形。名の欄（`├── ` などの線の後から、2 つ以上の空白の前まで）は `・` で並べてよく、`/` より後は根の直下の名に関わらない。根の直下の段（字下げの 1 段目）の名の欄が空白を含む行（例 `ASF の取り付け命令が置いた物`）は、名でなく組の見出しで、その下の 1 段（字下げの 2 段目）の名を根の直下の名に数える。木の根の直下の名は 1 度だけ。
- `workflows/` の直下は、`works-factory-<名>.yaml` を持つフォルダ（block と graph）・`.shared/`・`AGENTS.md` だけ。直下のフォルダが自分の名の YAML を持たなければ赤（block の名の表は持たない。持ち主の決め `shape-checks-only`）。
- 試験を置くフォルダ（`test_*.py` の在るフォルダとその上の全部）に `__init__.py` が在る（無いと Python 3.12 の unittest は黙って見つけない）。小さな対象のリポジトリの種 `tests/e2e/target-seed/` には置かない。
- 見るファイルは git が知る物と、まだ add していないが無視されない物（`.venv`・`__pycache__` など無視の物は見ない）。

## tests/layers/test_no_asf.py

`workflows/` の YAML の `include:`・`workflow:` の値が `works-factory-` で始まる（根の `AGENTS.md` の E8 の機械の行）。

- 外しは 1 つだけ: merge の `pr-open` が出口の語 `pr`（依頼の入力 `deliver` の値。`pr` の時だけ PR を作る）の時に起こす Archon 同梱の `archon-pr`（表 `tests/layers/scan.py` の `ARCHON_CALLS`。持ち主の決め `deliver-via-archon-pr`）。
- ASF のコードを写していないことと、`docs/asf-notes.md` の行は人が見る。

## tests/layers/test_names.py

グラフの名が `works-factory-<フォルダの名>` で、`archon-` で始まらない（根の `AGENTS.md` の E9 の機械の行）。自分の層のパスの部分が ASF の物の名で始まらない（E18 の機械の行）。

- E9: `workflows/<名>/works-factory-<名>.yaml` の `name:` がフォルダの名と同じ `works-factory-<名>`。
- E18: `bin/`・`workflows/`・`lib/`・`tests/`・`docs/` の下のパスの部分（フォルダとファイルの名）に、`factory`・`FACTORY`・`harness`・`.factory`・`archon-` で始まる物が無い（持ち主の決め `name-by-origin`）。ASF の物が根の `AGENTS.md` の木の場所の外に無いことは人が見る。

## tests/layers/test_lang_neutral.py

AI のノードへの指示の md（`workflows/*/prompts/`・`workflows/.shared/prompts/`）と `lib/` に、言語と実行器の名の語の表に当たる字が無い（根の `AGENTS.md` の E13 の機械の行。持ち主の決め `lang-neutral`）。

- 語の表は `tests/layers/scan.py` の `LANG_WORDS`。事実上の標準の形式（JUnit XML など）は表に入れない。
- 照らさない物: `lib/tests/`（lib 自身の試験）・`lib/AGENTS.md`・借りた superpowers の写し `lib/borrow/superpowers/`（上流の字のままの写しで、固定 `lib/borrow/borrow.json` の pin の sha256 が 1 字も変えさせない。フォルダに固定のファイルと台帳 `COPIED_FROM` のほかが無いことをここで見る）。
- 例外: 拡張子と言語の対応・テストのファイルの名の慣習の表と、それを作る標準ライブラリの import は、`lib/impact.py`・`lib/changemap.py`・`lib/libdocs.py`・`lib/libdocs_local.py` に限って書いてよい（根の `AGENTS.md` の E13 の「例外」の行）。機械はファイルごとに外すので、表の外に言語の名が無いことは人が見る。

## tests/layers/test_no_owner_env.py

`bin/`・`workflows/`・`lib/` に、持ち主の環境の字（`raiki61`・`claude-code-oauth-`・`/Users/`）が無い（根の `AGENTS.md` の E14 の機械の行。持ち主の決め `others-may-use`）。

- 持ち主の環境（Claude のアカウントの名・keychain の項目の名・GitHub のアカウントの名・置き場のパス）は、選べる道として置き、値は利用者の設定か起動の引数で渡す。
- 何かを削る直しが普通の利用者の環境で要らないかは人が見る。

## tests/layers/test_lib_blind.py

`lib/` に Archon の名の字の形が無く、`workflows`・`bin` の中の物を import しない（`lib/AGENTS.md` の E3 と根の `AGENTS.md` の E22 の機械の行）。

- Archon の名: `archon`・`$ARTIFACTS_DIR`・`$TYPED_ARTIFACTS_FILE`・`ARCHON_` で始まる環境変数・`INPUTS_<名>`・`WORKFLOW_ID`・`$LOOP_PREV`・`loop_group`・`$<ノード>.output`・ノードの id・`output_type` の語。
- import の向き: 層の地図 `docs/layers.json` で lib が頼ってよい層（`may_use`）の外の層の頭のフォルダ（`workflows`・`bin`）を import しない（`scan.LAYER_IMPORT`）。
- 照らしから外すのは `tests/layers/scan.py` の `ALLOWED["E3"]` の行だけ: この決まりの文の `lib/AGENTS.md` と、役が読む借りたスキルの読み替え `lib/borrow/unattended.md` が役に説く Archon の字（`<パス>#<字>` の行）。

## tests/layers/test_no_conversion.py

Archon が読む所（`place.workflow_source` の置き場の `.archon/workflows/<pack>/` の下）の全部のファイルが、`workflows/` とバイトで同じ（`workflows/AGENTS.md` の E1 の機械の行）。

- YAML は手で書き、生成・前処理・鍵の削りをしない。Archon は run の始めにその中身をバイトのまま写し取る。
- pack の形で置くので、`.shared/`（`ports.py` など）も同じ置き場に在る。

## tests/layers/test_archon_validate.py

`archon validate` が自分のグラフ（`works-factory-*`）に誤りも警告も出さない（`workflows/AGENTS.md` の E1 の機械の行）。

- 木は `tests/archon.py` の使い捨ての git の木に `workflows/` の全部（block と graph と `.shared/`）を pack の形（`.archon/workflows/works-factory/`）で置いた物。`validate` は `--workflow-source` を受けず黙って捨て、`--cwd` は git の木しか受けないので、この木を `--cwd` に渡す。
- 数えない警告は 1 つの形だけ: Claude Code に同梱の skill（`tests/archon.py` の `BUILTIN_SKILLS`）と借りる superpowers の skill（`BORROWED_SKILLS`。`lib/borrow/borrow.json` の `superpowers.skills`）をノードの `skills:` に名指した時の「Claude skill '<名>' not found on disk — expected for built-in…」の警告（level が warning・field が `skills`・文がこの形・名が 2 つの一覧のどちらかに在る、の全部が当たる物。照らしは `tests/archon.py` の `counted` の 1 か所）。訳は `docs/design/archon.md` の E1 の節。
- 2 つの一覧に無い名の警告と、同梱の名でも別の置き場に入っていて届かない時の誤り（installed elsewhere）は数える。種 `tests/layers/seeds/e1/workflows/skills/` で、その 2 つが数えられることを縛る。
- Archon の源か bun が無ければ見送る（CI は `WORKS_FACTORY_ARCHON_REQUIRED` で赤にする）。

## tests/layers/test_polyfills_listed.py

`workflows/.shared/` と `bin/_lib/` のファイルが、pack の口・入口の部品の外し・埋めの名簿の `- 埋め:` の行の頭の欄のどれかに当たる（`workflows/AGENTS.md` の E2 の機械の行）。

- pack の口: `ports.py`・`prompt.py`・`requestrows.py`。2 つ以上の block が使う断片と形（`prompts/`・`schemas/`）と `AGENTS.md` も口の側に数える。
- 入口の部品の外し: `bin/_lib/` の埋めでない物（起動の認証と隔離を元の works から持ってきた部品）は `tests/layers/scan.py` の `ALLOWED["E2"]` に 1 行ずつ訳つきで置く。
- 名簿 `docs/polyfills.md` の `- 埋め:` の行の頭の欄（`- 埋め:` の直後の、`、` 区切りのパスの並び）が名指す物だけを数え、行の説明の文にだけ名が出る部品は数えない。
- 木に在るかの照らしは頭の欄に限らず行の全部のパスに掛かり、名簿の `- 埋め:` の行が名指す `workflows/`・`bin/`・`lib/`・`tests/` の下のパスが木に無い行も赤。置き場のパスの直後に「（予定）」と書いた行は、木に無くてよい。

## tests/layers/test_block_returns.py

block と graph の返りが 1 つのノードの構造体で、仕事の結末の欄を持つ（`workflows/AGENTS.md` の E5 の機械の行）。

- どの workflow にも `returns:` と `outcome_field:` が在り、返すノードが `output_format` を持ち、`outcome_field` の欄がその `required` に在る（止めた Archon は `required` に在る boolean の欄しか受けない）。
- 返りに `report`（報告に載せる日本語の行の配列）が在ることは `tests/layers/test_block_shape.py`（7.1 の 8）が見る。
- graph が欄つきの参照 `$<include の id>.output.<欄>` で読む欄が返すノードの `output_format` に在るかは Archon の `validate`（`tests/layers/test_archon_validate.py`）が照らすので、ここでは照らさない。まるごとの参照 `$<include の id>.output` は validate が欄を見られないので、受けてよい置き場（script のノードの `with:<鍵>` の直の字か `with:<鍵>.from` の字）と、受けた script が `ports.picked` の口 1 つで読み、宣言した名が `output_format` に在ることをここで照らす。受けた script は環境変数を字のままの鍵でだけ読み、名を組む・回す・写す・渡す読みは赤。
- 許す物の表（`ALLOWED["E5"]`）は持たない（持ち主の決め `shape-checks-only`）。

## tests/layers/test_outward_write.py

外へ書く（`gh`・`git push`・`git merge` を呼ぶ）ノードが、block ごとに 1 つ以下（`workflows/AGENTS.md` の E6 の機械の行）。

- ノードの字は、直に書いた `script:`・`bash:` の中身と、名の script（block の `scripts/` のファイル）の中身。
- 書いた後に読み戻し、読めた値で返る（終了の値 0 を書けた証拠にしない）かは人が見る。

## tests/layers/test_readonly_nodes.py

作業ツリーを変えないノードが `mutates_checkout: false` を書き、役のノードが役の決まりを守る（`workflows/AGENTS.md` の E7 の機械の行）。

- 全部の block と graph の AI のノード（`prompt:`・`command:`。`loop_group` の中も）の印は道具から導く: `allowed_tools` に Bash・Edit・Write（`scan.TREE_CHANGERS`）が無い役は書き、在る役は書かない。外れは、変える道具を持つが作業ツリーを変えない役（表 `scan.KEEP_CHECKOUT`。訳つき）だけ。
- script・bash のノードは、作業ツリーを変えるノード（表 `scan.CHANGE_CHECKOUT`。訳つき）の外の全部が書き、表のノードは書かない。
- `loop:` のノードを置かない（在れば赤。Archon は `loop:` のノードの `mutates_checkout` を無視して警告を出すので、印を書けない）。
- AI のノードは `settingSources: [user]`・閉じた `sandbox`（`enabled: true`・`allowUnsandboxedCommands: false`）・表 `scan.ROLE_TOOLS` の中の `allowed_tools` を持つ。
- 役の `model` は表 `lib/launchgroups.py` の `GROUPS` の群の名（`'@wf-<群>'`）で、役にもグラフの根にも `effort`・`modelReasoningEffort` が無い（`test_role_model_names_a_group_without_effort`。ノードの `effort` は群の別名の `effort` より先に採られ、run ごとの `--model @wf-<群>=…` の付け替えが黙って効かなくなる）。
- Bash を持ち Edit・Write を持たない役は `sandbox.filesystem.denyWrite` に `scan.NO_TREE_WRITE`（`~/../archon-home`。起動が隔離した Archon の家）を書き、`'.'` を書かない（`test_bash_reader_without_no_tree_write_is_red`。`'.'` は cwd を塞がない。#293）。値は `isolate.DIRS` の置き場の名から引き、`isolate()` が組む HOME から解くと隔離した Archon の家を指す（`test_no_tree_write_names_the_isolated_archon_home`）。書き込みの柵の包み（役の claude の前に挟む殻。`docs/polyfills.md` の埋め P5、`workflows/.shared/fence.py`）は、`denyWrite` にこの値（印）が在る起動にだけ、書いてはならない場所の一覧を足す。それは `tests/shared/test_fence.py` が見る。
- 違反の見本は `tests/layers/seeds/e7`・`k18-*`・`k3-*` に 1 本 1 違反。
- 訳と Archon の振る舞いは `docs/design/archon.md` の E7 の節。

## tests/workflows/test_uv_scripts.py

block と graph の script の頭の uv の script の宣言（`workflows/AGENTS.md` の E7 の機械の行）。

Archon は script のノード（`runtime: uv`）を対象の作業ツリーを cwd に `uv run <ファイル>` で起こす。宣言が無いと uv は対象の `pyproject.toml` を拾い、作業ツリーに `.venv` と `uv.lock` を作る（作業ツリーを変えない約束が破れる。issue #92）。

- どの script も頭の 4 行が PEP 723 の宣言（`# /// script`・`# requires-python = ">=3.12"`・`# dependencies = []`・`# ///`）。
- Archon が探す所（`workflows/*/scripts/` と、その 1 段下のフォルダ）の `.py` が全部同じ宣言を持ち、YAML の `script:` の名が全部探したファイルに当たり、`script:` に本体を直に書かない（止めた Archon の `packages/workflows/src/script-discovery.ts` の `MAX_SCRIPT_DISCOVERY_DEPTH`・`scanScriptDir`、`executor-shared.ts` の `isInlineScript`）。
- `pyproject.toml` を置いた種の写しを cwd に `uv run` で起こしても、`git status --porcelain --ignored` が前後で同じ。

## tests/workflows/test_script_imports.py

graph と block の YAML の `script:` が名指すノードの script は、同じ `scripts/` のほかのノードの script を import しない（`workflows/AGENTS.md` の E4 の機械の行）。

- ノードの script を import すると、その script の振る舞いが 2 つのノードに跨る。共に使う物は、その block の `src/`（1 つの block だけ）か `lib/`・`workflows/.shared/` の口（2 つ以上の block）に置く（憲法の 4）。
- 同じ `scripts/` の import を拾う規則は `tests/layers/scan.py` の 1 か所が持ち、ここは許しの表を通さずにノードどうしだけを見る。
- script の名と `lib/` のモジュール・`.shared/` の口の名が重ならないこと（script のフォルダが `sys.path` の頭に来る）は `tests/layers/test_block_shape.py`（7.1 の 9）が見る。

## tests/layers/test_no_timeouts.py

`workflows/` の YAML で、ノードの種類が全部知った物で、どのノードも `timeout` を書かず、既定の期限が当たるノードの `idle_timeout`・`wait.deadline_ms` が全部 `1728000000`（`workflows/AGENTS.md` の E12 の機械の行。持ち主の決め `no-timeouts`）。

- 書かなければ期限の無い鍵は書かない: `script:`・`bash:` の `timeout`、`loop:`・`loop_group:` の `timeout`（`until_bash` の確かめ）。
- 書かなくても既定の期限が当たる鍵には、実質無しの値 `1728000000`（ミリ秒で 20 日。`scan.NO_DEADLINE`。埋め P14）を書く: `prompt:`・`command:` の `idle_timeout`、`loop:` の `idle_timeout`、`approval:` の `idle_timeout`、`wait:` の中の `deadline_ms`。`attention` の待ち（承認ノード）は期限を持たない。`cancel:`・`include:`・`workflow:` は期限を持たない。
- 知らない種類のノードは赤。鍵ごとの訳と止めた Archon の在り処は `docs/design/archon.md` の E12 の節。

## tests/layers/test_gates.py

承認ノードの形（`workflows/AGENTS.md` の E16 の機械の行。持ち主の決め `asf-way-gates-fanout`）。

- 全部の graph と block の承認ノードが `wait:` の `attention` で `form: select` を持ち、`options` に `lib/answer.py` の答えの語（`GO_WORDS`・`STOP_WORDS`。`STOP_WORDS` は `REJECT` を含む）を全部持つ（止めた Archon は `options` に無い答えを拒み、run は承認ノードで止まったまま）。
- `approval:` のノードが無い。どのグラフも頭に `interactive` を書かない（止めた Archon は読み込みで非推奨の警告を出し、効かない）。
- ループ（`loop_group`）の本体に承認ノードが無い（本体が承認ノードで終わるループの再開は会話を引き継がない）。
- include されるグラフ（block と、メイングラフと周の鎖のほかの graph）は頭に `worktree`・`container`・`evidence_policy`・`mutates_checkout` を書かない（一番上のグラフ〔メイングラフ・周の鎖〕は書いてよい）。
- 筋書きの stub は `workflow test` が照らす（答えの stub の無い承認ノードで止まると赤）。並べ（`fan_out:`）の形は人が見る。

## tests/layers/test_role_retry.py

graph と block の YAML の AI のノード（`prompt:`・`command:`。`loop_group` の本体の中も）が `retry` を形 `scan.ROLE_RETRY`（`{max_attempts: 2, on_error: all}`）で持つか、ノードの頭の行の真上に外す理由の行 `# retry なし: <理由>` を持つ（`workflows/AGENTS.md` の E19 の機械の行）。

- 両方在るのも赤。照らしは `tests/layers/scan.py` の `_role_retry`。
- `on_error: all` を書く訳（止めた Archon の既定は `on_error: transient` で、種類が `unknown` の失敗を出し直さない）と、`loop_group` のノードそのものに書けない訳は `docs/design/archon.md` の E19 の節。

## tests/layers/test_depth_skip.py

深さの段の表と line の段の表 `TIERS`（`scan.tiers()`。`workflows/line/src/tiers.py`）の一致と、深さを読む `when` の句の無さ（`workflows/AGENTS.md` の E20 の機械の行。持ち主の決め `depth-by-reason`・`three-tiers`）。

- 表は `docs/design/line.md` の「### 深さの段の表」（`scan.DEPTH_TABLE`）。行（段・省く物・足す物）が `TIERS` と等しい。省く物・足す物の欄は `` `名` `` を並べるか「無し」。
- どのノード（メイングラフ・include した graph と block の頭の段・ループの中）の `when` も、出力の深さの欄を読む句（`$<ノード>.output.<名に depth を含む欄>`）を持たない。省くかを `when:` に渡す時は、line が表から引いた真偽（`raise` の `checks`・`eyes_due` など）だけにする。
- 今の木は緑、小さな木で 1 本 1 違反の赤を作る。

## tests/layers/test_hermetic_env.py

`tests/`・`lib/tests/` の試験の子の環境は `tests/bin/hermetic.child_env` で作る（`tests/AGENTS.md` の E21 の機械の行）。

- `tests/` と `lib/tests/` の `*.py` に、`os.environ` を写す形（`scan.COPIED_ENVIRON`）と、`env=` の無い子の起こし（`scan.SPAWNS`）が無い。既定が `None` の引数を差し替えずに `env=` へ渡す形も当てる。照らしは `tests/layers/scan.py` の `_hermetic_env`。
- 外しは `scan.ALLOWED["E21"]` の行（訳つき）だけ: 子の環境を作る道具でなく利用者の環境を継ぐのが用途の物（本物の run・較正の命令の道具・試験を回す口 `tests/changed.py`）と、子の環境を組む口でない物（偽の script の字）。
- 試験を回す口が過程の環境から名を外し、外した値を `inherited` で引けることは `tests/test_shard.py` の `ScrubTest`。

## tests/layers/test_test_commands.py

run の中の確かめの命令と全部の試験の命令を、役が取り違えないように書いてある（`tests/AGENTS.md`。持ち主の決め `full-suite-in-ci`）。

- `tests/AGENTS.md` に run の中の命令 `uv run --isolated python3 tests/changed.py`（試験の中の定数 `UNIT`）が、全部の試験の命令より先に在る。
- 全部の試験の命令（`python3 -m unittest discover`）は `tests/AGENTS.md` の CI の行にだけ在り、その行は「CI が回す物」と「回さない」を持つ。ほかの決まりの文書（全部の階層の `AGENTS.md`・根の `README.md`・`MISSION.md`・`engineering.md`）と `pyproject.toml` には無い。
- どちらが run の中の命令と読めるか（読み方そのもの）は人が見る。

## tests/layers/test_rule_index.py

決まりの番号（E1 など）が、根の `AGENTS.md` の「決まりの置き場」の表の置き場にちょうど 1 つずつ在る（根の `AGENTS.md` の「決まりの置き場」）。

- 表の行は `| E<番号> | `<置き場>` |`、見出しは `## E<番号> `。表の番号は 1 から欠けずに並ぶ。
- 置き場の `AGENTS.md` は全部の階層を探す（`workflows/AGENTS.md`・`lib/AGENTS.md`・`tests/AGENTS.md`・`bin/AGENTS.md` と根）。
