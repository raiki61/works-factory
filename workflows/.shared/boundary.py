"""ブロックの script が Archon と出入りする唯一の口（workflows/AGENTS.md の E2・E4）。

止めた Archon（docs/design.md の「語」）が script の節に渡す物（packages/workflows/src/exec-environment.ts・schemas/dag-node.ts の inputEnvKey）:
入力は環境変数 INPUTS_<UPPER_SNAKE>、run の id は WORKFLOW_ID、run の成果物の置き場は ARTIFACTS_DIR。
入力は口を通さず、script が os.environ["INPUTS_<名>"] を字のまま読む（工程が inputs: を宣言していると、Archon は読み込みで script の字を走査して宣言の無い入力を拒むので、組み立てた名はその走査に見えない）。
外れは prev_reason の 1 つだけ（輪の頭の節が自分の with: の reason を返すだけの形を、ブロックごとに写さない）。
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
- parsed・value・text・flag・items・picked・pointed・needed: Archon が渡した入力の字を値に戻す（埋め skip_value の上の読み方）。script は入力の字を
  自分で json.loads しない（宣言した null の欄は空の字で届く。tests/workflows/test_input_reads.py が縛る）
- as_flag・as_text・as_items: picked の欄のように型を保って届いた値を、flag・text・items と同じ倒し方で読む

Archon に向いた事実（lib/ は Archon の名を持たない（lib/AGENTS.md の E3）ので、script がここから引いて lib/ へ引数で渡す）:
- RUNTIME_COPY・RUNTIME_COPY_PREFIX・RUNTIME_COPY_DIRS・SKIP: Archon が run の作業ツリーに写す工程の置き場。修正の変更でないので、
  差分・後始末・波及で数えない・消さない（パスの頭の字と、フォルダの名の組の形と、パスの頭の組の形）
- include_name(block)・place(block)・work_tree(): サブグラフ block の script のこの run の置き場（include ごとに分ける）と、
  run の作業ツリーの根
- shared_cache(): run をまたぐ控えの根
- RUNNER_PREFIXES・RUNNER_NAMES・drop_runner_env(): Archon が script の節に立てる変数
- line_place()・USER_ENV_RAN_DIR・aim_user_env(): メイングラフの run の置き場（fix の組の子の run からも辿る）と、対象のコマンドを利用者の
  HOME・XDG に戻して起こした印をそこへ置かせる変数（lib/userenv.py の RAN_DIR_ENV。drop_runner_env が先に立てる）
- prev_reason(): 輪の頭の節の返り（前の周の受け付けの理由）
- transcript(): この run の記録の行（Archon の logger が LOG_DIR に書く JSONL。節ごとの費用と落ちを読む）
"""
import contextlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import skip_value

POINTER_TYPE = "archon_artifact"
LINE_SCRIPT = "works:line-script"

_import_error = None

RUNTIME_COPY = ".archon"
RUNTIME_COPY_PREFIX = f"{RUNTIME_COPY}/"
RUNTIME_COPY_DIRS = ((RUNTIME_COPY,),)
SKIP = (RUNTIME_COPY_PREFIX,)
SHARED_CACHE_ENV = "STATE_DIR"
SHARED_CACHE = "works-factory"

# Archon が script の節に立てる変数（exec-environment.ts の buildExecNodeEnvironment。tests/shared/test_archon_contract.py が照らす）。
# 頭の一致は ARCHON_・INPUTS_ だけで、ほかは名の完全一致（CONTEXT などを頭で落とすと利用者の変数まで落とす）
RUNNER_PREFIXES = ("ARCHON_", "INPUTS_")
# lib/userenv.py の RAN_DIR_ENV の写し（境の口は lib/ を sys.path に足す前に読まれる。tests/shared/test_boundary.py が突き合わせる）
USER_ENV_RAN_DIR = "WORKS_FACTORY_USER_ENV_RAN_DIR"
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
    require_pointer(ptr)
    if ptr.get("run_id") != _run_id():
        raise ValueError(f"ほかの run のポインタ: {ptr.get('run_id')}（この run は {_run_id()}）")
    return inside_artifacts(ptr.get("path", ""))


def require_pointer(ptr) -> None:
    """ptr が指し札 {type: POINTER_TYPE, ...} の形でなければ ValueError"""
    if not isinstance(ptr, dict) or ptr.get("type") != POINTER_TYPE:
        raise ValueError(f"{POINTER_TYPE} のポインタでない: {ptr!r}")


def inside_artifacts(rel, root=None) -> Path:
    """run の置き場 root（無ければこの run の ARTIFACTS_DIR）からの相対パス rel を、Archon が通す形に限って置き場の中のパスにする"""
    # Archon は / と \ の両方で区切って .. を拒む。末尾の / は pathlib が落とすが、Archon の stat は ENOTDIR で拒む
    if (
        not isinstance(rel, str)
        or not rel
        or "\0" in rel
        or rel.startswith(("/", "\\"))
        or rel.endswith("/")
        or ".." in re.split(r"[\\/]", rel)
    ):
        raise ValueError(f"ポインタのパスは run の置き場からの相対で、.. を持たず、/ で終わらない: {rel!r}")
    return Path(root if root is not None else os.environ["ARTIFACTS_DIR"]) / rel


def rel_of(path) -> str:
    """置き場の中のパスを、この run の置き場からの相対の字に（resolve の逆）"""
    return Path(path).relative_to(Path(os.environ["ARTIFACTS_DIR"])).as_posix()


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


def parsed(raw):
    """入力の JSON の値。null・空の字・無い入力は None。JSON でなければ ValueError"""
    return skip_value.parsed(raw)


def value(raw):
    """入力の JSON の値。null・空の字・無い入力は None。JSON でなければ字のまま"""
    return skip_value.value(raw)


def pointed(raw) -> Path | None:
    """指し札の入力の字の先の、置き場の中のパス。null・空の字・無い入力は None。札でなければ ValueError"""
    ptr = parsed(raw)
    return None if ptr is None else resolve(ptr)


def needed(raw, name: str) -> Path:
    """必ず在る指し札の入力 name の先のパス。null・空の字・無い入力も ValueError"""
    path = pointed(raw)
    if path is None:
        raise ValueError(f"入力 {name} のポインタが無い（null か空の字）")
    return path


class Picked(dict):
    """picked が返す、宣言した名だけを持つ dict。宣言の外の名は [] でも get でも KeyError にする（打ち違いが黙って None にならない）"""

    def __missing__(self, key):
        raise KeyError(f"宣言の外の名 {key!r}（宣言した名: {', '.join(self)}）")

    def get(self, key):
        return self[key]


def picked(raw, names) -> Picked | None:
    """ブロックの返りまるごとの入力 raw を value で dict に戻し、宣言した名 names だけを持つ Picked にする（欠けた欄は None）。
    飛ばされた節（null・空の字・無い入力）は None。dict でなければ ValueError。返りまるごとを読む口はこれだけで、宣言の外の欄は
    値として script に届かない（names の形は tests/layers/scan.py の E5 が照らす）。ブロックの返りの欄の型は返す節の output_format が
    持つので、字の欄も型つきの dict で届き、字か値かを読み分ける表は要らない"""
    got = value(raw)
    if got is None:
        return None
    if not isinstance(got, dict):
        raise ValueError(f"まるごとの入力が object でない（{type(got).__name__}）: {str(got)[:80]!r}")
    return Picked((name, got.get(name)) for name in names)


def text(raw) -> str:
    """字の欄。飛ばされた節（null）と無い入力は空の字"""
    return skip_value.text(raw) or ""


def flag(raw) -> bool:
    return as_flag(skip_value.value(raw))


def items(raw) -> list:
    return as_items(skip_value.value(raw))


def as_flag(got) -> bool:
    """型を保って届いた値（picked の欄）の真偽。true の外は False"""
    return got is True


def as_text(got) -> str:
    """型を保って届いた値（picked の欄）の字。字の外（飛ばされた欄の None など）は空の字"""
    return got if isinstance(got, str) else ""


def as_items(got) -> list:
    """型を保って届いた値（picked の欄）の配列。配列の外は空。配列は写しを作らずに同じ list を返す"""
    return got if isinstance(got, list) else []


def line_place() -> Path | None:
    """メイングラフの run の成果物の置き場。fix の組の子の run は入力 out_dir（親の置き場の <メイングラフの run の置き場>/fix/<include の名>/groups）から
    3 つ上、ほか（out_dir が空）は自分の ARTIFACTS_DIR。out_dir の形が違う・ARTIFACTS_DIR が無ければ None"""
    out_dir = os.environ.get("INPUTS_OUT_DIR", "").strip()
    if not out_dir:
        artifacts = os.environ.get("ARTIFACTS_DIR")
        return Path(artifacts) if artifacts else None
    path = Path(out_dir)
    if path.name != "groups" or len(path.parents) < 3 or path.parents[1].name != "fix":
        return None
    return path.parents[2]


def aim_user_env() -> None:
    """対象のコマンドを利用者の HOME・XDG に戻した印を、メイングラフの run の置き場（line_place）に置かせる（USER_ENV_RAN_DIR）。置き場が
    引けなければ古い値も外す（利用者が明示した run では lib/userenv.restore が戻さずに止まる）"""
    top = line_place()
    if top is None:
        os.environ.pop(USER_ENV_RAN_DIR, None)
    else:
        os.environ[USER_ENV_RAN_DIR] = str(top)


def drop_runner_env() -> None:
    """Archon の変数を落とす。入力と置き場を読み終えた後、対象のテストを走らせる lib/ の関数を呼ぶ前に呼ぶ（lib/ は環境を os.environ
    から継いで子を起こす。節ごと・子の run ごとに値が違うので、残すと同じ run の中の試験の結果の使い回しの指紋も割れる）。
    落とす前に aim_user_env で印の置き場を立てる"""
    aim_user_env()
    for name in [n for n in os.environ if n.startswith(RUNNER_PREFIXES) or n in RUNNER_NAMES]:
        del os.environ[name]


def include_name(block: str) -> str:
    """この節を差し込んだ include の名（Archon が立てる節の実行の path ARCHON_NODE_EXECUTION の最初の __ より前）。同じサブグラフを
    2 度差し込む run で置き場を分ける。include の外の run と path が読めない時は block"""
    try:
        path = json.loads(os.environ.get("ARCHON_NODE_EXECUTION") or "{}").get("path") or ""
    except ValueError:
        path = ""
    head, sep, _ = path.partition("__")
    return head if sep and head else block


def place(block: str) -> Path:
    """サブグラフ block の script のこの run の置き場（run の成果物の置き場の下 <block>/<include の名>/）。無ければ作る"""
    folder = Path(os.environ["ARTIFACTS_DIR"]) / block / include_name(block)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def work_tree() -> Path:
    """run の作業ツリーの根（script の節は run の作業ツリーで起きる）"""
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
    return Path(top.stdout.strip())


def shared_cache() -> Path | None:
    """run をまたぐ控えの根（Archon が project ごとに渡す run をまたぐ置き場 STATE_DIR の下 works-factory/）。渡されなければ None で、
    控えを使わない"""
    state = os.environ.get(SHARED_CACHE_ENV)
    return Path(state) / SHARED_CACHE if state else None


def prev_reason() -> dict:
    """輪の頭の節の返り {reason}: 節の with: の reason（前の周の受け付けが拒んだ理由。1 周目は空の字）をそのまま返す。
    輪の中の役の節は自分の with: を結べない（workflows/AGENTS.md の E5）ので、役はこの節の返りを読む"""
    return {"reason": os.environ["INPUTS_REASON"]}


def transcript() -> tuple:
    """この run の記録（LOG_DIR/<WORKFLOW_ID>.jsonl）の行と、読めなかった訳。読めなければ (None, 訳)。JSON でない行は飛ばす"""
    log_dir, run_id = os.environ.get("LOG_DIR", ""), os.environ.get("WORKFLOW_ID", "")
    if not log_dir or not run_id:
        return None, "run の記録の置き場（LOG_DIR）か run の id（WORKFLOW_ID）が届いていない"
    path = Path(log_dir) / f"{run_id}.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        return None, f"run の記録 {path} が読めない（{e.strerror or e}。dry-run は記録を書かない）"
    rows = []
    for record in lines:
        try:
            rows.append(json.loads(record))
        except ValueError:
            continue
    return rows, ""


def _run_id() -> str:
    return os.environ["WORKFLOW_ID"]
