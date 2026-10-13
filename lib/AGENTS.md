<!-- coldwrite:skip AI 向けの決まり。語は docs/design.md の「語」のセクションで定義 -->
# 助け手（`lib/`）の決まり

`lib/` を書く時に読む。リポジトリ全体の決まりは根の `AGENTS.md`。

## E3 lib/ は Archon を知らない

- `lib/` は script ノードが呼ぶ Python の助け手だけを持つ（引用の照らし・TDD の赤の判定・元から赤の見分け・範囲の照らしなど）。流れ（どの確かめを・どの順で・どこで人に聞くか）・役の指示書・サブグラフの間で渡す物の型は持たない。それはグラフ（`workflows/`）と `docs/design.md` だけが持つ。
- `lib/` は Archon の名（`archon`・`$ARTIFACTS_DIR`・`$TYPED_ARTIFACTS_FILE`・`ARCHON_` で始まる環境変数・`INPUTS_<名>`・`WORKFLOW_ID`・`$LOOP_PREV`・`loop_group`・`$<節>.output`・ノードの id・`output_type` の語）を書かない。入力は引数とファイルのパス、出力は返り値と JSON。
- 機械: `tests/layers/test_lib_blind.py`（上の語の字の形が `lib/` に 1 つも無い。`import` に `workflows` と `bin` の中の物が無い。この決まりの文の `lib/AGENTS.md` は照らさない。今の works から写した lib に残る字は `tests/layers/scan.py` の `ALLOWED["E3"]` に `<パス>#<字>` で 1 つずつ名指し、区分の issue で外す）。
- 外のパッケージは使ってよい（持ち主の決め `outside-packages-ok`）。版を止め、依存の宣言は 1 か所に置く。宣言は根の `pyproject.toml` の `[project] dependencies`。試験の命令（`uv run --isolated`。`tests/AGENTS.md`）がこれを入れてから走らせる。Archon の `runtime: uv` のノードは今 `deps:` を持たず、script のノードは標準ライブラリと `lib/` だけで書く（`workflows/AGENTS.md` の E7 の `dependencies = []`）。外のパッケージを要るノードを足す時は `deps:` に写さずにこの宣言を引く（段 1 の決め。`docs/design.md` の「層の E3 の `deps:`」）。
