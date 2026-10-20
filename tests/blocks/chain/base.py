"""chain の block の試験の助け（テストのモジュールではない）。今の tests/e2e/test_line_scenarios.py の bound・scenarios の移し"""
import json
import pathlib

import yaml

from tests.blocks import kit


def line_graph() -> dict:
    """chain が周ごとに起こす line の YAML（workflows/line/。入力の名と既定値だけを照らす）"""
    return yaml.safe_load((kit.BLOCKS / "line" / "works-factory-line.yaml").read_text(encoding="utf-8"))


def scenarios(done) -> dict:
    try:
        report = json.loads(done.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(f"workflow test の返りが読めない（{error}）: {done.stdout}{done.stderr}") from None
    if "results" not in report:
        raise AssertionError(f"workflow test が筋書きを回せない: {json.dumps(report, ensure_ascii=False)}")
    return {pathlib.PurePosixPath(r["fixture"]).name.removesuffix(".stubs.yaml"): r for r in report["results"]}


def bound(trace: dict, value):
    """線の節の with: の 1 つの値を、dry-run の trace の出力で結ぶ（`$<id>.output.<欄>`・まるごとの参照 `$<id>.output` と `{from, if_skipped}`。
    差し込んだブロックの返りは trace に include の id の行が無いので、受け皿 `<id>-out` の got から読む）"""
    if isinstance(value, dict) and "from" in value:
        node = value["from"].split(".", 1)[0].lstrip("$")
        node = node if node in trace else f"{node}-out"   # 差し込んだブロックは受け皿の行で見る
        if node not in trace or trace[node]["state"] == "skipped":
            return value.get("if_skipped")
        value = value["from"]
    if isinstance(value, str) and value.startswith("$") and value.endswith(".output"):
        node = value[1:-len(".output")]
        if node in trace:
            return trace[node].get("output")   # 節の出力の丸ごと（関所の答えの字）
        if f"{node}-out" in trace:   # 差し込んだブロックの返りのまるごと（受け皿の got。飛んだ受け皿は null）
            out = trace[f"{node}-out"].get("output")
            return json.loads(out)["got"] if out else None
    if not (isinstance(value, str) and value.startswith("$") and ".output." in value):
        return value
    node, field = value[1:].split(".output.", 1)
    if node in trace:
        return json.loads(trace[node]["output"]).get(field)
    return (json.loads(trace[f"{node}-out"]["output"])["got"] or {}).get(field)
