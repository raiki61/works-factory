<!-- coldwrite:skip AI 向けの決まり。語は docs/design/README.md の頭の語の一覧で定義 -->
# 試験（`tests/`）の決まり

`tests/` に試験を書く時に読む。リポジトリ全体の決まりは根の `AGENTS.md`。

- run の中の確かめの全体の命令は、リポジトリの根からの `uv run --isolated python3 tests/changed.py` の 1 つ。実装・修正・見直しなど run の中の役は、作業中も最後の確かめもこれだけを回して先へ進む。変更に直に当たる試験（`lib/impact.py` の選び）と層の柵（`tests/layers/`）だけを回す。`uv run --isolated` が使い捨ての環境に `pyproject.toml` の宣言（PyYAML など）を入れてから走らせる。`tests/archon.py`・この文書・`pyproject.toml`・`.github/` が変わった時や、起点（`origin/main` との merge-base）が取れない時など、変更から試験を選べない時も全部は回さず、選べた範囲と層の柵だけを回し、全部の試験は CI に寄せると訳を出す（持ち主の決め `full-suite-in-ci`）。選んだモジュールは子に並べて回す（並べる数の既定と、上書きする環境変数 `WORKS_FACTORY_TEST_WORKERS` は `tests/shard.py`）。並べても結果が順で変わらないように、試験はほかのモジュールと置き場を分け合わない（一時の置き場は `tempfile` で取る）。
- 全部の試験（`uv run --isolated python3 -m unittest discover -s . -t .`）は CI が回す物。run の中・役の作業中には回さない（最後の確かめのためにも回さない）。main へのマージは CI の緑を待つ。CI（`.github/workflows/tests.yml`）は全部の試験を `tests/shard.py` で 4 つに分けて並べて走らせ、集めの check の `tests` を 4 つが全部緑の時だけ緑にする。分けは秒数の表 `tests/shard-seconds.json` で釣り合わせ、表に無いモジュールも必ずどれかの分けに入る（表の直し方は `tests/shard.py`）。機械: `tests/layers/test_test_commands.py`。どちらが run の中の命令と読めるかは人が見る。
- 試験を置くフォルダには全部 `__init__.py` を置く。無いと Python 3.12 の unittest は黙って見つけない。1 件も走らない時は終了の値 5 で落ちる。試験の無い木を緑にしない。
- 置き場: 形と層の決まりの yes/no の試験は `tests/layers/`（各決まりの「機械」の行。試験の細目はその試験の docstring）、block と graph の試験は `tests/blocks/<block の名の - を _ にした物>/`（助けは `tests/blocks/kit.py`。script を子のプロセスで、port の値だけを渡して回す。block の出力の見本は block の `returns:` の `output_format` から作る）、pack の YAML と script の形の試験は `tests/workflows/`、入口は `tests/bin/`、埋めと Archon との約束は `tests/shared/`、通しの試験と小さな対象のリポジトリの種は `tests/e2e/`、公開ベンチの比べは `tests/calibration/`。`lib/` の試験は `lib/tests/`。試験は block の `src/` をパスで読んでよい（読んではいけないのは `lib/` とほかの block の側）。
- `lib/tests/` の試験は、`lib/` を `sys.path` の後ろに足す（`append`。頭に入れると `lib/tests` が根の `tests` を隠す）。試験の助け（`gitkit`・`hermetic` など）の置き場は `tests/bin/` の 1 か所で、`from tests.bin.<名> import ...` で読む。Archon の要る試験の助け（止めた Archon の源と bun を見つけ、使い捨ての木を組む）だけは `tests/archon.py`。
- Archon の源（`bin/_lib/place.archon_source` で取る物）か bun が要る試験は、`tests/archon.py` の助けで源を見つけ、Archon を起こし、使い捨ての木を組む。無ければ名前つきで見送る（`skipTest("Archon の源が無い: ...")`）。源の置き場は環境変数 `WORKS_FACTORY_ARCHON_CACHE`（`archon_source` に渡す `cache`）で渡す。試験の中では取りに行かない。CI は源と bun を取り、環境変数 `WORKS_FACTORY_ARCHON_REQUIRED` を立てるので、見送る所が赤になる（CI の用意が崩れても黙って見送らない）。

## E21 試験の子の環境は hermetic.child_env で作る

- `tests/` と `lib/tests/` の試験が起こす子（`subprocess` の `env=`）の環境は、`tests/bin/hermetic.child_env(**overrides)` で作る。子を起こす時はいつも `env=` を渡し、`os.environ` を写して渡さない（写す形の一覧は `tests/layers/scan.py` の `COPIED_ENVIRON`、子を起こす呼び出しの一覧は同じく `SPAWNS`）。`env=` の無い子は親の環境を丸ごと受け継ぐ。親（開発者のシェルや run の中の Claude Code・Archon）が立てた名と、Archon が script のノードに立てる変数（pack の口 `workflows/.shared/ports.py` の `RUNNER_PREFIXES`・`RUNNER_NAMES`）が子へ漏れ、同じ試験が場で違う結果を返す。
- 外す名は `child_env` の 1 か所が決める（`tests/bin/hermetic.py` の `DROPPED_PREFIXES`・`DROPPED` と、pack の口から `hermetic.runner_vars()` が字で引く Archon の変数の名）。試験が意図して子へ渡す名は `child_env` の overrides で名指しする。口が自分の意図で外す名は `child_env` が作った環境から外す。
- 試験の過程そのものが読む既定の環境（`lib/` の関数が `os.environ` から引く既定）も場に依らない: 試験を回す口 `tests/shard.py` は、試験を集める前に `hermetic.scrub` で同じ名を自分の過程から外す（残すのは試験の用意の名 `hermetic.ARCHON_CACHE_ENV`・`ARCHON_REQUIRED_ENV`）。利用者の環境を継ぐのが用途の試験（本物の役で回す試験の旗 `WORKS_FACTORY_REAL_RUN` と認証）は、外す前の値を `hermetic.inherited(*prefixes)` で名指しして引き、Archon へは overrides で渡す。
- 外し: 子の環境を作る道具でなく利用者の環境を継ぐのが用途の物（本物の run・較正の命令の道具・試験を回す口 `tests/changed.py`）や、子の環境を組む口でない物（偽の script の字）は `tests/layers/scan.py` の `ALLOWED["E21"]` に訳つきで置く。
- 機械: `tests/layers/test_hermetic_env.py`・`tests/test_shard.py` の `ScrubTest`。

## E24 試験は利用者の本物の設定を読まない

- 試験は、走らせた機械の利用者の本物の設定（`~/.claude`・会社が配る管理者の設定・keychain）を読まない。読む道を持つコードの試験は、置き場を一時のフォルダへ向けて、その中の設定だけを読ませる。
- 向け先を替える口は、コード側に持つ（例: 殻が読む管理者の設定の置き場は環境変数 `WORKS_FACTORY_MANAGED_DIR`。`tests/bin/hermetic.child_env` が空の一時フォルダへ向ける）。口は無い時の既定の道を変えない（根の `AGENTS.md` の E14）。口が無い道は、本物の設定が在る時にその試験だけを skip し、訳を docstring に書く。
- 人が見る（子の環境の組み方は E21 が機械で縛る）。
