<!-- coldwrite:skip AI 向けの決まり。語は docs/design/README.md の頭の語の一覧で定義 -->
# 助け手（`lib/`）の決まり

`lib/` を書く時に読む。リポジトリ全体の決まりは根の `AGENTS.md`。

- 2 つ以上の使い手（block か graph か `bin/`）が使う物だけを置く。1 つの block だけが使う物は `workflows/<block>/src/`（憲法の 4。持ち主の決め `block-local-code`）。どのモジュールを残したかと使い手は `docs/design/README.md` の 9.3。
- 2 つ以上の block が読む出力の行の形（欄の名・語・行を読む述語）は、作り手の出力ごとに 1 モジュールに置く（手本は `worldmark`。`docs/design/README.md` の 4.1）。
- Archon の pointer・`INPUTS_`・place を解く所は `workflows/.shared/` の口（`ports.py` など）に置き、ここは解いた後のパスや値を受ける。
- AI に届く決まった文を Python の定数に持たない（憲法の 2）。役に届く文は block の md か `workflows/.shared/prompts/` の断片に置く。
  機械: `tests/layers/test_no_prompt_text_in_python.py`。照らす範囲は `lib/*.py` と block の `src/`・`scripts/` の 1 段目。`lib/` に効くのは「直下の定数に英語の文を持たない」だけで、「指示を組む関数が文の定数を読まない」は block の `src/`・`scripts/` に効く（`lib/` は指示を組まない）。
- 短い部品の例: `jsonfile`（JSON の読み書き）・`oneline`（1 行に畳む）・`rolekit`（受け付けの回の数え・却下の控え・諦め）・`worldmark`（世界の解の行の欄と語）・`carry`（依頼の容器の読み）・`webget`（網の口）・`materialkit`（素材の観点の族の共通の部品）・`eyekit`（独立の目の族 r1〜r4 の共通の部品）・`runlog`（run の記録の読み）・`judgmark`（判定の出力の行の形）。

## E3 lib/ は Archon を知らない

- `lib/` は Python の助け手だけを持つ。流れ（どの確かめを・どの順で・どこで人に聞くか）・指示の文・block の間で渡す物の型は持たない。それは graph と block（`workflows/`）と `docs/design/` が持つ。
- `lib/` は Archon の名（`archon`・`$ARTIFACTS_DIR`・`$TYPED_ARTIFACTS_FILE`・`ARCHON_` で始まる環境変数・`INPUTS_<名>`・`WORKFLOW_ID`・`$LOOP_PREV`・`loop_group`・`$<ノード>.output`・ノードの id・`output_type` の語）を書かない。入力は引数とファイルのパス、出力は返り値と JSON。`workflows/`・`bin/` の物を import しない（層の地図 `docs/layers.json`。根の `AGENTS.md` の E22）。
- 外のパッケージは使ってよい（持ち主の決め `outside-packages-ok`）。版を止め、依存の宣言は根の `pyproject.toml` の `[project] dependencies` の 1 か所に置く。Archon の `runtime: uv` の script のノードは `deps:` を持たず、標準ライブラリと `lib/` だけで書く（`workflows/AGENTS.md` の E7 の `dependencies = []`）。
- 外し: 仕様駆動の道の表（YAML）を読む script の 2 本、block の入口の `workflows/spec-driven/scripts/intake.py` と、起動の殻が表を読む `bin/_lib/spec-inputs.py` は、PyYAML を PEP 723 の頭で宣言する（`dependencies = ["PyYAML==<根の pyproject.toml と同じ版>"]`）。どちらも表の読みは `lib/spectable.py` を import する（docs/design/spec-driven.md の 6.7。機械: `tests/workflows/test_uv_scripts.py` の `YAML_READERS` と版の縛り）。
- 外し: `lib/runlog.py`（Archon の run の記録 `$LOG_DIR/<WORKFLOW_ID>.jsonl` を読む口）とその試験 `lib/tests/test_runlog.py`。report と chain の 2 つの block が使うので lib に上げた（`docs/design/integration.md` の 4.5-2 の決め）。機械の許しの表 `tests/layers/scan.py` の `ALLOWED["E3"]` に同じ 2 行が在る。
- 機械: `tests/layers/test_lib_blind.py`。
