"""事前審査の壁打ち（依頼 231）の決まりと往復の控え。

事前審査（p2.plan_review）が修正案に block（直しへ進めない穴）を挙げたら、同じ会話の修正案の役に返して案を直させ、
直した案を新しい会話の事前審査に掛け直す。block の無い案だけが直しへ進む。同じ block が残れば（前のどの往復かの block と
重なれば）直しへ進まずに人の関所で止まる。止め時は decide（その docstring が正本）。往復の数を数える定数は持たない
（輪が回せる往復の静的な上限は呼び手が record_pass の at_cap で渡す）。

控えは盤面の今の周の作業ファイル plan-converge.json（読み書きはこの口だけ）:
{"round": n, "passes": [往復の行], "outcome": 語 | None, "open": {"answers": [...]}}
往復の行: {"pass": k, "blocks": [key], "faces": [{key, kind, where, why}], "suggests": [key],
          "answers": [{key, handled, how}], "resolved": [key], "persists": [key], "outcome": 語,
          "origins": {key: 出自の語}, "origins_claimed": [採らなかった申告の行],
          "files": {名: 写した先}, "rejects": [{role, at, reason}（その往復の計画と事前審査の拒否の行。stash_rejects）]}
          （輪の上限の周で止めた行だけ "capped": true が付く。事前審査の返答の一番上に止まった時の推し STUCK_PUSH が在った往復だけ
          "push": {answer, note, why} が付く。形は gatemarks が照らし、無人の run が止まった案を推しで進める時の元になる）
k 往復目の行の answers と resolved は、k-1 往復目の答えの要る穴（block と開いた項目の suggest。owed_faces）への修正案の役の答えと、
直した案を読んだ審査の言い分。
origins は 2 往復目からの新しい block（前のどの往復の block の key とも違う物）ごとの出自で、審査の申告を控えの事実（項目の行の
hash・前の往復の項目の id・resolved）で照らして機械が決めた語（ORIGIN_MISSED・ORIGIN_INTRODUCED・ORIGIN_REPHRASED・
ORIGIN_UNSPLIT）。lines の頭の行の数は origins だけから数え、採らなかった申告（origins_claimed）は数えない。見落としを数えるのは
後の往復が審査した所だけで、閉じて後の往復が見ない項目の取りこぼしは数に出ない（1 回目に出た割合はその上限）。run の後で
見つかった穴は割合に入らない。

項目ごとの壁打ち（線の木の段 1。設計 docs/plans/2026-10-06-tree-line.md の 2.3 の 5）: 受けた案の項目を note_plan が控えの
"plan"（[{id, unit_keys, hash}]。id は unit_keys の組・hash は名前に戻した項目の行の sha256）に置くと、往復の行に
"items"（[{n, id, unit_keys, hash, state, blocks, reopened}]）・"synergy"（相乗りの審査が挙げた key）・"face_units"
（{key: unit_keys}）が付く。face は unit_keys が重なる項目の物（どの項目とも重ならない face は審査した全部の項目の物）。
項目の state: block の無い項目は CLOSED（次の往復で審査も直しもしない）・block が前のどれかの往復の block と重なれば HELD
（保留。後の往復でも保留）・ほかは OPEN。閉じた項目は block に名指されれば開き直す（相乗りの審査の道）。抜け方は全部の項目が
閉じれば CLEAN、ほかは decide の決まりを開いた項目の block で読む（docstring が正本）。
note_plan の無い控え（行に items が無い）は今までどおり全体で 1 つ。

- block_faces(review)・decide(passes): block の face と、続けるか止めるかの語（CLEAN・AGAIN・PERSISTED・UNSETTLED）
- read(b)・pass_no(b)・note_answers(b, answers)・record_pass(b, review, ...)・stash_rejects(b, rows)・held(doc):
  控えの読み書き
- held・filled_units・splice・answer_gaps・revise_section は盤面でなく控え（read の形の dict）を取る（盤面を持つ呼び手は
  read(b) を渡す）。add_pass（record_pass の往復の行を足す半分）・plan_rows（note_plan の行）と共に、盤面を持たない呼び手
  （planfile。周ごとのファイルから控えを組み直す）も使う
- note_plan(b, rows)・open_items(b)・filled_units(doc)・splice(doc, rows)・item_id・item_hash: 項目の控え・次に審査する項目の番号・
  返答に無ければ機械が差し込む項目の単位・直しの役が返した変えた項目の行に前の往復の行を差し込んで案の全体を組む口
  （閉じた項目を変えた行は拒み、前と同じ行は捨てる。返答が案の全部なら閉じた項目だけを差し込む）
- planned_units(plan): 今の案に在る単位の key の集合を組む唯一の口（控えの plan の行からも修正案の役の出力の plan の行からも。
  carried_notes・受け付けの plan_review_output・修正前の関所の照らしが同じ集合を引く）。その下の plan_keys(plan) は案の順・
  重複のまま字の key を並べる読み口（planfile の受け付けの照らしも引く）。item_units(plan, n) はその上で項目 n の単位の集合
  （番号の外は空）を組む唯一の口
- owed_faces(doc, p): 往復の行 p の、次の往復で答えと照らしが要る穴（block と、開いた項目に付いた suggest）。項目の在る控えでは
  今の開いた項目の分だけ。この絞りの住処はここ 1 つ（止め時は decide）
- answer_gaps(doc, answers)・resolved_gaps(b, faces, resolved): 修正案の役と事前審査の役の返答の欄の欠けと誤りの行（owed_faces の
  穴の分）。fixed_unchanged(doc, rows, answers): fixed と答えて block の項目を変えていない答え
- split(role, reply): 返答から欄を外す（事前審査の返答の任意の欄 ITEMS（項目ごとの判定の要約）・DESIGN_MAP（独立設計との
  対応表）・出自 ORIGINS・一番上の止まった時の推し STUCK_PUSH は tree_split が外す。下請けの答えのファイルの当たりの答えの型は
  HITS_SCHEMA・出自の型は ORIGIN_SCHEMA）
- pushable(doc): 止まった壁打ちを役の推しで越えてよいか（gatemarks.stuck_push が引く）
- stuck_keys(doc)・uncited(note, doc)・stuck_faces(doc): 止まった壁打ちの止めた block の key（stuck_reason も同じ式）・止まった時の
  推しの note が引いていない key と『項目 n』・保留の項目の前の往復の block を review.json の faces に足す行（印 HELD_MARK つき。
  block_faces は審査の挙げた block に数えない）
- carried_refs(b, opened): 今の往復が見ない項目が前の往復の答えの対応表（DESIGN_MAP）で受けた独立設計の要素の id（往復の行の items の refs。
  要素の網羅は全部の項目の答えを合わせて数える）
- item_blocks(b, n): 項目 n が答える前の往復の答えの要る穴の key（求める側。受け付けが下請けの答えの resolved か同じ key の face を求める）
- resolvable_keys(doc, n=None)・stray_resolved(doc, resolved, n=None): resolved に書いてよい key の集合（どの往復かの block と suggest の
  key。n で項目 n の範囲に絞る）の唯一の持ち主と、それに無い key の拒否の行（resolved_gaps と下請けの答えの受け付けが引く）
- prev_row(b, n)・answered_hits(b, n)・carried_notes(b): 前の往復のその項目の案の行・当たりの答えと、suggest の穴（往復の行の
  notes。項目を開き直さず、受け付けが後の往復の返答に今の案の単位だけで引き継ぎ、修正の段へ運ぶ。答えと照らしが要る suggest は
  owed_faces が引く開いた項目の物だけで、閉じた・保留の項目の物と審査が消えたと言った物は参考として渡る）
- revise_section(doc)・review_section(b)・stuck_reason(b)・lines(b): 指示書に足す文（review_section は、最後の往復に保留の項目が
  在れば HELD_CITES と保留の項目ごとの block の key も貼る）・関所の理由・報告の行（往復ごとの行は
  前の往復の block を審査が suggest に下げた key も名指し、disputed と答えた穴の key と根拠を 1 行ずつ後ろに足す）

役の型に欄を足す・返答から外す手順は住処 marks（種 converge）に任せる。外した欄は足し欄の控えでなく、この往復の控えに置く。
盤面の b のうち round・dir・work・trace だけを使い、標準ライブラリと住処 marks（L1）だけを import する（gatemarks がこのモジュールを
読み、entry が gatemarks を読むので、entry・rolekit・gatemarks を import すると輪になる）。
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil

import marks
import promptsection

RECORD = "plan-converge.json"
PASS_DIR = "plan-converge"
OP = "plan_converge"
DROPPED_OP = "plan_converge_dropped"
CLEAN = "clean"   # 抜け方の語（控えの outcome）
AGAIN = "again"
PERSISTED = "persisted"
UNSETTLED = "unsettled"
STUCK = (PERSISTED, UNSETTLED)
OPEN = "open"   # 項目の state（往復の行の items[].state）
CLOSED = "closed"
HELD = "held"
ANSWERS = "block_answers"
RESOLVED = "resolved"
HANDLED = ("fixed", "disputed")
FACE_KEYS = ("key", "kind", "where", "why")

REVISE_ASK = ("事前審査（別の目）が、修正案に下の block（直しへ進めない穴）を挙げた。block ごとに、案を直したなら handled に fixed、"
              "how に直した所を、直さずに異を唱えるなら handled に disputed、how に根拠を、block_answers に 1 行ずつ書け（key は下の key を"
              "一字も変えずに写す）。そのうえで変えた項目の行だけを plan に返せ（前の案と同じ型の行。閉じた項目は書くな。変えない開いた項目と"
              "保留の項目も書かなくてよく、機械が前の往復の行を差し込む。fixed と答えた block の項目は変えた行を返せ）。下の答えの要る suggest（開いた項目に付いた物）にも、block と同じく key ごとに"
              " block_answers に 1 行書け。suggest は止め時には数えない。直した案は新しい会話の事前審査に掛かり、"
              "同じ block が残るか、開いた block の数が前の往復より減らなければ直しへ進まずに承認ノードで止まる。")
REREVIEW_ASK = ("下は前の往復で挙がった block と答えの要る suggest と、修正案の役の答え（fixed＝直した・disputed＝異を唱えた）。今の案を読み、"
                "前の block と答えの要る suggest の key ごとに、穴が消えたなら resolved にその key を入れ、残っていれば同じ key のまま faces に"
                "挙げ直せ（block の見出しの物は severity block、答えの要る suggest の見出しの物は severity suggest のままで、block に上げない。"
                "同じ穴に別の key を付けない。key は一字も変えずに写す）。新しい穴は新しい key で挙げよ。前の block が 1 つでも block のまま"
                "残ると、案は直しへ進まず承認ノードで止まる（suggest は止め時に数えない）。")
ORIGIN_ASK = ("今の往復で新しく挙げた block（前のどの往復の block の key とも違う物）が在れば、origins に 1 件ずつ {key, origin} で"
              "出自を書け。origin は missed（前に審査した案の行に既に在ったのに、前の審査が見落とした穴）・introduced（直しが"
              "持ち込んだ穴）・rephrased（前の block の言い換え。of に言い換えた前の block の key を書き、その key は resolved に"
              "入れる）のどれか。分けられない時と、前の block を挙げ直すだけの時は書かない。")
PERSISTED_WHY = ("事前審査（記録の名 p2.plan_review）の同じ block が、案を直した後も残った（{keys}。壁打ち {n} 往復。"
                 "往復ごとの案と審査: {path}）")
UNSETTLED_WHY = ("事前審査（記録の名 p2.plan_review）の block が、壁打ち {n} 往復でも消えない（往復ごとに別の穴が出た。"
                 "最後の block: {keys}。往復ごとの案と審査: {path}）")
COUNTS_WHY = "開いた block の数: {counts}（前の往復より減らなかった）"
CAP_WHY = ("壁打ちのループの安全の上限 {n} 往復に届いた（減り続ける往復は普通は届かないので、仕組みの異常として止めた）。"
           "開いた block は減り続けていた（往復ごとの開いた数: {counts}）")
LINE_HEAD = ("事前審査の壁打ち: {n} 往復・抜け方は{word}（記録の名 {outcome}）・続いた block: {persists}・{share}"
             "（往復ごとの案と審査: {path}）")
# 1 回目の割合の分母に言い換えを入れないのは、言い換えが 1 回目の block の言い直しで新しい穴でないから。持ち込みを 1 回目の割合の
# 分母に入れないのは、直しが後で作った穴が 1 回目の見つける力を下げて見せるから（止めた全部のうちの割合には入れる）
LINE_SHARE = ("1 回目の block {first} 件・後の回の新しい block: 見落とし {missed}・持ち込み {introduced}・言い換え {rephrased}・"
              "分けられない {unsplit}。1 回目に出た割合は {share}（後の回が審査した所の見落としだけを数えるので、閉じた項目の取りこぼしは"
              "数えない上限。run の後で見つかった穴は割合に入らない）、止めた全部のうちでは {total}")
LINE_NO_BLOCK = "止めた block なし"
LINE_PASS = ("  - {k} 往復目: block {keys}・答えの要る穴（block と suggest）への答え fixed {f} 件・disputed {d} 件・審査が消えたと言った key {resolved}"
             "・審査が suggest に下げた key {down}")
CLOSED_ASK = "下の項目は前の往復で事前審査が block を挙げずに閉じた。plan に書くな（機械が前の往復の行のまま差し込む）:"
NOTES_HEAD = ("参考: 答えの要らない suggest の穴（閉じた・保留の項目に付いた物と、審査が消えたと言った物。答えなくてよく、採っても"
              "採らなくてもよい。項目を開き直さない。修正の段にも事前審査の返答として渡る）:")
HELD_NOTE = "下の項目は同じ block が続いたので保留にした（直さなくてよい。書かなければ機械が差し込む。承認ノードが読む）:"
ITEMS_WHY = "固まった項目: {closed}。保留の項目: {held}。開いたままの項目: {open}"
LINE_DISPUTED = "    退けた答え {key}: {how}"
LINE_ITEMS = "    項目: 閉じた {closed}・開いた {open}・保留 {held}・相乗りの審査の block {synergy}"
WORDS = {CLEAN: "block が消えた", PERSISTED: "同じ block が続いた", UNSETTLED: "開いた block が残ったまま止めた", AGAIN: "途中"}
NONE = "無い"

ANSWER_SCHEMA = {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["key", "handled", "how"],
    "properties": {"key": {"type": "string", "minLength": 8}, "handled": {"type": "string", "enum": list(HANDLED)},
                   "how": {"type": "string", "minLength": 10}}}}
RESOLVED_SCHEMA = {"type": "array", "items": {"type": "string"}}
FIELDS = {"plan-revise": (ANSWERS, ANSWER_SCHEMA, True), "plan-review": (RESOLVED, RESOLVED_SCHEMA, False)}
# 事前審査の束ね役の欄（線の木の段 1。役の型にだけ在り、盤面へ渡す前に外す。写しの graph は変えない）。束ね役は項目ごとの判定の
# 要約（ITEMS）だけを返し、当たりの答え・faces・相乗りは下請けが答えのファイルに書いて受け付け（機械）がまとめる（run 68f35d6b:
# 束ね役が当たりの答え 141〜197 行を返答に写して 1 往復に 119〜194 秒を使い、短く写した理由で型に拒まれて書き直した）
ITEMS = "items"
SYNERGY = "synergy"
VERDICTS = ("clean", "block")
ITEMS_SCHEMA = {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["item", "verdict", "blocks"],
    "properties": {"item": {"type": "integer", "minimum": 1}, "verdict": {"type": "string", "enum": list(VERDICTS)},
                   "blocks": {"type": "array", "items": {
                       "type": "object", "additionalProperties": False, "required": ["key", "why"],
                       "properties": {"key": {"type": "string"}, "why": {"type": "string"}}}}}}}
# 下請けの答えのファイルの当たりの答えの欄（受け付けが項目ごとに確かめる。理由は 10 字以上）
HIT_ANSWERS = ("covered", "no_effect", "block")
HITS_SCHEMA = {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["id", "answer", "why"],
    "properties": {"id": {"type": "string", "minLength": 2}, "answer": {"type": "string", "enum": list(HIT_ANSWERS)},
                   "why": {"type": "string", "minLength": 10}}}}
# 独立設計と案の仕組みの対応表（独立設計が立つ run の項目の答えが書く）。行は 2 つの向き。案→設計: 案の files の (項目, path, symbol)
# ごとにちょうど 1 行（change=add の symbol・change=remove の symbol・op が create・delete・rename の行（symbol は null））で、design_ref は
# 指す要素の id（対が無ければ null）。設計→案: item・path・symbol が null で design_ref が必須（案に対の無い要素）。design_quote は
# 独立設計の字のままの引用か、対が無ければ null。照らしは core の design.quote_gaps。事前審査の役の型にだけ在り、盤面へ渡す前に外す
DESIGN_MAP = "design_map"
DESIGN_MAP_SCHEMA = {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["item", "path", "symbol", "design_ref", "design_quote", "why"],
    "properties": {"item": {"type": ["integer", "null"], "minimum": 1}, "path": {"type": ["string", "null"]},
                   "symbol": {"type": ["string", "null"]}, "design_ref": {"type": ["string", "null"], "pattern": "^D[0-9]+$"},
                   "design_quote": {"type": ["string", "null"]}, "why": {"type": "string", "minLength": 10}}}}
# 新しい block の出自（2 往復目から。審査の申告で、機械が控えの事実で照らして採る）。of は rephrased の時の言い換えた前の key
ORIGINS = "origins"
ORIGIN_MISSED = "missed"   # 出自の語（往復の行の origins の値）
ORIGIN_INTRODUCED = "introduced"
ORIGIN_REPHRASED = "rephrased"
ORIGIN_UNSPLIT = "unsplit"
ORIGIN_WORDS = (ORIGIN_MISSED, ORIGIN_INTRODUCED, ORIGIN_REPHRASED, ORIGIN_UNSPLIT)
CLAIMED = (ORIGIN_MISSED, ORIGIN_INTRODUCED, ORIGIN_REPHRASED)   # 審査が申告してよい語
ORIGIN_SCHEMA = {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["key", "origin"],
    "properties": {"key": {"type": "string"}, "origin": {"type": "string", "enum": list(CLAIMED)},
                   "of": {"type": "string"}}}}
# 壁打ちが止まる往復の推し（事前審査の返答の一番上の欄。形は gatemarks.MARK_SCHEMA[RECOMMEND] の {answer, note, why}。値を往復の行の
# 欄 push に置くだけで、形の持ち主は gatemarks）。無人の run が、止まった案を推しで修正へ進める口（gatemarks.stuck_push。
# 越えてよいかは pushable）
STUCK_PUSH = "stuck_recommend"
HELD_MARK = "held"
KEY_CHAR = "[A-Za-z0-9_-]"   # key の 1 字（gatemarks の台帳の key の照らしも読む）
HELD_CITES_HEAD = "止まった時の推し（" + STUCK_PUSH + "）の note に引く物"
HELD_CITES = (HELD_CITES_HEAD + ": 下の保留の項目の block（今の往復は審査しない）と、今の往復で挙げる block の key 全部と、"
              "その項目の番号")
TREE_KEYS = (ITEMS, DESIGN_MAP, ORIGINS, SYNERGY, STUCK_PUSH)   # 事前審査の返答から外す木の欄


# ---------------------------------------------------------------- 決まり
def _faces(review) -> list[dict]:
    """審査の返答の face の行（返答が dict でない・faces が list でない・行が dict でない物は読まない）"""
    faces = review.get("faces") if isinstance(review, dict) else None
    return [f for f in faces if isinstance(f, dict)] if isinstance(faces, list) else []


def block_faces(review: dict) -> list[dict]:
    """審査の返答の severity が block の face（key で重複を除き、順を保つ）。機械が足した保留の項目の block（HELD_MARK つき。
    stuck_faces）は審査が挙げた block でないので数えない"""
    out = {}
    for f in _faces(review):
        if f.get("severity") == "block" and f.get("key") not in out and not f.get(HELD_MARK):
            out[f.get("key")] = f
    return list(out.values())


def decide(passes: list[dict]) -> str:
    """往復の止め時の決まりの正本。最後の往復の block が無ければ CLEAN、前のどれかの往復の block と重なれば PERSISTED、
    2 往復目から、開いた block の数が前の往復より減らなければ UNSETTLED、ほかは AGAIN（開いた block が減り続ける限り、往復の
    数では止めない）。最後の行に items が在れば項目ごと（_decide_items）: 開いた項目が無ければ、保留の項目が在れば PERSISTED・
    無ければ CLEAN。開いた項目の block の数が減らなければ、保留の項目が在れば PERSISTED・無ければ UNSETTLED。ほかは AGAIN。
    輪が回せる往復の静的な上限は決まりに入れない（add_pass の at_cap が、AGAIN の往復をその周で止める）。
    止め時が数えるのは block だけ: 開いた項目の suggest（答えは要る。owed_faces）に disputed と答え、審査が suggest のまま挙げ直しても、
    block が無ければ CLEAN（残った suggest は carried_notes が修正の段へ運ぶ）"""
    stop = not_fewer(passes)
    if passes[-1].get("items") is not None:
        return _decide_items(passes, stop)
    last = set(passes[-1]["blocks"])
    if not last:
        return CLEAN
    if any(last & set(p["blocks"]) for p in passes[:-1]):
        return PERSISTED
    return UNSETTLED if stop else AGAIN


def not_fewer(passes: list[dict]) -> bool:
    """2 往復目から、最後の往復の開いた block の数が前の往復より減っていない（decide の止める式。関所の理由の数の句も
    これで読む）"""
    return len(passes) >= 2 and len(_open_blocks(passes[-1])) >= len(_open_blocks(passes[-2]))


def _decide_items(passes: list[dict], stop: bool) -> str:
    states = [it.get("state") for it in passes[-1]["items"]]
    if OPEN not in states:
        return PERSISTED if HELD in states else CLEAN
    if stop:
        return PERSISTED if HELD in states else UNSETTLED
    return AGAIN


def item_id(unit_keys) -> str:
    """項目の見分け（unit_keys の組。並びに依らない）"""
    return " | ".join(sorted(str(k) for k in unit_keys or []))


def item_hash(row: dict) -> str:
    """項目の行（名前に戻した物）の sha256"""
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _label(it: dict) -> str:
    return f"項目 {it['n']}（{'、'.join(str(k) for k in it.get('unit_keys') or [])}）"


def _attributed(units: list, items: list) -> list[int]:
    """face の unit_keys が重なる項目の位置（どの項目とも重ならなければ全部）"""
    hit = [i for i, it in enumerate(items) if set(units) & set(it["unit_keys"])]
    return hit or list(range(len(items)))


def _origins(new: list, claimed: list, *, rows: list, prev: list, face_units: dict, earlier: set, earlier_units: dict,
             resolved: list) -> tuple[dict, list]:
    """（新しい block の key ごとの出自の語, 採らなかった申告の行）。審査の申告は、その block の項目の控えの事実が申告の語の
    条件を満たす時だけ採る（mine＝face の単位が重なる項目。重ならなければ全部の項目）:
    missed は mine の項目の行が前の往復と全部同じ時。introduced は今の往復でどれかの項目の行が変わった時（前の往復に無い項目も
    変わった物に数える。ほかの項目の行が変わって mine の項目に穴ができる、項目どうしの関わりの持ち込みを含む）。rephrased は
    of が前の往復の block で今の往復の resolved に在り、かつ of の前の往復の単位（earlier_units）が今の block の単位と重なる時。
    同じ key に食い違う申告が在れば、どれも採らない。
    採らない申告と申告の無い block は既定に落とす: mine の項目の id が全部前の往復の案に無ければ introduced・mine の項目の
    行が前の往復と全部同じなら missed・ほかは unsplit。項目の控えが前の往復と今の往復の両方に無ければ（mine が空）、どの
    申告も採らずに unsplit"""
    said = {}
    for c in claimed:
        said.setdefault(c["key"], set()).add((c["origin"], c.get("of")))
    conflicted = {key for key, claims in said.items() if len(claims) > 1}
    before = {it["id"]: it["hash"] for it in prev}
    changed = {r["id"] for r in rows if before.get(r["id"]) != r["hash"]}   # 前の往復に無い項目も変わった物に数える
    out = {}
    for key in new:
        mine = [rows[i] for i in _attributed(face_units.get(key) or [], rows)] if rows and prev else []
        if not mine:
            out[key] = ORIGIN_UNSPLIT
            continue
        ids = {r["id"] for r in mine}
        out[key] = (ORIGIN_INTRODUCED if all(i not in before for i in ids)
                    else ORIGIN_MISSED if not ids & changed else ORIGIN_UNSPLIT)
        origin, of = next(iter(said[key])) if key in said and key not in conflicted else (None, None)
        if origin == ORIGIN_INTRODUCED and changed:
            out[key] = ORIGIN_INTRODUCED
        elif (origin == ORIGIN_REPHRASED and of in earlier and of in resolved
              and set(earlier_units.get(of) or []) & set(face_units.get(key) or [])):
            out[key] = ORIGIN_REPHRASED
    return out, [copy.deepcopy(c) for c in claimed if c["key"] in conflicted or out.get(c["key"]) != c["origin"]]


def _item_states(plan: list, faces: list, face_units: dict, prev: list, earlier: set) -> list[dict]:
    before = {it["id"]: it for it in prev}
    rows = [{"n": n, "id": it["id"], "unit_keys": list(it["unit_keys"]), "hash": it["hash"], "state": OPEN, "blocks": [],
             "reopened": False, **({"row": copy.deepcopy(it["row"])} if "row" in it else {})} for n, it in enumerate(plan, 1)]
    for f in faces:
        for i in _attributed(face_units.get(f.get("key")) or [], rows):
            rows[i]["blocks"].append(f.get("key"))
    for r in rows:
        was = (before.get(r["id"]) or {}).get("state")
        if was == HELD:
            r["state"], r["blocks"] = HELD, (before[r["id"]].get("blocks") or [])
        elif not r["blocks"]:
            r["state"] = CLOSED
        elif set(r["blocks"]) & earlier:
            r["state"] = HELD
        r["reopened"] = was == CLOSED and r["state"] != CLOSED
    return rows


# ---------------------------------------------------------------- 控え
def _fresh(b) -> dict:
    return {"round": b.round, "passes": [], "outcome": None, "open": {}}


def read(b) -> dict:
    """今の周の控え。無い・読めない・形が違う・周が違うなら往復の無い控え"""
    try:
        doc = json.loads(b.work(RECORD).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return _fresh(b)
    if (not isinstance(doc, dict) or doc.get("round") != b.round or not isinstance(doc.get("passes"), list)
            or not all(isinstance(p, dict) for p in doc["passes"]) or not isinstance(doc.get("open", {}), dict)):
        return _fresh(b)
    out = {"round": b.round, "passes": doc["passes"], "outcome": doc.get("outcome"), "open": doc.get("open", {})}
    if isinstance(doc.get("plan"), list):
        out["plan"] = doc["plan"]
    return out


def _write(b, doc: dict) -> None:
    path = b.work(RECORD)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def pass_no(b) -> int:
    """次の事前審査の往復の番号"""
    return len(read(b)["passes"]) + 1


def note_answers(b, answers: list) -> None:
    """修正案の役の答えを open に置く（次の record_pass が往復の行へ移す）"""
    doc = read(b)
    doc["open"] = {"answers": copy.deepcopy(answers)}
    _write(b, doc)


def note_plan(b, rows: list) -> None:
    """受けた案の項目（名前に戻した行の並び）を控えの plan に置く（次の record_pass が項目ごとに読む。行そのものも row に置き、
    次の往復の下請けが前の往復からの差分を見る元にする）"""
    doc = read(b)
    doc["plan"] = plan_rows(rows)
    _write(b, doc)


def plan_rows(rows: list) -> list[dict]:
    """控えの plan の行 [{id, unit_keys, hash, row}]（受けた案の項目の行の並びから）"""
    return [{"id": item_id(r.get("unit_keys")), "unit_keys": [str(k) for k in r.get("unit_keys") or []],
             "hash": item_hash(r), "row": copy.deepcopy(r)} for r in rows if isinstance(r, dict)]


def plan_keys(plan) -> list:
    """今の案に在る単位の key を案の順に、重複も残して字のまま（控えの plan の行・修正案の役の出力の plan の行のどちらからも）。
    list でない plan・行で無い物・unit_keys が list でない行は読まない。planned_units と planfile の照らしの下の読み口"""
    return [k for r in plan if isinstance(r, dict) and isinstance(r.get("unit_keys"), list)
            for k in r["unit_keys"]] if isinstance(plan, list) else []


def planned_units(plan) -> set[str]:
    """今の案に在る単位の key の集合（plan_keys の key を plan_rows と同じく str にする）。carried_notes が持ち越す穴の単位と、
    受け付けが案に無い単位を拒む照らしは、この 1 つの集合で揃う"""
    return {str(k) for k in plan_keys(plan)}


def item_units(plan, n: int) -> set[str]:
    """項目 n（1 始まり）の単位の key の集合（planned_units と同じく str）。n が案の項目の番号の外か plan が list でなければ空。
    item_blocks・resolved_gaps・splice と受け付けの照らし・先行例の振り分け・2 度目の修正への申し送り（replan.fix_notes）は、この 1 つの集合で揃う"""
    return planned_units([plan[n - 1]]) if isinstance(plan, list) and 1 <= n <= len(plan) else set()


def _last_items(doc: dict) -> dict:
    return {it["id"]: it for it in (doc["passes"][-1].get("items") or [])} if doc["passes"] else {}


def _unsettled(row) -> bool:
    """往復の行の項目 row（最後の往復に同じ id の行が無ければ None）が、次の事前審査の見る項目か。閉じた・保留にした項目でない物
    （行の無い項目は、案を組み替えた新しい項目なので見る）。open_items と owed_faces はこの 1 つの決まりで開いた項目を引く"""
    return (row or {}).get("state") not in (CLOSED, HELD)


def open_items(b) -> list[int]:
    """次の事前審査が見る項目の番号（今の案の項目のうち、最後の往復で閉じた・保留にした項目でない物。_unsettled）。
    項目の控えが無ければ []"""
    doc = read(b)
    last = _last_items(doc)
    return [n for n, it in enumerate(doc.get("plan") or [], 1) if _unsettled(last.get(it["id"]))]


def carried_refs(b, opened) -> set:
    """今の案の項目のうち opened（今の往復が審査する項目の番号）でない項目が、前の往復の答えの対応表で受けた独立設計の要素の id の集まり
    （項目ごとに、その項目を最後に審査した往復の行の refs。要素の網羅は全部の項目の答えを合わせて数えるので、今の往復が見ない
    項目の物は控えから足す）。控えに項目の行・refs の無い項目は足さない"""
    doc = read(b)
    out = set()
    for n, item in enumerate(doc.get("plan") or [], 1):
        if n in set(opened):
            continue
        for p in reversed(doc["passes"]):
            row = next((x for x in p.get("items") or [] if x.get("id") == item["id"] and isinstance(x.get("refs"), list)), None)
            if row is not None:
                out.update(r for r in row["refs"] if isinstance(r, str))
                break
    return out


def prev_row(b, n: int) -> dict | None:
    """項目 n（今の案の項目の控え）を最後に審査した往復のその項目の行（同じ id。無い・行の控えの無い古い控えなら None）"""
    doc = read(b)
    plan = doc.get("plan") or []
    if not 1 <= n <= len(plan):
        return None
    for p in reversed(doc["passes"]):
        it = next((x for x in p.get("items") or [] if x.get("id") == plan[n - 1]["id"]), None)
        if it is not None and "row" in it:
            return it["row"]
    return None


def answered_hits(b, n: int) -> list:
    """項目 n（同じ id）の前の往復の当たりの答えの行（受け付けが下請けの答えから引いて items の hits に置いた物。新しい往復の順）"""
    doc = read(b)
    plan = doc.get("plan") or []
    if not 1 <= n <= len(plan):
        return []
    return [{**h, "pass": p["pass"]} for p in reversed(doc["passes"]) for x in p.get("items") or []
            if x.get("id") == plan[n - 1]["id"] for h in x.get("hits") or []]


def carried_notes(b) -> list:
    """修正の段へ運ぶ、前の往復の suggest の穴（答えの要る穴かどうかに依らない。答えの要る穴は owed_faces が引く）。
    往復の行の notes（key で 1 つ・新しい物を採る）のうち、どの往復でも block でなかった物。控えに
    今の案の項目（note_plan）が在れば、unit_keys をその key の全往復の写しの単位の和から案に在る物だけにした写しにし、指す単位が
    残らない穴は持ち越さない（受け付けの plan_review_output は案に無い単位を指す face を拒み、機械が足した face は審査役に直せない。
    持ち越して絞った写しも往復の行の notes に残るので、和を取らないと後の案が戻した単位が穴から消えたままになる）。往復の行の notes は変えない"""
    doc = read(b)
    blocks = {k for p in doc["passes"] for k in p.get("blocks", [])}
    out, units = {}, {}
    for p in doc["passes"]:
        for f in p.get("notes") or []:
            if f.get("key") not in blocks:
                out[f.get("key")] = f
                units.setdefault(f.get("key"), {}).update(dict.fromkeys(f.get("unit_keys") or []))
    if "plan" not in doc:
        return list(out.values())
    planned = planned_units(doc["plan"])
    kept = [{**f, "unit_keys": [k for k in units[key] if k in planned]} for key, f in out.items()]
    return [f for f in kept if f["unit_keys"]]


def item_blocks(b, n: int) -> list:
    """項目 n（1 始まり。今の案の項目の控え）が答える前の穴の key＝求める側（owed_faces の行のうち、unit_keys が項目と重なる物と、
    どの項目とも重ならない物。block と、開いた項目の suggest。出た順・重なりは 1 つ）。resolved に書いてよい側は resolvable_keys
    が持つ。控えか往復が無ければ []"""
    doc = read(b)
    in_scope = _item_scope(doc, n)
    if not doc["passes"] or in_scope is None:
        return []
    out = [f["key"] for p in doc["passes"] for f in owed_faces(doc, p) if in_scope(f["unit_keys"])]
    return list(dict.fromkeys(out))


def _item_scope(doc: dict, n: int):
    """項目 n（1 始まり）の範囲の述語 unit_keys -> bool（項目 n の単位と重なる物と、どの項目とも重ならない物。item_blocks と
    resolvable_keys が共有する）。n が今の案の項目の番号の外なら None"""
    plan = doc.get("plan") or []
    if not 1 <= n <= len(plan):
        return None
    mine, every = item_units(plan, n), planned_units(plan)
    return lambda units: _touches(units, mine, every)


def _closed_ids(doc: dict) -> set:
    """今の案の項目のうち、最後の往復で閉じた項目の id"""
    last = _last_items(doc)
    return {it["id"] for it in doc.get("plan") or [] if (last.get(it["id"]) or {}).get("state") == CLOSED}


def filled_units(doc: dict) -> list[str]:
    """返答に無ければ機械が前の往復の行を差し込む項目（控えの案の、行を持つ項目の全部。splice と同じ集合）の単位の key。
    項目の控えが無ければ []"""
    return plan_keys([it for it in doc.get("plan") or [] if "row" in it])


def splice(doc: dict, rows: list, *, fill: bool = True) -> tuple[list, list[str], list[str]]:
    """直しの役が返した行（名前に戻した行の並び）に前の往復の行を差し込んだ案の全体, 拒む行, 捨てた id を返す。
    控えの案の順に、閉じた項目は控えの行、開いた項目と保留の項目は返答の同じ id の行を並べる。控えに当たらない返答の行（単位を
    組み替えた行・新しい項目の行）は返答の順で後ろに足す（捨てない）。fill が真なら、開いた項目と保留の項目の行が返答に無く、
    その単位がどの返答の行にも無ければ控えの行を差し込む（役は変えた項目だけを返す。#571。fixed と答えて変えていない項目は
    fixed_unchanged が名指す）。fill が偽（返答が閉じた項目を除く案の全部）なら差し込まず、返答に無い項目は消える。閉じた項目の
    行が返答に在って控えと同じ hash なら捨て（捨てた id）、違えば拒む。閉じた項目の単位を別の行に入れた返答も拒む"""
    given = [r for r in rows if isinstance(r, dict)]
    by_id = {}
    for r in given:
        by_id.setdefault(item_id(r.get("unit_keys")), r)
    in_rows = {str(k) for r in given for k in r.get("unit_keys") or []}
    closed = _closed_ids(doc)
    whole, rejects, dropped, used = [], [], [], set()
    for n, it in enumerate(doc.get("plan") or [], 1):
        mine = by_id.get(it["id"])
        homeless = not item_units(doc["plan"], n) & in_rows
        if it["id"] in closed:
            if mine is not None:
                used.add(id(mine))
                if item_hash(mine) == it["hash"]:
                    dropped.append(it["id"])
                else:
                    rejects.append(f"閉じた項目 {n} を変えた（書くな。機械が差し込む）")
            elif not homeless:
                rejects.append(f"閉じた項目 {n} の単位を別の行に入れた（書くな。機械が差し込む）")
            if "row" in it:
                whole.append(copy.deepcopy(it["row"]))
        elif mine is not None:
            used.add(id(mine))
            whole.append(mine)
        elif fill and homeless and "row" in it:
            whole.append(copy.deepcopy(it["row"]))
    whole += [r for r in given if id(r) not in used]
    return whole, rejects, dropped


def fixed_unchanged(doc: dict, rows: list, answers) -> list[str]:
    """修正案の役が fixed と答えたのに、その block の項目を変えていない答えの行。block の単位（最後の往復の行の face_units）が
    重なる控えの項目（doc の plan）のどれも、合わせた案 rows（名前に戻した行の並び）で変わっていなければ（同じ id の行が在り、
    その hash が控えと同じ）名指す。同じ id の行が無い項目は単位を組み替えたので変えた物に数える。どの項目とも重ならない block と、
    返す往復の無い控えは見ない"""
    row = held(doc)
    if row is None:
        return []
    now = {item_id(r.get("unit_keys")): item_hash(r) for r in rows if isinstance(r, dict)}
    out = []
    for a in answers if isinstance(answers, list) else []:
        if not isinstance(a, dict) or a.get("handled") != "fixed":
            continue
        units = set((row.get("face_units") or {}).get(a.get("key")) or [])
        mine = [(n, it) for n, it in enumerate(doc.get("plan") or [], 1) if units & set(it["unit_keys"])]
        if mine and all(now.get(it["id"]) == it["hash"] for _, it in mine):
            names = "・".join(str(n) for n, _ in mine)
            out.append(f"block {a.get('key')} を fixed と答えたが、その block の項目 {names} を変えていない（直した行を返すか、"
                       "disputed にせよ）")
    return out


def add_pass(doc: dict, review: dict, *, answers: list, resolved: list, synergy: list | None = None,
             hits: dict | None = None, origins: list | None = None, at_cap: bool = False, refs: dict | None = None,
             push=None) -> dict:
    """控え doc に事前審査の返答 1 つを往復の行として足し、decide で抜け方を決めて doc と行の outcome に置く（ファイルの写し・
    書き込み・trace はしない）。at_cap（呼び手が渡す、輪がもう 1 周回せない事実）が真で decide が AGAIN の往復は、行に
    capped: true を立てて UNSETTLED（保留の項目が在れば PERSISTED）で止める（決まりは decide のまま。CLEAN と止める往復は
    変えない）。origins（審査の出自の申告の行。型は節の output_format か、受け付けが答えのファイルの型（ORIGIN_SCHEMA の写し）で照らし済み）は
    _origins が照らして、2 往復目からの新しい block の出自を行の origins に置く（採らなかった申告は origins_claimed）。refs（{項目の番号:
    その項目の答えの対応表の design_ref の並び}）は審査した項目の items の行に置く（carried_refs が、閉じた項目が受けた要素を後の往復の
    網羅に数える。carried_refs）。push（返答の一番上の止まった時の推し STUCK_PUSH の値。形は照らさず、読む gatemarks が照らす）は、
    在れば行の push に置く。返りは足した行"""
    passes = doc["passes"]
    k = len(passes) + 1
    faces = block_faces(review)
    blocks = [f.get("key") for f in faces]
    earlier = {key for p in passes for key in p.get("blocks", [])}
    suggests = [f.get("key") for f in _faces(review) if f.get("severity") != "block"]
    row = {"pass": k, "blocks": blocks, "faces": [{n: f.get(n, "") for n in FACE_KEYS} for f in faces],
           "suggests": list(dict.fromkeys(suggests)), "answers": answers,
           "notes": list({f.get("key"): copy.deepcopy(f) for f in _faces(review) if f.get("severity") != "block"}.values()),
           "resolved": list(resolved), "persists": [key for key in blocks if key in earlier], "outcome": None,
           "origins": {}, "origins_claimed": [], "files": {}, "rejects": []}
    if push is not None:
        row["push"] = copy.deepcopy(push)
    if doc.get("plan"):
        row["face_units"] = {f.get("key"): [str(k) for k in f.get("unit_keys") or []] for f in faces}
        row["items"] = _item_states(doc["plan"], faces, row["face_units"],
                                    list(_last_items(doc).values()), earlier)
        for it in row["items"]:
            if it["n"] in (hits or {}):
                it["hits"] = copy.deepcopy(hits[it["n"]])
            if it["n"] in (refs or {}):
                it["refs"] = list(refs[it["n"]])
        row["synergy"] = list(synergy or [])
    row["origins"], row["origins_claimed"] = _origins(
        [key for key in blocks if key not in earlier] if passes else [], origins if isinstance(origins, list) else [],
        rows=row.get("items") or [], prev=list(_last_items(doc).values()), face_units=row.get("face_units") or {},
        earlier=earlier, earlier_units={key: units for p in passes for key, units in (p.get("face_units") or {}).items()},
        resolved=list(resolved))
    passes.append(row)
    row["outcome"] = decide(passes)
    if at_cap and row["outcome"] == AGAIN:   # 輪がもう 1 周回せない: 抜けないと輪が尽きて節が落ちるので、ここで止める
        row["capped"] = True
        row["outcome"] = PERSISTED if HELD in [it.get("state") for it in row.get("items") or []] else UNSETTLED
    doc["outcome"] = row["outcome"]
    return row


def record_pass(b, review: dict, *, resolved: list, files: dict, synergy: list | None = None,
                hits: dict | None = None, origins: list | None = None, at_cap: bool = False, refs: dict | None = None,
                push=None) -> dict:
    """事前審査の返答 1 つを往復の行として足し、decide で抜け方を決めて控えを書く（行の組み立てと at_cap・origins は add_pass）。files（{名: パス}）の在るファイルを
    pass-<k>/ に写し、写した先を行に置く。盤面の trace に OP の行を書く。控えに項目（note_plan）が在れば行に items・
    synergy（相乗りの審査が挙げた key）・face_units を置き、hits（{項目の番号: 当たりの答えの行}。受け付けが下請けの答えの
    ファイルから引いた物）を審査した項目の items の行に置く。push（返答の一番上の止まった時の推し）は往復の行の push に置く（add_pass）。trace の行には新しい block の出自の語ごとの数も載る。返りは足した行"""
    doc = read(b)
    row = add_pass(doc, review, answers=doc["open"].get("answers", []), resolved=resolved, synergy=synergy,
                   hits=hits, origins=origins, at_cap=at_cap, refs=refs, push=push)
    k = row["pass"]
    dest = b.work(PASS_DIR) / f"pass-{k}"
    for name, src in files.items():
        if os.path.isfile(src):
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest / name)
            row["files"][name] = str(dest / name)
    doc["open"] = {}
    _write(b, doc)
    extra = {"items": {it["n"]: it["state"] for it in row["items"]}} if "items" in row else {}
    made = list(row["origins"].values())
    b.trace(OP, round=b.round, pass_=k, outcome=row["outcome"], blocks=row["blocks"], persists=row["persists"],
            **{word: made.count(word) for word in ORIGIN_WORDS}, **extra)
    return row


def stash_rejects(b, rows: list) -> None:
    """最後の往復の行の rejects に足す（往復が無ければ何もしない）"""
    doc = read(b)
    if doc["passes"]:
        doc["passes"][-1].setdefault("rejects", []).extend(rows)
        _write(b, doc)


def held(doc: dict) -> dict | None:
    """抜け方が AGAIN（修正案の役に返す）時の最後の往復の行"""
    return doc["passes"][-1] if doc.get("outcome") == AGAIN and doc.get("passes") else None


# ---------------------------------------------------------------- 返答の欄
def _open_blocks(row: dict) -> list:
    """往復の行の block のうち、開いた項目の物（items の無い行は全部）"""
    if row.get("items") is None:
        return list(row["blocks"])
    mine = {k for it in row["items"] if it.get("state") == OPEN for k in it.get("blocks") or []}
    return [k for k in row["blocks"] if k in mine]


def _touches(units, mine: set, every: set) -> bool:
    """穴の unit_keys が mine と重なるか、every のどの key とも重ならない（どの項目の穴かが決まらない穴は全部の項目の物）"""
    got = set(units)
    return bool(got & mine) or not got & every


def _pass_faces(p: dict) -> list[dict]:
    """往復の行 p の穴の行 [{FACE_KEYS, severity, unit_keys}]（絞らない）。p の block（face は p の faces、unit_keys は p の
    face_units）と、p の notes の suggest（block と同じ key は除く）。unit_keys は str。owed_faces と resolvable_keys が引く歩き"""
    units_of = p.get("face_units") or {}
    out = {}
    for f in p.get("faces", []):
        units = [str(k) for k in units_of.get(f.get("key")) or []]
        out[f.get("key")] = {**{n: f.get(n, "") for n in FACE_KEYS}, "severity": "block", "unit_keys": units}
    for f in p.get("notes") or []:
        if f.get("key") not in out:
            out[f.get("key")] = {**{n: f.get(n, "") for n in FACE_KEYS}, "severity": f.get("severity") or "suggest",
                                 "unit_keys": [str(k) for k in f.get("unit_keys") or []]}
    return list(out.values())


def resolvable_keys(doc: dict, n: int | None = None) -> set[str]:
    """審査役が resolved に書いてよい key の集合の唯一の持ち主（resolved_gaps と planblk の item_answer_gaps が stray_resolved を通して
    引く）。doc のどの往復かの穴（_pass_faces）の key の全部で、resolved 済みで持ち越された suggest も含む。n（1 始まり）を渡すと
    item_blocks と同じ _item_scope で、項目 n の単位と重なる穴と、どの項目とも重ならない穴に絞る（n が項目の番号の外なら空）。
    resolved 済みの suggest の言い直しを許す訳: owed_faces はどの往復の resolved に入った suggest も開き直さないので、言い直しは
    状態を変えず、拒めば出し直しを食うだけ。処分の違う申告（resolved と block の face の両方）は、この集合でなく両方の受け付けの
    『両方に在る』の照らしが拒む"""
    passes = doc.get("passes") or []
    if n is None:
        return {f["key"] for p in passes for f in _pass_faces(p)}
    in_scope = _item_scope(doc, n)
    if in_scope is None:
        return set()
    return {f["key"] for p in passes for f in _pass_faces(p) if in_scope(f["unit_keys"])}


def stray_resolved(doc: dict, resolved, n: int | None = None) -> list[str]:
    """resolved の key のうち resolvable_keys(doc, n) に無い物の拒否の行（n を渡すと『項目 n の』と範囲を名指す）"""
    ok = resolvable_keys(doc, n)
    where = "" if n is None else f"項目 {n} の"
    return [f"resolved の {key} は{where}前の往復の block と suggest に無い" for key in resolved if key not in ok]


def owed_faces(doc: dict, p: dict) -> list[dict]:
    """控え doc の往復の行 p について、次の往復で答えと照らしが要る穴の行 [{key, severity, kind, where, why, unit_keys}]
    （答えの要る穴の正本。answer_gaps・resolved_gaps・revise_section・review_section・item_blocks と planblk の下請けのファイルが
    これを引き、block の字と項目の state を自分では持たない）。中身は p の穴（_pass_faces）のうち、block の全部と、doc のどの往復の
    resolved にも入っていない suggest（審査が消えたと言った suggest は持ち越しの写しが後の往復の faces に残っても、答えも照らしも
    開き直さない）。どちらも今の開いた項目で絞る: face の unit_keys が
    今の開いた項目（doc の最後の往復の items のうち _unsettled の項目。open_items と同じ決まり）の unit_keys の和と重なる物か、その往復の項目のどの
    unit_keys とも重ならない物だけ（項目の unit_keys は最後の往復が審査した時の物。案を組み替えた後も、閉じた項目の suggest が
    組み替えで開いた項目の物にならない）。
    閉じた・保留の項目に付いた物は答えの要る穴でなく、参考の suggest として carried_notes が修正の段へ運ぶ。doc に plan が無いか、
    最後の往復に items が無ければ絞らない。止め時は decide"""
    passes = doc.get("passes") or []
    items = passes[-1].get("items") if passes and doc.get("plan") else None
    scoped = items is not None
    mine = planned_units([it for it in items or [] if _unsettled(it)])
    every = planned_units(items)
    resolved = {key for q in passes for key in q.get("resolved", [])}
    return [f for f in _pass_faces(p)
            if (f["severity"] == "block" or f["key"] not in resolved) and (not scoped or _touches(f["unit_keys"], mine, every))]


def answer_gaps(doc: dict, answers) -> list[str]:
    """修正案の役の block_answers の欠けと誤り。返した答えの要る穴（owed_faces。block と、開いた項目の suggest）の key ごとに、
    key が一字違わず、handled が HANDLED のどれかで、how が 10 字以上の行がちょうど 1 つ要る（face_units は block にだけ
    置かれるので、suggest に fixed と答えて変えない答えは fixed_unchanged では照らせず、次の往復の
    審査役の resolved の照らしが拾う）"""
    row = held(doc)
    owed = owed_faces(doc, row) if row else []
    blocks = [f["key"] for f in owed]
    rows = [a for a in answers if isinstance(a, dict)] if isinstance(answers, list) else []
    shaped = isinstance(answers, list) and len(rows) == len(answers)
    gaps = [] if shaped else ["block_answers の行の形が違う（{key, handled, how} の行の配列）"]
    for f in owed:
        key = f["key"]
        mine = [a for a in rows if a.get("key") == key]
        if not mine:
            gaps.append(f"{f['severity']} の key {key} への答えが無い")
            continue
        if len(mine) > 1:
            gaps.append(f"答えの要る穴の key {key} への答えが {len(mine)} 行ある（1 行だけにせよ）")
            continue
        a = mine[0]
        if a.get("handled") not in HANDLED:
            gaps.append(f"{key} の handled は fixed か disputed のどちらか（今は {a.get('handled')!r}）")
        if not isinstance(a.get("how"), str) or len(a["how"]) < 10:
            gaps.append(f"{key} の how が短い（10 字以上で、直した所か異を唱える根拠を書け）")
    gaps += [f"{a.get('key')} は前の往復の答えの要る穴（block と開いた項目の suggest）に無い" for a in rows if a.get("key") not in blocks]
    return gaps


def resolved_gaps(b, faces: list, resolved: list) -> list[str]:
    """事前審査の役の resolved の欠けと誤り。前のどの往復かの答えの要る穴（owed_faces。block と、開いた項目の suggest）の key は、
    resolved か faces のどちらかに要る（1 往復目は前の往復が無いので見ない）。resolved に書いてよい key は resolvable_keys の
    集合（stray_resolved が拒む）"""
    doc = read(b)
    passes = doc["passes"]
    if not passes:
        return []
    wanted = {f["key"]: f["severity"] for p in passes for f in owed_faces(doc, p)}
    face_keys = {f.get("key") for f in faces if isinstance(f, dict)}
    block_keys = {f.get("key") for f in block_faces({"faces": faces})}
    gaps = [f"前の {severity} {key} を resolved に入れるか、同じ key で faces に挙げ直せ"
            for key, severity in wanted.items() if key not in resolved and key not in face_keys]
    gaps += stray_resolved(doc, resolved)
    gaps += [f"{key} が resolved と block の face の両方に在る（消えたか残ったかのどちらか 1 つにせよ）"
             for key in resolved if key in block_keys]
    return gaps


def split(role: str, reply: dict) -> tuple[dict, list]:
    """（壁打ちの欄を外した返答の写し, 外した値（無ければ []））"""
    if role not in FIELDS:
        return copy.deepcopy(reply), []
    out, got = marks.split("converge", role, reply, (FIELDS[role][0],))
    got = got.get(FIELDS[role][0])
    return out, got if isinstance(got, list) else []


def tree_split(reply: dict) -> tuple[dict, dict]:
    """（木の欄 TREE_KEYS（束ね役の欄 ITEMS・SYNERGY と対応表 DESIGN_MAP・出自 ORIGINS と、壁打ちが止まる往復の一番上の推し
    STUCK_PUSH）を外した返答の写し, {欄: 値 | None}）"""
    out, got = marks.split("converge", "plan-review", reply, TREE_KEYS)
    return out, {name: got.get(name) for name in TREE_KEYS}


# ---------------------------------------------------------------- 文
def _keys(keys) -> str:
    return "、".join(keys) if keys else NONE


FACE_HEAD = promptsection.Section("### {key}", source="fn:converge._face_text")
PASS_HEAD = promptsection.Section("## {n} 往復目の block", source="fn:converge.review_section")
OWED_HEAD = promptsection.Section("## {n} 往復目の答えの要る suggest", source="fn:converge.review_section")


def _face_text(f: dict) -> str:
    return "\n".join([FACE_HEAD.format(key=f['key']), *(f"- {n}: {f[n]}" for n in FACE_KEYS[1:])])


def _owed_suggest_text(owed: list, n: int) -> list[str]:
    """答えの要る穴 owed のうち block でない物の節（OWED_HEAD の見出しと face 1 件 1 節。無ければ []）"""
    suggests = [f for f in owed if f["severity"] != "block"]
    return ["\n\n".join([OWED_HEAD.format(n=n), *(_face_text(f) for f in suggests)])] if suggests else []


def revise_section(doc: dict) -> str:
    """修正案の役に返す時の指示書の節（REVISE_ASK と、返した block の face 1 件 1 節と、答えの要る suggest（OWED_HEAD の下。
    開いた項目に付いた物）と、残りの suggest の参考（NOTES_HEAD の下。閉じた・保留の項目に付いた物と、審査が消えたと言った物）と、
    閉じた・保留の項目）。返さない時は空"""
    row = held(doc)
    if row is None:
        return ""
    owed = owed_faces(doc, row)
    parts = [REVISE_ASK, *(_face_text(f) for f in owed if f["severity"] == "block"), *_owed_suggest_text(owed, row["pass"])]
    notes = row.get("notes")
    asked = {f["key"] for f in owed}
    rest = [f for f in notes or [] if f.get("key") not in asked]
    if not notes:
        parts.append(f"suggest の key: {_keys(row['suggests'])}")
    elif rest:
        parts.append("\n\n".join([NOTES_HEAD, *(_face_text(f) for f in rest)]))
    for state, head in ((CLOSED, CLOSED_ASK), (HELD, HELD_NOTE)):
        named = [it for it in row.get("items") or [] if it.get("state") == state]
        if named:
            parts.append("\n".join([head, *(f"- {_label(it)}" for it in named)]))
    return "\n\n".join(parts)


def review_section(b) -> str:
    """2 往復目からの事前審査の指示書の節（REREVIEW_ASK と、前の往復ごとの block の face（PASS_HEAD の下）と答えの要る suggest
    （OWED_HEAD の下。owed_faces の物なので、閉じた項目の suggest と審査が消えたと言った suggest は貼らない）と修正案の役の答え）。
    最後の往復に保留の項目が在れば、最後に HELD_CITES と保留の項目ごとの『- 項目 n（単位）: block の key』の行も貼る（推しを書く役が
    stuck_recommend の note に引く key の集合を知る。束ね役の指示書も同じ節を貼る）。
    1 往復目は空。出自の頼み ORIGIN_ASK は貼らない（出自を書く役は、審査の答えを書く層ごとに違う。貼るのは書き手の居る層）"""
    doc = read(b)
    passes = doc["passes"]
    if not passes:
        return ""
    replies = [p.get("answers", []) for p in passes[1:]] + [doc["open"].get("answers", [])]
    parts = [REREVIEW_ASK]
    for p, answers in zip(passes, replies):
        parts.append(PASS_HEAD.format(n=p['pass']))
        parts += [_face_text(f) for f in p["faces"]] or [NONE]
        parts += _owed_suggest_text(owed_faces(doc, p), p["pass"])
        parts.append("修正案の役の答え:\n" + ("\n".join(f"- {a.get('key')}: {a.get('handled')}（{a.get('how')}）"
                                                      for a in answers) or NONE))
    held = [it for it in passes[-1].get("items") or [] if it.get("state") == HELD]
    if held:
        parts.append("\n".join([HELD_CITES, *(f"- {_label(it)}: {_keys(it.get('blocks') or [])}" for it in held)]))
    return "\n\n".join(parts)


def stuck_keys(doc: dict) -> list:
    """止まった壁打ち（PERSISTED・UNSETTLED）の、止めた block の key（stuck_reason・uncited・stuck_faces が読む 1 つの式）。
    項目の無い控えは PERSISTED なら最後の往復の続いた key・UNSETTLED なら最後の往復の block。項目の在る控えは、保留の項目の
    block（前の往復の物。今の往復は審査しない）と開いた項目の block。止まっていなければ []"""
    if doc["outcome"] not in STUCK:
        return []
    last = doc["passes"][-1]
    keys = last["persists"] if doc["outcome"] == PERSISTED else last["blocks"]
    if last.get("items") is not None:
        keys = list(dict.fromkeys(k for it in last["items"] if it.get("state") in (HELD, OPEN) for k in it["blocks"]))
    return keys


def _stuck_items(doc: dict) -> list:
    """止まった控えの最後の往復の、保留・開いた項目の番号（項目の無い控えは []）"""
    last = doc["passes"][-1] if doc["outcome"] in STUCK else {}
    return [it["n"] for it in last.get("items") or [] if it.get("state") in (HELD, OPEN)]


def uncited(note: str, doc: dict) -> list[str]:
    """止まった時の推し（STUCK_PUSH）の note が字のまま引いていない物の並び: stuck_keys の key（前後に key の字 KEY_CHAR が続かない
    一致。長い key の断片は引用に数えない）と、最後の往復の保留・開いた項目の『項目 n』（後ろに数字が続かない一致。『項目 12』は
    『項目 1』の引用に数えない）。止まっていなければ []。
    修正役に届くのは note だけなので、推しが修正の義務（止まった key と項目）に触れているかをここで照らす"""
    note = str(note or "")
    out = [k for k in stuck_keys(doc) if not re.search(rf"(?<!{KEY_CHAR})" + re.escape(k) + rf"(?!{KEY_CHAR})", note)]
    out += [name for n in _stuck_items(doc) for name in [f"項目 {n}"] if not re.search(re.escape(name) + r"(?!\d)", note)]
    return out


def stuck_faces(doc: dict) -> list[dict]:
    """止まった壁打ちの stuck_keys のうち、最後の往復の faces に無い key（保留の項目の前の往復の block）を、その key を最後に挙げた
    往復の faces と face_units から owed_faces と同じ形 {key, kind, where, why, severity: block, unit_keys} に印 HELD_MARK を足して
    返す（stuck_keys の順。挙げた往復が控えに無い key は返さない）。review.json の faces に足すと、修正役が事前審査の穴に key ごとに
    答える道（fixboard.plan_face_rows）に、保留の項目の block も義務として乗る"""
    keys = stuck_keys(doc)
    if not keys:
        return []
    passes = doc["passes"]
    now = {f.get("key") for f in passes[-1]["faces"]}
    out = []
    for key in keys:
        if key in now:
            continue
        for p in reversed(passes):
            f = next((x for x in p["faces"] if x.get("key") == key), None)
            if f is not None:
                out.append({**{n: f.get(n, "") for n in FACE_KEYS}, "severity": "block",
                            "unit_keys": [str(k) for k in (p.get("face_units") or {}).get(key) or []], HELD_MARK: True})
                break
    return out


def pushable(doc: dict) -> bool:
    """止まった壁打ちを、事前審査の役の推し（STUCK_PUSH）で越えてよいか: 抜け方が止まり（STUCK）で、最後の往復が輪の安全の上限の
    周で止めた物（capped）でない時だけ真。UNSETTLED か PERSISTED かでは絞らない（保留の項目が在る上限の止まりは PERSISTED になる）。
    capped を外す訳: 減り続ける往復はふつう上限に届かないので、上限での止まりは仕組みの異常（CAP_WHY）で、役の推しでなく人が見る物。
    capped を立てるのは add_pass で、止める往復の行だけなので、最後の行を見れば足りる"""
    return doc["outcome"] in STUCK and not doc["passes"][-1].get("capped")


def stuck_reason(b) -> str:
    """止まった壁打ちの関所の理由（PERSISTED・UNSETTLED の時だけ。ほかは空）"""
    doc = read(b)
    if doc["outcome"] not in STUCK:
        return ""
    passes = doc["passes"]
    last = passes[-1]
    text = PERSISTED_WHY if doc["outcome"] == PERSISTED else UNSETTLED_WHY
    keys = stuck_keys(doc)
    why = text.format(keys=_keys(keys), n=len(passes), path=b.work(PASS_DIR))
    why += "。" + _items_text(last["items"]) if last.get("items") is not None else ""
    # 同じ block が続いて止めた PERSISTED は数の比べで止めたのでないから、数の句を付けない
    stopped_open = doc["outcome"] == UNSETTLED or any(it.get("state") == OPEN for it in last.get("items") or [])
    counts = " → ".join(f"{p['pass']} 往復目 {len(_open_blocks(p))}" for p in passes)
    if last.get("capped"):   # 輪の安全の上限の周で止めた往復は減り続けていた: 減らなかったと言わず、上限に届いた異常を言う
        why += "。" + CAP_WHY.format(n=len(passes), counts=counts)
    elif stopped_open and not_fewer(passes):
        why += "。" + COUNTS_WHY.format(counts=counts)
    return why


def _items_text(items: list) -> str:
    def named(state, blocks=False):
        rows = [_label(it) + (f"・最後の block: {_keys(it['blocks'])}" if blocks else "")
                for it in items if it.get("state") == state]
        return "、".join(rows) or NONE
    return ITEMS_WHY.format(closed=named(CLOSED), held=named(HELD, True), open=named(OPEN, True))


def _share_text(passes: list) -> str:
    """頭の行の割合の句: 1 回目の block の数と、後の回の新しい block の出自ごとの数（往復の行の origins だけから数える）。
    1 回目に出た割合の分母は 1 回目・見落とし・分けられない（持ち込みと言い換えは入れない）、止めた全部のうちの割合の分母は
    それに持ち込みを足した数。止めた block が 0 件なら割らない。見落としは後の往復が審査した所の物だけなので、閉じて後の往復が
    見ない項目の取りこぼしは分母に入らず、1 回目に出た割合は実際より高く出うる（上限）。run の後で見つかった穴も割合に入らない"""
    first = len(passes[0].get("blocks", []))
    made = [w for p in passes[1:] for w in (p.get("origins") or {}).values()]
    n = {w: made.count(w) for w in ORIGIN_WORDS}
    seen = first + n[ORIGIN_MISSED] + n[ORIGIN_UNSPLIT]
    total = seen + n[ORIGIN_INTRODUCED]
    if not total:
        return LINE_NO_BLOCK
    return LINE_SHARE.format(first=first, missed=n[ORIGIN_MISSED], introduced=n[ORIGIN_INTRODUCED],
                             rephrased=n[ORIGIN_REPHRASED], unsplit=n[ORIGIN_UNSPLIT],
                             share=f"{first}/{seen}" if seen else NONE, total=f"{first}/{total}")


def lines(b) -> list[str]:
    """報告の行（往復が無ければ []。在れば頭の 1 行と往復ごとの 1 行）"""
    doc = read(b)
    passes = doc["passes"]
    if not passes:
        return []
    persists = list(dict.fromkeys(key for p in passes for key in p.get("persists", [])))
    out = [LINE_HEAD.format(n=len(passes), word=WORDS.get(doc["outcome"], doc["outcome"]), outcome=doc["outcome"],
                            persists=_keys(persists), share=_share_text(passes), path=b.work(PASS_DIR))]
    earlier = set()
    for p in passes:
        handled = [a.get("handled") for a in p.get("answers", []) if isinstance(a, dict)]
        down = [key for key in p.get("suggests", []) if key in earlier]   # 前の往復の block を suggest に下げた key
        out.append(LINE_PASS.format(k=p["pass"], keys=_keys(p["blocks"]), f=handled.count("fixed"),
                                    d=handled.count("disputed"), resolved=_keys(p.get("resolved", [])), down=_keys(down)))
        out += [LINE_DISPUTED.format(key=a.get("key"), how=a.get("how")) for a in p.get("answers", [])
                if isinstance(a, dict) and a.get("handled") == "disputed"]   # 退けた理由は、人が後から読めるよう報告に残す
        if p.get("items") is not None:
            count = {st: [str(it["n"]) for it in p["items"] if it.get("state") == st] for st in (CLOSED, OPEN, HELD)}
            out.append(LINE_ITEMS.format(closed=_keys(count[CLOSED]), open=_keys(count[OPEN]), held=_keys(count[HELD]),
                                         synergy=_keys(p.get("synergy") or [])))
        earlier.update(p.get("blocks", []))
    return out
