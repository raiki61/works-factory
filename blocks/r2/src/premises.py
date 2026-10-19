"""設計の後の前提の材料と控え（docs/design/r2.md の 1.5）。比べの役の頭に貼る。

前半 material は independent-design の block の src/premises.py の material を字のまま写した物（2 つの block が同じ物を持つ。組み込みで
lib の 1 モジュールに寄せる。r2.md の 9 節の 3）。人が決めた前提（承認ノードの答え・依頼が名指した設計書の節・対象の地図）を、見出しと
頼みの文を除いた形で返す。見出しと頼みの文は共通の断片 design-premises が持つ。後半は lib/eyeverdict.py の premise_section の、
独立設計の後に来た答え・前提のずれ・記録の制約・控えの組み方を、値で受ける形に写した物。
"""
from __future__ import annotations

import re
import types

import design    # lib/
import eyekit    # lib/
from rolekit import BoardGap   # lib/

NO_REQUEST = "依頼のファイルが渡っていない"
NO_MARKS = "（修正の印が渡っていない）"
NO_NOTE = "（申告の文なし）"
NONE = "（無い）"
KINDS = (*design.PREMISE_KINDS, "drift", "constraint")   # 控えの given の kind の許す一覧（貼る入力の種類 + 後半が足す 2 つ）


# ---------------------------------------------------------------- 依頼の名指しを引く道具（lib/eyeverdict.py の _MD_FENCE・_md_lines・_md_slugs・_MD_RULES の写し）
_MD_FENCE = re.compile(r"^\s{0,3}(```|~~~)")


def _md_lines(text):
    """(行番号, 行) を、コードブロック（``` / ~~~ の囲い）の外の行だけ返す"""
    fence = False
    for i, line in enumerate(text.splitlines(), 1):
        if _MD_FENCE.match(line):
            fence = not fence
        elif not fence:
            yield i, line


def _md_slugs(text):
    """見出しのアンカー（GitHub の書き方: 小文字にし、語の文字・- ・空白以外を落とし、空白を - に。重複は -1, -2 …）"""
    seen, out = {}, set()
    for _, line in _md_lines(text):
        m = design.MD_HEAD.match(line)
        if not m:
            continue
        h = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", m.group(2).strip())   # 見出しの中のリンクは文字だけが残る
        s = re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-")
        n = seen.get(s, 0)
        seen[s] = n + 1
        out.add(s if n == 0 else f"{s}-{n}")
    return out


MD_RULES = types.SimpleNamespace(
    MD_LINK=re.compile(r"(?<!!)\[[^\]\n]*\]\((?:<([^>\n]+)>|([^()\s<]+))(?:\s+\"[^\"]*\")?\)"),
    _md_lines=_md_lines, _md_slugs=_md_slugs)


def view_of(answers, request_text: str) -> types.SimpleNamespace:
    """前提を組むだけの見え方（承認ノードの答え・依頼の本文・名指しを引く道具だけ）"""
    return types.SimpleNamespace(record={"process": {"human_items": eyekit.human_items(answers)}},
                                 state={"inputs": {"request": request_text}}, rules=MD_RULES)


# ---------------------------------------------------------------- 前半（independent-design の material の写し）
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


# ---------------------------------------------------------------- 後半（premise_section の値で受ける写し）
def _lines(rows: list, none: str = NONE) -> str:
    return "\n".join(f"- {r}" for r in rows) if rows else none


def constraint_rows(constraints) -> list:
    """記録の制約の行 `（<kind>）<text>`。port constraints の値（行の配列か、それを constraints の欄に持つ object）"""
    rows = constraints.get("constraints") if isinstance(constraints, dict) else constraints
    return [f"（{c.get('kind')}）{c.get('text')}" if isinstance(c, dict) else str(c) for c in rows or []]


def constraints_text(constraints) -> str:
    return _lines(constraint_rows(constraints))


def after(ledger: dict, request_read: bool, design_premises, changed, constraints) -> dict:
    """設計の後の前提。{late, drift, constraints, ledger}。late は独立設計の控えの seen.count より後の人の答えの行（控えが無ければ
    数えず空）、drift は前提のずれの申告（changed.premise_drift が真なら premise_drift_note。空なら「（申告の文なし）」。changed が
    空なら「（修正の印が渡っていない）」）、constraints は記録の制約の行。ledger は貼った物の控え（given に drift・constraint の行を足し、
    依頼のファイルが読めない時は withheld に足し、控えが在れば after_design を持つ）。kind が KINDS の外なら BoardGap"""
    ledger = {"given": list(ledger["given"]), "withheld": list(ledger["withheld"]), "seen": ledger["seen"]}
    if not request_read:
        ledger["withheld"].append({"kind": "named_section", "what": "依頼", "why": NO_REQUEST})
    seen = design_premises.get("seen") if isinstance(design_premises, dict) else None
    late = ""
    if isinstance(seen, dict):
        answers = [g["what"] for g in ledger["given"] if g.get("kind") == "human_answer"]
        ledger["after_design"] = answers[seen.get("count") or 0:]
        late = _lines(ledger["after_design"], "")
    changed = changed if isinstance(changed, dict) and changed else None
    flag = changed.get("premise_drift") if changed else None
    drift = [str(changed.get("premise_drift_note") or "").strip() or NO_NOTE] if flag is True else []
    ledger["given"] += [{"kind": "drift", "what": d} for d in drift] + [{"kind": "constraint", "what": c} for c in constraint_rows(constraints)]
    outside = sorted({g["kind"] for g in ledger["given"]} - set(KINDS))
    if outside:
        raise BoardGap(f"貼った前提の種類が許す一覧（{' / '.join(KINDS)}）の外: {', '.join(outside)}")
    return {"late": late, "drift": _lines(drift) if flag is not None else NO_MARKS, "constraints": constraints_text(constraints),
            "ledger": ledger}
