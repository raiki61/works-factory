"""通しの run の記録を試みのフォルダに写し（collect）、写した記録に照らしの表を当てる（check）。筋書きと較正のランナーが命令として呼ぶ。

  python3 tests/e2e/evidence.py collect <試みのフォルダ> <run>
  python3 tests/e2e/evidence.py check <試みのフォルダ>

約束は docs/plans/2026-10-13-stage1-walking-skeleton.md の「照らしの道具」。試みのフォルダは make_target.py make が作る形
（target/・home/）。collect は殻 bin/works-factory で家 home/ の Archon を引き、親の run と fix の組の子の run（workflow runs の
parent_run_id）の置き場（terminal_record.artifacts.root）を evidence/parent/・evidence/child-<n>/ に写し、workflow get <run> --json
--verbose の出力を evidence/record/parent.json・evidence/record/child-<n>.json に置く（後で消える作業ツリーに依らない）。子の n は
workflow runs の started_at の順で 1 から。

照らしは 5 種（exists・json-has・json-equals・text-contains・node-completed）。where は evidence/ からの glob で、当たったファイルの
どれか 1 つで通れば通る。path は欄の道（. で区切る。数は並びの番目、* はどの要素・値でも）。node-completed は run の記録の nodes[]
に、節の id がちょうど node の節が completed で在れば通る（nodes[] は飛ばされた節・落ちた節も載せるので、節の名だけでは走ったと
言えない。include の頭で照らすと、差し込んだ節のどれか 1 つが走れば通ってしまう）。判じは pass・fail・missing（where に当たる
ファイルが無い）・unreadable（在るが読めない。黙って fail にしない。落とし穴 K15）の 4 つ。標準ライブラリだけ。期限を置かない。

check は照らしの表 evidence.json（能力の棚卸しの 1 行 = 表の 1 行）を読み、行ごとに判じを 1 行出し、最後に区分（L・J・P・F・T・
E・R・M）ごとの数を出す。判じは seen・absent（seen の行の照らしが通らない）・unreadable・unexpected（seen でない行の照らしが
通った。その行は seen へ移す）か、照らしを持たない・通らない行の種類そのもの。absent か unreadable が 1 つでも在れば終了の値 1。
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / "bin" / "works-factory"
EVIDENCE = "evidence"
CHECKS = ("exists", "json-has", "json-equals", "text-contains", "node-completed")
RULE_FIELDS = {"exists": {"check", "where"}, "json-has": {"check", "where", "path"},
               "json-equals": {"check", "where", "path", "value"}, "text-contains": {"check", "where", "text"},
               "node-completed": {"check", "where", "node"}}
COMPLETED = "completed"
PASS, FAIL, MISSING, UNREADABLE = "pass", "fail", "missing", "unreadable"
SHOWN = 80
RUNS_LISTED = "1000"
TABLE = Path(__file__).resolve().with_name("evidence.json")
# 行の種類ごとの欄。照らし（RULE_FIELDS）は seen の行に要り、scenario-only の行は持たず、ほかの行は見えたかを知るために持ってよい。
# seen の writer は where のファイルと欄を書くコードの「リポジトリの根からのパス:行」（run の記録の行は、その節を置く YAML の行）
ROW_FIELDS = {"seen": {"id", "kind", "writer"}, "scenario-only": {"id", "kind", "why"}, "seed-cannot": {"id", "kind", "why"},
              "waits-part": {"id", "kind", "part"}, "backlog": {"id", "kind", "why"},
              "handed-off": {"id", "kind", "why", "to"}}
# 線の配線（#211）がまだ入れていない部分。入った部分の行は seen・scenario-only・seed-cannot へ移す
PARTS = ("A", "B1", "B2", "C", "D1", "D2")
WHERE_HEADS = ("parent/", "child-*/", "record/")
SEEN, ABSENT, UNEXPECTED = "seen", "absent", "unexpected"
WRITER = r"[\w.-]+(?:/[\w.-]+)*:[1-9]\d*"


class Stop(Exception):
    pass


def launch(attempt: Path, *args: str, shell: Path = SHELL) -> subprocess.CompletedProcess:
    """殻で試みのフォルダの家の Archon を起こす（工程を回さない読むだけの命令なので認証を要らなくする）"""
    env = {**os.environ, "WORKS_FACTORY_HOME": str(attempt / "home"), "WORKS_FACTORY_NO_AUTH": "1"}
    return subprocess.run([sys.executable, str(shell), "workflow", *args, "--cwd", str(attempt / "target")],
                          cwd=attempt / "home", env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          encoding="utf-8")


def read_json(attempt: Path, *args: str, shell: Path = SHELL):
    done = launch(attempt, *args, shell=shell)
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError:
        raise Stop(f"workflow {' '.join(args)} が JSON を出さなかった（終了の値 {done.returncode}）: "
                   f"{' '.join(done.stderr.split())[:300]}") from None


def runs(attempt: Path, shell: Path = SHELL) -> list[dict]:
    """家の run の全部の行（workflow runs --json --all）。workflow status は走る・止まった run しか出さないので使わない"""
    listing = read_json(attempt, "runs", "--json", "--all", "--limit", RUNS_LISTED, shell=shell)
    rows = listing.get("runs") if isinstance(listing, dict) else None
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise Stop("workflow runs の返りに runs の一覧が無い")
    return rows


def children(rows: list[dict], run_id: str) -> list[str]:
    mine = [r for r in rows if r.get("parent_run_id") == run_id]
    return [r["id"] for r in sorted(mine, key=lambda r: (str(r.get("started_at") or ""), str(r.get("id"))))]


def fresh(attempt: Path) -> Path:
    """attempt/evidence/ を前の写しを消して空の record/ だけにし、その置き場を返す"""
    out = Path(attempt) / EVIDENCE
    if out.exists():
        shutil.rmtree(out)
    (out / "record").mkdir(parents=True)
    return out


def collect(attempt: Path, run_id: str, shell: Path = SHELL) -> dict:
    """親と子の run の置き場と記録を attempt/evidence/ に写す。写せなかった置き場は limits に名指す（黙って空にしない）"""
    attempt = Path(attempt)
    out = fresh(attempt)
    kids = children(runs(attempt, shell), run_id)
    limits = []
    for name, rid in [("parent", run_id), *((f"child-{n}", kid) for n, kid in enumerate(kids, 1))]:
        record = read_json(attempt, "get", rid, "--json", "--verbose", shell=shell)
        (out / "record" / f"{name}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n",
                                                     encoding="utf-8")
        root = ((record.get("terminal_record") or {}).get("artifacts") or {}).get("root") if isinstance(record, dict) else None
        if isinstance(root, str) and Path(root).is_dir():
            shutil.copytree(root, out / name, symlinks=True)
        else:
            limits.append(f"run {rid} の置き場（{root}）が無い")
    return {"run": run_id, "children": kids, "limits": limits}


def judge(evidence: Path, rule: dict) -> tuple[str, str]:
    """照らし 1 つを evidence に当てる。(判じ, 根拠の 1 行「evidence/ からの相対パス: 欄の道 = 値の頭 80 字」)"""
    files = sorted(p for p in Path(evidence).glob(rule["where"]) if p.is_file())
    if not files:
        return MISSING, f"{rule['where']}: 無い"
    unread = []
    for path in files:
        name = path.relative_to(evidence).as_posix()
        try:
            got = _one(path, rule)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            unread.append(f"{name}: 読めない（{type(e).__name__}）")
            continue
        if got is not None:
            return PASS, f"{name}: {got}"
    if unread:
        return UNREADABLE, "; ".join(unread)
    return FAIL, f"{rule['where']}: 当たらない"


def _one(path: Path, rule: dict) -> str | None:
    kind = rule["check"]
    if kind == "exists":
        return "在る" if path.stat().st_size > 0 else None
    text = path.read_text(encoding="utf-8")
    if kind == "node-completed":
        return _completed(json.loads(text), rule["node"])
    if kind == "text-contains":
        return f"字 = {rule['text'][:SHOWN]}" if rule["text"] in text else None
    for value in _walk(json.loads(text), rule["path"].split(".")):
        if (value == rule["value"]) if kind == "json-equals" else value not in (None, "", [], {}):
            return f"{rule['path']} = {json.dumps(value, ensure_ascii=False)[:SHOWN]}"
    return None


def _completed(record, name: str) -> str | None:
    nodes = record.get("nodes") if isinstance(record, dict) else None
    for node in nodes if isinstance(nodes, list) else ():
        ident = node.get("nodeId") if isinstance(node, dict) else None
        if ident == name and node.get("state") == COMPLETED:
            return f"{ident} = {COMPLETED}"
    return None


def _walk(node, steps: list[str]):
    if not steps:
        yield node
        return
    step, rest = steps[0], steps[1:]
    if step == "*":
        values = node.values() if isinstance(node, dict) else node if isinstance(node, list) else ()
        for value in values:
            yield from _walk(value, rest)
    elif isinstance(node, dict) and step in node:
        yield from _walk(node[step], rest)
    elif isinstance(node, list) and step.isdigit() and int(step) < len(node):
        yield from _walk(node[int(step)], rest)


def rule_problem(rule) -> str | None:
    """照らしの形の崩れ（無ければ None）"""
    if not isinstance(rule, dict) or rule.get("check") not in CHECKS:
        return f"照らし {rule!r} の check が {CHECKS} のどれでもない"
    if set(rule) != RULE_FIELDS[rule["check"]]:
        return f"照らし {rule!r} の欄が {sorted(RULE_FIELDS[rule['check']])} でない"
    if not all(isinstance(rule[k], str) and rule[k] for k in ("where", "path", "text", "node") if k in rule):
        return f"照らし {rule!r} の where・path・text・node が空でない字でない"
    if rule["check"] == "node-completed" and not rule["where"].startswith("record/"):
        return f"照らし {rule!r} の where が run の記録（record/）でない"
    if Path(rule["where"]).is_absolute() or ".." in Path(rule["where"]).parts:
        return f"照らし {rule!r} の where が evidence/ の外を指す"
    return None


def row_problem(row) -> str | None:
    """照らしの表の行の形の崩れ（無ければ None）"""
    if not isinstance(row, dict) or row.get("kind") not in ROW_FIELDS:
        return f"行 {row!r} の kind が {tuple(ROW_FIELDS)} のどれでもない"
    own = ROW_FIELDS[row["kind"]]
    if not own <= set(row) or not all(isinstance(row[k], str) and row[k].strip() for k in own):
        return f"行 {row!r} に {sorted(own)} が空でない字で無い"
    if row["kind"] == "seen" and not re.fullmatch(WRITER, row["writer"]):
        return f"行 {row['id']} の writer が「パス:行」でない"
    if row["kind"] == "waits-part" and row["part"] not in PARTS:
        return f"行 {row['id']} の part が {PARTS} のどれでもない"
    rule = {k: v for k, v in row.items() if k not in own}
    if row["kind"] == "scenario-only":
        return f"scenario-only の行 {row['id']} が照らし {rule!r} を持つ" if rule else None
    if not rule and row["kind"] != "seen":
        return None
    if problem := rule_problem(rule):
        return f"行 {row['id']} の{problem}"
    if not rule["where"].startswith(WHERE_HEADS):
        return f"行 {row['id']} の where が {WHERE_HEADS} のどれでも始まらない"
    return None


def read_table(path: Path = TABLE) -> list[dict]:
    try:
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise Stop(f"照らしの表 {path} を読めない（{type(e).__name__}）") from None
    if not isinstance(rows, list):
        raise Stop(f"照らしの表 {path} が行の並びでない")
    if problems := [p for p in map(row_problem, rows) if p]:
        raise Stop(f"照らしの表 {path} の行が崩れている: " + "; ".join(problems[:5]))
    return rows


def check(attempt: Path, table: Path = TABLE) -> list[dict]:
    """attempt/evidence/ に表の行ごとの照らしを当てる。行ごとに {id, kind, state, detail}"""
    evidence = Path(attempt) / EVIDENCE
    record = evidence / "record" / "parent.json"
    if not record.is_file():
        raise Stop(f"{record} が無い（この試みのフォルダに run の記録が無い）。先に evidence.py collect <試みのフォルダ> <run> を走らせる")
    out = []
    for row in read_table(table):
        rule = {k: v for k, v in row.items() if k not in ROW_FIELDS[row["kind"]]}
        state, detail = judge(evidence, rule) if rule else (None, "照らしを持たない")
        if state == UNREADABLE:
            shown = UNREADABLE
        elif row["kind"] == "seen":
            shown = SEEN if state == PASS else ABSENT
        else:
            shown = UNEXPECTED if state == PASS else row["kind"]
        out.append({"id": row["id"], "kind": row["kind"], "state": shown, "detail": detail})
    return out


def category(row_id: str) -> str:
    return "L" if row_id.startswith("L-") else row_id[0]


def counts(rows: list[dict]) -> dict[str, dict[str, int]]:
    """区分 → 判じ → 数"""
    out: dict[str, dict[str, int]] = {}
    for row in rows:
        per = out.setdefault(category(row["id"]), {})
        per[row["state"]] = per.get(row["state"], 0) + 1
    return out


def exit_code(rows: list[dict]) -> int:
    return 1 if any(row["state"] in (ABSENT, UNREADABLE) for row in rows) else 0


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "collect":
        try:
            got = collect(Path(argv[1]).resolve(), argv[2])
        except Stop as stop:
            print(f"evidence: {stop}", file=sys.stderr)
            return 1
        for limit in got["limits"]:
            print(f"evidence: {limit}", file=sys.stderr)
        print(json.dumps({"run": got["run"], "children": got["children"]}))
        return 1 if got["limits"] else 0
    if len(argv) == 2 and argv[0] == "check":
        try:
            rows = check(Path(argv[1]).resolve())
        except Stop as stop:
            print(f"evidence: {stop}", file=sys.stderr)
            return 1
        for row in rows:
            print("\t".join((row["state"], row["id"], row["kind"], row["detail"])))
        for name, per in counts(rows).items():
            print("\t".join([f"区分 {name}", *(f"{state}={n}" for state, n in sorted(per.items()))]))
        return exit_code(rows)
    print("使い方: evidence.py collect <試みのフォルダ> <run> | evidence.py check <試みのフォルダ>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
