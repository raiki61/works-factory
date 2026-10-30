"""形 theme（設計の案）の指示の値と受け付け（docs/design/plan-review.md の 19 節）。

- resubmitting(place, prev) -> 輪の前の周の受け付けが拒み、合わせた答えの控えが在るか（在れば出し直しの周）
- prompt_values(place, intake, repo) -> (values, when): 1 回目の役（review-theme）の指示の値（作り手は src/material.py の SLOTS・WHEN）
- fix_values(place, intake) -> (values, when): 出し直しの役（review-theme-fix。1 回目の役の会話の続き）の指示の値（拒否の訳と合わせた
  答えの在りか）
- take(place, reply, repo, *, keys, fix_reply=None) -> {ok, done, give_up, reason}: 設計の案の審査の返答の受け付け。出し直しは前の答えの
  控えと rolekit.merge_fields で合わせ（要る根の欄 files.REVIEW_REQUIRED）、合わせた答えの全体を照らす。上から 1 作業ツリーが役の前と
  同じ・2 穴の行ごとの照らし（形 text と同じ部品）・3 返答の全体（形 text と同じ）・4 前の往復の答えの要る穴の行き先
  （converge.resolved_gaps。往復の記録が項目の行 plan を持たないので、項目で絞らずに穴の鍵だけで照らす）。通れば review.json に
  {faces, shrink, reason, faces_none?, resolved?}。拒否の回数では諦めず、受け付けの網 rolekit.NET_AFTER 回目で done・give_up（その時は
  諦めの訳を reason に置いた空の返答を review.json に書く）

却下の理由の文は Python が組む日本語のまま（README 5.3）。照らしの部品は形 plan と形 text の受け付け（src/take.py・src/textform.py）の物。
"""
from __future__ import annotations

import pathlib

import prompt

import accept      # lib/
import converge    # lib/
import jsonfile    # lib/
import policy      # lib/。RECORDED_KEY
import rolekit     # lib/
from engine.util import Reject   # lib/graphloops/engine/util.py

from src import files, marks, material, steps, take as review_take, textform, view

NODE = "review-theme"          # 1 回目の役（prompts/review-theme.md）
FIX_NODE = "review-theme-fix"  # 出し直しの役（prompts/review-theme-fix.md）


def resubmitting(place, prev) -> bool:
    """prev は輪の前の周の受け付けの ok を値に戻した物"""
    return rolekit.resubmitting(pathlib.Path(place), files.THEME_NODE, prev)


def prompt_values(place, intake: dict, repo) -> tuple[dict, dict]:
    return material.fragment_values([f"node:{NODE}"], pathlib.Path(place), intake, repo)


def fix_values(place, intake: dict) -> tuple[dict, dict]:
    place = pathlib.Path(place)
    rejected = rolekit.rejected(place, files.THEME_NODE)
    values = {"rejection": rejected[-1] if rejected else "", "candidate": str(rolekit.candidate_path(place, files.THEME_NODE)),
              "lang": prompt.lang(intake.get("lang") or "")}
    return values, {"spawns": False}


def take(place, reply, repo, *, keys=accept.TREE_KEYS, fix_reply=None) -> dict:
    place = pathlib.Path(place)
    (place / files.REVIEW).unlink(missing_ok=True)
    intake = steps.read_intake(place)
    got = rolekit.round_outcome(rolekit.accept_parsed(
        place, files.THEME_NODE,
        rolekit.resubmitted(place, files.THEME_NODE, reply, fix_reply, rolekit.merge_fields, required=files.REVIEW_REQUIRED),
        lambda merged: accept.guard(lambda: _take(place, intake, merged, repo, keys)), net=True))
    if got["give_up"]:
        jsonfile.write(place / files.REVIEW, {"faces": [], "shrink": [], "reason": steps.GIVEN_UP_FACES + got["reason"]}, indent=2)
    return got


def _take(place: pathlib.Path, intake: dict, reply: dict, repo, keys) -> dict:
    moved = review_take._moved(place, repo, keys)
    if moved:
        raise Reject(moved)
    bare, resolved, _ = marks.split_review(reply)
    faces = bare.get("faces") or []
    gaps = review_take.face_row_gaps(faces, intake.get(policy.RECORDED_KEY) or []) + review_take.fences_twice(faces)
    if gaps:
        raise Reject(review_take._lines(review_take.FACE_REJECT, gaps))
    gaps = textform._whole_gaps(bare)
    if gaps:
        raise Reject(review_take._lines(textform.WHOLE_REJECT, gaps))
    gaps = converge.resolved_gaps(view.view(place, intake), faces, resolved)
    if gaps:
        raise Reject(review_take._lines(review_take.RESOLVED_REJECT, gaps))
    got = {k: bare[k] for k in ("faces", "shrink", "reason", "faces_none") if k in bare}
    jsonfile.write(place / files.REVIEW, {**got, converge.RESOLVED: resolved} if resolved else got, indent=2)
    return {"ok": True, "reason": ""}
