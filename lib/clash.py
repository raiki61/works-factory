"""組の合わせの直し（持ち主の決め clash-goes-to-ruling）。並べた組の子の差分を親の作業ツリーへ当てて確かめ直しが赤になった組を、
合わせ役がその組の変えたファイルの中だけで直し、直せなければ「組どうしの合わせの食い違い」の申し出（conflict.JOIN_SOURCE）を
裁定役に回す。

組を当てるノード（join）は赤の組を戻して後の組を当て続け、戻した組と字で当たらなかった組をこの控えに「直し待ち」で積む（record）。合わせのループは組を 1 つずつ
控えの差分から当て直し（stage）、合わせ役の返答を修正役と同じ 3 つの軸で受け付ける（problems: 触ってよいのは組が変えたファイル
だけ・赤だった試験が緑に戻る・許しの無い試験の書き換えは拒む。と書き込みの出どころ）。通れば組を戻せた組にし（settle_repaired）、
直せなければ当て直す前の木へ戻して申し出を積む（settle_parked）。裁定の後のループ（段 RULED）は、直す裁定（conflict.FIX_DECISIONS）を
受けた組だけを当て直して同じ受け付けを通し、それでも直せなければ ask_human つき（by BY_RULED_GIVE_UP）で人に回す。どの時点でも
作業ツリーは緑か合わせ役の手の中に在る。

このモジュールが持つ物（place は fix の run の置き場、repo は親の作業ツリー、skip は除くパスの頭）:
- FILE（置き場の控え {clashes: [{group_id, unit_ids, patch, names, shared, why, kind?, state, pass?, before?, staged?, marked?,
  requests?}]}。kind は KINDS（RED は確かめ直しが赤で戻した組、TEXT は字で当たらなかった組。無い行は RED）、state は PENDING・
  STAGED・REPAIRED・PARKED、pass は最後に扱った段、marked は当て直しで食い違いの印を書いたパス）と new_row(...)・record(place, rows)・load(place)
- todo(place, pass_): その段で扱う組の id（控えの順。FIRST は直し待ちと当て直し中、RULED は FIRST で回した組のうち、その組の
  申し出が全部直す裁定を受けた物と当て直し中）
- stage(place, repo, gid, pass_, skip): 控えの差分を 3 方向で当て直す（解けない食い違いは印つきで当てる。当てる前と後の木を控える。
  印を許しの無いテストのファイルに書いたら当て直せないとする）
- problems(place, repo, gid, reply, *, start, cases, skip, name, k): 受け付けの照らし（文の並び。空なら通る）
- settle_repaired(place, repo, gid, *, log): 組を戻せた組にする（join.json の行と単位・書き込みの記録・TDD のループの状態）
- settle_parked(place, repo, gid, *, pass_, why, skip): 当て直す前の木へ戻し、申し出を積み、join.json の行に訳を置く
- cites(patch_text, files): 申し出の名指し（<パス>:<差分の最初の塊の新しい側の始めの行>）
- brief(place, gid, pass_)・prompt(rules, pass_, values, ...): 合わせ役の材料のファイルと指示書
標準ライブラリだけ。期限は持たない。
"""
import os
import pathlib
import re
import sys

sys.dont_write_bytecode = True

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import conflict  # noqa: E402
import fixboard  # noqa: E402
import fixrules  # noqa: E402
import impact  # noqa: E402
import oneline  # noqa: E402
import rulebook  # noqa: E402
import stopby  # noqa: E402
import tddloop  # noqa: E402
import unittrees  # noqa: E402

FILE = "clash.json"
BRIEF = "clash-brief-{gid}.json"
PROMPT = "prompt-clash-{gid}.md"
STATES = (PENDING, STAGED, REPAIRED, PARKED) = ("pending", "staged", "repaired", "parked")
PASSES = (FIRST, RULED) = ("first", "ruled")
KINDS = (RED, TEXT) = ("red", "text")
ROLES = {FIRST: "clash", RULED: "clash-ruled"}
CANNOT = "cannot"                   # 合わせ役の返答の handled の語: 直せない（回数を待たずに申し出へ）
BY_RULED_GIVE_UP = stopby.declare("clash-ruled-give-up",
                                  "裁定の by: 組どうしの合わせの食い違いを裁定の直しで当て直しても受け付けを通らず、人に回した")
PARKED_TAIL = "。合わせ役が直せず、申し出 {ids} を裁定役に回した（控えの差分 {patch}）"
HUMAN_TAIL = "。裁定の直しでも合わせ役が直せず、申し出 {ids} を人に回した（控えの差分 {patch}）"
NOT_APPLIED = "控えの差分が今の作業ツリーに当たらない（{why}）"
LIMIT = "合わせのループの上限の周（{limit}）に届いたので、直さずに回した"
GAVE_UP = "合わせ役の返答が {n} 回とも受け付けを通らなかった（拒否の理由の全部 {file}）"
SAID_CANNOT = "合わせ役が直せないと答えた: {how}"
CLAIM = "組 {gid} の直しを親の作業ツリーで前の組と合わせると試験が赤（{red}）。{why}。控えの差分: {patch}"
TEXT_CLAIM = "組 {gid} の直しが親の作業ツリーで前の組の直しと同じ所を変え、字で当たらない（{red}）。{why}。控えの差分: {patch}"
MARKED_TESTS = ("字で当たらない所が許しの無いテストのファイルに在り、合わせ役は印を解けない（テストの範囲の裁定 fix_test_scope が"
                "要る）: {paths}")
UNRESOLVED = "食い違いの印が残っている（印を解いて両方の組の直しを両立させよ）: {paths}"
RULED_CLAIM = "裁定 {ids} の直しも通らなかった: "
OUTSIDE = "組が変えたファイルの外を変えた（触ってよいのは {allowed} だけ）: {paths}"
TESTS = "許しの無いテストのファイルを変えた（テストを緩めて緑にしない。直すべきテストなら直せないと答えて裁定に回せ）: {paths}"
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")


# ---------------------------------------------------------------- 控え
def _path(place) -> pathlib.Path:
    return pathlib.Path(place) / FILE


def load(place) -> list:
    """控えの組の行（控えの順。無ければ空）"""
    doc = fixboard.read_json(_path(place), {}) or {}
    return [r for r in doc.get("clashes") or [] if isinstance(r, dict)]


def _save(place, rows) -> None:
    fixboard.write_json(_path(place), {"clashes": rows})


def new_row(group_id: str, unit_ids, patch: str, names, earlier, why: str, kind: str) -> dict:
    """record に渡す組の行: names は組が変えたファイル、earlier は前に当てた組が変えたファイル（重なりを shared に置く）"""
    if kind not in KINDS:
        raise ValueError(f"合わせの控えの kind は {KINDS} のどれか: {kind!r}")
    return {"group_id": group_id, "unit_ids": list(unit_ids), "patch": patch, "names": list(names),
            "shared": sorted(set(names) & set(earlier)), "why": why, "kind": kind}


def record(place, rows) -> None:
    """組を当てるノードが、確かめ直しが赤で戻した組と字で当たらなかった組 rows（new_row の形。当てた順）を直し待ちで控える。
    rows が空なら何も書かない"""
    if rows:
        _save(place, [{**r, "state": PENDING} for r in rows])


def _row(rows, gid) -> dict:
    got = next((r for r in rows if r.get("group_id") == gid), None)
    if got is None:
        raise ValueError(f"合わせの控えに組 {gid!r} が無い")
    return got


def requests(place, row) -> list:
    """組の申し出の行（控えの requests の id。2 回目の修正の段が写した前の段の行 PRIOR は外す）"""
    ids = set(row.get("requests") or [])
    return [r for r in conflict.items(place) if r.get("id") in ids and not r.get(conflict.PRIOR)]


def todo(place, pass_: str) -> list:
    """段 pass_ で扱う組の id（控えの順）。当て直し中（STAGED）の組を先に続ける"""
    if pass_ not in PASSES:
        raise ValueError(f"合わせの段は {PASSES} のどれか: {pass_!r}")
    out = []
    for r in load(place):
        if r["state"] == STAGED and r.get("pass") == pass_:
            out.insert(0, r["group_id"])
        elif pass_ == FIRST and r["state"] == PENDING:
            out.append(r["group_id"])
        elif pass_ == RULED and r["state"] == PARKED and r.get("pass") == FIRST:
            got = requests(place, r)
            if got and all(conflict.decision(x) in conflict.FIX_DECISIONS for x in got):
                out.append(r["group_id"])
    return out


def ruled_paths(place, row) -> list:
    """組の申し出が受けた直す裁定の範囲 limits のパス（触ってよいファイルに足す）"""
    out = []
    for x in requests(place, row):
        for lim in (x.get(conflict.RULING) or {}).get("limits") or []:
            got = conflict.parse_limit(lim) if isinstance(lim, str) else None
            if got and got[0] not in out:
                out.append(got[0])
    return out


# ---------------------------------------------------------------- 組の結果
def result(place, gid) -> dict:
    """組の子の結果（置き場の groups.json の out_dir/<group_id>/result.json。fixboard.usable_result）。使えなければ ValueError"""
    plan = fixboard.read_json(pathlib.Path(place) / fixboard.GROUPS_FILE, {}) or {}
    got = fixboard.usable_result(pathlib.Path(plan.get("out_dir") or "") / gid)
    if got is None:
        raise ValueError(f"組 {gid} の子の結果が読めない")
    return got


def _joined(place) -> dict:
    doc = fixboard.read_json(pathlib.Path(place) / fixboard.JOIN_FILE)
    if not isinstance(doc, dict) or not isinstance(doc.get("groups"), list):
        raise ValueError(f"置き場に {fixboard.JOIN_FILE} が無い")
    return doc


def named_tests(place, gid) -> list:
    """確かめ直しで走らせる名指し: 今戻せている組の全部とこの組が赤 → 緑を確かめた名指し（組を当てるノードと同じ決まり）"""
    back = [g["group_id"] for g in _joined(place)["groups"] if g.get("returned") and g["group_id"] != gid]
    out: list = []
    for g in [*back, gid]:
        for t in fixboard.child_verified(result(place, g)):
            if t not in out:
                out.append(t)
    return out


# ---------------------------------------------------------------- 当て直し
def _back_to(repo, before: str, skip) -> None:
    tddloop.restore_paths(repo, before, fixboard.touched_since(repo, before, skip))


def stage(place, repo, gid: str, pass_: str, skip=()) -> tuple:
    """組 gid の控えの差分を作業ツリーへ 3 方向で当て直す（組を当てるノードと同じ当て方と試験のファイルの挿しの合わせ。それでも解けない
    食い違いは印つきで当て、印を書いたパスを marked に控える。unittrees.apply の marked）。(当たったか, 訳)。
    当てる前の木 before を先に控え、当てた後の木 staged を控える。もう当て直した組（STAGED）は何もしない。前の起動が当てる途中で
    落ちた組は before へ戻してから当て直す。印を許しの無いテストのファイルに書いた時は (False, MARKED_TESTS)（印つきの木は
    呼び手の settle_parked が before へ戻す）"""
    rows = load(place)
    row = _row(rows, gid)
    if row["state"] == STAGED:
        return True, ""
    if row.get("before") and row.get("pass") == pass_:
        _back_to(repo, row["before"], skip)
    r = result(place, gid)
    union = sorted({f for u in fixboard.child_tdd_units(r) for f in fixboard.unit_test_files(u)}
                   | {t["path"] for t in fixboard.child_allowed_rows(r)})
    row.update(before=tddloop.snapshot(repo), staged="")
    row["pass"] = pass_
    _save(place, rows)
    patch = pathlib.Path(row["patch"]).read_text(encoding="utf-8", errors="surrogateescape")
    marked: list = []
    ok, why = unittrees.apply(repo, patch, union=union, check=unittrees.tests_unique, marked=marked)
    if not ok:
        return False, NOT_APPLIED.format(why=oneline.one_line(why)[:300])
    locked = _unpermitted_tests(r, set(fixboard.allowed_tests(place, [r])), marked)
    if locked:   # 印を残しても消しても受け付けが拒む（problems の UNRESOLVED と TESTS）。回さずに裁定へ
        return False, MARKED_TESTS.format(paths="・".join(locked))
    row.update(state=STAGED, staged=tddloop.snapshot(repo), marked=marked)
    _save(place, rows)
    return True, ""


# ---------------------------------------------------------------- 受け付け
def _unpermitted_tests(r, permits: set, paths) -> list:
    """paths のうち、許し permits の無いテストのファイル（impact.is_test_file。宣言は組の子の結果 r の TDD のループの単位のテストの
    ファイル。組自身のテストであることは許しにならない）"""
    declared = {f for u in fixboard.child_tdd_units(r) for f in fixboard.unit_test_files(u)}
    return sorted(p for p in paths if impact.is_test_file(p, declared) and p not in permits)


def problems(place, repo, gid: str, reply: dict, *, start: dict, cases, skip=(), name: str = "", k: int = 1) -> list:
    """合わせ役の返答の受け付けの照らし（文の並び。空なら通る）。当て直しで印を書いたファイル（marked）に印が残れば UNRESOLVED。
    当て直した後の木から今の作業ツリーで変わったパスが:
    1. 組が変えたファイル（控えの names）と、段 RULED なら直す裁定の範囲のパス（ruled_paths）の和に収まる
    2. テストのファイル（impact.is_test_file。宣言は組の TDD のループの単位のテストのファイル）なら、許しの訳（fixboard.allowed_tests。
       承認済みの修正案・範囲の相談の合意・裁定 fix_test_scope・子の結果の許し）に在る（組自身のテストであることは許しにならない）
    3. 返答の files か bash_writes に在る（fixboard.undeclared_writes）
    の 3 つが通れば、4. 組の名指しのテストの中身が子の終わりの木と同じ（許しの在るテストのファイルは見ない）で、確かめ直し
    （fixboard.rerun_problem。名指しは named_tests、走らせ直しの置き場は <name>-<k>）が緑。start は始めの記録、cases は直す前の結末"""
    row = _row(load(place), gid)
    r = result(place, gid)
    staged = row.get("staged") or ""
    touched = fixboard.touched_since(repo, staged, skip)
    allowed = set(row["names"]) | (set(ruled_paths(place, row)) if row.get("pass") == RULED else set())
    out = []
    left = unittrees.markers_left(repo, row.get("marked") or [])
    if left:
        out.append(UNRESOLVED.format(paths="・".join(left)))
    outside = sorted(p for p in touched if p not in allowed)
    if outside:
        out.append(OUTSIDE.format(allowed="・".join(sorted(allowed)), paths="・".join(outside)))
    tdd_rows = fixboard.child_tdd_units(r)
    permits = set(fixboard.allowed_tests(place, [r]))
    tests = _unpermitted_tests(r, permits, touched)
    if tests:
        out.append(TESTS.format(paths="・".join(tests)))
    out += fixboard.undeclared_writes({"changes": [{"files": [f for f in reply.get("files") or [] if isinstance(f, str)]}],
                                       "bash_writes": reply.get("bash_writes") or []}, repo, staged, skip=skip)
    if out:
        return out
    red = fixboard.tests_moved(repo, r["end_tree"], tdd_rows, set(row["names"]) - permits) or fixboard.rerun_problem(
        place, repo, start.get("tdd_suite", ""), cases, named_tests(place, gid), name=f"{name or 'clash'}-{gid}-{k}",
        shared=row.get("shared") or [], test_cmd=fixboard.rerun_cmd(place, r, start.get("test_cmd", "")))
    return [f"直した後の確かめ直しが赤のまま: {red}"] if red else []


# ---------------------------------------------------------------- 片付け
def _rel(place, patch: str) -> str:
    return os.path.relpath(patch, place)


def _settle_join(place, gid: str, *, returned: bool, reason: str, mark: dict, extra=None) -> None:
    """join.json の組 gid の行と単位を置き直す（単位は fixboard.join_rows の決まりで組み直す。当ててから戻したパス backed_out は
    残す）"""
    doc = _joined(place)
    old = next(g for g in doc["groups"] if g.get("group_id") == gid)
    got = (result(place, gid) if returned else None, returned, reason)
    rows, units = fixboard.join_rows([{"group_id": gid, "unit_ids": old["unit_ids"]}], {gid: got},
                                     {gid: old.get("backed_out") or []}, extra)
    doc["groups"] = [{**rows[0], "clash": mark} if g.get("group_id") == gid else g for g in doc["groups"]]
    doc["units"] = [u for u in doc.get("units") or [] if u.get("group_id") != gid] + units
    fixboard.write_json(pathlib.Path(place) / fixboard.JOIN_FILE, doc)


def settle_repaired(place, repo, gid: str, *, log=None) -> None:
    """合わせ役の直しが受け付けを通った組 gid を、戻せた組にする: join.json の行（returned・理由は空・欄 clash の outcome は
    REPAIRED）と単位（子の結果の結末）、子の書き込みの記録を親の記録へ写し（writes.carry_children。log が在る時）、子の TDD の
    ループの状態を親の置き場へ写す（fixboard.adopt_tdd_states）。組を当てるノードが戻せた組にすることと同じ"""
    import writes
    import writelog
    rows = load(place)
    row = _row(rows, gid)
    r = result(place, gid)
    _settle_join(place, gid, returned=True, reason="",
                 mark={"outcome": REPAIRED, "requests": list(row.get("requests") or []), "patch": _rel(place, row["patch"])})
    if log is not None and pathlib.Path(log).is_file() and r.get("worktree"):
        writes.carry_children(log, repo, [(r["worktree"], writelog.log_here(r["worktree"]), row["names"])])
    fixboard.adopt_tdd_states(place, [r], repo)
    row.update(state=REPAIRED, staged="", before="", marked=[])
    _save(place, rows)


def cites(patch_text: str, files) -> list:
    """申し出の名指し: files ごとに <パス>:<差分のそのファイルの最初の塊の新しい側の始めの行>（取れなければ 1）"""
    first, cur = {}, None
    for ln in patch_text.splitlines():
        if ln.startswith("diff --git a/") and " b/" in ln:
            cur = ln.rsplit(" b/", 1)[1]
        elif cur and cur not in first and (m := HUNK.match(ln)):
            first[cur] = max(int(m[1]), 1)
    return [f"{f}:{first.get(f, 1)}" for f in files]


def settle_parked(place, repo, gid: str, *, pass_: str, why: str, skip=()) -> list:
    """組 gid を直さずに申し出へ回す: 当て直していれば当て直す前の木へ戻し（作業ツリーは緑に戻る）、組の単位ごとの申し出
    （conflict.clash_claims。段 RULED は ask_human と BY_RULED_GIVE_UP の裁定つきで人に回す）を積み、控えの差分を名指し
    （conflict.mark_clash_patch）、join.json の行の理由に訳を足して欄 clash の outcome を PARKED にする。戻せなければ組を当てた
    ままと名指し（欄 unrestored。fixboard.held が後のノードを止める）。積んだ申し出の id を返す"""
    rows = load(place)
    row = _row(rows, gid)
    before = row.get("before") if row.get("pass") == pass_ else ""
    stuck = []
    if before:
        try:
            _back_to(repo, before, skip)
        except Exception as e:  # noqa: BLE001  戻せない組を当てていないと言わない（組を当てるノードと同じ）
            stuck = fixboard.touched_since(repo, before, skip)
            why += "。" + fixboard.UNRESTORED.format(error=f"{type(e).__name__}: {oneline.one_line(e)[:300]}", why=row["why"])
    patch = pathlib.Path(row["patch"])
    text = patch.read_text(encoding="utf-8", errors="surrogateescape") if patch.is_file() else ""
    said = (TEXT_CLAIM if row.get("kind") == TEXT else CLAIM).format(gid=gid, red=oneline.one_line(row["why"])[:300], why=why, patch=patch)
    prior = [x["id"] for x in requests(place, row)]
    ruling = None
    if pass_ == RULED:
        said = RULED_CLAIM.format(ids="・".join(prior)) + said
        ruling = {"decision": conflict.ASK, "text": said, "limits": [], "by": BY_RULED_GIVE_UP}
    ids = conflict.park(place, conflict.clash_claims(row["unit_ids"], cites(text, row.get("shared") or row["names"]), said),
                        source=conflict.JOIN_SOURCE, ruling=ruling, pass_=RULED if pass_ == RULED else None)
    conflict.mark_clash_patch(place, ids, str(patch))
    if ruling:
        conflict.write_rulings(place)
    every = list(dict.fromkeys([*(row.get("requests") or []), *ids]))
    tail = (HUMAN_TAIL if pass_ == RULED else PARKED_TAIL).format(ids="・".join(ids), patch=patch)
    _settle_join(place, gid, returned=False, reason=row["why"] + tail,
                 mark={"outcome": PARKED, "requests": every, "patch": _rel(place, str(patch))},
                 extra={gid: stuck} if stuck else None)
    row.update(state=PARKED, requests=every, staged="", before="", marked=[])
    row["pass"] = pass_
    _save(place, rows)
    return ids


# ---------------------------------------------------------------- 合わせ役の材料と指示書
def brief(place, gid: str) -> pathlib.Path:
    """合わせ役の材料のファイル（置き場の clash-brief-<group_id>.json）: 組・単位・控えの差分・触ってよいファイル・前の組とも
    重なったファイル・食い違いの種（kind）・確かめ直しの赤の文か字で当たらなかった訳・食い違いの印を書いたファイル・走らせる名指し・
    戻せている組と、段 RULED なら裁定の文のファイルと組の申し出の裁定"""
    row = _row(load(place), gid)
    ruled = row.get("pass") == RULED
    doc = {"group_id": gid, "unit_ids": row["unit_ids"], "patch_file": row["patch"],
           "files": sorted(set(row["names"]) | (set(ruled_paths(place, row)) if ruled else set())),
           "shared": row.get("shared") or [], "kind": row.get("kind") or RED, "red": row["why"],
           "conflicted": row.get("marked") or [], "named_tests": named_tests(place, gid),
           "returned_groups": [g["group_id"] for g in _joined(place)["groups"] if g.get("returned")]}
    if ruled:
        doc["rulings_file"] = str(pathlib.Path(place) / conflict.RULINGS_FILE)
        doc["rulings"] = [{"id": x["id"], **{k: x[conflict.RULING].get(k) for k in ("decision", "text", "limits")}}
                          for x in requests(place, row)]
    return fixboard.write_json(pathlib.Path(place) / BRIEF.format(gid=gid), doc)


VALUES = ("brief_file", "patch_file")


def prompt(rules, pass_: str, values: dict, *, reject_file: str = "", iteration: int = 1, lang: str = "") -> str:
    """合わせ役の指示書（純粋）: 始めの記録の 2 行（fixrules.start_lines）→ 役の頭（clash-head-<段>。values の brief_file・
    patch_file で穴を埋める）→ 決まり（clash-keep）→ 返答（clash-reply）→ 返答の後に当たる物（clash-tail）を rulebook.render で繋ぐ。
    書く役の決まりの正本は載せない（返答の形が違い、食い違いの申し出の出口も無い。直せない時の出口は返答の cannot）。reject_file
    （この組の拒否の理由の全部のファイル）が在れば 1 行目で名指す。rules は決まりのファイル（呼び手の script が渡す）"""
    if pass_ not in PASSES:
        raise rulebook.Unfilled(f"合わせの段 {pass_!r} は {PASSES} のどれでもない")
    r = rulebook.sections(rules)
    always = "いつも"
    parts = [("clash-head", rulebook.fill(r[f"clash-head-{pass_}"], rulebook.pick(values, VALUES)), always + "（役・材料・run の値）"),
             ("clash-keep", r["clash-keep"], always + "（合わせ役の決まり）"),
             ("clash-reply", r["clash-reply"], always + "（返答の欄）"),
             ("clash-tail", r["clash-tail"], always + "（返答の後に当たる物）")]
    return rulebook.render(ROLES[pass_], iteration, parts, before=fixrules.start_lines(values), reject_file=reject_file,
                           lang=lang)["text"]

