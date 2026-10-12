"""ブロックの script が Archon と出入りする唯一の口（workflows/AGENTS.md の E2・E4）。

止めた Archon（docs/design.md の「語」）が script の節に渡す物（packages/workflows/src/exec-environment.ts・schemas/dag-node.ts の inputEnvKey）:
入力は環境変数 INPUTS_<UPPER_SNAKE>、run の id は WORKFLOW_ID、run の成果物の置き場は ARTIFACTS_DIR。
入力は口を通さず、script が os.environ["INPUTS_<名>"] を字のまま読む（工程が inputs: を宣言していると、Archon は読み込みで script の字を走査して宣言の無い入力を拒むので、組み立てた名はその走査に見えない）。
指し札の決まりは Archon の artifact-pointer.ts に合わせる。返りに入った指し札の先（在る・空でない・置き場の中）は Archon が節の終わりに照らすので、
ここでは札の形を組むだけにする。

落ちない script の口（線の script が使う）:
- run(compute, fallback): script は節として落ちない。落ちると、それを `{from, if_skipped}` で受ける節が読めず
  （止めた Archon の dag-executor.ts の resolveBindingDirective は落ちた節を if_skipped に落とさない）、報告まで届かないので、
  中の例外は fallback(理由) の返りにして返す
- guarded_imports(): script の lib/ の import を囲む（lib/ の置き場を sys.path に足してから読む）。import が落ちた訳は run が
  fallback の返りにする（lib/ の誤りでも節は落ちない）
- LINE_SCRIPT: fallback の返りの止めの理由。lib/stopby.py の LINE_SCRIPT の写し（lib を読めない時の fallback も引くので lib から
  読めない。lib/tests/test_stopby.py が突き合わせる）
- value・text・flag・items・field: Archon が渡した入力の字を値に戻す（埋め skip_value の上の読み方）
"""
import contextlib
import json
import os
import re
import sys
from pathlib import Path

import skip_value

POINTER_TYPE = "archon_artifact"
LINE_SCRIPT = "works:line-script"
TEXT_FIELDS = ("mode", "red_cause", "stop_reason", "objection", "rejudge_verdict", "hash", "reason", "unread")   # JSON として読まない欄

_import_error = None

# Archon が script の節に立てる変数（exec-environment.ts の buildExecNodeEnvironment。tests/shared/test_archon_contract.py が照らす）。
# 頭の一致は ARCHON_・INPUTS_ だけで、ほかは名の完全一致（CONTEXT などを頭で落とすと利用者の変数まで落とす）
RUNNER_PREFIXES = ("ARCHON_", "INPUTS_")
RUNNER_NAMES = frozenset({
    "ARTIFACTS_DIR", "STATE_DIR", "LOG_DIR", "ADOPTED_RUN_DIR", "WORKFLOW_ID", "BASE_BRANCH", "USER_MESSAGE", "ARGUMENTS",
    "LOOP_USER_INPUT", "LOOP_PREV_OUTPUT", "REJECTION_REASON", "CONTEXT", "EXTERNAL_CONTEXT", "ISSUE_CONTEXT", "TYPED_ARTIFACTS_FILE",
})


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
    """lib/ の置き場。入口が環境変数 WORKS_FACTORY_ROOT にリポジトリの根を渡していればその lib/、無ければこのファイルから辿った lib/。
    Archon は run の始めに工程のフォルダを写し取り、script はその写しから走るので、run の中ではこのファイルから辿っても届かない（docs/design.md の U5）"""
    root = os.environ.get("WORKS_FACTORY_ROOT")
    return Path(root) / "lib" if root else Path(__file__).resolve().parents[2] / "lib"


@contextlib.contextmanager
def guarded_imports():
    """lib/ の import を囲む。落ちたら訳を控え、後の run が compute を呼ばずに fallback の返りにする"""
    global _import_error
    lib = str(lib_root())
    if lib not in sys.path:
        sys.path.append(lib)
    try:
        yield
    except Exception as error:   # script は落ちない（上の docstring）
        _import_error = error


def run(compute, fallback) -> None:
    """compute() の返りを節の返りにする。lib/ の import が落ちていた時と compute の例外は fallback(理由の 1 行) の返りにする"""
    try:
        if _import_error is not None:
            raise _import_error
        out = compute()
    except Exception as error:   # script は落ちない（上の docstring）
        reason = " ".join(f"{type(error).__name__}: {error}".split())
        print(reason, file=sys.stderr)
        out = fallback(reason)
    returns(out)


def value(raw):
    return skip_value.value(raw)


def field(key: str, raw):
    """ブロックの返りの 1 欄。字の欄（TEXT_FIELDS）は字のまま、ほかは JSON として読む。飛ばされた節（null）は None"""
    return skip_value.text(raw) if key in TEXT_FIELDS else skip_value.value(raw)


def text(raw) -> str:
    """字の欄。飛ばされた節（null）と無い入力は空の字"""
    return skip_value.text(raw) or ""


def flag(raw) -> bool:
    return skip_value.value(raw) is True


def items(raw) -> list:
    got = skip_value.value(raw)
    return got if isinstance(got, list) else []


def drop_runner_env() -> None:
    """Archon の変数を落とす。入力と置き場を読み終えた後、対象のテストを走らせる lib/ の関数を呼ぶ前に呼ぶ（lib/ は環境を os.environ
    から継いで子を起こす。節ごと・子の run ごとに値が違うので、残すと同じ run の中の試験の結果の使い回しの指紋も割れる）"""
    for name in [n for n in os.environ if n.startswith(RUNNER_PREFIXES) or n in RUNNER_NAMES]:
        del os.environ[name]


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
