"""block の script が Archon と出入りする口（docs/design/README.md の 4 節。今の workflows/.shared/boundary.py の後継）。

口を通さずに書けない物: 入力の読み（text・flag・choice・json・file）・自分の place・出力の pointer・返り。script は入力を
`os.environ.get("INPUTS_<名>")` の字のままで読んでここへ渡す（名を組んで読まない。Archon の scanEnvironmentReads が照らす字の形）。

- text(raw) -> str: 字。無い・空は ""
- flag(raw) -> bool: "true" か "false"。ほかは ValueError
- choice(raw, words) -> str: words のどれか。ほかは ValueError
- json(raw, schema=None): JSON の値。raw は 3 通り: この run の pointer・ファイルのパス（絶対か作業ツリーからの相対）・値そのもの
  （JSON の字）。schema は呼んだ block の schemas/ のファイル名か、2 つ以上の block が使う形の shared:<ファイル名>（pack の
  .shared/schemas/）で、値をその形で照らす。読めない pointer・無いファイル・形に合わない
  値は、空にせず理由を名指して ValueError（落とし穴 K15・持ち主の決め no-silent-loosen）
- file(raw) -> Path | None: ファイル 1 つ（pointer かパス）。空・null は None。在らなければ ValueError
- place() -> Path: この node の block の run directory の中のフォルダ（$ARTIFACTS_DIR/<include の道>/。単独の run では
  $ARTIFACTS_DIR/）。無ければ作る。run directory の根は返さない（4.3）
- pointer(path) -> dict: place の中のファイルを指す Archon の pointer {type: archon_artifact, run_id, path}
- returns(obj): node の返り（JSON 1 つを標準出力へ）
- run(compute, fallback): compute() の返りを返す。例外は fallback(理由の 1 行) の返りにする（落ちない node の口）
- parsed(raw): JSON の値。null・空の字・無い入力は None（読めない JSON は ValueError）。飛ばされうる作り手の欄を受ける時
- picked(raw, names, optional=()): 作り手の返りまるごと（json の form）から、宣言した欄 names（と optional）だけを持つ dict。
  宣言の外の名を読むと KeyError、names の欄が返りに無くても KeyError（optional の欄は無ければ None）
- unknown_keywords(shape): 形の中の、照らしが読まない語の在りか（json の schema はこれが空でないと拒む）
- 対象のコマンドを起こす block（test-gate・fix など）の口。workflows/.shared/boundary.py と同じ約束の写しで、
  tests/blocks/shared/test_ports.py が突き合わせる:
  RUNTIME_COPY・RUNTIME_COPY_PREFIX（Archon が run の作業ツリーに写す置き場。差分に数えない）・RUNNER_PREFIXES・RUNNER_NAMES・
  drop_runner_env(user_env)（Archon が script の node に立てる変数を落とす。先に印の置き場 user_env を立てる）・suite_keep()（TDD の
  実行器の取り置きの根。起動の殻が渡す）
- shared_cache() -> Path | None: run をまたぐ控えの根（Archon が project ごとに渡す STATE_DIR の下の works-factory/。渡されなければ None で、
  控えを使わない。workflows/.shared/boundary.py の shared_cache と同じ約束の写し）
- polyfill(name): 埋め（workflows/.shared/<name>.py。fence・childsweep・child_pointer・skip_value）を読んだモジュール。組み込みで埋めを
  この pack の .shared/ へ移すまでの間だけ、リポジトリの根（WORKS_FACTORY_ROOT）から読む

import すると lib/ の置き場（環境変数 WORKS_FACTORY_ROOT の lib/。無ければこのファイルから辿った lib/）を sys.path の後ろに足す。
Archon は run の始めに pack を写し取るので、run の中ではこのファイルから辿っても lib/ に届かない（起動の殻が根を渡す）。
"""
import importlib.util
import inspect
import json as _json
import os
import re
import sys
from pathlib import Path

POINTER_TYPE = "archon_artifact"
RUNTIME_COPY = ".archon"
RUNTIME_COPY_PREFIX = f"{RUNTIME_COPY}/"
# Archon が script の node に立てる変数（止めた Archon の exec-environment.ts の buildExecNodeEnvironment）。頭の一致は ARCHON_・INPUTS_ だけ
RUNNER_PREFIXES = ("ARCHON_", "INPUTS_")
RUNNER_NAMES = frozenset({
    "ARTIFACTS_DIR", "STATE_DIR", "LOG_DIR", "ADOPTED_RUN_DIR", "WORKFLOW_ID", "BASE_BRANCH", "USER_MESSAGE", "ARGUMENTS",
    "LOOP_USER_INPUT", "LOOP_PREV_OUTPUT", "REJECTION_REASON", "CONTEXT", "EXTERNAL_CONTEXT", "ISSUE_CONTEXT", "TYPED_ARTIFACTS_FILE",
})
USER_ENV_RAN_DIR = "WORKS_FACTORY_USER_ENV_RAN_DIR"   # lib/userenv.py の RAN_DIR_ENV
SUITE_KEEP_ENV = "WORKS_FACTORY_SUITE_KEEP"            # bin/_lib/launcher.py の SUITE_KEEP_ENV
SHARED_CACHE_ENV = "STATE_DIR"                         # Archon が project ごとに渡す run をまたぐ置き場
SHARED_CACHE = "works-factory"                         # その下の、この pack の控えのフォルダ
ROOT_ENV = "WORKS_FACTORY_ROOT"
PACK = Path(__file__).resolve().parents[1]
SHARED = Path(__file__).resolve().parent


def lib_root() -> Path:
    root = os.environ.get(ROOT_ENV)
    return Path(root) / "lib" if root else PACK.parent / "lib"


if str(lib_root()) not in sys.path:
    sys.path.append(str(lib_root()))
if str(lib_root() / "graphloops") not in sys.path:
    sys.path.append(str(lib_root() / "graphloops"))


# ---------------------------------------------------------------- 呼んだ block
def caller_block() -> Path:
    """呼んだ script か src のモジュールが在る block のフォルダ（pack の直下のフォルダ）。.shared の中の呼びは飛ばす"""
    for frame in inspect.stack()[1:]:
        try:
            path = Path(frame.filename).resolve()
        except (OSError, ValueError):
            continue
        if path.is_relative_to(SHARED) or not path.is_relative_to(PACK):
            continue
        return PACK / path.relative_to(PACK).parts[0]
    raise ValueError(f"呼び手が pack {PACK} の block の中に無い（ports・prompt は block の script と src から呼ぶ）")


# ---------------------------------------------------------------- 入力
def text(raw) -> str:
    return "" if raw is None else str(raw)


def flag(raw) -> bool:
    word = text(raw).strip()
    if word not in ("true", "false"):
        raise ValueError(f"flag の入力は true か false（{word!r}）")
    return word == "true"


def choice(raw, words) -> str:
    word = text(raw).strip()
    if word not in words:
        raise ValueError(f"choice の入力は {'|'.join(words)} のどれか（{word!r}）")
    return word


def _pointer_path(ptr: dict) -> Path:
    run_id = os.environ.get("WORKFLOW_ID", "")
    if ptr.get("run_id") != run_id:
        raise ValueError(f"ほかの run の pointer: {ptr.get('run_id')!r}（この run は {run_id!r}）")
    rel = ptr.get("path")
    if (not isinstance(rel, str) or not rel or "\0" in rel or rel.startswith(("/", "\\")) or rel.endswith("/")
            or ".." in re.split(r"[\\/]", rel)):
        raise ValueError(f"pointer の path は run directory からの相対で、.. を持たず、/ で終わらない: {rel!r}")
    return Path(os.environ["ARTIFACTS_DIR"]) / rel


def _is_pointer(value) -> bool:
    return isinstance(value, dict) and value.get("type") == POINTER_TYPE


def _located(raw: str) -> Path | None:
    """raw がこの run の pointer かファイルのパスなら、そのパス。値そのものなら None"""
    try:
        value = _json.loads(raw)
    except ValueError:
        path = Path(raw.strip())
        return path if path.is_absolute() else Path.cwd() / path
    return _pointer_path(value) if _is_pointer(value) else None


def json(raw, schema: str | None = None):
    raw = text(raw)
    if not raw.strip():
        raise ValueError("json の入力が空（値そのもの・ファイルのパス・pointer のどれかを渡す）")
    path = _located(raw)
    if path is None:
        value = _json.loads(raw)
    else:
        try:
            value = _json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ValueError(f"json の入力のファイル {path} が無い") from None
        except (OSError, UnicodeDecodeError, ValueError) as error:
            raise ValueError(f"json の入力のファイル {path} が JSON として読めない: {error}") from None
    if schema is not None:
        _check(value, schema)
    return value


def _check(value, schema: str) -> None:
    from engine.schema import validate_schema   # lib/graphloops/engine/schema.py（KEEP。標準ライブラリだけの形の照らし）
    shared, _, name = schema.rpartition(":")
    if shared not in ("", "shared"):
        raise ValueError(f"形の名は <ファイル名> か shared:<ファイル名>: {schema!r}")
    path = (SHARED if shared else caller_block()) / "schemas" / name
    try:
        shape = _json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"形のファイル {path} が読めない: {error}") from None
    unknown = unknown_keywords(shape)
    if unknown:
        raise ValueError(f"形のファイル {path} が照らしの知らない語 {unknown} を持つ（照らしは黙って飛ばすので書かない。"
                         "使える語は lib/graphloops/engine/schema.py の KNOWN_KEYWORDS）")
    errors = validate_schema(value, shape)
    if errors:
        raise ValueError(f"入力が {schema} の形に合わない: {' / '.join(errors[:5])}")


def unknown_keywords(shape, at: str = "$") -> list[str]:
    """形の中の、照らし（engine.schema.validate_schema）が読まない語の在りか（`<道>.<語>`）。properties・patternProperties の鍵は
    欄の名なので数えない。anyOf・oneOf・format・$ref などは照らしが飛ばす（$ref は拒む）ので、書けば形が効かないまま通る"""
    from engine.schema import KNOWN_KEYWORDS
    out = []
    if isinstance(shape, dict):
        for key, sub in shape.items():
            if key in ("properties", "patternProperties") and isinstance(sub, dict):
                out += [hit for name, child in sub.items() for hit in unknown_keywords(child, f"{at}.{key}.{name}")]
            elif key not in KNOWN_KEYWORDS:
                out.append(f"{at}.{key}")
            elif key in ("items", "additionalProperties"):
                out += unknown_keywords(sub, f"{at}.{key}")
    return out


def file(raw) -> Path | None:
    raw = text(raw)
    if not raw.strip() or raw.strip() == "null":
        return None
    path = _located(raw)
    if path is None:
        raise ValueError(f"file の入力は pointer かファイルのパス（{raw[:80]!r}）")
    if not path.is_file():
        raise ValueError(f"file の入力のファイル {path} が無い")
    return path


# ---------------------------------------------------------------- place と出力
def _include_path() -> list[str]:
    """自分の node の実行の記録 ARCHON_NODE_EXECUTION の path の include の道。path は loop の本体の node なら
    `<loop の id>.<node の id>` の形で（止めた Archon の dag/run-context.ts の beginExecution が stepNamePrefix + node.id）、include の
    中の node の id は `<include の id>__<id>`。段ごとの最後の __ より前を順に継ぐ（judge__world__intake → judge/world、
    world__world-classes-loop.world-classes-prep → world）。dry-run（workflow test）は path に node の id だけを渡すので、include
    の中の loop の本体の node は include の道を失う（docs/design/README.md の 13 節）"""
    raw = os.environ.get("ARCHON_NODE_EXECUTION") or "{}"
    try:
        doc = _json.loads(raw)
    except ValueError:
        raise ValueError(f"ARCHON_NODE_EXECUTION が JSON でない（{raw[:80]!r}）。place を決められない") from None
    path = doc.get("path") if isinstance(doc, dict) else None
    steps = path.split(".") if isinstance(path, str) else []
    return [part for step in steps for part in step.split("__")[:-1] if part]


def place() -> Path:
    folder = Path(os.environ["ARTIFACTS_DIR"]).joinpath(*_include_path())
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def pointer(path) -> dict:
    rel = Path(path).resolve().relative_to(Path(os.environ["ARTIFACTS_DIR"]).resolve()).as_posix()
    return {"type": POINTER_TYPE, "run_id": os.environ["WORKFLOW_ID"], "path": rel}


def returns(obj: dict) -> None:
    """node の返り。Archon は JSON.parse で読むので NaN・Infinity は ValueError で止める"""
    print(_json.dumps(obj, ensure_ascii=False, allow_nan=False), flush=True)


def run(compute, fallback) -> None:
    try:
        out = compute()
    except Exception as error:  # noqa: BLE001 — 落ちない node の口
        reason = " ".join(f"{type(error).__name__}: {error}".split())
        print(reason, file=sys.stderr)
        out = fallback(reason)
    returns(out)


# ---------------------------------------------------------------- 返りまるごと・飛ばされうる欄
def parsed(raw):
    raw = text(raw)
    return None if not raw.strip() or raw.strip() == "null" else _json.loads(raw)


class Picked(dict):
    """宣言した名だけを持つ dict。宣言の外の名は [] でも get でも KeyError（打ち違いが黙って None にならない）"""

    def __missing__(self, key):
        raise KeyError(f"宣言の外の名 {key!r}（宣言した名: {', '.join(self)}）")

    def get(self, key, *_):
        return self[key]


def picked(raw, names, optional=()) -> Picked | None:
    """names の欄が返りに無ければ KeyError（作り手の欄の名の打ち違い・欄の消えを黙って None にしない）。optional の名だけは、無ければ None"""
    got = None if not text(raw).strip() or text(raw).strip() == "null" else json(raw)
    if got is None:
        return None
    if not isinstance(got, dict):
        raise ValueError(f"まるごとの入力が object でない（{type(got).__name__}）")
    absent = [name for name in names if name not in got and name not in optional]
    if absent:
        raise KeyError(f"返りに欄 {absent} が無い（在るのは {sorted(got)}。無くてよい欄は optional に名指す）")
    return Picked((name, got.get(name)) for name in (*names, *[o for o in optional if o not in names]))


# ---------------------------------------------------------------- 対象のコマンドを起こす block の口
def drop_runner_env(user_env: str) -> None:
    """Archon の変数を落とす（入力と place を読み終えた後、対象のコマンドを起こす前）。先に印の置き場 user_env（字。空なら外す）を立てる"""
    if user_env.strip():
        os.environ[USER_ENV_RAN_DIR] = user_env.strip()
    else:
        os.environ.pop(USER_ENV_RAN_DIR, None)
    for name in [n for n in os.environ if n.startswith(RUNNER_PREFIXES) or n in RUNNER_NAMES]:
        del os.environ[name]


def suite_keep() -> Path | None:
    keep = os.environ.get(SUITE_KEEP_ENV)
    return Path(keep) if keep else None


def shared_cache() -> Path | None:
    state = os.environ.get(SHARED_CACHE_ENV)
    return Path(state) / SHARED_CACHE if state else None


def polyfill(name: str):
    if not re.fullmatch(r"[a-z_]+", name):
        raise ValueError(f"埋めの名でない: {name!r}")
    if name in sys.modules:
        return sys.modules[name]
    path = lib_root().parent / "workflows" / ".shared" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or not path.is_file():
        raise ValueError(f"埋め {path} が無い")
    module = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        del sys.modules[name]
        raise
    finally:
        sys.dont_write_bytecode = saved
    return module
