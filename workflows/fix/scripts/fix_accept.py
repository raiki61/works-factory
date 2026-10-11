# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 fix-accept（形 group の修正の輪の終わり）: 修正役の返答を受け付ける（fixboard.accept_reply。照らしは factchecks・fixgates・
書き込みの出どころ（記録が無い run は段の頭の木からの変更が全部 changes[].files か bash_writes に在るか。未決 U6）・
recount.accept_fix・tddloop.selected_problems。除くパスの頭 fixio.SKIP）。

- 範囲の相談の周（入力 consulted が true）は受け付けを回さず done: false
- 修正役を起こさなかった（入力 reply が null）周は done: true（直す義務が残らない）
- 拒否は理由を置き場の reject-fix-accept-<iteration>.md に書いて done: false。iteration が 3 以上の拒否は、名指しの単位だけを
  段の頭の木に戻して諦め、ほかの単位を受けて done: true
- 範囲の外のはみ出しだけの返答は拒まずに範囲の相談に積むか機械が戻す（fixboard.settle_overflow）。積んだ回は done: false
- 1 回目で裁かれていない申し出が在れば輪を抜ける（done: true。裁定の後の修正役が受け付け直す）
置き場に残す物: fix-units.json（{unit_key: {status, reason}}）・fix-reply.json（受けた返答に 6 つの印と rejudge_requested を
前の控えと論理和で重ねた物）・allowed-tests.json（許したテストの変更のパス）。
返り {ok, done, reason, reason_file}。回す側の誤り（返答・回の番号が読めない・判定の写しが無い）は標準エラーに 1 行で非 0。
"""
import json
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

NAME = "fix-accept"
NOT_LAUNCHED = "修正役を起こさなかった（組の直す義務の単位が残らない）"


def main() -> dict:
    raw = os.environ["INPUTS_REPLY"]
    consulted = os.environ.get("INPUTS_CONSULTED", "").strip().lower() == "true"
    iteration = int(os.environ["INPUTS_ITERATION"])
    if consulted:
        return {"ok": False, "done": False, "reason": fixboard.CONSULTED, "reason_file": ""}
    place, repo = fixio.place(), fixio.repo()
    group = os.environ.get("INPUTS_GROUP", "").strip()
    owed = fixboard.group_owed(place, json.loads(group)["unit_ids"] if group else None)
    if raw.strip() in ("", "null"):
        _, excused = fixboard.fix_duty(place, owed)
        fixboard.write_json(place / fixboard.FIX_UNITS_FILE, fixboard.unit_outcomes(owed, {}, excused=excused))
        return {"ok": True, "done": True, "reason": NOT_LAUNCHED, "reason_file": ""}
    reply, why = rolekit.parse_reply(raw)
    if reply is None:
        raise ValueError(why)
    start = startrec.read(place)
    state, _ = fixboard.loop_files(place)
    judgment = fixboard.read_json(place / fixboard.JUDGMENT_FILE) or {}
    head = fixboard.stage_head(place, fixboard.FIX_HEAD_FILE)
    fixio.drop_runner_env()   # 対象のテストを走らせる前に Archon の変数を落とす（place は先に取った）
    got = fixboard.accept_reply(reply, place, repo, pass_="first", iteration=iteration, owed=owed,
                                judged=judgment.get("units"), suite=str(start.get("tdd_suite") or ""), state=state,
                                head=head, skip=fixio.SKIP)
    return finish(place, got, iteration)


def finish(place: Path, got: dict, iteration: int) -> dict:
    fixboard.write_json(place / fixboard.FIX_UNITS_FILE, got["units"])
    if got["ok"]:
        path = place / fixboard.FIX_REPLY_FILE
        fixboard.write_json(path, fixboard.reply_marks(got["reply"], fixboard.read_json(path)))
        fixboard.write_json(place / fixboard.ALLOWED_TESTS_FILE, fixboard.granted_tests(place))
        fixboard.trace(place, "fix_accepted", node=NAME, iteration=iteration, parked=sorted(got["parked"]),
                       conflicted=got["conflicted"])
        return {"ok": True, "done": True, "reason": fixboard.PARKED_FOR_RULING if got["conflicted"] else "",
                "reason_file": ""}
    reason_file = fixboard.write_text(place / fixboard.REJECT_NAME.format(name=NAME, k=iteration), got["reason"] + "\n")
    done = fixboard.loop_done(got, iteration)
    fixboard.trace(place, "fix_rejected", node=NAME, iteration=iteration, done=done, parked=sorted(got["parked"]))
    return {"ok": False, "done": done, "reason": got["reason"], "reason_file": str(reason_file)}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"{NAME}: {type(e).__name__}: {' '.join(str(e).split())}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(out)
