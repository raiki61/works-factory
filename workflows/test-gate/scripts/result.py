# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返す節 result: run.json と（在れば）任せ先の役の ci-material.json を読み、赤の原因と証拠を出し（green_cert.classify）、今の指紋を
取って認証する（green_cert.certify）。base は直す前の結末のファイル test-gate/base/baseline.json を書く（baseline_red.write_baseline）。
final は入力 baseline の指し札の先を baseline_red.read_baseline で読む。両方とも証拠の文 test-gate/<mode>/evidence.md を書く。
落ちない: 中の誤りは全部捕まえ、終了の値 0 で ok: false・green: false・red_cause: incomplete と、誤りを名指した証拠の指し札を返す
（返す節が落ちると線が先へ進めない）"""
import json
import os
import sys
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))

import baseline_red  # noqa: E402
import declared_checks  # noqa: E402
import green_cert  # noqa: E402
from engine import util  # noqa: E402  （declared_checks が lib/graphloops を sys.path に足す）

MODES = ("base", "final")
NONE_WORDS = ("", "null")   # 入力 baseline の「無い」


def rel(mode: str, name: str) -> str:
    return f"test-gate/{mode}/{name}"


def write(rel_path: str, text: str) -> dict:
    path = Path(os.environ["ARTIFACTS_DIR"]) / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return boundary.pointer(rel_path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def baseline_doc(raw: str):
    """入力 baseline の指し札の先の直す前の結末（無ければ None）。指し札が読めない・先が無い・形が違えば ValueError"""
    if raw.strip() in NONE_WORDS:
        return None
    return baseline_red.read_baseline(boundary.resolve(json.loads(raw)))


def suite_exit(run: dict):
    """1 件ごとの結末を取った一式の終了コード: tdd_suite が結末を返せばその値、JUnit の報告で試験を走らせた段だけなら最初の赤の段の
    値か 0。1 件ごとの結末を取れていなければ None（final はそれを「元の結末が無い」と読む）"""
    suite = run.get("suite")
    if suite and suite.get("exit") is not None and not suite.get("problems"):
        return suite["exit"]
    junit = [r for r in run["runs"] if r["name"] in run["junit_steps"] and r["name"] not in run["junit_unran"]]
    return next((r["exit"] for r in junit if r["exit"]), 0) if junit else None


def evidence(mode: str, out: dict, run: dict, material, summary: str, why: str, role_status) -> str:
    tests = {"by": run["by"], "suites": run["runs"], "test_cmd_same_as": run["same_as"], "test_cmd_how": run["test_cmd_how"],
             "skipped_steps": run["skipped_steps"]}
    lines = [f"# test-gate（{mode}）",
             "",
             f"- ok: {str(out['ok']).lower()}{'（' + why + '）' if why else ''}",
             f"- green: {str(out['green']).lower()}",
             f"- red_cause: {out['red_cause'] or '無し'}{'（' + summary + '）' if summary else ''}",
             f"- 走らせ方: {run['by']}・{declared_checks.suites_line(tests, role_status=role_status)}",
             f"- 素材: {json.dumps(material, ensure_ascii=False) if material is not None else '無い（任せ先の CI の役が素材を渡さなかった）'}",
             f"- ログ: {run['log'] or '無い'}",
             f"- JUnit の報告を宣言した段: {'・'.join(run['junit_steps']) or '無い'}"
             + (f"（試験を走らせなかった段: {'・'.join(run['junit_unran'])}）" if run["junit_unran"] else ""),
             f"- 一式（tdd_suite）: {json.dumps(run['suite'], ensure_ascii=False) if run.get('suite') else '無い'}",
             f"- 指紋: 走らせる前 {json.dumps(run['fingerprint_before'])}・後 {json.dumps(run['fingerprint_after'])}"]
    return "\n".join(lines) + "\n"


def certified(mode: str, start_raw: str, baseline_raw: str) -> dict:
    start = read_json(boundary.resolve(json.loads(start_raw)))
    artifacts = Path(os.environ["ARTIFACTS_DIR"])
    run_path = artifacts / rel(mode, "run.json")
    if not run_path.is_file():
        raise ValueError(f"{rel(mode, 'run.json')} が無い——節 run が落ちたか飛ばされた")
    run = read_json(run_path)
    ci_path = artifacts / rel(mode, "ci-material.json")
    role = run["by"] == "role_needed"
    material = (read_json(ci_path)["material"] if ci_path.is_file() else None) if role else run["material"]
    status = (material or {}).get("status")
    green = status == "clean"
    root = Path(util.repo_root() or os.getcwd())
    now = green_cert.fingerprint(root)
    if material is None:
        red_cause, summary = "incomplete", "任せ先の CI の役が素材を渡さなかった（受け付けが拒み続けた・輪が回らなかった）"
    else:
        base = baseline_doc(baseline_raw) if mode == "final" else None
        source = suite_exit(run) is not None
        cases = base["cases"] if base and base["exit"] is not None and source else None
        red_cause, summary = green_cert.classify(material=material, runs=run["runs"], cases=run["cases"], baseline_cases=cases,
                                                 junit_steps=run["junit_steps"], junit_unran=run["junit_unran"])
    ok, why = green_cert.certify(mode=mode, material_status=status, green=green, before=run["fingerprint_before"],
                                 after=run["fingerprint_after"], now=now)
    out = {"mode": mode, "ok": ok, "green": green, "red_cause": red_cause, "baseline": None, "fingerprint": None}
    if mode == "base":
        baseline_red.write_baseline(artifacts / rel(mode, "baseline.json"), suite=start.get("tdd_suite") or "",
                                    test_cmd=start.get("test_cmd") or "", rev=now["head"], exit=suite_exit(run),
                                    cases=run["cases"], by=run["by"], material=material, runs=run["runs"],
                                    skipped_steps=run["skipped_steps"], exit_codes={r["name"]: r["exit"] for r in run["runs"]},
                                    junit_steps=run["junit_steps"], fingerprint=now)
        out["baseline"] = boundary.pointer(rel(mode, "baseline.json"))
    else:
        out["fingerprint"] = now
    out["evidence"] = write(rel(mode, "evidence.md"), evidence(mode, out, run, material, summary, why, (status or "") if role else None))
    return out


def failed(mode: str, error: BaseException) -> dict:
    """誤りを名指した証拠の指し札つきの偽の結末。証拠の文が書けなければ failure.txt に誤りの 1 行"""
    line = f"{type(error).__name__}: {' '.join(str(error).split())}"
    try:
        ptr = write(rel(mode, "evidence.md"), f"# test-gate（{mode}）\n\n- ok: false（返す節の中の誤り）\n- 誤り: {line}\n\n```text\n"
                    + "".join(traceback.format_exception(error)) + "```\n")
    except Exception:
        ptr = write(rel(mode, "failure.txt"), line + "\n")
    return {"mode": mode, "ok": False, "green": False, "red_cause": "incomplete", "baseline": None, "fingerprint": None,
            "evidence": ptr}


def main() -> int:
    raw_mode = os.environ.get("INPUTS_MODE", "")
    mode = raw_mode if raw_mode in MODES else "final"
    try:
        if raw_mode not in MODES:
            raise ValueError(f"mode は {'・'.join(MODES)} のどれか: {raw_mode!r}")
        out = certified(mode, os.environ["INPUTS_START"], os.environ["INPUTS_BASELINE"])
    except Exception as e:
        out = failed(mode, e)
    boundary.returns(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
