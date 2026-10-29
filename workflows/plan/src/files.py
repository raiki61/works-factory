"""plan の block の place のファイルの名と、標準ライブラリだけの落ちない道（docs/design/plan.md の 1.4・4 節）。名はこのモジュールだけが持つ。

place の直下: current-round.json（{round}）・plan-writer-prompt-<n>.md・plan-writer-fix-prompt-<n>.md（prompt.emit）・libdocs/ と libdocs.json。
周のフォルダ r<k>/（k は round）の中: intake.json・round.json・slots.json・judgment.json・prior-*.json・prior-failures-in.json・pointed-<n>.txt・
ripple-units.json・tree.json・rejects-plan.json・candidate-plan.json・reply.json・p2.fix_plan.json・plan-fields.json・handoff.json・replan.json・
replan-gave-up.json・item-brief-<no>.md・ripple.json・trace.jsonl・prompt-error.json・finish-error.txt・off-shape-plan-fields.json・
off-shape-ripple.json。

このモジュールは標準ライブラリと ports だけを import する（lib/ の import が落ちても、intake と finish の fallback が周の事実を残せるように）。
"""
from __future__ import annotations

import json
import os
import pathlib

import ports

ROLE = "plan"                       # 受け付けの拒否の控えの名（rolekit.rejects_path）
# 修正案の役の答えに要る根の欄。役の型（YAML の output_format）は出し直しの役と同じ形にするので根の欄を要ると書かず、受け付けが
# rolekit.resubmitted で確かめる（#832。出し直しの役だけが書く欄 steps.WHOLE_PLAN も同じ所で 1 回目の答えから拒む）
REQUIRED = ("plan",)
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
POINTED_TEXT = "pointed-{n}.txt"   # 人の答えが名指し、役が読む版に無く、ほかの版で見つけた文書の本文（n は intake.json の pointed の 1 始まりの番）
RIPPLE = "ripple.json"
TRACE = "trace.jsonl"                          # lib/planmarks.py の TRACE_FILE（同上）
PROMPT_ERROR = "prompt-error.json"
FINISH_ERROR = "finish-error.txt"
OFF_SHAPE = "off-shape-{name}"                 # 出口の落ちた時に形の外れた控え（plan-fields.json・ripple.json）の元の中身を残す名
NO_PLAN = "受け付けを通った修正案が無い（修正案のループが回らなかったか、途中で落ちた）"

# 周を開き直した時に名で消すファイル（広い形で消さない。place の直下の指示の記録と、ほかの周のフォルダは消さない）
OWN_FILES = (INTAKE, ROUND, SLOTS, JUDGMENT_COPY, *PRIOR_COPIES.values(), PRIOR_FAILURES_IN, RIPPLE_UNITS, TREE, REJECTS, CANDIDATE, REPLY,
             FIX_PLAN, FIELDS, HANDOFF, REPLAN, REPLAN_GAVE_UP, RIPPLE, TRACE, PROMPT_ERROR, FINISH_ERROR,
             *(OFF_SHAPE.format(name=name) for name in (FIELDS, RIPPLE)))


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


def round_no(place) -> int:
    """今の周の番号（current-round.json。無い・読めなければ 1）"""
    got = read_json(pathlib.Path(place) / CURRENT_ROUND)
    k = got.get("round") if isinstance(got, dict) else None
    return k if isinstance(k, int) and not isinstance(k, bool) and k >= 1 else 1


def current_dir(place) -> pathlib.Path:
    return round_dir(place, round_no(place))


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
        return int(ports.json(text, "shared:plan-prior.schema.json")["round"]) + 1
    except (ValueError, KeyError, TypeError, OSError, ImportError):   # lib（形の照らし）が読めない入口の fallback も同じ式で決める
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


def _sound(point, path, minimal) -> tuple[dict | None, str]:
    """point（字のままの form で指す ports.pointer の呼び）で指した (pointer, 訳)。無い・空のファイルは minimal を書いてから指す。形に
    合わない控えは元の中身を OFF_SHAPE の名へ移してから minimal に書き直し、移した名を訳に書く（落ちない出口の中で、形の照らしの誤りを
    投げ直さない）。lib（形の照らし）が読めず照らせない時と書けない時は、在る控えに手を付けずに指さず (None, 訳)"""
    path = pathlib.Path(path)
    note = ""
    if filled(path):
        try:
            return point(), ""
        except ImportError as error:
            return None, f"{path.name} を照らせない（形の照らしが読めない: {error}）ので指さない"
        except Exception as error:  # noqa: BLE001 — 出口は落ちない。形の外れた控えは別の名に残して書き直す
            kept = path.with_name(OFF_SHAPE.format(name=path.name))
            try:
                os.replace(path, kept)
            except OSError as moved:
                return None, f"{path.name} が形に合わない（{error}）が、別の名へ移せない（{moved}）ので指さない"
            note = f"{path.name} が形に合わない（{error}）ので元の中身を {kept.name} に残し、「無い」を表す形に書き直した"
    try:
        write_json(path, minimal)
        return point(), note
    except ImportError as error:
        return None, "; ".join(filter(None, (note, f"{path.name} を照らせない（形の照らしが読めない: {error}）ので指さない")))
    except Exception as error:  # noqa: BLE001 — 書けない・指せない時も出口は約束の形で返す
        return None, "; ".join(filter(None, (note, f"{path.name} を書けないか指せない（{error}）ので指さない")))


def crash_finish(place, why: str) -> dict:
    """出口の中で落ちた時の返り。在って空でなく形に合う plan-fields.json・ripple.json を指し（無い・空の物は「無い」を表す形を書き、形に
    合わない物は元の中身を別の名に残して書き直す。照らせない・書けない物は指さない）、訳を finish-error.txt と返りの reason に書いて
    status failed の約束の形を返す"""
    place = pathlib.Path(place)
    k = round_no(place)
    d = round_dir(place, k)
    try:
        d.mkdir(parents=True, exist_ok=True)
        (d / FINISH_ERROR).write_text(why + "\n", encoding="utf-8")
    except OSError:
        pass
    plan, plan_note = _sound(lambda: ports.pointer(d / FIELDS, "json(shared:plan-fields.schema.json)"), d / FIELDS, {"round": k, "fields": []})
    ripple, ripple_note = _sound(lambda: ports.pointer(d / RIPPLE, "json(shared:ripple.schema.json)"), d / RIPPLE, {"items": [], "error": why})
    reason = "; ".join(filter(None, (why, plan_note, ripple_note)))
    return {"ok": False, "status": "failed", "reason": reason, "mode": "plan", "round": k, "owed": [], "plan": plan,
            "fix_plan": None, "reply": None, "handoff": None, "replan": None, "ripple": ripple, "rejects": [],
            "gave_up": None, "report": [f"修正案: 周 {k}・修正案を出せなかった（failed）: {reason}"]}
