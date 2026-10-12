# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 fix-ruled-accept（形 "" の裁定の後の修正の輪の終わり）: 裁定の後の修正役の返答を受け付ける（fixboard.accept_reply の ruled。
裁定 fix_test_scope の limits のテストの変更はここで初めて許す。新しい申し出は機械が ask_human に裁いて積む）。TDD の輪の状態は
join が組の子から写した物（fixboard.ruled_states。凍結したテスト・範囲・変更に当たる試験の確かめに使う）。

- 範囲の相談の周（入力 consulted が true）は受け付けを回さず done: false
- 役を起こさなかった（入力 reply が null。直す裁定が無い）周は done: true
- 拒否は理由を置き場の reject-fix-ruled-accept-<iteration>.md に書いて done: false。iteration が 3 以上の拒否は名指しの単位だけを
  段の頭の木（fix-ruled-head.json）に戻して諦め、ほかを受けて done: true
- 範囲の外のはみ出しだけの返答は拒まずに範囲の相談に積むか機械が戻す（fixboard.settle_overflow）。積んだ回は done: false
置き場に残す物: fix-ruled-reply.json（受けた返答に 6 つの印と rejudge_requested を前の控えと論理和で重ね、印を changed にも置いた物。
assert-changed・collect が読む）・fix-units.json・allowed-tests.json。
返り {ok, done, reason, reason_file}。回す側の誤りは標準エラーに 1 行で非 0。
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import fixio  # noqa: E402

import fixboard  # noqa: E402
import rolekit  # noqa: E402
import startrec  # noqa: E402

NAME = "fix-ruled-accept"
NOT_LAUNCHED = "裁定の後の修正役を起こさなかった（直す裁定が無い）"


def main() -> dict:
    raw = os.environ["INPUTS_REPLY"]
    consulted = os.environ.get("INPUTS_CONSULTED", "").strip().lower() == "true"
    iteration = int(os.environ["INPUTS_ITERATION"])
    if consulted:
        return {"ok": False, "done": False, "reason": fixboard.CONSULTED, "reason_file": ""}
    if raw.strip() in ("", "null"):
        return {"ok": True, "done": True, "reason": NOT_LAUNCHED, "reason_file": ""}
    reply, why = rolekit.parse_reply(raw)
    if reply is None:
        raise ValueError(why)
    place, repo = fixio.place(), fixio.repo()
    owed = fixboard.ruled_owed(place)
    start = startrec.read(place)
    judgment = fixboard.read_json(place / fixboard.JUDGMENT_FILE) or {}
    head = fixboard.stage_head(place, fixboard.RULED_HEAD_FILE)
    state, tests_state = fixboard.ruled_states(place)
    log = fixio.writes_log()
    fixio.drop_runner_env()   # 対象のテストを走らせる前に Archon の変数を落とす（place は先に取った）
    got = fixboard.accept_reply(reply, place, repo, pass_="ruled", iteration=iteration, owed=owed,
                                judged=judgment.get("units"), suite=str(start.get("tdd_suite") or ""), state=state,
                                tests_state=tests_state, head=head, skip=fixio.SKIP, log=log)
    fixboard.write_json(place / fixboard.FIX_UNITS_FILE, got["units"])
    if got["ok"]:
        path = place / fixboard.RULED_REPLY_FILE
        fixboard.write_json(path, fixboard.reply_marks(got["reply"], fixboard.read_json(path)))
        fixboard.write_json(place / fixboard.ALLOWED_TESTS_FILE, fixboard.granted_tests(place))
        fixboard.trace(place, "fix_ruled_accepted", node=NAME, iteration=iteration, parked=sorted(got["parked"]))
        return {"ok": True, "done": True, "reason": "", "reason_file": ""}
    reason_file = fixboard.write_text(place / fixboard.REJECT_NAME.format(name=NAME, k=iteration), got["reason"] + "\n")
    done = fixboard.loop_done(got, iteration)
    fixboard.trace(place, "fix_ruled_rejected", node=NAME, iteration=iteration, done=done, parked=sorted(got["parked"]))
    return {"ok": False, "done": done, "reason": got["reason"], "reason_file": str(reason_file)}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"{NAME}: {type(e).__name__}: {' '.join(str(e).split())}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(out)
