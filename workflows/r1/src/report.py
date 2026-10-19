"""報告の節「独立の目」に載せる R1 の行（docs/design/r1.md の 5.3）。頭の 1 行は eyekit.headline、続く行は削るとした所と、残した
コメントが運ぶ事実（report の設計書の 1.6 が求めた「削ったコメントと残した why」）"""
import eyekit    # lib/
import oneline   # lib/

DELETION = "  - 削るとした所: {where}（{why}）"
KEPT = "  - 残したコメントが運ぶ事実: {where}: {fact}"
NO_CANDIDATES = "  - コメントの削除候補は取れなかった（{why}）"


def _rows(reply, field: str) -> list:
    rows = reply.get(field) if isinstance(reply, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def lines(row: dict, minimality, comments: tuple) -> list:
    """row は判定の行、minimality は 2 段目の返答（無ければ None）、comments は前段の (返答, 読めない訳)"""
    out = [eyekit.headline("R1", row)]
    out += [DELETION.format(where=d.get("where"), why=oneline.one_line(d.get("why") or "")) for d in _rows(minimality, "deletions")]
    reply, why = comments
    if reply is None:
        out.append(NO_CANDIDATES.format(why=why))
    else:
        out += [KEPT.format(where=k.get("where"), fact=oneline.one_line(k.get("fact") or "")) for k in _rows(reply, "kept")]
    return out
