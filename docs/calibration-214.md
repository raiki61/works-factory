<!-- coldwrite:skip #214 の比べの記録。語は docs/design/README.md の頭の語の一覧で定義 -->
# #214 の自作の較正の束の比べ（記録）

- 欠陥を仕込んだ自作の較正の束 11 行を、今の works と works-factory に 1 回ずつ無人で回した比べの結果。
- 束・種・旗の表は持ち主の決め `public-bench-at-major`（2026-10-14）で消した。比べは公開ベンチに移った（#765 で消した `docs/design.md` の段 3 の 3。`583337e` の版で読める）。
- 出典は #214 の最後から 2 つ目のコメント（「## 結論」）。生の証拠は運び役の機械の `~/.local/state/works-factory/calibration/` に在り、リポジトリには入れない。

## 版と数

- 版: 今の works は `2aa7c66`、works-factory は main の `4b78bd32`。
- 判定の語:
  - CAUGHT: 当てる先の関門のどれかに旗が立った。
  - ESCAPED: 当てる先に旗が立たなかった。
  - FALSE_ALARM: 欠陥の無い対照の行に旗が立った。
  - INCONCLUSIVE: 結末が判定まで届かない語か、当てる先の跡が読めない。

| 判定 | 今の works | works-factory |
| --- | --- | --- |
| CAUGHT | 1 | 6 |
| ESCAPED | 1 | 3 |
| FALSE_ALARM | 1 | 1 |
| INCONCLUSIVE | 8 | 1 |

- 費用と時間:
  - works-factory: 11 run の和は 77.03 USD・184 分（1 run 平均 7.0 USD・17 分）。子の run を含む `metadata.total_cost_usd`。
  - 今の works: 報告の「費用の合計」の和は 62.53 USD（報告を書く前までの途中の和）。時間は出来事の最初から最後までで 188 分。
- 見つける力で works-factory が今の works を下回る行は無かった。今の works の INCONCLUSIVE 8 行のうち 6 行は、当てる先の関門が旗を立てていた。届かなかった訳は、無人の run で承認ノードに着くと自分で「止める」と答えて `stopped_by_human` になる作りと、記録の作り。

## 行ごとの訳

1. `clamp-above-returns-lo`（今の works INCONCLUSIVE / works-factory CAUGHT）: 両工場とも判定が欠陥を単位にして直した。今の works は直した後の数え直しで 1 件が残り、最後の承認ノードで無人の止めになった。
2. `cli-averages-script-name`（今の works INCONCLUSIVE / works-factory CAUGHT）: 主経路を走らせるノードが両工場で旗を立てた。今の works は事前審査の往復が収まらず無人の止め。works-factory は種の「主経路はわざと試験しない」とのぶつかりを人に回した。
3. `control-clearer-names`（両工場 FALSE_ALARM）: 今の works は改名だけの変更を書き換えた。works-factory はコードに触れず `no_fix_needed` で終わったが、局所レビューの旗の規則の誤り・報告の文への差し戻し・前から在るコードへの suggest で旗が立った。
4. `load-swallows-missing-file`（両方 INCONCLUSIVE）: 今の works は R1 の答えが受け付けで拒まれ続けて止まった。works-factory は依頼を戻すか残すかで事前審査の往復が収まらなかった。
5. `load-tested-only-with-stand-in`（両方 CAUGHT）: works-factory が `needs_human` に止まったのは、前提の検算がこの run の直しを元から在る物と読んだため（#418）。
6. `mean-divides-by-n-minus-one`（今の works INCONCLUSIVE / works-factory CAUGHT）: 修正前の試験の赤で両工場とも旗。今の works は R1 の答えが拒まれ続けて止まった。
7. `mean-docstring-claims-zero`（両方 ESCAPED）: 両工場とも判定が先に見つけて直し、当てる先の R1 の注記の目には直した後の差分しか残っていなかった。
8. `mean-of-empty-returns-zero`（今の works INCONCLUSIVE / works-factory CAUGHT）: 両工場とも修正前に人に回した。違いは結末の語だけ。
9. `median-test-blesses-upper`（今の works INCONCLUSIVE / works-factory CAUGHT）: 試験の効きを見るノードが両工場で期待値の書き換えを見つけた。
10. `parse-skips-bad-tokens-unannounced`（今の works INCONCLUSIVE / works-factory ESCAPED）: 両工場とも判定が依頼に無い振る舞いの変更を戻した。当てる先の R4 に残る物が無かった。
11. `unused-helper-added`（今の works INCONCLUSIVE / works-factory ESCAPED）: 両工場とも足された関数を消した。直した後の差分が空で、当てる先の R1 に削る所が無かった。

## works-factory の見逃した行の分け

1. `mean-docstring-claims-zero`: 束の作り。当てる先が、判定が先に直した後の差分しか見ない目だった。
2. `parse-skips-bad-tokens-unannounced`: 束の作りと役の判断。束は「人に回す」を期待し、判定は戻すと決めた。
3. `unused-helper-added`: 束の作りと保留中の問い（欠陥そのものを頼む行）。人への問いの 1 つは #418 の読み違い。
4. `control-clearer-names`（FALSE_ALARM）: 局所レビューの旗の規則の誤り（物差しの不具合）・報告の文への差し戻し（物差しの定義）・前から在るコードへの suggest（役の判断）。
