# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""周の鎖の出力ノード result（鎖の returns: result・outcome_field: closed）。

最後に走った周の決めの act・word・text と、周ごとの行 rounds（周の番号・子の run・結末の語・種・残りの鍵・費用・運んだ次の依頼
request・決めの act・word・text）を返す。closed は止めの語が closed の時だけ真。request は最後の周が運んだ次の依頼の絶対パスで、
鎖の後に続ける人が依頼に使う。
最後の差分のノード final-diff の返りから、bin/apply が読む欄（メイングラフの出力と同じ名と形）を載せる: apply・sealed（元の基から
採る周までの封じた差分。無ければ null）・outcome・r2_status（最後の差分に入る周のどれかで R2 が作り直しと言えばそれ、ほかは
採る周の物）・spec_questions（最後の差分に入る周の承認し直すかの問いの数の和。メイングラフと同じく常に整数）。report は周ごとの
表 chain.md のポインタ。
final-diff が落ちた・飛ばされた時は、どれも null（outcome は空・spec_questions は 0）。stop_reason は最後の差分を置いていない訳（final-diff の
reason か apply の reason。落ちた・飛ばされた時はそう書く）で、bin/apply が拒む時に名指す。
deliver は出口の語 pr の時だけ、PR を作った（act: pr と pr の在りか）か、作らずに止めた訳（act: stopped）か、作ったと確かめられ
なかった訳（act: unconfirmed）。渡しのブロック hand の返りの欄 deliver をそのまま載せ、hand の返りが無い時は訳を組む: 最後の差分を
置いていなければ stopped（訳は final-diff の reason か stop_reason）、置いたのに返りが無ければ（hand の中で push や PR の作成が済んだかもしれない）unconfirmed。出口の語が空なら null。
最後の決めが launch なのに次の決めが無い時は、次の周の子の run が落ちた（親の周のノードが落ち、後ろが飛んだ）ので act: wait と
続け方を返す。
lib を読まない。落ちない: ports を読めない時も、標準ライブラリだけで返す。

入力（with:）: start（chain-start の出力）・final（final-diff の出力）・hand（渡しのブロックの返りの欄 deliver。`{from, if_skipped: null}`）・d1〜d<周の数の上限>（round-k-decide の出力。番号の順に読む。どれも `{from, if_skipped: null}`）
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
try:
    import ports
    from src import reads
    unread = None
except Exception as error:   # 出力ノードは落ちない（上の docstring）
    ports, unread = None, error

CLOSED = "closed"
PR = "pr"   # 出口の語（lib/entry.py の DELIVER_PR。result は lib を読まないので字で持ち、試験が同じことを縛る）
FINAL = ("apply", "sealed", "report", "r2_status")


def from_final(final) -> dict:
    got = final if isinstance(final, dict) else {}
    if not got:
        why = "final-diff の出力が無い（落ちたか飛ばされた）"
    elif not isinstance(got.get("sealed"), dict):
        why = got.get("reason") or ""
    else:
        why = (got.get("apply") or {}).get("reason") or ""
    spec = got.get("spec_questions")
    return {"outcome": got.get("outcome") or "", "stop_reason": why, "spec_questions": spec if isinstance(spec, int) else 0,
            **{key: got.get(key) for key in FINAL}}


def delivered(start: dict, final, hand):
    if start.get("deliver") != PR:
        return None
    if isinstance(hand, dict):
        return hand
    got = final if isinstance(final, dict) else {}
    if got.get("placed") is not True:
        why = got.get("reason") or from_final(final)["stop_reason"] or "訳の記録が無い"
        return {"act": "stopped", "pr": None, "reason": f"最後の差分を置いていない（{why}）"}
    return {"act": "unconfirmed", "pr": None,
            "reason": "PR を作る渡しのサブグラフ hand の出力が無い（落ちたか飛ばされた。push と PR の作成が済んだかは run の記録で確かめる）"}


def result(start, final, decisions: list, hand=None) -> dict:
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
            "deliver": delivered(start, final, hand)}


def fallback(reason: str) -> dict:
    return {"closed": False, "ok": False, "reason": reason, "act": "refused", "word": "", "text": reason, "request": "",
            "rounds": [], **from_final(None), "deliver": None}


def main() -> None:
    if ports is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(fallback(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        ports.run(lambda: result(reads.value(os.environ.get("INPUTS_START")), reads.value(os.environ.get("INPUTS_FINAL")),
                                    reads.decisions(), reads.value(os.environ.get("INPUTS_HAND"))), fallback)


if __name__ == "__main__":
    main()
