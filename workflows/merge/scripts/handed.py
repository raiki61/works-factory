# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""merge の返す節 merge。照らしの節の返りに、対象へどう渡したか（欄 deliver）と、落ちても先へ進めてよい節の宣言（欄 optional）を足す。

deliver は seal の時 null。apply・check の時 {act, pr, reason}:
- 出口の語が空: act は placed（差分を run の置き場に置いた）か none（置かなかった）。対象には何も書かない
- 出口の語 pr: act は pr（PR を作って読み戻した。pr が {number, url, is_draft}）・stopped（commit の節より前で止めた。push も PR の
  作成もしていない。reason が訳）・unconfirmed（PR を作る子の run が落ちたか、読み戻しが合わなかった。push や PR の作成は済んで
  いるかもしれないので、作ったとも作らなかったとも言わない。reason が訳）。commit の節が積んで進めた時（pr・unconfirmed）は、
  積んだ項目の commit の並び commits と、1 つに倒した・積まなかった訳 split も載せる（報告が読む）
PR を作る子の run が落ちると読み戻しの節が飛ばされ、子の記録が読めないので、そのことを訳にする（子の run は Archon の記録に残る）。
optional は PR を作る子の run の節（落ちても報告まで進めてよい）。
落ちない: 照らしの節の返りが読めない時も、ok: false と訳を返す。
欄 report は src/report.py が組む（docs/design/merge.md の 9 節）。

入力: mode（照らしの形。返りが読めない時の mode）・place（照らしの節の返り）・commit（commit の節の返りか null）・read（読み戻しの節の返りか null）・optional（宣言の JSON の字）
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / ".shared"), str(Path(__file__).resolve().parents[1])]
import ports  # noqa: E402

PLACE = ("mode", "ok", "hash", "diff", "protected_hits", "protected_count", "reason", "deliver")
COMMIT = ("go", "head", "branch", "commits", "split", "reason")
READ = ("ok", "number", "url", "is_draft", "reason")
RETURNS = PLACE[:-1]
MODES = ("seal", "apply", "check")
PR = "pr"


def as_items(got) -> list:
    return got if isinstance(got, list) else []


def as_text(got) -> str:
    return got if isinstance(got, str) else ""


def deliver(place, commit, read) -> dict | None:
    if place.get("mode") == "seal":
        return None
    if place.get("deliver") != PR:
        return {"act": "placed" if place.get("ok") is True else "none", "pr": None, "reason": ""}
    if place.get("ok") is not True:
        return stopped(f"差分を置かなかった: {place.get('reason') or '訳の記録が無い'}")
    if commit is None:
        return stopped("commit のノードの出力が無い")
    if commit.get("go") is not True:
        return stopped(commit.get("reason") or "commit のノードが進めなかった（訳の記録が無い）")
    pushed = f"枝 {commit.get('branch')} の commit {commit.get('head')} を積んだ後"
    stacked = {"commits": as_items(commit.get("commits")), "split": as_text(commit.get("split"))}
    if read is None:
        return {**unconfirmed(f"{pushed}、PR を作る子の run が落ちたか返らなかった（push と PR の作成が済んだかは子の run の記録で確かめる）"),
                **stacked}
    if read.get("ok") is not True:
        return {**unconfirmed(f"{pushed}、PR の読み戻しが合わなかった: {read.get('reason') or '訳の記録が無い'}"), **stacked}
    made = {"number": read.get("number"), "url": read.get("url"), "is_draft": read.get("is_draft") is True}
    return {"act": "pr", "pr": made, "reason": "", **stacked}


def stopped(reason: str) -> dict:
    return {"act": "stopped", "pr": None, "reason": reason}


def unconfirmed(reason: str) -> dict:
    return {"act": "unconfirmed", "pr": None, "reason": reason}


def handed() -> dict:
    from src import files, report
    place = ports.picked(os.environ.get("INPUTS_PLACE"), PLACE)
    optional = as_items(ports.parsed(os.environ.get("INPUTS_OPTIONAL")))
    if place is None:
        return {**broken("照らしのノードの出力が無い"), "optional": optional}
    commit = ports.picked(os.environ.get("INPUTS_COMMIT"), COMMIT)
    read = ports.picked(os.environ.get("INPUTS_READ"), READ)
    handed_over = deliver(place, commit, read)
    return {**{name: place.get(name) for name in RETURNS}, "deliver": handed_over, "optional": optional,
            "report": report.lines(dict(place), handed_over, ports.place() / files.SEALED)}


def broken(reason: str) -> dict:
    mode = os.environ.get("INPUTS_MODE", "")
    return {"mode": mode if mode in MODES else "seal", "ok": False, "hash": "", "diff": None, "protected_hits": None,
            "protected_count": None, "reason": reason, "deliver": None, "optional": [],
            "report": [f"差分の確定（{mode if mode in MODES else 'seal'}）: {reason}"]}


ports.run(handed, broken)
