"""fix の置き場（run の作業のファイルを置くフォルダ。scripts が渡す）の読み書きの助け。

今の works の盤面の物 `b` から読んでいた値を、置き場のファイルか引数で受ける形にした物だけを置く。

- trace(place, op, **kw): 置き場の trace.jsonl に {"op": op, **kw} を 1 行足す（元の盤面の b.trace の代わり）
- base_rev(state, given=""): 突き合わせの起点の版（元 works/.shared/core/writes.py:88 の base_rev）
- marks_view(place, round_=1): planmarks の凍結した欄の読み口（frozen・rewrites・removes_permits）に渡す読むだけの形
  （dir と round だけ。conflict の test_permits・frozen_fields が使う。fix のブロックの中だけの合わせ口）
- owed_units_but_asked(place, owed, withheld=, returned=)・fix_duty(place, owed, withheld_by=, returned=)・
  nothing_owed_but_excused(place, owed, withheld_by=, returned=): 直す義務（元 works/.shared/core/conflict.py:676・696・787。
  盤面の写しの規則と問いの台帳を読んだ所を、値の引数で受ける）

標準ライブラリだけ。
"""
import json
import pathlib
import types

TRACE_FILE = "trace.jsonl"


def trace(place, op: str, **kw) -> None:
    """置き場 place の trace.jsonl に {"op": op, **kw} を JSON の 1 行で足す（フォルダが無ければ作る）"""
    path = pathlib.Path(place) / TRACE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"op": op, **kw}, ensure_ascii=False) + "\n")


def base_rev(state, given: str = "") -> str:
    """突き合わせの起点の版: state["inputs"]["review_rev"]（修正前に固めた版）。無ければ given、それも空なら HEAD。
    元 works/.shared/core/writes.py:88（盤面の b.state を読んだ）。state は同じ形の dict（{"inputs": {...}}）か None"""
    return ((state or {}).get("inputs") or {}).get("review_rev") or given or "HEAD"


def marks_view(place, round_: int = 1):
    """planmarks の凍結した欄の読み口（frozen・rewrites・removes_permits。読むのは b.dir と b.round だけ）に渡す読むだけの形:
    dir は置き場 place（plan-fields.json と凍結の印の行の在る trace.jsonl を置く所）、round は round_"""
    return types.SimpleNamespace(dir=pathlib.Path(place), round=round_)


def owed_units_but_asked(place, owed, *, withheld=(), returned=()) -> set:
    """直す義務の単位: owed（開いた単位から、人に諮っている fork の出どころ・depends を除いた物。元は盤面の写しの規則の
    _owed_units）から、関所に載せる問いのうち答えていない物の出どころ・depends（withheld。元は gatemarks.withheld）を除き、
    修正前の関所で人が答えた問いの出どころ・depends（returned。元は gatemarks.returned）を戻し、直す裁定でない裁定を受けた単位
    （conflict.held_by_rulings。ask_human・fix_plan_item）を除く。控えが読めなければ裁定の単位を外さない（義務を減らさない側）。
    元 works/.shared/core/conflict.py:676（盤面の b.state["graph"] の規則と b.record の問いを読んだ）"""
    import conflict
    got = (set(owed) - set(withheld)) | set(returned)
    try:
        return got - set(conflict.held_by_rulings(place))
    except ValueError:   # 控えが読めない置き場は外さない（義務を減らさない側）
        return got


def fix_duty(place, owed, *, withheld_by=None, returned=()) -> tuple:
    """(直す義務 owed_units_but_asked, 直す義務から外れた単位 {key: 理由})。外れた単位は、答えていない fork・escalate の問いの
    出どころ・depends（withheld_by {key: 問い}。元は gatemarks.withheld_by。理由はそこが組にした問い）と、直す裁定でない裁定を
    受けた単位（conflict.held_by_rulings。理由はその裁定）。1 単位が withheld と裁定の両方に当たれば裁定の理由。控えが読めなければ
    裁定の単位を外さない。1 回目に受け付けた返答の控え（conflict.held_reply）が在れば、その単位を直す義務から引き、理由
    conflict.ACCEPTED_WHY で外れた単位に足す（ほかの理由より先）。控えが壊れていれば held_reply の ValueError。
    元 works/.shared/core/conflict.py:696（盤面の記録と問いの台帳を読んだ）"""
    import conflict
    withheld_by = withheld_by or {}
    owed = owed_units_but_asked(place, owed, withheld=set(withheld_by), returned=returned)
    out = {k: f"答え待ちの問い {q.get('key')}（{q.get('kind')}・{q.get('status')}）" for k, q in withheld_by.items()}
    try:
        out.update(conflict.held_by_rulings(place))
    except ValueError:
        pass
    held, path = conflict.held_reply(place)
    accepted = conflict._held_keys(held)
    owed = owed - accepted
    out.update({k: conflict.ACCEPTED_WHY.format(path=path) for k in accepted})
    return owed, {k: why for k, why in out.items() if k not in owed}


def nothing_owed_but_excused(place, owed, *, withheld_by=None, returned=()) -> dict:
    """直す義務が空で、外れた単位（fix_duty の 2 つ目）が 1 件以上ある置き場なら外れた単位 {key: 理由}（空の changes が正しい
    返答）。違う・読めなければ空（止める側）。元 works/.shared/core/conflict.py:787"""
    try:
        owed, excused = fix_duty(place, owed, withheld_by=withheld_by, returned=returned)
        return excused if excused and not owed else {}
    except Exception:   # 置き場・控えが読めない: 空の申告は今どおり止める
        return {}
