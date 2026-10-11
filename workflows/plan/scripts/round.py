"""この差し込みの周を開く（lib/planfile.open_round）: plan/r<k>/ を作り、形（ruling が空でなければ replan）と役を起こすかを決め、
受けた事前審査の指摘を周のフォルダに写す。周の節が読む構造の置き場もここで決める。線が渡した指し札（空の字と null でない物）が
読めなければ役を起こさない（後の節は同じ入力を「無い」と読んで既定で進むため）。返り {round, mode, dir, go}"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import planfile  # noqa: E402


def main() -> None:
    plan_dir = Path(os.environ["ARTIFACTS_DIR"]) / planfile.PLAN_DIR
    try:
        ruling, why = json.loads(os.environ["INPUTS_RULING"] or "[]"), ""
    except json.JSONDecodeError as e:
        ruling, why = [], f"ruling が JSON の字でない: {e}"
    judgment, bad = planfile.read_pointed(os.environ["INPUTS_JUDGMENT"], boundary.resolve)
    review, bad_review = planfile.read_pointed(os.environ["INPUTS_REVIEW"], boundary.resolve)
    _, bad_start = planfile.read_pointed(os.environ["INPUTS_START"], boundary.resolve)
    _, bad_world = planfile.world_rows(os.environ["INPUTS_WORLD"], boundary.resolve)
    unread = [f"{name} が読めない（{b}）" for name, b in (("start", bad_start), ("review", bad_review), ("world", bad_world)) if b]
    if bad and not ruling:
        unread.append(f"判定が読めない（{bad}）")
    got = planfile.open_round(plan_dir, ruling=ruling, judgment=judgment, review=review,
                              units=planfile.units_of(os.environ["INPUTS_UNITS"]), repo=Path.cwd(),
                              why=why or "。".join(unread))
    boundary.returns({k: got[k] for k in ("round", "mode", "dir", "go")})

if __name__ == "__main__":
    main()
