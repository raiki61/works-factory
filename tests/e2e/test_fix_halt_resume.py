"""#576・#594: 修正のサブグラフの節が落ちた時、メイングラフの後ろが走らずに run が failed で止まり、親の resume で落ちた節から
続きが回ることを、止めた Archon で照らす。

fix ブロックの配線（組の節の fan_out の join・join の節と柵 nodes-ok と落ちの後ろの節の trigger_rule）を works-factory-fix.yaml
から、修正の後ろの節 fixed の trigger_rule を works-factory-line.yaml から読んで、AI の無い bash の節の使い捨ての工程に組む。
- 組の子: 子 → 組の節 → join → 柵・落ちの後ろの節 → 返す節 all_done → メイングラフの後ろ。子は項目 b の 1 回目だけ落ちる
  （使用枠の切れの代わり）
- 組でない節: prep → 1 回目だけ落ちる節 step（裁定や審査のループの代わり）→ 落ちの後ろの節 → 柵 → 返す節 all_done →
  メイングラフの後ろと fixed
"""
import json
import pathlib
import tempfile
import unittest

import yaml

from tests import archon

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIX_YAML = ROOT / "workflows" / "fix" / "works-factory-fix.yaml"
LINE_YAML = ROOT / "workflows" / "line" / "works-factory-line.yaml"

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
  - id: nodes-ok
    bash: "true"
    depends_on: [prep, groups-seq, join]
    trigger_rule: {guard_rule}
    timeout: 600000
    mutates_checkout: false
  - id: assert-changed
    bash: echo checked
    depends_on: [prep, join]
    trigger_rule: {chain_rule}
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

STEP_BLOCK = """name: works-factory-step-block
description: fix ブロックの組でない節の配線の写し
returns: fix
nodes:
  - id: prep
    bash: echo run >> {mark}/prep-count
    timeout: 600000
    mutates_checkout: false
  - id: step
    bash: |
      if [ ! -f {mark}/step ]; then touch {mark}/step; echo boom >&2; exit 3; fi
      echo stepped
    depends_on: [prep]
    timeout: 600000
    mutates_checkout: false
  - id: clean
    bash: echo cleaned
    depends_on: [prep, step]
    trigger_rule: {chain_rule}
    timeout: 600000
    mutates_checkout: false
  - id: assert-changed
    bash: echo checked
    depends_on: [prep, clean]
    trigger_rule: {chain_rule}
    timeout: 600000
    mutates_checkout: false
  - id: nodes-ok
    bash: "true"
    depends_on: [prep, step, clean, assert-changed]
    trigger_rule: {guard_rule}
    timeout: 600000
    mutates_checkout: false
  - id: fix
    bash: echo collect
    depends_on: [prep, step, clean, assert-changed]
    trigger_rule: all_done
    timeout: 600000
    mutates_checkout: false
"""

STEP_LINE = """name: works-factory-step-line
description: メイングラフの写し
nodes:
  - id: fixstage
    include: works-factory-step-block
  - id: after-fix
    bash: echo after-fix
    depends_on: [fixstage]
    timeout: 600000
    mutates_checkout: false
  - id: fixed
    bash: echo fixed
    depends_on: [after-fix, fixstage]
    trigger_rule: {fixed_rule}
    timeout: 600000
    mutates_checkout: false
"""


def wiring() -> dict:
    nodes = {n["id"]: n for n in yaml.safe_load(FIX_YAML.read_text(encoding="utf-8"))["nodes"]}
    fan_joins = {nodes[nid]["fan_out"]["join"] for nid in ("groups-par", "groups-seq")}
    assert len(fan_joins) == 1, fan_joins
    chain = {nodes[nid]["trigger_rule"] for nid in ("clean", "assert-changed", "delta-cut")}
    assert len(chain) == 1, chain
    line = {n["id"]: n for n in yaml.safe_load(LINE_YAML.read_text(encoding="utf-8"))["nodes"]}
    return {"fan_join": fan_joins.pop(), "join_rule": nodes["join"]["trigger_rule"],
            "guard_rule": nodes["nodes-ok"]["trigger_rule"], "chain_rule": chain.pop(),
            "fixed_rule": line["fixed"]["trigger_rule"]}


class FixHaltResumeCase(unittest.TestCase):
    def test_failed_child_halts_the_line_and_resume_continues_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, _ = self._place(tmp, {"halt-child": CHILD, "halt-block": BLOCK, "halt-line": LINE})
            with archon.tree(["halt-child", "halt-block", "halt-line"], workflows=src) as root:
                first, again, parent = self._run_and_resume(root, "works-factory-halt-line")
                children = [r["status"] for r in json.loads(archon.archon(root, "workflow", "runs", "--json").stdout)["runs"]
                            if r["workflow_name"] == "works-factory-halt-child"]
        self.assertIn(("node_failed", "fixstage__groups-seq"), first)
        for skipped in ("fixstage__join", "fixstage__nodes-ok", "fixstage__assert-changed", "after-fix"):
            self.assertIn(("node_skipped", skipped), first)
        self.assertNotIn(("node_completed", "after-fix"), first)
        self.assertEqual(parent["status"], "completed")
        self.assertEqual(children, ["completed", "completed"], "落ちた子を新しく起こさず、同じ run で続きから回した")
        for ran in ("fixstage__groups-seq", "fixstage__join", "fixstage__nodes-ok", "fixstage__assert-changed", "after-fix"):
            self.assertIn(("node_completed", ran), again)

    def test_failed_node_outside_the_groups_halts_the_line_and_resume_continues_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, mark = self._place(tmp, {"step-block": STEP_BLOCK, "step-line": STEP_LINE})
            with archon.tree(["step-block", "step-line"], workflows=src) as root:
                first, again, parent = self._run_and_resume(root, "works-factory-step-line")
            prep_runs = (mark / "prep-count").read_text(encoding="utf-8").splitlines()
        self.assertIn(("node_failed", "fixstage__step"), first)
        for skipped in ("fixstage__clean", "fixstage__assert-changed", "fixstage__nodes-ok", "after-fix", "fixed"):
            self.assertIn(("node_skipped", skipped), first)
        self.assertIn(("node_completed", "fixstage__fix"), first, "返す節は落ちの後も走る")
        self.assertEqual(parent["status"], "completed")
        for ran in ("fixstage__step", "fixstage__clean", "fixstage__assert-changed", "fixstage__nodes-ok", "after-fix", "fixed"):
            self.assertIn(("node_completed", ran), again)
        self.assertEqual(len(prep_runs), 1, "resume は落ちた節から続け、済んだ節を走らせ直さない")

    def _place(self, tmp, files):
        mark = pathlib.Path(tmp) / "marks"
        mark.mkdir()
        src = pathlib.Path(tmp) / "wf"
        for name, text in files.items():
            body = text.replace("{mark}", str(mark))
            for key, value in wiring().items():
                body = body.replace("{" + key + "}", value)
            (src / name).mkdir(parents=True)
            (src / name / f"works-factory-{name}.yaml").write_text(body, encoding="utf-8")
        return src, mark

    def _run_and_resume(self, root, line):
        """line を走らせて failed で止まるのを確かめ、resume する。返り (1 回目の節の出来事, resume の節の出来事, 親の run)"""
        archon.archon(root, "workflow", "run", line, "--no-worktree")
        parent, first = self._parent(root, line)
        self.assertEqual(parent["status"], "failed")
        resumed = archon.archon(root, "workflow", "resume", parent["id"])
        self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
        parent, both = self._parent(root, line)
        return first, both[len(first):], parent

    def _parent(self, root, line):
        runs = json.loads(archon.archon(root, "workflow", "runs", "--json").stdout)["runs"]
        parent = next(r for r in runs if r["workflow_name"] == line)
        detail = json.loads(archon.archon(root, "workflow", "get", parent["id"], "--json", "--verbose", "--events").stdout)
        return parent, [(e["event_type"], e["step_name"]) for e in detail["events"]
                        if e["event_type"].startswith("node_") and e["step_name"] and "." not in e["step_name"]]


if __name__ == "__main__":
    unittest.main()
