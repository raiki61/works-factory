"""手直しの役（refix-1・refix-2）の材料・指示の値・返答の受け付け（docs/design/delta-review.md の 3.8・5 節）。写す元は lib/fixboard.py の
_owed_rows・prep_fix・tie_items・hole_ties・delta_fix_problems・undeclared_refix・undeclared_writes・touched_since と lib/refix.py の
accept_fix・SCOPE_REJECT・brief_ties。

- owed_rows(place, n): 手直しが答える義務 [{key, from, text}]。n 回目の審査の穴の全部と、塞がっていない検算（closed が false）
- hole_ties(place, n): 義務の穴ごとの枝の名札（holeties.tie）。組めなければ例外（呼び手が訳にする）
- write_brief(place, n): 手直しの役が Read する材料を refix-<n>-brief.json に書く
- scope_lines(plan_items, permits): 指示の範囲の節に貼る (項目ごとの行, 全部の項目に効く許しの行)。受け付けが照らす値と同じ値
- take(...)・accept_reply(...): 返答の受け付け
"""
import os
import pathlib
import posixpath

import ports  # noqa: F401  （lib/ を sys.path に足す）

import jsonfile  # lib/
import holeties  # lib/
import leftovers  # lib/
import oneline  # lib/
import planmarks  # lib/
import planrange  # lib/
import rolekit  # lib/
import writelog  # lib/
import writes  # lib/

from src import cut, files, materials, verdicts

HANDLED = ("fixed", "declared")   # 手直しの答えの語（YAML の enum と同じ並び）
UNDECLARED = ("書き込みの記録が無い run で、作業ツリーの変更が返答の handled[].files にも bash_writes にも無い——直したファイルなら "
              "handled の files に足し、Bash で書いたなら bash_writes にパスと理由を書き、要らない変更なら戻せ: ")
# 手直しの変更が承認済みの修正案の項目の範囲から外れた時の拒否の頭（planrange.outside の行を続ける）
SCOPE_REJECT = ("手直しが承認済みの修正案の項目の範囲から外れた（項目の範囲の外で変えてよいのは、材料の ruled_paths と、範囲の相談で"
                "合意したパス・テストの変更の許しのパスだけ。外れた変更を戻して返答を丸ごと出し直せ。試験を回して出来たファイル"
                "（キャッシュ・結果の XML）も消せ。範囲の外が要る穴は直さずに declared で残し、how に理由を書け）: ")
PROBLEMS = "手直しの返答の照らしに通らない:\n"
MIN_HOW = 20   # md の差し込み口の値（YAML の minLength と同じ）


# ---------------------------------------------------------------- 義務と名札
def owed_rows(place, n: int) -> list:
    reply = jsonfile.read_or(pathlib.Path(place) / files.review_reply(n)) or {}
    rows = [{"key": f["key"], "from": files.REVIEW[n], "text": f"{f['kind']} {f['where']}:「{f['cite']}」——{f['why']}"}
            for f in reply.get("faces") or []]
    rows += [{"key": c["key"], "from": f"{files.REVIEW[n]}.checks", "text": f"塞いだと言われたが、差分で塞がっていない——{c['why']}"}
             for c in reply.get("checks") or [] if c["closed"] is False]
    return rows


def hole_ties(place, n: int) -> list:
    """n 回目の義務の穴ごとの枝の名札。where は n 回目の審査の faces から。1 回目は準拠の落ちた行・事前審査の穴・修正の changes を、
    2 回目は 1 回目の名札と 1 回目の手直しの handled（holeties.earlier）を使う。義務が無ければ []"""
    place = pathlib.Path(place)
    rows = owed_rows(place, n)
    if not rows:
        return []
    reply = jsonfile.read_or(place / files.review_reply(n)) or {}
    where = {f.get("key"): f.get("where") for f in reply.get("faces") or [] if isinstance(f, dict)}
    holes = [{"key": r["key"], "from": r["from"], "where": where.get(r["key"]) or "", "check": r["from"].endswith(".checks")} for r in rows]
    tied = (jsonfile.read_or(place / files.SCOPE) or {}).get("plan_items") or []
    if n == 1:
        return holeties.tie(holes, tied, compliance=verdicts.fail_rows(verdicts.read(place)),
                            plan_faces=((jsonfile.read_or(place / files.PLAN_REVIEW) or {}).get("faces") or []),
                            changes=((jsonfile.read_or(place / files.FIX_REPLY) or {}).get("changes") or []))
    handled = (jsonfile.read_or(place / files.refix_reply(n - 1)) or {}).get("handled") or []
    return holeties.tie(holes, tied, earlier=holeties.earlier(hole_ties(place, n - 1), handled))


def brief_ties(ties: list) -> list:
    """手直しの役の材料の ties の欄: 穴ごとの {key, branches（人が読む枝の名）, note, via}"""
    return [{"key": t["key"], "branches": [holeties.label(x) for x in t["branches"]], "note": holeties.note(t), "via": t["via"]}
            for t in ties]


def write_brief(place, n: int) -> pathlib.Path:
    place = pathlib.Path(place)
    scope = jsonfile.read_or(place / files.SCOPE) or {}
    doc = {"diff_file": cut.read_cut(place, n)["file"], "owed": owed_rows(place, n)}
    try:   # 穴ごとの枝の名札（材料だけで、答え方は変えない。組めなければ理由を置いて手直しは起こす）
        doc["ties"] = brief_ties(hole_ties(place, n))
    except Exception as error:  # noqa: BLE001
        doc["ties"], doc["ties_error"] = [], f"{type(error).__name__}: {oneline.one_line(error)}"
    if n == 1:
        doc.update(plan_items=scope.get("plan_items") or [], ruled_paths=scope.get("ruled_paths") or [], agreed=scope.get("agreed") or [])
        doc["compliance"] = verdicts.fail_rows(verdicts.read(place))
    return jsonfile.write(place / files.refix_brief(n), doc, indent=2)


# ---------------------------------------------------------------- 範囲の節の値
def _ticks(paths) -> str:
    return ", ".join(f"`{p}`" for p in paths) or "none"


def permit_union(place) -> list:
    """全部の項目に効く許しのパス（port permits のパスと範囲の欄の ruled_paths の和。重ねない）"""
    place = pathlib.Path(place)
    permits = jsonfile.read_or(place / files.PERMITS) or []
    ruled = (jsonfile.read_or(place / files.SCOPE) or {}).get("ruled_paths") or []
    return list(dict.fromkeys([*permits, *ruled]))


def scope_lines(plan_items: list, permits) -> tuple:
    """指示の範囲の節に貼る値 (scope_items, scope_permits)。承認済みの項目が無ければ両方空の字。値は受け付けが照らす値（planrange.outside が
    読む allowed_paths・テストのファイル・out_of_scope・合意で外したパスと、全部の項目に効く許し）"""
    if not plan_items:
        return "", ""
    lines = []
    for it in plan_items:
        units = ", ".join(str(k) for k in it.get("unit_keys") or []) or "none"
        oos = [f"`{r['glob']}`" + (f" ({r['why']})" if r.get("why") else "") for r in it.get("out_of_scope") or []
               if isinstance(r, dict) and isinstance(r.get("glob"), str) and r["glob"]]
        lines += [f"- Item {it.get('item')} (units: {units})",
                  f"  - allowed_paths: {_ticks(planrange.globs(it))}",
                  f"  - test files (ids in tests and rewrite_tests): {_ticks(planmarks.test_paths(it))}",
                  f"  - out_of_scope: {', '.join(oos) or 'none'}"]
        if it.get(planrange.LIFTED):
            lines.append(f"  - paths lifted from out_of_scope by a scope consultation: {_ticks(it[planrange.LIFTED])}")
    return "\n".join(lines), _ticks(list(permits))


# ---------------------------------------------------------------- 受け付け
def _declared(rows, repo) -> set:
    """行の files を、リポジトリの根からの相対パスに揃えた集合（絶対パスは親のフォルダと根のリンクを解いてから比べる）"""
    out, root = set(), os.path.realpath(repo)
    for row in rows:
        for f in row.get("files") or []:
            if isinstance(f, str) and f.strip():
                f = f.strip()
                if os.path.isabs(f):
                    f = os.path.relpath(os.path.join(os.path.realpath(os.path.dirname(f)), os.path.basename(f)), root)
                out.add(posixpath.normpath(f))
    return out


def touched_since(repo, tree: str) -> list:
    """木 tree（段の頭の木）から作業ツリーの今の姿（未追跡を含む・無視される物を除く）で変わったパス。除くパスの頭の下は数えない"""
    now = leftovers.snapshot(repo)
    return [p for p in leftovers.git_names(repo, "diff-tree", "-r", "--name-only", "--no-renames", tree, now)
            if not p.startswith(files.SKIP)]


def undeclared(reply: dict, repo, tree: str) -> list:
    """書き込みの出どころ（U6 の狭め）: 段の頭の木から変わったパスのうち、返答の handled[].files にも bash_writes の path にも無い物を
    名指す拒否の文（無ければ空の並び）"""
    told = _declared([{"files": h.get("files") or []} for h in reply.get("handled") or [] if isinstance(h, dict)], repo)
    told |= _declared([{"files": [w.get("path") for w in reply.get("bash_writes") or [] if isinstance(w, dict)]}], repo)
    left = [p for p in touched_since(repo, tree) if p not in told]
    return [UNDECLARED + ", ".join(left)] if left else []


def _keys_once(rows) -> list:
    seen, errs = set(), []
    for i, r in enumerate(rows):
        if r.get("key") in seen:
            errs.append(f"handled[{i}] の key が重複: {str(r.get('key'))[:60]}")
        seen.add(r.get("key"))
    return errs


def problems(place, n: int, reply: dict) -> list:
    """n 回目の手直しの返答の照らし: 義務の key ごとに 1 度だけ答え、余り・欠けが無く、fixed には files が在る"""
    asked = {r["key"] for r in owed_rows(place, n)}
    rows = [r for r in reply.get("handled") or [] if isinstance(r, dict)]
    errs = _keys_once(rows)
    errs += [f"handled の key '{str(r.get('key'))[:40]}' は差分の審査に無い" for r in rows if r.get("key") not in asked]
    errs += [f"穴 '{k[:40]}' に応答が無い" for k in sorted(asked - {r.get("key") for r in rows})]
    errs += [f"handled '{str(r.get('key'))[:40]}' は fixed なのに files が空" for r in rows if r.get("handled") == "fixed" and not r.get("files")]
    return errs


class Broken(Exception):
    """出し直しでは直らない配線の誤り（受け付けが要る控えが無い・形が違う）。guarded が stop にする"""


def stop(place, node: str, reason: str) -> dict:
    """出し直しても直らない壊れ: 訳を errors.json に積み、回数を待たずに諦める（出口が status: failed にする）"""
    path = pathlib.Path(place) / files.ERRORS
    jsonfile.write(path, [*(jsonfile.read_or(path) or []), {"node": node, "reason": reason}])
    return {"ok": False, "give_up": True, "reason": reason}


def guarded(place, node: str, compute) -> dict:
    """受け付けの本体を回す。中の例外は役への拒否（rolekit.accept_round が既定でする）にせず、stop で止める"""
    try:
        return compute()
    except Exception as error:  # noqa: BLE001
        why = str(error) if isinstance(error, Broken) else f"受け付けの中で例外（{type(error).__name__}: {oneline.one_line(error)}）"
        return stop(place, node, why)


def take(place, n: int, reply, repo, base: str, sealed) -> dict:
    """n 回目の手直しの返答の 1 回分の受け付け。sealed は入口の返りの凍結の印。受け付けの中の例外は stop で止める"""
    return guarded(place, files.REFIX[n] + "-accept", lambda: _take(pathlib.Path(place), n, reply, repo, base, sealed))


def _take(place, n: int, reply, repo, base: str, sealed) -> dict:
    if not isinstance(reply, dict):
        return {"ok": False, "reason": "返答が JSON のオブジェクトでない"}
    try:
        materials.verify(place, sealed)
    except ValueError as error:
        return stop(place, files.REFIX[n] + "-accept", f"範囲・許しの写しが入口の後に変わった: {error}")
    head = (jsonfile.read_or(place / files.refix_head(n)) or {}).get("tree") or ""
    if not head:
        raise Broken(f"手直しの段の頭の木 {files.refix_head(n)} が無い（手直しの役を起こす前に控えていない）")
    bad = problems(place, n, reply) + undeclared(reply, repo, head)
    if bad:
        return {"ok": False, "reason": PROBLEMS + "\n".join(f"  - {x}" for x in bad)}
    paths = writes.changed(repo, base)
    scope = jsonfile.read_or(place / files.SCOPE) or {}
    items = scope.get("plan_items") or []
    if items:   # 範囲の欄の無い run（項目が空）は照らさない
        first = set(cut.read_cut(place, 1)["files"])
        outside = planrange.outside(items, sorted(p for p in paths if p not in first), permit_union(place), hint=False)
        if outside:
            return {"ok": False, "reason": SCOPE_REJECT + "\n" + "\n".join(f"  - {x}" for x in outside)}
    log = writelog.log_here()
    got = writes.check(reply, repo, paths, pathlib.Path(log) if log else place / writelog.LOG, skip=files.SKIP)
    if got["problems"]:
        return {"ok": False, "reason": "\n".join(got["problems"])}
    jsonfile.write(place / files.refix_reply(n), got["reply"], indent=2)
    writes.trace(place, files.REFIX[n], got)
    return {"ok": True, "reason": ""}


def accept_reply(place, n: int, raw, repo, base: str, sealed) -> dict:
    """スクリプト refix_accept の本体。拒否は rolekit の控え（rejects-refix-<n>.json）に積み、3 回目で done（作業ツリーの手直しは
    戻さない）。返り {ok, done, reason}"""
    place = pathlib.Path(place)
    role = files.REFIX[n]
    iteration = rolekit.attempt(place, role)
    got = rolekit.accept_round(place, role, raw, lambda reply: take(place, n, reply, repo, base, sealed))
    files.trace(place, "refix_accepted" if got["ok"] else "refix_rejected", node=f"{role}-accept", iteration=iteration, done=bool(got["done"]))
    return {"ok": bool(got["ok"]), "done": bool(got["done"]), "reason": str(got["reason"])}
