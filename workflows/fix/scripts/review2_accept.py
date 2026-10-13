# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""2 回目の差分の審査役の返答の受け付け（節 review2-accept）。

支度（cut2）が go: false で役を起こさなかった（with: reply が null）時は done: true（2 回目の審査は回らなかった。控えは書かない）。
返答が在れば照らし（fixboard.delta_review_problems: 穴は手直しの差分が触ったファイルの今の姿に在る字列・fixed と言われた穴の
検算の漏れ）、受ける（refix.accept_review の 2 回目。読むだけの役の作業ツリーの写しも比べる）。受けたら置き場の
delta/review-2.json に {pass（直す義務が無い）, owed, reply_file} を書く。拒否は理由のファイルを置いて done: false、3 回目の
拒否で done: true（諦め。review-2.json に pass: false と理由）。返り {ok, done, reason, reason_file}。
回す側の誤り（返答が読めない・置き場が無い）は標準エラーに 1 行で非 0。
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
import refix  # noqa: E402
import rolekit  # noqa: E402

N = 2
NAME = "review2-accept"
NOT_LAUNCHED = "2 回目の審査役を起こさなかった（1 回目の手直しが fixed と答えた穴が無い）"


def main() -> None:
    raw = os.environ["INPUTS_REPLY"]
    if boundary.value(raw) is None:
        boundary.returns({"ok": True, "done": True, "reason": NOT_LAUNCHED, "reason_file": ""})
        return
    reply, why = rolekit.parse_reply(raw)
    if reply is None:
        raise ValueError(why)
    place, repo = boundary.place("fix"), boundary.work_tree()
    bad = fixboard.delta_review_problems(place, N, reply, repo)
    got = {"ok": False, "reason": "差分の審査の返答の照らしに通らない:\n" + "\n".join(f"  - {x}" for x in bad)} if bad else \
        refix.accept_review(reply, place, fixboard.start_tree(place), repo, n=N,
                            keys=accept.status_keys(os.environ.get("INPUTS_STATUS_GUARDED", "")))
    out = fixboard.accept_out(place, NAME, got)
    record = place / fixboard.DELTA_DIR / fixboard.DELTA_REVIEW.format(N)
    if out["ok"]:
        fixboard.write_json(record, {"pass": got["owed"] == 0, "owed": got["owed"], "reply_file": got["reply_file"]})
    elif out["done"]:
        fixboard.write_json(record, {"pass": False, "owed": 0, "reply_file": "", "gave_up": True,
                                  "reason": rolekit.given_up_reason(place, NAME)})
    boundary.returns(out)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"{NAME}: {type(e).__name__}: {' '.join(str(e).split())}")
