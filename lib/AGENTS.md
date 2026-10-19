<!-- coldwrite:skip AI 向けの決まり。語は docs/design.md の「語」のセクションで定義 -->
# 助け手（`lib/`）の決まり

`lib/` を書く時に読む。リポジトリ全体の決まりは根の `AGENTS.md`。

- `#765` の作り直しの間の pack `blocks/` から使う物は、2 つ以上の block（か graph か `bin/`）が使う物だけを置く。1 つの block だけが使う物は `blocks/<block>/src/`（持ち主の決め `block-local-code`）。Archon の pointer・`INPUTS_`・place を解く所は `blocks/.shared/` の口（`ports.py` など）に置き、ここは解いた後のパスや値を受ける。作り直しの間は、今のモジュール（block が写した元の物も含む）を変えない。2 つ以上の block が使う新しいモジュールは足してよい（試験は `lib/tests/`）。
- 2 つ以上の block が使う短い部品: `jsonfile`（JSON の読み書き）・`oneline`（1 行に畳む）・`rolekit`（受け付けの回の数え・却下の控え・諦め）・`worldmark`（世界の解の行の欄と語）・`carry`（依頼の容器の読み）・`webget`（網の口）・`materialkit`（素材の観点の族の共通の部品。docs/design/materials.md）。

## E3 lib/ は Archon を知らない

- `lib/` は script ノードが呼ぶ Python の助け手だけを持つ（引用の照らし・TDD の赤の判定・元から赤の見分け・範囲の照らしなど）。流れ（どの確かめを・どの順で・どこで人に聞くか）・役の指示書・サブグラフの間で渡す物の型は持たない。それはグラフ（`workflows/`）と `docs/design.md` だけが持つ。
- `lib/` は Archon の名（`archon`・`$ARTIFACTS_DIR`・`$TYPED_ARTIFACTS_FILE`・`ARCHON_` で始まる環境変数・`INPUTS_<名>`・`WORKFLOW_ID`・`$LOOP_PREV`・`loop_group`・`$<節>.output`・ノードの id・`output_type` の語）を書かない。入力は引数とファイルのパス、出力は返り値と JSON。
- 機械: `tests/layers/test_lib_blind.py`（上の語の字の形が `lib/` に 1 つも無い。`import` に、層の地図（`docs/layers.json`。根の `AGENTS.md` の E22）で lib が頼ってよい層の外（`workflows`・`bin`）の物が無い。この決まりの文の `lib/AGENTS.md` は照らさない。照らしから外すのは `tests/layers/scan.py` の `ALLOWED["E3"]` に `<パス>#<字>` で名指した、役に届く文に `$LOOP_PREV` が無いことを確かめる 3 つの試験の字と、役が読む借りたスキルの読み替え `lib/borrow/unattended.md` が役に説く Archon の字だけ）。
- 外のパッケージは使ってよい（持ち主の決め `outside-packages-ok`）。版を止め、依存の宣言は 1 か所に置く。宣言は根の `pyproject.toml` の `[project] dependencies`。試験の命令（`uv run --isolated`。`tests/AGENTS.md`）がこれを入れてから走らせる。Archon の `runtime: uv` のノードは今 `deps:` を持たず、script のノードは標準ライブラリと `lib/` だけで書く（`workflows/AGENTS.md` の E7 の `dependencies = []`）。外のパッケージを要るノードを足す時は `deps:` に写さずにこの宣言を引く（段 1 の決め。`docs/design.md` の「層の E3 の `deps:`」）。
