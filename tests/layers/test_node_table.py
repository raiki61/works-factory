"""graph の節の表 docs/nodes.json を木に照らす（docs/design.md の「受け入れの一覧」と段 3 の 2。持ち主の決め superset・
no-narrow・no-silent-loosen）。今の works の表の縛り（works/.shared/core/board.py の NodeTable・works/tests/test_board_table.py）を
写し、節の種類は Archon の鍵で見る。表は run の中で読まないので、崩れた表はここで merge の前に拒む。"""
import ast
import json
import pathlib
import re
import unittest
from unittest import mock

from tests.layers import scan
from tests.layers.scan import NODE_KINDS
from tests.layers.trees import tree

ROOT = pathlib.Path(__file__).resolve().parents[2]
TABLE = "docs/nodes.json"
DESIGN = "docs/design.md"
PACK = "pack.json"

# 出典: raiki61/claude-plugins@2aa7c66cf7abe1fe09699ac2942d107123214168 の works/.shared/core/graphloops/graphs/review-loop.json。
# 節の並びもその nodes の順。pack.json の works の止めが動いたら、SIXTY・OPTIONAL・KEEP_SOURCE_NAMES・GRAPH_SHA を新しい版から読み直して SOURCE を動かす。
SOURCE = {"repo": "raiki61/claude-plugins", "commit": "2aa7c66cf7abe1fe09699ac2942d107123214168"}
GRAPH_SHA = "2eb140b879e5"
SIXTY = (
    "p0.base", "p0.local_checks", "p0.premises", "p0.purpose", "p0.purpose_review", "p0.parallel_pr", "p0.prior_decisions",
    "p1.worktree_before", "p1.local_review", "p1.consistency_bypass", "p1.hygiene", "p1.external_standards",
    "p1.procedure_trace", "p1.gate_efficacy", "p1.test_double_fidelity", "p1.main_path_observation", "p1.provenance",
    "p1.worktree_after", "p2.diagnose", "p2.history", "p2.fix_plan", "p2.plan_review", "p2.human_gate",
    "p3.lane_merge", "p3.fix", "p3.fix_delta", "p3.delta_review", "p3.delta_owed", "p3.delta_fix",
    "p3.fix_delta2", "p3.delta_review2", "p3.delta_owed2", "p3.delta_fix2", "p3.gates_cut", "p3.delta_gates",
    "p4.ci", "p4.scalars", "p4.assemble", "r1.comment_candidates", "r1.minimality", "r2.design", "r2.compare",
    "r3.coherence", "r4.hidden_scope", "r4.human_gate", "stop.premise_check", "p4.record", "p4.final_gates", "converge",
    "report.human_items", "report.cold_check", "report", "p2.rejudge", "p2.rejudge_third",
    "spec.write", "spec.review", "spec.revise", "spec.approve", "spec.freeze", "spec.check",
)
OPTIONAL = frozenset({
    "p0.purpose_review", "p0.prior_decisions", "p1.procedure_trace", "p1.gate_efficacy", "p1.test_double_fidelity",
    "p2.history", "p3.delta_review", "r1.comment_candidates", "r1.minimality", "r2.compare", "r3.coherence",
    "r4.hidden_scope", "stop.premise_check", "p2.rejudge", "p2.rejudge_third",
})
# 出典: SOURCE の版の works/docs/keep-essence.md:10-21
KEEP_SOURCE_NAMES = {
    "1": "赤緑の機械の判定", "2": "元から赤のテストの区別", "3": "テストの凍結", "4": "3 回拒まれたら諦める",
    "5": "書き込みの出どころの突き合わせ", "6": "当たる試験を選んで回し、回さなかった試験を名で残す",
    "7": "欠陥の探し方の数え直し", "8": "食い違いの申し出と読むだけの裁定役", "9": "独立設計",
    "10": "守りのファイルに触れたら最後の関所を開く", "11": "直す単位ごとの記録が報告に届く", "12": "世界の解に照らす",
}
# 出典の名に許した直し {鍵: (元の字, 表の字)}。持ち主の決め graph-words で語をグラフの語にそろえた物だけ
KEEP_NAME_REWRITES = {"10": ("最後の関所を開く", "最後の承認ノードを開く")}
KEEP_NAMES = {k: v.replace(*KEEP_NAME_REWRITES[k]) if k in KEEP_NAME_REWRITES else v for k, v in KEEP_SOURCE_NAMES.items()}

BY_KINDS = {
    "role": set(scan.ROLE_KINDS),
    "machine": set(scan.CODE_KINDS),
    "archon": {"approval", "loop_group", "loop", "workflow", "include"},
}
BY = (*BY_KINDS, "absent")
FALLBACKS = ("role", "absent")
GRAPH_FIELDS = {"by", "where", "fallback", "fallback_where", "skippable", "proof", "reason", "gaps"}
KEEP_FIELDS = {"name", "by", "where", "proof", "reason", "gaps"}
GAP = re.compile(r"^#\d+ \S")
FIXTURE = re.compile(r"^workflows/[^/]+/fixtures/[^/]+\.stubs\.yaml$")
DESIGN_ID = re.compile(r"`([a-z][a-z0-9]*(?:\.[a-z0-9_]+)?)`")


class DuplicateKey(ValueError):
    pass


def _no_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateKey(key)
        out[key] = value
    return out


def block_nodes(root, prefix) -> tuple[dict[str, dict[str, str]], dict[str, set[str]]]:
    """木のブロックの節（{ブロック: {節の鍵: 種類}}）と、ブロックごとの include: の値。節の歩き方と include: の集め方は
    層の試験と 1 つ（scan.nodes・scan.includes）"""
    nodes, includes = {}, {}
    for path in sorted((root / "workflows").glob(f"*/{prefix}*.yaml")):
        block = path.parent.name
        if path.name != f"{prefix}{block}.yaml":
            continue
        rel = path.relative_to(root).as_posix()
        nodes[block] = {f"{block}/{scan._top(node, 'id').value}": next((k for k in NODE_KINDS if scan._top(node, k) is not None), None)
                        for node in scan.nodes(root, rel)}
        includes[block] = set(scan.includes(root, rel))
    return nodes, includes


def design_ids(root) -> list[str]:
    """docs/design.md の受け入れの一覧のチェックボックスの行に在る節の名"""
    ids, inside = [], False
    for line in (root / DESIGN).read_text(encoding="utf-8").splitlines():
        if line.startswith("### 受け入れの一覧"):
            inside = True
        elif inside and line.startswith("#"):
            break
        elif inside and re.match(r"^- \[[ x]\] ", line):
            ids += DESIGN_ID.findall(line)
    return ids


def _blank(value) -> bool:
    return not isinstance(value, str) or not value.strip()


def _strings(value) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


class _Check:
    def __init__(self, root):
        self.root = root
        self.out: list[str] = []
        self.held_nodes: dict[str, set[str]] = {}
        self.held_proofs: dict[str, set[str]] = {}
        self.held_rows: dict[str, set[str]] = {}

    def run(self):
        try:
            table = json.loads((self.root / TABLE).read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys)
        except DuplicateKey as e:
            self.out.append(f"{TABLE}: 同じ鍵 {e} が 2 度在る")
            return
        pack = json.loads((self.root / PACK).read_text(encoding="utf-8"))
        self.prefix = pack["ours"]["name_prefix"]
        line = pack["ours"]["line"].removeprefix(self.prefix)
        self.nodes, includes = block_nodes(self.root, self.prefix)
        self.pending = table.get("pending") or {}
        self.held_blocks = set(self.pending) - set(self.nodes)
        self.kinds = {key: kind for found in self.nodes.values() for key, kind in found.items()}
        self.covered: set[str] = set()
        self.where_keys: set[str] = set()
        self._pending()
        self._source(table.get("source") or {}, pack["works"])
        self._graph(table.get("graph") or {})
        self._keep(table.get("keep") or {})
        self._support(table.get("support") or {})
        self._downgrades(table.get("downgrades") or [], table.get("graph") or {})
        self._design(table.get("graph") or {})
        if line in self.nodes:
            self._wiring(table, line, includes[line])
        for key in sorted(set(self.kinds) - self.covered):
            self.out.append(f"{key}: 木の節が表（graph・keep の where・fallback_where・support）のどこにも無い")

    def _pending(self):
        for block, why in self.pending.items():
            if block in self.nodes:
                self.out.append(f"pending.{block}: workflows/{block}/ の YAML が在る。pending から {block} を消す")
            elif _blank(why):
                self.out.append(f"pending.{block}: 理由が無い")

    def _where(self, label, keys) -> tuple[set[str], set[str]]:
        """在る節の種類と、節を含む保留のブロックを返し、無い節を名指す（保留のブロックの節は数えるだけ）"""
        kinds, held = set(), set()
        for key in keys:
            self.covered.add(key)
            block = key.split("/", 1)[0]
            if block in self.held_blocks:
                self.held_nodes.setdefault(block, set()).add(key)
                held.add(block)
            elif key not in self.kinds:
                self.out.append(f"{label}: 節 {key} が木の YAML に無い")
            else:
                kinds.add(self.kinds[key])
        return kinds, held

    def _kind(self, label, want, kinds, held, problem):
        """在る節に want の種類が無ければ赤。保留のブロックの節を含む行は赤にしない。
        そのうち在る節も持つ行は、在る節の種類を照らさなかった行として名を残す（保留の節だけの行は節の数に入る）"""
        if want & kinds:
            return
        if not held:
            self.out.append(f"{label}: {problem}")
        elif kinds:
            for block in held:
                self.held_rows.setdefault(block, set()).add(label)

    def _proofs(self, label, refs):
        if not _strings(refs) or not refs:
            self.out.append(f"{label}: 証が 1 つも無い")
            return
        for ref in refs:
            problem = self._proof(ref)
            if problem:
                self.out.append(f"{label}: 証 {ref} の{problem}")

    def _proof(self, ref) -> str | None:
        path = ref.partition("::")[0]
        for block in self.held_blocks:
            if path.startswith(f"workflows/{block}/") or path == f"tests/workflows/test_{block.replace('-', '_')}.py":
                self.held_proofs.setdefault(block, set()).add(ref)
                return None
        if "::" not in ref:
            if not FIXTURE.match(ref):
                return "形が違う（<パス>::<クラス>.<メソッド> か workflows/<ブロック>/fixtures/<名>.stubs.yaml）"
            return None if (self.root / ref).is_file() else "筋書きのファイルが無い"
        cls, _, method = ref.partition("::")[2].partition(".")
        file = self.root / path
        if not file.is_file():
            return "ファイルが無い"
        tree_ = ast.parse(file.read_text(encoding="utf-8"))
        found = next((n for n in tree_.body if isinstance(n, ast.ClassDef) and n.name == cls), None)
        if found is None:
            return f"クラス {cls} が無い"
        if not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == method for n in found.body):
            return f"メソッド {method} が無い"
        return None

    def _gaps(self, label, row):
        """在る行の能力のうち証が無い・落ちている所。どれも戻す issue を名指す"""
        if "gaps" not in row:
            return
        gaps = row["gaps"]
        if not _strings(gaps) or not gaps:
            self.out.append(f"{label}: gaps が空か文字列の配列でない")
            return
        for gap in gaps:
            if not GAP.match(gap):
                self.out.append(f"{label}: gaps の値 {gap!r} が #<issue の番号> と欠けで始まらない")

    def _source(self, source, works):
        if source.get("graph_sha") != GRAPH_SHA:
            self.out.append(f"source.graph_sha: {source.get('graph_sha')!r} は固めた {GRAPH_SHA} と違う")
        for field, frozen in SOURCE.items():
            if source.get(field) != frozen:
                self.out.append(f"source.{field}: {source.get(field)!r} は出典の {frozen!r} と違う")
            if works.get(field) != frozen:
                self.out.append(f"{PACK}: works.{field} が出典の版 {frozen!r} から動いた。"
                                f"{pathlib.Path(__file__).name} の固めた節と名を新しい版から読み直し、SOURCE と表の source を動かす")

    def _graph(self, graph):
        for name in SIXTY:
            if name not in graph:
                self.out.append(f"graph.{name}: review-graph の節が表に無い")
        for name, row in graph.items():
            label = f"graph.{name}"
            if name not in SIXTY:
                self.out.append(f"{label}: review-graph の 60 節に無い")
            if not isinstance(row, dict):
                self.out.append(f"{label}: 行が object でない")
                continue
            for field in sorted(set(row) - GRAPH_FIELDS):
                self.out.append(f"{label}: 知らない欄 {field}")
            by = row.get("by")
            if by not in BY:
                self.out.append(f"{label}: 知らない by {by!r}（{'・'.join(BY)} のどれか）")
                continue
            if "skippable" in row and (row["skippable"] is not True or name not in OPTIONAL):
                self.out.append(f"{label}: skippable は review-graph で optional の節だけに true で付ける")
            if by == "absent":
                self._absent(label, row)
                continue
            self._present(label, by, row)

    def _absent(self, label, row):
        if _blank(row.get("reason")):
            self.out.append(f"{label}: absent に理由が無い")
        for field in ("where", "fallback", "fallback_where", "proof", "gaps"):
            if field in row:
                self.out.append(f"{label}: absent の行が {field} を持つ")

    def _present(self, label, by, row):
        where = row.get("where")
        if not _strings(where) or not where:
            self.out.append(f"{label}: where が無い")
        else:
            self.where_keys.update(where)
            kinds, held = self._where(label, where)
            self._kind(label, BY_KINDS[by], kinds, held,
                       f"by {by} なのに where に {'・'.join(sorted(BY_KINDS[by]))} の節が無い")
        self._fallback(label, by, row)
        self._proofs(label, row.get("proof"))
        self._gaps(label, row)

    def _fallback(self, label, by, row):
        fallback, fb_where = row.get("fallback"), row.get("fallback_where")
        if fallback is None and fb_where is None:
            return
        if by != "machine":
            self.out.append(f"{label}: fallback は machine の行だけが持てる")
            return
        if fallback not in FALLBACKS:
            self.out.append(f"{label}: fallback {fallback!r} は role か absent")
            return
        if fallback == "absent":
            if fb_where is not None:
                self.out.append(f"{label}: fallback absent なのに fallback_where が在る")
            return
        fb_where = fb_where if _strings(fb_where) else []
        self.where_keys.update(fb_where)
        kinds, held = self._where(label, fb_where)
        self._kind(label, BY_KINDS["role"], kinds, held, "fallback role なのに fallback_where に役の節が無い")

    def _keep(self, keep):
        if sorted(keep, key=lambda k: (len(k), k)) != list(KEEP_NAMES):
            self.out.append(f"keep: 鍵が 1〜12 でない（{', '.join(keep)}）")
        for num, row in keep.items():
            label = f"keep.{num}"
            if not isinstance(row, dict):
                self.out.append(f"{label}: 行が object でない")
                continue
            for field in sorted(set(row) - KEEP_FIELDS):
                self.out.append(f"{label}: 知らない欄 {field}")
            if num in KEEP_NAMES and row.get("name") != KEEP_NAMES[num]:
                self.out.append(f"{label}: name {row.get('name')!r} は {KEEP_NAMES[num]!r} でない")
            if row.get("by", "absent") != "absent":
                self.out.append(f"{label}: by は absent だけが書ける")
            if row.get("by") == "absent":
                self._absent(label, row)
                continue
            where = row.get("where")
            if not _strings(where) or not where:
                self.out.append(f"{label}: where が無い")
                where = []
            self.where_keys.update(where)
            self._where(label, where)
            self._proofs(label, row.get("proof"))
            self._gaps(label, row)

    def _support(self, support):
        for key, why in support.items():
            label = f"support.{key}"
            if _blank(why):
                self.out.append(f"{label}: 理由が無い")
            if key in self.where_keys:
                self.out.append(f"{label}: where か fallback_where にも在る")
            self._where(label, [key])

    def _downgrades(self, rows, graph):
        for i, row in enumerate(rows):
            node = row.get("node") if isinstance(row, dict) else None
            label = f"downgrades[{i}] {node}"
            if not isinstance(graph.get(node), dict) or graph[node].get("by") in (None, "absent"):
                self.out.append(f"{label}: node が graph の absent でない節でない")
            for field in ("what", "versus"):
                if not isinstance(row, dict) or _blank(row.get(field)):
                    self.out.append(f"{label}: {field} が無い")

    def _design(self, graph):
        for name in design_ids(self.root):
            if name not in graph:
                self.out.append(f"{DESIGN}: 受け入れの一覧の {name} が graph に無い")

    def _wiring(self, table, line, line_includes):
        rows = [(f"graph.{n}", r) for n, r in (table.get("graph") or {}).items()]
        rows += [(f"keep.{n}", r) for n, r in (table.get("keep") or {}).items()]
        for label, row in rows:
            if not isinstance(row, dict) or row.get("by") == "absent":
                continue
            keys = [k for field in ("where", "fallback_where") if _strings(row.get(field)) for k in row[field]]
            for block in sorted({k.split("/", 1)[0] for k in keys} - {line}):
                if f"{self.prefix}{block}" not in line_includes:
                    self.out.append(f"{label}: where か fallback_where のブロック {block} が線の include: に無い")


def check(root) -> tuple[list[str], dict[str, tuple[int, int, tuple[str, ...]]]]:
    """表と木の食い違いの行と、保留のブロックごとに照らさなかった（節の数, 証の数, 種類を照らさなかった行の名）"""
    c = _Check(root)
    c.run()
    held = {b: (len(c.held_nodes.get(b, ())), len(c.held_proofs.get(b, ())), tuple(sorted(c.held_rows.get(b, ()))))
            for b in sorted(set(c.held_nodes) | set(c.held_proofs))}
    return c.out, held


def problems(root) -> list[str]:
    """表と木の食い違いを 1 行ずつ返す（無ければ空）"""
    return check(root)[0]


# ---- 壊した木の種 ----

BLOCK_YAML = """name: works-factory-a
nodes:
  - id: x
    script: x
    output_format: {properties: {command: {type: string}}}
  - id: r
    command: r
  - id: g
    approval: {message: m}
  - id: lp
    loop_group:
      nodes:
        - id: inner
          prompt: p
          with: {script: s}
"""
PROOF_PY = "class ACase:\n    def test_ok(self):\n        pass\n"
OK_TEST = "tests/workflows/test_a.py::ACase.test_ok"
OK_FIXTURE = "workflows/a/fixtures/ok.stubs.yaml"
LINE_YAML = "name: works-factory-line\nnodes:\n  - id: start\n    script: start\n  - id: a\n    include: works-factory-a\n"


def base_table() -> dict:
    return {
        "source": {**SOURCE, "graph_sha": GRAPH_SHA},
        "graph": {n: {"by": "absent", "reason": "無し"} for n in SIXTY},
        "keep": {k: {"name": v, "by": "absent", "reason": "無し"} for k, v in KEEP_NAMES.items()},
        "support": {k: "種" for k in ("a/x", "a/r", "a/g", "a/lp", "a/inner")},
        "downgrades": [],
    }


def use(table, section, name, row):
    """行を置き、その where と fallback_where の節を support から外す"""
    table[section][name] = row
    for key in row.get("where", []) + row.get("fallback_where", []):
        table["support"].pop(key, None)
    return table


def files(table=None, **extra) -> dict:
    out = {
        TABLE: table if isinstance(table, str) else json.dumps(table or base_table(), ensure_ascii=False),
        DESIGN: "# 設計\n\n### 受け入れの一覧（review-graph と同じ能力）\n\n- [ ] `p0.base` 差分の根\n\n## 次\n",
        "workflows/a/works-factory-a.yaml": BLOCK_YAML,
        "tests/workflows/test_a.py": PROOF_PY,
        OK_FIXTURE: "stubs: []\n",
        PACK: (ROOT / PACK).read_text(encoding="utf-8"),
    }
    out.update(extra)
    return out


class NodeTableTest(unittest.TestCase):
    def broken(self, table=None, **extra) -> list[str]:
        with tree(files(table, **extra)) as root:
            return problems(root)

    def one(self, needle, table=None, **extra):
        got = self.broken(table, **extra)
        self.assertEqual(len(got), 1, got)
        self.assertIn(needle, got[0])

    def test_seed_is_clean(self):
        self.assertEqual(self.broken(), [])

    def test_real_tree_clean(self):
        self.assertEqual(problems(ROOT), [])

    def test_graph_nodes_are_the_sixty(self):
        t = base_table()
        del t["graph"]["p2.history"]
        self.one("graph.p2.history", t)
        t = base_table()
        t["graph"]["p9.extra"] = {"by": "absent", "reason": "無し"}
        self.one("graph.p9.extra", t)
        t = base_table()
        t["source"]["graph_sha"] = "000000000000"
        self.one("source.graph_sha", t)
        for field in ("repo", "commit"):
            t = base_table()
            t["source"][field] = "old"
            self.one(f"source.{field}: 'old' は出典の", t)
        pack = json.loads((ROOT / PACK).read_text(encoding="utf-8"))
        pack["works"]["commit"] = "0" * 40
        self.one(f"{PACK}: works.commit が出典の版", **{PACK: json.dumps(pack)})
        real = json.loads((ROOT / TABLE).read_text(encoding="utf-8"))
        self.assertEqual(list(real["graph"]), list(SIXTY))

    def test_duplicate_key_refused(self):
        text = json.dumps(base_table(), ensure_ascii=False)
        text = text.replace('"p0.base": {', '"p0.base": {"by": "absent", "reason": "前"}, "p0.base": {', 1)
        self.one("p0.base", text)

    def test_unknown_by_named(self):
        self.one("graph.p0.base: 知らない by 'engine_run'", use(base_table(), "graph", "p0.base", {"by": "engine_run"}))

    def test_unknown_field_named(self):
        t = base_table()
        t["graph"]["p0.base"]["fallback_wehre"] = []
        self.one("graph.p0.base: 知らない欄 fallback_wehre", t)
        t = base_table()
        t["graph"]["p0.base"] = "machine"
        self.one("graph.p0.base: 行が object でない", t)

    def test_absent_needs_reason(self):
        t = base_table()
        t["graph"]["p0.base"]["reason"] = "  "
        self.one("graph.p0.base: absent に理由が無い", t)
        t = base_table()
        del t["graph"]["p0.base"]["reason"]
        self.one("graph.p0.base: absent に理由が無い", t)
        t = base_table()
        t["graph"]["p0.base"]["proof"] = [OK_TEST]
        self.one("graph.p0.base: absent の行が proof を持つ", t)

    def test_where_node_gone_is_red(self):
        t = use(base_table(), "graph", "p0.base", {"by": "machine", "where": ["a/x", "a/gone"], "proof": [OK_TEST]})
        self.one("graph.p0.base: 節 a/gone", t)
        t = base_table()
        t["support"]["b/gone"] = "無いブロック"
        self.one("support.b/gone: 節 b/gone", t)
        self.one("graph.p0.base: where が無い", use(base_table(), "graph", "p0.base", {"by": "machine", "proof": [OK_TEST]}))

    def test_yaml_node_missing_from_table_is_red(self):
        t = base_table()
        del t["support"]["a/inner"]
        self.one("a/inner: 木の節が表", t)

    def test_nodes_walk_is_scans(self):
        """節の歩き方は scan.nodes の 1 つ（scan だけが新しい入れ子を辿るようになっても、表の網羅の照らしがその節を求める）"""
        extra = scan.nodes(ROOT, "workflows/judge/works-factory-judge.yaml")[0]
        walk = scan.nodes
        with mock.patch.object(scan, "nodes", lambda root, rel: [*walk(root, rel), extra] if "/a/" in rel else walk(root, rel)):
            self.one(f"a/{scan._top(extra, 'id').value}: 木の節が表")

    def test_support_overlap_and_reason(self):
        t = use(base_table(), "graph", "p0.base", {"by": "machine", "where": ["a/x"], "proof": [OK_TEST]})
        t["support"]["a/x"] = "重なり"
        self.one("support.a/x: where か fallback_where にも在る", t)
        t = base_table()
        t["support"]["a/x"] = ""
        self.one("support.a/x: 理由が無い", t)

    def test_by_matches_a_where_kind(self):
        row = {"by": "role", "where": ["a/x", "a/g", "a/lp"], "proof": [OK_TEST]}
        self.one("graph.p0.premises: by role", use(base_table(), "graph", "p0.premises", row))
        row = {"by": "machine", "where": ["a/r"], "proof": [OK_TEST]}
        self.one("graph.p0.base: by machine", use(base_table(), "graph", "p0.base", row))
        row = {"by": "archon", "where": ["a/x", "a/r"], "proof": [OK_TEST]}
        self.one("graph.p2.human_gate: by archon", use(base_table(), "graph", "p2.human_gate", row))
        row = {"by": "role", "where": ["a/inner"], "proof": [OK_TEST]}
        self.assertEqual(self.broken(use(base_table(), "graph", "p0.premises", row)), [])

    def test_fallback_only_on_machine(self):
        row = {"by": "role", "where": ["a/r"], "fallback": "absent", "proof": [OK_TEST]}
        self.one("graph.p0.premises: fallback は machine", use(base_table(), "graph", "p0.premises", row))
        row = {"by": "machine", "where": ["a/x"], "fallback": "machine", "proof": [OK_TEST]}
        self.one("graph.p0.base: fallback 'machine'", use(base_table(), "graph", "p0.base", row))
        row = {"by": "machine", "where": ["a/x"], "fallback": "role", "fallback_where": ["a/g"], "proof": [OK_TEST]}
        self.one("graph.p0.base: fallback role なのに", use(base_table(), "graph", "p0.base", row))
        row = {"by": "machine", "where": ["a/x"], "fallback": "absent", "fallback_where": ["b/r"], "proof": [OK_TEST]}
        self.one("graph.p0.base: fallback absent なのに fallback_where", use(base_table(), "graph", "p0.base", row))
        row = {"by": "machine", "where": ["a/x"], "fallback": "role", "fallback_where": ["a/r"], "proof": [OK_TEST]}
        self.assertEqual(self.broken(use(base_table(), "graph", "p0.base", row)), [])

    def test_skippable_only_optional(self):
        t = base_table()
        t["graph"]["p0.base"]["skippable"] = True
        self.one("graph.p0.base: skippable", t)
        t = base_table()
        t["graph"]["r1.minimality"]["skippable"] = True
        self.assertEqual(self.broken(t), [])

    def test_cited_proof_missing_is_red(self):
        for proof, needle in (("tests/workflows/test_b.py::ACase.test_ok", "ファイルが無い"),
                              ("tests/workflows/test_a.py::BCase.test_ok", "クラス BCase が無い"),
                              ("tests/workflows/test_a.py::ACase.test_gone", "メソッド test_gone が無い"),
                              ("workflows/a/fixtures/gone.stubs.yaml", "筋書きのファイルが無い"),
                              ("tests/workflows/test_a.py", "形が違う")):
            with self.subTest(proof=proof):
                row = {"by": "machine", "where": ["a/x"], "proof": [OK_FIXTURE, proof]}
                self.one(f"graph.p0.base: 証 {proof} の{needle}", use(base_table(), "graph", "p0.base", row))
        self.one("graph.p0.base: 証が 1 つも無い", use(base_table(), "graph", "p0.base", {"by": "machine", "where": ["a/x"]}))
        row = {"name": KEEP_NAMES["1"], "where": ["a/x"], "proof": []}
        self.one("keep.1: 証が 1 つも無い", use(base_table(), "keep", "1", row))

    def test_keep_essence_twelve(self):
        t = base_table()
        del t["keep"]["12"]
        self.one("keep: 鍵が 1〜12 でない", t)
        t = base_table()
        t["keep"]["3"]["name"] = "凍結"
        self.one("keep.3: name", t)
        t = base_table()
        t["keep"]["3"]["reason"] = ""
        self.one("keep.3: absent に理由が無い", t)
        t = base_table()
        t["keep"]["3"] = "凍結"
        self.one("keep.3: 行が object でない", t)
        t = base_table()
        t["keep"]["3"]["proff"] = []
        self.one("keep.3: 知らない欄 proff", t)
        row = {"name": KEEP_NAMES["1"], "by": "role", "where": ["a/x"], "proof": [OK_TEST]}
        self.one("keep.1: by は absent だけ", use(base_table(), "keep", "1", row))
        self.one("keep.1: where が無い", use(base_table(), "keep", "1", {"name": KEEP_NAMES["1"], "proof": [OK_TEST]}))
        row = {"name": KEEP_NAMES["1"], "where": ["a/x", "a/r"], "proof": [OK_TEST]}
        self.assertEqual(self.broken(use(base_table(), "keep", "1", row)), [])

    def test_gaps_name_an_issue(self):
        row = {"by": "machine", "where": ["a/x"], "proof": [OK_TEST], "gaps": ["#119 J45: 再開で上書きしない試験が無い"]}
        self.assertEqual(self.broken(use(base_table(), "graph", "p0.base", row)), [])
        for gaps, needle in ((["J45: 番号が無い"], "gaps の値 'J45: 番号が無い' が #<issue の番号> と欠けで始まらない"),
                             (["#119 "], "gaps の値 '#119 ' が #<issue の番号> と欠けで始まらない"),
                             ([], "gaps が空か文字列の配列でない"),
                             ("#119 J45", "gaps が空か文字列の配列でない")):
            with self.subTest(gaps=gaps):
                self.one(f"graph.p0.base: {needle}", use(base_table(), "graph", "p0.base", {**row, "gaps": gaps}))
        t = base_table()
        t["graph"]["p0.base"]["gaps"] = ["#119 J45: 欠け"]
        self.one("graph.p0.base: absent の行が gaps を持つ", t)
        row = {"name": KEEP_NAMES["5"], "where": ["a/x"], "proof": [OK_TEST], "gaps": ["F102: 番号が無い"]}
        self.one("keep.5: gaps の値 'F102: 番号が無い'", use(base_table(), "keep", "5", row))

    def test_design_ids_in_table(self):
        design = "### 受け入れの一覧\n\n- [ ] `p0.base`・`p9.gone` 何か（`workflows/a/fixtures/ok.stubs.yaml`）\n"
        self.one(f"{DESIGN}: 受け入れの一覧の p9.gone", **{DESIGN: design})
        ids = design_ids(ROOT)
        self.assertEqual(len(ids), 59, ids)
        self.assertEqual(set(SIXTY) - set(ids), {"p2.rejudge_third"})

    def test_downgrade_rows_valid(self):
        t = base_table()
        t["downgrades"] = [{"node": "p0.base", "what": "下げた", "versus": "元"}]
        self.one("downgrades[0] p0.base: node", t)
        t = use(base_table(), "graph", "p0.base", {"by": "machine", "where": ["a/x"], "proof": [OK_TEST]})
        t["downgrades"] = [{"node": "p0.base", "what": "下げた", "versus": " "}]
        self.one("downgrades[0] p0.base: versus", t)

    def test_where_blocks_wired_into_line(self):
        def wired(line_yaml):
            t = use(base_table(), "graph", "p0.base", {"by": "machine", "where": ["a/x"], "proof": [OK_TEST]})
            t["support"].update({"line/start": "始め", "line/a": "差し込み"})
            return self.broken(t, **{"workflows/line/works-factory-line.yaml": line_yaml})

        self.assertEqual(wired(LINE_YAML), [])
        got = wired(LINE_YAML.replace("include: works-factory-a", "include: works-factory-b"))
        self.assertEqual(len(got), 1, got)
        self.assertIn("graph.p0.base: where か fallback_where のブロック a が線の include: に無い", got[0])
        t = use(base_table(), "graph", "p0.base",
                {"by": "machine", "where": ["a/x"], "fallback": "role", "fallback_where": ["b/r"], "proof": [OK_TEST]})
        t["support"].update({"line/start": "始め", "line/a": "差し込み"})
        got = self.broken(t, **{"workflows/line/works-factory-line.yaml": LINE_YAML,
                                "workflows/b/works-factory-b.yaml": "name: works-factory-b\nnodes:\n  - id: r\n    command: r\n"})
        self.assertEqual(len(got), 1, got)
        self.assertIn("graph.p0.base: where か fallback_where のブロック b が線の include: に無い", got[0])

    def test_pending_block_tolerated_while_absent(self):
        t = base_table()
        t["pending"] = {"line": "線が入るまで"}
        row = {"by": "archon", "where": ["line/gate", "line/ask"], "proof": ["tests/workflows/test_line.py::LineCase.test_x"]}
        use(t, "graph", "p2.human_gate", row)
        t["support"]["line/start"] = "始め"
        with tree(files(t)) as root:
            self.assertEqual(check(root), ([], {"line": (3, 1, ())}))
        row = {"by": "role", "where": ["a/x", "line/r"], "proof": [OK_TEST]}
        use(t, "graph", "p0.premises", row)
        with tree(files(t)) as root:
            self.assertEqual(check(root), ([], {"line": (4, 1, ("graph.p0.premises",))}))
        row = {"by": "machine", "where": ["a/x"], "fallback": "role", "fallback_where": ["a/g", "line/r2"], "proof": [OK_TEST]}
        use(t, "graph", "p0.base", row)
        with tree(files(t)) as root:
            self.assertEqual(check(root), ([], {"line": (5, 1, ("graph.p0.base", "graph.p0.premises"))}))

    def test_pending_block_stale_is_red(self):
        t = base_table()
        t["pending"] = {"line": "線が入るまで"}
        t["support"].update({"line/start": "始め", "line/a": "差し込み"})
        self.one("pending.line: workflows/line/ の YAML が在る。pending から line を消す", t,
                 **{"workflows/line/works-factory-line.yaml": LINE_YAML})
        t = base_table()
        t["pending"] = {"zz": " "}
        self.one("pending.zz: 理由が無い", t)

    def test_pending_rows_are_named(self):
        errors, held = check(ROOT)
        self.assertEqual(errors, [])
        pending = json.loads((ROOT / TABLE).read_text(encoding="utf-8")).get("pending") or {}
        self.assertEqual(set(held), set(pending))
        if held:
            self.skipTest("・".join(f"保留: {b} の節 {n} 個・証 {m} 個・種類を照らさない行 {len(rows)} 個 {list(rows)}（{pending[b]}）"
                                    for b, (n, m, rows) in held.items()))


if __name__ == "__main__":
    unittest.main()
