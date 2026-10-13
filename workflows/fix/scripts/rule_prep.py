# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 rule-prep（形 "" の裁定の輪の頭）: 裁定役の指示書を組んで置き場に書く（ruling.prep。作業ツリーの姿を控え、申し出の控え・
判定・依頼・持ち主の決まりを名指す）。2 回目からは前の回の拒否の理由のファイル（rule-accept が書いた reject-rule-accept-<k>.md）を
1 行目で名指す。返り {prompt_file, iteration}。裁く申し出が無い・判定の写しが無い: 標準エラーに 1 行で非 0。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))

import fixboard  # noqa: E402
import fixrules  # noqa: E402
import policy  # noqa: E402
import rolekit  # noqa: E402
import rulebook  # noqa: E402
import ruling  # noqa: E402
import startrec  # noqa: E402

RULES = Path(__file__).resolve().parents[1] / "commands" / "fix-rules"
rulebook.CANON = RULES / "common.md"
fixrules.SHARED = rulebook.CANON
fixrules.RULES_DIR = RULES
ACCEPT = "rule-accept"


def main() -> dict:
    place, repo = boundary.place("fix"), boundary.work_tree()
    judgment = place / fixboard.JUDGMENT_FILE
    if not judgment.is_file():
        raise ValueError(f"置き場に判定の写し {judgment.name} が無い")
    done = rolekit.attempt(place, ruling.ROLE) - 1
    reject = place / fixboard.REJECT_NAME.format(name=ACCEPT, k=done)
    start = startrec.read(place)
    got = ruling.prep(place, repo, {"judgment_file": str(judgment), "policy_path": policy.frozen_copy(start)},
                      reject_file=str(reject) if done and reject.is_file() else "", lang=rolekit.lang_line(start))
    return {"prompt_file": got["prompt_file"], "iteration": int(got["iteration"])}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"rule-prep: {type(e).__name__}: {' '.join(str(e).split())}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(out)
