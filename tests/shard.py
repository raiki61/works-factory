# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""CI の試験を秒数で釣り合う分けに割って、1 つの分けだけを走らせる（テストのモジュールではない。test_*.py に当たらない）。

- 走らせる: リポジトリの根から `uv run --isolated python3 -m tests.shard --shard 1/4 --record <秒数の置き場>`。
  モジュールは `unittest discover -s . -t .` が見つける試験のモジュールを集め、
  秒数の表 `tests/shard-seconds.json` で重い順に一番軽い分けへ置く。表に無いモジュールは表の中央値の秒数とみなす。
  置いた後で、どの分けにも入らないモジュールと 2 つの分けに入ったモジュールが 0 かを確かめ、0 でなければ落ちる。
  表が古くても分けが偏るだけで、試験は漏れない。
- 表を直す: CI の各分けが上げた秒数（artifact の `shard-seconds-<i>`）を取り、
  `python3 -m tests.shard --merge <置き場>...` で表を作り直して、PR で入れる。
"""
import argparse
import json
import pathlib
import statistics
import sys
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TABLE = ROOT / "tests" / "shard-seconds.json"


def module_names(suite: unittest.TestSuite) -> set[str]:
    found = set()
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            found |= module_names(item)
        elif type(item).__module__ == "unittest.loader":
            found.add(item._testMethodName)   # 読み込めないモジュールは discover が _FailedTest（名はモジュール名）にする
        else:
            found.add(type(item).__module__)
    return found


def modules(root: pathlib.Path) -> list[str]:
    return sorted(module_names(unittest.TestLoader().discover(str(root), top_level_dir=str(root))))


def load_seconds(path: pathlib.Path) -> dict[str, float]:
    return json.loads(path.read_text(encoding="utf-8"))


def costs(names: list[str], seconds: dict[str, float]) -> dict[str, float]:
    unknown = statistics.median(seconds.values()) if seconds else 1.0
    return {name: seconds.get(name, unknown) for name in names}


def total(names: list[str], seconds: dict[str, float]) -> float:
    return sum(costs(names, seconds).values())


def plan(names: list[str], seconds: dict[str, float], n: int) -> list[list[str]]:
    cost = costs(names, seconds)
    shards: list[list[str]] = [[] for _ in range(n)]
    totals = [0.0] * n
    for name in sorted(names, key=lambda name: (-cost[name], name)):
        lightest = totals.index(min(totals))
        shards[lightest].append(name)
        totals[lightest] += cost[name]
    return [sorted(s) for s in shards]


def check(names: list[str], shards: list[list[str]]) -> None:
    placed = [name for s in shards for name in s]
    left_out = sorted(set(names) - set(placed))
    doubled = sorted({name for name in placed if placed.count(name) > 1})
    if left_out or doubled:
        sys.exit(f"分けに入らないモジュール: {left_out} / 2 つ以上の分けに入ったモジュール: {doubled}")


def merge(paths: list[pathlib.Path]) -> dict[str, float]:
    joined: dict[str, float] = {}
    for path in paths:
        joined.update(load_seconds(path))
    return {name: round(joined[name], 1) for name in sorted(joined)}


class TimedModule(unittest.TestSuite):
    def __init__(self, name: str, tests: unittest.TestSuite, seconds: dict[str, float]):
        super().__init__([tests])
        self.name = name
        self.seconds = seconds

    def run(self, result, debug=False):
        start = time.perf_counter()
        super().run(result, debug)
        self.seconds[self.name] = time.perf_counter() - start
        return result


def run(names: list[str], record: pathlib.Path | None) -> int:
    loader = unittest.TestLoader()
    seconds: dict[str, float] = {}
    suite = unittest.TestSuite(TimedModule(name, loader.loadTestsFromName(name), seconds) for name in names)
    result = unittest.TextTestRunner().run(suite)
    if record is not None:
        record.write_text(json.dumps(seconds, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not result.testsRun:
        return 5   # unittest と同じく、1 件も走らない分けを緑にしない
    return 0 if result.wasSuccessful() else 1


def shard_arg(value: str) -> tuple[int, int]:
    index, count = (int(part) for part in value.split("/"))
    if not 1 <= index <= count:
        raise argparse.ArgumentTypeError(f"i/N の i は 1 から N: {value}")
    return index, count


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m tests.shard")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--shard", type=shard_arg, metavar="I/N")
    action.add_argument("--merge", type=pathlib.Path, nargs="+", metavar="SECONDS")
    parser.add_argument("--record", type=pathlib.Path)
    args = parser.parse_args(argv)
    if args.merge:
        TABLE.write_text(json.dumps(merge(args.merge), indent=2) + "\n", encoding="utf-8")
        return 0
    index, count = args.shard
    names = modules(ROOT)
    shards = plan(names, load_seconds(TABLE), count)
    check(names, shards)
    return run(shards[index - 1], args.record)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
