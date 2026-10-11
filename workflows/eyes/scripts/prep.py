"""目の指示書に差し込む値を組み、置き場の eyes/prep.json にも書く（返す節 verdict がファイルで読む）"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import concepthome  # noqa: E402
import depth  # noqa: E402
import eyeverdict  # noqa: E402
import structmark  # noqa: E402

EYES = Path(os.environ["ARTIFACTS_DIR"]) / "eyes"


def opened(ptr) -> Path | None:
    return boundary.resolve(ptr) if ptr else None


def read(ptr):
    path = opened(ptr)
    return json.loads(path.read_text(encoding="utf-8")) if path else None


start = read(json.loads(os.environ["INPUTS_START"])) or {}
judgment_file = opened(json.loads(os.environ["INPUTS_JUDGMENT"]))
purpose = read(json.loads(os.environ["INPUTS_PURPOSE"])) or {}
design = eyeverdict.read_design(opened(json.loads(os.environ["INPUTS_DESIGN"])))
diff_file = opened(json.loads(os.environ["INPUTS_DIFF"]))
diff_text = diff_file.read_text(encoding="utf-8", errors="replace")
answer = json.loads(os.environ["INPUTS_ANSWERS"])
premises = judgment_file.with_name("premises.json") if judgment_file else None
depth_rows = json.loads(os.environ["INPUTS_DEPTH"]) or []
purpose_text = purpose.get("purpose_text") or ""
after = structmark.after_counts(EYES) or eyeverdict.NO_AFTER

out = {
    "run_eyes": depth.skip_reason({"units": {r["unit_id"]: r for r in sorted(depth_rows, key=lambda r: r["unit_id"])}}) == "",
    "compare_due": eyeverdict.r2_compare_due(design, purpose_text),
    "premise_due": eyeverdict.r2_premise_invalid(design),
    "purpose_text": purpose_text,
    "design_text": design.get("design") or "",
    "premise_invalid_reason": eyeverdict.premise_reason(design),
    "diff_file": str(diff_file),
    "diff_lines": len(diff_text.splitlines()),
    "changed_files": "、".join(eyeverdict.changed_files(diff_text)),
    "scalars": eyeverdict.scalars_text(eyeverdict.scalars(diff_text)),
    "cwd": os.getcwd(),
    "base_rev": start.get("base_rev") or "",
    "review_md": str(boundary.lib_root() / "REVIEW.md"),
    "policy_path": start.get("policy_md") or "",
    "r1_head": concepthome.R1_HEAD.format(section=after),
    "r3_head": concepthome.R3_HEAD.format(section=after),
    "concept_map": concepthome.section(os.getcwd()),
    "candidates_file": str(EYES / "r1-comments.json"),
    "judgment_file": str(judgment_file or ""),
    **eyeverdict.prompt_texts(
        units=json.loads(os.environ["INPUTS_UNITS"]),
        fix_units=json.loads(os.environ["INPUTS_FIX_UNITS"]),
        changed=json.loads(os.environ["INPUTS_CHANGED"]),
        answer=answer,
        constraints=json.loads(premises.read_text(encoding="utf-8")).get("constraints") if premises and premises.is_file() else None,
        green_ok=json.loads(os.environ["INPUTS_GREEN_OK"]),
        ripple_file=str(opened(json.loads(os.environ["INPUTS_RIPPLE"])) or ""),
        world_file=str(opened(json.loads(os.environ["INPUTS_WORLD"])) or ""),
        passed=eyeverdict._human_passed(json.loads(os.environ["INPUTS_PLAN_QUESTIONS"]), answer)),
}
EYES.mkdir(parents=True, exist_ok=True)
(EYES / "prep.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
boundary.returns(out)
