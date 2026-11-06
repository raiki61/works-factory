"""一言の向きの判定の決め（docs/design/answer-direction.md）。向きの語（aligned・redirected・unclear）と、aligned の真偽の決めはここ 1 か所
に置く。line は返りの真偽 aligned だけを読み、向きの語を知らない。

- due(answer_raw, asked_raw, plan_raw) -> {due, note, asked, plan, reason}: 役を起こすか。決めの語が通す語（lib/answer.py の GO_WORDS）で
  一言が空でない時だけ due 真（note は一言、asked は見せた項目の文の並び、plan は承認に掛けた計画の行の並び）。一言が空か止める語の答えは役を起こさず
  reason も空（落ちたのでなく要らない）。答え・見せた項目・計画が読めない時は役を起こさず、読めなかった入力を名指す reason を返す
- read_reply(raw) -> {direction, why}: 役の返答（JSON の字か dict）を読む。向きの語の外・why が字でない返答は direction が ""
- failed(reason): 判定が落ちた返り（status failed・aligned 偽）
- outcome(prep, raw) -> finish の返り {ok, status, reason, direction, aligned, why, report}: status は ok（役が読める返答を返した）・
  skipped（役を起こさなかった）・failed（支度が落ちた・入力が読めない・返答が無いか読めない）。aligned が真になるのは direction が
  aligned の時と skipped の時だけ（failed は偽。判定が落ちたのを通さない）
- REPLY・PROMPT_FILE・OWN_FILES: place のファイルの名（block が消してよいのもこの名のファイルだけ）
"""
import json

import ports  # 先に読む（lib/ を sys.path に足す）
import answer  # lib/
import oneline  # lib/

VERDICTS = ("aligned", "redirected", "unclear")   # YAML の direction の output_format の direction の enum と同じ（試験が突き合わせる）
ALIGNED, REDIRECTED, UNCLEAR = VERDICTS
REPLY = "reply.json"
PROMPT_FILE = "direction-prompt-1.md"      # prompt.emit が書く（node の id は direction、回の番号は 1）
OWN_FILES = (PROMPT_FILE, REPLY)
NO_REPLY = "一言の向きの役が返答を返さなかった（役が落ちたか飛ばされた）"
UNREADABLE_REPLY = "一言の向きの役の返答を読めない（向きの語 aligned・redirected・unclear と why が無い）"
SPOKEN = {REDIRECTED: "計画と違う向きを選んでいる", UNCLEAR: "向きが読めない"}   # 報告の行の訳（向きの語は報告に出さない）


def _skip() -> dict:
    return {"due": False, "note": "", "asked": [], "plan": [], "reason": ""}


def _fell(reason: str) -> dict:
    return {**_skip(), "reason": oneline.one_line(reason)}


def due(answer_raw, asked_raw, plan_raw) -> dict:
    try:
        given = ports.parsed(answer_raw)
    except ValueError as error:
        return _fell(f"入力 answer: 承認ノードの答えを読めない（{ports.text(answer_raw).strip()[:80]}: {type(error).__name__}）")
    if not isinstance(given, dict) or not isinstance(given.get("decision"), str):
        return _fell(f"入力 answer: 承認ノードの答えが {{decision, text}} の形でない（{ports.text(answer_raw).strip()[:80]}）")
    note = str(given.get("text") or "")
    if given["decision"] not in answer.GO_WORDS or not note.strip():
        return _skip()
    try:
        asked = [] if ports.parsed(asked_raw) is None else ports.json(asked_raw, "shown.schema.json")
    except ValueError as error:   # 形に合わない入力（ShapeError）も ValueError の子
        return _fell(f"入力 asked: 承認ノードで見せた項目を読めない（{ports.text(asked_raw).strip()[:80]}: {type(error).__name__}: {error}）")
    try:
        plan = [] if ports.parsed(plan_raw) is None else ports.json(plan_raw, "shown.schema.json")
        if not plan:
            raise ValueError("承認に掛けた計画の行が無い")
    except ValueError as error:   # 形に合わない入力（ShapeError）も ValueError の子
        return _fell(f"入力 plan: 承認に掛けた計画の行を読めない（{ports.text(plan_raw).strip()[:80]}: {type(error).__name__}: {error}）")
    return {"due": True, "note": note, "asked": asked, "plan": plan, "reason": ""}


def read_reply(raw) -> dict:
    got = raw
    if isinstance(raw, str):
        try:
            got = json.loads(raw) if raw.strip() else None
        except ValueError:
            got = None
    if not isinstance(got, dict) or got.get("direction") not in VERDICTS or not isinstance(got.get("why"), str):
        return {"direction": "", "why": ""}
    return {"direction": got["direction"], "why": got["why"]}


def _result(status: str, *, reason: str = "", direction: str = "", why: str = "") -> dict:
    aligned = status == "skipped" or direction == ALIGNED
    if status == "failed":
        report = [f"一言の向きの判定: 判定できなかった（{reason}）"]
    elif direction in SPOKEN:
        report = [oneline.one_line(f"一言の向きの判定: {SPOKEN[direction]}（{why}）")]
    else:
        report = []
    return {"ok": status != "failed", "status": status, "reason": reason, "direction": direction, "aligned": aligned, "why": why,
            "report": report}


def failed(reason: str) -> dict:
    """判定が落ちた返り（status failed・aligned 偽）。出口 finish が落ちた時の返りにも使う"""
    return _result("failed", reason=reason)


def outcome(prep, raw: str) -> dict:
    if not isinstance(prep, dict):
        return failed("支度の node が落ちた")
    if prep.get("due") is not True:
        reason = str(prep.get("reason") or "")
        return _result("failed", reason=reason) if reason else _result("skipped")
    if not raw.strip() or raw.strip() == "null":
        return _result("failed", reason=NO_REPLY)
    got = read_reply(raw)
    if not got["direction"]:
        return _result("failed", reason=UNREADABLE_REPLY)
    return _result("ok", **got)
