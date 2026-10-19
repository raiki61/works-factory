"""報告の行（docs/design/cold-read.md の 9 節）。pass なら行を返さない"""
import oneline  # lib/


def lines(*, status: str, reason: str, passed: bool, stuck: list) -> list:
    if status != "ok":
        return [f"初見の読み手: 読めなかった（{reason}）"]
    if passed:
        return []
    return [f"初見の読み手が通さなかった: {oneline.one_line('；'.join(stuck))}"]
