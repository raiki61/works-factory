"""人に回しうる行と外れの事実（docs/design/plan-review.md の 10 節）。今の lib/gatemarks.py の行の照らし（_gate_rows・_mark・
axis_reasons・_cite_check・_design_rows・_world_rows・_world_answers・_answered_rows・world_items、lib/gatemarks.py:483-711）と、
今の lib/boardview.py の replan_asks の事実の部分（_faces_of・replan_asks、lib/boardview.py:1118-1154）の写し。

承認ノードを開くか・聞き直すか（今の gatemarks._continued）・無人の推しで通すか・軸ごとにまとめるか（今の gate_axes.gather）・
形 replan の行を聞くか（ask）は line が決める。この block は行の事実と、4 つの軸ごとの揃わない訳だけを返す。

- asks(place, intake, review) -> [{kind, node, text, units, mark, decided, why}]: 修正案の narrows の行と、事前審査の穴のうち人に回す
  種類（files.HUMAN_FACE_KINDS）の行。why は {軸: [揃わない訳]}（揃う軸は載せない。空の dict は 4 つの軸が揃う）
- deviations(place, intake, review) -> [{source: "world", item, text, mark, why} | {source: "design", key, kind, why}]
- replan(place, intake, review) -> [{item, units, contract_changed, human, widened}]（files.REPLAN にも同じ行を書く）

決め手の欄は、narrows の行の分は intake.json の plan_marks（入口が外した物）、穴の行の分は受け付けが外した FACE_MARKS
（src/take.py が書く。review.json の faces と同じ並び）から読み、行に重ねてから行の欄として読む（今の _mark の「盤面の控えから読む」道は
持たない。設計書の 14 節の 10）。依頼の文と依頼のファイルは port request（intake.json の request・request_file）から読む（今の
conflict.request_file は始めの記録を読むので使わない）。
"""
from __future__ import annotations

import json
import pathlib

import cite        # lib/。決め手の出どころが現物に在るか
import converge    # lib/。HELD_MARK・planned_units
import design      # lib/。DRIFT_HEAD・UNPAIRED_HEAD
import gatemarks   # lib/。FIELDS・NO_NARROW・decided・AXES と訳の字
import jsonfile    # lib/
import planmarks   # lib/。read・contract_diff・widened
import policy      # lib/。unrecorded・RECORDED_KEY
import replan as replanlib   # lib/。bare
import structmark  # lib/
import worldmark   # lib/

from src import files, take, view

PLAN_NODE = files.PLAN_NODE
REVIEW_NODE = files.REVIEW_NODE
MARK_KEYS = (*gatemarks.FIELDS, gatemarks.NO_NARROW)
FACE_MARKS = take.FACE_MARKS   # 受け付けが穴の行から外した決め手の欄（review.json の faces と同じ並び。src/take.py が書く）
AXES = gatemarks.AXES


# ---------------------------------------------------------------- 決め手の欄
def _at(doc, *idx):
    """doc の idx の位置の値（並びは番号、dict は番号の字で引く。無ければ None）"""
    for i in idx:
        if isinstance(doc, list) and isinstance(i, int) and 0 <= i < len(doc):
            doc = doc[i]
        elif isinstance(doc, dict):
            doc = doc.get(str(i), doc.get(i))
        else:
            return None
    return doc


def _mark(row: dict) -> dict:
    """行の決め手と狭めない案（行が持つ欄だけ。今の gatemarks._mark の行の欄の道）"""
    return {k: row[k] for k in MARK_KEYS if k in row} if isinstance(row, dict) else {}


def _joined(row: dict, mark) -> dict:
    return {**row, **(mark if isinstance(mark, dict) else {})}


def face_marks(place) -> list:
    """受け付けが外した穴の行の決め手の欄（無い・読めなければ []）"""
    doc = jsonfile.read_or(pathlib.Path(place) / FACE_MARKS)
    return doc if isinstance(doc, list) else []


def _board(place, intake: dict, review: dict | None):
    return view.view(pathlib.Path(place), intake, review)


# ---------------------------------------------------------------- 行
def _gate_rows(place, intake: dict, review: dict) -> list:
    """承認ノードの決め手の濾しに掛ける行 [(kind, 文, 決め手, 節, 単位の key の並び)]（修正案の narrows と事前審査の人に回す種類の穴。
    記録された方針の行を名指さない kind policy の穴（policy.unrecorded）と、機械が足した保留の block（converge.HELD_MARK）は行にしない。
    narrows の単位はその項目の unit_keys、穴の単位は穴の unit_keys）"""
    rows = []
    marks = intake.get("plan_marks")
    for i, p in enumerate((intake.get("plan") or {}).get("plan") or []):
        if not isinstance(p, dict):
            continue
        keys = [k for k in p.get("unit_keys") or [] if isinstance(k, str)]
        for j, n in enumerate(p.get("narrows") or []):
            if not isinstance(n, dict):
                continue
            row = _joined(n, _at(marks, i, j))
            rows.append(("regression", f"修正案 {i + 1} が狭める能力: {row.get('what')}——{row.get('why')}", _mark(row), PLAN_NODE, keys))
    saved = face_marks(place)
    recorded = intake.get(policy.RECORDED_KEY) or []
    for j, f in enumerate((review or {}).get("faces") or []):
        if not isinstance(f, dict) or f.get(converge.HELD_MARK):
            continue
        m = _mark(_joined(f, _at(saved, j)))
        if f.get("kind") in files.HUMAN_FACE_KINDS and not policy.unrecorded(f, m, recorded):
            rows.append((f["kind"], f"事前審査の穴 [{f['kind']}] {f.get('key')}: {f.get('why')}", m, REVIEW_NODE,
                         [k for k in f.get("unit_keys") or [] if isinstance(k, str)]))
    return rows


def _design_rows(place) -> list:
    """構造の目の行（控えが無い・落ちた周は []）"""
    state = structmark.read(pathlib.Path(place) / structmark.COPY_FILE)
    if not state or state.get("status") != "ok":
        return []
    try:
        return structmark.rows(state.get("design_file") or "")
    except ValueError:
        return []


def _world_rows(place) -> dict | None:
    """{類の id: 世界の解の行}（段が行を出した run だけ。控えが無い・落ちた・読めない run は None＝今どおりの軸）"""
    got = worldmark.stage_rows(pathlib.Path(place), worldmark.COPY_STATE)
    return None if got is None else {r["class_id"]: r for r in got}


def _world_answers(b) -> list:
    """[(項目の番号（1 始まり）, 答え)]: 修正案の欄 structure の世界の解の答え（控えが無い・読めない周は []）"""
    try:
        fields = planmarks.read(b)
    except Exception:   # 控えの形の崩れは入口と支度が止める（ここは照らさない）
        return []
    out = []
    for n, f in enumerate(fields or [], 1):
        for a in (f.get("structure") if isinstance(f, dict) and isinstance(f.get("structure"), list) else []):
            if isinstance(a, dict) and isinstance(a.get(worldmark.ANSWER_KEY), str):
                out.append((n, a))
    return out


def _cite_check(place, intake: dict):
    """（決め手の文 → 出どころの誤りの 1 文（無ければ ""）の口, 依頼のファイル, 依頼の解き方の並び, 作業ツリーの根）。出どころの照らしは
    cite.sources_problem（依頼の引用は port request の本文と照らす）。作業ツリーの外で引いてよい根は依頼のファイルと place の親
    （run の中の指示書・判定を絶対パスで引ける）。依頼のファイルと依頼の解き方（worldmark.means_of）は世界の解の外れの決め手に
    ならない物"""
    req = str(intake.get("request_file") or "")
    quoted = str(intake.get("request") or "")
    try:
        quoted += "\n" + json.dumps(json.loads(quoted), ensure_ascii=False) if quoted else ""   # \u の逃がしを解いた字でも引ける
    except ValueError:
        pass
    repo = intake.get("cwd") or "."
    roots = [r for r in (req, str(pathlib.Path(place).resolve().parent)) if r]

    def cite_ok(text):
        return cite.sources_problem(text, repo, roots, quoted)
    return cite_ok, req, worldmark.means_of(pathlib.Path(place), worldmark.COPY_MEANS), repo


def _answered_rows(b) -> set | None:
    """修正案の欄 structure に答えのある汚れる行の単位（控えが読めなければ None＝照らさない。受け付けが欠けを拒む）"""
    try:
        fields = planmarks.read(b)
    except Exception:   # 控えの形の崩れは入口と支度が止める（ここは照らさない）
        return None
    if fields is None:
        return None
    return {r.get("row") for f in fields if isinstance(f, dict) for r in f.get("structure") or [] if isinstance(r, dict)}


def axis_reasons(place, intake: dict, b, mark: dict, units) -> dict:
    """4 つの軸（AXES）ごとの揃わない訳の並び {軸: [訳]}（全部の軸を持つ。今の gatemarks.axis_reasons）"""
    out = {axis: [] for axis in AXES}
    decided_by = str(mark.get("decided_by") or "").strip()
    if not decided_by or str(mark.get("undecided_because") or "").strip():
        out["obvious"].append(gatemarks.NOT_DECIDED)
    elif problem := _cite_check(place, intake)[0](decided_by):
        out["obvious"].append(problem)
    if mark.get("fences"):
        out["not_overkill"].append(gatemarks.FENCED.format(fences="・".join(map(str, mark["fences"]))))
    # 世界の解の段の行の在る run の世界の解の外れは world_items の行が聞く（ここでは見ない）
    if _world_rows(place) is None and not str(mark.get("world") or "").strip() and not cite.URL.search(decided_by):
        out["world"].append(gatemarks.NO_WORLD)
    ups = {r.get("unit_id") for r in _design_rows(place) if r.get("route") == structmark.ROUTE_UP}
    hit = sorted(set(units) & ups)
    if hit:
        out["clean"].append(f"構造の目が人に上げた単位（{'・'.join(hit)}）に当たる")
    dirty = structmark.dirty(pathlib.Path(place) / structmark.COPY_FILE)
    answered = _answered_rows(b)
    if answered is not None:
        miss = sorted(k for k in units if k in dirty and k not in answered)
        if miss:
            out["clean"].append(f"構造の目が汚れると見た単位（{'・'.join(miss)}）に修正案の答えが無い")
    outside = sorted(set(units) - converge.planned_units((intake.get("plan") or {}).get("plan")))
    if outside:
        out["not_overkill"].append(f"修正案の単位の外を名指す（{'・'.join(outside)}）")
    return out


def world_items(place, intake: dict, b) -> list:
    """世界の解の外れの行 [(項目の番号, 文, 決め手の欄の形, 揃わない訳の並び)]（控えの無い run・外れの無い案は []。今の
    gatemarks.world_items に項目の番号を足した物）"""
    world = _world_rows(place)
    if world is None:
        return []
    cite_ok, request_file, means, repo = _cite_check(place, intake)
    out = []
    for n, a in _world_answers(b):
        if a.get("follows") is True:
            continue
        row = world.get(a[worldmark.ANSWER_KEY]) or {"class_id": a[worldmark.ANSWER_KEY]}
        ok, why = worldmark.world_ok(a, row, request_file, means, cite_ok, repo)
        text = f"修正案 {n} の{worldmark.gate_line(row, a)}"
        out.append((n, text, {"decided_by": str(a.get("deviation") or ""), "world": worldmark.gate_line(row, a)},
                    [] if ok else [why]))
    return out


# ---------------------------------------------------------------- 返す事実
def asks(place, intake: dict, review: dict) -> list:
    """人に回しうる行（10.1）。形 plan も replan も同じ行を返す（使うかは line が決める）"""
    b = _board(place, intake, review)
    out = []
    for kind, text, mark, node, units in _gate_rows(place, intake, review):
        why = {axis: got for axis, got in axis_reasons(place, intake, b, mark, units).items() if got}
        out.append({"kind": kind, "node": node, "text": text, "units": units, "mark": mark,
                    "decided": gatemarks.decided(mark), "why": why})
    return out


def deviations(place, intake: dict, review: dict) -> list:
    """外れの行（10.2）: 修正案の欄 structure が世界の解の行から外れると答えた行と決め手の照らし、独立設計との構造の食い違い・
    対の無い仕組みの穴"""
    b = _board(place, intake, review)
    out = [{"source": "world", "item": n, "text": text, "mark": mark, "why": why}
           for n, text, mark, why in world_items(place, intake, b)]
    heads = (design.DRIFT_HEAD, design.UNPAIRED_HEAD)
    out += [{"source": "design", "key": f.get("key"), "kind": f.get("kind"), "why": f.get("why")}
            for f in (review or {}).get("faces") or []
            if isinstance(f, dict) and isinstance(f.get("why"), str) and f["why"].startswith(heads)]
    return out


def _faces_of(row: dict, review: dict, rows: list) -> list:
    """事前審査の穴のうち直した項目 row の分: unit_keys が項目の単位と重なる行と、どの直した項目とも重ならない行
    （今の boardview._faces_of）"""
    mine = set(row.get("units") or [])
    every = set().union(*(set(r.get("units") or []) for r in rows)) if rows else set()
    out = []
    for f in (review or {}).get("faces") or []:
        keys = {str(k) for k in f.get("unit_keys") or []} if isinstance(f, dict) else set()
        if keys & mine or not keys & every:
            out.append(f)
    return out


def replan(place, intake: dict, review: dict) -> list:
    """形 replan の直した項目ごとの事実（10.3）: 約束の欄の変化・人に回す種類の穴・範囲を広げただけか（約束の欄が変わり、人に回す穴が
    無い時だけ計算する）。files.REPLAN に同じ行を書く。聞くか（ask）は line が決める（無人の run かは line の事実）"""
    rows = [r for r in intake.get("replan_items") or [] if isinstance(r, dict)]
    out = []
    for row in rows:
        human = [{"key": f.get("key"), "kind": f.get("kind"), "why": f.get("why")}
                 for f in _faces_of(row, review, rows) if isinstance(f, dict) and f.get("kind") in files.HUMAN_FACE_KINDS]
        old, new = replanlib.bare(row["old"]), replanlib.bare(row["new"])
        changed = planmarks.contract_diff(old, new)
        out.append({"item": row["item"], "units": list(row.get("units") or []), "contract_changed": changed, "human": human,
                    "widened": planmarks.widened(old, new) if changed and not human else None})
    jsonfile.write(pathlib.Path(place) / files.REPLAN, out, indent=2)
    return out
