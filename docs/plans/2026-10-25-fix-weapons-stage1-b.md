# 直し方の型の段 1・PR B の実装の控え（受付 20261025-095016-54abf0）

- 何の話か: 設計の下書き [2026-10-24-fix-weapons.md](2026-10-24-fix-weapons.md)（以下「下書き」）の 4.4 の作る物 9（修正役の指示を付録 A の行き先どおりに型ごとの書き手へ移す）と、PR A（#869）が PR B に回した物のうち頼みが名指す物を作る PR B の、実装の部署の控え。PR A の控えは [2026-10-25-fix-weapons-stage1-a.md](2026-10-25-fix-weapons-stage1-a.md)。
- この控えに書く物: 下書きが黙っていた所で実装の部署が決めた事（持ち主・窓口が覆せる）と、どの commit で何を閉じたか。会話は納品のたびに空になるので、続きはここと PR の本文から読み直す。

## 1 形の決め（実装の部署の決め。持ち主が覆せる）

1. 型ごとの書き手の node を置く。組の子（1 回目の段）は `tdd-close`・`pin`・`tidy`・`static`・`variant`・`remove`、親（裁定の後の段）は `pin-ruled`・`tidy-ruled`・`static-ruled`・`variant-ruled`・`remove-ruled`。どれも返答の形は今の修正役の形（`*fix_reply`）に `evidence.kinds` を足した物で、必須の欄と空にできない欄を減らさない。
2. 型を 1 つずつ順に回す: 外の輪 `writers-loop`（`fresh_context: true`。1 周が型 1 つ）の中に、今の修正の輪 `fix-loop`（`fresh_context: false`）を入れ子に置く。外の輪の頭の script `writer-pick` が、注文の在る型を `WRITER_SEQUENCE` の順に 1 つ選んで置き場の `writer.json` に書き、その型の段の頭（段の頭の木・除くパスの姿・注文の `since`）を控え直す。内の輪の中では、書き手の node を 1 本の鎖（どの層も node 1 つ）に並べ、`fix-prep` が返す型の名で `when:` が 1 つだけを起こす。
   - 訳: 書き手を同じ層に並べると Archon が並んだ層として会話を切る（今の `ConversationCase`）。型ごとに別の輪を YAML に 6 本書くと node が 36 増える。入れ子にすると、内の輪の 1 周目はいつも新しい会話で起き（`dag-executor.ts` の「i === 1 ? undefined」）、型の中の出し直しは同じ会話を継ぐ。型どうしは会話を分け合わない。
   - 順: 1 回目の段は tdd の輪の後に `tdd-close` → `pin` → `tidy` → `static` → `variant` → `remove`（PR A の「tdd の輪が先」を保ち、残りは箱の順）。依存の辺での並べ替えはしない（22.6 の残り。守れない対は今の `unsatisfied` が名で書く）。
3. tdd の輪の単位の `changes` の行は、tdd の型の閉じの書き手 `tdd-close` が書く（下書き 3.1 の「輪が自分で changes を書く」を、fix の段の返答に欄を足す形でなく、輪の後の tdd の型の node で受けた）。訳: 周の全体の欄（`plan_faces`・`interactions`・`wrote_refs` など）は返し全体への答えで、段ごとの返答には置き場が無い。tdd の段の返答の形（段で欄が変わる 1 つの形）に必須の欄を足すと、段ごとに必須を変えられない（`anyOf` は形の検査が拒む）。`tdd-close` は今の修正役の、TDD の後に写す役目だけを tdd の型の側に移した物で、起こす AI の数は今と同じ（今の修正役は止めの無い組でいつも起きた）。修正役（variant ほか）からは TDD の要約を読む指示を全部外した（付録 A の F26 前半・F107・G14）。
4. 型ごとの状態: 拒否の控えと回の数え（`fix-accept-<型>`・`fix-ruled-accept-<型>`）・渡した証拠の控え（`<node>-delivered.json`）・段の頭の木は型ごと。受け付けの直す義務は、その型の注文の単位（組の直す義務との積）。受けた返答・単位の結末・閉鎖の表・数え直しの件数は、型ごとに受けた物を単位で重ねる（後の型が前の型の行を消さない）。範囲の相談の枠は段で 1 つ（今のまま）。
5. 指示の文の置き場: 今の `parts/fixer.md` を `parts/writer-top.md`（頭の材料の節）と `parts/writer.md`（決まりの本体）に割り、型ごとの頭（役の定義。付録 A の F21「型ごとの頭に言い直す」）を `parts/<型>.md` に置く。node の md は `{part:<型>}` の 1 行。型だけの文（variant の下請けの節・F123 の壊して赤・F135・変える段の申し出 `not_red` と brief の決まり 4・5）は、本体の中の段落の印で、`src/prompts.py` の型の表 `WRITER_WHEN` が型から引いた真偽で選ぶ（段落の外に出すと文の並びが変わるため）。

## 2 進み（commit ごと）

- [ ] 型ごとの書き手（移し）
- [ ] 消す 11（行ごとの commit）
- [ ] アセットの試験
- [ ] PR A の残り
