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
- 試験を集める前に、この過程の環境から試験の子へ渡さない名（tests/bin/hermetic.dropped）を外す（hermetic.scrub）。
- 集め方: 別の解釈系で discover し、親にはモジュールの名・数・置き場だけを戻す。親は試験本体を import しない。
- 並べ方: モジュールごとに新しい解釈系を起こし、同時に WORKERS_ENV（既定は SHARING の注記）本まで並べる。
  scrub の控えも子へ渡す。出力は unittest のまま（進みの印・落ちた試験の名と traceback をモジュールの名の順に・最後の Ran N tests と
  OK / FAILED）。1 つのモジュールの試験は同じ子で順に走るので、モジュールの中で置き場を分け合う試験はそのまま走る。
  子は直下の親が替わったら（親だけが止められた）終わり、子が途中で落ちたら、終わらなかったモジュールを赤にして最後の数えまで出す。
- 名指しのパスだけを走らせる: `python3 -m tests.shard --paths PATH...`（tests/changed.py が使う）。
  同じ集め方で見つけたモジュールのうち、名指しのファイルか名指しのフォルダの下に在る物だけを走らせる。
  手元の確かめなので、Archon を起こす試験を見送る旗 hermetic.ARCHON_DEFER_ENV を立てて子へ渡す（見送りの判断は tests/archon.py の
  runner の 1 か所。CI の旗 REQUIRED が在れば見送らない）。見送った試験は最後の数えの前に名を並べる。
  頭（__init__.py）で読めないパッケージ（discover がパッケージ名の 1 件にする物）は、その下のパスでも選ぶ。
  試験のモジュールの集め方（discover と PATTERN）は suites() の 1 か所に在り、作業中の選びと CI の分けの両方がそこから読む。
- 表を直す: CI の各分けが上げた秒数（artifact の `shard-seconds-<i>`）を取り、
  `python3 -m tests.shard --merge <置き場>...` で表を作り直して、PR で入れる。
"""
import argparse
import io
import importlib
import json
import subprocess
import tempfile
import os
import pathlib
import statistics
import sys
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed

from tests.bin import hermetic

ROOT = pathlib.Path(__file__).resolve().parents[1]
TABLE = ROOT / "tests" / "shard-seconds.json"
PATTERN = "test*.py"
WORKERS_ENV = "WORKS_FACTORY_TEST_WORKERS"
# 並べる子の数の既定は、機械の CPU の数を、同じ機械で同時にこの口を回しうる数で割った数。工場は同じ機械で run を 2〜3 本回し、
# run の中でも修正の段が組ごとの子の run を並べ、子もそれぞれこの口を回す。3 本 × 2 組で 6 とし、CPU が 12 に満たない機械
# （CI の 4 CPU の機械など）では 1 つの子で順に回す
SHARING = 6
POLL = 0.2   # 子が親の替わりを見る間隔（秒。lib/tree_run.py の POLL と同じ）。見張りは親が替わるまで続き、期限は無い
BROKEN = "（子が途中で終わった）"


class ModuleLoader(unittest.TestLoader):
    def loadTestsFromModule(self, module, *args, **kwargs):
        suite = super().loadTestsFromModule(module, *args, **kwargs)
        suite.module = module.__name__
        return suite


def collect(root: pathlib.Path) -> dict[str, dict]:
    found = {}
    for suite in ModuleLoader().discover(str(root), pattern=PATTERN, top_level_dir=str(root)):
        # 読み込めない・モジュールの頭で見送ったモジュールも discover の名と数を保つ
        name = getattr(suite, "module", None) or next(iter(suite))._testMethodName
        if count := suite.countTestCases():
            found[name] = {"root": str(root), "count": count}
    return found


def isolated(action: str, root: pathlib.Path, name: str = "") -> dict:
    """試験の import と実行を使い捨ての解釈系に閉じ込め、字と数だけを持ち帰る。"""
    with tempfile.TemporaryDirectory(prefix="shard-result-") as tmp:
        output = pathlib.Path(tmp) / "result.json"
        request = {"action": action, "root": str(root), "name": name, "output": str(output),
                   "parent": os.getpid(), "scrubbed": hermetic._SCRUBBED}
        env = hermetic.child_env(**hermetic.inherited(*hermetic.ARCHON_SETUP))
        done = subprocess.run([sys.executable, "-m", "tests.shard", "--child"], cwd=ROOT, env=env,
                              input=json.dumps(request), text=True)
        if done.returncode or not output.exists():
            raise ChildProcessError(f"{name or 'collect'} {BROKEN}: exit {done.returncode}")
        outcome = json.loads(output.read_text(encoding="utf-8"))
        if outcome.get("interrupted"):
            raise KeyboardInterrupt
        return outcome


def suites(root: pathlib.Path) -> dict[str, dict]:
    return isolated("collect", root.resolve())


def modules(root: pathlib.Path) -> list[str]:
    return sorted(suites(root))


def source(name: str) -> str:
    return name.replace(".", "/") + ".py"


def pick(names: list[str], paths: list[str]) -> list[str]:
    dirs = tuple(p.rstrip("/") + "/" for p in paths)

    def named(name: str) -> bool:
        # 頭（__init__.py）で読み込めないパッケージは、discover がパッケージ名の 1 件にするので、その下のパスでも選ぶ
        package = name.replace(".", "/") + "/"
        return source(name) in paths or source(name).startswith(dirs) or any(d.startswith(package) for d in dirs)

    return sorted(name for name in names if named(name))


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


class Recorded:
    """子で走った 1 件の試験の、結果の印字（TextTestResult.printErrors）に要る形だけの写し"""

    def __init__(self, description: str):
        self.description = description

    def __str__(self) -> str:
        return self.description

    def shortDescription(self) -> None:
        return None   # 説明の 2 行目は子の getDescription が description に入れ済み


def watch_parent(ppid: int) -> None:
    """直下の親が替わったら（親だけが SIGKILL・OOM で消えた）試験の子を終える。"""
    def watch() -> None:
        while os.getppid() == ppid:
            time.sleep(POLL)
        os._exit(1)

    threading.Thread(target=watch, daemon=True).start()


def run_module(name: str, root: pathlib.Path) -> dict:
    """子の中で 1 モジュールを走らせ、結果を親へ渡せる形（字と数）で返す"""
    stream = io.StringIO()
    result = unittest.TextTestResult(stream, descriptions=True, verbosity=1)
    start = time.perf_counter()
    sys.path.insert(0, str(root))
    loader = ModuleLoader()
    try:
        suite = loader.loadTestsFromModule(importlib.import_module(name))
    except unittest.SkipTest as e:
        suite = unittest.loader._make_skipped_test(name, e, loader.suiteClass)
    except Exception:
        suite, _ = unittest.loader._make_failed_import_test(name, loader.suiteClass)
    suite.run(result)

    def described(pairs):
        return [(result.getDescription(test), text) for test, text in pairs]

    return {"seconds": time.perf_counter() - start, "dots": stream.getvalue(), "run": result.testsRun,
            "errors": described(result.errors), "failures": described(result.failures),
            "skipped": described(result.skipped), "expectedFailures": described(result.expectedFailures),
            "unexpectedSuccesses": [result.getDescription(test) for test in result.unexpectedSuccesses]}


class Parallel:
    """同時に n 本まで、モジュールごとに新しい解釈系で走らせる。集計は名前順、進みの印は終了順。
    中断時は待ち行列を取り消し、実行中の子だけを待つ。親が消えた子は watch_parent が止める。"""

    def __init__(self, found: dict[str, dict], n: int, seconds: dict[str, float]):
        self.found, self.n, self.seconds = found, n, seconds

    def __call__(self, result: unittest.TextTestResult) -> unittest.TextTestResult:
        done, broken = {}, {}
        with ThreadPoolExecutor(self.n) as pool:
            futures = {pool.submit(isolated, "run", pathlib.Path(info["root"]), name): name
                       for name, info in self.found.items()}
            try:
                for future in as_completed(futures):
                    try:
                        done[futures[future]] = outcome = future.result()
                    except ChildProcessError as e:
                        broken[futures[future]] = f"{type(e).__name__}: {e}\n"
                        continue
                    result.stream.write(outcome["dots"])
                    result.stream.flush()
            except BaseException:
                pool.shutdown(cancel_futures=True)
                raise
        deferred = sorted({test.split("\n")[0] for name in done for test, why in done[name]["skipped"]
                           if why.startswith(hermetic.ARCHON_DEFERRED)})   # 1 行目だけ（2 行目は docstring）
        if deferred:
            result.stream.write(f"\n{hermetic.ARCHON_DEFERRED}（{len(deferred)} 件）:\n" + "".join(f"  {t}\n" for t in deferred))
            result.stream.flush()
        result.errors.extend((Recorded(f"{name} {BROKEN}"), text) for name, text in sorted(broken.items()))
        for name in sorted(done):
            outcome = done[name]
            self.seconds[name] = outcome["seconds"]
            result.testsRun += outcome["run"]
            for kind in ("errors", "failures", "skipped", "expectedFailures"):
                getattr(result, kind).extend((Recorded(test), text) for test, text in outcome[kind])
            result.unexpectedSuccesses.extend(Recorded(test) for test in outcome["unexpectedSuccesses"])
        return result


def run(found: dict[str, dict], record: pathlib.Path | None, n: int) -> int:
    seconds: dict[str, float] = {}
    result = unittest.TextTestRunner().run(Parallel(found, n, seconds))
    if record is not None:
        record.write_text(json.dumps(seconds, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not result.testsRun and result.wasSuccessful():
        return 5   # unittest と同じく、1 件も走らない分けを緑にしない（子が落ちて 1 件も数えられなかった分けは 1）
    return 0 if result.wasSuccessful() else 1


def workers() -> int:
    """並べる子の数。環境変数 WORKERS_ENV が在ればその数、無ければ CPU の数を SHARING で割った数（1 以上）"""
    value = os.environ.get(WORKERS_ENV)
    if value is None:
        return max(1, (os.cpu_count() or 1) // SHARING)
    if not value.isdigit() or int(value) < 1:
        sys.exit(f"{WORKERS_ENV} は 1 以上の整数: {value!r}")
    return int(value)


def shard_arg(value: str) -> tuple[int, int]:
    index, count = (int(part) for part in value.split("/"))
    if not 1 <= index <= count:
        raise argparse.ArgumentTypeError(f"i/N の i は 1 から N: {value}")
    return index, count


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m tests.shard")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--shard", type=shard_arg, metavar="I/N")
    action.add_argument("--paths", nargs="+", metavar="PATH")
    action.add_argument("--merge", type=pathlib.Path, nargs="+", metavar="SECONDS")
    parser.add_argument("--record", type=pathlib.Path)
    args = parser.parse_args(argv)
    if args.merge:
        TABLE.write_text(json.dumps(merge(args.merge), indent=2) + "\n", encoding="utf-8")
        return 0
    n = workers()   # 名は WORKS_FACTORY_ で始まり scrub が外すので、外す前に読む
    hermetic.scrub()
    os.environ.pop(hermetic.ARCHON_DEFER_ENV, None)   # scrub は残す名なので、親のシェルの旗が --shard の道に漏れないよう外す。立てるのは --paths だけ
    found = suites(ROOT)
    if args.paths:
        names = pick(sorted(found), args.paths)
        os.environ[hermetic.ARCHON_DEFER_ENV] = "1"   # 手元の確かめは Archon を起こさない（tests/archon.py の runner。CI は REQUIRED で回す）
        print(f"名指しのパスに当たる {len(names)} モジュールを回す（回さない: {len(found) - len(names)} モジュール。"
              f"全部は CI が回す）:")
        print("\n".join(f"  {name}" for name in names))
        sys.stdout.flush()
        return run({name: found[name] for name in names}, args.record, n)
    index, count = args.shard
    names = sorted(found)
    shards = plan(names, load_seconds(TABLE), count)
    check(names, shards)
    return run({name: found[name] for name in shards[index - 1]}, args.record, n)


def child() -> None:
    request = json.load(sys.stdin)
    watch_parent(request["parent"])
    hermetic.scrub()
    hermetic._SCRUBBED.update(request["scrubbed"])
    root = pathlib.Path(request["root"])
    try:
        outcome = collect(root) if request["action"] == "collect" else run_module(request["name"], root)
    except KeyboardInterrupt:
        outcome = {"interrupted": True}
    pathlib.Path(request["output"]).write_text(json.dumps(outcome), encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1:] == ["--child"]:
        child()
    else:
        sys.exit(main(sys.argv[1:]))
