"""並行 PR の機械の道（docs/design/parallel-pr.md の 1.3 の scan）。開いている PR と、この run の変更ファイルの交差を gh の読みだけで数え、
機械が決められない時だけ役 pr-check を起こす。元は lib/judge_accept.py の _github_repo・_pr_files・parallel_pr_plan・parallel_pr_scan・
parallel_pr_reply・_pr_material・pr_scan（元 works/.shared/core/graphloops/rules/review-loop.py）。始めの記録・止めの控え・依頼の
置き場は読まず、port の値を引数で受ける。
"""
import pathlib
import shutil

import accept as core_accept   # lib/
import forge                   # lib/
import ghreads                 # lib/（gh の読む口）
import jsonfile                # lib/
from engine.util import Reject   # lib/graphloops/

from . import files


def github_repo(repo):
    """並行 PR を引く gh -R の HOST/OWNER/REPO ——（値, 引けない理由）。remote の選び（upstream を先に、無ければ origin）は forge.detect、
    URL の読みは forge.repo_of。-R はホストまで書く（ホストの無い名を gh は GH_HOST で解き、別のホストを読みうる）"""
    remote = forge.detect(repo)["remote"] or "origin"
    url = forge._git(repo, "remote", "get-url", remote)
    if url is None:
        return None, f"remote '{remote}' の URL が引けない"
    got = forge.repo_of(url)
    if not got or got["kind"] != forge.GITHUB:
        return None, forge.redact(f"remote '{remote}' が GitHub でない（{url.strip()[:80]}）——同等のコマンドへの読み替えは役")
    return "/".join((got["host"], got["owner"], got["name"])), None


def wheres_of(request) -> list:
    """依頼の行（行の配列）の where の字の並び"""
    return [r["where"] for r in request if isinstance(r, dict) and isinstance(r.get("where"), str)]


def changed_files(repo, changed, base: str, wheres) -> list:
    """交差を取る変更ファイルの集合。順に最初に空でない物: port changed の値・base から作業ツリーまでの変更ファイル（lib/accept.touched_files。
    取れなければ空）・追跡中のパスのうち依頼の where の字に含まれる物（名の順）"""
    if changed:
        return list(changed)
    found = []
    if base:
        try:
            found = core_accept.touched_files(pathlib.Path(repo), base)
        except Reject:
            found = []
    if found:
        return found
    tracked = (forge._git(repo, "ls-files", "-z") or "").split("\0")
    return sorted({t for t in tracked if t and any(t in w for w in wheres)})


def plan(repo, changed, *, which=None) -> dict:
    """返り {fallback: 理由}（役に任せる）・{blocked: 理由}（走らせずに not_run）・{repo, head, files}（数えを走らせる）。
    which は gh を探す口（試験が差し替える）"""
    slug, why = github_repo(repo)
    if not slug:
        return {"fallback": why}
    if not (which or shutil.which)("gh"):
        return {"fallback": "gh がこの環境に無い"}
    if not changed:
        return {"blocked": "交差を取る変更ファイルの集合が空（差分も、依頼の where が名指す追跡中のパスも無い）——空の集合との交差は何も確かめない"}
    head = (forge._git(repo, "rev-parse", "HEAD") or "").strip()
    return {"repo": slug, "head": head, "files": changed}


def count(repo, slug: str, head: str, changed, *, gh=None) -> tuple:
    """開いている PR を gh -R で引き、自分の PR（headRefOid が head）を外して、残った PR の変更ファイルと changed の交差を取る。
    gh は lib/ghreads の読む口（gh(*args) -> (値, 読めない理由, no_host)。試験が差し替える）で、読むだけ。
    返り ({repo, listed, truncated, conflicts: [{pr, files}]}, "") か (None, gh が読めなかった理由)"""
    gh = gh or (lambda *args: ghreads._gh(pathlib.Path(repo), *args))
    mine = {f.strip() for f in changed if f.strip()}
    prs, why, _ = gh("pr", "list", "-R", slug, "--limit", str(files.PR_LIMIT), "--json", "number,headRefName,headRefOid")
    if not isinstance(prs, list):
        return None, why or "gh pr list の出力が配列でない"
    others = [pr for pr in prs if isinstance(pr, dict) and pr.get("headRefOid") != head]
    conflicts = []
    for pr in others:
        doc, why, _ = gh("pr", "view", str(pr.get("number")), "-R", slug, "--json", "files")
        if not isinstance(doc, dict):
            return None, why or f"gh pr view {pr.get('number')} の出力が object でない"
        got = {str(f.get("path")).strip() for f in doc.get("files") or [] if isinstance(f, dict) and f.get("path")}
        hit = sorted(got & mine)
        if hit:
            conflicts.append({"pr": str(pr.get("number")), "files": hit})
    return {"repo": slug, "listed": len(prs), "truncated": len(prs) >= files.PR_LIMIT, "conflicts": conflicts}, ""


def reply_of(launch: dict, got, why: str = "") -> dict:
    """数えの結果から返答を組む。交差が在れば 6 段（hunk を読んで担当の PR に申し送る）が要るので任せ先に回す（{fallback: 理由}）。
    ほかは {reply: 役の返答の形}"""
    empty = {"repo": "", "listed": 0, "truncated": False, "conflicts": []}
    if launch.get("blocked"):
        return {"reply": {"material": {"status": "not_run", "reason": launch["blocked"]}, **empty}}
    if got is None:
        return {"reply": {"material": {"status": "awaiting_human", "reason": f"並行 PR の数えが gh を読めない（確かめられなかった）: {str(why)[-600:]}"}, **empty}}
    rest = {k: got.get(k) for k in ("repo", "listed", "truncated")}
    if got.get("conflicts"):
        return {"fallback": f"並行 PR と {len(got['conflicts'])} 件交差した（{[c['pr'] for c in got['conflicts']][:10]}）——交差した hunk を読んで担当の PR に申し送る 6 段は役"}
    if got.get("truncated"):
        return {"reply": {"material": {"status": "awaiting_human", "reason": f"gh pr list が上限 {got.get('listed')} 件で打ち切られた——打ち切られた一覧で衝突なしと書かない"}, **rest, "conflicts": []}}
    return {"reply": {"material": {"status": "clean", "checked": (f"engine が gh -R {got['repo']} で open な PR {got['listed']} 件を引き、自分の PR（headRefOid が HEAD）を除いて、"
                                                            f"変更ファイルの集合と交差 0 件（打ち切りなし）")}, **rest, "conflicts": []}}


def _material(place, reply: dict) -> None:
    jsonfile.write(place / files.MATERIAL, {"role": files.ROLE, "reply": reply, "materials": {"parallel_pr": reply["material"]}})


def _clear(place) -> None:
    """この block が前の run で置いた名前つきのファイル（読んだ証拠の落ちた記録は時刻つきなので名の型で引く）を消す。place そのものと、ほかの名は消さない"""
    for name in files.OWN:
        (place / name).unlink(missing_ok=True)
    for path in place.glob(files.READS_FAILED):
        path.unlink()
    n = 1
    while (path := place / files.PROMPT.format(n=n)).is_file():
        path.unlink()
        n += 1


def scan(place, repo, *, request, base: str, changed, gh=None, which=None) -> dict:
    """機械の道を回す。返り {go_role, reason}: go_role は機械で決められず役 pr-check が要るか。
    前の run のこの block のファイルを名で引いて消し、役の前の作業ツリーの写し tree.json を取る。渡し物 pr-brief.json はどの道でも書く。
    機械が決めた時は素材の控えと、空の外す hunk の控えを書く。機械の道が落ちたら役に任せる（go_role 真）。
    作業ツリーの写しが取れなければ役を起こさず（受け付けが比べられない）、go_role 偽と訳を返す"""
    place, repo = pathlib.Path(place), pathlib.Path(repo)
    _clear(place)
    try:
        jsonfile.write(place / files.TREE, core_accept.tree_state(repo))
    except Reject as e:
        return _done(place, {"go_role": False, "reason": f"作業ツリーの写しが取れない（役の前後を比べられない）: {e}"})
    wheres = wheres_of(request)
    changed_set, head = [], ""
    try:
        changed_set = changed_files(repo, changed, base, wheres)
        head = (forge._git(repo, "rev-parse", "HEAD") or "").strip()
        no_forge = forge.reason(forge.detect(repo))
        if no_forge:
            result = {"reply": {"material": {"status": "not_applicable", "reason": no_forge},
                                "repo": "", "listed": 0, "truncated": False, "conflicts": []}}
        else:
            launch = plan(repo, changed_set, which=which)
            if "fallback" in launch:
                result = launch
            elif launch.get("blocked"):
                result = reply_of(launch, None)
            else:
                got, why = count(repo, launch["repo"], launch["head"], launch["files"], gh=gh)
                result = reply_of(launch, got, why)
    except Exception as e:  # noqa: BLE001  機械の道が落ちたら役に任せる（起こし直しは当たらない）
        result = {"fallback": f"機械の道が落ちた（{type(e).__name__}: {e}）——役に任せる"}
    jsonfile.write(place / files.BRIEF, {"node": files.NODE, "cwd": str(repo), "base": base, "changed_files": changed_set,
                                         "request_wheres": wheres, "fallback": result.get("fallback", "")})
    if "fallback" in result:
        return _done(place, {"go_role": True, "reason": result["fallback"]})
    reply = result["reply"]
    _material(place, reply)
    jsonfile.write(place / files.EXCLUDED, {"node": files.NODE, "head": head, "excluded": []})
    m = reply["material"]
    return _done(place, {"go_role": False, "reason": f"機械が決めた: {m['status']}（{m.get('reason') or m.get('checked') or ''}）"})


def _done(place, out: dict) -> dict:
    """返りを scan.json にも残す（出口が読む）"""
    jsonfile.write(place / files.SCAN, out)
    return out
