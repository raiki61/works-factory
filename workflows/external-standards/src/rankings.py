"""順位の行の照らし（docs/design/external-standards.md の 4 節）。外部標準照合の返答の rankings の行を受け付けで照らす。

写す元は lib/judge_accept.py の external_rankings・blank・EMPTY（元 works/.shared/core/graphloops/rules/review-loop.py:467・480・2973）。
Reject を上げる代わりに拒む文を返し、通れば None
"""
# 「書いていない」と同じ扱いにする語
EMPTY = ("なし", "無し", "ない", "無い", "特になし", "n/a", "none", "-", "未確認", "不明",
         "todo", "未実施", "未測定", "後で")
HEAD = "観点 external-standards: "


def blank(s, min_len) -> bool:
    """役が埋める自由文が「空同然」か（表と長さの両方で見る）"""
    t = (s or "").strip()
    return t.lower() in EMPTY or len(t) < min_len


def problem(reply) -> str | None:
    """差分が乗る選択肢（diff_at）は ranked のどれかで、最上位でないなら上位を採れない理由が要る。順位が空なら空の理由が要る"""
    errs = []
    if not reply.get("rankings") and blank(reply.get("rankings_none"), 10):
        errs.append("rankings が空なのに rankings_none（順位を付けられる一般化した問題が無い理由）が無い——空の順位で clean を名乗らせない")
    for i, r in enumerate(reply.get("rankings") or []):
        if r["diff_at"] not in r["ranked"]:
            errs.append(f"rankings[{i}] の diff_at '{r['diff_at'][:40]}' が ranked に無い——一次情報が推す選択肢のどれに乗るかを、ranked の綴りのまま書け")
        elif r["diff_at"] != r["ranked"][0] and blank(r.get("why_not_higher"), 10):
            errs.append(f"rankings[{i}]: 差分は最上位（{r['ranked'][0][:40]}）でなく '{r['diff_at'][:40]}' に乗るのに、上位を採れない理由（why_not_higher）が無い")
    return HEAD + "; ".join(errs) if errs else None
