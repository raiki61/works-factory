"""報告の節「独立の目」に載せる R3 の行（docs/design/r3.md の 5 節）。頭の 1 行だけ（seen・unseen は今も報告に載せない）"""
import eyekit    # lib/


def lines(row: dict) -> list:
    return [eyekit.headline("R3", row)]
