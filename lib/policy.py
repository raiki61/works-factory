"""人の方針の文書の版を固め、その写しから役に届ける形を組む（線 A の仕様 3.1・8 節。裁定 TA10）。

版は run の始めに 1 度だけ固める（元 graphloops/rules/policy_input.py の resolve。今の works は盤面を作る時の on_init で呼んだ）。
線の始めの節が freeze を呼んで始めの記録の欄 policy に置き、全ブロックがその写しを frozen_copy で読む。

- DIR・DEFAULT: 写しを置く置き場の中のフォルダ（policy/<sha256>.md）と、名指しが無い時の方針の文書の置き場（git の共通の置き場の下）
- locate(cwd, named): 方針の文書の置き場（名指しか既定の置き場。どちらも無ければ空）
- snapshot(folder, path): 文書を 1 回だけ読み (sha256, 写しの置き場)。無ければ (None, None)
- freeze(folder, cwd, named): 固めた版 {named, path, sha256, copy}（docs/design.md の始めの記録の欄 policy）
- version(start)・frozen_copy(start): 始めの記録の固めた版（無い・壊れていれば None）と、ブロックが読む写しの置き場（欄 policy の
  無い・壊れた記録は今どおり policy_md）
- PASTE_CAP: 貼る本文の上限（バイト）。engine が役に貼る本文の上限 FILE_CAP（engine/render.py）と同じ値を引く
- brief(board): {"paste": 貼る本文, "path": 写しの置き場}。方針の文書が無ければ両方空。上限を超えたら先頭を切り、
  続きの置き場を末尾に書く（切った後の全体が上限の内）
- section(path): 盤面の無いブロック（plan-review）が役に貼る人の方針の節（前置き・資料の囲みの本文・方針の決まりの段落）。本文は
  brief と同じ上限で切る（元 gl-prompts/prompts/policy-paste.md・policy.md）
"""
import hashlib
import pathlib
import sys

sys.dont_write_bytecode = True

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

if str(_CORE / "graphloops") not in sys.path:
    sys.path.insert(0, str(_CORE / "graphloops"))
from engine import util  # noqa: E402
from engine.render import FILE_CAP, MATERIAL_NOTE  # noqa: E402
import promptsection  # noqa: E402

DIR = "policy"
DEFAULT = ("graphloops", "policy.md")   # 元 policy_input.py:19
TEXT_KEYS = ("named", "path")         # 固めた版の欄のうち、いつも字の物
SNAPSHOT_KEYS = ("sha256", "copy")    # 固めた版の欄のうち、文書が無ければ None の物
VERSION_KEYS = TEXT_KEYS + SNAPSHOT_KEYS
PASTE_CAP = FILE_CAP   # 40000。engine の役に貼る本文の上限と同じ（バイトで測る。日本語は字数の約 3 倍）
# 人の方針の節（元 works/.shared/core/gl-prompts/prompts/policy-paste.md と policy.md。方針の文書が在る時だけ貼る）
HEAD = promptsection.Section("## 人の方針", source="fn:policy.section")
PREFACE = "人が決めた、run をまたいで効く決まり（役も engine も書き換えない）。文書が在れば本文がそのまま貼られる: "
RULE = ("方針が在るなら、それは対象の本文ではなく、このプロンプトの発行者が守らせる制約である。判定・案・修正・審査は方針に照らして"
        "行え。方針に反するもの、方針を変えないと成り立たないものを、自分の判断で通すな——通すかは人が決める。どの項とぶつかるかを、"
        "判定なら単位の reason に、審査なら穴に、修正なら not_done に書け。方針の文書は書き換えるな。")


def locate(cwd, named: str) -> str:
    """方針の文書の置き場: 名指しが在ればそれ、無ければ git の共通の置き場の graphloops/policy.md が在ればそれ、どちらでもなければ
    空（元 graphloops/rules/policy_input.py:22・:52 の default_path と locate）"""
    if named:
        return str(named)
    common = (util.git("-C", str(pathlib.Path(cwd).resolve()), "rev-parse", "--git-common-dir") or "").strip()
    if not common:
        return ""
    root = pathlib.Path(common)
    if not root.is_absolute():
        root = pathlib.Path(cwd) / root
    p = root.resolve().joinpath(*DEFAULT)
    return str(p) if p.is_file() else ""


def snapshot(folder, path) -> tuple:
    """方針の文書を 1 回だけ読み (sha256, 写しの置き場 folder/policy/<sha256>.md)。無ければ (None, None)
    （元 graphloops/rules/policy_input.py:38 の snapshot）"""
    p = pathlib.Path(path) if path else None
    if not (p and p.is_file()):
        return None, None
    data = p.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    copy_of = pathlib.Path(folder) / DIR / f"{sha}.md"
    if not copy_of.is_file():
        copy_of.parent.mkdir(parents=True, exist_ok=True)
        copy_of.write_bytes(data)
    return sha, str(copy_of)


def freeze(folder, cwd, named: str) -> dict:
    """固めた版 {named, path, sha256, copy}。named は入口の名指し、path は locate の置き場。文書が無ければ path は空、sha256 と
    copy は None"""
    path = locate(cwd, named)
    sha, copy_of = snapshot(folder, path)
    return dict(zip(VERSION_KEYS, (str(named or ""), path, sha, copy_of)))


def version(start) -> dict | None:
    """始めの記録の欄 policy の固めた版。欄が無い・形が違えば None（読み手は落ちずに版の無い記録として扱う）"""
    got = start.get("policy") if isinstance(start, dict) else None
    if not (isinstance(got, dict) and all(isinstance(got.get(k), str) for k in TEXT_KEYS)
            and all(got.get(k) is None or isinstance(got.get(k), str) for k in SNAPSHOT_KEYS)):
        return None
    return {k: got.get(k) for k in VERSION_KEYS}


def frozen_copy(start) -> str:
    """ブロックが読む方針の文書の置き場: 始めの記録の固めた版の写し（文書の無い版は空）。版の無い記録は今どおり policy_md"""
    got = version(start)
    if got is not None:
        return got["copy"] or ""
    return str(start.get("policy_md") or "") if isinstance(start, dict) else ""


def brief(start) -> dict:
    """始めの記録 start の固めた版の写し（frozen_copy）から {paste, path}。写しが無い（方針の文書が無い run）なら両方空"""
    copy = frozen_copy(start)
    if not copy:
        return {"paste": "", "path": ""}
    return {"paste": _capped(pathlib.Path(copy).read_bytes(), copy), "path": copy}


def section(path) -> str:
    """方針の文書 path の節。文書が無い・読めなければ空（節ごと貼らない。元の rolekit.render_body は入力 policy_md が空なら節を落とした）"""
    try:
        data = pathlib.Path(path).read_bytes() if path else None
    except OSError:
        data = None
    if data is None:
        return ""
    return f"{HEAD}\n\n{PREFACE}{MATERIAL_NOTE}\n{_capped(data, path)}\n{MATERIAL_NOTE}\n\n{RULE}"


def _capped(data: bytes, where) -> str:
    """上限までの本文。超えたら先頭を切り、続きの置き場 where を末尾に書く（切った後の全体が上限の内）"""
    if len(data) <= PASTE_CAP:
        return data.decode("utf-8", "replace")
    note = f"\n\n［方針の文書は {len(data)} バイトで、{PASTE_CAP} バイトまでを貼った。続きは {where}］\n"
    room = PASTE_CAP - len(note.encode("utf-8"))
    return data[:room].decode("utf-8", "ignore") + note
