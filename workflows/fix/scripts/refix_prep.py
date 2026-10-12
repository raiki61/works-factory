# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""1 回目の手直しの役の支度（節 refix-prep）: 1 回目の審査（置き場の delta/review-1.json）が直す義務を出した時だけ、義務と差分の
材料を置き場の refix1-brief.json に書き（fixboard.prep_fix）、指示書を組んで置き場に書く（fixboard.refix_prompt。決まりは
commands/fix-rules/ の refix.md と common.md。前の回の拒否が在れば理由のファイルを 1 行目で名指す）。
審査を受けていない・義務が無い（pass）・審査を諦めた時は go: false（手直しの役を起こさない）。返り {prompt_file, go, iteration}
（iteration は受け付けの拒否の数 + 1）。回す側の誤り（控えと義務が食い違う・修正案の欄の控えが壊れた）は標準エラーに 1 行で非 0。
"""
import functools
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import fixio  # noqa: E402
import fixboard  # noqa: E402
import groups  # noqa: E402
import policy  # noqa: E402
import refix  # noqa: E402
import refixrules  # noqa: E402
import rolekit  # noqa: E402
import rulebook  # noqa: E402
import startrec  # noqa: E402

N = 1
ACCEPT = "refix-accept"   # 受け付けの節（拒否の控えの名）
RULES = Path(__file__).resolve().parents[1] / "commands" / "fix-rules"
refixrules.RULES = RULES / "refix.md"
rulebook.CANON = RULES / "common.md"


def main() -> None:
    place = fixio.place()
    iteration = len(rolekit.rejected(place, ACCEPT)) + 1
    record = fixboard.read_json(place / fixboard.DELTA_DIR / fixboard.DELTA_REVIEW.format(N))
    if not isinstance(record, dict) or record.get("pass") is not False or record.get("gave_up"):
        boundary.returns({"prompt_file": "", "go": False, "iteration": iteration})
        return
    head = place / fixboard.REFIX_HEAD_FILE.format(N)
    if not head.is_file():
        fixboard.write_json(head, {"tree": groups.end_tree(fixio.repo())})
    start = startrec.read(place)
    fix_reply = place / fixboard.FIX_REPLY_FILE
    got = fixboard.prep_fix(place, N, items=functools.partial(fixboard.place_items, place), plan_review=fixboard.plan_review_file(place),
                            fix_reply=fix_reply if fix_reply.is_file() else None, policy=fixboard.policy_brief(start))
    if not got["ok"]:
        raise ValueError(got["reason"])
    text = fixboard.refix_prompt(N, {"brief_file": got["brief_file"], "diff_file": got["diff_file"], "policy_path": policy.frozen_copy(start),
                                     "request_file": str(start.get("request_file") or "")},
                                 reject_file=fixboard.last_reject_file(place, ACCEPT), iteration=iteration,
                                 lang=rolekit.lang_line(start))
    prompt = fixboard.write_text(place / fixboard.REFIX_PROMPT.format(refix.passes()[N]["fix"]), text)
    boundary.returns({"prompt_file": str(prompt), "go": True, "iteration": iteration})


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"refix-prep: {type(e).__name__}: {' '.join(str(e).split())}")
