"""振り分けと、route から型を引く表（docs/plans/2026-10-24-fix-weapons.md の 4.1 の 3。型を問わない部品）。

振り分けの段は TDD の輪の最初の段だった（tdd.py の route）。組の子の loop route-loop（route-prep → AI の route → route-step）に出し、
型の輪の前に回す。指示は変えない（prompts/route.md は {part:tdd} の 1 行で、src/prompts.py の route_values が同じ字を組む）。
返す語も tdd・direct と訳のまま。振り分けの段の状態は place の route.json（輪の状態と同じ欄の辞書。輪の置き場 tdd-<k>/ は置かない）に
置き、輪の状態は注文の node orders が route.json を読んで tdd.open_state で初めて作る（振り分けが数えた周の数・呼びの控え・渡した
証拠の種類は注文の型ごとの欄 orders.tdd で輪へ渡り、輪はそこから数え始める。回数の上限 MAX_ITERATIONS と申し出の数えは今と同じ）。

- plan_words(place, keys) -> {単位: 計画の語}・plan_removes(place, keys) -> {単位: 消す名やパス}: 凍結した計画の欄から機械が引く
- weapon_of(p, a, removes) -> 型の名: route から型を引く表（計画の語が先・AI の振りが後。上から順に最初に当たる行）
- route_keys(keys, words, removes) -> 振り分けの AI に渡す単位の並び（語の在る単位と消す名の在る単位を除く）
- path(place)・read(place) -> 振り分けの状態 route.json のパス・中身（無ければ {}）・open_route(place, repo, base_file, keys, ...) -> route.json を置く
- begin(st, keys) -> 状態を段 route にして振る単位を置く・step(state_file, reply, repo, ...): 振り分けの段
- counted(place, st) -> 注文の型ごとの欄 orders.tdd {iterations, calls, kinds}（輪が数え始める物）
"""
from __future__ import annotations

import pathlib
import time

import conflict   # lib/
import evidencekinds  # lib/
import planbrief  # lib/
import planmarks  # lib/
import writelog   # lib/
import writes     # lib/

import loopkit  # noqa: E402  （lib。輪と修正の block の両方が使う部品）
from src import common, files, runvals

WORDS = ("static", "tidy", "pin")   # 計画の語のうち、項目がどんな直しかの見分けの語（その語の型を引き、振り分けの AI に渡さない）
GAVE_UP = "振り分けの返答が {n} 回とも通らなかった: {why}"
ROUTED = "routed"   # 振り分けを済ませた状態の段の語（注文の node が tdd の単位の並びを置き、段を test にする）


def _fields(place, round_: int) -> list:
    try:
        return conflict.frozen_fields(pathlib.Path(place), round_) or []
    except ValueError as e:
        raise loopkit.Broken(str(e)) from None


def plan_words(place, keys, round_: int = 1) -> dict:
    """単位 → 計画の語（単位を持つ項目の route。tdd > direct > pin > tidy > static の順で 1 つ。項目が無ければ載せない）。
    計画の欄の控えの無い run は {}"""
    rank = ("tdd", "direct", "pin", "tidy", "static")
    out: dict = {}
    for f in _fields(place, round_):
        if not isinstance(f, dict) or f.get("route") not in rank:
            continue
        for k in f.get("unit_keys") or []:
            if k in keys and (k not in out or rank.index(f["route"]) < rank.index(out[k])):
                out[k] = f["route"]
    return out


def plan_whys(place, keys, round_: int = 1) -> dict:
    """単位 → 計画の route_why（route が tdd でない項目のうち最初の物。書いていなければ載せない）"""
    out: dict = {}
    for f in _fields(place, round_):
        why = str(f.get("route_why") or "").strip() if isinstance(f, dict) and f.get("route") not in (None, "tdd") else ""
        for k in (f.get("unit_keys") or []) if why else []:
            if k in keys:
                out.setdefault(k, why)
    return out


def plan_removes(place, keys, round_: int = 1) -> dict:
    """単位 → 消す名やパスの並び（単位を持つ項目の files の change=remove の symbol の名・op=delete の path・op=rename の元のパス from。
    現れた順・重なりは 1 つ。無い単位は載せない）"""
    out: dict = {}
    for f in _fields(place, round_):
        if not isinstance(f, dict):
            continue
        names = [n for _, n in planmarks.file_symbols(f, "remove")] + planmarks.removed_paths(f)
        for k in f.get("unit_keys") or [] if names else []:
            if k in keys:
                out[k] = list(dict.fromkeys([*out.get(k, []), *names]))
    return out


def weapon_of(p: str, a: str, removes) -> str:
    """route から型を引く表（下書き 4.1 の 3）。p は計画の語（無ければ ""）、a は振り分けの AI の答え（tdd・direct・無しは ""）。
    1. p が static・tidy・pin → その語の型（pin は下ごしらえを単独で）
    2. 単位に消す名が在る → remove
    3. p が tdd → tdd
    4. a が tdd → tdd
    5. 残り → variant（振り分けを諦めた時は a を無しとして同じ表で引く）"""
    if p in WORDS:
        return p
    if removes:
        return "remove"
    if p == "tdd" or a == "tdd":
        return "tdd"
    return "variant"


def route_keys(keys, words: dict, removes: dict) -> list:
    """振り分けの AI に渡す単位（振る単位の集まり）: keys から、計画の語が WORDS の単位と消す名の在る単位を除いた物（並び順のまま）"""
    return [k for k in keys if words.get(k) not in WORDS and not removes.get(k)]


WORK = "route"   # 振り分けの状態の欄 work（置き場の下の名。作らない。loopkit.conflict_item が親を置き場に引く）


def path(place) -> pathlib.Path:
    return pathlib.Path(place) / files.ROUTE_FILE


def read(place) -> dict:
    """振り分けの状態 route.json（無ければ {}。読めなければ Broken）"""
    p = path(place)
    return loopkit._load(p) if p.is_file() else {}


def begin(state: dict, keys: list) -> dict:
    """振り分けの状態 state（tdd.new_state が元の結末から組んだ物）を段 route にして、振る単位 keys を open_units に置く"""
    state.update(open_units=list(keys), phase="route", order=[], units={}, queue=[], cur=0)
    return state


def open_route(place, repo, base_file, keys, *, to_route=None, owed=None, withheld_by=None, returned=(), round_: int = 1,
               light=()) -> str:
    """振り分けの状態 route.json を place に置き、パスを返す（node route-go と tdd.start が呼ぶ）。to_route は振る単位（無ければ直す義務の
    全部）。輪の置き場 tdd-<k>/ は作らない（輪の状態は orders が作る）"""
    from src import tdd
    st = tdd.new_state(place, repo, base_file, keys, pathlib.Path(place) / WORK, owed=owed, withheld_by=withheld_by,
                       returned=returned, round_=round_, light=light)
    owed_keys = loopkit._owed(st)
    loopkit._save(path(place), begin(st, [k for k in owed_keys if to_route is None or k in to_route]))
    return str(path(place))


def counted(place, st: dict) -> dict:
    """注文の型ごとの欄 orders.tdd: 振り分けが使った周の数・呼びの控え・渡した証拠の種類（振り分けの控え ROUTE_DELIVERED の種類の並び）。
    輪はここから数え始め（回数の上限・calls を今と同じに続け、種類を減らさない）、最後の承認の tdd_refused は輪の記録の calls に振り分けの
    呼びも入るので今と同じに読む"""
    kinds = evidencekinds.delivered(pathlib.Path(place) / files.ROUTE_DELIVERED).get("kinds") or []
    return {"iterations": int(st.get("iterations") or 0), "calls": list(st.get("calls") or []), "kinds": sorted(kinds)}


def current_lines(st) -> list:
    """振り分けの指示の引き継ぎの節の行（今の段 route と、この段の返答が拒まれた回。前の単位も前の段の結果も無い）。輪の側の
    tdd.current_lines の段 route の枝を、振り分けの側へ移した物（輪の状態の段は tdd-start の後いつも test・fix・refactor か済み）"""
    tries = st.get("tries") or 0
    again = [f"- この段の返答は {tries} 回拒まれた（理由は上の「前の回の返答を機械が拒んだ理由」）"] if tries else []
    return ["- 今の段: route（直す義務の単位の振り分け）。このループの最初の段で、前の段の結果は無い", *again]


def prep(state_file, sources=None) -> dict:
    """node route-prep の材料（tdd.prep と同じ形 {go, new_unit, node, state, path, briefs}。振り分けは同じ会話を継ぐので new_unit は
    いつも偽、node は route（prompts.route_prompt が prompts/route.md を組み、route-prompt-<n>.md に書く）。済んだ（段が route でない）なら {"go": False, "new_unit": False}"""
    st = loopkit._load(state_file)
    if st.get("phase") != "route" or st.get("done"):
        return {"go": False, "new_unit": False}
    path = pathlib.Path(st["work"]) / common.PROMPT
    try:
        briefs = planbrief.cut_at(path.parent.parent, **(sources or {}))
    except planbrief.LedgerBroken as e:
        from src import rules
        raise loopkit.Broken(rules.brief_halt(e)) from None
    return {"go": True, "new_unit": False, "node": "route", "state": st, "path": path, "briefs": briefs}


def _route(st, reply, repo) -> list:
    """振り分けの返答を確かめる（今の tdd._route のまま。振る単位は状態の open_units から外れた単位を除いた物）。通れば単位ごとの
    行（tdd・direct）を置いて段を ROUTED にする"""
    rows = reply.get("units")
    if not isinstance(rows, list) or not all(isinstance(r, dict) and isinstance(r.get("unit_key"), str) for r in rows):
        return ["units は {unit_key（文字列）, route, why} の配列"]
    errs = []
    moved = sorted(set(loopkit.touched(repo, st["handoff"], loopkit.snapshot(repo))) - set(st["suite_made"]))
    if moved:
        errs.append(f"振り分けの段で作業ツリーを変えた: {moved[:5]}（この段では何も書かない）")
    keys = [r.get("unit_key") for r in rows]
    owed = loopkit._owed(st)
    errs += [f"'{k}' を 2 度以上振った" for k in dict.fromkeys(k for k in keys if keys.count(k) > 1)]
    errs += [f"直す義務の単位 '{k}' を振っていない" for k in owed if k not in keys]
    errs += [f"'{k}' は振らない（{common._not_owed_why(st, k)}）" for k in dict.fromkeys(k for k in keys if k not in owed)]
    for r in rows:
        if r.get("route") not in ("tdd", "direct"):
            errs.append(f"'{r.get('unit_key')}' の route は tdd か direct（{r.get('route')!r}）")
        elif r["route"] == "direct" and loopkit._blank(r.get("why")):
            errs.append(f"'{r.get('unit_key')}' は direct なのに、先にテストを書けない理由（why。{loopkit.MIN_WHY} 字以上）が無い")
        bound = loopkit._plan_tdd(st, r["unit_key"]) if r.get("route") == "direct" else ""
        if bound:
            errs.append(bound)
    if errs:
        return errs
    st["order"] = keys
    st["units"] = {r["unit_key"]: loopkit._unit(r["unit_key"], r["route"], (r.get("why") or "").strip() if r["route"] == "direct" else "")
                   for r in rows}
    st["phase"] = ROUTED
    return []


def _abort(st, why) -> None:
    """振り分けを諦めた: 振る単位を全部 AI の答え無し（direct の行。表で variant に引かれる）にして段を ROUTED にする"""
    st["note"] = why
    st["order"] = loopkit._owed(st)
    st["units"] = {k: {**loopkit._unit(k, "direct"), "gave_up": "route", "why": why} for k in st["order"]}
    st["phase"] = ROUTED


def _conflict(st, reply, repo, try_query=None) -> tuple:
    """振り分けの段の申し出（phase conflict）: 名指しが現物に在れば拒否に数えず、その単位を義務から外す。振る単位が残らなければ
    段を ROUTED にする"""
    place = pathlib.Path(st["work"]).parent
    probs, item = loopkit.conflict_item(st, reply, repo, set(loopkit._owed(st)), try_query,
                                        request_file=runvals.read(place)["request_file"], cite_root=place,
                                        briefs_by_unit=planbrief.by_unit_at(place))
    if probs:
        return probs, None
    loopkit._mark_parked(st, item["unit_key"], item["why_both_cannot_hold"])
    if not set(loopkit._owed(st)):
        st.update(order=[], units={}, phase=ROUTED)
    st["reason"] = ""
    return [], item


def step(state_file, reply, repo, try_query=None, log=None) -> dict:
    """node route-step。{ok, done, reason, phase, writes}。tdd.step の振り分けの段と同じ確かめ・同じ回数の数え（拒否 rolekit の
    3 回で諦める・周の数は輪の iterations に積む・呼びの記録 calls・止めた申し出は UNSENT）。済んだ状態に返答 None は何もしない"""
    st = loopkit._load(state_file)
    if st.get("phase") != "route":
        if reply is None:
            return {"ok": True, "done": True, "reason": "", "phase": st.get("phase", ROUTED), "writes": None}
        raise loopkit.Broken("振り分けは済んでいる（route-step を呼ぶ番でない）")
    t0, runs0 = time.monotonic(), st["runs"]
    call = {"n": st["iterations"] + 1,
            "phase": "conflict" if isinstance(reply, dict) and reply.get("phase") == "conflict" else "route", "unit_key": ""}
    item, source, got = None, conflict.TDD_SOURCE, None
    if isinstance(reply, dict) and reply.get("phase") != "conflict":
        moved = sorted(set(loopkit.touched(repo, st["handoff"], loopkit.snapshot(repo))) - set(st["suite_made"]))
        got = writes.check(reply, repo, moved, pathlib.Path(st["work"]) / writelog.LOG if log is None else pathlib.Path(log))
        reply = got.pop("reply")
    if not isinstance(reply, dict):
        probs = ["返答が JSON のオブジェクトでない"]
    elif got and got["problems"]:
        probs = got["problems"]
    elif reply.get("phase") == "conflict":
        probs, item = _conflict(st, reply, repo, try_query)
    elif reply.get("phase") != "route":
        probs = [f"今の段は route（返答の phase は {reply.get('phase')!r}）"]
    else:
        probs = _route(st, reply, repo)
    if probs and st["phase"] == "route":
        st["tries"] += 1
        st["reason"] = "\n".join(f"- {p}" for p in probs)
        if st["tries"] >= loopkit.retry_max():
            _abort(st, GAVE_UP.format(n=loopkit.retry_max(), why=probs[0][:200]))
    st["iterations"] += 1
    if st["phase"] == ROUTED:
        st.update(tries=0, reason="")
    if got and not got["problems"]:
        st["handoff"] = loopkit.snapshot(repo)
    st.setdefault("calls", []).append({**call, "ok": not probs, "runs": st["runs"] - runs0,
                                       "secs": round(time.monotonic() - t0, 1)})
    if item is not None:
        st.setdefault(loopkit.UNSENT, []).append({"source": source, "item": item})
    loopkit._save(state_file, st)
    done = st["phase"] == ROUTED
    return {"ok": not probs, "done": done, "reason": "\n".join(probs), "phase": st["phase"], "writes": got}
