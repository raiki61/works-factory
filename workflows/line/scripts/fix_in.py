# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""修正の段へ運ぶ値を 1 か所に集める node fix-in（docs/design/line.md の 4.1・5.2）。

修正から後ろの node（fix・replan・replan-review・refix-run・lens・delta-review の 2 段・rejudge-run・spec-check-run・eyes-in・eyes）は、
判定・構造の目・独立設計・計画の往復の値を、ここの返りの欄（$fix-in.output.<欄>）からだけ読む。
- 通常の run: 受け皿の got（直す前のテスト・判定のまとめ・構造の目）と返し（段の表・独立設計・計画の往復）と修正前の承認の答えを
  運ぶ値 received_live に組み、平らな欄にする。go は修正前の承認を通ったか。go が真なら、修正の前に 1 度だけ run の置き場を固定材料に
  写す（src.fixture.noted_capture。運ぶ値を控えに入れる。写せなくても止めない）
- 固定材料の run（start が取り込んだ）: start が置いた運ぶ値を同じ式で平らな欄にする。go は起動の承認を通ったか。写さない
足す欄: 単位の深さ units_tier（直す義務の単位の全部を承認済みの案の欄から tiers.decide_doc で）・skip_rerun（段が省く物を持つ時だけ、
軽量の単位の key）・switches（段の切り替え。tiers の返りか、運んだ判定の段で引き直した物）・no_fix（判定が止めずに直す単位を出さな
かったか、計画の status が nothing_owed）・excluded（判定のまとめの excluded。fix の 2 段に渡す。8.2）・policy（修正前の答えが
固め直した写しか、配る値の方針の写し）。運ぶ値の欄を受ける時は、要る欄を全部 ports.picked で名指す（欄の欠けた前の版の返りを
空と読まない。integration.md 4.3-12）。例外の時は進まない形と止めの語 works:line-script で、落ちた訳（壊れた始めの記録 start.json の名など）を
返りの reason に載せる（collect が報告の problems に出す）。落ちない時の reason は空。

入力（with:）: fixture（start の fixture）・start_go・ports・test_gate_base・judge・tiers・structure・design・rounds・before_fix_go・
before_fix_answer・before_fix_policy・deferred・passes・recorded（どれも飛ばされうるので {from, if_skipped: null}）と、仕様駆動の run だけが
渡す spec（spec-rounds の返り）・spec_before_fix_go・spec_before_fix_answer・spec_before_fix_policy・spec_deferred・spec_passes（spec_raw）
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

# 運ぶ値の部ごとに読む欄（received の鍵 → 欄の名）。欄を変える時は src.fixture.FORMAT を上げる
NAMES = {
    "test_gate_base": ("baseline", "suite"),
    "judge": ("ok", "stop_reason", "ready", "units", "judgment", "answer_ties", "out_of_purpose", "materials", "brief", "inputs", "purpose",
              "purpose_text", "means", "constraints", "world", "spec", "excluded", "decisions", "tier", "tier_record", "verify"),
    "tiers": ("tier", "omits", "merge", "tree", "adds", "lines"),
    "structure": ("structure",),
    "design": ("design", "reason", "premises"),
    "rounds": ("ok", "status", "round", "record", "plan", "fix_plan", "reply", "handoffs", "ripple", "owed", "review"),
}
JUDGE_FLAT = ("judgment", "units", "answer_ties", "materials", "out_of_purpose", "verify", "excluded", "tier_record", "decisions", "world",
              "spec", "purpose", "purpose_text", "means", "constraints", "brief", "inputs")
ROUND_FLAT = ("plan", "fix_plan", "ripple", "reply", "review", "record", "handoffs", "owed", "round")
NOTHING_OWED = "nothing_owed"   # plan の出力 status の語（直す義務 0 件の周）


def _part(raw, names):
    """飛ばされうる部の値（null は None。在れば要る欄を全部名指して picked。dict に戻す）"""
    got = ports.picked(raw, names)
    return None if got is None else dict(got)


def _text(raw) -> str | None:
    """飛ばされうる字の欄（Archon は字の値を字のまま渡す。null・空は None）"""
    text = ports.text(raw).strip()
    return None if text in ("", "null") else text


def received_live(raw: dict) -> dict:
    """通常の run の運ぶ値（鍵は collect と固定材料の控えが読む名）"""
    out = {name: _part(json.dumps(ports.parsed(raw[name])), names) if ports.parsed(raw[name]) is not None else None
           for name, names in NAMES.items()}
    out.update({"gate_before_fix": ports.parsed(raw["before_fix_answer"]), "before_fix_policy": _text(raw["before_fix_policy"]),
                "deferred": ports.parsed(raw["deferred"]) or [], "passes": ports.parsed(raw["passes"]) or [],
                "recorded": ports.parsed(raw["recorded"]) or []})
    return out


def _carried(received: dict) -> dict:
    """固定材料の運ぶ値を同じ欄で照らし直す（前の版の写しの欠けた欄を空と読まない）"""
    out = dict(received)
    for name, names in NAMES.items():
        if out.get(name) is not None:
            out[name] = _part(json.dumps(out[name]), names)
    return out


def _items(plan_ptr) -> list:
    """承認済みの案の欄（plan の出力 plan の先 {fields}）の項目。無い・読めなければ []"""
    if not isinstance(plan_ptr, dict):
        return []
    try:
        doc = json.loads(ports.file(json.dumps(plan_ptr)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = doc.get("fields") if isinstance(doc, dict) else None
    return items if isinstance(items, list) else []


def flat(received: dict, dealt: dict, record) -> dict:
    from src import tiers
    judge = received.get("judge") or {}
    rounds = received.get("rounds") or {}
    out = {name: judge.get(name) for name in JUDGE_FLAT}
    out["units"] = out["units"] if isinstance(out["units"], list) else []
    out["means"] = out["means"] if isinstance(out["means"], list) else []
    out["purpose_text"] = out["purpose_text"] or ""
    out.update({name: rounds.get(name) for name in ROUND_FLAT})
    out["handoffs"] = out["handoffs"] if isinstance(out["handoffs"], list) else []
    out["owed"] = out["owed"] if isinstance(out["owed"], list) else []
    out["round"] = out["round"] if isinstance(out["round"], int) else None
    base = received.get("test_gate_base") or {}
    design = received.get("design") or {}
    out.update({"baseline": base.get("baseline"), "suite": base.get("suite") or "",
                "structure": (received.get("structure") or {}).get("structure"),
                "design": design.get("design"), "design_reason": design.get("reason") or "", "design_premises": design.get("premises"),
                "answer": received.get("gate_before_fix"), "deferred": received.get("deferred") or [],
                "passes": received.get("passes") or [], "recorded": received.get("recorded") or [],
                "policy": received.get("before_fix_policy") or dealt.get("policy") or ""})
    sw = received.get("tiers")
    sw = dict(sw) if sw is not None else tiers.switches(judge.get("tier"), dealt.get("tree_named") or "", record)
    doc = tiers.decide_doc(_items(rounds.get("plan")), out["owed"], forced=dealt.get("forced") or "",
                           checked=dealt.get("has_checks") is True)
    out.update({"units_tier": tiers.rows_of(doc), "skip_rerun": tiers.skip_rerun(doc, sw.get("tier")), "switches": sw})
    out["no_fix"] = ((judge.get("ok") is True and judge.get("ready") is False and not judge.get("stop_reason"))
                     or rounds.get("status") == NOTHING_OWED)
    return out


SPEC_GATE = {"before_fix_go": "spec_before_fix_go", "before_fix_answer": "spec_before_fix_answer",
             "before_fix_policy": "spec_before_fix_policy", "deferred": "spec_deferred", "passes": "spec_passes"}


def spec_raw(raw: dict) -> dict:
    """仕様駆動の run（入力 spec が在る）の運ぶ値の元: 判定の部と往復の部は spec-rounds の返り {judge, rounds}（今の judge-out と
    plan-rounds-out の受け皿の got と同じ形）、修正前の承認の答えは spec- の付いた入力から取る。段の表・構造の目・独立設計・記録された
    方針は仕様駆動の run では回らないので null（docs/design/spec-driven.md の 6.2 の変える node の 4・6.8 の 1）。ほかの run は raw のまま"""
    spec = ports.parsed(raw.get("spec"))
    if spec is None:
        return raw
    if not isinstance(spec, dict):
        raise ValueError(f"spec（spec-rounds の返り）が object でない（{type(spec).__name__}）")
    out = {**raw, "judge": json.dumps(spec.get("judge"), ensure_ascii=False), "rounds": json.dumps(spec.get("rounds"), ensure_ascii=False),
           "tiers": "null", "structure": "null", "design": "null", "recorded": "null"}
    out.update({name: raw.get(spec_name) for name, spec_name in SPEC_GATE.items()})
    return out


def fix_in(raw: dict, place: Path, repo: Path, run_id: str) -> dict:
    from src import fixture
    raw = spec_raw(raw)
    dealt = ports.parsed(raw["ports"]) or {}
    record = ports.json(raw["record"]) if ports.parsed(raw.get("record")) is not None else None
    carried = ports.file(raw["fixture"]) if ports.parsed(raw["fixture"]) is not None else None
    start_go = ports.flag(raw["start_go"])
    live = received_live(raw)
    if carried is not None:
        received = _carried(json.loads(carried.read_text(encoding="utf-8")))
        return {**flat(received, dealt, record), "go": start_go, "received": received, "stop_reason": "", "reason": ""}
    go = ports.parsed(raw["before_fix_go"]) is True
    if go:
        fixture.noted_capture(place, repo, run_id=run_id, carried=live)
    return {**flat(live, dealt, record), "go": go, "received": None, "stop_reason": "", "reason": ""}


def compute() -> dict:
    raw = {"fixture": os.environ.get("INPUTS_FIXTURE"), "start_go": os.environ.get("INPUTS_START_GO"),
           "ports": os.environ.get("INPUTS_PORTS"), "test_gate_base": os.environ.get("INPUTS_TEST_GATE_BASE"),
           "judge": os.environ.get("INPUTS_JUDGE"), "tiers": os.environ.get("INPUTS_TIERS"),
           "structure": os.environ.get("INPUTS_STRUCTURE"), "design": os.environ.get("INPUTS_DESIGN"),
           "rounds": os.environ.get("INPUTS_ROUNDS"), "before_fix_go": os.environ.get("INPUTS_BEFORE_FIX_GO"),
           "before_fix_answer": os.environ.get("INPUTS_BEFORE_FIX_ANSWER"), "before_fix_policy": os.environ.get("INPUTS_BEFORE_FIX_POLICY"),
           "deferred": os.environ.get("INPUTS_DEFERRED"), "passes": os.environ.get("INPUTS_PASSES"),
           "recorded": os.environ.get("INPUTS_RECORDED"), "record": os.environ.get("INPUTS_RECORD"),
           "spec": os.environ.get("INPUTS_SPEC"), "spec_before_fix_go": os.environ.get("INPUTS_SPEC_BEFORE_FIX_GO"),
           "spec_before_fix_answer": os.environ.get("INPUTS_SPEC_BEFORE_FIX_ANSWER"),
           "spec_before_fix_policy": os.environ.get("INPUTS_SPEC_BEFORE_FIX_POLICY"),
           "spec_deferred": os.environ.get("INPUTS_SPEC_DEFERRED"), "spec_passes": os.environ.get("INPUTS_SPEC_PASSES")}
    return fix_in(raw, ports.place(), Path.cwd(), os.environ.get("WORKFLOW_ID", ""))


FALLBACK_KEYS = ("baseline", "judgment", "answer_ties", "materials", "out_of_purpose", "verify", "excluded", "tier_record", "decisions",
                 "world", "spec", "purpose", "constraints", "brief", "inputs", "structure", "design", "design_premises", "plan", "fix_plan",
                 "ripple", "reply", "review", "record", "round", "answer", "received")


def fallback(reason: str) -> dict:
    from src import guard
    return {**dict.fromkeys(FALLBACK_KEYS), "go": False, "no_fix": False, "stop_reason": guard.LINE_SCRIPT, "reason": reason, "policy": "", "deferred": [],
            "passes": [], "suite": "", "units": [], "purpose_text": "", "means": [], "recorded": [], "design_reason": "", "handoffs": [],
            "owed": [], "units_tier": [], "skip_rerun": [], "switches": {}}


ports.run(compute, fallback)
