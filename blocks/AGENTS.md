<!-- coldwrite:skip AI 向けの決まり。語は docs/design/README.md の頭の語の一覧で定義 -->
# block の置き場（`blocks/`）の決まり

#765 の作り直しの間の 2 つ目の pack。block と graph を書く時に読む。リポジトリ全体の決まりは根の `AGENTS.md`。設計の正本は `docs/design/README.md`。

- block を名指す依頼（例「world check」「世界の解」は `blocks/world/`、設計書は `docs/design/world.md`）は `blocks/` と `tests/blocks/` で閉じる。
- 作り直しの間は、`workflows/` の今のサブグラフ（指示書 `workflows/<サブグラフ>/commands/` を含む）・`lib/agents/` の今の役の定義・block が写した元の `lib/` のモジュール（`lib/worldblk.py`・`lib/worldcheck.py`・`lib/judge_accept.py` の `world_*` など。元は今の judge が使う）を触らない。組み込みで `workflows/` ごと入れ替わる。
- 「全部の役」「どの役も」と言う依頼は `blocks/` の役のこと。役が共に読む決まりは `.shared/prompts/` の断片 1 本で閉じる（断片の名は `.shared/AGENTS.md`）。

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
- 入力を足す（P）: 受け手の block の `inputs:`・`schemas/`・それを読む script と `src/`・`prompts/`・`tests/blocks/<block>/`。既定値つきの任意の入力なら、今の呼び手（policy-check などの graph）と根の README の例はそのまま回るので触らない。graph の `with:` は、その graph から値を渡すと依頼が言う時だけ足す。設計書の port の所は直す（port が変わる）。
- 観点を足す（N）: 新しい block のフォルダ `blocks/<block>/`・`tests/blocks/<block の名の - を _ にした物>/`・`docs/design/<block>.md`。graph の with: と include は、つなぐと依頼が言う時だけ。根の README は触らない（単独で回す例は world の 1 つで足りる。新しい block の単独の呼び方は `docs/design/<block>.md` の「単独で呼ぶ」の所に書く）。
- 2 つ以上の block が使う助け: Archon の pointer・`INPUTS_`・place を解く所は `.shared/` の口、解いた後のパスや値を受ける所は `lib/` の新しいモジュール（`.shared/AGENTS.md` の「`.shared` と `lib/` の分け」）。助けを置くだけの依頼では、使い手の block の `scripts/`・`src/` は触らない（使い始めは、その block を名指す別の変更で）。
- block の中で閉じる変更では、設計書 `docs/design/<block>.md` は port・node の並び・受け付けの決まりが変わる時だけ直し、筋書き（`fixtures/`）は通らなくなった時だけ直す。設計書は md の本文を写さない（本文の正本は block の `prompts/`）。

## 始め方

- 新しい block は `blocks/world/` を写して始める（手本は 1 つ）。graph の手本は `blocks/policy-check/`。
- 設計書は `docs/design/<block>.md` に 1 本。型は `docs/design/README.md` の 6 章、手本は `docs/design/world.md`。
- 置き場の形は `docs/design/README.md` の 3 章: `works-factory-<block>.yaml`・`prompts/<node-id>.md`（system prompt は `prompts/<node-id>.system.md`）・`prompts/parts/<name>.md`・`scripts/<name>.py`・`src/`（package の名は `src`）・`schemas/<port>.schema.json`・`fixtures/standalone.stubs.yaml`。
- 入力・place・指示は `.shared/` の口（`ports.py`・`prompt.py`・`requestrows.py`）を通して書く。口の一覧と、共通の断片・共通の port の形の名（今在る物と取り置いた物）は `.shared/AGENTS.md`。
- YAML に指示の文を書かない: `loop:` の node・`agents:`・`on_reject` と `decisions` の `rework` の `prompt` は使わない（`loop_group` と prep で書く）。
- 試験は `tests/blocks/<block の名の - を _ にした物>/`。助けは `tests/blocks/kit.py`。
- 単独で回す: `WORKS_FACTORY_FOLDER=blocks bin/works-factory workflow run works-factory-<block> --cwd <対象> --input <名>=<値>`。
- 機械: `tests/layers/test_block_shape.py`（`docs/design/README.md` の 7.1 の yes/no と、今ある yes/no の検査の当てはめ）。
