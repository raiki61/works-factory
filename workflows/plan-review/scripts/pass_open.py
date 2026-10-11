"""差し込みの頭（boardview.open_pass）: 入力の指し札の先を run の置き場の plan-review/ に写し、見え方の材料を置き、独立設計を
回すかと事前審査を木にするかを返す。落ちない（誤りは ok: false と訳で返し、後の節は返す節の偽の結末に進む）"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402

sys.path.append(str(boundary.lib_root()))
import boardview  # noqa: E402

YAML = Path(__file__).resolve().parents[1] / "works-factory-plan-review.yaml"


def pointed(text: str):
    """指し札の JSON の字を置き場の中のパスに（null は None）"""
    value = json.loads(text)
    return None if value is None else boundary.resolve(value)


def main() -> dict:
    folder = Path(os.environ["ARTIFACTS_DIR"]) / boardview.FOLDER
    try:
        got = boardview.open_pass(
            folder, cwd=Path.cwd(), judgment=pointed(os.environ["INPUTS_JUDGMENT"]),
            purpose=pointed(os.environ["INPUTS_PURPOSE"]), plan=pointed(os.environ["INPUTS_PLAN"]),
            structure=pointed(os.environ["INPUTS_STRUCTURE"]), ripple=pointed(os.environ["INPUTS_RIPPLE"]),
            world=pointed(os.environ["INPUTS_WORLD"]), start=pointed(os.environ["INPUTS_START"]),
            answers=json.loads(os.environ["INPUTS_ANSWERS"]), ruling=json.loads(os.environ["INPUTS_RULING"]) or [],
            yaml_text=YAML.read_text(encoding="utf-8"))
    except Exception as e:
        why = f"{type(e).__name__}: {e}"
        boardview.open_failed(folder, why)
        return {"ok": False, "r2_go": False, "tree": False, "k": 0, "form": "", "reason": why}
    return {"ok": True, **got, "reason": ""}


boundary.returns(main())
