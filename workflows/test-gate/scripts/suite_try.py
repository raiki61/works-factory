# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node suite-try: 輪の 1 周の終わり。照らす前の実行器（suitewrite.pending）が在れば 1 回だけ走らせ、その結末で照らす（suitewrite.settle:
JUnit XML が出て試験が 1 件以上なら実行器の控えの tdd_suite に結び、書いた物なら取り置く。取り置きが通らなければ捨てて done: false で
書き直しの周へ）。この 1 回が直す前の自己点検の回を兼ね（持ち主の決め base-selfcheck-only・docs/design/test-gate.md の 15 節）、node run が
run.json の selfcheck に置いた組（変更に関わる試験か見本の 1 つ。src/selfcheck.plan）だけを実行器に渡して走らせる。全部の試験は回さない。
通った結末は run.json の selfcheck に足す。走らせた後の指紋は通らなくても run.json の fingerprint_after に置く。
通った実行器の自己点検が赤で test_cmd が在れば、test_cmd を単体で 1 回走らせ（#836）、単体が緑なら（組が一式でなければ、実行器を
一式でも 1 回走らせてそれも赤なら）起動スクリプトが壊れていると selfcheck の broken に印を置き、実行器を退ける（suitewrite.distrust: tdd_suite を空に戻し、取り置きからも捨てる）。返す node が base を止める。
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
    from src import files, selfcheck, suite
    place = ports.place()
    doc = files.intake(place)
    state = suite.path(place)
    keep = ports.suite_keep()
    root = Path(util.repo_root() or os.getcwd())
    runner = suitewrite.pending(state)
    ports.drop_runner_env(doc["user_env_dir"])
    ran = cases = after = None
    run_file = place / files.RUN
    record = json.loads(run_file.read_text(encoding="utf-8"))   # node run が書いた物（suite-loop は run の後）
    check = record.get("selfcheck") or selfcheck.record({"how": selfcheck.WHOLE, "files": []})
    extra, only = selfcheck.args(root, check["plan"])
    if runner:
        try:
            name = "suite-again" if (place / "suite-suite.log").exists() else "suite"   # 書き直しの周は捨てた取り置きのログ（訳が名指す）を上書きしない
            cases, code, problems = baseline_red.run_suite(runner, root, place, name, args=extra, only=only)
            after = green_cert.fingerprint(root)
        except tree_run.Stopped as e:
            print(f"止められた（信号 {e.signum}）。テストは木ごと止めた", file=sys.stderr)
            sys.exit(128 + e.signum)
        ran = {"exe": runner, "exit": code, "problems": problems, "count": None if cases is None else len(cases),
               "log": str(place / f"suite-{name}.log")}
    out = suitewrite.settle(state, ran, keep)
    if after is not None:
        record["fingerprint_after"] = after
        if out["ok"]:
            check.update(ran=ran, cases=cases)
            record["log"] = ran["log"]
            if selfcheck.red(ran, cases) and doc["test_cmd"].strip():
                try:
                    check["test_cmd"] = selfcheck.compare(root, doc["test_cmd"], files.log_dir(place) / "test_cmd-alone.log")
                    record["fingerprint_after"] = green_cert.fingerprint(root)
                except tree_run.Stopped as e:
                    print(f"止められた（信号 {e.signum}）。テストは木ごと止めた", file=sys.stderr)
                    sys.exit(128 + e.signum)
                check["broken"] = check["test_cmd"]["status"] == "clean"
                if check["broken"] and extra:   # 組で赤・単体で緑: 組が test_cmd の外の赤を拾ったのでないか、実行器の一式で確かめる
                    try:
                        whole, code, problems = baseline_red.run_suite(runner, root, place, "suite-whole")
                        record["fingerprint_after"] = green_cert.fingerprint(root)
                    except tree_run.Stopped as e:
                        print(f"止められた（信号 {e.signum}）。テストは木ごと止めた", file=sys.stderr)
                        sys.exit(128 + e.signum)
                    check["whole"] = {"exit": code, "problems": problems, "count": None if whole is None else len(whole),
                                      "log": str(place / "suite-suite-whole.log")}
                    check["broken"] = selfcheck.red(check["whole"], whole)
                if check["broken"]:
                    suitewrite.distrust(state, keep, "test_cmd の単体は緑なのに、起動スクリプト越しだけが赤（直す前の自己点検）")
        record["selfcheck"] = check
        run_file.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    ports.run(attempt, lambda why: {"done": True, "ok": False, "why": why})
