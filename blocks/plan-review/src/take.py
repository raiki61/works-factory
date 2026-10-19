"""審査の受け付け（docs/design/plan-review.md の 9.1〜9.3）。今の lib/boardview.py の take_review・_take・named・_lines・_pass_rejects
（:971-1084）と、lib/planblk.py の受け付けの部品 face_row_gaps・design_gaps・kept_keys・item_refs・coverage_gaps・bound_map・_map_rows・
unit_name・_names（:630-713）の写し。

往復の記録に足す所（今の converge.record_pass・stash_rejects・止まった時の保留の穴を review.json に足す所）は写さず、往復の記録に足す
行の材料を pass.json に書く（line が converge.add_pass に渡す）。却下の理由の文は Python が組む日本語のまま（README 5.3）。

- take(place, reply, repo, *, keys, fix_reply=None, tree_reply=None, tree_fix_reply=None) -> {ok, done, give_up, reason}: 4 つの組の
  返答（起きなかった node は None）のうち起きた組を受ける。受け付けの網（rolekit.NET_AFTER 回目で done・give_up）
- 部品: face_row_gaps・design_gaps・item_refs・coverage_gaps・bound_map・fences_twice・named（src/tree.py も引く）。unit_name・_names・
  _map_rows・kept_keys は src/material.py の写し（材料の鍵の一覧と同じ部品）
"""
from __future__ import annotations

import copy
import pathlib
import re

import accept      # lib/。tree_moved・guard
import converge    # lib/
import design      # lib/
import gatemarks   # lib/。recommend_gaps
import jsonfile    # lib/
import planmarks   # lib/。machine_face_gaps
import policy      # lib/。face_gaps・RECORDED_KEY
import recount     # lib/。blank
import rolekit     # lib/
from engine.util import Reject   # lib/graphloops/engine/util.py

from src import files, marks, material, steps, view

REVIEW_NODE = files.REVIEW_NODE
# 受け付けの拒みの頭（今の lib/planblk.py:83-98 の字）
RECOMMEND_REJECT = (f"承認ノードの項目の行の推し（{gatemarks.RECOMMEND}）の形が崩れている（直して出し直せ）。"
                    f"書くなら {gatemarks.RECOMMEND_SHAPE} の形で:")
RESOLVED_REJECT = "前の往復の答えの要る穴の行き先が書かれていない（下の行を全部直して出し直せ）:"
FACE_REJECT = "穴の行に誤りが在る（下の行を全部直して出し直せ）:"
TREE_REJECT = "項目ごとの審査の答え（下請けの答えのファイル・束ね役の items）に欠けか誤りが在る（下の行を全部直して出し直せ）:"
READONLY_MOVED = "読むだけの役が作業ツリーを変えた: "
NO_TREE = "役を起こす前の作業ツリーの控え {name} が無い（支度のノードが走っていない）"
DESIGN_QUOTE_REJECT = ("独立設計の引用か design_map に誤りが在る（下の行を全部直して出し直せ。「」は独立設計と案の行の引用だけに使い、"
                       "ほかの引用は『』か `…` で書く）:")
FENCES_TWICE = "faces[{j}]（{key}）: fences に同じ語が 2 つ（{words}）"
GIVEN_UP_FACES = "事前審査の受け付けが諦めた: "   # 今の boardview.GIVEN_UP_FACES
FACE_MARKS = files.FACE_MARKS   # 穴の行から外した決め手の欄（review.json の faces と同じ並び。src/gate.py が読む）
MATERIAL_N = re.compile(r"review-material-(\d+)\.md")


# ---------------------------------------------------------------- 単位の名（unit_name・_names・_map_rows・kept_keys・_later・_map_items・
# _counts_coverage は src/material.py の写しを引く。材料の鍵の一覧と受け付けが同じ部品で組む）
unit_name = material.unit_name
_map_rows = material._map_rows
kept_keys = material.kept_keys
_later = material._later
_map_items = material._map_items
_counts_coverage = material._counts_coverage


def _names(b) -> list:
    return material._names(b, REVIEW_NODE)


def named(b, reply: dict) -> dict:
    """返答の faces・shrink の unit_keys の番号を単位の名に戻した写し（戻せない番号は番号のまま。照らしが拒む）"""
    names = _names(b)
    out = copy.deepcopy(reply)
    for field in ("faces", "shrink"):
        for row in out.get(field) or []:
            if isinstance(row, dict) and isinstance(row.get("unit_keys"), list):
                row["unit_keys"] = [unit_name(names, k) for k in row["unit_keys"]]
    return out


# ---------------------------------------------------------------- 独立設計の照らし（今の planblk の写し）
def bound_map(b, items: list, design_map) -> list:
    """項目 items の答えの対応表を、照らす案の行（_map_rows）の要る鍵に結び直し、余りの行を落とした写し（design.rebound）。受け付けは
    照らしと refs と網羅の数えの前に当てる"""
    return design.rebound(_map_rows(b, items), design_map or [])


def design_gaps(b, faces, items: list, design_map=None, kept=()) -> list[str]:
    """独立設計の引用の誤りの行（design.quote_gaps。設計が立たない run では空）。faces の unit_keys は単位の名に戻して重ね、案の行は
    往復の記録の作業の写しの項目 items の行。design_map を渡す（None でない）と items の files の (path, symbol) ごとの対応表も求める
    （kept の鍵は求めない。kept_keys）。独立設計の要素の網羅は照らさない（全部の項目の答えを合わせて coverage_gaps で当てる）"""
    names = _names(b)
    rows = _map_rows(b, items)
    got = [{**f, "unit_keys": [unit_name(names, k) for k in f.get("unit_keys") or []]} for f in faces or [] if isinstance(f, dict)]
    return design.quote_gaps(b.dir, b.design_schema, got, rows, design_map, kept)


def item_refs(b, n: int, refs: list, kept, design_map) -> list:
    """往復の記録に置く項目 n の design_ref の並び: 今の答えの refs と、kept の項目 n の鍵のうち design_map に行の無い鍵が在れば前の
    往復の項目 n の refs（converge.last_refs。書き直さなかった行が受けた要素を網羅に引き継ぐ。kept の鍵を全部書き直した答えは
    書いた行だけで数える）"""
    written = {(e.get("item"), e.get("path"), e.get("symbol")) for e in design_map or [] if isinstance(e, dict)}
    carried = converge.last_refs(b, n) if any(k[0] == n and k not in written for k in kept) else []
    return list(dict.fromkeys([*refs, *carried]))


def coverage_gaps(b, refs, items) -> list[str]:
    """独立設計の要素の網羅の誤りの行（design.coverage_gaps。設計が立たない run では空）。refs は今の往復の答えの対応表の design_ref
    の並び、items は今の往復が見る項目。見ない閉じた項目が前の往復の答えで受けた要素（converge.carried_refs）を足して数える"""
    stood = design.stands(b.dir, b.design_schema)
    return [] if stood is None else design.coverage_gaps(stood.get("elements"), [*refs, *converge.carried_refs(b, items)])


def face_row_gaps(faces, rows) -> list[str]:
    """事前審査の穴 faces の 1 行ずつに当てる照らしの束（誤りの行は『faces[j]（key）: …』）: kind policy の穴の方針の名指しと fences の
    policy_doc（policy.face_gaps。rows は記録された方針の一覧）・入口の穴の no_add（空同然は recount.blank。柵や入口を足さずに閉じる形か、
    無理な理由）・where で機械の足した欄を名指す block（planmarks.machine_face_gaps）。木の往復は項目 n の答えの faces と相乗りの答えに、
    木にしない往復は返答の faces に 1 度当てる。返答の全体の照らし（key の重複・案に無い単位・faces_none）は含まない（view.plan_review_output）"""
    faces = faces or []
    entrance = [f"faces[{j}]（{str(f.get('key'))[:40]}）: entrance に no_add（柵や入口を足さずに閉じる形。無理なら無理な理由）が無い"
                for j, f in enumerate(faces) if isinstance(f, dict) and f.get("kind") == "entrance" and recount.blank(f.get("no_add"), 20)]
    return policy.face_gaps(faces, rows) + entrance + planmarks.machine_face_gaps([f if isinstance(f, dict) else {} for f in faces])


def fences_twice(faces) -> list[str]:
    """fences に同じ語を 2 つ持つ穴の行（今は役の型の uniqueItems が拒んでいた。型の語は KNOWN_KEYWORDS だけなので受け付けが拒む）"""
    out = []
    for j, f in enumerate(faces or []):
        words = f.get("fences") if isinstance(f, dict) else None
        if isinstance(words, list):
            twice = sorted({str(w) for w in words if words.count(w) > 1})
            if twice:
                out.append(FENCES_TWICE.format(j=j, key=str(f.get("key"))[:40], words="・".join(twice)))
    return out


# ---------------------------------------------------------------- 受け付け
def _lines(head: str, gaps: list) -> str:
    return head + "\n" + "\n".join(f"  - {g}" for g in gaps)


def _moved(place: pathlib.Path, repo, keys) -> str:
    """役が作業ツリーを変えた・HEAD や枝を動かした訳（keys の欄で比べる。変えていなければ空）。起こす前の姿が読めなければその訳"""
    before = jsonfile.read_or(place / files.TREE_STATE)
    if not isinstance(before, dict):
        return NO_TREE.format(name=files.TREE_STATE)
    changes = accept.tree_moved(before, pathlib.Path(repo), keys=keys)
    return READONLY_MOVED + "；".join(changes) if changes else ""


def _pass_rejects(place: pathlib.Path) -> list:
    """往復の行に残す、この往復の事前審査の拒否の行 {role, at, reason, kind?}（計画の拒否は line が足す。place は include ごとに
    分かれるので、往復ごとに 0 から数え直す）"""
    return [{"role": REVIEW_NODE, **r} for r in rolekit.reject_rows(place, REVIEW_NODE)]


def _material_file(place: pathlib.Path) -> dict:
    """往復の記録に写す材料のファイル（輪の一番新しい review-material-<n>.md。無ければ空）"""
    got = sorted((int(m.group(1)), p) for p in place.glob("review-material-*.md") if (m := MATERIAL_N.fullmatch(p.name)))
    return {got[-1][1].name: str(got[-1][1])} if got else {}


def take(place, reply, repo, *, keys=accept.TREE_KEYS, fix_reply=None, tree_reply=None, tree_fix_reply=None) -> dict:
    """事前審査の受け付け（9.1）。reply・fix_reply は単独の組（review・review-fix）、tree_reply・tree_fix_reply は束ね役の組
    （review-tree・review-tree-fix）の返答で、どれも JSON に戻した値（起きなかった node は None）。出し直しは前の答えの控えと
    rolekit.merge_fields で合わせ（rolekit.resubmitted）、合わせた答えの全体を照らす。拒みは place の控えに積み、受け付けの網
    rolekit.NET_AFTER 回目で done・give_up（工場の不具合。その時は最後の拒みの訳を reason に置いた空の返答を review.json に書き、
    pass.json は書かない）。返り {ok, done, give_up, reason}"""
    place = pathlib.Path(place)
    intake = steps.read_intake(place)
    first = reply if reply is not None else tree_reply
    part = fix_reply if fix_reply is not None else tree_fix_reply
    got = rolekit.round_outcome(rolekit.accept_parsed(
        place, REVIEW_NODE, rolekit.resubmitted(place, REVIEW_NODE, first, part, rolekit.merge_fields),
        lambda merged: accept.guard(lambda: _take(place, intake, merged, repo, keys)), net=True))
    if got["give_up"]:
        jsonfile.write(place / files.REVIEW, {"faces": [], "shrink": [], "reason": GIVEN_UP_FACES + got["reason"]}, indent=2)
        jsonfile.write(place / FACE_MARKS, [], indent=2)
        (place / files.PASS).unlink(missing_ok=True)
    return got


def _take(place: pathlib.Path, intake: dict, reply: dict, repo, keys) -> dict:
    moved = _moved(place, repo, keys)
    if moved:
        raise Reject(moved)
    gaps = gatemarks.recommend_gaps(REVIEW_NODE, reply)
    if gaps:
        raise Reject(_lines(RECOMMEND_REJECT, gaps))
    b = view.view(place, intake)
    bare, resolved, tree = marks.split_review(reply)
    form = intake.get("form")
    # 木にしない往復は審査役 1 つの返答のまま（出自の申告 origins は役の型が確かめた返答の欄）。木の分かれ目は intake の tree 1 つ
    merged = {"review": bare, "resolved": resolved, "synergy": [], "hits": {}, "origins": list(tree.get(converge.ORIGINS) or []),
              "files": {}, "gaps": [], "off": True}
    if form == "plan" and intake.get("tree"):
        from src import tree as treeparts   # 木の部品は受け付けの部品（このモジュール）を引く
        merged = treeparts.tree_merge(b, bare, tree, resolved)
        if merged["gaps"]:
            raise Reject(_lines(TREE_REJECT, merged["gaps"]))
    refs = {}
    if merged.get("off"):
        gaps = face_row_gaps(merged["review"].get("faces") or [], intake.get(policy.RECORDED_KEY) or [])
        if gaps:
            raise Reject(_lines(FACE_REJECT, gaps))
        items = _map_items(b, intake)
        kept = kept_keys(b, items or []) if _later(b, intake) else set()
        dmap = bound_map(b, items or [], tree.get(converge.DESIGN_MAP))
        refs = {n: item_refs(b, n, [*design.refs_of([e for e in dmap if isinstance(e, dict) and e.get("item") == n]),
                                    *design.refs_of([e for e in dmap if isinstance(e, dict) and e.get("item") is None])], kept, dmap)
                for n in items or []}
        gaps = design_gaps(b, merged["review"].get("faces"), items, dmap, kept)
        if _counts_coverage(intake):
            gaps += coverage_gaps(b, [*design.refs_of(dmap), *(r for rs in refs.values() for r in rs)], items)
        if gaps:
            raise Reject(_lines(DESIGN_QUOTE_REJECT, gaps))
    review = named(b, merged["review"])
    if form == "plan":
        gaps = converge.resolved_gaps(b, review.get("faces") or [], merged["resolved"])
        if gaps:
            raise Reject(_lines(RESOLVED_REJECT, gaps))
    view.plan_review_output(b, REVIEW_NODE, review, None)
    twice = fences_twice(review.get("faces"))
    if twice:
        raise Reject(f"{REVIEW_NODE}: " + "; ".join(twice))
    bare_review, face_marks = marks.split_faces(review)
    written = {**bare_review, converge.RESOLVED: merged["resolved"]} if merged["resolved"] else bare_review
    jsonfile.write(place / files.REVIEW, written, indent=2)
    jsonfile.write(place / FACE_MARKS, face_marks, indent=2)
    if form == "plan":
        checks = jsonfile.read_or(place / files.PRECEDENT_CHECKS)
        if merged.get("precedents"):
            from src import tree as treeparts
            checks = treeparts.save_precedents(b, *merged["precedents"])
        doc = converge.read(b)
        jsonfile.write(place / files.PASS, {
            "pass": converge.pass_no(b), "plan": doc.get("plan") or [], "answers": (doc.get("open") or {}).get("answers", []),
            "review": bare_review, "resolved": merged["resolved"], "synergy": merged["synergy"], "hits": merged["hits"],
            "origins": merged["origins"], "refs": merged.get("refs") or refs, "push": tree.get(converge.STUCK_PUSH),
            "files": {**merged["files"], **_material_file(place)}, "rejects": _pass_rejects(place),
            "precedent_checks": checks if isinstance(checks, dict) else {}}, indent=2)
    return {"ok": True, "reason": ""}
