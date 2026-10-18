"""判定のブロック（workflows/judge/）が隣に書くファイル（docs/design.md の「サブグラフの出力の約束」の judge の出力の欄の先）の名の住処。

名の字はここだけが持つ（層の地図 docs/layers.json の homes が judge の住処にここを宣言し、照らし beside はここを数えない）。判定の書き手と
受け付け（judge_accept・premises・judgeverify・prcheck・purpose・headdepth・worldmark・diverted と、足し欄の種の表 marks）は、ここの
定数を import して引く。判定の外の読み手は名を持たず、判定の出力の欄のポインタで受ける（#680）。

名は fix の lib/fixbeside.py に倣い「判定の隣（beside）」から採った。fixbeside と違って欄 → ファイルの表（PORTS・FIRST_PORTS）は
受け付けの lib/judge_accept.py に置く: 表は判定の隣でない欄の先（目的の解き方 purpose_means は marks の種 means、決定記録の突合
decisions は policy が名を持つ）も並べるので、ここに置くと住処が書き手を import する向きになる。ここは何も import しない。
"""
PREMISES_FILE = "premises.json"                # 受け付けた実測役の返答 {"constraints": [...]}（欄 premises）
VERIFY_FILE = "judge-verify.json"              # 判定の裏取りの申し送り（欄 verify）
PR_EXCLUDED_FILE = "pr-excluded.json"          # 並行 PR の任せ先が外す hunk {node, head, excluded}（欄 pr_excluded。marks の種 pr）
MATERIALS_FILE = "materials.json"              # 素材の状態（素材の名 → {status, …}。欄 materials）
DEPTH_FILE = "depth-head.json"                 # run の頭の深さの控え（欄 depth_record）
PURPOSE_REVIEW_FILE = "purpose-review.json"    # 目的の監査の役の受けた返答（欄 purpose_review）
ANSWER_TIES_FILE = "answer-ties.json"          # 依頼の答えと作り直しの行を問い・単位に結んだ行（欄 answer_ties。marks の種 answers）
REVIEW_LENSES_FILE = "local-review-lenses.json"   # 局所レビューで確かめられなかったレンズの控え（欄 review_lenses）
PR_DRAFTS_FILE = "pr-downgrades.json"          # 並行 PR の担当への申し送りの下書き [{pr, files, note}]（欄 pr_drafts）
WORLD_STATE_FILE = "world-state.json"          # 世界の解の段の控え（欄 world_state）
REJUDGE_EXIT_FILE = "rejudge-exit.json"        # 再審の出口 {ok, reason, passes, verdicts, unsettled, …}（欄 rejudge_exit）
REJUDGE_DIFF_FILE = "rejudge-diff.json"        # 往復ごとの単位の前後の差 [{round, pass, verdict, changed, …}]（欄 rejudge_diff）
