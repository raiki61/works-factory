# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node fix-ruled-accept（全体の形の裁定の後の修正の輪の終わり）: 外の輪の頭 ruled-writer-pick が選んだ型の書き手の
返答を受け付ける（src/board.accept_reply の ruled）。直す義務は board.ruled_owed のうちその型の注文の単位（src/writers.owed）、頭の木は
fix-ruled-head.json（型を選ぶたびに控え直す）、輪の状態は board.ruled_states。拒否の控えと回の数えは型ごと。単位の結末と受けた返答は前の型の物に
単位で重ねる。輪を抜ける時に型を済ませた印を積む。
返り {ok, done, reason, reason_file}"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import oneline  # noqa: E402
import writelog  # noqa: E402

from src import board, runvals, writers  # noqa: E402

NODE = "fix-ruled-accept"
NOT_LAUNCHED = "裁定の後の修正役を起こさなかった（直す裁定が無い）"
SKIP = (ports.RUNTIME_COPY_PREFIX,)
GOT = ("ok", "reason", "reply", "report")   # 型の block の返りまるごとから拾う欄（reason は ok が偽の訳、reply は返答の pointer、report は報告に載せる行）


def written() -> tuple:
    """起きた型の書き手の (返答, 報告の行)。型の block の返りはまるごとを ports.picked で拾い、variant の node の返りは字で
    読む（writers.reply_of）"""
    blocks = {
        "pin": ports.picked(os.environ.get("INPUTS_REPLY_PIN"), GOT),
        "tidy": ports.picked(os.environ.get("INPUTS_REPLY_TIDY"), GOT),
        "static": ports.picked(os.environ.get("INPUTS_REPLY_STATIC"), GOT),
        "remove": ports.picked(os.environ.get("INPUTS_REPLY_REMOVE"), GOT),
    }
    return writers.reply_of(blocks, os.environ.get("INPUTS_REPLY_VARIANT"), "ruled",
                            lambda v: ports.polyfill("skip_value").value(v) is None)


def main() -> dict:
    reply, lines = written()
    place, repo = ports.place(), Path.cwd()
    weapon = writers.current(place)
    board.add_writer_report(place, weapon, lines)   # 範囲の相談の周も、起きた書き手の報告の行は残す
    consulted = os.environ.get("INPUTS_CONSULTED", "").strip().lower() == "true"
    if consulted:
        return {"ok": False, "done": False, "reason": board.CONSULTED, "reason_file": ""}
    if reply is None:
        writers.finished(place, weapon)
        return {"ok": True, "done": True, "reason": NOT_LAUNCHED, "reason_file": ""}
    name = writers.accept_name("ruled", weapon)
    iteration, stopped = board.round_number(place, name)
    if stopped:
        writers.finished(place, weapon)
        return stopped
    owed = writers.owed(place, board.ruled_owed(place))
    values = runvals.read(place)
    judgment = board.read_json(place / board.JUDGMENT_FILE) or {}
    head = board.fixer_head(place, "ruled")
    state, tests_state = board.ruled_states(place)
    log = writelog.log_here()
    ports.drop_runner_env(values["user_env_dir"])   # 対象のテストを走らせる前に Archon の変数を落とす（place は先に取った）
    got = board.accept_reply(reply, place, repo, pass_="ruled", iteration=iteration, owed=owed,
                             judged=judgment.get("units"), suite=str(values["tdd_suite"] or ""), state=state,
                             tests_state=tests_state, head=head, skip=SKIP, log=log)
    out = _finish(place, got, iteration, name)
    if out["done"]:
        writers.finished(place, weapon)
    return out


def _finish(place, got: dict, iteration: int, name: str) -> dict:
    board.merge_units(place, board.FIX_UNITS_FILE, got["units"])
    if got.get("stop"):   # 実行器が結末を返さない・試験を拾わない（board.no_suite_at_accept）: 出し直させずに輪を抜ける
        board.trace(place, "fix_ruled_stopped", node=name, iteration=iteration, reason=got["reason"])
        return {"ok": False, "done": True, "reason": got["reason"], "reason_file": ""}
    if got["ok"]:
        path = place / board.RULED_REPLY_FILE
        board.write_json(path, board.merge_reply(board.read_json(path), got["reply"]))
        board.trace(place, "fix_ruled_accepted", node=name, iteration=iteration, parked=sorted(got["parked"]))
        return {"ok": True, "done": True, "reason": "", "reason_file": ""}
    out = board.accept_out(place, name, got)
    board.trace(place, "fix_ruled_rejected", node=name, iteration=iteration, done=out["done"], parked=sorted(got["parked"]))
    return {**out, "reason": got["reason"]}


if __name__ == "__main__":
    try:
        out = main()
    except Exception as e:
        print(f"{NODE}: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    ports.returns(out)
