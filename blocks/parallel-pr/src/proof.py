"""読んだ証拠（docs/design/parallel-pr.md の 1.3 の pr-check-reads）。元は lib/judge_accept.py の pr_reads。並行 PR の役が渡し物
pr-brief.json を読んだ証拠を lib/reads の collect で集め、reads-pr-check.json と索引を書く。記録は渡し物を書いた時刻から後の、渡し物を
読んだ session の行で切る（役だけに渡す物）。受け付けの条件にしない（欠けは返りと報告に出す）。
"""
import pathlib

import jsonfile   # lib/
import reads      # lib/

from . import files


def collect(place, log, repo) -> dict:
    """返り {ok: True, missing, index_file}"""
    place = pathlib.Path(place)
    brief = place / files.BRIEF
    got = reads.collect(place, files.ROLE, [str(brief)], log, own=[str(brief)], since=reads.stamp(brief.stat().st_mtime), repo=repo)
    out = jsonfile.write(place / files.READS_INDEX, {files.ROLE: got["reads_file"]})
    return {"ok": True, "missing": got["missing"], "index_file": str(out)}
