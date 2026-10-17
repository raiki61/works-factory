# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返す節: 判定か再審の結果を、線との約束（docs/design.md の「judge の出力」）の欄で返す（lib/judge_accept.verdict）。ほかのブロックが
読む置き場のファイルは欄のポインタで返す（lib/judge_accept.PORTS）。run の頭の深さの欄 depth・depth_why は控え judge/depth-head.json
から読む（lib/headdepth。再審と控えの無い run は標準）。
決して落ちない: 境の口と lib を読む所から中の誤りを全部捕まえて標準エラーに書き、判定と目的の指し札の先を空の形で置いて
ready: false と止めの理由を返す（線は落ちた返す節の先へ進めない）"""
import json
import os
import sys
from pathlib import Path


# lib/judge_accept.PORTS・PURPOSE_PORTS の欄（lib を読めない時に null で返す。名の照らしは tests/workflows/test_judge.py）
PORTS = ("premises", "verify", "pr_excluded", "materials", "purpose_review", "depth_record", "decisions", "answer_ties",
         "review_lenses", "pr_drafts", "rejudge_exit", "rejudge_diff", "purpose_means", "world_state")


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
            "world": None, "spec": None, "out_of_purpose": None, "rejudge_verdict": None,
            **dict.fromkeys(PORTS), "depth": "標準", "depth_why": "判定の出力ノードが lib を読めない"}


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
    out.update(ja.head_depth(jdir, objection))
except Exception as e:  # noqa: BLE001  境の口か lib を読めない
    print(f"verdict: {type(e).__name__}: {e}", file=sys.stderr)
    out = fallen(objection)
try:
    print(json.dumps(out, ensure_ascii=False, allow_nan=False), flush=True)
except ValueError as e:
    print(f"verdict: 出力が JSON に書けない: {e}", file=sys.stderr)
    print(json.dumps(fallen(objection), ensure_ascii=False, allow_nan=False), flush=True)
