"""1 回目の審査の返答の 2 判定の欄（準拠 compliance・品質 quality。写す元は lib/deltamarks.py。依頼 218）。

承認済みの修正案の項目への準拠と、差分の品質の 2 つの判定を、受け付けが行から決まる語で照らす。
- gaps(reply, items): 欠けと誤りの行（審査の受け付けが拒む）。items は承認済みの修正案の項目（空は準拠が not_applicable）。裁定で外れた項目は
  held を持ち、その項目の落ちた行は拒む（外れた項目を手直しの義務にしない）
- malformed(reply): faces が穴の並びの形でない返答か（真なら受け付けは 2 判定の欄を照らさない）
- split(reply): （2 判定の欄を外した返答の写し, 外した欄）
- save(place, verdicts)・read(place)・fail_rows(verdicts): 控え verdicts.json（今の周の 1 回目の審査の 2 判定）と準拠の落ちた行
語:
- 落ちた行: kind が missing・extra・misunderstood の行。差分の中の所を faces に挙げ、その key を face_key に写して結ぶ。unverifiable の行は
  face_key を空にする
- 結ばれない穴: faces の key のうち、どの落ちた行の face_key にも無い物。在れば品質は fail、無ければ pass
"""
import copy
import pathlib

import ports  # noqa: F401  （lib/ と lib/graphloops/ を sys.path に足す）
from engine.schema import validate_schema  # lib/graphloops/

import jsonfile  # lib/

from src import files

SAVED_OP = "delta_verdicts_saved"   # save が trace.jsonl に書く行 {compliance: 判定, quality: 判定}
COMPLIANCE = ("pass", "fail", "unverifiable", "not_applicable")
QUALITY = ("pass", "fail")
KINDS = ("missing", "extra", "misunderstood", "unverifiable")
FAIL_KINDS = ("missing", "extra", "misunderstood")   # 落ちた行の kind（faces の穴に結ぶ）
MIN_WHY = 20
KEYS = ("compliance", "quality")
_WHY = {"type": "string", "minLength": MIN_WHY}
FIELD_SCHEMA = {
    "compliance": {"type": "object", "additionalProperties": False, "required": ["verdict", "items", "read"], "properties": {
        "verdict": {"type": "string", "enum": list(COMPLIANCE)},
        "items": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["item", "kind", "face_key", "why"],
            "properties": {"item": {"type": "integer", "minimum": 1}, "kind": {"type": "string", "enum": list(KINDS)},
                           "face_key": {"type": "string"}, "why": _WHY}}},
        "read": _WHY}},   # 何を読んで判じたか
    "quality": {"type": "object", "additionalProperties": False, "required": ["verdict", "why"], "properties": {
        "verdict": {"type": "string", "enum": list(QUALITY)}, "why": _WHY}},
}
REJECT = ("差分の審査の返答の 2 判定の欄（準拠 compliance・品質 quality）に欠けか誤りが在る:")


def malformed(reply) -> bool:
    """返答が object でないか、faces が key（文字列）を持つ object の並びでないか。真なら 2 判定の欄を照らさない（穴の key の集合が決まらない）"""
    faces = reply.get("faces") if isinstance(reply, dict) else None
    return not (isinstance(faces, list) and all(isinstance(f, dict) and isinstance(f.get("key"), str) for f in faces))


def _face_keys(reply: dict) -> set:
    faces = reply.get("faces")
    return {f["key"] for f in faces if isinstance(f, dict) and isinstance(f.get("key"), str)} if isinstance(faces, list) else set()


def _expected(rows: list) -> str:
    """準拠の行から決まる判定（落ちた行が 1 行でも在れば fail、無くて unverifiable が在れば unverifiable、行が無ければ pass）"""
    kinds = {r["kind"] for r in rows}
    if kinds & set(FAIL_KINDS):
        return "fail"
    return "unverifiable" if "unverifiable" in kinds else "pass"


def gaps(reply: dict, items: list | None) -> list:
    """2 判定の欄の欠けと誤りの行。空なら通る。型の誤りが在れば型の行だけを返す（中身の照らしは型の通った返答にだけ当てる）"""
    if not isinstance(reply, dict):
        return ["compliance: 返答が object でない（2 判定の欄を読めない）"]
    out = []
    for k in KEYS:
        if k not in reply:
            out.append(f"{k}: 無い（works の欄。型の {k} を見よ）")
        else:
            out += validate_schema(reply[k], FIELD_SCHEMA[k], k)
    if out:
        return out
    comp, qual = reply["compliance"], reply["quality"]
    rows, verdict, n = comp["items"], comp["verdict"], len(items or [])
    faces = _face_keys(reply)
    if not n:
        if verdict != "not_applicable":
            out.append(f"compliance.verdict（{verdict}）: 承認済みの修正案の項目が無い run は not_applicable にせよ")
        if rows:
            out.append("compliance.items: 承認済みの修正案の項目が無い run は空の並びにせよ")
    elif verdict == "not_applicable":
        out.append(f"compliance.verdict（not_applicable）: 承認済みの修正案の項目が {n} 個在る。"
                   "pass・fail・unverifiable のどれかにせよ")
    held = {it.get("item"): it.get("held") for it in items or [] if isinstance(it, dict) and it.get("held")}
    for j, r in enumerate(rows):
        if n and not 1 <= r["item"] <= n:
            out.append(f"compliance.items[{j}].item（{r['item']}）: 承認済みの修正案の項目の番号は 1〜{n}")
        if r["kind"] in FAIL_KINDS and r["item"] in held:
            out.append(f"compliance.items[{j}].item（{r['item']}）: 項目 {r['item']} は裁定で直す義務から外れた（held: "
                       f"{held[r['item']]}）。外れた項目に {r['kind']} の行を書くな（手直しに直させない。最後の承認ノードで人が決める）")
        if r["kind"] in FAIL_KINDS and r["face_key"] not in faces:
            out.append(f"compliance.items[{j}].face_key（{r['face_key']}）: faces の key に無い。"
                       "差分の中の所を faces に挙げて face_key で結べ")
        if r["kind"] not in FAIL_KINDS and r["face_key"]:
            out.append(f"compliance.items[{j}].face_key（{r['face_key']}）: unverifiable の行は穴に結ばない。face_key を空にせよ"
                       "（穴に結ぶのは missing・extra・misunderstood の行だけ）")
    if n and verdict != "not_applicable" and verdict != _expected(rows):
        out.append(f"compliance.verdict（{verdict}）: 行から決まる値は {_expected(rows)}（missing・extra・misunderstood が"
                   "1 行でも在れば fail、無くて unverifiable が在れば unverifiable、行が無ければ pass）")
    untied = sorted(faces - {r["face_key"] for r in rows if r["kind"] in FAIL_KINDS})
    want = "fail" if untied else "pass"
    if qual["verdict"] != want:
        why = (f"準拠の行に結ばれない穴が在る（{'・'.join(untied)}）" if untied else "準拠の行に結ばれない穴が無い")
        out.append(f"quality.verdict（{qual['verdict']}）: {why}ので {want} にせよ")
    return out


def split(reply):
    """（2 判定の欄を外した返答の写し, 外した欄 {compliance, quality}）。渡した返答は変えない。object でない返答はそのままの写しと空"""
    out = copy.deepcopy(reply)
    if not isinstance(out, dict):
        return out, {}
    return out, {k: out.pop(k) for k in KEYS if k in out}


def save(place, verdicts: dict) -> None:
    """place の verdicts.json を {"round": 1, **verdicts} で置き換え、trace.jsonl に SAVED_OP の行を足す"""
    jsonfile.write(pathlib.Path(place) / files.VERDICTS, {"round": 1, **verdicts})
    files.trace(place, SAVED_OP, compliance=verdicts["compliance"]["verdict"], quality=verdicts["quality"]["verdict"])


def read(place) -> dict | None:
    doc = jsonfile.read_or(pathlib.Path(place) / files.VERDICTS)
    return doc if isinstance(doc, dict) and doc.get("round") == 1 else None


def fail_rows(verdicts: dict | None) -> list:
    """控えの準拠の落ちた行（kind が missing・extra・misunderstood）。控えが無い・形が違えば空"""
    comp = verdicts.get("compliance") if isinstance(verdicts, dict) else None
    rows = comp.get("items") if isinstance(comp, dict) else None
    return [r for r in rows if isinstance(r, dict) and r.get("kind") in FAIL_KINDS] if isinstance(rows, list) else []
