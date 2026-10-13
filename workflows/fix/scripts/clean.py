# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""節 clean（形 ""）: 修正役が残した、git が無視するファイルのうち、置き場の控え fix-ignored-before.json（prep が取った）に無かった
物だけを消す（leftovers.remove_new_ignored。前から在ったフォルダの中身と、Archon の工程の置き場 .archon/ の下は消さない）。

消したパスの全件は置き場の fix-removed.json（{removed: [...]}）。返り {ok: true, count: 消した数}。
控えが無い・読めない・git が効かない・消せない: 標準エラーに 1 行で 1（生成物の残る木で後を回さない）。
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
import boundary  # noqa: E402
sys.path.append(str(boundary.lib_root()))

import leftovers  # noqa: E402
import oneline  # noqa: E402


def main() -> dict:
    out = leftovers.remove_new_ignored(boundary.place("fix"), boundary.work_tree(), skip=boundary.SKIP)
    return {"ok": True, "count": out["count"]}


if __name__ == "__main__":
    try:
        result = main()
    except Exception as e:
        print(f"clean: {type(e).__name__}: {oneline.one_line(e)}", file=sys.stderr)
        sys.exit(1)
    boundary.returns(result)
