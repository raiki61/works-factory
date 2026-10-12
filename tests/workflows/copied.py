"""役の指示書の写しの照らし（写しの台帳を持つブロックの試験が共に使う）"""
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
