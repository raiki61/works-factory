"""照らしの道具 tests/e2e/evidence.py の試験（collect・5 種の照らしの判じ・check）と、照らしの表 evidence.json の試験。
collect の後ろの Archon は偽の殻で、家の fake-runs.json の run を workflow runs・get で答える。

表の試験は、行の形と、seen の行の書き手の指し（writer の `path::名`）がリポジトリの定義を指すことを照らす。能力の棚卸しと線の
配線の文書への照らしは、組み込みで照らす相手ごと消した（docs/design/integration.md の 4.2-1f）。指しの読みは keep-essence の
照らし tests/layers/test_keep_essence.py と同じ口。"""
import ast
import io
import json
import pathlib
import re
import subprocess
import sys
import tokenize
import unittest
from collections.abc import Callable

import yaml

from tests import archon
from tests.bin import hermetic, stepnames
from tests.e2e import evidence, make_target
from tests.layers import scan
from tests.layers.test_keep_essence import POINTER, python_definitions, yaml_definitions

E2E = pathlib.Path(__file__).resolve().parent
ROOT = E2E.parents[1]
# 照らしの where の run の記録 → その run の工程（親は線、子は fix の組ごとの子の run）
RECORDS = {"record/parent.json": "works-factory-line", "record/child-*.json": "works-factory-fix"}
# 線の中のブロック（置き場の parent/ の次のフォルダ。line の include の id で、include の中の節の place はその id のフォルダの下に
# 重なる。例: parent/judge/diagnose/）のうち、種の run で必ず走り、seen の行を持つ物と、線そのもの。fix の組の子の run の置き場は
# 子の run の根（child-*/）で、fix の物。条件で回る include（lens・delta-review・案の直しの道・再審・仕様・修正の後の並行 PR）は
# 必ずは走らないので入れない。independent-design は種の run で必ず走るが、独立設計の能力の行は #261 の決め直しで本物の通しの
# 照らしの外（scenario-only）にしたので、seen の行が無く入れない（設計を目に渡した跡は L-W55、承認ノードの控えは L-W33 が照らす）
BLOCKS = ("test-gate-base", "judge", "structure", "plan", "plan-review-run", "fix", "test-gate-final", "eyes", "merge-seal",
          "merge-apply", "report")
LINE_ITSELF = "line"
# line の include の id → 差し込むブロックのフォルダ。置き場の parent/ の次のフォルダが include の id なら、Archon が include の道から
# place を作るので（workflows/.shared/ports.py の place）、フォルダの名は書き手のコードに無くてよい
INCLUDES = {n["id"]: n["include"].removeprefix("works-factory-") for n in stepnames.walk(stepnames.nodes("works-factory-line"))
            if "include" in n}
WRITERS = ("lib", "workflows", "bin")
# 名を組んで書く・名の表（block の src/files.py の定数）から引いて書くので、書き手のコードの字で引けない置き場 → 名を組む関数・表の
# 定数（`path::名`）。指示のファイル <node の id>-prompt-<n>.md は workflows/.shared/prompt.py の emit が組む
NAMED_BY_PATTERN = {
    "parent/gates/gate-start.json": "lib/answer.py::taken",
    "parent/gates/gate-final.json": "lib/answer.py::taken",
    "parent/gates/gate-*.json": "lib/answer.py::taken",
    "parent/gates/final-gate.md": "workflows/line/src/files.py::FINAL_GATE_MD",
    "parent/plan-converge.json": "workflows/line/src/files.py::PLAN_CONVERGE",
    "parent/plan/plan-writer-prompt-1.md": "workflows/.shared/prompt.py::emit",
    "parent/plan/r1/plan-fields.json": "lib/planmarks.py::FIELDS_FILE",
    "parent/plan/r1/rejects-plan.json": "lib/rolekit.py::rejects_path",
    "parent/plan/r1/rejects-plan.md": "lib/rolekit.py::rejects_text_path",
    "parent/plan/r1/ripple.json": "workflows/plan/src/files.py::RIPPLE",
    "parent/plan/r1/ripple-units.json": "workflows/plan/src/files.py::RIPPLE_UNITS",
    "parent/judge/verdict.json": "workflows/judge/src/files.py::VERDICT",
    "parent/judge/parallel-pr/material-pr-check.json": "workflows/parallel-pr/src/files.py::MATERIAL",
    "parent/judge/diagnose/query-examples.json": "workflows/diagnose/src/files.py::QUERY_EXAMPLES_FILE",
    "parent/structure/design.jsonl": "workflows/structure/src/files.py::DESIGN_FILE",
    "parent/eyes/r1/r1-comments.json": "workflows/r1/src/steps.py::save",
    "parent/eyes/r1/r1-minimality.json": "workflows/r1/src/steps.py::save",
    "parent/eyes/r1/r1-minimality-prompt-1.md": "workflows/.shared/prompt.py::emit",
    "parent/eyes/r2/r2-compare-prompt-1.md": "workflows/.shared/prompt.py::emit",
    "parent/eyes/r2/r2-premises.json": "workflows/r2/src/files.py::PREMISES",
    "parent/eyes/structure-after/structure-after.json": "workflows/structure/src/files.py::AFTER_FILE",
    "parent/delta-review/review-1-brief.json": "workflows/delta-review/src/files.py::review_brief",
    "parent/test-gate-base/logs/*/test_cmd.log": "lib/declared_checks.py::_planned_run",
    "parent/report/report.md": "workflows/report/src/files.py::REPORT_FILE",
}


class CodeText:
    """リポジトリのコードの字（コメント・Python の docstring を空の行にし、行の番号を保つ）と、コードの全部の定数（大文字の名 = 字）"""

    def __init__(self, read: Callable[[str], str] = lambda rel: (ROOT / rel).read_text(encoding="utf-8")):
        """read: リポジトリの根からのパス → ファイルの字（試験は行をずらした字を渡す）"""
        self.read = read
        self._lines: dict[str, list[str]] = {}
        sources = [p for top in WRITERS for p in (ROOT / top).rglob("*") if p.is_file() and p.suffix in (".py", ".yaml", ".sh")
                   and not {"tests", "fixtures"} & set(p.relative_to(ROOT).parts)]
        self.constants: dict[str, list[str]] = {}
        for p in sources:
            if p.suffix == ".py":
                for ident, value in _constants(read(p.relative_to(ROOT).as_posix())):
                    self.constants.setdefault(ident, []).append(value)

    def lines(self, rel: str) -> list[str]:
        if rel not in self._lines:
            text = self.read(rel)
            self._lines[rel] = _python_code(text) if rel.endswith(".py") else [re.sub(r"(^|\s)#.*$", "", line)
                                                                             for line in text.splitlines()]
        return self._lines[rel]

    def text(self, rel: str) -> str:
        return "\n".join(self.lines(rel))

    def names(self, text: str, name: str) -> bool:
        """text が name を字のまま持つか、name を作る定数（{…} の差し込みはどの字でも）の名を持つか"""
        if name in text:
            return True
        return any(re.fullmatch(".+".join(map(re.escape, re.split(r"\{[^}]*\}", value))), name)
                   for ident in set(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", text)) for value in self.constants.get(ident, ()))


def _builds(text: str, name: str) -> bool:
    """text の字の並びのどれかが、{…} の差し込みをどの字にもして name に当たるか（差し込みでない字が在る並びだけ）"""
    for value in re.findall(r'"([^"\n]*)"|\'([^\'\n]*)\'', text):
        fixed = re.split(r"\{[^}]*\}", "".join(value))
        if "".join(fixed) and re.fullmatch(".+".join(map(re.escape, fixed)), name):
            return True
    return False


def _constants(text: str):
    """Python の字の大文字の名に結んだ字（字の並び・f 字列の差し込みは {} にした字）の (名, 字) の並び"""
    def strings(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value
        elif isinstance(node, ast.JoinedStr):
            yield "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)
        elif isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            for elt in node.elts:
                yield from strings(elt)

    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            pairs = (zip(target.elts, node.value.elts) if isinstance(target, ast.Tuple) and isinstance(node.value, ast.Tuple)
                     else [(target, node.value)])
            for name, value in pairs:
                if isinstance(name, ast.Name) and name.id.isupper():
                    yield from ((name.id, v) for v in strings(value))


def _python_code(text: str) -> list[str]:
    """Python の字の行の並び。コメントと docstring（モジュール・クラス・関数の頭の字の式）を空にする"""
    lines = text.splitlines()
    for node in ast.walk(ast.parse(text)):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            for n in range(body[0].lineno - 1, body[0].end_lineno):
                lines[n] = ""
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT:
            row, col = tok.start
            lines[row - 1] = lines[row - 1][:col]
    return lines


def writer_code(code: CodeText, writer: str) -> tuple[str, str, str, str] | None:
    """writer（`path::名`）の (path, 名, 定義の字, ファイルの字)。ファイルか名の定義が無ければ None。在るかも定義の範囲も code.read の字で
    決める。YAML の名は節の id で、定義は節の字と、名前の script の節ならその script のコードの字（最上位のコードに決める行の在る
    script は、それを走らせる節で指す）"""
    pointed = POINTER.fullmatch(writer)
    if not pointed:
        return None
    path, name = pointed.groups()
    try:
        text = code.read(path)
    except FileNotFoundError:
        return None
    if path.endswith(".py"):
        span = python_definitions(text).get(name)
        if span is None:
            return None
        first, last = span
        return path, name, "\n".join(code.lines(path)[first - 1:last]), code.text(path)
    node = yaml_definitions(text).get(name)
    if node is None:
        return None
    scripts = [code.text(p.relative_to(ROOT).as_posix()) for p in scan.node_scripts((ROOT / path).parent, node)]
    body = "\n".join(code.lines(path)[node.start_mark.line:node.end_mark.line])
    return path, name, "\n".join([body, *scripts]), "\n".join([code.text(path), *scripts])


def writer_rows(rows: list[dict]) -> list[dict]:
    """表の seen の行と、NAMED_BY_PATTERN の置き場を where・writer にした行"""
    return [r for r in rows if r["kind"] == "seen"] + [{"id": w, "where": w, "writer": v} for w, v in NAMED_BY_PATTERN.items()]


def seen_writer_problems(rows: list[dict], code: CodeText) -> list[str]:
    out = []
    for row in rows:
        if pathlib.PurePosixPath(row["writer"]).parts[0] not in WRITERS:
            out.append(f"{row['id']}: {row['writer']} が {WRITERS} の外")
            continue
        found = writer_code(code, row["writer"])
        if found is None:
            out.append(f"{row['id']}: {row['writer']} が `path::名` でないか、その名の定義が無い")
            continue
        path, named, _, whole = found
        if row.get("check") == "node-completed":
            steps = {row["node"].split("__", 1)[0], row["node"].rsplit("__", 1)[-1].rsplit(".", 1)[-1]}
            if not (path.endswith(".yaml") and named in steps):
                out.append(f"{row['id']}: {row['writer']} が節 {row['node']} でない")
            continue
        if row["where"].startswith("record/"):
            continue
        rest = row["where"].split("/")[1:]
        folder = rest[0] if len(rest) > 1 and not re.search(r"[*?\[]", rest[0]) else ""
        if folder and folder not in INCLUDES:
            block = archon.WORKFLOWS / folder
            here = [whole, *(code.text(p.relative_to(ROOT).as_posix()) for p in sorted(block.rglob("*"))
                             if p.suffix in (".py", ".yaml") and "fixtures" not in p.parts)]
            if not any(code.names(t, folder) for t in here):
                out.append(f"{row['id']}: {row['where']} のフォルダ {folder} を書き手が作らない")
        if row["where"] in NAMED_BY_PATTERN:
            continue
        name = rest[-1]
        if re.search(r"[*?\[]", name):
            out.append(f"{row['id']}: glob の名 {name} は NAMED_BY_PATTERN に名指す")
        elif not code.names(whole, name):
            out.append(f"{row['id']}: {path} のコードに {name} の名もその名を作る定数も無い")
    return out


def pattern_writer_problems(code: CodeText, table: dict[str, str] = NAMED_BY_PATTERN) -> list[str]:
    out = []
    for where, writer in table.items():
        found = writer_code(code, writer)
        name = where.rsplit("/", 1)[-1]
        if found is None:
            out.append(f"{where}: {writer} が `path::名` でないか、その名の定義が無い")
        elif not (code.names(found[2], name) or _builds(found[2], name)):
            out.append(f"{where}: {writer} の定義が {name} の名を組まない")
    return out


def shifted(rel: str) -> str:
    """関係の無い 1 行（コメント）を頭に足した字"""
    return f"# 関係の無い 1 行\n{(ROOT / rel).read_text(encoding='utf-8')}"


FAKE_SHELL = """#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
home = pathlib.Path(os.environ["WORKS_FACTORY_HOME"])
runs = json.loads((home / "fake-runs.json").read_text(encoding="utf-8"))
with open(home / "calls.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps({"args": args, "no_auth": os.environ.get("WORKS_FACTORY_NO_AUTH")}) + "\\n")
if args[1] == "runs":
    print(json.dumps({"runs": [{k: r[k] for k in ("id", "parent_run_id", "started_at")} for r in runs]}))
elif args[1] == "get":
    run = next(r for r in runs if r["id"] == args[2])
    print(json.dumps({"id": run["id"], "status": "completed", "terminal_record": {"artifacts": {"root": run["root"]}}}))
"""


def block_of(where: str) -> str:
    """照らしの where を置く書き手のブロック（parent/ の次のフォルダ・child-*/ は fix・ほかは線そのもの）"""
    head, *rest = where.split("/")
    if head.startswith("child-"):
        return "fix"
    return rest[0] if head == "parent" and len(rest) > 1 and rest[0] in BLOCKS else LINE_ITSELF


class EvidenceTableCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = evidence.read_table(evidence.TABLE)
        cls.by_id = {row["id"]: row for row in cls.rows}

    def kind_of(self, kind):
        return {row["id"] for row in self.rows if row["kind"] == kind}

    def test_row_ids_are_unique(self):
        self.assertEqual(len(self.by_id), len(self.rows), "表に同じ ID の行が 2 つ在る")

    def test_every_row_has_a_known_kind_and_fields(self):
        for row in self.rows:
            with self.subTest(row=row.get("id")):
                self.assertIsNone(evidence.row_problem(row))
        for broken in ({"id": "J1", "kind": "seen", "writer": "lib/a.py::f"}, {"id": "J1", "kind": "maybe", "why": "x"},
                       {"id": "J1", "kind": "seen", "check": "exists", "where": "parent/a"},
                       {"id": "J1", "kind": "seen", "writer": "lib/a.py::f", "check": "node-completed", "where": "parent/a",
                        "node": "x"},
                       {"id": "J1", "kind": "waits-part", "part": "Z"}, {"id": "J1", "kind": "handed-off", "why": "x"},
                       {"id": "J1", "kind": "scenario-only", "why": "x", "check": "exists", "where": "parent/a"},
                       {"id": "J1", "kind": "seen", "writer": "lib/a.py::f", "check": "exists", "where": "elsewhere/a"}):
            with self.subTest(broken=broken):
                self.assertIsNotNone(evidence.row_problem(broken))

    def test_no_row_waits_for_a_part(self):
        """部分は全部 main に入り、check は waits-part の行が 1 つでも残れば落ちる（#154 の最後の通し c38831c2 は L-W08 だけで rc=1）"""
        self.assertEqual(self.kind_of("waits-part"), set())

    def test_rows_without_a_sure_trace_in_the_seed_run_are_seed_cannot_with_their_check(self):
        """#355（c38831c2）: E12 の削除候補は役が削る物を見つけた時だけ出る（健やかな種の run で必ず通る道でない。seen の基準 (3)）。
        L-W08 の記録は空の {units: [], paths: []} でも書かれ、働かなかった run と同じ跡（基準 (2)）。照らしは働いた時だけ当たる物で残す。
        置き場は組み込みの後の include の道（eyes の中の r1・judge の中の diagnose）の下"""
        for i, where in (("E12", "parent/eyes/r1/r1-comments.json"), ("L-W08", "parent/judge/diagnose/structure-units-dropped.json")):
            with self.subTest(row=i):
                row = self.by_id[i]
                self.assertEqual((row["kind"], row.get("check"), row.get("where")), ("seed-cannot", "json-has", where))

    def test_node_rules_name_node_ids_the_workflow_makes(self):
        """run の記録の節を照らす行は node-completed で、node はその run の工程の YAML から組んだ節の id そのもの（include の頭は
        差し込んだ節のどれか 1 つが走れば通るので名指さない）。種類を問わない（seen でない行も、当たらなければ unexpected を言えない）。
        nodes[] は飛ばされた節も載せるので、節の名を json-equals や text-contains で照らす行を置かない"""
        names = {where: stepnames.step_names(flow) for where, flow in RECORDS.items()}
        for row in self.rows:
            if not row.get("where", "").startswith("record/"):
                continue
            with self.subTest(row=row["id"]):
                self.assertIn(row["where"], names)
                self.assertFalse(row["check"] == "json-equals" and row["path"].endswith("nodeId"), "節の名だけの照らし")
                self.assertFalse(row["check"] == "text-contains" and ("nodeId" in row["text"] or row["text"].endswith('"')),
                                 "節の名だけの照らし")
                if row["check"] == "node-completed":
                    self.assertIn(row["node"], names[row["where"]])

    def test_seen_rows_name_a_writer_in_the_repository(self):
        """seen の行の writer は、能力を決める所（拒み・止め・既定でない側・値を作る所。保存の所でない）の `path::名` で、名は
        lib・workflows・bin のファイルに定義の在る関数・定数・`クラス.名`（YAML は節の id。最上位のコードで決める script は、それを
        走らせる節）。決める所は保存の所から離れうるので、where のファイル名かその名を作る定数は、writer のファイル（節なら節の
        script も）のコードの字（コメント・docstring・.md を除く）のどこかに在ればよい。where の置き場の頭のフォルダ（parent/・
        child-*/ の次）の名は、line の include の id（INCLUDES）か、書き手のファイルかそのブロックの script と YAML のコードの字に在る。名を組んで書く置き場は
        NAMED_BY_PATTERN に名を組む所と名指し、ここでは名の照らしを外す（名を組むかは test_named_by_pattern_bodies_build_the_name が
        縛る）。run の記録の節の行の writer は、その節の YAML の `path::節の id`"""
        self.assertEqual(seen_writer_problems(writer_rows(self.rows), CodeText()), [])

    def test_named_by_pattern_bodies_build_the_name(self):
        """NAMED_BY_PATTERN の指す名の定義（関数なら本体の全部、定数なら値、節なら節と script）が、その置き場の名を組む: 名を字の
        まま、名を作る定数、か字の並び（{…} の差し込みはどの字でも）で持つ。書き手の名が変わったら、表の指しもここで落ちる"""
        self.assertEqual(pattern_writer_problems(CodeText()), [])

    def test_writers_hold_when_lines_shift(self):
        """名で指すので、Python でも YAML でも関係の無い行がずれても照らしは緑のまま"""
        code = CodeText(read=shifted)
        for rel in ("lib/structmark.py", "workflows/eyes/works-factory-eyes.yaml"):
            self.assertEqual(len(code.lines(rel)), len(CodeText().lines(rel)) + 1)
        self.assertEqual(writer_code(code, "workflows/eyes/works-factory-eyes.yaml::structure-after")[2],
                         writer_code(CodeText(), "workflows/eyes/works-factory-eyes.yaml::structure-after")[2])
        self.assertEqual(seen_writer_problems(writer_rows(self.rows), code), [])
        self.assertEqual(pattern_writer_problems(code), [])

    def test_a_pointer_off_the_writer_fails(self):
        code = CodeText()
        for writer in ("lib/structmark.py:83", "lib/structmark.py::no_such_name", "lib/nope.py::f", "workflows/nope.yaml::x",
                       "docs/a.py::f"):
            with self.subTest(writer=writer):
                self.assertNotEqual(seen_writer_problems([{"id": "J1", "where": "parent/eyes/structure-after.json",
                                                           "writer": writer}], code), [])
        self.assertEqual(seen_writer_problems([{"id": "J1", "where": "parent/eyes/structure-after.json",
                                                "writer": "lib/structmark.py::write_after"}], code), [])
        for row in ({"where": "parent/judge/purpose-means-x.json", "writer": "lib/rolekit.py::lang_line"},
                    {"where": "parent/nosuchfolder/structure-after.json", "writer": "lib/structmark.py::write_after"},
                    {"where": "record/parent.json", "check": "node-completed", "node": "eyes__prep",
                     "writer": "workflows/eyes/works-factory-eyes.yaml::structure-after"}):
            with self.subTest(row=row):
                self.assertNotEqual(seen_writer_problems([{"id": "J1", **row}], code), [])
        for where, writer in (("parent/structure/brief-1.md", "lib/structmark.py::AFTER_FILE"),
                              ("parent/eyes/r1.json", "workflows/eyes/works-factory-eyes.yaml::structure-after"),
                              ("parent/eyes/r1-comments.json", "workflows/eyes/works-factory-eyes.yaml::structure-after"),
                              ("parent/plan/r1/rejects-plan.json", "lib/rolekit.py::lang_line")):
            with self.subTest(where=where, writer=writer):
                self.assertNotEqual(pattern_writer_problems(code, {where: writer}), [])

    def test_every_block_has_a_seen_row(self):
        """本物の通しが見るのは、本物の役で各ブロックが仕事をしたか。どのブロックにも seen の行が在る（埋め物でない中身かは
        IdleRunCase が縛る）"""
        seen = {}
        for row in self.rows:
            if row["kind"] == "seen":
                seen.setdefault(block_of(row["where"]), []).append(row["id"])
        for block in (LINE_ITSELF, *BLOCKS):
            with self.subTest(block=block):
                self.assertGreaterEqual(len(seen.get(block, [])), 1)

    def test_handed_off_rows_name_their_place(self):
        for row in self.rows:
            with self.subTest(row=row["id"]):
                if row["kind"] == "handed-off":
                    self.assertTrue(row["why"].strip() and row["to"].strip())


SCENARIO = ROOT / "tests" / "e2e" / "scenario.json"
SCRIPTS = archon.WORKFLOWS
IDLE_RUN = "idle"
SKIPPED, COMPLETED = "skipped", evidence.COMPLETED
LINE = "works-factory-line"
# 前の段が全部飛んでも走る線の節: 頭の testcmd・始め・入口の承認ノードの答え・修正の段へ運ぶ値の中継（go が偽なら何も書かない）・
# 修正の後のまとめ・判定のまとめ（どちらも none_failed_min_one_success で、運ぶ値が無ければ何もしない）・報告の集め・報告の
# ブロック・子の run の掃除・返す節（all_done）。match で当てるので頭と尾を区切る
ALWAYS_RAN = re.compile(r"(?:testcmd|start|answer-start|fix-in|fixed|judged|collect|report__.*|sweep-children|result)$")
# start に入力を受けさせない名指し（対象に無い固定材料のフォルダ）。受けない start は入力のこだまと版の控えだけを書く
REFUSED_INPUT = "fixture"


def seed_inputs(request: str) -> dict[str, str]:
    """筋書きが線を起こす命令の --input（<request> は種の依頼のパス）"""
    text = json.loads(SCENARIO.read_text(encoding="utf-8"))["assertions"][0]["description"]
    launch = re.search(r"`[^`]* workflow run works-factory-line [^`]*`", text).group(0)
    return {k: request if v == "<request>" else v.strip("'") for k, v in re.findall(r"--input (\w+)=('[^']*'|[^\s`]+)", launch)}


def idle_run(tmp: pathlib.Path, started: bool) -> pathlib.Path:
    """何も働かなかった run の試みのフォルダ。置き場は、どの能力も働かなくても書かれる物だけ: 線の始めの節 start と、BLOCKS の
    ブロックの落ちない返す節（YAML の returns）と、線の ALWAYS_RAN の script の節を、上流が全部飛んだ形（入力が null）で今の書き手の
    まま、その節の place で走らせた物（判定・計画の空の埋め物、報告の見出しと 0 件の行など）。fix の組の子の run は返す節 finish だけ。started が偽なら start は種の入力を受けず（入力のこだまと版の
    控えだけを書く）、run の記録は線と fix の組の子の全部の節が skipped。真なら start は種の入力を受けて書く欄を全部書き、線の
    ALWAYS_RAN の節は completed（ほかは skipped）"""
    made = make_target.make(tmp / "attempt", listed=False)
    target, attempt = pathlib.Path(made["target"]), tmp / "attempt"
    ev = attempt / evidence.EVIDENCE
    (ev / "record").mkdir(parents=True)

    def script(folder, rel, node="", unset="null", /, **inputs):
        """rel を節として走らせた返り。渡さない入力は unset（飛んだ節の返りは null、線の渡さない入力は空の字）"""
        path = SCRIPTS / rel
        env = hermetic.child_env(ARTIFACTS_DIR=str(folder), WORKFLOW_ID=IDLE_RUN)
        env.update({n: unset for n in re.findall(r"INPUTS_[A-Z0-9_]+", path.read_text(encoding="utf-8"))})
        env.update({f"INPUTS_{k.upper()}": v for k, v in inputs.items()})
        if node:
            env["ARCHON_NODE_EXECUTION"] = json.dumps({"path": node})
        done = subprocess.run([sys.executable, str(path)], cwd=target, env=env, capture_output=True, text=True,
                              encoding="utf-8", timeout=300)
        if done.returncode != 0:
            raise AssertionError(f"{rel} が落ちた: {done.stderr[-500:]}")
        return json.loads(done.stdout)

    parent = ev / "parent"
    parent.mkdir()
    refused = {} if started else {"fix_fixture": REFUSED_INPUT}
    begun = script(parent, "line/scripts/start.py", "start", "", **seed_inputs(made["request"]), **refused)
    if begun["ok"] != started:
        raise AssertionError(f"start の ok が {begun['ok']}（{begun['reason']}）")
    line = {n["id"]: n for n in stepnames.walk(stepnames.nodes(LINE))}

    def node(block, ident, folder, step, /, **inputs):
        """block の節 ident を、上流が全部飛んだ形（with: の $ の値は null、字のままの値と、line の include の with: から字のまま
        降りる値はそのまま）で step として走らせた返り。inputs は名指しで上書きする値"""
        n = next(x for x in stepnames.walk(stepnames.nodes(f"works-factory-{block}")) if x["id"] == ident)
        given = {}
        for key, value in (n.get("with") or {}).items():
            if isinstance(value, str) and value.startswith("$INPUTS."):
                value = (line.get(step.rsplit("__", 1)[0].rsplit(".", 1)[-1], {}).get("with") or {}).get(value.removeprefix("$INPUTS."))
            given[key] = value if isinstance(value, str) and "$" not in value else "null"
        return script(folder, f"{block}/scripts/{n['script']}.py", step, **{**given, **inputs})

    def returning(include, prefix=""):
        """line の include の返す節（ブロックの YAML の returns）を、その include の place で走らせた返り"""
        block = line[include]["include"].removeprefix("works-factory-")
        ident = yaml.safe_load((SCRIPTS / block / f"works-factory-{block}.yaml").read_text(encoding="utf-8"))["returns"]
        return node(block, ident, parent, f"{prefix}{include}__{ident}")

    for name in ("answer-start", "fix-in", "fixed", "judged"):
        node("line", name, parent, name)
    for include in BLOCKS:
        if include != "report":
            returning(include, "plan-rounds." if include in ("plan", "plan-review-run") else "")
    gathered = node("line", "collect", parent, "collect")
    node("report", "facts", parent, "report__facts", sections=json.dumps(gathered.get("sections")),
         facts=json.dumps(gathered.get("facts")))
    reported = returning("report")
    returned = node("line", "result", parent, "result", report=json.dumps(reported))
    child = ev / "child-1"
    child.mkdir()
    node("fix", "finish", child, "finish")
    for name, flow, value in (("parent", LINE, returned), ("child-1", "works-factory-fix", None)):
        nodes = [{"nodeId": n, "state": COMPLETED if started and flow == LINE and ALWAYS_RAN.match(n) else SKIPPED}
                 for n in sorted(stepnames.step_names(flow))]
        record = {"id": name, "status": "completed", "nodes": nodes,
                  "terminal_record": {"status": "completed", "nodes": nodes, "returns": {"value": value},
                                      "artifacts": {"root": str(ev / name)}}}
        (ev / "record" / f"{name}.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return attempt


class IdleRunCase(unittest.TestCase):
    """照らしの基準: その能力が働かなかった run では当たらない照らしだけを seen にする。何も働かなかった run に当たる行は、照らしを
    種の run の中身でしか当たらない字や値に替えるか、scenario-only・seed-cannot に移す。seen でない行も、当たれば unexpected と
    言えなくなるので同じ"""

    def test_no_row_holds_on_a_run_where_nothing_worked(self):
        for started in (False, True):
            with self.subTest(started=started):
                got = evidence.check(idle_run(hermetic.tmpdir(self), started))
                held = [f"{r['id']}（{r['kind']}）: {r['detail']}" for r in got
                        if r["state"] in (evidence.SEEN, evidence.UNEXPECTED)]
                self.assertEqual(held, [], "\n".join(held))
                self.assertEqual([r["id"] for r in got if r["state"] == evidence.UNREADABLE], [])


class EvidenceCheckCase(unittest.TestCase):
    def setUp(self):
        self.ev = hermetic.tmpdir(self) / "evidence"
        self.ev.mkdir()

    def put(self, name, text):
        (self.ev / name).parent.mkdir(parents=True, exist_ok=True)
        (self.ev / name).write_text(text, encoding="utf-8")

    def test_each_check_kind_passes_and_fails(self):
        self.put("parent/a.json", json.dumps({"rows": [{"status": "clean"}, {"status": "found", "x": [1]}], "empty": []}))
        self.put("parent/b.md", "- green: false\n")
        self.put("parent/empty.txt", "")
        self.put("record/parent.json", json.dumps({"nodes": [{"nodeId": "start", "state": "skipped"},
                                                             {"nodeId": "fix__prep", "state": "completed"}]}))
        cases = [
            ({"check": "exists", "where": "parent/*.md"}, evidence.PASS),
            ({"check": "exists", "where": "parent/empty.txt"}, evidence.FAIL),
            ({"check": "exists", "where": "parent/nothing"}, evidence.MISSING),
            ({"check": "json-has", "where": "parent/a.json", "path": "rows.1.x"}, evidence.PASS),
            ({"check": "json-has", "where": "parent/a.json", "path": "empty"}, evidence.FAIL),
            ({"check": "json-has", "where": "parent/a.json", "path": "rows.5"}, evidence.FAIL),
            ({"check": "json-equals", "where": "parent/a.json", "path": "rows.*.status", "value": "found"}, evidence.PASS),
            ({"check": "json-equals", "where": "parent/a.json", "path": "rows.0.status", "value": "found"}, evidence.FAIL),
            ({"check": "text-contains", "where": "parent/b.md", "text": "green: false"}, evidence.PASS),
            ({"check": "text-contains", "where": "parent/b.md", "text": "green: true"}, evidence.FAIL),
            ({"check": "node-completed", "where": "record/parent.json", "node": "fix__prep"}, evidence.PASS),
            ({"check": "node-completed", "where": "record/parent.json", "node": "fix"}, evidence.FAIL),
            ({"check": "node-completed", "where": "record/parent.json", "node": "fix__pre"}, evidence.FAIL),
            ({"check": "node-completed", "where": "record/parent.json", "node": "start"}, evidence.FAIL),
        ]
        for rule, want in cases:
            with self.subTest(rule=rule):
                self.assertIsNone(evidence.rule_problem(rule))
                self.assertEqual(evidence.judge(self.ev, rule)[0], want)
        self.assertEqual(evidence.judge(self.ev, cases[6][0])[1], 'parent/a.json: rows.*.status = "found"')

    def table(self, rows):
        """rows を表のファイルに書き、ev を evidence/ に持つ試みのフォルダに run の記録を置く"""
        self.put("record/parent.json", json.dumps({"id": "p1"}))
        table = self.ev.parent / "table.json"
        table.write_text(json.dumps(rows), encoding="utf-8")
        return table

    def checked(self, rows):
        """rows の表で check を当てる。(行ごとの (id, 判じ, 根拠), 終了の値)"""
        got = evidence.check(self.ev.parent, self.table(rows))
        return [(r["id"], r["state"], r["detail"]) for r in got], evidence.exit_code(got)

    def test_absent_row_exits_one_and_unreadable_file_is_named(self):
        self.put("parent/bad.json", "{")
        self.put("parent/good.json", json.dumps({"x": 1}))
        state, detail = evidence.judge(self.ev, {"check": "json-has", "where": "parent/bad.json", "path": "x"})
        self.assertEqual(state, evidence.UNREADABLE)
        self.assertIn("parent/bad.json", detail)
        state, _ = evidence.judge(self.ev, {"check": "json-has", "where": "parent/*.json", "path": "x"})
        self.assertEqual(state, evidence.PASS)
        seen = {"id": "J1", "kind": "seen", "writer": "lib/a.py::f", "check": "json-has", "where": "parent/good.json",
                "path": "x"}
        rows, code = self.checked([seen])
        self.assertEqual((rows, code), ([("J1", "seen", "parent/good.json: x = 1")], 0))
        rows, code = self.checked([seen, {**seen, "id": "J2", "path": "y"}])
        self.assertEqual((rows[1][:2], code), (("J2", "absent"), 1))
        rows, code = self.checked([{**seen, "where": "parent/bad.json"}])
        self.assertEqual((rows[0][1], code), ("unreadable", 1))
        self.assertIn("parent/bad.json: 読めない（JSONDecodeError）", rows[0][2])

    def test_unexpected_seen_is_reported(self):
        self.put("parent/a.md", "見えた\n")
        rule = {"check": "text-contains", "where": "parent/a.md", "text": "見えた"}
        rows, code = self.checked([
            {"id": "J1", "kind": "waits-part", "part": "B1", **rule},
            {"id": "J2", "kind": "backlog", "why": "決めた物", **rule, "text": "見えない"},
            {"id": "J3", "kind": "scenario-only", "why": "筋書きでのみ"},
            {"id": "J4", "kind": "seed-cannot", "why": "種に宣言が無い"},
        ])
        self.assertEqual([r[:2] for r in rows], [("J1", "unexpected"), ("J2", "backlog"), ("J3", "scenario-only"),
                                                 ("J4", "seed-cannot")])
        self.assertEqual(code, 1, "見えた waits-part の行も残りなので落ち")
        rows, code = self.checked([{"id": "J1", "kind": "backlog", "why": "決めた物", **rule},
                                   {"id": "J2", "kind": "handed-off", "why": "渡した", "to": "#1"},
                                   {"id": "J3", "kind": "seed-cannot", "why": "種に宣言が無い", **rule}])
        self.assertEqual(([r[:2] for r in rows], code), ([("J1", "unexpected"), ("J2", "handed-off"),
                                                          ("J3", "unexpected")], 0))

    def test_waits_part_row_left_exits_one(self):
        """部分は全部入ったので、waits-part の行が残る表の check は見えた・見えないに依らず落ちる"""
        rows, code = self.checked([{"id": "J1", "kind": "waits-part", "part": "B1"},
                                   {"id": "J2", "kind": "scenario-only", "why": "筋書きでのみ"}])
        self.assertEqual(([r[:2] for r in rows], code), ([("J1", "waits-part"), ("J2", "scenario-only")], 1))
        rows, code = self.checked([{"id": "J2", "kind": "scenario-only", "why": "筋書きでのみ"},
                                   {"id": "J3", "kind": "seed-cannot", "why": "種に宣言が無い"}])
        self.assertEqual(code, 0)

    def test_counts_are_by_inventory_category(self):
        self.put("parent/a.md", "x\n")
        rows = [{"id": i, "kind": "seen", "writer": "lib/a.py::f", "check": "exists", "where": "parent/a.md"}
                for i in ("L-E01", "L-G02", "J3")]
        got = evidence.check(self.ev.parent, self.table(rows + [{"id": "M4", "kind": "scenario-only", "why": "x"}]))
        self.assertEqual(evidence.counts(got), {"L": {"seen": 2}, "J": {"seen": 1}, "M": {"scenario-only": 1}})

    def test_attempt_without_a_record_stops_by_name(self):
        attempt = self.ev.parent
        done = subprocess.run([sys.executable, str(E2E / "evidence.py"), "check", str(attempt)], capture_output=True,
                              text=True, encoding="utf-8", env=hermetic.child_env(), timeout=60)
        self.assertEqual(done.returncode, 1)
        self.assertIn(str(attempt / "evidence" / "record" / "parent.json"), done.stderr)
        self.assertIn("collect", done.stderr)
        self.assertNotIn("Traceback", done.stderr)


    def test_cli_exits_one_on_an_absent_row(self):
        """筋書きの capabilities-evidenced が読むのは check の終了の値だけ。記録だけの試みのフォルダでは seen の行が absent"""
        self.put("record/parent.json", "{}")
        done = subprocess.run([sys.executable, str(E2E / "evidence.py"), "check", str(self.ev.parent)], capture_output=True,
                              text=True, encoding="utf-8", env=hermetic.child_env(), timeout=60)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertRegex(done.stdout, r"(?m)^absent\t")
        self.assertRegex(done.stdout, r"(?m)^区分 L\t")


class EvidenceCollectCase(unittest.TestCase):
    def test_collect_copies_parent_children_and_records(self):
        tmp = hermetic.tmpdir(self)
        attempt = tmp / "attempt"
        (attempt / "target").mkdir(parents=True)
        (attempt / "home").mkdir()
        shell = tmp / "shell.py"
        shell.write_text(FAKE_SHELL, encoding="utf-8")
        runs = []
        for rid, parent, at in (("p1", None, "1"), ("c2", "p1", "3"), ("c1", "p1", "2"), ("other", "x", "4")):
            root = tmp / "art" / rid
            (root / "sub").mkdir(parents=True)
            (root / "sub" / "out.json").write_text(json.dumps({"run": rid}), encoding="utf-8")
            runs.append({"id": rid, "parent_run_id": parent, "started_at": at, "root": str(root)})
        (attempt / "home" / "fake-runs.json").write_text(json.dumps(runs), encoding="utf-8")
        got = evidence.collect(attempt, "p1", shell)
        self.assertEqual(got, {"run": "p1", "children": ["c1", "c2"], "named": [("parent", "p1"), ("child-1", "c1"), ("child-2", "c2")],
                               "limits": []})
        ev = attempt / "evidence"
        for name, rid in (("parent", "p1"), ("child-1", "c1"), ("child-2", "c2")):
            self.assertEqual(json.loads((ev / name / "sub" / "out.json").read_text(encoding="utf-8")), {"run": rid})
            self.assertEqual(json.loads((ev / "record" / f"{name}.json").read_text(encoding="utf-8"))["id"], rid)
        calls = [json.loads(line) for line in (attempt / "home" / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertTrue(all(c["no_auth"] == "1" and c["args"][-2:] == ["--cwd", str(attempt / "target")] for c in calls))
        self.assertIn(["workflow", "get", "p1", "--json", "--verbose"], [c["args"][:5] for c in calls])

    def test_cli_names_its_usage(self):
        done = subprocess.run([sys.executable, str(E2E / "evidence.py"), "check"], capture_output=True, text=True,
                              encoding="utf-8", env=hermetic.child_env(), timeout=60)
        self.assertEqual(done.returncode, 2)
        self.assertIn("collect", done.stderr)
        self.assertIn("check", done.stderr)


if __name__ == "__main__":
    unittest.main()
