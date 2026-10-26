"""書き手の型の block（workflows/weapon-<型>/）の 3 本の script の本体（docs/plans/2026-10-24-fix-weapons.md の 11.10 の 1）。

各 block の scripts/writer_prep.py・writer_save.py・writer_out.py は、PEP 723 の頭・sys.path の 2 行・`import writerblock` と `from src import render`・
`writerblock.prep(render)`（writer_save.py は `writerblock.save()`、writer_out.py は `writerblock.out()`）だけで、6 つの block で 1 字も違わない。型の名は渡さない:
呼んだ script の在る block のフォルダの名 `weapon-<w>`（ports.caller_block）から引く。型ごとに違う物は block の src/render.py の表だけ。

- prep(table) -> {prompt}: 入力 order・slots を ports.json で読み、order.weapon が表の ORDER_WEAPON と違えば落ち（型の名と block の
  食い違いを書けなくする）、slots の values・when に型が持つ値と段落を足して（slots の名と重なれば落ちる）、指示を prompt.emit で
  組む。型が持つ値と段落は下の 2 つだけ。標準出力へ返りを書き、返りの dict を返す
  - 値: first_prompt（この block の place の <w>-prompt-1.md。続きの周が読み直す 1 回目の指示）・unattended・overlay_file
    （借りた写しの固定を照らしてから組む。範囲の相談の答えの後・はみ出しを相談に積んだ周は続きの段落だけを組む周なので、今と同じく
    空）・summary_file（表の SUMMARY が真の型だけ。slots の上の段の欄 summary_file を写す。空なら (empty)。続きの周は空）・g1_items（下請けの
    項目ごとの行。表の SPAWNS が真で、続きの周でなく、slots の subagents.owed が空でない時だけ。それ以外は空）
  - 段落: paragraphs(table) の spawns・g1・ask_variant。g1 は下請けの項目が 0 件なら偽に下ろし、ask_variant は slots の段落 ask が
    偽なら偽に下ろす（今の writer_values と同じ向き）
  - 下請け（表の SPAWNS が真の型。subagent_items）: slots の subagents から、項目ごとに g1-impl-<n>.md・g1-review-<n>.md を、brief の在る run は
    seat-briefs.md も、この block の place に書く（md は .shared/prompts の g1-*.md・seat-briefs.md を prompt.render_shared で組む。値と借りた型の
    埋めは lib/subagents.py）。g1-impl の {weapon_rule} は、この block の prompts/parts/head.md を prompt.render_part("head", {}) で組んだ字
    （型の決まり。下請けの実装役の手順書の「試験を書け」とぶつかる型の決まりを、文を 2 か所に写さずに渡す。11.8 の決め〔案 B〕）。
    借りた写しの固定の照合（seat.pinned）は下請けのファイルの書き込みより前。続きの周は組まない
- save() -> {saved}: 入力 reply（AI の node の出力）を ports.json で形（shared:writer-reply.schema.json）に照らし、place の
  reply-<n>.json に書く。<n> = prompt.round_of(<w>) - 1（同じ周の <w>-prep が書いた <w>-prompt-<n>.md と対）。形に合わなければ
  落ちる（返す節に結ばれない node なので落ちてよく、落ちればその周の終わりに内の輪が落ちる。計画の 11.3 の「落ちた周の守り」）
- out() -> {ok, reason, reply, report}: 入力を持たず、落ちない（K1。ports.run）。同じ <n> で、place に <w>-prompt-<n>.md が無いか
  out-<n>.json が在れば prep が落ちた周（前の周の返答を返し直さない）、reply-<n>.json が無ければ書き手か save が落ちた周で、どちらも
  ok: false・reply: null・report に reason の 1 行。ほかは ok: true と reply-<n>.json の pointer。返りは out-<n>.json にも書く。
  prep が落ちた周（<n> は前の周の番号で、書くと前の周の控えを消す）と fallback の時は書かない
- paragraphs(table) -> {spawns, g1, ask_variant}: 表の SPAWNS から引く下請けの段落の真偽（place を読まない。試験が同じ関数を読む）

表 table（block の src/render.py）は定数 ORDER_WEAPON（注文の weapon の語）・SPAWNS（下請けを起こすか）・SUMMARY（TDD の輪の要約を
受けるか）を 3 つとも持つ。既定の値は持たず、欠ければ落ちる。
"""
import json
import os
import pathlib

import ports
import prompt

import seat  # （lib/。ports を読むと lib/ が sys.path に入る）
import spseam  # （lib/）
import subagents  # （lib/）

ORDER_SCHEMA = "shared:weapon-order.schema.json"
SLOTS_SCHEMA = "shared:writer-slots.schema.json"
REPLY_SCHEMA = "shared:writer-reply.schema.json"
REPLY_FORM = f"json({REPLY_SCHEMA})"
BLOCK_HEAD = "weapon-"
EMPTY = "(empty)"   # 輪の要約が無い時の字（修正の block の prompts.shown と同じ字）
CONTINUING = ("resume", "overflow_answer", "queued")   # 続きの段落だけを組む周の段落


def weapon_block() -> str:
    """呼んだ script の在る block のフォルダの名から引いた block の名 `weapon-<w>` の <w>（node の id・md の名・グラフの名の末尾と同じ）"""
    name = ports.caller_block().name
    if not name.startswith(BLOCK_HEAD):
        raise ValueError(f"書き手の型の block のフォルダの名は {BLOCK_HEAD}<型>（{name!r}）")
    return name[len(BLOCK_HEAD):]


def _constant(table, name: str, kind: type):
    if not hasattr(table, name):
        raise ValueError(f"{ports.caller_block().name}/src/render.py に表の定数 {name} が無い（どの型も 3 つとも書く。既定の値は持たない）")
    value = getattr(table, name)
    if type(value) is not kind:
        raise ValueError(f"表の定数 {name} は {kind.__name__}（{value!r}）")
    return value


def paragraphs(table) -> dict:
    """表の SPAWNS から引く下請けの段落の真偽。place を読まない"""
    spawns = _constant(table, "SPAWNS", bool)
    return {"spawns": spawns, "g1": spawns, "ask_variant": spawns}


def _seat() -> tuple[str, str]:
    """(unattended, overlay_file)。借りた写しが固定と合わなければ落ちる（今の writer_values と同じ理由の文）"""
    try:
        seat.pinned()
        return seat.overlay_body(seat.OVERLAY_KINDS["fix"]).rstrip("\n"), str(spseam.BORROW_DIR / spseam.OVERLAY_FILE)
    except ValueError as error:
        raise ValueError(f"修正役の座を組めない: {error}") from None


def subagent_items(place, sub: dict) -> str:
    """slots の subagents（下請けを起こす単位 sub["owed"] が空でない）から、項目ごとの下請けのファイルを place に書き、修正役の指示の
    {g1_items} の字（項目ごとの 1 行を改行で並べた物）を返す。借りた写しの固定が合わなければ ValueError（呼び手が先に seat.pinned を呼ぶ）。
    実装役の指示 g1-impl の {weapon_rule} には、この block の prompts/parts/head.md（型の決まりの頭の段落）を空の値で組んだ字を渡す
    （表の SPAWNS が真の型だけがここへ来る。head.md に {名} が在れば prompt.render が値の欠けで落ちる。黙って空の字にしない）"""
    place = pathlib.Path(place)
    shown = {"scene": "g1-scene", "impl_report": "g1-impl-report", "report": "g1-report", "head_sha": "g1-head-sha"}
    texts = {key: prompt.render_shared(name, {}).strip() for key, name in shown.items()}
    rest = lambda key: prompt.render_shared("g1-rest", {"keys": key}).strip()   # noqa: E731
    if sub["seat_brief_rows"]:
        (place / subagents.SEAT_BRIEFS).write_text(prompt.render_shared("seat-briefs", {"brief_rows": sub["seat_brief_rows"]}), encoding="utf-8")
    rows = subagents.entries(place, sub, rest_title=rest, **texts)
    weapon_rule = prompt.render_part("head", {}).strip()
    asking = bool(sub["check_cmd"])   # 範囲の相談の節が入る周だけ、下請けに事前の確かめを走らせる
    for entry in rows:
        pathlib.Path(entry["impl_file"]).write_text(
            prompt.render_shared("g1-impl", {"template": entry["impl_template"], "check_cmd": sub["check_cmd"], "weapon_rule": weapon_rule},
                                {"spawns": False, "ask": asking}),
            encoding="utf-8")
        pathlib.Path(entry["review_file"]).write_text(prompt.render_shared("g1-review", {"template": entry["review_template"]}, {"spawns": False}),
                                                      encoding="utf-8")
    return "\n".join(f"- {subagents.row(entry)}" for entry in rows)


def _added(table, weapon: str, slots: dict, place) -> tuple[dict, dict]:
    """型が持つ (値, 段落)。slots の名と重なれば落ちる"""
    when = slots["when"]
    values = {"first_prompt": str(place / f"{weapon}-prompt-1.md"), "unattended": "", "overlay_file": "", "g1_items": ""}
    continuing = any(when[name] for name in CONTINUING)
    para = paragraphs(table)
    if not continuing:
        values["unattended"], values["overlay_file"] = _seat()   # 写しの照合を、下請けのファイルの書き込みより前に
        if para["spawns"] and slots["subagents"]["owed"]:
            try:
                values["g1_items"] = subagent_items(place, slots["subagents"])
            except ValueError as error:   # 写しの固定との食い違いも md と値の食い違いも、座を組めない落ち方（今の writer と同じ文）
                raise ValueError(f"修正役の座を組めない: {error}") from None
    if _constant(table, "SUMMARY", bool):   # 続きの周は輪の要約も組まない（今の writer_values の早い返りと同じく空）
        values["summary_file"] = "" if continuing else slots["summary_file"] if slots["summary_file"].strip() else EMPTY
    para["g1"] = para["g1"] and bool(values["g1_items"])   # 下請けの項目が 0 件の周は偽
    para["ask_variant"] = para["ask_variant"] and when["ask"]   # 下請けの相談の 1 文は、相談の節が入る周だけ
    for kind, added, given in (("値", values, slots["values"]), ("段落", para, when)):
        clash = sorted(set(added) & set(given))
        if clash:
            raise ValueError(f"型の block が足す{kind} {clash} が slots の{kind}の名と重なる")
    return values, para


def prep(table) -> dict:
    weapon = weapon_block()
    order = ports.json(os.environ.get("INPUTS_ORDER"), ORDER_SCHEMA)
    slots = ports.json(os.environ.get("INPUTS_SLOTS"), SLOTS_SCHEMA)
    expected = _constant(table, "ORDER_WEAPON", str)
    if order["weapon"] != expected:
        raise ValueError(f"block {BLOCK_HEAD}{weapon} が受ける注文の型は {expected!r}（注文の weapon は {order['weapon']!r}）")
    values, para = _added(table, weapon, slots, ports.place())
    out = prompt.emit(weapon, {**slots["values"], **values}, {**slots["when"], **para}, prompt.round_of(weapon))
    result = {"prompt": out["prompt"]}
    ports.returns(result)
    return result


def _number(weapon: str) -> int:
    """この周の指示の番号（同じ周の <w>-prep が <w>-prompt-<n>.md を書いた後なので round_of は n+1。reply- のファイルは数えない）"""
    return prompt.round_of(weapon) - 1


def save() -> dict:
    weapon = weapon_block()
    reply = ports.json(os.environ.get("INPUTS_REPLY"), REPLY_SCHEMA)
    path = ports.place() / f"reply-{_number(weapon)}.json"
    path.write_text(json.dumps(reply, ensure_ascii=False), encoding="utf-8")
    result = {"saved": True}
    ports.returns(result)
    return result


def _failed(reason: str) -> dict:
    return {"ok": False, "reason": reason, "reply": None, "report": [reason]}


def out() -> None:
    def compute() -> dict:
        weapon = weapon_block()
        place, n = ports.place(), _number(weapon)
        reply, kept = place / f"reply-{n}.json", place / f"out-{n}.json"
        if not (place / f"{weapon}-prompt-{n}.md").is_file() or kept.exists():
            # <n> は前の周の番号なので out-<n>.json を書かない（前の周の控えを消さない）
            return _failed(f"この周の指示を組む node {weapon}-prep が落ちた（前の周の返答を返し直さない）")
        if not reply.is_file():
            result = _failed(f"書き手の返答が無い（書き手の AI の node か、返答を置く node {weapon}-save が落ちた）")
        else:
            result = {"ok": True, "reason": "", "reply": ports.pointer(reply, REPLY_FORM), "report": []}
        kept.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result

    ports.run(compute, lambda reason: _failed(f"返す node が落ちた（{reason}）"))
