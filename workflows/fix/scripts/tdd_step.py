# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 tdd-step（形 group の tdd-loop の中。役 tdd の後）: 役の返答を機械が確かめて段を進める（tddloop.step）。

段は route → 単位ごとに test（赤）→ fix（緑）→（申告の在る単位だけ）refactor。赤・緑は実行器の JUnit XML で機械が決める
（役の申告では決まらない）。段ごとに 3 回目の拒否で諦め、その単位を単位の頭の木に戻し、機械の申し出を積んで次の単位へ。
食い違いの申し出（phase conflict）は、名指しが現物に在れば単位を止める（query の申し出は判定者の問いを当てる。querytest.judge_hits）。
止めた申し出は状態の未送の並びから置き場の conflicts.json に積む（tddloop.flush_unsent → conflict.park_claims。前の周が積めなかった
物も積み直す）。並べの周（tddlanes）は使わない（組の並べは子の run の fan_out が持つ）。
入力 reply は役 tdd の返答（役が飛ばされた周は null か空）。拒んだ理由は置き場の tdd-step-reject-<n>.md にも書き、パスを返す
（次の指示書にも tddloop.prep が載せる）。
返り {ok, done, reason, reason_file, phase}（done は輪が済んだ時）。輪の状態が読めない・済んだ輪に返答が来た・git が効かない:
標準エラーに 1 行で 1。
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

import conflict  # noqa: E402
import fixboard  # noqa: E402
import querytest  # noqa: E402
import tddloop  # noqa: E402

REJECT = "tdd-step-reject-{}.md"


def read_reply():
    raw = os.environ["INPUTS_REPLY"]
    if not raw.strip() or raw.strip() == "null":
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return raw   # 読めない返答は step が拒む（出し直しの回数に数える）


def main() -> dict:
    reply = read_reply()
    place = fixio.place()
    repo = fixio.repo()
    started = fixboard.read_json(place / fixboard.TDD_START_FILE)
    if not isinstance(started, dict):
        raise ValueError(f"置き場に {fixboard.TDD_START_FILE} が無い（group-start が走らなかった。{place}）")
    if not started.get("go"):
        return {"ok": True, "done": True, "reason": "", "reason_file": "", "phase": "done"}
    state = started["state_file"]
    judgment = fixboard.read_json(place / fixboard.JUDGMENT_FILE) or {}
    hits = querytest.judge_hits(judgment.get("units") or [] if isinstance(judgment, dict) else [])
    fixio.drop_runner_env()   # 対象のテストに Archon の変数を継がせない（place・repo は先に取った）
    out = tddloop.step(state, reply, repo, try_query=hits)
    tddloop.flush_unsent(state, lambda rows: conflict.park_claims(place, rows))
    reason_file = ""
    if out["reason"]:
        n = len(tddloop.load_state(state).get("calls") or [])
        reason_file = str(fixboard.write_text(place / REJECT.format(n), out["reason"] + "\n"))
    return {"ok": bool(out["ok"]), "done": bool(out["done"]), "reason": out["reason"], "reason_file": reason_file,
            "phase": out["phase"]}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:
        print(f"tdd-step: {type(e).__name__}: {' '.join(str(e).split())}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(result)
