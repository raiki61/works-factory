"""役の指示書の写しの照らし（写しの台帳を持つブロックの試験が共に使う）。元は今の works（pack.json の works.commit の版の
works/ の下）。写しに許した直しを後ろから逆に当てると、元のバイトに戻る"""
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "lib"))
import fixboard  # noqa: E402

# 台帳の直しの後ろに当てる書き直し {根からのパス: [{why, original, copied}]}。1 件ずつ元の字・写しの字と、許した訳
# （持ち主の決めか issue）を why に持つ
REWRITES = json.loads((pathlib.Path(__file__).with_name("copied_rewrites.json")).read_text(encoding="utf-8"))


def agent_body(role: str) -> str:
    """役の定義の本文（works/.shared/core/agents/<役>.md の前付けの後ろ。写しの lib/agents/<役>.md から読む）"""
    return (ROOT / "lib" / "agents" / f"{role}.md").read_text(encoding="utf-8").split("---\n", 2)[2].strip()


def role_definition(agent: str, body: str) -> str:
    """rolekit.with_role_definition（works/.shared/core/rolekit.py:208-212）が本文の頭に置いた段"""
    return f"{fixboard.ROLE_DEF_HEAD.format(agent=agent)}\n\n{body}\n\n---\n\n"


def assert_is_original(case, path: pathlib.Path, sha256: str, edits) -> None:
    """写しのファイル path の字が元に戻る（restore_text_problems。REWRITES の鍵は根からのパス）"""
    assert_text_is_original(case, path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8"), sha256, edits)


def assert_text_is_original(case, key: str, text: str, sha256: str, edits) -> None:
    """写しの字 text が元 1 つのバイト（sha256）に戻る（restore_text_problems が空）。key は写しのファイルの根からのパスか、
    YAML に直に書いた prompt: の `<YAML の根からのパス>#<ノードの id>`"""
    case.assertEqual(restore_text_problems(key, text, [(key, sha256, None)], edits), [])


def restore_problems(path: pathlib.Path, origins: list, edits: list) -> list:
    """写しのファイル path の restore_text_problems（REWRITES の鍵は根からのパス）"""
    return restore_text_problems(path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8"), origins, edits)


def restore_text_problems(key: str, text: str, origins: list, edits) -> list:
    """写しの字 text が台帳の行（K9）に合わない訳の並び（合えば空）。台帳の直し edits（(元の字, 写しの字[, 訳]) の並び。前から
    当てると元が写しになる順）と、その後ろの REWRITES[key] の書き直しを後ろから逆に当てる。直しの写しの字はどれも写しにちょうど
    1 度だけ現れる。元 origins は [(元の名, 元の sha256, 元のバイト数)] で、逆に当てた後をバイト数で切って 1 つずつ sha256 を見る
    （最後の元のバイト数 None は残りの全部）"""
    rewrites = [(r["original"], r["copied"], r["why"]) for r in REWRITES.get(key, [])]
    out = []
    for original, copied, *why in reversed([*edits, *rewrites]):
        n = text.count(copied)
        if n != 1:
            out.append(f"許した直し「{why[0] if why else original[:40]}」の写しの字が {n} 回在る（1 回のはず）: {copied[:80]!r}")
            continue
        text = text.replace(copied, original)
    raw, at = text.encode("utf-8"), 0
    for origin, sha, size in origins:
        size = len(raw) - at if size is None else size
        got = hashlib.sha256(raw[at:at + size]).hexdigest()
        if got != sha:
            out.append(f"元 {origin} に戻らない（sha256 {got}）")
        at += size
    if at != len(raw):
        out.append(f"元を全部繋いだ {at} バイトの後ろに {len(raw) - at} バイトが残る")
    return out


def rewritten(folder: pathlib.Path) -> set:
    """folder の直下で REWRITES が書き直しを持つファイルの名（台帳に無い名が在れば、使われない書き直し）"""
    return {pathlib.PurePosixPath(p).name for p in REWRITES if (ROOT / p).parent == folder}
