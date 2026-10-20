"""変異の宣言の読み（docs/design/gate-efficacy.md の 1.5）: 対象の根の宣言 .review-checks.json の任意の mutation の段
{argv, arms}（変異の実行器の呼び方の頭と、腕の一覧のパス）。指示の文は md が持ち、ここは run ごとの値と有無だけを返す。
元 lib/judge_accept.py の mutation_decl の分かれ方（段が在る・無い・無くて読みの誤りが在る）"""
import json

import materialkit  # noqa: F401  （lib/。import すると lib/graphloops/ が sys.path に入る）
from engine import declared  # lib/graphloops/

DECL_NAME = declared.DECL_NAME


def state(repo) -> dict:
    """{declared, argv, arms, error}。段が在れば declared 真と値（argv は JSON の配列の字）、無ければ declared 偽と、宣言の読みの誤り"""
    d = declared.read(repo)
    m = (d or {}).get("mutation")
    if m:
        return {"declared": True, "argv": json.dumps(m["argv"], ensure_ascii=False), "arms": str(m["arms"]), "error": ""}
    return {"declared": False, "argv": "", "arms": "",
            "error": (d or {}).get("mutation_error") or (d or {}).get("error") or ""}
