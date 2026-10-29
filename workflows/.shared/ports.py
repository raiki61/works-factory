"""block の script が Archon と出入りする口（docs/design/README.md の 4 節。今の workflows/.shared/boundary.py の後継）。

口を通さずに書けない物: 入力の読み（text・flag・choice・json・file）・自分の place・出力の pointer・返り。script は入力を
`os.environ.get("INPUTS_<名>")` の字のままで読んでここへ渡す（名を組んで読まない。Archon の scanEnvironmentReads が照らす字の形）。

- text(raw) -> str: 字。無い・空は ""
- flag(raw) -> bool: "true" か "false"。ほかは ValueError
- choice(raw, words) -> str: words のどれか。ほかは ValueError
- json(raw, schema): JSON の値。raw は 3 通り: この run の pointer・ファイルのパス（絶対か作業ツリーからの相対）・値そのもの
  （JSON の字）。schema（必須）は形の名で、値をその形で照らす。読めない pointer・無いファイルは理由を名指して ValueError、形に
  合わない値は ShapeError（ValueError の子。読んだ値を value に持つ）（落とし穴 K15・持ち主の決め no-silent-loosen）
- file(raw, form) -> Path | None: ファイル 1 つ（pointer かパス）。空・null は None。在らなければ ValueError。form（必須）は入力の
  宣言と同じ字で、json(<名>)・jsonl(<名>) は中身をその形で照らしてからパスを返す。file は字の文書で照らさないが、.json・.jsonl の
  ファイルは拒む（JSON は形を名指して運ぶ）
- carried_file(row) -> Path | None: form を値と一緒に運ぶ行 {ref, form}（報告の節の files のように、種類の違うファイルを 1 つの欄で
  中継する値）の ref を、行の form で file と同じに照らしてパスを返す。form は書き手が出どころの宣言の form を字で書く
- 形の名: block の schemas/ のファイル名・shared:<名>（pack の .shared/schemas/）・lib:<名>（lib/ の下。lib に住処の在る形）・
  returns:<workflow の名>（include した workflow の返す節の output_format。graph の受け皿の節の output_format だけが書け、口は読まない）。
  引き方は _shape_path の 1 か所
- form_of(description) -> (form, 名) | None: form の語（text・file・flag・choice(a|b)・json(<名>)・jsonl(<名>)）の住処。入力の
  description・形の中の description・口の呼びの form の字が使う
- open_shapes(shape, block_folder=None, *, shared=None, lib=None, returned=None): 形の中の、中身を宣言しない所の在りか（object に properties も
  patternProperties も無い・array に items が無い・型の無い所・type に 6 つの型を全部並べた所）。形の照らしは、知らない語（unknown_keywords）を先に、この開きを後に見て、
  どちらかが在れば形のファイルを拒む。静的な照らし（tests/layers）は木の根の shared と lib と、returns:<workflow の名> の引き returned を
  渡して同じ関数を使う
- is_pointer_shape(shape): 形が pointer の欄か（properties.type が const か 1 語の enum で archon_artifact）。pointer の判別の住処
- carries_file(shape): 所がファイルを運ぶか（pointer の欄か、型が string だけのパスの字）。その所の description の form は指す先の
  ファイルの form（値の形でない）
- shape_errors(value, schema, block_folder=None): 値を形の名で照らした誤りの一覧（試験の作り物を照らす tests/blocks/kit.py も使う）
- place() -> Path: この node の block の run directory の中のフォルダ（$ARTIFACTS_DIR/<include の道>/。単独の run では
  $ARTIFACTS_DIR/）。無ければ作る。run directory の根は返さない（4.3）
- include_folders(path) -> list[str]: node の実行の記録の path から、place の <include の道> のフォルダの並び（place が使う引き方）
- inside(rel, root) -> Path: 置き場 root からの相対パス rel の照らし（.. と先頭・末尾の / を拒む）。pointer の path の照らしと
  child_pointer（ほかの run の置き場の中）が使う
- pointer(path, form) -> dict: place の中のファイルを指す Archon の pointer {type: archon_artifact, run_id, path}。form（必須）は
  返す節の pointer の欄の description と同じ字で、中身を照らしてから指す（書き手が書いた時に読み手と同じ形で照らす）
- returns(obj): node の返り（JSON 1 つを標準出力へ）
- run(compute, fallback): compute() の返りを返す。例外は fallback(理由の 1 行) の返りにする（落ちない node の口）
- parsed(raw): JSON の値。null・空の字・無い入力は None（読めない JSON は ValueError）。飛ばされうる作り手の欄を受ける時
- picked(raw, names, optional=()): 作り手の返りまるごと（Archon が output_format で照らした値。pointer やパスは開かない）から、宣言した欄 names（と optional）だけを持つ dict。
  宣言の外の名を読むと KeyError、names の欄が返りに無くても KeyError（optional の欄は無ければ None）
- unknown_keywords(shape): 形の中の、照らしが読まない語の在りか（json の schema はこれが空でないと拒む）
- 対象のコマンドを起こす block（test-gate・fix など）の口。workflows/.shared/boundary.py と同じ約束の写しで、
  tests/blocks/shared/test_ports.py が突き合わせる:
  RUNTIME_COPY・RUNTIME_COPY_PREFIX（Archon が run の作業ツリーに写す置き場。差分に数えない）・RUNNER_PREFIXES・RUNNER_NAMES・
  drop_runner_env(user_env)（Archon が script の node に立てる変数を落とす。先に印の置き場 user_env を立てる）・suite_keep()（TDD の
  実行器の取り置きの根。起動の殻が渡す）
- shared_cache() -> Path | None: run をまたぐ控えの根（Archon が project ごとに渡す STATE_DIR の下の works-factory/。渡されなければ None で、
  控えを使わない。workflows/.shared/boundary.py の shared_cache と同じ約束の写し）
- polyfill(name): 埋め（このファイルと同じ .shared/ の <name>.py。fence・childsweep・skip_value）を読んだモジュール。埋めは pack と
  一緒に写し取られるので、run の中でもこのファイルの隣に在る。child_pointer は chain が .shared から直に import する

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
_HERE = SHARED   # この口の在る .shared（試験が SHARED を替えても、呼び手の見分けはここで飛ばす）


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
        if path.is_relative_to(_HERE) or not path.is_relative_to(PACK):
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


def inside(rel, root) -> Path:
    """置き場 root からの相対パス rel を、Archon が通す形に限って root の中のパスにする。形が違えば ValueError。Archon は / と \\ の両方で
    区切って .. を拒み、末尾の / は pathlib が落とすが Archon の stat は ENOTDIR で拒む（child_pointer も子の run の置き場の root で使う）"""
    if (not isinstance(rel, str) or not rel or "\0" in rel or rel.startswith(("/", "\\")) or rel.endswith("/")
            or ".." in re.split(r"[\\/]", rel)):
        raise ValueError(f"pointer の path は run directory からの相対で、.. を持たず、/ で終わらない: {rel!r}")
    return Path(root) / rel


def _pointer_path(ptr: dict) -> Path:
    run_id = os.environ.get("WORKFLOW_ID", "")
    if ptr.get("run_id") != run_id:
        raise ValueError(f"ほかの run の pointer: {ptr.get('run_id')!r}（この run は {run_id!r}）")
    return inside(ptr.get("path"), os.environ["ARTIFACTS_DIR"])


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


def json(raw, schema: str):
    raw = text(raw)
    if not raw.strip():
        raise ValueError("json の入力が空（値そのもの・ファイルのパス・pointer のどれかを渡す）")
    path = _located(raw)
    value = _json.loads(raw) if path is None else _read_json(path)
    _check(value, schema)
    return value


def _read_json(path: Path):
    try:
        return _json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"json の入力のファイル {path} が無い") from None
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValueError(f"json の入力のファイル {path} が JSON として読めない: {error}") from None


def _read_jsonl(path: Path) -> list:
    rows = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"jsonl のファイル {path} が読めない: {error}") from None
    for number, line in enumerate(lines, 1):
        if line.strip():
            try:
                rows.append(_json.loads(line))
            except ValueError as error:
                raise ValueError(f"jsonl のファイル {path} の {number} 行目が JSON として読めない: {error}") from None
    return rows


def _check_file(path: Path, form: str) -> None:
    """ファイル path の中身を form（file・json(<名>)・jsonl(<名>)）で照らす。file は字の文書で照らさないが、JSON のファイル（.json・
    .jsonl）を file で運ぶことは拒む（形を名指さずに受け渡しの JSON を読み書きさせない）"""
    parsed = form_of(form) if isinstance(form, str) and FORM.fullmatch(form) else None
    if parsed is None or parsed[0] not in ("file", *JSON_FORMS):
        raise ValueError(f"ファイルの form は file・json(<名>)・jsonl(<名>) の字: {form!r}")
    kind, name = parsed
    if kind == "file":
        if path.suffix in (".json", ".jsonl"):
            raise ValueError(f"JSON のファイル {path.name} を form file で運ばない（json(<名>)・jsonl(<名>) で形を名指す）")
        return
    if kind == "json":
        _check(_read_json(path), name)
        return
    errors = []
    for number, row in enumerate(_read_jsonl(path), 1):
        errors += [f"{number} 行目 {e}" for e in shape_errors(row, name)]
    if errors:
        raise ShapeError(f"{path.name} の行が {name} の形に合わない: {' / '.join(errors[:5])}")


class ShapeError(ValueError):
    """値が宣言の形に合わない（読めない入力の ValueError と分ける）。読んだ値を value に持つ"""

    def __init__(self, message: str, value=None):
        super().__init__(message)
        self.value = value


# form の語の住処（入力の description・形の中の description・口の呼びの form の字）。json(<名>)・jsonl(<名>) の名は block の schemas/
# のファイル名か、2 つ以上の block が使う shared:<名>（.shared/schemas/）か、lib に住処の在る lib:<名>（lib/ の下）か、include した
# workflow の返りの returns:<workflow の名>（返す節の output_format。ファイルでないので静的な照らしだけが読む。RETURNS_HEAD）
FORM = re.compile(r"(text|file|flag|choice\(([a-z0-9_-]+(?:\|[a-z0-9_-]+)+)\)|(json|jsonl)\(((?:shared:|lib:|returns:)?[A-Za-z0-9_.-]+)\))(?=: |$)")
JSON_FORMS = ("json", "jsonl")
ANY_TYPES = frozenset({"object", "array", "string", "number", "boolean", "null"})
RETURNS_HEAD = "returns"


def form_of(description) -> tuple[str, str | None] | None:
    """`<form>: <意味>` の字（か form の字そのもの）の (form の語, 名)。名は json・jsonl の形の名か choice の語の並び、ほかは None。
    form で始まらなければ None"""
    match = FORM.match(description) if isinstance(description, str) else None
    if match is None:
        return None
    if match[3]:
        return match[3], match[4]
    if match[2]:
        return "choice", match[2]
    return match[1], None


def _shape_path(name: str, block_folder=None, *, shared=None, lib=None) -> Path:
    """形の名のファイル。頭の無い名は block の schemas/（block_folder が無ければ呼んだ block）、shared: は .shared/schemas/、lib: は lib/"""
    head, _, rest = name.partition(":")
    if not rest:
        return Path(block_folder if block_folder is not None else caller_block()) / "schemas" / name
    if head == "shared":
        return Path(shared if shared is not None else SHARED) / "schemas" / rest
    if head == "lib":
        return Path(lib if lib is not None else lib_root()) / rest
    if head == RETURNS_HEAD:
        raise ValueError(f"{name!r} は include した workflow の返す node の形で、ファイルでない（口は YAML を読まない。静的な照らしだけが読む）")
    raise ValueError(f"形の名は <ファイル名>・shared:<ファイル名>・lib:<ファイル名>・returns:<workflow の名>: {name!r}")


def _load_shape(name: str, block_folder=None, *, shared=None, lib=None):
    path = _shape_path(name, block_folder, shared=shared, lib=lib)
    try:
        return path, _json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"形のファイル {path} が読めない: {error}") from None


def is_pointer_shape(shape) -> bool:
    """形が Archon の pointer の欄か（properties.type が const か 1 語の enum で archon_artifact）。pointer の判別の住処はここ 1 つ"""
    kind = shape.get("properties", {}).get("type") if isinstance(shape, dict) and isinstance(shape.get("properties"), dict) else None
    return isinstance(kind, dict) and (kind.get("const") == POINTER_TYPE or kind.get("enum") == [POINTER_TYPE])


def carries_file(shape) -> bool:
    """所が値でなくファイルを運ぶか: pointer の欄か、型が string だけの所（ファイルのパスの字）。その所の description の form は
    指す先のファイルの form で、値の形でない"""
    return is_pointer_shape(shape) or isinstance(shape, dict) and shape.get("type") in ("string", ["string"])


def _named(shape):
    """形の所の description が名指す json・jsonl の (form, 名)。無ければ None"""
    form = form_of(shape.get("description")) if isinstance(shape, dict) else None
    return form if form and form[0] in JSON_FORMS else None


def open_shapes(shape, block_folder=None, *, shared=None, lib=None, returned=None, at: str = "$", _seen: tuple = ()) -> list[str]:
    """形の中の、中身を宣言していない所の在りか。閉じと数えるのは照らし（engine.schema.validate_schema）が読む語だけ:
    object は空でない properties か空でない patternProperties か additionalProperties: false、array は items（中も同じに見る）。
    type・enum・const のどれも無い所と、形を書いた additionalProperties（照らしが読まない）は開き。type に JSON の 6 つの型を全部
    並べた所も「何でも受ける」で開き（properties・items を添えても。値の型は書き手が決めるので書ける。#861）。description が
    json(<名>)・jsonl(<名>) の所は名の形を引き、無い・読めない・開いている時は開き（名の形が中身を宣言する）。returns:<workflow の名> は
    returned(<名>) が返す (返す節の output_format, その workflow のフォルダ) を引く（静的な照らしが渡す。無ければ読めない）"""
    if not isinstance(shape, dict):
        return [at]
    named = _named(shape)
    if named is not None and not carries_file(shape):
        return _open_named(named[1], block_folder, shared, lib, returned, at, _seen)
    out = []
    if named is not None:
        out += _open_named(named[1], block_folder, shared, lib, returned, at, _seen)
    types = shape.get("type")
    types = {types} if isinstance(types, str) else set(types or ())
    if not types and "enum" not in shape and "const" not in shape:
        return out + [at]
    if ANY_TYPES <= types:
        return out + [f"{at}(6 つの型を全部並べた)"]
    extra = shape.get("additionalProperties")
    if isinstance(extra, dict):
        out.append(f"{at}.additionalProperties")
    props = shape.get("properties") if isinstance(shape.get("properties"), dict) else {}
    pats = shape.get("patternProperties") if isinstance(shape.get("patternProperties"), dict) else {}
    if "object" in types and not props and not pats and extra is not False:
        out.append(at)
    for key, part in (("properties", props), ("patternProperties", pats)):
        for name, sub in part.items():
            out += open_shapes(sub, block_folder, shared=shared, lib=lib, returned=returned, at=f"{at}.{key}.{name}", _seen=_seen)
    if "array" in types:
        if "items" not in shape:
            out.append(at)
        else:
            out += open_shapes(shape["items"], block_folder, shared=shared, lib=lib, returned=returned, at=f"{at}.items", _seen=_seen)
    return out


def _open_named(name, block_folder, shared, lib, returned, at, seen) -> list[str]:
    if name in seen:
        return []
    head, _, rest = name.partition(":")
    try:
        if head == RETURNS_HEAD:
            sub, block_folder = returned(rest) if returned is not None else (None, None)
            if sub is None:
                raise ValueError(name)
        else:
            _, sub = _load_shape(name, block_folder, shared=shared, lib=lib)
    except ValueError:
        return [f"{at}({name} が無いか読めない)"]
    return open_shapes(sub, block_folder, shared=shared, lib=lib, returned=returned, at=f"{at}({name})", _seen=(*seen, name))


def _expanded(shape, block_folder=None, seen: tuple = ()):
    """pointer でない所の json(<名>) を名の形に置き換えた形（照らしを 1 度で済ませる）。jsonl(<名>) は 1 行の形なので、値の所では
    行の配列として読む。所の type が null を許し名の形が許さなければ null を足す。名の巡りは辿った名の並びで止める"""
    if not isinstance(shape, dict):
        return shape
    named = _named(shape)
    if named is not None and not carries_file(shape) and named[1] not in seen:
        _, sub = _load_shape(named[1], block_folder)
        sub = _expanded(sub, block_folder, (*seen, named[1]))
        if named[0] == "jsonl":
            sub = {"type": "array", "items": sub}
        types = shape.get("type")
        types = [types] if isinstance(types, str) else list(types or ())
        sub_types = sub.get("type")
        sub_types = [sub_types] if isinstance(sub_types, str) else list(sub_types or ())
        if "null" in types and sub_types and "null" not in sub_types:
            sub = {**sub, "type": [*sub_types, "null"]}
        return sub
    out = dict(shape)
    for key in ("properties", "patternProperties"):
        if isinstance(shape.get(key), dict):
            out[key] = {name: _expanded(sub, block_folder, seen) for name, sub in shape[key].items()}
    if isinstance(shape.get("items"), dict):
        out["items"] = _expanded(shape["items"], block_folder, seen)
    return out


def shape_errors(value, schema: str, block_folder=None) -> list[str]:
    """値を形の名 schema で照らした誤り（空なら合う）。形のファイルが読めない・知らない語を持つ・中身を宣言しない所を持つなら ValueError"""
    from engine.schema import validate_schema   # lib/graphloops/engine/schema.py（KEEP。標準ライブラリだけの形の照らし）
    if block_folder is None and ":" not in schema:
        block_folder = caller_block()
    path, shape = _load_shape(schema, block_folder)
    unknown = unknown_keywords(shape)
    if unknown:
        raise ValueError(f"形のファイル {path} が照らしの知らない語 {unknown} を持つ（照らしは黙って飛ばすので書かない。"
                         "使える語は lib/graphloops/engine/schema.py の KNOWN_KEYWORDS）")
    holes = open_shapes(shape, block_folder)
    if holes:
        raise ValueError(f"形のファイル {path} が中身を宣言しない所 {holes} を持つ（object は properties か patternProperties、array は "
                         "items を書き、type に 6 つの型を全部並べない）")
    return validate_schema(value, _expanded(shape, block_folder))


def _check(value, schema: str, block_folder=None) -> None:
    errors = shape_errors(value, schema, block_folder)
    if errors:
        raise ShapeError(f"入力が {schema} の形に合わない: {' / '.join(errors[:5])}", value)


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
            elif key in ("items", "additionalProperties", "if", "then", "not"):
                out += unknown_keywords(sub, f"{at}.{key}")
            elif key == "allOf" and isinstance(sub, list):
                out += [hit for i, part in enumerate(sub) for hit in unknown_keywords(part, f"{at}.allOf[{i}]")]
    return out


def file(raw, form: str) -> Path | None:
    raw = text(raw)
    if not raw.strip() or raw.strip() == "null":
        return None
    path = _located(raw)
    if path is None:
        raise ValueError(f"file の入力は pointer かファイルのパス（{raw[:80]!r}）")
    if not path.is_file():
        raise ValueError(f"file の入力のファイル {path} が無い")
    _check_file(path, form)
    return path


def carried_file(row: dict) -> Path | None:
    ref = row["ref"]
    return file(_json.dumps(ref) if isinstance(ref, dict) else ref, row["form"])


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
    return include_folders(doc.get("path") if isinstance(doc, dict) else None)


def include_folders(path) -> list[str]:
    """node の実行の記録の path（上の _include_path の形）から、place の include の道のフォルダの並び。工場の外の見る道具が、run の記録の
    node の path から値の記録の在り処を引くのにも使う"""
    steps = path.split(".") if isinstance(path, str) else []
    return [part for step in steps for part in step.split("__")[:-1] if part]


def place() -> Path:
    folder = Path(os.environ["ARTIFACTS_DIR"]).joinpath(*_include_path())
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def pointer(path, form: str) -> dict:
    """place の中のファイル path を指す pointer。form（file・json(<名>)・jsonl(<名>)）で中身を照らしてから指し、合わなければ指さない"""
    _check_file(Path(path), form)
    rel = Path(path).resolve().relative_to(Path(os.environ["ARTIFACTS_DIR"]).resolve()).as_posix()
    return {"type": POINTER_TYPE, "run_id": os.environ["WORKFLOW_ID"], "path": rel}


def _output_formats() -> list[tuple[str, dict]]:
    """呼んだ script の node 自身の output_format の (node の id, 形)。正本は block の YAML のその節 1 つで写しを持たない（io-in-output-format）。
    node は ARCHON_NODE_EXECUTION の path の最後の段の id で引く（Archon が script の node に立てる記録。1 つの script を複数の node が
    使っても取り違えない）。記録が無い時（単独の呼び・試験）、PyYAML が読めない所（Archon が `uv run` で回す script）、node を引けない時は
    空で、そこは Archon が実行の後に同じ output_format で照らす（止めた Archon の dag-executor.ts の certifyExecOutput）"""
    try:
        path = _json.loads(os.environ.get("ARCHON_NODE_EXECUTION") or "{}").get("path")
    except (ValueError, AttributeError):
        return []
    if not isinstance(path, str) or not path:
        return []
    try:
        import yaml
        block = caller_block()
        doc = yaml.safe_load((block / f"works-factory-{block.name}.yaml").read_text(encoding="utf-8"))
    except (ImportError, OSError, ValueError):
        return []
    own = path.split(".")[-1].split("__")[-1]
    stack = list(doc.get("nodes") or []) if isinstance(doc, dict) else []
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("id") == own and isinstance(node.get("output_format"), dict):
                if node.get("script") != Path(sys.argv[0]).stem:
                    return []   # 記録の node が今回している script の node でない（試験が include に別の node を立てた）時は照らさない
                return [(own, node["output_format"])]
            stack.extend((node.get("loop_group") or {}).get("nodes") or [])
    return []


def _returned_errors(obj) -> None:
    """返す値を、この node の output_format で照らす。node が引ければ、その形に合わない時に ShapeError（どの node のどの欄が合わないかを名指す）"""
    try:
        from engine.schema import validate_schema   # lib/graphloops/engine/schema.py（lib が読めない所では照らさず返す）
    except ImportError:
        return
    formats = _output_formats()
    if not formats:
        return
    nid, shape = formats[0]
    if errors := validate_schema(obj, shape):
        raise ShapeError(f"node {nid} の戻り値が自分の output_format に合わない: {' / '.join(errors[:5])}", obj)


def returns(obj: dict) -> None:
    """node の戻り値。Archon は JSON.parse で読むので NaN・Infinity は ValueError で止める。node 自身の output_format に合わなければ
    ShapeError で落ちる（Archon が実行の後に照らすのと同じ形を、出どころの script が返す前に照らす）"""
    line = _json.dumps(obj, ensure_ascii=False, allow_nan=False)
    _returned_errors(obj)
    print(line, flush=True)


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
    raw = text(raw)
    if not raw.strip() or raw.strip() == "null":
        return None
    got = _json.loads(raw)   # 返りまるごとは Archon が output_format で照らした値。pointer やパスは開かない（ファイルは json・file で読む）
    if _is_pointer(got):
        raise ValueError("まるごとの入力が pointer（ファイルの中身は json(raw, <形>)・file(raw, <form>) で読む）")
    if not isinstance(got, dict):
        raise ValueError(f"まるごとの入力が object でない（{type(got).__name__}）")
    absent = [name for name in names if name not in got and name not in optional]
    if absent:
        raise KeyError(f"出力に欄 {absent} が無い（在るのは {sorted(got)}。無くてよい欄は optional に名指す）")
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
    path = SHARED / f"{name}.py"
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
