"""線の始めの節 start（docs/design.md の「線」の「順と関所」の 1）。

入口の入力を 1 つの形にそろえ（lib/entryshape.py）、始めの記録（lib/startrec.py の start.json の形）を run の置き場に書き、
指し札で返す。差分も依頼の行も無い・入力の組み合わせが拒まれる時は、落ちずに ok: false と止めの理由の語を返す。後ろの節は
when: で飛び、collect・report・result だけが走る（AI を起こす前に止める）。

入力は線の inputs:（環境変数 INPUTS_<名>）。対象のリポジトリは節の作業の置き場（cwd）。
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import linekit
from linekit import boundary

import answer
import carry
import depth
import entry
import entryshape
import gatemarks
import gatepolicy
import ghreads
import startrec

SPEC_ON = "on"
SPEC_WORDS = ("", SPEC_ON)
DESIGN_ONLY_WORDS = ("", gatemarks.DESIGN_ONLY)
THICKNESS = ("", "自動", depth.LIGHT, depth.STANDARD)
HEAVY = "重厚"
GATE = "gate-start"


class Refused(Exception):
    """入口の入力を受けない（人に向けた 1 行）"""


def raw_inputs() -> dict:
    return {
        "request": os.environ.get("INPUTS_REQUEST", ""),
        "base": os.environ.get("INPUTS_BASE", ""),
        "pr": os.environ.get("INPUTS_PR", ""),
        "spec": os.environ.get("INPUTS_SPEC", ""),
        "test_cmd": os.environ.get("INPUTS_TEST_CMD", ""),
        "tdd_suite": os.environ.get("INPUTS_TDD_SUITE", ""),
        "final_gate": os.environ.get("INPUTS_FINAL_GATE", ""),
        "unattended": os.environ.get("INPUTS_UNATTENDED", ""),
        "design_only": os.environ.get("INPUTS_DESIGN_ONLY", ""),
        "thickness": os.environ.get("INPUTS_THICKNESS", ""),
        "features_off": os.environ.get("INPUTS_FEATURES_OFF", ""),
        "features_on": os.environ.get("INPUTS_FEATURES_ON", ""),
        "policy_md": os.environ.get("INPUTS_POLICY_MD", ""),
        "fix_fixture": os.environ.get("INPUTS_FIX_FIXTURE", ""),
        "lang": os.environ.get("INPUTS_LANG", ""),
    }


def words(raw: dict, repo: Path) -> dict:
    """入力の語と名指したファイルを確かめる。受けない組み合わせ・無いファイルは Refused"""
    spec = raw["spec"].strip()
    if spec not in SPEC_WORDS:
        raise Refused(f"spec={raw['spec']!r} は知らない値（空か {SPEC_ON}）")
    try:
        gate = gatepolicy.check(raw["final_gate"], raw["unattended"], spec=bool(spec))
        off, on = entry.features_off(raw["features_off"]), entry.features_on(raw["features_on"])
    except (gatepolicy.Refused, entry.InputRefused) as error:
        raise Refused(str(error)) from None
    both = sorted(set(off) & set(on))
    if both:
        raise Refused(f"features_on と features_off の両方に {', '.join(both)} を名指した（片方だけ）")
    design_only = raw["design_only"].strip()
    if design_only not in DESIGN_ONLY_WORDS:
        raise Refused(f"design_only={raw['design_only']!r} は知らない値（空か {gatemarks.DESIGN_ONLY}）")
    thickness = raw["thickness"].strip()
    if thickness == HEAVY:
        raise Refused(f"thickness={HEAVY} で足す工程がまだ無い（{' / '.join(t for t in THICKNESS if t)}）")
    if thickness not in THICKNESS:
        raise Refused(f"thickness={raw['thickness']!r} は知らない値（{' / '.join(t for t in THICKNESS if t)}）")
    if raw["fix_fixture"].strip():
        raise Refused("固定材料（fix_fixture）から修正を始める道はまだ無い（判定と修正案を作り直さずに修正から始めるには、"
                      "fix のブロックが固定材料を受ける形が要る）。fix_fixture を空にして回す")
    return {**gate, "spec": spec, "design_only": design_only, "thickness": thickness, "features_off": off, "features_on": on,
            "policy_md": policy_md(raw["policy_md"], repo)}


def policy_md(rel: str, repo: Path) -> str:
    """方針の文書の絶対パス（名指しが無ければ空）。名指した文書が無ければ Refused。元 works/.shared/core/entry.py 588-593 行"""
    rel = rel.strip()
    if not rel:
        return ""
    path = Path(rel) if Path(rel).is_absolute() else repo / rel
    if not path.is_file():
        raise Refused(f"名指した方針の文書 {rel} が無い（policy_md。人の方針の文書を名指すなら先に置く）")
    return str(path)


def request(raw: dict, repo: Path) -> dict:
    """依頼のファイルを読む: {items, request_file, request_text, parts}。名指しが無ければ空"""
    rel = raw["request"].strip()
    if not rel:
        return {"items": [], "request_file": "", "request_text": "", "parts": carry.parts([])}
    path = Path(rel) if Path(rel).is_absolute() else repo / rel
    try:
        body = path.read_text(encoding="utf-8")
        parts = carry.parts(json.loads(body))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise Refused(f"依頼 {rel} を読めない（{type(error).__name__}: {error}）") from None
    problems = entry.request_problems(parts[carry.FINDINGS])
    if problems:
        raise Refused(f"依頼のファイル {rel} の形: findings の配列か {{findings, pr, issue, answers}} の形で、findings は "
                      "[{where, text, mechanism?, measured?, false_positive_if?}] の配列（空でない）: " + "; ".join(problems))
    return {"items": parts[carry.FINDINGS], "request_file": str(path.resolve()), "request_text": body, "parts": parts}


def versions(root: Path) -> dict:
    """版の控え: 止めた Archon の commit（ASF の factory/pack.json）と Claude Code の版。引けなければ空の字"""
    try:
        pinned = json.loads((root / "factory" / "pack.json").read_text(encoding="utf-8"))["integration_revision_required"]
    except (OSError, ValueError, KeyError):
        pinned = ""
    claude = shutil.which("claude")
    said = subprocess.run([claude, "--version"], capture_output=True, text=True) if claude else None
    return {"archon": pinned, "claude_code": said.stdout.strip() if said and said.returncode == 0 else ""}


def gate_text(shape: dict, record: dict, run_id: str) -> str:
    happened = f"run を始める前で止まった。入口: {startrec.words(shape)}"
    rest = [entry.features_part(record["features_off"], record["features_on"]), gatepolicy.head_words(record)]
    lines = gatemarks.head3(happened, "この入力で run を始めるか、止めるか（打つ行は末尾の答え方）", gatemarks.NO_PUSH)
    lines += ["", *[f"- {x}" for x in rest if x], "", "答え方:",
              f"- 始める: {answer.line(run_id, 'continue', '<一言>')}",
              f"- 止める: {answer.line(run_id, 'stop', '<理由>')}（報告は出る）"]
    return "\n".join(lines) + "\n"


def write(artifacts: Path, name: str, doc) -> dict:
    (artifacts / name).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return boundary.pointer(name)


def start(raw: dict, repo: Path, artifacts: Path, run_id: str) -> dict:
    record = {"run_id": run_id, "inputs": raw, "versions": versions(boundary.lib_root().parent)}
    try:
        checked = words(raw, repo)
        asked = request(raw, repo)
        reads = entryshape.github_reads(artifacts, repo, raw)
        if reads is not None:
            ghreads.place(artifacts, reads)
        change = entryshape.change_base(raw, repo, reads)
        entryshape.refuse_empty(asked["items"], change, repo)
        inp = {"items": asked["items"], "request_file": asked["request_file"], "request_text": asked["request_text"],
               "base": change["base"] if change else None, "pr": change["pr"] if change else None,
               "spec": bool(checked["spec"])}
        if checked["spec"] and not entryshape.request_text(inp).strip():
            raise Refused("spec=on には依頼の文（依頼のファイルか PR の題と本文）が要る")
        shape = entryshape.build(inp, repo)
    except (Refused, entryshape.Refused) as error:
        record["refused"] = str(error)
        return {"ok": False, "stop_reason": linekit.START_REFUSED, "reason": str(error),
                "record": write(artifacts, startrec.NAME, record), "prior_failures": None, "ask": False, "gate_text": "",
                "unattended": False, "design_only": False, "final_gate": ""}
    parts = asked["parts"]
    record.update({
        "input": shape, "base_rev": shape["head_rev"], "test_cmd": raw["test_cmd"], "tdd_suite": raw["tdd_suite"],
        gatepolicy.FINAL_KEY: checked[gatepolicy.FINAL_KEY], gatepolicy.UNATTENDED_KEY: checked[gatepolicy.UNATTENDED_KEY],
        "design_only": checked["design_only"], "thickness": checked["thickness"], "spec": checked["spec"],
        "policy_md": checked["policy_md"], "lang": raw["lang"],
        entry.FEATURES_KEY: checked["features_off"], entry.FEATURES_ON_KEY: checked["features_on"],
        entry.FEATURES_CUT_KEY: entry.features_cut(checked["features_off"], checked["features_on"]),
        "features": entry.feature_words(checked["features_off"], checked["features_on"]),
        "answers": parts[carry.ANSWERS], "request_text": entryshape.request_text(inp),
        "pr_file": entryshape.write_pr_file(artifacts, inp),
    })
    prior = None
    if parts[carry.PRIOR]:
        carry.place_prior(artifacts, parts[carry.PRIOR])
        prior = boundary.pointer(carry.PRIOR_IN_FILE)
    unattended = record[gatepolicy.UNATTENDED_KEY] == gatepolicy.UNATTENDED
    return {"ok": True, "stop_reason": "", "reason": "", "record": write(artifacts, startrec.NAME, record),
            "prior_failures": prior, "ask": not unattended, "gate_text": gate_text(shape, record, run_id),
            "unattended": unattended, "design_only": record["design_only"] == gatemarks.DESIGN_ONLY,
            "final_gate": record[gatepolicy.FINAL_KEY]}


def fallback(reason: str) -> dict:
    return {"ok": False, "stop_reason": linekit.LINE_SCRIPT, "reason": reason, "record": None, "prior_failures": None,
            "ask": False, "gate_text": "", "unattended": False, "design_only": False, "final_gate": ""}


if __name__ == "__main__":
    linekit.run(lambda: start(raw_inputs(), Path.cwd(), Path(os.environ["ARTIFACTS_DIR"]), os.environ["WORKFLOW_ID"]),
                fallback)
