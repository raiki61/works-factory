"""輪（loop_group）の会話の配線の試験（#571）。全部のブロックの YAML を PyYAML で読むだけ（Archon を起こさない）。

頼っている止めた Archon の振る舞いは tests/shared/test_archon_contract.py の ARCHON_ROWS の 5 行が源の字で縛る:
fresh_context: false の輪は前の周の最後の会話を次の周へ渡し 1 周目はいつも新しい会話・並んだ層は会話を切る・順の節は
並んだ層か context: fresh の時だけ新しい会話・context: fresh の節も順の層で completed になれば次の節の会話のカーソルになる
（FRESH_BY_DESIGN の report の訳が頼る）・名指しの続き（context: resume）は輪の本体の中では輪の前の節だけを指せる。

- 受け付けの出し直しの輪（本体の最後の節の id が accept で終わる輪）は fresh_context: false で、拒まれた後の出し直しは同じ役の
  会話の続きで起きる。外れは FRESH_BY_DESIGN の輪だけ
- fresh_context: false の輪の役（context: fresh でない AI の節）より前の層は全部 1 つの節だけ（並んだ層が在ると、宣言に反して役は
  毎回新しい会話で起きる）
- 周をまたぐ時の新しい会話は、輪の 1 周目がいつも新しい会話であること（上の契約の行）で決まり、この試験では縛らない
- 拒まれた所だけを出し直す輪（RESUBMIT）は、頭の節の resubmit で 1 回目の役と出し直しの役（<役>-fix）を振り分け、出し直しの役は
  1 回目の役の後ろの層で同じ起こし方・同じ型（required を外しただけ）・同じ prompt（FIX_PROMPT）で起き、受け付けは両方の返答を
  if_skipped: null で受ける。plan-review の輪は単独の組（plan-review／plan-review-fix）と束ね役の組（plan-review-tree／
  plan-review-tree-fix）の 2 組で、組ごとに頭の節の tree の条件が when に重なり、受け付けは 4 つの返答を if_skipped: null で受ける。
  eyes の R4 の輪も、R4 の組（r4-scope／r4-scope-fix）とまとめた役の組（eyes-one／eyes-one-fix）の 2 組で、頭の節の one_eye で振り分ける
"""
import pathlib
import unittest

import yaml

from tests.bin.stepnames import walk

ROOT = pathlib.Path(__file__).resolve().parents[2]
BLOCKS = sorted((ROOT / "workflows").glob("*/works-factory-*.yaml"))

FRESH_BY_DESIGN = {
    ("fix", "clash-loop"): "周ごとに扱う組が替わるので、前の周の組の会話を持ち込まない",
    ("fix", "clash-ruled-loop"): "周ごとに扱う組が替わるので、前の周の組の会話を持ち込まない",
    ("report", "write-loop"): "書き手と初見の読み手が同じ鎖に居て、会話を継ぐと次の周の書き手が初見の読み手の会話の続きで起きる。"
                              "前の周の考えの筋は引き継ぎのメモと前の答えのファイルで渡す（#589）",
}


# (ブロック, 輪) → (頭の節, 組の並び, 受け付け)。組は (1 回目の役, 出し直しの役, 頭の節の返りで振り分ける条件, 受け付けへの返答の名 2 つ)。
# 組が 1 つの輪は条件が空で、返答の名は reply・fix_reply
ONE = ("", ("reply", "fix_reply"))
RESUBMIT = {
    ("plan", "plan-loop"): ("plan-prep", (("plan-writer", "plan-writer-fix", *ONE),), "plan-accept"),
    ("plan-review", "review-loop"): ("review-prep", (
        ("plan-review", "plan-review-fix", "tree != true", ("reply", "fix_reply")),
        ("plan-review-tree", "plan-review-tree-fix", "tree == true", ("tree_reply", "tree_fix_reply"))), "review-accept"),
    ("judge", "spec-loop"): ("spec-reject", (("spec", "spec-fix", *ONE),), "spec-accept"),
    ("judge", "spec-review-loop"): ("spec-review-reject", (("spec-review", "spec-review-fix", *ONE),), "spec-review-accept"),
    ("judge", "spec-revise-loop"): ("spec-revise-reject", (("spec-revise", "spec-revise-fix", *ONE),), "spec-revise-accept"),
    ("judge", "rejudge-loop"): ("rejudge-reject", (("rejudge", "rejudge-fix", *ONE),), "rejudge-accept"),
    ("eyes", "r4-loop"): ("r4-reject", (
        ("r4-scope", "r4-scope-fix", "one_eye != true", ("reply", "fix_reply")),
        ("eyes-one", "eyes-one-fix", "one_eye == true", ("one_reply", "one_fix_reply"))), "r4-accept"),
    ("test-gate", "ci-loop"): ("ci-prep", (("ci", "ci-fix", *ONE),), "ci-accept"),
}
# 出し直しの役の prompt（YAML はブロックをまたいで文を共にできないので、9 つの節の字をこの 1 つに縛る）。brief は頭の節の指示書のパスの欄
FIX_PROMPT = ("前の回の返答は受け付けで拒まれた。この会話の続きで直す。指示書 `{brief}` を Read で全部読み、その指示に従え。"
              "返すのは指示書の返し方の形の JSON だけ。")
LAUNCH = ("model", "effort", "allowed_tools", "settingSources", "sandbox", "mutates_checkout", "idle_timeout", "retry")


def loops() -> list[tuple[str, dict]]:
    """(ブロックの名, 輪の節) の並び（全部のブロックの YAML の、入れ子も含む loop_group）"""
    out = []
    for path in BLOCKS:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        out += [(path.parent.name, n) for n in walk(doc["nodes"]) if "loop_group" in n]
    return out


def layers(body: list[dict]) -> list[list[str]]:
    """輪の本体の節の層（Archon と同じく、本体の中の depends_on だけを数える Kahn の層）"""
    deps = {n["id"]: {d for d in n.get("depends_on") or [] if d in {b["id"] for b in body}} for n in body}
    done, out = set(), []
    while len(done) < len(deps):
        layer = [i for i, d in deps.items() if i not in done and d <= done]
        if not layer:
            raise ValueError(f"本体の依存が輪になっている: {sorted(set(deps) - done)}")
        out.append(layer)
        done |= set(layer)
    return out


def parallel_before_role(group: dict) -> list[str]:
    """会話を続ける役（context: fresh でない AI の節）の層とその前に、並んだ層が在る役の名"""
    body = group["loop_group"]["nodes"]
    by_id = {n["id"]: n for n in body}
    split = layers(body)
    out = []
    for k, layer in enumerate(split):
        for i in layer:
            n = by_id[i]
            if ("command" in n or "prompt" in n) and n.get("context") != "fresh" and any(len(x) > 1 for x in split[:k + 1]):
                out.append(i)
    return out


def is_accept_loop(group: dict) -> bool:
    return group["loop_group"]["nodes"][-1]["id"].endswith("accept")


class LoopSessionsTest(unittest.TestCase):
    def test_accept_loops_continue_the_role_conversation(self):
        """受け付けの出し直しの輪は fresh_context: false（外れは FRESH_BY_DESIGN だけ）"""
        for block, n in loops():
            if not is_accept_loop(n) or (block, n["id"]) in FRESH_BY_DESIGN:
                continue
            with self.subTest(block=block, loop=n["id"]):
                self.assertIs(n["loop_group"].get("fresh_context"), False,
                              f"{block} の {n['id']} は受け付けの出し直しの輪なので、拒まれた後は同じ役の会話の続きで出し直させる")

    def test_fresh_by_design_rows_hit_the_tree(self):
        got = {(block, n["id"]): n["loop_group"].get("fresh_context") for block, n in loops()}
        for key in FRESH_BY_DESIGN:
            with self.subTest(loop=key):
                self.assertIs(got.get(key), True, f"表 FRESH_BY_DESIGN の {key} が木に無いか、新しい会話の輪でない")

    def test_continuing_loops_have_no_parallel_layer_before_the_role(self):
        for block, n in loops():
            if n["loop_group"].get("fresh_context") is not False:
                continue
            with self.subTest(block=block, loop=n["id"]):
                self.assertEqual(parallel_before_role(n), [],
                                 f"{block} の {n['id']}: 役の前に並んだ層が在り、会話を続ける宣言に反して役が新しい会話で起きる")

    def test_resubmit_loops_route_to_a_fix_role(self):
        """#571: 拒まれた周の次は、頭の節の resubmit が真なら 1 回目の役を飛ばし、出し直しの役が 1 回目の役の会話の続きで拒まれた所
        だけを返す。受け付けはどの組の返答も受ける（起きなかった役は null）。plan-review の輪は単独と束ね役の 2 組を持ち、組ごとに
        when に tree の条件が重なる。組の出し直しは、同じ組の 1 回目の後ろの層で、同じ起こし方・同じ型（required を外しただけ）・
        同じ FIX_PROMPT で起きる"""
        found = {(block, n["id"]): n for block, n in loops()}
        for (block, lid), (head, pairs, accept) in RESUBMIT.items():
            with self.subTest(block=block, loop=lid):
                body = {n["id"]: n for n in found[(block, lid)]["loop_group"]["nodes"]}
                self.assertEqual(found[(block, lid)]["loop_group"]["fresh_context"], False)
                self.assertEqual(body[head]["with"]["prev"], f"$LOOP_PREV.{accept}.output.ok")
                self.assertEqual(body[head]["output_format"]["properties"]["resubmit"], {"type": "boolean"})
                for role, fix, cond, (reply_name, fix_name) in pairs:
                    tail = f" && ${head}.output.{cond}" if cond else ""
                    first, again = body[role], body[fix]
                    self.assertEqual((first["when"], again["when"]),
                                     (f"${head}.output.resubmit != true{tail}", f"${head}.output.resubmit == true{tail}"))
                    self.assertEqual((again["depends_on"], again["trigger_rule"]), ([head, role], "none_failed_min_one_success"))
                    self.assertNotIn("context", again)
                    self.assertEqual(again["prompt"], FIX_PROMPT.format(brief=f"${head}.output.brief"))
                    self.assertEqual({k: again.get(k) for k in LAUNCH}, {k: first.get(k) for k in LAUNCH})
                    shape, fixed = first["output_format"], dict(again["output_format"])
                    self.assertEqual(fixed.pop("required"), [])
                    extra = set(fixed["properties"]) - set(shape["properties"])
                    self.assertEqual({**fixed, "properties": {k: v for k, v in fixed["properties"].items() if k not in extra}},
                                     {k: v for k, v in shape.items() if k != "required"})
                    self.assertEqual((body[accept]["with"][reply_name], body[accept]["with"][fix_name]),
                                     ({"from": f"${role}.output", "if_skipped": None}, {"from": f"${fix}.output", "if_skipped": None}))
                self.assertEqual((body[accept]["depends_on"], body[accept]["trigger_rule"]),
                                 ([x for pair in pairs for x in pair[:2]], "none_failed_min_one_success"))

    def test_parallel_head_is_caught(self):
        """見本: 頭に依存の無い節が 2 つ在る輪は赤"""
        group = {"loop_group": {"fresh_context": False, "nodes": [
            {"id": "a-prep", "script": "x"}, {"id": "a-reject", "script": "y"},
            {"id": "a", "command": "a", "depends_on": ["a-prep", "a-reject"]},
            {"id": "a-accept", "script": "z", "depends_on": ["a"]}]}}
        self.assertEqual(parallel_before_role(group), ["a"])
        group["loop_group"]["nodes"][1]["depends_on"] = ["a-prep"]
        self.assertEqual(parallel_before_role(group), [])


if __name__ == "__main__":
    unittest.main()
