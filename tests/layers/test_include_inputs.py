"""include した block の入力が、どれも渡るか、渡さない訳を名指した表に在る（`workflows/AGENTS.md` の E5 の機械の行。line の設計書の
L-W67 を全部の graph に効かせた物）。

- どの workflow（block と graph。`loop_group` の中も）の `include:` のノードも、include した block の `inputs:` の全部を `with:` で渡すか、
  下の表 `NOT_PASSED`（graph のフォルダの名 → {(include の id, 入力の名): 訳}）に訳を書く。既定値つきの入力は渡さなくても Archon は
  黙って回るので、配線を 1 本外すと、受け手は既定の値で前の振る舞いに黙って戻る（#984 の独立の目: eyes の graph が R2 へ渡す `means`）。
- `with:` の鍵は、include した block の `inputs:` に在る名だけ。
- 表の行は、include した block の `inputs:` に在り、`with:` で渡していない入力だけを名指す（渡し始めた行・消えた入力の行は赤）。
- 元は line の `tests/blocks/line/test_wiring.py` と judge の `tests/blocks/judge/test_judge.py` の同じ名の試験（graph ごとの表）。
  ほかの graph（eyes・chain・policy-check・fix）に効いていなかったので、表ごとここへ寄せた（持ち主の決め `mechanism-over-tests`）。
"""
import pathlib
import unittest

import yaml

from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]

# graph が渡さない入力と訳（各設計書の 1.2・1.6）
NOT_PASSED = {
    "line": {
        ("test-gate-base", "baseline"): "final の時だけ読む（base は直す前の結末を作る側）",
        ("structure", "base"): "after の時だけ読む（line は before で回す。after は eyes の graph の中）",
        ("structure", "plan"): "after の時だけ読む",
        **{(fix, name): "group の時だけ読む（whole の親が自分を子に起こす時に渡す）"
           for fix in ("fix", "refix-run", *(f"back-{k}-fix" for k in range(1, 4))) for name in ("group", "from_tree", "out_dir")},
        ("fix", "notes"): "案の直しの後の 2 回目の修正の段だけ",
        ("fix", "only_items"): "2 回目の修正の段だけ（1 回目は直す義務の単位の全部）",
        ("fix", "prior"): "2 回目の修正の段だけ（1 回目の段の申し送り）",
        ("fix", "item_kinds"): "独立の目から返した段だけが渡す（1 回目は元の案の route のまま）",
        ("lens", "lenses"): "block の既定の表（docs/design/line.md の 4.5）",
        ("lens-2", "lenses"): "block の既定の表",
        ("plan", "conflicts"): "形 replan だけが読む（往復の中は形 plan）",
        # 仕様駆動の道の include（docs/design/spec-driven.md の 6.2）。block works-factory-spec-driven は形ごとに読む入力が違う
        **{("spec-entry", name): "形 check の入力（形 entry は表だけを読む）" for name in
           ("base", "tdd", "out_of_scope", "ready", "plan", "plan_ok", "out_of_purpose")},
        ("spec-check", "table"): "形 entry の入力（形 check は表を読み直さず、形 entry の返りの写しを受ける）",
        **{("spec-diagnose", name): "仕様駆動の run の中で回らない段の値か、再審の道の入力（素材・世界の解・頭の深さ・仕様の段は会話の中か回さない）"
           for name in ("constraints", "materials", "pr_material", "reply_sources", "world_rows", "row_asks", "depth_why", "spec_rows", "spec_origin", "answers",
                        "prior_failures", "pr_text", "objection", "prior", "prior_brief", "prior_inputs", "spec", "verify", "excluded")},
        **{("spec-plan", name): "仕様駆動の run の中で回らない段の値（裏取り・並行 PR・頭の深さ・前の決め・世界の解・構造の目・前の周・申し出）"
           for name in ("verify", "excluded", "depth_record", "decisions", "world_rows", "structure", "prior_failures", "prior", "conflicts")},
        ("plan", "routes"): "計画の往復は依頼の文の run だけで回る（既定の auto）。仕様駆動の run は spec-plan が spec を渡す",
        ("replan", "routes"): "案の直しは仕様駆動の run では回らない（既定の auto）",
        ("rejudge-run", "request_files"): "再審の道は読まない（判定の道だけの入力）",
        **{(review, name): "方針の文と方針の文のファイル。仕様を固める会話から単独で回す時だけ使う（line は修正案を plan で渡す）"
           for review in ("plan-review-run", "replan-review") for name in ("proposal", "proposal_file")},
        **{(review, "theme_doc"): "形 theme の設計の案。この 2 つは修正案を審査する include で、設計の案は渡さない（設計の案を渡すのは設計の段の theme-review）"
           for review in ("plan-review-run", "replan-review")},
        **{(plan, "spec_doc"): "仕様駆動の run だけが渡す人と固めた仕様の本文（依頼の文の run の固めた仕様は spec）" for plan in ("plan", "replan")},
        ("spec-plan", "spec"): "仕様駆動の run は仕様の段の spec.json を作らない（固めた本文は spec_doc）",
        ("spec-plan", "means"): "仕様駆動の道は目的の役を通らず、頼みの解き方の文を持たない（docs/design/plan-review.md の 20 章の 3.1 の 1）",
        ("plan-review-run", "ruling"): "形 replan だけが読む",
        **{("theme-review", name): "形 theme は読まない（設計の案の審査が読む port は docs/design/plan-review.md の 19.1）"
           for name in ("proposal", "proposal_file", "plan", "fields", "judgment", "means", "structure", "ripple", "tree", "excluded", "ruling",
                        "conflicts")},
        ("theme-world", "means"): "テーマの run は依頼の解き方の文を持たない（入口の欄はテーマの文だけ。docs/design/line.md の 3.3 節）",
        **{("theme-blind", name): "設計の段は判定の前に回り、目的の固定・目的の監査・前提の実測がまだ無い（テーマの文をそのまま目的にする。3.3 節）"
           for name in ("purpose_source", "purpose_review", "constraints")},
        ("plan-review-run", "conflicts"): "形 replan だけが読む",
        **{("rejudge-run", name): "判定の道だけが読む（再審の道は prior と objection で考え直す。docs/design/diagnose.md の 1.2）"
           for name in ("answers", "base", "baseline", "constraints", "depth_why", "materials", "pr_material", "pr_text", "prior_failures",
                        "reply_sources", "request_origin", "row_asks", "spec_origin", "spec_rows")},
        ("spec-check-run", "request"): "write の時だけ読む", ("spec-check-run", "pr_text"): "write の時だけ読む",
        **{("merge-seal", name): "apply と check の時だけ読む"
           for name in ("answer", "deliver", "items", "r2", "request", "sealed_hash", "user_env_dir")},
    },
    "judge": {   # README の 8.1・各設計書の 1.2。block diagnose を include する節は diagnose-run
        ("spec", "spec"): "check の時だけ読む（判定の道は write）",
        ("diagnose-run", "objection"): "再審の道の入力（再審は line が diagnose を直に include する）",
        ("diagnose-run", "request_files"): "仕様駆動の道の入力（依頼そのものを書いたファイル。line の spec-diagnose が渡す。依頼の文の run は既定の空）",
        ("diagnose-run", "prior"): "再審の道の入力", ("diagnose-run", "prior_brief"): "再審の道の入力",
        ("diagnose-run", "prior_inputs"): "再審の道の入力", ("diagnose-run", "spec"): "再審の道の入力",
        ("diagnose-run", "verify"): "再審の道の入力", ("diagnose-run", "excluded"): "再審の道の入力",
        ("diagnose-run", "answers"): "空の配列で依頼の容器の answers を読む", ("diagnose-run", "prior_failures"): "空の配列で依頼の容器の物を読む",
    },
    "chain": {   # 鎖の hand は形 check（docs/design/merge.md の chain の hand。答えと確かめは各周の line で済んでいる）
        **{("hand", name): "形 apply の時だけ読む（check は封じた hash と今の差分を照らすだけ）"
           for name in ("answer", "eyes_ok", "green_ok", "r2")},
        ("hand", "fingerprint"): "形 seal と apply の時だけ読む（緑の認証の指紋を照らし直す。check は封じた hash と今の差分を照らすだけ）",
        ("hand", "items"): "鎖の親は修正案の項目の記録を持たない（null で PR の commit を 1 つに倒す）",
    },
    "policy-check": {   # 方針の文だけを入れる入口（docs/design/plan-review.md の policy-check の配線）。形 text は方針の文・目的・世界の解・言語だけを読む
        **{("review-run", name): "形 text（方針の文の審査）は読まない。修正案・判定・往復を持たない入口"
           for name in ("conflicts", "design", "design_why", "excluded", "fields", "judgment", "means", "plan",
                        "prior", "request", "ripple", "ruling", "structure", "theme_doc", "tree")},
        **{("review-run", name): "形 text も読むが、この入口は人の方針の文書と記録された方針を持たない（入力は方針の文・困り事・目的・web・言語だけ）"
           for name in ("policy", "recorded")},
        **{("review-run", name): "形 text も読むが、既定の HEAD で足りる（この入口は版を固めない）"
           for name in ("review_rev", "diff_base")},
        ("review-run", "proposal_file"): "在ると形 text に決まるが、方針の文は proposal で渡す",
    },
}


def _nodes(nodes):
    for node in nodes or []:
        if isinstance(node, dict):
            yield node
            yield from _nodes((node.get("loop_group") or {}).get("nodes"))


def _doc(path: pathlib.Path):
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None


def problems(root: pathlib.Path, table: dict) -> list[str]:
    """root の workflows/ の include のノードの、渡していない入力・block に無い鍵・表の古い行"""
    out, seen = [], set()
    for path in sorted((root / "workflows").glob("*/works-factory-*.yaml")):
        graph, doc = path.parent.name, _doc(path) or {}
        rows = table.get(graph, {})
        for node in _nodes(doc.get("nodes")):
            name = node.get("include")
            if not isinstance(name, str):
                continue
            block = name.removeprefix("works-factory-")
            included = _doc(root / "workflows" / block / f"{name}.yaml")
            where = f"{graph} のノード {node.get('id')}（{name}）"
            if included is None:
                out.append(f"{where}: include した block が workflows/ に無い")
                continue
            inputs, given = set(included.get("inputs") or {}), set(node.get("with") or {})
            out += [f"{where}: with: の鍵 {k} が block の inputs: に無い" for k in sorted(given - inputs)]
            ident = node.get("id")
            named = {k for i, k in rows if i == ident}
            seen.add((graph, ident))
            out += [f"{where}: 入力 {k} を渡さず、渡さない訳の表 NOT_PASSED にも無い" for k in sorted(inputs - given - named)]
            out += [f"{where}: 表 NOT_PASSED の行 {k} は渡しているか、block の inputs: に無い" for k in sorted(named & given | named - inputs)]
    out += [f"{graph}: 表 NOT_PASSED の行 {key} の include のノードが無い" for graph, rows in sorted(table.items()) for key in sorted(rows)
            if (graph, key[0]) not in seen]
    return out


class IncludeInputsTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(problems(ROOT, NOT_PASSED), [])

    BLOCK = ("name: works-factory-r2\ninputs:\n  base: {default: ''}\n  means: {default: '[]'}\nreturns: f\noutcome_field: ok\n"
             "nodes:\n  - id: f\n    script: f\n")

    def graph(self, with_: str, loop=False) -> str:
        node = f"  - id: r2\n    include: works-factory-r2\n    with:\n{with_}"
        if loop:
            node = "  - id: l\n    loop_group:\n      nodes:\n" + "".join(f"      {line}\n" for line in node.splitlines())
        return "name: works-factory-eyes\nnodes:\n" + node

    def check(self, graph: str, table=None) -> list[str]:
        files = {"workflows/r2/works-factory-r2.yaml": self.BLOCK, "workflows/eyes/works-factory-eyes.yaml": graph}
        with tree(files) as root:
            return problems(root, table or {})

    def test_every_input_passed_is_clean(self):
        self.assertEqual(self.check(self.graph("      base: x\n      means: y\n")), [])

    def test_unpassed_input_is_red_in_any_graph(self):
        """#984 の場面: eyes の graph が R2 へ means を渡さない（輪の中の include も同じ）"""
        for loop in (False, True):
            with self.subTest(loop=loop):
                got = self.check(self.graph("      base: x\n", loop=loop))
                self.assertEqual(len(got), 1, got)
                self.assertIn("入力 means を渡さず", got[0])

    def test_named_reason_lets_it_pass(self):
        self.assertEqual(self.check(self.graph("      base: x\n"), {"eyes": {("r2", "means"): "訳"}}), [])

    def test_key_outside_the_inputs_is_red(self):
        got = self.check(self.graph("      base: x\n      means: y\n      gone: z\n"))
        self.assertEqual(len(got), 1, got)
        self.assertIn("鍵 gone が block の inputs: に無い", got[0])

    def test_stale_rows_are_red(self):
        """渡し始めた行・block に無い入力の行・include のノードが無い行は赤"""
        for row, words in (((("r2", "means")), "渡しているか"), ((("r2", "gone")), "渡しているか"), ((("r9", "base")), "include のノードが無い")):
            with self.subTest(row=row):
                got = self.check(self.graph("      base: x\n      means: y\n"), {"eyes": {row: "訳"}})
                self.assertEqual(len(got), 1, got)
                self.assertIn(words, got[0])


if __name__ == "__main__":
    unittest.main()
