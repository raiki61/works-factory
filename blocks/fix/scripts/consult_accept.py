# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node consult-accept・ruled-consult-accept（修正の輪の中、答えの役の後）: 答え（飛ばされた周は null）を頼みごとに確かめ、1 頼み
1 行を place の trace.jsonl に書き、修正役が次の周に読む答えのファイルを書く（src/consult.settle。今のまま）。入力 pass は first か
ruled。返り {consulted, answer_file}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import oneline  # noqa: E402

from src import consult, rules  # noqa: E402


def main() -> dict:
    pass_ = os.environ["INPUTS_PASS"]
    node = rules.answer_node(pass_)
    try:
        answer = ports.polyfill("skip_value").parsed(os.environ.get("INPUTS_ANSWER"))
    except ValueError:
        answer = None   # 読めない答えは答えの無い周と同じ（行は unavailable）
    got = consult.settle(ports.place(), answer, pass_, node)
    return {"consulted": bool(got["consulted"]), "answer_file": str(got["answer_file"] or "")}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"consult-accept: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(out)
