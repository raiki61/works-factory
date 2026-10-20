"""レンズの表と、レンズごとの振り分け・定義の引き（docs/design/lens.md の 1.5。lib/lenses.py の LENSES・key・_any_change と
lib/fixboard.py の lens_route の引きの部分の写し）。

表の行ごとに YAML の node が 3 つ（<レンズ>-prep・<レンズ>・<レンズ>-take）在る。表に足す時は YAML の node も足す（試験が結ぶ）。
"""
import ports  # noqa: F401  （lib/ と lib/graphloops を読めるようにする）
from src import validator   # 元 lib/graphloops/engine/validator.py の写し。agent_def（利用者の plugin の役の定義を引く）

import oneline  # lib/

LENSES = ({"lens": "silent-failure-hunter", "agent": "pr-review-toolkit:silent-failure-hunter"},)
MIN_CITE = 4    # 返答の cite の字の下限（YAML の output_format の minLength と同じ）
MIN_WHY = 20    # 返答の why の字の下限（同上）
NO_CHANGE = "修正の差分に変わったファイルが無い"
NOT_NAMED = "入力 lenses が名指していない"


def key(name: str) -> str:
    return name.replace("-", "_")


def route(row: dict, files: list) -> tuple:
    """（起こすか, 起こさない理由）。変わったファイルが無ければ起こさない"""
    return (True, "") if files else (False, NO_CHANGE)


def definition(agent: str) -> tuple:
    """（定義の本文, 起こさない理由）。引けなければ本文は None で理由が入る。engine の探しが出所の曖昧さで止まる（SystemExit）時も理由にする"""
    try:
        got = validator.agent_def(agent)
    except (Exception, SystemExit) as e:  # noqa: BLE001
        return None, f"{agent} の定義を引けない（{type(e).__name__}: {oneline.one_line(e)}）"
    if got is None or not got.get("body"):
        return None, f"{agent} の定義が役の設定に無い（pr-review-toolkit が入っていない）"
    return got["body"], ""
