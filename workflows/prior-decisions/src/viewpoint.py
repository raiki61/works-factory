"""観点 prior-decisions（先行議論の突合）の宣言（docs/design/materials.md の 5.1・docs/design/prior-decisions.md の 1.5）。

対象差分が触れる領域（差分が空の判定から入る run では依頼が指す場所）の決定記録を洗わせ、決着済みの論点（settled）と素材
prior_decisions を返させる。いつも回し（1 run は 1 周で、いつも初回）、『条件に当たらない』は名乗れない。受け付けの流れと出口は
lib/materialkit が持ち、ここは宣言だけを持つ。
"""
import json

import materialkit  # lib/
import oneline  # lib/

NAME = "prior-decisions"
MATERIALS = ("prior_decisions",)
GUARDED = False   # AI の node が mutates_checkout: false を持たない（作業ツリーの照らしは porcelain も比べる）
NA = "never"
NA_REASON = ""
NA_PARAGRAPH = True   # 返答が material の欄を持ち、md が共通の断片 material-na を差し込む
NO_WHERE = "書いてある所の記録が無い"


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1)


def due(view, values) -> materialkit.Due:
    return materialkit.Due(True, "先行議論の突合は run ごとに 1 回回す（1 run は 1 周で、いつも初回）")


def fill(view, values, due) -> dict:
    raise NotImplementedError("prior-decisions はいつも回すので、回さない時の素材の埋めは呼ばれない")


def applies(view, values) -> materialkit.Due:
    raise NotImplementedError("prior-decisions は『条件に当たらない』を名乗れない（NA が never）")


def judged_na(view, values) -> bool:
    return False


def _request_rows(values) -> list:
    rows = values.get("request")
    rows = rows.get("findings") if isinstance(rows, dict) else rows
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def request_wheres(view, values) -> list:
    """判定から入る run の周（materialkit.is_entry_run: 対象差分が空で entry が在る）の、依頼の行の where の並び。そうでない run は []"""
    if not materialkit.is_entry_run(view, values):
        return []
    return [r["where"] for r in _request_rows(values) if isinstance(r.get("where"), str)]


def values(view, values) -> dict:
    return {"repo": str(view.repo), "base": view.base, "changed_files": _dump(list(view.changed_files)),
            "request_wheres": _dump(request_wheres(view, values))}


def when(view, values) -> dict:
    return {"spawns": False}


def before(view, values, reply, place) -> tuple:
    return None, reply, False


def after(view, values, reply, place):
    return None


def after_accept(reply, place) -> None:
    return None


def materials_of(reply) -> dict:
    return {"prior_decisions": reply["material"]} if isinstance(reply.get("material"), dict) else {}


def report_lines(doc) -> list:
    reply = doc.get("reply")
    rows = reply.get("settled") if isinstance(reply, dict) else None
    return [f"  - 決着済みの論点: {oneline.one_line(r.get('topic') or '')}（{oneline.one_line(r.get('where') or '') or NO_WHERE}）"
            for r in rows or [] if isinstance(r, dict)]
