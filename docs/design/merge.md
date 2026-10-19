# block の設計書: merge（差分の確定と取り込み）

- 何の話か: run の差分を封じて hash を取り、守りのファイルに触れたかを数え、最後の承認ノードの後に封じた差分と今の差分を照らしてから置く（出口の語 pr なら run の枝に積んで PR を作る）観点「差分の確定と取り込み」を、単独で呼べる block `blocks/merge/` にする設計。AI の node を持たない。型は [README.md](README.md)、書き方は [world.md](world.md) に従う。
- 決めたこと: 今の `workflows/merge/` の 5 つの node（place・pr-commit・pr-open・pr-read・merge）を、同じ並びの block にする。始めの記録の代わりに差分の根を port `base` で受け、出力に報告の行の欄 `report` を足す。守りのファイルの当たりを数えるのは、今の独立の目（eyes）の重ねの数えをやめて、この block の seal と apply だけにする（README 13 節）。形は seal・apply・check の 3 つを残し、PR の作成は Archon 同梱の `archon-pr` を子の run として起こす今の形を残す。振る舞いは変えない。
- 読む人: この block を作る実装の役（この設計書だけで作れるように書いた）。急ぎではない（README 11.1 の 1 波目。ほかの block と並べて作る）。
- 持ち主に求めること: なし。README の 8.4 と違う所（形が 3 つ・入力 `diff` が無い・`workflow: archon-pr`）は、どれも今の持ち主の決めと履歴から 1 つに決まったので、10 節に根拠を書いて進めた。keep-essence の 10 と封じた差分の守りの割り当ては 8 節。

この文書の語は README の頭の物を使う。ほかに:

- 封じる（seal）: 作業ツリーと差分の根の間の差分のバイトを place に書いて読み戻し、sha256（封じた hash）を取ること。最後の承認ノードで人が見るのはこの差分。
- 置く（apply）: 最後の承認ノードの後に、今の差分の hash が封じた hash と同じで、置いてよい決まり（4 節の `seal.apply_refusal`）を満たす時だけ、差分を place に書くこと。対象のリポジトリに当てるのは人（`bin/apply`）。
- 照らすだけ（check）: 周の鎖（chain）が、元の基から最後の差分までを封じた hash と照らして置くこと。答えと確かめは差分を作った所（各周の line）で済んでいる。
- 守りのファイル: 工場自身の試験・柵・受け付けの口の一覧（`lib/protected.json`。走っている pack の物を読む）と、対象のリポジトリが根の `.works-protected.json` で守ると宣言したファイル（差分の根の版の物を読む）。当たれば最後の承認ノードを必ず開き、通すのは人の答えだけ（keep-essence の 10）。
- 確かめられない行: 一覧や宣言が読めない・差分を数えられない時に、当たりとして数える 1 行（`seal.UNKNOWN_HEAD` で始まる）。黙って空にしない。
- 出口の語: `deliver` の値。空は置くだけ、`pr` は PR まで（`lib/entry.py` の `DELIVERS`）。
- 例の run: 本物の run `df5e111f-ea97-409b-8066-2245d32746ab`（対象 raiki61/works-factory、出口の語 pr）。置き場 `~/.local/state/works-factory/targets/6c76444e/archon-home/workspaces/raiki61/works-factory/artifacts/runs/df5e111f-…/merge/`（`sealed.diff`・`apply.diff`・`protected-all.json`）。PR #759 を下書きで作った。

## 1 block の全体

### 1.1 役

seal は、今の作業ツリーと差分の根の間の差分を封じ、守りのファイルに当たった行（全件の数と、先頭の数行と残りの 1 行）を返す。試験の後に作業ツリーが変わっていれば（緑の認証の指紋が今の木と違えば）封じても ok にしない。apply は、封じた hash と今の差分の hash を照らし、最後の答え・R2・緑・独立の目・指紋・守りの当たりを決まった順に見て、置いてよい時だけ置く。check は hash だけを照らして置く。apply と check の後、出口の語が pr なら、照らした差分を run の枝に修正案の項目ごとの commit で積み、`archon-pr` の子の run に push と PR の作成を任せ、作った PR を積んだ枝と commit に照らして読み戻す。どの誤りでも落ちず、`ok: false` と訳を返す。

### 1.2 port

入力（YAML の `inputs:`）:

- `mode`（必須）: `choice(seal|apply|check): 形。seal は今の差分を封じて守りのファイルの当たりを数える。apply は封じた hash と今の差分を照らし、置いてよい時だけ置く。check は封じた hash と今の差分を照らすだけで置く`
- `base`（必須）: `text: 差分の根の版（seal と apply は修正前の HEAD、check は鎖の元の基）`
- `fingerprint`: `json(fingerprint.schema.json): 修正の後のテストの緑の認証の指紋 {head, diff_hash}。null は指紋が無い（seal は照らさない。apply は人の答えが無ければ拒む）`。既定 `null`。
- `green_ok`: `flag: 修正の後のテストが通ったか（apply で、人の答えが無い時だけ読む）`。既定 `false`。
- `eyes_ok`: `flag: 修正の後の独立の確かめが通ったか（apply で、人の答えが無い時だけ読む）`。既定 `false`。
- `sealed_hash`: `text: 封じた差分の sha256（apply と check）。空は封じていない`。既定 `""`。
- `answer`: `json(answer.schema.json): 最後の承認ノードで人が返した答え {decision, text}。null は承認ノードが開かなかった（apply だけ）`。既定 `null`。
- `r2`: `json(r2.schema.json): 独立設計との比べ（R2）の {status, reason}。null は省いた・走らなかった（apply だけ）`。既定 `null`。
- `deliver`: `text: 出口の語。空は差分を place に置くだけ、pr は照らした差分を run の枝に積んで PR を作る（apply と check だけ）。ほかの語は ok: false`。既定 `""`。
- `request`: `file: 依頼のファイル（pr の時に、依頼が名指した issue を commit の文に閉じない参照で書く）。空は無い`。既定 `""`。
- `items`: `json(items.schema.json): 差分のパスを修正案の項目に決める記録 {items, claims, unread}（fix の出力。lib/itemcommits.py の merged の形）。null は無い（pr の時に 1 つの commit に倒す）`。既定 `null`。
- `user_env_dir`: `text: 利用者の HOME・XDG に戻して起こした印を置く置き場の絶対パス。空は置き場が無い（戻す run では pr の commit を積まずに止める）。pr の commit の hooks だけが読む`。既定 `""`。起動の殻は Archon を隔離した HOME で起こすが、対象のコマンド（ここでは commit の hooks）だけは利用者の HOME・XDG に戻して走らせ、戻した事の印のファイル `user-env-ran` をこの置き場に置く（`lib/userenv.py`・`tree_run.split_mark`）。報告がその印で「利用者の環境で走らせた」と言う。

出力（`returns: merge`、`outcome_field: ok`）。今の `merge` の 9 欄を字のまま保ち、`report` を足す:

- `mode`: `seal`・`apply`・`check`。
- `ok`: boolean。封じた・置いた・照らして置いたか（`reason` が空か）。
- `hash`: 字。差分の sha256（seal は封じた hash、apply と check は今の差分の hash）。差分が空・誤りの時は空。
- `diff`: pointer（`<place>/sealed.diff`・`apply.diff`・`refused.diff`）か null。拒んだ apply と check は `refused.diff` を指す（人が見られるように）。
- `protected_hits`: 字の配列か null。守りのファイルに当たった行（先頭 `listcut.SHOWN` 行と、超える時は残りの 1 行）。確かめられない時は確かめられない行。check と誤りの時は null。
- `protected_count`: 整数か null。当たった全件の数（確かめられない時は 0）。
- `reason`: 日本語の 1 行。ok でない訳。
- `deliver`: seal は null。apply と check は `{act, pr, reason, commits?, split?}`（`act` は `placed`・`none`・`pr`・`stopped`・`unconfirmed`）。今の `handed.py` の形のまま。
- `optional`: 落ちても線が先へ進めてよい node の宣言（`[{"node": "pr-open", "bare": false}]`）。
- `report`: 報告に載せる日本語の行の配列（9 節）。

今との違い: 今は差分の根を `start`（始めの記録の pointer。seal と apply）か `base_rev`（check）の 2 つの入力から読み分けていた。block は始めの記録を読まないので、3 つの形とも `base` 1 つで受ける。出力の `diff` の `path` は今 `merge/sealed.diff` などの決まった字の enum だったが、place は include の道で決まる（`merge-seal/sealed.diff`・`merge-apply/apply.diff`・`hand/apply.diff` など）ので、末尾の名の形で縛る（1.3）。

### 1.3 node の並び（`blocks/merge/works-factory-merge.yaml`）

1. `place`（script `merge.py`・`mutates_checkout: false`）: `with:` は `mode`・`base`・`fingerprint`・`green_ok`・`eyes_ok`・`sealed_hash`・`answer`・`r2`・`deliver` を `$INPUTS.<名>` で。差分を組んで封じる・照らす・置く（3 節）。返り `{mode, ok, hash, diff, protected_hits, protected_count, reason, base_rev, deliver}`（今のまま。`base_rev` は port `base` の値、`deliver` は確かめた出口の語）。
2. `pr-commit`（script `pr_commit.py`。`depends_on: [place]`・`when: "$place.output.ok == true && $place.output.deliver == 'pr' && $place.output.mode != 'seal'"`・`with: {mode: "$place.output.mode", base_rev: "$place.output.base_rev", sealed_hash: "$place.output.hash", request: $INPUTS.request, user_env_dir: $INPUTS.user_env_dir, items: $INPUTS.items}`）: 今のまま。作業ツリーの HEAD と index を変えるので `mutates_checkout` を書かない（今と同じ。E6 の外への書き込みの 1 つの node ではない。push はしない）。返りは今の `output_format` のまま。
3. `pr-open`（`workflow: archon-pr`。`depends_on: [pr-commit]`・`when: "$pr-commit.output.go == true"`・`with: {branch: "$pr-commit.output.branch"}`）: Archon 同梱の PR を作るグラフを子の run として起こす（10 節の 1）。push と PR の作成はこの子の run の script の node `publish` がする（外への書き込みの 1 つの node。E6）。
4. `pr-read`（script `pr_read.py`・`mutates_checkout: false`。`depends_on: [pr-open]`・`with: {got: "$pr-open.output", head: "$pr-commit.output.head", branch: "$pr-commit.output.branch", base_branch: "$pr-commit.output.base", repo: "$pr-commit.output.repo"}`）: 今のまま。
5. `merge`（script `handed.py`・`mutates_checkout: false`。`depends_on: [place, pr-commit, pr-read]`・`trigger_rule: all_done`・`with: {mode: $INPUTS.mode, place: "$place.output", commit: {from: "$pr-commit.output", if_skipped: null}, read: {from: "$pr-read.output", if_skipped: null}, optional: '[{"node": "pr-open", "bare": false}]'}`）: 渡し方 `deliver` と報告の行 `report` を足して返す（報告の行は `src.report.lines(place, deliver, sealed_diff)`。10 節の 13）。

`output_format` は今の物を写し、2 か所だけ替える: `place` と `merge` の `diff.path` の `enum: [merge/sealed.diff, merge/apply.diff, merge/refused.diff]` を `pattern: "(^|/)(sealed|apply|refused)\\.diff$"` に（place の道は include で決まる）、`merge` に `report: {type: array, items: {type: string}}` を足して `required` に入れる。

YAML の頭の `description:` は今の物から、埋めと他の block の振る舞いの文を外して写す。

### 1.4 place のファイル

`ports.place()`（単独の run では `$ARTIFACTS_DIR/`、line から include された時は `$ARTIFACTS_DIR/merge-seal/` か `$ARTIFACTS_DIR/merge-apply/`、chain からは `$ARTIFACTS_DIR/hand/`。今はどれも `merge/`）の下に書く。名は `src/files.py` だけが持つ:

- `sealed.diff`（seal）・`apply.diff`（置いた apply と check）・`refused.diff`（拒んだ apply と check）。どれも `seal.write_readback` が隣の `*.tmp` に書いて読み戻してから付け替える。
- `protected-all.json`（seal と apply。守りの当たりの全件 `{protected_hits: [...]}`。出力の残りの 1 行がこのファイルを名指す）。

apply と check は始めに前の `apply.diff` を消し、置くと決めた時だけ書く（やり直しが拒んでも古い物が残らない。今のまま）。place の作り直し（中を全部消す）はしない: seal と apply は line の別の include なので place が分かれ、同じ include のやり直しで前の `refused.diff` が残っても、返りの pointer が指すのはその回に書いた物だけ。

### 1.5 コードの置き場と、作る・触るファイル

作るファイル（この block の PR が触るのはこれと `tests/blocks/merge/` と、この設計書だけ）:

- `blocks/merge/works-factory-merge.yaml`
- `blocks/merge/scripts/merge.py`・`pr_commit.py`・`pr_read.py`・`handed.py`（今の 4 本の写し。3 節の違いだけを直す）
- `blocks/merge/src/__init__.py`（空）
- `blocks/merge/src/files.py`: place のファイルの名（1.4）と `PROTECTED_FILE`（今の `merge.py:20` の `merge/protected-all.json` の代わり）。
- `blocks/merge/src/report.py`: 報告の行（9 節）。
形のファイル 4 本は `anyOf` を使わず `type: ["object", "null"]` と `required`・`properties` で書く（10 節の 10）:

- `blocks/merge/schemas/fingerprint.schema.json`: `{"type": ["object", "null"], "required": ["head", "diff_hash"], "properties": {"head": {"type": "string"}, "diff_hash": {"type": "string"}}}`。
- `blocks/merge/schemas/answer.schema.json`: `{"type": ["object", "null"], "required": ["decision"], "properties": {"decision": {"type": "string"}, "text": {"type": "string"}}}`。
- `blocks/merge/schemas/r2.schema.json`: `{"type": ["object", "null"], "required": ["status"], "properties": {"status": {"type": "string"}, "reason": {"type": "string"}}}`。
- `blocks/merge/schemas/items.schema.json`: `{"type": ["object", "null"]}`（中の形は `itemcommits.split` が読み、読めない記録は 1 つの commit に倒す。今のまま）。
- `blocks/merge/fixtures/` の 7 本（11 節）。
- `tests/blocks/merge/__init__.py`・`test_merge.py`（11 節）。

AI の node を持たないので `prompts/` を置かない（README 7.1 の 2 は AI の node の md だけを縛る）。

使う `lib/`（どれも README 9.3 の KEEP）: `seal`（`digest`・`write_readback`・`diff_files`・`seal_refusal`・`apply_refusal`・`hash_refusal`・`unknown_row`・`deleted_paths`・`deleted_lines`・`UNKNOWN_HEAD`・`REDESIGN`）・`protect`（`merged`・`hits`・`lines`・`shown`・`Broken`）・`green_cert`（`diff_bytes`・`diff_between`・`matches`）・`entry`（`deliver_word`・`DELIVERS`。`entry` は README 9.3 で line・chain・merge が使う KEEP）・`entryshape`（`named`）・`forge`（`repo_of`）・`itemcommits`（`split`）・`runbranch`（`pr_branches`・`staged`・`commit_parts`・`commit`・`git`・`ORIGIN`・`GitFailed`・`PartFailed`）・`tree_run`（`outside_env`・`split_mark`・`place_mark`）・`oneline`・`listcut`。

使う土台の `ports.py` の口（どれも今の土台に在る。この PR は `ports.py` を触らない。10 節の 9）: `text`・`flag`・`choice`・`json`・`file`・`parsed`・`picked`・`place`・`pointer`・`run`・`drop_runner_env`・`RUNTIME_COPY`・`RUNTIME_COPY_PREFIX`。今の `boundary.py` の口のうち土台に無い物（`resolve`・`value`・`items`・`as_items`・`as_text`・`guarded_imports`・`SKIP`）は足さず、block の中で組む（`resolve` の代わりに `ports.place()` と `src/files.py` の名、`SKIP` の代わりに `(ports.RUNTIME_COPY_PREFIX,)`、ほかは各 script の数行の関数と script の頭の import の受け）。

作り直しの間は `workflows/merge/` と、使う lib を変えない。

### 1.6 つなぎ方（graph の側。block には書かない）

- line（今と同じ 2 か所）:
  - `merge-seal`（`mode: seal`）: 独立の目の後。`with:` は `base` ← 始めの記録の `base_rev`（修正前の HEAD）・`fingerprint` ← `$test-gate-final.output.fingerprint`・`green_ok` ← `$test-gate-final.output.ok`・`eyes_ok` ← eyes のまとめの `ok`。`when:` は「直した差分が在る」（今の `$fixed.output.no_fix == false`）。
  - `merge-apply`（`mode: apply`）: 最後の承認ノードの答えの後。`with:` は seal と同じ物に `sealed_hash` ← `$merge-seal.output.hash`・`answer` ← 最後の答え・`r2` ← eyes のまとめの `r2`・`deliver` ← line の入力 `deliver`・`request` ← 依頼のファイル・`user_env_dir` ← 始めの記録・`items` ← fix の出力の項目の記録（今の `$fixed.output.item_claims`）。
- chain の `hand`（`mode: check`）: 出口の語 pr の時だけ。`with:` は `base` ← 鎖の元の基・`sealed_hash` ← 最後の差分の封じた hash・`deliver`・`request`・`user_env_dir`（今と同じ）。
- 守りの当たりの読み手: line の最後の承認ノード（`protected_hits`・`protected_count`。当たりか確かめられない行が在れば、開き方に関わらず必ず開き、冒頭 3 行で名指し、3 行の直後の最初の節に並べる。`gatepolicy.opens` の `guarded`）・`bin/apply`（封じた差分と R2 の作り直しを照らして当てる。--allow-failed の時は line の受け皿の node `merge-seal-out` の出力を run の記録から読む）・report（`report` と、人が決めることの数えに `protected_hits`・`protected_count`）。
- README 13 節の移し: 今は独立の目（eyes）も同じ当たりを数え（`workflows/eyes/scripts/protected.py`）、eyes の `ok` が「守りのパスを確かめられたか」を含み（`lib/eyeverdict.py:531-553`）、報告が seal の当たりが無い時に eyes の当たりを読んでいた（`runreport._hits`、`lib/runreport.py:1049-1060`）。最後の承認ノードと `merge` の apply が読んでいたのは、もとから seal の当たりだけ（`ask_final.py` の `SEAL`・`seal.apply_refusal` の `protected`）。新しい形では当たりを数えるのはこの block の seal と apply だけで、eyes のまとめは当たりを数えない（eyes の設計書の側の直し）。確かめられない時は、この block の確かめられない行が承認ノードを開き、apply を拒む（今の eyes の `ok` が偽になるのと同じ所に倒れる）。

## 2 AI の node

持たない。PR の題と本文を決める AI の node は `archon-pr` の子の run の中に在り（同梱のグラフの `prepare`。書き込みをしない）、この block の外の物。この block は子の run に枝だけを渡し、題と本文の材料は積んだ commit の文で渡す（`with:` と `input:` を一緒に書けないため。今の `works-factory-merge.yaml:128-131` のコメントの訳）。

## 3 script の node

どの script も今の写しで、違いは下に書いた所だけ。入力は `os.environ.get("INPUTS_<名>")` の字のままで読み、`ports` の口に渡す。どれも落ちない（誤りは終了の値 0 で `ok: false`・`go: false` と訳）。

### 3.1 `merge.py`（node `place`）

今の `workflows/merge/scripts/merge.py`（117 行）の写し。順:

1. `mode` が `seal`・`apply`・`check` のどれでもなければ `ValueError`（全体の `except` が `broken(mode_of(…), "<型>: <文>")` を返す）。
2. apply と check は、前の `apply.diff`（`ports.place() / files.APPLIED`。10 節の 9）を消す。
3. `deliver` を `entry.deliver_word` で確かめる（外の語は `InputRefused` → 全体の `except`）。
4. 差分の根は port `base`（違い: 今は seal と apply が始めの記録の `base_rev`、check が入力 `base_rev`）。空なら `ValueError("差分の根 base が無い: ''")`。
5. 差分のバイト `green_cert.diff_bytes(repo, base, skip=(ports.RUNTIME_COPY_PREFIX,))`（Archon が作業ツリーに置く工程の写し `.archon/` を載せない）。空なら `broken(mode, "差分が空（<base> から今の作業ツリーまで変わった物が無い）")`。
6. check: `seal.hash_refusal(sealed_hash, seal.digest(data))` が空なら `apply.diff`、でなければ `refused.diff` に書いて、その pointer と訳を返す（守りの当たりは数えない。null）。
7. seal と apply: 守りの当たり。`seal.diff_files(repo, data)` の行数を付けた `protect.hits(stats, protect.merged(repo, base))` を `protect.lines` にする。`protect.Broken` か `ValueError` なら `[seal.unknown_row(<訳>)]` と数 0（確かめられない行を当たりとして数える）。
8. seal: `seal.seal_refusal(fingerprint=…, fingerprint_ok=green_cert.matches(fingerprint, repo))`。`sealed.diff` に書く（拒んでも書く。人が最後の承認ノードで見る）。全件を `protected-all.json` に書き、出力の当たりは `protect.shown(protected, "protected_hits", <protected-all.json の絶対パス>)`、数は全件の数。
9. apply: `seal.apply_refusal(sealed_hash=…, current_hash=seal.digest(data), answer=…, green_ok=…, eyes_ok=…, r2=…, fingerprint_ok=green_cert.matches(fingerprint, repo), protected=<全件>)`。空なら `apply.diff`、でなければ `refused.diff` に書く。返りの当たりは今と同じく全件（apply の当たりは承認ノードが読まない。今の挙動のまま）。
10. 返り `{mode, ok: not reason, hash, diff, protected_hits, protected_count, reason, base_rev: base, deliver}`。

`fingerprint`・`answer`・`r2` は空と `null` を無しに読み、JSON として読めない字は `ValueError`（`ok: false`）。形のファイルに合わない値は、`fingerprint` は「指紋が合わない」、`answer` は「通さない答え」として拒む側に倒し、落とさない（差分のファイル・hash・守りの当たりは書く。今の挙動と同じ所に倒れる）。`r2` の形の違いは `ValueError`（10 節の 11）。`green_ok`・`eyes_ok` は flag の form で読み、真偽でない値は偽（今の `boundary.parsed` の読みと同じく `fact is not True` で拒む側に倒れる）。

### 3.2 `pr_commit.py`（node `pr-commit`）

今の `workflows/merge/scripts/pr_commit.py`（190 行）の写し。違いは `boundary` を `ports` に替えるだけ（`boundary.RUNTIME_COPY`・`boundary.SKIP`・`boundary.drop_runner_env`・`boundary.text`・`boundary.value`・`boundary.run`・`boundary.guarded_imports`）。順は今のまま: 形が apply か check・根が在る → 本体の作業ツリーか切り離された HEAD でない・run の枝の名が対象の既定の枝と違う（`runbranch.pr_branches`）→ origin の URL から PR を出す repo を決める（`forge.repo_of`）→ 今の差分の hash が封じた hash と同じ → 依頼が名指した issue の番号を引く（`entryshape.named`。最後の commit の文に `Refs #<n>` で書く。引けなくても止めない）→ Archon の変数を落とす → 対象のコマンドの環境（`tree_run.outside_env`）と印の置き場で hooks を走らせて積む（項目ごとの commit、決められなければ 1 つ。項目のどれかで hooks が落ちれば 1 つに積み直す）→ 積んだ最後の commit までの差分の hash を封じた hash と照らす。push と PR の作成はしない。

### 3.3 `pr_read.py`（node `pr-read`）

今の `workflows/merge/scripts/pr_read.py`（80 行）の写し。違いは `boundary` を `ports` に替えるだけ。作ったと言うのは、記録の PR が開いていて、repo と head の repo が origin の repo（大文字と小文字は区別しない）、head の枝が積んだ枝、base の枝が既定の枝、head の版が積んだ commit と同じ時だけ。

### 3.4 `handed.py`（node `merge`）

今の `workflows/merge/scripts/handed.py`（95 行）の写しに、報告の行を足す。違い:

- 返りに `report: src.report.lines(place, deliver, sealed_diff)` を足す（9 節。引数は 10 節の 13）。`place` の返りが読めない時は `report: ["差分の確定（<mode>）: 照らしのノードの出力が無い"]`。
- `boundary` を `ports` に替える。

`deliver` の組み方は今のまま: seal は null。出口の語が空なら `placed`（ok）か `none`。pr なら、置かなかった・commit の node の出力が無い・進めなかった → `stopped`（push も PR の作成もしていない）、子の run が落ちたか返らなかった・読み戻しが合わない → `unconfirmed`（push と PR の作成は済んでいるかもしれないので、作ったとも作らなかったとも言わない）、合った → `pr`。`pr` と `unconfirmed` は積んだ項目の commit の並び `commits` と 1 つに倒した訳 `split` も載せる。

## 4 受け付け

AI の返答を受けないので、却下と諦めの loop は無い。置いてよいかの決まりは 3.1 の 9（`seal.apply_refusal`。上から順に見て最初の理由で拒む）:

1. 封じた hash が空（seal が走っていない）。
2. 今の差分の hash が封じた hash と違う。
3. 答えが在り、通す語（`answer.GO_WORDS`）のどれでもない（止め札もここ）。
4. R2 が `redesign-needed`（人の通しの答えでも拒む。部分を取り込まない）。
5. 答えが無い（承認ノードが開かなかった）のに、緑でない・目が通していない・指紋が今の木と違う・守りのファイルに当たった・守りのファイルを確かめられない、のどれか。守りのファイルは人の通しの答えだけが通す。

答えが通す語なら、赤でも、独立の目が R2 の作り直しの外の判定（`fix-needed` など）で通さなかった時でも置く（人が決めた）。

## 5 単独で呼ぶ

```sh
bin/works-factory <読ませるフォルダを blocks/ にする引数（名は実装で決める）> workflow run works-factory-merge \
  --cwd <対象> --input mode=seal --input base=<差分の根の commit>
```

置く時は `--input mode=apply --input base=<同じ根> --input sealed_hash=<seal の出力の hash> --input answer='{"decision":"approve","text":""}'`。照らすだけは `mode=check`。出力は `workflow get <run>` の `merge` の返り。始めの記録は要らない。殻の引数の名は（未確認）（world の 7 節と同じ）。

## 6 元の works と graphloops の同じ場面

元の works は差分を封じず、`dev/use.sh:401-433` が差分を組み直して `git apply --check` で当てた（消すファイル・止まった run・当たらない差分を拒む）。守りのファイルの確かめは `.shared/core/protect.py` と line の境（`line_edge.py:640-647`）。graphloops には封じる・置く・渡す段が無い（`p4.final_gates` は変異の確かめの段で、`engine/role_run.py:155` の `protected_paths` は git のフォルダへの書き込みを sandbox で塞ぐ物）。

同じ物（工場がそのまま持つ）: 守りの一覧を作業ツリーでなく走っている pack から読む（元の works の `protect.py:8`、工場の `lib/protect.py:8,45`）・守りのファイルに当たれば最後の承認ノードを開く・当てるのは人。

工場に無い物・違う物と、その訳:

1. 計画が許したテストの書き換えを、守りのファイルと同じ確かめに通す（元の works は許したテストの一覧を 2 つ目の守りの一覧として同じ確かめに入れ、承認ノードを必ず開いた。`line_edge.py:643-645`）: 工場は別の節にして、今も最後の承認ノードを必ず開く（`ask_final.py:66,170`。#264 `86c3f28c`・`b0708f49`）。ただし apply の拒みの決まり（`seal.apply_refusal`）には許したテストの入力が無い。計画の M30（`docs/plans/2026-10-13-line-wiring.md:336,341`）は「答えが無ければ置かない」と書き、graph の上では承認ノードが必ず開き無人の run は止まるので、答えの無い apply には届かない。apply で拒まないと決めた記録は無い（（未確認））。この block も今のまま足さない（足すのは振る舞いの変更で、作り直しの外）。
2. 守りの一覧が壊れている時: 元の works は誤りの文と空の当たりを返した（`line_edge.py:640-647`）。工場は確かめられない行を当たりとして数える（#66 `73971978`）。この block も同じ。
3. 当てる道の旗: 元の works は止まった run を環境変数 `WORKS_USE_ALLOW_STOPPED=1` で通した（`use.sh:405-428`）。工場は `bin/apply` の 1 回ごとの旗 `--allow-stopped`（#114 `39354afc`・`afbc62b4`）。この block の外（`bin/`）。
4. 出口の語 pr（元の works と graphloops に無い）: 工場が足した（#729 `4d885316`・`e810ce72`、項目ごとの commit は #569 `b2d1e58d`、hooks を利用者の環境で走らせるのは #759 `9fa376ba`）。push と PR の作成は同梱の `archon-pr` に任せる（持ち主の決め `deliver-via-archon-pr`、`docs/owner-decisions.md:381-392`、issue #555）。自前の push と PR の道（gh の探し方の写し・gh の旗の自前の読み・push の hooks を飛ばす）は、持ち主の決め `no-tool-quirks` と `concept-home` に反するとして採らなかった。
5. 入力 `diff`: 工場は意図して外した（#266 `3adce5e5`「merge の読まない入力 diff をやめ」）。`merge.py` は入力の差分を読まず、作業ツリーと根から組み直して指紋と照らすので、使われない入力が層の柵の許しの行で隠れていた。この block も持たない（10 節の 2）。

この block が両方より良く、残す物: 封じた hash を書いて読み戻し、apply・pr の積む前・積んだ後・`bin/apply` の 4 か所で照らす（#66。人が承認した差分と出ていく差分が同じことが確かめられる）・緑の認証の指紋を seal と apply で照らし直す（試験の後に変わった木を緑として出さない）・R2 の作り直しは人の通しの答えでも部分を取り込まない・守りの一覧と宣言が壊れていても確かめられない行で拒む側に倒れる・対象のリポジトリが自分の守りのファイルを宣言でき、差分の根の版の物を読む（修正が宣言を緩めても効かない。#178 `2e392b7a`）・当たりの行を出力では短く切り、全件を place に残す・落ちない（拒んだやり直しに古い `apply.diff` を残さない）・照らすだけの形 check（鎖）・PR は既定の枝の名を拒み、作った PR を枝・版・向け先まで読み戻し、確かめられなければ「確かめられなかった」と言う。

## 7 組み込みの時に block の外で直す所（この block の PR では触らない）

- `bin/_lib/apply.py:41` の `APPLY_DIFF, SEALED_DIFF = "merge/apply.diff", "merge/sealed.diff"` と、それを `output_format` の enum と縛る試験（`tests/bin/`）: 出力の `diff.path` は enum でなく末尾の名の形になる（1.3）。`bin/apply` は pointer の先を読むので、字を名の末尾（`apply.diff`・`sealed.diff`）の照らしに替える。
- `lib/protected.json` の行のうち、作り直しで消える・移るパス（`final-gate` の `workflows/.shared/boundary.py`・`edge-test` の `tests/shared/test_boundary.py`・`layers-test` の `tests/layers/*.py`・`yaml-rules-data` の `tests/layers/seeds/**`）: 一覧は「行を足す・消すのは人だけ」（`protected.json` の `about`）なので、組み込みの PR で行の直しを人に諮る。`lib/tests/test_protect.py` はどの行も追跡のファイルに当たるかを見るので、直さなければ赤になる。守りの関門の新しい住処（この block の `scripts/merge.py`・line の最後の承認ノードの `src/`・`ports.py`）を一覧に足すかも、人の決め。
- line の `ask_final` と report の `_hits` から、eyes の当たりへの落ち（`runreport.py:1056` の `rows or …eyes…`）を外す（1.6）。

## 8 守る keep-essence と封じた差分

- 10（守りのファイルに触れたら最後の承認ノードを開く）: 当たりを数えるのはこの block（README 13 節）。開くのは line の最後の承認ノード、拒むのはこの block の apply（答えが無ければ）と `bin/apply`。守りの試験（`tests/blocks/merge/` に作り直す）: `SealTest` の `test_protected_hit_is_named`・`test_many_protected_hits_keep_the_return_short`・`test_index_marks_do_not_hide_a_protected_hit`・`test_broken_manifest_is_an_unknown_hit_and_blocks_apply_without_answer`・`test_uncountable_diff_is_an_unknown_hit`、`ApplyTest` の `test_no_answer_and_protected_hit_refuses`・`test_apply_refuses_target_protected_hit_without_answer`。KEEP の `lib/tests/test_protect.py`。読み手の側の筋書き `workflows/line/fixtures/eyes-failed-protected.stubs.yaml` は新しい line へ（line の設計書）。通しの試験の小さな対象（`tests/e2e/target-seed/`）は守りのファイルに触れない作りなので、この仕組みは本物の run ではまだ一度も通っていない（README 10 節の 10。種に守りの宣言 `.works-protected.json` と、それに当たる依頼を足せば通る。e2e の筋書きの直しで、この block の外）。
- 封じた差分（keep-essence の 12 の番号の外。10 と 1 を支える土台）: 人が最後の承認ノードで見た差分と、置く・積む・当てる差分が同じであることを hash で縛る。緑の認証（test-gate の `fingerprint`）が今の木と合わなければ封じても ok にせず、答えの無い apply は拒む（試験が通った木と出ていく木が同じ）。守りの試験: `SealTest.test_seal_hashes_the_written_diff`・`test_changed_fingerprint_refuses_but_writes`・`test_sealed_diff_has_no_runtime_folder`・`test_empty_diff_is_null`、`ApplyTest.test_same_tree_applies_the_sealed_diff`・`test_tree_changed_after_seal_refuses`・`test_refused_retry_removes_the_earlier_apply`・`test_stop_answer_refuses`・`test_no_answer_and_red_refuses`・`test_no_answer_and_clean_run_applies_only_when_every_check_passed`・`test_unverifiable_r2_with_approve_applies`・`test_redesign_r2_with_continue_refuses`、`CheckTest` の 3 本、`PrCommitTest.test_stacked_tree_is_checked_against_the_sealed_hash_as_a_whole`・`test_other_diff_is_not_committed`。KEEP の `lib/tests/test_seal.py`・`lib/tests/test_green_cert.py`・`tests/bin/test_apply.py`。
- 1（赤緑の機械の判定）と 2（元から赤の区別）の読み手: apply は答えが無い時に test-gate の `ok`（機械が認証した緑）を読み、緑でなければ置かない。
- e2e の `tests/e2e/evidence.json` の M1・M3・M7・M16・M17 は、place のパス（`parent/merge/sealed.diff` → `parent/merge-seal/sealed.diff`、`parent/merge/apply.diff` → `parent/merge-apply/apply.diff`）を新しい物に合わせる。

## 9 報告の行（`src/report.py`）

今の `lib/runreport.py` が merge の返りから組む行のうち、この block の事実だけで決まる物を同じ字で組む（node の id の札は形の語に替える。block は line の中の名を知らない）。

- どの形でも、`ok` でない時に 1 行: `差分の<封じ・置き・照らし>（<mode>）が ok でない: <reason>`（今の `_stop_lines` の `<node> が ok でない: <reason>`）。
- seal: `sealed.diff` が消すファイルの行（今の `_tests_head_lines` の `seal.deleted_lines(seal.deleted_paths(<封じた差分の字>), where=<sealed.diff の絶対パス>)`。読めなければ `取り込むと消えるファイル: 封じた差分が読めない（<訳>）`）。
- apply と check:
  - `deliver.act` が `pr`: `PR を作った: <url>（<下書きの PR か PR> #<number>。merge は対象のレビューと決まりに任せる）`（今の `apply_said` の頭。`runreport.PR_MADE`）。
  - `stopped`: `PR を作らずに止めた: <reason>`（`PR_STOPPED`）。`unconfirmed`: `PR を作ったと確かめられなかった: <reason>`（`PR_UNCONFIRMED`）。
  - 積んだ commit の行（今の `_pr_commit_lines` の写し。`PR の commit: 修正案の項目ごとに <n> 本（…）` と項目ごとの `項目 <item>: <head の頭 12 字>（<subject>）`、1 つに倒した時は `PR の commit: 項目ごとに分けなかった（<split>）`）。
- 守りの当たりの行は `report` に入れない。当たりは「人が決めること」の件数の 1 つで、ほかの block の件数と合わせて数えるので、report が `protected_hits`・`protected_count` の欄から組む（今の `_hits` と同じ字の `守りのパスに当たった差分: <count> 件`）。
- `bin/apply` の打ち方の行（`差分を対象に当てる: bin/apply <run> …`）も入れない。結末の語と最後の承認ノードの答えで変わる行で、report と line の事実で決まる。

## 10 自分で決めた事

1. PR の作成を、Archon 同梱の `archon-pr` を `workflow:` で子の run として起こす今の形のまま block の中に置く。根拠: 持ち主の決め `deliver-via-archon-pr`（`docs/owner-decisions.md:381-392`）と、根の `AGENTS.md` の E8 の外し（「外しは 1 つだけ: 出口の語 pr の時に merge が `workflow:` で起こす `archon-pr`」）。README 7.1 の 6 は「block の `workflow:` は自分の YAML の名だけ」と書くので、この 1 つの外しを形の検査に足す要がある（README の直し）。外しを line に移す形（merge が枝を返し、line が `archon-pr` を起こし、もう 1 度 merge が読み戻す）は、積む・作る・読み戻すの 1 つの流れが 2 つの block と graph に割れ、`handed.py` の `unconfirmed` の判じ（子の run が落ちたか）が block をまたぐ。
2. 入力 `diff` を持たない（README の 8.4 は `diff file` を書く）。根拠: #266 `3adce5e5` が意図して外した（読まない入力。差分は作業ツリーと根から組み直し、指紋と照らす）。README 1.3 の変更の歩かせ（代表の commit を新しい形の上で紙で辿った検討）の 4 項が、この commit を歩かせている。README の 8.4 の直し。
3. 形を `seal`・`apply`・`check` の 3 つにする（README の 8.4 は `seal|apply`）。根拠: chain の `hand` が `check` を使う（`workflows/chain/works-factory-chain.yaml:384-395`）。消すと鎖の PR の道が落ちる。
4. 出力の欄の名を今のまま（`hash`・`diff`・`protected_hits`・`protected_count`・`deliver`）にする（README の 8.4 は `sealed`・`protected_hits`・`pr` と書く）。根拠: line の最後の承認ノード（`ask_final.py` の `SEAL`）・`bin/apply`（--allow-failed で run の記録から読む欄）・chain・報告が今の名で読む。README の名は中身の言い方で、名を替えると読み手の全部と `bin/` が動く。
5. 差分の根を 3 つの形とも port `base` 1 つで受け、必須にする。根拠: README 4.2（始めの記録を読まない）。今は seal と apply が始めの記録から、check が入力から読み分けていたが、どれも同じ意味（差分の根）。根の無い run は今も `ok: false` なので、必須にして読み込みの時に名指す。
6. （9 で替えた）土台の `ports.py` に要る口を 1.5 に並べ、無い物は最初に要った block の PR が足す。根拠: 今の `boundary.py` の口で、test-gate・fix も使う（憲法の 4）。README 3 節は `ports.py` を `boundary.py` の後継と書くが、口の一覧を決めていない。
7. 出力の `diff.path` を enum から末尾の名の形に替える。根拠: README 4.4（place は include の道で決まる）で、line の 2 つの include と chain の 1 つで place の字が違う。名の住処は block の `src/files.py` だけ（README 4.4）。
8. 守りの当たりの行と `bin/apply` の打ち方の行を `report` に入れず、欄で返す。根拠: README 4.1 は報告の文を事実を持つ block が組むと決めたが、この 2 つは他の block の事実（ほかの人が決めることの件数・結末の語・最後の答え）と合わせて初めて決まる。事実を欄で返し、組むのは report と line にする。
9. 土台の `ports.py` を直さず、1.5 の口のうち無い物は block の中で組む。根拠: 土台は別の PR の持ち物で、この PR が触るのは `blocks/merge/` と `tests/blocks/merge/` と設計書だけ（作り直しの間は既存の共通の口を変えない）。`resolve` は要らない（place の下のファイルは `ports.place()` と `src/files.py` の名で直に指す）。`value`・`items`・`as_items`・`as_text` は各 script の 2〜3 行の関数（`parsed` の読みと型の倒し方）に、`SKIP` は `(ports.RUNTIME_COPY_PREFIX,)` に、`guarded_imports` は script の頭の `try: import …` と `ports.run` の fallback に替えた。10 節の 6 の「最初に要った PR が足す」は、足す先が土台の PR になるので、足さずに済む形にした。本文は 1.5 の使う口の段と 3.1 の 2。
10. 形のファイル 4 本は、`anyOf` でなく `type: [object, "null"]`（と `required`・`properties`）で書く。根拠: `blocks/.shared/AGENTS.md` と `ports.unknown_keywords` が `anyOf` を拒む（`KNOWN_KEYWORDS` に無く、照らしが黙って飛ばす）。`required` は値が object の時だけ効くので、null は通り、object は `decision`・`status`・`head`・`diff_hash` を要る。本文は 1.5 の形のファイルの段。
11. 入力 `green_ok`・`eyes_ok` は `ports.flag` で読み、`true`/`false` でない値（空・`null` など）は偽に倒す（拒む側）。根拠: 1.2 の「真偽でない値は偽」。`ports.flag` は不正な字で落ちるので、script が `ValueError` を偽に替える。`fingerprint`・`answer`・`r2` は空と `null` を無し（`None`）に、それ以外は `ports.json` で読む。JSON として読めない字は `ok: false`。形の照らしに落ちた `fingerprint` は合わない指紋、`answer` は通さない答えとして拒み、差分と守りの当たりは書く（今の挙動の「拒むが書く」のまま）。`r2` の形の違いは `ok: false`。本文は 3.1。
12. 入力 `request`（form `file`）は `ports.file` で読み、読めない・無いファイルは空に倒す（依頼が名指した issue を引けなくても止めない。今の `entryshape.named` の挙動のまま）。`items` は `ports.json` で形を照らし、JSON として読めない字は字のまま `itemcommits.split` に渡して 1 つの commit に倒す（今の `boundary.value` のまま）。
13. `report.lines` の引数は `(place, deliver, sealed_diff)`（前の版の設計の `(place, commit, read, deliver)` から替えた）。根拠: 積んだ commit の並びと訳は `deliver` が `commits`・`split` で既に持つので、commit と read の返りを渡し直す要が無い。seal の消すファイルの行は封じた差分を読むので、実のパス（`ports.place()` の `sealed.diff`）を受ける。node `merge` の place は seal の node と同じ include の道なので同じ場所を指す。本文は 1.3 の 5 と 3.4。
14. この block は AI の node を持たないので、プロンプトの md も指示の比べの試験も無い。作業は 1 つの commit にまとめた（#764 の 2 つの commit の形は AI の md の写しと翻訳のための物）。`pr_commit.py` の commit の文など、人に見せる日本語の字は今のまま日本語で残す（AI に届く指示ではなく、PR の本文の材料と報告の行）。
15. 標準の筋書きは今の `seal.stubs.yaml` を `standalone.stubs.yaml` に改めた物（6 本はそのまま）。入力は `base` を 40 字の版で。`place` と `pr-commit` と `pr-open` は stub で差し替え、`pr-read` と `merge` は本物の script が走る。

## 11 試験

- standalone の fixture（`blocks/merge/fixtures/`。今の 7 本の入力の `start` を `base` に替える。script の node も差し替え、配線を見る）:
  - `standalone.stubs.yaml`（今の `seal.stubs.yaml`）: 入力は `mode: seal`・`base: <40 字の版>`。`reached: [place, merge]`（PR の node は走らない）。
  - `apply.stubs.yaml`・`apply-refused.stubs.yaml`・`empty-diff.stubs.yaml`: 置く・拒む・差分が空。
  - `pr.stubs.yaml`・`pr-same-branch.stubs.yaml`・`pr-child-failed.stubs.yaml`: PR を作る・既定の枝の名で止める・子の run が落ちて `unconfirmed`。
  - 差し替えの `diff.path` は `sealed.diff`・`apply.diff`（単独の run の place は run directory の根）。
- `tests/blocks/merge/test_merge.py`（script を子のプロセスで回す。始めの記録の無い使い捨ての `ARTIFACTS_DIR` と git のリポジトリで、port の値だけを渡す。今の `tests/workflows/test_merge.py` から写す）:
  - `ShapeTest`: `test_header`・`test_nodes_are_place_the_pr_path_and_the_return`・`test_pr_path_runs_only_after_the_check_for_the_word_pr`・`test_inputs_are_the_contract`（入力の鍵が 1.2 の 12 個で、`mode` と `base` が必須）・`test_output_format_is_the_contract`（`report` を足し、`diff.path` は pattern）。足す: `workflow:` が `archon-pr` だけ（10 節の 1）。
  - `SealTest`・`ApplyTest`・`CheckTest`・`PrCommitTest`・`PrReadTest`・`HandedTest` の全部。始めの記録の `base_rev` を port `base` に替える。
  - `NeverFailsTest`: `test_unknown_mode`・`test_empty_mode`・`test_unknown_deliver_word`・`test_answer_not_json`・`test_r2_not_json`・`test_lib_missing`・`test_checkout_not_git`。始めの記録の 3 本（`test_start_not_json`・`test_start_of_another_run`・`test_start_record_without_base_rev`）は、`test_empty_base_is_not_ok`（`base` が空なら `ok: false` と「差分の根 base が無い」）の 1 本に替える。
  - 足す: `report` の行（seal の消すファイル・ok でない・PR を作った・止めた・確かめられなかった・積んだ commit）。守りの当たりと `bin/apply` の行が `report` に無い（10 節の 8）。
  - `FixturesTest`: block の fixture の照らし（README 7.1 の 4 と 11.2）に替わる。
- 指示の比べ（README 11.4）: AI の node を持たないので無い。
- keep-essence と封じた差分の守りの試験は 8 節。

## 12 未確認

- 起動の殻で `blocks/` を読ませる引数の名と、5 節の命令の正確な形。
- `archon workflow test` が `workflow: archon-pr` の node を `blocks/` の pack だけを読ませた時にも差し替えで通すか（今の筋書き `pr.stubs.yaml` は `workflows/` の pack で通っている）。
- 計画が許したテストの書き換えを apply で拒まない今の形を、意図して決めた記録（6 節の 1）。
