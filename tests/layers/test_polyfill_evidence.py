"""埋めの名簿 docs/polyfills.md の `### P<番号>` の行ごとに、証拠が止めた Archon の源のファイルと引用で在り処を書き、行番号を
書かず、引用の字が止めた版の源に字のまま在る。上流の確かめの行が止めた版を名指す（#672。名簿の頭の決まり）。"""
import pathlib
import re
import unittest

from tests import archon
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs" / "polyfills.md"
ROW = re.compile(r"^### (P\d+) ")
CITATION = re.compile(r"^  - `([^`]+)` の")
QUOTE = re.compile(r"「([^」]+)」")
LINE_NUMBER = re.compile(r"\d+(?:-\d+)? ?行")


def rows(text: str) -> dict[str, list[str]]:
    """行の名 → その行の欄の字の行（次の見出しまで）"""
    found, current = {}, None
    for line in text.splitlines():
        if line.startswith("#"):
            head = ROW.match(line)
            current = found.setdefault(head.group(1), []) if head else None
        elif current is not None:
            current.append(line)
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


def problems(text: str, commit: str, source: pathlib.Path | None) -> list[str]:
    """名簿の字の食い違いを 1 行ずつ返す。source が None なら引用の字の照らしを飛ばす"""
    out = []
    for name, lines in rows(text).items():
        field = evidence(lines)
        citations = field[1:]
        if not citations:
            out.append(f"{name}: 証拠の下に源のファイルと引用の行が無い")
        out += [f"{name}: 証拠に行番号: {line.strip()}" for line in field if LINE_NUMBER.search(line)]
        for line in citations:
            cited = CITATION.match(line)
            quotes = QUOTE.findall(line)
            if cited is None or not quotes:
                out.append(f"{name}: 証拠の行がファイルのパスと「引用」で始まらない: {line.strip()}")
            elif source is not None:
                path = source / cited.group(1)
                body = path.read_text(encoding="utf-8") if path.is_file() else None
                out += [f"{name}: {cited.group(1)} に「{quote}」が無い" for quote in quotes
                        if body is None or quote not in body]
        if not any(line.startswith(f"- 上流（`{commit[:8]}` の後の dev") for line in lines):
            out.append(f"{name}: 止めた版 {commit[:8]} の後の上流の確かめの行が無い")
    return out


PIN = archon.PACK["archon"]["commit"]


class PolyfillEvidenceTest(unittest.TestCase):
    def test_registry_shape(self):
        text = REGISTRY.read_text(encoding="utf-8")
        self.assertGreaterEqual(len(rows(text)), 9)
        self.assertEqual(problems(text, PIN, None), [])

    def test_quotes_are_in_pinned_source(self):
        self.assertEqual(problems(REGISTRY.read_text(encoding="utf-8"), PIN, archon.source()), [])

    def test_quote_missing_from_source_is_red(self):
        registry = ("### P1 穴\n- 証拠:\n  - `a.ts` の「in the file」「not in it」（説明）\n"
                    f"- 上流（`{PIN[:8]}` の後の dev（2026-10-17 まで））: 塞がっていない。\n")
        with tree({"a.ts": "// in the file\n"}) as source:
            got = problems(registry, PIN, source)
        self.assertEqual(got, ["P1: a.ts に「not in it」が無い"])

    def test_line_number_is_red(self):
        registry = f"### P1 穴\n- 証拠:\n  - `a.ts` の「x」（12-14 行）\n- 上流（`{PIN[:8]}` の後の dev）: 無し\n"
        self.assertEqual(problems(registry, PIN, None), ["P1: 証拠に行番号: - `a.ts` の「x」（12-14 行）"])

    def test_citation_without_path_or_quote_is_red(self):
        registry = f"### P1 穴\n- 証拠: 文だけ\n  - 引用の無い行\n- 上流（`{PIN[:8]}` の後の dev）: 無し\n"
        self.assertEqual(problems(registry, PIN, None), ["P1: 証拠の行がファイルのパスと「引用」で始まらない: - 引用の無い行"])

    def test_upstream_line_of_other_pin_is_red(self):
        registry = "### P1 穴\n- 証拠:\n  - `a.ts` の「x」\n- 上流（`d97d00ef` の後の dev）: 無し\n"
        self.assertEqual(problems(registry, PIN, None), [f"P1: 止めた版 {PIN[:8]} の後の上流の確かめの行が無い"])


if __name__ == "__main__":
    unittest.main()
