# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 prep（形 ""）: 入力を置き場に写し、git が無視するファイルを控え（p1.worktree_before）、始めの木を取り、組を作る（lanekit.groups）。

置き場（fixio.place() = $ARTIFACTS_DIR/fix/<include の名>/）に書く物: r1/start.json（始めの記録の写し。欠けた欄は既定）・
judgment.json・plan-fields.json と凍結の印（planmarks.save）・p2.fix_plan.json（修正案の隣に在れば）・ripple.json・world.json・
depth.json・answers.json・units.json・only-items.json・baseline.json（{cases, exit}）・fix-ignored-before.json・human-notes.md（関所の一言と答えで戻った単位の行。
無ければ書かない）・base-rev.json
（修正前の版。親の HEAD の sha。組の子が写して受け付けの起点にする）・groups.json
（返りと同じ物）。組の子が結果を書く out_dir（置き場の groups/）も作る。
返り {groups: [{group_id, unit_ids, items}], count, par, start_tree, out_dir}。入力が読めない・git が効かない: 標準エラーに 1 行で 1。
"""
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))
import fixio  # noqa: E402

import baseline_red  # noqa: E402
import fixboard  # noqa: E402
import groups  # noqa: E402
import leftovers  # noqa: E402
import planmarks  # noqa: E402
import startrec  # noqa: E402

START_DEFAULTS = {"tdd_suite": "", "test_cmd": "", "policy_md": "", "request_file": "", "features_cut": []}


def value(raw: str, name: str):
    """入力の字を JSON で読む（空・null は None）"""
    if not (raw or "").strip() or raw.strip() == "null":
        return None
    try:
        return json.loads(raw)
    except ValueError as e:
        raise ValueError(f"入力 {name} が JSON として読めない: {e}（頭: {raw[:120]!r}）") from None


def pointed(raw: str, name: str):
    """入力の指し札の先のパス（空・null は None）"""
    ptr = value(raw, name)
    return None if ptr is None else boundary.resolve(ptr)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> dict:
    place = fixio.place()
    repo = fixio.repo()
    start = read_json(pointed(os.environ["INPUTS_START"], "start"))
    if not isinstance(start, dict):
        raise ValueError("始めの記録が JSON のオブジェクトでない")
    start = {**START_DEFAULTS, **{k: v for k, v in start.items() if v is not None}}
    fixboard.write_json(startrec.path(place), start)
    judgment = read_json(pointed(os.environ["INPUTS_JUDGMENT"], "judgment"))
    fixboard.write_json(place / fixboard.JUDGMENT_FILE, judgment)

    plan_file = pointed(os.environ.get("INPUTS_PLAN", ""), "plan")
    plan = None
    if plan_file is not None:
        doc = read_json(plan_file)
        if not isinstance(doc, dict) or not isinstance(doc.get("fields"), list):
            raise ValueError(f"修正案の欄 {plan_file.name} の形が違う（{{round, fields}}）")
        amended = doc.get(planmarks.AMENDED_KEY)
        planmarks.save(place, 1, doc["fields"], {int(n): c for n, c in amended.items()} if isinstance(amended, dict) else None)
        reply = plan_file.parent / fixboard.PLAN_REPLY_FILE
        if reply.is_file():
            plan = read_json(reply)
            fixboard.write_json(place / fixboard.PLAN_REPLY_FILE, plan)
    for name, file in (("ripple", fixboard.RIPPLE_FILE), ("world", fixboard.WORLD_FILE)):
        src = pointed(os.environ.get(f"INPUTS_{name.upper()}", ""), name)
        if src is not None:
            fixboard.write_json(place / file, read_json(src))
    for name, file in (("depth", fixboard.DEPTH_FILE), ("answers", fixboard.ANSWERS_FILE), ("units", fixboard.UNITS_FILE)):
        got = value(os.environ.get(f"INPUTS_{name.upper()}", ""), name)
        if got not in (None, "", [], {}) or name == "units":
            fixboard.write_json(place / file, got if got is not None else [])
    only = value(os.environ.get("INPUTS_ONLY_ITEMS", ""), "only_items") or []
    if not isinstance(only, list):
        raise ValueError("入力 only_items が配列でない")
    fixboard.write_json(place / fixboard.ONLY_ITEMS_FILE, only)
    base = pointed(os.environ.get("INPUTS_BASELINE", ""), "baseline")
    if base is not None:
        got = baseline_red.read_baseline(base)
        fixboard.write_json(place / fixboard.BASELINE_FILE, {"cases": got["cases"], "exit": got["exit"]})

    leftovers.record_ignored(place, repo)
    fixboard.record_base_rev(place, repo)
    start_tree = groups.end_tree(repo)
    items = planmarks.approved_items(fixboard.plan_view(place, plan, judgment)) if plan is not None else None
    fixboard.write_notes(place)
    grps = fixboard.fix_groups(fixboard.group_owed(place), items, only)
    out_dir = place / "groups"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = {"groups": grps, "count": len(grps), "par": fixboard.parallel(grps, start.get("features_cut"), repo),
           "start_tree": start_tree, "out_dir": str(out_dir)}
    fixboard.write_json(place / fixboard.GROUPS_FILE, out)
    return out


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:   # 回す側の誤り（入力が読めない・置き場が無い・git が効かない）
        print(f"prep: {type(e).__name__}: {' '.join(str(e).split())}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(result)
