"""仕様の役（書く・審査・直す）の返答の受け付け（今の lib/judge_accept.py の _spec_errors・spec_write_output・spec_review_output・
spec_revise_output・spec_take の写しを、place の名で受ける形にした物。docs/design/spec.md の 8 節）。

- 書く役: 鍵が一意・受け入れ条件が要件を指す・要件は受け入れ条件を 1 件以上持つ・テストのファイルが読めて、その名と Given/When/Then を含む。
  通ったら審査役の前の作業ツリーの写しを置く
- 審査役: 作業ツリーが写しから変わっていない（読むだけの役）・穴の鍵が一意・穴が無いなら faces_none に確かめた事
- 直す役: 審査の穴の鍵に 1 度ずつ答える・直した仕様に書く役と同じ照らし
返答が JSON のオブジェクトでない・形が違う時も、投げずに拒否として返す
"""
from __future__ import annotations

import pathlib

import accept   # lib/。作業ツリーの写しと比べ
from engine.util import READ_CAP, Reject, read_capped   # lib/graphloops/engine/util.py

from src import files

EMPTY = ("なし", "無し", "ない", "無い", "特になし", "n/a", "none", "-", "未確認", "不明",
         "todo", "未実施", "未測定", "後で")  # 「書いていない」と同じ扱いにする語


def blank(text, min_len: int) -> bool:
    """役が埋める自由文が「空同然」か（表と長さの両方で見る）"""
    t = (text or "").strip()
    return t.lower() in EMPTY or len(t) < min_len


def _keys_once(rows, label: str) -> list:
    seen, errs = set(), []
    for i, r in enumerate(rows):
        if r["key"] in seen:
            errs.append(f"{label}[{i}] の key が重複: {r['key'][:60]}")
        seen.add(r["key"])
    return errs


def spec_errors(spec, root) -> list:
    """仕様の形の誤りの文の一覧（無ければ空）"""
    root = pathlib.Path(root or ".")
    reqs, acs = spec["requirements"], spec["acceptance"]
    errs = _keys_once(reqs, "requirements") + _keys_once(acs, "acceptance")
    rkeys = {r["key"] for r in reqs}
    errs += [f"acceptance '{a['key']}' の requirement '{a['requirement']}' が requirements に無い" for a in acs if a["requirement"] not in rkeys]
    errs += [f"要件 '{k}' に受け入れ条件が無い——実行できるテストを 1 つ以上書け" for k in sorted(rkeys - {a["requirement"] for a in acs})]
    for a in acs:
        data, why = read_capped(str(root / a["file"]), READ_CAP)
        if data is None:
            errs.append(f"acceptance '{a['key']}' のテストのファイル {a['file']} が読めない（{why}）——対象リポジトリに先に書け")
            continue
        text = data.decode("utf-8", errors="replace")
        if a["name"] not in text:
            errs.append(f"acceptance '{a['key']}' の name '{a['name']}' が {a['file']} に無い")
        miss = [w for w in files.GWT if w not in text]
        if miss:
            errs.append(f"acceptance '{a['key']}' の {a['file']} に {'/'.join(miss)} が無い——受け入れ条件は Given/When/Then をテストの中に書く")
    return errs


def write_output(out, root) -> None:
    errs = spec_errors(out, root)
    if errs:
        raise Reject(f"{files.NODES['write']}: " + "; ".join(errs))


def review_output(out) -> None:
    faces = out.get("faces") or []
    errs = _keys_once(faces, "faces")
    if not faces and blank(out.get("faces_none"), files.MIN_FACES_NONE):
        errs.append("穴を挙げないなら faces_none に何を確かめて無いと言えるかを書け")
    if errs:
        raise Reject(f"{files.NODES['review']}: " + "; ".join(errs))


def revise_output(out, review, root) -> None:
    """審査の穴に key ごとに 1 度だけ答える。審査の返答は引数 review（受けた spec-review.json）"""
    asked = {f["key"] for f in (review or {}).get("faces") or []}
    rows = out["handled"]
    errs = _keys_once(rows, "handled")
    errs += [f"handled の key '{r['key'][:40]}' は仕様の審査に無い" for r in rows if r["key"] not in asked]
    errs += [f"仕様の審査の '{k[:40]}' に応答が無い——{files.HANDLED[0]}（どう取り込んだか）か {files.HANDLED[1]}（残す理由）で答えろ"
             for k in sorted(asked - {r["key"] for r in rows})]
    errs += spec_errors(out["spec"], root)
    if errs:
        raise Reject(f"{files.NODES['revise']}: " + "; ".join(errs))


def revise_due(review) -> bool:
    """直す輪を回すか: 審査が穴を 1 件以上挙げた時"""
    return bool((review or {}).get("faces"))


def current(place):
    """いまの仕様: 直した版（spec-revise.json の spec）が在ればそれ、無ければ最初の版（spec-write.json）。どちらも無ければ None"""
    revised = files.read(files.role_file(place, "revise"))
    return revised["spec"] if revised else files.read(files.role_file(place, "write"))


def _snapshot(path):
    """置き場に置いた作業ツリーの写し（accept.tree_state の形）。無ければ None、読めない・形が違えば Reject"""
    try:
        snap = files.read(path)
    except ValueError as e:
        raise Reject(f"作業ツリーの写し {path} が読めない（{e}）") from None
    if snap is None:
        return None
    accept.type_errors(snap, accept.TREE_SCHEMA, f"作業ツリーの写し {path} ")
    return {k: snap[k] for k in accept.TREE_KEYS}


def _moved_since(path, repo, keys) -> list:
    snap = _snapshot(path)
    if snap is None:
        raise Reject(f"作業ツリーの写し {path} が無い——役を起こす前の作業ツリーと比べられない（写しを置くノードが先に走る）")
    return accept.tree_moved(snap, pathlib.Path(repo), keys=keys)


def take(place, role: str, reply, root, *, keys=accept.TREE_KEYS) -> dict:
    """仕様の役の返答を受け付ける。返り {ok, reason, revise}。
    - 読むだけの役（review）は作業ツリーを、書く役の返答を受けた時に置いた写しと比べ、変わっていれば拒む。書く役（write・revise）は
      テストのファイルを書くので比べない
    - 通れば返答を spec-<役>.json に置く。write が通ったら審査役の前の作業ツリーの写しを置く
    - revise は審査が穴を挙げた時だけ真（直す輪を回すか）
    keys は審査役の写しと比べる欄"""
    place, root = pathlib.Path(place), pathlib.Path(root)
    if role not in files.ROLES:
        return {"ok": False, "reason": f"役 {role!r} を知らない（{' / '.join(files.ROLES)}）", "revise": False}
    nid = files.NODES[role]
    snap = None
    try:
        if not isinstance(reply, dict):
            raise Reject(f"{nid}: 返答が JSON のオブジェクトでない（{type(reply).__name__}）")
        if role == "review":
            moved = _moved_since(files.snapshot_path(place), root, keys)
            if moved:
                raise Reject("読むだけの役が作業ツリーを変えた: 仕様の審査は読むだけの役で、作業ツリー・HEAD・枝・git が無視する"
                             "ファイルを変えてはいけない（変えた物を元に戻せ）（" + "・".join(moved) + "）")
            review_output(reply)
        elif role == "write":
            write_output(reply, root)
            snap = accept.tree_state(root)
        else:
            revise_output(reply, files.read(files.role_file(place, "review")), root)
    except Reject as e:
        return {"ok": False, "reason": str(e), "revise": False}
    except (KeyError, TypeError, AttributeError, ValueError) as e:
        return {"ok": False, "reason": f"{nid}: 返答の形が違う（{type(e).__name__}: {e}）", "revise": False}
    files.write(files.role_file(place, role), reply)
    if snap is not None:
        files.write(files.snapshot_path(place), snap)
    return {"ok": True, "reason": "", "revise": role == "review" and revise_due(reply)}
