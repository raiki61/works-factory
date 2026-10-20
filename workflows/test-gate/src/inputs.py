"""script が with: で受けた入力の字を値に戻す（Archon が運ぶ字。飛ばされた node の null と空の字は None）。"""
from __future__ import annotations

import json


def value(raw):
    """JSON の値。null・空の字・無い入力は None。JSON でなければ字のまま（読めない返答を、呼び手が「JSON として読めない」と拒む）"""
    if raw is None or not raw.strip() or raw.strip() == "null":
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return raw
