"""返す node の中身: run.json を読み、赤の原因と証拠を出し（green_cert.classify）、今の指紋を取って認証する（green_cert.certify）。
今の workflows/test-gate/scripts/result.py の suite_exit・test_outcomes・gate_fields・evidence・certified・failed の写しで、始めの記録の
代わりに intake.json と suite-state.json を読む。
- 走らせ方が決まらない道（by role_needed。持ち主の決め related-tests-only）の素材は、機械が実行器の結果から組む（runner_material）。
  実行器の緑は認証しない（green_cert.RUNNER_HELD）。任せ先の CI の役は外した（docs/design/test-gate.md の 14 節）

- base は直す前の自己点検（持ち主の決め base-selfcheck-only・docs/design/test-gate.md の 15 節）: 素材は run.json の selfcheck（実行器を
  小さな試験の組で 1 回走らせた結末）だけから組む（base_material）。起動スクリプトが壊れている（test_cmd の単体は緑なのに実行器越しだけが
  赤。#836）なら ok を偽にして判定の前で止め、訳を reason に置く
- final は、落ちた試験のうち元の結末に無い物を修正前の版で走らせ直した結末（run.json の base_rerun）を元の結末に足してから比べる（with_rerun）
- base は直す前の結末のファイル baseline.json を書く（baseline_red.write_baseline。suite は suite-state.json の tdd_suite、test_cmd は
  intake.json から）。final は port baseline のファイルを baseline_red.read_baseline で読み、修正前のテストの行を証拠に足し、
  テストごとの修正前と今の結末（test_outcomes）を返す
- 起こした段と起こせなかった段の名（ran_steps。任せ先の役の run は素材の systems）・走らせ方（by・suites_line）・ログ（log）・
  修正前のテスト（baseline_line）・認証しなかった訳（reason）は 1 行に畳んで返す。証拠の文 evidence.md の行も同じ値から組む
- 足した欄: suite・suite_note（src/suite.py）・related（関わる試験の選びと走らせたか）と report（src/report.py）
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
RUNNER_STEP = "関わる試験の実行器"   # by role_needed の run の ran_steps に載せる段の名
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


def evidence(mode: str, out: dict, run: dict, material, summary: str) -> str:
    """証拠の文。走らせ方・ログ・修正前のテスト・ok の訳は返り out の欄（1 行に畳んだ物）と同じ値で書く。ほかの自由な文の値
    （素材の reason）も 1 行に畳む"""
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
             *([f"- engine の結果を任せ先へ落とした訳: {one(run['fell_back'])}"] if run.get("fell_back") else []),
             *([f"- {out['baseline_line']}"] if out["baseline_line"] else []),
             f"- 素材: {json.dumps(material, ensure_ascii=False) if material is not None else '無い'}",
             *[f"- {row}" for row in related_lines(run)],
             f"{LOG_ROW}{v['log']}",
             f"- JUnit の報告を宣言した段: {'・'.join(run['junit_steps']) or '無い'}"
             + (f"（試験を走らせなかった段: {'・'.join(run['junit_unran'])}）" if run["junit_unran"] else ""),
             f"- 一式（tdd_suite）: {json.dumps(run['suite'], ensure_ascii=False) if run.get('suite') else '無い'}",
             *([f"- 直す前の自己点検: {json.dumps(_brief_check(run['selfcheck']), ensure_ascii=False)}"] if run.get("selfcheck") else []),
             *([f"- 修正前の版で走らせ直した: {json.dumps(_brief_rerun(run['base_rerun']), ensure_ascii=False)}"]
               if run.get("base_rerun") else []),
             f"- 指紋: 走らせる前 {json.dumps(run['fingerprint_before'])}・後 {json.dumps(run['fingerprint_after'])}"]
    return "\n".join(lines) + "\n"


def _brief_check(check: dict) -> dict:
    """証拠の文の自己点検の行（1 件ごとの結末は件数だけ）"""
    cases = check.get("cases")
    return {**{k: v for k, v in check.items() if k != "cases"}, "cases": None if cases is None else len(cases)}


def _brief_rerun(rerun: dict) -> dict:
    """証拠の文の走らせ直しの行（1 件ごとの結末は件数だけ）"""
    cases = rerun.get("cases")
    return {**{k: v for k, v in rerun.items() if k != "cases"}, "cases": None if cases is None else len(cases)}


def runner_material(mode: str, run: dict) -> dict:
    """by role_needed の run の素材（機械が実行器の結果から組む）。実行器が走って結末が取れた（suite_exit が None でない）なら、終了コード
    0 は clean、ほかは found（count は落ちた件数、最低 1）。変更に関わる試験が無く走らせなかったなら not_applicable。実行器が無い・走らな
    かった・結末が取れないなら、base は awaiting_human、final は not_run（緑を仮定しない）"""
    import baseline_red
    code = suite_exit(run)
    cases = run.get("cases") or []
    if code is not None:
        if code == 0:
            return {"status": "clean", "checked": f"AI が書いた実行器が試験 {len(cases)} 件を走らせた（終了コード 0）"}
        failed = sum(1 for c in cases if c.get("outcome") in baseline_red.FAILED)
        return {"status": "found", "count": max(failed, 1), "detail": f"AI が書いた実行器が試験 {len(cases)} 件を走らせ、終了コード {code}"}
    related = run.get("related") or {}
    if related.get("applied") and not related.get("whole") and not related.get("files"):
        return {"status": "not_applicable", "reason": "変更に関わる試験が無いので試験を走らせなかった。全体の試験は CI と人に任せる"}
    problems = "；".join((run.get("suite") or {}).get("problems") or [])
    why = problems or "TDD の実行器が無いか、走らなかった（実行器を作れなかった訳は suite_note）。全体の試験は CI と人に任せる"
    return {"status": "awaiting_human" if mode == "base" else "not_run", "reason": why}


NO_BASE_TESTS = ("直す前の版では全部の試験を回さない（自己点検だけ）。自己点検に使う実行器が無いので、直す前の試験は走らせていない"
                 "——試験は修正の後の最後のテストで走らせる")
HOW_WORDS = {"related": "変更に関わる試験", "sample": "見本の試験のファイル 1 つ", "whole": "一式"}


def base_material(run: dict, doc: dict) -> dict:
    """直す前の素材（自己点検の結末だけから）。宣言の準備（setup）が落ちたら not_run（判定の前で止める）。実行器が結末を返したら、終了コード 0 で落ちた試験が無ければ clean、ほかは found。
    結末が無い時: 人が渡した実行器（port tdd_suite）が走らなかったなら not_run（試験が 1 つも走らない——判定の前で止めて準備を案内する）。
    走らせ方が決まらない道（by role_needed）は awaiting_human（今までどおり鎖を止めない）。ほか（実行器を作れなかった）は not_applicable"""
    import baseline_red
    import declared_checks
    check = run.get("selfcheck") or {}
    ran, cases = check.get("ran") or {}, check.get("cases")
    how = HOW_WORDS.get((check.get("plan") or {}).get("how"), "")
    if check.get("setup"):
        return {"status": "not_run", "reason": f"直す前の自己点検: {check['setup']}"}
    if ran and not ran.get("problems") and cases is not None and ran.get("exit") is not None:
        failed = sum(1 for c in cases if c.get("outcome") in baseline_red.FAILED)
        said = f"直す前の自己点検: 実行器が{how}の試験 {len(cases)} 件を走らせた（終了コード {ran['exit']}）"
        if ran["exit"] == 0 and not failed:
            return {"status": "clean", "checked": said}
        return {"status": "found", "count": max(failed, 1), "detail": said}
    if doc.get("tdd_suite"):
        why = "；".join(ran.get("problems") or []) or "人が渡した実行器が走らなかった"
        return {"status": "not_run", "reason": f"直す前の自己点検: {why}"}
    if run["by"] == declared_checks.ROLE_NEEDED:
        return {"status": "awaiting_human",
                "reason": "TDD の実行器が無いか、走らなかった（実行器を作れなかった訳は suite_note）。全体の試験は CI と人に任せる"}
    return {"status": "not_applicable", "reason": NO_BASE_TESTS}


def base_suites(run: dict) -> str:
    """直す前の走らせ方の 1 行"""
    check = run.get("selfcheck") or {}
    ran = check.get("ran") or {}
    how = HOW_WORDS.get((check.get("plan") or {}).get("how"), "")
    if ran.get("count") is not None and not ran.get("problems"):
        return f"直す前は自己点検だけ（全部の試験は回さない）: 実行器を{how}の試験 {ran['count']} 件で走らせた（終了コード {ran.get('exit')}）"
    return "直す前は自己点検だけ（全部の試験は回さない）: 自己点検に使う実行器が無いか、走らなかった"


def base_steps(run: dict, doc: dict) -> dict:
    """直す前の ran_steps: 自己点検の実行器が結末を返したら走らせた段、人が渡した実行器が走らなければ走らせられなかった段"""
    from src import selfcheck
    check = run.get("selfcheck") or {}
    ran = check.get("ran") or {}
    if ran.get("count") is not None and not ran.get("problems"):
        return {"ran": [selfcheck.STEP], "unran": []}
    return {"ran": [], "unran": [selfcheck.STEP] if doc.get("tdd_suite") else []}


def planned_run(root, run: dict, test_cmd: str) -> dict:
    """直す前の結末の how（修正役がテストを回す環境を探さないよう材料に貼る行。declared_checks.run_how）に渡す、走らせる計画の段の行。
    直す前は走らせないので、宣言の段と test_cmd を計画から並べる"""
    import declared_checks
    steps = [{"name": st["name"]} for st in declared_checks.checks_plan(root).get("steps") or []]
    if (test_cmd or "").strip():
        steps.append({"name": declared_checks.TEST_CMD_STEP})
    return {**run, "runs": steps}


def with_rerun(base, run: dict):
    """元の結末 base（read_baseline の返りか None）に、最後のテストが修正前の版で走らせ直した結末（run.json の base_rerun）を足した物。
    走らせ直した試験は、その結末で元の結末の行を置き換える。走らせ直しは最後と同じ走らせ方なので、落ちた試験のうち走らせ直しの結末にも
    元の結末にも居ない物は修正前の版に無かった試験で、元に無かった物として introduced と読んでよい（narrow を偽にする）。
    走らせ直していない・結末が取れなかった時は base のまま"""
    rerun = run.get("base_rerun") or {}
    cases = rerun.get("cases")
    if cases is None:
        return base
    import baseline_red
    got = set(baseline_red.outcomes(cases))
    old = [c for c in (base or {}).get("cases") or [] if baseline_red._key(c) not in got]
    exit_ = (base or {}).get("exit")
    return {**(base or {"suite": "", "test_cmd": "", "rev": rerun.get("rev") or "", "material": None}),
            "cases": [*old, *cases], "exit": exit_ if exit_ is not None else (rerun.get("exit") if rerun.get("exit") is not None else 0),
            "narrow": False}


def runner_steps(run: dict) -> dict:
    """by role_needed の run の ran_steps: 実行器が結末を取れたら走らせた段、取れなければ走らせられなかった段"""
    return {"ran": [RUNNER_STEP], "unran": []} if suite_exit(run) is not None else {"ran": [], "unran": [RUNNER_STEP]}


def related_lines(run: dict) -> list:
    """証拠の文の関わる試験の行（絞らない道は無し）"""
    import related
    got = run.get("related") or {}
    return related.lines(got) if got.get("applied") else []


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
    from engine import util   # declared_checks が lib/graphloops を sys.path に足す

    from src import report, suite

    place = pathlib.Path(place)
    doc = files.intake(place)
    mode = doc["mode"]
    if mode not in declared_checks.MODES:
        raise ValueError(f"mode は {'・'.join(declared_checks.MODES)} のどれか: {mode!r}")
    run_path = place / files.RUN
    if not run_path.is_file():
        raise ValueError(f"{files.RUN} が無い——node run が落ちたか飛ばされた")
    run = read_json(run_path)
    role = run["by"] == declared_checks.ROLE_NEEDED
    check = run.get("selfcheck") or {}
    if mode == "base":
        material = base_material(run, doc)
        cases_now = check.get("cases") or []
    else:
        material = runner_material(mode, run) if role else run["material"]
        cases_now = run["cases"]
    status = (material or {}).get("status")
    green = status == "clean"
    root = pathlib.Path(util.repo_root() or os.getcwd())
    now = green_cert.fingerprint(root)
    base = given = None   # given は port baseline の元の結末（修正前のテストの行はこれを言う）。base は走らせ直しを足した物
    if mode == "final":
        given = baseline_red.read_baseline(pathlib.Path(doc["baseline"])) if doc.get("baseline") else None
        base = with_rerun(given, run)
    cases, rows = test_outcomes(base, run) if mode == "final" else (None, None)
    red_cause, summary = green_cert.classify(material=material, runs=run["runs"], cases=cases_now, baseline_cases=cases,
                                             junit_steps=run["junit_steps"], junit_unran=run["junit_unran"],
                                             baseline_narrow=bool(base and base.get("narrow")))
    ok, why = green_cert.certify(mode=mode, material_status=status, green=green, before=run["fingerprint_before"],
                                 after=run["fingerprint_after"], now=now, self_reported=role, held_reason=green_cert.RUNNER_HELD,
                                 material_reason=(material or {}).get("reason"))
    if mode == "base" and check.get("broken"):
        from src import selfcheck
        ok, why = False, selfcheck.broken_line(check)
    if mode == "base":
        steps = base_steps(run, doc)
    else:
        steps = runner_steps(run) if role else green_cert.ran_steps(run["runs"], run["junit_unran"])
    out = {"mode": mode, "ok": ok, "green": green, "red_cause": red_cause, "ran_steps": steps,
           "baseline": None, "fingerprint": None, "test_outcomes": rows}
    state = suite.load(place)
    if mode == "base":
        ran = check.get("ran") or {}
        exit_ = ran.get("exit") if check.get("cases") is not None and not ran.get("problems") else None
        baseline_red.write_baseline(place / files.BASELINE, suite=state.get("tdd_suite") or "", test_cmd=doc["test_cmd"],
                                    rev=now["head"], exit=exit_, cases=cases_now, by=run["by"], material=material,
                                    runs=[], skipped_steps=[], narrow=(check.get("plan") or {}).get("how") != "whole",
                                    exit_codes={}, junit_steps=[], fingerprint=now, selfcheck=check,
                                    how=declared_checks.run_how(root, planned_run(root, run, doc["test_cmd"]), test_cmd=doc["test_cmd"],
                                                                material=material))
        out["baseline"] = ports.pointer(place / files.BASELINE)
        suites = base_suites(run)
    else:
        out["fingerprint"] = now
        tests = {"by": run["by"], "suites": run["runs"], "test_cmd_same_as": run["same_as"], "test_cmd_how": run["test_cmd_how"],
                 "skipped_steps": run["skipped_steps"]}
        suites = declared_checks.suites_line(tests, role_status=(status or "") if role else None)
    out.update(gate_fields(run, suites, declared_checks.baseline_line(given) if mode == "final" else "", why))
    write(place, files.EVIDENCE, evidence(mode, out, run, material, summary))
    out["evidence"] = ports.pointer(place / files.EVIDENCE)
    out["optional"] = optional_items(optional_raw)
    out["related"] = run.get("related") or files.NOT_PICKED
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
            "optional": [], "suite": _port_suite(place), "suite_note": "", "related": files.NOT_PICKED,
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
