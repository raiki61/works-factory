<!-- coldwrite:skip AI 向けの決まり。語は docs/design/README.md の頭の語の一覧で定義 -->
# pack（`workflows/`）の決まり

block と graph の YAML・AI のノードへの指示の md・script・`src/`・`.shared/` を書く時に読む。リポジトリ全体の決まりは根の `AGENTS.md`。設計の正本は `docs/design/README.md`、block ごとの設計書は `docs/design/<block>.md`。

- block を名指す依頼（例「world check」「世界の解」は `workflows/world/`、設計書は `docs/design/world.md`）は `workflows/<block>/` と `tests/blocks/<block の名の - を _ にした物>/` で閉じる。
- 「全部の役」「どの役も」と言う依頼は pack の全部の役のこと。役が共に読む決まりは `.shared/prompts/` の断片 1 本で閉じる（断片の名は `.shared/AGENTS.md`）。

## 憲法

1. YAML はつなぐだけ。値はコードが計算し、判断は AI がする（Archon の憲法の "YAML coordinates. Code computes. Agents judge."）。
2. AI のノードの指示は、そのノードの md 1 本に英語で書く。Python は指示の文を持たず、md の `{name}` に値を渡す。
3. block は宣言した port だけで受け渡しし、ほかの block を名指さない。つなぐのは graph だけ。
4. 1 つの block だけが使うコードは、その block のフォルダに置く。`lib/` には 2 つ以上の block が使う物だけを置く。
5. どの block も、文とリポジトリだけで単独で回る。block ごとの standalone の fixture で確かめる。
6. 機械の検査は yes/no の形の決まりだけにする。数の上限や許す物の表では縛らず、間違った書き方を API と置き場の形で書けなくする。

## 変更の種類ごとに閉じる所（`docs/design/README.md` の 1.2）

- 指示の文だけを変える（I）: その node の `prompts/<node-id>.md` 1 本。同じ block の 2 つ以上の node が使う文は `prompts/parts/<name>.md`、2 つ以上の block が使う文は `.shared/prompts/<name>.md`（`.shared/AGENTS.md` の名の一覧も試験も直さない）。返す形・`src/`・試験・設計書は、依頼が返す形や検査を変えると言う時だけ触る。
- 受け付けに確かめを足す（A）: その block の `src/` の受け付け・`prompts/<node-id>.md` の 1 段落・`tests/blocks/<block>/`・設計書の受け付けの所（受け付けの決まりが変わる）。`fixtures/` は触らない（筋書きは完了・`reached`・指示の字だけを見るので、拒否を足しても通る）。
- 不具合を直す（B）: その block の `src/`（と `scripts/`）と `tests/blocks/<block>/`。設計書と、共通の口（`.shared/` の `requestrows.py`・`ports.py`）・形・断片は、原因がそこに見えても直さない（出力の形は設計書に決めてあり、直すのはそれに合わせる block のコード）。
- 入力を足す（P）: 受け手の block の `inputs:`・`schemas/`・それを読む script と `src/`・`prompts/`・`tests/blocks/<block>/`。既定値つきの任意の入力なら、今の呼び手（graph）と根の README の例はそのまま回るので触らない。graph の `with:` は、その graph から値を渡すと依頼が言う時だけ足す。設計書の port の所は直す（port が変わる）。
- 観点を足す（N）: 新しい block のフォルダ `workflows/<block>/`・`tests/blocks/<block の名の - を _ にした物>/`・`docs/design/<block>.md`。graph の `with:` と include は、つなぐと依頼が言う時だけ。根の README は触らない（単独で回す例は world の 1 つで足りる。新しい block の単独の呼び方は設計書の「単独で呼ぶ」の所に書く）。
- 2 つ以上の block が使う助け: Archon の pointer・`INPUTS_`・place を解く所は `.shared/` の口、解いた後のパスや値を受ける所は `lib/` の新しいモジュール（`.shared/AGENTS.md` の「`.shared` と `lib/` の分け」）。助けを置くだけの依頼では、使い手の block の `scripts/`・`src/` は触らない（使い始めは、その block を名指す別の変更で）。
- 承認ノード・無人の方針・深さの表・計画の往復を変える（U・D）: line の `src/`（`docs/design/line.md`）。未知の種類 → 段の表は head-depth の `src/`。
- block の中で閉じる変更では、設計書 `docs/design/<block>.md` は port・node の並び・受け付けの決まりが変わる時だけ直し、筋書き（`fixtures/`）は通らなくなった時だけ直す。設計書は md の本文を写さない（本文の正本は block の `prompts/`）。

## 始め方

- 新しい block は `workflows/world/` を写して始める（手本は 1 つ）。graph の手本は `workflows/policy-check/`。
- 設計書は `docs/design/<block>.md` に 1 本。型は `docs/design/README.md` の 6 章、手本は `docs/design/world.md`。
- 置き場の形は `docs/design/README.md` の 3 章: `works-factory-<block>.yaml`・`prompts/<node-id>.md`（system prompt は `prompts/<node-id>.system.md`）・`prompts/parts/<name>.md`・`scripts/<name>.py`・`src/`（package の名は `src`）・`schemas/<port>.schema.json`・`fixtures/standalone.stubs.yaml`。
- 入力・place・指示は `.shared/` の口（`ports.py`・`prompt.py`・`requestrows.py`）を通して書く。口の一覧と、共通の断片・共通の port の形の名は `.shared/AGENTS.md`。
- YAML に指示の文を書かない: `loop:` の node・`agents:`・`on_reject` と `decisions` の `rework` の `prompt` は使わない（`loop_group` と prep で書く）。
- 試験は `tests/blocks/<block の名の - を _ にした物>/`。助けは `tests/blocks/kit.py`。筋書きで届かない AI の node（`workflow:` の `fan_out:` の先・loop の 2 周目だけに回る node）の指示は、block の試験 `test_prompts.py` の表 `RENDERED` に行を置いて照らす。
- 単独で回す: `bin/works-factory workflow run works-factory-<block> --cwd <対象> --input <名>=<値>`。
- 機械: `tests/layers/test_block_shape.py`（`docs/design/README.md` の 7.1 の yes/no）。

## E1 YAML は変換せずに Archon に渡す

- `workflows/` の YAML は手で書き、`bin/` は写さずに Archon に読ませる（`--workflow-source` に渡す置き場の `.archon/workflows/works-factory` がこのフォルダを指す pack の形。`bin/_lib/place.py`）。生成・前処理・鍵の削りをしない。
- Archon の確かめ（`archon validate`）が警告なしで通る。数えない警告は、同梱の skill と借りる superpowers の skill を `skills:` に名指した時の「ディスクに無い」の 1 つの形だけ（訳は `docs/design/archon.md`）。
- 機械: `tests/layers/test_no_conversion.py`・`tests/layers/test_archon_validate.py`・`tests/layers/test_block_shape.py` の `ArchonCase`。

## E2 `.shared/` の中身は口と埋めだけで、埋めは名簿に載せる

- `.shared/` のファイルは、Archon との出入りの口（`ports.py`・`prompt.py`・`requestrows.py`）・2 つ以上の block が使う断片と形（`prompts/`・`schemas/`）・埋め（polyfill。Archon に無い物を外から補う部品）だけ。
- 埋めは `docs/polyfills.md` に 1 行ずつ載せる（穴・Archon の証拠の引用・外す条件）。置き場を持たない埋め（YAML の型・期限の値）も載せる。`bin/_lib/` の埋めでない入口の部品は `tests/layers/scan.py` の `ALLOWED["E2"]` に訳つきで置く。
- 機械: `tests/layers/test_polyfills_listed.py`・`tests/layers/test_polyfill_evidence.py`。

## E4 block はほかの block のファイルを指さず、入力の説明で作り手を名指さない

- block の `scripts/`・`src/` は、ほかの block のフォルダへのパスを組まず、run directory の根（`ARTIFACTS_DIR`）を読まない。受け取りは `with:` の入力（`ports` の form の口）と、作り手の出力の欄の pointer だけ。place のファイルの名はその block の `src/` だけが持つ。
- 入力の `description:` は `<form>: <意味>` で受け取る値の形と意味を書き、作り手（ほかの block・graph のノード）を名指さない。結びは graph の `with:` だけが持つ（持ち主の決め `io-in-output-format`）。
- script は同じ `scripts/` の別の script を import しない（共に使う物は `src/`）。script の名を `lib/` のモジュールと `.shared/` の口の名にしない。
- 機械: `tests/layers/test_block_shape.py`（7.1 の 5・7・9）・`tests/workflows/test_script_imports.py`。入力の説明が作り手を名指さないことは人が見る。

## E5 block の出力は 1 つのノードの構造体

- block の YAML は `returns:` で 1 つのノードを名指し、`outcome_field:` で仕事がうまくいったかの欄を名指す。返りの `output_format` には `report`（報告に載せる日本語の行の配列）を置く。block の間で渡す物の型の正本は、そのノードの `output_format` と graph の `with:` だけ（持ち主の決め `io-in-output-format`）。
- 大きい中身はファイルに置き、出力には pointer `{type: archon_artifact, run_id, path}` を入れる。作り手の欄を 3 つ以上読む受け手は、返りを丸ごと置いたファイルの pointer 1 つで受ける（`docs/design/README.md` の 4.2）。
- 飛ばされうる段の出力は、受ける側の `with:` に `{ from: "$<id>.output.<欄>", if_skipped: null }` で受ける。include の受け手へ束ねて渡す時は、graph の中継の script のノードで受けてから渡す（埋め P2）。
- 機械: `tests/layers/test_block_returns.py`・`tests/layers/test_block_shape.py`（7.1 の 8）。

## E6 外への書き込みは 1 つの script のノードで、書いた後に読み戻す

- GitHub・対象のリポジトリの main・人に見える所への書き込みは、block ごとに 1 つの `script:` のノードだけが行う。書いた後に読み戻し、読めた値で返る。終了の値 0 は書けた証拠にしない。
- 機械: `tests/layers/test_outward_write.py`。読み戻しの有無は人が見る。

## E7 読むだけのノードは mutates_checkout: false を書く

- 作業ツリーを変えないノード（読むだけの役と、読むだけの script）は `mutates_checkout: false` を書く。AI のノードの印は道具から決まる（Bash・Edit・Write の無い役は書く）。Bash を持ち Edit・Write を持たない役は `sandbox.filesystem.denyWrite` に起動が隔離した Archon の家を書く（埋め P5 の印を兼ねる）。
- AI のノードは `settingSources: [user]`・閉じた `sandbox`・道具の表の中の `allowed_tools` を持ち、`model` は群の名（`lib/launchgroups.py`）を書いて `effort` を書かない。グラフの根にも `effort` を書かない。
- `runtime: uv` の script は頭に uv の script の宣言（PEP 723 の 4 行）を置く。
- 訳と Archon の振る舞いは `docs/design/archon.md`。
- 機械: `tests/layers/test_readonly_nodes.py`・`tests/workflows/test_uv_scripts.py`・`tests/layers/test_block_shape.py` の `RealTreeCase`。

## E12 期限・タイムアウトを置かない

- YAML のノードにも script にも期限を置かない。止める時は止め札で止める。持ち主の決め `no-timeouts`。書かなくても既定の期限が当たる鍵（AI のノードと `loop:` の `idle_timeout`・`wait:` の `deadline_ms`）には実質無しの値 `1728000000` を書く（埋め P14。鍵ごとの訳は `docs/design/archon.md`）。
- 機械: `tests/layers/test_no_timeouts.py`。

## E16 承認ノードと並べは最新の ASF の形で書く

- 承認ノードは `wait:` の `attention` を `form: select` で書き、`options` に答えの語（`lib/answer.py` の `GO_WORDS`・`STOP_WORDS`）を全部並べる。後ろのノードは答え `{decision, text}` を `{ from: "$<承認ノード>.output", if_skipped: null }` で受ける。`approval:` とグラフの頭の `interactive:` は書かない。ループの本体に承認ノードを置かない。持ち主の決め `asf-way-gates-fanout`。
- 筋書きが承認ノードを通る時は、その承認ノードの答えを stub に書く。
- 並べは `fan_out:` で書く。作業ツリーに書く並べ（fix の組）は組ごとに子の run を起こして作業ツリーを分ける。待ちの列・固定の枝の数・錠は持たない（持ち主の決め `no-queue`）。
- 機械: `tests/layers/test_gates.py`。並べの形は人が見る。

## E17 対象のリポジトリには差分を置くだけ

- merge の既定は、封じた差分を run の place に置くだけ。対象のリポジトリに当てるのは人で、`bin/apply` が封じた hash を照らしてから当てる（持ち主の決め `diff-only-to-target`・`others-may-use`）。
- 選べる道は出口の語（入力 `deliver`。語の一覧は `lib/entry.py` の `DELIVERS`）で選ぶ。今の語は空と `pr` だけ。`pr` の道は merge の中の 2 つだけで作り、push と PR の作成は Archon 同梱の `archon-pr` に任せる（持ち主の決め `deliver-via-archon-pr`）。対象の既定の枝へは push しない。周の鎖の子は PR を作らず、鎖の親が最後に 1 本だけ作る。
- 設計は `docs/design/merge.md`。
- 機械: `tests/blocks/merge/`・`tests/blocks/chain/`・`tests/shared/test_archon_contract.py` の `ArchonPrTest`・`tests/bin/test_launcher.py`。対象が守るほかの枝は人が見る。

## E19 AI ノードの出し直しは Archon の retry で持つ

- AI ノード（`loop_group` の本体の中も）は `retry: {max_attempts: 2, on_error: all}` を持つ。`loop_group` のノードそのものには書かない。2 回走ると困るノードだけ外し、ノードの頭の行の真上に `# retry なし: <理由>` を 1 行で書く。工場の側に自前の出し直しを作らない。
- 機械: `tests/layers/test_role_retry.py`。

## E20 深さの段は表 1 か所に置き、when の句で飛ばさない

- run の頭の深さの段（軽量・標準・重厚）の定義は line の `src/tiers.py` の `TIERS` 1 か所。`docs/design/line.md` の「深さの段の表」はその写しで、行は `TIERS` と等しい。持ち主の決め `depth-by-reason`・`three-tiers`。
- ノードを深さの値で飛ばさない: どのノードの `when` も、出力の深さの欄を読む句を持たない。省くかを `when:` に渡す時は、line が表から引いた真偽だけにする。計画の壁打ち（plan と plan-review の往復）はどの段でも省かない。
- 機械: `tests/layers/test_depth_skip.py`。
