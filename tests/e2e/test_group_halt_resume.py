"""#576: 修正の組の子の run が落ちた時、親の組の節が落ちてメイングラフを止め、親の resume で落ちた子が続きから回ることを、止めた
Archon で照らす。

fix ブロックの組の配線（組の節の fan_out の join・join の節と柵 groups-ok の trigger_rule）を works-factory-fix.yaml から読んで、AI
の無い bash の節の使い捨ての工程（子 → 組の節 → join → 柵・join を結ぶ all_done の節 → 返す節 all_done → メイングラフの後ろ）に
組む。子は項目 b の 1 回目だけ落ちる（使用枠の切れの代わり）。
"""
import json
import pathlib
import tempfile
import unittest

import yaml

from tests import archon

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIX_YAML = ROOT / "workflows" / "fix" / "works-factory-fix.yaml"

CHILD = """name: works-factory-halt-child
description: 項目 b の 1 回目だけ落ちる子
nodes:
  - id: work
    bash: |
      if [ "$ARGUMENTS" = "b" ] && [ ! -f {mark}/child-b ]; then touch {mark}/child-b; echo boom >&2; exit 3; fi
      echo "ok:$ARGUMENTS"
    timeout: 600000
    mutates_checkout: false
"""

BLOCK = """name: works-factory-halt-block
description: fix ブロックの組の配線の写し
returns: fix
nodes:
  - id: prep
    bash: printf '%s' '["a","b"]'
    timeout: 600000
    mutates_checkout: false
  - id: groups-seq
    workflow: works-factory-halt-child
    depends_on: [prep]
    fan_out:
      items: $prep.output
      max_parallel: 1
      join: {fan_join}
  - id: join
    bash: echo joined
    depends_on: [prep, groups-seq]
    trigger_rule: {join_rule}
    timeout: 600000
    mutates_checkout: false
  - id: groups-ok
    bash: "true"
    depends_on: [prep, groups-seq, join]
    trigger_rule: {guard_rule}
    timeout: 600000
    mutates_checkout: false
  - id: assert-changed
    bash: echo checked
    depends_on: [prep, join]
    trigger_rule: all_done
    timeout: 600000
    mutates_checkout: false
  - id: fix
    bash: echo collect
    depends_on: [prep, groups-seq, join, assert-changed]
    trigger_rule: all_done
    timeout: 600000
    mutates_checkout: false
"""

LINE = """name: works-factory-halt-line
description: メイングラフの写し
nodes:
  - id: fixstage
    include: works-factory-halt-block
  - id: after-fix
    bash: echo after-fix
    depends_on: [fixstage]
    timeout: 600000
    mutates_checkout: false
"""


def wiring() -> dict:
    nodes = {n["id"]: n for n in yaml.safe_load(FIX_YAML.read_text(encoding="utf-8"))["nodes"]}
    fan_joins = {nodes[nid]["fan_out"]["join"] for nid in ("groups-par", "groups-seq")}
    assert len(fan_joins) == 1, fan_joins
    return {"fan_join": fan_joins.pop(), "join_rule": nodes["join"]["trigger_rule"],
            "guard_rule": nodes["groups-ok"]["trigger_rule"]}


class GroupHaltResumeCase(unittest.TestCase):
    def test_failed_child_halts_the_line_and_resume_continues_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            mark = pathlib.Path(tmp) / "marks"
            mark.mkdir()
            src = pathlib.Path(tmp) / "wf"
            for name, text in (("halt-child", CHILD), ("halt-block", BLOCK), ("halt-line", LINE)):
                body = text.replace("{mark}", str(mark))
                for key, value in wiring().items():
                    body = body.replace("{" + key + "}", value)
                (src / name).mkdir(parents=True)
                (src / name / f"works-factory-{name}.yaml").write_text(body, encoding="utf-8")
            with archon.tree(["halt-child", "halt-block", "halt-line"], workflows=src) as root:
                archon.archon(root, "workflow", "run", "works-factory-halt-line", "--no-worktree")
                parent, first = self._parent(root)
                self.assertEqual(parent["status"], "failed")
                resumed = archon.archon(root, "workflow", "resume", parent["id"])
                self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
                parent, both = self._parent(root)
                children = [r["status"] for r in json.loads(archon.archon(root, "workflow", "runs", "--json").stdout)["runs"]
                            if r["workflow_name"] == "works-factory-halt-child"]
        self.assertIn(("node_failed", "fixstage__groups-seq"), first)
        for skipped in ("fixstage__join", "fixstage__groups-ok", "after-fix"):
            self.assertIn(("node_skipped", skipped), first)
        self.assertNotIn(("node_completed", "after-fix"), first)
        self.assertEqual(parent["status"], "completed")
        self.assertEqual(children, ["completed", "completed"], "落ちた子を新しく起こさず、同じ run で続きから回した")
        again = both[len(first):]
        for ran in ("fixstage__groups-seq", "fixstage__join", "fixstage__groups-ok", "after-fix"):
            self.assertIn(("node_completed", ran), again)
        self.assertIn(("node_prior_cache_invalidated", "fixstage__assert-changed"), again)

    def _parent(self, root):
        runs = json.loads(archon.archon(root, "workflow", "runs", "--json").stdout)["runs"]
        parent = next(r for r in runs if r["workflow_name"] == "works-factory-halt-line")
        detail = json.loads(archon.archon(root, "workflow", "get", parent["id"], "--json", "--verbose", "--events").stdout)
        return parent, [(e["event_type"], e["step_name"]) for e in detail["events"]
                        if e["event_type"].startswith("node_") and e["step_name"] and "." not in e["step_name"]]


if __name__ == "__main__":
    unittest.main()
