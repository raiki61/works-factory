# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""読んだ証拠の節（lib/planfile.collect_reads）: この周に起こした修正案の役が、機械が渡したパスを読んだかを、隔離した設定の
フックの記録（lib/reads.log_here。隔離した Claude の設定の置き場の下）から集め、周のフォルダに reads-<役>.json と索引を書く。
受け付けの条件にしない。返す節に結ばない。落ちない: 中の誤りは ok: false と訳で返す。返り {ok, missing, index_file, reason}"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROLE = "plan-writer"            # 道具を持つ役の節（YAML の plan-loop の中）
QUIET = ("structure-eye",)      # 道具を持たない役の節（読む物が無い）


def collected() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    sys.path.append(str(boundary.lib_root()))
    import planfile
    import policy
    import reads

    start, _ = planfile.read_pointed(os.environ["INPUTS_START"], boundary.resolve)
    got = planfile.collect_reads(Path(os.environ["ARTIFACTS_DIR"]) / os.environ["INPUTS_DIR"],
                                 reads.log_here(), role=ROLE, quiet=QUIET,
                                 policy_md=policy.frozen_copy(start if isinstance(start, dict) else {}), repo=Path.cwd())
    boundary.returns({**got, "reason": ""})


def main() -> int:
    try:
        collected()
    except Exception as e:  # noqa: BLE001  読んだ証拠は受け付けの条件でない（線を止めない。境の口を読めない時も返す）
        print(json.dumps({"ok": False, "missing": [], "index_file": "", "reason": f"{type(e).__name__}: {' '.join(str(e).split())}"},
                         ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
