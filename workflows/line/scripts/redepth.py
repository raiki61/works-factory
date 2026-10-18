# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""直した後に深さを上げ直す節 redepth（docs/design.md の「メイングラフ」の「順と承認ノード」の 7 の後。元 works/darkfactory/lib/depth.py:302 raise_）。

計画の深さを、案の直しが走れば直した案の単位の行で単位ごとに置き換え（1 回目の単位の行は残す。元は全部の単位の控えを残して
上げた）、修正の後の信号で標準へ上げる（lib/depth.py の raise_doc。下げない）。信号は、単位ごとに: 修正の段が止めた単位
（status が fixed でない単位）、run 全体に: 申し出が在る・答えていない問い（問いの台帳の問いごと。元 depth.signals の
gatemarks.pending。台帳が読めなければ上げる側に倒す）・案の直しが走った・再審が走った と、修正のサブグラフの中の上げ直し
（fixboard.redepth）と同じ数えの信号（修正の差分が頭の深さの引用した where の外に出た・TDD のループで修正役が
拒まれた・範囲の相談をした・直さずに残すと答えた事前審査の block〔入力 plan_declared〕。数えと控えの扱いは lib/latedepth.py の
signals で、fix_signals は指し札を解いて渡すだけ）。どれも上げるだけで下げない。返り {depth: [{unit_id, depth, why}],
skip_optional: 省く理由の文（run の頭の深さの段が省く物を持ち、単位がどれも軽量の時だけ。depth.skip_reason。ほかは空）, raised,
counted: run の広さの数え（記録だけで上げる信号にしない）と起点の 1 行（信号の控えが無い訳を「／」で添える。latedepth.signals）, stop_reason}。
例外の時は止めの理由 works:line-script を返し、試験の関門から先は飛ぶ（深さの分からない差分を目に通さない）。

入力（with:）: depth・replan_depth（`{from, if_skipped: null}`）・head_depth（run の頭の深さの段の語）・units・conflicts・plan・diff・records（fixed の返り）・judgment（judged の返り）・
start（始めの記録）・answer（修正前の関所の答え）・depth_record（1 回目の判定の頭の深さの控えのポインタ）・
answer_ties・materials（judged の返りの結びと素材の状態のポインタ）・replanned・rejudged（after-fix の返り）・plan_declared（fixed の返り）
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import changemap
    import depth as depthlib
    import fixbeside
    import gatemarks
    import latedepth
    import startrec


def _doc(ptr):
    return json.loads(boundary.resolve(ptr).read_text(encoding="utf-8"))


def pending_signals(judgment, start, answer, ties, materials) -> list:
    """答えていない問いの信号（問いの台帳の問いごと。依頼の answers と修正前の関所の答えが答えた問いは数えない）。判定が無ければ空、
    台帳が読めなければ読めない訳の 1 行（上げる側に倒す）"""
    if judgment is None:
        return []
    try:
        b = gatemarks.ledger_at(boundary.resolve(judgment), startrec.load(boundary.resolve(start)) if start is not None else None, answer,
                                ties_file=boundary.resolve(ties) if ties is not None else None,
                                materials_file=boundary.resolve(materials) if materials is not None else None)
        return [f"答えていない問い {q.get('key')}" for q in gatemarks.pending(b)]
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        return [f"問いの台帳が読めない（{type(error).__name__}）"]


READ_ERRORS = (OSError, ValueError, TypeError, AttributeError, KeyError)


def _plan_items(plan) -> list:
    """計画の欄（plan-fields.json の fields）。無い・読めない・形が違うなら空"""
    try:
        doc = _doc(plan) if plan is not None else {}
        items = doc.get("fields") if isinstance(doc, dict) else None
    except READ_ERRORS:
        items = None
    return items if isinstance(items, list) else []


def _diff_paths(diff) -> list:
    """修正の差分（diff の指し札）の触るファイル（changemap.split_diff）。読めなければ READ_ERRORS の例外"""
    return list(changemap.split_diff(boundary.resolve(diff).read_text(encoding="utf-8", errors="replace"))[0])


def touched_files(diff) -> tuple:
    """(修正の差分の触るファイル, 数えの起点の 1 行)。修正の差分を読めなければ空で、起点は計画の allowed_paths とその訳"""
    try:
        return _diff_paths(diff), f"修正の差分 {diff['path']}"
    except READ_ERRORS as error:
        return [], f"{latedepth.PLAN_ORIGIN}（修正の差分を読めない: {type(error).__name__}）"


def fix_signals(plan, diff, records, depth_record, keys, declared=()) -> tuple:
    """(修正の後の run の信号, counted)。数えと控えの扱いは latedepth.signals で、ここは with: の指し札を解くだけ: 信号の元は
    最後の修正の段（records の最後）の控えの欄を lib/fixbeside.py の late_records で読み、引用は 1 回目の判定の頭の深さの控え
    （depth_record のポインタ。解けなければ引用は無い）。diff が null（直す物が無い周）・指し札が解けない時は修正の段の元を渡さない"""
    try:
        boundary.resolve(diff)
    except READ_ERRORS:
        late = None
    else:
        late = fixbeside.late_records(records[-1] if isinstance(records, list) and records else None, boundary.resolve)
    try:
        head_record = boundary.resolve(depth_record) if depth_record is not None else None
    except READ_ERRORS:
        head_record = None
    touched, origin = touched_files(diff)
    return latedepth.signals(_plan_items(plan), keys, touched, origin=origin, head_record=head_record, late=late, declared=declared)


def merged(planned, replanned) -> list:
    """計画の深さの行を、直した案の深さの行で単位ごとに置き換えた並び（直した案だけに在る単位は後ろに足す）"""
    rows = {r["unit_id"]: r for r in planned or [] if isinstance(r, dict) and r.get("unit_id")}
    rows.update({r["unit_id"]: r for r in replanned or [] if isinstance(r, dict) and r.get("unit_id")})
    return list(rows.values())


def redepth(planned, replanned_depth, units, conflicts, signals, *, replanned: bool, rejudged: bool, head: str,
            counted: str = "") -> dict:
    rows = merged(planned if isinstance(planned, list) else [], replanned_depth if isinstance(replanned_depth, list) else [])
    doc = {"units": {r["unit_id"]: {"depth": r.get("depth"), "why": [r["why"]] if r.get("why") else []} for r in rows}, "raised": []}
    stopped = {u["unit_id"]: f"修正の段が止めた単位（{u.get('status')}）" for u in units or []
               if isinstance(u, dict) and u.get("unit_id") and u.get("status") != "fixed"}
    run = []
    if conflicts:
        run.append(f"申し出が在る（{len(conflicts)} 件）")
    run += list(signals)
    if replanned:
        run.append("案の直しが走った")
    if rejudged:
        run.append("再審が走った")
    raised = depthlib.raise_doc(doc, units=stopped, run=run)
    return {"depth": [{"unit_id": key, "depth": row["depth"], "why": " / ".join(row["why"])} for key, row in raised["units"].items()],
            "skip_optional": depthlib.skip_reason(raised, head), "raised": raised["raised"], "counted": counted, "stop_reason": ""}


def from_env() -> dict:
    def value(name):
        return boundary.value(os.environ.get(f"INPUTS_{name}"))
    planned, replanned_depth = value("DEPTH"), value("REPLAN_DEPTH")
    keys = [r["unit_id"] for r in merged(planned if isinstance(planned, list) else [],
                                        replanned_depth if isinstance(replanned_depth, list) else []) if r.get("unit_id")]
    late, counted = fix_signals(value("PLAN"), value("DIFF"), value("RECORDS"), value("DEPTH_RECORD"), keys,
                                declared=boundary.items(os.environ.get("INPUTS_PLAN_DECLARED")))
    pending = pending_signals(value("JUDGMENT"), value("START"), value("ANSWER"), value("ANSWER_TIES"), value("MATERIALS"))
    return {"planned": planned, "replanned_depth": replanned_depth, "units": boundary.items(os.environ.get("INPUTS_UNITS")),
            "conflicts": boundary.items(os.environ.get("INPUTS_CONFLICTS")), "signals": [*pending, *late],
            "replanned": boundary.flag(os.environ.get("INPUTS_REPLANNED")), "rejudged": boundary.flag(os.environ.get("INPUTS_REJUDGED")),
            "counted": counted, "head": os.environ.get("INPUTS_HEAD_DEPTH", "")}


def compute() -> dict:
    got = from_env()
    return redepth(got["planned"], got["replanned_depth"], got["units"], got["conflicts"], got["signals"],
                   replanned=got["replanned"], rejudged=got["rejudged"], counted=got["counted"], head=got["head"])


def fallback(reason: str) -> dict:
    return {"depth": [], "skip_optional": "", "raised": [f"深さを上げ直せなかった（{reason}）"], "counted": "",
            "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(compute, fallback)
