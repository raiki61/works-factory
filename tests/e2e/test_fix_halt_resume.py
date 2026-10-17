"""#576・#594: 修正のサブグラフの節が落ちた時、メイングラフの後ろが走らずに run が failed で止まり、親の resume で落ちた節から
続きが回ることを、止めた Archon で照らす。

fix ブロックの配線（組の節の fan_out の join・join の節と柵 nodes-ok と落ちの後ろの節の trigger_rule・レンズの段の結び）を
works-factory-fix.yaml から（受け止める段の宣言も、返す節 fix の with: の optional から）、修正の後ろの節 fixed の trigger_rule を works-factory-line.yaml から読んで、
AI の無い節の使い捨ての工程に組む。写しの柵 nodes-ok の依存は、実物と同じ決まり（guarded）で写しの節から組む。
- 組の子: 子 → 組の節 → join → 柵・落ちの後ろの節 → 返す節 all_done → メイングラフの後ろ。子は項目 b の 1 回目だけ落ちる
  （使用枠の切れの代わり）
- 組でない節: prep → 1 回目だけ落ちる節 step（裁定や審査のループの代わり）→ 落ちの後ろの節 → 柵 → 返す節 all_done →
  メイングラフの後ろと fixed
- レンズ（F327）: 支度 → 落ちるレンズ → 中継（実物の lens_reply.py）→ 集め役 → 審査 → 柵 → 返す節 → メイングラフの後ろ
"""
import json
import pathlib
import re
import shutil
import sys
import tempfile
import unittest

import yaml

from tests import archon

if str(archon.ROOT / "lib") not in sys.path:
    sys.path.append(str(archon.ROOT / "lib"))
import runreport  # noqa: E402

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
    depends_on: {guarded}
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
    depends_on: {guarded}
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


LENS_BLOCK = """name: works-factory-lens-block
description: fix ブロックのレンズの段の配線の写し
returns: fix
nodes:
  - id: lens-prep
    bash: echo prepared
    timeout: 600000
    mutates_checkout: false
  - id: lens
    bash: "echo boom >&2; exit 3"
    depends_on: [lens-prep]
    timeout: 600000
    mutates_checkout: false
  - id: lens-reply
    script: lens_reply
    runtime: uv
    depends_on: {reply_deps}
    timeout: 600000
    mutates_checkout: false
    with: {reply_with}
  - id: lens-collect
    script: lens_collect
    runtime: uv
    depends_on: {collect_deps}
    trigger_rule: {collect_rule}
    timeout: 600000
    mutates_checkout: false
    with: {collect_with}
  - id: delta-loop
    bash: echo reviewed
    depends_on: [lens-collect]
    trigger_rule: {chain_rule}
    timeout: 600000
    mutates_checkout: false
  - id: nodes-ok
    bash: "true"
    depends_on: {guarded}
    trigger_rule: {guard_rule}
    timeout: 600000
    mutates_checkout: false
  - id: fix
    bash: echo collect
    depends_on: [lens-prep, lens, lens-reply, lens-collect, delta-loop]
    trigger_rule: all_done
    timeout: 600000
    mutates_checkout: false
"""

LENS_LINE = """name: works-factory-lens-line
description: メイングラフの写し
nodes:
  - id: fixstage
    include: works-factory-lens-block
  - id: after-fix
    bash: echo after-fix
    depends_on: [fixstage]
    timeout: 600000
    mutates_checkout: false
"""

# 写しの集め役: 受けた返りを書き出すだけ（null はレンズが落ちて中継が飛んだ印）
COLLECT_SCRIPT = """import json, os
print(json.dumps({"reply": os.environ.get("INPUTS_REPLY")}))
"""


def absorbed(ids) -> set:
    """ids のうち、fix 自身が返す節の with: の optional で受け止めると宣言した節（落ちても止めない段。線は include の id の頭を付けて受ける）"""
    fix = {n["id"]: n for n in yaml.safe_load(FIX_YAML.read_text(encoding="utf-8"))["nodes"]}
    declared = [f"fix__{row['node']}" for row in json.loads(fix["fix"]["with"]["optional"])]
    return {nid for nid in ids if runreport._declared(f"fix__{nid}", declared)}


def guarded(ids) -> list:
    """柵 nodes-ok が結ぶ節: 返す節 fix・柵自身・落ちても止めない段のほかの全部（実物も写しもこの決まり）"""
    return [nid for nid in ids if nid not in {"fix", "nodes-ok"} | absorbed(ids)]


def wiring() -> dict:
    top = yaml.safe_load(FIX_YAML.read_text(encoding="utf-8"))["nodes"]
    nodes = {n["id"]: n for n in top}
    assert set(nodes["nodes-ok"]["depends_on"]) == set(guarded([n["id"] for n in top])), "実物の柵の結びが決まりに合わない"
    fan_joins = {nodes[nid]["fan_out"]["join"] for nid in ("groups-par", "groups-seq")}
    assert len(fan_joins) == 1, fan_joins
    chain = {nodes[nid]["trigger_rule"] for nid in ("clean", "assert-changed", "delta-cut", "delta-loop")}
    assert len(chain) == 1, chain
    line = {n["id"]: n for n in yaml.safe_load(LINE_YAML.read_text(encoding="utf-8"))["nodes"]}
    return {"fan_join": fan_joins.pop(), "join_rule": nodes["join"]["trigger_rule"],
            "guard_rule": nodes["nodes-ok"]["trigger_rule"], "chain_rule": chain.pop(),
            "fixed_rule": line["fixed"]["trigger_rule"],
            "reply_deps": json.dumps(nodes["lens-reply"]["depends_on"]), "reply_with": json.dumps(nodes["lens-reply"]["with"]),
            "collect_deps": json.dumps(nodes["lens-collect"]["depends_on"]),
            "collect_rule": nodes["lens-collect"]["trigger_rule"], "collect_with": json.dumps(nodes["lens-collect"]["with"])}


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

    def test_failed_lens_is_recorded_and_the_line_goes_on(self):
        """F327: レンズが落ちても中継が飛ぶだけで、集め役は返り null を受けて走り、審査・柵・返す節・メイングラフの後ろまで進む
        （run は落ちた節を持つので failed で終わり、報告が受け止めた落ちに載せる）"""
        with tempfile.TemporaryDirectory() as tmp:
            src, _ = self._place(tmp, {"lens-block": LENS_BLOCK, "lens-line": LENS_LINE})
            scripts = src / "lens-block" / "scripts"
            scripts.mkdir()
            shutil.copy(FIX_YAML.parent / "scripts" / "lens_reply.py", scripts / "lens_reply.py")
            (scripts / "lens_collect.py").write_text(COLLECT_SCRIPT, encoding="utf-8")
            with archon.tree(["lens-block", "lens-line"], workflows=src) as root:
                archon.archon(root, "workflow", "run", "works-factory-lens-line", "--no-worktree")
                parent, events = self._parent(root, "works-factory-lens-line")
                detail = json.loads(archon.archon(root, "workflow", "get", parent["id"], "--json", "--verbose", "--events").stdout)
        self.assertEqual(parent["status"], "failed")
        self.assertIn(("node_failed", "fixstage__lens"), events)
        self.assertIn(("node_skipped", "fixstage__lens-reply"), events)
        for ran in ("fixstage__lens-collect", "fixstage__delta-loop", "fixstage__nodes-ok", "fixstage__fix", "after-fix"):
            self.assertIn(("node_completed", ran), events)
        collected = next(e for e in detail["events"]
                         if (e["event_type"], e["step_name"]) == ("node_completed", "fixstage__lens-collect"))
        self.assertEqual(json.loads(collected["data"]["node_output"]), {"reply": "null"})

    def _place(self, tmp, files):
        mark = pathlib.Path(tmp) / "marks"
        mark.mkdir()
        src = pathlib.Path(tmp) / "wf"
        for name, text in files.items():
            body = text.replace("{mark}", str(mark))
            ids = re.findall(r"^  - id: (\S+)$", body, flags=re.M)
            for key, value in {**wiring(), "guarded": json.dumps(guarded(ids))}.items():
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
