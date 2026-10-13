# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""周の鎖の出力ノード result（鎖の returns: result・outcome_field: closed）。

最後に走った周の決めの act・word・text と、周ごとの行 rounds（周の番号・子の run・結末の語・種・残りの鍵・費用・運んだ次の依頼
request・決めの act・word・text）を返す。closed は止めの語が closed の時だけ真。request は最後の周が運んだ次の依頼の絶対パスで、
鎖の後に続ける人が依頼に使う。各周の差分は、その周の頭（前の周の commit）からの物なので、周の順に当てる。
最後の決めが launch なのに次の決めが無い時は、次の周の子の run が落ちた（親の周のノードが落ち、後ろが飛んだ）ので act: wait と
続け方を返す。
lib を読まない。落ちない: 境の口を読めない時も、標準ライブラリだけで返す。

入力（with:）: start（chain-start の出力）・d1〜d5（round-k-decide の出力。どれも `{from, if_skipped: null}`）
"""
import json
import os
import sys
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    unread = None
except Exception as error:   # 出力ノードは落ちない（上の docstring）
    boundary, unread = None, error

CLOSED = "closed"


def result(start, decisions: list) -> dict:
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
            "request": rows[-1].get("request") or "" if rows else "", "rounds": rows}


def fallback(reason: str) -> dict:
    return {"closed": False, "ok": False, "reason": reason, "act": "refused", "word": "", "text": reason, "request": "",
            "rounds": []}


def main() -> None:
    if boundary is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(fallback(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        decisions = [os.environ.get(name) for name in ("INPUTS_D1", "INPUTS_D2", "INPUTS_D3", "INPUTS_D4", "INPUTS_D5")]
        boundary.run(lambda: result(boundary.value(os.environ.get("INPUTS_START")), [boundary.value(d) for d in decisions]),
                     fallback)


if __name__ == "__main__":
    main()
