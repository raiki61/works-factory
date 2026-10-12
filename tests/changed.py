# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""作業中の試験の選び（ASF の harness/harness.config.json の unit。テストのモジュールではない。test_*.py に当たらない）。

変更（origin/main との merge-base からの差と、未追跡を含む作業ツリーの差）に直に当たる試験のモジュールと、層の柵
（tests/layers/）だけを unittest で回す。全部の試験は CI（.github/workflows/tests.yml）が回す。持ち主の決め 2026-10-12（#130）。
- 選び: lib/impact.py の map と select_tests（direct_only。起点か深さ 1）が選んだパス・変わったファイル・層の柵のフォルダを候補にし、
  どれが試験のモジュールかは tests/shard.py --paths が CI と同じ集め方（discover の規則）で決める
- 全部を回す: 選びが全部が要ると言った時・WHOLE と WHOLE_DIRS の変更・起点が取れない時・選びが落ちた時（緑を仮定しない）。
  全部は CI と同じ集め方（tests/shard.py。discover の規則）を 1 つの分けで回す
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


def merge_base():
    try:
        done = subprocess.run(["git", "-C", str(ROOT), "merge-base", BASE_REF, "HEAD"], capture_output=True, text=True)
    except OSError:
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def choose():
    """(試験の候補のパス, 全部を回す訳)。訳が在れば全部を回す"""
    base = merge_base()
    if not base:
        return [], [f"起点が取れない（git merge-base {BASE_REF} HEAD が失敗）"]
    try:
        m = impact.map(ROOT, rev=base, diff=True)
        changed = m["seeds"]["from_diff"]
        whole = [p for p in changed if p in WHOLE or p.startswith(WHOLE_DIRS)]
        if whole:
            return [], [f"試験の全体に効く物が変わった: {p}" for p in whole]
        sel = impact.select_tests(m, direct_only=True)
    except Exception as e:   # 選びが落ちたら緑を仮定せず全部を回す
        return [], [f"選びが落ちた: {type(e).__name__}: {e}"]
    if sel["run_all"]:
        return [], sel["reasons"]
    return sorted({*sel["selected"], *changed}) + [FENCE], []


def main():
    started = time.monotonic()
    paths, reasons = choose()
    print(f"changed.py: 選びに {time.monotonic() - started:.1f} 秒")
    if reasons:
        print("全部の試験を回す。訳:")
        print("\n".join(f"  {r}" for r in reasons))
        cmd = ["-m", "tests.shard", "--shard", "1/1"]
    else:
        cmd = ["-m", "tests.shard", "--paths", *paths]
    sys.stdout.flush()
    return subprocess.run([sys.executable, *cmd], cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())
