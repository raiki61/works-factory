"""人の方針の文を役に届ける形に組む（線 A の仕様 3.1・8 節。裁定 TA10）。

方針の文書の置き場を決めて写しを固定するのは、盤面を作る時の写しの RL の on_init（policy_input.resolve。共通の git の置き場の
graphloops/policy.md か、入力 policy_md で名指した文書を、盤面の policy/<sha256>.md に写し、record.process.policy に
{path, sha256, copy} を置く）。ここはその写しから、start がブロックの入力（policy_paste・policy_path）に渡す物を組むだけ。

- PASTE_CAP: 貼る本文の上限（バイト）。engine が役に貼る本文の上限 FILE_CAP（engine/render.py）と同じ値を引く
- brief(board): {"paste": 貼る本文, "path": 写しの置き場}。方針の文書が無ければ両方空。上限を超えたら先頭を切り、
  続きの置き場を末尾に書く（切った後の全体が上限の内）
- section(path): 盤面の無いブロック（plan-review）が役に貼る人の方針の節（前置き・資料の囲みの本文・方針の決まりの段落）。本文は
  brief と同じ上限で切る（元 gl-prompts/prompts/policy-paste.md・policy.md）
"""
import pathlib
import sys

sys.dont_write_bytecode = True

_CORE = pathlib.Path(__file__).resolve().parent
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

if str(_CORE / "graphloops") not in sys.path:
    sys.path.insert(0, str(_CORE / "graphloops"))
from engine.render import FILE_CAP, MATERIAL_NOTE  # noqa: E402
import promptsection  # noqa: E402

PASTE_CAP = FILE_CAP   # 40000。engine の役に貼る本文の上限と同じ（バイトで測る。日本語は字数の約 3 倍）
# 人の方針の節（元 works/.shared/core/gl-prompts/prompts/policy-paste.md と policy.md。方針の文書が在る時だけ貼る）
HEAD = promptsection.Section("## 人の方針", source="fn:policy.section")
PREFACE = "人が決めた、run をまたいで効く決まり（役も engine も書き換えない）。文書が在れば本文がそのまま貼られる: "
RULE = ("方針が在るなら、それは対象の本文ではなく、このプロンプトの発行者が守らせる制約である。判定・案・修正・審査は方針に照らして"
        "行え。方針に反するもの、方針を変えないと成り立たないものを、自分の判断で通すな——通すかは人が決める。どの項とぶつかるかを、"
        "判定なら単位の reason に、審査なら穴に、修正なら not_done に書け。方針の文書は書き換えるな。")


def brief(b) -> dict:
    """record.process.policy.copy（固定した版の写し）から {paste, path}。写しが無い（方針の文書が無い run）なら両方空"""
    copy = ((b.record.get("process") or {}).get("policy") or {}).get("copy")
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
