<!-- coldwrite:skip このリポジトリの作りの決まり。語は docs/design.md の「語」の節で定義 -->
# engineering.md（このリポジトリの作りの決まり）

コードを書く前と審査の前に読む。審査で指摘する時は決まりの番号（`E1` など）を引く。ここに無い好みは指摘しない。

- 層は 4 つ: 入口 `bin/`・グラフ `workflows/`（持ち主の言うエッセンス。線とブロックの YAML・役の指示書・節の script）・境 `workflows/.shared/`（Archon の入出力の口と埋めだけ）・助け手 `lib/`（Archon を知らない Python）。絵と理由は `docs/design.md`。
- 「機械」の行は、その決まりを守らせる試験。今は予定（土台の計画 `docs/plans/2026-10-11-foundation.md` で作る）。
- 試験で縛れない決まりは「人が見る」と書く。審査の目が引く。

## E1 YAML は変換せずに Archon に渡す

- `workflows/` の YAML は手で書き、`bin/` はバイトを変えずに Archon の家（`$ARCHON_HOME/workflows/works-factory/`）に置く。生成・前処理・鍵の削りをしない。
- 作りの規則は Archon の `workflow-language-constitution.md`（v0.11.1 に在る。要点「YAML coordinates. Code computes. Agents judge.」）。YAML は節の順・関所・繰り返し・入出力の配線だけを持つ。値の計算は `script:` の節か役の指示書に置く。
- Archon の確かめ（`archon validate workflows`）が警告なしで通る。
- 機械: `tests/layers/test_no_conversion.py`（置いた物と `workflows/` のバイト一致）・`tests/layers/test_archon_validate.py`（確かめの結果に誤りも警告も無い）。

## E2 境の中身は全部、名簿に載せる

- `workflows/.shared/` のファイルは 2 種類だけ。Archon との出入りの口（境の入出力のモジュール。1 つ）と、埋め（polyfill。Archon に無い物を外から補う部品）。
- 埋めは `docs/archon-polyfills.md` に 1 行ずつ載せる。載せる欄は、穴・Archon の証拠の引用・外す条件。
- 機械: `tests/layers/test_polyfills_listed.py`（`workflows/.shared/` のファイルが、境の口か名簿の行のどれかにちょうど当たる。名簿に在って木に無い行も赤）。

## E3 lib/ は Archon を知らない

- `lib/` は script の節が呼ぶ Python の助け手だけを持つ（引用の照らし・TDD の赤の判定・元から赤の見分け・範囲の照らしなど）。流れ（どの確かめを・どの順で・どこで人に聞くか）・役の指示書・ブロックの間で渡す物の型は持たない。それはグラフ（`workflows/`）と `docs/design.md` だけが持つ。
- `lib/` は Archon の名（`archon`・`$ARTIFACTS_DIR`・`$TYPED_ARTIFACTS_FILE`・`ARCHON_` で始まる環境変数・節の id・`output_type` の語）を書かない。入力は引数とファイルのパス、出力は返り値と JSON。
- 機械: `tests/layers/test_lib_blind.py`（上の語の字の形が `lib/` に 1 つも無い。`import` に `workflows` と `bin` の中の物が無い）。
- 外のパッケージは使ってよい（持ち主の決め `outside-packages-ok`）。版を止め、依存の宣言は 1 か所に置く。どこに置くか（`pyproject.toml` と節の `deps:` をどう 1 つにするか）は土台の計画の Task 2 で決める。

## E4 ブロックはほかのブロックのファイルを指さない

- ブロック（`workflows/<名>/`）の script は、ほかのブロックのフォルダへのパスを組まない。受け取りは `with:` の入力・前の節の返り・指し札（`archon_artifact`）・型つきの成果物（`output_type`）だけ。
- ブロックの script は `lib/` と境の口を呼ぶだけで、確かめの中身を持たない。
- 機械: `tests/layers/test_block_paths.py`（ブロックの script の字に、ほかのブロックの名と、`lib/`・`workflows/.shared/` の外への相対パスが無い）。

## E5 ブロックの返りは 1 つの節の構造体

- ブロックの YAML は `returns:` で 1 つの節を名指す。ブロックの間で渡す物の型の正本は、その節の `output_format`（素の JSON Schema）と、線の `with:` だけ。写しの型は持たない（持ち主の決め `io-in-output-format`）。
- 大きい中身はファイルに置き、返りには指し札 `{type: archon_artifact, run_id, path}` を入れる。
- 集まりは `output_type` の型つきの成果物で渡し、受け手は型で引く。引く時は include の頭（`<include の id>__`）と `loopGroupPath` で自分の分だけに絞り、一覧の `errors` を捨てない（読めた分と一緒に返す）。
- 仕事の結末を表す欄は `outcome_field:` で名指す。run が終わったことと仕事がうまくいったことは別の事実。
- 機械: `tests/layers/test_block_returns.py`（全ブロックに `returns:` と `outcome_field:` が在り、返す節が `output_format` を持ち、`outcome_field` の欄がその `required` に在る。線の `with:` が読む `$<include の id>.output.<欄>` は、そのブロックの返す節の `output_format` の欄に在る。読み手の無い返りの欄も赤）。

## E6 外への書き込みは 1 つの script の節で、書いた後に読み戻す

- GitHub・対象のリポジトリの main・人に見える所への書き込みは、ブロックごとに 1 つの `script:` の節だけが行う。書いた後に読み戻し、読めた値で返る。終了の値 0 は書けた証拠にしない。
- 機械: `tests/layers/test_outward_write.py`（`gh`・`git push`・`git merge` を呼ぶ節がブロックに 1 つ以下。名簿は試験の中の表）。読み戻しの有無は人が見る。

## E7 読むだけの節は mutates_checkout: false を書く

- 作業ツリーを変えない節（判定・計画・事前審査・独立の目・報告の役と、読むだけの script）は `mutates_checkout: false` を書く。Archon は書いた節が作業ツリーを変えたら、その節を落とす。
- 機械: `tests/layers/test_readonly_nodes.py`（ブロック `judge`・`plan`・`plan-review`・`eyes`・`report` の役の節に全部在る。ほかのブロックは試験の中の表で名指した節）。

## E8 ASF は横に並べて見るだけ

- ASF と Archon 同梱の工程を `include:`・`workflow:` で呼ばない。ASF のコードを自分の層（`bin/`・`workflows/`・`lib/`）に写さない。採るのは型（なぜその形か）だけ。
- ASF の取り付け命令が置いた物（`factory/`・`harness/`・`FACTORY.md`・`FACTORY_RULES.md`・`.factory/`）は、ASF がこのリポジトリを作るための物で、4 つの層の外に置いたまま手を加えない。ASF の共有の工程への決まりは `factory/WORKFLOW_POLICY.md`。持ち主の決め `asf-installer-in-repo`。
- ASF の型を採ったら、`docs/asf-notes.md` に 1 行足す（ASF の commit・ファイル・採った先のブロック・違いと訳）。
- 機械: `tests/layers/test_no_asf.py`（`include:`・`workflow:` の値が `works-factory-` で始まる）。写していないことと名簿の行は人が見る。

## E9 工程の名は archon- で始めない

- 工程の名は `works-factory-<フォルダの名>`。線は `works-factory-line`。Archon の家で ASF（`archon-*`）と並んでも名前で選び分けられる。
- 機械: `tests/layers/test_names.py`。

## E10 4 つの層の外に仕組みを足す前に、持ち主の決めを書く

- 新しい層・置き場・常駐する仕組みは、先に `docs/owner-decisions.md` に持ち主の言葉つきで決めを書いてから足す。
- 人が見る（審査の目が `docs/owner-decisions.md` の行を探す）。

## E11 仕組みを足す前に 3 つを確かめる

1. Archon が持っているか（v0.11.1 の文書と、`docs/design.md` の「Archon の分かっていること」）。
2. ASF が持っているか（`docs/asf-notes.md` と、置いた `workflows/asf/`）。
3. 本当に要るか（今の works の能力の一覧 `docs/design.md` の「能力の棚卸し」のどれに当たるか）。

- 計画の文書に 3 つの答えを書く。人が見る。

## E12 期限・タイムアウトを置かない

- YAML の節にも script にも期限を置かない。止める時は止め札で止める。持ち主の決め `no-timeouts`。
- Archon は鍵を書かない節にも既定の期限を当てる（`script:` の節は 2 分で打ち切る。Archon の文書 `guides/script-nodes.md` の `timeout`「Default: `120000`」）。だから期限を外すには、期限を持つ節（`script:`・`bash:` の `timeout` と AI の節の `idle_timeout`）に、実質無しの値 `1728000000`（ミリ秒で 20 日。今の works と同じ値）を書く。
- 機械: `tests/layers/test_no_timeouts.py`（`workflows/` の YAML で、期限を持つ節の `timeout`・`idle_timeout` が全部 `1728000000`）。

## E13 対象の言語を知らない

- 役の指示書（`workflows/*/commands/`）と `lib/` に、特定の言語・テストの実行器の名を書かない。事実上の標準の形式（JUnit XML など）は名指してよい。持ち主の決め `lang-neutral`。
- 機械: `tests/layers/test_lang_neutral.py`（言語と実行器の名の語の表に当たる字が無い。表は試験の中）。

## E14 既定の道は普通の利用者の環境でそのまま動く

- 普通の利用者とは、Claude Code に `claude /login` しただけの人・macOS 以外の人・API キーや会社のゲートウェイを使う人など。持ち主の決め `others-may-use`。
- 持ち主の環境（Claude のアカウントの名・keychain の項目の名・GitHub のアカウントの名・置き場のパス）はリポジトリに書かない。選べる道として置き、値は利用者の設定（リポジトリの外）か起動の引数で渡す。
- 何かを削る・落とす直しは、持ち主の環境で要らないかだけでなく、普通の利用者の環境で要らないかを書く。人が見る。
- 機械: `tests/layers/test_no_owner_env.py`（`bin/`・`workflows/`・`lib/` に、持ち主の環境の字（`raiki61`・`claude-code-oauth-`・`/Users/`）が無い）。
