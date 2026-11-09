"""並行 PR の出口が落ちた時の返り（形は同じ。ok は真のまま——止めるかは line が決め、確かめられなかったと status が言う）。
標準ライブラリだけを読む（出口の script が lib を読めない時にも同じ形を返す。落とし穴 K1）"""

DOWNGRADES = [{"what": "担当の PR へ申し送りを投稿しない（下書きを報告に載せる）",
               "versus": "review-graph は任せ先の役が gh で投稿する"}]


def fallen(why: str) -> dict:
    reason = f"並行 PR の出口が落ちた（{why}）"
    return {"ok": True, "status": "failed", "stop_reason": "", "reason": reason, "material": {"status": "not_run", "reason": reason},
            "excluded": None, "drafts": None, "reads": None, "downgrades": [dict(row) for row in DOWNGRADES],
            "report": [f"並行 PR: 確かめが終わらなかった（{reason}）"]}
