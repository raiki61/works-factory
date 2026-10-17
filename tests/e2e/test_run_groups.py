"""殻が新しい run に渡す群の別名の層（place.run_config の --config）を、止めた Archon の run の記録で照らす。AI の役は走らせない。

Archon は起動の時に解いた別名を run の metadata の ai_configuration に記録し、workflow: の子の run はそれを受け継ぎ、resume は
戻す（AI ノードはこの記録から模型と effort を引く）。だから記録の値が、対象のリポジトリの別名にも利用者の --config の別名にも替わらず
群の表の値かを見る。家は本番と同じく別名を書かない物（archon.archon の aliases=False）で、群の値は --config の層からしか来ない。
"""
import json
import pathlib
import tempfile
import unittest

from bin._lib import place
from tests import archon

GROUP = "@wf-judge-core"
PARENT = """name: works-factory-groups-parent
description: 子の run を 1 本起こす親
nodes:
  - id: kid
    workflow: works-factory-groups-child
"""
CHILD = f"""name: works-factory-groups-child
description: 関所で止まる子。AI の節は走らない
nodes:
  - id: first
    bash: echo first
  - id: gate
    wait:
      attention: 止める
      form: select
      options: [{{ id: approve }}, {{ id: reject }}]
    depends_on: [first]
  - id: after
    bash: echo after
    depends_on: [gate]
  - id: ai
    prompt: 走らない
    model: '{GROUP}'
    depends_on: [after]
    when: "$after.output == 'never'"
"""


class RunGroupsCase(unittest.TestCase):
    def test_target_alias_cannot_replace_the_group_and_children_and_resume_keep_it(self):
        table = place.group_presets()[GROUP]
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp) / "wf"
            for name, text in {"groups-parent": PARENT, "groups-child": CHILD}.items():
                (src / name).mkdir(parents=True)
                (src / name / f"works-factory-{name}.yaml").write_text(text, encoding="utf-8")
            with archon.tree(["groups-parent", "groups-child"], workflows=src) as root:
                (root / ".archon" / "config.yaml").write_text(
                    f"aliases:\n  '{GROUP}': {{provider: claude, model: haiku, effort: low}}\n", encoding="utf-8")
                mine = {"env": {"WF_MINE": "1"}, "aliases": {GROUP: {"provider": "claude", "model": "haiku", "effort": "low"}}}
                argv = place.workflow_run(archon.source(), root, place.run_config(pathlib.Path(tmp), mine), root,
                                          "works-factory-groups-parent", "--no-worktree", "--model", f"{GROUP}=sonnet")
                paused = archon.archon(root, *argv[2:], aliases=False)
                self.assertEqual(paused.returncode, 0, paused.stdout + paused.stderr)
                runs = {r["workflow_name"]: r for r in json.loads(archon.archon(root, "workflow", "runs", "--json", aliases=False).stdout)["runs"]}
                child = runs["works-factory-groups-child"]
                self.assertEqual(child["parent_run_id"], runs["works-factory-groups-parent"]["id"])
                launched = {name: self._ai(root, run["id"]) for name, run in runs.items()}
                approved = archon.archon(root, "workflow", "approve", child["id"], "--json", aliases=False)
                self.assertEqual(approved.returncode, 0, approved.stdout + approved.stderr)
                resumed = archon.archon(root, "workflow", "resume", child["id"], aliases=False)
                self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
                after = self._ai(root, child["id"])
                status = self._get(root, child["id"])["status"]
                sealed = self._get(root, runs["works-factory-groups-parent"]["id"])["metadata"]["run_config"]["keys"]
        named = {"aliases": {GROUP: {"provider": "claude", "model": "sonnet"}}}
        for name, ai in launched.items():
            with self.subTest(name):
                self.assertEqual(ai["baseAiProfile"]["aliases"][GROUP], table)
                self.assertEqual(ai["modelOverrides"], named, "呼ぶ人の名指しは子の run にも届く")
        self.assertEqual(status, "completed")
        self.assertIn("env.WF_MINE", sealed, "利用者の --config の env は run の層に入る")
        self.assertEqual(after, launched["works-factory-groups-child"], "resume は起動の時の記録のまま")

    def _get(self, root, run_id):
        return json.loads(archon.archon(root, "workflow", "get", run_id, "--json", aliases=False).stdout)

    def _ai(self, root, run_id):
        return self._get(root, run_id)["metadata"]["ai_configuration"]


if __name__ == "__main__":
    unittest.main()
