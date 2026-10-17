"""merge に要る確かめの名（main の保護が名指す REQUIRED）が、CI（.github/workflows/）の job が出す check の名と合う。
CI の job の名を変えて、main の保護が待つ check が出なくならないように縛る。

check の名は job の name、無ければ job の id。matrix の job は分けごとに名が変わるので、必須の確かめには使えない。
"""
import pathlib
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
REQUIRED = ("tests",)


def check_names(workflow: dict) -> set[str]:
    """matrix を持たない job が出す check の名"""
    return {job.get("name", job_id) for job_id, job in (workflow.get("jobs") or {}).items()
            if "matrix" not in (job.get("strategy") or {})}


def problems(required: tuple[str, ...], workflows: list[dict]) -> list[str]:
    names = set().union(*(check_names(w) for w in workflows))
    return [f"必須の確かめ {name} を出す CI の job が無い" for name in required if name not in names]


class RequiredChecksTest(unittest.TestCase):
    def test_every_required_check_has_a_job(self):
        workflows = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted(WORKFLOWS.glob("*.y*ml"))]
        self.assertEqual(problems(REQUIRED, workflows), [])

    def test_renamed_or_matrix_job_is_not_the_check(self):
        renamed = {"jobs": {"tests": {"name": "unit tests"}}}
        matrix = {"jobs": {"tests": {"strategy": {"matrix": {"shard": [1, 2]}}}}}
        for workflow in (renamed, matrix, {"jobs": {"test": {}}}):
            with self.subTest(workflow=workflow):
                self.assertEqual(problems(("tests",), [workflow]), ["必須の確かめ tests を出す CI の job が無い"])
        self.assertEqual(problems(("tests",), [{"jobs": {"tests": {"needs": "shard"}}}]), [])
