"""全部のブロックの YAML（workflows/<ブロック>/works-factory-<ブロック>.yaml）の節の印の照らし。

- coldwrite を節の plugins: に名指さない。coldwrite は隔離した設定の settings.json の hooks で全部の役に効かせる
  （bin/_lib/toolset.py）。節に名指すと、入れていない普通の利用者（E14）の run でその節が落ちる
- 作業ツリーの姿を比べる受け付けの節の with: の status_guarded が真 ⇔ 受ける役の節（depends_on のただ 1 つの prompt・command の
  節）が mutates_checkout: false。真の節の script は INPUTS_STATUS_GUARDED を読む。同じ script を回すほかの節は偽を書く
  （Archon の validate は、script が読む INPUTS_* を全部の節が結ぶことを求める。だからブロックの中で印を持つ節の script が、
  そのブロックの作業ツリーを比べる受け付けの script の全部になる）
"""
import pathlib
import unittest

import yaml

WORKFLOWS = pathlib.Path(__file__).resolve().parents[2] / "workflows"
DOCS = {p.parent.name: yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted(WORKFLOWS.glob("*/works-factory-*.yaml"))}


def walk(nodes):
    for n in nodes:
        yield n
        yield from walk((n.get("loop_group") or {}).get("nodes") or [])


def guarded_nodes(doc) -> list:
    return [n for n in walk(doc["nodes"]) if "status_guarded" in (n.get("with") or {})]


def coldwrite_named(doc) -> list:
    return [n["id"] for n in walk(doc["nodes"]) if any("coldwrite" in str(p) for p in n.get("plugins") or [])]


def guarded_mismatches(doc, block: str) -> list:
    nodes = {n["id"]: n for n in walk(doc["nodes"])}
    tree_accepts = {n["script"] for n in guarded_nodes(doc)}
    out = []
    for n in nodes.values():
        if n.get("script") not in tree_accepts:
            continue
        flag = (n.get("with") or {}).get("status_guarded")
        roles = [nodes[d] for d in n.get("depends_on") or [] if d in nodes and ("prompt" in nodes[d] or "command" in nodes[d])]
        if not roles:
            if flag not in (None, False):
                out.append(f"{n['id']}: 役を受けない節の status_guarded が {flag!r}")
            continue
        if len(roles) != 1:
            out.append(f"{n['id']}: 受ける役が 1 つでない（{[r['id'] for r in roles]}）")
            continue
        want = roles[0].get("mutates_checkout") is False
        if (flag is True) != want or flag not in (None, True, False):
            out.append(f"{n['id']}: status_guarded {flag!r} だが役 {roles[0]['id']} の mutates_checkout は "
                       f"{roles[0].get('mutates_checkout')!r}")
        script = WORKFLOWS / block / "scripts" / f"{n['script']}.py"
        if flag is True and "INPUTS_STATUS_GUARDED" not in script.read_text(encoding="utf-8"):
            out.append(f"{n['id']}: script {script.name} が INPUTS_STATUS_GUARDED を読まない")
    return out


class NodeFlagsCase(unittest.TestCase):

    def test_no_node_names_coldwrite(self):
        for block, doc in DOCS.items():
            with self.subTest(block):
                self.assertEqual(coldwrite_named(doc), [])

    def test_guarded_accepts_flag_matches_role(self):
        for block, doc in DOCS.items():
            with self.subTest(block):
                self.assertEqual(guarded_mismatches(doc, block), [])

    def test_some_accepts_are_guarded(self):
        """印を持つ節が 1 つも無ければ上の照らしは空回りする"""
        self.assertTrue(any(n["with"]["status_guarded"] is True for doc in DOCS.values() for n in guarded_nodes(doc)))


if __name__ == "__main__":
    unittest.main()
