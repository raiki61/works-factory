# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""周の事実のノード round-k-facts。決めのノードがファイルを読まずに決められるよう、周の読み書きをここに寄せる。

1. 子の run の出力 next_request（子の置き場の次の依頼の下書きのポインタ）を埋め P6（child_pointer）で読む。null なら次の依頼は無い
   （閉じた周では普通）
2. 運ぶ次の依頼（lib/chain.next_request。1 周目の依頼と、1 周目に名指した PR を chain.first_of で足す）に所見が在れば、親の置き場の
   chain/<子のノードの id>/ に書き、その絶対パスを request に返す（次の周の子の入力 request になる）
3. 残りの行の鍵 keys・運ばなかった下書きの行 held_rows・読んだ子のファイル source（人が下書きを見直す先）を返す
4. 周の費用を親の run の記録の子のノードの行から読む。読めなければ cost_read: false（0 と読まない）
読めなかった物は error に訳を書き、決めが halted で止める。

入力（with:）: next_request（子の出力の欄）・child（費用を引く子のノードの id）・first_request・first_pr（chain-start の出力の欄）
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
import child_pointer  # noqa: E402

with boundary.guarded_imports():
    import carry
    import chain
    import runreport


def cost_of(child: str) -> tuple:
    """子のノードの費用 (USD か None, 読めたか)。記録が無い・費用の欄の無い行が在る時は読めない"""
    rows, _ = boundary.transcript()
    facts = runreport.transcript_facts(rows)
    cost = facts["cost"].get(child)
    return cost, cost is not None and child not in facts["uncosted"]


def first_doc(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def facts() -> dict:
    child = boundary.text(os.environ.get("INPUTS_CHILD"))
    cost, cost_read = cost_of(child)
    out = {"ok": True, "error": "", "run": "", "keys": [], "held_rows": [], "request": "", "source": "", "cost": cost,
           "cost_read": cost_read}
    ptr = boundary.parsed(os.environ.get("INPUTS_NEXT_REQUEST"))
    if ptr is None:
        return out
    try:
        source = child_pointer.resolve(ptr)
        nxt = json.loads(source.read_text(encoding="utf-8"))
        first = chain.first_of(first_doc(boundary.text(os.environ.get("INPUTS_FIRST_REQUEST"))),
                               boundary.value(os.environ.get("INPUTS_FIRST_PR")) or 0)
        carried = chain.next_request(nxt, first)
    except (OSError, ValueError) as error:
        return {**out, "error": f"子の次の依頼を読めない（{' '.join(f'{type(error).__name__}: {error}'.split())}）"}
    request = ""
    if carried[carry.FINDINGS]:
        place = Path(os.environ["ARTIFACTS_DIR"]) / "chain" / child
        place.mkdir(parents=True, exist_ok=True)
        carry.write(place / carry.NEXT_REQUEST_FILE, carried)
        request = str(place / carry.NEXT_REQUEST_FILE)
    return {**out, "run": ptr["run_id"], "keys": chain.keys_of(nxt), "held_rows": chain.held_rows(nxt), "request": request,
            "source": str(source)}


def fallback(reason: str) -> dict:
    return {"ok": False, "error": reason, "run": "", "keys": [], "held_rows": [], "request": "", "source": "", "cost": None,
            "cost_read": False}


if __name__ == "__main__":
    boundary.run(facts, fallback)
