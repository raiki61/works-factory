"""局所レビューの fork のレンズ（/code-review）の所見が役に届かなかった行を「見ていない」と書く口。

**なぜ要るか（実測 2026-10-08、利用者の run f57a5374 ほか 6 つの works の家の会話の記録）。** 組み込みの skill code-review は
fork（下請けの会話）で走る。返答の道具 StructuredOutput を継いだ fork は所見をそこへ書いて終わり、親の Skill の結果は
『Skill execution completed』だけになった。局所レビューの役は /code-review の行を items 空・failed に『本文なし』で返し、
写しの規則（local_review_covers_lenses）は行が在れば通すので、消えた所見は「見たが所見なし」と同じ形で記録に入った
（f57a5374 では 10 件。うち 1 件は 2 run 後に阻害になった）。

0.2.48 から局所レビューの役は包みの旗 text-reply で起き（adapter.py の頭の 21）、子にも fork にも返答の道具が無いので、
/code-review は所見を本文で返す。それでも /code-review の行が空なら、本文で返った 0 件と届かなかった物を見分けられないので、
受け付け（blk-material の take。今は lib/judge_accept.material_take）は FORK_LENSES の空の行を「所見なし」でなく「見ていない」と書く（mark_unseen。起こし直しても
同じ形で落ちるので拒まない）。見ていない、は作業ファイル LENS_FILE に残す（報告の「未確認のレンズ」の節に出す report_lines は持ってこなかった）。0.2.46 の拾い戻し（包みの PostToolUse:StructuredOutput のフック record-output.py が下請けの返答を残し、
受け付けが戻す）は、旗の起動では戻す物が無く（実の run の控えで 3 本とも 0 件）、2026-10-09 の掃除で外した。

- mark_unseen(reply, skills): (印を付けた返答の写し, 控え {unseen})。受けた返答は書き換えない
"""
import copy

LENS_FILE = "local-review-lenses.json"     # 周の作業ファイル（board/r<N>/）。受け付けが毎回書き直す
# fork で走り、返答が親に届かないと実測したレンズ。空の行は「所見なし」に数えない
# （/simplify・/security-review は親の会話の中で走る。実測の Skill の所要 14 ミリ秒・256 ミリ秒）
FORK_LENSES = ("/code-review",)
UNSEEN_TAG = "【works: 所見を受け取れていない——このレンズは見ていないのと同じに扱え】"


def mark_unseen(reply: dict, skills: list) -> tuple:
    """宣言の skill のレンズ（/ で始まる名）のうち FORK_LENSES の行が items 空で invoked なら、failed の頭に UNSEEN_TAG を置き、
    material の文の欄（checked・detail・reason）にも同じ印を足した写しを返す。親の会話で走ったレンズの行は役の申告のまま"""
    out = copy.deepcopy(reply)
    notes = {"unseen": []}
    lenses = {e["skill"] for e in skills if isinstance(e.get("skill"), str) and e["skill"].startswith("/")}
    mat = out.get("material") if isinstance(out.get("material"), dict) else None
    for row in out.get("findings") or []:
        lens = row.get("skill") if isinstance(row, dict) else None
        if lens not in lenses or lens not in FORK_LENSES or row.get("items") or row.get("invoked") is not True:
            continue
        row["failed"] = f"{UNSEEN_TAG} {str(row.get('failed') or '')}"
        notes["unseen"].append(lens)
        if mat is not None:
            for k in ("checked", "detail", "reason"):
                if isinstance(mat.get(k), str):
                    mat[k] = f"{mat[k]}（{lens}: {UNSEEN_TAG}）"
    return out, notes

