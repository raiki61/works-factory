<!-- coldwrite:skip AI 向けの決まり。語は docs/design.md の「語」のセクションで定義 -->
# 試験（`tests/`）の決まり

`tests/` に試験を書く時に読む。リポジトリ全体の決まりは根の `AGENTS.md`。

- run の中の確かめの全体の命令は、リポジトリの根からの `uv run --isolated python3 tests/changed.py` の 1 つ（`harness/harness.config.json` の `unit` と同じ字）。実装・修正・見直しなど run の中の役は、作業中も最後の確かめもこれだけを回して先へ進む。変更に直に当たる試験（`lib/impact.py` の選び）と層の柵（`tests/layers/`）だけを回す。`uv run --isolated` が使い捨ての環境に `pyproject.toml` の宣言（PyYAML など）を入れてから走らせる。`tests/archon.py`・この文書・`pyproject.toml`・`.github/` が変わった時や、起点（`origin/main` との merge-base）が取れない時など、変更から試験を選べない時も全部は回さず、選べた範囲と層の柵だけを回し、全部の試験は CI に寄せると訳を出す（持ち主の決め `full-suite-in-ci`）。
- 全部の試験（`uv run --isolated python3 -m unittest discover -s . -t .`）は CI が回す物。run の中・役の作業中には回さない（最後の確かめのためにも回さない）。main へのマージは CI の緑を待つ。CI（`.github/workflows/tests.yml`）は全部の試験を `tests/shard.py` で 4 つに分けて並べて走らせ、集めの check の `tests` を 4 つが全部緑の時だけ緑にする。分けは秒数の表 `tests/shard-seconds.json` で釣り合わせ、表に無いモジュールも必ずどれかの分けに入る（表の直し方は `tests/shard.py`）。機械: `tests/layers/test_test_commands.py`（上の run の中の命令が `unit` と同じ字。全部の試験の命令を書く決まりの文書はここだけ）。どちらが run の中の命令と読めるかは人が見る。
- 考えの住処の柵の試験 `tests/layers/test_concept_fences.py` の `NotAboveMain` は、HEAD と `origin/main` の分かれ目の表と比べる。`origin/main` が無い clone・浅い clone では見送らずに赤になるので、手元で走らせる前に `git fetch origin main` で取る（CI は `fetch-depth: 0` で全履歴を取る）。
- 試験を置くフォルダには全部 `__init__.py` を置く。無いと Python 3.12 の unittest は黙って見つけない。1 件も走らない時は終了の値 5 で落ちる。試験の無い木を緑にしない。
- 置き場: 層の決まりの試験は `tests/layers/`（各決まりの「機械」の行）、入口は `tests/bin/`、境は `tests/shared/`、サブグラフの YAML の形と筋書きの試験は `tests/workflows/`、通しの試験と小さな対象のリポジトリの種は `tests/e2e/`。`lib/` の試験は `lib/tests/`。
- `lib/tests/` の試験は、`lib/` を `sys.path` の後ろに足す（`append`。頭に入れると `lib/tests` が根の `tests` を隠す）。試験の助け（`gitkit`・`hermetic` など）の置き場は `tests/bin/` の 1 か所で、`from tests.bin.<名> import ...` で読む。Archon の要る試験の助け（止めた Archon の源と bun を見つけ、使い捨ての木を組む）だけは `tests/archon.py`。
- Archon の源（`bin/_lib/place.archon_source` で取る物）か bun が要る試験は、`tests/archon.py` の助けで源を見つけ、Archon を起こし、使い捨ての木を組む。無ければ名前つきで見送る（`skipTest("Archon の源が無い: ...")`）。源の置き場は環境変数 `WORKS_FACTORY_ARCHON_CACHE`（`archon_source` に渡す `cache`）で渡す。試験の中では取りに行かない。CI は源と bun を取り、環境変数 `WORKS_FACTORY_ARCHON_REQUIRED` を立てるので、見送る所が赤になる（CI の用意が崩れても黙って見送らない）。
