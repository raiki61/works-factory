#!/usr/bin/env python3
"""試験の 2 つの束（tests と lib/tests）を unittest で走らせる。CI と harness/ci.py が同じこれを呼ぶ。

各々の束は `python3 -m unittest discover -s <束> -t .` で走らせる（docs/plans/2026-10-11-foundation.md の「全体の決まり」）。

- 束のフォルダが無い: まだ試験が無いので見送り、見送ったことを 1 行出す。
- 終了の値 0: 通った。
- 終了の値 5（Python 3.12 の unittest が「1 件も走らなかった」時に返す値）:
  - 束の下に test*.py が 1 つも無い: まだ試験が無いので通す。そのことを 1 行出す。
  - test*.py が在る: 書いた試験が見つかっていない（__init__.py の抜けなど）ので落とす。
- ほかの値: 落とす。

最後に `UNITTEST_TOTAL ran=<走った件数の和>` を出す。harness/harness.config.json の unit_count_pattern がこの行を読む。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUITES = ("tests", "lib/tests")
NO_TESTS_RAN = 5


def main() -> int:
    total = 0
    failed: list[str] = []
    for suite in SUITES:
        directory = ROOT / suite
        if not directory.is_dir():
            print(f"UNITTEST_SKIP {suite}: フォルダが無い（まだ試験が無い）", flush=True)
            continue
        argv = [sys.executable, "-m", "unittest", "discover", "-s", suite, "-t", "."]
        print(f"UNITTEST_RUN {suite}: {' '.join(argv[1:])}", flush=True)
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
        sys.stdout.write(result.stdout)
        sys.stdout.write(result.stderr)
        counts = re.findall(r"^Ran (\d+) tests? in ", result.stderr, re.M)
        ran = int(counts[-1]) if counts else 0
        total += ran
        if result.returncode == 0:
            print(f"UNITTEST_OK {suite}: {ran} 件", flush=True)
        elif result.returncode == NO_TESTS_RAN and not any(directory.rglob("test*.py")):
            print(f"UNITTEST_EMPTY {suite}: test*.py が無い（まだ試験が無い）", flush=True)
        elif result.returncode == NO_TESTS_RAN:
            print(f"UNITTEST_FAILED {suite}: test*.py が在るのに 1 件も走らなかった（__init__.py の抜けを疑う）", flush=True)
            failed.append(suite)
        else:
            print(f"UNITTEST_FAILED {suite}: 終了の値 {result.returncode}", flush=True)
            failed.append(suite)
    print(f"UNITTEST_TOTAL ran={total}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
