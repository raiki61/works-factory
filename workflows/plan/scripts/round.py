"""この差し込みの周を開く（lib/planfile.open_round）: plan/r<k>/ を作り、形（ruling が空でなければ replan）と役を起こすかを決め、
受けた事前審査の指摘を周のフォルダに写す。返り {round, mode, dir, go}"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import planfile  # noqa: E402


def main() -> None:
    plan_dir = Path(os.environ["ARTIFACTS_DIR"]) / "plan"
    try:
        ruling, why = json.loads(os.environ["INPUTS_RULING"] or "[]"), ""
    except json.JSONDecodeError as e:
        ruling, why = [], f"ruling が JSON の字でない: {e}"
    judgment, bad = planfile.read_pointed(os.environ["INPUTS_JUDGMENT"], boundary.resolve)
    review, _ = planfile.read_pointed(os.environ["INPUTS_REVIEW"], boundary.resolve)
    got = planfile.open_round(plan_dir, ruling=ruling, judgment=judgment, review=review,
                              why=why or ("" if ruling else bad and f"判定が読めない（{bad}）"))
    boundary.returns({"round": got["round"], "mode": got["mode"], "dir": f"plan/r{got['round']}", "go": got["go"]})


if __name__ == "__main__":
    main()
