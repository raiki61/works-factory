# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""書き手のループが受け取った答え（受け取れなかった訳も。runreport.accept が報告の置き場に書く runreport.AI_FILE）のポインタを返す。
答えのファイルが無い時と、境の口も lib/ も読めない時は ok: false・ai: null（落ちない）"""
import json
import os
import sys
from pathlib import Path

NO_ANSWER = {"ok": False, "ai": None}

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
except Exception:  # noqa: BLE001 — 落ちない（下で NO_ANSWER を返す）
    boundary = None


def main() -> dict:
    sys.path.append(str(boundary.lib_root()))
    import runreport

    answer = Path(os.environ["ARTIFACTS_DIR"]) / runreport.OUT_DIR / runreport.AI_FILE
    return {"ok": True, "ai": boundary.pointer(boundary.rel_of(answer))} if answer.is_file() else NO_ANSWER


if __name__ == "__main__" and boundary is None:   # 境の口を読めない時
    print(json.dumps(NO_ANSWER, allow_nan=False), flush=True)
elif __name__ == "__main__":
    try:
        result = main()
    except Exception:  # noqa: BLE001 — 落ちない
        result = NO_ANSWER
    boundary.returns(result)
