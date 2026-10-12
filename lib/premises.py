"""前提の実測（graphloops の節 p0.premises）の部品。判定のブロックの受け付け（lib/judge_accept の check_premises）が読む。実行基盤を知らない関数だけを出す。

- PREMISES_FILE: 受け付けた実測役の返答 {"constraints": [...]} のファイルの名
- PREMISES_REQUEST_FILE: 型を確かめた依頼の行の控えの名
- claims(items): 依頼の行のうち measured（依頼者が測ったと書いた値）を持つ物の {where, measured}

受け付け（作業ツリー → 依頼の実測の測り直し → 写した rules の measured_needs_output）は lib/judge_accept.check_premises に在る。
"""
import pathlib
import sys

sys.dont_write_bytecode = True   # 下で import する写しの engine の分（accept.py と同じ。この物自身の分は呼び手が止める）

CORE = pathlib.Path(__file__).resolve().parent
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

PREMISES_FILE = "premises.json"                     # 受け付けた実測役の返答 {"constraints": [...]}

PREMISES_REQUEST_FILE = "premises-request.json"     # intake が型を確かめた依頼の行（JSON の配列）


def claims(items: list) -> list:
    """依頼の行のうち measured（依頼者が測ったと書いた値）を持つ物の {where, measured}。実測役はこの where を text にそのまま入れて
    測り直す（blk-premises の check_claims が確かめる）"""
    return [{"where": it["where"], "measured": it["measured"]} for it in items or []
            if isinstance(it, dict) and isinstance(it.get("where"), str) and it.get("measured") not in (None, "")]

