# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""作業中の試験の選び（run の中の確かめの全体の命令。テストのモジュールではない。test_*.py に当たらない）。

変更（origin/main との merge-base からの差と、未追跡を含む作業ツリーの差）に直に当たる試験のモジュールと、層の柵
（tests/layers/）だけを unittest で回す（モジュールを子に並べる。並べる数は tests/shard.py の WORKERS_ENV と SHARING）。全部の試験は CI（.github/workflows/tests.yml）が回す。持ち主の決め 2026-10-12（#130）。
- 選び: lib/impact.py の map が変更に直に当てたファイル（direct。起点か深さ 1）・変わったファイル・層の柵のフォルダを候補にし、
  どれが試験のモジュールかは tests/shard.py --paths が CI と同じ集め方（discover の規則）で決める。
  impact の select_tests は選べたかとその訳だけに使う（impact の試験の名の規則で候補を絞らない）
- 選べない時（選びが全部が要ると言った時・WHOLE と WHOLE_DIRS の変更・起点が取れない時・選びが落ちた時）も全部は回さず、
  選べた範囲と層の柵だけを回し、全部の試験は CI に寄せると訳を出す（持ち主の決め full-suite-in-ci。docs/owner-decisions.md）
- 出力: 選んだモジュール・回さないモジュールの数・訳を先に標準出力へ出し、最後は unittest の数え（Ran N tests）のまま
"""
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "lib"))

import impact  # noqa: E402

BASE_REF = "origin/main"
FENCE = "tests/layers"
# 多くの試験が頼るのに import の辺で届かない物（試験の命令・依存の宣言・CI・試験の助けと決まり）
WHOLE = ("tests/archon.py", "tests/AGENTS.md", "pyproject.toml")
WHOLE_DIRS = (".github/",)
IN_CI = "全部の試験は CI に寄せる（持ち主の決め full-suite-in-ci）"


def merge_base():
    try:
        done = subprocess.run(["git", "-C", str(ROOT), "merge-base", BASE_REF, "HEAD"], capture_output=True, text=True)
    except OSError:
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def choose():
    """(試験の候補のパス, 選べなかった訳)。訳が在っても全部は回さず、候補だけを回す"""
    base = merge_base()
    if not base:
        return [FENCE], [f"起点が取れない（git merge-base {BASE_REF} HEAD が失敗）"]
    try:
        m = impact.map(ROOT, rev=base, diff=True)
        changed = m["seeds"]["from_diff"]
        reached = [p for p in [*m["seeds"]["files"], *m["reach"]] if impact.direct(m, p)]
        paths = sorted({*reached, *changed}) + [FENCE]
        whole = [p for p in changed if p in WHOLE or p.startswith(WHOLE_DIRS)]
        if whole:
            return paths, [f"試験の全体に効く物が変わった: {p}" for p in whole]
        sel = impact.select_tests(m, direct_only=True)
    except Exception as e:   # 選びが落ちたら層の柵だけを回し、落ちた訳を出す
        return [FENCE], [f"選びが落ちた: {type(e).__name__}: {e}"]
    return paths, sel["reasons"] if sel["run_all"] else []


def main():
    started = time.monotonic()
    paths, reasons = choose()
    print(f"changed.py: 選びに {time.monotonic() - started:.1f} 秒")
    if reasons:
        print(f"{IN_CI}。選べなかった訳:")
        print("\n".join(f"  {r}" for r in reasons))
    sys.stdout.flush()
    return subprocess.run([sys.executable, "-m", "tests.shard", "--paths", *paths], cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())
