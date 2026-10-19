"""R1 の最小性の役の材料の行（R1 だけが使う）。lib/eyeverdict.py の prompt_texts の units_text・fixes_text（:349-356）の写し"""
NO_UNITS = "（単位の目録が渡っていない）"
NO_FIXES = "（修正の単位の結末が渡っていない）"


def _lines(rows: list, none: str) -> str:
    return "\n".join(f"- {r}" for r in rows) if rows else none


def units_text(units) -> str:
    """判定が切った根本の単位の目録 [{id, summary, paths}] の行"""
    rows = [f"{u.get('id')}: {u.get('summary')}（{', '.join(u.get('paths') or [])}）" for u in units or [] if isinstance(u, dict)]
    return _lines(rows, NO_UNITS)


def fixes_text(fixes) -> str:
    """この run の修正の単位ごとの結末 [{unit_id, group_id, status, reason}] の行"""
    rows = [f"{u.get('unit_id')}（組 {u.get('group_id')}）: {u.get('status')}——{u.get('reason')}" for u in fixes or [] if isinstance(u, dict)]
    return _lines(rows, NO_FIXES)
