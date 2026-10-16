"""run の差分の封印と、封じた差分を置いてよいかの決まり。標準ライブラリと答えの語（answer.GO_WORDS・STOP_WORDS）と件数の決まらない一覧の切り口（listcut）だけ（git は repo を cwd にして呼ぶ）。

差分を組む・作業ツリーの指紋を取るのは green_cert（差分の組み方の 1 か所）で、ここは持たない。
封じる型は ASF の merge-queue（gate の封印を execute が照らし直し、書いた後に読み戻す）に倣う。

- SealError: 書けない・読み戻しが書いた物と違う
- digest(data) -> str: sha256 の 16 進 64 字
- write_readback(path, data) -> str: 隣の一時ファイルに書いて読み戻し、合えば path に付け替えて digest を返す。違えば SealError
  （書けたと言わない・path は前のまま）
- diff_files(repo, data) -> {path: (added, deleted)}: 差分のバイトに載るファイルごとの行数。読めなければ ValueError
- seal_refusal(*, fingerprint, fingerprint_ok) -> str: 封じてよいかの理由（空なら封じてよい）
- unknown_row(reason) -> str: 守りのパスを確かめられない時に、当たりとして数える 1 行
- deleted_paths(text) -> list: 封じた差分の字が消すファイル（DELETED_HEAD）
- deleted_lines(paths, where) -> list: 取り込むと消えるファイルの行（承認ノードの文と報告が共に引く）。listcut.SHOWN 件までは取り込む前に
  1 本ずつ名指し、超える分は件数と where（封じた差分の実のパス）で指す
- apply_refusal(*, ...) -> str: 置いてよいかの理由（空なら置く）。決まりは関数の doc
"""
import hashlib
import os
import pathlib
import re
import subprocess

import listcut
from answer import GO_WORDS, STOP_WORDS

REQUEST_BY = "request:"          # 止め札: 文がこれで始まる止める語（今の works の report.REQUEST_BY）
PASSED, REDESIGN, UNVERIFIABLE = STATUSES = ("pass", "redesign-needed", "unverifiable")   # 目の状態の語の持ち主（ほかは写さずここを読む）
UNKNOWN_HEAD = "守りのパスを確かめられない（差分が一覧に触れていないとは言えない）: "
DELETED_HEAD = "取り込むと消えるファイル"


class SealError(Exception):
    """書けない・読み戻しが書いた物と違う"""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_readback(path, data: bytes) -> str:
    path = pathlib.Path(path)
    tmp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(data)
        back = tmp.read_bytes()
        if digest(back) != digest(data):
            raise SealError(f"{path} の読み戻しが書いた物と違う（書いた {digest(data)}・読んだ {digest(back)}）")
        os.replace(tmp, path)
    except OSError as e:
        raise SealError(f"{path} に書けない（{e}）") from e
    finally:
        tmp.unlink(missing_ok=True)
    return digest(back)


def diff_files(repo, data: bytes) -> dict:
    """封じる差分のバイトそのものに載るファイルごとの (足した行, 消した行)。バイナリは (None, None)。
    本物の index を通して数え直すと assume-unchanged・skip-worktree の印の付いたファイルが見えないので、差分から読む。
    --whitespace=nowarn は利用者の apply.whitespace=error の設定で数える口が落ちないため"""
    done = subprocess.run(["git", "apply", "--numstat", "--whitespace=nowarn", "-z", "-"], input=data, cwd=repo,
                          capture_output=True)
    if done.returncode != 0:
        raise ValueError(f"差分のファイルを数えられない: {done.stderr.decode('utf-8', 'replace').strip()[-300:]}")
    out = {}
    for rec in done.stdout.decode("utf-8", "replace").split("\0"):
        if rec:
            added, deleted, name = rec.split("\t", 2)
            out[name] = (None, None) if added == "-" else (int(added), int(deleted))
    return out


def seal_refusal(*, fingerprint, fingerprint_ok) -> str:
    """緑の認証の指紋 fingerprint が在り、今の木と合わなければ（fingerprint_ok が偽。照らすのは green_cert.matches）理由。
    fingerprint が無ければ照らさない"""
    if fingerprint is None or fingerprint_ok:
        return ""
    return "緑の認証の指紋が今の木と違う（test-gate の後に作業ツリーが変わった）"


def unknown_row(reason: str) -> str:
    return UNKNOWN_HEAD + reason


def deleted_paths(text: str) -> list:
    """git の差分の字のうち、ファイルを消す節（見出しに deleted file mode）のパス（現れた順・重ねない。元 works/dev/lib.sh:595-597 の
    diff --diff-filter=D --name-only と同じ物を、封じた差分そのものから読む）。パスは '--- a/…' 行を正とし、中身の無いファイルの
    削除のように '---' 行の無い節は 'diff --git' の見出しから引く（どちらも git の引用を changemap.unquote_git_path で解く）"""
    from changemap import unquote_git_path
    out, head, gone, path = [], None, False, None

    def close():
        name = path or head
        if gone and name is not None and name not in out:
            out.append(name)
    for line in text.split("\n"):
        if line.startswith("diff --git "):
            close()
            m = re.match(r'diff --git ("?)a/(.*?)\1 ("?)b/(.*?)\3$', line)
            head = unquote_git_path(m.group(1) + m.group(2) + m.group(1)) if m else None
            gone, path = False, None
        elif line.startswith("deleted file mode"):
            gone = True
        elif line.startswith("--- ") and not line.startswith("--- /dev/null") and path is None:
            got = unquote_git_path(line[4:].strip())
            path = got[2:] if got.startswith("a/") else got
    close()
    return out


def deleted_lines(paths, where: str) -> list:
    """取り込むと消えるファイルの行（承認ノードの文と報告が同じ字で並べる）。where は封じた差分の実のパス。paths が listcut.SHOWN 件を
    超える時は先頭 SHOWN 件と『ほか K 件（全件: where）』の 1 行だけ（行の数は本数に依らない）"""
    return listcut.lines(paths, where=where, prefix=f"{DELETED_HEAD}: ")


def _answer_refusal(answer: dict) -> str:
    word = answer.get("decision")
    if word in GO_WORDS:
        return ""
    text = answer.get("text")
    if word in STOP_WORDS and isinstance(text, str) and text.startswith(REQUEST_BY):
        kind = "（止め札）"
    elif word in STOP_WORDS:
        kind = ""
    else:
        kind = f"（通す語 {'・'.join(GO_WORDS)} のどれでもない）"
    return f"最後の承認ノードで {word or '語なし'} と答えた{kind}"


def apply_refusal(*, sealed_hash, current_hash, answer, green_ok, eyes_ok, r2, fingerprint_ok, protected) -> str:
    """置いてよいかの理由（空なら置く）。上から順に見て最初の理由を返す:
    1. sealed_hash が空（seal が走っていない）
    2. current_hash が sealed_hash と違う
    3. 答え answer（{decision, text}）が在り、decision が通す語 GO_WORDS のどれでもない（止め札もここ）
    4. r2（None か {status, reason}）の status が REDESIGN（unverifiable は機械で拒まず人の答えに任せる）。人の通しの答えでも拒む（R2 が作り直しと言った run は部分を取り込まない）
    5. 答えが無い（関所が開かなかった）のに、green_ok・eyes_ok・fingerprint_ok のどれかが真でないか、protected（守りの当たりの行。
       unknown_row の行は「確かめられない」として書き分けるが、当たりと同じく拒む）が空でない。守りのパスは人の通しの答えだけが通す
    答えが通す語なら、赤でも・R2 の作り直しのほかの目の阻害でも置く"""
    if not sealed_hash:
        return "封じた hash が無い（seal が走っていない）"
    if current_hash != sealed_hash:
        return f"封じた差分と今の差分が違う（封じた {sealed_hash}・今 {current_hash}）"
    if answer is not None:
        why = _answer_refusal(answer)
        if why:
            return why
    if isinstance(r2, dict) and r2.get("status") == REDESIGN:
        return f"R2 が作り直しと言った（部分を取り込まない）: {r2.get('reason') or '理由なし'}"
    if answer is None:
        unchecked = [word for word, fact in (("緑でない", green_ok), ("目が通していない", eyes_ok),
                                             ("緑の認証の指紋が今の木と違う", fingerprint_ok)) if fact is not True]
        unknown = [row for row in protected if row.startswith(UNKNOWN_HEAD)]
        if len(unknown) < len(protected):
            unchecked.append(f"守りのパスに当たった（{len(protected) - len(unknown)} 行）")
        if unknown:
            unchecked.append("守りのパスを確かめられない")
        if unchecked:
            return f"人の通しの答えが無いのに {'・'.join(unchecked)}"
    return ""
