"""修正の後の局所レビュー（レンズ）のブロックの中身。控え lens.json の形と読み書きは core の lens だけが持つ。

レンズは利用者が入れた pr-review-toolkit の agent（定義は写さない。役の隔離した設定のキャッシュか <PLUGIN>_ROOT から
engine.validator.agent_def で前付けを剥がした本文を引く。引くのは呼び手の lens-prep の script）。レンズの節は定義の本文を指示書に貼った節そのもので、子（Agent）を起こさない
（節ごとの model が効くように。持ち主 2026-10-01）。

- LENSES:               レンズの表（{lens, agent, route}。route(files) -> (go, 理由)。行ごとに YAML のレンズの節と、その返りの中継の節が 1 つずつ在る）
- key(row):            振り分けの出口の欄の頭（<key>_go・prompt_<key>）
- render(row, body, diff_file, files, lang): レンズの節の指示書（定義の本文 body（engine.validator.agent_def の body）と、この線での
                        読み方・返し方）
- collect(board, replies): 集め役。レンズの節の出口（{レンズの名: 境の口 value が読んだ出口の値}。無ければ None）で置き場 board の
                        lens.json を埋め、落ちたレンズも理由つきで記録して ok。控えが無い・読めない時は ok: false と理由
"""
import json
import pathlib
import sys

sys.dont_write_bytecode = True

import fixboard  # noqa: E402  （役の定義の見出し ROLE_DEF_HEAD）
import lens  # noqa: E402
import promptsection  # noqa: E402


def _any_change(files):
    return (True, "") if files else (False, "修正の差分に変わったファイルが無い")


LENSES = (
    {"lens": "silent-failure-hunter", "agent": "pr-review-toolkit:silent-failure-hunter", "route": _any_change},
)


def key(row) -> str:
    return row["lens"].replace("-", "_")


TASK_HEAD = promptsection.Section("## このセクションでの仕事", source="fn:lenses.render")
REPLY_HEAD = promptsection.Section("## 返答の書き方", source="fn:lenses.render")


def render(row, body: str, diff_file: str, files: list, lang: str) -> str:
    return "\n".join([
        fixboard.ROLE_DEF_HEAD.format(agent=row['agent']), "", body.strip(), "", "---", "",
        TASK_HEAD, "",
        f"この役は修正の後の局所レビューのレンズ（{row['lens']}）として、新しい会話で起きている。上の定義の観点だけで、"
        "この周の修正が作った差分を見る。修正を書いた役の会話も、判定の経緯も引き継いでいない。",
        "この役は読むだけの役。使えるのは Read・Grep・Glob だけで、作業ツリーを 1 文字も変えない。子（Agent）は起こせない——"
        "定義がほかの道具や子に触れていても、自分で読んで答えよ。", "",
        f"- 修正の差分: `{diff_file}`（Read せよ。周の頭に固めた版と修正後の姿の差）",
        f"- 変わったファイル: {json.dumps(files, ensure_ascii=False)}", "",
        "差分は起点であって境ではない——呼び元・読む側まで読め。指摘は変わったファイルの中の物だけを挙げる。"
        "指摘は差分の審査役が検算してから穴にする。",
        "",
        REPLY_HEAD, "",
        "- 指摘 1 件ごとに `findings` の 1 行: `where`（変わったファイルのパス。上の一覧の字のまま）・"
        "`cite`（そのファイルの今の姿に在る字列そのまま。4 字以上）・`why`（何が黙って失敗し、誰が気づけないか。20 字以上）。",
        "- 指摘が無いなら `findings` を空にし、`findings_none` に何を読んで無いと言えるかを書け。",
        "- 返すのは JSON だけ。", "", lang,
    ]) + "\n"


def collect(board, replies: dict) -> dict:
    b = pathlib.Path(board)
    try:
        rows = lens.collect(b, {row["lens"]: replies.get(row["lens"]) for row in LENSES})
    except ValueError as e:
        return {"ok": False, "reason": str(e), "lens_file": "", "ran": 0, "failed": 0, "not_routed": 0}
    count = {s: sum(1 for r in rows if r["state"] == s) for s in ("ran", "failed", "not_routed")}
    return {"ok": True, "reason": "", "lens_file": str(b / lens.LENS_FILE), **count}
