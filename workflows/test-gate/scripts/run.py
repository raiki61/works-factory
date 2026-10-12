# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 run: 走らせる前の指紋を取り、走らせ方を機械で決めて走らせ（declared_checks.run_ci）、tdd_suite が在れば一式を 1 回走らせて
1 件ごとの結末を足し、走らせた後の指紋を取る。結果の全部は test-gate/<mode>/run.json に書き、節の返りは output_format の欄だけ。
base は同じ run の中の試験の結果の控え（run の置き場の直下の tree_run.REUSE_SUB。run の名は始めの記録の run_id）を引いて置く。
fix の TDD の輪の頭が同じ控えを引く。final は引かず置かない（最後のテストは省かない）。旗 tree_run.RERUN_ENV が立てば引かない。
テストを起こす前に Archon の変数を落とす（対象のテストに継がせず、節ごとに違う値で控えの指紋を割らない）。
止められたら木を止め終えてから返りを出さずに 128+信号で抜ける。走らせられない（範囲の宣言の誤りなど）は 1 で、理由を標準エラーに 1 行"""
import json
import os
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))

import accept  # noqa: E402
import baseline_red  # noqa: E402
import carry  # noqa: E402
import checkscope  # noqa: E402
import declared_checks  # noqa: E402
import green_cert  # noqa: E402
import tree_run  # noqa: E402
from engine import util  # noqa: E402  （accept が lib/graphloops を sys.path に足す）

LOGS = "logs"
WORKSPACE_PREFIX = ".archon/"   # Archon が run の作業ツリーに置く物。修正の変更でない
OUTPUT = ("by", "material", "runs", "skipped_steps", "same_as", "log", "junit_steps", "fingerprint_before", "fingerprint_after")


def changed(root: Path, base_rev: str, wheres=()):
    """範囲の宣言と照らす変更（根からのパス）。base_rev から今の作業ツリーまでに触ったファイルと、依頼の where が名指す追跡中の
    パス（wheres。request_wheres）の和から Archon の置き場を除いた物。測れない（git の誤り・空）なら None（絞らない）"""
    files = set(checkscope.request_files(root, wheres))
    if base_rev:
        try:
            files |= set(accept.touched_files(root, base_rev))
        except accept.Reject:
            return None
    return sorted(f for f in files if not f.startswith(WORKSPACE_PREFIX)) or None


def request_wheres(start: dict, mode: str) -> list:
    """判定から入る run（入口の差分が空）の base で、依頼の行の where の並び。修正の前の入口の確かめは、変更を依頼が名指す所で
    決める（修正が where の外へ広がれば final がその変更で照らす）。差分の在る入口・final・依頼が無いか読めない時は []（足さない）"""
    if mode != "base" or not ((start.get("input") or {}).get("diff") or {}).get("empty") or not start.get("request_file"):
        return []
    try:
        findings = carry.parts(json.loads(Path(start["request_file"]).read_text(encoding="utf-8")))[carry.FINDINGS]
    except (OSError, UnicodeDecodeError, ValueError):
        return []
    return [f["where"] for f in findings if isinstance(f, dict) and isinstance(f.get("where"), str)]


def fresh_gate(gate: Path) -> Path:
    """同じ run で同じ形をもう 1 度差し込んだ時に、前の回の素材・拒否・記録を読まないよう gate の中を logs/ のほかは消し、今回のログの
    置き場 logs/a<k>/（k は空いた最初の番号。前の走りのログを上書きしない）を返す（元 works/.shared/core/board.py:1404 _log_dir）"""
    gate.mkdir(parents=True, exist_ok=True)
    for path in gate.iterdir():
        if path.name == LOGS:
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
    k = 1
    while (gate / LOGS / f"a{k}").exists():
        k += 1
    return gate / LOGS / f"a{k}"


def main() -> int:
    mode = os.environ["INPUTS_MODE"]
    if mode not in declared_checks.MODES:
        print(f"mode は {'・'.join(declared_checks.MODES)} のどれか: {mode!r}", file=sys.stderr)
        return 1
    start = json.loads(boundary.resolve(json.loads(os.environ["INPUTS_START"])).read_text(encoding="utf-8"))
    root = Path(util.repo_root() or os.getcwd())
    artifacts = Path(os.environ["ARTIFACTS_DIR"])
    gate = artifacts / "test-gate" / mode
    log_dir = fresh_gate(gate)
    reuse = (tree_run.reuse_place(artifacts, start.get("run_id") or "", rerun=bool(os.environ.get(tree_run.RERUN_ENV)))
             if mode == "base" else None)
    boundary.drop_runner_env()
    base_rev = start.get("base_rev") or ""
    suite = start.get("tdd_suite") or ""
    wheres = request_wheres(start, mode)
    try:
        before = green_cert.fingerprint(root)
        ci = declared_checks.run_ci(root, test_cmd=start.get("test_cmd") or "", log_dir=log_dir,
                                    changed=lambda: changed(root, base_rev, wheres), after_judge=mode == "final",
                                    report_dir=gate / "junit", reuse=reuse)
        ran = None
        if suite:
            cases, code, problems = baseline_red.run_suite(suite, root, gate, "suite")
            ran = {"exe": suite, "exit": code, "problems": problems}
            ci["cases"] += cases or []
        after = green_cert.fingerprint(root)
    except tree_run.Stopped as e:
        print(f"止められた（信号 {e.signum}）。テストは木ごと止めた", file=sys.stderr)
        return 128 + e.signum
    except (declared_checks.CiRefused, ValueError) as e:
        print(f"テストを走らせられない: {e}", file=sys.stderr)
        return 1
    doc = {"mode": mode, "base_rev": base_rev, **ci, "suite": ran, "fingerprint_before": before, "fingerprint_after": after}
    (gate / "run.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    boundary.returns({k: doc[k] for k in OUTPUT})
    return 0


if __name__ == "__main__":
    sys.exit(main())
