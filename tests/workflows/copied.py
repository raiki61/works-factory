"""役の指示書の写しの照らし（写しの台帳を持つブロックの試験が共に使う）。元は今の works（pack.json の works.commit の版の
works/ の下）。写しに許した直しを後ろから逆に当てると、元のバイトに戻る"""
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "lib"))
import fixboard  # noqa: E402


def agent_body(role: str) -> str:
    """役の定義の本文（works/.shared/core/agents/<役>.md の前付けの後ろ。写しの lib/agents/<役>.md から読む）"""
    return (ROOT / "lib" / "agents" / f"{role}.md").read_text(encoding="utf-8").split("---\n", 2)[2].strip()


def role_definition(agent: str, body: str) -> str:
    """rolekit.with_role_definition（works/.shared/core/rolekit.py:208-212）が本文の頭に置いた段"""
    return f"{fixboard.ROLE_DEF_HEAD.format(agent=agent)}\n\n{body}\n\n---\n\n"


def assert_is_original(case, text: str, sha256: str, edits) -> None:
    """写しの字 text に台帳の直し edits（(元の字, 写しの字, …) の並び。前から当てると元が写しになる順）を後ろから逆に当てると、
    元のバイト（sha256）に戻る。直しの写しの字はどれも写しにちょうど 1 度だけ現れる"""
    for original, copied, *_ in reversed(edits):
        case.assertEqual(text.count(copied), 1, copied)
        text = text.replace(copied, original)
    case.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), sha256)


def restore_problems(text: str, origins: list, edits: list) -> list:
    """写しの字 text が台帳の行（K9。元 origins は [(元のパス, 元の sha256, 元のバイト数)]、直し edits は [(元の字, 写しの字, 訳)]）に
    合わない訳の並び（合えば空）。元が 2 つ以上なら、逆に当てた後をバイト数で切って 1 つずつ sha256 を見る"""
    out = []
    for original, copied, why in reversed(edits):
        n = text.count(copied)
        if n != 1:
            out.append(f"許した直し「{why}」の写しの字が {n} 回在る（1 回のはず）: {copied[:80]!r}")
            continue
        text = text.replace(copied, original)
    raw, at = text.encode("utf-8"), 0
    for path, sha, size in origins:
        got = hashlib.sha256(raw[at:at + size]).hexdigest()
        if got != sha:
            out.append(f"元 {path} に戻らない（sha256 {got}）")
        at += size
    if at != len(raw):
        out.append(f"元を全部繋いだ {at} バイトの後ろに {len(raw) - at} バイトが残る")
    return out
