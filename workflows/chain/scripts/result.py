# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""周の鎖の出力ノード result（鎖の returns: result・outcome_field: closed）。

最後に走った周の決めの act・word・text と、周ごとの行 rounds（周の番号・子の run・結末の語・種・残りの鍵・費用・運んだ次の依頼
request・決めの act・word・text）を返す。closed は止めの語が closed の時だけ真。request は最後の周が運んだ次の依頼の絶対パスで、
鎖の後に続ける人が依頼に使う。
出口のノード deliver（入力 deliver が pr の時だけ走る）の返りの欄 delivered {ok, branch, commit, url, reason}（run 専用の枝と PR を読み戻した
結果、または作らなかった訳）をそのまま返す（置いてよいかは merge の中が照らす。ここは受け入れの決めを持たない）。ノード deliver が飛んだ
（deliver が空）・鎖を受けなかった時は null。
最後の差分のノード final-diff の返りから、bin/apply が読む欄（メイングラフの出力と同じ名と形）を載せる: apply・sealed（元の基から
採る周までの封じた差分。無ければ null）・outcome・r2_status（最後の差分に入る周のどれかで R2 が作り直しと言えばそれ、ほかは
採る周の物）。report は周ごとの表 chain.md のポインタ。
final-diff が落ちた・飛ばされた時は、どれも null（outcome は空）。stop_reason は最後の差分を置いていない訳（final-diff の
reason か apply の reason。落ちた・飛ばされた時はそう書く）で、bin/apply が拒む時に名指す。
最後の決めが launch なのに次の決めが無い時は、次の周の子の run が落ちた（親の周のノードが落ち、後ろが飛んだ）ので act: wait と
続け方を返す。
lib を読まない。落ちない: 境の口を読めない時も、標準ライブラリだけで返す。

入力（with:）: start（chain-start の出力）・final（final-diff の出力）・delivered（ノード deliver の出力の欄 delivered）・d1〜d<周の数の上限>（round-k-decide の出力。番号の順に読む。どれも `{from, if_skipped: null}`）
"""
import json
import os
import re
import sys
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    unread = None
except Exception as error:   # 出力ノードは落ちない（上の docstring）
    boundary, unread = None, error

CLOSED = "closed"
FINAL = ("apply", "sealed", "report", "r2_status")
DECISION = re.compile(r"INPUTS_D[1-9][0-9]*")   # 周 k の決めの入力 d<k>。周の数はグラフの with: が持つ。final_diff.py も同じ読み（試験が縛る）


def from_final(final) -> dict:
    got = final if isinstance(final, dict) else {}
    if not got:
        why = "final-diff の出力が無い（落ちたか飛ばされた）"
    elif not isinstance(got.get("sealed"), dict):
        why = got.get("reason") or ""
    else:
        why = (got.get("apply") or {}).get("reason") or ""
    return {"outcome": got.get("outcome") or "", "stop_reason": why, **{key: got.get(key) for key in FINAL}}


def result(start, final, decisions: list, delivered=None) -> dict:
    if not isinstance(start, dict) or start.get("ok") is not True:
        reason = start.get("reason") if isinstance(start, dict) else "chain-start の出力が無い"
        return fallback(reason or "chain-start が鎖を受けなかった")
    made = [d for d in decisions if isinstance(d, dict)]
    rows = max((d.get("rows") or [] for d in made), key=len, default=[])
    last = made[-1] if made else start
    act, word, text = last.get("act") or "", last.get("word") or "", last.get("text") or ""
    if act == "launch":
        act, word = "wait", ""
        text = (f"{len(made) + 1} 周目の子の run か、その周のノードが落ちた。親の run を resume すると Archon が落ちた子を 1 度"
                "起こし直す")
    return {"closed": word == CLOSED, "ok": True, "reason": "", "act": act, "word": word, "text": text,
            "request": rows[-1].get("request") or "" if rows else "", "rounds": rows, **from_final(final),
            "delivered": delivered if isinstance(delivered, dict) else None}


def fallback(reason: str) -> dict:
    return {"closed": False, "ok": False, "reason": reason, "act": "refused", "word": "", "text": reason, "request": "",
            "rounds": [], **from_final(None), "delivered": None}


def main() -> None:
    if boundary is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(fallback(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        names = sorted(filter(DECISION.fullmatch, os.environ), key=lambda name: int(name[len("INPUTS_D"):]))
        decisions = [os.environ[name] for name in names]
        boundary.run(lambda: result(boundary.value(os.environ.get("INPUTS_START")), boundary.value(os.environ.get("INPUTS_FINAL")),
                                    [boundary.value(d) for d in decisions], boundary.value(os.environ.get("INPUTS_DELIVERED"))), fallback)


if __name__ == "__main__":
    main()
