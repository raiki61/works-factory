# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 consult-accept・ruled-consult-accept（修正の輪の中、答えの役の後）: 答え（飛ばされた周は null）を頼みごとに確かめ（許すのは
頼んだ物の中だけ）、1 頼み 1 行を置き場の trace.jsonl に書き、修正役が次の周に読む答えのファイルを書く（consult.settle）。
頼みの無い周は consulted: false で何も書かない。入力 pass は first か ruled。
返り {consulted, answer_file}。回す側の誤り（pass が読めない・置き場が壊れた）は標準エラーに 1 行で非 0。
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))

import consult  # noqa: E402

NODES = {"first": "consult-answer", "ruled": "ruled-consult-answer"}   # 答えの役の節（記録に残す）


def main() -> dict:
    pass_ = os.environ["INPUTS_PASS"]
    if pass_ not in NODES:
        raise ValueError(f"入力 pass は {sorted(NODES)} のどれか: {pass_!r}")
    try:
        answer = boundary.parsed(os.environ.get("INPUTS_ANSWER"))
    except ValueError:
        answer = None   # 読めない答えは答えの無い周と同じ（行は unavailable）
    got = consult.settle(boundary.place("fix"), answer, pass_, NODES[pass_])
    return {"consulted": bool(got["consulted"]), "answer_file": str(got["answer_file"] or "")}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"consult-accept: {type(e).__name__}: {' '.join(str(e).split())}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(out)
