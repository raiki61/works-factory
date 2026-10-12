# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返す節: 判定か再審の結果を、線との約束（docs/design.md の「judge の返り」）の欄で返す（lib/judge_accept.verdict）。
決して落ちない: 境の口と lib を読む所から中の誤りを全部捕まえて標準エラーに書き、判定と目的の指し札の先を空の形で置いて
ready: false と止めの理由を返す（線は落ちた返す節の先へ進めない）"""
import json
import os
import sys
from pathlib import Path


def fallen(objection: str) -> dict:
    """lib を読めなかった時の約束の形。判定と目的の指し札の先（Archon が在って空でないかを照らす）を空の形で置く"""
    here = "rejudge" if objection.strip() else "judge"
    folder = Path(os.environ.get("ARTIFACTS_DIR", ".")) / here
    empty = {"judgment.json": {"units": [], "questions": [], "framing": "", "one_shot": "", "materials_missing": [],
                               "carried_r1": [], "one_shot_closes": [], "precedents": []},
             "purpose.json": {"purpose_text": "", "source": "", "known_weaknesses": [], "source_files": []}}
    try:
        folder.mkdir(parents=True, exist_ok=True)
        for name, doc in empty.items():
            if not (folder / name).is_file():
                (folder / name).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    ptr = lambda name: {"type": "archon_artifact", "run_id": os.environ.get("WORKFLOW_ID", ""), "path": f"{here}/{name}"}  # noqa: E731
    return {"ready": False, "stop_reason": "works:rejudge" if objection.strip() else "works:judge", "units": [],
            "judgment": ptr("judgment.json"), "purpose": ptr("purpose.json"),
            "world": None, "spec": None, "out_of_purpose": None, "rejudge_verdict": None}


def leave(out: dict) -> None:
    """返りを境の口 boundary.returns で書く。境の口を読めない時だけ、同じ形（allow_nan=False）を標準ライブラリで書く"""
    shared = str(Path(__file__).resolve().parents[2] / ".shared")
    if shared not in sys.path:
        sys.path.insert(0, shared)
    try:
        import boundary
    except Exception:  # noqa: BLE001  境の口を読めない時（返す節は落ちない）
        print(json.dumps(out, ensure_ascii=False, allow_nan=False), flush=True)
        return
    boundary.returns(out)


objection = os.environ.get("INPUTS_OBJECTION", "")
ja = None
try:
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary

    sys.path.append(str(boundary.lib_root()))
    import judge_accept as ja

    jdir = boundary.resolve(boundary.pointer(ja.JUDGE_DIR))
    rdir = boundary.resolve(boundary.pointer(ja.REJUDGE_DIR))
    try:
        out = ja.verdict(jdir, rdir, Path.cwd(), objection, boundary.pointer)
    except Exception as e:  # noqa: BLE001  返す節は落ちない
        print(f"verdict: {type(e).__name__}: {e}", file=sys.stderr)
        out = ja.verdict_fallback(jdir, rdir, objection, boundary.pointer)
except Exception as e:  # noqa: BLE001  境の口か lib を読めない
    print(f"verdict: {type(e).__name__}: {e}", file=sys.stderr)
    out = fallen(objection)
try:
    leave(out)
except ValueError as e:
    print(f"verdict: 返りが JSON に書けない: {e}", file=sys.stderr)
    leave(fallen(objection))
