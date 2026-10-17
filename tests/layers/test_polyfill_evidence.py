"""埋めの名簿 docs/polyfills.md の項目（`### ` の見出し。候補を含む）ごとに、証拠が止めた Archon の源のファイルと引用で在り処を書き、
行番号を書かず、引用の字が止めた版の源の挙げたファイルに 1 か所だけ在る。`P<番号>` の行は、上流の確かめの行が止めた版と読んだ dev の
commit を名指し、「塞がった」には塞いだ upstream の commit か PR を添える。「外した」の項目は源と版の照らしから外す（#672・#690。名簿の頭の決まり）。"""
import pathlib
import re
import unittest
from dataclasses import dataclass

from tests import archon
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs" / "polyfills.md"
ROW = re.compile(r"^(P\d+) ")
REMOVED = "外した"
CITATION = re.compile(r"^  - `([^`]+)` の")
QUOTE = re.compile(r"「([^」]+)」")
LINE_NUMBER = re.compile(r"\d+(?:[-〜–]\d+)? ?行")
FILE_LINE = re.compile(r"[\w-]\.\w+:\d+")
UPSTREAM_REF = re.compile(r"`[0-9a-f]{8,}`|#\d+")


@dataclass
class Entry:
    name: str
    row: bool
    removed: bool
    lines: list[str]


def entries(text: str) -> list[Entry]:
    """`### ` の見出しの項目（コードの囲みの中は除く）。lines は次の見出しまでの字の行"""
    found, current, section, fenced = [], None, "", False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if fenced:
            continue
        if line.startswith("## "):
            section, current = line[3:].strip(), None
        elif line.startswith("### "):
            head = line[4:].strip()
            row = ROW.match(head)
            current = Entry(row.group(1) if row else head, row is not None, section == REMOVED, [])
            found.append(current)
        elif line.startswith("#"):
            current = None
        elif current is not None:
            current.lines.append(line)
    return found


def evidence(lines: list[str]) -> list[str]:
    """`- 証拠:` の行と、その下の字下げした行"""
    out = []
    for line in lines:
        if out and not line.startswith("  "):
            break
        if out or line.startswith("- 証拠:"):
            out.append(line)
    return out


def upstream(entry: Entry, commit: str) -> list[str]:
    """上流の確かめの行が止めた版と読んだ dev の commit を名指し、「塞がった」に塞いだ upstream の commit か PR が在るか"""
    head = re.compile(rf"^- 上流（`{commit[:8]}` の後の dev の `([0-9a-f]{{8,}})` まで）: (.*)")
    results = [m.groups() for m in map(head.match, entry.lines) if m]
    if not results:
        return [f"{entry.name}: 止めた版 {commit[:8]} の後の dev の読んだ commit を名指す上流の確かめの行が無い"]
    # 止めた版と読んだ dev の commit そのものは、塞いだ証拠に数えない
    return [f"{entry.name}: 塞がったと書くのに塞いだ upstream の commit か PR が無い: {result}"
            for dev, result in results
            if "塞がった" in result and not UPSTREAM_REF.search(result.replace(f"`{dev}`", "").replace(f"`{commit[:8]}`", ""))]


def problems(text: str, commit: str, source: pathlib.Path | None) -> list[str]:
    """名簿の字の食い違いを 1 行ずつ返す。source が None なら引用の字の照らしを飛ばす"""
    out = []
    for entry in entries(text):
        name, field = entry.name, evidence(entry.lines)
        citations = field[1:]
        if entry.row and not citations:
            out.append(f"{name}: 証拠の下に源のファイルと引用の行が無い")
        out += [f"{name}: 行番号: {line.strip()}" for line in entry.lines
                if FILE_LINE.search(line) or (line in field and LINE_NUMBER.search(line))]
        for line in citations:
            cited = CITATION.match(line)
            quotes = QUOTE.findall(line)
            if cited is None or not quotes:
                out.append(f"{name}: 証拠の行がファイルのパスと「引用」で始まらない: {line.strip()}")
            elif source is not None and not entry.removed:
                path = source / cited.group(1)
                body = path.read_text(encoding="utf-8") if path.is_file() else ""
                out += [f"{name}: {cited.group(1)} に「{quote}」が {body.count(quote)} か所（1 か所でない）"
                        for quote in quotes if body.count(quote) != 1]
        if entry.row and not entry.removed:
            out += upstream(entry, commit)
    return out


PIN = archon.PACK["archon"]["commit"]
DEV = "f906471c"


def registry(*body: str) -> str:
    return "\n".join(body) + "\n"


class PolyfillEvidenceTest(unittest.TestCase):
    def test_registry_shape(self):
        text = REGISTRY.read_text(encoding="utf-8")
        self.assertGreaterEqual(sum(entry.row for entry in entries(text)), 9)
        self.assertEqual(problems(text, PIN, None), [])

    def test_quotes_are_in_pinned_source(self):
        self.assertEqual(problems(REGISTRY.read_text(encoding="utf-8"), PIN, archon.source()), [])

    def test_quote_missing_from_source_is_red(self):
        text = registry("### P1 穴", "- 証拠:", "  - `a.ts` の「in the file」「not in it」（説明）",
                        f"- 上流（`{PIN[:8]}` の後の dev の `{DEV}` まで）: 塞がっていない。")
        with tree({"a.ts": "// in the file\n"}) as source:
            got = problems(text, PIN, source)
        self.assertEqual(got, ["P1: a.ts に「not in it」が 0 か所（1 か所でない）"])

    def test_quote_hitting_two_places_is_red(self):
        text = registry("### P1 穴", "- 証拠:", "  - `a.ts` の「twice」（説明）",
                        f"- 上流（`{PIN[:8]}` の後の dev の `{DEV}` まで）: 塞がっていない。")
        with tree({"a.ts": "// twice\n// twice more\n"}) as source:
            got = problems(text, PIN, source)
        self.assertEqual(got, ["P1: a.ts に「twice」が 2 か所（1 か所でない）"])

    def test_line_number_is_red(self):
        text = registry("### P1 穴", "- 証拠:", "  - `a.ts` の「x」（12-14 行）",
                        f"- 上流（`{PIN[:8]}` の後の dev の `{DEV}` まで）: 無し")
        self.assertEqual(problems(text, PIN, None), ["P1: 行番号: - `a.ts` の「x」（12-14 行）"])

    def test_file_colon_number_is_red(self):
        text = registry("### P1 穴", "- 証拠:", "  - `a.ts` の「x」（`a.ts:12`）",
                        f"- 上流（`{PIN[:8]}` の後の dev の `{DEV}` まで）: 無し")
        self.assertEqual(problems(text, PIN, None), ["P1: 行番号: - `a.ts` の「x」（`a.ts:12`）"])

    def test_candidate_line_number_is_red(self):
        text = registry("## 今の行", "### 候補（まだ埋めでない）: 口", "- 穴: 無い。証拠: `model-validation.ts:447-483`")
        self.assertEqual(problems(text, PIN, None),
                         ["候補（まだ埋めでない）: 口: 行番号: - 穴: 無い。証拠: `model-validation.ts:447-483`"])

    def test_candidate_quote_is_checked(self):
        text = registry("### 候補（まだ埋めでない）: 口", "- 証拠:", "  - `a.ts` の「absent」")
        with tree({"a.ts": "// present\n"}) as source:
            got = problems(text, PIN, source)
        self.assertEqual(got, ["候補（まだ埋めでない）: 口: a.ts に「absent」が 0 か所（1 か所でない）"])

    def test_template_in_fence_is_not_an_entry(self):
        self.assertEqual(entries(registry("```", "### P<番号> 名", "- 証拠: 文", "```")), [])

    def test_removed_row_skips_source_and_pin(self):
        text = registry("## 外した", "### P1 穴", "- 証拠:", "  - `gone.ts` の「old」",
                        "- 上流（`d97d00ef` の後の dev の `12345678` まで）: 塞がった（`abcdef12`）。")
        with tree({"a.ts": "// present\n"}) as source:
            got = problems(text, PIN, source)
        self.assertEqual(got, [])

    def test_removed_row_still_bans_line_numbers(self):
        text = registry("## 外した", "### P1 穴", "- 証拠:", "  - `a.ts` の「x」（3 行）")
        self.assertEqual(problems(text, PIN, None), ["P1: 行番号: - `a.ts` の「x」（3 行）"])

    def test_citation_without_path_or_quote_is_red(self):
        text = registry("### P1 穴", "- 証拠: 文だけ", "  - 引用の無い行",
                        f"- 上流（`{PIN[:8]}` の後の dev の `{DEV}` まで）: 無し")
        self.assertEqual(problems(text, PIN, None), ["P1: 証拠の行がファイルのパスと「引用」で始まらない: - 引用の無い行"])

    def test_upstream_line_of_other_pin_is_red(self):
        text = registry("### P1 穴", "- 証拠:", "  - `a.ts` の「x」", f"- 上流（`d97d00ef` の後の dev の `{DEV}` まで）: 無し")
        self.assertEqual(problems(text, PIN, None),
                         [f"P1: 止めた版 {PIN[:8]} の後の dev の読んだ commit を名指す上流の確かめの行が無い"])

    def test_upstream_line_without_dev_commit_is_red(self):
        text = registry("### P1 穴", "- 証拠:", "  - `a.ts` の「x」", f"- 上流（`{PIN[:8]}` の後の dev（2026-10-17 まで））: 無し")
        self.assertEqual(problems(text, PIN, None),
                         [f"P1: 止めた版 {PIN[:8]} の後の dev の読んだ commit を名指す上流の確かめの行が無い"])

    def test_closed_without_upstream_commit_is_red(self):
        head = f"- 上流（`{PIN[:8]}` の後の dev の `{DEV}` まで）: "
        text = registry("### P1 穴", "- 証拠:", "  - `a.ts` の「x」", head + "塞がった。")
        self.assertEqual(problems(text, PIN, None), ["P1: 塞がったと書くのに塞いだ upstream の commit か PR が無い: 塞がった。"])
        for named in ("塞がった（`1e2d8acc0`）。", "塞がった（upstream の #4355）。"):
            with self.subTest(named=named):
                self.assertEqual(problems(registry("### P1 穴", "- 証拠:", "  - `a.ts` の「x」", head + named), PIN, None), [])


if __name__ == "__main__":
    unittest.main()
