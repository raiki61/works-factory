<!-- coldwrite:skip AI 向けの決まりの正本。語は docs/design/README.md の頭の語の一覧で定義 -->
# AGENTS.md（works-factory の AI 向けの決まり）

works-factory は、修正依頼を受けて確かめ済みの変更と報告を返す工場。Archon（AI の処理をグラフにして YAML で書いて回す道具）の上で動く。目的と範囲は `MISSION.md`、設計の正本は `docs/design/README.md`（block ごとの設計書は `docs/design/<block>.md`）、持ち主の決めの正本は `docs/owner-decisions.md`。

## 憲法

1. YAML はつなぐだけ。値はコードが計算し、判断は AI がする（Archon の憲法の "YAML coordinates. Code computes. Agents judge."）。
2. AI のノードの指示は、そのノードの md 1 本に英語で書く。Python は指示の文を持たず、md の `{name}` に値を渡す。
3. block は宣言した port だけで受け渡しし、ほかの block を名指さない。つなぐのは graph だけ。
4. 1 つの block だけが使うコードは、その block のフォルダに置く。`lib/` には 2 つ以上の block が使う物だけを置く。
5. どの block も、文とリポジトリだけで単独で回る。block ごとの standalone の fixture で確かめる。
6. 機械の検査は yes/no の形の決まりだけにする。数の上限や許す物の表では縛らず、間違った書き方を API と置き場の形で書けなくする。

## 読み方

- コードを書く前と審査の前に、この文書と、触るフォルダとその上の階層の `AGENTS.md` を読む。審査で指摘する時は決まりの番号（`E1` など）か憲法の番号を引く。書いてない好みは指摘しない。
- AGENTS.md には決まりとパスだけを書く。決まりを守らせる試験の細目はその試験の docstring に、設計の細目は `docs/design/` に置く（持ち主の決め `rules-tests-design-apart`）。各決まりの「機械」の行がその試験を名指す。試験で縛れない決まりは「人が見る」と書く。
- 試験を足す・不具合を直す前に、仕組みで照らせないかを見る。場面ごとの自前の試験を継ぎ足さない（持ち主の決め `mechanism-over-tests`。試験の細目は `tests/AGENTS.md`）。
- `CLAUDE.md` を置かない。Claude Code は `CLAUDE.md` が在ると `AGENTS.md` を読まない（持ち主の決め `agents-md-per-level`）。
- 文書は日本語。ただし根の `README.md` は英語の 1 版（持ち主の決め `readme-english`）。AI のノードへの指示の md は英語（`prompts-english`）。
- スキル（SKILL.md）やコマンドを書く・直す前に https://github.com/raiki61/claude-plugins/blob/main/docs/standards/skill-authoring.md を読む。
- 元の works（このリポジトリの前の形。`raiki61/claude-plugins` の `works/`、版は `pack.json` の `works.commit`）は参照するだけで、作り直しの目標ではない。元に在って工場に無い物は、工場の git の履歴で意図して外したかを確かめてから戻すかを決める（持ち主の決め `read-original-works`・`lib-port-ended`）。

## 決まりの置き場

| 番号 | 置き場 |
| --- | --- |
| E1 | `workflows/AGENTS.md` |
| E2 | `workflows/AGENTS.md` |
| E3 | `lib/AGENTS.md` |
| E4 | `workflows/AGENTS.md` |
| E5 | `workflows/AGENTS.md` |
| E6 | `workflows/AGENTS.md` |
| E7 | `workflows/AGENTS.md` |
| E8 | `AGENTS.md` |
| E9 | `AGENTS.md` |
| E10 | `AGENTS.md` |
| E11 | `AGENTS.md` |
| E12 | `workflows/AGENTS.md` |
| E13 | `AGENTS.md` |
| E14 | `AGENTS.md` |
| E15 | `bin/AGENTS.md` |
| E16 | `workflows/AGENTS.md` |
| E17 | `workflows/AGENTS.md` |
| E18 | `AGENTS.md` |
| E19 | `workflows/AGENTS.md` |
| E20 | `workflows/AGENTS.md` |
| E21 | `tests/AGENTS.md` |
| E22 | `AGENTS.md` |
| E23 | `workflows/AGENTS.md` |
| E24 | `tests/AGENTS.md` |

## リポジトリの形

ファイルを足す前に、ここで置き場を決める。ここに無い置き場を足すのは E10。各フォルダの `AGENTS.md` はそのフォルダの決まりで、AI の道具が上の階層の物と自動で合わせて読む。

```text
works-factory/
├── bin/                         入口（AGENTS.md が E15）。起動の殻 works-factory（人は Archon の命令をそのまま打つ）と、差分を当てる apply
│   └── _lib/                    入口の中身。Archon の源の取り寄せと起こし方・起動の認証と隔離・プラグインの選び・run の作業ツリーの起点
├── workflows/                   pack（AGENTS.md が憲法と E1・E2・E4〜E7・E12・E16・E17・E19・E20）。置かずに --workflow-source で Archon に読ませる（E1）
│   ├── <block>/                 block 1 つ（観点 1 つ。例 world）。手本は world
│   │   ├── works-factory-<block>.yaml   YAML 1 本（graph の名もこれ。E9）
│   │   ├── prompts/             AI のノードごとの指示の md（<node-id>.md・<node-id>.system.md）と、同じ block の 2 つ以上のノードが使う断片 parts/<name>.md
│   │   ├── scripts/             script のノード（Archon が名で探す）
│   │   ├── src/                 この block だけが使う Python（package の名は src）
│   │   ├── schemas/             json の port の形
│   │   └── fixtures/            筋書き（standalone.stubs.yaml は必ず置く）
│   ├── <graph>/                 block を include でつなぐ graph（line・chain・judge・eyes・policy-check）。形は block と同じ。手本は policy-check
│   └── .shared/                 pack の共通の部品（AGENTS.md が口の一覧）。口 ports.py・prompt.py・requestrows.py・2 つ以上の block が使う断片 prompts/ と形 schemas/・埋め（E2）
├── lib/                         助け手（AGENTS.md が E3）。Archon を知らない Python で、2 つ以上の block（か graph か bin/）が使う物だけ
│   ├── borrow/                  借りた superpowers の写しと固定（borrow.json）・継ぎ目の表（seams.json）・無人の読み替え（unattended.md）。読み口は lib/spseam.py
│   ├── graphloops/engine/       元の graphloops の小道具のうち残る 3 つ（declared.py・schema.py・util.py）
│   └── tests/                   lib/ の試験
├── tests/                       lib/ 以外の試験（AGENTS.md が試験の決まり）
│   ├── layers/                  形と層の決まりの yes/no の試験（各決まりの「機械」の行）。block の形は test_block_shape.py
│   ├── blocks/                  block の試験（tests/blocks/<block の名の - を _ にした物>/。助けは tests/blocks/kit.py）
│   ├── workflows/               pack の YAML と script の形の試験
│   ├── bin/                     入口の試験
│   ├── shared/                  埋めと Archon との約束の試験
│   ├── calibration/             公開ベンチの比べ
│   └── e2e/                     小さな対象のリポジトリの種（target-seed/。__init__.py を置かない）と、通しの試験と筋書き（scenario.json。人が読む要約は scenario.md）
├── docs/
│   ├── design/                  設計。README.md が型（憲法・置き場・port・指示の組み立て・形の検査・keep-essence）、<block>.md が block と graph の設計書、archon.md が Archon の分かっていること
│   ├── owner-decisions.md       持ち主の決めの正本
│   ├── asf-notes.md             ASF から採った型
│   ├── polyfills.md             埋めの名簿（E2）
│   ├── concepts.md・concepts.json   考えの住処の地図と表（対象のリポジトリとして読まれる）
│   ├── layers.json              層の地図（E22）
│   ├── calibration-214.md       #214 の自作の較正の束の比べの記録（束は消した）
│   └── plans/                   実装の計画
├── .github/workflows/tests.yml  CI。check の名は tests（4 つの分けを集める。分けは tests/shard.py）
├── pack.json                    版の止め（Archon の版は factory/pack.json）
├── pyproject.toml               Python の外のパッケージの宣言（1 か所。持ち主の決め outside-packages-ok。lib/AGENTS.md の E3）
├── .gitignore
├── AGENTS.md                    AI 向けの決まり（この文書）。下のフォルダの AGENTS.md と自動で合わさる
├── MISSION.md・README.md
├── engineering.md               ASF の役が読む入口。ここを指すだけ
└── ASF の取り付け命令が置いた物（持ち主の決め asf-installer-in-repo。E8）
    ├── factory/・FACTORY.md・FACTORY_RULES.md     手を加えない。factory/ は consumer.py・pack.json・WORKFLOW_POLICY.md だけ
    └── .factory/holdout/HOLDOUT.md                書く
```

- 試験を置くフォルダには全部 `__init__.py` を置く（無いと Python 3.12 の unittest は黙って見つけない）。run の中の確かめは根からの `tests/changed.py` の 1 つで、全部の試験は CI だけが回す（`tests/AGENTS.md`）。
- 機械: `tests/layers/test_layout.py`。

## E8 ASF は横に並べて見るだけ

- ASF と Archon 同梱のグラフを `include:`・`workflow:` で呼ばない。外しは 1 つだけ: 出口の語 `pr` の時に merge が `workflow:` で起こす `archon-pr`（持ち主の決め `deliver-via-archon-pr`。`workflows/AGENTS.md` の E17）。ASF のコードを自分の層（`bin/`・`workflows/`・`lib/`）に写さない。採るのは型（なぜその形か）だけ。
- ASF の取り付け命令が置いた物（`factory/`・`FACTORY.md`・`FACTORY_RULES.md`・`.factory/`）は、層の外に置いたまま手を加えない（外した物の一覧は持ち主の決め `asf-installer-in-repo`）。ASF の共有のグラフへの決まりは `factory/WORKFLOW_POLICY.md`。
- ASF の型を採ったら、`docs/asf-notes.md` に 1 行足す。
- 機械: `tests/layers/test_no_asf.py`。写していないことと名簿の行は人が見る。

## E9 グラフの名は archon- で始めない

- グラフの名は `works-factory-<フォルダの名>`。メイングラフは `works-factory-line`。
- 機械: `tests/layers/test_names.py`。

## E10 層の外に仕組みを足す前に、持ち主の決めを書く

- 新しい層・置き場・常駐する仕組みは、先に `docs/owner-decisions.md` に持ち主の言葉つきで決めを書いてから足す。
- 人が見る。

## E11 仕組みを足す前に 3 つを確かめる

1. Archon が持っているか（`docs/design/archon.md`）。
2. ASF が持っているか（`docs/asf-notes.md` と、取った Archon の源の `.archon/workflows/sdlc/`）。
3. 本当に要るか（`docs/design/README.md` の 10 章の keep-essence と、block の設計書の「元の works と graphloops の同じ場面」のどれに当たるか）。

- 計画の文書か設計書に 3 つの答えを書く。人が見る。

## E13 対象の言語を知らない

- AI のノードへの指示の md（`workflows/*/prompts/`・`workflows/.shared/prompts/`）と `lib/` に、特定の言語・テストの実行器の名を書かない。事実上の標準の形式（JUnit XML など）は名指してよい。持ち主の決め `lang-neutral`。
- 例外: 拡張子と言語の対応・テストのファイルの名の慣習の表と、その表を作る標準ライブラリの import は、`lib/impact.py`・`lib/changemap.py`・`lib/libdocs.py`・`lib/libdocs_local.py` に限って書いてよい。
- 借りた superpowers の写し（`lib/borrow/superpowers/`）は照らさない（上流の字のままの写しで、固定が 1 字も変えさせない）。
- 機械: `tests/layers/test_lang_neutral.py`。

## E14 既定の道は普通の利用者の環境でそのまま動く

- 普通の利用者とは、Claude Code に `claude /login` しただけの人・macOS 以外の人・API キーや会社のゲートウェイを使う人など。持ち主の決め `others-may-use`。
- 持ち主の環境（Claude のアカウントの名・keychain の項目の名・GitHub のアカウントの名・置き場のパス）はリポジトリに書かない。選べる道として置き、値は利用者の設定（リポジトリの外）か起動の引数で渡す。
- 何かを削る・落とす直しは、持ち主の環境で要らないかだけでなく、普通の利用者の環境で要らないかを書く。人が見る。
- 機械: `tests/layers/test_no_owner_env.py`。

## E18 取ってきた物と自分の物を名前で見分けられるようにする

- 取ってきた物は元の名前と場所のまま置き、名前を変えない。ASF の物は `factory`・`FACTORY`・`harness`・`.factory`・`archon-` で始まる。自分の物には、それらで始まる名前を付けない（持ち主の決め `name-by-origin`）。自分のグラフは `works-factory-` で始める（E9）。
- 元の works から元のまま持ってきた物（`bin/_lib/` の起動の部品など。E15）は元と同じファイル名で置き、どこから持ってきたかを commit に書く。#765 の組み込みで block の `src/` へ移した物には当てない（`lib-port-ended`）。
- 機械: `tests/layers/test_names.py`。ASF の物が上の木の場所の外に無いことは人が見る。

## E22 層は地図に沿って頼る

- 層の地図は `docs/layers.json` の 1 か所。層は起動の殻 `bin/`・メイングラフと周の鎖・block と graph・pack の共通の部品 `workflows/.shared/`・共通の lib `lib/` で、層ごとに頼ってよい層（`may_use`）を書く。
- graph と block（`workflows/`）と `lib/` は `bin/` の物を import しない。Archon の上で動く物は、Archon の外の起動の殻に頼らない。殻の事実が要る時は、殻が組んだ物を env で渡し、その名は読む側の部品が持つ。
- block どうしは互いに頼らない（憲法の 3）。block の `src/` を import してよいのは同じ block の `scripts/`・`src/` と、その block の試験だけ（`lib/` とほかの block は読まない）。
- 機械: `tests/layers/test_lib_blind.py`（lib の向き）・`tests/layers/test_block_shape.py`（ほかの block のフォルダへのパス）。`workflows/` から `bin/` への import は人が見る。
