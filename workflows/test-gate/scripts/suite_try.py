# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 suite-try: 輪の 1 周の終わり。照らす前の実行器（suitewrite.pending）が在れば 1 回だけ走らせ、その結末で照らす（suitewrite.settle:
JUnit XML が出て試験が 1 件以上なら始めの記録の tdd_suite に結び、書いた物なら取り置く。取り置きが通らなければ捨てて done: false で
書き直しの周へ）。この 1 回が修正前のテストの一式の回を兼ね、通った結末は test-gate/<mode>/run.json の suite と 1 件ごとの結末に足す
（ノード run が tdd_suite を走らせた時と同じ形）。走らせた後の指紋は通らなくても run.json の fingerprint_after に置く。
テストを起こす前に Archon の変数を落とし、利用者の HOME・XDG に戻して起こした印は入力 user_env_dir の置き場に置かせる（ノード run と同じ）。
止められたら木を止め終えてから返りを出さずに 128+信号で抜ける。ほかの誤りは done: true・ok: false と訳の返りにする。{done, ok, why}"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

with boundary.guarded_imports():
    import baseline_red
    import declared_checks
    import green_cert
    import suitewrite
    import tree_run
    from engine import util   # declared_checks が lib/graphloops を sys.path に足す


def attempt() -> dict:
    start = boundary.needed(os.environ.get("INPUTS_START", ""), "start")
    gate = Path(os.environ["ARTIFACTS_DIR"]) / "test-gate" / os.environ.get("INPUTS_MODE", "")
    keep = boundary.suite_keep()
    root = Path(util.repo_root() or os.getcwd())
    runner = suitewrite.pending(start)
    boundary.drop_runner_env(os.environ.get("INPUTS_USER_ENV_DIR", ""))
    ran = cases = after = None
    if runner:
        try:
            again = (gate / "suite-suite.log").exists()   # 書き直しの周は捨てた取り置きのログ（訳が名指す）を上書きしない
            cases, code, problems = baseline_red.run_suite(runner, root, gate, "suite-again" if again else "suite")
            after = green_cert.fingerprint(root)
        except tree_run.Stopped as e:
            print(f"止められた（信号 {e.signum}）。テストは木ごと止めた", file=sys.stderr)
            sys.exit(128 + e.signum)
        ran = {"exe": runner, "exit": code, "problems": problems, "count": None if cases is None else len(cases)}
    out = suitewrite.settle(start, ran, keep)
    if after is not None:
        run_file = gate / declared_checks.RUN_FILE
        doc = json.loads(run_file.read_text(encoding="utf-8"))
        doc["fingerprint_after"] = after
        if out["ok"]:
            doc["suite"] = ran
            doc["cases"] += cases
        run_file.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    boundary.run(attempt, lambda reason: {"done": True, "ok": False, "why": reason})
