"""根の直下のファイルとフォルダが根の AGENTS.md の「リポジトリの形」の木に在る物だけ。`workflows/` の直下が `line/`・8 つのブロック・
`.shared/` だけ。各ブロックが `works-factory-<ブロック>.yaml` を持つ。試験のフォルダに `__init__.py` が在る（根の AGENTS.md の機械の行）。

木の名は AGENTS.md から読み、ここに写さない。ブロックの名は tests/layers/scan.py の BLOCKS。
見るファイルは git が知る物と、まだ add していないが無視されない物（.venv・__pycache__ など無視の物は見ない）。
"""
import pathlib
import re
import unittest

from tests.bin.gitkit import git
from tests.layers import scan

ROOT = pathlib.Path(__file__).resolve().parents[2]
TREE = re.compile(r"^## リポジトリの形\n.*?^```text\n(.*?)^```", re.M | re.S)
BRANCH = re.compile(r"^((?:│   |    )*)(?:├── |└── )(.*)$")
SEED = "tests/e2e/target-seed"


def root_names(agents_md):
    """木の根の直下の名の集まり。名の欄（2 つ以上の空白の前）は ・ で並べてよく、/ より後は根の名に関わらない。
    根の直下の欄が空白を含む行は名でなく組の見出しで、その下の 1 段が根の直下の名"""
    lines = TREE.search(agents_md).group(1).splitlines()[1:]
    names, group = set(), False
    for line in lines:
        m = BRANCH.match(line)
        if not m:
            continue
        depth = len(m.group(1)) // 4
        field = re.split(r"\s{2,}", m.group(2).strip())[0]
        if depth == 0:
            group = " " in field
            if group:
                continue
        elif not (depth == 1 and group):
            continue
        names.update(part.split("/")[0] for part in field.split("・"))
    return names


def problems(paths, agents_md):
    """パスの一覧（根からの相対・/ 区切り）が木と食い違う所を 1 行ずつ返す（無ければ空）"""
    out = []
    allowed = root_names(agents_md)
    for top in sorted({p.split("/")[0] for p in paths} - allowed):
        out.append(f"根の直下の {top} が木に無い")
    blocks = set(scan.BLOCKS) | {".shared"}
    flows = [p.split("/", 1)[1] for p in paths if p.startswith("workflows/")]
    for name in sorted({f for f in flows if "/" not in f} - {"AGENTS.md"}):
        out.append(f"workflows/ の直下のファイル {name} は AGENTS.md の外")
    folders = sorted({f.split("/")[0] for f in flows if "/" in f})
    have = set(paths)
    for name in folders:
        if name not in blocks:
            out.append(f"workflows/{name}/ は line・ブロック・.shared のどれでもない")
        elif name != ".shared" and f"workflows/{name}/works-factory-{name}.yaml" not in have:
            out.append(f"workflows/{name}/ に works-factory-{name}.yaml が無い")
    homes = {p.rpartition("/")[0] for p in paths if re.fullmatch(r"test_.*\.py", p.rpartition("/")[2])}
    need = set()
    for home in homes:
        if home == SEED or home.startswith(SEED + "/"):
            continue
        parts = home.split("/")
        need.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
    for folder in sorted(need):
        if f"{folder}/__init__.py" not in have:
            out.append(f"試験のフォルダ {folder}/ に __init__.py が無い")
    if f"{SEED}/__init__.py" in have:
        out.append(f"{SEED}/ に __init__.py が在る（置かない）")
    return out


def real_paths():
    return [p for p in git(ROOT, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0") if p]


def agents_md():
    return (ROOT / "AGENTS.md").read_text(encoding="utf-8")


GOOD = ["AGENTS.md", "lib/__init__.py", "lib/tests/__init__.py", "lib/tests/test_a.py",
        "workflows/AGENTS.md", "workflows/judge/works-factory-judge.yaml", "workflows/.shared/boundary.py",
        f"{SEED}/tests/test_x.py"]


class LayoutTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(problems(real_paths(), agents_md()), [])

    def test_root_names_cover_the_tree(self):
        self.assertLessEqual(
            {"bin", "workflows", "lib", "tests", "docs", ".github", "AGENTS.md", "pyproject.toml", "factory",
             "FACTORY.md", "harness", ".factory", "MISSION.md", "README.md"},
            root_names(agents_md()))

    def test_good_seed_is_clean(self):
        self.assertEqual(problems(GOOD, agents_md()), [])

    def check(self, path, words):
        found = problems([*GOOD, path], agents_md())
        self.assertEqual(len(found), 1, found)
        self.assertIn(words, found[0])

    def test_unknown_root_file(self):
        self.check("notes.txt", "notes.txt")

    def test_unknown_workflows_folder(self):
        self.check("workflows/skills/a.md", "workflows/skills/")

    def test_unknown_workflows_file(self):
        self.check("workflows/README.md", "README.md")

    def test_block_without_its_yaml(self):
        self.check("workflows/plan/commands/a.md", "works-factory-plan.yaml")

    def test_test_folder_without_init(self):
        self.check("lib/tests/deep/test_b.py", "lib/tests/deep/")

    def test_target_seed_with_init(self):
        self.check(f"{SEED}/__init__.py", SEED)


if __name__ == "__main__":
    unittest.main()
