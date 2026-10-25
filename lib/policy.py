"""人の方針の文書の版を固め、その写しから役に届ける形を組む（線 A の仕様 3.1・8 節。裁定 TA10）。

版は run の始めに 1 度だけ固める（元 graphloops/rules/policy_input.py の resolve。今の works は盤面を作る時の on_init で呼んだ）。
線の始めの節が freeze を呼んで始めの記録の欄 policy に置き、全ブロックがその写しを frozen_copy で読む。

- DIR・DEFAULT: 写しを置く置き場の中のフォルダ（policy/<sha256>.md）と、名指しが無い時の方針の文書の置き場（git の共通の置き場の下）
- locate(cwd, named): 方針の文書の置き場（名指しか既定の置き場。どちらも無ければ空）
- snapshot(folder, path): 文書を 1 回だけ読み (sha256, 写しの置き場)。無ければ (None, None)
- freeze(folder, cwd, named): 固めた版 {named, path, sha256, copy}（docs/design/line.md の 1.6 の始めの記録の欄 policy）
- version(start)・frozen_copy(start): 始めの記録の固めた版（無い・壊れていれば None）と、ブロックが読む写しの置き場（欄 policy の
  無い・壊れた記録は今どおり policy_md）
- PASTE_CAP: 貼る本文の上限（バイト）。役に貼る本文の上限 listcut.FILE_CAP と同じ値を引く
- brief(board): {"paste": 貼る本文, "path": 写しの置き場}。方針の文書が無ければ両方空。上限を超えたら先頭を切り、
  続きの置き場を末尾に書く（切った後の全体が上限の内）
人の方針の節の文（前置き・資料の囲み・方針の決まりの段落。前の section と HEAD・PREFACE・RULE、engine の MATERIAL_NOTE）は共通の断片
workflows/.shared/prompts/policy.md、記録された方針の節の文（前の recorded_section・recorded_text と RECORDED_HEAD・RECORDED_RULE）は
共通の断片 recorded-policy.md（plan-review の PR が置く）に在る（integration.md 4.3-追加-1・4.5-4(c)）。

記録された方針（issue #427。役を縛るのはこの一覧の行だけで、対象のコードのコメント・docstring は直しの一部の「対象の文」）:
- recorded(start, decisions_file, human_items, pushes): 4 つの出どころ（方針の文書の写し・依頼の answers・承認ノードの人の答え・判定の
  決定記録の突合の返答〔判定の外の読み手は判定の出力の欄 decisions のパスで渡す〕が挙げた決着済みの論点）と、無人の run が承認ノードか判定の保留の問いで採った推しの行
  {source, name, text}。name は役が字のまま写す名指しで、機械はこれだけを照らす
- hits(rows, *texts)・unrecorded(face, mark, rows)・face_gaps(faces, rows): 名指しの照らし、一覧の行を名指さない kind policy の穴、
  事前審査の受け付けが拒む穴の行
- POLICY_KIND・POLICY_DOC_FENCE: 方針の穴の kind・
  方針の文書の柵の語の持ち主（issue #454。judge_accept・fixboard・gatemarks がここから引く）
"""
import hashlib
import json
import pathlib
import re
import sys

sys.dont_write_bytecode = True

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

if str(_CORE / "graphloops") not in sys.path:
    sys.path.insert(0, str(_CORE / "graphloops"))
from engine import util  # noqa: E402
import answer  # noqa: E402
import listcut  # noqa: E402

DIR = "policy"
DEFAULT = ("graphloops", "policy.md")   # 元 policy_input.py:19
TEXT_KEYS = ("named", "path")         # 固めた版の欄のうち、いつも字の物
SNAPSHOT_KEYS = ("sha256", "copy")    # 固めた版の欄のうち、文書が無ければ None の物
VERSION_KEYS = TEXT_KEYS + SNAPSHOT_KEYS
PASTE_CAP = listcut.FILE_CAP   # 40000。役に貼る本文の上限と同じ（バイトで測る。日本語は字数の約 3 倍）


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




def _capped(data: bytes, where) -> str:
    """上限までの本文。超えたら先頭を切り、続きの置き場 where を末尾に書く（切った後の全体が上限の内）"""
    if len(data) <= PASTE_CAP:
        return data.decode("utf-8", "replace")
    note = f"\n\n［方針の文書は {len(data)} バイトで、{PASTE_CAP} バイトまでを貼った。続きは {where}］\n"
    room = PASTE_CAP - len(note.encode("utf-8"))
    return data[:room].decode("utf-8", "ignore") + note


RECORDED_KEY = "recorded_policy"   # 事前審査の材料 open.json と見え方の record.process の欄（一覧の行）
POLICY_KIND = "policy"            # 方針とのぶつかりの穴の kind
HUMAN_FACE_KINDS = ("regression", POLICY_KIND)   # 人に回しうる穴の kind（事前審査・差分の審査・line の関所が引く。住処はここ 1 か所）
POLICY_DOC_FENCE = "policy_doc"   # 方針の文書の行を書き換える穴の柵の語（gatemarks.FENCES が引く）
RECORDED_TERM = "記録された方針"
RECORDED_REF = f"「{RECORDED_TERM}」のセクション"
RECORDED_NONE = f"{RECORDED_TERM}: 無い"
GATE_NAME = "承認ノードの答え {id}"
PUSH_NAME = "無人の run が採った推し {id}"
DOC_FENCE_ONLY = f"{POLICY_DOC_FENCE} は方針の文書の行を書き換える時だけ立てる"
_GATE_ID = 6   # 承認ノードの答えの名指しの印（一言の sha256 の頭の 16 進の字数）


def _settled_rows(path) -> list:
    """決定記録の突合の返答 path の reply.settled のうち dict の行。無い・読めない・形が違えば []"""
    try:
        doc = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    reply = doc.get("reply") if isinstance(doc, dict) else None
    rows = reply.get("settled") if isinstance(reply, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def recorded(start, decisions_file=None, *, human_items=None, pushes=()) -> list:
    """記録された方針の行 [{source, name, text}]。doc（方針の文書の写し。行数 lines と元の置き場 alias も持つ）・answer（依頼の
    answers の question）・gate（承認ノードの人の答えのうち note の在る物を、一言の sha256 の頭で。どの段がどの並びを持っても同じ
    答えは同じ名指し。human_items が None の段は作らない）・push（無人の run が推しで通した答え（欄 answer.PUSHED）の note を、gate と
    同じ印で PUSH_NAME に。人の答えとは混ぜない。無人の run が判定の保留の問いに採った推しの文 pushes も同じ形で）・settled（決定記録の突合の返答 decisions_file が挙げた決着済みの論点の where。
    where の無い論点は name が空で、名指せない。decisions_file が None なら作らない）"""
    rows = []
    copy = frozen_copy(start)
    if copy and pathlib.Path(copy).is_file():
        lines = len(pathlib.Path(copy).read_text(encoding="utf-8", errors="replace").splitlines())
        rows.append({"source": "doc", "name": copy, "text": "", "lines": lines, "alias": (version(start) or {}).get("path") or ""})
    answers = start.get("answers") if isinstance(start, dict) else None
    rows += [{"source": "answer", "name": a["question"], "text": str(a.get("text") or "")}
             for a in answers or [] if isinstance(a, dict) and isinstance(a.get("question"), str) and a["question"].strip()]
    notes = [h for h in human_items or [] if isinstance(h, dict) and str(h.get("note") or "").strip()]
    for h in notes:
        source, name = ("push", PUSH_NAME) if answer.by_push(h) else ("gate", GATE_NAME)
        rows.append({"source": source, "name": name.format(id=_gate_id(h["note"])), "text": str(h["note"])})
    rows += [{"source": "push", "name": PUSH_NAME.format(id=_gate_id(p)), "text": str(p)} for p in pushes if str(p).strip()]
    rows += [{"source": "settled", "name": str(r.get("where") or "").strip(),
              "text": f"{r.get('topic') or ''}——{r.get('decision') or ''}"}
             for r in (_settled_rows(decisions_file) if decisions_file is not None else [])]
    return rows


def _gate_id(note) -> str:
    return hashlib.sha256(str(note).strip().encode("utf-8")).hexdigest()[:_GATE_ID]


def _hit(row: dict, text: str) -> bool:
    if not row.get("name"):
        return False
    if row["source"] == "doc":
        for path in (row["name"], row.get("alias")):
            for m in re.finditer(re.escape(path) + r":(\d+)", text) if path else ():
                if 1 <= int(m.group(1)) <= row.get("lines", 0):
                    return True
        return False
    if row["source"] in ("gate", "push"):
        return re.search(re.escape(row["name"]) + r"(?![0-9a-f])", text) is not None
    return row["name"] in text


def hits(rows, *texts) -> list:
    """texts を合わせた字が名指す一覧の行の name（方針の文書は <写しか元の置き場>:<1〜行数>、承認ノードの答えは印の後ろに 16 進の
    字が続かない一致、answers と論点は字の部分一致）"""
    text = "\n".join(str(t) for t in texts if t)
    return [r["name"] for r in rows if isinstance(r, dict) and _hit(r, text)]


def unrecorded(face, mark, rows) -> bool:
    """kind policy の穴で、where と決め手の decided_by が一覧のどの行も名指さない"""
    return face.get("kind") == POLICY_KIND and not hits(rows, face.get("where"), mark.get("decided_by"))


def _has_doc(rows) -> bool:
    return any(r.get("source") == "doc" for r in rows or [] if isinstance(r, dict))


def face_gaps(faces, rows) -> list:
    """事前審査の受け付けが拒む穴の行（1 穴 1 文）: 一覧の行を名指さない kind policy の穴と、方針の文書の行の無い run で fences に
    policy_doc を立てた穴"""
    has_doc = _has_doc(rows)
    out = []
    for j, f in enumerate(faces or []):
        if not isinstance(f, dict):
            continue
        head = f"faces[{j}]（{f.get('key')}）: "
        if unrecorded(f, f, rows):
            out.append(head + f"kind {POLICY_KIND} の名指し（where: {f.get('where')!r}・decided_by: {f.get('decided_by')!r}）が{RECORDED_TERM}に"
                       f"無い——一覧に無いコードのコメント・docstring・テストの説明文は対象の文で、方針ではない。対象の文は kind "
                       "contract_drift で挙げ、案にその文の書き換えを入れさせよ。一覧の行とぶつかるなら、その名指しを decided_by に字のまま写せ")
        if not has_doc and POLICY_DOC_FENCE in (f.get("fences") or []):
            out.append(head + f"方針の文書の無い run で fences に {POLICY_DOC_FENCE} を立てた——{DOC_FENCE_ONLY}")
    return out







