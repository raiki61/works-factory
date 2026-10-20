"""報告の節「世界の解」の行を値から組む（lib/worldmark.py の report_lines を、控えのファイルでなく値で受ける形にした写し）。
行の語（VERDICT_WORDS・NOT_WEB・DIFFERS・WEB）は lib/worldmark が持つ。"""
import worldmark  # lib/


def _mark(row: dict) -> str:
    return f"（{worldmark.NOT_WEB}）" if row.get("basis") != worldmark.WEB else ""


def _versus(row: dict) -> str:
    v = row.get("versus") or {}
    word = worldmark.VERDICT_WORDS.get(v.get("verdict"), str(v.get("verdict")))
    head = f"依頼の解き方「{v.get('proposed')}」は{word}" if v.get("proposed") else word
    return f"{head}——{v['challenge']}" if v.get("verdict") == worldmark.DIFFERS and v.get("challenge") else head


def lines(*, status: str, reason: str, rows: list, classes: int, dropped: int) -> list:
    if status != "ok":
        return [f"- 世界の解の段が落ちた（行なしで進んだ）: {reason or '理由の記録が無い'}"]
    out = [f"- 類 {r['class_id']}（依頼の行 {r['finding']}）: {r['practice']}{_mark(r)}（{_versus(r)}）" for r in rows]
    out.append(f"- 類 {classes}・落とした抜き書き {dropped}")
    return out
