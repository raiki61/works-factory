"""前提の実測（graphloops の節 p0.premises）の部品。判定のブロックの受け付け（lib/judge_accept の check_premises）が読む。実行基盤を知らない関数だけを出す。

- PREMISES_FILE: 受け付けた実測役の返答 {"constraints": [...]} のファイルの名
- PREMISES_REQUEST_FILE: 型を確かめた依頼の行の控えの名（collect が読む）
- claims(items): 依頼の行のうち measured（依頼者が測ったと書いた値）を持つ物の {where, measured}
- collect(board): 出口（置き場の premises.json から。v1 の欄 constraints_file・constraints_summary に数を足した物）

受け付け（作業ツリー → 依頼の実測の測り直し → 写した rules の measured_needs_output）は lib/judge_accept.check_premises に在る。
"""
import json
import pathlib
import sys

sys.dont_write_bytecode = True   # 下で import する写しの engine の分（accept.py と同じ。この物自身の分は呼び手が止める）

CORE = pathlib.Path(__file__).resolve().parent
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

PREMISES_FILE = "premises.json"                     # 受け付けた実測役の返答 {"constraints": [...]}

PREMISES_REQUEST_FILE = "premises-request.json"     # intake が型を確かめた依頼の行（JSON の配列）
NONE_SUMMARY = "（測る数値・事実の主張は依頼に無かった。制約 0 件）"


class Broken(Exception):
    """盤面の premises.json が無い・読めない・形が崩れている（collect は終了コード 1）"""


def claims(items: list) -> list:
    """依頼の行のうち measured（依頼者が測ったと書いた値）を持つ物の {where, measured}。実測役はこの where を text にそのまま入れて
    測り直す（blk-premises の check_claims が確かめる）"""
    return [{"where": it["where"], "measured": it["measured"]} for it in items or []
            if isinstance(it, dict) and isinstance(it.get("where"), str) and it.get("measured") not in (None, "")]


def request_items(board: pathlib.Path) -> list | None:
    """intake が控えた依頼の行（無い・読めないなら None）"""
    try:
        doc = json.loads((pathlib.Path(board) / PREMISES_REQUEST_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, list) else None


def _covering(where: str, constraints: list) -> list:
    return [c for c in constraints if isinstance(c, dict) and isinstance(c.get("text"), str) and where in c["text"]]


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def collect(board: pathlib.Path) -> dict:
    """前提の実測のブロックの出口。盤面の premises.json（受け付けを通った返答）から
    {ok, premises_file, constraints_file, constraints_summary, constraints, measured, hypotheses, claims, claims_hypothesis, reads_file}。
    constraints・measured・hypotheses は制約の行・kind 実測・kind 仮説の数。claims は依頼の measured の行の数、claims_hypothesis は
    そのうち where を含む制約が仮説だけの数（測り直せなかった依頼の実測）。constraints_file は v1 の欄（premises_file と同じ）、
    constraints_summary は判定役に貼る 1 行 1 制約の要約（measured_output は載せない）。reads_file はまだ無い（空）。
    premises.json が無い・読めない・形が崩れていれば Broken"""
    path = pathlib.Path(board) / PREMISES_FILE
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Broken(f"共有ボードの {PREMISES_FILE} が読めない（{path}: {type(e).__name__}: {e}）——受け付けを通った前提の実測が無い") from None
    cs = doc.get("constraints") if isinstance(doc, dict) else None
    if not isinstance(cs, list) or not all(isinstance(c, dict) and all(isinstance(c.get(k), str) for k in ("text", "measured_how", "kind"))
                                           for c in cs):
        raise Broken(f"共有ボードの {PREMISES_FILE} の形が崩れている（constraints[].text・measured_how・kind が要る）: {path}")
    asked = claims(request_items(board) or [])
    hyp = [c for c in asked if not any(x["kind"] == "実測" for x in _covering(c["where"], cs))]
    summary = "\n".join(f"- [{c['kind']}] {_one_line(c['text'])}（測り方: {_one_line(c['measured_how'])}）" for c in cs)
    return {"ok": True, "premises_file": str(path), "constraints_file": str(path), "constraints_summary": summary or NONE_SUMMARY,
            "constraints": len(cs), "measured": sum(c["kind"] == "実測" for c in cs),
            "hypotheses": sum(c["kind"] == "仮説" for c in cs), "claims": len(asked), "claims_hypothesis": len(hyp),
            "reads_file": ""}

