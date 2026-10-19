"""plan の block の place のファイルの名と、標準ライブラリだけの落ちない道（docs/design/plan.md の 1.4・4 節）。名はこのモジュールだけが持つ。

place の直下: current-round.json（{round}）・plan-writer-prompt-<n>.md・plan-writer-fix-prompt-<n>.md（prompt.emit）・libdocs/ と libdocs.json。
周のフォルダ r<k>/（k は round）の中: intake.json・round.json・slots.json・judgment.json・prior-*.json・prior-failures-in.json・
ripple-units.json・tree.json・rejects-plan.json・candidate-plan.json・reply.json・p2.fix_plan.json・plan-fields.json・handoff.json・replan.json・
replan-gave-up.json・item-brief-<no>.md・ripple.json・trace.jsonl・prompt-error.json・finish-error.txt。

このモジュールは標準ライブラリと ports だけを import する（lib/ の import が落ちても、intake と finish の fallback が周の事実を残せるように）。
"""
from __future__ import annotations

import json
import os
import pathlib

import ports

ROLE = "plan"                       # 受け付けの拒否の控えの名（rolekit.rejects_path）
CURRENT_ROUND = "current-round.json"
INTAKE = "intake.json"
ROUND = "round.json"
SLOTS = "slots.json"
JUDGMENT_COPY = "judgment.json"
PRIOR_COPIES = {"reply": "prior-reply.json", "fields": "prior-fields.json", "fix_plan": "prior-fix-plan.json",
                "ripple": "prior-ripple.json", "review": "prior-review.json"}
PRIOR_FAILURES_IN = "prior-failures-in.json"   # lib/carry.py の PRIOR_IN_FILE（試験が突き合わせる）
RIPPLE_UNITS = "ripple-units.json"
TREE = "tree.json"
REJECTS = f"rejects-{ROLE}.json"               # lib/rolekit.py の rejects_path が組む名（試験が突き合わせる）
CANDIDATE = f"candidate-{ROLE}.json"           # lib/rolekit.py の candidate_path が組む名（同上）
REPLY = "reply.json"
FIX_PLAN = "p2.fix_plan.json"
FIELDS = "plan-fields.json"                    # lib/planmarks.py の FIELDS_FILE（同上）
HANDOFF = "handoff.json"                       # lib/handoff.py の path_of が組む名（同上）
REPLAN = "replan.json"                         # lib/replan.py の TRIP_FILE（同上）
REPLAN_GAVE_UP = "replan-gave-up.json"
ITEM_BRIEF = "item-brief-{no}.md"
RIPPLE = "ripple.json"
TRACE = "trace.jsonl"                          # lib/planmarks.py の TRACE_FILE（同上）
PROMPT_ERROR = "prompt-error.json"
FINISH_ERROR = "finish-error.txt"
NO_PLAN = "受け付けを通った修正案が無い（修正案のループが回らなかったか、途中で落ちた）"

# 周を開き直した時に名で消すファイル（広い形で消さない。place の直下の指示の記録と、ほかの周のフォルダは消さない）
OWN_FILES = (INTAKE, ROUND, SLOTS, JUDGMENT_COPY, *PRIOR_COPIES.values(), PRIOR_FAILURES_IN, RIPPLE_UNITS, TREE, REJECTS, CANDIDATE, REPLY,
             FIX_PLAN, FIELDS, HANDOFF, REPLAN, REPLAN_GAVE_UP, RIPPLE, TRACE, PROMPT_ERROR, FINISH_ERROR)


def read_json(path, default=None):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return default


def write_json(path, doc) -> pathlib.Path:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def round_dir(place, k: int) -> pathlib.Path:
    return pathlib.Path(place) / f"r{k}"


def current_round(place) -> int:
    """今の周の番号（current-round.json。無い・読めなければ 1）"""
    got = read_json(pathlib.Path(place) / CURRENT_ROUND)
    k = got.get("round") if isinstance(got, dict) else None
    return k if isinstance(k, int) and not isinstance(k, bool) and k >= 1 else 1


def current_dir(place) -> pathlib.Path:
    return round_dir(place, current_round(place))


def read_round(d) -> dict:
    """周のフォルダの round.json（無い・読めなければ、フォルダの名の番号と形 plan・役を起こさない形）"""
    d = pathlib.Path(d)
    got = read_json(d / ROUND, {})
    base = {"round": int(d.name[1:]) if d.name[:1] == "r" and d.name[1:].isdigit() else 1, "mode": "plan", "go": False, "why": "", "items": []}
    doc = {**base, **got} if isinstance(got, dict) else base
    if doc["mode"] not in ("plan", "replan"):
        doc["mode"] = "plan"
    if not isinstance(doc["items"], list):
        doc["items"] = []
    return doc


def highest_round(place) -> int:
    """place に在る周のフォルダ r<n> の一番大きい n（無ければ 0）"""
    nums = [int(p.name[1:]) for p in pathlib.Path(place).glob("r*") if p.is_dir() and p.name[1:].isdigit()]
    return max(nums, default=0)


def next_round(place, raw_prior) -> int:
    """この周の番号。port prior が読めれば prior.round + 1、空なら 1。空でないのに読めない時は、在る周のフォルダの一番大きい番号 + 1
    （前の周のフォルダを開き直して、pointer の先のファイルを消さない）。標準ライブラリと ports だけ（intake の fallback も同じ式で番号を決める）"""
    text = ports.text(raw_prior)
    if not text.strip():
        return 1
    try:
        return int(ports.json(text)["round"]) + 1
    except (ValueError, KeyError, TypeError, OSError):
        return highest_round(place) + 1


def crash_round(place, why: str, k: int) -> dict:
    """周を開く途中で落ちた時の返り。標準ライブラリだけで、周 k のフォルダに go 偽・訳つきの round.json と current-round.json を置く
    （周のフォルダが無ければ作る。k は next_round が決めた番号で、前の周の番号を使い回さない）。error 真の印は出口が failed と読む"""
    place = pathlib.Path(place)
    doc = {"round": k, "mode": "plan", "go": False, "why": why, "items": [], "error": True}
    try:
        write_json(round_dir(place, k) / ROUND, doc)
        write_json(place / CURRENT_ROUND, {"round": k})
    except OSError:
        pass
    return {"go": False, "mode": "plan", "round": k, "reason": why}


def filled(path) -> bool:
    path = pathlib.Path(path)
    return path.is_file() and path.stat().st_size > 0


def crash_finish(place, why: str) -> dict:
    """出口の中で落ちた時の返り。標準ライブラリだけで、在って空でない plan-fields.json・ripple.json を置き、訳を finish-error.txt に書いて
    status failed の約束の形を返す"""
    place = pathlib.Path(place)
    k = current_round(place)
    d = round_dir(place, k)
    try:
        d.mkdir(parents=True, exist_ok=True)
        (d / FINISH_ERROR).write_text(why + "\n", encoding="utf-8")
        if not filled(d / FIELDS):
            write_json(d / FIELDS, {"round": k, "fields": []})
        if not filled(d / RIPPLE):
            write_json(d / RIPPLE, {"items": [], "error": why})
    except OSError:
        pass
    return {"ok": False, "status": "failed", "reason": why, "mode": "plan", "round": k, "owed": [], "plan": ports.pointer(d / FIELDS),
            "fix_plan": None, "reply": None, "handoff": None, "replan": None, "ripple": ports.pointer(d / RIPPLE), "rejects": [],
            "gave_up": None, "report": [f"修正案: 周 {k}・修正案を出せなかった（failed）: {why}"]}
