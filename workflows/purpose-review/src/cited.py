"""目的の監査の根拠の数え直し（docs/design/purpose-review.md の 1.5・4 節）。

写す元 lib/judge_accept.py の purpose_findings_cited・_cite_errors（findings の道だけ）・_count_in_version・_grep_count・_repo_root。
役の返答の findings の行 {text, cite, hits} の cite を、固めた版 rev に対して `git grep -F -cI` で数え直し、件数の申告 hits と突き合わせる。
呼ぶのは materialkit.accept で、git の向きは呼び手が accept.in_repo で対象のリポジトリに固定している。
"""
import ports  # noqa: F401  （lib/ と lib/graphloops を sys.path に入れる）
from engine.util import Reject, _grep, git, repo_root, sum_counts

HEAD = "観点 purpose-review: "


def _grep_count(cite, rev):
    """固めた版に対する `git grep -F -cI`（字面として数える）。（`…:数` の文字列, ""）か（None, 理由）"""
    root = repo_root(git)
    if root is None:
        return None, "git が動かない"
    return _grep(["git", "grep", "-F", "-cI", "-e", cite, rev, "--", ":(top)"], root)


def _count_in_version(i, row, cite, rev, probed, errs):
    """根拠の字列を版 rev で数え、0 件・件数の申告（hits）の違いを errs に積む。数えられなければ Reject"""
    got, why = _grep_count(cite, rev)
    if why:
        if "alive" not in probed:
            probed["alive"] = git("rev-parse", "--is-inside-work-tree") is not None
            probed["rev"] = git("rev-parse", "--verify", f"{rev}^{{commit}}") is not None
        if not probed["alive"]:
            raise Reject(f"{HEAD}指摘の根拠を数え直せない（git が動かない）——確かめられないものを合格にはしない")
        if not probed["rev"]:
            raise Reject(f"{HEAD}指摘の根拠を数え直せない（採点する版 {rev[:12]} を解決できない）"
                         "——版が消えた run では、数えた結果も『現物に無い』も言えない")
        raise Reject(f"{HEAD}指摘の根拠を数え直せない（{why}）——確かめられないものを合格にはしない")
    hits = sum_counts(got)
    if hits is None:
        raise Reject(f"{HEAD}指摘の根拠を数え直せない（git grep -c の出力が `…:数` の形でない: {got.splitlines()[:1]}）")
    if hits == 0:
        errs.append(f"findings[{i}]: '{cite[:40]}' が現物に 1 件も無い")
    elif row.get("hits") != hits:
        errs.append(f"findings[{i}]: '{cite[:40]}' の件数の申告 {row.get('hits')} が数え直し {hits} と違う")


def _errors(rows, rev) -> list:
    """findings の行ごとの外れの文。指し先を持たない根拠の行の 4 つの照らし（dict・cite が空・改行・NUL）と版での数え直し"""
    if not rev:
        raise Reject(f"{HEAD}指摘の根拠を数え直せない（採点する版が固まっていない）——確かめられないものを合格にはしない")
    probed, errs = {}, []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errs.append(f"findings[{i}]: 素の文字列は受け取らない")
            continue
        cite = (row.get("cite") or "").strip()
        if not cite:
            errs.append(f"findings[{i}]: cite（作業ツリーで引ける字列）が空")
            continue
        if "\n" in cite or "\r" in cite:
            errs.append(f"findings[{i}]: cite に改行が入っている")
            continue
        if "\0" in cite or "\0" in (row.get("target") or "") or "\0" in (row.get("where") or ""):
            errs.append(f"findings[{i}]: cite / target / where に NUL が入っている")
            continue
        _count_in_version(i, row, cite, rev, probed, errs)
    return errs


def problem(reply, rev, narrows):
    """拒む文か None。『狭めている』（narrows）なのに findings が空・根拠が版で裏取りできない時は文。数え直せない時（git が動かない・
    版を解決できない）も、その字を返す"""
    rows = reply.get("findings") or []
    if reply.get("verdict") == narrows and not rows:
        return (f"{HEAD}『{narrows}』のに findings が空——**判定には作業ツリーで引ける根拠を 1 件以上付けろ**"
                "（欠落を指摘したいなら、欠けている場所の周辺に実在する字列を cite にして、そこに在るべき物が無いことを text に書く）")
    try:
        errs = _errors(rows, rev)
    except Reject as e:
        return str(e)
    if errs:
        return f"{HEAD}指摘の根拠が作業ツリーで裏取りできない: " + "; ".join(errs)
    return None
