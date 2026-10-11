<!-- coldwrite:skip このリポジトリの作りの決まり。語は docs/design.md の「語」の節で定義 -->
# engineering.md（このリポジトリの作りの決まり）

コードを書く前と審査の前に読む。審査で指摘する時は決まりの番号（`E1` など）を引く。ここに無い好みは指摘しない。

- 層は 4 つ: 入口 `bin/`・グラフ `workflows/`（持ち主の言うエッセンス。線とブロックの YAML・役の指示書・節の script）・境 `workflows/.shared/`（Archon の入出力の口と埋めだけ）・助け手 `lib/`（Archon を知らない Python）。絵と理由は `docs/design.md`。
- 「機械」の行は、その決まりを守らせる試験。今は予定（土台の計画 `docs/plans/2026-10-11-foundation.md` で作る）。
- 試験で縛れない決まりは「人が見る」と書く。審査の目が引く。

## リポジトリの形

ファイルを足す前に、ここで置き場を決める。ここに無い置き場を足すのは E10。

```text
works-factory/
├── bin/                         入口。人が打つ口（start・answer・show・apply）と起動の殻
│   └── _lib/                    入口の中身。版の取り寄せと配置・起動の認証と隔離・プラグインの選び（E15）
├── workflows/                   グラフ（エッセンス）。バイトのまま Archon の家の workflows/works-factory/ に置く（E1）
│   ├── line/
│   │   ├── works-factory-line.yaml   線。ブロックを並べ、人の関所を置く
│   │   └── fixtures/                 線の筋書きの試験
│   ├── <ブロック>/              judge・plan・plan-review・fix・test-gate・eyes・report・merge の 8 つ
│   │   ├── works-factory-<ブロック>.yaml   ブロックの工程（工程の名もこれ。E9）
│   │   ├── commands/            役の指示書の本文
│   │   ├── scripts/             script の節。lib/ と境の口を呼ぶだけ
│   │   └── fixtures/            Archon の筋書きの試験
│   └── .shared/                 境。Archon との出入りの口 1 つと埋め（E2）
├── lib/                         助け手。Archon を知らない Python（E3）
│   └── tests/                   lib/ の試験
├── tests/                       lib/ 以外の試験
│   ├── layers/                  層の決まりの試験（この文書の「機械」の行）
│   ├── bin/                     入口の試験
│   ├── shared/                  境の試験
│   └── e2e/                     小さな対象のリポジトリの種と、通しの試験
├── docs/
│   ├── design.md                設計（線・ブロック・能力の棚卸し・未決）
│   ├── owner-decisions.md       持ち主の決めの正本
│   ├── asf-notes.md             ASF から採った型
│   ├── archon-polyfills.md      埋めの名簿
│   └── plans/                   実装の計画
├── .github/workflows/tests.yml  CI。check の名は tests
├── pack.json                    版の止め（Archon・ASF）
├── .gitignore
├── MISSION.md・engineering.md・README.md
└── ASF の取り付け命令が置いた物（持ち主の決め asf-installer-in-repo。E8）
    ├── factory/・FACTORY.md・FACTORY_RULES.md     手を加えない
    ├── harness/                 END-TO-END.md・harness.config.json・runtime.inputs.json・runtime.scenario.json だけ書く。ほかは手を加えない
    └── .factory/holdout/HOLDOUT.md                書く
```

- 試験を置くフォルダには全部 `__init__.py` を置く（無いと Python 3.12 の unittest は黙って見つけない）。試験は根から `python3 -m unittest discover -s . -t .` の 1 つで走る。
- 機械: `tests/layers/test_layout.py`（根の直下のファイルとフォルダが上の木に在る物だけ。`workflows/` の直下が `line/`・8 つのブロック・`.shared/` だけ。各ブロックが `works-factory-<ブロック>.yaml` を持つ。試験のフォルダに `__init__.py` が在る）。

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
- ブロックの間は `with:` と返りの構造体だけで渡す。飛ばされうる段の返りは、受ける側の `with:` に `{ from: "$<id>.output.<欄>", if_skipped: null }` を書く（ASF の `W/ship/archon-ship.yaml`:148）。並べた物の集まりは `fan_out:` の返り（入力の順の配列）で受ける。
- 型つきの成果物の一覧（`$TYPED_ARTIFACTS_FILE`）を読むのは report ブロックだけ。輪の返りは最後の 1 周しか残らないので、全部の周の記録（試験の関門の認証・認めた元からの赤・範囲の外の所見）を拾うのに使う（ASF の `W/.shared/report.ts`:130-140 と同じ）。引く時は include の頭（`<include の id>__`）と `loopGroupPath` で自分の分だけに絞り、一覧の `errors` を捨てない（読めた分と一緒に返す）。読む部品は report ブロックの中に置く。
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
- 機械: `tests/layers/test_names.py`（E18 と同じ試験）。

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

## E15 起動の認証と隔離は今の works から持ってきた物を使う

- Archon の実行ファイルの版の固定と指紋の確かめと置き場の隔離（今の works の `works/dev/archon.sh`）、認証の切り替え（`works/.shared/core/auth_launch.py`・`claude_auth.py`）、隔離した Claude に見せるプラグインの選び（`works/dev/toolset.py`）を、その試験ごと `bin/_lib/` に持ってくる。作り直さない。持ち主の決め `bring-launch`。
- 今の works の打つ口（`works/dev/use.sh`・`lib.sh`・`launch.py`）は持ってこない。Archon の CLI と `bin/` の薄い口で置き換える。
- 持ってきた物の中の、今の works だけの事情（写しの同期の説明・works の置き場の名）は、works-factory の言葉に直す。直した所は commit に書く。
- 人が見る。

## E16 人の関所と並べは最新の ASF の形で書く

- 人の関所: 工程に `interactive: true` を書き、関所の節は `approval:`（見せる文 `message` と選び肢 `decisions`）で書く。後ろの節はその答えを `{ from: "$<関所>.output", if_skipped: null }` で受ける（ASF の `W/merge-queue/archon-merge-queue.yaml`:8・179-225）。持ち主の決め `asf-way-gates-fanout`。
- 並べ: `fan_out:`（`items`・`as`・`max_parallel`・`join`）で書く（ASF の `W/verify-runtime-suite/archon-verify-runtime-suite.yaml`:27-34）。作業ツリーに書く並べ（fix の組）は、組ごとに子の run を起こして作業ツリーを分ける。子の run が自分の作業ツリーを持つかは段 1 で実測する（`docs/design.md` の U8）。待ちの列・固定の枝の数・錠は持たない（持ち主の決め `no-queue`）。
- 機械: `tests/layers/test_gates.py`（`approval:` の節を持つ YAML に `interactive: true` が在る）。並べの形は人が見る。

## E17 対象のリポジトリには差分を置くだけ

- merge ブロックの既定は、封じた差分を run の置き場に置くだけ。対象のリポジトリに当てるのは人で、`bin/apply` が封じた hash を照らしてから当てる。PR を作る・merge する動きは、使う人が選んだ時だけ働く道にする。対象のリポジトリごとにレビューと merge の決まりと権限が違うため（持ち主の決め `diff-only-to-target`・`others-may-use`）。
- ASF が PR を merge するのは、ASF がこのリポジトリ（works-factory）を作る時だけ。
- 人が見る。

## E18 取ってきた物と自分の物を名前で見分けられるようにする

- 取ってきた物は元の名前と場所のまま置き、名前を変えない。ASF の物は `factory`・`FACTORY`・`harness`・`.factory`・`archon-` で始まる。Archon の家では、ASF の工程は `workflows/asf/`、自分の工程は `workflows/works-factory/` に分けて置く。持ち主の決め `name-by-origin`。
- 自分の物には、それらで始まる名前を付けない（ファイル・フォルダ・工程・型の名）。自分の工程は `works-factory-` で始める（E9）。
- 今の works から持ってきた物（E15）は、元と同じファイル名で置く。元と見比べられるようにするため。どこから持ってきたかは commit に書く。
- 機械: `tests/layers/test_names.py`（`bin/`・`workflows/`・`lib/`・`tests/`・`docs/` の下のパスの部分に、`factory`・`harness`・`archon-` で始まる物が無い。ASF の物が「リポジトリの形」の木の場所の外に無い）。

