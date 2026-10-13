"""修正のブロックの返り diff の隣の約束のファイル（docs/design.md の「サブグラフの出力の約束」の隣のファイル）のうち、閉鎖の表と
差分の審査の穴の名札の書き手と、diff の隣の控えの全部の読み手。

書き手は修正の出力ノード（write）。読み手は最後の承認ノードと報告（read で読み、行の口で文にする）。出力の欄は増やさず、diff の
ポインタの先と同じフォルダ（修正の段ごとの置き場）に置く。組の子の run は子の置き場に書くので、子の結果（fixboard.group_result）の
欄 closure・claimed で親へ運び、親の置き場の分（裁定の後の修正の段）と合わせる。

- CLOSURE_FILE: {rows: [閉鎖の表の行（querytest.save_closure の行）], claimed: [修正役が changes に載せた単位の key]}
- DELTA_HOLES_FILE: {ties: {"1": [名札（holeties.tie の行）] か組めない訳の字, "2": …}, handled: {"1": [手直しの handled の行], "2": …}}
どちらも、書けなかった・組めなかった時は {"error": 訳} を置き、読み手は訳を名指す（0 件に見せない）。
修正役が人に回した物（handoffs）と申告と数え直しが合わない単位（mismatched）は fix の出力の欄が正本で、ここでは読まない。
read が同じ diff の隣から一緒に読む物（書き手は fix のほかの所）:
- fixboard.ACCEPT_TRACE_FILE（accept-trace.json）: 受け付けの行の並び（選んだ試験の知らせ・赤緑を確かめずに受けた回・はみ出しの
  決着・範囲の相談。fixboard.accept_trace_rows）
- fixboard.LENSES_FILE（lenses.json）: レンズの集め役の事実 {collector: {ok, reason}}。レンズの数え（lens.summary）は置き場の
  lens.json と差分の審査の 1 回目の出力から読む時に数える
- leftovers.REMOVED_FILE（fix-removed.json）: clean が消したパス（読みは leftovers.removed）

- claimed_of(reply)・closure_rows(place): 子の結果と親が欄を組む口
- write(place, results, ruled_reply, *, items, plan_review, fix_reply): 書く
- read(folders): 段ごとの置き場（fix と 2 度目の修正）の全部を読み合わせた見え方
- closure_lines・not_closed・tests_left_lines・gates_lines・plan_ask_lines・branch_rows・always_rows・lens_lines・next_items:
  最後の承認ノードと報告が同じ行を出す口（元 works/.shared/core/report.py の branch_rows・gates_lines・plan_ask_lines・
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

import fixboard  # noqa: E402
import impact  # noqa: E402  （受け付けの trace の op の住処）
import oneline  # noqa: E402
import querytest  # noqa: E402

CLOSURE_FILE = "closure.json"
DELTA_HOLES_FILE = "delta-holes.json"
FILES = (CLOSURE_FILE, DELTA_HOLES_FILE)
TESTS_OP, SKIPPED_OP, OVERFLOW_OP = impact.ACCEPT_TRACE_OP, impact.ACCEPT_GATES_SKIPPED_OP, impact.ACCEPT_OVERFLOW_OP
BRANCH_HEAD = "差分の審査の穴の枝（機械が修正案の項目に結んだ名札。手直しの役にも同じ名札を渡した）"   # 1 回目の往復の頭
ANOMALY_LINE = "仕組みの異常: 取れない（元は共有ボードの trace と包みの記録から数えた。docs/design.md の U6）"
LENS_WHERE = "レンズ"
CLOSURE_UNREAD = "閉じたかを数えていない"   # 閉鎖の表の控えを読めない行の尾（outcome.residue が修正の残りにする）


def passes() -> tuple:
    """差分の審査と手直しの往復の番号（refix.passes の 1 か所から引く）"""
    import refix
    return tuple(refix.passes())


def branch_head(n: int) -> str:
    """n 回目の往復の穴の枝の頭"""
    return BRANCH_HEAD if n == passes()[0] else f"{n} 回目の審査の穴の枝"


def handled_head(n: int) -> str:
    """n 回目の往復の手直しの結果の頭"""
    return "手直しの結果" if n == passes()[0] else f"{n} 回目の手直しの結果"


# ---------------------------------------------------------------- 欄を組む口（子の結果と親の書き手）
def claimed_of(reply) -> list:
    """修正役が changes に載せた単位の key（申告。閉じたかは閉鎖の表が決める）"""
    return [str(c["unit_key"]) for c in (reply.get("changes") if isinstance(reply, dict) else None) or []
            if isinstance(c, dict) and isinstance(c.get("unit_key"), str)]


def closure_rows(place) -> list | None:
    """置き場の閉鎖の表（querytest.CLOSURE_FILE）の行。表が無ければ []、在るのに読めない・形が違えば None（書き手が訳にする）"""
    path = pathlib.Path(place) / querytest.CLOSURE_FILE
    if not path.is_file():
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    rows = doc.get("rows") if isinstance(doc, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else None


# ---------------------------------------------------------------- 書く
def _ties(place, *, items, plan_review, fix_reply) -> tuple:
    """({往復: 名札 | 組めない訳}, {往復: handled の行})"""
    import refix
    ties, handled = {}, {}
    for n in passes():
        try:
            ties[str(n)] = fixboard.hole_ties(place, n, items=items, plan_review=plan_review, fix_reply=fix_reply)
        except Exception as e:   # 名札は材料。組めない訳を置いて先へ（元 report._ties）
            ties[str(n)] = f"{type(e).__name__}: {oneline.one_line(e)}"
        out = fixboard.output(place, refix._pass(n)["fix"]) or {}
        handled[str(n)] = [h for h in out.get("handled") or [] if isinstance(h, dict)]
    return ties, handled


def write(place, results, ruled_reply=None, *, items=None, plan_review=None, fix_reply=None) -> None:
    """置き場 place に FILES を書く。results は戻せた組の子の結果（欄 closure・claimed。closure が None の子は表を読めなかった）、
    ruled_reply は裁定の後の修正役の返答（親の置き場の段。無ければ None）。items・plan_review・fix_reply は手直しの穴の名札の材料
    （fixboard.hole_ties の引数）。1 つのファイルが組めなくても、ほかは書く（組めない物は {"error": 訳}）"""
    place = pathlib.Path(place)
    results = [r for r in results or [] if isinstance(r, dict)]

    def put(name, build):
        try:
            doc = build()
        except Exception as e:   # 隣のファイルは材料。組めない訳を置き、出力ノードは落とさない
            doc = {"error": f"{type(e).__name__}: {oneline.one_line(e)}"}
        fixboard.write_json(place / name, doc)

    def closure():
        own = closure_rows(place)
        broken = [str(res.get("group_id")) for res in results if "closure" in res and res["closure"] is None]
        if own is None or broken:
            raise ValueError("閉鎖の表を読めない（" + "・".join([*(f"組 {g}" for g in broken), *(["この置き場"] if own is None else [])])
                             + "）")
        rows = {}
        for r in [*(x for res in results for x in res.get("closure") or []), *own]:
            if isinstance(r, dict):
                rows[r.get("unit_key")] = r   # 裁定の後の段の表がその単位の 1 回目の表を上書きする
        claimed = [*(k for res in results for k in res.get("claimed") or []), *claimed_of(ruled_reply)]
        return {"rows": list(rows.values()), "claimed": list(dict.fromkeys(claimed))}

    def holes():
        ties, handled = _ties(place, items=items, plan_review=plan_review, fix_reply=fix_reply)
        return {"ties": ties, "handled": handled}
    put(CLOSURE_FILE, closure)
    put(DELTA_HOLES_FILE, holes)


# ---------------------------------------------------------------- 読む
def _load(path: pathlib.Path, unread: list, *, rows: bool = False):
    """控え 1 つ（無い・読めない・{"error"}・形が違う物は unread に訳を足して None）。rows なら行の配列を求める"""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        unread.append(f"修正の控え {path} が無い")
        return None
    except (OSError, ValueError) as e:
        unread.append(f"修正の控え {path} が読めない（{type(e).__name__}: {oneline.one_line(e)}）")
        return None
    if isinstance(doc, dict) and "error" in doc:
        unread.append(f"修正の控え {path} を組めなかった（{oneline.one_line(doc['error'])}）")
        return None
    if not isinstance(doc, list if rows else dict):
        unread.append(f"修正の控え {path} の形が違う（{'行の配列' if rows else 'オブジェクト'}でない）")
        return None
    return doc


def _lens_summary(folder: pathlib.Path, unread: list) -> dict:
    """置き場のレンズの数え（lens.summary）と報告の行（lens.report_lines）と集め役の事実（fixboard.LENSES_FILE。読めなければ unread に訳）"""
    import lens
    import refix
    review = fixboard.out_file(folder, refix._pass(passes()[0])["review"])
    review = review if review.is_file() else None
    doc = _load(folder / fixboard.LENSES_FILE, unread)
    collector = doc.get("collector") if isinstance(doc, dict) else None
    return {"summary": lens.summary(folder, review), "lines": lens.report_lines(folder, review),
            "collector": collector if isinstance(collector, dict) else None}


def read(folders) -> dict:
    """段ごとの置き場（diff のポインタの先のフォルダ。fix と 2 度目の修正の順）を読み合わせる。返り {closure, claimed, ties, handled,
    lenses, trace, tests, removed, unread, closure_unread, folders}。ties・handled・lenses・removed は段ごとの並び [(フォルダ, 中身)]。
    trace は受け付けの行（accept-trace.json）、tests はそのうち段・組・受け付けの段ごとに最後の回の選んだ試験の行。読めない・無いファイルと {"error"} は unread に訳（0 件に見せない）。閉鎖の表の控えの
    訳は closure_unread にも置く（閉じたかを数えていない。outcome.residue が修正の残りに数える）"""
    import leftovers
    got = {"closure": {}, "claimed": [], "ties": [], "handled": [], "lenses": [], "trace": [], "tests": [], "removed": [], "unread": [],
           "closure_unread": [], "folders": []}
    for folder in folders or []:
        folder = pathlib.Path(folder)
        got["folders"].append(folder)
        closure_unread: list = []
        closure = _load(folder / CLOSURE_FILE, closure_unread) or {}
        got["unread"] += closure_unread
        got["closure_unread"] += [f"{x}——{CLOSURE_UNREAD}" for x in closure_unread]
        for r in closure.get("rows") or []:
            if isinstance(r, dict):
                got["closure"][r.get("unit_key")] = r   # 2 度目の修正の段の表がその単位の前の表を上書きする
        got["claimed"] += [k for k in closure.get("claimed") or [] if isinstance(k, str) and k not in got["claimed"]]
        holes = _load(folder / DELTA_HOLES_FILE, got["unread"]) or {}
        got["ties"].append((folder, holes.get("ties") or {}))
        got["handled"].append((folder, holes.get("handled") or {}))
        trace = [r for r in _load(folder / fixboard.ACCEPT_TRACE_FILE, got["unread"], rows=True) or [] if isinstance(r, dict)]
        got["trace"] += trace
        got["tests"] += _accepted_tests(trace)
        got["lenses"].append((folder, _lens_summary(folder, got["unread"])))
        got["removed"].append((folder, leftovers.removed(folder)))
    got["closure"] = list(got["closure"].values())
    return got


def _accepted_tests(trace: list) -> list:
    """1 つの修正の段の受け付けの選んだ試験の行（TESTS_OP）のうち、組と受け付けの段（pass）ごとの最後の回の物（回ごとに足した行の
    うち受けた回。fixboard.tests_trace）"""
    last: dict = {}
    for row in trace:
        if row.get("op") == TESTS_OP:
            key = (row.get("group_id"), row.get("pass"))
            if key not in last or (row.get("attempt") or 0) >= (last[key].get("attempt") or 0):
                last[key] = row
    return list(last.values())


# ---------------------------------------------------------------- 行の口（最後の関所と報告が同じ行を出す）
def closure_lines(got: dict, *, mismatched_only: bool = False, stuck_only: bool = False) -> list:
    """閉鎖の数え直しの行（querytest.closure_lines。既定の列は表に行の無い申告の単位も名指す）"""
    return querytest.closure_lines(got["closure"], mismatched_only=mismatched_only, stuck_only=stuck_only,
                                   claimed=() if (mismatched_only or stuck_only) else got["claimed"])


def not_closed(got: dict) -> list:
    """閉鎖の表で閉じていない（closed が偽の）単位の key（元 report._closed_units の裏）"""
    return [str(r.get("unit_key")) for r in got["closure"] if r.get("closed") is False]


def _left(got: dict, field: str) -> list:
    return list(dict.fromkeys(t for row in got["tests"] for t in row.get(field) or [] if isinstance(t, str)))


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
        out.append(f"承認ノードの条件の相談で認めた新しいテスト: {'・'.join(gated)}（今の木に在る物を赤緑か守りで確かめた）")
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


def branch_rows(got: dict) -> list:
    """手直しの往復ごとの穴の枝の名札（件数の 1 行 holeties.count_line と穴ごとの行。組めなければ訳の 1 行）と手直しの結果（handled
    の行）。元 report.branch_rows と line_edge._final_text の手直しの結果。穴も手直しも無ければ []"""
    import gatemarks
    import holeties
    rows = []
    for (_, ties), (_, handled) in zip(got["ties"], got["handled"]):
        for n in passes():
            t = ties.get(str(n))
            if isinstance(t, str):
                rows.append(f"{branch_head(n)}: 組めない（{t}）")
            elif t:
                rows.append(f"{branch_head(n)}: {holeties.count_line(t)}")
                rows += [f"  - {x}" for x in holeties.lines(t)]
            h = handled.get(str(n)) or []
            if h:
                rows.append(f"{handled_head(n)}（{len(h)} 件）:")
                rows += [f"  - {x.get('key')}: {gatemarks.HANDLED_WORDS.get(x.get('handled'), '')}（{x.get('handled')}）——{oneline.one_line(x.get('how') or '')}"
                         for x in h]
    return rows


def lens_lines(got: dict) -> list:
    """報告の「未確認のレンズ」のセクションの行（lens.report_lines。段ごと）"""
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
            rows.append(f"clean が消したファイル{where}: 読めない（{oneline.one_line(gone['reason'])}）")
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
            rows.append(f"レンズ{where}: 読めない（{oneline.one_line(s.get('reason'))}）——どのレンズが見たかを確かめられない")
        elif not s.get("ran"):
            rows.append(f"レンズ{where}: 走らせていない（控えが無い）")
        else:
            rows.append(f"{lens.count_line(s)}{where}")
            for r in s.get("rows") or []:
                taken = "調べていない" if r.get("adopted") is None else f"採った {r['adopted']}・採らなかった {r['not_adopted']}"
                rows.append(f"  - {r.get('lens')}: {taken}・形の誤りで捨てた {r.get('dropped')}（出した発見 {r.get('findings')}）")
            rows += [f"  - 落ちたレンズ {f.get('lens')}（再実行の要あり）: {oneline.one_line(f.get('reason'))}" for f in s.get("failed") or []]
        collector = doc.get("collector")
        if isinstance(collector, dict) and collector.get("ok") is False:
            rows.append(f"レンズの集め役{where}: {oneline.one_line(collector.get('reason') or '訳が無い')}")
    if not seen:
        rows.append("レンズ: 控えが無い（修正の段が無い run か、控えが読めない。下の読めなかった控えの訳）")
    rows.append(ANOMALY_LINE)
    return rows


def next_items(got: dict) -> list:
    """次の依頼の行 [{where, text}]（元 report.next_request の手直しの行と lens_next_items）: 手直しが declared で残した穴と、
    2 回目の手直しが fixed と言った穴（3 回目の審査が無いので検算が要る。どちらも枝の名札を添える）、落ちたレンズを「再実行の要あり」、
    レンズの控えが読めなければそれも同じ言い方で"""
    import holeties
    items = []
    for (_, ties), (_, handled) in zip(got["ties"], got["handled"]):
        for n in passes():
            t = ties.get(str(n))
            tags = {x["key"]: holeties.note(x) for x in t if isinstance(x, dict) and "key" in x} if isinstance(t, list) else {}
            for h in handled.get(str(n)) or []:
                if not isinstance(h.get("key"), str):
                    continue
                where = (h.get("files") or [None])[0] or h["key"]
                tag = f"（枝: {tags[h['key']]}）" if h["key"] in tags else ""
                if h.get("handled") == "declared":
                    items.append({"where": str(where), "text": f"{h['key']}（手直しが declared で残した穴: {h.get('how') or ''}）{tag}"})
                elif h.get("handled") == "fixed" and n == passes()[-1]:
                    items.append({"where": str(where),
                                  "text": f"{h['key']}（手直し {n} 回目が fixed と言ったが、{n + 1} 回目の審査は無い——検算が要る: "
                                          f"{h.get('how') or ''}）{tag}"})
    for folder, doc in got["lenses"]:
        s = doc.get("summary") if isinstance(doc.get("summary"), dict) else {}
        if s and not s.get("readable"):
            items.append({"where": LENS_WHERE, "text": f"レンズの控えが読めない——再実行の要あり: {oneline.one_line(s.get('reason'))}"})
            continue
        items += [{"where": f"{LENS_WHERE} {f.get('lens')}",
                   "text": f"{f.get('lens')}（再実行の要あり: 落ちて観点を誰も見ていない。理由: {oneline.one_line(f.get('reason'))}）"}
                  for f in s.get("failed") or [] if isinstance(f, dict)]
    return items
