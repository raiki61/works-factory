"""審査役（review-1・review-2）の返答の受け付け（docs/design/delta-review.md の 2.8・4 節。写す元は lib/fixboard.py の
delta_review_problems・claimed_closed・tree_moved_since・take と lib/refix.py の accept_review・inner_faces・_added_text）。

照らす順: 穴と検算の照らし（problems）→ 1 回目だけ 2 判定の照らし（verdicts.gaps）→ 2 判定の欄を外した返答に機械の穴（内側の語）を
足す → 役を起こす前に撮った作業ツリーの写しと今の作業ツリーを比べる。通れば review-<n>-reply.json・verdicts.json・review-<n>.json の順に書く。
"""
import pathlib

import ports  # noqa: F401  （lib/ と lib/graphloops/ を sys.path に足す）
from engine.util import READ_CAP, read_capped  # lib/graphloops/

import accept  # lib/
import jsonfile  # lib/
import leftovers  # lib/
import oneline  # lib/
import policy  # lib/
import report  # lib/
import rolekit  # lib/
from engine.schema import validate_schema  # lib/graphloops/

from src import cut, files, materials, touchup, verdicts

FACE_KINDS = ("copy", "entrance", "contract_drift", "dead_path", "scope_creep")   # 穴の語（YAML の kind の enum と同じ並び）
HUMAN_FACE_KINDS = ("regression", policy.POLICY_KIND)
PLAN_ONLY_FACE_KINDS = HUMAN_FACE_KINDS + ("precedent",)   # 事前審査だけの語（ここでは受け付けない）
CLAIMED = {1: "absorbed", 2: "fixed"}   # 塞いだと言われた答えの語（1 回目は修正役の plan_faces、2 回目は 1 回目の手直しの handled）
NONE_MIN = 20   # faces_none の字の下限
MIN_KEY, MIN_CITE, MIN_WHY = 8, 4, 20   # md の差し込み口の値（YAML の minLength と同じ）
READONLY_MOVED = "読むだけの役が作業ツリーを変えた: "
PROBLEMS = "差分の審査の返答の照らしに通らない:\n"


def claimed_closed(place, n: int) -> set:
    """n 回目の審査が検算する『塞いだ』と言われた穴の key: 1 回目は修正役が plan_faces で absorbed と答えた穴（fix-reply.json）、
    2 回目は 1 回目の手直しが fixed と答えた穴（refix-1-reply.json）"""
    place = pathlib.Path(place)
    if n == 1:
        rows = (jsonfile.read_or(place / files.FIX_REPLY) or {}).get("plan_faces")
    else:
        rows = (jsonfile.read_or(place / files.refix_reply(n - 1)) or {}).get("handled")
    return {r.get("key") for r in rows or [] if isinstance(r, dict) and r.get("handled") == CLAIMED[n]}


def _keys_once(rows, label) -> list:
    seen, errs = set(), []
    for i, r in enumerate(rows):
        k = r.get("key") if isinstance(r, dict) else None
        if k in seen:
            errs.append(f"{label}[{i}] の key が重複: {str(k)[:60]}")
        seen.add(k)
    return errs


def problems(place, n: int, reply: dict, repo) -> list:
    """n 回目の審査の返答の照らし（拒む行の並び。空なら通る）: 穴の key は一意、kind は事前審査だけの語でない、where はこの往復の差分が
    触ったファイル、cite はそのファイルの今の姿に在る字列、穴が無いなら faces_none（NONE_MIN 字以上）。検算 checks は『塞いだ』と言われた
    穴に 1 件ずつ、余り・欠け・重複なし"""
    d = cut.read_cut(place, n)
    changed, root = set(d.get("files") or []), pathlib.Path(repo)
    faces = [f for f in reply.get("faces") or [] if isinstance(f, dict)]
    errs = _keys_once(faces, "faces")
    for i, f in enumerate(faces):
        kind, where, cite = f.get("kind"), str(f.get("where") or ""), str(f.get("cite") or "")
        if kind in HUMAN_FACE_KINDS:
            errs.append(f"faces[{i}] の kind '{kind}' は事前審査だけの語——修正の後の後退・方針とのぶつかりは後の段が人に聞く")
            continue
        if kind in PLAN_ONLY_FACE_KINDS:
            errs.append(f"faces[{i}] の kind '{kind}' は事前審査だけの語——判定者の先行例はこのノードに渡っていない")
            continue
        if where not in changed:
            errs.append(f"faces[{i}] の where '{where[:60]}' はこの往復の差分が触ったファイルでない（{sorted(changed)[:5]}）")
            continue
        data, _ = read_capped(str(root / where), READ_CAP)
        if data is None or not cite or cite.encode("utf-8") not in data:
            errs.append(f"faces[{i}] の cite '{cite[:40]}' が {where} の今の姿に無い——在る字列を写せ")
    if not faces and len(str(reply.get("faces_none") or "").strip()) < NONE_MIN:
        errs.append("穴を挙げないなら faces_none に何を読んで無いと言えるかを書け")
    claimed, checks = claimed_closed(place, n), [c for c in reply.get("checks") or [] if isinstance(c, dict)]
    errs += _keys_once(checks, "checks")
    errs += [f"checks の key '{str(c.get('key'))[:40]}' は塞いだと言われた穴に無い" for c in checks if c.get("key") not in claimed]
    errs += [f"塞いだと言われた穴 '{str(k)[:40]}' に検算が無い——差分で塞がったか（closed）を 1 件ずつ書け"
             for k in sorted(claimed - {c.get("key") for c in checks}, key=str)]
    return errs


def _added_text(place, n: int, repo) -> str:
    """n 回目の照らしに当てる差分の字。1 回目は修正の差分。2 回目は修正の前の版から 2 回目に固めた姿までの、修正か手直しが触った
    ファイルの差分（1 回目の手直しが直したと答えて残した語も拾う）"""
    d = cut.read_cut(place, n)
    if n == 1:
        return pathlib.Path(d["file"]).read_text(encoding="utf-8", errors="replace")
    first = cut.read_cut(place, 1)
    names = sorted({*(first.get("files") or []), *(d.get("files") or [])})
    return leftovers.git(repo, "diff", first["base"], d["rev"], "--", *names) if names else ""


def inner_faces(place, n: int, repo) -> list:
    """n 回目の照らしの差分が足した行のうち、works の内側の語（report.INNER_WORD）を含む行の機械の穴 [{key, kind, where, cite, why}]。
    対象が修正の前の版で既に使う語は数えない。key は「<kind> <パス>:<行>」"""
    base = cut.read_cut(place, 1)["base"]
    return [{"key": f"{report.INNER_FACE_KIND} {h['path']}:{h['line']}", "kind": report.INNER_FACE_KIND, "where": h["path"],
             "cite": h["text"], "why": f"足した行に works の内側の語（{'・'.join(h['words'])}）が在る。対象の読み手に通じない。言い換えよ"}
            for h in report.inner_word_hits(_added_text(place, n, repo), lambda w: report.target_uses(repo, base, w))]


def tree_moved(place, n: int, repo) -> str:
    """役を起こす前の作業ツリーの写し review-<n>-tree.json と今の作業ツリーの違いを述べる文（同じなら空）。写しが無い・形が違えば
    その訳（読むだけの役を起こす前に写しを撮っていない）"""
    path = pathlib.Path(place) / files.review_tree(n)
    snap = jsonfile.read_or(path)
    if snap is None:
        return f"作業ツリーの写し {path} が無いか読めない（読むだけの役を起こす前に写しを撮っていない）"
    errs = validate_schema(snap, accept.TREE_SCHEMA)
    if errs:
        return f"作業ツリーの写し {path} の形が違う: " + "; ".join(errs)
    moved = accept.tree_moved({k: snap[k] for k in accept.TREE_KEYS}, pathlib.Path(repo), keys=files.TREE_KEYS)
    if not moved:
        return ""
    return READONLY_MOVED + "この役は読むだけの役で、作業ツリー・HEAD・枝・git が無視するファイルを変えてはいけない（" + "・".join(moved) + "）"


def take(place, n: int, reply, repo) -> dict:
    """n 回目の審査役の返答の 1 回分の受け付け。返り {ok, reason} か {ok: True, owed}。諦めは rolekit の輪が数える"""
    if not isinstance(reply, dict):
        return {"ok": False, "reason": "返答が JSON のオブジェクトでない"}
    try:
        materials.verify(place)
    except ValueError as error:
        return touchup.stop(place, files.REVIEW[n] + "-accept", f"範囲・許しの写しが入口の後に変わった: {error}")
    bad = problems(place, n, reply, repo)
    if bad:
        return {"ok": False, "reason": PROBLEMS + "\n".join(f"  - {x}" for x in bad)}
    split_off = None
    bare = reply
    if n == 1 and not verdicts.malformed(reply):
        scope = jsonfile.read_or(pathlib.Path(place) / files.SCOPE) or {}
        gaps = verdicts.gaps(reply, scope.get("plan_items") or [])
        if gaps:
            return {"ok": False, "reason": verdicts.REJECT + "\n" + "\n".join(f"  - {g}" for g in gaps)}
        bare, split_off = verdicts.split(reply)
    elif n == 1:
        bare = verdicts.split(reply)[0]   # 穴の並びの形でない返答は 2 判定を照らさず、欄を外して受ける（返答の型は node の output_format が照らす）
    extra = inner_faces(place, n, repo) if isinstance(bare.get("faces"), list) else []
    if extra:
        bare = {**bare, "faces": [*bare["faces"], *extra]}
    moved = tree_moved(place, n, repo)
    if moved:
        return {"ok": False, "reason": moved}
    path = jsonfile.write(pathlib.Path(place) / files.review_reply(n), bare, indent=2)
    if split_off:
        try:
            verdicts.save(place, split_off)
        except Exception as error:  # noqa: BLE001  書けない・形にできない: 受けた審査に欄が無いまま先へ進ませない
            reason = (f"審査の返答を受けた後で、受け付けが外した欄の控え {files.VERDICTS} を置けない"
                      f"（控えの無いまま先へ進ませない）: {type(error).__name__}: {oneline.one_line(error)}")
            return touchup.stop(place, files.REVIEW[n] + "-accept", reason)
    owed = len(touchup.owed_rows(place, n))
    jsonfile.write(pathlib.Path(place) / files.review_record(n), {"pass": owed == 0, "owed": owed, "reply_file": str(path)})
    return {"ok": True, "reason": "", "owed": owed}


def gave_up_record(place, n: int) -> None:
    jsonfile.write(pathlib.Path(place) / files.review_record(n),
                   {"pass": False, "owed": 0, "reply_file": "", "gave_up": True,
                    "reason": rolekit.given_up_reason(pathlib.Path(place), files.REVIEW[n])})


def accept_reply(place, n: int, raw, repo) -> dict:
    """スクリプト review_accept の本体: 返答の字 raw を受け、拒否は rolekit の控え（rejects-review-<n>.json）に積み、3 回目で done。
    返り {ok, done, reason}"""
    place = pathlib.Path(place)
    got = rolekit.accept_round(place, files.REVIEW[n], raw, lambda reply: take(place, n, reply, repo),
                               on_give_up=lambda: gave_up_record(place, n))
    return {"ok": bool(got["ok"]), "done": bool(got["done"]), "reason": str(got["reason"])}
