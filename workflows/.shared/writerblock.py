"""書き手の型の block（workflows/weapon-<型>/）の 2 本の script の本体（docs/plans/2026-10-24-fix-weapons.md の 11.10 の 1）。

各 block の scripts/writer_prep.py・writer_out.py は、PEP 723 の頭・sys.path の 2 行・`import writerblock` と `from src import render`・
`writerblock.prep(render)`（writer_out.py は `writerblock.out()`）だけで、6 つの block で 1 字も違わない。型の名は渡さない:
呼んだ script の在る block のフォルダの名 `weapon-<w>`（ports.caller_block）から引く。型ごとに違う物は block の src/render.py の表だけ。

- prep(table) -> {prompt}: 入力 order・slots を ports.json で読み、order.weapon が表の ORDER_WEAPON と違えば落ち（型の名と block の
  食い違いを書けなくする）、slots の values・when に型が持つ値と段落を足して（slots の名と重なれば落ちる）、指示を prompt.emit で
  組む。型が持つ値と段落は下の 2 つだけ。標準出力へ返りを書き、返りの dict を返す
  - 値: first_prompt（この block の place の <w>-prompt-1.md。続きの周が読み直す 1 回目の指示）・unattended・overlay_file
    （借りた写しの固定を照らしてから組む。範囲の相談の答えの後・はみ出しを相談に積んだ周は続きの段落だけを組む周なので、今と同じく
    空）・summary_file（表の SUMMARY が真の型だけ。slots の上の段の欄 summary_file を写す。空なら (empty)。続きの周は空）・g1_items（D1 は空）
  - 段落: paragraphs(table) の spawns・g1・ask_variant。g1 は下請けの項目が 0 件なら偽に下ろし、ask_variant は slots の段落 ask が
    偽なら偽に下ろす（今の writer_values と同じ向き）
- out() -> {ok, reply, report}: 入力 reply（AI の node の出力）を ports.json で形（shared:writer-reply.schema.json）に照らし、place の
  reply-<n>.json に書いて pointer で返す。<n> = prompt.round_of(<w>) - 1（同じ周の <w>-prep が書いた <w>-prompt-<n>.md と対）。
  形に合わなければ ok: false で返さずに落ちる（受け付けを飛んだ型と同じ null にして、返答が無かった周を黙って済ませない）
- paragraphs(table) -> {spawns, g1, ask_variant}: 表の SPAWNS から引く下請けの段落の真偽（place を読まない。試験が同じ関数を読む）

表 table（block の src/render.py）は定数 ORDER_WEAPON（注文の weapon の語）・SPAWNS（下請けを起こすか）・SUMMARY（TDD の輪の要約を
受けるか）を 3 つとも持つ。既定の値は持たず、欠ければ落ちる。
"""
import json
import os

import ports
import prompt

import seat  # （lib/。ports を読むと lib/ が sys.path に入る）
import spseam  # （lib/）

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


def _added(table, weapon: str, slots: dict, place) -> tuple[dict, dict]:
    """型が持つ (値, 段落)。slots の名と重なれば落ちる"""
    when = slots["when"]
    values = {"first_prompt": str(place / f"{weapon}-prompt-1.md"), "unattended": "", "overlay_file": "", "g1_items": ""}
    continuing = any(when[name] for name in CONTINUING)
    if not continuing:
        values["unattended"], values["overlay_file"] = _seat()
    if _constant(table, "SUMMARY", bool):   # 続きの周は輪の要約も組まない（今の writer_values の早い返りと同じく空）
        values["summary_file"] = "" if continuing else slots["summary_file"] if slots["summary_file"].strip() else EMPTY
    para = paragraphs(table)
    para["g1"] = para["g1"] and bool(values["g1_items"])   # 下請けの項目が 0 件の周は偽（D1 は下請けを移さないので、いつも空）
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


def out() -> dict:
    weapon = weapon_block()
    reply = ports.json(os.environ.get("INPUTS_REPLY"), REPLY_SCHEMA)
    path = ports.place() / f"reply-{prompt.round_of(weapon) - 1}.json"
    path.write_text(json.dumps(reply, ensure_ascii=False), encoding="utf-8")
    result = {"ok": True, "reply": ports.pointer(path, REPLY_FORM), "report": []}
    ports.returns(result)
    return result
