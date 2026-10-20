"""形 text（方針の文だけ）の指示の値と受け付け（docs/design/plan-review.md の 7 節・9.4）。

- values(place, intake) -> (values, when): prompts/review-text.md の差し込み口の値と段落の真偽（作り手は src/material.py の
  SLOTS・WHEN。値の組み方は形 plan の役と同じ口）
- take(place, raw, repo, *, keys) -> {ok, done, give_up, reason}: 方針の文の審査の返答の受け付け。上から 1 作業ツリーが役の前と同じ・
  2 穴の行ごとの照らし（kind policy の穴の方針の名指しと policy_doc の柵・入口の穴の no_add・fences の重なり）・3 返答の全体（faces・
  shrink の key の重なり・穴も別案も無いのに faces_none が空同然）。通れば review.json に {faces, shrink, reason, faces_none?}。
  rolekit.GIVE_UP_AFTER 回目で諦める（review.json を書かない。出口が gave_up を返す）。出し直しは同じ会話の続きで丸ごと（{shared:rejected}）

却下の理由の文は Python が組む日本語のまま（README 5.3）。照らしの部品は形 plan の受け付け（src/take.py）と同じ物を使う。
"""
from __future__ import annotations

import pathlib

import accept      # lib/
import jsonfile    # lib/
import policy      # lib/。RECORDED_KEY
import rolekit     # lib/
from engine.util import Reject   # lib/graphloops/engine/util.py

from src import files, material, take as review_take, view

NODE = "review-text"   # AI の node の id（prompts/review-text.md）
WHOLE_REJECT = "返答の全体に誤りが在る（下の行を全部直して出し直せ）:"
NONE_WHY = "穴も別案も挙げないなら faces_none に何を確かめて無いと言えるかを書け"


def values(place, intake: dict, repo=None) -> tuple[dict, dict]:
    """prompts/review-text.md の差し込み口の値と段落の真偽。repo は作業ツリー（既定は intake の cwd）"""
    return material.fragment_values([f"node:{NODE}"], place, intake, repo or intake.get("cwd") or ".")


def _whole_gaps(reply: dict) -> list[str]:
    """返答の全体の照らし（view.plan_review_output の、単位を持たない形の部分: key の重なり・faces_none）"""
    rows = [r for r in (reply.get("faces") or []) + (reply.get("shrink") or []) if isinstance(r, dict)]
    gaps = view._keys_once(rows, "faces・shrink")
    if not rows and view.blank(reply.get("faces_none"), 20):
        gaps.append(NONE_WHY)
    return gaps


def take(place, raw, repo, *, keys=accept.TREE_KEYS) -> dict:
    """方針の文の審査の受け付け（9.4）。返り {ok, done, give_up, reason}"""
    place = pathlib.Path(place)
    intake = jsonfile.read_or(place / files.INTAKE)
    rows = (intake.get(policy.RECORDED_KEY) or []) if isinstance(intake, dict) else []

    def run(reply):
        moved = review_take._moved(place, repo, keys)
        if moved:
            raise Reject(moved)
        faces = reply.get("faces") or []
        gaps = review_take.face_row_gaps(faces, rows) + review_take.fences_twice(faces)
        if gaps:
            raise Reject(review_take._lines(review_take.FACE_REJECT, gaps))
        gaps = _whole_gaps(reply)
        if gaps:
            raise Reject(review_take._lines(WHOLE_REJECT, gaps))
        got = {k: reply[k] for k in ("faces", "shrink", "reason", "faces_none") if k in reply}
        jsonfile.write(place / files.REVIEW, got)
        return {"ok": True, "reason": ""}

    return rolekit.round_outcome(rolekit.accept_round(place, files.TEXT_NODE, raw, lambda reply: accept.guard(lambda: run(reply))))

