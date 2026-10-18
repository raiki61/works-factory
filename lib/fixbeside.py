"""修正のブロックの返り diff の隣の約束のファイル（docs/design.md の「サブグラフの出力の約束」の fix の出力）のうち、閉鎖の表と
差分の審査の穴の名札の書き手と、ほかのブロックとメイングラフが読む控えを出力の欄にする口と読む口。

書き手は修正の出力ノード（write と returned）。控えは diff のポインタの先と同じフォルダ（修正の段ごとの置き場）に置き、ほかが読む物は
出力の欄で返す（PORTS はポインタの欄 → 置き場のファイル、FROM は中身の欄 → 元のファイル）。組の子の run は子の置き場に書くので、子の
結果（fixboard.group_result）の欄 closure・claimed で親へ運び、親の置き場の分（裁定の後の修正の段）と合わせる。

- CLOSURE_FILE: {rows: [閉鎖の表の行（querytest.save_closure の行）], claimed: [修正役が changes に載せた単位の key]}
- DELTA_HOLES_FILE: {ties: {"1": [名札（holeties.tie の行）] か組めない訳の字, "2": …}, handled: {"1": [手直しの handled の行], "2": …}}
どちらも、書けなかった・組めなかった時は {"error": 訳} を置き、読み手は訳を名指す（0 件に見せない）。
修正役が人に回した物（handoffs）と申告と数え直しが合わない単位（mismatched）は fix の出力の欄が正本で、ここでは読まない。
欄で返すほかの控え（書き手は fix のほかの所）:
- allowed_tests（fixboard.ALLOWED_TESTS_FILE）: 許したテストの変更の訳 [{path, permit, source}]
- accept_trace（fixboard.ACCEPT_TRACE_FILE）: 受け付けの行の並び（選んだ試験の知らせ・赤緑を確かめずに受けた回・はみ出しの
  決着・範囲の相談。fixboard.accept_trace_rows）
- lenses（fixboard.LENSES_FILE）: レンズの集め役の事実 {collector: {ok, reason}} に、returned が置き場のレンズの数え（lens.summary）と
  報告の行（lens.report_lines）を summary・lines で足した物
- tdd_unit（fixboard.TDD_UNIT_FILE）: 組ごとの TDD の記録（書き手は fix の tdd-unit。eyes が R2 の比較役に貼る）
- removed: clean が消したパスの控え（leftovers.REMOVED_FILE。置き場の根と scope の根の）のポインタの並び（leftovers.found）。
  clean が走っていなければ []、探せなければ null。消したパスの全件はファイルにだけ在る
- tdd_refused: TDD の輪の状態（tddloop.STATE）の calls から修正役が拒まれた単位 {refused, unread}（tdd_refused）

- claimed_of(reply)・closure_rows(place): 子の結果と親が欄を組む口
- write(place, results, ruled_reply, *, items, plan_review, fix_reply): 書く
- returned(place, pointer)・require_ports(got)・stage(got): 返す節の控えの欄を組む口と、この版より前に走った修正の返りを resume で
  受けたかの照らしと、返りから読み手の口に渡す段を切る口
- read(stages, resolve)・tdd(stage, resolve)・late_records(stage, resolve)・late_place(place, result_files): 読み手の口。段（fix の返りの控えの欄の dict。ポインタのまま）
  と、ポインタを置き場の中のパスに戻す関数 resolve を受け、どの欄がポインタかを知って戻すのはここだけ（_port）。read は段の並び
  （fix と 2 度目の修正の順）を読み合わせた見え方、tdd は段の TDD の記録、late_records は線の redepth が修正の後に深さを上げる
  信号（TDD の拒否・範囲の相談）の元。late_place は同じ形の元を返す節より前の置き場から読む口（fixboard.redepth）で、どちらの
  元も latedepth.signals に渡す
- tdd_refused(folder, unread): TDD の輪の状態から修正役が拒まれた単位の名を読む口（late_place と returned が同じ読みで使う）
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
import leftovers  # noqa: E402
import listcut  # noqa: E402
import oneline  # noqa: E402
import querytest  # noqa: E402
import tddloop  # noqa: E402

CLOSURE_FILE = "closure.json"
DELTA_HOLES_FILE = "delta-holes.json"
# 返す節の出力の欄 → 置き場の控え。ほかのブロックとメイングラフはこの欄で受け、名で開かない（docs/design.md の「fix の出力」）
PORTS = {"allowed_tests": fixboard.ALLOWED_TESTS_FILE, "accept_trace": fixboard.ACCEPT_TRACE_FILE, "lenses": fixboard.LENSES_FILE,
         "closure": CLOSURE_FILE, "delta_holes": DELTA_HOLES_FILE, "tdd_unit": fixboard.TDD_UNIT_FILE}
FROM = {"removed": leftovers.REMOVED_FILE, "tdd_refused": tddloop.STATE}
PRIOR_VERSION = "前の版の修正の出力。workflow run で最初から起こし直す"
REMOVED_UNRETURNED = "修正の出力が消したファイルの控えを返せなかった"
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
    """置き場 place に CLOSURE_FILE と DELTA_HOLES_FILE を書く。results は戻せた組の子の結果（欄 closure・claimed。closure が None の子は表を読めなかった）、
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


def _lens_counts(place: pathlib.Path) -> dict:
    """置き場のレンズの数え（lens.summary）と報告の行（lens.report_lines。差分の審査の 1 回目の出力と合わせて数える）"""
    import lens
    import refix
    review = fixboard.out_file(place, refix._pass(passes()[0])["review"])
    review = review if review.is_file() else None
    return {"summary": lens.summary(place, review), "lines": lens.report_lines(place, review)}


def returned(place, pointer) -> dict:
    """返す節の控えの欄（PORTS・FROM）。pointer は置き場の中のパスをポインタにする口。lenses.json にはレンズの数えと報告の行を足して
    から指す（集め役の事実の欄 collector は書き手のまま。読めない・object でない控えは書き直さず、読み手が訳を名指す）。PORTS の先が
    無い欄は null。removed は leftovers.found の各ファイルのポインタ（探せなければ null）、tdd_refused は {refused, unread}"""
    place = pathlib.Path(place)
    lenses = place / fixboard.LENSES_FILE
    try:
        doc = fixboard.read_json(lenses)
    except ValueError:
        doc = None
    if isinstance(doc, dict):
        fixboard.write_json(lenses, {**doc, **_lens_counts(place)})
    try:
        removed = [pointer(p) for p in leftovers.found(place)]
    except leftovers.Unreadable:
        removed = None
    unread: list = []
    return {**{field: pointer(place / name) if (place / name).is_file() else None for field, name in PORTS.items()},
            "removed": removed, "tdd_refused": {"refused": tdd_refused(place, unread), "unread": unread}}


def require_ports(got: dict | None) -> None:
    """修正の返り（受け皿の got か、口 boundary.picked で受けた返り）が控えの欄 PORTS・FROM を持つか照らす（飛んだ段の None は
    照らさない）。欄の鍵が無いか、いつも object の tdd_refused が null（picked は欠けた欄を null で埋める）の返りは、この版より前に走った
    修正の控えを resume で受けた物で、欄を空と読むと控えを「無い」と読むので、ValueError で止める"""
    if got is not None and (any(field not in got for field in (*PORTS, *FROM)) or got.get("tdd_refused") is None):
        raise ValueError(PRIOR_VERSION)


def stage(got) -> dict:
    """修正の返り got から、読み手の口に渡す段 {diff, 控えの欄}（メイングラフが 1 回目と 2 度目の修正の段を並べる形）"""
    return {"diff": got["diff"], **{field: got[field] for field in (*PORTS, *FROM)}}


READ_ERRORS = (ValueError, TypeError, AttributeError, KeyError)


def _port(stage: dict, field: str, resolve, unread: list) -> pathlib.Path | None:
    """段の欄 field のポインタを置き場の中のパスに戻す（null・戻せなければ unread に訳を足して None）"""
    ptr = stage.get(field)
    if ptr is None:
        unread.append(f"修正の控え {field} が無い")
        return None
    try:
        return pathlib.Path(resolve(ptr))
    except READ_ERRORS as e:
        unread.append(f"修正の控え {field} のポインタを読めない（{type(e).__name__}: {oneline.one_line(e)}）")
        return None


def _place(stage: dict, resolve) -> pathlib.Path | None:
    """段の置き場（diff の先のフォルダ。戻せなければ None）"""
    try:
        return pathlib.Path(resolve(stage.get("diff"))).parent
    except READ_ERRORS:
        return None


def _removed(stage: dict, resolve, place: pathlib.Path | None) -> dict:
    """段の欄 removed（clean が消したパスの控えのポインタの並び）を leftovers.read_removed で読む。[] は走らせていない、null と戻せない
    ポインタは読めない（訳つき）。scope は各ファイルが段の置き場 place の根か直下のフォルダかで決まる"""
    ptrs = stage.get("removed")
    if ptrs is None:
        return {**leftovers.read_removed([]), "ran": True, "readable": False, "reason": REMOVED_UNRETURNED}
    files, bad = [], []
    for ptr in ptrs if isinstance(ptrs, list) else [ptrs]:
        try:
            files.append(pathlib.Path(resolve(ptr)))
        except READ_ERRORS as e:
            bad.append(f"{type(e).__name__}: {oneline.one_line(e)}")
    got = leftovers.read_removed(files, place)
    if bad:
        got.update(ran=True, readable=False, reason="・".join([*([got["reason"]] if got["reason"] else []),
                                                               f"消したファイルの控えのポインタを読めない（{'／'.join(bad)}）"]))
    return got


def _allowed(path: pathlib.Path | None, rows: list, unread: list) -> None:
    """許したテストの変更の訳を rows に重ねずに足す（読めない・行の配列でなければ unread に訳。黙って空にしない）"""
    if path is None:
        return
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc, list) or not all(isinstance(row, dict) for row in doc):
            raise ValueError("行の配列でない")
    except (OSError, ValueError) as error:
        unread.append(f"許したテストの変更の訳 {path} を読めない（{type(error).__name__}: {error}）")
        return
    rows += [row for row in doc if row not in rows]


def read(stages, resolve) -> dict:
    """修正の段ごとの返りの控えの欄の dict（fix と 2 度目の修正の順。ポインタのまま）を読み合わせる。resolve はポインタを置き場の中の
    パスに戻す関数（戻せなければ ValueError など）。返り {closure, claimed, ties, handled, lenses, trace, tests, removed, allowed, unread,
    closure_unread}。ties・handled・lenses・removed は段ごとの並び [(段の名, 中身)]。trace は受け付けの行、tests はそのうち段・組・
    受け付けの段ごとに最後の回の選んだ試験の行、allowed は許したテストの変更の訳（段の順に重ねない）。null・戻せない・読めない・無い
    控えと {"error"} は unread に訳（0 件に見せない）。閉鎖の表の控えの訳は closure_unread にも置く（閉じたかを数えていない。
    outcome.residue が修正の残りに数える）。removed の読めなさは行に出すが unread に入れない"""
    got = {"closure": {}, "claimed": [], "ties": [], "handled": [], "lenses": [], "trace": [], "tests": [], "removed": [], "allowed": [],
           "unread": [], "closure_unread": []}
    for n, stage in enumerate(stages or [], 1):
        if not isinstance(stage, dict):
            got["unread"].append("修正の段の出力が dict でない")
            continue
        place = _place(stage, resolve)
        label = place.name if place is not None else f"段 {n}"
        closure_unread: list = []
        path = _port(stage, "closure", resolve, closure_unread)
        closure = (_load(path, closure_unread) if path is not None else None) or {}
        got["unread"] += closure_unread
        got["closure_unread"] += [f"{x}——{CLOSURE_UNREAD}" for x in closure_unread]
        for r in closure.get("rows") or []:
            if isinstance(r, dict):
                got["closure"][r.get("unit_key")] = r   # 2 度目の修正の段の表がその単位の前の表を上書きする
        got["claimed"] += [k for k in closure.get("claimed") or [] if isinstance(k, str) and k not in got["claimed"]]
        path = _port(stage, "delta_holes", resolve, got["unread"])
        holes = (_load(path, got["unread"]) if path is not None else None) or {}
        got["ties"].append((label, holes.get("ties") or {}))
        got["handled"].append((label, holes.get("handled") or {}))
        path = _port(stage, "accept_trace", resolve, got["unread"])
        trace = [r for r in (_load(path, got["unread"], rows=True) if path is not None else None) or [] if isinstance(r, dict)]
        got["trace"] += trace
        got["tests"] += _accepted_tests(trace)
        path = _port(stage, "lenses", resolve, got["unread"])
        doc = (_load(path, got["unread"]) if path is not None else None) or {}
        got["lenses"].append((label, {"summary": doc.get("summary"), "lines": doc.get("lines") or [],
                                      "collector": doc.get("collector") if isinstance(doc.get("collector"), dict) else None}))
        got["removed"].append((label, _removed(stage, resolve, place)))
        _allowed(_port(stage, "allowed_tests", resolve, got["unread"]), got["allowed"], got["unread"])
    got["closure"] = list(got["closure"].values())
    return got


def tdd(stage, resolve):
    """段の TDD の記録（欄 tdd_unit の先。組ごとの段の物の配列）か、無い・読めない訳の字"""
    unread: list = []
    if not isinstance(stage, dict):
        return "修正の段の出力が dict でない"
    path = _port(stage, "tdd_unit", resolve, unread)
    doc = _load(path, unread, rows=True) if path is not None else None
    return doc if doc is not None else unread[0]


def tdd_refused(folder, unread: list) -> list:
    """置き場 folder の TDD の輪の状態（tddloop.states）の calls から修正役が拒まれた単位の名（tddloop.refused_units）。在るのに
    読めない・{"error"}・形が違う状態は unread に訳を足す（latedepth.signals が上げる側へ倒す）。輪の状態が 1 つも無い
    置き場は TDD の輪が走っていないので拒否も無い"""
    refused = []
    for state in tddloop.states(folder):
        doc = _load(state, unread)
        refused += tddloop.refused_units(doc.get("calls") if doc is not None else None)
    return refused


def late_records(stage, resolve) -> dict:
    """段（最後の修正の段の返りの控えの欄）の、修正の後に深さを上げる信号の元: TDD の拒否（欄 tdd_refused）と、受け付けの行（欄
    accept_trace の先）。返り {refused: [単位の名], trace: 受け付けの行の並び | None, missing: [無い控えの名], unread: [在るのに読めない・
    {"error"}・形が違う訳]}。受け付けの行の欄が null なら None で missing に名を、在るのに読めない控えは unread に訳を足す
    （latedepth.signals の late。late_place と同じ決まり）。行は dict の物だけ"""
    got: dict = {"refused": [], "trace": None, "missing": [], "unread": []}
    if not isinstance(stage, dict):
        got["unread"].append("修正の段の出力が dict でない")
        return got
    refused = stage.get("tdd_refused")
    if isinstance(refused, dict) and isinstance(refused.get("refused"), list) and isinstance(refused.get("unread"), list):
        got["refused"] = [str(k) for k in refused["refused"]]
        got["unread"] += [str(x) for x in refused["unread"]]
    else:
        got["unread"].append("修正の控え tdd_refused の形が違う（{refused, unread} でない）")
    if stage.get("accept_trace") is None:
        got["missing"].append(PORTS["accept_trace"])
        return got
    path = _port(stage, "accept_trace", resolve, got["unread"])
    rows = _load(path, got["unread"], rows=True) if path is not None else None
    got["trace"] = None if rows is None else [r for r in rows if isinstance(r, dict)]
    return got


def late_place(place, result_files: dict) -> tuple:
    """返す節より前の修正の段の置き場 place の、late_records と同じ形の信号の元と、読めた組の子の結果の並び。result_files は
    戻せた組の id → 子の結果（fixboard.RESULT_FILE）のパス。子の結果が無い組は missing に名を、在るのに読めない子の結果と置き場の
    受け付けの行（fixboard.accept_trace_rows が拒む形）は unread に訳を足し、受け付けの行を None にする"""
    got: dict = {"refused": [], "trace": None, "missing": [], "unread": []}
    got["refused"] = tdd_refused(place, got["unread"])
    results = []
    for gid, path in result_files.items():
        path = pathlib.Path(path)
        if not path.is_file():
            got["missing"].append(f"組 {gid} の {path.name}")
            continue
        doc = _load(path, got["unread"])
        if doc is not None:
            results.append(doc)
    try:
        got["trace"] = fixboard.accept_trace_rows(place, results)
    except ValueError as e:
        got["unread"].append(oneline.one_line(e))
    return got, results


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
    for _, doc in got["lenses"]:
        out += [str(x) for x in doc.get("lines") or []]
    return out


def _top(scope: str, path: str) -> str:
    """上位のフォルダごとの本数の区分: パスの頭の 1 段。根に直に在るファイル（区切りの / が無い名）はファイル名ごとに数えず 1 つの区分に
    まとめる。include の scope の分は scope の名を頭に付け、盤面の直下の分の同じ名のフォルダと混ぜない"""
    top = path.split("/", 1)[0] if "/" in path else "（根）"
    return f"{scope} の {top}" if scope else top


def always_rows(got: dict) -> list:
    """clean が消したファイル・レンズ・仕組みの異常の行（0 件でも、走らせていない・読めないを 0 件と分ける。元 report.always_rows の
    頭の 3 つ。残りの行は呼び手が持つ）。字下げの行は内訳で、先頭 listcut.SHOWN 本と（それを超える時は）上位のフォルダごとの本数（scope ごと）。
    全件は欄 removed の先のファイルに在る（残りの行がその置き場を指す）"""
    rows = []
    for label, gone in got["removed"]:
        where = f"（{label}）"
        if not gone["readable"]:
            rows.append(f"clean が消したファイル{where}: 読めない（{oneline.one_line(gone['reason'])}）")
        elif not gone["ran"]:
            rows.append(f"clean が消したファイル{where}: 走らせていない（消したファイルの控えが無い。clean の前に止まった）")
        else:
            rows.append(f"clean が消したファイル{where}: {gone['count']} 本")
            rows += listcut.lines(gone["paths"], where="、".join(gone["files"]))
            if len(gone["paths"]) > listcut.SHOWN:
                tops = collections.Counter(_top(scope, n) for scope, names in gone["by_scope"].items() for n in names)
                rows += ["  - 上位のフォルダごとの本数:", *listcut.lines((f"{k}: {v} 本" for k, v in tops.most_common()), prefix="    - ")]
    if not got["removed"]:
        rows.append("clean が消したファイル: 走らせていない（修正の段が無い run）")
    import lens
    seen = False
    for label, doc in got["lenses"]:
        s = doc.get("summary") if isinstance(doc.get("summary"), dict) else None
        where = f"（{label}）"
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
    for _, doc in got["lenses"]:
        s = doc.get("summary") if isinstance(doc.get("summary"), dict) else {}
        if s and not s.get("readable"):
            items.append({"where": LENS_WHERE, "text": f"レンズの控えが読めない——再実行の要あり: {oneline.one_line(s.get('reason'))}"})
            continue
        items += [{"where": f"{LENS_WHERE} {f.get('lens')}",
                   "text": f"{f.get('lens')}（再実行の要あり: 落ちて観点を誰も見ていない。理由: {oneline.one_line(f.get('reason'))}）"}
                  for f in s.get("failed") or [] if isinstance(f, dict)]
    return items
