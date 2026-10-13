# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""n 回目の手直しの役の支度（節 refix-prep・refix2-prep。入力 n は 1 か 2）: n 回目の審査（置き場の delta/review-<n>.json）が直す
義務を出した時だけ、義務と差分の材料を置き場の refix<n>-brief.json に書き（fixboard.prep_fix）、指示書を組んで置き場に書く
（fixboard.refix_prompt。決まりは commands/fix-rules/ の refix.md と common.md。前の回の拒否が在れば、この輪の拒否の理由の全部のファイルを 1 行目で名指す）。
審査を受けていない・義務が無い（pass）・審査を諦めた時は go: false（手直しの役を起こさない）。返り {prompt_file, go, iteration}
（iteration は受け付けの拒否の数 + 1）。回す側の誤り（控えと義務が食い違う・修正案の欄の控えが壊れた）は標準エラーに 1 行で非 0。
"""
import functools
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import fixboard  # noqa: E402
import groups  # noqa: E402
import oneline  # noqa: E402
import policy  # noqa: E402
import refix  # noqa: E402
import refixrules  # noqa: E402
import rolekit  # noqa: E402
import rulebook  # noqa: E402
import startrec  # noqa: E402

RULES = Path(__file__).resolve().parents[1] / "commands" / "fix-rules"
refixrules.RULES = RULES / "refix.md"
rulebook.CANON = RULES / "common.md"


def main(n: int) -> None:
    accept = f"{refix.FIX_ROLE[n]}-accept"   # 受け付けの節（拒否の控えの名）
    place = boundary.place("fix")
    iteration = rolekit.attempt(place, accept)
    record = fixboard.read_json(place / fixboard.DELTA_DIR / fixboard.DELTA_REVIEW.format(n))
    if not isinstance(record, dict) or record.get("pass") is not False or record.get("gave_up"):
        boundary.returns({"prompt_file": "", "go": False, "iteration": iteration})
        return
    head = place / fixboard.REFIX_HEAD_FILE.format(n)
    if not head.is_file():
        fixboard.write_json(head, {"tree": groups.end_tree(boundary.work_tree())})
    start = startrec.read(place)
    fix_reply = place / fixboard.FIX_REPLY_FILE
    got = fixboard.prep_fix(place, n, items=functools.partial(fixboard.place_items, place), plan_review=fixboard.plan_review_file(place),
                            fix_reply=fix_reply if fix_reply.is_file() else None, policy=fixboard.policy_brief(start))
    if not got["ok"]:
        raise ValueError(got["reason"])
    text = fixboard.refix_prompt(n, {"brief_file": got["brief_file"], "diff_file": got["diff_file"], "policy_path": policy.frozen_copy(start),
                                     "request_file": str(start.get("request_file") or "")},
                                 reject_file=fixboard.rejects_file(place, accept, iteration - 1), iteration=iteration,
                                 lang=rolekit.lang_line(start))
    prompt = fixboard.write_text(place / fixboard.REFIX_PROMPT.format(refix.passes()[n]["fix"]), text)
    boundary.returns({"prompt_file": str(prompt), "go": True, "iteration": iteration})


if __name__ == "__main__":
    n = refix.round_input(os.environ.get("INPUTS_N"), "refix_prep")
    try:
        main(n)
    except Exception as e:
        sys.exit(f"{refix.FIX_ROLE[n]}-prep: {type(e).__name__}: {oneline.one_line(e)}")
