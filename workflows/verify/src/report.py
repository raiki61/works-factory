"""報告の節「判定の単位の裏取り」の行（docs/design/verify.md の 5 節）。申し送り verify.json の値から組む"""
import oneline  # lib/

HEAD = "判定の単位の裏取り"


def _list(value) -> list:
    return value if isinstance(value, list) else []


def lines(doc, ran: bool) -> list:
    """doc は申し送りの dict、ran は束ね役を起こしたか。回さなかった時は訳の 1 行"""
    doc = doc if isinstance(doc, dict) else {}
    syn = doc.get("synergy") if isinstance(doc.get("synergy"), dict) else {}
    if not ran:
        return [f"{HEAD}: 回さなかった（{oneline.one_line('・'.join(map(str, _list(syn.get('errors')))))}）"]
    units = [u for u in _list(doc.get("units")) if isinstance(u, dict)]
    notes = []
    for u in units:
        key = u.get("key")
        if u.get("state") != "checked":
            notes.append(f"確かめられなかった: {key}（{oneline.one_line('・'.join(map(str, _list(u.get('errors')))))}）")
            continue
        if u.get("verdict") == "not_root":
            notes.append(f"根本でない: {key}（本当の根: {oneline.one_line(u.get('real_root'))}。{oneline.one_line(u.get('why'))}）")
        elif u.get("verdict") == "unsure":
            notes.append(f"根本か決められない: {key}（{oneline.one_line(u.get('why'))}）")
        if u.get("evidence_found") is False:
            notes.append(f"証拠が無い: {key}（{oneline.one_line(u.get('evidence'))}）")
        if u.get("location_ok") is False:
            notes.append(f"場所が違う: {key}（正しい場所: {oneline.one_line(u.get('location'))}）")
    if syn.get("state") == "checked":
        notes += [f"重複: {'・'.join(map(str, r.get('units') or []))}（{oneline.one_line(r.get('why'))}）"
                  for r in _list(syn.get("duplicates")) if isinstance(r, dict)]
        notes += [f"順番: {r.get('first')} → {r.get('then')}（{oneline.one_line(r.get('why'))}）"
                  for r in _list(syn.get("order")) if isinstance(r, dict)]
    else:
        notes.append("単位どうしの相乗りは確かめられなかった")
    if not notes:
        return [f"{HEAD}: {len(units)} 単位とも根本・証拠・場所が合った（重複・順番の名指しなし）"]
    return [f"{HEAD}（{len(units)} 単位。単位は消していない。減らすなら承認ノードか再審で）:", *[f"  - {x}" for x in notes]]
