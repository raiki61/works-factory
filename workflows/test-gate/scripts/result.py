# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返す node result: run.json を読み、赤の原因と証拠を出し（green_cert.classify）、今の指紋を取って認証する（green_cert.certify。
走らせ方が決まらない道は、機械が実行器の結果から素材を組み、final の緑は認証しない）。base は直す前の結末のファイル
baseline.json を書く。final は port baseline の指すファイルを読み、修正前のテストの行を証拠に足し、テストごとの修正前と今の結末
（test_outcomes）を返す。足した欄は suite・suite_note（TDD の実行器と 1 行）・related（関わる試験の選び）と report（報告の日本語の行）。
落ちない: 共通の口（ports）の import から先の誤りは全部捕まえ、終了の値 0 で ok: false・green: false・red_cause: incomplete と、誤りを名指した証拠の
pointer を返す（返す node が落ちると線が先へ進めない）。その時の by などの字の欄は空、reason は INNER_ERROR。
入力 optional（落ちても線が先へ進めてよい node の宣言）は読んだ並びのまま返りの欄 optional に載せる"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]


def main() -> int:
    try:
        import ports
        from src import certify
        place = ports.place()
    except Exception as error:  # noqa: BLE001 — 共通の口か run の置き場が引けなくても落ちない（証拠を書く先が無いので、札だけ返す）
        line = f"{type(error).__name__}: {' '.join(str(error).split())}"
        print(line, file=sys.stderr)
        print(json.dumps({"mode": "final", "ok": False, "green": False, "red_cause": "incomplete",
                          "ran_steps": {"ran": [], "unran": []}, "baseline": None, "fingerprint": None,
                          "test_outcomes": {"summary": None, "details": None, "unmeasured": "出力ノードの中の誤り"},
                          "evidence": {"type": "archon_artifact", "run_id": os.environ.get("WORKFLOW_ID", ""), "path": "failure.txt"},
                          "by": "", "suites_line": "", "log": "", "baseline_line": "", "reason": "出力ノードの中の誤り",
                          "optional": [], "suite": None, "suite_note": "",
                          "related": {"applied": False, "whole": False, "files": [], "left": [], "far": [], "reasons": [], "ran": "none"},
                          "report": [f"試験の関門: 出力ノードの中の誤り（工場の不具合）——{line}"]}, ensure_ascii=False, allow_nan=False), flush=True)
        return 0
    try:
        out = certify.certified(place, os.environ.get("INPUTS_OPTIONAL"))
    except Exception as error:  # noqa: BLE001 — 落ちない node の口
        out = certify.failed(place, error)
    ports.returns(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
