#!/bin/sh
# 種の TDD の実行器: 第 1 引数に JUnit XML を書き、残りの引数（試験のファイルと node id）だけを走らせる。対象の根で走る
out=$1
shift
PYTHONDONTWRITEBYTECODE=1 exec uv run --no-project --with pytest==9.1.1 pytest -p no:cacheprovider --continue-on-collection-errors --junitxml="$out" "$@"
