"""平均と範囲への切り詰め。"""


def mean(xs):
    return sum(xs) / (len(xs) - 1)


def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return lo
    return x
