# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""目の指示書に差し込む値を組み、置き場の eyes/prep.json にも書く（返す節 verdict がファイルで読む。R4 の方針とのぶつかりを照らす記録された方針の行 policy.RECORDED_KEY も足す。無人の run が判定の保留の問いに採った推しも
問いの台帳（gatemarks.taken_pushes）から読んでその行に足し、独立設計の比較役に貼る人の答えには混ぜない）。比較役に貼った前提の控えは
eyes/r2-premises.json に書く。目が読む累積差分は、入口の base（startrec.diff_base。差分の run では PR の根）から今の作業ツリーまで
（未追跡を含み、Archon の写しの下は除く）を取って eyes/run.diff に書き、空・取れない時は訳を eyes/run-diff-none.txt に書いてそれを指す
（直す物が無い run も、修正前の HEAD でなく頼まれた変更を目が見る）。比較役には機械の実測も貼る: テストごとの base と最後の結末
（試験の関門が比べた入力 test_outcomes）と TDD のループの記録（修正の段ごとの diff の隣の記録）、累積差分の起点が PR の根か修正前の HEAD かと PR の差分・直しの差分の分かれ。前の run の前提の検算が運んだ実測（入力 premises の先の制約のうち measured_how が
carry.CARRIED_HOW_HEAD で始まる行）が在る run は、深さで目を省かない（run_eyes を真に）。R1 には最後の試験の関門の証拠の文（入力 checks。走らせ方・ログの置き場が書いてある）の
置き場 checks_file を名指す（渡っていない・読めない時は、そう書いた訳の文）。目を回す run で、run の頭の深さの段が目を
まとめる（depth.merges）なら one_eye を真にし、まとめた役が読む観点ごとの指示書を eyes/one/ に書いてその並びを one_briefs に置く
（eyeverdict.one_briefs）"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import boardview  # noqa: E402
import carry  # noqa: E402
import concepthome  # noqa: E402
import depth  # noqa: E402
import eyeverdict  # noqa: E402
import fixboard  # noqa: E402
import gatemarks  # noqa: E402
import policy  # noqa: E402
import rolekit  # noqa: E402
import startrec  # noqa: E402

EYES = Path(os.environ["ARTIFACTS_DIR"]) / "eyes"


def entry_base() -> str:
    if not base_rev:
        raise ValueError("始めの記録に入口の base が無く、累積差分の起点が分からない")
    return base_rev


def taken_pushes() -> tuple:
    """(無人の run が判定の保留の問いに採った推しの文, 添える行)。問いの台帳を最後の関所と同じ判定・結び・修正前の関所の答えで読み、
    読めなければ最後の関所（ask_final.ledger）と同じく止めずに推しを無しにして、添える行に訳"""
    if judgment_file is None:
        return [], []
    try:
        b = gatemarks.ledger_at(judgment_file, start, answer, ties_file=boundary.pointed(os.environ["INPUTS_ANSWER_TIES"]),
                                materials_file=boundary.pointed(os.environ["INPUTS_MATERIALS"]))
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        return [], [f"- 判定の問いの控えか始めの記録を読めない（無人の run が保留の問いに採った推しを並べていない。{type(error).__name__}: {error}）"]
    return [f"問い {q.get('key')}: {push}" for q, push, _ in gatemarks.taken_pushes(b)], []


def one_text(name: str) -> str:
    """観点ごとの役の指示書 commands/<name>.md に、この節の出力の欄 out を差し込んだ本文（まとめた役が読む。R4 の拒否の理由は、
    まとめた役の会話の中の物を指す字）"""
    text = (Path(__file__).resolve().parents[1] / "commands" / f"{name}.md").read_text(encoding="utf-8")
    text = re.sub(r"\$prep\.output\.([A-Za-z0-9_]+)", lambda m: str(out[m.group(1)]), text)
    return text.replace("$r4-reject.output.reason", eyeverdict.ONE_REJECTS)


def read(raw):
    path = boundary.pointed(raw)
    return json.loads(path.read_text(encoding="utf-8")) if path else None


start = read(os.environ["INPUTS_START"]) or {}
judgment_file = boundary.pointed(os.environ["INPUTS_JUDGMENT"])
purpose = read(os.environ["INPUTS_PURPOSE"]) or {}
design_file = boundary.pointed(os.environ["INPUTS_DESIGN"])
design = eyeverdict.read_design(design_file)
base_rev = startrec.diff_base(start)
diff_file, diff_text, diff_why = fixboard.diff_file(Path.cwd(), entry_base, EYES, "run.diff", "run-diff-none.txt", boundary.SKIP)
answer = boundary.parsed(os.environ["INPUTS_ANSWERS"])
changed = boundary.parsed(os.environ["INPUTS_CHANGED"])
premises = boundary.pointed(os.environ["INPUTS_PREMISES"])
constraints = json.loads(premises.read_text(encoding="utf-8")).get("constraints") if premises and premises.is_file() else None
request_file = startrec.request_file(start)
request = Path(request_file) if request_file else None
repo_review = Path.cwd() / "REVIEW.md"
gate_evidence = boundary.pointed(os.environ["INPUTS_CHECKS"])
if gate_evidence is None:
    checks_file = "（最後の試験の関門の証拠が渡っていない）"
elif not gate_evidence.is_file():
    checks_file = f"（入力 checks の証拠の文が読めない: {gate_evidence}）"
else:
    checks_file = str(gate_evidence)
depth_rows = boundary.parsed(os.environ["INPUTS_DEPTH"]) or []
head = os.environ.get("INPUTS_HEAD_DEPTH", "")
purpose_text = purpose.get("purpose_text") or ""
after = eyeverdict.after_section(EYES, EYES.parent / boardview.FOLDER, boundary.pointed(os.environ["INPUTS_PLAN"]))
human_items = eyeverdict.human_items(boundary.parsed(os.environ["INPUTS_START_ANSWERS"]), answer)
pushes, pushes_unread = taken_pushes()
recorded = policy.recorded(start, boundary.pointed(os.environ["INPUTS_DECISIONS"]), human_items=human_items, pushes=pushes)
premises_text, r2_ledger = eyeverdict.premise_section(
    human_items=human_items,
    request_text=request.read_text(encoding="utf-8") if request and request.is_file() else None, repo=Path.cwd(),
    changed=changed, constraints=constraints,
    design_seen=(eyeverdict.read_json(design_file.with_name(eyeverdict.DESIGN_PREMISES)) or {}).get("seen") if design_file else None)

out = {
    # 前の run の前提の検算が運んだ実測が制約に在る run は、深さで目を省かない（元 review-loop.py:3755 の r2_refire_forced。R2 を回し直す）
    "run_eyes": depth.skip_reason({"units": {r["unit_id"]: r for r in sorted(depth_rows, key=lambda r: r["unit_id"])}}, head) == ""
    or any(isinstance(c, dict) and str(c.get("measured_how") or "").startswith(carry.CARRIED_HOW_HEAD) for c in constraints or []),
    "compare_due": eyeverdict.r2_compare_due(design, purpose_text),
    "premise_due": eyeverdict.r2_premise_invalid(design),
    "purpose_text": purpose_text,
    "design_text": design.get("design") or "",
    "design_reply": json.dumps(design, ensure_ascii=False, indent=1),
    "diff_file": str(diff_file),
    "diff_lines": len(diff_text.splitlines()),
    "changed_files": "、".join(eyeverdict.changed_files(diff_text)) or diff_why,
    "scalars": eyeverdict.scalars_text(eyeverdict.scalars(diff_text, boundary.parsed(os.environ["INPUTS_X_SCALARS"]), diff_why)),
    "cwd": os.getcwd(),
    "base_rev": base_rev,
    "review_md": str(boundary.lib_root() / "REVIEW.md"),
    "repo_review_md": str(repo_review) if repo_review.is_file() else "（対象のリポジトリの根に REVIEW.md は無い）",
    "checks_file": checks_file,
    "policy_path": policy.frozen_copy(start),
    "recorded_policy": "\n".join([policy.recorded_section(recorded), *pushes_unread]),
    "lang_line": rolekit.lang_line(start),
    "r1_head": concepthome.R1_HEAD.format(section=after),
    "r3_head": concepthome.R3_HEAD.format(section=after),
    "concept_map": concepthome.section(os.getcwd()),
    "candidates_file": str(EYES / "r1-comments.json"),
    "judgment_file": str(judgment_file or ""),
    "premises_text": premises_text,
    "measured_text": eyeverdict.measured_section(boundary.parsed(os.environ["INPUTS_TEST_OUTCOMES"]),
                                                 eyeverdict.tdd_stages(boundary.parsed(os.environ["INPUTS_RECORDS"]), boundary.resolve)),
    "origin_text": eyeverdict.origin_section(Path.cwd(), base_rev, startrec.head_rev(start), startrec.diff_base_label(start),
                                             cumulative_empty=not diff_text and not diff_why, skip=boundary.SKIP),
    **eyeverdict.prompt_texts(
        units=boundary.parsed(os.environ["INPUTS_UNITS"]),
        fix_units=boundary.parsed(os.environ["INPUTS_FIX_UNITS"]),
        changed=changed,
        constraints=constraints,
        green_ok=boundary.parsed(os.environ["INPUTS_GREEN_OK"]),
        ripple_file=str(boundary.pointed(os.environ["INPUTS_RIPPLE"]) or ""),
        world_file=str(boundary.pointed(os.environ["INPUTS_WORLD"]) or ""),
        passed=eyeverdict._human_passed(boundary.parsed(os.environ["INPUTS_PLAN_QUESTIONS"]), answer),
        declared=boundary.parsed(os.environ["INPUTS_PLAN_DECLARED"])),
}
EYES.mkdir(parents=True, exist_ok=True)
out["one_eye"] = out["run_eyes"] and bool(depth.merges(head))
out["one_briefs"] = eyeverdict.one_briefs(EYES, {name: one_text(name) for name, _ in eyeverdict.ONE_VIEWS}) if out["one_eye"] else ""
(EYES / eyeverdict.R2_PREMISES).write_text(json.dumps(r2_ledger, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(EYES / eyeverdict.PREP_FILE).write_text(json.dumps({**out, policy.RECORDED_KEY: recorded}, ensure_ascii=False), encoding="utf-8")
boundary.returns(out)
