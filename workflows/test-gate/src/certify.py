"""返す node の中身: run.json と（任せ先の役の run なら）ci-material.json を読み、赤の原因と証拠を出し（green_cert.classify）、今の指紋を
取って認証する（green_cert.certify。final で素材を任せ先の役が書いた緑は自己申告として認証しない）。今の workflows/test-gate/scripts/
result.py の suite_exit・test_outcomes・gate_fields・evidence・role_systems・certified・failed の写しで、始めの記録の代わりに
intake.json と suite-state.json を読む。

- base は直す前の結末のファイル baseline.json を書く（baseline_red.write_baseline。suite は suite-state.json の tdd_suite、test_cmd は
  intake.json から）。final は port baseline のファイルを baseline_red.read_baseline で読み、修正前のテストの行を証拠に足し、
  テストごとの修正前と今の結末（test_outcomes）を返す
- 起こした段と起こせなかった段の名（ran_steps。任せ先の役の run は素材の systems）・走らせ方（by・suites_line）・ログ（log）・
  修正前のテスト（baseline_line）・認証しなかった訳（reason）は 1 行に畳んで返す。証拠の文 evidence.md の行も同じ値から組む
- 任せ先の役の run で包みの宣言が無ければ証拠に NO_ADAPTER_NOTE を足す。残った作業ツリーの写しを消す
- 足した欄: suite・suite_note（src/suite.py）と report（src/report.py）
- failed: 中の誤りは全部捕まえ、ok: false・green: false・red_cause: incomplete と、誤りを名指した証拠の pointer を返す（返す node が落ちると
  線が先へ進めない）。by などの字の欄は空、reason は INNER_ERROR。lib の import はこの関数の外（certified の中）に置き、lib が読めなくても
  failed は返せる
"""
from __future__ import annotations

import json
import os
import pathlib
import traceback

import ports

from src import files

INNER_ERROR = "出力ノードの中の誤り"
RUN_ROW, LOG_ROW = "- 走らせ方: ", "- ログ: "   # 証拠の文の走らせ方・ログの行の頭（書くのはここだけ。試験と通しの照らしはここから引く）


def write(place, name: str, text: str) -> pathlib.Path:
    path = pathlib.Path(place) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def read_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def suite_exit(run: dict):
    """1 件ごとの結末を取った一式の終了コード: tdd_suite が結末を返せばその値、JUnit の報告で試験を走らせた段だけなら最初の赤の段の
    値か 0。1 件ごとの結末を取れていなければ None（final はそれを「元の結末が無い」と読む）"""
    suite = run.get("suite")
    if suite and suite.get("exit") is not None and not suite.get("problems"):
        return suite["exit"]
    junit = [r for r in run["runs"] if r["name"] in run["junit_steps"] and r["name"] not in run["junit_unran"]]
    return next((r["exit"] for r in junit if r["exit"]), 0) if junit else None


def test_outcomes(base, run: dict) -> tuple:
    """(赤の原因の照らしに渡す元の 1 件ごとの結末か None, 返りの欄 test_outcomes {rows, unmeasured})。元の結末と今の結末を比べて
    よいのは、元の結末が 1 件ごとの結末を取り（exit が None でない）、今の一式も取れた（suite_exit）時だけ。比べない時は rows を空に
    して訳を unmeasured に書く"""
    import baseline_red
    if base is None:
        why = "base の実測（baseline）が無い（実行器の無い run か、base のテストが走っていない）"
    elif base["exit"] is None:
        why = "base のテストは 1 件ごとの結末を取っていない"
    elif suite_exit(run) is None:
        why = "最後のテストは 1 件ごとの結末を取っていない"
    else:
        return base["cases"], {"rows": baseline_red.test_outcomes(base["cases"], run["cases"]), "unmeasured": ""}
    return None, {"rows": [], "unmeasured": why}


def gate_fields(run: dict, suites: str, base_line: str, why: str) -> dict:
    """返りの欄 by・suites_line・log・baseline_line・reason（字の値は 1 行に畳む）"""
    import oneline
    one = oneline.one_line
    return {"by": run["by"], "suites_line": one(suites), "log": one(run["log"] or ""), "baseline_line": one(base_line), "reason": one(why)}


def evidence(mode: str, out: dict, run: dict, material, summary: str, note: str = "") -> str:
    """証拠の文。走らせ方・ログ・修正前のテスト・ok の訳は返り out の欄（1 行に畳んだ物）と同じ値で書く。ほかの自由な文の値（役の
    素材の reason が入る）も 1 行に畳む。note は包みの知らせ（declared_checks.NO_ADAPTER_NOTE か空）"""
    import declared_checks
    import oneline
    one = oneline.one_line
    v = declared_checks.gate_values(out)
    lines = [f"# test-gate（{mode}）",
             "",
             f"- ok: {str(out['ok']).lower()}{'（' + out['reason'] + '）' if out['reason'] else ''}",
             f"- green: {str(out['green']).lower()}",
             f"- red_cause: {out['red_cause'] or '無し'}{'（' + one(summary) + '）' if summary else ''}",
             f"{RUN_ROW}{v['suites']}",
             *([f"- 包み: {note}"] if note else []),
             *([f"- engine の結果を任せ先へ落とした訳: {one(run['fell_back'])}"] if run.get("fell_back") else []),
             *([f"- {out['baseline_line']}"] if out["baseline_line"] else []),
             f"- 素材: {json.dumps(material, ensure_ascii=False) if material is not None else '無い（任せ先の CI の役が素材を渡さなかった）'}",
             f"{LOG_ROW}{v['log']}",
             f"- JUnit の報告を宣言した段: {'・'.join(run['junit_steps']) or '無い'}"
             + (f"（試験を走らせなかった段: {'・'.join(run['junit_unran'])}）" if run["junit_unran"] else ""),
             f"- 一式（tdd_suite）: {json.dumps(run['suite'], ensure_ascii=False) if run.get('suite') else '無い'}",
             f"- 指紋: 走らせる前 {json.dumps(run['fingerprint_before'])}・後 {json.dumps(run['fingerprint_after'])}"]
    return "\n".join(lines) + "\n"


def role_systems(material) -> dict:
    """任せ先の役の素材が書いた系統の名の分け（無ければ両方空。役の run は段の行を持たない）"""
    return (material or {}).get("systems") or {"ran": [], "unran": []}


def mode_of(place) -> str:
    """failed が使う形。intake.json が読めなければ final（この後の段が読む形）"""
    try:
        mode = files.read(place, files.INTAKE).get("mode")
    except (OSError, ValueError, AttributeError):
        mode = None
    return "base" if mode == "base" else "final"


def certified(place, optional_raw) -> dict:
    """返りの dict（pointer・port の値の欄を含む）。誤りは呼び手 failed が拾う"""
    import baseline_red
    import declared_checks
    import green_cert
    import rolekit
    from engine import util   # declared_checks が lib/graphloops を sys.path に足す

    from src import report, suite

    fence = ports.polyfill("fence")
    place = pathlib.Path(place)
    doc = files.intake(place)
    mode = doc["mode"]
    if mode not in declared_checks.MODES:
        raise ValueError(f"mode は {'・'.join(declared_checks.MODES)} のどれか: {mode!r}")
    if (place / files.SNAPSHOT).is_file():
        declared_checks.drop_copy(read_json(place / files.SNAPSHOT).get("top"))
    run_path = place / files.RUN
    if not run_path.is_file():
        raise ValueError(f"{files.RUN} が無い——node run が落ちたか飛ばされた")
    run = read_json(run_path)
    ci_path = place / files.MATERIAL
    role = run["by"] == declared_checks.ROLE_NEEDED
    material = (read_json(ci_path)["material"] if ci_path.is_file() else None) if role else run["material"]
    status = (material or {}).get("status")
    green = status == "clean"
    root = pathlib.Path(util.repo_root() or os.getcwd())
    now = green_cert.fingerprint(root)
    base = None
    if mode == "final" and doc.get("baseline"):
        base = baseline_red.read_baseline(pathlib.Path(doc["baseline"]))
    cases, rows = test_outcomes(base, run) if mode == "final" else (None, None)
    if material is None:   # 3 回とも拒まれて諦めた時は最後の拒否の文を人に見える証拠に出す（T45。元 ci_role.collect :349-356）
        red_cause = green_cert.INCOMPLETE
        summary = (rolekit.given_up_reason(place, declared_checks.CI_ROLE)
                   or "任せ先の CI の役が素材を渡さなかった（受け付けが拒み続けた・ループが回らなかった）")
    else:
        red_cause, summary = green_cert.classify(material=material, runs=run["runs"], cases=run["cases"], baseline_cases=cases,
                                                 junit_steps=run["junit_steps"], junit_unran=run["junit_unran"])
    ok, why = green_cert.certify(mode=mode, material_status=status, green=green, before=run["fingerprint_before"],
                                 after=run["fingerprint_after"], now=now, self_reported=role,
                                 material_reason=(material or {}).get("reason"))
    out = {"mode": mode, "ok": ok, "green": green, "red_cause": red_cause,
           "ran_steps": role_systems(material) if role else green_cert.ran_steps(run["runs"], run["junit_unran"]),
           "baseline": None, "fingerprint": None, "test_outcomes": rows}
    state = suite.load(place)
    if mode == "base":
        baseline_red.write_baseline(place / files.BASELINE, suite=state.get("tdd_suite") or "", test_cmd=doc["test_cmd"],
                                    rev=now["head"], exit=suite_exit(run), cases=run["cases"], by=run["by"], material=material,
                                    runs=run["runs"], skipped_steps=run["skipped_steps"],
                                    exit_codes={r["name"]: r["exit"] for r in run["runs"]}, junit_steps=run["junit_steps"],
                                    fingerprint=now, how=declared_checks.run_how(root, run, test_cmd=doc["test_cmd"], material=material))
        out["baseline"] = ports.pointer(place / files.BASELINE)
    else:
        out["fingerprint"] = now
    tests = {"by": run["by"], "suites": run["runs"], "test_cmd_same_as": run["same_as"], "test_cmd_how": run["test_cmd_how"],
             "skipped_steps": run["skipped_steps"]}
    suites = declared_checks.suites_line(tests, role_status=(status or "") if role else None)
    out.update(gate_fields(run, suites, declared_checks.baseline_line(base) if mode == "final" else "", why))
    note = declared_checks.NO_ADAPTER_NOTE if role and not os.environ.get(fence.RECORDS_ENV) else ""
    write(place, files.EVIDENCE, evidence(mode, out, run, material, summary, note))
    out["evidence"] = ports.pointer(place / files.EVIDENCE)
    out["optional"] = optional_items(optional_raw)
    out.update(suite.outputs(place, mode, doc["tdd_suite"]))
    out["report"] = report.lines(mode, out, place)
    return out


def optional_items(raw) -> list:
    """入力 optional（落ちても線が先へ進めてよい node の宣言 [{node, bare}] の JSON の字）を読んだ並びのまま。空は空の並び"""
    if raw is None or not raw.strip() or raw.strip() == "null":
        return []
    got = json.loads(raw)
    return got if isinstance(got, list) else []


def failed(place, error: BaseException) -> dict:
    """誤りを名指した証拠の pointer つきの偽の結末。証拠の文が書けなければ failure.txt に誤りの 1 行（それも書けなければ札だけ）"""
    mode = mode_of(place)
    line = f"{type(error).__name__}: {' '.join(str(error).split())}"
    name = files.EVIDENCE
    try:
        write(place, name, f"# test-gate（{mode}）\n\n- ok: false（{INNER_ERROR}）\n- 誤り: {line}\n\n```text\n"
              + "".join(traceback.format_exception(error)) + "```\n")
    except Exception:
        name = files.FAILURE
        try:
            write(place, name, line + "\n")
        except Exception:
            pass
    pointer = _pointer(place, name)
    return {"mode": mode, "ok": False, "green": False, "red_cause": "incomplete", "ran_steps": {"ran": [], "unran": []},
            "baseline": None, "fingerprint": None,
            "test_outcomes": {"rows": [], "unmeasured": INNER_ERROR} if mode == "final" else None,
            "evidence": pointer, "by": "", "suites_line": "", "log": "", "baseline_line": "", "reason": INNER_ERROR,
            "optional": [], "suite": _port_suite(place), "suite_note": "",
            "report": [f"試験の関門（{mode}）: {INNER_ERROR}（工場の不具合）——{pointer['path']}"]}


def _pointer(place, name: str) -> dict:
    """証拠の pointer。run の置き場が引けなければ、札の形だけ（パスは place の中の名）で返す"""
    try:
        return ports.pointer(pathlib.Path(place) / name)
    except (KeyError, ValueError):
        return {"type": ports.POINTER_TYPE, "run_id": os.environ.get("WORKFLOW_ID", ""), "path": name}


def _port_suite(place) -> str:
    """failed の suite: port の tdd_suite（intake.json が読めなければ空）"""
    try:
        return str(files.read(place, files.INTAKE).get("tdd_suite") or "")
    except (OSError, ValueError, AttributeError):
        return ""
