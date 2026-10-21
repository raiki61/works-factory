"""仕様駆動の道の表（docs/design/spec-driven.md の 2.3）の読みと照らしと、会話で回す部品に渡す入力の組み立て（2.5・2.6・6.7）。

表を読むのは 2 か所: block works-factory-spec-driven の入口の script と、起動の殻が表を読む script（bin/_lib/spec-inputs.py）。
どちらも PyYAML を宣言した uv の script で、このモジュールを import する（外のパッケージは使ってよい。持ち主の決め outside-packages-ok）。
run の記録を読んで照らす所（2.6 の 2 の a〜e）は殻の側に在り、ここは表・設計書・組んだ入力の値だけを扱う。

- PARTS: 仕様を固める会話の中で必ず回す 5 つの部品の名（表の reviews の part）
- read(root, table) -> Spec: 表と設計書を読む（読めない物は Spec.unread に訳を置き、落ちない）
- problems(spec) -> [訳]: 入口の確かめの 1〜4（2.3。どれも yes/no で、1 件 1 文）
- heading_hits(md) -> [名]: 設計書の見出しのうち表の欄の名に当たる物（2.6 の 1）
- design_rows(spec)・acceptance_rows(spec): 依頼の行（頭の行と節の行・受け入れの行。2.5）
- proposal_text(spec): 設計書の本文と、表から reviews を除いた字（計画の審査の方針の文と、計画の部品の固めた仕様）・
  proposal_name(text): その字を置くファイルの名（中身の sha256 を名に持つ）
- part_inputs(spec) -> {部品: {入力: 値}}: 部品ごとに組む入力（計画の審査の方針の文は proposal_name のファイルで渡し、名の sha256 で照らす）
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
from typing import NamedTuple

import yaml

import oneline

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE / "graphloops") not in sys.path:
    sys.path.insert(0, str(_HERE / "graphloops"))   # 写しの engine（entry と同じ足し方）
from engine.schema import validate_schema  # noqa: E402

FIELDS = ("purpose", "acceptance", "test_cmd", "out_of_scope")   # 表の 4 つ（持ち主の決め spec-driven-shape）
CARRY = ("design", "reviews")                                     # run を表 1 本で回すための運ぶ欄
PLAN_REVIEW, INDEPENDENT_DESIGN, PREMISES, PRIOR_DECISIONS, WORLD = (
    "works-factory-plan-review", "works-factory-independent-design", "works-factory-premises", "works-factory-prior-decisions",
    "works-factory-world")
PARTS = (PLAN_REVIEW, INDEPENDENT_DESIGN, PREMISES, PRIOR_DECISIONS, WORLD)
HANDLINGS = ("accepted",)
# 設計書の見出しに置かない名（2.6 の 1）。表の欄の名と、その日本語の名・英語の名
HEADING_NAMES = (*FIELDS, "目的", "受け入れの条件", "受け入れ条件", "試験のコマンド", "テストのコマンド", "触らない物", "触らないもの",
                 "acceptance criteria", "test command", "out of scope", "non-goals")
TDD_HEADING = "tdd で直す所"   # 設計書の「TDD で直す所」の見出し（見出しの字の正規形）
_TEXT = {"type": "string", "minLength": 1}
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["design", "purpose", "acceptance", "reviews"],
    "properties": {
        "design": _TEXT,
        "purpose": _TEXT,
        "acceptance": {"type": "array", "minItems": 1, "items": {
            "type": "object", "additionalProperties": False, "required": ["key", "when", "then"],
            "properties": {"key": _TEXT, "given": {"type": "string"}, "when": _TEXT, "then": _TEXT}}},
        "test_cmd": {"type": "string"},
        "out_of_scope": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["glob", "why"], "properties": {"glob": _TEXT, "why": _TEXT}}},
        "reviews": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["part", "run", "findings"],
            "properties": {"part": _TEXT, "run": _TEXT, "findings": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["key", "text", "handling", "owner_words"],
                "properties": {"key": _TEXT, "text": _TEXT, "handling": {"type": "string", "enum": list(HANDLINGS)},
                               "owner_words": _TEXT}}}}}},
    },
}
_FENCE = re.compile(r"^ {0,3}(```|~~~)")
_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
_SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_NUMBER = re.compile(r"^\d+(?:\.\d+)*\.?\s+")


class Spec(NamedTuple):
    """読んだ表と設計書。table は表の中身（読めなければ None）、design は設計書の本文（読めなければ None）、unread は読めない訳"""
    root: pathlib.Path
    table_rel: str
    design_rel: str
    table: dict | None
    design: str | None
    unread: tuple


def _rel(root: pathlib.Path, path) -> str:
    """対象の根からの相対の字（根の外のパスは渡された字のまま）"""
    path = pathlib.Path(path)
    full = path if path.is_absolute() else root / path
    try:
        return full.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def read(root, table) -> Spec:
    """対象の根 root と表のパス table（相対なら根から）から表と設計書を読む。落ちない"""
    root = pathlib.Path(root)
    table_rel = _rel(root, table)
    try:
        doc = yaml.safe_load((root / table_rel).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        return Spec(root, table_rel, "", None, None, (f"表 {table_rel} を読めない（{error}）",))
    except yaml.YAMLError as error:
        return Spec(root, table_rel, "", None, None, (f"表 {table_rel} を YAML として読めない（{oneline.one_line(error)}）",))
    if not isinstance(doc, dict):
        return Spec(root, table_rel, "", None, None, (f"表 {table_rel} が欄の並び（YAML の mapping）でない",))
    design = doc.get("design")
    if not isinstance(design, str) or not design.strip():
        return Spec(root, table_rel, "", doc, None, ())
    design_rel = _rel(root, design.strip())
    try:
        text = (root / design_rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return Spec(root, table_rel, design_rel, doc, None, (f"設計書 {design_rel} が対象に無いか読めない（{type(error).__name__}）",))
    return Spec(root, table_rel, design_rel, doc, text, ())


# ---------------------------------------------------------------- 入口の確かめの 1〜4
def problems(spec: Spec) -> list:
    if spec.table is None:
        return list(spec.unread)
    out = [f"表の形: {e}" for e in validate_schema(spec.table, SCHEMA)]
    keys = [a.get("key") for a in spec.table.get("acceptance") or [] if isinstance(a, dict)]
    out += [f"表の形: acceptance の key {k} が 2 度在る" for k in sorted({k for k in keys if keys.count(k) > 1}, key=str)]
    out += list(spec.unread)
    if spec.design is not None:
        out += [f"設計書 {spec.design_rel} の見出しに表の欄の名 {name} が在る（表の 4 つは設計書に書かない）"
                for name in heading_hits(spec.design)]
    parts = [r.get("part") for r in spec.table.get("reviews") or [] if isinstance(r, dict)]
    for part in PARTS:
        n = parts.count(part)
        if n != 1:
            out.append(f"reviews に部品 {part} の記録が {n} 件（必ず回す 5 つの部品が 1 件ずつ要る）")
    return out


# ---------------------------------------------------------------- 設計書の見出しと節
def _headings(md: str) -> list:
    """[(行の番号, 見出しの深さ, 見出しの字)]（コードの囲みの中の行は見ない）"""
    out, fence, lines = [], None, md.splitlines()
    for i, line in enumerate(lines):
        got = _FENCE.match(line)
        if fence:
            if got and got.group(1) == fence:
                fence = None
            continue
        if got:
            fence = got.group(1)
            continue
        atx = _ATX.match(line)
        if atx:
            out.append((i, len(atx.group(1)), re.sub(r"[ \t]+#+$", "", atx.group(2) or "").strip()))
        elif i > 0 and _SETEXT.match(line) and lines[i - 1].strip() and not _ATX.match(lines[i - 1]) and not _FENCE.match(lines[i - 1]):
            out.append((i - 1, 1 if line.strip()[0] == "=" else 2, lines[i - 1].strip()))
    return out


def _bare(heading: str) -> str:
    """見出しの字の正規形（頭の節の番号・` を外し、英字を小文字にする）"""
    return _NUMBER.sub("", heading.replace("`", "").strip()).strip().lower()


def heading_hits(md: str) -> list:
    return [_bare(h) for _, _, h in _headings(md) if _bare(h) in HEADING_NAMES]


def sections(md: str) -> list:
    """[(見出しの字, 本文)]: 2 段目の見出し（ATX の ## と Setext の ---）ごとの節（次の 2 段目以上の見出しまで）"""
    heads = _headings(md)
    lines = md.splitlines()
    out = []
    for n, (i, depth, text) in enumerate(heads):
        if depth != 2:
            continue
        setext = not _ATX.match(lines[i])
        end = next((j for j, d, _ in heads[n + 1:] if d <= 2), len(lines))
        out.append((text, "\n".join(lines[i + (2 if setext else 1):end]).strip()))
    return out


def has_tdd(md: str) -> bool:
    """設計書に「TDD で直す所」の節が在り、本文が空でない"""
    return any(_bare(h) == TDD_HEADING and body for h, body in sections(md))


# ---------------------------------------------------------------- 部品に渡す入力（2.5）
def design_rows(spec: Spec) -> list:
    """頭の行（設計書の頭の「何の話か」と「決めたこと」の行。無ければ最初の 2 段目の見出しの前の本文）と、節の行"""
    heads = _headings(spec.design)
    lines = spec.design.splitlines()
    first = next((i for i, d, _ in heads if d == 2), len(lines))
    pre = [ln for ln in lines[:first] if not _ATX.match(ln)]
    picked = [ln.strip() for ln in pre if re.match(r"^\s*[-*]\s*(何の話か|決めたこと)\s*[:：]", ln)]
    head = {"where": spec.design_rel, "text": "\n".join(picked) or "\n".join(pre).strip()}
    return [head, *({"where": f"{spec.design_rel}#{h}", "text": body} for h, body in sections(spec.design))]


def acceptance_rows(spec: Spec) -> list:
    out = []
    for a in spec.table.get("acceptance") or []:
        given = str(a.get("given") or "").strip()
        text = (f"前提: {given}。" if given else "") + f"きっかけ: {str(a['when']).strip()}。振る舞い: {str(a['then']).strip()}。"
        out.append({"where": f"{spec.table_rel}#{a['key']}", "text": text})
    return out


def table_text(spec: Spec) -> str:
    """表から reviews を除いた字（欄の並びは表のまま）"""
    bare = {k: v for k, v in spec.table.items() if k != "reviews"}
    return yaml.safe_dump(bare, allow_unicode=True, sort_keys=False, width=1 << 20).rstrip()


def proposal_text(spec: Spec) -> str:
    """前後の空白を除いた字（計画の審査の入口は方針の文の前後の空白を除いてから sha256 を取るので、同じ字にする）"""
    return f"{spec.design.strip()}\n\n---\n機械が確かめる表（{spec.table_rel}）:\n\n{table_text(spec)}"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def proposal_name(text: str) -> str:
    """方針の文を置くファイルの名（中身の sha256 を名に持つ。計画の審査の run の記録に残る proposal_file の名で、審査した版を照らす）"""
    return f"spec-proposal-{sha256(text)}.md"


def part_inputs(spec: Spec) -> dict:
    """部品ごとに組む入力（値は JSON の値。--input に渡す時は字にする〔input_args〕）。計画の審査の方針の文は proposal_file で渡すので
    ここに入れず、proposal_name のファイルの名で照らす"""
    purpose = str(spec.table["purpose"]).strip()
    rows = design_rows(spec)
    return {
        PLAN_REVIEW: {"purpose": purpose},
        INDEPENDENT_DESIGN: {"purpose": purpose},
        PREMISES: {"request": rows},
        PRIOR_DECISIONS: {"request": rows, "entry": f"仕様を固める会話（{spec.design_rel} と {spec.table_rel}）"},
        WORLD: {"request": [rows[0], *acceptance_rows(spec)], "purpose": purpose},
    }


def input_text(value) -> str:
    """--input に渡す字（字はそのまま、ほかは JSON）"""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
