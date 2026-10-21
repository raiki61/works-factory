# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""周の鎖の始めのノード chain-start。

入力の周の数 rounds と費用の上限 budget_usd を lib/chain.limits で確かめ、範囲の外なら act: refused で返して AI の前で止める。
設計だけの run（design_only）は差分を作らず次の周の基が無いので、design_only を名指した鎖も同じく拒む。固定材料（fix_fixture）は
1 つの run の修正の前の写しで、2 周目からの依頼と木はそれと違うので、fix_fixture を名指した鎖も同じく拒む。仕様駆動の道の表（spec_table）も
1 つの run の入口で、2 周目からの依頼（前の周の残り）とは組めないので、名指した鎖を拒む（docs/design/spec-driven.md の 6.2）。
受けた時は 0 周目の決めと同じ形（act: launch・1 周目の子の入力 request・base・pr・spec・前までの周の行 rows: []）を返すので、
5 組の周のノードは番号と前の決めのほかは同じ形になる。後ろの決めが読む rounds・budget と、2 周目から運ぶ 1 周目の依頼の絶対パス
first_request・1 周目に名指した PR の番号 first_pr（メイングラフの入口と同じ entryshape.named_pr の読み。無ければ 0）と、
最後の差分の元の基 origin（run の作業ツリーの今の HEAD。1 周目の子の始めの記録の base_rev と同じ版。commit の無い木なら空）と、
確かめた出口の語 deliver（lib/entry.py の DELIVERS。知らない語は act: refused）も返す。
返りの user_env_dir は鎖の run の共有の置き場（ports.place()。refused の時は空）で、hand の commit の節が commit の hooks を
利用者の環境に戻して印を置く要件（workflows/AGENTS.md の E4: 一番上のグラフの始めのノードが作って入力で渡す）。印は鎖の報告に載せない
（殻の起動の 1 行が告げる。chain.md は hand より前に書かれる）。
出力ノード result が結ぶので落ちない: ports か lib を読めない時も標準ライブラリだけで act: refused を返す。

入力: rounds・budget_usd・request・base・pr・spec・design_only・fix_fixture・spec_table・deliver（鎖の入力）
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
    import entry
    import entryshape
    unread = None
except Exception as error:   # 出力ノードが結ぶので落ちない（上の docstring）
    ports, unread = None, error


DESIGN_ONLY_REFUSED = "周の鎖は design_only と組めない（設計だけの run は差分を作らず、次の周の基が無い）"
FIX_FIXTURE_REFUSED = ("周の鎖は fix_fixture と組めない（固定材料は 1 つの run の修正の前の写しで、2 周目からの依頼と木はそれと違う。"
                       "固定材料はメイングラフの run 1 つに名指す）")
SPEC_TABLE_REFUSED = ("周の鎖は spec_table と組めない（仕様駆動の道の表は 1 つの run の入口で、2 周目からの依頼は前の周の残り。"
                      "表はメイングラフの run 1 つに名指す）")


def refused(reason: str) -> dict:
    return {"ok": False, "reason": reason, "act": "refused", "word": "", "text": reason, "request": "", "base": "", "pr": "",
            "spec": "", "rows": [], "rounds": 0, "budget": None, "first_request": "", "first_pr": 0, "origin": "", "deliver": "",
            "user_env_dir": ""}


def start() -> dict:
    if reads.text(os.environ.get("INPUTS_DESIGN_ONLY")):
        return refused(DESIGN_ONLY_REFUSED)
    if reads.text(os.environ.get("INPUTS_FIX_FIXTURE")):
        return refused(FIX_FIXTURE_REFUSED)
    if reads.text(os.environ.get("INPUTS_SPEC_TABLE")):
        return refused(SPEC_TABLE_REFUSED)
    request = reads.text(os.environ.get("INPUTS_REQUEST"))
    pr = reads.text(os.environ.get("INPUTS_PR"))
    try:
        rounds, budget = chain.limits(reads.text(os.environ.get("INPUTS_ROUNDS")),
                                      reads.text(os.environ.get("INPUTS_BUDGET_USD")))
        deliver = entry.deliver_word(reads.text(os.environ.get("INPUTS_DELIVER")))
    except (ValueError, entry.InputRefused) as error:
        return refused(str(error))
    first = str(reads.work_tree() / request) if request and not Path(request).is_absolute() else request
    return {"ok": True, "reason": "", "act": "launch", "word": "", "text": "1 周目を起こす", "request": request,
            "base": reads.text(os.environ.get("INPUTS_BASE")), "pr": pr, "spec": reads.text(os.environ.get("INPUTS_SPEC")),
            "rows": [], "rounds": rounds, "budget": budget, "first_request": first,
            "first_pr": entryshape.named_pr({"pr": pr}) or 0, "origin": reads.head(), "deliver": deliver,
            "user_env_dir": str(ports.place())}


def main() -> None:
    if ports is None:
        reason = f"{type(unread).__name__}: {unread}"
        print(reason, file=sys.stderr)
        print(json.dumps(refused(reason), ensure_ascii=False, allow_nan=False), flush=True)
    else:
        ports.run(start, refused)


if __name__ == "__main__":
    main()
