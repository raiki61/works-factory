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

記録された方針（issue #427。役を縛るのはこの一覧の行だけで、対象のコードのコメント・docstring は直しの一部の「対象の文」）:
- recorded(start, settled, human_items): 4 つの出どころ（方針の文書の写し・依頼の answers・承認ノードの人の答え・決着済みの論点）
  の行 {source, name, text}。name は役が字のまま写す名指しで、機械はこれだけを照らす
- settled_rows(folder): 決定記録の突合の返答（PRIOR_DECISIONS_FILE）の決着済みの論点の行
- hits(rows, *texts)・unrecorded(face, mark, rows)・face_gaps(faces, rows): 名指しの照らし、一覧の行を名指さない kind policy の穴、
  事前審査の受け付けが拒む穴の行
- recorded_section(rows, gates_given): 役に貼る「記録された方針」のセクション（名指せる行が無ければ RECORDED_NONE）
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


RECORDED_KEY = "recorded_policy"   # 事前審査の材料 open.json と見え方の record.process の欄（一覧の行）
PRIOR_DECISIONS_FILE = "material-prior-decisions.json"   # 判定の置き場の決定記録の突合の返答（judge_accept.material_take が書く）
RECORDED_TERM = "記録された方針"
RECORDED_REF = f"「{RECORDED_TERM}」のセクション"
RECORDED_NONE = f"{RECORDED_TERM}: 無い"
RECORDED_HEAD = promptsection.Section(f"## {RECORDED_TERM}", source="fn:policy.recorded_section")
GATE_NAME = "承認ノードの答え {n}"
RECORDED_RULE = ("記録された方針は、人か対象の持ち主が「決めた」と記録に残した決まりで、出どころは下の 4 つだけ（方針の文書の写し・"
                 "依頼の answers・承認ノードの人の答え・決定記録の突合が挙げた決着済みの論点）。対象のリポジトリのコードのコメント・"
                 "docstring・テストの説明文は、下の行に当たらない限り「対象の文」——コードの今の姿の説明で、持ち主の決めではない。"
                 "対象の文が綺麗な形と食い違うなら、方針とのぶつかりにせず、直しの一部としてその文を書き換えよ。方針とぶつかると言う時は、"
                 "下の行の名指しを字のまま写せ（機械が一覧に当たるかを照らし、当たらなければ拒む）。")
_CAP = 120   # セクションに並べる答え・論点の頭の字数


def settled_rows(folder) -> list:
    """判定の置き場 folder の決定記録の突合の返答の reply.settled のうち dict の行。無い・読めない・形が違えば []"""
    try:
        doc = json.loads((pathlib.Path(folder) / PRIOR_DECISIONS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    reply = doc.get("reply") if isinstance(doc, dict) else None
    rows = reply.get("settled") if isinstance(reply, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def recorded(start, *, settled=(), human_items=None) -> list:
    """記録された方針の行 [{source, name, text}]。doc（方針の文書の写し。行数 lines と元の置き場 alias も持つ）・answer（依頼の
    answers の question）・gate（承認ノードの人の答えのうち note の在る物を並びの順に 1 から。human_items が None の段は作らない）・
    settled（決着済みの論点の where。where の無い論点は name が空で、名指せない）"""
    rows = []
    copy = frozen_copy(start)
    if copy and pathlib.Path(copy).is_file():
        lines = len(pathlib.Path(copy).read_text(encoding="utf-8", errors="replace").splitlines())
        rows.append({"source": "doc", "name": copy, "text": "", "lines": lines, "alias": (version(start) or {}).get("path") or ""})
    answers = start.get("answers") if isinstance(start, dict) else None
    rows += [{"source": "answer", "name": a["question"], "text": str(a.get("text") or "")}
             for a in answers or [] if isinstance(a, dict) and isinstance(a.get("question"), str) and a["question"].strip()]
    notes = [h for h in human_items or [] if isinstance(h, dict) and str(h.get("note") or "").strip()]
    rows += [{"source": "gate", "name": GATE_NAME.format(n=n), "text": str(h["note"])} for n, h in enumerate(notes, 1)]
    rows += [{"source": "settled", "name": str(r.get("where") or "").strip(),
              "text": f"{r.get('topic') or ''}——{r.get('decision') or ''}"} for r in settled if isinstance(r, dict)]
    return rows


def _hit(row: dict, text: str) -> bool:
    if not row.get("name"):
        return False
    if row["source"] == "doc":
        for path in (row["name"], row.get("alias")):
            for m in re.finditer(re.escape(path) + r":(\d+)", text) if path else ():
                if 1 <= int(m.group(1)) <= row.get("lines", 0):
                    return True
        return False
    if row["source"] == "gate":
        return re.search(re.escape(row["name"]) + r"(?!\d)", text) is not None
    return row["name"] in text


def hits(rows, *texts) -> list:
    """texts を合わせた字が名指す一覧の行の name（方針の文書は <写しか元の置き場>:<1〜行数>、承認ノードの答えは番号の後ろに数字が
    続かない一致、answers と論点は字の部分一致）"""
    text = "\n".join(str(t) for t in texts if t)
    return [r["name"] for r in rows if isinstance(r, dict) and _hit(r, text)]


def unrecorded(face, mark, rows) -> bool:
    """kind policy の穴で、where と決め手の decided_by が一覧のどの行も名指さない"""
    return face.get("kind") == "policy" and not hits(rows, face.get("where"), mark.get("decided_by"))


def face_gaps(faces, rows) -> list:
    """事前審査の受け付けが拒む穴の行（1 穴 1 文）: 一覧の行を名指さない kind policy の穴と、方針の文書の行の無い run で fences に
    policy_doc を立てた穴"""
    has_doc = any(r.get("source") == "doc" for r in rows if isinstance(r, dict))
    out = []
    for j, f in enumerate(faces or []):
        if not isinstance(f, dict):
            continue
        head = f"faces[{j}]（{f.get('key')}）: "
        if unrecorded(f, f, rows):
            out.append(head + f"kind policy の名指し（where: {f.get('where')!r}・decided_by: {f.get('decided_by')!r}）が{RECORDED_TERM}に"
                       f"無い——一覧に無いコードのコメント・docstring・テストの説明文は対象の文で、方針ではない。対象の文は kind "
                       "contract_drift で挙げ、案にその文の書き換えを入れさせよ。一覧の行とぶつかるなら、その名指しを decided_by に字のまま写せ")
        if not has_doc and "policy_doc" in (f.get("fences") or []):
            out.append(head + "方針の文書の無い run で fences に policy_doc を立てた——policy_doc は方針の文書の行を書き換える時だけ立てる")
    return out


def recorded_section(rows, *, gates_given=True) -> str:
    """役に貼る「記録された方針」のセクション。名指せる行が 1 つも無ければ頭に RECORDED_NONE。gates_given が偽の段（承認ノードの
    答えを入力に持たない役）は、その行を「この役には渡っていない」と書く"""
    rows = [r for r in rows or [] if isinstance(r, dict)]
    of = {s: [r for r in rows if r.get("source") == s] for s in ("doc", "answer", "gate", "settled")}
    out = [RECORDED_HEAD, "", RECORDED_RULE, ""]
    if not any(r.get("name") for r in rows):
        out.append(RECORDED_NONE)
    doc = of["doc"][0] if of["doc"] else None
    out.append("- 方針の文書: " + (f"名指し `{doc['name']}:<行>`（1〜{doc['lines']} 行。元の置き場 {doc['alias'] or '無い'}）"
                                  if doc else "無い"))
    out.append("- 依頼の answers: " + ("" if of["answer"] else "無い"))
    out += [f"  - 名指し {json.dumps(r['name'], ensure_ascii=False)}: {_head(r['text'])}" for r in of["answer"]]
    out.append("- 承認ノードの人の答え: " + ("この役には渡っていない" if not gates_given else "" if of["gate"] else "無い"))
    out += [f"  - 名指し `{r['name']}`: {_head(r['text'])}" for r in of["gate"]] if gates_given else []
    out.append("- 決着済みの論点（決定記録の突合）: " + ("" if of["settled"] else "無い"))
    out += [f"  - 名指し {json.dumps(r['name'], ensure_ascii=False)}: {_head(r['text'])}" if r["name"]
            else f"  - （where が無いので名指せない）{_head(r['text'])}" for r in of["settled"]]
    return "\n".join(x.rstrip() for x in out)


def _head(text: str) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= _CAP else text[:_CAP] + "…"
