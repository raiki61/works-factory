# stats

点数の小さな統計。

- `mean(xs)`: 平均。空の `xs` は `ValueError`。
- `median(xs)`: 中央値。偶数個は中の 2 つの平均。空の `xs` は `ValueError`。
- `clamp(x, lo, hi)`: `x` を `lo` 以上 `hi` 以下に収める。`lo > hi` は `ValueError`。
- `parse_scores(text)`: カンマ区切りの整数を並びにする。数でない要素は `ValueError`。
- `load_scores(path)`: ファイルを読み、`parse_scores` で並びにする。

## 使い方

引数の平均を 1 行出す。

```sh
python3 stats.py 1 2 3
```

出力は `2.0`。
