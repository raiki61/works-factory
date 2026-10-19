# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node run: 走らせる前の指紋を取り、走らせ方を機械で決めて走らせ（declared_checks.run_ci）、tdd_suite が在れば一式を 1 回走らせて
1 件ごとの結末を足し、走らせた後の指紋を取る。結果の全部は place の run.json に書き、node の返りは output_format の欄だけ。
返りの suite_owed は、この後に TDD の実行器を用意するか（suitewrite.need。tdd_suite を省いた run の base）。
値は intake.json から読む。base は同じ run の中の試験の結果の控え（reuse_dir。run の名は reuse_key、空ならこの run の id）を引いて置く。
fix の TDD の輪の頭が同じ控えを引く。final は引かず置かない（最後のテストは省かない）。旗 tree_run.RERUN_ENV が立てば引かない。
テストを起こす前に Archon の変数を落とす（対象のテストに継がせず、node ごとに違う値で控えの指紋を割らない）。利用者の HOME・XDG に戻して
起こした印は user_env_dir の置き場に置かせる。
止められたら木を止め終えてから返りを出さずに 128+信号で抜ける。走らせられない（範囲の宣言の誤りなど）は 1 で、理由を標準エラーに 1 行"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

import baseline_red  # noqa: E402  （lib/）
import declared_checks  # noqa: E402
import green_cert  # noqa: E402
import suitewrite  # noqa: E402
import tree_run  # noqa: E402
from engine import util  # noqa: E402  （lib/graphloops）

from src import files, scope, suite  # noqa: E402

OUTPUT = ("by", "material", "runs", "skipped_steps", "same_as", "log", "junit_steps", "fingerprint_before", "fingerprint_after")


def main() -> int:
    place = ports.place()
    doc = files.intake(place)
    mode = doc["mode"]
    root = Path(util.repo_root() or os.getcwd())
    log_dir = files.log_dir(place)
    reuse = (tree_run.reuse_place(doc["reuse_dir"], doc["reuse_key"] or os.environ["WORKFLOW_ID"],
                                  rerun=bool(os.environ.get(tree_run.RERUN_ENV)))
             if mode == "base" else None)
    state = suite.load(place)
    owed = suitewrite.need(state, mode)
    ports.drop_runner_env(doc["user_env_dir"])
    wheres = scope.request_wheres(doc["request"], mode, doc["request_scope"])
    try:
        before = green_cert.fingerprint(root)
        ci = declared_checks.run_ci(root, test_cmd=doc["test_cmd"], log_dir=log_dir,
                                    changed=lambda: scope.changed(root, doc["base"], wheres), after_judge=mode == "final",
                                    report_dir=place / files.JUNIT, reuse=reuse)
        ran = None
        if doc["tdd_suite"]:
            cases, code, problems = baseline_red.run_suite(doc["tdd_suite"], root, place, "suite")
            ran = {"exe": doc["tdd_suite"], "exit": code, "problems": problems}
            ci["cases"] += cases or []
        after = green_cert.fingerprint(root)
    except tree_run.Stopped as e:
        print(f"止められた（信号 {e.signum}）。テストは木ごと止めた", file=sys.stderr)
        return 128 + e.signum
    except (declared_checks.CiRefused, ValueError) as e:
        print(f"テストを走らせられない: {e}", file=sys.stderr)
        return 1
    record = {"mode": mode, "base_rev": doc["base"], **ci, "suite": ran, "fingerprint_before": before, "fingerprint_after": after}
    (place / files.RUN).write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    ports.returns({**{k: record[k] for k in OUTPUT}, "suite_owed": owed})
    return 0


if __name__ == "__main__":
    sys.exit(main())
