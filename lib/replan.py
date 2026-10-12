"""同じ run の中の案の直し（依頼 226）。裁定 fix_plan_item の単位は次の run へ持ち越さず、同じ run の中で案に戻す。

案の直しの役（計画のブロックを ruling の入力つきで 2 度目に差し込んだ口）が読む文と、項目の形の小道具だけを置く:
- TRIP_FILE・TRIP_KEYS: 案の直しの控えの名と、その行の欄（item・units・rows（待つ行の id）・old（承認済みの項目）・brief・
  new（関所の決め手の欄を外した直した項目）・new_marks（外した欄）・review・contract_changed・human_faces・widened・ask・
  answer・result・why）。まだ無い値は null
- 修正案の役には誤りと裁かれた項目・申し出・裁定の文だけを渡し（REPLAN_ASK）、返答は渡した項目に限る（数・unit_keys の字・
  works の欄・狭めない案の誤りを全部並べて 1 回で拒む。REPLAN_REJECT）。項目ごとの節の見出しは ITEM_HEAD・OLD_HEAD・ROW_HEAD
- new_item(row): 控えの行の直した項目に、外した決め手の欄を narrows の行ごとに戻した形
- _bare(item): 項目から関所の決め手の欄を外した写し（約束の欄の比べに使う）
- _json_block(doc)・_malformed(reply): 項目を指示書に貼る JSON の段と、修正案の返答の形の崩れ
- WIDEN_OP・WIDEN_LINE・WIDEN_PARTS・widen_text(widened)・AMEND_HEAD・amend_lines(items, …): 無人の run で聞かずに通した範囲を
  広げるだけの直しの文と、同じ run の中で直した項目ごとの 1 行とその見出し（線の ask-replan・ask-final と報告が読む）
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys

sys.dont_write_bytecode = True

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import gatemarks  # noqa: E402
import planmarks  # noqa: E402
import promptsection  # noqa: E402

TRIP_FILE = "replan.json"
TRIP_KEYS = ("item", "units", "rows", "old", "brief", "new", "new_marks", "review", "contract_changed", "human_faces", "widened",
             "ask", "answer", "result", "why")
REPLAN_ASK = ("承認済みの修正案の項目のうち、下に貼った項目だけを直せ。修正の段で修正役がこの項目の誤りを申し出て、裁定役が"
              "fix_plan_item（案の項目そのものの誤り）と裁いた。申し出の文と裁定の文を読み、裁定の文が名指した所を直した項目を"
              "返せ。plan は下に貼った項目と同じ数・同じ順で、各項目の unit_keys は貼った文字列を一字も変えずに写せ（番号で書かない）。"
              "ほかの項目は返すな。直した項目は事前審査に掛かり、約束の欄（unit_keys・narrows・removes・allowed_paths・out_of_scope・"
              "rewrite_tests・tests の behavior）を変えた時は人の関所に出る。")
REPLAN_REJECT = "直した項目の返答に誤りが在る（下の行を全部直して出し直せ）:"
ITEM_HEAD = promptsection.Section("## 直す項目 {n}（承認済みの修正案の項目の番号）", source="fn:replan._section")
OLD_HEAD = promptsection.Section("### 前の項目（承認済み。機械が貼った）", source="fn:replan._section")
ROW_HEAD = promptsection.Section("### 修正の段の申し出と裁定（{id}）", source="fn:replan._section")
# 無人の run で範囲を広げるだけの直しを聞かずに通した項目の文（元 replan.py:152-154。案の直しの関所の節と報告が同じ字を読む）
WIDEN_OP = "replan_widened_unattended"
WIDEN_LINE = "直した——無人の run なので人に聞かずに範囲を広げた（{what}）"
WIDEN_PARTS = {"allowed_paths": "allowed_paths に足した", "out_of_scope": "out_of_scope から外した"}
AMEND_HEAD = "同じ run の中で直した修正案の項目"   # 報告と最後の関所の文の見出し（元 replan.AMEND_HEAD）
APPROVED = "直した——人が承認した"                  # 元 replan.lines の項目ごとの結末の語
PASSED = "直した——聞かずに通した（手段の欄だけ）"
STOPPED_WHY = "人が関所 gate-replan で run を止めた: {text}"   # 元 replan.STOPPED_WHY（関所の名は線の節の id）
NOT_RUN_WHY = "2 度目の修正が走らなかった（直した案ができなかったか、案の直しの関所が開かずに止めた）"
NO_NOTE = "（一言なし）"                          # 元 replan.NO_NOTE
GATE_STOPS = ("stop", "reject")                   # 案の直しの関所の止める語（元 replan.DECISIONS の stop に当たる語）
PENDING_WHY = "未完了（前の run が途中で落ちて、案の直しを終えていない）"   # 元 replan.PENDING_WHY（途中で落ちた run の待つ行）


def amend_lines(items, *, refixed: bool, answer=None, widened=(), whys=None, pending: bool = False) -> list[str]:
    """同じ run の中で直した修正案の項目ごとの 1 行（元 replan.lines :767）。items は直した計画の項目の id（fix の replan_items）、
    refixed は 2 度目の修正が走ったか、answer は案の直しの関所の答え {decision, text, asked}（asked の「項目 <id>:」の行が聞いた項目）、
    widened は無人の run で聞かずに通した範囲を広げるだけの直しの行（「項目 <id>: <WIDEN_LINE>」）、whys は {項目の id: 申し出の行の
    諦めた訳 replan_why}、pending は途中で落ちた run（2 度目の修正が走らなかった項目を未完了と言う）"""
    answer = answer if isinstance(answer, dict) else {}
    asked = [a for a in answer.get("asked") or [] if isinstance(a, str)]
    wide = {}
    for row in widened or ():
        head, sep, text = str(row).partition(":")
        if sep:
            wide[head.removeprefix("項目").strip()] = text.strip()
    stop = (STOPPED_WHY.format(text=" ".join(str(answer.get("text") or "").split()) or NO_NOTE)
            if answer.get("decision") in GATE_STOPS else "")
    out = []
    for item in items or ():
        ident = str(item)
        if refixed:
            how = wide.get(ident) or (APPROVED if answer and any(a.startswith(f"項目 {ident}:") for a in asked) else PASSED)
        elif pending:
            how = PENDING_WHY
        else:
            how = f"直さずに諦めた: {(whys or {}).get(ident) or stop or NOT_RUN_WHY}"
        out.append(f"案の項目 {ident}: {how}")
    return out


def widen_text(widened: dict) -> str:
    """範囲を広げるだけの直しを無人の run で聞かずに通した項目の文（元 replan._widen_text :761。足した glob・外した glob を並べる）"""
    parts = [f"{WIDEN_PARTS[k]}: {', '.join(str(g) for g in widened.get(k) or [])}" for k in WIDEN_PARTS if widened.get(k)]
    return WIDEN_LINE.format(what="／".join(parts))


def new_item(row: dict) -> dict:
    """TRIP_FILE の行の直した項目（new）に、外した決め手の欄（new_marks）を narrows の行ごとに戻した形"""
    out = copy.deepcopy(row.get("new") or {})
    for narrow, marks in zip(out.get("narrows") or [], row.get("new_marks") or []):
        if isinstance(narrow, dict) and isinstance(marks, dict):
            narrow.update(copy.deepcopy(marks))
    return out


def _json_block(doc) -> list:
    return ["```json", json.dumps(doc, ensure_ascii=False, indent=1), "```"]


def _malformed(reply) -> bool:
    """修正案の返答の形が崩れているか（plan が list でない・行が dict でない・narrows が list でない）。崩れていれば欄の検査を
    飛ばす"""
    plan = reply.get("plan") if isinstance(reply, dict) else None
    if not isinstance(plan, list):
        return True
    return any(not isinstance(p, dict) or not isinstance(p.get("narrows") or [], list) for p in plan)


def _bare(item: dict) -> dict:
    """項目から関所の決め手の欄（narrows の行の decided_by・no_narrow など）を外した写し"""
    return gatemarks.split(planmarks.NODE, {"plan": [copy.deepcopy(item)]})[0]["plan"][0]
