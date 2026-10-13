"""run ごとの版の控え（始めの記録の欄 versions）。元 works/.shared/core/versions.py（名は元のまま。E18）。

run の記録は実行基盤の記録と run の置き場が正本で、版だけは誰も残さないので、線の start が始めの記録に 1 つ置き、run どうしを比べる時に
引けるようにする。分からない値は null にし、unknown[鍵] に理由を書く（推測で埋めない・黙って落とさない。元 versions.py 59-117 行）。
入口が拒む run でも、確かめの前に作る（元 works/blk-entry/scripts/start.py。拒みの訳を版と並べて引ける）。

- snapshot(root, env=os.environ, *, run_id="", settings=None, given=None) -> dict:
  {schema, run_id, at, works: {rev, dirty}, claude_code, borrowed, settings, python, platform, unknown, <given の鍵>}
  - works: works-factory の根 root の git の版（rev）と、追跡したファイルに commit していない変更が在るか（dirty）
  - claude_code: PATH の上の claude の `--version` の 1 行（startrec.cli_version）
  - borrowed: 起動の殻が run の隔離した設定の置き場（env の CLAUDE_CONFIG_DIR）に書いた借りた物の記録
  - settings: 呼び手が渡した run の設定の写し（線の start は切る機能・入れる機能を渡す）
  - given: 呼び手が引いた値 {鍵: (値か None, 引けない訳)}。値が None なら null と unknown[鍵] に訳（実行基盤の版のように
    lib が知らない物は呼び手が引く。lib/AGENTS.md の E3）
- pinned(path, key) -> (値か None, 訳): JSON のファイル path の字の欄 key（引けなければ None と訳）
- LINE_REV・line_rev(versions): メイングラフの版（works-factory の版 works.rev）の欄の道と、版の控えからそれを引く口（snapshot が
  書き、報告の来歴の行が読む。鍵の持ち主はここ 1 つ）
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import platform
import subprocess
import sys
from typing import Mapping

import startrec
import oneline

SCHEMA = 1
LINE_REV = ("works", "rev")   # 版の控えの中のメイングラフの版の欄の道（グラフは works-factory の木に在る）
TOOLSET_RECORD = ".works-toolset.json"   # 起動の殻 bin/_lib/toolset.py の RECORD と同じ名（lib は bin を読まない。試験が突き合わせる）


def line_rev(versions) -> str | None:
    """版の控え versions（snapshot の返り）のメイングラフの版（LINE_REV の道の字。無い・空なら None）"""
    got = versions
    for key in LINE_REV:
        got = got.get(key) if isinstance(got, dict) else None
    return got if isinstance(got, str) and got else None


def _git(root: pathlib.Path, *args):
    try:
        got = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8")
    except OSError as e:
        return None, f"git を起こせない（{type(e).__name__}）"
    if got.returncode != 0:
        return None, oneline.one_line(got.stderr or f"git {' '.join(args)} が {got.returncode} で終わった")
    return got.stdout.strip(), ""


def _works(root: pathlib.Path, unknown: dict) -> dict:
    rev, why = _git(root, "rev-parse", "HEAD")
    if rev is None:
        unknown["works.rev"] = f"works-factory の根 {root} の git の版を引けない（{why}）"
        return {"rev": None, "dirty": None}
    status, why = _git(root, "status", "--porcelain", "--untracked-files=no")
    if status is None:
        unknown["works.dirty"] = f"works-factory の根 {root} の git status を引けない（{why}）"
    return {"rev": rev, "dirty": None if status is None else bool(status)}


def pinned(path, key: str) -> tuple:
    """JSON のファイル path の字の欄 key を (値, "") で。引けなければ (None, 訳)"""
    path = pathlib.Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))[key]
    except (OSError, ValueError, KeyError, TypeError) as e:
        return None, f"{path} の {key} を引けない（{type(e).__name__}）"
    if not (isinstance(value, str) and value.strip()):
        return None, f"{path} の {key} が空か字でない"
    return value.strip(), ""


def _borrowed(env: Mapping[str, str], unknown: dict):
    cfg = (env.get("CLAUDE_CONFIG_DIR") or "").strip()
    if not cfg:
        unknown["borrowed"] = "env の CLAUDE_CONFIG_DIR が無い（起動の殻 bin/works-factory を通さずに起こした run）"
        return None
    path = pathlib.Path(cfg) / TOOLSET_RECORD
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        unknown["borrowed"] = f"借りた物の記録が無い（{path}）"
        return None
    except (OSError, ValueError) as e:
        unknown["borrowed"] = f"借りた物の記録が読めない（{path}: {type(e).__name__}）"
        return None
    if not isinstance(doc, dict):
        unknown["borrowed"] = f"借りた物の記録が JSON のオブジェクトでない（{path}）"
        return None
    return doc


def snapshot(root, env: Mapping[str, str] = os.environ, *, run_id: str = "", settings: dict | None = None,
             given: dict | None = None) -> dict:
    root = pathlib.Path(root)
    unknown: dict = {}
    claude = startrec.cli_version("claude") or None
    if claude is None:
        unknown["claude_code"] = "PATH の上の claude の --version を引けない（無いか、0 で終わらない）"
    out = {
        "schema": SCHEMA,
        "run_id": run_id,
        "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "works": _works(root, unknown),
        "claude_code": claude,
        "borrowed": _borrowed(env, unknown),
        "settings": dict(settings or {}),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    for key, (value, why) in (given or {}).items():
        out[key] = value
        if value is None:
            unknown[key] = why
    return {**out, "unknown": unknown}
