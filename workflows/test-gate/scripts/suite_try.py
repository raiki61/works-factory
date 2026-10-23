# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node suite-try: 輪の 1 周の終わり。照らす前の実行器（suitewrite.pending）が在れば、走らせずに実行器の控えの tdd_suite に結ぶ
（suitewrite.adopt。持ち主の決め base-runs-nothing: 直す前の版では試験を何も走らせない）。実行器が JUnit XML を書くか・壊れていないかは、
修正の段の TDD の輪が関わる試験を最初に走らせた所で確かめ、壊れていれば書き直させる（docs/design/fix.md の 18 節）。照らした実行器を
取り置くのもそこ。{done, ok, why}（done はいつも真。書き手が作れなかった周は ok が偽と訳）"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def attempt() -> dict:
    import suitewrite
    from src import suite
    return suitewrite.adopt(suite.path(ports.place()))


if __name__ == "__main__":
    ports.run(attempt, lambda why: {"done": True, "ok": False, "why": why})
