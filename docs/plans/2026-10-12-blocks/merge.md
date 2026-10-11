<!-- coldwrite:skip ASF の役が読む計画（issue の本文）。語は works-factory の docs/design.md の「語」の節で定義 -->
# merge: 取り込みのブロックを中身ごと作る（workflows/merge/ と、それだけが使う lib/ の部品と試験）

works-factory は、修正依頼を受けて確かめ済みの変更と報告を返す工場を、Archon（AI の工程を YAML で書いて回す道具）の上に作り直しているリポジトリ。前の形の「今の works」（公開リポジトリ raiki61/claude-plugins の `works/`。移す元の版は `pack.json` の `works.commit` = `2aa7c66cf7abe1fe09699ac2942d107123214168`）は、判定・計画・修正・確かめ・報告をつないだ工場で、その能力を 1 つも落とさずに、線（`workflows/line/`。ブロックを並べる 1 本の工程）・8 つのブロック（`workflows/<名>/`）・助け手（`lib/`。Archon を知らない Python）に移している。この issue は、そのうちのブロック `merge` を、フォルダの中身ごと 1 つの PR で作る。8 つのブロックは別々の run で同時に作られ、線とはブロックの返りの約束（`docs/design.md` の「ブロックの返りの約束」）だけでつながる。元のファイルは `https://raw.githubusercontent.com/raiki61/claude-plugins/2aa7c66cf7abe1fe09699ac2942d107123214168/<パス>` で読める（本文の「元」の欄の `<パス>`）。ASF は Archon の作者が作った、issue から PR までの工程の束（`docs/design.md` の「語」）。

## 読む物

- 根の `AGENTS.md`（リポジトリの形・E8〜E11・E13・E14・E18）、`workflows/AGENTS.md`（E1・E2・E4〜E7・E12・E16・E17）、`lib/AGENTS.md`（E3）、`tests/AGENTS.md`。決まりの番号 E1〜E18 の中身はそれらの文書に在る。
- `docs/design.md`: 「ブロック」の `merge` の節・「ブロックの返りの約束」の `merge` の返り・「能力の棚卸し」の `merge` の行・「受け入れの一覧」・「Archon の分かっていること」と未決 U1〜U8・「作りの順」の段 2 の `merge` の個別の行。
- `docs/plans/2026-10-12-lib-port.md` の「移し方」1〜6（この issue で `lib/` に持ってくる部品も同じ移し方に従う）。
- `docs/owner-decisions.md` のうち本文が引く決め。
- Archon の振る舞いは、ASF と同じ Archon の源（`coleam00/Archon` の commit `d97d00ef15cce4b15d39e42635e4e86996ec1351`。持ち主の決め `archon-same-as-asf`）の文書 `packages/docs-web/src/content/docs/`（特に `guides/script-nodes.md`・`guides/authoring-workflows.md`・`reference/cli.md` の dry-run と `workflow test`）で確かめる。ASF の工程は同じ commit の `.archon/workflows/sdlc/`（本文の `W`）。
- ブロックの分:
  - 元（今の works）: `works/dev/lib.sh` の関数 `works_dev_show_run` の中の python のうち、差分を組む所（`BRING_BACK` の枝。一時の index で `read-tree HEAD` → `add -A` → `diff --cached --binary <base_rev>`）。`works/dev/use.sh` の `apply`（950-971 行）と `apply_checked`（396-433 行）。`works/.shared/core/protect.py`・`protected.json`・`answer.py`（`VERBS`）・`report.py` の `FINAL_GATE_STOPS`（172 行）と `stopped_run`（648-667 行）。`works/darkfactory/lib/line_edge.py` の `_protected`（640-651 行。最後の関所を守りのファイルで必ず開く所）。
  - ASF: `W/merge-queue/archon-merge-queue.yaml`（`path-policy`:73-81・`gate` の封印・`approval`:180-190・`execute` が `approval` と `path_policy` を受け直す所）、`W/merge-queue/scripts/merge-action.ts`（:214 封印・:241-244 `authorized`・:281 digest の照らし・:337-369 読み戻し）、`W/merge-queue/README.md`:34-35、`W/README.md`:82-93（外への書き込みは 1 つの script で、読み戻せなければ落ちる）。
  - Archon: `guides/approval-nodes.md`（決めを書いた承認の節の答えは `{decision, text}`）、`W/triage/archon-triage.yaml`:110-115（指し札の `output_format` の書き方）。

## 目的と引き継ぐ能力

2 つの形で線に差し込まれる（`merge-seal`・`merge-apply`）。seal は人に見せる差分を封じ（sha256）、守りのパスの当たりを出す。apply は封じた hash を今の差分と照らし、違えば止める。同じなら外へ 1 度だけ書き、読み戻す。既定の書き先は run の置き場の差分で、対象のリポジトリへ当てるのは人（`bin/apply`。土台の計画 Task 7 で作る物で、この issue では作らない）。持ち主の決め `diff-only-to-target`（「勝手にPRをマージしたりするのは他のリポジトリで使う前提では合わなかったりしないか」）と E17。

能力の棚卸しの行:

- 差分の封印と外への書き込み（新）— 今は人が `works/dev/use.sh apply` で当てる。差分は `works/dev/lib.sh` の `works_dev_show_run` が run の worktree と始めの版 `base_rev` の差（未追跡を含む。一時の index。worktree の index は動かさない）で組む → merge・`lib/seal`（新しく書く。元のファイルが無いので lib-port-as-is の対象外。ファイル名 `lib/seal.py`）。差分を組む関数そのものは、test-gate の指紋と同じ組み方にそろえるため`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/green_cert.py` の `diff_bytes(repo, rev)` を使う（差分を組む口を 1 つにする。持ち主の決め `one-source`）
- 守りのパス — `works/.shared/core/protect.py`・`protected.json` → `lib/protected`（ファイルは元の名 `lib/protect.py`・`lib/protected.json`。eyes と merge の 2 つが読むので、`docs/plans/2026-10-12-blocks/prereq.md` の issue（ブロックの前の共有の部品）で入る。一覧の行はそこで works-factory 自身の守りのファイルに書き直される。この issue では持ってこない）
- 止めた run の差分を当てない — `works/dev/use.sh` の `apply_checked` が `report.stopped_run`（最後の関所の stop・reject、止め札、線の止め）を見て拒む → merge apply が人の答えを見て置かない（止め札は持ち主の決め `report-on-stop` で「最後の関所で止める と答えた扱い」になるので、同じ道で拒まれる）

keep-essence の 12（今の works の `works/docs/keep-essence.md`）のうち: 10「守りのファイルで最後の関所」（eyes・線と共に持つ。merge は seal が当たりを返し、apply が人の通しの答え（`approve`・`continue`）の無い当たりを機械で拒む）。受け入れの一覧（review-graph の節）に merge だけが持つ行は無い。

持ち主の決め `small-core`（「R2 が作り直しと言った run は部分を取り込まない」。当て方「R2 の作り直しの判定で merge（apply）を機械で拒む」）も apply が持つ（下の「置くかの決まり」の 4）。

## 作る物

### ブロックのフォルダ `workflows/merge/`

- `works-factory-merge.yaml`（工程の名も `works-factory-merge`。E9）:
  - `inputs:` に約束の入力を全部宣言する: `mode`（required）・`start`（required）・`diff`（required）・`fingerprint`・`green_ok`・`eyes_ok`・`sealed_hash`・`answer`・`r2`（`mode`・`start`・`diff` のほかは `default: ""`。飛ばされた値・seal の時の apply だけの値は空か `null` の字で届く）。`r2` と `diff` の null 可は、波の前に入る人の直し（本文の「人が入れる前提の直し」の 1・2）で約束に入っている。
  - `returns: merge`・`outcome_field: ok`。`interactive:` は書かない（このブロックは人の関所を持たない。最後の関所は線の `gate-final`）。
  - 節は 1 つ: `merge`（`script: merge`・`runtime: uv`・`mutates_checkout: false`・`timeout: 1728000000`・`with:` で上の入力を全部 `$INPUTS.<名>` から渡す・`output_format` は下の「返りの約束」）。作業ツリーは変えない（git の一時の index は一時のフォルダに置き、書くのは run の置き場だけ）。形の分けを YAML の `when:` で 2 本にしないのは、返す節を 1 つに保つため（`docs/design.md` の書き方の決め「2 つの形を持つブロックは、返す節を 1 つのまま mode の欄で形を返す」）。
- `commands/`: 作らない（役の節が無い。人に見せる文は線の関所が組む）。
- `scripts/merge.py`: 頭は「共通の書き方」の形。返す節は落ちない（線は落ちた返す節の先へ進めない）: script の全体を 1 つの `try` で包み、どの例外でも（知らない `mode`・壊れた入力・開けない指し札・`import` の失敗も）終了の値 0 で `ok: false`・`hash: ""`・`diff: null`・`protected_hits: null`・理由を `output_format` に合う形で返す。`mode` の欄は入力が `apply` なら `apply`、ほかは `seal`（知らない語は理由に字のまま書く）。この包みの返しは `boundary` を読めなくても書けるよう、標準ライブラリの `json` だけで組む。読む入力を JSON で開き（`""`・`null` の字は値なし）、`start` の指し札を `boundary.resolve` で開いて `base_rev` を読み、作業ツリー（節の cwd。止めた Archon は script の節を run の作業ツリー（対象のリポジトリ）を cwd にして走らせる: `packages/workflows/src/dag-executor.ts`:3822-3823 の注「the execution cwd (the target repo)」と :3886 の `runSubprocess(..., { cwd })`）と一緒に `lib/seal.py` の関数を呼ぶ。返りは `boundary.returns`、指し札は `boundary.pointer`。決まりの中身は書かない（E4）。
  - seal: `green_cert.diff_bytes(<木>, base_rev)` で今の差分を組む → `green_cert.fingerprint(<木>)` で今の木の指紋を取り（`ValueError` なら指紋が違う扱いで理由に書く）`seal.seal_refusal` に渡す（緑の認証の指紋 `fingerprint` と違えば理由。`fingerprint` が無ければ照らさない）→ `merge/sealed.diff` に `seal.write_readback` で書いて読み戻す → `protect.touched(<木>, base_rev)` を `protect.lines` で 1 行ずつにして `protected_hits` に入れる。`protect.Broken`（一覧が読めない・git が引けない）の時は `seal.unknown_row(<理由>)` の 1 行を入れる（当たりが無いとは言えない。今の works の `works/darkfactory/lib/line_edge.py`:640-651 の `_protected` が fail closed で理由を返し、最後の関所の文に「差分が一覧に触れていないとは言えない」の節を出した所と同じ向き）。
  - 入力 `diff`（fix の累積差分の指し札）は受けるが読まない。封じるのは今の木から組み直した差分で、fix の後に木が変わっていないことは緑の認証の指紋（test-gate final が fix の後の木で取り、seal と apply が今の木と照らす）が見る。
  - apply: 同じ `green_cert.diff_bytes` で今の差分を組み、`seal.digest` を取る → `protect.touched` で今の当たりを取る（`protect.Broken` なら `seal.unknown_row` の 1 行を当たりとして扱う）→ `green_cert.matches(fingerprint, <木>)` で指紋を照らす → 入力 `r2` を読む（空の字か `null` = 独立の目が R2 を省いた・走らなかった、object = `{status, reason}`）→ `seal.apply_refusal(...)` が空なら `merge/apply.diff` に `seal.write_readback` で 1 度書き、読み戻した hash で返る。理由が在れば置かず、照らしに使った今の差分を `merge/refused.diff` に書いて指し、`ok: false` と理由で返る。apply の返りの `protected_hits` は約束どおり `null`（守りの当たりは照らしに使うだけで返さない）。
  - 差分が空（全部の単位を諦めた run など）か組めない（git が落ちた・`base_rev` が無い）時は、`diff: null`・`hash: ""`・`ok: false`・理由（「差分が空」か落ちた訳）で返る（指し札は空でないファイルしか指せない。`diff` の null 可は波の前に約束に入る）。空の差分を「封じた」と言わない。
- `fixtures/`（Archon の `workflow test`。筋書きは配線だけを見る。`merge` の節は差し替える。止めた Archon の dry-run は、差し替えが節ごとに 1 つの値で、`exec-code: true` の時は空の `ARTIFACTS_DIR`・`WORKFLOW_ID=dry-run` で走る（`reference/cli.md` の dry-run の節）ので、指し札の入力と git の木を要る script の中身は通せない。中身は下の Python の試験が subprocess で通す）:
  - `seal.stubs.yaml`: `fixture.inputs` に `mode: seal` と仮の指し札。`merge` の差し替えは `{mode: seal, ok: true, hash: <64 字>, diff: {type: archon_artifact, run_id: <字>, path: merge/sealed.diff}, protected_hits: [], reason: ""}`。`expect: completed`・`reached: [merge]`。
  - `apply.stubs.yaml`: `mode: apply`・`sealed_hash`・`answer`・`r2` を与え、`{mode: apply, ok: true, ..., path: merge/apply.diff, protected_hits: null, reason: ""}`。`expect: completed`・`reached: [merge]`。
  - `apply-refused.stubs.yaml`: 差し替えの返りが `ok: false`・`path: merge/refused.diff`・理由つき。`expect: completed`（run の終わりと仕事の結末は別の事実。ASF の A2）。
  - `empty-diff.stubs.yaml`: 差し替えの返りが `diff: null`・`hash: ""`・`ok: false`。`expect: completed`（`diff` の null が `output_format` に通ることの確かめ）。

### lib/ に持ってくる部品（このブロックだけが使う物）

今の works から持ってくる部品は無い（差分を組む所は今の works では殻 `works/dev/lib.sh` の中の python で、モジュールが無い）。新しく 1 つ書く:

- `lib/seal.py`（新）。Archon を知らない（E3。`archon`・`ARTIFACTS_DIR`・`output_type` などの字を書かない）。標準ライブラリと lib の `answer`（答えの語）だけを読む。差分を組む・指紋を取る関数は持たない（`docs/plans/2026-10-12-blocks/prereq.md` の issue の `lib/green_cert.py` を script が呼ぶ）。口:
  - `class SealError(Exception)`: 書けない・読み戻しが合わない。
  - `digest(data: bytes) -> str`: sha256 の 16 進 64 字。
  - `write_readback(path, data: bytes) -> str`: 書いて読み戻し、`digest` が合えば読み戻した hash を返す。合わなければ `SealError`（書けたと言わない。E6）。
  - `seal_refusal(*, fingerprint, current_fingerprint) -> str`: 封じてよいかの理由（空なら封じてよい）。`fingerprint` が在って `current_fingerprint` と違えば（`current_fingerprint` が取れなかった時も）「緑の認証の指紋が今の木と違う（test-gate の後に作業ツリーが変わった）」。
  - `unknown_row(reason: str) -> str`: 守りのパスを確かめられなかった時の 1 行（「守りのパスを確かめられない（差分が一覧に触れていないとは言えない）: <理由>」。今の works の `line_edge.py` の `PROTECTED_UNKNOWN` の文の向き）。
  - `apply_refusal(*, sealed_hash, current_hash, answer, green_ok, eyes_ok, r2, fingerprint_ok, protected) -> str`: 置いてよいかの理由（空なら置く）。`r2` は `None` か `{status, reason}`。`protected` は守りの当たりの行（`unknown_row` の行も当たりとして数える）。下の「置くかの決まり」の表をそのまま持つ。
  - 答えの語: `PASS = ("approve", answer.VERBS[0])`（通す。`approve` は止めた Archon の承認の節が `decisions` に求める語（`guides/approval-nodes.md`）、`continue` は今の works の答えの語 `lib/answer.py` の `VERBS`）・`STOPS = (answer.VERBS[1], "reject")`（止める。`reject` は今の works の `report.FINAL_GATE_STOPS`）。止め札は `text` が `request:` で始まる止める語（今の works の `report.REQUEST_BY`）。`PASS` の外の語は、`STOPS` でも知らない語でも全部「通さない」。
  - `REDESIGN = "redesign-needed"`: R2 の作り直しの語（eyes の返りの `r2.status` の enum `pass`・`redesign-needed`・`unverifiable` の 1 つ）。`unverifiable`（R2 の節が落ちた・独立設計が無い）は機械では拒まず、人の答えに任せる。
- 置くかの決まり（`apply_refusal`。上から順に見て最初の理由を返す）:
  1. `sealed_hash` が空 → 「封じた hash が無い（seal が走っていない）」
  2. `current_hash != sealed_hash` → 「封じた差分と今の差分が違う」（ASF の `merge-action.ts`:281 の型）
  3. 答えが在り、`decision` が `PASS` のどれでもない → 「最後の関所で <語> と答えた」（止め札も持ち主の決め `report-on-stop` でここに来る）
  4. 持ち主の決め `small-core`（「R2 が作り直しと言った run は部分を取り込まない」）: `r2` が object で `status` が `REDESIGN` → 「R2 が作り直しと言った（部分を取り込まない）」。人の通しの答えでも拒む。拒むのはこの語だけで、`unverifiable` とほかの目（R1・R3・R4）の阻害は人の答えに任せる（持ち主の決め `superset`: 今の works より多くは拒まない。今の works は目の阻害でも人が当てられた）。封じた差分は seal の指し札の先 `merge/sealed.diff` に残り、人は見られる。
  5. 答えが無い（関所が開かなかった）のに、`green_ok` が偽・`eyes_ok` が偽・`fingerprint_ok` が偽・`protected` が空でない のどれか → 「人の通しの答えが無いのに <どれ>」（守りのパスは人の通しの答えだけが通す。今の works の `protected.json` の about。ASF の `execute` が `path_policy` を受け直す型）
- 答えが `PASS` なら、緑でなくても・R2 の作り直しのほかの目の阻害でも置く（今の works は最後のテストが赤でも、目が阻害でも人が当てられた。`works/darkfactory/darkfactory.yaml` の最後の関所と `use.sh apply`）。

### 試験

- `lib/tests/test_seal.py`（新）。試験の木は `from tests.bin.gitkit import git` で一時のリポジトリに作る。`lib/` は `sys.path` の後ろに足す（`tests/AGENTS.md`）。
  - `digest`。
  - `write_readback`: 書いた物の hash が返る／読み戻しが違う時（書いた後に中身を替える偽の書き手）`SealError`。
  - `seal_refusal`: 指紋が同じ・違う・取れなかった・認証の指紋が無い。`unknown_row` の文の頭。
  - `apply_refusal`: 上の決まりの 1〜5 と「通しの答えなら赤でも・R1 の阻害でも置く」を 1 行ずつ。答えの語 `approve`・`continue` で通す。`stop`・`reject`・`hold`・空の dict・`text` が `request:` で始まる `stop`（止め札）で拒む。`r2` の形ごと（`None` で eyes_ok 偽と通しの答え → 置く・`unverifiable` と通しの答え → 置く・`redesign-needed` と通しの答え → 拒む・`pass` と通しの答え → 置く・答え無しで eyes_ok 偽 → 拒む）。`protected` が `unknown_row` の 1 行だけで答え無し → 拒む。
- `tests/workflows/test_merge.py`（新。PyYAML で YAML を読み、Archon を起こさない）:
  - YAML の形: 名が `works-factory-merge`・`returns: merge`・`outcome_field: ok`・節が `merge` の 1 つ・`mutates_checkout: false`・`timeout: 1728000000`・`output_format` の `properties` の名の集まりが約束の 6 欄ちょうどで全部 `required`・`additionalProperties: false`・`ok` が boolean・`protected_hits` が null を取る・`inputs:` の名の集まりが約束の 9 つ（`r2` を含む）ちょうど・`diff` が null を取る・`approval:` の節が無い。
  - script を通しで走らせる（`subprocess` で `scripts/merge.py` を、一時の git の木を cwd、`WORKFLOW_ID`・`ARTIFACTS_DIR`・`INPUTS_*` を環境にして。始めの記録の `start.json` と fix の差分は一時の置き場に置き、`boundary.pointer` の形の JSON を入力にする）:
    - seal: 返りの `hash` が `merge/sealed.diff` の sha256 と同じ・`ok` が真・`reason` が空。
    - seal: 指紋が違う（入力の `fingerprint` を変える）→ `ok` が偽で理由が在り、差分は書かれている。
    - seal: 守りの一覧が読めない（試験の中で `protect.MANIFEST` を壊れたファイルに替える）→ `protected_hits` が `unknown_row` の 1 行。続く apply が答え無しなら置かない。
    - seal: 守りの一覧の行に当たるファイルを作った木 → `protected_hits` に 1 行（当てる行は `protect.load()` の最初の字のままのパスの行から選ぶ。一覧の中身に試験を縛らない）。
    - apply: seal と同じ木・答え `{"decision": "continue", "text": ""}` → `ok` 真・`merge/apply.diff` が在り hash が封じた物と同じ。
    - apply: seal の後に木を変える → `ok` 偽・「封じた差分と今の差分が違う」・`merge/apply.diff` が無い・`merge/refused.diff` が在る。
    - apply: 答え `stop` → 置かない。答え無し（`null`）で `green_ok` 偽 → 置かない。答え無しで守りの当たり在り → 置かない。`r2` が `{"status": "unverifiable", "reason": "…"}` で `eyes_ok` 偽・答え `approve` → 置く。`r2` が `redesign-needed` で答え `continue` → 置かない。
    - 返す節は落ちない（subprocess で壊れた入力を与え、どれも終了の値 0 で、返りの JSON が `output_format` に合い（PyYAML で読んだ YAML の `output_format` の欄・型・enum で照らす）`ok` が偽で理由が在る）: 知らない `mode`（`merge`）・`mode` が空・`start` が JSON でない・`start` がほかの run の指し札・始めの記録に `base_rev` が無い・`answer` が JSON でない・`r2` が JSON でない・作業ツリーが git でない。差分が空 → `diff` が `null`・`ok` 偽・`hash` が空。
    - 筋書きを Archon で回す（`tests/archon.py` の使い捨ての木。その木には `workflows/merge/` と `.shared/` だけを置く）: `fixtures/` の筋書きが全部通る。止めた Archon の源が無ければ `tests/archon.py` が `skipTest("Archon の源が無い: ...")` で見送る。
    - 書き込み（E6）: 作業ツリーの `git status --porcelain` が script の前後で同じ。

## 返りの約束（`docs/design.md`「ブロックの返りの約束」の `merge` の返りのまま）

- 返す節 `merge`・`outcome_field: ok`（ASF の `W/merge-queue/archon-merge-queue.yaml` の封印と読み戻し）
- 既定は E17: apply は封じた差分を run の置き場に置くだけ。対象のリポジトリへ当てるのは人（`bin/apply`）。
- 入力（`with:`）:
  - `mode`: `seal`（`merge-seal`）・`apply`（`merge-apply`）
  - `start` ← `$start.output.record`
  - `diff` ← `$fix.output.diff`
  - `fingerprint` ← `$test-gate-final.output.fingerprint`、`green_ok` ← `$test-gate-final.output.ok`
  - `eyes_ok` ← `$eyes.output.ok`
  - `sealed_hash` ← `$merge-seal.output.hash`（apply だけ。seal は null）
  - `answer` ← `{ from: "$gate-final.output", if_skipped: null }`（apply だけ）
  - `r2` ← `{ from: "$eyes.output.r2", if_skipped: null }`（apply だけ。波の前に入る人の直しの 1 で約束に入る）
- 返り:
  - `mode`（string）: `seal`・`apply` → report
  - `ok`（boolean）: seal は差分を封じた。apply は封じた hash と今の差分が合い、置いて読み戻せた → 線 11（seal）・report
  - `hash`（string）: seal は封じた差分の sha256。apply は読み戻した差分の sha256 → 線 11・merge（apply が照らす）
  - `diff`（指し札・null 可）: seal は封じた差分。apply は置いた先（人が `bin/apply` で当てる物）。差分が空か組めない時は null（`ok` は false、`reason` に訳）→ report（null 可は波の前に入る人の直しの 2 で約束に入る）
  - `protected_hits`（array of string・null 可）: 守りのパスの当たり。seal だけ → 線 11
  - `reason`（string）: ok が false の訳（hash の食い違いなど）。ok なら `""` → report
- 書き方: `mode` は `enum: [seal, apply]`。`diff` は `type: [object, "null"]` で、object の時 `{type: {type: string, enum: [archon_artifact]}, run_id: {type: string}, path: {type: string, enum: [merge/sealed.diff, merge/apply.diff, merge/refused.diff]}}`（`required` に 3 つ。`W/triage/archon-triage.yaml`:110-115 の形）。置き場の名を形ごとに分けるのは、同じ run の中で seal と apply が同じ置き場を使うため（include ごとに置き場が分かれるかは未決 U2）。apply が置かなかった時の `diff` は `merge/refused.diff`（照らしに使った今の差分。何が置かれなかったかを人が見る）、`hash` はその sha256。
- 返す節の `output_format` は、上の欄をちょうど持つ（全部 `required`・`additionalProperties: false`）。欄を足す・名を変える・型を変える・欄を落とすのは線との約束を変えることなので、この PR ではしない。要ると分かったら PR の本文の「約束を変える頼み」に書き、約束どおりの形で作り終える。

## 共通の書き方

- script の節は名指しの script（`script: <名>`・`runtime: uv`・ファイルは `scripts/<名>.py`）。頭で境の口と lib/ を次の形で読む（Archon の `guides/script-nodes.md` の「Share code within a pack」の Python の形。パスの字に `../` を書かないので E4 の照らしに当たらない）:
  ```python
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".shared"))
  import boundary
  sys.path.append(str(boundary.lib_root()))
  ```
  入力は `os.environ["INPUTS_<名>"]` を字のまま読む（名前を組まない。issue #11）。返りは `boundary.returns(...)`、指し札は `boundary.pointer(...)`・`boundary.resolve(...)`。確かめの中身は書かず、lib/ の関数を呼ぶだけ（E4）。
- 始めの記録は入力 `start`（指し札）で受け、`boundary.resolve` で開いて JSON で読む。欄の形は `lib/startrec.py`。
- 期限: 期限を持つ節（`script:`・`bash:` の `timeout`、`prompt:`・`command:` の `idle_timeout`、`loop:` の `idle_timeout` と `timeout`、`loop_group:` の `timeout`、`approval:` の `idle_timeout`）には全部 `1728000000` を書く（E12）。
- 役の節の `model:`・`effort:` は今の works の `works/.shared/core/stage-models.json` と役の前付け（`works/.shared/core/agents/`）の値を写す（持ち主の決め `model-effort`）。
- 役の指示書（`commands/`）と `lib/` に、対象の言語・テストの実行器の名を書かない（E13）。持ち主の環境の字（`raiki61`・`/Users/` など）を書かない（E14）。
- 外への書き込み（GitHub・対象のリポジトリの main・人に見える所）は、このブロックでは 1 つの script の節 `merge` だけ（apply の形の時の `merge/apply.diff`。人が `bin/apply` で当てる物）。書いた後に読み戻す（E6）。`gh`・`git push`・`git merge` は呼ばない。
- ブロックの YAML と script は、ほかのブロックのフォルダを指さない（E4）。ほかのブロックの返りは `with:` の入力として受けるだけ。
- 筋書き（fixture）は Archon の `workflow test` の形（`fixtures/<名>.stubs.yaml`。予約の鍵 `fixture:`（`expect`・`fail-node`・`reached`・`inputs`・`resolved-text-contains`）と `exec-code:`、残りの鍵は節の id → 差し替えの出力）。script の中身まで通したい筋書きは `exec-code: true`。
- ブロックの YAML の形の試験（`tests/workflows/test_<名>.py`）は PyYAML で YAML を読み、Archon を起こさない。筋書きは同じ `tests/workflows/test_<名>.py` が、issue #47（P0）の `tests/archon.py` の使い捨ての木（そのブロックのフォルダと `.shared/` だけを置く）で `archon workflow test` を走らせて回す。

## Archon で書けない所

無し。封印・照らし・書き込みと読み戻しは script の節、人の答えは線の承認の節（`{decision, text}`）、飛ばされた関所は `if_skipped: null` で書ける。線が include の入力に `if_skipped` を通せない穴（`docs/polyfills.md` の P2）は線の側の埋めで、merge は `answer` を `""`・`null` の字の時に「答え無し」と読むだけ。

## E11 の 3 つの答え

1. Archon が持っているか: 差分の封印・照らし・置き場への書き込みは持たない（script の節で書く）。人の答えの形（`approval` の `decisions`）と run の置き場（指し札）は Archon の物を使う。
2. ASF が持っているか: `W/merge-queue/` の封印（`gate` の `plan_digest` を `execute` が照らす）・守りのパス（`path-policy`）・書いた後の読み戻し（`merge-action.ts`:337-369）。型を採り、コードは写さない（E8）。違い: 封じる物は PR の計画でなく run の差分（始めの版 `base_rev` から今の作業ツリーまで）、書き先は GitHub でなく run の置き場。
3. 本当に要るか: 能力の棚卸しの「差分の封印と外への書き込み（新）」「守りのパス」、keep-essence の 10、持ち主の決め `small-core`・`diff-only-to-target`・`report-on-stop`。

## 受け入れ

1. 試験を先に入れて赤を見る（lib/ の部品が無い・YAML が無い）。その後で部品と YAML を入れて緑。赤と緑の出力の要約を PR に書く。
2. リポジトリの根からの全部の試験 `uv run --isolated python3 -m unittest discover -s . -t .` が緑。`tests/layers/` の層の試験（その時に在る物全部）も緑のまま。
3. Archon の源が在る所で `archon workflow test workflows/merge` の筋書きが全部通る。在る所で `archon validate workflows` に `works-factory-merge` の誤りも警告も無い。Archon が無い所では、筋書きを回す試験は名前つきで見送られる（`tests/archon.py` の `skipTest("Archon の源が無い: ...")`）。PR には、Archon で回した結果か、回せなかった訳を書く。
4. 持ってきた lib/ のファイルを元と比べた差分が、lib-port の「移し方」1〜5 で決めた直しだけ。（この issue は今の works から持ってくるファイルが無いので、当たる物は無い。`lib/seal.py` は新しいファイル。）
5. PR の本文に次を並べる（守りのパスの文書に書く代わり。土台の持ち主が `docs/design.md`・`docs/asf-notes.md` に写す）:
   - lib-port の「移し方」6 の 4 つ（元のパス → 置いた先・外した物と理由・言い換えた行・盤面の物を引数で受ける関数の一覧）。この issue では「持ってきた物は無い。`lib/seal.py` は新しく書いた。組み方の元は `works/dev/lib.sh` の `works_dev_show_run`」と書く。
   - 採った ASF の型（`docs/asf-notes.md` の「書き方」の 4 行の形）。A5・A6・A7 の「採った先」に merge の何を当てたか。
   - 「能力の棚卸し」と「受け入れの一覧」のこのブロックの行ごとの、証の試験か筋書きの名
   - 約束を変える頼み・使いたかった埋め（あれば）
6. ブロックの分（`docs/design.md` の段 2 の `merge` の行）:
   - seal と apply の 2 つの形が 1 つの返す節（`merge`）と `mode` の欄で返る。
   - 封じた hash と今の差分が違えば apply は止まる（置かない。`ok: false`・理由）。
   - 外への書き込みは 1 つの script の節（`merge`）で、書いた後に読み戻す（読み戻しの hash が違えば書けたと言わない）。
   - 守りのパスの当たりは人に回す（seal が `protected_hits` で線 11 に返し、apply は人の通しの答え（`approve`・`continue`）の無い当たりを置かない）。
   - 作業ツリーを変えない（`mutates_checkout: false` と、前後の `git status` が同じ試験）。
   - 返す節 `merge` は落ちない（どの壊れた入力でも終了の値 0 で `ok: false`・理由。subprocess の試験）。

## 範囲

- 作るのは `workflows/merge/` の下・本文の「lib/ に持ってくる部品」の lib/ のファイル・本文の「試験」のファイルだけ。
- 触らない（守りのパス。ASF の merge が人の手に残す）: `workflows/line/**`・`workflows/.shared/**`・`docs/design.md`・`docs/owner-decisions.md`・全部の `AGENTS.md`・`pack.json`・`README.md`・`MISSION.md`・`engineering.md`・`.github/**`・`harness/**`・`factory/**`・`.factory/**`。
- 触らない（同じ時に別の run が作る）: ほかの 7 つのブロックのフォルダ（`workflows/<ほかの名>/`）と、それらの issue が名指す lib/・試験のファイル。ほかの PR と同じファイルを作らない。
- 触らない（前に入る物）: lib-port と`docs/plans/2026-10-12-blocks/prereq.md` の issue で入った lib/ のファイル（本文の「依存」に並べた物）とその試験、`tests/workflows/__init__.py`・`tests/archon.py`、`pyproject.toml`、`docs/`（PR の本文に書く。上の受け入れ 5）。持ってきた部品の中で前提の部品に直しが要ると分かったら、直さず PR の本文に書く。
- 決めた範囲で能力を落とす直しが要ると分かったら（持ち主の決め `superset`・`no-narrow`）、止めて PR の本文に書く。
- 作るファイル（これだけ）:
  ```text
  workflows/merge/**
  lib/seal.py
  lib/tests/test_seal.py
  tests/workflows/test_merge.py
  ```
  `workflows/merge/**` の中身は `works-factory-merge.yaml`・`scripts/merge.py`・`fixtures/seal.stubs.yaml`・`fixtures/apply.stubs.yaml`・`fixtures/apply-refused.stubs.yaml`・`fixtures/empty-diff.stubs.yaml`。
- このブロックの外の事: `bin/apply`（封じた hash を照らして対象に当てる口。今の works の `apply_checked` の確かめ: 消す行の許し・止めた run・`git apply --check`）は土台の計画 Task 7。PR を作る・merge する道（E17 の「使う人が選んだ時だけ働く道」）は今の works に無いので、この issue では作らない（置き換えの後の足し。`docs/design.md` の merge の節）。最後の関所を開くか（無人の方針・守りの当たりで必ず開く）は線。

## 依存

- 前に入る人の直し（守りのパスの文書。この issue より前に main に入るので、中身はリポジトリのそこを読む）:
  - H1: `tests/workflows/`（ブロックの YAML の形と筋書きの試験の置き場）をリポジトリの形の木に載せる（根の `AGENTS.md`・`tests/AGENTS.md`）。
  - H2: report の返す節に boolean の `ok` を足し、`outcome_field: ok` にする。結末の 10 語 `outcome` は別の string の欄のまま（`docs/design.md` の「report の返り」。止めた Archon の `outcome_field` は `required` の boolean しか受けない）。
  - H3: 段 2 の共通の受け入れ 4・5（ASF の型・証の名）を「PR の本文に書き、土台の持ち主が `docs/` に写す」に直す（`docs/design.md` の「作りの順」）。
  - H4: E13 の例外。拡張子と言語の対応・テストのファイルの名の慣習の表と、その表を作る標準ライブラリの import を、`lib/impact.py`・`lib/changemap.py`・`lib/tddloop.py`・`lib/fixrules.py`・`lib/libdocs.py`・`lib/libdocs_local.py` に限って許す（根の `AGENTS.md`。機械の表 `tests/layers/scan.py` の `ALLOWED["E13"]` には、そのファイルを入れる PR が 1 行ずつ足す）。
  - H5: ブロックをまたぐ形（`docs/design.md` の「ブロックの返りの約束」の「書き方の決め」）。
    - 指し札の先は今の works の同じ名のファイルの形。次の隣のファイルだけは約束の一部で、ほかのブロックも名で開く: `judgment`（`judgment.json`）の隣の `premises.json`・`judge-verify.json`・`pr-excluded.json`・`materials.json`、`plan`（`plan-fields.json`）の隣の `p2.fix_plan.json`、`structure`（`structure-state.json`）の隣の `design.jsonl`、`review` の隣の `gate-passes.json`。ほかの隣のファイルは作ったブロックの中だけで読む。
    - 直す前の結末のファイル: 必須の欄 `{suite, test_cmd, rev, exit, cases}`（`suite` は始めの記録の `tdd_suite` の実行ファイル。`cases` は JUnit の 1 件ごとの結末の並び）。読み書きは `lib/baseline_red.py` だけ。test-gate は自分の欄を足してよい。
    - fix の `conflicts` の先は `conflicts.json` = `{"items": […]}`（今の works の `conflict.py` の形）。
    - 型つきの成果物: `green-cert` は test-gate の返す節の出力。`tdd-unit` は fix の 1 回の差し込みに 1 つで、中身は組ごとの段の物 `[{group_id, ran, reason, suite, reused, units}]`（今の works の blk-fix の `tdd` の出口。走らなかった組も `ran: false` で載る）。`eye-verdict` は `{eye, status, reason}`（`eye` は `r1`・`r2`・`r3`・`r4`・`premise-check`）。
    - 人の関所（`approval:`）の `decisions` は `approve` を含む（Archon の決まり）。通す語は `approve`・`continue`、止める語は `stop`・`reject`。止め札は止める語で、文が `request:` で始まる物。ブロックの `stop_reason` は人の止めを `human:<所>`、止め札を `request:<所>` の形で返す。
    - 約束に無い入力は、ブロックの YAML の `inputs:` に既定値（`""`・`"null"`・`"[]"`）つきで宣言し、線が渡す前も動く形にする。返りの欄は足さない。
    - 返す節は落ちない。中の誤りを全部捕まえ、そのブロックの偽の結末（`ok: false` など）と訳を、`output_format` に合う形で返す（線は落ちた返す節の先へ進めない）。
  - H7: 始めの記録に `tdd_suite`（TDD の輪と 1 件ごとの結末に使う実行ファイルのパス。無ければ `""`）を載せる（`docs/design.md` の「線の始めの節 `start` の返り」）。
  - H8: R2 の `status` に `unverifiable`（R2 の比べの節が落ちた・独立設計が無い。前提が崩れた時は `premise_check` にも載る）を足し、merge の入力に `r2` を足し、merge の返り `diff` を null 可にする（`docs/design.md` の eyes と merge の返り）。merge は `redesign-needed` だけを人の答えに関わらず拒み、`unverifiable` は人に回す。
  - H10: E16 の機械の行を「`approval:` の節を持つ工程を起こす一番上の工程（線）に `interactive: true` が在る。差し込まれるブロックは工程の頭に `interactive`・`worktree`・`container`・`evidence_policy`・`mutates_checkout` を書かない」に直す（`workflows/AGENTS.md`。差し込まれた工程の頭のこれらの鍵は Archon が読み込みの警告つきで捨てる）。
- 前に入る PR: issue #47（P0。工程の読み込みの pack の形 `.archon/workflows/works-factory/<ブロック>/`・script が lib/ を見つける道 `boundary.lib_root()`（`WORKS_FACTORY_ROOT`。未決 U5）・Archon の要る試験の助け `tests/archon.py`・CI の Archon の源）と、`docs/plans/2026-10-12-blocks/prereq.md` の issue（2 つ以上のブロックが読む lib/ の部品と `tests/workflows/__init__.py`）。

- main に在る物（lib-port の PR と`docs/plans/2026-10-12-blocks/prereq.md` の issue）:
  - lib-port: `lib/accept.py`（`touched_files`。`protect` が読む）・`lib/planmarks.py`（`glob_match`。`protect` が読む）・`lib/startrec.py`（始めの記録の欄の形）・`lib/answer.py`（答えの語 `VERBS`）。
  - `docs/plans/2026-10-12-blocks/prereq.md` の issue（ブロックの前の共有の部品）: `lib/protect.py`・`lib/protected.json`（守りのパス。行は works-factory 自身の守りのファイルに書き直される。eyes も読む）・`lib/tests/test_protect.py`、`lib/green_cert.py`（`diff_bytes(repo, rev) -> bytes`（差分を組む口 1 つ。未追跡を含み、作業ツリーの index と HEAD を動かさない）・`fingerprint(repo) -> {head, diff_hash}`・`matches(cert_fingerprint, repo) -> bool`。test-gate が認証に入れ、merge が封じる差分と今の木の照らしに使う）、`tests/workflows/__init__.py`。
  - issue #47（P0。8 本より先に入る）: `tests/archon.py`（止めた Archon の源と bun を見つけ、無ければ `skipTest("Archon の源が無い: ...")`。名指した工程のフォルダと `.shared/` だけを `.archon/workflows/works-factory/` の下に置いた使い捨ての git の木で、使い捨ての `ARCHON_HOME` と `WORKS_FACTORY_ROOT` で Archon を走らせる）・pack の置き方（`place.workflow_source` が `.archon/workflows/works-factory/<ブロック>/` にする）・未決 U5（`boundary.lib_root()` が `WORKS_FACTORY_ROOT` を読む）・CI が Archon の源と bun を取る事・`archon validate` の層の試験。
  - 置き方の要点: ブロックは packaged workflow（`.archon/workflows/works-factory/` → リポジトリの `workflows/`。pack は works-factory、工程のフォルダはブロック）として読まれ、名指しの script は `workflows/merge/scripts/` から、境の口は pack の `.shared/` から読める。script から lib/ に届く道（未決 U5）はissue #47（P0）が決める。このブロックは `boundary.lib_root()` を呼ぶだけ。
  - `tests/bin/gitkit.py`（試験の木）・`workflows/.shared/boundary.py`（境の口）。
- 前に入る人の直し（このブロックだけ。波の前に入る）: 本文の「人が入れる前提の直し」の 1（入力 `r2`）・2（`diff` の null 可）。
- ほかのブロック: 待たない。ほかのブロックの返りは線の `with:` で入力として届くだけで、このブロックの試験はその形の入力を筋書きと試験の中で作る。

## 人が入れる前提の直し

共通の前提は本文の「依存」の前に入る人の直し（H1〜H5。最後の関所の答えの語と止め札の形は H5）。このブロックだけの物。どれも 8 本の波の前に入り、この issue はそれが入った約束で作る:

1. 入力 `r2` を約束に足す。`docs/design.md`「merge の返り」の入力の `answer` の行の次に 1 行足す:
   「`r2` ← `{ from: "$eyes.output.r2", if_skipped: null }`（apply だけ。seal は渡さない）。R2 が `redesign-needed` なら人の答えに関わらず置かない（持ち主の決め `small-core`）。`unverifiable` とほかの目の阻害は人の答えに任せる」
   線の `merge-apply` の `with:` にも同じ物を足す（`workflows/line/works-factory-line.yaml`）。訳: 約束の `eyes_ok` だけでは R2 の作り直しとほかの目の阻害を分けられない。R2 の作り直しだけを機械で拒み、ほかは今の works と同じく人に任せる（持ち主の決め `superset`）。
2. `diff` を null 可にする。`docs/design.md`「merge の返り」の返りの行「`diff`（指し札）: seal は封じた差分。apply は置いた先（人が `bin/apply` で当てる物）→ report」を次に替える:
   「`diff`（指し札・null 可）: seal は封じた差分。apply は置いた先（人が `bin/apply` で当てる物）。差分が空か組めない時は null（`ok` は false、`reason` に訳）→ report」
   訳: Archon の指し札は空でないファイルしか指せないので、差分が空（全部の単位を諦めた run）・組めない時を返りで表すには null が要る。
