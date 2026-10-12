# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""2 回目の手直しの役の返答の受け付け（節 refix2-accept）。

支度が go: false で役を起こさなかった（with: reply が null）時は、受ける物が無いので done: true。返答が在れば、義務の key に
1 度ずつ答えたかを照らし（fixboard.delta_fix_problems）、run の始めの木からの変更のうち修正の段が触ったファイルの外を承認済みの
修正案の項目の範囲で照らして外れを拒み（planrange.check_paths）、書き込みの出どころ（段の頭の木からの変更が全部 handled[].files か bash_writes に在るか。未決 U6。と writes の記録）を照らして
受ける（refix.accept_fix。除くパスの頭 fixio.SKIP）。拒否は理由のファイルを置いて done: false、3 回目の拒否で done: true（諦め）。
返り {ok, done, reason, reason_file}。回す側の誤り（返答・回の番号が読めない・修正案の欄の控えが壊れた）は標準エラーに 1 行で非 0。
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
import fixboard  # noqa: E402
import refix  # noqa: E402
import rolekit  # noqa: E402

N = 2
NAME = "refix2-accept"
NOT_LAUNCHED = "手直しの役を起こさなかった（2 回目の審査が直す義務を出していない・審査を受けていない）"


def main() -> None:
    raw = os.environ["INPUTS_REPLY"]
    iteration = int(os.environ["INPUTS_ITERATION"])
    if raw.strip() in ("", "null"):
        boundary.returns({"ok": True, "done": True, "reason": NOT_LAUNCHED, "reason_file": ""})
        return
    reply, why = rolekit.parse_reply(raw)
    if reply is None:
        raise ValueError(why)
    place, repo = fixio.place(), fixio.repo()
    bad = fixboard.delta_fix_problems(place, N, reply) + fixboard.undeclared_refix(
        reply, repo, fixboard.stage_head(place, fixboard.REFIX_HEAD_FILE.format(N)), skip=fixio.SKIP)
    got = {"ok": False, "reason": "手直しの返答の照らしに通らない:\n" + "\n".join(f"  - {x}" for x in bad)} if bad else \
        refix.accept_fix(reply, place, fixboard.start_tree(place), repo, n=N,
                         items=functools.partial(fixboard.place_items, place), skip=fixio.SKIP, log=fixio.writes_log())
    out = fixboard.accept_out(place, NAME, got)
    fixboard.trace(place, "refix_accepted" if out["ok"] else "refix_rejected", node=NAME, iteration=iteration,
                   done=out["done"])
    boundary.returns(out)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(f"{NAME}: {type(e).__name__}: {' '.join(str(e).split())}")
