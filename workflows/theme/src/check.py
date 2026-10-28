"""設計の案の受け付けの照らし（docs/design/theme.md の 4.4 と 6.2）。どれも yes/no で、照らしに外れた所ごとに拒否の行を 1 つ返す。
拒否の行は返答の中身（欄の id・パス・行）で変わる文なので、人に見せる日本語のままここで組む（docs/design/README.md の 5.3）。

照らしの順:
1. 形（shared:theme-design.schema.json）。外れたら後の照らしをしない
2. 名指しの <パス>:<行> が固めた版に在る（current の where・decided の by・checks の rule は名指しを 1 つ以上持つ。parts の where・
   checks の where は名指しが在ればそれを照らす）
3. asks の各行: pick が案の id のどれか（案が 2 つ以上・cost と gain が空でないのは形が照らす）
4. decided の各行の by（2 の名指し）
5. reuse の各行: part が parts の id・existing が current の id（空なら why_not。形が空でない字を求める）
6. 作り変えの照らし（6.2）: changes の op rework の各パスが起点の木に在り、inventory がそのファイルの空でない行を全部覆う・範囲が
   ファイルの中で重ならない・drop は why と narrows の名指しを持つ・move と merge の dest が parts か changes の id
7. block_answers が前の往復の答えの要る穴の全部の key に答える（lib/converge.py の answer_gaps）
8. answers_used が渡された人の答えの全部の id を持ち、行ごとに applied か declined_why を持つ
9. premises の by owner の各行の from が、渡された人の答えの id か、テーマの md の空でない行を指す
ほかに、欄ごとの id が重ならないこと・changes の parts が parts の id を指すことを照らす（名指しの先を 1 つに決めるため）。
"""
from __future__ import annotations

import pathlib
import re
import subprocess

import ports

import converge   # lib/。answer_gaps
import design     # lib/。anchors・anchor_misses

from src import files

THEME_REF = re.compile(r"^theme:(\d+)(?:-(\d+))?$")
PATH_OF = re.compile(r"^(\S+?)(?::\d+(?:-\d+)?)?$")
ID_LISTS = ("premises", "current", "parts", "asks", "decided", "changes")


# ---------------------------------------------------------------- 起点の木とテーマの md
def base_text(repo, base: str, path: str) -> str | None:
    """起点の版 base（空は HEAD）のファイル path の字。無ければ None"""
    got = subprocess.run(["git", "-C", str(repo), "show", f"{base or 'HEAD'}:{path}"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return got.stdout if got.returncode == 0 else None


def _span(lines: str) -> tuple[int, int]:
    a, b = lines.split("-")
    return int(a), int(b)


# ---------------------------------------------------------------- 照らしの部分
def _id_gaps(doc: dict) -> list[str]:
    out = []
    for name in ID_LISTS:
        ids = [row["id"] for row in doc[name]]
        out += [f"{name} の id {i} が 2 行に在る（id は 1 行に 1 つ）" for i in sorted({i for i in ids if ids.count(i) > 1})]
    for q in doc["asks"]:
        ids = [o["id"] for o in q["options"]]
        out += [f"asks {q['id']} の案の id {i} が 2 つ在る" for i in sorted({i for i in ids if ids.count(i) > 1})]
    return out


def _anchor_gaps(doc: dict, repo) -> list[str]:
    """名指しの <パス>:<行> が固めた版に在るか（must は名指しを 1 つ以上要る欄）"""
    out = []
    fields = [("current", "where", True), ("decided", "by", True), ("checks", "rule", True), ("parts", "where", False), ("checks", "where", False)]
    for name, key, must in fields:
        for i, row in enumerate(doc[name], 1):
            text = row[key]
            label = f"{name} の {row.get('id') or f'{i} 行目'} の {key}"
            if must and not design.anchors(text):
                out.append(f"{label} に <パス>:<行> の名指しが無い（{text}）")
            out += [f"{label} の名指し {miss} が固めた版に当たらない" for miss in design.anchor_misses(text, repo)]
    return out


def _ask_gaps(doc: dict) -> list[str]:
    return [f"asks {q['id']} の pick {q['pick']} が案の id（{', '.join(o['id'] for o in q['options'])}）に無い"
            for q in doc["asks"] if q["pick"] not in {o["id"] for o in q["options"]}]


def _ref_gaps(doc: dict) -> list[str]:
    parts = {p["id"] for p in doc["parts"]}
    current = {n["id"] for n in doc["current"]}
    out = []
    for r in doc["reuse"]:
        if r["part"] not in parts:
            out.append(f"reuse の part {r['part']} が parts の id に無い")
        out += [f"reuse の {r['part']} の existing {n} が current の id に無い" for n in r["existing"] if n not in current]
    for c in doc["changes"]:
        out += [f"changes {c['id']} の parts {d} が parts の id に無い" for d in c["parts"] if d not in parts]
    return out


def rework_gaps(doc: dict, repo, base: str) -> list[str]:
    """作り変えの照らし（docs/design/theme.md の 6.2）。行の分け方は書き手が決め、ここは覆いだけを照らす"""
    out = []
    dests = {p["id"] for p in doc["parts"]} | {c["id"] for c in doc["changes"]}
    narrows = [n["what"] for n in doc["narrows"]]
    rows_of: dict[str, list] = {}
    for row in doc["inventory"]:
        rows_of.setdefault(row["path"], []).append(row)
        where = f"{row['path']}:{row['lines']}"
        if row["to"] == "drop":
            if not row["why"].strip():
                out.append(f"inventory {where} は drop なのに why が空")
            if not any(where in what for what in narrows):
                out.append(f"inventory {where} は drop なのに、narrows に {where} を名指す行が無い")
        if row["to"] in ("move", "merge") and row["dest"] not in dests:
            out.append(f"inventory {where} は {row['to']} なのに、dest {row['dest']!r} が parts か changes の id に無い")
    for c in doc["changes"]:
        if c["op"] != "rework":
            continue
        named = PATH_OF.match(c["where"].strip())
        if not named:
            out.append(f"changes {c['id']} は rework なのに、where {c['where']!r} がファイルのパス（<パス> か <パス>:<行>）でない")
            continue
        path = named.group(1)
        text = base_text(repo, base, path)
        if text is None:
            out.append(f"changes {c['id']} は rework なのに、{path} が起点の木（{base or 'HEAD'}）に無い")
            continue
        lines = text.splitlines()
        rows = rows_of.get(path, [])
        if not rows:
            out.append(f"changes {c['id']} は rework なのに、inventory に {path} の行が無い（空でない行を全部、行の範囲で覆う）")
            continue
        spans = []
        for row in rows:
            a, b = _span(row["lines"])
            if not 1 <= a <= b <= len(lines):
                out.append(f"inventory {path}:{row['lines']} がファイルの行の外（ファイルは {len(lines)} 行）")
                continue
            hit = [s for s in spans if not (b < s[0] or s[1] < a)]
            out += [f"inventory {path}:{row['lines']} が {path}:{s[0]}-{s[1]} と重なる" for s in hit]
            spans.append((a, b))
        covered = {n for a, b in spans for n in range(a, b + 1)}
        missed = [n for n, line in enumerate(lines, 1) if line.strip() and n not in covered]
        if missed:
            out.append(f"inventory が {path} の空でない行 {_ranges(missed)} を覆っていない（覆いの抜け）")
    return out


def _ranges(nums: list[int]) -> str:
    out, start, prev = [], nums[0], nums[0]
    for n in nums[1:] + [None]:
        if n is not None and n == prev + 1:
            prev = n
            continue
        out.append(f"{start}" if start == prev else f"{start}-{prev}")
        if n is not None:
            start = prev = n
    return "・".join(out)


def _answer_gaps(doc: dict, answer_ids: list[str]) -> list[str]:
    used = [u["answer"] for u in doc["answers_used"]]
    out = [f"answers_used に人の答え {h} の行が無い（渡した答えは全部、使い道を書く）" for h in answer_ids if h not in used]
    out += [f"answers_used の {h} は渡した人の答えに無い" for h in used if h not in answer_ids]
    out += [f"answers_used の {u['answer']} に applied も declined_why も無い（入れた欄の id か、入れなかった訳を書く）"
            for u in doc["answers_used"] if not u.get("applied") and not (u.get("declined_why") or "").strip()]
    return out


def _premise_gaps(doc: dict, answer_ids: list[str], theme_lines: list[str]) -> list[str]:
    out = []
    for p in doc["premises"]:
        if p["by"] != "owner":
            continue
        src = p["from"].strip()
        if src in answer_ids:
            continue
        m = THEME_REF.match(src)
        if m:
            a, b = int(m.group(1)), int(m.group(2) or m.group(1))
            if 1 <= a <= b <= len(theme_lines) and any(line.strip() for line in theme_lines[a - 1:b]):
                continue
            out.append(f"premises {p['id']} の from {src} がテーマの md の空でない行に当たらない（テーマの md は {len(theme_lines)} 行）")
            continue
        out.append(f"premises {p['id']} は by owner なのに、from {src!r} が人の答えの id（H<n>）でもテーマの md の行（theme:<行>）でもない")
    return out


# ---------------------------------------------------------------- 全体
def gaps(doc, *, repo, base: str, theme_lines: list[str], answer_ids: list[str], prior: dict | None) -> list[str]:
    """設計の案 doc の拒否の行（空なら通る）"""
    shape = ports.shape_errors(doc, "shared:theme-design.schema.json")
    if shape:
        return [f"形 {files.DESIGN_SCHEMA} に合わない: {e}" for e in shape]
    out = _id_gaps(doc) + _anchor_gaps(doc, repo) + _ask_gaps(doc) + _ref_gaps(doc) + rework_gaps(doc, repo, base)
    if prior is not None:
        out += converge.answer_gaps(prior, doc["block_answers"])
    return out + _answer_gaps(doc, answer_ids) + _premise_gaps(doc, answer_ids, theme_lines)
