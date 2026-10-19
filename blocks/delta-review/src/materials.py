"""port の読みと、材料の place への写し（docs/design/delta-review.md の 1.2・1.5）。読めない port は理由を名指す ValueError（入口が
「入力 <名>: …」の頭を付けて intake.json に残す）。"""
import hashlib
import json
import pathlib

import ports
import requestrows

import jsonfile  # lib/
import lens      # lib/
import planmarks  # lib/
import policy    # lib/。PASTE_CAP と貼る本文の切り方

from src import files


def scope(raw) -> dict:
    """port plan（範囲の欄のファイル）。object なら plan_items・ruled_paths・agreed、配列なら項目の並びだけ（合意と裁定が無い）。
    空は修正案の無い run。範囲の欄の無い項目の並び（planmarks.scoped が偽）は修正案の無い run と同じに扱う"""
    path = ports.file(raw)
    if path is None:
        return {"plan_items": [], "ruled_paths": [], "agreed": []}
    doc = ports.json(str(path))
    if isinstance(doc, list):
        doc = {"plan_items": doc}
    if not isinstance(doc, dict):
        raise ValueError(f"範囲の欄のファイル {path} が object でも配列でもない")
    items = doc.get("plan_items", [])
    if not isinstance(items, list):
        raise ValueError("範囲の欄の plan_items が配列でない")
    for i, it in enumerate(items):
        if not isinstance(it, dict) or not isinstance(it.get("item"), int) or isinstance(it.get("item"), bool) or it["item"] < 1:
            raise ValueError(f"範囲の欄の plan_items[{i}] が object でないか、item が 1 以上の整数でない")
    ruled, agreed = doc.get("ruled_paths", []), doc.get("agreed", [])
    if not (isinstance(ruled, list) and all(isinstance(p, str) for p in ruled)):
        raise ValueError("範囲の欄の ruled_paths が字の配列でない")
    if not (isinstance(agreed, list) and all(isinstance(a, dict) for a in agreed)):
        raise ValueError("範囲の欄の agreed が object の配列でない")
    return {"plan_items": items if planmarks.scoped(items) else [], "ruled_paths": ruled, "agreed": agreed}


def fix_reply(raw):
    """port fix_reply（修正役の受け付けられた返答）。null は直す返答が無い"""
    return ports.json(raw, "fix-reply.schema.json")


def permit_paths(raw) -> list:
    """port permits（テストの変更の許しの行 [{path, permit, source}]、またはパスの字の配列）のパス。重ねずに現れた順"""
    out = []
    for i, row in enumerate(ports.json(raw, "permits.schema.json")):
        path = row.get("path") if isinstance(row, dict) else row
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"permits[{i}] からパスの字が取れない")
        if path not in out:
            out.append(path)
    return out


def plan_review(raw):
    """port plan_review（事前審査の返答 {faces, shrink}）。null は事前審査の無い run"""
    return ports.json(raw, "plan-review.schema.json")


def policy_body(path) -> str:
    """方針の文書の本文を貼る形に（policy.PASTE_CAP バイトまで。超えたら先頭を切り、続きの置き場を末尾に書く）。読めなければ ValueError"""
    try:
        return policy._capped(pathlib.Path(path).read_bytes(), str(path))
    except OSError as error:
        raise ValueError(f"方針の文書 {path} が読めない: {error}") from None


def lens_copy(place, raw) -> str:
    """port lens_rows（レンズの控えのファイル）を place の lens.json に写し、形を lens.read で照らす。空は写さない。
    読めない・形が違えば写しを消して訳の字（lens_error）を返す。読めれば空の字"""
    try:
        path = ports.file(raw)
    except ValueError as error:
        return str(error)
    target = pathlib.Path(place) / files.LENS
    target.unlink(missing_ok=True)
    if path is None:
        return ""
    try:
        doc = ports.json(str(path))
        jsonfile.write(target, doc)
        lens.read(place)
    except ValueError as error:
        target.unlink(missing_ok=True)
        return str(error)
    return ""


def request_copy(place, raw) -> str:
    """port request を requestrows で照らし、行が在れば place の request.json に書いてパスを返す。行が 0 なら書かずに空の字"""
    if not requestrows.findings(raw):
        return ""
    return str(jsonfile.write(pathlib.Path(place) / files.REQUEST, ports.json(raw)))


# ---------------------------------------------------------------- 凍結の印（lib/planmarks.py の凍結の印と同じ形）
# 手直しの役が書き換えると許しが黙って広がる写し（テストの変更の許しは 1 本。keep-essence 3）。cut-1.json の files は範囲の照らしで外すパス
SEALED = (files.SCOPE, files.PERMITS, files.cut(1))


def seal(place, names) -> dict:
    """入口が写しを置いた後に、写しのバイトの sha256 を trace.jsonl に 1 行ずつ書き（planmarks.SAVED_OP の行 {round, sha256} に、写しの名
    file を足す）、{写しの名: sha256} を返す。返りは入口の返りの seal になり、受け付けの node へは Archon が with: で渡す（役の手の届かない所）"""
    out = {}
    for name in names:
        out[name] = hashlib.sha256((pathlib.Path(place) / name).read_bytes()).hexdigest()
        files.trace(place, planmarks.SAVED_OP, round=1, file=name, sha256=out[name])
    return out


def verify(place, sealed) -> None:
    """受け付けが写しを使う前に印と照らす。sealed は入口の返りの seal（with: の値）。trace.jsonl の印が写しごとにちょうど 1 本でない・
    写しが読めない・sha256 が sealed とも印とも合わない（入口の後に書き換えた）なら名指す ValueError"""
    rows = []
    try:
        rows = [json.loads(x) for x in (pathlib.Path(place) / files.TRACE).read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError, ValueError):
        pass
    if not isinstance(sealed, dict):
        raise ValueError("入口の返りの凍結の印 seal が受け付けに渡っていない（with: の配線の誤り）")
    for name in SEALED:
        marks = [r for r in rows if isinstance(r, dict) and r.get("op") == planmarks.SAVED_OP and r.get("file") == name]
        if not marks:
            raise ValueError(f"写し {name} の凍結の印が無い（入口が置いていない）")
        if len(marks) > 1:
            raise ValueError(f"写し {name} の凍結の印が重なった（{len(marks)} 本。入口は 1 本だけ書く）")
        if not isinstance(sealed.get(name), str):
            raise ValueError(f"入口の返りの seal に写し {name} の印が無い")
        try:
            raw = (pathlib.Path(place) / name).read_bytes()
        except OSError as error:
            raise ValueError(f"写し {name} が読めない。{planmarks.SAVED_OP} の印が在る: {error}") from None
        digest = hashlib.sha256(raw).hexdigest()
        if digest != sealed[name] or digest != marks[0].get("sha256"):
            raise ValueError(f"写し {name} のバイトの sha256 が入口の印と違う（入口の後に書き換えた）")
