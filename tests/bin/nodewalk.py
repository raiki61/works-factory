"""工程の YAML の節の並びを、輪（loop_group）の中の入れ子までたどる（test_* でないので unittest の発見に拾われない）。

ファイルを開かないので RUNTIME_READS を持たない。影響の地図（lib/impact.py）は、宣言を持つ部品を直に import する試験を
workflows/ の下のどの変更でも選ぶ。1 つの block の YAML しか読まない試験は、宣言を持つ tests/bin/stepnames.py でなくここから
walk を読み、手元の確かめの選びを軽く保つ（持ち主の決め light-in-loop）。workflows/ の全部の YAML を読む試験は stepnames から読む。
"""
from collections.abc import Iterator


def walk(listed: list[dict]) -> Iterator[dict]:
    """節の並びの節を、輪の中の入れ子まで書いたままの形で出す（include を開かない）"""
    for node in listed:
        yield node
        if "loop_group" in node:
            yield from walk(node["loop_group"]["nodes"])
