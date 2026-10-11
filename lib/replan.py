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

TRIP_FILE = "replan.json"          # 今の周の作業ファイル {"round": n, "items": [行], "answered"?: answer の返り}
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
