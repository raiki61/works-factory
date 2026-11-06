"""一言の向きの判定の決め（docs/design/answer-direction.md）。向きの語（aligned・redirected・unclear）と、aligned の真偽の決めはここ 1 か所
に置く。line は返りの真偽 aligned だけを読み、向きの語を知らない。

- due(answer_raw, asked_raw, plan_raw) -> {due, note, asked, plan, reason}: 役を起こすか。決めの語が通す語（lib/answer.py の GO_WORDS）で
  一言が空でない時だけ due 真（note は一言、asked は見せた項目の文の並び、plan は plan_lines）。一言が空か止める語の答えは役を起こさず
  reason も空（落ちたのでなく要らない）。答え・見せた項目・計画が読めない時は役を起こさず、読めなかった入力を名指す reason を返す
- plan_lines(doc) -> 行の並び: 修正案の各項目の approach と、files の path・op の要約
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
REPLY = "reply.json"                       # 役の返答の写し（受け皿 direction-save が書く。役が飛ばされた・落ちた回は書かない）
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
        path = ports.file(plan_raw, "json(shared:fix-plan.schema.json)")
        if path is None:
            raise ValueError("承認に掛けた計画の修正案が渡されていない")
        plan = plan_lines(json.loads(path.read_text(encoding="utf-8")))
        if not plan:
            raise ValueError("計画の修正案に項目が無い")
    except (ValueError, OSError) as error:   # UnicodeDecodeError・JSONDecodeError は ValueError の子
        return _fell(f"入力 plan: 承認に掛けた計画の修正案を読めない（{ports.text(plan_raw).strip()[:80]}: {type(error).__name__}: {error}）")
    return {"due": True, "note": note, "asked": asked, "plan": plan, "reason": ""}


def plan_lines(doc) -> list:
    """修正案 {plan: [項目の行]} の項目ごとの 1 行目 `項目 <n>: <approach>` と、files の `  - <path> (<op>)`。項目の行でない物は数えない"""
    items = [i for i in (doc.get("plan") if isinstance(doc, dict) else None) or [] if isinstance(i, dict)]
    out = []
    for n, item in enumerate(items, 1):
        out.append(f"項目 {n}: {oneline.one_line(item.get('approach') or '（approach の記録が無い）')}")
        out += [f"  - {oneline.one_line(f.get('path') or '')} ({oneline.one_line(f.get('op') or '')})"
                for f in item.get("files") or [] if isinstance(f, dict)]
    return out


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
