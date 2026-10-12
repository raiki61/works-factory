# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""この差し込みの周を開く（lib/planfile.open_round）: plan/r<k>/ を作り、形（ruling が空でなければ replan）と役を起こすかを決め、
受けた事前審査の指摘を周のフォルダに写す。周の節が読む構造の置き場もここで決める。線が渡した指し札（空の字と null でない物）が
読めなければ役を起こさない（後の節は同じ入力を「無い」と読んで既定で進むため）。返り {round, mode, dir, go}。
落ちない: 返す節が dir を束ねるので、境の口と lib の import から先の誤りは全部捕まえ、標準ライブラリだけで周を go: false・訳つきで
開いて返す（周を開く途中で落ちて round.json の無い周のフォルダが残っていれば、それを使う）"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

# lib/planfile.py の PLAN_DIR・ROUND_FILE と、役を起こさない周の構造の置き場（open_round）と同じ字。試験が突き合わせる
PLAN_DIR = "plan"
ROUND_FILE = "round.json"
STRUCTURE_DIR = "structure"


def opened() -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    sys.path.append(str(boundary.lib_root()))
    import planfile

    plan_dir = Path(os.environ["ARTIFACTS_DIR"]) / planfile.PLAN_DIR
    try:
        ruling, why = json.loads(os.environ["INPUTS_RULING"] or "[]"), ""
    except json.JSONDecodeError as e:
        ruling, why = [], f"ruling が JSON の字でない: {e}"
    start, bad_start = planfile.read_pointed(os.environ["INPUTS_START"], boundary.resolve)
    judgment, bad = planfile.read_judgment(os.environ["INPUTS_JUDGMENT"], start, boundary.resolve)
    review, bad_review = planfile.read_pointed(os.environ["INPUTS_REVIEW"], boundary.resolve)
    _, bad_world = planfile.world_rows(os.environ["INPUTS_WORLD"], boundary.resolve)
    unread = [f"{name} が読めない（{b}）" for name, b in (("start", bad_start), ("review", bad_review), ("world", bad_world)) if b]
    if bad and not ruling:
        unread.append(f"判定が読めない（{bad}）")
    got = planfile.open_round(plan_dir, ruling=ruling, judgment=judgment, review=review,
                              units=planfile.units_of(os.environ["INPUTS_UNITS"]), repo=Path.cwd(),
                              why=why or "。".join(unread))
    return {k: got[k] for k in ("round", "mode", "dir", "go")}


def failed(error: BaseException) -> dict:
    plan_dir = Path(os.environ.get("ARTIFACTS_DIR", ".")) / PLAN_DIR
    rounds = sorted((p for p in plan_dir.glob("r*") if p.is_dir() and p.name[1:].isdigit()), key=lambda p: int(p.name[1:]))
    d = rounds[-1] if rounds and not (rounds[-1] / ROUND_FILE).exists() else plan_dir / f"r{len(rounds) + 1}"
    k = int(d.name[1:])
    why = f"周を開く節の中で誤りが起きた: {type(error).__name__}: {' '.join(str(error).split())}"
    doc = {"round": k, "mode": "plan", "go": False, "why": why, "items": [], "structure": f"{d.name}/{STRUCTURE_DIR}"}
    try:
        d.mkdir(parents=True, exist_ok=True)
        (d / ROUND_FILE).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    except OSError:
        pass
    return {"round": k, "mode": "plan", "dir": f"{PLAN_DIR}/{d.name}", "go": False}


def main() -> int:
    try:
        out = opened()
    except Exception as e:  # noqa: BLE001  返す節が dir を束ねるので、この節は落ちない
        out = failed(e)
    print(json.dumps(out, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
