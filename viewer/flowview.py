"""工場の作りの図と run の一覧と再生を 1 枚の HTML に起こす入口（見る道具。決まりは viewer/AGENTS.md の E25、設計は
docs/design/viewer.md）。引数を読み、src/ の部品を順に呼ぶだけ。読むだけで、書くのは名指した出力のファイルと、利用者のキャッシュに
置く図の配置の道具 elkjs（viewer/elkjs.json の版。初めての 1 回だけ網から取る）だけ。

使い方（工場の clone の根から）:
    uv run --isolated python3 viewer/flowview.py [--target <対象のリポジトリ> [--run <run の id か頭の字>]] [--ja-batches <束の置き場>] <出力>
    uv run --isolated python3 viewer/flowview.py --ja-import <束の置き場>
    uv run --isolated python3 viewer/flowview.py --ja-prune

- --target が無ければ、今の木の作りだけを出す
- --target が在れば、run の家を殻と同じ関数（bin/_lib/launcher.py の target_root・run_home）で引き、親の run の一覧を入れる。
  --run が無ければ一番新しい親の run を見る。図は run の写し（Archon が run の始めに写し取った作り）から作り、写しが無ければ今の木から作る
- 出力は工場の clone の外に置く（ページに対象の字と会話の中身が入る）。ページは 1 枚で完結し、別のファイルを読まない
- 日本語の写し（src/ja.py）は訳の控えから引く。--ja-batches は、ページに出す字のうち訳の無い段落を束にして書く（訳すのは取り次ぐ会話。
  束も clone の外に置く）。--ja-import は訳した束を訳の控えに取り込み、--ja-prune は viewer/ja/ から今の木の md に無い段落の訳を消す。
  この 2 つはページを書かない
"""
import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bin._lib import isolate, launcher  # noqa: E402
from viewer.src import ja, page, runread, session, shape, stages  # noqa: E402

PACK = json.loads((ROOT / "pack.json").read_text(encoding="utf-8"))["ours"]
TREE = ROOT / PACK["folder"]
ANSWER = "bin/works-factory workflow respond {run} approve|stop --cwd {target}"


class Refused(Exception):
    """見る道具が出力を書かずに止まる訳"""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="viewer/flowview.py", description=__doc__.splitlines()[0])
    parser.add_argument("--target", help="対象のリポジトリ（run の家を引く）")
    parser.add_argument("--run", default="", help="見る run の id か頭の字（無ければ一番新しい親の run）")
    parser.add_argument("--ja-batches", metavar="DIR", help="ページに出す字のうち訳の無い段落を束にして DIR に書く（clone の外）")
    parser.add_argument("--ja-import", metavar="DIR", help="DIR の訳の束（batch-<n>.ja.txt）を訳の控えに取り込む（ページは書かない）")
    parser.add_argument("--ja-prune", action="store_true", help="viewer/ja/ から今の木の md に無い段落の訳を消す（ページは書かない）")
    parser.add_argument("out", nargs="?", help="出力の HTML（工場の clone の外）")
    args = parser.parse_args(argv)
    if args.ja_import or args.ja_prune:
        return keep_ja(args.ja_import, args.ja_prune)
    if not args.out:
        parser.error("出力の HTML が要る")
    try:
        out = outside_clone(Path(args.out))
        batches = outside_clone(Path(args.ja_batches)) if args.ja_batches else None
        data, todo = build(args.target, args.run, dict(os.environ), Path.cwd())
        html = page.render(data, dict(os.environ))
    except (Refused, launcher.Stop, page.Unfetched) as stop:
        print(f"flowview: {stop}", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    run = data["run"]
    print(f"{out} {round(out.stat().st_size / 1024)} KB・graph {len(data['shape']['graphs'])}・"
          f"run {run['id'][:8] if run else 'なし'}（一覧 {len(data['runs'])}）・図に当たらないノード {len(data['unmatched'])}・"
          f"訳の無い段落 指示の md {data['ja']['md']}・会話 {data['ja']['texts']}")
    if batches is not None:
        print(f"訳の無い段落 {len(todo)} 個 → 束 {ja.export(todo, batches)} 個（{batches}）")
    return 0


def keep_ja(folder: str | None, prune: bool) -> int:
    """訳の控えの取り込みと掃除。取り込みは今の木の md の段落の訳だけを viewer/ja/ に、ほかを利用者のキャッシュに書く。
    拒んだ物（置き場や束が無い・合わない訳）が在れば 1 で終わる（取り込めた訳は取り込む）"""
    refused = []
    if folder:
        to_repo, to_cache, refused = ja.take(Path(folder), dict(os.environ))
        print(f"取り込んだ viewer/ja/ に {to_repo}・キャッシュに {to_cache}")
        for line in refused:
            print(f"拒んだ: {line}", file=sys.stderr)
    if prune:
        print(f"viewer/ja/ から古い段落の訳 {ja.prune()} 個を消した")
    return 1 if refused else 0


def build(target: str | None, wanted: str, user: dict, here: Path) -> tuple[dict, dict[str, str]]:
    """出力のデータと、訳の無い段落（{鍵: 英語}）。target が無ければ今の木の作りだけ"""
    data, pack = read(target, wanted, user, here)
    stages.attach(data)
    return data, ja.attach(data, pack, user)


def read(target: str | None, wanted: str, user: dict, here: Path) -> tuple[dict, Path]:
    """出力のデータ（日本語の写しの前）と、図を作った pack のフォルダ"""
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
        return data, TREE
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
        return data, TREE
    run = runread.run(db, run_id)
    run["answer"] = ANSWER.format(run=run_id, target=shlex.quote(str(root))) if run["waiting"] else ""
    copy = Path(run["copy"]) / PACK["pack"] if run["copy"] else None
    pack = copy if copy is not None and copy.is_dir() else TREE
    if pack == copy:
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
    return data, pack


def tree_shape() -> dict:
    return shape.read(TREE, PACK["name_prefix"], ROOT / "docs" / "design")


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
