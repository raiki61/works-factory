"""事前審査の block の、盤面の無い見え方と書き先（docs/design/plan-review.md の 1.5。lib/boardview.py:153-303 の見え方の部分の写し）。

今の事前審査の部品（lib の converge・planmarks・design・gatemarks・policy と、この block の src/ に写した planblk の部分）は、盤面 b を
引数に取る形のまま在る。この block は盤面を持たないので、place（ports.place()）の上で今の盤面と同じ形の読むだけの見え方（view）と
書き先（place）を組んで、それらの関数に渡す。書き手が書いた控え（往復の記録の作業の写し plan-converge.json・却下の控え）は同じ
place に置き、見え方がそのまま読む。

- view(folder, inputs, review=None): 読むだけの見え方。inputs は入口が書いた intake.json の中身（src/steps.py の docstring の欄）
- place(folder): 書き先（converge の note_plan・note_answers が書く）
- rules: 見え方が b.rules で渡す物のうち、この block の部品が読む plan_review_output と HUMAN_FACE_KINDS だけ
- blank・EMPTY・_keys_once・plan_review_output: 返答の全体の照らし（元の名のまま）

写した元と違う所: record は units・process.precedents・process.diagnosis・process.recorded_policy だけを持つ（questions・materials・
human_items・purpose_review は承認ノードと独立設計の材料で、この block は読まない）。state.inputs は cwd・request・policy_md・
review_rev だけ（review_rev は intake.json の review_rev。policy_md は方針の写しのパス policy_copy）。state.outputs は判定の写し
judgment.json の名だけ（ライブラリの文書の節の写しが引く）。
"""
from __future__ import annotations

import copy
import datetime
import json
import pathlib
import types

import converge   # lib/
import policy     # lib/。RECORDED_KEY
from engine.util import Reject   # lib/graphloops/engine/util.py

from src import files

PLAN_NODE = files.PLAN_NODE
REVIEW_NODE = files.REVIEW_NODE

# 元 works/.shared/core/graphloops/rules/review-loop.py:467
EMPTY = ("なし", "無し", "ない", "無い", "特になし", "n/a", "none", "-", "未確認", "不明",
         "todo", "未実施", "未測定", "後で")


def blank(s, min_len):
    """役が埋める自由文が空同然か（表と長さの両方で見る。元 review-loop.py:480）"""
    t = (s or "").strip()
    return t.lower() in EMPTY or len(t) < min_len


def _keys_once(rows, label):
    """行の key が重複しないか（重複の文の一覧。元 review-loop.py:3067）"""
    seen, errs = set(), []
    for i, r in enumerate(rows):
        if r["key"] in seen:
            errs.append(f"{label}[{i}] の key が重複: {r['key'][:60]}")
        seen.add(r["key"])
    return errs


def plan_review_output(b, nid, out, item):
    """事前審査の穴は案の単位を指し、key は一意。穴も別案も無いなら faces_none を書く（元 review-loop.py:3096。out の unit_keys は単位の名に
    戻した物）。持つのは返答の全体の照らし（key の重複・案に無い単位・faces_none）だけ。穴の行ごとの照らし（方針の名指し・入口の穴の
    no_add・機械の欄を名指す block）は src/take.py の face_row_gaps"""
    planned = converge.planned_units((b.output_of_round(PLAN_NODE, b.round) or {}).get("plan"))
    rows = (out.get("faces") or []) + (out.get("shrink") or [])
    errs = _keys_once(rows, "faces・shrink")
    for r in rows:
        stray = [k for k in r["unit_keys"] if k not in planned]
        if stray:
            errs.append(f"{r['key'][:40]}: unit_keys {[str(k)[:40] for k in stray]} は修正案に無い")
    if not rows and blank(out.get("faces_none"), 20):
        errs.append("穴も別案も挙げないなら faces_none に何を確かめて無いと言えるかを書け")
    if errs:
        raise Reject(f"{nid}: " + "; ".join(errs))


rules = types.SimpleNamespace(HUMAN_FACE_KINDS=files.HUMAN_FACE_KINDS, plan_review_output=plan_review_output)


# ---------------------------------------------------------------- 見え方と書き先
def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _tracer(folder: pathlib.Path):
    def trace(op, **row):
        with open(folder / files.TRACE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": _now(), "op": op, **row}, ensure_ascii=False) + "\n")
    return trace


def place(folder) -> types.SimpleNamespace:
    """書き手（converge の note_plan・note_answers）の書き先: round（いつも 1）・dir・work(name)・trace(op, **row)。place folder の
    本物のファイルに書く"""
    d = pathlib.Path(folder)
    return types.SimpleNamespace(round=1, dir=d, work=lambda name: d / name, trace=_tracer(d))


def view(folder, inputs: dict, review: dict | None = None) -> types.SimpleNamespace:
    """読むだけの見え方。inputs は入口が置いた intake.json の中身、review は今の往復の受けた事前審査の返答。round はいつも 1
    （converge.read は控えの周が見え方の周と違うと控えを捨てるので、往復と案の直しを同じ周に積む）。木の関数が読みと書きを同じ b で
    行うので、work(name)・scope_root・trace は place の本物のファイルを指す"""
    d = pathlib.Path(folder)
    outs = {PLAN_NODE: inputs.get("plan"), REVIEW_NODE: review}
    names = list(inputs.get("names") or [])
    record = {"units": copy.deepcopy(inputs.get("units") or []),
              "process": {policy.RECORDED_KEY: copy.deepcopy(inputs.get(policy.RECORDED_KEY) or []),
                          "precedents": copy.deepcopy(inputs.get("precedents") or []),
                          "diagnosis": copy.deepcopy(inputs.get("diagnosis") or {})}}
    state = {"inputs": {"cwd": inputs.get("cwd") or ".", "request": inputs.get("request") or "",
                        "policy_md": inputs.get("policy_copy") or "", "review_rev": inputs.get("review_rev") or "HEAD"},
             "works": {}, "outputs": {"p2.diagnose": {"file": files.JUDGMENT}}}   # 判定の写し（lib_section の写しが引く）
    return types.SimpleNamespace(
        round=1, dir=d, scope="", scope_root=d, record=record, state=state, rules=rules,
        faces_schema={x: copy.deepcopy(((inputs.get("review_schema") or {}).get("properties") or {}).get(x) or {})
                      for x in ("faces", "shrink")},
        design_schema=copy.deepcopy(inputs.get("design_schema") or {}),
        work=lambda name: d / name, trace=_tracer(d),
        output_of_round=lambda node, rnd: copy.deepcopy(outs.get(node)) if rnd == 1 else None,
        latest_output=lambda node: None,
        pointer_rows=lambda node: {"pointers": [{"names": list(names)}]})
