"""line の place のファイルの名（docs/design/line.md の 1.4）。line は一番上の graph なので、place は run directory の根。名の字は
このモジュールだけが持つ。標準ライブラリだけ。KEEP の lib が自分で名を持って書く物（ghreads の github.json・entryshape の pr.md・
carry の prior-failures-in.json・answer の gates/<承認ノード>.json・policy の方針の写し）は、ここに写さない。

- START: 始めの記録（start が 1 度書く。拒んだ run も版の控えと拒みの訳を書く。起動の殻と包みと bin/ が同じ所を読むので、名と置き場を
  変えない。今の lib/startrec.py の REL）
- CARRIED: 依頼の容器の constraints（start が書く。premises の port carried に渡す）
- PLAN_CONVERGE: 計画の往復の記録（plan-out が周ごとに 1 行足して書き直す。plan-review の port prior の先）。PLAN_CONVERGE_DIR は
  往復の行の files の写しの置き場で、PLAN_CONVERGE_FILES はその中の周ごとのフォルダ（plan-converge/<k>/）
- PLAN_PRIOR: 次の周の plan の port prior の先（plan-rounds/prior-<k>.json）
- PLAN_REVIEW: 止まった案を無人の run が推しで進める周の、事前審査の返答に保留の穴を足した写し（plan-out が書き、修正の段へ渡す）
- PLAN_TALK: 設計の相談の承認ノードで人が設計し直しを求めた周の、次の plan の port prior の先（design-turn が書く。前の周の prior の
  記録を、人の求めを block に差し込んだ記録に替えた写し。n は求めの通し番号）
- TALK_ANSWERS: 設計の相談の承認ノードの答えの並び（design-turn が答えごとに書き直す。人が読む控え）
- REPLAN_PRIOR: 案の直しの plan の port prior の先（after-fix が書く）
- FINAL_GATE_MD: 開いた最後の承認ノードの文の控え
- SECTIONS・FACTS: report に pointer で渡す 2 つの形（collect が書く。docs/design/line.md の 7 節）
"""
START = "r1/start.json"
CARRIED = "carried.json"
PLAN_CONVERGE = "plan-converge.json"
PLAN_CONVERGE_DIR = "plan-converge"
PLAN_CONVERGE_FILES = PLAN_CONVERGE_DIR + "/{k}"
PLAN_PRIOR = "plan-rounds/prior-{k}.json"
PLAN_REVIEW = "plan-rounds/review-{k}.json"
PLAN_TALK = "plan-rounds/talk-{n}.json"
TALK_ANSWERS = "gates/gate-design.json"
REPLAN_PRIOR = "replan-prior.json"
FINAL_GATE_MD = "gates/final-gate.md"
SECTIONS = "report-in/sections.json"
FACTS = "report-in/facts.json"
