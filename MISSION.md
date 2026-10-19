# Mission

## 目的

人の修正依頼を受け、対象のリポジトリで直しを作り、確かめてから人に返す工場を、持ち主の自分版として持つ。持ち主以外の人も、自分の環境でそのまま使える形にする（持ち主の決め `others-may-use`）。

- 流れ: 判定 → 計画 → 事前審査 → 修正 → 試験の関門 → 独立の目 → 報告。途中に承認ノード（人に答えを聞いて止まる所）を置く。
  - 修正は TDD（先に落ちるテストを書き、直して通す）で進め、互いに触らない直しは別々の作業ツリー（枝）で並べて進める。
  - 独立の目は、直しを作った AI と別の AI が 4 つの観点（R1〜R4。中身は `docs/design/judge-eyes.md` の 2 章と `docs/design/r1.md`〜`r4.md`）で直しを確かめる段。
- 土台: Archon（AI の処理をグラフにして YAML で書き、機械が順に回す道具）の、ASF と同じ開発中の源（止めた Archon（`docs/design/archon.md` の「語」））。書き方は、Archon の作者が作った SDLC のグラフの束 ASF（AI software factory）に寄せる。
- 持ち主のエッセンスはグラフそのもの（どの確かめと役が在り、何をし、どの順でつながり、どこで人に聞くか）。Archon の書き方で `workflows/` に書く。script ノードが呼ぶ Python の助け手は、Archon を知らない `lib/` に置く。
- 今の works（raiki61/claude-plugins の `works/`）と同じ能力に届いたら置き換える。

## 範囲の外

- Archon・ASF の中身を直すこと。Archon に足りない所は、このリポジトリの `workflows/.shared/` に置く埋め（polyfill。Archon に無い物を外から補う小さな部品）で塞ぎ、`docs/polyfills.md` に書く。Archon の開発元には連絡しない。
- ASF のコードを写すこと。型（作りの考え）だけを採り、`docs/asf-notes.md` に書く。
- ASF や Archon 同梱のグラフを `include`（別のグラフを取り込む Archon の書き方）すること。横に並べて見比べるだけ。
- グラフの YAML を別の形から変換して作ること。YAML は手で書き、そのまま Archon に渡す。
- 4 つの層の外の新しい層や仕組み。層は、人が打つ入口（`bin/`）・グラフ（`workflows/`）・Archon との境（`workflows/.shared/`）・助け手（`lib/`）。足すなら先に持ち主の決めを `docs/owner-decisions.md` に書く。
- 特定の言語・テストの実行器に寄った確かめ。対象に依らない言い方で書く。
