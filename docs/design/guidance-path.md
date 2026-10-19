# block の設計書: guidance-path（案内の道の目）

- 何の話か: README の 8.6 の「入る前」の目。文脈を持たない AI に典型の変更の頼みだけを渡し、リポジトリの入口から案内（AGENTS.md・設計書）と手本だけを頼りに辿らせ、変更を置く所と写す手本を記録する。置いた所が、その頼みが閉じるべき所（README の 1 節）の外なら、案内の直しを出す。型は [README.md](README.md)、手本は [world.md](world.md)。
- 決めたこと: 読み手（guidance-walk）は頼みごとに新しい会話で起こし、閉じるべき所を見せない。比べは機械（compare）。外れた頼みだけを、別の役（guidance-fix）に、読み手が辿った道と閉じるべき所を見せて、案内の直しを 3 種（案内を足す・手本を替える・置き場で塞ぐ）で出させる。手本は convergence-loops の firstread-loop（用事だけを渡された読み役が入口から自分で探す）。
- 持ち主に求めること: なし。

## 1 block の全体

### 1.1 port

入力:

- `requests`（必須）: `json(requests.schema.json): 頼みの一覧 [{id, request, closes}]`。値そのものか pointer で渡す（パスでは受けない。閉じるべき所を読み手の作業ツリーに置かない）。`request` は読み手に渡す頼みの文、`closes` は閉じるべき所（作業ツリーの根からのファイルかフォルダのパス。置いた所が全部どれかの中なら当たり。訳ありの 2 か所はパスを 2 つ書く）。新しい block を足す頼みは `blocks/{new}/`・`tests/blocks/{new_}/`・`docs/design/{new}.md` と書く: 置いた所の全部が同じ 1 つの名に結ばれ（`{new_}` はその名の `-` を `_` にした物）、その所が作業ツリーにまだ無い時だけ当たる。
- `entry`: `text: 入口のファイル（空白区切り）。空は README.md と AGENTS.md`。既定 `""`。
- `lang`: `text`。人に見せる欄（why・change・stuck・guessed）の言語。既定 `""`。

出力（`returns: finish`、`outcome_field: ok`）: `ok`（全部の頼みを辿れて、外れには直しが通ったか）・`status`・`reason`・`paths`（pointer。頼みごとの辿った道・置いた所・写した物・詰まり・推測・当たりか）・`fixes`（`[{request, kind, where, change, why}]`。`kind` は `guide`・`model`・`block`）・`hits`・`misses`・`report`（日本語の行）。

### 1.2 node の並び（`blocks/guidance-path/works-factory-guidance-path.yaml`）

1. `intake`（script）: port を読み、頼みの id の重なり・入口のファイルの在る無し・入口が見せない所の中でないかを照らして `intake.json` を書く。消すのは、この block が名を持つファイルだけ（頼みの id ごとの却下の控えは名を組んで消す）。落ちない。
2. `walk-loop`（`loop_group`・`fresh_context: true`・`max_iterations: 60`）: 1 周が頼み 1 つの 1 回。`walk-prep` がまだ辿っていない頭の頼みの指示を組み、`guidance-walk`（AI。`Read`・`Glob`・`Grep`・`@wf-report`。`denied_tools` の `Read(./<所>)` で、この目の block・試験・設計書と `.archon/` を読めない。並びは `src/steps.py` の `HIDDEN`）が辿り、`walk-accept` が受け付ける。頼みごとに 3 回拒めば諦めて次へ（`rolekit` の控え `rejects-walk-<id>.json`）。`done` は全部の頼みが済んだか。`max_iterations` は Archon が輪に求める上限で、頼みの数 × 3 回が収まる大きさ（尽きれば出口が辿れなかった頼みを名指す）。
3. `compare`（script）: 置いた所を `closes` と比べ、`compare.json` を書く。
4. `fix-loop`（`when: $compare.output.due`。3 回）: `fix-prep`・`guidance-fix`（AI。`Read`・`Glob`・`Grep`・`@wf-judge-core`）・`fix-accept`。
5. `finish`（script。`trigger_rule: all_done`）: `paths.json` を書き、返りを組む。落ちない。

place のファイルの名は `src/steps.py` だけが持つ（`intake.json`・`walks.json`・`compare.json`・`fixes.json`・`paths.json`・却下の控え・`guidance-*-prompt-<n>.md`）。

## 2 node の設計シート: guidance-walk（読み手）

1. 役: 初めてこのリポジトリに来た人として、頼み 1 つを、入口から案内と手本だけで辿り、変更を置く所と写す手本を返す。変更はしない。
2. port: `requests` の 1 行の `request` だけ（`closes` は渡さない）・`entry`・`lang`・前の回の却下（place の控え）。
3. 組み立ての順（`prompts/guidance-walk.md`）: `{shared:rejected}`（条件 `rejected`）・役の定義と決まりの箇条（決まった文）・`## The request` と `{request}`・`## Entry files` と `{entry}`（箇条の行）・`## How to answer`（決まった文と `{lang}`）・結びの 1 文。
4. 返す形: `steps [{file, why}]`・`placed [{path, change}]`・`copied [{path, why}]`・`stuck [字]`・`guessed [字]`。人に見せる欄は why・change・stuck・guessed（`{lang}`）。
5. 描いた骨組み: 初めての本物の run は fb59418a（頼み 7 件。当たり 1・外れ 6・案内の直し 15 件。直しの当て方は README の 13 章）。
6. 今の指示との差: 新しい役（今の工場に無い）。
7. 元の works と graphloops の同じ場面: convergence-loops の firstread-loop の読み役（`~/src/claude-plugins/convergence-loops/`）。違い: 読み手に「止まった所・推測した所」に加えて「置く所・写す手本」を答えさせ、機械が閉じるべき所と比べる。firstread-loop の「読んだ後の誤解」の聞き取りは持たない（この目が見るのは置き場の誤りだけ）。
8. 受け付け: `steps` の各ファイルが作業ツリーに在り、見せない所の中でない・パスが根からの相対で `..` を持たない・`placed` と `steps` が空でない。3 回で諦め、`walks.json` にその頼みの諦めた理由を残す。
9. 試験: `fixtures/standalone.stubs.yaml`（頼み 1 つを外して直しまで）・`tests/blocks/guidance_path/`（当たりと外れ・受け付け・入口の誤り・比べ）。

## 3 node の設計シート: guidance-fix（案内を見直す役）

1. 役: 外れた頼みの道を読み、案内がどの段で閉じるべき所から逸らしたか（どこも指さなかったか）を見つけ、案内の直しを出す。読み手を責めない。
2. port: `compare.json` の外れた頼みと、その `walks.json` の行・`requests` の `closes`・`entry`・`lang`・前の回の却下。
3. 組み立ての順（`prompts/guidance-fix.md`）: `{shared:rejected}`（条件 `rejected`）・役の定義と決まりの箇条（直しの 3 種の語 `{guide}`・`{model}`・`{block}`）・`## Requests that missed` と `{misses}`（`src/steps.py` が組む頼みごとの節 `### Request <id>`）・`## Entry files` と `{entry}`・`## How to answer`・結びの 1 文。
4. 返す形: `fixes [{request, kind, where, change, why}]`。人に見せる欄は change・why（`{lang}`）。
5. 描いた骨組み: 2 節の 5 と同じく、本物の run の後に足す。
6. 今の指示との差: 新しい役。
7. 元の works と graphloops の同じ場面: firstread-loop の「直しは当てる前に別の目で叩かせ、引き金が立ったら詰まりの修繕を止めて導線そのものを疑う」に当たる。この block は直しを当てず、案を返すだけ（当てるのは持ち主か、後の PR）。
8. 受け付け: 外れた頼みの全部に 1 つ以上の直し・`kind` が 3 種のどれか・`where` が根からの相対のパス。3 回で諦める。
9. 試験: 2 節の 9 と同じ。

## 4 回す時

README の 8.6: block を作り始める前に新しい形で 1 回、その後は案内か置き場の形を変えるたび。頼みの例と閉じるべき所は README の 1.3 の歩かせから取る（例「この AI の役に確かめを 1 つ足す」は `blocks/<block>/`、「観点の block を 1 つ足す」は新しい `blocks/<block>/` と `docs/design/<block>.md`）。
