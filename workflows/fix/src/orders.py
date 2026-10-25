"""組の子の頭の注文（docs/plans/2026-10-24-fix-weapons.md の 2.1・4.1 の 3。node orders。今の tdd-go に替わる）。

振り分け（route-loop）の後に、計画の語・消す名・振り分けの答えから型の表（route.weapon_of）で単位ごとに型を引き、型ごとの注文を
orders/<weapon>.json（schemas/weapon-order.schema.json の形）に書き、索引を orders.json に書く。tdd に引いた単位は輪の状態に
並べ（tdd.assign）、YAML の when: へは型ごとの輪を回すかの真偽だけを返す（憲法の 1）。

PR A の形（docs/plans/2026-10-25-fix-weapons-stage1-a.md の 1）: 型ごとの書き手の指示は作る物 9（PR B）で作るので、tdd でない型の
注文は全部、今の修正役の輪（fix-loop）が受ける。修正役は今と同じく tdd の輪が緑にした単位の行も changes に写すので、修正役の輪は
止めの無い組でいつも回る（writer）。

- compute(place, repo) -> {tdd, writer, stop, reason}
- weapons(place) -> {単位: 型の名}: 書いた注文の索引から引く（受け付けが型の義務を引く口）
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


def stage_of(place, pass_: str = "first") -> int:
    """段の番（下書き 2.1 の stage）: 修正の block を入れた回 n（前の段の申し送り prior が在れば 2）の、1 回目の段は 2n−1、
    裁定の後の段は 2n"""
    n = 2 if (pathlib.Path(place) / files.PRIOR_DIR).is_dir() else 1
    return 2 * n - 1 if pass_ == "first" else 2 * n


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
    （stage の例外）。行は {kind, duty, test, source}（test は範囲の文字列か名指しの id。replan の行は単位の並び units を source に持つ）"""
    try:
        rows = conflict.test_permits(pathlib.Path(place), rulings=rulings)
    except ValueError:
        rows = []
    prior = returns_of(place)
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
        if kind != "replan" and _pulled(test, prior, stage if kind == "ruled" else None):
            continue
        out.append({"kind": kind, "duty": duty, "test": test, "source": str(r.get("source") or "")})
    return out


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


def _order(place, weapon, keys, rows, *, group_id, stage, since, base_file, whys, removes, why_untested=False) -> dict:
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
        units.append(unit)
    doc = {"weapon": weapon, "group": group_id, "stage": stage, "since": since, "base": base_file, "units": units,
           "scope": {"allowed_paths": allowed, "out_of_scope": [{"glob": str(o.get("glob") or ""), "why": str(o.get("why") or "")}
                                                                for o in out_scope]},
           "permits": permits_for(place, items, stage=stage, rulings=False)}
    if why_untested:
        doc["why_untested"] = "；".join(dict.fromkeys(whys.get(k, "") for k in keys if whys.get(k)))
    return doc


def compute(place, repo) -> dict:
    """node orders の本体。{tdd（tdd の輪を回す）, writer（修正役の輪を回す）, stop（組を止める）, reason}"""
    place, repo = pathlib.Path(place), pathlib.Path(repo)
    started = _start(place)
    if started.get("suite_broken") is True:   # 起動スクリプトが書き直しても壊れたまま（docs/design/fix.md の 19 節）
        return {"tdd": False, "writer": False, "stop": True, "reason": str(started.get("reason") or GATE_STOP)}
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
    if not taken:   # 実行器が無い・走らない組: tdd の輪を回さず、tdd の単位も修正役が受ける（今の形。止めは作る物 6）
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
    stage = stage_of(place)
    since = groups.end_tree(repo)
    rows = _unit_rows(place, keys)
    by: dict = {}
    for k in owed:
        by.setdefault(weapons[k], []).append(k)
    d = place / files.ORDERS_DIR
    d.mkdir(parents=True, exist_ok=True)
    sequence = [w for w in ("pin", "tidy", "static", "tdd", "variant", "remove") if w in by]
    for w in sequence:
        jsonfile.write(d / f"{w}.json", _order(place, w, by[w], rows, group_id=str(group.get("group_id") or ""), stage=stage,
                                               since=since, base_file=str(basecase.path(place)) if base else "",
                                               whys=whys, removes=removes, why_untested=w == "static"))
    jsonfile.write(place / files.ORDERS_FILE, {"sequence": sequence, "weapons": weapons, "stage": stage, "since": since,
                                               "unsatisfied": unsatisfied(place, owed, weapons, sequence)})
    loop = common.load_state(state) if state else {}
    return {"tdd": bool(loop) and not loop.get("done"), "writer": True, "stop": False, "reason": ""}


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


def _slot(w: str) -> int:
    """今の組の子で型の注文が回る順（PR A: 下ごしらえ・tidy・static・variant・remove は修正役の輪が 1 つの返答で受け、tdd の輪が先）"""
    return 0 if w == "tdd" else 1


def weapons(place) -> dict:
    """単位 → 型の名（orders.json の weapons。無い・読めなければ {}）"""
    doc = jsonfile.read_or(pathlib.Path(place) / files.ORDERS_FILE)
    got = doc.get("weapons") if isinstance(doc, dict) else None
    return dict(got) if isinstance(got, dict) else {}

