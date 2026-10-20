"""根の直下のファイルとフォルダが、根の `AGENTS.md` の「リポジトリの形」の木に在る物だけ（根の `AGENTS.md` の機械の行）。

- 木の名は AGENTS.md から読み、ここに写さない。木は「リポジトリの形」の ```text の中の行で、1 行は `├── 名   説明` の形。名の欄（`├── ` などの線の後から、2 つ以上の空白の前まで）は `・` で並べてよく、`/` より後は根の直下の名に関わらない。根の直下の段（字下げの 1 段目）の名の欄が空白を含む行（例 `ASF の取り付け命令が置いた物`）は、名でなく組の見出しで、その下の 1 段（字下げの 2 段目）の名を根の直下の名に数える。木の根の直下の名は 1 度だけ。
- `workflows/` の直下は、`works-factory-<名>.yaml` を持つフォルダ（block と graph）・`.shared/`・`AGENTS.md` だけ。直下のフォルダが自分の名の YAML を持たなければ赤（block の名の表は持たない。持ち主の決め `shape-checks-only`）。
- 試験を置くフォルダ（`test_*.py` の在るフォルダとその上の全部）に `__init__.py` が在る（無いと Python 3.12 の unittest は黙って見つけない）。小さな対象のリポジトリの種 `tests/e2e/target-seed/` には置かない。
- 見るファイルは git が知る物と、まだ add していないが無視されない物（`.venv`・`__pycache__` など無視の物は見ない）。
"""
import pathlib
import re
import unittest

from tests.bin.gitkit import git

ROOT = pathlib.Path(__file__).resolve().parents[2]
TREE = re.compile(r"^## リポジトリの形\n.*?^```text\n(.*?)^```", re.M | re.S)
BRANCH = re.compile(r"^((?:│   |    )*)(?:├── |└── )(.*)$")
SEEDS = ("tests/e2e/target-seed",)


def root_names(agents_md):
    return set(root_entries(agents_md))


def root_entries(agents_md):
    """木の根の直下の名の並び（木に書いた順・重なりも残す）。名の欄（2 つ以上の空白の前）は ・ で並べてよく、/ より後は根の名に関わらない。
    根の直下の欄が空白を含む行は名でなく組の見出しで、その下の 1 段が根の直下の名"""
    lines = TREE.search(agents_md).group(1).splitlines()[1:]
    names, group = [], False
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
        names.extend(part.split("/")[0] for part in field.split("・"))
    return names


def problems(paths, agents_md):
    """パスの一覧（根からの相対・/ 区切り）が木と食い違う所を 1 行ずつ返す（無ければ空）"""
    entries = root_entries(agents_md)
    out = [f"木の根の直下の {name} が 2 度在る" for name in sorted({n for n in entries if entries.count(n) > 1})]
    allowed = set(entries)
    for top in sorted({p.split("/")[0] for p in paths} - allowed):
        out.append(f"根の直下の {top} が木に無い")
    flows = [p.split("/", 1)[1] for p in paths if p.startswith("workflows/")]
    for name in sorted({f for f in flows if "/" not in f} - {"AGENTS.md"}):
        out.append(f"workflows/ の直下のファイル {name} は AGENTS.md の外")
    folders = sorted({f.split("/")[0] for f in flows if "/" in f} - {".shared"})
    have = set(paths)
    for name in folders:
        if f"workflows/{name}/works-factory-{name}.yaml" not in have:
            out.append(f"workflows/{name}/ に works-factory-{name}.yaml が無い（直下のフォルダは自分の名の YAML を持つ block・graph と .shared だけ）")
    homes = {p.rpartition("/")[0] for p in paths if re.fullmatch(r"test_.*\.py", p.rpartition("/")[2])}
    need = set()
    for home in homes:
        if any(home == seed or home.startswith(seed + "/") for seed in SEEDS):
            continue
        parts = home.split("/")
        need.update("/".join(parts[:i]) for i in range(1, len(parts) + 1))
    for folder in sorted(need):
        if f"{folder}/__init__.py" not in have:
            out.append(f"試験のフォルダ {folder}/ に __init__.py が無い")
    for seed in SEEDS:
        if f"{seed}/__init__.py" in have:
            out.append(f"{seed}/ に __init__.py が在る（置かない）")
    return out


def real_paths():
    return [p for p in git(ROOT, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0") if p]


def agents_md():
    return (ROOT / "AGENTS.md").read_text(encoding="utf-8")


GOOD = ["AGENTS.md", "lib/__init__.py", "lib/tests/__init__.py", "lib/tests/test_a.py",
        "workflows/AGENTS.md", "workflows/judge/works-factory-judge.yaml", "workflows/.shared/ports.py",
        *(f"{seed}/tests/test_x.py" for seed in SEEDS)]


class LayoutTest(unittest.TestCase):
    def test_real_tree_clean(self):
        self.assertEqual(problems(real_paths(), agents_md()), [])

    def test_root_names_cover_the_tree(self):
        self.assertLessEqual(
            {"bin", "workflows", "lib", "tests", "docs", ".github", "AGENTS.md", "pyproject.toml", "factory",
             "FACTORY.md", ".factory", "MISSION.md", "README.md"},
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
        self.check("workflows/skills/a.md", "workflows/skills/ に works-factory-skills.yaml が無い")

    def test_any_folder_with_its_yaml_is_clean(self):
        self.assertEqual(problems([*GOOD, "workflows/any-name/works-factory-any-name.yaml"], agents_md()), [])

    def test_folder_with_another_name_yaml(self):
        self.check("workflows/plan/works-factory-judge.yaml", "works-factory-plan.yaml")

    def test_unknown_workflows_file(self):
        self.check("workflows/README.md", "README.md")

    def test_block_without_its_yaml(self):
        self.check("workflows/plan/commands/a.md", "works-factory-plan.yaml")

    def test_test_folder_without_init(self):
        self.check("lib/tests/deep/test_b.py", "lib/tests/deep/")

    def test_target_seed_with_init(self):
        self.check("tests/e2e/target-seed/__init__.py", "tests/e2e/target-seed")

    def test_root_name_listed_twice(self):
        tree = agents_md()
        line = next(ln for ln in tree.splitlines() if ln.startswith("├── pack.json "))
        found = problems(GOOD, tree.replace(line, f"{line}\n{line}", 1))
        self.assertEqual(found, ["木の根の直下の pack.json が 2 度在る"])


if __name__ == "__main__":
    unittest.main()
