# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""周の止めの決めのノード round-k-decide。ファイルを読まず、with: の値だけで決める（筋書きで本当に走らせて止めの語を照らす）。

前までの周の行 rows に、この周の行（結末の語と、report.OUTCOME_KINDS が引いた種・周の事実・commit の結果）を足し、lib/chain.step
で次の一手を決める。返す物は 0 周目の決め（chain-start）と同じ形で、次の周の子の入力 request・base・pr・spec を持つ。2 周目からの
子には request だけを運ぶ次の依頼に替え、base・pr・spec は空にする（1 周目に名指した PR は次の依頼の pr の欄で運ぶ）。request は
次を起こす時だけ埋める。周の commit か周の事実が読めなかった周は halted で止める。
周の行には、最後の差分のノードが採る周の答えとして読む子の出力の placed（子が差分を置いたか。apply.ok が真か）・r2_status・
spec_questions（承認し直すかの問いの数。整数でなければ 0）も載せる。
出力ノード result が結ぶので落ちない: ports か lib を読めない時も、標準ライブラリだけで halted を返す。

入力（with:）: rows（前の決めの出力の欄）・outcome・apply・r2_status・spec_questions（子の run の出力の欄）・facts（round-k-facts の出力）・commit（round-k-commit の
出力）・rounds_max・budget（chain-start の出力の欄）
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
    import chain
    import report
    unread = None
except Exception as error:   # 出力ノード result が結ぶので落ちない（上の docstring）
    ports, unread = None, error



def as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def decide() -> dict:
    rows = reads.items(os.environ.get("INPUTS_ROWS"))
    outcome = reads.text(os.environ.get("INPUTS_OUTCOME"))
    facts = as_dict(reads.value(os.environ.get("INPUTS_FACTS")))
    commit = as_dict(reads.value(os.environ.get("INPUTS_COMMIT")))
    budget = reads.value(os.environ.get("INPUTS_BUDGET"))
    placed = as_dict(reads.value(os.environ.get("INPUTS_APPLY"))).get("ok") is True
    held = facts.get("held_rows") or []
    spec = reads.value(os.environ.get("INPUTS_SPEC_QUESTIONS"))
    row = {"n": len(rows) + 1, "run": facts.get("run") or "", "outcome": outcome, "kind": report.OUTCOME_KINDS.get(outcome),
           "keys": facts.get("keys") or [], "held": len(held), "same_tree": commit.get("changed") is False,
           "cost": facts.get("cost"), "cost_read": facts.get("cost_read") is True, "minutes": facts.get("minutes"),
           "head": commit.get("head") or "", "placed": placed, "r2_status": reads.value(os.environ.get("INPUTS_R2_STATUS")),
           "spec_questions": spec if isinstance(spec, int) and not isinstance(spec, bool) else 0,
           "request": facts.get("request") or "", "source": facts.get("source") or ""}
    error = (commit.get("reason") or "周の結果を commit できなかった") if commit.get("ok") is not True else facts.get("error") or ""
    doc = {"rounds_max": reads.value(os.environ.get("INPUTS_ROUNDS_MAX")), "budget_usd": budget, "rounds": [*rows, row]}
    got = chain.step(doc, {**row, "held_rows": held, "error": error})
    row.update(got)
    return {**got, "request": row["request"] if got["act"] == "launch" else "", "base": "", "pr": "", "spec": "",
            "rows": doc["rounds"]}


def halted(reason: str) -> dict:
    return {"act": "stop", "word": "halted", "text": f"周の決めを組めなかった（{reason}）", "request": "", "base": "", "pr": "",
            "spec": "", "rows": []}


def main() -> None:
    if ports is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(halted(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        ports.run(decide, halted)


if __name__ == "__main__":
    main()
