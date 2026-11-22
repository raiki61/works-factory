"""Archon の待ち方の模型（試験の助け。試験のモジュールではない）。tests/workflows と tests/blocks/line の 2 か所以上の試験が使うので tests/bin/ に置く（tests/AGENTS.md）。"""


def would_run(n: dict, states: dict) -> bool:
    """節 n が待つ節（depends_on）の状態 states から、trigger_rule の決まりで走るか。状態は completed・failed・skipped（when などで飛んだ）・
    skipped_after_failure（前が落ちたので飛んだ）。決まりは Archon の待ち方（packages/workflows/src/dag/trigger-rule.ts の all_success・
    one_success・none_failed_min_one_success・all_done）と同じ"""
    upstream = [states[dep] for dep in n["depends_on"]]
    failed = [s for s in upstream if s in ("failed", "skipped_after_failure")]
    done = [s for s in upstream if s == "completed"]
    rule = n.get("trigger_rule") or "all_success"
    if rule == "all_success":
        return len(done) == len(upstream)
    if rule == "one_success":
        return bool(done)
    if rule == "none_failed_min_one_success":
        return not failed and bool(done)
    if rule == "all_done":
        return True
    raise AssertionError(f"知らない待ち方 {rule}")
