<!-- coldwrite:skip AI 向けの決まりの正本。語は docs/design.md の「語」のセクションで定義 -->
# AGENTS.md（works-factory の AI 向けの決まり）

works-factory は、修正依頼を受けて確かめ済みの変更と報告を返す工場。Archon（AI の処理をグラフにして YAML で書いて回す道具）の上で動く。目的と範囲は `MISSION.md`、設計は `docs/design.md`、持ち主の決めの正本は `docs/owner-decisions.md`。

- コードを書く前と審査の前に、この文書と、触るフォルダとその上の階層の `AGENTS.md` を読む。審査で指摘する時は決まりの番号（`E1` など）を引く。書いてない好みは指摘しない。
- 「機械」の行は、その決まりを守らせる試験。今は予定（土台の計画 `docs/plans/2026-10-11-foundation.md` で作る）。試験で縛れない決まりは「人が見る」と書く。
- `CLAUDE.md` を置かない。Claude Code は `CLAUDE.md` が在ると `AGENTS.md` を読まない（持ち主の決め `agents-md-per-level`）。
- 文書は日本語。
- 今の works（このリポジトリの前の形。`raiki61/claude-plugins` の `works/`、移す元の版は `pack.json` の `works.commit`）を読めば分かる事は、ここに書き直さず元を読む。確かめの部品の作り・その試験・能力の訳がそれに当たる。移す時は元のファイル名を残す（E18）。持ち主の決め `read-original-works`。役の指示書の中身はこれに当たらない。役の指示書は初見の読み手で詰まりが無くなるまで書き直す。写しの台帳を持つ指示書は、書き直しを台帳の許した直しとして記録する（持ち主の決め `prompts-coldread`）。

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

## リポジトリの形

ファイルを足す前に、ここで置き場を決める。ここに無い置き場を足すのは E10。各フォルダの `AGENTS.md` はそのフォルダの決まりで、AI の道具が上の階層の物と自動で合わせて読む。

```text
works-factory/
├── bin/                         入口（AGENTS.md が E15）。起動の殻 works-factory（人は Archon の命令をそのまま打つ）と、差分を当てる apply
│   └── _lib/                    入口の中身。Archon の源の取り寄せと起こし方・起動の認証と隔離・プラグインの選び（E15）
├── workflows/                   グラフ（エッセンス。AGENTS.md がグラフの決まり）。置かずに --workflow-source で Archon に読ませる（E1）
│   ├── line/
│   │   ├── works-factory-line.yaml   メイングラフ。サブグラフを並べ、承認ノードを置く
│   │   ├── scripts/                  メイングラフの script ノード。lib/ と境の口を呼ぶだけ
│   │   └── fixtures/                 メイングラフの筋書きの試験
│   ├── <サブグラフ>/            judge・plan・plan-review・fix・test-gate・eyes・report・merge の 8 つ
│   │   ├── works-factory-<サブグラフ>.yaml   サブグラフの YAML（グラフの名もこれ。E9）
│   │   ├── commands/            役の指示書の本文
│   │   ├── scripts/             script ノード。lib/ と境の口を呼ぶだけ
│   │   └── fixtures/            Archon の筋書きの試験
│   └── .shared/                 境。Archon との出入りの口 1 つと埋め（E2）
├── lib/                         助け手（AGENTS.md が E3）。Archon を知らない Python（E3）
│   ├── graphloops/engine/       lib の部品が頼る graphloops の小道具（持ち主の決め lib-port-as-is）
│   └── tests/                   lib/ の試験
├── tests/                       lib/ 以外の試験（AGENTS.md が試験の決まり）
│   ├── layers/                  層の決まりの試験（この文書の「機械」の行）
│   ├── bin/                     入口の試験
│   ├── shared/                  境の試験
│   ├── workflows/               サブグラフの YAML の形と筋書きの試験（test_<サブグラフ>.py。筋書きは tests/archon.py の使い捨ての木で回す）
│   └── e2e/                     小さな対象のリポジトリの種（target-seed/。__init__.py を置かない）と、通しの試験
├── docs/
│   ├── design.md                設計（メイングラフ・サブグラフ・能力の棚卸し・未決）
│   ├── owner-decisions.md       持ち主の決めの正本
│   ├── asf-notes.md             ASF から採った型
│   ├── polyfills.md      埋めの名簿
│   ├── concepts.md              考えの住処の地図
│   ├── concepts.json            考えの住処の柵の表（tests/layers/test_concept_fences.py が照らす）
│   ├── calibration-214.md       #214 の自作の較正の束の比べの記録（束は消した）
│   └── plans/                   実装の計画
├── .github/workflows/tests.yml  CI。check の名は tests（4 つの分けを集める。分けは tests/shard.py）
├── pack.json                    版の止め（Archon の版は factory/pack.json）
├── pyproject.toml               Python の外のパッケージの宣言（1 か所。持ち主の決め outside-packages-ok・overnight-speed。lib/AGENTS.md の E3）
├── .gitignore
├── AGENTS.md                    AI 向けの決まり（この文書）。下のフォルダの AGENTS.md と自動で合わさる
├── MISSION.md・README.md
├── engineering.md               ASF の役が読む入口。ここを指すだけ
└── ASF の取り付け命令が置いた物（持ち主の決め asf-installer-in-repo。E8）
    ├── factory/・FACTORY.md・FACTORY_RULES.md     手を加えない
    ├── harness/                 END-TO-END.md・harness.config.json・runtime.inputs.json・runtime.scenario.json だけ書く。ほかは手を加えない
    └── .factory/holdout/HOLDOUT.md                書く
```

- 試験を置くフォルダには全部 `__init__.py` を置く（無いと Python 3.12 の unittest は黙って見つけない）。run の中の確かめは根からの `tests/changed.py` の 1 つ（変更に当たる試験と層の柵）で、全部の試験は CI だけが回す（命令と外のパッケージの入れ方は `tests/AGENTS.md`）。
- 機械: `tests/layers/test_layout.py`（根の直下のファイルとフォルダが上の木に在る物だけ。木の根の直下の名は 1 度だけ。`workflows/` の直下が `line/`・8 つのサブグラフ・`.shared/` だけ。各サブグラフが `works-factory-<サブグラフ>.yaml` を持つ。試験のフォルダに `__init__.py` が在る）。

## E8 ASF は横に並べて見るだけ

- ASF と Archon 同梱のグラフを `include:`・`workflow:` で呼ばない。ASF のコードを自分の層（`bin/`・`workflows/`・`lib/`）に写さない。採るのは型（なぜその形か）だけ。
- ASF の取り付け命令が置いた物（`factory/`・`harness/`・`FACTORY.md`・`FACTORY_RULES.md`・`.factory/`）は、ASF がこのリポジトリを作るための物で、4 つの層の外に置いたまま手を加えない。ASF の共有のグラフへの決まりは `factory/WORKFLOW_POLICY.md`。持ち主の決め `asf-installer-in-repo`。
- ASF の型を採ったら、`docs/asf-notes.md` に 1 行足す（ASF の commit・ファイル・採った先のサブグラフ・違いと訳）。
- 機械: `tests/layers/test_no_asf.py`（`include:`・`workflow:` の値が `works-factory-` で始まる）。写していないことと名簿の行は人が見る。

## E9 グラフの名は archon- で始めない

- グラフの名は `works-factory-<フォルダの名>`。メイングラフは `works-factory-line`。ASF（`archon-*`）と並べて見比べても名前で選び分けられる。
- 機械: `tests/layers/test_names.py`（E18 と同じ試験）。

## E10 4 つの層の外に仕組みを足す前に、持ち主の決めを書く

- 新しい層・置き場・常駐する仕組みは、先に `docs/owner-decisions.md` に持ち主の言葉つきで決めを書いてから足す。
- 人が見る（審査の目が `docs/owner-decisions.md` の行を探す）。

## E11 仕組みを足す前に 3 つを確かめる

1. Archon が持っているか（止めた Archon（`docs/design.md` の「語」）の文書と、`docs/design.md` の「Archon の分かっていること」）。
2. ASF が持っているか（`docs/asf-notes.md` と、取った Archon の源の `.archon/workflows/sdlc/`）。
3. 本当に要るか（今の works の能力の一覧 `docs/design.md` の「能力の棚卸し」のどれに当たるか）。

- 計画の文書に 3 つの答えを書く。人が見る。

## E13 対象の言語を知らない

- 役の指示書（`workflows/*/commands/`）と `lib/` に、特定の言語・テストの実行器の名を書かない。事実上の標準の形式（JUnit XML など）は名指してよい。持ち主の決め `lang-neutral`。
- `lib/` は Python で書くので、`lib/tests/`（lib 自身の試験）と `lib/AGENTS.md` は照らさず、語の表に `python` を入れない。
- 例外: 拡張子と言語の対応・テストのファイルの名の慣習の表と、その表を作る標準ライブラリの import は、`lib/impact.py`・`lib/changemap.py`・`lib/tddloop.py`・`lib/fixrules.py`・`lib/libdocs.py`・`lib/libdocs_local.py` に限って書いてよい。機械の表 `tests/layers/scan.py` の `ALLOWED["E13"]` には、そのファイルを入れる PR が 1 行ずつ足す。機械はファイルごとに外すので、表の外に言語の名が無いことは人が見る。
- 機械: `tests/layers/test_lang_neutral.py`（言語と実行器の名の語の表に当たる字が無い。表は `tests/layers/scan.py` の中）。

## E14 既定の道は普通の利用者の環境でそのまま動く

- 普通の利用者とは、Claude Code に `claude /login` しただけの人・macOS 以外の人・API キーや会社のゲートウェイを使う人など。持ち主の決め `others-may-use`。
- 持ち主の環境（Claude のアカウントの名・keychain の項目の名・GitHub のアカウントの名・置き場のパス）はリポジトリに書かない。選べる道として置き、値は利用者の設定（リポジトリの外）か起動の引数で渡す。
- 何かを削る・落とす直しは、持ち主の環境で要らないかだけでなく、普通の利用者の環境で要らないかを書く。人が見る。
- 機械: `tests/layers/test_no_owner_env.py`（`bin/`・`workflows/`・`lib/` に、持ち主の環境の字（`raiki61`・`claude-code-oauth-`・`/Users/`）が無い）。

## E18 取ってきた物と自分の物を名前で見分けられるようにする

- 取ってきた物は元の名前と場所のまま置き、名前を変えない。ASF の物は `factory`・`FACTORY`・`harness`・`.factory`・`archon-` で始まる。ASF のグラフは Archon の源の `.archon/workflows/sdlc/` に、自分のグラフはこのリポジトリの `workflows/` に在り、混ぜて置かない。持ち主の決め `name-by-origin`。
- 自分の物には、それらで始まる名前を付けない（ファイル・フォルダ・グラフ・型の名）。自分のグラフは `works-factory-` で始める（E9）。
- 今の works から持ってきた物（E15）は、元と同じファイル名で置く。元と見比べられるようにするため。どこから持ってきたかは commit に書く。
- 機械: `tests/layers/test_names.py`（`bin/`・`workflows/`・`lib/`・`tests/`・`docs/` の下のパスの部分に、`factory`・`FACTORY`・`harness`・`.factory`・`archon-` で始まる物が無い）。ASF の物が「リポジトリの形」の木の場所の外に無いことは人が見る。
