# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""差し込みの頭（boardview.open_pass）: 入力の指し札の先を run の置き場の plan-review/ に写し、見え方の材料を置き、独立設計を
回すかと事前審査を木にするか（始めの記録の review_tree の名指し、無ければ入力 head_depth の頭の深さの段の足し。形 review の時だけ
段の足しを引く）を返す。役の節の型（output_format）はブロックの YAML から読んで渡す。入力 mode が design（直す物が
無い周）は修正案を読まず、独立設計の材料だけを置いて形 design を返す（boardview.open_design。事前審査の輪は飛ぶ）。
修正案の役の返答 fix_plan は plan・structure・ripple と同じく要る入力で、null なら入力の名を挙げて落ちる（空の案で事前審査を回さない）。
落ちない: 始めに前の差し込みの材料 open.json を消し（後の節が前の差し込みの結末を今回の物として読まない）、境の口と lib の import
から先の誤りは全部捕まえて、落ちた訳 open-error.txt を置き ok: false と訳を返す（後の節は返す節の偽の結末に進む）"""
import json
import os
import re
import sys
from pathlib import Path

YAML = Path(__file__).resolve().parents[1] / "works-factory-plan-review.yaml"
# boardview.FOLDER・OPEN_FILE・OPEN_ERROR（境の口と lib を読めない時にも消して書けるよう字で持つ。試験が一致を縛る）
FOLDER = "plan-review"
OPEN_FILE = "open.json"
OPEN_ERROR = "open-error.txt"


def node_schema(yaml_text: str, node_id: str) -> dict:
    """ブロックの YAML の節 node_id の output_format。script は外のパッケージ無しで走るので、役の節の output_format は JSON の形
    （YAML の flow の書き方。JSON は YAML の部分集合）で書き、ここは節の行の後の最初の output_format: の値を JSON として読む（値の頭の
    YAML の錨 &<名> は飛ばす）"""
    head = re.search(rf"^\s*- id: {re.escape(node_id)}\s*$", yaml_text, re.M)
    if head is None:
        raise ValueError(f"YAML にノード {node_id} が無い")
    key = re.compile(r"^\s*output_format:\s*(?:&[\w-]+\s+)?", re.M).search(yaml_text, head.end())
    nxt = re.compile(r"^\s*- id: ", re.M).search(yaml_text, head.end())
    if key is None or (nxt is not None and nxt.start() < key.start()):
        raise ValueError(f"ノード {node_id} に output_format が無い")
    try:
        got, _ = json.JSONDecoder().raw_decode(yaml_text, key.end())
    except ValueError as e:
        raise ValueError(f"ノード {node_id} の output_format が JSON の形でない: {e}") from None
    if not isinstance(got, dict):
        raise ValueError(f"ノード {node_id} の output_format が object でない")
    return got


def opened() -> tuple:
    """（境の口, 返り）"""
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
    import boundary
    sys.path.append(str(boundary.lib_root()))
    import boardview

    text = YAML.read_text(encoding="utf-8")
    folder = Path(os.environ["ARTIFACTS_DIR"]) / boardview.FOLDER
    unread = []

    def port(name: str, raw):
        """判定の出力の欄を受ける入力の先（null は None。先が無ければ訳を unread に積み、null と同じに読む）"""
        path = boundary.pointed(raw)
        if path is not None and not path.is_file():
            unread.append(f"入力 {name} の先が無い（{path}）——無いとして読んだ")
            return None
        return path

    shared = {"judgment": boundary.needed(os.environ["INPUTS_JUDGMENT"], "judgment"),
              "purpose": boundary.needed(os.environ["INPUTS_PURPOSE"], "purpose"),
              "world": boundary.pointed(os.environ["INPUTS_WORLD"]), "start": boundary.pointed(os.environ["INPUTS_START"]),
              "answers": boundary.parsed(os.environ["INPUTS_ANSWERS"]), "design_schema": node_schema(text, "r2-design"),
              "purpose_review": boundary.pointed(os.environ.get("INPUTS_PURPOSE_REVIEW", "")),
              "decisions": port("decisions", os.environ.get("INPUTS_DECISIONS", "")), "unread": unread}
    if os.environ.get("INPUTS_MODE", "") == boardview.DESIGN_FORM:   # 直す物が無い周: 修正案を読まずに独立設計だけ
        got = boardview.open_design(folder, cwd=Path.cwd(), **shared)
        return boundary, {"ok": True, **got, "reason": ""}
    fix_plan = boundary.needed(os.environ["INPUTS_FIX_PLAN"], "fix_plan")
    if not fix_plan.is_file():
        raise ValueError(f"入力 fix_plan の先が無い（{fix_plan}）")
    got = boardview.open_pass(
        folder, cwd=Path.cwd(), **shared, plan=boundary.needed(os.environ["INPUTS_PLAN"], "plan"), fix_plan=fix_plan,
        plan_rejects=boundary.items(os.environ["INPUTS_PLAN_REJECTS"]),
        structure=boundary.needed(os.environ["INPUTS_STRUCTURE"], "structure"),
        ripple=boundary.needed(os.environ["INPUTS_RIPPLE"], "ripple"),
        ruling=boundary.parsed(os.environ["INPUTS_RULING"]) or [], conflicts=boundary.pointed(os.environ["INPUTS_CONFLICTS"]),
        gate_answers=boundary.parsed(os.environ["INPUTS_GATE_ANSWERS"]), round_limit=boundary.parsed(os.environ["INPUTS_ROUND_LIMIT"]),
        review_schema=node_schema(text, "plan-review"), head_depth=os.environ.get("INPUTS_HEAD_DEPTH", "").strip(),
        materials=port("materials", os.environ.get("INPUTS_MATERIALS", "")),
        pr_excluded=port("pr_excluded", os.environ.get("INPUTS_PR_EXCLUDED", "")),
        purpose_means=port("purpose_means", os.environ.get("INPUTS_PURPOSE_MEANS", "")))
    return boundary, {"ok": True, **got, "reason": ""}


def main() -> int:
    folder = Path(os.environ.get("ARTIFACTS_DIR", ".")) / FOLDER
    try:
        (folder / OPEN_FILE).unlink(missing_ok=True)
        (folder / OPEN_ERROR).unlink(missing_ok=True)
        boundary, out = opened()
        boundary.returns(out)
    except Exception as e:
        why = f"{type(e).__name__}: {' '.join(str(e).split())}"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / OPEN_ERROR).write_text(why, encoding="utf-8")
        except OSError:
            pass
        print(json.dumps({"ok": False, "r2_go": False, "tree": False, "k": 0, "form": "", "reason": why}, ensure_ascii=False,
                         allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
