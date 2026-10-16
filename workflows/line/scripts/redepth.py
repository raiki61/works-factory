# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""直した後に深さを上げ直す節 redepth（docs/design.md の「メイングラフ」の「順と承認ノード」の 7 の後。元 works/darkfactory/lib/depth.py:302 raise_）。

計画の深さを、案の直しが走れば直した案の単位の行で単位ごとに置き換え（1 回目の単位の行は残す。元は全部の単位の控えを残して
上げた）、修正の後の信号で標準へ上げる（lib/depth.py の raise_doc。下げない）。信号は、単位ごとに: 修正の段が止めた単位
（status が fixed でない単位）、run 全体に: 申し出が在る・答えていない問い（問いの台帳の問いごと。元 depth.signals の
gatemarks.pending。台帳が読めなければ上げる側に倒す）・案の直しが走った・再審が走った・run 全体の広さ（計画の allowed_paths と
修正の実際の差分のファイルの和集合とテストの本数。depth.run_wide。軽量の名指しでも上げる）・修正の後の 3 つの事実
（修正の差分が頭の深さの役の引用した where のファイルの外に出た・TDD のループで修正役が拒まれた・修正役が範囲の相談をした。
fix_signals。理由の文は depth.late_signals）。どれも上げるだけで下げない。返り {depth: [{unit_id, depth, why}],
skip_optional: 省く理由の文（run の頭の深さの段が省く物を持ち、単位がどれも軽量の時だけ。depth.skip_reason。ほかは空）, raised,
counted: run の広さの数えと起点の 1 行（fix_signals の隣の控えが無い訳を「／」で添える）, stop_reason}。
例外の時は止めの理由 works:line-script を返し、試験の関門から先は飛ぶ（深さの分からない差分を目に通さない）。

入力（with:）: depth・replan_depth（`{from, if_skipped: null}`）・head_depth（run の頭の深さの段の語）・units・conflicts・plan・diff（fixed の返り）・judgment（judged の返り）・
start（始めの記録）・answer（修正前の関所の答え）・ties_judgment（1 回目の判定。結びの隣のファイル）・replanned・rejudged（after-fix の返り）
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import changemap
    import consult
    import depth as depthlib
    import fixbeside
    import gatemarks
    import headdepth
    import startrec

PLAN_ORIGIN = "計画の allowed_paths"   # 元 depth.PLAN_ORIGIN（修正の差分を読めない時の数えの起点）


def _doc(ptr):
    return json.loads(boundary.resolve(ptr).read_text(encoding="utf-8"))


def pending_signals(judgment, start, answer, ties_judgment) -> list:
    """答えていない問いの信号（問いの台帳の問いごと。依頼の answers と修正前の関所の答えが答えた問いは数えない）。判定が無ければ空、
    台帳が読めなければ読めない訳の 1 行（上げる側に倒す）"""
    if judgment is None:
        return []
    try:
        b = gatemarks.ledger_at(boundary.resolve(judgment), startrec.load(boundary.resolve(start)) if start is not None else None, answer,
                                boundary.resolve(ties_judgment) if ties_judgment is not None else None)
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


def wide_signals(plan, diff, keys) -> tuple:
    """(run 全体の広さの信号, 数えた数と起点の 1 行)。修正の差分を読めなければ計画の allowed_paths だけで数え、起点にそう書く"""
    items = _plan_items(plan)
    try:
        touched = _diff_paths(diff)
        origin = f"修正の差分 {diff['path']}"
    except READ_ERRORS as error:
        touched, origin = [], f"{PLAN_ORIGIN}（修正の差分を読めない: {type(error).__name__}）"
    wide, paths = depthlib.run_wide(items, keys, touched)
    return wide, f"触るファイル {paths} 個（起点: {origin}）"


NO_LATE_RECORD = "修正の後の信号の控えが無い（{name}）——範囲の相談を数えていない"
LATE_UNREAD = "修正の後の信号の控えが読めない（{why}）"


def fix_signals(plan, diff, ties_judgment, keys) -> tuple:
    """(修正の後の 3 つの事実の信号, counted に添える訳の並び)。事実の言い方は depth.late_signals、引用の外の差分は depth.outside_cited:
    引用の外の差分は diff の触るファイルを、1 回目の判定（ties_judgment）の隣の頭の深さの控えの where のファイル（headdepth.cited_files）と比べ、
    TDD の拒否と範囲の相談は diff の隣の TDD の輪の状態 tdd-<k>/state.json と accept-trace.json の行を lib/fixbeside.py の late_records で読む。
    diff が null（直す物が無い周）・指し札が解けない時は何も足さず訳も添えない。控えの扱いは 1 つの決まり: 受け付けの行が無い時は
    上げずに訳を添え（NO_LATE_RECORD。黙らない）、在るのに読めない・{error}・形が違う時だけ LATE_UNREAD の信号で上げる側へ倒す。
    TDD の輪の状態が無い置き場は輪が走っていない（本物の run で TDD の前に止まった run は単位が止めた単位として既に上がる）。
    判定の隣に控えが無い・where の無い run は引用の外を持たない"""
    if diff is None:
        return [], []
    try:
        folder = boundary.resolve(diff).parent
    except READ_ERRORS:
        return [], []
    try:
        touched = _diff_paths(diff)
    except READ_ERRORS:
        touched = []
    try:
        cited = headdepth.cited_files(headdepth.read(boundary.resolve(ties_judgment).parent)) if ties_judgment is not None else []
    except READ_ERRORS:
        cited = []
    got = fixbeside.late_records(folder)
    signals = depthlib.late_signals(outside=depthlib.outside_cited(_plan_items(plan), keys, touched, cited), refused=got["refused"],
                                    consulted=consult.consulted_units(got["trace"] or []))
    return ([*signals, *(LATE_UNREAD.format(why=why) for why in got["unread"])],
            [NO_LATE_RECORD.format(name=name) for name in got["missing"]])


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
    wide, counted = wide_signals(value("PLAN"), value("DIFF"), keys)
    late, missing = fix_signals(value("PLAN"), value("DIFF"), value("TIES_JUDGMENT"), keys)
    pending = pending_signals(value("JUDGMENT"), value("START"), value("ANSWER"), value("TIES_JUDGMENT"))
    return {"planned": planned, "replanned_depth": replanned_depth, "units": boundary.items(os.environ.get("INPUTS_UNITS")),
            "conflicts": boundary.items(os.environ.get("INPUTS_CONFLICTS")), "signals": [*pending, *wide, *late],
            "replanned": boundary.flag(os.environ.get("INPUTS_REPLANNED")), "rejudged": boundary.flag(os.environ.get("INPUTS_REJUDGED")),
            "counted": counted + "".join(f"／{why}" for why in missing), "head": os.environ.get("INPUTS_HEAD_DEPTH", "")}


def compute() -> dict:
    got = from_env()
    return redepth(got["planned"], got["replanned_depth"], got["units"], got["conflicts"], got["signals"],
                   replanned=got["replanned"], rejudged=got["rejudged"], counted=got["counted"], head=got["head"])


def fallback(reason: str) -> dict:
    return {"depth": [], "skip_optional": "", "raised": [f"深さを上げ直せなかった（{reason}）"], "counted": "",
            "stop_reason": boundary.LINE_SCRIPT}


if __name__ == "__main__":
    boundary.run(compute, fallback)
