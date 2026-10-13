# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 rule-accept（形 "" の裁定の輪の終わり）: 裁定役の返答を照らし（ruling.accept_rule: 読むだけの見張り・名指しの現物・裁定の形）、
通れば裁定を置き場の conflicts.json に積む。拒めば理由を置き場の reject-rule-accept-<iteration>.md に書き（次の rule-prep が名指す）、
3 回目の拒否では裁かれていない申し出を人へ回して done。返り {ok, done, reason, reason_file}。
回す側の誤り（返答・回の番号が読めない・rule-prep の控えが無い）は標準エラーに 1 行で非 0。
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))

import accept  # noqa: E402
import fixboard  # noqa: E402
import oneline  # noqa: E402
import rolekit  # noqa: E402
import ruling  # noqa: E402

NAME = "rule-accept"


def main() -> dict:
    reply, why = rolekit.parse_reply(os.environ["INPUTS_REPLY"])
    if reply is None:
        raise ValueError(why)
    iteration = int(os.environ["INPUTS_ITERATION"])
    place, repo = boundary.place("fix"), boundary.work_tree()
    got = ruling.accept_rule(reply, place, fixboard.base_rev_of(place), repo,
                             keys=accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", "")))
    if got["ok"]:
        return {"ok": True, "done": True, "reason": "", "reason_file": ""}
    path = fixboard.write_text(place / fixboard.REJECT_NAME.format(name=NAME, k=iteration), str(got["reason"]) + "\n")
    return {"ok": False, "done": bool(got["done"]), "reason": str(got["reason"]), "reason_file": str(path)}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"{NAME}: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(out)
