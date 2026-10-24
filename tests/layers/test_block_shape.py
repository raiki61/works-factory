"""pack（tests/archon.py の WORKFLOWS。組み込みの入れ替えの後の workflows/）の block と graph の形の検査（docs/design/README.md の 7.1）。どれも yes/no で、数の上限・許す物の表は持たない。

1. AI の node の prompt: は、同じ workflow の script の node の `$<id>.output.prompt` 1 つだけ。command: を持つ AI の node は無い。
   systemPrompt: を持つなら、同じ prep の `$<id>.output.system` 1 つだけで、prompts/<node-id>.system.md が在る（逆も）
2. AI の node ごとに prompts/<node-id>.md が在り、prompts/ の直下の md はどれもどれかの AI の node の物（<node-id>.md か
   <node-id>.system.md）。prompts/parts/ の md はどれも同じ block のどれかの md から {part:…} で差し込まれるか、同じ block の
   scripts/・src/ の prompt.render_part("<name>" の呼び（コメントと文の字の中は数えない）が名指す。md の
   {shared:…}・{part:…} の先が在る
3. 指示が筋書きの値で md から組める: standalone の筋書きは exec-code: true。どの AI の node も、exec-code: true でその prep を
   差し替えない筋書きのどれかで reached に在り、その筋書きの resolved-text-contains が、その node の md の決まった文（断片を
   入れ、差し込み口と段落の印で割った字）の一続きの中に在る（prep が md を prompt.render で本当に組んだ証）。standalone の筋書きの
   AI の node の resolved-text-contains は、どれも決まった文。筋書きで届かない node（workflow: の fan_out の先・loop の 2 周目）は、block の
   試験 tests/blocks/<block>/test_prompts.py の表 RENDERED（{node の id: md の決まった文}）に行が在り、その字が md の決まった文の中に在れば
   照らされたと数える（表の行で prep を回して照らすのは試験の側）。筋書きを Archon の workflow test で回して全部が通る（ArchonCase。
   Archon の源が無ければ見送り、CI は赤）
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
11. YAML に指示の文を置く鍵が無い: loop: の node（loop_group と prep で書く）・agents:・on_reject の prompt・decisions の rework の
   prompt。形のファイル（block の schemas/ と .shared/schemas/）は照らしの知らない語を持たない（ports.unknown_keywords）
10. どの workflow にも試験のフォルダ tests/blocks/<名の - を _ にした物>/ が在り、__init__.py と test_*.py を持つ（Python の
   package の名は - を持てない）
12. AI の node の md（と system の md。{shared:…}・{part:…} を入れた後）に `"欄":` の形で書いた欄が、その node の output_format の
   どこかの深さの properties に在る（形に無い欄は Archon の構造化の出力が拒むので、役は指示が求める欄を返せない。
   docs/design/integration.md の 4.2-2。tests/workflows/test_reply_fields.py の後継。指示の文は md だけなので lib の字は辿らない）
13. include: の node（loop_group の本体の中の物も）の id が、include する workflow の中のどの node の id（上の段も、どの深さの
   loop_group の本体も）とも違う。Archon の include の展開（packages/workflows/src/include-expander.ts）は、取り込む workflow の
   上の段の id だけを `<include の id>__<id>` に改め、loop_group の本体の中の `$<id>.output` は改めない。同じ id だと、本体の中の
   `$<id>.output` が include の returns の node を指してしまい、本当の run で「その node はまだ出力を持たない」と落ちる
   取り込む workflow がさらに取り込む workflow（line → eyes → r4 の 2 段）の繰り返しの中の node と、同じ graph の別の include が持ち込む
   繰り返しの中の node の id も同じに数える。
   （筋書きはこれを捕まえない: graph の筋書きは include した block の入口と出口を台本で差し替えて中の loop を回さず、block の筋書きは
   block を単独で回す。dry-run は include の中の loop の本体に include の道を渡さないので、本体の script を本物で回す graph の筋書きも組めない）
14. .shared/prompts/ の断片が頭の 1 行に `<!-- required-for-tools: <道具> <道具> -->` の印を持つなら、そのどれかの道具を allowed_tools に持つ
   AI の node の指示（md と system の md。{shared:…}・{part:…} を入れた後）に、その断片が入っている。段落（<!-- if … -->）の中だけに
   在って段落が外れると消える場合は入っていないと数える（全部の段落を真にした組み立てと全部を偽にした組み立ての両方に在ることを求める。
   組み立ては workflows/.shared/prompt.py の `_select`）。道具に結びつく断片の印は断片自身が持ち、別の対応表は持たない（憲法の 6）

今ある yes/no の検査も pack（workflows/）に当てる（ExistingRulesCase）: E6（外への書き込み）・E7（読むだけの node の印）・E12（期限を
置かない）・E16（承認ノードの形）・E19（AI の node の retry）は tests/layers/scan.py の照らしを、pack を一時の木の workflows/ に写して
当てる。uv の script の頭の宣言（4 行）はここで照らす。E1（archon validate が警告なしで通る）は ArchonCase。
"""
import ast
import json
import pathlib
import re
import shutil
import sys
import tempfile
import unittest

import yaml

from tests import archon
from tests.workflows import test_uv_scripts as uv_scripts
from tests.blocks import kit
from tests.layers import scan
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
BLOCKS = archon.WORKFLOWS   # pack のフォルダ workflows/（pack.json の ours.folder から読む。docs/design/integration.md の 4.5-11）
SHARED = ".shared"
LIB = ROOT / "lib"
FORM = re.compile(r"^(text|file|flag|json\((shared:)?([A-Za-z0-9_.-]+)\)|choice\([a-z0-9_-]+(?:\|[a-z0-9_-]+)+\)): ")
SYSTEM_REF = re.compile(r"^\$([a-z0-9][a-z0-9_-]*)\.output\.system$")
PROMPT_REF = re.compile(r"^\$([a-z0-9][a-z0-9_-]*)\.output\.prompt$")
FRAGMENT = re.compile(r"\{(shared|part):([a-z0-9][a-z0-9_-]*)\}")
RENDER_PART_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")   # workflows/.shared/prompt.py の NODE_ID と同じ字（render_part はほかの名を拒む）
MARK = re.compile(r"^<!-- (if|if not|end) ([a-z0-9_]+) -->$")
REQUIRED_FOR_TOOLS = re.compile(r"\A<!-- required-for-tools: ([A-Za-z]+(?: [A-Za-z]+)*) -->\n")   # workflows/.shared/prompt.py の同名と同じ形
JSON_KEY = re.compile(r'"([A-Za-z_]\w*)"\s*:', re.ASCII)
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
    """workflow の node の全部（どの深さの loop_group の本体も。fix の相談の答えの役は修正の輪の中の輪に在る）"""
    return all_nodes(doc.get("nodes"))


def all_nodes(listed) -> list[dict]:
    """node の全部（どの深さの loop_group の本体も）"""
    out = []
    for node in listed or []:
        out.append(node)
        out += all_nodes((node.get("loop_group") or {}).get("nodes"))
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


def render_part_names(text: str) -> set[str]:
    """Python の字の中の prompt.render_part("<name>", …) の呼びが名指す断片の名（コメントと文の字の中の物は呼びでないので数えない。
    名が RENDER_PART_NAME に合わない呼びは回すと落ちるので数えない）"""
    try:
        tree_ = ast.parse(text)
    except SyntaxError:
        return set()
    return {call.args[0].value for call in ast.walk(tree_)
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "render_part"
            and isinstance(call.func.value, ast.Name) and call.func.value.id == "prompt" and call.args
            and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str)
            and RENDER_PART_NAME.fullmatch(call.args[0].value)}


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
        called = {name for path in py_files(folder) for name in render_part_names(path.read_text(encoding="utf-8"))}
        out += [f"{folder.name}: prompts/parts/{p}.md はどの md からも {{part:{p}}} で差し込まれない（prompt.render_part(\"{p}\" の呼びも無い）"
                for p in sorted(parts - {name for kind, name in refs if kind == "part"} - called)]
        for kind, name in sorted(refs):
            where = pack / SHARED / "prompts" if kind == "shared" else prompts / "parts"
            if not (where / f"{name}.md").is_file():
                out.append(f"{folder.name}: {{{kind}:{name}}} の先 {where.relative_to(pack)}/{name}.md が無い")
    return out


def fixed_text(pack: pathlib.Path, folder: pathlib.Path, node_id: str) -> list[str]:
    """node の md（と system の md）の決まった文の一続きの並び: 断片を入れ、差し込み口と段落の印の行で割った字"""
    chunks = []
    for name in (f"{node_id}.md", f"{node_id}.system.md"):
        path = folder / "prompts" / name
        if not path.is_file():
            continue
        text = _expand(path.read_text(encoding="utf-8"), pack, folder)
        lines = [line for line in text.split("\n") if not MARK.match(line.strip())]
        chunks += [c for c in re.split(r"\{[a-z0-9_]+\}", "\n".join(lines).replace("{{", "{").replace("}}", "}")) if c.strip()]
    return chunks


def _expand(text: str, pack: pathlib.Path, folder: pathlib.Path, depth: int = 0) -> str:
    def one(m):
        kind, name = m.groups()
        path = (pack / SHARED / "prompts" if kind == "shared" else folder / "prompts" / "parts") / f"{name}.md"
        return _expand(path.read_text(encoding="utf-8").rstrip("\n"), pack, folder, depth + 1) if path.is_file() and depth < 8 else ""
    return FRAGMENT.sub(one, text)


def rendered_rows(folder: pathlib.Path, tests: pathlib.Path | None = None) -> dict:
    """block の試験 tests/blocks/<block>/test_prompts.py の表 RENDERED（{node の id: md の決まった文}。表の行を照らすのは試験の側で、
    ここは表の在りと字だけを読む）。無ければ {}"""
    path = kit.tests_of(folder.name, *([tests] if tests else [])) / "test_prompts.py"
    if not path.is_file():
        return {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "RENDERED" for t in node.targets):
            try:
                got = ast.literal_eval(node.value)
            except ValueError:
                return {}
            return got if isinstance(got, dict) else {}
    return {}


def check_standalone_renders(pack: pathlib.Path, tests: pathlib.Path | None = None) -> list[str]:
    out = []
    for folder in folders(pack):
        doc = load(folder)
        if not ai_nodes(doc):
            continue
        prep_of = {n["id"]: PROMPT_REF.match(n["prompt"]).group(1) for n in ai_nodes(doc)
                   if isinstance(n.get("prompt"), str) and PROMPT_REF.match(n["prompt"])}
        fixtures = {p.name.removesuffix(".stubs.yaml"): yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                    for p in sorted((folder / "fixtures").glob("*.stubs.yaml"))}
        standalone = fixtures.get(STANDALONE)
        at = f"{folder.name}/fixtures/{STANDALONE}.stubs.yaml"
        if standalone is not None and standalone.get("exec-code") is not True:
            out.append(f"{at} が exec-code: true でない（prep が本当に指示を組まない）")
        for node in ai_nodes(doc):
            nid = node["id"]
            chunks = fixed_text(pack, folder, nid)
            proved = False
            for name, fx in fixtures.items():
                decl = fx.get("fixture") or {}
                said = (decl.get("resolved-text-contains") or {}).get(nid)
                runs = fx.get("exec-code") is True and nid in (decl.get("reached") or []) and prep_of.get(nid) not in fx
                fixed = isinstance(said, str) and any(said in c for c in chunks)
                if name == STANDALONE and said is not None and not fixed:
                    out.append(f"{at} の resolved-text-contains の {nid} が prompts/{nid}.md の決まった文の中に無い（値でなく md の文で照らす）")
                proved |= runs and fixed
            reached = any(nid in ((fx.get("fixture") or {}).get("reached") or []) for fx in fixtures.values())
            rendered = rendered_rows(folder, tests).get(nid)   # 表の行は筋書きで届かない node だけを照らす（届く node は筋書きで照らす）
            proved |= not reached and isinstance(rendered, str) and any(rendered in c for c in chunks)
            if not proved:
                out.append(f"{folder.name}: AI の node {nid} の指示を md から組んだと照らす筋書きが無い（exec-code: true・prep を差し替えない・"
                           f"reached に在る・resolved-text-contains が md の決まった文。筋書きで届かない node は試験の表 RENDERED の行）")
    return out


TEXT_KEYS_PARENT = ("on_reject", "rework")


def _text_keys(value, at: str) -> list[str]:
    out = []
    if isinstance(value, dict):
        for key, sub in value.items():
            if key == "agents":
                out.append(f"{at}.agents")
            elif key == "prompt" and at.rsplit(".", 1)[-1].split("[")[0] in TEXT_KEYS_PARENT:
                out.append(f"{at}.prompt")
            out += _text_keys(sub, f"{at}.{key}")
    elif isinstance(value, list):
        for i, sub in enumerate(value):
            out += _text_keys(sub, f"{at}[{i}]")
    return out


def check_no_text_in_yaml(pack: pathlib.Path) -> list[str]:
    from_ports = _ports().unknown_keywords
    out = []
    for folder in folders(pack):
        for node in nodes(load(folder)):
            if "loop" in node:
                out.append(f"{folder.name}: node {node['id']} が loop: を持つ（指示の文が YAML に入る。loop_group と prep で書く）")
            out += [f"{folder.name}: node {node['id']} が {hit} を持つ（指示の文は md に置く）"
                    for hit in _text_keys({k: v for k, v in node.items() if k not in ("output_format",)}, node["id"])]
    for path in sorted([*(pack / SHARED / "schemas").glob("*.json"), *[p for f in folders(pack) for p in (f / "schemas").glob("*.json")]]):
        try:
            unknown = from_ports(json.loads(path.read_text(encoding="utf-8")))
        except ValueError as error:
            unknown = [f"JSON でない: {error}"]
        if unknown:
            out.append(f"{path.relative_to(pack)}: 照らしの知らない語 {unknown}")
    return out


def _ports():
    import importlib
    if str(BLOCKS / SHARED) not in sys.path:
        sys.path.append(str(BLOCKS / SHARED))
    return importlib.import_module("ports")


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


def shape_names(shape) -> set:
    """形のどの深さの `properties` の名も（`patternProperties` の鍵は名でない）"""
    if isinstance(shape, list):
        return set().union(*map(shape_names, shape))
    if not isinstance(shape, dict):
        return set()
    names = set((shape.get("properties") or {}).keys())
    for key in ("properties", "patternProperties"):
        names |= shape_names(list((shape.get(key) or {}).values()))
    for key in ("items", "additionalProperties", "anyOf", "oneOf", "allOf"):
        names |= shape_names(shape.get(key))
    return names


def _prompt():
    _ports()
    import importlib
    return importlib.import_module("prompt")


def check_tool_fragments(pack: pathlib.Path) -> list[str]:
    select = _prompt()._select
    marked = {}   # 断片の名 → (印の行, 道具の集合)
    for path in sorted((pack / SHARED / "prompts").glob("*.md")):
        if m := REQUIRED_FOR_TOOLS.match(path.read_text(encoding="utf-8")):
            marked[path.stem] = (m.group(0).strip(), set(m.group(1).split()))
    out = []
    for folder in folders(pack):
        for node in ai_nodes(load(folder)):
            tools = set(node.get("allowed_tools") or [])
            texts = [_expand(path.read_text(encoding="utf-8"), pack, folder)
                     for path in (folder / "prompts" / f"{node['id']}.md", folder / "prompts" / f"{node['id']}.system.md") if path.is_file()]
            for name, (line, needs) in sorted(marked.items()):
                if not tools & needs:
                    continue
                names = {m.group(2) for text in texts for row in text.split("\n") if (m := MARK.match(row.strip()))}
                if not any(all(line in select(text, dict.fromkeys(names, state))[0] for state in (True, False)) for text in texts):
                    out.append(f"{folder.name}: AI の node {node['id']} は道具 {sorted(tools & needs)} を持つが、指示（md）に {{shared:{name}}} が"
                               f"（段落に頼らずには）入っていない")
    return out


def check_reply_fields(pack: pathlib.Path) -> list[str]:
    out = []
    for folder in folders(pack):
        for node in ai_nodes(load(folder)):
            texts = [_expand(path.read_text(encoding="utf-8"), pack, folder)
                     for path in (folder / "prompts" / f"{node['id']}.md", folder / "prompts" / f"{node['id']}.system.md")
                     if path.is_file()]
            missing = sorted({k for t in texts for k in JSON_KEY.findall(t)} - shape_names(node.get("output_format") or {}))
            if missing:
                out.append(f"{folder.name}: AI の node {node['id']} の md が書く欄 {missing} が output_format に無い")
    return out


def check_include_ids_unique(pack: pathlib.Path) -> list[str]:
    docs = {load(folder).get("name"): load(folder) for folder in folders(pack)}

    def body_ids(name, seen=()) -> set:
        """name の workflow が展開後も改められずに残る id: loop_group の本体の中の node と、取り込む workflow の同じ物（何段でも）"""
        doc = docs.get(name)
        if doc is None or name in seen:
            return set()
        out = set()
        for node in all_nodes(doc.get("nodes")):
            out |= {n["id"] for n in all_nodes((node.get("loop_group") or {}).get("nodes"))}
            out |= body_ids(node.get("include"), (*seen, name))
        return out

    def inner_ids(name) -> set:
        doc = docs.get(name)
        if doc is None:
            return set()
        return {n["id"] for n in all_nodes(doc.get("nodes"))} | body_ids(name)

    out = []
    for folder in folders(pack):
        includes = [n for n in all_nodes(load(folder).get("nodes")) if n.get("include")]
        for node in includes:
            if node["id"] in inner_ids(node["include"]):
                out.append(f"{folder.name}: include の node {node['id']} の id が、取り込む {node['include']} の中の node の id"
                           f"（その先で取り込む workflow の繰り返しの中の node も含む）と同じ"
                           f"（本体の中の ${node['id']}.output が include の returns を指してしまう。include の id を <名>-run などに変える）")
            for other in includes:
                if other is not node and node["id"] in body_ids(other["include"]):
                    out.append(f"{folder.name}: include の node {node['id']} の id が、同じ graph の別の include {other['id']}"
                               f"（{other['include']}）が持ち込む繰り返しの中の node の id と同じ"
                               f"（その本体の中の ${node['id']}.output が include の returns を指してしまう。include の id を <名>-run などに変える）")
    return out


CHECKS = (check_prompt_from_prep, check_prompt_files, check_standalone_renders, check_standalone_inputs, check_input_forms,
          check_graphs_have_no_roles, check_no_run_root_or_other_folders, check_returns_carry_outcome_and_report, check_module_names,
          check_block_tests, check_no_text_in_yaml, check_reply_fields, check_include_ids_unique, check_tool_fragments)


class RealTreeCase(unittest.TestCase):
    def test_blocks_hold_every_shape(self):
        for check in CHECKS:
            with self.subTest(check=check.__name__):
                self.assertEqual(check(BLOCKS), [])

    def test_uv_script_heads(self):
        for folder in folders(BLOCKS):
            for py in sorted((folder / "scripts").glob("*.py")):
                with self.subTest(script=str(py.relative_to(BLOCKS))):
                    # 表（YAML）を読む script の外しの持ち主は tests/workflows/test_uv_scripts.py の header_of（lib/AGENTS.md の E3）
                    self.assertEqual(py.read_text(encoding="utf-8").splitlines()[:4], uv_scripts.header_of(py, BLOCKS))
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
                                                                         "inputs": {"text_in": "x"},
                                                                         "resolved-text-contains": {"role": "rules"}},
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
            elif check in (check_block_tests, check_standalone_renders):
                got = check(root, root / "tests-of-blocks")
            else:
                got = check(root)
        return got

    def nested_include(self, loop_id, include_id, *, sibling):
        """demo の繰り返しの中に node loop_id を置き、other に id loop_id の include を足した木の変更。sibling が偽なら other が mid を取り込み、
        mid が demo を取り込む 2 段（line → eyes → r4 の形）。真なら other の別の include include_id が demo を取り込む（同じ graph の別の include）"""
        demo = yaml.safe_load(self.GOOD["demo/works-factory-demo.yaml"])
        other = yaml.safe_load(self.GOOD["other/works-factory-other.yaml"])
        demo["nodes"] = [*demo["nodes"], {"id": "outer", "loop_group": {"nodes": [{"id": loop_id, "script": "prep"}]}}]
        mid = {"name": "works-factory-mid", "returns": "x", "outcome_field": "ok",
               "nodes": [{"id": include_id, "include": "works-factory-demo"}]}
        if sibling:
            other["nodes"] = [*other["nodes"], {"id": include_id, "include": "works-factory-demo"},
                              {"id": loop_id, "include": "works-factory-mid"}]
            mid["nodes"] = [{"id": "x", "script": "x"}]
        else:
            other["nodes"] = [*other["nodes"], {"id": loop_id, "include": "works-factory-mid"}]
        return {"demo/works-factory-demo.yaml": yaml.safe_dump(demo), "other/works-factory-other.yaml": yaml.safe_dump(other),
                "mid/works-factory-mid.yaml": yaml.safe_dump(mid)}

    def tool_fragment(self, role_md, tools=("Read", "WebSearch")):
        """道具に結びつく断片 tooly（印 WebSearch・WebFetch のどれか）を足し、demo の role が道具 tools を持ち md が role_md の木の変更"""
        demo = yaml.safe_load(self.GOOD["demo/works-factory-demo.yaml"])
        demo["nodes"][1]["allowed_tools"] = list(tools)
        return {".shared/prompts/tooly.md": "<!-- required-for-tools: WebSearch WebFetch -->\ntooly\n",
                "demo/works-factory-demo.yaml": yaml.safe_dump(demo), "demo/prompts/role.md": role_md}

    def test_tool_fragment_is_taken_without_depending_on_a_paragraph(self):
        """印の道具を持つ node の md が断片を段落の外で入れる（part の中でもよい）か、印の道具を持たない node なら赤にならない"""
        for role_md, tools in (("{shared:tooly}\n", ("WebFetch",)), ("{part:rules}\n", ("WebFetch",)), ("rules\n", ("Read", "Bash"))):
            with self.subTest(role_md=role_md, tools=tools):
                changes = self.tool_fragment(role_md, tools)
                changes["demo/prompts/parts/rules.md"] = "{shared:tooly}\n"
                self.assertEqual(self.broken(check_tool_fragments, changes), [])

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
        other = yaml.safe_load(self.GOOD["other/works-factory-other.yaml"])

        def nodes_with(i, **kw):
            copy = json.loads(json.dumps(demo))
            copy["nodes"][i].update(kw)
            return yaml.safe_dump(copy)
        no_report = json.loads(json.dumps(demo))
        no_report["nodes"][2]["output_format"]["required"] = ["ok"]
        def fixture_with(**decl):
            base = {"reached": ["prep", "role", "finish"], "inputs": {"text_in": "x"}, "resolved-text-contains": {"role": "rules"}}
            return {"demo/fixtures/standalone.stubs.yaml": yaml.safe_dump({"fixture": {**base, **decl}, "exec-code": True, "role": {}})}
        with_loop = {**demo, "nodes": [*demo["nodes"], {"id": "again", "loop": {"prompt": "Say it.", "until": "DONE"}}]}
        with_agents = nodes_with(1, agents={"helper": {"description": "d", "prompt": "Help."}})
        with_reject = nodes_with(2, on_reject={"prompt": "Fix it.", "max_attempts": 2})
        with_rework = {**demo, "nodes": [*demo["nodes"], {"id": "gate", "wait": {"attention": "a", "decisions": [{"rework": {"prompt": "x"}}]}}]}
        cases = [
            (check_prompt_from_prep, {"demo/works-factory-demo.yaml": nodes_with(1, prompt="Do the thing.")}, "$<id>.output.prompt でない"),
            (check_prompt_from_prep, {"demo/works-factory-demo.yaml": nodes_with(1, command="role")}, "command: を持つ"),
            (check_prompt_from_prep, {"demo/works-factory-demo.yaml": nodes_with(1, systemPrompt="You are the role.")}, "systemPrompt: が"),
            (check_prompt_from_prep, {"demo/prompts/role.system.md": "You are the role.\n"}, "片方しか無い"),
            (check_prompt_files, {"demo/prompts/role.md": None}, "prompts/role.md が無い"),
            (check_prompt_files, {"demo/prompts/stray.md": "x"}, "prompts/stray.md はどの AI の node の物でもない"),
            (check_prompt_files, {"demo/prompts/parts/unused.md": "x"}, "{part:unused} で差し込まれない"),
            (check_prompt_files, {"demo/prompts/role.md": "{shared:absent}\n{part:rules}\n"}, "{shared:absent} の先"),
            (check_standalone_renders, {"demo/fixtures/standalone.stubs.yaml": yaml.safe_dump(
                {"fixture": {"reached": ["prep", "role", "finish"], "inputs": {"text_in": "x"}}, "role": {}})}, "exec-code: true でない"),
            (check_standalone_renders, {"demo/fixtures/standalone.stubs.yaml": yaml.safe_dump(
                {"fixture": {"reached": ["prep", "role", "finish"], "inputs": {"text_in": "x"}, "resolved-text-contains": {"role": "rules"}},
                 "exec-code": True, "prep": {"prompt": "rules"}})}, "照らす筋書きが無い"),
            (check_standalone_renders, fixture_with(reached=["prep", "finish"]), "照らす筋書きが無い"),
            (check_standalone_renders, fixture_with(**{"resolved-text-contains": {"role": "x"}}), "決まった文の中に無い"),
            (check_standalone_renders, fixture_with(**{"resolved-text-contains": {}}), "照らす筋書きが無い"),
            (check_standalone_inputs, {"other/fixtures/standalone.stubs.yaml": None}, "standalone.stubs.yaml が無い"),
            (check_standalone_inputs, {"demo/fixtures/standalone.stubs.yaml": yaml.safe_dump(
                {"fixture": {"inputs": {"text_in": "x", "extra": "y"}}, "exec-code": True})}, "入力 extra が inputs: に無い"),
            (check_standalone_inputs, {"demo/fixtures/standalone.stubs.yaml": yaml.safe_dump(
                {"fixture": {"inputs": {"text_in": '{"type": "archon_artifact", "run_id": "r", "path": "p"}'}}})}, "pointer"),
            (check_standalone_inputs, {"demo/fixtures/standalone.stubs.yaml": yaml.safe_dump({"fixture": {}})}, "必須の入力 text_in"),
            (check_input_forms, {"demo/works-factory-demo.yaml": self.yaml_with(inputs={"a": {"description": "something"}})},
             "`<form>: ` で始まらない"),
            (check_input_forms, {"demo/schemas/doc.schema.json": None}, "demo/schemas/doc.schema.json が無い"),
            (check_input_forms, {"other/schemas/doc.schema.json": "{}"}, "形のファイル doc.schema.json が"),
            (check_input_forms, {"demo/works-factory-demo.yaml": self.yaml_with(
                inputs={"a": {"description": "json(shared:absent.schema.json): x"}})}, ".shared/schemas/absent.schema.json が無い"),
            (check_graphs_have_no_roles, {"demo/works-factory-demo.yaml": yaml.safe_dump(
                {**demo, "nodes": [*demo["nodes"], {"id": "sub", "include": "works-factory-other"}]})}, "graph が AI の node"),
            (check_graphs_have_no_roles, {"demo/works-factory-demo.yaml": yaml.safe_dump(
                {**demo, "nodes": [*demo["nodes"], {"id": "kid", "workflow": "works-factory-other"}]})}, "graph が AI の node"),
            (check_no_run_root_or_other_folders, {"demo/scripts/prep.py": "import os\nos.environ['ARTIFACTS_DIR']\n"}, "字 ARTIFACTS_DIR"),
            (check_no_run_root_or_other_folders, {"demo/src/x.py": "P = '../other/scripts/x.py'\n"}, "'../other'"),
            (check_returns_carry_outcome_and_report, {"demo/works-factory-demo.yaml": yaml.safe_dump(no_report)}, "欄 report が無い"),
            (check_module_names, {"demo/src/__init__.py": None, "demo/src/steps_of_demo.py": ""}, "__init__.py が無い"),
            (check_module_names, {"demo/scripts/steps.py": ""}, "['steps']"),
            (check_module_names, {"demo/scripts/ports.py": ""}, "['ports']"),
            (check_block_tests, {"tests-of-blocks/other/test_other.py": None}, "tests/blocks/other/"),
            (check_no_text_in_yaml, {"demo/works-factory-demo.yaml": yaml.safe_dump(with_loop)}, "loop: を持つ"),
            (check_no_text_in_yaml, {"demo/works-factory-demo.yaml": with_agents}, "role.agents"),
            (check_no_text_in_yaml, {"demo/works-factory-demo.yaml": with_reject}, "finish.on_reject.prompt"),
            (check_no_text_in_yaml, {"demo/works-factory-demo.yaml": yaml.safe_dump(with_rework)}, "rework.prompt"),
            (check_no_text_in_yaml, {"demo/schemas/doc.schema.json": '{"anyOf": [], "format": "uri"}'}, "$.anyOf"),
            (check_no_text_in_yaml, {".shared/schemas/x.schema.json": '{"oneOf": []}'}, "$.oneOf"),
            (check_reply_fields, {"demo/prompts/role.md": '{shared:rejected}\n{part:rules}\nReturn {{"ok": true}}.\n'}, "['ok']"),
            (check_reply_fields, {"demo/prompts/parts/rules.md": 'rules\n"field": x\n'}, "['field']"),
            (check_include_ids_unique, {"other/works-factory-other.yaml": yaml.safe_dump(
                {**other, "nodes": [*other["nodes"], {"id": "role", "include": "works-factory-demo"}]})}, "include の node role"),
            (check_include_ids_unique, {"other/works-factory-other.yaml": yaml.safe_dump(
                {**other, "nodes": [*other["nodes"], {"id": "outer", "loop_group": {"nodes": [
                    {"id": "finish", "include": "works-factory-demo"}]}}]})}, "include の node finish"),
            (check_include_ids_unique, {"other/works-factory-other.yaml": yaml.safe_dump(
                {**other, "nodes": [*other["nodes"], {"id": "deep", "include": "works-factory-demo"}]}),
                "demo/works-factory-demo.yaml": yaml.safe_dump({**demo, "nodes": [*demo["nodes"], {"id": "outer", "loop_group": {
                    "nodes": [{"id": "inner", "loop_group": {"nodes": [{"id": "deep", "script": "prep"}]}}]}}]})},
             "include の node deep"),
            (check_tool_fragments, self.tool_fragment("rules\n"), "{shared:tooly} が"),
            (check_tool_fragments, self.tool_fragment("{shared:rejected}\n<!-- if on -->\n{shared:tooly}\n<!-- end on -->\n"), "{shared:tooly} が"),
            (check_tool_fragments, self.tool_fragment("<!-- if not on -->\n{shared:tooly}\n<!-- end on -->\n"), "{shared:tooly} が"),
            (check_include_ids_unique, self.nested_include("deep2", "mid-inner", sibling=False), "include の node deep2"),
            (check_include_ids_unique, self.nested_include("deep2", "other-inner", sibling=True), "別の include other-inner"),
        ]
        for check, changes, word in cases:
            with self.subTest(check=check.__name__, changes=sorted(changes)):
                got = self.broken(check, changes)
                self.assertTrue(any(word in line for line in got), (word, got))

    def test_rendered_table_proves_a_node_the_fixtures_do_not_reach(self):
        """筋書きで届かない AI の node は、block の試験の表 RENDERED の行（md の決まった文）で照らされたと数える。字が md に無い行は数えない"""
        unreached = yaml.safe_dump({"fixture": {"reached": ["prep", "finish"], "inputs": {"text_in": "x"}}, "exec-code": True, "role": {}})
        for table, clean in (('RENDERED = {"role": "rules"}\n', True), ('RENDERED = {"role": "x"}\n', False)):
            with self.subTest(table=table):
                got = self.broken(check_standalone_renders, {"demo/fixtures/standalone.stubs.yaml": unreached,
                                                             "tests-of-blocks/demo/test_prompts.py": table})
                self.assertEqual(got == [], clean, got)

    def test_rendered_table_does_not_prove_a_node_the_fixtures_reach(self):
        """筋書きで届く node は表 RENDERED の行では照らされない（筋書きの resolved-text-contains がなければ照らす筋書きが無い）"""
        reached = yaml.safe_dump({"fixture": {"reached": ["prep", "role", "finish"], "inputs": {"text_in": "x"}}, "exec-code": True,
                                  "role": {}})
        got = self.broken(check_standalone_renders, {"demo/fixtures/standalone.stubs.yaml": reached,
                                                     "tests-of-blocks/demo/test_prompts.py": 'RENDERED = {"role": "rules"}\n'})
        self.assertTrue(any("照らす筋書きが無い" in line for line in got), got)

    def test_part_named_only_by_render_part(self):
        """parts の md は、scripts/・src/ の prompt.render_part("<name>" の呼びだけが名指しても通る。コメントの中の字・名の字が
        prompt.NODE_ID に合わない呼び（回すと落ちる）・どこからも名指されない物は赤"""
        brief = {"demo/prompts/parts/brief.md": "brief\n"}
        cases = [("from src import prompt\nprompt.render_part('brief', {})\n", True),
                 ("# prompt.render_part('brief', {}) は使わない\n", False),
                 ('"""prompt.render_part("brief", {})"""\n', False),
                 ("", False)]
        for code, clean in cases:
            with self.subTest(code=code):
                got = self.broken(check_prompt_files, {**brief, "demo/src/x.py": code})
                self.assertEqual(got == [], clean, got)
        got = self.broken(check_prompt_files, {"demo/prompts/parts/my_brief.md": "x\n",
                                               "demo/src/x.py": "prompt.render_part('my_brief', {})\n"})
        self.assertTrue(any("{part:my_brief} で差し込まれない" in line for line in got), got)

    def test_role_in_a_nested_loop_owns_its_prompt(self):
        """入れ子の輪（loop_group の本体の loop_group）の中の AI の node も、自分の prompts/<id>.md を持つ役に数える"""
        demo = yaml.safe_load(self.GOOD["demo/works-factory-demo.yaml"])
        deep = {"id": "outer", "loop_group": {"nodes": [{"id": "inner", "loop_group": {"nodes": [
            {"id": "deep-role", "prompt": "$prep.output.prompt"}]}}]}}
        doc = yaml.safe_dump({**demo, "nodes": [*demo["nodes"], deep]})
        self.assertEqual(self.broken(check_prompt_files, {"demo/works-factory-demo.yaml": doc, "demo/prompts/deep-role.md": "x\n"}), [])
        got = self.broken(check_prompt_files, {"demo/works-factory-demo.yaml": doc})
        self.assertTrue(any("prompts/deep-role.md が無い" in line for line in got), got)

    def test_self_workflow_is_allowed_in_a_block(self):
        """block が起こしてよい workflow は自分（直しの組ごとに自分を子の run として起こす形）"""
        demo = yaml.safe_load(self.GOOD["demo/works-factory-demo.yaml"])
        doc = yaml.safe_dump({**demo, "nodes": [*demo["nodes"], {"id": "kid", "workflow": "works-factory-demo"}]})
        self.assertEqual(self.broken(check_graphs_have_no_roles, {"demo/works-factory-demo.yaml": doc}), [])


class ExistingRulesCase(unittest.TestCase):
    """今ある yes/no の検査（tests/layers/scan.py）を pack（workflows/）に当てる。pack を一時の木の workflows/ に写して当てる"""

    RULES = ("E6", "E7", "E12", "E16", "E19")

    def test_existing_rules_hold_on_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            shutil.copytree(BLOCKS, root / "workflows", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copy(ROOT / "pack.json", root / "pack.json")
            shutil.copytree(ROOT / "factory", root / "factory")
            # graph（include を持つ物）は役を持たないので、graph の名（judge・eyes など）の役を名指す表 KEEP_CHECKOUT の行が
            # 「工程に無い」と出る。その行は表の話で、graph の形の外れではない
            graphs = {f.name for f in folders(BLOCKS) if any("include" in n for n in nodes(load(f)))}
            stale = re.compile(rf"^workflows/({'|'.join(map(re.escape, graphs)) or '$^'})/[^:]+:1: 表 KEEP_CHECKOUT が名指した役 ")
            for rule in self.RULES:
                with self.subTest(rule=rule):
                    got = [line.replace("workflows/", "blocks/", 1) for line in scan.problems(rule, root) if not stale.match(line)]
                    self.assertEqual(got, [])


class ArchonCase(unittest.TestCase):
    """E1 と 7.1 の 3: pack（workflows/）の全部の workflow を Archon の validate に通し、全部の筋書きを workflow test で回す"""

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
