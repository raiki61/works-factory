<!-- coldwrite:skip 実装の計画。語は docs/design.md の「語」の節で定義 -->
# 段 0 土台（実装計画）

> **実装する者へ:** superpowers:subagent-driven-development（推し）か superpowers:executing-plans で Task ごとに進める。手順は `- [ ]` で追う。

**目的:** 段 1 の歩く骨組みが乗る土台を作る。版の取り寄せと起こし方・層の試験・境の口・線（ブロックの代わりで筋書きを回す）・入口の殻 1 本。

**作り:** 4 つの層（入口 `bin/`・グラフ `workflows/`・境 `workflows/.shared/`・助け手 `lib/`）の器と、器を縛る試験を先に置く。ブロックは段 2 の issue が各々中身ごと作る（持ち主の決め `overnight-speed`）。線はブロックの返りの約束だけを読み、試験だけで使うブロックの代わりで確かめる。

**道具:** Python 3.12 以上・unittest・git・`gh`・`bun`・止めた Archon の源（`docs/design.md` の「語」。持ち主の決め `archon-same-as-asf`）。

**仕様:** `docs/design.md`（層・線・ブロック・Archon の分かっていること）と 各階層の `AGENTS.md`（E1〜E18）。

## 全体の決まり

- 言語: Python 3.12 以上。外のパッケージは使ってよい（持ち主の決め `outside-packages-ok`）。自前で書く前に既製の物を当たり、版を止め、依存の宣言は 1 か所に置く（Task 2 で決める）。
- 版の止め: `pack.load` の値だけを使う。Archon の源の commit は ASF の止め `factory/pack.json` の `integration_revision_required`（今は `d97d00ef15cce4b15d39e42635e4e86996ec1351`）1 つで、根の `pack.json` には書かない。Archon の本体と ASF の工程（`source_directory`。`.archon/workflows/sdlc`）の両方をここから取る。
- 置き場: Archon の家には何も置かない。自分の工程は `--workflow-source` で置かずに読ませ、ASF はその源の中の物を読む（issue #25）。
- ASF のファイルをこのリポジトリに入れない（試験の種にも入れない）。
- 工程の名は `works-factory-<フォルダの名>`、線は `works-factory-line`。
- ブロックの間で渡す物の型の正本は、返す節の `output_format` と線の `with:` だけ。型の写しを作らない（持ち主の決め `io-in-output-format`）。
- 期限を置かない（E12）。Archon の既定の期限を外すため、期限を持つ節には `1728000000` を書く。
- 試験はリポジトリの根から `uv run --isolated python3 -m unittest discover -s . -t .` の 1 つで走る（CI も ASF の `harness/harness.config.json` の `unit` も同じ命令）。`tests/`・`tests/bin/`・`lib/tests/` など試験を置くフォルダには、全部 `__init__.py` を置く（無いと Python 3.12 は黙って見つけない）。Archon の源が要る試験は、無ければ名前つきで見送る（`skipTest("Archon の源が無い: ...")`）。CI（`.github/workflows/tests.yml`）は止めた Archon の源と bun を取る（Task 3b）ので、CI では見送らない。

## 見るべき所（Task の試験が当たる物）

1. Archon の源が取れない（網が無い・commit が消えた・依存が入らない）: 途中まで取った物を残さず、何が取れなかったかを 1 行で言って止まる。前に取った源は残る。→ `tests/bin/test_place.py` の `test_failure_leaves_previous_source`
2. Archon の家にほかの工程（同梱・ほかの pack）が在る: 何も置かないので触らない。→ `tests/bin/test_place.py` の `test_repo_and_archon_home_are_untouched`
3. 型つきの成果物の一覧に `errors` が在る: 読めた分と一緒に返し、捨てない。→ 段 2 の report ブロックの issue（型つきの成果物の一覧を読むのは report だけ。E5）
4. 空のファイルへの指し札: 返りに入った札は Archon が節の終わりに照らし、名前つきの誤りで止める。境の口は札の形を組むだけで、先を照らさない。→ Archon の節の終わりの照らし（このリポジトリに試験は無い。持ち主の決め `asf-way-gates-fanout`）
5. `archon validate workflows` の警告: 自分の工程の警告は赤。ASF の警告（今は `archon-merge-queue` の script のパスの 2 つ）は数えない。→ Task 3b の `tests/layers/test_archon_validate.py`

---

### Task 1: 版の取り寄せと配置

> PR #6 で入った後、issue #25（持ち主の決め `archon-same-as-asf`）で形を変えた。今の口は `pack.load`（Archon の版は ASF の `factory/pack.json` から読む）・`place.archon_source`（源を 1 度だけ取って依存を入れる）・`place.workflow_source`（`--workflow-source` に渡す置き場）・`place.workflow_run`（起こす命令）。実行ファイルの取り寄せ（`archon_binary`）と家への配置（`asf_tree`・`place`）は消した。下はその時の記録。

**Files:**
- Create: `bin/_lib/pack.py`・`bin/_lib/place.py`
- Create: `tests/__init__.py`・`tests/bin/__init__.py`（無いと Python 3.12 の unittest が黙って見つけない）
- Modify: `pack.json`（Linux x64 の Archon の実行ファイルと sha256 を足す。CI は ubuntu で走り、ほかの人も Linux で使うため。E14）
- Test: `tests/bin/test_place.py`

**Interfaces:**
- Produces:
  - `pack.load(root: Path) -> dict`（`pack.json` を読み、上の鍵が欠けたら `ValueError`）
  - `place.archon_binary(pack: dict, cache: Path, download: Callable[[str, str, Path], Path]) -> Path`（キャッシュに無ければ `download(repo, release, dest_dir)` で取り、sha256 を照らす。合わなければ `RuntimeError`（消すのは人。パスを文に入れる））
  - `place.asf_tree(pack: dict, cache: Path, fetch: Callable[[str, str, str, Path], None]) -> Path`（`fetch(repo, commit, folder, dest)` で `<cache>/asf/<commit>/` に取り、そのフォルダを返す。在れば取らない）
  - `place.place(pack: dict, root: Path, archon_home: Path, asf_dir: Path) -> None`（`root/workflows/` を `archon_home/workflows/works-factory/` に、`asf_dir` を `archon_home/workflows/asf/` にバイトのまま置く。各々を一時の置き場に作ってから入れ替える）
  - 既定の `download` は `gh release download`、既定の `fetch` は `git` の部分 clone（`--filter=blob:none --sparse`）。試験は偽の関数を渡す。

- [ ] **Step 1: 試験を書く**（`tests/bin/test_place.py`）
  - `test_load_rejects_missing_keys`: `asf.commit` を抜いた `pack.json` で `ValueError`
  - `test_binary_sha_mismatch_names_path`: 偽の download が違う中身を書くと `RuntimeError`、文にパスが在る
  - `test_binary_cached_no_download`: キャッシュに正しい中身が在れば download が呼ばれない
  - `test_place_is_byte_identical`: 置いた `works-factory/` の全ファイルが `workflows/` とバイトで同じ（E1）
  - `test_place_touches_only_own_folders`: 前から在る `archon_home/workflows/other/x.yaml` と `archon_home/workflows/archon-foo.yaml` が残る
  - `test_fetch_failure_leaves_previous_placement`: fetch が例外を出すと、前に置いた `workflows/asf/` の中身がそのまま
  - `test_repo_never_gets_asf_files`: 配置の後、`root` の下に新しいファイルが無い
- [ ] **Step 2: 走らせて赤を見る**: `python3 -m unittest tests.bin.test_place -v` → `ModuleNotFoundError`
- [ ] **Step 3: 上の口を実装する**
- [ ] **Step 4: 走らせて緑**: 同じ命令で全部 OK
- [ ] **Step 5: commit**: `git add bin/_lib tests/bin && git commit -m "feat(bin): 版の取り寄せと Archon の家への配置"`

### Task 2: 層の試験と lib/ の器

**Files:**
- Create: `lib/__init__.py`・`lib/tests/__init__.py`
- Create: `tests/layers/scan.py`・`tests/layers/test_polyfills_listed.py`・`test_lib_blind.py`・`test_block_paths.py`・`test_no_asf.py`・`test_names.py`・`test_no_timeouts.py`・`test_lang_neutral.py`・`test_no_owner_env.py`
- Create: 依存の宣言の置き場 1 か所（`pyproject.toml` か、節の `deps:` から引ける形。Step 0 で決める）
- Create: `tests/layers/seeds/`（決まりを破った小さな木。試験が赤を出すことの確かめ用）

**Interfaces:**
- Produces: `scan.problems(rule: str, root: Path) -> list[str]`（`rule` は `"E2"`・`"E3"`・`"E4"`・`"E8"`・`"E9"`・`"E12"`・`"E13"`・`"E14"`。1 行に 1 つ、`<パス>:<行>: <何が>`）。各試験は本物の木で `[]`、種の木で 1 つ以上を確かめる。
- 決まりの中身は 各階層の `AGENTS.md` の各 E の「機械」の行。E2 の名簿の読みは `docs/polyfills.md` の `- 埋め:` の行の `workflows/.shared/<名>` の字。境の口は `workflows/.shared/boundary.py` の 1 つ。

- [ ] **Step 1: 種の木を作る**: `seeds/e2`（名簿に無い `.shared/extra.py`）・`seeds/e3`（`lib/x.py` に `TYPED_ARTIFACTS_FILE`）・`seeds/e4`（`workflows/judge/scripts/a.py` に `../plan/`）・`seeds/e8`（`include: archon-triage`）・`seeds/e9`（名 `archon-x`）・`seeds/e12`（`timeout: 10`）・`seeds/e13`（`workflows/judge/commands/a.md` に `pytest`）
- [ ] **Step 2: 試験を書く**: 各試験に `test_real_tree_clean`（`problems(rule, リポジトリの根) == []`）と `test_seed_caught`（種で `len(...) >= 1`、文に種のパスが在る）。E2 は加えて `test_listed_but_missing_is_red`（名簿に在って木に無い行も赤）
- [ ] **Step 3: 走らせて赤**: `python3 -m unittest discover -s tests/layers -t . -v` → `ModuleNotFoundError: scan`
- [ ] **Step 4: `scan.problems` を実装する**: 字の形の照らしは正規表現、YAML は既製の YAML の読み手で読む（字の行で読む自前の読み手を作らない）
- [ ] **Step 5: 走らせて緑**
- [ ] **Step 6: commit**: `git commit -m "test(layers): 層の境の試験（E2・E3・E4・E8・E9・E12・E13・E14）と lib/ の器"`

### Task 3: 境の口

**Files:**
- Create: `workflows/.shared/boundary.py`
- Test: `tests/shared/test_boundary.py`

**Interfaces:**
- Produces（ブロックの script が Archon と出入りする口はこれだけ。入力だけは口を通さず、script が `os.environ["INPUTS_<名>"]` を字のまま読む）:
  - `boundary.returns(obj: dict) -> None`（JSON を標準出力に 1 つ書く。型は Archon が節の `output_format` で照らすので、ここでは照らさない）
  - `boundary.pointer(rel: str) -> dict`（`{type: "archon_artifact", run_id, path}` の形を組むだけ。先が在る・空でない・置き場の中かは、返りに入った札を Archon が節の終わりに照らす）
  - `boundary.resolve(ptr: dict) -> Path`（同じ run の物で、パスが置き場からの相対の物だけ。違えば、また空のパスや NUL を含むパスなら `ValueError`）
  - `boundary.lib_root() -> Path`（`lib/` の置き場。決め方は段 1 の未決 U5。段 0 はリポジトリの中の `lib/` を返す）

- [ ] **Step 1: 試験を書く**（偽の一覧のファイルと環境で）
  - `test_pointer_names_this_run`・`test_resolve_refuses_other_run`・`test_resolve_refuses_bad_path`（空のパス・NUL を含むパス・置き場の外）
  - `test_returns_writes_one_json`: 標準出力が JSON 1 つちょうど
- [ ] **Step 2: 赤**: `python3 -m unittest tests.shared.test_boundary -v`
- [ ] **Step 3: 実装**
- [ ] **Step 4: 緑**。Task 2 の `test_polyfills_listed` も緑のまま（境の口は名簿の外で許される 1 つ）
- [ ] **Step 5: commit**: `git commit -m "feat(shared): Archon との境の口"`

### Task 3b: 土台の足し（pack の形の置き場・lib の見つけ方・Archon の要る試験の助け・CI の源）

> 線・入口の殻・8 つのブロックの issue が共に頼る物を先に 1 つの小さな PR で置き、後の issue が互いを待たないようにする。中身の正本は `docs/plans/2026-10-12-groundwork-line-launcher.md` の P0 の節。

**Files:**
- Modify: `bin/_lib/place.py`（`workflow_source` の置き場を `.archon/workflows/works-factory` → `workflows/` の pack の形にする。`cache_dir(env)` を足す）・`pack.json`（`ours.pack`）・`workflows/.shared/boundary.py`（`lib_root()` が `WORKS_FACTORY_ROOT` を読む。U5）・`.github/workflows/tests.yml`（止めた Archon の源と bun）
- Create: `tests/archon.py`（源と bun を見つけ、無ければ名前つきで見送る。使い捨ての木を組む）
- Test: `tests/bin/test_place.py`・`tests/shared/test_boundary.py`・`tests/layers/test_no_conversion.py`・`tests/layers/test_archon_validate.py`

**Interfaces:**
- 止めた Archon は、名前で指す script を pack の形の工程の時だけ工程のフォルダの `scripts/` から探し、pack の部品は `<pack>/.shared/` から読む（`guides/script-nodes.md` の「Named Script Resolution」・`script-discovery.ts` 151-222 行）。だから置き場を pack の形にする。
- `test_archon_validate`: 線が `include:` する工程が 1 つでも無い間は、線を名前つきで見送り、ほかの工程は照らし続ける。

- [ ] **Step 1: 試験を書く** → **Step 2: 赤** → **Step 3: 実装** → **Step 4: 緑**（CI で Archon の要る試験が見送られない）
- [ ] **Step 5: commit**: `git commit -m "feat: 自分の工程を pack の形で読ませ、lib の見つけ方と Archon の要る試験の助けを置く"`

### Task 4: 線

> 持ち主の決め `overnight-speed` で、ブロック 8 つは各々の issue が自分のフォルダを中身ごと作る。この Task は線だけを作り、Archon の筋書きの試験を `exec-code: true` で回す。ブロックの代わり（試験だけで使う同じ名の小さな工程）を置く予定だったが、線の PR #74 の間に 8 つのブロックが全部 main に入ったので、筋書きは本物のブロックと組んで回し、代わりは置かない。中身の正本は `docs/plans/2026-10-12-groundwork-line-launcher.md` の A の節。下は要点。

**Files:**
- Create: `workflows/line/works-factory-line.yaml`・`workflows/line/scripts/`・`workflows/line/fixtures/`（筋書き）・`workflows/.shared/skip_value.py`（埋め P2）
- Create: `lib/entryshape.py`・`lib/entry.py`（機能の切り替えの塊だけ）とその試験（持ち主の決め `lib-port-as-is`）
- Test: `tests/layers/test_block_returns.py`・`test_outward_write.py`・`test_readonly_nodes.py`・`test_gates.py`・`tests/e2e/test_line_scenarios.py`・`tests/workflows/test_line.py`（線の script の決め）・`tests/workflows/test_gate_head.py`（関所の文の頭。今の works の試験を戻した物）
- Modify: `docs/design.md`（線の中の id・U2〜U4・P2 の受け手の書き方・線の止め札の行）・`docs/polyfills.md`（P2）・`docs/asf-notes.md`（A9〜A11）・`workflows/AGENTS.md` の E5

**Interfaces:**
- Consumes: Task 3 の境の口・Task 3b・#30 の `lib/`（`startrec`・`gatepolicy`・`stopby`・`converge`・`gatemarks`・`answer`・`planmarks` ほか）・`docs/design.md` の「ブロックの返りの約束」
- Produces:
  - 線の順・関所・往復は `docs/design.md` の「線」の 1〜13。関所は E16 の形で、どの関所も `decisions` に `approve`・`continue`・`stop` を持つ（`continue` は lib/answer.py の答えの行の語）。`stop` は後ろを飛ばして report へ流す（持ち主の決め `report-on-stop`）。報告つきの止めは関所の `stop`・`reject` だけ。関所の間は報告の無い `cancel` を狭めとして認めた（持ち主の決め `stop-at-gates`）。
  - include の受け手に `if_skipped` を書けない（P2）ので、関所の答えと飛ばされうる返りは線の返しの節（`answer-*`・`judged`・`fixed`・`plan-out`・`collect`）で受け直してから渡す。
  - 計画の往復は `loop_group` の中の 2 つの `include:` と、終わりの返しの節 `plan-out`（中の節は外から見えないため。抜けるのは通し・止め・3 周目のどれか）。`report` は `trigger_rule: all_done`。線の返す節は線の `result`（`outcome_field: fixed`）。
  - 線とブロックの欄の照らしは Archon の `validate`（Task 3b の `test_archon_validate`）。

- [ ] **Step 1: 試験を書く**（層の試験 4 つと種・`tests/e2e/test_line_scenarios.py`・`lib/` の 2 つの元の試験）
- [ ] **Step 2: 赤**: `uv run --isolated python3 -m unittest discover -s . -t .`
- [ ] **Step 3: `lib/` の 2 つ・線の script・線の YAML と筋書きを書く**（線は本物の 8 ブロックを差し込む。代わりのブロックは PR #74 の 5 回目の直しで外した）
- [ ] **Step 4: 緑**。筋書きが全部 `workflow test` で通る
- [ ] **Step 5: commit**: `git commit -m "feat(workflows): 線と、本物のブロックで回す筋書き"`

### Task 5: 入口の殻 1 本（bin/works-factory）

> 持ち主の決め `one-launcher` で書き直した（前の形の `bin/start`・`answer`・`show` は PR #20 を閉じて作らない）。Task 6 の部品を今の works の `works/dev/archon.sh` と同じ順でつなぐ殻 1 本で、人は Archon の命令をそのまま打つ。中身の正本は `docs/plans/2026-10-12-groundwork-line-launcher.md` の B の節。下は要点。

**Files:**
- Create: `bin/works-factory`（`bin/_lib/launcher.py` の `main` を呼ぶだけ）・`bin/_lib/launcher.py`
- Modify: `README.md`・根の `AGENTS.md` の `bin/` の行・`bin/AGENTS.md` の E15・`docs/design.md`・`docs/polyfills.md` の P1
- Test: `tests/bin/test_launcher.py`

**Interfaces:**
- Consumes: Task 1 の `pack.load`・`place.archon_source`・`place.workflow_source`・`place.workflow_run`、Task 3b の `place.cache_dir`、Task 6 の `isolate.isolate`・`hostgh.write`・`toolset.py install`・`auth_launch.py check|exec`
- Produces:
  - `bin/works-factory <Archon の CLI の引数>`: 隔離の前の値を取る → 対象（git の根）ごとに起動をまたいで同じ家（`WORKS_FACTORY_HOME`、無ければ `${XDG_STATE_HOME:-~/.local/state}/works-factory/targets/<対象の sha256 の頭 8 字>`）→ 止めた Archon の源 → 隔離 → gh の口 → 送信を切る・mise の信頼（今の works と同じ条件）→ `WORKS_FACTORY_ROOT` → 工程を回す命令の時は認証の確かめとプラグインの選び（`validate` はプラグインの選びだけを `--no-plugins` で）→ `workflow run` の時は `place.workflow_run` で `--cwd` と `--workflow-source` を利用者の引数の前に置く（利用者の `--workflow-source` は拒む）→ `auth_launch.py exec` で `bun`（絶対パスに直す）`<源>/packages/cli/src/cli.ts` に置き換わる。
  - 既定はホストのログインのまま（E14）。選べる道は環境変数（`WORKS_FACTORY_HOME`・`WORKS_FACTORY_KEYCHAIN_ITEM`・`WORKS_FACTORY_NO_AUTH`・`WORKS_FACTORY_COLDWRITE_MARKETPLACE(_REPO)`）。
  - 周の鎖は殻に置かない（置き先の推しは線の後ろの `workflow:` の節。段 3 で確かめる）。ASF をこの殻から起こすのは別の issue。

- [ ] **Step 1: 試験を書く**（偽の `bun`・`claude`・`gh` を PATH に置き、殻を子のプロセスで走らせる）
- [ ] **Step 2: 赤**: `python3 -m unittest tests.bin.test_launcher -v`
- [ ] **Step 3: 実装**（Task 6 の部品は変えない）
- [ ] **Step 4: 緑**。全部の試験 `uv run --isolated python3 -m unittest discover -s . -t .` が緑
- [ ] **Step 5: commit**: `git commit -m "feat(bin): 入口の殻 works-factory"`

### Task 6: 起動の認証と置き場の隔離を今の works から持ってくる

移す元は今の works（`pack.json` の `works.commit` の `raiki61/claude-plugins` の `works/`）。持ち主の決め `bring-launch`（「3は全部持ってきたらいいのでは」）と `agents-md-per-level` の「最後には要らないものは全部掃除する感じでもいいよ」に従い、頼っている部品ごと全部を元の名のまま持ってくる。要らない所を削るのは、全部が動いた後の掃除の段。

**Files:**
- Create（`bin/_lib/`。元の名のまま）: `auth_launch.py`・`claude_auth.py`（元 `works/.shared/core/`）・`toolset.py`（元 `works/dev/`。部分コマンドも全部）・`hostgh.py`（元 `works/dev/`。GitHub のアカウントの選び）・これらが import する `spseam.py`・`changemap.py`・`copyledger.py`（元 `works/.shared/core/`）と、その先でさらに import する物
- Create: `bin/_lib/isolate.py`（`works/dev/archon.sh` の、HOME・`ARCHON_HOME`・`CLAUDE_CONFIG_DIR`・`XDG_*` を run の置き場へ向ける所を Python に移した物）
- Test（`tests/bin/`。元の名のまま）: `test_auth_launch.py`・`test_toolset.py`・`hostgh.py` を縛る元の試験と、試験の助け `hermetic.py`・`gitkit.py`（元 `works/tests/`）。`isolate.py` は元に単体の試験が無いので `test_isolate.py` を新しく書く（向け先が全部 run の置き場の下にある・利用者の `CLAUDE_CONFIG_DIR` を隔離の前に取る）

**Interfaces:**
- 根の `AGENTS.md` の E14・E18 と `bin/AGENTS.md` の E15 のとおり。作り直さない。直すのは今の works だけの事情（写しの同期の説明・works の置き場の名・`WORKS_` で始まる環境変数の名・持ち主の環境の字 `raiki61` など。E14）だけで、直した所を commit に書く。
- 既定はホストのログインのまま（`claude /login` の人・API キー・会社のゲートウェイの人がそのまま動く）。選べる道: Claude のアカウントを keychain の項目の名で選ぶ（選んだ時はそれより上に効く資格を子に渡さない）・GitHub のアカウントを名で選ぶ（`hostgh.py`）・Archon の家の置き場を選ぶ。値は利用者の設定（リポジトリの外）か引数で渡す。どの出どころの認証で起こしたかを 1 行出す。
- Archon は Task 1 の `place.archon_source` で取った源から起こす（`archon.sh` の実行ファイルの取り寄せは持ってこない。E15）。
- Task 5 の殻 `bin/works-factory`・`bin/_lib/launcher.py` には触らない。これが入って Task 5 とつながったら（段 1）、ASF もこの入口から起こし、今の仮の殻 `~/.local/state/works-factory/bin/asf-env` は捨てる。

- [ ] **Step 1: 元の試験と試験の助けを持ってきて、直した名に合わせる**（赤）
- [ ] **Step 2: 元のファイルと頼っている部品を持ってきて直す**（緑）。`test_isolate.py` を書いて赤 → `isolate.py` で緑
- [ ] **Step 3: 全部の試験** `uv run --isolated python3 -m unittest discover -s . -t .` が緑
- [ ] **Step 4: commit**: `git commit -m "feat(bin): 起動の認証と置き場の隔離を今の works から持ってくる"`

### Task 7: 封じた差分を当てる口（bin/apply）

**Files:**
- Create: `bin/apply`（中身は `bin/_lib/apply.py` を呼ぶだけ）・`bin/_lib/apply.py`
- Test: `tests/bin/test_apply.py`

**Interfaces:**
- Consumes: Task 4 の merge ブロックの返す節の `output_format`（封じた差分の指し札と hash の欄）と、Task 5 の家の決め方（run の置き場を Archon の `workflow get <run> --json` で引くため、`bin/apply` も同じ家で Archon を起こす）
- Produces: `apply.apply(run_id: str, target: Path) -> None`（merge の返りの指し札の差分を、封じた hash を照らしてから `git apply` する。違えば止まり、対象の木は変えない）

- [ ] **Step 1: 試験を書く**: `test_apply_refuses_changed_diff`（封じた hash と違う差分で止まり、対象の木は変わらない）・`test_apply_applies_sealed_diff`（同じなら当たる）
- [ ] **Step 2: 赤** → **Step 3: 実装** → **Step 4: 緑**（全部の試験）
- [ ] **Step 5: commit**: `git commit -m "feat(bin): 封じた差分を当てる apply"`

## 段 0 の終わりの確かめ

- [ ] 全部の試験が緑。見送りは Archon の源が無い時だけ。
- [ ] `docs/design.md` の U3・U4 に分かった事を書いた。
- [ ] `docs/polyfills.md` の行と `workflows/.shared/` が揃う（`test_polyfills_listed`）。
