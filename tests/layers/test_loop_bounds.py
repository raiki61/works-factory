"""受け付けの loop の配線と上限の yes/no（keep-essence の 4「3 回拒まれたら諦める」。`workflows/AGENTS.md` の「始め方」の機械の行）。

- 受け付けの node とは、`output_format` が `lib/rolekit.py` の `round_outcome` の欄 `ok`・`done`・`reason` を宣言する node
  （`give_up` は持たない受け付けも在る）。欄の形で見分けるので、表に loop を並べない（憲法の 6）。
- loop の本体（入れ子の loop の本体は数えない）に受け付けの node が在れば、その loop の `until_bash` はそのどれかの
  `.output.done` を読む。読まない（`true` に替えた・`ok` を読む）と、受け付けが諦めても拒んでも loop が抜けない・1 回で抜ける。
- 受け付けの loop（本体に受け付けの node を持つか、`until_bash` が受け付けの node の `.output.done` を読む loop）の
  `max_iterations` は `rolekit.GIVE_UP_AFTER` 以上。下回ると、受け付けが諦める前に Archon が loop を尽きさせ、諦めの行
  （拒否の控えと give_up）を出さずに loop が落ちる。上回るのは構わない（受け付けが諦めて done を返せば until で抜ける）。
- `done` だけを返す loop（test-gate の実行器の loop の `{done, ok, why}`・fix の書き手の選び `{done, go, writer}`）は
  受け付けでないので数えない。
- 方針 net の受け付け（plan と plan-review の網 `rolekit.NET_AFTER`）の loop が網の数に届くことは、欄の形で網か見分けられないので
  この試験は見ない（`tests/blocks/plan/test_shape.py` と plan-review の試験が見る）。
- 受け付けの node の `output_format` から欄 `reason` を別の名にすると、その node は受け付けと数えられなくなる（この試験の外。
  script の返りが型に合わなくなるので、筋書きを回す `tests/layers/test_block_shape.py` の `ArchonCase` が見る）。
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


def _accepts(nodes) -> set:
    return {n.get("id") for n in nodes or []
            if ROUND_FIELDS <= set(((n.get("output_format") or {}).get("properties") or {}))}


def loops(root: pathlib.Path):
    """木の pack の受け付けの loop を (YAML の根からのパス, loop の node, 本体の受け付けの node の id, until が done を読む id) で出す"""
    for path in sorted((root / "workflows").glob("*/*.yaml")):
        listed = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("nodes") or []
        everywhere = _accepts(walk(listed))
        for node in walk(listed):
            group = node.get("loop_group")
            if not group:
                continue
            body = _accepts(group.get("nodes"))
            reads = set(UNTIL_DONE.findall(str(group.get("until_bash", ""))))
            if body or reads & everywhere:
                yield path.relative_to(root).as_posix(), node, body, reads


def accept_loops(root: pathlib.Path):
    for rel, node, _, _ in loops(root):
        yield rel, node


def problems(root: pathlib.Path) -> list[str]:
    out = []
    for rel, n, body, reads in loops(root):
        group = n["loop_group"]
        if body and not body & reads:
            out.append(f"{rel}: 受け付けの loop {n['id']} の until_bash が本体の受け付け（{', '.join(sorted(body))}）の"
                       " .output.done を読まない")
        bound = group.get("max_iterations")
        if not isinstance(bound, int) or bound < rolekit.GIVE_UP_AFTER:
            out.append(f"{rel}: 受け付けの loop {n['id']} の max_iterations {bound} が"
                       f" 諦めの回数 rolekit.GIVE_UP_AFTER（{rolekit.GIVE_UP_AFTER}）に届かない")
    return out


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


    def test_breaking_the_until_wiring_of_a_real_loop_is_red(self):
        """本物の木の loop の until_bash を `true` に替えても、`done` を `ok` に読み替えても赤（上限は 3 のまま）"""
        text = (ROOT / REAL).read_text(encoding="utf-8")
        until = "until_bash: done=$hygiene-accept.output.done; test \"$done\" = true\n"
        self.assertIn(until, text)
        for broken in ("until_bash: 'true'\n", until.replace(".output.done", ".output.ok")):
            with self.subTest(broken=broken), tree({REAL: text.replace(until, broken, 1)}) as root:
                got = problems(root)
                self.assertEqual(len(got), 1, got)
                self.assertIn("hygiene-loop の until_bash が本体の受け付け（hygiene-accept）", got[0])

    def test_lowering_a_rewired_loop_is_still_red(self):
        """until の配線を壊して上限も 1 に下げた loop は、数えから外れずに 2 つとも赤"""
        text = (ROOT / REAL).read_text(encoding="utf-8")
        until = "until_bash: done=$hygiene-accept.output.done; test \"$done\" = true\n"
        broken = text.replace(until, "until_bash: 'true'\n", 1).replace(f"max_iterations: {rolekit.GIVE_UP_AFTER}\n", "max_iterations: 1\n", 1)
        with tree({REAL: broken}) as root:
            self.assertEqual(len(problems(root)), 2, problems(root))

if __name__ == "__main__":
    unittest.main()
