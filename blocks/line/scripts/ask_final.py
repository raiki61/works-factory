# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""最後の承認ノードを開くかと、見せる文を決める node ask-final（docs/design/line.md の 2 節の 4・6 節・8.1。決めと文は src.final）。

受け皿の got（試験・目・封じ・仕様・修正の後の並行 PR・案の直しの事前審査）と line の node の返り（fix-in・fixed・judged）を読み、
開ける理由の列から開くかを決める。開いた文は place の gates/final-gate.md に残す。merge の apply に渡す値（sealed_hash・fingerprint・
green_ok・eyes_ok・r2）もこの node が受け皿の got から返す（受け皿の got の中の欄は Archon の with: で読めない。output_format の宣言の
外の道になるため）。封じが飛んだ・落ちた時は sealed_hash が空で、開ける理由に「差分を封じられなかった」が入る（閉じた側に倒れる）。

入力（with:）: fix_in・fixed・judged（line の node の返り）・tests・eyes・seal・spec_check・parallel_after・replan_review（受け皿の got か
null）・replan_answer（案の直しの承認ノードの答えか null）・widened（ask-replan の widened か null）・start_answer（起動の承認ノードの答えか
null。今は文に載せない）・record（始めの記録の pointer）・final_gate（開き方）・ports（start の配る値）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

FIX_IN = ("answer", "passes", "structure", "record", "judgment", "units")
FIXED = ("no_fix", "conflicts", "handoffs", "mismatched", "objection", "units", "groups", "stages", "replan_items", "refixed", "skip_why")
JUDGED = ("units", "judgment", "answer_ties", "materials", "rejudged", "rejudge_verdict", "lines")
TESTS = ("ok", "green", "red_cause", "ran_steps", "by", "suites_line", "log", "baseline_line", "reason", "fingerprint")
EYES = ("ok", "r1", "r2", "r3", "r4", "questions", "passes", "premise_check", "notes", "after", "after_ok")
SEAL = ("ok", "reason", "hash", "protected_hits", "protected_count", "diff")
SPEC = ("questions", "unchecked")
PARALLEL = ("ok", "status", "stop_reason", "reason", "material", "report")


def compute() -> dict:
    raw = {"fix_in": os.environ.get("INPUTS_FIX_IN"), "fixed": os.environ.get("INPUTS_FIXED"), "judged": os.environ.get("INPUTS_JUDGED"),
           "tests": os.environ.get("INPUTS_TESTS"), "eyes": os.environ.get("INPUTS_EYES"), "seal": os.environ.get("INPUTS_SEAL"),
           "spec_check": os.environ.get("INPUTS_SPEC_CHECK"), "parallel_after": os.environ.get("INPUTS_PARALLEL_AFTER"),
           "replan_review": os.environ.get("INPUTS_REPLAN_REVIEW"), "replan_answer": os.environ.get("INPUTS_REPLAN_ANSWER"),
           "widened": os.environ.get("INPUTS_WIDENED"), "start_answer": os.environ.get("INPUTS_START_ANSWER"),
           "record": os.environ.get("INPUTS_RECORD"), "final_gate": os.environ.get("INPUTS_FINAL_GATE"),
           "ports": os.environ.get("INPUTS_PORTS")}
    from src import files, final, gates, rounds, startrec

    given = ports.parsed(raw["ports"]) or {}
    fix_in = ports.picked(raw["fix_in"], FIX_IN)
    fixed = ports.picked(raw["fixed"], FIXED)
    if fix_in is None or fixed is None:
        raise ValueError("fix-in か fixed の返りが無い（with: の鍵の結びを確かめる）")
    tests, eyes, seal = ports.picked(raw["tests"], TESTS), ports.picked(raw["eyes"], EYES), ports.picked(raw["seal"], SEAL)
    parallel_after = ports.picked(raw["parallel_after"], PARALLEL)
    unread = []
    record_path = ports.file(raw["record"])
    try:
        record = startrec.load(record_path) if record_path else {}
    except (OSError, ValueError) as error:
        record, unread = {}, [f"始めの記録を読めない（保留の問いと起点の版を読んでいない。{type(error).__name__}: {error}）"]
    missing: list = []   # 指す先が無い・読めない控え（開ける理由にする。形の違う pointer は落ちる）
    doc = gates.read_located(fix_in["record"], "往復の記録", missing)
    rounds_lines = rounds.lines(doc, str(ports.place() / files.PLAN_CONVERGE_DIR)) if isinstance(doc, dict) else []
    widened = ports.parsed(raw["widened"])
    got = final.gather(fix_in=dict(fix_in), fixed=dict(fixed), judged=ports.picked(raw["judged"], JUDGED), tests=tests, eyes=eyes,
                       seal_got=seal, spec_check=ports.picked(raw["spec_check"], SPEC), parallel_after=parallel_after,
                       replan_answer=ports.parsed(raw["replan_answer"]), widened=widened if isinstance(widened, list) else [],
                       record=record, given=given, rounds_lines=rounds_lines, unread=unread, missing=missing)
    out = final.ask(got, mode=ports.text(raw["final_gate"]), unattended=bool(given.get("unattended")), run_id=os.environ["WORKFLOW_ID"])
    return {**final.keep(out, ports.place()), **final.merge_values(tests, eyes, seal)}


def fallback(reason: str) -> dict:
    from src import guard

    return {"open": False, "go": False, "stop_reason": guard.LINE_SCRIPT, "text": "", "reasons": [reason], "sealed_hash": "",
            "fingerprint": None, "green_ok": False, "eyes_ok": False, "r2": None}


ports.run(compute, fallback)
