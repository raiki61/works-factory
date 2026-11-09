"""独立の目から修正の段へ返す輪の、周の頭の決めと周の記録の行の形と最後の周の状態の選び（docs/design/line.md の 1.3・4.3・5.4）。

独立の目（eyes）の判定が作り切れていない所を言った時（eyes の route が fix）に、今の作業ツリーのまま修正の段へ名指しで返し、直した後に最後の
試験と独立の目をもう一度通す。周は line の一番上に LIMIT 周分並べ（周 k の節は back-k〔周の頭〕・back-k-fix〔修正〕・back-k-fixed〔段の合わせ〕・
back-k-gate〔最後の試験〕・back-k-eyes〔独立の目〕と、それぞれの受け皿）、最後に上限の訳を記録するだけの周の頭 back-(LIMIT+1) と、最後に走った
周の頭を集める eyes-back を置く。書き手（周の頭と集め）と読み手（最後の承認ノード・報告の節・封じ）はどれも line の中なので、周の記録の形と
抜ける訳の字はここの 1 か所に置く。返した段が止まった・落ちた周は、その周の試験と目が無いので、返す前に最後に試験と独立の目を通った周の
状態（前の周の頭が運ぶ）を持ち越して封じ、戻す先の木を checkpoint に書く。
封じる前には、返した段の試験を通っていない書き換えが残る作業ツリーを checkpoint の木へ戻し、その書き換えを控えに分ける（restore_before_seal）。

- LIMIT: 返す周の数（YAML の周の節の数と同じ数。周の頭 turn はここを直に読む）。計画の往復の上限 rounds.LIMIT とは別の物
- HEAD: 最後の承認ノードと報告が返した周の節に付ける見出し
- FIELDS: 周の頭の出力の欄の名。RECORD: 集め eyes-back の出力の欄の名（最後に走った周の頭の状態）。どちらも checkpoint（返す前の状態を封じた時の周の番号と戻す先の木。ほかは null）を持つ
- EXITS・CAP_WHY: 輪を抜けた訳の字（fell・stop・unchanged・no_fix・cap。目の route が stay の時は目の route_why が訳）
- SEALED_FIXED: 返す前の状態を封じる時に、返した段の合わせから前の周の合わせの物に替える欄（封じる差分を語る欄）
- row(k, eyes, items, tree)・count(rows)・capped(record)・left_text(left): 周の記録の行と数え方（行の tree は返す時の木）
- tree_now(repo) -> 今の作業ツリーの木の sha（読めなければ空の字）。script が turn の snap に渡す
- turn(...) -> 周の頭の出力: 返すかを決め、返す時は修正の段への入力（only_items・item_kinds〔返した項目の種を修正案の項目の番号ごとに運ぶだけ。型の語は
  修正の段が引く。prior が null の段へは空〕・notes・prior ほか）を組み、snap で返す時の木を取る
- restore_before_seal(repo, checkpoint, fingerprint, kept) -> {restored, kept, reason}: 封じる前に作業ツリーを返す前の木へ戻し、返した段の書き換えを kept に控える
  （line の src で作業ツリーを書く唯一の関数）。戻せなかった訳の字は RESTORE_NO_TREE・RESTORE_ERROR・RESTORE_DIFFERS
- last(heads) -> 集め eyes-back の出力・current(eyes_back, fixed, tests, eyes) -> (fixed, tests, eyes): 最後の周の状態の選びの 1 か所
- lines(rows, exit_, left, checkpoint, back_restore) -> 最後の承認ノードと報告が同じ行に読む返した周の行（返したが直せなかった項目・封じに出したのが
  返す前の状態であること・戻しの結末・差分が変わらなかったので返す前と同じ状態であることも言う。字は UNFIXED・SEALED_BEFORE・KEPT_AWAY・UNTOUCHED・
  RESTORE_FAILED・NO_RESTORE_RECORD・SAME_AS_BEFORE）
- broken(eyes_back, head) -> 集めが飛んだのに周の頭が走ったか（報告が BROKE の 1 行を出す）
"""
from __future__ import annotations

import re

import gatemarks
import green_cert
import leftovers
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
UNFIXED = "返したが直せなかった項目: {items}"
SEALED_BEFORE = "封じに出したのは {round} 周目に返す前の状態（最後の試験と独立の目を通った物）"
KEPT_AWAY = "返した段の書き換えは作業ツリーから戻し、{kept} に差分として控えた（git apply で戻せる）"
KEPT_AT = "返した段の書き換えは {kept} に差分として控えた（git apply で戻せる）"
UNTOUCHED = "返した段は作業ツリーを変えていなかった"
RESTORE_FAILED = "返す前の状態へ戻せなかった（{reason}）"
NO_RESTORE_RECORD = "戻しの結末の記録が無い"
SAME_AS_BEFORE = "返しの修正で差分が変わらなかったので、封じに出したのは返す前と同じ状態"
UNTIED = "返す項目を修正案の項目に結べなかったので、全部の項目を対象にする"
NOTE_HEAD = "独立の目"
FIELDS = ("go", "round", "only_items", "notes", "prior", "plan", "fix_plan", "ripple", "plan_review", "answers", "skip_rerun", "more", "rows",
          "exit", "left", "fixed", "tests", "eyes", "fingerprint", "green_ok", "eyes_ok", "sealable", "item_claims", "item_kinds", "checkpoint")
RECORD = ("rows", "exit", "left", "fixed", "tests", "eyes", "fingerprint", "green_ok", "eyes_ok", "sealable", "item_claims", "checkpoint")
SEALED_FIXED = ("diff", "diffed", "changed", "units", "groups", "item_claims")
FIX_ROUTE = "fix"
UNFINISHED = "unfinished"   # 返す項目の種のうち作り残し（直す前の赤を求める側）。種の語の列挙の正本は独立の目の出力の形
RESTORE_NO_TREE = "戻す先の木が記録に無い（返す周の頭が作業ツリーの木を取れなかった）ので、作業ツリーを返す前の姿に戻せなかった"
RESTORE_ERROR = "作業ツリーを返す前の姿に戻す途中で落ちた（書き換えの控えを書けなかったか、戻しの git が失敗した）"
RESTORE_DIFFERS = "作業ツリーを返す前の木に戻したが、返す前の指紋と合わない（返した段が commit したか、HEAD を動かした）"
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


def row(k: int, eyes, items: list, tree: str = "") -> dict:
    """周の記録の行: k 回目に返した時の R1・R2 の判定の語と、返した項目と、返した時の作業ツリーの木（tree。取れなかった行は欄を持たない）"""
    word = lambda eye: str(_d(_d(eyes).get(eye)).get("status") or "")   # noqa: E731
    return {"round": k, "r1": word("r1"), "r2": word("r2"), "items": [dict(i) for i in items], **({"tree": tree} if tree else {})}


def tree_now(repo) -> str:
    """repo の作業ツリーの今の姿の木の sha（lib の leftovers.snapshot。作業ツリーも本物の index も変えない）。読めなければ空の字を返す
    （周の頭が落ちて『輪の節が落ちた』と読まれないように。木が空なら戻す側が閉じた側に倒れる）"""
    try:
        return leftovers.snapshot(repo)
    except (leftovers.Unreadable, OSError):
        return ""


def _no_tree() -> str:
    return ""


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
    結べた項目の番号とその指摘の種。ただし結べなかった指摘に作り残し（unfinished）が 1 つでも在れば、その指摘は notes でだけ渡り
    どの項目で直されるか分からないので、only の全部の項目を unfinished にする（赤の義務を黙って外さない。持ち主の決め no-silent-loosen）。
    結べず全部を対象にした時は、全部の項目の番号に返した種を並べる。種の無い指摘は行を作らない"""
    if only:
        ties = _ties(items, plan_fields)
        tied = [id(i) for i, _ in ties]
        if any(i.get("kind") == UNFINISHED and id(i) not in tied for i in items):
            return [{"item": n, "kind": UNFINISHED} for n in only]
        pairs = [(n, i.get("kind")) for i, n in ties]
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
            "item_claims": _d(fixed).get("item_claims"), "item_kinds": [], "checkpoint": None}


def _held(k, fixed, prev, rows, more, why) -> dict | None:
    """k が 2 以上で、返した段が止まった・落ちたせいでその周の試験か目の返りが欠けた時の、返す前の状態を封じる記録。前の周の頭（返した周）が
    運ぶ試験・目・合わせが、返す前に最後に試験と独立の目を通った状態なので、それを持ち越す。記録の fixed は返した段の合わせを土台にし、
    封じる差分を語る欄 SEALED_FIXED だけを前の周の合わせの物に替える（異議・人に回した物・段ごとの止めの語は返した段の物のまま届く）。
    left は前の周が返した項目、checkpoint は戻す先（前の周 k-1 の頭が返す時に取った木。取れていなければ空の字）。前の周の記録が読めない
    時は None（呼び手が閉じた側に倒す）"""
    before = _d(prev).get("fixed")
    if not (isinstance(before, dict) and isinstance(prev.get("tests"), dict) and isinstance(prev.get("eyes"), dict)):
        return None
    sealed = {**fixed, **{key: before[key] for key in SEALED_FIXED if key in before}}
    last = rows[-1] if rows else {}
    return {**_base(k, sealed, prev["tests"], prev["eyes"], rows, more), "exit": why, "left": [dict(i) for i in last.get("items") or []],
            "checkpoint": {"round": k - 1, "tree": last.get("tree") or ""}}


def turn(*, k: int, prev, fixed, judged, fix_in, tests, eyes, replan, answer_replan, plan_fields, snap=_no_tree) -> dict:
    """周 k の頭の決め。返す時は go を真にして修正の段への入力を組み、snap（引数無しで木の sha の字を返す関数）で返す時の作業ツリーの木を
    新しい周の行に置く（返さない抜け方では snap を呼ばない）。抜ける時は go を偽にして exit に訳を書く。周の頭はどの周も走る
    （Archon は飛んだ node の出力を when: が読むと誤りにするので、頭に when: を置かない）。前の周の頭が返さなかった周は何もせず、
    前の周の頭の記録（抜けた訳・返した周の行・残った作り残し・最後の状態）をそのまま運ぶ。決める順:
    0. k が 2 以上で前の周の頭が返さなかった（go が真でない）→ 前の記録をそのまま運ぶ
    1. 前の周の頭か合わせが欠けた（k が 2 以上で prev が無い・fixed が無い）→ 輪の節が落ちた。k が 2 以上なら状態は持たず封じない
    2. 前の段の修正の stop_reason か異議が空でない・合わせが進めない（k が 1 なら判定の stop_reason も）→ 修正の段が止めた。合わせの
       stop_why（止めの語と組の止めた訳）が在れば『（<語か合わせが進めなかった旨>：<stop_why>）』と組で載せる。
       合わせの no_fix が真（直す物が無い run。計画が無いので修正役を起こせない）→ 直す物が無い run は返さない。
       どちらも、目が返そうとした項目を left に運ぶ（周の行が 0 でも lines が名指す）。k が 2 以上で試験か目の返りが欠けていれば
       止めの訳のまま、返す前の状態を封じる（_held）。試験と目が揃っていれば、その周の状態のまま封じる
    3. 試験か目の返りが欠けた → k が 2 以上なら輪の節が落ちたとして、返す前の状態を封じる（_held。前の周の記録が読めなければ封じない）。
       1 周目は目か試験が返らなかっただけ（輪の節は落ちていない）なので返す物を読めない訳で抜ける
    4. k が 2 以上で試験の指紋の diff_hash が前の周と同じ → 返しの修正で差分が変わらなかった（stop_why が在れば UNDONE で修正の段が
       直さなかった訳を添える。その周の状態を封じ、戻す先は無い）
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
        return {**_base(k, None, None, None, rows, more), "exit": EXITS["fell"]} if k > 1 else leave(EXITS["fell"])
    if not isinstance(fixed, dict) or (k > 1 and not isinstance(prev, dict)):
        return fall()
    lacking = not isinstance(tests, dict) or not isinstance(eyes, dict)
    pending = [dict(i) for i in _items(eyes)] if _d(eyes).get("route") == FIX_ROUTE else []
    stops = [str(fixed.get("stop_reason") or ""), oneline.one_line(fixed.get("objection") or ""),
             str(_d(judged).get("stop_reason") or "") if k == 1 else ""]
    why = next((s for s in stops if s), "" if fixed.get("go") is True else "修正の段の合わせが進めなかった")
    stop_why = oneline.one_line(fixed.get("stop_why") or "")
    if why:
        stop = f"{EXITS['stop']}（{why}：{stop_why}）" if stop_why else f"{EXITS['stop']}（{why}）"
        return (_held(k, fixed, prev, rows, more, stop) if k > 1 and lacking else None) or leave(stop, left=pending)
    if fixed.get("no_fix") is True:
        return leave(EXITS["no_fix"], left=pending)
    if lacking:
        return (_held(k, fixed, prev, rows, more, EXITS["fell"]) or fall()) if k > 1 else leave(NO_RETURN)
    if k > 1 and _diff_hash(tests) and _diff_hash(tests) == str(_d(_d(prev).get("fingerprint")).get("diff_hash") or ""):
        return leave(UNDONE.format(why=stop_why) if stop_why else EXITS["unchanged"], left=pending)
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
    prior = prior if isinstance(prior, (dict, list)) else None
    # 前の段が申し送りを持たない（carry が null）段へは種を渡さず元の案の route で回す（修正の block は prior の無い段への種を拒む）
    kinds = _kinds(items, plan_fields, only) if prior is not None else []
    return {**out, **plan, "go": True, "only_items": only, "item_kinds": kinds, "notes": "\n".join([*notes, *([] if only else [UNTIED])]),
            "prior": prior, "rows": [*rows, row(k, eyes, items, snap())]}


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


# ---------------------------------------------------------------- 封じる前の戻し
def restore_before_seal(repo, checkpoint, fingerprint, kept) -> dict:
    """返す前の状態を封じる時（checkpoint が在る時）に、作業ツリーを返す前の木 checkpoint["tree"] に戻す（line の src で作業ツリーを書く唯一の関数）。
    封じと当ては今の作業ツリーを読むので、返した段の試験を通っていない書き換えが残ったままだと、返す前の状態を封じられない。
    戻す前に、返す前の木から今の作業ツリーへの差分を kept（Path）に書く（git apply で作業ツリーへ戻せる）。結末は
    {"restored": 戻して指紋が合ったか, "kept": 控えを書いたらそのパス（書かなければ空）, "reason": 戻せなかった訳（RESTORE_*。戻した・触らなかった時は空）}。
    checkpoint が dict でない時と、指紋がもう今の作業ツリーと合う時は、作業ツリーにも kept にも触らない。戻せない・合わない時は封じる側の
    指紋の照らしが拒む（閉じた側に倒れる）"""
    out = {"restored": False, "kept": "", "reason": ""}
    if not isinstance(checkpoint, dict) or green_cert.matches(fingerprint, repo):
        return out
    tree = checkpoint.get("tree")
    if not isinstance(tree, str) or not tree:
        return {**out, "reason": RESTORE_NO_TREE}
    try:
        patch = green_cert.diff_between(repo, tree, leftovers.snapshot(repo))
        kept.parent.mkdir(parents=True, exist_ok=True)
        kept.write_bytes(patch)
    except (leftovers.Unreadable, OSError, ValueError):
        return {**out, "reason": RESTORE_ERROR}
    out["kept"] = str(kept)
    try:
        leftovers.restore(repo, tree)
    except (leftovers.Unreadable, OSError):
        return {**out, "reason": RESTORE_ERROR}
    if not green_cert.matches(fingerprint, repo):
        return {**out, "reason": RESTORE_DIFFERS}
    return {**out, "restored": True}


# ---------------------------------------------------------------- 最後の周の状態
def last(heads) -> dict | None:
    """周の頭の出力の並び（飛んだ周は None）から、最後に走った周の頭の状態を選ぶ。1 度も返さなかった run では最初の周の頭が最初の
    状態をそのまま持つ。返した段が止まった・落ちた周の頭は、返す前に最後に試験と独立の目を通った状態と戻す先 checkpoint を持つ。
    1 つも走っていなければ None"""
    ran = [h for h in heads or [] if isinstance(h, dict)]
    return {key: ran[-1].get(key) for key in RECORD} if ran else None


def current(eyes_back, fixed, tests, eyes) -> tuple:
    """最後に試験と独立の目を通った周の状態 (fixed, tests, eyes) を選ぶ 1 か所。輪の記録の側を取るのは、記録が在り、記録の fixed が null
    でない時だけ（返した段が止まった・落ちた周の記録は、返す前の状態を持ち越して fixed が null でない）。ほかは渡された最初の物を返す
    （輪の記録の無い run・集めが落ちた記録・状態が欠けた記録）"""
    record = _d(eyes_back)
    if record and record.get("fixed") is not None:
        return record["fixed"], record.get("tests"), record.get("eyes")
    return fixed, tests, eyes


# ---------------------------------------------------------------- 返した周の行
def _sealed_lines(exit_: str, checkpoint, back_restore) -> list:
    """封じに出した状態の出どころの行: checkpoint（返す前の状態を封じた周の記録）が在れば封じたのが返す前の状態であることと戻しの結末（戻せなくても控えが在ればその在りか）を、
    抜けた訳が差分の変わらなかった時は返す前と同じ状態であることを言う"""
    out = []
    if isinstance(checkpoint, dict):
        out.append(SEALED_BEFORE.format(round=checkpoint.get("round")))
        if not isinstance(back_restore, dict):
            out.append(NO_RESTORE_RECORD)
        elif back_restore.get("reason"):
            out.append(RESTORE_FAILED.format(reason=back_restore["reason"]))
            if back_restore.get("kept"):
                out.append(KEPT_AT.format(kept=back_restore["kept"]))
        elif back_restore.get("restored"):
            out.append(KEPT_AWAY.format(kept=back_restore.get("kept") or ""))
        else:
            out.append(UNTOUCHED)
    if str(exit_ or "").startswith(EXITS["unchanged"]):
        out.append(SAME_AS_BEFORE)
    return out


def lines(rows, exit_: str = "", left=(), checkpoint=None, back_restore=None) -> list:
    """最後の承認ノードと報告が同じ行に読む、返した周の行。返した周ごとに『k 周目: 返した（R1: <語>・R2: <語>）——返した項目: …』を並べ、
    返した周が 1 つ以上在れば返した段が通っていない確かめの 1 行と、抜けた訳の 1 行を付ける。上限の抜け方の訳は残った作り残しを名指し、ほかの
    抜け方で残った作り残し left が在れば返したが直せなかった項目の 1 行（UNFIXED）を足す。checkpoint（返す前の状態を封じた周の記録）が在れば
    封じに出したのが何周目に返す前の状態かの行（SEALED_BEFORE）と、戻しの結末 back_restore（封じる前の戻しの返り。null は記録が無い）を言う
    行を足し、抜けた訳が差分の変わらなかった時は返す前と同じ状態の行（SAME_AS_BEFORE）を足す。0 回の時は、目が返そうとした項目 left が在れば
    返さなかった訳と項目の 1 行（UNRETURNED）、無ければ空。目の語の言い方は gatemarks.REVIEW_WORDS（字をここで持たない）"""
    done = [r for r in rows or [] if isinstance(r, dict)]
    if not done:
        return [UNRETURNED.format(why=exit_ or "訳の記録が無い", items=left_text(left))] if left_text(left) else []
    word = lambda s: gatemarks.REVIEW_WORDS.get(s, s or "判定の語が無い")   # noqa: E731
    out = [f"{r.get('round')} 周目: 返した（R1: {word(r.get('r1'))}・R2: {word(r.get('r2'))}）——返した項目: "
           + ("／".join(item_text(i) for i in r.get("items") or [] if isinstance(i, dict)) or "無し") for r in done]
    out.append(NOT_REVIEWED)
    if exit_:
        out.append(f"輪を抜けた訳: {cap_text(left) if exit_ == CAP_WHY else exit_}")
    if exit_ != CAP_WHY and left_text(left):
        out.append(UNFIXED.format(items=left_text(left)))
    return [*out, *_sealed_lines(exit_, checkpoint, back_restore)]


def broken(eyes_back, head) -> bool:
    """返す輪が途中で落ちたか: 集め eyes-back の記録が無い（null）のに周の頭 back-1 が走った。周の節が中の誤りで落ちても、次の周の頭と集めは
    one_success で待つので走るが、周の頭そのものが落ちると集め・封じ・最後の承認ノードまで飛ぶ（封じないので差分は当たらない）。報告の
    状態は current が選ぶ最初の物（返す前の物）になるので、報告がそう言う"""
    return eyes_back is None and isinstance(head, dict)
