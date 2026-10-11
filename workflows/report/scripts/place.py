"""run の置き場の中の報告の置き場と、そこのパスの指し札（facts.py・report_accept.py・collect.py が import する部品。節の script でない）。
三つの script が同じ置き場を読み書きして、AI の報告を受け渡す。lib/ を読めない時の最後の受け皿（訳だけのファイル）もここに置き、
lib/ に頼らない。"""
import os
from pathlib import Path

import boundary

OUT = "report"
UNWRITTEN = "report-unwritten.md"   # 報告を組めない時の訳だけのファイル（lib の runreport.FALLBACK_FILE と同じ名）


def out_dir() -> Path:
    """報告の置き場（run の置き場の OUT）"""
    return Path(os.environ["ARTIFACTS_DIR"]) / OUT


def rel_path(path) -> str:
    """置き場の中のパスを、run の置き場からの相対の字に"""
    return Path(path).relative_to(Path(os.environ["ARTIFACTS_DIR"])).as_posix()


def rel(path) -> dict | None:
    """置き場の中のパスを、置き場からの相対の指し札に（None は None）"""
    return None if path is None else boundary.pointer(rel_path(path))


def failed_line(what: str, error: BaseException) -> str:
    """思わぬ誤りの 1 行（返す節は stop_reason に report: を付けて載せる）"""
    return f"{what}を組めなかった（{type(error).__name__}: {' '.join(str(error).split())}）"


def unwritten(why: str) -> dict:
    """lib/ に頼らず訳だけの 1 ファイルを書いて指す（書けなくても札は返す。先の無い札は実行基盤が節の終わりに拒む）"""
    path = out_dir() / UNWRITTEN
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# 報告（run {os.environ.get('WORKFLOW_ID', '—')}）\n\n報告を組めなかった: {why}\n", encoding="utf-8")
    except OSError:
        pass
    return boundary.pointer(f"{OUT}/{UNWRITTEN}")
