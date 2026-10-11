<!-- coldwrite:skip 実装の計画。語は docs/design.md の「語」の節で定義 -->
# 段 0 土台（実装計画）

> **実装する者へ:** superpowers:subagent-driven-development（推し）か superpowers:executing-plans で Task ごとに進める。手順は `- [ ]` で追う。

**目的:** 段 1 の歩く骨組みが乗る土台を作る。版の取り寄せと配置・層の試験・境の口・線の骨組み（ブロックの返す節の `output_format` を含む）・人の打つ口。

**作り:** 4 つの層（入口 `bin/`・グラフ `workflows/`・境 `workflows/.shared/`・助け手 `lib/`）の器と、器を縛る試験を先に置く。ブロックの中身は `output_format` に合う返りを返すだけの仮の物で、段 2 の issue が本物に替える。

**道具:** Python 3.12 以上・unittest・git・`gh`・Archon v0.11.1 の実行ファイル。

**仕様:** `docs/design.md`（層・線・ブロック・Archon の分かっていること）と `engineering.md`（E1〜E18）。

## 全体の決まり

- 言語: Python 3.12 以上。外のパッケージは使ってよい（持ち主の決め `outside-packages-ok`）。自前で書く前に既製の物を当たり、版を止め、依存の宣言は 1 か所に置く（Task 2 で決める）。
- 版の止め: `pack.json` の値だけを使う（Archon `v0.11.1`・実行ファイル `archon-darwin-arm64` の sha256 `b9338474fd3151d5d5402d76ae278105e65835f2e3506a93f0e5e4a378d10ede`・ASF の commit `d97d00ef15cce4b15d39e42635e4e86996ec1351`・フォルダ `.archon/workflows/sdlc`）。
- 置き場: 自分の工程は `$ARCHON_HOME/workflows/works-factory/`、ASF は `$ARCHON_HOME/workflows/asf/`。ほかの置き場に触らない。
- ASF のファイルをこのリポジトリに入れない（試験の種にも入れない）。
- 工程の名は `works-factory-<フォルダの名>`、線は `works-factory-line`。
- ブロックの間で渡す物の型の正本は、返す節の `output_format` と線の `with:` だけ。型の写しを作らない（持ち主の決め `io-in-output-format`）。
- 期限を置かない（E12）。Archon の既定の期限を外すため、期限を持つ節には `1728000000` を書く。
- 試験はリポジトリの根から `python3 -m unittest discover -s . -t .` の 1 つで走る（CI も ASF の `harness/harness.config.json` の `unit` も同じ命令）。`tests/`・`tests/bin/`・`lib/tests/` など試験を置くフォルダには、全部 `__init__.py` を置く（無いと Python 3.12 は黙って見つけない）。Archon の実行ファイルが要る試験は、無ければ名前つきで見送る（`skipTest("archon の実行ファイルが無い: ...")`）。CI は実行ファイルを取ってから走るので見送らない。

## 見るべき所（Task の試験が当たる物）

1. ASF の commit が取れない（網が無い・commit が消えた）: 途中まで置いた物を残さず、何が取れなかったかを 1 行で言って止まる。前に置いた `workflows/asf/` は残る。→ Task 1 の `test_fetch_failure_leaves_previous_placement`
2. Archon の家にほかの工程（同梱・ほかの pack）が在る: 消さない・上書きしない。→ Task 1 の `test_place_touches_only_own_folders`
3. 型つきの成果物の一覧に `errors` が在る: 読めた分と一緒に返し、捨てない。→ 段 2 の report ブロックの issue（型つきの成果物の一覧を読むのは report だけ。E5）
4. 空のファイルへの指し札: Archon が拒むので、境の口が作る時点で名前つきの誤りで止まる。→ Task 3 の `test_pointer_refuses_empty_file`
5. `archon validate workflows` の警告: 自分の工程の警告は赤。ASF の警告（今は `archon-merge-queue` の script のパスの 2 つ）は数えない。→ Task 4 の `test_validate_has_no_warnings_for_ours`

---

### Task 1: 版の取り寄せと配置

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
- 決まりの中身は `engineering.md` の各 E の「機械」の行。E2 の名簿の読みは `docs/archon-polyfills.md` の `- 埋め:` の行の `workflows/.shared/<名>` の字。境の口は `workflows/.shared/boundary.py` の 1 つ。

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
- Produces（ブロックの script が Archon と出入りする口はこれだけ）:
  - `boundary.inputs(names: list[str]) -> dict[str, str]`（Archon が script に渡す入力を読む。足りない名は `KeyError` に名を入れる）
  - `boundary.returns(obj: dict) -> None`（JSON を標準出力に 1 つ書く。型は Archon が節の `output_format` で照らすので、ここでは照らさない）
  - `boundary.pointer(rel: str) -> dict`（`{type: "archon_artifact", run_id, path}`。ファイルが無い・空・置き場の外なら `ValueError`）
  - `boundary.resolve(ptr: dict) -> Path`（同じ run の物だけ。違えば `ValueError`）
  - `boundary.lib_root() -> Path`（`lib/` の置き場。決め方は段 1 の未決 U5。段 0 はリポジトリの中の `lib/` を返す）

- [ ] **Step 1: 試験を書く**（偽の一覧のファイルと環境で）
  - `test_pointer_refuses_empty_file`・`test_pointer_refuses_outside`・`test_resolve_refuses_other_run`
  - `test_returns_writes_one_json`: 標準出力が JSON 1 つちょうど
- [ ] **Step 2: 赤**: `python3 -m unittest tests.shared.test_boundary -v`
- [ ] **Step 3: 実装**
- [ ] **Step 4: 緑**。Task 2 の `test_polyfills_listed` も緑のまま（境の口は名簿の外で許される 1 つ）
- [ ] **Step 5: commit**: `git commit -m "feat(shared): Archon との境の口"`

### Task 4: 線の骨組み

**Files:**
- Create: `workflows/README.md`（pack の決まり。`engineering.md` を指すだけ）
- Create: `workflows/line/works-factory-line.yaml`・`workflows/line/fixtures/`
- Create: 8 つのブロックの各々 `workflows/<名>/works-factory-<名>.yaml`・`scripts/stub.py`・`fixtures/`
- Test: `tests/layers/test_block_returns.py`・`test_outward_write.py`・`test_readonly_nodes.py`・`test_no_conversion.py`・`test_archon_validate.py`

**Interfaces:**
- Consumes: Task 3 の `boundary.returns`
- Produces:
  - 線の順・関所・往復は `docs/design.md` の「線」の 1〜13 のとおり。関所は Archon の承認の節で、`when:` は線の節の返りで決める（段 0 は既定で開く）。
  - 各ブロックは `returns:` に 1 つの節と `outcome_field:` を持つ。その節の `output_format` に、`docs/design.md` の「線が運ぶ物」の欄を書く（段 2 の issue と線の約束。段 2 は狭めずに中身を入れる）。指し札の欄は `{type: archon_artifact, run_id, path}` の形。結末の 10 語は report の返す節の `output_format` の enum（今の works の `.shared/core/report.py` の `OUTCOMES` を字のまま）。
  - 仮の `stub.py` は `boundary.returns(<output_format に合う最小の物>)` だけを行う。
  - test-gate と merge は入力 `mode`（`base`・`final`、`seal`・`apply`）を持つ。
- 試験の中身は `engineering.md` の E1・E5・E6・E7 の「機械」の行。`test_archon_validate.py` は Task 1 で置いた家で `archon validate workflows` を走らせ、`works-factory-` の名の行に誤りも警告も無いことを見る。

- [ ] **Step 1: 試験を書く**（E5・E6・E7 は YAML の字の行を読む）
  - `test_block_returns.py`: `test_every_block_returns_one_node`・`test_outcome_field_in_required`・`test_line_reads_only_declared_fields`（線の `$<include の id>.output.<欄>` がそのブロックの `output_format` に在る）・`test_no_unread_return_field`（読み手の無い返りの欄が赤）
  - `test_archon_validate.py`: `test_validate_has_no_warnings_for_ours`
- [ ] **Step 2: 赤**: `python3 -m unittest discover -s tests/layers -t . -v`
- [ ] **Step 3: YAML と仮の script を書く**。往復の `loop_group` に include を置けるかは未決 U4。置けなければ往復は段 1 の課題として、段 0 は 1 回だけ回す形にし、その旨を YAML のコメントと `docs/design.md` の U4 に書く
- [ ] **Step 4: 緑**。加えて `archon workflow run works-factory-line --dry-run`（v0.11.1 の筋書きの試し）が通るかを見て、結果を `docs/design.md` の U3 に書く
- [ ] **Step 5: commit**: `git commit -m "feat(workflows): 線の骨組みと仮のブロック"`

### Task 5: 人の打つ口

**Files:**
- Create: `bin/start`・`bin/answer`・`bin/show`・`bin/apply`（Python の実行ファイル。中身は `bin/_lib/cli.py` を呼ぶだけ）・`bin/_lib/cli.py`
- Test: `tests/bin/test_cli.py`

**Interfaces:**
- Consumes: Task 1 の `pack.load`・`place.*`
- Produces:
  - `cli.start(target: Path, request: str, archon: Callable[[list[str]], str]) -> str`（配置してから `archon workflow run works-factory-line` を起こし、run の id を返す）
  - `cli.answer(run_id: str, text: str, archon) -> None`・`cli.show(run_id: str, archon) -> str`・`cli.apply(run_id: str, target: Path) -> None`（merge の返りの指し札の差分を、封じた hash を照らしてから `git apply` する。違えば止まる）
  - 認証の既定: ホストの `gh` と Claude のログインをそのまま引き継ぐ（Archon は既定で `claude /login` の認証を使う。Archon の `.env.example` の `CLAUDE_USE_GLOBAL_AUTH`）。呼んだ側の環境の API キー・ゲートウェイの資格もそのまま渡す。資格を環境変数で役に渡さない。
  - 選べる道（持ち主の決め `others-may-use`・E14）: Claude のアカウントを名で選ぶ（macOS の keychain の項目の名か `CLAUDE_CODE_OAUTH_TOKEN`。選んだ時はそれより上に効く資格を子に渡さない）。GitHub のアカウントを名で選ぶ（`gh auth token -u <名>`）。Archon の家の置き場を選ぶ。値は利用者の設定（リポジトリの外）か引数で渡す。どの出どころの認証で起こしたかを 1 行出す（認証の落ちと役の返事の不良を見分けるため）。
  - これが入ったら、ASF もこの入口から起こす（工程の名で選び分ける）。今の仮の殻 `~/.local/state/works-factory/bin/asf-env` は捨てる。
- 持ち主の居ない `running` の扱い（埋め P1）は段 1 で足す。段 0 の `show` は Archon の状態をそのまま出す。

- [ ] **Step 1: 試験を書く**（偽の `archon` 関数で引数を記録）
  - `test_start_places_then_runs`: 配置が先、次に `workflow run works-factory-line`
  - `test_apply_refuses_changed_diff`: 封じた hash と違う差分で止まり、対象の木は変わらない
  - `test_apply_applies_sealed_diff`: 同じなら当たる
- [ ] **Step 2: 赤**: `python3 -m unittest tests.bin.test_cli -v`
- [ ] **Step 3: 実装**
- [ ] **Step 4: 緑**。全部の試験 `python3 -m unittest discover -s . -t .` が緑
- [ ] **Step 5: commit**: `git commit -m "feat(bin): start・answer・show・apply"`

## 段 0 の終わりの確かめ

- [ ] 全部の試験が緑。見送りは Archon の実行ファイルが無い時だけ。
- [ ] `docs/design.md` の U3・U4 に分かった事を書いた。
- [ ] `docs/archon-polyfills.md` の行と `workflows/.shared/` が揃う（`test_polyfills_listed`）。
