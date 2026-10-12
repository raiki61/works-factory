# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""1 回目の差分の審査役の返答の受け付け（節 delta-accept）。

返答（with: reply）を照らし（fixboard.delta_review_problems: 穴は差分が触ったファイルの今の姿に在る字列・検算の漏れ）、
準拠と品質の 2 判定の欄を承認済みの修正案の項目と照らして受ける（refix.accept_review。読むだけの役の作業ツリーの写しも比べる）。
受けたら置き場の delta/review-1.json に {pass（直す義務が無い）, owed, reply_file} を書く。拒否は理由のファイルを置いて
done: false、3 回目の拒否で done: true（諦め。review-1.json に pass: false と理由）。返り {ok, done, reason, reason_file}。
回す側の誤り（返答が読めない・置き場が無い・修正案の欄の控えが壊れた）は標準エラーに 1 行で非 0。
"""
import functools
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import fixio  # noqa: E402
import accept  # noqa: E402
import fixboard  # noqa: E402
import refix  # noqa: E402
import rolekit  # noqa: E402

N = 1
NAME = "delta-accept"


def main() -> None:
    reply, why = rolekit.parse_reply(os.environ["INPUTS_REPLY"])
    if reply is None:
        raise ValueError(why)
    place, repo = fixio.place(), fixio.repo()
    fix_reply = place / fixboard.FIX_REPLY_FILE
    bad = fixboard.delta_review_problems(place, N, reply, repo, fix_reply=fix_reply if fix_reply.is_file() else None)
    got = {"ok": False, "reason": "差分の審査の返答の照らしに通らない:\n" + "\n".join(f"  - {x}" for x in bad)} if bad else \
        refix.accept_review(reply, place, fixboard.start_tree(place), repo, n=N,
                            items=functools.partial(fixboard.place_items, place),
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
        sys.exit(f"delta-accept: {type(e).__name__}: {' '.join(str(e).split())}")
