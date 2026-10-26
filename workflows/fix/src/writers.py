"""型ごとの書き手を 1 つずつ順に回す口（docs/plans/2026-10-25-fix-weapons-stage1-b.md の 1。node writer-pick・ruled-writer-pick と、
修正の輪の fix-prep・fix-accept・fix-ruled-prep・fix-ruled-accept・consult-check が読む）。

外の輪の 1 周が型 1 つ。writer-pick が注文の在る型を SEQUENCE の順に選んで置き場の writer.json に書き、その型の段の頭（段の頭の木・
除くパスの姿・注文の since）を控え直す。内の輪の受け付けが done を返した型を done に積む。型ごとの状態（拒否の控えと回の数え・
渡した証拠の控え）の名は、ここの accept_name・ledger が型の名から引く。

- pick(place, repo, pass_) -> {go, writer, done}
- current(place) -> 今の型の名（選んでいなければ ""）
- node(pass_, weapon) -> 型の書き手の node の名（型の block を include する node の id。1 回目の段 w-<型>・裁定の後 wr-<型>）
- hand_over(place, pass_, weapon, slots, owed=()) -> {order, slots}: 型の block に渡す入力の pointer（slots は place に書く。注文の無い置き場の FALLBACK だけは、直す義務の全部を受ける注文もここで書く）
- stage_mark(place, pass_, weapon) -> 型の書き手の段の頭の印のファイル（修正の block の place の中。hand_over が書く 1 回目の slots）
- owed(place, keys) -> keys のうち今の型の注文の単位（並びは keys のまま）
- accept_name(pass_, weapon)・ledger(place, pass_, weapon)
- finished(place, weapon): 受け付けが型を済ませた印を積む
- reply_of(blocks, pass_) -> (書き手の返答の dict, 報告の行): 起きた書き手の 1 つ。型の block の返りまるごと {ok, reason, reply, report}
  （受ける script が ports.picked で拾った物。飛んだ block は None）は reply の pointer を解く。どれも起きていなければ (None, [])
"""
from __future__ import annotations

import json as _json
import pathlib

import ports      # .shared/（呼ぶ script が sys.path に入れる）

import conflict   # lib/
import groups     # lib/
import jsonfile   # lib/

from src import board, files, intake, orders, rules


SEQUENCE = {"first": ("tdd", "pin", "tidy", "static", "variant", "remove"),
            "ruled": ("pin", "tidy", "static", "variant", "remove")}   # 型を回す順（tdd の輪の後。残りは箱の順。下書き 4.1 の 3）
ACCEPT = {"first": "fix-accept", "ruled": "fix-ruled-accept"}


BLOCK_WEAPON = {"tdd": "tdd-close"}   # 型の名 → 型の block の名の末尾（閉じの書き手の block は weapon-tdd-close）
NODE_HEAD = {"first": "w", "ruled": "wr"}   # 型の block を include する node の id の頭


def block_of(weapon: str) -> str:
    """型 weapon の書き手の block の名の末尾（<w>。node の id・md の名・指示のファイルの名の頭）"""
    return BLOCK_WEAPON.get(weapon, weapon)


def node(pass_: str, weapon: str) -> str:
    """型 weapon の書き手の node の名。型の block を include する node の id（1 回目の段 w-<型>、裁定の後の段 wr-<型>。tdd は輪の閉じの
    書き手の block tdd-close）"""
    if weapon not in SEQUENCE[pass_]:
        raise ValueError(f"段 {pass_} に型 {weapon!r} の書き手は無い")
    return f"{NODE_HEAD[pass_]}-{block_of(weapon)}"


def stage_mark(place, pass_: str, weapon: str) -> pathlib.Path:
    """型 weapon の書き手の段の頭の印: 修正の block が自分の place に書く、その書き手の 1 回目のファイル。hand_over が書く
    slots-<include の id>-1.json（型の block の place の中は読まない。E4）"""
    return pathlib.Path(place) / f"slots-{node(pass_, weapon)}-1.json"


def nodes(pass_: str) -> list:
    return [node(pass_, w) for w in SEQUENCE[pass_]]


def accept_name(pass_: str, weapon: str) -> str:
    """型ごとの受け付けの名（拒否の控え rejects-<名>.json と回の数え。型が替われば 1 回目から数える）"""
    return f"{ACCEPT[pass_]}-{weapon}"


def ledger(place, pass_: str, weapon: str) -> pathlib.Path:
    """型の書き手に渡した証拠の種類と回の控え（node ごと）"""
    return pathlib.Path(place) / files.delivered(node(pass_, weapon))


def _state(place) -> dict:
    doc = jsonfile.read_or(pathlib.Path(place) / files.WRITER_FILE)
    return doc if isinstance(doc, dict) else {}


FALLBACK = "variant"   # 注文の無い置き場（注文を書く段を通らない置き場）で直す義務の全部を受ける型（route から型を引く表の 5 と同じ行き先）


def current(place) -> str:
    """今の型の名。外の輪の頭が選んでいなければ ""。注文の無い置き場（注文を書く段 orders・write_ruled を通らずに修正の輪を回す置き場）は
    FALLBACK（直す義務の全部を受ける）"""
    got = str(_state(place).get("weapon") or "")
    if got:
        return got
    return "" if orders.order_docs(place) else FALLBACK


def _pending(place, pass_: str) -> list:
    """注文の在る型のうち済んでいない物（SEQUENCE の順）"""
    docs = orders.order_docs(place)
    done = set(_state(place).get("done") or [])
    if not docs:   # 注文の無い置き場: 直す義務の全部を FALLBACK の書き手が受ける
        return [] if FALLBACK in done else [FALLBACK]
    return [w for w in SEQUENCE[pass_] if w in docs and docs[w].get("units") and w not in done]


def ruled_due(place) -> bool:
    """裁定の後の段で直す裁定が在るか（1 回目の段の裁定〔2 回目の段が写した行〕と組どうしの合わせの申し出は除く）"""
    return bool([r for r in conflict.ruled_fix(place) if not r.get(conflict.PRIOR) and r.get("source") != conflict.JOIN_SOURCE])


def pick(place, repo, pass_: str, skip=()) -> dict:
    """外の輪の頭: 次に回す型を選んで writer.json に書き、型の段の頭を控え直す。回す型が無ければ go: false"""
    place, repo = pathlib.Path(place), pathlib.Path(repo)
    if pass_ == "first":
        orders.regive(place)   # tdd の輪が諦めた単位を variant の注文に書き直す（何度呼んでも同じ）
        if board.no_suite_stop(place):   # 組が no-suite で止まった: 残りの型を回さない
            return {"go": False, "writer": "", "done": True}
    else:
        if not ruled_due(place):
            return {"go": False, "writer": "", "done": True}
        if not orders.is_ruled(place):
            head = place / rules.head_file("ruled")
            board.write_json(head, {"tree": groups.end_tree(repo)})
            orders.write_ruled(place, board.ruled_owed(place), since=board.fixer_head(place, "ruled"))
    pending = _pending(place, pass_)
    if not pending:
        return {"go": False, "writer": "", "done": True}
    weapon = pending[0]
    st = _state(place)
    if st.get("weapon") != weapon or st.get("pass") != pass_:
        board.record_skipped(place, repo, skip)   # 印より先に（落ちて回し直した支度が控えを飛ばさない）
        tree = groups.end_tree(repo)
        board.write_json(place / rules.head_file(pass_), {"tree": tree})
        orders.restart(place, weapon, since=tree)
        jsonfile.write(place / files.WRITER_FILE, {"pass": pass_, "weapon": weapon, "done": list(st.get("done") or [])})
    return {"go": True, "writer": node(pass_, weapon), "done": len(pending) == 1}


def owed(place, keys) -> list:
    """keys（組か段の直す義務の単位）のうち今の型の注文の単位"""
    w = current(place)
    docs = orders.order_docs(place)
    if not docs and w == FALLBACK:
        return list(keys)
    doc = docs.get(w) or {}
    mine = {str(u.get("key")) for u in doc.get("units") or [] if isinstance(u, dict)}
    return [k for k in keys if k in mine]


def finished(place, weapon: str) -> None:
    st = _state(place)
    done = [*(st.get("done") or [])]
    if weapon and weapon not in done:
        done.append(weapon)
    jsonfile.write(pathlib.Path(place) / files.WRITER_FILE, {**st, "done": done})


def _order_path(place, pass_: str, weapon: str, owed) -> pathlib.Path:
    """型 weapon の注文のファイル orders/<w>.json。注文の無い置き場（注文を書く段を通らない置き場。current が FALLBACK を返す）の FALLBACK だけは、
    型の block が注文を必ず受けるので、直す義務の全部 owed を受ける注文を fallback-order-<段>.json に書いてそれを指す（orders/ に書くと注文の在る
    置き場になり、current が FALLBACK を返さなくなる。型の block は注文の weapon の語だけを読む）"""
    place = pathlib.Path(place)
    path = place / files.ORDERS_DIR / f"{weapon}.json"
    if path.is_file() or weapon != FALLBACK or orders.order_docs(place):
        return path
    group = (intake.load(place).get("group") or {}).get("group_id") or "whole"
    head = board.read_json(place / rules.head_file(pass_)) or {}
    doc = {"weapon": weapon, "group": group, "stage": orders.stage_of(place, pass_), "since": str(head.get("tree") or "unknown"), "base": "",
           "units": [{"key": k, "removes": [], "tests": []} for k in owed], "scope": {"allowed_paths": [], "out_of_scope": []}, "permits": []}
    return jsonfile.write(place / f"fallback-order-{pass_}.json", doc)


def hand_over(place, pass_: str, weapon: str, slots: dict, owed=()) -> dict:
    """型の block に渡す入力: slots を place の slots-<node>-<n>.json に書き（n は同じ node の前の周の数 + 1）、その型の注文 orders/<型>.json と
    ともに pointer で返す {order, slots}（どちらも形に合うことを ports.pointer が照らす。合わなければ落ちる）。注文の無い置き場の FALLBACK の
    注文は _order_path が書く（owed はその単位）"""
    place = pathlib.Path(place)
    name = node(pass_, weapon)
    n = len(list(place.glob(f"slots-{name}-*.json"))) + 1
    path = place / f"slots-{name}-{n}.json"
    jsonfile.write(path, slots)
    return {"order": ports.pointer(_order_path(place, pass_, weapon, owed), "json(shared:weapon-order.schema.json)"),
            "slots": ports.pointer(path, "json(shared:writer-slots.schema.json)")}


def reply_of(blocks: dict, pass_: str):
    """起きた書き手の 1 つの (返答の dict, 報告の行の並び)。blocks は型の名 → 型の block の返りまるごと（受ける script が
    ports.picked(<INPUTS_REPLY_<型>>, ("ok", "reason", "reply", "report")) で拾った物。飛んだ block は None）。返りは ok が真でなければ、
    block の名・include の id と返りの reason を名指した ValueError（block の返す節 writer_out は落ちず、指示を組む node・書き手・返答を置く
    node のどれかが落ちた周は ok: false と reason を返す。呼び手は place に書く前にここで落ちる。計画 docs/plans/2026-10-24-fix-weapons.md の
    11.3 の「落ちた周の守り」）。返答が形（shared:writer-reply.schema.json）に合わない・読めない時も ValueError。報告の行は返りの report。
    どれも起きていなければ (None, [])"""
    for w in SEQUENCE[pass_]:
        got = blocks.get(w)
        if got is None:
            continue
        if got["ok"] is not True:
            raise ValueError(f"型の block weapon-{block_of(w)}（include の id {node(pass_, w)}）の返りの ok が真でない（{got['ok']!r}）:"
                             f" {got['reason']}")
        return ports.json(_json.dumps(got["reply"]), "shared:writer-reply.schema.json"), [str(x) for x in got["report"] or []]
    return None, []
