"""run（工場の 1 回の実行）を 1 枚の HTML のページに組んで標準出力に出す入口（見る道具。決まりは viewer/AGENTS.md の E25、設計は
docs/design/viewer.md の 9 章、持ち主の決め run-page-v4）。引数を読み、読みと組みの部品を順に呼ぶだけ。

使い方（工場の clone の根から。ページはファイルに書かず標準出力に出すので、置き場は利用者がリダイレクトで決める）:
    uv run --isolated python3 viewer/runpage.py --target <対象のリポジトリ> [--run <run の id か頭の字>] > <ページ.html>

- 読みは viewer/runtrace.py の read と同じ（run の家は殻と同じ関数で引き、Archon の DB は読むだけで開く）。--run が無ければ一番新しい
  親の run。組みは src/page.py。外へは何も送らない
- 止まる時（run の家に DB が無い・run が当たらない・対象のフォルダが無いなど）は 1 行の訳を標準エラーに出し、終了の値 2
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bin._lib import launcher  # noqa: E402
from viewer import runtrace  # noqa: E402
from viewer.src import page  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="viewer/runpage.py", description=__doc__.splitlines()[0])
    parser.add_argument("--target", required=True, help="対象のリポジトリ（run の家を引く）")
    parser.add_argument("--run", default="", help="ページにする run の id か頭の字（無ければ一番新しい親の run）")
    args = parser.parse_args(argv)
    try:
        data = runtrace.read(args.target, args.run, dict(os.environ), Path.cwd())
        target = launcher.target_root(Path(args.target), Path.cwd())
    except (runtrace.Refused, launcher.Stop) as stop:
        print(f"runpage: {stop}", file=sys.stderr)
        return 2
    made = page.render(data, target, runtrace.PACK["pack"])
    sys.stdout.buffer.write(made.encode("utf-8"))
    sys.stdout.flush()
    print(f"runpage: run {data['run']['id'][:8]}・作りは {data['shape_from']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
