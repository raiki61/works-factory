# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node rule-accept（全体の形の裁定の輪の終わり）: 裁定役の返答を照らして積む（ruling.accept_rule。今のまま。作業ツリーが
rule-tree.json から動いた・id の過不足・limits・grounds・ask_why・replace_query の試し…）。3 回目の拒否で裁かれていない申し出を全部
ask_human にして人へ回す。返り {ok, done, reason, reason_file}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


import accept  # noqa: E402
import oneline  # noqa: E402
import rolekit  # noqa: E402

from src import board, ruling  # noqa: E402


NAME = "rule-accept"


def main() -> dict:
    reply, why = rolekit.parse_reply(os.environ["INPUTS_REPLY"])
    if reply is None:
        raise ValueError(why)
    place, repo = ports.place(), Path.cwd()
    got = ruling.accept_rule(reply, place, board.base_rev_of(place), repo,
                             keys=accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", "")))
    if got["ok"]:
        return {"ok": True, "done": True, "reason": "", "reason_file": ""}
    return {"ok": False, "done": bool(got["done"]), "reason": str(got["reason"]),
            "reason_file": rolekit.reject_file_or_blank(place, ruling.ROLE)}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"{NAME}: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(out)
