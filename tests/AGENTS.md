<!-- coldwrite:skip AI 向けの決まり。語は docs/design.md の「語」の節で定義 -->
# 試験（`tests/`）の決まり

`tests/` に試験を書く時に読む。リポジトリ全体の決まりは根の `AGENTS.md`。

- 試験はリポジトリの根から `uv run --isolated python3 -m unittest discover -s . -t .` の 1 つで走る。`uv run --isolated` が使い捨ての環境に `pyproject.toml` の宣言（PyYAML など）を入れてから走らせる。CI（`.github/workflows/tests.yml`）と ASF の `harness/harness.config.json` の `unit` も同じ命令。宣言を入れた Python なら `python3 -m unittest discover -s . -t .` でも同じ。
- 試験を置くフォルダには全部 `__init__.py` を置く。無いと Python 3.12 の unittest は黙って見つけない。1 件も走らない時は終了の値 5 で落ちる。試験の無い木を緑にしない。
- 置き場: 層の決まりの試験は `tests/layers/`（各決まりの「機械」の行）、入口は `tests/bin/`、境は `tests/shared/`、ブロックの YAML の形と筋書きの試験は `tests/workflows/`、通しの試験と小さな対象のリポジトリの種は `tests/e2e/`。`lib/` の試験は `lib/tests/`。
- `lib/tests/` の試験は、`lib/` を `sys.path` の後ろに足す（`append`。頭に入れると `lib/tests` が根の `tests` を隠す）。試験の助け（`gitkit`・`hermetic` など）の置き場は `tests/bin/` の 1 か所で、`from tests.bin.<名> import ...` で読む。
- Archon の源（`bin/_lib/place.archon_source` で取る物）か bun が要る試験は、`tests/archon.py` の助けで源を見つけ、Archon を起こし、使い捨ての木を組む。無ければ名前つきで見送る（`skipTest("Archon の源が無い: ...")`）。源の置き場は環境変数 `WORKS_FACTORY_ARCHON_CACHE`（`archon_source` に渡す `cache`）で渡す。試験の中では取りに行かない。CI は源と bun を取るので見送らない。
