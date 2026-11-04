"""run の記録を OpenTelemetry のトレースに組み、利用者が名指した受け口へ OTLP/HTTP で送る入口（見る道具。決まりは viewer/AGENTS.md の
E25、設計は docs/design/viewer.md の 8 章、持ち主の決め run-trace-otlp）。引数を読み、src/ の部品を順に呼ぶだけ。

使い方（工場の clone の根から。受け口は利用者が手元で起こす。例 Arize Phoenix の http://127.0.0.1:6006/v1/traces）:
    uv run --isolated --extra trace python3 viewer/runtrace.py --target <対象のリポジトリ> [--run <run の id か頭の字>]
        [--endpoint <URL>] [--remote]

- 順: 先に送り先を決め（src/sendto.py。拒めば run を読まずに 1 行の訳と終了の値 2 で止まる）、自分の過程の env から OTEL_ の名を
  外し、run を選び（--run が無ければ一番新しい親の run）、span の木を組み（src/trace.py）、src/otlp.py を関数の中で読んで送る。
  頭で otlp を読まないので、拒む道は SDK の無い環境でも走り切る
- 送り先は --endpoint か env の OTEL_EXPORTER_OTLP_TRACES_ENDPOINT・OTEL_EXPORTER_OTLP_ENDPOINT で名指す。既定の送り先は持たない。
  会話と道具の中身は span に載る。手元でない送り先は --remote を付けた時だけ送る
- run の家は殻と同じ関数（bin/_lib/launcher.py の target_root・run_home）で引き、Archon の DB は読むだけで開く
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bin._lib import isolate, launcher  # noqa: E402
from viewer.src import runread, sendto, session, shape, stages, trace  # noqa: E402

PACK = json.loads((ROOT / "pack.json").read_text(encoding="utf-8"))["ours"]
TREE = ROOT / PACK["folder"]


class Refused(Exception):
    """送らずに止まる訳"""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="viewer/runtrace.py", description=__doc__.splitlines()[0])
    parser.add_argument("--target", required=True, help="対象のリポジトリ（run の家を引く）")
    parser.add_argument("--run", default="", help="送る run の id か頭の字（無ければ一番新しい親の run）")
    parser.add_argument("--endpoint", help="OTLP/HTTP の受け口の URL（そのまま使う。例 http://127.0.0.1:6006/v1/traces）")
    parser.add_argument("--remote", action="store_true", help="手元でない送り先へも送る（span は会話と道具の中身を持つ）")
    args = parser.parse_args(argv)
    try:
        where = sendto.decide(args.endpoint, dict(os.environ), args.remote)
    except sendto.Refused as stop:
        print(f"runtrace: {stop}", file=sys.stderr)
        return 2
    for name in sendto.dropped(os.environ):
        del os.environ[name]
    try:
        data = read(args.target, args.run, dict(os.environ), Path.cwd())
        built = trace.build(data)
        if not built["spans"] or not built["spans"][0]["start"]:
            raise Refused(f"run {data['run']['id']} に時刻の在る出来事が無い")
        filled = timed(built)
    except (Refused, launcher.Stop) as stop:
        print(f"runtrace: {stop}", file=sys.stderr)
        return 2
    from viewer.src import otlp   # 決めの後、OTEL_ の名を外した後に読む
    try:
        sent = otlp.send(built, where)
    except otlp.Failed as failed:
        print(f"runtrace: {failed}", file=sys.stderr)
        return 1
    unread = sum(built["unread"].values())
    print(f"run {data['run']['id'][:8]}・span {sent} → {where.url}・trace {built['trace_id']}・読めなかった物 {unread}"
          f"・祖先の時刻で埋めた span {filled}")
    return 0


def timed(built: dict) -> int:
    """時刻の無い span（時刻が 1 つも読めない下請け・時刻の読めない往復。trace.build は始めも終わりも None で返す）を、一番近い
    時刻の在る祖先の始めと終わりで埋め、印 trace.TIME_FROM_ANCESTOR を付け、埋めた数を返す。読めなかった物（unread）には足さない
    （時刻の読めない往復は会話の読みが既に数えているので、足すと二重になる）。送らずに落とすと、子の span が親を失う"""
    by_id = {span["id"]: span for span in built["spans"]}

    def times(span: dict) -> tuple:
        seen = set()
        while span is not None and not (span["start"] and span["end"]) and span["id"] not in seen:
            seen.add(span["id"])
            span = by_id.get(span["parent"])
        return (span["start"], span["end"]) if span is not None and span["start"] and span["end"] else (None, None)

    filled = 0
    for span in built["spans"]:
        if not (span["start"] and span["end"]):
            span["start"], span["end"] = times(by_id.get(span["parent"])) if span["parent"] else (None, None)
            if span["start"] is None:
                span["start"], span["end"] = built["spans"][0]["start"], built["spans"][0]["end"]
            span["attributes"][trace.TIME_FROM_ANCESTOR] = True
            filled += 1
    return filled


def read(target: str, wanted: str, user: dict, here: Path) -> dict:
    """trace.build に渡すデータ（run と会話の読みと段の集計）。作りは run の写しの中の pack から読み、写しが無ければ今の木から読む。
    どちらから読んだかを shape_from（"run-copy" か "tree"）に持つ（runread.copy の写しの置き場が本物の Archon と合うかの照らしの手がかり）"""
    texts = {}

    def keep(text: str) -> str:
        text = runread.mend(text)
        mark = hashlib.sha1(text.encode()).hexdigest()[:12]
        texts.setdefault(mark, text)
        return mark

    root = launcher.target_root(Path(target), here)
    home = launcher.run_home(user, root)
    db = home / isolate.DIRS["ARCHON_HOME"] / runread.DB_FILE
    if not db.is_file():
        raise Refused(f"run の家 {home} に Archon の DB が無い（この対象で run を回していない）")
    try:
        run_id = runread.pick(db, wanted)
    except LookupError as error:
        raise Refused(str(error)) from None
    run = runread.run(db, run_id)
    copy = Path(run["copy"]) / PACK["pack"] if run["copy"] else None
    pack = copy if copy is not None and copy.is_dir() else TREE
    run["sessions"] = session.collect(run, home / isolate.DIRS["CLAUDE_CONFIG_DIR"] / "projects", keep)
    data = {"shape": shape.read(pack, PACK["name_prefix"], ROOT / "docs" / "design"), "shape_from": "run-copy" if pack == copy else "tree",
            "run": run, "texts": texts}
    stages.attach(data)
    return data


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
