"""人が決めた前提の材料（承認ノードの答え・依頼が名指した設計書の節・対象のリポジトリの地図）を、見出しと頼みの文を除いた形で返す
（docs/design/independent-design.md の 2.3 の 3）。見出しと頼みの文は共通の断片 prompts/design-premises.md が持つ。

lib/design.py の human_answers・named_sections・repo_map を呼び、返りの本文から頭（見出しと頼みの文の 2 段落）を外す。lib の頭の字は読まず、
頭の形（# が 3 つの見出し）だけで見分ける。頭が無い本文はそのまま使う。控え {given, withheld, seen} は、この module の material が組む。
"""
from __future__ import annotations

import re

import design    # lib/
from rolekit import BoardGap   # lib/

LIB_HEAD = re.compile(r"### [^#\n]")   # lib の節の見出し（3 つの # と空白。本文の見出しは # が 4 つ以上なのでこれに当たらない）


def _body(text: str, what: str) -> str:
    """lib が組んだ節の本文 text から頭（見出しと頼みの文の 2 段落）を外した材料。見出しと頼みの文は共通の断片 prompts/design-premises.md が
    持つので、lib の字は読まない（頭の形だけで見分ける）。頭が無い本文（頭を md へ出した後の lib）はそのまま。空の節は空"""
    if not text:
        return ""
    if not LIB_HEAD.match(text):
        return text
    parts = text.split("\n\n", 2)
    if len(parts) < 3:
        raise ValueError(f"{what} の本文に見出しと頼みの文の後ろの材料が無い")
    return parts[2]


def material(view, repo) -> dict:
    """{answers, named, map, ledger}。answers・named・map は材料の字（答えの行・節の本文・地図の本文。無ければ空）。
    ledger は {given, withheld, seen}（貼った入力の控え。kind は design.PREMISE_KINDS の中だけ）"""
    human, rows, machine, seen = design.human_answers(view)
    named, named_given, named_withheld = design.named_sections(view, repo)
    mapped, map_given, map_withheld = design.repo_map(repo)
    given = [{"kind": "human_answer", "what": r} for r in rows] + named_given + map_given
    outside = sorted({g["kind"] for g in given} - set(design.PREMISE_KINDS))
    if outside:   # 一覧の外の源（ほかの block の出力など）から貼る口を作らない
        raise BoardGap(f"独立設計に渡す入力の種類が許す一覧（{' / '.join(design.PREMISE_KINDS)}）の外: {', '.join(outside)}")
    withheld = ([{"kind": "human_item", "what": m, "why": "answer の無い行（機械が積んだ。人の答えでない）"} for m in machine]
                + named_withheld + map_withheld)
    return {"answers": _body(human, "承認ノードの答え"),
            "named": _body(named, "名指しの節"),
            "map": _body(mapped, "地図"),
            "ledger": {"given": given, "withheld": withheld, "seen": seen}}
