"""欠陥を仕込んだ較正の束（corpus.json）の読み手（テストのモジュールではない。test_*.py に当たらない）。

束を読んで形を確かめ（load）、1 行の仕込みを種の写しに当てて書き出し（materialize）、写しで種の試験と証人を
子の Python で走らせ（seed_results・witness_result）、後の走り手が 1 行の run の結果を数える（score）。
標準ライブラリだけ。期限を置かない（持ち主の決め no-timeouts）。git の操作はしない。

    python3 tests/calibration/corpus.py list
    python3 tests/calibration/corpus.py materialize <id> <dest> [--corpus <corpus.json>]
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CORPUS = HERE / "corpus.json"
DESIGN = ROOT / "docs" / "design.md"
ROW_HEAD = re.compile(r"`([^`]+)`(?:（[^）]*）)?")

if str(ROOT / "lib") not in sys.path:
    sys.path.append(str(ROOT / "lib"))   # 頭に入れると lib/tests が根の tests を隠す（tests/AGENTS.md）
from report import OUTCOMES  # noqa: E402

KINDS = ("boundary", "error-path-succeeds", "test-blesses-bug", "comment-lies", "dead-code", "hidden-scope",
         "swallowed-error", "stand-in-diverges", "main-path-broken", "none")
WITNESSLESS = ("comment-lies", "dead-code", "none")   # 振る舞いを変えない型と対照
ENTRIES = ("change", "request")
VIEWS = ("tests", "review")
FACTORIES = ("works", "works-factory")
UNREACHED = ("record_invalid", "interrupted", "stopped_by_request", "stopped_by_human", "stopped_by_line")
MIN_AIMS = 6
HEAD_FIELDS = {"about": str, "seed": str, "run_inputs": dict, "rows": list, "dropped": list}
ROW_FIELDS = {"id": str, "kind": str, "entry": str, "visible": str, "edits": list, "red": list,
              "witness": (str, type(None)), "request": list, "catcher": (str, type(None)), "outcome": str, "why": str}
OBSERVED_FIELDS = ("id", "factory", "run_id", "outcome", "flagged")
INCONCLUSIVE = "INCONCLUSIVE"
VERDICTS = ("CAUGHT", "ESCAPED", "CLEAN", "FALSE_ALARM", INCONCLUSIVE)
COPY_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


class CorpusError(Exception):
    """束の形の崩れ。見つけた訳を全部、1 行ずつ並べる"""


class NotInjected(Exception):
    """仕込みの old が、当てる時点の字の中にちょうど 1 か所でない"""


def load(path=CORPUS) -> dict:
    path = pathlib.Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CorpusError(f"{path} が JSON として読めない: {e}") from None
    problems = _problems(data, path.parent)
    if problems:
        raise CorpusError(f"{path} の形が崩れている:\n" + "\n".join(problems))
    return data


def _acceptance_ids() -> set:
    """受け入れの一覧の各行（- [ ] …）の頭に・でつながる id。id の後ろの（禁: …）は飛ばす。行の文の backtick の語は受けない"""
    text = DESIGN.read_text(encoding="utf-8")
    section = text[text.index("### 受け入れの一覧"):]
    end = section.find("\n## ")
    ids = set()
    for row in re.findall(r"^- \[[ x]\] (.*)$", section if end < 0 else section[:end], re.M):
        pos = 0
        while head := ROW_HEAD.match(row, pos):
            ids.add(head[1])
            pos = head.end()
            if not row.startswith("・", pos):
                break
            pos += 1
    return ids


def _problems(data, folder) -> list:
    if not isinstance(data, dict):
        return ["頭が dict でない"]
    out = [f"頭の欄 {k} が無い" for k in HEAD_FIELDS if k not in data]
    out += [f"頭の欄 {k} の型が違う" for k, t in HEAD_FIELDS.items() if k in data and not isinstance(data[k], t)]
    if out:
        return out
    seed = folder / data["seed"]
    if not seed.is_dir():
        out.append(f"種のフォルダ {data['seed']} が無い")
    for i, gone in enumerate(data["dropped"]):
        if not (isinstance(gone, dict) and set(gone) == {"id", "why"}):
            out.append(f"dropped[{i}] が {{id, why}} でない")
    known = _acceptance_ids()
    ids = []
    for i, row in enumerate(data["rows"]):
        name = f"rows[{i}] ({row.get('id') if isinstance(row, dict) else '?'})"
        if not isinstance(row, dict):
            out.append(f"{name}: dict でない")
            continue
        if isinstance(row.get("id"), str):
            ids.append(row["id"])
        out += [f"{name}: {p}" for p in _row_problems(row, seed, known)]
    out += [f"id {x} が 2 つ以上在る" for x in sorted({x for x in ids if ids.count(x) > 1})]
    rows = [r for r in data["rows"] if isinstance(r, dict)]
    for field, words in (("entry", ENTRIES), ("visible", VIEWS)):
        missing = set(words) - {r.get(field) for r in rows if isinstance(r.get(field), str)}
        if missing:
            out.append(f"{field} が {sorted(missing)} の行が無い")
    if not any(r.get("kind") == "none" for r in rows):
        out.append("対照の行（kind none）が無い")
    aims = {r.get("catcher") for r in rows if isinstance(r.get("catcher"), str)}
    if len(aims) < MIN_AIMS:
        out.append(f"狙いの id が {len(aims)} 種（{MIN_AIMS} 種以上要る）")
    return out


def _row_problems(row, seed, known) -> list:
    out = [f"欄 {k} が無い" for k in ROW_FIELDS if k not in row]
    out += [f"欄 {k} の型が違う" for k, t in ROW_FIELDS.items() if k in row and not isinstance(row[k], t)]
    if out:
        return out
    for field, words in (("kind", KINDS), ("entry", ENTRIES), ("visible", VIEWS)):
        if row[field] not in words:
            out.append(f"{field} {row[field]} が {words} のどれでもない")
    if row["outcome"] not in OUTCOMES:
        out.append(f"outcome {row['outcome']} が lib/report.py の OUTCOMES に無い")
    if not row["why"].strip():
        out.append("why が空")
    if not row["edits"]:
        out.append("edits が空")
    for j, e in enumerate(row["edits"]):
        if not (isinstance(e, dict) and set(e) == {"file", "old", "new"} and all(isinstance(v, str) for v in e.values())):
            out.append(f"edits[{j}] が {{file, old, new}} の字でない")
        elif e["old"] == e["new"]:
            out.append(f"edits[{j}] の old と new が同じ")
    if bool(row["red"]) != (row["visible"] == "tests"):
        out.append("red は visible が tests の時だけ空でない")
    needs_witness = row["visible"] == "review" and row["kind"] not in WITNESSLESS
    if needs_witness != isinstance(row["witness"], str):
        out.append("witness は review の行で振る舞いを変える型の時だけ本文、ほかは null")
    if not row["request"]:
        out.append("request が空")
    for j, line in enumerate(row["request"]):
        if not (isinstance(line, dict) and set(line) == {"where", "text"} and isinstance(line["where"], str)):
            out.append(f"request[{j}] が {{where, text}} でないか where が字でない")
        elif not (seed / line["where"]).exists():
            out.append(f"request[{j}] の where {line['where']} が種に無い")
    control = row["kind"] == "none"
    if (row["catcher"] is None) != control:
        out.append("catcher が null なのは対照（kind none）だけ")
    also = row.get("also", [])
    if not (isinstance(also, list) and all(isinstance(x, str) for x in also)):
        return out + ["also が字の並びでない"]
    if control and also:
        out.append("also は対照（kind none）に置かない（score は対照の also を数えない）")
    aims = _aims(row)
    out += [f"当てる先 {a} が docs/design.md の受け入れの一覧に無い" for a in aims if a not in known]
    if any(a.startswith("p1.") for a in aims) and row["entry"] != "change":
        out.append("p1. の素材の役を当てる行は entry が change（依頼だけの run では起きない）")
    return out


def _aims(row) -> list:
    return [row["catcher"], *row.get("also", [])] if row["catcher"] else []


def _row(data, row_id) -> dict:
    for row in data["rows"]:
        if row["id"] == row_id:
            return row
    raise CorpusError(f"行 {row_id} が束に無い")


def _injected(seed: pathlib.Path, edits) -> dict:
    texts = {}
    for e in edits:
        text = texts.get(e["file"])
        if text is None:
            target = seed / e["file"]
            if not target.is_file():
                raise NotInjected(f"{e['file']} が種に無いので old が 0 か所（ちょうど 1 か所が要る）: {e['old']!r}")
            text = target.read_text(encoding="utf-8")
        count = text.count(e["old"])
        if count != 1:
            raise NotInjected(f"{e['file']} に old が {count} か所（ちょうど 1 か所が要る）: {e['old']!r}")
        texts[e["file"]] = text.replace(e["old"], e["new"])
    return texts


def materialize(row_id, dest, corpus=None) -> dict:
    path = pathlib.Path(corpus or CORPUS)
    data = load(path)
    row = _row(data, row_id)
    seed = path.parent / data["seed"]
    dest = pathlib.Path(dest).resolve()
    if any(dest.iterdir()):
        raise ValueError(f"{dest} が空でない")
    texts = _injected(seed, row["edits"])
    base, head = dest / "base", dest / "head"
    for tree in (base, head):
        shutil.copytree(seed, tree, ignore=COPY_IGNORE)
    for tree in (head, base) if row["entry"] == "request" else (head,):
        for name, text in texts.items():
            (tree / name).write_text(text, encoding="utf-8")
    request = dest / "request.json"
    request.write_text(json.dumps(row["request"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"id": row["id"], "entry": row["entry"], "base": str(base), "head": str(head), "request": str(request)}


def _child(tree, code, *args, stdin=None):
    """tree で子の Python を起こす。-B は -E が PYTHONDONTWRITEBYTECODE を読まないため（孫は環境の方を読む）"""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, "-E", "-s", "-B", "-c", code, str(tree), *args], input=stdin,
                          capture_output=True, text=True, encoding="utf-8", cwd=tree, env=env)


SEED_RUNNER = """
import json, sys, unittest
tree = sys.argv[1]
sys.path.insert(0, tree)
result = unittest.TestResult()
unittest.defaultTestLoader.discover(tree, pattern="test_*.py", top_level_dir=tree).run(result)
print(json.dumps({"ran": result.testsRun, "failures": sorted(t.id() for t, _ in result.failures),
                  "errors": sorted(t.id() for t, _ in result.errors)}))
"""

WITNESS_ASSERT = 3
WITNESS_RUNNER = f"""
import sys
sys.path.insert(0, sys.argv[1])
try:
    exec(compile(sys.stdin.read(), "<witness>", "exec"), {{"__name__": "__witness__"}})
except AssertionError:
    sys.exit({WITNESS_ASSERT})
"""


def seed_results(tree) -> dict:
    done = _child(tree, SEED_RUNNER)
    lines = done.stdout.strip().splitlines()
    try:
        return json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError):
        raise RuntimeError(f"{tree} の種の試験が結果を出さなかった（終了の値 {done.returncode}）:\n{done.stderr}") from None


def witness_result(tree, source) -> str:
    code = _child(tree, WITNESS_RUNNER, stdin=source).returncode
    return "pass" if code == 0 else "assert" if code == WITNESS_ASSERT else "error"


def _observed_problem(row, observed):
    if not isinstance(observed, dict):
        return "observed が dict でない"
    missing = [k for k in OBSERVED_FIELDS if k not in observed]
    if missing:
        return f"observed に欄 {missing} が無い"
    if observed["id"] != row["id"]:
        return f"observed の id {observed['id']} が行の id {row['id']} と違う"
    if observed["factory"] not in FACTORIES:
        return f"observed の factory {observed['factory']} が {FACTORIES} のどれでもない"
    flagged = observed["flagged"]
    if not (isinstance(flagged, list) and all(isinstance(x, str) for x in flagged)):
        return "observed の flagged が字の並びでない"
    return None


def score(row, observed) -> dict:
    """INCONCLUSIVE の run は測れていないので missed_by を空にする（足し合わせて見逃しの関門を数えられるように）"""
    aims = _aims(row)
    problem = _observed_problem(row, observed)
    if problem:
        return {"id": row["id"], "verdict": INCONCLUSIVE, "aimed_hit": False, "caught_by": [], "missed_by": [],
                "outcome_as_expected": False, "detail": problem}
    flagged, outcome = observed["flagged"], observed["outcome"]
    caught_by = [a for a in aims if a in flagged]
    out = {"id": row["id"], "aimed_hit": row["catcher"] in flagged, "caught_by": caught_by,
           "missed_by": [a for a in aims if a not in flagged], "outcome_as_expected": outcome == row["outcome"]}
    if outcome in UNREACHED or outcome not in OUTCOMES:
        return {**out, "verdict": INCONCLUSIVE, "missed_by": [], "detail": f"結末 {outcome} は判定まで届いていない run"}
    if row["kind"] == "none":
        if flagged:
            return {**out, "verdict": "FALSE_ALARM", "detail": f"対照に所見か赤: {flagged}"}
        if outcome != "no_fix_needed":
            return {**out, "verdict": "FALSE_ALARM", "detail": f"対照の結末が {outcome}（no_fix_needed でない）"}
        return {**out, "verdict": "CLEAN", "detail": ""}
    if caught_by:
        return {**out, "verdict": "CAUGHT", "detail": f"見つけた関門 {caught_by}"}
    return {**out, "verdict": "ESCAPED", "detail": f"当てる先 {aims} のどれも flagged {flagged} に無い"}


def main(argv=None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--corpus", default=str(CORPUS))
    parser = argparse.ArgumentParser(description="欠陥を仕込んだ較正の束の読み手")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", parents=[common])
    made = sub.add_parser("materialize", parents=[common])
    made.add_argument("id")
    made.add_argument("dest")
    args = parser.parse_args(argv)
    if args.command == "list":
        for row in load(args.corpus)["rows"]:
            print(json.dumps({"id": row["id"], "entry": row["entry"], "catcher": row["catcher"]}, ensure_ascii=False))
        return 0
    try:
        print(json.dumps(materialize(args.id, args.dest, corpus=args.corpus), ensure_ascii=False))
    except NotInjected as e:
        print(f"NotInjected: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
