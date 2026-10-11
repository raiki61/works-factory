"""ブロックの script が Archon と出入りする唯一の口（workflows/AGENTS.md の E2・E4）。

止めた Archon（docs/design.md の「語」）が script の節に渡す物（packages/workflows/src/exec-environment.ts・schemas/dag-node.ts の inputEnvKey）:
入力は環境変数 INPUTS_<UPPER_SNAKE>、run の id は WORKFLOW_ID、run の成果物の置き場は ARTIFACTS_DIR。
入力は口を通さず、script が os.environ["INPUTS_<名>"] を字のまま読む（工程が inputs: を宣言していると、Archon は読み込みで script の字を走査して宣言の無い入力を拒むので、組み立てた名はその走査に見えない）。
指し札の決まりは Archon の artifact-pointer.ts に合わせる。返りに入った指し札の先（在る・空でない・置き場の中）は Archon が節の終わりに照らすので、
ここでは札の形を組むだけにする。
"""
import json
import os
import re
from pathlib import Path

POINTER_TYPE = "archon_artifact"


def returns(obj: dict) -> None:
    """節の返りを JSON 1 つで標準出力に書く。型は Archon が節の output_format で照らす。
    Archon は JSON.parse で読むので、NaN・Infinity は ValueError で止める"""
    print(json.dumps(obj, ensure_ascii=False, allow_nan=False), flush=True)


def pointer(rel: str) -> dict:
    """この run の置き場からの相対パス rel を指す札を作る"""
    return {"type": POINTER_TYPE, "run_id": _run_id(), "path": rel}


def resolve(ptr: dict) -> Path:
    """この run の指し札を、置き場の中のパスに戻す"""
    if ptr.get("type") != POINTER_TYPE:
        raise ValueError(f"{POINTER_TYPE} の指し札でない: {ptr!r}")
    if ptr.get("run_id") != _run_id():
        raise ValueError(f"ほかの run の指し札: {ptr.get('run_id')}（この run は {_run_id()}）")
    return _inside_artifacts(ptr.get("path", ""))


def lib_root() -> Path:
    """lib/ の置き場。Archon が run の始めに写し取った所から走る時の決め方は docs/design.md の U5（段 1 で決める）。段 0 はリポジトリの中"""
    return Path(__file__).resolve().parents[2] / "lib"


def _run_id() -> str:
    return os.environ["WORKFLOW_ID"]


def _inside_artifacts(rel: str) -> Path:
    # Archon は / と \ の両方で区切って .. を拒む。末尾の / は pathlib が落とすが、Archon の stat は ENOTDIR で拒む
    if (
        not rel
        or "\0" in rel
        or rel.startswith(("/", "\\"))
        or rel.endswith("/")
        or ".." in re.split(r"[\\/]", rel)
    ):
        raise ValueError(f"指し札のパスは run の置き場からの相対で、.. を持たず、/ で終わらない: {rel}")
    return Path(os.environ["ARTIFACTS_DIR"]) / rel
