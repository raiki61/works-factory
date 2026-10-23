# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""node run: 走らせる前の指紋を取り、形ごとに走らせ、走らせた後の指紋を取る。結果の全部は place の run.json に書き、node の返りは
output_format の欄だけ。返りの suite_owed は、この後に TDD の実行器を用意するか（suitewrite.need。tdd_suite を省いた run の base）。
- base（直す前の自己点検。持ち主の決め base-selfcheck-only・docs/design/test-gate.md の 15 節）: 全部の試験を回さない。走らせ方の語は
  計画だけで決め（declared_checks.plan_by。範囲の宣言の誤りは走らせる前に止める）、変更に関わる試験を選んで自己点検の組を決め
  （src/selfcheck.plan）、run.json の selfcheck に置く。宣言の準備（setup）だけは走らせ（tree_run.prepare）、落ちたら selfcheck の setup に
  訳を置く（返す node が base を止める。実行器は用意しない）。人が tdd_suite を渡していれば、その実行器をここで組の試験だけ 1 回走らせる。
  用意する実行器は輪の suite-try が同じ組で走らせる
- final: 走らせ方を機械で決めて走らせ（declared_checks.run_ci）、tdd_suite が在れば一式を 1 回走らせて 1 件ごとの結末を足す。
  走らせ方が決まらない道（by role_needed）は、変更に関わる試験だけを選び（lib/related.pick。持ち主の決め related-tests-only）、その試験の
  ファイルだけを実行器に渡す。選べなければ一式、関わる試験が無ければ走らせない（run.json の related に選びと、走らせたかの ran）。
  落ちた試験のうち元の結末（port baseline）に無い物が在れば、同じ走らせ方を修正前の版（port base）の一時の worktree で 1 回走らせ、
  1 件ごとの結末を run.json の base_rerun に置く（返す node が元の結末に足して赤の原因を分ける）。final は控えを引かず置かない
- テストを起こす前に Archon の変数を落とす（対象のテストに継がせず、node ごとに違う値で控えの指紋を割らない）。利用者の HOME・XDG に戻して
  起こした印は user_env_dir の置き場に置かせる
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
import related  # noqa: E402
import suitewrite  # noqa: E402
import tree_run  # noqa: E402
from engine import util  # noqa: E402  （lib/graphloops）

from src import files, scope, selfcheck, suite  # noqa: E402

OUTPUT = ("by", "material", "runs", "skipped_steps", "same_as", "log", "junit_steps", "fingerprint_before", "fingerprint_after")
NONE_RUN = {"material": None, "runs": [], "skipped_steps": [], "same_as": None, "test_cmd_how": None, "log": "", "cases": [],
            "junit_steps": [], "junit_unran": []}


def main() -> int:
    place = ports.place()
    doc = files.intake(place)
    mode = doc["mode"]
    root = Path(util.repo_root() or os.getcwd())
    log_dir = files.log_dir(place)
    state = suite.load(place)
    owed = suitewrite.need(state, mode)
    ports.drop_runner_env(doc["user_env_dir"])
    try:
        before = green_cert.fingerprint(root)
        record = base_run(root, place, doc) if mode == "base" else final_run(root, place, doc, log_dir)
        after = green_cert.fingerprint(root)
        owed = owed and not (record.get("selfcheck") or {}).get("setup")   # 準備が落ちた base は止まるので、実行器を書かせない
    except tree_run.Stopped as e:
        print(f"止められた（信号 {e.signum}）。テストは木ごと止めた", file=sys.stderr)
        return 128 + e.signum
    except (declared_checks.CiRefused, ValueError) as e:
        print(f"テストを走らせられない: {e}", file=sys.stderr)
        return 1
    record = {"mode": mode, "base_rev": doc["base"], **record, "fingerprint_before": before, "fingerprint_after": after}
    (place / files.RUN).write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    ports.returns({**{k: record[k] for k in OUTPUT}, "suite_owed": owed})
    return 0


def base_run(root: Path, place: Path, doc: dict) -> dict:
    """直す前の自己点検の記録（全部の試験は回さない）。人が渡した実行器だけをここで組の試験で 1 回走らせる"""
    by = declared_checks.plan_by(root, doc["test_cmd"])
    picked = scope.related_pick(root, doc, place / files.IMPACT)
    check = selfcheck.record(selfcheck.plan(root, picked))
    try:   # 宣言の準備（setup）だけは走らせ、落ちた base を止める（試験は走らせない）
        tree_run.prepare(str(root), env=tree_run.outside_env(os.environ))
    except OSError as e:
        check["setup"] = f"{e}"
    if doc["tdd_suite"] and not check.get("setup"):
        extra, only = selfcheck.args(root, check["plan"])
        cases, code, problems = baseline_red.run_suite(doc["tdd_suite"], root, place, "suite", args=extra, only=only)
        check["ran"] = {"exe": doc["tdd_suite"], "exit": code, "problems": problems, "count": None if cases is None else len(cases),
                        "log": str(place / "suite-suite.log")}
        check["cases"] = cases
    # related は最後のテストの絞りの欄（直す前の組は selfcheck の plan が持ち、報告は suites_line で言う）
    return {**NONE_RUN, "by": by, "log": (check["ran"] or {}).get("log", ""), "suite": None,
            "related": files.related_record(None, None), "selfcheck": check}


def final_run(root: Path, place: Path, doc: dict, log_dir: Path) -> dict:
    """最後のテストの記録（今までどおり一式。赤が元の結末に無ければ修正前の版で同じ走らせ方を 1 回）"""
    ci = declared_checks.run_ci(root, test_cmd=doc["test_cmd"], log_dir=log_dir,
                                changed=lambda: scope.changed(root, doc["base"], ()), after_judge=True,
                                report_dir=place / files.JUNIT, reuse=None)
    ran = None
    extra, narrow = (), False
    picked = scope.related_pick(root, doc, place / files.IMPACT) if ci["by"] == declared_checks.ROLE_NEEDED else None
    if doc["tdd_suite"] and (picked is None or picked["whole"] or picked["files"]):
        narrow = picked is not None and not picked["whole"]
        extra = related.args(root, picked) if narrow else ()
        cases, code, problems = baseline_red.run_suite(doc["tdd_suite"], root, place, "suite", args=extra, only=narrow)
        ran = {"exe": doc["tdd_suite"], "exit": code, "problems": problems}
        ci["cases"] += cases or []
    record = {**ci, "suite": ran, "related": files.related_record(picked, ran)}
    if ran and picked is not None:
        record["log"] = str(place / "suite-suite.log")
    try:
        rerun = base_rerun(root, place, doc, ci, ran, extra, narrow, log_dir)
    except (declared_checks.CiRefused, ValueError, OSError) as e:   # 走らせ直せないのは最後のテストの誤りでない（比べる事実が無いだけ）
        rerun = {"rev": doc["base"], "cases": None, "exit": None, "problems": [f"{type(e).__name__}: {e}"], "logs": []}
    if rerun is not None:
        record["base_rerun"] = rerun
    return record


def base_rerun(root: Path, place: Path, doc: dict, ci: dict, ran, extra, narrow: bool, log_dir: Path):
    """落ちた試験のうち元の結末に無い物が在れば、最後と同じ走らせ方（JUnit の報告を持つ宣言の段と実行器）を修正前の版の一時の
    worktree で 1 回走らせた {rev, cases, problems}（走らせない時は None）。写せない・結末が取れない時は cases が None と訳"""
    known = set()
    if doc["baseline"]:
        try:
            known = set(baseline_red.outcomes(baseline_red.read_baseline(Path(doc["baseline"]))["cases"]))
        except ValueError:
            known = set()
    fresh = [c for c in ci["cases"] if c["outcome"] in baseline_red.FAILED and baseline_red._key(c) not in known]
    if not fresh or not doc["base"] or not (ran or ci["junit_steps"]):
        return None
    out = {"rev": doc["base"], "cases": None, "exit": None, "problems": [], "logs": []}
    with baseline_red.temp_tree(root, doc["base"]) as (copy, cant):
        if copy is None:
            out["problems"] = [f"修正前の版 {doc['base']} を写せない（{'；'.join(cant)}）"]
            return out
        cases = []
        if ci["junit_steps"]:
            old = declared_checks.run_ci(copy, test_cmd="", log_dir=log_dir / "base-rev",   # 1 件ごとの結末が要るのは JUnit の段だけ
                                         changed=lambda: scope.changed(root, doc["base"], ()), after_judge=True,
                                         report_dir=place / files.JUNIT_BASE_REV, reuse=None)
            cases += old["cases"]
            out["logs"].append(old["log"])
            out["exit"] = next((r["exit"] for r in old["runs"] if r["name"] in old["junit_steps"] and r["exit"]), 0)
        if ran:
            moved = [str(copy / rel) for rel in (Path(a).relative_to(root.resolve()) for a in extra) if (copy / rel).exists()]
            got, code, problems = baseline_red.run_suite(doc["tdd_suite"], copy, place, "suite-base-rev", args=moved, only=narrow)
            out["logs"].append(str(place / "suite-suite-base-rev.log"))
            if got is None:
                out["problems"] = problems
                return out
            cases += got
            out["exit"] = code
    out["cases"] = cases
    return out


if __name__ == "__main__":
    sys.exit(main())
