"""点数の小さな統計。較正の緑の種（全部の試験が緑）。"""
import sys


def mean(xs):
    """xs の平均。空の xs は ValueError を上げる。"""
    if not xs:
        raise ValueError("mean of empty")
    return sum(xs) / len(xs)


def median(xs):
    """xs の中央値。偶数個は中の 2 つの平均。空なら ValueError。"""
    if not xs:
        raise ValueError("median of empty")
    ordered = sorted(xs)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def clamp(x, lo, hi):
    """x を lo 以上 hi 以下に収める。lo > hi は ValueError。"""
    if lo > hi:
        raise ValueError("lo > hi")
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def parse_scores(text):
    """カンマ区切りの整数を並びにする。数でない要素は ValueError。"""
    return [int(token) for token in text.split(",")]


def load_scores(path):
    """path のファイルを読み、parse_scores で並びにする。"""
    with open(path, encoding="utf-8") as f:
        return parse_scores(f.read())


if __name__ == "__main__":
    print(mean([float(arg) for arg in sys.argv[1:]]))
