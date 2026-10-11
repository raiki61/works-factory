"""ブロックの script が Archon と出入りする唯一の口（workflows/AGENTS.md の E2・E4）。

Archon v0.11.1 が script の節に渡す物（packages/workflows/src/exec-environment.ts・schemas/dag-node.ts の inputEnvKey）:
入力は環境変数 INPUTS_<UPPER_SNAKE>、run の id は WORKFLOW_ID、run の成果物の置き場は ARTIFACTS_DIR。
指し札の決まりは Archon の artifact-pointer.ts に合わせる。Archon は返りに入った指し札を節の終わりに照らすので、
ここではそれより先に、名前つきの誤りで止める。
"""
import json
import os
import re
from pathlib import Path

POINTER_TYPE = "archon_artifact"


def inputs(names: list[str]) -> dict[str, str]:
    """節の入力を名で読む。足りない名は KeyError に名を入れる"""
    values = {}
    for name in names:
        key = "INPUTS_" + name.replace("-", "_").upper()
        if key not in os.environ:
            raise KeyError(f"入力 {name} が無い（環境変数 {key}）")
        values[name] = os.environ[key]
    return values


def returns(obj: dict) -> None:
    """節の返りを JSON 1 つで標準出力に書く。型は Archon が節の output_format で照らす"""
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def pointer(rel: str) -> dict:
    """この run の置き場の中の、在って空でない普通のファイルを指す札を作る"""
    path = _inside_artifacts(rel)
    if not path.is_file():
        raise ValueError(f"指し札の先が普通のファイルでない（無いかフォルダ）: {rel}")
    if path.stat().st_size == 0:
        raise ValueError(f"指し札の先が空のファイル: {rel}")
    return {"type": POINTER_TYPE, "run_id": _run_id(), "path": rel}


def resolve(ptr: dict) -> Path:
    """この run の指し札を、置き場の中のパスに戻す"""
    if ptr.get("type") != POINTER_TYPE:
        raise ValueError(f"{POINTER_TYPE} の指し札でない: {ptr!r}")
    if ptr.get("run_id") != _run_id():
        raise ValueError(f"ほかの run の指し札: {ptr.get('run_id')}（この run は {_run_id()}）")
    return _inside_artifacts(ptr.get("path", ""))


def lib_root() -> Path:
    """lib/ の置き場。Archon の家に置いた時の決め方は docs/design.md の U5（段 1 で決める）。段 0 はリポジトリの中"""
    return Path(__file__).resolve().parents[2] / "lib"


def _run_id() -> str:
    return os.environ["WORKFLOW_ID"]


def _inside_artifacts(rel: str) -> Path:
    # Archon は / と \ の両方で区切って .. を拒む
    if not rel or "\0" in rel or rel.startswith(("/", "\\")) or ".." in re.split(r"[\\/]", rel):
        raise ValueError(f"指し札のパスは run の置き場からの相対で、.. を持たない: {rel}")
    return Path(os.environ["ARTIFACTS_DIR"]) / rel
