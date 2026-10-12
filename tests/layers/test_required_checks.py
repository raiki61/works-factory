"""merge に要る確かめの名（harness/harness.config.json の required_checks）が、CI（.github/workflows/）の job が出す check の名と
合う。食い違えば merge queue が待つ必須の確かめが永遠に来ない（または別の名を待つ）。

check の名は job の name、無ければ job の id。matrix の job は分けごとに名が変わるので、必須の確かめには使えない。
"""
import json
import pathlib
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONFIG = ROOT / "harness" / "harness.config.json"
WORKFLOWS = ROOT / ".github" / "workflows"


def required_checks(config: dict) -> list[str]:
    value = config["required_checks"].strip()
    return [] if value == "none" else [name.strip() for name in value.split(",") if name.strip()]


def check_names(workflow: dict) -> set[str]:
    """matrix を持たない job が出す check の名"""
    return {job.get("name", job_id) for job_id, job in (workflow.get("jobs") or {}).items()
            if "matrix" not in (job.get("strategy") or {})}


def problems(required: list[str], workflows: list[dict]) -> list[str]:
    names = set().union(*(check_names(w) for w in workflows))
    return [f"必須の確かめ {name} を出す CI の job が無い" for name in required if name not in names]


class RequiredChecksTest(unittest.TestCase):
    def test_every_required_check_has_a_job(self):
        required = required_checks(json.loads(CONFIG.read_text(encoding="utf-8")))
        self.assertTrue(required, "required_checks が空か none")
        workflows = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted(WORKFLOWS.glob("*.y*ml"))]
        self.assertEqual(problems(required, workflows), [])

    def test_renamed_or_matrix_job_is_not_the_check(self):
        renamed = {"jobs": {"tests": {"name": "unit tests"}}}
        matrix = {"jobs": {"tests": {"strategy": {"matrix": {"shard": [1, 2]}}}}}
        for workflow in (renamed, matrix, {"jobs": {"test": {}}}):
            with self.subTest(workflow=workflow):
                self.assertEqual(problems(["tests"], [workflow]), ["必須の確かめ tests を出す CI の job が無い"])
        self.assertEqual(problems(["tests"], [{"jobs": {"tests": {"needs": "shard"}}}]), [])
        self.assertEqual(required_checks({"required_checks": "none"}), [])
