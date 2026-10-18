# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返す節（boardview.collect）。
落ちない: 境の口と lib の import から先の誤りは全部捕まえ、終了の値 0 で、偽の結末と訳を返りの約束の形で返す（返す節が落ちると線が
先へ進めない）。その時は境の口を通さず、置き場の plan-review/failed/ に事前審査の返答・設計の控え・聞かずに通した行（空。report が
review.json の隣を名で開く）と承認ノードの項目と壁打ちの行（gate.json）を素の json で書き、指し札も字で組む（諦めの行 gave_up は null）"""
import json
import os
import sys
from pathlib import Path

# boardview.FOLDER・REVIEW_FILE・PASSES_FILE・GATE_FILE と design.DESIGN_FILE、gate_axes.AXES、gatemarks.GIVEN_UP_KIND（境の口と lib を読めない時にも
# 書けるよう字で持つ。試験が一致を縛る）
FAILED = "plan-review/failed"
REVIEW_FILE = "review.json"
DESIGN_FILE = "design.json"
PASSES_FILE = "gate-passes.json"
GATE_FILE = "gate.json"
AXES = ("obvious", "world", "clean", "not_overkill")
FAILED_HEAD = "出力ノードが落ちた: "
FAILED_KIND = "given_up"


def collected() -> tuple:
    """（境の口, 返り）"""
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    sys.path.append(str(boundary.lib_root()))
    import boardview

    artifacts = Path(os.environ["ARTIFACTS_DIR"])
    got = boardview.collect(artifacts / boardview.FOLDER)
    return boundary, {**got, **{name: boundary.pointer(got[name].relative_to(artifacts).as_posix()) for name in ("review", "design")}}


def failed(error: BaseException) -> dict:
    """誤りを訳に載せた偽の結末"""
    note = FAILED_HEAD + f"{type(error).__name__}: {' '.join(str(error).split())}"
    folder = Path(os.environ.get("ARTIFACTS_DIR", ".")) / FAILED
    for name, doc in ((REVIEW_FILE, {"faces": [], "shrink": [], "reason": note}), (DESIGN_FILE, {"missing": note}),
                      (PASSES_FILE, []), (GATE_FILE, {"items": [{"kind": FAILED_KIND, "text": note}], "converge": []})):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / name).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        except OSError:
            pass
    pointer = lambda name: {"type": "archon_artifact", "run_id": os.environ.get("WORKFLOW_ID", ""), "path": f"{FAILED}/{name}"}  # noqa: E731
    return {"pass": False, "stalled": False, "review": pointer(REVIEW_FILE), "design": pointer(DESIGN_FILE),
            "gate_axes": {axis: {"ok": False, "note": note} for axis in AXES}, "ask_human": True, "questions": [{"kind": FAILED_KIND, "text": note}],
            "gave_up": None}


def main() -> int:
    try:
        boundary, out = collected()
        boundary.returns(out)
    except Exception as e:
        print(json.dumps(failed(e), ensure_ascii=False, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
