# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返す節（lib/structfile.keep_state）。構造の目の控え structure-state.json を書き（置き場に書けなければ訳つきの failed の控えを
別の置き場に置く）、{ok（控えの status が ok）, structure（控えの
指し札）, optional} を返す。
落ちない: 境の口と lib の import から先の誤りは全部捕まえ、標準ライブラリだけで訳つきの failed の控え（設計の行のファイルは 0 バイト。
秒の欄は書かず、読み手は 0 と読む）を書いて ok: false と指し札を返す（線は落ちた返す節の先へ進めない）。
返りの全部（failed も）に欄 optional を載せる: 入力（with:）optional の、このブロックが落ちても線が先へ進めてよい節の宣言
（[{node, bare}] の JSON の字）を境の口 boundary.items で読んだ並び。境の口を読めない時だけ []"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

# lib/structfile.py の DIR・STATE_FILE と eye.DESIGN_FILE と同じ字。試験が突き合わせる
DIR = "structure"
STATE_FILE = "structure-state.json"
DESIGN_FILE = "design.jsonl"


def collected() -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    sys.path.append(str(boundary.lib_root()))
    import structfile
    import structmark

    art = Path(os.environ["ARTIFACTS_DIR"])
    state = structfile.keep_state(art)
    return {"ok": (structmark.read(state) or {}).get("status") == "ok", "structure": boundary.pointer(state.relative_to(art).as_posix())}


def failed(error: BaseException) -> dict:
    """ok: false と、在って空でない控えの指し札。境の口が読めなかった時にも出せるよう、札は境の口を通さずに組む"""
    art = Path(os.environ["ARTIFACTS_DIR"])
    out = art / DIR
    out.mkdir(parents=True, exist_ok=True)
    design = out / DESIGN_FILE
    if not design.is_file():
        design.write_bytes(b"")
    reason = f"出力ノードの中で誤りが起きた: {type(error).__name__}: {' '.join(str(error).split())}"
    doc = {"status": "failed", "reason": reason, "design_file": str(design), "skipped": []}
    (out / STATE_FILE).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"ok": False, "structure": {"type": "archon_artifact", "run_id": os.environ.get("WORKFLOW_ID", ""),
                                       "path": f"{DIR}/{STATE_FILE}"}}


def declared() -> list:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
        import boundary
        return boundary.items(os.environ.get("INPUTS_OPTIONAL"))
    except Exception:  # noqa: BLE001  返す節は落ちない
        return []


def main() -> int:
    try:
        out = collected()
    except Exception as e:  # noqa: BLE001  返す節は落ちない（誤りは訳に残して ok: false）
        out = failed(e)
    print(json.dumps({**out, "optional": declared()}, ensure_ascii=False, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
