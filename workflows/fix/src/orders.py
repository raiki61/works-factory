"""組の子の頭の注文（docs/plans/2026-10-24-fix-weapons.md の 2.1・4.1 の 3。node orders。今の tdd-go に替わる）。

振り分け（route-loop）の後に、計画の語・消す名・振り分けの答えから型の表（route.weapon_of）で単位ごとに型を引き、型ごとの注文を
orders/<weapon>.json（schemas/weapon-order.schema.json の形）に書き、索引を orders.json に書く。tdd に引いた単位は輪の状態に
並べ（tdd.assign）、YAML の when: へは型ごとの輪を回すかの真偽だけを返す（憲法の 1）。

型ごとの注文は、tdd の輪の後の書き手の輪（writers-loop）が型ごとの書き手で 1 つずつ受ける（docs/plans/2026-10-25-fix-weapons-stage1-b.md
の 1。src/writers.py）。tdd の輪が緑にした単位の行は tdd の輪の閉じの書き手 tdd-close が書くので、書き手の輪は止めの無い組でいつも回る（writer）。

- compute(place, repo) -> {tdd, writer, stop, reason}
- no_suite_why(place) -> 組の頭で止める訳（下書き 3.9 の止め方の 1。止めないなら空）
- weapons(place) -> {単位: 型の名}: 書いた注文の索引から引く（受け付けが型の義務を引く口）
- later_agreed(place) -> 段の頭の後に取れた範囲の相談の合意の許しの範囲（凍結の照らし duties.frozen_by_returns が足す）
- stage_of(place) -> 段の番（1 回目の段 2n−1。n は修正の block を入れた回で、前の段の申し送りが在れば 2）
"""
from __future__ import annotations

import pathlib

import conflict   # lib/
import groups     # lib/
import jsonfile   # lib/
import planmarks  # lib/

from src import basecase, board, common, files, intake, route, runvals, tdd

GATE_STOP = "起動スクリプトが書き直しても壊れたまま"
NO_SUITE_STOP = ("試験の実行器が無いか走らない組（{why}）で、計画の語が static でない単位 {keys} が在る——型を回さず、確かめていない"
                 "直しを書き進めずに止めた（下書き 3.9。static だけの組は止めない）")


def stage_of(place, pass_: str = "first") -> int:
    """段の番（下書き 2.1 の stage）: 修正の block を入れた回 n（前の段の申し送り prior が在れば 2）の、1 回目の段は 2n−1、
    裁定の後の段は 2n"""
    n = 2 if (pathlib.Path(place) / files.PRIOR_DIR).is_dir() else 1
    return 2 * n - 1 if pass_ == "first" else 2 * n


def no_suite_why(place) -> str:
    """組の頭の止め no-suite の yes/no（下書き 3.9 の止め方の 1）: 組に計画の語が static でない単位が在り、かつ元の結末が取れていない
    （実行器が無い・起こせない・結末が取れない）が起動スクリプトの壊れ（suite_broken。書き直しの道が持つ）でもない時の訳。でなければ空。
    前の半分は振り分けの AI の答え無しで決まるので、止める組では振り分けの AI を起こさない"""
    place = pathlib.Path(place)
    started = _start(place)
    if started.get("suite_broken") is True:
        return ""
    base = basecase.read(place)
    if base and base.get("taken"):
        return ""
    keys = [str(k) for k in (intake.load(place).get("group") or {}).get("unit_ids") or []]
    words = route.plan_words(place, keys)
    moving = [k for k in keys if words.get(k) != "static"]
    if not moving:
        return ""
    return NO_SUITE_STOP.format(why=str(started.get("reason") or basecase.NO_SUITE), keys=moving[:20])


def _start(place) -> dict:
    got = board.read_json(pathlib.Path(place) / board.TDD_START_FILE)
    return got if isinstance(got, dict) else {}


def _unit_rows(place, keys, round_: int = 1) -> dict:
    """単位 → 注文の単位の行の材料 {items, tests, scope}（凍結した計画の欄から機械が引く。欄の無い run は空）"""
    try:
        fields = conflict.frozen_fields(pathlib.Path(place), round_) or []
    except ValueError:
        fields = []
    out = {k: {"items": [], "tests": [], "allowed": [], "out": []} for k in keys}
    for n, f in enumerate(fields, 1):
        if not isinstance(f, dict):
            continue
        for k in f.get("unit_keys") or []:
            if k not in out:
                continue
            row = out[k]
            row["items"].append(n)
            for key in ("tests", "rewrite_tests"):
                row["tests"] += [r["id"] for r in f.get(key) or [] if isinstance(r, dict) and isinstance(r.get("id"), str)
                                 and r["id"] not in row["tests"]]
            row["allowed"] += [g for g in f.get("allowed_paths") or [] if isinstance(g, str) and g not in row["allowed"]]
            row["out"] += [o for o in f.get("out_of_scope") or [] if isinstance(o, dict) and o not in row["out"]]
    return out


KINDS = {conflict.PLAN_TEST_ID: ("rewrite", True), conflict.REMOVES_TEST_ID: ("remove", False),
         conflict.AGREED_TEST_ID: ("agreed", False), conflict.RULED_TEST_ID: ("ruled", False),
         conflict.BROKEN_TEST_ID: ("broken", False), conflict.AMENDED_TEST_ID: ("replan", False)}


def _kind(row_id: str):
    for head, kd in KINDS.items():
        if row_id == head or row_id.startswith(head + "-"):
            return kd
    return None


def permits_for(place, items: list, *, stage: int, rulings: bool) -> list:
    """注文の permits（下書き 2.1）: conflict.test_permits の行を、この注文の項目で絞った物（修正案の行は項目の番号で絞り、ほかの行は
    run の全体の許しなのでそのまま）から、run の今までの返しの控え returns/ の evidence.added・rewritten の試験と tdd が凍らせた
    ファイルを引く（前の型の物を引く）。案の直しの許し replan は引かない。裁定の行 ruled は、その裁定の段の番以下で返した物を引かない
    （stage の例外。裁定の段の番は裁定の控えの欄 stage。欄の無い裁定は 0 と読み、どの返しも引く）。行は {kind, duty, test, source}
    （test は範囲の文字列か名指しの id。replan の行は単位の並び units を source に持つ）"""
    try:
        rows = conflict.test_permits(pathlib.Path(place), rulings=rulings)
    except ValueError:
        rows = []
    prior = returns_of(place)
    ruled_at = _ruling_stages(place) if rulings else {}
    out = []
    for r in rows:
        kd = _kind(str(r.get("id") or ""))
        if kd is None:
            continue
        kind, duty = kd
        if kind in ("rewrite", "remove"):
            n = str(r["id"]).rsplit("-", 1)[-1]
            if not n.isdigit() or int(n) not in items:
                continue
        test = str(r.get("test") or r.get("limit") or ",".join(r.get("units") or []))
        if kind != "replan" and _pulled(test, prior, ruled_at.get(str(r.get("id")), 0) if kind == "ruled" else None):
            continue
        out.append({"kind": kind, "duty": duty, "test": test, "source": str(r.get("source") or "")})
    return out


def _ruling_stages(place) -> dict:
    """裁定の許しの行の id（conflict.RULED_TEST_ID-<申し出の id>）→ その裁定の段の番（裁定の控えの欄 stage。無ければ 0）"""
    try:
        rows = conflict.items(pathlib.Path(place))
    except ValueError:
        return {}
    return {f"{conflict.RULED_TEST_ID}-{r.get('id')}": int((r.get("ruling") or {}).get("stage") or 0)
            for r in rows if isinstance(r, dict) and isinstance(r.get("ruling"), dict)}


def _pulled(test: str, prior: list, ruled_stage) -> bool:
    """許しの行 test（名指しの id か範囲の文字列）が、前の返しの足した・書き換えた試験か凍ったファイルに当たるか。ruled_stage が
    在れば、その段の番以下で返した物は引かない（裁定がそれを見て許した）"""
    path = common_path(test)
    for ret in prior:
        if ruled_stage is not None and int(ret.get("stage") or 0) <= ruled_stage:
            continue
        ids = [*ret.get("added", []), *ret.get("rewritten", [])]
        if test in ids or path in {common_path(i) for i in ids} or path in (ret.get("frozen") or {}):
            return True
    return False


def common_path(test: str) -> str:
    """名指しの id・範囲の文字列のパスの部分"""
    head = test.partition("::")[0]
    got = conflict.parse_limit(head) if ":" in head else None
    return (got[0] if got else head).strip()


def returns_of(place) -> list:
    """置き場の返しの控え returns/<k>.json の全部（番号を問わない。読めない物は飛ばさない: 読めなければ ValueError）"""
    d = pathlib.Path(place) / files.RETURNS_DIR
    out = []
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        doc = jsonfile.read_or(p)
        if not isinstance(doc, dict):
            raise ValueError(f"返しの控え {p} が読めない")
        out.append(doc)
    return out


def write_return(place, doc: dict) -> pathlib.Path:
    """共通の受け付けが通した返しを returns/<k>.json に書く（<k> は置き場で使われていない一番小さい番号）"""
    d = pathlib.Path(place) / files.RETURNS_DIR
    d.mkdir(parents=True, exist_ok=True)
    k = 1
    while (d / f"{k}.json").exists():
        k += 1
    return jsonfile.write(d / f"{k}.json", doc)


def _order(place, weapon, keys, rows, *, group_id, stage, since, base_file, whys, removes, why_untested=False, rulings=False,
           checked=None) -> dict:
    units = []
    items = []
    allowed, out_scope = [], []
    for k in keys:
        r = rows.get(k) or {"items": [], "tests": [], "allowed": [], "out": []}
        items += [n for n in r["items"] if n not in items]
        allowed += [g for g in r["allowed"] if g not in allowed]
        out_scope += [o for o in r["out"] if o not in out_scope]
        unit = {"key": k, "items": r["items"], "removes": list(removes.get(k) or []), "tests": r["tests"]}
        if whys.get(k):
            unit["why"] = whys[k]
        if checked and checked.get(k):
            unit["checked_as"] = checked[k]
        units.append(unit)
    doc = {"weapon": weapon, "group": group_id, "stage": stage, "since": since, "base": base_file, "units": units,
           "scope": {"allowed_paths": allowed, "out_of_scope": [{"glob": str(o.get("glob") or ""), "why": str(o.get("why") or "")}
                                                                for o in out_scope]},
           "permits": permits_for(place, items, stage=stage, rulings=rulings)}
    if why_untested:
        doc["why_untested"] = "；".join(dict.fromkeys(whys.get(k, "") for k in keys if whys.get(k)))
    return doc


def compute(place, repo) -> dict:
    """node orders の本体。{tdd（tdd の輪を回す）, writer（書き手の輪を回す）, stop（組を止める）, reason}"""
    place, repo = pathlib.Path(place), pathlib.Path(repo)
    started = _start(place)
    if started.get("suite_broken") is True:   # 起動スクリプトが書き直しても壊れたまま（docs/design/fix.md の 19 節）
        return {"tdd": False, "writer": False, "stop": True, "reason": str(started.get("reason") or GATE_STOP)}
    if started.get("no_suite") is True:   # 組の頭が止めた（no_suite_why。下書き 3.9）
        return {"tdd": False, "writer": False, "stop": True, "reason": str(started.get("reason") or "")}
    group = intake.load(place).get("group") or {}
    keys = [str(k) for k in group.get("unit_ids") or []]
    words, removes, whys = route.plan_words(place, keys), route.plan_removes(place, keys), route.plan_whys(place, keys)
    state = str(started.get("state_file") or "")
    st = common.load_state(state) if state else {}
    answered = {k: (u or {}).get("route", "") for k, u in (st.get("units") or {}).items()}
    gave_up = {k for k, u in (st.get("units") or {}).items() if (u or {}).get("gave_up")}
    parked = set(st.get("parked") or [])
    owed = [k for k in keys if k not in parked]
    weapons = {k: route.weapon_of(words.get(k, ""), "" if k in gave_up else answered.get(k, ""), removes.get(k)) for k in owed}
    base = basecase.read(place)
    taken = bool(base and base.get("taken"))
    tdd_keys = [k for k in owed if weapons[k] == "tdd"] if taken else []
    if not taken:   # 元の結末を取らない組（static だけの組。ほかは組の頭が no-suite で止めた）: tdd の輪を回さない
        weapons = {k: ("variant" if w == "tdd" else w) for k, w in weapons.items()}
    values = runvals.read(place)
    if tdd_keys or state:
        if not state:
            light = [k for k in values.get("skip_rerun") or [] if k in keys]
            state = tdd.open_state(place, repo, str(basecase.path(place)), keys, owed=set(keys), light=light)
        mark = {k: "tdd" if weapons.get(k) == "tdd" else "direct" for k in owed}
        tdd.assign(state, repo, mark, {k: whys.get(k) or answered_why(st, k) for k in owed})
        started.update(go=True, state_file=state, summary_file=str(pathlib.Path(state).parent / tdd.SUMMARY))
        board.write_json(place / board.TDD_START_FILE, started)
    _write_orders(place, keys, owed, weapons, stage=stage_of(place), since=groups.end_tree(repo), has_base=bool(base))
    loop = common.load_state(state) if state else {}
    return {"tdd": bool(loop) and not loop.get("done"), "writer": True, "stop": False, "reason": ""}


ORDER_SEQUENCE = ("pin", "tidy", "static", "tdd", "variant", "remove")


def _write_orders(place, keys, owed, weapons: dict, *, stage: int, since: str, has_base: bool, agreed=None) -> list:
    """型ごとの注文 orders/<w>.json と索引 orders.json を書く（単位の無い型の注文は消す）。型の並びを返す"""
    place = pathlib.Path(place)
    group = intake.load(place).get("group") or {}
    whys, removes = route.plan_whys(place, keys), route.plan_removes(place, keys)
    rows = _unit_rows(place, keys)
    by: dict = {}
    for k in owed:
        by.setdefault(weapons[k], []).append(k)
    d = place / files.ORDERS_DIR
    d.mkdir(parents=True, exist_ok=True)
    sequence = [w for w in ORDER_SEQUENCE if w in by]
    for w in ORDER_SEQUENCE:
        if w not in by:
            (d / f"{w}.json").unlink(missing_ok=True)
            continue
        jsonfile.write(d / f"{w}.json", _order(place, w, by[w], rows, group_id=str(group.get("group_id") or ""), stage=stage,
                                               since=since, base_file=str(basecase.path(place)) if has_base else "",
                                               whys=whys, removes=removes, why_untested=w == "static"))
    jsonfile.write(place / files.ORDERS_FILE, {"sequence": sequence, "weapons": weapons, "stage": stage, "since": since,
                                               "agreed": agreed_keys(place) if agreed is None else list(agreed),
                                               "unsatisfied": unsatisfied(place, owed, weapons, sequence)})
    return sequence


def agreed_keys(place) -> list:
    """置き場の範囲の相談の合意（conflict.agreed。写した行も）の見分けの字 <group_id>:<id> の並び（注文の索引の欄 agreed。段の頭に
    在った合意。permits_for が前の返しに当たる物を引いた合意と、段の途中で取れた合意を見分ける）"""
    try:
        rows = conflict.agreed(pathlib.Path(place))
    except ValueError:
        rows = []
    return [_agreed_key(r) for r in rows]


def _agreed_key(row: dict) -> str:
    return f"{row.get('group_id') or ''}:{row.get('id')}"


def later_agreed(place) -> list:
    """段の頭（注文の索引の欄 agreed）の後に取れた範囲の相談の合意の許しの範囲（許しの唯一の元 conflict.test_permits の agreed の
    行の limit）。相談はその時の木の凍結を見て許したので、前の返しの凍ったファイルに当たっても引かない（下書き 2.1 の「後の段で直したい時は、範囲の相談か申し出の
    道に乗る」）。注文の無い置き場は []"""
    idx = jsonfile.read_or(pathlib.Path(place) / files.ORDERS_FILE)
    if not isinstance(idx, dict):
        return []
    seen = set(idx.get("agreed") or [])
    try:
        rows = [r for r in conflict.agreed(pathlib.Path(place)) if _agreed_key(r) not in seen]
        permits = conflict.test_permits(pathlib.Path(place), rulings=False, agreed_rows=rows) if rows else []
    except ValueError:
        return []
    return [str(r["limit"]) for r in permits if _kind(str(r.get("id") or "")) == ("agreed", False) and r.get("limit")]


def regive(place) -> list:
    """tdd の輪が諦めた単位（輪の状態の units の gave_up）を、同じ箱の variant の注文に書き直す（下書き 4.1 の 3 の gave_up の
    単位の書き直し。route から型を引く表の 5 と同じ行き先）。注文 orders/tdd.json から外し orders/variant.json に足し、索引の weapons を
    替える（段の番・since・元の結末・段の頭の合意 agreed は今の注文のまま）。注文の無い組・諦めの無い組は何もしない。何度呼んでも同じ。書き直した単位を返す"""
    place = pathlib.Path(place)
    idx = jsonfile.read_or(place / files.ORDERS_FILE)
    if not isinstance(idx, dict) or not isinstance(idx.get("weapons"), dict):
        return []
    state = str(_start(place).get("state_file") or "")
    units = (common.load_state(state).get("units") or {}) if state and pathlib.Path(state).is_file() else {}
    weapons = dict(idx["weapons"])
    moved = [k for k, w in weapons.items() if w == "tdd" and (units.get(k) or {}).get("gave_up")]
    if not moved:
        return []
    weapons.update({k: "variant" for k in moved})
    group = intake.load(place).get("group") or {}
    keys = [str(k) for k in group.get("unit_ids") or []]
    _write_orders(place, keys, [k for k in keys if k in weapons], weapons, stage=int(idx.get("stage") or stage_of(place)),
                  since=str(idx.get("since") or ""), has_base=basecase.read(place) is not None, agreed=idx.get("agreed") or [])
    return moved


RULED_WEAPON = {"tdd": "variant"}   # 裁定の後の直しの型: 元の単位と同じ箱の型（tdd の単位は variant。ほかは元の型のまま。下書き 4.1 の 6）
RULED_PASS = "ruled"                 # 裁定の後の段の注文の索引の欄 pass の値（受け付けが組の子の注文と見分ける）


def returned_weapons(place) -> dict:
    """置き場の返しの控え returns/ の全部から、単位 → その単位を最後に返した型の名（番号の順に読み、後の物が勝つ）"""
    d = pathlib.Path(place) / files.RETURNS_DIR
    out = {}
    for p in sorted(d.glob("*.json"), key=lambda q: (len(q.stem), q.stem)) if d.is_dir() else []:
        doc = jsonfile.read_or(p)
        if not isinstance(doc, dict):
            raise ValueError(f"返しの控え {p} が読めない")
        for u in doc.get("units") or []:
            if isinstance(u, dict) and isinstance(u.get("key"), str):
                out[u["key"]] = str(doc.get("weapon") or "")
    return out


def write_ruled(place, owed: list, *, since: str) -> list:
    """裁定の後の直しの注文（下書き 4.1 の 6。node fix-ruled-prep が段の頭で 1 度書く）: 直す義務の単位 owed を、親の置き場の返しの
    控えの元の型から同じ箱の型（RULED_WEAPON）に引いて orders/<w>.json に書き、単位の行に照らしに使う元の型 checked_as を書く（控えに
    無い単位は variant に引き、checked_as を書かない）。段の番は stage_of の ruled、since は段の頭の木、permits は裁定の範囲を入れて
    （rulings=True）前の型の物を引く。元の結末は親の受け付けの選び（board.ruled_base）。索引 orders.json は pass ruled を持つ。型の並びを返す"""
    place = pathlib.Path(place)
    keys = [str(k) for k in owed]
    was = returned_weapons(place)
    weapons = {k: RULED_WEAPON.get(was.get(k, ""), was.get(k) or "variant") for k in keys}
    checked = {k: was[k] for k in keys if was.get(k)}
    whys, removes = route.plan_whys(place, keys), route.plan_removes(place, keys)
    rows = _unit_rows(place, keys)
    stage = stage_of(place, RULED_PASS)
    got = board.ruled_base(place)
    base_file = str(pathlib.Path(got) / files.BASE_FILE) if got else ""
    by: dict = {}
    for k in keys:
        by.setdefault(weapons[k], []).append(k)
    d = place / files.ORDERS_DIR
    d.mkdir(parents=True, exist_ok=True)
    sequence = [w for w in ORDER_SEQUENCE if w in by]
    for w in ORDER_SEQUENCE:
        if w not in by:
            (d / f"{w}.json").unlink(missing_ok=True)
            continue
        jsonfile.write(d / f"{w}.json", _order(place, w, by[w], rows, group_id=RULED_PASS, stage=stage, since=since, base_file=base_file,
                                               whys=whys, removes=removes, why_untested=w == "static", rulings=True,
                                               checked=checked))
    jsonfile.write(place / files.ORDERS_FILE, {"sequence": sequence, "weapons": weapons, "stage": stage, "since": since,
                                               "pass": RULED_PASS, "agreed": agreed_keys(place), "unsatisfied": []})
    return sequence


def restart(place, weapon: str, *, since: str) -> None:
    """型 weapon を回し始める時に、その型の注文と索引の since を今の木にする（型を 1 つずつ順に回すので、後の型の差分の起点は前の型が
    返した木。下書き 2.1 の since・docs/plans/2026-10-25-fix-weapons-stage1-b.md の 1）"""
    place = pathlib.Path(place)
    path = place / files.ORDERS_DIR / f"{weapon}.json"
    doc = jsonfile.read_or(path)
    if isinstance(doc, dict):
        jsonfile.write(path, {**doc, "since": since})
    idx = jsonfile.read_or(place / files.ORDERS_FILE)
    if isinstance(idx, dict):
        jsonfile.write(place / files.ORDERS_FILE, {**idx, "since": since})


def is_ruled(place) -> bool:
    """置き場の注文の索引が裁定の後の段の物か"""
    doc = jsonfile.read_or(pathlib.Path(place) / files.ORDERS_FILE)
    return isinstance(doc, dict) and doc.get("pass") == RULED_PASS


def checked_as(place) -> dict:
    """単位 → 照らしに使う元の型（注文の単位の行の checked_as。在る物だけ）"""
    out = {}
    for doc in order_docs(place).values():
        for u in doc.get("units") or []:
            if isinstance(u, dict) and u.get("checked_as"):
                out[str(u.get("key"))] = str(u["checked_as"])
    return out


def answered_why(st, k) -> str:
    return str(((st.get("units") or {}).get(k) or {}).get("why") or "")


def unsatisfied(place, keys, weapons: dict, sequence: list) -> list:
    """型を 1 回ずつ回す並び sequence で守れない、項目の間の依存の対（planmarks.depends_pairs の「前の単位 → 後の単位」で、後の単位の
    型が前の単位の型より先に回る物）の [{before, after}]。黙って崩さず、組の結果と報告に名で出す"""
    try:
        fields = conflict.frozen_fields(pathlib.Path(place), 1) or []
    except ValueError:
        return []
    out = []
    for a, b in planmarks.depends_pairs(fields):
        if a in weapons and b in weapons and a in keys and b in keys:
            wa, wb = _slot(weapons[a]), _slot(weapons[b])
            if wb < wa:
                out.append({"before": a, "after": b})
    return out


WRITER_ORDER = ("tdd", "pin", "tidy", "static", "variant", "remove")   # 組の子で型の注文が回る順（tdd の輪の後に型の書き手を 1 つずつ。src/writers.SEQUENCE と同じ）


def _slot(w: str) -> int:
    """今の組の子で型の注文が回る順の番"""
    return WRITER_ORDER.index(w) if w in WRITER_ORDER else len(WRITER_ORDER)


def weapons(place) -> dict:
    """単位 → 型の名（orders.json の weapons。無い・読めなければ {}）"""
    doc = jsonfile.read_or(pathlib.Path(place) / files.ORDERS_FILE)
    got = doc.get("weapons") if isinstance(doc, dict) else None
    return dict(got) if isinstance(got, dict) else {}



def order_docs(place) -> dict:
    """置き場の型ごとの注文 {型の名: orders/<w>.json の中身}（無ければ {}。読めない注文は ValueError）"""
    d = pathlib.Path(place) / files.ORDERS_DIR
    out = {}
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        doc = jsonfile.read_or(p)
        if not isinstance(doc, dict):
            raise ValueError(f"注文 {p} が読めない")
        out[p.stem] = doc
    return out


def named_tests(place) -> list:
    """受け付けの名指しの出どころ（下書き 2.1 の「受け付けの名指しの出どころ」）のうち注文の物: 全部の注文の units[].tests と、
    permits の rewrite の行の test（現れた順・重ねない）。返しの evidence.named・added・rewritten は書き手が返す PR B で足す"""
    out: list = []
    for doc in order_docs(place).values():
        ids = [t for u in doc.get("units") or [] if isinstance(u, dict) for t in u.get("tests") or []]
        ids += [r.get("test") for r in doc.get("permits") or [] if isinstance(r, dict) and r.get("kind") == "rewrite"]
        out += [t for t in dict.fromkeys(ids) if isinstance(t, str) and t.strip() and t not in out]
    return out
