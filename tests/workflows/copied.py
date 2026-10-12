"""役の指示書の写しの照らし（写しの台帳を持つブロックの試験が共に使う）"""
import hashlib


def assert_is_original(case, text: str, sha256: str, edits) -> None:
    """写しの字 text に台帳の直し edits（(元の字, 写しの字, …) の並び。前から当てると元が写しになる順）を後ろから逆に当てると、
    元のバイト（sha256）に戻る。直しの写しの字はどれも写しにちょうど 1 度だけ現れる"""
    for original, copied, *_ in reversed(edits):
        case.assertEqual(text.count(copied), 1, copied)
        text = text.replace(copied, original)
    case.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), sha256)
