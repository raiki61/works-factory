# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node suite-try: 輪の 1 周の終わり。照らす前の実行器（suitewrite.pending）が在れば 1 回だけ走らせ、その結末で照らす（suitewrite.settle:
JUnit XML が出て試験が 1 件以上なら実行器の控えの tdd_suite に結び、書いた物なら取り置く。取り置きが通らなければ捨てて done: false で
書き直しの周へ）。この 1 回が修正前のテストの一式の回を兼ね、通った結末は place の run.json の suite と 1 件ごとの結末に足す
（node run が tdd_suite を走らせた時と同じ形）。走らせた後の指紋は通らなくても run.json の fingerprint_after に置く。
テストを起こす前に Archon の変数を落とし、利用者の HOME・XDG に戻して起こした印は user_env_dir の置き場に置かせる（node run と同じ）。
止められたら木を止め終えてから返りを出さずに 128+信号で抜ける。ほかの誤りは done: true・ok: false と訳の返りにする。{done, ok, why}"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402


def attempt() -> dict:
    import baseline_red
    import green_cert
    import suitewrite
    import tree_run
    from engine import util   # lib/graphloops
    from src import files, suite
    place = ports.place()
    doc = files.intake(place)
    state = suite.path(place)
    keep = ports.suite_keep()
    root = Path(util.repo_root() or os.getcwd())
    runner = suitewrite.pending(state)
    ports.drop_runner_env(doc["user_env_dir"])
    ran = cases = after = None
    if runner:
        try:
            again = (place / "suite-suite.log").exists()   # 書き直しの周は捨てた取り置きのログ（訳が名指す）を上書きしない
            cases, code, problems = baseline_red.run_suite(runner, root, place, "suite-again" if again else "suite")
            after = green_cert.fingerprint(root)
        except tree_run.Stopped as e:
            print(f"止められた（信号 {e.signum}）。テストは木ごと止めた", file=sys.stderr)
            sys.exit(128 + e.signum)
        ran = {"exe": runner, "exit": code, "problems": problems, "count": None if cases is None else len(cases)}
    out = suitewrite.settle(state, ran, keep)
    if after is not None:
        run_file = place / files.RUN
        record = json.loads(run_file.read_text(encoding="utf-8"))
        record["fingerprint_after"] = after
        if out["ok"]:
            record["suite"] = ran
            record["cases"] += cases
        run_file.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    ports.run(attempt, lambda why: {"done": True, "ok": False, "why": why})
