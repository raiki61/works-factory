"""目的の監査の根拠の数え直し（docs/design/purpose-review.md の 1.5・4 節）。

写す元 lib/judge_accept.py の purpose_findings_cited。数え直しの本体（_cite_errors の findings の道・_count_in_version・_grep_count）は
写さず、指し先の照らしの 1 か所 lib/cite の物を使う。役の返答の findings の行 {text, cite, hits} の cite を、固めた版 rev に対して
`git grep -F -cI` で数え直し、件数の申告 hits と突き合わせる。呼ぶのは materialkit.accept で、git の向きは呼び手が accept.in_repo で
対象のリポジトリに固定している。
"""
import ports  # noqa: F401  （lib/ と lib/graphloops を sys.path に入れる）
import cite  # lib/。_cite_errors（findings の道は指し先を持たず、置き場 jdir を読まない）
from engine.util import Reject

NID = "観点 purpose-review"
HEAD = f"{NID}: "


def problem(reply, rev, narrows):
    """拒む文か None。『狭めている』（narrows）なのに findings が空・根拠が版で裏取りできない時は文。数え直せない時（git が動かない・
    版を解決できない）も、その字を返す"""
    rows = reply.get("findings") or []
    if reply.get("verdict") == narrows and not rows:
        return (f"{HEAD}『{narrows}』のに findings が空——**判定には作業ツリーで引ける根拠を 1 件以上付けろ**"
                "（欠落を指摘したいなら、欠けている場所の周辺に実在する字列を cite にして、そこに在るべき物が無いことを text に書く）")
    try:
        errs, _ = cite._cite_errors(None, NID, rows, rev, "findings")
    except Reject as e:
        return str(e)
    if errs:
        return f"{HEAD}指摘の根拠が作業ツリーで裏取りできない: " + "; ".join(errs)
    return None
