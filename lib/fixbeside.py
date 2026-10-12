"""修正のブロックの返り diff の隣の約束のファイル（docs/design.md の「ブロックの返りの約束」の隣のファイル）の書き手と読み手。

書き手は修正の返す節（write。止めた時は empty で訳つきの空の形）。読み手は最後の関所と報告（read で読み、行の口で文にする）。
返りの欄は増やさず、diff の指し札の先と同じフォルダ（修正の段ごとの置き場）に置く。組の子の run は子の置き場に書くので、子の
結果（fixboard.group_result）の欄 handoffs・closure・claimed・accept_trace で親へ運び、親の置き場の分（裁定の後の修正の段）と合わせる。

- HANDOFFS_FILE: [{unit_key, accepted}]。修正役が壊すと分かって通した理由（返答の changes[].breaks.accepted。空白だけは除く）
- CLOSURE_FILE: {rows: [閉鎖の表の行（querytest.save_closure の行）], claimed: [修正役が changes に載せた単位の key]}
- DELTA_HOLES_FILE: {ties: {"1": [名札（holeties.tie の行）] か組めない訳の字, "2": …}, handled: {"1": [手直しの handled の行], "2": …}}
- LENSES_FILE: {summary: lens.summary の返り, lines: lens.report_lines の返り}
- ACCEPT_TRACE_FILE: {rows: [受け付けの trace の行（trace_ops の op の行）]}
- leftovers.REMOVED_FILE（fix-removed.json）: clean が消したパス（書き手は修正の節 clean。読みは leftovers.removed）
どのファイルも、書けなかった・組めなかった時は {"error": 訳} を置き、読み手は訳を名指す（0 件に見せない）。

- handoffs_of(reply)・claimed_of(reply)・trace_rows(place)・closure_rows(place): 置き場と返答から欄を組む口（子の結果と親が使う）
- write(place, results, ruled_reply, *, items, plan_review, fix_reply)・empty(place, why): 書く
- read(folders): 段ごとの置き場（fix と 2 度目の修正）の全部を読み合わせた見え方
- handoff_lines・closure_lines・tests_left_lines・gates_lines・plan_ask_lines・branch_rows・always_rows・lens_lines・next_items:
  最後の関所と報告が同じ行を出す口（元 works/.shared/core/report.py の handoff_lines・branch_rows・gates_lines・plan_ask_lines・
  always_rows・lens_next_items・next_request の手直しの行、works/darkfactory/lib/line_edge.py の _ci_left）
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

HANDOFFS_FILE = "handoffs.json"
CLOSURE_FILE = "closure.json"
DELTA_HOLES_FILE = "delta-holes.json"
LENSES_FILE = "lenses.json"
ACCEPT_TRACE_FILE = "accept-trace.json"
FILES = (HANDOFFS_FILE, CLOSURE_FILE, DELTA_HOLES_FILE, LENSES_FILE, ACCEPT_TRACE_FILE)
import impact  # noqa: E402  （受け付けの trace の op の住処）

TESTS_OP, SKIPPED_OP, OVERFLOW_OP = impact.ACCEPT_TRACE_OP, impact.ACCEPT_GATES_SKIPPED_OP, impact.ACCEPT_OVERFLOW_OP
PASSES = (1, 2)                                  # 差分の審査と手直しの往復（refix.passes の番号）
HANDOFF_HEAD = "修正役が人に回した物（壊すと分かって通した理由 breaks.accepted。役だけで決めた代償なので人が確かめる）"
BRANCH_HEAD = {1: "差分の審査の穴の枝（機械が修正案の項目に結んだ名札。手直しの役にも同じ名札を渡した）",
               2: "2 回目の審査の穴の枝"}
HANDLED_HEAD = {1: "手直しの結果", 2: "2 回目の手直しの結果"}
ANOMALY_LINE = "仕組みの異常: 取れない（元は盤面の trace と包みの記録から数えた。docs/design.md の U6）"
LENS_WHERE = "レンズ"


def _one_line(text) -> str:
    return " ".join(str(text).split())


def _write(path: pathlib.Path, doc) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 欄を組む口（子の結果と親の書き手）
def handoffs_of(reply) -> list:
    """返答の changes[].breaks.accepted（空白だけの行は除く）を [{unit_key, accepted}] に。返答が無い・形が違えば []"""
    out = []
    for c in (reply.get("changes") if isinstance(reply, dict) else None) or []:
        breaks = c.get("breaks") if isinstance(c, dict) else None
        got = breaks.get("accepted") if isinstance(breaks, dict) else None
        if isinstance(got, str) and got.strip():
            out.append({"unit_key": str(c.get("unit_key")), "accepted": _one_line(got)})
    return out


def claimed_of(reply) -> list:
    """修正役が changes に載せた単位の key（申告。閉じたかは閉鎖の表が決める）"""
    return [str(c["unit_key"]) for c in (reply.get("changes") if isinstance(reply, dict) else None) or []
            if isinstance(c, dict) and isinstance(c.get("unit_key"), str)]


def trace_ops() -> tuple:
    """受け付けの trace の op（選んだ試験・赤緑を確かめずに受けた回・はみ出しの決着・範囲の相談）"""
    import conflict
    return TESTS_OP, SKIPPED_OP, OVERFLOW_OP, conflict.ASKED_OP


def trace_rows(place) -> list:
    """置き場の trace のうち受け付けの行（trace_ops）。trace が無ければ []。壊れた行は飛ばす"""
    import fixboard
    try:
        lines = (pathlib.Path(place) / fixboard.TRACE_FILE).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    ops, out = trace_ops(), []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("op") in ops:
            out.append(row)
    return out


def closure_rows(place) -> list:
    """置き場の閉鎖の表（querytest.CLOSURE_FILE）の行。無い・読めなければ []"""
    import querytest
    try:
        doc = _read(pathlib.Path(place) / querytest.CLOSURE_FILE)
    except (OSError, ValueError):
        return []
    return [r for r in (doc.get("rows") if isinstance(doc, dict) else None) or [] if isinstance(r, dict)]


# ---------------------------------------------------------------- 書く
def _ties(place, *, items, plan_review, fix_reply) -> tuple:
    """({往復: 名札 | 組めない訳}, {往復: handled の行})"""
    import fixboard
    import refix
    ties, handled = {}, {}
    for n in PASSES:
        try:
            ties[str(n)] = fixboard.hole_ties(place, n, items=items, plan_review=plan_review, fix_reply=fix_reply)
        except Exception as e:   # 名札は材料。組めない訳を置いて先へ（元 report._ties）
            ties[str(n)] = f"{type(e).__name__}: {_one_line(e)}"
        out = fixboard.output(place, refix._pass(n)["fix"]) or {}
        handled[str(n)] = [h for h in out.get("handled") or [] if isinstance(h, dict)]
    return ties, handled


def _lenses(place) -> dict:
    import fixboard
    import lens
    import refix
    review = fixboard.out_file(place, refix._pass(1)["review"])
    review = review if review.is_file() else None
    return {"summary": lens.summary(place, review), "lines": lens.report_lines(place, review)}


def write(place, results, ruled_reply=None, *, items=None, plan_review=None, fix_reply=None) -> None:
    """置き場 place に 5 つのファイルを書く。results は戻せた組の子の結果（欄 handoffs・closure・claimed・accept_trace）、ruled_reply は
    裁定の後の修正役の返答（親の置き場の段。無ければ None）。items・plan_review・fix_reply は手直しの穴の名札の材料
    （fixboard.hole_ties の引数）。1 つのファイルが組めなくても、ほかは書く（組めない物は {"error": 訳}）"""
    place = pathlib.Path(place)
    results = [r for r in results or [] if isinstance(r, dict)]

    def put(name, build):
        try:
            doc = build()
        except Exception as e:   # 隣のファイルは材料。組めない訳を置き、返す節は落とさない
            doc = {"error": f"{type(e).__name__}: {_one_line(e)}"}
        _write(place / name, doc)

    def closure():
        rows = {}
        for r in [*(x for res in results for x in res.get("closure") or []), *closure_rows(place)]:
            if isinstance(r, dict):
                rows[r.get("unit_key")] = r   # 裁定の後の段の表がその単位の 1 回目の表を上書きする
        claimed = [*(k for res in results for k in res.get("claimed") or []), *claimed_of(ruled_reply)]
        return {"rows": list(rows.values()), "claimed": list(dict.fromkeys(claimed))}

    def holes():
        ties, handled = _ties(place, items=items, plan_review=plan_review, fix_reply=fix_reply)
        return {"ties": ties, "handled": handled}
    put(HANDOFFS_FILE, lambda: [*(h for res in results for h in res.get("handoffs") or [] if isinstance(h, dict)),
                                *handoffs_of(ruled_reply)])
    put(CLOSURE_FILE, closure)
    put(DELTA_HOLES_FILE, holes)
    put(LENSES_FILE, lambda: _lenses(place))
    put(ACCEPT_TRACE_FILE, lambda: {"rows": [*(t for res in results for t in res.get("accept_trace") or [] if isinstance(t, dict)),
                                             *trace_rows(place)]})


def empty(place, why: str) -> None:
    """止めた・返りを組めなかった時の空の形（どのファイルも {"error": why}。在る物は上書きしない）"""
    place = pathlib.Path(place)
    for name in FILES:
        if not (place / name).is_file():
            _write(place / name, {"error": why})


# ---------------------------------------------------------------- 読む
def read(folders) -> dict:
    """段ごとの置き場（diff の指し札の先のフォルダ。fix と 2 度目の修正の順）を読み合わせる。返り {handoffs, closure, claimed, ties,
    handled, lenses, trace, removed, unread, folders}。ties・handled・lenses・removed は段ごとの並び [(フォルダ, 中身)]。読めない・無い
    ファイルと {"error"} は unread に訳（0 件に見せない）"""
    import leftovers
    got = {"handoffs": [], "closure": {}, "claimed": [], "ties": [], "handled": [], "lenses": [], "trace": [], "removed": [],
           "unread": [], "folders": []}
    for folder in folders or []:
        folder = pathlib.Path(folder)
        got["folders"].append(folder)
        docs = {}
        for name in FILES:
            try:
                doc = _read(folder / name)
            except FileNotFoundError:
                got["unread"].append(f"修正の控え {folder / name} が無い")
                continue
            except (OSError, ValueError) as e:
                got["unread"].append(f"修正の控え {folder / name} が読めない（{type(e).__name__}: {_one_line(e)}）")
                continue
            if isinstance(doc, dict) and "error" in doc:
                got["unread"].append(f"修正の控え {folder / name} を組めなかった（{_one_line(doc['error'])}）")
                continue
            docs[name] = doc
        got["handoffs"] += [h for h in docs.get(HANDOFFS_FILE) or [] if isinstance(h, dict)]
        closure = docs.get(CLOSURE_FILE) or {}
        for r in closure.get("rows") or []:
            if isinstance(r, dict):
                got["closure"][r.get("unit_key")] = r   # 2 度目の修正の段の表がその単位の前の表を上書きする
        got["claimed"] += [k for k in closure.get("claimed") or [] if isinstance(k, str) and k not in got["claimed"]]
        holes = docs.get(DELTA_HOLES_FILE) or {}
        got["ties"].append((folder, holes.get("ties") or {}))
        got["handled"].append((folder, holes.get("handled") or {}))
        if LENSES_FILE in docs:
            got["lenses"].append((folder, docs[LENSES_FILE]))
        got["trace"] += [r for r in (docs.get(ACCEPT_TRACE_FILE) or {}).get("rows") or [] if isinstance(r, dict)]
        got["removed"].append((folder, leftovers.removed(folder)))
    got["closure"] = list(got["closure"].values())
    return got


# ---------------------------------------------------------------- 行の口（最後の関所と報告が同じ行を出す）
def handoff_lines(got: dict) -> list:
    """修正役が人に回した物（1 件 1 行。元 report.handoff_lines）"""
    return [f"{h.get('unit_key')}: 壊すと分かって通した——{_one_line(h.get('accepted'))}" for h in got["handoffs"]]


def closure_lines(got: dict, *, mismatched_only: bool = False, stuck_only: bool = False) -> list:
    """閉鎖の数え直しの行（querytest.closure_lines。既定の列は表に行の無い申告の単位も名指す）"""
    import querytest
    return querytest.closure_lines(got["closure"], mismatched_only=mismatched_only, stuck_only=stuck_only,
                                   claimed=() if (mismatched_only or stuck_only) else got["claimed"])


def not_closed(got: dict) -> list:
    """閉鎖の表で閉じていない（closed が偽の）単位の key（元 report._closed_units の裏）"""
    return [str(r.get("unit_key")) for r in got["closure"] if r.get("closed") is False]


def _left(got: dict, field: str) -> list:
    return list(dict.fromkeys(t for row in got["trace"] if row.get("op") == TESTS_OP for t in row.get(field) or []
                              if isinstance(t, str)))


def tests_left_lines(got: dict) -> list:
    """受け付けが手元で回さなかった試験・最後のテストの段に任せた試験・遠くて読み切れないファイル（元 line_edge._final_text の
    _ci_left の 3 つ。字下げの行は内訳）"""
    out = []
    left = _left(got, "ci_left")
    if left:
        out.append(f"修正の受け付けが手元で回さなかった試験（{len(left)} 件。run はその緑を確かめない——取り込みの前に人が回すか CI で確かめる）:")
        out += [f"  - {t}" for t in left]
    final = _left(got, "final_left")
    if final:
        out.append(f"修正の受け付けが変更に直には関わらないので回さず、最後のテストの段に任せた試験（{len(final)} 件。上のテストの"
                   "一式に入る物はそこで確かめた。入らない物は CI で確かめる）:")
        out += [f"  - {t}" for t in final]
    far = _left(got, "final_far")
    if far:
        out.append(f"修正の受け付けが一式を回す理由にせず、最後のテストの段に任せた変更から遠く、どの試験に関わるか読み切れないファイル（{len(far)} 件）:")
        out += [f"  - {t}" for t in far]
    return out


def gates_lines(got: dict) -> list:
    """事後の関門の束が赤緑を確かめずに受けた回（回の数と理由。同じ理由は 1 度）と、はみ出しを相談で認めた・戻した行・関所の条件の
    相談で認めた新しいテスト・守りのテスト（元 report.gates_lines）"""
    out = []
    rows = [r for r in got["trace"] if r.get("op") == SKIPPED_OP]
    if rows:
        whys = list(dict.fromkeys(w for r in rows for w in r.get("why") or [] if isinstance(w, str)))
        out.append(f"事後の関門の束: 受け付け {len(rows)} 回が受け入れのテストの赤緑を確かめずに通した（理由: {' / '.join(whys)[:600]}）")
    agreed, undone, guards, gated = [], [], [], []
    for r in (r for r in got["trace"] if r.get("op") == OVERFLOW_OP):
        agreed += [f"相談 {i}" for i in r.get("agreed") or [] if f"相談 {i}" not in agreed]
        gated += [g for g in r.get("gate_tests") or [] if isinstance(g, str) and g not in gated]
        undone += [x for x in r.get("reverted") or [] if isinstance(x, dict) and x not in undone]
        guards += [g for g in r.get("guards") or [] if isinstance(g, str) and g not in guards]
    if agreed:
        out.append(f"はみ出しを相談で認めた: {'・'.join(agreed)}（範囲に入れ、新しいテストは赤緑を確かめた）")
    if gated:
        out.append(f"人の関所の条件の相談で認めた新しいテスト: {'・'.join(gated)}（今の木に在る物を赤緑か守りで確かめた）")
    out += [f"守りのテストを認めた（今の木で緑だけを確かめた）: {g}" for g in guards]
    for x in undone:
        what = "・".join([*(x.get("paths") or []), *(x.get("tests") or []), *(x.get("new_tests") or [])]) or "（無し）"
        out.append(f"はみ出しを戻した（相談で認められなかった・聞けなかった・合意のテストが赤緑で落ちた）: {what}"
                   f"（控えの差分 {x.get('patch') or '（無し）'}）")
    return out


def plan_ask_lines(got: dict) -> list:
    """範囲の相談の 1 問 1 答（元 report.plan_ask_lines）: 1 行目に回数と答えごとの数、続けて 1 相談 1 行"""
    import conflict
    rows = [r for r in got["trace"] if r.get("op") == conflict.ASKED_OP]
    if not rows:
        return []
    kinds = collections.Counter(r.get("decision") if r.get("status") == "answered" else r.get("status") for r in rows)
    out = [f"範囲の相談: {len(rows)} 回（" + "・".join(f"{k} {n}" for k, n in kinds.items()) + "）"]
    for r in rows:
        head = f"  - 相談 {r.get('id')}（項目 {r.get('item')}）: "
        if r.get("status") != "answered":
            why = r.get("why_refused") or r.get("why_unavailable") or " / ".join(r.get("notes") or [])
            out.append(f"{head}{r.get('status')}——{str(why)[:300]}")
            continue
        granted = [*(r.get("granted_paths") or []), *(r.get("granted_tests") or []),
                   *(f"新しいテスト {g.get('id')}（{g.get('red_kind')}）" for g in r.get("granted_new_tests") or [] if isinstance(g, dict))]
        lifted = [h for h in r.get("overrode_out_of_scope") or [] if isinstance(h, dict)]
        kept = [h for h in r.get("out_of_scope") or [] if isinstance(h, dict) and str(h.get("item")) == str(r.get("item"))]
        oos = ("・out_of_scope を外した: " + "・".join(f"{h.get('path')}（項目 {r.get('item')} の out_of_scope の {h.get('glob')}）"
                                                    for h in lifted) if lifted else
               "・out_of_scope は外したまま: " + "・".join(str(h.get("path")) for h in kept)
               if kept and r.get("decision") != "allow" else "")
        out.append(f"{head}{r.get('decision')}" + (f"（{'・'.join(granted)}）" if granted else "") + oos
                   + f"——{str(r.get('reason') or '')[:300]}")
    return out


def _note(t: dict) -> str:
    import holeties
    return holeties.note(t)


def branch_rows(got: dict) -> list:
    """手直しの往復ごとの穴の枝の名札（件数の 1 行 holeties.count_line と穴ごとの行。組めなければ訳の 1 行）と手直しの結果（handled
    の行）。元 report.branch_rows と line_edge._final_text の手直しの結果。穴も手直しも無ければ []"""
    import gatemarks
    import holeties
    rows = []
    for (_, ties), (_, handled) in zip(got["ties"], got["handled"]):
        for n in PASSES:
            t = ties.get(str(n))
            if isinstance(t, str):
                rows.append(f"{BRANCH_HEAD[n]}: 組めない（{t}）")
            elif t:
                rows.append(f"{BRANCH_HEAD[n]}: {holeties.count_line(t)}")
                rows += [f"  - {x}" for x in holeties.lines(t)]
            h = handled.get(str(n)) or []
            if h:
                rows.append(f"{HANDLED_HEAD[n]}（{len(h)} 件）:")
                rows += [f"  - {x.get('key')}: {gatemarks.HANDLED_WORDS.get(x.get('handled'), '')}（{x.get('handled')}）——{_one_line(x.get('how') or '')}"
                         for x in h]
    return rows


def lens_lines(got: dict) -> list:
    """報告の「未確認のレンズ」の節の行（lens.report_lines の控え。段ごと）"""
    out = []
    for folder, doc in got["lenses"]:
        out += [str(x) for x in doc.get("lines") or []]
    return out


def always_rows(got: dict) -> list:
    """clean が消したファイル・レンズ・仕組みの異常の行（0 件でも、走らせていない・読めないを 0 件と分ける。元 report.always_rows の
    頭の 3 つ。残りの行は呼び手が持つ）。字下げの行は内訳"""
    rows = []
    for folder, gone in got["removed"]:
        where = f"（{folder.name}）"
        if not gone["readable"]:
            rows.append(f"clean が消したファイル{where}: 読めない（{_one_line(gone['reason'])}）")
        elif not gone["ran"]:
            rows.append(f"clean が消したファイル{where}: 走らせていない（fix-removed.json が無い。clean の前に止まった）")
        else:
            rows.append(f"clean が消したファイル{where}: {gone['count']} 本")
            rows += [f"  - {n}" for n in gone["paths"]]
    if not got["removed"]:
        rows.append("clean が消したファイル: 走らせていない（修正の段が無い run）")
    import lens
    seen = False
    for folder, doc in got["lenses"]:
        s = doc.get("summary") if isinstance(doc.get("summary"), dict) else None
        where = f"（{folder.name}）"
        if s is None:
            continue
        seen = True
        if not s.get("readable"):
            rows.append(f"レンズ{where}: 読めない（{_one_line(s.get('reason'))}）——どのレンズが見たかを確かめられない")
        elif not s.get("ran"):
            rows.append(f"レンズ{where}: 走らせていない（控えが無い）")
        else:
            rows.append(f"{lens.count_line(s)}{where}")
            for r in s.get("rows") or []:
                taken = "調べていない" if r.get("adopted") is None else f"採った {r['adopted']}・採らなかった {r['not_adopted']}"
                rows.append(f"  - {r.get('lens')}: {taken}・形の誤りで捨てた {r.get('dropped')}（出した発見 {r.get('findings')}）")
            rows += [f"  - 落ちたレンズ {f.get('lens')}（再実行の要あり）: {_one_line(f.get('reason'))}" for f in s.get("failed") or []]
    if not seen:
        rows.append("レンズ: 控えが無い（修正の段が無い run か、控えが読めない。下の読めなかった控えの訳）")
    rows.append(ANOMALY_LINE)
    return rows


def next_items(got: dict) -> list:
    """次の依頼の行 [{where, text}]（元 report.next_request の手直しの行と lens_next_items）: 手直しが declared で残した穴と、
    2 回目の手直しが fixed と言った穴（3 回目の審査が無いので検算が要る。どちらも枝の名札を添える）、落ちたレンズを「再実行の要あり」、
    レンズの控えが読めなければそれも同じ言い方で"""
    items = []
    for (_, ties), (_, handled) in zip(got["ties"], got["handled"]):
        for n in PASSES:
            t = ties.get(str(n))
            tags = {x["key"]: _note(x) for x in t if isinstance(x, dict) and "key" in x} if isinstance(t, list) else {}
            for h in handled.get(str(n)) or []:
                if not isinstance(h.get("key"), str):
                    continue
                where = (h.get("files") or [None])[0] or h["key"]
                tag = f"（枝: {tags[h['key']]}）" if h["key"] in tags else ""
                if h.get("handled") == "declared":
                    items.append({"where": str(where), "text": f"{h['key']}（手直しが declared で残した穴: {h.get('how') or ''}）{tag}"})
                elif h.get("handled") == "fixed" and n == PASSES[-1]:
                    items.append({"where": str(where),
                                  "text": f"{h['key']}（手直し 2 回目が fixed と言ったが、3 回目の審査は無い——検算が要る: {h.get('how') or ''}）{tag}"})
    for folder, doc in got["lenses"]:
        s = doc.get("summary") if isinstance(doc.get("summary"), dict) else {}
        if s and not s.get("readable"):
            items.append({"where": LENS_WHERE, "text": f"レンズの控えが読めない——再実行の要あり: {_one_line(s.get('reason'))}"})
            continue
        items += [{"where": f"{LENS_WHERE} {f.get('lens')}",
                   "text": f"{f.get('lens')}（再実行の要あり: 落ちて観点を誰も見ていない。理由: {_one_line(f.get('reason'))}）"}
                  for f in s.get("failed") or [] if isinstance(f, dict)]
    return items
