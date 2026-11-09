"""README の "Running one block on its own" の機械が描く区間を、6 つの部品の YAML の宣言と表 `docs/standalone-blocks.json` から描いて照らす。

縛る事:
- README の印 `<!-- standalone_blocks_begin -->` と `<!-- standalone_blocks_end -->` の間が、`render` が描いた字と 1 字違わず等しい
  （印が無い・始めだけ・2 組在る時は合格にしない）
- 表の入力の名が YAML の `inputs:` に在り、YAML で `required: true` の入力が表に在り、例の名が表の入力に在る
- 表が 6 つの部品の行を持ち、英語の欄と測りの値が欠けない
- 費用が `NOTICE_USD` 以上の部品だけが、呼ぶ前に読む知らせを頭に持つ

表は人が単独で打つ入力の唯一の目録で、必須か・既定・返す node は YAML から描く。筋書き（fixtures）は読まない。

区間を書き直す口: `uv run --isolated python3 -m tests.workflows.test_standalone_blocks --write`（通常の試験の走りでは書かない）。
"""
import copy
import json
import pathlib
import re
import shlex
import sys
import unittest

import yaml

from tests.blocks import kit

ROOT = pathlib.Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
TABLE = ROOT / "docs" / "standalone-blocks.json"
BLOCK_NAMES = ("plan-review", "independent-design", "premises", "prior-decisions", "world", "diagnose")
BEGIN = "<!-- standalone_blocks_begin -->"
END = "<!-- standalone_blocks_end -->"
NOTICE_USD = 1.0
NOTICE = "Read before calling: this block spends real model budget (see the measured cost below); check it before you start the run."
WRITE_COMMAND = "uv run --isolated python3 -m tests.workflows.test_standalone_blocks --write"
MEASURED_KEYS = ("date", "runs", "model", "wall", "cost_usd", "run_id")


class SectionError(ValueError):
    pass


def load_table(path: pathlib.Path = TABLE) -> dict | None:
    """表を読む。ファイルが無ければ None（problems が赤の行にする）"""
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def declared(blocks=BLOCK_NAMES) -> dict:
    """部品ごとの YAML の宣言。YAML が無い部品は載せない"""
    found = {}
    for block in blocks:
        paths = list((kit.BLOCKS / block).glob("works-factory-*.yaml"))
        if len(paths) == 1:
            found[block] = yaml.safe_load(paths[0].read_text(encoding="utf-8"))
    return found


def _default(spec: dict) -> str:
    if "default" not in spec:
        return "(none)"
    value = spec["default"]
    return f"`{value}`" if isinstance(value, str) and value else f"`{json.dumps(value, ensure_ascii=False)}`"


def render_block(row: dict, doc: dict) -> str:
    block, yaml_inputs = row["block"], doc.get("inputs") or {}
    lines = [f"#### `{block}`", ""]
    if row["measured"]["cost_usd"] >= NOTICE_USD:
        lines += [f"> {NOTICE}", ""]
    lines += [f"Returns: {row['returns_en']}", "", "| Input | Required | Default | What to give |", "| --- | --- | --- | --- |"]
    for name, text in row["inputs"].items():
        spec = yaml_inputs.get(name) or {}
        lines.append(f"| `{name}` | {'yes' if spec.get('required') else 'no'} | {_default(spec)} | {text} |")
    rest = len(yaml_inputs) - len(row["inputs"])
    command = f"bin/works-factory workflow run works-factory-{block} --cwd <target>"
    command += "".join(f" --input {name}={shlex.quote(str(value))}" for name, value in row["example"].items())
    m = row["measured"]
    lines += ["", f"{rest} more inputs are wired by the main graph; leave them at their defaults.", "",
              "```sh", command, "```", "", f"Return node: `{doc.get('returns')}`.", "",
              f"Time and cost: measured on {m['date']} ({m['runs']} run{'s' if m['runs'] != 1 else ''}, model {m['model']}): "
              f"{m['wall']} wall time, ${m['cost_usd']:.2f} (run `{m['run_id']}`).", "", f"Reading the return: {row['read_en']}"]
    return "\n".join(lines)


def render(table: dict, docs: dict | None = None) -> str:
    docs = declared() if docs is None else docs
    return "\n\n".join(render_block(row, docs.get(row["block"], {})) for row in table["blocks"])


def section(text: str) -> str:
    """README の印の間を返す。印が無い・1 組でない時は SectionError"""
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SectionError(f"README needs exactly one {BEGIN} and one {END} (found {text.count(BEGIN)} and {text.count(END)})")
    start, end = text.index(BEGIN) + len(BEGIN), text.index(END)
    if end < start:
        raise SectionError(f"{END} comes before {BEGIN}")
    return text[start:end].strip("\n")


def table_problems(table: dict | None, docs: dict | None = None) -> list[str]:
    if table is None:
        return [f"[table] {TABLE.relative_to(ROOT)} is missing"]
    docs = declared() if docs is None else docs
    rows = table.get("blocks") or []
    if not rows:
        return ["[table] the table has no blocks"]
    found = [row.get("block") for row in rows]
    out = []
    if sorted(found) != sorted(BLOCK_NAMES):
        out.append(f"[rows] the table must list exactly {sorted(BLOCK_NAMES)}, found {found}")
    for row in rows:
        block = row.get("block")
        if block not in docs:
            out.append(f"[rows] {block}: no workflow YAML")
            continue
        for key in ("returns_en", "read_en", "inputs", "example", "measured"):
            if not row.get(key):
                out.append(f"[rows] {block}: `{key}` is missing")
        for key in MEASURED_KEYS:
            if (row.get("measured") or {}).get(key) in (None, ""):
                out.append(f"[rows] {block}: measured.{key} is missing")
        yaml_inputs = docs[block].get("inputs") or {}
        listed = row.get("inputs") or {}
        for name in listed:
            if name not in yaml_inputs:
                out.append(f"[inputs] {block}: `{name}` is in the table but not in the YAML inputs")
        for name, spec in yaml_inputs.items():
            if (spec or {}).get("required") is True and name not in listed:
                out.append(f"[inputs] {block}: required input `{name}` is not in the table")
        for name in row.get("example") or {}:
            if name not in listed:
                out.append(f"[inputs] {block}: example input `{name}` is not in the table inputs")
    return out


def problems(readme: str, table: dict | None, docs: dict | None = None) -> list[str]:
    out = table_problems(table, docs)
    try:
        body = section(readme)
    except SectionError as e:
        return out + [f"[markers] {e}"]
    if not out and body != render(table, docs):
        out.append(f"[section] the marked README section differs from the render; rewrite it with: {WRITE_COMMAND}")
    return out


def rewritten(readme: str, table: dict | None, docs: dict | None = None) -> str:
    """`--write` の中身。表が宣言と揃わない時と印が 1 組でない時は、README を返さず止まる。"""
    bad = table_problems(table, docs)
    if bad:
        raise SectionError("refusing to write the section; fix the table first:\n" + "\n".join(bad))
    section(readme)
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
    return pattern.sub(lambda _: f"{BEGIN}\n{render(table, docs)}\n{END}", readme, count=1)


def _of(kind: str, lines: list[str]) -> list[str]:
    return [line for line in lines if line.startswith(f"[{kind}]")]


class StandaloneBlocksCase(unittest.TestCase):
    def setUp(self):
        self.readme = README.read_text(encoding="utf-8")
        self.table = load_table()
        self.docs = declared()

    def need_table(self):
        self.assertIsNotNone(self.table, f"{TABLE.relative_to(ROOT)} is missing")

    def test_readme_section_equals_the_render(self):
        self.need_table()
        self.assertEqual(section(self.readme), render(self.table, self.docs), f"rewrite it with: {WRITE_COMMAND}")

    def test_table_inputs_are_declared_and_cover_required(self):
        self.need_table()
        self.assertEqual(_of("inputs", problems(self.readme, self.table, self.docs)), [])
        self.assertTrue(any(row["inputs"] for row in self.table["blocks"]))

    def test_every_block_has_its_rows(self):
        self.need_table()
        self.assertEqual(_of("rows", problems(self.readme, self.table, self.docs)) + _of("table", problems(self.readme, self.table, self.docs)), [])
        self.assertEqual(sorted(row["block"] for row in self.table["blocks"]), sorted(BLOCK_NAMES))
        self.assertTrue(_of("table", problems(self.readme, {"blocks": []}, self.docs)), "an empty table must be red")

    def test_markers_missing_or_doubled_are_red(self):
        self.need_table()
        self.assertIn(BEGIN, self.readme)
        self.assertIn(END, self.readme)
        body = section(self.readme)
        cases = {
            "no markers": self.readme.replace(BEGIN, "").replace(END, ""),
            "begin only": self.readme.replace(END, ""),
            "end only": self.readme.replace(BEGIN, ""),
            "two pairs": self.readme + f"\n{BEGIN}\n{body}\n{END}\n",
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                self.assertRaises(SectionError, section, text)
                self.assertTrue(_of("markers", problems(text, self.table, self.docs)))

    def test_injected_regressions_are_red(self):
        self.need_table()
        self.assertEqual(problems(self.readme, self.table, self.docs), [])
        body = section(self.readme)
        first = self.table["blocks"][0]
        needs = next(b for b in self.table["blocks"] if any((s or {}).get("required") for n, s in self.docs[b["block"]]["inputs"].items() if n in b["inputs"]))
        required = next(n for n, s in self.docs[needs["block"]]["inputs"].items() if (s or {}).get("required") and n in needs["inputs"])

        def table_with(change):
            table = copy.deepcopy(self.table)
            change(table)
            return table

        def docs_with(change):
            docs = copy.deepcopy(self.docs)
            change(docs)
            return docs

        def drop_required(t):
            row = next(r for r in t["blocks"] if r["block"] == needs["block"])
            del row["inputs"][required]
            row["example"].pop(required, None)

        def rename_yaml_input(d):
            inputs = d[first["block"]]["inputs"]
            name = next(iter(first["inputs"]))
            inputs[name + "_renamed"] = inputs.pop(name)

        mutated = body[:10] + ("X" if body[10] != "X" else "Y") + body[11:]
        injections = {
            "one character of the section": ("section", self.readme.replace(body, mutated), self.table, self.docs),
            "a YAML input renamed": ("inputs", self.readme, self.table, docs_with(rename_yaml_input)),
            "an undeclared name in the table": ("inputs", self.readme, table_with(lambda t: t["blocks"][0]["inputs"].update({"no_such_input": "x"})), self.docs),
            "a required input removed from the table": ("inputs", self.readme, table_with(drop_required), self.docs),
            "an example name not in the table": ("inputs", self.readme, table_with(lambda t: t["blocks"][0]["example"].update({"no_such_input": "x"})), self.docs),
            "markers removed": ("markers", self.readme.replace(BEGIN, "").replace(END, ""), self.table, self.docs),
        }
        for name, (kind, readme, table, docs) in injections.items():
            with self.subTest(injection=name):
                found = problems(readme, table, docs)
                self.assertTrue(_of(kind, found), f"{name}: expected a [{kind}] line, got {found}")
                if kind == "section":
                    self.assertIn(WRITE_COMMAND, " ".join(found))

    def test_write_refuses_a_table_that_disagrees_with_the_declarations(self):
        self.need_table()
        self.assertEqual(rewritten(self.readme, self.table, self.docs), self.readme)
        broken = copy.deepcopy(self.table)
        broken["blocks"][0]["inputs"]["no_such_input"] = "x"
        with self.assertRaises(SectionError):
            rewritten(self.readme, broken, self.docs)
        with self.assertRaises(SectionError):
            rewritten(self.readme, {"blocks": []}, self.docs)
        with self.assertRaises(SectionError):
            rewritten(self.readme, None, self.docs)

    def test_costly_blocks_carry_the_notice(self):
        self.need_table()
        costly = set()
        for row in self.table["blocks"]:
            text = render_block(row, self.docs[row["block"]])
            with self.subTest(block=row["block"]):
                has = NOTICE in text
                self.assertEqual(has, row["measured"]["cost_usd"] >= NOTICE_USD)
                if has:
                    costly.add(row["block"])
                    self.assertEqual(text.splitlines()[2], f"> {NOTICE}", "the notice comes right after the heading")
        self.assertEqual(costly, {"plan-review", "diagnose"})


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        try:
            README.write_text(rewritten(README.read_text(encoding="utf-8"), load_table()), encoding="utf-8")
        except SectionError as e:
            sys.exit(str(e))
        print(f"wrote {README}")
    else:
        unittest.main()
