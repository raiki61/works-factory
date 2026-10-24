"""殻が新しい run のノードに渡す環境変数（launcher.run_env を place.run_config の --config の env: に載せた物）が、止めた Archon の
新しい run・workflow: の子の run・resume の 3 つの道で bash のノードに届くことを照らす。AI の役は走らせない。

家は本番と同じく何も書かない物（archon.archon の aliases=False）。起こす Archon の環境の WORKS_FACTORY_ROOT は古い値にし、答えの行の頭
（lib/answer.ENV）は置かない（hermetic が外す）ので、ノードが見る値は --config の層からしか来ない。
"""
import json
import pathlib
import tempfile
import unittest

from bin._lib import launcher, place
from lib import answer
from tests import archon

NAMES = ("WORKS_FACTORY_ROOT", answer.ENV)


def seen(node: str, out: pathlib.Path) -> str:
    """ノード node が見た NAMES の値を out/<node>.json に書く bash のノード"""
    pairs = ", ".join(f'"{name}": "${name}"' for name in NAMES)
    return f"""  - id: {node}
    bash: |
      cat > '{out / node}.json' <<EOF
      {{{pairs}}}
      EOF
"""


def parent(out: pathlib.Path) -> str:
    return f"""name: works-factory-env-parent
description: 値を控えてから子の run を 1 本起こす親
nodes:
{seen("fresh", out)}  - id: kid
    workflow: works-factory-env-child
    depends_on: [fresh]
"""


def child(out: pathlib.Path) -> str:
    return f"""name: works-factory-env-child
description: 値を控えて関所で止まり、resume の後にもう一度控える子
nodes:
{seen("child", out)}  - id: gate
    wait:
      attention: 止める
      form: select
      options: [{{ id: approve }}, {{ id: reject }}]
    depends_on: [child]
{seen("resumed", out)}    depends_on: [gate]
"""


class RunEnvCase(unittest.TestCase):
    def test_run_env_reaches_nodes_of_fresh_child_and_resumed_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            out = tmp / "seen"
            out.mkdir()
            src = tmp / "wf"
            for name, text in {"env-parent": parent(out), "env-child": child(out)}.items():
                (src / name).mkdir(parents=True)
                (src / name / f"works-factory-{name}.yaml").write_text(text, encoding="utf-8")
            with archon.tree(["env-parent", "env-child"], workflows=src) as root:
                env = launcher.run_env(tmp / "home", root)
                stale = {"WORKS_FACTORY_ROOT": str(tmp / "stale")}
                argv = place.workflow_run(archon.source(), root, place.run_config(tmp, env), root,
                                          "works-factory-env-parent", "--no-worktree")
                paused = archon.archon(root, *argv[2:], aliases=False, **stale)
                self.assertEqual(paused.returncode, 0, paused.stdout + paused.stderr)
                runs = {r["workflow_name"]: r for r in
                        json.loads(archon.archon(root, "workflow", "runs", "--json", aliases=False, **stale).stdout)["runs"]}
                kid = runs["works-factory-env-child"]["id"]
                for step in (["approve", kid, "--json"], ["resume", kid]):
                    done = archon.archon(root, "workflow", *step, aliases=False, **stale)
                    self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                sealed = json.loads(archon.archon(root, "workflow", "get", runs["works-factory-env-parent"]["id"], "--json",
                                                  aliases=False, **stale).stdout)["metadata"]["run_config"]["keys"]
            got = {node: json.loads((out / f"{node}.json").read_text(encoding="utf-8"))
                   for node in ("fresh", "child", "resumed") if (out / f"{node}.json").exists()}
        self.assertEqual(env["WORKS_FACTORY_ROOT"], str(launcher.ROOT))
        for node in ("fresh", "child", "resumed"):
            with self.subTest(node):
                self.assertTrue(got.get(node) == env)
        self.assertIn("workflows.autoResumeOnQuotaReset", sealed, "使用枠の方針も同じ層で封じる")


if __name__ == "__main__":
    unittest.main()
