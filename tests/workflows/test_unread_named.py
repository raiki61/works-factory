"""読めないポインタの入力を、黙って空や当たりにせず名指す（落とし穴 K15。持ち主の決め no-silent-loosen。docs/design/README.md の 4.2）。

pack（tests/archon.py の WORKFLOWS）のブロックごとに、宣言の入力のうちポインタを受けうる物を 1 つずつ壊れた先（run の置き場に無い
ファイル gone/x9.json）にして、その入力を読む script を子のプロセスで走らせ、返り（標準出力の JSON）か書いたファイルに、その入力の名が
載ることを見る。
- ポインタを受けうる入力: YAML の inputs: の description の form が json(<schema>) か file の物（4.1。口 ports の json・file は
  この run の pointer・ファイルのパス・値そのものの 3 通りを受ける）。line の request は起動の殻が渡すファイルのパスで、pointer は
  来ないので見ない
- 読む script: script の字に `INPUTS_<名>` が在るか、`INPUTS_{…}` を組んで読む script が名の字を持つ物。YAML の順に走らせる。
  ほかの入力はブロックの standalone の筋書き（fixtures/standalone.stubs.yaml の fixture.inputs。7.1 の 4）の値
- 名指し: 同じ値で壊さない run（対照）と比べ、壊れた run だけが返すか書く字（JSON は葉の字、ほかは行。数字だけが違う字〔時刻など〕は
  同じ字と見る）のうち、入力の名を語として
  持ち（パスの一部 `start.json`・`plan/r1` は語に数えない）、読めない・無いことも言う物（UNREAD）が 1 つ以上在る。口の訳（「json の
  入力のファイル <パス> が無い」）だけではどの入力かが分からないので、名指しに数えない。落ちた script の標準エラーは数えない
- 照らせない物: standalone の値では読み手がその入力に届かない（mode が違う・前の確かめで止まる）時は、壊れた run と対照の run の字が
  同じになる。それは黙った読みと見分けられないので、この試験は見送り、ブロックの試験が見る。見送りの無い入力が 1 つも無ければ赤
- 許す表は持たない（持ち主の決め shape-checks-only）
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

import yaml

from tests.archon import ROOT, WORKFLOWS
from tests.bin import hermetic
from tests.bin.gitkit import committed_copy
from tests.layers import scan

SEED = ROOT / "tests" / "e2e" / "target-seed"
RUN_ID = "run-unread"
GONE = "gone/x9.json"
BROKEN = json.dumps({"type": "archon_artifact", "run_id": RUN_ID, "path": GONE})
SKIP = ("line",)   # 入力 request は起動の殻が渡すファイルのパス（pointer は来ない）
POINTER_FORMS = ("json", "jsonl", "file")   # pointer かファイルのパスを受ける form（語の住処は workflows/.shared/ports.py の form_of）
UNREAD = re.compile(r"読めな|読めず|読み損|無い|壊れ|unread|missing|not found|No such file")


def word(pattern: str) -> re.Pattern:
    """pattern を語として当てる式。前後が `[\\w\\-/.]` の時は語の一部（plan-fields.json・fix_plan・plan/r1）で数えない"""
    return re.compile(rf"(?<!(?a:[\w\-/.]))(?:{pattern})(?!(?a:[\w\-/.]))")


def reads(text: str, name: str) -> bool:
    """script の字が入力 name を読むか。Archon は名の - を _ にして大文字の INPUTS_<名> で渡す。`INPUTS_{…}` を組んで読む script は
    名の字を持つ物を読み手に数える"""
    if re.search(rf"INPUTS_{re.escape(name.replace('-', '_').upper())}(?![A-Z0-9_])", text):
        return True
    return "INPUTS_{" in text and bool(re.search(rf"[\"']{re.escape(name)}[\"']", text))


def flat(nodes) -> list[dict]:
    out = []
    for node in nodes or []:
        out.append(node)
        if isinstance(node.get("loop_group"), dict):
            out.extend(flat(node["loop_group"].get("nodes")))
    return out


def pointer_inputs(doc: dict) -> list[str]:
    return [name for name, spec in (doc.get("inputs") or {}).items()
            if isinstance(spec, dict) and (scan.ports().form_of(spec.get("description")) or ("",))[0] in POINTER_FORMS]


def readers(block: pathlib.Path, doc: dict, name: str) -> list[dict]:
    return [node for node in flat(doc["nodes"]) if "script" in node
            and reads((block / "scripts" / f"{node['script']}.py").read_text(encoding="utf-8"), name)]


def standalone(block: pathlib.Path) -> dict:
    """standalone の筋書きの入力（Archon と同じく字はそのまま、ほかは JSON の字）"""
    path = block / "fixtures" / "standalone.stubs.yaml"
    given = ((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("fixture") or {}).get("inputs") or {} \
        if path.is_file() else {}
    return {k: v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for k, v in given.items()}


def leaves(value) -> list[str]:
    if isinstance(value, dict):
        return [s for v in value.values() for s in leaves(v)]
    if isinstance(value, list):
        return [s for v in value for s in leaves(v)]
    return [value] if isinstance(value, str) else []


def said(text: str) -> list[str]:
    """字を、JSON なら葉の字、JSON の行の並びなら行ごとの葉の字、ほかは行に分ける"""
    try:
        return leaves(json.loads(text))
    except ValueError:
        pass
    out = []
    for line in text.splitlines():
        try:
            out.extend(leaves(json.loads(line)))
        except ValueError:
            out.append(line)
    return out


def fresh(broken: set, control: set) -> set:
    """壊れた run だけの字。数字だけが違う字（書いた時刻・掛かった秒）は対照と同じ字と見る"""
    seen = {re.sub(r"\d+", "0", s) for s in control}
    return {s for s in broken if re.sub(r"\d+", "0", s) not in seen}


def named(name: str, strings) -> bool:
    """字のどれかが、入力の名を語として持ち、読めない・無いことも言う"""
    pattern = word(re.escape(name))
    return any(pattern.search(s) and UNREAD.search(s) for s in strings)


class Observed:
    """1 つの入力の、対照の run と壊れた run の字"""

    def __init__(self, block: str, name: str):
        self.block, self.name = block, name
        self.folder = WORKFLOWS / block
        self.doc = yaml.safe_load((self.folder / f"works-factory-{block}.yaml").read_text(encoding="utf-8"))
        self.order = readers(self.folder, self.doc, name)
        self.inputs = standalone(self.folder)

    def run(self, broken: bool) -> tuple[set, list]:
        """(返りと書いたファイルの字の集まり, 落ちた script の (id, 終了の値, 標準エラーの最後の行))"""
        with tempfile.TemporaryDirectory() as tmp:
            art = pathlib.Path(tmp) / "art"
            art.mkdir()
            repo = pathlib.Path(tmp) / "repo"
            committed_copy(repo, SEED)
            inputs = {**self.inputs, **({self.name: BROKEN} if broken else {})}
            strings, fell = [], []
            for node in self.order:
                env = hermetic.child_env(**{f"INPUTS_{k.replace('-', '_').upper()}": v for k, v in inputs.items()},
                                         ARTIFACTS_DIR=str(art), WORKFLOW_ID=RUN_ID, WORKS_FACTORY_ROOT=str(ROOT),
                                         PYTHONDONTWRITEBYTECODE="1", WORKS_LIBDOCS_WEB="off")
                done = subprocess.run([sys.executable, str(self.folder / "scripts" / f"{node['script']}.py")],
                                      cwd=repo, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                      encoding="utf-8")
                if done.returncode != 0:
                    fell.append((node["id"], done.returncode, (done.stderr.strip().splitlines() or [""])[-1]))
                strings.extend(said(done.stdout))
            for path in sorted(art.rglob("*")):
                if path.is_file():
                    strings.extend(said(path.read_text(encoding="utf-8", errors="replace")))
            real = os.path.realpath(tmp)
            return {s.replace(real, "<tmp>").replace(tmp, "<tmp>") for s in strings}, fell


def pointer_rows() -> list[tuple[str, str]]:
    rows = []
    for spec in sorted(WORKFLOWS.glob("*/works-factory-*.yaml")):
        block = spec.parent.name
        if spec.stem == f"works-factory-{block}" and block not in SKIP:
            rows.extend((block, name) for name in pointer_inputs(yaml.safe_load(spec.read_text(encoding="utf-8"))))
    return rows


class UnreadNamedCase(unittest.TestCase):
    maxDiff = None

    def test_every_pointer_input_unreadable_is_named(self):
        quiet, seen_any = {}, False
        for block, name in pointer_rows():
            with self.subTest(block=block, input=name):
                seen = Observed(block, name)
                if not seen.order:
                    continue
                control, _ = seen.run(broken=False)
                broken, fell = seen.run(broken=True)
                new = fresh(broken, control)
                if not new and not fell:
                    continue   # standalone の値では読み手がこの入力に届かない（docstring の「照らせない物」）
                seen_any = True
                if not named(name, new):
                    quiet[(block, name)] = f"落ちた script: {fell}" if fell else f"名の無い訳: {sorted(new)[:2]}"
        self.assertTrue(seen_any, "壊れた先を読ませられた入力が 1 つも無い（照らしが空回りする）")
        self.assertEqual(quiet, {}, "壊れた先を名指さない入力")

    def test_naming_counts_only_new_words_outside_paths(self):
        control = {"plan/r1/round.json", "start は読めた"}
        self.assertTrue(named("start", {"start が読めない: gone/x9.json"} - control))
        self.assertFalse(named("start", {"    start = read_json(ports.json(start_raw))"}))
        self.assertFalse(named("start", {"start は読めた"} - control))
        self.assertFalse(named("plan", {"plan/r1/x.json", "plan-review/failed", "plan_dir"}))
        self.assertFalse(named("start", {"FileNotFoundError: <tmp>/art/gone/x9.json"}))
        self.assertFalse(named("request", {"ValueError: json の入力のファイル <tmp>/art/gone/x9.json が無い"}))
        self.assertEqual(fresh({"at 2026-10-19T13:59:34", "start が読めない"}, {"at 2026-10-19T13:59:30"}), {"start が読めない"})
        self.assertEqual(said('{"a": ["start が読めない", 1], "start": null}'), ["start が読めない"])
        self.assertEqual(said('{"a": "x"}\nplain\n'), ["x", "plain"])

    def test_pointer_inputs_are_read_from_the_form(self):
        doc = {"inputs": {"a": {"description": "json(judgment.schema.json): 判定"},
                          "f": {"description": "file: 方針の文書"},
                          "b": {"description": "text: 判定の json(x) を言うだけ"}, "c": {"default": ""}}}
        self.assertEqual(pointer_inputs(doc), ["a", "f"])
        self.assertTrue(reads('os.environ["INPUTS_START"]', "start"))
        self.assertFalse(reads('os.environ["INPUTS_START_ANSWERS"]', "start"))
        self.assertTrue(reads('for name in ("ripple", "world"):\n    os.environ.get(f"INPUTS_{name.upper()}")', "world"))


if __name__ == "__main__":
    unittest.main()
