# block の設計書: gate-efficacy（ゲートの実効性確認）

- 何の話か: 対象差分が新設・変更した検証ゲート（CI ジョブ・assert・テスト・pre-commit）が、守るべき違反を本当に捕まえるかを、条件の腕ごとに壊した写しで確かめる素材の観点「ゲートの実効性確認」を、単独で呼べる block `blocks/gate-efficacy/` にする設計。素材の観点の族の 1 本で、族の共通の形は [materials.md](materials.md)、1 本目の手本は [prior-decisions.md](prior-decisions.md) に従う。型は [README.md](README.md)。
- 決めたこと: 今の judge の `material-route` の 1 列と `gate-efficacy-loop`（prep・役・accept）を、5 つの node（intake・prep・役・accept・finish）の block にする。入力は差分の根・変異の検算をまとめる道の語（`gates`）・判定から入る run の出どころ・言語の 4 つの port だけ。回す条件（`gates` が `merge` でなく、判定から入る run でない）と、ゲートの印が無い差分で役の『条件に当たらない』を受ける決め（今の `gate_signals`・`role_judged_na`）と、腕の照らし（今の `gate_arms_all_red`）は、この block の `src/` に移す。今は Python が日本語の文で組んで材料に貼っていた「変異の腕の一覧と実行器の在りか」の段（`mutation_decl`）は、md の 3 つの段落と値に割る。役のすること（写しの上で腕ごとに壊して赤・対照の緑・守る行の通過を測る。対象が宣言した変異の実行器が在ればそれで撃つ）は変えない。持ち主の決め `no-mutation-in-graph`（graph の中で変異の検算を回さない）はそのまま守る（7 節）。
- 持ち主に求めること: なし。
- 読む人と使い方: この block を作る実装者（1〜4 節の名と順をそのまま作る）。素材の観点の残りの 10 本と同時に作る（README の 11.1 の 1 波目。族の部品と prior-decisions の PR の後）。

この文書の語は README・materials.md・prior-decisions.md の頭の物を使う。よく出る物の短い言い直し（定義の正本はそれぞれの頭）: block は単独で呼べる 1 本の Archon の workflow、素材の観点（族）は判定の前に素材を集める 11 本の block、判定から入る run は差分が空で人の依頼が 1 件以上の run（port `entry` にその出どころの文〔例「人の依頼（/path/req.json）」〕が入る）、周は判定と修正の 1 回り（工場は 1 run = 1 周）、機械の節は AI でなく script が受け持つ graph の節、KEEP は作り直しの後も `lib/` に残す部品。ほかに:

- ゲートの検算の役（gate-efficacy）: 対象差分が触れた検証ゲートを、リポジトリの写し（`mktemp -d` の下）の上で腕ごとに壊して走らせ、腕ごとの結果（`arms`）と素材の状態を返す AI の役。道具は Read・Grep・Glob・Bash・WebSearch・WebFetch。Bash は網の開いた sandbox の中で走り、作業ツリーの外に写しを作れる（今の `test_run_launch`）。
- 腕: ゲートの条件の分かれ目 1 つ（例「`if body.pinned is not None:` の柵」）。返答の `arms` の 1 行 `{gate, arm, red_confirmed, control_green, hit_evidence, note?}`。`red_confirmed` は壊した写しで赤を見た、`control_green` は壊していない写しで緑を見た、`hit_evidence` はその腕が守る行を実際に通った印を見た記録。
- ゲートの印: 差分に機械が見る「ゲートに触れた」印。ゲートの定義のファイル（テスト・CI・pre-commit・フック・lint・試験の設定・変異の腕の一覧の宣言など。`GATE_FILE_PATTERNS`）と、assert を足す・消す行（今の `gate_signals`、`lib/judge_accept.py:2017-2032`）。
- 変異の宣言: 対象の根の `.review-checks.json`（`graphloops/engine/declared.py` の `DECL_NAME`）の任意の `mutation` の段 `{argv, arms}`（変異の実行器の呼び方の頭と、腕の一覧のパス）。宣言の必須の段は対象の試験の段の並び `suite` で、`mutation` はその横に置ける任意の段。宣言が JSON でない・`suite` が空などで宣言ごと読めない時は、`declared.read` が誤りの字（`error`）を返す。
- 合流の道: 始めの記録の `gates` が `merge` の run（今の `GATES_MERGE`、`lib/judge_accept.py:366`）。いくつかの run の直しを 1 つの枝に合わせた後の版で、変異の検算をまとめて 1 回撃つ道（元の works の入口の選び）で、この観点を回さない。
- 例の run: 本物の run `53e71318-ac9f-4468-ae72-5f6ed569a667`（対象 <owner>/<repo>。置き場 `~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-…/judge/`）。差分の在る通常の run（変更ファイル 23 本。テストのファイルを含む）で、変異の宣言は無い。ゲートの検算の役は 1 回目で受け付けを通った（`material-gate-efficacy.json` の `materials.gate_efficacy.status` が `found`・`count` 3、`arms` 4 行。全部の腕が赤・対照の緑・通過の印をそろえ、実 DB とフロントエンドの試験は撃てなかったと `detail` に書いた）。同じ対象の run `17ee8ecc-717a-4dc7-92b6-25ecd08fa15b` も同じ形（`found`・`count` 6・`arms` 8 行）。骨組みの値は 53e71318 から取った。

## 1 block の全体

### 1.1 役

対象差分が検証ゲートを新設・変更しているなら、ゲートが捕まえるべき違反を条件の腕ごとに 1 つずつ写しの上で作って赤を確かめ、壊していない写しで緑を確かめ、腕が守る行を実際に通ったことを印で測り、腕ごとの結果と素材の状態を返す。対象が変異の腕の一覧と実行器を宣言していればそれで撃つ。本物の作業ツリーは変えない。機械が、作業ツリーを変えていないか・腕の行が赤と対照の緑と通過の印をそろえずに `clean` を名乗っていないか・素材の欄が決まりに合うかで受け付ける。合流の道の run と判定から入る run では役を起こさず、理由つきの素材の状態を機械が書く。

### 1.2 port

入力（YAML の `inputs:`）:

- `base`: materials.md の 1.2 のまま。
- `gates`: `text: 変異の検算をまとめる道の語。"merge" は合流した版でまとめて撃つ run で、この観点を回さない（素材は not_applicable と訳）。ほかの字と空は、この run で回す`。既定 `""`。form を `text` にした訳は 7 節。
- `entry`: materials.md の 1.2 のまま。
- `lang`: `text: 人に見せる欄（material の detail・checked・reason と、arms の各行の arm・note・hit_evidence）の言語。空は依頼の言語`。既定 `""`。

`request`・`purpose` は持たない（今の穴 `MATERIAL_HOLES['gate-efficacy']`〔`lib/judge_accept.py:1733`〕にも回す条件 `gate_efficacy_due` にも出てこない）。

出力（`returns: finish`、`outcome_field: ok`）: materials.md の 1.2 の 5 欄だけ。`material.json` の `reply` は受けた返答（`material`・`arms`）、`materials` は `{"gate_efficacy": <返答の material>}`。

今との違い: 今は `gates` を始めの記録（`judge/start.json` の `gates`。`start_view`、`lib/judge_accept.py:3785`）から名で開き、回すかは `material-route` が `gate_efficacy_due` で決め、回さない時の埋めは `_fill_one`（`:1946-1949`）が `material-route.json` に書いた。受けた返答は `judge/material-gate-efficacy.json` に書き、判定役の材料（`_diagnose_ctx`、`:2764-2779`）が `reply.arms` を `record.process.gate_arms` として、`reply` を `out.p1.gate_efficacy` として読んだ。

### 1.3 node の並び（`blocks/gate-efficacy/works-factory-gate-efficacy.yaml`）

materials.md の 1.3 の雛形の `<観点>` を `gate-efficacy` にした物。

1. `intake`（script `intake.py`）: port を読み、対象差分を取り、回すかを決め、回すなら作業ツリーを写す。返り `{due, reason}`。
2. `gate-efficacy-loop`（`loop_group`、最大 3 回、`fresh_context: false`、`until_bash: done=$gate-efficacy-accept.output.done; test "$done" = true`、`when: $intake.output.due == true`）
   - `gate-efficacy-prep`（script `role_prep.py`。`with:` を持たない）: 指示を組む。返り `{prompt}`。
   - `gate-efficacy`（AI）。`prompt: "$gate-efficacy-prep.output.prompt"`・`depends_on: [gate-efficacy-prep]`。起こし方は今の `test_run_launch`（`workflows/judge/works-factory-judge.yaml:1494-1510`）を字のまま展開する: `model: '@wf-judge-materials'`・`settingSources: [user]`・`allowed_tools: [Read, Grep, Glob, Bash, WebSearch, WebFetch]`・`sandbox: {enabled: true, allowUnsandboxedCommands: false, failIfUnavailable: true, enableWeakerNetworkIsolation: true, network: {allowedDomains: ['*'], allowLocalBinding: true}, filesystem: {allowWrite: [/], denyWrite: ['~/../archon-home']}}`（今の注記「denyWrite は pr-check の注釈と同じ」は、block に pr-check が無いので prior-decisions.md の 1.3 が写す `net_closed_launch` の注記 3 行〔「作業ツリー・ほかの run の worktree・artifacts を書けなくする（~ は起動が隔離した HOME で、~/../archon-home が Archon の家。'.' は cwd でなく設定の一時ファイルのフォルダに解かれる。実測 2026-10-13。issue #293）」「起こす直前に包み（workflows/.shared/fence.py）がこの値を印と読み、cwd・共通の .git・worktree の根などを足す（#309）」。`works-factory-judge.yaml:475-477`〕を字のまま置く）・`idle_timeout: 1728000000`。`retry: {max_attempts: 2, on_error: all}`。`mutates_checkout:` は今と同じく置かない。`output_format` は今のまま（2.4）。
   - `gate-efficacy-accept`（script `role_accept.py`。`with: {reply: $gate-efficacy.output}`）: 返り `{ok, done, reason}`。
3. `finish`（script `finish.py`。`depends_on: [intake, gate-efficacy-loop]`・`trigger_rule: all_done`）: `material.json` を書き、出力を返す。どの段が落ちても落ちない。

### 1.4 place のファイル

materials.md の 1.4 の名だけ: `intake.json`・`view.json`・`diff.patch`・`changed-files.txt`・`tree.json`・`gate-efficacy-prompt-<n>.md`・`rejects-gate-efficacy.json`・`rejects-gate-efficacy.md`・`accepted.json`・`material.json`。観点だけの控えは無い。

1 つ目の commit（2.9 の指示の比べの間）だけ、`material-gate-efficacy-brief.md`（今の材料のファイルと同じ字）も書く。2 つ目の commit で書かなくなる。

### 1.5 コードの置き場

- `blocks/gate-efficacy/src/__init__.py`（空）。
- `blocks/gate-efficacy/src/signals.py`: ゲートの印。写す元 `lib/judge_accept.py:2003-2032`（注記ごと）。
  - `GATE_FILE_PATTERNS`（字のまま。最後の要素は `rf"(^|/){re.escape(checkscope.SCOPE_DECL)}$"` で、`lib/checkscope.py`〔KEEP〕を import する）・`GATE_FILES`（今の `_GATE_FILES`）・`ASSERT_LINE`（今の `_ASSERT_LINE`）。
  - `gate_signals(changed_files, diff_text: str) -> list[str]`（字のまま）。
  - `signals_of(view) -> list[str] | None`: `view.diff_file` を `encoding="utf-8", errors="replace"` で読み、`gate_signals(list(view.changed_files), 本文)` を返す。読めなければ（`TypeError`・`OSError`）`None`（今の `role_judged_na` の `:2045-2048`）。
- `blocks/gate-efficacy/src/mutation.py`: 変異の宣言の読み。写す元 `mutation_decl`（`:2083-2096`）の分かれ方だけを写し、文は持たない（2.6）。
  - `state(repo) -> dict`: `d = declared.read(repo)`（`lib/graphloops/engine/declared.py`。KEEP）。`m = (d or {}).get("mutation")`。`m` が在れば `{"declared": True, "argv": json.dumps(m["argv"], ensure_ascii=False), "arms": str(m["arms"]), "error": ""}`。無ければ `{"declared": False, "argv": "", "arms": "", "error": (d or {}).get("mutation_error") or (d or {}).get("error") or ""}`。
  - `DECL_NAME = declared.DECL_NAME`（`".review-checks.json"`）。
- `blocks/gate-efficacy/src/arms.py`: 腕の照らし。写す元 `_unproven`・`gate_arms_all_red`（`:2160-2183`）。`raise Reject(...)` を `return 文` に、`f"{nid}: "` を `f"観点 {name}: "` にした物。字は 3 節。`blank` は `lib/recount.py` の `blank`（KEEP。今の `judge_accept.blank` と同じ表 `EMPTY` と同じ長さの見方）を使う。
  - `unproven(arms) -> list[str]`・`arms_problem(name: str, reply: dict) -> str | None`。
- `blocks/gate-efficacy/src/viewpoint.py`: materials.md の 5.1 の宣言。中身:
  - `NAME = "gate-efficacy"`
  - `MATERIALS = ("gate_efficacy",)`
  - `GUARDED = False`（AI の node が `mutates_checkout: false` を持たない。今の accept の `with: {status_guarded: false, …}`。`workflows/judge/works-factory-judge.yaml:1548`）
  - `NA = "cond"`、`NA_REASON = "対象差分は検証ゲート（CI ジョブ・assert・テスト・pre-commit）を新設・変更していない"`（今の `MATERIAL_NODES['p1.gate_efficacy']['na_reason']`、`:1676`）。
  - `GATES_MERGE = "merge"`、`GATES_MERGE_WHY = "変異の検算は合流した版でまとめて 1 回撃つ（init --input gates=merge）"`（字のまま。`:366`・`:1301`）。
  - `due(view, values)`: 順に、(1) `values["gates"] == GATES_MERGE` なら `materialkit.Due(False, GATES_MERGE_WHY)`（今の `_deep_due` の `merge_off` が入口より先に見る順。`:1552-1555`）、(2) `materialkit.is_entry_run(view, values)`（`entry` が在り、かつ対象差分が空）なら `materialkit.entry_skip("ゲートの検算")`（修正が入って差分が出来た run は入口の周でないので、古い `entry` が残っていても検算を回す）、(3) ほかは `materialkit.Due(True, "ゲートの検算は合流の道でも判定から入る run でもない run で回す（差分の形の申告 touches_gates は機械が真に倒す。1 run は 1 周で、いつも初回）")`。今の `gate_efficacy_due` の 1 周目の値（`touches_gates` 真・前の周の修正なし）は、合流と入口を外せばいつも真。
  - `fill(view, values, due)`: `values["gates"] == GATES_MERGE` なら `{"gate_efficacy": {"status": "not_applicable", "reason": f"{GATES_MERGE_WHY}——差分はゲートに触れているが、この run では撃たない。合流した版を gates=merge 無しの run で回し、そこの P1 のゲートの検算が撃つ"}}`（`_fill_one` の `:1946-1949` の字のまま）。`materialkit.is_entry_run(view, values)` なら `{"gate_efficacy": materialkit.fill_entry(values["entry"], None)}`（`request` を持たないので件数の句は materials.md の 2.6 の「渡されていない」の形）。ほかは `raise NotImplementedError`（`due` が真の時は呼ばれない）。
  - `applies(view, values)`: `materialkit.Due(True, "差分が検証ゲートに触れる")`（今の `gates_touched` は `touches_gates` を機械が真に倒すので、1 run = 1 周ではいつも真。理由の字は `_touched` の真の枝の字。`:1479`）。
  - `judged_na(view, values)`: `got = signals.signals_of(view)`。`got is None` なら `False`、ほかは `not got`（今の `role_judged_na`。`touches_gates` を外して評価する条件は、前の周の修正の申告が無いのでいつも偽で、残るのは印の有無だけ）。
  - `values(view, values)`: `{"repo": str(view.repo), "base": view.base, "diff_file": view.diff_file, "changed_files_file": view.changed_files_file, "decl_name": mutation.DECL_NAME}` に、`m = mutation.state(view.repo)` から `mutation_argv`（`m["argv"]`）・`mutation_arms`（`m["arms"]`）・`mutation_error`（`m["declared"]` なら空の字、ほかは `m["error"]`）の 3 つを足した物。段落が入らない回も 4 つの値（`decl_name` を含む）をいつも渡す（条件ごとの足し分けにしない。7 節の決めと同じ）。
  - `when(view, values)`: `m = mutation.state(view.repo)`。`{"spawns": False, "mutation_declared": m["declared"], "mutation_undeclared": not m["declared"], "mutation_unreadable": (not m["declared"]) and bool(m["error"])}`。
  - `before(view, values, reply, place)`: `return None, reply, False`。
  - `after(view, values, reply, place)`: `return arms.arms_problem(NAME, reply)`。
  - `after_accept(reply, place)`: 何もしない。
  - `materials_of(reply)`: `{"gate_efficacy": reply["material"]} if isinstance(reply.get("material"), dict) else {}`（今の `writes` の `materials.gate_efficacy ← material`。`:1679`）。
  - `report_lines(doc)`: `reply` が null なら `[]`。ほかは `arms` の行ごとに `f"  - 腕: {oneline(arm)}（{oneline(gate)}。赤 {'見た' if red_confirmed else '見ていない'}・対照の緑 {'見た' if control_green else '見ていない'}・守る行の通過 {'見た' if not recount.blank(hit_evidence, 10) else '見ていない'}）"`。
- `blocks/gate-efficacy/src/oldbrief.py`（1 つ目の commit だけ）: 今の材料のファイルを同じ字で組む `brief(view, values) -> str`。今の `MATERIAL_BRIEF_HEAD`・頭の 1 文・5 つの穴の節・`MUTATION_UNDECLARED` と `mutation_decl` の文・`_na_note` の文を、この 1 本の中に字のまま持つ（2 つ目の commit でファイルごと消すので、Python が指示の文を持つのはこの間だけ）。
- 使う `lib/`: `materialkit`・`rolekit`・`oneline`・`recount`（`blank`）・`checkscope`（`SCOPE_DECL`）・`graphloops/engine/declared.py`（`read`・`DECL_NAME`）。どれも KEEP（README の 9.3）。`recount` と `checkscope` の使い手の欄に「素材の観点（gate-efficacy）」が足る。

### 1.6 つなぎ方（graph の側。block には書かない）

- 判定のまとめ（`blocks/judge/`）: `include: works-factory-gate-efficacy`、`depends_on` は materials.md の 1.6。`with:` は `base: <line が始めの記録から引いた diff_base>`・`gates: <line が始めの記録から引いた gates。無ければ空>`・`entry: <line が始めの記録から引いた出どころの文>`・`lang: <始めの記録の lang>`。
- 読み手:
  - diagnose の `materials`（11 本の `material` の配列の 1 つ）。`materialkit.assemble` が `materials.gate_efficacy` を 15 欄の 1 つにする。
  - diagnose の判定の材料の「ゲートの実効性確認」の行（今の `record.process.gate_arms` と `out.p1.gate_efficacy`）。diagnose は `materialkit.read` で読んだ `material.json` の `reply.arms`（腕の行の配列）と `reply`（返答の全部）を、今と同じ形で受ける。`reply` の形は今の `judge/material-gate-efficacy.json` の `reply` と同じなので、読み方は変わらない（読む口の作り替えは diagnose の設計書が決める）。
  - ほかに `arms` を読む物は無い（`lib/`・`workflows/`・`bin/` を `gate_arms`・`"arms"`・`gate-efficacy` の字で探した。2026-10-19）。

## 2 node の設計シート: gate-efficacy（ゲートの検算の役）

### 2.1 役

対象差分が新設・変更した検証ゲートを、写しの上で腕ごとに壊して赤・対照の緑・守る行の通過を測り、腕ごとの結果と素材の状態を返す。

### 2.2 port

`intake.json` の `view`（← port `base` と作業ツリー。`repo`・`base`・`diff_file`・`changed_files`・`changed_files_file`）・`values.gates` と `values.entry`（← port `gates`・`entry`。回すかの決めだけに使い、指示には入らない）・`values.lang`（← port `lang`）、対象の根の変異の宣言（← 作業ツリーの `.review-checks.json`。prep の時に読む）、拒否の控え（← accept が place に積んだ物）。

### 2.3 組み立ての順（`prompts/gate-efficacy.md`）

materials.md の 3.1 の並び。

1. `<!-- if rejected -->` `{shared:rejected}` `<!-- end rejected -->` — 条件: `rejects-gate-efficacy.json` に拒否が 1 件以上。`{rejection}` ← `rolekit.rejects_text(rolekit.rejected(place, "gate-efficacy"))`。
2. 役の定義の断片は置かない（今の md の頭は外への検索の決まりの塊だけ。materials.md の 5.2）。
3. `{shared:query-rule}`。`spawns: false`（Agent の道具を持たない）。
4. 役の 1 段落（決まった文）。
5. 道具の段落（決まった文。写しを `mktemp -d` に作る・作業ツリーへの書き込みは包みが止める）と `{shared:material-readonly}`。works-gh は持たない（今の `test_run_launch` は `excludedCommands` を持たない）。
6. `## Materials` と 4 つの差し込み口: `{repo}` ← `view.repo`、`{base}` ← `view.base`、`{diff_file}` ← `view.diff_file`（place の `diff.patch` の絶対パス。役は Read で読む）、`{changed_files_file}` ← `view.changed_files_file`（place の `changed-files.txt` の絶対パス）。
7. `## What to do`（決まった文）: 今の graphloops の指示の段（`material-gate-efficacy.md:34-43`）を英語にした物。中の変異の在りかの所に、差し込むかを選ぶ段落 3 つ:
   - `<!-- if mutation_declared -->` … `<!-- end mutation_declared -->` — 条件: 変異の宣言が在り、`mutation` の段が読めた。口 `{decl_name}` ← `mutation.DECL_NAME`、`{mutation_argv}` ← `mutation.state(repo)["argv"]`（JSON の配列の字。今の `json.dumps(m['argv'], ensure_ascii=False)`）、`{mutation_arms}` ← `mutation.state(repo)["arms"]`（腕の一覧のパス）。
   - `<!-- if mutation_undeclared -->` … `<!-- end mutation_undeclared -->` — 条件: 上の逆。口 `{decl_name}`。
   - `<!-- if mutation_unreadable -->` … `<!-- end mutation_unreadable -->` — 条件: 宣言の `mutation` の段が無く、宣言の読みが誤りを返した（`mutation_error` か `error`）。口 `{mutation_error}` ← その誤りの字（`declared.read` が組む日本語の 1 行。run ごとの値）。
8. `{shared:material-status}`。
9. `## Whether you may write not_applicable` と `{shared:material-na}` — 扱いは `cond`。`applies` がいつも真なので、`na_cond_true`（差分にゲートの印が在る）か `na_judged`（印が無い）のどちらかだけが真。`{na_why}` ← `"差分が検証ゲートに触れる"`。
10. `## Where to point`、観点の前置きの 1 文（決まった文。この役の返答に `where` の欄が無い）、`{shared:material-where}`。
11. 言語の 1 文と `{lang}`。
12. 結びの 1 文。

md の本文（英語。この block の 2 つ目の commit でこのまま置く）:

```markdown
<!-- if rejected -->
{shared:rejected}
<!-- end rejected -->

{shared:query-rule}

You are the gate-efficacy role. Your only job is to check that the verification gates the target diff adds or changes really catch the violations they are meant to catch. You are given neither the local findings nor any other material.

Your tools are Read, Grep, Glob, Bash, WebSearch, and WebFetch. Bash runs inside a sandbox. Make your copies of the repository in a temporary place (`mktemp -d`); the wrapper stops writes to the target's working tree.

{shared:material-readonly}

## Materials

- Repository: {repo}
- Base commit: {base}
- Target diff (from the base commit to the current state of the working tree, including new untracked files; Read it): {diff_file}
- List of changed files (one file per line; Read only what you need): {changed_files_file}

## What to do

If the target diff adds or changes a verification gate (a CI job, an assert, a test, a pre-commit hook), make, **for each conditional arm of the gate, one violation** that the gate should catch, confirm that it turns red, and put it back afterwards. **A red result from removing the whole check is not evidence that an arm is guarded** (measured: the form the design forbade most strongly turned red when the whole check was removed, yet that arm had never been hit). **Also run once on an unbroken copy and confirm it is green** (`control_green`): if the harness itself is broken, every arm shows the same colour and you can write the opposite conclusion. **Do not break the real working tree: for each arm, make a copy of the repository under `mktemp -d`, break the copy, and run the whole set of checks on it** (a copy inside the repository dirties the working-tree comparison and the records, and breaking a shared tree and restoring it cannot, in principle, be detected by comparing the state before and after). Do not treat a gate whose red you have never confirmed as verified.

**A red result is not evidence that the red came from the line you want to guard.** For each arm, also measure that **the run actually passed through the line that arm guards** (`hit_evidence`). How to measure it: make one more copy in which the value that the check (the branch) writes is replaced with a unique marker, and see that the marker appears in the output or in the records. If it does not appear, that scenario never passed through the guarded line (measured 2026-09-13: for the check on whether a value may be carried over, injecting a regression left the checks green, and the marker did not appear in the records either). Only when the red, the green of the control, and this are all present does the arm count as evidence of coverage.

**If the target repository has a list of mutation arms and a mutation runner, fire with them.** Where they are and how to call them:

<!-- if mutation_declared -->
the mutation stage of the target repository's declaration `{decl_name}`: the head of the runner's command line is {mutation_argv}, and the list of arms is {mutation_arms} (the runner's `--help` is the authority on the spelling of its options).
<!-- end mutation_declared -->
<!-- if mutation_undeclared -->
the target repository's declaration (`{decl_name}`) has no mutation stage. Look for where they are and how to call them in what the target repository itself names (its README, CONTRIBUTING, CI definitions, its own REVIEW.md, and so on). This prompt does not carry the names of tools or the spelling of their arguments.
<!-- end mutation_undeclared -->
<!-- if mutation_unreadable -->
(The declaration exists, but its mutation stage cannot be read: {mutation_error})
<!-- end mutation_unreadable -->

If the runner has a way to build the shape of this answer from the results it fired, return that output as it is; do not rebuild it by hand. If whoever runs it writes a throwaway script on the spot, arms whose replaced string disappeared when the code was rewritten drop out silently, and nobody can fire the same arm in the next round either (measured 2026-09-23: 25 arms dropped out in the first round and 18 in the second). If this diff added or fixed a check, adding or fixing its arm in the list is also part of this diff's work. But fixing the list is not this role's job: the step that fixes the diff after the judgment does it, and this role changes neither the list nor the working tree. If you find an arm that is missing from the list or out of date, fire that arm by hand on a copy, write in that row's `note` in `arms` that the mutation arm list needs this arm added (or fixed), and write the same in `material.detail` (a record so that the fix includes it). In a repository with no list, do the steps above by hand on a copy.

If results fired earlier exist and the runner has a way to carry earlier results over, pass them to it and fire fewer arms. Other runs are working on the same machine, so run the runner at low priority (with `nice -n 19`). Wait until it has finished firing: if the runner rewrites its results after each arm, then even if it stops partway, the rest can be fired by passing the same results to its carry-over option.

Do not kill it from outside after a time limit (`timeout` and the like) (measured 2026-09-24: a delegate fired all arms under `timeout 1800` and answered that it had written results when there were none).

In `arms`, give `gate`, `arm`, `red_confirmed`, `control_green`, and `hit_evidence` for each arm.

{shared:material-status}

## Whether you may write not_applicable

{shared:material-na}

## Where to point

This role's answer (`material` and `arms`) has no `where` field. The rule below applies when you write a location as `<path>:<line>` inside the `note` or `hit_evidence` of an arm, or inside `material.detail`.

{shared:material-where}

Write `material.detail`, `material.checked`, `material.reason`, and the `arm`, `note`, and `hit_evidence` of each row of `arms` in {lang}. Keep keys, enum values, identifiers, paths, commands, and quoted text as they are.

Return only JSON that matches the output schema.
```

md の中に `$` の字は無い。差し込み口のほかの `{` も無い。変異の 3 つの段落は入れ子にせず並べ、`mutation_unreadable` は `mutation_undeclared` が真の時だけ真になる（2 つが同時に入る形で、今の「探させる文（読めない訳）」の字の並びと同じ）。

言語・会話・retry は prior-decisions.md の 2.3 の終わりと同じ。

### 2.4 返す形

今の `output_format` のまま（`workflows/judge/works-factory-judge.yaml:1512-1542`）:

- `material`: prior-decisions.md の 2.4 と同じ形（`status` の 6 語・`count`・`detail`・`checked`・`reason`・`from_round`、`required: [status]`）。
- `arms`: `[{gate, arm, red_confirmed (boolean), control_green (boolean), note?, hit_evidence}]`・各行 `additionalProperties: false`・`required: [gate, arm, red_confirmed, control_green, hit_evidence]`。
- 全体 `additionalProperties: false`・`required: [material, arms]`。

人に見せる欄は `material.detail`・`material.checked`・`material.reason` と、`arms` の各行の `arm`・`note`・`hit_evidence`（判定の材料と報告の行に載る）で、言語は `{lang}`。`gate` はゲートのファイルや名の名指しなので字のまま。

### 2.5 描いた骨組み（例の run の値）

例の run では、今の指示は 2 か所に在った: `workflows/judge/commands/material-gate-efficacy.md`（54 行。`$gate-efficacy-prep.output.lang_line`・`.reason`・`.brief_file` を Archon が入れた物）と、役が Read した `judge/material-gate-efficacy-brief.md`（27 行）。新しい指示はこの 2 つを 1 本にする:

```markdown
{shared:query-rule の本文: Rules for queries to outside services …}

You are the gate-efficacy role. …（決まった文。役は同じ会話の続きで起こし直されるので「新しい会話」とは書かない）

Your tools are Read, Grep, Glob, Bash, WebSearch, and WebFetch. Bash runs inside a sandbox. …

{shared:material-readonly の本文: Do not change a single character of the target's working tree, …}

## Materials

- Repository: ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/worktrees/archon/task-works-factory-line-1792307529854
- Base commit: 7defb7ec5fac098b7302f5bfc11a02f151f4d262
- Target diff (…; Read it): ~/.local/state/works-factory/targets/316e3bbc/archon-home/workspaces/<owner>/<repo>/artifacts/runs/53e71318-ac9f-4468-ae72-5f6ed569a667/judge/gate-efficacy/diff.patch
- List of changed files (…): ~/…/runs/53e71318-ac9f-4468-ae72-5f6ed569a667/judge/gate-efficacy/changed-files.txt

## What to do

If the target diff adds or changes a verification gate …（決まった文 2 段落）

**If the target repository has a list of mutation arms and a mutation runner, fire with them.** Where they are and how to call them:

the target repository's declaration (`.review-checks.json`) has no mutation stage. Look for where they are …

If the runner has a way to build the shape of this answer …（決まった文 3 段落と arms の 1 文）

{shared:material-status の本文: How to write `material`: …}

## Whether you may write not_applicable

The condition of this viewpoint holds for this run (差分が検証ゲートに触れる), so the acceptance step rejects `not_applicable`. …

## Where to point

This role's answer (`material` and `arms`) has no `where` field. …

Write the `<path>:<line>` of a location (`where`) as a line number in the current file in the working tree. …

Write `material.detail`, … in the language of the request (the user's language). …

Return only JSON that matches the output schema.
```

例の run は 1 回目で通ったので却下の段落は入らない（`rejects-gate-efficacy.json` が無い）。対象の根に変異の宣言の `mutation` の段が無く、読みの誤りも無かったので、`mutation_undeclared` の段落だけが入る（今の材料のファイルの「## 材料: loop.mutation_decl.text」が `MUTATION_UNDECLARED` の字だけだったのと同じ）。変更ファイルに `backend/tests/api/_fakes.py` などのテストのファイルが在り、ゲートの印が在るので、『条件に当たらない』は `na_cond_true` の段落（今の材料のファイルの末尾の節「このノードの条件 `gates_touched` はこの周に真（差分が検証ゲートに触れる）なので…拒む」と同じ扱い）。差分と変更ファイルのパスは、今の `judge/diff.patch`・`judge/changed-files.txt` から、判定のまとめから include された時の place（`judge/<この観点の include の id>/`）に移る（include の id は判定のまとめが決める。ここでは `gate-efficacy` と書いた）。`lang` は空で、`{lang}` に既定の文が入った形。

### 2.6 今の指示との差

今の指示は `workflows/judge/commands/material-gate-efficacy.md`（54 行）と、`lib/judge_accept.py` の `material_prep`（`:2116-2135`）が描く材料のファイルの 2 か所に在る。prior-decisions.md の 2.6 と同じ移し・まとめ（材料の節を `## Materials` へ・『条件に当たらない』の節を `{shared:material-na}` へ・却下の段落 2 つを `{shared:rejected}` の 1 回へ・作業ツリーを変えるなの句を `{shared:material-readonly}` へ・素材の書き方を `{shared:material-status}` へ・所見の場所の段を `{shared:material-where}` へ・言語の 1 行を md の 1 文へ・「graphloops のノード p1.gate_efficacy を…行う」と見出しと区切りの `---` を消す）は、ここでも同じ。この観点だけの差:

- 移した: 外への検索の決まりの塊（md:3-10）を `{shared:query-rule}` に。今の md の頭の「Agent で子を起こすなら、子への指示に下の塊をそのまま含めよ」は、この役が Agent を持たないので `spawns: false` で入れない段落になる。
- 割った: 材料のファイルの「## 材料: loop.mutation_decl.text」（Python の `mutation_decl` が `MUTATION_UNDECLARED` などの日本語の文で組んだ 1 段落。`:2083-2096`・`:1733`）を、md の 3 つの段落（`mutation_declared`・`mutation_undeclared`・`mutation_unreadable`）と値（`decl_name`・`mutation_argv`・`mutation_arms`・`mutation_error`）に。決まった文を md に、run ごとの値（宣言の中身と読みの誤り）だけを Python に残す（憲法の 2）。分かれ方（段が在る・無い・無くて誤りが在る）は今の 3 通りのまま。
- 移した: 道具の段（md:28 の手順 3）の「写しは一時の置き場（mktemp -d）に作れ。対象の作業ツリーへの書き込みは包みが止める」を道具の段落に。手順 3 の尾の「1 文字も変えるな…」は `{shared:material-readonly}` に。
- 残した: 所見の場所の段の前置き「この役の返答（material と arms）には `where` 欄が無い。下の決まりは、arms の note・hit_evidence や material の detail の中で場所を書く時に当てる」（md:50。#221）を、観点の前置きとして `## Where to point` の頭に。
- 消した: 「前の周の修正と手直しが足した分岐を、起点の版から機械で作る腕で撃つのは前の周の並行のノード（p3.delta_gates）で、ここでは撃たない」（md:40 の中ほど）。訳: 名指す `p3.delta_gates` は工場に無いノード（持ち主の決め `no-mutation-in-graph`。`docs/nodes.json` の `absent`）で、1 run = 1 周なので「前の周の修正」も無い。block はほかの役を名指さない（憲法の 3）。役のすることは変わらない（撃たない物の名指しが消えるだけ）。
- 消した: graphloops の見出し「P1 ゲートの実効性確認（writer が実行・該当 PR のみ）」（md:34）。「writer が実行」は graphloops の起こす側の名で、この役の振る舞いを決めない。
- 言い換えた: 「P3（判定の後に差分を直す段）」（md:40 の 2 か所）を "the step that fixes the diff after the judgment" に（段の番号で他の block を名指さない）。「変異の腕の一覧に足す（直す）要あり」の字は、機械が読まない（`lib/`・`workflows/` を探して読み手が無い）ので、決まった字を求めず、`{lang}` で書く人に見せる note の中身として言い換えた。
- 消した: 素材の書き方の尾「欄と値の正本は review-record.py」（prior-decisions と同じ）。
- 足した物は無い。英語にした（#764）。役の名「ゲートの実効性確認の役（任せ先）」は "the gate-efficacy role"。

### 2.7 元の works と graphloops の同じ場面

族の形の差は materials.md の 9 節。この観点だけの差:

- 元の works の `works/blk-material/commands/gate-efficacy.md`（8 行）は、engine が描いた graphloops の指示書のファイル（`prompt_file`）を Read で読ませる薄い md だった。工場は指示書を md の中に写し、値だけを材料のファイルにした（#76）。新しい形は値も指示の中に入れる。
- 指示書の本文は、元の works が持った graphloops の写し（`works/.shared/core/gl-prompts/prompts/review-loop/p1.gate_efficacy.md`）と、graphloops の今の物（`~/src/claude-plugins/graphloops/prompts/review-loop/p1.gate_efficacy.md`）で、語の違い（「柵」と「チェック」・「節」と「ノード」・`hist.snapshot.diff_file` と `loop.diff_file`）のほかは同じ。工場はそこに 2 つを足した: 一覧を直すのは判定の後に直す段でこの役は一覧も作業ツリーも変えない・足りない腕は写しの上で手で撃って `note` と `detail` に「一覧に足す要あり」と書く（元は「P3 の修正に含めよ」の 1 句。#221）と、所見の場所の段の前置き（#221）。この block も持つ。
- 差分の形の申告 `touches_gates`: graphloops は p0.base の AI の役が差分を読んで申告する（`prompts/review-loop/p0.base.md:15`）。元の works の線 A と工場は p0.base を機械の節にし（工場 #76・`docs/nodes.json` の `p0.base` は `by: machine`、#129）、`touches_gates` を判定せずに真へ倒す。その代わりに、ゲートの印が無い差分ではゲートの検算の役の『条件に当たらない』を受ける差し替え（元の works の `works/.shared/core/entry.py:206-255` の `gate_signals`・`role_judged_na_works`）を #76 で移した。工場はゲートの定義のファイルの表を `*.ini`・`*.cfg` 全部に広げた（元の works は `tox.ini`・`pytest.ini`・`setup.cfg`・`mypy.ini` の名指し。試験の実行器の名が言語の中立の語の表〔E13〕に当たるため。#76）。この block も同じ表を持つ。graphloops の p0.base の役は、工場に無い（意図して外した記録は #76 の「p0.base は機械」の置き換えだけ。p0.base の役そのものを外した PR は（未確認））。
- graphloops の変異の検算（`p3.delta_gates`・`p4.final_gates`。直したコードを機械で作る腕で撃つ）は、元の works にも工場にも無い。持ち主の決め `no-mutation-in-graph`（2026-10-13、#378）でグラフに戻さない。この観点の役が、対象が宣言した実行器を写しの上で撃つ・手で壊して撃つのは、その決めの外の、判定の前の素材の測りで、今もしている（例の run の 2 本とも、宣言が無く手で撃った）。この block はそれを変えない。
- 回さない道（合流の道 `gates=merge`）: 元の works は入口の `init --input gates=merge` で選べた（`GATES_MERGE_WHY` の字に名残がある）。工場の line は始めの記録に `gates` を書かない（`lib/`・`workflows/`・`bin/` に書き手が無い。2026-10-19）ので、今の工場の run ではこの道に入らない。意図して外した記録は（未確認）。この block は port `gates` で受け、道そのものは今の条件のまま残す。
- 受け付け: 元の works の受け付け（`works/blk-material/lib/material.py` の take）と工場の受け付けは同じ順で、後の照らし `gate_arms_all_red` は graphloops の `MATERIAL_NODES` の `post_check` の写し（元 rules:3023）。

この block が両方より良く、残す物: 機械が `touches_gates` を倒しても、ゲートの印の無い差分では役の判断で『条件に当たらない』を受け、印が在れば測らせる（graphloops は p0.base の役の判断だけ、元の works は同じ）・腕が赤・対照の緑・守る行の通過をそろえずに `clean` を名乗るのを機械が拒む・作業ツリーを機械が照らす・変異の宣言の在りかを指示に入れ、無い時は道具の名を持たずに対象の側を探させる。

### 2.8 受け付け

materials.md の 4 節の順。観点の前の照らしは無く、後の照らしは `arms.arms_problem`（3 節）。

- 拒む物: JSON のオブジェクトでない返答・役が作業ツリーを変えた（`GUARDED` が偽なので比べる欄は `porcelain` を含む全部。写しを作業ツリーの中に作った時もここで拒む）・腕の照らし（3 節の 3 つ）・素材 `gate_efficacy` が無い・`carried_over`・`not_applicable`（`na_cond_true` の run。`na_judged` の run は受ける。materials.md の 2.8）・知らない status・status ごとの要る欄の欠け。
- 所見の場所: この返答は `where` と `text` を両方持つ行を持たないので、`materialkit.where_rows` は何も拾わず、場所の照らしは拒まない（今と同じ）。md の前置きと `{shared:material-where}` は、役が `note`・`hit_evidence`・`detail` の中に場所を書く時の書き方として残す。
- 返答の形（`output_format`）の外れは Archon が node の段で拒む。
- 3 回目の拒否でループを抜け、`finish` が `status: gave_up`・最後の拒否の文・素材に `not_run` を書く（prior-decisions.md の 2.8 と同じ）。

### 2.9 試験

- standalone の fixture（`blocks/gate-efficacy/fixtures/`）:
  - `standalone.stubs.yaml`: `fixture.inputs` は `base: ""`・`gates: ""`・`entry: ""`・`lang: ""`。AI の node `gate-efficacy` だけを台本の返答（`material: {status: clean, checked: "…"}`・`arms` 1 行〔`red_confirmed: true`・`control_green: true`・`hit_evidence` 10 字以上〕）で差し替え、script は本物。`reached` に `finish`。`finish` の `status` が `ran`。
  - `gave-up.stubs.yaml`: 台本の返答は `material.status: clean`・`arms: []`（腕が 0 行で拒まれる）。筋書きでは輪が 1 周で終わるので拒否は 1 回で、run は `completed`、出口は落ちずに返る（fixture 自身の注にあるとおり）。3 回で諦めて `finish` が `status: gave_up` を返す数えは `test_gate_efficacy.py` の `test_three_rejections_give_up` が確かめる。
  - `skipped.stubs.yaml`: `gates: merge`。AI の node に届かず、`finish` の `status` が `skipped`。
  - `entry.stubs.yaml`: `entry: "人の依頼（standalone）"`。`finish` の `status` が `skipped`。
- `tests/blocks/gate_efficacy/test_gate_efficacy.py`（materials.md の 8 節の block の試験。始めの記録の無い使い捨ての `ARTIFACTS_DIR` と git のリポジトリ）:
  - 写す元 `lib/tests/test_judge_accept.py::DueCase.test_gates_merge_turns_gate_efficacy_off`: `gates: merge` なら `intake` の `due` が偽で、`material.json` の `gate_efficacy` が `not_applicable`・`reason` が `GATES_MERGE_WHY` で始まる。`entry` が在れば `due` が偽で、`fill_entry` の字。合流と入口が両方在れば合流の字（順の照らし）。
  - 写す元 `MaterialCase.test_accept_rules` の `gate-efficacy` の部分: `clean` で `red_confirmed: false` の腕を持つ返答は拒まれ、`accepted.json` が無い。
  - 写す元 `MaterialCase.test_gate_role_may_judge_a_gate_free_diff_not_applicable`: ゲートの印の無い差分（`app.txt` だけ）では、組んだ指示に `na_judged` の段落が入り、`not_applicable` の返答を受ける。`test_app.txt` を足した差分では `na_cond_true` の段落が入り、同じ返答を拒む。
  - 写す元 `MaterialCase.test_gate_prep_shows_the_declared_mutation_stage` の 5 つの場合: 宣言の段が在る（`mutation_declared` の段落が入り、値に `["mutate", "--fast"]` と `arms.txt`）・段が無い（`mutation_undeclared` だけ）・段が壊れている（`mutation_undeclared` と `mutation_unreadable`、値に誤りの字）・宣言が JSON でない・`suite` が空（どちらも `mutation_undeclared` と `mutation_unreadable`）。照らすのは段落の真偽と値で、文の字ではない。
  - 足す（腕の照らし）: 3 節の 3 つの文がそれぞれの返答で出る。`found` で未達の腕は 2 つ目を通る。`awaiting_human` で未達の腕は 2 つ目を通る。3 つがそろった腕だけの `clean` は通る。
  - 足す（起こし方の照らし）: block の YAML の AI の node の `model`・`allowed_tools`・`sandbox`・`idle_timeout`・`retry` が、今の `tests/workflows/test_judge.py:95` の表の gate-efficacy の行（`"sonnet", "medium", INVESTIGATE, DELEGATE, …`）が照らす物と同じ。
- `tests/blocks/gate_efficacy/test_signals.py`: 写す元 `lib/tests/test_judge_accept.py::GateSignalsCase` の 4 本（`test_docstring_only_diff_has_no_signal`・`test_gate_files_are_signals`・`test_added_or_removed_assert_is_a_signal`・`test_context_assert_is_not_a_signal`）を `src.signals.gate_signals` に向ける。`test_only_the_gate_node_lets_the_role_judge`（ほかの節は差し替えを受けない）は写さない（`judged_na` はこの block の宣言だけが持ち、ほかの観点の `judged_na` が偽を返すことは各観点の `test_viewpoint.py` が見る）。
- `tests/blocks/gate_efficacy/test_viewpoint.py`: materials.md の 8 節。`NA == "cond"` なので `applies` は `Due(True, …)` を返し、`fill` は `due` が真の値で `NotImplementedError` を上げる。
- 指示の比べ（README の 11.4）: `tests/blocks/gate_efficacy/test_prompts.py`（1 つ目の commit だけ。2 つ目の commit で消した）。
  - 1 つ目の commit: `prompts/gate-efficacy.md` を、今の `workflows/judge/commands/material-gate-efficacy.md` の `$gate-efficacy-prep.output.lang_line` を `{lang_line}` に、`.reason` を `{reason}` に、`.brief_file` を `{brief_file}` に替えた日本語の字で置く（prior-decisions.md の 2.9 と同じ形）。試験は例の run の値（`base`・リポジトリのパス・変異の宣言なし・ゲートの印あり）で、(a) 組んだ指示が今の md に同じ 3 つの値を入れた字と同じ、(b) `oldbrief.brief` の字が例の run の `judge/material-gate-efficacy-brief.md` と同じ（run directory とリポジトリのパスは試験の物に置き換えて比べる）ことを照らす。
  - 2 つ目の commit（英語）: 1 つ目の試験と `src/oldbrief.py` を消し、例の run の値で組んだ新しい指示と、今の md と材料のファイルを並べた物を PR に載せ、2.6 の差の一覧どおりかを審査に出す。
- 守る keep-essence の番号: 無い（README の 10 節の 12 の仕組みにこの観点は出てこない。1 の赤緑の機械の判定は fix の仕組みで、この観点の腕の赤とは別）。守るのは「腕が赤・対照の緑・守る行の通過をそろえずに `clean` を名乗れない」と「ゲートの印の無い差分だけ役の『条件に当たらない』を受ける」で、上の試験が見る。
- 終わりの条件の命令（1 モジュールずつ。1 つ目の commit では `tests.blocks.gate_efficacy.test_prompts` も回した。2 つ目の commit で消した）:

```sh
uv run --isolated python3 -m unittest discover -s tests/blocks/gate_efficacy -t .
uv run --isolated python3 -m unittest tests.layers.test_block_shape
```

## 3 script の node

materials.md の 6 節の雛形のまま。この block だけの物:

- `intake.py` が読む入力は `INPUTS_BASE`・`INPUTS_GATES`・`INPUTS_ENTRY`・`INPUTS_LANG` の 4 つ。どれも `ports.text(…)`。値の dict の鍵は `base`・`gates`・`entry`・`lang`。
- 1 つ目の commit だけ、`role_prep.py` が `src.oldbrief.brief(view, values)` を place の `material-gate-efficacy-brief.md` に書いてから組む。

## 4 受け付けの文

materials.md の 2.8 と 4 節の文のほかに、後の照らし `arms.arms_problem(name, reply)` の 3 つ（今の `gate_arms_all_red` の字の `{nid}:` を `観点 {name}:` に替えた物。順に見て、最初に当たった 1 つを返す）。`arms = reply.get("arms", [])`、`st = reply.get("material", {}).get("status")`、`blank` は `recount.blank`（`blank(s, 10)` は、字が空同然の語の表 `EMPTY`〔「なし」「n/a」「未確認」など〕に当たるか、前後の空白を除いて 10 字未満なら真）:

1. `arms` が空で `st` が `materialkit.OBSERVED_STATUS`（`found`・`clean`）のどれか: `f"観点 {name}: status={st} なのに腕が 0 行——撃った腕を行にするか、撃てた腕が無いなら not_run（理由つき）で書け"`
2. `st` が `found` でも `awaiting_human` でもなく、`unproven(arms)`（赤・対照の緑・`hit_evidence`〔`blank(…, 10)` でない〕のどれかを欠く腕）が空でない: `f"観点 {name}: 赤を見ていない腕 {unred} / 壊していない写しで緑を確かめていない腕 {nocontrol} / 守る行を通ったことを測っていない腕 {nohit} が在るのに status=clean——未達は found（count と detail に腕を書く）、人の起動待ちなら awaiting_human（reason に何を待つか）"`。`unred`・`nocontrol`・`nohit` は、それぞれ `red_confirmed` が偽・`control_green` が偽・`blank(hit_evidence, 10)` が真の腕の `arm` の list（`repr` の字のまま）。字の `status=clean` は `st` が `not_run` などでも今のまま出す（6 節）。
3. `red_confirmed` と `control_green` が真で `blank(hit_evidence, 10)` が真の腕が 1 つ以上（status を問わない）: `f"観点 {name}: 腕 {nohit} は赤も control の緑も見ているが、**その腕が守る行を通ったこと**を測っていない（hit_evidence）——赤は柵の不在の検知であって、この腕がその柵に当たった証拠にならない。分岐が書く値を一意の印に替え、その印が出力か記録に現れることを確かめて hit_evidence に書け"`

どれにも当たらなければ `None`。

## 5 単独で呼ぶ

```sh
bin/works-factory <読ませるフォルダを blocks/ にする引数（名は土台の PR で決める）> workflow run works-factory-gate-efficacy \
  --input base=<差分の根の commit> --input gates= --input entry=
```

作業ツリーは Archon の cwd（対象のリポジトリ）。出力は `workflow get <run>` の `finish` の返り。始めの記録は要らない。`base` を空にすると HEAD からの差分（未追跡の新しいファイルを含む）を見る。役は写しを作業ツリーの外（`mktemp -d`）に作り、網に出る（試験の依存を取りうる）。

## 6 未確認

- 工場の line が始めの記録に `gates` を書くか。今は書き手が無く（2.7）、合流の道は試験でしか通らない。新しい line の設計書が `gates` を始めの記録の欄として残すかを決める。この block は port の既定 `""` で今の run と同じに動く。`GATES_MERGE_WHY` の字の「init --input gates=merge」は元の works の入口の名残で、工場の起動の殻に同じ入力は無い。字は振る舞いを変えないよう今のまま写した。
- 腕の照らしの 2 つ目の文の「status=clean」が、`st` が `not_run`・`not_applicable` の時にも出ること（今の `gate_arms_all_red` のまま）。直すかは、この作り直しの後に別に扱う（振る舞いを変えない）。
- 変異の宣言の `argv`・`arms` と読みの誤りの字は対象のリポジトリの中身で、`$` の後に英字が続く字（例 `$HOME`）を含みうる。materials.md の 3.1 の「値に `$…` を置かない」は対象の中身までは縛れない。Archon が `prompt:` の値の中の `$…` を置き換え直すかは、土台の PR の確かめ（README の未確認の一覧の大きい指示の行と同じ所）に寄せる。
- 判定のまとめが付ける include の id（2.5 の骨組みのパスの `judge/gate-efficacy/`）。

## 7 自分で決めた事（この block だけ）

- port `gates` の form を `text`（`"merge"` だけが意味を持ち、ほかの字と空は回す）にする。訳: 今の始めの記録の `gates` は形を問わない字で（`start_view` は字でなければ空）、条件は `gates == "merge"` の等しさだけを見る。`choice(merge|…)` にすると空と他の字を受ける今の読みと外れ、読めない入力で `failed` になる道が増える。
- 変異の在りかの段（今の `mutation_decl` が Python の日本語の文で組んだ物）を、md の 3 つの段落と 4 つの値に割る。訳: 憲法の 2（Python は指示の文を持たない）。分かれ方は今の 3 通りのままで、run ごとの値（宣言の中身と読みの誤り）だけが Python に残る。`MUTATION_UNDECLARED` の文は 1 つ目の commit の `oldbrief.py` にだけ残る。
- 「p3.delta_gates で撃つのでここでは撃たない」の句を消す。訳: 名指すノードは工場に無く（`no-mutation-in-graph`）、1 run = 1 周で「前の周の修正」も無い。撃たない物の名指しなので、役のすることは変わらない。
- 腕の照らしの `blank` に `lib/recount.py` の `blank` を使い、写さない。訳: 同じ表 `EMPTY` と同じ見方（字の欄では同じ値を返す）を持つ KEEP の部品が在る。3 つ目の写しを block に置くと、空同然の語の表が 3 か所に割れる。返答の `hit_evidence` は `output_format` で字に決まるので、`recount.blank` の字でない値の扱い（空とみなす）の違いは効かない。
- ゲートの印・変異の宣言の読み・腕の照らしを `src/` の 3 つのファイル（`signals.py`・`mutation.py`・`arms.py`）に分ける。訳: 写す元が `lib/judge_accept.py` の別々の所（`:2003-2050`・`:2083-2096`・`:2160-2183`）にあり、試験も別々（`GateSignalsCase`・`test_gate_prep_shows_the_declared_mutation_stage`・`test_accept_rules`）。1 本にすると `viewpoint.py` が宣言の外の中身を持つ。
- `due` の回す時の訳の字を「ゲートの検算は合流の道でも判定から入る run でもない run で回す（…1 run は 1 周で、いつも初回）」にする。訳: 今の字（「…前の周の P3 が何かを直した周——成り立つ（round=1・…）」）は 1 run = 1 周で効かない枝を名指す。prior-decisions.md の `due` の字と同じ書き方にそろえた。回さない時の訳と素材の埋めの字は今のまま。
- 回さない時の fixture を、合流（`skipped.stubs.yaml`）と入口（`entry.stubs.yaml`）の 2 本にする。訳: 回さない道が 2 つ在り、埋めの字が違う。
- 報告の行に腕ごとの 1 行を足す。訳: 素材の 1 行（materials.md の 2.10）は `detail` を 1 行に縮めるので、腕の 3 つの印のどれが欠けたかが報告から見えない。腕の行は判定の材料に載る事実そのまま。
- 変異の 4 つの値（`mutation_argv`・`mutation_arms`・`mutation_error` と `decl_name`）は、段落が入らない回も空の字でいつも渡す（`values` の欄で、3 条件の足し分けにしない）。訳: 共通の `prompt.render` が選ばれない段落の中の差し込み口にも値を要り、足りないと落ちる（`.shared/AGENTS.md`）。
- `fill` の判定から入る run の枝は `materialkit.fill_entry(entry, None)`（件数の句は「渡されていない」）にする。訳: 1.5 の `0` は「0 件」と読まれ、この block は `request` を持たないので事実と違う。materials.md の 2.6 は `request` を持たない観点に `None` を渡すと決めている。
- md の役の 1 段落から「started in a new conversation」を外し、"You are the gate-efficacy role." で始める。訳: 輪が `fresh_context: false` で、2 回目以降は同じ会話の続きで出し直すため、「新しい会話」は事実に合わない（調整役の指摘）。`fixtures/` の決まった文もこれに合わせた。prep・役・accept は 1 つずつ別の層で、同じ層に並ぶ node は無い。
- 1 つ目の commit の `oldbrief.py` は、今の `material_prep` の材料のファイルと同じ字を試験で突き合わせる（`test_prompts.py`。今の `judge_accept` を直に呼んで比べる）。例の run のファイルは使わない（手元の家のパスが要るため）。2 つ目の commit で `oldbrief.py`・`test_prompts.py` と prep の旧い値の渡し方を消した。
