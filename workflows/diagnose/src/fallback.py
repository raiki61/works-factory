"""診断の出口が落ちた時の返り（docs/design/diagnose.md の 5.6 の「出口は落ちない」）。標準ライブラリと境の口 ports だけを読む
（出口の script が lib を読めない時にも同じ形を返す。落とし穴 K1）。

- fallen(place, why, objection) -> 出口の返りの欄を全部持つ止めの出力。judgment は在る判定のファイルが形に合えばそれを指し、無い・形に
  合わない時は空の形を書き直してから指す（形に合わない判定を指さない。ここでは形の誤りを投げない）。形の照らし（lib）を読めない時は
  指さずに null
- 止めの語は lib/stopby.py の語の字（src.files の JUDGE_STOP・REJUDGE_STOP が読み込みの時に同じ字かを照らす）
"""
from __future__ import annotations

import json
import pathlib

import ports

JUDGE, REJUDGE = "judge", "rejudge"  # intake の mode の語
JUDGMENT_FILE = "judgment.json"
JUDGE_STOP, REJUDGE_STOP = "works:judge", "works:rejudge"
EMPTY_JUDGMENT = {"units": [], "questions": [], "framing": "", "one_shot": "", "materials_missing": [], "carried_r1": [],
                  "one_shot_closes": [], "precedents": []}
DOWNGRADES = [{"what": "再審は判定役の会話を継がず、保存した返答を読む新しい会話で回す",
               "versus": "review-graph と今の works は判定役の会話を継ぐ"}]


def _judgment(place: pathlib.Path) -> dict:
    """在る判定のファイルが形に合えばそれを、無い・形に合わない時は空の形を書き直してから指す"""
    try:
        return ports.pointer(place / JUDGMENT_FILE, "json(shared:judgment.schema.json)")
    except ValueError:   # 無い・読めない・形に合わない（ShapeError も ValueError の子）
        place.mkdir(parents=True, exist_ok=True)
        (place / JUDGMENT_FILE).write_text(json.dumps(EMPTY_JUDGMENT, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return ports.pointer(place / JUDGMENT_FILE, "json(shared:judgment.schema.json)")


def fallen(place, why: str, objection: str) -> dict:
    mode = REJUDGE if str(objection or "").strip() else JUDGE
    reason = f"判定の出口が落ちた（{' '.join(str(why).split())}）"
    place = pathlib.Path(place)
    try:
        judgment = _judgment(place)
    except ImportError:   # 形の照らし（lib）を読めない: 照らせない判定は指さない（judge の graph の落ちの返りと同じく null）
        judgment = None
    return {"ok": False, "status": "failed", "mode": mode, "stop_reason": REJUDGE_STOP if mode == REJUDGE else JUDGE_STOP,
            "reason": reason, "ready": False, "judgment": judgment, "units": [], "questions": [], "inputs": None, "brief": None,
            "materials": None, "out_of_purpose": None, "answer_ties": None, "rejudge_verdict": None, "rejudge_exit": None,
            "rejudge_diff": None, "downgrades": [dict(row) for row in DOWNGRADES],
            "report": [f"{'再審' if mode == REJUDGE else '判定'}: {reason}"]}
