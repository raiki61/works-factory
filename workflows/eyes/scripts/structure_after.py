"""直した後の構造を、始めの版から今の作業ツリーまでの差分で測り、置き場の eyes/structure-after.json に書く。
測れなくても節は落とさず status: failed と理由を返す（線を止めない）"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import planmarks  # noqa: E402
import stage_b  # noqa: E402
import structmark  # noqa: E402

RUNTIME_COPY = ".archon/"   # 作業ツリーの中の実行基盤の写しは差分に数えない

after, devs, problems = {}, [], []
try:
    start_ptr = json.loads(os.environ["INPUTS_START"])
    start = json.loads(boundary.resolve(start_ptr).read_text(encoding="utf-8")) if start_ptr else {}
    after = stage_b.run(Path.cwd(), start.get("base_rev") or "", skip_prefix=RUNTIME_COPY)
    if after["status"] != "ok":
        problems.append(after["reason"])
except Exception as e:  # noqa: BLE001  測れない訳はどれも理由に残して進む
    problems.append(f"直しの後の実測が落ちた: {e}")
try:
    plan_ptr = json.loads(os.environ["INPUTS_PLAN"])
    plan = json.loads(boundary.resolve(plan_ptr).read_text(encoding="utf-8")) if plan_ptr else {}
    devs = planmarks.deviations(plan.get("fields"))
except Exception as e:  # noqa: BLE001
    problems.append(f"修正案の外れの訳が読めない: {e}")

eyes = Path(os.environ["ARTIFACTS_DIR"]) / "eyes"
eyes.mkdir(parents=True, exist_ok=True)
status, reason = ("failed", " / ".join(problems)) if problems else ("ok", "")
structmark.write_after(eyes, status=status, reason=reason, after=after, deviations=devs)
boundary.returns({"after": boundary.pointer(f"eyes/{structmark.AFTER_FILE}"), "status": status, "reason": reason})
