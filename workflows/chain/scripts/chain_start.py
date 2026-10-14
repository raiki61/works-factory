# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""周の鎖の始めのノード chain-start。

入力の周の数 rounds と費用の上限 budget_usd を lib/chain.limits で確かめ、範囲の外なら act: refused で返して AI の前で止める。
設計だけの run（design_only）は差分を作らず次の周の基が無いので、design_only を名指した鎖も同じく拒む。固定材料（fix_fixture）は
1 つの run の修正の前の写しで、2 周目からの依頼と木はそれと違うので、fix_fixture を名指した鎖も同じく拒む。
受けた時は 0 周目の決めと同じ形（act: launch・1 周目の子の入力 request・base・pr・spec・前までの周の行 rows: []）を返すので、
5 組の周のノードは番号と前の決めのほかは同じ形になる。後ろの決めが読む rounds・budget と、2 周目から運ぶ 1 周目の依頼の絶対パス
first_request・1 周目に名指した PR の番号 first_pr（メイングラフの入口と同じ entryshape.named_pr の読み。無ければ 0）と、
最後の差分の元の基 origin（run の作業ツリーの今の HEAD。1 周目の子の始めの記録の base_rev と同じ版。commit の無い木なら空）も返す。
出力ノード result が結ぶので落ちない: 境の口を読めない時も標準ライブラリだけで act: refused を返す。

入力: rounds・budget_usd・request・base・pr・spec・design_only・fix_fixture（鎖の入力）
"""
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    unread = None
except Exception as error:   # 出力ノードが結ぶので落ちない（上の docstring）
    boundary, unread = None, error

if boundary is not None:
    with boundary.guarded_imports():
        import chain
        import entryshape


DESIGN_ONLY_REFUSED = "周の鎖は design_only と組めない（設計だけの run は差分を作らず、次の周の基が無い）"
FIX_FIXTURE_REFUSED = ("周の鎖は fix_fixture と組めない（固定材料は 1 つの run の修正の前の写しで、2 周目からの依頼と木はそれと違う。"
                       "固定材料はメイングラフの run 1 つに名指す）")


def refused(reason: str) -> dict:
    return {"ok": False, "reason": reason, "act": "refused", "word": "", "text": reason, "request": "", "base": "", "pr": "",
            "spec": "", "rows": [], "rounds": 0, "budget": None, "first_request": "", "first_pr": 0, "origin": ""}


def head() -> str:
    done = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], capture_output=True, text=True, encoding="utf-8")
    return done.stdout.strip() if done.returncode == 0 else ""


def start() -> dict:
    if boundary.text(os.environ.get("INPUTS_DESIGN_ONLY")):
        return refused(DESIGN_ONLY_REFUSED)
    if boundary.text(os.environ.get("INPUTS_FIX_FIXTURE")):
        return refused(FIX_FIXTURE_REFUSED)
    request = boundary.text(os.environ.get("INPUTS_REQUEST"))
    pr = boundary.text(os.environ.get("INPUTS_PR"))
    try:
        rounds, budget = chain.limits(boundary.text(os.environ.get("INPUTS_ROUNDS")),
                                      boundary.text(os.environ.get("INPUTS_BUDGET_USD")))
    except ValueError as error:
        return refused(str(error))
    first = str(boundary.work_tree() / request) if request and not Path(request).is_absolute() else request
    return {"ok": True, "reason": "", "act": "launch", "word": "", "text": "1 周目を起こす", "request": request,
            "base": boundary.text(os.environ.get("INPUTS_BASE")), "pr": pr, "spec": boundary.text(os.environ.get("INPUTS_SPEC")),
            "rows": [], "rounds": rounds, "budget": budget, "first_request": first,
            "first_pr": entryshape.named_pr({"pr": pr}) or 0, "origin": head()}


def main() -> None:
    if boundary is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(refused(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        boundary.run(start, refused)


if __name__ == "__main__":
    main()
