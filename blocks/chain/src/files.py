"""chain の置き場のファイルの名（親の run の place からの相対）。bin/apply が最後の差分を引く名は lib/chain.py の FINAL・REPORT と同じ
（tests/blocks/chain/test_chain.py が突き合わせる）"""
FINAL = "chain/final.diff"                  # 元の基から採る周までの封じた最後の差分
REPORT = "chain.md"                        # 周ごとの表
NEXT_REQUEST_DIR = "chain"                 # chain/<子のノードの id>/ に次の依頼を書く


def round_diff(n: int) -> str:
    """止まった周が残す差分（前の周の head からその周の head まで）"""
    return f"chain/round-{n}.diff"
