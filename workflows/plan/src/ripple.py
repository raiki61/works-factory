"""波及の一覧（今の lib/ripple.py の写し。docs/design/README.md の 9.2 の MOVE。docs/design/plan.md の 1.5）。

修正案の項目が変える名（単位の key の `+` の後から `:` までの ASCII の名と、項目の files の change=add の symbol の名の ASCII の語のうち、対象に在る物）を
`git grep -n -w` で引き、当たりを本体（呼び出し元・文書）と試験に分ける。Python の試験は当たりを含む試験の関数の id
（`path::Class[::内の Class…]::test_x`。planmarks.test_defs）まで引き、試験でない関数・ほかの言語はファイルと行（`path:line`）。当たりを項目の allowed_paths
（glob）・tests と rewrite_tests の id とそのファイルに照らし、覆っていない当たりに項目ごとの id（h1・h2…）を振って名指す。
試験の id・パス・試験の名（test_・Test で始まる）は変える名に数えず、試験のモジュール（impact.is_test が module を返すファイル）の行だけに出る名は
その行のファイルの中の当たりを捨て（別の試験が import して使う時だけ名指す）、呼び出し元でない文書と生成物（NON_CODE_DIRS・
NON_CODE_FILES）の当たりは捨てる（run 68f35d6b: 足す試験の id の断片 works・tests・test_report・HeadCase と、設計書の行が
覆っていない当たりの大半で、下請けが全部 no_effect と答えていた）。
当たりのファイルが多い名（COMMON_FILES を超える）は数だけを載せ、覆っていない当たりに入れない（下請けが判断する。持ち主の決定
2026-10-06）。2 つ以上の項目の allowed_paths・当たりに出たファイルを「項目どうしの重なり」として並べる（相乗りの審査が読む）。
項目が消す名（files の change=remove の symbol の名と、消えるパス——op=delete の行の path と op=rename の行の元のパス from）の残る名指しも同じに引き、kind removed（本体）・removed_test（試験）で
名指す（消した後に壊れる参照。変える名の当たり code・test とは別の行で、同じ行に両方当たれば両方残る）。消す名に限り設計書の置き場
docs/plans の当たりも数える（今の設計書に残る古さ。non_code の keep_plans）。CHANGELOG・docs-archive・skip_dirs は捨てたまま。

- names(unit_keys, files)・build(repo, fields, common_files=, skip_dirs=)・for_units(repo, unit_keys, skip_dirs=)・uncovered(doc, n):
  一覧を作る・読む（fields は盤面の plan-fields.json の項目の欄の並び。planmarks.split の形）
- units_rows(doc)・rows(doc)・item_text(doc, n): 指示書に入れる材料の行（英語の札。見出し・頼み・作れなかった時の文は
  prompts/plan-writer.md に移した。元の HEAD・UNITS_HEAD・SCOPE_ASK・ERROR_NOTE は持たない）

例外で止めない: git が無い・リポジトリでない時は一覧の error に理由を書き、項目の行を持たない（受け付けは答えを求めない）。
"""
from __future__ import annotations

import ast
import pathlib
import posixpath
import re
import subprocess

import ports  # noqa: F401  （lib/ を sys.path に足す）

import impact      # lib/。テストのファイルの名の慣習 is_test の正本
import planmarks   # lib/
import planrange   # lib/。項目の範囲に入るかの決まり inside の 1 か所

# 当たりのファイルがこの数を超える名は数だけ（run 195g の一番広い本物の波及は edge.py の入力の組を共有する 17 の節と試験で、
# それは全部並べる。境は段 1 の run の当たりの数を見て直す。設計の 7 の 3）
COMMON_FILES = 25
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_TEST_NAME = re.compile(r"^(test_|Test[A-Z_])")   # 試験の関数・クラスの名（足す試験の名で、呼び出し元を引く名でない）
# 呼び出し元でない文書と生成物（当たりに数えない小さな一覧）: 設計書・古い文書の置き場（段の並びがパスのどこに在っても）と、
# 実行基盤の pack の写し（呼び手が skip_dirs で渡す。dogfood が作り直す物）。README など振る舞いを書く文書は契約のずれの元なので数える
NON_CODE_DIRS = (("docs", "plans"), ("docs-archive",))   # パスの段の並び（パスのどこに在っても）
NON_CODE_FILES = ("CHANGELOG.md", "HANDOFF.md")
# 項目ごとに繰り返す札（英語。docs/design/plan.md の 2.3 の終わりの波及の行）
COMMON_NOTE = "a name with hits in many files (only the count; the callers are not all listed)"
REMOVED_MARK = " (a hit of a name to remove)"
REMOVED_KINDS = {"code": "removed", "test": "removed_test"}   # 変える名の当たりの kind → 消す名の当たりの kind


def _changed(unit_keys, files) -> dict[str, frozenset]:
    """変える名の候補 → 当たりを捨てるファイル。名は単位の key の `+` の後から `:` までの ASCII の名と、files の change=add の symbol の名の
    ASCII の語。:: を含む名・試験の名（_TEST_NAME）・3 字未満は数えない。試験のモジュール（行の path を impact.is_test が module と読む。
    名の慣習の正本は impact.is_test の 1 か所）の行だけに出る名（助け手・定数）は、その行の path の中の当たりを捨てる（別のファイルが
    使う時だけ呼び手を引く）。ほかの行・単位の key にも出る名は、どこの当たりも捨てない。名と path は別の欄なので、パスか名かを字から推さない"""
    own: dict[str, set[str] | None] = {}   # None: 試験のモジュールの外にも出た名

    def put(found, path=None):
        for n in found:
            if len(n) < 3 or _TEST_NAME.match(n):
                continue
            if path is None or own.get(n, set()) is None:
                own[n] = None
            else:
                own.setdefault(n, set()).add(path)

    for k in unit_keys or []:
        if isinstance(k, str) and "+" in k:
            put(_NAME.findall(k.split("+", 1)[1].split(":", 1)[0]))
    for row in planmarks.file_rows({"files": files}):
        path = row.get("path")
        in_test_module = isinstance(path, str) and impact.is_test(path) == "module"
        for sym in planmarks.symbol_rows(row):
            name = sym.get("name")
            if sym.get("change") == "add" and isinstance(name, str) and "::" not in name:
                put(_NAME.findall(name), path if in_test_module else None)
    return {n: frozenset(paths or ()) for n, paths in own.items()}


def _removed_names(files) -> list[str]:
    """消す名の候補: files の change=remove の symbol の探す語（planmarks.search_word）と、消えるパス（op=delete の行の path と op=rename の
    行の元のパス from。planmarks.removed_paths）の字のままと、.py ならモジュールの名・.py でなければ最後の段のファイルの名（名が
    パスか識別子かは行の欄で決まっているので、字から推さない）"""
    out = [planmarks.search_word(name) or "" for _, name in planmarks.file_symbols({"files": files}, "remove")]
    for path in planmarks.removed_paths({"files": files}):
        out += [path, planmarks.declared_name(path) if path.endswith(".py") else posixpath.basename(path.rstrip("/"))]
    return [n for n in out if len(n) >= 3 and not _TEST_NAME.match(n)]


def names(unit_keys, files) -> list[str]:
    """変える名・消す名の候補（現れた順・重なりは 1 つ）: 単位の key の `+` の後から `:` までの ASCII の名と、files の change=add の symbol の
    名の ASCII の語（_changed）と、消す名（_removed_names）。試験の名（_TEST_NAME）は数えない"""
    return list(dict.fromkeys([*_changed(unit_keys, files), *_removed_names(files)]))


def non_code(path: str, *, skip_dirs, keep_plans: bool = False) -> bool:
    """呼び出し元でない文書・生成物のパスか（NON_CODE_DIRS と skip_dirs の並びがパスのどこかに在る・名が NON_CODE_FILES）。keep_plans
    なら設計書の置き場 ('docs', 'plans') の並びは捨てない（消す名の残りは今の設計書にも在る）"""
    parts = pathlib.PurePosixPath(path).parts
    dirs = parts[:-1]
    skip = tuple(seq for seq in (*NON_CODE_DIRS, *skip_dirs) if not (keep_plans and seq == ("docs", "plans")))
    return (any(dirs[i:i + len(seq)] == seq for seq in skip for i in range(len(dirs)))
            or (parts[-1] if parts else "") in NON_CODE_FILES)


def _git_grep(repo: pathlib.Path, name: str, skip_dirs, keep_plans: bool = False) -> list[tuple[str, int]]:
    p = subprocess.run(["git", "-C", str(repo), "grep", "-n", "-w", "-I", "-F", "-e", name],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    if p.returncode not in (0, 1):
        raise OSError(p.stderr.strip() or f"git grep が {p.returncode} で落ちた")
    out = []
    for line in p.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) >= 2 and parts[1].isdigit() and not non_code(parts[0], skip_dirs=skip_dirs, keep_plans=keep_plans):
            out.append((parts[0], int(parts[1])))
    return out


def is_test(path: str) -> bool:
    """試験の側のファイルか（テストのモジュールか、テストのフォルダの下の支え。名の慣習は impact.is_test の 1 か所）"""
    return impact.is_test(path) is not None


def _test_id(repo: pathlib.Path, path: str, line: int, cache: dict) -> str:
    """当たりの行を含む試験の関数の id（planmarks.test_defs の形。入れ子のクラスは外から順に）。引けなければ path:line"""
    if path.endswith(".py"):
        if path not in cache:
            try:
                cache[path] = ast.parse((repo / path).read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
                cache[path] = None
        if cache[path] is not None:
            for tid, fn in planmarks.test_defs(cache[path], path):
                if fn.lineno <= line <= (fn.end_lineno or fn.lineno):
                    return tid
    return f"{path}:{line}"


def _name_row(repo: pathlib.Path, name: str, common_files: int, cache: dict, skip_dirs,
              keep_plans: bool = False, own_files: frozenset = frozenset()) -> dict | None:
    hits = [h for h in _git_grep(repo, name, skip_dirs, keep_plans) if h[0] not in own_files]
    if not hits:
        return None
    files = sorted({p for p, _ in hits})
    # 多い名かは設計書の置き場の当たりを除いて数える（消す名で数え入れた計画書が、本体の残りの列挙を数だけに落とさない）
    common = len([p for p in files if not non_code(p, skip_dirs=skip_dirs)]) > common_files
    row = {"name": name, "files": len(files), "common": common, "code": [], "tests": []}
    if row["common"]:
        return row
    for path, line in hits:
        if is_test(path):
            tid = _test_id(repo, path, line, cache)
            if tid not in row["tests"]:
                row["tests"].append(tid)
        else:
            row["code"].append(f"{path}:{line}")
    return row


def _path_of(at: str) -> str:
    return at.split("::", 1)[0] if "::" in at else at.rsplit(":", 1)[0]


def _covered(f: dict, kind: str, at: str) -> bool:
    ids = {r.get("id") for key in ("tests", "rewrite_tests") for r in f.get(key) or [] if isinstance(r, dict)}
    if kind in ("test", REMOVED_KINDS["test"]) and "::" in at:
        return at in ids
    return planrange.inside(_path_of(at), f)


def _item(repo: pathlib.Path, n: int, f: dict, common_files: int, cache: dict, skip_dirs) -> dict:
    changed = _changed(f.get("unit_keys"), f.get("files"))
    removed = set(_removed_names(f.get("files")))
    rows = [r for r in (_name_row(repo, nm, common_files, cache, skip_dirs, keep_plans=nm in removed,
                                  own_files=frozenset() if nm in removed else changed.get(nm, frozenset()))
                        for nm in names(f.get("unit_keys"), f.get("files"))) if r is not None]
    out, seen = [], set()

    def add(hit):
        if (hit["kind"], hit["at"]) not in seen:
            seen.add((hit["kind"], hit["at"]))
            out.append({"id": f"h{len(out) + 1}", **hit})

    for r in rows:
        for kind, key in (("code", "code"), ("test", "tests")):
            for at in r[key]:
                if r["name"] in changed and not non_code(_path_of(at), skip_dirs=skip_dirs) and not _covered(f, kind, at):
                    add({"name": r["name"], "kind": kind, "at": at})
                if r["name"] in removed and not _covered(f, REMOVED_KINDS[kind], at):
                    add({"name": r["name"], "kind": REMOVED_KINDS[kind], "at": at})
    return {"item": n, "unit_keys": list(f.get("unit_keys") or []), "names": rows, "uncovered": out}


def _overlaps(fields: list, items: list) -> list[dict]:
    seen: dict[str, list] = {}
    for f, it in zip(fields, items):
        paths = {g for g in f.get("allowed_paths") or [] if isinstance(g, str) and not any(c in g for c in "*?[")}
        paths |= {_path_of(at) for r in it["names"] for key in ("code", "tests") for at in r[key]}
        for p in paths:
            seen.setdefault(p, []).append(it["item"])
    return [{"at": p, "items": sorted(set(ns))} for p, ns in sorted(seen.items()) if len(set(ns)) >= 2]


def build(repo, fields: list, *, common_files: int = COMMON_FILES, skip_dirs) -> dict:
    """項目ごとの波及の一覧 {"items": [{item, unit_keys, names, uncovered}], "overlaps": [{at, items}], "error": ""}。
    fields は項目の欄の並び（番号は 1 始まりの並びの順）。git が引けなければ items は空で error に理由"""
    repo = pathlib.Path(repo)
    rows = [f if isinstance(f, dict) else {} for f in fields or []]
    cache: dict = {}
    try:
        items = [_item(repo, n, f, common_files, cache, skip_dirs) for n, f in enumerate(rows, 1)]
    except OSError as e:
        return {"items": [], "overlaps": [], "error": str(e) or type(e).__name__}
    return {"items": items, "overlaps": _overlaps(rows, items), "error": ""}


def for_units(repo, unit_keys: list, *, common_files: int = COMMON_FILES, skip_dirs) -> dict:
    """案の前の一覧 {"units": [{unit_key, names}], "error": ""}（照らす範囲が無いので覆っていない当たりを持たない）"""
    repo = pathlib.Path(repo)
    cache: dict = {}
    try:
        units = [{"unit_key": k, "names": [r for r in (_name_row(repo, nm, common_files, cache, skip_dirs) for nm in names([k], []))
                                           if r is not None]} for k in unit_keys or [] if isinstance(k, str)]
    except OSError as e:
        return {"units": [], "error": str(e) or type(e).__name__}
    return {"units": units, "error": ""}


def uncovered(doc: dict, n: int) -> list[dict]:
    """項目 n（1 始まり）の覆っていない当たり（一覧に項目が無ければ []）"""
    for it in (doc or {}).get("items") or []:
        if it.get("item") == n:
            return list(it.get("uncovered") or [])
    return []


NO_NAME = "- no name of it exists in the target"


def _names_text(rows: list) -> list[str]:
    out = []
    for r in rows:
        if r.get("common"):
            out.append(f"- {r['name']}: hits in {r['files']} files ({COMMON_NOTE})")
            continue
        out.append(f"- {r['name']}: hits in {r['files']} files")
        out += [f"  - body {at}" for at in r.get("code") or []]
        out += [f"  - test {at}" for at in r.get("tests") or []]
    return out


def item_text(doc: dict, n: int) -> str:
    """項目 n の材料の行（変える名と当たり・覆っていない当たり）。一覧に項目が無ければ見出しと当たり無しの 1 行"""
    it = next((x for x in (doc or {}).get("items") or [] if x.get("item") == n), None)
    if it is None:
        return f"### Item {n}\n\nThe names it changes were not found in the target (no hits)"
    lines = [f"### Item {n} (unit_keys: {', '.join(map(str, it['unit_keys']))})", "", "Names changed and their hits:"]
    lines += _names_text(it["names"]) or [NO_NAME]
    lines += ["", "Hits not covered:"]
    lines += [f"- {h['id']}: {h['kind']} {h['at']} (name {h['name']}){REMOVED_MARK if h['kind'] in REMOVED_KINDS.values() else ''}"
              for h in it["uncovered"]] or ["- none"]
    return "\n".join(lines)


def rows(doc: dict) -> str:
    """項目ごとの一覧の材料の行（全部の項目と、項目どうしの重なり）。error が在る・項目が無ければ空の字"""
    doc = doc or {}
    if doc.get("error") or not doc.get("items"):
        return ""
    parts = [item_text(doc, x["item"]) for x in doc["items"]]
    if doc.get("overlaps"):
        parts.append("Overlaps between items (files that appear in the scope or hits of two or more items):\n"
                     + "\n".join(f"- {o['at']}: items {', '.join(map(str, o['items']))}" for o in doc["overlaps"]))
    return "\n\n".join(parts)


def units_rows(doc: dict) -> str:
    """案の前の一覧の材料の行（単位ごと）。error が在る・単位が無ければ空の字"""
    doc = doc or {}
    if doc.get("error") or not doc.get("units"):
        return ""
    return "\n\n".join("\n".join([f"### Unit {u['unit_key']}", *(_names_text(u["names"]) or [NO_NAME])])
                       for u in doc["units"])
