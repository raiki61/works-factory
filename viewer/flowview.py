"""工場の作りの図と run の再生のデータを 1 つの JSON に起こす入口（見る道具。決まりは viewer/AGENTS.md の E25、設計は
docs/design/viewer.md）。引数を読み、src/ の部品を順に呼ぶだけ。読むだけで、書くのは名指した出力のファイルだけ。

使い方（工場の clone の根から）:
    uv run --isolated python3 viewer/flowview.py [--target <対象のリポジトリ> [--run <run の id か頭の字>]] <出力>

- --target が無ければ、今の木の作りだけを出す
- --target が在れば、run の家を殻と同じ関数（bin/_lib/launcher.py の target_root・run_home）で引き、親の run の一覧を入れる。
  --run が無ければ一番新しい親の run を見る。図は run の写し（Archon が run の始めに写し取った作り）から作り、写しが無ければ今の木から作る
- 出力は工場の clone の外に置く（ページに対象の字と会話の中身が入る）
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bin._lib import isolate, launcher  # noqa: E402
from viewer.src import runread, session, shape  # noqa: E402

PACK = json.loads((ROOT / "pack.json").read_text(encoding="utf-8"))["ours"]
ANSWER = "bin/works-factory workflow respond {run} approve|stop --cwd {target}"


class Refused(Exception):
    """見る道具が出力を書かずに止まる訳"""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="viewer/flowview.py", description=__doc__.splitlines()[0])
    parser.add_argument("--target", help="対象のリポジトリ（run の家を引く）")
    parser.add_argument("--run", default="", help="見る run の id か頭の字（無ければ一番新しい親の run）")
    parser.add_argument("out", help="出力のファイル（工場の clone の外）")
    args = parser.parse_args(argv)
    try:
        out = outside_clone(Path(args.out))
        data = build(args.target, args.run, dict(os.environ), Path.cwd())
    except (Refused, launcher.Stop) as stop:
        print(f"flowview: {stop}", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    run = data["run"]
    print(f"{out} {round(out.stat().st_size / 1024)} KB・graph {len(data['shape']['graphs'])}・"
          f"run {run['id'][:8] if run else 'なし'}（一覧 {len(data['runs'])}）・図に当たらないノード {len(data['unmatched'])}")
    return 0


def build(target: str | None, wanted: str, user: dict, here: Path) -> dict:
    """出力のデータ。target が無ければ今の木の作りだけ"""
    texts = {}

    def keep(text: str) -> str:
        """同じ字（Claude Code の既定の system など）を会話ごとに持たず、1 つにして番号で指す"""
        mark = hashlib.sha1(text.encode()).hexdigest()[:12]
        texts.setdefault(mark, text)
        return mark

    data = {"made_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "commit": commit(), "target": "",
            "runs": [], "run": None, "shape_from": "tree", "unmatched": [], "texts": texts}
    if target is None:
        if wanted:
            raise Refused("--run には --target が要る（run の家は対象から引く）")
        data["shape"] = tree_shape()
        return data
    root = launcher.target_root(Path(target), here)
    home = launcher.run_home(user, root)
    db = home / isolate.DIRS["ARCHON_HOME"] / runread.DB_FILE
    if not db.is_file():
        raise Refused(f"run の家 {home} に Archon の DB が無い（この対象で run を回していない）")
    data["target"] = str(root)
    data["runs"] = runread.runs(db)
    try:
        run_id = runread.pick(db, wanted)
    except LookupError as error:
        if wanted:
            raise Refused(str(error)) from None
        data["shape"] = tree_shape()
        return data
    run = runread.run(db, run_id)
    run["answer"] = ANSWER.format(run=run_id, target=root) if run["waiting"] else ""
    copy = Path(run["copy"]) / PACK["pack"] if run["copy"] else None
    if copy is not None and copy.is_dir():
        data["shape"], data["shape_from"] = shape.read(copy, PACK["name_prefix"], ROOT / "docs" / "design"), "run-copy"
    else:
        data["shape"] = tree_shape()
    data["unmatched"] = unmatched(data["shape"]["graphs"], run)
    projects = home / isolate.DIRS["CLAUDE_CONFIG_DIR"] / "projects"
    sessions = {}
    for event in run["events"]:
        preview = event.get("session")
        if preview and preview not in sessions:
            found = session.find(projects, preview)
            if found is not None:
                sessions[preview] = session.read(found, keep)
    run["sessions"] = sessions
    data["run"] = run
    return data


def tree_shape() -> dict:
    return shape.read(ROOT / PACK["folder"], PACK["name_prefix"], ROOT / "docs" / "design")


def unmatched(graphs: dict, run: dict) -> list[str]:
    """run の出来事と飛んだノードに、図の当たる所（at）を付け、当たらない道を返す"""
    folder = next((name for name, graph in graphs.items() if graph["name"] == run["graph"]), None)
    out = []
    for entry in [*run["events"], *run["skipped"]]:
        entry["at"] = shape.locate(graphs, folder, entry["tokens"]) if folder else None
        if entry["at"] is None:
            out.append("/".join(entry["tokens"]))
    return sorted(set(out))


def outside_clone(out: Path) -> Path:
    """出力の実のパス。工場の clone の下なら拒む（ページに対象の字と会話の中身が入るので、公開のリポジトリへ紛れ込ませない）"""
    real = Path(os.path.realpath(out))
    if real.is_relative_to(ROOT):
        raise Refused(f"出力 {real} は工場の clone {ROOT} の下。ページに対象の字と会話の中身が入るので、clone の外に置く")
    return real


def commit() -> str:
    done = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, encoding="utf-8")
    return done.stdout.strip()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
