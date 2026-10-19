# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""line の後始末の node sweep-children（報告の後、line の返す node result の前。docs/design/line.md の 1.3 の 27・1.5。今のまま）。

fix の組の子の run が残した作業ツリーと枝を消し、{cleaned, left, error} を返す。result がこれを line の返りの欄 children に載せる。
この run の子で status が completed の物を、子を起こした node と、それと同じ include の中の子の作業ツリーを読む node が済んだ時だけ
選ぶことと、止めた Archon の起こし方は埋め childsweep（埋め P7）。
node は落ちない: 落ちると result がこの node の返りを読めず line の返りまで落ちるので、共通の口を読めない時も例外も error に畳む。
入力は無い。node の cwd は run の作業ツリーで、Archon の --cwd に渡す。
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
try:
    sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
    import ports
    unread = None
except Exception as error:   # node は落ちない（上の docstring）
    ports, unread = None, error


def sweep() -> dict:
    childsweep = ports.polyfill("childsweep")   # 読めない訳も ports.run が fallback に畳む
    return childsweep.sweep(os.environ["WORKFLOW_ID"], os.getcwd(), dict(os.environ))


def fallback(reason: str) -> dict:
    return {"cleaned": [], "left": [], "error": reason}



def main() -> None:
    if ports is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(fallback(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        ports.run(sweep, fallback)


if __name__ == "__main__":   # 試験は名で読んで main を直に呼ぶ
    main()
