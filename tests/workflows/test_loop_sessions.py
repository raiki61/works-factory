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
- 拒まれた所だけを出し直す輪（RESUBMIT）は、頭の節の resubmit で 1 回目の役と出し直しの役（<役>-fix）を振り分ける。出し直しの役の
  指示は、出し直しの周にだけ走る出し直しの支度の節（<…>-fix-prep）が md から組み（docs/design/README.md の 7.1 の 1。指示の字は
  YAML に置かない）、出し直しの役は 1 回目の役の後ろの層で、同じ起こし方・同じ型で起きる（型が違うと、Claude Code が型を道具の
  定義として指示の頭に置くので、会話の続きの最初の要求でキャッシュが効かない。#832）。型は根の欄を要ると書かない（要る欄は受け付けが
  rolekit.resubmitted で確かめる）。
  受け付けは両方の返答を if_skipped: null で受ける。plan-review の輪は単独の組（review／review-fix）と束ね役の組（review-tree／
  review-tree-fix）の 2 組で、組ごとに頭の節の tree の条件が when に重なり、出し直しの支度の節は 2 組で 1 つ、受け付けは 4 つの返答を
  if_skipped: null で受ける。頭が resubmit を返す輪は全部 RESUBMIT に在る
- pack は tests/archon.py の WORKFLOWS（入れ替えの前も後も同じ口。docs/design/integration.md の 4.5-11）
"""
import pathlib
import unittest

import yaml

from tests.archon import WORKFLOWS
from tests.bin.stepnames import walk

BLOCKS = sorted(WORKFLOWS.glob("*/works-factory-*.yaml"))

FRESH_BY_DESIGN = {
    ("fix", "clash-loop"): "周ごとに扱う組が替わるので、前の周の組の会話を持ち込まない",
    ("fix", "clash-ruled-loop"): "周ごとに扱う組が替わるので、前の周の組の会話を持ち込まない",
    ("guidance-path", "walk-loop"): "読み手は頼みごとに新しい会話で起こし、前の頼みで見た所を持ち込ませない"
                                    "（docs/design/README.md の 13 節。案内の直しは別の輪の別の役）",
    ("report", "write-loop"): "書き手と初見の読み手が同じ鎖に居て、会話を継ぐと次の周の書き手が初見の読み手の会話の続きで起きる。"
                              "前の周の考えの筋は引き継ぎのメモと前の答えのファイルで渡す（#589）",
}


# (ブロック, 輪) → (頭の節, 出し直しの支度の節, 組の並び, 受け付け)。組は (1 回目の役, 出し直しの役, 頭の節の返りで振り分ける条件,
# 受け付けへの返答の名 2 つ)。組が 1 つの輪は条件が空で、返答の名は reply・fix_reply
ONE = ("", ("reply", "fix_reply"))
RESUBMIT = {
    ("diagnose", "rejudge-loop"): ("rejudge-prep", "rejudge-fix-prep", (("rejudge", "rejudge-fix", *ONE),), "rejudge-accept"),
    ("plan", "plan-loop"): ("plan-prep", "plan-fix-prep", (("plan-writer", "plan-writer-fix", *ONE),), "plan-accept"),
    ("plan-review", "review-loop"): ("review-prep", "review-fix-prep", (
        ("review", "review-fix", "tree != true", ("reply", "fix_reply")),
        ("review-tree", "review-tree-fix", "tree == true", ("tree_reply", "tree_fix_reply"))), "review-accept"),
    ("plan-review", "theme-loop"): ("theme-prep", "theme-fix-prep", (("review-theme", "review-theme-fix", *ONE),), "theme-accept"),
    ("r4", "r4-loop"): ("r4-scope-prep", "r4-scope-fix-prep", (("r4-scope", "r4-scope-fix", *ONE),), "r4-scope-accept"),
    ("spec", "spec-write-loop"): ("spec-write-prep", "spec-write-fix-prep", (("spec-write", "spec-write-fix", *ONE),),
                                  "spec-write-accept"),
    ("spec", "spec-review-loop"): ("spec-review-prep", "spec-review-fix-prep", (("spec-review", "spec-review-fix", *ONE),),
                                   "spec-review-accept"),
    ("spec", "spec-revise-loop"): ("spec-revise-prep", "spec-revise-fix-prep", (("spec-revise", "spec-revise-fix", *ONE),),
                                   "spec-revise-accept"),
    ("theme", "write-loop"): ("write-prep", "theme-fix-prep", (("theme-writer", "theme-writer-fix", *ONE),), "write-accept"),
}
LAUNCH = ("model", "effort", "allowed_tools", "denied_tools", "skills", "plugins", "settingSources", "sandbox", "mutates_checkout",
          "idle_timeout", "retry")
EITHER = "none_failed_min_one_success"   # 飛ばされた節を depends_on に持っても走る trigger_rule


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


def ancestors(body: list[dict], nid: str) -> set[str]:
    """輪の本体の中で、節 nid が depends_on で辿って頼る節の全部"""
    deps = {n["id"]: set(n.get("depends_on") or []) for n in body}
    out, todo = set(), list(deps.get(nid, ()))
    while todo:
        i = todo.pop()
        if i in deps and i not in out:
            out.add(i)
            todo += deps[i]
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
        だけを返す。出し直しの役の指示は出し直しの支度の節が組む。受け付けはどの組の返答も受ける（起きなかった役は null）。plan-review の
        輪は単独と束ね役の 2 組を持ち、組ごとに when に tree の条件が重なる。組の出し直しは、同じ組の 1 回目の後ろの層で、同じ起こし方・
        同じ型（#832。根の欄は要ると書かない）で起きる"""
        found = {(block, n["id"]): n for block, n in loops()}
        for (block, lid), (head, again_prep, pairs, accept) in RESUBMIT.items():
            with self.subTest(block=block, loop=lid):
                group = found[(block, lid)]["loop_group"]
                body = {n["id"]: n for n in group["nodes"]}
                self.assertEqual(group["fresh_context"], False)
                self.assertEqual(body[head]["with"]["prev"], f"$LOOP_PREV.{accept}.output.ok")
                self.assertEqual(body[head]["output_format"]["properties"]["resubmit"], {"type": "boolean"})
                prep = body[again_prep]
                self.assertEqual((prep["when"], prep.get("trigger_rule")), (f"${head}.output.resubmit == true", EITHER))
                self.assertIn(head, prep["depends_on"])
                for role, fix, cond, (reply_name, fix_name) in pairs:
                    tail = f" && ${head}.output.{cond}" if cond else ""
                    first, again = body[role], body[fix]
                    self.assertEqual((first["when"], again["when"]),
                                     (f"${head}.output.resubmit != true{tail}", f"${head}.output.resubmit == true{tail}"))
                    self.assertLessEqual({head, again_prep}, set(again["depends_on"]))
                    self.assertIn(role, ancestors(group["nodes"], fix), f"{fix} が {role} の後ろの層に無い")
                    if role in again["depends_on"]:
                        self.assertEqual(again.get("trigger_rule"), EITHER, f"{fix} は飛ばされた {role} を待って走らない")
                    self.assertNotIn("context", again)
                    self.assertEqual(again["prompt"], f"${again_prep}.output.prompt")
                    self.assertEqual({k: again.get(k) for k in LAUNCH}, {k: first.get(k) for k in LAUNCH})
                    self.assertEqual(again["output_format"], first["output_format"], f"{fix} の型が {role} の型と違う")
                    self.assertEqual(first["output_format"]["required"], [], f"{role} の型が根の欄を要ると書く")
                    self.assertEqual((body[accept]["with"][reply_name], body[accept]["with"][fix_name]),
                                     ({"from": f"${role}.output", "if_skipped": None}, {"from": f"${fix}.output", "if_skipped": None}))
                self.assertEqual((body[accept]["depends_on"], body[accept]["trigger_rule"]),
                                 ([x for pair in pairs for x in pair[:2]], EITHER))

    def test_every_resubmit_head_is_in_the_table(self):
        """頭の節が resubmit を返す輪は全部 RESUBMIT に在る（表の外の輪の振り分けを照らし落とさない）"""
        heads = {(block, n["id"]) for block, n in loops()
                 if "resubmit" in ((n["loop_group"]["nodes"][0].get("output_format") or {}).get("properties") or {})}
        self.assertEqual(sorted(heads ^ set(RESUBMIT)), [])

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
