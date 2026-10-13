# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""目の指示書に差し込む値を組み、置き場の eyes/prep.json にも書く（返す節 verdict がファイルで読む）。比較役に貼った前提の控えは
eyes/r2-premises.json に書く。目が読む累積差分は、入口の base（startrec.diff_base。差分の run では PR の根）から今の作業ツリーまで
（未追跡を含み、Archon の写しの下は除く）を取って eyes/run.diff に書き、空・取れない時は訳を eyes/run-diff-none.txt に書いてそれを指す
（直す物が無い run も、修正前の HEAD でなく頼まれた変更を目が見る）。前の run の前提の検算が運んだ実測（判定の premises.json の制約のうち measured_how が
carry.CARRIED_HOW_HEAD で始まる行）が在る run は、深さで目を省かない（run_eyes を真に。R2 を回し直す）"""
import json
import os
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
import policy  # noqa: E402
import premises as _premises  # noqa: E402
import rolekit  # noqa: E402
import startrec  # noqa: E402

EYES = Path(os.environ["ARTIFACTS_DIR"]) / "eyes"


def entry_base() -> str:
    if not base_rev:
        raise ValueError("始めの記録に入口の base が無く、累積差分の起点が分からない")
    return base_rev


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
premises = judgment_file.with_name(_premises.PREMISES_FILE) if judgment_file else None
constraints = json.loads(premises.read_text(encoding="utf-8")).get("constraints") if premises and premises.is_file() else None
request = Path(start["request_file"]) if start.get("request_file") else None
repo_review = Path.cwd() / "REVIEW.md"
depth_rows = boundary.parsed(os.environ["INPUTS_DEPTH"]) or []
purpose_text = purpose.get("purpose_text") or ""
after = eyeverdict.after_section(EYES, EYES.parent / boardview.FOLDER, boundary.pointed(os.environ["INPUTS_PLAN"]))
premises_text, r2_ledger = eyeverdict.premise_section(
    human_items=eyeverdict.human_items(boundary.parsed(os.environ["INPUTS_START_ANSWERS"]), answer),
    request_text=request.read_text(encoding="utf-8") if request and request.is_file() else None, repo=Path.cwd(),
    changed=changed, constraints=constraints,
    design_seen=(eyeverdict.read_json(design_file.with_name(eyeverdict.DESIGN_PREMISES)) or {}).get("seen") if design_file else None)

out = {
    # 前の run の前提の検算が運んだ実測が制約に在る run は、深さで目を省かない（元 review-loop.py:3755 の r2_refire_forced。R2 を回し直す）
    "run_eyes": depth.skip_reason({"units": {r["unit_id"]: r for r in sorted(depth_rows, key=lambda r: r["unit_id"])}}) == ""
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
    "policy_path": policy.frozen_copy(start),
    "lang_line": rolekit.lang_line(start),
    "r1_head": concepthome.R1_HEAD.format(section=after),
    "r3_head": concepthome.R3_HEAD.format(section=after),
    "concept_map": concepthome.section(os.getcwd()),
    "candidates_file": str(EYES / "r1-comments.json"),
    "judgment_file": str(judgment_file or ""),
    "premises_text": premises_text,
    **eyeverdict.prompt_texts(
        units=boundary.parsed(os.environ["INPUTS_UNITS"]),
        fix_units=boundary.parsed(os.environ["INPUTS_FIX_UNITS"]),
        changed=changed,
        constraints=constraints,
        green_ok=boundary.parsed(os.environ["INPUTS_GREEN_OK"]),
        ripple_file=str(boundary.pointed(os.environ["INPUTS_RIPPLE"]) or ""),
        world_file=str(boundary.pointed(os.environ["INPUTS_WORLD"]) or ""),
        passed=eyeverdict._human_passed(boundary.parsed(os.environ["INPUTS_PLAN_QUESTIONS"]), answer)),
}
EYES.mkdir(parents=True, exist_ok=True)
(EYES / eyeverdict.R2_PREMISES).write_text(json.dumps(r2_ledger, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(EYES / "prep.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
boundary.returns(out)
