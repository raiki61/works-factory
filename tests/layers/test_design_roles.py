"""docs/design.md の「## サブグラフ」の各節の役の一覧（`- 役（`commands/`）: …`）が、そのサブグラフの `workflows/<名>/commands/` の
直下と合う（#533）。一覧は 1 文目（最初の「。」まで）の `…` で囲んだ字で、`*` を含む字は名の型、`/` で終わる字はフォルダ。
直下の .md とフォルダの全部が一覧のどれかに当たり、一覧の字の全部が直下のどれかに当たる。`commands/` の無いサブグラフの節は一覧を持たない。
"""
import fnmatch
import pathlib
import re
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
DESIGN = ROOT / "docs" / "design.md"
SUBGRAPHS_HEAD = "## サブグラフ"
SECTION = re.compile(r"^### ([a-z-]+)（")
ROLES = "- 役（`commands/`）: "
CODE = re.compile(r"`([^`\n]+)`")


def listed(text: str) -> dict[str, list[list[str]]]:
    """サブグラフの名 → その節の役の一覧の行ごとの字の並び"""
    found, name, inside = {}, None, False
    for line in text.splitlines():
        if line.startswith("## "):
            inside, name = line == SUBGRAPHS_HEAD, None
        elif inside and (m := SECTION.match(line)):
            name = m.group(1)
            found[name] = []
        elif name and line.startswith(ROLES):
            found[name].append(CODE.findall(line[len(ROLES):].split("。", 1)[0]))
    return found


def present(commands: pathlib.Path) -> list[str]:
    return sorted(p.stem if p.is_file() else p.name + "/" for p in commands.iterdir()
                  if p.is_dir() or p.suffix == ".md")


def problems(text: str, workflows: pathlib.Path) -> list[str]:
    out = []
    for name, lines in listed(text).items():
        commands = workflows / name / "commands"
        if not commands.is_dir():
            out += [f"{name}: commands/ が無いのに役の一覧が在る"] if lines else []
            continue
        if len(lines) != 1:
            out.append(f"{name}: 役の一覧の行が {len(lines)} 個（1 個でない）")
            continue
        names, have = lines[0], present(commands)
        out += [f"{name}: 一覧の {n} が commands/ に無い" for n in names if not fnmatch.filter(have, n)]
        out += [f"{name}: commands/ の {h} が一覧に無い" for h in have if not any(fnmatch.fnmatchcase(h, n) for n in names)]
    return out


class DesignRoles(unittest.TestCase):
    def test_role_lists_match_commands(self):
        text = DESIGN.read_text(encoding="utf-8")
        self.assertTrue(listed(text), "docs/design.md に「## サブグラフ」の節が無い")
        self.assertEqual(problems(text, ROOT / "workflows"), [])

    def test_drift_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            commands = pathlib.Path(tmp) / "judge" / "commands"
            (commands / "rules").mkdir(parents=True)
            for stem in ("spec", "material-a", "material-b", "rejudge"):
                (commands / f"{stem}.md").write_text("", encoding="utf-8")
            (pathlib.Path(tmp) / "line").mkdir()
            doc = "\n".join([SUBGRAPHS_HEAD, "### judge（判定）", ROLES + "`spec`・`material-*`・`rules/`・`gone`。`rejudge` は後で書く。",
                             "### line（メイングラフ）", ROLES + "`x`。", "## 次"])
            self.assertEqual(problems(doc, pathlib.Path(tmp)), [
                "judge: 一覧の gone が commands/ に無い", "judge: commands/ の rejudge が一覧に無い",
                "line: commands/ が無いのに役の一覧が在る"])
