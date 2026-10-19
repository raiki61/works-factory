# graph の設計書: line（メイングラフ）と chain（周の鎖）

- 何の話か: 工場のメイングラフ `works-factory-line` を、block を `include:` で並べる graph `blocks/line/` に作り直す設計（組み込みの PR で作る。README の 11.3 の 1）。あわせて、line を周ごとに子の run として起こす `works-factory-chain` の移しを 12 節に短く書く。型は [README.md](README.md) の 1 節（graph の定義と形の直し 7）・4 節・8.7 節に従う。判定と独立の目のまとめ（judge・eyes の graph）は [judge-eyes.md](judge-eyes.md)。
- 決めたこと: line は配線と流れの決めだけを持つ。持つのは、どの block をいつ回すか（`when:`）・承認ノード 4 つ・計画の往復の記録と止めと安全の上限・一度だけの include（案の直し・2 度目の修正・再審・修正の後の並行 PR の確かめ直し）・深さの表（段 → 回す物）と、fix と delta-review の間の 1 回の上げ直し・無人の方針・始めの記録（line だけが書き、block には port の値として配る）・報告への受け渡し（`sections`・`facts`）。AI の node は持たない。README 8.7 の「今の工場の穴」3 つは 8 節で決めた（並行 PR を修正の後に 1 度だけ確かめ直す・fix に外した hunk を渡す・入力 `gates` を足す）。
- 持ち主（リポジトリの owner）に求めること: 1 つ。入力 `gates`（変異の検算を合流でまとめる道）を line に足すこと（8 節の 3）。前の棚卸しで「段 3 で変異の検算と一緒に持ち主に聞く」と決めた件（`docs/plans/2026-10-13-capabilities/line.md` の S37）なので、既定の振る舞いを変えない形で足し、通すかを確かめてもらう。ほかは README・持ち主の決め・今のコードで決まった（13 節）。決まらない物は 15 節。
- 読む人: 組み込みの PR で line と chain を書く実装の役。block の設計書の書き手（自分の block の port を line がどこから配るかを 1.6・4〜7 節で引く）。

この文書の語は README の頭の物を使う（block・graph・port・place・prep・accept・pointer・埋め・Archon の YAML の鍵・form の書き方）。ほかに:

- 始めの記録: line の `start` が run の頭に 1 度書く記録（今の `lib/startrec.py` の形。run directory の `r1/start.json`）。block はこれを読まない（README 4.2・4.3）。
- 配る値: 始めの記録から `start` が引いて、出力の欄 `ports` に並べる値。block の port に `with:` で渡す。
- 受け皿: 埋め P8（include の返りを受け直す script の node。`<include の id>-out`）。返す node が落ちても受け皿が飛ぶだけにして、`all_done` で集める node を落とさない（今の `workflows/line/scripts/returned.py`）。
- 返し: 埋め P2（飛ばされうる値を `{from, if_skipped: null}` で受けて明示の値で返す script の node。include の `with:` は束ねを読まないため）。
- 段: run の頭の深さ（軽量・標準・重厚。head-depth の出力 `tier`）。単位の深さ: 判定の単位ごとの軽量か標準（今の `depth.unit_depth`）。
- 今の line: `workflows/line/`（YAML 1253 行・script 25 本）。今の棚卸し: `docs/plans/2026-10-13-capabilities/line.md`（L-E・L-G・L-W・L-D の行。組み込みで消える表なので、この文書の 9 節が行き先を持つ）。

## 1 graph の全体

### 1.1 役

修正依頼か差分を受け、block を並べて直しを作り、承認ノードで人に見せ、差分を封じて置き、どの道でも報告を出す。判定と独立の目は、それぞれ 1 つの include（judge と eyes の graph）で呼ぶ。line が決めるのは流れだけで、観点の判断と計算（測る・照らす・AI の役）は block に在る。例外は README が line に置くと決めた 4 つ: 承認ノードと無人の方針（1.2 の U）・深さの表と上げ直し（1.2 の D）・計画の往復の記録と止め（形の直し 6）・報告の結末の事実の読み分け（`facts`。report の設計書の 1.6）。

### 1.2 port

入力（YAML の `inputs:`。今の line の 16 個と、足す 1 個 `gates`）。form は README の 4.1 の物（`text`・`file`・`json(<形>)`・`flag`・`choice(a|b)`）。語を受ける入力は `text` にする（`start` が知らない語を名指して拒む今の文を残すため。`choice` は Archon が照らさず、拒む所が増えるだけ）。説明の字は今の YAML の `description` を、作り手を名指さない形で写す。

- `request`: `file: 修正依頼のファイル（findings の JSON の配列か {findings, pr, issue, answers, prior_failures, constraints} の形）。相対なら対象の根から。依頼の行か差分の少なくとも 1 つが要る`。既定 `""`。
- `base`: `text: 差分の根を名指す版（枝・タグ・commit）。差分の根は base と HEAD の merge-base。pr と一緒には名指さない`。既定 `""`。
- `pr`: `text: PR の番号。base の版と head は run の中で gh で読む。base と一緒には名指さない`。既定 `""`。
- `spec`: `text: 仕様の段を挟むか（空か on）。依頼の文が要り、無人の run・固定材料とは組めない`。既定 `""`。
- `test_cmd`・`tdd_suite`・`final_gate`・`unattended`・`design_only`・`thickness`・`features_off`・`features_on`・`policy_md`・`fix_fixture`・`lang`・`deliver`: 今の説明のまま（form は `text`）。
- `gates`（足す）: `text: 変異の検算をまとめる道の語（空か merge）。merge は合流した版でまとめて撃つ run で、ゲートの検算の観点を回さない。ほかの語は拒む`。既定 `""`（8 節の 3）。

出力（`returns: result`・`outcome_field: fixed`）。欄の名は今のまま（`bin/apply`・chain・通しの試験が今の名で読む。report の設計書の 1.6）:

- `fixed`: 結末が `fixed` か `fixed_needs_check` の時だけ真。
- `ok`・`outcome`・`stop_reason`・`next_request`・`prior_failures`: report の返りのまま。
- `report`・`report_ai`: report の返りの `machine`・`human` を今の名で写す（report の設計書の 1.6）。
- `apply`（`{ok, hash, diff, reason}` か null）・`sealed`（`{ok, hash, diff}` か null）・`r2_status`（字か null）・`final_answer`（`{decision, text, asked}` か null）・`spec_questions`（整数）・`children`（`{cleaned, left, error}` か null）: 今の `result.py` のまま。
- 形の検査（README 7.1 の 8）は返す node に欄 `outcome_field`（`fixed`）と `report` が在るかの yes/no で、今の `report`（機械の報告の pointer）で通る。line は一番上の graph で、line を include する graph は無い（chain は `workflow:` で起こし、`outcome` などを読む）ので、line 自身の報告の行は `report` の欄でなく `sections` の節 1（7.1）に入れる。欄の名は変えない（13 節）。

### 1.3 node の並び（`blocks/line/works-factory-line.yaml`）

番号は流れの順。`<<: *receiver` は受け皿（今の YAML の錨と同じ形。`with: {got, names}`）。include の `with:` の中身は 4〜7 節と 1.6。script の node はどれも `runtime: uv`・`mutates_checkout: false`・uv の頭の宣言 4 行。

0. `testcmd`（script）→ `testcmd-stop`（`cancel:`。`when: $testcmd.output.stop == true`）: 今のまま（9 節の L-E）。
1. `start`（script。`depends_on: [testcmd]`・`when: $testcmd.output.stop == false`）: 入力を確かめ、始めの記録を書き、配る値を返す（1.6）。
2. `gate-start`（`wait:`。`when: $start.output.ask == true`）→ `answer-start`（script `gate_answer`。`trigger_rule: none_failed_min_one_success`）: 起動の承認ノード（2 節の 1）。
3. `test-gate-base`（include `works-factory-test-gate`。`when: $answer-start.output.go == true && $start.output.from_fixture == false`）→ `test-gate-base-out`（受け皿）。
4. `judge`（include `works-factory-judge`。`when: $test-gate-base.output.ok == true`）→ `judge-out`（受け皿）。
5. `tiers`（script。`depends_on: [judge]`・`when: $judge.output.ok == true`）: 段 → 回す物の表を引く（5.1）。
6. `owed`（script。`depends_on: [judge, answer-start]`・`when: $judge.output.ready == true`。計画の周の前の支度: 1 回目の周が修正案の役を起こすかと、事前審査に渡す記録された方針の行 `recorded`）→ `structure`（include `works-factory-structure`、`mode: before`。`when: $owed.output.owed == true`）→ `structure-out`（受け皿）→ `structure-in`（返し。`depends_on: [judge, structure]`・`none_failed_min_one_success`・`when: $judge.output.ready == true`）。
7. `independent-design`（include。`depends_on: [judge]`・`when: $judge.output.ok == true`）→ `independent-design-out`（受け皿）→ `design-in`（返し。`depends_on: [judge, independent-design]`・`none_failed_min_one_success`・`when: $judge.output.ok == true`）。
8. `plan-rounds`（`loop_group`。`max_iterations: 20`。`depends_on: [judge, structure-in, design-in, tiers]`。`when: $judge.output.ready == true && $owed.output.stop_reason == '' && $structure-in.output.stop_reason == ''`）。本体は `plan`（include `works-factory-plan`）→ `plan-review-run`（include `works-factory-plan-review`。`depends_on: [plan]`・`when: $plan.output.ok == true`）→ `plan-out`（script。`depends_on: [plan, plan-review-run]`・`none_failed_min_one_success`）。`until_bash: 'done=$plan-out.output.done; [ "$done" = "true" ]'`（3 節）。→ `plan-rounds-out`（受け皿）。
9. `ask-before-fix`（script。`depends_on: [plan-rounds]`）→ `gate-before-fix`（`wait:`。`when: $ask-before-fix.output.open == true`）→ `answer-before-fix`（script。`none_failed_min_one_success`）: 修正前の承認ノード（2 節の 2）。
10. `fix-in`（script。`depends_on: [answer-start, test-gate-base-out, judge-out, tiers, structure-out, design-in, plan-rounds-out, ask-before-fix, answer-before-fix]`・`none_failed_min_one_success`）: 修正の段へ運ぶ値を 1 か所に集め、単位の深さと `skip_rerun` を引き、固定材料を写す（4.1・5.2）。
11. `fix`（include `works-factory-fix`、`mode: whole`。`when: $fix-in.output.go == true`）→ `fix-out`（受け皿）。
12. `after-fix`（script。`depends_on: [fix]`）: 案の直しを差し込むかと、案の直しに渡す前の周のファイル（4.2）。
13. `raise`（script。`depends_on: [fix-in, fix, after-fix]`・`when: $fix-in.output.go == true`）: 修正の後の上げ直し。run に 1 回、1 回目の修正の段と差分の審査の間（5.3）。
14. 1 回目の段の差分の審査: `lens`（include `works-factory-lens`。`depends_on: [raise]`・`when: $raise.output.checks == true && $fix.output.ok == true`）→ `lens-out`（受け皿）→ `lens-in`（返し。`depends_on: [raise, lens-out]`・`none_failed_min_one_success`）→ `delta-review`（include `works-factory-delta-review`。`depends_on: [lens-in]`・`when:` は `lens` と同じ）→ `delta-review-out`（受け皿）。
15. 案の直し（一度だけ。4.2）: `replan`（include `works-factory-plan`。`depends_on: [after-fix, delta-review-out]`・`none_failed_min_one_success`・`when: $after-fix.output.replan == true`。作業ツリーを変える手直しの後に回す）→ `replan-out`（受け皿）→ `replan-review`（include `works-factory-plan-review`。`when: $replan.output.ok == true`）→ `replan-review-out`（受け皿）→ `ask-replan`（script）→ `gate-replan`（`wait:`）→ `answer-replan`（script。`none_failed_min_one_success`）→ `refix-run`（include `works-factory-fix`、`mode: whole`。`when: $answer-replan.output.go == true`）→ `refix-run-out`（受け皿。足す）。
16. 2 度目の段の差分の審査（2 度目の修正が走った時だけ。delta-review と lens の設計書の 1.6「2 度目の修正の段も、もう 1 回 include する」）: `lens-2` → `lens-2-out` → `lens-2-in` → `delta-review-2` → `delta-review-2-out`。形は 14 と同じで、`when:` は `$raise.output.checks == true && $refix-run.output.ok == true`、`with:` は 2 度目の fix の出力から。上げ直しはしない（5.3）。
17. `fixed`（script。`depends_on: [fix-in, after-fix, raise, fix-out, lens-out, delta-review-out, replan-out, refix-run-out, lens-2-out, delta-review-2-out]`・`none_failed_min_one_success`）: 2 つの修正の段と、段ごとの差分の審査を合わせる（4.3）。
18. 修正の後の読むだけの 3 つ（互いを待たない。`depends_on: [fixed]`。作業ツリーを変える手直しの後に置き、読むだけの役の「作業ツリーを変えていない」の照らしと重ねない）:
    - `parallel-pr-after`（include `works-factory-parallel-pr`。`when: $start.output.ports.entry != '' && $fixed.output.diffed == true`）→ `parallel-pr-after-out`（受け皿）。8 節の 1。
    - `rejudge`（include `works-factory-diagnose`。`when: $fixed.output.rejudge == true`）→ `rejudge-out`（受け皿）。4.4。
    - `spec-check`（include `works-factory-spec`、`mode: check`。`when: $start.output.ports.spec == true`）→ `spec-check-out`（受け皿）。
19. `judged`（script。`depends_on: [fixed, rejudge]`・`none_failed_min_one_success`）: 判定（再審が走れば再審）を後ろへ渡す（4.4）。
20. `test-gate-final`（include。`depends_on: [judged, parallel-pr-after-out, spec-check-out]`・`none_failed_min_one_success`・`when: $fixed.output.go == true && $judged.output.stop_reason == ''`）→ `test-gate-final-out`（受け皿）。上げ直しの止め（`raise` の `works:line-script`）は `fixed.go` が偽にして運ぶ（`raise` は直す物が無い周に飛ぶので、`when:` で直に読まない）。
21. `eyes-in`（script。`depends_on: [test-gate-final]`）→ `eyes`（include `works-factory-eyes`。`depends_on: [eyes-in]`）→ `eyes-out`（受け皿）。
22. `merge-seal`（include `works-factory-merge`、`mode: seal`。`depends_on: [eyes-out]`・`when: $fixed.output.no_fix == false`）→ `merge-seal-out`（受け皿。id は `bin/apply` が名指すので今のまま）。
23. `ask-final`（script。`depends_on: [eyes-out, merge-seal-out]`・`none_failed_min_one_success`）→ `gate-final`（`wait:`）→ `answer-final`（script `gate_answer`。`none_failed_min_one_success`）: 最後の承認ノード（2 節の 4）。
24. `merge-apply`（include、`mode: apply`。`depends_on: [answer-final]`・`when: $answer-final.output.go == true && $fixed.output.no_fix == false`）→ `merge-apply-out`（受け皿。id は今のまま）。
25. `collect`（script。全部の受け皿・返し・承認の答え・line の script の node に `depends_on`。`trigger_rule: all_done`・`always_run: true`）: `sections` と `facts` を組んで place に書く（7 節）。
26. `report`（include `works-factory-report`。`depends_on: [collect]`・`trigger_rule: all_done`）。
27. `sweep-children`（script。`depends_on: [report]`・`all_done`）: fix の組の子の run の作業ツリーの後始末（今のまま。1.5）。
28. `result`（script。`depends_on: [collect, report, sweep-children]`・`all_done`・`always_run: true`）: line の返す node。

`merge-seal` は `eyes` でなく `eyes-out` に依る: eyes の graph の返す node が落ちても `merge-seal` の `with:` が落ちた node を読まないため（読めば Archon が誤りで止める）。受け皿が飛べば封じも飛び、最後の承認ノードが「差分を封じられなかった」を開ける理由にする（閉じた側に倒れる）。今は `$eyes.output.ok` を直に読んでいた（eyes の返す node は落ちない作りだった）。

### 1.4 place のファイル（line が書く物と書く順）

line は一番上の graph なので、place は run directory の根（README 4.4。include の道が空）。ファイルの名は line の `src/files.py` だけが持つ。

1. `r1/start.json`（始めの記録。`start` が 1 度書く。拒んだ run も版の控えと拒みの訳を書く。今の `startrec.REL` のまま。起動の殻と包み〔`graph_map` の読み〕と `bin/` が同じ所を読むので、名と置き場を変えない）。
2. `github.json`（名指した PR・issue の gh の読み。0600。在れば読み直さない。今の `ghreads.place`）・`pr.md`（PR の題と本文。`entryshape.write_pr_file`）・`prior-failures-in.json`（依頼の prior_failures。`carry.place_prior`）・`carried.json`（依頼の容器の `constraints`。足す。premises の port `carried` に渡す）・方針の写し（`policy.freeze`。今のまま）。どれも `start` が書く。
3. `gates/gate-start.json`（起動の承認ノードの答え。`answer.taken`。同じ承認ノードは書き直す）。
4. `plan-converge.json`（計画の往復の記録。`plan-out` が周ごとに 1 行足して書き直す。plan-review の port `prior` の先。3 節）・`plan-converge/<k>/`（往復の行の `files` の写し）・`plan-rounds/prior-<k>.json`（次の周の plan の port `prior` の先。3 節）。
5. `gates/gate-before-fix.json`。通した答えが方針の文書の変化を通していれば、`r1/start.json` の欄 `policy` を固め直した版で書き直す（今の `before_fix_answer.carry_policy`。書き直すのは始めの記録の書き手の line だけ。2 節の 2）。
6. 固定材料の写し（`fix-in` が修正に入る時に 1 度だけ。`fixture.noted_capture`。写せなくても止めない）。
7. `replan-prior.json`（案の直しの plan の port `prior` の先。`after-fix` が書く。4.2）・`gates/gate-replan.json`。
8. `gates/final-gate.md`（開いた最後の承認ノードの文の控え）・`gates/gate-final.json`。
9. `report-in/sections.json`・`report-in/facts.json`（`collect` が書き、report に pointer で渡す。7 節）。

### 1.5 コードの置き場

- `blocks/line/scripts/`: node ごとに 1 本（`testcmd`・`start`・`gate_answer`・`returned`・`relay`〔返しの 4 つ `structure-in`・`design-in`・`lens-in`・`lens-2-in`。今の `structure_in.py` の形を 1 本にした物。`with:` の `field` で運ぶ欄を名指す〕・`tiers`・`owed`・`plan_out`・`ask_before_fix`・`before_fix_answer`・`fix_in`・`after_fix`・`ask_replan`・`replan_answer`・`fixed`・`raise_depth`〔node `raise`。名を `lib/` と重ねない〕・`judged`・`eyes_in`・`ask_final`・`collect`・`sweep_children`・`result`）。どれも `ports` の口で入力を読み、`src/` を呼ぶだけ。
- `blocks/line/src/`（package `src`）:
  - `files.py`: 1.4 のファイルの名。
  - `startrec.py`・`fixture.py`・`testcmd_check.py`・`versions.py`: README 9.2 の MOVE（今の `lib/` の同じ名のモジュール）。ただし `startrec` の読む口は KEEP の lib（`headdepth`・`suitewrite`・`conflict`・`runreport`）がまだ読むので、組み込みで使い手を数え、残る使い手があれば読む口だけを `lib/` に残す（15 節）。
  - `deal.py`（足す）: 始めの記録から配る値を引く（1.6）。
  - `gates.py`: 承認ノードの決め（今の `lib/gatepolicy.py` の全部と、`lib/gatemarks.py` の承認ノードの決めの部分〔開くか・項目の行・軸・通した行・無人の抜け方〕、`lib/gate_axes.py`）。問いの行の形（`ASKING`・`asks_human`・推しの尾の字の形）と承認ノードの文の組み立て `gate_text` は KEEP の `lib/gatemarks` を引く（README 9.3）。
  - `final.py`: 最後の承認ノードの開ける理由と文（今の `ask_final.py` の中身）。
  - `tiers.py`: 段 → 回す物の表と単位の深さと上げ直し（今の `lib/depth.py` の `TIERS`・`unit_depth`・`decide_doc`・`raise_doc`・`skip_reason`・`omits`・`merges`・`tier_adds`・`tier_auto`・`lines` と、`lib/latedepth.py`）。段の語 4 つ（`LIGHT`・`STANDARD`・`HEAVY`・`HEADS`）は先に `lib/headdepth` へ移す（README 9.3・11.3 の 5）。
  - `rounds.py`: 計画の往復の記録と止め（今の `lib/converge.py` の `read`・`add_pass`・`record_pass`・`decide`・`proceeds`・`capped`・`stuck_keys`・`stuck_reason`・`lines`・`open_items`・`held`）。項目の読みと穴の札の形（`planned_units`・`central` など、plan と plan-review も使う物）は KEEP の `lib/converge` に残す（README 9.3）。
  - `stages.py`: 2 つの修正の段の合わせ（今の `fixed.py` の中身と、組み込みで DELETE される `fixbeside` の読み口のうち line が読む物〔`stage`・`late_records`・`read`〕。fix の設計書の 1.2 の「`fixbeside.read`・`records` は組み込みで line の src/ に移る」）。
  - `facts.py`・`sections.py`: report へ渡す 2 つの形を組む（7 節）。
- 使う `lib/`（KEEP。README 9.3）: `answer`・`carry`・`entry`・`entryshape`・`runbranch`・`green_cert`・`declared_checks`・`suitewrite`・`cite`・`conflict`（行の形）・`replan`・`ghreads`・`forge`・`protect`・`seal`・`listcut`・`itemcommits`・`planmarks`・`querytest`・`outpurpose`・`policy`・`headdepth`・`gatemarks`（行の形）・`report`・`runreport`（軽くした物）・`stopby`・`tree_run`・`userenv`・`worldmark`・`structmark`・`oneline`・`jsonfile`。
- 使う埋め: `childsweep`（`sweep-children`。今の `reader_of` が fix の中の node の名 `join` を持つので、「子を起こした node と同じ include の中の node が全部 completed になるまで消さない」に替える。README 1.3 の歩かせ 4）・`child_pointer`（chain）。
- 作り直しの間は line を作らない（今の line が動く）。line は組み込みの PR で書く（README 11.3 の 1）。その PR で MOVE の元を消す。

### 1.6 始めの記録と配る値

始めの記録は今の形（`lib/startrec.py`）に欄 `gates` を足した物。書き手は `start` だけで、`answer-before-fix` が欄 `policy` を 1 度書き直す（1.4 の 5）。block は読まない。`start` は書いた記録から下の値を引いて出力の欄 `ports`（object）に並べ、node は `$start.output.ports.<名>` で読む。固定材料の run は、取り込んだ記録（`fixture.adopt` が今の run の id・入力・版で書き換えた物）から同じ式で引く（値の源を 1 つにする）。拒んだ run の `ports` は全部の欄を空の値で持つ（後ろは `when:` で飛ぶ）。

- `request`: 依頼のファイルの絶対パス。依頼の無い run は `"[]"`。読み手: judge の graph（head-depth・spec・parallel-pr・premises・purpose・world・prior-decisions）・test-gate の `request`・`parallel-pr-after`。block は `requestrows` で読み、下書きの行と知らない鍵を拒む（`start` も `carry.parts` で先に拒んでいる）。
- `request_file`: 同じ絶対パスか `""`（`file` の form の port 用）。読み手: independent-design・fix・merge（apply）・eyes の graph（r2〜r4）。
- `pr_text`: PR の番号・題・本文を並べた文（今の `judge_accept.pr_file_text` の字。line の `deal.py` へ写す）。PR の無い run は `""`。読み手: purpose・spec。
- `carried`: `carried.json` の pointer か `"[]"`。読み手: premises。`carried_measured`（flag）: その中に `measured_how` が `carry.CARRIED_HOW_HEAD` で始まる行が在るか。読み手: `raise`（5.3）。
- `base`: 入口の差分の根（`startrec.diff_base`）。読み手: judge の graph（素材の 11 本・parallel-pr）・independent-design・eyes の graph（r1〜r4）。
- `base_rev`: 修正前の HEAD（`startrec.head_rev`）。読み手: test-gate・merge・independent-design の `head`・lens・delta-review・`parallel-pr-after`・eyes の graph（structure after の `base`）。
- `request_origin`: 依頼の行の出どころの名（判定から入る run は下の `entry` と同じ字、ほかは「人の依頼（<依頼のファイル>）」。今の `judge_accept.request_batches` の字）。読み手: diagnose の `request_origin`。
- `base_label`（`startrec.diff_base_label`）・`review_rev`（`startrec.read_rev`）: 読み手: r2 の `base_label`・plan と plan-review の `review_rev`。
- `entry`: 判定から入る run の出どころの文。入口の差分が空で依頼の行が 1 件以上の時だけ `f"人の依頼（{request_file か '依頼の行'}）"`、ほかは `""`（今の `judge_accept.due_view` の `record.process.request_entry.origin` と同じ字）。読み手: 素材の 11 本・`parallel-pr-after` の `when:`。
- `lang`: 始めの記録の `lang`。どの include にも渡す（README 5.3。空の時の扱いは 15 節）。
- `web`: いつも `"on"`。今の line に web を切る入力は無く、網が無い時は world の block が自分で知識だけの行に倒す（world の設計書の 1.2）。world の設計書の 1.6 は「`features_cut` から引く」と書くが、機能の語に web は無い（`lib/entry.py` の `FEATURES`）。
- `world`（flag）: `features_cut` に `world` が無いか。読み手: judge の graph（world を回すか）。
- `spec`（flag）: `input.spec`。読み手: judge の graph（spec write）・head-depth の `spec`・`spec-check` の `when:`。
- `has_checks`（flag）: `test_cmd` か `tdd_suite` が空でない（今の `depth.has_checks`）。読み手: head-depth・`fix-in`。
- `thickness`: head-depth の `choice(auto|light|standard|heavy)` に写した語（空・自動 → auto、軽量 → light、標準 → standard、重厚 → heavy）。`forced`: 単位の深さを固定する語（空・自動 → 空、軽量・標準・重厚 → その語。`fix-in` が `decide_doc` に渡す）。
- `design_only`（flag）・`unattended`（flag）: 読み手: head-depth・fix の `unattended`・承認ノードの script。
- `policy`: 固めた方針の写しのパス（`policy.frozen_copy`）か `""`。読み手: structure・independent-design・plan・plan-review・fix・eyes の graph。`answer-before-fix` が固め直した時は、その後ろの読み手に `$answer-before-fix.output.policy` を渡す（2 節の 2）。
- `test_cmd`・`tdd_suite`・`reuse_dir`（`tree_run.reuse_dir`）・`user_env_dir`（run directory の根）・`run_id`（test-gate と fix の `reuse_key`）・`deliver`・`gates`。
- `parallel`（flag）: `features_cut` に `fix_lanes` も `tdd_lanes` も無い。読み手: fix の `parallel`。
- `verify_by_tier`（object）: 段ごとに判定の裏取りを回すか（`{軽量: bool, 標準: bool, 重厚: bool}`。`entry.switch(記録, "judge_verify", tier_adds(段)) == "on"` を段ごとに引いた物）。読み手: judge の graph（judge-eyes.md の 1.3）。段の表を judge の graph に持たせないため、line が表を引いた結果を値で渡す（13 節）。
- `tree_named`: 事前審査の木の名指し（`features_on`・`features_off` の `review_tree` の名指しだけを読んだ `on`・`off`、名指しが無ければ空）。読み手: `tiers`。
- `takes_push`（flag）: 無人の run（`gatepolicy.unattended_of`）。読み手: plan の `takes_push`。
- `request_scope`（flag）: 入口の差分が空か（`startrec.diff_empty`）。読み手: test-gate の `request_scope`。
- `prior_rows`: 依頼の容器の `prior_failures` の行の配列（`start` が `prior-failures-in.json` に置いた物の値）。読み手: plan の `prior_failures`。diagnose は依頼の容器から自分で読むので渡さない（diagnose の設計書の 1.2）。
- `request_answers`: 始めの記録の `answers`（依頼が先に持っていた答え）の配列。読み手: fix の `request_answers`・plan の `answers`・`eyes-in`（記録された方針の行）。

`start` のほかの出力は今のまま（`ok`・`stop_reason`・`reason`・`record`〔始めの記録の pointer。line の script だけが読む〕・`prior_failures`・`ask`・`gate_text`・`unattended`・`design_only`・`final_gate`・`from_fixture`・`fixture`）。`spec` と `reuse_dir`・`user_env_dir` は `ports` へ移す。

## 2 承認ノード（4 つ。どれも `wait:` の `attention`・`form: select`・`options` は `approve`・`continue`・`stop`・`reject`）

仕様の承認ノードは spec の block の中に在り、line は持たない（README 8.1）。答えの受け方は 4 つとも `lib/answer.py` の `taken`（承認ノードが飛ばされたら前の node の決めをそのまま渡し、answer は null。通す語なら go、ほかの語は `human:<承認ノード>` で止める。一言が空なら既定の文。答えを `gates/<承認ノード>.json` に書く）。

1. 起動の承認ノード `gate-start`: `start` が `ask`（無人の run でない）を返した時に開く。文は `start.gate_text`（今の冒頭 3 行・入口の文・固定材料の行・段・機能・最後の承認ノードの開き方・出口・テストの注・答え方 2 行）に、`gates` の句（merge の時だけ「変異の検算: 合流した版でまとめて撃つ（gates=merge）——この run ではゲートの検算を回さない」）を足す。
2. 修正前の承認ノード `gate-before-fix`: `ask-before-fix` が決める（今の `ask_before_fix.py` の決まりのまま）。
   - 計画ができていない → 開かず、修正へも進まない。
   - 必ず開く: 往復が止まった（3 節の `stalled`）・設計だけの run。この 2 つは承認ノードの項目に「設計だけ」の種類の行を 1 行足して開く。項目の中に同じ種類の行（止まった理由を尾に持つ行）が既に在れば、その行を足さない（同じ行を 2 度載せない。L-D19・P249）。開くことは変わらない。
   - 開く: 4 つの軸（自明・世界の解・汚くない・やりすぎでない）のどれかが通らない・事前審査が人に聞くと言った・承認ノードの項目が在る。軸の訳は項目の尾に在るので、軸の行は項目が無い時だけ足す。
   - 軸と項目の行は line が組む（今は事前審査が `gate_axes`・`questions`・`gate_passes` を返していた。README 9.2 で `gate_axes` と `gatemarks` の決めの部分は line。plan-review の設計書の 1.6 の「line が往復ごとに持つ事」）。材料: 最後の往復の事前審査の `asks`（`decided` が偽か `why` の在る行は項目、`decided` が真で `why` の無い行は聞かずに通す行）と `deviations`（`world` の `why` の在る行は項目）・構造の目の人に上げる行（`structure-in`。今の `design_items`）・判定の問いの台帳の問い（`gatemarks.ledger_at`）・設計だけ・止まりの行・方針の文書の変化（固めた写しと今の方針の文書の版を `policy.version` で比べる。今の事前審査の照らしを line が持つ）。4 つの軸は `asks` と `deviations` の `why` を軸ごとに集める（今の `gate_axes.gather`）。聞かずに通した行は出どころつきで `passes` に返す（L-G18・L-G19。最後の承認ノードと報告が並べる）。定石からの外れと、構造の目が上げた問いは 1 度だけ聞き、人が continue した同じ文は聞き直さない（今の `gatemarks._continued`。L-G29）。
   - 返り: `open`・`go`・`stop_reason`・`text`・`deferred`・`asked`・`pushed`・`passes`。
   - `answer-before-fix`: 答えの `asked` に載せた行を付ける（fix の `answers` が問いの単位を直す義務に戻す。S46）。通した答えが方針の文書の変化の項目を通したなら、今の方針の文書を固め直し（`policy.freeze`）、始めの記録の `policy` を書き直し、返りの `policy` にその写しのパス（ほかは `$start.output.ports.policy` の値）を返す（今の `carry_policy` と `boardview.passed_version`。固め直す決めは line に移った）。
3. 案の直しの承認ノード `gate-replan`: `ask-replan` が決める（今の `ask_replan.py` のまま）。直した項目ごとに承認済みの項目と約束の欄を比べ（`planmarks.contract_diff`）、変わった項目と、事前審査が人に聞くと言った時に開く。読めない計画は聞く側に倒す。文は項目ごとの節（約束の欄の変化・人に聞く穴・その項目を誤りとした申し出の文と裁定の文〔fix の `conflicts`。字のまま〕・前と後の項目の JSON）。`answer-replan` は 2 度目の修正に渡す `fix_answers`（修正前の条件が先・案の直しの一言が後）・`fix_notes`（採った項目の事前審査の穴のうち人に聞く種類でない物）・`fix_ripple`（作り直した波及の一覧。作れなかった時だけ 1 回目の物）と、足して `skip_rerun`（5.2）を返す。
4. 最後の承認ノード `gate-final`: `ask-final` が決める（今の `ask_final.py` の決まりのまま。`src/final.py`）。開ける理由の列を 1 つ組み、開くかと冒頭の 1 行目をこの列だけから作る。
   - 開き方に依らず開く（must）: 守りのパスに当たった・確かめられなかった（merge の seal の `protected_hits`）・書き換えを許したテストを触った・人に回した食い違いの申し出・申し出の控えを読めない・修正の段の控えを読めない・承認の後に受け入れ条件のテストが変わった（spec の check の `questions`。照らせなかった時は「照らせなかった」と言う）。
   - 開き方で開く理由: 最後のテストが緑でない・修正役が人に回した物・独立の目が通さなかった（eyes の `r1`〜`r4` の行。語は `gatemarks.REVIEW_WORDS`）・前提の検算が人に上げた（eyes の `premise_check` が escalate。E36）・申告と数え直しが合わない単位・考えの住処の柵の数が増えた（structure after の行）・人に聞いている問い（eyes の `questions` と台帳）・止めずに残った異議（再審が採らなかった）・差分を封じられなかった・足す: 修正の後の並行 PR の確かめ直しが重なりを見つけた・確かめ直せなかった（8 節の 1）。
   - 判定の役が保留にしたままの問いは冒頭と本文に見せるが、開ける理由に数えない（L-G36）。
   - 開き方は `gates.opens`（always はいつも・when_needed は理由が在る時・protected_only は守りのパスの当たりの時）。
   - 本文の節の並びは今のまま（守りのパス → 申し出 → 修正役が人に回した物 → 減っていない単位 → 例で試していない単位 → 閉鎖の数え直し → 同じ run で直した案の項目 → 最後のテストの一式と修正前のテスト → 回さなかった試験 → ログ・作業ツリー → 差分の審査の穴と手直し → 異議と再審 → 構造のブロックが落ちた周 → 直した後の実測 → 修正前に通した行と往復 → 許したテストの変更 → 取り込むと消えるファイル → 独立の目と R2 の入力の控え → clean とレンズ → 残り → 承認し直すかの問い → 人に聞いている問い → 保留と答えた問いと当たらなかった答え → 出口 pr の時の push 先の 1 行）。足す節: 「修正の後の並行 PR の確かめ直し」を独立の目の前に置く。
   - 読む物は修正の事実（`fixed` と、その `stages` の段ごとの fix・lens・delta-review の got）・試験（`test-gate-final-out`）・目（`eyes-out`）・封じ（`merge-seal-out`）・判定（`judged`）・仕様（`spec-check-out`）・往復の記録（`plan-converge.json`）・修正前と案の直しの答え・並行 PR（`parallel-pr-after-out`）。どれも受け皿の got を `ports.picked` で名指して読む（欄を 3 つ以上読むので、まるごとで受ける。README 4.2）。

## 3 計画の往復（記録・止め・安全の上限）

往復の記録と止め時は line が持つ（形の直し 6）。plan と plan-review は前の周を port `prior` で受け、1 周分の事実を返す（plan の設計書の 1.6・plan-review の設計書の 1.6）。

- 本体の並び（1.3 の 8）: `plan` → `plan-review-run` → `plan-out`。本体に承認ノードを置かない（E16）。本体に AI の node が直に無いので、README 13 章の「resume で輪が 1 周目から回る役」の決まり（wave 1 の決まり 1・2）は include の中の各 block が持つ。`fresh_context` は今と同じく書かない。
- `plan` の `prior`: `"$LOOP_PREV.plan-out.output.plan_prior"`。plan-review の `prior`: `"$LOOP_PREV.plan-out.output.record"`。1 周目はどちらも空（dry-run は `$LOOP_PREV` を置き換えないので、筋書きは 1 周目の空だけを見る。S36）。
- 前の周のファイルは 2 本に分ける（plan の設計書の 1.6 が line に任せた「同じファイルにできるか」の決め）: plan の `prior` は plan の形（`plan-prior.schema.json`: `{round, reply, fields, fix_plan, ripple, review, record, handoffs}`）、plan-review の `prior` は往復の記録の形（`PRIOR_SHAPE`: `{passes, plan, outcome, precedent_checks}`）。訳: 2 つの block の形は欄の意味が違い（plan は記録を欄 `record` に入れて受け、plan-review は記録そのものを受ける）、1 本に重ねると片方の形の変更がもう片方の読み手に及ぶ。記録の中身は 1 つで、plan の `prior.record` は `plan-converge.json` と同じ中身を写す。
- 事前審査の木: plan-review の `tree` は `choice(on|off|auto)`（plan-review の設計書の 1.2）。line は `$tiers.output.tree` を渡すだけで、auto の「開いた項目が 2 つ以上」の数えは plan-review が持つ。往復の上限の数 `round_limit` は渡さない（上限で止めたかは line が決める。README 1.3 の歩かせ 14）。
- `plan-out`（script。`src/rounds.py`）:
  1. 入力: plan の返りまるごと（`$plan.output`）・事前審査の返りまるごと（`{from: "$plan-review-run.output", if_skipped: null}`）。`ports.picked` で読む欄: plan の `ok`・`status`・`reason`・`round`・`owed`・`plan`・`fix_plan`・`reply`・`handoff`・`ripple`・`rejects`・`gave_up`、plan-review の `ok`・`status`・`round`・`holes`・`blocks`・`pass`・`asks`・`deviations`・`reason`。
  2. 事前審査が通った周は、`pass` の材料で往復の行を記録 `plan-converge.json` に足す（今の `converge.record_pass`・`add_pass`・`stash_rejects` を line が当てる: `review`・`answers`・`resolved`・`synergy`・`hits`・`origins`・`refs`・`push` を渡し、輪がもう 1 周回せない周〔周の番号 = 20〕は `at_cap`。`files` を `plan-converge/<k>/` へ写し、plan の `rejects` と事前審査の拒否を往復の行に積み、`precedent_checks` を記録の頭に置く。plan-review の設計書の 1.6 の「line が往復ごとに持つ事」）。穴の出自と続いた穴の照らしは plan-review が前の周の記録を見て `pass` に入れて返す（README 8.2）。次の周の plan の `prior`（`plan-rounds/prior-<k>.json`）を書く。
  3. 止め時は `rounds.decide`（今の `converge.decide`。抜け方の語 CLEAN・SETTLED・AGAIN・PERSISTED・UNSETTLED。往復の数・block の数で止めない）。`done` は、plan が `ok` でない（`nothing_owed`・`held`・`gave_up`・`failed`）・事前審査が `ok` でない（諦めた・落ちた）・抜け方が修正へ進む語（`proceeds`）・止まった（PERSISTED・UNSETTLED）・周の番号が安全の上限 20 以上、のどれか（今の `plan_out.py`）。上限 20 は `max_iterations` と同じ数（試験が突き合わせる）。上限の周で止めた行には `capped: true` を付け、その止まりは工場の不具合として人に見せる（`CAP_WHY`。無人の run でも推しで越えない。`stuck_pushable`）。
  4. 止まった案を無人の run が推しで進める時は、保留の項目の前の往復の block（`converge.stuck_faces`）を、修正の段へ渡す事前審査の返答に足したファイルを書いて `review` に返す（今の `boardview._take:1065-1068`。fix の `plan_review`・delta-review の `plan_review` が読む）。
  5. 返り: `done`・`ok`（plan と事前審査が通り、修正へ進む抜け方）・`status`（plan の `status`。`nothing_owed` は直す物が無い周）・`round`・`plan_prior`・`record`・`plan`・`fix_plan`・`reply`・`handoffs`（全部の周の `handoff` の pointer の並び）・`ripple`・`owed`・`gave_up`・`stalled`（止まった）・`capped`・`review`（修正の段へ渡す事前審査の返答の pointer）・`asks`・`deviations`・`stop_reason`。例外の時は計画ができなかった形（`ok: false`・`done: true`）と `works:line-script`。
- 修正前の承認ノードの往復の止まりの行（2 節の 2）と報告の往復ごとの行（`rounds.lines`）・1 回目に出た穴の割合は、この記録から line が組む（README 1.3 の歩かせ 14）。
- 計画の壁打ちは、どの段でも省かない（今の E20 の決まり。持ち主の決め `depth-by-reason`）。

## 4 一度だけの include と、block への配線

### 4.1 修正の段へ運ぶ値（`fix-in`）

今の `fix_in.py` のまま、運ぶ値を受け皿の got と修正前の答えから組んで平らな欄にする。固定材料の run は `start` が取り込んだ写しの値を運ぶ。通常の run は修正に入る時に 1 度だけ、運ぶ値を固定材料として写す（`fixture.noted_capture`。運ぶ値の鍵が変わるので `fixture.FORMAT` を上げる。前の版の固定材料は `fixture.adopt` が拒む）。運ぶ欄は、修正から後ろの node が読む判定・構造の目・独立設計・計画の往復の値の全部（4.5 の「修正から後ろ」）。足す欄: 単位の深さ `units_tier`・`skip_rerun`・`switches`（5.2）・`no_fix`（判定が止めずに直す単位を出さなかったか、計画の `status` が `nothing_owed`。直す物が無い周の印）・`excluded`（並行 PR が外した hunk の pointer。8 節の 2）。`go` は修正前の承認を通ったか（固定材料の run は起動の承認）。

### 4.2 案の直しと 2 度目の修正（一度だけ）

- `after-fix`: fix の `replan_items` が空でなければ `replan: true`（1 run に 1 度。今のまま）。真の時は、案の直しの plan の `prior`（承認済みの案の周: 最後の周の `reply`・`fields`〔欄 `plan`〕・`fix_plan`・`ripple` と、全部の周の `handoff`。`review` と `record` は null。plan の設計書の 1.6）を `replan-prior.json` に書いて pointer を返す。
- `replan` の `with:`: plan と同じ物に、`ruling: "$fix.output.replan_items"`・`conflicts: "$fix.output.conflicts"`・`prior: "$after-fix.output.prior"`。
- `replan-review` の `with:`: plan-review と同じ物に、`proposal`・`fields`・`ripple` ← `replan` の出力・`ruling`・`conflicts`（L-D25・S21）・`prior` ← 計画の往復が終わった時の記録（`$fix-in.output.record`。承認済みの案の行がここに在る）。`tree: "off"`（往復の外。今の案の直しの事前審査は木を作らなかった）。修正前の承認ノードの答えで通した行を聞き直さないこと（L-D26・S22）は、line が `ask-replan` で決める（plan-review の設計書の 1.6）。
- `ask-replan` の「聞く」の決め: 直した項目ごとの plan-review の出力 `replan` の行 `{item, units, contract_changed, human, widened}` を読み、`(contract_changed かつ 無人の run で widened でない) か human が在る` 項目を聞く（今の `boardview.replan_asks`。plan-review の設計書の 1.6）。読めない行は聞く側に倒す（今の `ask_replan.py`）。
- `refix-run` の `with:`: fix と同じ物に、`plan`・`fix_plan` ← `replan`・`ripple` ← `$answer-replan.output.fix_ripple`・`answers` ← `fix_answers`・`notes` ← `fix_notes`・`only_items` ← `$fix.output.replan_items`・`prior` ← `$fix.output.carry`・`plan_review` ← `replan-review` の `holes`・`skip_rerun` ← `$answer-replan.output.skip_rerun`。
- 2 度目の修正でまた案の誤りと裁かれた行は、案の段に戻らずに諦めて人に回す（L-D38。fix の中の `replan.settle`）。line に 2 度目の差し込みは無い。

### 4.3 2 つの段の合わせ（`fixed`）

今の `fixed.py` の決まりのまま（`src/stages.py`）: 単位は後の物・申し出・許したテストの変更・人に回した物・数え直しの食い違い・残すと答えた block は和・`x_scalars` は名ごとに 2 度目を優先・`replan_items` は 1 回目・`objection` は両方の異議をつなぐ・`rejudge` は異議が在り止まっていない時。`held` になるのは、案の直しが要ったのに 2 度目の修正が走らなかった・`after-fix` か `raise` が止めた・fix か refix が止めの語（`works:unrestored`）を返した・fix が返らなかった時。held の時は 1 回目の差分も試験の関門から先へ進めない（L-W47）。今との違い:

- `fix-in.no_fix` が真なら、直す物が無い形を返す（今は design-only の include が走ったかで決めた。新しい形では independent-design がどの周でも走るので、印を `fix-in` から受ける）。fix が走らず `no_fix` でもない（承認ノードで止めた・計画ができなかった）なら、`go: false` の形を返す。
- 段ごとの差分の審査とレンズを合わせる: `go` は「held でなく、最後の段の fix の `ok` が真で、どの段の lens・delta-review も `ok` が偽でない（回さなかった段は数えない）」（lens と delta-review の設計書の 1.6「`ok` が false なら止める」）。`done` は `go` で、どの段の delta-review も回さなかったか `pass`（delta-review の設計書の 1.6 の「変更の確かめが通った ∧（審査を飛ばした ∨ `pass`）∧ 戻せない組が無い」）。審査が通らなかった・諦めた（`gave_up`）は止めず、残りに数える（7.2 の `left`）。
- `diff`: 累積の差分の pointer。最後の段の delta-review が回れば `$delta-review(-2).output.diff`（手直しの後の姿）、回らなければ最後の段の fix の `diff`（delta-review の設計書の 1.6 が line に任せた「累積の差分の読み手」の決め）。
- 足す欄: `diffed`（累積の差分が在る）・`checks`・`eyes_due`（`raise` の返りか、`raise` が飛んだ直す物が無い周は `checks: false`・`eyes_due: true`。直す物が無い周も R2 で「直す物が無い」判定を確かめる。L-W07）・`stages`（段ごとの fix・lens・delta-review の受け皿の got。最後の承認ノードと報告が段ごとに読む）・`carry`（lens と delta-review の `carry` の和。次の run の依頼へ）・`tdd`（段ごとの fix の `tdd` を段の順に並べた配列。r2 の `tdd`）。

### 4.4 再審（一度だけ）と `judged`

- 再審は判定のまとめを通らず、line が diagnose の block を直に include する（`rejudge`。diagnose の設計書の 1.6）。判定のまとめの中の素材・世界の解・目的は再審の道を通らない（今の「run で 1 回」を配線で続ける）。
- `rejudge` の `with:`（diagnose の設計書の 1.6）: `objection: "$fixed.output.objection"`・`prior` ← `$fix-in.output.judgment`（1 回目の判定。再審は 1 回目を上書きしない。J104）・`prior_brief` ← `$fix-in.output.brief`・`prior_inputs` ← `$fix-in.output.inputs`・`world_rows`・`purpose`・`policy`・`spec`・`verify`・`excluded` ← `fix-in` が運んだ判定のまとめの返り・`lang`。
- 1 回目の判定が無い run は `fixed.rejudge` が偽なので届かない（今の `works:rejudge-session` の止めは diagnose の中に残る。J100）。
- `judged`: 今の `judged.py` のまま。再審が走れば再審の `units`・`judgment`・`rejudge_verdict`・`rejudge_exit`・`rejudge_diff`、走らなければ 1 回目を返す。`answer_ties`・`materials`・`out_of_purpose` は 1 回目の物を使い続ける（再審の道の diagnose は null で返す。diagnose の設計書の 1.6）。再審の前後の比べ（後に開いた単位・block から下げた単位・異議が名指さずに変わった単位）は `rejudge_exit` の先を読み、読めなければ訳を `unread` に返す（L-D45・L-D46）。再審が止まった（`ok` が偽）時は止めの語を `stop_reason` で返し、試験の関門・独立の目・merge へ進めない（L-D48）。再審が直す単位にした単位の行と「再審されずに残った異議」の行・次の依頼への運び（今の `runreport.rejudge_opened`・`rejudge_lines`・`outpurpose.next_items`）は line が組む（7.2）。

### 4.5 block ごとの `with:`（line が配る物）

`P` は `$start.output.ports`、`J` は判定のまとめの返り（judge-eyes.md の 1.2）。作り手の名指しは line の側だけが持つ。修正から後ろの node（fix・replan・replan-review・refix-run・lens・delta-review の 2 段・rejudge・spec-check・eyes-in・eyes）は、判定・構造の目・独立設計・計画の値を `$judge.output.*` などでなく `$fix-in.output.<欄>` から読む（固定材料の run は判定と計画が飛び、`fix-in` が写しの値を運ぶため。今の line の形のまま）。

- test-gate base: `mode: base`・`test_cmd`・`tdd_suite`・`base` ← `P.base_rev`・`request` ← `P.request`・`request_scope`・`reuse_dir`・`reuse_key` ← `P.run_id`・`user_env_dir`・`lang`。
- test-gate final: `mode: final`・同じ物に `tdd_suite` ← `$test-gate-base.output.suite`・`baseline` ← `$test-gate-base.output.baseline`（固定材料の run は `fix-in` が運んだ値）。
- judge の graph: judge-eyes.md の 1.2 の入力を `P`・`$test-gate-base.output.baseline` から。
- structure before: `mode: before`・`units` ← `J.units`・`intent: "[]"`・`policy` ← `P.policy`・`lang`。
- independent-design: `purpose` ← `J.purpose_text`・`purpose_source` ← `J.purpose_source`・`purpose_review` ← `J.purpose_review`・`constraints` ← `J.constraints`・`answers` ← `$answer-start.output.answer`（承認ノードが開かなかった run は null。port は null を「答えが無い」と読む）・`request` ← `P.request_file`・`policy`・`base` ← `P.base`・`head` ← `P.base_rev`・`lang`。
- plan（往復の中。plan の設計書の 1.6）: `judgment`・`units` ← `J.judgment`・`J.units`・`answer_ties`・`materials` ← `J.answer_ties`・`J.materials`・`answers` ← `P.request_answers`・`takes_push` ← `P.takes_push`・`verify` ← `J.verify`・`excluded` ← `J.excluded`・`depth_record` ← `J.tier_record`・`decisions` ← `J.decisions`・`world_rows` ← `J.world`・`structure` ← `$structure-in.output.structure`・`spec` ← `J.spec`・`policy`・`prior_failures` ← 依頼の容器の `prior_failures`（`P.prior_rows`。`start` が `prior-failures-in.json` に置いた行の値）・`base` ← `P.base_rev`・`review_rev`・`diff_base` ← `P.base`・`lang`・`prior`・`ruling: "[]"`。
- plan-review（往復の中。plan-review の設計書の 1.6）: `proposal` ← `$plan.output.fix_plan`・`fields` ← `$plan.output.plan`・`judgment` ← `J.judgment`・`purpose` ← `J.purpose_text`・`design`・`design_why` ← `$design-in.output.design`・`.reason`・`world_rows` ← `J.world`・`means` ← `J.means`・`structure` ← `$structure-in.output.structure`・`ripple` ← `$plan.output.ripple`・`prior`・`tree` ← `$tiers.output.tree`・`excluded` ← `J.excluded`・`policy`・`recorded`（line が `policy.recorded` で組んだ行。始めの承認ノードの答えと判定の `decisions` を含む。`owed` が組んで返す）・`request` ← `P.request_file`・`review_rev`・`diff_base` ← `P.base`・`lang`。
- fix（1 回目。fix の設計書の 1.6）: `mode: whole`・`judgment`・`answer_ties`・`materials`・`plan`・`fix_plan`・`ripple`・`plan_review`（`$fix-in.output.review`。3 節の 4 の推しの穴を足した物）・`answers` ← 修正前の答え（`asked` つき）・`request_answers` ← `P.request_answers`・`unattended`・`parallel`・`test_cmd`・`reuse_dir`・`reuse_key`・`user_env_dir`・`lang`・`policy` ← `$answer-before-fix.output.policy`・`request` ← `P.request_file`・`baseline`・`tdd_suite` ← `$test-gate-base.output.suite`・`skip_rerun` ← `$fix-in.output.skip_rerun`・`excluded` ← `$fix-in.output.excluded`（8 節の 2。fix の設計書に port を足す）。
- lens（段ごと。lens の設計書の 1.6）: `base` ← その段の fix の `start_tree`・`lenses` は書かない（block の既定の表）・`lang`。
- delta-review（段ごと。delta-review の設計書の 1.6）: `base` ← その段の fix の `start_tree`・`plan` ← その段の fix の `scope`・`lens_rows` ← その段の `lens-in` の `rows`・`fix_reply` ← その段の fix の `reply`・`permits` ← その段の fix の `allowed_tests`・`plan_review` ← その段の fix に渡したのと同じ事前審査の返答・`policy`・`request` ← `P.request`・`lang`。
- parallel-pr（修正の後）: `request` ← `P.request`・`base` ← `P.base_rev`（修正の差分のファイルを変更ファイルにする）・`changed: "[]"`・`lang`。
- rejudge（diagnose）: 上の 4.4。
- spec check: `mode: check`・`spec` ← `$fix-in.output.spec`（無ければ `""`。照らす仕様が無いという問いを block が返す）・`user_env_dir`・`lang`。
- eyes の graph（judge-eyes.md の 2.2）: `run` ← `$fixed.output.eyes_due`・`merge` ← `eyes-in`（5.4）・`skip_why` ← `fixed` が運ぶ `raise` の `skip_why`・`base` ← `P.base`・`head` ← `P.base_rev`・`base_label` ← `P.base_label`・`units`・`judgment` ← `judged`・`purpose` ← `$fix-in.output.purpose_text`・`plan`・`ripple` ← `fixed`（案の直しが走れば直した案）・`fixes`（最後の段の fix の `units`）・`x_scalars`・`changed`・`declared`（fix の `plan_declared`）・`tdd` ← `fixed`・`design`・`design_reason`・`design_premises` ← `fix-in` が運んだ independent-design の `design`・`reason`・`premises`・`constraints` ← `fix-in` が運んだ `J.constraints`・`world_rows` ← `fix-in` が運んだ `J.world`・`green`（`ok`）・`checks`（`evidence`）・`test_outcomes` ← `test-gate-final`・`policy`・`review`・`pushes`・`answers`・`asked` ← `eyes-in`・`request` ← `P.request_file`・`decisions` ← `fix-in` が運んだ `J.decisions`・`intent: "[]"`・`lang`。`eyes-in`（script）が組む物: `merge`（5.4）・`policy`（`{from: "$answer-before-fix.output.policy", if_skipped: null}` で受け、飛んだ run〔直す物が無い周〕は `P.policy`）・`review`（fix が使った案を審査した最後の往復の結論 `{round, verdict, blocks, why}`。往復の記録から。案の直しが走れば案の直しの事前審査の結論。今の `boardview.read_open_of` の「往復と案が組むか」の照らしも持つ。r1 の設計書の 1.6）・`pushes`（無人の run が判定の保留の問いに採った推し。`gatemarks.taken_pushes` を、最後の承認ノードと同じ判定・結び・修正前の答えで読む。読めなければ空と、報告の行に訳）・`answers`（`{start, before_fix}`）・`asked`（修正前の承認ノードで聞いた項目 `[{kind, text}]`。今の `plan_questions`）。
- merge seal: `mode: seal`・`base` ← `P.base_rev`・`fingerprint` ← `$test-gate-final-out.output.got.fingerprint`・`green_ok` ← 同じ `ok`・`eyes_ok` ← `$eyes-out.output.got.ok`。
- merge apply: seal と同じ物に `sealed_hash` ← `$merge-seal-out.output.got.hash`・`answer` ← `$answer-final.output.answer`・`r2` ← `$eyes-out.output.got.r2`・`deliver` ← `P.deliver`・`request` ← `P.request_file`・`user_env_dir`・`items` ← `$fixed.output.item_claims`。
- report: `sections` ← `$collect.output.sections`・`facts` ← `$collect.output.facts`・`lang`。

## 5 深さの表（段 → 回す物）と上げ直し

### 5.1 表（`src/tiers.py` の `TIERS`。今の `lib/depth.py` の `TIERS` を写す）

- 軽量: 省く物 `omits` = 差分の審査とそれに続くレンズ・手直し、独立の目の R1〜R4（R1 の削除候補を含む）、軽量の単位の緑の後の試験の走らせ直し。足す物は無い。事前審査の木の auto は off。目をまとめる物 `merges` = R3 を R4 の会話に入れる。
- 標準: 省く物も足す物も無い。木の auto は auto。
- 重厚: 足す物 = 名指さない既定の機能の全部（判定の裏取り・事前審査の木）。単位の深さは標準に固定。木の auto は auto。
- 省く物は「段が省く物を持ち、単位の深さがどれも軽量の時だけ」省く（今の `skip_reason`。issue #561 の答え）。
- 種類 → 段の表（今の `headdepth.UNKNOWNS`）は head-depth の block が持ち、line は持たない（形の直し 5）。

`tiers`（script。判定の後）: `$judge.output.tier` を表で引いて返す（固定材料の run は判定が飛ぶので `tiers` も飛び、`fix-in` が運んだ判定の返りの `tier` で同じ表を引き直す。修正から後ろの node は段の切り替えを `$fix-in.output.switches` から読む）: `tier`・`omits`（段が省く物を持つか）・`merge`（段が目をまとめるか）・`tree`（`P.tree_named` が名指しならその語。無ければ `entry.switch(記録, "review_tree", tier_adds(段), tier_auto(段))` の語〔重厚は足す機能に在るので on・軽量は off・標準は auto〕。今の `boardview.py:426-429` と同じ式）・`adds`（報告の「段が足した物」）・`lines`（報告の「省く物・足した物」の行。head-depth の設計書の 8 節の 3）。段の語が表に無ければ標準と読み、行に訳（今の `named` の倒し方）。

### 5.2 単位の深さ（`fix-in` と `answer-replan`）

- `fix-in`: 直す義務の単位（plan の出力 `owed`）の全部を、承認済みの案の欄（plan の出力 `plan` の先）から `decide_doc(items, owed, forced=P.forced, checked=P.has_checks)` で決める（今は plan の block が返していた `depth`。README 1.2 の D で line。plan の設計書の 1.2 の `owed`）。返り `units_tier`（`[{unit_id, depth, why}]`）・`skip_rerun`（段が省く物を持つ時だけ、軽量の単位の key。ほかは `[]`）・`switches`（`{tier, omits, merge, tree, lines}`。`tiers` の返りか、固定材料の run は運んだ判定の `tier` で引き直した物）。
- `answer-replan`: 直した案の単位を、案の直しが走ったので全部標準と読み（5.3 の信号「案の直しが走る」）、1 回目の行を単位ごとに置き換えた並び（今の `redepth.merged`）を返す。2 度目の修正の `skip_rerun` は `[]`（全部が標準なので省く単位は無い）。

### 5.3 上げ直し（`raise`。1 回目の修正の段と差分の審査の間で run に 1 回）

今の line の `redepth` と fix の中の `fixboard.redepth` を 1 つにした物（形の直し 5）。fix の中の上げ直しは無くなる。

- 置き場: 1 回目の fix と `after-fix` の後、1 回目の lens・delta-review の前（README の「fix と delta-review の間で 1 回だけ」）。2 度目の修正の段の前では上げ直さない。訳: 2 度目の修正は案の直しが走った run にだけ在り、「案の直しが走る」は run 全体を標準へ上げる信号（L-D09）なので、1 回目の上げ直しの時点で全部の単位が標準になっている。2 度目の段で数える信号（止めた単位・拒否・相談）は、標準より上へは上げられないので、結果を変えない。だから 2 度目の段の lens・delta-review と独立の目は、この 1 回の結果を読む。
- 上げる信号（どれも標準へ上げ、下げない。`raise_doc`）: 単位ごと＝1 回目の fix が止めた単位（`units` の `status` が `fixed` でない）。run 全体＝申し出が在る（fix の `conflicts`）・答えていない問い（`gatemarks.pending`。台帳が読めなければ上げる側に倒す）・案の直しが走る（`after-fix.replan`）・修正役の異議が在る（fix の `objection`。今の fix の中の上げ直しが数えた信号。fix の設計書の 16 節の 4 の問いの答え）・修正の差分が頭の深さの引用の外に出た・TDD の輪で修正役が拒まれた（fix の `tdd_refused`）・範囲の相談をした（fix の `accept_trace` の相談の行）・直さずに残すと答えた事前審査の block（fix の `plan_declared`）（後ろの 4 つは `latedepth.signals`。引用は `J.tier_record`。fix の設計書の 1.6 が名指した読み口）。
- 返り: `units`（上げた後の行）・`checks`（差分の審査・レンズ・目を回すか。`switches.omits` が偽か、上げた後の単位の深さに標準が 1 つでも在る時に真）・`skip_why`（回さない時の訳。今の `skip_reason` の文）・`eyes_due`（`checks` か `P.carried_measured`。前の run の前提の検算が運んだ実測が在る run は目を省かない。今の `eyes/prep.py:107-109`）・`raised`・`counted`（run の広さの数え。記録だけで上げる信号にしない。issue #760）・`lines`（報告の冒頭 2 の深さの行。今の `depth.lines`）・`stop_reason`。
- 例外の時は `works:line-script` を返し、`fixed` が held にして試験の関門から先は飛ぶ（深さの分からない差分を目に通さない）。
- `when:` が読むのは `checks` の真偽（lens・delta-review の 2 段）と、`fixed` が運ぶ `eyes_due`（eyes の graph の `run`）だけで、深さの語や名に depth を含む欄を読まない（今の `tests/layers/test_depth_skip.py` の照らしは続く。13 節）。

### 5.4 独立の目を回すか・まとめるか（`eyes-in`）

`run` ← `$fixed.output.eyes_due`（直す物が無い周は `raise` が飛ぶので、`fixed` が真を返す）。`merge` ← `$fix-in.output.switches.merge` が真で `run` が真（目を省かずに回す軽量の run だけ R3 を R4 に入れる。今の `depth.merges`。持ち主の決め `eyes-by-reason`）。直した後の実測（structure after）は `run` に依らず回す（E71。eyes の graph の側）。

## 6 無人の方針（`src/gates.py`。今の `lib/gatepolicy.py` の決めのまま）

- 入口: `unattended` は空か `true`。仕様の段と無人の run は組めない（`start` が AI の前で拒む）。無人の run の `final_gate` の空の既定は `when_needed`（人の居る run は `always`）。
- 起動の承認ノードは開かない（`start.ask` が偽）。
- 修正前: 判定の推しが選択肢を名指す fork・held は台帳の読みが答えとして採り、出どころを直す義務に戻す。採れない台帳の問い（fork・escalate）は承認ノードに載せず `deferred` で返し、報告と次の依頼の下書きへ回す（L-G33・L-G38・L-G41）。ほかの項目が在れば `passage`: 項目の全部が通す推しの尾を持つ時だけ推しで進み（`pushed`）、ほかは開かずに `works:needs-human` で止める。止まった往復の行も、推しの尾が付く条件（`stuck_pushable`。上限で止めた往復は付かない）を満たせば推しで進む。設計だけの run は無人でも止まる（L-G27）。
- 案の直し: 範囲を広げるだけの直し（`planmarks.widened`）は聞かずに通し、足した・外した glob を `widened` で返して報告へ（L-G45）。約束の欄が変わった項目は推しを持たないので止まる（L-D30）。
- 最後: 開くはずの時は開かずに `works:needs-human` で止め、merge の apply を飛ばす（L-G39・L-W25）。
- 機械は推しを作らない（推しは記録に書かれた物だけ。L-G24）。

## 7 報告への受け渡し（`collect`）

`collect` は落ちない（今のまま: 境の口を読めない時も標準ライブラリだけで fallback を書く）。受け皿の got・返し・承認の答え・line の script の止めの語を受け、2 つのファイルを place に書いて pointer を返す。

### 7.1 `sections`（並び）

節は block の `report` の欄をそのまま `lines` にし、見出しを line が付ける。見出しの字と並びは今の機械の報告の節に合わせ（report の設計書の 1.6）、今の報告に無かった節は後ろに run の流れの順で足す。どの節も、その block が走らなかった run では載せない（走ったのに行が無い節は report が 1 行を置く）。

1. 入口・段・決めた人（line）: 今の `_entry_lines` の行（始めの記録・固定材料・入口の文・最後の承認ノードの開き方・段と機能・決めた人の数・forge が無い時の行・走った段と飛ばされた段〔段の表 `stages`〕・下げている所〔parallel-pr・independent-design・diagnose の出力の `downgrades` の行の数と行。今の `lib/downgrades.json` の読みの替わり。README 9.2〕・run の頭の深さの省く物と足した物〔`switches.lines`。段と根拠は head-depth の節〕・深さの行〔`raise.lines`〕・前の失敗の行・方針の行・直す前のテストの語・テストの凍結が効いていない組〔fix の `freeze_off`〕）と、足す行: 判定の裏取りを回さなかった訳（`$judge.output.verify` が null の時。「既定で切（features の既定）」「features_off で切」「段 <語> は足さない」のどれか。verify の設計書の 1.6）・変異の検算の道（gates=merge の時）。
2. TDD のループの単位ごとの結末（fix の `report`）・同（2 度目の修正）（refix の `report`）。
3. 緑の認証（test-gate final の `report`。base の行も同じ節の頭に）。
4. 独立の目（eyes の graph の `sections` の目の 4 節と、まとめの行）。
5. 構造の目（structure before の `report` と、eyes の graph が運ぶ structure after の `report`）。
6. 世界の解（world の `report`）。
7. 未確認のレンズと局所レビュー（local-review の `report`）。
8. 判定（目的の外とした所見を含む）（diagnose の `report`）。
9. 以下は今の報告に無かった節（run の順）: 直す前のテスト・run の頭の深さ・仕様・並行 PR・前提の実測・目的・素材（残り 10 本の観点ごとに 1 節）・判定の単位の裏取り・独立設計・計画の往復（plan と plan-review の `report` と line の往復ごとの行 `rounds.lines`）・修正前の承認ノード（聞かずに通した行・載せなかった問い）・レンズと差分の審査（1 回目の段。lens と delta-review の `report`。回さなかった段は line が「差分の審査を回さないのでレンズは起こさない（<訳>）」の 1 行を組む。今の `fixboard.LENS_NOT_DUE`）・案の直し（replan・replan-review の `report` と、聞かずに通した広げる直し `widened`）・レンズと差分の審査（2 度目の段）・並行 PR（修正の後）・再審（diagnose の `report` と前後の比べ）・仕様の照らし・封じた差分と置いた差分（merge の `report`）。
10. 模型の群の選び（line）: head-depth の `record` を KEEP の `headdepth.groups_lines` で組む（report の設計書の 1.6 が line の決めとした所。ノードごとの模型の事実は report の「模型」の節に在る）。

`files`（節「3. 見る所」の元。今の `runreport.POINTERS` の 18 個）は、その事実を持つ節に入れる: 判定・目的の外の所見（判定の節）・目的・定石（世界の解）・仕様・計画・波及・事前審査（計画の往復）・構造の目・直した後の構造・独立設計・差分・申し出と裁定（TDD の節）・直す前の結末・試験の記録 2 つ（緑の認証）・封じた差分・置いた差分。

### 7.2 `facts`

欄と意味は report の設計書の 1.2 の表。line の `src/facts.py` が、表の「今」の計算（`lib/outcome.py`・`lib/runreport.py` の同じ名の関数）を、受け皿の got を今の `returns` の形に詰め直して呼ぶ（作り直しの間は lib のまま。組み込みで、`outcome` の読み分けの部分は `facts.py` に入り、結末の 10 語と決める順は report の `src/outcome.py` へ。README 9.2）。line だけが知る値の出どころ:

- `start_ok`・`problems`・`notes`: 始めの記録の読めなさと `outcome.record_problems`。
- `gates`: 4 つの承認ノードの答え（承認ノードの順。開かなかった物は `decision: null`）。仕様の承認ノードの答えは spec の block の出力の止めの語で届く。
- `stops`: line の script の止めの語（`start`・`answer-*`・`ask-*`・`fix-in`・`after-fix`・`owed`・`structure-in`・`fixed`・`raise`・`judged`）と、block の返りの `stop_reason`（judge の graph・fix・refix・spec check・test-gate）。
- `halts`: 往復が進まない（`{at: "plan-review", word: stopby.PLAN_CONVERGE}`。`plan-out.stalled` で、修正へ進まなかった run）・計画の諦め・封じと置きの ok でない行。
- `waits`: 人に回した申し出（`conflict.asked_rows`）・案の直しを待つ申し出・ほか（eyes の `premise_check` が escalate・r4 の問い・承認ノードを開かなかった修正前の問い〔無人の `deferred`〕）。
- `cut`: 段の表 `stages`（今の `collect.STAGES` を新しい node の名に直した物）の続きの切れ目。
- `optional`: 落ちても受け止める段の宣言。line 自身は `eyes__`（eyes の graph まるごと）と `lens__`（レンズ。今は fix の中の宣言だった）。block の返りの `optional` は受け皿の got から頭を付けて重ねずに足す（今の `absorbed`）。
- `returned`・`no_fix`・`left`（`runreport.residue` の行。差分の審査が通らなかった行・案の直しを諦めた項目・再審が開いた単位〔次の依頼へ運ぶ〕を含む）・`proved`（最後のテストの ok と green と封じの ok）・`head`（`split_line`・`_pushed_said`・`_stopped_why`・`_ran_notes`・`suitewrite.head_note`・`userenv.NOTE`・`testcmd` の注意の行 `notices`）・`asks`・`tallied`（守りのパスの当たりの全件の数 `protected_count`）・`counted_left`・`decisions`・`apply`・`carry`（`runreport.next_request`・`prior_failures`・`answer_drafts`・`carry.carried_constraints`。前提の検算の実測は eyes の `premise_check` の facts から）・`stop_lines`・`outcome_parts`・`round`（往復の記録の周の数）・`line_rev`（`versions.line_rev`）。

## 8 今の工場の穴（README 8.7）の決め

### 8.1 並行 PR の確かめを、最初の修正の後に回し直す

- 今の事実: `judge_accept.parallel_pr_due`（1 周目か、判定から入る run で最初に修正が入った次の周）は写したが名指す node が無く、修正の後に確かめ直さない（parallel-pr の設計書の 6 節の 2）。graphloops は次の周で、その周に固めた版から変更ファイルを取り直して回す。工場は 1 run = 1 周（持ち主の決め `carry`）で、周の鎖の次の周も、前の周の commit の後の HEAD を差分の根にするので、前の周が直したファイルを並行 PR と突き合わせない。判定から入る run では、1 回目の確かめは依頼の `where` のファイルしか見ていない。どの道でも能力が落ちている。
- 決め: 判定から入る run（`P.entry` が空でない）で、直した差分が在る時だけ、parallel-pr の block を修正の後に 1 度だけ include する（1.3 の 18 の `parallel-pr-after`。`base` は修正前の HEAD なので、変更ファイルは直した差分のファイル）。graphloops の「最初の修正の次の周」を 1 run の中で当てた形。差分の在る run（通常の run）は 1 回目の確かめが差分のファイルを見ているので、今の graphloops と同じく回さない。
- 読み手: 最後の承認ノード（`status` が `found` なら「直したファイルが開いている PR と重なる（N 件）」、`not_run`・`awaiting_human`・`failed` なら「修正の後の並行 PR の確かめ直しができなかった（訳）」を、開き方で開く理由に足す）・報告（節「並行 PR（修正の後）」と、申し送りの下書き `drafts` を人が決めることの行に）。run は止めない（`stop_reason` が在っても止めず、承認ノードの理由にする。判定はもう済んでいて、次の周の判定に当たる読み手が line の中に無いため）。外した hunk（`excluded`）は修正の後には読み手が無いので渡さない。
- 振る舞いの変わる所: 判定から入る無人の run で重なりが見つかると、`when_needed` の最後の承認ノードが開くはずになり、`works:needs-human` で止まる（今は止まらずに置いた）。重なる直しを人が見ずに置かない側に倒した。

### 8.2 fix が外した hunk（`excluded`）を受け取らない

- 今の事実: parallel-pr が外した hunk は plan・plan-review・案の直し・再審の材料・報告に届くが、fix と diagnose には届かず、外した範囲を直しても拒む関門が無い（parallel-pr の設計書の 6 節の 5）。元の works は判定・修正案・修正に渡す作りで、配線が無かった。
- 決め: line は `$judge.output.excluded`（judge の graph が parallel-pr の `excluded` を返す）を `fix-in` で運び、fix の 1 回目と 2 度目に port `excluded` で渡す。外した hunk を修正役の差分が触ったら拒む関門は fix の受け付けに置く（役の返答の受け付けは block の物。line は計算しない）。fix の設計書の 1.2 にこの port が無いので、fix の設計書に足してもらう（15 節）。diagnose には今のまま渡さない（判定は外す範囲を決める前の材料を読み、外した hunk は案の項目を通して直しの範囲から外れる）。

### 8.3 始めの記録に `gates` を書く物が無い

- 今の事実: gate-efficacy の `gates` が `merge` の時にこの観点を回さない道は、始めの記録の欄 `gates` を読むが、書き手が工場に無い。訳の字 `GATES_MERGE_WHY` は元の works の入口の入力（`init --input gates=merge`）を名指す。前の棚卸しは「線が入力 gates を落とした。持ち主の確かめ待ち（段 3 で変異の検算と一緒に聞く）」とした（S37・L-E40）。
- 決め: line に入力 `gates`（空か `merge`）を足し、`start` が知らない語を拒み（`entry` の語の確かめと同じ形の `Refused`）、始めの記録の欄 `gates` に置き、gate-efficacy の port `gates` に配る。chain も同じ名で子に渡す（12 節）。既定の空は今の振る舞いと同じ（観点を回す）なので、名指さない run は変わらない。元の能力（元の works の入口が持った道）を戻すだけで、ほかの能力を削らない。
- 持ち主への確かめ: S37 で聞くと決めた件なので、冒頭の「求めること」に置いた。通さない答えなら、入力を足さず、gate-efficacy の `gates` は既定の空のまま（今と同じ）にし、訳の字の「init --input gates=merge」を「この工場の入口には無い」に替える。
- 字の直し: `GATES_MERGE_WHY` の「（init --input gates=merge）」は、足した後は line の入力の名を言う字（「（works-factory-line の --input gates=merge）」）に替える。字は gate-efficacy の block が持つので、その block の直し（15 節）。

## 9 今の line との比べ（全部の確かめ・止め・承認ノード・書く順の行き先）

今の node ごとに、持つ決まりと、新しい形の在りか。棚卸しの行（L-E・L-G・L-W・L-D）は行き先の所に名指す。

- `testcmd`・`testcmd-stop`: test_cmd が対象の手元（run の作業ツリーと同じ git の作業ツリーのうち外の全部）を走らせる形なら AI の前で止める・`WORKS_FACTORY_ALLOW_TESTCMD=1` で止めずに注意・確かめが落ちたら止める・止めない時の注意の行を報告の冒頭へ。→ line（今のまま。`src/testcmd_check.py`）。
- `start`: 入力の語の確かめ（spec・final_gate・unattended・features の知らない語と両方への名指し・design_only・thickness・段が足す機能を features_off で切る組・deliver・足す gates）・固定材料のフォルダと方針の文書の在りか・spec と固定材料の組みの拒み・依頼のファイルの読めない／JSON でない／形が違うの 3 つの拒み・findings の型（L-E01〜L-E04）・PR と issue の gh の読み（L-E11〜L-E15）・差分の根（L-E07〜L-E10・L-E20・L-E21）・依頼も差分も無い入力の拒み（L-E07）・spec=on で依頼の文が無い時の拒み（L-E29）・入口の形 `input`（L-E19）・版の控え（L-E44〜L-E46。拒む run でも書く）・方針の固め（L-E35・S24）・prior_failures の置き（L-E05）・固定材料の取り込み（L-E42）・起動の承認ノードの文（L-E47〜L-E49）・落ちない（L-E53）。→ line の `start`（今のまま）と、配る値（1.6。L-E33 の「機能の切り替えがブロックに届く」は、block が記録を読む形から line が値で配る形に替わる）。
- `gate-start`・`answer-start`: 2 節の 1（L-G01〜L-G10）。
- `test-gate-base`(-out): 今のまま。判定の前に走り、固定材料の run は飛ぶ。
- `judge`(-out): judge の graph（judge-eyes.md）。返りの欄の名は変わる（1.6・4.5 が新しい名で読む）。今の `judge_accept.require_ports`（前の版の返りを resume で受けたら止める）は、新しい graph の返りの形で同じ照らしを `fix-in` と `collect` に置く（欄の欠けた got を空と読まない。L-W67 の能力）。
- `owed`・`structure`(-out)・`structure-in`: 今のまま（計画の 1 回目の周が修正案の役を起こす run でだけ構造の目を測る）。`owed` の決め（`planfile.round_inputs`・`held_why`）は plan と line が共に使うので、README 9.2 の `planfile` の MOVE から外し、その 2 つを `lib/` に残す（13 節・15 節）。
- `design-only`(-out): 直す物が無い周の独立設計。→ independent-design の include（判定の後に 1 回。どの周でも）。直す物が無い周の印は `fix-in.no_fix`。今の plan-review の `mode: design` の道は無くなる（independent-design の設計書の 1.6）。
- `plan-rounds`（`plan`・`plan-review-run`・`plan-out`）と受け皿 2 つ: 3 節。受け皿は 1 つにまとめる（欄の名を 1 つの `names` に並べる）。往復の記録・止め・安全の上限 20・上限でも輪が落ちずに抜ける（L-D16）・前の周の返りを次の周へ（L-D17。今の `review` は 2 本の `prior` になる）・事前審査の木の段の読み（今は plan-review が `head_depth` を受けて決めた。→ `tiers` の `tree` を plan-review の `tree` に渡し、auto の数えは plan-review）・事前審査の中に在った往復の行の書き・止め時・止まった案の推しの穴の足し（今の `boardview._take`。→ `plan-out`）。
- `ask-before-fix`・`gate-before-fix`・`answer-before-fix`: 2 節の 2 と 6 節（L-G17〜L-G41・L-W14・L-W38・L-W39・L-D19〜L-D21）。軸と通した行は line が組む（今は事前審査が返した）。
- `fix-in`: 4.1（L-W65・L-E43）。
- `fix`(-out)・`after-fix`・`replan`(-out)・`replan-review`(-out)・`ask-replan`・`gate-replan`・`answer-replan`・`refix-run`: 4.2 と 2 節の 3（L-W17・L-W18・L-W44〜L-W48・L-D23〜L-D40）。
- `fixed`: 4.3（L-W49・L-D37）。
- `spec-check`: spec の block の `mode: check`（spec の設計書の 1.6）。照らせない時の問い（spec=on なのに仕様の指しが無い）は block が返す。止めの語 `works:spec-changed`（人待ち）は line が spec の返りの `questions` から立てる。差分の審査・最後のテスト・独立の目は飛ばさない（今のまま）。
- `rejudge-run`(-out)・`judged`: 4.4（L-W40〜L-W43・L-D41〜L-D49）。再審は判定役の会話を継がない（持ち主の決め。S40）のは diagnose の中。
- `redepth`: 5.3（L-W50・L-W51・L-D05〜L-D13）。fix の中の上げ直し（`fixboard.redepth`。差分の審査を省くか）と合わせて、1 回目の修正の段と差分の審査の間の 1 回にした。差分の審査とレンズは今と同じく修正の段ごとに回る（delta-review と lens の block を段ごとに include）。
- `test-gate-final`(-out): 今のまま（L-W52・L-W53）。`when:` の読む物は `fixed.go`・`judged.stop_reason`・`raise.stop_reason`。
- `eyes`(-out): eyes の graph（judge-eyes.md）。守りのパスの当たりは merge へ移った（README 13 節）。
- `merge-seal`(-out)・`merge-apply`(-out): 今のまま（L-W59）。apply は最後の承認ノードの go の後だけ。
- `ask-final`・`gate-final`・`answer-final`: 2 節の 4（L-G48〜L-G51・L-W20〜L-W37。keep-essence の 6・8・10・11）。
- `collect`・`report`・`sweep-children`・`result`: 7 節と 1.3 の 25〜28（L-W60〜L-W62）。報告はいつも走り、resume でも回し直す（`always_run`。include の `always_run` は Archon が捨てるので、`collect` の返りが変われば report が回し直る今の形）。
- line の script は落ちない（例外も lib の import の失敗も `works:line-script` の返りにして報告まで届く。L-G52・L-W63）: どの script も `ports` の `run(fn, fallback)` の形（今の `boundary.run`）。
- 消した物と訳:
  - 判定の裏取りの申し送りを回さなかった形で毎回置くこと（今の `judge_accept.py:3968-3970`）: 回さない run は verify の block を include せず、読み手は null を受ける。回さなかった訳は line の節 1 の行（7.1）。plan の指示の「確かめられなかった」の節は plan の設計書の決め。
  - `plan-review` の入力 `round_limit`・`head_depth`: 上限で止めたかと木の段の読みは line が決める（3 節・5.1）。
  - 受け皿の 2 つ（`plan-rounds-out`・`plan-rounds-review-out`）を 1 つに: 運ぶ欄は同じ。
  - 型つきの成果物の一覧の読み（今の report の facts の `listing`）: report が読まない（report の設計書の 1.2）。line も読まない。
  - `docs/design.md` の節の名指し（今の YAML と script の docstring）: 設計書は `docs/design/line.md`。

## 10 元の works と graphloops の同じ場面

- 元の works の線（`works/darkfactory/darkfactory.yaml`・`lib/line_edge.py`）: 承認ノード 4 つ・計画の往復・案の直しの refit・再審の h-rejudge（refit の後）・深さの上げ直し `depth.raise_`・最後の承認ノードの `_final_needs`。工場は同じ順で写し（今の line の docstring が元の行を名指す）、この設計は形を変えない。元の works に在って工場に無い物のうち、この設計で戻すのは入口の `gates`（8.3）。元の works の止め札（関所の間で走っている run を外から止める）は持ち込まない（S60 の決め `stop-at-gates`）。
- graphloops の review-graph（`graphs/review-loop.json` の周の loop）: 周ごとに P0〜P4 を回し、次の周の頭で判定を回し直す。工場は 1 run = 1 周で、次の周は chain が別の run で回す。graphloops の周の条件で工場に無い物のうち、並行 PR の回し直しはこの設計で 1 run の中に戻す（8.1）。ほかの周の条件（目的の出典を前の周が触った時の目的の監査の回し直しなど）は、1 run = 1 周ではいつも偽で、今も回らない（素材の観点の族の設計書の 5.2）。
- 意図して外した記録: 周の鎖の 1 run = 1 周（持ち主の決め `carry`）。並行 PR の回し直しを外した PR の記録は（未確認）（parallel-pr の設計書の 6 節の 2）。

## 11 試験

graph は AI の node を持たないので、README 6 節の node ごとの 9 項（指示の組み立て・描いた骨組み・指示の比べ）は当たらない。確かめは筋書きと振る舞いの試験と通しの試験。

- standalone の筋書き `blocks/line/fixtures/standalone.stubs.yaml`（7.1 の 4）: `fixture.inputs` は `request`（`fixtures/request.json`）・`test_cmd` だけ。include した block の AI の node と、include の中の loop の本体の script を台本で差し替え（README 13 章: dry-run は include の道を loop の本体に渡さない）、line の script は本物で回す。`reached` に `result`。
- 今の筋書き 36 本（`workflows/line/fixtures/`）を新しい node の id に書き直す（README 11.3 の 2）。足す筋書き: `parallel-pr-after-found`（判定から入る run で、修正の後の並行 PR が found → 最後の承認ノードが開く）・`gates-merge`（`gates=merge` で gate-efficacy が skipped）・`gates-refused`（知らない語で AI の前に止まる）・`fix-excluded`（`excluded` が fix に届く。`resolved-text-contains` でなく `with` の値の照らし）・`light-all-units`（軽量で全部の単位が軽量 → lens・delta-review・r1〜r4 が飛び、structure after は走る）。
- 振る舞いの試験 `tests/blocks/line/`（今の `tests/workflows/test_line.py`・`test_gate_head.py`・`test_testcmd_head.py` と `lib/tests/test_fixture.py`・`test_startrec.py`・`test_testcmd_check.py`・`test_versions.py` を元にする。README 9.5）:
  - `test_start.py`: 入力の拒み（今の `StartCase` の全部）と、配る値（1.6 の欄ごと。`entry` が差分の空と依頼の数の両方で決まる・`verify_by_tier` が名指しで全段 on/off になる・`gates` の語）。
  - `test_gates.py`: 4 つの承認ノード（今の `GateAnswerCase`・`AskBeforeFixCase`・`AskReplanCase`・`AskFinalCase`・`AskFinalReadsCase`・`FinalGateCase`・`UnattendedPolicyCallCase`・`LedgerAsksCase`）。足す: 修正の後の並行 PR の found と失敗が開ける理由に入り must でない。
  - `test_tiers.py`: 表の行が今の `depth.TIERS` と同じ（組み込みの前に写しを照らす）・単位の深さ・`skip_rerun`・上げ直しの信号の全部（今の `RedepthCase`）・`checks` と `eyes_due`（前の run が運んだ実測で省かない）。
  - `test_rounds.py`: 往復の記録の行・止め時の 5 語・上限 20 と `max_iterations` の突き合わせ・上限で止めた行の `capped`・止まった案を推しで進める時の保留の穴の足し・2 本の `prior` の形（今の `PlanOutCase`・`PlanOutNothingOwedCase`）。
  - `test_stages.py`: 2 つの段の合わせ（今の `FixedCase`）と `no_fix`・held・`diffed`。
  - `test_collect.py`: `sections` の並び・`files`・`facts` の欄（report の設計書の 1.2 の表の欄ごと）・前の版の返りを空と読まない・落ちない（今の `CollectAndResultCase`・`FallbackCase`・`BrokenLibCase`・`ReturnedCase`）。
  - `test_wiring.py`: YAML の配線（今の `LineWiringCase`・`FixWiringCase`・`NoFixWiringCase`・`SharedPlacesWiringCase`・`StructureOnceCase`・`HandoffCase`）。足す yes/no: include した block の `inputs:` の全部が、line の `with:` で渡るか、渡さない訳を名指した一覧に在る（L-W67）・一度だけの include（`replan`・`replan-review`・`refix-run`・`rejudge`・`parallel-pr-after`）が line に 1 つずつ・`when:` が名に depth を含む欄を読まない。
- 通しの試験: `tests/e2e/test_line_scenarios.py` を新しい line に書き直し、`tests/e2e/evidence.json` の行の書き手を新しい関数の名に替える（L-E33 は line の節 1 の行に。verify の設計書の 1.6）。
- 守る keep-essence: 6（回さなかった試験を最後の承認ノードに名で並べる。`test_gates.py`）・8（人に回した申し出で最後の承認ノードが開く。`conflict-ask` の筋書き）・10（守りのパスに触れたら開き、apply を拒む。`eyes-failed-protected` の筋書きを `seal-protected` に改める）・11（単位ごとの記録が最後の承認ノードと報告に届く。`test_gates.py`・`test_collect.py`）・12（定石からの外れを修正前の承認ノードで人に回す。`test_gates.py`）。

## 12 chain（周の鎖）

今の `workflows/chain/` を `blocks/chain/` に移す（README 11.3 の 1）。line を周ごとに子の run として起こす形・5 組の周の node・止めの決め・最後の差分・PR の渡しは今のまま。直す所だけ:

- 子の line に渡す入力の錨 `line_inputs` に `gates: "$INPUTS.gates"` を足し、鎖の入力にも `gates`（説明は「どの周の子にも渡すメイングラフの同じ名の入力」）を足す（8.3）。
- `hand`（include `works-factory-merge`、`mode: check`）の `with:` の `base_rev` を、merge の port の名 `base` に改める（merge の設計書の 1.6）。ほかの欄（`sealed_hash`・`deliver`・`request`・`user_env_dir`）は今のまま。
- script（`chain_start`・`round_commit`・`round_facts`・`decide`・`final_diff`・`result`）は `boundary` の代わりに `ports` の口で入力を読む。読む lib（`chain`・`entry`・`entryshape`・`runbranch`・`carry`・`runreport`・`report`・`seal`）と埋め `child_pointer` は KEEP（README 9.3）。chain の置き場のファイル（`chain/final.diff`・`chain/round-<k>.diff`・`chain.md`・`chain/<子>/next-request.json`）の名は `blocks/chain/src/files.py` が持つ。
- 子の line の返りの欄（`outcome`・`apply`・`r2_status`・`spec_questions`・`next_request`）は line が今の名で返す（1.2）ので、`decide` と `round_facts` は変わらない。
- 守る能力（L-D55〜L-D57）: 周の数 1〜5 と費用の上限の確かめ・design_only と fix_fixture の拒み・止めの語の順（周の数 → 結末の種 → 人が要る → 進みが無い → 費用）・周の commit を run の枝にだけ積む（`worktree.enabled: true`）・次の依頼に 1 周目の answers・pr・issue を足し下書きの行は運ばない・止まった周を採らずに最後の差分を封じる・出口の語 pr の時だけ親が PR を 1 本作る。試験は今の `tests/workflows/test_chain.py` と筋書き 8 本を `tests/blocks/chain/` と `blocks/chain/fixtures/` へ移す。

## 13 自分で決めた事

- 判定の裏取りを回すかを、段ごとの真偽の表 `verify_by_tier` で judge の graph に渡す。根拠: 段は judge の graph の中の head-depth が決め、段 → 回す物の表は line が持つ（形の直し 5）。表を judge の graph に写すと知る所が 2 つになる。line が表を引いた結果を値で渡せば、judge の graph は段で真偽を選ぶだけ（流れの決め）で済む。
- 再審は diagnose の block を line が直に include する（判定のまとめを 2 度 include しない）。根拠: 再審の道で回るのは diagnose だけで、まとめを include すると 16 の block に `when:` で再審を外す句が要る。持ち主の決め `rejudge-cohabit`（再審は判定と同じ block）は守る。
- independent-design を判定の後に 1 回 include し、直す物が無い周の印は `fix-in.no_fix` にする。根拠: independent-design の設計書の 1.6。今の plan-review の `mode: design` の道が無くなる。
- 上げ直しを 1 回目の修正の段と差分の審査の間に 1 回だけ置き、差分の審査とレンズは段ごとに回す。根拠: README の形の直し 5（line が fix と delta-review の間で 1 回）と、delta-review・lens の設計書の 1.6（段ごとに include し、段の fix の `start_tree`・`scope`・`reply`・`allowed_tests` を受ける）。2 度目の段は案の直しの信号で全部が標準なので、上げ直しを足さなくても結果は同じ（5.3）。
- line の返りの欄 `report`（機械の報告の pointer）の名を変えない。根拠: `bin/`・chain・通しの試験が今の名で読み、形の検査（7.1 の 8）は欄の有無の yes/no で通る（1.2）。line の報告の行は `sections` に入る。
- 差分の審査が通らなかった・諦めたことを `fixed.go` に混ぜず、残りに数える。`ok` が偽（段が壊れた）の時だけ止める。根拠: delta-review の設計書の 1.6（`ok` が false なら止め、`gave_up` は止めない）。今も審査が通らなかった差分は最後のテストへ進み、結末を fixed にしない（今の `review_failed` の道）ので、結末は同じ。
- 修正の後の読むだけの 3 つ（並行 PR の確かめ直し・再審・仕様の照らし）を、最後の段の差分の審査の後（`fixed` の後）に置く。根拠: どれも「役が作業ツリーを変えていない」を照らすので、作業ツリーを変える手直しと重ねられない。今の再審と仕様の照らしも 2 つの修正の段（中の手直しを含む）の後だった。
- `owed` の決め（`planfile.round_inputs`・`held_why`）を `lib/` に残す。根拠: plan（周を開く口）と line（構造の目を回すか）の 2 つが同じ式を引く（今の docstring「周と同じ入力の同じ並びで決めるようにこの関数を引く」）。憲法の 4。
- `when:` が読む上げ直しの欄を `checks`・`eyes_due` の真偽にする。根拠: README 1.2 の D（verify・delta-review・r1〜r4 を回すかは line の `when:`）と、KEEP の `tests/layers/test_depth_skip.py`（`when:` が名に depth を含む欄を読まない）の両方を満たす。表を引くのは line の `src/` で、`when:` は結果の真偽だけを読む。E20 の文の「ノードを深さの値で飛ばさない」は、組み込みで「深さの語を `when:` に書かない。表を引くのは line の src」に書き直す（`workflows/AGENTS.md` の決まりの直し。11.3 の 6）。
- 配る値を `start` の出力の欄 `ports` 1 つにまとめる。根拠: 始めの記録の書き手と読み口を 1 か所にする（今の L-E24 の柵の意図）。node ごとに記録を開いて引き直すと、続きの run で値が黙って変わった `8dfebca6` の形が戻る。
- `lang` は始めの記録の値をそのまま全部の include に渡す（15 節に残りの問い）。
- 受け皿を include ごとに置き、`all_done` で集める node（`collect`・`ask-final`・`fix-in`）は受け皿の got だけを読む。根拠: 今の埋め P8 のまま。block の返す node が落ちない作りでも、Archon が落ちた node への `with:` を誤りにする事実は変わらない。

## 14 消した・移した物の一覧（能力の照らし）

keep-essence の 12 の仕組みのうち、line が担う物（6・8・10・11・12）と読む物（1〜5・7・9）は、どれも block の出力の欄を読む形で残る（11 節の試験）。line から消えて block へ移った決めは、README 9.2 の line の MOVE と 1.2 の U・D の通り（承認ノードの決め・深さ・往復の記録は line に残り、計算は block へ）。落とした能力は無い。振る舞いの変わる所は 2 つ: 判定から入る無人の run が修正の後の並行 PR の重なりで止まる（8.1）・外した hunk を触る修正が拒まれる（8.2。fix の設計書が足す時）。上げ直しの数え方は 1 回目の段の後の 1 回になるが、2 度目の段は今も全部が標準に上がっていたので、結果は変わらない（5.3）。

## 15 未確認

2 波目・3 波目の設計書（diagnose・plan・plan-review・fix・delta-review・lens・r2〜r4）は、この設計書を書き終える前に置かれたので、配線は全部その 1.2 と 1.6 に合わせた。残る食い違い:

- fix に port `excluded` を足し、外した hunk を触った返答を拒む関門を受け付けに足すこと（8.2）。fix の設計書の 1.2 に無い。fix の設計書の直しで確かめる。
- fix の設計書の 16 節の 4（line の上げ直しが修正役の異議を信号に足すか）の答えは「足す」（5.3）。
- plan の設計書の 1.6 の「事前審査の port `prior` と同じファイルにできるか」の答えは「2 本に分ける」（3 節）。
- delta-review の設計書の 1.6 の「累積の差分の読み手」の答えは 4.3 の `diff`。
- diagnose の設計書の 1.6 は判定の道の `materials` を「11 本の material を並べた JSON の配列」、並行 PR の札を `pr_material` で別に受ける。judge-eyes.md の 1.3 はその形で渡す。
- 単位の深さを line が決めるのに、plan の出力 `owed` と欄 `plan` を読む（5.2）。plan の設計書の 1.6 の「line の単位ごとの深さ（`plan` の欄と `owed`）」と合う。

ほか:

- 入力 `gates` を足すことの持ち主の確かめ（冒頭・8.3）。通れば、gate-efficacy の block の `GATES_MERGE_WHY` の字を line の入力の名に替える直しを、その block の PR で出す。
- `lang` が空の時: README 5.3 は「空なら line が依頼の言語を決めて渡す」と言うが、言語を自動で選ぶ仕組みを作らない決めとぶつかる。この設計は空のまま渡す（依頼を読む役は既定の文で依頼の言語に書く）。依頼を見ない役（test-gate の任せ先・実行器の書き手）に、依頼の文の頭を引いて「この文と同じ言語」と書いた値を渡すかを決める。
- `startrec` の読む口の残し方: KEEP の lib（`headdepth`・`suitewrite`・`conflict`・`runreport`）が始めの記録を読む所が組み込みの後に残るか。残れば読む口だけを `lib/` に残す。
- 包みが始めの記録を読む `graph_map`（機能の語）は、block の外の埋めが line の記録を読む形のまま残る。README 4.3 は block の話で埋めに当たらないと読んだ。
- `fixture.FORMAT` を上げた後、今の固定材料（前の版の写し）を新しい line で使えないこと。報告の「固定材料」の行を持つ前の run の写しは取り込めず、AI の前で拒む。
- 判定から入る run で修正の後に並行 PR を回すと、無人の run が止まる場合が増える（8.1）。持ち主の決め（無人は推しで進む）とは別の、事実が無い所での止まりなので止める側に倒したが、確かめていない。
- dry-run が include の中の loop の本体に include の道を渡さない（README 13 章）ので、line の筋書きは計画の往復の中の include した block の loop の本体の script を差し替える。本体を走らせる確かめは各 block の筋書きが持つ。
