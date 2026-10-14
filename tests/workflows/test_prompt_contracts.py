"""役の指示書ごとに、書き直しの前後で変えない 4 つを約束の表 `prompt_contracts.json` に照らす（持ち主の決め `prompts-coldread`）。

- 差し込みの名（`inserts`）: 本文から機械で抜いた `$…`・`{{…}}`・`［材料:…］`・`<<…>>` の字の集まりが表と同じ。
- 返す JSON の形（`returns`）: その指示書を使うノードの並びと、その `output_format` の正規の JSON の sha256 と、本文が `"欄":` の形で
  書く欄の名の集まりが表と同じ。
- 禁じた入力（`forbidden`）・手順の順（`steps`）・止める条件（`stops`）: 各項目の `quote` が本文に在り、`steps` は表の順に並ぶ。
  `forbidden` の `quote` は否定・限定の語か命令の結びまで含む（`POLARITY`）。
  `what` が凍った意味で、書き直しで変えてよいのは `quote` だけ（`what` が変わっていないことは、約束を置いた commit との差分を人が見る）。

表の鍵は、`workflows/*/commands/` の下の全部・`lib/agents/*.md`・グラフの YAML のノードの `prompt`・`systemPrompt`
（`<YAML のパス>#<ノードの id>.<鍵>`）。木の指示書と表の鍵は過不足なく同じ。
"""
import functools
import hashlib
import json
import pathlib
import re
import sys
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))

import judge_accept  # noqa: E402
import planblk  # noqa: E402
import policy  # noqa: E402
import rulebook  # noqa: E402
CONTRACTS = pathlib.Path(__file__).resolve().parent / "prompt_contracts.json"
INLINE_KEYS = ("prompt", "systemPrompt")
INSERT = re.compile(r"(?a:\$[A-Za-z_][\w-]*(?:\.[\w-]+)*)|\{\{[^}]*\}\}|［材料:[^］]*］|" + rulebook.HOLE.pattern)
JSON_KEY = re.compile(r'"([A-Za-z_]\w*)"\s*:', re.ASCII)
SPACE = re.compile(r"\s")
# 禁じた入力の quote は否定・限定の語か命令の結びまで含む。否定が quote の外に在ると、禁止を許可に裏返しても quote は本文に残る
POLARITY = re.compile(r"ない|無[いく]|禁|ず|だけ|のみ|止|しか|拒|でなく|な(?![ぁ-ん])|[けせれろよ](?=[。）*]|$)|\bnot\b", re.IGNORECASE)


def _nodes(nodes):
    for node in nodes:
        yield node
        if "loop_group" in node:
            yield from _nodes(node["loop_group"]["nodes"])


@functools.cache
def graph_nodes(root):
    """`(YAML の根からのパス, ノード)` を全部のグラフについて"""
    found = []
    for path in sorted(pathlib.Path(root).glob("workflows/*/*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        found += [(path.relative_to(root).as_posix(), node) for node in _nodes(doc.get("nodes", []))]
    return found


def prompts(root):
    """{表の鍵: 本文}"""
    root = pathlib.Path(root)
    files = [p for p in root.glob("workflows/*/commands/**/*") if p.is_file()] + list(root.glob("lib/agents/*.md"))
    out = {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in sorted(files)}
    for rel, node in graph_nodes(root):
        for key in INLINE_KEYS:
            if key in node:
                out[f"{rel}#{node['id']}.{key}"] = node[key]
    return out


def users(root, key):
    """その指示書を使うノード `<YAML のパス>#<id>` → ノード。`command:` は同じフォルダの `commands/<名>.md` を指す"""
    found = {}
    for rel, node in graph_nodes(root):
        if "#" in key:
            hit = key == f"{rel}#{node['id']}.{key.rsplit('.', 1)[1]}"
        else:
            hit = "command" in node and key == f"{pathlib.PurePosixPath(rel).parent}/commands/{node['command']}.md"
        if hit:
            found[f"{rel}#{node['id']}"] = node
    return found


def shape_sha(nodes):
    """ノードの `output_format` の正規の JSON の sha256。ノードが無ければ None、ノードで形が違えば形の数を字で"""
    shapes = {json.dumps(n.get("output_format"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
              for n in nodes.values()}
    if not shapes:
        return None
    if len(shapes) > 1:
        return f"{len(shapes)} 通りの形"
    return hashlib.sha256(shapes.pop().encode("utf-8")).hexdigest()


def measured(root, key, text):
    """機械で抜ける 2 つ（差し込みの名・返す JSON の形）"""
    nodes = users(root, key)
    return {
        "inserts": sorted({m.group() for m in INSERT.finditer(text)}),
        "returns": {"nodes": sorted(nodes), "output_format_sha256": shape_sha(nodes),
                    "json_keys": sorted(set(JSON_KEY.findall(text)))},
    }


def quote_problems(key, text, contract):
    """`forbidden`・`steps`・`stops` の `quote` が本文に無い・`steps` が順に並ばない・`forbidden` の `quote` が否定を含まない。空白は比べない"""
    flat = SPACE.sub("", text)
    out = []
    for kind in ("forbidden", "steps", "stops"):
        pos = 0
        for item in contract[kind]:
            quote = SPACE.sub("", item["quote"])
            if kind == "forbidden" and not POLARITY.search(item["quote"]):
                out.append(f"{key}: forbidden の「{item['what']}」の quote が否定・限定の語を含まない: {item['quote']!r}")
            at = flat.find(quote, pos) if quote else -1
            if at < 0:
                where = "の後ろ" if kind == "steps" and pos else ""
                out.append(f"{key}: {kind} の「{item['what']}」の quote が本文{where}に無い: {item['quote']!r}")
            elif kind == "steps":
                pos = at + len(quote)
    return out


def problems(root, contracts):
    found = prompts(root)
    out = [f"{key}: 約束の表に無い" for key in sorted(found.keys() - contracts.keys())]
    out += [f"{key}: 木に無い" for key in sorted(contracts.keys() - found.keys())]
    for key in sorted(found.keys() & contracts.keys()):
        contract, text = contracts[key], found[key]
        got = measured(root, key, text)
        out += [f"{key}: {part} が {got[part]!r}（表は {contract[part]!r}）" for part in got if got[part] != contract[part]]
        out += quote_problems(key, text, contract)
    return out


class PromptContractsTest(unittest.TestCase):
    def test_every_prompt_keeps_its_contract(self):
        contracts = json.loads(CONTRACTS.read_text(encoding="utf-8"))
        self.assertEqual(problems(ROOT, contracts), [])

    def test_recorded_policy_readers_name_the_section(self):
        """#427: 方針とのぶつかりを見る役の指示書と事前審査の頭は、同じ「記録された方針」のセクションを指す。目的と制約だけを読む
        独立設計の役（r2-design）は指さない"""
        self.assertEqual(policy.RECORDED_HEAD, "## 記録された方針")
        for rel in ("workflows/judge/commands/diagnose.md", "workflows/judge/commands/material-prior-decisions.md",
                    "workflows/plan-review/commands/plan-review.md", "workflows/eyes/commands/r3-coherence.md",
                    "workflows/eyes/commands/r4-scope.md"):
            with self.subTest(rel):
                self.assertIn(policy.RECORDED_REF, (ROOT / rel).read_text(encoding="utf-8"))
        self.assertIn(policy.RECORDED_REF, planblk.HANDOFF_REVIEW)
        self.assertNotIn(policy.RECORDED_TERM, (ROOT / "workflows/plan-review/commands/r2-design.md").read_text(encoding="utf-8"))

    def test_diagnose_names_the_premise_three_mark_the_acceptance_reads(self):
        """#427: 受け付けが ③ の名乗りと読むのは undecided_because の頭の印だけ。指示書はその印とその置き場を書く"""
        text = (ROOT / "workflows/judge/commands/diagnose.md").read_text(encoding="utf-8")
        self.assertIn("`undecided_because` の頭に印", text)
        self.assertIn(f"頭の印に {judge_accept.PREMISE_THREE} を書くなら", text)
        self.assertTrue(judge_accept.claims_premise_three(f"{judge_accept.PREMISE_THREE} 記録された方針の行とぶつかる"))

    def test_quote_must_be_in_the_text(self):
        contract = {"forbidden": [{"what": "道具を呼ばない", "quote": "道具を呼ぶな"}], "steps": [], "stops": []}
        got = quote_problems("a.md", "道具は使わない。", contract)
        self.assertEqual(len(got), 1)
        self.assertIn("道具を呼ばない", got[0])

    def test_forbidden_quote_must_carry_its_negation(self):
        text = "使える道具は与えられたものだけで、それ以外——ファイルの作成・編集・削除を含む——もできる。"
        bare = {"forbidden": [{"what": "作成・編集・削除しない", "quote": "ファイルの作成・編集・削除を含む"}], "steps": [], "stops": []}
        self.assertEqual(len(quote_problems("a.md", text, bare)), 1)
        held = {"forbidden": [{"what": "作成・編集・削除しない", "quote": "ファイルの作成・編集・削除を含む——はできない"}],
                "steps": [], "stops": []}
        self.assertEqual(len(quote_problems("a.md", text, held)), 1, "否定を裏返すと quote が本文に無い")
        for quote in ("道具を呼ぶな", "写しは一時の置き場に作れ", "Do not modify code"):
            contract = {"forbidden": [{"what": "x", "quote": quote}], "steps": [], "stops": []}
            self.assertEqual(quote_problems("a.md", quote, contract), [], quote)

    def test_quote_ignores_whitespace(self):
        contract = {"forbidden": [{"what": "道具を呼ばない", "quote": "道具を 呼ぶな"}], "steps": [], "stops": []}
        self.assertEqual(quote_problems("a.md", "道具を\n呼ぶな。", contract), [])

    def test_steps_must_keep_their_order(self):
        steps = [{"what": "読む", "quote": "読め"}, {"what": "返す", "quote": "返せ"}]
        contract = {"forbidden": [], "steps": steps, "stops": []}
        self.assertEqual(quote_problems("a.md", "1. 読め。2. 返せ。", contract), [])
        self.assertEqual(len(quote_problems("a.md", "1. 返せ。2. 読め。", contract)), 1)

    def test_inserts_are_pinned(self):
        text = "`$prep.output.brief_file` を読み、{{record.units | pick key}} と ［材料: inputs.cwd］ と <<diff_file>> を見よ。$ARTIFACTS_DIRの下"
        self.assertEqual(measured(ROOT, "a.md", text)["inserts"],
                         ["$ARTIFACTS_DIR", "$prep.output.brief_file", "<<diff_file>>", "{{record.units | pick key}}", "［材料: inputs.cwd］"])

    def test_json_keys_are_pinned(self):
        text = '`{"rulings": [{"id": "<id>", "text": "…"}]}` を返す'
        self.assertEqual(measured(ROOT, "a.md", text)["returns"]["json_keys"], ["id", "rulings", "text"])

    def test_command_node_shape_is_pinned(self):
        nodes = users(ROOT, "workflows/plan/commands/fix-plan.md")
        self.assertEqual(sorted(nodes), ["workflows/plan/works-factory-plan.yaml#plan-writer"])
        self.assertRegex(shape_sha(nodes), r"^[0-9a-f]{64}$")

    def test_new_and_stale_keys_are_red(self):
        contracts = json.loads(CONTRACTS.read_text(encoding="utf-8"))
        contracts["workflows/plan/commands/gone.md"] = contracts.pop("workflows/plan/commands/fix-plan.md")
        got = problems(ROOT, contracts)
        self.assertIn("workflows/plan/commands/fix-plan.md: 約束の表に無い", got)
        self.assertIn("workflows/plan/commands/gone.md: 木に無い", got)


if __name__ == "__main__":
    unittest.main()
