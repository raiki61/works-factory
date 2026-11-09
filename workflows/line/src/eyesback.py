"""独立の目から修正の段へ返す輪の、周の頭の決めと周の記録の行の形と最後の周の状態の選び（docs/design/line.md の 1.3・4.3・5.4）。

独立の目（eyes）の判定が作り切れていない所を言った時（eyes の route が fix）に、今の作業ツリーのまま修正の段へ名指しで返し、直した後に最後の
試験と独立の目をもう一度通す。周は line の一番上に LIMIT 周分並べ（周 k の節は back-k〔周の頭〕・back-k-fix〔修正〕・back-k-fixed〔段の合わせ〕・
back-k-gate〔最後の試験〕・back-k-eyes〔独立の目〕と、それぞれの受け皿）、最後に上限の訳を記録するだけの周の頭 back-(LIMIT+1) と、最後に走った
周の頭を集める eyes-back を置く。書き手（周の頭と集め）と読み手（最後の承認ノード・報告の節・封じ）はどれも line の中なので、周の記録の形と
抜ける訳の字はここの 1 か所に置く。

- LIMIT: 返す周の数（YAML の周の節の数と同じ数。周の頭 turn はここを直に読む）。計画の往復の上限 rounds.LIMIT とは別の物
- HEAD: 最後の承認ノードと報告が返した周の節に付ける見出し
- FIELDS: 周の頭の出力の欄の名。RECORD: 集め eyes-back の出力の欄の名（最後に走った周の頭の状態）
- EXITS・CAP_WHY: 輪を抜けた訳の字（fell・stop・unchanged・no_fix・cap。目の route が stay の時は目の route_why が訳）
- row(k, eyes, items)・count(rows)・capped(record)・left_text(left): 周の記録の行と数え方
- turn(...) -> 周の頭の出力: 返すかを決め、返す時は修正の段への入力（only_items・item_kinds〔返した項目の種を修正案の項目の番号ごとに運ぶだけ。型の語は
  修正の段が引く〕・notes・prior ほか）を組む
- last(heads) -> 集め eyes-back の出力・current(eyes_back, fixed, tests, eyes) -> (fixed, tests, eyes): 最後の周の状態の選びの 1 か所
- lines(rows, exit_, left) -> 最後の承認ノードと報告が同じ行に読む返した周の行
- broken(eyes_back, head) -> 集めが飛んだのに周の頭が走ったか（報告が BROKE の 1 行を出す）
"""
from __future__ import annotations

import re

import gatemarks
import oneline
import planrange

LIMIT = 3
HEAD = "独立の目から修正の段へ返した物"
CAP_WHY = f"独立の目から修正の段へ {LIMIT} 周返したが直り切らなかった"
NO_RETURN = "独立の目か最後の試験の返りが無い（返す物を読めない）"
EXITS = {
    "fell": "返す周のノードが落ちた（周の頭が前の周の出力か、案の直しの出力を読めなかった）",
    "stop": "修正の段が止めた",
    "unchanged": "返しの修正で差分が変わらなかった",
    "no_fix": "直す物が無い run は返さない",
    "cap": CAP_WHY,
}
UNDONE = EXITS["unchanged"] + "（修正の段が直さなかった訳: {why}）"
NOT_REVIEWED = "返した段の差分は、段ごとの差分の審査・並行 PR との重なりの確かめ直し・仕様の照らし・異議の再審を通っていない"
NOTHING = "返す物が無い"
BROKE = "返す輪が途中で落ちた（下の状態は返す前の物）"   # 集めが飛んだのに周の頭が走った run の報告の 1 行（broken）
UNRETURNED = "独立の目が返す項目を挙げたが、修正の段へ返さなかった（{why}）——返さなかった項目: {items}"
UNTIED = "返す項目を修正案の項目に結べなかったので、全部の項目を対象にする"
NOTE_HEAD = "独立の目"
FIELDS = ("go", "round", "only_items", "notes", "prior", "plan", "fix_plan", "ripple", "plan_review", "answers", "skip_rerun", "more", "rows",
          "exit", "left", "fixed", "tests", "eyes", "fingerprint", "green_ok", "eyes_ok", "sealable", "item_claims", "item_kinds")
RECORD = ("rows", "exit", "left", "fixed", "tests", "eyes", "fingerprint", "green_ok", "eyes_ok", "sealable", "item_claims")
FIX_ROUTE = "fix"
_LINE_AT = re.compile(r":\d+(?:-\d+)?$")


def _d(value) -> dict:
    return value if isinstance(value, dict) else {}


def _items(eyes) -> list:
    return [i for i in _d(eyes).get("findings") or [] if isinstance(i, dict) and isinstance(i.get("text"), str) and i["text"]]


def item_text(item: dict) -> str:
    """返す項目 1 つの字『R1: <where>: <text>』（where が空なら『R1: <text>』）"""
    where = str(item.get("where") or "")
    return f"{str(item.get('eye') or '').upper()}: " + (f"{where}: " if where else "") + oneline.one_line(item.get("text") or "")


def left_text(left) -> str:
    """残った作り残しの 1 つの字（『／』で区切る）"""
    return "／".join(item_text(i) for i in left or [] if isinstance(i, dict))


def cap_text(left) -> str:
    """上限まで返して直り切らなかった時の文（最後の承認ノードの開ける理由と、返した周の行の抜けた訳が同じ字を使う）。残った作り残しは
    人の判断に回す"""
    return f"{CAP_WHY}。残った作り残し: {left_text(left) or '（記録が無い）'}（人が判断する）"


def row(k: int, eyes, items: list) -> dict:
    """周の記録の行: k 回目に返した時の R1・R2 の判定の語と、返した項目"""
    word = lambda eye: str(_d(_d(eyes).get(eye)).get("status") or "")   # noqa: E731
    return {"round": k, "r1": word("r1"), "r2": word("r2"), "items": [dict(i) for i in items]}


def count(rows) -> int:
    return len([r for r in rows or [] if isinstance(r, dict)])


def capped(record) -> bool:
    """上限の周まで返して、まだ直し切れずに抜けた記録か"""
    return _d(record).get("exit") == CAP_WHY


def fell(record) -> bool:
    """輪の記録が無い、または輪の節が落ちた記録か（最後の承認ノードが開ける理由にする）"""
    return record is None or _d(record).get("exit") == EXITS["fell"]


# ---------------------------------------------------------------- 周の頭
def _diff_hash(tests) -> str:
    fingerprint = _d(_d(tests).get("fingerprint"))
    return fingerprint.get("diff_hash") if isinstance(fingerprint.get("diff_hash"), str) else ""


def _ties(items: list, plan_fields) -> list:
    """返す項目の where の path を、修正案の項目（plan-fields の欄の並びの番号。1 から）に結んだ (返す項目, 番号) の並び（planrange.owner の結び）。
    どの項目の範囲にも入らない where は結ばない"""
    plan = [{"item": n, **f} for n, f in enumerate(plan_fields or [], 1) if isinstance(f, dict)]
    out = []
    for i in items:
        path = _LINE_AT.sub("", str(i.get("where") or "").strip())
        if path and any(planrange.inside(path, p) for p in plan):
            out.append((i, planrange.owner(path, plan)["item"]))
    return out


def _tied(items: list, plan_fields) -> list:
    return sorted({n for _, n in _ties(items, plan_fields)})


def _kinds(items: list, plan_fields, only: list) -> list:
    """返した項目の種を修正案の項目の番号ごとに並べた [{item, kind}]（現れた順・重なりは 1 つ）。項目に結べた時（only が空でない）は、
    結べた項目の番号とその指摘の種。結べず全部を対象にした時は、全部の項目の番号に返した種を並べる。種の無い指摘は行を作らない"""
    if only:
        pairs = [(n, i.get("kind")) for i, n in _ties(items, plan_fields)]
    else:
        pairs = [(n, i.get("kind")) for i in items for n in range(1, len(plan_fields or []) + 1)]
    return [{"item": n, "kind": kind} for n, kind in dict.fromkeys(pairs) if isinstance(kind, str) and kind]


def _base(k, fixed, tests, eyes, rows, more) -> dict:
    """どの抜け方でも運ぶ最後の状態の欄。sealable は最後の目の got が在る時だけ真（試験と合わせも欠けていないこと）"""
    return {"go": False, "round": k, "only_items": [], "notes": "", "prior": None, "plan": None, "fix_plan": None, "ripple": None,
            "plan_review": None, "answers": None, "skip_rerun": [], "more": more, "rows": rows, "exit": "", "left": [],
            "fixed": fixed, "tests": tests, "eyes": eyes, "fingerprint": _d(tests).get("fingerprint") if isinstance(_d(tests).get("fingerprint"), dict) else None,
            "green_ok": _d(tests).get("ok") is True, "eyes_ok": _d(eyes).get("ok") is True,
            "sealable": isinstance(fixed, dict) and isinstance(tests, dict) and isinstance(eyes, dict),
            "item_claims": _d(fixed).get("item_claims"), "item_kinds": []}


def turn(*, k: int, prev, fixed, judged, fix_in, tests, eyes, replan, answer_replan, plan_fields) -> dict:
    """周 k の頭の決め。返す時は go を真にして修正の段への入力を組む。抜ける時は go を偽にして exit に訳を書く。周の頭はどの周も走る
    （Archon は飛んだ node の出力を when: が読むと誤りにするので、頭に when: を置かない）。前の周の頭が返さなかった周は何もせず、
    前の周の頭の記録（抜けた訳・返した周の行・残った作り残し・最後の状態）をそのまま運ぶ。決める順:
    0. k が 2 以上で前の周の頭が返さなかった（go が真でない）→ 前の記録をそのまま運ぶ
    1. 前の周の頭か合わせが欠けた（k が 2 以上で prev が無い・fixed が無い）→ 輪の節が落ちた
    2. 前の段の修正の stop_reason か異議が空でない・合わせが進めない（k が 1 なら判定の stop_reason も）→ 修正の段が止めた。合わせの
       stop_why（止めの語と組の止めた訳）が在れば『（<語か合わせが進めなかった旨>：<stop_why>）』と組で載せる。
       合わせの no_fix が真（直す物が無い run。計画が無いので修正役を起こせない）→ 直す物が無い run は返さない。
       どちらも、目が返そうとした項目を left に運ぶ（周の行が 0 でも lines が名指す）
    3. 試験か目の返りが欠けた → k が 2 以上なら輪の節が落ちた。1 周目は目か試験が返らなかっただけ（輪の節は落ちていない）なので返す物を読めない訳で抜ける
    4. k が 2 以上で試験の指紋の diff_hash が前の周と同じ → 返しの修正で差分が変わらなかった（stop_why が在れば UNDONE で修正の段が
       直さなかった訳を添える）
    5. 目の route が fix でない・返す項目が無い → 目の route_why（無ければ『返す物が無い』）
    6. k が LIMIT を越えた → 上限の訳（残った作り残しを left に運ぶ）
    7. 案の直しの返りが読めない（1 周目で refixed が真なのに案の直しか答えの返りが無い）→ 輪の節が落ちた
    ほかは返す。k が 2 以上の plan・fix_plan・ripple・plan_review・answers・skip_rerun は前の周の頭の値をそのまま運ぶ"""
    if k > 1 and isinstance(prev, dict) and prev.get("go") is not True:
        return {**{key: prev.get(key) for key in FIELDS}, "go": False, "round": k}
    rows = [dict(r) for r in _d(prev).get("rows") or [] if isinstance(r, dict)]
    more = list(_d(fixed).get("more") or [])
    out = _base(k, fixed, tests, eyes, rows, more)

    def leave(why: str, **extra) -> dict:
        return {**out, **extra, "exit": why}

    def fall() -> dict:
        return leave(EXITS["fell"], sealable=False if k > 1 else out["sealable"])
    if not isinstance(fixed, dict) or (k > 1 and not isinstance(prev, dict)):
        return fall()
    pending = [dict(i) for i in _items(eyes)] if _d(eyes).get("route") == FIX_ROUTE else []
    stops = [str(fixed.get("stop_reason") or ""), oneline.one_line(fixed.get("objection") or ""),
             str(_d(judged).get("stop_reason") or "") if k == 1 else ""]
    why = next((s for s in stops if s), "" if fixed.get("go") is True else "修正の段の合わせが進めなかった")
    stop_why = oneline.one_line(fixed.get("stop_why") or "")
    if why:
        return leave(f"{EXITS['stop']}（{why}：{stop_why}）" if stop_why else f"{EXITS['stop']}（{why}）", left=pending)
    if fixed.get("no_fix") is True:
        return leave(EXITS["no_fix"], left=pending)
    if not isinstance(tests, dict) or not isinstance(eyes, dict):
        return fall() if k > 1 else leave(NO_RETURN)
    if k > 1 and _diff_hash(tests) and _diff_hash(tests) == str(_d(_d(prev).get("fingerprint")).get("diff_hash") or ""):
        return leave(UNDONE.format(why=stop_why) if stop_why else EXITS["unchanged"])
    items = _items(eyes)
    if eyes.get("route") != FIX_ROUTE or not items:
        return leave(oneline.one_line(eyes.get("route_why") or "") or NOTHING)
    if k > LIMIT:
        return leave(EXITS["cap"], left=[dict(i) for i in items])
    if k == 1:
        plan = _first_plan(fixed, fix_in, replan, answer_replan)
        if plan is None:
            return fall()
    else:
        plan = {key: _d(prev).get(key) for key in ("plan", "fix_plan", "ripple", "plan_review", "answers", "skip_rerun")}
    only = _tied(items, plan_fields)
    notes = [f"{NOTE_HEAD} {item_text(i)}" for i in items]
    stages = fixed.get("stages") if isinstance(fixed.get("stages"), list) else []
    prior = _d(_d(stages[-1] if stages else None).get("fix")).get("carry") if stages else None
    return {**out, **plan, "go": True, "only_items": only, "item_kinds": _kinds(items, plan_fields, only), "notes": "\n".join([*notes, *([] if only else [UNTIED])]),
            "prior": prior if isinstance(prior, (dict, list)) else None, "rows": [*rows, row(k, eyes, items)]}


def _first_plan(fixed: dict, fix_in, replan, answer_replan) -> dict | None:
    """1 周目に返しの修正へ渡す案の欄。最後の修正の段が使った案の選びは合わせ（stages.fixed）が持つので plan はその物を運び、ほかは
    合わせの refixed の真偽で引き分ける: 真なら案の直しの後の修正（refix-run）と同じ出どころ、偽なら 1 回目の修正と同じ出どころ。
    refixed が真で案の直しか答えの返りが無ければ None（読めない）"""
    if fixed.get("refixed") is True:
        if not isinstance(replan, dict) or not isinstance(answer_replan, dict):
            return None
        return {"plan": fixed.get("plan"), "fix_plan": replan.get("fix_plan"), "ripple": answer_replan.get("fix_ripple"),
                "plan_review": answer_replan.get("plan_review"), "answers": answer_replan.get("fix_answers"),
                "skip_rerun": list(answer_replan.get("skip_rerun") or [])}
    first = _d(fix_in)
    return {"plan": fixed.get("plan"), "fix_plan": first.get("fix_plan"), "ripple": fixed.get("ripple"), "plan_review": first.get("review"),
            "answers": first.get("answer"), "skip_rerun": list(first.get("skip_rerun") or [])}


# ---------------------------------------------------------------- 最後の周の状態
def last(heads) -> dict | None:
    """周の頭の出力の並び（飛んだ周は None）から、最後に走った周の頭の状態を選ぶ。1 度も返さなかった run では最初の周の頭が最初の
    状態をそのまま持つ。1 つも走っていなければ None"""
    ran = [h for h in heads or [] if isinstance(h, dict)]
    return {key: ran[-1].get(key) for key in RECORD} if ran else None


def current(eyes_back, fixed, tests, eyes) -> tuple:
    """最後の周の状態 (fixed, tests, eyes) を選ぶ 1 か所。輪の記録の側を取るのは、記録が在り、その exit が『輪の節が落ちた』でなく、記録の
    fixed が null でない時だけ。ほかは渡された最初の物を返す（輪の記録の無い run・集めが落ちた記録・状態が欠けた記録）"""
    record = _d(eyes_back)
    if record and record.get("exit") != EXITS["fell"] and record.get("fixed") is not None:
        return record["fixed"], record.get("tests"), record.get("eyes")
    return fixed, tests, eyes


# ---------------------------------------------------------------- 返した周の行
def lines(rows, exit_: str = "", left=()) -> list:
    """最後の承認ノードと報告が同じ行に読む、返した周の行。返した周ごとに『k 周目: 返した（R1: <語>・R2: <語>）——返した項目: …』を並べ、
    返した周が 1 つ以上在れば返した段が通っていない確かめの 1 行と、抜けた訳の 1 行（残った作り残しがあれば名指す）を付ける。0 回の時は、
    目が返そうとした項目 left が在れば返さなかった訳と項目の 1 行（UNRETURNED）、無ければ空。目の語の言い方は gatemarks.REVIEW_WORDS
    （字をここで持たない）"""
    done = [r for r in rows or [] if isinstance(r, dict)]
    if not done:
        return [UNRETURNED.format(why=exit_ or "訳の記録が無い", items=left_text(left))] if left_text(left) else []
    word = lambda s: gatemarks.REVIEW_WORDS.get(s, s or "判定の語が無い")   # noqa: E731
    out = [f"{r.get('round')} 周目: 返した（R1: {word(r.get('r1'))}・R2: {word(r.get('r2'))}）——返した項目: "
           + ("／".join(item_text(i) for i in r.get("items") or [] if isinstance(i, dict)) or "無し") for r in done]
    out.append(NOT_REVIEWED)
    if exit_:
        out.append(f"輪を抜けた訳: {cap_text(left) if exit_ == CAP_WHY else exit_}")
    return out


def broken(eyes_back, head) -> bool:
    """返す輪が途中で落ちたか: 集め eyes-back の記録が無い（null）のに周の頭 back-1 が走った。周の節が中の誤りで落ちると、Archon の
    none_failed_min_one_success は前が落ちて飛んだ節を落ちた節と同じに数えるので、集め・封じ・最後の承認ノードまで飛ぶ（封じないので
    差分は当たらない）。報告の状態は current が選ぶ最初の物（返す前の物）になるので、報告がそう言う"""
    return eyes_back is None and isinstance(head, dict)
