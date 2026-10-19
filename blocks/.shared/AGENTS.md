<!-- coldwrite:skip AI 向けの決まり。語は docs/design/README.md の頭の語の一覧で定義 -->
# pack の共通の部品（`blocks/.shared/`）の決まり

block の script と `src/` が Archon と出入りする口と、2 つ以上の block が使う指示の断片と port の形を置く。設計は `docs/design/README.md` の 4 章と 5 章。

## 口を通さずに書けない物

- 入力の読み: script は `os.environ.get("INPUTS_<名>")` を字のまま読み、`ports` の form の口（`text`・`flag`・`choice`・`json`・`file`）に渡す。名を組んで読まない。
- place: `ports.place()` だけ。run directory の根（Archon の環境変数）を script と `src/` に書かない。ほかの block に渡すファイルは `ports.pointer(path)` で出力に入れる。
- 指示: prep は `prompt.emit(node_id, values, when, n)`（組むだけなら `prompt.render`）だけで組む。md のパスも文も渡さない。
- node の出力: `ports.returns(obj)`。落ちない node は `ports.run(compute, fallback)`。

## 口の一覧

- `ports.py`: `text(raw)`・`flag(raw)`・`choice(raw, words)`・`json(raw, schema)`（schema は block の `schemas/` の名か `shared:<名>`）・`file(raw)`・`parsed(raw)`・`picked(raw, names)`・`place()`・`pointer(path)`・`returns(obj)`・`run(compute, fallback)`・`lib_root()`。import すると `lib/` が読めるようになる。
- `ports.py` の、対象のコマンドを起こす block の口（`workflows/.shared/boundary.py` と同じ約束）: `RUNTIME_COPY`・`RUNTIME_COPY_PREFIX`・`RUNNER_PREFIXES`・`RUNNER_NAMES`・`drop_runner_env(user_env)`・`suite_keep()`。
- 埋め: `ports.polyfill(name)`（`fence`・`childsweep`・`child_pointer`・`skip_value`）。組み込みで埋めをここへ移すまで、リポジトリの `workflows/.shared/` から読む。役の書き込みの柵（`fence`）は起動の殻が役の claude を包むので、block が import する物ではない（読むだけの役は YAML の `sandbox.filesystem.denyWrite` に印を書く。根の `workflows/AGENTS.md` の E7）。
- `prompt.py`: `render(node_id, values, when)`・`emit(node_id, values, when, n)`・`lang(raw)`・`PromptError`。

## 置く物

- `prompts/<name>.md`: 2 つ以上の block が使う指示の断片。md から `{shared:<name>}` で入れる。今在る名: `rejected`（前の回の却下。中の口 `{rejection}`）・`query-rule`（外への検索の決まり。段落 `spawns` の真偽が要る）・`lang-default`（`lang` が空の時の言語の文）・`role-judge`・`role-blind-judge`・`role-cold-reader`・`role-inspector`・`role-investigator`（役の定義 5 本）。足りない断片は、最初に要った PR が足す。名は設計書の段で決める。
- 取り置いた断片の名（まだ置かない。最初に要った PR が、この名で足す）: `resubmit`・`policy`・`design-premises`・`unknown-asks`・`works-gh`・`material-status`・`material-na`・`material-where`・`material-readonly`・`handoff`・`report-head-check`。
- `schemas/<name>.schema.json`: 2 つ以上の block が使う port の形。今在る物: `request.schema.json`（依頼の行）。
- 埋め（Archon に無い物を外から補う部品）は組み込みで `workflows/.shared/` から移す。今は置かない。
- 機械: `tests/layers/test_block_shape.py`・口の試験は `tests/blocks/shared/`。
