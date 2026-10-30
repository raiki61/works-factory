"""始めの記録（run directory の r1/start.json）の書き手と読む口（元 lib/startrec.py。docs/design/line.md の 1.5・1.6 の MOVE と
integration.md の 4.3-追加-6・4.3-9）。

始めの記録は line の start が run の頭に 1 度書く控えで、入口の入力の形（欄 input）と run の入力の控え（test_cmd・機能の切り替え…）を
持つ。書き手は start と固定材料の取り込み（src.fixture.adopt）、欄 policy を 1 度書き直すのは修正前の承認ノードの答え。block は
読まず、start が引いた配る値（src.deal）を port で受ける。読む口はここ 1 つで、KEEP の lib には読む口を残さない（4.3-追加-6。
lib の関数は値を引数で受ける）。名と置き場（src.files.START）は起動の殻と包みと bin/ が同じ所を読むので変えない。
前は置き場の名を 3 か所が、読む口を 6 か所が別々に持ち、続きの run で機能の切り替えが黙って変わった 8dfebca6 の元になった。

- REL: run directory の根からの置き場
- path(board_dir): run directory の根からの始めの記録のパス
- read(board_dir): 始めの記録の dict（無い・読めない・dict でなければ {}。読み手が欠けを欄ごとに扱う）
- load(file): 始めの記録のファイル file の dict。無い・読めなければ OSError・ValueError、dict でなければ ValueError
- write(board_dir, doc)・save(file, doc): 始めの記録を置く（書きは lib/jsonfile.py の write。4.3-9）
- shape(doc): 入口の入力の形（欄 input の dict）。無い前の版の控えは None
- diff_empty(doc)・requests(doc): 入口の差分が空か・依頼の行の数（入力の形が無ければ None）
- request_file(doc): 依頼のファイルのパス（欄 request_file、無ければ input.request_file、どちらも無ければ空の字）
- read_rev(doc)・diff_base(doc)・head_rev(doc)・diff_base_label(doc): 読む版（review_rev）・入口の差分の根（input.base.rev）・
  修正前の HEAD（base_rev）・BASE の出どころの文（input.base.label）
- words(shape): 起動の承認ノードの文と報告の冒頭 2 の入口の文
- cli_version(command): 始めの記録の版の控えに置く、PATH の上の命令の `--version` の 1 行（無い・落ちたら空の字）
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import jsonfile

from src import files

REL = files.START
P1_OFF_WORDS = "P1 の役は起こさない"   # 差分が空の run の入口の文の尻（入口の印が立ち、1 周目の P1 の役を起こさない）
SPEC_WORDS = "仕様の段あり"


def path(board_dir) -> pathlib.Path:
    """run directory の根 board_dir からの始めの記録のパス"""
    return pathlib.Path(board_dir) / REL


def read(board_dir) -> dict:
    """始めの記録（無い・読めない・dict でなければ空の dict）"""
    try:
        return load(path(board_dir))
    except (OSError, ValueError):
        return {}


def load(file) -> dict:
    """始めの記録のファイル file の dict（無い・読めなければ OSError・ValueError、dict でなければ ValueError）"""
    doc = json.loads(pathlib.Path(file).read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"始めの記録 {file} が JSON のオブジェクトでない")
    return doc


def write(board_dir, doc: dict) -> pathlib.Path:
    """始めの記録 doc を path(board_dir) に置く"""
    return save(path(board_dir), doc)


def save(file, doc: dict) -> pathlib.Path:
    """始めの記録 doc をファイル file に置く（一時のファイルから置き換える）"""
    return jsonfile.write(file, doc, indent=2, parents=True)


def shape(doc: dict):
    """入口の入力の形（欄 input）。dict でない・無ければ None"""
    got = doc.get("input") if isinstance(doc, dict) else None
    return got if isinstance(got, dict) else None


def request_file(doc) -> str:
    """依頼のファイルのパス（欄 request_file。無い・空なら入口の入力の形の input.request_file。どちらも無ければ空の字）"""
    for got in ((doc if isinstance(doc, dict) else {}).get("request_file"), (shape(doc) or {}).get("request_file")):
        if isinstance(got, str) and got:
            return got
    return ""


def diff_empty(doc: dict):
    """入口の差分が空か（input.diff.empty の真偽）。入力の形・欄が無ければ None"""
    s = shape(doc)
    got = (s.get("diff") or {}).get("empty") if s is not None and isinstance(s.get("diff"), dict) else None
    return got if isinstance(got, bool) else None


def requests(doc: dict):
    """依頼の行の数（input.requests）。入力の形・欄が無ければ None"""
    s = shape(doc)
    got = s.get("requests") if s is not None else None
    return got if isinstance(got, int) and not isinstance(got, bool) else None


def read_rev(doc: dict) -> str:
    """役の材料の読む版（欄 review_rev）。無い前の版の控えは base_rev、それも無ければ HEAD"""
    return _text(doc, "review_rev") or _text(doc, "base_rev") or "HEAD"


def diff_base(doc: dict) -> str:
    """役の材料の BASE（入口の差分の根 input.base.rev）。入力の形が無い前の版の控えは base_rev、それも無ければ空の字"""
    s = shape(doc)
    base = s.get("base") if s is not None else None
    got = base.get("rev") if isinstance(base, dict) else None
    return got if isinstance(got, str) and got else _text(doc, "base_rev")


def head_rev(doc: dict) -> str:
    """修正前の HEAD（欄 base_rev）。無ければ HEAD"""
    return _text(doc, "base_rev") or "HEAD"


def diff_base_label(doc: dict) -> str:
    """BASE の出どころの文（入口の変換が書いた input.base.label）。入力の形・欄が無ければ空の字"""
    s = shape(doc)
    base = s.get("base") if s is not None else None
    got = base.get("label") if isinstance(base, dict) else None
    return got if isinstance(got, str) else ""


def _text(doc: dict, key: str) -> str:
    got = doc.get(key) if isinstance(doc, dict) else None
    return got if isinstance(got, str) else ""


def words(s: dict) -> str:
    """入口の文（「入口: 」の後ろ）: 差分 <根の版の頭 12 字>..HEAD（N ファイル・<出どころ>）・依頼 N 件 ／
    差分なし（<出どころ>）・依頼 N 件——P1 の役は起こさない。仕様の段を挟む run は「・仕様の段あり」を足す"""
    base, diff = s["base"], s["diff"]
    if diff["empty"]:
        out = f"差分なし（{base['label']}）・依頼 {s['requests']} 件——{P1_OFF_WORDS}"
    else:
        out = f"差分 {base['rev'][:12]}..HEAD（{diff['files']} ファイル・{base['label']}）・依頼 {s['requests']} 件"
    return out + (f"・{SPEC_WORDS}" if s.get("spec") else "")


def cli_version(command: str) -> str:
    found = shutil.which(command)
    if found is None:
        return ""
    try:
        said = subprocess.run([found, "--version"], capture_output=True, text=True)
    except OSError:
        return ""
    return said.stdout.strip() if said.returncode == 0 else ""
