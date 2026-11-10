"""chain の block の試験の助け（テストのモジュールではない）。元の test_line_scenarios.py の bound・scenarios の移し"""
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


def _traced(trace: dict, node: str) -> str:
    """with: が名指す chain の節の trace の行の id。include の節は trace に行が無いので、差し込んだ block の返す節
    `<include の id>__<returns:>`（Archon が `$<include>.output` を解く先）"""
    if node in trace:
        return node
    top = {n["id"]: n for n in yaml.safe_load((kit.BLOCKS / "chain" / "works-factory-chain.yaml").read_text(encoding="utf-8"))["nodes"]}
    inner = str(top.get(node, {}).get("include", "")).removeprefix("works-factory-")
    if not inner:
        return node
    doc = yaml.safe_load((kit.BLOCKS / inner / f"works-factory-{inner}.yaml").read_text(encoding="utf-8"))
    return f"{node}__{doc['returns']}"


def bound(trace: dict, value):
    """線の節の with: の 1 つの値を、dry-run の trace の出力で結ぶ（`$<id>.output.<欄>`・まるごとの参照 `$<id>.output` と `{from, if_skipped}`。
    差し込んだブロックの返りは trace に include の id の行が無いので、返す節の行から読む）"""
    if isinstance(value, dict) and "from" in value:
        node = _traced(trace, value["from"].split(".", 1)[0].lstrip("$"))
        if node not in trace or trace[node]["state"] == "skipped":
            return value.get("if_skipped")
        value = value["from"]
    if isinstance(value, str) and value.startswith("$") and value.endswith(".output"):
        node = _traced(trace, value[1:-len(".output")])
        return trace[node].get("output") if node in trace else None   # 節の出力の丸ごと（関所の答えの字）
    if not (isinstance(value, str) and value.startswith("$") and ".output." in value):
        return value
    node, field = value[1:].split(".output.", 1)
    return json.loads(trace[_traced(trace, node)]["output"]).get(field)
