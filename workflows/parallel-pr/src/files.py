"""並行 PR の block のファイルの名と定数（docs/design/parallel-pr.md の 1.4・1.5）。place のファイルの名はここだけが持つ。"""
import reads   # lib/

from . import fallback

ROLE = "pr-check"
NODE = "p0.parallel_pr"   # 控えの node の欄の値。読み手が古い控えと同じ形で読めるように今のまま
PR_LIMIT = 100            # gh pr list の --limit
STAGES = ("before", "after")   # port stage の語。after は修正の後の確かめ直しで、hunk を外さない

TREE = "tree.json"                       # 役の前の作業ツリーの写し
BRIEF = "pr-brief.json"                  # 役への渡し物 {node, cwd, base, changed_files, changed_source, unmeasured, request_wheres, fallback, stage}
MATERIAL = "material-pr-check.json"      # 素材の控え {role, reply, materials: {parallel_pr}}
EXCLUDED = "pr-excluded.json"            # 外す hunk {node, head, excluded: [{pr, file, start, end, why, text, sha256}]}
DRAFTS = "pr-downgrades.json"            # 申し送りの下書き [{pr, files, note}]
REJECTS = f"rejects-{ROLE}.json"         # rolekit の却下の控え
SCAN = "scan.json"                       # scan の返り {go_role, reason}（出口が読む）
READS = reads.evidence_name(ROLE)        # 読んだ証拠
READS_INDEX = reads.index_name(ROLE)     # その索引
PROMPT = f"{ROLE}-prompt-{{n}}.md"       # 組んだ指示（prompt.emit が書く）
# 読んだ証拠を集める node が落ちた時に lib/reads.guarded が置く落ちた記録（名に時刻が入るので、名の型で引く）
READS_FAILED = READS.removesuffix(".json") + "-failed-*.json"

# この block が place に書く名前つきのファイル（scan が前の run の物を名で引いて消す）。組んだ指示は n を 1 から数えて在る分だけ
OWN = (TREE, BRIEF, MATERIAL, EXCLUDED, DRAFTS, REJECTS, SCAN, READS, READS_INDEX)

# この block が元の能力から下げている所の宣言（元の downgrades.json の p0.parallel_pr の行の字）
DOWNGRADES = fallback.DOWNGRADES   # 出口が落ちた時の返り（標準ライブラリだけ）と 1 か所
