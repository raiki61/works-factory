<!-- coldwrite:skip AI 向けの決まり。語は docs/design/README.md の頭の語の一覧で定義 -->
# 見る道具（`viewer/`）の決まり

`viewer/` を書く時に読む。リポジトリ全体の決まりは根の `AGENTS.md`、設計は `docs/design/viewer.md`、置き場の決めは持ち主の決め `viewer-in-repo`・`run-page-v4`。

見る道具は、run（工場の 1 回の実行）の記録を OpenTelemetry のトレースにして、利用者が名指した受け口（手元に置いた Phoenix など）へ送る物と、run を 1 枚の HTML のページにする物で、工場が直しを作る流れには入らない（持ち主の決め `run-trace-otlp`・`run-page-v4`）。

- 入口は 2 本で、どちらも引数を読み `src/` の部品を順に呼ぶだけ: トレースを送る `runtrace.py` と、ページを標準出力に出す `runpage.py`。読む部品は、作りの読み `src/shape.py`・Archon の記録の読み `src/runread.py`・Claude Code の会話の記録の読み `src/session.py` と、段（line の一番上のノードを人の言葉で畳んだ単位）の表 `stages.json` とそれを読む段ごとの集計 `src/stages.py`。トレースの部品は、span の木の組み `src/trace.py`・送り先の決め `src/sendto.py`・OTLP での送り `src/otlp.py`。ページの部品は、組み `src/page.py`・block の入出力と実行条件の解き `src/ioflow.py`・指示の md のプレースホルダの値の切り出し `src/fill.py` と、雛形と埋める物のフォルダ `page/`（`page.tpl.html`・`tokens.css`・図の配置のライブラリの写し `dagre.js`）。
- Archon の名（記録の行の型・DB の表と欄・置き場の形）は `src/runread.py` の 1 か所に置く。run の家は殻の口（`bin/AGENTS.md` の「`viewer/` が読む殻の口」）で引き、字で写さない。
- 試験は `tests/viewer/`。

## E25 見る道具は工場の外に置き、書く物と送る物を限る

元の works の決まりの E25（`docs/design/README.md`・`docs/design/r1.md`〜`r4.md`・`tests/e2e/evidence.json` が引く物）とは別。

1. 見る道具は工場の外の物で、工場の中（`bin/`・`workflows/`・`lib/`）から import もパスでの名指しもしない。読み手は人だけ。機械: `tests/layers/test_viewer_apart.py`（`viewer/` のパスと `import viewer`・`from viewer` の字が、`viewer/`・`tests/viewer/`・文書の外に在れば赤）。
2. 見る道具はファイルを書かない。ページは標準出力に出す（置き場は利用者がリダイレクトで決める）。DB は読むだけで開く。外へ送るのは `runtrace.py` だけで、送り先は利用者が名指し、既定の送り先を持たない。手元でない送り先は `--remote` の時だけ送る。送りに使う値（送り先・headers・送りの形）は `src/sendto.py` の 1 か所が読み、OpenTelemetry の SDK に `OTEL_` の名を読ませない。機械: `tests/viewer/test_sendto.py`（送り先の決め・拒み・headers・proxy）・`tests/viewer/test_runtrace.py`（入口が決めを通ってから SDK を読む）・`tests/viewer/test_otlp.py`（CI の job `trace`。答えが exporter に渡り、`OTEL_` の名が SDK に届かない）・`tests/viewer/test_runpage.py`（DB を読むだけで開き、ページの入口が DB を変えない・run の metadata の `run_config` がページに出ない）。人が見る: ファイルを書かないことと、トレースの入口が DB を読むだけで開くこと（読みの口 `src/runread.py` の `connect` は同じ）。
3. ページは 1 枚で完結し、別のファイルや網からスクリプトを読まない（持ち主の見方。VS Code の Remote-SSH の HTML のビューア）。機械: `tests/viewer/test_runpage.py`（`page/` の全部に `<script src`・`import(`・`fetch(` が無い）。
4. 見た目の決まりは置かない。ページの見た目は試験で縛らない（持ち主の言葉「まあみながらまたブラッシュアップしましょうよ」）。
