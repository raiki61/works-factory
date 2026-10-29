<!-- coldwrite:skip AI 向けの決まり。語は docs/design/README.md の頭の語の一覧で定義 -->
# 見る道具（`viewer/`）の決まり

`viewer/` を書く時に読む。リポジトリ全体の決まりは根の `AGENTS.md`、設計は `docs/design/viewer.md`、置き場の決めは持ち主の決め `viewer-in-repo`。

見る道具は、工場の作り（graph と block の図・指示の md）と、run（工場の 1 回の実行）の一覧と再生を、人が 1 枚で見るための物。工場が直しを作る流れには入らない。

- 入口は `flowview.py`（引数を読み、`src/` の部品を順に呼ぶだけ）。読む部品は `src/`（作りの読み `shape.py`・Archon の記録の読み `runread.py`・Claude Code の会話の記録の読み `session.py`）と、札の「何をする物か」の 1 行の選び `what.py`。1 枚の HTML の組み立ては `src/page.py`、雛形は `page.tpl.html`、図の配置の道具 elkjs の版と照らしの値は `elkjs.json`。流れの画面の段（line の一番上のノードを人の言葉で畳んだ単位）の表は `stages.json`、段ごとの集計は `src/stages.py`。日本語の写し（指示の md を段落ごとに訳した、人が読むための射影）は `src/ja.py` が訳の控えから組み、工場の指示の md の段落の訳の控えは `ja/paragraphs.json`（持ち主の決め `viewer-in-repo` の 4）。
- Archon の名（記録の行の型・DB の表と欄・置き場の形）は `src/runread.py` の 1 か所に置く。run の家は殻の口（`bin/AGENTS.md` の「`viewer/` が読む口」）で引き、字で写さない。
- 試験は `tests/viewer/`。

## E25 見る道具は工場の外に置き、読むだけにする

元の works の決まりの E25（`docs/design/README.md`・`docs/design/r1.md`〜`r4.md`・`tests/e2e/evidence.json` が引く物）とは別。

1. 見る道具は工場の外の物で、工場の中（`bin/`・`workflows/`・`lib/`）から import もパスでの名指しもしない。読み手は人だけ。機械: `tests/layers/test_viewer_apart.py`（`viewer/` のパスと `import viewer`・`from viewer` の字が、`viewer/`・`tests/viewer/`・文書の外に在れば赤）。
2. 見る道具は読むだけ。書くのは出力（ページと訳の束。工場の clone の外。clone の下なら見る道具が拒む）と、利用者のキャッシュ（elkjs の tarball・リポジトリに入れない訳の控え）と、訳の取り込みと掃除の命令（`--ja-import`・`--ja-prune`）が書く `ja/paragraphs.json` だけ。DB は読むだけで開く。人が見る。
3. 出力のページは 1 枚で完結し、別のファイルからスクリプトを読まない（持ち主の見方。VS Code の Remote-SSH の HTML のビューア）。機械: `tests/viewer/test_page.py`（雛形に `<script src`・`import(`・`fetch(` が無い。`docs/design/viewer.md` の照らしの 4）。
4. 見た目の決まりは置かない。雛形の見た目は試験で縛らない（持ち主の言葉「まあみながらまたブラッシュアップしましょうよ」）。
