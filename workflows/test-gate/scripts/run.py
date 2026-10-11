# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 run: 走らせる前の指紋を取り、走らせ方を機械で決めて走らせ（declared_checks.run_ci）、tdd_suite が在れば一式を 1 回走らせて
1 件ごとの結末を足し、走らせた後の指紋を取る。結果の全部は test-gate/<mode>/run.json に書き、節の返りは output_format の欄だけ。
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
import declared_checks  # noqa: E402
import green_cert  # noqa: E402
import tree_run  # noqa: E402
from engine import util  # noqa: E402  （accept が lib/graphloops を sys.path に足す）

WORKSPACE_PREFIX = ".archon/"   # Archon が run の作業ツリーに置く物。修正の変更でない
OUTPUT = ("by", "material", "runs", "skipped_steps", "same_as", "log", "junit_steps", "fingerprint_before", "fingerprint_after")


def changed(root: Path, base_rev: str):
    """範囲の宣言と照らす変更（根からのパス）。base_rev から今の作業ツリーまでに触ったファイルから Archon の置き場を除いた物。
    測れない（base_rev が無い・git の誤り・空）なら None（絞らない）"""
    if not base_rev:
        return None
    try:
        files = accept.touched_files(root, base_rev)
    except accept.Reject:
        return None
    return [f for f in files if not f.startswith(WORKSPACE_PREFIX)] or None


def main() -> int:
    mode = os.environ["INPUTS_MODE"]
    if mode not in declared_checks.MODES:
        print(f"mode は {'・'.join(declared_checks.MODES)} のどれか: {mode!r}", file=sys.stderr)
        return 1
    start = json.loads(boundary.resolve(json.loads(os.environ["INPUTS_START"])).read_text(encoding="utf-8"))
    root = Path(util.repo_root() or os.getcwd())
    gate = Path(os.environ["ARTIFACTS_DIR"]) / "test-gate" / mode
    shutil.rmtree(gate, ignore_errors=True)   # 同じ run で同じ形をもう 1 度差し込んだ時に、前の回の素材と拒否を読まない
    gate.mkdir(parents=True)
    base_rev = start.get("base_rev") or ""
    suite = start.get("tdd_suite") or ""
    try:
        before = green_cert.fingerprint(root)
        ci = declared_checks.run_ci(root, test_cmd=start.get("test_cmd") or "", log_dir=gate / "logs",
                                    changed=lambda: changed(root, base_rev), after_judge=mode == "final",
                                    report_dir=gate / "junit")
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
