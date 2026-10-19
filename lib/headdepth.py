"""run の頭の深さ（issue #441。docs/design.md の「深さの段の表」）の段の語と控えの読み（README 9.3 の KEEP。integration.md 4.5-6・4.3-5）。
使うのは head-depth と line。

run 全体の深さの段（軽量・標準・重厚）の語と並び HEADS はここ 1 か所（前は lib/depth.py。depth は line へ移る）。依頼の行ごとの
未知の種類 → 段の表・事実の測り・機械の止め・役の材料・返答の照らし（前の facts・gate・brief・check・tier_of・UNKNOWNS）は
head-depth の src/steps.py、種類ごとの受け手への指示の文（前の ASKS・section）は読み手の diagnose・plan の md、報告の冒頭 2 の行
（前の report_line）は line の src/ に在る。

- LIGHT・STANDARD・HEAVY・HEADS: 段の語と、軽い順の並び
- RECORD: 判定の置き場の控えの名（字をここに直に書く。前は judgebeside.DEPTH_FILE）
- record(depth, why, *, items, facts_doc, groups): 控えの形。groups は役の群の選びを launchgroups.choices で照らした行（既定のまま・
  拒んだ時は空）。この run では効かず記録だけ
- write(jdir, doc)・read(jdir): 判定の置き場の控え RECORD の読み書き。read_file(path): 控えのファイルの読み（判定の外の読み手は
  判定の出力の欄 depth_record のパスで読む）。どちらの読みも無い・読めない時に標準の控え
- cited_files(doc): 控えの items の where が指すファイル（cite.CITE で読む）。修正の後に差分が引用の外に出たかを数える口
- groups_lines(doc): 報告の ## 模型 のセクションに並べる群ごとの選びの行。選びか既定への戻しの在る群だけを 1 群 1 行で描き、
  無ければ NO_CHOICE の 1 行。記録だけで走りの模型は起動の時の口で替える 1 行（RUN_SWITCH）を添える
"""
import json
import pathlib
import sys

sys.dont_write_bytecode = True   # 下の import が pack の中に __pycache__ を作らないように

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import cite  # noqa: E402
import jsonfile  # noqa: E402
import oneline  # noqa: E402

LIGHT = "軽量"
STANDARD = "標準"
HEAVY = "重厚"
HEADS = (LIGHT, STANDARD, HEAVY)
RECORD = "depth-head.json"
NO_RECORD = "run の頭の深さの控えが無い"


def record(depth_word: str, why: str, *, items=(), facts_doc=None, groups=()) -> dict:
    return {"depth": depth_word, "why": why, "items": list(items), "facts": facts_doc or {}, "groups": list(groups)}


def write(jdir, doc: dict) -> pathlib.Path:
    return jsonfile.write(pathlib.Path(jdir) / RECORD, doc, parents=True)


def read_file(path) -> dict:
    try:
        doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return record(STANDARD, NO_RECORD)
    if not isinstance(doc, dict) or doc.get("depth") not in HEADS:
        return record(STANDARD, NO_RECORD)
    return doc


def read(jdir) -> dict:
    return read_file(pathlib.Path(jdir) / RECORD)


def cited_files(doc) -> list:
    """頭の深さの控え doc（read の返り）の items の where が指すファイル（cite.CITE の `<パス>:<行>` のパスか、行の無い `<パス>`。
    現れた順・重なりは 1 つ）。where の無い行・items の無い控え（標準・名指し・機械の止め）は何も足さない。修正の後に、差分が
    引用の外に出たかを数える口（depth.outside_cited の cited）"""
    out = []
    for it in (doc.get("items") if isinstance(doc, dict) else None) or []:
        where = str(it.get("where") or "").strip() if isinstance(it, dict) else ""
        m = cite.CITE.match(where)
        path = m["path"] if m else where
        if path and path not in out:
            out.append(path)
    return out



NO_CHOICE = "役の選びは無い（呼ぶ人の名指しと層の付け替えの後の値は下のノードごとの行）"
RUN_SWITCH = ("役の選びは記録だけで、この run にも子の run にも次の周にも効かない。走りの模型を替えるには、run を起こす時に "
              "--model @wf-<群>=<模型> を渡す（effort も替えるなら <模型> の代わりに effort を持つ別名 @<名> を書く）。")


def _group_line(row: dict) -> str:
    group = oneline.one_line(row.get("group") or "") or "（群の名が無い）"
    why = oneline.one_line(row.get("fallback") or row.get("why") or "") or "訳の記録が無い"
    pair = row.get("default") if isinstance(row.get("default"), dict) else {}
    if not pair.get("model"):
        return f"{group}: 表に無い群を既定に戻した（訳: {why}）"
    default = "・".join(filter(None, [pair["model"], pair.get("effort")]))
    if row.get("fallback"):
        return f"{group}: 役の選びを既定 {default} に戻した（訳: {why}）"
    return f"{group}: 既定 {default} → 役の選び {row.get('model')}・{row.get('effort')}（{row.get('direction')}。訳: {why}）"


def groups_lines(doc) -> list:
    """報告の ## 模型 のセクションに並べる、役の選びの行。控え doc（read が読んだ物。控えの無い run は None）の groups の行ごとに 1 行
    （1 群 1 行。選ばれていない群の行は出さない）: 選びは既定の (model, effort)・役の選び・向き・訳、既定に戻した行は戻した訳。
    選びも戻した行も無い・控えの無い run は NO_CHOICE の 1 行。どちらの形も最後に RUN_SWITCH の 1 行（記録だけであることと、
    走りの模型を替える起動の時の口）を添える。
    既定の値は控えの行の default（控えた時の表の既定）を使い、表を後で替えても控えと食い違わない"""
    groups = doc.get("groups") if isinstance(doc, dict) else None
    rows = [_group_line(r) for r in groups if isinstance(r, dict)] if isinstance(groups, list) else []
    return [*(rows or [NO_CHOICE]), RUN_SWITCH]
