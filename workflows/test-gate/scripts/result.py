# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""返す節 result: run.json と（在れば）任せ先の役の ci-material.json を読み、赤の原因と証拠を出し（green_cert.classify）、今の指紋を
取って認証する（green_cert.certify。final で素材を任せ先の役が書いた緑は自己申告として認証しない）。base は直す前の結末のファイル
test-gate/base/baseline.json を書く（baseline_red.write_baseline）。final は入力 baseline の指し札の先を baseline_red.read_baseline で読み、
修正前のテストの行（declared_checks.baseline_line）を証拠に足す。走らせ方（by・suites_line）・ログ（log）・修正前のテスト（baseline_line）・
認証しなかった訳（reason）は 1 行に畳んで返りに載せ、証拠の文 test-gate/<mode>/evidence.md の行も同じ値から組む（報告と最後の関所は
返りの欄を読む）。任せ先の役の節が落ちて残った作業ツリーの写し（ci-snapshot.json の top）を消す。
落ちない: 境の口と lib の import から先の誤りは全部捕まえ、終了の値 0 で ok: false・green: false・red_cause: incomplete と、誤りを
名指した証拠の指し札を返す（返す節が落ちると線が先へ進めない）。その時の by などの字の欄は空、reason は INNER_ERROR"""
import json
import os
import sys
import traceback
from pathlib import Path

INNER_ERROR = "出力ノードの中の誤り"


def rel(mode: str, name: str) -> str:
    return f"test-gate/{mode}/{name}"


def write(rel_path: str, text: str) -> None:
    path = Path(os.environ["ARTIFACTS_DIR"]) / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def suite_exit(run: dict):
    """1 件ごとの結末を取った一式の終了コード: tdd_suite が結末を返せばその値、JUnit の報告で試験を走らせた段だけなら最初の赤の段の
    値か 0。1 件ごとの結末を取れていなければ None（final はそれを「元の結末が無い」と読む）"""
    suite = run.get("suite")
    if suite and suite.get("exit") is not None and not suite.get("problems"):
        return suite["exit"]
    junit = [r for r in run["runs"] if r["name"] in run["junit_steps"] and r["name"] not in run["junit_unran"]]
    return next((r["exit"] for r in junit if r["exit"]), 0) if junit else None


def gate_fields(run: dict, suites: str, base_line: str, why: str) -> dict:
    """返りの欄 by・suites_line・log・baseline_line・reason（字の値は 1 行に畳む）"""
    import oneline
    one = oneline.one_line
    return {"by": run["by"], "suites_line": one(suites), "log": one(run["log"] or ""), "baseline_line": one(base_line), "reason": one(why)}


def evidence(mode: str, out: dict, run: dict, material, summary: str) -> str:
    """証拠の文。走らせ方・ログ・修正前のテスト・ok の訳は返り out の欄（1 行に畳んだ物）と同じ値で書く。ほかの自由な文の値（役の
    素材の reason が入る）も 1 行に畳む"""
    import declared_checks
    import oneline
    one = oneline.one_line
    v = declared_checks.gate_values(out)
    lines = [f"# test-gate（{mode}）",
             "",
             f"- ok: {str(out['ok']).lower()}{'（' + out['reason'] + '）' if out['reason'] else ''}",
             f"- green: {str(out['green']).lower()}",
             f"- red_cause: {out['red_cause'] or '無し'}{'（' + one(summary) + '）' if summary else ''}",
             f"- 走らせ方: {v['suites']}",
             *([f"- engine の結果を任せ先へ落とした訳: {one(run['fell_back'])}"] if run.get("fell_back") else []),
             *([f"- {out['baseline_line']}"] if out["baseline_line"] else []),
             f"- 素材: {json.dumps(material, ensure_ascii=False) if material is not None else '無い（任せ先の CI の役が素材を渡さなかった）'}",
             f"- ログ: {v['log']}",
             f"- JUnit の報告を宣言した段: {'・'.join(run['junit_steps']) or '無い'}"
             + (f"（試験を走らせなかった段: {'・'.join(run['junit_unran'])}）" if run["junit_unran"] else ""),
             f"- 一式（tdd_suite）: {json.dumps(run['suite'], ensure_ascii=False) if run.get('suite') else '無い'}",
             f"- 指紋: 走らせる前 {json.dumps(run['fingerprint_before'])}・後 {json.dumps(run['fingerprint_after'])}"]
    return "\n".join(lines) + "\n"


def certified(mode: str, start_raw: str, baseline_raw: str) -> tuple:
    """（境の口, 返り）"""
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    sys.path.append(str(boundary.lib_root()))
    import baseline_red
    import declared_checks
    import green_cert
    import rolekit
    from engine import util   # declared_checks が lib/graphloops を sys.path に足す

    if mode not in declared_checks.MODES:
        raise ValueError(f"mode は {'・'.join(declared_checks.MODES)} のどれか: {mode!r}")
    artifacts = Path(os.environ["ARTIFACTS_DIR"])
    snap_path = artifacts / rel(mode, "ci-snapshot.json")
    if snap_path.is_file():
        declared_checks.drop_copy(read_json(snap_path).get("top"))
    start = read_json(boundary.needed(start_raw, "start"))
    run_path = artifacts / rel(mode, "run.json")
    if not run_path.is_file():
        raise ValueError(f"{rel(mode, 'run.json')} が無い——ノード run が落ちたか飛ばされた")
    run = read_json(run_path)
    ci_path = artifacts / rel(mode, "ci-material.json")
    role = run["by"] == declared_checks.ROLE_NEEDED
    material = (read_json(ci_path)["material"] if ci_path.is_file() else None) if role else run["material"]
    status = (material or {}).get("status")
    green = status == "clean"
    root = Path(util.repo_root() or os.getcwd())
    now = green_cert.fingerprint(root)
    base = None
    if mode == "final" and (base_file := boundary.pointed(baseline_raw)) is not None:
        base = baseline_red.read_baseline(base_file)
    if material is None:   # 3 回とも拒まれて諦めた時は最後の拒否の文を人に見える証拠に出す（T45。元 ci_role.collect :349-356）
        red_cause = "incomplete"
        summary = (rolekit.given_up_reason(artifacts / rel(mode, ""), declared_checks.CI_ROLE)
                   or "任せ先の CI の役が素材を渡さなかった（受け付けが拒み続けた・ループが回らなかった）")
    else:
        cases = base["cases"] if base and base["exit"] is not None and suite_exit(run) is not None else None
        red_cause, summary = green_cert.classify(material=material, runs=run["runs"], cases=run["cases"], baseline_cases=cases,
                                                 junit_steps=run["junit_steps"], junit_unran=run["junit_unran"])
    ok, why = green_cert.certify(mode=mode, material_status=status, green=green, before=run["fingerprint_before"],
                                 after=run["fingerprint_after"], now=now, self_reported=role)
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
    tests = {"by": run["by"], "suites": run["runs"], "test_cmd_same_as": run["same_as"], "test_cmd_how": run["test_cmd_how"],
             "skipped_steps": run["skipped_steps"]}
    suites = declared_checks.suites_line(tests, role_status=(status or "") if role else None)
    out.update(gate_fields(run, suites, declared_checks.baseline_line(base) if mode == "final" else "", why))
    write(rel(mode, "evidence.md"), evidence(mode, out, run, material, summary))
    out["evidence"] = boundary.pointer(rel(mode, "evidence.md"))
    return boundary, out


def failed(mode: str, error: BaseException) -> dict:
    """誤りを名指した証拠の指し札つきの偽の結末。証拠の文が書けなければ failure.txt に誤りの 1 行（それも書けなければ札だけ）。
    境の口が読めなかった時にも出せるよう、札は境の口を通さずに組む"""
    line = f"{type(error).__name__}: {' '.join(str(error).split())}"
    name = "evidence.md"
    try:
        write(rel(mode, name), f"# test-gate（{mode}）\n\n- ok: false（{INNER_ERROR}）\n- 誤り: {line}\n\n```text\n"
              + "".join(traceback.format_exception(error)) + "```\n")
    except Exception:
        name = "failure.txt"
        try:
            write(rel(mode, name), line + "\n")
        except Exception:
            pass
    return {"mode": mode, "ok": False, "green": False, "red_cause": "incomplete", "baseline": None, "fingerprint": None,
            "evidence": {"type": "archon_artifact", "run_id": os.environ.get("WORKFLOW_ID", ""), "path": rel(mode, name)},
            "by": "", "suites_line": "", "log": "", "baseline_line": "", "reason": INNER_ERROR}


def main() -> int:
    raw_mode = os.environ.get("INPUTS_MODE", "")
    try:
        boundary, out = certified(raw_mode, os.environ["INPUTS_START"], os.environ["INPUTS_BASELINE"])
        boundary.returns(out)
    except Exception as e:
        print(json.dumps(failed(raw_mode if raw_mode == "base" else "final", e), ensure_ascii=False, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
