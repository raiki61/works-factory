# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 tdd-unit（形 ""・output_type: tdd-unit）: 子の結果から、組ごとの TDD の輪の結果を 1 つの型つきの成果物にして出す（子の run の
型つきの成果物は子の run の物で親の一覧に載らないので、親の節で出す）。

本文は [{group_id, ran, reason, suite, reused, units: [...]}]（tddloop.exit_fields の形。実行器の無い組・結果の無い組は ran: false・
units: []）。同じ物を置き場の tdd-unit.json にも書き、標準出力に出す。置き場の groups.json が無い・読めない: 標準エラーに 1 行で 1。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))

import fixboard  # noqa: E402


def result_of(out_dir: Path, gid: str):
    try:
        doc = fixboard.read_json(out_dir / gid / fixboard.RESULT_FILE)
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def main() -> list:
    place = boundary.place("fix")
    plan = fixboard.read_json(place / fixboard.GROUPS_FILE)
    if not isinstance(plan, dict) or not isinstance(plan.get("groups"), list):
        raise ValueError(f"置き場に groups.json が無いか形が違う（{place}）")
    out_dir = Path(plan["out_dir"])
    body = fixboard.tdd_units(plan["groups"], {g["group_id"]: result_of(out_dir, g["group_id"]) for g in plan["groups"]})
    fixboard.write_json(place / "tdd-unit.json", body)
    return body


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:
        print(f"tdd-unit: {type(e).__name__}: {' '.join(str(e).split())}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(result)
