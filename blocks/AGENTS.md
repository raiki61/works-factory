<!-- coldwrite:skip AI 向けの決まり。語は docs/design/README.md の頭の語の一覧で定義 -->
# block の置き場（`blocks/`）の決まり

#765 の作り直しの間の 2 つ目の pack。block と graph を書く時に読む。リポジトリ全体の決まりは根の `AGENTS.md`。設計の正本は `docs/design/README.md`。

## 憲法

1. YAML はつなぐだけ。値はコードが計算し、判断は AI がする（Archon の憲法の "YAML coordinates. Code computes. Agents judge."）。
2. AI のノードの指示は、そのノードの md 1 本に英語で書く。Python は指示の文を持たず、md の `{name}` に値を渡す。
3. block は宣言した port だけで受け渡しし、ほかの block を名指さない。つなぐのは graph だけ。
4. 1 つの block だけが使うコードは、その block のフォルダに置く。`lib/` には 2 つ以上の block が使う物だけを置く。
5. どの block も、文とリポジトリだけで単独で回る。block ごとの standalone の fixture で確かめる。
6. 機械の検査は yes/no の形の決まりだけにする。数の上限や許す物の表では縛らず、間違った書き方を API と置き場の形で書けなくする。

## 始め方

- 新しい block は `blocks/world/` を写して始める（手本は 1 つ）。graph の手本は `blocks/policy-check/`。
- 設計書は `docs/design/<block>.md` に 1 本。型は `docs/design/README.md` の 6 章、手本は `docs/design/world.md`。
- 置き場の形は `docs/design/README.md` の 3 章: `works-factory-<block>.yaml`・`prompts/<node-id>.md`（system prompt は `prompts/<node-id>.system.md`）・`prompts/parts/<name>.md`・`scripts/<name>.py`・`src/`（package の名は `src`）・`schemas/<port>.schema.json`・`fixtures/standalone.stubs.yaml`。
- 入力・place・指示は `.shared/` の口（`ports.py`・`prompt.py`）を通して書く。口の一覧と、共通の断片・共通の port の形の名（今在る物と取り置いた物）は `.shared/AGENTS.md`。
- 試験は `tests/blocks/<block の名の - を _ にした物>/`。助けは `tests/blocks/kit.py`。
- 単独で回す: `WORKS_FACTORY_FOLDER=blocks bin/works-factory workflow run works-factory-<block> --cwd <対象> --input <名>=<値>`。
- 機械: `tests/layers/test_block_shape.py`（`docs/design/README.md` の 7.1 の yes/no と、今ある yes/no の検査の当てはめ）。
