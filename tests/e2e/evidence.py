"""通しの run の記録を試みのフォルダに写し（collect）、写した記録に照らしを当てる（judge）。筋書きと較正のランナーが命令として呼ぶ。

  python3 tests/e2e/evidence.py collect <試みのフォルダ> <run>

約束は docs/plans/2026-10-13-stage1-walking-skeleton.md の「照らしの道具」。試みのフォルダは make_target.py make が作る形
（target/・home/）。collect は殻 bin/works-factory で家 home/ の Archon を引き、親の run と fix の組の子の run（workflow runs の
parent_run_id）の置き場（terminal_record.artifacts.root）を evidence/parent/・evidence/child-<n>/ に写し、workflow get <run> --json
--verbose の出力を evidence/record/parent.json・evidence/record/child-<n>.json に置く（後で消える作業ツリーに依らない）。子の n は
workflow runs の started_at の順で 1 から。

照らしは 4 種（exists・json-has・json-equals・text-contains）。where は evidence/ からの glob で、当たったファイルのどれか 1 つで
通れば通る。path は欄の道（. で区切る。数は並びの番目、* はどの要素・値でも）。判じは pass・fail・missing（where に当たる
ファイルが無い）・unreadable（在るが読めない。黙って fail にしない。落とし穴 K15）の 4 つ。標準ライブラリだけ。期限を置かない。
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHELL = ROOT / "bin" / "works-factory"
EVIDENCE = "evidence"
CHECKS = ("exists", "json-has", "json-equals", "text-contains")
RULE_FIELDS = {"exists": {"check", "where"}, "json-has": {"check", "where", "path"},
               "json-equals": {"check", "where", "path", "value"}, "text-contains": {"check", "where", "text"}}
PASS, FAIL, MISSING, UNREADABLE = "pass", "fail", "missing", "unreadable"
SHOWN = 80
RUNS_LISTED = "1000"


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
    if kind == "text-contains":
        return f"字 = {rule['text'][:SHOWN]}" if rule["text"] in text else None
    for value in _walk(json.loads(text), rule["path"].split(".")):
        if (value == rule["value"]) if kind == "json-equals" else value not in (None, "", [], {}):
            return f"{rule['path']} = {json.dumps(value, ensure_ascii=False)[:SHOWN]}"
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
    if not all(isinstance(rule[k], str) and rule[k] for k in ("where", "path", "text") if k in rule):
        return f"照らし {rule!r} の where・path・text が空でない字でない"
    if Path(rule["where"]).is_absolute() or ".." in Path(rule["where"]).parts:
        return f"照らし {rule!r} の where が evidence/ の外を指す"
    return None


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
    print("使い方: evidence.py collect <試みのフォルダ> <run>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
