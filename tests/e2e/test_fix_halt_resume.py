"""#576・#594: 修正のサブグラフの節が落ちた時、メイングラフの後ろが走らずに run が failed で止まり、親の resume で落ちた節から
続きが回ることを、止めた Archon で照らす。

fix ブロックの配線（組の節の fan_out の join・join の節と柵 nodes-ok と落ちの後ろの節の trigger_rule・返す節 finish の trigger_rule）を
works-factory-fix.yaml から、修正の後ろの節 fixed の trigger_rule と、受け止める段の宣言（collect の with: の optional）と
レンズの受け皿の結びを works-factory-line.yaml から、レンズの段の配線を works-factory-lens.yaml から読んで、AI の無い節の使い捨ての
工程に組む。写しの柵 nodes-ok の依存は、実物と同じ決まり（guarded）で写しの節から組む。include の id は線の実物と同じ fix・lens。
- 組の子: 子 → 組の節 → join → 柵・落ちの後ろの節 → 返す節 finish → メイングラフの後ろ。子は項目 b の 1 回目だけ落ちる
  （使用枠の切れの代わり）
- 組でない節: prep → 1 回目だけ落ちる節 step（裁定や修正のループの代わり）→ 落ちの後ろの節 clean・assert-changed → 柵 → 返す節
  finish → メイングラフの後ろと fixed
- レンズ（F327）: レンズは組み込みで fix から分かれた自分のブロック（works-factory-lens）で、柵を持たない。支度 → 落ちるレンズ →
  受け取り（飛ぶ）→ 返す節 finish → 線の受け皿 lens-out・中継 lens-in。落ちたレンズの節は、線の collect の optional が受け止めると
  宣言した中に在る
"""
import json
import pathlib
import re
import sys
import tempfile
import unittest

import yaml

from tests import archon

if str(archon.ROOT / "lib") not in sys.path:
    sys.path.append(str(archon.ROOT / "lib"))
import runlog  # noqa: E402  （run の記録の読み。受け止めの宣言の決まり _declared の持ち主。integration.md の 4.5-2）

FIX_YAML = archon.WORKFLOWS / "fix" / "works-factory-fix.yaml"
LINE_YAML = archon.WORKFLOWS / "line" / "works-factory-line.yaml"
LENS_YAML = archon.WORKFLOWS / "lens" / "works-factory-lens.yaml"
FIX_RETURNS = "finish"   # fix の返す節（works-factory-fix.yaml の returns）

CHILD = """name: works-factory-halt-child
description: 項目 b の 1 回目だけ落ちる子
nodes:
  - id: work
    bash: |
      if [ "$ARGUMENTS" = "b" ] && [ ! -f {mark}/child-b ]; then touch {mark}/child-b; echo boom >&2; exit 3; fi
      echo "ok:$ARGUMENTS"
    mutates_checkout: false
"""

BLOCK = """name: works-factory-halt-block
description: fix ブロックの組の配線の写し
returns: finish
nodes:
  - id: prep
    bash: printf '%s' '["a","b"]'
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
    mutates_checkout: false
  - id: nodes-ok
    bash: "true"
    depends_on: {guarded}
    trigger_rule: {guard_rule}
    mutates_checkout: false
  - id: assert-changed
    bash: echo checked
    depends_on: [prep, join]
    trigger_rule: {chain_rule}
    mutates_checkout: false
  - id: finish
    bash: echo collect
    depends_on: [prep, groups-seq, join, assert-changed]
    trigger_rule: {finish_rule}
    mutates_checkout: false
"""

LINE = """name: works-factory-halt-line
description: メイングラフの写し
nodes:
  - id: fix
    include: works-factory-halt-block
  - id: after-fix
    bash: echo after-fix
    depends_on: [fix]
    mutates_checkout: false
"""

STEP_BLOCK = """name: works-factory-step-block
description: fix ブロックの組でない節の配線の写し
returns: finish
nodes:
  - id: prep
    bash: echo run >> {mark}/prep-count
    mutates_checkout: false
  - id: step
    bash: |
      if [ ! -f {mark}/step ]; then touch {mark}/step; echo boom >&2; exit 3; fi
      echo stepped
    depends_on: [prep]
    mutates_checkout: false
  - id: clean
    bash: echo cleaned
    depends_on: [prep, step]
    trigger_rule: {chain_rule}
    mutates_checkout: false
  - id: assert-changed
    bash: echo checked
    depends_on: [prep, clean]
    trigger_rule: {chain_rule}
    mutates_checkout: false
  - id: nodes-ok
    bash: "true"
    depends_on: {guarded}
    trigger_rule: {guard_rule}
    mutates_checkout: false
  - id: finish
    bash: echo collect
    depends_on: [prep, step, clean, assert-changed]
    trigger_rule: {finish_rule}
    mutates_checkout: false
"""

STEP_LINE = """name: works-factory-step-line
description: メイングラフの写し
nodes:
  - id: fix
    include: works-factory-step-block
  - id: after-fix
    bash: echo after-fix
    depends_on: [fix]
    mutates_checkout: false
  - id: fixed
    bash: echo fixed
    depends_on: [after-fix, fix]
    trigger_rule: {fixed_rule}
    mutates_checkout: false
"""


# レンズの段の写し。受け取りと返す節は bash の代わり: 受け取りはレンズが落ちると飛ぶので走らず、実物の返す節は place の控えを
# 読んで組むので、ここで照らす配線（落ちても走って受け皿へ渡す）の外。{lens} は実物のレンズの節の id
LENS_BLOCK = """name: works-factory-lens-block
description: lens ブロックの配線の写し
returns: finish
nodes:
  - id: intake
    bash: echo routed
    mutates_checkout: false
  - id: {lens}-prep
    bash: echo prepared
    depends_on: [intake]
    mutates_checkout: false
  - id: {lens}
    bash: "echo boom >&2; exit 3"
    depends_on: [{lens}-prep]
    mutates_checkout: false
  - id: {lens}-take
    bash: echo taken
    depends_on: {take_deps}
    mutates_checkout: false
  - id: finish
    bash: echo collect
    depends_on: {lens_finish_deps}
    trigger_rule: {lens_finish_rule}
    mutates_checkout: false
"""

LENS_LINE = """name: works-factory-lens-line
description: メイングラフの写し
nodes:
  - id: lens
    include: works-factory-lens-block
  - id: lens-out
    bash: echo received
    depends_on: {lens_out_deps}
    mutates_checkout: false
  - id: lens-in
    bash: echo relayed
    depends_on: [lens-out]
    trigger_rule: {lens_in_rule}
    mutates_checkout: false
"""


def _nodes(path) -> dict:
    return {n["id"]: n for n in yaml.safe_load(path.read_text(encoding="utf-8"))["nodes"]}


def collectors() -> set:
    """fix の実物で trigger_rule が all_done の節（前の節が落ちても飛ばされても走る集め。返す節 finish と読んだ証拠の fix-reads）"""
    return {nid for nid, n in _nodes(FIX_YAML).items() if n.get("trigger_rule") == "all_done"}


def guarded(ids) -> list:
    """柵 nodes-ok が結ぶ節: 柵自身と、落ちても走る集め（collectors）のほかの全部（実物も写しもこの決まり）"""
    return [nid for nid in ids if nid not in {"nodes-ok"} | collectors()]


def line_absorbs(step: str) -> bool:
    """線の run の節 step を、線の collect の with: の optional（include 丸ごと受け止める段の宣言）が受け止めるか"""
    return runlog._declared(step, json.loads(_nodes(LINE_YAML)["collect"]["with"]["optional"]))


def wiring() -> dict:
    nodes = _nodes(FIX_YAML)
    assert set(nodes["nodes-ok"]["depends_on"]) == set(guarded(nodes)), "実物の柵の結びが決まりに合わない"
    assert nodes[FIX_RETURNS]["trigger_rule"] == "all_done", "返す節は落ちの後も走る"
    fan_joins = {nodes[nid]["fan_out"]["join"] for nid in ("groups-par", "groups-seq")}
    assert len(fan_joins) == 1, fan_joins
    chain = {nodes[nid]["trigger_rule"] for nid in ("conflict-check", "clean", "assert-changed")}
    assert len(chain) == 1, chain
    line = _nodes(LINE_YAML)
    lens_doc = yaml.safe_load(LENS_YAML.read_text(encoding="utf-8"))
    lens_nodes = {n["id"]: n for n in lens_doc["nodes"]}
    (lens,) = [nid for nid, n in lens_nodes.items() if "prompt" in n]
    assert lens_nodes[f"{lens}-prep"]["depends_on"] == ["intake"] and lens_nodes[lens]["depends_on"] == [f"{lens}-prep"], lens
    returns = lens_doc["returns"]
    return {"fan_join": fan_joins.pop(), "join_rule": nodes["join"]["trigger_rule"],
            "guard_rule": nodes["nodes-ok"]["trigger_rule"], "chain_rule": chain.pop(),
            "finish_rule": nodes[FIX_RETURNS]["trigger_rule"], "fixed_rule": line["fixed"]["trigger_rule"],
            "lens": lens, "take_deps": json.dumps(lens_nodes[f"{lens}-take"]["depends_on"]),
            "lens_finish_deps": json.dumps(lens_nodes[returns]["depends_on"]),
            "lens_finish_rule": lens_nodes[returns]["trigger_rule"],
            "lens_out_deps": json.dumps(line["lens-out"]["depends_on"]), "lens_in_rule": line["lens-in"]["trigger_rule"]}


class FixHaltResumeCase(unittest.TestCase):
    def test_failed_child_halts_the_line_and_resume_continues_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, _ = self._place(tmp, {"halt-child": CHILD, "halt-block": BLOCK, "halt-line": LINE})
            with archon.tree(["halt-child", "halt-block", "halt-line"], workflows=src) as root:
                first, again, parent = self._run_and_resume(root, "works-factory-halt-line")
                children = [r["status"] for r in json.loads(archon.archon(root, "workflow", "runs", "--json").stdout)["runs"]
                            if r["workflow_name"] == "works-factory-halt-child"]
        self.assertIn(("node_failed", "fix__groups-seq"), first)
        self.assertFalse(line_absorbs("fix__groups-seq"), "修正の組の落ちは線が受け止めない段")
        for skipped in ("fix__join", "fix__nodes-ok", "fix__assert-changed", "after-fix"):
            self.assertIn(("node_skipped", skipped), first)
        self.assertNotIn(("node_completed", "after-fix"), first)
        self.assertEqual(parent["status"], "completed")
        self.assertEqual(children, ["completed", "completed"], "落ちた子を新しく起こさず、同じ run で続きから回した")
        for ran in ("fix__groups-seq", "fix__join", "fix__nodes-ok", "fix__assert-changed", "after-fix"):
            self.assertIn(("node_completed", ran), again)

    def test_failed_node_outside_the_groups_halts_the_line_and_resume_continues_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, mark = self._place(tmp, {"step-block": STEP_BLOCK, "step-line": STEP_LINE})
            with archon.tree(["step-block", "step-line"], workflows=src) as root:
                first, again, parent = self._run_and_resume(root, "works-factory-step-line")
            prep_runs = (mark / "prep-count").read_text(encoding="utf-8").splitlines()
        self.assertIn(("node_failed", "fix__step"), first)
        self.assertFalse(line_absorbs("fix__step"), "修正の段の落ちは線が受け止めない段")
        for skipped in ("fix__clean", "fix__assert-changed", "fix__nodes-ok", "after-fix", "fixed"):
            self.assertIn(("node_skipped", skipped), first)
        self.assertIn(("node_completed", f"fix__{FIX_RETURNS}"), first, "返す節は落ちの後も走る")
        self.assertEqual(parent["status"], "completed")
        for ran in ("fix__step", "fix__clean", "fix__assert-changed", "fix__nodes-ok", "after-fix", "fixed"):
            self.assertIn(("node_completed", ran), again)
        self.assertEqual(len(prep_runs), 1, "resume は落ちた節から続け、済んだ節を走らせ直さない")

    def test_failed_lens_is_recorded_and_the_line_goes_on(self):
        """F327: レンズが落ちても受け取りが飛ぶだけで、返す節は走り、線の受け皿と中継まで進む（レンズのブロックは柵を持たない。
        run は落ちた節を持つので failed で終わり、落ちた節は線の collect の optional が受け止めると宣言した中に在るので、報告が
        受け止めた落ちに載せる）"""
        lens = wiring()["lens"]
        with tempfile.TemporaryDirectory() as tmp:
            src, _ = self._place(tmp, {"lens-block": LENS_BLOCK, "lens-line": LENS_LINE})
            with archon.tree(["lens-block", "lens-line"], workflows=src) as root:
                archon.archon(root, "workflow", "run", "works-factory-lens-line", "--no-worktree")
                parent, events = self._parent(root, "works-factory-lens-line")
        self.assertEqual(parent["status"], "failed")
        self.assertIn(("node_failed", f"lens__{lens}"), events)
        self.assertTrue(line_absorbs(f"lens__{lens}"), "落ちたレンズの節を線が受け止めると宣言していない")
        self.assertIn(("node_skipped", f"lens__{lens}-take"), events)
        for ran in ("lens__finish", "lens-out", "lens-in"):
            self.assertIn(("node_completed", ran), events)

    def _place(self, tmp, files):
        mark = pathlib.Path(tmp) / "marks"
        mark.mkdir()
        src = pathlib.Path(tmp) / "wf"
        wired = wiring()
        for name, text in files.items():
            body = text.replace("{mark}", str(mark))
            for key, value in wired.items():
                body = body.replace("{" + key + "}", value)
            ids = re.findall(r"^  - id: (\S+)$", body, flags=re.M)
            body = body.replace("{guarded}", json.dumps(guarded(ids)))
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
