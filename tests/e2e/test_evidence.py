"""照らしの道具 tests/e2e/evidence.py の試験（collect・5 種の照らしの判じ・check）と、照らしの表 evidence.json の試験。
collect の後ろの Archon は偽の殻で、家の fake-runs.json の run を workflow runs・get で答える。

表の試験は、表を能力の棚卸し docs/plans/2026-10-13-capabilities/ と線の配線の文書 docs/plans/2026-10-13-line-wiring.md に
照らす。棚卸しの行は、区分の ID で始まる頭の箇条で「本物の run」の欄を持つ物（ほかの行を指すだけの参照の行と、穴の要約の再掲は
欄を持たない）。"""
import ast
import io
import json
import pathlib
import re
import subprocess
import sys
import tokenize
import unittest

from tests.bin import hermetic, stepnames
from tests.e2e import evidence, make_target

E2E = pathlib.Path(__file__).resolve().parent
ROOT = E2E.parents[1]
INVENTORY = ROOT / "docs" / "plans" / "2026-10-13-capabilities"
INVENTORY_FILES = ("line.md", "judge.md", "plan.md", "fix.md", "tail.md")
WIRING = ROOT / "docs" / "plans" / "2026-10-13-line-wiring.md"
ROW_ID = r"(?:L-[EGWD]|[JPFTERM])\d+[a-z]?"
SCENARIO_ONLY = "筋書きでのみ"
# 基準で seen から移した scenario-only の行の why の頭（棚卸しの字でなく移した訳を持つ）
OUT_OF_REAL_RUN = "本物の通しの照らしの外（#261 の決め直し）: "
# 基準で移した行の棚卸しの「本物の run」の欄の字（筋書きでのみ（本物の通しの照らしの外。在れば <元の名指し>））
OUT_OF_REAL_RUN_MARK = "本物の通しの照らしの外"
# 照らしの where の run の記録 → その run の工程（親は線、子は fix の組ごとの子の run）
RECORDS = {"record/parent.json": "works-factory-line", "record/child-*.json": "works-factory-fix"}
OUTSIDE = "この文書の外"
# 線の中のブロック（置き場の parent/ の次のフォルダ）と線そのもの。fix の組の子の run の置き場は fix
BLOCKS = ("judge", "plan", "plan-review", "fix", "test-gate", "eyes", "merge", "report")
LINE_ITSELF = "line"
WRITERS = ("lib", "workflows", "bin")
# 名を組んで書く・名の表から引いて書くので字で引けない置き場 → 名を組む所・表の行（Archon が書く物は、その節を置く YAML の行）
NAMED_BY_PATTERN = {
    "parent/gates/gate-start.json": "lib/answer.py:64",
    "parent/gates/gate-final.json": "lib/answer.py:64",
    "parent/gates/gate-*.json": "lib/answer.py:64",
    "parent/plan/r1/plan-fields.json": "lib/marks.py:44",
    "parent/fix/fix/plan-fields.json": "lib/marks.py:44",
    "parent/judge/purpose-means.json": "lib/marks.py:57",
    "parent/eyes/r1.json": "workflows/eyes/scripts/eye_verdict.py:18",
    "parent/eyes/r1-comments.json": "workflows/eyes/works-factory-eyes.yaml:142",
    "parent/nodes/*.meta.json": "workflows/fix/works-factory-fix.yaml:175",
    "parent/judge/material-prior-decisions-brief.md": "lib/judge_accept.py:2095",
    "parent/judge/material-prior-decisions.json": "lib/judge_accept.py:2582",
    "parent/plan/r1/brief-1.md": "lib/planfile.py:83",
    "parent/plan/structure/*/eye-prompt-1.md": "lib/eye.py:38",
    "parent/plan-review/plan-review-items/pass-1/item-1.md": "lib/planblk.py:802",
    "parent/plan-review/plan-converge/pass-1/item-1.json": "lib/planblk.py:92",
    "parent/fix/fix/review1-brief.json": "lib/refix.py:163",
    "parent/test-gate/base/logs/*/test_cmd.log": "lib/declared_checks.py:490",
}


class CodeText:
    """リポジトリのコードの字（コメント・Python の docstring を空の行にし、行の番号を保つ）と、コードの全部の定数（大文字の名 = 字）"""

    def __init__(self):
        self._lines: dict[str, list[str]] = {}
        sources = [p for top in WRITERS for p in (ROOT / top).rglob("*") if p.is_file() and p.suffix in (".py", ".yaml", ".sh")
                   and not {"tests", "fixtures"} & set(p.relative_to(ROOT).parts)]
        self.constants: dict[str, list[str]] = {}
        for p in sources:
            if p.suffix == ".py":
                for ident, value in _constants(p.read_text(encoding="utf-8")):
                    self.constants.setdefault(ident, []).append(value)

    def lines(self, rel: str) -> list[str]:
        if rel not in self._lines:
            path = ROOT / rel
            text = path.read_text(encoding="utf-8")
            self._lines[rel] = _python_code(text) if path.suffix == ".py" else [re.sub(r"(^|\s)#.*$", "", line)
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


def inventory() -> dict[str, str]:
    """棚卸しの行の ID → 「本物の run」の欄の字"""
    rows, current = {}, None
    for name in INVENTORY_FILES:
        for line in (INVENTORY / name).read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                current = None
            elif head := re.match(rf"- ({ROW_ID})[ 〔]", line):
                current = head.group(1)
            elif current and (real := re.match(r"\s+- 本物の run: (.*)", line)):
                rows.setdefault(current, real.group(1))
    return rows


def block_of(where: str) -> str:
    """照らしの where を置く書き手のブロック（parent/ の次のフォルダ・child-*/ は fix・ほかは線そのもの）"""
    head, *rest = where.split("/")
    if head.startswith("child-"):
        return "fix"
    return rest[0] if head == "parent" and len(rest) > 1 and rest[0] in BLOCKS else LINE_ITSELF


def wiring() -> tuple[dict[str, set[str]], dict[str, str]]:
    """線の配線の文書の（部分の名 → 閉じる行）と（「この文書の外」の行 → それを名指した節の名）"""
    parts, outside = {}, {}
    part = section = None
    for line in WIRING.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            head = re.match(r"## 部分 (\S+) ", line)
            part = head.group(1) if head else None
            section = OUTSIDE if line.startswith(f"## {OUTSIDE}") else None
        elif section and line.startswith("### "):
            section = line[4:].strip()
        elif part and (closing := re.match(rf"- ({ROW_ID})〔", line)):
            parts.setdefault(part, set()).add(closing.group(1))
        elif section and section != OUTSIDE:
            for named in re.findall(rf"(?<![\w-])({ROW_ID})(?!\d)", line):
                outside.setdefault(named, section)
    return parts, outside


class EvidenceTableCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = evidence.read_table(evidence.TABLE)
        cls.by_id = {row["id"]: row for row in cls.rows}
        cls.inventory = inventory()

    def kind_of(self, kind):
        return {row["id"] for row in self.rows if row["kind"] == kind}

    def test_every_inventory_row_is_in_the_table(self):
        self.assertGreater(len(self.inventory), 1000)
        self.assertEqual(len(self.by_id), len(self.rows), "表に同じ ID の行が 2 つ在る")
        self.assertEqual(set(self.by_id) - set(self.inventory), set(), "棚卸しに無い行が表に在る")
        self.assertEqual(set(self.inventory) - set(self.by_id), set(), "棚卸しの行が表に無い")

    def test_every_row_has_a_known_kind_and_fields(self):
        for row in self.rows:
            with self.subTest(row=row.get("id")):
                self.assertIsNone(evidence.row_problem(row))
        for broken in ({"id": "J1", "kind": "seen", "writer": "lib/a.py:1"}, {"id": "J1", "kind": "maybe", "why": "x"},
                       {"id": "J1", "kind": "seen", "check": "exists", "where": "parent/a"},
                       {"id": "J1", "kind": "seen", "writer": "lib/a.py", "check": "exists", "where": "parent/a"},
                       {"id": "J1", "kind": "seen", "writer": "lib/a.py:1", "check": "node-completed", "where": "parent/a",
                        "node": "x"},
                       {"id": "J1", "kind": "waits-part", "part": "Z"}, {"id": "J1", "kind": "handed-off", "why": "x"},
                       {"id": "J1", "kind": "scenario-only", "why": "x", "check": "exists", "where": "parent/a"},
                       {"id": "J1", "kind": "seen", "writer": "lib/a.py:1", "check": "exists", "where": "elsewhere/a"}):
            with self.subTest(broken=broken):
                self.assertIsNotNone(evidence.row_problem(broken))

    def test_scenario_only_rows_match_the_inventory(self):
        """線の配線の部分は全部 main に入ったので、閉じる行も棚卸しが筋書きでのみと書けば scenario-only（部分を待たない）"""
        scenario_only = self.kind_of("scenario-only")
        says = {i for i, real in self.inventory.items() if real.startswith(SCENARIO_ONLY)}
        never = {i for i, real in self.inventory.items() if SCENARIO_ONLY not in real}
        self.assertEqual(says - scenario_only, set(), "棚卸しが筋書きでのみと書く行が scenario-only でない")
        self.assertEqual(scenario_only & never, set(), "棚卸しが筋書きでのみと書かない行が scenario-only")
        self.assertEqual(self.kind_of("waits-part") - never, set(), "棚卸しが筋書きでのみと書く行が部分を待っている")
        for i in sorted(scenario_only):
            with self.subTest(row=i):
                if self.by_id[i]["why"].startswith(OUT_OF_REAL_RUN):
                    self.assertIn(OUT_OF_REAL_RUN_MARK, self.inventory[i], "基準で移した行の棚卸しの欄が直っていない")
                else:
                    self.assertEqual(self.by_id[i]["why"], self.inventory[i], "欄 why が棚卸しの字でない")

    def test_waits_part_rows_are_closing_rows_of_that_part(self):
        """部分の閉じる行のうち scenario-only でない行は全部 waits-part（本物の run の記録で置き場を決めた行を移す時に、この試験を直す）"""
        parts, _ = wiring()
        for part in evidence.PARTS:
            with self.subTest(part=part):
                waiting = {row["id"] for row in self.rows if row["kind"] == "waits-part" and row["part"] == part}
                self.assertTrue(parts.get(part))
                self.assertEqual(waiting, parts[part] - self.kind_of("scenario-only"))

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
        """seen の行の writer は、能力の決める行（拒み・止め・既定でない側・値を作る行。保存の行でない）で、lib・workflows・bin の
        コードの在る行。決める行は保存の行から離れうるので、where のファイル名かその名を作る定数は、writer のファイルのコードの字
        （コメント・docstring・.md を除く）のどこかに在ればよい。where の置き場の頭のフォルダ（parent/・child-*/ の次）の名も、
        書き手のファイルかそのブロックの script と YAML のコードの字に在る。名を組んで書く置き場は NAMED_BY_PATTERN に名を組む行と
        名指し、名の照らしだけを外す。run の記録の節の行の writer は、その節の id を置く YAML の行"""
        code = CodeText()
        for row in [r for r in self.rows if r["kind"] == "seen"] + [{"id": w, "where": w, "writer": v}
                                                                     for w, v in NAMED_BY_PATTERN.items()]:
            with self.subTest(row=row["id"]):
                path, line = row["writer"].rsplit(":", 1)
                self.assertIn(pathlib.PurePosixPath(path).parts[0], WRITERS)
                lines = code.lines(path)
                self.assertLessEqual(int(line), len(lines))
                self.assertTrue(lines[int(line) - 1].strip(), f"{row['writer']} がコードの行でない（空かコメント）")
                if row.get("check") == "node-completed":
                    steps = {row["node"].split("__", 1)[0], row["node"].rsplit("__", 1)[-1].rsplit(".", 1)[-1]}
                    placed = re.findall(r"\bid: (\S+)", "\n".join(lines[int(line) - 1:int(line) + 1]))
                    self.assertTrue(steps & set(placed), f"{row['writer']} が節 {row['node']} を置く行でない")
                    continue
                if row["where"].startswith("record/"):
                    continue
                rest = row["where"].split("/")[1:]
                folder = rest[0] if len(rest) > 1 and not re.search(r"[*?\[]", rest[0]) else ""
                if folder:
                    block = ROOT / "workflows" / folder
                    here = [code.text(path), *(code.text(p.relative_to(ROOT).as_posix()) for p in sorted(block.rglob("*"))
                                               if p.suffix in (".py", ".yaml") and "fixtures" not in p.parts)]
                    self.assertTrue(any(code.names(t, folder) for t in here), f"{row['where']} のフォルダ {folder} を書き手が作らない")
                if row["where"] in NAMED_BY_PATTERN:
                    continue
                name = rest[-1]
                self.assertNotRegex(name, r"[*?\[]", "glob の名は NAMED_BY_PATTERN に名指す")
                self.assertTrue(code.names(code.text(path), name), f"{path} のコードに {name} の名もその名を作る定数も無い")

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

    def test_backlog_and_handed_off_rows_name_their_place(self):
        _, outside = wiring()
        for row in self.rows:
            with self.subTest(row=row["id"]):
                if row["kind"] == "backlog":
                    self.assertEqual(row["why"], outside.get(row["id"]), "backlog の行は「この文書の外」のその節の名を持つ")
                if row["kind"] == "handed-off":
                    self.assertTrue(row["why"].strip() and row["to"].strip())


SCENARIO = ROOT / "harness" / "runtime.scenario.json"
SCRIPTS = ROOT / "workflows"
IDLE_RUN = "idle"
SKIPPED, COMPLETED = "skipped", evidence.COMPLETED
LINE = "works-factory-line"
# 前の段が全部飛んでも走る線の節: 始め・入口の関所の答え・報告の集め・報告のブロック（AI の書き手は記録が崩れていなければ走る。
# lib/runreport.py の ai_go）・返す節
ALWAYS_RAN = re.compile(r"start|answer-start|collect|report__.*|result")
# start に入力を受けさせない名指し（固定材料から始める道はまだ無い）。受けない start は入力のこだまと版の控えだけを書く
REFUSED_INPUT = "fixture"


def seed_inputs(request: str) -> dict[str, str]:
    """筋書きが線を起こす命令の --input（<request> は種の依頼のパス）"""
    text = json.loads(SCENARIO.read_text(encoding="utf-8"))["assertions"][0]["description"]
    launch = re.search(r"`[^`]* workflow run works-factory-line [^`]*`", text).group(0)
    return {k: request if v == "<request>" else v.strip("'") for k, v in re.findall(r"--input (\w+)=('[^']*'|[^\s`]+)", launch)}


def idle_run(tmp: pathlib.Path, started: bool) -> pathlib.Path:
    """何も働かなかった run の試みのフォルダ。置き場は、どの能力も働かなくても書かれる物だけ: 線の始めの節 start と、各ブロックと
    メイングラフの落ちない返す節・目の prep を、上流が全部飛んだ形（入力が null）で今の書き手のまま走らせた物（判定・計画の空の
    埋め物、目の prep がいつも書く欄、報告の見出しと 0 件の行など）。started が偽なら start は種の入力を受けず（入力のこだまと版の
    控えだけを書く）、run の記録は線と fix の組の子の全部の節が skipped。真なら start は種の入力を受けて書く欄を全部書き、線の
    ALWAYS_RAN の節は completed（ほかは skipped）"""
    made = make_target.make(tmp / "attempt", listed=False)
    target, attempt = pathlib.Path(made["target"]), tmp / "attempt"
    ev = attempt / evidence.EVIDENCE
    (ev / "record").mkdir(parents=True)

    def ptr(rel):
        return json.dumps({"type": "archon_artifact", "run_id": IDLE_RUN, "path": rel})

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
    start = ptr("r1/start.json")   # 線の start が始めの記録を置く所（lib/startrec.py の REL）
    refused = {} if started else {"fix_fixture": REFUSED_INPUT}
    begun = script(parent, "line/scripts/start.py", "", "", **seed_inputs(made["request"]), **refused)
    if begun["ok"] != started:
        raise AssertionError(f"start の ok が {begun['ok']}（{begun['reason']}）")
    for mode in ("base", "final"):
        script(parent, "test-gate/scripts/result.py", f"test-gate-{mode}__result", mode=mode, start=start)
    script(parent, "judge/scripts/verdict.py", objection="")
    judgment = ptr("judge/judgment.json")
    opened = script(parent, "plan/scripts/round.py", ruling="", start=start, judgment=judgment)
    script(parent, "plan/scripts/plan_collect.py", dir=opened["dir"], start=start, judgment=judgment)
    script(parent, "plan-review/scripts/result.py", start=start)
    script(parent, "fix/scripts/collect.py", "fix__fix", mode="")
    (parent / "empty.diff").write_text("", encoding="utf-8")
    script(parent, "eyes/scripts/prep.py", "eyes__prep", start=start, judgment=judgment, purpose=ptr("judge/purpose.json"),
           diff=ptr("empty.diff"), changed="[]", depth="[]", x_scalars="[]", units="[]", fix_units="[]", green_ok="false",
           plan_questions="[]")
    script(parent, "eyes/scripts/verdict.py", "eyes__verdict", start=start, plan_questions="[]")
    for mode in ("seal", "apply"):
        script(parent, "merge/scripts/merge.py", f"merge-{mode}__merge", mode=mode, start=start, sealed_hash="")
    script(parent, "line/scripts/collect.py", start=start)
    facts = script(parent, "report/scripts/facts.py", start=start)
    returned = script(parent, "line/scripts/result.py",
                      **{k: json.dumps(facts[k]) for k in ("ok", "outcome", "stop_reason", "report", "next_request",
                                                           "prior_failures")})
    child = ev / "child-1"
    child.mkdir()
    script(child, "fix/scripts/collect.py", mode="group", group=json.dumps({"group_id": "g1", "unit_ids": ["stats.py"]}))
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
        seen = {"id": "J1", "kind": "seen", "writer": "lib/a.py:1", "check": "json-has", "where": "parent/good.json",
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
        self.assertEqual(code, 0)

    def test_counts_are_by_inventory_category(self):
        self.put("parent/a.md", "x\n")
        rows = [{"id": i, "kind": "seen", "writer": "lib/a.py:1", "check": "exists", "where": "parent/a.md"}
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
        self.assertEqual(got, {"run": "p1", "children": ["c1", "c2"], "limits": []})
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
