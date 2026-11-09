"""受け付けの輪の上限が諦めの回数に届くかの yes/no（keep-essence の 4「3 回拒まれたら諦める」。`workflows/AGENTS.md` の「始め方」の機械の行）。

- 受け付けの輪とは、`loop_group` の `until_bash` が `$<id>.output.done` を読み、その node `<id>` の `output_format` が
  `lib/rolekit.py` の `round_outcome` の欄 `ok`・`done`・`reason` を宣言する輪（`give_up` は持たない受け付けも在る）。欄の形で
  見分けるので、表に輪を並べない（憲法の 6）。`done` だけを返す輪（test-gate の実行器の輪の `{done, ok, why}`・fix の書き手の
  選び `{done, go, writer}`）は受け付けでないので数えない。
- 受け付けの輪の `max_iterations` は `rolekit.GIVE_UP_AFTER` 以上。下回ると、受け付けが諦める前に Archon が輪を尽きさせ、
  諦めの行（拒否の控えと give_up）を出さずに輪が落ちる。上回るのは構わない（受け付けが諦めて done を返せば until で抜ける）。
- 方針 net の受け付け（plan と plan-review の網 `rolekit.NET_AFTER`）の輪が網の数に届くことは、欄の形で網か見分けられないので
  この試験は見ない（`tests/blocks/plan/test_shape.py` と plan-review の試験が見る）。
"""
import pathlib
import re
import unittest

import yaml

from tests.bin.stepnames import walk
from tests.layers import scan  # noqa: F401 — lib/ を sys.path の後ろに足す（rolekit が lib のモジュールを名で読む）
from tests.layers.trees import tree
from lib import rolekit

ROOT = pathlib.Path(__file__).resolve().parents[2]
UNTIL_DONE = re.compile(r"\$([\w-]+)\.output\.done\b")
ROUND_FIELDS = {"ok", "done", "reason"}
REAL = "workflows/hygiene/works-factory-hygiene.yaml"   # 受け付けの輪を 1 つ持つ本物の block


def accept_loops(root: pathlib.Path):
    """木の pack の受け付けの輪を (YAML の根からのパス, 輪の node) で出す"""
    for path in sorted((root / "workflows").glob("*/*.yaml")):
        listed = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("nodes") or []
        by_id = {n.get("id"): n for n in walk(listed)}
        for node in walk(listed):
            group = node.get("loop_group")
            if not group:
                continue
            for ref in UNTIL_DONE.findall(str(group.get("until_bash", ""))):
                shape = (by_id.get(ref) or {}).get("output_format") or {}
                if ROUND_FIELDS <= set(shape.get("properties") or {}):
                    yield path.relative_to(root).as_posix(), node
                    break


def problems(root: pathlib.Path) -> list[str]:
    return [f"{rel}: 受け付けの輪 {n['id']} の max_iterations {n['loop_group'].get('max_iterations')} が"
            f" 諦めの回数 rolekit.GIVE_UP_AFTER（{rolekit.GIVE_UP_AFTER}）に届かない"
            for rel, n in accept_loops(root)
            if not isinstance(n["loop_group"].get("max_iterations"), int)
            or n["loop_group"]["max_iterations"] < rolekit.GIVE_UP_AFTER]


class LoopBoundsTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(problems(ROOT), [])

    def test_finds_the_accept_loops_of_the_real_tree(self):
        got = {(rel, n["id"]) for rel, n in accept_loops(ROOT)}
        self.assertIn((REAL, "hygiene-loop"), got, "受け付けの輪の見分けが壊れた")
        self.assertNotIn(("workflows/test-gate/works-factory-test-gate.yaml", "suite-loop"), got)

    def test_lowering_a_real_loop_below_the_give_up_count_is_red(self):
        text = (ROOT / REAL).read_text(encoding="utf-8")
        bound = f"max_iterations: {rolekit.GIVE_UP_AFTER}\n"
        self.assertIn(bound, text)
        with tree({REAL: text.replace(bound, f"max_iterations: {rolekit.GIVE_UP_AFTER - 1}\n", 1)}) as root:
            got = problems(root)
        self.assertEqual(len(got), 1, got)
        self.assertIn("hygiene-loop", got[0])

    def test_a_loop_that_only_reads_done_is_not_an_accept_loop(self):
        body = ("name: works-factory-x\nnodes:\n  - id: g\n    loop_group:\n      max_iterations: 1\n"
                "      until_bash: done=$try.output.done; test \"$done\" = true\n      nodes:\n"
                "        - id: try\n          script: t\n          output_format:\n            type: object\n"
                "            properties: {done: {type: boolean}, ok: {type: boolean}, why: {type: string}}\n")
        with tree({"workflows/x/works-factory-x.yaml": body}) as root:
            self.assertEqual(list(accept_loops(root)), [])
            self.assertEqual(problems(root), [])
            with_reason = body.replace("why: {type: string}", "reason: {type: string}")
        with tree({"workflows/x/works-factory-x.yaml": with_reason}) as root:
            self.assertEqual(len(problems(root)), 1)


if __name__ == "__main__":
    unittest.main()
