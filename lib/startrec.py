"""始めの記録（盤面の r1/start.json。考え start-record）の住処。層 L1（標準ライブラリだけ）。

始めの記録は、線の入口（入口のブロックの節 open。中身は core の entry.start）が run の入力を確かめて置く控えで、入口の入力の形
（欄 input）と run の入力の控え（test_cmd・adapter・機能の切り替え…）と start の結果（ci_role_go・pr_go・head_line）を持つ。
書き手は entry.start と固定材料の取り込み（fixture.adopt）。約束（JSON Schema）は入口のブロックの schemas/start.schema.json で、
欄 input は同じ置き場の input.schema.json と同じ形。置き場の名と読む口はここ 1 つで、ほかのモジュール・殻はここを引く
（前は置き場の名を 3 か所が、読む口を 6 か所が別々に持ち、続きの run で機能の切り替えが黙って変わった 8dfebca6 の元になった）。

- NAME・REL: 周の置き場の中の名（盤面の work(NAME) が今の周 r<N>/ に置く）と、盤面の根からの置き場（1 周目）
- path(board_dir): 盤面の根からの始めの記録のパス。置き場はこの 1 つで、線の start は run の置き場の根を盤面の根として
  ここに書き（write）、ブロックは指し札の先を自分の置き場の同じ所へ字のまま写す（adopt）。読み手は全部 read で読む
- read(board_dir): 始めの記録の dict（無い・読めない・dict でなければ {}。読み手が欠けを欄ごとに扱う）
- load(file): 始めの記録のファイル file（指し札の先）の dict。無い・読めなければ OSError・ValueError、dict でなければ ValueError
  （読めないことを訳にする読み手の口。read はこれを {} に落とす）
- write(board_dir, doc): 始めの記録を path(board_dir) に置いてパスを返す
- adopt(board_dir, src): 線の始めの記録のファイル src を path(board_dir) へ字のまま写し、その dict を返す（欄を足さず・既定で
  埋めない。写しが元と食い違って機能の切り替えが黙って変わらないように。JSON のオブジェクトでなければ ValueError）
- shape(doc): 入口の入力の形（欄 input の dict）。無い前の版の控え（入口の入力の形を持つ前の固定材料）は None
- diff_empty(doc): 入口の差分が空か（真偽）。入力の形が無ければ None
- requests(doc): 依頼の行の数。入力の形が無ければ None
- request_file(doc): 依頼のファイルのパス（欄 request_file、無ければ入口の入力の形の input.request_file、どちらも無ければ空の字）。
  始めの記録の依頼のファイルを読む式はここ 1 つ（盤面から読む conflict.request_file もここを引く）
- read_rev(doc)・diff_base(doc): 役の材料の「読む版」（欄 review_rev。役が根拠を取る版）と「BASE」（入口の差分の根 input.base.rev）。
  差分の run では 2 つが違う
- diff_base_label(doc): BASE の出どころの文（input.base.label）
- words(shape): 頭の行と報告の冒頭 2 の入口の文（例: 差分なし（HEAD）・依頼 2 件——P1 の役は起こさない）。出どころは
  base.label（入口の変換が書いた文）で、入口の種類で分岐しない
- cli_version(command): 始めの記録の版の控えに置く、PATH の上の命令の `--version` の 1 行（無い・落ちたら空の字）
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

NAME = "start.json"
REL = f"r1/{NAME}"
P1_OFF_WORDS = "P1 の役は起こさない"   # 差分が空の run の入口の文の尻（入口の印が立ち、1 周目の P1 の役を起こさない）
SPEC_WORDS = "仕様の段あり"


def path(board_dir) -> pathlib.Path:
    """盤面の根 board_dir からの始めの記録のパス"""
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
    """始めの記録 doc を path(board_dir) に置く（一時のファイルから置き換える）"""
    p = path(board_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(p)
    return p


def adopt(board_dir, src) -> dict:
    """線の始めの記録のファイル src を path(board_dir) へ字のまま写し、その dict を返す。src と写しが同じなら写さない"""
    src, p = pathlib.Path(src), path(board_dir)
    data = src.read_bytes()
    doc = json.loads(data.decode("utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"始めの記録 {src} が JSON のオブジェクトでない")
    if src.resolve() != p.resolve():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return doc


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
