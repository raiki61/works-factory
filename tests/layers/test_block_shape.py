"""blocks/ の block と graph の形の検査（docs/design/README.md の 7.1）。どれも yes/no で、数の上限・許す物の表は持たない。

1. AI の node の prompt: は、同じ workflow の script の node の `$<id>.output.prompt` 1 つだけ。command: を持つ AI の node は無い。
   systemPrompt: を持つなら、同じ prep の `$<id>.output.system` 1 つだけで、prompts/<node-id>.system.md が在る（逆も）
2. AI の node ごとに prompts/<node-id>.md が在り、prompts/ の直下の md はどれもどれかの AI の node の物（<node-id>.md か
   <node-id>.system.md）。prompts/parts/ の md はどれも同じ block のどれかの md から {part:…} で差し込まれる。md の
   {shared:…}・{part:…} の先が在る
3. 指示が standalone の値で組める: standalone の筋書きは exec-code: true で、AI の node の prompt: が指す prep の node を差し替えず、
   AI の node を全部 reached に持つ（prep が prompt.render を本当に通る）。筋書きを Archon の workflow test で回して全部が通る
   （ArchonCase。Archon の源が無ければ見送り、CI は赤）
4. どの workflow にも fixtures/standalone.stubs.yaml が在り、その fixture.inputs の鍵は workflow の inputs: の中にあって pointer の
   値を持たず、必須の入力を全部持つ
5. どの入力の description も `<form>: ` で始まり（form は text・file・flag・json(<schema>)・choice(a|b|…)）、json の <schema> が
   その workflow の schemas/ に在る（shared:<schema> は pack の .shared/schemas/ に在る）。形のファイルの名は pack の中で 1 か所に
   しか無い（2 つ以上の block が使う形は .shared/schemas/ に 1 つ。憲法の 4）
6. ほかの workflow を名指す workflow（include:、自分の外を指す workflow: を持つ物。graph）は AI の node を持たない。block（AI の
   node を持つ物）が起こしてよい workflow は自分だけ
7. scripts/ と src/ の .py に、字 ARTIFACTS_DIR と、ほかの workflow のフォルダへのパス（blocks/<名>・../<名>/・
   .archon/workflows/<pack>/<名>）が無い
8. returns: の node の output_format の properties と required に、outcome_field: の欄と report の欄が在る
9. src/ が在れば __init__.py を持つ package。scripts/ の名は lib/ のモジュールの名・pack の共通の口（.shared/*.py）の名・src と
   重ならない。.shared/*.py の名も lib/ のモジュールの名と重ならない（script のフォルダと .shared が sys.path の頭に来るため）
10. どの workflow にも試験のフォルダ tests/blocks/<名の - を _ にした物>/ が在り、__init__.py と test_*.py を持つ（Python の
   package の名は - を持てない）

今ある yes/no の検査も blocks/ に当てる（ExistingRulesCase）: E6（外への書き込み）・E7（読むだけの node の印）・E12（期限を
置かない）・E16（承認ノードの形）・E19（AI の node の retry）は tests/layers/scan.py の照らしを、blocks/ を workflows/ の場所に写した
一時の木に当てる。uv の script の頭の宣言（4 行）はここで照らす。E1（archon validate が警告なしで通る）は ArchonCase。
"""
import json
import pathlib
import re
import shutil
import tempfile
import unittest

import yaml

from tests import archon
from tests.blocks import kit
from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
BLOCKS = ROOT / "blocks"
SHARED = ".shared"
LIB = ROOT / "lib"
FORM = re.compile(r"^(text|file|flag|json\((shared:)?([A-Za-z0-9_.-]+)\)|choice\([a-z0-9_-]+(?:\|[a-z0-9_-]+)+\)): ")
SYSTEM_REF = re.compile(r"^\$([a-z0-9][a-z0-9_-]*)\.output\.system$")
PROMPT_REF = re.compile(r"^\$([a-z0-9][a-z0-9_-]*)\.output\.prompt$")
FRAGMENT = re.compile(r"\{(shared|part):([a-z0-9][a-z0-9_-]*)\}")
UV_HEAD = ["# /// script", '# requires-python = ">=3.12"', "# dependencies = []", "# ///"]
STANDALONE = "standalone"


def folders(pack: pathlib.Path) -> list[pathlib.Path]:
    """pack の中の workflow のフォルダ（Archon と同じく、dot で始まる物と fixtures を外し、YAML を持つ物）"""
    return sorted(p for p in pack.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name != "fixtures"
                  and any(p.glob("*.yaml")))


def load(folder: pathlib.Path) -> dict:
    [path] = folder.glob("*.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def nodes(doc: dict) -> list[dict]:
    """workflow の node の全部（loop_group の本体も）"""
    out = []
    for node in doc.get("nodes") or []:
        out.append(node)
        out += (node.get("loop_group") or {}).get("nodes") or []
    return out


def is_ai(node: dict) -> bool:
    return "prompt" in node or "command" in node


def ai_nodes(doc: dict) -> list[dict]:
    return [n for n in nodes(doc) if is_ai(n)]


def preps(doc: dict) -> set[str]:
    return {m.group(1) for n in ai_nodes(doc) if isinstance(n.get("prompt"), str) and (m := PROMPT_REF.match(n["prompt"]))}


def fixture(folder: pathlib.Path, name: str = STANDALONE) -> dict | None:
    path = folder / "fixtures" / f"{name}.stubs.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None


def is_pointer(value: str) -> bool:
    try:
        got = json.loads(value)
    except ValueError:
        return False
    return isinstance(got, dict) and got.get("type") == "archon_artifact"


def py_files(folder: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for sub in ("scripts", "src") for p in (folder / sub).rglob("*.py") if "__pycache__" not in p.parts)


# ---------------------------------------------------------------- 7.1 の 9 つ（pack のフォルダを受け、問題の行を返す）
def check_prompt_from_prep(pack: pathlib.Path) -> list[str]:
    out = []
    for folder in folders(pack):
        doc = load(folder)
        scripts = {n["id"] for n in nodes(doc) if "script" in n}
        for node in ai_nodes(doc):
            at = f"{folder.name}: AI の node {node['id']}"
            if "command" in node:
                out.append(f"{at} が command: を持つ（指示は prep の $<id>.output.prompt で受ける）")
                continue
            ref = PROMPT_REF.match(node["prompt"]) if isinstance(node["prompt"], str) else None
            if not ref or ref.group(1) not in scripts:
                out.append(f"{at} の prompt: が同じ workflow の script の node の $<id>.output.prompt でない（{node['prompt']!r:.60}）")
                continue
            system = node.get("systemPrompt")
            has_md = (folder / "prompts" / f"{node['id']}.system.md").is_file()
            sref = SYSTEM_REF.match(system) if isinstance(system, str) else None
            if system is not None and not (sref and sref.group(1) == ref.group(1)):
                out.append(f"{at} の systemPrompt: が prompt: と同じ prep の $<id>.output.system でない（文は prompts/<id>.system.md に置く）")
            elif (system is not None) != has_md:
                out.append(f"{at} の systemPrompt: と prompts/{node['id']}.system.md の片方しか無い")
    return out


def check_prompt_files(pack: pathlib.Path) -> list[str]:
    out = []
    for folder in folders(pack):
        prompts = folder / "prompts"
        ids = {n["id"] for n in ai_nodes(load(folder))}
        mds = {p.stem for p in prompts.glob("*.md")} if prompts.is_dir() else set()
        out += [f"{folder.name}: AI の node {i} の prompts/{i}.md が無い" for i in sorted(ids - mds)]
        out += [f"{folder.name}: prompts/{m}.md はどの AI の node の物でもない" for m in sorted(mds - ids - {f"{i}.system" for i in ids})]
        texts = [p.read_text(encoding="utf-8") for p in prompts.rglob("*.md")] if prompts.is_dir() else []
        refs = {m.groups() for text in texts for m in FRAGMENT.finditer(text)}
        parts = {p.stem for p in (prompts / "parts").glob("*.md")} if (prompts / "parts").is_dir() else set()
        out += [f"{folder.name}: prompts/parts/{p}.md はどの md からも {{part:{p}}} で差し込まれない"
                for p in sorted(parts - {name for kind, name in refs if kind == "part"})]
        for kind, name in sorted(refs):
            where = pack / SHARED / "prompts" if kind == "shared" else prompts / "parts"
            if not (where / f"{name}.md").is_file():
                out.append(f"{folder.name}: {{{kind}:{name}}} の先 {where.relative_to(pack)}/{name}.md が無い")
    return out


def check_standalone_renders(pack: pathlib.Path) -> list[str]:
    out = []
    for folder in folders(pack):
        doc, fx = load(folder), fixture(folder)
        if fx is None or not ai_nodes(doc):
            continue
        at = f"{folder.name}/fixtures/{STANDALONE}.stubs.yaml"
        if fx.get("exec-code") is not True:
            out.append(f"{at} が exec-code: true でない（prep が本当に指示を組まない）")
        stubbed = sorted(preps(doc) & set(fx))
        if stubbed:
            out.append(f"{at} が prep の node {stubbed} を差し替える")
        reached = set((fx.get("fixture") or {}).get("reached") or [])
        missing = sorted({n["id"] for n in ai_nodes(doc)} - reached)
        if missing:
            out.append(f"{at} の reached に AI の node {missing} が無い")
    return out


def check_standalone_inputs(pack: pathlib.Path) -> list[str]:
    out = []
    for folder in folders(pack):
        doc, fx = load(folder), fixture(folder)
        at = f"{folder.name}/fixtures/{STANDALONE}.stubs.yaml"
        if fx is None:
            out.append(f"{at} が無い")
            continue
        declared = doc.get("inputs") or {}
        given = (fx.get("fixture") or {}).get("inputs") or {}
        out += [f"{at}: 入力 {k} が inputs: に無い" for k in sorted(set(given) - set(declared))]
        out += [f"{at}: 入力 {k} が pointer（standalone は文とリポジトリだけで回す）" for k, v in sorted(given.items())
                if isinstance(v, str) and is_pointer(v)]
        required = {k for k, spec in declared.items() if (spec or {}).get("required") is True and "default" not in spec}
        out += [f"{at}: 必須の入力 {k} が無い" for k in sorted(required - set(given))]
    return out


def check_input_forms(pack: pathlib.Path) -> list[str]:
    out = []
    for folder in folders(pack):
        for name, spec in sorted((load(folder).get("inputs") or {}).items()):
            text = (spec or {}).get("description")
            match = FORM.match(text) if isinstance(text, str) else None
            if not match:
                out.append(f"{folder.name}: 入力 {name} の description が `<form>: ` で始まらない")
            elif match.group(3) and not ((pack / SHARED if match.group(2) else folder) / "schemas" / match.group(3)).is_file():
                where = f"{SHARED}/schemas" if match.group(2) else f"{folder.name}/schemas"
                out.append(f"{folder.name}: 入力 {name} の形 {where}/{match.group(3)} が無い")
    homes = {}
    for folder in [pack / SHARED, *folders(pack)]:
        for path in (folder / "schemas").glob("*.json"):
            homes.setdefault(path.name, []).append(folder.name)
    out += [f"形のファイル {n} が {'・'.join(h)} に在る（2 つ以上の block が使う形は {SHARED}/schemas/ に 1 つ）"
            for n, h in sorted(homes.items()) if len(h) > 1]
    return out


def check_graphs_have_no_roles(pack: pathlib.Path) -> list[str]:
    out = []
    for folder in folders(pack):
        doc = load(folder)
        own = doc.get("name")
        named = sorted({n["include"] for n in nodes(doc) if "include" in n}
                       | {n["workflow"] for n in nodes(doc) if "workflow" in n and n["workflow"] != own})
        if named and ai_nodes(doc):
            out.append(f"{folder.name}: ほかの workflow {named} を名指す graph が AI の node "
                       f"{sorted(n['id'] for n in ai_nodes(doc))} を持つ（観点の判断は block に置く）")
    return out


def check_no_run_root_or_other_folders(pack: pathlib.Path) -> list[str]:
    out = []
    names = [f.name for f in folders(pack)]
    for folder in folders(pack):
        others = [re.escape(n) for n in names if n != folder.name]
        path = re.compile(rf"(?:blocks/|\.\./|\.archon/workflows/[^/\s\"']+/)(?:{'|'.join(others)})(?![A-Za-z0-9_-])") if others else None
        for py in py_files(folder):
            text = py.read_text(encoding="utf-8")
            rel = py.relative_to(pack)
            if "ARTIFACTS_DIR" in text:
                out.append(f"{rel}: 字 ARTIFACTS_DIR が在る（place は ports.place で受ける）")
            if path and (hit := path.search(text)):
                out.append(f"{rel}: ほかの workflow のフォルダへのパス {hit.group(0)!r} が在る")
    return out


def check_returns_carry_outcome_and_report(pack: pathlib.Path) -> list[str]:
    out = []
    for folder in folders(pack):
        doc = load(folder)
        sink, field = doc.get("returns"), doc.get("outcome_field")
        node = next((n for n in nodes(doc) if n["id"] == sink), None)
        if not sink or not field or node is None:
            out.append(f"{folder.name}: returns: と outcome_field: と、returns の node が要る")
            continue
        shape = node.get("output_format") or {}
        for want in (field, "report"):
            if want not in (shape.get("properties") or {}) or want not in (shape.get("required") or []):
                out.append(f"{folder.name}: returns の node {sink} の output_format に欄 {want} が無い（properties と required）")
    return out


def check_module_names(pack: pathlib.Path, lib: pathlib.Path = LIB) -> list[str]:
    out = []
    lib_names = {p.stem for p in lib.glob("*.py")} | {p.name for p in lib.iterdir() if p.is_dir() and (p / "__init__.py").is_file()}
    shared = {p.stem for p in (pack / SHARED).glob("*.py")}
    out += [f"{SHARED}/{n}.py の名が lib/ のモジュールと重なる" for n in sorted(shared & lib_names)]
    for folder in folders(pack):
        if (folder / "src").is_dir() and not (folder / "src" / "__init__.py").is_file():
            out.append(f"{folder.name}: src/ に __init__.py が無い（src は package）")
        scripts = {p.stem for p in (folder / "scripts").rglob("*.py")} if (folder / "scripts").is_dir() else set()
        clash = sorted(scripts & (lib_names | shared | {"src"}))
        if clash:
            out.append(f"{folder.name}: scripts/ の名 {clash} が lib/・{SHARED}/ のモジュールか src と重なる")
    return out


def check_block_tests(pack: pathlib.Path, tests: pathlib.Path | None = None) -> list[str]:
    tests = tests or ROOT / "tests" / "blocks"
    out = []
    for folder in folders(pack):
        where = kit.tests_of(folder.name, tests)
        if not (where / "__init__.py").is_file() or not any(where.glob("test_*.py")):
            out.append(f"{folder.name}: 試験のフォルダ tests/blocks/{where.name}/ に __init__.py と test_*.py が無い")
    return out


CHECKS = (check_prompt_from_prep, check_prompt_files, check_standalone_renders, check_standalone_inputs, check_input_forms,
          check_graphs_have_no_roles, check_no_run_root_or_other_folders, check_returns_carry_outcome_and_report, check_module_names,
          check_block_tests)


class RealTreeCase(unittest.TestCase):
    def test_blocks_hold_every_shape(self):
        for check in CHECKS:
            with self.subTest(check=check.__name__):
                self.assertEqual(check(BLOCKS), [])

    def test_uv_script_heads(self):
        for folder in folders(BLOCKS):
            for py in sorted((folder / "scripts").glob("*.py")):
                with self.subTest(script=str(py.relative_to(BLOCKS))):
                    self.assertEqual(py.read_text(encoding="utf-8").splitlines()[:4], UV_HEAD)
            for node in nodes(load(folder)):
                if "script" in node:
                    with self.subTest(node=f"{folder.name}:{node['id']}"):
                        self.assertTrue((folder / "scripts" / f"{node['script']}.py").is_file())
                        self.assertEqual(node.get("runtime"), "uv")


class SeedCase(unittest.TestCase):
    """どの検査も、違反を 1 つ持つ小さな pack で赤になる"""

    GOOD = {
        ".shared/prompts/rejected.md": "{rejection}\n",
        ".shared/ports.py": "",
        "demo/works-factory-demo.yaml": yaml.safe_dump({
            "name": "works-factory-demo",
            "inputs": {"text_in": {"required": True, "description": "text: a"},
                       "doc": {"default": "[]", "description": "json(doc.schema.json): b"},
                       "mode": {"default": "a", "description": "choice(a|b): c"}},
            "returns": "finish", "outcome_field": "ok",
            "nodes": [{"id": "prep", "script": "prep", "runtime": "uv"},
                      {"id": "role", "prompt": "$prep.output.prompt", "depends_on": ["prep"]},
                      {"id": "finish", "script": "finish", "runtime": "uv",
                       "output_format": {"type": "object", "required": ["ok", "report"],
                                         "properties": {"ok": {"type": "boolean"}, "report": {"type": "array"}}}}]}),
        "demo/prompts/role.md": "{shared:rejected}\n{part:rules}\n",
        "demo/prompts/parts/rules.md": "rules\n",
        "demo/schemas/doc.schema.json": "{}",
        "demo/scripts/prep.py": "import ports\n",
        "demo/scripts/finish.py": "import ports\n",
        "demo/src/__init__.py": "",
        "demo/fixtures/standalone.stubs.yaml": yaml.safe_dump({"fixture": {"reached": ["prep", "role", "finish"],
                                                                         "inputs": {"text_in": "x"}},
                                                             "exec-code": True, "role": {}}),
        "other/works-factory-other.yaml": yaml.safe_dump({
            "name": "works-factory-other", "returns": "x", "outcome_field": "ok",
            "nodes": [{"id": "x", "script": "x", "runtime": "uv",
                       "output_format": {"required": ["ok", "report"], "properties": {"ok": {}, "report": {}}}}]}),
        "other/scripts/x.py": "",
        "other/fixtures/standalone.stubs.yaml": yaml.safe_dump({"fixture": {"reached": ["x"]}}),
        "tests-of-blocks/demo/__init__.py": "",
        "tests-of-blocks/demo/test_demo.py": "",
        "tests-of-blocks/other/__init__.py": "",
        "tests-of-blocks/other/test_other.py": "",
    }

    def broken(self, check, changes=None):
        """GOOD の木に changes（パス → 中身。None は消す）を当てて check を回す"""
        files = {k: v for k, v in {**self.GOOD, **(changes or {})}.items() if v is not None}
        with tree(files) as root, tempfile.TemporaryDirectory() as lib:
            (pathlib.Path(lib) / "steps.py").write_text("", encoding="utf-8")
            if check is check_module_names:
                got = check(root, pathlib.Path(lib))
            elif check is check_block_tests:
                got = check(root, root / "tests-of-blocks")
            else:
                got = check(root)
        return got

    def yaml_with(self, **top):
        doc = yaml.safe_load(self.GOOD["demo/works-factory-demo.yaml"])
        doc.update(top)
        return yaml.safe_dump(doc)

    def test_good_seed_is_clean(self):
        for check in CHECKS:
            with self.subTest(check=check.__name__):
                self.assertEqual(self.broken(check), [])

    def test_each_check_catches_its_break(self):
        demo = yaml.safe_load(self.GOOD["demo/works-factory-demo.yaml"])

        def nodes_with(i, **kw):
            copy = json.loads(json.dumps(demo))
            copy["nodes"][i].update(kw)
            return yaml.safe_dump(copy)
        no_report = json.loads(json.dumps(demo))
        no_report["nodes"][2]["output_format"]["required"] = ["ok"]
        cases = [
            (check_prompt_from_prep, {"demo/works-factory-demo.yaml": nodes_with(1, prompt="Do the thing.")}),
            (check_prompt_from_prep, {"demo/works-factory-demo.yaml": nodes_with(1, command="role")}),
            (check_prompt_files, {"demo/prompts/role.md": None}),
            (check_prompt_files, {"demo/prompts/stray.md": "x"}),
            (check_prompt_files, {"demo/prompts/parts/unused.md": "x"}),
            (check_prompt_files, {"demo/prompts/role.md": "{shared:absent}\n{part:rules}\n"}),
            (check_standalone_renders, {"demo/fixtures/standalone.stubs.yaml": yaml.safe_dump(
                {"fixture": {"reached": ["prep", "role", "finish"], "inputs": {"text_in": "x"}}, "role": {}})}),
            (check_standalone_renders, {"demo/fixtures/standalone.stubs.yaml": yaml.safe_dump(
                {"fixture": {"reached": ["prep", "finish"], "inputs": {"text_in": "x"}}, "exec-code": True, "prep": {"prompt": "x"}})}),
            (check_standalone_inputs, {"other/fixtures/standalone.stubs.yaml": None}),
            (check_standalone_inputs, {"demo/fixtures/standalone.stubs.yaml": yaml.safe_dump(
                {"fixture": {"inputs": {"text_in": "x", "extra": "y"}}, "exec-code": True})}),
            (check_standalone_inputs, {"demo/fixtures/standalone.stubs.yaml": yaml.safe_dump(
                {"fixture": {"inputs": {"text_in": '{"type": "archon_artifact", "run_id": "r", "path": "p"}'}}})}),
            (check_standalone_inputs, {"demo/fixtures/standalone.stubs.yaml": yaml.safe_dump({"fixture": {}})}),
            (check_input_forms, {"demo/works-factory-demo.yaml": self.yaml_with(inputs={"a": {"description": "something"}})}),
            (check_input_forms, {"demo/schemas/doc.schema.json": None}),
            (check_graphs_have_no_roles, {"demo/works-factory-demo.yaml": yaml.safe_dump(
                {**demo, "nodes": [*demo["nodes"], {"id": "sub", "include": "works-factory-other"}]})}),
            (check_graphs_have_no_roles, {"demo/works-factory-demo.yaml": yaml.safe_dump(
                {**demo, "nodes": [*demo["nodes"], {"id": "kid", "workflow": "works-factory-other"}]})}),
            (check_no_run_root_or_other_folders, {"demo/scripts/prep.py": "import os\nos.environ['ARTIFACTS_DIR']\n"}),
            (check_no_run_root_or_other_folders, {"demo/src/x.py": "P = '../other/scripts/x.py'\n"}),
            (check_returns_carry_outcome_and_report, {"demo/works-factory-demo.yaml": yaml.safe_dump(no_report)}),
            (check_module_names, {"demo/src/__init__.py": None, "demo/src/steps_of_demo.py": ""}),
            (check_module_names, {"demo/scripts/steps.py": ""}),
            (check_module_names, {"demo/scripts/ports.py": ""}),
            (check_prompt_from_prep, {"demo/works-factory-demo.yaml": nodes_with(1, systemPrompt="You are the role.")}),
            (check_prompt_from_prep, {"demo/prompts/role.system.md": "You are the role.\n"}),
            (check_input_forms, {"other/schemas/doc.schema.json": "{}"}),
            (check_input_forms, {"demo/works-factory-demo.yaml": self.yaml_with(
                inputs={"a": {"description": "json(shared:absent.schema.json): x"}})}),
            (check_block_tests, {"tests-of-blocks/other/test_other.py": None}),
        ]
        for check, changes in cases:
            with self.subTest(check=check.__name__, changes=sorted(changes)):
                self.assertNotEqual(self.broken(check, changes), [])

    def test_self_workflow_is_allowed_in_a_block(self):
        """block が起こしてよい workflow は自分（直しの組ごとに自分を子の run として起こす形）"""
        demo = yaml.safe_load(self.GOOD["demo/works-factory-demo.yaml"])
        doc = yaml.safe_dump({**demo, "nodes": [*demo["nodes"], {"id": "kid", "workflow": "works-factory-demo"}]})
        self.assertEqual(self.broken(check_graphs_have_no_roles, {"demo/works-factory-demo.yaml": doc}), [])


class ExistingRulesCase(unittest.TestCase):
    """今ある yes/no の検査（tests/layers/scan.py）を blocks/ に当てる。scan は木の workflows/ を見るので、blocks/ をそこへ写した一時の木に当てる"""

    RULES = ("E6", "E7", "E12", "E16", "E19")

    def test_existing_rules_hold_on_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            shutil.copytree(BLOCKS, root / "workflows", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copy(ROOT / "pack.json", root / "pack.json")
            shutil.copytree(ROOT / "factory", root / "factory")
            for rule in self.RULES:
                with self.subTest(rule=rule):
                    got = [line.replace("workflows/", "blocks/", 1) for line in scan.problems(rule, root)]
                    self.assertEqual(got, [])


class ArchonCase(unittest.TestCase):
    """E1 と 7.1 の 3: blocks/ の全部の workflow を Archon の validate に通し、全部の筋書きを workflow test で回す"""

    @classmethod
    def setUpClass(cls):
        names = [f.name for f in folders(BLOCKS)]
        try:
            with archon.blocks_tree(names) as root:
                cls.checked = archon.archon(root, "validate", "workflows", "--json", "--cwd", str(root))
                pack = archon.place.pack_folder(archon.PACK, root)
                cls.tested = archon.archon(root, "workflow", "test", str(pack), "--json", "--cwd", str(root))
        except unittest.SkipTest as skip:
            cls.skipped = str(skip)
            return
        cls.skipped = ""

    def setUp(self):
        if self.skipped:
            self.skipTest(self.skipped)

    def test_validate_has_no_issue(self):
        results = json.loads(self.checked.stdout)["results"]
        names = {f"works-factory-{f.name}" for f in folders(BLOCKS)}
        self.assertEqual({r["workflowName"] for r in results} & names, names)
        issues = {r["workflowName"]: [i for i in r["issues"] if archon.counted(i)] for r in results}
        self.assertEqual({k: v for k, v in issues.items() if v}, {})

    def test_every_fixture_passes(self):
        text = self.tested.stdout
        doc = json.JSONDecoder().raw_decode(text[text.index("{"):])[0]
        want = {f"{f.name}/fixtures/{p.name}" for f in folders(BLOCKS) for p in (f / "fixtures").glob("*.stubs.yaml")}
        got = {r["fixture"].split("/", 1)[1]: r for r in doc["results"]}
        self.assertEqual(set(got), want)
        for name, result in sorted(got.items()):
            with self.subTest(fixture=name):
                self.assertTrue(result["pass"], result)
                self.assertEqual((result["missingStubs"], result["unusedStubs"]), ([], []), result)


if __name__ == "__main__":
    unittest.main()
