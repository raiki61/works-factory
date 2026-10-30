"""2 つの修正の段の合わせと、修正の段の控えの読み口（docs/design/line.md の 1.5・4.3。integration.md 4.5-3）。

元は今の workflows/line/scripts/fixed.py の中身と、組み込みで消える lib/fixbeside.py の読み口のうち line が読む物（stage・read・tdd・
late_records と、最後の承認ノードと報告が同じ行を出す closure_lines・not_closed・tests_left_lines・gates_lines・plan_ask_lines・
always_rows・next_items）。名は元のまま（E18）。差分の審査の穴の枝（branch_rows）・レンズの行・手直しの行は delta-review と lens の
block が自分の出力の report・carry で返すので写さない（delta-review の設計書の 1.6）。lib は KEEP の物だけを読む。

- PORTS・FROM: fix の出力の控えの欄（pointer の欄と、中身の欄）。stage(got) は fix の受け皿の got から読み手の口に渡す段
- resolve(ptr, field): 作り手の返りの欄 field の pointer（か、パスの字）を、その欄の宣言の form で中身を照らしてこの run の place の
  中のパスに戻す（戻せない・形に合わなければ ValueError）。resolve を受ける読み手の口は resolve(ptr, 欄の名) で呼ぶ
- read(stages, resolve)・tdd(stage, resolve)・late_records(stage, resolve): 読み手の口（元 fixbeside の同じ名。delta_holes・lenses を読まない）
- fixed(values) -> fixed の node の返り（YAML の output_format の欄）。values は fixed.py が受け皿の got から組んだ dict
- held_of(values) -> (held か, 訳)・go_done(values, held) -> (go, done)
"""
from __future__ import annotations

import collections
import json
import pathlib

# fix の出力の欄 → 控えの中身（docs/design/fix.md の 1.2）。読み手はこの欄で受け、fix の place を名で開かない
PORTS = ("allowed_tests", "accept_trace", "closure", "tdd_unit")
FROM = ("removed", "tdd_refused", "removed_tests", "untested")
READ_ERRORS = (ValueError, TypeError, AttributeError, KeyError)
CLOSURE_UNREAD = "閉じたかを数えていない"   # 閉鎖の表の控えを読めない行の尾（facts.residue が修正の残りにする）
REMOVED_UNRETURNED = "修正の出力が消したファイルの控えを返せなかった"
ANOMALY_LINE = "仕組みの異常: 取れない（元は共有ボードの trace と包みの記録から数えた。docs/design/archon.md の U6）"
STAGE_NAMES = ("修正の段", "案を直した後の修正の段")   # stages の並び（1 回目・2 度目）。lib/report.py の TDD_STAGES と同じ順
# held の訳（報告と試験が読む）
HELD_REPLAN = "案の直しが要ったのに 2 度目の修正が走らなかった"
HELD_LINE = "修正の後の line の script が止めた"
HELD_STOP = "修正の段が止めの語を返した"
HELD_UNRETURNED = "修正の段が返らなかった"


def _spec_objection() -> str:
    import stopby   # lib/（呼ぶ時に読む。src を lib なしで読む試験の道を残す）
    return stopby.declare("spec-objection", "仕様駆動の run で、修正の段が案と作業ツリーの食い違いを申し出た（案の直しと再審へ進まず止めた）")


SPEC_OBJECTION = "works:spec-objection"   # _spec_objection が declare する語（docs/design/spec-driven.md の 6.2 の変える node の 6）


def _opened():
    """作り手の返りの欄の名 → その欄の pointer の字を、作り手が宣言した form で照らしてパスに戻す読み（ports.file）"""
    import ports
    return {
        "diff": lambda raw: ports.file(raw, "file"),
        "closure": lambda raw: ports.file(raw, "json(shared:closure.schema.json)"),
        "accept_trace": lambda raw: ports.file(raw, "json(shared:accept-trace.schema.json)"),
        "allowed_tests": lambda raw: ports.file(raw, "json(shared:allowed-tests.schema.json)"),
        "tdd_unit": lambda raw: ports.file(raw, "json(shared:tdd-units.schema.json)"),
        "removed": lambda raw: ports.file(raw, "json(shared:removed.schema.json)"),
        "conflicts": lambda raw: ports.file(raw, "json(lib:conflicts.schema.json)"),
        "judgment": lambda raw: ports.file(raw, "json(shared:judgment.schema.json)"),
        "answer_ties": lambda raw: ports.file(raw, "json(shared:answer-ties.schema.json)"),
        "materials": lambda raw: ports.file(raw, "json(shared:materials-state.schema.json)"),
        "excluded": lambda raw: ports.file(raw, "json(shared:excluded.schema.json)"),
        "out_of_purpose": lambda raw: ports.file(raw, "json(lib:out-of-purpose.schema.json)"),
        "tier_record": lambda raw: ports.file(raw, "json(shared:depth-record.schema.json)"),
        "rejudge_exit": lambda raw: ports.file(raw, "json(shared:rejudge-exit.schema.json)"),
        "after": lambda raw: ports.file(raw, "json(shared:structure-after.schema.json)"),
        "baseline": lambda raw: ports.file(raw, "json(lib:baseline.schema.json)"),
        "record": lambda raw: ports.file(raw, "json(shared:plan-converge.schema.json)"),
        "plan": lambda raw: ports.file(raw, "json(shared:plan-fields.schema.json)"),
        "start": lambda raw: ports.file(raw, "json(start-record.schema.json)"),
        "prior_failures": lambda raw: ports.file(raw, "json(shared:prior-failures.schema.json)"),
    }


def resolve(ptr, field: str) -> pathlib.Path:
    """作り手の返りの欄 field の pointer（{type, run_id, path}）かパスの字を、place の中のファイルのパスに戻す（その欄の宣言の form で
    中身を照らす。在らない・形に合わなければ ValueError）"""
    raw = json.dumps(ptr) if isinstance(ptr, dict) else str(ptr)
    got = _opened()[field](raw)
    if got is None:
        raise ValueError("pointer が空")
    return got


def stage(got) -> dict:
    """修正の返り got（受け皿の got）から、読み手の口に渡す段 {diff, 控えの欄}（line が 1 回目と 2 度目の修正の段を並べる形）"""
    return {"diff": got["diff"], **{field: got[field] for field in (*PORTS, *FROM)}}


def _load(path: pathlib.Path, unread: list, *, rows: bool = False):
    """控え 1 つ（無い・読めない・{"error"}・形が違う物は unread に訳を足して None）。rows なら行の配列を求める"""
    import oneline
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


def _port(stage: dict, field: str, resolve, unread: list) -> pathlib.Path | None:
    """段の欄 field のポインタを置き場の中のパスに戻す（null・戻せなければ unread に訳を足して None）"""
    import oneline
    ptr = stage.get(field)
    if ptr is None:
        unread.append(f"修正の控え {field} が無い")
        return None
    try:
        return pathlib.Path(resolve(ptr, field))
    except READ_ERRORS as e:
        unread.append(f"修正の控え {field} のポインタを読めない（{type(e).__name__}: {oneline.one_line(e)}）")
        return None


def _place(stage: dict, resolve) -> pathlib.Path | None:
    """段の置き場（diff の先のフォルダ。戻せなければ None）"""
    try:
        return pathlib.Path(resolve(stage.get("diff"), "diff")).parent
    except READ_ERRORS:
        return None


def _removed(stage: dict, resolve, place: pathlib.Path | None) -> dict:
    """段の欄 removed（clean が消したパスの控えのポインタの並び）を leftovers.read_removed で読む。[] は走らせていない、null と戻せない
    ポインタは読めない（訳つき）"""
    import leftovers
    import oneline
    ptrs = stage.get("removed")
    if ptrs is None:
        return {**leftovers.read_removed([]), "ran": True, "readable": False, "reason": REMOVED_UNRETURNED}
    files, bad = [], []
    for ptr in ptrs if isinstance(ptrs, list) else [ptrs]:
        try:
            files.append(pathlib.Path(resolve(ptr, "removed")))
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


def _accepted_tests(trace: list) -> list:
    """1 つの修正の段の受け付けの選んだ試験の行のうち、組と受け付けの段（pass）ごとの最後の回の物"""
    import impact
    last: dict = {}
    for row in trace:
        if row.get("op") == impact.ACCEPT_TRACE_OP:
            key = (row.get("group_id"), row.get("pass"))
            if key not in last or (row.get("attempt") or 0) >= (last[key].get("attempt") or 0):
                last[key] = row
    return list(last.values())


def read(stages, resolve) -> dict:
    """修正の段ごとの返りの控えの欄の dict（fix と 2 度目の修正の順。ポインタのまま）を読み合わせる（元 fixbeside.read。差分の審査の
    穴とレンズの控えは fix の出力に無くなったので読まない）。返り {closure, claimed, trace, tests, removed, allowed, removed_tests,
    untested, unread, closure_unread}。removed は段ごとの並び [(段の名, 中身)]。removed_tests・untested は段の欄の行に段の名 stage を
    足して段の順に並べた物（消した試験・試験を求めなかった直し。下書き 4.1 の 7）。null・戻せない・読めない・無い控えと {"error"} は
    unread に訳"""
    got = {"closure": {}, "claimed": [], "trace": [], "tests": [], "removed": [], "allowed": [], "removed_tests": [], "untested": [],
           "unread": [], "closure_unread": []}
    for n, stage in enumerate(stages or [], 1):
        if not isinstance(stage, dict):
            got["unread"].append("修正の段の出力が dict でない")
            continue
        place = _place(stage, resolve)
        label = STAGE_NAMES[n - 1] if n <= len(STAGE_NAMES) else f"段 {n}"
        closure_unread: list = []
        path = _port(stage, "closure", resolve, closure_unread)
        closure = (_load(path, closure_unread) if path is not None else None) or {}
        got["unread"] += closure_unread
        got["closure_unread"] += [f"{x}——{CLOSURE_UNREAD}" for x in closure_unread]
        for r in closure.get("rows") or []:
            if isinstance(r, dict):
                got["closure"][r.get("unit_key")] = r   # 2 度目の修正の段の表がその単位の前の表を上書きする
        got["claimed"] += [k for k in closure.get("claimed") or [] if isinstance(k, str) and k not in got["claimed"]]
        path = _port(stage, "accept_trace", resolve, got["unread"])
        trace = [r for r in (_load(path, got["unread"], rows=True) if path is not None else None) or [] if isinstance(r, dict)]
        got["trace"] += trace
        got["tests"] += _accepted_tests(trace)
        got["removed"].append((label, _removed(stage, resolve, place)))
        _allowed(_port(stage, "allowed_tests", resolve, got["unread"]), got["allowed"], got["unread"])
        for field in ("removed_tests", "untested"):
            rows = stage.get(field)
            if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
                got["unread"].append(f"修正の段（{label}）の欄 {field} が行の並びでない")
                continue
            got[field] += [{**r, "stage": label} for r in rows]
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


def late_records(stage, resolve) -> dict:
    """段（最後の修正の段の返りの控えの欄）の、修正の後に深さを上げる信号の元: TDD の拒否（欄 tdd_refused）と、受け付けの行（欄
    accept_trace の先）。返り {refused, trace, missing, unread}（元 fixbeside.late_records）"""
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
        got["missing"].append("accept_trace")
        return got
    path = _port(stage, "accept_trace", resolve, got["unread"])
    rows = _load(path, got["unread"], rows=True) if path is not None else None
    got["trace"] = None if rows is None else [r for r in rows if isinstance(r, dict)]
    return got


# ---------------------------------------------------------------- 行の口（最後の承認ノードと報告が同じ行を出す）
def closure_lines(got: dict, *, mismatched_only: bool = False, stuck_only: bool = False) -> list:
    """閉鎖の数え直しの行（querytest.closure_lines。既定の列は表に行の無い申告の単位も名指す）"""
    import querytest
    return querytest.closure_lines(got["closure"], mismatched_only=mismatched_only, stuck_only=stuck_only,
                                   claimed=() if (mismatched_only or stuck_only) else got["claimed"])


def not_closed(got: dict) -> list:
    """閉鎖の表で閉じていない（closed が偽の）単位の key"""
    return [str(r.get("unit_key")) for r in got["closure"] if r.get("closed") is False]


def _left(got: dict, field: str) -> list:
    return list(dict.fromkeys(t for row in got["tests"] for t in row.get(field) or [] if isinstance(t, str)))


def tests_left_lines(got: dict) -> list:
    """受け付けが手元で回さなかった試験・最後のテストの段に任せた試験・遠くて読み切れないファイル（keep-essence の 6。字下げの行は内訳）"""
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
    """事後の関門の束が赤緑を確かめずに受けた回と、はみ出しを相談で認めた・戻した行・関所の条件の相談で認めた新しいテスト・守りのテスト"""
    import impact
    out = []
    rows = [r for r in got["trace"] if r.get("op") == impact.ACCEPT_GATES_SKIPPED_OP]
    if rows:
        whys = list(dict.fromkeys(w for r in rows for w in r.get("why") or [] if isinstance(w, str)))
        out.append(f"事後の関門の束: 受け付け {len(rows)} 回が受け入れのテストの赤緑を確かめずに通した（理由: {' / '.join(whys)[:600]}）")
    agreed, undone, guards, gated = [], [], [], []
    for r in (r for r in got["trace"] if r.get("op") == impact.ACCEPT_OVERFLOW_OP):
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
    """範囲の相談の 1 問 1 答: 1 行目に回数と答えごとの数、続けて 1 相談 1 行"""
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


def _top(scope: str, path: str) -> str:
    top = path.split("/", 1)[0] if "/" in path else "（根）"
    return f"{scope} の {top}" if scope else top


def always_rows(got: dict) -> list:
    """clean が消したファイル・仕組みの異常の行（0 件でも、走らせていない・読めないを 0 件と分ける。元 fixbeside.always_rows のうち
    レンズの行でない部分。レンズの行は lens の block の report が返す）"""
    import listcut
    import oneline
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
    rows.append(ANOMALY_LINE)
    return rows


def next_items(got: dict, carry=()) -> list:
    """次の依頼の行 [{where, text}]（元 fixbeside.next_items のうち手直しの行でない部分）。手直しが残した穴と落ちたレンズの行は、
    delta-review と lens の block が出力の carry で返し、fixed が段ごとに和にして運ぶ（carry）。ここはそれを重ねずに並べ、閉鎖の表を
    読めなかった訳（got の closure_unread）を「確かめ直しの要あり」の行に足す"""
    items, seen = [], set()
    for row in [*(r for r in carry or () if isinstance(r, dict)),
                *({"where": "修正", "text": f"{x}（確かめ直しの要あり）"} for x in got.get("closure_unread") or [])]:
        key = (str(row.get("where")), str(row.get("text")))
        if key not in seen:
            seen.add(key)
            items.append({"where": key[0], "text": key[1]})
    return items


# ---------------------------------------------------------------- 2 つの段の合わせ（fixed）
def union(*lists) -> list:
    seen, out = set(), []
    for row in (x for rows in lists for x in rows or []):
        key = json.dumps(row, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


def _d(v) -> dict:
    return v if isinstance(v, dict) else {}


def held_of(values: dict) -> tuple[bool, str]:
    """held か（試験の関門から先へ進めない）と訳: 案の直しが要ったのに 2 度目の修正が走らなかった・after-fix か raise が止めた・fix か
    refix が止めの語（works:unrestored）を返した・fix が返らなかった（docs/design/line.md の 4.3。L-W47）"""
    fix, refix, after = values.get("fix"), values.get("refix"), _d(values.get("after_fix"))
    raise_ = _d(values.get("raise"))
    if fix is None:
        return True, HELD_UNRETURNED
    if after.get("stop_reason") or raise_.get("stop_reason"):
        return True, HELD_LINE
    if any(isinstance(r, dict) and r.get("stop_reason") for r in (fix, refix)):
        return True, HELD_STOP
    if after.get("replan") is True and refix is None:
        return True, HELD_REPLAN
    return False, ""


def go_done(values: dict, held: bool) -> tuple[bool, bool]:
    """go: held でなく、最後の段の fix の ok が真で、どの段の lens・delta-review も ok が偽でない（回さなかった段は数えない）。
    done: go で、最後の段の変更の確かめが通り、どの段の delta-review も回さなかったか pass（delta-review の設計書の 1.6）"""
    last = values["refix"] if values.get("refix") is not None else values["fix"]
    reviews = [r for r in (values.get("lens"), values.get("delta"), values.get("lens_2"), values.get("delta_2")) if isinstance(r, dict)]
    go = not held and _d(last).get("ok") is True and all(r.get("ok") is not False for r in reviews)
    deltas = [r for r in (values.get("delta"), values.get("delta_2")) if isinstance(r, dict)]
    done = go and _d(_d(last).get("checked")).get("ok") is True and all(r.get("pass") is True for r in deltas)
    return go, done


def left_rows(values: dict) -> list:
    """止めずに残りに数える行（7.2 の left）: 差分の審査が通らなかった・諦めた段と、案の直しを諦めた項目"""
    rows = []
    for n, key in ((1, "delta"), (2, "delta_2")):
        d = values.get(key)
        if isinstance(d, dict) and d.get("ok") is True and d.get("pass") is not True:
            rows.append({"where": "差分の審査", "text": f"{STAGE_NAMES[n - 1]}の差分の審査が通っていない（{d.get('status')}・"
                                                     f"{d.get('rounds')} 回。{d.get('reason') or '訳の記録が無い'}）"})
    for key in ("replan",):
        for r in _d(values.get(key)).get("gave_up") or []:
            if isinstance(r, dict):
                rows.append({"where": f"案の直しを終えられなかった項目 {r.get('item')}", "text": f"{r.get('why')}。裁定の文: {r.get('ruling')}"})
    return rows


def no_fix(values: dict) -> dict:
    """直す物が無い周の形: 直す物も差分も申し出も無く、最後のテストと独立の目へ進める（go）。目は回す（R2 が「直す物が無い」判定を
    確かめる。L-W07）。差分が無いので封じず当てない（merge-seal・merge-apply の when: が no_fix を読む）"""
    fix_in = _d(values.get("fix_in"))
    return {**empty(), "go": True, "done": True, "no_fix": True, "eyes_due": True, "plan": fix_in.get("plan"),
            "ripple": fix_in.get("ripple")}


def empty() -> dict:
    """どの欄も空の形（修正が走らなかった周の土台。fallback も同じ欄を持つ）"""
    return {"go": False, "done": False, "held": False, "no_fix": False, "diffed": False, "checks": False, "eyes_due": False,
            "skip_why": "", "rejudge": False, "refixed": False, "stages": [], "carry": [], "tdd": [], "units": [], "groups": [],
            "conflicts": [], "replan_items": [], "objection": "", "diff": None, "item_claims": None, "allowed_test_changes": [],
            "changed": None, "x_scalars": {}, "handoffs": [], "handoff_titles": {}, "mismatched": [], "plan_declared": [], "plan": None, "ripple": None,
            "left": [], "stop_reason": ""}


def fixed(values: dict) -> dict:
    """2 つの修正の段と段ごとの差分の審査を合わせる（docs/design/line.md の 4.3。今の fixed.py の決まりのまま）。values の鍵は
    fixed.py の入力の名（fix_in・fix・after_fix・raise・lens・delta・replan・refix・lens_2・delta_2。走らなかった物は None）"""
    import itemcommits
    fix_in = _d(values.get("fix_in"))
    if fix_in.get("no_fix") is True:
        return no_fix(values)
    fix, refix = values.get("fix"), values.get("refix")
    if fix is None and fix_in.get("go") is not True:
        return {**empty(), "plan": fix_in.get("plan"), "ripple": fix_in.get("ripple")}   # 承認ノードで止めた・計画ができなかった
    held, _ = held_of(values)
    go, done = go_done(values, held) if fix is not None else (False, False)
    fix = _d(fix)
    raise_ = values.get("raise")
    last = refix if refix is not None else fix
    last_delta = values.get("delta_2") if refix is not None else values.get("delta")
    diff = last_delta.get("diff") if isinstance(last_delta, dict) and last_delta.get("diff") else last.get("diff")
    own = next((s for s in (fix.get("stop_reason"), _d(refix).get("stop_reason")) if isinstance(s, str) and s), "")
    units = {}
    for unit in [*(fix.get("units") or []), *(_d(refix).get("units") or [])]:
        if isinstance(unit, dict):
            units[unit.get("unit_id")] = unit
    said = [str(r.get("objection") or "").strip() for r in (fix, _d(refix))]
    objection = "\n".join(dict.fromkeys(o for o in said if o))
    spec_stop = values.get("from_spec") is True and bool(objection or fix.get("replan_items"))
    if spec_stop:   # 仕様駆動の run: 案の直し（run の中の計画の審査）と再審へ進まず、異議を名指して止める
        held, go, done = True, False, False
    scalars = {**_d(fix.get("x_scalars")), **_d(_d(refix).get("x_scalars"))}
    again = values.get("replan") if refix is not None and isinstance(values.get("replan"), dict) else None
    stages = [{"stage": 1, "fix": values.get("fix"), "lens": values.get("lens"), "delta": values.get("delta")}]
    if refix is not None:
        stages.append({"stage": 2, "fix": refix, "lens": values.get("lens_2"), "delta": values.get("delta_2")})
    carry = union(*(_d(s.get(k)).get("carry") for s in stages for k in ("lens", "delta")))
    if isinstance(raise_, dict):
        checks, eyes_due, skip_why = raise_.get("checks") is True, raise_.get("eyes_due") is True, str(raise_.get("skip_why") or "")
    else:
        checks, eyes_due, skip_why = False, False, ""
    return {
        **empty(),
        "go": go, "done": done, "held": held, "diffed": diff is not None,
        "checks": checks, "eyes_due": eyes_due, "skip_why": skip_why,
        "rejudge": bool(objection) and not held and not spec_stop,
        "refixed": refix is not None,
        "stages": stages, "carry": carry,
        "tdd": [s["fix"].get("tdd") if isinstance(s["fix"].get("tdd"), list) else [] for s in stages if isinstance(s.get("fix"), dict)],
        "units": list(units.values()),
        "groups": union(fix.get("groups"), _d(refix).get("groups")),
        "conflicts": [c for c in (_d(refix).get("conflicts") or fix.get("conflicts"),) if c],
        "replan_items": fix.get("replan_items") or [],
        "objection": objection,
        "diff": diff,
        "item_claims": itemcommits.merged([r.get("item_claims") for r in (fix, refix) if isinstance(r, dict)]),
        "allowed_test_changes": union(fix.get("allowed_test_changes"), _d(refix).get("allowed_test_changes")),
        "changed": last.get("changed"),
        "x_scalars": scalars,
        "handoffs": union(fix.get("handoffs"), _d(refix).get("handoffs")),
        "handoff_titles": {**_d(_d(refix).get("handoff_titles")), **_d(fix.get("handoff_titles"))},
        "mismatched": union(fix.get("mismatched"), _d(refix).get("mismatched")),
        "plan_declared": union(fix.get("plan_declared"), _d(refix).get("plan_declared")),
        "plan": (again or fix_in).get("plan"),
        "ripple": (again or fix_in).get("ripple"),
        "left": left_rows(values),
        "stop_reason": _spec_objection() if spec_stop else own,
    }


# ---------------------------------------------------------------- 判定（再審が走れば再審）を後ろへ渡す（judged）
REJUDGE_WHERE = "判定（再審の結果）"           # lib/report.py の REJUDGE_WHERE と同じ字
REJUDGE_LEFT_WHERE = "判定（再審されずに残った異議）"
REJUDGE_FELL = "再審が返らなかった（diagnose の返す node が落ちた）"
COMPARED = ("new_open_units", "lowered", "unnamed_changed")


def _exit_keys(doc, field: str) -> list:
    return [k for k in (_d(doc).get(field) or []) if isinstance(k, str) and k]


def _judgment_units(ptr) -> dict | None:
    """判定の judgment の pointer の先の units {key: 単位}。無ければ空、読めなければ None"""
    try:
        doc = json.loads(resolve(ptr, "judgment").read_text(encoding="utf-8")) if ptr else {}
    except (OSError, *READ_ERRORS):
        return None
    return {u["key"]: u for u in _d(doc).get("units") or [] if isinstance(u, dict) and isinstance(u.get("key"), str)}


def rejudge_exit(rejudge: dict | None) -> tuple:
    """(再審の出口の中身, 読めなかった訳)。再審が走っていなければ (None, "")。出口は diagnose の出力の欄 rejudge_exit の先"""
    import oneline
    import report
    if rejudge is None:
        return None, ""
    ptr = rejudge.get("rejudge_exit")
    if ptr is None:
        return report.rejudge_exit(None)
    try:
        path = resolve(ptr, "rejudge_exit")
    except READ_ERRORS as error:
        return None, f"再審の出口の pointer を開けない（{type(error).__name__}: {oneline.one_line(error)}）"
    return report.rejudge_exit(path)


def rejudge_lines(rejudge: dict | None, objection: str, exit_: tuple, fixed_units: list) -> list:
    """決着した再審の結果の行と、再審されずに残った異議（元 runreport.rejudge_lines。報告の節「再審」と最後の承認ノードが読む）"""
    import oneline
    verdict = _d(rejudge).get("rejudge_verdict") if rejudge else None
    objection = oneline.one_line(objection or "")
    left = [f"再審されずに残った異議: {objection}"] if objection and not verdict else []
    if rejudge is None:
        return left
    doc, why = exit_
    if doc is None:
        return [f"再審の記録が読めない（{why}）——再審の結果を確かめる", *left]
    raw = [v for v in doc.get("verdicts") or []] if isinstance(doc.get("verdicts"), list) else []
    obj = oneline.one_line(doc.get("objection") or "") or objection
    opened, lowered = rejudge_opened(doc, fixed_units), rejudge_lowered(rejudge, doc)
    if not (raw or opened or lowered or obj):
        return left
    verdicts = "・".join(v if isinstance(v, str) and v else "（判定の欄が無い）" for v in raw) or "（判定の往復が無い）"
    return [f"再審の結果（{len(raw)} 往復）: {verdicts}" + (f"（異議: {obj}）" if obj else ""),
            *[f"  - 再審が直す単位にした（この run では直していない——次の run に渡す）: {k}" for k in opened],
            *[f"  - 再審が block から {label} に下げた（拒まずに見せる——人が確かめる）: {k}" for k, label in lowered],
            *left]


def rejudge_opened(exit_doc, fixed_units: list) -> list:
    """再審が直す単位にした単位のうち修正の段が受けていない物（再審の出口の new_open_units。この run では直していない）"""
    done = {u.get("unit_id") for u in fixed_units or [] if isinstance(u, dict)}
    return [k for k in _exit_keys(exit_doc, "new_open_units") if k not in done]


def rejudge_lowered(rejudge: dict | None, exit_doc) -> list:
    """再審が block から他のラベルに下げた単位 [(key, 今のラベル)]（今のラベルは再審の judgment）"""
    now = _judgment_units(_d(rejudge).get("judgment"))
    if now is None:
        return [(k, "（再審の判定を読めない）") for k in _exit_keys(exit_doc, "lowered")]
    return [(k, str(_d(now.get(k)).get("label") or "（判定に無い）")) for k in _exit_keys(exit_doc, "lowered")]


def rejudge_carry(rejudge: dict | None, objection: str, exit_doc, fixed_units: list) -> list:
    """次の依頼の行（元 runreport.next_request の再審の行）: 再審の答えか残った異議・再審が直す単位にした単位・block から下げた単位"""
    import oneline
    verdict = _d(rejudge).get("rejudge_verdict") if rejudge else None
    objection = oneline.one_line(objection or "")
    items = []
    if isinstance(verdict, str) and verdict:
        items.append({"where": REJUDGE_WHERE, "text": f"再審: {verdict}" + (f"（異議: {objection}）" if objection else "")})
    elif objection:
        items.append({"where": REJUDGE_LEFT_WHERE, "text": objection})
    items += [{"where": k, "text": f"{k}（再審が直す単位にした——この run では直していない）"} for k in rejudge_opened(exit_doc, fixed_units)]
    items += [{"where": k, "text": f"{k}（再審が block から {label} に下げた——人が確かめる）"}
              for k, label in rejudge_lowered(rejudge, exit_doc)]
    return items


def judged(fix_in: dict, rejudge: dict | None, *, due: bool, objection: str, fixed_units: list = ()) -> dict:
    """判定を後ろへ渡す（docs/design/line.md の 4.4。今の judged.py のまま）: 再審が走れば再審の units・judgment・rejudge_*、走らなければ
    1 回目。answer_ties・materials・out_of_purpose は 1 回目の物を使い続ける。前後の比べは再審の出口から（読めなければ訳を unread）。
    再審が止まった（ok が偽）・走るはずが返らなかった時は止めの語を stop_reason で返し、試験の関門・独立の目・merge へ進めない（L-D48）"""
    import stopby
    fix_in = _d(fix_in)
    first = {key: fix_in.get(key) for key in ("answer_ties", "materials", "out_of_purpose")}
    exit_ = rejudge_exit(rejudge)
    base = {**first, "rejudged": rejudge is not None, "lines": rejudge_lines(rejudge, objection, exit_, list(fixed_units)),
            "carry": rejudge_carry(rejudge, objection, exit_[0], list(fixed_units))}
    if rejudge is None:
        stop = stopby.REJUDGE if due else ""
        return {**base, "units": fix_in.get("units") or [], "judgment": fix_in.get("judgment"), "rejudge_verdict": None,
                "rejudge_exit": None, "rejudge_diff": None, **{k: [] for k in COMPARED},
                "unread": REJUDGE_FELL if due else "", "stop_reason": stop}
    doc, why = exit_
    compared = ({k: _exit_keys(doc, k) for k in COMPARED} if doc is not None else {k: [] for k in COMPARED})
    stop = "" if rejudge.get("ok") is True else (rejudge.get("stop_reason") or stopby.REJUDGE)
    return {**base, "units": rejudge.get("units") or [], "judgment": rejudge.get("judgment"),
            "rejudge_verdict": rejudge.get("rejudge_verdict"), "rejudge_exit": rejudge.get("rejudge_exit"),
            "rejudge_diff": rejudge.get("rejudge_diff"), **compared,
            "unread": "" if doc is not None else f"再審の前後を比べられない（{why}）", "stop_reason": stop}
