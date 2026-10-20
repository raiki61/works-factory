"""報告の行（docs/design/head-depth.md の 1.5）。段と根拠だけを持つ。段 → 回す物の表から引く「省く物・足した物」は line が組む"""


def report_line(tier: str, why: str) -> str:
    return f"run の頭の深さ: {tier}" + (f"（根拠: {why}）" if why else "")
