# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""線の後始末の節 sweep-children（報告の後、線の返す節 result の前。issue #113）。

fix の並べの子の run が残した作業ツリーと枝を消し、{cleaned, left, error} を返す。result がこれを線の返りの欄
children に載せる。この run の子で status が completed の物を、子を起こした fan_out の節と join が済んだ時だけ選ぶことと、止めた
Archon の起こし方は境の埋め workflows/.shared/childsweep.py（埋め P7）。
今の works は run の中で切った worktree を自分で消していた（works/.shared/core/unittrees.py:275 の sweep）。
節は落ちない: 落ちると result がこの節の返りを読めず線の返りまで落ちるので、境の口を読めない時も例外も error に畳む。
入力は無い。節の cwd は run の作業ツリーで、Archon の --cwd に渡す。
"""
import json
import os
import sys
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    unread = None
except Exception as error:   # 節は落ちない（上の docstring）
    boundary, unread = None, error


def sweep() -> dict:
    import childsweep   # 境の口と同じ置き場。読めない訳も boundary.run が fallback に畳む
    return childsweep.sweep(os.environ["WORKFLOW_ID"], os.getcwd(), dict(os.environ))


def fallback(reason: str) -> dict:
    return {"cleaned": [], "left": [], "error": reason}


def main() -> None:
    if boundary is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(fallback(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        boundary.run(sweep, fallback)


if __name__ == "__main__":
    main()
