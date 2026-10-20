# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""事前審査の入口: port を読み、形（plan・replan・text）を決め、place のこの block のファイルを名で消して材料を写し、intake.json を
書く。返り {due, form, tree, k, reason}。読めない port は due: false と訳（intake-error.json）。落ちない"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def compute():
    from src import steps
    return steps.intake(
        ports.place(), Path.cwd(),
        proposal=os.environ.get("INPUTS_PROPOSAL"), fields=os.environ.get("INPUTS_FIELDS"), judgment=os.environ.get("INPUTS_JUDGMENT"),
        purpose=os.environ.get("INPUTS_PURPOSE"), design=os.environ.get("INPUTS_DESIGN"), design_why=os.environ.get("INPUTS_DESIGN_WHY"),
        world_rows=os.environ.get("INPUTS_WORLD_ROWS"), means=os.environ.get("INPUTS_MEANS"), structure=os.environ.get("INPUTS_STRUCTURE"),
        ripple=os.environ.get("INPUTS_RIPPLE"), prior=os.environ.get("INPUTS_PRIOR"), tree=os.environ.get("INPUTS_TREE"),
        excluded=os.environ.get("INPUTS_EXCLUDED"), policy=os.environ.get("INPUTS_POLICY"), recorded=os.environ.get("INPUTS_RECORDED"),
        request=os.environ.get("INPUTS_REQUEST"), review_rev=os.environ.get("INPUTS_REVIEW_REV"), diff_base=os.environ.get("INPUTS_DIFF_BASE"),
        ruling=os.environ.get("INPUTS_RULING"), conflicts=os.environ.get("INPUTS_CONFLICTS"), lang=os.environ.get("INPUTS_LANG"))


ports.run(compute, lambda why: {"due": False, "form": "", "tree": False, "k": 0, "reason": f"事前審査の入口が落ちた（{why}）"})
