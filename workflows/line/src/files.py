"""line の place のファイルの名（docs/design/line.md の 1.4）。line は一番上の graph なので、place は run directory の根。名の字は
このモジュールだけが持つ。標準ライブラリだけ。KEEP の lib が自分で名を持って書く物（ghreads の github.json・entryshape の pr.md・
carry の prior-failures-in.json・answer の gates/<承認ノード>.json・policy の方針の写し）は、ここに写さない。

- START: 始めの記録（start が 1 度書く。拒んだ run も版の控えと拒みの訳を書く。起動の殻と包みと bin/ が同じ所を読むので、名と置き場を
  変えない。今の lib/startrec.py の REL）
- CARRIED: 依頼の容器の constraints（start が書く。行が無ければ空の配列。premises の port carried に渡す）
- REQUEST: 依頼の写し（start が書く。依頼のファイルが無い run は空の配列。block の port request に pointer で渡す）
- PLAN_CONVERGE: 計画の往復の記録（plan-out が周ごとに 1 行足して書き直す。plan-review の port prior の先）。PLAN_CONVERGE_DIR は
  往復の行の files の写しの置き場で、PLAN_CONVERGE_FILES はその中の周ごとのフォルダ（plan-converge/<k>/）
- PLAN_PRIOR: 次の周の plan の port prior の先（plan-rounds/prior-<k>.json）
- PLAN_REVIEW: 止まった案を無人の run が推しで進める周の、事前審査の返答に保留の穴を足した写し（plan-out が書き、修正の段へ渡す）
- PLAN_TALK: 設計の相談の承認ノードで人が設計し直しを求めた周の、次の plan の port prior の先（design-turn が書く。前の周の prior の
  記録を、人の求めを block に差し込んだ記録に替えた写し。n は求めの通し番号）
- TALK_ANSWERS: 設計の相談の承認ノードの答えの並び（design-turn が答えごとに書き直す。人が読む控え）
- NOTES: 対話モードの run の人の指摘の受け箱（人が 1 行に 1 つ足していく字のファイル。line は読むだけで書かない。design-turn が周の頭で、
  前の周までに取った数より後の行を拾う）。TALK_ROUND: 往復ごとの設計の控え（design-talk が周の終わりに書き、在りかを告げる。人が読む）
- THEME: テーマの写し（start がテーマの文か md の中身を固める。設計の段の書き手の port theme の先。3.3 節）。THEME_REQUEST: テーマを
  1 行の依頼の行にした写し（start が書く。設計の段の頭の世界の解の port request の先）
- THEME_CONVERGE: 設計の往復の記録（theme-out が周ごとに 1 行足して書き直す。形は PLAN_CONVERGE と同じ。事前審査の形 theme の port prior の先）。
  THEME_TALK・THEME_ANSWERS・THEME_ROUND は PLAN_TALK・TALK_ANSWERS・TALK_ROUND の設計の段の物（PLAN_TALK に当たる写しは書かない
  ので THEME_TALK は無い）
- THEME_APPROVED: 承認された設計の案の md の写し・THEME_DESCENDED: 承認された設計の変える所を依頼の行にした依頼のファイル（theme-descend が書く）
- THEME_NEXT_DIR: 計画の承認ノードで設計へ戻した時の、続きの run の材料の置き場（theme-return が書く。中のファイルは THEME_NEXT_*）
- REPLAN_PRIOR: 案の直しの plan の port prior の先（after-fix が書く）
- FINAL_GATE_MD: 開いた最後の承認ノードの文の控え
- SECTIONS・FACTS: report に pointer で渡す 2 つの形（collect が書く。docs/design/line.md の 7 節）
"""
START = "r1/start.json"
CARRIED = "carried.json"
REQUEST = "request.json"
PLAN_CONVERGE = "plan-converge.json"
PLAN_CONVERGE_DIR = "plan-converge"
PLAN_CONVERGE_FILES = PLAN_CONVERGE_DIR + "/{k}"
PLAN_PRIOR = "plan-rounds/prior-{k}.json"
PLAN_REVIEW = "plan-rounds/review-{k}.json"
PLAN_TALK = "plan-rounds/talk-{n}.json"
TALK_ANSWERS = "gates/gate-design.json"
NOTES = "talk/notes.txt"
TALK_ROUND = "talk/round-{k}.md"
THEME = "theme.md"
THEME_REQUEST = "theme/world-request.json"
THEME_CONVERGE = "theme-converge.json"
THEME_ANSWERS = "gates/gate-theme.json"
THEME_ROUND = "talk/theme-{k}.md"
THEME_APPROVED = "theme/approved.md"
THEME_DESCENDED = "theme/request.json"
THEME_NEXT_DIR = "theme/next"
THEME_NEXT_THEME = THEME_NEXT_DIR + "/theme.md"
THEME_NEXT_REQUEST = THEME_NEXT_DIR + "/request.json"
THEME_NEXT_COMMAND = THEME_NEXT_DIR + "/command.txt"
REPLAN_PRIOR = "replan-prior.json"
FINAL_GATE_MD = "gates/final-gate.md"
SECTIONS = "report-in/sections.json"
FACTS = "report-in/facts.json"
