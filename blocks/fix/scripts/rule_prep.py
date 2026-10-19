# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node rule-prep（全体の形の裁定の輪の頭）: 作業ツリーの姿を控え（rule-tree.json。読むだけの役の見張り）、裁定役の指示を md から
組む（src/ruling.prep の値を src/prompts.ruler_values が prompts/ruler.md に入れる）。前の回の却下は控え rejects-rule.json の全部。
返り {prompt, iteration}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import oneline  # noqa: E402

from src import board, prompts, ruling, runvals  # noqa: E402


def main() -> dict:
    place, repo = ports.place(), Path.cwd()
    judgment = place / board.JUDGMENT_FILE
    if not judgment.is_file():
        raise ValueError(f"置き場に判定の写し {judgment.name} が無い")
    got = ruling.prep(place, repo, {"judgment_file": str(judgment), "policy_path": runvals.read(place)["policy"]})
    out = prompts.ruler(place, got)
    return {"prompt": out["prompt"], "iteration": int(got["iteration"])}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"rule-prep: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(out)
