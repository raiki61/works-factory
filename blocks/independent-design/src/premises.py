"""人が決めた前提の材料（承認ノードの答え・依頼が名指した設計書の節・対象のリポジトリの地図）を、見出しと頼みの文を除いた形で返す
（docs/design/independent-design.md の 2.3 の 3）。見出しと頼みの文は共通の断片 prompts/design-premises.md が持つ。

lib/design.py の human_answers・named_sections・repo_map を呼び、返りの本文から頭の字を removeprefix で外す。頭の字が本文の頭に無ければ
ValueError（lib の字が変わった時に、黙って見出しを二重に貼らない）。控え {given, withheld, seen} は design.premises と同じ組み方。
"""
from __future__ import annotations

import design    # lib/
from rolekit import BoardGap   # lib/


def _body(text: str, head: str, ask: str, what: str) -> str:
    """lib が組んだ節の本文 text から頭の字（見出し + 頼みの文）を外した材料。空の節は空"""
    if not text:
        return ""
    prefix = f"{head}\n\n{ask}\n\n"
    if not text.startswith(prefix):
        raise ValueError(f"{what} の本文の頭が lib/design.py の見出しと頼みの文と違う——共通の断片と lib の字を合わせ直す")
    return text.removeprefix(prefix)


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
    return {"answers": _body(human, design.HUMAN_HEAD, design.HUMAN_ASK, "承認ノードの答え"),
            "named": _body(named, design.NAMED_HEAD, design.NAMED_ASK, "名指しの節"),
            "map": _body(mapped, design.MAP_HEAD, design.MAP_ASK, "地図"),
            "ledger": {"given": given, "withheld": withheld, "seen": seen}}
