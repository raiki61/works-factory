# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""独立の目から修正の段へ返す輪の周の頭 back-k（docs/design/line.md の 1.3・5.4。決めは src/eyesback.py の turn）。

毎周走る（前の周の頭が返さなかった周は前の記録をそのまま運ぶ）。直前の目の判定の route が fix で、返す項目（findings）があれば、go を真にして修正の段への入力（only_items・notes・prior・案の欄）を返す。
返す時は今の作業ツリーの木（snap に渡す eyesback.tree_now）を新しい周の行に控える。
抜ける時は go を偽にして抜けた訳 exit を返し、最後に試験と独立の目を通った状態を持ち越す（返した段が止まった・落ちた周は、返す前のその状態と
戻す先の checkpoint を持ち越して封じる）。落ちない: 読めない・決められない時は輪の節が落ちたとして抜ける（状態を持たず封じず、
最後の承認ノードが開ける理由にする）。

入力（with:）: round（周の番号）・prev（前の周の頭の出力。1 周目は null）・fixed（直前の修正の段の合わせ）・judged・fix_in
（line の node の返り）・tests・eyes（直前の最後の試験と独立の目の返り）・replan・answer_replan（案の直しの返りと答えの node の
出力。1 周目だけ読み、ほかは null）。include の返りは直に結び（落ちた後にも走る one_success の読み手なので、結ぶ返す節は落ちない形に縛る。
docs/design/line.md の 13.1）、口 ports.picked で欄を名指して読む。
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

TESTS = ("mode", "ok", "green", "red_cause", "ran_steps", "baseline", "fingerprint", "test_outcomes", "evidence", "by", "suites_line", "log",
         "baseline_line", "reason", "suite", "suite_note", "related", "report")
EYES = ("ok", "r1", "r2", "r3", "r4", "questions", "means_questions", "passes", "premise_check", "notes", "after", "dirty", "escalate",
        "after_ok", "findings", "route", "route_why", "report", "sections")
REPLAN = ("fix_plan",)
ANSWER_REPLAN = ("plan_review", "fix_answers", "fix_ripple", "skip_rerun")
EXIT_FELL = "返す周のノードが落ちた（周の頭が前の周の出力か、案の直しの出力を読めなかった）"   # src/eyesback.py の EXITS["fell"] と同じ字（試験が突き合わせる）


def dicted(got):
    return None if got is None else dict(got)


def plan_fields(fixed):
    """合わせの出力の plan（修正案の欄の控え）の欄の並び。読めなければ None（返す項目を修正案の項目に結べない）"""
    pointer = fixed.get("plan") if isinstance(fixed, dict) else None
    if pointer is None:
        return None
    try:
        doc = ports.json(json.dumps(pointer), "shared:plan-fields.schema.json")
    except ValueError:
        return None
    return doc.get("fields") if isinstance(doc, dict) else None


def compute():
    from src import eyesback
    raw = {"round": os.environ.get("INPUTS_ROUND"), "prev": os.environ.get("INPUTS_PREV"),
           "fixed": os.environ.get("INPUTS_FIXED"), "judged": os.environ.get("INPUTS_JUDGED"), "fix_in": os.environ.get("INPUTS_FIX_IN"),
           "answer_replan": os.environ.get("INPUTS_ANSWER_REPLAN")}
    fixed = ports.parsed(raw["fixed"])
    return eyesback.turn(
        k=int(ports.text(raw["round"])), prev=ports.parsed(raw["prev"]), fixed=fixed,
        judged=ports.parsed(raw["judged"]), fix_in=ports.parsed(raw["fix_in"]), tests=dicted(ports.picked(os.environ.get("INPUTS_TESTS"), TESTS)),
        eyes=dicted(ports.picked(os.environ.get("INPUTS_EYES"), EYES)), replan=dicted(ports.picked(os.environ.get("INPUTS_REPLAN"), REPLAN)),
        answer_replan=dicted(ports.picked(raw["answer_replan"], ANSWER_REPLAN)),
        plan_fields=plan_fields(fixed), snap=lambda: eyesback.tree_now(Path.cwd()))


def fallen(reason: str) -> dict:
    return {"go": False, "round": 0, "only_items": [], "notes": "", "prior": None, "plan": None, "fix_plan": None, "ripple": None,
            "plan_review": None, "answers": None, "skip_rerun": [], "more": [], "rows": [], "exit": EXIT_FELL, "left": [], "fixed": None,
            "tests": None, "eyes": None, "fingerprint": None, "green_ok": False, "eyes_ok": False, "sealable": False, "item_claims": None,
            "item_kinds": [], "checkpoint": None}


ports.run(compute, fallen)
