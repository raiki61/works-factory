"""block r4 の役の返答の型のうち、承認ノードの問いに効く所（docs/design/r4.md の 8 節）。PyYAML で読むだけ（Archon を起こさない）。

棚卸しが発火した返答（capability_inventory.fired が真）に消えた能力 lost を要るのは、YAML の output_format の if/then だけ（Archon の
Ajv が照らす。受け付けの src/gate.py は lost を無ければ空として読み、消えた能力の行は最後の承認ノードの問いになる）。if/then が落ちると、
発火したのに lost を書かない返答が問いを作らずに通る。役の形のほかの所（道具・群・輪）は tests/layers の全体の検査が見る。
"""
import unittest

import yaml

from tests.blocks import kit

DOC = yaml.safe_load((kit.BLOCKS / "r4" / "works-factory-r4.yaml").read_text(encoding="utf-8"))
LOOP = next(n for n in DOC["nodes"] if "loop_group" in n)
NODES = {n["id"]: n for n in [*DOC["nodes"], *LOOP["loop_group"]["nodes"]]}
ROLES = {i: n for i, n in NODES.items() if "prompt" in n}


class ReplyTypeCase(unittest.TestCase):
    def test_inventory_requires_lost(self):
        """test_r4_inventory_requires_lost: 棚卸しが発火した返答（fired: true）は lost が要る。if/then は Archon の Ajv が照らす（lib の
        engine.schema は if/then を読まないので、型の形で縛り、読める部分だけ照らす）"""
        kit.load("r4", "files")   # lib/ を sys.path に足す
        from engine.schema import validate_schema
        self.assertEqual(sorted(ROLES), ["r4-scope", "r4-scope-fix"])
        for nid in ROLES:
            schema = NODES[nid]["output_format"]
            self.assertEqual(schema["if"], {"properties": {"capability_inventory": {"properties": {"fired": {"const": True}}}}})
            self.assertEqual(schema["then"], {"properties": {"capability_inventory": {"required": ["fired", "lost"]}}})
        schema = NODES["r4-scope"]["output_format"]
        reply = {"status": "pass", "reason": "なし", "policy_conflicts": [], "surfaced": [], "seen": [], "unseen": [],
                 "capability_inventory": {"fired": True, "lost": []}}
        self.assertEqual(validate_schema(reply, schema), [])
        self.assertNotEqual(validate_schema({**reply, "status": "weird"}, schema), [])


    def test_status_words_are_the_seal_words(self):
        """2 つの役の返答の型の status の語が lib/seal.py の目の状態の語のうち R4 が言える物（fix-needed は seal.FIX_EYES の目だけ）と
        同じ（元 test_role_schemas_match_graph の status の照らし）。redesign-needed が型から落ちると作り直しを返せない"""
        kit.load("r4", "files")   # lib/ を sys.path に足す
        import seal
        for nid in ROLES:
            with self.subTest(nid):
                self.assertEqual(tuple(NODES[nid]["output_format"]["properties"]["status"]["enum"]),
                                 tuple(s for s in seal.STATUSES if s != seal.FIX_NEEDED))

if __name__ == "__main__":
    unittest.main()
