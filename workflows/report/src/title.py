"""報告の題の行（1 行目）の型の字と、依頼の字からの型の選び方（docs/design/report.md の 1.8）。題の型の字はこのモジュールだけが持つ。

標準ライブラリと .shared の ports だけを読む（lib を import しない）ので、lib を読めない最後の落ち先（scripts/ の except 側）も、頭の文面表
head.py の題の 3 行も、機械の報告の題 machine.title_row も、同じ字をここから引く。

- RUN・REQUEST・REQUEST_MORE: 題の型の鍵（頭の表 head.Line の値と同じ字）。TEXT: 鍵 → 題の型の字（`{run}`・`{request}`・`{more}` が差し込み口）
- fold(text) -> str: 字の空白（改行・タブを含む）の並びを 1 つの空白に詰め、両端を落とした字（lib の oneline.one_line と同じ振る舞い）
- choose(requests) -> (鍵, 1 つ目の畳んだ字, ほかの件数): 畳んで空になる物を除いた依頼の字が 0 件なら RUN、1 件なら REQUEST、2 件以上なら REQUEST_MORE
- render(run_id, requests) -> str: 題の行の字
- requests_in(raw) -> tuple: facts の入力の字（値そのもの・ファイルのパス・pointer）か facts.json から依頼の字 request_texts を緩く読む。
  読めない時は誤りを上げずに空のタプルを返す。緩い読みは落ちない口の予備の道だけが使う（主の道は facts_in で形を照らして読む）

facts の入力を読む所は facts_in.from_port が別に持つ（同じ欄 request_texts を形を照らして読む）。ここで読み直すのは、facts_in が lib の
engine.schema に頼るので lib を読めない落ち先からは呼べないから。pointer の開き方は写さず ports.located を呼ぶ。
"""
import json

import ports

RUN = "title"
REQUEST = "title_request"
REQUEST_MORE = "title_request_more"
TEXT = {
    RUN: "# 報告（run {run}）",
    REQUEST: "# 報告（run {run}）: {request}",
    REQUEST_MORE: "# 報告（run {run}）: {request}（ほかの依頼の行 {more} 件）",
}


def fold(text) -> str:
    return " ".join(str(text).split())


def choose(requests) -> tuple[str, str, int]:
    folded = [x for x in (fold(r) for r in requests) if x]
    if not folded:
        return RUN, "", 0
    if len(folded) == 1:
        return REQUEST, folded[0], 0
    return REQUEST_MORE, folded[0], len(folded) - 1


def render(run_id: str, requests) -> str:
    key, request, more = choose(requests)
    return TEXT[key].format(run=run_id, request=request, more=more)


def requests_in(raw) -> tuple:
    """読めた依頼の字（全部が字の配列の時だけ）。形を照らさない在りかの読み ports.located で引くので、pointer の開き方は写さない"""
    try:
        raw = ports.text(raw)
        if not raw.strip():
            return ()
        path = ports.located(raw)
        doc = json.loads(raw if path is None else path.read_text(encoding="utf-8"))
        texts = doc.get("request_texts") if isinstance(doc, dict) else None
        if isinstance(texts, list) and all(isinstance(t, str) for t in texts):
            return tuple(texts)
    except Exception:  # noqa: BLE001 — 落ちない口の予備の道が呼ぶので、読めない物（壊れた JSON・別の run の pointer・無いファイル）は依頼の字なしにする
        pass
    return ()
